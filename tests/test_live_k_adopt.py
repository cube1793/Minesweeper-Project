"""FLAG-free K entry contracts, real native graphs, and fake-process boundaries."""
from copy import deepcopy
from dataclasses import replace
import json
import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()
from PyQt5.QtWidgets import QApplication

import live_k_policy as k
import live_policy_job as jobs
import live_policy_worker as worker
from live_policy_transport import MAX_MESSAGE_BYTES, MAX_SEQUENCE, MAX_V1_SEQUENCE, message, write_once
from experiments.program_k_capability import KLocalSession
from experiments.program_k_policy import KPolicyIntegrityError
from stage3_physical import action_cost, load_timing_table
from tests.test_live_k_policy import initial, ONE_SETUP, permit


def adopted(observation=ONE_SETUP, mines=1, revision=503, cursor=(3, 1)):
    return k.KSnapshot(uuid4().hex, 7, 0, len(observation[0]), len(observation), mines,
                       observation, cursor, revision, entry_mode=k.ADOPT_CURRENT,
                       start_input_revision=revision, definition=k.ADOPT_DEFINITION, game_id="f" * 32)


class KAdoptContractTests(unittest.TestCase):
    def test_first_adopt_runs_native_once_and_keeps_original_graph_and_cursor_leg(self):
        state = adopted()
        original = KLocalSession.analyze_decision
        with patch.object(KLocalSession, 'analyze_decision', autospec=True, side_effect=original) as analyze:
            owner = k.KOwner(state, load_timing_table())
            owner._select = Mock(wraps=owner._select)
            self.assertEqual(owner.session.M, frozenset())
            p = owner.propose(state)
            graph = owner.selection
            for _ in range(3):
                permit(owner, p)
            analyze.assert_called_once()
            owner._select.assert_called_once()
            self.assertEqual(owner._select.call_args.kwargs, {})
            self.assertIs(owner.selection, graph)
            self.assertIs(graph.evidence, owner.decision)
            self.assertEqual(p.snapshot.input_seq, 0)
            self.assertFalse(p.initial)
            self.assertEqual((p.action, p.x, p.y), ('OPEN', 3, 0))
            self.assertEqual((p.snapshot.base_m_revision, p.pending_m_revision), (0, 1))
            self.assertEqual(p.preinput_m, ((1, 0),))
            self.assertEqual(p.modeled_action_us, action_cost(owner.table, (3, 1), (3, 0)))

    def test_canonical_initial_still_has_no_native_analysis_and_distinct_definition(self):
        with patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('native call')):
            state = initial()
            owner = k.KOwner(state, load_timing_table())
            p = owner.propose(state)
            permit(owner, p)
        self.assertTrue(p.initial)
        self.assertEqual((p.x, p.y, p.pending_m_revision), (0, 0, 0))
        self.assertEqual(state.definition, k.DEFINITION)
        self.assertNotEqual(state.definition, adopted().definition)

    def test_all_hidden_adopt_is_exact_guess_and_never_initial_open(self):
        state = adopted(((-2,) * 5,), 2, 2, (4, 0))
        owner = k.KOwner(state, load_timing_table())
        p = owner.propose(state)
        self.assertTrue(p.is_guess)
        self.assertFalse(p.initial)
        self.assertEqual(p.continuation, 'EXACT_GUESS')
        self.assertEqual(p.pending_m_revision, 1)
        self.assertEqual(p.safe_cells, ())
        self.assertIsNotNone(p.probabilities)
        permit(owner, p)

    def test_adopt_ack_advances_global_local_and_m_separately(self):
        state = adopted(cursor=(0, 0))
        owner = k.KOwner(state, load_timing_table())
        first = owner.propose(state)
        ack = k.make_ack(permit(owner, first), 'PLAYING', ((1, -3, 1, -2), (1, 1, 1, -2)))
        nxt = owner.acknowledge(ack)
        self.assertEqual((nxt.input_seq, nxt.start_input_revision, nxt.input_revision, nxt.base_m_revision),
                         (1, 503, 504, 1))
        second = owner.propose(nxt)
        self.assertEqual(second.action, 'CHORD')
        self.assertEqual(second.pending_m_revision, 2)
        self.assertEqual(second.snapshot.definition, k.ADOPT_DEFINITION)
        permit(owner, second)

    def test_start_rejects_flags_nonempty_m_and_terminal_before_session_creation(self):
        raw = k.to_dict(adopted())
        for change in ({'base_m': [[1, 0]]}, {'observation': [[1, -3, 1, -2], [1, 1, 1, -2]]},
                       {'status': 'WON'}, {'status': 'LOST'}, {'input_seq': 1, 'input_revision': 504,
                                                               'base_m_revision': 1}):
            with self.subTest(change=change), patch('experiments.program_k_capability.KLocalSession') as session:
                with self.assertRaises(ValueError):
                    k.KOwner(k.from_dict({**raw, **change}, k.KSnapshot), load_timing_table())
                session.assert_not_called()

    def test_entry_revision_definition_strict_types_fields_and_relations(self):
        raw = k.to_dict(adopted())
        mutations = [('entry_mode', v) for v in (True, 0, 1.0, None, 'ADOPT', k.CANONICAL_NEW)]
        mutations += [('definition', v) for v in (True, 0, None, k.DEFINITION)]
        mutations += [(field, value) for field in ('input_seq', 'input_revision', 'start_input_revision',
                                                   'base_m_revision') for value in (True, 0.0, -1, None)]
        mutations += [('start_input_revision', 0), ('start_input_revision', 504), ('input_revision', 502),
                      ('base_m_revision', 1), ('input_seq', 481)]
        for field, value in mutations:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                k.from_dict({**raw, field: value}, k.KSnapshot)
        for field in raw:
            bad = dict(raw)
            del bad[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                k.from_dict(bad, k.KSnapshot)
        with self.assertRaises(ValueError):
            k.from_dict({**raw, 'unexpected': 1}, k.KSnapshot)

    def test_nested_snapshot_binding_is_required_in_every_wire_dto(self):
        state = adopted()
        owner = k.KOwner(state, load_timing_table())
        p = owner.propose(state)
        request = k.KValidation(state, p.token, uuid4().hex, p.pending_m_revision)
        admission = owner.validate(request)
        ack = k.make_ack(admission, 'LOST')
        cases = [(state, ()), (p, ('snapshot',)), (request, ('snapshot',)),
                 (admission, ('proposal', 'snapshot')), (ack, ('permit', 'proposal', 'snapshot'))]
        for value, path in cases:
            raw = k.to_dict(value)
            self.assertEqual(k.from_dict(json.loads(json.dumps(raw)), type(value)), value)
            for field in ('entry_mode', 'definition', 'start_input_revision'):
                bad = deepcopy(raw)
                nested = bad
                for key in path:
                    nested = nested[key]
                del nested[field]
                with self.subTest(dto=type(value).__name__, field=field), self.assertRaises(ValueError):
                    k.from_dict(bad, type(value))

    def test_structurally_valid_different_start_binding_rejected_at_admit_validate_ack(self):
        state = adopted()
        owner = k.KOwner(state, load_timing_table())
        p = owner.propose(state)
        changed = replace(state, start_input_revision=504, input_revision=504)
        with self.assertRaises(ValueError):
            k.admit_proposal(p, changed)
        with self.assertRaises(ValueError):
            owner.validate(k.KValidation(changed, p.token, uuid4().hex, p.pending_m_revision))
        a = permit(owner, p)
        wrong = replace(a, proposal=replace(p, snapshot=changed))
        with self.assertRaises(ValueError):
            owner.acknowledge(k.make_ack(wrong, 'LOST'))
        self.assertIs(owner.pending, p)

    def test_adopt_cannot_claim_initial_or_canonical_m_schedule(self):
        state = adopted(((-2,) * 5,), 2, 10, (0, 0))
        p = k.KOwner(state, load_timing_table()).propose(state)
        with self.assertRaises(ValueError):
            replace(p, kind='initial', action='OPEN', x=0, y=0, category='POLICY_INITIAL_OPEN',
                    continuation='INITIAL', pending_m_revision=0, compute_ns=0, probabilities=None)
        with self.assertRaises(ValueError):
            replace(p, pending_m_revision=0)
        with self.assertRaises(ValueError):
            k.KValidation(state, p.token, uuid4().hex, 0)

    def test_zero_analysis_revision_cannot_carry_an_injected_m(self):
        with self.assertRaisesRegex(ValueError, 'revision zero'):
            replace(initial(), input_seq=1, input_revision=1,
                    observation=ONE_SETUP, base_m=((1, 0),))

    def test_high_global_revision_does_not_expand_local_or_wire_bounds(self):
        state = adopted(revision=1000000)
        owner = k.KOwner(state, load_timing_table())
        p = owner.propose(state)
        self.assertEqual(owner.input_limit, 3)
        self.assertEqual(p.snapshot.input_seq, 0)
        self.assertEqual(k.sequence_limit(state), 31681)
        self.assertEqual(MAX_SEQUENCE, 63362)
        self.assertEqual(MAX_V1_SEQUENCE, 1921)
        self.assertEqual(MAX_MESSAGE_BYTES, 2 * 1024 * 1024)
        for seq in (9, 481):
            with self.subTest(seq=seq), self.assertRaises(ValueError):
                replace(state, input_seq=seq, input_revision=1000000 + seq, base_m_revision=seq)

    def test_new_owner_empty_m_does_not_restore_previous_owner_or_selection(self):
        state = adopted()
        old = k.KOwner(state, load_timing_table())
        old.propose(state)
        self.assertTrue(old.session.M)
        new_state = replace(state, run_id=uuid4().hex)
        new = k.KOwner(new_state, load_timing_table())
        self.assertEqual(new.session.M, frozenset())
        self.assertIsNone(new.decision)
        self.assertIsNone(new.selection)
        new.propose(new_state)
        self.assertIsNot(new.session, old.session)
        self.assertIsNot(new.decision, old.decision)

    def test_native_failure_blocks_reanalysis_without_fallback(self):
        for code in ('SETUP_OPEN_SURVIVED', 'NO_REVEAL_CANDIDATE'):
            with self.subTest(code=code):
                state = adopted()
                owner = k.KOwner(state, load_timing_table())
                owner._select = Mock(side_effect=KPolicyIntegrityError(code, 'adopt fixture'))
                with self.assertRaisesRegex(ValueError, code):
                    owner.propose(state)
                with self.assertRaises(ValueError):
                    owner.propose(state)
                owner._select.assert_called_once()

    def test_worker_adopt_start_validate_terminal_protocol_has_one_native_analysis(self):
        state, outputs = adopted(), []
        def read(directory, channel, seq, run):
            if seq == 0:
                return message(run, seq, 'START', k.to_dict(state))
            if seq == 1:
                p = k.from_dict(outputs[-1]['payload'], k.KProposal)
                return message(run, seq, 'VALIDATE', k.to_dict(k.KValidation(state, p.token, 'd' * 32, 1)))
            a = k.from_dict(outputs[-1]['payload'], k.KPermit)
            return message(run, seq, 'ACK', k.to_dict(k.make_ack(a, 'LOST')))
        original = KLocalSession.analyze_decision
        with patch.object(worker, 'read_next', side_effect=read), \
                patch.object(worker, 'write_once', side_effect=lambda d, c, s, m: outputs.append(m)), \
                patch.object(KLocalSession, 'analyze_decision', autospec=True, side_effect=original) as analyze:
            self.assertEqual(worker.serve('unused', state.run_id), 0)
            analyze.assert_called_once()
        self.assertEqual([m['kind'] for m in outputs], ['PROPOSAL', 'ADMITTED', 'FINISHED'])
        self.assertIsNone(outputs[-1]['payload']['observation'])
        self.assertEqual(outputs[-1]['payload']['input_revision'], 504)


class KAdoptJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.state = adopted(cursor=(0, 0))
        self.owner = k.KOwner(self.state, load_timing_table())
        self.process = Mock()
        self.process.poll.return_value = None
        self.process.wait.return_value = 0
        self.job = jobs.LivePolicyJob()
        self.addCleanup(self.job.shutdown)
        with patch.object(jobs.subprocess, 'Popen', return_value=self.process), \
                patch.object(jobs, 'create_scope', return_value=None):
            self.job.start(self.state)
        self.job.timer.stop()
        self.p = self.owner.propose(self.state)
        self.publish('PROPOSAL', k.to_dict(self.p))

    def publish(self, kind, value):
        write_once(self.job._directory, 'worker', self.job._sequence,
                   message(self.state.run_id, self.job._sequence, kind, value))
        self.job.poll()

    def admission(self):
        nonce = uuid4().hex
        self.job.validate_pending(self.state, nonce)
        a = self.owner.validate(k.KValidation(self.state, self.p.token, nonce, 1))
        self.publish('ADMITTED', k.to_dict(a))
        return a

    def test_start_binding_and_actual_ack_are_in_job_record(self):
        a = self.admission()
        self.job.mark_applying(self.p.token, a.nonce)
        self.job.acknowledge('LOST')
        ack = self.job._sent_ack
        self.owner.acknowledge(ack)
        self.publish('FINISHED', k.to_dict(ack))
        self.process.poll.return_value = 0
        self.job.poll()
        record = self.job.last_record
        self.assertEqual(record['entry_mode'], k.ADOPT_CURRENT)
        self.assertEqual(record['definition'], k.ADOPT_DEFINITION)
        self.assertEqual(record['start_input_revision'], 503)
        self.assertEqual(record['start_cursor'], (0, 0))
        self.assertEqual(record['last_k_ack']['input_revision'], 504)
        self.assertIsNone(record['unconfirmed_k_ack'])
        self.assertTrue(record['cleanup_complete'])

    def test_changed_start_in_permit_is_rejected_before_consumption(self):
        nonce = uuid4().hex
        self.job.validate_pending(self.state, nonce)
        a = self.owner.validate(k.KValidation(self.state, self.p.token, nonce, 1))
        changed = replace(self.state, start_input_revision=504, input_revision=504)
        self.publish('ADMITTED', k.to_dict(replace(a, proposal=replace(self.p, snapshot=changed))))
        self.assertEqual(self.job.state, 'cancelling')
        self.assertEqual(self.job._applied_count, 0)

    def test_exact_ack_then_next_only_and_old_start_never_resumes(self):
        a = self.admission()
        with self.assertRaises(ValueError):
            self.job.request(self.state)
        self.job.mark_applying(self.p.token, a.nonce)
        self.job.acknowledge('PLAYING', ((1, -3, 1, -2), (1, 1, 1, -2)))
        ack = self.job._sent_ack
        nxt = self.owner.acknowledge(ack)
        with self.assertRaises(ValueError):
            self.job.request(nxt)
        self.publish('ACKED', k.to_dict(ack))
        with self.assertRaises(ValueError):
            self.job.request(replace(nxt, start_input_revision=504, input_revision=505))
        self.job.request(nxt)
        self.assertEqual(self.job.state, 'computing')

    def test_cancelled_owner_must_finish_cleanup_before_new_adopt(self):
        self.job.cancel('normal retire')
        with patch.object(jobs.subprocess, 'Popen') as launch:
            with self.assertRaises(RuntimeError):
                self.job.start(adopted())
            launch.assert_not_called()
        self.process.poll.return_value = 0
        self.job.poll()
        self.assertEqual(self.job.state, 'idle')
        self.assertTrue(self.job.last_record['cleanup_complete'])
        new = adopted()
        with patch.object(jobs.subprocess, 'Popen', return_value=self.process), \
                patch.object(jobs, 'create_scope', return_value=None):
            self.job.start(new)
        self.job.timer.stop()
        self.assertEqual(self.job._expected_snapshot, new)
        self.assertIsNone(self.job._last_k_ack)

