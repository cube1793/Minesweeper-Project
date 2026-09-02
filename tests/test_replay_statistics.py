import os
import sys
import types
import unittest
from importlib.util import find_spec
from unittest.mock import Mock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_PYQT5_AVAILABLE = find_spec("PyQt5") is not None


def _install_pyqt_stubs_if_needed():
    if _PYQT5_AVAILABLE:
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
    qt_widgets.QSizePolicy.Fixed = 0

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

if _PYQT5_AVAILABLE:
    from PyQt5.QtWidgets import QApplication
else:
    QApplication = None

_TEST_QAPPLICATION = None


def _ensure_test_qapplication():
    global _TEST_QAPPLICATION
    if not _PYQT5_AVAILABLE:
        return None

    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    _TEST_QAPPLICATION = application
    return application

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
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
import ui_manager
from ui_manager import MinesweeperUI, STAT_ROWS


class _StatItem:
    def __init__(self, text):
        self.text = text

    def setText(self, text):
        self.text = text


class _SignalProbe:
    def connect(self, callback):
        self.callback = callback


class _TimerProbe:
    def __init__(self, *_args, **_kwargs):
        self.timeout = _SignalProbe()
        self.active = False
        self.interval = None

    def setInterval(self, interval):
        self.interval = interval

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def isActive(self):
        return self.active


class _WidgetProbe:
    def __init__(self):
        self.text = None
        self.fixed_size = None

    def setText(self, text):
        self.text = text

    def setFixedSize(self, width, height):
        self.fixed_size = (width, height)


class _GridProbe:
    def __init__(self):
        self.widgets = []

    def addWidget(self, widget, y, x):
        self.widgets.append((widget, x, y))

    def removeWidget(self, widget):
        self.widgets = [entry for entry in self.widgets if entry[0] is not widget]


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


class MinesweeperUIEngineOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.qt_application = _ensure_test_qapplication()

    def _live_engine(self):
        engine = MinesweeperEngine(width=4, height=3, num_mines=2)
        engine.reset_with_mines(
            width=4,
            height=3,
            num_mines=2,
            mine_positions={(2, 1), (3, 2)},
        )
        return engine

    def _replay_data(self):
        return ReplayData(
            board=ReplayBoard(
                width=2,
                height=2,
                num_mines=1,
                mine_positions={(1, 1)},
            ),
            events=(
                ReplayEvent(1.0, 0, 0, ACTION_OPEN),
                ReplayEvent(2.0, 1, 1, ACTION_FLAG),
                ReplayEvent(3.0, 0, 0, ACTION_CHORD),
            ),
        )

    def _ui_with_live_engine(self, live_engine):
        with (
            patch.object(ui_manager, "QTimer", _TimerProbe),
            patch.object(MinesweeperUI, "_init_ui"),
            patch.object(MinesweeperUI, "_init_shortcuts"),
            patch.object(MinesweeperUI, "render_board"),
            patch.object(MinesweeperUI, "_update_statistics_panel"),
        ):
            return MinesweeperUI(live_engine)

    def _prepare_lifecycle_ui(self, live_engine):
        ui = self._ui_with_live_engine(live_engine)
        ui.reset_button = _WidgetProbe()
        ui.timer_label = _WidgetProbe()
        ui._build_grid = Mock()
        ui._apply_initial_window_size = Mock()
        ui.render_board = Mock()
        ui._update_statistics_panel = Mock()
        ui._update_replay_statistics_panel = Mock()
        ui._update_replay_status_label = Mock()
        ui._update_replay_controls = Mock()
        ui._stop_replay_autoplay = Mock()
        return ui

    def _enter_replay(self, ui):
        player = ReplayPlayer(self._replay_data())
        ui._enter_replay_mode(player)
        return player

    def _zini_snapshot_requested_by(self, ui):
        create_files = Mock(side_effect=RuntimeError("stop before worker launch"))
        ui._create_zini_worker_files = create_files
        ui._cleanup_zini_worker_files = Mock()
        ui._zini_result_token = None
        ui._zini_process = None
        ui._zini_process_token = None

        with patch("builtins.print"):
            ui._ensure_zini_metric_job()

        return create_files.call_args.args[1]

    def test_constructor_keeps_injected_live_engine_identity(self):
        live_engine = self._live_engine()

        ui = self._ui_with_live_engine(live_engine)

        self.assertIs(ui.engine, live_engine)
        self.assertEqual(ui._normal_game_config, (4, 3, 2))
        self.assertEqual(
            (
                ui._replay_recorder.width,
                ui._replay_recorder.height,
                ui._replay_recorder.num_mines,
            ),
            (4, 3, 2),
        )

    def test_replay_navigation_keeps_live_identity_and_selector_tracks_seek(self):
        live_engine = self._live_engine()
        ui = self._prepare_lifecycle_ui(live_engine)

        player = self._enter_replay(ui)

        self.assertIs(ui.engine, live_engine)
        self.assertIs(ui._engine_for_current_mode(), player.engine)

        ui.on_replay_next()
        self.assertIs(ui.engine, live_engine)
        self.assertIs(ui._engine_for_current_mode(), player.engine)

        before_seek_engine = player.engine
        player.go_to(2)
        ui._refresh_replay_view_after_move()
        self.assertIsNot(player.engine, before_seek_engine)
        self.assertIs(ui.engine, live_engine)
        self.assertIs(ui._engine_for_current_mode(), player.engine)

        before_previous_engine = player.engine
        ui.on_replay_previous()
        self.assertIsNot(player.engine, before_previous_engine)
        self.assertIs(ui.engine, live_engine)
        self.assertIs(ui._engine_for_current_mode(), player.engine)

    def test_replay_operations_do_not_mutate_live_engine(self):
        live_engine = self._live_engine()
        live_engine.step(2, 1, Action.FLAG)
        live_engine.step(0, 0, Action.FLAG)
        before = {
            "config": (
                live_engine.width,
                live_engine.height,
                live_engine.num_mines,
            ),
            "observation": live_engine.get_observation(),
            "snapshot": live_engine.get_board_snapshot(),
            "counters": live_engine.get_counter_snapshot(),
            "flags": live_engine.count_flags(),
        }
        ui = self._prepare_lifecycle_ui(live_engine)

        player = self._enter_replay(ui)
        ui.on_replay_next()
        player.go_to(player.event_count)
        ui._refresh_replay_view_after_move()
        ui.on_replay_previous()

        self.assertIs(ui.engine, live_engine)
        self.assertEqual(
            (live_engine.width, live_engine.height, live_engine.num_mines),
            before["config"],
        )
        self.assertEqual(live_engine.get_observation(), before["observation"])
        self.assertEqual(live_engine.get_board_snapshot(), before["snapshot"])
        self.assertEqual(live_engine.get_counter_snapshot(), before["counters"])
        self.assertEqual(live_engine.count_flags(), before["flags"])

    def test_replay_input_and_reset_handlers_leave_live_engine_untouched(self):
        live_engine = self._live_engine()
        live_engine.step(2, 1, Action.FLAG)
        before_observation = live_engine.get_observation()
        before_counters = live_engine.get_counter_snapshot()
        ui = self._prepare_lifecycle_ui(live_engine)
        self._enter_replay(ui)

        ui.on_left_click(0, 0)
        ui.on_right_click(0, 0)
        ui.on_both_click(0, 0)
        ui.on_reset()

        self.assertIs(ui.engine, live_engine)
        self.assertEqual(live_engine.get_observation(), before_observation)
        self.assertEqual(live_engine.get_counter_snapshot(), before_counters)

    def test_exit_replay_resets_same_live_engine_to_saved_config(self):
        live_engine = self._live_engine()
        live_engine.step(2, 1, Action.FLAG)
        ui = self._prepare_lifecycle_ui(live_engine)
        token_before_replay = ui._zini_job_token
        player = self._enter_replay(ui)
        self.assertEqual(ui._zini_job_token, token_before_replay + 1)
        player.go_to(player.event_count)
        ui._refresh_replay_view_after_move()

        ui._exit_replay_mode()

        self.assertIs(ui.engine, live_engine)
        self.assertIs(ui._engine_for_current_mode(), live_engine)
        self.assertFalse(ui._replay_mode)
        self.assertIsNone(ui._replay_player)
        self.assertEqual(ui._zini_job_token, token_before_replay + 2)
        self.assertEqual(
            (live_engine.width, live_engine.height, live_engine.num_mines),
            (4, 3, 2),
        )
        self.assertFalse(live_engine.get_board_snapshot().mines_placed)
        self.assertTrue(
            all(
                value == CellState.HIDDEN.value
                for row in live_engine.get_observation()
                for value in row
            )
        )
        self.assertEqual(live_engine.count_flags(), 0)
        self.assertEqual(live_engine.get_counter_snapshot()["active_clicks"], 0)
        self.assertEqual(live_engine.get_counter_snapshot()["wasted_clicks"], 0)
        self.assertEqual(
            (
                ui._replay_recorder.width,
                ui._replay_recorder.height,
                ui._replay_recorder.num_mines,
            ),
            (4, 3, 2),
        )

    def test_replay_grid_render_size_and_mine_counter_use_replay_engine(self):
        live_engine = self._live_engine()
        ui = self._ui_with_live_engine(live_engine)
        player = ReplayPlayer(self._replay_data())
        player.go_to(2)
        ui._replay_mode = True
        ui._replay_player = player
        ui._buttons = {}
        ui._cell_size = 10
        ui.grid = _GridProbe()
        ui.board_container = _WidgetProbe()
        ui.mine_label = _WidgetProbe()
        ui.resize = Mock()
        ui._render_cell = Mock()

        ui._build_grid()
        ui._apply_initial_window_size()
        ui.render_board()

        self.assertEqual(set(ui._buttons), {(0, 0), (1, 0), (0, 1), (1, 1)})
        self.assertEqual(len(ui.grid.widgets), 4)
        self.assertEqual(ui.board_container.fixed_size, (20, 20))
        ui.resize.assert_called_once_with(
            20 + ui_manager.STATS_PANEL_WIDTH + 60,
            20 + 130,
        )
        self.assertEqual(ui._render_cell.call_count, 4)
        self.assertEqual(
            [call.args[1] for call in ui._render_cell.call_args_list],
            [value for row in player.engine.get_observation() for value in row],
        )
        self.assertEqual(ui.mine_label.text, "💣 000")
        self.assertIs(ui.engine, live_engine)

    def test_zini_snapshot_uses_live_or_latest_replay_engine_by_mode(self):
        live_engine = self._live_engine()
        ui = self._ui_with_live_engine(live_engine)

        live_snapshot = self._zini_snapshot_requested_by(ui)
        self.assertEqual(live_snapshot, live_engine.get_board_snapshot())

        player = ReplayPlayer(self._replay_data())
        replaced_engine = player.engine
        player.go_to(player.event_count)
        self.assertIsNot(player.engine, replaced_engine)
        ui._replay_mode = True
        ui._replay_player = player
        ui._zini_job_token += 1

        replay_snapshot = self._zini_snapshot_requested_by(ui)

        self.assertEqual(replay_snapshot, player.engine.get_board_snapshot())
        self.assertNotEqual(replay_snapshot, live_engine.get_board_snapshot())
        self.assertIs(ui.engine, live_engine)

    def test_live_replay_recording_still_uses_injected_engine(self):
        live_engine = self._live_engine()
        ui = self._ui_with_live_engine(live_engine)

        live_engine.step(2, 1, Action.FLAG)
        ui._record_replay_event(2, 1, Action.FLAG)

        self.assertIs(ui.engine, live_engine)
        self.assertEqual(len(ui._replay_recorder.events), 1)
        self.assertEqual(ui._replay_recorder.events[0].action, ACTION_FLAG)
        self.assertEqual(
            ui._replay_recorder.board.mine_positions,
            live_engine.get_board_snapshot().mines,
        )


if __name__ == "__main__":
    unittest.main()
