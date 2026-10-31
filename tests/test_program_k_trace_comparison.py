"""D4.1 exact pairs. Portable literal models are NOT admitted E1 evidence."""

import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from experiments import program_k_control_trace_adapter as c
from experiments import program_k_trace_adapter as k
from experiments import program_k_trace_comparison as pair


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "results/program_k_research" / k.ACCEPTED_RUN_ID
PROFILE = ROOT / "calibration/stage3_physical_profile_v1.json"
HAS_EVIDENCE = all((ARTIFACT / name).is_file() for name in ("qualification.json", "COMPLETE.json"))


def literal_pair():
    """Handwritten domain fixture; no JSON, Engine, solver, or evidence creation.

    The constructor consumes admitted-model shapes, not byte authentication.
    Fake references below deliberately never enter the authenticated factories.
    """
    def ref(index, typename):
        return k.EvidenceReference(k.QUALIFICATION_SHA256, index, typename)

    provenance = {f.name: "PORTABLE_TEST_ONLY" for f in fields(k.KTraceProvenance)}
    provenance.update(run_id=k.ACCEPTED_RUN_ID, qualification_sha256=k.QUALIFICATION_SHA256,
                      qualification_size=k.QUALIFICATION_SIZE, complete_sha256=k.COMPLETE_SHA256,
                      profile_sha256=k.PROFILE_SHA256, table_sha256=k.TABLE_SHA256, model_id=k.MODEL_ID,
                      source_files=(), historical_runtime=(), scope=k.RESEARCH_SCOPE,
                      no_effectiveness_claim=k.NO_EFFECTIVENESS_CLAIM)
    identity = dict(case_id="S-LIFECYCLE", repetition=1, width=4, height=1, num_mines=1, first_click=(0, 0),
                    board_fingerprint=c.FIXED_CASES[0][-1], source_type="PRE_EXISTING_REGRESSION_FIXTURE",
                    benchmark_set_id=None, board_generator_version=None, seed_scheme=None,
                    game_index=None, seed=None, fixture_id="S-LIFECYCLE", provenance="PORTABLE_TEST_ONLY",
                    permitted_claims=())
    mine = frozenset({(1, 0)})
    empty = frozenset()
    initial = ((-2, -2, -2, -2),)
    cp = c.ControlTraceProvenance(**provenance)
    kp = k.KTraceProvenance(**provenance)
    ci = c.ControlCaseIdentity(**identity, schedule_index=6, variant="CONTROL")
    ki = k.KCaseIdentity(**identity, schedule_index=8, variant="K-P0")
    ca, ka = [], []
    cf = [c.ControlTraceFrame(0, initial, "PLAYING", (0, 0), 0, empty, empty)]
    kf = [k.KTraceFrame(0, initial, "PLAYING", (0, 0), 0, empty, empty, empty)]
    for i, (action, target, row) in enumerate((
            ("OPEN", (0, 0), (1, -2, -2, -2)), ("FLAG", (1, 0), (1, -3, -2, -2)),
            ("OPEN", (2, 0), (1, -3, 1, -2)), ("CHORD", (2, 0), (1, -3, 1, 0)))):
        status = "WON" if i == 3 else "PLAYING"
        ca.append(c.ControlActionView(i, action, target, cf[-1].cursor, 126005, (i + 1) * 126005,
                    status, int(action != "FLAG"), int(action == "FLAG"),
                    ref(100 + i, "stage3_runner.Stage3ActionTrace"),
                    ref(200 + i, "experiments.program_k_evidence.PublicEffectRecord"),
                    ref(300 + i, "experiments.program_k_e1_audit.V1ActionAudit"),
                    ref(400 + i, "experiments.program_k_e1_audit.ModelCCostAudit")))
        cf.append(c.ControlTraceFrame(i + 1, (row,), status, target, (i + 1) * 126005, mine if i else empty, empty))
    for i, (target, cost, row) in enumerate(((0, 126005, (1, -2, -2, -2)),
                                            (2, 180604, (1, -2, 1, -2)), (3, 126005, (1, -3, 1, 0)))):
        status = "WON" if i == 2 else "PLAYING"
        total = kf[-1].cumulative_modeled_us + cost
        ka.append(k.KActionView(i, "OPEN", (target, 0), kf[-1].cursor, cost, total, status,
                    "PORTABLE_TEST_ONLY", kf[-1].logical_mines, mine if i else empty, 1, 0, (),
                    ref(500 + i, "experiments.program_k_runner.KActionTrace"),
                    ref(600 + i, "experiments.program_k_evidence.PublicEffectRecord"), None))
        kf.append(k.KTraceFrame(i + 1, (row,), status, (target, 0), total, mine if i else empty,
                               empty, mine if status == "WON" else empty))

    def run(index, variant, actions):
        offset = 1000 + index * 10
        return c.RecordedRunIdentity(index, variant, f"SCHEDULED_RUN:{index:02d}", str(index) * 64, 123,
                    ref(offset, "experiments.program_k_e1_operational.E1OperationResult"),
                    ref(offset + 1, "experiments.program_k_e1_execution.E1ScheduledRunArchive"),
                    ref(offset + 2, "experiments.program_k_runner." + ("ControlCaptureResult" if variant == "CONTROL" else "KRunResult")),
                    ref(offset + 3, "experiments.program_k_e1_audit.E1RunAudit"),
                    ref(700, "experiments.program_k_e1_harness.SealedCaseRegistration"),
                    ref(701, "experiments.program_k_e1_execution.CaseMaterializationReceipt"),
                    tuple(a.trace for a in actions), tuple(a.effect for a in actions))

    control = c.ControlTracePresentation(cp, ci, run(6, "CONTROL", ca), tuple(ca), tuple(cf),
                    k.TerminalAnswerReference(mine, ci.board_fingerprint, ca[-1].effect),
                    ref(702, "experiments.program_k_harness.GuessCheckpointAudit"), "0" * 64)
    kp0 = k.KTracePresentation(kp, ki, tuple(ka), tuple(kf),
                               k.TerminalAnswerReference(mine, ki.board_fingerprint, ka[-1].effect))
    return pair.ProgramKComparisonPair(control, kp0, run(8, "K-P0", ka))


