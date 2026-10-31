"""D4.2: independent presentation clocks and immutable archived frames only."""

import ast
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from fractions import Fraction
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()

from experiments import program_k_trace_adapter as k
from experiments import program_k_control_trace_adapter as c
from experiments import program_k_trace_comparison as pairs
from experiments import program_k_trace_comparison_demo as demo
from tests.test_program_k_trace_comparison import literal_pair

try:
    from PyQt5.QtCore import QEvent, QPoint, Qt, QTimer
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication, QLabel, QStyle, QStyleOptionSlider
    from experiments import program_k_trace_comparison_ui as ui
except ImportError:
    ui = None


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT, PROFILE = demo.DEFAULT_ARTIFACT_DIRECTORY, demo.DEFAULT_PROFILE
HAS_EVIDENCE = all((ARTIFACT / name).is_file() for name in ("qualification.json", "COMPLETE.json"))


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, ns):
        self.now += ns


class DemoTests(unittest.TestCase):
    def test_loads_admitted_pairs_once_without_options_for_execution(self):
        admitted = (literal_pair(),)
        with patch.object(demo, "load_accepted_e1_pairs", return_value=admitted) as load:
            self.assertIs(demo.load_demo_pairs(), admitted)
        load.assert_called_once_with(ARTIFACT, profile_path=PROFILE)

    def test_bad_evidence_stops_before_qt_startup(self):
        with patch.object(demo, "load_demo_pairs", side_effect=pairs.TraceComparisonError("bad evidence")), \
                patch.object(demo, "configure_qt_plugin_path") as setup, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(demo.main([]), 1)
            setup.assert_not_called()

    def test_help_does_not_load_evidence(self):
        with patch.object(demo, "load_demo_pairs") as load, redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stopped:
            demo.main(["--help"])
        self.assertEqual(stopped.exception.code, 0)
        load.assert_not_called()

    def test_ui_has_no_parser_loader_answer_lookup_or_execution_dependency(self):
        source = (ROOT / "experiments/program_k_trace_comparison_ui.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imports, {"time", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets",
                                  "experiments.program_k_control_trace_adapter", "experiments.program_k_trace_comparison",
                                  "experiments.program_k_trace_viewer"})
        for forbidden in ("answer_reference", "read_bytes", "load_accepted", "json.loads", "describe_knowledge",
                          "Stage3Execution", "KTracePresentation(", "subprocess", "QProcess"):
            self.assertNotIn(forbidden, source)

    def test_closed_source_files_remain_byte_identical(self):
        expected = {
            "experiments/program_k_trace_adapter.py": "43eea1a8f68ab8e333999d2b4f3ba7c4cd1e7b60a19e970a0dcb91a990cd61a4",
            "experiments/program_k_control_trace_adapter.py": "c65f0edeae364f7d40996b61401e9e44e56f1fccd7bc90e23178c3edde9d2330",
            "experiments/program_k_trace_comparison.py": "7df2ff741a9a41fac62afc98f5b500ccb03889b9e61d45c546b52e9823cb6388",
            "experiments/program_k_trace_viewer.py": "1ed58f418d2f557e3908dfd370a72181357af1d1fc90164a8d30c2db75d038b3",
            "experiments/program_k_trace_demo.py": "c062ed098ec675a4d90b7916ab1bf8325587e9f3d5d788dd361fbcc1337729c3",
            "tests/test_program_k_trace_adapter.py": "e03511fd512f92f56f20f831ac36bc6d2a084ee1f55d3f80cdf1edc9a7b6a81c",
            "tests/test_program_k_control_trace_adapter.py": "1793cfbd27cfb651e860af7b7549a6ed5932a4c8fee9a105919a56730a22601b",
            "tests/test_program_k_trace_comparison.py": "88d608452c4fb4480a6b4599f0d776e371943a1f65691ea96d26682cf436b87a",
            "tests/test_program_k_trace_viewer.py": "751e63cb0f44c8f886fb3342715ce6ebf2621aa7a9b578c9882a92aa0c32202b",
        }
        for file, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT / file).read_bytes()).hexdigest(), digest, file)


