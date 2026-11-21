"""F: launcher selection and the multi-algorithm result window (offscreen Qt)."""

from contextlib import ExitStack
import os
import random
import unittest
from unittest.mock import patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    import same_board_comparison_launcher as launcher
    from same_board_runs_ui import SameBoardRunsWindow

from core_engine import CellState
from replay_model import ReplayData, ReplayEvent
from same_board_algorithms import (
    ALGORITHMS, TIME_DEPENDENCE_NOTE, execute_algorithm, not_run, validate_run,
)
from same_board_comparison import HumanComparisonContext
from same_board_runner import run_same_board_comparison
from tests.test_same_board_algorithms import WIN_BOARD
from tests.test_same_board_runner import human_context

DECISION_ENTRY_POINTS = (
    "live_k_policy.KOwner.propose", "stage4_live_worker.Session.propose",
    "simple_runner.run_simple", "stage3_runner.run_stage3", "subprocess.Popen",
    "same_board_algorithms.execute_algorithm",
)


def preset_context():
    # A full Human game on the 9x9/10 board: the first OPEN hits a mine.
    return HumanComparisonContext(ReplayData(WIN_BOARD, (ReplayEvent(1.5, 8, 0, "OPEN"),)),
                                  declared_full_game_human=True)


class FakeQueue:
    """Stand-in for SameBoardAlgorithmQueue: no processes; tests deliver runs."""

    def __init__(self, parent=None):
        from PyQt5.QtCore import QObject, pyqtSignal

        class Signals(QObject):
            run_finished = pyqtSignal(object, object)
            finished = pyqtSignal(object)

        self.signals = Signals()
        self.run_finished, self.finished = self.signals.run_finished, self.signals.finished
        self.state, self.current_algorithm, self.started, self.cancel_calls = "idle", None, [], 0
        self.token = 40

    def start(self, board, algorithms, r_target=None):
        self.token += 1
        self.started.append((board, tuple(algorithms), r_target))
        self.state, self.current_algorithm = "running", algorithms[0]
        return self.token

    def cancel(self):
        self.cancel_calls += 1

    def deliver(self, runs, *, finish=True):
        for run in runs:
            self.run_finished.emit(self.token, run)
        if finish:
            self.state, self.current_algorithm = "idle", None
            self.finished.emit(self.token)

    def shutdown(self):
        self.state = "idle"


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class AlgorithmSelectionUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.context = preset_context()
        cls.runs = {key: validate_run(WIN_BOARD, execute_algorithm(key, WIN_BOARD,
                                                                    r_target="120" if key == "S4_R" else None))
                    for key in ALGORITHMS}

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.queue_factory = self.stack.enter_context(patch.object(launcher, "SameBoardAlgorithmQueue", FakeQueue))
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            try:
                window.close()
            except RuntimeError:
                pass
        self.app.processEvents()

    def launcher_window(self, context=None):
        window = launcher.SameBoardComparisonLauncherWindow(context or self.context)
        self.windows.append(window)
        return window

    def forbid_computation(self):
        stack = ExitStack()
        for target in DECISION_ENTRY_POINTS:
            stack.enter_context(patch(target, side_effect=AssertionError(target)))
        return stack

    def test_default_selection_runs_only_existing_job_and_opens_existing_window(self):
        context = human_context(with_trace=True)
        execution = run_same_board_comparison(context)
        window = self.launcher_window(context)
        self.assertEqual(window.selected_algorithms(), ("S2", "S3"))
        for key in ALGORITHMS[2:]:
            self.assertFalse(window.algorithm_checks[key].isEnabled())  # 4x1 board is not a preset
        with patch.object(window.job, "start", return_value=1) as start, \
                patch.object(launcher, "SameBoardComparisonWindow") as viewer:
            window.run_button.click()
            start.assert_called_once_with(context)
            window.job.succeeded.emit(1, execution)
        self.assertEqual(window.queue.started, [])
        viewer.assert_called_once_with(execution, window)
        self.assertIsNone(window._runs_window)
        self.assertIn("Completed — Stage 2: WON; Stage 3: WON", window.status_label.text())

    def test_selection_controls_r_target_and_board_support(self):
        window = self.launcher_window()
        self.assertTrue(all(window.algorithm_checks[key].isEnabled() for key in ALGORITHMS))
        r_check = window.algorithm_checks["S4_R"]
        for text, accepted in (("", True), ("abc", True), ("-3", True), ("120", False)):
            with patch.object(launcher.QInputDialog, "getText", return_value=(text, accepted)):
                r_check.setChecked(True)
            self.assertFalse(r_check.isChecked(), text)
            self.assertIsNone(window._r_target)
            self.assertIn("Stage4 R not selected", window.status_label.text())
        with patch.object(launcher.QInputDialog, "getText", return_value=("135", True)):
            r_check.setChecked(True)
        self.assertTrue(r_check.isChecked())
        self.assertEqual(window._r_target, "135")
        self.assertIn("target 135%", r_check.text())
        window.algorithm_checks["S2"].setChecked(False)
        window.algorithm_checks["K_P0"].setChecked(True)
        window.run_button.click()
        self.assertEqual(window.queue.started[0][1:], (("S3", "K_P0", "S4_R"), "135"))
        self.assertFalse(window.run_button.isEnabled())
        self.assertTrue(window.cancel_button.isEnabled())
        self.assertFalse(window.algorithm_group.isEnabled())
        r_check.setChecked(False)
        self.assertIsNone(window._r_target)

    def test_shuffled_arrival_orders_keep_rows_and_playback_mapped(self):
        keys = ("S3", "K_P0", "K_D23", "S4_S")
        for seed in range(4):
            with self.subTest(seed=seed):
                window = self.launcher_window()
                window.algorithm_checks["S2"].setChecked(False)
                for key in keys[1:]:
                    window.algorithm_checks[key].setChecked(True)
                window.run_button.click()
                runs = [self.runs[key] for key in keys]
                random.Random(seed).shuffle(runs)
                window.queue.deliver(runs)
                viewer = window._runs_window
                self.assertIsInstance(viewer, SameBoardRunsWindow)
                self.assertEqual(list(viewer.runs), list(keys))
                labels = [viewer.table.item(row, 0).text() for row in range(viewer.table.rowCount())]
                self.assertEqual(labels, ["Human", "Stage 3 V1", "K-P0", "K (K_D23)", "Stage4 S"])
                for key in keys:
                    viewer.shown_selector.setCurrentIndex(viewer.shown_selector.findData(key))
                    viewer.last_button.click()
                    self.assertEqual(viewer.index_label.text(),
                                     f"Action index {len(self.runs[key].moves)} / {len(self.runs[key].moves)}")
                    self.assertEqual(viewer.players[key].moves, self.runs[key].moves)

    def test_shown_result_change_never_runs_or_computes(self):
        window = self.launcher_window()
        window.algorithm_checks["S2"].setChecked(False)
        for key in ("K_LC1", "S4_M"):
            window.algorithm_checks[key].setChecked(True)
        window.run_button.click()
        window.queue.deliver([self.runs[key] for key in ("S4_M", "S3", "K_LC1")])
        viewer = window._runs_window
        started = list(window.queue.started)
        with self.forbid_computation():
            for _ in range(2):
                for index in range(viewer.shown_selector.count()):
                    viewer.shown_selector.setCurrentIndex(index)
                    viewer.next_button.click()
                    viewer.slider.setValue(viewer.slider.maximum())
        self.assertEqual(window.queue.started, started)

    def test_unexecuted_algorithms_are_absent(self):
        window = self.launcher_window()
        window.algorithm_checks["S2"].setChecked(False)
        window.algorithm_checks["S3"].setChecked(False)
        window.algorithm_checks["K_LC0"].setChecked(True)
        window.run_button.click()
        window.queue.deliver([self.runs["K_LC0"]])
        viewer = window._runs_window
        self.assertEqual(list(viewer.runs), ["K_LC0"])
        self.assertEqual([viewer.shown_selector.itemData(i) for i in range(viewer.shown_selector.count())],
                         ["HUMAN", "K_LC0"])
        self.assertEqual(viewer.table.rowCount(), 2)
        self.assertFalse(viewer.legacy_button.isVisibleTo(viewer))

    def test_runs_window_shows_settings_outcomes_and_time_dependence(self):
        runs = {"K_P0": self.runs["K_P0"], "S4_R": self.runs["S4_R"],
                "K_LC0": not_run("K_LC0", "LIMIT", "Algorithm limit 30 s reached."),
                "K_LC1": not_run("K_LC1", "CANCELLED", "Cancelled while running."),
                "K_D23": not_run("K_D23", "ERROR", "Execution failed: boom")}
        viewer = SameBoardRunsWindow(self.context, runs)
        self.windows.append(viewer)
        table = {viewer.table.item(row, 0).text(): [viewer.table.item(row, c).text()
                                                     for c in range(viewer.table.columnCount())]
                 for row in range(viewer.table.rowCount())}
        self.assertEqual({row: values[1] for row, values in table.items()},
                         {"Human": "LOST", "K-P0": "WON", "K-LC0": "LIMIT", "K-LC1": "CANCELLED",
                          "K (K_D23)": "ERROR", "Stage4 R": "WON"})
        self.assertIn(TIME_DEPENDENCE_NOTE, table["Stage4 R"][8])
        self.assertNotIn(TIME_DEPENDENCE_NOTE, table["K-P0"][8])
        self.assertIn("R target: 120%", table["Stage4 R"][7])
        self.assertIn("entry: FIXED_BOARD", table["K-P0"][7])
        self.assertEqual(table["K-LC0"][2:7], ["—"] * 5)
        self.assertIn("boom", table["K (K_D23)"][8])
        self.assertEqual(f"{runs['K_P0'].model_c_total_us / 1e6:.3f}", table["K-P0"][6])
        # Only played runs are offered for playback; failed ones stay in the table.
        self.assertEqual([viewer.shown_selector.itemData(i) for i in range(viewer.shown_selector.count())],
                         ["HUMAN", "K_P0", "S4_R"])
        labels = " ".join(label.text() for label in viewer.findChildren(launcher.QLabel))
        self.assertIn("not a speed ranking", labels)

    def test_runs_window_plays_flag_and_chord_by_index(self):
        run = self.runs["K_D23"]
        actions = [move.action for move in run.moves]
        self.assertIn("FLAG", actions)
        self.assertIn("CHORD", actions)
        viewer = SameBoardRunsWindow(self.context, {"K_D23": run})
        self.windows.append(viewer)
        viewer.shown_selector.setCurrentIndex(1)
        flag_index = actions.index("FLAG") + 1
        viewer.slider.setValue(flag_index)
        move = run.moves[flag_index - 1]
        observation = viewer.players["K_D23"].observation()
        self.assertEqual(int(observation[move.y][move.x]), CellState.FLAGGED.value)
        self.assertEqual(viewer.index_label.text(), f"Action index {flag_index} / {len(run.moves)}")
        viewer.last_button.click()
        self.assertEqual(viewer.players["K_D23"].status(), "WON")
        viewer.first_button.click()
        self.assertTrue(all(int(v) == CellState.HIDDEN.value
                            for row in viewer.players["K_D23"].observation() for v in row))
        viewer.shown_selector.setCurrentIndex(0)
        self.assertEqual(viewer.index_label.text(), "Action index 0 / 1")
        viewer.shown_selector.setCurrentIndex(1)
        self.assertEqual(viewer.index_label.text(), f"Action index 0 / {len(run.moves)}")

    def test_cancel_during_run_keeps_finished_results(self):
        window = self.launcher_window()
        for key in ("K_P0", "S4_S"):
            window.algorithm_checks[key].setChecked(True)
        with patch.object(window.job, "start", return_value=7):
            window.run_button.click()
        execution = run_same_board_comparison(self.context)
        window.job.succeeded.emit(7, execution)
        self.assertEqual(window.queue.started[0][1], ("K_P0", "S4_S"))
        window.queue.deliver([self.runs["K_P0"]], finish=False)
        window.cancel_button.click()
        self.assertEqual(window.queue.cancel_calls, 1)
        self.assertFalse(window.cancel_button.isEnabled())
        window.queue.deliver([not_run("S4_S", "CANCELLED", "Cancelled while running.")])
        self.assertIn("Cancelled", window.status_label.text())
        self.assertIsNone(window._runs_window)  # A cancelled comparison is not auto-opened.
        self.assertTrue(window.open_result_button.isEnabled())
        window.open_result_button.click()
        viewer = window._runs_window
        self.assertEqual({key: run.outcome for key, run in viewer.runs.items()},
                         {"S2": "WON", "S3": "WON", "K_P0": "WON", "S4_S": "CANCELLED"})
        self.assertTrue(viewer.legacy_button.isVisibleTo(viewer))
        with patch.object(launcher, "SameBoardComparisonWindow") as legacy:
            viewer.legacy_button.click()
        legacy.assert_called_once_with(execution, window)

    def test_legacy_cancel_marks_pair_and_queue_cancelled(self):
        window = self.launcher_window()
        window.algorithm_checks["K_P0"].setChecked(True)
        with patch.object(window.job, "start", return_value=9), patch.object(window.job, "cancel"):
            window.run_button.click()
            window.cancel_button.click()
            window.job.cancelled.emit(9)
        self.assertEqual(window.queue.started, [])
        self.assertEqual({key: run.outcome for key, run in window._runs.items()},
                         {"S2": "CANCELLED", "S3": "CANCELLED", "K_P0": "CANCELLED"})
        self.assertTrue(window.run_button.isEnabled())

    def test_main_dispatches_new_worker_flag(self):
        import main
        with patch("sys.argv", ["main.py", "--same-board-algorithm-worker", "a", "b"]), \
                patch("same_board_algorithm_worker.main", return_value=0) as worker_main:
            self.assertEqual(main.main(), 0)
        worker_main.assert_called_once_with(["--same-board-algorithm-worker", "a", "b"])


if __name__ == "__main__":
    unittest.main()
