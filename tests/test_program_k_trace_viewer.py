"""D2/D3 portable presentation tests plus accepted-E1 read-only coverage.

Portable models are hand-written D1 dataclasses, NOT accepted research evidence.
No fixtures execute a solver/Engine or regenerate the ignored E1 archive.
"""

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
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()

from experiments import program_k_trace_adapter as d1
from experiments import program_k_trace_demo as demo

try:
    from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt5.QtTest import QSignalSpy, QTest
    from PyQt5.QtWidgets import QApplication, QLabel, QStyle, QStyleOptionSlider
    from experiments import program_k_trace_viewer as ui
except ImportError:
    ui = None


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = demo.DEFAULT_ARTIFACT_DIRECTORY
PROFILE = demo.DEFAULT_PROFILE
HAS_EVIDENCE = all((ARTIFACT / name).is_file() for name in ("qualification.json", "COMPLETE.json"))


class FakeClock:
    def __init__(self):
        self.now_ns = 0

    def __call__(self):
        return self.now_ns

    def advance(self, nanoseconds):
        self.now_ns += nanoseconds


def portable_presentation():
    """Literal four-input public stream, intentionally not an E1 artifact."""
    digest = "0" * 64
    provenance = d1.KTraceProvenance(
        run_id="PORTABLE_TEST_ONLY", qualification_sha256=digest, qualification_size=0,
        complete_sha256=digest, qualification_source_digest=digest, operational_source_digest=digest,
        plan_source_digest=digest, base_source_digest=digest, execution_source_digest=digest,
        audit_source_digest=digest, spec_sha256=digest, protocol_sha256=digest, profile_sha256=digest,
        table_sha256=digest, model_id="TEST_ONLY", source_files=(), historical_runtime=(), scope="TEST_ONLY")
    case = d1.KCaseIdentity(
        case_id="TEST_ONLY", schedule_index=0, repetition=1, variant="K-P0", width=4, height=1,
        num_mines=1, first_click=(0, 0), board_fingerprint=digest, source_type="MANUAL_TEST_ONLY",
        benchmark_set_id=None, board_generator_version=None, seed_scheme=None, game_index=None,
        seed=None, fixture_id="TEST_ONLY", provenance="Hand-written public frames, not research evidence.",
        permitted_claims=("Test-only presentation behavior.",))
    h, f = d1.HIDDEN, d1.FLAGGED
    observations = (((h, h, h, h),), ((1, h, h, h),), ((1, f, h, h),),
                    ((1, f, 1, h),), ((1, f, 1, 0),))
    moves = (("OPEN", (0, 0)), ("FLAG", (1, 0)), ("OPEN", (2, 0)), ("CHORD", (2, 0)))
    durations = (100000, 250000, 175000, 125000)
    categories = ("POLICY_INITIAL_OPEN", "SETUP_CHORD", "DIRECT_SAFE_OPEN", "DIRECT_CHORD")
    ref = d1.EvidenceReference(digest, 0, "MANUAL_TEST_ONLY")
    empty, mine = frozenset(), frozenset({(1, 0)})
    frames = [d1.KTraceFrame(0, observations[0], "PLAYING", (0, 0), 0, empty, empty, empty)]
    actions, cumulative = [], 0
    for i, ((action, target), duration, category) in enumerate(zip(moves, durations, categories)):
        cumulative += duration
        status = "WON" if i == 3 else "PLAYING"
        known = mine if i >= 1 else empty
        actions.append(d1.KActionView(
            i, action, target, frames[-1].cursor, duration, cumulative, status, category,
            frames[-1].logical_mines, known, int(action != "FLAG"), int(action == "FLAG"), (), ref, ref, None))
        frames.append(d1.KTraceFrame(i + 1, observations[i + 1], status, target, cumulative,
                                    known, known, empty))
    return d1.KTracePresentation(provenance, case, tuple(actions), tuple(frames),
                                 d1.TerminalAnswerReference(mine, digest, ref))


def portable_knowledge_presentation(*, materialize=True):
    """Literal HIDDEN -> known/HIDDEN -> optional explicit FLAG -> WIN stream."""
    original = portable_presentation()
    hidden, flag = d1.HIDDEN, d1.FLAGGED
    empty, mine = frozenset(), frozenset({(1, 0)})
    # A second OPEN carries the already-acquired logical mine into frame 2.
    inputs = [("OPEN", (0, 0), ((1, hidden, hidden, hidden),), empty, empty, empty, 100000),
              ("OPEN", (2, 0), ((1, hidden, 1, hidden),), mine, empty, empty, 250000)]
    if materialize:
        inputs.append(("FLAG", (1, 0), ((1, flag, 1, hidden),), mine, mine, empty, 175000))
    inputs.append(("OPEN", (3, 0), ((1, flag, 1, 0),), mine,
                   mine if materialize else empty, empty if materialize else mine, 125000))
    frames, actions, cumulative = [original.frames[0]], [], 0
    for i, (action, target, observation, known, explicit, automatic, duration) in enumerate(inputs):
        cumulative += duration
        status = "WON" if i == len(inputs) - 1 else "PLAYING"
        category = "POLICY_INITIAL_OPEN" if i == 0 else "SETUP_CHORD" if action == "FLAG" else "DIRECT_SAFE_OPEN"
        actions.append(replace(original.actions[0], input_index=i, action=action, target=target,
                               cursor_before=frames[-1].cursor, modeled_action_us=duration,
                               cumulative_modeled_us=cumulative, status_after=status, category=category,
                               M_before=frames[-1].logical_mines, preinput_M=known,
                               safe_cells_opened_delta=int(action == "OPEN"), explicit_flag_delta=int(action == "FLAG")))
        frames.append(d1.KTraceFrame(i + 1, observation, status, target, cumulative, known, explicit, automatic))
    return replace(original, actions=tuple(actions), frames=tuple(frames))


