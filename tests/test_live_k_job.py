"""K-specific fake-process lifecycle and in-process worker protocol checks."""
from dataclasses import replace
import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QSignalSpy

import live_k_policy as k
import live_policy_job as jobs
import live_policy_worker as worker
from live_policy_transport import message, read_next, write_once
from stage3_physical import load_timing_table
from tests.test_live_k_policy import initial, ONE_SETUP


class LiveKJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.now = 0.0
        self.job = jobs.LivePolicyJob(clock=lambda: self.now)
        self.addCleanup(self.job.shutdown)
        self.admitted = QSignalSpy(self.job.admitted)
        self.finished = QSignalSpy(self.job.finished)
        self.process = Mock()
        self.process.poll.return_value = None
        self.process.wait.return_value = 0
        with patch.object(jobs.subprocess, 'Popen', return_value=self.process), \
                patch.object(jobs, 'create_scope', return_value=None):
            self.job.start(initial())
        self.job.timer.stop()
        self.owner = k.KOwner(initial(), load_timing_table())

    def publish(self, kind, payload):
        write_once(self.job._directory, 'worker', self.job._sequence,
                   message(self.job.active_run_id, self.job._sequence, kind, payload))
        self.job.poll()

    def pending(self):
        p = self.owner.propose(initial())
        self.publish('PROPOSAL', k.to_dict(p))
        return p

    def validate(self, p):
        nonce = uuid4().hex
        self.job.validate_pending(p.snapshot, nonce)
        request = read_next(self.job._directory, 'parent', self.job._sequence, self.job.active_run_id)
        self.assertEqual(request['kind'], 'VALIDATE')
        return self.owner.validate(k.from_dict(request['payload'], k.KValidation))

    def test_worker_roundtrip_required_and_token_single_use_then_explicit_next(self):
        p = self.pending()
        with self.assertRaises(ValueError):
            self.job.mark_applying(p.token)
        a = self.validate(p)
        self.publish('ADMITTED', k.to_dict(a))
        self.assertEqual(self.job.state, 'admitted')
        with self.assertRaises(ValueError):
            self.job.mark_applying(p.token, 'd' * 32)
        self.job.mark_applying(p.token, a.nonce)
        with self.assertRaises(ValueError):
            self.job.mark_applying(p.token, a.nonce)
        self.job.acknowledge('PLAYING', ONE_SETUP)
        ack = self.job._sent_ack
        following = self.owner.acknowledge(ack)
        self.publish('ACKED', k.to_dict(ack))
        self.assertEqual(self.job.state, 'ready')
        self.assertIsNone(self.job.pending)
        self.assertEqual(self.job._proposal_count, 1)
        self.job.request(following)
        self.assertEqual(self.job.state, 'computing')

    def test_pause_during_validation_drains_late_admission_keeps_original_pending(self):
        p = self.pending()
        a = self.validate(p)
        deadline = self.job._deadline
        self.job.invalidate_admission()
        self.assertEqual(self.job._deadline, deadline)
        self.publish('ADMITTED', k.to_dict(a))
        self.assertEqual(self.job.state, 'pending')
        self.assertEqual(self.job.pending, p)
        self.assertIsNone(self.job._deadline)
        with self.assertRaises(ValueError):
            self.job.mark_applying(p.token, a.nonce)
        b = self.validate(p)
        self.assertNotEqual(a.nonce, b.nonce)
        self.publish('ADMITTED', k.to_dict(b))
        self.job.mark_applying(p.token, b.nonce)
        self.assertEqual(self.job._applied_count, 1)

    def test_validation_response_five_seconds_pause_does_not_extend_cap(self):
        p = self.pending()
        self.validate(p)
        self.job.invalidate_admission()
        self.now = 5.0
        self.job.poll()
        self.assertEqual(self.job._intent, 'TIMEOUT')
        self.assertEqual(self.job._intent_reason, 'validating')
        self.assertEqual(self.job._applied_count, 0)

    def test_computing_thirty_seconds_and_idle_excluded(self):
        self.assertEqual(self.job._deadline, 30.0)
        self.job.invalidate_admission()
        self.assertEqual(self.job._deadline, 30.0)
        p = self.pending()
        self.now = 10000
        self.job.poll()
        self.assertEqual(self.job.state, 'pending')
        self.assertEqual(self.job.pending, p)

    def test_acquired_m_pending_idle_keeps_session_and_revalidates_without_analysis(self):
        p = self.pending()
        a = self.validate(p)
        self.publish('ADMITTED', k.to_dict(a))
        self.job.mark_applying(p.token, a.nonce)
        self.job.acknowledge('PLAYING', ONE_SETUP)
        ack = self.job._sent_ack
        following = self.owner.acknowledge(ack)
        self.publish('ACKED', k.to_dict(ack))
        self.job.request(following)
        p = self.owner.propose(following)
        self.publish('PROPOSAL', k.to_dict(p))
        graph = self.owner.selection
        self.assertEqual(p.preinput_m, ((1, 0),))
        self.now = 100000
        self.job.invalidate_admission()
        self.job.poll()
        a = self.validate(p)
        self.publish('ADMITTED', k.to_dict(a))
        self.assertIs(self.owner.selection, graph)
        self.assertEqual(self.owner.session.M, frozenset({(1, 0)}))

    def test_tampered_admission_fails_without_consumption(self):
        p = self.pending()
        a = self.validate(p)
        self.publish('ADMITTED', k.to_dict(replace(a, nonce='b' * 32)))
        self.assertEqual(self.job.state, 'cancelling')
        self.assertTrue(self.job._failure.startswith('REPLY_TRANSPORT:'))
        self.assertEqual(self.job._applied_count, 0)

    def test_terminal_success_only_after_reap_cleanup_with_exact_ack(self):
        p = self.pending()
        a = self.validate(p)
        self.publish('ADMITTED', k.to_dict(a))
        self.job.mark_applying(p.token, a.nonce)
        self.job.acknowledge('WON')
        ack = self.job._sent_ack
        self.owner.acknowledge(ack)
        self.publish('FINISHED', k.to_dict(ack))
        self.assertFalse(self.finished)
        self.assertEqual(self.job._finish_exit_deadline, 5.0)
        self.process.poll.return_value = 0
        directory = self.job._directory
        self.job.poll()
        self.assertEqual(self.job.last_record['status'], 'SUCCEEDED')
        self.assertTrue(self.job.last_record['cleanup_complete'])
        self.assertFalse(directory.exists())
        self.assertEqual(self.job.last_record['policy_id'], 'K_P0')
        self.assertEqual(self.job.last_record['validation_count'], 1)

    def test_cleanup_failure_retains_ownership_and_blocks_any_new_owner(self):
        self.pending()
        self.job.cancel('manual')
        self.process.poll.return_value = 0
        with patch.object(jobs.shutil, 'rmtree', side_effect=OSError('cleanup fixture')):
            self.job.poll()
        self.assertEqual(self.job.state, 'blocked')
        self.assertFalse(self.job.last_record['cleanup_complete'])
        with self.assertRaises(RuntimeError), patch.object(jobs.subprocess, 'Popen') as launch:
            self.job.start(initial())
        launch.assert_not_called()

    def test_cancel_before_admission_blocks_late_reply(self):
        p = self.pending()
        a = self.validate(p)
        self.job.cancel('manual/close')
        write_once(self.job._directory, 'worker', self.job._sequence,
                   message(initial().run_id, self.job._sequence, 'ADMITTED', k.to_dict(a)))
        self.job.poll()
        self.assertFalse(self.admitted)
        self.assertEqual(self.job._applied_count, 0)


