"""Slice-3 public audit tests, using manually detached public evidence only.

Frozen case identities are metadata bindings, not executed research fixtures.
No board is generated, materialized, stepped, or supplied as an audit answer.
The public observations below are declared synthetic literals, and are not
claims about the corresponding frozen layout's actual execution.
"""

import ast
from contextlib import ExitStack, contextmanager
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from enum import Enum
from fractions import Fraction
import hashlib
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus
from experiments import program_k_capability as capability
from experiments import program_k_e1_audit as audit
from experiments import program_k_e1_execution as execution
from experiments import program_k_e1_harness as e1
from experiments import program_k_evidence as evidence
from experiments import program_k_harness as harness
from experiments import program_k_oracles as oracles
from experiments import program_k_policy as policy
from experiments import program_k_runner as runner
from simple_algorithm import SimpleMove
from simple_decision import DecisionKind
import stage3_physical as physical
from stage3_planner import plan_position
from stage3_runner import Stage3ActionTrace, Stage3RunResult


ROOT = Path(__file__).resolve().parents[1]
H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)
_PLAN = None


def _plan():
    """Seal public metadata directly; deliberately never seal/generate boards."""
    global _PLAN
    if _PLAN is None:
        prerequisite = e1.AcceptedE0Prerequisite(
            e1.ACCEPTED_E0_RUN_ID, e1.ACCEPTED_E0_QUALIFICATION_SHA256,
            e1.ACCEPTED_E0_SOURCE_DIGEST, "E0_PASS", "E0_QUALIFIED",
            e1.ACCEPTED_P8_EVIDENCE_DIGEST, e1.FROZEN_SPEC_SHA256,
            e1.FROZEN_PROTOCOL_SHA256, e1.MODEL_ID, e1.PROFILE_SHA256,
            e1.TABLE_SHA256,
        )
        runtime = e1.capture_runtime_identity()
        cases = []
        for case_id in e1.CASE_IDS:
            definition = e1._definition(case_id)
            index = definition.game_index
            cases.append(e1.SealedCaseRegistration(
                case_id, definition.source_type, definition.width,
                definition.height, definition.num_mines, (0, 0),
                None if index is None else "EXPERT_GENERAL_V1",
                None if index is None else "V1",
                None if index is None else "game_index",
                index, index, case_id if index is None else None,
                definition.board_fingerprint, definition.provenance,
                definition.prior_exposure, definition.overlap, definition.purpose,
                definition.permitted_claims, runtime,
            ))
        _PLAN = e1.E1Plan(
            prerequisite, e1.capture_e1_source_identity(prerequisite), runtime,
            tuple(cases), e1.build_schedule(),
        )
    return _PLAN


def _corrupt(value, **changes):
    """Fault injection preserves the exact detached record type."""
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            result, field.name, changes.get(field.name, getattr(value, field.name)))
    return result


def _replace_trace(archive, index, **changes):
    result = archive.result
    traces = list(result.traces)
    traces[index] = _corrupt(traces[index], **changes)
    if archive.schedule_entry.variant == "CONTROL":
        result = _corrupt(result, control=_corrupt(result.control, traces=tuple(traces)))
    else:
        result = _corrupt(result, traces=tuple(traces))
    return _corrupt(archive, result=result)


def _replace_effect(archive, index, **changes):
    if archive.schedule_entry.variant == "CONTROL":
        effects = list(archive.result.effects)
        effects[index] = _corrupt(effects[index], **changes)
        return _corrupt(archive, result=_corrupt(archive.result, effects=tuple(effects)))
    return _replace_trace(
        archive, index,
        public_effect=_corrupt(archive.result.traces[index].public_effect, **changes))


def _public_result(variant, width, height, num_mines, prefixes=()):
    """Archive declared public transitions without a physical input or Engine.

    ``prefixes`` lists the public observations after the canonical initial
    input and after each subsequent nonterminal input. A final public LOST
    marker terminates the fixture; it is never read as proof of a mine.
    """
    table = physical.load_timing_table()
    hidden = tuple((H,) * width for _ in range(height))
    observations = (hidden,) + tuple(prefixes)
    owner = capability.KLocalSession(width, height, num_mines)
    cursor, proofs, traces, effects, spans = (0, 0), (), [], [], []
    shadow = runner.ShadowCheckpoint()
    for index, before in enumerate(observations):
        initial = index == 0
        previous_m = owner.M
        decision = selection = k_decision = flag = soundness = None
        if initial:
            move = SimpleMove(Action.OPEN, 0, 0)
            category = "POLICY_INITIAL_OPEN"
        elif variant == "K-P0":
            k_decision = owner.analyze_decision(before, status=GameStatus.PLAYING)
            selection = policy.select_policy(k_decision, cursor, table)
            move, category = selection.move, selection.category
        else:
            decision = plan_position(before, num_mines, cursor, table)
            move = decision.move
            if variant == "K-CONTROL":
                admission = capability.CurrentPhysicalFlagAdmission(
                    before, frozenset((p.move.x, p.move.y) for p in proofs))
                k_decision = owner.analyze_decision(
                    before, status=GameStatus.PLAYING, physical_flag_admission=admission)
                shadow = runner.ShadowCheckpoint(
                    last_valid_M=owner.M, decision=k_decision,
                    last_valid_boundary=index, evidence_valid=True)
                soundness = evidence.compare_shadow_soundness(
                    evidence.project_v1_decision(decision),
                    k_decision.selection_safe_cells, boundary=index)
                if move.action is Action.FLAG:
                    flag = evidence.make_v1_flag_provenance(
                        before, decision, num_mines=num_mines,
                        boundary=index, prior_flags=proofs)
        final = index == len(observations) - 1
        if final:
            rows = [list(row) for row in before]
            if move.action is Action.OPEN:
                rows[move.y][move.x] = int(CellState.EXPLODED)
            elif move.action is Action.FLAG:
                rows[move.y][move.x] = F
            elif move.action is Action.CHORD:
                for y in range(max(0, move.y-1), min(height, move.y+2)):
                    for x in range(max(0, move.x-1), min(width, move.x+2)):
                        if before[y][x] == H:
                            rows[y][x] = 0
            after = tuple(tuple(row) for row in rows)
            status = GameStatus.LOST
        else:
            after, status = observations[index + 1], GameStatus.PLAYING
        cost = table[abs(move.x - cursor[0])][abs(move.y - cursor[1])]
        effect = evidence.make_public_effect(
            before, move, after, input_index=index, status_after=status,
            cursor_before=cursor, modeled_action_us=cost)
        if variant == "CONTROL":
            span = evidence.DecisionTimings(
                v1_plan_position_ns=None if initial else 11, evidence_ns=13)
            trace = Stage3ActionTrace(
                move, decision, span.v1_plan_position_ns, cursor, cost, status,
                effect.safe_cells_opened_delta, effect.explicit_flag_delta)
        elif variant == "K-P0":
            span = evidence.DecisionTimings(
                k_analysis_planning_ns=None if initial else 17,
                k_execution_validation_ns=19, evidence_ns=23)
            trace = runner.KActionTrace(
                index, move, category, selection, cursor, cost, status,
                previous_m, owner.M, span, effect, "CAPTURED")
        else:
            span = evidence.DecisionTimings(
                v1_plan_position_ns=None if initial else 11,
                v1_execution_validation_ns=19,
                shadow_ns=None if initial else 29,
                comparison_ns=None if initial else 31, evidence_ns=13)
            trace = runner.KControlActionTrace(
                index, before, decision, move, cursor, cost, status, shadow,
                previous_m, owner.M, span, effect, "CAPTURED",
                soundness, flag, proofs)
        traces.append(trace)
        effects.append(effect)
        spans.append(span)
        cursor = (move.x, move.y)
        if flag is not None and not final:
            proofs += (flag,)
    traces = tuple(traces)
    if variant == "CONTROL":
        return runner.ControlCaptureResult(
            Stage3RunResult(status, traces), tuple(effects), tuple(spans))
    if variant == "K-P0":
        return runner.KRunResult(status, traces, owner.M)
    return runner.KControlRunResult(
        status, traces, replace(shadow, decision=None, evidence_valid=False))


def _archive(variant="K-P0", case_id="S-LOSS", prefixes=None):
    plan = _plan()
    case = next(item for item in plan.cases if item.case_id == case_id)
    if prefixes is None:
        prefixes = {
            "S-WIN": (),
            "S-LOSS": (((1, H, H, H, H),),),
            "S-LIFECYCLE": (((1, H, 1, H),),),
            "X-0": (((1,) + (H,) * 29,) + ((H,) * 30,) * 15,),
        }[case_id]
        if case_id == "S-LOSS" and variant != "K-P0":
            prefixes += (((1, F, H, H, H),),)
    result = _public_result(variant, case.width, case.height, case.num_mines, prefixes)
    receipt = execution.CaseMaterializationReceipt(
        case.case_id, case.source_type, case.width, case.height,
        case.num_mines, case.first_click, case.game_index, case.seed,
        case.board_fingerprint, case.runtime,
        "FIXED_SYNTHETIC_RESET" if case.game_index is None else "EXPERT_GENERAL_V1_RESET",
    )
    entry = next(item for item in plan.schedule
                 if item.case_id == case_id and item.variant == variant and item.repetition == 1)
    return execution.E1ScheduledRunArchive(
        execution.capture_execution_source_identity(plan), plan.source_identity.digest,
        entry, case, receipt, result, 1.0,
        "APPLIED" if variant == "K-CONTROL" else "NOT_APPLICABLE")


class AuditCase(unittest.TestCase):
    def checked(self, archive=None):
        return audit.audit_scheduled_run(_plan(), _archive() if archive is None else archive)

    def assertFails(self, archive):
        result = self.checked(archive)
        self.assertEqual(result.audit_status, "FAIL", result)
        self.assertTrue(result.discrepancies)
        return result