class DemoAdmissionTests(unittest.TestCase):
    def test_demo_loads_fixed_four_selections_once(self):
        views = (portable_presentation(),)
        with patch.object(demo, "load_accepted_e1_traces", return_value=views) as load:
            self.assertIs(demo.load_demo_presentations(Path("archive"), profile_path=Path("profile")), views)
        load.assert_called_once_with(Path("archive"), schedule_indices=(8, 14, 20, 26), profile_path=Path("profile"))

    def test_missing_corrupt_archive_stops_before_qt_startup(self):
        with patch.object(demo, "load_demo_presentations", side_effect=d1.KTraceAdapterError("bad digest")), \
                patch.object(demo, "configure_qt_plugin_path") as qt, \
                redirect_stderr(io.StringIO()) as errors, redirect_stdout(io.StringIO()):
            self.assertEqual(demo.main([]), 1)
        qt.assert_not_called()
        self.assertIn("bad digest", errors.getvalue())

    def test_demo_help_does_not_load_evidence(self):
        with patch.object(demo, "load_demo_presentations") as load, redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit) as exit_info:
            demo.main(["--help"])
        self.assertEqual(exit_info.exception.code, 0)
        load.assert_not_called()

    def test_viewer_owns_no_loader_parser_answers_or_knowledge_inference(self):
        tree = ast.parse((ROOT / "experiments/program_k_trace_viewer.py").read_text(encoding="utf-8"))
        imported = set()
        attributes = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
            elif isinstance(node, ast.Attribute):
                attributes.add(node.attr)
        self.assertLessEqual(imported, {"fractions", "time", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets",
                                       "experiments.program_k_trace_adapter", "stage3_modeled_playback",
                                       "visualization_reference_overlays"})
        self.assertFalse(attributes & {"preinput_M", "M_before",
                                       "acquisitions", "answer_reference", "loads", "read_bytes", "open"})
        self.assertLessEqual({"logical_mines", "hidden_logical_mines", "explicit_flags", "automatic_flags"}, attributes)


