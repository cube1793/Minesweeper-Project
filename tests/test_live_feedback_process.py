"""Two opt-in UI-feedback wire cases. Never collected by focused discovery.

The approved increment plan/ledger is mandatory. Test engines alone receive
tiny explicit layouts. Production WindowsWorkerScope and workers are unchanged.
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
from live_analysis import present_k_proposal
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
        handle = api.OpenProcess(0x1000, False, pid)  # Query only, no kill authority.
        if not handle:
            raise C.WinError(C.get_last_error())
        try:
            item = process_identity(handle, pid)
            member = W.BOOL()
            if not api.IsProcessInJob(handle, scope.handle, C.byref(member)) or not member.value:
                raise RuntimeError('Owned PID membership was not confirmed')
            item.update(role='launcher' if pid == launcher_pid else 'owned runtime descendant',
                        membership_verified=True)
            result.append(item)
        finally:
            api.CloseHandle(handle)
    return result


@unittest.skipUnless(os.environ.get('MINESWEEPER_UI_FEEDBACK_PROCESS_PLAN'), 'Requires new UI feedback plan')
class LiveFeedbackProcessTests(unittest.TestCase):
    ownership_unclear = False

    @classmethod
    def setUpClass(cls):
        if os.name != 'nt':
            raise unittest.SkipTest('Windows containment only')
        cls.app = QApplication.instance() or QApplication([])
        cls.plan_path = Path(os.environ['MINESWEEPER_UI_FEEDBACK_PROCESS_PLAN'])
        cls.plan = json.loads(cls.plan_path.read_text('utf-8'))
        cls.ledger_path = Path(os.environ['MINESWEEPER_UI_FEEDBACK_PROCESS_LEDGER'])

    def setUp(self):
        self.assertFalse(type(self).ownership_unclear, 'No further start with unresolved ownership')
        self.case = next(case for case in self.plan['cases'] if case['id'] == self.id())
        self.ledger = json.loads(self.ledger_path.read_text('utf-8'))
        self.assertEqual(self.ledger['identity'], self.plan['identity'])
        self.assertFalse(self.ledger.get('stop_further_starts'))
        self.started = time.monotonic()
        self.receipt = dict(case=self.id(), attempt=1, owner_start_attempts=0, owner_starts=0,
                            fixture_descendant_starts=0, actions=[], wire=[], version=PROTOCOL_VERSION)
        self.ledger['receipts'].append(self.receipt)
        self.job = LivePolicyJob()
        self.root_process = self.scope = self.directory = None
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
        self.last_beat = now
        self.beats += 1

    def until(self, condition):
        while not condition():
            self.assertLess(time.monotonic() - self.started, self.plan['case_cap_seconds'])
            self.assertLess(time.time(), self.ledger['deadline_utc_epoch'])
            QTest.qWait(10)

    def capture_wire(self):
        if self.directory is None or not self.directory.exists():
            return
        # Every captured object is already a strictly decoded public wire value.
        self.receipt['wire'] = [dict(file=p.name, message=json.loads(p.read_text('utf-8')))
                                for p in sorted(self.directory.glob('*.json'))]

    def launch(self, state):
        self.assertEqual(self.receipt['owner_start_attempts'], 0)
        self.assertLess(self.ledger['owner_start_attempts'], self.plan['normal_max_owner_starts'])
        self.assertLess(self.ledger['owner_start_attempts'], self.plan['total_owner_start_limit'])
        if self.ledger['first_start_utc_epoch'] is None:
            self.ledger['first_start_utc_epoch'] = time.time()
            self.ledger['deadline_utc_epoch'] = time.time() + self.plan['campaign_wall_cap_seconds']
        self.assertLess(time.time(), self.ledger['deadline_utc_epoch'])
        self.ledger['owner_start_attempts'] += 1
        self.receipt['owner_start_attempts'] = 1
        self.save()  # Persist budget consumption before invoking production start.
        self.job.start(state)
        self.root_process, self.scope, self.directory = self.job._process, self.job._scope, self.job._directory
        if self.root_process is None:
            self.ledger['stop_further_starts'] = True
            self.receipt['startup_failure'] = 'No process handle returned: creation not inferred from exception'
            self.save()
            self.fail(self.job._failure)
        self.ledger['owner_starts'] += 1
        self.receipt.update(owner_starts=1, launcher=process_identity(int(self.root_process._handle), self.root_process.pid),
                            scope_name=self.scope.name, private_directory=str(self.directory))
        self.save()
        self.until(lambda: self.job.state in ('pending', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'pending', self.job.last_record)
        self.receipt['owned_processes'] = owned_processes(self.scope, self.root_process.pid)
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

    def cleanup_owned(self):
        self.capture_wire()
        try:
            self.job.shutdown()
            record = self.job.last_record
            self.receipt['job_record'] = record
            self.receipt['launcher_returncode'] = self.root_process.poll() if self.root_process else None
            self.receipt['private_directory_removed'] = self.directory is None or not self.directory.exists()
            self.receipt['scope_handle_closed'] = self.scope is None or self.scope.handle is None
            clean = (self.job._process is None and self.job._scope is None and self.job._directory is None
                     and self.receipt['private_directory_removed'] and self.receipt['scope_handle_closed']
                     and (self.root_process is None or self.root_process.poll() is not None)
                     and (record is None or (record.get('reaped') and record.get('tree_active_count') == 0
                                             and record.get('cleanup_complete'))))
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
            self.ledger['campaign_elapsed_seconds'] = (time.time() - self.ledger['first_start_utc_epoch']
                                                        if self.ledger['first_start_utc_epoch'] else 0)
            self.save()
            self.job.deleteLater()
            self.heartbeat.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def actual_step(self, engine, permit=None):
        p = self.job.pending
        self.assertLess(len(self.receipt['actions']), self.case['input_cap'])
        self.job.mark_applying(p.token, permit.nonce) if permit else self.job.mark_applying(p.token)
        engine.step(p.x, p.y, p.move.action)
        status = engine.status  # Status first: terminal observation is never read.
        observation = engine.get_observation() if status == GameStatus.PLAYING else None
        self.job.acknowledge(status.name, observation)
        ack = self.job._sent_ack
        self.receipt['actions'].append(dict(proposal=k.to_dict(p) if permit else v1.proposal_to_dict(p),
                                             ack=k.to_dict(ack) if permit else v1.ack_to_dict(ack)))
        self.capture_wire()
        self.save()
        return ack

    def test_ui_p01_k_exact_probability_wire_pause_readmit(self):
        engine = MinesweeperEngine(5, 1, 3)
        engine.reset_with_mines(5, 1, 3, {(1, 0), (3, 0), (4, 0)})
        state = k.KSnapshot(uuid4().hex, 1, 0, 5, 1, 3, ((-2,) * 5,), (0, 0), 0)
        self.launch(state)
        ack = self.actual_step(engine, self.validate())
        self.until(lambda: self.job.state in ('ready', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'ready', self.job.last_record)
        self.job.request(k.next_snapshot(ack.permit.proposal, ack))
        self.until(lambda: self.job.state in ('pending', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'pending', self.job.last_record)
        p = self.job.pending
        self.assertEqual((p.x, p.y), (2, 0))
        self.assertEqual((p.probabilities.selected_mine_worlds, p.probabilities.total_worlds), (2, 3))
        self.assertEqual(p.preinput_m, ((1, 0),))
        self.assertIn('지뢰 확률 66.7%', present_k_proposal(p).status_text)
        self.job.validate_pending(p.snapshot, uuid4().hex)
        self.job.invalidate_admission()
        self.until(lambda: self.job.state in ('pending', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'pending', self.job.last_record)
        self.assertIs(self.job.pending, p)
        admitted = self.validate()
        self.assertEqual(admitted.proposal, p)
        ack = self.actual_step(engine, admitted)
        self.assertEqual(ack.status, 'WON')
        self.assertIsNone(ack.observation)
        # Capture FINISHED before poll performs the fixed exit/drain cleanup.
        self.until(lambda: self.job._terminal_reply is not None or self.job.active_run_id is None)
        self.capture_wire()
        self.until(lambda: self.job.active_run_id is None)
        self.assertEqual(self.job.last_record['status'], 'SUCCEEDED')
        self.assertEqual(self.job.last_record['proposal_count'], 2)
        self.assertEqual(self.job.last_record['validation_count'], 3)
        self.assertGreater(self.beats, 0)

    def test_ui_p02_v1_v4_initial_terminal(self):
        engine = MinesweeperEngine(2, 1, 0)
        state = v1.PublicSnapshot(uuid4().hex, 1, 0, 2, 1, 0, ((-2, -2),), (0, 0))
        self.launch(state)
        ack = self.actual_step(engine)
        self.assertEqual(ack.status, 'WON')
        self.assertIsNone(ack.observation)
        self.until(lambda: self.job._terminal_reply is not None or self.job.active_run_id is None)
        self.capture_wire()
        self.until(lambda: self.job.active_run_id is None)
        self.assertEqual(self.job.last_record['status'], 'SUCCEEDED')
        self.assertEqual(self.job.last_record['proposal_count'], 1)
        self.assertGreater(self.beats, 0)
