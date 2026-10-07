"""Exact outcome-aware comparisons over synthetic, complete persisted facts.

The fixtures deliberately test the structural evaluation boundary, without
inventing hidden boards or replaying the repeated public action targets.
"""

import ast
import json
import sqlite3
import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import benchmark_comparison as comparison
import benchmark_runner
import benchmark_statistics as statistics
import stage3_benchmark_runner
import stage3_physical as physical
import telemetry_repository as repository
import telemetry_schema as schema
from benchmark_board import EXPERT_GENERAL_V1
from core_engine import Action, GameStatus
from telemetry_collector import TelemetryCollector
from telemetry_model import InferenceCategory


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class ComparisonTestCase(unittest.TestCase):
    def setUp(self):
        self.left = self.connection()
        self.right = self.connection()
        self.table = physical.load_timing_table()

    def connection(self):
        connection = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        schema.initialize_schema(connection)
        return connection

    def create_run(self, connection, stage, count, **overrides):
        builder = (benchmark_runner._benchmark_identity if stage == 2
                   else stage3_benchmark_runner._benchmark_identity)
        values = dict(
            **builder(EXPERT_GENERAL_V1), requested_games=count,
            created_at="2026-10-07T00:00:00Z", git_commit="a" * 40,
            git_dirty=False, run_status=schema.RUN_STATUS_RUNNING,
            environment_snapshot={"fixture": "synthetic-public-facts"},
        )
        values.update(overrides)
        return repository.create_run(connection, **values)

    def persist(self, connection, run_id, stage, index, result="WIN", count=2, targets=None):
        if targets is None:
            targets = ((Action.OPEN, 0, 0),) * count
        terminal = GameStatus.WON if result == "WIN" else GameStatus.LOST
        collector = TelemetryCollector()
        for action_index, (action, x, y) in enumerate(targets):
            final = action_index == len(targets) - 1
            metadata = {}
            if action_index:
                guess = final and result == "LOSS"
                metadata = dict(
                    inference_category=(InferenceCategory.PROBABILITY_GUESS if guess
                                        else InferenceCategory.LOCAL_DETERMINISTIC),
                    selection_candidate_count=1 if stage == 2 else None,
                    target_mine_probability=(Fraction(1, 3) if guess else
                                             None if action == Action.CHORD else
                                             Fraction(int(action == Action.FLAG))),
                    minimum_available_mine_probability=Fraction(1, 3) if guess else None,
                    decision_compute_ns=17 if stage == 2 else 91,
                )
            collector.record_action(
                action_type=action, x=x, y=y,
                status_after=terminal if final else GameStatus.PLAYING,
                safe_cells_opened_delta=int(action != Action.FLAG and not (final and result == "LOSS")),
                explicit_flag_delta=int(action == Action.FLAG), **metadata,
            )
        game = collector.finalize(
            game_index=index, seed=index, board_fingerprint=f"{index:064x}",
            board_3bv=1, board_ops=0,
        )
        game_id = repository.persist_completed_game(connection, run_id, game, collector.events)
        cursor = (0, 0)
        cost = 0
        for _, x, y in targets:
            cost += self.table[abs(x - cursor[0])][abs(y - cursor[1])]
            cursor = x, y
        return game_id, cost

    def pair(self, left_games=(("WIN", 2),), right_games=None, *, completed=True):
        if right_games is None:
            right_games = left_games
        self.assertEqual(len(left_games), len(right_games))
        ids = []
        costs = []
        for connection, stage, games in ((self.left, 2, left_games), (self.right, 3, right_games)):
            run_id = self.create_run(connection, stage, len(games))
            ids.append(run_id)
            game_costs = []
            for index, (result, count) in enumerate(games):
                _, cost = self.persist(connection, run_id, stage, index, result, count)
                game_costs.append(cost)
            if completed:
                repository.update_run_status(connection, run_id, schema.RUN_STATUS_COMPLETED)
            costs.append(tuple(game_costs))
        return tuple(ids), tuple(costs)

    def compare(self, ids=(1, 1), prefix=1, **kwargs):
        kwargs.setdefault("left_source_label", "accepted-stage2-copy")
        kwargs.setdefault("right_source_label", "stage3-fixture")
        return comparison.compare_stage2_stage3_sources(
            self.left, ids[0], self.right, ids[1], prefix, **kwargs,
        )

    def update_run(self, connection, run_id, **values):
        for key, value in values.items():
            connection.execute(f"UPDATE benchmark_runs SET {key} = ? WHERE run_id = ?", (value, run_id))

    def assert_unchanged_rejection(self, call):
        before = [tuple(connection.iterdump()) for connection in (self.left, self.right)]
        changes = [connection.total_changes for connection in (self.left, self.right)]
        with self.assertRaises(ValueError):
            call()
        self.assertEqual(before, [tuple(connection.iterdump()) for connection in (self.left, self.right)])
        self.assertEqual(changes, [connection.total_changes for connection in (self.left, self.right)])


