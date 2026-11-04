"""LC0 Live identity, original-graph/ranking and strict wire boundary tests."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from core_engine import Action, GameStatus
from experiments.program_k_capability import KLocalSession
from experiments.program_k_lc0_policy import apply_distance_band, validate_distance_selection
from experiments.program_k_policy import KPolicyIntegrityError
from experiments.program_k_runner import validate_k_p0_execution
import live_k_policy as k
import live_policy_job as jobs
import live_policy_worker as worker
from live_policy_transport import message, read_next, write_once, validate_message, PROTOCOL_VERSION
from stage3_physical import load_timing_table
from tests.test_live_k_policy import initial, permit, ONE_SETUP
from tests.test_live_k_adopt import adopted
from tests.test_live_k_flag_adopt import flag_start, tiny_engine, apply
from tests.live_k_lc0_fixtures import distance_engine, DISTANCE_PREFIX, LC0_FIRST, P0_FIRST


def lc0(state):
    return replace(state, policy_id=k.POLICY_K_LC0,
                   definition=k.definition_for_entry(state.entry_mode, k.POLICY_K_LC0),
                   phase=state.phase if state.phase in (k.PHASE_BOOTSTRAP, k.PHASE_PREPARATION) else k.PHASE_LC0)


def distance_owner(policy=k.POLICY_K_LC0):
    engine = distance_engine()
    state = flag_start(engine, revision=len(DISTANCE_PREFIX), cursor=(1, 3))
    if policy == k.POLICY_K_LC0:
        state = lc0(state)
    owner = k.KOwner(state, load_timing_table())
    return engine, owner, owner.expected


class LiveLC0OwnerTests(unittest.TestCase):
    def test_each_entry_distinct_definition_and_all_nested_wire_bindings(self):
        for entry, state in ((k.CANONICAL_NEW, initial()), (k.ADOPT_CURRENT, adopted()),
                             (k.FLAG_ADOPT, flag_start())):
            with self.subTest(entry=entry):
                state = lc0(state)
                owner = k.KOwner(state, load_timing_table())
                p = owner.propose(owner.expected)
                req = k.KValidation(p.snapshot, p.token, uuid4().hex, p.pending_m_revision)
                admitted = owner.validate(req)
                for value in (state, p, req, admitted):
                    self.assertEqual(k.from_dict(k.to_dict(value), type(value)), value)
                self.assertEqual(p.snapshot.policy_id, k.POLICY_K_LC0)
                self.assertEqual(p.snapshot.definition, k.definition_for_entry(entry, k.POLICY_K_LC0))
                self.assertNotEqual(p.snapshot.definition, k.definition_for_entry(entry))
                self.assertEqual(p.snapshot.game_id, state.game_id)
                self.assertEqual(p.snapshot.start_input_revision, state.start_input_revision)

    def test_initial_does_no_analysis_selection_or_distance_work(self):
        owner = k.KOwner(lc0(initial()), load_timing_table())
        with patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('analysis')), \
                patch.object(owner, '_select', side_effect=AssertionError('native')), \
                patch.object(owner, '_distance_adapter', side_effect=AssertionError('distance')):
            p = owner.propose(owner.expected)
            permit(owner, p)
        self.assertTrue(p.initial)
        self.assertIsNone(owner.distance_selection)

    def test_real_lc0_override_one_analysis_one_native_control_false_and_retained_identity(self):
        engine, owner, state = distance_owner()
        self.assertEqual(state.phase, k.PHASE_LC0)
        self.assertEqual(state.bootstrap.removable, ())
        with patch.object(KLocalSession, 'analyze_decision', autospec=True, side_effect=KLocalSession.analyze_decision) as analyze, \
                patch.object(owner, '_select', wraps=owner._select) as select, \
                patch.object(owner, '_distance_adapter', wraps=owner._distance_adapter) as distance, \
                patch.object(owner, '_validate_distance', wraps=owner._validate_distance) as rank:
            p = owner.propose(state)
            choice = owner.distance_selection
            self.assertEqual((p.action, p.x, p.y), LC0_FIRST)
            self.assertEqual((choice.native.move.action.name, choice.native.move.x, choice.native.move.y), P0_FIRST)
            self.assertTrue(choice.overridden)
            self.assertFalse(choice.control)
            self.assertIs(choice.native, owner.native_selection)
            self.assertIs(choice.selected, owner.selection)
            self.assertIs(choice.native.evidence, owner.decision)
            self.assertIs(choice.selected.evidence, owner.decision)
            self.assertIs(choice.selected.survivors, choice.native.survivors)
            self.assertIs(choice.selected.candidates, choice.native.candidates)
            for _ in range(3):
                permit(owner, p)
            analyze.assert_called_once()
            select.assert_called_once_with(owner.decision, state.cursor, owner.table)
            distance.assert_called_once_with(choice.native, control=False)
            self.assertEqual(rank.call_count, 3)
            self.assertTrue(all(c.args[0] is choice for c in rank.call_args_list))
            self.assertIs(owner.distance_selection, choice)

    def test_physically_safe_native_g_is_rejected_as_lc0_substitute(self):
        _, owner, state = distance_owner()
        p = owner.propose(state)
        g = owner.native_selection
        validate_k_p0_execution(state.observation, g.move, status=GameStatus.PLAYING,
            num_mines=state.num_mines, cursor=state.cursor, current_mines=owner.session.M,
            decision=owner.decision, selection=g)
        owner.selection = g
        with self.assertRaisesRegex(ValueError, 'original native graph'):
            permit(owner, p)

    def test_wrong_rank_even_with_matching_replaced_pending_and_safe_selection_rejected(self):
        _, owner, state = distance_owner()
        p = owner.propose(state)
        g = owner.native_selection
        # Deliberate corruption of the retained frozen object exercises ranking,
        # independently of the identity guard against replacing that object.
        object.__setattr__(owner.distance_selection, 'selected', g)
        object.__setattr__(owner.distance_selection, 'reason', 'NATIVE_G_RETAINED')
        owner.selection = g
        owner.pending = replace(p, action=g.move.action.name, x=g.move.x, y=g.move.y, category=g.category)
        with self.assertRaises(KPolicyIntegrityError):
            permit(owner, owner.pending)

    def test_equal_distance_choice_copy_cannot_replace_original_and_display_uses_lc0(self):
        from live_analysis import present_k_proposal, OverlayKind
        _,owner,state=distance_owner()
        p=owner.propose(state)
        original=owner.distance_selection
        view=present_k_proposal(p)
        self.assertIn('K-LC0',view.status_text)
        self.assertEqual(view.move,original.selected.move)
        self.assertNotEqual(view.move,original.native.move)
        self.assertTrue(view.overlays[(p.x,p.y)].recommended)
        self.assertTrue(all(view.overlays[cell].kind is OverlayKind.SAFE for cell in p.safe_cells))
        self.assertTrue(all(overlay.probability is None for overlay in view.overlays.values()))
        owner.distance_selection=replace(original)
        with self.assertRaisesRegex(ValueError,'original native graph'):
            permit(owner,p)

    def test_control_and_detached_original_graph_are_rejected_in_validate(self):
        for variant in ('control', 'native', 'decision', 'selected'):
            with self.subTest(variant=variant):
                _, owner, state = distance_owner()
                p = owner.propose(state)
                if variant == 'control':
                    owner.distance_selection = apply_distance_band(owner.native_selection, control=True)
                    owner.selection = owner.distance_selection.selected
                elif variant == 'native':
                    owner.native_selection = replace(owner.native_selection)
                elif variant == 'decision':
                    owner.decision = replace(owner.decision)
                else:
                    owner.selection = replace(owner.selection)
                with self.assertRaises(ValueError):
                    permit(owner, p)

    def test_other_policy_game_entry_start_generation_token_nonce_and_m_are_rejected(self):
        for variant in ('policy', 'game', 'generation', 'run', 'start', 'token', 'nonce', 'M'):
            with self.subTest(variant=variant):
                owner = k.KOwner(lc0(adopted()), load_timing_table())
                p = owner.propose(owner.expected)
                request = k.KValidation(p.snapshot, p.token, uuid4().hex, p.pending_m_revision)
                if variant == 'policy':
                    state = replace(p.snapshot, policy_id=k.POLICY_K, definition=k.ADOPT_DEFINITION, phase=k.PHASE_K)
                    request = replace(request, snapshot=state)
                elif variant in ('game', 'generation', 'run'):
                    key = dict(game='game_id', generation='board_generation', run='run_id')[variant]
                    request = replace(request, snapshot=replace(p.snapshot, **{key: 99 if variant=='generation' else 'c'*32}))
                elif variant == 'start':
                    request = replace(request, snapshot=replace(p.snapshot, start_input_revision=504, input_revision=504))
                elif variant == 'token':
                    request = replace(request, token='b'*32)
                elif variant == 'nonce':
                    owner.validate(request)
                else:
                    request = object.__new__(k.KValidation)
                    for name, value in vars(k.KValidation(p.snapshot, p.token, uuid4().hex, p.pending_m_revision)).items():
                        object.__setattr__(request, name, value)
                    object.__setattr__(request, 'pending_m_revision', 99)
                with self.assertRaises(ValueError):
                    owner.validate(request)

    def test_cross_policy_ack_is_not_the_original_permit(self):
        owner = k.KOwner(lc0(initial()), load_timing_table())
        p = owner.propose(owner.expected)
        a = permit(owner, p)
        other = replace(p, snapshot=replace(p.snapshot, policy_id=k.POLICY_K, definition=k.DEFINITION, phase=k.PHASE_K))
        ack = k.make_ack(replace(a, proposal=other), 'PLAYING', ONE_SETUP)
        with self.assertRaisesRegex(ValueError, 'permit/nonce'):
            owner.acknowledge(ack)

    def test_exact_guess_keeps_original_risk_target_no_setup(self):
        state = lc0(adopted(observation=((1,-2),(-2,-2)), mines=1, revision=1, cursor=(0,0)))
        owner = k.KOwner(state, load_timing_table())
        p = owner.propose(state)
        self.assertTrue(p.is_guess)
        self.assertIs(owner.selection, owner.native_selection)
        self.assertIsNone(owner.selection.plan)
        self.assertEqual((p.x,p.y), owner.decision.guess_target)
        self.assertEqual(p.probabilities.selected_mine_worlds, 1)
        self.assertEqual(p.probabilities.total_worlds, 3)
        permit(owner,p)

    def test_native_integrity_failure_is_not_a_fallback(self):
        owner = k.KOwner(lc0(adopted()), load_timing_table())
        owner._select = Mock(side_effect=KPolicyIntegrityError('SETUP_OPEN_SURVIVED','test'))
        with self.assertRaises(KPolicyIntegrityError): owner.propose(owner.expected)
        self.assertIsNone(owner.pending)
        self.assertIsNone(owner.expected)
        self.assertEqual(owner._select.call_count, 1)

    def test_mixed_flags_same_session_actual_observation_then_lc0_first_only(self):
        engine = tiny_engine()
        owner = k.KOwner(lc0(flag_start(engine)), load_timing_table())
        session = owner.session
        proof = owner.bootstrap_proof.analysis
        state = owner.expected
        with patch.object(KLocalSession,'analyze_decision',autospec=True,side_effect=KLocalSession.analyze_decision) as analyze, \
                patch.object(KLocalSession,'validate',autospec=True,side_effect=KLocalSession.validate) as validate:
            for target in ((3,0),(4,0)):
                p=owner.propose(state)
                self.assertEqual((p.x,p.y),target)
                self.assertTrue(p.is_preparation)
                self.assertIsNone(owner.distance_selection)
                state,ack=apply(owner,engine,p)
                self.assertEqual(ack.permit.proposal.snapshot.policy_id,k.POLICY_K_LC0)
            analyze.assert_not_called()
            self.assertEqual(state.phase,k.PHASE_LC0)
            p=owner.propose(state)
            self.assertIs(owner.session,session)
            self.assertIs(owner.bootstrap_proof.analysis,proof)
            analyze.assert_called_once()
            validate.assert_called_once_with(session,state.observation,status=GameStatus.PLAYING)
            self.assertEqual(owner.decision.observation,state.observation)
            self.assertNotEqual(owner.decision.observation,owner.bootstrap_proof.view)
            self.assertIs(owner.selection,owner.distance_selection.selected)
            permit(owner,p)

    def test_ack_discards_original_choice_and_requires_fresh_next_not_suffix(self):
        owner=k.KOwner(lc0(adopted(cursor=(0,0))),load_timing_table())
        p=owner.propose(owner.expected)
        self.assertEqual(p.action,'FLAG')
        old=owner.distance_selection
        self.assertGreater(len(old.selected.plan.actions),1)
        grid=tuple(tuple(-3 if (x,y)==(p.x,p.y) else v for x,v in enumerate(row)) for y,row in enumerate(p.snapshot.observation))
        state=owner.acknowledge(k.make_ack(permit(owner,p),'PLAYING',grid))
        self.assertIsNone(owner.distance_selection)
        self.assertIsNone(owner.native_selection)
        self.assertIsNone(owner.decision)
        owner._select=Mock(side_effect=RuntimeError('fresh selection failure'))
        with self.assertRaisesRegex(RuntimeError,'fresh selection'): owner.propose(state)
        self.assertIsNone(owner.pending)

    def test_p0_same_fixture_stays_native_and_never_loads_distance_adapter(self):
        _,owner,state=distance_owner(k.POLICY_K)
        p=owner.propose(state)
        self.assertEqual((p.action,p.x,p.y),P0_FIRST)
        self.assertIs(owner.selection,owner.native_selection)
        self.assertIsNone(owner._distance_adapter)
        self.assertIsNone(owner.distance_selection)
        permit(owner,p)

    def test_wire_v9_rejects_all_old_versions_and_missing_game_id(self):
        self.assertEqual(PROTOCOL_VERSION,9)
        envelope=message('a'*32,0,'START',k.to_dict(lc0(initial())))
        for version in (True,1,2,3,4,5,6,7,8,10):
            with self.subTest(version=version),self.assertRaises(ValueError):
                validate_message(dict(envelope,version=version))
        data=deepcopy(envelope['payload'])
        del data['game_id']
        with self.assertRaises(ValueError): k.from_dict(data,k.KSnapshot)

    def test_no_eager_lc_runtime_and_protected_numeric_bounds(self):
        tree=ast.parse(Path(k.__file__).read_text('utf-8'))
        top=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertFalse(any('program_k_' in ast.unparse(n) for n in top))
        self.assertEqual((k.MAX_K_INPUTS,k.MAX_VALIDATIONS_PER_INPUT,k.MAX_K_SEQUENCE,k.MAX_FLAG_ADOPT_SEQUENCE),(480,64,31681,63362))


class LiveLC0JobTests(unittest.TestCase):
    def test_inprocess_worker_dispatch_lc0_initial_validate_terminal_ack(self):
        import tempfile
        state=lc0(initial(2,1,0))
        owner=k.KOwner(state,load_timing_table())
        p=owner.propose(state)
        request=k.KValidation(state,p.token,'c'*32,0)
        ack=k.make_ack(k.KPermit(p,request.nonce),'WON')
        commands=iter([message(state.run_id,0,'START',k.to_dict(state)),
                       message(state.run_id,1,'VALIDATE',k.to_dict(request)),
                       message(state.run_id,2,'ACK',k.to_dict(ack))])
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(worker,'read_next',side_effect=lambda *a: next(commands)), \
                patch.object(k,'KOwner',return_value=owner), \
                patch.object(owner,'propose',return_value=p):
            self.assertEqual(worker.serve(directory,state.run_id),0)
            payload=read_next(directory,'worker',2,state.run_id)['payload']
            self.assertEqual(payload['permit']['proposal']['snapshot']['policy_id'],k.POLICY_K_LC0)
            self.assertEqual(payload['permit']['proposal']['snapshot']['game_id'],state.game_id)

    def test_parent_rejects_other_policy_permit_without_consumption(self):
        from tests.test_live_k_job import LiveKJobTests
        case=LiveKJobTests()
        case.setUpClass()
        case.setUp()
        try:
            p=case.pending()
            admitted=case.validate(p)
            altered=replace(p,snapshot=lc0(p.snapshot))
            case.publish('ADMITTED',k.to_dict(replace(admitted,proposal=altered)))
            self.assertEqual(case.job._applied_count,0)
            self.assertIsNotNone(case.job._failure)
        finally: case.doCleanups()