@unittest.skipIf(ui is None, "PyQt5 unavailable")
class PortablePlayerTests(unittest.TestCase):
    def setUp(self):
        self.presentation = portable_presentation()
        self.clock = FakeClock()
        self.player = ui.KTracePlayer(self.presentation)
        self.playback = ui.KTracePlayback(self.player, clock=self.clock)

    def test_accepts_only_immutable_d1_models(self):
        invalid = (None, {}, SimpleNamespace(**vars(self.player)),
                   replace(self.presentation, actions=list(self.presentation.actions)),
                   replace(self.presentation, frames=list(self.presentation.frames)))
        for value in invalid:
            with self.subTest(value=type(value)), self.assertRaises(TypeError):
                ui.KTracePlayer(value)
        self.assertIs(self.player.presentation, self.presentation)

    def test_initial_frame_and_no_fabricated_action(self):
        self.assertIs(self.player.current_frame, self.presentation.frames[0])
        self.assertIsNone(self.player.current_action)
        self.assertEqual(self.player.completed_route, ())
        self.assertEqual(self.player.current_frame.status, "PLAYING")
        self.assertTrue(all(v == d1.HIDDEN for row in self.player.current_frame.observation for v in row))

    def test_navigation_uses_exact_d1_frames_actions_and_prefixes(self):
        for index in (0, 1, 4, 2, 3, 0, 4):
            self.assertIs(self.player.go_to(index), self.presentation.frames[index])
            self.assertIs(self.player.current_frame, self.presentation.frame(index))
            self.assertIs(self.player.current_action, self.presentation.actions[index - 1] if index else None)
            self.assertEqual(self.player.completed_route, self.presentation.completed_route(index))
        self.assertFalse(self.player.next())
        self.assertTrue(self.player.previous())
        self.assertEqual(self.player.current_index, 3)
        self.player.go_to(0)
        self.assertFalse(self.player.previous())
        for index in (True, -1, 5, 0.5):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.player.go_to(index)
        self.assertEqual(self.player.current_index, 0)

    def test_index_commit_waits_for_exact_interval_even_on_early_timer_tick(self):
        self.playback.play()
        self.clock.advance(199999999)
        self.playback.update()
        self.assertEqual(self.player.current_index, 0)
        self.assertEqual(self.player.current_frame.cumulative_modeled_us, 0)
        self.assertEqual(self.playback.progress, Fraction(199999999, 200000000))
        self.clock.advance(1)
        self.playback.update()
        self.assertEqual(self.player.current_index, 1)
        self.assertEqual(self.playback.progress, 0)
        self.assertEqual(self.player.current_frame.cumulative_modeled_us, 100000)

    def test_model_c_commit_waits_for_exact_recorded_duration(self):
        self.playback.set_mode(ui.MODEL_C_MODE)
        self.playback.play()
        self.clock.advance(99999999)
        self.playback.update()
        self.assertEqual(self.player.current_index, 0)
        self.clock.advance(1)
        self.playback.update()
        self.assertEqual(self.player.current_index, 1)
        self.assertEqual(self.playback.pending_duration_us, 250000)

    def test_both_modes_pause_resume_exclude_paused_wall_time(self):
        for mode in (ui.INDEX_MODE, ui.MODEL_C_MODE):
            with self.subTest(mode=mode):
                self.playback.cancel_partial()
                self.player.go_to(0)
                self.playback.set_mode(mode)
                duration_ns = self.playback.pending_duration_us * 1000
                self.playback.play()
                self.clock.advance(duration_ns // 2)
                self.playback.pause()
                self.assertEqual(self.playback.progress, Fraction(1, 2))
                self.assertEqual(self.player.current_index, 0)
                self.clock.advance(10000000000)
                self.playback.update()
                self.assertEqual(self.playback.progress, Fraction(1, 2))
                self.playback.play()
                self.clock.advance(duration_ns // 2 - 1)
                self.playback.update()
                self.assertEqual(self.player.current_index, 0)
                self.clock.advance(1)
                self.playback.update()
                self.assertEqual(self.player.current_index, 1)

    def test_late_ticks_catch_up_and_end_without_wrapping(self):
        for mode in (ui.INDEX_MODE, ui.MODEL_C_MODE):
            with self.subTest(mode=mode):
                self.playback.cancel_partial()
                self.player.go_to(0)
                self.playback.set_mode(mode)
                self.playback.play()
                self.clock.advance(10000000000)
                self.playback.update()
                self.assertEqual(self.player.current_index, 4)
                self.assertFalse(self.playback.running)
                self.assertEqual(self.playback.progress, 0)
                self.assertIs(self.player.current_frame, self.presentation.frames[-1])
                self.playback.play()
                self.assertFalse(self.playback.running)

    def test_model_speed_and_index_interval_have_separate_authority(self):
        self.playback.set_speed(8)
        self.assertEqual(self.playback.speed, 1)
        self.assertEqual(self.playback.model_speed, 8)
        self.playback.play()
        self.clock.advance(100000000)
        self.playback.update()
        self.assertEqual(self.playback.progress, Fraction(1, 2))
        self.playback.set_index_interval(1000)
        self.assertEqual(self.playback.progress, Fraction(1, 2))
        self.clock.advance(499999999)
        self.playback.update()
        self.assertEqual(self.player.current_index, 0)
        self.clock.advance(1)
        self.playback.update()
        self.assertEqual(self.player.current_index, 1)
        self.playback.set_mode(ui.MODEL_C_MODE)
        self.assertFalse(self.playback.running)
        self.assertEqual(self.playback.speed, 8)
        self.assertEqual(self.playback.pending_duration_us, self.presentation.actions[1].modeled_action_us)

    def test_speed_change_consumes_old_rate_and_preserves_exact_costs(self):
        self.playback.set_mode(ui.MODEL_C_MODE)
        self.playback.play()
        self.clock.advance(50000000)
        self.playback.set_speed(2)
        self.assertEqual(self.playback.progress, Fraction(1, 2))
        self.clock.advance(24999999)
        self.playback.update()
        self.assertEqual(self.player.current_index, 0)
        self.clock.advance(1)
        self.playback.update()
        self.assertEqual(self.player.current_frame.cumulative_modeled_us, 100000)

    def test_cancel_then_manual_seek_discards_partial_and_unsampled_time(self):
        self.playback.play()
        self.clock.advance(300000000)  # Unsampled; manual seek must not commit it.
        self.playback.cancel_partial()
        self.player.go_to(2)
        self.assertEqual(self.playback.progress, 0)
        self.assertEqual(self.player.current_frame.cumulative_modeled_us, 350000)
        self.playback.play()
        self.clock.advance(199999999)
        self.playback.update()
        self.assertEqual(self.player.current_index, 2)

    def test_invalid_rates_modes_and_clock_failure_fail_without_early_commit(self):
        for value in (True, 19, 5001, 20.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.playback.set_index_interval(value)
        with self.assertRaises(ValueError):
            self.playback.set_mode("Engine")
        with self.assertRaises(ValueError):
            self.playback.set_speed(3)
        self.playback.play()
        self.clock.advance(100000000)
        self.playback.update()
        self.clock.now_ns = 1
        with self.assertRaises(ValueError):
            self.playback.update()
        self.assertFalse(self.playback.running)
        self.assertEqual(self.playback.progress, Fraction(1, 2))
        self.assertEqual(self.player.current_index, 0)


@unittest.skipIf(ui is None, "PyQt5 unavailable")
class _WindowCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.windows = []
        self.clock = FakeClock()
        self.presentation = portable_presentation()
        self.window = self.make_window((self.presentation,))

    def make_window(self, presentations):
        window = ui.KTraceViewerWindow(presentations, clock=self.clock)
        self.windows.append(window)
        return window

    def tearDown(self):
        for window in self.windows:
            if not window._closed:
                window.close()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def assert_frame(self, window, index):
        p = window.player.presentation
        frame = p.frame(index)
        self.assertIs(window.player.current_frame, frame)
        self.assertIs(window.board.observation, frame.observation)
        self.assertEqual(window.slider.value(), index)
        self.assertEqual(window.board.overlay.targets, p.completed_route(index))
        self.assertEqual(window.board.knowledge_overlay.hidden_mines, frame.hidden_logical_mines)
        self.assertEqual(window.board.overlay.current_cursor, frame.cursor)
        self.assertEqual(window.detail_labels["cumulative_modeled_us"].text(), f"{frame.cumulative_modeled_us:,} µs")
        for y, row in enumerate(frame.observation):
            for x, value in enumerate(row):
                self.assertEqual(window.board.cells[x, y].public_state, value)
        self.assertIn(frame.status, window.status_label.text())
        self.assertIn(f"K logical known mines: {len(frame.logical_mines)} ·", window.knowledge_label.text())
        self.assertIn(f"Hidden logical known mines: {len(frame.hidden_logical_mines)} ·", window.knowledge_label.text())
        self.assertIn(f"Explicit physical flags: {len(frame.explicit_flags)} ·", window.knowledge_label.text())
        self.assertIn(f"Automatic WIN flags: {len(frame.automatic_flags)}", window.knowledge_label.text())


class PortableWindowTests(_WindowCase):
    def test_viewer_type_boundary_and_initial_ui(self):
        for value in (None, (), [], [self.presentation], (SimpleNamespace(),)):
            with self.subTest(value=type(value)), self.assertRaises(TypeError):
                ui.KTraceViewerWindow(value)
        self.assertEqual(self.window.windowTitle(), ui.TITLE)
        self.assert_frame(self.window, 0)
        self.assertIsNone(self.window.board.overlay.action_target)
        self.assertIsNone(self.window.board.overlay.movement_start)
        for name in ("ordinal", "action", "target", "cursor_before", "modeled_action_us", "status_after", "category"):
            self.assertEqual(self.window.detail_labels[name].text(), "—")
        self.assertIn("not E2 effectiveness evidence", self.window.limitation_label.text())
        self.assertIn("not production / Gate-P", self.window.limitation_label.text())
        self.assertFalse(self.window.playback.running)

    def test_navigation_buttons_and_slider_exact_seek(self):
        self.window.next_button.click()
        self.assert_frame(self.window, 1)
        self.window.last_button.click()
        self.assert_frame(self.window, 4)
        self.window.previous_button.click()
        self.assert_frame(self.window, 3)
        self.window.first_button.click()
        self.assert_frame(self.window, 0)
        for index in (2, 1, 4, 0):
            self.window.slider.setValue(index)
            self.assert_frame(self.window, index)

    def test_action_context_and_cursor_endpoints_are_exact(self):
        for index, action in enumerate(self.presentation.actions, 1):
            self.window.seek(index)
            self.assert_frame(self.window, index)
            expected = dict(ordinal=f"{index} / 4", action=action.action, target=str(action.target),
                            cursor_before=str(action.cursor_before), modeled_action_us=f"{action.modeled_action_us:,} µs",
                            status_after=action.status_after, category=action.category)
            for name, text in expected.items():
                self.assertEqual(self.window.detail_labels[name].text(), text)
            self.assertEqual(self.window.board.overlay.cursor_center, ui._MotionOverlay.cell_center(action.target))
            self.assertEqual(self.window.board.overlay.action_target, action.target)

    def test_partial_motion_leaves_board_context_route_and_model_c_committed(self):
        for mode in (ui.INDEX_MODE, ui.MODEL_C_MODE):
            with self.subTest(mode=mode):
                self.window.seek(1)
                self.window.mode_combo.setCurrentText(mode)
                self.window.on_play_pause()
                self.clock.advance(self.window.playback.pending_duration_us * 500)
                self.window._advance_playback()
                self.assert_frame(self.window, 1)
                self.assertEqual(self.window.detail_labels["action"].text(), "OPEN")
                self.assertEqual(self.window.board.overlay.action_target, (1, 0))
                self.assertEqual(self.window.board.overlay.cursor_center, QPointF(28, 14))
                self.assertEqual(self.window.board.overlay.targets, ((0, 0),))
                self.window.on_play_pause()
                self.assertFalse(self.window.timer.isActive())
                paused = self.window.board.overlay.cursor_center
                self.clock.advance(1000000000)
                self.window.refresh()
                self.assertEqual(self.window.board.overlay.cursor_center, paused)

    def test_direct_track_seek_and_handle_press_cancel_partial(self):
        self.window.show()
        self.app.processEvents()
        self.window.seek(1)
        self.window.on_play_pause()
        self.clock.advance(100000000)
        self.window._advance_playback()
        slider = self.window.slider
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
        QTest.mousePress(slider, Qt.LeftButton, pos=handle.center())
        QTest.mouseRelease(slider, Qt.LeftButton, pos=handle.center())
        self.assertFalse(self.window.playback.running)
        self.assertEqual(self.window.playback.progress, 0)
        self.assertEqual(self.window.board.overlay.cursor_center, ui._MotionOverlay.cell_center((0, 0)))
        QTest.mouseClick(slider, Qt.LeftButton, pos=QPoint(slider.width() - 1, slider.height() // 2))
        self.assert_frame(self.window, 4)

    def test_manual_same_frame_seek_aligns_cursor_and_cancels_time(self):
        self.window.seek(1)
        self.window.on_play_pause()
        self.clock.advance(100000000)
        self.window._advance_playback()
        self.window.seek(1)
        self.assert_frame(self.window, 1)
        self.assertFalse(self.window.playback.running)
        self.assertEqual(self.window.playback.progress, 0)
        self.assertEqual(self.window.board.overlay.cursor_center, QPointF(14, 14))

    def test_case_selection_resets_frame_and_never_loads_again(self):
        second = replace(self.presentation, case=replace(self.presentation.case, case_id="SECOND_TEST"))
        window = self.make_window((self.presentation, second))
        window.on_play_pause()
        self.clock.advance(100000000)
        window._advance_playback()
        with patch.object(d1, "load_accepted_e1_traces", side_effect=AssertionError("UI must not load")), \
                patch.object(Path, "read_bytes", side_effect=AssertionError("navigation must not read files")):
            window.case_selector.setCurrentIndex(1)
            self.assertIs(window.player.presentation, second)
            self.assert_frame(window, 0)
            self.assertFalse(window.timer.isActive())
            window.on_last()
            window.on_first()
            window.case_selector.setCurrentIndex(0)
            self.assert_frame(window, 0)

    def test_glyphs_include_loss_feedback_and_auto_flagged_public_state(self):
        cell = self.window.board.cells[0, 0]
        for value, text, description in (
            (d1.HIDDEN, "", "HIDDEN"), (d1.FLAGGED, "⚑", "FLAGGED"), (d1.EXPLODED, "✹", "EXPLODED"),
            (d1.MINE, "✹", "MINE"), (d1.FALSE_FLAG, "×", "FALSE_FLAG"), (0, "", "Revealed 0"),
            *((number, str(number), f"Revealed {number}") for number in range(1, 9)),
        ):
            with self.subTest(value=value):
                cell.render_state(value)
                self.assertEqual(cell.public_state, value)
                self.assertEqual(cell.text(), text)
                self.assertIn(description, cell.toolTip())
        with self.assertRaises(ValueError):
            cell.render_state(9)

    def test_logical_overlay_preserves_public_glyphs_and_never_consults_terminal_answer(self):
        frames = list(self.presentation.frames)
        frames[1] = replace(frames[1], logical_mines=frozenset({(1, 0)}))
        # A poison answer value proves the UI does not even consult that field.
        window = self.make_window((replace(self.presentation, frames=tuple(frames), answer_reference=object()),))
        window.seek(1)
        cell = window.board.cells[1, 0]
        self.assertEqual(cell.public_state, d1.HIDDEN)
        self.assertEqual(cell.text(), "")
        self.assertIn("K logical known mine", cell.toolTip())
        self.assertEqual(window.board.knowledge_overlay.hidden_mines, frozenset({(1, 0)}))
        self.assertFalse(hasattr(window, "answer_checkbox"))
        self.assertFalse(hasattr(window, "answer_overlay"))

    def test_board_click_cannot_execute_or_navigate(self):
        self.window.show()
        self.app.processEvents()
        frame = self.window.player.current_frame
        for button in (Qt.LeftButton, Qt.RightButton, Qt.MiddleButton):
            QTest.mouseClick(self.window.board.cells[1, 0], button)
        self.assertIs(self.window.player.current_frame, frame)
        self.assertFalse(self.window.playback.running)

    def test_route_uses_shared_painter_with_completed_prefix_only(self):
        self.window.seek(3)
        overlay = self.window.board.overlay
        with patch.object(ui, "paint_action_target_route") as paint:
            overlay.grab()
        self.assertTrue(paint.called)
        self.assertEqual(paint.call_args.args[1], [QPointF(14, 14), QPointF(42, 14), QPointF(70, 14)])
        self.window.route_checkbox.setChecked(False)
        self.assertFalse(overlay.show_route)
        self.assertEqual(overlay.targets, self.presentation.completed_route(3))

    def test_cursor_geometry_is_render_only_straight_smoothstep(self):
        point = ui._MotionOverlay.interpolated_center((0, 0), (2, 1), Fraction(1, 4))
        self.assertEqual(point, QPointF(22.75, 18.375))
        self.assertEqual(ui._MotionOverlay.interpolated_center((1, 0), (1, 0), Fraction(1, 2)), QPointF(42, 14))
        self.assertIn("not recorded mouse movement", self.window.legend_label.text())
        self.assertIn("not wall clock", self.window.playback_label.toolTip())

    def test_clock_failure_stops_and_keeps_last_sampled_frame(self):
        self.window.on_play_pause()
        self.clock.advance(100000000)
        self.window._advance_playback()
        self.clock.now_ns = 0
        self.window._advance_playback()
        self.assertFalse(self.window.timer.isActive())
        self.assertFalse(self.window.playback.running)
        self.assertEqual(self.window.playback.progress, Fraction(1, 2))
        self.assertIn("Playback stopped", self.window.error_label.text())
        self.assert_frame(self.window, 0)

    def test_close_stops_only_owned_timer_without_sampling_or_child_jobs(self):
        self.window.show()
        spy = QSignalSpy(self.window.closed)
        self.window.on_play_pause()
        self.clock.advance(1000000000)  # Do not commit this unsampled time at close.
        player, playback, timer = self.window.player, self.window.playback, self.window.timer
        self.window.close()
        self.assertTrue(self.window._closed)
        self.assertEqual(len(spy), 1)
        self.assertFalse(timer.isActive())
        self.assertFalse(playback.running)
        self.assertEqual(player.current_index, 0)
        self.assertFalse(any(hasattr(self.window, name) for name in ("job", "worker", "process")))
        self.window._advance_playback()
        self.window.on_play_pause()
        self.assertEqual(player.current_index, 0)


class LogicalKnowledgeTests(_WindowCase):
    def setUp(self):
        self.windows = []
        self.clock = FakeClock()
        self.presentation = portable_knowledge_presentation()
        self.window = self.make_window((self.presentation,))

    def test_d3_initial_frame_has_no_markers_and_default_is_on(self):
        self.assertTrue(self.window.knowledge_checkbox.isChecked())
        self.assertEqual(self.window.knowledge_checkbox.text(), "Show K logical known mines")
        self.assertFalse(self.window.board.knowledge_overlay.hidden_mines)
        self.assert_frame(self.window, 0)
        for cell in self.window.board.cells.values():
            self.assertNotIn("K logical known mine", cell.toolTip())

    def test_d3_direct_seek_restores_only_the_selected_frame_knowledge(self):
        for index in (1, 2, 4, 0, 3, 2, 1):
            self.window.slider.setValue(index)
            self.assert_frame(self.window, index)
            for coordinate, cell in self.window.board.cells.items():
                self.assertEqual("K logical known mine" in cell.toolTip(),
                                 coordinate in self.presentation.frame(index).logical_mines)

    def test_d3_previous_next_first_last_restore_knowledge(self):
        for handler, index in ((self.window.on_next, 1), (self.window.on_next, 2),
                               (self.window.on_next, 3), (self.window.on_previous, 2),
                               (self.window.on_last, 4), (self.window.on_first, 0)):
            handler()
            self.assert_frame(self.window, index)

    def test_d3_case_change_clears_future_mine_knowledge(self):
        second = replace(self.presentation, case=replace(self.presentation.case, case_id="SECOND_K_TEST"))
        window = self.make_window((self.presentation, second))
        window.seek(2)
        self.assertTrue(window.board.knowledge_overlay.hidden_mines)
        window.case_selector.setCurrentIndex(1)
        self.assert_frame(window, 0)
        self.assertFalse(window.board.knowledge_overlay.hidden_mines)
        self.assertNotIn("K logical known mine", window.board.cells[1, 0].toolTip())

    def check_partial_boundary(self, mode):
        self.window.seek(1)
        self.window.mode_combo.setCurrentText(mode)
        self.window.on_play_pause()
        duration_ns = self.window.playback.pending_duration_us * 1000
        self.clock.advance(duration_ns - 1)
        self.window._advance_playback()
        self.assert_frame(self.window, 1)
        self.assertFalse(self.window.board.knowledge_overlay.hidden_mines)
        self.assertNotIn("K logical known mine", self.window.board.cells[1, 0].toolTip())
        self.clock.advance(1)
        self.window._advance_playback()
        self.assert_frame(self.window, 2)
        self.assertEqual(self.window.board.knowledge_overlay.hidden_mines, frozenset({(1, 0)}))
        self.assertEqual(self.window.board.cells[1, 0].public_state, d1.HIDDEN)

    def test_d3_index_partial_motion_does_not_acquire_until_exact_commit(self):
        self.check_partial_boundary(ui.INDEX_MODE)

    def test_d3_model_c_partial_motion_does_not_acquire_until_exact_commit(self):
        self.check_partial_boundary(ui.MODEL_C_MODE)

    def test_d3_pause_resume_preserves_the_committed_logical_layer_in_both_modes(self):
        for mode in (ui.INDEX_MODE, ui.MODEL_C_MODE):
            with self.subTest(mode=mode):
                self.window.seek(1)
                self.window.mode_combo.setCurrentText(mode)
                self.window.on_play_pause()
                duration_ns = self.window.playback.pending_duration_us * 1000
                self.clock.advance(duration_ns // 2)
                self.window.on_play_pause()
                self.assertEqual(self.window.playback.progress, Fraction(1, 2))
                self.assert_frame(self.window, 1)
                self.clock.advance(10000000000)
                self.window.refresh()
                self.assertFalse(self.window.board.knowledge_overlay.hidden_mines)
                self.window.on_play_pause()
                self.clock.advance(duration_ns // 2 - 1)
                self.window._advance_playback()
                self.assert_frame(self.window, 1)
                self.clock.advance(1)
                self.window._advance_playback()
                self.assert_frame(self.window, 2)

    def test_d3_manual_seek_during_partial_motion_aligns_knowledge_and_cursor(self):
        self.window.seek(2)
        self.window.on_play_pause()
        self.clock.advance(100000000)
        self.window._advance_playback()
        self.assert_frame(self.window, 2)
        self.assertIn((1, 0), self.window.board.knowledge_overlay.hidden_mines)
        self.window.seek(1)
        self.assert_frame(self.window, 1)
        self.assertFalse(self.window.playback.running)
        self.assertFalse(self.window.board.knowledge_overlay.hidden_mines)
        self.assertEqual(self.window.board.overlay.cursor_center, QPointF(14, 14))
        self.window.seek(3)
        self.assert_frame(self.window, 3)
        self.assertFalse(self.window.board.knowledge_overlay.hidden_mines)
        self.assertIn("K logical known mine", self.window.board.cells[1, 0].toolTip())

    def test_d3_toggle_preserves_playback_clock_route_cursor_costs_and_evidence(self):
        for mode in (ui.INDEX_MODE, ui.MODEL_C_MODE):
            with self.subTest(mode=mode):
                self.window.seek(2)
                self.window.mode_combo.setCurrentText(mode)
                self.window.on_play_pause()
                self.clock.advance(self.window.playback.pending_duration_us * 500)
                self.window._advance_playback()
                frame = self.window.player.current_frame
                overlay = self.window.board.overlay
                route, center = overlay.targets, QPointF(overlay.cursor_center)
                progress = self.window.playback.progress
                target = overlay.action_target
                cost = self.window.detail_labels["cumulative_modeled_us"].text()
                self.clock.advance(1000000000)  # Toggling must not consume unsampled time.
                with patch.object(self.window.playback, "update", side_effect=AssertionError("toggle sampled clock")), \
                        patch.object(d1, "load_accepted_e1_traces", side_effect=AssertionError("toggle loaded evidence")):
                    for visible in (False, True, False, True):
                        self.window.knowledge_checkbox.setChecked(visible)
                        self.assertEqual(self.window.board.knowledge_overlay.isHidden(), not visible)
                        self.assertTrue(self.window.playback.running)
                        self.assertTrue(self.window.timer.isActive())
                        self.assertIs(self.window.player.current_frame, frame)
                        self.assertIs(overlay.targets, route)
                        self.assertEqual(overlay.cursor_center, center)
                        self.assertEqual(overlay.action_target, target)
                        self.assertEqual(self.window.playback.progress, progress)
                        self.assertEqual(self.window.detail_labels["cumulative_modeled_us"].text(), cost)
                self.window.seek(2)

    def test_d3_public_observations_text_and_styles_are_unchanged_by_marker_visibility(self):
        self.window.seek(2)
        frame = self.window.player.current_frame
        before = {coordinate: (cell.public_state, cell.text(), cell.styleSheet())
                  for coordinate, cell in self.window.board.cells.items()}
        for visible in (False, True, False):
            self.window.knowledge_checkbox.setChecked(visible)
            self.assertIs(self.window.board.observation, frame.observation)
            self.assertEqual(before, {coordinate: (cell.public_state, cell.text(), cell.styleSheet())
                                      for coordinate, cell in self.window.board.cells.items()})

    def test_d3_physical_flag_stays_primary_with_secondary_logical_provenance(self):
        self.window.seek(2)
        cell = self.window.board.cells[1, 0]
        self.assertEqual(cell.public_state, d1.HIDDEN)
        self.assertEqual(cell.text(), "")
        self.assertIn("K logical known mine", cell.toolTip())
        self.window.on_next()
        self.assertEqual(cell.public_state, d1.FLAGGED)
        self.assertEqual(cell.text(), "⚑")
        self.assertNotIn((1, 0), self.window.board.knowledge_overlay.hidden_mines)
        self.assertIn("physical FLAG", cell.toolTip())
        self.assertIn("explicit physical FLAG", cell.toolTip())
        self.assertIn("K logical known mine", cell.toolTip())
        self.assertEqual(cell.accessibleName(), cell.toolTip())

    def test_d3_automatic_win_flag_is_not_labeled_explicit(self):
        window = self.make_window((portable_knowledge_presentation(materialize=False),))
        window.on_last()
        cell = window.board.cells[1, 0]
        self.assertEqual(cell.text(), "⚑")
        self.assertIn("physical FLAG", cell.toolTip())
        self.assertIn("automatic WIN flag", cell.toolTip())
        self.assertNotIn("explicit", cell.toolTip())
        self.assertIn("K logical known mine", cell.toolTip())
        self.assertIn("Explicit physical flags: 0", window.knowledge_label.text())
        self.assertIn("Automatic WIN flags: 1", window.knowledge_label.text())
        # A public terminal FLAG alone is never promoted to logical knowledge.
        no_knowledge = replace(window.player.current_frame, logical_mines=frozenset())
        window.board.render_knowledge(no_knowledge)
        self.assertNotIn("K logical known mine", cell.toolTip())
        self.assertIn("automatic WIN flag", cell.toolTip())

    def test_d3_marker_is_transparent_separate_and_below_route_target_cursor(self):
        self.window.show()
        self.window.seek(2)
        self.app.processEvents()
        knowledge, motion = self.window.board.knowledge_overlay, self.window.board.overlay
        self.assertTrue(knowledge.testAttribute(Qt.WA_TransparentForMouseEvents))
        self.assertTrue(knowledge.testAttribute(Qt.WA_NoSystemBackground))
        self.assertEqual(knowledge.focusPolicy(), Qt.NoFocus)
        self.assertEqual(knowledge.geometry(), self.window.board.rect())
        children = self.window.board.children()
        self.assertLess(children.index(self.window.board.cells[1, 0]), children.index(knowledge))
        self.assertLess(children.index(knowledge), children.index(motion))
        for visible in (False, True):
            self.window.knowledge_checkbox.setChecked(visible)
            self.assertLess(self.window.board.children().index(knowledge), self.window.board.children().index(motion))
        # Check actual rendered pixels, rather than inferring visibility from sets.
        self.window.route_checkbox.setChecked(False)
        def green_pixels(image, column):
            return sum(image.pixelColor(x, y).name() == "#17663f"
                       for x in range(column * 28, (column + 1) * 28) for y in range(28))
        image = self.window.board.grab().toImage()
        self.assertGreater(green_pixels(image, 1), 0)
        self.assertEqual(green_pixels(image, 3), 0)  # Ordinary HIDDEN.
        self.window.knowledge_checkbox.setChecked(False)
        self.assertEqual(green_pixels(self.window.board.grab().toImage(), 1), 0)
        self.window.knowledge_checkbox.setChecked(True)
        self.window.seek(3)  # Physical FLAG is never overpainted by the diamond.
        self.assertEqual(green_pixels(self.window.board.grab().toImage(), 1), 0)

    def test_d3_factual_counts_and_tooltips_remain_available_when_markers_hidden(self):
        self.window.seek(2)
        summary = self.window.knowledge_label.text()
        self.window.knowledge_checkbox.setChecked(False)
        self.assertEqual(self.window.knowledge_label.text(), summary)
        self.assertIn("K logical known mine", self.window.board.cells[1, 0].toolTip())
        self.assertIn("still physically HIDDEN", self.window.board.cells[1, 0].accessibleName())

    def test_d3_hidden_layer_keeps_current_data_through_seek_then_reenable(self):
        self.window.knowledge_checkbox.setChecked(False)
        self.window.seek(2)
        self.assert_frame(self.window, 2)
        self.assertTrue(self.window.board.knowledge_overlay.isHidden())
        self.window.knowledge_checkbox.setChecked(True)
        self.assertEqual(self.window.board.knowledge_overlay.hidden_mines, frozenset({(1, 0)}))
        self.window.knowledge_checkbox.setChecked(False)
        self.window.seek(0)
        self.window.knowledge_checkbox.setChecked(True)
        self.assertFalse(self.window.board.knowledge_overlay.hidden_mines)


@unittest.skipUnless(HAS_EVIDENCE and ui is not None, "Accepted E1 archive or PyQt5 absent; never regenerate evidence.")
class AcceptedCaseTests(_WindowCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.accepted = demo.load_demo_presentations()

    def setUp(self):
        self.windows = []
        self.clock = FakeClock()
        self.window = self.make_window(self.accepted)

    def test_four_cases_all_frames_actions_routes_and_costs_match_d1(self):
        expected = ((8, "S-LIFECYCLE", "WON", 3, 432614), (14, "S-REPLAN", "WON", 14, 2382644),
                    (20, "S-LOSS", "LOST", 2, 306609), (26, "X-0", "WON", 180, 31586418))
        for position, presentation in enumerate(self.accepted):
            with self.subTest(case=presentation.case.case_id):
                self.assertEqual((presentation.case.schedule_index, presentation.case.case_id,
                                  presentation.terminal_status, len(presentation.actions), presentation.total_modeled_us),
                                 expected[position])
                self.window.case_selector.setCurrentIndex(position)
                self.assert_frame(self.window, 0)
                for index in range(len(presentation.frames)):
                    self.window.seek(index)
                    self.assert_frame(self.window, index)
                    if index:
                        action = presentation.actions[index - 1]
                        self.assertEqual(self.window.detail_labels["action"].text(), action.action)
                        self.assertEqual(self.window.detail_labels["modeled_action_us"].text(),
                                         f"{action.modeled_action_us:,} µs")

    def test_lifecycle_both_modes_complete_with_exact_public_cells(self):
        for mode in (ui.INDEX_MODE, ui.MODEL_C_MODE):
            self.window.seek(0)
            self.window.mode_combo.setCurrentText(mode)
            self.window.on_play_pause()
            self.clock.advance(10000000000)
            self.window._advance_playback()
            self.assert_frame(self.window, 3)
            self.assertFalse(self.window.timer.isActive())
            self.assertEqual(self.window.board.cells[1, 0].public_state, d1.FLAGGED)
        self.window.seek(2)
        self.assertEqual(self.window.board.cells[1, 0].public_state, d1.HIDDEN)
        self.assertEqual(self.window.board.cells[1, 0].text(), "")

    def test_d3_lifecycle_marks_only_frame_two_then_preserves_auto_flag(self):
        for index in (0, 1):
            self.window.seek(index)
            self.assertFalse(self.window.board.knowledge_overlay.hidden_mines)
            self.assertNotIn("K logical known mine", self.window.board.cells[1, 0].toolTip())
        self.window.seek(2)
        self.assert_frame(self.window, 2)
        cell = self.window.board.cells[1, 0]
        self.assertEqual(self.window.board.knowledge_overlay.hidden_mines, frozenset({(1, 0)}))
        self.assertEqual(cell.public_state, d1.HIDDEN)
        self.assertEqual(cell.text(), "")
        self.assertIn("K logical known mine", cell.toolTip())
        self.window.on_last()
        self.assertFalse(self.window.board.knowledge_overlay.hidden_mines)
        self.assertEqual(cell.text(), "⚑")
        self.assertIn("automatic WIN flag", cell.toolTip())
        self.assertNotIn("explicit", cell.toolTip())
        self.assertIn("K logical known mine", cell.toolTip())
        self.assertIn("Explicit physical flags: 0", self.window.knowledge_label.text())
        self.assertIn("Automatic WIN flags: 1", self.window.knowledge_label.text())

    def test_d3_replan_materializes_a_hidden_known_mine_without_losing_provenance(self):
        self.window.select_case(1)
        p = self.window.player.presentation
        transitions = [a for a in p.actions if a.action == "FLAG" and a.target in p.frame(a.input_index).hidden_logical_mines]
        self.assertTrue(transitions)
        for action in transitions:
            self.window.seek(action.input_index)
            self.assertIn(action.target, self.window.board.knowledge_overlay.hidden_mines)
            cell = self.window.board.cells[action.target]
            self.assertEqual(cell.public_state, d1.HIDDEN)
            self.window.on_next()
            self.assertNotIn(action.target, self.window.board.knowledge_overlay.hidden_mines)
            self.assertEqual(cell.public_state, d1.FLAGGED)
            self.assertEqual(cell.text(), "⚑")
            self.assertIn("K logical known mine", cell.toolTip())
            self.assertIn("explicit physical FLAG", cell.toolTip())
            self.assertNotIn("automatic", cell.toolTip())

    def test_d3_loss_disclosure_does_not_invent_logical_knowledge(self):
        self.window.select_case(2)
        self.window.on_last()
        frame = self.window.player.current_frame
        self.assertEqual(frame.logical_mines, frozenset({(1, 0)}))
        self.assertFalse(self.window.board.knowledge_overlay.hidden_mines)
        known, exploded = self.window.board.cells[1, 0], self.window.board.cells[2, 0]
        self.assertEqual(known.public_state, d1.MINE)
        self.assertIn("K logical known mine", known.toolTip())
        self.assertEqual(exploded.public_state, d1.EXPLODED)
        self.assertNotIn("K logical known mine", exploded.toolTip())
        self.assertIn("terminal public disclosure", exploded.toolTip())
        self.assertIn("K logical known mines: 1", self.window.knowledge_label.text())
        self.window.on_first()
        self.assertNotIn("K logical known mine", self.window.board.cells[1, 0].toolTip())

    def test_d3_lifecycle_real_durations_do_not_publish_next_m_early(self):
        for mode in (ui.INDEX_MODE, ui.MODEL_C_MODE):
            with self.subTest(mode=mode):
                self.window.seek(1)
                self.window.mode_combo.setCurrentText(mode)
                self.window.on_play_pause()
                duration_ns = self.window.playback.pending_duration_us * 1000
                self.clock.advance(duration_ns - 1)
                self.window._advance_playback()
                self.assertFalse(self.window.board.knowledge_overlay.hidden_mines)
                self.assert_frame(self.window, 1)
                self.clock.advance(1)
                self.window._advance_playback()
                self.assert_frame(self.window, 2)
                self.assertEqual(self.window.board.knowledge_overlay.hidden_mines, frozenset({(1, 0)}))

    def test_d3_all_accepted_seek_frames_restore_logical_and_flag_provenance(self):
        for case_index, p in enumerate(self.accepted):
            self.window.select_case(case_index)
            for index in range(len(p.frames) - 1, -1, -1):
                self.window.seek(index)
                self.assert_frame(self.window, index)
                frame = p.frame(index)
                for coordinate, cell in self.window.board.cells.items():
                    self.assertEqual("K logical known mine" in cell.toolTip(), coordinate in frame.logical_mines)
                    self.assertEqual("explicit physical FLAG" in cell.toolTip(), coordinate in frame.explicit_flags)
                    self.assertEqual("automatic WIN flag" in cell.toolTip(), coordinate in frame.automatic_flags)

    def test_d3_expert_overlay_has_hidden_markers_and_distinct_flag_states(self):
        self.window.select_case(3)
        self.window.seek(90)
        frame = self.window.player.current_frame
        self.assertTrue(frame.hidden_logical_mines)
        self.assertTrue(frame.explicit_flags)
        self.assertEqual(len(self.window.board.cells), 480)
        self.assertEqual(self.window.board.knowledge_overlay.hidden_mines, frame.hidden_logical_mines)
        self.assertFalse(frame.hidden_logical_mines & frame.explicit_flags)
        self.window.knowledge_checkbox.setChecked(False)
        self.assert_frame(self.window, 90)
        self.window.knowledge_checkbox.setChecked(True)
        self.assert_frame(self.window, 90)

    def test_replan_real_sequence_and_loss_feedback(self):
        self.window.case_selector.setCurrentIndex(1)
        seen = []
        for index in range(1, 15):
            self.window.seek(index)
            seen.append(self.window.detail_labels["action"].text())
        self.assertEqual({a: seen.count(a) for a in set(seen)}, {"OPEN": 8, "FLAG": 2, "CHORD": 4})
        self.window.case_selector.setCurrentIndex(2)
        self.window.on_last()
        self.assertIn("LOST", self.window.status_label.text())
        states = {cell.public_state for cell in self.window.board.cells.values()}
        self.assertIn(d1.EXPLODED, states)
        self.assertIn(d1.MINE, states)
        self.assertIn(d1.HIDDEN, states)

    def test_expert_identity_and_direct_seek(self):
        self.window.case_selector.setCurrentIndex(3)
        self.assertEqual(len(self.window.board.cells), 480)
        self.assertIn("30×16 / 99 mines", self.window.case_selector.currentText())
        self.assertIn(d1.ACCEPTED_RUN_ID, self.window.identity_label.text())
        self.assertIn(d1.QUALIFICATION_SHA256, self.window.identity_label.toolTip())
        for index in (179, 0, 90, 180):
            self.window.slider.setValue(index)
            self.assert_frame(self.window, index)

    def test_fresh_process_denies_gameplay_imports_writes_and_owned_processes(self):
        script = textwrap.dedent('''
            import importlib.abc
            import os
            from pathlib import Path
            import sys
            root = Path.cwd()
            allowed = {'qt_bootstrap', 'stage3_modeled_playback', 'visualization_reference_overlays'}
            local = {p.stem for p in root.glob('*.py')} - allowed
            research = {'experiments.program_k_trace_adapter', 'experiments.program_k_trace_viewer',
                        'experiments.program_k_trace_demo'}
            class NoGameplay(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.split('.')[0] in local or (fullname.startswith('experiments.') and fullname not in research):
                        raise AssertionError('Forbidden import: ' + fullname)
            sys.meta_path.insert(0, NoGameplay())
            def guard(event, args):
                if event == 'open':
                    mode, flags = args[1:3]
                    assert not (isinstance(mode, str) and any(c in mode for c in 'wax+'))
                    assert not (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
                assert not event.startswith(('subprocess.', 'socket.'))
                assert event not in ('os.system', 'os.remove', 'os.rename', 'os.mkdir', 'os.fork', 'os.posix_spawn')
            sys.addaudithook(guard)
            from qt_bootstrap import configure_qt_plugin_path
            configure_qt_plugin_path()
            from PyQt5.QtCore import QEvent
            from PyQt5.QtWidgets import QApplication
            from experiments.program_k_trace_demo import load_demo_presentations
            from experiments.program_k_trace_viewer import KTraceViewerWindow, MODEL_C_MODE
            views = load_demo_presentations()
            app = QApplication([])
            window = KTraceViewerWindow(views)
            window.show()
            for index in range(4):
                window.select_case(index)
                window.seek(min(2, window.player.step_count))
                window.knowledge_checkbox.setChecked(False)
                window.knowledge_checkbox.setChecked(True)
                window.on_last()
                window.on_first()
            window.mode_combo.setCurrentText(MODEL_C_MODE)
            window.on_play_pause()
            app.processEvents()
            window.on_play_pause()
            window.close()
            app.sendPostedEvents(None, QEvent.DeferredDelete)
            app.processEvents()
            assert not any(m in sys.modules for m in local)
            print('D2 import/write/process boundary PASS')
        ''')
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("boundary PASS", result.stdout)

    def test_artifact_and_profile_bytes_remain_pinned(self):
        for path, digest in ((ARTIFACT / "qualification.json", d1.QUALIFICATION_SHA256),
                             (ARTIFACT / "COMPLETE.json", d1.COMPLETE_SHA256),
                             (PROFILE, d1.PROFILE_SHA256)):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
