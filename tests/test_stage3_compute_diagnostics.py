"""Diagnostic observation preserves production semantics and measures real calls.

Hidden layouts below arrange small engines only. They never enter the diagnostic
planner wrapper; only the runner's existing public inputs cross that boundary.
"""

import ast
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import inspect
import unittest
from unittest.mock import patch

from core_engine import Action, CellState, MinesweeperEngine
import simple_decision
import stage3_compute_diagnostics as diagnostics
from stage3_physical import load_timing_table
import stage3_planner
import stage3_runner
from stage3_telemetry import trace_to_telemetry


H, F = CellState.HIDDEN, CellState.FLAGGED


def fixed_engine(width, height, mines):
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), mines)
    return engine


def semantic_stream(result):
    return tuple(
        (
            trace.move,
            trace.decision,
            trace.cursor_before,
            trace.modeled_action_us,
            trace.status_after,
            trace.safe_cells_opened_delta,
            trace.explicit_flag_delta,
            replace(trace_to_telemetry(trace), decision_compute_ns=None),
        )
        for trace in result.traces
    )


PATCHED_BOUNDARIES = (
    (stage3_runner, "plan_position"),
    (stage3_planner, "analyze_position"),
    (simple_decision, "infer_deterministic"),
    (simple_decision, "calculate_probabilities"),
    (stage3_planner, "generate_reveal_plans"),
    (stage3_planner, "exact_route"),
)


class TimingSummaryTests(unittest.TestCase):
    def test_nearest_rank_known_unsorted_integer_samples(self):
        summary = diagnostics.summarize_samples(range(100, 0, -1))
        self.assertEqual(summary.count, 100)
        self.assertEqual(
            (summary.p50_ns, summary.p90_ns, summary.p95_ns,
             summary.p99_ns, summary.max_ns),
            (50, 90, 95, 99, 100),
        )

    def test_p50_is_nearest_rank_not_average_of_middle_values(self):
        summary = diagnostics.summarize_samples((40, 10, 30, 20))
        self.assertEqual(summary.p50_ns, 20)
        self.assertEqual(summary.p90_ns, 40)
        self.assertEqual(summary.p95_ns, 40)
        self.assertEqual(summary.p99_ns, 40)
        self.assertEqual(summary.max_ns, 40)

    def test_nearest_rank_ceil_and_large_integers_remain_exact(self):
        base = 10 ** 30
        summary = diagnostics.summarize_samples(base + index for index in range(1, 12))
        self.assertEqual(
            (summary.p50_ns, summary.p90_ns, summary.p95_ns,
             summary.p99_ns, summary.max_ns),
            (base + 6, base + 10, base + 11, base + 11, base + 11),
        )
        self.assertIs(type(summary.p99_ns), int)

    def test_empty_is_not_applicable_and_zero_is_a_real_sample(self):
        empty = diagnostics.summarize_samples(())
        zero = diagnostics.summarize_samples((0,))
        self.assertEqual(empty.count, 0)
        self.assertEqual(
            (empty.p50_ns, empty.p90_ns, empty.p95_ns, empty.p99_ns, empty.max_ns),
            (None,) * 5,
        )
        self.assertEqual(zero.count, 1)
        self.assertEqual(
            (zero.p50_ns, zero.p90_ns, zero.p95_ns, zero.p99_ns, zero.max_ns),
            (0,) * 5,
        )

    def test_invalid_or_boolean_samples_are_rejected(self):
        for bad in (True, False, -1, 1.5, "1", None):
            with self.subTest(sample=bad), self.assertRaises((TypeError, ValueError)):
                diagnostics.summarize_samples((3, bad, 7))

    def test_summary_is_immutable(self):
        summary = diagnostics.summarize_samples((1,))
        with self.assertRaises(FrozenInstanceError):
            summary.count = 10


class ComputeDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def plan(self, observation, num_mines):
        return stage3_runner.plan_position(observation, num_mines, (0, 0), self.table)

    def test_returned_decision_is_the_actual_production_object(self):
        observed = []
        original = stage3_runner.plan_position
        observation = [[0, H]]
        reference = original(observation, 0, (0, 0), self.table)

        def production_call(*args, **kwargs):
            result = original(*args, **kwargs)
            observed.append(result)
            return result

        with patch.object(stage3_runner, "plan_position", side_effect=production_call) as call:
            with diagnostics.ComputeDiagnostics() as measured:
                result = self.plan(observation, 0)
            self.assertEqual(call.call_count, 1)
        self.assertIs(result, observed[0])
        self.assertEqual(result, reference)
        self.assertEqual(measured.counts["complete"], 1)

    def test_actual_phase_call_counts_for_each_production_path(self):
        cases = (
            ("local safe", [[0, H]], 0, 0, 1, 2),
            ("local mine fallback", [[1, H, H]], 1, 0, 1, 0),
            ("global safe", [[1, F, H, H]], 1, 1, 1, 2),
            ("probability guess", [[H, H]], 1, 1, 0, 0),
        )
        for name, observation, mines, probability_count, candidate_count, route_count in cases:
            with self.subTest(path=name), ExitStack() as stack:
                original_observation = deepcopy(observation)
                spies = {
                    key: stack.enter_context(patch.object(module, attribute, wraps=getattr(module, attribute)))
                    for key, module, attribute in (
                        ("local_inference", simple_decision, "infer_deterministic"),
                        ("probability_analysis", simple_decision, "calculate_probabilities"),
                        ("candidate_generation", stage3_planner, "generate_reveal_plans"),
                        ("exact_routing", stage3_planner, "exact_route"),
                    )
                }
                with diagnostics.ComputeDiagnostics() as measured:
                    self.plan(observation, mines)
                expected = {
                    "complete": 1, "analysis": 1, "local_inference": 1,
                    "probability_analysis": probability_count,
                    "planner_only": 1, "candidate_generation": candidate_count,
                    "exact_routing": route_count,
                }
                self.assertEqual(measured.counts, expected)
                for key, spy in spies.items():
                    self.assertEqual(measured.counts[key], spy.call_count)
                if name == "local safe":
                    self.assertEqual(tuple(spies["exact_routing"].call_args.args[2]), ())
                self.assertEqual(observation, original_observation)

    def test_no_probability_call_is_absent_not_measured_zero(self):
        with patch.object(simple_decision, "calculate_probabilities", side_effect=AssertionError("unexpected probability")):
            with diagnostics.ComputeDiagnostics() as measured:
                self.plan([[0, H]], 0)
        self.assertEqual(measured.samples["probability_analysis"], ())
        self.assertIsNone(measured.decisions[0].probability_analysis_ns)
        self.assertEqual(measured.summaries()["probability_analysis"].count, 0)
        self.assertIsNone(measured.summaries()["probability_analysis"].p50_ns)

    def test_same_invocation_attribution_and_nested_timing_exactly(self):
        # The direct safe OPEN and the zero-clue OPEN both call exact_route;
        # physical sequences are deduplicated only after these actual calls.
        ticks = (100, 110, 120, 140, 180, 190, 200, 220, 230, 240, 250, 300)
        with patch.object(diagnostics, "perf_counter_ns", side_effect=ticks) as clock:
            with diagnostics.ComputeDiagnostics() as measured:
                self.plan([[0, H]], 0)
        self.assertEqual(clock.call_count, 12)
        self.assertEqual(measured.samples, {
            "complete": (200,), "analysis": (70,), "local_inference": (20,),
            "probability_analysis": (), "planner_only": (130,),
            "candidate_generation": (60,), "exact_routing": (20, 10),
        })
        item = measured.decisions[0]
        self.assertEqual(item.complete_ns - item.analysis_ns, item.planner_only_ns)
        self.assertEqual(item.exact_routing_ns, (20, 10))
        self.assertEqual(item.candidate_generation_ns, 60)
        self.assertLessEqual(sum(item.exact_routing_ns), item.candidate_generation_ns)
        # Routing is already inside candidate generation; their sum is not a phase total.
        self.assertEqual(item.candidate_generation_ns, 60)
        self.assertIsNone(item.probability_analysis_ns)

    def test_real_zero_duration_does_not_turn_absent_calls_into_samples(self):
        with patch.object(diagnostics, "perf_counter_ns", return_value=100):
            with diagnostics.ComputeDiagnostics() as measured:
                self.plan([[0, H]], 0)
        self.assertEqual(measured.samples["complete"], (0,))
        self.assertEqual(measured.samples["local_inference"], (0,))
        self.assertEqual(measured.samples["probability_analysis"], ())

    def test_negative_same_invocation_remainder_fails_without_clamping(self):
        # Every nested elapsed value is positive, but complete < analysis.
        ticks = (100, 110, 120, 140, 180, 190, 200, 220, 230, 240, 250, 160)
        with patch.object(diagnostics, "perf_counter_ns", side_effect=ticks):
            with self.assertRaisesRegex(diagnostics.ComputeDiagnosticsError, "Negative.*remainder"):
                with diagnostics.ComputeDiagnostics() as measured:
                    self.plan([[0, H]], 0)
        self.assertEqual(measured.decisions, ())
        self.assertTrue(all(count == 0 for count in measured.counts.values()))

    def test_missing_nested_analysis_fails_closed(self):
        decision = self.plan([[0, H]], 0)
        with patch.object(stage3_runner, "plan_position", return_value=decision):
            with self.assertRaisesRegex(diagnostics.ComputeDiagnosticsError, "exactly one analysis"):
                with diagnostics.ComputeDiagnostics() as measured:
                    self.plan([[0, H]], 0)
        self.assertEqual(measured.decisions, ())

    def test_missing_local_inference_fails_closed(self):
        evidence = simple_decision.analyze_position([[0, H]], 0)
        with patch.object(stage3_planner, "analyze_position", return_value=evidence):
            with self.assertRaisesRegex(diagnostics.ComputeDiagnosticsError, "local-inference"):
                with diagnostics.ComputeDiagnostics() as measured:
                    self.plan([[0, H]], 0)
        self.assertEqual(measured.decisions, ())

    def test_phase_calls_outside_declared_parent_are_rejected(self):
        evidence = simple_decision.analyze_position([[0, H]], 0)
        calls = (
            lambda: simple_decision.infer_deterministic(evidence.constraints),
            lambda: simple_decision.calculate_probabilities([[H, H]], 1),
            lambda: stage3_planner.generate_reveal_plans([[0, H]], evidence, (0, 0), self.table),
            lambda: stage3_planner.exact_route(self.table, (0, 0), (), evidence.move),
        )
        for call in calls:
            with self.subTest(call=call), diagnostics.ComputeDiagnostics() as measured:
                with self.assertRaisesRegex(diagnostics.ComputeDiagnosticsError, "nested directly"):
                    call()
            self.assertEqual(measured.decisions, ())

    def test_nested_context_cannot_replace_active_instrumentation(self):
        with diagnostics.ComputeDiagnostics() as first:
            current = tuple(getattr(module, name) for module, name in PATCHED_BOUNDARIES)
            with self.assertRaisesRegex(diagnostics.ComputeDiagnosticsError, "one diagnostic context"):
                with diagnostics.ComputeDiagnostics():
                    self.fail("Nested context entered")
            self.assertEqual(tuple(getattr(module, name) for module, name in PATCHED_BOUNDARIES), current)
            self.plan([[0, H]], 0)
        self.assertEqual(first.counts["complete"], 1)

    def test_multiple_decisions_keep_per_invocation_attribution(self):
        with diagnostics.ComputeDiagnostics() as measured:
            self.plan([[0, H]], 0)
            self.plan([[H, H]], 1)
        self.assertEqual(len(measured.decisions), 2)
        first, second = measured.decisions
        self.assertNotEqual(first.invocation_index, second.invocation_index)
        self.assertIsNone(first.probability_analysis_ns)
        self.assertIsNotNone(second.probability_analysis_ns)
        self.assertIsNone(second.candidate_generation_ns)
        self.assertEqual(second.exact_routing_ns, ())
        for item in measured.decisions:
            self.assertEqual(item.planner_only_ns, item.complete_ns - item.analysis_ns)
        self.assertEqual(measured.samples["planner_only"], tuple(item.planner_only_ns for item in measured.decisions))

    def test_real_runner_actions_telemetry_outcomes_and_modeled_cost_match(self):
        fixtures = (
            (4, 1, frozenset({(1, 0)})),
            (5, 1, frozenset({(1, 0), (2, 0)})),
            (6, 4, frozenset({(1, 2), (2, 1), (4, 0), (4, 1), (4, 2)})),
        )
        for width, height, mines in fixtures:
            with self.subTest(dimensions=(width, height), mines=mines):
                reference = stage3_runner.run_stage3(fixed_engine(width, height, mines), table=self.table)
                with diagnostics.ComputeDiagnostics() as measured:
                    instrumented = stage3_runner.run_stage3(fixed_engine(width, height, mines), table=self.table)
                self.assertEqual(instrumented.status, reference.status)
                self.assertEqual(instrumented.moves, reference.moves)
                self.assertEqual(instrumented.total_modeled_us, reference.total_modeled_us)
                self.assertEqual(semantic_stream(instrumented), semantic_stream(reference))
                self.assertEqual(measured.counts["complete"], len(reference.traces) - 1)
                self.assertEqual(measured.counts["local_inference"], len(reference.traces) - 1)
                expected_probability = sum(trace.decision is not None and trace.decision.evidence.probability_result is not None for trace in reference.traces)
                self.assertEqual(measured.counts["probability_analysis"], expected_probability)
        self.assertIn(Action.CHORD, tuple(move.action for move in reference.moves))

    def test_initial_policy_only_game_has_no_planning_populations(self):
        with diagnostics.ComputeDiagnostics() as measured:
            result = stage3_runner.run_stage3(fixed_engine(3, 1, frozenset({(2, 0)})), table=self.table)
        self.assertEqual(len(result.traces), 1)
        self.assertTrue(all(count == 0 for count in measured.counts.values()))
        self.assertTrue(all(summary.p50_ns is None for summary in measured.summaries().values()))

    def test_context_restores_all_boundaries_on_normal_exit(self):
        before = tuple(getattr(module, name) for module, name in PATCHED_BOUNDARIES)
        with diagnostics.ComputeDiagnostics():
            self.plan([[0, H]], 0)
        self.assertEqual(tuple(getattr(module, name) for module, name in PATCHED_BOUNDARIES), before)

    def test_context_restores_all_boundaries_on_solver_or_base_exception(self):
        for error in (ValueError("body"), KeyboardInterrupt(), SystemExit()):
            with self.subTest(error=type(error).__name__):
                before = tuple(getattr(module, name) for module, name in PATCHED_BOUNDARIES)
                with self.assertRaises(type(error)):
                    with diagnostics.ComputeDiagnostics():
                        raise error
                self.assertEqual(tuple(getattr(module, name) for module, name in PATCHED_BOUNDARIES), before)
        before = tuple(getattr(module, name) for module, name in PATCHED_BOUNDARIES)
        with self.assertRaisesRegex(ValueError, "num_mines"):
            with diagnostics.ComputeDiagnostics() as measured:
                self.plan([[0, H]], True)
        self.assertEqual(measured.decisions, ())
        self.assertEqual(tuple(getattr(module, name) for module, name in PATCHED_BOUNDARIES), before)

    def test_physical_validation_still_runs_inside_complete_call(self):
        original = stage3_planner.validate_timing_table
        with patch.object(stage3_planner, "validate_timing_table", wraps=original) as validate:
            with diagnostics.ComputeDiagnostics() as measured:
                self.plan([[0, H]], 0)
        self.assertEqual(validate.call_count, 1)
        self.assertEqual(measured.counts["complete"], 1)

    def test_samples_are_snapshots_and_decision_records_are_immutable(self):
        with diagnostics.ComputeDiagnostics() as measured:
            self.plan([[0, H]], 0)
            snapshot = measured.samples
            self.plan([[H, H]], 1)
        self.assertEqual(len(snapshot["complete"]), 1)
        self.assertEqual(len(measured.samples["complete"]), 2)
        snapshot["complete"] = ()
        self.assertEqual(len(measured.samples["complete"]), 2)
        with self.assertRaises(FrozenInstanceError):
            measured.decisions[0].complete_ns = -1

    def test_source_has_no_hidden_engine_or_database_oracle(self):
        tree = ast.parse(inspect.getsource(diagnostics))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or "").split(".")[0])
        forbidden_imports = {
            "core_engine", "benchmark_board", "board_analyzer", "sqlite3",
            "telemetry_schema", "telemetry_repository", "benchmark_repository",
            "benchmark_runner", "stage3_benchmark_runner", "benchmark_modeled_time",
        }
        self.assertFalse(imports & forbidden_imports)
        forbidden_names = {
            "BoardSnapshot", "get_board_snapshot", "mine_positions", "fingerprint",
            "step", "reset_with_mines", "execute", "executemany", "commit",
            "rollback", "cursor_before", "decision_compute_ns",
        }
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        names.update(node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute))
        self.assertFalse(names & forbidden_names)


if __name__ == "__main__":
    unittest.main()
