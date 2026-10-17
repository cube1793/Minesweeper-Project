"""Synthetic in-memory timeline facts; no boards, solvers or evidence artifacts."""

import ast
import copy
import inspect
import unittest
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from unittest.mock import patch

import benchmark_modeled_time as modeled
from core_engine import Action, GameStatus, MinesweeperEngine
import stage3_physical as physical
from telemetry_model import ActionEvent, GameRecord, InferenceCategory
import timeline_analytics as timeline


def event(index, action=Action.OPEN, x=0, y=0, **overrides):
    values = dict(
        action_index=index, action_type=action, x=x, y=y,
        status_after=GameStatus.PLAYING, safe_cells_opened_delta=0,
        explicit_flag_delta=0, inference_category=None,
        selection_candidate_count=None, target_mine_probability=None,
        minimum_available_mine_probability=None, decision_compute_ns=None,
    )
    values.update(overrides)
    return ActionEvent(**values)


def completed_game(status=GameStatus.WON):
    """Structurally valid recorded facts, without asserting a hidden layout."""
    events = (
        event(0, safe_cells_opened_delta=2),
        event(1, Action.FLAG, 2, 1, explicit_flag_delta=1,
              inference_category=InferenceCategory.LOCAL_DETERMINISTIC,
              selection_candidate_count=3, target_mine_probability=Fraction(1),
              decision_compute_ns=7),
        event(2, Action.CHORD, 1, 2, safe_cells_opened_delta=3,
              inference_category=InferenceCategory.GLOBAL_CERTAINTY,
              decision_compute_ns=0),
        event(3, Action.OPEN, 1, 0, status_after=status,
              safe_cells_opened_delta=1 if status == GameStatus.WON else 0,
              inference_category=InferenceCategory.PROBABILITY_GUESS,
              selection_candidate_count=4,
              target_mine_probability=Fraction(10**100 + 1, 3 * 10**100),
              minimum_available_mine_probability=Fraction(1, 3),
              decision_compute_ns=11),
    )
    record = GameRecord(
        game_index=0, seed=42, board_fingerprint="synthetic-opaque-identity",
        first_click_x=0, first_click_y=0,
        result="WIN" if status == GameStatus.WON else "LOSS",
        total_actions=4, open_count=2, flag_count=1, chord_count=1,
        local_deterministic_count=1, global_certainty_count=1,
        probability_guess_count=1, had_probability_guess=True,
        first_guess_action_index=3, board_3bv=3, board_ops=1,
        compute_time_total_ns=18, compute_time_max_ns=11,
    )
    return record, events


def single_action_game(status=GameStatus.WON):
    events = (event(0, status_after=status,
                    safe_cells_opened_delta=8 if status == GameStatus.WON else 0),)
    record = GameRecord(
        game_index=0, seed=0, board_fingerprint="synthetic-single-action",
        first_click_x=0, first_click_y=0,
        result="WIN" if status == GameStatus.WON else "LOSS",
        total_actions=1, open_count=1, flag_count=0, chord_count=0,
        local_deterministic_count=0, global_certainty_count=0,
        probability_guess_count=0, had_probability_guess=False,
        first_guess_action_index=None, board_3bv=1, board_ops=1,
        compute_time_total_ns=0, compute_time_max_ns=None,
    )
    return record, events


class TimelineAnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluation = modeled.authenticate_model_c()

    def setUp(self):
        self.record, self.events = completed_game()

    def project(self, record=None, events=None, **overrides):
        options = dict(width=3, height=3, evaluation=self.evaluation)
        options.update(overrides)
        return timeline.project_timeline(
            self.record if record is None else record,
            self.events if events is None else events, **options,
        )

    def test_multi_action_win_preserves_original_authorities_and_all_action_kinds(self):
        result = self.project()
        self.assertIs(result.record, self.record)
        self.assertEqual(result.record.result, "WIN")
        self.assertIsInstance(result.actions, tuple)
        self.assertEqual(len(result.actions), 4)
        for item, original in zip(result.actions, self.events):
            self.assertIs(item.event, original)
        self.assertEqual(tuple(item.event.action_type for item in result.actions), (
            Action.OPEN, Action.FLAG, Action.CHORD, Action.OPEN,
        ))
        self.assertEqual(result.actions[-1].event.status_after, GameStatus.WON)

    def test_action_costs_cumulative_costs_and_total_are_exact_integers(self):
        result = self.project()
        # Authenticated frozen table values, including the initial target input.
        self.assertEqual(tuple(item.modeled_action_us for item in result.actions),
                         (126005, 193056, 144891, 180604))
        self.assertEqual(tuple(item.cumulative_modeled_us for item in result.actions),
                         (126005, 319061, 463952, 644556))
        self.assertEqual(result.total_modeled_us, 644556)
        self.assertIs(type(result.total_modeled_us), int)
        for item in result.actions:
            for value in (item.modeled_action_us, item.cumulative_modeled_us,
                          item.dx, item.dy, item.squared_displacement):
                self.assertIs(type(value), int)

    def test_total_exactly_matches_existing_reconstruction_for_win_and_loss(self):
        for status in (GameStatus.WON, GameStatus.LOST):
            record, events = completed_game(status)
            with self.subTest(status=status):
                expected = modeled.reconstruct_game(
                    record, events, width=3, height=3, evaluation=self.evaluation,
                )
                self.assertEqual(self.project(record, events).total_modeled_us,
                                 expected.total_modeled_us)

    def test_loss_includes_terminal_input_and_only_recorded_reveal_effects(self):
        result = self.project(*completed_game(GameStatus.LOST))
        self.assertEqual(result.record.result, "LOSS")
        self.assertEqual(result.actions[-1].event.status_after, GameStatus.LOST)
        self.assertEqual(result.actions[-1].modeled_action_us, 180604)
        self.assertEqual(result.total_modeled_us, 644556)
        self.assertEqual(result.actions[-1].cumulative_safe_cells_opened, 5)

    def test_single_canonical_open_win_or_loss_has_positive_same_cell_cost(self):
        for status in (GameStatus.WON, GameStatus.LOST):
            with self.subTest(status=status):
                result = self.project(*single_action_game(status))
                self.assertEqual(len(result.actions), 1)
                self.assertEqual(result.actions[0].completed_action_count, 1)
                self.assertEqual(result.actions[0].squared_displacement, 0)
                self.assertEqual(result.total_modeled_us, 126005)
                self.assertEqual(result.cumulative_modeled_curve, ((0, 0), (1, 126005)))

    def test_repeated_same_cell_flag_inputs_each_cost_time_and_keep_signed_flag_effect(self):
        record, events = single_action_game()
        events = (
            replace(events[0], status_after=GameStatus.PLAYING, safe_cells_opened_delta=1),
            event(1, Action.FLAG, 1, 0, explicit_flag_delta=1),
            event(2, Action.FLAG, 1, 0, explicit_flag_delta=-1, status_after=GameStatus.WON),
        )
        record = replace(record, total_actions=3, flag_count=2)
        result = self.project(record, events)
        self.assertEqual(result.total_modeled_us, 3 * 126005)
        self.assertEqual(result.actions[-1].squared_displacement, 0)
        self.assertEqual(result.actions[-1].modeled_action_us, 126005)
        self.assertEqual(tuple(item.event.explicit_flag_delta for item in result.actions), (0, 1, -1))

    def test_completed_action_count_and_curve_origins_do_not_fabricate_an_event(self):
        result = self.project()
        self.assertEqual(tuple(item.event.action_index for item in result.actions), (0, 1, 2, 3))
        self.assertEqual(tuple(item.completed_action_count for item in result.actions), (1, 2, 3, 4))
        self.assertEqual(result.cumulative_modeled_curve,
                         ((0, 0), (1, 126005), (2, 319061), (3, 463952), (4, 644556)))
        self.assertEqual(result.cumulative_safe_reveal_curve,
                         ((0, 0), (1, 2), (2, 2), (3, 5), (4, 6)))
        self.assertEqual(len(result.actions), len(self.events))

    def test_signed_displacements_and_squared_cell_center_geometry(self):
        result = self.project()
        self.assertEqual(tuple((item.dx, item.dy, item.squared_displacement) for item in result.actions),
                         ((0, 0, 0), (2, 1, 5), (-1, 1, 2), (0, -2, 4)))

    def test_cumulative_safe_reveals_do_not_turn_automatic_effects_into_actions(self):
        result = self.project(*single_action_game())
        self.assertEqual(result.cumulative_safe_reveal_curve, ((0, 0), (1, 8)))
        self.assertEqual(result.record.flag_count, 0)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.total_modeled_us, 126005)

    def test_exact_probability_objects_survive_without_policy_reinterpretation(self):
        original = self.events[-1]
        projected = self.project().actions[-1].event
        self.assertIs(projected.target_mine_probability, original.target_mine_probability)
        self.assertIs(projected.minimum_available_mine_probability,
                      original.minimum_available_mine_probability)
        # These differ below float precision; projection must not round or
        # enforce a historical minimum-risk selection policy by reanalysis.
        self.assertGreater(projected.target_mine_probability,
                           projected.minimum_available_mine_probability)
        self.assertEqual(projected.target_mine_probability - projected.minimum_available_mine_probability,
                         Fraction(1, 3 * 10**100))

    def test_nullable_metadata_and_zero_compute_remain_distinct(self):
        actions = self.project().actions
        for name in ("inference_category", "selection_candidate_count", "target_mine_probability",
                     "minimum_available_mine_probability", "decision_compute_ns"):
            self.assertIsNone(getattr(actions[0].event, name))
        self.assertIsNone(actions[2].event.target_mine_probability)
        self.assertIsNone(actions[2].event.minimum_available_mine_probability)
        self.assertEqual(actions[2].event.decision_compute_ns, 0)
        self.assertIs(type(actions[2].event.decision_compute_ns), int)
        self.assertEqual(tuple(item.event.decision_compute_ns for item in actions), (None, 7, 0, 11))

    def test_stage2_candidate_counts_present_and_stage3_style_none_preserved(self):
        self.assertEqual(self.project().actions[-1].event.selection_candidate_count, 4)
        events = tuple(replace(item, selection_candidate_count=None) for item in self.events)
        result = self.project(events=events)
        self.assertTrue(all(item.event.selection_candidate_count is None for item in result.actions))
        self.assertEqual(result.total_modeled_us, self.project().total_modeled_us)

    def test_no_analysis_and_zero_duration_analysis_keep_distinct_nullable_summaries(self):
        record, events = single_action_game()
        self.assertIsNone(self.project(record, events).record.compute_time_max_ns)
        analyzed = (replace(events[0], inference_category=InferenceCategory.LOCAL_DETERMINISTIC,
                            decision_compute_ns=0),)
        record = replace(record, local_deterministic_count=1, compute_time_max_ns=0)
        result = self.project(record, analyzed)
        self.assertEqual(result.record.compute_time_max_ns, 0)
        self.assertEqual(result.actions[0].event.decision_compute_ns, 0)
        self.assertEqual(result.total_modeled_us, 126005)

    def test_large_compute_integers_are_preserved_and_do_not_change_model_c_cost(self):
        duration = 10**100 + 17
        events = (*self.events[:-1], replace(self.events[-1], decision_compute_ns=duration))
        record = replace(self.record, compute_time_total_ns=duration + 7, compute_time_max_ns=duration)
        result = self.project(record, events)
        self.assertEqual(result.actions[-1].event.decision_compute_ns, duration)
        self.assertEqual(result.total_modeled_us, self.project().total_modeled_us)

    def test_authenticated_evaluation_retains_all_model_provenance_without_copying(self):
        result = self.project()
        self.assertIs(result.evaluation, self.evaluation)
        identity = physical.MODEL_C_V1_IDENTITY
        for name in ("physical_model_id", "physical_profile_version", "physical_profile_sha256",
                     "timing_table_sha256", "timing_unit"):
            self.assertEqual(getattr(result.evaluation, name), getattr(identity, name))

    def test_game_summary_disagreements_are_rejected_even_when_record_is_internally_valid(self):
        changes = (
            dict(total_actions=5, open_count=3),
            dict(first_click_x=1), dict(first_click_y=1), dict(result="LOSS"),
            dict(open_count=1, flag_count=2), dict(flag_count=0, chord_count=2),
            dict(chord_count=0, flag_count=2),
            dict(local_deterministic_count=0), dict(global_certainty_count=0),
            dict(probability_guess_count=0, had_probability_guess=False, first_guess_action_index=None),
            dict(local_deterministic_count=0, probability_guess_count=2),
            dict(first_guess_action_index=2),
            dict(compute_time_total_ns=19), dict(compute_time_max_ns=12),
        )
        for change in changes:
            with self.subTest(change=change):
                record = replace(self.record, **change)
                with self.assertRaises(ValueError):
                    self.project(record=record)

    def test_game_model_itself_rejects_inconsistent_guess_and_compute_nullability(self):
        for change in (dict(had_probability_guess=False), dict(first_guess_action_index=None),
                       dict(compute_time_max_ns=None)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(self.record, **change)

    def test_missing_extra_duplicate_shifted_gapped_and_reordered_events_are_rejected(self):
        cases = (
            (), self.events[:-1], (*self.events, self.events[-1]),
            (self.events[0], replace(self.events[1], action_index=0), *self.events[2:]),
            tuple(replace(item, action_index=item.action_index + 1) for item in self.events),
            (self.events[0], replace(self.events[1], action_index=8), *self.events[2:]),
            tuple(reversed(self.events)),
        )
        for index, events in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(modeled.ModeledTimeValidationError):
                self.project(events=events)

    def test_early_terminal_post_terminal_and_unfinished_streams_are_rejected(self):
        for index, status in ((0, GameStatus.WON), (1, GameStatus.LOST),
                              (3, GameStatus.PLAYING), (3, GameStatus.LOST)):
            events = list(self.events)
            events[index] = replace(events[index], status_after=status)
            with self.subTest(index=index, status=status), self.assertRaises(modeled.ModeledTimeValidationError):
                self.project(events=tuple(events))
        # Count agrees, but an extra physical input after the recorded WIN is invalid.
        events = (*self.events, event(4, status_after=GameStatus.WON))
        record = replace(self.record, total_actions=5, open_count=3)
        with self.assertRaises(modeled.ModeledTimeValidationError):
            self.project(record, events)

    def test_noncanonical_first_input_is_rejected(self):
        for change in (dict(action_type=Action.FLAG), dict(action_type=Action.CHORD), dict(x=1), dict(y=1)):
            events = (replace(self.events[0], **change), *self.events[1:])
            with self.subTest(change=change), self.assertRaises(modeled.ModeledTimeValidationError):
                self.project(events=events)

    def test_out_of_bounds_targets_and_invalid_dimensions_are_rejected(self):
        for change in (dict(x=3), dict(y=3), dict(x=30), dict(y=16)):
            events = (self.events[0], replace(self.events[1], **change), *self.events[2:])
            with self.subTest(change=change), self.assertRaises(modeled.ModeledTimeValidationError):
                self.project(events=events)
        for width, height in ((0, 3), (31, 3), (3, 17), (True, 3), (3, 3.0)):
            with self.subTest(dimensions=(width, height)), self.assertRaises(modeled.ModeledTimeValidationError):
                self.project(width=width, height=height)

    def test_invalid_public_action_status_enums_are_rejected_by_existing_validator(self):
        for change in (dict(action_type=1), dict(action_type="OPEN"),
                       dict(status_after=1), dict(status_after="PLAYING")):
            events = (self.events[0], replace(self.events[1], **change), *self.events[2:])
            with self.subTest(change=change), self.assertRaises(modeled.ModeledTimeValidationError):
                self.project(events=events)

    def test_existing_models_and_immutable_event_tuple_are_required(self):
        for record, events in ((object(), self.events), (self.record, list(self.events)),
                               (self.record, iter(self.events)), (self.record, (object(),))):
            with self.subTest(record=type(record), events=type(events)), self.assertRaises(ValueError):
                self.project(record, events)

    def test_explicit_authenticated_evaluation_is_required(self):
        for evaluation in (None, object(), self.evaluation.table):
            with self.subTest(evaluation=type(evaluation)), self.assertRaises(modeled.ModeledTimeValidationError):
                self.project(evaluation=evaluation)

    def test_inputs_are_unchanged_and_projection_is_repeatable(self):
        before = copy.deepcopy((self.record, self.events, self.evaluation))
        first = self.project()
        self.assertEqual(self.project(), first)
        self.assertEqual((self.record, self.events, self.evaluation), before)

    def test_output_dataclasses_and_nested_data_are_immutable(self):
        result = self.project()
        for obj, name, value in ((result, "total_modeled_us", 0), (result, "actions", ()),
                                 (result.actions[0], "dx", 99), (result.actions[0], "event", None),
                                 (result.record, "seed", 99), (result.actions[0].event, "x", 99),
                                 (result.evaluation, "timing_unit", "ms")):
            with self.subTest(field=name), self.assertRaises(FrozenInstanceError):
                setattr(obj, name, value)
        with self.assertRaises(TypeError):
            result.actions[0] = result.actions[-1]
        curve = result.cumulative_modeled_curve
        with self.assertRaises(TypeError):
            curve[0] = (1, 1)

    def test_existing_cost_seams_are_used_and_total_disagreement_fails_closed(self):
        with patch.object(modeled, "reconstruct_game", wraps=modeled.reconstruct_game) as reconstruct, \
                patch.object(physical, "action_cost", wraps=physical.action_cost) as cost:
            self.project()
        reconstruct.assert_called_once_with(
            self.record, self.events, width=3, height=3, evaluation=self.evaluation,
        )
        self.assertEqual(cost.call_count, len(self.events))
        self.assertEqual(tuple(call.args[1:] for call in cost.call_args_list), (
            ((0, 0), (0, 0)), ((0, 0), (2, 1)), ((2, 1), (1, 2)), ((1, 2), (1, 0)),
        ))
        self.assertTrue(all(call.args[0] is self.evaluation.table for call in cost.call_args_list))
        with patch.object(physical, "action_cost", return_value=1):
            with self.assertRaisesRegex(ValueError, "total disagrees"):
                self.project()

    def test_projection_needs_no_database_execution_hidden_layout_or_reauthentication(self):
        with ExitStack() as stack:
            for target in ("sqlite3.connect", "stage3_physical.load_timing_table",
                           "stage3_runner.run_stage3", "simple_runner.run_simple",
                           "stage3_planner.plan_position", "simple_decision.analyze_position"):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            for name in ("__init__", "step", "get_board_snapshot"):
                stack.enter_context(patch.object(MinesweeperEngine, name, side_effect=AssertionError(name)))
            self.project()
        tree = ast.parse(inspect.getsource(timeline))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
        forbidden_imports = {"sqlite3", "PySide6", "PyQt6", "stage3_runner", "stage3_planner",
                             "simple_runner", "simple_decision", "telemetry_repository"}
        self.assertFalse({name.split(".")[0] for name in imports} & forbidden_imports)
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertFalse(attributes & {"get_board_snapshot", "step", "mine_positions", "board_fingerprint",
                                       "board_3bv", "board_ops", "plan_position", "analyze_position"})


if __name__ == "__main__":
    unittest.main()
