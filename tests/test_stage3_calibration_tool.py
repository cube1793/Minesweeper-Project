"""Synthetic event-driven Qt collection tests; all sessions live in temp dirs."""

import io
from contextlib import ExitStack
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import qt_bootstrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtCore import QEvent, QPointF, QSize, Qt, QTimer
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication, QPushButton
except ImportError:
    QApplication = None
else:
    import stage3_calibration_tool as tool


class BootstrapTests(unittest.TestCase):
    def test_game_keeps_the_same_bootstrap_entry_point(self):
        import main
        self.assertIs(main._configure_qt_plugin_path, qt_bootstrap.configure_qt_plugin_path)

    def test_non_windows_is_noop(self):
        with patch.object(sys, "platform", "linux"), patch.object(qt_bootstrap.os.path, "isdir") as isdir:
            qt_bootstrap.configure_qt_plugin_path()
        isdir.assert_not_called()

    def test_windows_preserves_original_candidate_order_and_override_behavior(self):
        fake = SimpleNamespace(__file__=os.path.join("root", "PyQt5", "__init__.py"))
        qt5 = os.path.join("root", "PyQt5", "Qt5", "plugins", "platforms")
        qt = os.path.join("root", "PyQt5", "Qt", "plugins", "platforms")
        for available, expected in (({qt5, qt}, qt5), ({qt}, qt), (set(), "existing")):
            with self.subTest(available=available), \
                 patch.object(sys, "platform", "win32"), \
                 patch.dict(sys.modules, {"PyQt5": fake}), \
                 patch.dict(os.environ, {"QT_QPA_PLATFORM_PLUGIN_PATH": "existing"}), \
                 patch.object(qt_bootstrap.os.path, "isdir", side_effect=lambda p: p in available):
                qt_bootstrap.configure_qt_plugin_path()
                self.assertEqual(os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"], expected)

    def test_bootstrap_failure_remains_nonfatal(self):
        with patch.object(sys, "platform", "win32"), \
             patch.dict(sys.modules, {"PyQt5": None}), \
             patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            qt_bootstrap.configure_qt_plugin_path()
        self.assertIn("Qt", stderr.getvalue())

    def test_game_worker_dispatch_still_precedes_bootstrap(self):
        import main
        with patch.object(sys, "argv", ["main.py", "--zini-metric-worker", "p", "r"]), \
             patch.object(main, "_configure_qt_plugin_path") as bootstrap, \
             patch("zini_metric_worker.main", return_value=7):
            self.assertEqual(main.main(), 7)
        bootstrap.assert_not_called()


class FakeClock:
    def __init__(self):
        self.now = 1_000_000_000
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.now

    def advance(self, delta=10_000_000):
        self.now += delta


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class CollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="stage3-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.clock = FakeClock()
        self.window = tool.CalibrationWindow(output_dir=self.temp.name, clock_ns=self.clock)
        self.addCleanup(self.close_window)
        self.window.show()
        self.app.processEvents()

    def close_window(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    @staticmethod
    def center(cell):
        return [cell[0] * 28 + 14.25, cell[1] * 28 + 13.75]

    def send_mouse(self, kind, cell, button=Qt.NoButton, buttons=Qt.NoButton, position=None):
        point = QPointF(*(self.center(cell) if position is None else position))
        event = QMouseEvent(kind, point, button, Qt.MouseButtons(buttons), Qt.NoModifier)
        self.app.sendEvent(self.window.canvas, event)

    def start(self):
        trial = self.window.current_trial
        self.send_mouse(QEvent.MouseButtonPress, trial.start_cell,
                        tool.BUTTONS[trial.start_button], tool.BUTTONS[trial.start_button])
        return trial

    def release_start(self, trial):
        self.clock.advance()
        self.send_mouse(QEvent.MouseButtonRelease, trial.start_cell, tool.BUTTONS[trial.start_button])

    def target(self, trial, release=True, kind=QEvent.MouseButtonPress):
        self.clock.advance()
        button = tool.BUTTONS[trial.target_button]
        self.send_mouse(kind, trial.target_cell, button, button)
        if release:
            self.send_mouse(QEvent.MouseButtonRelease, trial.target_cell, button)

    def valid_attempt(self):
        trial = self.start()
        self.release_start(trial)
        self.target(trial)
        return trial

    def records(self):
        return [json.loads(line) for line in self.window.writer.trials_path.read_text(encoding="utf-8").splitlines()]

    def select_trial(self, predicate):
        # Simulate an existing progress position to exercise one boundary/event,
        # without physically running hundreds of official trials in a UI test.
        self.window.trial_index = next(i for i, trial in enumerate(self.window.manifest.trials) if predicate(trial))
        self.window._refresh()
        return self.window.current_trial

    def test_single_canvas_and_start_target_are_present_before_timing(self):
        trial = self.window.current_trial
        self.assertEqual(self.window.state, tool.TrialState.READY)
        self.assertEqual((self.window.canvas.width(), self.window.canvas.height()), (840, 448))
        self.assertLessEqual(self.window.width(), 880)
        self.assertEqual(len(self.window.findChildren(QPushButton)), 1)
        self.assertTrue(self.window.canvas.hasMouseTracking())
        self.assertIn(f"START {trial.start_cell}", self.window.transition_label.text())
        self.assertIn(f"TARGET {trial.target_cell}", self.window.transition_label.text())
        self.assertIn(trial.start_button, self.window.transition_label.text())
        image = self.window.canvas.grab().toImage()
        self.assertFalse(image.isNull())
        self.assertNotEqual(image.pixelColor(trial.start_cell[0] * 28 + 1, trial.start_cell[1] * 28 + 1).name(), "#f5f7fa")
        self.assertIsNone(self.window._attempt)
        self.assertEqual(self.clock.calls, 0)

    def test_mapping_uses_logical_pixels_and_rejects_all_outer_edges(self):
        for position, expected in (((0, 0), (0, 0)), ((27.999, 27.999), (0, 0)),
                                   ((28, 28), (1, 1)), ((839.9, 447.9), (29, 15)),
                                   ((-0.1, 1), None), ((1, -0.1), None), ((840, 0), None), ((0, 448), None)):
            self.assertEqual(self.window.canvas.cell_at(position), expected)

    def test_wrong_ready_input_does_not_start_a_timed_attempt(self):
        trial = self.window.current_trial
        wrong_cell = ((trial.start_cell[0] + 1) % 30, trial.start_cell[1])
        correct = tool.BUTTONS[trial.start_button]
        wrong = Qt.RightButton if correct == Qt.LeftButton else Qt.LeftButton
        for cell, button, buttons in ((wrong_cell, correct, correct), (trial.start_cell, wrong, wrong),
                                      (trial.start_cell, correct, Qt.LeftButton | Qt.RightButton)):
            self.send_mouse(QEvent.MouseButtonPress, cell, button, buttons)
            self.send_mouse(QEvent.MouseButtonRelease, cell, button)
        self.assertEqual(self.window.state, tool.TrialState.READY)
        self.assertIsNone(self.window._attempt)
        self.assertEqual(self.window.attempt_indices, {})
        self.assertEqual(self.records(), [])

    def test_correct_start_enters_active_and_stores_actual_fractional_pixels(self):
        trial = self.start()
        self.assertEqual(self.window.state, tool.TrialState.ACTIVE)
        self.assertEqual(self.window._attempt["start_press_ns"], self.clock.now)
        self.assertEqual(self.window._attempt["start_press_px"], self.center(trial.start_cell))
        self.assertEqual(self.window._attempt["trajectory"][0]["relative_time_ns"], 0)
        self.assertEqual(self.records(), [])

    def test_start_enters_active_without_ui_or_io_after_timestamp(self):
        operations = [
            (self.window, "_refresh"), (self.window.canvas, "repaint"),
            (self.window.canvas, "update"), (self.window.writer, "append_attempt"),
            (QTimer, "singleShot"), (QTimer, "start"),
        ]
        operations.extend((label, "setText") for label in (
            self.window.progress_label, self.window.transition_label,
            self.window.status_label, self.window.output_label,
        ))
        expected_start = self.clock.now
        with ExitStack() as stack:
            spies = [stack.enter_context(patch.object(obj, name, wraps=getattr(obj, name)))
                     for obj, name in operations]
            self.start()
            self.app.processEvents()
            self.assertEqual(self.window.state, tool.TrialState.ACTIVE)
            self.assertEqual(self.window._attempt["start_press_ns"], expected_start)
            self.assertEqual(self.clock.calls, 1)
            for (_, name), spy in zip(operations, spies):
                with self.subTest(operation=name):
                    spy.assert_not_called()
        self.assertEqual(self.records(), [])

    def test_all_four_transitions_complete_validly_after_release(self):
        for start, target in (("LEFT", "LEFT"), ("LEFT", "RIGHT"), ("RIGHT", "LEFT"), ("RIGHT", "RIGHT")):
            with self.subTest(start=start, target=target):
                self.select_trial(lambda t: (t.start_button, t.target_button) == (start, target))
                trial = self.valid_attempt()
                record = self.records()[-1]
                self.assertTrue(record["valid"])
                self.assertIsNone(record["invalid_reason"])
                self.assertEqual(record["trial_id"], trial.trial_id)
                self.assertEqual(record["duration_ns"], 20_000_000)

    def test_start_release_is_required_even_for_same_button(self):
        self.select_trial(lambda t: t.start_button == t.target_button)
        trial = self.start()
        self.target(trial)
        self.assertEqual(self.records()[0]["invalid_reason"], "START_NOT_RELEASED")
        self.assertEqual(self.window.current_trial, trial)
        self.assertEqual(self.window.state, tool.TrialState.READY)

    def test_press_to_press_duration_and_trajectory_use_independent_boundaries(self):
        trial = self.start()
        start_time = self.clock.now
        self.release_start(trial)
        self.clock.advance(30_000_000)
        self.send_mouse(QEvent.MouseMove, trial.start_cell, position=[500.5, 200.25])
        self.clock.advance(90_000_000)
        self.target(trial)
        record = self.records()[0]
        self.assertEqual(record["duration_ns"], self.clock.now - start_time)
        self.assertEqual(record["duration_ns"], record["target_press_ns"] - record["start_press_ns"])
        self.assertEqual([s["kind"] for s in record["trajectory"]], ["start", "move", "target"])
        self.assertEqual(record["trajectory"][-1]["relative_time_ns"], record["duration_ns"])
        self.assertEqual(record["target_press_px"], self.center(trial.target_cell))
        self.assertTrue(all(type(s["relative_time_ns"]) is int for s in record["trajectory"]))
        self.assertLess(record["trajectory"][1]["relative_time_ns"], record["duration_ns"])

    def test_press_timestamps_are_captured_before_hit_testing(self):
        cell_at = self.window.canvas.cell_at

        def delayed_hit_test(position):
            self.clock.advance(1_000_000)
            return cell_at(position)

        expected_start = self.clock.now
        with patch.object(self.window.canvas, "cell_at", side_effect=delayed_hit_test):
            trial = self.start()
        self.release_start(trial)
        expected_target = self.clock.now
        with patch.object(self.window.canvas, "cell_at", side_effect=delayed_hit_test):
            self.send_mouse(QEvent.MouseButtonPress, trial.target_cell,
                            tool.BUTTONS[trial.target_button], tool.BUTTONS[trial.target_button])
        record = self.records()[0]
        self.assertEqual(record["start_press_ns"], expected_start)
        self.assertEqual(record["target_press_ns"], expected_target)
        self.assertEqual(record["duration_ns"], expected_target - expected_start)

    def test_explicit_endpoints_exist_without_move_events(self):
        trial = self.valid_attempt()
        samples = self.records()[0]["trajectory"]
        self.assertEqual([s["kind"] for s in samples], ["start", "target"])
        self.assertEqual([samples[0]["x_px"], samples[0]["y_px"]], self.center(trial.start_cell))
        self.assertEqual([samples[-1]["x_px"], samples[-1]["y_px"]], self.center(trial.target_cell))

    def test_zero_offset_double_click_event_is_a_real_target_press(self):
        self.select_trial(lambda t: t.offset_id == "O00" and t.start_button == t.target_button)
        trial = self.start()
        self.release_start(trial)
        self.target(trial, kind=QEvent.MouseButtonDblClick)
        self.assertTrue(self.records()[0]["valid"])
        self.assertEqual(len(self.records()[0]["trajectory"]), 2)
        self.assertEqual(self.records()[0]["start_press_px"], self.records()[0]["target_press_px"])

    def test_slow_correct_attempt_is_accepted(self):
        trial = self.start()
        self.release_start(trial)
        self.clock.advance(3 * 60 * 60 * 1_000_000_000)
        self.target(trial)
        self.assertTrue(self.records()[0]["valid"])
        self.assertGreater(self.records()[0]["duration_ns"], 10_000_000_000_000)

    def test_zero_duration_is_a_protocol_error_not_a_valid_sample(self):
        trial = self.start()
        self.send_mouse(QEvent.MouseButtonRelease, trial.start_cell, tool.BUTTONS[trial.start_button])
        self.send_mouse(QEvent.MouseButtonPress, trial.target_cell,
                        tool.BUTTONS[trial.target_button], tool.BUTTONS[trial.target_button])
        self.assertFalse(self.records()[0]["valid"])
        self.assertEqual(self.records()[0]["invalid_reason"], "NON_POSITIVE_DURATION")
        self.assertEqual(self.window.current_trial, trial)

    def test_wrong_target_and_wrong_button_are_preserved_and_retry_same_id(self):
        for reason in ("WRONG_TARGET", "WRONG_TARGET_BUTTON"):
            trial = self.start()
            self.release_start(trial)
            button = tool.BUTTONS[trial.target_button]
            cell = ((trial.target_cell[0] + 1) % 30, trial.target_cell[1])
            if reason == "WRONG_TARGET_BUTTON":
                button = Qt.RightButton if button == Qt.LeftButton else Qt.LeftButton
                cell = trial.target_cell
            self.clock.advance()
            self.send_mouse(QEvent.MouseButtonPress, cell, button, button)
            self.send_mouse(QEvent.MouseButtonRelease, cell, button)
            self.assertEqual(self.records()[-1]["invalid_reason"], reason)
            self.assertEqual(self.window.current_trial, trial)
        self.valid_attempt()
        records = self.records()
        self.assertEqual([r["attempt_index"] for r in records], [1, 2, 3])
        self.assertEqual({r["trial_id"] for r in records}, {trial.trial_id})
        self.assertEqual([r["valid"] for r in records], [False, False, True])

    def test_overlapping_buttons_invalidate_on_press_move_and_release(self):
        for kind in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease):
            with self.subTest(kind=kind):
                trial = self.start()
                self.clock.advance()
                other = Qt.RightButton if trial.start_button == "LEFT" else Qt.LeftButton
                self.send_mouse(kind, trial.start_cell, other, Qt.LeftButton | Qt.RightButton)
                self.assertEqual(self.records()[-1]["invalid_reason"], "BUTTON_OVERLAP")
                self.send_mouse(QEvent.MouseButtonRelease, trial.start_cell, other)

    def test_wrong_or_duplicate_release_and_missing_release_move_are_protocol_violations(self):
        for variant in ("wrong_release", "duplicate_release", "lost_release"):
            trial = self.start()
            if variant == "duplicate_release":
                self.release_start(trial)
            self.clock.advance()
            other = Qt.RightButton if trial.start_button == "LEFT" else Qt.LeftButton
            if variant == "lost_release":
                self.send_mouse(QEvent.MouseMove, trial.start_cell)
            else:
                button = other if variant == "wrong_release" else tool.BUTTONS[trial.start_button]
                self.send_mouse(QEvent.MouseButtonRelease, trial.start_cell, button)
            self.assertEqual(self.records()[-1]["invalid_reason"], "PROTOCOL_STATE")

    def test_pointer_leave_event_and_grabbed_outside_movement_invalidate(self):
        trial = self.start()
        self.clock.advance()
        self.app.sendEvent(self.window.canvas, QEvent(QEvent.Leave))
        self.assertEqual(self.records()[-1]["invalid_reason"], "POINTER_LEFT_CANVAS")
        self.send_mouse(QEvent.MouseButtonRelease, trial.start_cell, tool.BUTTONS[trial.start_button])
        self.start()
        self.clock.advance()
        self.send_mouse(QEvent.MouseMove, trial.start_cell, buttons=tool.BUTTONS[trial.start_button], position=[-0.5, 25])
        self.assertEqual(self.records()[-1]["invalid_reason"], "POINTER_LEFT_CANVAS")

    def test_window_deactivation_and_escape_interrupt_without_fake_target(self):
        for reason in ("WINDOW_DEACTIVATED", "MANUAL_INTERRUPT"):
            trial = self.start()
            self.clock.advance()
            if reason == "WINDOW_DEACTIVATED":
                self.app.sendEvent(self.window, QEvent(QEvent.WindowDeactivate))
            else:
                QTest.keyClick(self.window.canvas, Qt.Key_Escape)
            record = self.records()[-1]
            self.assertEqual(record["invalid_reason"], reason)
            self.assertIsNone(record["target_press_ns"])
            self.assertIsNone(record["target_press_px"])
            self.assertIsNone(record["duration_ns"])
            self.assertEqual(record["end_ns"], self.clock.now)
            self.assertEqual([s["kind"] for s in record["trajectory"]], ["start"])
            self.send_mouse(QEvent.MouseButtonRelease, trial.start_cell, tool.BUTTONS[trial.start_button])

    def test_ready_interrupt_events_do_not_create_attempts(self):
        self.app.sendEvent(self.window, QEvent(QEvent.WindowDeactivate))
        self.app.sendEvent(self.window.canvas, QEvent(QEvent.Leave))
        QTest.keyClick(self.window.canvas, Qt.Key_Escape)
        self.assertEqual(self.window.state, tool.TrialState.READY)
        self.assertEqual(self.records(), [])
        self.assertEqual(self.clock.calls, 0)

    def test_valid_advances_once_and_rearms_only_after_target_release(self):
        original_index = self.window.trial_index
        trial = self.start()
        self.release_start(trial)
        self.target(trial, release=False)
        self.assertEqual(self.window.trial_index, original_index + 1)
        self.start()  # A stale press cannot start the next attempt.
        self.assertEqual(self.window.state, tool.TrialState.READY)
        self.send_mouse(QEvent.MouseButtonRelease, trial.target_cell, tool.BUTTONS[trial.target_button])
        self.assertEqual(self.window.trial_index, original_index + 1)
        self.assertEqual(len(self.records()), 1)
        self.start()
        self.assertEqual(self.window.state, tool.TrialState.ACTIVE)

    def test_external_release_allows_retry_on_window_reactivation(self):
        trial = self.start()
        self.app.sendEvent(self.window, QEvent(QEvent.WindowDeactivate))
        with patch.object(QApplication, "mouseButtons", return_value=Qt.NoButton):
            self.app.sendEvent(self.window, QEvent(QEvent.WindowActivate))
        self.assertEqual(self.start(), trial)
        self.assertEqual(self.window.state, tool.TrialState.ACTIVE)

    def test_warmup_and_official_block_boundaries_require_continue(self):
        for index in (23, 151, 279):
            with self.subTest(index=index):
                self.window.trial_index = index
                self.window._refresh()
                self.valid_attempt()
                self.assertEqual(self.window.state, tool.TrialState.BLOCK_COMPLETE)
                self.assertEqual(self.window.trial_index, index + 1)
                count = len(self.records())
                self.start()
                self.assertEqual(len(self.records()), count)
                QTest.mouseClick(self.window.continue_button, Qt.LeftButton)
                self.assertEqual(self.window.state, tool.TrialState.READY)

    def test_final_trial_finishes_once_and_closes_complete_session(self):
        # Seed prior progress in memory; only the final trial receives events.
        self.window.trial_index = 407
        self.window.writer.accepted_ids.update(t.trial_id for t in self.window.manifest.trials[:-1])
        self.window.writer.valid_counts.update({"WARMUP": 24, "OFFICIAL": 383})
        self.window._refresh()
        self.valid_attempt()
        self.assertEqual(self.window.state, tool.TrialState.FINISHED)
        self.assertTrue(self.window.writer.closed)
        self.window.close()
        metadata = json.loads(self.window.writer.session_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["session_status"], "COMPLETED")
        self.assertEqual(metadata["valid_official_attempts"], 384)
        self.assertIsNotNone(metadata["session_ended_at_utc"])
        self.assertEqual(len(self.records()), 1)

    def test_incomplete_accepted_set_cannot_claim_completed_session(self):
        self.window.trial_index = 407
        with patch.object(sys, "stderr", new_callable=io.StringIO):
            self.valid_attempt()
        self.assertIn("Incomplete", self.window.storage_error)
        self.window.close()
        metadata = json.loads(self.window.writer.session_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["session_status"], "FAILED")

    def test_completed_attempt_is_appended_and_flushed_before_advancing(self):
        real_stream = self.window.writer._stream
        spy = Mock(wraps=real_stream)
        self.window.writer._stream = spy
        trial = self.start()
        self.release_start(trial)
        self.app.sendEvent(self.window, QEvent(QEvent.WindowDeactivate))
        self.assertEqual(spy.write.call_count, 1)
        self.assertEqual(spy.flush.call_count, 1)
        first_bytes = self.window.writer.trials_path.read_bytes()
        self.assertTrue(first_bytes.endswith(b"\n"))
        self.valid_attempt()
        self.assertEqual(spy.write.call_count, 2)
        self.assertEqual(spy.flush.call_count, 2)
        payload = self.window.writer.trials_path.read_bytes()
        self.assertTrue(payload.startswith(first_bytes))
        self.assertEqual(payload.count(b"\n"), 2)
        self.assertEqual([r["valid"] for r in self.records()], [False, True])

    def test_flush_failure_stops_without_advancing_or_retrying_append(self):
        spy = Mock(wraps=self.window.writer._stream)
        spy.flush.side_effect = OSError("disk unavailable")
        self.window.writer._stream = spy
        with patch.object(sys, "stderr", new_callable=io.StringIO):
            self.valid_attempt()
        self.assertEqual(self.window.state, tool.TrialState.FINISHED)
        self.assertEqual(self.window.trial_index, 0)
        self.assertEqual(self.window.writer.accepted_ids, set())
        self.assertIsNotNone(self.window._attempt)
        self.assertEqual(spy.write.call_count, 1)
        self.assertIn("disk unavailable", self.window.status_label.text())

    def test_close_active_preserves_invalid_attempt_and_marks_session_aborted(self):
        self.start()
        self.clock.advance()
        self.window.close()
        self.assertEqual(self.records()[0]["invalid_reason"], "WINDOW_CLOSED")
        metadata = json.loads(self.window.writer.session_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["session_status"], "ABORTED")
        self.assertEqual(metadata["invalid_attempts"], 1)

    def test_metadata_captures_protocol_manifest_environment_and_explicit_refresh_absence(self):
        metadata = json.loads(self.window.writer.session_path.read_text(encoding="utf-8"))
        required = {"protocol_version", "manifest_sha256", "manifest_path", "manifest_seed", "session_id",
                    "session_started_at_utc", "session_ended_at_utc", "session_status", "os", "python_version",
                    "python_implementation", "pyqt_version", "qt_version", "qt_platform", "clock",
                    "grid_width", "grid_height", "cell_size_px", "screen_name", "screen_resolution_logical_px",
                    "qt_logical_dpi", "device_pixel_ratio", "display_refresh_rate_hz",
                    "display_refresh_rate_status", "display_refresh_rate_unavailable_reason"}
        self.assertTrue(required <= metadata.keys())
        self.assertEqual(metadata["manifest_seed"], 20260930)
        self.assertEqual(metadata["manifest_sha256"], tool.FROZEN_MANIFEST_SHA256)
        self.assertEqual(metadata["protocol_version"], "STAGE3_CALIBRATION_V1")
        self.assertEqual((metadata["grid_width"], metadata["grid_height"], metadata["cell_size_px"]), (30, 16, 28))
        self.assertIsNone(metadata["display_refresh_rate_hz"])
        self.assertEqual(metadata["display_refresh_rate_unavailable_reason"], "virtual_platform")
        self.assertEqual(metadata["session_status"], "IN_PROGRESS")
        self.assertEqual(metadata["clock"], "injected")
        self.assertIn(metadata["session_id"], self.window.writer.trials_path.name)
        self.assertIn(metadata["session_id"], self.window.writer.session_path.name)

    def test_production_clock_defaults_to_perf_counter_ns(self):
        with patch.object(tool.time, "perf_counter_ns", return_value=123) as clock:
            other = tool.CalibrationWindow(output_dir=self.temp.name)
            try:
                self.assertIs(other.clock_ns, clock)
                self.assertEqual(other.writer.metadata["clock"], "time.perf_counter_ns")
                clock.assert_not_called()
            finally:
                other.close()
                other.deleteLater()

    def test_refresh_rate_metadata_cannot_change_timing_or_validity(self):
        for rate in (None, 60.0, 144.0):
            self.window.writer.metadata["display_refresh_rate_hz"] = rate
            self.valid_attempt()
        self.assertEqual([r["valid"] for r in self.records()], [True] * 3)
        self.assertEqual([r["duration_ns"] for r in self.records()], [20_000_000] * 3)

    def test_writer_refuses_duplicate_accepted_trial(self):
        self.valid_attempt()
        before = self.window.writer.trials_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Duplicate accepted trial ID"):
            self.window.writer.append_attempt(self.records()[0])
        self.assertEqual(self.window.writer.trials_path.read_bytes(), before)

    def test_separate_launches_never_overwrite_existing_session_files(self):
        first_bytes = self.window.writer.session_path.read_bytes()
        other = tool.CalibrationWindow(output_dir=self.temp.name, clock_ns=self.clock)
        try:
            self.assertNotEqual(other.writer.session_path, self.window.writer.session_path)
            self.assertNotEqual(other.writer.trials_path, self.window.writer.trials_path)
            self.assertEqual(self.window.writer.session_path.read_bytes(), first_bytes)
        finally:
            other.close()
            other.deleteLater()


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class FrozenInputAndMetadataTests(unittest.TestCase):
    def test_loader_reads_reviewed_file_without_regeneration(self):
        with patch("stage3_calibration.generate_manifest_v1", side_effect=AssertionError("Regeneration forbidden")):
            manifest = tool.load_frozen_manifest()
        self.assertEqual(manifest.seed, 20260930)
        self.assertEqual(len(manifest.trials), 408)

    def test_missing_modified_and_noncanonical_manifests_are_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            with self.assertRaises(FileNotFoundError):
                tool.load_frozen_manifest(path)
            original = tool.FROZEN_MANIFEST_PATH.read_bytes()
            for payload in (b"{}", original + b"\n", original.replace(b'20260930', b'20260931')):
                path.write_bytes(payload)
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    tool.load_frozen_manifest(path)

    def test_missing_manifest_fails_before_any_output_is_created(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            with self.assertRaises(FileNotFoundError):
                tool.CalibrationWindow(output_dir=output, manifest_path=Path(directory) / "missing.json")
            self.assertFalse(output.exists())

    def test_refresh_metadata_reports_approximate_values_and_preserves_absence(self):
        screen = SimpleNamespace(size=lambda: QSize(1920, 1080), name=lambda: "test-display",
                                 logicalDotsPerInch=lambda: 96.0, devicePixelRatio=lambda: 1.5,
                                 refreshRate=Mock(return_value=144.0))
        data = tool.display_metadata(screen, "windows")
        self.assertEqual(data["display_refresh_rate_hz"], 144.0)
        self.assertEqual(data["display_refresh_rate_status"], "qt_reported_approximate")
        self.assertIsNone(data["display_refresh_rate_unavailable_reason"])
        self.assertEqual(data["screen_resolution_logical_px"], [1920, 1080])
        for value in (None, 0, -1, math.nan, math.inf, True, "144"):
            screen.refreshRate.return_value = value
            data = tool.display_metadata(screen, "windows")
            self.assertIsNone(data["display_refresh_rate_hz"])
            self.assertEqual(data["display_refresh_rate_unavailable_reason"], "invalid_qt_report")
        screen.refreshRate.side_effect = RuntimeError("no refresh rate")
        self.assertEqual(tool.display_metadata(screen, "windows")["display_refresh_rate_unavailable_reason"], "qt_query_failed")
        self.assertIsNone(tool.display_metadata(None, "windows")["display_refresh_rate_hz"])
        screen.refreshRate.reset_mock()
        self.assertIsNone(tool.display_metadata(screen, "offscreen")["display_refresh_rate_hz"])
        screen.refreshRate.assert_not_called()

    def test_import_is_independent_of_engine_game_ui_and_output_creation(self):
        script = (
            "import builtins\n"
            "original = builtins.__import__\n"
            "def guarded(name, *args, **kwargs):\n"
            "    if name in ('core_engine', 'ui_manager', 'main', 'sqlite3'):\n"
            "        raise AssertionError(name)\n"
            "    return original(name, *args, **kwargs)\n"
            "builtins.__import__ = guarded\n"
            "import stage3_calibration_tool\n"
            "assert stage3_calibration_tool.load_frozen_manifest().seed == 20260930\n"
        )
        result = subprocess.run([sys.executable, "-c", script], cwd=tool.ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_entry_point_runs_standalone_and_closes_without_measurements(self):
        script = (
            "from PyQt5.QtCore import QTimer\n"
            "import stage3_calibration_tool as tool\n"
            "import sys\n"
            "original_show = tool.CalibrationWindow.show\n"
            "def show_then_close(window):\n"
            "    original_show(window)\n"
            "    QTimer.singleShot(0, window.close)\n"
            "tool.CalibrationWindow.show = show_then_close\n"
            "raise SystemExit(tool.main(['--output-dir', sys.argv[1], '--notes', 'synthetic startup test']))\n"
        )
        with TemporaryDirectory(prefix="stage3-synthetic-startup-") as directory:
            result = subprocess.run([sys.executable, "-c", script, directory], cwd=tool.ROOT,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            sessions = list(Path(directory).glob("calibration_session_*.json"))
            trials = list(Path(directory).glob("calibration_trials_*.jsonl"))
            self.assertEqual((len(sessions), len(trials)), (1, 1))
            metadata = json.loads(sessions[0].read_bytes())
            self.assertEqual(metadata["session_status"], "ABORTED")
            self.assertEqual(metadata["notes"], "synthetic startup test")
            self.assertEqual(trials[0].read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
