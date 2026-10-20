"""Pure Slice-4 tests: all 54 records are manually declared public evidence.

The frozen case identifiers below bind metadata only. No case is executed, no
board or hidden answer is constructed, and no per-run audit is recomputed.
Synthetic PASS/coverage results make no claim about actual E1 execution.
"""

import ast
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from enum import Enum
from fractions import Fraction
import hashlib
import inspect
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import benchmark_board
import core_engine
from core_engine import Action, CellState, GameStatus
from experiments import program_k_capability as capability
from experiments import program_k_e1_audit as audit
from experiments import program_k_e1_execution as execution
from experiments import program_k_e1_harness as e1
from experiments import program_k_e1_suite as suite
from experiments import program_k_evidence as evidence
from experiments import program_k_evaluator as evaluator
from experiments import program_k_harness as harness
from experiments import program_k_oracles as oracles
from experiments import program_k_policy as policy
from experiments import program_k_runner as runner
from simple_algorithm import InferenceResult, SimpleMove
from simple_decision import DecisionKind, SimpleDecision
from stage3_planner import RevealPlan, Stage3Decision
from stage3_runner import Stage3ActionTrace, Stage3RunResult
from tests.test_program_k_e1_audit import _corrupt, _plan


ROOT = Path(__file__).resolve().parents[1]
H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)
EMPTY = frozenset()
_DATA = None


def _semantic_k(rows, mines, owned, safes):
    """Declare detached fields directly, without capability/planner calls."""
    flags = frozenset((x, y) for y, row in enumerate(rows)
                      for x, value in enumerate(row) if value == F)
    hidden = frozenset((x, y) for y, row in enumerate(rows)
                       for x, value in enumerate(row) if value == H)
    account = capability.Accounting(
        flags, hidden, owned, flags | owned, hidden - owned,
        mines - len(flags | owned), ())
    local = capability.LocalAnalysis(
        account, account, EMPTY, safes, safes, EMPTY, safes, ())
    return capability.DecisionAnalysis(
        rows, mines, local, None, None, "NOT_REACHED", account, (),
        "LOCAL_SAFE", safes, None)


def _declared_result(case, variant, *, status=GameStatus.WON, cost_bias=0):
    """Public literals are test data, never generated/replayed game states."""
    hidden = tuple((H,) * case.width for _ in range(case.height))
    extended = case.case_id == "S-LIFECYCLE"
    if extended:
        afters = (((1, H, 1, H),), ((1, F, 1, H),), ((1, F, 1, 0),))
        moves = (SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 1, 0),
                 SimpleMove(Action.CHORD, 2, 0))
    else:
        afters = (tuple((0,) * case.width for _ in range(case.height)),)
        moves = (SimpleMove(Action.OPEN, 0, 0),)
    before, cursor = hidden, (0, 0)
    traces, effects, timings = [], [], []
    for index, (move, after) in enumerate(zip(moves, afters)):
        terminal = status if index == len(moves) - 1 else GameStatus.PLAYING
        cost = 100 + index * 10 + cost_bias
        effect = evidence.make_public_effect(
            before, move, after, input_index=index, status_after=terminal,
            cursor_before=cursor, modeled_action_us=cost)
        v1 = None
        k_decision = None
        selection = None
        owned = frozenset({(1, 0)}) if index else EMPTY
        category = "POLICY_INITIAL_OPEN" if not index else "SETUP_CHORD" if index == 1 else "DIRECT_CHORD"
        if index:
            safes = frozenset({(3, 0)})
            v1_evidence = SimpleDecision(
                DecisionKind.LOCAL_DETERMINISTIC, move, (),
                InferenceResult(safes, frozenset({(1, 0)}) if index == 1 else EMPTY), None)
            actions = moves[index:] if index == 1 else (move,)
            plan = RevealPlan(actions, sum(100 + i * 10 + cost_bias
                                          for i in range(index, len(moves))), 1)
            v1 = Stage3Decision(v1_evidence, move, plan)
            k_decision = _semantic_k(before, case.num_mines, owned, safes)
            candidate = policy.KCandidate(
                plan, category, frozenset({(1, 0)}) if index == 1 else EMPTY, safes)
            selection = policy.PolicySelection(
                k_decision, cursor, move, plan, category, (candidate,), (candidate,))
        if variant == "CONTROL":
            span = evidence.DecisionTimings(
                v1_plan_position_ns=11 if index else None, evidence_ns=13)
            trace = Stage3ActionTrace(
                move, v1, span.v1_plan_position_ns, cursor, cost, terminal,
                effect.safe_cells_opened_delta, effect.explicit_flag_delta)
        elif variant == "K-CONTROL":
            span = evidence.DecisionTimings(
                v1_plan_position_ns=11 if index else None, v1_execution_validation_ns=17,
                shadow_ns=19 if index else None, comparison_ns=23 if index else None,
                evidence_ns=13)
            shadow = runner.ShadowCheckpoint(
                last_valid_M=owned, decision=k_decision,
                last_valid_boundary=index if index else None, evidence_valid=bool(index))
            soundness = (evidence.ShadowSoundnessEvidence(
                "NO_DISCREPANCY", index, None, evidence.project_v1_decision(v1),
                ((3, 0),)) if index else None)
            trace = runner.KControlActionTrace(
                index, before, v1, move, cursor, cost, terminal, shadow,
                owned, owned, span, effect, "CAPTURED", soundness)
        else:
            span = evidence.DecisionTimings(
                k_analysis_planning_ns=29 if index else None,
                k_execution_validation_ns=31, evidence_ns=37)
            trace = runner.KActionTrace(
                index, move, category, selection, cursor, cost, terminal,
                owned, owned, span, effect, "CAPTURED")
        traces.append(trace)
        effects.append(effect)
        timings.append(span)
        before, cursor = after, (move.x, move.y)
    if variant == "CONTROL":
        return runner.ControlCaptureResult(
            Stage3RunResult(status, tuple(traces)), tuple(effects), tuple(timings))
    if variant == "K-CONTROL":
        return runner.KControlRunResult(
            status, tuple(traces), replace(traces[-1].shadow, decision=None, evidence_valid=False))
    return runner.KRunResult(status, tuple(traces), traces[-1].preinput_M)


def _mechanisms(result):
    records = []
    for index, trace in enumerate(result.traces):
        setup = trace.move.action is Action.FLAG
        chord = trace.move.action is Action.CHORD
        selection = trace.selection
        plan = None if selection is None else selection.plan
        records.append(audit.MechanismObservation(
            index, trace.move.action, (trace.move.x, trace.move.y), trace.category,
            frozenset({(1, 0)}) if setup else EMPTY,
            frozenset({(3, 0)}) if index else EMPTY,
            None if plan is None else plan.actions[-1],
            None if plan is None else plan.latency_us,
            None if plan is None else plan.reveals,
            trace.modeled_action_us, trace.public_effect.safe_cells_opened_delta,
            "SETUP_CHORD_FLAG" if setup else "CHORD_AFTER_PRIOR_SETUP" if chord else "OTHER",
            frozenset({(1, 0)}) if chord else EMPTY, (1,) if chord else ()))
    return tuple(records)


