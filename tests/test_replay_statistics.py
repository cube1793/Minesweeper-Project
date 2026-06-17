import os
import sys
import types
import unittest
from importlib.util import find_spec


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _install_pyqt_stubs_if_needed():
    if find_spec("PyQt5") is not None:
        return

    pyqt5 = types.ModuleType("PyQt5")
    qt_widgets = types.ModuleType("PyQt5.QtWidgets")
    qt_core = types.ModuleType("PyQt5.QtCore")
    qt_gui = types.ModuleType("PyQt5.QtGui")

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, _name):
            def _method(*args, **kwargs):
                return None

            return _method

    class _Signal:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            pass

    class _Qt:
        NoFocus = 0
        ClickFocus = 1
        Horizontal = 1
        LeftButton = 1
        transparent = 0
        NoPen = 0

    class _QSize:
        def __init__(self, width=0, height=0):
            self.width = width
            self.height = height

    class _QFont(_Dummy):
        Bold = 75

    class _QIcon(_Dummy):
        Normal = 0
        Disabled = 1
        Off = 0

    class _QStyle(_Dummy):
        CC_Slider = 1
        SC_SliderHandle = 2

    def _pyqt_signal(*args, **kwargs):
        return _Signal(*args, **kwargs)

    for name in (
        "QWidget",
        "QPushButton",
        "QGridLayout",
        "QVBoxLayout",
        "QHBoxLayout",
        "QLabel",
        "QComboBox",
        "QSizePolicy",
        "QShortcut",
        "QInputDialog",
        "QSpinBox",
        "QDoubleSpinBox",
        "QScrollArea",
        "QSlider",
        "QTableWidget",
        "QTableWidgetItem",
        "QAbstractItemView",
        "QHeaderView",
        "QFileDialog",
        "QMessageBox",
        "QStyleOptionSlider",
    ):
        setattr(qt_widgets, name, _Dummy)
    qt_widgets.QStyle = _QStyle

    qt_core.Qt = _Qt
    qt_core.pyqtSignal = _pyqt_signal
    qt_core.QTimer = _Dummy
    qt_core.QPoint = _Dummy
    qt_core.QSize = _QSize

    qt_gui.QFont = _QFont
    qt_gui.QKeySequence = _Dummy
    qt_gui.QColor = _Dummy
    qt_gui.QIcon = _QIcon
    qt_gui.QPainter = _Dummy
    qt_gui.QPixmap = _Dummy
    qt_gui.QPolygon = _Dummy

    sys.modules["PyQt5"] = pyqt5
    sys.modules["PyQt5.QtWidgets"] = qt_widgets
    sys.modules["PyQt5.QtCore"] = qt_core
    sys.modules["PyQt5.QtGui"] = qt_gui


_install_pyqt_stubs_if_needed()

from core_engine import GameStatus
from replay_model import (
    ACTION_CHORD,
    ACTION_FLAG,
    ACTION_OPEN,
    ReplayBoard,
    ReplayData,
    ReplayEvent,
)
from replay_player import ReplayPlayer
from replay_statistics import ReplayStatisticsAnalyzer, STAT_KEYS
from ui_manager import MinesweeperUI, STAT_ROWS


class _StatItem:
    def __init__(self, text):
        self.text = text

    def setText(self, text):
        self.text = text