@unittest.skipIf(ui is None, "PyQt5 unavailable")
class PortableWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.admitted = (literal_pair(),)

    def setUp(self):
        self.clocks = (Clock(), Clock())
        self.window = ui.ProgramKComparisonWindow(self.admitted, control_clock=self.clocks[0], kp0_clock=self.clocks[1])
        self.window.resize(1400, 950)
        self.window.show()
        self.app.processEvents()
        self.panels = (self.window.control_panel, self.window.kp0_panel)

    def tearDown(self):
        self.window.close()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def snapshot(self, panel):
        return (panel.player.current_index, panel.player.current_frame, panel.playback.mode, panel.playback.model_speed,
                panel.playback.index_interval_ms, panel.playback.running, panel.playback.partial_modeled_us,
                panel.board.overlay.targets, panel.board.overlay.cursor_center,
                tuple((key, label.text()) for key, label in panel.detail_labels.items()))

    def start(self, panel, mode=ui.INDEX_MODE if ui else "Index"):
        panel.mode_combo.setCurrentText(mode)
        panel.on_play_pause()

    def tick(self, side, ns):
        self.clocks[side].advance(ns)
        self.panels[side]._advance_playback()

    def test_only_admitted_pair_type_and_control_domain_types(self):
        p = self.admitted[0]
        for invalid in ((), [], (p.control,), (p.kp0,), (p, p)):
            with self.assertRaises(TypeError):
                ui.ProgramKComparisonWindow(invalid)
        with self.assertRaises(TypeError):
            ui.ControlTracePlayer(p.kp0)
        self.assertIs(type(self.panels[0].player.presentation), c.ControlTracePresentation)

    def test_initial_frames_no_fabricated_action_route_or_knowledge(self):
        for panel in self.panels:
            self.assertEqual(panel.player.current_index, 0)
            self.assertIsNone(panel.player.current_action)
            self.assertEqual(panel.board.overlay.targets, ())
            self.assertIsNone(panel.board.overlay.action_target)
            self.assertTrue(all(cell.public_state == -2 for cell in panel.board.cells.values()))
            self.assertEqual(panel.detail_labels["action"].text(), "—")
        self.assertEqual(self.panels[1].board.knowledge_overlay.hidden_mines, frozenset())

    def test_owned_controllers_timers_players_and_clocks_are_independent(self):
        a, b = self.panels
        for name in ("player", "playback", "timer", "_clock"):
            self.assertIsNot(getattr(a, name), getattr(b, name))
        self.assertEqual(len(self.window.findChildren(QTimer)), 2)
        for name in ("player", "playback", "timer", "clock", "progress", "seek", "sync"):
            self.assertFalse(hasattr(self.window, name))

    def test_each_side_first_previous_next_last_exact_and_independent(self):
        for i, panel in enumerate(self.panels):
            other = self.panels[1 - i]
            before = self.snapshot(other)
            for button, target in ((panel.next_button, 1), (panel.last_button, panel.player.step_count),
                                   (panel.previous_button, panel.player.step_count - 1), (panel.first_button, 0)):
                QTest.mouseClick(button, Qt.LeftButton)
                self.assertEqual(panel.player.current_index, target)
                self.assertEqual(self.snapshot(other), before)

    def test_control_slider_does_not_change_k(self):
        before = self.snapshot(self.panels[1])
        self.panels[0].slider.setValue(2)
        self.assertEqual(self.panels[0].player.current_index, 2)
        self.assertEqual(self.snapshot(self.panels[1]), before)

    def test_k_slider_does_not_change_control(self):
        before = self.snapshot(self.panels[0])
        self.panels[1].slider.setValue(2)
        self.assertEqual(self.panels[1].player.current_index, 2)
        self.assertEqual(self.snapshot(self.panels[0]), before)

    def test_direct_track_seek_and_handle_press_cancel_only_own_partial(self):
        for i, panel in enumerate(self.panels):
            panel.on_first()
            self.start(panel)
            self.tick(i, 50000000)
            before = self.snapshot(self.panels[1 - i])
            option = QStyleOptionSlider()
            panel.slider.initStyleOption(option)
            handle = panel.slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, panel.slider)
            span = panel.slider.width() - handle.width()
            x = handle.width() // 2 + span * 2 // panel.player.step_count
            expected = QStyle.sliderValueFromPosition(0, panel.player.step_count, x - handle.width() // 2, span, option.upsideDown)
            QTest.mouseClick(panel.slider, Qt.LeftButton, pos=QPoint(x, panel.slider.height() // 2))
            self.assertEqual(panel.player.current_index, expected)
            self.assertFalse(panel.playback.running)
            self.assertEqual(panel.playback.progress, 0)
            self.assertEqual(self.snapshot(self.panels[1 - i]), before)
            panel.on_first()
            self.start(panel)
            self.tick(i, 50000000)
            panel.slider.initStyleOption(option)
            handle = panel.slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, panel.slider)
            QTest.mouseClick(panel.slider, Qt.LeftButton, pos=handle.center())
            self.assertEqual(panel.player.current_index, 0)
            self.assertEqual(panel.playback.progress, 0)

    def test_control_playback_does_not_advance_k(self):
        before = self.snapshot(self.panels[1])
        self.start(self.panels[0])
        self.tick(0, 200000000)
        self.assertEqual(self.panels[0].player.current_index, 1)
        self.assertEqual(self.snapshot(self.panels[1]), before)

    def test_k_playback_does_not_advance_control(self):
        before = self.snapshot(self.panels[0])
        self.start(self.panels[1])
        self.tick(1, 200000000)
        self.assertEqual(self.panels[1].player.current_index, 1)
        self.assertEqual(self.snapshot(self.panels[0]), before)

    def test_each_side_index_boundary_never_commits_early(self):
        for i, panel in enumerate(self.panels):
            self.start(panel)
            self.tick(i, 199999999)
            self.assertEqual(panel.player.current_index, 0)
            self.assertEqual(panel.playback.progress, Fraction(199999999, 200000000))
            self.tick(i, 1)
            self.assertEqual(panel.player.current_index, 1)
            self.assertEqual(panel.playback.progress, 0)
            panel.on_play_pause()

    def test_each_side_model_c_boundary_at_all_speeds(self):
        for i, panel in enumerate(self.panels):
            for speed_index, speed in enumerate(ui.SUPPORTED_SPEEDS):
                panel.on_first()
                panel.mode_combo.setCurrentText(ui.MODEL_C_MODE)
                panel.speed_combo.setCurrentIndex(speed_index)
                duration = Fraction(panel.player.pending_action.modeled_action_us * 1000, speed)
                self.assertEqual(duration.denominator, 1)
                panel.on_play_pause()
                self.tick(i, int(duration) - 1)
                self.assertEqual(panel.player.current_index, 0)
                self.tick(i, 1)
                self.assertEqual(panel.player.current_index, 1)
                panel.on_play_pause()

    def test_each_side_pause_resume_excludes_paused_time_in_both_modes(self):
        for i, panel in enumerate(self.panels):
            for mode in (ui.INDEX_MODE, ui.MODEL_C_MODE):
                panel.on_first()
                panel.mode_combo.setCurrentText(mode)
                duration = panel.playback.pending_duration_us * 1000
                panel.on_play_pause()
                self.tick(i, duration // 2)
                panel.on_play_pause()
                before = self.snapshot(panel)
                self.tick(i, duration * 10)
                self.assertEqual(self.snapshot(panel), before)
                panel.on_play_pause()
                self.tick(i, duration - duration // 2)
                self.assertEqual(panel.player.current_index, 1)
                panel.on_play_pause()

    def test_each_side_late_tick_catches_up_exactly_in_both_modes(self):
        for i, panel in enumerate(self.panels):
            for mode in (ui.INDEX_MODE, ui.MODEL_C_MODE):
                panel.on_first()
                panel.mode_combo.setCurrentText(mode)
                duration = (600000 if mode == ui.INDEX_MODE else sum(a.modeled_action_us for a in panel.player.presentation.actions[:3]))
                panel.on_play_pause()
                self.tick(i, duration * 1000)
                self.assertEqual(panel.player.current_index, 3)
                self.assertEqual(panel.playback.progress, 0)
                panel.cancel_partial()

    def test_partial_movement_keeps_each_committed_frame_route_cost_and_m(self):
        for i, panel in enumerate(self.panels):
            for mode in (ui.INDEX_MODE, ui.MODEL_C_MODE):
                panel.seek(1)
                frame = panel.player.current_frame
                route = panel.board.overlay.targets
                detail = panel.detail_labels["cumulative_modeled_us"].text()
                panel.mode_combo.setCurrentText(mode)
                duration = panel.playback.pending_duration_us * 1000
                panel.on_play_pause()
                self.tick(i, duration // 2)
                self.assertIs(panel.player.current_frame, frame)
                self.assertIs(panel.board.observation, frame.observation)
                self.assertEqual(panel.board.overlay.targets, route)
                self.assertEqual(panel.detail_labels["cumulative_modeled_us"].text(), detail)
                self.assertNotEqual(panel.board.overlay.cursor_center, ui._MotionOverlay.cell_center(frame.cursor))
                if i == 1:
                    self.assertEqual(panel.board.knowledge_overlay.hidden_mines, frame.hidden_logical_mines)
                    self.assertEqual(frame.logical_mines, frozenset())
                self.tick(i, duration - duration // 2)
                self.assertEqual(panel.player.current_index, 2)
                if i == 1:
                    self.assertEqual(panel.board.knowledge_overlay.hidden_mines, frozenset({(1, 0)}))
                panel.cancel_partial()

    def test_manual_seek_aligns_partial_cursor_route_and_m(self):
        for i, panel in enumerate(self.panels):
            self.start(panel)
            self.tick(i, 50000000)
            panel.seek(2)
            self.assertFalse(panel.playback.running)
            self.assertEqual(panel.playback.progress, 0)
            self.assertEqual(panel.board.overlay.cursor_center, ui._MotionOverlay.cell_center(panel.player.current_frame.cursor))
            self.assertEqual(panel.board.overlay.targets, panel.player.presentation.completed_route(2))
        self.assertEqual(self.panels[1].board.knowledge_overlay.hidden_mines, frozenset({(1, 0)}))

    def test_modes_rates_and_intervals_do_not_affect_other_panel(self):
        for i, panel in enumerate(self.panels):
            before = self.snapshot(self.panels[1 - i])
            panel.interval_spin.setValue(5000)
            panel.mode_combo.setCurrentText(ui.MODEL_C_MODE)
            panel.speed_combo.setCurrentIndex(5)
            self.assertEqual((panel.playback.index_interval_ms, panel.playback.model_speed), (5000, 8))
            self.assertEqual(self.snapshot(self.panels[1 - i]), before)

    def test_simultaneous_different_modes_rates_one_paused_and_terminal(self):
        a, b = self.panels
        a.interval_spin.setValue(100)
        b.mode_combo.setCurrentText(ui.MODEL_C_MODE)
        b.speed_combo.setCurrentIndex(0)
        a.on_play_pause()
        b.on_play_pause()
        self.tick(0, 200000000)
        self.tick(1, 100000000)
        a.on_play_pause()
        before = self.snapshot(a)
        self.tick(1, 600000000)
        self.assertEqual(self.snapshot(a), before)
        b.on_last()
        self.assertEqual((a.player.current_index, b.player.current_frame.status), (2, "WON"))
        self.assertEqual(a.player.current_frame.status, "PLAYING")

    def test_pair_selection_stops_both_and_discards_partial_without_reload(self):
        for i, panel in enumerate(self.panels):
            panel.seek(1)
            self.start(panel)
            self.tick(i, 50000000)
        old = tuple((p.player, p.playback) for p in self.panels)
        with patch.object(demo, "load_demo_pairs", side_effect=AssertionError("reload")), \
                patch.object(pairs, "load_accepted_e1_pairs", side_effect=AssertionError("reload")), \
                patch.object(Path, "open", side_effect=AssertionError("navigation IO")):
            self.window.select_pair(0)
        for panel, (player, playback) in zip(self.panels, old):
            self.assertFalse(playback.running)
            self.assertEqual(playback.progress, 0)
            self.assertIsNot(panel.player, player)
            self.assertFalse(panel.timer.isActive())
            self.assertEqual(panel.player.current_index, 0)
        self.assertEqual(self.panels[1].board.knowledge_overlay.hidden_mines, frozenset())

    def test_control_has_no_knowledge_layer_control_tooltips_are_physical(self):
        control = self.panels[0]
        self.assertIsNone(control.knowledge_checkbox)
        self.assertFalse(hasattr(control.board, "knowledge_overlay"))
        self.assertNotIn("category", control.detail_labels)
        for i in range(control.player.step_count + 1):
            control.seek(i)
            text = " ".join(cell.toolTip() for cell in control.board.cells.values())
            for phrase in ("K logical", "K input", "known mine", "K-CONTROL", "acquisition"):
                self.assertNotIn(phrase, text)
        control.seek(2)
        self.assertIn("executed CONTROL input", control.board.cells[1, 0].toolTip())

    def test_k_marker_hidden_then_flag_primary_and_auto_provenance(self):
        panel = self.panels[1]
        panel.seek(1)
        self.assertEqual(panel.board.knowledge_overlay.hidden_mines, frozenset())
        panel.seek(2)
        cell = panel.board.cells[1, 0]
        self.assertEqual(cell.public_state, -2)
        self.assertEqual(cell.text(), "")
        self.assertIn("K logical known mine", cell.toolTip())
        self.assertTrue(panel.board.knowledge_overlay.testAttribute(Qt.WA_TransparentForMouseEvents))
        panel.on_last()
        self.assertEqual((cell.public_state, cell.text()), (-3, "⚑"))
        self.assertIn("automatic WIN flag", cell.toolTip())
        self.assertNotIn("explicit physical FLAG", cell.toolTip())
        self.assertIn("K logical known mine", cell.toolTip())
        self.assertEqual(panel.board.knowledge_overlay.hidden_mines, frozenset())

    def test_control_automatic_flags_never_create_an_action(self):
        original = self.admitted[0].control
        # Unadmitted literal public-frame unit fixture; never passed to a loader.
        final = replace(original.frames[-1], explicit_flags=frozenset(), automatic_flags=frozenset({(1, 0)}))
        board = ui._ControlBoard(4, 1)
        board.render_frame(final)
        self.assertEqual(board.cells[1, 0].text(), "⚑")
        self.assertIn("automatic WIN flag; no executed FLAG input", board.cells[1, 0].toolTip())
        self.assertNotIn("explicit", board.cells[1, 0].toolTip())
        self.assertEqual(len(original.actions), 4)
        board.deleteLater()

    def test_logical_toggle_changes_no_playback_or_motion_state(self):
        panel = self.panels[1]
        panel.seek(2)
        self.start(panel)
        self.tick(1, 50000000)
        before = tuple(self.snapshot(p) for p in self.panels)
        self.clocks[1].advance(50000000)  # unsampled elapsed time stays unsampled
        panel.knowledge_checkbox.setChecked(False)
        self.assertEqual(tuple(self.snapshot(p) for p in self.panels), before)
        self.assertFalse(panel.board.knowledge_overlay.isVisible())
        panel.knowledge_checkbox.setChecked(True)
        self.assertEqual(tuple(self.snapshot(p) for p in self.panels), before)

    def test_all_frames_action_context_costs_prefix_route_and_cursor_exact(self):
        for panel in self.panels:
            for i, frame in enumerate(panel.player.presentation.frames):
                panel.seek(i)
                self.assertIs(panel.board.observation, frame.observation)
                self.assertEqual(panel.board.overlay.targets, panel.player.presentation.completed_route(i))
                self.assertEqual(len(panel.board.overlay.targets), i)
                self.assertEqual(panel.board.overlay.cursor_center, ui._MotionOverlay.cell_center(frame.cursor))
                self.assertEqual(panel.detail_labels["cumulative_modeled_us"].text(), f"{frame.cumulative_modeled_us:,} µs")
                if i:
                    a = panel.player.presentation.actions[i - 1]
                    for key, value in (("action", a.action), ("target", str(a.target)), ("cursor_before", str(a.cursor_before)),
                                       ("modeled_action_us", f"{a.modeled_action_us:,} µs"), ("status_after", a.status_after)):
                        self.assertEqual(panel.detail_labels[key].text(), value)

    def test_navigation_does_no_file_access_and_board_click_executes_nothing(self):
        with patch.object(Path, "open", side_effect=AssertionError("navigation IO")):
            for panel in self.panels:
                panel.on_next()
                panel.on_last()
                panel.on_previous()
                panel.on_first()
                before = self.snapshot(panel)
                QTest.mouseClick(panel.board.cells[0, 0], Qt.LeftButton)
                QTest.mouseClick(panel.board.cells[1, 0], Qt.RightButton)
                self.assertEqual(self.snapshot(panel), before)

    def test_no_comparative_judgment_labels_and_exact_difference_heading(self):
        w = self.window
        self.assertEqual(w.difference_heading.text(), "Recorded difference for this preserved case — K-P0 minus CONTROL")
        text = " ".join(label.text() for label in (w.difference_heading, w.difference_label, w.difference_note)).lower()
        for word in ("improvement", "speedup", "saved", "faster", "better", "superior", "efficiency gain", "optimal"):
            self.assertNotIn(word, text)
        self.assertIn(pairs.LIMITATION, w.limitation_label.text())
        self.assertIn(self.admitted[0].identity.board_fingerprint, w.fingerprint_label.text())

    def test_clock_failure_is_local_and_close_does_not_sample_either_clock(self):
        for panel in self.panels:
            self.start(panel)
        self.clocks[0].now = -1
        self.panels[0]._advance_playback()
        self.assertFalse(self.panels[0].playback.running)
        self.assertTrue(self.panels[0].error_label.isVisible())
        self.assertTrue(self.panels[1].playback.running)
        for panel in self.panels:
            panel.playback._clock = lambda: self.fail("close sampled clock")
        self.window.close()
        for panel in self.panels:
            self.assertFalse(panel.timer.isActive())
            self.assertFalse(panel.playback.running)
            self.assertTrue(panel._closed)


@unittest.skipUnless(HAS_EVIDENCE and ui is not None, "Accepted E1 archive or PyQt5 absent; no regeneration.")
class AcceptedWindowTests(PortableWindowTests):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.admitted = demo.load_demo_pairs()

    # The portable tests intentionally use the first pair's literal lifecycle.
    # Re-run them against the real admitted first pair as a D2/D3 regression.

    def test_exact_four_choices_and_pair_change_resets_both(self):
        self.assertEqual(self.window.pair_selector.count(), 4)
        for i, p in enumerate(self.admitted):
            self.assertEqual(self.window.pair_selector.itemData(i), p.identity.case_id)
            for side, panel in enumerate(self.panels):
                panel.on_first()
                self.start(panel)
                self.tick(side, 50000000)
            self.window.pair_selector.setCurrentIndex(i)
            self.window.select_pair(i)  # also exercises explicit reselection of the same case
            for panel in self.panels:
                self.assertEqual(panel.player.current_index, 0)
                self.assertFalse(panel.playback.running)
                self.assertEqual(panel.playback.progress, 0)
            self.assertEqual(self.panels[1].board.knowledge_overlay.hidden_mines, frozenset())

    def test_exact_accepted_summaries_and_signed_differences(self):
        expected = ((4, 3, -1, 1, -1, -1, -71406), (15, 14, -1, 3, -3, -1, -86720),
                    (3, 2, -1, 0, -1, 0, None), (227, 180, -47, 33, -51, -29, -8400666))
        for i, (p, values) in enumerate(zip(self.admitted, expected)):
            self.window.select_pair(i)
            for panel, facts in ((self.panels[0], p.control_facts), (self.panels[1], p.kp0_facts)):
                text = panel.summary_label.text()
                for text_value in (facts.outcome, f"Inputs {facts.total_inputs}", f"OPEN {facts.open_inputs}",
                                   f"FLAG {facts.flag_inputs}", f"CHORD {facts.chord_inputs}", f"{facts.model_c_total_us:,} µs"):
                    self.assertIn(text_value, text)
            self.assertEqual((p.control_facts.total_inputs, p.kp0_facts.total_inputs, p.difference.total_inputs,
                              p.difference.open_inputs, p.difference.flag_inputs, p.difference.chord_inputs,
                              p.difference.model_c_us), values)
            for caption, value in zip(("Inputs", "OPEN", "FLAG", "CHORD"), values[2:6]):
                self.assertIn(f"Δ {caption} " + (f"{value:+,}" if value else "0"), self.window.difference_label.text())
            self.assertIn(p.identity.board_fingerprint, self.window.fingerprint_label.text())
        self.window.select_pair(2)
        self.assertIn("Δ Model C N/A", self.window.difference_label.text())
        self.assertEqual(self.window.difference_note.text(), ui.LOSS_TIME_NOTE)

    def test_all_accepted_public_frames_and_routes_equal_each_source(self):
        for i, p in enumerate(self.admitted):
            self.window.select_pair(i)
            for panel, view in ((self.panels[0], p.control), (self.panels[1], p.kp0)):
                for index, frame in enumerate(view.frames):
                    panel.seek(index)
                    self.assertEqual(tuple(tuple(panel.board.cells[x, y].public_state for x in range(view.case.width))
                                           for y in range(view.case.height)), frame.observation)
                    self.assertEqual(panel.board.overlay.targets, view.completed_route(index))
                    if panel.is_control:
                        self.assertFalse(hasattr(panel.board, "knowledge_overlay"))
                    else:
                        self.assertEqual(panel.board.knowledge_overlay.hidden_mines, frame.hidden_logical_mines)

    def test_replan_explicit_k_flag_preserves_logical_provenance(self):
        self.window.select_pair(1)
        p = self.panels[1]
        action = next(a for a in p.player.presentation.actions if a.action == "FLAG")
        p.seek(action.input_index + 1)
        cell = p.board.cells[action.target]
        self.assertEqual(cell.text(), "⚑")
        self.assertIn("explicit physical FLAG", cell.toolTip())
        self.assertIn("K logical known mine", cell.toolTip())
        self.assertNotIn(action.target, p.board.knowledge_overlay.hidden_mines)

    def test_loss_feedback_is_independent_and_not_k_knowledge(self):
        self.window.select_pair(2)
        self.panels[0].on_last()
        self.assertEqual(self.panels[1].player.current_index, 0)
        self.assertEqual(self.panels[0].board.cells[2, 0].public_state, -4)
        self.panels[1].on_last()
        kframe = self.panels[1].player.current_frame
        self.assertEqual(self.panels[1].board.knowledge_overlay.hidden_mines, kframe.hidden_logical_mines)
        self.assertNotIn((2, 0), kframe.logical_mines)

    def test_expert_fixed_cell_size_independent_scroll_and_accessible_controls(self):
        self.window.select_pair(3)
        self.app.processEvents()
        for panel in self.panels:
            self.assertEqual((panel.board.width(), panel.board.height()), (840, 448))
            self.assertTrue(all(cell.size().width() == 28 for cell in panel.board.cells.values()))
            self.assertGreater(panel.scroll_area.horizontalScrollBar().maximum(), 0)
            self.assertGreaterEqual(panel.slider.width(), 400)
            self.assertTrue(panel.play_button.isVisible())
            self.assertTrue(panel.speed_combo.isVisible())
        a, b = self.panels
        a.scroll_area.horizontalScrollBar().setValue(a.scroll_area.horizontalScrollBar().maximum())
        self.assertEqual(b.scroll_area.horizontalScrollBar().value(), 0)
        frame = next(f for f in b.player.presentation.frames if f.hidden_logical_mines)
        b.seek(frame.index)
        self.assertTrue(b.board.knowledge_overlay.hidden_mines)
        self.assertEqual(a.player.current_index, 0)

    def test_fresh_process_denies_execution_imports_writes_and_processes(self):
        script = textwrap.dedent('''
            import importlib.abc
            import os
            from pathlib import Path
            import sys
            root = Path.cwd()
            local = {p.stem for p in root.glob('*.py')} - {'qt_bootstrap', 'stage3_modeled_playback', 'visualization_reference_overlays'}
            allowed = {'experiments.program_k_trace_adapter', 'experiments.program_k_control_trace_adapter',
                       'experiments.program_k_trace_comparison', 'experiments.program_k_trace_viewer',
                       'experiments.program_k_trace_comparison_ui', 'experiments.program_k_trace_comparison_demo'}
            class Guard(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.split('.')[0] in local or (fullname.startswith('experiments.') and fullname not in allowed):
                        raise AssertionError('Forbidden execution dependency: ' + fullname)
            sys.meta_path.insert(0, Guard())
            def audit(event, args):
                if event == 'open':
                    mode, flags = args[1:3]
                    assert not (isinstance(mode, str) and any(c in mode for c in 'wax+'))
                    assert not (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
                assert not event.startswith(('subprocess.', 'socket.'))
                assert event not in ('os.system', 'os.remove', 'os.rename', 'os.mkdir', 'os.fork', 'os.posix_spawn')
            sys.addaudithook(audit)
            from qt_bootstrap import configure_qt_plugin_path
            configure_qt_plugin_path()
            from PyQt5.QtCore import QEvent
            from PyQt5.QtWidgets import QApplication
            from experiments.program_k_trace_comparison_demo import load_demo_pairs
            from experiments.program_k_trace_comparison_ui import ProgramKComparisonWindow, MODEL_C_MODE
            admitted = load_demo_pairs()
            app = QApplication([])
            window = ProgramKComparisonWindow(admitted)
            window.show()
            for i in range(4):
                window.select_pair(i)
                for panel in (window.control_panel, window.kp0_panel):
                    panel.on_next()
                    panel.on_last()
                    panel.on_first()
                    panel.mode_combo.setCurrentText(MODEL_C_MODE)
                    panel.on_play_pause()
                    app.processEvents()
                    panel.on_play_pause()
                window.kp0_panel.knowledge_checkbox.setChecked(False)
                window.kp0_panel.knowledge_checkbox.setChecked(True)
            window.close()
            app.sendPostedEvents(None, QEvent.DeferredDelete)
            app.processEvents()
            assert not any(name in sys.modules for name in local)
            print('D4.2 import/write/process boundary PASS')
        ''')
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("boundary PASS", result.stdout)

    def test_artifact_profile_hashes_preserved(self):
        for path, digest in ((ARTIFACT / "qualification.json", k.QUALIFICATION_SHA256),
                             (ARTIFACT / "COMPLETE.json", k.COMPLETE_SHA256), (PROFILE, k.PROFILE_SHA256)):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
