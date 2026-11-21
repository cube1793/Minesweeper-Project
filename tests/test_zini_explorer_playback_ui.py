"""Offscreen Qt checks of click-unit playback in the ZiNi Explorer (E-C2..E-C10)."""

import ast
from contextlib import ExitStack
import os
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, PropertyMock, patch

from tests.ui_settings import isolate_ui_settings

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
try:
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    from core_engine import Action, GameStatus, MinesweeperEngine
    from replay_model import ACTION_OPEN, ReplayBoard, ReplayData, ReplayEvent
    from replay_player import ReplayPlayer
    from ui_manager import MinesweeperUI
    from zini_explorer_ui import ZiniExplorerWindow
    from zini_metric_worker import write_result_atomic

from tests.test_zini_playback import (
    CENTER_RESULT, CENTER_SNAPSHOT, FALLBACK_RESULT, FALLBACK_SNAPSHOT,
    MULTI_RESULT, MULTI_SNAPSHOT, expected_state,
)
from tests.zini_fixtures import _expert_seed1003_snapshot
from tests.zini_v1_golden import GOLDEN
from zini_calculator import ZiniMove, ZiniResult
from zini_explorer import ZiniExplorerController
from zini_playback import ZiniPlaybackPlayer
from zini_trace import build_zini_trace

ROOT = Path(__file__).resolve().parents[1]
LOGICAL_NAMES = ("current_index", "step_count", "current_step", "revealed",
                 "flagged_mines", "cumulative_clicks", "go_to", "next", "previous")
SELECTION_TEXT_KEYS = ("premium", "best_premium", "selection", "tie_count")


def payload(token, result=CENTER_RESULT):
    return {"token": token, "clicks": result.clicks, "moves": result.moves, "error": None}


def ready_controller(snapshot=CENTER_SNAPSHOT, result=CENTER_RESULT):
    controller = ZiniExplorerController()
    controller.begin(7, snapshot, eligible=True)
    controller.receive(payload(7, result), expected_token=7)
    if controller.request_trace() is None:
        raise AssertionError(controller.error)
    return controller


