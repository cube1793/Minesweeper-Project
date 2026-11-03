"""Seven opt-in NEW K Windows scenarios, never the historical F02 suite.

The external NEW_K_PROCESS_TEST_PLAN.json must be fixed before invocation.
No discovery: this class is run only by the named unit evidence launcher.
"""
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()
from PyQt5.QtCore import QTimer
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import live_k_policy as k
import live_policy_job as jobs
from core_engine import GameStatus, MinesweeperEngine
from tests.test_live_k_policy import initial


@unittest.skipUnless(os.environ.get('MINESWEEPER_NEW_K_PROCESS_PLAN'), 'Requires explicit new K plan')
class LiveKProcessTests(unittest.TestCase):
    receipts = []
    starts = 0
    ownership_unclear = False

    @classmethod
    def setUpClass(cls):
        if os.name != 'nt':
            raise unittest.SkipTest('Windows containment evidence only')
        cls.app = QApplication.instance() or QApplication([])
        cls.plan_path = Path(os.environ['MINESWEEPER_NEW_K_PROCESS_PLAN'])
        cls.plan = json.loads(cls.plan_path.read_text(encoding='utf-8'))
        cls.receipt_path = Path(os.environ['MINESWEEPER_NEW_K_PROCESS_RECEIPTS'])
        cls.pass_started = time.monotonic()

    def setUp(self):
        self.assertFalse(self.ownership_unclear, 'Ownership unresolved: no more child starts')
        self.assertIn(self._testMethodName, self.plan['cases'])
        self.started = time.monotonic()
        self.beats = 0
        self.max_gap = 0
        self.last_beat = self.started
        self.heartbeat = QTimer()
        self.heartbeat.setInterval(10)
        self.heartbeat.timeout.connect(self.beat)
        self.heartbeat.start()
        self.job = jobs.LivePolicyJob()
        self.root_process = self.scope = self.directory = None
        self.receipt = {'scenario': self._testMethodName, 'attempt': 1, 'owner_start_attempts': 0,
                        'owner_starts': 0, 'fixture_descendant_starts': 0, 'actions': []}
        self.receipts.append(self.receipt)
        self.addCleanup(self.cleanup_owned)
        self.save()

    def beat(self):
        now = time.monotonic()
        self.max_gap = max(self.max_gap, now - self.last_beat)
        self.last_beat = now
        self.beats += 1

    def save(self):
        self.receipt_path.write_text(json.dumps(self.receipts, indent=2), encoding='utf-8')

    def until(self, condition):
        while not condition():
            self.assertLess(time.monotonic() - self.started, self.plan['case_cap_seconds'])
            self.assertLess(time.monotonic() - self.pass_started, self.plan['pass_cap_seconds'])
            QTest.qWait(10)

    def capture_fixture(self):
        if self.directory is not None:
            for name in ('k-fixture.json', 'k-descendant.json'):
                path = self.directory / name
                if path.exists():
                    data = json.loads(path.read_text(encoding='utf-8'))
                    self.receipt[name] = data
                    if name == 'k-fixture.json':
                        self.receipt['fixture_descendant_starts'] = data['fixture_descendant_starts']

    def cleanup_owned(self):
        self.capture_fixture()
        try:
            self.job.shutdown()
            record = self.job.last_record
            self.receipt['job_record'] = record
            self.receipt['launcher_returncode'] = self.root_process.poll() if self.root_process else None
            self.receipt['private_directory_removed'] = self.directory is None or not self.directory.exists()
            self.receipt['scope_handle_closed'] = self.scope is None or self.scope.handle is None
            clean = (self.job._process is None and self.job._scope is None and self.job._directory is None
                     and self.receipt['private_directory_removed'] and self.receipt['scope_handle_closed'])
            self.receipt['ownership_cleanup_verified'] = clean
            type(self).ownership_unclear = not clean
            self.assertTrue(clean)
        except Exception as exc:
            type(self).ownership_unclear = True
            self.receipt['cleanup_exception'] = repr(exc)
            raise
        finally:
            self.heartbeat.stop()
            self.receipt.update(heartbeat_count=self.beats, heartbeat_max_gap_seconds=self.max_gap,
                                elapsed_seconds=time.monotonic() - self.started)
            self.save()
            self.job.deleteLater()
            self.app.processEvents()

    def launch(self, state, mode=None):
        self.assertLess(self.starts, self.plan['max_owner_starts'])
        self.assertEqual(self.receipt['owner_start_attempts'], 0)
        self.receipt['owner_start_attempts'] = 1
        self.save()
        if mode:
            fixture = Path(__file__).parent / 'fixtures/live_k_worker.py'
            command = lambda directory, run, scope: [sys.executable, '-B', str(fixture), str(directory), run, scope, mode]
            with patch.object(jobs, 'build_worker_command', side_effect=command):
                self.job.start(state)
        else:
            self.job.start(state)
        self.root_process, self.scope, self.directory = self.job._process, self.job._scope, self.job._directory
        if self.root_process is not None:
            type(self).starts += 1
            self.receipt.update(owner_starts=1, launcher_pid=self.root_process.pid,
                                scope_name=self.scope.name, active_tree_at_launch=self.scope.active_count,
                                private_directory=str(self.directory))
        self.save()
        self.until(lambda: self.job.state in ('pending', 'idle', 'blocked'))
        self.capture_fixture()
        self.assertEqual(self.job.state, 'pending', self.job.last_record)
        self.assertGreater(self.beats, 0)

    def validate(self):
        p = self.job.pending
        self.job.validate_pending(p.snapshot, uuid4().hex)
        self.until(lambda: self.job.state in ('admitted', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'admitted', self.job.last_record)
        return self.job._permit

    def actual_step(self, engine):
        a = self.validate()
        p = a.proposal
        self.job.mark_applying(p.token, a.nonce)
        engine.step(p.x, p.y, p.move.action)
        status = engine.status
        after = engine.get_observation() if status == GameStatus.PLAYING else None
        self.job.acknowledge(status.name, after)
        ack = self.job._sent_ack
        self.receipt['actions'].append({'proposal': k.to_dict(p), 'ack': k.to_dict(ack)})
        self.save()
        return ack

    def test_k01_native_small_engine_flag_fresh_chord_terminal(self):
        engine = MinesweeperEngine(5, 4, 2)
        engine.reset_with_mines(5, 4, 2, {(1, 2), (3, 2)})
        self.launch(initial(5, 4, 2))
        for _ in range(20):
            ack = self.actual_step(engine)
            if ack.status != 'PLAYING':
                break
            self.until(lambda: self.job.state in ('ready', 'idle', 'blocked'))
            self.assertEqual(self.job.state, 'ready', self.job.last_record)
            self.job.request(k.next_snapshot(ack.permit.proposal, ack))
            self.until(lambda: self.job.state in ('pending', 'idle', 'blocked'))
            self.assertEqual(self.job.state, 'pending', self.job.last_record)
        self.until(lambda: self.job.active_run_id is None)
        self.assertEqual(self.job.last_record['status'], 'SUCCEEDED')
        actions = [a['proposal']['action'] for a in self.receipt['actions']]
        self.assertIn('FLAG', actions)
        self.assertIn('CHORD', actions)
        self.assertLessEqual(len(actions), 20)

    def test_k02_native_initial_terminal_no_next(self):
        engine = MinesweeperEngine(2, 1, 0)
        self.launch(initial(2, 1, 0))
        ack = self.actual_step(engine)
        self.assertEqual(ack.status, 'WON')
        self.assertIsNone(ack.observation)
        self.until(lambda: self.job.active_run_id is None)
        self.assertEqual(self.job.last_record['status'], 'SUCCEEDED')
        self.assertEqual(self.job.last_record['proposal_count'], 1)

    def test_k03_real_pending_pause_validation_revoke_resume_cancel(self):
        self.launch(initial())
        p = self.job.pending
        self.job.validate_pending(p.snapshot, uuid4().hex)
        self.job.invalidate_admission()
        self.until(lambda: self.job.state in ('pending', 'idle', 'blocked'))
        self.assertEqual(self.job.state, 'pending')
        self.assertEqual(self.job.pending, p)
        a = self.validate()
        self.assertEqual(a.proposal, p)
        self.assertEqual(self.job._proposal_count, 1)
        self.assertEqual(self.job._applied_count, 0)
        self.job.cancel('K pause/resume fixture complete')
        self.until(lambda: self.job.active_run_id is None)
        self.assertEqual(self.job.last_record['status'], 'CANCELLED')

    def test_k04_validation_timeout_heartbeat_cleanup(self):
        self.launch(initial(), 'slow_validation')
        self.job.validate_pending(self.job.pending.snapshot, uuid4().hex)
        beats = self.beats
        self.until(lambda: self.job.active_run_id is None)
        self.assertEqual(self.job.last_record['status'], 'TIMEOUT')
        self.assertEqual(self.job.last_record['intent_reason'], 'validating')
        self.assertGreater(self.beats - beats, 10)

    def test_k05_close_owned_descendant_cleanup(self):
        self.launch(initial(), 'tree_close')
        self.until(lambda: (self.directory / 'k-descendant.json').exists())
        self.capture_fixture()
        self.assertTrue(self.receipt['k-descendant.json']['membership_verified'])
        self.receipt['active_tree_before_close'] = self.scope.active_count
        self.job.shutdown()
        self.assertEqual(self.job.last_record['status'], 'CLOSED')
        self.assertTrue(self.job.last_record['cleanup_complete'])

    def test_k06_tampered_permit_zero_inputs_cleanup(self):
        self.launch(initial(), 'tampered_permit')
        self.job.validate_pending(self.job.pending.snapshot, uuid4().hex)
        self.until(lambda: self.job.active_run_id is None)
        self.assertEqual(self.job.last_record['status'], 'FAILED')
        self.assertTrue(self.job.last_record['error'].startswith('REPLY_TRANSPORT:'))
        self.assertEqual(self.job.last_record['consumed_token_count'], 0)

    def test_k07_finished_exit_cap_keeps_actual_terminal_input(self):
        engine = MinesweeperEngine(2, 1, 0)
        self.launch(initial(2, 1, 0), 'delayed_exit')
        ack = self.actual_step(engine)
        self.until(lambda: self.job.active_run_id is None)
        self.assertEqual(ack.status, 'WON')
        self.assertEqual(len(self.receipt['actions']), 1)
        self.assertEqual(self.job.last_record['status'], 'FAILED')
        self.assertTrue(self.job.last_record['error'].startswith('FINISH_EXIT_TIMEOUT:'))