class SourceAndBindingTests(AuditCase):
    def test_current_execution_identity_bound_exactly(self):
        archive = _archive()
        source = audit.capture_audit_source_identity(_plan(), archive)
        self.assertEqual(source.execution_source_digest, archive.execution_source_identity.digest)
        self.assertEqual(source.execution_source_digest,
                         "45b1e40ad36f473a4682f36a152fea2904bcf0b58d0fb4c7016e7930356aac82")

    def test_exact_audit_bytes_and_size(self):
        source = audit.capture_audit_source_identity(_plan(), _archive())
        raw = Path(audit.__file__).read_bytes()
        self.assertEqual(source.audit_file.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(source.audit_file.size_bytes, len(raw))
        self.assertEqual(source.audit_file.path, "experiments/program_k_e1_audit.py")

    def test_identity_is_deterministic(self):
        archive = _archive()
        first = audit.capture_audit_source_identity(_plan(), archive)
        second = audit.capture_audit_source_identity(_plan(), archive)
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)

    def test_test_file_excluded_from_runtime_identity(self):
        source = audit.capture_audit_source_identity(_plan(), _archive())
        self.assertNotIn("test_program_k_e1_audit", repr(source))
        self.assertEqual(source.audit_file.path, audit.AUDIT_SOURCE_PATH)

    def test_temporary_audit_byte_mutation_changes_identity(self):
        archive = _archive()
        with TemporaryDirectory() as directory:
            target = Path(directory) / audit.AUDIT_SOURCE_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes(Path(audit.__file__).read_bytes())
            first = audit._capture_audit_source_identity(_plan(), archive, Path(directory))
            target.write_bytes(target.read_bytes() + b"\n# temporary source identity probe\n")
            second = audit._capture_audit_source_identity(_plan(), archive, Path(directory))
        self.assertNotEqual(first.digest, second.digest)
        self.assertEqual(first.execution_source_digest, second.execution_source_digest)

    def test_execution_source_drift_rejected(self):
        archive = _archive()
        changed_file = replace(archive.execution_source_identity.execution_file, sha256="a" * 64)
        changed = replace(archive.execution_source_identity, execution_file=changed_file)
        with patch.object(execution, "capture_execution_source_identity", return_value=changed):
            with self.assertRaises(audit.E1AuditError):
                self.checked(archive)

    def test_plan_digest_substitution_rejected_before_oracles(self):
        archive = _corrupt(_archive(), plan_source_digest="b" * 64)
        with patch.object(oracles, "enumerate_public_worlds") as oracle:
            with self.assertRaises(audit.E1AuditError):
                self.checked(archive)
        oracle.assert_not_called()

    def test_schedule_substitution_rejected(self):
        archive = _archive()
        archive = _corrupt(archive, schedule_entry=_plan().schedule[0])
        with self.assertRaises(audit.E1AuditError):
            self.checked(archive)

    def test_case_substitution_rejected(self):
        with self.assertRaises(audit.E1AuditError):
            self.checked(_corrupt(_archive(), case=_plan().cases[0]))

    def test_receipt_binding_rejected(self):
        archive = _archive()
        receipt = _corrupt(archive.receipt, board_fingerprint="c" * 64)
        with self.assertRaises(audit.E1AuditError):
            self.checked(_corrupt(archive, receipt=receipt))

    def test_structural_completion_required(self):
        with self.assertRaises(audit.E1AuditError):
            self.checked(_corrupt(_archive(), completion_status="INCOMPLETE"))

    def test_variant_result_class_required(self):
        archive = _archive()
        other = _archive("CONTROL").result
        with self.assertRaises(audit.E1AuditError):
            self.checked(_corrupt(archive, result=other))

    def test_exact_input_types_required(self):
        for plan, archive in ((None, _archive()), (_plan(), object())):
            with self.subTest(plan=type(plan), archive=type(archive)):
                with self.assertRaises(audit.E1AuditError):
                    audit.audit_scheduled_run(plan, archive)

    def test_caller_cannot_override_public_premises(self):
        for name in ("case", "variant", "num_mines", "logical_M", "observation", "hidden_answer"):
            with self.subTest(name=name):
                with self.assertRaises(TypeError):
                    audit.audit_scheduled_run(_plan(), _archive(), **{name: None})

    def test_source_identity_checked_after_work(self):
        archive = _archive()
        original = audit.capture_audit_source_identity(_plan(), archive)
        changed = replace(original, audit_file=replace(original.audit_file, sha256="d" * 64))
        with patch.object(audit, "capture_audit_source_identity",
                          side_effect=(original, changed)) as capture:
            with self.assertRaises(audit.E1AuditError):
                self.checked(archive)
        self.assertEqual(capture.call_count, 2)

    def test_none_trace_collection_rejected_before_oracle_work(self):
        for variant in e1.VARIANTS:
            archive = _archive(variant)
            if variant == "CONTROL":
                changed = _corrupt(
                    archive.result,
                    control=_corrupt(archive.result.control, traces=None))
            else:
                changed = _corrupt(archive.result, traces=None)
            with self.subTest(variant=variant), patch.object(
                    oracles, "collect_oracle_diagnostics") as collector:
                with self.assertRaises(audit.E1AuditError):
                    self.checked(_corrupt(archive, result=changed))
                collector.assert_not_called()

    def test_wrong_known_trace_record_rejected_before_oracle_work(self):
        archive = _archive()
        result = _corrupt(
            archive.result,
            traces=(archive.result.traces[0], evidence.DecisionTimings()))
        with patch.object(oracles, "collect_oracle_diagnostics") as collector:
            with self.assertRaises(audit.E1AuditError):
                self.checked(_corrupt(archive, result=result))
        collector.assert_not_called()

    def test_none_control_effect_or_timing_collection_rejected(self):
        archive = _archive("CONTROL")
        for name in ("effects", "timings"):
            with self.subTest(collection=name), patch.object(
                    oracles, "collect_oracle_diagnostics") as collector:
                changed = _corrupt(archive.result, **{name: None})
                with self.assertRaises(audit.E1AuditError):
                    self.checked(_corrupt(archive, result=changed))
                collector.assert_not_called()

    def test_malformed_nested_shadow_failure_rejected_before_oracle_work(self):
        archive = _archive("K-CONTROL")
        failure = runner.ShadowFailure("SHADOW_TIMEOUT", 1, None, "fixture timeout")
        malformed = (
            ("text", "broken"),
            ("wrong_known_record", evidence.DecisionTimings()),
            ("missing_class", _corrupt(failure, failure_class=None)),
            ("missing_detail", _corrupt(failure, detail=None)),
        )
        for location in ("trace", "final"):
            for label, value in malformed:
                if location == "trace":
                    shadow = _corrupt(archive.result.traces[1].shadow, failure=value)
                    changed = _replace_trace(archive, 1, shadow=shadow)
                else:
                    shadow = _corrupt(archive.result.shadow, failure=value)
                    changed = _corrupt(
                        archive, result=_corrupt(archive.result, shadow=shadow))
                with self.subTest(location=location, failure=label), patch.object(
                        oracles, "collect_oracle_diagnostics") as collector:
                    with self.assertRaises(audit.E1AuditError):
                        self.checked(changed)
                    collector.assert_not_called()


class PublicStreamAndCostTests(AuditCase):
    def test_complete_stream_pass_and_exact_existing_record_retained(self):
        archive = _archive()
        effects = tuple(t.public_effect for t in archive.result.traces)
        expected = evidence.validate_public_effect_stream(effects, complete=True)
        result = self.checked(archive)
        self.assertEqual(result.public_effect_audit, expected)
        self.assertEqual(result.audit_status, "PASS", result)

    def test_all_three_variants_accept_complete_manual_stream(self):
        for variant in e1.VARIANTS:
            with self.subTest(variant=variant):
                result = self.checked(_archive(variant))
                self.assertEqual(result.audit_status, "PASS", result)
                self.assertEqual(result.variant, variant)

    def test_missing_effect_is_incomplete_and_no_oracle_work(self):
        result = self.checked(_replace_trace(_archive(), 1, public_effect=None))
        self.assertEqual(result.audit_status, "INCOMPLETE", result)
        self.assertEqual(result.oracle_calls, ())

    def test_misordered_input_fails_without_oracle_work(self):
        result = self.assertFails(_replace_effect(_archive(), 1, input_index=7))
        self.assertEqual(result.oracle_calls, ())

    def test_postterminal_input_fails(self):
        archive = _archive()
        effect = archive.result.traces[0].public_effect
        archive = _replace_effect(
            archive, 0, status_after=GameStatus.LOST,
            after_observation=replace(effect.after_observation, status=GameStatus.LOST))
        self.assertFails(archive)

    def test_effect_cursor_corruption_fails(self):
        self.assertFails(_replace_effect(_archive(), 1, cursor_after=(4, 0)))

    def test_trace_cursor_corruption_fails(self):
        self.assertFails(_replace_trace(_archive(), 1, cursor_before=(4, 0)))

    def test_observation_chain_corruption_fails(self):
        self.assertFails(_replace_effect(
            _archive(), 1, before_observation=((0, H, H, H, H),)))

    def test_nonplaying_preinput_fails(self):
        self.assertFails(_replace_effect(_archive(), 1, status_before=GameStatus.WON))

    def test_final_status_corruption_fails(self):
        archive = _archive()
        self.assertFails(_corrupt(archive, result=_corrupt(archive.result, status=GameStatus.WON)))

    def test_effect_delta_corruption_fails(self):
        self.assertFails(_replace_effect(_archive(), 0, safe_cells_opened_delta=99))

    def test_trace_move_binding_corruption_fails(self):
        self.assertFails(_replace_trace(_archive(), 1, move=SimpleMove(Action.OPEN, 4, 0)))

    def test_model_c_costs_and_exact_total(self):
        archive = _archive()
        result = self.checked(archive)
        table = physical.load_timing_table()
        expected = tuple(table[abs(t.move.x-t.cursor_before[0])][
            abs(t.move.y-t.cursor_before[1])] for t in archive.result.traces)
        self.assertEqual(tuple(row.expected_us for row in result.cost_audits), expected)
        self.assertEqual(result.expected_total_us, sum(expected))
        self.assertEqual(result.recorded_total_us, archive.result.total_modeled_us)
        self.assertTrue(all(row.status == "PASS" for row in result.cost_audits))

    def test_wrong_trace_cost_rejected(self):
        archive = _archive()
        self.assertFails(_replace_trace(
            archive, 1, modeled_action_us=archive.result.traces[1].modeled_action_us+1))

    def test_wrong_effect_cost_rejected(self):
        archive = _archive()
        self.assertFails(_replace_effect(
            archive, 1, modeled_action_us=archive.result.traces[1].modeled_action_us+1))

    def test_mutually_consistent_wrong_cost_still_fails_table_check(self):
        archive = _archive()
        wrong = archive.result.traces[1].modeled_action_us + 1
        archive = _replace_trace(archive, 1, modeled_action_us=wrong)
        archive = _replace_effect(archive, 1, modeled_action_us=wrong)
        result = self.assertFails(archive)
        self.assertTrue(any(row.status == "FAIL" for row in result.cost_audits))

    def test_authenticated_existing_table_loader_used(self):
        with patch.object(physical, "load_timing_table", wraps=physical.load_timing_table) as loader:
            self.checked()
        self.assertGreaterEqual(loader.call_count, 1)

    def test_empty_complete_marked_archives_are_incomplete_without_cost_failure(self):
        for variant in e1.VARIANTS:
            archive = _archive(variant)
            if variant == "CONTROL":
                result = _corrupt(archive.result,
                    control=_corrupt(archive.result.control, traces=()),
                    effects=(), timings=())
            elif variant == "K-P0":
                result = _corrupt(archive.result, traces=(), final_M=frozenset())
            else:
                result = _corrupt(archive.result, traces=())
            with self.subTest(variant=variant):
                checked = self.checked(_corrupt(archive, result=result))
                self.assertEqual(checked.audit_status, "INCOMPLETE", checked)
                self.assertEqual(checked.public_effect_audit.status, "INCOMPLETE")
                self.assertEqual(checked.oracle_calls, ())
                self.assertEqual(checked.cost_audits, ())
                self.assertEqual(checked.recorded_total_us, 0)
                self.assertFalse(checked.discrepancies)

    def test_missing_control_effect_inside_tuple_is_incomplete(self):
        archive = _archive("CONTROL")
        effects = (archive.result.effects[0], None, archive.result.effects[2])
        result = self.checked(_corrupt(
            archive, result=_corrupt(archive.result, effects=effects)))
        self.assertEqual(result.audit_status, "INCOMPLETE", result)
        self.assertEqual(result.oracle_calls, ())

    def test_missing_control_timing_inside_tuple_is_incomplete(self):
        archive = _archive("CONTROL")
        timings = (archive.result.timings[0], None, archive.result.timings[2])
        result = self.checked(_corrupt(
            archive, result=_corrupt(archive.result, timings=timings)))
        self.assertEqual(result.audit_status, "INCOMPLETE", result)
        self.assertIsNone(result.timings[1].timings)


