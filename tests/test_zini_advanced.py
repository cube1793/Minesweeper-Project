import unittest
from dataclasses import FrozenInstanceError
from random import Random

from board_snapshot import BoardSnapshot
from zini_advanced import (
    _AdvancedTrajectory,
    _ChainNeighborhoodPolicyV1,
    _StandardNeighborhoodPolicyV1,
    _collect_neighborhood_decisions,
    _get_neighborhood_policy,
    _rollout_neighborhood_deviation,
)
from zini_calculator import (
    ZiniAdvancedSearchResult,
    ZiniAdvancedTerminationReason,
    ZiniNeighborhoodBeamConfig,
    ZiniResult,
    _resolve_standard_phase_evaluations,
    _validate_neighborhood_beam_config,
    calculate_g_zini,
    calculate_g_zini_neighborhood_beam_bounded,
)
from zini_core import _build_premium_context
from tests.zini_fixtures import (
    _advanced_search_snapshot,
    _board_c_snapshot,
    _move_signature,
    _replay_zini_result,
)


class ZiniAdvancedTests(unittest.TestCase):
    def test_neighborhood_policy_dispatches_standard_v1(self):
        policy = _get_neighborhood_policy(ZiniNeighborhoodBeamConfig())

        self.assertIsInstance(policy, _StandardNeighborhoodPolicyV1)

    def test_neighborhood_policy_dispatches_chain_v1(self):
        policy = _get_neighborhood_policy(
            ZiniNeighborhoodBeamConfig(ranking_policy="chain_v1")
        )

        self.assertIsInstance(policy, _ChainNeighborhoodPolicyV1)

    def test_standard_v1_iterator_yields_exactly_one_rollout(self):
        snapshot = _advanced_search_snapshot()
        context = _build_premium_context(snapshot)
        trajectory = _AdvancedTrajectory(calculate_g_zini(snapshot))
        config = ZiniNeighborhoodBeamConfig()
        decision = _collect_neighborhood_decisions(
            snapshot,
            context,
            trajectory,
            config,
        )[0]
        alternative = decision.alternatives[0]
        policy = _get_neighborhood_policy(config)

        rollouts = tuple(
            policy.iter_rollout_deviations(
                snapshot,
                decision,
                alternative,
                context,
                config,
                Random(config.seed),
                set(),
            )
        )

        self.assertEqual(len(rollouts), 1)
        self.assertEqual(
            rollouts[0],
            _rollout_neighborhood_deviation(
                decision,
                alternative,
                context,
            ),
        )

    def test_chain_v1_depth_one_matches_standard_v1(self):
        snapshot = _advanced_search_snapshot()
        shared = dict(
            chain_depth=1,
            max_seconds=None,
            max_evaluations=20,
            stall_seconds=None,
            seed=1234,
        )
        standard = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=ZiniNeighborhoodBeamConfig(
                ranking_policy="standard_v1",
                **shared,
            ),
        )
        chain = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=ZiniNeighborhoodBeamConfig(
                ranking_policy="chain_v1",
                **shared,
            ),
        )

        self.assertEqual(chain.result, standard.result)
        self.assertEqual(chain.evaluations, standard.evaluations)
        self.assertEqual(chain.generations, standard.generations)
        self.assertEqual(chain.termination_reason, standard.termination_reason)

    def test_chain_v1_rollouts_preserve_first_deviation(self):
        snapshot = _advanced_search_snapshot()
        context = _build_premium_context(snapshot)
        trajectory = _AdvancedTrajectory(calculate_g_zini(snapshot))
        config = ZiniNeighborhoodBeamConfig(
            ranking_policy="chain_v1",
            chain_depth=2,
            chain_branching=2,
        )
        policy = _get_neighborhood_policy(config)
        decision = _collect_neighborhood_decisions(
            snapshot,
            context,
            trajectory,
            config,
        )[0]
        alternative = decision.alternatives[0]

        rollouts = tuple(
            policy.iter_rollout_deviations(
                snapshot,
                decision,
                alternative,
                context,
                config,
                Random(config.seed),
                set(),
            )
        )

        self.assertGreater(len(rollouts), 1)
        first_deviation = rollouts[0].result.moves[decision.step_index]
        for rollout in rollouts[1:]:
            self.assertEqual(
                rollout.result.moves[decision.step_index],
                first_deviation,
            )

    def test_chain_v1_small_board_result_is_valid(self):
        snapshot = _advanced_search_snapshot()
        baseline = calculate_g_zini(snapshot)
        search = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=ZiniNeighborhoodBeamConfig(
                ranking_policy="chain_v1",
                max_seconds=None,
                max_evaluations=30,
                stall_seconds=None,
                seed=7,
            ),
        )
        state = _replay_zini_result(snapshot, search.result)

        self.assertFalse(search.exact)
        self.assertTrue(state.all_safe_cells_revealed())
        self.assertTrue(state.flagged_mines <= snapshot.mines)
        self.assertLessEqual(search.best_clicks, baseline.clicks)
        self.assertEqual(
            search.result.clicks,
            sum(move.clicks_added for move in search.result.moves),
        )

    def test_chain_v1_is_reproducible_with_fixed_evaluation_budget(self):
        snapshot = _advanced_search_snapshot()
        config = ZiniNeighborhoodBeamConfig(
            ranking_policy="chain_v1",
            max_seconds=None,
            max_evaluations=30,
            stall_seconds=None,
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

        self.assertEqual(first.result, second.result)
        self.assertEqual(first.evaluations, second.evaluations)
        self.assertEqual(first.generations, second.generations)
        self.assertEqual(first.termination_reason, second.termination_reason)

    def test_chain_v1_zero_evaluations_returns_baseline(self):
        snapshot = _advanced_search_snapshot()
        baseline = calculate_g_zini(snapshot)
        search = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=ZiniNeighborhoodBeamConfig(
                ranking_policy="chain_v1",
                max_seconds=None,
                max_evaluations=0,
            ),
        )

        self.assertEqual(
            search.termination_reason,
            ZiniAdvancedTerminationReason.EVALUATION_LIMIT,
        )
        self.assertEqual(search.evaluations, 0)
        self.assertEqual(search.result, baseline)

    def test_standard_seeded_chain_v1_resolves_phase_budgets(self):
        even = ZiniNeighborhoodBeamConfig(
            ranking_policy="standard_seeded_chain_v1",
            max_evaluations=50,
        )
        odd = ZiniNeighborhoodBeamConfig(
            ranking_policy="standard_seeded_chain_v1",
            max_evaluations=51,
        )
        explicit = ZiniNeighborhoodBeamConfig(
            ranking_policy="standard_seeded_chain_v1",
            max_evaluations=50,
            standard_phase_evaluations=20,
        )

        self.assertEqual(_resolve_standard_phase_evaluations(even), 25)
        self.assertEqual(_resolve_standard_phase_evaluations(odd), 26)
        self.assertEqual(_resolve_standard_phase_evaluations(explicit), 20)

    def test_standard_seeded_chain_v1_returns_valid_best_so_far(self):
        snapshot = _advanced_search_snapshot()
        phase_one = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=ZiniNeighborhoodBeamConfig(
                ranking_policy="standard_v1",
                max_seconds=None,
                max_evaluations=15,
                stall_seconds=None,
                seed=7,
            ),
        )
        search = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=ZiniNeighborhoodBeamConfig(
                ranking_policy="standard_seeded_chain_v1",
                max_seconds=None,
                max_evaluations=30,
                standard_phase_evaluations=15,
                stall_seconds=None,
                seed=7,
            ),
        )
        state = _replay_zini_result(snapshot, search.result)

        self.assertFalse(search.exact)
        self.assertLessEqual(search.best_clicks, phase_one.best_clicks)
        self.assertLessEqual(search.evaluations, 30)
        self.assertTrue(state.all_safe_cells_revealed())
        self.assertTrue(state.flagged_mines <= snapshot.mines)
        self.assertEqual(
            search.result.clicks,
            sum(move.clicks_added for move in search.result.moves),
        )

    def test_standard_seeded_chain_v1_is_reproducible(self):
        snapshot = _advanced_search_snapshot()
        config = ZiniNeighborhoodBeamConfig(
            ranking_policy="standard_seeded_chain_v1",
            max_seconds=None,
            max_evaluations=30,
            standard_phase_evaluations=15,
            stall_seconds=None,
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

        self.assertEqual(first.result, second.result)
        self.assertEqual(first.evaluations, second.evaluations)
        self.assertEqual(first.generations, second.generations)
        self.assertEqual(first.termination_reason, second.termination_reason)

    def test_standard_seeded_chain_v1_zero_evaluations_returns_baseline(self):
        snapshot = _advanced_search_snapshot()
        baseline = calculate_g_zini(snapshot)
        search = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=ZiniNeighborhoodBeamConfig(
                ranking_policy="standard_seeded_chain_v1",
                max_seconds=None,
                max_evaluations=0,
            ),
        )

        self.assertEqual(
            search.termination_reason,
            ZiniAdvancedTerminationReason.EVALUATION_LIMIT,
        )
        self.assertEqual(search.evaluations, 0)
        self.assertEqual(search.result, baseline)

    def test_standard_seeded_chain_v1_zero_seconds_returns_baseline(self):
        snapshot = _advanced_search_snapshot()
        baseline = calculate_g_zini(snapshot)
        search = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=ZiniNeighborhoodBeamConfig(
                ranking_policy="standard_seeded_chain_v1",
                max_seconds=0,
                max_evaluations=20,
                standard_phase_evaluations=10,
            ),
        )

        self.assertEqual(
            search.termination_reason,
            ZiniAdvancedTerminationReason.TIME_LIMIT,
        )
        self.assertEqual(search.evaluations, 0)
        self.assertEqual(search.result, baseline)

    def test_standard_seeded_chain_v1_zero_chain_budget_keeps_phase_one(self):
        snapshot = _advanced_search_snapshot()
        phase_one = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=ZiniNeighborhoodBeamConfig(
                ranking_policy="standard_v1",
                max_seconds=None,
                max_evaluations=20,
                stall_seconds=None,
                seed=7,
            ),
        )
        seeded = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=ZiniNeighborhoodBeamConfig(
                ranking_policy="standard_seeded_chain_v1",
                max_seconds=None,
                max_evaluations=20,
                standard_phase_evaluations=20,
                stall_seconds=None,
                seed=7,
            ),
        )

        self.assertEqual(seeded.result, phase_one.result)
        self.assertEqual(seeded.evaluations, phase_one.evaluations)
        self.assertEqual(seeded.generations, phase_one.generations)
        self.assertEqual(
            seeded.termination_reason,
            ZiniAdvancedTerminationReason.EVALUATION_LIMIT,
        )

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
        self.assertEqual(config.chain_depth, 2)
        self.assertEqual(config.chain_branching, 2)
        self.assertIsNone(config.standard_phase_evaluations)
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
            {"chain_depth": 0},
            {"chain_depth": -1},
            {"chain_branching": 0},
            {"chain_branching": -1},
            {"standard_phase_evaluations": -1},
            {"max_seconds": -1},
            {"max_evaluations": -1},
            {"stall_seconds": -1},
            {
                "max_seconds": None,
                "max_evaluations": None,
                "stall_seconds": None,
            },
            {"ranking_policy": "unknown"},
            {
                "ranking_policy": "standard_seeded_chain_v1",
                "max_seconds": 1,
                "max_evaluations": None,
            },
            {
                "ranking_policy": "standard_seeded_chain_v1",
                "max_evaluations": 10,
                "standard_phase_evaluations": 11,
            },
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


if __name__ == "__main__":
    unittest.main()
