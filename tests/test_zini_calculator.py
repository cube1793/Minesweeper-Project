import unittest
from dataclasses import FrozenInstanceError

from board_snapshot import BoardSnapshot
from zini_calculator import (
    ZiniAdvancedSearchResult,
    ZiniAdvancedTerminationReason,
    ZiniNeighborhoodBeamConfig,
    ZiniResult,
    ZiniSearchResult,
    _AdvancedTrajectory,
    _apply_premium_candidate,
    _collect_neighborhood_decisions,
    _extract_static_3bv_units,
    _build_premium_context,
    _copy_zini_state,
    _find_premium_candidates,
    _find_fallback_click_targets,
    _get_neighborhood_policy,
    _PremiumCandidate,
    _StandardNeighborhoodPolicyV1,
    _ZiniBoardState,
    _apply_next_g_zini_move,
    _calculate_premium,
    _click_covered_candidate,
    _click_fallback_cell,
    _flag_and_chord_uncovered_candidate,
    _select_fallback_click_target,
    _select_best_premium_candidate,
    _validate_neighborhood_beam_config,
    _zini_state_key,
    calculate_g_zini,
    calculate_g_zini_neighborhood_beam_bounded,
    calculate_g_zini_min_ties,
    calculate_g_zini_min_ties_bounded,
)


def _move_signature(result):
    return tuple(
        (move.action, move.x, move.y, move.premium, move.clicks_added)
        for move in result.moves
    )


def _advanced_search_snapshot():
    return BoardSnapshot(
        width=4,
        height=4,
        num_mines=3,
        mines_placed=True,
        mines=frozenset({(2, 0), (2, 2), (3, 3)}),
        adjacent=(
            (0, 1, 0, 1),
            (0, 2, 2, 2),
            (0, 1, 0, 2),
            (0, 1, 2, 0),
        ),
    )


def _board_c_snapshot():
    return BoardSnapshot(
        width=9,
        height=9,
        num_mines=10,
        mines_placed=True,
        mines=frozenset(
            {
                (1, 0),
                (6, 0),
                (3, 1),
                (8, 2),
                (0, 3),
                (5, 4),
                (2, 5),
                (7, 6),
                (4, 7),
                (0, 8),
            }
        ),
        adjacent=(
            (1, 0, 2, 1, 1, 1, 0, 1, 0),
            (1, 1, 2, 0, 1, 1, 1, 2, 1),
            (1, 1, 1, 1, 1, 0, 0, 1, 0),
            (0, 1, 0, 0, 1, 1, 1, 1, 1),
            (1, 2, 1, 1, 1, 0, 1, 0, 0),
            (0, 1, 0, 1, 1, 1, 2, 1, 1),
            (0, 1, 1, 2, 1, 1, 1, 0, 1),
            (1, 1, 0, 1, 0, 1, 1, 1, 1),
            (0, 1, 0, 1, 1, 1, 0, 0, 0),
        ),
    )


def _replay_zini_result(snapshot, result):
    state = _ZiniBoardState.create(snapshot)
    context = _build_premium_context(snapshot)

    for expected in result.moves:
        candidates = _find_premium_candidates(state, context)
        best_premium = max(
            (candidate.premium for candidate in candidates),
            default=None,
        )
        coord = (expected.x, expected.y)

        if expected.action == "fallback_click":
            if best_premium is not None and best_premium >= 0:
                raise AssertionError(
                    "Fallback move used with non-negative Premium."
                )
            if coord not in _find_fallback_click_targets(state, context):
                raise AssertionError("Fallback move target is unavailable.")
            actual = _click_fallback_cell(state, coord, context)
        else:
            matching = tuple(
                candidate
                for candidate in candidates
                if candidate.coord == coord
            )
            if len(matching) != 1:
                raise AssertionError("Premium move target is unavailable.")
            actual = _apply_premium_candidate(state, matching[0], context)

        if actual != expected:
            raise AssertionError("Replayed move does not match result trace.")

    return state


_EXPERT_SEED1003_MINES = frozenset(
    {
        (0, 0), (12, 0), (13, 0), (16, 0), (0, 1), (1, 1),
        (2, 1), (3, 1), (14, 1), (19, 1), (7, 2), (8, 2),
        (9, 2), (11, 2), (16, 2), (2, 3), (10, 3), (11, 3),
        (13, 3), (23, 3), (26, 3), (27, 3), (2, 4), (3, 4),
        (8, 4), (10, 4), (11, 4), (17, 4), (18, 4), (1, 5),
        (13, 5), (21, 5), (23, 5), (24, 5), (25, 5), (4, 6),
        (6, 6), (13, 6), (14, 6), (17, 6), (18, 6), (20, 6),
        (26, 6), (27, 6), (8, 7), (10, 7), (11, 7), (12, 7),
        (18, 7), (21, 7), (22, 7), (27, 7), (3, 8), (14, 8),
        (17, 8), (19, 8), (20, 8), (21, 8), (5, 9), (6, 9),
        (9, 9), (11, 9), (12, 9), (16, 9), (27, 9), (28, 9),
        (17, 10), (26, 10), (29, 10), (13, 11), (16, 11),
        (19, 11), (20, 11), (22, 11), (25, 11), (27, 11),
        (7, 12), (9, 12), (12, 12), (20, 12), (26, 12),
        (1, 13), (4, 13), (17, 13), (26, 13), (1, 14),
        (11, 14), (25, 14), (27, 14), (1, 15), (9, 15),
        (12, 15), (13, 15), (14, 15), (18, 15), (21, 15),
        (22, 15), (23, 15), (28, 15),
    }
)