class V1AndReplayTests(AuditCase):
    def test_control_v1_validation_retained(self):
        result = self.checked(_archive("CONTROL"))
        self.assertEqual(len(result.v1_audits), 3)
        self.assertTrue(all(item.status == "PASS" for item in result.v1_audits))

    def test_k_control_v1_validation_and_shadow_replay_retained(self):
        result = self.checked(_archive("K-CONTROL"))
        self.assertEqual(result.audit_status, "PASS", result)
        self.assertEqual(len(result.v1_audits), 3)
        self.assertTrue(result.replay_audits)
        self.assertTrue(all(item.decision_status == "PASS"
                            for item in result.replay_audits if item.input_index))

    def test_invalid_archived_v1_action_fails(self):
        archive = _archive("CONTROL")
        decision = archive.result.traces[1].decision
        changed = replace(decision, move=SimpleMove(Action.OPEN, 0, 0))
        self.assertFails(_replace_trace(archive, 1, decision=changed))

    def test_missing_noninitial_v1_decision_incomplete(self):
        result = self.checked(_replace_trace(_archive("CONTROL"), 1, decision=None))
        self.assertEqual(result.audit_status, "INCOMPLETE", result)
        self.assertTrue(result.incomplete_reasons)

    def test_missing_k_control_v1_context_preserves_independent_k_replay(self):
        archive = _archive("K-CONTROL")
        shadow = archive.result.traces[2].shadow
        result = self.checked(_replace_trace(archive, 2, decision=None))
        self.assertEqual(result.audit_status, "INCOMPLETE", result)
        self.assertEqual(result.v1_audits[2].status, "INCOMPLETE")
        self.assertEqual(result.replay_audits[2].decision_status, "PASS")
        self.assertEqual(result.replay_audits[2].shadow, shadow)
        self.assertFalse(result.discrepancies)
        self.assertTrue(any(item.input_index == 2 and item.phase == "D"
                            and item.status == "PASS" for item in result.oracle_b_audits))

    def test_k_p0_decision_and_policy_replay_equal(self):
        result = self.checked()
        self.assertTrue(result.replay_audits)
        self.assertTrue(all(item.decision_status == item.policy_status == "PASS"
                            for item in result.replay_audits if item.input_index))

    def test_mismatched_k_decision_fails(self):
        archive = _archive()
        selection = archive.result.traces[1].selection
        changed = replace(selection.evidence, guess_target=(4, 0))
        self.assertFails(_replace_trace(archive, 1, selection=replace(selection, evidence=changed)))

    def test_mismatched_policy_plan_fails(self):
        archive = _archive(case_id="S-LIFECYCLE")
        selection = archive.result.traces[1].selection
        changed = replace(selection, plan=replace(selection.plan, latency_us=selection.plan.latency_us+1))
        self.assertFails(_replace_trace(archive, 1, selection=changed))

    def test_mislabeled_category_fails(self):
        self.assertFails(_replace_trace(_archive(), 1, category="DIRECT_SAFE_OPEN"))

    def test_initial_k_input_cannot_carry_inference(self):
        archive = _archive()
        self.assertFails(_replace_trace(archive, 0, selection=archive.result.traces[1].selection))

    def test_retained_m_lifecycle_cannot_be_repaired(self):
        self.assertFails(_replace_trace(_archive(), 1, M_before=frozenset({(4, 0)})))

    def test_final_m_extension_fails(self):
        archive = _archive()
        result = _corrupt(archive.result, final_M=archive.result.final_M | {(4, 0)})
        self.assertFails(_corrupt(archive, result=result))

    def test_shadow_timeout_preserved_without_fabricated_replay(self):
        archive = _archive("K-CONTROL", prefixes=(((1, H, H, H, H),),))
        failure = runner.ShadowFailure("SHADOW_TIMEOUT", 1, None, "bounded fixture timeout")
        shadow = runner.ShadowCheckpoint(
            enabled=False, failure=failure, last_valid_M=frozenset())
        archive = _replace_trace(archive, 1, shadow=shadow, preinput_M=frozenset())
        archive = _corrupt(archive, result=_corrupt(archive.result, shadow=shadow))
        result = self.checked(archive)
        self.assertEqual(result.audit_status, "INCOMPLETE", result)
        self.assertFalse(any(item.decision_status == "PASS" for item in result.replay_audits))
        self.assertEqual(result.acquisition_audits, ())
        self.assertTrue(any("SHADOW_TIMEOUT" in reason for reason in result.incomplete_reasons))

    def test_semantic_shadow_failure_is_failure(self):
        archive = _archive("K-CONTROL", prefixes=(((1, H, H, H, H),),))
        failure = runner.ShadowFailure("SHADOW_SOUNDNESS_VIOLATION", 1, None, "fixture defect", 1)
        shadow = runner.ShadowCheckpoint(enabled=False, failure=failure)
        archive = _replace_trace(archive, 1, shadow=shadow, preinput_M=frozenset())
        archive = _corrupt(archive, result=_corrupt(archive.result, shadow=shadow))
        self.assertFails(archive)

    def test_every_local_certificate_uses_accepted_verifier(self):
        archive = _archive(case_id="S-LIFECYCLE")
        certificates = archive.result.traces[1].selection.evidence.local.certificates
        with patch.object(harness, "audit_acquisition", wraps=harness.audit_acquisition) as verifier:
            result = self.checked(archive)
        self.assertEqual(tuple(item.certificate for item in result.acquisition_audits), certificates)
        self.assertEqual(verifier.call_count, len(certificates))
        self.assertTrue(all(item.status == "PASS" for item in result.acquisition_audits))

    def test_missing_acquisition_certificate_fails(self):
        archive = _archive()
        selection = archive.result.traces[1].selection
        decision = selection.evidence
        changed = replace(decision, local=replace(decision.local, certificates=()))
        self.assertFails(_replace_trace(archive, 1, selection=replace(selection, evidence=changed)))

    def test_altered_acquisition_certificate_fails(self):
        archive = _archive()
        selection = archive.result.traces[1].selection
        decision = selection.evidence
        certificate = replace(decision.local.certificates[0], target=(4, 0))
        changed = replace(decision, local=replace(decision.local, certificates=(certificate,)))
        self.assertFails(_replace_trace(archive, 1, selection=replace(selection, evidence=changed)))

    def test_external_v1_flag_provenance_retained_and_publicly_verified(self):
        archive = _archive("K-CONTROL")
        flag = archive.result.traces[1].external_flag
        with patch.object(evidence, "verify_v1_flag_provenance",
                          wraps=evidence.verify_v1_flag_provenance) as verifier:
            result = self.checked(archive)
        self.assertEqual(result.audit_status, "PASS", result)
        record = result.v1_audits[1]
        self.assertEqual(record.external_flag, flag)
        self.assertEqual(record.external_verification.status, "PASS")
        self.assertEqual(result.replay_audits[2].external_antecedents, (flag,))
        self.assertGreaterEqual(verifier.call_count, 1)
        self.assertFalse(flag.enters_M)

    def test_missing_executed_v1_flag_provenance_incomplete(self):
        archive = _archive("K-CONTROL", prefixes=(((1, H, H, H, H),),))
        result = self.checked(_replace_trace(archive, 1, external_flag=None))
        self.assertEqual(result.audit_status, "INCOMPLETE", result)
        self.assertTrue(any("FLAG provenance" in text for text in result.incomplete_reasons))

    def test_altered_executed_v1_flag_provenance_fails(self):
        archive = _archive("K-CONTROL")
        flag = archive.result.traces[1].external_flag
        changed = replace(flag, num_mines=3)
        self.assertFails(_replace_trace(archive, 1, external_flag=changed))

    def test_external_v1_flag_antecedents_are_chronological(self):
        archive = _archive("K-CONTROL")
        self.assertTrue(archive.result.traces[2].external_flag_antecedents)
        self.assertFails(_replace_trace(archive, 2, external_flag_antecedents=()))

    def test_k_p0_cannot_invent_bare_physical_flag_support(self):
        archive = _archive()
        trace = archive.result.traces[1]
        decision = trace.selection.evidence
        changed = replace(decision, observation=((1, F, H, H, H),))
        self.assertFails(_replace_trace(
            archive, 1, selection=replace(trace.selection, evidence=changed)))


