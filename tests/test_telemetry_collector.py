"""Generic, already-executed fact fixtures; no solver or Engine execution."""

import inspect
import runpy
import sys
import types
import unittest
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
from unittest.mock import patch

import telemetry_collector
from core_engine import Action, GameStatus
from telemetry_collector import TelemetryCollector
from telemetry_model import ActionEvent, GameRecord, InferenceCategory


def physical_facts(**overrides):
    facts = dict(
        action_type=Action.OPEN, x=4, y=2, status_after=GameStatus.PLAYING,
        safe_cells_opened_delta=1, explicit_flag_delta=0,
    )
    facts.update(overrides)
    return facts


def analyzed_facts(category=InferenceCategory.LOCAL_DETERMINISTIC, **overrides):
    facts = physical_facts(
        inference_category=category, selection_candidate_count=3,
        target_mine_probability=Fraction(0),
        minimum_available_mine_probability=None, decision_compute_ns=7,
    )
    if category == InferenceCategory.PROBABILITY_GUESS:
        # Intentionally not the Stage 2 minimum-risk choice: collection is generic.
        facts.update(
            target_mine_probability=Fraction(2, 5),
            minimum_available_mine_probability=Fraction(1, 5),
        )
    facts.update(overrides)
    return facts


def finalize(collector, **overrides):
    inputs = dict(
        game_index=12, seed=42, board_fingerprint="opaque-evaluation-fingerprint",
        board_3bv=31, board_ops=4,
    )
    inputs.update(overrides)
    return collector.finalize(**inputs)


