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

    def _ui_for_replay(self, replay_data, zini=5):
        ui = MinesweeperUI.__new__(MinesweeperUI)
        ui._replay_player = ReplayPlayer(replay_data)
        ui._display_time = 0.0
        ui._ensure_zini_metric_job = lambda: None
        ui._current_zini_clicks = lambda: zini
        ui._replay_display_time = lambda: ui._display_time
        ui._prepare_replay_counter_state(replay_data)
        return ui

    def _stats_at(self, ui, index, display_time=None):
        ui._replay_player.go_to(index)
        if display_time is None:
            display_time = ui._replay_player.current_time
        ui._display_time = display_time
        return ui._build_replay_statistics()

    def test_completed_replay_stays_unmasked_when_current_state_is_playing(self):
        ui = self._ui_for_replay(self._lost_replay())

        stats = self._stats_at(ui, 1)

        self.assertTrue(ui._replay_is_completed)
        self.assertEqual(ui._replay_player.engine.status, GameStatus.PLAYING)
        self.assertEqual(stats["time"], "1.000")
        self.assertEqual(stats["bbbv"], "1/8")
        self.assertNotEqual(stats["bbbv"], "-")

        self._stats_at(ui, 7)
        self.assertTrue(ui._replay_is_completed)

    def test_incomplete_replay_masks_all_stat_rows_and_overwrites_old_values(self):
        ui = self._ui_for_replay(self._incomplete_replay())
        ui._stat_value_items = {
            key: _StatItem("old") for key, _label, _dummy in STAT_ROWS
        }

        ui._update_replay_statistics_panel()

        self.assertFalse(ui._replay_is_completed)
        self.assertEqual(
            set(ui._build_replay_statistics()),
            {key for key, _label, _dummy in STAT_ROWS},
        )
        for key, _label, _dummy in STAT_ROWS:
            self.assertEqual(ui._build_replay_statistics()[key], "-")
            self.assertEqual(ui._stat_value_items[key].text, "-")

    def test_3bv_and_ops_current_values_move_while_totals_stay_fixed(self):
        ui = self._ui_for_replay(self._won_opening_replay())

        initial = self._stats_at(ui, 0, display_time=0.0)
        finished = self._stats_at(ui, 1, display_time=1.0)

        self.assertEqual(initial["bbbv"], "0/1")
        self.assertEqual(initial["ops"], "0/1")
        self.assertEqual(finished["bbbv"], "1/1")
        self.assertEqual(finished["ops"], "1/1")
        self.assertEqual(initial["bbbv"].split("/")[1], finished["bbbv"].split("/")[1])
        self.assertEqual(initial["ops"].split("/")[1], finished["ops"].split("/")[1])

    def test_click_counters_use_active_plus_wasted_format_by_action(self):
        ui = self._ui_for_replay(self._lost_replay())

        stats = self._stats_at(ui, 7)

        self.assertEqual(stats["clicks"], "4 + 3")
        self.assertEqual(stats["left"], "1 + 1")
        self.assertEqual(stats["right"], "2 + 1")
        self.assertEqual(stats["chord"], "1 + 1")

    def test_derived_metrics_use_replay_time_and_expected_formats(self):
        ui = self._ui_for_replay(self._lost_replay(), zini=5)

        stats = self._stats_at(ui, 6, display_time=6.0)

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
        ui = self._ui_for_replay(self._lost_replay(), zini=5)

        before_chord = self._stats_at(ui, 5, display_time=5.0)
        after_chord = self._stats_at(ui, 6, display_time=6.0)

        self.assertEqual(before_chord["zini"], "5")
        self.assertEqual(after_chord["zini"], "5")
        self.assertEqual(before_chord["zne"], "1.0000")
        self.assertEqual(before_chord["znt"], "1.6667")
        self.assertEqual(after_chord["zne"], "0.8333")
        self.assertEqual(after_chord["znt"], "1.2500")

    def test_zero_division_metrics_are_masked_at_initial_position(self):
        ui = self._ui_for_replay(self._lost_replay(), zini=5)

        stats = self._stats_at(ui, 0, display_time=0.0)

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
        ui = self._ui_for_replay(self._lost_replay(), zini=5)

        at_event_time = self._stats_at(ui, 6, display_time=6.0)
        between_events = self._stats_at(ui, 6, display_time=6.5)

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


if __name__ == "__main__":
    unittest.main()