def _manual_audit(archive, source):
    result, variant = archive.result, archive.schedule_entry.variant
    costs = tuple(audit.ModelCCostAudit(
        i, t.modeled_action_us, t.modeled_action_us, t.modeled_action_us, "PASS")
                  for i, t in enumerate(result.traces))
    spans = []
    for index, trace in enumerate(result.traces):
        timing = result.timings[index] if variant == "CONTROL" else trace.timings
        measures = tuple(audit.TimingSpan(
            name, boundary, getattr(timing, name),
            "MEASURED" if getattr(timing, name) is not None else
            "UNMEASURED" if variant == "CONTROL" and name == "v1_execution_validation_ns"
            else "NOT_APPLICABLE") for name, boundary in audit._TIMING_BOUNDARIES)
        spans.append(audit.TimingCoverage(index, timing, measures))
    p3 = (harness.GuessCheckpointAudit(
        archive.case.case_id, variant, archive.case.num_mines,
        harness.content_digest(harness.ExecutionArchive(archive.case.case_id, variant, result)),
        (), ()) if variant != "K-CONTROL" else None)
    calls = (oracles.OracleCallDiagnostic(
        0, "A", "COMPLETE_WORLD_ENUMERATION", "1" * 64, "2" * 64, 41, 2,
        "EVALUATED", "INDEPENDENT BOUNDED ARITHMETIC EVIDENCE", None),) if variant == "K-P0" else ()
    a_records = (audit.OracleAAudit(
        0, harness.OracleCoverage("ORACLE_A_EVALUATED", 2, 16, None),
        oracles.OracleAResult(2, (((1, 0), 1), ((2, 0), 1))), 2, "PASS", ()),) if calls else ()
    replays = []
    if variant != "CONTROL":
        for i, trace in enumerate(result.traces):
            decision = trace.shadow.decision if variant == "K-CONTROL" else (
                trace.selection.evidence if trace.selection is not None else None)
            decision_digest = None if decision is None else harness.content_digest(decision)
            selection_digest = (harness.content_digest(trace.selection)
                                if variant == "K-P0" and trace.selection is not None else None)
            replays.append(audit.KReplayAudit(
                i, "PASS" if i else "NOT_APPLICABLE",
                "PASS" if i and variant == "K-P0" else "NOT_APPLICABLE",
                decision_digest, decision_digest, selection_digest, selection_digest,
                trace.shadow if variant == "K-CONTROL" else None, (), ""))
    return audit.E1RunAudit(
        source, archive.execution_source_identity.digest, archive.schedule_entry,
        archive.case, variant, archive.schedule_entry.repetition,
        evidence.EvidenceComparison("PASS", 0), costs, result.total_modeled_us,
        result.total_modeled_us,
        tuple(audit.V1ActionAudit(i, "PASS", "", None, None)
              for i in range(len(result.traces))) if variant != "K-P0" else (),
        tuple(replays),
        (), a_records, (), calls,
        (audit.OracleDiagnosticSpan(0, "DECLARED_ORACLE_A", 0, 1, "PASS", ()),) if calls else (),
        p3, "COMPLETE" if p3 is not None else "NOT_APPLICABLE",
        _mechanisms(result) if variant == "K-P0" else (),
        "COMPLETE" if variant == "K-P0" else "NOT_APPLICABLE",
        tuple(spans), audit.TIMING_CONTEXT, (), (), "PASS")


def _data():
    global _DATA
    if _DATA is None:
        plan = _plan()
        source = execution.capture_execution_source_identity(plan)
        archives = []
        for entry in plan.schedule:
            case = next(c for c in plan.cases if c.case_id == entry.case_id)
            receipt = execution.CaseMaterializationReceipt(
                case.case_id, case.source_type, case.width, case.height,
                case.num_mines, case.first_click, case.game_index, case.seed,
                case.board_fingerprint, case.runtime,
                "FIXED_SYNTHETIC_RESET" if case.game_index is None else "EXPERT_GENERAL_V1_RESET")
            archives.append(execution.E1ScheduledRunArchive(
                source, plan.source_identity.digest, entry, case, receipt,
                _declared_result(case, entry.variant), 1.0,
                "APPLIED" if entry.variant == "K-CONTROL" else "NOT_APPLICABLE"))
        source = audit.capture_audit_source_identity(plan, archives[0])
        archives = tuple(archives)
        _DATA = plan, archives, tuple(_manual_audit(a, source) for a in archives)
    return _DATA


def _index(case="S-LIFECYCLE", variant="K-P0", repetition=1):
    return next(e.schedule_index for e in _plan().schedule
                if (e.case_id, e.variant, e.repetition) == (case, variant, repetition))


def _set(items, index, value):
    return items[:index] + (value,) + items[index + 1:]


def _bind_p3(archive, checked):
    """When mutating an archive deliberately, retain its exact new P-3 binding."""
    if checked.p3_audit is None:
        return checked
    digest = harness.content_digest(harness.ExecutionArchive(
        archive.case.case_id, archive.schedule_entry.variant, archive.result))
    return replace(checked, p3_audit=replace(checked.p3_audit, archive_digest=digest))


def _trace(archive, index, **changes):
    traces = _set(archive.result.traces, index, _corrupt(archive.result.traces[index], **changes))
    result = archive.result
    result = (_corrupt(result, control=_corrupt(result.control, traces=traces))
              if archive.schedule_entry.variant == "CONTROL" else _corrupt(result, traces=traces))
    return _corrupt(archive, result=result)


def _checkpoint(case, *, outcome=GameStatus.WON, scale=1, domain=None):
    domain = ((1, 0), (2, 0)) if domain is None else domain
    return harness.GuessCheckpoint(
        case.case_id, 1, (((0, 0), 1),), EMPTY, frozenset(domain), 1, 2 * scale,
        tuple((c, scale) for c in domain), tuple((c, Fraction(1, 2)) for c in domain),
        Fraction(1, 2), frozenset(domain), min(domain, key=lambda c: (c[1], c[0])), outcome)


class SuiteCase(unittest.TestCase):
    def aggregate(self, archives=None, audits=None):
        plan, base_archives, base_audits = _data()
        return suite.aggregate_e1_suite(
            plan, base_archives if archives is None else archives,
            base_audits if audits is None else audits)

    def changed_archive(self, index, archive):
        _, archives, audits = _data()
        checked = _bind_p3(archive, audits[index])
        # Duration-only mutations must retain both copies of the archived
        # measurement while remaining semantically equal across repetitions.
        refreshed = _manual_audit(archive, checked.source_identity)
        checked = replace(checked, timings=refreshed.timings)
        return _set(archives, index, archive), _set(audits, index, checked)

    def changed_audit(self, index, **changes):
        return _set(_data()[2], index, _corrupt(_data()[2][index], **changes))

    def repetition(self, result, case="S-LIFECYCLE", variant="K-P0"):
        return next(r for r in result.repetitions if r.case_id == case and r.variant == variant)


class SourceIdentityTests(SuiteCase):
    def test_current_committed_slice3_identity(self):
        plan, archives, audits = _data()
        current = audit.capture_audit_source_identity(plan, archives[0])
        self.assertEqual(current.digest, "ac547f94fb15340d3d0e94f13722372d57edf3cda5f73da63191dc596b866df4")
        identity = suite.capture_suite_source_identity(plan, archives[0], audits[0])
        self.assertEqual(identity.audit_source_digest, current.digest)

    def test_exact_suite_bytes_and_size(self):
        source = suite.capture_suite_source_identity(_data()[0], _data()[1][0], _data()[2][0])
        raw = Path(suite.__file__).read_bytes()
        self.assertEqual(source.suite_file.path, "experiments/program_k_e1_suite.py")
        self.assertEqual(source.suite_file.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(source.suite_file.size_bytes, len(raw))

    def test_identity_is_deterministic(self):
        args = (_data()[0], _data()[1][0], _data()[2][0])
        first = suite.capture_suite_source_identity(*args)
        second = suite.capture_suite_source_identity(*args)
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)

    def test_test_file_excluded(self):
        source = suite.capture_suite_source_identity(_data()[0], _data()[1][0], _data()[2][0])
        self.assertNotIn("test_program_k_e1_suite", repr(source))

    def test_suite_byte_mutation_changes_identity_without_writing(self):
        args = (_data()[0], _data()[1][0], _data()[2][0], ROOT)
        first = suite._capture_suite_source_identity(*args)
        read = Path.read_bytes
        def altered(path):
            raw = read(path)
            return raw + b"\n# in-memory source probe\n" if path.name == "program_k_e1_suite.py" else raw
        with patch.object(Path, "read_bytes", altered):
            second = suite._capture_suite_source_identity(*args)
        self.assertNotEqual(first.digest, second.digest)
        self.assertEqual(first.audit_source_digest, second.audit_source_digest)

    def test_slice3_source_drift_rejected(self):
        current = _data()[2][0].source_identity
        changed = replace(current, audit_file=replace(current.audit_file, sha256="a" * 64))
        with patch.object(audit, "capture_audit_source_identity", return_value=changed):
            with self.assertRaises(suite.E1SuiteError):
                self.aggregate()

    def test_suite_identity_recaptured_after_aggregation(self):
        args = (_data()[0], _data()[1][0], _data()[2][0])
        first = suite.capture_suite_source_identity(*args)
        changed = replace(first, suite_file=replace(first.suite_file, sha256="b" * 64))
        with patch.object(suite, "capture_suite_source_identity", side_effect=(first, changed)) as capture:
            with self.assertRaises(suite.E1SuiteError):
                self.aggregate()
        self.assertEqual(capture.call_count, 2)

    def test_frozen_authority_identity_retained(self):
        source = self.aggregate().source_identity
        for name in ("spec_sha256", "protocol_sha256", "model_id", "profile_sha256", "table_sha256"):
            self.assertEqual(getattr(source, name), getattr(_plan().prerequisite, name))


