"""Offscreen Qt integration, explicitly NOT human native acceptance."""

from contextlib import ExitStack
from fractions import Fraction
import os
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
from PyQt5.QtCore import QEvent, QObject, QPoint, QPointF, Qt, pyqtSignal
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication, QStyle, QStyleOptionSlider
from experiments.random_expert_exhibition_ui import AbsoluteSeekSlider, ExhibitionWindow, TracePanel
from experiments import random_expert_exhibition_model as model
from experiments.random_expert_exhibition_playback import INTERVAL_MODE, MODEL_C_MODE
from tests.test_random_expert_exhibition_execution import synthetic_expert_pair


def long_ui_pair():
    """Synthetic public trace for navigation only; no board generation or runner."""
    def trace(variant, count):
        empty, mine = frozenset(), frozenset({(29, 15)})
        rows = [[model.HIDDEN] * 30 for _ in range(16)]
        frames = [model.ExhibitionFrame(0, tuple(map(tuple, rows)), "PLAYING", (0, 0), 0, empty, empty, empty)]
        actions = []
        for i in range(count):
            last = i == count - 1
            target = (29, 15) if last else (i % 30, i // 30)
            rows[target[1]][target[0]] = model.EXPLODED if last else 1
            status = "LOST" if last else "PLAYING"
            before = frames[-1]
            knowledge = mine if variant == "K-P0" and i >= 1 else empty
            cost = 100000 + i * 10
            actions.append(model.ExhibitionAction(i, "OPEN", target, before.cursor, cost, status,
                                                 before.logical_mines, knowledge, 0 if last else 1))
            frames.append(model.ExhibitionFrame(i + 1, tuple(map(tuple, rows)), status, target,
                                               before.cumulative_modeled_us + cost, knowledge, empty, empty))
        return model.ExhibitionTrace(variant, tuple(actions), tuple(frames))
    base = synthetic_expert_pair()
    return model.ExhibitionPair(base.board, trace("V1", 200), trace("K-P0", 160), base.source)


def slider_geometry(slider):
    option = QStyleOptionSlider()
    slider.initStyleOption(option)
    style = slider.style()
    return option, style.subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, slider), \
        style.subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)


def click_frame(slider, value):
    option, groove, handle = slider_geometry(slider)
    span = groove.width() - handle.width()
    x = groove.x() + handle.width() // 2 + QStyle.sliderPositionFromValue(
        slider.minimum(), slider.maximum(), value, span, option.upsideDown)
    point = QPoint(x, groove.center().y())
    QTest.mousePress(slider, Qt.LeftButton, pos=point)
    at_press = slider.value()
    QTest.mouseRelease(slider, Qt.LeftButton, pos=point)
    return at_press


class FakeJob(QObject):
    finished = pyqtSignal(object, str, object)
    progressed = pyqtSignal(object, object)

    def __init__(self):
        super().__init__()
        self.state, self.last_record, self._phase = "idle", None, None
        self.records = []
        self.elapsed, self.token, self.starts = 0, 0, []
        self.fail_close = False

    def start(self, index):
        if self.state != "idle":
            raise RuntimeError("busy")
        self.token += 1
        self.starts.append(index)
        self.state = "running"
        return self.token

    def cancel(self):
        self.state = "cancelling"

    def shutdown(self):
        if self.fail_close:
            self.state = "blocked"
            raise RuntimeError("test cleanup failure")
        self.state = "closed"

    def publish(self, pair):
        self.state = "idle"
        self.finished.emit(self.token, "SUCCEEDED", pair)


class ExhibitionUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.pair = synthetic_expert_pair()
        cls.long_pair = long_ui_pair()

    def setUp(self):
        self.job = FakeJob()
        self.window = ExhibitionWindow(job=self.job)
        self.window.show()
        self.addCleanup(self.window.close)

    def install(self):
        self.window.run_index(11)
        self.job.publish(self.pair)

    def install_long(self):
        self.now = 0
        for panel in (self.window.left, self.window.right):
            panel._clock = lambda: self.now
        self.window.run_index(11)
        self.job.publish(self.long_pair)
        return self.window.left, self.window.right

    def test_common_play_pause_are_idempotent_with_one_side_already_running(self):
        left, right = self.install_long()
        self.assertTrue(self.window.play_all_button.isEnabled())
        self.assertFalse(self.window.pause_all_button.isEnabled())
        self.assertFalse(self.window.reset_all_button.isEnabled())
        left.seek(20)
        right.seek(5)
        left.change_interval(200)
        right.change_cps(3)
        left.play()
        self.now = 100_000_000
        anchor = left.playback._last_clock_ns
        QTest.mouseClick(self.window.play_all_button, Qt.LeftButton)
        self.window.play_all()
        self.assertEqual(left.playback._last_clock_ns, anchor)
        self.assertTrue(left.playback.running and right.playback.running)
        self.assertFalse(self.window.play_all_button.isEnabled())
        self.now = 200_000_000
        left.tick()
        right.tick()
        self.assertEqual((left.player.current_index, right.player.current_index), (21, 5))
        self.assertEqual(right.playback.progress, Fraction(3, 10))
        QTest.mouseClick(self.window.pause_all_button, Qt.LeftButton)
        fraction = right.playback.progress
        self.window.pause_all()
        self.assertEqual(right.playback.progress, fraction)
        self.assertFalse(left.playback.running or right.playback.running)
        self.assertFalse(left.timer.isActive() or right.timer.isActive())
        self.assertEqual((left.playback.interval_ms, right.playback.cps), (200, 3))

    def test_common_play_ended_side_and_both_ended_never_rewind(self):
        left, right = self.install_long()
        left.seek(left.player.step_count)
        self.window.play_all()
        self.assertFalse(left.playback.running)
        self.assertTrue(right.playback.running)
        self.assertEqual(left.player.current_index, 200)
        right.seek(right.player.step_count)
        self.assertFalse(self.window.play_all_button.isEnabled())
        self.assertFalse(self.window.pause_all_button.isEnabled())
        self.assertTrue(self.window.reset_all_button.isEnabled())
        self.window.play_all()
        self.assertEqual((left.player.current_index, right.player.current_index), (200, 160))

    def test_common_reset_drops_partial_restores_frame_zero_and_keeps_pair_and_settings(self):
        left, right = self.install_long()
        left.change_cps(3)
        right.change_interval(1000)
        left.mode.setCurrentIndex(1)
        left.speed.setCurrentIndex(4)  # Model C 4x
        left.seek(2)
        right.seek(1)
        self.window.play_all()
        self.now = 10_000_000
        left.tick()
        right.tick()
        self.assertGreater(right.playback.progress, 0)
        self.assertFalse(right.board.frame.logical_mines)  # next frame knows M; not committed
        QTest.mouseClick(self.window.reset_all_button, Qt.LeftButton)
        self.assertIs(self.window.pair, self.long_pair)
        for panel, trace in ((left, self.long_pair.v1), (right, self.long_pair.k)):
            self.assertIs(panel.board.frame, trace.frames[0])
            self.assertEqual(panel.player.current_index, 0)
            self.assertEqual(panel.playback.progress, 0)
            self.assertEqual(panel.board.route, ())
            self.assertEqual(panel.board.frame.cumulative_modeled_us, 0)
            self.assertFalse(panel.board.frame.logical_mines)
            self.assertFalse(panel.timer.isActive() or panel.playback.running)
        self.assertEqual((left.playback.mode, left.playback.model_speed, left.playback.cps), (MODEL_C_MODE, 4, 3))
        self.assertEqual(right.playback.interval_ms, 1000)
        self.assertFalse(self.window.reset_all_button.isEnabled())

    def test_common_controls_follow_empty_busy_cancel_clear_and_close(self):
        buttons = (self.window.play_all_button, self.window.pause_all_button, self.window.reset_all_button)
        self.assertFalse(any(b.isEnabled() for b in buttons))
        self.window.play_all()
        self.window.reset_all()
        left, right = self.install_long()
        self.window.play_all()
        self.now = 50_000_000
        self.window.run_index(97)
        self.assertFalse(any(b.isEnabled() for b in buttons))
        self.assertFalse(left.timer.isActive() or right.timer.isActive())
        self.window.cancel()
        self.job.state = "idle"
        self.job.finished.emit(self.job.token, "CANCELLED", {})
        self.assertFalse(any(b.isEnabled() for b in buttons))
        self.install_long()
        left.clear()
        self.assertFalse(any(b.isEnabled() for b in buttons))
        left.install(self.long_pair.v1)
        self.window.play_all()
        self.now = 70_000_000
        left.tick()
        right.tick()
        self.window.close()
        self.assertTrue(self.window._closed)
        self.assertFalse(any(b.isEnabled() for b in buttons))
        self.assertFalse(left.timer.isActive() or right.timer.isActive())
        self.assertFalse(left.playback.running or right.playback.running)

    def test_actual_groove_click_seeks_selected_panel_only_and_discards_partial(self):
        left, right = self.install_long()
        self.window.resize(1920, 1000)
        QApplication.processEvents()
        self.window.play_all()
        self.now = 125_000_000
        left.tick()
        right.tick()
        right_state = (right.player.current_frame, right.playback.progress, right.playback.running)
        at_press = click_frame(left.slider, 180)
        self.assertAlmostEqual(at_press, 180, delta=1)
        self.assertEqual(left.player.current_index, at_press)
        self.assertIs(left.board.frame, self.long_pair.v1.frames[at_press])
        self.assertEqual(len(left.board.route), at_press)
        self.assertEqual(left.playback.progress, 0)
        self.assertFalse(left.playback.running or left.timer.isActive())
        self.assertEqual((right.player.current_frame, right.playback.progress, right.playback.running), right_state)
        at_press = click_frame(left.slider, 20)
        self.assertAlmostEqual(at_press, 20, delta=1)
        left_state = (left.player.current_frame, left.playback.progress)
        at_press = click_frame(right.slider, 145)
        self.assertAlmostEqual(at_press, 145, delta=1)
        self.assertIs(right.board.frame, self.long_pair.k.frames[at_press])
        self.assertEqual(right.board.frame.logical_mines, self.long_pair.k.frames[at_press].logical_mines)
        self.assertFalse(right.playback.running)
        self.assertEqual((left.player.current_frame, left.playback.progress), left_state)

    def test_custom_input_commit_reciprocal_rounding_and_no_feedback_drift(self):
        left, right = self.install_long()
        cps_signal, ms_signal = QSignalSpy(left.cps_box.valueChanged), QSignalSpy(left.interval_ms_box.valueChanged)
        left.cps_box.setFocus()
        left.cps_box.selectAll()
        QTest.keyClick(left.cps_box, Qt.Key_Backspace)
        self.assertEqual(left.playback.cps, 4)
        QTest.keyClicks(left.cps_box, "3")
        self.assertEqual(left.playback.cps, 4)  # not applied during typing
        QTest.keyClick(left.cps_box, Qt.Key_Return)
        self.assertEqual(left.playback.cps, 3)
        self.assertEqual(left.interval_ms_box.value(), 333.333)
        self.assertIsNone(left.interval.currentData())
        self.assertIn("≈333.333", left.pacing_note.text())
        self.assertEqual((len(cps_signal), len(ms_signal)), (1, 0))
        duration = left.playback.interval_us
        for _ in range(20):
            left._sync_interval_controls()
            QTest.keyClick(left.interval_ms_box, Qt.Key_Return)
        self.assertEqual(left.playback.interval_us, duration)
        self.assertEqual((len(cps_signal), len(ms_signal)), (1, 0))
        self.assertEqual(right.playback.cps, 4)
        left.interval_ms_box.setValue(249)
        self.assertEqual(left.playback.interval_ms, 249)
        self.assertEqual(left.cps_box.value(), 4.016)
        self.assertIn("≈4.016", left.pacing_note.text())
        for preset, index in ((250, 0), (200, 1), (500, 2)):
            left.interval.setCurrentIndex(index)
            self.assertEqual(left.playback.interval_ms, preset)
            self.assertEqual(left.interval.currentData(), preset)

    def test_manual_spin_and_model_mode_keep_partial_and_independent_preferences(self):
        left, right = self.install_long()
        left.play()
        self.now = 125_000_000
        left.cps_box.setValue(3)
        self.assertEqual(left.playback.progress, Fraction(1, 2))
        self.assertTrue(left.playback.running)
        self.assertIs(left.board.frame, self.long_pair.v1.frames[0])
        left.pause()
        left.interval_ms_box.setValue(1000)
        left.interval_ms_box.stepUp()
        self.assertEqual(left.playback.interval_ms, 1010)
        self.assertEqual(left.playback.progress, Fraction(1, 2))
        self.assertFalse(left.playback.running)
        left.change_cps(3)
        duration = left.playback.interval_us
        left.mode.setCurrentIndex(1)
        self.assertFalse(left.interval_ms_box.isEnabled() or left.cps_box.isEnabled() or left.interval.isEnabled())
        self.assertTrue(left.speed.isEnabled())
        left.speed.setCurrentIndex(5)
        self.assertEqual(left.playback.pending_duration_us, self.long_pair.v1.actions[0].modeled_action_us)
        left.mode.setCurrentIndex(0)
        self.assertEqual(left.playback.interval_us, duration)
        self.assertEqual(left.playback.progress, Fraction(1, 2))
        self.assertEqual(left.playback.model_speed, 8)
        self.assertEqual(right.playback.interval_ms, 250)

    def test_manual_bounds_and_preferences_survive_clear_install(self):
        left, _ = self.install_long()
        for ms, cps in ((20, 50), (10000, .1)):
            left.interval_ms_box.setValue(ms)
            self.assertEqual(left.cps_box.value(), cps)
            self.assertEqual(left.playback.interval_ms, ms)
        left.cps_box.setValue(3)
        duration = left.playback.interval_us
        left.clear()
        self.assertFalse(left.interval_ms_box.isEnabled() or left.cps_box.isEnabled())
        self.assertEqual((left.slider.minimum(), left.slider.maximum()), (0, 0))
        left.install(self.long_pair.v1)
        self.assertEqual(left.playback.interval_us, duration)

    def test_common_seek_timing_do_not_execute_generate_read_or_change_source(self):
        left, right = self.install_long()
        source = self.long_pair.source
        trace_ids = (id(left.player.trace), id(right.player.trace))
        with ExitStack() as stack:
            for target in ("builtins.open", "io.open", "core_engine.MinesweeperEngine",
                           "benchmark_board.generate_board", "experiments.random_expert_exhibition_execution.run_expert_pair",
                           "experiments.random_expert_exhibition_execution.run_control_capture",
                           "experiments.random_expert_exhibition_execution.run_k_p0"):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            self.window.play_all()
            self.now = 125_000_000
            left.change_cps(3)
            right.change_interval(123.456)
            self.window.pause_all()
            left.seek(140)
            right.seek(80)
            self.window.reset_all()
        self.assertIs(self.window.pair.source, source)
        self.assertEqual((id(left.player.trace), id(right.player.trace)), trace_ids)
        self.assertEqual(self.job.starts, [11])

    def test_controls_index_input_and_duplicate_start_block(self):
        for invalid in ("-1", "100000", "2010000", "11.0", "abc", ""):
            self.window.index_edit.setText(invalid)
            self.window.run_entered_index()
        self.assertFalse(self.job.starts)
        self.window.index_edit.setText("99999")
        QTest.mouseClick(self.window.run_button, Qt.LeftButton)
        self.assertEqual(self.job.starts, [99999])
        self.assertFalse(self.window.draw_button.isEnabled())
        self.assertTrue(self.window.cancel_button.isEnabled())
        self.window.run_index(11)
        self.assertEqual(self.job.starts, [99999])

    def test_draw_uses_current_index_only(self):
        with patch("experiments.random_expert_exhibition_ui.draw_index", return_value=97) as draw:
            QTest.mouseClick(self.window.draw_button, Qt.LeftButton)
            draw.assert_called_once_with(None)
        self.assertEqual(self.job.starts, [97])

    def test_complete_installs_separate_paused_players_with_250ms_default(self):
        self.install()
        left, right = self.window.left, self.window.right
        self.assertIsNot(left.player, right.player)
        self.assertIsNot(left.playback, right.playback)
        self.assertIsNot(left.timer, right.timer)
        self.assertEqual(left.playback.interval_ms, 250)
        self.assertEqual(right.playback.interval_ms, 250)
        self.assertFalse(left.playback.running)
        self.assertIn("fingerprint", self.window.identity.text())
        self.assertIn("미커밋", self.window.info_button.toolTip())
        self.assertTrue(self.window.run_button.isEnabled())

    def test_stale_result_and_completion_after_cancel_do_not_install(self):
        self.window.run_index(11)
        self.window.completed(self.job.token + 1, "SUCCEEDED", self.pair)
        self.assertIsNone(self.window.pair)
        self.window.cancel()
        self.job.publish(self.pair)
        self.assertIsNone(self.window.pair)
        self.assertIsNone(self.window.left.player)

    def test_independent_navigation_timer_speed_and_frame_commit(self):
        self.install()
        left, right = self.window.left, self.window.right
        QTest.mouseClick(left.last, Qt.LeftButton)
        self.assertEqual((left.player.current_index, right.player.current_index), (1, 0))
        QTest.mouseClick(left.first, Qt.LeftButton)
        left.interval.setCurrentIndex(2)
        self.assertEqual((left.playback.interval_ms, right.playback.interval_ms), (500, 250))
        left.slider.setValue(1)
        self.assertEqual(left.board.frame, self.pair.v1.frames[1])
        self.assertEqual(right.board.frame, self.pair.k.frames[0])
        self.assertEqual(left.board.route, ((0, 0),))

    def test_panel_partial_motion_and_actual_qtimer(self):
        now = [0]
        panel = TracePanel("test", clock=lambda: now[0])
        self.addCleanup(panel.close)
        panel.install(self.pair.k)
        panel.toggle()
        now[0] = 125_000_000
        QTest.qWait(30)
        self.assertEqual(panel.player.current_index, 0)
        self.assertFalse(panel.board.frame.automatic_flags)
        self.assertEqual(panel.board.route, ())
        now[0] = 250_000_000
        QTest.qWait(30)
        self.assertEqual(panel.player.current_index, 1)
        self.assertFalse(panel.timer.isActive())
        self.assertEqual(len(panel.board.frame.automatic_flags), 99)

    def test_1920_layout_and_per_panel_small_window_scroll(self):
        self.install()
        self.window.resize(1920, 1000)
        QTest.qWait(10)
        for panel in (self.window.left, self.window.right):
            self.assertEqual((panel.board.width(), panel.board.height()), (840, 448))
            self.assertEqual(panel.scroll.horizontalScrollBar().maximum(), 0)
            self.assertEqual(panel.scroll.verticalScrollBar().maximum(), 0)
        self.window.resize(900, 700)
        QTest.qWait(10)
        for panel in (self.window.left, self.window.right):
            self.assertGreater(panel.scroll.horizontalScrollBar().maximum(), 0)

    def test_close_cleanup_failure_rejects_close_and_blocks_start(self):
        self.window.run_index(11)
        self.job.fail_close = True
        self.window.close()
        self.assertFalse(self.window._closed)
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.run_button.isEnabled())
        self.assertIn("닫기 보류", self.window.status.text())
        self.job.fail_close = False
        self.window.close()
        self.assertTrue(self.window._closed)
        self.window.completed(self.job.token, "SUCCEEDED", self.pair)
        self.assertIsNone(self.window.pair)

    def test_info_note_and_success_metrics_are_not_effectiveness_claims(self):
        self.install()
        self.assertIn("K-P0 − V1", self.window.difference.text())
        self.assertIn("Model C 승리 시간", self.window.difference.text())
        self.assertNotIn("preserved", self.window.windowTitle().lower())
        self.assertIn("OPEN 1 / FLAG 0 / CHORD 0", self.window.left.summary.text())


class AbsoluteSeekSliderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.slider = AbsoluteSeekSlider()
        self.slider.setRange(0, 200)
        self.slider.setPageStep(10)
        self.slider.resize(600, 40)
        self.slider.show()
        QApplication.processEvents()
        self.addCleanup(self.slider.close)

    def test_real_far_groove_presses_and_releases_seek_absolute_both_ways(self):
        slider = self.slider
        for value in (180, 20, 200, 0):
            at_press = click_frame(slider, value)
            self.assertAlmostEqual(at_press, value, delta=1)
            self.assertEqual(slider.value(), at_press)  # release must not add a page step
        QTest.qWait(30)
        self.assertEqual(slider.value(), 0)

    def test_handle_off_center_press_drag_release_retains_native_grab_offset(self):
        slider = self.slider
        slider.setValue(100)
        _, groove, handle = slider_geometry(slider)
        start = QPoint(handle.left() + 1, handle.center().y())
        span = groove.width() - handle.width()
        finish = start + QPoint(round(span * .2), 0)
        QTest.mousePress(slider, Qt.LeftButton, pos=start)
        self.assertEqual(slider.value(), 100)
        self.assertTrue(slider.isSliderDown())
        # Offscreen QTest.mouseMove does not deliver a held-button move on Windows.
        # Keep real QTest press/release and send the intervening Qt drag event explicitly.
        QApplication.sendEvent(slider, QMouseEvent(QEvent.MouseMove, QPointF(finish),
                                                  Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        at_move = slider.value()
        QTest.mouseRelease(slider, Qt.LeftButton, pos=finish)
        self.assertAlmostEqual(at_move, 140, delta=1)
        self.assertEqual(slider.value(), at_move)
        self.assertFalse(slider.isSliderDown())

    def test_resize_small_empty_and_disabled_ranges_are_safe(self):
        slider = self.slider
        for width in (90, 800, 60):
            slider.resize(width, 40)
            QApplication.processEvents()
            slider.setValue(100)
            click_frame(slider, 200)
            self.assertEqual(slider.value(), 200)
            click_frame(slider, 0)
            self.assertEqual(slider.value(), 0)
        slider.setEnabled(False)
        click_frame(slider, 200)
        self.assertEqual(slider.value(), 0)
        slider.setEnabled(True)
        slider.setRange(0, 0)
        QTest.mousePress(slider, Qt.LeftButton, pos=QPoint(40, 20))
        QTest.mouseRelease(slider, Qt.LeftButton, pos=QPoint(40, 20))
        self.assertEqual(slider.value(), 0)

    def test_keyboard_and_right_to_left_geometry_remain_native(self):
        slider = self.slider
        slider.setValue(100)
        QTest.keyClick(slider, Qt.Key_Right)
        self.assertEqual(slider.value(), 101)
        QTest.keyClick(slider, Qt.Key_End)
        self.assertEqual(slider.value(), 200)
        QTest.keyClick(slider, Qt.Key_Home)
        self.assertEqual(slider.value(), 0)
        slider.setLayoutDirection(Qt.RightToLeft)
        for value in (180, 20, 200, 0):
            click_frame(slider, value)
            self.assertAlmostEqual(slider.value(), value, delta=1)


if __name__ == "__main__":
    unittest.main()