_EXPERT_SEED1003_120_TRACE = (
    ("click", 19, 14, 5, 1),
    ("click", 5, 7, 3, 1),
    ("click", 8, 9, 5, 1),
    ("flag_chord", 8, 9, 5, 2),
    ("click", 14, 9, 5, 1),
    ("flag_chord", 14, 9, 5, 2),
    ("click", 11, 11, 5, 1),
    ("flag_chord", 11, 11, 5, 2),
    ("flag_chord", 19, 14, 5, 2),
    ("click", 18, 1, 4, 1),
    ("flag_chord", 18, 1, 4, 2),
    ("click", 8, 6, 4, 1),
    ("flag_chord", 8, 6, 4, 2),
    ("click", 11, 5, 3, 1),
    ("flag_chord", 11, 5, 3, 3),
    ("click", 19, 10, 3, 1),
    ("click", 16, 6, 3, 1),
    ("flag_chord", 16, 6, 3, 2),
    ("flag_chord", 5, 7, 3, 3),
    ("flag_chord", 19, 10, 3, 3),
    ("click", 10, 14, 3, 1),
    ("flag_chord", 10, 14, 3, 3),
    ("click", 13, 2, 2, 1),
    ("flag_chord", 15, 8, 0, 2),
    ("flag_chord", 13, 2, 2, 3),
    ("flag_chord", 14, 3, 2, 1),
    ("click", 24, 3, 2, 1),
    ("flag_chord", 24, 3, 2, 2),
    ("click", 19, 4, 2, 1),
    ("flag_chord", 19, 4, 3, 2),
    ("click", 2, 6, 2, 1),
    ("flag_chord", 2, 6, 3, 2),
    ("flag_chord", 8, 10, 2, 1),
    ("flag_chord", 20, 10, 2, 1),
    ("flag_chord", 18, 11, 2, 2),
    ("click", 24, 12, 2, 1),
    ("flag_chord", 24, 12, 3, 2),
    ("click", 15, 0, 1, 1),
    ("flag_chord", 15, 0, 1, 2),
    ("flag_chord", 15, 10, 1, 2),
    ("flag_chord", 11, 13, 1, 1),
    ("click", 25, 15, 1, 1),
    ("flag_chord", 25, 15, 1, 2),
    ("click", 4, 1, 0, 1),
    ("flag_chord", 4, 1, 1, 2),
    ("flag_chord", 4, 2, 0, 1),
    ("flag_chord", 18, 2, 0, 1),
    ("click", 0, 4, 0, 1),
    ("flag_chord", 0, 4, 1, 1),
    ("click", 27, 4, 0, 1),
    ("flag_chord", 27, 4, 0, 3),
    ("flag_chord", 10, 5, 0, 1),
    ("flag_chord", 9, 8, 0, 2),
    ("flag_chord", 16, 10, 0, 1),
    ("click", 28, 11, 0, 1),
    ("flag_chord", 28, 11, 1, 3),
    ("flag_chord", 1, 12, 0, 2),
    ("flag_chord", 2, 12, 0, 1),
    ("flag_chord", 28, 12, 0, 1),
    ("fallback_click", 1, 0, None, 1),
    ("fallback_click", 2, 0, None, 1),
    ("fallback_click", 2, 2, None, 1),
    ("fallback_click", 10, 2, None, 1),
    ("fallback_click", 8, 3, None, 1),
    ("fallback_click", 9, 3, None, 1),
    ("fallback_click", 22, 5, None, 1),
    ("fallback_click", 19, 6, None, 1),
    ("fallback_click", 21, 6, None, 1),
    ("fallback_click", 22, 6, None, 1),
    ("fallback_click", 13, 7, None, 1),
    ("fallback_click", 19, 7, None, 1),
    ("fallback_click", 20, 7, None, 1),
    ("fallback_click", 24, 7, None, 1),
    ("fallback_click", 11, 8, None, 1),
    ("fallback_click", 12, 8, None, 1),
    ("fallback_click", 18, 8, None, 1),
    ("fallback_click", 27, 8, None, 1),
    ("fallback_click", 29, 9, None, 1),
    ("fallback_click", 26, 11, None, 1),
    ("fallback_click", 8, 12, None, 1),
    ("fallback_click", 14, 13, None, 1),
    ("fallback_click", 0, 14, None, 1),
    ("fallback_click", 6, 14, None, 1),
    ("fallback_click", 0, 15, None, 1),
    ("fallback_click", 16, 15, None, 1),
    ("fallback_click", 27, 15, None, 1),
    ("fallback_click", 29, 15, None, 1),
)


def _expert_seed1003_snapshot():
    width = 30
    height = 16
    mines = _EXPERT_SEED1003_MINES

    if len(mines) != 99:
        raise AssertionError("Expert seed 1003 fixture must contain 99 mines.")
    if any(not (0 <= x < width and 0 <= y < height) for x, y in mines):
        raise AssertionError("Expert seed 1003 mine is outside the 30x16 board.")

    adjacent = tuple(
        tuple(
            0
            if (x, y) in mines
            else sum(
                (nx, ny) in mines
                for ny in range(max(0, y - 1), min(height, y + 2))
                for nx in range(max(0, x - 1), min(width, x + 2))
                if (nx, ny) != (x, y)
            )
            for x in range(width)
        )
        for y in range(height)
    )

    return BoardSnapshot(
        width=width,
        height=height,
        num_mines=99,
        mines_placed=True,
        mines=mines,
        adjacent=adjacent,
    )