class ReplayStatisticsTests(unittest.TestCase):
    def _lost_replay(self):
        return ReplayData(
            board=ReplayBoard(
                width=3,
                height=3,
                num_mines=1,
                mine_positions={(1, 1)},
            ),
            events=(
                ReplayEvent(1.0, 0, 0, ACTION_OPEN),
                ReplayEvent(2.0, 0, 0, ACTION_OPEN),
                ReplayEvent(3.0, 1, 1, ACTION_FLAG),
                ReplayEvent(4.0, 1, 1, ACTION_FLAG),
                ReplayEvent(5.0, 1, 1, ACTION_FLAG),
                ReplayEvent(6.0, 0, 0, ACTION_CHORD),
                ReplayEvent(7.0, 0, 0, ACTION_CHORD),
                ReplayEvent(8.0, 1, 1, ACTION_OPEN),
                ReplayEvent(9.0, 1, 1, ACTION_FLAG),
                ReplayEvent(10.0, 1, 1, ACTION_OPEN),
            ),
        )

    def _won_opening_replay(self):
        return ReplayData(
            board=ReplayBoard(
                width=3,
                height=3,
                num_mines=1,
                mine_positions={(2, 2)},
            ),
            events=(
                ReplayEvent(1.0, 0, 0, ACTION_OPEN),
            ),
        )

    def _incomplete_replay(self):
        return ReplayData(
            board=ReplayBoard(
                width=3,
                height=3,
                num_mines=1,
                mine_positions={(1, 1)},
            ),
            events=(
                ReplayEvent(1.0, 0, 0, ACTION_OPEN),
            ),
        )

    def _timeline_for(self, replay_data):
        return ReplayStatisticsAnalyzer.analyze(replay_data)

    def _stats_at(self, timeline, index, display_time, zini=5):
        return ReplayStatisticsAnalyzer.statistics_at(
            timeline=timeline,
            index=index,
            replay_time=display_time,
            board_zini=zini,
        )

    def _ui_for_replay(self, replay_data, zini=5):
        ui = MinesweeperUI.__new__(MinesweeperUI)
        ui._replay_player = ReplayPlayer(replay_data)
        ui._display_time = 0.0
        ui._ensure_zini_metric_job = lambda: None
        ui._current_zini_clicks = lambda: zini
        ui._replay_display_time = lambda: ui._display_time
        ui._prepare_replay_counter_state(replay_data)
        return ui

    def test_completed_replay_stays_unmasked_when_current_state_is_playing(self):
        replay_data = self._lost_replay()
        timeline = self._timeline_for(replay_data)
        player = ReplayPlayer(replay_data)

        player.go_to(1)
        stats = self._stats_at(timeline, 1, 1.0)

        self.assertTrue(timeline.is_completed)
        self.assertEqual(player.engine.status, GameStatus.PLAYING)
        self.assertEqual(stats["time"], "1.000")
        self.assertEqual(stats["bbbv"], "1/8")
        self.assertNotEqual(stats["bbbv"], "-")

        self._stats_at(timeline, 7, 7.0)
        self.assertTrue(timeline.is_completed)

    def test_incomplete_replay_masks_all_stat_rows(self):
        timeline = self._timeline_for(self._incomplete_replay())
        stats = self._stats_at(timeline, 1, 1.0)

        self.assertFalse(timeline.is_completed)
        self.assertEqual(set(stats), set(STAT_KEYS))
        for key in STAT_KEYS:
            self.assertEqual(stats[key], "-")

    def test_3bv_and_ops_current_values_move_while_totals_stay_fixed(self):
        timeline = self._timeline_for(self._won_opening_replay())

        initial = self._stats_at(timeline, 0, 0.0)
        finished = self._stats_at(timeline, 1, 1.0)

        self.assertEqual(initial["bbbv"], "0/1")
        self.assertEqual(initial["ops"], "0/1")
        self.assertEqual(finished["bbbv"], "1/1")
        self.assertEqual(finished["ops"], "1/1")
        self.assertEqual(initial["bbbv"].split("/")[1], finished["bbbv"].split("/")[1])
        self.assertEqual(initial["ops"].split("/")[1], finished["ops"].split("/")[1])

    def test_click_counters_use_active_plus_wasted_format_by_action(self):
        timeline = self._timeline_for(self._lost_replay())

        stats = self._stats_at(timeline, 7, 7.0)

        self.assertEqual(stats["clicks"], "4 + 3")
        self.assertEqual(stats["left"], "1 + 1")
        self.assertEqual(stats["right"], "2 + 1")
        self.assertEqual(stats["chord"], "1 + 1")

    def test_derived_metrics_use_replay_time_and_expected_formats(self):
        timeline = self._timeline_for(self._lost_replay())

        stats = self._stats_at(timeline, 6, 6.0, zini=5)

        self.assertEqual(stats["time"], "6.000")
        self.assertEqual(stats["est_time"], "16.000")
        self.assertEqual(stats["bbbv_per_sec"], "0.5000")
        self.assertEqual(stats["cps"], "1.0000")
        self.assertEqual(stats["efficiency"], "50%")
        self.assertEqual(stats["ioe"], "0.5000")
        self.assertEqual(stats["thrp"], "0.7500")
        self.assertEqual(stats["corr"], "0.6667")
        self.assertEqual(stats["zne"], "0.8333")
        self.assertEqual(stats["znt"], "1.2500")

    def test_zini_is_fixed_while_zne_and_znt_follow_current_click_counts(self):
        timeline = self._timeline_for(self._lost_replay())

        before_chord = self._stats_at(timeline, 5, 5.0, zini=5)
        after_chord = self._stats_at(timeline, 6, 6.0, zini=5)

        self.assertEqual(before_chord["zini"], "5")
        self.assertEqual(after_chord["zini"], "5")
        self.assertEqual(before_chord["zne"], "1.0000")
        self.assertEqual(before_chord["znt"], "1.6667")
        self.assertEqual(after_chord["zne"], "0.8333")
        self.assertEqual(after_chord["znt"], "1.2500")

    def test_zero_division_metrics_are_masked_at_initial_position(self):
        timeline = self._timeline_for(self._lost_replay())

        stats = self._stats_at(timeline, 0, 0.0, zini=5)

        for key in (
            "est_time",
            "bbbv_per_sec",
            "cps",
            "efficiency",
            "ioe",
            "thrp",
            "corr",
            "zne",
            "znt",
        ):
            self.assertEqual(stats[key], "-")

    def test_between_event_time_changes_only_time_based_replay_statistics(self):
        timeline = self._timeline_for(self._lost_replay())

        at_event_time = self._stats_at(timeline, 6, 6.0, zini=5)
        between_events = self._stats_at(timeline, 6, 6.5, zini=5)

        for key in ("time", "est_time", "bbbv_per_sec", "cps"):
            self.assertNotEqual(at_event_time[key], between_events[key])

        for key in (
            "bbbv",
            "clicks",
            "left",
            "right",
            "chord",
            "ops",
            "efficiency",
            "ioe",
            "thrp",
            "corr",
            "zini",
            "zne",
            "znt",
        ):
            self.assertEqual(at_event_time[key], between_events[key])

    def test_ui_replay_statistics_panel_applies_analyzer_result(self):
        ui = self._ui_for_replay(self._lost_replay(), zini=5)
        ui._stat_value_items = {
            key: _StatItem("old") for key, _label, _dummy in STAT_ROWS
        }
        ui._replay_player.go_to(6)
        ui._display_time = 6.0

        ui._update_replay_statistics_panel()

        self.assertIsNotNone(ui._replay_counter_timeline)
        self.assertTrue(ui._replay_counter_timeline.is_completed)
        self.assertEqual(ui._stat_value_items["bbbv"].text, "3/8")
        self.assertEqual(ui._stat_value_items["ops"].text, "0/0")
        self.assertEqual(ui._stat_value_items["clicks"].text, "4 + 2")
        self.assertEqual(ui._stat_value_items["zini"].text, "5")
        self.assertEqual(ui._stat_value_items["zne"].text, "0.8333")

    def test_ui_incomplete_replay_masks_panel_and_overwrites_old_values(self):
        ui = self._ui_for_replay(self._incomplete_replay())
        ui._stat_value_items = {
            key: _StatItem("old") for key, _label, _dummy in STAT_ROWS
        }

        ui._update_replay_statistics_panel()

        self.assertIsNotNone(ui._replay_counter_timeline)
        self.assertFalse(ui._replay_counter_timeline.is_completed)
        for key, _label, _dummy in STAT_ROWS:
            self.assertEqual(ui._stat_value_items[key].text, "-")


if __name__ == "__main__":
    unittest.main()
