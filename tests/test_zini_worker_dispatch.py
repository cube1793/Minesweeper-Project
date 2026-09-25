"""Source/frozen ZiNi entry points and the UI subprocess lifecycle."""

import os
from pathlib import Path
import pickle
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from board_snapshot import BoardSnapshot
from zini_calculator import ZiniNeighborhoodBeamConfig


ROOT = Path(__file__).resolve().parents[1]


class WorkerEntryPointTests(unittest.TestCase):
    def test_both_entry_points_compute_without_pyqt(self):
        snapshot = BoardSnapshot(
            width=3, height=3, num_mines=0, mines_placed=True,
            mines=frozenset(), adjacent=((0, 0, 0),) * 3,
        )
        payload = {
            "token": 42,
            "snapshot": snapshot,
            "config": ZiniNeighborhoodBeamConfig(max_evaluations=1),
        }
        for entry in (["zini_metric_worker.py"],
                      ["main.py", "--zini-metric-worker"]):
            with self.subTest(entry=entry), TemporaryDirectory(prefix="zini space ") as temp:
                payload_path = Path(temp) / "payload.pkl"
                result_path = Path(temp) / "result.pkl"
                payload_path.write_bytes(pickle.dumps(payload))
                # -S removes site-packages, including PyQt, from the child.
                result = subprocess.run(
                    [sys.executable, "-S", str(ROOT / entry[0]), *entry[1:],
                     str(payload_path), str(result_path)],
                    cwd=temp, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(pickle.loads(result_path.read_bytes()), {
                    "token": 42, "clicks": 1, "error": None,
                })
                self.assertEqual(sorted(p.name for p in Path(temp).iterdir()),
                                 ["payload.pkl", "result.pkl"])

    def test_dispatch_rejects_wrong_arity_without_starting_qt(self):
        for args in ([], ["payload.pkl"], ["a", "b", "c"]):
            with self.subTest(args=args):
                result = subprocess.run(
                    [sys.executable, "-S", str(ROOT / "main.py"),
                     "--zini-metric-worker", *args],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("usage:", result.stderr)

    def test_dispatch_propagates_worker_exit_code_before_qt_setup(self):
        import main

        with (
            patch.object(sys, "argv", ["Minesweeper.exe", "--zini-metric-worker", "p", "r"]),
            patch("zini_metric_worker.main", return_value=7) as worker,
            patch.object(main, "_configure_qt_plugin_path") as configure,
        ):
            self.assertEqual(main.main(), 7)
        worker.assert_called_once_with(["--zini-metric-worker", "p", "r"])
        configure.assert_not_called()


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    from core_engine import MinesweeperEngine
    from ui_manager import MinesweeperUI, ZINI_WORKER_SCRIPT
    from zini_metric_worker import write_result_atomic


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class WorkerLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.engine = MinesweeperEngine(3, 3, 1)
        self.ui = MinesweeperUI(self.engine)
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.addCleanup(self.close_ui)

    def close_ui(self):
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def launch(self, frozen):
        process = Mock()
        process.poll.return_value = None
        with (
            patch.object(sys, "frozen", frozen, create=True),
            patch("ui_manager.subprocess.Popen", return_value=process) as popen,
        ):
            self.ui._ensure_zini_metric_job()
        payload_path = self.ui._zini_payload_path
        result_path = self.ui._zini_result_path
        popen.assert_called_once_with(
            [sys.executable, "--zini-metric-worker" if frozen else ZINI_WORKER_SCRIPT,
             payload_path, result_path],
            cwd=os.path.dirname(ZINI_WORKER_SCRIPT),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.assertTrue(Path(payload_path).is_file())
        self.assertFalse(Path(result_path).exists())
        self.assertTrue(self.ui._zini_poll_timer.isActive())
        return process, payload_path, result_path

    def test_source_launch_poll_and_cleanup(self):
        self.check_completed_launch(frozen=False)

    def test_frozen_launch_poll_and_cleanup(self):
        self.check_completed_launch(frozen=True)

    def check_completed_launch(self, frozen):
        process, payload_path, result_path = self.launch(frozen)
        with open(payload_path, "rb") as stream:
            payload = pickle.load(stream)
        self.assertEqual(payload["snapshot"], self.engine.get_board_snapshot())
        # An unfinished child is neither restarted nor reaped by polling.
        with patch("ui_manager.subprocess.Popen") as popen:
            self.ui._ensure_zini_metric_job()
            self.ui._poll_zini_metric_job()
        popen.assert_not_called()
        process.wait.assert_not_called()
        write_result_atomic(result_path, {
            "token": payload["token"], "clicks": 5, "error": None,
        })
        self.ui._poll_zini_metric_job()
        self.assertEqual(self.ui._current_zini_clicks(), 5)
        process.wait.assert_called_once_with(timeout=0.1)
        self.assert_cleared(payload_path, result_path)

    def test_reset_terminates_frozen_worker_and_cleans_files(self):
        process, payload_path, result_path = self.launch(frozen=True)
        token = self.ui._zini_job_token
        self.ui.on_reset()
        process.terminate.assert_called_once()
        self.assertGreater(self.ui._zini_job_token, token)
        self.assertIsNone(self.ui._current_zini_clicks())
        self.assert_cleared(payload_path, result_path)

    def test_stale_frozen_result_is_ignored(self):
        process, payload_path, result_path = self.launch(frozen=True)
        write_result_atomic(result_path, {
            "token": self.ui._zini_job_token - 1, "clicks": 999, "error": None,
        })
        self.ui._poll_zini_metric_job()
        self.assertIsNone(self.ui._current_zini_clicks())
        self.assert_cleared(payload_path, result_path)

    def test_failed_frozen_launch_cleans_files_and_stops_retrying(self):
        with (
            patch.object(sys, "frozen", True, create=True),
            patch("ui_manager.subprocess.Popen", side_effect=OSError("launch failed")) as popen,
            patch("builtins.print"),
        ):
            self.ui._ensure_zini_metric_job()
            self.ui._ensure_zini_metric_job()
        popen.assert_called_once()
        self.assertEqual(self.ui._zini_result_token, self.ui._zini_job_token)
        self.assertIsNone(self.ui._current_zini_clicks())
        self.assert_cleared(*popen.call_args.args[0][-2:])

    def assert_cleared(self, payload_path, result_path):
        self.assertFalse(Path(payload_path).exists())
        self.assertFalse(Path(result_path).exists())
        self.assertIsNone(self.ui._zini_process)
        self.assertIsNone(self.ui._zini_payload_path)
        self.assertIsNone(self.ui._zini_result_path)
        self.assertFalse(self.ui._zini_poll_timer.isActive())


if __name__ == "__main__":
    unittest.main()