class ZiniCalculatorTests(unittest.TestCase):
    def test_neighborhood_policy_dispatches_standard_v1(self):
        policy = _get_neighborhood_policy(ZiniNeighborhoodBeamConfig())

        self.assertIsInstance(policy, _StandardNeighborhoodPolicyV1)

    def test_standard_v1_board_c_small_budget_trace_is_stable(self):
        config = ZiniNeighborhoodBeamConfig(
            max_seconds=None,
            max_evaluations=20,
            stall_seconds=None,
            seed=1234,
        )

        search = calculate_g_zini_neighborhood_beam_bounded(
            _board_c_snapshot(),
            config=config,
        )

        self.assertFalse(search.exact)
        self.assertEqual(
            search.termination_reason,
            ZiniAdvancedTerminationReason.EVALUATION_LIMIT,
        )
        self.assertEqual(search.best_clicks, 16)
        self.assertEqual(search.evaluations, 20)
        self.assertEqual(search.generations, 2)
        self.assertEqual(
            _move_signature(search.result),
            (
                ("click", 5, 7, 2, 1),
                ("click", 1, 1, 3, 1),
                ("flag_chord", 1, 1, 3, 2),
                ("flag_chord", 5, 7, 3, 2),
                ("flag_chord", 4, 6, 2, 1),
                ("click", 4, 1, 1, 1),
                ("flag_chord", 4, 1, 2, 2),
                ("flag_chord", 2, 2, 0, 1),
                ("flag_chord", 3, 7, 0, 1),
                ("fallback_click", 8, 0, None, 1),
                ("fallback_click", 7, 4, None, 1),
                ("fallback_click", 0, 5, None, 1),
                ("fallback_click", 8, 6, None, 1),
            ),
        )

    def test_neighborhood_beam_rejects_unplaced_snapshot(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=False,
            mines=frozenset(),
            adjacent=((0, 0), (0, 0)),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini_neighborhood_beam_bounded(snapshot)

    def test_neighborhood_beam_default_config_returns_valid_result(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        search = calculate_g_zini_neighborhood_beam_bounded(snapshot)

        self.assertIsInstance(search, ZiniAdvancedSearchResult)
        self.assertFalse(search.exact)
        self.assertEqual(
            search.termination_reason,
            ZiniAdvancedTerminationReason.SEARCH_EXHAUSTED,
        )
        self.assertEqual(search.result.clicks, search.best_clicks)
        self.assertLessEqual(search.best_clicks, search.deterministic_clicks)
        self.assertEqual(
            search.result.clicks,
            sum(move.clicks_added for move in search.result.moves),
        )

    def test_neighborhood_beam_zero_evaluations_returns_baseline(self):
        snapshot = _advanced_search_snapshot()
        baseline = calculate_g_zini(snapshot)
        config = ZiniNeighborhoodBeamConfig(
            max_seconds=None,
            max_evaluations=0,
        )

        search = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=config,
        )

        self.assertEqual(
            search.termination_reason,
            ZiniAdvancedTerminationReason.EVALUATION_LIMIT,
        )
        self.assertEqual(search.evaluations, 0)
        self.assertEqual(search.result, baseline)

    def test_neighborhood_beam_zero_seconds_returns_baseline(self):
        snapshot = _advanced_search_snapshot()
        baseline = calculate_g_zini(snapshot)
        config = ZiniNeighborhoodBeamConfig(
            max_seconds=0,
            max_evaluations=0,
            stall_seconds=0,
        )

        search = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=config,
        )

        self.assertEqual(
            search.termination_reason,
            ZiniAdvancedTerminationReason.TIME_LIMIT,
        )
        self.assertEqual(search.evaluations, 0)
        self.assertEqual(search.result, baseline)

    def test_neighborhood_beam_zero_stall_returns_baseline(self):
        snapshot = _advanced_search_snapshot()
        baseline = calculate_g_zini(snapshot)
        config = ZiniNeighborhoodBeamConfig(
            max_seconds=None,
            max_evaluations=20,
            stall_seconds=0,
        )

        search = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=config,
        )

        self.assertEqual(
            search.termination_reason,
            ZiniAdvancedTerminationReason.STALL_LIMIT,
        )
        self.assertEqual(search.evaluations, 0)
        self.assertEqual(search.result, baseline)

    def test_neighborhood_beam_is_reproducible_with_fixed_evaluation_budget(self):
        snapshot = _advanced_search_snapshot()
        config = ZiniNeighborhoodBeamConfig(
            max_seconds=None,
            max_evaluations=20,
            seed=1234,
        )

        first = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=config,
        )
        second = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=config,
        )

        self.assertEqual(first.best_clicks, second.best_clicks)
        self.assertEqual(
            _move_signature(first.result),
            _move_signature(second.result),
        )
        self.assertEqual(first.evaluations, second.evaluations)
        self.assertEqual(first.generations, second.generations)

    def test_neighborhood_beam_result_replays_with_current_move_semantics(self):
        snapshot = _advanced_search_snapshot()
        config = ZiniNeighborhoodBeamConfig(
            max_seconds=None,
            max_evaluations=20,
            seed=7,
        )

        search = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=config,
        )
        state = _replay_zini_result(snapshot, search.result)

        self.assertTrue(state.all_safe_cells_revealed())
        self.assertTrue(state.flagged_mines <= snapshot.mines)
        self.assertLessEqual(search.best_clicks, search.deterministic_clicks)
        self.assertEqual(
            search.result.clicks,
            sum(move.clicks_added for move in search.result.moves),
        )

    def test_neighborhood_decisions_copy_state_and_exclude_original_move(self):
        snapshot = _advanced_search_snapshot()
        result = calculate_g_zini(snapshot)
        context = _build_premium_context(snapshot)
        decisions = _collect_neighborhood_decisions(
            snapshot,
            context,
            _AdvancedTrajectory(result),
            ZiniNeighborhoodBeamConfig(),
        )

        self.assertGreater(len(decisions), 1)
        self.assertEqual(
            len({id(decision.state) for decision in decisions}),
            len(decisions),
        )
        for decision in decisions:
            original = result.moves[decision.step_index]
            original_coord = (original.x, original.y)
            self.assertTrue(
                all(
                    alternative.coord != original_coord
                    for alternative in decision.alternatives
                )
            )

    def test_neighborhood_fallback_alternatives_exclude_original_target(self):
        snapshot = BoardSnapshot(
            width=3,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0, 1),),
        )
        result = calculate_g_zini(snapshot)
        context = _build_premium_context(snapshot)

        decisions = _collect_neighborhood_decisions(
            snapshot,
            context,
            _AdvancedTrajectory(result),
            ZiniNeighborhoodBeamConfig(),
        )

        self.assertEqual((result.moves[0].x, result.moves[0].y), (0, 0))
        self.assertEqual(len(decisions), 1)
        self.assertEqual(
            tuple(
                alternative.coord
                for alternative in decisions[0].alternatives
            ),
            ((2, 0),),
        )

    def test_neighborhood_beam_config_has_safe_defaults(self):
        config = ZiniNeighborhoodBeamConfig()

        self.assertEqual(config.premium_window, 2)
        self.assertEqual(config.beam_size, 8)
        self.assertEqual(config.max_decision_points, 6)
        self.assertEqual(config.max_alternatives_per_point, 3)
        self.assertEqual(config.prefix_diversity_length, 20)
        self.assertEqual(config.retain_click_margin, 3)
        self.assertEqual(config.max_seconds, 5.0)
        self.assertEqual(config.max_evaluations, 500)
        self.assertIsNone(config.stall_seconds)
        self.assertEqual(config.seed, 0)
        self.assertEqual(config.ranking_policy, "standard_v1")
        self.assertIsNone(_validate_neighborhood_beam_config(config))

    def test_neighborhood_beam_config_is_frozen(self):
        config = ZiniNeighborhoodBeamConfig()

        with self.assertRaises(FrozenInstanceError):
            config.beam_size = 16

    def test_neighborhood_beam_config_accepts_zero_execution_budgets(self):
        config = ZiniNeighborhoodBeamConfig(
            max_seconds=0,
            max_evaluations=0,
            stall_seconds=0,
        )

        self.assertIsNone(_validate_neighborhood_beam_config(config))

    def test_neighborhood_beam_config_rejects_invalid_values(self):
        invalid_configs = (
            {"premium_window": -1},
            {"beam_size": 0},
            {"max_decision_points": 0},
            {"max_alternatives_per_point": 0},
            {"prefix_diversity_length": 0},
            {"retain_click_margin": -1},
            {"max_seconds": -1},
            {"max_evaluations": -1},
            {"stall_seconds": -1},
            {
                "max_seconds": None,
                "max_evaluations": None,
                "stall_seconds": None,
            },
            {"ranking_policy": "unknown"},
        )

        for values in invalid_configs:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    ZiniNeighborhoodBeamConfig(**values)

    def test_advanced_termination_reason_values_are_stable(self):
        self.assertEqual(
            tuple(reason.value for reason in ZiniAdvancedTerminationReason),
            (
                "time_limit",
                "evaluation_limit",
                "stall_limit",
                "search_exhausted",
            ),
        )

    def test_advanced_search_result_stores_best_so_far_metadata(self):
        config = ZiniNeighborhoodBeamConfig()
        result = ZiniAdvancedSearchResult(
            result=ZiniResult(clicks=1),
            exact=False,
            termination_reason=ZiniAdvancedTerminationReason.SEARCH_EXHAUSTED,
            elapsed_seconds=0.1,
            evaluations=2,
            generations=1,
            best_clicks=1,
            deterministic_clicks=2,
            strategy_name="neighborhood_beam",
            strategy_version="1",
            config=config,
        )

        self.assertFalse(result.exact)
        self.assertEqual(result.best_clicks, result.result.clicks)
        self.assertIs(result.config, config)

    def test_copy_zini_state_preserves_key_without_sharing_mutable_sets(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        state.flag_mine((1, 0))

        copied = _copy_zini_state(state)

        self.assertEqual(_zini_state_key(copied), _zini_state_key(state))
        self.assertIsNot(copied.revealed, state.revealed)
        self.assertIsNot(copied.flagged_mines, state.flagged_mines)

    def test_apply_premium_candidate_preserves_covered_then_revealed_routing(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        candidate = _PremiumCandidate(coord=(0, 0), premium=0)

        click = _apply_premium_candidate(state, candidate, context)
        flag_chord = _apply_premium_candidate(state, candidate, context)

        self.assertEqual(click.action, "click")
        self.assertEqual(click.clicks_added, 1)
        self.assertEqual(flag_chord.action, "flag_chord")
        self.assertEqual(flag_chord.clicks_added, 2)
        self.assertEqual(state.revealed, {(0, 0)})
        self.assertEqual(state.flagged_mines, {(1, 0)})

    def test_unplaced_snapshot_is_not_calculable(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=False,
            mines=frozenset(),
            adjacent=((0, 0), (0, 0)),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini(snapshot)

    def test_calculate_g_zini_empty_board_returns_one_fallback_click(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        result = calculate_g_zini(snapshot)

        self.assertIsInstance(result, ZiniResult)
        self.assertIsInstance(result.moves, tuple)
        self.assertEqual(result.clicks, 1)
        self.assertEqual(len(result.moves), 1)
        self.assertEqual(_move_signature(result), (("fallback_click", 0, 0, None, 1),))
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_calculate_g_zini_two_cell_mine_board_uses_negative_premium_fallback(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )

        result = calculate_g_zini(snapshot)

        self.assertEqual(result.clicks, 1)
        self.assertEqual(len(result.moves), 1)
        self.assertEqual(_move_signature(result), (("fallback_click", 0, 0, None, 1),))
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_calculate_g_zini_center_mine_board_matches_expected_trace(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )

        result = calculate_g_zini(snapshot)

        self.assertEqual(result.clicks, 5)
        self.assertEqual(len(result.moves), 4)
        self.assertEqual(
            _move_signature(result),
            (
                ("click", 1, 0, 2, 1),
                ("flag_chord", 1, 0, 2, 2),
                ("flag_chord", 0, 1, 1, 1),
                ("flag_chord", 2, 1, 0, 1),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )
        self.assertTrue(all(move.clicks_added > 0 for move in result.moves))

    def test_calculate_g_zini_corner_opening_board_matches_expected_trace(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )

        result = calculate_g_zini(snapshot)

        self.assertEqual(result.clicks, 1)
        self.assertEqual(len(result.moves), 1)
        self.assertEqual(
            _move_signature(result),
            (
                ("fallback_click", 2, 0, None, 1),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )
        self.assertTrue(all(move.clicks_added > 0 for move in result.moves))

    def test_calculate_g_zini_min_ties_rejects_unplaced_snapshot(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=False,
            mines=frozenset(),
            adjacent=((0, 0), (0, 0)),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini_min_ties(snapshot)

    def test_calculate_g_zini_min_ties_d1_matches_expected_trace(self):
        snapshot = BoardSnapshot(
            width=5,
            height=5,
            num_mines=2,
            mines_placed=True,
            mines=frozenset({(1, 0), (1, 3)}),
            adjacent=(
                (1, 0, 1, 0, 0),
                (1, 1, 1, 0, 0),
                (1, 1, 1, 0, 0),
                (1, 0, 1, 0, 0),
                (1, 1, 1, 0, 0),
            ),
        )

        result = calculate_g_zini_min_ties(snapshot)

        self.assertEqual(result.clicks, 6)
        self.assertEqual(len(result.moves), 5)
        self.assertEqual(
            _move_signature(result),
            (
                ("click", 0, 2, 2, 1),
                ("flag_chord", 0, 2, 2, 2),
                ("flag_chord", 0, 3, 1, 1),
                ("fallback_click", 0, 0, None, 1),
                ("fallback_click", 3, 0, None, 1),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_calculate_g_zini_min_ties_d2_matches_expected_trace(self):
        snapshot = BoardSnapshot(
            width=4,
            height=4,
            num_mines=3,
            mines_placed=True,
            mines=frozenset({(2, 0), (2, 2), (3, 3)}),
            adjacent=(
                (0, 1, 0, 1),
                (0, 2, 2, 2),
                (0, 1, 0, 2),
                (0, 1, 2, 0),
            ),
        )

        result = calculate_g_zini_min_ties(snapshot)

        self.assertEqual(result.clicks, 5)
        self.assertEqual(len(result.moves), 3)
        self.assertEqual(
            _move_signature(result),
            (
                ("click", 2, 1, 0, 1),
                ("flag_chord", 2, 1, 0, 3),
                ("flag_chord", 1, 2, 1, 1),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_calculate_g_zini_min_ties_d3_matches_expected_trace(self):
        snapshot = BoardSnapshot(
            width=4,
            height=4,
            num_mines=3,
            mines_placed=True,
            mines=frozenset({(3, 0), (2, 1), (2, 3)}),
            adjacent=(
                (0, 1, 2, 0),
                (0, 1, 0, 2),
                (0, 2, 2, 2),
                (0, 1, 0, 1),
            ),
        )

        result = calculate_g_zini_min_ties(snapshot)

        self.assertEqual(result.clicks, 5)
        self.assertEqual(len(result.moves), 3)
        self.assertEqual(
            _move_signature(result),
            (
                ("click", 1, 1, 0, 1),
                ("flag_chord", 1, 1, 1, 2),
                ("flag_chord", 2, 2, 1, 2),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_calculate_g_zini_min_ties_board_c_matches_expected_trace(self):
        snapshot = BoardSnapshot(
            width=9,
            height=9,
            num_mines=10,
            mines_placed=True,
            mines=frozenset(
                {
                    (1, 0),
                    (6, 0),
                    (3, 1),
                    (8, 2),
                    (0, 3),
                    (5, 4),
                    (2, 5),
                    (7, 6),
                    (4, 7),
                    (0, 8),
                }
            ),
            adjacent=(
                (1, 0, 2, 1, 1, 1, 0, 1, 0),
                (1, 1, 2, 0, 1, 1, 1, 2, 1),
                (1, 1, 1, 1, 1, 0, 0, 1, 0),
                (0, 1, 0, 0, 1, 1, 1, 1, 1),
                (1, 2, 1, 1, 1, 0, 1, 0, 0),
                (0, 1, 0, 1, 1, 1, 2, 1, 1),
                (0, 1, 1, 2, 1, 1, 1, 0, 1),
                (1, 1, 0, 1, 0, 1, 1, 1, 1),
                (0, 1, 0, 1, 1, 1, 0, 0, 0),
            ),
        )

        result = calculate_g_zini_min_ties(snapshot)

        self.assertEqual(result.clicks, 16)
        self.assertEqual(len(result.moves), 13)
        self.assertEqual(
            _move_signature(result),
            (
                ("click", 1, 1, 3, 1),
                ("flag_chord", 1, 1, 3, 2),
                ("click", 4, 6, 2, 1),
                ("flag_chord", 4, 6, 2, 2),
                ("flag_chord", 5, 7, 2, 1),
                ("click", 4, 1, 1, 1),
                ("flag_chord", 4, 1, 2, 2),
                ("flag_chord", 2, 2, 0, 1),
                ("flag_chord", 3, 7, 0, 1),
                ("fallback_click", 8, 0, None, 1),
                ("fallback_click", 7, 4, None, 1),
                ("fallback_click", 0, 5, None, 1),
                ("fallback_click", 8, 6, None, 1),
            ),
        )
        self.assertEqual(
            result.clicks,
            sum(move.clicks_added for move in result.moves),
        )

    def test_bounded_min_ties_finishes_exactly_on_small_board(self):
        snapshot = BoardSnapshot(
            width=4,
            height=4,
            num_mines=3,
            mines_placed=True,
            mines=frozenset({(2, 0), (2, 2), (3, 3)}),
            adjacent=(
                (0, 1, 0, 1),
                (0, 2, 2, 2),
                (0, 1, 0, 2),
                (0, 1, 2, 0),
            ),
        )

        search = calculate_g_zini_min_ties_bounded(snapshot)

        self.assertIsInstance(search, ZiniSearchResult)
        self.assertTrue(search.exact)
        self.assertFalse(search.timed_out)
        self.assertFalse(search.state_limited)
        self.assertEqual(search.result.clicks, 5)
        self.assertEqual(search.best_clicks, 5)
        self.assertEqual(search.deterministic_clicks, 6)
        self.assertGreaterEqual(search.elapsed_seconds, 0)
        self.assertGreater(search.unique_states, 0)
        self.assertGreater(search.search_calls, 0)
        self.assertEqual(
            search.result.clicks,
            sum(move.clicks_added for move in search.result.moves),
        )

    def test_bounded_min_ties_stops_at_state_limit(self):
        snapshot = BoardSnapshot(
            width=4,
            height=4,
            num_mines=3,
            mines_placed=True,
            mines=frozenset({(2, 0), (2, 2), (3, 3)}),
            adjacent=(
                (0, 1, 0, 1),
                (0, 2, 2, 2),
                (0, 1, 0, 2),
                (0, 1, 2, 0),
            ),
        )

        search = calculate_g_zini_min_ties_bounded(snapshot, max_states=1)

        self.assertFalse(search.exact)
        self.assertFalse(search.timed_out)
        self.assertTrue(search.state_limited)
        self.assertEqual(search.unique_states, 1)
        self.assertLessEqual(
            search.result.clicks,
            search.deterministic_clicks,
        )

    def test_bounded_min_ties_stops_at_time_limit(self):
        snapshot = BoardSnapshot(
            width=4,
            height=4,
            num_mines=3,
            mines_placed=True,
            mines=frozenset({(2, 0), (2, 2), (3, 3)}),
            adjacent=(
                (0, 1, 0, 1),
                (0, 2, 2, 2),
                (0, 1, 0, 2),
                (0, 1, 2, 0),
            ),
        )

        search = calculate_g_zini_min_ties_bounded(snapshot, max_seconds=0.0)

        self.assertFalse(search.exact)
        self.assertTrue(search.timed_out)
        self.assertFalse(search.state_limited)
        self.assertEqual(search.unique_states, 0)
        self.assertLessEqual(
            search.result.clicks,
            search.deterministic_clicks,
        )

    def test_bounded_min_ties_rejects_unplaced_snapshot(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=False,
            mines=frozenset(),
            adjacent=((0, 0), (0, 0)),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini_min_ties_bounded(snapshot)

    def test_bounded_min_ties_rejects_negative_seconds(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini_min_ties_bounded(snapshot, max_seconds=-1)

    def test_bounded_min_ties_rejects_negative_states(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini_min_ties_bounded(snapshot, max_states=-1)

    def test_expert_seed1003_replays_known_120_trace(self):
        snapshot = _expert_seed1003_snapshot()
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        replayed_moves = []

        self.assertEqual(snapshot.width, 30)
        self.assertEqual(snapshot.height, 16)
        self.assertEqual(len(snapshot.mines), 99)
        self.assertEqual(len(_EXPERT_SEED1003_120_TRACE), 87)

        for step, expected in enumerate(_EXPERT_SEED1003_120_TRACE, start=1):
            with self.subTest(step=step, expected=expected):
                action, x, y, premium, clicks_added = expected
                coord = (x, y)
                candidates = _find_premium_candidates(state, context)
                best_premium = max(
                    (candidate.premium for candidate in candidates),
                    default=None,
                )
                before_revealed = set(state.revealed)
                before_flagged = set(state.flagged_mines)

                if action == "fallback_click":
                    self.assertTrue(
                        best_premium is None or best_premium < 0
                    )
                    # This intentionally locks the known trace to the current
                    # unresolved-static-3BV fallback policy as well as replay
                    # move validity.
                    self.assertEqual(
                        _select_fallback_click_target(state, context),
                        coord,
                    )
                    self.assertNotIn(coord, snapshot.mines)
                    self.assertNotIn(coord, state.revealed)
                    self.assertIsNone(premium)
                    self.assertEqual(clicks_added, 1)

                    move = _click_fallback_cell(state, coord, context)
                else:
                    matching_candidates = [
                        candidate
                        for candidate in candidates
                        if candidate.coord == coord
                    ]
                    self.assertEqual(len(matching_candidates), 1)
                    candidate = matching_candidates[0]

                    self.assertEqual(candidate.premium, premium)
                    self.assertNotIn(coord, snapshot.mines)
                    self.assertGreater(snapshot.adjacent[y][x], 0)

                    if action == "click":
                        self.assertNotIn(coord, state.revealed)
                        self.assertEqual(clicks_added, 1)
                        move = _click_covered_candidate(state, candidate)
                    else:
                        self.assertEqual(action, "flag_chord")
                        self.assertIn(coord, state.revealed)
                        flags_before = len(state.flagged_mines)

                        move = _flag_and_chord_uncovered_candidate(
                            state,
                            candidate,
                            context,
                        )

                        new_flags = len(state.flagged_mines) - flags_before
                        self.assertEqual(clicks_added, new_flags + 1)

                self.assertEqual(
                    (
                        move.action,
                        move.x,
                        move.y,
                        move.premium,
                        move.clicks_added,
                    ),
                    expected,
                )
                self.assertTrue(
                    state.revealed != before_revealed
                    or state.flagged_mines != before_flagged
                )
                self.assertTrue(state.flagged_mines <= snapshot.mines)
                replayed_moves.append(move)

        self.assertEqual(len(replayed_moves), 87)
        self.assertEqual(
            sum(move.clicks_added for move in replayed_moves),
            120,
        )
        self.assertEqual(len(state.revealed), 381)
        self.assertTrue(state.all_safe_cells_revealed())
        self.assertEqual(len(state.flagged_mines), 33)
        self.assertTrue(state.flagged_mines <= snapshot.mines)

    def test_static_units_empty_board_has_one_opening(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        units = _extract_static_3bv_units(snapshot)

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].kind, "opening")
        self.assertEqual(units[0].representative, (0, 0))
        self.assertEqual(units[0].cells, frozenset({(0, 0)}))

    def test_static_units_center_mine_has_eight_isolated_numbers(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )

        units = _extract_static_3bv_units(snapshot)

        self.assertEqual(len(units), 8)
        self.assertTrue(all(unit.kind == "isolated" for unit in units))
        self.assertEqual(
            [unit.representative for unit in units],
            [
                (0, 0),
                (1, 0),
                (2, 0),
                (0, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            ],
        )

    def test_static_units_corner_mine_has_one_opening_represented_top_left(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )

        units = _extract_static_3bv_units(snapshot)

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].kind, "opening")
        self.assertEqual(units[0].representative, (2, 0))
        self.assertEqual(
            units[0].cells,
            frozenset({(2, 0), (2, 1), (0, 2), (1, 2), (2, 2)}),
        )
        self.assertEqual(units[0].opening_id, 0)

    def test_dynamic_state_reveals_single_cell_opening_and_completes_board(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        unit = _extract_static_3bv_units(snapshot)[0]
        state = _ZiniBoardState.create(snapshot)

        state.reveal_unit(unit)

        self.assertEqual(state.revealed, {(0, 0)})
        self.assertTrue(state.all_safe_cells_revealed())

    def test_dynamic_state_reveals_opening_zero_cells_and_border_ring(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        unit = _extract_static_3bv_units(snapshot)[0]
        state = _ZiniBoardState.create(snapshot)

        state.reveal_unit(unit)

        self.assertEqual(
            state.revealed,
            {
                (1, 0),
                (2, 0),
                (0, 1),
                (1, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            },
        )
        self.assertTrue(state.all_safe_cells_revealed())

    def test_dynamic_state_reveals_isolated_number_only(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        unit = _extract_static_3bv_units(snapshot)[0]
        state = _ZiniBoardState.create(snapshot)

        state.reveal_unit(unit)

        self.assertEqual(unit.kind, "isolated")
        self.assertEqual(unit.representative, (0, 0))
        self.assertEqual(state.revealed, {(0, 0)})
        self.assertFalse(state.all_safe_cells_revealed())

    def test_dynamic_state_flags_mine_coordinate(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)

        state.flag_mine((1, 0))

        self.assertEqual(state.flagged_mines, {(1, 0)})

    def test_dynamic_state_rejects_non_mine_flag(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)

        with self.assertRaises(ValueError):
            state.flag_mine((0, 0))

    def test_premium_counts_adjacent_unflagged_mines_without_counting_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        # Adjacent covered isolated cells: (1, 0), (0, 1). The covered
        # isolated candidate (0, 0) is not adjacent to itself and is not
        # counted. Adjacent unflagged mines: (1, 1).
        self.assertEqual(premium, 0)

    def test_premium_ignores_already_flagged_adjacent_mines(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.flag_mine((1, 1))
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        self.assertEqual(premium, 1)

    def test_premium_deduplicates_multiple_adjacent_zero_cells(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (1, 1), context)

        # Candidate (1, 1) touches several zero cells from the same opening,
        # two covered BORDER numbers, and one unflagged mine. The opening is
        # counted once, BORDER numbers are not independent 3BV, and the covered
        # BORDER candidate receives the non-3BV penalty.
        self.assertEqual(premium, -2)

    def test_premium_excludes_border_only_opening_contact(self):
        snapshot = BoardSnapshot(
            width=4,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 1)}),
            adjacent=((1, 1, 0, 0), (0, 1, 0, 0), (1, 1, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        # Candidate (0, 0) touches only BORDER numbers from the opening at its
        # east side, not any zero cell from that opening. The opening must not
        # be counted as adjacent covered 3BV. The negative value is intentional
        # and must not be clamped to zero.
        self.assertEqual(premium, -2)

    def test_premium_applies_covered_border_penalty_only_while_covered(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        covered_premium = _calculate_premium(state, (1, 1), context)
        state.revealed.add((1, 1))
        uncovered_premium = _calculate_premium(state, (1, 1), context)

        self.assertEqual(covered_premium, -2)
        self.assertEqual(uncovered_premium, -1)

    def test_premium_excludes_already_revealed_adjacent_3bv(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        # Only (0, 1) remains as adjacent covered 3BV. The adjacent mine is
        # still unflagged, so the Premium is negative and remains unclamped.
        self.assertEqual(premium, -1)

    def test_select_best_candidate_uses_highest_premium_and_top_left_tie_break(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (1, 0))
        self.assertEqual(candidate.premium, 2)

    def test_select_best_candidate_uses_flagged_mines_in_premium(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.flag_mine((1, 1))
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (1, 0))
        self.assertEqual(candidate.premium, 3)

    def test_select_best_candidate_tie_breaks_by_y_then_x(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1), (1, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (0, 0))
        self.assertEqual(candidate.premium, 0)

    def test_find_premium_candidates_excludes_covered_zero_cells(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidates = _find_premium_candidates(state, context)

        self.assertEqual(
            {candidate.coord for candidate in candidates},
            {(1, 0), (0, 1), (1, 1)},
        )

    def test_select_best_candidate_allows_negative_premium(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (0, 0))
        self.assertEqual(candidate.premium, -2)

    def test_select_best_candidate_returns_none_when_no_number_candidates_exist(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        self.assertEqual(_find_premium_candidates(state, context), ())
        self.assertIsNone(_select_best_premium_candidate(state, context))

    def test_select_best_candidate_returns_none_when_board_is_solved(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.update(
            (x, y)
            for y in range(snapshot.height)
            for x in range(snapshot.width)
            if (x, y) not in snapshot.mines
        )
        context = _build_premium_context(snapshot)

        self.assertIsNone(_select_best_premium_candidate(state, context))

    def test_click_covered_candidate_reveals_isolated_number_only(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        candidate = _select_best_premium_candidate(state, context)

        move = _click_covered_candidate(state, candidate)

        self.assertEqual(state.revealed, {candidate.coord})
        self.assertEqual(move.action, "click")
        self.assertEqual((move.x, move.y), candidate.coord)
        self.assertEqual(move.premium, candidate.premium)
        self.assertEqual(move.clicks_added, 1)

    def test_click_covered_candidate_reveals_border_number_only(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        candidate = next(
            candidate
            for candidate in _find_premium_candidates(state, context)
            if candidate.coord == (1, 1)
        )

        move = _click_covered_candidate(state, candidate)

        self.assertEqual(state.revealed, {(1, 1)})
        self.assertTrue(
            {(2, 0), (2, 1), (0, 2), (1, 2), (2, 2)}.isdisjoint(
                state.revealed
            )
        )
        self.assertEqual(move.action, "click")
        self.assertEqual((move.x, move.y), (1, 1))
        self.assertEqual(move.premium, candidate.premium)
        self.assertEqual(move.clicks_added, 1)

    def test_click_covered_candidate_rejects_already_revealed_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        candidate = _select_best_premium_candidate(state, context)
        state.revealed.add(candidate.coord)

        with self.assertRaises(ValueError):
            _click_covered_candidate(state, candidate)

    def test_click_covered_candidate_rejects_mine_coordinate(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        candidate = _PremiumCandidate(coord=(1, 0), premium=0)

        with self.assertRaises(ValueError):
            _click_covered_candidate(state, candidate)

    def test_click_covered_candidate_rejects_zero_cell(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        candidate = _PremiumCandidate(coord=(0, 0), premium=0)

        with self.assertRaises(ValueError):
            _click_covered_candidate(state, candidate)

    def test_flag_chord_flags_adjacent_mine_and_reveals_safe_neighbors(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        context = _build_premium_context(snapshot)
        candidate = _PremiumCandidate(
            coord=(1, 0),
            premium=_calculate_premium(state, (1, 0), context),
        )

        move = _flag_and_chord_uncovered_candidate(state, candidate, context)

        self.assertEqual(state.flagged_mines, {(1, 1)})
        self.assertEqual(
            state.revealed,
            {(1, 0), (0, 0), (2, 0), (0, 1), (2, 1)},
        )
        self.assertEqual(move.action, "flag_chord")
        self.assertEqual((move.x, move.y), (1, 0))
        self.assertEqual(move.premium, 2)
        self.assertEqual(move.clicks_added, 2)

    def test_flag_chord_counts_only_chord_when_adjacent_mine_already_flagged(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        state.flag_mine((1, 1))
        context = _build_premium_context(snapshot)
        candidate = _PremiumCandidate(
            coord=(1, 0),
            premium=_calculate_premium(state, (1, 0), context),
        )

        move = _flag_and_chord_uncovered_candidate(state, candidate, context)

        self.assertEqual(state.flagged_mines, {(1, 1)})
        self.assertEqual(move.premium, 3)
        self.assertEqual(move.clicks_added, 1)

    def test_flag_chord_reveals_opening_through_adjacent_zero_cell(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 1))
        state.flag_mine((0, 0))
        context = _build_premium_context(snapshot)
        candidate = _PremiumCandidate(
            coord=(1, 1),
            premium=_calculate_premium(state, (1, 1), context),
        )

        move = _flag_and_chord_uncovered_candidate(state, candidate, context)

        self.assertEqual(
            state.revealed,
            {
                (1, 0),
                (0, 1),
                (1, 1),
                (2, 0),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            },
        )
        self.assertEqual(move.clicks_added, 1)

    def test_flag_chord_reveals_border_neighbors_without_border_only_opening(self):
        snapshot = BoardSnapshot(
            width=4,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 1)}),
            adjacent=((1, 1, 0, 0), (0, 1, 0, 0), (1, 1, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        state.flag_mine((0, 1))
        context = _build_premium_context(snapshot)
        candidate = _PremiumCandidate(coord=(0, 0), premium=0)

        move = _flag_and_chord_uncovered_candidate(state, candidate, context)

        self.assertEqual(state.revealed, {(0, 0), (1, 0), (1, 1)})
        self.assertTrue(
            {(2, 0), (2, 1), (1, 2), (2, 2), (3, 2)}.isdisjoint(
                state.revealed
            )
        )
        self.assertEqual(move.clicks_added, 1)

    def test_flag_chord_rejects_covered_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        candidate = _PremiumCandidate(coord=(1, 0), premium=2)

        with self.assertRaises(ValueError):
            _flag_and_chord_uncovered_candidate(
                state, candidate, _build_premium_context(snapshot)
            )

    def test_flag_chord_rejects_negative_premium(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        candidate = _PremiumCandidate(coord=(0, 0), premium=-1)

        with self.assertRaises(ValueError):
            _flag_and_chord_uncovered_candidate(
                state, candidate, _build_premium_context(snapshot)
            )

    def test_flag_chord_rejects_mine_candidate(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        candidate = _PremiumCandidate(coord=(1, 0), premium=0)

        with self.assertRaises(ValueError):
            _flag_and_chord_uncovered_candidate(
                state, candidate, _build_premium_context(snapshot)
            )

    def test_flag_chord_rejects_zero_candidate(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        candidate = _PremiumCandidate(coord=(0, 0), premium=0)

        with self.assertRaises(ValueError):
            _flag_and_chord_uncovered_candidate(
                state, candidate, _build_premium_context(snapshot)
            )

    def test_select_fallback_click_target_returns_single_empty_cell(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        self.assertEqual(
            _select_fallback_click_target(state, context),
            (0, 0),
        )

    def test_fallback_click_zero_reveals_opening_and_solves_board(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _click_fallback_cell(state, (0, 0), context)

        self.assertEqual(state.revealed, {(0, 0)})
        self.assertTrue(state.all_safe_cells_revealed())
        self.assertEqual(move.action, "fallback_click")
        self.assertEqual((move.x, move.y), (0, 0))
        self.assertIsNone(move.premium)
        self.assertEqual(move.clicks_added, 1)

    def test_fallback_click_zero_reveals_opening_and_border_ring(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _click_fallback_cell(state, (2, 0), context)

        self.assertEqual(
            state.revealed,
            {
                (1, 0),
                (0, 1),
                (1, 1),
                (2, 0),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            },
        )
        self.assertEqual(move.action, "fallback_click")
        self.assertIsNone(move.premium)
        self.assertEqual(move.clicks_added, 1)

    def test_fallback_click_number_reveals_only_that_number(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _click_fallback_cell(state, (0, 0), context)

        self.assertEqual(state.revealed, {(0, 0)})
        self.assertEqual(move.action, "fallback_click")
        self.assertEqual((move.x, move.y), (0, 0))
        self.assertIsNone(move.premium)
        self.assertEqual(move.clicks_added, 1)

    def test_select_fallback_click_target_uses_top_leftmost_unrevealed_3bv_unit(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        self.assertEqual(
            _select_fallback_click_target(state, context),
            (2, 0),
        )

    def test_find_fallback_click_targets_uses_deterministic_row_major_order(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        targets = _find_fallback_click_targets(state, context)

        self.assertEqual(
            targets,
            (
                (0, 0),
                (1, 0),
                (2, 0),
                (0, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            ),
        )
        self.assertEqual(_select_fallback_click_target(state, context), targets[0])

    def test_select_fallback_click_target_returns_none_when_all_safe_revealed(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        context = _build_premium_context(snapshot)

        self.assertIsNone(_select_fallback_click_target(state, context))

    def test_fallback_click_rejects_mine_target(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        with self.assertRaises(ValueError):
            _click_fallback_cell(state, (1, 0), context)

    def test_fallback_click_rejects_already_revealed_target(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        context = _build_premium_context(snapshot)

        with self.assertRaises(ValueError):
            _click_fallback_cell(state, (0, 0), context)

    def test_fallback_click_rejects_zero_without_opening_unit(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        broken_context = type(context)(
            analysis=context.analysis,
            units=context.units,
            opening_units_by_id={},
            isolated_cells=context.isolated_cells,
        )

        with self.assertRaises(ValueError):
            _click_fallback_cell(state, (0, 0), broken_context)

    def test_apply_next_move_returns_none_when_solved(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        context = _build_premium_context(snapshot)

        self.assertIsNone(_apply_next_g_zini_move(state, context))

    def test_apply_next_move_clicks_covered_best_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _apply_next_g_zini_move(state, context)

        self.assertEqual(move.action, "click")
        self.assertEqual((move.x, move.y), (1, 0))
        self.assertEqual(move.premium, 2)
        self.assertEqual(move.clicks_added, 1)
        self.assertEqual(state.revealed, {(1, 0)})

    def test_apply_next_move_flag_chords_revealed_non_negative_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        context = _build_premium_context(snapshot)

        move = _apply_next_g_zini_move(state, context)

        self.assertEqual(move.action, "flag_chord")
        self.assertEqual((move.x, move.y), (1, 0))
        self.assertEqual(move.premium, 2)
        self.assertEqual(move.clicks_added, 2)
        self.assertEqual(state.flagged_mines, {(1, 1)})
        self.assertEqual(
            state.revealed,
            {(1, 0), (0, 0), (2, 0), (0, 1), (2, 1)},
        )

    def test_apply_next_move_uses_fallback_when_best_premium_is_negative(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _apply_next_g_zini_move(state, context)

        self.assertEqual(move.action, "fallback_click")
        self.assertEqual((move.x, move.y), (0, 0))
        self.assertIsNone(move.premium)
        self.assertEqual(move.clicks_added, 1)
        self.assertEqual(state.revealed, {(0, 0)})

    def test_apply_next_move_uses_fallback_when_no_premium_candidate_exists(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _apply_next_g_zini_move(state, context)

        self.assertEqual(move.action, "fallback_click")
        self.assertEqual((move.x, move.y), (0, 0))
        self.assertIsNone(move.premium)
        self.assertEqual(move.clicks_added, 1)
        self.assertEqual(state.revealed, {(0, 0)})
        self.assertTrue(state.all_safe_cells_revealed())


if __name__ == "__main__":
    unittest.main()