class CoverageAndBindingTests(SuiteCase):
    def test_complete_exact_order_has_54_bindings(self):
        result = self.aggregate()
        self.assertEqual(len(result.bindings), 54)
        self.assertEqual(tuple(b.schedule_entry for b in result.bindings), _plan().schedule)
        self.assertEqual(result.suite_status, "PASS")

    def test_missing_archive_rejected(self):
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(archives=_data()[1][:-1])

    def test_extra_archive_rejected(self):
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(archives=_data()[1] + (_data()[1][0],))

    def test_missing_audit_rejected(self):
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(audits=_data()[2][:-1])

    def test_extra_audit_rejected(self):
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(audits=_data()[2] + (_data()[2][0],))

    def test_duplicate_archive_rejected(self):
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(archives=_set(_data()[1], 1, _data()[1][0]))

    def test_duplicate_audit_rejected(self):
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(audits=_set(_data()[2], 1, _data()[2][0]))

    def test_reordered_pairs_rejected(self):
        _, archives, audits = _data()
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate((archives[1], archives[0]) + archives[2:],
                           (audits[1], audits[0]) + audits[2:])

    def test_wrong_schedule_fields_rejected(self):
        original = _data()[1][0]
        for changes in ({"case_id": "S-LOSS"}, {"repetition": 2},
                        {"variant": "K-P0"}, {"schedule_index": 1}):
            with self.subTest(changes=changes), self.assertRaises(suite.E1SuiteError):
                archive = _corrupt(original, schedule_entry=_corrupt(original.schedule_entry, **changes))
                self.aggregate(archives=_set(_data()[1], 0, archive))

    def test_mutable_input_lists_rejected(self):
        for archives, audits in ((list(_data()[1]), _data()[2]), (_data()[1], list(_data()[2]))):
            with self.subTest(collection=type(archives)), self.assertRaises(suite.E1SuiteError):
                self.aggregate(archives, audits)

    def test_exact_archive_and_audit_types_required(self):
        for archives, audits in ((_set(_data()[1], 0, object()), _data()[2]),
                                (_data()[1], _set(_data()[2], 0, object()))):
            with self.assertRaises(suite.E1SuiteError):
                self.aggregate(archives, audits)

    def test_exact_plan_required(self):
        with self.assertRaises(suite.E1SuiteError):
            suite.aggregate_e1_suite(None, _data()[1], _data()[2])

    def test_mixed_plan_digest_rejected(self):
        archive = _corrupt(_data()[1][10], plan_source_digest="c" * 64)
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(archives=_set(_data()[1], 10, archive))

    def test_mixed_execution_identity_rejected(self):
        archive = _data()[1][10]
        identity = replace(archive.execution_source_identity, execution_file=replace(
            archive.execution_source_identity.execution_file, sha256="d" * 64))
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(archives=_set(_data()[1], 10, _corrupt(archive, execution_source_identity=identity)))

    def test_mixed_audit_identity_rejected(self):
        checked = _data()[2][10]
        identity = replace(checked.source_identity, audit_file=replace(
            checked.source_identity.audit_file, sha256="e" * 64))
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(audits=self.changed_audit(10, source_identity=identity))

    def test_original_archive_and_audit_objects_retained(self):
        result = self.aggregate()
        for binding, archive, checked in zip(result.bindings, _data()[1], _data()[2]):
            self.assertIs(binding.archive, archive)
            self.assertIs(binding.audit, checked)
            self.assertEqual(binding.execution_source_digest, archive.execution_source_identity.digest)
            self.assertEqual(binding.audit_source_digest, checked.source_identity.digest)

    def test_content_digests_are_deterministic(self):
        first, second = self.aggregate(), self.aggregate()
        self.assertEqual(tuple((b.archive_content_digest, b.audit_content_digest) for b in first.bindings),
                         tuple((b.archive_content_digest, b.audit_content_digest) for b in second.bindings))

    def test_content_digests_include_compare_false_timing_fields(self):
        index = _index()
        archive = _data()[1][index]
        span = replace(archive.result.traces[1].timings, evidence_ns=999)
        changed = _trace(archive, 1, timings=span)
        before = self.aggregate().bindings[index]
        after = self.aggregate(*self.changed_archive(index, changed)).bindings[index]
        self.assertNotEqual(before.archive_content_digest, after.archive_content_digest)
        self.assertNotEqual(before.audit_content_digest, after.audit_content_digest)

    def test_wrong_audit_pair_rejected(self):
        checked = _data()[2][0]
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(audits=_set(_data()[2], 3, checked))

    def test_stale_p3_content_digest_rejected(self):
        index = _index()
        changed = _trace(_data()[1][index], 1, category="CHANGED_CATEGORY")
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(archives=_set(_data()[1], index, changed))

    def test_audit_only_suite_not_accepted(self):
        with self.assertRaises((TypeError, suite.E1SuiteError)):
            suite.aggregate_e1_suite(_plan(), _data()[2])