class OracleAndP3Tests(AuditCase):
    def test_oracle_b_phase_d_and_e_retained(self):
        result = self.checked()
        self.assertEqual(len(result.oracle_b_audits), 2)
        self.assertTrue(all(item.status == "PASS" for item in result.oracle_b_audits))
        self.assertIn("SHARED-KERNEL REPRESENTATION EVIDENCE", repr(result.oracle_b_audits))
        self.assertIn("simple_probability.calculate_probabilities", repr(result.oracle_b_audits))
        self.assertIn("AUDITOR", repr(result.oracle_b_audits))

    def test_oracle_a_bounded_equality_retained(self):
        result = self.checked()
        self.assertEqual(len(result.oracle_a_audits), 1)
        self.assertIn("EVALUATED", repr(result.oracle_a_audits))
        self.assertIn("OracleAResult", repr(result.oracle_a_audits))
        self.assertEqual(result.audit_status, "PASS", result)

    def test_large_public_observation_not_evaluated_is_not_failure(self):
        result = self.checked(_archive(case_id="X-0"))
        self.assertEqual(result.audit_status, "PASS", result)
        self.assertIn("NOT_EVALUATED", repr(result.oracle_a_audits))
        self.assertIn("16", repr(result.oracle_a_audits))
        self.assertTrue(any(call.status == "NOT_EVALUATED" and call.variable_count > 16
                            for call in result.oracle_calls))

    def test_oracle_b_mismatch_fails(self):
        original = oracles.materialized_exact_reference
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            return replace(result, total_worlds=result.total_worlds+1)
        with patch.object(oracles, "materialized_exact_reference", side_effect=changed):
            self.assertFails(_archive())

    def test_oracle_a_mismatch_fails(self):
        original = oracles.enumerate_public_worlds
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            return replace(result, total_worlds=result.total_worlds+1)
        with patch.object(oracles, "enumerate_public_worlds", side_effect=changed):
            self.assertFails(_archive())

    def exact_nested_type_fault(self, oracle_name, *, coordinate=False):
        archive = _archive()
        original = getattr(oracles, oracle_name)
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            first, *remaining = result.mine_worlds
            cell, count = first
            if coordinate:
                self.assertEqual(cell[1], 0)
                cell = (cell[0], False)
            else:
                self.assertEqual(count, 1)
                count = True
            return replace(result, mine_worlds=((cell, count), *remaining))
        with patch.object(oracles, oracle_name, side_effect=changed):
            checked = self.assertFails(archive)
        record = (checked.oracle_a_audits[0] if oracle_name == "enumerate_public_worlds"
                  else next(item for item in checked.oracle_b_audits if item.phase == "D"))
        self.assertEqual(record.status, "FAIL")
        # Diagnostics also detect the returned output digest; this assertion
        # independently requires a semantic/type diagnosis for the nested bool.
        self.assertTrue(record.discrepancies)
        return record

    def test_oracle_a_nested_bool_count_is_semantic_failure(self):
        self.exact_nested_type_fault("enumerate_public_worlds")

    def test_oracle_a_nested_bool_coordinate_is_semantic_failure(self):
        self.exact_nested_type_fault("enumerate_public_worlds", coordinate=True)

    def test_oracle_b_nested_bool_count_is_semantic_failure(self):
        self.exact_nested_type_fault("materialized_exact_reference")

    def test_oracle_b_nested_bool_coordinate_is_semantic_failure(self):
        self.exact_nested_type_fault("materialized_exact_reference", coordinate=True)

    def test_diagnostic_order_positive_duration_and_no_evaluator(self):
        result = self.checked()
        self.assertTrue(result.oracle_calls)
        self.assertEqual(tuple(item.sequence for item in result.oracle_calls),
                         tuple(range(len(result.oracle_calls))))
        for item in result.oracle_calls:
            self.assertIn(item.oracle, ("A", "B"))
            self.assertEqual(len(item.input_digest), 64)
            self.assertGreater(item.duration_ns, 0)
            if item.status == "EVALUATED":
                self.assertEqual(len(item.output_digest), 64)
        self.assertNotIn("EVALUATOR", repr(result.oracle_calls))

    def test_oracle_calls_are_scoped_to_current_audit(self):
        first = self.checked()
        second = self.checked()
        self.assertEqual(len(first.oracle_calls), len(second.oracle_calls))
        self.assertEqual(first.oracle_calls[0].sequence, 0)
        self.assertEqual(second.oracle_calls[0].sequence, 0)

    def diagnostic_fault(self, **changes):
        archive = _archive()
        original = oracles.measure_oracle_call
        @contextmanager
        def changed(*args, **kwargs):
            with original(*args, **kwargs) as measurement:
                yield measurement
            for collector in oracles._oracle_diagnostic_collectors:
                collector[-1] = _corrupt(collector[-1], **changes)
        with patch.object(oracles, "measure_oracle_call", changed):
            return self.assertFails(archive)

    def test_zero_evaluated_oracle_duration_fails(self):
        result = self.diagnostic_fault(duration_ns=0)
        self.assertTrue(any("duration" in text for text in result.discrepancies))

    def test_zero_actual_not_evaluated_duration_fails(self):
        archive = _archive(case_id="X-0")
        original = oracles.measure_oracle_call
        @contextmanager
        def changed(*args, **kwargs):
            try:
                with original(*args, **kwargs) as measurement:
                    yield measurement
            finally:
                for collector in oracles._oracle_diagnostic_collectors:
                    if collector and collector[-1].status == "NOT_EVALUATED":
                        collector[-1] = _corrupt(collector[-1], duration_ns=0)
        with patch.object(oracles, "measure_oracle_call", changed):
            result = self.assertFails(archive)
        self.assertTrue(any(item.status == "NOT_EVALUATED" and item.duration_ns == 0
                            for item in result.oracle_calls))
        self.assertTrue(any("duration" in text for text in result.discrepancies))

    def test_over_envelope_exact_ancestor_emits_no_synthetic_current_a_call(self):
        # Public corner 1-of-3 plus total17 forces the other16 cells to G1.
        # A valid earlier exact proof had19 variables. Four retained proofs
        # leave15 current variables, but independent A still cannot certify
        # the over-envelope ancestor and must emit no invented leaf call.
        observation = ((1,) + (H,) * 9, (H,) * 10)
        decision = capability.KLocalSession(10, 2, 17).analyze_decision(
            observation, status=GameStatus.PLAYING)
        proofs = decision.exact_certificates[:4]
        logical = frozenset(item.target for item in proofs)
        reference = oracles.materialized_exact_reference(
            observation, 17, status=GameStatus.PLAYING,
            logical_mines=logical, proofs=proofs)
        findings = audit._Findings()
        with oracles.collect_oracle_diagnostics() as calls:
            record, span = audit._oracle_a(
                1, observation, 17, logical, proofs, decision.phase_d,
                reference, calls, findings)
        self.assertEqual(record.status, "NOT_EVALUATED", record)
        self.assertEqual(record.coverage.status, "ORACLE_A_NOT_EVALUATED")
        self.assertEqual(record.coverage.variable_count, 19)
        self.assertEqual(record.checkpoint_variable_count, 15)
        self.assertEqual(record.coverage.envelope, 16)
        self.assertEqual(calls, [])
        self.assertEqual((span.start, span.stop, span.status), (0, 0, "PASS"))
        self.assertEqual(findings.failures, [])
        self.assertEqual(findings.missing, [])

    def test_diagnostic_input_digest_misbinding_fails(self):
        result = self.diagnostic_fault(input_digest="a" * 64)
        self.assertTrue(any("binding" in text for text in result.discrepancies))

    def test_diagnostic_output_digest_misbinding_fails(self):
        result = self.diagnostic_fault(output_digest="b" * 64)
        self.assertTrue(any("output" in text for text in result.discrepancies))

    def test_diagnostic_variable_count_misbinding_fails(self):
        result = self.diagnostic_fault(variable_count=999)
        self.assertTrue(any("variable" in text for text in result.discrepancies))

    def test_diagnostic_order_corruption_fails(self):
        result = self.diagnostic_fault(sequence=99)
        self.assertTrue(any("sequence" in text for text in result.discrepancies))

    def test_oracle_a_cannot_claim_non_evaluation_within_envelope(self):
        archive = _archive()
        with patch.object(oracles, "enumerate_public_worlds",
                          side_effect=oracles.OracleANotEvaluated(3)):
            result = self.assertFails(archive)
        self.assertTrue(any("envelope" in text or "diagnostic" in text
                            for text in result.discrepancies))

    def test_control_one_run_p3_checkpoint_retained(self):
        result = self.checked(_archive("CONTROL"))
        self.assertIsInstance(result.p3_audit, harness.GuessCheckpointAudit)
        self.assertEqual(result.p3_status, "COMPLETE")
        self.assertEqual(len(result.p3_audit.checkpoints), 1)

    def test_k_p0_one_run_p3_checkpoint_retained(self):
        result = self.checked()
        self.assertIsInstance(result.p3_audit, harness.GuessCheckpointAudit)
        self.assertEqual(result.p3_status, "COMPLETE")
        self.assertEqual(len(result.p3_audit.checkpoints), 1)
        checkpoint = result.p3_audit.checkpoints[0]
        self.assertEqual(checkpoint.target, (2, 0))

    def test_k_control_p3_not_applicable(self):
        result = self.checked(_archive("K-CONTROL"))
        self.assertEqual(result.p3_status, "NOT_APPLICABLE")
        self.assertIsNone(result.p3_audit)

    def test_no_cross_run_guess_comparison(self):
        with patch.object(harness, "compare_guess_checkpoints",
                          side_effect=AssertionError("cross-run comparison prohibited")):
            result = self.checked()
        self.assertEqual(result.audit_status, "PASS")


