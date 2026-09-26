"""Frozen statistics and explicit pairing over persisted telemetry facts."""

import ast
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import benchmark_statistics as statistics
import telemetry_repository as repository
import telemetry_schema as schema
from core_engine import Action, GameStatus
from telemetry_collector import TelemetryCollector
from telemetry_model import InferenceCategory


LARGE_RISK = Fraction(10**99 + 7, 10**100 + 9)


def local(timing=7):
    return InferenceCategory.LOCAL_DETERMINISTIC, Action.FLAG, timing, Fraction(1)


def global_certainty(timing=13, action=Action.OPEN):
    return InferenceCategory.GLOBAL_CERTAINTY, action, timing, Fraction(0)


def guess(risk=Fraction(1, 3), timing=11):
    return InferenceCategory.PROBABILITY_GUESS, Action.OPEN, timing, risk


class StatisticsTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "statistics.sqlite3"
        self.connection = repository.connect_database(self.database)
        self.addCleanup(self.connection.close)

    def create_run(self, **overrides):
        values = dict(
            telemetry_schema_version=schema.TELEMETRY_SCHEMA_VERSION,
            created_at="2026-09-27T00:00:00Z", git_commit="a" * 40, git_dirty=False,
            solver_stage=schema.SOLVER_STAGE_STAGE_2,
            solver_policy=schema.SOLVER_POLICY_SIMPLE_MINIMUM_RISK,
            solver_config_snapshot={"accept_guesses": True},
            width=8, height=6, num_mines=7,
            first_click_policy=schema.FIRST_CLICK_FIXED_0_0,
            board_generator_version=schema.BOARD_GENERATOR_V1,
            benchmark_set_id="TEST_STATISTICS_V1", requested_games=6,
            environment_snapshot={"python": "test-runtime", "cpu": "test-cpu"},
            run_status=schema.RUN_STATUS_RUNNING,
        )
        values.update(overrides)
        return repository.create_run(self.connection, **values)

    def persist(
        self, run_id, index=0, *, result=schema.GAME_RESULT_WIN, decisions=(),
        board_3bv=1, fingerprint=None, first_click=(0, 0),
    ):
        """Use the Collector's real summaries without executing solver logic."""
        terminal = {
            schema.GAME_RESULT_WIN: GameStatus.WON,
            schema.GAME_RESULT_LOSS: GameStatus.LOST,
        }[result]
        collector = TelemetryCollector()
        collector.record_action(
            action_type=Action.OPEN, x=first_click[0], y=first_click[1],
            status_after=GameStatus.PLAYING if decisions else terminal,
            safe_cells_opened_delta=1, explicit_flag_delta=0,
        )
        for offset, (category, action, timing, risk) in enumerate(decisions):
            status = terminal if offset == len(decisions) - 1 else GameStatus.PLAYING
            collector.record_action(
                action_type=action, x=1, y=0, status_after=status,
                safe_cells_opened_delta=int(action != Action.FLAG and status != GameStatus.LOST),
                explicit_flag_delta=int(action == Action.FLAG),
                inference_category=category, selection_candidate_count=1,
                target_mine_probability=risk,
                # Deliberately different to detect use of minimum instead of
                # selected risk. Minimum-risk policy is owned by the adapter.
                minimum_available_mine_probability=(
                    Fraction(1, 100) if category == InferenceCategory.PROBABILITY_GUESS else None
                ),
                decision_compute_ns=timing,
            )
        record = collector.finalize(
            game_index=index, seed=index,
            board_fingerprint=f"{index:064x}" if fingerprint is None else fingerprint,
            board_3bv=board_3bv, board_ops=0,
        )
        return repository.persist_completed_game(self.connection, run_id, record, collector.events)

    def finish(self, run_id, status=schema.RUN_STATUS_COMPLETED):
        repository.update_run_status(self.connection, run_id, status)

    def mixed_run(self):
        run_id = self.create_run()
        self.persist(run_id, 0, board_3bv=11, decisions=(
            local(), global_certainty(0, Action.CHORD), global_certainty(),
        ))
        self.persist(run_id, 1, board_3bv=2, result=schema.GAME_RESULT_LOSS, decisions=(guess(),))
        self.persist(run_id, 2, board_3bv=11, decisions=(
            guess(Fraction(2, 9), 5), local(17), guess(timing=19), global_certainty(23, Action.CHORD),
        ))
        self.persist(run_id, 3, board_3bv=0)
        self.finish(run_id, schema.RUN_STATUS_FAILED)
        return run_id

    def pair(self, *, requested=3, stored=None, complete=True, right_overrides=None):
        left = self.create_run(requested_games=requested)
        right = self.create_run(requested_games=requested, **(right_overrides or {}))
        for run_id in (left, right):
            for index in range(requested if stored is None else stored):
                self.persist(run_id, index)
            if complete:
                self.finish(run_id)
        return left, right


