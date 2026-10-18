"""Bounded synthetic fixed boards and recorded inputs; no solver/evidence runs."""

import ast
from collections import Counter
import copy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction
import inspect
import unittest
from unittest.mock import patch

from board_analyzer import analyze_board
from board_snapshot import BoardSnapshot
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
import benchmark_modeled_time as modeled
import exemplar_board_reconstruction as reconstruction
from telemetry_model import ActionEvent, GameRecord, InferenceCategory
from timeline_analytics import project_timeline


def fixed_board(width, height, mines):
    engine = MinesweeperEngine()
    engine.reset_with_mines(width, height, len(mines), mines)
    return engine.get_board_snapshot()


def event(index, action, x, y, safe=0, flag=0, status=GameStatus.PLAYING, **metadata):
    values = dict(
        action_index=index, action_type=action, x=x, y=y,
        status_after=status, safe_cells_opened_delta=safe, explicit_flag_delta=flag,
        inference_category=None, selection_candidate_count=None,
        target_mine_probability=None, minimum_available_mine_probability=None,
        decision_compute_ns=None,
    )
    values.update(metadata)
    return ActionEvent(**values)


class ExemplarBoardReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluation = modeled.authenticate_model_c()

    def timeline(self, board, events, result="WIN", **record_changes):
        """Only fixture summaries are derived; public effects are explicit inputs."""
        counts = Counter(item.action_type for item in events)
        categories = Counter(item.inference_category for item in events)
        guesses = [item.action_index for item in events
                   if item.inference_category == InferenceCategory.PROBABILITY_GUESS]
        times = [item.decision_compute_ns for item in events if item.decision_compute_ns is not None]
        analysis = analyze_board(board)
        values = dict(
            game_index=0, seed=0, board_fingerprint="synthetic-not-authenticated-here",
            first_click_x=0, first_click_y=0, result=result,
            total_actions=len(events), open_count=counts[Action.OPEN],
            flag_count=counts[Action.FLAG], chord_count=counts[Action.CHORD],
            local_deterministic_count=categories[InferenceCategory.LOCAL_DETERMINISTIC],
            global_certainty_count=categories[InferenceCategory.GLOBAL_CERTAINTY],
            probability_guess_count=len(guesses), had_probability_guess=bool(guesses),
            first_guess_action_index=guesses[0] if guesses else None,
            board_3bv=analysis.total_3bv, board_ops=analysis.total_ops,
            compute_time_total_ns=sum(times), compute_time_max_ns=max(times, default=None),
        )
        values.update(record_changes)
        return project_timeline(
            GameRecord(**values), events, width=board.width, height=board.height,
            evaluation=self.evaluation,
        )

    def win(self):
        board = fixed_board(3, 3, {(1, 1)})
        events = (
            event(0, Action.OPEN, 0, 0, safe=1),
            event(1, Action.FLAG, 1, 1, flag=1),
            event(2, Action.CHORD, 0, 0, safe=2),
            event(3, Action.OPEN, 2, 0, safe=1),
            event(4, Action.CHORD, 2, 0, safe=1),
            event(5, Action.OPEN, 0, 2, safe=1),
            event(6, Action.CHORD, 0, 2, safe=1),
            event(7, Action.OPEN, 2, 2, safe=1, status=GameStatus.WON),
        )
        return board, self.timeline(board, events)

    def loss(self):
        board = fixed_board(4, 3, {(1, 0), (3, 0), (3, 2)})
        events = (
            event(0, Action.OPEN, 0, 0, safe=1),
            event(1, Action.FLAG, 3, 2, flag=1),
            event(2, Action.FLAG, 0, 1, flag=1),
            event(3, Action.OPEN, 1, 0, status=GameStatus.LOST),
        )
        return board, self.timeline(board, events, "LOSS")

    def flood_clear(self):
        board = fixed_board(4, 3, {(1, 0)})
        events = (
            event(0, Action.OPEN, 0, 0, safe=1),
            event(1, Action.FLAG, 3, 2, flag=1),
            event(2, Action.OPEN, 3, 1, safe=10, status=GameStatus.WON),
        )
        return board, self.timeline(board, events)

    def test_win_frames_match_every_direct_engine_prefix(self):
        board, timeline = self.win()
        result = reconstruction.reconstruct_board(board, timeline)
        self.assertEqual(len(result.frames), len(timeline.actions) + 1)
        self.assertEqual(result.frames[0].status, GameStatus.PLAYING)
        self.assertEqual(result.frames[0].observation, ((CellState.HIDDEN,) * 3,) * 3)
        engine = MinesweeperEngine()
        engine.reset_with_mines(board.width, board.height, board.num_mines, board.mines)
        for ordinal, item in enumerate(timeline.actions, 1):
            engine.step(item.event.x, item.event.y, item.event.action_type)
            self.assertEqual(result.frames[ordinal].observation,
                             tuple(tuple(row) for row in engine.get_observation()))
            self.assertEqual(result.frames[ordinal].status, engine.status)
        self.assertEqual(result.frames[-1].status, GameStatus.WON)

    def test_exact_safe_sets_before_after_and_same_target_chord(self):
        board, timeline = self.win()
        result = reconstruction.reconstruct_board(board, timeline)
        self.assertEqual(result.newly_revealed_safe_by_action, (
            frozenset({(0, 0)}), frozenset(), frozenset({(1, 0), (0, 1)}),
            frozenset({(2, 0)}), frozenset({(2, 1)}), frozenset({(0, 2)}),
            frozenset({(1, 2)}), frozenset({(2, 2)}),
        ))
        self.assertEqual(result.frames[4].observation[1][2], CellState.HIDDEN)
        self.assertEqual(result.frames[5].observation[1][2], 1)
        self.assertEqual((timeline.actions[4].dx, timeline.actions[4].dy), (0, 0))
        self.assertGreater(timeline.actions[4].modeled_action_us, 0)

    def test_terminal_loss_public_feedback_and_pre_loss_frame(self):
        board, timeline = self.loss()
        result = reconstruction.reconstruct_board(board, timeline)
        before, after = result.frames[-2:]
        self.assertEqual(before.status, GameStatus.PLAYING)
        self.assertEqual(before.observation[0][1], CellState.HIDDEN)
        self.assertEqual(before.observation[1][0], CellState.FLAGGED)
        self.assertEqual(after.status, GameStatus.LOST)
        self.assertEqual(after.observation[0][1], CellState.EXPLODED)
        self.assertEqual(after.observation[0][3], CellState.MINE)
        self.assertEqual(after.observation[1][0], CellState.FALSE_FLAG)
        self.assertEqual(after.observation[2][3], CellState.FLAGGED)
        self.assertEqual(after.observation[0][0], 1)
        self.assertEqual(after.observation[2][0], CellState.HIDDEN)
        self.assertEqual(result.newly_revealed_safe_by_action[-1], frozenset())

    def test_losing_chord_continues_safe_reveals_after_explosion(self):
        board = fixed_board(3, 3, {(1, 0)})
        events = (
            event(0, Action.OPEN, 0, 0, safe=1),
            event(1, Action.FLAG, 0, 1, flag=1),
            event(2, Action.CHORD, 0, 0, safe=1, status=GameStatus.LOST),
        )
        result = reconstruction.reconstruct_board(board, self.timeline(board, events, "LOSS"))
        self.assertEqual(result.newly_revealed_safe_by_action[-1], frozenset({(1, 1)}))
        self.assertEqual(result.frames[-1].observation[0][1], CellState.EXPLODED)
        self.assertEqual(result.frames[-1].observation[1][0], CellState.FALSE_FLAG)
        self.assertEqual(result.frames[-1].observation[1][1], 1)

    def test_automatic_win_flags_do_not_create_events_or_explicit_effects(self):
        board = fixed_board(3, 3, {(2, 2)})
        timeline = self.timeline(board, (event(0, Action.OPEN, 0, 0, safe=8, status=GameStatus.WON),))
        result = reconstruction.reconstruct_board(board, timeline)
        self.assertEqual(len(result.frames), 2)
        self.assertEqual(result.frames[-1].observation[2][2], CellState.FLAGGED)
        self.assertEqual(timeline.actions[0].event.explicit_flag_delta, 0)
        self.assertEqual(result.final_counters.right_text, "0")
        self.assertEqual(result.final_counters.active_clicks, 1)
        self.assertNotIn((2, 2), result.newly_revealed_safe_by_action[0])

    def test_flood_clears_safe_flag_and_counts_it_as_new_safe(self):
        board, timeline = self.flood_clear()
        result = reconstruction.reconstruct_board(board, timeline)
        self.assertEqual(result.frames[2].observation[2][3], CellState.FLAGGED)
        self.assertEqual(result.frames[3].observation[2][3], 0)
        self.assertIn((3, 2), result.newly_revealed_safe_by_action[2])
        self.assertEqual(len(result.newly_revealed_safe_by_action[2]), 10)
        self.assertEqual(timeline.actions[2].event.explicit_flag_delta, 0)
        self.assertEqual(result.frames[-1].observation[0][1], CellState.FLAGGED)
        self.assertEqual(result.final_counters.right_text, "0 + 1")

    def test_zero_mine_fixed_board_and_static_references(self):
        board = fixed_board(2, 2, set())
        timeline = self.timeline(board, (event(0, Action.OPEN, 0, 0, safe=4, status=GameStatus.WON),))
        result = reconstruction.reconstruct_board(board, timeline)
        self.assertEqual(result.board_reference, reconstruction.BoardReferenceMetrics(1, 1, 0))
        self.assertEqual(result.frames[-1].observation, ((0, 0), (0, 0)))

    def test_board_reference_uses_analyzer_without_spatial_overlays(self):
        board, timeline = self.win()
        with patch.object(reconstruction, "analyze_board", wraps=analyze_board) as analyze:
            result = reconstruction.reconstruct_board(board, timeline)
        analyze.assert_called_once_with(board)
        self.assertEqual(result.board_reference, reconstruction.BoardReferenceMetrics(8, 0, 8))
        self.assertEqual({f.name for f in fields(result.board_reference)},
                         {"total_3bv", "total_ops", "isolated_number_count"})

    def test_final_public_counter_summary_matches_direct_engine(self):
        for fixture in (self.win, self.loss, self.flood_clear):
            with self.subTest(fixture=fixture.__name__):
                board, timeline = fixture()
                result = reconstruction.reconstruct_board(board, timeline)
                engine = MinesweeperEngine()
                engine.reset_with_mines(board.width, board.height, board.num_mines, board.mines)
                for item in timeline.actions:
                    engine.step(item.event.x, item.event.y, item.event.action_type)
                snapshot, stats = engine.get_counter_snapshot(), engine.get_stats()
                for name in ("status", "active_clicks", "wasted_clicks", "completed_3bv"):
                    self.assertEqual(getattr(result.final_counters, name), snapshot[name])
                for name in ("bbbv", "ops", "clicks", "left", "right", "chord"):
                    self.assertEqual(getattr(result.final_counters, name + "_text"), stats[name])
                self.assertEqual(snapshot["active_clicks"] + snapshot["wasted_clicks"],
                                 timeline.record.total_actions)

    def test_frame_counters_match_public_engine_at_every_prefix(self):
        for fixture in (self.win, self.loss, self.flood_clear):
            with self.subTest(fixture=fixture.__name__):
                board, timeline = fixture()
                result = reconstruction.reconstruct_board(board, timeline)
                self.assertEqual(len(result.frame_counters), len(timeline.actions) + 1)
                self.assertEqual(result.frame_counters[0], reconstruction.FrameCounterSummary(
                    GameStatus.PLAYING, 0, 0, 0, 0, "0", "0", "0", "0"))
                engine = MinesweeperEngine()
                engine.reset_with_mines(board.width, board.height, board.num_mines, board.mines)
                for index, captured in enumerate(result.frame_counters):
                    if index:
                        event = timeline.actions[index - 1].event
                        engine.step(event.x, event.y, event.action_type)
                    raw, stats = engine.get_counter_snapshot(), engine.get_stats()
                    for name in ("status", "active_clicks", "wasted_clicks", "completed_3bv", "completed_ops"):
                        self.assertEqual(getattr(captured, name), raw[name])
                    for name in ("clicks", "left", "right", "chord"):
                        self.assertEqual(getattr(captured, name + "_text"), stats[name])
                    self.assertEqual(captured.status, result.frames[index].status)
                    self.assertEqual(captured.active_clicks + captured.wasted_clicks, index)

    def test_prefix_open_flag_chord_clicks_and_3bv_progress(self):
        result = reconstruction.reconstruct_board(*self.win())
        self.assertEqual(tuple(item.completed_3bv for item in result.frame_counters),
                         (0, 1, 1, 3, 4, 5, 6, 7, 8))
        self.assertEqual(tuple(item.completed_ops for item in result.frame_counters), (0,) * 9)
        for index, item in enumerate(result.frame_counters):
            self.assertEqual(item.clicks_text, str(index))
        self.assertEqual(tuple((item.left_text, item.right_text, item.chord_text)
                               for item in result.frame_counters), (
            ("0", "0", "0"), ("1", "0", "0"), ("1", "1", "0"),
            ("1", "1", "1"), ("2", "1", "1"), ("2", "1", "2"),
            ("3", "1", "2"), ("3", "1", "3"), ("4", "1", "3"),
        ))

    def test_prefix_ops_and_wasted_clicks_keep_terminal_formatting(self):
        result = reconstruction.reconstruct_board(*self.flood_clear())
        self.assertEqual(tuple(item.completed_3bv for item in result.frame_counters), (0, 1, 1, 2))
        self.assertEqual(tuple(item.completed_ops for item in result.frame_counters), (0, 0, 0, 1))
        self.assertEqual(tuple((item.active_clicks, item.wasted_clicks)
                               for item in result.frame_counters), ((0, 0), (1, 0), (1, 1), (2, 1)))
        self.assertEqual(result.frame_counters[2].clicks_text, "2")
        self.assertEqual(result.frame_counters[2].right_text, "1")
        self.assertEqual(result.frame_counters[-1].clicks_text, "2 + 1")
        self.assertEqual(result.frame_counters[-1].right_text, "0 + 1")

    def test_terminal_frame_counter_reconciles_with_final_compatibility_summary(self):
        for fixture in (self.win, self.loss, self.flood_clear):
            with self.subTest(fixture=fixture.__name__):
                result = reconstruction.reconstruct_board(*fixture())
                current, final = result.frame_counters[-1], result.final_counters
                for name in ("status", "active_clicks", "wasted_clicks", "completed_3bv",
                             "clicks_text", "left_text", "right_text", "chord_text"):
                    self.assertEqual(getattr(current, name), getattr(final, name))
                self.assertEqual(final.bbbv_text,
                                 f"{current.completed_3bv}/{result.board_reference.total_3bv}")
                self.assertEqual(final.ops_text,
                                 f"{current.completed_ops}/{result.board_reference.total_ops}")

    def test_counter_timeline_captured_in_single_replay_without_extra_inputs(self):
        board, timeline = self.win()
        step = MinesweeperEngine.step
        inputs = []

        def record_step(engine, x, y, action):
            inputs.append((x, y, action))
            return step(engine, x, y, action)

        with patch.object(MinesweeperEngine, "step", new=record_step):
            result = reconstruction.reconstruct_board(board, timeline)
        self.assertEqual(inputs, [(item.event.x, item.event.y, item.event.action_type)
                                  for item in timeline.actions])
        self.assertEqual(len(result.frame_counters), len(inputs) + 1)

    def test_summary_retains_no_time_rates_extra_raw_breakdowns_or_zini(self):
        board, timeline = self.loss()
        result = reconstruction.reconstruct_board(board, timeline)
        self.assertEqual({f.name for f in fields(result.final_counters)}, {
            "status", "active_clicks", "wasted_clicks", "completed_3bv",
            "bbbv_text", "ops_text", "clicks_text", "left_text", "right_text", "chord_text",
        })
        self.assertEqual(result.final_counters.clicks_text, "3 + 1")
        self.assertEqual(result.final_counters.left_text, "2")
        self.assertEqual(result.final_counters.right_text, "1 + 1")
        self.assertEqual({f.name for f in fields(result.frame_counters[0])}, {
            "status", "active_clicks", "wasted_clicks", "completed_3bv", "completed_ops",
            "clicks_text", "left_text", "right_text", "chord_text",
        })

    def test_reconstruction_clock_does_not_change_published_values(self):
        board, timeline = self.win()
        with patch("core_engine.time.perf_counter", return_value=10):
            first = reconstruction.reconstruct_board(board, timeline)
        with patch("core_engine.time.perf_counter", side_effect=range(100, 1000)):
            second = reconstruction.reconstruct_board(board, timeline)
        self.assertEqual(first, second)

    def test_unplaced_and_wrong_board_types_rejected(self):
        board, timeline = self.win()
        for invalid in (None, object(), replace(board, mines_placed=False), replace(board, mines_placed=1)):
            with self.subTest(board=invalid), self.assertRaisesRegex(ValueError, "finalized BoardSnapshot"):
                reconstruction.reconstruct_board(invalid, timeline)

    def test_invalid_dimensions_mine_count_and_coordinates_rejected(self):
        board, timeline = self.win()
        changes = (
            dict(width=0), dict(height=True), dict(width=3.0), dict(num_mines=-1),
            dict(num_mines=9), dict(num_mines=2), dict(mines={(9, 0)}),
            dict(mines={(True, 0)}), dict(mines={(0, 0, 0)}),
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                reconstruction.reconstruct_board(replace(board, **change), timeline)

    def test_inconsistent_adjacency_shape_or_value_rejected_before_replay(self):
        board, timeline = self.win()
        for adjacent in ((), ((1,),), ((0, 0, 0),) * 3,
                         ((True, 1, 1), *board.adjacent[1:]),
                         ((1.0, 1, 1), *board.adjacent[1:])):
            with self.subTest(adjacent=adjacent), \
                    patch.object(MinesweeperEngine, "step", side_effect=AssertionError("must not replay")), \
                    self.assertRaisesRegex(ValueError, "BoardSnapshot adjacency/layout"):
                reconstruction.reconstruct_board(replace(board, adjacent=adjacent), timeline)

    def test_board_metric_disagreement_rejected(self):
        board, timeline = self.win()
        for field in ("board_3bv", "board_ops"):
            changed = replace(timeline, record=replace(timeline.record, **{field: 99}))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                reconstruction.reconstruct_board(board, changed)

    def test_target_outside_supplied_board_rejected(self):
        board, timeline = self.win()
        events = tuple(item.event for item in timeline.actions)
        events = (events[0], replace(events[1], x=5), *events[2:])
        # Valid timeline for a larger dimension, but not for this fixed board.
        wider = project_timeline(timeline.record, events, width=6, height=3, evaluation=self.evaluation)
        with self.assertRaisesRegex(ValueError, "outside the supplied board"):
            reconstruction.reconstruct_board(board, wider)

    def test_safe_reveal_disagreement_rejected(self):
        board, timeline = self.win()
        events = tuple(item.event for item in timeline.actions)
        changed = self.timeline(board, (replace(events[0], safe_cells_opened_delta=2), *events[1:]))
        with self.assertRaisesRegex(ValueError, "safe reveal delta"):
            reconstruction.reconstruct_board(board, changed)

    def test_incompatible_explicit_flag_metadata_rejected(self):
        board, timeline = self.win()
        events = tuple(item.event for item in timeline.actions)
        for index, delta in ((0, 1), (1, 0), (1, -1), (2, 1), (2, -1)):
            modified = list(events)
            modified[index] = replace(modified[index], explicit_flag_delta=delta)
            with self.subTest(index=index, delta=delta), self.assertRaisesRegex(ValueError, "explicit_flag_delta"):
                reconstruction.reconstruct_board(board, self.timeline(board, tuple(modified)))

    def test_flag_on_revealed_target_rejected(self):
        board, timeline = self.win()
        events = [item.event for item in timeline.actions]
        events[1] = replace(events[1], x=0, y=0)
        with self.assertRaisesRegex(ValueError, "FLAG target must be HIDDEN"):
            reconstruction.reconstruct_board(board, self.timeline(board, tuple(events)))

    def test_unflag_cannot_be_disguised_as_positive_flag(self):
        board, timeline = self.win()
        events = [item.event for item in timeline.actions]
        events[2] = replace(events[2], action_type=Action.FLAG, x=1, y=1,
                            explicit_flag_delta=1, safe_cells_opened_delta=0)
        with self.assertRaisesRegex(ValueError, "UNFLAG is unsupported"):
            reconstruction.reconstruct_board(board, self.timeline(board, tuple(events)))

    def test_false_terminal_outcome_in_structurally_valid_timeline_rejected(self):
        board, timeline = self.loss()
        events = tuple(item.event for item in timeline.actions)
        changed = self.timeline(board, (*events[:-1], replace(events[-1], status_after=GameStatus.WON)))
        with self.assertRaisesRegex(ValueError, "status_after"):
            reconstruction.reconstruct_board(board, changed)

    def test_premature_engine_terminal_rejected(self):
        board = fixed_board(3, 3, {(2, 2)})
        events = (event(0, Action.OPEN, 0, 0, safe=8),
                  event(1, Action.OPEN, 1, 0, status=GameStatus.WON))
        with self.assertRaisesRegex(ValueError, "Action 1 reconstructed status"):
            reconstruction.reconstruct_board(board, self.timeline(board, events))

    def test_post_terminal_input_is_never_executed(self):
        board, timeline = self.win()
        # Deliberately corrupt an otherwise validated timeline at this local boundary.
        extra = replace(timeline.actions[-1], event=replace(timeline.actions[-1].event, action_index=8))
        changed = replace(timeline, actions=(*timeline.actions, extra), record=replace(
            timeline.record, total_actions=9, open_count=5))
        applied = []
        step = MinesweeperEngine.step

        def record_step(engine, x, y, action):
            applied.append((x, y, action))
            return step(engine, x, y, action)

        with patch.object(MinesweeperEngine, "step", new=record_step), \
                self.assertRaisesRegex(ValueError, "follows terminal"):
            reconstruction.reconstruct_board(board, changed)
        self.assertEqual(len(applied), 8)

    def test_final_record_outcome_mismatch_rejected(self):
        board, timeline = self.win()
        changed = replace(timeline, record=replace(timeline.record, result="LOSS"))
        with self.assertRaisesRegex(ValueError, "Final reconstructed outcome"):
            reconstruction.reconstruct_board(board, changed)

    def test_incomplete_nonterminal_stream_rejected(self):
        board, timeline = self.win()
        changed = replace(timeline, actions=timeline.actions[:-1], record=replace(
            timeline.record, total_actions=7, open_count=3))
        with self.assertRaisesRegex(ValueError, "Final reconstructed outcome"):
            reconstruction.reconstruct_board(board, changed)

    def test_invalid_timeline_container_and_count_rejected(self):
        board, timeline = self.win()
        for invalid in (None, object(), replace(timeline, record=None),
                        replace(timeline, actions=()), replace(timeline, actions=list(timeline.actions)),
                        replace(timeline, actions=timeline.actions[:-1])):
            with self.subTest(timeline=type(invalid)), self.assertRaises(ValueError):
                reconstruction.reconstruct_board(board, invalid)

    def test_malformed_items_enums_and_order_rejected(self):
        board, timeline = self.win()
        item = timeline.actions[1]
        invalid = (None, replace(item, event=None),
                   replace(item, event=replace(item.event, action_type=1)),
                   replace(item, event=replace(item.event, status_after=0)),
                   replace(item, event=replace(item.event, action_index=0)),
                   replace(item, event=replace(item.event, action_index=3)))
        for bad in invalid:
            changed = replace(timeline, actions=(timeline.actions[0], bad, *timeline.actions[2:]))
            with self.subTest(item=bad), self.assertRaises(ValueError):
                reconstruction.reconstruct_board(board, changed)

    def test_original_objects_exact_fraction_and_nullable_metadata_retained(self):
        board, timeline = self.win()
        events = [item.event for item in timeline.actions]
        probability = Fraction(10**100 + 1, 3 * 10**100)
        events[-1] = replace(events[-1], inference_category=InferenceCategory.PROBABILITY_GUESS,
                             target_mine_probability=probability,
                             minimum_available_mine_probability=Fraction(1, 3),
                             selection_candidate_count=None, decision_compute_ns=0)
        timeline = self.timeline(board, tuple(events))
        before = copy.deepcopy((board, timeline))
        result = reconstruction.reconstruct_board(board, timeline)
        self.assertIs(result.board_snapshot, board)
        self.assertIs(result.timeline, timeline)
        self.assertEqual((board, timeline), before)
        for item, original in zip(result.timeline.actions, events):
            self.assertIs(item.event, original)
        self.assertIs(result.timeline.actions[-1].event.target_mine_probability, probability)
        self.assertIsNone(result.timeline.actions[-1].event.selection_candidate_count)
        self.assertEqual(result.timeline.actions[-1].event.decision_compute_ns, 0)
        self.assertIsNone(result.timeline.actions[0].event.decision_compute_ns)
        self.assertEqual(result, reconstruction.reconstruct_board(board, timeline))

    def test_outputs_and_nested_storage_are_immutable_with_no_engine(self):
        result = reconstruction.reconstruct_board(*self.win())
        for value in (result, result.frames[0], result.frame_counters[0],
                      result.board_reference, result.final_counters):
            with self.subTest(type=type(value)), self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)
        with self.assertRaises(TypeError):
            result.frames[0].observation[0][0] = 9
        with self.assertRaises(TypeError):
            result.frames[0] = result.frames[-1]
        with self.assertRaises(TypeError):
            result.frame_counters[0] = result.frame_counters[-1]
        with self.assertRaises(AttributeError):
            result.newly_revealed_safe_by_action[0].add((2, 2))

        def check(value):
            self.assertNotIsInstance(value, (MinesweeperEngine, list, dict, set))
            if is_dataclass(value):
                for field in fields(value):
                    check(getattr(value, field.name))
            elif isinstance(value, (tuple, frozenset)):
                for item in value:
                    check(item)
        check(result)

    def test_failure_publishes_no_result_and_leaves_inputs_unchanged(self):
        board, timeline = self.win()
        changed = replace(timeline.actions[-1], event=replace(
            timeline.actions[-1].event, safe_cells_opened_delta=2))
        timeline = replace(timeline, actions=(*timeline.actions[:-1], changed))
        before = copy.deepcopy((board, timeline))
        with patch.object(reconstruction, "ExemplarBoardReconstruction") as publish, \
                self.assertRaisesRegex(ValueError, "safe reveal delta"):
            reconstruction.reconstruct_board(board, timeline)
        publish.assert_not_called()
        self.assertEqual((board, timeline), before)

    def test_no_model_reevaluation_database_or_random_board_generation(self):
        board, timeline = self.win()
        with patch("timeline_analytics.project_timeline", side_effect=AssertionError("reevaluation")), \
                patch("benchmark_modeled_time.reconstruct_game", side_effect=AssertionError("reevaluation")), \
                patch("stage3_physical.load_timing_table", side_effect=AssertionError("authentication")), \
                patch("stage3_physical.action_cost", side_effect=AssertionError("second cost authority")), \
                patch("sqlite3.connect", side_effect=AssertionError("database")), \
                patch("core_engine.random.sample", side_effect=AssertionError("random board")):
            result = reconstruction.reconstruct_board(board, timeline)
        self.assertIs(result.timeline, timeline)

    def test_source_has_only_narrow_dependencies_and_public_engine_access(self):
        tree = ast.parse(inspect.getsource(reconstruction))
        forbidden = {
            "PyQt5", "PyQt6", "PySide2", "PySide6", "ui_manager", "sqlite3",
            "telemetry_repository", "benchmark_board", "representative_boards",
            "simple_decision", "simple_runner", "stage3_planner", "stage3_runner",
            "stage3_execution", "replay_model", "replay_player",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                names = []
            for name in names:
                self.assertNotIn(name.split(".")[0], forbidden)
                self.assertFalse(name.startswith("zini"))
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "engine":
                self.assertFalse(node.attr.startswith("_"), node.attr)


if __name__ == "__main__":
    unittest.main()
