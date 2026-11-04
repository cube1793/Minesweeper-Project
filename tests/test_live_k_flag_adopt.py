"""Native local bootstrap, strict preparation protocol and fixed tiny fixtures."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import live_k_policy as k
from live_k_bootstrap import KBootstrap, mask_flags
from core_engine import Action, GameStatus, MinesweeperEngine
from experiments.program_k_capability import KLocalSession
from stage3_physical import action_cost, load_timing_table


MIXED_PREFIX = (('OPEN', 0, 0), ('OPEN', 2, 0), ('FLAG', 1, 0), ('FLAG', 3, 0), ('FLAG', 4, 0))


def tiny_engine(prefix=MIXED_PREFIX):
    engine = MinesweeperEngine(5, 1, 2)
    engine.reset_with_mines(5, 1, 2, {(1, 0), (4, 0)})
    for action, x, y in prefix:
        engine.step(x, y, Action[action])
    return engine


def flag_start(engine=None, revision=5, cursor=(4, 0)):
    engine = tiny_engine() if engine is None else engine
    return k.make_snapshot(
        run_id=uuid4().hex, game_id='f' * 32, board_generation=7, input_seq=0,
        width=engine.width, height=engine.height, num_mines=engine.num_mines,
        observation=engine.get_observation(), cursor=cursor, input_revision=revision,
        entry_mode=k.FLAG_ADOPT, definition=k.FLAG_ADOPT_DEFINITION,
        start_input_revision=revision, phase=k.PHASE_BOOTSTRAP,
    )


def admit(owner, proposal):
    return owner.validate(k.KValidation(proposal.snapshot, proposal.token, uuid4().hex,
                                       proposal.pending_m_revision))


def apply(owner, engine, proposal):
    permit = admit(owner, proposal)
    engine.step(proposal.x, proposal.y, proposal.move.action)
    after = engine.get_observation() if engine.status == GameStatus.PLAYING else None
    ack = k.make_ack(permit, engine.status, after)
    return owner.acknowledge(ack), ack


class KFlagAdoptTests(unittest.TestCase):
    def setUp(self):
        self.table = load_timing_table()

    def test_bootstrap_exactly_one_native_local_without_decision_select_or_exact(self):
        state = flag_start()
        original = KLocalSession.analyze_local
        with patch.object(KLocalSession, 'analyze_local', autospec=True, side_effect=original) as local, \
                patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('decision')), \
                patch('experiments.program_k_policy.select_policy', side_effect=AssertionError('select')), \
                patch('simple_probability.calculate_probabilities', side_effect=AssertionError('exact')):
            owner = k.KOwner(state, self.table)
        local.assert_called_once()
        self.assertIs(local.call_args.args[0], owner.session)
        self.assertEqual(local.call_args.args[1], mask_flags(state.observation))
        self.assertEqual(local.call_args.kwargs, {'status': GameStatus.PLAYING})
        self.assertIs(owner.bootstrap_proof.session, owner.session)
        b = owner.expected.bootstrap
        self.assertEqual((b.mines, b.retained, b.proved_safe, b.unverified),
                         (((1, 0),), ((1, 0),), ((3, 0),), ((4, 0),)))
        self.assertEqual(owner.bootstrap_proof.analysis.after.M, owner.session.M)
        self.assertEqual(state.observation, ((1, -3, 1, -3, -3),))

    def test_mixed_fixture_preserves_retained_flag_through_preparation_and_wins(self):
        engine = tiny_engine()
        owner = k.KOwner(flag_start(engine), self.table)
        session, proof = owner.session, owner.bootstrap_proof.analysis
        state = owner.expected
        with patch.object(KLocalSession, 'analyze_local', side_effect=AssertionError('repeat local')), \
                patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('early decision')):
            for seq, x in enumerate((3, 4)):
                p = owner.propose(state)
                self.assertEqual((p.action, p.x, p.y, p.kind), ('FLAG', x, 0, 'prepare'))
                self.assertEqual((p.snapshot.input_seq, p.snapshot.preparation_seq, p.pending_m_revision), (0, seq, 1))
                self.assertEqual(p.modeled_action_us, action_cost(self.table, state.cursor, (x, 0)))
                state, ack = apply(owner, engine, p)
                self.assertEqual(engine.get_observation()[0][1], -3)
                self.assertEqual(state.input_revision, 6 + seq)
                self.assertEqual(state.base_m_revision, 1)
                self.assertIs(owner.bootstrap_proof.analysis, proof)
        self.assertEqual((state.phase, state.input_seq, state.preparation_seq, state.k_start_input_revision),
                         (k.PHASE_K, 0, 2, 7))
        owner._select = Mock(wraps=owner._select)
        original = KLocalSession.analyze_decision
        with patch.object(KLocalSession, 'analyze_decision', autospec=True, side_effect=original) as decision:
            p = owner.propose(state)
        decision.assert_called_once()
        owner._select.assert_called_once()
        self.assertEqual(owner._select.call_args.kwargs, {})
        self.assertIs(owner.session, session)
        self.assertIs(owner.selection.evidence, owner.decision)
        self.assertEqual(owner.decision.observation, state.observation)
        self.assertIsNot(owner.decision.local, proof)
        self.assertEqual((p.action, p.x, p.y, p.pending_m_revision), ('OPEN', 3, 0, 2))
        following, ack = apply(owner, engine, p)
        self.assertIsNone(following)
        self.assertEqual((engine.status, ack.input_revision), (GameStatus.WON, 8))

    def test_all_flagged_playing_has_no_initial_hidden_requirement(self):
        engine = tiny_engine(tuple(('FLAG', x, 0) for x in range(5)))
        owner = k.KOwner(flag_start(engine), self.table)
        self.assertEqual(owner.expected.bootstrap.retained, ())
        state = owner.expected
        for x in range(5):
            p = owner.propose(state)
            self.assertEqual(p.x, x)
            state, _ = apply(owner, engine, p)
        self.assertEqual((state.input_revision, state.k_start_input_revision, state.input_seq), (10, 10, 0))
        p = owner.propose(state)
        self.assertTrue(p.is_guess)
        self.assertFalse(p.initial)

    def test_preopen_flag_never_turns_into_canonical_free_open(self):
        engine = tiny_engine((('FLAG', 0, 0),))
        owner = k.KOwner(flag_start(engine, 1, (0, 0)), self.table)
        state, _ = apply(owner, engine, owner.propose(owner.expected))
        p = owner.propose(state)
        self.assertTrue(p.is_guess)
        self.assertEqual((p.x, p.y, p.pending_m_revision), (0, 0, 2))
        self.assertFalse(p.initial)

    def test_zero_removals_transition_has_no_fake_input(self):
        engine = tiny_engine(MIXED_PREFIX[:3])
        owner = k.KOwner(flag_start(engine, 3, (1, 0)), self.table)
        state = owner.expected
        self.assertEqual((state.phase, state.preparation_seq, state.input_revision, state.k_start_input_revision),
                         (k.PHASE_K, 0, 3, 3))
        self.assertEqual(state.bootstrap.removable, ())
        p = owner.propose(state)
        self.assertFalse(p.is_preparation)
        self.assertEqual(p.pending_m_revision, 2)
        admit(owner, p)

    def test_pause_validation_reuses_original_proof_and_enforces_64_nonces(self):
        owner = k.KOwner(flag_start(), self.table)
        p = owner.propose(owner.expected)
        proof = owner.bootstrap_proof.analysis
        with patch.object(KLocalSession, 'analyze_local', side_effect=AssertionError('repeat')), \
                patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('repeat')):
            for _ in range(64):
                admit(owner, p)
            with self.assertRaises(ValueError):
                admit(owner, p)
            with self.assertRaises(ValueError):
                owner.propose(p.snapshot)
        self.assertIs(proof, owner.bootstrap_proof.analysis)

    def test_strict_new_snapshot_fields_and_old_raw_m_rejection(self):
        start = flag_start()
        changes = ({'phase': k.PHASE_K}, {'phase': True}, {'bootstrap': {}}, {'base_m': ((1, 0),)},
                   {'base_m_revision': 1}, {'preparation_seq': True}, {'input_seq': 1},
                   {'start_input_revision': 0}, {'k_start_input_revision': 5}, {'input_revision': 6},
                   {'entry_mode': k.ADOPT_CURRENT, 'definition': k.ADOPT_DEFINITION},
                   {'entry_mode': k.CANONICAL_NEW, 'definition': k.DEFINITION}, {'status': 'WON'})
        for change in changes:
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(start, **change)
        state = k.KOwner(start, self.table).expected
        for change in ({'preparation_seq': 1}, {'phase': k.PHASE_K}, {'input_seq': 1},
                       {'k_start_input_revision': True}, {'k_start_input_revision': 6},
                       {'base_m_revision': 2}, {'base_m': ()}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(state, **change)

    def test_bootstrap_partition_types_domain_and_field_codecs(self):
        owner = k.KOwner(flag_start(), self.table)
        b = owner.expected.bootstrap
        p = owner.propose(owner.expected)
        permit = admit(owner, p)
        for value in (b, p.snapshot, p, permit, k.KValidation(p.snapshot, p.token, uuid4().hex, 1)):
            raw = k.to_dict(value)
            self.assertEqual(k.from_dict(raw, type(value)), value)
            for field in raw:
                changed = deepcopy(raw)
                del changed[field]
                with self.subTest(dto=type(value).__name__, missing=field), self.assertRaises(ValueError):
                    k.from_dict(changed, type(value))
            with self.assertRaises(ValueError):
                k.from_dict({**raw, 'extra': 1}, type(value))
        for change in ({'local_calls': True}, {'local_calls': 2}, {'scope': 'V1'}, {'retained': ()},
                       {'removable': ((4, 0),)}, {'proved_safe': ((1, 0),)},
                       {'flags': ((1, 0),)}, {'mines': ((30, 0),)}, {'compute_ns': -1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(b, **change)

    def test_structure_valid_summary_substitution_cannot_replace_native_proof(self):
        owner = k.KOwner(flag_start(), self.table)
        state = owner.expected
        b = replace(state.bootstrap, proved_safe=(), unverified=((3, 0), (4, 0)))
        altered = replace(state, bootstrap=b)
        with self.assertRaises(ValueError):
            owner.propose(altered)
        p = owner.propose(state)
        with self.assertRaises(ValueError):
            owner.validate(k.KValidation(altered, p.token, uuid4().hex, 1))
        forged = replace(p, snapshot=altered)
        with self.assertRaises(ValueError):
            k.admit_proposal(forged, state)

    def test_prepare_rejects_wrong_target_retained_flag_and_fake_policy_kind(self):
        owner = k.KOwner(flag_start(), self.table)
        p = owner.propose(owner.expected)
        for change in ({'x': 1}, {'x': 4}, {'x': 2}, {'action': 'OPEN'}, {'kind': 'certain'},
                       {'category': 'SETUP_CHORD'}, {'compute_ns': 1}, {'pending_m_revision': 2},
                       {'safe_cells': ((3, 0),)}, {'preinput_m': ()}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(p, **change)

    def test_ack_requires_exact_single_unflag_revision_cursor_and_permit(self):
        owner = k.KOwner(flag_start(), self.table)
        p = owner.propose(owner.expected)
        permit = admit(owner, p)
        good = k.make_ack(permit, 'PLAYING', ((1, -3, 1, -2, -3),))
        for change in ({'observation': p.snapshot.observation}, {'observation': ((1, -2, 1, -3, -3),)},
                       {'observation': ((1, -3, 1, -2, -2),)}, {'observation': ((1, -3, 1, 1, -3),)},
                       {'input_revision': 7}, {'input_revision': True}, {'cursor': (4, 0)},
                       {'status': 'WON', 'observation': None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(good, **change)
        with self.assertRaises(ValueError):
            owner.acknowledge(replace(good, permit=replace(permit, nonce=uuid4().hex)))
        owner.acknowledge(good)
        with self.assertRaises(ValueError):
            owner.acknowledge(good)

    def test_contradiction_is_not_converted_to_unverified(self):
        state = replace(flag_start(), width=3, num_mines=1, observation=((0, -3, 1),), cursor=(1, 0))
        with self.assertRaises(ValueError):
            k.KOwner(state, self.table)

    def test_per_mode_input_and_sequence_bounds(self):
        start = flag_start(revision=1000000)
        self.assertEqual(k.sequence_limit(start), 63362)
        self.assertEqual(k.MAX_K_SEQUENCE, 31681)
        self.assertEqual(k.MAX_FLAG_ADOPT_SEQUENCE, 2 * 480 * (64 + 2) + 2)
        owner = k.KOwner(start, self.table)
        self.assertEqual(owner.input_limit, 2)
        self.assertEqual(owner.expected.k_start_input_revision, 1000002)
        with self.assertRaises(ValueError):
            replace(owner.expected, preparation_seq=481)

    def test_registered_readopt_fixture_keeps_manual_waste_and_uses_fresh_proof(self):
        engine = tiny_engine()
        first = k.KOwner(flag_start(engine), self.table)
        state, _ = apply(first, engine, first.propose(first.expected))
        self.assertEqual((state.input_revision, state.cursor), (6, (3, 0)))
        engine.step(0, 0, Action.OPEN)  # Recorded manual no-op after retirement.
        second = k.KOwner(flag_start(engine, 7, (0, 0)), self.table)
        self.assertIsNot(first.session, second.session)
        self.assertEqual(second.expected.bootstrap.removable, ((4, 0),))
        self.assertEqual(second.expected.bootstrap.retained, ((1, 0),))
        p = second.propose(second.expected)
        self.assertEqual((p.action, p.x), ('FLAG', 4))
        state, _ = apply(second, engine, p)
        self.assertEqual(state.k_start_input_revision, 8)
        p = second.propose(state)
        self.assertEqual((p.action, p.x), ('OPEN', 3))
        state, ack = apply(second, engine, p)
        self.assertIsNone(state)
        self.assertEqual((engine.status, ack.input_revision), (GameStatus.WON, 9))

    def test_registered_canonical_and_flag_free_fixtures(self):
        for entry, prefix, expected in (
                (k.CANONICAL_NEW, (), (0, 2, 3)),
                (k.ADOPT_CURRENT, (('OPEN', 0, 0),), (2, 3))):
            with self.subTest(entry=entry):
                engine = tiny_engine(prefix)
                state = k.make_snapshot(run_id=uuid4().hex, game_id='f' * 32, board_generation=7, input_seq=0,
                                        width=5, height=1, num_mines=2,
                                        observation=engine.get_observation(), cursor=(0, 0),
                                        entry_mode=entry, definition=k.definition_for_entry(entry),
                                        start_input_revision=len(prefix), input_revision=len(prefix))
                owner = k.KOwner(state, self.table)
                for x in expected:
                    p = owner.propose(state)
                    self.assertEqual((p.action, p.x, p.y), ('OPEN', x, 0))
                    state, _ = apply(owner, engine, p)
                self.assertIsNone(state)
                self.assertEqual(engine.status, GameStatus.WON)

    def test_registered_v1_flag_review_fixture(self):
        import live_policy as v1
        engine = tiny_engine()
        state = v1.make_snapshot(run_id=uuid4().hex, board_generation=7, input_seq=0,
                                 width=5, height=1, num_mines=2,
                                 observation=engine.get_observation(), cursor=(4, 0),
                                 entry_mode=v1.ADOPT_CURRENT, input_revision=5,
                                 phase=v1.PHASE_FLAG_REVIEW, initial_flag_count=3)
        review = None
        for action, x in (('FLAG', 3), ('FLAG', 4), ('OPEN', 3)):
            p = v1.plan_snapshot(state, table=self.table,
                                 review=review if state.phase == v1.PHASE_FLAG_REVIEW else None)
            review = p.review
            self.assertEqual((p.action, p.x, p.y), (action, x, 0))
            engine.step(x, 0, p.move.action)
            after = engine.get_observation() if engine.status == GameStatus.PLAYING else None
            state = v1.validate_ack(p, v1.make_ack(p, engine.status, after))
        self.assertIsNone(state)
        self.assertEqual(engine.status, GameStatus.WON)