class RunStatisticsTests(StatisticsTestCase):
    def test_unknown_run_rejected_by_both_statistics_entry_points(self):
        for function in (statistics.get_run_coverage, statistics.calculate_run_statistics):
            with self.subTest(function=function.__name__):
                with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "Unknown run_id"):
                    function(self.connection, 999)

    def test_run_id_rejects_boolean_and_coercible_identity(self):
        self.create_run()
        for value in (True, False, 1.0, "1", Fraction(1), None):
            for function in (statistics.get_run_coverage, statistics.calculate_run_statistics):
                with self.subTest(value=value, function=function.__name__):
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "run_id"):
                        function(self.connection, value)

    def test_empty_failed_run_exposes_coverage_without_a_loss(self):
        run_id = self.create_run(run_status=schema.RUN_STATUS_FAILED, failure_code="TEST_FAILURE")
        result = statistics.calculate_run_statistics(self.connection, run_id)
        self.assertEqual(result.coverage, statistics.RunCoverage(
            run_id, schema.RUN_STATUS_FAILED, 6, 0, 0, False, True, False, False,
        ))
        for field in (
            "wins", "losses", "games_with_probability_guess", "local_deterministic_count",
            "global_certainty_count", "probability_guess_count", "total_actions", "open_count",
            "flag_count", "chord_count", "compute_time_total_ns", "decision_compute_count",
        ):
            self.assertEqual(getattr(result, field), 0, field)
        for field in ("win_rate", "guess_game_rate", "mean_guess_count",
                      "mean_decision_compute_ns", "max_decision_compute_ns"):
            self.assertIsNone(getattr(result, field), field)
        for field in ("guess_count_distribution", "probability_guess_distribution",
                      "decision_compute_percentiles_ns", "board_3bv_distribution"):
            self.assertEqual(getattr(result, field), (), field)

    def test_failed_run_counts_only_committed_results_and_includes_zero_guesses(self):
        run_id = self.mixed_run()
        # Other runs must not affect either summary or event aggregates.
        other = self.create_run()
        self.persist(other, result=schema.GAME_RESULT_LOSS, decisions=(guess(Fraction(1, 2), 999),))
        result = statistics.calculate_run_statistics(self.connection, run_id)
        self.assertEqual(result.coverage, statistics.RunCoverage(
            run_id, schema.RUN_STATUS_FAILED, 6, 4, 4, False, True, False, False,
        ))
        self.assertEqual((result.wins, result.losses), (3, 1))
        self.assertEqual(result.win_rate, Fraction(3, 4))
        self.assertEqual(result.games_with_probability_guess, 2)
        self.assertEqual(result.guess_game_rate, Fraction(1, 2))
        self.assertEqual(result.mean_guess_count, Fraction(3, 4))
        for value in (result.win_rate, result.guess_game_rate, result.mean_guess_count):
            self.assertIsInstance(value, Fraction)
        self.assertEqual(result.guess_count_distribution, ((0, 2), (1, 1), (2, 1)))
        self.assertEqual(result.board_3bv_distribution, ((0, 1), (2, 1), (11, 2)))
        self.assertEqual(result.probability_guess_distribution, ((Fraction(2, 9), 1), (Fraction(1, 3), 2)))
        self.assertEqual((result.local_deterministic_count, result.global_certainty_count,
                          result.probability_guess_count), (2, 3, 3))
        self.assertEqual((result.total_actions, result.open_count, result.flag_count, result.chord_count),
                         (12, 8, 2, 2))
        self.assertEqual(result.compute_time_total_ns, 95)
        self.assertEqual(result.decision_compute_count, 8)
        self.assertEqual(result.mean_decision_compute_ns, Fraction(95, 8))
        self.assertEqual(result.max_decision_compute_ns, 23)
        self.assertEqual(result.decision_compute_percentiles_ns, ((50, 11), (90, 23), (95, 23), (99, 23)))

    def test_policy_only_win_has_zero_guess_means_but_no_decision_mean(self):
        run_id = self.create_run(requested_games=1)
        self.persist(run_id)
        self.finish(run_id)
        result = statistics.calculate_run_statistics(self.connection, run_id)
        self.assertEqual(result.win_rate, Fraction(1))
        self.assertEqual(result.guess_game_rate, Fraction(0))
        self.assertEqual(result.mean_guess_count, Fraction(0))
        self.assertEqual(result.guess_count_distribution, ((0, 1),))
        self.assertEqual(result.probability_guess_distribution, ())
        self.assertEqual((result.compute_time_total_ns, result.decision_compute_count), (0, 0))
        self.assertIsNone(result.mean_decision_compute_ns)
        self.assertIsNone(result.max_decision_compute_ns)
        self.assertEqual(result.decision_compute_percentiles_ns, ())

    def test_nearest_rank_percentiles_for_exact_and_fractional_ranks(self):
        for count, expected in (
            (1, ((50, 0), (90, 0), (95, 0), (99, 0))),
            (3, ((50, 1), (90, 2), (95, 2), (99, 2))),
            (100, ((50, 49), (90, 89), (95, 94), (99, 98))),
        ):
            with self.subTest(count=count):
                run_id = self.create_run(requested_games=1)
                # Reverse persisted observation order to require numeric sorting.
                self.persist(run_id, decisions=tuple(global_certainty(t) for t in reversed(range(count))))
                result = statistics.calculate_run_statistics(self.connection, run_id)
                self.assertEqual(result.decision_compute_count, count)
                self.assertEqual(result.compute_time_total_ns, count * (count - 1) // 2)
                self.assertEqual(result.mean_decision_compute_ns, Fraction(count - 1, 2))
                self.assertEqual(result.max_decision_compute_ns, count - 1)
                self.assertEqual(result.decision_compute_percentiles_ns, expected)

    def test_large_integer_timings_remain_exact_with_ties(self):
        run_id = self.create_run()
        base = 2**53 + 1
        self.persist(run_id, decisions=tuple(global_certainty(t) for t in (base + 2, base, base)))
        result = statistics.calculate_run_statistics(self.connection, run_id)
        self.assertEqual(result.compute_time_total_ns, 3 * base + 2)
        self.assertEqual(result.mean_decision_compute_ns, Fraction(3 * base + 2, 3))
        self.assertEqual(result.max_decision_compute_ns, base + 2)
        self.assertEqual(result.decision_compute_percentiles_ns,
                         ((50, base), (90, base + 2), (95, base + 2), (99, base + 2)))
        self.assertTrue(all(type(value) is int for _, value in result.decision_compute_percentiles_ns))

    def test_compute_total_uses_summary_while_decision_statistics_use_raw_events(self):
        run_id = self.create_run()
        game_id = self.persist(run_id, decisions=(global_certainty(9),))
        # Local corruption proves that statistics neither repairs nor rederives
        # the stored game total when computing event-level measurements.
        self.connection.execute("UPDATE games SET compute_time_total_ns = 123 WHERE game_id = ?", (game_id,))
        result = statistics.calculate_run_statistics(self.connection, run_id)
        self.assertEqual(result.compute_time_total_ns, 123)
        self.assertEqual(result.mean_decision_compute_ns, Fraction(9))
        self.assertEqual(result.max_decision_compute_ns, 9)

    def test_selected_guess_risks_decode_before_numeric_ordering(self):
        run_id = self.create_run()
        self.persist(run_id, decisions=(
            guess(), local(), guess(Fraction(2, 9)), global_certainty(), guess(LARGE_RISK), guess(),
        ))
        self.assertGreater(LARGE_RISK.numerator, 2**63 - 1)
        self.assertGreater(LARGE_RISK.denominator, 2**63 - 1)
        statements = []
        self.connection.set_trace_callback(statements.append)
        try:
            with (
                patch.object(statistics, "decode_probability", wraps=repository.decode_probability) as decode,
                patch.object(Fraction, "__float__", side_effect=AssertionError("No float conversion")),
            ):
                result = statistics.calculate_run_statistics(self.connection, run_id)
        finally:
            self.connection.set_trace_callback(None)
        self.assertEqual(result.probability_guess_distribution,
                         ((LARGE_RISK, 1), (Fraction(2, 9), 1), (Fraction(1, 3), 2)))
        self.assertCountEqual([call.args[0] for call in decode.call_args_list],
                              ["1/3", "2/9", repository.encode_probability(LARGE_RISK)])
        queries = [sql.upper() for sql in statements if "TARGET_MINE_PROBABILITY" in sql.upper()]
        self.assertEqual(len(queries), 1)
        self.assertIn("GROUP BY E.TARGET_MINE_PROBABILITY", queries[0])
        for forbidden in ("ORDER BY", "MIN(", "MAX(", "AVG(", "SUM(", "CAST("):
            self.assertNotIn(forbidden, queries[0])

    def test_invalid_persisted_guess_probability_fails_instead_of_being_omitted(self):
        run_id = self.create_run()
        game_id = self.persist(run_id, decisions=(guess(),))
        for value in (None, "2/6", "not-a-probability"):
            with self.subTest(value=value):
                self.connection.execute(
                    "UPDATE action_events SET target_mine_probability = ? "
                    "WHERE game_id = ? AND inference_category = ?",
                    (value, game_id, schema.INFERENCE_PROBABILITY_GUESS),
                )
                with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "probability-guess target"):
                    statistics.calculate_run_statistics(self.connection, run_id)

    def test_analyzed_action_at_index_zero_still_counts_as_a_decision(self):
        run_id = self.create_run()
        collector = TelemetryCollector()
        collector.record_action(
            action_type=Action.OPEN, x=0, y=0, status_after=GameStatus.WON,
            safe_cells_opened_delta=1, explicit_flag_delta=0,
            inference_category=InferenceCategory.GLOBAL_CERTAINTY,
            selection_candidate_count=1, target_mine_probability=Fraction(0), decision_compute_ns=5,
        )
        record = collector.finalize(game_index=0, seed=0, board_fingerprint="0" * 64, board_3bv=1, board_ops=0)
        repository.persist_completed_game(self.connection, run_id, record, collector.events)
        result = statistics.calculate_run_statistics(self.connection, run_id)
        self.assertEqual(result.decision_compute_count, 1)
        self.assertEqual(result.mean_decision_compute_ns, Fraction(5))


