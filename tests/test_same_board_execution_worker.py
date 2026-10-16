"""Trusted-local, board-only Same-board worker transport and source entry point."""

from contextlib import redirect_stderr
from dataclasses import fields
import io
import os
from pathlib import Path
import pickle
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmark_board import calculate_board_fingerprint
from core_engine import Action, GameStatus
from replay_model import ReplayBoard
from same_board_execution_worker import (
    build_worker_command, calculate_same_board_execution, main, write_result_atomic,
)
from same_board_runner import SolverExecution, run_fixed_layout_solvers
from simple_runner import SimpleActionTrace, SimpleRunResult
from stage3_runner import Stage3ActionTrace, Stage3RunResult


ROOT = Path(__file__).resolve().parents[1]
SAFE_BOARD = ReplayBoard(4, 1, 1, {(1, 0)})
MINED_ORIGIN_BOARD = ReplayBoard(2, 2, 1, {(0, 0)})
ENVELOPE_FIELDS = {"token", "solver_execution", "error"}


class WorkerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = {"token": 42, "board": SAFE_BOARD}
        cls.envelope = calculate_same_board_execution(cls.payload)

    def assert_failure(self, received, *, token, prefix=None):
        self.assertEqual(set(received), ENVELOPE_FIELDS)
        self.assertEqual(received["token"], token)
        self.assertIsNone(received["solver_execution"])
        self.assertIsInstance(received["error"], str)
        self.assertTrue(received["error"])
        if prefix is not None:
            self.assertTrue(received["error"].startswith(prefix), received["error"])

    def test_minimal_board_payload_returns_complete_solver_evidence(self):
        self.assertEqual(set(self.payload), {"token", "board"})
        self.assertEqual(set(self.envelope), ENVELOPE_FIELDS)
        self.assertEqual(self.envelope["token"], 42)
        self.assertIsNone(self.envelope["error"])
        execution = self.envelope["solver_execution"]
        self.assertIsInstance(execution, SolverExecution)
        self.assertEqual(execution.layout.board, SAFE_BOARD)
        self.assertIsInstance(execution.stage2_result, SimpleRunResult)
        self.assertIsInstance(execution.stage3_result, Stage3RunResult)
        self.assertEqual(execution.stage2_result.status, GameStatus.WON)
        self.assertEqual(execution.stage3_result.status, GameStatus.WON)
        self.assertGreater(len(execution.stage2_traces), 1)
        self.assertGreater(len(execution.stage3_result.traces), 1)
        self.assertTrue(all(isinstance(trace, SimpleActionTrace) for trace in execution.stage2_traces))
        self.assertTrue(all(isinstance(trace, Stage3ActionTrace) for trace in execution.stage3_result.traces))
        self.assertEqual(execution.stage2_result.replay_data.board, SAFE_BOARD)
        self.assertIsNone(execution.stage2_result.replay_data.mouse_trace)
        forbidden = {"context", "human_replay", "human_metrics", "mouse_trace", "game_index", "seed",
                     "benchmark_set_id", "engine", "time", "speed", "performance"}
        self.assertTrue(forbidden.isdisjoint(field.name for field in fields(execution)))

    def test_delegates_once_with_only_board_and_retains_native_solver_output(self):
        expected = self.envelope["solver_execution"]
        with patch("same_board_execution_worker.run_fixed_layout_solvers", return_value=expected) as run:
            received = calculate_same_board_execution(self.payload)
        run.assert_called_once_with(SAFE_BOARD)
        self.assertIs(received["solver_execution"], expected)
        self.assertIsNone(received["error"])

    def test_arbitrary_size_integer_tokens_survive_transport(self):
        for token in (0, 2**137 + 123):
            with self.subTest(token=token), patch(
                "same_board_execution_worker.run_fixed_layout_solvers",
                return_value=self.envelope["solver_execution"],
            ):
                received = pickle.loads(pickle.dumps(calculate_same_board_execution({
                    "token": token, "board": SAFE_BOARD,
                })))
            self.assertIs(type(received["token"]), int)
            self.assertEqual(received["token"], token)
            self.assertIsNone(received["error"])

    def test_payload_shape_is_closed_and_cannot_transport_human_data(self):
        for payload in (
            None, [], (), {}, {"token": 42}, {"board": SAFE_BOARD},
            {**self.payload, "events": ()}, {**self.payload, "mouse_trace": None},
            {**self.payload, "context": object()}, {**self.payload, "elapsed_time": 1.0},
            {**self.payload, "board_fingerprint": "claimed hash"},
            {**self.payload, "game_index": 0},
        ):
            with self.subTest(payload=payload), patch(
                "same_board_execution_worker.run_fixed_layout_solvers",
            ) as run:
                received = calculate_same_board_execution(payload)
            token = payload.get("token") if type(payload) is dict else None
            self.assert_failure(received, token=token, prefix="Transport failed:")
            run.assert_not_called()

    def test_invalid_token_types_fail_before_execution(self):
        for token in (None, True, False, 42.0, -1, "42", object()):
            with self.subTest(token=token), patch(
                "same_board_execution_worker.run_fixed_layout_solvers",
            ) as run:
                received = calculate_same_board_execution({"token": token, "board": SAFE_BOARD})
            self.assert_failure(received, token=None, prefix="Transport failed:")
            run.assert_not_called()

    def test_wrong_board_type_fails_closed(self):
        for board in (None, {}, (4, 1, 1, {(1, 0)}), "board"):
            with self.subTest(board=board), patch("same_board_runner.run_simple") as stage2:
                received = calculate_same_board_execution({"token": 42, "board": board})
            self.assert_failure(received, token=42)
            stage2.assert_not_called()

    def test_unpickled_board_validation_is_not_bypassed(self):
        # Pickle does not run dataclass __post_init__: corruption must be
        # rejected again at the child boundary, before either solver executes.
        for attribute, value in (("width", 0), ("height", 17), ("width", 31),
                                 ("num_mines", 0), ("mine_positions", frozenset({(4, 0)})),
                                 ("width", True)):
            board = pickle.loads(pickle.dumps(SAFE_BOARD))
            object.__setattr__(board, attribute, value)
            payload = pickle.loads(pickle.dumps({"token": 43, "board": board}))
            with self.subTest(attribute=attribute, value=value), patch(
                "same_board_runner.run_simple",
            ) as stage2, patch("same_board_runner.run_stage3") as stage3:
                received = calculate_same_board_execution(payload)
            self.assert_failure(received, token=43)
            stage2.assert_not_called()
            stage3.assert_not_called()

    def test_layout_fingerprint_is_recomputed_from_exact_board(self):
        execution = self.envelope["solver_execution"]
        self.assertEqual(execution.layout.board_fingerprint, calculate_board_fingerprint(
            SAFE_BOARD.width, SAFE_BOARD.height, SAFE_BOARD.num_mines, SAFE_BOARD.mine_positions,
        ))
        different = calculate_same_board_execution({"token": 44, "board": MINED_ORIGIN_BOARD})
        self.assertIsNone(different["error"])
        self.assertEqual(different["solver_execution"].layout.board, MINED_ORIGIN_BOARD)
        self.assertNotEqual(different["solver_execution"].layout, execution.layout)

    def test_mined_origin_is_immediate_loss_without_regeneration_or_retry(self):
        with patch("same_board_execution_worker.run_fixed_layout_solvers", wraps=run_fixed_layout_solvers) as run, \
             patch("simple_runner.analyze_position", side_effect=AssertionError("unexpected analysis")), \
             patch("stage3_runner.plan_position", side_effect=AssertionError("unexpected planning")), \
             patch("core_engine.random.sample", side_effect=AssertionError("regeneration")):
            received = calculate_same_board_execution({"token": 45, "board": MINED_ORIGIN_BOARD})
        run.assert_called_once_with(MINED_ORIGIN_BOARD)
        self.assertIsNone(received["error"])
        execution = received["solver_execution"]
        for traces, metrics in ((execution.stage2_traces, execution.stage2_metrics),
                               (execution.stage3_result.traces, execution.stage3_metrics)):
            self.assertEqual(len(traces), 1)
            self.assertEqual((traces[0].move.action, traces[0].move.x, traces[0].move.y), (Action.OPEN, 0, 0))
            self.assertEqual(traces[0].status_after, GameStatus.LOST)
            self.assertEqual(metrics.outcome, GameStatus.LOST)
            self.assertIsNone(traces[0].decision_compute_ns)
            self.assertEqual(metrics.model_c_total_us, execution.model_c_evaluation.table[0][0])

    def test_solver_and_planner_failure_returns_error_once_without_loss(self):
        for target in ("same_board_runner.run_simple", "stage3_runner.plan_position"):
            with self.subTest(target=target), patch(target, side_effect=RuntimeError("injected failure")) as fail:
                received = calculate_same_board_execution(self.payload)
            fail.assert_called_once()
            self.assert_failure(received, token=42, prefix="Execution failed:")
            self.assertIn("injected failure", received["error"])

    def test_pickle_round_trip_preserves_native_results_traces_and_metrics(self):
        restored = pickle.loads(pickle.dumps(self.envelope, protocol=pickle.HIGHEST_PROTOCOL))
        self.assertEqual(restored, self.envelope)
        before = self.envelope["solver_execution"]
        after = restored["solver_execution"]
        self.assertIsInstance(after, SolverExecution)
        self.assertIs(type(after.stage2_traces), tuple)
        self.assertIs(type(after.stage3_result.traces), tuple)
        self.assertEqual(after.layout, before.layout)
        self.assertEqual(after.stage2_result, before.stage2_result)
        self.assertEqual(after.stage3_result, before.stage3_result)
        for metrics in (after.stage2_metrics, after.stage3_metrics):
            self.assertIs(type(metrics.model_c_total_us), int)
            self.assertIs(type(metrics.decision_compute_total_ns), int)

    def test_atomic_publication_replaces_only_after_complete_pickle_is_closed(self):
        for existing in (False, True):
            with self.subTest(existing=existing), TemporaryDirectory() as temp:
                result_path = Path(temp) / "result.pkl"
                previous = pickle.dumps({"previous": True})
                if existing:
                    result_path.write_bytes(previous)
                replace = os.replace

                def publish(temp_path, target):
                    self.assertEqual(Path(temp_path).parent, result_path.parent)
                    self.assertEqual(Path(target), result_path)
                    self.assertEqual(pickle.loads(Path(temp_path).read_bytes()), self.envelope)
                    if existing:
                        self.assertEqual(result_path.read_bytes(), previous)
                    else:
                        self.assertFalse(result_path.exists())
                    replace(temp_path, target)

                with patch("same_board_execution_worker.os.replace", side_effect=publish) as publish_call:
                    write_result_atomic(str(result_path), self.envelope)
                publish_call.assert_called_once()
                self.assertEqual(pickle.loads(result_path.read_bytes()), self.envelope)
                self.assertEqual(list(Path(temp).iterdir()), [result_path])

    def test_partial_write_or_serialization_failure_never_publishes_partial_result(self):
        for error_type in (pickle.PicklingError, OSError):
            for existing in (False, True):
                with self.subTest(error=error_type, existing=existing), TemporaryDirectory() as temp:
                    result_path = Path(temp) / "result.pkl"
                    previous = pickle.dumps({"previous": True})
                    if existing:
                        result_path.write_bytes(previous)

                    def partial_write(result, result_file, **kwargs):
                        result_file.write(b"partial pickle")
                        result_file.flush()
                        raise error_type("injected write failure")

                    with patch("same_board_execution_worker.pickle.dump", side_effect=partial_write), \
                         patch("same_board_execution_worker.os.replace") as replace:
                        with self.assertRaisesRegex(error_type, "injected write failure"):
                            write_result_atomic(str(result_path), self.envelope)
                    replace.assert_not_called()
                    self.assertEqual(list(Path(temp).iterdir()), [result_path] if existing else [])
                    if existing:
                        self.assertEqual(result_path.read_bytes(), previous)

    def test_replace_failure_cleans_private_temp_and_preserves_previous_result(self):
        with TemporaryDirectory() as temp:
            result_path = Path(temp) / "result.pkl"
            previous = pickle.dumps({"previous": True})
            result_path.write_bytes(previous)
            with patch("same_board_execution_worker.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    write_result_atomic(str(result_path), self.envelope)
            self.assertEqual(result_path.read_bytes(), previous)
            self.assertEqual(list(Path(temp).iterdir()), [result_path])

    def test_wrong_cli_arity_has_no_io_or_execution(self):
        for argv in ([], ["worker"], ["worker", "payload"], ["worker", "p", "r", "extra"]):
            stderr = io.StringIO()
            with self.subTest(argv=argv), redirect_stderr(stderr), patch(
                "same_board_execution_worker.run_fixed_layout_solvers",
            ) as run, patch("builtins.open") as open_file, patch(
                "same_board_execution_worker.write_result_atomic",
            ) as write:
                self.assertEqual(main(argv), 2)
            self.assertIn("usage:", stderr.getvalue())
            run.assert_not_called()
            open_file.assert_not_called()
            write.assert_not_called()


class WorkerEntryPointTests(unittest.TestCase):
    def run_entry(self, args, cwd):
        # -S removes site-packages, including PyQt. An unrelated cwd also proves
        # that module/calibration paths are not accidentally relative to cwd.
        return subprocess.run(
            [sys.executable, "-B", "-S", str(ROOT / "same_board_execution_worker.py"), *map(str, args)],
            cwd=cwd, capture_output=True, text=True, timeout=30,
        )

    def test_source_entry_runs_safe_and_mined_layouts_without_pyqt_from_unrelated_cwd(self):
        for board, status in ((SAFE_BOARD, GameStatus.WON), (MINED_ORIGIN_BOARD, GameStatus.LOST)):
            with self.subTest(board=board), TemporaryDirectory(prefix="same board worker space ") as temp:
                payload_path = Path(temp) / "payload.pkl"
                result_path = Path(temp) / "result.pkl"
                payload_path.write_bytes(pickle.dumps({"token": 2**137, "board": board}))
                completed = self.run_entry((payload_path, result_path), temp)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                received = pickle.loads(result_path.read_bytes())
                self.assertEqual(set(received), ENVELOPE_FIELDS)
                self.assertEqual(received["token"], 2**137)
                self.assertIsNone(received["error"])
                execution = received["solver_execution"]
                self.assertEqual(execution.layout.board, board)
                self.assertEqual(execution.stage2_result.status, status)
                self.assertEqual(execution.stage3_result.status, status)
                self.assertEqual(sorted(path.name for path in Path(temp).iterdir()), ["payload.pkl", "result.pkl"])

    def test_worker_import_and_execution_require_no_qt_or_parent_job(self):
        code = """
import sys
for name in ('PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'same_board_execution_job',
             'stage3_execution_job', 'stage3_execution', 'telemetry_model', 'telemetry_repository'):
    sys.modules[name] = None
from replay_model import ReplayBoard
from same_board_execution_worker import calculate_same_board_execution
result = calculate_same_board_execution({'token': 1, 'board': ReplayBoard(1, 1, 0, ())})
assert result['error'] is None, result
assert result['solver_execution'].stage2_result.status.name == 'WON'
assert result['solver_execution'].stage3_result.status.name == 'WON'
"""
        completed = subprocess.run([sys.executable, "-B", "-S", "-c", code], cwd=ROOT,
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_unreadable_missing_and_malformed_payload_publish_only_transport_error(self):
        for encoded in (None, b"invalid pickle", pickle.dumps({}), pickle.dumps({"token": 7}),
                        pickle.dumps({"token": True, "board": SAFE_BOARD}),
                        pickle.dumps({"token": 7, "board": SAFE_BOARD}) + b"trailing data"):
            with self.subTest(encoded=encoded), TemporaryDirectory() as temp:
                payload_path = Path(temp) / "payload.pkl"
                result_path = Path(temp) / "result.pkl"
                if encoded is not None:
                    payload_path.write_bytes(encoded)
                completed = self.run_entry((payload_path, result_path), temp)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                received = pickle.loads(result_path.read_bytes())
                self.assertEqual(set(received), ENVELOPE_FIELDS)
                self.assertIsNone(received["solver_execution"])
                self.assertTrue(received["error"].startswith("Transport failed:"), received)
                self.assertEqual(sorted(path.name for path in Path(temp).iterdir()),
                                 ["payload.pkl", "result.pkl"] if encoded is not None else ["result.pkl"])

    def test_unwritable_result_path_causes_nonzero_exit_without_partial_publication(self):
        with TemporaryDirectory() as temp:
            payload_path = Path(temp) / "payload.pkl"
            result_path = Path(temp) / "missing" / "result.pkl"
            payload_path.write_bytes(pickle.dumps({"token": 8, "board": SAFE_BOARD}))
            completed = self.run_entry((payload_path, result_path), temp)
            self.assertNotEqual(completed.returncode, 0)
            self.assertTrue(completed.stderr)
            self.assertFalse(result_path.exists())
            self.assertEqual(list(Path(temp).iterdir()), [payload_path])

    def test_source_command_uses_module_relative_absolute_worker_path(self):
        with patch.object(sys, "frozen", False, create=True):
            command = build_worker_command("request.pkl", "reply.pkl")
        self.assertEqual(command, [sys.executable, str(ROOT / "same_board_execution_worker.py"),
                                   "request.pkl", "reply.pkl"])

    def test_frozen_command_uses_distinct_application_worker_switch(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", "Minesweeper.exe"):
            command = build_worker_command("request.pkl", "reply.pkl")
        self.assertEqual(command, ["Minesweeper.exe", "--same-board-execution-worker", "request.pkl", "reply.pkl"])


if __name__ == "__main__":
    unittest.main()