class RepetitionTests(SuiteCase):
    def test_exactly_27_semantic_repetition_records(self):
        result = self.aggregate()
        self.assertEqual(len(result.repetitions), 27)
        self.assertTrue(all(r.status == "PASS" for r in result.repetitions))

    def test_timing_only_archive_change_is_deterministic(self):
        index = _index(repetition=2)
        archive = _data()[1][index]
        changed = _trace(archive, 1, timings=replace(archive.result.traces[1].timings,
                                                   k_analysis_planning_ns=987654))
        self.assertEqual(self.repetition(self.aggregate(*self.changed_archive(index, changed))).status, "PASS")

    def test_control_planner_duration_noise_excluded(self):
        index = _index(variant="CONTROL", repetition=2)
        archive = _trace(_data()[1][index], 1, decision_compute_ns=123456)
        spans = _set(archive.result.timings, 1, replace(archive.result.timings[1],
                                                     v1_plan_position_ns=123456))
        archive = _corrupt(archive, result=_corrupt(archive.result, timings=spans))
        result = self.aggregate(*self.changed_archive(index, archive))
        self.assertEqual(self.repetition(result, variant="CONTROL").status, "PASS")

    def test_oracle_duration_noise_excluded(self):
        index = _index(repetition=2)
        checked = _data()[2][index]
        calls = (replace(checked.oracle_calls[0], duration_ns=987654321),)
        result = self.aggregate(audits=self.changed_audit(index, oracle_calls=calls))
        self.assertEqual(self.repetition(result).status, "PASS")

    def test_audited_runner_duration_noise_excluded(self):
        index = _index(repetition=2)
        archive = _data()[1][index]
        timing = replace(archive.result.traces[1].timings, evidence_ns=88888)
        result = self.aggregate(*self.changed_archive(index, _trace(archive, 1, timings=timing)))
        self.assertEqual(self.repetition(result).status, "PASS")

    def test_category_change_is_semantic_divergence(self):
        index = _index(repetition=2)
        archive = _trace(_data()[1][index], 1, category="DIFFERENT_CATEGORY")
        result = self.aggregate(*self.changed_archive(index, archive))
        self.assertEqual(self.repetition(result).status, "FAIL")

    def test_physical_action_change_is_repetition_divergence(self):
        index = _index(repetition=2)
        changed = _trace(_data()[1][index], 1, move=SimpleMove(Action.OPEN, 3, 0))
        self.assertEqual(self.repetition(self.aggregate(*self.changed_archive(index, changed))).status, "FAIL")

    def test_terminal_outcome_change_is_repetition_divergence(self):
        index = _index(repetition=2)
        archive = _data()[1][index]
        archive = replace(archive, result=_declared_result(archive.case, "K-P0", status=GameStatus.LOST))
        self.assertEqual(self.repetition(self.aggregate(*self.changed_archive(index, archive))).status, "FAIL")

    def test_public_effect_change_is_repetition_divergence(self):
        index = _index(repetition=2)
        archive = _data()[1][index]
        old = archive.result.traces[-1].public_effect
        changed = evidence.make_public_effect(
            old.before_observation, archive.result.traces[-1].move, ((1, F, 1, 1),),
            input_index=2, status_after=old.status_after, cursor_before=old.cursor_before,
            modeled_action_us=old.modeled_action_us)
        archive = _trace(archive, 2, public_effect=changed)
        self.assertEqual(self.repetition(self.aggregate(*self.changed_archive(index, archive))).status, "FAIL")

    def test_k_decision_change_is_semantic_divergence(self):
        index = _index(repetition=2)
        archive = _data()[1][index]
        selected = archive.result.traces[1].selection
        changed = replace(selected, evidence=replace(selected.evidence, continuation="EXACT_GUESS"))
        result = self.aggregate(*self.changed_archive(index, _trace(archive, 1, selection=changed)))
        self.assertEqual(self.repetition(result).status, "FAIL")

    def test_final_logical_m_change_is_semantic_divergence(self):
        index = _index(repetition=2)
        archive = _data()[1][index]
        archive = _corrupt(archive, result=_corrupt(archive.result, final_M=EMPTY))
        self.assertEqual(self.repetition(self.aggregate(*self.changed_archive(index, archive))).status, "FAIL")

    def test_mechanism_change_is_semantic_divergence(self):
        index = _index(repetition=2)
        checked = _data()[2][index]
        obs = _set(checked.mechanism_observations, 1,
                   replace(checked.mechanism_observations[1], plan_latency_us=999))
        self.assertEqual(self.repetition(self.aggregate(
            audits=self.changed_audit(index, mechanism_observations=obs))).status, "FAIL")

    def test_p3_checkpoint_change_is_semantic_divergence(self):
        index = _index(repetition=2)
        checked = _data()[2][index]
        p3 = replace(checked.p3_audit, checkpoints=(_checkpoint(checked.case),))
        result = self.aggregate(audits=self.changed_audit(index, p3_audit=p3))
        self.assertEqual(self.repetition(result).status, "FAIL")

    def test_oracle_semantic_result_change_is_divergence(self):
        index = _index(repetition=2)
        checked = _data()[2][index]
        oracle = replace(checked.oracle_a_audits[0], result=oracles.OracleAResult(
            4, (((1, 0), 2), ((2, 0), 2))))
        result = self.aggregate(audits=self.changed_audit(index, oracle_a_audits=(oracle,)))
        self.assertEqual(self.repetition(result).status, "FAIL")

    def test_missing_p3_projection_is_incomplete(self):
        audits = _data()[2]
        for rep in (1, 2):
            i = _index(repetition=rep)
            audits = _set(audits, i, _corrupt(audits[i], p3_audit=None, p3_status="INCOMPLETE",
                                             audit_status="INCOMPLETE", incomplete_reasons=("Missing P3",)))
        result = self.aggregate(audits=audits)
        self.assertEqual(self.repetition(result).status, "INCOMPLETE")

    def test_asymmetric_missing_required_audit_record_is_incomplete(self):
        index = _index(repetition=2)
        checked = _data()[2][index]
        result = self.aggregate(audits=self.changed_audit(index, cost_audits=checked.cost_audits[:-1]))
        self.assertEqual(self.repetition(result).status, "INCOMPLETE")


class ControlIdentityTests(SuiteCase):
    def test_exactly_18_identity_pairs_pass(self):
        result = self.aggregate()
        self.assertEqual(len(result.control_identity_pairs), 18)
        self.assertTrue(all(p.status == "PASS" for p in result.control_identity_pairs))

    def test_existing_effect_and_o4_comparators_called(self):
        with patch.object(evidence, "compare_public_effects", wraps=evidence.compare_public_effects) as effects:
            with patch.object(evidence, "compare_v1_decisions", wraps=evidence.compare_v1_decisions) as decisions:
                result = self.aggregate()
        self.assertEqual(effects.call_count, 22)
        self.assertEqual(decisions.call_count, 4)
        self.assertEqual(sum(len(p.v1_decision_comparisons) for p in result.control_identity_pairs), 4)

    def test_physical_move_cursor_cost_and_status_mismatch_fail(self):
        index = _index(variant="K-CONTROL")
        for changes in ({"move": SimpleMove(Action.OPEN, 3, 0)}, {"cursor_before": (2, 0)},
                        {"modeled_action_us": 999}, {"status_after": GameStatus.LOST}):
            with self.subTest(changes=changes):
                archive = _trace(_data()[1][index], 1, **changes)
                result = self.aggregate(*self.changed_archive(index, archive))
                self.assertEqual(result.control_identity_pairs[2].status, "FAIL")

    def test_public_effect_mismatch_fails(self):
        index = _index(variant="K-CONTROL")
        archive = _data()[1][index]
        old = archive.result.traces[1].public_effect
        effect = evidence.make_public_effect(
            old.before_observation, archive.result.traces[1].move, ((1, F, 1, 0),),
            input_index=1, status_after=old.status_after, cursor_before=old.cursor_before,
            modeled_action_us=old.modeled_action_us)
        result = self.aggregate(*self.changed_archive(index, _trace(archive, 1, public_effect=effect)))
        self.assertEqual(result.control_identity_pairs[2].status, "FAIL")

    def test_o4_semantic_mismatch_fails(self):
        index = _index(variant="K-CONTROL")
        archive = _data()[1][index]
        decision = archive.result.traces[1].decision
        changed = replace(decision, plan=replace(decision.plan, latency_us=999))
        result = self.aggregate(*self.changed_archive(index, _trace(archive, 1, decision=changed)))
        self.assertEqual(result.control_identity_pairs[2].status, "FAIL")

    def test_missing_v1_decision_is_incomplete(self):
        archives, audits = _data()[1:]
        for rep in (1, 2):
            i = _index(variant="K-CONTROL", repetition=rep)
            archives = _set(archives, i, _trace(archives[i], 1, decision=None))
        result = self.aggregate(archives, audits)
        self.assertEqual(result.control_identity_pairs[2].status, "INCOMPLETE")

    def test_shadow_timeout_retains_physical_stream_and_is_incomplete(self):
        archives, audits = _data()[1:]
        before = archives[_index(variant="K-CONTROL")].result.moves
        for rep in (1, 2):
            i = _index(variant="K-CONTROL", repetition=rep)
            failure = runner.ShadowFailure("SHADOW_TIMEOUT", 1, None, "synthetic timeout")
            old = archives[i].result.traces[1].shadow
            shadow = replace(old, enabled=False, decision=None, failure=failure, evidence_valid=False)
            archives = _set(archives, i, _trace(archives[i], 1, shadow=shadow))
            replay = replace(audits[i].replay_audits[1], decision_status="INCOMPLETE",
                             archived_decision_digest=None, replayed_decision_digest=None, shadow=shadow)
            audits = _set(audits, i, replace(audits[i], audit_status="INCOMPLETE",
                                           replay_audits=_set(audits[i].replay_audits, 1, replay),
                                           incomplete_reasons=("Shadow timeout",)))
        result = self.aggregate(archives, audits)
        self.assertEqual(result.control_identity_pairs[2].status, "INCOMPLETE")
        self.assertEqual(result.bindings[_index(variant="K-CONTROL")].archive.result.moves, before)
        self.assertEqual(result.suite_status, "INCOMPLETE")

    def test_shadow_soundness_violation_fails(self):
        index = _index(variant="K-CONTROL")
        archive = _data()[1][index]
        old = archive.result.traces[1].soundness
        guess = replace(old.v1_decision, evidence=replace(
            old.v1_decision.evidence, kind=DecisionKind.PROBABILITY_GUESS))
        soundness = replace(old, classification="SHADOW_SOUNDNESS_VIOLATION",
                            implicated_boundary=1, v1_decision=guess)
        result = self.aggregate(*self.changed_archive(index, _trace(archive, 1, soundness=soundness)))
        self.assertEqual(result.control_identity_pairs[2].status, "FAIL")

    def test_trace_count_mismatch_fails(self):
        index = _index(variant="K-CONTROL")
        archive = _data()[1][index]
        archive = _corrupt(archive, result=_corrupt(archive.result, traces=archive.result.traces[:-1]))
        self.assertEqual(self.aggregate(*self.changed_archive(index, archive)).control_identity_pairs[2].status,
                         "FAIL")


