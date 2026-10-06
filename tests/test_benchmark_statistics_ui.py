"""Real offscreen Qt boundaries using small local telemetry fixtures."""

import ast
import os
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import benchmark_statistics as statistics
import benchmark_statistics_presentation as presentation
import telemetry_repository as repository
from tests.test_benchmark_statistics import StatisticsTestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication
    import pyqtgraph
except ImportError:
    QApplication = None
else:
    import benchmark_statistics_ui as viewer
    from core_engine import MinesweeperEngine
    from replay_model import ReplayBoard, ReplayData, ReplayEvent
    from replay_player import ReplayPlayer
    from ui_manager import MinesweeperUI


@unittest.skipIf(QApplication is None, "PyQt5 / PyQtGraph unavailable")
class StatisticsUITests(StatisticsTestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.window = viewer.BenchmarkStatisticsWindow()
        self.addCleanup(self.close_window)

    def close_window(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def official_run(self):
        run_id = self.create_run(requested_games=1)
        self.persist(run_id)
        self.finish(run_id)
        return run_id

    def select_run(self, run_id):
        self.window.run_combo.setCurrentIndex(self.window.run_combo.findData(run_id))

    def test_constructs_in_korean_without_opening_database(self):
        self.assertEqual(self.window.windowTitle(), "벤치마크 통계")
        self.assertEqual(self.window.tabs.count(), 4)
        self.assertIsNone(self.window.connection)
        self.assertIsNone(self.window.current_statistics)
        self.assertFalse(self.window.run_combo.isEnabled())

    def test_opens_readonly_lists_runs_and_selects_via_backend(self):
        diagnostic = self.mixed_run()
        official = self.official_run()
        with (
            patch.object(viewer, "connect_database_readonly", wraps=repository.connect_database_readonly) as connect,
            patch.object(viewer.statistics, "calculate_run_statistics", wraps=statistics.calculate_run_statistics) as calculate,
        ):
            self.assertTrue(self.window.open_database(self.database))
            connect.assert_called_once_with(self.database)
            self.assertEqual(self.window.run_combo.count(), 2)
            self.assertEqual(self.window.selected_run_id, official)
            calculate.assert_called_once_with(self.window.connection, official)
            self.assertEqual(self.window.state_label.text(), "공식 기준 사용 가능")
            self.select_run(diagnostic)
            self.assertEqual(calculate.call_count, 2)
            calculate.assert_called_with(self.window.connection, diagnostic)
        with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"):
            self.window.connection.execute("DELETE FROM benchmark_runs")
        self.assertEqual(self.window.state_label.text(), "진단용 실행")
        expected = {
            "run_status": "FAILED", "requested_games": "6", "processed_games": "4",
            "stored_game_count": "4", "exact_processed_prefix": "예", "exact_requested_prefix": "아니요",
            "git_dirty": "아니요", "official_eligible": "아니요", "wins": "3", "losses": "1",
            "win_rate": "3/4 (75.00%)", "mean_guess_count": "3/4 (≈ 0.75)",
            "compute_time_total_ns": "95 ns", "decision_compute_count": "8",
            "mean_decision_compute_ns": "95/8 ns (≈ 11.875 ns)", "max_decision_compute_ns": "23 ns",
            "p50": "11 ns", "p90": "23 ns", "p95": "23 ns", "p99": "23 ns",
            "local_deterministic_count": "2", "global_certainty_count": "3",
            "probability_guess_count": "3", "total_actions": "12", "open_count": "8",
            "flag_count": "2", "chord_count": "2", "games_with_probability_guess": "2",
            "guess_game_rate": "1/2 (50.00%)",
        }
        for key, value in expected.items():
            self.assertEqual(self.window.value_labels[key].text(), value, key)

    def test_all_graphs_use_backend_distribution_and_keep_exact_risk(self):
        self.mixed_run()
        self.window.open_database(self.database)
        result = self.window.current_statistics
        for points, distribution, bars in (
            (self.window.guess_points, result.guess_count_distribution, self.window.guess_bars),
            (self.window.board_points, result.board_3bv_distribution, self.window.board_bars),
        ):
            self.assertEqual(tuple((p.x, p.count) for p in points), distribution)
            self.assertEqual(tuple(bars.opts["x"]), tuple(x for x, _ in distribution))
            self.assertEqual(tuple(bars.opts["height"]), tuple(y for _, y in distribution))
        self.assertEqual(self.window.guess_points[0].x, 0)
        self.assertEqual(self.window.guess_points[0].count, 2)
        spots = self.window.risk_scatter.points()
        self.assertEqual(tuple((p.data().probability, p.data().count) for p in spots),
                         result.probability_guess_distribution)
        self.assertLess(spots[0].pos().x(), spots[1].pos().x())
        self.assertEqual(tuple(point.pos().x() for point in spots),
                         tuple(float(risk * 100) for risk, _ in result.probability_guess_distribution))
        self.assertEqual(tuple(p.data().exact_label for p in spots), ("2/9", "1/3"))
        self.window.risk_scatter.sigClicked.emit(self.window.risk_scatter, [spots[1]], None)
        self.assertEqual(self.window.risk_combo.currentText(), "1/3")
        self.assertIn("1/3", self.window.risk_detail_label.text())
        self.assertIn("1/3", self.window.risk_scatter.opts["tip"](0, 0, spots[1].data()))

    def test_percent_axis_ticks_and_graph_mouse_interaction(self):
        self.mixed_run()
        self.window.open_database(self.database)
        axis = self.window.risk_plot.getAxis("bottom")
        self.assertEqual(axis.tickStrings([0, 25, 50, 75, 100], 1, 25),
                         ["0%", "25%", "50%", "75%", "100%"])
        self.assertEqual(axis.tickStrings([0.77, 1.23], 1, 0.01), ["0.77%", "1.23%"])
        left, right = self.window.risk_plot.getViewBox().viewRange()[0]
        self.assertLessEqual(left, 0)
        self.assertGreaterEqual(right, 100)
        for language in ("en", "ko"):
            self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
            self.assertEqual(axis.labelText, presentation.text("risk_x", language))
            self.assertIn("%", axis.labelText)
            self.assertEqual(self.window.guess_plot.getViewBox().mouseEnabled(), [False, False])
            self.assertEqual(self.window.board_plot.getViewBox().mouseEnabled(), [False, False])
            self.assertEqual(self.window.risk_plot.getViewBox().mouseEnabled(), [True, True])

    def test_language_round_trip_keeps_reader_selection_result_and_plot_items(self):
        diagnostic = self.mixed_run()
        self.official_run()
        self.window.open_database(self.database)
        self.select_run(diagnostic)
        self.window.risk_combo.setCurrentIndex(1)
        result = self.window.current_statistics
        reader = self.window.connection
        points = self.window.risk_points
        graph_data = self.window.risk_scatter.data
        domains = {key: self.window.value_labels[key].text() for key in (
            "benchmark_set_id", "solver_stage", "solver_policy", "first_click_policy",
            "board_generator_version", "run_status",
        )}
        with patch.object(viewer.statistics, "calculate_run_statistics") as calculate:
            for language in ("en", "ko"):
                self.window.language_combo.setCurrentIndex(self.window.language_combo.findData(language))
                self.assertEqual(self.window.windowTitle(), presentation.text("title", language))
                for key, label in self.window._labels.items():
                    self.assertEqual(label.text(), presentation.text(key, language))
                for key, group in self.window._groups.items():
                    self.assertEqual(group.title(), presentation.text(key, language))
                for index, key in enumerate(("summary", "guess_graph", "risk_graph", "board_graph")):
                    self.assertEqual(self.window.tabs.tabText(index), presentation.text(key, language))
                self.assertEqual(self.window.guess_plot.getAxis("bottom").labelText,
                                 presentation.text("guess_x", language))
                self.assertIs(self.window.current_statistics, result)
                self.assertIs(self.window.connection, reader)
                self.assertIs(self.window.risk_points, points)
                self.assertIs(self.window.risk_scatter.data, graph_data)
                self.assertEqual(self.window.selected_run_id, diagnostic)
                self.assertEqual(self.window.risk_combo.currentIndex(), 1)
                for key, value in domains.items():
                    self.assertEqual(self.window.value_labels[key].text(), value)
            calculate.assert_not_called()

    def test_empty_valid_database_and_empty_run_show_no_stale_values(self):
        self.assertTrue(self.window.open_database(self.database))
        self.assertEqual(self.window.run_combo.count(), 0)
        self.assertEqual(self.window.state_label.text(), presentation.text("empty_database"))
        self.create_run(run_status="FAILED")
        self.window.open_database(self.database)
        self.assertEqual(self.window.state_label.text(), presentation.text("diagnostic"))
        self.assertEqual(self.window.value_labels["win_rate"].text(), "—")
        self.assertEqual(self.window.value_labels["p99"].text(), "—")
        self.assertEqual(self.window.risk_points, ())

    def test_bad_database_errors_preserve_previous_selection_and_connection(self):
        run_id = self.official_run()
        self.window.open_database(self.database)
        reader = self.window.connection
        invalid = self.database.with_name("invalid.db")
        invalid.write_bytes(b"not SQLite")
        incompatible = self.database.with_name("incompatible.db")
        raw = sqlite3.connect(incompatible)
        raw.execute("PRAGMA user_version=99")
        raw.close()
        missing_tables = self.database.with_name("missing-tables.db")
        raw = sqlite3.connect(missing_tables)
        raw.execute("PRAGMA user_version=1")
        raw.close()
        for path in (self.database.with_name("missing.db"), invalid, incompatible, missing_tables):
            with self.subTest(path=path):
                self.assertFalse(self.window.open_database(path))
                self.assertIn(presentation.text("error"), self.window.error_label.text())
                self.assertIs(self.window.connection, reader)
                self.assertEqual(self.window.selected_run_id, run_id)
                self.assertEqual(reader.execute("SELECT 1").fetchone()[0], 1)

    def test_failed_candidate_query_closes_candidate_keeps_old_reader(self):
        self.official_run()
        self.window.open_database(self.database)
        reader = self.window.connection
        candidate = repository.connect_database_readonly(self.database)
        with (
            patch.object(viewer, "connect_database_readonly", return_value=candidate),
            patch.object(viewer.statistics, "list_benchmark_runs", side_effect=sqlite3.OperationalError("read failure")),
        ):
            self.assertFalse(self.window.open_database(self.database))
        with self.assertRaises(sqlite3.ProgrammingError):
            candidate.execute("SELECT 1")
        self.assertIs(self.window.connection, reader)

    def test_selection_query_failure_clears_previous_result_and_graphs(self):
        failed = self.mixed_run()
        self.official_run()
        self.window.open_database(self.database)
        with patch.object(viewer.statistics, "calculate_run_statistics",
                          side_effect=statistics.BenchmarkStatisticsError("bad risk")):
            self.select_run(failed)
        self.assertIsNone(self.window.current_statistics)
        self.assertEqual(self.window.guess_points, ())
        self.assertEqual(self.window.risk_points, ())
        self.assertEqual(self.window.value_labels["wins"].text(), "—")
        self.assertEqual(self.window.value_labels["official_eligible"].text(), "—")
        self.assertIn("bad risk", self.window.error_label.text())

    def test_successful_database_switch_and_all_close_routes_release_reader(self):
        self.official_run()
        self.window.open_database(self.database)
        old = self.window.connection
        other = self.database.with_name("other.db")
        repository.connect_database(other).close()
        self.window.open_database(other)
        with self.assertRaises(sqlite3.ProgrammingError):
            old.execute("SELECT 1")
        for close in (self.window.close, self.window.reject,
                      lambda: QTest.keyClick(self.window, Qt.Key_Escape)):
            self.window.open_database(self.database)
            self.window.show()
            reader = self.window.connection
            close()
            self.assertIsNone(self.window.connection)
            with self.assertRaises(sqlite3.ProgrammingError):
                reader.execute("SELECT 1")

    def test_main_game_ownership_and_active_controls_unchanged(self):
        self.mixed_run()
        self.official_run()
        engine = MinesweeperEngine(3, 3, 1)
        with patch.object(MinesweeperUI, "_ensure_zini_metric_job"):
            main = MinesweeperUI(engine)
            self.addCleanup(main.deleteLater)
            self.addCleanup(main.close)
            main.simple_auto_checkbox.setChecked(True)
            main._simple_auto_timer.setInterval(60000)
            before = (engine.get_board_snapshot(), engine.get_counter_snapshot(), main._replay_mode,
                      main._replay_player, main._replay_data, main._analysis_result,
                      main._simple_auto_pending, main._simple_auto_timer.isActive(),
                      main.simple_auto_checkbox.isChecked(), main._zini_job_token, main._zini_process,
                      main._timer.isActive(), main._timer_running, main.difficulty_combo.currentText())
            with patch.object(engine, "reset", wraps=engine.reset) as reset:
                main.benchmark_statistics_button.click()
                window = main._benchmark_statistics_window
                window.open_database(self.database)
                window.run_combo.setCurrentIndex(1)
                window.language_combo.setCurrentIndex(1)
                window.open_database(self.database.with_name("missing.db"))
                other = self.database.with_name("switch.db")
                repository.connect_database(other).close()
                window.open_database(other)
                window.close()
                reset.assert_not_called()
            self.assertIs(main.engine, engine)
            after = (engine.get_board_snapshot(), engine.get_counter_snapshot(), main._replay_mode,
                     main._replay_player, main._replay_data, main._analysis_result,
                     main._simple_auto_pending, main._simple_auto_timer.isActive(),
                     main.simple_auto_checkbox.isChecked(), main._zini_job_token, main._zini_process,
                     main._timer.isActive(), main._timer_running, main.difficulty_combo.currentText())
            self.assertEqual(before, after)
            main.on_benchmark_statistics()
            self.assertIs(main._benchmark_statistics_window, window)
            window.open_database(self.database)
            reader = window.connection
            main.close()
            with self.assertRaises(sqlite3.ProgrammingError):
                reader.execute("SELECT 1")

    def test_viewer_does_not_change_active_replay_or_analysis(self):
        self.official_run()
        with patch.object(MinesweeperUI, "_ensure_zini_metric_job"):
            main = MinesweeperUI(MinesweeperEngine(3, 3, 1))
            self.addCleanup(main.deleteLater)
            self.addCleanup(main.close)
            data = ReplayData(ReplayBoard(2, 2, 1, frozenset({(1, 1)})),
                              (ReplayEvent(1.0, 0, 0, "OPEN"),))
            player = ReplayPlayer(data)
            main._enter_replay_mode(player)
            main.analysis_checkbox.setChecked(True)
            analysis = main._replay_analysis_result
            timeline = main._replay_counter_timeline
            engine = main.engine
            replay_engine = player.engine
            main.on_benchmark_statistics()
            window = main._benchmark_statistics_window
            window.open_database(self.database)
            window.language_combo.setCurrentIndex(1)
            window.close()
            self.assertIs(main.engine, engine)
            self.assertIs(main._replay_player, player)
            self.assertIs(player.engine, replay_engine)
            self.assertIs(main._replay_data, data)
            self.assertIs(main._replay_analysis_result, analysis)
            self.assertIs(main._replay_counter_timeline, timeline)
            self.assertTrue(main._replay_mode)
            self.assertEqual(player.current_index, 0)


class UIDependencyTests(unittest.TestCase):
    def test_ui_imports_only_its_presentation_statistics_and_readonly_repository(self):
        path = Path(__file__).resolve().parents[1] / "benchmark_statistics_ui.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        allowed = sys.stdlib_module_names | {
            "PyQt5", "pyqtgraph", "benchmark_statistics", "benchmark_statistics_presentation",
            "telemetry_repository",
        }
        for node in ast.walk(tree):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                self.assertIn(name.split(".")[0], allowed)
            if isinstance(node, ast.ImportFrom) and node.module == "telemetry_repository":
                self.assertEqual([alias.name for alias in node.names], ["connect_database_readonly"])


if __name__ == "__main__":
    unittest.main()
