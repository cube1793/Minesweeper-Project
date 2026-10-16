"""Pure solver-only transport validation and parent-side Human composition."""

from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from core_engine import GameStatus, MinesweeperEngine
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from same_board_comparison import HumanComparisonContext
from same_board_runner import (
    ComparisonExecutionError, SolverExecution, compose_same_board_execution,
    run_fixed_layout_solvers, run_same_board_comparison,
)
from tests.test_same_board_runner import human_context


def round_trip(value):
    return pickle.loads(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))


class SolverTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = human_context(with_trace=True)
        cls.execution = run_fixed_layout_solvers(cls.context.layout.board)

    def test_solver_only_result_is_immutable_and_has_no_human_or_benchmark_fields(self):
        self.assertIs(type(self.execution), SolverExecution)
        self.assertIs(self.execution.layout.board, self.context.layout.board)
        self.assertEqual(self.execution.layout, self.context.layout)
        self.assertEqual({item.name for item in fields(self.execution)}, {
            "layout", "stage2_result", "stage2_traces", "stage3_result",
            "model_c_evaluation", "stage2_metrics", "stage3_metrics",
        })
        with self.assertRaises(FrozenInstanceError):
            self.execution.layout = None
        self.assertEqual(round_trip(self.execution), self.execution)

    def test_composition_retains_original_parent_context_and_native_solver_objects(self):
        transported = round_trip(self.execution)
        with patch("same_board_runner.run_simple", side_effect=AssertionError("rerun")), \
             patch("same_board_runner.run_stage3", side_effect=AssertionError("rerun")):
            result = compose_same_board_execution(self.context, transported)
        self.assertIs(result.context, self.context)
        self.assertIs(result.context.human_replay, self.context.human_replay)
        self.assertIs(result.context.human_replay.mouse_trace, self.context.human_replay.mouse_trace)
        self.assertIs(result.stage2_result, transported.stage2_result)
        self.assertIs(result.stage2_traces, transported.stage2_traces)
        self.assertIs(result.stage3_result, transported.stage3_result)
        self.assertEqual(result.human_metrics.replay_elapsed_seconds, 12.5)
        self.assertEqual(result.stage2_metrics, transported.stage2_metrics)
        self.assertEqual(result.stage3_metrics, transported.stage3_metrics)

    def test_probability_decisions_survive_solver_only_transport_and_composition(self):
        board = ReplayBoard(2, 2, 1, {(1, 1)})
        context = HumanComparisonContext(ReplayData(board, (
            ReplayEvent(0, 0, 0, "OPEN"), ReplayEvent(1, 1, 0, "OPEN"), ReplayEvent(2, 0, 1, "OPEN"),
        )), declared_full_game_human=True)
        execution = run_fixed_layout_solvers(board)
        result = compose_same_board_execution(context, round_trip(execution))
        stage2_probability = result.stage2_traces[1].decision.probability_result
        stage3_probability = result.stage3_result.traces[1].decision.evidence.probability_result
        self.assertIsNotNone(stage2_probability)
        self.assertIsNotNone(stage3_probability)
        self.assertEqual(stage2_probability, execution.stage2_traces[1].decision.probability_result)
        self.assertEqual(stage3_probability, execution.stage3_result.traces[1].decision.evidence.probability_result)
        self.assertIs(result.context, context)

    def test_synchronous_api_delegates_only_the_board_and_keeps_accepted_result_shape(self):
        with patch("same_board_runner.run_fixed_layout_solvers", return_value=self.execution) as run:
            result = run_same_board_comparison(self.context)
        run.assert_called_once_with(self.context.layout.board)
        self.assertEqual(result, compose_same_board_execution(self.context, self.execution))

    def test_composition_requires_native_solver_result_and_admitted_context(self):
        for context, execution in ((None, self.execution), (self.context.human_replay, self.execution),
                                   (self.context, None), (self.context, {})):
            with self.subTest(context=type(context), execution=type(execution)), \
                 self.assertRaises(ComparisonExecutionError):
                compose_same_board_execution(context, execution)

    def test_execution_for_another_layout_cannot_attach_to_human_context(self):
        with self.assertRaisesRegex(ComparisonExecutionError, "layout"):
            compose_same_board_execution(human_context(mined_origin=True), self.execution)

    def test_fingerprint_is_recomputed_instead_of_trusting_pickled_field(self):
        execution = round_trip(self.execution)
        object.__setattr__(execution.layout, "board_fingerprint", "invented")
        with self.assertRaisesRegex(ComparisonExecutionError, "layout"):
            compose_same_board_execution(self.context, execution)

    def test_model_authentication_is_local_and_serialized_model_tampering_fails_closed(self):
        for corruption in ("table_value", "float_table", "mutable_table", "cursor", "version", "digest"):
            execution = round_trip(self.execution)
            model = execution.model_c_evaluation
            table = model.table
            if corruption == "table_value":
                object.__setattr__(model, "table", ((table[0][0] + 1, *table[0][1:]), *table[1:]))
            elif corruption == "float_table":
                object.__setattr__(model, "table", ((float(table[0][0]), *table[0][1:]), *table[1:]))
            elif corruption == "mutable_table":
                object.__setattr__(model, "table", [list(row) for row in table])
            elif corruption == "cursor":
                object.__setattr__(model, "initial_cursor", (False, 0))
            elif corruption == "version":
                object.__setattr__(model, "physical_profile_version", float(model.physical_profile_version))
            else:
                object.__setattr__(model, "timing_table_sha256", "invented")
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                compose_same_board_execution(self.context, execution)
        with patch("same_board_runner.authenticate_model_c", side_effect=ValueError("local authentication")):
            with self.assertRaisesRegex(ValueError, "local authentication"):
                compose_same_board_execution(self.context, self.execution)

    def test_transported_summaries_are_checked_against_native_streams(self):
        for name in ("stage2_metrics", "stage3_metrics"):
            metrics = getattr(self.execution, name)
            for altered in (
                replace(metrics, model_c_total_us=metrics.model_c_total_us + 1),
                replace(metrics, decision_compute_total_ns=metrics.decision_compute_total_ns + 1),
                replace(metrics, outcome=GameStatus.LOST),
                replace(metrics, outcome=int(metrics.outcome)),
                replace(metrics, actions=replace(metrics.actions, flag_input_count=True)),
                replace(metrics, actions=replace(metrics.actions, open_count=float(metrics.actions.open_count))),
            ):
                with self.subTest(name=name, altered=altered), self.assertRaisesRegex(ComparisonExecutionError, "metrics"):
                    compose_same_board_execution(self.context, replace(self.execution, **{name: altered}))

    def test_decision_types_and_shallow_native_shapes_are_checked(self):
        # Decision internals are retained trusted-local evidence, not recursively
        # revalidated. Their native boundary types and relationships still matter.
        for corruption in ("stage2_decision", "stage3_decision", "evidence_type", "plan_type", "extra", "cycle"):
            execution = round_trip(self.execution)
            decision = execution.stage3_result.traces[1].decision
            if corruption == "stage2_decision":
                object.__setattr__(execution.stage2_traces[1], "decision", MinesweeperEngine(1, 1, 0))
            elif corruption == "stage3_decision":
                object.__setattr__(execution.stage3_result.traces[1], "decision", MinesweeperEngine(1, 1, 0))
            elif corruption == "evidence_type":
                object.__setattr__(decision, "evidence", MinesweeperEngine(1, 1, 0))
            elif corruption == "plan_type":
                object.__setattr__(decision, "plan", MinesweeperEngine(1, 1, 0))
            elif corruption == "extra":
                object.__setattr__(execution.stage2_result, "engine", MinesweeperEngine(1, 1, 0))
            else:
                object.__setattr__(decision, "evidence", decision)
            with self.subTest(corruption=corruption), self.assertRaises(ComparisonExecutionError):
                compose_same_board_execution(self.context, execution)

    def test_relied_upon_native_objects_reject_unexpected_attributes(self):
        selectors = (
            lambda e: e, lambda e: e.layout, lambda e: e.layout.board,
            lambda e: e.stage2_result, lambda e: e.stage2_result.replay_data,
            lambda e: e.stage2_result.replay_data.events[0],
            lambda e: e.stage2_traces[0], lambda e: e.stage2_traces[0].move,
            lambda e: e.stage2_traces[1].decision,
            lambda e: e.stage3_result, lambda e: e.stage3_result.traces[0],
            lambda e: e.stage3_result.traces[1].decision,
            lambda e: e.stage3_result.traces[1].decision.evidence,
            lambda e: e.model_c_evaluation,
            lambda e: e.stage2_metrics, lambda e: e.stage2_metrics.actions,
            lambda e: e.stage3_metrics, lambda e: e.stage3_metrics.actions,
        )
        for select in selectors:
            execution = round_trip(self.execution)
            target = select(execution)
            object.__setattr__(target, "unexpected", "extra")
            with self.subTest(native_type=type(target)), self.assertRaises(ComparisonExecutionError):
                compose_same_board_execution(self.context, execution)

    def test_both_trace_deltas_require_exact_nonnegative_integers(self):
        for stage in (2, 3):
            for name in ("safe_cells_opened_delta", "explicit_flag_delta"):
                for value in (True, False, -1, 0.0, 1.0, None, "0"):
                    execution = round_trip(self.execution)
                    trace = execution.stage2_traces[0] if stage == 2 else execution.stage3_result.traces[0]
                    object.__setattr__(trace, name, value)
                    with self.subTest(stage=stage, field=name, value=value), \
                         self.assertRaisesRegex(ComparisonExecutionError, "deltas"):
                        compose_same_board_execution(self.context, execution)

    def test_cursor_requires_exact_in_bounds_integer_pair(self):
        board = self.context.layout.board
        for value in ((False, 0), (0, False), (0.0, 0), (0, 0.0), [0, 0],
                      (0,), (0, 0, 0), (-1, 0), (board.width, 0), (0, board.height)):
            execution = round_trip(self.execution)
            object.__setattr__(execution.stage3_result.traces[0], "cursor_before", value)
            with self.subTest(value=value), self.assertRaisesRegex(ComparisonExecutionError, "Coordinate"):
                compose_same_board_execution(self.context, execution)

    def test_validly_typed_cursor_still_must_follow_executed_chain(self):
        execution = round_trip(self.execution)
        object.__setattr__(execution.stage3_result.traces[1], "cursor_before", (2, 0))
        with self.assertRaisesRegex(ComparisonExecutionError, "cursor"):
            compose_same_board_execution(self.context, execution)

    def test_native_trace_decision_and_move_types_cannot_be_replaced_by_lookalikes(self):
        from types import SimpleNamespace
        for stage in (2, 3):
            execution = round_trip(self.execution)
            trace = execution.stage2_traces[1] if stage == 2 else execution.stage3_result.traces[1]
            object.__setattr__(trace, "move", SimpleNamespace(**vars(trace.move)))
            with self.subTest(stage=stage), self.assertRaises(ComparisonExecutionError):
                compose_same_board_execution(self.context, execution)

    def test_stage2_native_stream_and_terminal_status_are_reconstructed_after_transport(self):
        for corruption in ("missing", "false_loss", "trailing"):
            execution = round_trip(self.execution)
            result = execution.stage2_result
            traces = execution.stage2_traces
            if corruption == "missing":
                execution = replace(execution, stage2_traces=traces[:-1])
            elif corruption == "false_loss":
                from simple_runner import StopReason
                execution = replace(execution,
                    stage2_result=replace(result, status=GameStatus.LOST, stop_reason=StopReason.LOST),
                    stage2_traces=(*traces[:-1], replace(traces[-1], status_after=GameStatus.LOST)))
            else:
                replay = replace(result.replay_data, events=(*result.replay_data.events, result.replay_data.events[-1]))
                execution = replace(execution, stage2_result=replace(result, moves=(*result.moves, result.moves[-1]),
                                                                     replay_data=replay),
                                    stage2_traces=(*traces, traces[-1]))
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                compose_same_board_execution(self.context, execution)

    def test_stage3_reconstruction_and_each_recorded_cost_are_checked(self):
        result = self.execution.stage3_result
        for changed in (
            replace(result, status=GameStatus.LOST, traces=(
                *result.traces[:-1], replace(result.traces[-1], status_after=GameStatus.LOST))),
            replace(result, traces=(replace(result.traces[0], modeled_action_us=result.traces[0].modeled_action_us + 1),
                                    replace(result.traces[1], modeled_action_us=result.traces[1].modeled_action_us - 1),
                                    *result.traces[2:])),
        ):
            with self.subTest(changed=changed), self.assertRaises(ComparisonExecutionError):
                compose_same_board_execution(self.context, replace(self.execution, stage3_result=changed))

    def test_unpickled_stage2_replay_is_revalidated_without_changing_replay_semantics(self):
        for corruption in ("nan_elapsed", "mutable_events", "human_label"):
            execution = round_trip(self.execution)
            replay = execution.stage2_result.replay_data
            if corruption == "nan_elapsed":
                object.__setattr__(replay.events[0], "elapsed_time", float("nan"))
            elif corruption == "mutable_events":
                object.__setattr__(replay, "events", list(replay.events))
            else:
                object.__setattr__(replay, "source_type", "human")
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                compose_same_board_execution(self.context, execution)

    def test_unpickled_board_validation_precedes_solver_execution(self):
        for name, value in (("width", True), ("width", 31), ("height", 17), ("num_mines", 0),
                            ("mine_positions", frozenset({(100, 0)})), ("mine_positions", {(1, 0)})):
            board = round_trip(self.context.layout.board)
            object.__setattr__(board, name, value)
            with self.subTest(name=name, value=value), patch("same_board_runner.run_simple") as runner:
                with self.assertRaises(ValueError):
                    run_fixed_layout_solvers(board)
                runner.assert_not_called()


class FullSizeSolverTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from benchmark_board import EXPERT_GENERAL_V1, generate_board
        from same_board_execution_worker import WORKER_SCRIPT

        # Reuse a deterministic full-size fixture, transporting only its board.
        # Benchmark identity is neither requested from nor returned by the worker.
        mines = generate_board(EXPERT_GENERAL_V1, 0).mine_positions
        board = ReplayBoard(30, 16, 99, mines)
        mine = min(mines, key=lambda cell: (cell[1], cell[0]))
        cls.context = HumanComparisonContext(ReplayData(board, (
            ReplayEvent(1.25, *mine, "OPEN"),
        )), declared_full_game_human=True)
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        root = Path(directory.name)
        payload, result = root / "payload.pkl", root / "result.pkl"
        payload.write_bytes(pickle.dumps({"token": 1, "board": board}))
        completed = subprocess.run(
            [sys.executable, "-B", "-S", WORKER_SCRIPT, str(payload), str(result)],
            cwd=root, capture_output=True, text=True, timeout=60,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)
        envelope = pickle.loads(result.read_bytes())
        if envelope["error"] is not None:
            raise AssertionError(envelope["error"])
        cls.execution = envelope["solver_execution"]

    def test_genuine_full_size_worker_evidence_is_accepted_without_replacement(self):
        execution = self.execution
        self.assertIs(type(execution), SolverExecution)
        self.assertEqual((execution.layout.board.width, execution.layout.board.height), (30, 16))
        # Qualify the fixture: substantial native inference, probability and plans,
        # rather than a full-size board that loses after a single canonical input.
        self.assertGreater(len(execution.stage2_traces), 100)
        self.assertGreater(len(execution.stage3_result.traces), 100)
        self.assertTrue(any(t.decision and t.decision.probability_result for t in execution.stage2_traces))
        self.assertTrue(any(t.decision and t.decision.evidence.probability_result
                            for t in execution.stage3_result.traces))
        self.assertTrue(any(t.decision and t.decision.plan for t in execution.stage3_result.traces))
        result = compose_same_board_execution(self.context, execution)
        self.assertIs(result.context, self.context)
        self.assertIs(result.stage2_result, execution.stage2_result)
        self.assertIs(result.stage2_traces, execution.stage2_traces)
        self.assertIs(result.stage3_result, execution.stage3_result)
        self.assertEqual(result.stage2_metrics.outcome, GameStatus.WON)
        self.assertEqual(result.stage3_metrics.outcome, GameStatus.WON)

    def test_composition_does_not_visit_nested_decision_evidence(self):
        from simple_algorithm import Constraint, InferenceResult
        from simple_decision import SimpleDecision
        from simple_probability import CellProbability, ProbabilityResult
        from stage3_planner import RevealPlan

        def forbidden(instance, name):
            raise AssertionError(f"Parent traversed {type(instance).__name__}.{name}")

        def shallow_decision(instance, name):
            if name in {"constraints", "deterministic_result", "probability_result"}:
                return forbidden(instance, name)
            return object.__getattribute__(instance, name)

        def shallow_plan(instance, name):
            if name in {"actions", "latency_us", "reveals"}:
                return forbidden(instance, name)
            return object.__getattribute__(instance, name)

        # Structural performance guard, not a machine-specific latency threshold:
        # any recursive walk of this genuine native graph fails at its boundary.
        # The evidence itself is neither changed nor removed from the result.
        with ExitStack() as stack:
            for native in (Constraint, InferenceResult, CellProbability, ProbabilityResult):
                stack.enter_context(patch.object(native, "__getattribute__", forbidden))
            stack.enter_context(patch.object(SimpleDecision, "__getattribute__", shallow_decision))
            stack.enter_context(patch.object(RevealPlan, "__getattribute__", shallow_plan))
            result = compose_same_board_execution(self.context, self.execution)
        self.assertIs(result.stage2_traces, self.execution.stage2_traces)
        self.assertIs(result.stage3_result, self.execution.stage3_result)


if __name__ == "__main__":
    unittest.main()