class SyntheticPublicCheckpointTests(unittest.TestCase):
    """Private semantic seam only: these literal dimensions are not E1 cases."""

    def components(self, observation, num_mines, *, variant="K-P0", later=()):
        case = SimpleNamespace(
            case_id="NON_E1_MANUAL_PUBLIC_FIXTURE",
            width=len(observation[0]), height=len(observation),
            num_mines=num_mines, first_click=(0, 0))
        result = _public_result(
            variant, case.width, case.height, num_mines, (observation,) + later)
        return audit._audit_run(result, variant, case), result, case

    def exact_changed(self):
        # The corner's 1-of-3 constraint plus total seven forces all six
        # nonadjacent cells to G1. Only public clue/total premises are supplied.
        return self.components(((1, H, H, H, H), (H, H, H, H, H)), 7)

    def test_every_exact_certificate_audited_in_retained_order(self):
        components, result, _ = self.exact_changed()
        certificates = result.traces[1].selection.evidence.exact_certificates
        self.assertEqual(len(certificates), 6)
        self.assertEqual(components["audit_status"], "PASS", components)
        audits = components["acquisition_audits"]
        self.assertEqual(tuple(item.certificate for item in audits), certificates)
        self.assertTrue(all(item.status == "PASS" for item in audits))
        for index, item in enumerate(audits):
            self.assertEqual(item.prior_certificates, certificates[:index])

    def test_phase_e_changed_auditor_reenumeration_uses_audited_g1(self):
        components, result, _ = self.exact_changed()
        decision = result.traces[1].selection.evidence
        self.assertEqual(decision.phase_e_status, "REACHED_CHANGED")
        phases = components["oracle_b_audits"]
        self.assertEqual(tuple(item.phase for item in phases), ("D", "E"))
        self.assertEqual(phases[0].logical_mines, decision.local.after.M)
        self.assertEqual(phases[1].logical_mines, decision.after.M)
        self.assertEqual(phases[1].proofs, decision.exact_certificates)
        self.assertEqual(phases[1].result.G1, frozenset())
        self.assertIn("AUDITOR re-enumeration only", phases[1].interpretation)

    def test_exact_g0_preserved_through_nonempty_g1_restriction(self):
        components, result, _ = self.components(((1, 1, 2, H), (H, H, H, H)), 3)
        self.assertEqual(components["audit_status"], "PASS", components)
        decision = result.traces[1].selection.evidence
        self.assertTrue(decision.phase_d.G0)
        self.assertTrue(decision.phase_d.G1)
        self.assertEqual(decision.phase_d.G0, decision.phase_e.G0)
        self.assertFalse(decision.phase_e.G1)

    def test_missing_exact_certificate_fails_and_does_not_upgrade_phase_e(self):
        _, result, case = self.exact_changed()
        trace = result.traces[1]
        decision = trace.selection.evidence
        changed = replace(decision, exact_certificates=decision.exact_certificates[:-1])
        trace = replace(trace, selection=replace(trace.selection, evidence=changed))
        result = replace(result, traces=(result.traces[0], trace))
        components = audit._audit_run(result, "K-P0", case)
        self.assertEqual(components["audit_status"], "FAIL")
        phase_d = next(item for item in components["oracle_b_audits"] if item.phase == "D")
        self.assertEqual(phase_d.status, "PASS")
        self.assertIsNotNone(phase_d.result)
        self.assertEqual(components["oracle_a_audits"][0].status, "PASS")
        self.assertIsNotNone(components["oracle_a_audits"][0].result)
        self.assertFalse(any(item.phase == "E" and item.status == "PASS"
                             for item in components["oracle_b_audits"]))

    def test_failed_acquisition_records_and_spans_do_not_stop_later_certificates(self):
        observation = ((1, H, H, H, H), (H, H, H, H, H))
        case = SimpleNamespace(case_id="NON_E1_FAILED_ACQUISITION_FIXTURE",
                               width=5, height=2, num_mines=7, first_click=(0, 0))
        result = _public_result("K-P0", 5, 2, 7, (observation,))
        original = harness.audit_acquisition
        def failed(*args, **kwargs):
            record = original(*args, **kwargs)
            return replace(record, status="FAIL", detail="Injected public provenance failure")
        with patch.object(harness, "audit_acquisition", side_effect=failed) as verifier:
            components = audit._audit_run(result, "K-P0", case)
        certificates = result.traces[1].selection.evidence.exact_certificates
        self.assertEqual(components["audit_status"], "FAIL")
        self.assertEqual(verifier.call_count, len(certificates))
        self.assertEqual(tuple(item.certificate for item in components["acquisition_audits"]),
                         certificates)
        self.assertTrue(all(item.status == "FAIL" for item in components["acquisition_audits"]))
        spans = tuple(item for item in components["oracle_spans"] if item.operation == "ACQUISITION")
        self.assertEqual(len(spans), len(certificates))

    def test_malformed_external_provenance_retains_failed_acquisition_and_span(self):
        archive = _archive("K-CONTROL")
        flag = archive.result.traces[1].external_flag
        bad_evidence = _corrupt(flag.decision.evidence, constraints=())
        malformed = _corrupt(flag, decision=_corrupt(flag.decision, evidence=bad_evidence))
        certificate = archive.result.traces[1].shadow.decision.local.certificates[0]
        findings = audit._Findings()
        with oracles.collect_oracle_diagnostics() as calls:
            record, span, passed = audit._audit_certificate(
                certificate, 2, (), (malformed,), calls, findings)
        self.assertFalse(passed)
        self.assertEqual(record.status, "FAIL")
        self.assertEqual(record.certificate, certificate)
        self.assertEqual(record.boundary, 2)
        self.assertEqual(span.operation, "ACQUISITION")
        self.assertEqual((span.start, span.stop), (0, len(calls)))
        self.assertTrue(findings.failures)

    def test_phase_e_cannot_acquire_new_mine(self):
        _, result, case = self.exact_changed()
        trace = result.traces[1]
        decision = trace.selection.evidence
        phase_e = replace(decision.phase_e, G1=frozenset({(1, 0)}))
        changed = replace(decision, phase_e=phase_e)
        trace = replace(trace, selection=replace(trace.selection, evidence=changed))
        result = replace(result, traces=(result.traces[0], trace))
        components = audit._audit_run(result, "K-P0", case)
        self.assertEqual(components["audit_status"], "FAIL")
        self.assertTrue(any("Phase E" in text for text in components["discrepancies"]))

    def test_phase_e_changed_label_cannot_be_rewritten(self):
        _, result, case = self.exact_changed()
        trace = result.traces[1]
        decision = replace(trace.selection.evidence, phase_e_status="REACHED_NO_CHANGE")
        trace = replace(trace, selection=replace(trace.selection, evidence=decision))
        result = replace(result, traces=(result.traces[0], trace))
        components = audit._audit_run(result, "K-P0", case)
        self.assertEqual(components["audit_status"], "FAIL")

    def test_raw_setup_flag_and_actual_later_chord_are_distinct(self):
        before = ((1, H, 1, H), (1, 1, 1, H))
        flagged = ((1, F, 1, H), (1, 1, 1, H))
        components, result, _ = self.components(before, 1, later=(flagged,))
        self.assertEqual(components["audit_status"], "PASS", components)
        setup, chord = components["mechanism_observations"][1:]
        self.assertEqual(setup.action, Action.FLAG)
        self.assertEqual(setup.kind, "SETUP_CHORD_FLAG")
        self.assertEqual(setup.selected_category, "SETUP_CHORD")
        self.assertEqual(setup.setup_cells, frozenset({(1, 0)}))
        self.assertEqual(setup.safe_cells_opened_delta, 0)
        self.assertEqual(setup.planned_terminal_reveal_action.action, Action.CHORD)
        self.assertEqual(chord.action, Action.CHORD)
        self.assertEqual(chord.kind, "CHORD_AFTER_PRIOR_SETUP")
        self.assertEqual(chord.prior_setup_input_indices, (1,))
        self.assertIn((1, 0), chord.relevant_physical_flags)
        self.assertGreater(chord.safe_cells_opened_delta, 0)
        self.assertEqual(chord.safe_cells_opened_delta,
                         result.traces[-1].public_effect.safe_cells_opened_delta)

    def test_abandoned_setup_has_no_realized_benefit_credit(self):
        components, _, _ = self.components(((1, H, 1, H), (1, 1, 1, H)), 1)
        setup = components["mechanism_observations"][-1]
        self.assertEqual(setup.kind, "SETUP_CHORD_FLAG")
        self.assertEqual(setup.action, Action.FLAG)
        self.assertEqual(setup.safe_cells_opened_delta, 0)
        self.assertFalse(any(item.action is Action.CHORD
                             for item in components["mechanism_observations"]))
        self.assertFalse({field.name for field in fields(setup)} & {
            "saving", "realized_benefit", "productive_chord", "qualification"})

    def test_direct_chord_has_no_invented_prior_setup(self):
        # Inspect the retained mechanism helper in isolation: a current direct
        # CHORD can exist without any earlier setup in the supplied substream.
        before = ((1, H, 1, H), (1, 1, 1, H))
        flagged = ((1, F, 1, H), (1, 1, 1, H))
        _, result, _ = self.components(before, 1, later=(flagged,))
        trace = replace(result.traces[-1], input_index=0)
        effect = replace(trace.public_effect, input_index=0)
        trace = replace(trace, public_effect=effect)
        result = replace(result, traces=(trace,))
        findings = audit._Findings()
        observations = audit._mechanisms(result, (effect,), findings)
        self.assertEqual(observations[0].kind, "DIRECT_CHORD")
        self.assertEqual(observations[0].prior_setup_input_indices, ())


class TimingAndPurityTests(AuditCase):
    def test_exact_archived_timing_records_retained(self):
        archive = _archive()
        result = self.checked(archive)
        self.assertEqual(tuple(item.timings for item in result.timings),
                         tuple(trace.timings for trace in archive.result.traces))

    def test_missing_required_k_analysis_span_incomplete(self):
        archive = _archive()
        span = replace(archive.result.traces[1].timings, k_analysis_planning_ns=None)
        result = self.checked(_replace_trace(archive, 1, timings=span))
        self.assertEqual(result.audit_status, "INCOMPLETE", result)

    def test_missing_required_k_validation_span_incomplete(self):
        archive = _archive()
        span = replace(archive.result.traces[0].timings, k_execution_validation_ns=None)
        result = self.checked(_replace_trace(archive, 0, timings=span))
        self.assertEqual(result.audit_status, "INCOMPLETE", result)

    def test_missing_required_evidence_span_incomplete(self):
        archive = _archive()
        span = replace(archive.result.traces[0].timings, evidence_ns=None)
        result = self.checked(_replace_trace(archive, 0, timings=span))
        self.assertEqual(result.audit_status, "INCOMPLETE", result)

    def test_initial_na_and_control_unmeasured_validation_explicit(self):
        result = self.checked(_archive("CONTROL"))
        self.assertIsNone(result.timings[0].timings.v1_plan_position_ns)
        self.assertIsNone(result.timings[0].timings.v1_execution_validation_ns)
        self.assertIn("UNMEASURED", repr(result.timings))

    def test_timing_context_cannot_claim_resource_comparability(self):
        result = self.checked()
        self.assertEqual(result.timing_context,
                         "ARCHIVED_RUNNER_SPANS; supervisor/tracer context is not inferred here")
        self.assertNotIn("RESOURCE_PASS", repr(result))

    def test_purity_blocks_materialization_runners_evaluator_and_persistence(self):
        archive = _archive()
        before_plan, before_archive = repr(_plan()), repr(archive)
        from experiments import program_k_evaluator as evaluator
        import core_engine
        with ExitStack() as stack:
            blocked = []
            for module, names in (
                (execution, ("_materialize_case", "execute_scheduled_entry")),
                (runner, ("run_control_capture", "run_k_control", "run_k_p0")),
                (e1, ("_seal_fixed_cases", "generate_board")),
                (core_engine, ("MinesweeperEngine",)),
                (evaluator, ("evaluate_falsification",)),
                (harness, ("persist_qualification", "execute_e0", "evaluate_execution_archives")),
                (Path, ("write_bytes", "write_text", "mkdir")),
            ):
                for name in names:
                    blocked.append(stack.enter_context(patch.object(
                        module, name, side_effect=AssertionError("forbidden audit side effect"))))
            result = self.checked(archive)
        for mock in blocked:
            mock.assert_not_called()
        self.assertEqual(result.audit_status, "PASS")
        self.assertEqual(repr(_plan()), before_plan)
        self.assertEqual(repr(archive), before_archive)

    def test_source_has_no_execution_persistence_or_qualification_calls(self):
        source = inspect.getsource(audit)
        tree = ast.parse(source)
        calls = {node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                 for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, (ast.Name, ast.Attribute))}
        forbidden = {
            "execute_scheduled_entry", "_materialize_case", "MinesweeperEngine",
            "run_control_capture", "run_k_control", "run_k_p0", "evaluate_falsification",
            "execute_e0", "check_frozen_p8", "persist_qualification", "mkdir",
            "write_text", "write_bytes", "compare_guess_checkpoints", "generate_board",
        }
        self.assertFalse(calls & forbidden, calls & forbidden)
        for verdict in ("E1_PASS", "E1_QUALIFIED", "RESEARCH_PASS"):
            self.assertNotIn(verdict, source)

    def test_audit_graph_is_immutable_detached_public_data(self):
        result = self.checked()
        seen = set()
        def visit(value):
            if id(value) in seen:
                return
            seen.add(id(value))
            self.assertNotIsInstance(value, (list, dict, set))
            self.assertFalse(callable(value))
            self.assertNotIn(type(value).__name__, (
                "MinesweeperEngine", "BoardSnapshot", "Thread", "Process", "Future"))
            if value is None or isinstance(value, (str, int, bool, Fraction, Enum)):
                return
            if isinstance(value, (tuple, frozenset)):
                for item in value:
                    visit(item)
                return
            self.assertTrue(is_dataclass(value), type(value))
            self.assertTrue(value.__dataclass_params__.frozen)
            for field in fields(value):
                self.assertNotIn(field.name, ("hidden_answer", "mine_layout", "mine_positions", "engine"))
                visit(getattr(value, field.name))
        visit(result)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            result.audit_status = "FAIL"

    def test_no_suite_or_productive_chord_verdict_in_result(self):
        result = self.checked()
        names = {field.name for field in fields(result)}
        self.assertFalse(names & {
            "qualification", "progression_allowed", "productive_chord_pass",
            "supplement", "research_verdict", "e1_verdict"})

    def test_control_mechanism_explicitly_not_applicable(self):
        for variant in ("CONTROL", "K-CONTROL"):
            result = self.checked(_archive(variant))
            self.assertEqual(result.mechanism_status, "NOT_APPLICABLE")
            self.assertEqual(result.mechanism_observations, ())

    def test_k_mechanism_actual_public_delta_and_cost_retained(self):
        archive = _archive()
        result = self.checked(archive)
        self.assertEqual(len(result.mechanism_observations), len(archive.result.traces))
        for item, trace in zip(result.mechanism_observations, archive.result.traces):
            self.assertEqual(item.safe_cells_opened_delta, trace.public_effect.safe_cells_opened_delta)
            self.assertEqual(item.modeled_action_us, trace.modeled_action_us)
        self.assertNotIn("realized_benefit", repr(result.mechanism_observations))


