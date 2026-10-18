"""Source/frozen ZiNi entry points and the UI subprocess lifecycle."""

import os
from dataclasses import replace
from pathlib import Path
import pickle
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tests.ui_settings import isolate_ui_settings
from unittest.mock import Mock, patch

from board_snapshot import BoardSnapshot
from zini_calculator import ZiniMove, ZiniNeighborhoodBeamConfig, ZiniResult
from zini_metric_worker import calculate_counter_zini
from zini_calculator import calculate_g_zini
from zini_trace import build_zini_trace


ROOT = Path(__file__).resolve().parents[1]


class WorkerEntryPointTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = BoardSnapshot(
            width=3, height=3, num_mines=0, mines_placed=True,
            mines=frozenset(), adjacent=((0, 0, 0),) * 3,
        )
        self.payload = {
            "token": 42,
            "snapshot": self.snapshot,
            "config": ZiniNeighborhoodBeamConfig(max_evaluations=1),
        }
        self.moves = (ZiniMove("fallback_click", 0, 0, None, 1),)

    def test_success_transports_existing_final_moves_after_one_search(self):
        search_result = Mock(best_clicks=1, result=ZiniResult(1, self.moves))
        with patch(
            "zini_metric_worker.calculate_g_zini_neighborhood_beam_bounded",
            return_value=search_result,
        ) as search:
            result = calculate_counter_zini(self.payload)
        search.assert_called_once_with(self.snapshot, config=self.payload["config"])
        self.assertEqual(result, {
            "token": 42, "clicks": 1, "moves": self.moves, "error": None,
        })
        self.assertIs(result["moves"], self.moves)
        self.assertEqual(result["clicks"], sum(move.clicks_added for move in result["moves"]))

    def test_search_failure_preserves_failure_shape(self):
        with patch(
            "zini_metric_worker.calculate_g_zini_neighborhood_beam_bounded",
            side_effect=ValueError("search failed"),
        ) as search:
            result = calculate_counter_zini(self.payload)
        search.assert_called_once_with(self.snapshot, config=self.payload["config"])
        self.assertEqual(result, {
            "token": 42, "clicks": None, "moves": None,
            "error": "ValueError('search failed')",
        })

    def test_inconsistent_click_total_becomes_failure_without_retry(self):
        search_result = Mock(best_clicks=2, result=ZiniResult(1, self.moves))
        with patch(
            "zini_metric_worker.calculate_g_zini_neighborhood_beam_bounded",
            return_value=search_result,
        ) as search:
            result = calculate_counter_zini(self.payload)
        search.assert_called_once_with(self.snapshot, config=self.payload["config"])
        self.assertEqual(result, {
            "token": 42, "clicks": None, "moves": None,
            "error": "ValueError('ZiNi click count does not match final moves.')",
        })

    def test_both_entry_points_compute_without_pyqt(self):
        self.check_entry_points(self.payload, {
            "token": 42, "clicks": 1, "moves": self.moves, "error": None,
        })

    def test_both_entry_points_report_calculation_failure_without_pyqt(self):
        payload = {**self.payload, "snapshot": None}
        expected = calculate_counter_zini(payload)
        self.assertIsNotNone(expected["error"])
        self.check_entry_points(payload, expected)

    def check_entry_points(self, payload, expected):
        for entry in (["zini_metric_worker.py"],
                      ["main.py", "--zini-metric-worker"]):
            with self.subTest(entry=entry), TemporaryDirectory(prefix="zini space ") as temp:
                payload_path = Path(temp) / "payload.pkl"
                result_path = Path(temp) / "result.pkl"
                payload_path.write_bytes(pickle.dumps(payload))
                # -S removes site-packages, including PyQt, from the child.
                result = subprocess.run(
                    [sys.executable, "-B", "-S", str(ROOT / entry[0]), *entry[1:],
                     str(payload_path), str(result_path)],
                    cwd=temp, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                received = pickle.loads(result_path.read_bytes())
                self.assertEqual(received, expected)
                self.assertEqual(set(received), {"token", "clicks", "moves", "error"})
                if received["error"] is None:
                    self.assertIs(type(received["moves"]), tuple)
                    self.assertTrue(all(type(move) is ZiniMove for move in received["moves"]))
                    self.assertEqual(received["clicks"], sum(
                        move.clicks_added for move in received["moves"]
                    ))
                else:
                    self.assertIsNone(received["clicks"])
                    self.assertIsNone(received["moves"])
                    self.assertIs(type(received["error"]), str)
                self.assertEqual(sorted(p.name for p in Path(temp).iterdir()),
                                 ["payload.pkl", "result.pkl"])

    def test_dispatch_rejects_wrong_arity_without_starting_qt(self):
        for args in ([], ["payload.pkl"], ["a", "b", "c"]):
            with self.subTest(args=args):
                result = subprocess.run(
                    [sys.executable, "-B", "-S", str(ROOT / "main.py"),
                     "--zini-metric-worker", *args],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("usage:", result.stderr)

    def test_dispatch_propagates_worker_exit_code_before_qt_setup(self):
        import main

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "argv", ["Minesweeper.exe", "--zini-metric-worker", "p", "r"]),
            patch("zini_metric_worker.main", return_value=7) as worker,
            patch.object(main, "_configure_qt_plugin_path") as configure,
        ):
            self.assertEqual(main.main(), 7)
        worker.assert_called_once_with(["--zini-metric-worker", "p", "r"])
        configure.assert_not_called()


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    from core_engine import Action, GameStatus, MinesweeperEngine
    from replay_model import ACTION_OPEN, ReplayBoard, ReplayData, ReplayEvent
    from replay_player import ReplayPlayer
    from ui_manager import MinesweeperUI, ZINI_WORKER_SCRIPT
    from zini_metric_worker import write_result_atomic


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class WorkerLaunchTests(unittest.TestCase):
    def test_main_counter_config_is_shared_authority_alias(self):
        import ui_manager
        import zini_metric_job
        self.assertIs(ui_manager.ZINI_COUNTER_CONFIG, zini_metric_job.ZINI_COUNTER_CONFIG)

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.engine = MinesweeperEngine(3, 3, 1)
        self.settings = isolate_ui_settings(self)
        self.ui = MinesweeperUI(self.engine)
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.result = calculate_g_zini(self.engine.get_board_snapshot())
        self.addCleanup(self.close_ui)

    def close_ui(self):
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def launch(self, frozen):
        process = Mock()
        process.poll.return_value = None
        with (
            patch.object(sys, "frozen", frozen, create=True),
            patch("zini_metric_job.subprocess.Popen", return_value=process) as popen,
        ):
            self.ui._ensure_zini_metric_job()
        payload_path = self.ui._zini_payload_path
        result_path = self.ui._zini_result_path
        popen.assert_called_once_with(
            [sys.executable, "--zini-metric-worker" if frozen else ZINI_WORKER_SCRIPT,
             payload_path, result_path],
            cwd=os.path.dirname(ZINI_WORKER_SCRIPT),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.assertTrue(Path(payload_path).is_file())
        self.assertFalse(Path(result_path).exists())
        self.assertTrue(self.ui._zini_poll_timer.isActive())
        return process, payload_path, result_path

    def test_source_launch_poll_and_cleanup(self):
        self.check_completed_launch(frozen=False)

    def test_unplaced_live_board_does_not_launch_worker(self):
        self.ui.on_reset()
        with patch("zini_metric_job.subprocess.Popen") as popen:
            self.ui._ensure_zini_metric_job()
            self.ui.on_both_click(0, 0)  # CHORD does not fix an unplaced board.
            self.ui._update_statistics_panel(self.engine.get_stats())
        popen.assert_not_called()
        self.assertFalse(self.engine.get_board_snapshot().mines_placed)
        self.assertIsNone(self.ui._zini_explorer.token)

    def test_first_open_or_flag_starts_one_async_job_with_immutable_final_board(self):
        for action in (self.ui.on_left_click, self.ui.on_right_click):
            with self.subTest(action=action.__name__):
                self.ui.on_reset()
                process = Mock()
                process.poll.return_value = None
                with (patch("core_engine.random.sample", return_value=[(1, 1)]),
                      patch("zini_metric_job.subprocess.Popen", return_value=process) as popen):
                    action(0, 0)
                    popen.assert_called_once()
                    self.assertEqual(self.engine.status, GameStatus.PLAYING)
                    sent = pickle.loads(Path(self.ui._zini_payload_path).read_bytes())["snapshot"]
                    self.assertTrue(sent.mines_placed)
                    self.assertEqual(sent.mines, frozenset({(1, 1)}))
                    self.ui.on_left_click(0, 1)
                    self.ui.on_right_click(2, 2)
                    self.ui._poll_zini_metric_job()
                    popen.assert_called_once()
                process.wait.assert_not_called()
                self.assertEqual(sent, self.engine.get_board_snapshot())
                self.assertEqual(self.ui._stat_value_items["zini"].text(), "-")
                self.assertFalse(self.ui.zini_explorer_button.isEnabled())
                self.assertIsNone(self.ui.request_zini_explorer_trace())
                self.assertIsNone(self.ui._zini_explorer_window)

    def test_precomputed_result_is_silent_during_play_and_immediate_at_won_or_lost(self):
        for outcome in ("won", "lost"):
            with self.subTest(outcome=outcome):
                self.ui.on_reset()
                process = Mock()
                process.poll.return_value = None
                with (patch("core_engine.random.sample", return_value=[(1, 1)]),
                      patch("zini_metric_job.subprocess.Popen", return_value=process) as popen,
                      patch("zini_explorer.build_zini_trace") as build):
                    self.ui.on_left_click(0, 0)
                    popen.assert_called_once()
                    self.finish_result()
                    self.assertTrue(self.ui._zini_explorer.completed)
                    self.assertEqual(self.ui._current_zini_clicks(), self.result.clicks)
                    self.assertEqual(self.ui._stat_value_items["zini"].text(), "-")
                    self.assertFalse(self.ui.zini_explorer_button.isEnabled())
                    self.ui.on_open_zini_explorer()
                    self.assertIsNone(self.ui._zini_explorer_window)
                    self.assertIsNone(self.ui._zini_explorer.snapshot)
                    self.assertIsNone(self.ui._zini_explorer.moves)
                    self.ui.on_left_click(0, 1)
                    if outcome == "lost":
                        self.ui.on_left_click(1, 1)
                    else:
                        for y in range(3):
                            for x in range(3):
                                if (x, y) != (1, 1):
                                    self.ui.on_left_click(x, y)
                    self.assertEqual(self.engine.status, GameStatus.LOST if outcome == "lost" else GameStatus.WON)
                    self.assertEqual(self.ui._stat_value_items["zini"].text(), str(self.result.clicks))
                    self.assertTrue(self.ui.zini_explorer_button.isEnabled())
                    popen.assert_called_once()
                    build.assert_not_called()

    def test_live_precompute_reset_rejects_old_result_on_next_board(self):
        self.ui.on_reset()
        process = Mock()
        process.poll.return_value = None
        with (patch("core_engine.random.sample", return_value=[(1, 1)]),
              patch("zini_metric_job.subprocess.Popen", return_value=process)):
            self.ui.on_left_click(0, 0)
        self.assertIs(self.ui._zini_process, process)
        old_token = self.ui._zini_job_token
        paths = self.ui._zini_payload_path, self.ui._zini_result_path
        self.ui.on_reset()
        process.terminate.assert_called_once()
        self.assert_cleared(*paths)
        self.assert_invalidated()
        new_process = Mock()
        new_process.poll.return_value = None
        with (patch("core_engine.random.sample", return_value=[(1, 1)]),
              patch("zini_metric_job.subprocess.Popen", return_value=new_process)):
            self.ui.on_right_click(0, 0)
        self.assertGreater(self.ui._zini_job_token, old_token)
        stale = {"token": old_token, "clicks": 999, "moves": self.result.moves, "error": None}
        self.assertFalse(self.ui._zini_explorer.receive(stale, expected_token=old_token))
        self.assertFalse(self.ui._zini_explorer.receive(stale, expected_token=self.ui._zini_job_token))
        self.assertIsNone(self.ui._current_zini_clicks())
        self.assertEqual(self.ui._stat_value_items["zini"].text(), "-")
        self.assertFalse(self.ui.zini_explorer_button.isEnabled())

    def test_next_action_does_not_restart_exited_worker_before_result_poll(self):
        self.ui.on_reset()
        process = Mock()
        process.poll.return_value = None
        with (patch("core_engine.random.sample", return_value=[(1, 1)]),
              patch("zini_metric_job.subprocess.Popen", return_value=process) as popen):
            self.ui.on_left_click(0, 0)
            popen.assert_called_once()
            payload_path, result_path = self.ui._zini_payload_path, self.ui._zini_result_path
            write_result_atomic(result_path, {
                "token": self.ui._zini_job_token, "clicks": self.result.clicks,
                "moves": self.result.moves, "error": None,
            })
            process.poll.return_value = 0
            self.ui.on_left_click(0, 1)
            popen.assert_called_once()
            self.assertEqual(self.ui._zini_result_path, result_path)
            self.assertTrue(Path(result_path).is_file())
            process.wait.assert_not_called()
            self.ui._poll_zini_metric_job()
            self.assertEqual(self.ui._current_zini_clicks(), self.result.clicks)
            self.assert_cleared(payload_path, result_path)

    def test_frozen_launch_poll_and_cleanup(self):
        self.check_completed_launch(frozen=True)

    def check_completed_launch(self, frozen):
        self.engine.step(1, 1, Action.OPEN)
        process, payload_path, result_path = self.launch(frozen)
        with open(payload_path, "rb") as stream:
            payload = pickle.load(stream)
        self.assertEqual(payload["snapshot"], self.engine.get_board_snapshot())
        self.assertEqual(self.ui._zini_explorer.snapshot, payload["snapshot"])
        # An unfinished child is neither restarted nor reaped by polling.
        with patch("zini_metric_job.subprocess.Popen") as popen:
            self.ui._ensure_zini_metric_job()
            self.ui._poll_zini_metric_job()
        popen.assert_not_called()
        process.wait.assert_not_called()
        write_result_atomic(result_path, {
            "token": payload["token"], "clicks": self.result.clicks,
            "moves": self.result.moves, "error": None,
        })
        with patch("zini_explorer.build_zini_trace") as builder:
            self.ui._poll_zini_metric_job()
            self.ui._counter_metric_values()
        builder.assert_not_called()
        self.assertEqual(self.ui._current_zini_clicks(), 5)
        self.assertEqual(self.ui._zini_explorer.moves, self.result.moves)
        self.assertEqual(self.ui._zini_explorer.snapshot, payload["snapshot"])
        process.wait.assert_called_once_with(timeout=0.1)
        self.assert_cleared(payload_path, result_path)
        with patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as builder:
            trace = self.ui.request_zini_explorer_trace()
            self.assertIs(self.ui.request_zini_explorer_trace(), trace)
        builder.assert_called_once()
        self.assertEqual(trace.snapshot, payload["snapshot"])

    def test_reset_terminates_frozen_worker_and_cleans_files(self):
        process, payload_path, result_path = self.launch(frozen=True)
        token = self.ui._zini_job_token
        self.ui.on_reset()
        process.terminate.assert_called_once()
        self.assertGreater(self.ui._zini_job_token, token)
        self.assertIsNone(self.ui._current_zini_clicks())
        self.assert_cleared(payload_path, result_path)

    def test_stale_frozen_result_is_ignored(self):
        process, payload_path, result_path = self.launch(frozen=True)
        write_result_atomic(result_path, {
            "token": self.ui._zini_job_token - 1, "clicks": 999,
            "moves": None, "error": None,
        })
        self.ui._poll_zini_metric_job()
        self.assertIsNone(self.ui._current_zini_clicks())
        self.assert_cleared(payload_path, result_path)

    def test_failed_frozen_launch_cleans_files_and_stops_retrying(self):
        with (
            patch.object(sys, "frozen", True, create=True),
            patch("zini_metric_job.subprocess.Popen", side_effect=OSError("launch failed")) as popen,
            patch("builtins.print"),
        ):
            self.ui._ensure_zini_metric_job()
            self.ui._ensure_zini_metric_job()
        popen.assert_called_once()
        self.assertEqual(self.ui._zini_explorer.token, self.ui._zini_job_token)
        self.assertTrue(self.ui._zini_explorer.completed)
        self.assertIsNotNone(self.ui._zini_explorer.worker_error)
        self.assertIsNone(self.ui._current_zini_clicks())
        self.assert_cleared(*popen.call_args.args[0][-2:])

    def finish_result(self, **changes):
        payload = {
            "token": self.ui._zini_job_token, "clicks": self.result.clicks,
            "moves": self.result.moves, "error": None,
        }
        payload.update(changes)
        write_result_atomic(self.ui._zini_result_path, payload)
        self.ui._poll_zini_metric_job()
        return payload

    def assert_invalidated(self):
        controller = self.ui._zini_explorer
        self.assertIsNone(controller.token)
        self.assertIsNone(controller.snapshot)
        self.assertIsNone(controller.moves)
        self.assertIsNone(controller.trace)
        self.assertIsNone(controller.error)
        self.assertIsNone(self.ui._current_zini_clicks())
        self.assertIsNone(self.ui.request_zini_explorer_trace())

    def test_result_uses_sent_snapshot_without_reading_current_engine(self):
        self.engine.step(1, 1, Action.OPEN)
        _, payload_path, _ = self.launch(frozen=False)
        sent = pickle.loads(Path(payload_path).read_bytes())["snapshot"]
        # Simulate different engine contents at delivery; joining must use token data.
        self.engine.reset_with_mines(3, 3, 1, {(0, 0)})
        self.engine.step(0, 0, Action.OPEN)
        with patch.object(
            self.engine, "get_board_snapshot", side_effect=AssertionError("fresh snapshot"),
        ):
            self.finish_result()
            trace = self.ui.request_zini_explorer_trace()
        self.assertEqual(trace.snapshot, sent)
        self.assertNotEqual(trace.snapshot, self.engine.get_board_snapshot())

    def test_counters_do_not_build_or_search_again_and_trace_failure_keeps_clicks(self):
        self.engine.step(1, 1, Action.OPEN)
        self.launch(frozen=False)
        with (
            patch("zini_explorer.build_zini_trace", side_effect=RuntimeError("trace failed")) as builder,
            patch("zini_calculator.calculate_g_zini_neighborhood_beam_bounded") as search,
            patch("zini_metric_job.subprocess.Popen") as popen,
        ):
            self.finish_result()
            self.ui._update_statistics_panel(self.engine.get_stats())
            builder.assert_not_called()
            self.assertIsNone(self.ui.request_zini_explorer_trace())
            self.assertIsNone(self.ui.request_zini_explorer_trace())
            self.ui._update_statistics_panel(self.engine.get_stats())
            self.ui._ensure_zini_metric_job()
        builder.assert_called_once()
        search.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(self.ui._current_zini_clicks(), 5)
        self.assertEqual(self.ui._stat_value_items["zini"].text(), "5")
        self.assertIsNotNone(self.ui._zini_explorer.trace_error)
        self.assertIsNone(self.ui._zini_explorer.worker_error)

    def test_semantically_invalid_moves_fail_lazily_without_losing_counter(self):
        self.engine.step(1, 1, Action.OPEN)
        self.launch(frozen=False)
        moves = (replace(self.result.moves[0], premium=99), *self.result.moves[1:])
        self.finish_result(moves=moves)
        self.assertIsNone(self.ui._zini_explorer.error)
        self.assertIsNone(self.ui.request_zini_explorer_trace())
        self.assertEqual(self.ui._current_zini_clicks(), 5)
        self.assertIsNotNone(self.ui._zini_explorer.trace_error)

    def test_malformed_payloads_do_not_escape_poll_or_restart_search(self):
        cases = (
            None, [], 5, {},
            {"clicks": 5, "moves": None, "error": None},
            {"clicks": 5, "moves": (("click", 1, 0, 2, 1),), "error": None},
            {"clicks": True, "moves": self.result.moves, "error": None},
            {"clicks": 5, "moves": self.result.moves, "error": False},
        )
        self.engine.step(1, 1, Action.OPEN)
        for case in cases:
            with self.subTest(payload=case):
                self.ui._reset_zini_metric_job()
                _, payload_path, result_path = self.launch(frozen=False)
                payload = ({"token": self.ui._zini_job_token, **case}
                           if type(case) is dict else case)
                Path(result_path).write_bytes(pickle.dumps(payload))
                with patch("builtins.print"), patch("zini_metric_job.subprocess.Popen") as popen:
                    self.ui._poll_zini_metric_job()
                    self.ui._ensure_zini_metric_job()
                popen.assert_not_called()
                self.assertTrue(self.ui._zini_explorer.completed)
                self.assertIsNotNone(self.ui._zini_explorer.error)
                self.assertIsNone(self.ui.request_zini_explorer_trace())
                valid_counter = (type(case) is dict and type(case.get("clicks")) is int
                                 and case.get("error") is None)
                self.assertEqual(self.ui._current_zini_clicks(), 5 if valid_counter else None)
                self.assert_cleared(payload_path, result_path)

    def test_worker_failure_is_separate_from_trace_failure(self):
        self.engine.step(1, 1, Action.OPEN)
        self.launch(frozen=False)
        with patch("builtins.print"):
            self.finish_result(clicks=None, moves=None, error="ValueError('worker failed')")
        self.assertIsNone(self.ui._current_zini_clicks())
        self.assertIsNotNone(self.ui._zini_explorer.worker_error)
        self.assertIsNone(self.ui._zini_explorer.trace_error)

    def test_corrupt_pickle_and_exited_worker_are_terminal_failures(self):
        for corrupt in (True, False):
            with self.subTest(corrupt=corrupt):
                self.ui._reset_zini_metric_job()
                process, payload_path, result_path = self.launch(frozen=False)
                if corrupt:
                    Path(result_path).write_bytes(b"invalid pickle")
                else:
                    process.poll.return_value = 3
                    process.returncode = 3
                with patch("builtins.print"), patch("zini_metric_job.subprocess.Popen") as popen:
                    self.ui._poll_zini_metric_job()
                    self.ui._ensure_zini_metric_job()
                popen.assert_not_called()
                self.assertIsNotNone(self.ui._zini_explorer.worker_error)
                self.assertIsNone(self.ui._current_zini_clicks())
                self.assert_cleared(payload_path, result_path)

    def test_reset_board_change_and_close_invalidate_pending_or_built_trace(self):
        for action in (self.ui.on_reset, lambda: self.ui._rebuild_game(4, 3, 1), self.ui.close):
            for built in (False, True):
                with self.subTest(action=action, built=built):
                    self.ui._reset_zini_metric_job()
                    self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
                    self.engine.step(1, 1, Action.OPEN)
                    _, payload_path, result_path = self.launch(frozen=False)
                    old_token = self.ui._zini_job_token
                    if built:
                        old_result = self.finish_result()
                        self.assertIsNotNone(self.ui.request_zini_explorer_trace())
                    else:
                        old_result = {"token": old_token, "clicks": 5,
                                      "moves": self.result.moves, "error": None}
                    action()
                    self.assert_invalidated()
                    self.assert_cleared(payload_path, result_path)
                    self.assertFalse(self.ui._zini_explorer.receive(
                        old_result, expected_token=old_token,
                    ))
                    self.assert_invalidated()

    def test_live_information_gate_blocks_playing_and_allows_won_lost(self):
        self.ui.on_reset()
        self.assertIsNone(self.ui.request_zini_explorer_trace())
        self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.launch(frozen=False)
        self.finish_result()
        with patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as builder:
            self.assertIsNone(self.ui.request_zini_explorer_trace())
            self.assertIsNone(self.ui._zini_explorer.snapshot)
            self.assertIsNone(self.ui._zini_explorer.moves)
            builder.assert_not_called()
            self.engine.step(1, 1, Action.OPEN)
            trace = self.ui.request_zini_explorer_trace()
            self.assertIsNotNone(trace)
            # A live completed board may only expose while its current status is terminal.
            self.engine.status = GameStatus.PLAYING
            self.ui._update_statistics_panel(self.engine.get_stats())
            self.assertIsNone(self.ui._zini_explorer.trace)
            self.assertIsNone(self.ui.request_zini_explorer_trace())
            self.engine.status = GameStatus.WON
            self.assertIs(self.ui.request_zini_explorer_trace(), trace)
        builder.assert_called_once()

    def replay(self, outcome):
        cells = ([(0, 0)] if outcome == "pending" else
                 [(0, 0), (1, 1)] if outcome == "lost" else
                 [(x, y) for y in range(3) for x in range(3) if (x, y) != (1, 1)])
        return ReplayPlayer(ReplayData(
            board=ReplayBoard(width=3, height=3, num_mines=1, mine_positions={(1, 1)}),
            events=tuple(ReplayEvent(float(i + 1), x, y, ACTION_OPEN)
                         for i, (x, y) in enumerate(cells)),
        ))

    def test_completed_replay_allows_trace_at_first_middle_last_for_won_and_lost(self):
        for outcome in ("won", "lost"):
            with self.subTest(outcome=outcome):
                player = self.replay(outcome)
                process = Mock()
                process.poll.return_value = None
                with patch("zini_metric_job.subprocess.Popen", return_value=process):
                    self.ui._enter_replay_mode(player)
                self.assertTrue(self.ui._replay_counter_timeline.is_completed)
                with patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as builder:
                    self.finish_result()
                    builder.assert_not_called()
                    trace = self.ui.request_zini_explorer_trace()
                    for index in (0, player.event_count // 2, player.event_count):
                        player.go_to(index)
                        self.ui._refresh_replay_view_after_move()
                        self.assertTrue(self.ui._zini_explorer.eligible)
                        self.assertIs(self.ui.request_zini_explorer_trace(), trace)
                builder.assert_called_once()
                self.ui._exit_replay_mode()
                self.assert_invalidated()

    def test_replay_entry_exit_invalidates_old_session_and_incomplete_record_is_blocked(self):
        for built in (False, True):
            with self.subTest(built=built):
                self.engine.reset_with_mines(3, 3, 1, {(1, 1)})
                self.engine.step(1, 1, Action.OPEN)
                _, payload_path, result_path = self.launch(frozen=False)
                if built:
                    self.finish_result()
                    self.assertIsNotNone(self.ui.request_zini_explorer_trace())
                self.ui._enter_replay_mode(self.replay("pending"))
                self.assert_invalidated()
                self.assert_cleared(payload_path, result_path)
                self.assertFalse(self.ui._replay_counter_timeline.is_completed)
                # Even direct low-level job preparation cannot grant access.
                self.launch(frozen=False)
                self.finish_result()
                with patch("zini_explorer.build_zini_trace") as builder:
                    for index in (0, 1):
                        self.ui._replay_player.go_to(index)
                        self.ui._refresh_replay_view_after_move()
                        self.assertFalse(self.ui._zini_explorer.eligible)
                        self.assertIsNone(self.ui.request_zini_explorer_trace())
                builder.assert_not_called()
                self.ui._exit_replay_mode()
                self.assert_invalidated()

    def assert_cleared(self, payload_path, result_path):
        self.assertFalse(Path(payload_path).exists())
        self.assertFalse(Path(result_path).exists())
        self.assertIsNone(self.ui._zini_process)
        self.assertIsNone(self.ui._zini_payload_path)
        self.assertIsNone(self.ui._zini_result_path)
        self.assertFalse(self.ui._zini_poll_timer.isActive())


if __name__ == "__main__":
    unittest.main()
