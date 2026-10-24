"""I3 synthetic scalar fixtures only; no board generation or E2 corpus execution."""

import ast
import builtins
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction
import hashlib
import inspect
import io
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from experiments import program_k_e2_analysis as analysis
from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_records as records


SEED = bytes(range(32))
DIGEST = bytes(range(32, 64))
WIN, LOSS = records.Outcome.WIN, records.Outcome.LOSS


def row(position=0, *, game_index=None, control=200_010, kp0=10,
        control_compute=10, kp0_compute=20, outcomes=(WIN, WIN),
        setup=0, fallback=0, flag_to_open=0, diagnosis="synthetic scalar fixture",
        p3=records.P3Status.PASS):
    """Supply scalar observations; the identity is never used to generate a board."""
    board = records.BoardIdentity(
        position + 41 if game_index is None else game_index,
        "synthetic-fingerprint-" + str(position), 3, 3, 1, (0, 0),
        "synthetic generator identity", "synthetic spec identity")
    delta = kp0 - control if outcomes == (WIN, WIN) else None
    pair = records.PairComparisonRecord(
        board, outcomes[0], outcomes[1], p3, delta,
        records.G5ExposureSummary(setup, fallback, flag_to_open), diagnosis)
    return analysis.BoardAnalysisRow(
        position, pair, control, kp0, control_compute, kp0_compute)


def analyze(rows, **kwargs):
    return analysis.analyze_effectiveness(
        rows, protocol_seed=SEED, corpus_digest=DIGEST,
        concurrency=kwargs.pop("concurrency", 2), **kwargs)


def metric(lower=1, upper=1, *, zero=0, missing=0):
    undefined = zero + missing
    interval = None if undefined else (Fraction(lower), Fraction(upper))
    return analysis.BootstrapMetric(
        interval, 10_000 - undefined, undefined, zero, missing)


def gates(**changes):
    return {**{"G" + str(i): analysis.GateStatus.PASS for i in range(1, 11)},
            **changes}