class OutcomeComparisonTests(ComparisonTestCase):
    def test_all_four_outcomes_and_exact_whole_prefix_win_rates(self):
        ids, costs = self.pair(
            (("WIN", 7), ("WIN", 11), ("LOSS", 13), ("LOSS", 17)),
            (("WIN", 3), ("LOSS", 2), ("WIN", 19), ("LOSS", 2)),
        )
        report = self.compare(ids, 4, require_official=True)
        self.assertEqual(report.outcomes, comparison.OutcomeContingency(1, 1, 1, 1))
        self.assertEqual((report.stage2_wins, report.stage2_losses, report.stage2_win_rate), (2, 2, Fraction(1, 2)))
        self.assertEqual((report.stage3_wins, report.stage3_losses, report.stage3_win_rate), (2, 2, Fraction(1, 2)))
        self.assertEqual(report.prefix_games, 4)
        self.assertIs(report.require_official, True)
        primary = report.primary
        self.assertEqual(primary.game_count, 1)
        self.assertEqual((primary.stage2_total_us, primary.stage3_total_us), (costs[0][0], costs[1][0]))
        self.assertEqual(primary.total_delta_us, costs[1][0] - costs[0][0])
        self.assertEqual(primary.paired_deltas_us, ((0, costs[1][0] - costs[0][0]),))
        self.assertEqual(primary.ratio, Fraction(3, 7))
        self.assertEqual(primary.reduction, Fraction(4, 7))
        self.assertEqual((primary.stage3_faster, primary.stage2_faster, primary.ties), (1, 0, 0))
        self.assertEqual(report.diagnostic_stage2_total_us, sum(costs[0]))
        self.assertEqual(report.diagnostic_stage3_total_us, sum(costs[1]))

    def test_faster_slower_and_exact_ties_use_signed_paired_deltas(self):
        ids, costs = self.pair((("WIN", 4), ("WIN", 2), ("WIN", 3)),
                               (("WIN", 2), ("WIN", 5), ("WIN", 3)))
        primary = self.compare(ids, 3).primary
        expected = tuple((index, right - left) for index, (left, right) in enumerate(zip(*costs)))
        self.assertEqual(primary.paired_deltas_us, expected)
        self.assertEqual((primary.stage3_faster, primary.stage2_faster, primary.ties), (1, 1, 1))
        self.assertEqual(primary.stage3_faster + primary.stage2_faster + primary.ties, primary.game_count)
        self.assertEqual(primary.total_delta_us, sum(delta for _, delta in expected))

    def test_primary_is_ratio_of_totals_with_opposite_per_game_mean_conclusion(self):
        ids, costs = self.pair((("WIN", 10), ("WIN", 1)), (("WIN", 5), ("WIN", 3)))
        primary = self.compare(ids, 2).primary
        mean_ratio = sum((Fraction(right, left) for left, right in zip(*costs)), Fraction()) / 2
        self.assertEqual(mean_ratio, Fraction(7, 4))
        self.assertGreater(mean_ratio, 1)
        self.assertEqual(primary.ratio, Fraction(sum(costs[1]), sum(costs[0])))
        self.assertEqual(primary.ratio, Fraction(8, 11))
        self.assertLess(primary.ratio, 1)
        self.assertEqual(primary.reduction, Fraction(3, 11))

    def test_identical_outcomes_can_have_misleading_whole_prefix_early_loss_total(self):
        ids, _ = self.pair((("WIN", 2), ("LOSS", 30)), (("WIN", 4), ("LOSS", 2)))
        report = self.compare(ids, 2)
        self.assertEqual(report.outcomes, comparison.OutcomeContingency(1, 0, 0, 1))
        self.assertEqual(report.primary.ratio, Fraction(2))
        self.assertEqual(report.primary.reduction, Fraction(-1))
        self.assertLess(report.diagnostic_stage3_total_us, report.diagnostic_stage2_total_us)
        self.assertEqual(report.primary.paired_deltas_us, ((0, 2 * self.table[0][0]),))

    def test_negative_reduction_is_not_clamped(self):
        ids, _ = self.pair((("WIN", 2),), (("WIN", 5),))
        primary = self.compare(ids).primary
        self.assertEqual(primary.ratio, Fraction(5, 2))
        self.assertEqual(primary.reduction, Fraction(-3, 2))
        self.assertEqual((primary.stage3_faster, primary.stage2_faster, primary.ties), (0, 1, 0))

    def test_no_common_wins_has_empty_sums_and_unavailable_ratio(self):
        ids, _ = self.pair((("WIN", 2), ("LOSS", 3), ("LOSS", 4)),
                           (("LOSS", 2), ("WIN", 3), ("LOSS", 2)))
        report = self.compare(ids, 3)
        self.assertEqual(report.outcomes, comparison.OutcomeContingency(0, 1, 1, 1))
        primary = report.primary
        self.assertEqual((primary.game_count, primary.stage2_total_us, primary.stage3_total_us,
                          primary.total_delta_us, primary.stage3_faster, primary.stage2_faster, primary.ties),
                         (0, 0, 0, 0, 0, 0, 0))
        self.assertEqual(primary.paired_deltas_us, ())
        self.assertIsNone(primary.ratio)
        self.assertIsNone(primary.reduction)
        self.assertEqual(report.stage2_win_rate, Fraction(1, 3))
        self.assertEqual(report.stage3_win_rate, Fraction(1, 3))

    def test_single_common_win_can_be_an_exact_tie(self):
        self.pair((("WIN", 1),))
        primary = self.compare().primary
        self.assertEqual(primary.stage2_total_us, self.table[0][0])
        self.assertEqual(primary.stage3_total_us, self.table[0][0])
        self.assertEqual(primary.ratio, Fraction(1))
        self.assertEqual(primary.reduction, Fraction(0))
        self.assertEqual(primary.paired_deltas_us, ((0, 0),))
        self.assertEqual((primary.stage3_faster, primary.stage2_faster, primary.ties), (0, 0, 1))

    def test_explicit_prefix_excludes_later_games(self):
        ids, _ = self.pair((("WIN", 2), ("LOSS", 20)), (("WIN", 2), ("WIN", 30)))
        report = self.compare(ids, 1, require_official=True)
        self.assertEqual(report.outcomes, comparison.OutcomeContingency(1, 0, 0, 0))
        self.assertEqual((report.stage2_win_rate, report.stage3_win_rate), (Fraction(1), Fraction(1)))
        self.assertEqual(report.diagnostic_stage3_total_us, 2 * self.table[0][0])

    def test_cost_uses_every_open_flag_chord_target_in_order(self):
        targets = ((Action.OPEN, 0, 0), (Action.FLAG, 29, 15),
                   (Action.CHORD, 7, 3), (Action.OPEN, 2, 9))
        for connection, stage in ((self.left, 2), (self.right, 3)):
            run = self.create_run(connection, stage, 1)
            self.persist(connection, run, stage, 0, targets=targets)
            repository.update_run_status(connection, run, schema.RUN_STATUS_COMPLETED)
        primary = self.compare().primary
        expected = self.table[0][0] + self.table[29][15] + self.table[22][12] + self.table[5][6]
        self.assertEqual((primary.stage2_total_us, primary.stage3_total_us), (expected, expected))

    def test_fraction_arithmetic_and_report_are_immutable(self):
        ids, _ = self.pair((("WIN", 7),), (("WIN", 3),))
        with patch.object(Fraction, "__float__", side_effect=AssertionError("no float conversion")):
            report = self.compare(ids)
        self.assertIsInstance(report.primary.ratio, Fraction)
        self.assertIsInstance(report.primary.reduction, Fraction)
        self.assertIsInstance(report.stage2_win_rate, Fraction)

        def assert_exact(value):
            self.assertNotIsInstance(value, float)
            if is_dataclass(value):
                for field in fields(value):
                    assert_exact(getattr(value, field.name))
            elif isinstance(value, tuple):
                for item in value:
                    assert_exact(item)
        assert_exact(report)
        for value, attribute in ((report, "prefix_games"), (report.primary, "ratio"),
                                 (report.outcomes, "ww"), (report.left, "run_id")):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, attribute, None)


