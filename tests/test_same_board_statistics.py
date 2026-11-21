"""F-S3: Same-board statistics reuse the existing Replay statistics code.

Expected values come from the main window's Replay path (ReplayPlayer index and
current_time into ReplayStatisticsAnalyzer) and from an independent engine
replay for click counts; nothing is read back from same_board_statistics.
"""

import unittest
from unittest.mock import patch

from board_analyzer import analyze_board
from core_engine import Action, MinesweeperEngine
from replay_model import SOURCE_ALGORITHM, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from replay_statistics import STAT_KEYS, ReplayStatisticsAnalyzer
import same_board_statistics as statistics
from same_board_algorithms import AlgorithmRun, execute_algorithm, not_run, validate_run
from tests.test_same_board_algorithms import LOSS_BOARD, WIN_BOARD
from tests.test_same_board_runner import human_context


def main_window_replay_statistics(replay):
    """What the main window shows at the last Replay index (index mode)."""
    player = ReplayPlayer(replay)
    player.go_to(player.event_count)
    timeline = ReplayStatisticsAnalyzer.analyze(replay)
    return ReplayStatisticsAnalyzer.statistics_at(
        timeline=timeline, index=player.current_index, replay_time=player.current_time, board_zini=None)


def engine_clicks(board, moves):
    engine = MinesweeperEngine(board.width, board.height, board.num_mines)
    engine.reset_with_mines(board.width, board.height, board.num_mines, board.mine_positions)
    for move in moves:
        engine.step(move.x, move.y, Action[move.action])
    counters = engine.get_counter_snapshot()
    return counters["active_clicks"], counters["wasted_clicks"], engine.status.name


class SameBoardStatisticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = validate_run(WIN_BOARD, execute_algorithm("K_D23", WIN_BOARD))
        cls.loss = validate_run(LOSS_BOARD, execute_algorithm("K_P0", LOSS_BOARD))

    def test_labels_follow_the_main_statistics_keys(self):
        self.assertEqual(tuple(key for key, _ in statistics.STAT_LABELS), STAT_KEYS)
        self.assertEqual(statistics.TIME_KEYS, ("time", "est_time", "bbbv_per_sec", "cps"))

    def test_human_statistics_equal_existing_replay_statistics(self):
        for replay in (human_context(with_trace=True).human_replay,
                       human_context(prelude=True).human_replay,  # FLAG/CHORD and wasted clicks
                       human_context(mined_origin=True).human_replay,
                       ReplayData(WIN_BOARD, (ReplayEvent(1.5, 8, 0, "OPEN"),))):
            with self.subTest(events=len(replay.events)):
                expected = main_window_replay_statistics(replay)
                actual = statistics.human_statistics(replay)
                for key in STAT_KEYS:
                    if key in statistics.ZINI_KEYS:
                        self.assertEqual(actual[key], "—")
                    else:
                        self.assertEqual(actual[key], expected[key], key)
                self.assertEqual(actual["time"], f"{replay.events[-1].elapsed_time:.3f}")

    def test_algorithm_statistics_use_the_same_analyzer(self):
        calls = []
        real_analyze = ReplayStatisticsAnalyzer.analyze.__func__

        def spy(cls, replay):
            calls.append(replay)
            return real_analyze(cls, replay)

        with patch.object(ReplayStatisticsAnalyzer, "analyze", classmethod(spy)):
            stats = statistics.algorithm_statistics(WIN_BOARD, self.win)
        self.assertEqual(len(calls), 1)
        replay = calls[0]
        self.assertEqual(replay.source_type, SOURCE_ALGORITHM)
        self.assertEqual(replay.board, WIN_BOARD)
        self.assertEqual([(e.x, e.y, e.action) for e in replay.events],
                         [(m.x, m.y, m.action) for m in self.win.moves])
        expected = ReplayStatisticsAnalyzer.statistics_at(
            ReplayStatisticsAnalyzer.analyze(replay), len(replay.events), 0.0, None)
        for key in STAT_KEYS:
            if key not in statistics.TIME_KEYS + statistics.ZINI_KEYS:
                self.assertEqual(stats[key], expected[key], key)
        # Independent of the analyzer: engine counters and the board 3BV.
        active, wasted, status = engine_clicks(WIN_BOARD, self.win.moves)
        self.assertEqual(status, "WON")
        total_3bv = analyze_board(ReplayPlayer(replay).engine.get_board_snapshot()).total_3bv
        self.assertEqual(stats["bbbv"], f"{total_3bv}/{total_3bv}")
        self.assertEqual(stats["clicks"], str(active) if not wasted else f"{active} + {wasted}")
        self.assertEqual(stats["ioe"], f"{total_3bv / (active + wasted):.4f}")
        self.assertIn("FLAG", [m.action for m in self.win.moves])
        self.assertIn("CHORD", [m.action for m in self.win.moves])

    def test_time_items_are_dash_for_algorithms(self):
        stats = statistics.algorithm_statistics(WIN_BOARD, self.win)
        for key in statistics.TIME_KEYS + statistics.ZINI_KEYS:
            self.assertEqual(stats[key], "—", key)
        human = statistics.human_statistics(human_context(with_trace=True).human_replay)
        for key in ("time", "est_time", "bbbv_per_sec", "cps"):
            self.assertNotEqual(human[key], "—", key)

    def test_unfinished_runs_follow_existing_masking(self):
        masked = ReplayStatisticsAnalyzer.masked_statistics()
        playing = next(i for i, m in enumerate(self.win.moves) if m.status_after == "PLAYING")
        stopped = validate_run(WIN_BOARD, AlgorithmRun(
            "K_D23", "STOPPED", self.win.moves[:playing + 1], self.win.settings, "stopped"))
        self.assertTrue(stopped.playable)
        for run in (stopped, not_run("K_LC0", "LIMIT", "한도"), not_run("K_LC1", "CANCELLED", "취소"),
                    not_run("K_D23", "ERROR", "오류")):
            with self.subTest(outcome=run.outcome):
                stats = statistics.algorithm_statistics(WIN_BOARD, run)
                for key in STAT_KEYS:
                    expected = "—" if key in statistics.TIME_KEYS + statistics.ZINI_KEYS else masked[key]
                    self.assertEqual(stats[key], expected, key)
        # A loss is a finished game: it is computed, not masked.
        self.assertEqual(self.loss.outcome, "LOST")
        lost = statistics.algorithm_statistics(LOSS_BOARD, self.loss)
        self.assertNotEqual(lost["bbbv"], "-")
        self.assertEqual(lost["clicks"], main_window_replay_statistics(
            statistics.algorithm_replay(LOSS_BOARD, self.loss.moves))["clicks"])


if __name__ == "__main__":
    unittest.main()