class TelemetryCollectorTests(unittest.TestCase):
    def test_indices_start_at_zero_and_remain_contiguous(self):
        collector = TelemetryCollector()
        self.assertEqual(collector.events, ())
        for index in range(4):
            event = collector.record_action(**analyzed_facts(x=index))
            self.assertEqual(event.action_index, index)
            self.assertIs(collector.events[index], event)
        self.assertEqual([event.action_index for event in collector.events], [0, 1, 2, 3])

    def test_caller_cannot_supply_an_index_or_an_event(self):
        collector = TelemetryCollector()
        self.assertNotIn("action_index", inspect.signature(collector.record_action).parameters)
        for unexpected in (dict(action_index=0), dict(action_index=99), dict(event=object())):
            with self.subTest(unexpected=unexpected), self.assertRaises(TypeError):
                collector.record_action(**physical_facts(), **unexpected)
        self.assertEqual(collector.events, ())
        self.assertEqual(collector.record_action(**physical_facts()).action_index, 0)

    def test_event_snapshots_and_input_dictionaries_cannot_mutate_history(self):
        collector = TelemetryCollector()
        facts = physical_facts()
        first = collector.record_action(**facts)
        snapshot = collector.events
        facts.update(x=99, safe_cells_opened_delta=99)
        collector.record_action(**analyzed_facts())
        self.assertEqual(snapshot, (first,))
        self.assertEqual((first.x, first.safe_cells_opened_delta), (4, 1))
        with self.assertRaises(TypeError):
            snapshot[0] = collector.events[1]
        with self.assertRaises(AttributeError):
            collector.events = ()
        copied = list(collector.events)
        copied.clear()
        self.assertEqual(len(collector.events), 2)

    def test_action_event_is_immutable_with_exact_semantic_fields(self):
        event = TelemetryCollector().record_action(**physical_facts())
        self.assertEqual(tuple(field.name for field in fields(ActionEvent)), (
            "action_index", "inference_category", "selection_candidate_count",
            "target_mine_probability", "minimum_available_mine_probability",
            "decision_compute_ns", "action_type", "x", "y", "status_after",
            "safe_cells_opened_delta", "explicit_flag_delta",
        ))
        for field in fields(event):
            with self.subTest(field=field.name), self.assertRaises(FrozenInstanceError):
                setattr(event, field.name, None)

    def test_initial_policy_open_has_null_metadata_and_preserves_physical_facts(self):
        event = TelemetryCollector().record_action(**physical_facts(
            x=8, y=3, safe_cells_opened_delta=11,
        ))
        self.assertEqual(event.action_index, 0)
        self.assertEqual((
            event.inference_category, event.selection_candidate_count,
            event.target_mine_probability, event.minimum_available_mine_probability,
            event.decision_compute_ns,
        ), (None,) * 5)
        self.assertEqual((
            event.action_type, event.x, event.y, event.status_after,
            event.safe_cells_opened_delta, event.explicit_flag_delta,
        ), (Action.OPEN, 8, 3, GameStatus.PLAYING, 11, 0))

    def test_partial_policy_metadata_is_rejected_without_consuming_index(self):
        collector = TelemetryCollector()
        for name, value in (
            ("selection_candidate_count", 1), ("target_mine_probability", Fraction(0)),
            ("minimum_available_mine_probability", Fraction(0)), ("decision_compute_ns", 0),
        ):
            with self.subTest(field=name), self.assertRaises(ValueError):
                collector.record_action(**physical_facts(**{name: value}))
            self.assertEqual(collector.events, ())
        self.assertEqual(collector.record_action(**physical_facts()).action_index, 0)

    def test_analyzed_metadata_requires_its_structural_nonnull_fields(self):
        for category in InferenceCategory:
            required = ["selection_candidate_count", "target_mine_probability", "decision_compute_ns"]
            if category == InferenceCategory.PROBABILITY_GUESS:
                required.append("minimum_available_mine_probability")
            for name in required:
                with self.subTest(category=category, field=name), self.assertRaises(ValueError):
                    TelemetryCollector().record_action(**analyzed_facts(category, **{name: None}))
            if category != InferenceCategory.PROBABILITY_GUESS:
                with self.subTest(category=category), self.assertRaises(ValueError):
                    TelemetryCollector().record_action(**analyzed_facts(
                        category, minimum_available_mine_probability=Fraction(0),
                    ))

    def test_model_itself_rejects_partial_null_metadata(self):
        event = TelemetryCollector().record_action(**physical_facts())
        with self.assertRaises(ValueError):
            replace(event, decision_compute_ns=0)
        analyzed = TelemetryCollector().record_action(**analyzed_facts())
        with self.assertRaises(ValueError):
            replace(analyzed, target_mine_probability=None)

    def test_rejected_action_between_events_leaves_no_gap(self):
        collector = TelemetryCollector()
        first = collector.record_action(**physical_facts())
        with self.assertRaises(ValueError):
            collector.record_action(**analyzed_facts(decision_compute_ns=-1, status_after=GameStatus.LOST))
        second = collector.record_action(**analyzed_facts())
        self.assertEqual(collector.events, (first, second))
        self.assertEqual(second.action_index, 1)

    def test_analyzed_index_zero_and_multiple_unanalyzed_events_are_generic(self):
        collector = TelemetryCollector()
        first = collector.record_action(**analyzed_facts())
        self.assertEqual(first.action_index, 0)
        self.assertEqual(first.inference_category, InferenceCategory.LOCAL_DETERMINISTIC)
        collector.record_action(**physical_facts())
        collector.record_action(**physical_facts(status_after=GameStatus.WON))
        record = finalize(collector)
        self.assertEqual(record.total_actions, 3)
        self.assertEqual(record.local_deterministic_count, 1)

    def test_exact_fraction_objects_and_generic_metadata_are_preserved(self):
        target = Fraction(10**400 + 1, 3 * 10**400)
        minimum = Fraction(1, 3)
        with patch.object(Fraction, "__float__", side_effect=AssertionError("No float conversion")):
            for category in InferenceCategory:
                with self.subTest(category=category):
                    facts = analyzed_facts(
                        category, selection_candidate_count=10**30,
                        target_mine_probability=target, decision_compute_ns=10**40,
                        minimum_available_mine_probability=(
                            minimum if category == InferenceCategory.PROBABILITY_GUESS else None
                        ),
                    )
                    event = TelemetryCollector().record_action(**facts)
                    for name, value in facts.items():
                        self.assertIs(getattr(event, name), value)
        self.assertNotEqual(target, minimum)

    def test_basic_types_and_numeric_ranges_are_rejected(self):
        invalid_values = {
            "action_type": ("OPEN", 0, True, GameStatus.PLAYING, object()),
            "status_after": ("WON", 1, True, Action.FLAG, object()),
            "x": (-1, True, 1.0, []),
            "y": (-1, False, 2.0),
            "safe_cells_opened_delta": (-1, False, 1.0),
            "explicit_flag_delta": (-2, 2, True, 0.0),
            "inference_category": ("local_deterministic", 1),
            "selection_candidate_count": (0, -1, True, 1.0),
            "decision_compute_ns": (-1, True, 1.0),
            "target_mine_probability": (0, 0.5, "1/2", Fraction(-1, 2), Fraction(3, 2)),
            "minimum_available_mine_probability": (0, 0.5, "1/2", Fraction(-1, 2), Fraction(3, 2)),
        }
        for name, values in invalid_values.items():
            for value in values:
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    TelemetryCollector().record_action(**analyzed_facts(
                        InferenceCategory.PROBABILITY_GUESS, **{name: value},
                    ))

    def test_terminal_event_is_retained_and_blocks_every_later_action(self):
        for status in (GameStatus.WON, GameStatus.LOST):
            with self.subTest(status=status):
                collector = TelemetryCollector()
                first = collector.record_action(**physical_facts())
                terminal = collector.record_action(**analyzed_facts(status_after=status))
                for later_status in GameStatus:
                    with self.assertRaisesRegex(ValueError, "after a terminal"):
                        collector.record_action(**physical_facts(status_after=later_status))
                self.assertEqual(collector.events, (first, terminal))
                self.assertEqual(terminal.action_index, 1)
                finalize(collector)
                with self.assertRaises(ValueError):
                    collector.record_action(**physical_facts())
                self.assertEqual(collector.events, (first, terminal))

    def test_finalization_rejects_empty_and_nonterminal_games_without_closing_them(self):
        collector = TelemetryCollector()
        with self.assertRaisesRegex(ValueError, "without a terminal"):
            finalize(collector)
        collector.record_action(**physical_facts())
        with self.assertRaisesRegex(ValueError, "without a terminal"):
            finalize(collector)
        collector.record_action(**analyzed_facts(status_after=GameStatus.WON))
        self.assertEqual(finalize(collector).result, "WIN")

    def test_terminal_status_maps_to_only_win_or_loss_and_finalizes_once(self):
        for status, result in ((GameStatus.WON, "WIN"), (GameStatus.LOST, "LOSS")):
            with self.subTest(status=status):
                collector = TelemetryCollector()
                collector.record_action(**physical_facts(status_after=status))
                record = finalize(collector)
                self.assertEqual(record.result, result)
                self.assertIs(type(record.result), str)
                with self.assertRaisesRegex(ValueError, "already been finalized"):
                    finalize(collector, seed=99)
                self.assertEqual(record.seed, 42)

    def test_game_record_is_immutable_and_contains_only_frozen_fields(self):
        collector = TelemetryCollector()
        collector.record_action(**physical_facts(status_after=GameStatus.WON))
        record = finalize(collector)
        self.assertEqual(tuple(field.name for field in fields(GameRecord)), (
            "game_index", "seed", "board_fingerprint", "first_click_x", "first_click_y",
            "result", "total_actions", "open_count", "flag_count", "chord_count",
            "local_deterministic_count", "global_certainty_count", "probability_guess_count",
            "had_probability_guess", "first_guess_action_index", "board_3bv", "board_ops",
            "compute_time_total_ns", "compute_time_max_ns",
        ))
        for field in fields(record):
            with self.subTest(field=field.name), self.assertRaises(FrozenInstanceError):
                setattr(record, field.name, None)

    def test_counts_guess_and_compute_summaries_match_raw_events(self):
        collector = TelemetryCollector()
        facts = (
            physical_facts(),
            analyzed_facts(action_type=Action.FLAG, safe_cells_opened_delta=0,
                           explicit_flag_delta=1, decision_compute_ns=10),
            analyzed_facts(InferenceCategory.GLOBAL_CERTAINTY, decision_compute_ns=0),
            analyzed_facts(InferenceCategory.PROBABILITY_GUESS, decision_compute_ns=15),
            analyzed_facts(action_type=Action.CHORD, decision_compute_ns=7),
            analyzed_facts(InferenceCategory.PROBABILITY_GUESS, action_type=Action.CHORD,
                           status_after=GameStatus.LOST, safe_cells_opened_delta=2,
                           decision_compute_ns=12),
        )
        for fact in facts:
            collector.record_action(**fact)
        record = finalize(collector)
        self.assertEqual((record.total_actions, record.open_count, record.flag_count, record.chord_count),
                         (6, 3, 1, 2))
        self.assertEqual(record.total_actions, len(collector.events))
        self.assertEqual(record.total_actions, record.open_count + record.flag_count + record.chord_count)
        self.assertEqual((record.local_deterministic_count, record.global_certainty_count,
                          record.probability_guess_count), (2, 1, 2))
        self.assertIs(record.had_probability_guess, True)
        self.assertEqual(record.first_guess_action_index, 3)
        self.assertEqual((record.compute_time_total_ns, record.compute_time_max_ns), (44, 15))
        self.assertEqual((record.first_click_x, record.first_click_y), (4, 2))
        self.assertEqual(record.result, "LOSS")

    def test_zero_one_and_multiple_guesses_including_first_action_guess(self):
        for guess_count in (0, 1, 3):
            with self.subTest(guess_count=guess_count):
                collector = TelemetryCollector()
                for _ in range(guess_count):
                    collector.record_action(**analyzed_facts(InferenceCategory.PROBABILITY_GUESS))
                collector.record_action(**analyzed_facts(status_after=GameStatus.WON))
                record = finalize(collector)
                self.assertEqual(record.probability_guess_count, guess_count)
                self.assertIs(record.had_probability_guess, guess_count > 0)
                self.assertEqual(record.first_guess_action_index, 0 if guess_count else None)
                if guess_count:
                    self.assertEqual(collector.events[record.first_guess_action_index].inference_category,
                                     InferenceCategory.PROBABILITY_GUESS)

    def test_zero_decision_game_keeps_policy_timing_null(self):
        collector = TelemetryCollector()
        collector.record_action(**physical_facts(status_after=GameStatus.WON, safe_cells_opened_delta=6))
        record = finalize(collector)
        self.assertEqual((record.total_actions, record.open_count), (1, 1))
        self.assertEqual((record.local_deterministic_count, record.global_certainty_count,
                          record.probability_guess_count), (0, 0, 0))
        self.assertIs(record.had_probability_guess, False)
        self.assertIsNone(record.first_guess_action_index)
        self.assertEqual(record.compute_time_total_ns, 0)
        self.assertIsNone(record.compute_time_max_ns)
        self.assertIsNone(collector.events[0].decision_compute_ns)

    def test_zero_duration_analysis_is_distinct_from_no_analysis(self):
        collector = TelemetryCollector()
        collector.record_action(**analyzed_facts(decision_compute_ns=0, status_after=GameStatus.WON))
        record = finalize(collector)
        self.assertEqual((record.compute_time_total_ns, record.compute_time_max_ns), (0, 0))

    def test_compute_aggregation_keeps_arbitrary_size_integer_precision(self):
        collector = TelemetryCollector()
        collector.record_action(**physical_facts())
        timings = (10**40 + 1, 10**40, 0)
        for index, timing in enumerate(timings):
            collector.record_action(**analyzed_facts(
                decision_compute_ns=timing,
                status_after=GameStatus.WON if index == 2 else GameStatus.PLAYING,
            ))
        record = finalize(collector)
        self.assertEqual(record.compute_time_total_ns, 2 * 10**40 + 1)
        self.assertEqual(record.compute_time_max_ns, 10**40 + 1)

    def test_evaluation_inputs_are_preserved_without_container_aliases(self):
        collector = TelemetryCollector()
        collector.record_action(**physical_facts(status_after=GameStatus.WON))
        inputs = dict(game_index=0, seed=0, board_fingerprint="provided-identity", board_3bv=123, board_ops=17)
        record = collector.finalize(**inputs)
        inputs.update(board_3bv=999, board_ops=999, board_fingerprint="changed")
        self.assertEqual((record.game_index, record.seed, record.board_fingerprint,
                          record.board_3bv, record.board_ops), (0, 0, "provided-identity", 123, 17))

    def test_invalid_evaluation_inputs_allow_retry_but_no_summary_overrides(self):
        collector = TelemetryCollector()
        collector.record_action(**physical_facts(status_after=GameStatus.WON))
        for name, value in (
            ("game_index", -1), ("seed", True), ("board_fingerprint", []),
            ("board_fingerprint", ""), ("board_3bv", -1), ("board_ops", 1.5),
        ):
            with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                finalize(collector, **{name: value})
        for name in (
            "result", "total_actions", "had_probability_guess", "first_guess_action_index",
            "compute_time_total_ns", "first_click_x", "events",
        ):
            with self.subTest(field=name), self.assertRaises(TypeError):
                finalize(collector, **{name: 0})
        self.assertEqual(finalize(collector).total_actions, 1)

    def test_game_record_rejects_inconsistent_summary_arithmetic_and_nullability(self):
        collector = TelemetryCollector()
        collector.record_action(**physical_facts(status_after=GameStatus.WON))
        record = finalize(collector)
        for overrides in (
            dict(total_actions=2), dict(open_count=2), dict(local_deterministic_count=2),
            dict(had_probability_guess=True), dict(had_probability_guess=1),
            dict(probability_guess_count=1), dict(first_guess_action_index=0),
            dict(compute_time_total_ns=1), dict(compute_time_max_ns=0),
            dict(result="ERROR"), dict(result="ABORTED"), dict(result=1),
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                replace(record, **overrides)

        guessed = TelemetryCollector()
        guessed.record_action(**analyzed_facts(InferenceCategory.PROBABILITY_GUESS, status_after=GameStatus.LOST))
        record = finalize(guessed)
        for overrides in (
            dict(first_guess_action_index=None), dict(first_guess_action_index=-1),
            dict(first_guess_action_index=1), dict(compute_time_max_ns=None),
            dict(compute_time_max_ns=8), dict(compute_time_total_ns=8),
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                replace(record, **overrides)

    def test_representative_execution_effects_are_preserved_without_recomputation(self):
        # These fact values mirror Batch 1 fixtures, without repeating Engine steps.
        cases = (
            ("win_auto_flags", Action.OPEN, GameStatus.WON, 1, 0),
            ("flood_including_flagged_safe_cell", Action.OPEN, GameStatus.WON, 11, 0),
            ("loss_display", Action.OPEN, GameStatus.LOST, 0, 0),
            ("losing_chord_with_safe_reveals", Action.CHORD, GameStatus.LOST, 2, 0),
        )
        for label, action, status, safe, flags in cases:
            with self.subTest(effect=label):
                collector = TelemetryCollector()
                event = collector.record_action(**analyzed_facts(
                    action_type=action, status_after=status,
                    safe_cells_opened_delta=safe, explicit_flag_delta=flags,
                ))
                finalize(collector)
                self.assertEqual((event.safe_cells_opened_delta, event.explicit_flag_delta), (safe, flags))

        collector = TelemetryCollector()
        for delta in (1, -1):
            collector.record_action(**analyzed_facts(
                action_type=Action.FLAG, safe_cells_opened_delta=0, explicit_flag_delta=delta,
            ))
        collector.record_action(**physical_facts(status_after=GameStatus.WON))
        self.assertEqual(finalize(collector).flag_count, 2)
        self.assertEqual(tuple(event.explicit_flag_delta for event in collector.events), (1, -1, 0))

    def test_collection_and_finalization_need_only_public_enums_not_execution_or_analysis(self):
        public_types = types.ModuleType("core_engine")
        public_types.Action = Action
        public_types.GameStatus = GameStatus
        blocked = dict.fromkeys((
            "simple_algorithm", "simple_probability", "simple_decision", "simple_runner",
            "simple_telemetry", "board_snapshot", "board_analyzer", "replay_model",
            "replay_recorder", "sqlite3",
        ))
        with patch.dict(sys.modules, {"core_engine": public_types, **blocked}):
            namespace = runpy.run_path(telemetry_collector.__file__)
            collector = namespace["TelemetryCollector"]()
            collector.record_action(**physical_facts())
            collector.record_action(**analyzed_facts(
                InferenceCategory.PROBABILITY_GUESS, status_after=GameStatus.LOST,
            ))
            record = finalize(collector)
        self.assertEqual(record.result, "LOSS")
        self.assertEqual(record.probability_guess_count, 1)
        self.assertEqual((record.board_3bv, record.board_ops), (31, 4))
        for name in ("SimpleDecision", "DecisionKind", "SimpleActionTrace", "decision_to_telemetry",
                     "analyze_position", "analyze_board", "MinesweeperEngine"):
            self.assertNotIn(name, namespace)


if __name__ == "__main__":
    unittest.main()
