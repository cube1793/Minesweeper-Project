"""F-S1..F-S4: the multi-algorithm result window and the Korean window text (offscreen Qt)."""

from contextlib import ExitStack
import os
import re
import unittest
from unittest.mock import patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
try:
    from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import (
        QAbstractButton, QAbstractSpinBox, QApplication, QComboBox, QGroupBox, QLabel, QStyle,
        QStyleOptionSlider, QTabWidget, QTableWidget, QWidget,
    )
except ImportError:
    QApplication = None
else:
    import same_board_comparison_launcher as launcher
    from same_board_comparison_ui import SameBoardComparisonWindow, _IndexInterval, _IndexSlider
    from same_board_runs_ui import COLUMNS, HUMAN, SameBoardRunsWindow
    from tests.test_same_board_algorithm_ui import FakeQueue, preset_context

from core_engine import CellState
from same_board_algorithms import ALGORITHMS, LABELS, TIME_DEPENDENCE_NOTE, execute_algorithm, not_run, validate_run
from same_board_runner import run_same_board_comparison
from same_board_statistics import STAT_LABELS, algorithm_statistics, human_statistics
from same_board_timed_playback import (
    INDEX_INTERVAL_DEFAULT_MS, INDEX_INTERVAL_MAX_MS, INDEX_INTERVAL_MIN_MS,
)
from tests.test_same_board_algorithms import WIN_BOARD
from tests.test_same_board_runner import human_context
from visualization_reference_overlays import derive_answer_clues

# F-S4 allowlist (amendment 01, section 4): abbreviations, proper names and units.
ALLOWED_WORDS = {
    "BV", "IOE", "CPS", "Efficiency", "Ops", "Thrp", "Corr", "ZiNi", "ZNE", "ZNT",
    "Stage", "Stage4", "Simple", "V1", "K", "K-P0", "K-LC0", "K-LC1", "K_D23", "S", "M", "R",
    "Model", "C", "Human", "Replay", "indexed", "ms", "s", "ns", "x",
}
WORD = re.compile(r"[A-Za-z][A-Za-z0-9_\-]*")


def english_outside_allowlist(text):
    bad = []
    for word in WORD.findall(text):
        if word in ALLOWED_WORDS or re.fullmatch(r"[A-Z0-9_]+", word):
            continue  # Allowed name, or an upper-case ID/code (FIXED_BOARD, WON, HIDDEN, ...).
        if re.fullmatch(r"[0-9a-f]{8,}", word):
            continue  # Hexadecimal layout fingerprint.
        bad.append(word)
    return bad