class LiveKWorkerProtocolTests(unittest.TestCase):
    def test_start_validate_terminal_ack_and_no_terminal_analysis(self):
        outputs = []
        def read(_directory, _direction, seq, run):
            if seq == 0:
                return message(run, seq, 'START', k.to_dict(initial()))
            if seq == 1:
                p = k.from_dict(outputs[-1]['payload'], k.KProposal)
                return message(run, seq, 'VALIDATE', k.to_dict(k.KValidation(p.snapshot, p.token, 'b' * 32, 0)))
            a = k.from_dict(outputs[-1]['payload'], k.KPermit)
            return message(run, seq, 'ACK', k.to_dict(k.make_ack(a, 'LOST')))
        with patch.object(worker, 'read_next', side_effect=read), \
                patch.object(worker, 'write_once', side_effect=lambda d, c, s, m: outputs.append(m)), \
                patch('experiments.program_k_capability.KLocalSession.analyze_decision', side_effect=AssertionError('initial/terminal')):
            self.assertEqual(worker.serve('unused', initial().run_id), 0)
        self.assertEqual([m['kind'] for m in outputs], ['PROPOSAL', 'ADMITTED', 'FINISHED'])
        self.assertIsNone(outputs[-1]['payload']['observation'])

    def test_ack_without_validate_is_error_and_never_success(self):
        outputs = []
        def read(d, c, seq, run):
            if seq == 0:
                return message(run, seq, 'START', k.to_dict(initial()))
            p = k.from_dict(outputs[0]['payload'], k.KProposal)
            return message(run, seq, 'ACK', k.to_dict(k.make_ack(k.KPermit(p, 'c' * 32), 'WON')))
        with patch.object(worker, 'read_next', side_effect=read), \
                patch.object(worker, 'write_once', side_effect=lambda d, c, s, m: outputs.append(m)):
            self.assertEqual(worker.serve('unused', initial().run_id), 1)
        self.assertEqual([m['kind'] for m in outputs], ['PROPOSAL', 'ERROR'])
