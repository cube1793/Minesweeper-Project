"""Same-board application worker dispatch before any Qt/GUI setup."""

import builtins
from pathlib import Path
import pickle
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from core_engine import GameStatus
from replay_model import ReplayBoard


ROOT = Path(__file__).resolve().parents[1]
WORKER_FLAG = "--same-board-execution-worker"


class SameBoardWorkerDispatchTests(unittest.TestCase):
    def test_dispatch_forwards_arguments_and_exit_code_before_qt_setup(self):
        import main as application

        worker = ModuleType("same_board_execution_worker")
        worker.main = Mock(return_value=7)
        real_import = builtins.__import__

        def forbid_gui(name, *args, **kwargs):
            if name.startswith("PyQt") or name == "ui_manager":
                raise AssertionError(f"GUI import before worker dispatch: {name}")
            return real_import(name, *args, **kwargs)

        for frozen in (False, True):
            with self.subTest(frozen=frozen), patch.object(
                sys, "frozen", frozen, create=True,
            ), patch.object(
                sys, "argv", ["Minesweeper.exe", WORKER_FLAG, "p", "r"],
            ), patch.dict(
                sys.modules, {"same_board_execution_worker": worker},
            ), patch.object(
                application, "_configure_qt_plugin_path",
            ) as configure, patch("builtins.__import__", side_effect=forbid_gui):
                self.assertEqual(application.main(), 7)
            worker.main.assert_called_once_with([WORKER_FLAG, "p", "r"])
            configure.assert_not_called()
            worker.main.reset_mock()

    def test_existing_worker_dispatch_remains_separate(self):
        import main as application

        for flag, module_name in (
            ("--stage3-execution-worker", "stage3_execution_worker"),
            ("--zini-metric-worker", "zini_metric_worker"),
        ):
            worker = ModuleType(module_name)
            worker.main = Mock(return_value=9)
            comparison = ModuleType("same_board_execution_worker")
            comparison.main = Mock(side_effect=AssertionError("Wrong dispatch"))
            with self.subTest(flag=flag), patch.object(
                sys, "argv", ["Minesweeper.exe", flag, "p", "r"],
            ), patch.dict(
                sys.modules, {module_name: worker, "same_board_execution_worker": comparison},
            ), patch.object(application, "_configure_qt_plugin_path") as configure:
                self.assertEqual(application.main(), 9)
            worker.main.assert_called_once_with([flag, "p", "r"])
            comparison.main.assert_not_called()
            configure.assert_not_called()

    def run_entry(self, args, cwd):
        # -S removes site-packages, including PyQt. The unrelated cwd contains
        # neither the application modules nor the frozen physical profile.
        return subprocess.run(
            [sys.executable, "-B", "-S", str(ROOT / "main.py"), WORKER_FLAG,
             *map(str, args)],
            cwd=cwd, capture_output=True, text=True, timeout=30,
        )

    def test_real_dispatch_executes_exact_safe_and_mined_boards_without_pyqt(self):
        cases = (
            (ReplayBoard(4, 1, 1, {(1, 0)}), GameStatus.WON),
            (ReplayBoard(2, 2, 1, {(0, 0)}), GameStatus.LOST),
        )
        token = 2**100 + 37
        for board, expected_status in cases:
            with self.subTest(board=board), TemporaryDirectory(prefix="same board dispatch ") as temp:
                payload = Path(temp) / "payload.pkl"
                result = Path(temp) / "result.pkl"
                payload.write_bytes(pickle.dumps({"token": token, "board": board}))
                completed = self.run_entry((payload, result), temp)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                envelope = pickle.loads(result.read_bytes())
                self.assertEqual(set(envelope), {"token", "solver_execution", "error"})
                self.assertIs(type(envelope["token"]), int)
                self.assertEqual(envelope["token"], token)
                self.assertIsNone(envelope["error"])
                execution = envelope["solver_execution"]
                self.assertEqual(execution.layout.board, board)
                self.assertEqual(execution.stage2_result.replay_data.board, board)
                self.assertEqual(execution.stage2_result.status, expected_status)
                self.assertEqual(execution.stage3_result.status, expected_status)
                if expected_status == GameStatus.LOST:
                    self.assertEqual(len(execution.stage2_traces), 1)
                    self.assertEqual(len(execution.stage3_result.traces), 1)
                self.assertEqual(sorted(path.name for path in Path(temp).iterdir()),
                                 ["payload.pkl", "result.pkl"])

    def test_dispatch_wrong_arity_returns_usage_without_qt_or_files(self):
        for args in ((), ("payload.pkl",), ("p", "r", "extra")):
            with self.subTest(args=args), TemporaryDirectory() as temp:
                completed = self.run_entry(args, temp)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn("usage: same_board_execution_worker.py", completed.stderr)
                self.assertEqual(list(Path(temp).iterdir()), [])

    def test_dispatch_malformed_transport_publishes_error_without_solver_result(self):
        for encoded in (b"unreadable pickle", pickle.dumps({"token": 1})):
            with self.subTest(encoded=encoded), TemporaryDirectory() as temp:
                payload = Path(temp) / "payload.pkl"
                result = Path(temp) / "result.pkl"
                payload.write_bytes(encoded)
                completed = self.run_entry((payload, result), temp)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                envelope = pickle.loads(result.read_bytes())
                self.assertEqual(set(envelope), {"token", "solver_execution", "error"})
                self.assertIsNone(envelope["solver_execution"])
                self.assertIsInstance(envelope["error"], str)
                self.assertTrue(envelope["error"].strip())
                self.assertEqual(sorted(path.name for path in Path(temp).iterdir()),
                                 ["payload.pkl", "result.pkl"])


if __name__ == "__main__":
    unittest.main()
