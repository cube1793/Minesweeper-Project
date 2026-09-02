import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from board_analyzer import analyze_board
from core_engine import Action, CellState, GameStatus, MinesweeperEngine


class MinesweeperEngineRegressionTests(unittest.TestCase):
    def _engine_with_mines(self, width, height, mine_positions):
        engine = MinesweeperEngine(
            width=width,
            height=height,
            num_mines=len(mine_positions),
        )
        engine.reset_with_mines(
            width=width,
            height=height,
            num_mines=len(mine_positions),
            mine_positions=mine_positions,
        )
        return engine

    def assert_click_counts(self, engine, active=None, wasted=None):
        active = active or {}
        wasted = wasted or {}
        expected_active = {
            "total": 0,
            "left": 0,
            "right": 0,
            "chord": 0,
            **active,
        }
        expected_wasted = {
            "total": 0,
            "left": 0,
            "right": 0,
            "chord": 0,
            **wasted,
        }

        self.assertEqual(engine._active_clicks, expected_active)
        self.assertEqual(engine._wasted_clicks, expected_wasted)
        for counts in (engine._active_clicks, engine._wasted_clicks):
            self.assertEqual(
                counts["total"],
                counts["left"] + counts["right"] + counts["chord"],
            )

        counter_snapshot = engine.get_counter_snapshot()
        self.assertEqual(counter_snapshot["status"], engine.status)
        self.assertEqual(
            counter_snapshot["active_clicks"], engine._active_clicks["total"]
        )
        self.assertEqual(
            counter_snapshot["wasted_clicks"], engine._wasted_clicks["total"]
        )
        self.assertEqual(
            counter_snapshot["completed_3bv"], engine._effective_3bv
        )

    def assert_fresh_runtime_state(self, engine):
        self.assertEqual(engine.status, GameStatus.PLAYING)
        self.assertEqual(engine.get_elapsed_time(), 0.0)
        self.assertFalse(engine._timer_started)
        self.assertIsNone(engine._start_time)
        self.assertIsNone(engine._end_time)
        self.assertEqual(engine.count_flags(), 0)
        self.assertEqual(engine._exploded_cells, set())
        self.assertEqual(engine._opened_groups, set())
        self.assertEqual(engine._opened_isolated, set())
        self.assertEqual(engine._effective_3bv, 0)
        self.assertEqual(engine._effective_ops, 0)
        self.assert_click_counts(engine)

    def test_new_game_stats_and_snapshot_before_mines_are_placed(self):
        engine = MinesweeperEngine(width=9, height=9, num_mines=10)

        observation = engine.get_observation()
        self.assertEqual(len(observation), 9)
        self.assertTrue(
            all(
                value == CellState.HIDDEN.value
                for row in observation
                for value in row
            )
        )

        stats = engine.get_stats()
        self.assertEqual(stats["bbbv"], "-/-")
        self.assertEqual(stats["ops"], "-/-")
        self.assertEqual(stats["clicks"], "0")
        self.assertEqual(stats["left"], "0")
        self.assertEqual(stats["right"], "0")
        self.assertEqual(stats["chord"], "0")

        snapshot = engine.get_board_snapshot()
        self.assertEqual(snapshot.width, 9)
        self.assertEqual(snapshot.height, 9)
        self.assertEqual(snapshot.num_mines, 10)
        self.assertFalse(snapshot.mines_placed)
        self.assertEqual(snapshot.mines, frozenset())
        self.assertIsInstance(snapshot.mines, frozenset)
        self.assertIsInstance(snapshot.adjacent, tuple)
        self.assertTrue(all(isinstance(row, tuple) for row in snapshot.adjacent))
        self.assertTrue(
            all(value == 0 for row in snapshot.adjacent for value in row)
        )

        with self.assertRaises(FrozenInstanceError):
            snapshot.width = 99
        with self.assertRaises(AttributeError):
            snapshot.mines.add((0, 0))
        with self.assertRaises(TypeError):
            snapshot.adjacent[0][0] = 1

    def test_open_first_action_preserves_basic_flow_and_snapshot_copy(self):
        engine = MinesweeperEngine(width=9, height=9, num_mines=10)

        observation, reward, terminated, truncated, info = engine.step(
            4, 4, Action.OPEN
        )

        self.assertFalse(truncated)
        self.assertEqual(info["status"], engine.status)
        self.assertEqual(terminated, engine.status != GameStatus.PLAYING)
        self.assertIn(engine.status, (GameStatus.PLAYING, GameStatus.WON))
        self.assertEqual(reward, 1.0 if terminated else 0.01)
        self.assertEqual(info["stats"]["clicks"], "1")
        self.assertEqual(info["stats"]["left"], "1")
        self.assertEqual(info["stats"]["right"], "0")
        self.assertEqual(info["stats"]["chord"], "0")

        snapshot = engine.get_board_snapshot()
        self.assertTrue(snapshot.mines_placed)
        self.assertEqual(len(snapshot.mines), 10)
        self.assertEqual(len(snapshot.adjacent), 9)
        self.assertTrue(all(len(row) == 9 for row in snapshot.adjacent))

        analysis = analyze_board(snapshot)
        self.assertEqual(engine._total_3bv, analysis.total_3bv)
        self.assertEqual(engine._total_ops, analysis.total_ops)
        self.assertEqual(engine._opening_id, [list(row) for row in analysis.opening_id])
        self.assertEqual(
            engine._cell_class,
            [
                [None if cell_class is None else int(cell_class) for cell_class in row]
                for row in analysis.cell_class
            ],
        )

        safe_zone = {
            (x, y)
            for y in range(3, 6)
            for x in range(3, 6)
        }
        self.assertTrue(safe_zone.isdisjoint(snapshot.mines))
        self.assertEqual(snapshot.adjacent[4][4], 0)
        self.assertEqual(observation[4][4], 0)

        original_snapshot_mines = snapshot.mines
        original_snapshot_adjacent = snapshot.adjacent
        engine.reset()
        self.assertTrue(snapshot.mines_placed)
        self.assertEqual(snapshot.mines, original_snapshot_mines)
        self.assertEqual(snapshot.adjacent, original_snapshot_adjacent)
        self.assertFalse(engine.get_board_snapshot().mines_placed)

    def test_flag_first_action_preserves_counter_flow(self):
        engine = MinesweeperEngine(width=9, height=9, num_mines=10)

        _, _, terminated, truncated, info = engine.step(0, 0, Action.FLAG)

        self.assertFalse(terminated)
        self.assertFalse(truncated)
        self.assertEqual(engine.count_flags(), 1)
        self.assertEqual(info["status"], GameStatus.PLAYING)
        self.assertEqual(info["stats"]["clicks"], "1")
        self.assertEqual(info["stats"]["left"], "0")
        self.assertEqual(info["stats"]["right"], "1")
        self.assertEqual(info["stats"]["chord"], "0")
        self.assertTrue(engine.get_board_snapshot().mines_placed)

    def test_open_classifies_progress_and_repeat_click(self):
        engine = self._engine_with_mines(3, 3, {(1, 1)})

        observation, reward, terminated, truncated, info = engine.step(
            0, 0, Action.OPEN
        )

        self.assertEqual(observation[0][0], 1)
        self.assertEqual(reward, 0.01)
        self.assertFalse(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["status"], GameStatus.PLAYING)
        self.assert_click_counts(
            engine,
            active={"total": 1, "left": 1},
        )

        before_repeat = engine.get_observation()
        observation, reward, terminated, truncated, _ = engine.step(
            0, 0, Action.OPEN
        )

        self.assertEqual(observation, before_repeat)
        self.assertEqual(reward, 0.01)
        self.assertFalse(terminated)
        self.assertFalse(truncated)
        self.assert_click_counts(
            engine,
            active={"total": 1, "left": 1},
            wasted={"total": 1, "left": 1},
        )

    def test_open_on_flagged_cell_is_wasted_and_keeps_flag(self):
        engine = self._engine_with_mines(3, 3, {(1, 1)})
        engine.step(1, 1, Action.FLAG)

        observation, reward, terminated, truncated, info = engine.step(
            1, 1, Action.OPEN
        )

        self.assertEqual(observation[1][1], CellState.FLAGGED.value)
        self.assertNotIn((1, 1), engine._exploded_cells)
        self.assertEqual(engine.status, GameStatus.PLAYING)
        self.assertEqual(reward, 0.01)
        self.assertFalse(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["status"], GameStatus.PLAYING)
        self.assert_click_counts(
            engine,
            active={"total": 1, "right": 1},
            wasted={"total": 1, "left": 1},
        )

    def test_flag_on_mine_is_active_and_unflag_is_wasted(self):
        engine = self._engine_with_mines(3, 3, {(1, 1)})

        flagged, _, _, _, _ = engine.step(1, 1, Action.FLAG)
        self.assertEqual(flagged[1][1], CellState.FLAGGED.value)
        self.assert_click_counts(
            engine,
            active={"total": 1, "right": 1},
        )

        unflagged, reward, terminated, truncated, _ = engine.step(
            1, 1, Action.FLAG
        )
        self.assertEqual(unflagged[1][1], CellState.HIDDEN.value)
        self.assertEqual(reward, 0.01)
        self.assertFalse(terminated)
        self.assertFalse(truncated)
        self.assert_click_counts(
            engine,
            active={"total": 1, "right": 1},
            wasted={"total": 1, "right": 1},
        )

    def test_flag_on_safe_or_revealed_cell_is_wasted(self):
        with self.subTest(case="safe cell"):
            engine = self._engine_with_mines(3, 3, {(1, 1)})

            observation, reward, terminated, truncated, _ = engine.step(
                0, 0, Action.FLAG
            )

            self.assertEqual(observation[0][0], CellState.FLAGGED.value)
            self.assertEqual(reward, 0.01)
            self.assertFalse(terminated)
            self.assertFalse(truncated)
            self.assert_click_counts(
                engine,
                wasted={"total": 1, "right": 1},
            )

        with self.subTest(case="revealed cell"):
            engine = self._engine_with_mines(3, 3, {(1, 1)})
            engine.step(0, 0, Action.OPEN)
            before_flag = engine.get_observation()

            observation, reward, terminated, truncated, _ = engine.step(
                0, 0, Action.FLAG
            )

            self.assertEqual(observation, before_flag)
            self.assertEqual(engine.count_flags(), 0)
            self.assertEqual(reward, 0.01)
            self.assertFalse(terminated)
            self.assertFalse(truncated)
            self.assert_click_counts(
                engine,
                active={"total": 1, "left": 1},
                wasted={"total": 1, "right": 1},
            )

    def test_chord_guard_cases_are_wasted_without_board_progress(self):
        cases = []

        covered = self._engine_with_mines(3, 3, {(1, 1)})
        cases.append(("covered", covered, (0, 0)))

        zero = self._engine_with_mines(5, 3, {(2, 0), (2, 1), (2, 2)})
        zero.step(0, 1, Action.OPEN)
        self.assertEqual(zero.get_observation()[1][0], 0)
        cases.append(("zero", zero, (0, 1)))

        mismatch = self._engine_with_mines(3, 3, {(1, 1)})
        mismatch.step(0, 0, Action.OPEN)
        self.assertEqual(mismatch.get_observation()[0][0], 1)
        cases.append(("flag count mismatch", mismatch, (0, 0)))

        for case, engine, (x, y) in cases:
            with self.subTest(case=case):
                before_chord = engine.get_observation()
                before_active = dict(engine._active_clicks)
                before_wasted = dict(engine._wasted_clicks)

                observation, reward, terminated, truncated, _ = engine.step(
                    x, y, Action.CHORD
                )

                self.assertEqual(observation, before_chord)
                self.assertEqual(reward, 0.01)
                self.assertFalse(terminated)
                self.assertFalse(truncated)
                self.assertEqual(engine._active_clicks, before_active)
                self.assertEqual(
                    engine._wasted_clicks["total"],
                    before_wasted["total"] + 1,
                )
                self.assertEqual(
                    engine._wasted_clicks["chord"],
                    before_wasted["chord"] + 1,
                )
                self.assert_click_counts(
                    engine,
                    active={
                        key: value
                        for key, value in before_active.items()
                        if value
                    },
                    wasted={
                        **{
                            key: value
                            for key, value in before_wasted.items()
                            if value
                        },
                        "total": before_wasted["total"] + 1,
                        "chord": before_wasted["chord"] + 1,
                    },
                )

    def test_wrong_flag_chord_loses_but_continues_processing_targets(self):
        engine = self._engine_with_mines(3, 3, {(0, 0)})
        engine.step(1, 1, Action.OPEN)
        engine.step(0, 1, Action.FLAG)

        observation, reward, terminated, truncated, info = engine.step(
            1, 1, Action.CHORD
        )

        self.assertEqual(engine.status, GameStatus.LOST)
        self.assertEqual(observation[0][0], CellState.EXPLODED.value)
        self.assertEqual(observation[2][2], 0)
        self.assertTrue(engine._revealed[2][2])
        self.assertEqual(reward, -1.0)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["status"], GameStatus.LOST)
        self.assert_click_counts(
            engine,
            active={"total": 2, "left": 1, "chord": 1},
            wasted={"total": 1, "right": 1},
        )

    def test_invalid_coordinates_and_action_preserve_playing_state(self):
        engine = self._engine_with_mines(3, 3, {(1, 1)})
        with patch("core_engine.time.perf_counter", return_value=10.0) as clock:
            engine.step(0, 0, Action.OPEN)
            clock.return_value = 12.0
            before_observation = engine.get_observation()
            before_status = engine.status
            before_elapsed = engine.get_elapsed_time()
            before_counters = engine.get_counter_snapshot()
            before_active = dict(engine._active_clicks)
            before_wasted = dict(engine._wasted_clicks)
            before_timer = (
                engine._timer_started,
                engine._start_time,
                engine._end_time,
            )

            invalid_coordinates = ((-1, 0), (3, 0), (0, -1), (0, 3))
            for x, y in invalid_coordinates:
                with self.subTest(x=x, y=y):
                    observation, reward, terminated, truncated, info = engine.step(
                        x, y, Action.OPEN
                    )
                    self.assertEqual(observation, before_observation)
                    self.assertEqual(reward, 0.0)
                    self.assertFalse(terminated)
                    self.assertFalse(truncated)
                    self.assertEqual(set(info), {"invalid", "stats"})
                    self.assertIs(info["invalid"], True)

            observation, reward, terminated, truncated, info = engine.step(0, 0, 99)
            self.assertEqual(observation, before_observation)
            self.assertEqual(reward, 0.0)
            self.assertFalse(terminated)
            self.assertFalse(truncated)
            self.assertEqual(set(info), {"invalid_action", "stats"})
            self.assertIs(info["invalid_action"], True)

            self.assertEqual(engine.status, before_status)
            self.assertEqual(engine.get_observation(), before_observation)
            self.assertEqual(engine.get_elapsed_time(), before_elapsed)
            self.assertEqual(engine.get_counter_snapshot(), before_counters)
            self.assertEqual(engine._active_clicks, before_active)
            self.assertEqual(engine._wasted_clicks, before_wasted)
            self.assertEqual(
                (engine._timer_started, engine._start_time, engine._end_time),
                before_timer,
            )

    def test_invalid_action_and_standalone_chord_do_not_start_timer(self):
        with self.subTest(case="invalid action"):
            engine = self._engine_with_mines(3, 3, {(1, 1)})
            with patch("core_engine.time.perf_counter") as clock:
                _, reward, terminated, truncated, info = engine.step(0, 0, 99)

                clock.assert_not_called()
                self.assertEqual(reward, 0.0)
                self.assertFalse(terminated)
                self.assertFalse(truncated)
                self.assertEqual(set(info), {"invalid_action", "stats"})
                self.assert_fresh_runtime_state(engine)

        with self.subTest(case="standalone chord"):
            engine = self._engine_with_mines(3, 3, {(1, 1)})
            with patch("core_engine.time.perf_counter") as clock:
                _, reward, terminated, truncated, info = engine.step(
                    0, 0, Action.CHORD
                )

                clock.assert_not_called()
                self.assertEqual(reward, 0.01)
                self.assertFalse(terminated)
                self.assertFalse(truncated)
                self.assertEqual(info["status"], GameStatus.PLAYING)
                self.assertEqual(engine.get_elapsed_time(), 0.0)
                self.assertFalse(engine._timer_started)
                self.assertIsNone(engine._start_time)
                self.assertIsNone(engine._end_time)
                self.assert_click_counts(
                    engine,
                    wasted={"total": 1, "chord": 1},
                )

    def test_first_open_or_flag_starts_timer(self):
        cases = (
            ("open", Action.OPEN, (0, 0)),
            ("flag", Action.FLAG, (1, 1)),
        )
        for case, action, (x, y) in cases:
            with self.subTest(case=case):
                engine = self._engine_with_mines(3, 3, {(1, 1)})
                with patch(
                    "core_engine.time.perf_counter", return_value=100.0
                ) as clock:
                    engine.step(x, y, action)

                    self.assertTrue(engine._timer_started)
                    self.assertEqual(engine._start_time, 100.0)
                    self.assertIsNone(engine._end_time)
                    clock.return_value = 103.25
                    self.assertEqual(engine.get_elapsed_time(), 3.25)

    def test_terminal_timer_freezes_and_reset_returns_it_to_zero(self):
        engine = self._engine_with_mines(3, 3, {(1, 1)})
        with patch("core_engine.time.perf_counter", return_value=10.0) as clock:
            engine.step(0, 0, Action.OPEN)
            clock.return_value = 15.0
            engine.step(1, 1, Action.OPEN)

            self.assertEqual(engine.status, GameStatus.LOST)
            self.assertEqual(engine.get_elapsed_time(), 5.0)
            self.assertEqual(engine._end_time, 15.0)
            clock.return_value = 999.0
            self.assertEqual(engine.get_elapsed_time(), 5.0)

            observation = engine.reset()

            self.assertTrue(
                all(
                    value == CellState.HIDDEN.value
                    for row in observation
                    for value in row
                )
            )
            self.assertEqual(engine.get_elapsed_time(), 0.0)
            self.assertFalse(engine._timer_started)
            self.assertIsNone(engine._start_time)
            self.assertIsNone(engine._end_time)

    def test_win_reward_and_remaining_mine_auto_flag(self):
        engine = self._engine_with_mines(2, 1, {(1, 0)})

        observation, reward, terminated, truncated, info = engine.step(
            0, 0, Action.OPEN
        )

        self.assertEqual(engine.status, GameStatus.WON)
        self.assertEqual(
            observation,
            [[1, CellState.FLAGGED.value]],
        )
        self.assertEqual(engine.count_flags(), 1)
        self.assertEqual(reward, 1.0)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["status"], GameStatus.WON)
        self.assert_click_counts(
            engine,
            active={"total": 1, "left": 1},
        )

    def test_loss_reward_and_observation_cell_states(self):
        engine = self._engine_with_mines(5, 2, {(0, 0), (2, 0), (4, 0)})
        engine.step(2, 0, Action.FLAG)
        engine.step(1, 1, Action.FLAG)

        observation, reward, terminated, truncated, info = engine.step(
            0, 0, Action.OPEN
        )

        self.assertEqual(engine.status, GameStatus.LOST)
        self.assertEqual(observation[0][0], CellState.EXPLODED.value)
        self.assertEqual(observation[0][2], CellState.FLAGGED.value)
        self.assertEqual(observation[0][4], CellState.MINE.value)
        self.assertEqual(observation[1][1], CellState.FALSE_FLAG.value)
        self.assertEqual(reward, -1.0)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["status"], GameStatus.LOST)
        self.assert_click_counts(
            engine,
            active={"total": 2, "left": 1, "right": 1},
            wasted={"total": 1, "right": 1},
        )

    def test_step_after_terminal_preserves_state_and_response_contract(self):
        engine = self._engine_with_mines(3, 3, {(1, 1)})
        with patch("core_engine.time.perf_counter", return_value=10.0) as clock:
            engine.step(0, 0, Action.OPEN)
            clock.return_value = 15.0
            engine.step(1, 1, Action.OPEN)

            before_observation = engine.get_observation()
            before_counters = engine.get_counter_snapshot()
            before_active = dict(engine._active_clicks)
            before_wasted = dict(engine._wasted_clicks)
            before_elapsed = engine.get_elapsed_time()
            before_stats = engine.get_stats()
            clock.return_value = 999.0

            terminal_inputs = (
                (0, 0, Action.OPEN),
                (1, 1, Action.FLAG),
                (-1, -1, 99),
            )
            for x, y, action in terminal_inputs:
                with self.subTest(x=x, y=y, action=action):
                    observation, reward, terminated, truncated, info = engine.step(
                        x, y, action
                    )
                    self.assertEqual(observation, before_observation)
                    self.assertEqual(reward, 0.0)
                    self.assertTrue(terminated)
                    self.assertFalse(truncated)
                    self.assertEqual(
                        info,
                        {"status": GameStatus.LOST, "stats": before_stats},
                    )

            self.assertEqual(engine.status, GameStatus.LOST)
            self.assertEqual(engine.get_observation(), before_observation)
            self.assertEqual(engine.get_counter_snapshot(), before_counters)
            self.assertEqual(engine._active_clicks, before_active)
            self.assertEqual(engine._wasted_clicks, before_wasted)
            self.assertEqual(engine.get_elapsed_time(), before_elapsed)

    def test_reset_clears_progress_runtime_and_analysis_state(self):
        engine = self._engine_with_mines(3, 3, {(1, 1)})
        with patch("core_engine.time.perf_counter", return_value=10.0):
            engine.step(0, 0, Action.OPEN)
            engine.step(1, 1, Action.FLAG)
        self.assertGreater(engine._total_3bv, 0)

        observation = engine.reset()

        self.assertTrue(
            all(
                value == CellState.HIDDEN.value
                for row in observation
                for value in row
            )
        )
        self.assert_fresh_runtime_state(engine)
        snapshot = engine.get_board_snapshot()
        self.assertFalse(snapshot.mines_placed)
        self.assertEqual(snapshot.mines, frozenset())
        self.assertTrue(
            all(value == 0 for row in snapshot.adjacent for value in row)
        )
        self.assertEqual(engine._total_3bv, 0)
        self.assertEqual(engine._total_ops, 0)
        self.assertTrue(
            all(value == -1 for row in engine._opening_id for value in row)
        )
        self.assertTrue(
            all(value is None for row in engine._cell_class for value in row)
        )

    def test_reset_with_mines_clears_lost_state_before_new_layout(self):
        engine = self._engine_with_mines(5, 2, {(0, 0), (2, 0), (4, 0)})
        with patch("core_engine.time.perf_counter", return_value=10.0):
            engine.step(2, 0, Action.FLAG)
            engine.step(1, 1, Action.FLAG)
            engine.step(0, 0, Action.OPEN)
        self.assertEqual(engine.status, GameStatus.LOST)

        new_mines = {(3, 0), (3, 1)}
        observation = engine.reset_with_mines(
            width=4,
            height=2,
            num_mines=2,
            mine_positions=new_mines,
        )

        self.assertEqual(engine.width, 4)
        self.assertEqual(engine.height, 2)
        self.assertEqual(engine.num_mines, 2)
        self.assertTrue(
            all(
                value == CellState.HIDDEN.value
                for row in observation
                for value in row
            )
        )
        self.assert_fresh_runtime_state(engine)
        snapshot = engine.get_board_snapshot()
        self.assertTrue(snapshot.mines_placed)
        self.assertEqual(snapshot.mines, frozenset(new_mines))
        analysis = analyze_board(snapshot)
        self.assertEqual(engine._total_3bv, analysis.total_3bv)
        self.assertEqual(engine._total_ops, analysis.total_ops)
        self.assertEqual(engine._opening_id, [list(row) for row in analysis.opening_id])
        self.assertEqual(
            engine._cell_class,
            [
                [None if cell_class is None else int(cell_class) for cell_class in row]
                for row in analysis.cell_class
            ],
        )


if __name__ == "__main__":
    unittest.main()
