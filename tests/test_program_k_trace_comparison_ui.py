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

    @unittest.skipIf(ui is None, "PyQt5 unavailable")
    def test_launcher_opens_maximized_without_changing_window_geometry_contract(self):
        admitted = (literal_pair(),)
        with patch.object(demo, "load_demo_pairs", return_value=admitted) as load, \
                patch.object(demo, "configure_qt_plugin_path"), \
                patch("PyQt5.QtWidgets.QApplication") as app_type, \
                patch.object(ui, "ProgramKComparisonWindow") as window_type, redirect_stdout(io.StringIO()):
            app_type.instance.return_value.exec_.return_value = 0
            self.assertEqual(demo.main([]), 0)
            load.assert_called_once_with(ARTIFACT, profile_path=PROFILE)
            window_type.assert_called_once_with(admitted)
            window_type.return_value.showMaximized.assert_called_once_with()
            window_type.return_value.show.assert_not_called()
            app_type.instance.return_value.exec_.assert_called_once_with()

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
            "experiments/program_k_trace_comparison_demo.py": "67113bf21e8819aed0daa801a15c0515336f3fc37e9861b7c8d0c1be0d20b972",
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
        panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(mode))
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
                panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(ui.MODEL_C_MODE))
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
                panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(mode))
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
                panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(mode))
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
                panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(mode))
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
            panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(ui.MODEL_C_MODE))
            panel.speed_combo.setCurrentIndex(5)
            self.assertEqual((panel.playback.index_interval_ms, panel.playback.model_speed), (5000, 8))
            self.assertEqual(self.snapshot(self.panels[1 - i]), before)

    def test_simultaneous_different_modes_rates_one_paused_and_terminal(self):
        a, b = self.panels
        a.interval_spin.setValue(100)
        b.mode_combo.setCurrentIndex(b.mode_combo.findData(ui.MODEL_C_MODE))
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
                    for key, value in (("action", ui.ACTION_TEXT[a.action]), ("target", str(a.target)), ("cursor_before", str(a.cursor_before)),
                                       ("modeled_action_us", f"{a.modeled_action_us:,} µs"), ("status_after", ui.STATUS_TEXT[a.status_after])):
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
        self.assertEqual(w.difference_heading.text(), "이 사례의 기록상 차이 (개선 방식 − 기존 방식)")
        self.assertIn("음수는 개선 방식의 기록값이 기존 방식보다 작다는 뜻입니다.", w.difference_note.text())
        self.assertNotIn("Δ", w.difference_heading.text() + w.difference_label.text())
        text = " ".join(label.text() for label in (w.difference_heading, w.difference_label, w.difference_note)).lower()
        for word in ("improvement", "speedup", "saved", "faster", "better", "superior", "efficiency gain", "optimal",
                     "향상", "우월", "더 빠름", "절약", "효율", "더 빠른 알고리즘", "우수한 방식", "최적화 성공"):
            self.assertNotIn(word, text)
        self.assertEqual(w.limitation_label.text(), "저장된 연구 사례를 보여주는 화면이며, 통계적 성능 검증 결과는 아닙니다.")
        self.assertIn(self.admitted[0].identity.board_fingerprint, w.identity_label.toolTip())
        self.assertEqual(w.current_pair.difference.direction, "K-P0 minus CONTROL")
        self.assertIn(w.current_pair.difference.direction, w.difference_heading.toolTip())
        self.assertEqual(w.difference_heading.toolTip(), w.difference_heading.accessibleDescription())

    def test_korean_title_panel_headings_navigation_and_detail_captions(self):
        self.assertEqual(self.window.windowTitle(), "지뢰찾기 알고리즘 비교 — 기존 방식 vs 개선 방식 (Program K)")
        self.assertNotIn("K-P0", self.window.windowTitle())
        self.assertEqual(self.panels[0].title(), "기존 방식")
        self.assertEqual(self.panels[1].title(), "개선 방식 (Program K)")
        for panel in self.panels:
            self.assertEqual([button.text() for button in (panel.first_button, panel.previous_button,
                             panel.play_button, panel.next_button, panel.last_button)], ["처음", "이전", "재생", "다음", "끝"])
            self.assertEqual(panel.route_checkbox.text(), "완료 이동 경로 표시")
            self.assertEqual(panel.mode_combo.accessibleName(), panel.variant + " 재생 기준")
            self.assertEqual(panel.interval_spin.accessibleName(), panel.variant + " 입력 간격")
            self.assertEqual(panel.speed_combo.accessibleName(), panel.variant + " Model C 배속")
            labels = {label.text() for label in panel.findChildren(QLabel)}
            for caption in ("재생 기준", "입력 간격", "배속", "순번:", "동작:", "대상 좌표:", "이전 커서:",
                            "동작 Model C 시간:", "누적 Model C 시간:", "실행 후 상태:"):
                self.assertIn(caption, labels)
            self.start(panel)
            self.assertEqual(panel.play_button.text(), "일시정지")
            panel.on_play_pause()
            self.assertEqual(panel.play_button.text(), "재생")
        self.assertEqual(self.panels[1].knowledge_checkbox.text(), "확정한 지뢰 표시 (초록 ◇)")
        self.assertIn("동작 분류:", {label.text() for label in self.panels[1].findChildren(QLabel)})

    def test_action_status_localization_does_not_change_archived_values(self):
        statuses = {"PLAYING": "진행 중", "WON": "승리", "LOST": "패배"}
        actions = {"OPEN": "열기 (OPEN)", "FLAG": "깃발 (FLAG)", "CHORD": "동시 열기 (CHORD)"}
        for panel in self.panels:
            presentation = panel.player.presentation
            recorded = (presentation.actions, presentation.frames)
            for index, frame in enumerate(presentation.frames):
                panel.seek(index)
                self.assertIs(panel.player.current_frame, frame)
                self.assertIn(f"상태: {statuses[frame.status]}", panel.status_label.text())
                if index:
                    action = presentation.actions[index - 1]
                    self.assertIs(panel.player.current_action, action)
                    self.assertEqual(panel.detail_labels["action"].text(), actions[action.action])
                    self.assertEqual(panel.detail_labels["status_after"].text(), statuses[action.status_after])
            self.assertEqual((presentation.actions, presentation.frames), recorded)
            self.assertTrue(all(a.action in actions and a.status_after in statuses for a in presentation.actions))

    def test_translated_modes_use_original_item_data_and_independent_controller_tokens(self):
        self.assertEqual((ui.INDEX_MODE, ui.MODEL_C_MODE), ("Index", "Model C Time"))
        for index, panel in enumerate(self.panels):
            before = self.snapshot(self.panels[1 - index])
            self.assertEqual([(panel.mode_combo.itemText(i), panel.mode_combo.itemData(i)) for i in range(2)],
                             [("입력 순서", "Index"), ("Model C 시간", "Model C Time")])
            for caption, mode in (("Model C 시간", "Model C Time"), ("입력 순서", "Index")):
                panel.mode_combo.setCurrentText(caption)
                self.assertEqual(panel.playback.mode, mode)
                self.assertEqual(panel.mode_combo.currentData(), mode)
                panel.refresh()
                self.assertEqual(panel.mode_combo.currentText(), caption)
                self.assertEqual(self.snapshot(self.panels[1 - index]), before)

    def test_provenance_is_concise_but_full_identity_remains_accessible(self):
        w, identity = self.window, self.admitted[0].identity
        self.assertEqual(w.identity_label.text(), "같은 지뢰 배치에서 기존 방식과 개선 방식의 기록을 비교합니다. 좌우 기록은 각각 독립적으로 재생할 수 있습니다.")
        for widget in (w.identity_label, w.pair_selector):
            for field in ("연구 기록 상세 정보", f"내부 기록 ID: {identity.case_id}", "승인 E1", identity.run_id,
                          identity.board_fingerprint, str(identity.first_click),
                          f"반복 {identity.repetition}", f"CONTROL 기록 {identity.control_schedule_index}",
                          f"K-P0 기록 {identity.kp0_schedule_index}"):
                self.assertIn(field, widget.toolTip())
                self.assertIn(field, widget.accessibleDescription())
        visible_text = " ".join(label.text() for label in w.findChildren(QLabel)) + w.pair_selector.currentText()
        self.assertNotIn(identity.run_id, visible_text)
        self.assertNotIn(identity.board_fingerprint, visible_text)
        self.assertIn("같은 지뢰 배치", w.identity_label.text())
        self.assertTrue(w.identity_label.isVisible())
        self.assertTrue(w.limitation_label.isVisible())

    def test_main_surface_uses_audience_names_without_losing_variant_identity(self):
        w = self.window
        self.assertEqual((self.panels[0].variant, self.panels[1].variant), ("CONTROL", "K-P0"))
        for panel in self.panels:
            self.assertIn(panel.variant, panel.toolTip())
            self.assertEqual(panel.toolTip(), panel.accessibleDescription())
            self.assertIn("동시 열기(CHORD)", panel.summary_label.toolTip())
            self.assertIn("깃발 수가 숫자와 같을 때", panel.summary_label.toolTip())
        self.assertIn("Stage-3 V1", self.panels[0].toolTip())
        self.assertIn("통계적 효과 입증을 뜻하지 않습니다", self.panels[1].toolTip())
        prominent = " ".join([w.windowTitle(), w.pair_selector.currentText(),
                             *(panel.title() for panel in self.panels),
                             *(label.text() for label in (w.identity_label, w.limitation_label,
                               w.difference_heading, w.difference_label, w.difference_note, w.legend_label)),
                             *(panel.summary_label.text() for panel in self.panels)])
        for token in ("K-P0", "CONTROL", "E1", "Stage-3 V1", "S-LIFECYCLE", "S-REPLAN", "S-LOSS", "X-0",
                      "OPEN", "FLAG", "CHORD", "K logical known mine"):
            self.assertNotIn(token, prominent)
        for claim in ("더 빠른 알고리즘", "우수한 방식", "성능 향상", "효율 개선", "최적화 성공", "속도 향상", "절약"):
            self.assertNotIn(claim, prominent)

    def test_program_k_explanation_describes_unflagged_known_mines_without_new_layer(self):
        control, kp0 = self.panels
        self.assertIsNone(control.knowledge_checkbox)
        self.assertFalse(hasattr(control.board, "knowledge_overlay"))
        tooltip = kp0.knowledge_checkbox.toolTip()
        self.assertIn("Program K는 확정한 지뢰를 반드시 즉시 깃발로 표시하지 않고", tooltip)
        self.assertIn("필요할 때까지 논리적으로 기억할 수 있습니다", tooltip)
        self.assertIn("초록 ◇ = Program K가 지뢰로 확정했지만 아직 깃발을 놓지 않은 칸", tooltip)
        self.assertEqual(kp0.knowledge_checkbox.accessibleDescription(), tooltip)
        self.assertNotIn("P0", tooltip)
        self.assertIn("초록 ◇ = 개선 방식이 지뢰로 확정했지만 아직 깃발을 놓지 않은 칸", self.window.legend_label.text())
        self.assertIn("빨간 깃발 = 실제 깃발", self.window.legend_label.text())
        kp0.seek(2)
        self.assertEqual(kp0.board.knowledge_overlay.hidden_mines, kp0.player.current_frame.hidden_logical_mines)
        self.assertEqual(control.player.current_index, 0)

    def test_model_c_explanation_distinguishes_modeled_real_and_cpu_time(self):
        label = self.window.model_c_label
        self.assertTrue(label.isVisible())
        self.assertIn("마우스 이동·입력의 모델 시간", label.text())
        self.assertIn("마우스 이동과 입력을 모델링한 시간", label.toolTip())
        self.assertIn("실제 경과 시간이나 CPU 계산 시간이 아닙니다", label.toolTip())
        self.assertIn("마이크로초", label.toolTip())
        self.assertEqual(label.accessibleDescription(), label.toolTip())

    def test_only_one_compact_bottom_legend_with_precise_cursor_tooltip(self):
        w = self.window
        self.assertIs(w.layout().itemAt(w.layout().count() - 1).widget(), w.legend_label)
        self.assertIsNotNone(w.layout().itemAt(w.layout().count() - 2).layout())  # panels directly above
        for text in ("초록 ◇", "빨간 깃발", "파란 원", "주황 테두리", "보라 선"):
            self.assertIn(text, w.legend_label.text())
        self.assertNotIn("Model C", w.legend_label.text())
        self.assertNotIn("\n", w.legend_label.text())
        for text in ("완료한 입력의 대상 좌표만", "표시용 합성", "실제 마우스 궤적 기록이 아닙니다", "다음 입력 대상"):
            self.assertIn(text, w.legend_label.toolTip())
        self.assertEqual(w.legend_label.accessibleDescription(), w.legend_label.toolTip())

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

    def test_audience_case_labels_preserve_all_four_exact_pair_identities(self):
        expected = (("S-LIFECYCLE", "기본 예제 · 4×1 / 지뢰 1"),
                    ("S-REPLAN", "복합 동작 예제 · 6×4 / 지뢰 5"),
                    ("S-LOSS", "패배 예제 · 5×1 / 지뢰 2"),
                    ("X-0", "상급 보드 예제 · 30×16 / 지뢰 99"))
        selector = self.window.pair_selector
        for i, ((case_id, caption), pair) in enumerate(zip(expected, self.admitted)):
            self.assertEqual(selector.itemText(i), caption)
            self.assertEqual(selector.itemData(i), case_id)
            for internal_id, _ in expected:
                self.assertNotIn(internal_id, caption)
            self.window.select_pair(i)
            self.assertIs(self.window.current_pair, pair)
            self.assertIs(self.panels[0].player.presentation, pair.control)
            self.assertIs(self.panels[1].player.presentation, pair.kp0)
            for detail in (selector.itemData(i, Qt.ToolTipRole), selector.itemData(i, Qt.AccessibleDescriptionRole),
                           selector.toolTip(), selector.accessibleDescription(),
                           self.window.identity_label.toolTip(), self.window.identity_label.accessibleDescription()):
                for value in (f"내부 기록 ID: {case_id}", "승인 E1", pair.identity.run_id, pair.identity.board_fingerprint,
                              f"반복 {pair.identity.repetition}", f"최초 열기 {pair.identity.first_click}",
                              f"CONTROL 기록 {pair.identity.control_schedule_index}", f"K-P0 기록 {pair.identity.kp0_schedule_index}"):
                    self.assertIn(value, detail)
            self.assertEqual(pair.difference.direction, "K-P0 minus CONTROL")

    def test_exact_accepted_summaries_and_signed_differences(self):
        expected = ((4, 3, -1, 1, -1, -1, -71406), (15, 14, -1, 3, -3, -1, -86720),
                    (3, 2, -1, 0, -1, 0, None), (227, 180, -47, 33, -51, -29, -8400666))
        for i, (p, values) in enumerate(zip(self.admitted, expected)):
            self.window.select_pair(i)
            for panel, facts in ((self.panels[0], p.control_facts), (self.panels[1], p.kp0_facts)):
                text = panel.summary_label.text()
                for text_value in (ui.STATUS_TEXT[facts.outcome], f"입력 {facts.total_inputs}", f"열기 {facts.open_inputs}",
                                   f"깃발 {facts.flag_inputs}", f"동시 열기 {facts.chord_inputs}", f"{facts.model_c_total_us:,} µs",
                                   f"직접 깃발 {facts.explicit_physical_flags}", f"승리 시 자동 깃발 {facts.automatic_win_flags}"):
                    self.assertIn(text_value, text)
            self.assertEqual((p.control_facts.total_inputs, p.kp0_facts.total_inputs, p.difference.total_inputs,
                              p.difference.open_inputs, p.difference.flag_inputs, p.difference.chord_inputs,
                              p.difference.model_c_us), values)
            for caption, value in zip(("입력 수 차이", "열기", "깃발", "동시 열기"), values[2:6]):
                self.assertIn(f"{caption} " + (f"{value:+,}" if value else "0"), self.window.difference_label.text())
            if values[-1] is not None:
                self.assertIn(f"Model C 시간 차이: {values[-1]:+,} µs", self.window.difference_label.text())
            self.assertIn(p.identity.board_fingerprint, self.window.identity_label.toolTip())
            self.assertIn(p.identity.run_id, self.window.pair_selector.accessibleDescription())
        self.window.select_pair(2)
        self.assertIsNone(self.window.current_pair.difference.model_c_us)
        self.assertIn("Model C 시간 차이: 비교하지 않음", self.window.difference_label.text())
        self.assertNotIn("N/A", self.window.difference_label.text())
        self.assertIn("양쪽 모두 패배한 사례이므로 승리 시간 비교에는 사용하지 않습니다.", self.window.difference_note.text())
        self.assertIn("각 실행의 종료 시점 Model C 시간은 좌우에 별도로 표시합니다.", self.window.difference_note.text())
        for panel in self.panels:
            panel.on_last()
            self.assertEqual(panel.player.current_frame.status, "LOST")
            self.assertIn("상태: 패배", panel.status_label.text())
            self.assertEqual(panel.detail_labels["status_after"].text(), "패배")

    def test_expert_desktop_width_fits_and_restored_window_keeps_scroll_fallback(self):
        self.window.select_pair(3)
        self.window.resize(1920, 1000)
        self.app.processEvents()
        for panel in self.panels:
            self.assertEqual((panel.board.width(), panel.board.height()), (840, 448))
            self.assertEqual(panel.scroll_area.horizontalScrollBar().maximum(), 0)
        self.window.resize(1400, 950)
        self.app.processEvents()
        for panel in self.panels:
            self.assertGreater(panel.scroll_area.horizontalScrollBar().maximum(), 0)
            self.assertEqual(panel.board.cells[0, 0].width(), 28)

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
                    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData(MODEL_C_MODE))
                    assert panel.playback.mode == MODEL_C_MODE
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