class CoverageTests(StatisticsTestCase):
    def test_official_eligibility_requires_clean_completed_exact_prefix(self):
        for dirty in (False, True):
            with self.subTest(dirty=dirty):
                run_id = self.create_run(requested_games=2, git_dirty=dirty)
                for index in (1, 0):
                    self.persist(run_id, index)
                self.finish(run_id)
                self.assertEqual(statistics.get_run_coverage(self.connection, run_id), statistics.RunCoverage(
                    run_id, schema.RUN_STATUS_COMPLETED, 2, 2, 2, dirty, True, True, not dirty,
                ))

    def test_every_noncompleted_status_is_diagnostic_even_with_full_coverage(self):
        for status in (schema.RUN_STATUS_CREATED, schema.RUN_STATUS_RUNNING, schema.RUN_STATUS_ABORTED,
                       schema.RUN_STATUS_INTERRUPTED, schema.RUN_STATUS_FAILED):
            with self.subTest(status=status):
                run_id = self.create_run(requested_games=1, run_status=status)
                self.persist(run_id)
                coverage = statistics.get_run_coverage(self.connection, run_id)
                self.assertEqual(coverage.run_status, status)
                self.assertTrue(coverage.exact_requested_prefix)
                self.assertFalse(coverage.official_eligible)

    def test_same_count_shifted_or_gapped_coverage_is_not_official(self):
        for indices in ((1, 2, 3), (0, 1, 3), (0, 2, 3)):
            with self.subTest(indices=indices):
                run_id = self.create_run(requested_games=3)
                for index in indices:
                    self.persist(run_id, index)
                self.finish(run_id)
                coverage = statistics.get_run_coverage(self.connection, run_id)
                self.assertEqual((coverage.requested_games, coverage.processed_games, coverage.stored_game_count),
                                 (3, 3, 3))
                self.assertFalse(coverage.exact_processed_prefix)
                self.assertFalse(coverage.exact_requested_prefix)
                self.assertFalse(coverage.official_eligible)

    def test_partial_metadata_and_actual_stored_coverage_remain_distinct(self):
        run_id = self.create_run()
        self.persist(run_id, 0)
        self.persist(run_id, 1)
        self.finish(run_id, schema.RUN_STATUS_ABORTED)
        self.connection.execute("UPDATE benchmark_runs SET processed_games = 1 WHERE run_id = ?", (run_id,))
        coverage = statistics.get_run_coverage(self.connection, run_id)
        self.assertEqual(coverage, statistics.RunCoverage(
            run_id, schema.RUN_STATUS_ABORTED, 6, 1, 2, False, False, False, False,
        ))
        self.assertEqual(repository.fetch_run(self.connection, run_id)["processed_games"], 1)

    def test_missing_and_extra_rows_cannot_be_hidden_by_completed_metadata(self):
        for corruption in ("missing", "extra"):
            with self.subTest(corruption=corruption):
                run_id = self.create_run(requested_games=2)
                self.persist(run_id, 0)
                game_id = self.persist(run_id, 1)
                if corruption == "missing":
                    self.connection.execute("DELETE FROM games WHERE game_id = ?", (game_id,))
                else:
                    self.connection.execute(
                        "UPDATE benchmark_runs SET processed_games = 1 WHERE run_id = ?", (run_id,),
                    )
                    self.persist(run_id, 2)
                self.finish(run_id)
                coverage = statistics.get_run_coverage(self.connection, run_id)
                self.assertEqual(coverage.processed_games, 2)
                self.assertEqual(coverage.stored_game_count, 1 if corruption == "missing" else 3)
                self.assertFalse(coverage.exact_requested_prefix)
                self.assertFalse(coverage.official_eligible)

    def test_empty_run_does_not_materialize_the_requested_range(self):
        run_id = self.create_run(requested_games=2**63 - 1)
        coverage = statistics.get_run_coverage(self.connection, run_id)
        self.assertEqual(coverage.stored_game_count, 0)
        self.assertTrue(coverage.exact_processed_prefix)
        self.assertFalse(coverage.exact_requested_prefix)


