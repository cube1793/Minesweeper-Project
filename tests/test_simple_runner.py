"""Real-engine integration; hidden layouts are used only to arrange fixtures."""

import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from random import Random
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from replay_json import replay_data_from_dict, replay_data_to_dict
from replay_model import ReplayData, SOURCE_ALGORITHM
from replay_player import ReplayPlayer
from replay_recorder import ReplayRecorder
from simple_algorithm import InconsistentObservationError, SimpleMove
from simple_decision import DecisionKind, analyze_position
from simple_runner import SimpleRunnerError, StopReason, run_simple


H = CellState.HIDDEN.value
F = CellState.FLAGGED.value


class SimpleRunnerTests(unittest.TestCase):
    @staticmethod
    def engine_with_mines(width, height, mines):
        engine = MinesweeperEngine(width, height, len(mines))
        engine.reset_with_mines(width, height, len(mines), mines)
        return engine

    def run_traced(self, engine, *, accept_guesses=False):
        """Assert that analysis/step alternate, against the live public position."""
        trace = []
        decisions = []
        original_step = engine.step

        def analyze(observation, num_mines):
            self.assertEqual(engine.status, GameStatus.PLAYING)
            self.assertEqual(observation, engine.get_observation())
            self.assertEqual(num_mines, engine.num_mines)
            if trace:
                self.assertEqual(trace[-1][0], "step")
            decision = analyze_position(observation, num_mines)
            decisions.append(decision)
            trace.append(("analyze", deepcopy(observation)))
            return decision

        def step(x, y, action):
            self.assertEqual(engine.status, GameStatus.PLAYING)
            move = SimpleMove(action, x, y)
            if trace:
                self.assertEqual(trace[-1][0], "analyze")
                self.assertEqual(move, decisions[-1].move)
            else:
                self.assertTrue(all(value == H for row in engine.get_observation() for value in row))
                self.assertEqual(move, SimpleMove(Action.OPEN, 0, 0))
            result = original_step(x, y, action)
            trace.append(("step", move))
            return result

        with (
            patch("simple_runner.analyze_position", side_effect=analyze),
            patch.object(engine, "step", side_effect=step),
        ):
            result = run_simple(engine, accept_guesses=accept_guesses)

        self.assertEqual(result.moves, tuple(value for tag, value in trace if tag == "step"))
        self.assert_replay_moves(result)
        return result, decisions, trace

    def assert_replay_moves(self, result):
        self.assertEqual(result.replay_data.source_type, SOURCE_ALGORITHM)
        self.assertEqual(len(result.replay_data.events), len(result.moves))
        for event, move in zip(result.replay_data.events, result.moves):
            self.assertEqual((event.x, event.y, event.action), (move.x, move.y, move.action.name))

    def assert_replays_to_engine(self, result, engine):
        player = ReplayPlayer(result.replay_data)
        self.assertEqual(player.go_to(player.event_count), engine.get_observation())
        self.assertEqual(player.engine.status, result.status)
        self.assertEqual(player.engine.get_board_snapshot(), engine.get_board_snapshot())

    def test_fresh_random_game_opens_origin_without_analyzing_unopened_board(self):
        engine = MinesweeperEngine(4, 3, 3)
        with patch("core_engine.random.sample", side_effect=Random(23).sample):
            result, decisions, trace = self.run_traced(engine)

        self.assertEqual(result.moves[0], SimpleMove(Action.OPEN, 0, 0))
        self.assertTrue(result.started_from_hidden)
        self.assertNotIn((0, 0), result.replay_data.board.mine_positions)
        self.assertEqual(trace[0], ("step", result.moves[0]))
        if decisions:
            self.assertTrue(any(value != H for row in trace[1][1] for value in row))
        self.assert_replays_to_engine(result, engine)

    def test_fresh_fixed_board_first_open_is_in_moves_and_replay(self):
        engine = self.engine_with_mines(4, 1, {(1, 0)})

        result, _, trace = self.run_traced(engine)

        self.assertEqual(result.moves[0], SimpleMove(Action.OPEN, 0, 0))
        self.assertEqual(trace[1], ("analyze", [[1, H, H, H]]))
        first = result.replay_data.events[0]
        self.assertEqual((first.x, first.y, first.action), (0, 0, "OPEN"))

    def test_partially_opened_board_continues_at_its_current_position(self):
        engine = self.engine_with_mines(4, 1, {(1, 0)})
        engine.step(0, 0, Action.OPEN)

        result, _, trace = self.run_traced(engine)

        self.assertEqual(trace[0], ("analyze", [[1, H, H, H]]))
        self.assertEqual(result.moves[0], SimpleMove(Action.FLAG, 1, 0))
        self.assertNotIn(SimpleMove(Action.OPEN, 0, 0), result.moves)
        self.assertFalse(result.started_from_hidden)
        self.assertEqual(result.status, GameStatus.WON)

    def test_flag_only_start_uses_analysis_even_when_no_cell_has_been_opened(self):
        engine = self.engine_with_mines(3, 1, {(0, 0)})
        engine.step(0, 0, Action.FLAG)

        result, decisions, trace = self.run_traced(engine)

        self.assertEqual(trace[0], ("analyze", [[F, H, H]]))
        self.assertEqual(decisions[0].kind, DecisionKind.GLOBAL_CERTAINTY)
        self.assertEqual(result.moves[0], SimpleMove(Action.OPEN, 1, 0))
        self.assertFalse(result.started_from_hidden)
        self.assertEqual(result.stop_reason, StopReason.WON)

    def test_local_and_global_safe_decisions_execute_with_guesses_disabled(self):
        engine = self.engine_with_mines(4, 1, {(1, 0)})

        result, decisions, _ = self.run_traced(engine)

        self.assertEqual([decision.kind for decision in decisions], [
            DecisionKind.LOCAL_DETERMINISTIC,
            DecisionKind.GLOBAL_CERTAINTY,
            DecisionKind.LOCAL_DETERMINISTIC,
        ])
        self.assertEqual(result.moves, (
            SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 1, 0),
            SimpleMove(Action.OPEN, 2, 0), SimpleMove(Action.OPEN, 3, 0),
        ))
        self.assertEqual(result.stop_reason, StopReason.WON)
        self.assertIsNone(result.pending_decision)

    def test_global_mines_execute_before_guess_pause_with_guesses_disabled(self):
        engine = self.engine_with_mines(5, 1, {(0, 0), (3, 0), (4, 0)})
        engine.step(1, 0, Action.OPEN)

        result, decisions, trace = self.run_traced(engine)

        self.assertEqual(result.moves, (
            SimpleMove(Action.FLAG, 3, 0), SimpleMove(Action.FLAG, 4, 0),
        ))
        self.assertEqual([decision.kind for decision in decisions], [
            DecisionKind.GLOBAL_CERTAINTY, DecisionKind.GLOBAL_CERTAINTY,
            DecisionKind.PROBABILITY_GUESS,
        ])
        self.assertEqual(trace[-1], ("analyze", [[H, 1, H, F, F]]))
        self.assertEqual(result.status, GameStatus.PLAYING)
        self.assertEqual(result.stop_reason, StopReason.GUESS_REQUIRED)
        self.assertIs(result.pending_decision, decisions[-1])

    def test_guess_pause_preserves_local_moves_and_does_not_step_the_guess(self):
        engine = self.engine_with_mines(5, 1, {(1, 0), (2, 0)})

        result, decisions, _ = self.run_traced(engine, accept_guesses=False)

        self.assertEqual(result.moves, (
            SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 1, 0),
        ))
        self.assertEqual(result.status, GameStatus.PLAYING)
        self.assertEqual(engine.status, GameStatus.PLAYING)
        self.assertEqual(result.stop_reason, StopReason.GUESS_REQUIRED)
        self.assertIs(result.pending_decision, decisions[-1])
        self.assertEqual(result.pending_decision.move, SimpleMove(Action.OPEN, 2, 0))
        self.assertEqual(engine.get_observation()[0][2], H)
        self.assertEqual(
            {cell.probability for cell in result.pending_decision.probability_result.probabilities},
            {Fraction(1, 3)},
        )

    def test_existing_guess_position_can_pause_without_any_physical_action(self):
        engine = self.engine_with_mines(3, 1, {(0, 0)})
        engine.step(1, 0, Action.OPEN)

        result, decisions, _ = self.run_traced(engine)

        self.assertEqual(result.moves, ())
        self.assertEqual(result.replay_data.events, ())
        self.assertEqual(result.replay_data.board.mine_positions, {(0, 0)})
        self.assertEqual(result.stop_reason, StopReason.GUESS_REQUIRED)
        self.assertIs(result.pending_decision, decisions[0])

    def test_accepted_minimum_probability_guess_can_lose_after_local_certainty(self):
        engine = self.engine_with_mines(5, 1, {(1, 0), (2, 0)})

        result, decisions, trace = self.run_traced(engine, accept_guesses=True)

        self.assertEqual(result.moves, (
            SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 1, 0),
            SimpleMove(Action.OPEN, 2, 0),
        ))
        self.assertEqual(decisions[-1].kind, DecisionKind.PROBABILITY_GUESS)
        self.assertEqual(result.status, GameStatus.LOST)
        self.assertEqual(result.stop_reason, StopReason.LOST)
        self.assertIsNone(result.pending_decision)
        self.assertEqual(trace[-1], ("step", result.moves[-1]))
        self.assert_replays_to_engine(result, engine)

    def test_accepted_guess_can_continue_to_win(self):
        engine = self.engine_with_mines(5, 1, {(1, 0), (4, 0)})

        result, decisions, _ = self.run_traced(engine, accept_guesses=True)

        self.assertIn(DecisionKind.PROBABILITY_GUESS, [decision.kind for decision in decisions])
        self.assertEqual(result.status, GameStatus.WON)
        self.assertEqual(result.stop_reason, StopReason.WON)
        self.assertIsNone(result.pending_decision)
        self.assert_replays_to_engine(result, engine)

    def test_flag_is_followed_by_fresh_observation_and_global_analysis(self):
        engine = self.engine_with_mines(4, 1, {(1, 0)})

        _, decisions, trace = self.run_traced(engine)

        self.assertEqual(trace[2], ("step", SimpleMove(Action.FLAG, 1, 0)))
        self.assertEqual(trace[3], ("analyze", [[1, F, H, H]]))
        self.assertIsNone(decisions[0].probability_result)
        self.assertIsNotNone(decisions[1].probability_result)

    def test_multiple_certain_cells_are_reanalyzed_after_each_single_action(self):
        engine = self.engine_with_mines(3, 2, {(1, 0), (0, 1), (1, 1)})

        result, decisions, _ = self.run_traced(engine)

        self.assertEqual(result.moves[1:4], (
            SimpleMove(Action.FLAG, 1, 0), SimpleMove(Action.FLAG, 0, 1),
            SimpleMove(Action.FLAG, 1, 1),
        ))
        self.assertEqual(
            [len(decision.deterministic_result.mine_cells) for decision in decisions[:3]],
            [3, 2, 1],
        )
        self.assertEqual(len(decisions), len(result.moves) - 1)

    def test_first_open_win_stops_without_any_analysis(self):
        for width, height, mines in ((1, 1, set()), (3, 2, set()), (2, 1, {(1, 0)})):
            with self.subTest(size=(width, height)):
                engine = self.engine_with_mines(width, height, mines)
                with patch("simple_runner.analyze_position") as analyze:
                    result = run_simple(engine)

                analyze.assert_not_called()
                self.assertEqual(result.moves, (SimpleMove(Action.OPEN, 0, 0),))
                self.assertEqual(result.stop_reason, StopReason.WON)
                self.assert_replay_moves(result)

    def test_already_terminal_engines_receive_no_analysis_or_actions(self):
        for status, x, reason in (
            (GameStatus.WON, 0, StopReason.WON),
            (GameStatus.LOST, 1, StopReason.LOST),
        ):
            with self.subTest(status=status):
                engine = self.engine_with_mines(2, 1, {(1, 0)})
                engine.step(x, 0, Action.OPEN)
                original = engine.get_observation()
                with (
                    patch("simple_runner.analyze_position") as analyze,
                    patch.object(engine, "step") as step,
                ):
                    result = run_simple(engine, accept_guesses=True)

                analyze.assert_not_called()
                step.assert_not_called()
                self.assertEqual(engine.get_observation(), original)
                self.assertEqual(result.status, status)
                self.assertEqual(result.stop_reason, reason)
                self.assertEqual(result.moves, ())
                self.assertEqual(result.replay_data.events, ())
                self.assertIsNone(result.pending_decision)

    def test_replay_records_post_step_elapsed_time_then_captures_board_once(self):
        engine = self.engine_with_mines(4, 1, {(1, 0)})
        recorder = ReplayRecorder(4, 1, 1, SOURCE_ALGORITHM)
        trace = []
        stepped = []
        original_step = engine.step
        original_record = recorder.record_event
        original_capture = recorder.capture_board

        def step(x, y, action):
            result = original_step(x, y, action)
            stepped.append(SimpleMove(action, x, y))
            trace.append("step")
            return result

        def record(elapsed_time, x, y, action):
            self.assertEqual(trace[-1], "step")
            self.assertEqual(elapsed_time, 100.0 + len(stepped))
            trace.append("record")
            return original_record(elapsed_time, x, y, action)

        def capture(snapshot):
            self.assertEqual(trace[-1], "record")
            self.assertTrue(snapshot.mines_placed)
            trace.append("capture")
            return original_capture(snapshot)

        with (
            patch("simple_runner.ReplayRecorder", return_value=recorder) as constructor,
            patch.object(engine, "step", side_effect=step),
            patch.object(engine, "get_elapsed_time", side_effect=lambda: 100.0 + len(stepped)),
            patch.object(engine, "get_board_snapshot", wraps=engine.get_board_snapshot) as snapshot,
            patch.object(recorder, "record_event", side_effect=record),
            patch.object(recorder, "capture_board", side_effect=capture),
        ):
            result = run_simple(engine)

        constructor.assert_called_once_with(4, 1, 1, SOURCE_ALGORITHM)
        snapshot.assert_called_once_with()
        self.assertEqual(trace, ["step", "record", "capture"] + ["step", "record"] * 3)
        self.assertEqual([event.elapsed_time for event in result.replay_data.events], [101, 102, 103, 104])

    def test_partial_replay_round_trips_json_and_restores_playing_position(self):
        engine = self.engine_with_mines(5, 1, {(1, 0), (2, 0)})
        result = run_simple(engine)

        restored = replay_data_from_dict(replay_data_to_dict(result.replay_data))

        self.assertEqual(restored, result.replay_data)
        self.assertEqual(result.stop_reason, StopReason.GUESS_REQUIRED)
        self.assertEqual(result.status, GameStatus.PLAYING)
        self.assert_replays_to_engine(result, engine)

    def test_completed_replay_matches_every_intermediate_position_in_existing_player(self):
        engine = self.engine_with_mines(3, 2, {(1, 0), (0, 1), (1, 1)})
        result, _, trace = self.run_traced(engine)
        player = ReplayPlayer(result.replay_data)
        analyzed = [value for tag, value in trace if tag == "analyze"]

        for index, observation in enumerate(analyzed, start=1):
            self.assertEqual(player.go_to(index), observation)
        self.assert_replays_to_engine(result, engine)
        self.assertEqual(result.stop_reason, StopReason.WON)

    def test_continuation_replay_keeps_only_real_new_actions_and_can_join_prior_history(self):
        engine = self.engine_with_mines(5, 1, {(1, 0), (4, 0)})
        paused = run_simple(engine)

        continued = run_simple(engine, accept_guesses=True)

        self.assertTrue(paused.started_from_hidden)
        self.assertFalse(continued.started_from_hidden)
        self.assertEqual(continued.moves[0], paused.pending_decision.move)
        self.assertEqual(continued.stop_reason, StopReason.WON)
        self.assert_replay_moves(continued)
        combined = ReplayData(
            board=continued.replay_data.board,
            events=paused.replay_data.events + continued.replay_data.events,
            source_type=SOURCE_ALGORITHM,
        )
        player = ReplayPlayer(combined)
        self.assertEqual(player.go_to(player.event_count), engine.get_observation())
        self.assertEqual(player.engine.status, GameStatus.WON)
        # v1 alone has no earlier position: a suffix is explicitly a segment.
        suffix_player = ReplayPlayer(continued.replay_data)
        self.assertNotEqual(suffix_player.go_to(suffix_player.event_count), engine.get_observation())

    def test_identical_fixed_board_and_start_state_produce_identical_moves(self):
        for started in (False, True):
            with self.subTest(started=started):
                results = []
                for _ in range(3):
                    engine = self.engine_with_mines(5, 1, {(1, 0), (4, 0)})
                    if started:
                        engine.step(0, 0, Action.OPEN)
                    results.append(run_simple(engine, accept_guesses=True))
                self.assertTrue(all(result.moves == results[0].moves for result in results))
                self.assertTrue(all(result.stop_reason == results[0].stop_reason for result in results))

    def test_different_hidden_layouts_with_same_visible_start_have_same_pending_decision(self):
        results = []
        for mines in ({(0, 0)}, {(2, 0)}):
            engine = self.engine_with_mines(3, 1, mines)
            engine.step(1, 0, Action.OPEN)
            results.append(run_simple(engine))

        self.assertEqual(results[0].pending_decision, results[1].pending_decision)
        self.assertEqual(results[0].moves, results[1].moves)
        self.assertNotEqual(results[0].replay_data.board, results[1].replay_data.board)

    def test_snapshot_answer_data_is_only_sent_to_recorder_never_analyzer(self):
        engine = self.engine_with_mines(4, 1, {(1, 0)})
        # Deliberately different replay metadata must not influence any move.
        other_snapshot = self.engine_with_mines(4, 1, {(2, 0)}).get_board_snapshot()
        with patch.object(engine, "get_board_snapshot", return_value=other_snapshot):
            result, _, _ = self.run_traced(engine)

        self.assertEqual(result.moves, (
            SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 1, 0),
            SimpleMove(Action.OPEN, 2, 0), SimpleMove(Action.OPEN, 3, 0),
        ))
        self.assertEqual(result.replay_data.board.mine_positions, {(2, 0)})
        self.assertEqual(result.status, GameStatus.WON)

    def test_none_decision_while_playing_raises_explicit_runner_error(self):
        engine = self.engine_with_mines(3, 1, {(0, 0)})
        engine.step(1, 0, Action.OPEN)
        with (
            patch("simple_runner.analyze_position", return_value=None),
            patch.object(engine, "step") as step,
            self.assertRaisesRegex(SimpleRunnerError, "no move while PLAYING"),
        ):
            run_simple(engine)
        step.assert_not_called()

    def test_no_progress_action_raises_instead_of_looping(self):
        engine = self.engine_with_mines(4, 1, {(1, 0)})
        with (
            patch.object(engine, "step") as step,
            patch("simple_runner.analyze_position") as analyze,
            self.assertRaisesRegex(SimpleRunnerError, "no progress"),
        ):
            run_simple(engine)

        step.assert_called_once_with(0, 0, Action.OPEN)
        analyze.assert_not_called()

    def test_stale_flag_decision_cannot_toggle_a_flag_or_loop(self):
        engine = self.engine_with_mines(4, 1, {(1, 0)})
        engine.step(0, 0, Action.OPEN)
        stale = analyze_position(engine.get_observation(), engine.num_mines)
        with (
            patch("simple_runner.analyze_position", return_value=stale) as analyze,
            patch.object(engine, "step", wraps=engine.step) as step,
            self.assertRaisesRegex(SimpleRunnerError, "HIDDEN cell"),
        ):
            run_simple(engine)

        step.assert_called_once_with(1, 0, Action.FLAG)
        self.assertEqual(analyze.call_count, 2)
        self.assertEqual(engine.get_observation()[0][1], F)

    def test_invalid_selected_actions_are_rejected_without_step(self):
        engine = self.engine_with_mines(4, 1, {(1, 0)})
        engine.step(0, 0, Action.OPEN)
        decision = analyze_position(engine.get_observation(), engine.num_mines)
        for move in (
            SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.OPEN, -1, 0),
            SimpleMove(Action.FLAG, 4, 0), SimpleMove(Action.CHORD, 1, 0),
        ):
            with self.subTest(move=move):
                with (
                    patch("simple_runner.analyze_position", return_value=replace(decision, move=move)),
                    patch.object(engine, "step") as step,
                    self.assertRaisesRegex(SimpleRunnerError, "HIDDEN cell"),
                ):
                    run_simple(engine)
                step.assert_not_called()

    def test_inconsistent_visible_flags_propagate_solver_error(self):
        engine = self.engine_with_mines(3, 2, {(1, 1)})
        engine.step(0, 0, Action.OPEN)
        engine.step(1, 0, Action.FLAG)
        engine.step(0, 1, Action.FLAG)
        with (
            patch.object(engine, "step") as step,
            self.assertRaises(InconsistentObservationError),
        ):
            run_simple(engine, accept_guesses=True)
        step.assert_not_called()

    def test_impossible_global_flag_budget_raises_before_first_runner_action(self):
        engine = self.engine_with_mines(5, 1, {(1, 0)})
        engine.step(0, 0, Action.OPEN)
        engine.step(3, 0, Action.FLAG)
        engine.step(4, 0, Action.FLAG)
        original = engine.get_observation()
        counters = engine.get_counter_snapshot()
        self.assertEqual(original, [[1, H, H, F, F]])

        for accept_guesses in (False, True):
            with self.subTest(accept_guesses=accept_guesses):
                with (
                    patch.object(engine, "step", wraps=engine.step) as step,
                    self.assertRaisesRegex(InconsistentObservationError, "remaining_mines=-1"),
                ):
                    run_simple(engine, accept_guesses=accept_guesses)

                step.assert_not_called()
                self.assertEqual(engine.get_observation(), original)
                self.assertEqual(engine.get_counter_snapshot(), counters)
                self.assertEqual(engine.status, GameStatus.PLAYING)

    def test_run_result_is_immutable_and_copies_move_sequence(self):
        result = run_simple(self.engine_with_mines(4, 1, {(1, 0)}))
        moves = list(result.moves)
        copied = replace(result, moves=moves)
        moves.clear()

        self.assertEqual(copied, result)
        self.assertIsInstance(copied.moves, tuple)
        with self.assertRaises(FrozenInstanceError):
            copied.stop_reason = StopReason.LOST
        with self.assertRaises(FrozenInstanceError):
            copied.replay_data.events = ()

    def test_guess_policy_requires_boolean_before_touching_engine(self):
        engine = self.engine_with_mines(4, 1, {(1, 0)})
        with patch.object(engine, "step") as step:
            for value in (None, "False", 0, 1):
                with self.subTest(value=value):
                    with self.assertRaisesRegex(ValueError, "accept_guesses"):
                        run_simple(engine, accept_guesses=value)
        step.assert_not_called()


if __name__ == "__main__":
    unittest.main()