class P3OutcomeTests(SuiteCase):
    def test_exact_comparator_called_for_18_pairs(self):
        with patch.object(harness, "compare_guess_checkpoints", wraps=harness.compare_guess_checkpoints) as compare:
            result = self.aggregate()
        self.assertEqual(compare.call_count, 18)
        self.assertEqual(len(result.p3_outcome_pairs), 18)
        self.assertTrue(all(type(p.comparison) is harness.GuessComparison for p in result.p3_outcome_pairs))

    def test_matching_no_guess_pairs_pass(self):
        self.assertTrue(all(p.comparison.status == "PASS" for p in self.aggregate().p3_outcome_pairs))

    def test_matching_uncertain_checkpoints_pass(self):
        audits = _data()[2]
        for variant in ("CONTROL", "K-P0"):
            for rep in (1, 2):
                i = _index(variant=variant, repetition=rep)
                p3 = replace(audits[i].p3_audit, checkpoints=(_checkpoint(audits[i].case),))
                audits = _set(audits, i, replace(audits[i], p3_audit=p3))
        result = self.aggregate(audits=audits)
        self.assertEqual(result.p3_outcome_pairs[2].comparison.status, "PASS")

    def test_missing_extra_checkpoint_is_existing_comparator_failure(self):
        i = _index()
        checked = _data()[2][i]
        changed = replace(checked.p3_audit, checkpoints=(_checkpoint(checked.case),))
        result = self.aggregate(audits=self.changed_audit(i, p3_audit=changed))
        self.assertEqual(result.p3_outcome_pairs[2].comparison.status, "FAIL")

    def test_count_mismatch_with_same_fraction_fails(self):
        audits = _data()[2]
        for variant, scale in (("CONTROL", 1), ("K-P0", 2)):
            i = _index(variant=variant)
            p3 = replace(audits[i].p3_audit, checkpoints=(_checkpoint(audits[i].case, scale=scale),))
            audits = _set(audits, i, replace(audits[i], p3_audit=p3))
        result = self.aggregate(audits=audits)
        self.assertEqual(result.p3_outcome_pairs[2].comparison.status, "FAIL")

    def test_target_candidate_mismatch_fails(self):
        audits = _data()[2]
        for variant, domain in (("CONTROL", ((1, 0), (2, 0))), ("K-P0", ((2, 0), (3, 0)))):
            i = _index(variant=variant)
            p3 = replace(audits[i].p3_audit, checkpoints=(_checkpoint(audits[i].case, domain=domain),))
            audits = _set(audits, i, replace(audits[i], p3_audit=p3))
        self.assertEqual(self.aggregate(audits=audits).p3_outcome_pairs[2].comparison.status, "FAIL")

    def test_risk_mismatch_uses_exact_fraction_comparison(self):
        audits = _data()[2]
        i, j = _index(variant="CONTROL"), _index()
        first = _checkpoint(audits[i].case)
        domain = ((1, 0), (2, 0), (3, 0))
        second = harness.GuessCheckpoint(
            audits[j].case.case_id, 1, (((0, 0), 1),), EMPTY, frozenset(domain), 1, 4,
            (((1, 0), 2), ((2, 0), 1), ((3, 0), 1)),
            (((1, 0), Fraction(1, 2)), ((2, 0), Fraction(1, 4)), ((3, 0), Fraction(1, 4))),
            Fraction(1, 4), frozenset({(2, 0), (3, 0)}), (2, 0), GameStatus.WON)
        for index, checkpoint in ((i, first), (j, second)):
            audits = _set(audits, index, replace(audits[index], p3_audit=replace(
                audits[index].p3_audit, checkpoints=(checkpoint,))))
        self.assertEqual(self.aggregate(audits=audits).p3_outcome_pairs[2].comparison.status, "FAIL")

    def test_missing_checkpoint_evidence_is_incomplete(self):
        audits = _data()[2]
        for rep in (1, 2):
            i = _index(repetition=rep)
            p3 = replace(audits[i].p3_audit, incomplete=("Uncertain evidence unavailable",))
            audits = _set(audits, i, replace(audits[i], p3_audit=p3, p3_status="INCOMPLETE",
                                           audit_status="INCOMPLETE", incomplete_reasons=("Missing evidence",)))
        self.assertEqual(self.aggregate(audits=audits).p3_outcome_pairs[2].comparison.status, "INCOMPLETE")

    def _outcomes(self, control, kp0):
        archives, audits = _data()[1:]
        for variant, status in (("CONTROL", control), ("K-CONTROL", control), ("K-P0", kp0)):
            for rep in (1, 2):
                i = _index(case="S-WIN", variant=variant, repetition=rep)
                archive = archives[i]
                result = _declared_result(archive.case, variant, status=status)
                archive = replace(archive, result=result)
                archives = _set(archives, i, archive)
                audits = _set(audits, i, _bind_p3(archive, audits[i]))
        return self.aggregate(archives, audits)

    def test_wl_is_semantic_failure(self):
        result = self._outcomes(GameStatus.WON, GameStatus.LOST)
        self.assertEqual(result.p3_outcome_pairs[0].outcome, "WL")
        self.assertEqual(result.suite_status, "FAIL")
        self.assertIsNone(result.model_c.games[0].delta_us)
        self.assertEqual(result.model_c.wl_count, 2)

    def test_lw_is_semantic_failure(self):
        result = self._outcomes(GameStatus.LOST, GameStatus.WON)
        self.assertEqual(result.p3_outcome_pairs[0].outcome, "LW")
        self.assertEqual(result.suite_status, "FAIL")
        self.assertIsNone(result.model_c.games[0].delta_us)
        self.assertEqual(result.model_c.lw_count, 2)

    def test_ll_is_permitted_semantics_and_no_speed_delta(self):
        result = self._outcomes(GameStatus.LOST, GameStatus.LOST)
        self.assertEqual(result.p3_outcome_pairs[0].outcome, "LL")
        self.assertEqual(result.p3_outcome_pairs[0].status, "PASS")
        self.assertEqual(result.suite_status, "PASS")
        self.assertEqual(result.model_c.ll_count, 2)
        self.assertEqual(result.model_c.ww_count, 16)
        self.assertEqual(len(result.model_c.ww_deltas), 16)