class PairingTests(StatisticsTestCase):
    def test_valid_pair_allows_solver_commit_and_environment_differences(self):
        left, right = self.pair(right_overrides=dict(
            solver_stage="TEST_OTHER_STAGE", solver_policy="TEST_OTHER_POLICY",
            solver_config_snapshot={"different": True}, git_commit="b" * 40,
            environment_snapshot={"python": "other-runtime", "cpu": "other-cpu"},
        ))
        result = statistics.validate_paired_prefix(self.connection, left, right, 3, require_official=True)
        self.assertEqual(result, statistics.PairedComparison(
            left, right, "TEST_STATISTICS_V1", 3,
            tuple(statistics.PairedGameIdentity(i, i, f"{i:064x}", 0, 0) for i in range(3)), True,
        ))

    def test_each_run_compatibility_fact_is_required_even_in_diagnostic_mode(self):
        for field, value in (
            ("benchmark_set_id", "OTHER_SET"), ("width", 9), ("height", 7), ("num_mines", 8),
            ("first_click_policy", "TEST_OTHER_FIRST_CLICK"),
            ("board_generator_version", "TEST_OTHER_GENERATOR"),
            ("telemetry_schema_version", schema.TELEMETRY_SCHEMA_VERSION + 1),
        ):
            for official in (False, True):
                with self.subTest(field=field, official=official):
                    left, right = self.pair(requested=1, right_overrides={field: value})
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, field):
                        statistics.validate_paired_prefix(self.connection, left, right, 1, require_official=official)

    def test_each_game_identity_mismatch_is_rejected(self):
        for field, value in (("seed", 99), ("board_fingerprint", "f" * 64),
                             ("first_click_x", 2), ("first_click_y", 1)):
            for side in (0, 1):
                with self.subTest(field=field, side=side):
                    runs = self.pair()
                    # Fixed test-owned column names; corruption remains local.
                    self.connection.execute(
                        f"UPDATE games SET {field} = ? WHERE run_id = ? AND game_index = 1", (value, runs[side]),
                    )
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, f"game_index 1: {field}"):
                        statistics.validate_paired_prefix(self.connection, *runs, 3)

    def test_missing_first_middle_or_last_index_on_either_side_is_rejected(self):
        for side in (0, 1):
            for missing in (0, 1, 2):
                with self.subTest(side=side, missing=missing):
                    runs = self.pair()
                    self.connection.execute(
                        "DELETE FROM games WHERE run_id = ? AND game_index = ?", (runs[side], missing),
                    )
                    # An inner join would return two apparently valid pairs.
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "missing exact coverage"):
                        statistics.validate_paired_prefix(self.connection, *runs, 3)

    def test_matching_gap_on_both_sides_is_not_silently_inner_joined(self):
        left, right = self.pair()
        self.connection.execute(
            "DELETE FROM games WHERE run_id IN (?, ?) AND game_index = 1", (left, right),
        )
        with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "missing exact coverage"):
            statistics.validate_paired_prefix(self.connection, left, right, 3)

    def test_duplicate_fingerprints_at_different_indices_are_retained(self):
        runs = (self.create_run(requested_games=2), self.create_run(requested_games=2))
        for run_id in runs:
            for index in (0, 1):
                self.persist(run_id, index, fingerprint="a" * 64)
            self.finish(run_id)
        result = statistics.validate_paired_prefix(self.connection, *runs, 2, require_official=True)
        self.assertEqual(tuple(game.game_index for game in result.identities), (0, 1))
        self.assertEqual(tuple(game.seed for game in result.identities), (0, 1))
        self.assertEqual(tuple(game.board_fingerprint for game in result.identities), ("a" * 64,) * 2)

    def test_explicit_nested_prefix_of_official_runs_is_accepted(self):
        left = self.create_run(requested_games=2)
        right = self.create_run(requested_games=3)
        for run_id, count in ((left, 2), (right, 3)):
            for index in range(count):
                self.persist(run_id, index)
            self.finish(run_id)
        result = statistics.validate_paired_prefix(self.connection, left, right, 1, require_official=True)
        self.assertEqual(result.prefix_games, 1)
        self.assertEqual(len(result.identities), 1)
        self.assertTrue(result.require_official)

    def test_diagnostic_result_is_not_upgraded_when_runs_are_official_eligible(self):
        left, right = self.pair()
        result = statistics.validate_paired_prefix(self.connection, left, right, 2)
        self.assertFalse(result.require_official)
        self.assertEqual(result.prefix_games, 2)

    def test_diagnostic_prefix_does_not_compare_rows_outside_the_requested_range(self):
        left, right = self.pair()
        self.connection.execute(
            "UPDATE games SET seed = 99 WHERE run_id = ? AND game_index = 2", (right,),
        )
        result = statistics.validate_paired_prefix(self.connection, left, right, 2)
        self.assertEqual(tuple(game.game_index for game in result.identities), (0, 1))
        with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "seed"):
            statistics.validate_paired_prefix(self.connection, left, right, 3)

    def test_prefix_must_be_positive_integer_excluding_bool(self):
        left, right = self.pair()
        for value in (0, -1, True, False, 1.0, "1", Fraction(1), None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "prefix_games"):
                    statistics.validate_paired_prefix(self.connection, left, right, value)

    def test_prefix_cannot_exceed_either_requested_count_even_if_row_exists(self):
        for side in (0, 1):
            with self.subTest(side=side):
                runs = self.pair(complete=False)
                # Leave all three game rows present to separate requested-range
                # validation from actual identity coverage validation.
                self.connection.execute(
                    "UPDATE benchmark_runs SET requested_games = 2, processed_games = 2 WHERE run_id = ?",
                    (runs[side],),
                )
                for prefix in (3, 2**80):
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "exceeds requested_games"):
                        statistics.validate_paired_prefix(self.connection, *runs, prefix)

    def test_unknown_run_rejected_on_either_side(self):
        left, right = self.pair()
        for runs in ((999, right), (left, 999)):
            with self.subTest(runs=runs):
                with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "Unknown run_id"):
                    statistics.validate_paired_prefix(self.connection, *runs, 1)

    def test_pairing_rejects_coercible_run_ids_and_official_flag(self):
        left, right = self.pair()
        for runs in ((True, right), (left, str(right))):
            with self.subTest(runs=runs):
                with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "run_id"):
                    statistics.validate_paired_prefix(self.connection, *runs, 1)
        for value in (1, "false", None):
            with self.subTest(require_official=value):
                with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "require_official"):
                    statistics.validate_paired_prefix(self.connection, left, right, 1, require_official=value)

    def test_dirty_completed_run_on_either_side_is_rejected_in_official_mode(self):
        for side in (0, 1):
            with self.subTest(side=side):
                runs = self.pair()
                self.connection.execute("UPDATE benchmark_runs SET git_dirty = 1 WHERE run_id = ?", (runs[side],))
                with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "not official-eligible"):
                    statistics.validate_paired_prefix(self.connection, *runs, 2, require_official=True)
                self.assertFalse(statistics.validate_paired_prefix(self.connection, *runs, 2).require_official)

    def test_noncompleted_run_on_either_side_rejected_with_even_full_coverage(self):
        for side in (0, 1):
            for status in (schema.RUN_STATUS_RUNNING, schema.RUN_STATUS_ABORTED, schema.RUN_STATUS_FAILED):
                with self.subTest(side=side, status=status):
                    runs = self.pair()
                    self.finish(runs[side], status)
                    with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "not official-eligible"):
                        statistics.validate_paired_prefix(self.connection, *runs, 2, require_official=True)

    def test_official_mode_checks_full_requested_coverage_beyond_selected_prefix(self):
        for side in (0, 1):
            with self.subTest(side=side):
                runs = self.pair()
                self.connection.execute(
                    "UPDATE games SET game_index = 3 WHERE run_id = ? AND game_index = 2", (runs[side],),
                )
                with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "not official-eligible"):
                    statistics.validate_paired_prefix(self.connection, *runs, 2, require_official=True)
                self.assertEqual(statistics.validate_paired_prefix(self.connection, *runs, 2).prefix_games, 2)

    def test_two_partial_runs_can_pair_only_the_explicit_stored_prefix(self):
        left, right = self.pair(requested=5, stored=2, complete=False)
        self.finish(left, schema.RUN_STATUS_FAILED)
        self.finish(right, schema.RUN_STATUS_ABORTED)
        result = statistics.validate_paired_prefix(self.connection, left, right, 2)
        self.assertEqual(result.prefix_games, 2)
        self.assertEqual(len(result.identities), 2)
        self.assertFalse(result.require_official)
        with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "missing exact coverage"):
            statistics.validate_paired_prefix(self.connection, left, right, 3)
        with self.assertRaisesRegex(statistics.BenchmarkStatisticsError, "not official-eligible"):
            statistics.validate_paired_prefix(self.connection, left, right, 2, require_official=True)


