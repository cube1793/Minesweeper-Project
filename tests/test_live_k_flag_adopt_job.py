"""Parent and worker protocol boundaries without spawning processes."""
from dataclasses import replace
import unittest
from uuid import uuid4

from PyQt5.QtTest import QSignalSpy

import live_k_policy as k
import live_policy_worker as worker
import live_policy_transport as transport
from stage3_physical import load_timing_table
from tests.test_live_k_flag_adopt import flag_start
from tests.test_live_k_policy import initial
from tests.test_live_policy_job import LivePolicyJobTests


class KFlagJobTests(unittest.TestCase):
    setUpClass = classmethod(LivePolicyJobTests.setUpClass.__func__)
    setUp = LivePolicyJobTests.setUp
    launch = LivePolicyJobTests.launch
    publish = LivePolicyJobTests.publish

    def boot(self):
        self.start = flag_start()
        self.launch(self.start)
        self.owner = k.KOwner(self.start, load_timing_table())
        self.publish('BOOTSTRAPPED', k.to_dict(self.owner.expected.bootstrap))
        self.job.poll()
        return self.owner.expected

    def test_bootstrap_has_no_consumed_token_and_next_is_explicit(self):
        signals = QSignalSpy(self.job.bootstrapped)
        state = self.boot()
        self.assertEqual(self.job.state, 'ready')
        self.assertEqual(signals[0][0], (self.start, state))
        self.assertEqual(self.job._applied_count, 0)
        self.assertIsNone(self.job.pending)
        self.assertIsNone(self.job._deadline)
        self.assertEqual(self.job._sequence, 1)
        self.job.request(state)
        self.assertEqual(self.job.state, 'computing')
        msg = transport.read_next(self.job._directory, 'parent', 1, self.start.run_id)
        self.assertEqual((msg['version'], msg['kind']), (10, 'NEXT'))
        self.assertEqual(k.from_dict(msg['payload'], k.KSnapshot), state)

    def test_preparation_validation_ack_counters_and_binding(self):
        state = self.boot()
        self.job.request(state)
        p = self.owner.propose(state)
        self.publish('PROPOSAL', k.to_dict(p))
        self.job.poll()
        nonce = uuid4().hex
        self.job.validate_pending(state, nonce)
        permit = self.owner.validate(self.job._sent_validation)
        self.publish('ADMITTED', k.to_dict(permit))
        self.job.poll()
        self.job.mark_applying(p.token, nonce)
        with self.assertRaises(ValueError):
            self.job.mark_applying(p.token, nonce)
        self.job.acknowledge('PLAYING', ((1, -3, 1, -2, -3),))
        ack = self.job._sent_ack
        expected = self.owner.acknowledge(ack)
        self.publish('ACKED', k.to_dict(ack))
        self.job.poll()
        self.assertEqual(self.job._expected_snapshot, expected)
        self.assertEqual(self.job._k_preparation_count, 1)
        self.assertEqual(self.job._k_input_count, 0)
        self.assertEqual(self.job._ack_count, 1)
        self.assertEqual(self.job._last_k_ack, ack)

    def test_structurally_valid_changed_summary_rejected_on_next(self):
        state = self.boot()
        b = replace(state.bootstrap, proved_safe=(), unverified=state.bootstrap.removable)
        with self.assertRaises(ValueError):
            self.job.request(replace(state, bootstrap=b))
        self.assertEqual(self.job.state, 'ready')

    def test_wrong_bootstrap_origin_fails_closed_without_next(self):
        self.start = flag_start()
        self.launch(self.start)
        other = flag_start()
        owner = k.KOwner(other, load_timing_table())
        raw = k.to_dict(owner.expected.bootstrap)
        raw['original_observation'][0][0] = 2
        self.publish('BOOTSTRAPPED', raw)
        self.job.poll()
        self.assertEqual(self.job.state, 'cancelling')
        self.assertEqual(self.job._applied_count, 0)
        self.assertIsNotNone(self.job._failure)

    def test_pause_invalidates_nonce_without_discarding_preparation(self):
        state = self.boot()
        self.job.request(state)
        p = self.owner.propose(state)
        self.publish('PROPOSAL', k.to_dict(p))
        self.job.poll()
        self.job.validate_pending(state, uuid4().hex)
        permit = self.owner.validate(self.job._sent_validation)
        self.job.invalidate_admission()
        self.publish('ADMITTED', k.to_dict(permit))
        self.job.poll()
        self.assertEqual(self.job.state, 'pending')
        self.assertEqual(self.job.pending, p)
        with self.assertRaises(ValueError):
            self.job.mark_applying(p.token, permit.nonce)

    def test_parent_and_worker_keep_exact_per_mode_sequence_bounds(self):
        for state, bound in ((flag_start(), 63362), (initial(), 31681)):
            with self.subTest(mode=state.entry_mode):
                self.job._start_snapshot = state
                self.job._sequence = bound
                self.job._check_sequence()
                worker._check_sequence(bound, k.sequence_limit(state))
                self.job._sequence += 1
                with self.assertRaises(ValueError):
                    self.job._check_sequence()
                with self.assertRaises(ValueError):
                    worker._check_sequence(bound + 1, k.sequence_limit(state))
        self.job._start_snapshot = None
        self.job._sequence = 1921
        self.job._check_sequence()
        worker._check_sequence(1921, transport.MAX_V1_SEQUENCE)
        self.job._sequence = 1922
        with self.assertRaises(ValueError):
            self.job._check_sequence()
        with self.assertRaises(ValueError):
            worker._check_sequence(1922, transport.MAX_V1_SEQUENCE)