def expert_controller():
    saved = GOLDEN["deterministic/expert1003"]["expected"]
    return ready_controller(_expert_seed1003_snapshot(), ZiniResult(
        saved["clicks"], tuple(ZiniMove(*move) for move in saved["moves"]),
    ))


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class PlaybackWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.windows = []
        self.addCleanup(self.close_windows)

    def close_windows(self):
        for window in self.windows:
            try:
                window.timer.stop()
                window.close()
            except RuntimeError:
                pass
        self.app.processEvents()

    def window_for(self, controller):
        window = ZiniExplorerWindow(controller)
        self.windows.append(window)
        return window

    def test_header_clicks_and_slider_equal_position_everywhere(self):
        for controller in (ready_controller(), ready_controller(MULTI_SNAPSHOT, MULTI_RESULT),
                           expert_controller()):
            window = self.window_for(controller)
            total = controller.clicks
            self.assertEqual(controller.playback_count, total)
            self.assertEqual((window.slider.minimum(), window.slider.maximum()), (0, total))
            for position in list(range(total + 1)) + [total // 2, 0]:
                with self.subTest(total=total, position=position):
                    window.slider.setValue(position)
                    self.assertEqual(controller.playback_position, position)
                    self.assertEqual(window.slider.value(), position)
                    self.assertEqual(window.clicks_label.text(), f"Clicks {position} / {total}")
            window.last_button.click()
            self.assertEqual(window.clicks_label.text(), f"Clicks {total} / {total}")

    def test_details_show_unit_kind_target_step_and_order_note(self):
        window = self.window_for(ready_controller(MULTI_SNAPSHOT, MULTI_RESULT))
        labels = window.diagnostic_labels
        self.assertEqual(labels["unit"].text(), "—")
        self.assertEqual(labels["premium_basis"].text(), "—")
        expected = ["클릭 · (1, 0) · 1 / 2", "깃발 1/2 · (0, 0) · 2 / 2",
                    "깃발 2/2 · (2, 0) · 2 / 2", "화음 · (1, 0) · 2 / 2"]
        for position, text in enumerate(expected, 1):
            window.next_button.click()
            self.assertEqual(window.controller.playback_position, position)
            self.assertEqual(labels["unit"].text(), text)
        note = window.unit_note_label.text()
        self.assertIn("좌상단(행 우선) 표시 순서", note)
        self.assertIn("실제 클릭 순서가 아닙니다", note)
        self.assertIn("논리 단계 전체 기준", note)
        self.assertIs(window.unit_note_label.parentWidget(), window.details_panel)
        fallback = self.window_for(ready_controller(FALLBACK_SNAPSHOT, FALLBACK_RESULT))
        fallback.next_button.click()
        self.assertEqual(fallback.diagnostic_labels["unit"].text(), "fallback 클릭 · (2, 0) · 1 / 2")
        center = self.window_for(ready_controller())
        center.slider.setValue(4)
        self.assertEqual(center.diagnostic_labels["unit"].text(), "화음 · (0, 1) · 3 / 4")

    def test_premium_details_are_pre_state_values_at_every_unit_of_a_move(self):
        for controller in (ready_controller(MULTI_SNAPSHOT, MULTI_RESULT), ready_controller(),
                           expert_controller()):
            window = self.window_for(controller)
            trace = controller.trace
            with ExitStack() as stack:
                for target in ("zini_trace._build_premium_context", "zini_trace._find_premium_candidates",
                               "zini_explorer.build_zini_trace"):
                    stack.enter_context(patch(target, side_effect=AssertionError(target)))
                seen = {}
                for position in range(1, controller.playback_count + 1):
                    window.slider.setValue(position)
                    unit = controller.playback_unit
                    step = trace.steps[unit.step_index]
                    labels = window.diagnostic_labels
                    values = tuple(labels[key].text() for key in SELECTION_TEXT_KEYS)
                    self.assertEqual(labels["premium"].text(),
                                     "—" if step.move.premium is None else str(step.move.premium))
                    self.assertEqual(labels["best_premium"].text(), str(step.best_premium))
                    self.assertEqual(labels["tie_count"].text(), str(step.tie_count))
                    self.assertEqual(labels["premium_basis"].text(),
                                     f"논리 단계 {step.step_index + 1}의 적용 전 상태 기준")
                    self.assertEqual(labels["action"].text(), step.move.action)
                    self.assertEqual(labels["coordinate"].text(), f"({step.move.x}, {step.move.y})")
                    self.assertEqual(seen.setdefault(step.step_index, values), values)
            self.assertEqual(sorted(seen), list(range(len(trace.steps))))

    def test_selection_border_follows_unit_target(self):
        for controller in (ready_controller(MULTI_SNAPSHOT, MULTI_RESULT), ready_controller(),
                           ready_controller(FALLBACK_SNAPSHOT, FALLBACK_RESULT)):
            window = self.window_for(controller)
            trace = controller.trace
            for position in range(controller.playback_count + 1):
                window.slider.setValue(position)
                unit = controller.playback_unit
                selected = {coord for coord, cell in window.cells.items() if cell.selected}
                if unit is None:
                    self.assertEqual(selected, set())
                    continue
                step = trace.steps[unit.step_index]
                if unit.kind == "flag":
                    self.assertEqual(selected, {step.newly_flagged[unit.flag_number - 1]})
                    self.assertEqual(window.cells[unit.target].state, "flagged")
                    self.assertIn("border: 2px solid #2463c5", window.cells[unit.target].styleSheet())
                else:
                    self.assertEqual(selected, {(step.move.x, step.move.y)})

    def test_window_source_uses_only_playback_api(self):
        module = ast.parse((ROOT / "zini_explorer_ui.py").read_text(encoding="utf-8"))
        used = set()
        for node in ast.walk(module):
            if isinstance(node, ast.Attribute):
                base = node.value
                if ((isinstance(base, ast.Attribute) and base.attr == "controller")
                        or (isinstance(base, ast.Name) and base.id == "controller")):
                    used.add(node.attr)
        self.assertFalse(used & set(LOGICAL_NAMES), used & set(LOGICAL_NAMES))
        self.assertLessEqual({"playback_position", "playback_count", "playback_unit", "playback_step",
                              "seek_playback", "next_playback", "previous_playback"}, used)
        # Runtime: every logical member raises, yet the window fully works.
        controller = ready_controller(MULTI_SNAPSHOT, MULTI_RESULT)
        with ExitStack() as stack:
            for name in LOGICAL_NAMES:
                original = getattr(ZiniExplorerController, name)
                if isinstance(original, property):
                    stack.enter_context(patch.object(ZiniExplorerController, name, new_callable=PropertyMock,
                                                     side_effect=AssertionError(name)))
                else:
                    stack.enter_context(patch.object(ZiniExplorerController, name,
                                                     side_effect=AssertionError(name)))
            window = self.window_for(controller)
            for action in (window.next_button.click, window.next_button.click, window.previous_button.click,
                           window.last_button.click, window.first_button.click,
                           lambda: window.slider.setValue(3)):
                action()
            window.interval_spin.setValue(20)
            window.play_button.click()
            window._advance_autoplay()
            window.timer.stop()
            window.answer_display_checkbox.click()
            window.details_button.click()
        self.assertEqual(controller.playback_position, 4)

    def test_all_navigation_moves_by_playback_unit(self):
        controller = ready_controller(MULTI_SNAPSHOT, MULTI_RESULT)
        window = self.window_for(controller)
        trace = controller.trace
        steps = []
        for action, expected in ((window.next_button.click, 1), (window.next_button.click, 2),
                                 (window.next_button.click, 3), (window.previous_button.click, 2),
                                 (window.last_button.click, 4), (window.previous_button.click, 3),
                                 (window.first_button.click, 0), (lambda: window.slider.setValue(2), 2)):
            action()
            steps.append(controller.playback_position)
            revealed, flags = expected_state(trace, expected)
            self.assertEqual(controller.playback_position, expected)
            self.assertEqual(window.slider.value(), expected)
            self.assertEqual({c for c, cell in window.cells.items() if cell.state == "flagged"}, flags)
            self.assertEqual({c for c, cell in window.cells.items() if cell.state == "revealed"}, revealed)
        self.assertEqual(steps, [1, 2, 3, 2, 4, 3, 0, 2])
        window.first_button.click()
        observed = []
        window.interval_spin.setValue(20)
        window.timer.timeout.connect(lambda: observed.append(controller.playback_position))
        window.play_button.click()
        deadline = time.monotonic() + 3
        while window.timer.isActive() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertEqual(observed, [1, 2, 3, 4])
        self.assertEqual(window.clicks_label.text(), "Clicks 4 / 4")

    def test_default_interval_500_range_and_unit_wording(self):
        window = self.window_for(ready_controller())
        spin = window.interval_spin
        self.assertEqual((spin.value(), window.timer.interval()), (500, 500))
        self.assertEqual((spin.minimum(), spin.maximum()), (20, 5000))
        self.assertEqual(spin.suffix(), " ms/클릭")
        self.assertEqual(spin.toolTip(), "재생 단위(클릭 1회)당 자동 재생 간격")
        self.assertEqual(window.previous_button.toolTip(), "이전 재생 단위")
        self.assertEqual(window.next_button.toolTip(), "다음 재생 단위")
        self.assertEqual(window.slider.accessibleName(), "재생 위치 (누적 Clicks)")
        texts = [spin.suffix(), spin.toolTip(), window.slider.accessibleName()]
        texts += [button.toolTip() for button in (window.first_button, window.previous_button,
                                                  window.play_button, window.next_button, window.last_button)]
        from PyQt5.QtWidgets import QLabel
        texts += [label.text() for label in window.findChildren(QLabel)
                  if label.text() in ("재생 간격", "Index 간격")]
        self.assertIn("재생 간격", texts)
        for text in texts:
            self.assertNotIn("논리 단계", text)
            self.assertNotIn("Index", text)
            self.assertNotIn("ms/step", text)
        # A new window starts at the default again; the timer uses the spin value.
        spin.setValue(900)
        window.play_button.click()
        self.assertEqual(window.timer.interval(), 900)
        window.timer.stop()
        self.assertEqual(self.window_for(ready_controller()).interval_spin.value(), 500)

    def test_autoplay_stops_at_end_and_on_navigation(self):
        controller = ready_controller(MULTI_SNAPSHOT, MULTI_RESULT)
        window = self.window_for(controller)
        window.slider.setValue(2)  # Mid-move start.
        window.interval_spin.setValue(20)
        window.play_button.click()
        deadline = time.monotonic() + 3
        while window.timer.isActive() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(window.timer.isActive())
        self.assertEqual(controller.playback_position, 4)
        self.assertFalse(window.play_button.isEnabled())
        window._advance_autoplay()
        self.assertEqual(controller.playback_position, 4)
        window.interval_spin.setValue(5000)
        for name, action in (("first", window.first_button.click), ("previous", window.previous_button.click),
                             ("next", window.next_button.click), ("last", window.last_button.click),
                             ("slider", lambda: window.slider.setValue(1))):
            with self.subTest(action=name):
                window.slider.setValue(2)
                window.play_button.click()
                self.assertTrue(window.timer.isActive())
                action()
                self.assertFalse(window.timer.isActive())
                before = controller.playback_position
                window._advance_autoplay()
                self.assertEqual(controller.playback_position, before)


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class PlaybackMainUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.engine = MinesweeperEngine(3, 3, 1)
        self.settings = isolate_ui_settings(self)
        self.ui = MinesweeperUI(self.engine)
        self.addCleanup(self.close_ui)
        warning = patch("ui_manager.QMessageBox.warning")
        warning.start()
        self.addCleanup(warning.stop)

    def close_ui(self):
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def launch(self):
        process = Mock()
        process.poll.return_value = None
        with patch("zini_metric_job.subprocess.Popen", return_value=process):
            self.ui._ensure_zini_metric_job()

    def finish(self):
        write_result_atomic(self.ui._zini_result_path, payload(self.ui._zini_job_token))
        self.ui._poll_zini_metric_job()

    def prepare_lost_live(self):
        self.ui._reset_zini_metric_job()
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.engine.step(1, 1, Action.OPEN)
        self.assertEqual(self.engine.status, GameStatus.LOST)
        self.launch()
        self.finish()

    def test_open_builds_trace_and_units_once_and_reopen_keeps_position(self):
        self.prepare_lost_live()
        controller = self.ui._zini_explorer
        with patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as build, \
                patch("zini_explorer.ZiniPlaybackPlayer", wraps=ZiniPlaybackPlayer) as player:
            self.ui.zini_explorer_button.click()
            window = self.ui._zini_explorer_window
            window.next_button.click()
            window.next_button.click()
            window.interval_spin.setValue(5000)
            window.play_button.click()
            window._advance_autoplay()
            self.assertEqual(controller.playback_position, 3)
            window.slider.setValue(2)
            window.close()
            self.assertIsNone(self.ui._zini_explorer_window)
            self.assertEqual(controller.playback_position, 2)
            self.ui.zini_explorer_button.click()
            reopened = self.ui._zini_explorer_window
            self.assertIsNot(reopened, window)
            self.assertEqual(reopened.slider.value(), 2)
            self.assertEqual(reopened.clicks_label.text(), "Clicks 2 / 5")
            reopened.last_button.click()
            reopened.first_button.click()
            reopened.close()
            self.ui.zini_explorer_button.click()
            self.assertEqual(self.ui._zini_explorer_window.slider.value(), 0)
            build.assert_called_once()
            player.assert_called_once()
            self.assertIs(player.call_args.args[0], controller.trace)

    def test_counters_path_never_builds_trace_or_units(self):
        with patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as build, \
                patch("zini_explorer.ZiniPlaybackPlayer", wraps=ZiniPlaybackPlayer) as player:
            self.prepare_lost_live()
            self.ui._counter_metric_values()
            self.ui._update_statistics_panel(self.engine.get_stats())
            self.assertEqual(self.ui._current_zini_clicks(), 5)
            self.assertTrue(self.ui.zini_explorer_button.isEnabled())
            build.assert_not_called()
            player.assert_not_called()
            self.assertIsNone(self.ui._zini_explorer.playback_position)

    def test_board_mode_change_and_invalidate_drop_position(self):
        def enter_replay():
            player = ReplayPlayer(ReplayData(
                ReplayBoard(3, 3, 1, {(1, 1)}),
                (ReplayEvent(1.0, 0, 0, ACTION_OPEN), ReplayEvent(2.0, 1, 1, ACTION_OPEN)),
            ))
            process = Mock()
            process.poll.return_value = None
            with patch("zini_metric_job.subprocess.Popen", return_value=process):
                self.ui._enter_replay_mode(player)

        for name, action in (("reset", self.ui.on_reset),
                             ("board", lambda: self.ui._rebuild_game(4, 3, 1)),
                             ("replay", enter_replay),
                             ("invalidate", self.ui._zini_explorer.invalidate)):
            with self.subTest(action=name):
                if self.ui._replay_mode:
                    self.ui._exit_replay_mode()
                self.prepare_lost_live()
                self.ui.on_open_zini_explorer()
                window = self.ui._zini_explorer_window
                window.slider.setValue(3)
                self.assertEqual(self.ui._zini_explorer.playback_position, 3)
                action()
                self.assertIsNone(self.ui._zini_explorer.playback_position)
                self.assertIsNone(self.ui._zini_explorer.playback_unit)
                if name != "invalidate":
                    self.assertFalse(window.isVisible())
                    self.assertIsNone(self.ui._zini_explorer_window)
        if self.ui._replay_mode:
            self.ui._exit_replay_mode()


if __name__ == "__main__":
    unittest.main()