class ComparisonIdentityTests(ComparisonTestCase):
    def test_equal_run_ids_are_disambiguated_by_source_labels(self):
        ids, _ = self.pair()
        self.assertEqual(ids, (1, 1))
        report = self.compare(ids)
        self.assertEqual((report.left.run_id, report.right.run_id), (1, 1))
        self.assertEqual((report.left.label, report.right.label), ("accepted-stage2-copy", "stage3-fixture"))
        self.assertEqual((report.left.solver_stage, report.right.solver_stage), ("STAGE_2", "STAGE_3"))
        self.assertEqual((report.left.telemetry_schema_version, report.right.telemetry_schema_version), (1, 2))
        self.assertEqual((report.left.evaluation_kind, report.right.evaluation_kind),
                         ("post_hoc_frozen_model_c", "declared_frozen_model_c"))

    def test_same_source_runs_use_the_same_higher_level_comparison(self):
        for stage, count in ((2, 5), (3, 3)):
            run_id = self.create_run(self.left, stage, 1)
            self.persist(self.left, run_id, stage, 0, count=count)
            repository.update_run_status(self.left, run_id, schema.RUN_STATUS_COMPLETED)
        report = comparison.compare_stage2_stage3_sources(
            self.left, 1, self.left, 2, 1, left_source_label="combined:stage2",
            right_source_label="combined:stage3", require_official=True,
        )
        self.assertEqual((report.left.run_id, report.right.run_id), (1, 2))
        self.assertEqual(report.primary.ratio, Fraction(3, 5))

    def test_source_labels_are_explicit_distinct_nonblank_text(self):
        self.pair()
        for side in ("left_source_label", "right_source_label"):
            for value in (None, "", "  ", True, 1):
                with self.subTest(side=side, value=value):
                    self.assert_unchanged_rejection(lambda: self.compare(**{side: value}))
        self.assert_unchanged_rejection(lambda: self.compare(left_source_label="same", right_source_label="same"))

    def test_stage2_and_stage3_roles_cannot_be_reversed(self):
        self.pair()
        for official in (False, True):
            with self.subTest(official=official):
                self.assert_unchanged_rejection(lambda: comparison.compare_stage2_stage3_sources(
                    self.right, 1, self.left, 1, 1, left_source_label="stage3", right_source_label="stage2",
                    require_official=official,
                ))

    def test_solver_identity_rejected_separately_from_valid_board_pairing(self):
        self.pair()
        for connection, changes in (
            (self.left, {"solver_stage": "OTHER_STAGE", "solver_policy": "OTHER_POLICY",
                         "telemetry_schema_version": 2}),
            (self.right, {"solver_stage": "OTHER_STAGE", "solver_policy": "OTHER_POLICY",
                          "telemetry_schema_version": 1}),
        ):
            original = dict(repository.fetch_run(connection, 1))
            for field, value in changes.items():
                with self.subTest(side=connection is self.left, field=field):
                    self.update_run(connection, 1, **{field: value})
                    statistics.validate_paired_prefix_sources(self.left, 1, self.right, 1, 1, require_official=True)
                    self.assert_unchanged_rejection(lambda: self.compare(require_official=True))
                    self.assert_unchanged_rejection(self.compare)
                    self.update_run(connection, 1, **{field: original[field]})

    def test_stage2_canonical_configuration_is_enforced(self):
        self.pair()
        for config in ({}, {"accept_guesses": False, "initial_open": [0, 0]},
                       {"accept_guesses": True, "initial_open": [1, 0]},
                       {"accept_guesses": 1, "initial_open": [0, 0]},
                       {"accept_guesses": True, "initial_open": [False, 0]},
                       {"accept_guesses": True, "initial_open": [0, 0], "extra": 1}):
            with self.subTest(config=config):
                self.update_run(self.left, 1, solver_config_snapshot=canonical_json(config))
                self.assert_unchanged_rejection(lambda: self.compare(require_official=True))

    def test_every_stage3_frozen_configuration_component_is_enforced(self):
        self.pair()
        original = json.loads(repository.fetch_run(self.right, 1)["solver_config_snapshot"])
        changes = dict(
            initial_open=[1, 0], initial_cursor=[1, 0], algorithm_spec_version=2,
            algorithm_spec_sha256="0" * 64, physical_model_id="unknown",
            physical_profile_version=2, physical_profile_sha256="0" * 64,
            timing_table_sha256="0" * 64, timing_unit="ms",
        )
        self.assertEqual(set(changes), set(original))
        for field, value in changes.items():
            with self.subTest(field=field):
                changed = {**original, field: value}
                self.update_run(self.right, 1, solver_config_snapshot=canonical_json(changed))
                self.assert_unchanged_rejection(lambda: self.compare(require_official=True))

    def test_missing_malformed_extra_and_wrong_typed_stage3_config_rejected(self):
        self.pair()
        original = json.loads(repository.fetch_run(self.right, 1)["solver_config_snapshot"])
        variants = ["not-json", "null", "[]", "{}", canonical_json({**original, "extra": 1}),
                    canonical_json({**original, "algorithm_spec_version": True}),
                    canonical_json({**original, "physical_profile_version": 1.0}),
                    canonical_json({**original, "initial_cursor": [False, 0]})]
        for raw in variants:
            with self.subTest(raw=raw):
                self.update_run(self.right, 1, solver_config_snapshot=raw)
                self.assert_unchanged_rejection(self.compare)

    def test_matching_noncanonical_corpus_is_not_a_stage2_stage3_comparison(self):
        self.pair()
        for field, value in (("benchmark_set_id", "OTHER_CORPUS"), ("width", 29),
                             ("height", 15), ("num_mines", 98),
                             ("first_click_policy", "OTHER_POLICY"), ("board_generator_version", "V2")):
            originals = [repository.fetch_run(connection, 1)[field] for connection in (self.left, self.right)]
            with self.subTest(field=field):
                for connection in (self.left, self.right):
                    self.update_run(connection, 1, **{field: value})
                statistics.validate_paired_prefix_sources(self.left, 1, self.right, 1, 1)
                self.assert_unchanged_rejection(self.compare)
            for connection, original in zip((self.left, self.right), originals):
                self.update_run(connection, 1, **{field: original})

    def test_official_eligibility_is_required_only_when_requested(self):
        self.pair(completed=False)
        self.compare()
        self.assert_unchanged_rejection(lambda: self.compare(require_official=True))
        for connection in (self.left, self.right):
            repository.update_run_status(connection, 1, schema.RUN_STATUS_COMPLETED)
        self.update_run(self.left, 1, git_dirty=1)
        self.compare()
        self.assert_unchanged_rejection(lambda: self.compare(require_official=True))