def _above16_public_flag():
    """Detached 19-variable public certificate; no Engine or hidden layout."""
    observation = ((1,) + (H,) * 9, (H,) * 10)
    decision = plan_position(observation, 17, (0, 0), physical.load_timing_table())
    flag = evidence.make_v1_flag_provenance(observation, decision, num_mines=17, boundary=1)
    return flag, decision


def _s_replan_public_prefixes():
    """Literal public observations only, independent of a board/Engine."""
    return (
        ((0, 1, H, H, H, H), (1, 2, H, H, H, H), (H, H, H, H, H, H), (H, H, H, H, H, H)),
        ((0, 1, H, H, H, H), (1, 2, H, H, H, H), (H, H, 2, H, H, H), (H, H, H, H, H, H)),
        ((0, 1, H, H, H, H), (1, 2, H, 4, H, H), (H, H, 2, H, H, H), (H, H, H, H, H, H)),
        ((0, 1, H, H, H, H), (1, 2, H, 4, H, 3), (H, H, 2, H, H, H), (H, H, H, H, H, H)),
    )


def _qualify_public_flags(flags, prerequisite=None):
    premises, findings = audit._PhysicalFlagPremises(prerequisite), audit._Findings()
    records, spans = [], []
    with oracles.collect_oracle_diagnostics() as calls:
        for flag in flags:
            record, span = premises.qualify(flag, calls=calls, findings=findings)
            records.append(record)
            if span is not None:
                spans.append(span)
            premises.admit(flag, record)
    return tuple(records), premises, tuple(calls), tuple(spans), findings


def _local_public_flag_chain(k):
    """Direct public all-mines clues, detached from any actual game.

    Before measurement the work guard is fixed: k frozen current-node checks,
    k one-target support views, exactly k*(k-1)/2 chronological prior references.
    The 30x16 public declaration has isolated HIDDEN variables, each bounded by
    public clues whose residual equals its complete unresolved neighborhood.
    """
    cells = tuple((x, y) for y in range(1, 16, 2) for x in range(1, 30, 2))[:k]
    unresolved = frozenset(cells)
    rows = tuple(tuple(H if (x, y) in unresolved else sum(
        abs(cx-x) <= 1 and abs(cy-y) <= 1 for cx, cy in unresolved)
        for x in range(30)) for y in range(16))
    records = []
    for index in range(k):
        constraints = evidence._public_constraints(rows)
        mines = frozenset(cell for c in constraints
                          if c.hidden_cells and c.remaining_mines == len(c.hidden_cells)
                          for cell in c.hidden_cells)
        safe = frozenset(cell for c in constraints if c.remaining_mines == 0 for cell in c.hidden_cells)
        target = min(mines, key=lambda c: (c[1], c[0]))
        move = evidence.MoveProjection(Action.FLAG, *target)
        projection = evidence.V1DecisionProjection(move, evidence.V1EvidenceProjection(
            DecisionKind.LOCAL_DETERMINISTIC, move, constraints,
            evidence.DeterministicProjection(evidence._set_cells(safe), evidence._set_cells(mines)),
            None), None)
        record = evidence.ExternalV1FlagProvenance(rows, k, projection, move,
                                                   index+1, index+1, tuple(records))
        records.append(record)
        rows = tuple(tuple(F if (x, y) == target else v for x, v in enumerate(row))
                     for y, row in enumerate(rows))
    return tuple(records)