def visible_texts(widget):
    """Every user-visible text of a window: titles, labels, buttons, tabs, headers, tooltips."""
    texts = [widget.windowTitle(), widget.toolTip()]
    for child in widget.findChildren(QWidget):
        texts.append(child.toolTip())
        if isinstance(child, QLabel):
            texts.append(child.text())
        elif isinstance(child, QAbstractButton):
            texts.append(child.text())
        elif isinstance(child, QGroupBox):
            texts.append(child.title())
        elif isinstance(child, QTabWidget):
            texts += [child.tabText(i) for i in range(child.count())]
        elif isinstance(child, QComboBox):
            texts += [child.itemText(i) for i in range(child.count())]
        elif isinstance(child, QTableWidget):
            for column in range(child.columnCount()):
                header = child.horizontalHeaderItem(column)
                texts.append(header.text() if header else "")
                for row in range(child.rowCount()):
                    item = child.item(row, column)
                    texts.append(item.text() if item else "")
        if isinstance(child, QAbstractSpinBox):
            texts += [child.specialValueText(), child.suffix(), child.prefix()]
    return [text for text in texts if text]


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class SameBoardRunsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.context = preset_context()
        cls.runs = {key: validate_run(WIN_BOARD, execute_algorithm(
            key, WIN_BOARD, r_target="120" if key == "S4_R" else None)) for key in ALGORITHMS}

    def setUp(self):
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            try:
                window.close()
            except RuntimeError:
                pass
        self.app.processEvents()

    def viewer(self, runs=None, shown="K_D23"):
        window = SameBoardRunsWindow(self.context, runs if runs is not None else {"K_D23": self.runs["K_D23"]})
        self.windows.append(window)
        if shown is not None:
            window.shown_selector.setCurrentIndex(window.shown_selector.findData(shown))
        return window

    # --- F-S1 -------------------------------------------------------------------

    def test_track_click_seeks_directly_and_handle_drag_still_works(self):
        window = self.viewer()
        window.show()
        self.app.processEvents()
        slider = window.slider
        self.assertIsInstance(slider, _IndexSlider)
        count = window._player().count
        self.assertGreater(count, slider.pageStep())
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
        x = slider.width() * 4 // 5
        span = slider.width() - handle.width()
        expected = QStyle.sliderValueFromPosition(0, count, x - handle.width() // 2, span, False)
        window.on_play_pause()
        QTest.mouseClick(slider, Qt.LeftButton, pos=QPoint(x, slider.height() // 2))
        self.assertEqual(window._index(), expected)  # Directly, not one page step.
        self.assertNotEqual(window._index(), slider.pageStep())
        self.assertEqual((slider.value(), window.players["K_D23"].index), (expected, expected))
        self.assertFalse(window.autoplay_timer.isActive())
        slider.initStyleOption(option)
        handle = slider.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, slider)
        QTest.mousePress(slider, Qt.LeftButton, pos=handle.center())
        self.assertTrue(slider.isSliderDown())
        target = QPoint(slider.width() // 4, handle.center().y())
        self.app.sendEvent(slider, QMouseEvent(QEvent.MouseMove, QPointF(target),
                                               Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QTest.mouseRelease(slider, Qt.LeftButton, pos=target)
        self.assertFalse(slider.isSliderDown())
        self.assertLess(window._index(), count // 2)
        self.assertEqual(window.index_label.text(), f"행동 {window._index()} / {count}")

    # --- F-S2 -------------------------------------------------------------------

    def test_autoplay_advances_one_action_per_interval_and_stops_at_end(self):
        window = self.viewer()
        count = window._player().count
        self.assertEqual(window.play_button.text(), "재생")
        window.on_play_pause()
        self.assertTrue(window.autoplay_timer.isActive())
        self.assertEqual(window.autoplay_timer.interval(), INDEX_INTERVAL_DEFAULT_MS)
        self.assertEqual(window.play_button.text(), "일시정지")
        for expected in range(1, count + 1):
            window.autoplay_timer.timeout.emit()
            self.assertEqual(window._index(), expected)
            self.assertEqual(window.slider.value(), expected)
        self.assertFalse(window.autoplay_timer.isActive())
        self.assertEqual(window.play_button.text(), "재생")
        self.assertFalse(window.play_button.isEnabled())
        self.assertEqual(window.players["K_D23"].status(), "WON")
        # Pause keeps the position; a real QTimer advances on its own and stops at the end.
        window.first_button.click()
        window.on_play_pause()
        window.autoplay_timer.timeout.emit()
        window.on_play_pause()
        self.assertEqual((window._index(), window.autoplay_timer.isActive()), (1, False))
        window.interval_entry.setValue(INDEX_INTERVAL_MIN_MS)
        window.on_play_pause()
        for _ in range(2000):  # PyQt5 has no qWaitFor; at most 20 s.
            if not window.autoplay_timer.isActive():
                break
            QTest.qWait(10)
        self.assertFalse(window.autoplay_timer.isActive())
        self.assertEqual(window._index(), count)

    def test_autoplay_stops_on_navigation_result_change_and_close(self):
        window = self.viewer({"K_D23": self.runs["K_D23"], "K_P0": self.runs["K_P0"]})
        operations = {
            "first": window.first_button.click, "previous": window.previous_button.click,
            "next": window.next_button.click, "last": window.last_button.click,
            "slider": lambda: window.slider.setValue(window.slider.value() + 2),
            "track": lambda: window.slider.track_seek.emit(1),
            "result": lambda: window.shown_selector.setCurrentIndex(window.shown_selector.findData("K_P0")),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name):
                window.shown_selector.setCurrentIndex(window.shown_selector.findData("K_D23"))
                window._seek(3)
                window.on_play_pause()
                self.assertTrue(window.autoplay_timer.isActive())
                operation()
                self.assertFalse(window.autoplay_timer.isActive())
                self.assertEqual(window.play_button.text(), "재생")
        window.shown_selector.setCurrentIndex(window.shown_selector.findData("K_D23"))
        window._seek(0)
        window.on_play_pause()
        self.assertTrue(window.close())
        self.assertFalse(window.autoplay_timer.isActive())

    def test_interval_matches_existing_defaults_and_range(self):
        window = self.viewer()
        entry = window.interval_entry
        self.assertIsInstance(entry, _IndexInterval)
        self.assertEqual((entry.value(), entry.minimum(), entry.maximum()),
                         (INDEX_INTERVAL_DEFAULT_MS, INDEX_INTERVAL_MIN_MS, INDEX_INTERVAL_MAX_MS))
        self.assertEqual((INDEX_INTERVAL_DEFAULT_MS, INDEX_INTERVAL_MIN_MS, INDEX_INTERVAL_MAX_MS), (200, 20, 5000))
        execution = run_same_board_comparison(human_context(with_trace=True))
        existing = SameBoardComparisonWindow(execution)
        self.windows.append(existing)
        for attribute in ("value", "minimum", "maximum", "specialValueText", "suffix"):
            self.assertEqual(getattr(entry, attribute)(), getattr(existing.interval_entry, attribute)(), attribute)
        entry.setValue(INDEX_INTERVAL_MIN_MS)
        self.assertEqual(entry.text(), "최대 (20 ms)")
        window.on_play_pause()
        entry.setValue(750)
        self.assertTrue(window.autoplay_timer.isActive())  # A new interval keeps playing.
        self.assertEqual(window.autoplay_timer.interval(), 750)

    def test_hidden_answers_toggle_paints_only_hidden_cells(self):
        window = self.viewer()
        overlay = window.answer_overlay
        self.assertFalse(window.answer_checkbox.isChecked())
        self.assertFalse(overlay.isVisibleTo(window.board_container))
        self.assertEqual(overlay.answers, derive_answer_clues(9, 9, WIN_BOARD.mine_positions))
        window.answer_checkbox.setChecked(True)
        self.assertTrue(overlay.isVisibleTo(window.board_container))
        for index in (0, 5, window._player().count):
            window._seek(index)
            observation = window._player().observation()
            self.assertEqual(overlay.hidden_mask, tuple(tuple(v == CellState.HIDDEN for v in row)
                                                        for row in observation))
        window.answer_checkbox.setChecked(False)
        self.assertFalse(overlay.isVisibleTo(window.board_container))

    # --- F-S3 -------------------------------------------------------------------

    def test_summary_table_columns_and_selected_detail(self):
        runs = {"K_P0": self.runs["K_P0"], "S4_R": self.runs["S4_R"],
                "K_LC0": not_run("K_LC0", "LIMIT", "알고리즘별 한도 30 s에 도달함.")}
        window = self.viewer(runs, shown=None)
        table = window.table
        self.assertEqual([table.horizontalHeaderItem(c).text() for c in range(table.columnCount())],
                         list(COLUMNS))
        self.assertEqual(COLUMNS, ("실행", "결과", "3BV", "행동 수", "Efficiency", "IOE", "Model C 시간 (s)"))
        rows = {table.item(r, 0).text(): [table.item(r, c).text() for c in range(table.columnCount())]
                for r in range(table.rowCount())}
        stats = algorithm_statistics(WIN_BOARD, runs["K_P0"])
        self.assertEqual(rows["K-P0"][1:6], ["WON", stats["bbbv"], str(len(runs["K_P0"].moves)),
                                             stats["efficiency"], stats["ioe"]])
        self.assertEqual(rows["K-LC0"][1:], ["LIMIT", "-", "—", "-", "-", "—"])
        human = human_statistics(self.context.human_replay)
        self.assertEqual(rows["Human"], ["Human", "LOST", human["bbbv"], "1", human["efficiency"], human["ioe"], "—"])
        self.assertIn("속도 순위가 아닙니다", window.note_label.text())
        self.assertIn("선택한 결과: Human", window.detail_label.text())
        window.shown_selector.setCurrentIndex(window.shown_selector.findData("S4_R"))
        self.assertEqual(table.currentRow(), window.row_keys.index("S4_R"))
        detail = window.detail_label.text()
        for expected in ("최종 결과: WON (승리)", "설정:\n", "진입: FIXED_BOARD", "R 목표: 120%", TIME_DEPENDENCE_NOTE):
            self.assertIn(expected, detail)
        table.setCurrentCell(window.row_keys.index("K_LC0"), 0)  # Not playable, still selectable here.
        self.assertIn("최종 결과: LIMIT (시간 한도)", window.detail_label.text())
        self.assertIn("알고리즘별 한도 30 s", window.detail_label.text())
        self.assertEqual(window.shown_key(), "S4_R")

    def test_statistics_tab_lists_items_by_run(self):
        runs = {"K_P0": self.runs["K_P0"], "K_LC1": not_run("K_LC1", "CANCELLED", "실행 중 취소됨.")}
        window = self.viewer(runs, shown=None)
        self.assertEqual([window.tabs.tabText(i) for i in range(window.tabs.count())], ["요약", "보드", "통계"])
        self.assertEqual([header.text() for header in window.statistics_headers], ["Human", "K-P0", "K-LC1"])
        self.assertEqual(list(window.statistics_labels), ["결과", *(caption for _, caption in STAT_LABELS)])
        expected = (human_statistics(self.context.human_replay), algorithm_statistics(WIN_BOARD, runs["K_P0"]),
                    algorithm_statistics(WIN_BOARD, runs["K_LC1"]))
        for key, caption in STAT_LABELS:
            self.assertEqual(tuple(label.text() for label in window.statistics_labels[caption]),
                             tuple(stats[key] for stats in expected), caption)
        self.assertEqual(tuple(label.text() for label in window.statistics_labels["결과"]),
                         ("LOST", "WON", "CANCELLED"))
        self.assertEqual(window.statistics_labels["시간"][1].text(), "—")
        self.assertIn("실제 경과 시간", window.statistics_note.text())

    def test_default_size_has_no_horizontal_scroll(self):
        # All nine algorithms on the narrowest default window (9x9 board, 760 px wide).
        window = self.viewer(dict(self.runs), shown=None)
        window.show()
        self.app.processEvents()
        self.assertLessEqual(window.width(), 760)
        self.assertEqual(window.table.horizontalScrollBar().maximum(), 0)
        for column in range(window.table.columnCount()):
            for row in range(window.table.rowCount()):
                item = window.table.item(row, column)
                needed = window.table.fontMetrics().horizontalAdvance(item.text())
                self.assertLessEqual(needed, window.table.columnWidth(column), (row, column))
        window.tabs.setCurrentIndex(2)
        self.app.processEvents()
        self.assertEqual(window.statistics_scroll.horizontalScrollBar().maximum(), 0)
        for labels in window.statistics_labels.values():
            for label in labels:
                self.assertLessEqual(label.fontMetrics().horizontalAdvance(label.text()), label.width(),
                                     label.text())
        for header in window.statistics_headers:
            widest = max(header.fontMetrics().horizontalAdvance(word) for word in header.text().split())
            self.assertLessEqual(widest, header.width(), header.text())

    # --- F-S4 -------------------------------------------------------------------

    def assert_korean(self, name, texts):
        for text in texts:
            self.assertEqual(english_outside_allowlist(text), [], f"{name}: {text!r}")

    def test_four_windows_have_no_english_outside_allowlist(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(launcher, "SameBoardAlgorithmQueue", FakeQueue))
            window = launcher.SameBoardComparisonLauncherWindow(
                self.context, source_description="currently loaded Replay")
            self.windows.append(window)
            self.assert_korean("launcher idle", visible_texts(window))
            self.assertIn("현재 불러온 Replay", window.source_label.text())
            dialog = window._r_target_dialog()
            self.assert_korean("R target dialog", visible_texts(dialog) + [
                dialog.labelText(), dialog.okButtonText(), dialog.cancelButtonText()])
            self.assertEqual((dialog.okButtonText(), dialog.cancelButtonText()), ("확인", "취소"))
            dialog.deleteLater()
            with patch.object(launcher.SameBoardComparisonLauncherWindow, "_ask_r_target",
                              return_value=("120", True)):
                window.algorithm_checks["S4_R"].setChecked(True)
            window.algorithm_checks["S2"].setChecked(False)
            window.algorithm_checks["K_P0"].setChecked(True)
            window.run_button.click()
            self.assert_korean("launcher running", visible_texts(window))
            window.queue.deliver([self.runs["S3"], self.runs["K_P0"]], finish=False)
            self.assert_korean("launcher partial", visible_texts(window))
            window.queue.deliver([self.runs["S4_R"]])
            self.assert_korean("launcher completed", visible_texts(window))
            runs_window = window._runs_window
            self.assertIsInstance(runs_window, SameBoardRunsWindow)
            for index in range(runs_window.shown_selector.count()):
                runs_window.shown_selector.setCurrentIndex(index)
                runs_window.on_play_pause()
                self.assert_korean(f"results {index}", visible_texts(runs_window))
            for row in range(runs_window.table.rowCount()):
                runs_window.table.setCurrentCell(row, 0)
                self.assert_korean(f"results detail {row}", [runs_window.detail_label.text()])
            failed = SameBoardRunsWindow(self.context, {key: not_run(key, outcome, detail) for key, outcome, detail in (
                ("K_LC0", "LIMIT", "알고리즘별 한도 30 s에 도달함."), ("K_LC1", "CANCELLED", "실행 중 취소됨."),
                ("S4_M", "LIMIT", "전체 한도에 도달함."))})
            self.windows.append(failed)
            self.assert_korean("results not played", visible_texts(failed))
        for context in (human_context(with_trace=True), human_context(prelude=True), human_context(mined_origin=True)):
            detail = SameBoardComparisonWindow(run_same_board_comparison(context))
            self.windows.append(detail)
            for index in range(detail.run_selector.count()):
                detail.run_selector.setCurrentIndex(index)
                detail.on_last()
                for mode in range(detail.mode_selector.count()):
                    detail.mode_selector.setCurrentIndex(mode)
                    detail.on_play_pause()
                    self.assert_korean("detail window", visible_texts(detail))
                    detail.on_play_pause()
        self.assertEqual(english_outside_allowlist("Show hidden answers Run"), ["Show", "hidden", "answers", "Run"])


if __name__ == "__main__":
    unittest.main()