class InputAndPrimaryTests(unittest.TestCase):
    def test_row_is_frozen_slotted_and_compact(self):
        value = row()
        self.assertEqual(tuple(f.name for f in fields(value)), (
            "position", "pair", "control_model_us", "kp0_model_us",
            "control_compute_ns", "kp0_compute_ns"))
        self.assertFalse(hasattr(value, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            value.position = 1

    def test_row_exact_integer_types_and_bounds(self):
        class IntSubclass(int):
            pass
        value = row()
        invalid = {
            "position": (-1, True, 1.0, IntSubclass(0)),
            "control_model_us": (None, 0, -1, True, 1.0, IntSubclass(1)),
            "kp0_model_us": (None, 0, -1, True, 1.0, IntSubclass(1)),
            "control_compute_ns": (-1, True, 1.0, IntSubclass(0)),
            "kp0_compute_ns": (-1, True, 1.0, IntSubclass(0)),
        }
        for name, values in invalid.items():
            for invalid_value in values:
                with self.subTest(name=name, value=invalid_value):
                    with self.assertRaises(analysis.AnalysisError):
                        replace(value, **{name: invalid_value})
        self.assertIsNone(replace(value, control_compute_ns=None).control_compute_ns)
        self.assertEqual(replace(value, control_compute_ns=0).control_compute_ns, 0)

    def test_pair_exact_ownership_and_nested_revalidation(self):
        class PairSubclass(records.PairComparisonRecord):
            pass
        value = row()
        copied = PairSubclass(*(getattr(value.pair, f.name) for f in fields(value.pair)))
        for invalid in (None, object(), copied):
            with self.assertRaises(analysis.AnalysisError):
                replace(value, pair=invalid)
        for owner, field in (("g5", "qualifying_fallback_flags"), ("board", "game_index")):
            damaged = row()
            object.__setattr__(getattr(damaged.pair, owner), field, True)
            with self.assertRaises(analysis.AnalysisError):
                replace(damaged)

    def test_nonterminal_model_totals_may_be_missing_but_not_invalid(self):
        for outcomes in ((records.Outcome.ERROR, WIN), (LOSS, records.Outcome.INCOMPLETE)):
            with self.subTest(outcomes=outcomes):
                value = row(outcomes=outcomes, control=None, kp0=None)
                self.assertIsNone(value.control_model_us)
                self.assertIsNone(value.kp0_model_us)
                with self.assertRaises(analysis.AnalysisError):
                    replace(value, control_model_us=0)
        for outcomes in ((WIN, LOSS), (LOSS, WIN), (LOSS, LOSS)):
            with self.assertRaises(analysis.AnalysisError):
                row(outcomes=outcomes, control=None, kp0=None)

    def test_ww_delta_must_match_signed_totals(self):
        value = row(control=101, kp0=103)
        self.assertEqual(value.pair.ww_delta_us, 2)
        for wrong in (-2, 0, 3):
            with self.assertRaises(analysis.AnalysisError):
                replace(value, pair=replace(value.pair, ww_delta_us=wrong))

    def test_whole_input_requires_exact_nonempty_tuple_and_exact_rows(self):
        class TupleSubclass(tuple):
            pass
        class RowSubclass(analysis.BoardAnalysisRow):
            pass
        value = row()
        subclass = RowSubclass(*(getattr(value, f.name) for f in fields(value)))
        for rows in ((), [], [value], iter((value,)), TupleSubclass((value,)), (object(),), (subclass,)):
            with self.subTest(kind=type(rows)), self.assertRaises(analysis.AnalysisError):
                analyze(rows)

    def test_positions_and_game_indices_are_not_sorted_or_deduplicated(self):
        cases = ((row(1), row(0)), (row(0), row(0)), (row(0), row(2)),
                 (row(0, game_index=99), row(1, game_index=99)))
        for rows in cases:
            with self.assertRaises(analysis.AnalysisError):
                analyze(rows)

    def test_entry_revalidates_exact_existing_rows(self):
        value = row()
        object.__setattr__(value, "position", True)
        with self.assertRaises(analysis.AnalysisError):
            analyze((value,))

    def test_primary_is_exact_ratio_of_totals_and_compute_is_separate(self):
        result = analyze((row(0, control=10, kp0=5, fallback=1),
                          row(1, control=30, kp0=10, fallback=1)))
        primary = result.primary
        self.assertEqual((primary.n_w, primary.s_c, primary.s_k, primary.total_delta), (2, 40, 15, -25))
        self.assertEqual(primary.ratio, Fraction(3, 8))
        self.assertNotEqual(primary.ratio, (Fraction(5, 10) + Fraction(10, 30)) / 2)
        self.assertEqual(primary.reduction, Fraction(5, 8))
        self.assertEqual(primary.mean_saving_us, Fraction(25, 2))
        self.assertIs(type(primary.ratio), Fraction)
        self.assertEqual(result.g9.observed_mean_net_headroom_ns, Fraction(12_490))

    def test_error_incomplete_and_all_terminal_categories_are_exclusive(self):
        outcomes = ((WIN, WIN), (WIN, LOSS), (LOSS, WIN), (LOSS, LOSS),
                    (records.Outcome.ERROR, records.Outcome.INCOMPLETE),
                    (records.Outcome.INCOMPLETE, records.Outcome.ERROR),
                    (WIN, records.Outcome.INCOMPLETE))
        result = analyze(tuple(row(i, outcomes=o) for i, o in enumerate(outcomes)))
        self.assertEqual(tuple(getattr(result.outcomes, name) for name in
                               ("ww", "wl", "lw", "ll", "error", "incomplete")),
                         (1, 1, 1, 1, 2, 1))
        self.assertEqual(sum(getattr(result.outcomes, f.name) for f in fields(result.outcomes)), result.n)

    def test_no_ww_keeps_zero_sums_and_undefined_effects(self):
        result = analyze((row(outcomes=(LOSS, LOSS)),))
        self.assertEqual((result.primary.n_w, result.primary.s_c, result.primary.s_k,
                          result.primary.total_delta), (0, 0, 0, 0))
        self.assertIsNone(result.primary.ratio)
        self.assertIsNone(result.primary.reduction)
        self.assertIsNone(result.primary.mean_saving_us)
        self.assertEqual(result.g8.cause, analysis.G8Cause.OBSERVED_NO_WW)
        self.assertEqual(result.g9.cause, analysis.G9Cause.OBSERVED_NO_WW)
        self.assertEqual(result.g8.status, analysis.GateStatus.DEFER)
        self.assertEqual(result.g9.status, analysis.GateStatus.DEFER)

    def test_concurrency_and_context_and_booleans_are_owned(self):
        for bad in (0, -1, True, 1.0, "2", None):
            with self.assertRaises(analysis.AnalysisError):
                analyze((row(),), concurrency=bad)
        for kwargs in ({"context": ["text"]}, {"context": (1,)},
                       {"g5_evidence_complete": 1}, {"implementation_identity_fail": 1},
                       {"pathology": "NONE"}):
            with self.assertRaises(analysis.AnalysisError):
                analyze((row(),), **kwargs)


class DiagnosticTests(unittest.TestCase):
    def test_signed_counts_odd_median_ranks_and_positive_maximum(self):
        values = (-8, -3, 0, 4, 9)
        result = analysis._diagnostics(tuple(row(i, control=100, kp0=100 + delta)
                                             for i, delta in enumerate(values)))
        self.assertEqual((result.faster, result.slower, result.ties), (2, 2, 1))
        self.assertEqual(result.distribution.median, 0)
        self.assertIs(type(result.distribution.median), int)
        self.assertEqual((result.distribution.p90, result.distribution.p95, result.distribution.p99), (9, 9, 9))
        self.assertEqual(result.maximum_slowdown, 9)

    def test_even_median_is_fraction_and_nearest_ranks_do_not_interpolate(self):
        result = analysis._distribution(tuple(range(1, 101)))
        self.assertEqual(result.median, Fraction(101, 2))
        self.assertIs(type(result.median), Fraction)
        self.assertEqual((result.p90, result.p95, result.p99), (90, 95, 99))
        self.assertEqual(result.mean, Fraction(101, 2))
        self.assertEqual((result.minimum, result.maximum, result.count), (1, 100, 100))

    def test_empty_and_no_positive_delta_have_no_maximum_slowdown(self):
        empty = analysis._diagnostics(())
        self.assertEqual(empty.distribution.count, 0)
        self.assertIsNone(empty.distribution.median)
        self.assertIsNone(empty.distribution.p99)
        self.assertIsNone(empty.maximum_slowdown)
        self.assertEqual(empty.worst, ())
        nonpositive = analysis._diagnostics((row(0, control=100, kp0=99),
                                            row(1, control=100, kp0=100)))
        self.assertIsNone(nonpositive.maximum_slowdown)

    def test_worst_twenty_sorts_delta_then_index_then_position(self):
        values = tuple(row(i, game_index=25 - i, control=100, kp0=110) for i in range(25))
        diagnostics = analysis._diagnostics(values)
        self.assertEqual(analysis.DIAGNOSTIC_WORST_N, 20)
        self.assertEqual(tuple(w.game_index for w in diagnostics.worst), tuple(range(1, 21)))
        self.assertEqual(tuple(w.position for w in diagnostics.worst), tuple(range(24, 4, -1)))
        varied = analysis._diagnostics((row(0, game_index=3, control=100, kp0=99),
                                       row(1, game_index=2, control=100, kp0=102),
                                       row(2, game_index=1, control=100, kp0=102)))
        self.assertEqual(tuple((w.delta_us, w.game_index) for w in varied.worst), ((2, 1), (2, 2), (-1, 3)))
        # Exercise the final comparator independently; whole-analysis input
        # correctly rejects duplicate game indices before reaching diagnostics.
        tied = analysis._diagnostics((row(1, game_index=7, control=100, kp0=102),
                                     row(0, game_index=7, control=100, kp0=102)))
        self.assertEqual(tuple(w.position for w in tied.worst), (0, 1))

    def test_overall_and_exposed_diagnostics_are_separate(self):
        result = analyze((row(0, control=100, kp0=90, fallback=1),
                          row(1, control=100, kp0=120)))
        self.assertEqual(result.ww_diagnostics.distribution.count, 2)
        self.assertEqual(result.g5.diagnostics.distribution.count, 1)
        self.assertEqual(result.ww_diagnostics.distribution.median, Fraction(5))
        self.assertEqual(result.g5.diagnostics.distribution.median, -10)

    def test_diagnostic_identity_and_text_do_not_change_gates(self):
        first = analyze((row(0, fallback=1), row(1, fallback=1)))
        second = analyze((row(0, game_index=900, fallback=1, diagnosis="different supplied diagnosis"),
                           row(1, game_index=899, fallback=1)))
        self.assertNotEqual(first.ww_diagnostics.worst, second.ww_diagnostics.worst)
        self.assertEqual((first.g5.status, first.g8.status, first.g9.status),
                         (second.g5.status, second.g8.status, second.g9.status))
        self.assertEqual(first.bootstrap, second.bootstrap)


class BootstrapTests(unittest.TestCase):
    def test_independent_splitmix64_golden_outputs(self):
        expected = (0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4,
                    0x06C45D188009454F, 0xF88BB8A8724C81EC)
        state = 0
        actual = []
        for _ in expected:
            state, output = analysis.splitmix64_step(state)
            actual.append(output)
        self.assertEqual(tuple(actual), expected)
        self.assertEqual(state, (4 * 0x9E3779B97F4A7C15) & ((1 << 64) - 1))

    def test_independent_synthetic_boot_seed_golden(self):
        # Independently obtained using .NET SHA256, with no E2 protocol bytes.
        golden = "6df8398e8ae5c0f3c0523611ef155e12354f45bc0c4210dbdb51d4eb8216bb3e"
        expected = hashlib.sha256(b"PROGRAM_K_E2_BOOTSTRAP_V1\0" + SEED + b"\0" + DIGEST).digest()
        self.assertEqual(expected.hex(), golden)
        self.assertEqual(analysis.bootstrap_seed(SEED, DIGEST).hex(), golden)

    def test_seed_ownership_and_exact_length(self):
        class BytesSubclass(bytes):
            pass
        bad_values = (b"", b"x" * 31, b"x" * 33, bytearray(SEED), memoryview(SEED),
                      BytesSubclass(SEED), "x" * 32, None)
        for bad in bad_values:
            for left, right in ((bad, DIGEST), (SEED, bad)):
                with self.assertRaises(analysis.AnalysisError):
                    analysis.bootstrap_seed(left, right)
                with self.assertRaises(analysis.AnalysisError):
                    analysis.analyze_effectiveness((row(),), protocol_seed=left,
                                                   corpus_digest=right, concurrency=1)

    def test_uniform_rejects_biased_tail_and_continues_state(self):
        limit = ((1 << 64) // 3) * 3
        with patch.object(analysis, "splitmix64_step", side_effect=((1, limit), (2, limit - 1))) as step:
            self.assertEqual(analysis.uniform_position(0, 3), (2, 2, 1))
        self.assertEqual([call.args for call in step.call_args_list], [(0,), (1,)])

    def test_prng_and_position_strict_bounds(self):
        for bad in (-1, 1 << 64, True, 0.0):
            with self.assertRaises(analysis.AnalysisError):
                analysis.splitmix64_step(bad)
        for bad in (0, -1, True, 1.0):
            with self.assertRaises(analysis.AnalysisError):
                analysis.uniform_position(0, bad)

    def test_each_accepted_position_updates_all_three_metrics(self):
        rows = (row(0, control=1000, kp0=990, control_compute=100, kp0_compute=101),
                row(1, control=1000, kp0=960, control_compute=100, kp0_compute=103, fallback=1),
                row(2, control=1000, kp0=930, control_compute=100, kp0_compute=107, fallback=1))
        draw_count = 0
        def draw(state, n):
            nonlocal draw_count
            self.assertEqual(n, 3)
            position = (0, 1, 1)[draw_count % 3]
            draw_count += 1
            return (state + 1) & ((1 << 64) - 1), position, 0
        with patch.object(analysis, "uniform_position", side_effect=draw) as sampled:
            result = analyze(rows)
        self.assertEqual(sampled.call_count, 30_000)
        self.assertEqual((result.bootstrap.replicates, result.bootstrap.accepted_draws,
                          result.bootstrap.rejected_draws), (10_000, 30_000, 0))
        self.assertEqual(result.bootstrap.g8.interval, (Fraction(30), Fraction(30)))
        self.assertEqual(result.bootstrap.g5.interval, (Fraction(40), Fraction(40)))
        self.assertEqual(result.bootstrap.g9.interval, (Fraction(89993, 3), Fraction(89993, 3)))
        self.assertEqual(result.bootstrap.seed_hex,
                         "6df8398e8ae5c0f3c0523611ef155e12354f45bc0c4210dbdb51d4eb8216bb3e")
        for value in (result.bootstrap.g5, result.bootstrap.g8, result.bootstrap.g9):
            self.assertEqual((value.defined_count, value.undefined_count), (10_000, 0))

    def test_registered_percentile_indices_use_all_ten_thousand_defined_means(self):
        # N=2: 249 low replicates, 9501 mixed replicates, 250 high replicates.
        # Ranks 250 and 9750 are both mixed; rank 9751 would be high.
        rows = (row(0, control=100, kp0=100, fallback=1),
                row(1, control=100, kp0=80, fallback=1))
        accepted = 0
        def draw(state, n):
            nonlocal accepted
            replicate, offset = divmod(accepted, 2)
            accepted += 1
            position = 0 if replicate < 249 else (offset if replicate < 9750 else 1)
            return (state + 1) & ((1 << 64) - 1), position, 0
        with patch.object(analysis, "uniform_position", side_effect=draw):
            result = analyze(rows)
        self.assertEqual(result.bootstrap.g8.interval, (Fraction(10), Fraction(10)))
        self.assertEqual(result.bootstrap.g5.interval, (Fraction(10), Fraction(10)))
        self.assertEqual(accepted, 20_000)

    def test_undefined_replicates_are_counted_and_never_discarded_for_interval(self):
        rows = (row(0, fallback=1), row(1, outcomes=(LOSS, LOSS)))
        result = analyze(rows)
        for value in (result.bootstrap.g5, result.bootstrap.g8, result.bootstrap.g9):
            self.assertGreater(value.undefined_count, 0)
            self.assertGreater(value.defined_count, 0)
            self.assertEqual(value.defined_count + value.undefined_count, 10_000)
            self.assertIsNone(value.interval)
        self.assertEqual(result.g5.cause, analysis.G5Cause.BOOTSTRAP_ZERO_EXPOSED_WW)
        self.assertEqual(result.g8.cause, analysis.G8Cause.BOOTSTRAP_ZERO_WW)
        self.assertEqual(result.g9.cause, analysis.G9Cause.BOOTSTRAP_ZERO_WW)

    def test_repeat_analysis_is_exactly_deterministic(self):
        rows = (row(0, fallback=1), row(1, control=400_020, kp0=20))
        self.assertEqual(analyze(rows), analyze(rows))


class BootstrapProgressTests(unittest.TestCase):
    def setUp(self):
        self.rows = (row(0, fallback=1),
                     row(1, control=400_020, kp0=20, control_compute=100,
                         kp0_compute=200, fallback=1))

    def test_none_preserves_accepted_result_golden(self):
        # Captured with these two synthetic rows from accepted source commit
        # 9071469e2e4a884722ea02e2faea3441d916876c before the observer addition.
        result = analyze(self.rows, bootstrap_progress=None)
        self.assertEqual(hashlib.sha256(repr(result).encode("utf-8")).hexdigest(),
                         "5d3f6fa9db9129be7426d5c4a463bf5defa655004ef7ed44fec28af0bc348fc0")
        self.assertEqual(result.bootstrap.accepted_draws, 20_000)

    def test_observer_preserves_result_and_reports_every_registered_replicate(self):
        baseline = analyze(self.rows)
        before = tuple(repr(value) for value in self.rows)
        events = []

        def observe(completed, total):
            self.assertIs(type(completed), int)
            self.assertIs(type(total), int)
            events.append((completed, total))
            # Only immutable scalar counts cross the observer boundary. Local
            # changes and arbitrary return values cannot supply analysis data.
            completed += 100
            total = -1
            return {"completed": completed, "total": total, "rows": ()}

        result = analyze(self.rows, bootstrap_progress=observe)
        self.assertEqual(result, baseline)
        self.assertEqual(tuple(repr(value) for value in self.rows), before)
        self.assertEqual(events, [(completed, 10_000) for completed in range(10_001)])
        self.assertEqual(result.bootstrap.replicates, 10_000)

    def test_completed_counts_follow_draws_and_callback_failure_propagates(self):
        class ObserverFailure(RuntimeError):
            pass

        original_draw = analysis.uniform_position
        for fail_at in (0, 3, 10_000):
            with self.subTest(fail_at=fail_at):
                accepted = 0
                events = []
                failure = ObserverFailure("synthetic observer failed")

                def draw(state, n):
                    nonlocal accepted
                    value = original_draw(state, n)
                    accepted += 1
                    return value

                def observe(completed, total):
                    events.append((completed, total))
                    self.assertEqual(accepted, completed * len(self.rows))
                    if completed == fail_at:
                        raise failure

                with patch.object(analysis, "uniform_position", new=draw):
                    with self.assertRaises(ObserverFailure) as raised:
                        analyze(self.rows, bootstrap_progress=observe)
                self.assertIs(raised.exception, failure)
                self.assertEqual(accepted, fail_at * len(self.rows))
                self.assertEqual(events, [(completed, 10_000) for completed in range(fail_at + 1)])

    def test_observer_preserves_shared_draws_rejections_and_exact_metrics(self):
        rows = (row(0, control=1000, kp0=990, control_compute=100, kp0_compute=101),
                row(1, control=1000, kp0=960, control_compute=100, kp0_compute=103, fallback=1),
                row(2, control=1000, kp0=930, control_compute=100, kp0_compute=107, fallback=1))
        events = []
        accepted = 0

        def draw(state, n):
            nonlocal accepted
            self.assertEqual(n, 3)
            position = (0, 1, 1)[accepted % 3]
            accepted += 1
            return (state + 1) & ((1 << 64) - 1), position, 2

        with patch.object(analysis, "uniform_position", new=draw):
            result = analyze(rows, bootstrap_progress=lambda done, total: events.append((done, total)))
        self.assertEqual((accepted, result.bootstrap.accepted_draws, result.bootstrap.rejected_draws),
                         (30_000, 30_000, 60_000))
        self.assertEqual(result.bootstrap.g8.interval, (Fraction(30), Fraction(30)))
        self.assertEqual(result.bootstrap.g5.interval, (Fraction(40), Fraction(40)))
        self.assertEqual(result.bootstrap.g9.interval, (Fraction(89993, 3), Fraction(89993, 3)))
        self.assertEqual(events, [(completed, 10_000) for completed in range(10_001)])

    def test_noncallable_observer_is_rejected_before_sampling(self):
        with patch.object(analysis, "uniform_position", side_effect=AssertionError("Unexpected sampling")):
            for invalid in (False, 0, "observer", (), [], object()):
                with self.subTest(invalid=type(invalid)):
                    with self.assertRaises(analysis.AnalysisError):
                        analyze(self.rows, bootstrap_progress=invalid)
                    with self.assertRaises(analysis.AnalysisError):
                        analysis._shared_bootstrap(self.rows, SEED, DIGEST, progress=invalid)

    def test_invalid_analysis_input_does_not_start_progress(self):
        events = []
        with self.assertRaises(analysis.AnalysisError):
            analyze(self.rows[::-1], bootstrap_progress=lambda done, total: events.append((done, total)))
        self.assertEqual(events, [])


class G5Tests(unittest.TestCase):
    def test_zero_exposure_even_with_setup_flags_is_not_applicable(self):
        result = analyze((row(setup=77),), g5_evidence_complete=True)
        self.assertEqual(result.g5.exposure_count, 0)
        self.assertEqual(result.g5.exposure_fraction, Fraction(0))
        self.assertEqual(result.g5.diagnostic_setup_chord_flags, 77)
        self.assertEqual(result.g5.status, analysis.GateStatus.NOT_APPLICABLE)
        self.assertEqual(result.g5.cause, analysis.G5Cause.NO_EXPOSURE)

    def test_zero_exposure_with_incomplete_evidence_is_incomplete(self):
        result = analyze((row(setup=77),), g5_evidence_complete=False,
                         gate_statuses=gates(G5=analysis.GateStatus.INCOMPLETE))
        self.assertEqual(result.g5.exposure_count, 0)
        self.assertEqual(result.g5.diagnostic_setup_chord_flags, 77)
        self.assertEqual((result.g5.status, result.g5.cause),
                         (analysis.GateStatus.INCOMPLETE, analysis.G5Cause.MISSING_REQUIRED_DATA))
        self.assertEqual(result.overall.verdict, analysis.OverallVerdict.INCOMPLETE)
        self.assertFalse(result.overall.e3_trigger)

    def test_zero_exposure_na_requires_complete_evidence_before_bootstrap_state(self):
        for complete in (True, False):
            expected = ((analysis.GateStatus.NOT_APPLICABLE, analysis.G5Cause.NO_EXPOSURE)
                        if complete else
                        (analysis.GateStatus.INCOMPLETE, analysis.G5Cause.MISSING_REQUIRED_DATA))
            for bootstrap in (metric(), metric(zero=10_000), metric(missing=1)):
                with self.subTest(complete=complete, bootstrap=bootstrap):
                    self.assertEqual(analysis.classify_g5(
                        exposure_count=0, evidence_complete=complete, bootstrap=bootstrap), expected)
        self.assertEqual(analysis.classify_g5(
            exposure_count=1, evidence_complete=True, bootstrap=metric(missing=1)),
            (analysis.GateStatus.INCOMPLETE, analysis.G5Cause.MISSING_REQUIRED_DATA))

    def test_invalid_g5_na_cannot_support_overall_research_pass(self):
        statuses = gates(G5=analysis.GateStatus.NOT_APPLICABLE)
        with self.assertRaises(analysis.AnalysisError):
            analyze((row(),), g5_evidence_complete=False, gate_statuses=statuses)
        valid = analyze((row(),), gate_statuses=statuses)
        with self.assertRaises(analysis.AnalysisError):
            replace(valid.g5, evidence_complete=False)
        corrupted_g5 = replace(valid.g5)
        object.__setattr__(corrupted_g5, "evidence_complete", False)
        with self.assertRaises(analysis.AnalysisError):
            replace(valid, g5=corrupted_g5)

    def test_all_row_exposure_counts_are_separate_from_exposed_ww(self):
        result = analyze((row(0, fallback=2, setup=5),
                          row(1, outcomes=(LOSS, LOSS), flag_to_open=3, setup=7),
                          row(2, setup=11)))
        self.assertEqual(result.g5.exposure_count, 2)
        self.assertEqual(result.g5.exposure_fraction, Fraction(2, 3))
        self.assertEqual(result.g5.exposed_ww_count, 1)
        self.assertEqual(result.g5.qualifying_fallback_flags, 2)
        self.assertEqual(result.g5.qualifying_flag_to_open_setup_flags, 3)
        self.assertEqual(result.g5.diagnostic_setup_chord_flags, 23)
        self.assertEqual(result.g5.mean_saving_us, Fraction(200_000))

    def test_missing_evidence_precedes_undefined_exposed_bootstrap(self):
        result = analysis.classify_g5(exposure_count=1, evidence_complete=False, bootstrap=metric(zero=1))
        self.assertEqual(result, (analysis.GateStatus.INCOMPLETE, analysis.G5Cause.MISSING_REQUIRED_DATA))
        integrated = analyze((row(fallback=1),), g5_evidence_complete=False)
        self.assertEqual(integrated.g5.status, analysis.GateStatus.INCOMPLETE)

    def test_g5_exact_interval_inequalities(self):
        cases = ((0, 0, analysis.GateStatus.PASS), (0, 2, analysis.GateStatus.PASS),
                 (-3, -1, analysis.GateStatus.FAIL), (-1, 0, analysis.GateStatus.DEFER),
                 (-1, 1, analysis.GateStatus.DEFER))
        for lower, upper, expected in cases:
            with self.subTest(lower=lower, upper=upper):
                status, _ = analysis.classify_g5(exposure_count=1, evidence_complete=True,
                                                  bootstrap=metric(lower, upper))
                self.assertEqual(status, expected)

    def test_exposure_without_any_ww_remains_defer(self):
        result = analyze((row(outcomes=(LOSS, LOSS), fallback=1),))
        self.assertEqual(result.g5.exposed_ww_count, 0)
        self.assertIsNone(result.g5.mean_saving_us)
        self.assertEqual(result.g5.status, analysis.GateStatus.DEFER)


class G8Tests(unittest.TestCase):
    def test_missing_model_data_classification_without_weakening_row(self):
        status, cause = analysis.classify_g8(
            observed_ww=1, missing_required_data=True, bootstrap=metric(zero=1))
        self.assertEqual((status, cause),
                         (analysis.GateStatus.INCOMPLETE, analysis.G8Cause.MISSING_REQUIRED_DATA))
        with self.assertRaises(analysis.AnalysisError):
            replace(row(), control_model_us=None)

    def test_g8_exact_margin_boundaries(self):
        self.assertEqual(identity.PRACTICAL_MARGIN_US_PER_WW, 126_005)
        cases = ((126006, 126007, analysis.GateStatus.PASS),
                 (126004, 126004, analysis.GateStatus.FAIL),
                 (126005, 126005, analysis.GateStatus.DEFER),
                 (126005, 126006, analysis.GateStatus.DEFER),
                 (126004, 126005, analysis.GateStatus.DEFER),
                 (126004, 126006, analysis.GateStatus.DEFER))
        for lower, upper, expected in cases:
            with self.subTest(lower=lower, upper=upper):
                status, cause = analysis.classify_g8(
                    observed_ww=1, missing_required_data=False, bootstrap=metric(lower, upper))
                self.assertEqual(status, expected)
                self.assertEqual(cause, analysis.G8Cause.MARGIN_OVERLAP
                                 if expected is analysis.GateStatus.DEFER else analysis.G8Cause.NONE)

    def test_observed_no_ww_has_precedence_over_bootstrap_zero(self):
        actual = analysis.classify_g8(observed_ww=0, missing_required_data=False, bootstrap=metric(zero=10_000))
        self.assertEqual(actual, (analysis.GateStatus.DEFER, analysis.G8Cause.OBSERVED_NO_WW))


class G9Tests(unittest.TestCase):
    def test_exact_headroom_compute_diagnostics_and_supplied_concurrency(self):
        result = analyze((row(0, control=31, kp0=20, control_compute=7, kp0_compute=300),
                          row(1, control=50, kp0=20, control_compute=500, kp0_compute=200)), concurrency=7)
        self.assertEqual(result.g9.observed_mean_net_headroom_ns, Fraction(41007, 2))
        self.assertEqual(result.g9.control_compute.mean, Fraction(507, 2))
        self.assertEqual(result.g9.kp0_compute.mean, Fraction(250))
        self.assertEqual(result.g9.added_compute.mean, Fraction(-7, 2))
        self.assertEqual((result.concurrency, result.g9.concurrency), (7, 7))

    def test_missing_compute_has_highest_g9_precedence_and_is_never_zero(self):
        for pathology in analysis.G9PathologyDisposition:
            with self.subTest(pathology=pathology):
                result = analyze((row(control_compute=None),), pathology=pathology)
                self.assertEqual(result.g9.status, analysis.GateStatus.INCOMPLETE)
                self.assertEqual(result.g9.cause, analysis.G9Cause.MISSING_REQUIRED_DATA)
                self.assertEqual(result.g9.missing_compute_rows, 1)
                self.assertIsNone(result.g9.observed_mean_net_headroom_ns)
                self.assertEqual(result.g9.control_compute.count, 0)
                self.assertEqual(result.g9.kp0_compute.count, 1)
                self.assertEqual(result.g9.added_compute.count, 0)

    def test_non_ww_missing_compute_is_not_required(self):
        result = analyze((row(0), row(1, outcomes=(LOSS, LOSS), control_compute=None, kp0_compute=None)))
        self.assertEqual(result.g9.missing_compute_rows, 0)
        self.assertNotEqual(result.g9.status, analysis.GateStatus.INCOMPLETE)

    def test_pathology_precedes_no_ww_or_bootstrap_zero(self):
        for pathology, status, cause in (
                (analysis.G9PathologyDisposition.INHERENT_PATHOLOGY, analysis.GateStatus.FAIL,
                 analysis.G9Cause.INHERENT_PATHOLOGY),
                (analysis.G9PathologyDisposition.UNRESOLVED_PATHOLOGY, analysis.GateStatus.DEFER,
                 analysis.G9Cause.UNRESOLVED_PATHOLOGY)):
            actual = analysis.classify_g9(observed_ww=0, missing_compute=False,
                                          pathology=pathology, bootstrap=metric(zero=10_000))
            self.assertEqual(actual, (status, cause))

    def test_interval_never_causes_g9_fail(self):
        for lower, upper, expected in ((1, 2, analysis.GateStatus.PASS),
                                       (0, 0, analysis.GateStatus.DEFER),
                                       (-2, -1, analysis.GateStatus.DEFER),
                                       (-1, 1, analysis.GateStatus.DEFER)):
            actual, cause = analysis.classify_g9(
                observed_ww=1, missing_compute=False, pathology=analysis.G9PathologyDisposition.NONE,
                bootstrap=metric(lower, upper))
            self.assertEqual(actual, expected)
            self.assertEqual(cause, analysis.G9Cause.NONE if expected is analysis.GateStatus.PASS
                             else analysis.G9Cause.NONPOSITIVE_LOWER_BOUND)

    def test_pathology_vocabulary_has_no_implementation_defect(self):
        self.assertEqual({value.value for value in analysis.G9PathologyDisposition},
                         {"NONE", "UNRESOLVED_PATHOLOGY", "INHERENT_PATHOLOGY"})


class VerdictTests(unittest.TestCase):
    def test_exact_five_way_priority(self):
        status = analysis.GateStatus
        cases = ((gates(G1=status.INCOMPLETE, G2=status.FAIL, G3=status.DEFER), True,
                  analysis.OverallVerdict.IMPLEMENTATION_IDENTITY_FAIL),
                 (gates(G1=status.INCOMPLETE, G2=status.FAIL, G3=status.DEFER), False,
                  analysis.OverallVerdict.INCOMPLETE),
                 (gates(G2=status.FAIL, G3=status.DEFER), False, analysis.OverallVerdict.RESEARCH_FAIL),
                 (gates(G3=status.DEFER), False, analysis.OverallVerdict.RESEARCH_DEFER),
                 (gates(), False, analysis.OverallVerdict.RESEARCH_PASS),
                 (gates(G5=status.NOT_APPLICABLE), False, analysis.OverallVerdict.RESEARCH_PASS))
        for statuses, identity_fail, expected in cases:
            self.assertEqual(analysis.classify_overall(statuses, implementation_identity_fail=identity_fail), expected)

    def test_gate_set_is_exact_even_under_identity_fail(self):
        class DictSubclass(dict):
            pass
        bad_sets = [(), list(gates().items()), DictSubclass(gates()),
                    {key: value for key, value in gates().items() if key != "G10"},
                    gates(G11=analysis.GateStatus.PASS), gates(G1="PASS")]
        for name in ("G1", "G2", "G3", "G4", "G6", "G7", "G8", "G9", "G10"):
            bad_sets.append(gates(**{name: analysis.GateStatus.NOT_APPLICABLE}))
        for statuses in bad_sets:
            for identity_fail in (False, True):
                with self.assertRaises(analysis.AnalysisError):
                    analysis.classify_overall(statuses, implementation_identity_fail=identity_fail)
        for bad in (0, 1, None, "false"):
            with self.assertRaises(analysis.AnalysisError):
                analysis.classify_overall(gates(), implementation_identity_fail=bad)

    def test_e3_requires_exact_margin_overlap_and_all_other_gates_qualified(self):
        for g5 in (analysis.GateStatus.PASS, analysis.GateStatus.NOT_APPLICABLE):
            statuses = gates(G5=g5, G8=analysis.GateStatus.DEFER)
            self.assertTrue(analysis.e3_trigger(statuses, implementation_identity_fail=False,
                                                g8_cause=analysis.G8Cause.MARGIN_OVERLAP))
            self.assertFalse(analysis.e3_trigger(statuses, implementation_identity_fail=True,
                                                 g8_cause=analysis.G8Cause.MARGIN_OVERLAP))
        statuses = gates(G8=analysis.GateStatus.DEFER)
        for cause in analysis.G8Cause:
            self.assertEqual(analysis.e3_trigger(statuses, implementation_identity_fail=False, g8_cause=cause),
                             cause is analysis.G8Cause.MARGIN_OVERLAP)
        for name in statuses:
            for bad in (analysis.GateStatus.FAIL, analysis.GateStatus.INCOMPLETE, analysis.GateStatus.DEFER):
                if name == "G8" and bad is analysis.GateStatus.DEFER:
                    continue
                with self.subTest(name=name, status=bad):
                    self.assertFalse(analysis.e3_trigger(
                        statuses | {name: bad}, implementation_identity_fail=False,
                        g8_cause=analysis.G8Cause.MARGIN_OVERLAP))
        for g8 in (analysis.GateStatus.PASS, analysis.GateStatus.FAIL):
            self.assertFalse(analysis.e3_trigger(gates(G8=g8), implementation_identity_fail=False,
                                                 g8_cause=analysis.G8Cause.MARGIN_OVERLAP))

    def test_e3_rejects_inexact_cause_and_incomplete_gate_set(self):
        for cause in ("MARGIN_OVERLAP", None, 1):
            with self.assertRaises(analysis.AnalysisError):
                analysis.e3_trigger(gates(G8=analysis.GateStatus.DEFER),
                                    implementation_identity_fail=False, g8_cause=cause)
        with self.assertRaises(analysis.AnalysisError):
            analysis.e3_trigger({}, implementation_identity_fail=True,
                                g8_cause=analysis.G8Cause.MARGIN_OVERLAP)

    def test_supplied_overall_is_owned_and_must_match_computed_gates(self):
        statuses = gates(G5=analysis.GateStatus.NOT_APPLICABLE)
        result = analyze((row(),), gate_statuses=statuses)
        self.assertIsNotNone(result.overall)
        snapshot = result.overall
        statuses["G1"] = analysis.GateStatus.FAIL
        self.assertEqual(result.overall, snapshot)
        self.assertEqual(dict(result.overall.gates)["G1"], analysis.GateStatus.PASS)
        for name in ("G5", "G8", "G9"):
            with self.assertRaises(analysis.AnalysisError):
                analyze((row(),), gate_statuses=gates(G5=analysis.GateStatus.NOT_APPLICABLE)
                        | {name: analysis.GateStatus.FAIL})
        with self.assertRaises(analysis.AnalysisError):
            analyze((row(fallback=1),), gate_statuses=gates(G5=analysis.GateStatus.NOT_APPLICABLE))

    def test_raw_comparator_failure_is_not_automatically_research_failure(self):
        result = analyze((row(p3=records.P3Status.FAIL),),
                         gate_statuses=gates(G5=analysis.GateStatus.NOT_APPLICABLE))
        self.assertIsNotNone(result.overall)
        self.assertEqual(result.overall.verdict, analysis.OverallVerdict.RESEARCH_PASS)
        self.assertEqual(result.g8.status, analysis.GateStatus.PASS)
        self.assertEqual(result.g9.status, analysis.GateStatus.PASS)


class ResultInvariantTests(unittest.TestCase):
    def test_analysis_result_rejects_contradictory_g5_status_and_cause(self):
        valid = analyze((row(fallback=1),))
        incomplete = analyze((row(fallback=1),), g5_evidence_complete=False)
        cases = ((valid, replace(valid.g5, status=analysis.GateStatus.FAIL)),
                 (valid, replace(valid.g5, cause=analysis.G5Cause.MISSING_REQUIRED_DATA)),
                 (incomplete, replace(incomplete.g5, status=analysis.GateStatus.PASS,
                                      cause=analysis.G5Cause.NONE)))
        for result, contradictory in cases:
            with self.subTest(status=contradictory.status, cause=contradictory.cause):
                with self.assertRaisesRegex(analysis.AnalysisError, "G5 status/cause"):
                    replace(result, g5=contradictory)

    def test_analysis_result_rejects_contradictory_g8_status_and_cause(self):
        valid = analyze((row(),))
        margin = analyze((row(control=126_006, kp0=1),))
        below = analyze((row(control=126_005, kp0=1),))
        cases = ((valid, replace(valid.g8, status=analysis.GateStatus.FAIL)),
                 (valid, replace(valid.g8, cause=analysis.G8Cause.MARGIN_OVERLAP)),
                 (valid, replace(valid.g8, status=analysis.GateStatus.INCOMPLETE,
                                 cause=analysis.G8Cause.MISSING_REQUIRED_DATA)),
                 (margin, replace(margin.g8, status=analysis.GateStatus.PASS)),
                 (below, replace(below.g8, status=analysis.GateStatus.PASS,
                                 cause=analysis.G8Cause.MARGIN_OVERLAP)))
        for result, contradictory in cases:
            with self.subTest(status=contradictory.status, cause=contradictory.cause):
                with self.assertRaisesRegex(analysis.AnalysisError, "G8 status/cause"):
                    replace(result, g8=contradictory)

    def test_analysis_result_rejects_contradictory_g9_status_and_cause(self):
        valid = analyze((row(),))
        missing = analyze((row(control_compute=None),))
        cases = ((valid, replace(valid.g9, status=analysis.GateStatus.FAIL)),
                 (valid, replace(valid.g9, cause=analysis.G9Cause.INHERENT_PATHOLOGY)),
                 (valid, replace(valid.g9, pathology=analysis.G9PathologyDisposition.INHERENT_PATHOLOGY)),
                 (missing, replace(missing.g9, status=analysis.GateStatus.PASS,
                                   cause=analysis.G9Cause.NONE)))
        for result, contradictory in cases:
            with self.subTest(status=contradictory.status, cause=contradictory.cause):
                with self.assertRaisesRegex(analysis.AnalysisError, "G9 status/cause"):
                    replace(result, g9=contradictory)

    def test_gate_invariants_use_ww_count_and_observed_missing_compute(self):
        no_ww = analyze((row(outcomes=(LOSS, LOSS), fallback=1),))
        for name in ("g8", "g9"):
            cause = (analysis.G8Cause.BOOTSTRAP_ZERO_WW if name == "g8"
                     else analysis.G9Cause.BOOTSTRAP_ZERO_WW)
            with self.subTest(gate=name), self.assertRaisesRegex(analysis.AnalysisError, "status/cause"):
                replace(no_ww, **{name: replace(getattr(no_ww, name), cause=cause)})
        valid = analyze((row(),))
        # Isolate the observed-missing input: bootstrap still has defined means.
        contradictory = replace(valid.g9, missing_compute_rows=1, observed_mean_net_headroom_ns=None)
        with self.assertRaisesRegex(analysis.AnalysisError, "G9 status/cause"):
            replace(valid, g9=contradictory)

    def test_na_result_status_is_valid_only_for_zero_exposure_g5(self):
        unexposed = analyze((row(),))
        exposed = analyze((row(fallback=1),))
        for value in (unexposed.g8, unexposed.g9, exposed.g5):
            with self.assertRaises(analysis.AnalysisError):
                replace(value, status=analysis.GateStatus.NOT_APPLICABLE)
        with self.assertRaises(analysis.AnalysisError):
            replace(unexposed.g5, status=analysis.GateStatus.PASS)

    def test_overall_result_rejects_contradictory_verdict_and_unqualified_e3(self):
        status = analysis.GateStatus
        cases = ((gates(G1=status.INCOMPLETE, G2=status.FAIL, G3=status.DEFER), True,
                  analysis.OverallVerdict.IMPLEMENTATION_IDENTITY_FAIL),
                 (gates(G1=status.INCOMPLETE, G2=status.FAIL, G3=status.DEFER), False,
                  analysis.OverallVerdict.INCOMPLETE),
                 (gates(G8=status.FAIL, G3=status.DEFER), False, analysis.OverallVerdict.RESEARCH_FAIL),
                 (gates(G3=status.DEFER), False, analysis.OverallVerdict.RESEARCH_DEFER),
                 (gates(), False, analysis.OverallVerdict.RESEARCH_PASS))
        for statuses, identity_fail, verdict in cases:
            value = analysis.OverallAssessment(tuple(statuses.items()), identity_fail, verdict, False)
            for wrong in analysis.OverallVerdict:
                if wrong is not verdict:
                    with self.assertRaises(analysis.AnalysisError):
                        replace(value, verdict=wrong)
        failed = analysis.OverallAssessment(tuple(gates(G8=status.FAIL).items()), False,
                                            analysis.OverallVerdict.RESEARCH_FAIL, False)
        with self.assertRaises(analysis.AnalysisError):
            replace(failed, e3_trigger=True)

    def test_analysis_result_rejects_false_e3_for_exact_qualified_margin_overlap(self):
        result = analyze((row(control=126_006, kp0=1),),
                         gate_statuses=gates(G5=analysis.GateStatus.NOT_APPLICABLE,
                                             G8=analysis.GateStatus.DEFER))
        self.assertEqual(result.g8.cause, analysis.G8Cause.MARGIN_OVERLAP)
        self.assertTrue(result.overall.e3_trigger)
        with self.assertRaises(analysis.AnalysisError):
            replace(result, overall=replace(result.overall, e3_trigger=False))


class G9CompactSummaryInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.complete = analyze((row(0, control_compute=2, kp0_compute=10),
                                row(1, control_compute=6, kp0_compute=8)))
        cls.missing = analyze((row(0, control_compute=2, kp0_compute=10),
                               row(1, control_compute=6, kp0_compute=None),
                               row(2, control_compute=None, kp0_compute=30)))
        cls.no_ww = analyze((row(outcomes=(LOSS, LOSS), control_compute=None, kp0_compute=None),))

    def test_valid_complete_missing_and_no_ww_summaries_remain_valid(self):
        for result in (self.complete, self.missing, self.no_ww):
            self.assertEqual(replace(result), result)
        complete = self.complete.g9
        self.assertEqual((complete.control_compute.count, complete.kp0_compute.count,
                          complete.added_compute.count, complete.missing_compute_rows), (2, 2, 2, 0))
        self.assertEqual((complete.control_compute.mean, complete.kp0_compute.mean,
                          complete.added_compute.mean), (Fraction(4), Fraction(9), Fraction(5)))
        self.assertEqual(complete.observed_mean_net_headroom_ns, Fraction(199_999_995))
        missing = self.missing.g9
        self.assertEqual((missing.control_compute.count, missing.kp0_compute.count,
                          missing.added_compute.count, missing.missing_compute_rows), (2, 2, 1, 2))
        self.assertNotEqual(missing.added_compute.mean, missing.kp0_compute.mean - missing.control_compute.mean)
        self.assertIsNone(missing.observed_mean_net_headroom_ns)
        self.assertEqual(missing.status, analysis.GateStatus.INCOMPLETE)
        empty = self.no_ww.g9
        self.assertEqual((empty.control_compute.count, empty.kp0_compute.count,
                          empty.added_compute.count, empty.missing_compute_rows), (0, 0, 0, 0))
        self.assertIsNone(empty.observed_mean_net_headroom_ns)

    def test_complete_compute_rejects_arbitrary_observed_fraction(self):
        changed = replace(self.complete.g9, observed_mean_net_headroom_ns=Fraction(123, 7))
        with self.assertRaisesRegex(analysis.AnalysisError, "G9 observed net headroom"):
            replace(self.complete, g9=changed)

    def test_complete_compute_requires_present_exact_observed_mean(self):
        for value in (None, 0, True, 1.0):
            with self.subTest(value=value):
                changed = replace(self.complete.g9)
                object.__setattr__(changed, "observed_mean_net_headroom_ns", value)
                with self.assertRaises(analysis.AnalysisError):
                    replace(self.complete, g9=changed)

    def test_complete_compute_rejects_changed_added_mean_even_if_observed_is_adjusted(self):
        # Six is within the stored added-compute min/max, so local distribution
        # validation alone cannot detect the cross-summary arithmetic corruption.
        added = replace(self.complete.g9.added_compute, mean=Fraction(6))
        for observed in (self.complete.g9.observed_mean_net_headroom_ns,
                         self.complete.primary.mean_saving_us * 1000 - added.mean):
            changed = replace(self.complete.g9, added_compute=added, observed_mean_net_headroom_ns=observed)
            with self.assertRaisesRegex(analysis.AnalysisError, "G9 complete-compute mean arithmetic"):
                replace(self.complete, g9=changed)

    def test_complete_compute_rejects_incorrect_control_kp0_added_counts(self):
        for name in ("control_compute", "kp0_compute", "added_compute"):
            for count in (0, 1, 3):
                with self.subTest(distribution=name, count=count):
                    changed = replace(self.complete.g9, **{name: analysis._distribution((7,) * count)})
                    with self.assertRaisesRegex(analysis.AnalysisError, "G9 comparable-compute distribution counts"):
                        replace(self.complete, g9=changed)

    def test_no_ww_rejects_fabricated_observed_mean(self):
        changed = replace(self.no_ww.g9, observed_mean_net_headroom_ns=Fraction(1))
        with self.assertRaisesRegex(analysis.AnalysisError, "requires no observed G9 mean"):
            replace(self.no_ww, g9=changed)

    def test_missing_compute_rejects_fabricated_observed_mean(self):
        changed = replace(self.missing.g9)
        object.__setattr__(changed, "observed_mean_net_headroom_ns", Fraction(1))
        with self.assertRaises(analysis.AnalysisError):
            replace(self.missing, g9=changed)

    def test_missing_compute_requires_added_count_to_equal_available_pairs(self):
        for count in (0, 2):
            with self.subTest(count=count):
                changed = replace(self.missing.g9, added_compute=analysis._distribution((8,) * count))
                with self.assertRaisesRegex(analysis.AnalysisError, "G9 comparable-compute distribution counts"):
                    replace(self.missing, g9=changed)

    def test_partial_arm_counts_stay_between_available_pairs_and_ww_count(self):
        for name in ("control_compute", "kp0_compute"):
            for count in (0, 4):
                with self.subTest(distribution=name, count=count):
                    changed = replace(self.missing.g9, **{name: analysis._distribution((7,) * count)})
                    with self.assertRaisesRegex(analysis.AnalysisError, "G9 comparable-compute distribution counts"):
                        replace(self.missing, g9=changed)

    def test_no_ww_rejects_nonempty_compute_distributions(self):
        for name in ("control_compute", "kp0_compute", "added_compute"):
            with self.subTest(distribution=name):
                changed = replace(self.no_ww.g9, **{name: analysis._distribution((1,))})
                with self.assertRaisesRegex(analysis.AnalysisError, "G9 comparable-compute distribution counts"):
                    replace(self.no_ww, g9=changed)


class PurityAndMemoryBoundaryTests(unittest.TestCase):
    def test_ast_dependency_boundary_and_no_dynamic_execution(self):
        source = inspect.getsource(analysis)
        tree = ast.parse(source)
        forbidden_roots = {"os", "pathlib", "subprocess", "socket", "sqlite3", "random"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name.split(".")[0], sys.stdlib_module_names)
                    self.assertNotIn(alias.name.split(".")[0], forbidden_roots)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                if node.module == "experiments":
                    self.assertTrue({alias.name for alias in node.names} <=
                                    {"program_k_e2_identity", "program_k_e2_records"})
                elif node.module.startswith("experiments."):
                    self.assertIn(node.module, {"experiments.program_k_e2_identity",
                                                "experiments.program_k_e2_records"})
                else:
                    self.assertIn(node.module.split(".")[0], sys.stdlib_module_names)
                    self.assertNotIn(node.module.split(".")[0], forbidden_roots)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "exec", "eval", "__import__", "compile"})
        self.assertNotIn("__dict__", source)

    def test_shared_bootstrap_has_one_sampling_site_and_no_draw_matrix(self):
        tree = ast.parse(inspect.getsource(analysis._shared_bootstrap))
        sampling = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name) and node.func.id == "uniform_position"]
        self.assertEqual(len(sampling), 1)
        for node in ast.walk(tree):
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                self.assertLessEqual(len(node.generators), 1, "No nested draw matrix comprehension")
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else "")
                self.assertNotIn(name, {"deepcopy", "copy", "load", "decode", "read", "read_bytes", "read_text"})
        # Output retains summary scalars, never 10,000 means or sampled positions.
        result = analyze((row(fallback=1),))
        self.assertEqual(tuple(field.name for field in fields(result.bootstrap)),
                         ("replicates", "accepted_draws", "rejected_draws", "seed_hex", "g5", "g8", "g9"))

    def test_result_is_deeply_immutable_without_evidence_graphs_or_float(self):
        result = analyze((row(fallback=1),), context=("supplied context",))
        def check(value):
            self.assertNotIsInstance(value, (float, list, dict, records.PairComparisonRecord,
                                            records.BoardIdentity, records.PhysicalInputRecord,
                                            records.DecisionSpanRecord))
            if is_dataclass(value):
                self.assertFalse(hasattr(value, "__dict__"))
                self.assertTrue(value.__dataclass_params__.frozen)
                for field in fields(value):
                    check(getattr(value, field.name))
            elif type(value) is tuple:
                for child in value:
                    check(child)
        check(result)
        with self.assertRaises(FrozenInstanceError):
            result.n = 2

    def test_fresh_module_and_analysis_do_not_access_io_or_execution(self):
        source = compile(inspect.getsource(analysis), analysis.__file__, "exec")
        name = "_i3_analysis_purity_probe"
        probe = types.ModuleType(name)
        supplied = (row(fallback=1),)
        targets = ((builtins, "open"), (io, "open"), (os, "open"), (os, "stat"),
                   (os, "listdir"), (os, "scandir"), (os, "getcwd"), (os, "getenv"),
                   (os, "system"), (subprocess, "Popen"), (subprocess, "run"),
                   (Path, "read_bytes"), (Path, "write_bytes"), (Path, "read_text"), (Path, "write_text"))
        with patch.dict(sys.modules, {name: probe}), ExitStack() as stack:
            for owner, attribute in targets:
                stack.enter_context(patch.object(owner, attribute, side_effect=AssertionError("Unexpected I/O")))
            for name_to_block in ("select_indices", "select_subset_positions", "corpus_digest",
                                  "validate_protocol_bytes", "arm_order"):
                stack.enter_context(patch.object(identity, name_to_block,
                                                side_effect=AssertionError("Unexpected corpus/execution work")))
            exec(source, probe.__dict__)
            result = analyze(supplied)
        self.assertEqual(result.n, 1)


if __name__ == "__main__":
    unittest.main()
