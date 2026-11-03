"""K-P0 Live increment: pure public owner/codec, no process or corpus."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import live_k_policy as k
from core_engine import Action, GameStatus, MinesweeperEngine
from experiments.program_k_capability import KLocalSession
from experiments.program_k_policy import KPolicyIntegrityError
from live_policy import LivePolicyError
from live_policy_transport import MAX_SEQUENCE, message, validate_message
from stage3_physical import action_cost, load_timing_table

H, F = -2, -3
ONE_SETUP = ((1, H, 1, H), (1, 1, 1, H))


def initial(width=4, height=2, mines=1):
    return k.KSnapshot('a' * 32, 1, 0, width, height, mines,
                       tuple((H,) * width for _ in range(height)), (0, 0), 0)


def permit(owner, proposal):
    return owner.validate(k.KValidation(proposal.snapshot, proposal.token, uuid4().hex,
                                       proposal.pending_m_revision))


def after_initial(observation=ONE_SETUP, mines=1):
    start = initial(len(observation[0]), len(observation), mines)
    owner = k.KOwner(start, load_timing_table())
    p = owner.propose(start)
    a = k.make_ack(permit(owner, p), 'PLAYING', observation)
    following = owner.acknowledge(a)
    return owner, following


class LiveKPolicyTests(unittest.TestCase):
    def test_initial_has_zero_analysis_selection_and_empty_m(self):
        with patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('analysis')):
            owner = k.KOwner(initial(), load_timing_table())
            owner._select = Mock(side_effect=AssertionError('selection'))
            p = owner.propose(initial())
            admitted = permit(owner, p)
        self.assertTrue(p.initial)
        self.assertFalse(p.is_guess)
        self.assertEqual(p.preinput_m, ())
        self.assertEqual(admitted.proposal, p)
        owner._select.assert_not_called()

    def test_one_analysis_select_original_graph_current_m_and_no_suffix(self):
        owner, state = after_initial()
        original = KLocalSession.analyze_decision
        with patch.object(KLocalSession, 'analyze_decision', autospec=True, side_effect=original) as analysis:
            owner._select = Mock(wraps=owner._select)
            p = owner.propose(state)
            self.assertEqual(p.action, 'FLAG')
            self.assertIs(owner.selection.evidence, owner.decision)
            self.assertGreater(len(owner.selection.plan.actions), 1)
            self.assertEqual(p.snapshot.base_m, ())
            self.assertEqual(p.preinput_m, ((1, 0),))
            self.assertEqual((p.snapshot.base_m_revision, p.pending_m_revision), (0, 1))
            graph = owner.selection
            owner._validate = Mock(wraps=owner._validate)
            for _ in range(3):
                permit(owner, p)
            self.assertIs(owner.selection, graph)
            self.assertIs(owner._validate.call_args.kwargs['current_mines'], owner.session.M)
            self.assertIs(owner._validate.call_args.kwargs['decision'], owner.decision)
            self.assertIs(owner._validate.call_args.kwargs['selection'], graph)
            self.assertEqual(analysis.call_count, 1)
            self.assertEqual(owner._select.call_count, 1)
            self.assertEqual(owner._select.call_args.kwargs, {})
            with self.assertRaises(LivePolicyError):
                owner.propose(state)

    def test_validation_rereads_session_m_and_rejects_changed_current_m(self):
        owner, state = after_initial()
        p = owner.propose(state)
        # Public property seam only: never inject _M/_previous or restore state.
        with patch.object(KLocalSession, 'M', new=property(lambda _self: frozenset())):
            with self.assertRaisesRegex(ValueError, 'M_MISMATCH'):
                permit(owner, p)

    def test_flag_ack_then_explicit_fresh_analysis_then_physical_chord(self):
        owner, state = after_initial()
        p = owner.propose(state)
        flagged = ((1, F, 1, H), (1, 1, 1, H))
        old_graph = owner.selection
        nxt = owner.acknowledge(k.make_ack(permit(owner, p), 'PLAYING', flagged))
        self.assertIsNone(owner.pending)
        self.assertIsNone(owner.decision)
        self.assertEqual(nxt.base_m, ((1, 0),))
        p2 = owner.propose(nxt)
        self.assertEqual(p2.action, 'CHORD')
        self.assertIsNot(owner.selection, old_graph)
        permit(owner, p2)

    def test_ack_cannot_replace_token_action_nonce_or_public_effect(self):
        for change in ('token', 'nonce', 'effect', 'regression', 'unchanged'):
            with self.subTest(change=change):
                owner, state = after_initial()
                p = owner.propose(state)
                a = k.make_ack(permit(owner, p), 'PLAYING', ((1, F, 1, H), (1, 1, 1, H)))
                if change == 'token':
                    a = replace(a, permit=replace(a.permit, proposal=replace(p, token='b' * 32)))
                elif change == 'nonce':
                    a = replace(a, permit=replace(a.permit, nonce='b' * 32))
                else:
                    grid = {'effect': ((1, F, 1, 0), (1, 1, 1, H)),
                            'regression': ((0, F, 1, H), (1, 1, 1, H)),
                            'unchanged': ONE_SETUP}[change]
                    a = replace(a, observation=grid)
                with self.assertRaises(ValueError):
                    owner.acknowledge(a)
                self.assertIs(owner.pending, p)

    def test_no_next_before_ack_no_duplicate_ack_or_nonce(self):
        owner = k.KOwner(initial(), load_timing_table())
        p = owner.propose(initial())
        request = k.KValidation(p.snapshot, p.token, 'c' * 32, 0)
        admitted = owner.validate(request)
        with self.assertRaises(ValueError):
            owner.validate(request)
        with self.assertRaises(ValueError):
            owner.propose(initial())
        ack = k.make_ack(admitted, 'PLAYING', ONE_SETUP)
        owner.acknowledge(ack)
        with self.assertRaises(ValueError):
            owner.acknowledge(ack)

    def test_terminal_is_status_first_and_never_analyzes_again(self):
        class Sentinel:
            def __iter__(self):
                raise AssertionError('terminal truth touched')
        for status in ('WON', 'LOST'):
            with self.subTest(status=status):
                owner = k.KOwner(initial(), load_timing_table())
                p = owner.propose(initial())
                admitted = permit(owner, p)
                with self.assertRaises(LivePolicyError):
                    k.make_ack(admitted, status, Sentinel())
                with patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('terminal')):
                    self.assertIsNone(owner.acknowledge(k.make_ack(admitted, status)))
                    with self.assertRaises(ValueError):
                        owner.propose(initial())
                self.assertEqual(owner.session.M, frozenset())

    def test_canonical_start_and_ui_domain_are_distinct(self):
        self.assertFalse(k.supports_board(4, 2, 1))
        for size in ((9, 9, 10), (16, 16, 40), (30, 16, 99)):
            self.assertTrue(k.supports_board(*size))
        for changes in ({'input_revision': 1}, {'cursor': (1, 0)}, {'observation': ONE_SETUP}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                k.validate_start_snapshot(replace(initial(), **changes))

    def test_exact_guess_preserves_acquired_m_without_adding_flag(self):
        owner, state = after_initial(((1, H, H, H, H),), 3)
        p = owner.propose(state)
        self.assertTrue(p.is_guess)
        self.assertEqual(p.preinput_m, ((1, 0),))
        self.assertEqual((p.action, p.x, p.y), ('OPEN', 2, 0))
        self.assertEqual(owner.selection.candidates, ())
        permit(owner, p)

    def test_finite_revalidation_budget_and_strict_transport_bound(self):
        owner = k.KOwner(initial(), load_timing_table())
        p = owner.propose(initial())
        for _ in range(k.MAX_VALIDATIONS_PER_INPUT):
            permit(owner, p)
        with self.assertRaisesRegex(ValueError, 'budget'):
            permit(owner, p)
        self.assertGreaterEqual(MAX_SEQUENCE, k.MAX_K_SEQUENCE)
        validate_message(message('a' * 32, MAX_SEQUENCE, 'VALIDATE', {}))
        for bad in (True, 1.0, MAX_SEQUENCE + 1):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                message('a' * 32, bad, 'VALIDATE', {})

    def test_strict_roundtrip_rejects_types_keys_lengths_and_bindings(self):
        owner = k.KOwner(initial(), load_timing_table())
        p = owner.propose(initial())
        admitted = permit(owner, p)
        values = (initial(), p, k.KValidation(p.snapshot, p.token, 'd' * 32, 0),
                  admitted, k.make_ack(admitted, 'PLAYING', ONE_SETUP))
        for value in values:
            with self.subTest(dto=type(value).__name__):
                raw = json.loads(json.dumps(k.to_dict(value)))
                self.assertEqual(k.from_dict(raw, type(value)), value)
                for mutation in ('extra', 'missing'):
                    bad = deepcopy(raw)
                    if mutation == 'extra':
                        bad['unknown'] = 0
                    else:
                        del bad[next(iter(bad))]
                    with self.assertRaises(ValueError):
                        k.from_dict(bad, type(value))
        for field, bad in (('width', True), ('input_seq', 0.0), ('input_revision', 1),
                           ('base_m_revision', False), ('policy_id', 'STAGE3_V1'),
                           ('definition', 'unknown'), ('profile_sha256', '0' * 64),
                           ('cursor', [False, 0]), ('observation', [[True] * 4] * 2)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                raw = k.to_dict(initial())
                raw[field] = bad
                k.from_dict(raw, k.KSnapshot)
        with self.assertRaises(ValueError):
            k.admit_proposal(p, replace(initial(), board_generation=2))

    def test_native_integrity_error_propagates_without_fallback(self):
        for code in ('SETUP_OPEN_SURVIVED', 'NO_REVEAL_CANDIDATE', 'SECOND_PASS_MINE'):
            with self.subTest(code=code):
                owner, state = after_initial()
                owner._select = Mock(side_effect=KPolicyIntegrityError(code, 'injected native failure'))
                with self.assertRaisesRegex(ValueError, code):
                    owner.propose(state)
                self.assertIsNone(owner.pending)

    def test_small_engine_first_input_cost_ack_and_fresh_flag_chord(self):
        # Tiny explicit layout stays solely in this parent engine harness.
        engine = MinesweeperEngine(5, 4, 2)
        engine.reset_with_mines(5, 4, 2, {(1, 2), (3, 2)})
        state = initial(5, 4, 2)
        owner = k.KOwner(state, load_timing_table())
        actions, costs, old = [], [], None
        for _ in range(20):
            p = owner.propose(state)
            a = permit(owner, p)
            if old is not None and not p.initial:
                self.assertIsNot(owner.selection, old)
            old = owner.selection
            costs.append(action_cost(owner.table, state.cursor, (p.x, p.y)))
            self.assertEqual(p.modeled_action_us, costs[-1])
            engine.step(p.x, p.y, p.move.action)
            status = engine.status
            after = engine.get_observation() if status is GameStatus.PLAYING else None
            state = owner.acknowledge(k.make_ack(a, status, after))
            actions.append(p.action)
            if status is not GameStatus.PLAYING:
                break
        self.assertIn('FLAG', actions)
        self.assertIn('CHORD', actions)
        self.assertTrue(owner.closed)


if __name__ == '__main__':
    unittest.main()