class MechanismTests(SuiteCase):
    def _changed_observations(self, transform, reps=(1, 2)):
        audits = _data()[2]
        for rep in reps:
            i = _index(repetition=rep)
            audits = _set(audits, i, replace(audits[i],
                                           mechanism_observations=transform(audits[i].mechanism_observations)))
        return self.aggregate(audits=audits)

    def test_actual_prior_setup_and_productive_chord_both_repetitions_observed(self):
        coverage = self.aggregate().mechanism_coverage
        self.assertEqual(coverage.status, "OBSERVED")
        self.assertIn("S-LIFECYCLE", coverage.observed_case_ids)
        self.assertEqual(len(coverage.progressions), 2)

    def test_only_one_repetition_cannot_establish_coverage(self):
        result = self._changed_observations(
            lambda obs: tuple(replace(o, kind="DIRECT_CHORD" if o.action is Action.CHORD else "OTHER",
                                      prior_setup_input_indices=()) for o in obs),
            reps=(2,))
        self.assertNotEqual(result.mechanism_coverage.status, "OBSERVED")
        self.assertEqual(result.mechanism_coverage.status, "MISSING")

    def test_direct_chord_is_not_required_coverage(self):
        result = self._changed_observations(lambda obs: tuple(
            replace(o, kind="DIRECT_CHORD" if o.action is Action.CHORD else "OTHER",
                    prior_setup_input_indices=()) for o in obs))
        self.assertEqual(result.mechanism_coverage.status, "MISSING")
        self.assertEqual(result.suite_status, "INCOMPLETE")
        self.assertEqual(result.supplement_status, "REQUIRED_PROSPECTIVE_A_E5")

    def test_abandoned_setup_receives_no_productive_credit(self):
        result = self._changed_observations(lambda obs: tuple(
            replace(o, kind="DIRECT_CHORD", prior_setup_input_indices=())
            if o.action is Action.CHORD else o for o in obs))
        self.assertEqual(result.mechanism_coverage.status, "MISSING")
        self.assertEqual(result.mechanism_coverage.progressions, ())
        self.assertEqual(result.model_c.ww_kp0_total_us, self.aggregate().model_c.ww_kp0_total_us)

    def test_zero_reveal_chord_never_observed(self):
        result = self._changed_observations(lambda obs: tuple(
            replace(o, safe_cells_opened_delta=0) if o.action is Action.CHORD else o for o in obs))
        self.assertNotEqual(result.mechanism_coverage.status, "OBSERVED")

    def test_malformed_prior_index_is_invalid(self):
        result = self._changed_observations(lambda obs: tuple(
            replace(o, prior_setup_input_indices=(77,)) if o.action is Action.CHORD else o for o in obs))
        self.assertEqual(result.mechanism_coverage.status, "INVALID")
        self.assertEqual(result.suite_status, "FAIL")
        self.assertEqual(result.supplement_status, "NOT_APPLICABLE_ON_FAILURE")

    def test_forward_prior_index_is_invalid(self):
        result = self._changed_observations(lambda obs: tuple(
            replace(o, prior_setup_input_indices=(2,)) if o.action is Action.CHORD else o for o in obs))
        self.assertEqual(result.mechanism_coverage.status, "INVALID")

    def test_missing_relevant_physical_flag_is_invalid(self):
        result = self._changed_observations(lambda obs: tuple(
            replace(o, relevant_physical_flags=EMPTY) if o.action is Action.CHORD else o for o in obs))
        self.assertEqual(result.mechanism_coverage.status, "INVALID")

    def test_invalid_setup_never_retains_productive_progression(self):
        result = self._changed_observations(lambda obs: tuple(
            replace(o, setup_cells=EMPTY) if o.kind == "SETUP_CHORD_FLAG" else o for o in obs))
        self.assertEqual(result.mechanism_coverage.status, "INVALID")
        self.assertEqual(result.mechanism_coverage.progressions, ())

    def test_terminal_boundary_invalidates_claimed_progression(self):
        archives, audits = _data()[1:]
        for rep in (1, 2):
            i = _index(repetition=rep)
            archives = _set(archives, i, _trace(archives[i], 1, status_after=GameStatus.LOST))
            audits = _set(audits, i, _bind_p3(archives[i], audits[i]))
        self.assertEqual(self.aggregate(archives, audits).mechanism_coverage.status, "INVALID")

    def test_nonpassing_audit_cannot_supply_observed_mechanism(self):
        audits = _data()[2]
        for rep in (1, 2):
            i = _index(repetition=rep)
            audits = _set(audits, i, replace(audits[i], audit_status="INCOMPLETE",
                                           incomplete_reasons=("Missing public evidence",)))
        self.assertNotEqual(self.aggregate(audits=audits).mechanism_coverage.status, "OBSERVED")

    def test_no_counterfactual_saving_or_benefit_fields(self):
        result = self.aggregate().mechanism_coverage
        for item in (result,) + result.progressions:
            self.assertFalse(any("saving" in f.name or "benefit" in f.name for f in fields(item)))


