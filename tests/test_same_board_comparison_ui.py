"""Offscreen result-viewer tests using completed, genuine small-board evidence."""

import ast
from contextlib import ExitStack
from copy import deepcopy
import os
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
try:
    from PyQt5.QtCore import QEvent, Qt, QTimer
    from PyQt5.QtGui import QCloseEvent, QFontDatabase
    from PyQt5.QtTest import QSignalSpy, QTest
    from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea, QWidget
except ImportError:
    QApplication = None
else:
    import same_board_comparison_ui as ui
    from same_board_comparison_ui import SameBoardComparisonWindow
    from stage3_visualizer_ui import CELL_SIZE, Stage3VisualizerCell

from core_engine import CellState, GameStatus
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from same_board_comparison import HumanComparisonContext
from same_board_playback import ComparisonRun, SameBoardPlayback
from same_board_runner import run_same_board_comparison
from tests.test_same_board_playback import captured_comparison
from tests.test_same_board_runner import human_context


RUNS = (ComparisonRun.HUMAN, ComparisonRun.STAGE2, ComparisonRun.STAGE3)


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class SameBoardComparisonUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # Windows' offscreen plugin can expose no fonts at all. Use an installed
        # font for real text geometry/painting, then release this test-owned font.
        cls._test_font_id = -1
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"
        if not QFontDatabase().families() and font_path.is_file():
            cls._test_font_id = QFontDatabase.addApplicationFont(str(font_path))
        # Producers run only to prepare already-completed fixtures, never in UI.
        cls.execution, cls.prefixes = captured_comparison()
        cls.canonical = run_same_board_comparison(human_context())
        cls.loss = run_same_board_comparison(human_context(mined_origin=True, with_trace=True))
        full_replay = ReplayData(ReplayBoard(30, 16, 2, {(0, 0), (29, 15)}), (
            ReplayEvent(0.0, 1, 1, "FLAG"), ReplayEvent(2.5, 0, 0, "OPEN"),
        ))
        cls.full_size = run_same_board_comparison(
            HumanComparisonContext(full_replay, declared_full_game_human=True)
        )

    @classmethod
    def tearDownClass(cls):
        if cls._test_font_id >= 0:
            QFontDatabase.removeApplicationFont(cls._test_font_id)

    def setUp(self):
        self.windows = []
        self.addCleanup(self.close_windows)
        self.window = self.create_window(self.execution)

    def create_window(self, execution, parent=None):
        window = SameBoardComparisonWindow(execution, parent)
        self.windows.append(window)
        return window

    def close_windows(self):
        for window in self.windows:
            try:
                window.close()
            except RuntimeError:  # WA_DeleteOnClose may already have run.
                pass
        self.app.processEvents()

    def select(self, run, window=None):
        window = window or self.window
        window.run_selector.setCurrentIndex(window.run_selector.findData(run))

    def indices(self, window=None):
        playback = (window or self.window).playback
        return tuple(playback.index_for(run) for run in RUNS)

    def rendered(self, window=None):
        window = window or self.window
        board = window.execution.context.layout.board
        return [[window.cells[x, y].logical_state for x in range(board.width)]
                for y in range(board.height)]

    def summary(self, window=None):
        return {name: tuple(label.text() for label in labels)
                for name, labels in (window or self.window).summary_labels.items()}

    def assert_presentation(self, window=None):
        window = window or self.window
        player = window.playback
        self.assertEqual(self.rendered(window), player.get_observation())
        self.assertEqual(window.slider.minimum(), 0)
        self.assertEqual(window.slider.maximum(), player.action_count())
        self.assertEqual(window.slider.value(), player.current_index)
        self.assertEqual(window.index_label.text(), f"Action index {player.current_index} / {player.action_count()}")
        self.assertEqual(window.status_label.text(), f"Current reconstructed status: {player.status.name}")

    def test_window_owns_one_coordinator_and_one_read_only_board(self):
        parent = QWidget()
        self.addCleanup(parent.close)
        with patch.object(ui, "SameBoardPlayback", wraps=SameBoardPlayback) as factory:
            window = self.create_window(self.execution, parent)
        factory.assert_called_once_with(self.execution)
        self.assertEqual(window.windowType(), Qt.Window)
        self.assertTrue(window.testAttribute(Qt.WA_DeleteOnClose))
        self.assertIs(window.parent(), parent)
        self.assertIs(window.execution, self.execution)
        self.assertIs(window.playback.execution, self.execution)
        self.assertEqual(len(window.findChildren(QScrollArea)), 1)
        self.assertIs(window.scroll_area.widget(), window.board_container)
        self.assertFalse(window.scroll_area.widgetResizable())
        self.assertEqual(len(window.findChildren(Stage3VisualizerCell)), 24)
        self.assertEqual([window.run_selector.itemText(i) for i in range(3)], ["Human", "Stage 2", "Stage 3"])
        self.assertEqual(window.run_selector.count(), 3)
        self.assertEqual([window.run_selector.itemData(i) for i in range(3)], list(RUNS))
        self.assertIs(window.playback.selected_run, ComparisonRun.HUMAN)
        self.assertEqual(self.indices(window), (0, 0, 0))

    def test_construction_failure_propagates_to_future_owner(self):
        with patch.object(ui, "SameBoardPlayback", side_effect=ValueError("invalid completed source")):
            with self.assertRaisesRegex(ValueError, "invalid completed source"):
                SameBoardComparisonWindow(self.execution)

    def test_all_three_initial_boards_are_hidden(self):
        for run in RUNS:
            self.select(run)
            self.assertEqual(self.rendered(), [[CellState.HIDDEN] * 6 for _ in range(4)])
            self.assert_presentation()

    def test_first_middle_terminal_and_arbitrary_seeks_match_original_runs(self):
        for run in RUNS:
            self.select(run)
            count = self.window.playback.action_count()
            for index in (1, count // 2, count, 3, 0, count - 1):
                with self.subTest(run=run, index=index):
                    self.window.slider.setValue(index)
                    observation, status = self.prefixes[run][index]
                    self.assertEqual(self.rendered(), observation)
                    self.assertEqual(self.window.playback.status, status)
                    self.assert_presentation()

    def test_render_uses_injected_observation_even_at_a_source_mine(self):
        window = self.window
        self.assertIn((4, 0), self.execution.context.layout.board.mine_positions)
        for value in (*range(9), CellState.HIDDEN, CellState.FLAGGED,
                      CellState.MINE, CellState.EXPLODED, CellState.FALSE_FLAG):
            observation = [[CellState.HIDDEN] * 6 for _ in range(4)]
            observation[0][4] = value
            with patch.object(window.playback, "get_observation", return_value=observation):
                window.refresh()
            self.assertEqual(self.rendered(), observation)

    def test_terminal_public_win_and_loss_states(self):
        self.window.on_last()
        self.assertIs(self.window.playback.status, GameStatus.WON)
        self.assert_presentation()
        window = self.create_window(self.full_size)
        window.on_last()
        self.assertIs(window.playback.status, GameStatus.LOST)
        self.assertEqual(window.cells[0, 0].logical_state, CellState.EXPLODED)
        self.assertEqual(window.cells[29, 15].logical_state, CellState.MINE)
        self.assertEqual(window.cells[1, 1].logical_state, CellState.FALSE_FLAG)
        self.assert_presentation(window)

    def test_selector_restores_three_independent_indices_without_seek(self):
        window = self.window
        for run, index in zip(RUNS, (3, 5, 2)):
            self.select(run)
            window.slider.setValue(index)
        with patch.object(window.playback, "select", wraps=window.playback.select) as select, \
             patch.object(window.playback, "go_to", side_effect=AssertionError("selection seek")) as seek:
            for run in (*RUNS, *reversed(RUNS)):
                self.select(run)
                self.assertEqual(self.indices(), (3, 5, 2))
                self.assert_presentation()
            self.assertGreater(select.call_count, 0)
            seek.assert_not_called()

    def test_shorter_slider_range_does_not_clamp_another_player(self):
        window = self.window
        self.assertEqual(tuple(window.playback.action_count(run) for run in RUNS), (20, 21, 15))
        self.select(ComparisonRun.STAGE2)
        window.on_last()
        with patch.object(window.playback, "go_to", side_effect=AssertionError("range-change seek")) as seek:
            self.select(ComparisonRun.STAGE3)
            self.assertEqual((window.slider.maximum(), window.slider.value()), (15, 0))
            self.assertEqual(self.indices(), (0, 21, 0))
            self.select(ComparisonRun.STAGE2)
            self.assertEqual((window.slider.maximum(), window.slider.value()), (21, 21))
            seek.assert_not_called()

    def test_out_of_range_navigation_is_rejected_not_mapped(self):
        self.select(ComparisonRun.STAGE3)
        self.window.slider.setValue(2)
        self.window.on_slider_changed(21)  # A valid Stage-2 index is invalid here.
        self.assertEqual(self.indices(), (0, 0, 2))
        self.assertEqual(self.window.slider.value(), 2)
        self.assertIn("Playback error:", self.window.error_label.text())
        self.assert_presentation()

    def test_all_navigation_buttons_affect_selected_run_only_and_do_not_wrap(self):
        window = self.window
        for run in RUNS:
            self.select(run)
            before = self.indices()
            self.assertFalse(window.first_button.isEnabled())
            self.assertFalse(window.previous_button.isEnabled())
            self.assertTrue(window.next_button.isEnabled())
            self.assertTrue(window.last_button.isEnabled())
            window.next_button.click()
            self.assertEqual(window.playback.current_index, 1)
            window.previous_button.click()
            self.assertEqual(window.playback.current_index, 0)
            window.on_previous()
            self.assertEqual(window.playback.current_index, 0)
            window.last_button.click()
            self.assertEqual(window.playback.current_index, window.playback.action_count())
            self.assertFalse(window.next_button.isEnabled())
            self.assertFalse(window.last_button.isEnabled())
            self.assertTrue(window.first_button.isEnabled())
            self.assertTrue(window.previous_button.isEnabled())
            window.on_next()
            self.assertEqual(window.playback.current_index, window.playback.action_count())
            window.first_button.click()
            self.assertEqual(window.playback.current_index, 0)
            for other, old in zip(RUNS, before):
                if other is not run:
                    self.assertEqual(window.playback.index_for(other), old)
            self.assert_presentation()

    def test_refresh_is_read_only_and_preserves_preexisting_signal_blocks(self):
        window = self.window
        for run in RUNS:
            window.playback.select(run)
            window.playback.go_to(3)
            with ExitStack() as stack:
                mocks = [stack.enter_context(patch.object(window.playback, method,
                          side_effect=AssertionError(method))) for method in ("select", "go_to", "next", "previous")]
                for blocked in (False, True):
                    window.slider.blockSignals(blocked)
                    window.run_selector.blockSignals(blocked)
                    window.refresh()
                    self.assertEqual(window.slider.signalsBlocked(), blocked)
                    self.assertEqual(window.run_selector.signalsBlocked(), blocked)
                    self.assert_presentation()
                for mocked in mocks:
                    mocked.assert_not_called()
            window.slider.blockSignals(False)
            window.run_selector.blockSignals(False)

    def test_current_status_is_not_final_outcome_including_first_action_loss(self):
        window = self.create_window(self.loss)
        final = self.summary(window)["Final outcome"]
        self.assertEqual(final, ("WON", "LOST", "LOST"))
        for run in RUNS:
            self.select(run, window)
            self.assertEqual(window.status_label.text(), "Current reconstructed status: PLAYING")
            if run is not ComparisonRun.HUMAN:
                window.next_button.click()
                self.assertEqual(window.playback.current_index, 1)
                self.assertEqual(window.status_label.text(), "Current reconstructed status: LOST")
            else:
                window.last_button.click()
                self.assertEqual(window.status_label.text(), "Current reconstructed status: WON")
            self.assertEqual(self.summary(window)["Final outcome"], final)
            self.assertTrue(window.error_label.isHidden())

    def test_summary_uses_exact_metrics_and_separate_units(self):
        for execution in (self.execution, self.canonical, self.loss):
            window = self.create_window(execution)
            human, s2, s3 = execution.human_metrics, execution.stage2_metrics, execution.stage3_metrics
            metrics = (human, s2, s3)
            self.assertEqual(self.summary(window), {
                "Final outcome": tuple(m.outcome.name for m in metrics),
                "Semantic actions": tuple(str(m.actions.semantic_action_count) for m in metrics),
                "OPEN inputs": tuple(str(m.actions.open_count) for m in metrics),
                "FLAG inputs (incl. unflag)": tuple(str(m.actions.flag_input_count) for m in metrics),
                "CHORD inputs": tuple(str(m.actions.chord_count) for m in metrics),
                "Human Replay elapsed": (f"{human.replay_elapsed_seconds} s", "—", "—"),
                "Model C cost through termination": ("—", f"{s2.model_c_total_us:,} µs", f"{s3.model_c_total_us:,} µs"),
                "Decision compute total": ("—", f"{s2.decision_compute_total_ns:,} ns", f"{s3.decision_compute_total_ns:,} ns"),
            })
            before = self.summary(window)
            for run in RUNS:
                self.select(run, window)
                window.on_last()
                self.assertEqual(self.summary(window), before)
            labels = " ".join(label.text().lower() for label in window.findChildren(QLabel))
            for forbidden in ("winner", "ranking", "faster", "slower", "%", "score", "speed", "time-to-win"):
                self.assertNotIn(forbidden, labels)

    def test_canonical_first_open_qualification_and_caveat(self):
        window = self.create_window(self.canonical)
        text = window.qualification_label.text()
        for expected in ("Exact same fixed layout verified", "Human first recorded event: OPEN (0, 0)",
                         "Human first OPEN: (0, 0); zero-based Replay event index 0", "Prelude before first OPEN: no",
                         "Stage 2 first action: OPEN (0, 0)", "Stage 3 first action: OPEN (0, 0)",
                         "Solver origin (0, 0): not a mine", "Matching recorded start: yes — Human event 0 is OPEN (0, 0)."):
            self.assertIn(expected, text)
        for expected in ("does not establish", "historical mine placement", "execution semantics",
                         "exclusively-Human provenance", "controlled experiment"):
            self.assertIn(expected, window.caveat_label.text())

    def test_prelude_first_open_qualification_keeps_original_event_position(self):
        text = self.window.qualification_label.text()
        self.assertIn("Human first recorded event: CHORD (0, 0)", text)
        self.assertIn("Human first OPEN: (0, 0); zero-based Replay event index 3", text)
        self.assertIn("Prelude before first OPEN: yes", text)
        self.assertIn("Matching recorded start: no — prelude before first OPEN.", text)

    def test_other_human_open_and_mined_origin_are_factual_not_failure(self):
        window = self.create_window(self.loss)
        text = window.qualification_label.text()
        self.assertIn("Human first recorded event: OPEN (1, 0)", text)
        self.assertIn("Human first OPEN: (1, 0); zero-based Replay event index 0", text)
        self.assertIn("first OPEN targets (1, 0)", text)
        self.assertIn("Solver origin (0, 0): mine", text)
        self.assertIn("ordinary fresh-game first-OPEN placement safety does not apply",
                      " ".join(label.text() for label in window.findChildren(QLabel)))
        self.assertTrue(window.error_label.isHidden())

    def test_mouse_trace_is_default_off_original_and_mouse_transparent(self):
        window = self.window
        overlay = window.mouse_trace_overlay
        replay = self.execution.context.human_replay
        self.assertFalse(window.mouse_trace_checkbox.isChecked())
        self.assertTrue(window.mouse_trace_checkbox.isEnabled())
        self.assertTrue(overlay.isHidden())
        self.assertIs(overlay._trace, replay.mouse_trace)
        self.assertIs(overlay._events, replay.events)
        self.assertIs(overlay.parent(), window.board_container)
        self.assertEqual(overlay.geometry(), window.board_container.rect())
        self.assertEqual(overlay._cell_size, CELL_SIZE)
        self.assertTrue(overlay.testAttribute(Qt.WA_TransparentForMouseEvents))
        self.assertEqual(window.mouse_trace_checkbox.text(), "Show Human Mouse Trace (entire recording)")
        self.assertIn("independent of the current action index", window.mouse_trace_checkbox.toolTip())

    def test_absent_mouse_trace_never_enables_or_displays_overlay(self):
        window = self.create_window(self.canonical)
        for run in RUNS:
            self.select(run, window)
            window.on_last()
            self.assertFalse(window.mouse_trace_checkbox.isEnabled())
            self.assertTrue(window.mouse_trace_overlay.isHidden())
            self.assertIsNone(window.mouse_trace_overlay._trace)

    def test_mouse_trace_is_human_only_and_remembers_local_preference(self):
        window = self.window
        window.show()
        self.app.processEvents()
        window.mouse_trace_checkbox.click()
        self.assertTrue(window.mouse_trace_overlay.isVisible())
        for run in (ComparisonRun.STAGE2, ComparisonRun.STAGE3):
            self.select(run)
            self.assertTrue(window.mouse_trace_checkbox.isChecked())
            self.assertFalse(window.mouse_trace_checkbox.isEnabled())
            self.assertTrue(window.mouse_trace_overlay.isHidden())
            window.on_last()
            self.assertTrue(window.mouse_trace_overlay.isHidden())
        self.select(ComparisonRun.HUMAN)
        self.assertTrue(window.mouse_trace_checkbox.isEnabled())
        self.assertTrue(window.mouse_trace_overlay.isVisible())

    def test_whole_trace_geometry_and_identity_are_static_at_every_human_index(self):
        window = self.window
        window.mouse_trace_checkbox.setChecked(True)
        overlay = window.mouse_trace_overlay
        geometry = overlay._presentation_geometry()
        original = deepcopy(self.execution.context.human_replay)
        for index in range(window.playback.action_count() + 1):
            window.slider.setValue(index)
            self.assertIs(overlay._presentation_geometry(), geometry)
            self.assertIs(overlay._trace, self.execution.context.human_replay.mouse_trace)
            self.assertIs(overlay._events, self.execution.context.human_replay.events)
        # Both recorded endpoints remain present at index zero too.
        window.on_first()
        self.assertEqual(len(geometry[1]), 2)
        self.assertEqual(self.execution.context.human_replay, original)

    def test_navigation_error_preserves_state_restores_slider_and_can_clear(self):
        window = self.window
        window.show()
        window.slider.setValue(3)
        before = (self.indices(), self.rendered(), self.summary())
        with patch.object(window.playback, "go_to", side_effect=ValueError("<bad seek>")):
            window.slider.setValue(7)
        self.assertEqual((self.indices(), self.rendered(), self.summary()), before)
        self.assertEqual(window.slider.value(), 3)
        self.assertEqual(window.error_label.text(), "Playback error: <bad seek>")
        self.assertEqual(window.error_label.textFormat(), Qt.PlainText)
        self.assertFalse(window.error_label.isHidden())
        window.next_button.click()
        self.assertEqual(window.playback.current_index, 4)
        self.assertTrue(window.error_label.isHidden())
        self.assertEqual(window.error_label.text(), "")

    def test_stage3_real_failed_step_preserves_committed_board(self):
        self.select(ComparisonRun.STAGE3)
        self.window.slider.setValue(2)
        before = (self.indices(), self.rendered(), self.summary())
        from core_engine import MinesweeperEngine
        step = MinesweeperEngine.step

        def fail_after_step(engine, *args):
            step(engine, *args)
            raise ValueError("step failed after candidate mutation")

        with patch.object(MinesweeperEngine, "step", fail_after_step):
            self.window.next_button.click()
        self.assertEqual((self.indices(), self.rendered(), self.summary()), before)
        self.assertIn("candidate mutation", self.window.error_label.text())
        self.window.next_button.click()
        self.assertEqual(self.window.playback.current_index, 3)
        self.assertTrue(self.window.error_label.isHidden())

    def test_no_producers_admission_job_or_model_evaluation_in_viewer(self):
        forbidden = (
            "same_board_runner.run_same_board_comparison", "same_board_runner.run_fixed_layout_solvers",
            "same_board_runner.compose_same_board_execution", "same_board_runner.run_simple",
            "same_board_runner.run_stage3", "simple_runner.run_simple", "stage3_runner.run_stage3",
            "simple_runner.analyze_position", "simple_decision.analyze_position",
            "stage3_runner.plan_position", "stage3_planner.plan_position",
            "same_board_execution_worker.calculate_same_board_execution",
            "same_board_execution_job.SameBoardExecutionJob.__init__",
            "same_board_execution_job.SameBoardExecutionJob.start",
            "same_board_execution_job.SameBoardExecutionJob.shutdown",
            "same_board_runner.authenticate_model_c", "same_board_runner.evaluate_ordered_actions",
            "benchmark_modeled_time.authenticate_model_c", "benchmark_modeled_time.evaluate_ordered_actions",
            "stage3_physical.action_cost", "stage3_physical.load_timing_table",
            "benchmark_board.generate_board", "core_engine.random.sample",
            "same_board_comparison.HumanComparisonContext.__post_init__",
            "stage3_visualizer_ui.Stage3VisualizerWindow.__init__",
            "stage3_trace_player.Stage3TracePlayer.__init__",
            "stage3_modeled_playback.Stage3ModeledPlayback.__init__",
        )
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch(name, side_effect=AssertionError(name))) for name in forbidden]
            window = self.create_window(self.execution)
            for run in RUNS:
                self.select(run, window)
                window.on_last()
                window.on_first()
                window.on_next()
                window.on_previous()
                window.slider.setValue(3)
                window.mouse_trace_checkbox.setChecked(True)
                window.refresh()
                self.assertTrue(window.error_label.isHidden(), window.error_label.text())
            window.close()
            for mocked in mocks:
                mocked.assert_not_called()

    def test_sources_metrics_and_native_evidence_keep_identity_and_deep_equality(self):
        window = self.window
        execution = self.execution
        before = deepcopy(execution)
        identities = (
            execution.context, execution.context.human_replay, execution.context.human_replay.mouse_trace,
            execution.stage2_result, execution.stage2_result.replay_data, execution.stage2_traces,
            execution.stage3_result, execution.stage3_result.traces,
            execution.human_metrics, execution.stage2_metrics, execution.stage3_metrics,
        )
        for run in RUNS:
            self.select(run)
            for index in (3, window.playback.action_count(), 0, 1):
                window.slider.setValue(index)
                window.mouse_trace_checkbox.setChecked(not window.mouse_trace_checkbox.isChecked())
        self.assertEqual(execution, before)
        after = window.execution
        for original, retained in zip(identities, (
            after.context, after.context.human_replay, after.context.human_replay.mouse_trace,
            after.stage2_result, after.stage2_result.replay_data, after.stage2_traces,
            after.stage3_result, after.stage3_result.traces,
            after.human_metrics, after.stage2_metrics, after.stage3_metrics,
        )):
            self.assertIs(original, retained)
        self.assertIs(window.playback.execution, execution)
        for old, new in zip(execution.stage2_traces, after.stage2_traces):
            self.assertIs(old.decision, new.decision)
        for old, new in zip(execution.stage3_result.traces, after.stage3_result.traces):
            self.assertIs(old.decision, new.decision)

    def test_board_mouse_clicks_and_paint_never_navigate_or_mutate(self):
        window = self.window
        window.show()
        self.app.processEvents()
        window.mouse_trace_checkbox.setChecked(True)
        before = deepcopy(self.execution)
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch.object(window.playback, name,
                      side_effect=AssertionError(name))) for name in ("select", "go_to", "next", "previous")]
            for button in (Qt.LeftButton, Qt.RightButton, Qt.MiddleButton):
                QTest.mouseClick(window.cells[0, 0], button)
            self.assertFalse(window.board_container.grab().isNull())
            for mocked in mocks:
                mocked.assert_not_called()
        self.assertEqual(self.indices(), (0, 0, 0))
        self.assertEqual(self.execution, before)

    def test_full_size_board_keeps_fixed_cells_and_scrollable_viewport(self):
        window = self.create_window(self.full_size)
        window.resize(650, 700)
        window.show()
        self.app.processEvents()
        self.assertEqual((window.board_container.width(), window.board_container.height()),
                         (30 * CELL_SIZE, 16 * CELL_SIZE))
        self.assertEqual(len(window.cells), 480)
        self.assertTrue(all((cell.width(), cell.height()) == (CELL_SIZE, CELL_SIZE)
                            for cell in window.cells.values()))
        self.assertGreater(window.scroll_area.horizontalScrollBar().maximum(), 0)
        self.assertGreater(window.scroll_area.verticalScrollBar().maximum(), 0)
        for bar in (window.scroll_area.horizontalScrollBar(), window.scroll_area.verticalScrollBar()):
            bar.setValue(bar.maximum())
            self.assertEqual(bar.value(), bar.maximum())
        self.assertGreater(window.scroll_area.viewport().height(), 0)
        self.select(ComparisonRun.STAGE3, window)
        window.on_next()
        self.assertEqual(window.status_label.text(), "Current reconstructed status: LOST")

    def test_viewer_has_no_timer_process_controls_or_hidden_render_access(self):
        window = self.window
        self.assertEqual(window.findChildren(QTimer), [])
        self.assertEqual({button.text() for button in window.findChildren(QPushButton)},
                         {"First", "Previous", "Next", "Last"})
        for name in ("job", "worker", "process", "token", "timer", "speed", "modeled_playback"):
            self.assertFalse(hasattr(window, name), name)
        tree = ast.parse(Path(ui.__file__).read_text(encoding="utf-8"))
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertFalse(attributes & {"mine_positions", "terminal_observation", "_human", "_stage2", "_stage3"})
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertFalse(imports & {"ui_manager", "same_board_execution_job", "same_board_execution_worker", "subprocess"})

    def test_wrapped_factual_labels_have_room_for_their_complete_text(self):
        window = self.create_window(self.full_size)
        window.resize(1000, 820)
        window.show()
        self.app.processEvents()
        for label in window.findChildren(QLabel):
            if label.wordWrap() and not label.isHidden():
                with self.subTest(text=label.text()):
                    self.assertTrue(label.hasHeightForWidth())
                    self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))

    def test_close_emits_once_and_late_navigation_is_inert(self):
        window = self.window
        signal = QSignalSpy(window.closed)
        before = self.indices()
        self.assertTrue(window.close())
        self.assertTrue(window._closed)
        event = QCloseEvent()
        window.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(len(signal), 1)
        for operation in (window.on_first, window.on_previous, window.on_next, window.on_last,
                          lambda: window.on_slider_changed(3), lambda: window.on_run_changed(1), window.refresh):
            operation()
        self.assertEqual(self.indices(), before)

    def test_ignored_close_keeps_viewer_live_and_emits_nothing(self):
        window = self.window
        signal = QSignalSpy(window.closed)
        event = QCloseEvent()
        with patch.object(QWidget, "closeEvent", side_effect=lambda event: event.ignore()):
            window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertFalse(window._closed)
        self.assertEqual(len(signal), 0)
        window.on_next()
        self.assertEqual(window.playback.current_index, 1)

    def test_accepted_close_deletes_qt_window_after_deferred_events(self):
        from PyQt5 import sip

        window = self.window
        signal = QSignalSpy(window.closed)
        window.show()
        self.assertTrue(window.close())
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertTrue(sip.isdeleted(window))
        self.assertEqual(len(signal), 1)

    def test_recreated_viewer_has_fresh_indices_and_overlay_preference(self):
        old = self.window
        for run, index in zip(RUNS, (3, 5, 2)):
            self.select(run)
            old.slider.setValue(index)
        old.mouse_trace_checkbox.setChecked(True)
        old.close()
        window = self.create_window(self.execution)
        self.assertIs(window.execution, self.execution)
        self.assertIs(window.playback.selected_run, ComparisonRun.HUMAN)
        self.assertEqual(self.indices(window), (0, 0, 0))
        self.assertFalse(window.mouse_trace_checkbox.isChecked())


if __name__ == "__main__":
    unittest.main()
