"""Deterministic offscreen presentation tests; fixtures never run a solver."""

import ast
import builtins
from contextlib import ExitStack
from copy import deepcopy
from fractions import Fraction
from dataclasses import replace
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import Mock, patch

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
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from simple_algorithm import SimpleMove
from stage3_execution import Stage3Execution
import stage3_identity
import stage3_physical
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


class FakeClock:
    def __init__(self):
        self.now_ns = 0

    def __call__(self):
        return self.now_ns

    def advance(self, nanoseconds):
        self.now_ns += nanoseconds


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

    def create_window(self, execution, parent=None, **kwargs):
        window = Stage3VisualizerWindow(execution, parent, **kwargs)
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
        self.assertEqual(window.title_label.text(), "Stage-3 Visualizer")
        self.assertEqual(window.algorithm_label.text(), "Algorithm: Stage-3 V1")
        self.assertEqual(window.physical_label.text(), "Physical: Model C · profile v1")
        self.assertEqual(window.playback_label.text(), "Playback: Index · 200 ms/step (presentation)")
        self.assertNotIn("Stage-3 V1 / Model C",
                         " ".join(label.text() for label in window.findChildren(QLabel)))
        window.show()
        self.app.processEvents()
        for label in (window.algorithm_label, window.physical_label, window.playback_label):
            self.assertTrue(label.isVisible())
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

    def test_labels_read_shared_authorities_at_construction(self):
        with patch.object(stage3_identity, "STAGE3_V1_IDENTITY", replace(
            stage3_identity.STAGE3_V1_IDENTITY, algorithm_spec_version=7,
        )), patch.object(stage3_physical, "MODEL_C_V1_IDENTITY", replace(
            stage3_physical.MODEL_C_V1_IDENTITY, physical_profile_version=9,
        )), patch.object(stage3_physical, "MODEL_C_DISPLAY_NAME", "Test model"):
            window = self.create_window(self.execution)
            self.assertEqual(window.algorithm_label.text(), "Algorithm: Stage-3 V7")
            self.assertEqual(window.physical_label.text(), "Physical: Test model · profile v9")
            self.assertEqual(window.playback_label.text(),
                             "Playback: Index · 200 ms/step (presentation)")

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
        self.assertIn("recorded modeled time is unchanged", window.interval_spin.toolTip())
        window.slider.setValue(2)
        original = replace(self.execution)
        result = self.execution.result
        traces = result.traces
        total = result.total_modeled_us
        cumulative = window.player.cumulative_modeled_us
        labels = {key: label.text() for key, label in window.detail_labels.items()}
        window.play_button.click()
        for interval in (20, 5000, 387):
            window.interval_spin.setValue(interval)
            self.assertTrue(window.timer.isActive())
            self.assertEqual(window.timer.interval(), interval)
            self.assert_index(window, 2)
            self.assertEqual({key: label.text() for key, label in window.detail_labels.items()}, labels)
            self.assertEqual(window.playback_label.text(),
                             f"Playback: Index · {interval} ms/step (presentation)")
            self.assertIs(window.player.execution, self.execution)
            self.assertIs(self.execution.result, result)
            self.assertIs(self.execution.result.traces, traces)
            self.assertEqual(self.execution, original)
            self.assertEqual(self.execution.result.total_modeled_us, total)
            self.assertEqual(window.player.cumulative_modeled_us, cumulative)
        window.timer.timeout.emit()
        self.assert_index(window, 3)

    def test_programmatic_slider_refresh_does_not_seek_or_stop_timer(self):
        window = self.window
        window.play_button.click()
        window.timer.timeout.emit()
        self.assert_index(window, 1)
        self.assertTrue(window.timer.isActive())
        with patch.object(window.player, "go_to", side_effect=AssertionError("refresh sought")):
            window.refresh()
        self.assert_index(window, 1)
        self.assertTrue(window.timer.isActive())
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

    def create_modeled_window(self, index=0, execution=None):
        clock = FakeClock()
        window = self.create_window(execution or self.execution, clock=clock)
        window.slider.setValue(index)
        window.mode_combo.setCurrentText("Modeled-Time")
        return window, clock

    def test_playback_modes_and_rates_default_without_persistence(self):
        window = self.window
        self.assertEqual([window.mode_combo.itemText(i) for i in range(2)], ["Index", "Modeled-Time"])
        self.assertEqual(window.mode_combo.currentText(), "Index")
        self.assertTrue(window.interval_spin.isEnabled())
        self.assertFalse(window.speed_combo.isEnabled())
        self.assertEqual(window.speed_combo.currentText(), "1×")
        self.assertEqual(window.modeled_playback.speed, 1)
        window.interval_spin.setValue(387)
        window.mode_combo.setCurrentText("Modeled-Time")
        window.speed_combo.setCurrentText("8×")
        reopened = self.create_window(self.execution)
        self.assertEqual(reopened.mode_combo.currentText(), "Index")
        self.assertEqual(reopened.interval_spin.value(), 200)
        self.assertEqual(reopened.speed_combo.currentText(), "1×")
        self.assertEqual(reopened.modeled_playback.speed, 1)
        self.assertFalse(reopened.modeled_playback.running)
        self.assertFalse(reopened.timer.isActive())

    def test_mode_switch_stops_discards_partial_and_retains_committed_index(self):
        window, clock = self.create_modeled_window(2)
        self.assertFalse(window.interval_spin.isEnabled())
        self.assertTrue(window.speed_combo.isEnabled())
        self.assertFalse(window.timer.isActive())
        self.assertIsNone(window.overlay.presentation_position)
        window.on_play_pause()
        clock.advance(123456)
        window.timer.timeout.emit()
        self.assertGreater(window.modeled_playback.partial_modeled_us, 0)
        clock.advance(10**12)  # Switching must discard unsampled time, too.
        window.mode_combo.setCurrentText("Index")
        self.assert_index(window, 2)
        self.assertFalse(window.timer.isActive())
        self.assertFalse(window.modeled_playback.running)
        self.assertEqual(window.modeled_playback.partial_modeled_us, 0)
        self.assertIsNone(window.overlay.presentation_position)
        self.assertEqual(window.overlay.action_target, (1, 0))
        self.assertTrue(window.interval_spin.isEnabled())
        self.assertFalse(window.speed_combo.isEnabled())
        self.assertEqual(window.timer.interval(), 200)
        window.on_play_pause()
        window.timer.timeout.emit()
        self.assert_index(window, 3)
        window.mode_combo.setCurrentText("Modeled-Time")
        self.assert_index(window, 3)
        self.assertFalse(window.timer.isActive())
        self.assertEqual(window.play_button.text(), "Play")
        self.assertEqual(window.modeled_playback.partial_modeled_us, 0)
        self.assertIsNone(window.overlay.presentation_position)
        self.assertEqual(window.playback_label.text(), "Playback: Modeled-Time · 1× (presentation)")

    def test_modeled_timer_requests_frames_without_advancing_by_tick_count(self):
        window, clock = self.create_modeled_window(1)
        window.on_play_pause()
        self.assertTrue(window.modeled_playback.running)
        self.assertTrue(window.timer.isActive())
        self.assertEqual(window.timer.interval(), 16)
        self.assertEqual(window.timer.timerType(), Qt.PreciseTimer)
        self.assertEqual(window.play_button.text(), "Pause")
        for _ in range(10):
            window.timer.timeout.emit()
        self.assertEqual(window.modeled_playback.partial_modeled_us, 0)
        self.assert_index(window, 1)
        clock.advance(self.execution.result.traces[1].modeled_action_us * 250)
        window.timer.timeout.emit()
        self.assertEqual(window.modeled_playback.progress, Fraction(1, 4))
        self.assertEqual(window.overlay.cursor_center, QPointF(14 + 28 * 5 / 32, 14))
        self.assertEqual(window.overlay.current_cursor, (0, 0))
        self.assertEqual(window.overlay.action_target, (1, 0))

    def test_same_cell_first_action_waits_for_boundary_then_refreshes_once(self):
        window, clock = self.create_modeled_window()
        trace = self.execution.result.traces[0]
        self.assertEqual(trace.modeled_action_us, 126005)
        before = window.player.get_observation()
        window.on_play_pause()
        self.assertEqual(window.overlay.cursor_center, QPointF(14, 14))
        self.assertEqual(window.overlay.action_target, (0, 0))
        with patch.object(window, "refresh", wraps=window.refresh) as refresh:
            clock.advance(63002500)
            window.timer.timeout.emit()
            self.assertEqual(window.modeled_playback.progress, Fraction(1, 2))
            self.assertEqual(window.overlay.cursor_center, QPointF(14, 14))
            self.assertIsNone(window.overlay.movement_line)
            self.assertEqual(window.player.get_observation(), before)
            self.assertEqual(window.detail_labels["action"].text(), "—")
            refresh.assert_not_called()
            clock.advance(63002500)
            window.timer.timeout.emit()
            refresh.assert_called_once_with()
            self.assert_index(window, 1)
            self.assertEqual(window.cells[(0, 0)].logical_state, 1)
            self.assertEqual(window.overlay.cursor_center, QPointF(14, 14))
            self.assertEqual(window.overlay.action_target, (1, 0))
            self.assertEqual(window.detail_labels["action"].text(), "OPEN")
            window.timer.timeout.emit()
            refresh.assert_called_once_with()

    def test_smoothstep_endpoints_quarter_midpoint_and_straight_paths(self):
        overlay = self.window.overlay
        for start, target in (((0, 0), (2, 1)), ((2, 1), (0, 0)), ((1, 0), (1, 1)), ((0, 0), (0, 0))):
            trace = replace(self.execution.result.traces[0], cursor_before=start,
                            move=SimpleMove(Action.OPEN, *target))
            for u, q in ((Fraction(0), 0), (Fraction(1, 4), Fraction(5, 32)),
                         (Fraction(1, 2), Fraction(1, 2)), (Fraction(1), 1)):
                with self.subTest(start=start, target=target, u=u):
                    overlay.set_pending(trace, start, u)
                    a, b = overlay.cell_center(start), overlay.cell_center(target)
                    self.assertEqual(overlay.cursor_center, a + (b - a) * float(q))
                    self.assertEqual(overlay.current_cursor, start)
                    expected_line = None if start == target else (start, target)
                    self.assertEqual(overlay.movement_line, expected_line)
        self.assertEqual(self.window.player.current_index, 0)

    def test_modeled_pause_samples_time_and_resume_preserves_frozen_cursor(self):
        window, clock = self.create_modeled_window(1)
        window.on_play_pause()
        clock.advance(self.execution.result.traces[1].modeled_action_us * 250)
        window.on_play_pause()  # Pause samples time even without an intervening frame.
        position = QPointF(window.overlay.cursor_center)
        partial = window.modeled_playback.partial_modeled_us
        self.assertEqual(window.modeled_playback.progress, Fraction(1, 4))
        self.assertFalse(window.timer.isActive())
        self.assertFalse(window.modeled_playback.running)
        self.assertEqual(window.play_button.text(), "Play")
        clock.advance(10**12)
        window.timer.timeout.emit()
        self.assertEqual(window.overlay.cursor_center, position)
        window.on_play_pause()
        self.assertEqual(window.overlay.cursor_center, position)
        self.assertEqual(window.modeled_playback.partial_modeled_us, partial)
        window.timer.timeout.emit()
        self.assertEqual(window.overlay.cursor_center, position)
        clock.advance(1000)
        window.timer.timeout.emit()
        self.assertEqual(window.modeled_playback.partial_modeled_us, partial + 1)
        self.assertGreater(window.overlay.cursor_center.x(), position.x())

    def test_pause_can_cross_boundaries_and_refresh_committed_board_once(self):
        window, clock = self.create_modeled_window()
        window.on_play_pause()
        clock.advance(sum(t.modeled_action_us for t in self.execution.result.traces[:2]) * 1000 + 7000)
        with patch.object(window, "refresh", wraps=window.refresh) as refresh:
            window.on_play_pause()
            refresh.assert_called_once_with()
        self.assert_index(window, 2)
        self.assertEqual(window.modeled_playback.partial_modeled_us, 7)
        self.assertFalse(window.timer.isActive())
        self.assertFalse(window.modeled_playback.running)

    def test_late_frame_commits_every_action_but_refreshes_board_once(self):
        window, clock = self.create_modeled_window()
        traces = self.execution.result.traces
        applied = []
        real_step = MinesweeperEngine.step

        def step(engine, x, y, action):
            applied.append(SimpleMove(action, x, y))
            return real_step(engine, x, y, action)

        window.on_play_pause()
        clock.advance(sum(t.modeled_action_us for t in traces[:3]) * 1000 + traces[3].modeled_action_us * 250)
        with patch.object(window, "refresh", wraps=window.refresh) as refresh, patch.object(
            window.player, "go_to", side_effect=AssertionError("Frame sought"),
        ), patch.object(MinesweeperEngine, "step", new=step), patch.object(
            window.cells[(0, 0)], "render_state", wraps=window.cells[(0, 0)].render_state,
        ) as cell_render:
            window.timer.timeout.emit()
            refresh.assert_called_once_with()
            cell_render.assert_called_once()
        self.assertEqual(tuple(applied), self.execution.result.moves[:3])
        self.assert_index(window, 3)
        self.assertEqual(window.modeled_playback.progress, Fraction(1, 4))
        self.assertEqual(window.overlay.cursor_center, QPointF(14 + 56 * 5 / 32, 14))
        self.assertEqual(window.detail_labels["action"].text(), "CHORD")
        self.assertEqual(window.detail_labels["target"].text(), "(0, 0)")
        self.assertEqual(window.overlay.action_target, (2, 0))

    def test_partial_frame_only_updates_overlay_and_keeps_applied_details(self):
        window, clock = self.create_modeled_window(1)
        window.on_play_pause()
        details = {key: label.text() for key, label in window.detail_labels.items()}
        with patch.object(window, "refresh", side_effect=AssertionError("Full refresh")), patch.object(
            stage3_visualizer_ui.Stage3VisualizerCell, "render_state", side_effect=AssertionError("Cell restyle"),
        ), patch.object(window.player, "go_to", side_effect=AssertionError("Seek")), patch.object(
            window.player, "get_observation", side_effect=AssertionError("Board read"),
        ):
            for _ in range(2):
                clock.advance(self.execution.result.traces[1].modeled_action_us * 250)
                window.timer.timeout.emit()
        self.assertEqual(window.modeled_playback.progress, Fraction(1, 2))
        self.assertEqual(window.overlay.cursor_center, QPointF(28, 14))
        self.assertEqual({key: label.text() for key, label in window.detail_labels.items()}, details)
        self.assert_index(window, 1)

    def test_programmatic_refresh_keeps_modeled_partial_progress_and_timer(self):
        window, clock = self.create_modeled_window(1)
        window.on_play_pause()
        clock.advance(123456)
        window.timer.timeout.emit()
        position = QPointF(window.overlay.cursor_center)
        partial = window.modeled_playback.partial_modeled_us
        with patch.object(window.modeled_playback, "cancel_partial", side_effect=AssertionError("Cancelled")), patch.object(
            window.player, "go_to", side_effect=AssertionError("Sought"),
        ):
            window.refresh()
        self.assertEqual(window.overlay.cursor_center, position)
        self.assertEqual(window.modeled_playback.partial_modeled_us, partial)
        self.assertTrue(window.modeled_playback.running)
        self.assertTrue(window.timer.isActive())
        self.assertFalse(window.slider.signalsBlocked())

    def test_modeled_speed_selector_has_exact_six_rates_and_labels(self):
        window, clock = self.create_modeled_window()
        labels = ("0.25×", "0.5×", "1×", "2×", "4×", "8×")
        self.assertEqual([window.speed_combo.itemText(i) for i in range(6)], list(labels))
        for index, rate in enumerate((Fraction(1, 4), Fraction(1, 2), 1, 2, 4, 8)):
            with self.subTest(rate=rate):
                window.on_first()
                window.speed_combo.setCurrentIndex(index)
                self.assertEqual(window.modeled_playback.speed, rate)
                self.assertEqual(window.playback_label.text(), f"Playback: Modeled-Time · {labels[index]} (presentation)")
                window.on_play_pause()
                clock.advance(1000)
                window.timer.timeout.emit()
                self.assertEqual(window.modeled_playback.partial_modeled_us, rate)
                self.assertEqual(window.timer.interval(), 16)

    def test_speed_change_catches_up_at_old_rate_and_preserves_remainder(self):
        window, clock = self.create_modeled_window()
        window.on_play_pause()
        clock.advance(self.execution.result.traces[0].modeled_action_us * 1000 + 3500)
        with patch.object(window, "refresh", wraps=window.refresh) as refresh:
            window.speed_combo.setCurrentText("8×")
            refresh.assert_called_once_with()
        self.assert_index(window, 1)
        self.assertEqual(window.modeled_playback.partial_modeled_us, Fraction(7, 2))
        self.assertEqual(window.modeled_playback.speed, 8)
        self.assertTrue(window.timer.isActive())
        clock.advance(3000)
        window.timer.timeout.emit()
        self.assertEqual(window.modeled_playback.partial_modeled_us, Fraction(55, 2))

    def test_paused_speed_change_and_inactive_interval_do_not_move_cursor(self):
        window, clock = self.create_modeled_window(1)
        window.on_play_pause()
        clock.advance(7000)
        window.on_play_pause()
        position = QPointF(window.overlay.cursor_center)
        clock.advance(10**12)
        window.speed_combo.setCurrentText("0.25×")
        window.interval_spin.setValue(4999)  # Programmatic changes cannot alter frame cadence.
        self.assertEqual(window.overlay.cursor_center, position)
        self.assertEqual(window.modeled_playback.partial_modeled_us, 7)
        self.assertFalse(window.timer.isActive())
        self.assertEqual(window.timer.interval(), 16)
        self.assertEqual(window.playback_label.text(), "Playback: Modeled-Time · 0.25× (presentation)")
        window.mode_combo.setCurrentText("Index")
        self.assertEqual(window.timer.interval(), 4999)
        self.assertEqual(window.playback_label.text(), "Playback: Index · 4999 ms/step (presentation)")

    def test_terminal_speed_change_stops_timer_without_wrap_or_restart(self):
        window, clock = self.create_modeled_window()
        window.on_play_pause()
        clock.advance(self.execution.result.total_modeled_us * 1000)
        with patch.object(window, "refresh", wraps=window.refresh) as refresh:
            window.speed_combo.setCurrentText("4×")
            refresh.assert_called_once_with()
        self.assert_index(window, 5)
        self.assertFalse(window.timer.isActive())
        self.assertFalse(window.modeled_playback.running)
        self.assertFalse(window.play_button.isEnabled())
        self.assertEqual(window.play_button.text(), "Play")
        self.assertIsNone(window.overlay.presentation_position)
        self.assertEqual(window.modeled_playback.partial_modeled_us, 0)
        window.on_play_pause()
        window.timer.timeout.emit()
        self.assert_index(window, 5)

    def test_every_modeled_manual_navigation_cancels_before_integer_operation(self):
        operations = (("on_first", None, 0), ("on_previous", None, 1), ("on_next", None, 3),
                      ("on_last", None, 5), ("on_slider_changed", 4, 4), ("on_slider_changed", 2, 2))
        for method, argument, expected in operations:
            with self.subTest(method=method, argument=argument):
                window, clock = self.create_modeled_window(2)
                window.on_play_pause()
                clock.advance(100000)
                window.timer.timeout.emit()
                clock.advance(10**12)
                real_methods = {name: getattr(window.player, name) for name in ("next", "previous", "go_to")}

                def checked(name, *args):
                    self.assertFalse(window.timer.isActive())
                    self.assertFalse(window.modeled_playback.running)
                    self.assertEqual(window.modeled_playback.partial_modeled_us, 0)
                    return real_methods[name](*args)

                with ExitStack() as stack:
                    for name in real_methods:
                        stack.enter_context(patch.object(window.player, name, side_effect=lambda *args, name=name: checked(name, *args)))
                    if argument is None:
                        getattr(window, method)()
                    else:
                        getattr(window, method)(argument)
                self.assert_index(window, expected)
                self.assertEqual(window.modeled_playback.partial_modeled_us, 0)
                self.assertIsNone(window.overlay.presentation_position)
                self.assertFalse(window.timer.isActive())
                window.timer.timeout.emit()
                self.assert_index(window, expected)

    def test_slider_value_and_same_index_mouse_presses_cancel_partial(self):
        for interaction in ("value", "handle", "track"):
            with self.subTest(interaction=interaction):
                window, clock = self.create_modeled_window()
                window.show()
                self.app.processEvents()
                slider = window.slider
                option = QStyleOptionSlider()
                slider.initStyleOption(option)
                handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
                window.on_play_pause()
                clock.advance(63002500)
                window.timer.timeout.emit()
                clock.advance(10**12)
                if interaction == "value":
                    slider.setValue(3)
                else:
                    point = handle.center() if interaction == "handle" else QPoint(handle.right() + 1, slider.height() // 2)
                    QTest.mouseClick(slider, Qt.LeftButton, pos=point)
                self.assert_index(window, 3 if interaction == "value" else 0)
                self.assertEqual(window.modeled_playback.partial_modeled_us, 0)
                self.assertFalse(window.modeled_playback.running)
                self.assertFalse(window.timer.isActive())
                self.assertIsNone(window.overlay.presentation_position)

    def test_zero_duration_play_commits_immediately_with_one_refresh(self):
        for costs, expected in (((0, 0, 10, 20, 30), 2), ((0, 0, 0, 0, 0), 5)):
            with self.subTest(costs=costs):
                result = replace(self.execution.result, traces=tuple(
                    replace(trace, modeled_action_us=cost) for trace, cost in zip(self.execution.result.traces, costs)
                ))
                window, _ = self.create_modeled_window(execution=replace(self.execution, result=result))
                with patch.object(window, "refresh", wraps=window.refresh) as refresh:
                    window.on_play_pause()
                    refresh.assert_called_once_with()
                self.assert_index(window, expected)
                self.assertEqual(window.modeled_playback.partial_modeled_us, 0)
                self.assertEqual(window.timer.isActive(), expected < 5)
                self.assertEqual(window.modeled_playback.running, expected < 5)

    def test_boundary_failure_keeps_safe_commits_visible_and_never_auto_retries(self):
        traces = list(self.execution.result.traces)
        traces[1] = replace(traces[1], status_after=L)
        execution = replace(self.execution, result=replace(self.execution.result, traces=traces))
        window, clock = self.create_modeled_window(execution=execution)
        window.on_play_pause()
        clock.advance(10**12)
        with patch.object(window, "refresh", wraps=window.refresh) as refresh:
            window.timer.timeout.emit()
            refresh.assert_called_once_with()
        self.assert_index(window, 1)
        self.assertFalse(window.modeled_playback.running)
        self.assertFalse(window.timer.isActive())
        self.assertEqual(window.play_button.text(), "Play")
        self.assertEqual(window.modeled_playback.progress, 1)
        self.assertEqual(window.overlay.cursor_center, window.overlay.cell_center((1, 0)))
        self.assertFalse(window.error_label.isHidden())
        self.assertIn("Trace 2 status_after", window.error_label.text())
        self.assertEqual(window.error_label.textFormat(), Qt.PlainText)
        with patch.object(window.player, "next", side_effect=AssertionError("Automatic retry")):
            window.timer.timeout.emit()
        self.assert_index(window, 1)
        window.on_first()
        self.assertTrue(window.error_label.isHidden())

    def test_clock_failure_on_frame_pause_or_speed_preserves_cursor_and_stops(self):
        for operation in ("frame", "pause", "speed"):
            with self.subTest(operation=operation):
                window, clock = self.create_modeled_window(1)
                window.on_play_pause()
                clock.advance(7000)
                window.timer.timeout.emit()
                position = QPointF(window.overlay.cursor_center)
                clock.now_ns = 6999
                if operation == "frame":
                    window.timer.timeout.emit()
                elif operation == "pause":
                    window.on_play_pause()
                else:
                    window.speed_combo.setCurrentText("8×")
                self.assertFalse(window.timer.isActive())
                self.assertFalse(window.modeled_playback.running)
                self.assertEqual(window.overlay.cursor_center, position)
                self.assertEqual(window.modeled_playback.partial_modeled_us, 7)
                self.assertIn("backwards", window.error_label.text())
                self.assertEqual(window.speed_combo.currentText(), "1×")
                self.assertEqual(window.playback_label.text(), "Playback: Modeled-Time · 1× (presentation)")
                self.assert_index(window, 1)

    def test_accepted_modeled_close_cancels_and_late_callback_is_inert(self):
        window, clock = self.create_modeled_window(1)
        window.on_play_pause()
        clock.advance(7000)
        window.timer.timeout.emit()
        observed = []
        window.closed.connect(lambda: observed.append((window.timer.isActive(), window.modeled_playback.running)))
        self.assertTrue(window.close())
        self.assertEqual(observed, [(False, False)])
        self.assertEqual(window.modeled_playback.partial_modeled_us, 0)
        with patch.object(window.player, "next", side_effect=AssertionError("Closed advance")), patch.object(
            window, "refresh", side_effect=AssertionError("Closed refresh"),
        ):
            clock.advance(10**12)
            window.timer.timeout.emit()
            window.on_play_pause()
        self.assertEqual(window.player.current_index, 1)
        self.assertFalse(window.timer.isActive())

    def test_ignored_close_keeps_modeled_playback_running(self):
        window, clock = self.create_modeled_window(1)
        window.on_play_pause()
        clock.advance(7000)
        window.timer.timeout.emit()
        event = QCloseEvent()
        with patch.object(QWidget, "closeEvent", side_effect=lambda event: event.ignore()):
            window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertTrue(window.modeled_playback.running)
        self.assertTrue(window.timer.isActive())
        self.assertEqual(window.modeled_playback.partial_modeled_us, 7)

    def test_reference_controls_default_off_and_layers_are_mouse_transparent(self):
        w = self.window
        self.assertEqual(w.answer_checkbox.text(), "Show hidden answers")
        self.assertEqual(w.route_checkbox.text(), "Show action-target route")
        self.assertIn("not recorded cursor trajectory", w.route_checkbox.toolTip())
        layers = (w.answer_overlay, w.route_overlay, w.overlay)
        self.assertEqual(tuple(child for child in w.board_container.children() if child in layers), layers)
        for layer in layers:
            self.assertTrue(layer.testAttribute(Qt.WA_TransparentForMouseEvents))
            self.assertEqual(layer.geometry(), w.board_container.rect())
        for checkbox, layer in ((w.answer_checkbox, w.answer_overlay), (w.route_checkbox, w.route_overlay)):
            self.assertFalse(checkbox.isChecked())
            self.assertTrue(layer.isHidden())
        w.on_next()
        self.assertEqual(w.overlay.action_target, (0, 0))  # Existing context needs neither reference toggle.

    def test_answers_derive_once_from_retained_finalized_board_and_dimensions(self):
        execution = execution_fixture("flood")
        with patch.object(stage3_visualizer_ui, "derive_answer_clues",
                          wraps=stage3_visualizer_ui.derive_answer_clues) as derive:
            w = self.create_window(execution)
            derive.assert_called_once_with(4, 1, execution.board.mine_positions)
            self.assertIs(derive.call_args.args[2], execution.board.mine_positions)
            self.assertEqual(w.answer_overlay.answers, ((1, -1, 1, 0),))
            answers = w.answer_overlay.answers
            with self.assertRaises(TypeError):
                answers[0][0] = 8
            for index in (1, 2, 0):
                w.on_slider_changed(index)
                w.answer_checkbox.toggle()
                w.route_checkbox.toggle()
            w.on_play_pause()
            w.timer.timeout.emit()
            w.timer.timeout.emit()
            self.assertIs(w.answer_overlay.answers, answers)
            self.assertEqual(derive.call_count, 1)

    def test_hidden_answers_preserve_public_text_accessibility_flags_and_terminal_feedback(self):
        for kind in ("win", "loss", "flood"):
            w = self.create_window(execution_fixture(kind))
            for index in range(w.player.step_count + 1):
                w.on_slider_changed(index)
                observation = w.player.get_observation()
                expected = tuple(tuple(value == H for value in row) for row in observation)
                self.assertEqual(w.answer_overlay.hidden_mask, expected)
                def public():
                    return tuple((cell.logical_state, cell.text(), cell.toolTip(), cell.accessibleName(),
                                  cell.accessibleDescription(), cell.styleSheet()) for cell in w.cells.values())
                before = public()
                for checked in (True, False):
                    w.answer_checkbox.setChecked(checked)
                    self.assertEqual(public(), before)
                    self.assertEqual(w.player.get_observation(), observation)
            if kind == "loss":
                self.assertEqual(w.answer_overlay.hidden_mask, ((False, False, False, True, False, False),))
                self.assertEqual(tuple(cell.logical_state for cell in w.cells.values()),
                                 (1, CellState.EXPLODED, CellState.FALSE_FLAG, H, CellState.MINE, F))

    def test_answer_mask_uses_public_observation_even_at_a_retained_mine(self):
        w = self.window
        observation = [[H, 3, F], [CellState.EXPLODED, CellState.FALSE_FLAG, CellState.MINE]]
        with patch.object(w.player, "get_observation", return_value=observation):
            w.refresh()
        self.assertEqual(w.answer_overlay.answers[0][1], -1)
        self.assertEqual(w.answer_overlay.hidden_mask, ((True, False, False), (False, False, False)))
        w.answer_checkbox.setChecked(True)
        self.assertEqual(w.cells[(1, 0)].text(), "3")
        painter = Mock()
        with patch.object(stage3_visualizer_ui, "QPainter", return_value=painter):
            w.answer_overlay.paintEvent(None)
        self.assertEqual([call.args[2] for call in painter.drawText.call_args_list], ["1"])
        painter.setOpacity.assert_called_once_with(0.35)

    def test_answer_painter_shows_mine_and_clue_keeps_zero_blank_and_restores_off(self):
        w = self.create_window(execution_fixture("flood"))
        w.show()
        self.app.processEvents()
        before = w.board_container.grab().toImage()
        w.answer_checkbox.setChecked(True)
        self.assertTrue(w.answer_overlay.isVisible())
        # Literal painter commands avoid changing the process-wide font database
        # on Windows offscreen Qt, which may expose no installed glyph fonts.
        painter = Mock()
        with patch.object(stage3_visualizer_ui, "QPainter", return_value=painter):
            w.answer_overlay.paintEvent(None)
        self.assertEqual([(call.args[0].x(), call.args[2]) for call in painter.drawText.call_args_list],
                         [(0, "1"), (28, "✹"), (56, "1")])
        painter.setOpacity.assert_called_once_with(0.35)
        w.answer_checkbox.setChecked(False)
        self.assertTrue(w.answer_overlay.isHidden())
        self.assertEqual(before, w.board_container.grab().toImage())

    def test_route_prefix_zero_one_middle_final_and_repeated_executed_targets(self):
        first = self.execution.result.traces[0]
        repeated = replace(first, safe_cells_opened_delta=0)
        traces = (first, repeated, *self.execution.result.traces[1:])
        execution = replace(self.execution, result=replace(self.execution.result, traces=traces))
        w = self.create_window(execution)
        targets = ((0, 0), (0, 0), (1, 0), (0, 0), (2, 0), (2, 1))
        self.assertEqual(w.route_overlay.targets, ())
        w.route_checkbox.setChecked(True)
        for k in (0, 1, 2, 3, 6, 4, 0):
            w.on_slider_changed(k)
            self.assertEqual(w.route_overlay.targets, targets[:k])
            painter = Mock()
            with patch.object(stage3_visualizer_ui, "QPainter", return_value=painter):
                w.route_overlay.paintEvent(None)
            if k < 2:
                painter.drawPolyline.assert_not_called()
            else:
                self.assertEqual(painter.drawPolyline.call_count, 2)
                self.assertEqual(tuple(painter.drawPolyline.call_args.args[0]),
                                 tuple(w.overlay.cell_center(target) for target in targets[:k]))

    def test_route_has_no_fabricated_origin_or_planned_suffix(self):
        # The first executed target differs from the declared (0, 0) cursor.
        # Decision evidence is deliberately inaccessible; it is not route data.
        decision_reads = []
        class UnreadDecision:
            def __getattr__(self, name):
                decision_reads.append(name)
                raise AssertionError("Planner evidence read")
        decision = UnreadDecision()
        trace = replace(self.execution.result.traces[0], move=SimpleMove(Action.FLAG, 1, 0),
                        decision=decision, safe_cells_opened_delta=0, explicit_flag_delta=1)
        execution = replace(self.execution, result=Stage3RunResult(P, (trace,)))
        w = self.create_window(execution)
        w.on_last()
        self.assertEqual(w.route_overlay.targets, ((1, 0),))
        self.assertEqual(w.overlay.movement_line, ((0, 0), (1, 0)))
        painter = Mock()
        with patch.object(stage3_visualizer_ui, "QPainter", return_value=painter):
            w.route_overlay.paintEvent(None)
        painter.drawPolyline.assert_not_called()
        self.assertEqual(decision_reads, [])

    def test_route_pixels_and_shared_style_restore_when_disabled(self):
        w = self.window
        w.show()
        self.app.processEvents()
        w.on_slider_changed(2)
        w.overlay.hide()
        before = w.board_container.grab().toImage()
        w.route_checkbox.setChecked(True)
        self.assertNotEqual(before, w.board_container.grab().toImage())
        painter = Mock()
        with patch.object(stage3_visualizer_ui, "QPainter", return_value=painter):
            w.route_overlay.paintEvent(None)
        self.assertEqual([(call.args[0].color().getRgb(), call.args[0].widthF())
                          for call in painter.setPen.call_args_list],
                         [((255, 255, 255, 100), 3.5), ((90, 70, 115, 165), 2.0)])
        w.route_checkbox.setChecked(False)
        self.assertEqual(before, w.board_container.grab().toImage())

    def test_partial_modeled_motion_keeps_reference_prefix_until_exact_commit(self):
        w, clock = self.create_modeled_window(1)
        w.answer_checkbox.setChecked(True)
        w.route_checkbox.setChecked(True)
        mask, route = w.answer_overlay.hidden_mask, w.route_overlay.targets
        w.on_play_pause()
        with patch.object(w, "refresh", wraps=w.refresh) as refresh:
            clock.advance(self.execution.result.traces[1].modeled_action_us * 250)
            w.timer.timeout.emit()
            self.assertEqual(w.overlay.cursor_center, QPointF(14 + 28 * 5 / 32, 14))
            self.assertEqual(w.overlay.action_target, (1, 0))  # Pending context remains independent.
            self.assertEqual(w.player.current_index, 1)
            self.assertIs(w.answer_overlay.hidden_mask, mask)
            self.assertIs(w.route_overlay.targets, route)
            self.assertEqual(route, ((0, 0),))
            refresh.assert_not_called()
            clock.advance(self.execution.result.traces[1].modeled_action_us * 750)
            w.timer.timeout.emit()
            refresh.assert_called_once_with()
        self.assertEqual(w.player.current_index, 2)
        self.assertEqual(w.route_overlay.targets, ((0, 0), (1, 0)))
        self.assertFalse(w.answer_overlay.hidden_mask[0][1])

    def test_reference_toggles_are_independent_during_index_modeled_and_paused_playback(self):
        for mode in ("Index", "Modeled-Time", "paused"):
            w, clock = self.create_modeled_window(1)
            if mode == "Index":
                w.mode_combo.setCurrentText(mode)
            w.on_play_pause()
            if mode != "Index":
                clock.advance(7000)
                w.timer.timeout.emit()
            if mode == "paused":
                w.on_play_pause()
            def state():
                return (w.player.current_index, w.player.cumulative_modeled_us,
                        w.modeled_playback.partial_modeled_us, w.modeled_playback.running,
                        w.timer.isActive(), w.timer.interval(), QPointF(w.overlay.cursor_center))
            before = state()
            for answers, route in ((False, False), (True, False), (False, True), (True, True)):
                w.answer_checkbox.setChecked(answers)
                w.route_checkbox.setChecked(route)
                self.assertEqual(state(), before)
                self.assertEqual(w.answer_overlay.isHidden(), not answers)
                self.assertEqual(w.route_overlay.isHidden(), not route)
                layers = (w.answer_overlay, w.route_overlay, w.overlay)
                self.assertEqual(tuple(c for c in w.board_container.children() if c in layers), layers)

    def test_reference_toggles_and_partial_repaint_do_no_domain_or_board_work(self):
        w, clock = self.create_modeled_window(1)
        w.show()
        self.app.processEvents()
        w.on_play_pause()
        forbidden = (
            "stage3_execution.run_expert_stage3_execution", "stage3_runner.run_stage3",
            "stage3_planner.plan_position", "stage3_planner.analyze_position",
            "simple_decision.analyze_position", "simple_probability.calculate_probabilities",
            "stage3_execution.generate_board", "benchmark_board.generate_board",
            "benchmark_modeled_time.authenticate_model_c", "benchmark_modeled_time.evaluate_ordered_actions",
            "stage3_physical.load_timing_table", "stage3_physical.action_cost",
            "stage3_execution_job.Stage3ExecutionJob.start", "subprocess.Popen",
            "core_engine.MinesweeperEngine.__init__", "core_engine.MinesweeperEngine.step",
            "core_engine.MinesweeperEngine.reset_with_mines", "stage3_visualizer_ui.derive_answer_clues",
            "stage3_visualizer_ui.Stage3VisualizerCell.render_state",
        )
        with ExitStack() as stack:
            guards = [stack.enter_context(patch(name, side_effect=AssertionError(name))) for name in forbidden]
            for owner, names in ((w, ("refresh",)), (w.player, ("get_observation", "go_to", "next", "previous"))):
                guards.extend(stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
                              for name in names)
            for answers, route in ((True, False), (False, True), (True, True), (False, False)):
                w.answer_checkbox.setChecked(answers)
                w.route_checkbox.setChecked(route)
                clock.advance(1000)
                w.timer.timeout.emit()
                self.assertFalse(w.board_container.grab().isNull())
            self.assertTrue(w.error_label.isHidden(), w.error_label.text())
            self.assertEqual(w.modeled_playback.partial_modeled_us, 4)
            for guard in guards:
                guard.assert_not_called()

    def test_reference_overlays_update_on_index_autoplay_and_navigation(self):
        w = self.window
        w.answer_checkbox.setChecked(True)
        w.route_checkbox.setChecked(True)
        targets = ((0, 0), (1, 0), (0, 0), (2, 0), (2, 1))
        w.on_play_pause()
        for k in range(1, 6):
            w.timer.timeout.emit()
            self.assertEqual(w.route_overlay.targets, targets[:k])
            self.assertEqual(w.answer_overlay.hidden_mask,
                             tuple(tuple(value == H for value in row) for row in w.player.get_observation()))
        self.assertFalse(w.timer.isActive())
        for operation, k in ((w.on_previous, 4), (w.on_first, 0), (w.on_next, 1), (w.on_last, 5)):
            operation()
            self.assertEqual(w.route_overlay.targets, targets[:k])

    def test_close_with_reference_overlays_then_reopen_has_fresh_defaults(self):
        w, clock = self.create_modeled_window(1)
        w.answer_checkbox.setChecked(True)
        w.route_checkbox.setChecked(True)
        w.on_play_pause()
        clock.advance(7000)
        w.timer.timeout.emit()
        w.close()
        with patch.object(w, "refresh", side_effect=AssertionError("Closed refresh")), patch.object(
            w.player, "next", side_effect=AssertionError("Closed advance"),
        ):
            clock.advance(10**12)
            w.timer.timeout.emit()
        self.assertFalse(w.timer.isActive())
        self.assertFalse(w.modeled_playback.running)
        reopened = self.create_window(self.execution)
        self.assertFalse(reopened.answer_checkbox.isChecked())
        self.assertFalse(reopened.route_checkbox.isChecked())
        self.assertTrue(reopened.answer_overlay.isHidden())
        self.assertTrue(reopened.route_overlay.isHidden())
        self.assertEqual(reopened.route_overlay.targets, ())
        self.assertEqual(reopened.player.current_index, 0)

    def test_module_dependencies_allow_only_finalized_truth_for_reference_rendering(self):
        source = Path(stage3_visualizer_ui.__file__).read_text(encoding="utf-8")
        module = ast.parse(source)
        allowed = {"PyQt5", "core_engine", "stage3_execution", "stage3_trace_player",
                   "stage3_identity", "stage3_physical", "stage3_modeled_playback",
                   "visualization_reference_overlays"}
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                self.assertIn(name.split(".")[0], allowed)
        # The sole truth read must feed the neutral clue derivation, never a
        # planner/admissibility path or a private execution/Engine mutation.
        truth_reads = [node for node in ast.walk(module)
                       if isinstance(node, ast.Attribute) and node.attr == "mine_positions"]
        self.assertEqual(len(truth_reads), 1)
        self.assertEqual(ast.unparse(truth_reads[0]), "execution.board.mine_positions")
        derivations = [node for node in ast.walk(module) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name) and node.func.id == "derive_answer_clues"]
        self.assertEqual(len(derivations), 1)
        self.assertEqual([ast.unparse(arg) for arg in derivations[0].args],
                         ["execution.spec.width", "execution.spec.height", "execution.board.mine_positions"])
        self.assertIs(derivations[0].args[2], truth_reads[0])
        for forbidden in ("decision_compute_ns", "run_stage3", "run_expert_stage3_execution",
                          "plan_position", "subprocess", "ReplayData", "ReplayPlayer", "QSettings",
                          "load_timing_table", "authenticate_model_c", "action_cost", "._engine",
                          "same_board_comparison_ui", "exemplar_board_viewer_ui"):
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
            "benchmark_modeled_time.authenticate_model_c", "PyQt5.QtCore.QSettings",
            "pathlib.Path.read_bytes", "pathlib.Path.read_text",
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
            for interval in (20, 5000):
                window.interval_spin.setValue(interval)
                self.assertEqual(window.playback_label.text(),
                                 f"Playback: Index · {interval} ms/step (presentation)")
            for _ in self.execution.result.traces:
                window.timer.timeout.emit()
            self.assertEqual(window.player.current_index, 5)
            original = deepcopy(self.execution)
            modeled, clock = self.create_modeled_window()
            modeled.on_play_pause()
            clock.advance(63002500)
            modeled.timer.timeout.emit()
            modeled.on_play_pause()
            modeled.speed_combo.setCurrentText("8×")
            modeled.on_play_pause()
            clock.advance(self.execution.result.total_modeled_us * 1000)
            modeled.timer.timeout.emit()
            self.assertEqual(modeled.player.current_index, 5)
            self.assertEqual(modeled.player.cumulative_modeled_us, self.execution.result.total_modeled_us)
            self.assertEqual(self.execution, original)
            modeled.on_first()
            modeled.mode_combo.setCurrentText("Index")
            for mock in mocks:
                mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