class StatisticsBoundaryTests(StatisticsTestCase):
    def test_statistics_and_pairing_are_select_only_and_preserve_database_contents(self):
        left = self.mixed_run()
        right = self.create_run()
        for index in range(4):
            self.persist(right, index)
        before = tuple(self.connection.iterdump())
        changes = self.connection.total_changes
        statements = []
        rejected = []

        def allow_reads_only(operation, argument, unused, database, source):
            if operation not in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION):
                rejected.append((operation, argument))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        self.connection.set_trace_callback(statements.append)
        self.connection.set_authorizer(allow_reads_only)
        try:
            statistics.get_run_coverage(self.connection, left)
            statistics.calculate_run_statistics(self.connection, left)
            statistics.validate_paired_prefix(self.connection, left, right, 4)
            with self.assertRaises(statistics.BenchmarkStatisticsError):
                statistics.validate_paired_prefix(self.connection, left, right, 4, require_official=True)
            with self.assertRaises(statistics.BenchmarkStatisticsError):
                statistics.validate_paired_prefix(self.connection, left, right, 5)
        finally:
            self.connection.set_authorizer(None)
            self.connection.set_trace_callback(None)
        self.assertEqual(rejected, [])
        self.assertTrue(statements)
        self.assertTrue(all(sql.lstrip().upper().startswith("SELECT ") for sql in statements))
        self.assertEqual(self.connection.total_changes, changes)
        self.assertEqual(tuple(self.connection.iterdump()), before)
        self.assertFalse(self.connection.in_transaction)
        self.assertIs(self.connection.row_factory, sqlite3.Row)
        self.assertIsNone(self.connection.isolation_level)
        self.assertEqual(self.connection.execute("SELECT 1").fetchone()[0], 1)

    def test_read_only_connection_with_default_tuple_rows_is_supported(self):
        left, right = self.pair()
        reader = sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True)
        self.addCleanup(reader.close)
        self.assertTrue(statistics.get_run_coverage(reader, left).official_eligible)
        self.assertEqual(statistics.calculate_run_statistics(reader, left).wins, 3)
        self.assertTrue(statistics.validate_paired_prefix(reader, left, right, 2, require_official=True).require_official)
        self.assertIsNone(reader.row_factory)
        self.assertFalse(reader.in_transaction)
        self.assertEqual(reader.execute("SELECT 1").fetchone(), (1,))

    def test_caller_transaction_is_left_open_and_pending_work_is_not_committed(self):
        left, right = self.pair()
        self.connection.execute("BEGIN")
        try:
            self.connection.execute("UPDATE benchmark_runs SET app_version = 'pending' WHERE run_id = ?", (left,))
            changes = self.connection.total_changes
            statistics.get_run_coverage(self.connection, left)
            statistics.calculate_run_statistics(self.connection, left)
            statistics.validate_paired_prefix(self.connection, left, right, 2, require_official=True)
            self.assertTrue(self.connection.in_transaction)
            self.assertEqual(self.connection.total_changes, changes)
        finally:
            self.connection.rollback()
        self.assertIsNone(repository.fetch_run(self.connection, left)["app_version"])

    def test_results_and_nested_identities_are_immutable(self):
        left, right = self.pair()
        result = statistics.calculate_run_statistics(self.connection, left)
        pair = statistics.validate_paired_prefix(self.connection, left, right, 2)
        for model, field, value in ((result, "wins", 99), (result.coverage, "official_eligible", False),
                                    (pair, "prefix_games", 99), (pair.identities[0], "seed", 99)):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(model, field, value)
        for value in (result.guess_count_distribution, result.probability_guess_distribution,
                      result.decision_compute_percentiles_ns, result.board_3bv_distribution, pair.identities):
            self.assertIsInstance(value, tuple)

    def test_statistics_dependencies_are_standard_library_schema_and_repository_only(self):
        tree = ast.parse(Path(statistics.__file__).read_text(encoding="utf-8"))
        allowed = sys.stdlib_module_names | {"telemetry_schema", "telemetry_repository"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                self.assertIn(name.split(".")[0], allowed)


if __name__ == "__main__":
    unittest.main()
