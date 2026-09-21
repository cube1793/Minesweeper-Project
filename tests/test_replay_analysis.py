"""Stage 2-5 public-only analysis, comparison and replay ownership contracts."""

import unittest
from copy import deepcopy
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus
from live_analysis import first_click_presentation, present_decision
from replay_analysis import (
    ReplayComparisonKind as Kind, analyze_replay_step, compare_replay_action,
)
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from simple_algorithm import InconsistentObservationError, InferenceResult, SimpleMove
from simple_decision import DecisionKind, SimpleDecision, analyze_position
from simple_probability import CellProbability, ProbabilityResult

H, F = CellState.HIDDEN, CellState.FLAGGED


def event(action="OPEN", x=0, y=0, time=1.0):
    return ReplayEvent(time, x, y, action)


def analyze_player(player):
    # This adapter is deliberately limited to the public boundary.
    return analyze_replay_step(
        player.get_observation(), player.engine.num_mines,
        current_index=player.current_index, events=player.replay_data.events,
        status=player.engine.status,
    )


class ReplayAnalysisTests(unittest.TestCase):
    def player(self):
        return ReplayPlayer(ReplayData(
            ReplayBoard(3, 3, 1, {(1, 1)}),
            (event(), event("FLAG", 1, 1, 2), event("FLAG", 1, 1, 3)),
        ))

    def test_index_uses_current_observation_and_next_unapplied_event(self):
        player = self.player()
        for index in range(1, player.event_count + 1):
            with self.subTest(index=index):
                player.go_to(index)
                observation = player.get_observation()
                with patch("replay_analysis.analyze_position", wraps=analyze_position) as analyze:
                    result = analyze_player(player)
                analyze.assert_called_once_with(observation, 1)
                self.assertEqual(result.current_index, index)
                self.assertIs(result.next_event, player.replay_data.events[index]
                              if index < player.event_count else None)

    def test_solver_finishes_before_next_event_is_read(self):
        observation = [[1, H], [H, H]]
        completed = []

        class Events:
            def __len__(self):
                return 1

            def __getitem__(self, index):
                self_test.assertEqual(completed, [True])
                self_test.assertEqual(index, 0)
                return event(x=1)

        self_test = self

        def solve(obs, mines):
            result = analyze_position(obs, mines)
            completed.append(True)
            return result

        with patch("replay_analysis.analyze_position", side_effect=solve) as analyze:
            result = analyze_replay_step(observation, 1, current_index=0,
                                         events=Events(), status=GameStatus.PLAYING)
        analyze.assert_called_once_with(observation, 1)
        self.assertIsNotNone(result.presentation.move)

    def test_first_click_on_reconstructed_fixed_board_never_reads_snapshot(self):
        player = self.player()
        self.assertTrue(player.engine.get_board_snapshot().mines_placed)
        with (
            patch.object(player.engine, "get_board_snapshot", side_effect=AssertionError("hidden snapshot")),
            patch.object(ReplayBoard, "mine_positions", create=True, new=property(
                lambda _: self.fail("hidden layout"))),
            patch("replay_analysis.analyze_position") as analyze,
        ):
            result = analyze_player(player)
        analyze.assert_not_called()
        self.assertEqual(result.presentation, first_click_presentation())
        self.assertEqual(result.comparison_kind, Kind.EXACT_RECOMMENDATION)

    def test_first_click_other_open_is_different_not_equivalent(self):
        result = analyze_replay_step([[H, H]], 1, current_index=0,
                                     events=(event(x=1),), status=GameStatus.PLAYING)
        self.assertEqual(result.comparison_kind, Kind.DIFFERENT)
        self.assertIn("추천과 다름", result.status_text)
        self.assertNotRegex(result.status_text, "오답|실수|나쁜 수")

    def test_flag_unflag_all_hidden_after_index_zero_uses_real_probability(self):
        player = ReplayPlayer(ReplayData(
            ReplayBoard(3, 3, 1, {(1, 1)}),
            (event("FLAG", 1, 1), event("FLAG", 1, 1, 2)),
        ))
        player.go_to(2)
        with patch("replay_analysis.analyze_position", wraps=analyze_position) as analyze:
            result = analyze_player(player)
        analyze.assert_called_once_with([[H] * 3 for _ in range(3)], 1)
        self.assertEqual(result.presentation.decision.kind, DecisionKind.PROBABILITY_GUESS)
        self.assertNotIn("첫 클릭", result.status_text)

    def test_normal_analysis_never_reads_snapshot_layout_or_executes_actions(self):
        player = self.player()
        player.next()
        with (
            patch.object(player.engine, "get_board_snapshot", side_effect=AssertionError("snapshot")),
            patch.object(player.engine, "step", side_effect=AssertionError("action")),
            patch.object(ReplayBoard, "mine_positions", create=True, new=property(
                lambda _: self.fail("hidden layout"))),
            patch("replay_analysis.analyze_position", wraps=analyze_position) as analyze,
        ):
            result = analyze_player(player)
        analyze.assert_called_once_with(player.get_observation(), 1)
        self.assertIsNotNone(result.presentation)

    def test_different_hidden_layouts_with_identical_public_state_match(self):
        results = []
        for mine in ((1, 0), (0, 1), (1, 1)):
            player = ReplayPlayer(ReplayData(ReplayBoard(2, 2, 1, {mine}), (event(),)))
            player.next()
            results.append(analyze_player(player))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    def test_next_event_changes_only_comparison_not_recommendation(self):
        results = [analyze_replay_step(
            [[1, H], [H, H]], 1, current_index=0, events=(actual,), status=GameStatus.PLAYING,
        ) for actual in (event(x=1), event("FLAG", 1, 1), event("CHORD"))]
        self.assertTrue(all(result.presentation == results[0].presentation for result in results))

    def local_presentation(self):
        return present_decision([[H] * 5], SimpleDecision(
            DecisionKind.LOCAL_DETERMINISTIC, SimpleMove(Action.FLAG, 2, 0), (),
            InferenceResult({(0, 0), (1, 0)}, {(2, 0), (3, 0)}), None,
        ))

    def test_exact_requires_both_action_and_coordinate(self):
        presentation = self.local_presentation()
        self.assertEqual(compare_replay_action([[H] * 5], presentation, event("FLAG", 2)),
                         Kind.EXACT_RECOMMENDATION)
        self.assertEqual(compare_replay_action([[H] * 5], presentation, event("OPEN", 2)),
                         Kind.DIFFERENT)

    def test_other_safe_open_and_mine_flag_are_equivalent(self):
        presentation = self.local_presentation()
        for actual in (event("OPEN", 1), event("FLAG", 3)):
            self.assertEqual(compare_replay_action([[H] * 5], presentation, actual),
                             Kind.EQUIVALENT_CANDIDATE)

    def test_other_minimum_risk_open_is_equivalent(self):
        result = analyze_replay_step([[1, H], [H, H]], 1, current_index=0,
                                     events=(event(x=1, y=1),), status=GameStatus.PLAYING)
        self.assertEqual(result.presentation.decision.kind, DecisionKind.PROBABILITY_GUESS)
        self.assertEqual(result.comparison_kind, Kind.EQUIVALENT_CANDIDATE)
        self.assertIn("동등한 최소 위험 후보", result.status_text)

    def test_global_certainties_support_other_zero_open_and_hundred_flag(self):
        probabilities = ProbabilityResult(1, tuple(
            CellProbability((x, 0), int(x >= 2), 1) for x in range(4)
        ), (), ())
        decision = SimpleDecision(DecisionKind.GLOBAL_CERTAINTY, SimpleMove(Action.OPEN, 0, 0),
                                  (), InferenceResult((), ()), probabilities)
        for actual in (event(x=1), event("FLAG", 3)):
            with patch("replay_analysis.analyze_position", return_value=decision):
                result = analyze_replay_step([[H] * 4], 2, current_index=1,
                                             events=(event(), actual), status=GameStatus.PLAYING)
            self.assertEqual(result.comparison_kind, Kind.EQUIVALENT_CANDIDATE)
            self.assertIn("동등한 확정", result.status_text)

    def test_unknown_or_wrong_action_for_evidence_is_different(self):
        for actual in (event(x=4), event("FLAG", 1), event("OPEN", 3)):
            self.assertEqual(compare_replay_action([[H] * 5], self.local_presentation(), actual),
                             Kind.DIFFERENT)

    def test_chord_unflag_and_nonhidden_actions_are_unsupported(self):
        for actual in (event("CHORD"), event("FLAG", 1), event("OPEN", 1),
                       event("OPEN", 2), event("FLAG", 2), event(x=9)):
            with self.subTest(actual=actual):
                self.assertEqual(compare_replay_action([[H, F, 1]], first_click_presentation(), actual),
                                 Kind.UNSUPPORTED_ACTUAL)

    def test_unflag_status_retains_physical_event_and_explains_toggle(self):
        result = analyze_replay_step([[1, F], [H, H]], 1, current_index=0,
                                     events=(event("FLAG", 1),), status=GameStatus.PLAYING)
        self.assertEqual(result.comparison_kind, Kind.UNSUPPORTED_ACTUAL)
        self.assertIn("FLAG (UNFLAG)", result.status_text)
        self.assertIn("Simple Algorithm 비교 대상 아님", result.status_text)

    def test_final_incomplete_position_keeps_recommendation_without_next(self):
        player = self.player()
        player.go_to(player.event_count)
        result = analyze_player(player)
        self.assertIsNotNone(result.presentation.move)
        self.assertIsNone(result.next_event)
        self.assertEqual(result.comparison_kind, Kind.NO_NEXT_ACTION)
        self.assertIn("다음 실제 수 없음", result.status_text)

    def test_terminal_with_trailing_events_never_analyzes(self):
        for status in (GameStatus.WON, GameStatus.LOST):
            with patch("replay_analysis.analyze_position") as analyze:
                result = analyze_replay_step([[H]], 0, current_index=0,
                                             events=(event(),), status=status)
            analyze.assert_not_called()
            self.assertIsNone(result.presentation)
            self.assertEqual(result.status_text, "게임 종료")

    def test_local_certainty_does_not_add_probability_or_reselect_move(self):
        with patch("simple_decision.calculate_probabilities") as probabilities:
            result = analyze_replay_step([[1, F], [H, H]], 1, current_index=0,
                                         events=(event(x=1, y=1),), status=GameStatus.PLAYING)
        probabilities.assert_not_called()
        self.assertEqual(result.presentation.decision.kind, DecisionKind.LOCAL_DETERMINISTIC)
        self.assertEqual(result.comparison_kind, Kind.EQUIVALENT_CANDIDATE)

    def test_repeated_analysis_preserves_all_input_and_player_state(self):
        player = self.player()
        player.next()
        engine = player.engine
        observation = player.get_observation()
        before = deepcopy((observation, player.replay_data, engine.get_counter_snapshot(),
                           engine.get_board_snapshot(), player.current_index))
        for _ in range(3):
            analyze_replay_step(observation, 1, current_index=player.current_index,
                                events=player.replay_data.events, status=engine.status)
        self.assertIs(player.engine, engine)
        self.assertEqual((observation, player.replay_data, engine.get_counter_snapshot(),
                          engine.get_board_snapshot(), player.current_index), before)

    def test_public_contradictions_propagate_without_mutation(self):
        observation = [[1, F], [F, H]]
        before = deepcopy(observation)
        with self.assertRaises(InconsistentObservationError):
            analyze_replay_step(observation, 1, current_index=0,
                                events=(), status=GameStatus.PLAYING)
        self.assertEqual(observation, before)

    def test_invalid_index_is_rejected_without_solver(self):
        for index in (-1, 2, True, 0.5):
            with patch("replay_analysis.analyze_position") as analyze:
                with self.assertRaises(ValueError):
                    analyze_replay_step([[H]], 0, current_index=index,
                                        events=(event(),), status=GameStatus.PLAYING)
            analyze.assert_not_called()


if __name__ == "__main__":
    unittest.main()