class PortablePairTests(unittest.TestCase):
    def setUp(self):
        self.pair = literal_pair()

    def reject(self, **changes):
        with self.assertRaises(pair.TraceComparisonError):
            replace(self.pair, **changes)

    def test_literal_fixture_has_separate_types_and_exact_facts(self):
        p = self.pair
        self.assertIs(type(p.control), c.ControlTracePresentation)
        self.assertIs(type(p.kp0), k.KTracePresentation)
        self.assertEqual((p.control_facts.total_inputs, p.kp0_facts.total_inputs), (4, 3))
        self.assertEqual((p.difference.total_inputs, p.difference.flag_inputs, p.difference.model_c_us), (-1, -1, -71406))
        self.assertEqual((p.control_facts.explicit_physical_flags, p.kp0_facts.explicit_physical_flags), (1, 0))
        self.assertEqual((p.control_facts.automatic_win_flags, p.kp0_facts.automatic_win_flags), (0, 1))

    def test_constructor_keeps_d1_object_and_knowledge_unchanged(self):
        p = self.pair
        clone = pair.ProgramKComparisonPair(p.control, p.kp0, p.kp0_run)
        self.assertIs(clone.kp0, p.kp0)
        self.assertIs(clone.kp0.frames, p.kp0.frames)
        self.assertEqual(clone.kp0.frame(2).hidden_logical_mines, frozenset({(1, 0)}))
        self.assertFalse(hasattr(clone.control.frame(2), "logical_mines"))

    def test_wrong_control_schedule_and_k_schedule_rejected(self):
        p = self.pair
        for index in (7, 8, 9, 12, True, 6.0):
            self.reject(control=replace(p.control, case=replace(p.control.case, schedule_index=index)))
        for index in (6, 7, 11, 14, True, 8.0):
            self.reject(kp0=replace(p.kp0, case=replace(p.kp0.case, schedule_index=index)))

    def test_repetition_and_variant_mismatch_rejected(self):
        p = self.pair
        for value in (2, True, 1.0):
            self.reject(control=replace(p.control, case=replace(p.control.case, repetition=value)))
            self.reject(kp0=replace(p.kp0, case=replace(p.kp0.case, repetition=value)))
        self.reject(control=replace(p.control, case=replace(p.control.case, variant="K-CONTROL")))
        self.reject(kp0=replace(p.kp0, case=replace(p.kp0.case, variant="K-CONTROL")))
        self.reject(control=replace(p.control, provenance=replace(p.control.provenance, variant="K-CONTROL")))

    def test_case_geometry_first_click_and_fixture_mismatch_rejected(self):
        for name, value in (("case_id", "S-LOSS"), ("width", 5), ("height", 2), ("num_mines", 2),
                            ("first_click", (2, 0)), ("source_type", "DIFFERENT"), ("fixture_id", "OTHER"),
                            ("benchmark_set_id", "OTHER"), ("seed", 1), ("game_index", 1),
                            ("provenance", "OTHER"), ("board_fingerprint", "0" * 64)):
            with self.subTest(field=name):
                self.reject(kp0=replace(self.pair.kp0, case=replace(self.pair.kp0.case, **{name: value})))

    def test_historical_source_and_model_profile_mismatch_rejected(self):
        for name in ("execution_source_digest", "audit_source_digest", "plan_source_digest", "qualification_sha256",
                     "complete_sha256", "profile_sha256", "table_sha256", "model_id"):
            with self.subTest(field=name):
                self.reject(kp0=replace(self.pair.kp0, provenance=replace(self.pair.kp0.provenance, **{name: "other"})))

    def test_terminal_layout_and_reference_mismatch_rejected(self):
        p = self.pair
        for changes in (dict(mines=frozenset({(2, 0)})), dict(board_fingerprint="0" * 64),
                        dict(terminal_effect=p.kp0.actions[0].effect)):
            self.reject(kp0=replace(p.kp0, answer_reference=replace(p.kp0.answer_reference, **changes)))

    def test_operations_results_and_payloads_must_be_distinct(self):
        p = self.pair
        for field in ("operation_id", "operation", "archive", "result", "audit", "payload_sha256"):
            self.reject(kp0_run=replace(p.kp0_run, **{field: getattr(p.control.run, field)}))

    def test_same_registration_and_materialization_references_required(self):
        p = self.pair
        for field in ("registration", "materialization"):
            ref = getattr(p.kp0_run, field)
            self.reject(kp0_run=replace(p.kp0_run, **{field: replace(ref, node_index=999)}))

    def test_run_references_must_bind_admitted_actions(self):
        p = self.pair
        self.reject(kp0_run=replace(p.kp0_run, traces=tuple(reversed(p.kp0_run.traces))))
        self.reject(kp0_run=replace(p.kp0_run, effects=p.kp0_run.effects[:-1]))
        self.reject(kp0_run=replace(p.kp0_run, operation=replace(p.kp0_run.operation, artifact_sha256="0" * 64)))
        self.reject(kp0_run=replace(p.kp0_run, payload_size=0))

    def test_partial_physical_traces_rejected(self):
        p = self.pair
        self.reject(kp0=replace(p.kp0, frames=p.kp0.frames[:-1]))
        self.reject(control=replace(p.control, actions=p.control.actions[:-1]))
        self.reject(kp0=replace(p.kp0, frames=()))
        bad_final = replace(p.kp0.frames[-1], status="PLAYING")
        self.reject(kp0=replace(p.kp0, frames=p.kp0.frames[:-1] + (bad_final,)))

    def test_invalid_nested_action_frame_and_cost_types_fail_closed(self):
        p = self.pair
        self.reject(kp0=replace(p.kp0, actions=(1,) + p.kp0.actions[1:]))
        self.reject(kp0=replace(p.kp0, frames=(1,) + p.kp0.frames[1:]))
        for cost in (True, "126005"):
            action = replace(p.kp0.actions[0], modeled_action_us=cost)
            self.reject(kp0=replace(p.kp0, actions=(action,) + p.kp0.actions[1:]))

    def test_action_order_cursor_and_cumulative_tamper_rejected(self):
        p = self.pair
        for changes in (dict(input_index=99), dict(cursor_before=(3, 0)), dict(cumulative_modeled_us=1),
                        dict(modeled_action_us=0), dict(action="UNKNOWN")):
            changed = replace(p.kp0.actions[1], **changes)
            self.reject(kp0=replace(p.kp0, actions=(p.kp0.actions[0], changed, p.kp0.actions[2])))

    def test_deep_immutability_including_no_mutable_nested_inputs(self):
        p = self.pair
        for value in (p, p.identity, p.control_facts, p.kp0_facts, p.difference, p.kp0_run):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)
        self.reject(kp0=replace(p.kp0, actions=list(p.kp0.actions)))
        self.reject(control=replace(p.control, frames=list(p.control.frames)))
        self.reject(kp0=replace(p.kp0, answer_reference=replace(p.kp0.answer_reference, mines={(1, 0)})))

    def test_fake_k_control_object_not_coerced_or_accepted(self):
        self.reject(control=self.pair.kp0)
        self.reject(kp0=self.pair.control)
        self.reject(kp0_run=object())

    def test_queries_and_independent_frame_access_need_no_files(self):
        with patch.object(Path, "open", side_effect=AssertionError("No navigation IO")):
            p = self.pair
            for i in range(len(p.control.frames)):
                self.assertEqual(p.control.frame(i).index, i)
                self.assertEqual(len(p.control.completed_route(i)), i)
                self.assertEqual(p.kp0.frame(0).index, 0)
            self.assertEqual((p.identity.case_id, p.difference.direction), ("S-LIFECYCLE", "K-P0 minus CONTROL"))
            self.assertFalse(any(hasattr(p, name) for name in ("playhead", "progress", "seek", "clock")))

    def test_public_byte_factory_never_accepts_literal_models_or_corrupt_bytes(self):
        for data in ((b"", b"", b""), (self.pair, b"", b"")):
            with self.assertRaises(pair.TraceComparisonError):
                pair.project_accepted_e1_pairs(*data)

    def test_module_imports_only_two_adapters_and_stdlib(self):
        tree = ast.parse(Path(pair.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                if node.module == "experiments":
                    self.assertLessEqual({a.name for a in node.names}, {"program_k_control_trace_adapter", "program_k_trace_adapter"})
                else:
                    self.assertIn(node.module.split(".")[0], sys.stdlib_module_names)
            elif isinstance(node, ast.Import):
                self.assertTrue(all(a.name.split(".")[0] in sys.stdlib_module_names for a in node.names))


@unittest.skipUnless(HAS_EVIDENCE, "Accepted E1 archive absent; never regenerate evidence.")
class AcceptedPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ((ARTIFACT / "qualification.json").read_bytes(),
                    (ARTIFACT / "COMPLETE.json").read_bytes(), PROFILE.read_bytes())
        cls.pairs = pair.project_accepted_e1_pairs(*cls.data)

    def test_all_four_exact_pairs_and_fingerprints(self):
        for p, fixed in zip(self.pairs, c.FIXED_CASES, strict=True):
            index, case_id, w, h, n, fp = fixed
            self.assertEqual(p.identity, pair.ComparisonPairIdentity(k.ACCEPTED_RUN_ID, case_id, 1, index, index + 2, w, h, n, (0, 0), fp))
            self.assertEqual(p.control.answer_reference.mines, p.kp0.answer_reference.mines)
            self.assertEqual(p.control.run.registration, p.kp0_run.registration)
            self.assertEqual(p.control.run.materialization, p.kp0_run.materialization)
            self.assertNotEqual(p.control.run.operation, p.kp0_run.operation)
            self.assertNotEqual(p.control.run.result, p.kp0_run.result)

    def test_exact_per_side_counts_outcomes_model_c_and_deltas(self):
        expected = (
            ((4, 2, 1, 1, 504020, "WON"), (3, 3, 0, 0, 432614, "WON"), (-1, 1, -1, -1, -71406)),
            ((15, 5, 5, 5, 2469364, "WON"), (14, 8, 2, 4, 2382644, "WON"), (-1, 3, -3, -1, -86720)),
            ((3, 2, 1, 0, 378015, "LOST"), (2, 2, 0, 0, 306609, "LOST"), (-1, 0, -1, 0, None)),
            ((227, 42, 99, 86, 39987084, "WON"), (180, 75, 48, 57, 31586418, "WON"), (-47, 33, -51, -29, -8400666)),
        )
        for p, (cf, kf, delta) in zip(self.pairs, expected, strict=True):
            for facts, expected_facts in ((p.control_facts, cf), (p.kp0_facts, kf)):
                self.assertEqual((facts.total_inputs, facts.open_inputs, facts.flag_inputs, facts.chord_inputs,
                                  facts.model_c_total_us, facts.outcome), expected_facts)
                self.assertEqual(facts.explicit_physical_flags, facts.flag_inputs)
            d = p.difference
            self.assertEqual((d.total_inputs, d.open_inputs, d.flag_inputs, d.chord_inputs, d.model_c_us), delta)
            self.assertEqual(d.label, "Recorded difference for this preserved case")

    def test_loss_keeps_termination_diagnostics_but_no_comparative_model_c_delta(self):
        loss = self.pairs[2]
        self.assertEqual((loss.control_facts.model_c_total_us, loss.kp0_facts.model_c_total_us), (378015, 306609))
        self.assertIsNone(loss.difference.model_c_us)
        self.assertIn("N/A", loss.difference.model_c_applicability)

    def test_factory_retains_original_d1_objects_without_reprojection_or_mutation(self):
        original = k.project_accepted_e1_traces(*self.data, schedule_indices=pair.K_PAIR_INDICES)
        with patch.object(k, "project_accepted_e1_traces", return_value=original) as project:
            result = pair.project_accepted_e1_pairs(*self.data)
        project.assert_called_once_with(*self.data, schedule_indices=(8, 14, 20, 26))
        for p, view in zip(result, original, strict=True):
            self.assertIs(p.kp0, view)
            self.assertIs(p.kp0.actions, view.actions)
            self.assertIs(p.kp0.frames, view.frames)

    def test_wrong_pair_order_fails_closed(self):
        p, other = self.pairs[:2]
        with self.assertRaises(pair.TraceComparisonError):
            pair.ProgramKComparisonPair(p.control, other.kp0, other.kp0_run)

    def test_late_k_admission_failure_publishes_no_partial_pairs(self):
        with patch.object(k, "project_accepted_e1_traces", side_effect=k.KTraceAdapterError("K failed")), self.assertRaisesRegex(
                pair.TraceComparisonError, "K failed"):
            pair.project_accepted_e1_pairs(*self.data)

    def test_late_control_admission_failure_publishes_no_partial_pairs(self):
        original = c._project_run
        def project(*args):
            if args[2] == 24:
                raise c.ControlTraceAdapterError("fourth CONTROL failed")
            return original(*args)
        with patch.object(c, "_project_run", side_effect=project), patch.object(k, "project_accepted_e1_traces") as kp0:
            with self.assertRaisesRegex(pair.TraceComparisonError, "fourth CONTROL failed"):
                pair.project_accepted_e1_pairs(*self.data)
            kp0.assert_not_called()

    def test_late_pair_mismatch_returns_no_partial_collection(self):
        admitted = tuple(p.kp0 for p in self.pairs)
        bad = replace(admitted[-1], case=replace(admitted[-1].case, seed=1))
        with patch.object(k, "project_accepted_e1_traces", return_value=admitted[:-1] + (bad,)), self.assertRaises(pair.TraceComparisonError):
            pair.project_accepted_e1_pairs(*self.data)

    def test_loader_reads_each_input_once_and_no_navigation_io(self):
        original = k._read_bounded
        calls = []
        def read(path, size):
            calls.append(Path(path).resolve())
            return original(path, size)
        with patch.object(k, "_read_bounded", side_effect=read):
            result = pair.load_accepted_e1_pairs(ARTIFACT)
        self.assertEqual(calls, [(ARTIFACT / "qualification.json").resolve(), (ARTIFACT / "COMPLETE.json").resolve(), PROFILE.resolve()])
        with patch.object(Path, "open", side_effect=AssertionError("Unexpected navigation access")):
            for p in result:
                self.assertEqual(len(p.control.completed_route(len(p.control.actions))), p.control_facts.total_inputs)
                self.assertEqual(len(p.kp0.completed_route(len(p.kp0.actions))), p.kp0_facts.total_inputs)
                self.assertEqual(p.identity.board_fingerprint, p.control.case.board_fingerprint)


if __name__ == "__main__":
    unittest.main()
