"""Trusted-local Stage-3 worker transport and both PyQt-free entry points."""

from contextlib import redirect_stderr
from fractions import Fraction
import io
import os
from pathlib import Path
import pickle
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmark_board import BenchmarkBoard, BenchmarkSetSpec, EXPERT_GENERAL_V1, generate_board
from core_engine import GameStatus
from stage3_execution import Stage3Execution, run_expert_stage3_execution
from stage3_execution_worker import calculate_stage3_execution, main, write_result_atomic
from stage3_planner import Stage3Decision
from stage3_runner import Stage3ActionTrace, Stage3RunResult


ROOT = Path(__file__).resolve().parents[1]
EXPERT_INDEX = 0  # Fast real run with retained exact probability evidence.
ENTRY_POINTS = (
    ("stage3_execution_worker.py",),
    ("main.py", "--stage3-execution-worker"),
)


class WorkerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = {"token": 42, "game_index": EXPERT_INDEX}
        cls.envelope = calculate_stage3_execution(cls.payload)

    def test_real_payload_returns_complete_expert_execution(self):
        self.assertEqual(set(self.envelope), {"token", "execution", "error"})
        self.assertEqual(self.envelope["token"], self.payload["token"])
        self.assertIsNone(self.envelope["error"])
        execution = self.envelope["execution"]
        self.assertIsInstance(execution, Stage3Execution)
        self.assertIs(execution.spec, EXPERT_GENERAL_V1)
        self.assertIsInstance(execution.board, BenchmarkBoard)
        self.assertEqual(execution.board, generate_board(EXPERT_GENERAL_V1, EXPERT_INDEX))
        self.assertEqual(execution.board.game_index, self.payload["game_index"])
        self.assertIsInstance(execution.result, Stage3RunResult)
        self.assertIn(execution.result.status, (GameStatus.WON, GameStatus.LOST))
        self.assertGreater(len(execution.result.traces), 1)
        self.assertTrue(all(isinstance(trace, Stage3ActionTrace)
                            for trace in execution.result.traces))
        self.assertEqual(execution.result.status, execution.result.traces[-1].status_after)

    def test_delegates_once_with_only_index_and_preserves_returned_object(self):
        execution = self.envelope["execution"]
        token = object()
        with patch("stage3_execution_worker.run_expert_stage3_execution",
                   return_value=execution) as run:
            received = calculate_stage3_execution({"token": token, "game_index": EXPERT_INDEX})
        run.assert_called_once_with(EXPERT_INDEX)
        self.assertIs(received["token"], token)
        self.assertIs(received["execution"], execution)
        self.assertIs(received["execution"].result, execution.result)
        self.assertIsNone(received["error"])

    def test_invalid_index_returns_diagnostic_without_retry(self):
        for index in (-1, True, "0", None):
            with self.subTest(index=index), patch(
                "stage3_execution_worker.run_expert_stage3_execution",
                wraps=run_expert_stage3_execution,
            ) as run:
                received = calculate_stage3_execution({"token": 43, "game_index": index})
            run.assert_called_once_with(index)
            self.assertEqual(set(received), {"token", "execution", "error"})
            self.assertEqual(received["token"], 43)
            self.assertIsNone(received["execution"])
            self.assertIn("ValueError", received["error"])
            self.assertIn("game_index", received["error"])

    def test_execution_exception_returns_diagnostic_without_retry(self):
        with patch("stage3_execution_worker.run_expert_stage3_execution",
                   side_effect=RuntimeError("planner failed")) as run:
            received = calculate_stage3_execution(self.payload)
        run.assert_called_once_with(EXPERT_INDEX)
        self.assertEqual(received, {
            "token": 42, "execution": None, "error": "RuntimeError('planner failed')",
        })

    def test_missing_transport_fields_fail_before_execution(self):
        for payload in ({}, {"game_index": EXPERT_INDEX}, {"token": 42}):
            with self.subTest(payload=payload), patch(
                "stage3_execution_worker.run_expert_stage3_execution",
            ) as run:
                with self.assertRaises(KeyError):
                    calculate_stage3_execution(payload)
                run.assert_not_called()

    def test_pickle_preserves_complete_result_and_exact_decision_data(self):
        # Compare one execution with its round trip, never independent compute timings.
        received = pickle.loads(pickle.dumps(self.envelope, protocol=pickle.HIGHEST_PROTOCOL))
        self.assertEqual(received, self.envelope)
        before = self.envelope["execution"]
        after = received["execution"]
        self.assertIsInstance(after, Stage3Execution)
        self.assertIsInstance(after.spec, BenchmarkSetSpec)
        self.assertIsInstance(after.board, BenchmarkBoard)
        self.assertIsInstance(after.result, Stage3RunResult)
        self.assertEqual(after.board.board_fingerprint, before.board.board_fingerprint)
        self.assertEqual(after.board.mine_positions, before.board.mine_positions)
        self.assertEqual(after.result.moves, before.result.moves)
        self.assertEqual(after.result.status, before.result.status)
        self.assertEqual(after.result.total_modeled_us, before.result.total_modeled_us)
        self.assertIs(type(after.result.traces), tuple)
        probability_cells = []
        plans = []
        for original, restored in zip(before.result.traces, after.result.traces):
            self.assertIsInstance(restored, Stage3ActionTrace)
            self.assertEqual(restored, original)
            self.assertEqual(restored.status_after, original.status_after)
            self.assertIs(type(restored.modeled_action_us), int)
            self.assertEqual(restored.modeled_action_us, original.modeled_action_us)
            self.assertEqual(restored.decision_compute_ns, original.decision_compute_ns)
            if original.decision is None:
                self.assertIsNone(restored.decision)
                continue
            self.assertIsInstance(restored.decision, Stage3Decision)
            self.assertEqual(restored.decision, original.decision)
            if restored.decision.plan is not None:
                plans.append(restored.decision.plan)
            original_probabilities = original.decision.evidence.probability_result
            restored_probabilities = restored.decision.evidence.probability_result
            if original_probabilities is not None:
                self.assertEqual(restored_probabilities, original_probabilities)
                for old_cell, new_cell in zip(original_probabilities.probabilities,
                                              restored_probabilities.probabilities):
                    # V1 retains integer world counts; Fraction is an exact property.
                    self.assertIs(type(new_cell.mine_worlds), int)
                    self.assertIs(type(new_cell.total_worlds), int)
                    self.assertEqual(new_cell.mine_worlds, old_cell.mine_worlds)
                    self.assertEqual(new_cell.total_worlds, old_cell.total_worlds)
                    self.assertIsInstance(new_cell.probability, Fraction)
                    self.assertEqual(new_cell.probability, old_cell.probability)
                    probability_cells.append(new_cell)
        self.assertTrue(plans)
        self.assertTrue(probability_cells)
        self.assertTrue(any(cell.total_worlds > 2**53 for cell in probability_cells))
        self.assertTrue(any(0 < cell.probability < 1 for cell in probability_cells))

    def test_atomic_publication_replaces_only_with_complete_pickle(self):
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

                with patch("stage3_execution_worker.os.replace", side_effect=publish) as replace_call:
                    write_result_atomic(str(result_path), self.envelope)
                replace_call.assert_called_once()
                self.assertEqual(pickle.loads(result_path.read_bytes()), self.envelope)
                self.assertEqual(list(Path(temp).iterdir()), [result_path])

    def test_serialization_and_write_failure_clean_temp_without_publication(self):
        for error_type in (pickle.PicklingError, OSError):
            for existing in (False, True):
                with self.subTest(error=error_type, existing=existing), TemporaryDirectory() as temp:
                    result_path = Path(temp) / "result.pkl"
                    previous = pickle.dumps({"previous": True})
                    if existing:
                        result_path.write_bytes(previous)

                    def fail_after_partial_write(result, result_file, **kwargs):
                        result_file.write(b"partial pickle")
                        result_file.flush()
                        raise error_type("injected write failure")

                    with patch("stage3_execution_worker.pickle.dump",
                               side_effect=fail_after_partial_write), patch(
                        "stage3_execution_worker.os.replace",
                    ) as replace_call:
                        with self.assertRaisesRegex(error_type, "injected write failure"):
                            write_result_atomic(str(result_path), self.envelope)
                    replace_call.assert_not_called()
                    self.assertEqual(list(Path(temp).iterdir()), [result_path] if existing else [])
                    if existing:
                        self.assertEqual(result_path.read_bytes(), previous)

    def test_replace_failure_cleans_temp_and_preserves_previous_result(self):
        with TemporaryDirectory() as temp:
            result_path = Path(temp) / "result.pkl"
            previous = pickle.dumps({"previous": True})
            result_path.write_bytes(previous)
            with patch("stage3_execution_worker.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    write_result_atomic(str(result_path), self.envelope)
            self.assertEqual(result_path.read_bytes(), previous)
            self.assertEqual(list(Path(temp).iterdir()), [result_path])

    def test_wrong_cli_arity_has_no_io_or_execution(self):
        for argv in ([], ["worker"], ["worker", "payload"], ["worker", "p", "r", "extra"]):
            stderr = io.StringIO()
            with self.subTest(argv=argv), redirect_stderr(stderr), patch(
                "stage3_execution_worker.run_expert_stage3_execution",
            ) as run, patch("builtins.open") as open_file, patch(
                "stage3_execution_worker.write_result_atomic",
            ) as write:
                self.assertEqual(main(argv), 2)
            self.assertIn("usage: stage3_execution_worker.py <payload.pkl> <result.pkl>",
                          stderr.getvalue())
            run.assert_not_called()
            open_file.assert_not_called()
            write.assert_not_called()


class WorkerEntryPointTests(unittest.TestCase):
    def run_entry(self, entry, args, cwd):
        # -S removes site-packages, including PyQt. Paths are absolute because
        # cwd deliberately has neither source modules nor calibration data.
        return subprocess.run(
            [sys.executable, "-B", "-S", str(ROOT / entry[0]), *entry[1:], *map(str, args)],
            cwd=cwd, capture_output=True, text=True, timeout=30,
        )

    def test_both_entry_points_execute_from_unrelated_cwd_without_pyqt(self):
        expected_board = generate_board(EXPERT_GENERAL_V1, EXPERT_INDEX)
        for entry in ENTRY_POINTS:
            with self.subTest(entry=entry), TemporaryDirectory(prefix="stage3 worker space ") as temp:
                payload_path = Path(temp) / "payload.pkl"
                result_path = Path(temp) / "result.pkl"
                payload_path.write_bytes(pickle.dumps({"token": 101, "game_index": EXPERT_INDEX}))
                completed = self.run_entry(entry, (payload_path, result_path), temp)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                received = pickle.loads(result_path.read_bytes())
                self.assertEqual(set(received), {"token", "execution", "error"})
                self.assertEqual(received["token"], 101)
                self.assertIsNone(received["error"])
                execution = received["execution"]
                self.assertIsInstance(execution, Stage3Execution)
                self.assertIsInstance(execution.spec, BenchmarkSetSpec)
                self.assertIsInstance(execution.board, BenchmarkBoard)
                self.assertEqual(execution.spec, EXPERT_GENERAL_V1)
                self.assertEqual(execution.board, expected_board)
                self.assertIsInstance(execution.result, Stage3RunResult)
                self.assertIn(execution.result.status, (GameStatus.WON, GameStatus.LOST))
                self.assertGreater(len(execution.result.traces), 1)
                self.assertTrue(all(isinstance(trace, Stage3ActionTrace)
                                    for trace in execution.result.traces))
                self.assertTrue(any(isinstance(trace.decision, Stage3Decision)
                                    for trace in execution.result.traces))
                self.assertEqual(sorted(path.name for path in Path(temp).iterdir()),
                                 ["payload.pkl", "result.pkl"])

    def test_both_entry_points_publish_execution_failure_with_zero_exit(self):
        for entry in ENTRY_POINTS:
            with self.subTest(entry=entry), TemporaryDirectory() as temp:
                payload_path = Path(temp) / "payload.pkl"
                result_path = Path(temp) / "result.pkl"
                payload_path.write_bytes(pickle.dumps({"token": 102, "game_index": -1}))
                completed = self.run_entry(entry, (payload_path, result_path), temp)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                received = pickle.loads(result_path.read_bytes())
                self.assertEqual(received["token"], 102)
                self.assertIsNone(received["execution"])
                self.assertIn("ValueError", received["error"])
                self.assertEqual(sorted(path.name for path in Path(temp).iterdir()),
                                 ["payload.pkl", "result.pkl"])

    def test_both_entry_points_fail_transport_without_publishing_result(self):
        cases = (
            (b"unreadable pickle", "result.pkl"),
            (pickle.dumps({"game_index": EXPERT_INDEX}), "result.pkl"),
            (pickle.dumps({"token": 103}), "result.pkl"),
            (pickle.dumps({"token": 103, "game_index": -1}), "missing/result.pkl"),
        )
        for entry in ENTRY_POINTS:
            for encoded, target in cases:
                with self.subTest(entry=entry, target=target, payload=encoded), TemporaryDirectory() as temp:
                    payload_path = Path(temp) / "payload.pkl"
                    result_path = Path(temp) / target
                    payload_path.write_bytes(encoded)
                    completed = self.run_entry(entry, (payload_path, result_path), temp)
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertTrue(completed.stderr)
                    self.assertFalse(result_path.exists())
                    self.assertEqual(list(Path(temp).iterdir()), [payload_path])

    def test_both_entry_points_reject_wrong_arity_without_pyqt_or_files(self):
        for entry in ENTRY_POINTS:
            for args in ((), ("payload.pkl",), ("p", "r", "extra")):
                with self.subTest(entry=entry, args=args), TemporaryDirectory() as temp:
                    completed = self.run_entry(entry, args, temp)
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertIn("usage: stage3_execution_worker.py", completed.stderr)
                    self.assertEqual(list(Path(temp).iterdir()), [])

    def test_main_dispatch_returns_worker_exit_code_before_qt_setup(self):
        import main as application

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "argv", ["Minesweeper.exe", "--stage3-execution-worker", "p", "r"]),
            patch("stage3_execution_worker.main", return_value=7) as worker,
            patch.object(application, "_configure_qt_plugin_path") as configure,
        ):
            self.assertEqual(application.main(), 7)
        worker.assert_called_once_with(["--stage3-execution-worker", "p", "r"])
        configure.assert_not_called()


if __name__ == "__main__":
    unittest.main()