class ComparisonSafetyTests(ComparisonTestCase):
    def test_report_identifies_the_shared_authenticated_frozen_model(self):
        self.pair()
        with (
            patch.object(comparison, "authenticate_model_c", wraps=comparison.authenticate_model_c) as authenticate,
            patch.object(comparison, "reconstruct_persisted_game", wraps=comparison.reconstruct_persisted_game) as reconstruct,
        ):
            report = self.compare()
        authenticate.assert_called_once_with()
        self.assertEqual(reconstruct.call_count, 2)
        self.assertTrue(all(call.kwargs["evaluation"] is report.evaluation for call in reconstruct.call_args_list))
        evaluation = report.evaluation
        self.assertEqual(evaluation.table, self.table)
        self.assertEqual(evaluation.initial_cursor, (0, 0))
        self.assertEqual(evaluation.physical_model_id, "overlap_floor_log2_distance_v1")
        self.assertEqual(evaluation.physical_profile_version, 1)
        self.assertEqual(evaluation.physical_profile_sha256,
                         "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b")
        self.assertEqual(evaluation.timing_table_sha256,
                         "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b")
        self.assertEqual(evaluation.timing_unit, "us")

    def test_correct_stored_hashes_do_not_bypass_missing_or_corrupt_profile_bytes(self):
        self.pair()
        for failure in (FileNotFoundError("missing preserved profile"), None):
            with self.subTest(failure=failure):
                with patch.object(Path, "read_bytes", side_effect=failure, return_value=b"corrupt-profile"):
                    self.assert_unchanged_rejection(self.compare)

    def test_deleted_action_rows_fail_even_when_game_pairing_passes(self):
        self.pair()
        self.right.execute("DELETE FROM action_events")
        paired = statistics.validate_paired_prefix_sources(self.left, 1, self.right, 1, 1)
        self.assertEqual(len(paired.identities), 1)
        self.assert_unchanged_rejection(self.compare)

    def test_invalid_stream_in_each_non_ww_outcome_fails_the_entire_comparison(self):
        ids, _ = self.pair((("WIN", 2), ("WIN", 3), ("LOSS", 3), ("LOSS", 3)),
                           (("WIN", 2), ("LOSS", 3), ("WIN", 3), ("LOSS", 3)))
        for index in (1, 2, 3):
            for connection in (self.left, self.right):
                with self.subTest(index=index, side=connection is self.left):
                    connection.execute("SAVEPOINT invalid_stream")
                    connection.execute(
                        "DELETE FROM action_events WHERE action_index = 1 AND game_id = "
                        "(SELECT game_id FROM games WHERE run_id = 1 AND game_index = ?)", (index,),
                    )
                    statistics.validate_paired_prefix_sources(self.left, 1, self.right, 1, 4)
                    self.assert_unchanged_rejection(lambda: self.compare(ids, 4))
                    connection.execute("ROLLBACK TO invalid_stream")
                    connection.execute("RELEASE invalid_stream")

    def test_invalid_stream_cannot_disappear_into_an_empty_common_win_subset(self):
        self.pair((("LOSS", 3),))
        self.left.execute("UPDATE action_events SET x = 30 WHERE action_index = 1")
        self.assert_unchanged_rejection(self.compare)

    def test_invalid_nonterminal_or_final_status_is_not_used_as_an_outcome(self):
        self.pair()
        for index, status in ((0, schema.STATUS_AFTER_WON), (1, schema.STATUS_AFTER_LOST)):
            with self.subTest(index=index):
                self.right.execute("SAVEPOINT invalid_status")
                self.right.execute("UPDATE action_events SET status_after = ? WHERE action_index = ?", (status, index))
                self.assert_unchanged_rejection(self.compare)
                self.right.execute("ROLLBACK TO invalid_status")
                self.right.execute("RELEASE invalid_status")

    def test_unknown_run_invalid_prefix_and_nonboolean_official_flag_fail(self):
        self.pair()
        for ids in ((999, 1), (1, 999), (True, 1), (1, "1")):
            with self.subTest(ids=ids):
                self.assert_unchanged_rejection(lambda: self.compare(ids))
        for prefix in (0, -1, 2, True, 1.0, "1", None):
            with self.subTest(prefix=prefix):
                self.assert_unchanged_rejection(lambda: self.compare(prefix=prefix))
        for value in (1, "true", None):
            with self.subTest(official=value):
                self.assert_unchanged_rejection(lambda: self.compare(require_official=value))

    def test_select_only_preserves_query_only_connections_and_caller_transactions(self):
        self.pair()
        before = [tuple(connection.iterdump()) for connection in (self.left, self.right)]
        statements = []
        changes = [connection.total_changes for connection in (self.left, self.right)]
        for connection in (self.left, self.right):
            connection.row_factory = None
            connection.execute("PRAGMA query_only = ON")
            connection.execute("BEGIN")
            connection.set_trace_callback(statements.append)
        try:
            self.compare(require_official=True)
        finally:
            for connection in (self.left, self.right):
                connection.set_trace_callback(None)
        self.assertTrue(statements)
        self.assertTrue(all(statement.lstrip().upper().startswith("SELECT ") for statement in statements), statements)
        for connection, count in zip((self.left, self.right), changes):
            self.assertIsNone(connection.row_factory)
            self.assertIsNone(connection.isolation_level)
            self.assertTrue(connection.in_transaction)
            self.assertEqual(connection.total_changes, count)
            self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
        self.assertEqual(before, [tuple(connection.iterdump()) for connection in (self.left, self.right)])

    def test_stage2_post_hoc_evaluation_does_not_backfill_its_configuration(self):
        self.pair()
        original = repository.fetch_run(self.left, 1)["solver_config_snapshot"]
        report = self.compare()
        self.assertEqual(repository.fetch_run(self.left, 1)["solver_config_snapshot"], original)
        self.assertEqual(set(json.loads(original)), {"accept_guesses", "initial_open"})
        self.assertNotEqual(report.left.evaluation_kind, report.right.evaluation_kind)

    def test_solver_specific_counts_and_compute_fields_are_not_comparison_metrics(self):
        self.pair()
        first = self.compare()
        self.left.execute("UPDATE action_events SET decision_compute_ns = 99999999 WHERE action_index > 0")
        self.left.execute("UPDATE action_events SET selection_candidate_count = 77 WHERE action_index > 0")
        self.right.execute("UPDATE games SET compute_time_total_ns = 999999999")
        self.assertEqual(self.compare(), first)
        names = {field.name for field in fields(first)} | {field.name for field in fields(first.primary)}
        self.assertFalse(any("compute" in name or "candidate" in name for name in names))

    def test_comparison_has_no_engine_solver_replay_or_mutating_sql_dependency(self):
        tree = ast.parse(Path(comparison.__file__).read_text(encoding="utf-8"))
        imports = set()
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        forbidden = {"core_engine", "simple_algorithm", "simple_runner", "simple_probability",
                     "simple_decision", "stage3_planner", "stage3_runner", "board_analyzer",
                     "benchmark_runner", "stage3_benchmark_runner", "replay_player"}
        self.assertFalse(imports & forbidden, imports & forbidden)
        self.assertFalse(calls & {"analyze_position", "plan_position", "run_stage3", "get_board_snapshot",
                                 "reset_with_mines", "execute_action", "connect", "commit", "rollback", "float"})


if __name__ == "__main__":
    unittest.main()