class ModelAndDiagnosticTests(SuiteCase):
    def test_exact_integer_complete_game_totals(self):
        model = self.aggregate().model_c
        self.assertEqual(len(model.games), 18)
        self.assertEqual((model.ww_count, model.wl_count, model.lw_count, model.ll_count), (18, 0, 0, 0))
        self.assertEqual((model.control_wins, model.control_losses, model.kp0_wins, model.kp0_losses),
                         (18, 0, 18, 0))
        self.assertEqual(model.ww_control_total_us, 2260)
        self.assertEqual(model.ww_kp0_total_us, 2260)
        self.assertEqual(model.ww_total_delta_us, 0)
        self.assertEqual((model.kp0_faster_count, model.control_faster_count, model.tie_count), (0, 0, 18))
        self.assertEqual(len(model.ww_deltas), 18)
        self.assertTrue(all(type(delta) is int and delta == 0 for _, _, delta in model.ww_deltas))

    def test_positive_and_negative_ww_deltas(self):
        archives, audits = _data()[1:]
        for case_id, bias in (("S-WIN", -5), ("S-LOSS", 7)):
            for rep in (1, 2):
                i = _index(case=case_id, repetition=rep)
                archive = replace(archives[i], result=_declared_result(archives[i].case, "K-P0", cost_bias=bias))
                archives = _set(archives, i, archive)
                audits = _set(audits, i, _manual_audit(archive, audits[i].source_identity))
        model = self.aggregate(archives, audits).model_c
        self.assertEqual((model.kp0_faster_count, model.control_faster_count, model.tie_count), (2, 2, 14))
        self.assertEqual(model.ww_total_delta_us, 4)
        self.assertIn(("S-WIN", 1, -5), model.ww_deltas)
        self.assertIn(("S-LOSS", 2, 7), model.ww_deltas)

    def test_diagnostics_retain_exact_timing_context_and_resource_status(self):
        result = self.aggregate()
        self.assertEqual(result.resource_status, "NOT_EVALUATED_IN_SLICE_4")
        self.assertEqual(result.diagnostics.resource_status, "NOT_EVALUATED_IN_SLICE_4")
        self.assertEqual(result.diagnostics.timing_context, audit.TIMING_CONTEXT)
        self.assertIn("OPEN", result.diagnostics.n2_status)
        self.assertIn("OPEN", result.n2_status)
        self.assertEqual(result.effectiveness_status, "NOT_EVALUATED_IN_E1")

    def test_counts_by_variant_are_exact(self):
        diagnostics = self.aggregate().diagnostics
        counts = {c.variant: c for c in diagnostics.by_variant}
        for variant in e1.VARIANTS:
            c = counts[variant]
            self.assertEqual(c.actions_audited, 22)
            self.assertEqual(c.acquisition_audits, 0)
            self.assertEqual(c.p3_checkpoints, 0)
            self.assertEqual(c.oracle_calls, 18 if variant == "K-P0" else 0)
            self.assertEqual(c.oracle_a_evaluated, 18 if variant == "K-P0" else 0)
            self.assertEqual(c.oracle_a_not_evaluated, 0)
        self.assertEqual(counts["K-P0"].setup_flags, 2)
        self.assertEqual(counts["K-P0"].actual_chords, 2)
        self.assertEqual(counts["K-P0"].productive_progressions, 2)

    def test_runner_timings_keep_unmeasured_and_na_separate(self):
        spans = self.aggregate().diagnostics.runner_timings
        validation = next(s for s in spans if s.variant == "CONTROL" and s.name == "v1_execution_validation_ns")
        self.assertEqual(validation.measured_ns, ())
        self.assertEqual(validation.unmeasured_count, 22)
        planner = next(s for s in spans if s.variant == "CONTROL" and s.name == "v1_plan_position_ns")
        self.assertEqual(planner.measured_ns, (11, 11, 11, 11))
        self.assertEqual(planner.not_applicable_count, 18)

    def test_oracle_spans_not_merged_into_runner_spans(self):
        diagnostics = self.aggregate().diagnostics
        self.assertTrue(diagnostics.oracle_timings)
        self.assertFalse(any(41 in s.measured_ns for s in diagnostics.runner_timings))
        self.assertEqual(sum(len(s.measured_ns) for s in diagnostics.oracle_timings), 18)

    def test_nonzero_acquisition_oracle_a_and_phase_d_e_counts(self):
        audits = _data()[2]
        for rep in (1, 2):
            index = _index(repetition=rep)
            checked = audits[index]
            rows = ((1, H, 1, H),)
            certificate = oracles.LocalMineCertificate(
                rows, 1, (0, 0), (1, 0), EMPTY, GameStatus.PLAYING)
            check = oracles.LocalCertificateCheck(
                (1, 0), (0, 0), 1, EMPTY, EMPTY, frozenset({(1, 0)}), 1, ())
            acquisition = harness.AcquisitionAudit(
                certificate, 1, (), (), check, "PASS", "Declared public acquisition",
                EMPTY, frozenset({(1, 0)}))
            oracle_b = oracles.OracleBResult(
                ((1, F, 1, H),), ((3, 0),), ((3, 0),), (), 1, (((3, 0), 0),),
                frozenset({(3, 0)}), EMPTY, Fraction(0), frozenset({(3, 0)}))
            expected = capability.ExactAnalysis(
                oracle_b.unresolved_cells, oracle_b.frontier_cells, oracle_b.unconstrained_cells,
                oracle_b.total_worlds, oracle_b.mine_worlds, oracle_b.G0, oracle_b.G1,
                oracle_b.minimum_risk, oracle_b.minimum_risk_cells)
            b_audits = tuple(audit.OracleBAudit(
                1, phase, frozenset({(1, 0)}), (certificate,), expected, oracle_b,
                "PASS", (), "Declared public representation evidence") for phase in ("D", "E"))
            not_evaluated = audit.OracleAAudit(
                1, harness.OracleCoverage("ORACLE_A_NOT_EVALUATED", 17, 16, "Declared envelope"),
                None, 17, "NOT_EVALUATED", ())
            calls = checked.oracle_calls + (
                oracles.OracleCallDiagnostic(
                    1, "A", "COMPLETE_WORLD_ENUMERATION", "3" * 64, None, 43, 17,
                    "NOT_EVALUATED", "INDEPENDENT BOUNDED ARITHMETIC EVIDENCE", "Declared envelope"),
                oracles.OracleCallDiagnostic(
                    2, "B", "MATERIALIZED_EXACT", "4" * 64, "5" * 64, 47, 1,
                    "EVALUATED", "SHARED-KERNEL REPRESENTATION EVIDENCE", None),
                oracles.OracleCallDiagnostic(
                    3, "B", "MATERIALIZED_LOCAL", "6" * 64, "7" * 64, 53, 1,
                    "EVALUATED", "SHARED-KERNEL REPRESENTATION EVIDENCE", None))
            checked = replace(
                checked, acquisition_audits=(acquisition,), oracle_b_audits=b_audits,
                oracle_a_audits=checked.oracle_a_audits + (not_evaluated,),
                oracle_calls=calls,
                oracle_spans=(audit.OracleDiagnosticSpan(1, "DECLARED_DIAGNOSTICS", 0, 4, "PASS", ()),))
            audits = _set(audits, index, checked)
        result = self.aggregate(audits=audits)
        counts = next(c for c in result.diagnostics.by_variant if c.variant == "K-P0")
        self.assertEqual(counts.acquisition_audits, 2)
        self.assertEqual(counts.oracle_a_evaluated, 18)
        self.assertEqual(counts.oracle_a_not_evaluated, 2)
        self.assertEqual((counts.oracle_b_phase_d, counts.oracle_b_phase_e), (2, 2))
        self.assertEqual(counts.oracle_calls, 24)
        self.assertEqual(sum(s.sample_count for s in result.diagnostics.oracle_timings), 24)
        self.assertEqual(result.suite_status, "PASS")

    def test_failure_and_incomplete_record_counts_are_exact(self):
        audits = self.changed_audit(
            0, discrepancies=("First declared failure", "Second declared failure"), audit_status="FAIL")
        audits = _set(audits, 3, replace(audits[3], audit_status="INCOMPLETE",
                                       incomplete_reasons=("First absent", "Second absent", "Third absent")))
        counts = next(c for c in self.aggregate(audits=audits).diagnostics.by_variant
                      if c.variant == "CONTROL")
        self.assertEqual((counts.failure_records, counts.incomplete_records), (2, 3))
        self.assertEqual((counts.failed_runs, counts.incomplete_runs), (1, 1))

    def test_unmeasured_required_span_count_retained(self):
        index = _index()
        archive = _data()[1][index]
        timing = replace(archive.result.traces[1].timings, k_execution_validation_ns=None)
        archives, audits = self.changed_archive(index, _trace(archive, 1, timings=timing))
        record = audits[index].timings[1]
        record = replace(record, spans=tuple(
            replace(span, coverage="UNMEASURED_REQUIRED") if span.name == "k_execution_validation_ns"
            else span for span in record.spans))
        checked = replace(audits[index], timings=_set(audits[index].timings, 1, record),
                          audit_status="INCOMPLETE", incomplete_reasons=("Required measurement absent",))
        result = self.aggregate(archives, _set(audits, index, checked))
        span = next(s for s in result.diagnostics.runner_timings
                    if s.variant == "K-P0" and s.name == "k_execution_validation_ns")
        self.assertEqual(span.unmeasured_required_count, 1)
        self.assertEqual(span.sample_count, 21)
        self.assertEqual(span.measured_ns, (31,) * 21)
        self.assertEqual(result.suite_status, "INCOMPLETE")

    def test_absent_timing_records_counted_without_fabricated_values(self):
        index = _index()
        checked = _data()[2][index]
        result = self.aggregate(audits=self.changed_audit(
            index, timings=checked.timings[1:], audit_status="INCOMPLETE",
            incomplete_reasons=("Absent timing record",)))
        spans = tuple(s for s in result.diagnostics.runner_timings if s.variant == "K-P0")
        self.assertEqual(len(spans), len(audit._TIMING_BOUNDARIES))
        self.assertTrue(all(s.absent_record_count == 1 for s in spans))
        self.assertEqual(result.suite_status, "INCOMPLETE")

    def test_no_threshold_or_effectiveness_fields(self):
        model = self.aggregate().model_c
        self.assertFalse(any("threshold" in f.name or "qualified" in f.name or "acceptance" in f.name
                             for f in fields(model)))


