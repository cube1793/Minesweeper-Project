"""Deterministic offscreen presentation tests; fixtures never run a solver."""

import ast
import builtins
from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
try:
    from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt5.QtGui import QCloseEvent, QMouseEvent
    from PyQt5.QtTest import QSignalSpy, QTest
    from PyQt5.QtWidgets import QApplication, QLabel, QStyle, QStyleOptionSlider, QWidget
except ImportError:
    QApplication = None
else:
    import stage3_visualizer_ui
    from stage3_visualizer_ui import CELL_SIZE, Stage3VisualizerWindow

from benchmark_board import BenchmarkBoard, BenchmarkSetSpec, calculate_board_fingerprint
from core_engine import Action, CellState, GameStatus
from simple_algorithm import SimpleMove
from stage3_execution import Stage3Execution
from stage3_runner import Stage3ActionTrace, Stage3RunResult
from stage3_trace_player import Stage3TracePlayer


H, F = CellState.HIDDEN, CellState.FLAGGED
P, W, L = GameStatus.PLAYING, GameStatus.WON, GameStatus.LOST


def execution_fixture(kind="win"):
    """Small hand-recorded streams, including a deliberately wrong loss flag.

    This mirrors the trace-player tests' ability to reconstruct public physical
    inputs without planner evidence. No generation, planning or worker runs.
    """
    if kind == "win":
        width, height, mines = 3, 2, frozenset({(1, 0)})
        actions = (
            (Action.OPEN, 0, 0, P, 1, 0),
            (Action.FLAG, 1, 0, P, 0, 1),
            (Action.CHORD, 0, 0, P, 2, 0),
            (Action.OPEN, 2, 0, P, 1, 0),
            (Action.OPEN, 2, 1, W, 1, 0),
        )
    elif kind == "loss":
        width, height, mines = 6, 1, frozenset({(1, 0), (4, 0), (5, 0)})
        actions = (
            (Action.OPEN, 0, 0, P, 1, 0),
            (Action.FLAG, 2, 0, P, 0, 1),
            (Action.FLAG, 5, 0, P, 0, 1),
            (Action.OPEN, 1, 0, L, 0, 0),
        )
    elif kind == "flood":
        width, height, mines = 4, 1, frozenset({(1, 0)})
        actions = ((Action.OPEN, 0, 0, P, 1, 0), (Action.OPEN, 3, 0, W, 2, 0))
    else:
        raise ValueError(kind)
    spec = BenchmarkSetSpec("VISUALIZER_TEST_V1", width, height, len(mines), 0, 0, "V1", "game_index")
    board = BenchmarkBoard(17, 17, mines, calculate_board_fingerprint(width, height, len(mines), mines))
    traces, cursor = [], (0, 0)
    for index, (action, x, y, status, safe_delta, flag_delta) in enumerate(actions):
        traces.append(Stage3ActionTrace(
            SimpleMove(action, x, y), None, 987654321 if index else None, cursor,
            126005 + index * 100003, status, safe_delta, flag_delta,
        ))
        cursor = (x, y)
    return Stage3Execution(spec, board, Stage3RunResult(actions[-1][3], tuple(traces)))


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class Stage3VisualizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.windows = []
        self.addCleanup(self.close_windows)
        self.execution = execution_fixture()
        self.window = self.create_window(self.execution)

    def create_window(self, execution, parent=None):
        window = Stage3VisualizerWindow(execution, parent)
        self.windows.append(window)
        return window

    def close_windows(self):
        for window in self.windows:
            try:
                window.close()
            except RuntimeError:  # WA_DeleteOnClose may already have run.
                pass
        self.app.processEvents()

    def assert_index(self, window, index):
        oracle = Stage3TracePlayer(window.player.execution)
        oracle.go_to(index)
        self.assertEqual(window.player.current_index, index)
        self.assertEqual(window.player.current_trace, oracle.current_trace)
        self.assertEqual(window.player.status, oracle.status)
        self.assertEqual(window.player.get_observation(), oracle.get_observation())
        self.assertEqual(window.player.cumulative_modeled_us, oracle.cumulative_modeled_us)
        self.assertEqual(window.slider.value(), index)
        self.assertEqual(window.step_label.text(), f"Step {index} / {oracle.step_count}")
        self.assertEqual(window.overlay.current_cursor, oracle.current_cursor)
        self.assertEqual(window.status_label.text(), f"Current reconstructed status: {oracle.status.name}")
        for y, row in enumerate(oracle.get_observation()):
            for x, value in enumerate(row):
                self.assertEqual(window.cells[(x, y)].logical_state, value)

    def test_construction_identity_and_independent_players(self):
        window = self.window
        self.assertIsInstance(window.player, Stage3TracePlayer)
        self.assertIs(window.player.execution, self.execution)
        self.assertEqual(window.windowTitle(), "Stage-3 Visualizer")
        self.assertIn("Stage-3 V1 / Model C", window.title_label.text())
        self.assertIn(self.execution.spec.benchmark_set_id, window.identity_label.text())
        self.assertIn("Game index: 17", window.identity_label.text())
        self.assertIn("Final result: WON", window.identity_label.text())
        self.assertIn(self.execution.board.board_fingerprint, window.fingerprint_label.text())
        self.assertTrue(window.isWindow())
        self.assertTrue(window.testAttribute(Qt.WA_DeleteOnClose))
        self.assertIs(window.timer.parent(), window)
        other = self.create_window(self.execution, window)
        self.assertTrue(other.isWindow())
        self.assertIsNot(window.player, other.player)
        other.on_last()
        self.assert_index(window, 0)
        loss = self.create_window(execution_fixture("loss"))
        self.assertIn("Final result: LOST", loss.identity_label.text())
        self.assertIn("PLAYING", loss.status_label.text())

    def test_initial_board_cursor_time_and_placeholders(self):
        window = self.window
        self.assert_index(window, 0)
        self.assertEqual(window.player.get_observation(), [[H, H, H], [H, H, H]])
        self.assertEqual(window.overlay.current_cursor, (0, 0))
        self.assertIsNone(window.overlay.movement_start)
        self.assertIsNone(window.overlay.action_target)
        self.assertIsNone(window.overlay.movement_line)
        self.assertEqual(window.detail_labels["cumulative_modeled_us"].text(), "0 µs")
        for key in ("action", "target", "movement", "modeled_action_us", "status_after",
                    "safe_cells_opened_delta", "explicit_flag_delta"):
            self.assertEqual(window.detail_labels[key].text(), "—")
        for cell in window.cells.values():
            self.assertEqual(cell.logical_state, H)
            self.assertEqual(cell.text(), "")
            self.assertEqual((cell.width(), cell.height()), (28, 28))

    def test_hidden_flag_number_and_zero_rendering_from_real_observations(self):
        window = self.window
        window.on_next()
        self.assertEqual(window.cells[(0, 0)].logical_state, 1)
        self.assertEqual(window.cells[(0, 0)].text(), "1")
        self.assertIn("#0000ff", window.cells[(0, 0)].styleSheet())
        self.assertEqual(window.cells[(1, 0)].logical_state, H)
        self.assertEqual(window.cells[(1, 0)].text(), "")
        window.on_next()
        self.assertEqual(window.cells[(1, 0)].logical_state, F)
        self.assertEqual(window.cells[(1, 0)].text(), "⚑")
        flood = self.create_window(execution_fixture("flood"))
        flood.on_last()
        self.assertEqual(flood.cells[(3, 0)].logical_state, 0)
        self.assertEqual(flood.cells[(3, 0)].text(), "")
        self.assertIn("#e0e0e0", flood.cells[(3, 0)].styleSheet())
        self.assertEqual(flood.cells[(1, 0)].logical_state, F)  # Public automatic win flag.

    def test_loss_states_come_from_reconstructed_observation(self):
        window = self.create_window(execution_fixture("loss"))
        window.slider.setValue(3)
        self.assertEqual([window.cells[(x, 0)].logical_state for x in range(6)], [1, H, F, H, H, F])
        window.on_last()
        expected = [1, CellState.EXPLODED, CellState.FALSE_FLAG, H, CellState.MINE, F]
        self.assertEqual(window.player.get_observation(), [expected])
        for x, state in enumerate(expected):
            self.assertEqual(window.cells[(x, 0)].logical_state, state)
        exploded, false_flag, mine = (window.cells[(x, 0)] for x in (1, 2, 4))
        self.assertEqual(exploded.text(), "✹")
        self.assertIn("#ff5555", exploded.styleSheet())
        self.assertEqual(mine.text(), "✹")
        self.assertNotIn("#ff5555", mine.styleSheet())
        self.assertEqual(false_flag.text(), "×")
        window.on_first()
        self.assertTrue(all(cell.logical_state == H and cell.text() == "" for cell in window.cells.values()))

    def test_all_number_values_and_observation_authority(self):
        # Inject public values at a coordinate whose fixed source board has a
        # mine. Refresh must honor the observation even there, without seeking.
        window = self.window
        for value in range(9):
            with self.subTest(value=value), patch.object(
                window.player, "get_observation", return_value=[[H, value, H], [H, H, H]],
            ), patch.object(window.player, "go_to", side_effect=AssertionError("refresh seek")):
                window.refresh()
                cell = window.cells[(1, 0)]
                self.assertEqual(cell.logical_state, value)
                self.assertEqual(cell.text(), "" if value == 0 else str(value))

    def test_navigation_and_nonsequential_slider_match_player(self):
        window = self.window
        for operation, index in (
            (window.next_button.click, 1), (window.next_button.click, 2),
            (window.previous_button.click, 1), (window.last_button.click, 5),
            (window.first_button.click, 0), (lambda: window.slider.setValue(4), 4),
            (lambda: window.slider.setValue(1), 1), (lambda: window.slider.setValue(3), 3),
        ):
            operation()
            self.assert_index(window, index)
        self.assertEqual((window.slider.minimum(), window.slider.maximum()), (0, 5))

    def test_cursor_and_line_use_trace_coordinates_including_same_cell(self):
        window = self.window
        for index, trace in enumerate(self.execution.result.traces, 1):
            window.slider.setValue(index)
            target = (trace.move.x, trace.move.y)
            overlay = window.overlay
            self.assertEqual(overlay.movement_start, trace.cursor_before)
            self.assertEqual(overlay.action_target, target)
            self.assertEqual(overlay.current_cursor, target)
            expected = None if trace.cursor_before == target else (trace.cursor_before, target)
            self.assertEqual(overlay.movement_line, expected)
            self.assertEqual(overlay.cell_center(target), QPointF((target[0] + .5) * 28, (target[1] + .5) * 28))
        window.slider.setValue(1)
        self.assertEqual(window.overlay.action_target, (0, 0))
        self.assertIsNone(window.overlay.movement_line)
        window.on_first()
        self.assertIsNone(window.overlay.action_target)
        self.assertIsNone(window.overlay.movement_start)
        self.assertIn("modeled cell-to-cell displacement", window.legend_label.text())
        self.assertIn("not a continuous OS mouse trajectory", window.legend_label.text())

    def test_displayed_trace_fields_are_exact_including_large_integer_costs(self):
        costs = (126005, 2**60 + 1, 3, 2**60 + 7, 11)
        result = replace(self.execution.result, traces=tuple(
            replace(trace, modeled_action_us=cost) for trace, cost in zip(self.execution.result.traces, costs)
        ))
        window = self.create_window(replace(self.execution, result=result))
        for index, trace in enumerate(result.traces, 1):
            window.slider.setValue(index)
            target = (trace.move.x, trace.move.y)
            expected = {
                "action": trace.move.action.name, "target": str(target),
                "movement": f"{trace.cursor_before} → {target}",
                "modeled_action_us": f"{costs[index - 1]:,} µs",
                "cumulative_modeled_us": f"{sum(costs[:index]):,} µs",
                "total_modeled_us": f"{sum(costs):,} µs",
                "status_after": trace.status_after.name,
                "safe_cells_opened_delta": str(trace.safe_cells_opened_delta),
                "explicit_flag_delta": str(trace.explicit_flag_delta),
            }
            self.assertEqual({key: label.text() for key, label in window.detail_labels.items()}, expected)
        text = " ".join(label.text() for label in window.findChildren(QLabel))
        self.assertNotIn("decision_compute_ns", text)
        self.assertNotIn("987654321", text)

    def test_boundary_controls_and_no_wrap_at_final_index(self):
        window = self.window
        for index, enabled in ((0, (False, False, True, True, True)), (5, (True, True, False, False, False))):
            window.slider.setValue(index)
            buttons = (window.first_button, window.previous_button, window.play_button,
                       window.next_button, window.last_button)
            self.assertEqual(tuple(button.isEnabled() for button in buttons), enabled)
        window.on_play_pause()
        window.on_next()
        window.timer.timeout.emit()
        self.assertFalse(window.timer.isActive())
        self.assert_index(window, 5)

    def test_one_timeout_one_trace_pause_and_final_stop(self):
        window = self.window
        window.play_button.click()
        self.assertTrue(window.timer.isActive())
        self.assertEqual(window.play_button.text(), "Pause")
        self.assert_index(window, 0)
        window.timer.timeout.emit()
        self.assert_index(window, 1)
        window.play_button.click()
        self.assertFalse(window.timer.isActive())
        window.timer.timeout.emit()  # Even a late queued callback is inert.
        self.assert_index(window, 1)
        window.play_button.click()
        for index in range(2, 6):
            window.timer.timeout.emit()
            self.assert_index(window, index)
        self.assertFalse(window.timer.isActive())
        self.assertEqual(window.play_button.text(), "Play")
        window.timer.timeout.emit()
        self.assert_index(window, 5)

    def test_real_timer_reaches_final_once_per_timeout(self):
        window = self.window
        observed = []
        window.timer.timeout.connect(lambda: observed.append(window.player.current_index))
        window.interval_spin.setValue(20)
        window.play_button.click()
        deadline = time.monotonic() + 3
        while window.timer.isActive() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(window.timer.isActive())
        self.assertEqual(observed, [1, 2, 3, 4, 5])
        self.assertEqual(window.play_button.text(), "Play")

    def test_every_manual_navigation_stops_autoplay(self):
        window = self.window
        for operation, index in (
            (window.first_button.click, 0), (window.previous_button.click, 1),
            (window.next_button.click, 3), (window.last_button.click, 5),
            (lambda: window.slider.setValue(4), 4),
            (lambda: window.slider.sliderPressed.emit(), 2),
            (lambda: window.slider.trackPressed.emit(), 2),
        ):
            window.slider.setValue(2)
            window.play_button.click()
            self.assertTrue(window.timer.isActive())
            operation()
            self.assertFalse(window.timer.isActive())
            self.assertEqual(window.play_button.text(), "Play")
            window.timer.timeout.emit()
            self.assert_index(window, index)

    def test_interval_changes_only_presentation_timer(self):
        window = self.window
        self.assertEqual((window.interval_spin.minimum(), window.interval_spin.maximum()), (20, 5000))
        self.assertEqual(window.interval_spin.value(), 200)
        self.assertEqual(window.timer.interval(), 200)
        self.assertEqual(window.interval_spin.suffix(), " ms/step")
        self.assertIn("not Model C physical time", window.interval_spin.toolTip())
        window.slider.setValue(2)
        original = self.execution.result
        labels = {key: label.text() for key, label in window.detail_labels.items()}
        window.play_button.click()
        for interval in (20, 5000, 387):
            window.interval_spin.setValue(interval)
            self.assertTrue(window.timer.isActive())
            self.assertEqual(window.timer.interval(), interval)
            self.assert_index(window, 2)
            self.assertEqual({key: label.text() for key, label in window.detail_labels.items()}, labels)
            self.assertEqual(self.execution.result, original)

    def test_programmatic_slider_refresh_does_not_seek_or_stop_timer(self):
        window = self.window
        window.play_button.click()
        with patch.object(window.player, "go_to", wraps=window.player.go_to) as seek:
            window.timer.timeout.emit()
            seek.assert_called_once_with(1)
            self.assertTrue(window.timer.isActive())
            seek.reset_mock()
            window.refresh()
            seek.assert_not_called()
        self.assertFalse(window.slider.signalsBlocked())
        window.slider.blockSignals(True)
        window.refresh()
        self.assertTrue(window.slider.signalsBlocked())
        window.slider.blockSignals(False)

    def slider_handle(self):
        slider = self.window.slider
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        return slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)

    def test_slider_track_clicks_exact_ends_and_same_index_stop(self):
        window = self.window
        window.show()
        self.app.processEvents()
        slider = window.slider
        for x, index in ((slider.width() - 1, 5), (0, 0)):
            slider.setValue(2)
            window.on_play_pause()
            QTest.mouseClick(slider, Qt.LeftButton, pos=QPoint(x, slider.height() // 2))
            self.assert_index(window, index)
            self.assertFalse(window.timer.isActive())
        window.on_play_pause()
        point = QPoint(self.slider_handle().right() + 1, slider.height() // 2)
        QTest.mouseClick(slider, Qt.LeftButton, pos=point)
        self.assert_index(window, 0)
        self.assertFalse(window.timer.isActive())

    def test_native_handle_drag_seeks_exact_indices_and_stops_playback(self):
        window = self.window
        window.show()
        self.app.processEvents()
        slider = window.slider
        slider.setValue(1)
        handle = self.slider_handle()
        press = handle.center() + QPoint(2, 0)
        window.on_play_pause()
        QTest.mousePress(slider, Qt.LeftButton, pos=press)
        try:
            self.assertTrue(slider.isSliderDown())
            self.assertFalse(window.timer.isActive())
            for index in (2, 4, 3):
                point = press + QPoint(round((slider.width() - handle.width()) * (index - 1) / 5), 0)
                event = QMouseEvent(QEvent.MouseMove, QPointF(point), QPointF(slider.mapToGlobal(point)),
                                    Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
                self.app.sendEvent(slider, event)
                self.assert_index(window, index)
        finally:
            QTest.mouseRelease(slider, Qt.LeftButton, pos=point)

    def test_accepted_close_stops_timer_and_emits_once(self):
        window = self.window
        signal = QSignalSpy(window.closed)
        observed = []
        window.closed.connect(lambda: observed.append((window.timer.isActive(), window._closed)))
        window.on_play_pause()
        self.assertTrue(window.close())
        self.assertEqual(len(signal), 1)
        self.assertEqual(observed, [(False, True)])
        # Before deferred deletion, a duplicate event cannot publish twice.
        event = QCloseEvent()
        window.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(len(signal), 1)
        window.on_play_pause()
        self.assertFalse(window.timer.isActive())

    def test_ignored_close_does_not_emit_closed(self):
        window = self.window
        signal = QSignalSpy(window.closed)
        event = QCloseEvent()
        with patch.object(QWidget, "closeEvent", side_effect=lambda event: event.ignore()):
            window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertEqual(len(signal), 0)
        self.assertFalse(window._closed)

    def test_read_only_board_mouse_input_and_paint_do_not_change_execution(self):
        window = self.window
        original = replace(self.execution)
        window.show()
        self.app.processEvents()
        for index in (0, 1, 3, 5):
            window.slider.setValue(index)
            for button in (Qt.LeftButton, Qt.RightButton, Qt.MiddleButton):
                QTest.mouseClick(window.cells[(0, 0)], button)
            self.assertFalse(window.board_container.grab().isNull())
            self.assert_index(window, index)
        self.assertEqual(self.execution, original)

    def test_module_dependencies_are_only_presentation_and_no_hidden_truth(self):
        source = Path(stage3_visualizer_ui.__file__).read_text(encoding="utf-8")
        module = ast.parse(source)
        allowed = {"PyQt5", "core_engine", "stage3_execution", "stage3_trace_player"}
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                self.assertIn(name.split(".")[0], allowed)
        for forbidden in ("mine_positions", "decision_compute_ns", "run_stage3", "run_expert_stage3_execution",
                          "plan_position", "subprocess", "ReplayData", "ReplayPlayer", "QSettings"):
            self.assertNotIn(forbidden, source)

    def test_construction_navigation_and_autoplay_never_call_producers(self):
        forbidden_calls = (
            "stage3_execution.run_expert_stage3_execution", "stage3_execution.run_stage3",
            "stage3_runner.run_stage3", "stage3_runner.plan_position", "stage3_planner.plan_position",
            "stage3_planner.analyze_position", "simple_decision.analyze_position",
            "simple_probability.calculate_probabilities", "simple_decision.calculate_probabilities",
            "simple_probability.choose_probability_move", "simple_decision.choose_probability_move",
            "stage3_execution.generate_board", "benchmark_board.generate_board",
            "stage3_physical.action_cost", "stage3_physical.load_timing_table",
        )
        forbidden_imports = {"stage3_execution_worker", "subprocess", "ui_manager", "zini_explorer_ui",
                             "zini_explorer", "replay_player", "replay_model"}
        real_import = builtins.__import__

        def guard_import(name, *args, **kwargs):
            if name.split(".")[0] in forbidden_imports:
                raise AssertionError(f"Consumer imported {name}")
            return real_import(name, *args, **kwargs)

        with ExitStack() as stack:
            mocks = [stack.enter_context(patch(name, side_effect=AssertionError(name))) for name in forbidden_calls]
            # Full discovery may have loaded the worker already; never import it
            # just for this test. The import guard handles an unloaded worker.
            worker = sys.modules.get("stage3_execution_worker")
            if worker is not None:
                for name in ("main", "run_expert_stage3_execution", "write_result_atomic"):
                    mocks.append(stack.enter_context(patch.object(worker, name, side_effect=AssertionError(name))))
            stack.enter_context(patch("builtins.__import__", side_effect=guard_import))
            stack.enter_context(patch("builtins.open", side_effect=AssertionError("consumer file I/O")))
            window = self.create_window(self.execution)
            for index in (5, 0, 3, 1):
                window.slider.setValue(index)
            window.on_next()
            window.on_previous()
            window.on_last()
            window.on_first()
            window.on_play_pause()
            for _ in self.execution.result.traces:
                window.timer.timeout.emit()
            self.assertEqual(window.player.current_index, 5)
            for mock in mocks:
                mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
