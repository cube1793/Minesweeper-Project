"""Post-hoc ZiNi path diagnostics, delta playback, and V1 isolation contracts.

Frozen V1 outputs test current algorithm output. The historical 120-click
witness tests only a known valid path; its diagnostics are not search history.
"""

from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import random
import unittest
from unittest.mock import patch

from board_snapshot import BoardSnapshot
from tests.zini_fixtures import (
    _EXPERT_SEED1003_120_TRACE,
    _advanced_search_snapshot,
    _expert_seed1003_snapshot,
    _replay_zini_result,
)
from tests.zini_golden_helpers import (
    WORKLOADS,
    assert_golden_equal,
    canonical_output,
    run_workload,
    workload_snapshot,
)
from tests.zini_v1_golden import GOLDEN
from zini_calculator import ZiniMove, ZiniResult, calculate_g_zini
from zini_core import (
    _ZiniBoardState,
    _apply_premium_candidate,
    _build_premium_context,
    _find_premium_candidates,
    _run_g_zini_loop,
)
from zini_trace import (
    TRACE_SCHEMA_VERSION,
    ZINI_SEMANTICS_VERSION,
    ZiniTrace,
    ZiniTracePlayer,
    ZiniTraceSelection,
    ZiniTraceStep,
    build_zini_trace,
)


def _center_mine_snapshot():
    return BoardSnapshot(
        width=3, height=3, num_mines=1, mines_placed=True,
        mines=frozenset({(1, 1)}),
        adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
    )


def _separated_numbers_snapshot():
    return BoardSnapshot(
        width=3, height=1, num_mines=1, mines_placed=True,
        mines=frozenset({(1, 0)}), adjacent=((1, 0, 1),),
    )


def _path_result(signatures):
    moves = tuple(ZiniMove(*entry) for entry in signatures)
    return ZiniResult(sum(move.clicks_added for move in moves), moves)


def _deviate_then_finish(snapshot, coord):
    """Make a valid test path with one chosen deviation and greedy closure."""
    state = _ZiniBoardState.create(snapshot)
    context = _build_premium_context(snapshot)
    candidate = next(
        item for item in _find_premium_candidates(state, context)
        if item.coord == coord
    )
    first = _apply_premium_candidate(state, candidate, context)
    moves = (first, *_run_g_zini_loop(state, context))
    return ZiniResult(sum(move.clicks_added for move in moves), moves)


class ZiniTraceBuilderTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = _center_mine_snapshot()
        self.result = calculate_g_zini(self.snapshot)
        self.trace = build_zini_trace(self.snapshot, self.result)

    def assert_complete_trace(self, snapshot, result, trace):
        self.assertEqual(tuple(step.move for step in trace.steps), result.moves)
        self.assertEqual(trace.total_clicks, result.clicks)
        self.assertEqual(
            sum(step.move.clicks_added for step in trace.steps), result.clicks,
        )
        revealed, flagged = set(), set()
        for index, step in enumerate(trace.steps):
            with self.subTest(step=index):
                self.assertEqual(step.step_index, index)
                for delta in (step.newly_revealed, step.newly_flagged):
                    self.assertIsInstance(delta, tuple)
                    self.assertEqual(
                        delta, tuple(sorted(set(delta), key=lambda cell: (cell[1], cell[0]))),
                    )
                self.assertTrue(revealed.isdisjoint(step.newly_revealed))
                self.assertTrue(flagged.isdisjoint(step.newly_flagged))
                revealed.update(step.newly_revealed)
                flagged.update(step.newly_flagged)
        safe_cells = {
            (x, y) for y in range(snapshot.height) for x in range(snapshot.width)
            if (x, y) not in snapshot.mines
        }
        self.assertEqual(revealed, safe_cells)
        self.assertLessEqual(flagged, snapshot.mines)
        reference = _replay_zini_result(snapshot, result)
        self.assertEqual(revealed, reference.revealed)
        self.assertEqual(flagged, reference.flagged_mines)

    def test_small_deterministic_trace_has_versions_and_logical_steps(self):
        self.assertEqual(TRACE_SCHEMA_VERSION, 1)
        self.assertEqual(ZINI_SEMANTICS_VERSION, 1)
        self.assertEqual(self.trace.schema_version, TRACE_SCHEMA_VERSION)
        self.assertEqual(self.trace.semantics_version, ZINI_SEMANTICS_VERSION)
        self.assertEqual(self.trace.snapshot, self.snapshot)
        self.assertEqual(len(self.trace.steps), 4)
        self.assertEqual(self.trace.total_clicks, 5)
        self.assert_complete_trace(self.snapshot, self.result, self.trace)

    def test_click_delta_and_pre_move_greedy_diagnostics(self):
        step = self.trace.steps[0]
        self.assertEqual(step.move, ZiniMove("click", 1, 0, 2, 1))
        self.assertEqual(step.newly_revealed, ((1, 0),))
        self.assertEqual(step.newly_flagged, ())
        self.assertEqual(step.best_premium, 2)
        self.assertEqual(step.tie_count, 4)
        self.assertEqual(step.selection, ZiniTraceSelection.GREEDY)

    def test_flag_chord_delta_counts_only_new_flags(self):
        step = self.trace.steps[1]
        self.assertEqual(step.move, ZiniMove("flag_chord", 1, 0, 2, 2))
        self.assertEqual(step.newly_revealed, ((0, 0), (2, 0), (0, 1), (2, 1)))
        self.assertEqual(step.newly_flagged, ((1, 1),))
        self.assertEqual(step.tie_count, 2)
        later = self.trace.steps[2]
        self.assertEqual(later.newly_revealed, ((0, 2), (1, 2)))
        self.assertEqual(later.newly_flagged, ())
        self.assertEqual(later.move.clicks_added, 1)

    def test_opening_fallback_reveals_zero_group_and_border_ring(self):
        snapshot = BoardSnapshot(
            width=3, height=3, num_mines=1, mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        result = calculate_g_zini(snapshot)
        trace = build_zini_trace(snapshot, result)
        self.assertEqual(len(trace.steps), 1)
        step = trace.steps[0]
        self.assertEqual(step.move, ZiniMove("fallback_click", 2, 0, None, 1))
        self.assertEqual(step.newly_revealed, (
            (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2),
        ))
        self.assertEqual(step.newly_flagged, ())
        self.assertEqual(step.selection, ZiniTraceSelection.FALLBACK_GREEDY)
        self.assertLess(step.best_premium, 0)
        self.assert_complete_trace(snapshot, result, trace)

    def test_no_number_candidates_have_none_best_and_zero_ties(self):
        snapshot = BoardSnapshot(1, 1, 0, True, frozenset(), ((0,),))
        trace = build_zini_trace(snapshot, calculate_g_zini(snapshot))
        self.assertIsNone(trace.steps[0].best_premium)
        self.assertEqual(trace.steps[0].tie_count, 0)
        self.assertEqual(trace.steps[0].newly_revealed, ((0, 0),))
        self.assertEqual(trace.steps[0].selection, ZiniTraceSelection.FALLBACK_GREEDY)

    def test_already_solved_board_accepts_empty_zero_click_path(self):
        snapshot = BoardSnapshot(1, 1, 1, True, frozenset({(0, 0)}), ((0,),))
        trace = build_zini_trace(snapshot, ZiniResult(0))
        self.assertEqual(trace.steps, ())
        self.assertEqual(trace.total_clicks, 0)

    def test_maximum_premium_tie_alternate(self):
        result = _deviate_then_finish(self.snapshot, (0, 1))
        trace = build_zini_trace(self.snapshot, result)
        step = trace.steps[0]
        self.assertEqual(step.move, ZiniMove("click", 0, 1, 2, 1))
        self.assertEqual(step.best_premium, 2)
        self.assertEqual(step.tie_count, 4)
        self.assertEqual(step.selection, ZiniTraceSelection.MAX_TIE_ALT)
        self.assert_complete_trace(self.snapshot, result, trace)

    def test_below_maximum_premium_is_state_relationship_only(self):
        result = _deviate_then_finish(self.snapshot, (0, 0))
        trace = build_zini_trace(self.snapshot, result)
        step = trace.steps[0]
        self.assertEqual(step.move, ZiniMove("click", 0, 0, 0, 1))
        self.assertEqual(step.best_premium, 2)
        self.assertEqual(step.tie_count, 4)
        self.assertEqual(step.selection, ZiniTraceSelection.BELOW_MAX)
        self.assert_complete_trace(self.snapshot, result, trace)

    def test_covered_negative_premium_can_be_below_nonnegative_maximum(self):
        snapshot = _advanced_search_snapshot()
        result = _deviate_then_finish(snapshot, (1, 0))
        trace = build_zini_trace(snapshot, result)
        self.assertEqual(trace.steps[0].move, ZiniMove("click", 1, 0, -1, 1))
        self.assertEqual(trace.steps[0].best_premium, 0)
        self.assertEqual(trace.steps[0].tie_count, 5)
        self.assertEqual(trace.steps[0].selection, ZiniTraceSelection.BELOW_MAX)
        self.assert_complete_trace(snapshot, result, trace)

    def test_fallback_alternate_and_greedy_preserve_negative_max_ties(self):
        snapshot = _separated_numbers_snapshot()
        result = _path_result((
            ("fallback_click", 2, 0, None, 1),
            ("fallback_click", 0, 0, None, 1),
        ))
        trace = build_zini_trace(snapshot, result)
        self.assertEqual(
            tuple(step.selection for step in trace.steps),
            (ZiniTraceSelection.FALLBACK_ALT, ZiniTraceSelection.FALLBACK_GREEDY),
        )
        self.assertEqual(tuple(step.best_premium for step in trace.steps), (-2, -2))
        # Candidates include already revealed numbers: this is not target count.
        self.assertEqual(tuple(step.tie_count for step in trace.steps), (2, 2))
        self.assertEqual(trace.steps[0].newly_revealed, ((2, 0),))
        self.assertEqual(trace.steps[1].newly_revealed, ((0, 0),))
        self.assert_complete_trace(snapshot, result, trace)

    def test_trace_models_are_frozen_and_store_deltas_without_cumulative_state(self):
        for instance, name, value in (
            (self.trace, "total_clicks", 99),
            (self.trace.steps[0], "step_index", 99),
            (self.trace.steps[0].move, "clicks_added", 99),
        ):
            with self.subTest(model=type(instance).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(instance, name, value)
        self.assertIsInstance(self.trace.steps, tuple)
        step_fields = {field.name for field in fields(ZiniTraceStep)}
        self.assertTrue(step_fields.isdisjoint({
            "revealed", "flagged_mines", "cumulative_clicks", "candidate_count",
        }))

    def test_constructor_copies_mutable_step_and_delta_sequences(self):
        coordinate = [1, 0]
        revealed = [coordinate]
        flags = []
        step = replace(self.trace.steps[0], newly_revealed=revealed, newly_flagged=flags)
        steps = [step]
        trace = ZiniTrace(self.snapshot, self.result.clicks, steps)
        coordinate[0] = 99
        revealed.append((0, 0))
        flags.append((1, 1))
        steps.clear()
        self.assertEqual(trace.steps, (step,))
        self.assertEqual(step.newly_revealed, ((1, 0),))
        self.assertEqual(step.newly_flagged, ())

    def test_unknown_trace_versions_are_rejected(self):
        for field in ("schema_version", "semantics_version"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    replace(self.trace, **{field: 2})

    def test_every_frozen_v1_path_is_accepted_with_exact_moves(self):
        for name, golden in GOLDEN.items():
            with self.subTest(workload=name):
                snapshot = workload_snapshot(golden["inputs"]["board"])
                result = _path_result(golden["expected"]["moves"])
                trace = build_zini_trace(snapshot, result)
                self.assert_complete_trace(snapshot, result, trace)

    def test_expert_deterministic_125_path_has_only_greedy_choices(self):
        snapshot = _expert_seed1003_snapshot()
        result = _path_result(GOLDEN["deterministic/expert1003"]["expected"]["moves"])
        trace = build_zini_trace(snapshot, result)
        self.assertEqual((result.clicks, len(trace.steps)), (125, 87))
        self.assertEqual(Counter(step.selection for step in trace.steps), {
            ZiniTraceSelection.GREEDY: 62,
            ZiniTraceSelection.FALLBACK_GREEDY: 25,
        })
        self.assert_complete_trace(snapshot, result, trace)

    def test_historical_120_witness_has_real_tie_and_below_max_deviations(self):
        snapshot = _expert_seed1003_snapshot()
        result = _path_result(_EXPERT_SEED1003_120_TRACE)
        trace = build_zini_trace(snapshot, result)
        self.assertEqual((result.clicks, len(trace.steps)), (120, 87))
        self.assertEqual(Counter(step.selection for step in trace.steps), {
            ZiniTraceSelection.GREEDY: 55,
            ZiniTraceSelection.MAX_TIE_ALT: 2,
            ZiniTraceSelection.BELOW_MAX: 2,
            ZiniTraceSelection.FALLBACK_GREEDY: 28,
        })
        expected_deviations = (
            (0, 5, 5, 13, ZiniTraceSelection.MAX_TIE_ALT),
            (1, 3, 5, 12, ZiniTraceSelection.BELOW_MAX),
            (15, 3, 3, 9, ZiniTraceSelection.MAX_TIE_ALT),
            (23, 0, 2, 12, ZiniTraceSelection.BELOW_MAX),
        )
        for index, premium, best, ties, selection in expected_deviations:
            with self.subTest(step=index):
                step = trace.steps[index]
                self.assertEqual((step.move.premium, step.best_premium, step.tie_count,
                                  step.selection), (premium, best, ties, selection))
        self.assert_complete_trace(snapshot, result, trace)


class ZiniTraceValidationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = _center_mine_snapshot()
        self.result = calculate_g_zini(self.snapshot)

    def assert_bad_first_move(self, **changes):
        moves = (replace(self.result.moves[0], **changes), *self.result.moves[1:])
        # Keep the top-level count well typed to exercise the recorded field.
        result = ZiniResult(int(sum(move.clicks_added for move in moves)), moves)
        with self.assertRaisesRegex(ValueError, r"[Ss]tep 0"):
            build_zini_trace(self.snapshot, result)

    def test_illegal_coordinates_are_rejected(self):
        for x, y in ((1, 1), (-1, 0), (3, 0), (0, 3)):
            with self.subTest(coord=(x, y)):
                self.assert_bad_first_move(x=x, y=y)

    def test_unknown_action_and_wrong_covered_state_action_are_rejected(self):
        for action in ("unknown", "flag_chord", "fallback_click"):
            with self.subTest(action=action):
                self.assert_bad_first_move(action=action)

    def test_wrong_premium_is_rejected(self):
        for premium in (None, 1, 3):
            with self.subTest(premium=premium):
                self.assert_bad_first_move(premium=premium)

    def test_wrong_clicks_added_is_rejected_even_if_total_matches(self):
        for clicks in (0, 2):
            with self.subTest(clicks_added=clicks):
                self.assert_bad_first_move(clicks_added=clicks)

    def test_incorrect_chord_click_cost_is_rejected(self):
        moves = list(self.result.moves)
        moves[1] = replace(moves[1], clicks_added=1)
        result = ZiniResult(sum(move.clicks_added for move in moves), tuple(moves))
        with self.assertRaisesRegex(ValueError, r"[Ss]tep 1"):
            build_zini_trace(self.snapshot, result)

    def test_negative_premium_chord_is_rejected_with_nonnegative_maximum(self):
        moves = (*self.result.moves[:2], ZiniMove("flag_chord", 0, 0, -1, 1))
        result = ZiniResult(sum(move.clicks_added for move in moves), moves)
        with self.assertRaisesRegex(ValueError, r"[Ss]tep 2"):
            build_zini_trace(self.snapshot, result)

    def test_bool_and_float_fields_cannot_impersonate_recorded_integers(self):
        for changes in (
            {"x": True}, {"x": 1.0}, {"y": False}, {"y": 0.0},
            {"premium": 2.0}, {"clicks_added": True}, {"clicks_added": 1.0},
        ):
            with self.subTest(changes=changes):
                self.assert_bad_first_move(**changes)
        for total in (True, 5.0):
            with self.subTest(total=total):
                with self.assertRaises(ValueError):
                    build_zini_trace(self.snapshot, replace(self.result, clicks=total))

    def test_wrong_total_and_incomplete_trajectories_are_rejected(self):
        cases = (
            replace(self.result, clicks=self.result.clicks + 1),
            ZiniResult(0),
            ZiniResult(1, self.result.moves[:1]),
        )
        for result in cases:
            with self.subTest(result=result):
                with self.assertRaises(ValueError):
                    build_zini_trace(self.snapshot, result)

    def test_move_after_final_solved_state_is_rejected(self):
        result = ZiniResult(self.result.clicks + 1, (
            *self.result.moves, ZiniMove("fallback_click", 0, 0, None, 1),
        ))
        with self.assertRaisesRegex(ValueError, r"[Ss]tep 4"):
            build_zini_trace(self.snapshot, result)

    def test_fallback_rejects_non_targets_and_recorded_premium_or_cost(self):
        snapshot = _separated_numbers_snapshot()
        for move in (
            ZiniMove("fallback_click", 1, 0, None, 1),
            ZiniMove("fallback_click", 0, 0, -2, 1),
            ZiniMove("fallback_click", 0, 0, None, 2),
            ZiniMove("click", 0, 0, -2, 1),
        ):
            with self.subTest(move=move):
                with self.assertRaisesRegex(ValueError, r"[Ss]tep 0"):
                    build_zini_trace(snapshot, ZiniResult(move.clicks_added, (move,)))

    def test_fallback_rejects_already_revealed_target(self):
        snapshot = _separated_numbers_snapshot()
        move = ZiniMove("fallback_click", 0, 0, None, 1)
        with self.assertRaisesRegex(ValueError, r"[Ss]tep 1"):
            build_zini_trace(snapshot, ZiniResult(2, (move, move)))

    def test_unplaced_snapshot_is_rejected(self):
        with self.assertRaises(ValueError):
            build_zini_trace(replace(self.snapshot, mines_placed=False), self.result)


class ZiniTracePlayerTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = _center_mine_snapshot()
        self.trace = build_zini_trace(self.snapshot, calculate_g_zini(self.snapshot))
        self.player = ZiniTracePlayer(self.trace)

    def test_index_zero_is_empty_with_no_current_step(self):
        self.assertIs(self.player.trace, self.trace)
        self.assertEqual(self.player.step_count, 4)
        self.assertEqual(self.player.current_index, 0)
        self.assertIsNone(self.player.current_step)
        self.assertEqual(self.player.revealed, frozenset())
        self.assertEqual(self.player.flagged_mines, frozenset())

    def test_next_previous_and_boundaries(self):
        self.assertFalse(self.player.previous())
        self.assertTrue(self.player.next())
        self.assertEqual(self.player.current_index, 1)
        self.assertEqual(self.player.current_step, self.trace.steps[0])
        self.assertEqual(self.player.revealed, frozenset({(1, 0)}))
        self.assertTrue(self.player.next())
        self.assertEqual(self.player.flagged_mines, frozenset({(1, 1)}))
        self.assertTrue(self.player.previous())
        self.assertEqual(self.player.current_index, 1)
        self.assertEqual(self.player.revealed, frozenset({(1, 0)}))
        self.assertEqual(self.player.flagged_mines, frozenset())
        self.player.go_to(self.player.step_count)
        before = (self.player.revealed, self.player.flagged_mines)
        self.assertFalse(self.player.next())
        self.assertEqual((self.player.revealed, self.player.flagged_mines), before)

    def test_go_to_first_middle_final_and_back(self):
        expected = {
            0: (frozenset(), frozenset()),
            2: (frozenset({(1, 0), (0, 0), (2, 0), (0, 1), (2, 1)}),
                frozenset({(1, 1)})),
            4: (frozenset({(0, 0), (1, 0), (2, 0), (0, 1), (2, 1),
                           (0, 2), (1, 2), (2, 2)}), frozenset({(1, 1)})),
        }
        for index in (0, 2, 4, 2, 0, 4):
            with self.subTest(index=index):
                self.player.go_to(index)
                self.assertEqual(self.player.current_index, index)
                self.assertEqual((self.player.revealed, self.player.flagged_mines),
                                 expected[index])
                self.assertEqual(self.player.current_step,
                                 None if index == 0 else self.trace.steps[index - 1])

    def test_invalid_indices_fail_without_changing_state(self):
        self.player.go_to(2)
        before = (self.player.current_index, self.player.revealed, self.player.flagged_mines)
        for index in (-1, 5, 1.0, True, None, "2"):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    self.player.go_to(index)
                self.assertEqual((self.player.current_index, self.player.revealed,
                                  self.player.flagged_mines), before)

    def test_exposed_states_are_immutable_and_do_not_change_retroactively(self):
        self.player.go_to(2)
        old_revealed = self.player.revealed
        old_flags = self.player.flagged_mines
        for cells in (old_revealed, old_flags):
            self.assertIsInstance(cells, frozenset)
            with self.assertRaises(AttributeError):
                cells.add((99, 99))
        for attribute, value in (
            ("current_index", 99), ("revealed", set()),
            ("flagged_mines", set()), ("trace", None),
        ):
            with self.subTest(attribute=attribute):
                with self.assertRaises(AttributeError):
                    setattr(self.player, attribute, value)
        self.player.go_to(0)
        self.assertEqual(len(old_revealed), 5)
        self.assertEqual(old_flags, frozenset({(1, 1)}))

    def test_playback_applies_only_deltas_without_rebuilding_board_semantics(self):
        with ExitStack() as stack:
            for target in (
                "zini_trace._build_premium_context",
                "zini_trace._find_premium_candidates",
                "zini_trace._apply_premium_candidate",
                "zini_trace._click_fallback_cell",
                "zini_trace.build_zini_trace",
            ):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            player = ZiniTracePlayer(self.trace)
            for index in range(player.step_count + 1):
                player.go_to(index)
            while player.previous():
                pass
        self.assertEqual(player.current_index, 0)
        self.assertEqual(player.revealed, frozenset())

    def test_empty_trace_boundaries(self):
        snapshot = BoardSnapshot(1, 1, 1, True, frozenset({(0, 0)}), ((0,),))
        player = ZiniTracePlayer(build_zini_trace(snapshot, ZiniResult(0)))
        player.go_to(0)
        self.assertFalse(player.next())
        self.assertFalse(player.previous())
        self.assertEqual(player.step_count, 0)
        self.assertIsNone(player.current_step)


class ZiniTraceIsolationTests(unittest.TestCase):
    def test_builder_never_runs_search_or_uses_randomness(self):
        snapshot = _expert_seed1003_snapshot()
        result = _path_result(_EXPERT_SEED1003_120_TRACE)
        before = deepcopy(result)
        random_state = random.getstate()
        with ExitStack() as stack:
            for target in (
                "random.Random.seed", "random.Random.random", "random.Random.getrandbits",
                "random.random", "random.choice", "random.sample", "random.randrange",
                "zini_calculator.calculate_g_zini",
                "zini_calculator.calculate_g_zini_min_ties_bounded",
                "zini_calculator.calculate_g_zini_neighborhood_beam_bounded",
                "zini_min_ties._MinTieSearch.find_best_moves",
                "zini_advanced._NeighborhoodBeamSearch.run",
            ):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            trace = build_zini_trace(snapshot, result)
            self.assertEqual(trace, build_zini_trace(snapshot, result))
        self.assertEqual(result, before)
        self.assertEqual(random.getstate(), random_state)

    def check_fresh_workload_before_and_after_trace(self, name):
        inputs = WORKLOADS[name]
        output = run_workload(inputs)
        before = deepcopy(output)
        expected = GOLDEN[name]["expected"]
        assert_golden_equal(self, expected, canonical_output(output), workload=name)
        result = output if isinstance(output, ZiniResult) else output.result
        snapshot = workload_snapshot(inputs["board"])
        trace = build_zini_trace(snapshot, result)
        self.assertEqual(output, before)  # Includes original elapsed time/config.
        self.assertEqual(tuple(step.move for step in trace.steps), result.moves)
        fresh_output = run_workload(inputs)
        assert_golden_equal(self, expected, canonical_output(fresh_output), workload=name)
        self.assertEqual(canonical_output(output), canonical_output(fresh_output))

    def test_deterministic_trace_off_on_equivalence_matches_v1_golden(self):
        for name in ("deterministic/board_c", "deterministic/expert1003"):
            with self.subTest(workload=name):
                self.check_fresh_workload_before_and_after_trace(name)

    def test_all_fixed_20_evaluation_advanced_policies_preserve_exact_output(self):
        for policy in ("standard_v1", "chain_v1", "standard_seeded_chain_v1"):
            with self.subTest(policy=policy):
                name = f"advanced/expert1003/{policy}"
                self.assertEqual(WORKLOADS[name]["config"]["max_evaluations"], 20)
                self.check_fresh_workload_before_and_after_trace(name)


if __name__ == "__main__":
    unittest.main()
