"""Opt-in certainty v5 wire receipts; two named cases, no fixture descendants.

Requires this increment's immutable plan and persistent budget ledger. Layouts
belong only to parent engines. No prior real-worker suite is imported/run.
"""
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
import unittest
from uuid import uuid4

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()
from PyQt5.QtCore import QCoreApplication, QEvent, QTimer
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from core_engine import GameStatus, MinesweeperEngine
from live_analysis import OverlayKind, present_k_proposal
import live_k_policy as k
import live_policy as v1
from live_policy_job import LivePolicyJob
from live_policy_transport import PROTOCOL_VERSION


def process_identity(handle, pid):
    api = C.WinDLL('kernel32', use_last_error=True)
    api.GetProcessTimes.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
    api.GetProcessTimes.restype = W.BOOL
    times = [W.FILETIME() for _ in range(4)]
    if not api.GetProcessTimes(handle, *(C.byref(t) for t in times)):
        raise C.WinError(C.get_last_error())
    created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    return dict(pid=pid, creation_filetime_100ns=created,
                creation_utc=(datetime(1601, 1, 1, tzinfo=timezone.utc)
                              + timedelta(microseconds=created // 10)).isoformat())


def owned_processes(scope, launcher_pid):
    class Pids(C.Structure):
        _fields_ = [('assigned', W.DWORD), ('count', W.DWORD), ('pids', C.c_size_t * 32)]
    pids = Pids()
    if not scope.api.QueryInformationJobObject(scope.handle, 3, C.byref(pids), C.sizeof(pids), None):
        raise C.WinError(C.get_last_error())
    if pids.count > 32:
        raise RuntimeError('Unexpected owned tree size')
    api = scope.api
    api.OpenProcess.argtypes, api.OpenProcess.restype = [W.DWORD, W.BOOL, W.DWORD], W.HANDLE
    result = []
    for pid in pids.pids[:pids.count]:
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            raise C.WinError(C.get_last_error())
        try:
            item = process_identity(handle, pid)
            member = W.BOOL()
            if not api.IsProcessInJob(handle, scope.handle, C.byref(member)) or not member.value:
                raise RuntimeError('Owned PID membership not confirmed')
            item.update(role='launcher' if pid == launcher_pid else 'owned runtime interpreter',
                        membership_verified=True, fixture_descendant=False)
            result.append(item)
        finally:
            api.CloseHandle(handle)
    return result


@unittest.skipUnless(os.environ.get('MINESWEEPER_K_CERTAINTY_PROCESS_PLAN'), 'Requires certainty process plan')
class LiveKCertaintyProcessTests(unittest.TestCase):
    ownership_unclear = False

    @classmethod
    def setUpClass(cls):
        if os.name != 'nt':
            raise unittest.SkipTest('Windows containment only')
        cls.app = QApplication.instance() or QApplication([])
        cls.plan = json.loads(Path(os.environ['MINESWEEPER_K_CERTAINTY_PROCESS_PLAN']).read_text('utf-8-sig'))
        cls.ledger_path = Path(os.environ['MINESWEEPER_K_CERTAINTY_PROCESS_LEDGER'])
        if cls.plan['identity'] != 'MAIN_LIVE_K_CERTAINTY_DISPLAY_P01':
            raise RuntimeError('Wrong increment plan')

    def setUp(self):
        self.assertFalse(type(self).ownership_unclear)
        self.case = next(c for c in self.plan['cases'] if c['id'] == self.id())
        self.ledger = json.loads(self.ledger_path.read_text('utf-8-sig'))
        self.assertEqual(self.ledger['identity'], self.plan['identity'])
        self.assertFalse(self.ledger['stop_further_starts'])
        self.started = time.monotonic()
        self.receipt = dict(case=self.id(), attempt=1, owner_start_attempts=0, owner_starts=0,
                            fixture_descendants=0, actions=[], wire=[], wire_version=PROTOCOL_VERSION)
        self.ledger['receipts'].append(self.receipt)
        self.job = LivePolicyJob()
        self.process = self.scope = self.directory = None
        self.beats, self.max_gap, self.last_beat = 0, 0.0, self.started
        self.heartbeat = QTimer()
        self.heartbeat.setInterval(10)
        self.heartbeat.timeout.connect(self.beat)
        self.heartbeat.start()
        self.addCleanup(self.cleanup_owned)
        self.save()

    def save(self):
        self.ledger_path.write_text(json.dumps(self.ledger, indent=2), 'utf-8')

    def beat(self):
        now = time.monotonic()
        self.max_gap = max(self.max_gap, now - self.last_beat)
        self.last_beat, self.beats = now, self.beats + 1

    def until(self, condition):
        while not condition():
            self.assertLess(time.monotonic() - self.started, self.plan['case_cap_seconds'])
            self.assertLess(time.monotonic(), self.ledger['deadline_monotonic'])
            self.assertLess(time.time(), self.ledger['deadline_utc_epoch'])
            QTest.qWait(10)

    def capture_wire(self):
        if self.directory is not None and self.directory.exists():
            # Public JSON only; terminal proof is job_record.terminal after strict
            # parsing. Cleanup may remove FINISHED before this sampling point.
            for path in sorted(self.directory.glob('*.json')):
                if path.name not in {item['file'] for item in self.receipt['wire']}:
                    self.receipt['wire'].append(dict(file=path.name, message=json.loads(path.read_text('utf-8'))))

    def launch(self, state):
        self.assertEqual(PROTOCOL_VERSION, 5)
        self.assertLess(self.ledger['owner_start_attempts'], self.plan['planned_owner_starts'])
        self.assertLess(self.ledger['owner_start_attempts'], self.plan['max_owner_starts'])
        self.assertEqual(self.ledger['case_attempts'].get(self.id(), 0), 0)
        if self.ledger['first_start_utc_epoch'] is None:
            now, mono = time.time(), time.monotonic()
            self.ledger.update(first_start_utc_epoch=now, first_start_monotonic=mono,
                               deadline_utc_epoch=now + self.plan['campaign_cap_seconds'],
                               deadline_monotonic=mono + self.plan['campaign_cap_seconds'])
        self.assertLess(time.time(), self.ledger['deadline_utc_epoch'])
        self.ledger['owner_start_attempts'] += 1
        self.ledger['case_attempts'][self.id()] = 1
        self.receipt['owner_start_attempts'] = 1
        self.save()  # Budget/deadline persisted before production launch.
        self.job.start(state)
        self.process, self.scope, self.directory = self.job._process, self.job._scope, self.job._directory
        if self.process is None:
            self.ledger['stop_further_starts'] = True
            self.receipt['startup_error'] = 'No handle returned; creation count is not inferred from exception'
            self.save()
            self.fail(self.job.last_record)
        self.ledger['owner_starts'] += 1
        self.receipt.update(owner_starts=1, launcher=process_identity(int(self.process._handle), self.process.pid),
                            scope_name=self.scope.name, private_directory=str(self.directory))
        self.save()
        self.until(lambda: self.job.state in ('pending', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'pending', self.job.last_record)
        self.receipt['owned_processes'] = owned_processes(self.scope, self.process.pid)
        self.receipt['active_tree_when_pending'] = self.scope.active_count
        self.capture_wire()
        self.save()

    def validate(self):
        p = self.job.pending
        self.job.validate_pending(p.snapshot, uuid4().hex)
        self.until(lambda: self.job.state in ('admitted', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'admitted', self.job.last_record)
        self.capture_wire()
        return self.job._permit

    def actual_step(self, engine, permit=None):
        p = self.job.pending
        self.assertLess(len(self.receipt['actions']), self.case['input_cap'])
        self.job.mark_applying(p.token, permit.nonce) if permit else self.job.mark_applying(p.token)
        engine.step(p.x, p.y, p.move.action)
        status = engine.status
        observation = engine.get_observation() if status == GameStatus.PLAYING else None
        self.job.acknowledge(status.name, observation)
        ack = self.job._sent_ack
        self.receipt['actions'].append(dict(proposal=k.to_dict(p) if permit else v1.proposal_to_dict(p),
                                             ack=k.to_dict(ack) if permit else v1.ack_to_dict(ack),
                                             status=status.name, modeled_action_us=p.modeled_action_us))
        self.capture_wire()
        self.save()
        return ack

    def next_k(self, ack):
        self.until(lambda: self.job.state in ('ready', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'ready', self.job.last_record)
        self.job.request(k.next_snapshot(ack.permit.proposal, ack))
        self.until(lambda: self.job.state in ('pending', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'pending', self.job.last_record)
        self.capture_wire()
        return self.job.pending

    def cleanup_owned(self):
        self.capture_wire()
        try:
            self.job.shutdown()
            record = self.job.last_record
            self.receipt.update(job_record=record,
                                launcher_returncode=self.process.poll() if self.process else None,
                                private_directory_removed=self.directory is None or not self.directory.exists(),
                                scope_handle_closed=self.scope is None or self.scope.handle is None)
            clean = (self.job._process is None and self.job._scope is None and self.job._directory is None
                     and self.receipt['private_directory_removed'] and self.receipt['scope_handle_closed']
                     and (self.process is None or self.process.poll() is not None)
                     and record is not None and record.get('reaped') and record.get('tree_active_count') == 0
                     and record.get('cleanup_complete'))
            self.receipt['ownership_cleanup_verified'] = bool(clean)
            self.assertTrue(clean, self.receipt)
        except Exception as exc:
            type(self).ownership_unclear = True
            self.ledger['stop_further_starts'] = True
            self.receipt['cleanup_exception'] = repr(exc)
            raise
        finally:
            self.heartbeat.stop()
            self.receipt.update(heartbeat_count=self.beats, heartbeat_max_gap_seconds=self.max_gap,
                                elapsed_seconds=time.monotonic() - self.started)
            first = self.ledger['first_start_utc_epoch']
            self.ledger['campaign_elapsed_seconds'] = time.time() - first if first else 0
            self.save()
            self.job.deleteLater()
            self.heartbeat.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_certainty_p01_k_guess_safe_colors_terminal(self):
        engine = MinesweeperEngine(5, 1, 2)
        engine.reset_with_mines(5, 1, 2, {(1, 0), (4, 0)})
        state = k.KSnapshot(uuid4().hex, 1, 0, 5, 1, 2, ((-2,) * 5,), (0, 0), 0)
        self.launch(state)
        initial = self.job.pending
        self.assertEqual(initial.safe_cells, ())
        self.assertTrue(all(o.kind is None for o in present_k_proposal(initial).overlays.values()))
        guess = self.next_k(self.actual_step(engine, self.validate()))
        self.assertEqual(guess.continuation, 'EXACT_GUESS')
        self.assertEqual(guess.safe_cells, ())
        self.assertEqual(guess.preinput_m, ((1, 0),))
        self.assertEqual(present_k_proposal(guess).overlays[(1, 0)].kind, OverlayKind.MINE)
        self.assertIn('지뢰 확률 33.3%', present_k_proposal(guess).status_text)
        self.job.validate_pending(guess.snapshot, uuid4().hex)
        self.job.invalidate_admission()
        self.until(lambda: self.job.state in ('pending', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'pending')
        self.assertIs(self.job.pending, guess)
        certain = self.next_k(self.actual_step(engine, self.validate()))
        self.assertEqual(certain.continuation, 'LOCAL_SAFE')
        self.assertEqual(certain.safe_cells, ((3, 0),))
        colors = present_k_proposal(certain).overlays
        self.assertEqual(colors[(3, 0)].kind, OverlayKind.SAFE)
        self.assertEqual(colors[(1, 0)].kind, OverlayKind.MINE)
        self.assertNotIn((4, 0), colors)
        ack = self.actual_step(engine, self.validate())
        self.assertEqual(ack.status, 'WON')
        self.assertIsNone(ack.observation)
        self.until(lambda: self.job.active_run_id is None)
        record = self.job.last_record
        self.assertEqual(record['status'], 'SUCCEEDED')
        self.assertEqual(record['proposal_count'], 3)
        self.assertEqual(record['validation_count'], 4)
        self.assertEqual(record['terminal'], k.to_dict(ack))
        self.assertGreater(self.beats, 0)

    def test_certainty_p02_v1_v5_terminal(self):
        engine = MinesweeperEngine(2, 1, 0)
        state = v1.PublicSnapshot(uuid4().hex, 1, 0, 2, 1, 0, ((-2, -2),), (0, 0))
        self.launch(state)
        ack = self.actual_step(engine)
        self.assertEqual(ack.status, 'WON')
        self.assertIsNone(ack.observation)
        self.until(lambda: self.job.active_run_id is None)
        record = self.job.last_record
        self.assertEqual(record['status'], 'SUCCEEDED')
        self.assertEqual(record['proposal_count'], 1)
        self.assertEqual(record['terminal'], dict(token=ack.token, input_seq=ack.input_seq, status=ack.status))
        self.assertGreater(self.beats, 0)
