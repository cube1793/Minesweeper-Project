"""Live singleton integration boundaries; native arithmetic remains native tests."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from core_engine import Action, GameStatus
from experiments.program_k_capability import KLocalSession
from experiments import program_k_lc1_policy as singleton
from experiments.program_k_lc0_policy import validate_distance_selection
from experiments.program_k_policy import KPolicyIntegrityError
import live_k_policy as k
from live_analysis import present_k_proposal, OverlayKind
from live_policy_transport import message, validate_message, PROTOCOL_VERSION
from stage3_physical import load_timing_table
from tests.live_k_lc1_fixtures import as_policy, singleton_start, singleton_engine, LC1_FIRST, BASELINE_FIRST
from tests.test_live_k_policy import initial, permit, ONE_SETUP
from tests.test_live_k_adopt import adopted
from tests.test_live_k_flag_adopt import flag_start, tiny_engine, apply


class LiveLC1OwnerTests(unittest.TestCase):
    def owner(self, state=None):
        return k.KOwner(state or singleton_start(), load_timing_table())

    def test_three_entries_distinct_definitions_strict_nested_roundtrip(self):
        for source in (initial(), adopted(), flag_start()):
            state = as_policy(source)
            with self.subTest(entry=state.entry_mode):
                owner = self.owner(state)
                p = owner.propose(owner.expected)
                request = k.KValidation(p.snapshot, p.token, uuid4().hex, p.pending_m_revision)
                admitted = owner.validate(request)
                # terminal only for non-preparation; preparation requires exact grid.
                after = (p.snapshot.bootstrap.observation_after(1) if p.is_preparation else None)
                ack = k.make_ack(admitted, 'PLAYING' if after else 'WON', after)
                for value in (state, p, request, admitted, ack):
                    self.assertEqual(k.from_dict(k.to_dict(value), type(value)), value)
                    wire = message(state.run_id, 0, 'START', k.to_dict(value))
                    self.assertEqual(validate_message(wire)['version'], 10)
                self.assertEqual(p.snapshot.policy_id, k.POLICY_K_LC1)
                self.assertEqual(p.snapshot.game_id, state.game_id)
                self.assertEqual(p.snapshot.phase, k.PHASE_PREPARATION if p.is_preparation else k.PHASE_LC1)
                for policy in (k.POLICY_K, k.POLICY_K_LC0):
                    self.assertNotEqual(state.definition, k.definition_for_entry(state.entry_mode, policy))

    def test_strict_wire_rejects_old_unknown_versions_fields_and_wrong_definition(self):
        data = k.to_dict(singleton_start())
        self.assertEqual(PROTOCOL_VERSION, 10)
        envelope = message(data['run_id'], 0, 'START', data)
        for version in (True, 0, 1, 7, 8, 9, 11, '10', 10.0):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate_message(dict(envelope, version=version))
        for key, value in (('policy_id', 'K-LC1'), ('definition', k.LC0_ADOPT_DEFINITION),
                           ('phase', k.PHASE_LC0), ('game_id', ''), ('unknown', 1)):
            bad = dict(data, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                k.from_dict(bad, k.KSnapshot)
        del data['game_id']
        with self.assertRaises(ValueError): k.from_dict(data, k.KSnapshot)

    def test_initial_zero_inference_selection_and_both_adapters(self):
        owner = self.owner(as_policy(initial()))
        with patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('analyze')), \
                patch.object(owner, '_select', side_effect=AssertionError('select')), \
                patch.object(owner, '_singleton_adapter', side_effect=AssertionError('LC1')), \
                patch.object(singleton, 'apply_distance_band', side_effect=AssertionError('LC0')):
            p = owner.propose(owner.expected)
            permit(owner, p)
        self.assertTrue(p.initial)
        self.assertIsNone(owner.singleton_selection)
        self.assertIsNone(owner.distance_selection)

    def test_override_exactly_one_native_lc1_internal_lc0_and_no_validation_display_work(self):
        owner = self.owner()
        with patch.object(KLocalSession, 'analyze_decision', autospec=True, side_effect=KLocalSession.analyze_decision) as analyze, \
                patch.object(owner, '_select', wraps=owner._select) as native, \
                patch.object(owner, '_singleton_adapter', wraps=owner._singleton_adapter) as lc1, \
                patch.object(singleton, 'apply_distance_band', wraps=singleton.apply_distance_band) as lc0, \
                patch.object(owner, '_validate_singleton', wraps=owner._validate_singleton) as validate:
            p = owner.propose(owner.expected)
            original = owner.singleton_selection
            self.assertTrue(original.exception_applied)
            self.assertEqual((p.action, p.x, p.y), LC1_FIRST)
            b = original.baseline.selected.move
            self.assertEqual((b.action.name, b.x, b.y), BASELINE_FIRST)
            self.assertIs(owner.distance_selection, original.baseline)
            self.assertIs(original.selected, owner.selection)
            self.assertIs(original.native, owner.native_selection)
            for _ in range(3):
                permit(owner, p)
                view = present_k_proposal(p)
                self.assertEqual(view.move, original.selected.move)
                self.assertIn('K-LC1', view.status_text)
                self.assertIs(view.overlays[(2, 1)].kind, OverlayKind.SAFE)
                self.assertIs(view.overlays[(2, 2)].kind, OverlayKind.MINE)
            analyze.assert_called_once()
            native.assert_called_once_with(owner.decision, p.snapshot.cursor, owner.table)
            lc1.assert_called_once_with(original.native)
            lc0.assert_called_once_with(original.native, control=False)
            self.assertEqual(validate.call_count, 3)
            self.assertTrue(all(call.args[0] is original for call in validate.call_args_list))
        with self.assertRaises(KPolicyIntegrityError):
            validate_distance_selection(replace(original.baseline, selected=original.selected))

    def test_fallback_retains_actual_baseline_and_exact_guess_skips_geometry(self):
        for state in (as_policy(adopted()), as_policy(adopted(observation=((1, -2), (-2, -2)),
                                                          mines=1, revision=1, cursor=(0, 0)))):
            owner = self.owner(state)
            if state.width == 2:
                with patch.object(singleton, '_hidden_components', side_effect=AssertionError('guess geometry')):
                    p = owner.propose(state)
                    permit(owner, p)
                self.assertTrue(p.is_guess)
                self.assertIs(owner.selection, owner.native_selection)
                self.assertIsNone(owner.selection.plan)
                self.assertEqual((p.x, p.y), owner.decision.guess_target)
                self.assertEqual((p.probabilities.selected_mine_worlds, p.probabilities.total_worlds), (1, 3))
                self.assertFalse(owner.singleton_selection.assessments)
            else:
                p = owner.propose(state)
                permit(owner, p)
                self.assertFalse(owner.singleton_selection.exception_applied)
                self.assertIs(owner.selection, owner.distance_selection.selected)

    def test_equal_copies_and_other_legal_survivors_cannot_replace_original_binding(self):
        for variant in ('singleton', 'baseline', 'native', 'decision', 'selected', 'candidates',
                        'survivors', 'baseline_selected', 'coordinated_graph', 'legal_baseline', 'pending'):
            with self.subTest(variant=variant):
                owner = self.owner()
                p = owner.propose(owner.expected)
                choice = owner.singleton_selection
                if variant == 'singleton': owner.singleton_selection = replace(choice)
                elif variant == 'baseline':
                    owner.distance_selection = replace(choice.baseline)
                    object.__setattr__(choice, 'baseline', owner.distance_selection)
                elif variant == 'native': owner.native_selection = replace(choice.native)
                elif variant == 'decision': owner.decision = replace(owner.decision)
                elif variant == 'selected':
                    owner.selection = replace(choice.selected)
                    object.__setattr__(choice, 'selected', owner.selection)
                elif variant in ('candidates', 'survivors'):
                    copied = tuple(list(getattr(choice.native, variant)))
                    object.__setattr__(choice.native, variant, copied)
                    object.__setattr__(choice.selected, variant, copied)
                elif variant == 'baseline_selected':
                    object.__setattr__(choice.baseline, 'selected', replace(choice.baseline.selected))
                elif variant == 'coordinated_graph':
                    owner.decision = replace(owner.decision)
                    for selection in (choice.native, choice.selected, choice.baseline.selected):
                        object.__setattr__(selection, 'evidence', owner.decision)
                elif variant == 'legal_baseline':
                    owner.selection = choice.baseline.selected
                    object.__setattr__(choice, 'selected', owner.selection)
                else: owner.pending = replace(p)
                with self.assertRaisesRegex(ValueError, 'original'):
                    permit(owner, p)
                self.assertEqual(owner._nonces, set())
                self.assertIsNone(owner.permit)

    def test_policy_game_run_generation_start_m_token_nonce_rejected_without_consumption(self):
        for variant in ('policy', 'game', 'run', 'generation', 'start', 'base_m', 'pending_m', 'token', 'nonce'):
            with self.subTest(variant=variant):
                owner = self.owner()
                p = owner.propose(owner.expected)
                request = k.KValidation(p.snapshot, p.token, uuid4().hex, p.pending_m_revision)
                if variant == 'policy': request = replace(request, snapshot=as_policy(p.snapshot, k.POLICY_K_LC0))
                elif variant in ('game', 'run', 'generation'):
                    key = dict(game='game_id', run='run_id', generation='board_generation')[variant]
                    request = replace(request, snapshot=replace(p.snapshot, **{key: 99 if variant == 'generation' else 'b'*32}))
                elif variant == 'start':
                    request = replace(request, snapshot=replace(p.snapshot, start_input_revision=2, input_revision=2))
                elif variant == 'base_m': object.__setattr__(request.snapshot, 'base_m_revision', 99)
                elif variant == 'pending_m': object.__setattr__(request, 'pending_m_revision', 99)
                elif variant == 'token': request = replace(request, token='c'*32)
                else: owner.validate(request)
                previous = set(owner._nonces)
                with self.assertRaises(ValueError): owner.validate(request)
                self.assertEqual(owner._nonces, previous)
                self.assertIs(owner.pending, p)

    def test_exact_ack_clears_binding_and_next_fresh_analysis_never_runs_suffix(self):
        engine = singleton_engine()
        owner = self.owner()
        p = owner.propose(owner.expected)
        original = owner.singleton_selection
        admitted = permit(owner, p)
        bad = k.make_ack(replace(admitted, nonce='a'*32), 'WON')
        with self.assertRaises(ValueError): owner.acknowledge(bad)
        self.assertIs(owner.singleton_selection, original)
        engine.step(p.x, p.y, p.move.action)
        state = owner.acknowledge(k.make_ack(admitted, engine.status, engine.get_observation()))
        for value in (owner.pending, owner.decision, owner.native_selection, owner.selection,
                      owner.singleton_selection, owner.distance_selection, owner._singleton_binding,
                      owner._original_singleton_pending): self.assertIsNone(value)
        with patch.object(owner, '_select', wraps=owner._select) as select:
            next_p = owner.propose(state)
            select.assert_called_once()
        self.assertEqual(next_p.action, 'FLAG')
        self.assertNotIn((2, 1), next_p.safe_cells)
        self.assertIsNot(owner.singleton_selection, original)
        self.assertEqual(owner.session.M, original.native.evidence.after.M)

    def test_flag_preparation_keeps_session_then_validates_actual_observation(self):
        engine = tiny_engine()
        owner = self.owner(as_policy(flag_start(engine)))
        session, proof = owner.session, owner.bootstrap_proof.analysis
        state = owner.expected
        with patch.object(KLocalSession, 'analyze_decision', autospec=True, side_effect=KLocalSession.analyze_decision) as analyze, \
                patch.object(KLocalSession, 'validate', autospec=True, side_effect=KLocalSession.validate) as validate:
            for target in ((3, 0), (4, 0)):
                p = owner.propose(state)
                self.assertEqual((p.x, p.y), target)
                self.assertTrue(p.is_preparation)
                self.assertIsNone(owner.singleton_selection)
                state, _ = apply(owner, engine, p)
            analyze.assert_not_called()
            p = owner.propose(state)
            analyze.assert_called_once()
            validate.assert_called_once_with(session, state.observation, status=GameStatus.PLAYING)
            self.assertIs(owner.session, session)
            self.assertIs(owner.bootstrap_proof.analysis, proof)
            self.assertEqual(owner.decision.observation, state.observation)
            self.assertNotEqual(owner.decision.observation, owner.bootstrap_proof.view)
            self.assertEqual(p.snapshot.phase, k.PHASE_LC1)
            permit(owner, p)

    def test_native_setup_failure_propagates_and_cannot_retry_session(self):
        owner = self.owner()
        state = owner.expected
        error = KPolicyIntegrityError('SETUP_OPEN_SURVIVED', 'sentinel')
        owner._select = Mock(side_effect=error)
        with self.assertRaises(KPolicyIntegrityError) as caught: owner.propose(state)
        self.assertIs(caught.exception, error)
        self.assertIsNone(owner.pending)
        with self.assertRaises(ValueError): owner.propose(state)
        owner._select.assert_called_once()

    def test_no_eager_native_imports_or_lifecycle_changes_needed(self):
        for filename in ('live_k_policy.py', 'ui_manager.py', 'live_analysis.py'):
            tree = ast.parse((Path(k.__file__).parent / filename).read_text('utf-8'))
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    self.assertNotIn('program_k_lc', ast.unparse(node))


class LiveLC1JobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from tests import test_live_k_job as base
        self.state = as_policy(initial())
        with patch.object(base, 'initial', return_value=self.state):
            base.LiveKJobTests.setUp(self)

    def publish(self, kind, payload):
        from tests.test_live_k_job import LiveKJobTests
        LiveKJobTests.publish(self, kind, payload)

    def pending(self):
        p = self.owner.propose(self.state)
        self.publish('PROPOSAL', k.to_dict(p))
        return p

    def validate(self, p):
        from tests.test_live_k_job import LiveKJobTests
        return LiveKJobTests.validate(self, p)

    def test_parent_exact_roundtrip_token_once_and_fresh_next(self):
        from tests.test_live_k_job import LiveKJobTests
        LiveKJobTests.test_worker_roundtrip_required_and_token_single_use_then_explicit_next(self)

    def test_parent_pause_drains_old_nonce_without_consumption(self):
        from tests.test_live_k_job import LiveKJobTests
        LiveKJobTests.test_pause_during_validation_drains_late_admission_keeps_original_pending(self)

    def test_parent_rejects_other_policy_admission_without_consumption(self):
        p = self.pending()
        admitted = self.validate(p)
        other = replace(p, snapshot=as_policy(p.snapshot, k.POLICY_K_LC0))
        self.publish('ADMITTED', k.to_dict(replace(admitted, proposal=other)))
        self.assertEqual(self.job._applied_count, 0)
        self.assertIsNotNone(self.job._failure)

    def test_worker_original_lc1_dispatch_and_no_terminal_reanalysis(self):
        import live_policy_worker as worker
        outputs = []
        def read(directory, direction, seq, run):
            if seq == 0: return message(run, seq, 'START', k.to_dict(self.state))
            if seq == 1:
                p = k.from_dict(outputs[-1]['payload'], k.KProposal)
                return message(run, seq, 'VALIDATE', k.to_dict(k.KValidation(p.snapshot, p.token, 'b'*32, 0)))
            admitted = k.from_dict(outputs[-1]['payload'], k.KPermit)
            return message(run, seq, 'ACK', k.to_dict(k.make_ack(admitted, 'LOST')))
        with patch.object(worker, 'read_next', side_effect=read), \
                patch.object(worker, 'write_once', side_effect=lambda d, c, s, m: outputs.append(m)), \
                patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('initial/terminal')):
            self.assertEqual(worker.serve('unused', self.state.run_id), 0)
        self.assertEqual([m['kind'] for m in outputs], ['PROPOSAL', 'ADMITTED', 'FINISHED'])
        self.assertEqual(outputs[-1]['payload']['permit']['proposal']['snapshot']['policy_id'], k.POLICY_K_LC1)


if __name__ == '__main__':
    unittest.main()