class ReadinessPhysicalFlagTests(unittest.TestCase):
    def test_s_replan_17_variable_public_prefix_qualifies_without_scheduled_execution(self):
        case = SimpleNamespace(case_id="NON_E1_S_REPLAN_PUBLIC_PREFIX",
                               width=6, height=4, num_mines=5, first_click=(0, 0))
        with patch.object(execution, "execute_scheduled_entry",
                          side_effect=AssertionError("Actual E1 forbidden")) as scheduled:
            result = _public_result("K-CONTROL", 6, 4, 5, _s_replan_public_prefixes())
            components = audit._audit_run(result, "K-CONTROL", case,
                                           prerequisite=_plan().prerequisite)
        scheduled.assert_not_called()
        self.assertEqual(components["audit_status"], "PASS",
                         components["discrepancies"] + components["incomplete_reasons"])
        action = components["v1_audits"][4]
        self.assertEqual(action.external_flag.move, evidence.MoveProjection(Action.FLAG, 2, 1))
        self.assertEqual(action.external_qualification.public_hidden_variables, 17)
        self.assertEqual(action.external_verification.status, "NOT_EVALUATED")
        self.assertEqual(action.external_qualification.status, "PASS")
        self.assertEqual(action.external_qualification.shared_kernel_evidence,
                         "SHARED-KERNEL REPRESENTATION EVIDENCE")
        self.assertEqual(action.external_qualification.prerequisite, _plan().prerequisite)

    def test_above16_raw_non_evaluation_and_accepted_e0_shared_route(self):
        flag, _ = _above16_public_flag()
        raw = evidence.verify_v1_flag_provenance(flag)
        records, _, calls, spans, findings = _qualify_public_flags((flag,), _plan().prerequisite)
        q = records[0]
        self.assertEqual(raw.status, "NOT_EVALUATED")
        self.assertEqual(q.raw_verification, raw)
        self.assertEqual(q.node_verification, raw)
        self.assertEqual(q.status, "PASS", q.detail)
        self.assertEqual(q.shared_kernel_evidence, "SHARED-KERNEL REPRESENTATION EVIDENCE")
        self.assertEqual(q.prerequisite, _plan().prerequisite)
        self.assertFalse(q.independent_bounded_enumeration_ran)
        self.assertEqual(q.bounded_status, "NOT_EVALUATED")
        self.assertEqual(q.shared_kernel_input_digest,
                         oracles.oracle_b_input_digest(flag.observation, 17, frozenset()))
        self.assertEqual(tuple(c.oracle for c in calls), ("B",))
        self.assertEqual((spans[0].start, spans[0].stop, spans[0].status), (0, 1, "PASS"))
        self.assertFalse(findings.failures)

    def test_missing_or_wrong_e0_binding_cannot_pass(self):
        flag, _ = _above16_public_flag()
        for prerequisite, status in (
                (None, "INCOMPLETE"),
                (_corrupt(_plan().prerequisite, source_digest="f"*64), "FAIL")):
            with self.subTest(status=status):
                records, _, calls, _, _ = _qualify_public_flags((flag,), prerequisite)
                self.assertEqual(records[0].status, status)
                self.assertEqual(calls, ())

    def test_shared_count_marginal_partition_certainty_and_target_faults_fail(self):
        flag, _ = _above16_public_flag()
        original = oracles._materialized_exact
        mutations = (
            lambda r: replace(r, total_worlds=r.total_worlds+1),
            lambda r: replace(r, mine_worlds=((r.mine_worlds[0][0], 0),) + r.mine_worlds[1:]),
            lambda r: replace(r, unresolved_cells=tuple(reversed(r.unresolved_cells))),
            lambda r: replace(r, G1=frozenset()),
            lambda r: replace(r, shared_kernel_evidence="independent arithmetic"),
        )
        for mutation in mutations:
            def changed(*args, **kwargs):
                return mutation(original(*args, **kwargs))
            with self.subTest(mutation=mutations.index(mutation)), patch.object(
                    oracles, "_materialized_exact", side_effect=changed):
                records, _, _, _, _ = _qualify_public_flags((flag,), _plan().prerequisite)
                self.assertEqual(records[0].status, "FAIL")
        invalid = replace(flag, move=evidence.MoveProjection(Action.FLAG, 1, 0))
        records, _, _, _, _ = _qualify_public_flags((invalid,), _plan().prerequisite)
        self.assertEqual(records[0].status, "FAIL")

    def test_unavailable_shared_comparison_is_incomplete(self):
        flag, _ = _above16_public_flag()
        for behavior in (None, OSError("Required public comparison unavailable")):
            options = {"return_value": None} if behavior is None else {"side_effect": behavior}
            with self.subTest(behavior=type(behavior)), patch.object(
                    oracles, "_materialized_exact", **options):
                records, _, _, _, findings = _qualify_public_flags((flag,), _plan().prerequisite)
                self.assertEqual(records[0].status, "INCOMPLETE")
                self.assertFalse(findings.failures)

    def test_bounded_exact_after_shared_ancestor_runs_independent_enumeration(self):
        first, _ = _above16_public_flag()
        records, rows = [first], first.observation
        for index in range(2, 5):
            previous = records[-1]
            rows = tuple(tuple(F if (x, y) == (previous.move.x, previous.move.y) else v
                               for x, v in enumerate(row)) for y, row in enumerate(rows))
            decision = plan_position(rows, 17, (previous.move.x, previous.move.y),
                                     physical.load_timing_table())
            records.append(evidence.make_v1_flag_provenance(
                rows, decision, num_mines=17, boundary=index, prior_flags=tuple(records)))
        qualified, _, _, _, _ = _qualify_public_flags(tuple(records), _plan().prerequisite)
        self.assertTrue(all(q.status == "PASS" for q in qualified), tuple(q.detail for q in qualified))
        q = qualified[-1]
        self.assertEqual(q.public_hidden_variables, 16)
        self.assertTrue(q.independent_bounded_enumeration_ran)
        self.assertEqual(q.node_verification.status, "PASS")
        self.assertEqual(q.raw_verification.status, "NOT_EVALUATED")
        self.assertTrue(q.raw_verification.detail.startswith("FLAG antecedent:"))
        self.assertIsNone(q.shared_kernel_result)
        self.assertEqual(q.raw_verification, evidence.verify_v1_flag_provenance(records[-1]))

    def test_local_after_shared_ancestor_requires_current_independent_local_pass(self):
        rows = _s_replan_public_prefixes()[-1]
        decision = plan_position(rows, 5, (5, 1), physical.load_timing_table())
        first = evidence.make_v1_flag_provenance(rows, decision, num_mines=5, boundary=4)
        current = (
            (0, 1, 1, 3, H, H), (1, 2, F, 4, H, 3),
            (H, H, 2, H, H, H), (H, H, H, H, H, H))
        decision = plan_position(current, 5, (3, 0), physical.load_timing_table())
        self.assertEqual(decision.evidence.kind, DecisionKind.LOCAL_DETERMINISTIC)
        self.assertEqual(decision.move.action, Action.FLAG)
        second = evidence.make_v1_flag_provenance(
            current, decision, num_mines=5, boundary=7, prior_flags=(first,))
        qualified, _, calls, _, _ = _qualify_public_flags((first, second), _plan().prerequisite)
        q = qualified[-1]
        self.assertEqual(q.status, "PASS", q.detail)
        self.assertEqual(q.raw_verification, evidence.verify_v1_flag_provenance(second))
        self.assertEqual(q.raw_verification.status, "NOT_EVALUATED")
        self.assertEqual(q.node_verification.status, "PASS")
        self.assertEqual(q.node_verification.detail, "PUBLIC_V1_LOCAL_FLAG_EVIDENCE")
        self.assertFalse(q.independent_bounded_enumeration_ran)
        self.assertIsNone(q.shared_kernel_result)
        self.assertEqual(len(calls), 1)  # only the earlier >16 physical FLAG
        corrupted = replace(second, decision=replace(second.decision, evidence=replace(
            second.decision.evidence, constraints=())))
        qualified, _, _, _, _ = _qualify_public_flags((first, corrupted), _plan().prerequisite)
        self.assertEqual(qualified[-1].status, "FAIL")

    def test_bounded_failure_never_uses_shared_fallback_or_claims_unrun_enumeration(self):
        rows = ((1, H, H, H, H), (H, H, H, H, H))
        decision = plan_position(rows, 7, (0, 0), physical.load_timing_table())
        flag = evidence.make_v1_flag_provenance(rows, decision, num_mines=7, boundary=1)
        probability = flag.decision.evidence.probability_result
        corruptions = (
            replace(flag, decision=replace(flag.decision, evidence=replace(
                flag.decision.evidence, constraints=()))),
            replace(flag, decision=replace(flag.decision, evidence=replace(
                flag.decision.evidence, probability_result=replace(
                    probability, probabilities=tuple(replace(p, mine_worlds=p.mine_worlds*2,
                                                            total_worlds=p.total_worlds*2)
                                                     for p in probability.probabilities),
                    total_worlds=probability.total_worlds*2)))),
        )
        for expected_ran, invalid in zip((False, True), corruptions):
            with self.subTest(enumerated=expected_ran), patch.object(
                    oracles, "_materialized_exact", side_effect=AssertionError("No fallback")):
                qualified, _, _, _, _ = _qualify_public_flags((invalid,), _plan().prerequisite)
                self.assertEqual(qualified[0].status, "FAIL")
                self.assertIs(qualified[0].independent_bounded_enumeration_ran, expected_ran)

    def test_small_dag_raw_results_equal_frozen_verifier_exactly(self):
        flags = _local_public_flag_chain(6)
        qualified, _, _, _, _ = _qualify_public_flags(flags)
        self.assertEqual(tuple(q.raw_verification for q in qualified),
                         tuple(evidence.verify_v1_flag_provenance(f) for f in flags))

    def test_long_valid_chain_admits_unique_nodes_without_recursive_support(self):
        # Prospective work bounds declared in fixture docstring before counting.
        for k in (16, 32, 64, 98):
            with self.subTest(k=k), patch.object(
                    harness, "_flag_public_support", side_effect=AssertionError("Recursive support forbidden")):
                qualified, premises, calls, _, findings = _qualify_public_flags(
                    _local_public_flag_chain(k))
                self.assertTrue(all(q.status == "PASS" for q in qualified))
                self.assertEqual(premises.work(), audit.PhysicalFlagWork(k, k, 0, k*(k-1)//2, k))
                self.assertEqual(calls, ())
                self.assertFalse(findings.failures)
                self.assertEqual(len(audit._support_history((), tuple(premises.records), premises)), k)

    def test_false_semantic_pair_never_becomes_true_on_repeated_cache_access(self):
        left = _local_public_flag_chain(2)
        right = (left[0], replace(left[1], num_mines=3))
        memo = {}
        self.assertFalse(audit._semantic_equal(left, right, memo))
        self.assertFalse(audit._semantic_equal(left, right, memo))

    def test_changed_duplicate_missing_reordered_and_future_premises_fail(self):
        flags = _local_public_flag_chain(3)
        changes = (
            (),
            (flags[0], flags[0]),
            tuple(reversed(flags[:2])),
            (flags[0], replace(flags[1], input_index=4, boundary=4)),
            (flags[0], replace(flags[1], num_mines=4)),
        )
        for prior in changes:
            with self.subTest(indices=tuple(f.input_index for f in prior)):
                premises = _qualify_public_flags(flags[:2])[1]
                with self.assertRaises(audit.E1AuditError):
                    premises.qualify(replace(flags[2], prior_flags=prior),
                                     calls=[], findings=audit._Findings())


class ExactReferenceReuseTests(unittest.TestCase):
    """Arithmetic reuse never supplies authority for a target or proof history."""

    def fixture(self):
        rows = ((1, H, H, H, H), (H, H, H, H, H))
        case = SimpleNamespace(case_id="NON_E1_EXACT_REUSE_PUBLIC_FIXTURE",
                               width=5, height=2, num_mines=7, first_click=(0, 0))
        result = _public_result("K-P0", 5, 2, 7, (rows,))
        return rows, result, case

    def projected(self, components):
        from experiments import program_k_e1_suite as suite
        return suite._encoded(tuple(sorted(components.items())), semantic=True)

    def uncached(self):
        return SimpleNamespace(oracles=oracles, audit_acquisition=harness.audit_acquisition)

    def test_repeated_identical_public_requests_enumerate_once(self):
        rows = ((H, H, H),)
        with patch.object(oracles, "_enumerate_supported_values",
                          wraps=oracles._enumerate_supported_values) as enumerate_values:
            references = audit._ExactReferenceReuse()
            with oracles.collect_oracle_diagnostics() as calls:
                results = tuple(references.oracles.enumerate_public_worlds(
                    rows, 1, status=GameStatus.PLAYING) for _ in range(7))
        self.assertEqual(enumerate_values.call_count, 1)
        self.assertEqual(results, (oracles.OracleAResult(
            3, (((0, 0), 1), ((1, 0), 1), ((2, 0), 1))),) * 7)
        self.assertEqual(len(calls), 7)
        self.assertTrue(all(c.status == "EVALUATED" for c in calls))

    def test_two_distinct_public_requests_repeated_n_m_enumerate_once_each(self):
        rows = ((H, H, H),)
        totals = (1,) * 5 + (2,) * 3 + (1, 2)
        expected = tuple(oracles.enumerate_public_worlds(
            rows, n, status=GameStatus.PLAYING) for n in totals)
        with patch.object(oracles, "_enumerate_supported_values",
                          wraps=oracles._enumerate_supported_values) as enumerate_values:
            references = audit._ExactReferenceReuse()
            actual = tuple(references.oracles.enumerate_public_worlds(
                rows, n, status=GameStatus.PLAYING) for n in totals)
        self.assertEqual(actual, expected)
        self.assertEqual(enumerate_values.call_count, 2)
        self.assertNotEqual(actual[0].mine_worlds, actual[5].mine_worlds)

    def test_equal_separately_allocated_history_and_arithmetic_reuse(self):
        rows, result, _ = self.fixture()
        proof = result.traces[1].selection.evidence.exact_certificates[0]
        copied_rows = tuple(tuple(v for v in row) for row in rows)
        copied_proof = replace(proof, observation=copied_rows,
                               mine_worlds=tuple((tuple(c), n) for c, n in proof.mine_worlds))
        self.assertIsNot(copied_rows, rows)
        self.assertIsNot(copied_proof, proof)
        self.assertEqual(copied_proof, proof)
        with patch.object(oracles, "_enumerate_supported_values",
                          wraps=oracles._enumerate_supported_values) as enumerate_values, patch.object(
                oracles, "_materialized_exact_values",
                wraps=oracles._materialized_exact_values) as materialize:
            references = audit._ExactReferenceReuse()
            first = references.oracles.materialized_exact_reference(
                rows, 7, status=GameStatus.PLAYING,
                logical_mines=frozenset((proof.target,)), proofs=(proof,))
            second = references.oracles.materialized_exact_reference(
                copied_rows, 7, status=GameStatus.PLAYING,
                logical_mines=frozenset(tuple(c) for c in (copied_proof.target,)),
                proofs=tuple(p for p in (copied_proof,)))
        self.assertEqual(first, second)
        self.assertEqual(enumerate_values.call_count, 1)
        self.assertEqual(materialize.call_count, 1)

    def test_each_arithmetic_input_part_changes_reference_request(self):
        # Exercise the primitive's complete contract, comparing every result
        # with its unchanged implementation before any memo is populated.
        base = (((H, H, H),), frozenset(), frozenset({(0, 0), (1, 0), (2, 0)}), 1)
        requests = (
            base,
            (((H, H, H, H),), *base[1:]),
            (base[0], frozenset({(3, 0)}), *base[2:]),
            (base[0], base[1], frozenset({(0, 0), (1, 0)}), base[3]),
            (*base[:3], 2),
        )
        expected = tuple(oracles._enumerate_supported(*args) for args in requests)
        with patch.object(oracles, "_enumerate_supported_values",
                          wraps=oracles._enumerate_supported_values) as enumerate_values:
            references = audit._ExactReferenceReuse()
            for _ in range(2):
                self.assertEqual(tuple(references.oracles._enumerate_supported(*args)
                                       for args in requests), expected)
        self.assertEqual(enumerate_values.call_count, len(requests))

    def test_changed_materialized_domain_and_mine_total_miss(self):
        requests = (
            (((H, H, H),), 1, frozenset()),
            (((H, H, H, H),), 1, frozenset()),
            (((H, H, H),), 2, frozenset()),
            (((H, H, H),), 1, frozenset({(0, 0)})),
        )
        expected = tuple(oracles._materialized_exact(*args) for args in requests)
        with patch.object(oracles, "_materialized_exact_values",
                          wraps=oracles._materialized_exact_values) as materialize:
            references = audit._ExactReferenceReuse()
            for _ in range(2):
                self.assertEqual(tuple(references.oracles._materialized_exact(*args)
                                       for args in requests), expected)
        self.assertEqual(materialize.call_count, len(requests))

    def test_arithmetic_key_distinguishes_boolean_from_equal_integer(self):
        # The low-level arithmetic accepts either combinations count, but
        # Python's True == 1 must not merge different typed requests.
        rows, fixed = ((H, H, H),), frozenset()
        unresolved = frozenset({(0, 0), (1, 0), (2, 0)})
        with patch.object(oracles, "_enumerate_supported_values",
                          wraps=oracles._enumerate_supported_values) as enumerate_values:
            references = audit._ExactReferenceReuse()
            results = tuple(references.oracles._enumerate_supported(rows, fixed, unresolved, count)
                            for count in (1, True, 1, True))
        self.assertEqual(results[0], results[1])
        self.assertEqual(enumerate_values.call_count, 2)

    def test_live_facades_do_not_share_results_or_rebind_module_functions(self):
        names = ("_enumerate_supported", "_materialized_exact", "_check_exact",
                 "_verify_history", "materialized_exact_reference", "enumerate_public_worlds")
        originals = tuple(getattr(oracles, name) for name in names)
        acquisition = harness.audit_acquisition
        with patch.object(oracles, "_enumerate_supported_values",
                          wraps=oracles._enumerate_supported_values) as enumerate_values:
            first, second = audit._ExactReferenceReuse(), audit._ExactReferenceReuse()
            results = tuple(checker.enumerate_public_worlds(((H, H, H),), 1, status=GameStatus.PLAYING)
                            for checker in (first.oracles, first.oracles, second.oracles, oracles))
        self.assertEqual(results, (results[0],) * 4)
        self.assertEqual(enumerate_values.call_count, 3)
        for name, original in zip(names, originals):
            self.assertIs(getattr(oracles, name), original)
        self.assertIs(harness.audit_acquisition, acquisition)

    def test_full_audit_bounds_enumeration_by_distinct_arithmetic_not_targets(self):
        _, result, case = self.fixture()
        with patch.object(oracles, "_enumerate_supported_values",
                          wraps=oracles._enumerate_supported_values) as enumerate_values:
            components = audit._audit_run(result, "K-P0", case)
        self.assertEqual(components["audit_status"], "PASS", components["discrepancies"])
        certificates = result.traces[1].selection.evidence.exact_certificates
        self.assertEqual(len(certificates), 6)
        self.assertEqual(tuple(a.certificate for a in components["acquisition_audits"]), certificates)
        self.assertTrue(all(a.status == "PASS" for a in components["acquisition_audits"]))
        self.assertEqual(enumerate_values.call_count, 1)
        self.assertGreater(sum(c.oracle == "A" for c in components["oracle_calls"]), 6)

    def test_separate_audit_runs_start_with_empty_reuse(self):
        _, result, case = self.fixture()
        with patch.object(oracles, "_enumerate_supported_values",
                          wraps=oracles._enumerate_supported_values) as enumerate_values:
            first = audit._audit_run(result, "K-P0", case)
            first_count = enumerate_values.call_count
            second = audit._audit_run(result, "K-P0", case)
        self.assertEqual(first_count, 1)
        self.assertEqual(enumerate_values.call_count, 2)
        self.assertEqual(first["audit_status"], second["audit_status"])
        self.assertEqual(self.projected(first), self.projected(second))

    def test_warm_arithmetic_never_authorizes_changed_target_or_claim(self):
        _, result, _ = self.fixture()
        certificate = result.traces[1].selection.evidence.exact_certificates[0]
        references = audit._ExactReferenceReuse()
        good = references.oracles.verify_exact_global_certificate(certificate)
        self.assertEqual(good.oracle_a_status, "ORACLE_A_EVALUATED")
        bad_counts = ((certificate.mine_worlds[0][0], 99),) + certificate.mine_worlds[1:]
        for changed in (
            replace(certificate, target=(1, 0)),
            replace(certificate, total_worlds=certificate.total_worlds + 1),
            replace(certificate, mine_worlds=bad_counts),
            replace(certificate, exact_reached=False),
        ):
            with self.subTest(changed=changed):
                for _ in range(2):
                    with self.assertRaises(oracles.PublicProofError):
                        references.oracles.verify_exact_global_certificate(changed)

    def test_warm_arithmetic_never_bypasses_history_support_or_status(self):
        rows, result, _ = self.fixture()
        certificate = result.traces[1].selection.evidence.exact_certificates[0]
        logical = frozenset({certificate.target})
        references = audit._ExactReferenceReuse()
        references.oracles.materialized_exact_reference(
            rows, 7, status=GameStatus.PLAYING, logical_mines=logical, proofs=(certificate,))
        invalid_histories = ((), (replace(certificate, total_worlds=99),))
        for proofs in invalid_histories:
            with self.subTest(proofs=proofs), self.assertRaises(oracles.PublicProofError):
                references.oracles.materialized_exact_reference(
                    rows, 7, status=GameStatus.PLAYING, logical_mines=logical, proofs=proofs)
        with self.assertRaises(oracles.PublicProofError):
            references.oracles.materialized_exact_reference(
                rows, 7, status=GameStatus.LOST, logical_mines=logical, proofs=(certificate,))

    def test_failed_reference_does_not_become_cached_success(self):
        rows = ((H, H, H),)
        with patch.object(oracles, "_enumerate_supported_values",
                          side_effect=oracles.PublicProofError("contradictory public arithmetic")) as enumerate_values:
            references = audit._ExactReferenceReuse()
            with oracles.collect_oracle_diagnostics() as calls:
                for _ in range(2):
                    with self.assertRaises(oracles.PublicProofError):
                        references.oracles.enumerate_public_worlds(rows, 1, status=GameStatus.PLAYING)
        self.assertEqual(enumerate_values.call_count, 2)
        self.assertEqual(tuple(c.status for c in calls), ("ERROR", "ERROR"))

    def test_not_evaluated_remains_not_evaluated_on_repetition(self):
        rows = ((H,) * 17,)
        references = audit._ExactReferenceReuse()
        with oracles.collect_oracle_diagnostics() as calls:
            for _ in range(2):
                with self.assertRaises(oracles.OracleANotEvaluated) as caught:
                    references.oracles.enumerate_public_worlds(rows, 1, status=GameStatus.PLAYING)
                self.assertEqual(caught.exception.variable_count, 17)
        self.assertEqual(tuple(c.status for c in calls), ("NOT_EVALUATED", "NOT_EVALUATED"))
        self.assertTrue(all(c.output_digest is None for c in calls))

    def test_shared_reference_cannot_replace_first_bounded_independent_check(self):
        rows, result, _ = self.fixture()
        certificate = result.traces[1].selection.evidence.exact_certificates[0]
        with patch.object(oracles, "_enumerate_supported_values",
                          wraps=oracles._enumerate_supported_values) as enumerate_values:
            references = audit._ExactReferenceReuse()
            references.oracles.materialized_exact_reference(rows, 7, status=GameStatus.PLAYING)
            self.assertEqual(enumerate_values.call_count, 0)
            checked = references.oracles.verify_exact_global_certificate(certificate)
        self.assertEqual(enumerate_values.call_count, 1)
        self.assertEqual(checked.oracle_a_status, "ORACLE_A_EVALUATED")
        self.assertEqual(checked.arithmetic_evidence, "INDEPENDENT BOUNDED ARITHMETIC EVIDENCE")

    def test_cached_and_uncached_audit_semantics_match_existing_projection(self):
        _, result, case = self.fixture()
        with patch.object(audit, "_ExactReferenceReuse", side_effect=self.uncached):
            before = audit._audit_run(result, "K-P0", case)
        after = audit._audit_run(result, "K-P0", case)
        self.assertEqual(before["audit_status"], "PASS")
        self.assertEqual(after["audit_status"], "PASS")
        self.assertEqual(self.projected(before), self.projected(after))

    def test_warmed_audit_failure_matches_uncached_semantic_projection(self):
        _, result, case = self.fixture()
        trace = result.traces[1]
        decision = trace.selection.evidence
        first, second, *later = decision.exact_certificates
        changed = replace(decision, exact_certificates=(
            first, replace(second, total_worlds=second.total_worlds + 1), *later))
        trace = replace(trace, selection=replace(trace.selection, evidence=changed))
        invalid = replace(result, traces=(result.traces[0], trace))
        with patch.object(audit, "_ExactReferenceReuse", side_effect=self.uncached):
            before = audit._audit_run(invalid, "K-P0", case)
        with patch.object(oracles, "_enumerate_supported_values",
                          wraps=oracles._enumerate_supported_values) as enumerate_values:
            after = audit._audit_run(invalid, "K-P0", case)
        self.assertEqual(before["audit_status"], "FAIL")
        self.assertEqual(after["audit_status"], "FAIL")
        self.assertEqual(after["acquisition_audits"][0].status, "PASS")
        self.assertEqual(after["acquisition_audits"][1].status, "FAIL")
        self.assertEqual(enumerate_values.call_count, 1)
        self.assertEqual(self.projected(before), self.projected(after))

    def test_cached_and_uncached_r1_shared_flag_semantics_match(self):
        case = SimpleNamespace(case_id="NON_E1_REUSE_SHARED_FLAG",
                               width=6, height=4, num_mines=5, first_click=(0, 0))
        result = _public_result("K-CONTROL", 6, 4, 5, _s_replan_public_prefixes())
        prerequisite = _plan().prerequisite
        with patch.object(audit, "_ExactReferenceReuse", side_effect=self.uncached):
            before = audit._audit_run(result, "K-CONTROL", case, prerequisite=prerequisite)
        after = audit._audit_run(result, "K-CONTROL", case, prerequisite=prerequisite)
        self.assertEqual(self.projected(before), self.projected(after))
        qualification = after["v1_audits"][4].external_qualification
        self.assertEqual(qualification.raw_verification.status, "NOT_EVALUATED")
        self.assertEqual(qualification.status, "PASS")
        self.assertEqual(qualification.shared_kernel_evidence, "SHARED-KERNEL REPRESENTATION EVIDENCE")

    def test_cache_hit_measures_fresh_work_instead_of_repeating_enumeration_duration(self):
        rows = ((H, H, H),)
        with patch.object(oracles, "perf_counter_ns", side_effect=(100, 1100, 2000, 2007)):
            references = audit._ExactReferenceReuse()
            with oracles.collect_oracle_diagnostics() as calls:
                first = references.oracles.enumerate_public_worlds(rows, 1, status=GameStatus.PLAYING)
                second = references.oracles.enumerate_public_worlds(rows, 1, status=GameStatus.PLAYING)
        self.assertEqual(first, second)
        self.assertEqual(tuple(c.duration_ns for c in calls), (1000, 7))
        self.assertEqual(sum(c.duration_ns for c in calls), 1007)
        self.assertEqual(calls[0].output_digest, calls[1].output_digest)
        self.assertEqual(tuple(c.sequence for c in calls), (0, 1))


if __name__ == "__main__":
    unittest.main()