class StatusAndPurityTests(SuiteCase):
    def test_nested_failure_cannot_be_hidden_by_top_level_pass(self):
        audits = _data()[2]
        for rep in (1, 2):
            index = _index(repetition=rep)
            old = audits[index]
            costs = _set(old.cost_audits, 1, replace(old.cost_audits[1], status="FAIL"))
            audits = _set(audits, index, replace(old, cost_audits=costs))
        result = self.aggregate(audits=audits)
        self.assertEqual(result.suite_status, "FAIL")
        self.assertNotEqual(result.mechanism_coverage.status, "OBSERVED")

    def test_missing_replay_digest_is_incomplete(self):
        audits = _data()[2]
        for rep in (1, 2):
            index = _index(repetition=rep)
            replay = replace(audits[index].replay_audits[1],
                             archived_decision_digest=None, replayed_decision_digest=None)
            audits = _set(audits, index, replace(
                audits[index], replay_audits=_set(audits[index].replay_audits, 1, replay)))
        result = self.aggregate(audits=audits)
        self.assertEqual(result.suite_status, "INCOMPLETE")
        self.assertNotEqual(result.mechanism_coverage.status, "OBSERVED")

    def test_replay_digest_disagreement_fails(self):
        index = _index()
        checked = _data()[2][index]
        replay = replace(checked.replay_audits[1], replayed_decision_digest="f" * 64)
        result = self.aggregate(audits=self.changed_audit(
            index, replay_audits=_set(checked.replay_audits, 1, replay)))
        self.assertEqual(result.suite_status, "FAIL")

    def test_stale_same_key_k_control_cost_binding_fails(self):
        index = _index(variant="K-CONTROL")
        checked = _data()[2][index]
        cost = replace(checked.cost_audits[1], trace_us=12345)
        result = self.aggregate(audits=self.changed_audit(
            index, cost_audits=_set(checked.cost_audits, 1, cost)))
        self.assertEqual(result.suite_status, "FAIL")
        self.assertTrue(any("different archive content" in f for f in result.semantic_failures))

    def test_stale_same_key_k_control_replay_binding_fails(self):
        index = _index(variant="K-CONTROL")
        checked = _data()[2][index]
        replay = replace(checked.replay_audits[1], archived_decision_digest="f" * 64,
                         replayed_decision_digest="f" * 64)
        result = self.aggregate(audits=self.changed_audit(
            index, replay_audits=_set(checked.replay_audits, 1, replay)))
        self.assertEqual(result.suite_status, "FAIL")
        self.assertTrue(any("different archive content" in f for f in result.semantic_failures))

    def test_fail_dominates_incomplete(self):
        audits = self.changed_audit(0, discrepancies=("Declared failure",), audit_status="FAIL")
        audits = _set(audits, 3, replace(audits[3], incomplete_reasons=("Declared missing",),
                                       audit_status="INCOMPLETE"))
        result = self.aggregate(audits=audits)
        self.assertEqual(result.suite_status, "FAIL")
        self.assertTrue(result.semantic_failures)
        self.assertTrue(result.incomplete_reasons)

    def test_incomplete_per_run_never_passes(self):
        audits = _data()[2]
        for index in (0, 3):
            audits = _set(audits, index, replace(audits[index], incomplete_reasons=("Missing field",),
                                                audit_status="INCOMPLETE"))
        self.assertEqual(self.aggregate(audits=audits).suite_status, "INCOMPLETE")

    def test_semantic_pass_does_not_expose_qualification(self):
        result = self.aggregate()
        self.assertEqual(result.suite_status, "PASS")
        self.assertEqual(result.supplement_status, "NOT_REQUIRED")
        for name in ("E1_PASS", "E1_QUALIFIED", "RESEARCH_PASS", "RESEARCH_FAIL", "progression_allowed"):
            self.assertFalse(hasattr(result, name))

    def test_all_forbidden_execution_oracle_and_writer_boundaries_blocked(self):
        _data()
        targets = [
            (execution, "execute_scheduled_entry"), (execution, "_materialize_case"),
            (audit, "audit_scheduled_run"),
            (runner, "run_control_capture"), (runner, "run_k_control"), (runner, "run_k_p0"),
            (core_engine, "MinesweeperEngine"), (execution, "MinesweeperEngine"),
            (benchmark_board, "generate_board"),
            (oracles, "enumerate_public_worlds"), (oracles, "verify_local_certificate"),
            (oracles, "verify_exact_global_certificate"),
            (oracles, "materialized_exact_reference"), (oracles, "collect_oracle_diagnostics"),
            (evaluator, "evaluate_falsification"), (evaluator, "derive_terminal_answer"),
            (evaluator, "verify_bound_finding"), (evaluator, "collect_evaluator_diagnostics"),
            (Path, "write_text"), (Path, "write_bytes"), (Path, "mkdir"),
            (subprocess, "Popen"), (subprocess, "run"),
        ]
        for module in (oracles, harness):
            targets.extend((module, name) for name in vars(module)
                           if callable(getattr(module, name)) and
                           (name.startswith("oracle_") or name.startswith("evaluate_")
                            or name.startswith("persist_") or name.startswith("write_")))
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch.object(
                obj, name, side_effect=AssertionError("Forbidden boundary: " + name)))
                     for obj, name in targets]
            result = self.aggregate()
        self.assertEqual(result.suite_status, "PASS")
        for mock in mocks:
            mock.assert_not_called()

    def test_immutable_result_graph_has_no_live_or_hidden_payload(self):
        result = self.aggregate()
        seen = set()
        def visit(value):
            if id(value) in seen:
                return
            seen.add(id(value))
            self.assertNotIsInstance(value, (list, dict, set))
            self.assertFalse(callable(value))
            self.assertNotIn(type(value).__name__, ("MinesweeperEngine", "BoardSnapshot", "Thread", "Popen"))
            if type(value) in (tuple, frozenset):
                for child in value:
                    visit(child)
            elif is_dataclass(value):
                self.assertTrue(type(value).__dataclass_params__.frozen)
                for field in fields(value):
                    self.assertNotIn(field.name, ("mine_positions", "mines", "answer", "hidden_answer"))
                    visit(getattr(value, field.name))
            else:
                self.assertIsInstance(value, (str, int, float, bool, type(None), Fraction, Enum))
        visit(result)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            result.suite_status = "FAIL"

    def test_mutable_payload_in_archive_rejected(self):
        index = _index()
        archive = _trace(_data()[1][index], 1, M_before=[])
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(archives=_set(_data()[1], index, archive))

    def test_mutable_payload_in_audit_rejected(self):
        with self.assertRaises(suite.E1SuiteError):
            self.aggregate(audits=self.changed_audit(0, cost_audits=[]))

    def test_suite_ast_forbids_execution_persistence_and_qualification(self):
        tree = ast.parse(inspect.getsource(suite))
        forbidden = {"execute_scheduled_entry", "_materialize_case", "audit_scheduled_run",
                     "run_control_capture", "run_k_control", "run_k_p0", "MinesweeperEngine",
                     "generate_board", "execute_e0", "write_text", "write_bytes", "mkdir",
                     "persist", "select_supplement", "Popen"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else "")
                self.assertNotIn(name, forbidden)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotIn(node.value, {"E1_PASS", "E1_QUALIFIED", "RESEARCH_PASS", "RESEARCH_FAIL"})

    def test_new_fixture_does_not_call_execution_analysis_or_audit(self):
        tree = ast.parse(inspect.getsource(_declared_result) + "\n" + inspect.getsource(_manual_audit))
        forbidden = {"execute_scheduled_entry", "audit_scheduled_run", "_materialize_case",
                     "plan_position", "analyze_decision", "select_policy", "generate_board",
                     "MinesweeperEngine", "enumerate_public_worlds"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else "")
                self.assertNotIn(name, forbidden)


if __name__ == "__main__":
    unittest.main()
