"""I8 pure admission qualification using tiny literal operational measurements.

The synthetic seeds select indices only. No boards, solver, real rehearsal,
Nmax payloads, bootstrap calculation, official evidence or envelope is produced.
"""

from contextlib import contextmanager, ExitStack
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import ast
import builtins
import inspect
import io
import os
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_operational as op
from experiments import program_k_e2_qualification as q
from experiments import program_k_e2_readiness as r
from experiments import program_k_e2_records as records


_SEED = b"synthetic-i8-operational-seed-v1"
_PHASES = (records.Phase.AGGREGATION, records.Phase.VALIDATION,
           records.Phase.PUBLICATION, records.Phase.READBACK, records.Phase.REPORT)
_CANDIDATES = r.AMENDMENT_REVIEW_PATHS


def _counts(n):
    overlap = max(0, min(n, 128) + min(n, 256) - n)
    return r.SubsetCounts(n, min(n, 256), overlap, overlap, sha256(str(n).encode()).digest())


_TARGETS = tuple(_counts(n) for n in identity.N_LADDER)


@lru_cache(maxsize=1)
def _workload():
    indices = r.synthetic_candidate_indices(0)
    selection = r.SyntheticCorpusSelection(_SEED, 0, r.subset_counts(_SEED, indices))
    return r.SyntheticWorkload(selection, _TARGETS[-1])


def _envelope(concurrency=1, **changes):
    value = op.OperatingEnvelope(
        concurrency=concurrency, max_decision_wall_ms=30_000, max_arm_wall_ms=420_000,
        max_case_wall_ms=840_000, max_job_wall_ms=900_000,
        max_launcher_wall_ms=43_200_000, shadow_timeout_ms=1_000,
        max_physical_inputs=50_000, worker_memory_cap_bytes=4_294_967_296,
        coordinator_memory_cap_bytes=4_294_967_296, memory_cap_bytes=4_294_967_296,
        archive_cap_bytes=17_179_869_184, monitor_interval_ms=1,
        max_payload_bytes=67_108_864, max_ipc_frame_bytes=65_536,
        aggregation_wall_ms=43_200_000, validation_wall_ms=43_200_000,
        publication_wall_ms=43_200_000, readback_wall_ms=43_200_000,
        report_wall_ms=43_200_000)
    return replace(value, **changes)


def _component(wall_ns=64, durable_bytes=64, **changes):
    value = r.ComponentMeasurement(wall_ns=wall_ns, durable_bytes=durable_bytes,
        max_unit_bytes=(durable_bytes + 63) // 64, completed_units=64)
    return replace(value, **changes)


def _oracle(wall_ns=64, durable_bytes=64, **changes):
    return replace(r.OracleMeasurement(wall_ns, durable_bytes, (durable_bytes + 63) // 64, 64), **changes)


def _containment(route, **changes):
    return replace(r.RouteContainment(route, 100, 200, 300, 1, 2, 3, 0, 1,
                                     10, 10, True, True, True, True, True), **changes)


def _measurement(concurrency=1, **changes):
    value = r.R0AConcurrencyMeasurement(
        concurrency=concurrency, plan=r.build_r0a_plan(_SEED),
        primary=_component(), k_control=_component(), oracle_primary=_oracle(),
        determinism=_component(), oracle_k_bind=r.WallRouteMeasurement(64, 64),
        oracle_d_repeat=_oracle(),
        references=tuple(r.ReferenceMeasurement(route, 64, 1, 64)
                         for route in ("K", "D", "O_K_SETUP", "O_D_SETUP")),
        containment=tuple(_containment(route) for route in r.CALIBRATION_ROUTES),
        wall_accounting=r.WallAccounting.CONSERVATIVE_STANDALONE,
        byte_accounting=r.ByteAccounting.NON_OVERLAPPING, envelope=_envelope(concurrency),
        max_worker_memory_bytes=100, max_coordinator_memory_bytes=200,
        max_combined_memory_bytes=300, max_decision_wall_ns=1, max_arm_wall_ns=2,
        max_case_wall_ns=3, max_shadow_wall_ns=1, max_physical_inputs=1,
        watchdogs_complete=True, resources_complete=True, cleanup_complete=True,
        progress_complete=True)
    return replace(value, **changes)


def _measurements(**changes):
    return tuple(_measurement(c, **changes) for c in (1, 2, 4))


def _r0b(measurements=None, **changes):
    measurements = _measurements() if measurements is None else measurements
    sizing = r.derive_r0b_sizing_plan(measurements)
    value = r.R0BMeasurement(
        protocol_seed=_SEED, n_max=10_000, complete_wall_ns=5,
        phases=tuple(r.PhaseMeasurement(phase, 1, 1, 1, 1, True, True)
                     for phase in _PHASES),
        bootstrap_replicates=10_000, bootstrap_n=10_000,
        shared_bootstrap_complete=True, compact_scalar_bootstrap=True,
        streaming_reconstruction=True, readback_complete=True, progress_bounded=True,
        synthetic_non_evidence=True,
        unit_bytes=sizing.unit_bytes,
        workload=_workload(),
        supporting=r.SupportingStreams(tuple(records.StreamDigest(name, "a" * 64, 1, 1)
            for name in ("operations", "resources", q.IDENTITY_STREAM)), True, True, True,
            True, True, True), realized_fixed_allowance_bytes=4,
        realized_max_unit_payload_bytes=max(v[3] for v in r.synthetic_unit_payloads(_workload(), sizing.unit_bytes)),
        max_combined_memory_bytes=300, containment_complete=True,
        archive_bytes=sum(count * getattr(sizing.unit_bytes, field.name)
                          for count, field in zip(_workload().unit_counts, fields(sizing.unit_bytes))) + 4)
    return replace(value, **changes)


def _select(measurements=None, r0b=None):
    measurements = _measurements() if measurements is None else measurements
    return r.select_operating_candidate(measurements, _r0b(measurements) if r0b is None else r0b, _TARGETS)


class RehearsalPlanTests(unittest.TestCase):
    def test_same_first_64_indices_for_all_three_concurrencies(self):
        plan = r.build_r0a_plan(_SEED)
        expected = identity.select_indices(identity.REHEARSAL_LABEL, _SEED,
            identity.REHEARSAL_LOW, identity.REHEARSAL_HIGH, 64,
            identity.E2_REHEARSAL_EXCLUSION_SET)
        self.assertEqual(plan.ordered_indices, expected)
        self.assertEqual(plan.schedule, ((1, expected), (2, expected), (4, expected)))
        self.assertEqual(len(set(expected)), 64)
        self.assertEqual(plan, r.build_r0a_plan(_SEED))
        self.assertEqual(repr(plan), repr(r.build_r0a_plan(_SEED)))

    def test_plan_rejects_wrong_count_order_replacement_and_seed(self):
        plan = r.build_r0a_plan(_SEED)
        for indices in (plan.ordered_indices[:-1], plan.ordered_indices[::-1],
                        plan.ordered_indices + (plan.ordered_indices[0],),
                        (plan.ordered_indices[1],) + plan.ordered_indices[1:]):
            with self.subTest(indices=indices[:2]), self.assertRaises(ValueError):
                replace(plan, ordered_indices=indices)
        for seed in (b"short", bytearray(_SEED), "x" * 32, None):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                r.build_r0a_plan(seed)

    def test_plan_and_measurements_are_frozen_and_slotted(self):
        for value in (r.build_r0a_plan(_SEED), _component(), _measurement(),
                      _r0b(), r.derive_r0b_sizing_plan(_measurements())):
            self.assertFalse(hasattr(value, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)

    def test_no_board_solver_coordinator_or_bootstrap_execution(self):
        with ExitStack() as stack:
            for owner, name in ((q.execution, "execute_primary"),
                                (q.execution, "execute_repeat"),
                                (q.execution, "execute_k_control"),
                                (op, "coordinate"), (q.analysis, "analyze_effectiveness")):
                stack.enter_context(patch.object(owner, name,
                    side_effect=AssertionError("I8 must remain pure: " + name)))
            stack.enter_context(patch("benchmark_board.generate_board",
                                     side_effect=AssertionError("No board generation")))
            self.assertEqual(_select().candidate.n, 10_000)


class MeasurementValidationTests(unittest.TestCase):
    def test_missing_duplicate_unknown_concurrency_and_wrong_container(self):
        values = _measurements()
        for invalid in (values[:-1], values + (values[0],), [*values], (),
                        (values[0], values[0], values[2])):
            with self.subTest(invalid=type(invalid)), self.assertRaises(ValueError):
                r.validate_r0a_measurements(invalid)
        for c in (0, 3, 8, True, 1.0):
            with self.subTest(concurrency=c), self.assertRaises(ValueError):
                replace(values[0], concurrency=c)

    def test_measurement_order_is_canonical_and_deterministic(self):
        values = _measurements()
        self.assertEqual(r.validate_r0a_measurements(values[::-1]), values)
        self.assertEqual(_select(values), _select(values[::-1]))

    def test_different_valid_rehearsal_streams_cannot_be_combined(self):
        values = _measurements()
        changed = replace(values[1], plan=r.build_r0a_plan(b"y" * 32))
        with self.assertRaises(ValueError):
            r.validate_r0a_measurements((values[0], changed, values[2]))

    def test_exact_positive_component_measurements_only(self):
        for field in ("wall_ns", "durable_bytes", "max_unit_bytes"):
            for invalid in (0, -1, True, 1.0, Fraction(1), float("nan"), float("inf")):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    replace(_component(), **{field: invalid})

    def test_component_completion_and_maximum_must_reconcile(self):
        for changes in ({"completed_units": True},
                        {"max_unit_bytes": 65}, {"durable_bytes": 129, "max_unit_bytes": 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(_component(), **changes)
        for name in ("primary", "k_control", "oracle_primary", "determinism"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                factory = _oracle if name == "oracle_primary" else _component
                _select(_measurements(**{name: replace(factory(), completed_units=63)}))

    def test_incomplete_operational_coverage_and_nonboolean_flags(self):
        for name in ("watchdogs_complete", "resources_complete", "cleanup_complete", "progress_complete"):
            for invalid in (False, 1, None):
                with self.subTest(name=name, invalid=invalid), self.assertRaises(ValueError):
                    _select(_measurements(**{name: invalid}))

    def test_ambiguous_wall_and_overlapping_bytes_are_rejected(self):
        for field, invalid in (("wall_accounting", "INCLUSIVE_OVERLAP"),
                               ("wall_accounting", "NON_OVERLAPPING"),
                               ("byte_accounting", "INCLUSIVE")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(_measurement(), **{field: invalid})
        with self.assertRaisesRegex(ValueError, "COMPLETE_STANDALONE_WALL_REQUIRED"):
            _measurement(wall_accounting=r.WallAccounting.NON_OVERLAPPING)

    def test_memory_and_wall_measurements_require_exact_integers(self):
        names = ("max_worker_memory_bytes", "max_coordinator_memory_bytes", "max_combined_memory_bytes",
                 "max_decision_wall_ns", "max_arm_wall_ns", "max_case_wall_ns", "max_shadow_wall_ns",
                 "max_physical_inputs", "watchdog_breaches", "resource_breaches")
        for name in names:
            for invalid in (-1, True, 1.0):
                with self.subTest(name=name, invalid=invalid), self.assertRaises(ValueError):
                    replace(_measurement(), **{name: invalid})

    def test_envelope_concurrency_and_memory_evidence_reconcile(self):
        for changes in ({"envelope": _envelope(2)}, {"max_combined_memory_bytes": 99}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(_measurement(), **changes)

    def test_frozen_provisional_caps_cannot_be_loosened(self):
        for field, value in (("max_decision_wall_ms", 30_001), ("max_arm_wall_ms", 420_001),
                             ("shadow_timeout_ms", 1_001), ("max_launcher_wall_ms", 43_200_001),
                             ("memory_cap_bytes", 4_294_967_297), ("archive_cap_bytes", 17_179_869_185),
                             ("fixed_report_receipt_allowance", 1)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                _envelope(**{field: value})

    def test_registered_operational_breaches_exclude_candidate(self):
        for name in ("watchdog_breaches", "resource_breaches"):
            values = _measurements(**{name: 1})
            with self.subTest(name=name):
                self.assertIsNone(_select(values).candidate)

    def test_observed_caps_must_fit_without_silent_loosening(self):
        for name, value in (("max_decision_wall_ns", 30_000_000_001),
                            ("max_arm_wall_ns", 420_000_000_001),
                            ("max_case_wall_ns", 840_000_000_001),
                            ("max_shadow_wall_ns", 1_000_000_001),
                            ("max_physical_inputs", 50_001)):
            with self.subTest(name=name):
                changes = {name: value}
                if name == "max_decision_wall_ns":
                    changes.update(max_arm_wall_ns=value, max_case_wall_ns=value)
                if name == "max_arm_wall_ns":
                    changes.update(max_case_wall_ns=value)
                self.assertIsNone(_select(_measurements(**changes)).candidate)

    def test_shadow_equality_matches_runner_strict_deadline_semantics(self):
        self.assertIsNotNone(_select(_measurements(max_shadow_wall_ns=1_000_000_000)).candidate)
        self.assertIsNone(_select(_measurements(max_shadow_wall_ns=1_000_000_001)).candidate)

    def test_i6_decision_arm_and_case_reach_cap_at_equality(self):
        for changes in (
            {"max_decision_wall_ns": 30_000_000_000, "max_arm_wall_ns": 30_000_000_000,
             "max_case_wall_ns": 30_000_000_000},
            {"max_arm_wall_ns": 420_000_000_000, "max_case_wall_ns": 420_000_000_000},
            {"max_case_wall_ns": 840_000_000_000},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(_select(_measurements(**changes)).candidate)


class PostprocessingTests(unittest.TestCase):
    def test_sizing_uses_component_maximum_over_every_concurrency_and_rounds_up(self):
        values = _measurements()
        values = (replace(values[0], primary=_component(durable_bytes=65)),
                  replace(values[1], k_control=_component(durable_bytes=129)),
                  replace(values[2], oracle_primary=_oracle(durable_bytes=193)))
        plan = r.derive_r0b_sizing_plan(values)
        self.assertEqual(plan.n_max, 10_000)
        self.assertEqual(_workload().unit_counts[:3], (10_000, 256, 128))
        self.assertEqual(plan.unit_bytes, r.ComponentSizes(3, 5, 6, 6, 2, 2))
        self.assertEqual(plan, r.derive_r0b_sizing_plan(values[::-1]))

    def test_r0b_is_complete_nmax_shared_bootstrap_facts_only(self):
        values = _measurements()
        measured = _r0b(values)
        self.assertEqual(r.validate_r0b_measurement(measured, values), measured)
        self.assertEqual(r.project_postprocess(measured), Fraction(10))
        self.assertEqual(tuple(value.phase for value in measured.phases), _PHASES)

    def test_missing_r0b_wrong_identity_and_nmax_are_rejected(self):
        with self.assertRaises(ValueError):
            r.select_operating_candidate(_measurements(), None, _TARGETS)
        for changes in ({"n_max": 9_999}, {"n_max": True}, {"bootstrap_n": 9_999},
                        {"bootstrap_replicates": 9_999}, {"protocol_seed": b"short"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                r.validate_r0b_measurement(replace(_r0b(), **changes), _measurements())
        with self.assertRaises(ValueError):
            r.validate_r0b_measurement(replace(_r0b(), protocol_seed=b"y" * 32), _measurements())

    def test_each_completion_complexity_and_progress_fact_is_required(self):
        for name in ("shared_bootstrap_complete", "compact_scalar_bootstrap", "streaming_reconstruction",
                     "readback_complete", "progress_bounded", "synthetic_non_evidence"):
            for invalid in (False, 1):
                with self.subTest(name=name, invalid=invalid), self.assertRaises(ValueError):
                    r.validate_r0b_measurement(replace(_r0b(), **{name: invalid}), _measurements())

    def test_every_postprocessing_phase_must_be_complete_and_uniquely_ordered(self):
        value = _r0b()
        for phases in (value.phases[:-1], value.phases[::-1], value.phases + (value.phases[0],),
                       (value.phases[0],) * 5):
            with self.subTest(phases=phases), self.assertRaises(ValueError):
                r.validate_r0b_measurement(replace(value, phases=phases), _measurements())
        for changes in ({"complete": False}, {"progress_bounded": False}, {"processed": 0},
                        {"processed": 2}, {"total": 0}, {"total": True},
                        {"wall_ns": 0}, {"wall_ns": True}, {"output_bytes": -1},
                        {"phase": records.Phase.EXECUTION}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                bad = replace(value.phases[0], **changes)
                r.validate_r0b_measurement(replace(value, phases=(bad,) + value.phases[1:]), _measurements())

    def test_complete_wall_cannot_omit_phase_work(self):
        for invalid in (4, 0, True, 5.0):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                r.validate_r0b_measurement(replace(_r0b(), complete_wall_ns=invalid), _measurements())
        self.assertEqual(r.project_postprocess(replace(_r0b(), complete_wall_ns=13)), Fraction(26))

    def test_r0b_payloads_below_safety_scaled_maximum_are_rejected(self):
        for name in ("primary", "k_control", "oracle_primary", "oracle_repeat", "determinism", "reference"):
            measured = _r0b()
            measured = replace(measured, unit_bytes=replace(measured.unit_bytes, **{name: 1}))
            with self.subTest(name=name), self.assertRaises(ValueError):
                r.validate_r0b_measurement(measured, _measurements())

    def test_postprocessing_output_bytes_are_exact_and_reconciled(self):
        for invalid in (-1, True, 5.0, 4):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                r.validate_r0b_measurement(replace(_r0b(), archive_bytes=invalid), _measurements())
        measured = _r0b()
        phase = replace(measured.phases[0], output_bytes=measured.archive_bytes + 1)
        with self.assertRaises(ValueError):
            r.validate_r0b_measurement(replace(measured, phases=(phase,) + measured.phases[1:]), _measurements())


class ExactAdmissionTests(unittest.TestCase):
    def test_component_scaling_uses_capped_subset_counts_exactly(self):
        measured = _measurement(primary=_component(3), k_control=_component(5),
                                oracle_primary=_oracle(7), determinism=_component(11))
        for n in (1, 63, 64, 127, 128, 129, 255, 256, 257, 1_000, 10_000):
            expected = Fraction(2 * (3*n + 5*min(n, 256) + 7*min(n, 128)
                                     + 11*min(n, 256) + 64*_counts(n).i_ok
                                     + 64*_counts(n).i_od), 64)
            with self.subTest(n=n):
                self.assertEqual(r.project_execution(n, measured, _counts(n)), expected)
                self.assertIs(type(r.project_execution(n, measured, _counts(n))), Fraction)

    def test_archive_uses_conservative_component_maxima_not_double_summing_runs(self):
        values = _measurements()
        values = (replace(values[0], primary=_component(durable_bytes=128)),
                  replace(values[1], k_control=_component(durable_bytes=192)),
                  replace(values[2], oracle_primary=_oracle(durable_bytes=256)))
        expected = Fraction(3, 2) * Fraction(128*1000 + 192*256 + 256*128 + 64*256 + 64*256, 64)
        self.assertEqual(r.project_archive(1_000, values, _counts(1000)), expected + 268_435_456)

    def test_largest_n_precedes_primary_throughput(self):
        values = tuple(_measurement(c, primary=_component(wall_ns=wall))
                       for c, wall in ((1, 64), (2, 32), (4, 16)))
        result = _select(values)
        self.assertEqual((result.candidate.n, result.candidate.envelope.concurrency), (10_000, 4))
        self.assertEqual(len(result.projections), 12)

    def test_equal_throughput_selects_lower_concurrency(self):
        self.assertEqual(_select().candidate.envelope.concurrency, 1)

    def test_higher_throughput_has_priority_over_lower_concurrency(self):
        values = (_measurement(1, primary=_component(65)), _measurement(2),
                  _measurement(4, primary=_component(63)))
        self.assertEqual(_select(values).candidate.envelope.concurrency, 4)

    def test_highest_n_wins_even_when_another_candidate_is_faster(self):
        values = (_measurement(1), _measurement(2, primary=_component(65)),
                  _measurement(4, primary=_component(32),
                               k_control=_component(5_399_999_999_750)))
        result = _select(values)
        self.assertEqual((result.candidate.n, result.candidate.envelope.concurrency), (10_000, 1))
        faster_floor = next(value for value in result.projections if (value.n, value.concurrency) == (1000, 4))
        self.assertTrue(faster_floor.admitted)
        self.assertGreater(faster_floor.primary_pairs_per_hour, result.candidate.projection.primary_pairs_per_hour)

    def test_only_n1000_admissible_selects_floor(self):
        values = _measurements(primary=_component(wall_ns=1_000_000_000_000))
        self.assertEqual(_select(values).candidate.n, 1_000)

    def test_no_floor_admission_returns_operational_not_ready(self):
        result = _select(_measurements(primary=_component(wall_ns=2_000_000_000_000)))
        self.assertIsNone(result.candidate)
        self.assertEqual(result.state.value, "ACTUAL_E2_NOT_READY")

    def test_launcher_exact_12h_and_one_ns_over(self):
        # N=1000, all four component walls 32 ns -> execution = 1640 ns.
        values = _measurements(primary=_component(32), k_control=_component(32),
                               oracle_primary=_oracle(32), determinism=_component(32))
        complete = (43_200_000_000_000 - 1_640) // 2
        result = _select(values, _r0b(values, complete_wall_ns=complete))
        self.assertEqual(result.candidate.n, 1_000)
        self.assertEqual(result.candidate.projection.launcher_wall_ns, Fraction(43_200_000_000_000))
        # Changes contribute +125 -120 -4 = exactly one projected nanosecond.
        changed = tuple(replace(value, primary=_component(36), k_control=_component(17),
                                oracle_primary=_oracle(31)) for value in values)
        over = r.project_execution(1_000, changed[0], _counts(1000)) + 2 * complete
        self.assertEqual(over, Fraction(43_200_000_000_001))
        self.assertIsNone(_select(changed, _r0b(changed, complete_wall_ns=complete)).candidate)

    def test_archive_exact_16gib_and_minimal_lattice_fraction_over(self):
        k_bytes = 2_818_571_846
        values = _measurements(primary=_component(durable_bytes=64),
            k_control=_component(durable_bytes=k_bytes), oracle_primary=_oracle(durable_bytes=128),
            determinism=_component(durable_bytes=64))
        self.assertEqual(r.project_archive(1_000, values, _counts(1000)), Fraction(17_179_869_184))
        self.assertEqual(_select(values).candidate.n, 1_000)
        changed = _measurements(primary=_component(durable_bytes=69),
            k_control=_component(durable_bytes=k_bytes-20), oracle_primary=_oracle(durable_bytes=129),
            determinism=_component(durable_bytes=64))
        self.assertEqual(r.project_archive(1_000, changed, _counts(1000)), Fraction(17_179_869_184) + Fraction(3, 16))
        self.assertIsNone(_select(changed).candidate)

    def test_corrected_integer_memory_boundaries_are_exact(self):
        admitted = _measurements(max_combined_memory_bytes=2_863_311_530)
        rejected = _measurements(max_combined_memory_bytes=2_863_311_531)
        self.assertEqual(r.project_memory(admitted[0]), Fraction(4_294_967_295))
        self.assertEqual(r.project_memory(rejected[0]), Fraction(8_589_934_593, 2))
        self.assertIsNotNone(_select(admitted).candidate)
        self.assertIsNone(_select(rejected).candidate)
        with self.assertRaises(ValueError):
            _measurement(max_combined_memory_bytes=Fraction(8_589_934_592, 3))

    def test_rounding_is_conservative_and_never_authorizes_an_overage(self):
        for value, expected in ((Fraction(0), 0), (Fraction(1), 1),
                                (Fraction(3, 2), 2), (Fraction(8_589_934_593, 2), 4_294_967_297)):
            self.assertEqual(r.ceil_fraction(value), expected)
        with self.assertRaises(ValueError):
            r.ceil_fraction(1.5)

    def test_invalid_projection_population_is_rejected(self):
        for invalid in (0, -1, True, 1.0, Fraction(1000)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                r.project_execution(invalid, _measurement(), _counts(1000))

    def test_exact_frozen_constants_and_candidate_ladder_cannot_drift(self):
        for name, invalid in (("N_LADDER", (1_000, 5_000, 10_000)),
            ("R0_A_CONCURRENCY_CANDIDATES", (1, 2, 3, 4)), ("R0_A_BOARD_COUNT", 63),
            ("EXECUTION_WALL_SAFETY_FACTOR", Fraction(1)),
            ("POSTPROCESS_WALL_SAFETY_FACTOR", Fraction(1)),
            ("ARCHIVE_BYTES_SAFETY_FACTOR", Fraction(1)), ("MEMORY_SAFETY_FACTOR", Fraction(1)),
            ("MAX_ACTUAL_E2_LAUNCHER_WALL_SECONDS", 43_201),
            ("MAX_COMBINED_MEMORY_BYTES", 4_294_967_297),
            ("MAX_ARCHIVE_BYTES", 17_179_869_185), ("FIXED_REPORT_RECEIPT_ALLOWANCE", 0)):
            values, measured = _measurements(), _r0b()
            with self.subTest(name=name), patch.object(identity, name, invalid), self.assertRaises(ValueError):
                r.select_operating_candidate(values, measured, _TARGETS)

    def test_same_value_float_constants_do_not_become_authority(self):
        values, measured = _measurements(), _r0b()
        for name, value in (("EXECUTION_WALL_SAFETY_FACTOR", 2.0),
                             ("ARCHIVE_BYTES_SAFETY_FACTOR", 1.5),
                             ("MAX_COMBINED_MEMORY_BYTES", 4294967296.0),
                             ("R0_A_CONCURRENCY_CANDIDATES", (True, 2, 4))):
            with self.subTest(name=name), patch.object(identity, name, value), self.assertRaises(ValueError):
                r.select_operating_candidate(values, measured, _TARGETS)

    def test_public_selection_revalidates_forged_frozen_measurement(self):
        values = _measurements()
        object.__setattr__(values[0], "max_combined_memory_bytes", True)
        with self.assertRaises(ValueError):
            r.select_operating_candidate(values, _r0b(), _TARGETS)

    def test_decision_rejects_wrong_priority_order_or_invented_admission(self):
        result = _select()
        smaller = next(value for value in result.projections if (value.n, value.concurrency) == (1000, 1))
        proposal = replace(result.candidate, n=1000, projection=smaller, target_counts=_counts(1000))
        with self.assertRaises(ValueError):
            replace(result, candidate=proposal)
        with self.assertRaises(ValueError):
            replace(result, projections=result.projections[::-1])
        with self.assertRaises(ValueError):
            replace(smaller, memory_bytes=Fraction(4_294_967_297), reasons=())
        with self.assertRaises(ValueError):
            replace(result, state=r.AdmissionState.ACTUAL_E2_NOT_READY, candidate=None)


class OutcomeAndAuthorizationTests(unittest.TestCase):
    def test_treatment_delta_counts_gates_and_mechanisms_cannot_be_inputs(self):
        values, measured = _measurements(), _r0b()
        baseline = r.select_operating_candidate(values, measured, _TARGETS)
        for name, effects in (("model_c_delta", (10**100, -(10**100))),
                              ("ww_wl_lw_ll", ((10000, 0, 0, 0), (0, 0, 10000, 0))),
                              ("g5_g8_g9", (("PASS",)*3, ("FAIL",)*3)),
                              ("mechanism_counts", (0, 10**100))):
            for effect in effects:
                with self.subTest(name=name, effect=effect), self.assertRaises(TypeError):
                    replace(values[0], **{name: effect})
            self.assertEqual(r.select_operating_candidate(values, measured, _TARGETS), baseline)

    def test_generic_payload_and_measurement_subclass_cannot_supply_outcomes(self):
        values = _measurements()
        forged = SimpleNamespace(**{field.name: getattr(values[0], field.name) for field in fields(values[0])},
                                 model_c_delta=10**100)
        with self.assertRaises(ValueError):
            r.select_operating_candidate((forged,) + values[1:], _r0b(), _TARGETS)
        with self.assertRaises(ValueError):
            r.select_operating_candidate({value.concurrency: value for value in values}, _r0b(), _TARGETS)

        class WithEffect(r.R0AConcurrencyMeasurement):
            pass

        subclass = WithEffect(**{field.name: getattr(values[0], field.name) for field in fields(values[0])})
        object.__setattr__(subclass, "effect", 10**100)
        with self.assertRaises(ValueError):
            r.select_operating_candidate((subclass,) + values[1:], _r0b(), _TARGETS)

    def test_proposal_has_no_freeze_publication_or_actual_e2_authority(self):
        result = _select()
        self.assertEqual(result.state.value, "CANDIDATE_PROPOSED")
        self.assertIs(result.candidate.frozen, False)
        self.assertIs(result.candidate.actual_e2_authorized, False)
        for name in ("frozen", "actual_e2_authorized"):
            with self.assertRaises(TypeError):
                replace(result.candidate, **{name: True})
        forbidden = ("RESEARCH_PASS", "RESEARCH_FAIL", "RESEARCH_DEFER", "R0_PASS", "ACTUAL_E2_READY", "E2_READY")
        for value in forbidden:
            self.assertNotIn(value, repr(result))
            with self.assertRaises(ValueError):
                type(result.state)(value)


class AmendmentReadinessTests(unittest.TestCase):
    def test_zero_primary_and_repeat_bytes_keep_complete_positive_walls(self):
        values = _measurements(oracle_primary=_oracle(17, 0), oracle_d_repeat=_oracle(19, 0))
        plan = r.derive_r0b_sizing_plan(values)
        self.assertEqual((plan.unit_bytes.oracle_primary, plan.unit_bytes.oracle_repeat), (0, 0))
        measured = _r0b(values)
        self.assertEqual(r.validate_r0b_measurement(measured, values), measured)
        rows = r.synthetic_unit_payloads(measured.workload, measured.unit_bytes)
        self.assertEqual(sum('oracle_primary' in v[2] for v in rows), 128)
        self.assertEqual(sum('oracle_repeat' in v[2] for v in rows), measured.workload.selection.counts.i_od)
        self.assertGreater(r.project_execution(1000, values[0], _counts(1000)), 0)
        with self.assertRaises(ValueError):
            _oracle(0, 0)

    def test_oracle_maxima_reference_routes_and_i_ok_wall_only(self):
        values = _measurements(oracle_primary=_oracle(11, 64), oracle_d_repeat=_oracle(13, 129))
        references = values[0].references[:-1] + (r.ReferenceMeasurement('O_D_SETUP', 193, 4, 64),)
        values = (replace(values[0], references=references),) + values[1:]
        sizes = r.derive_r0b_sizing_plan(values).unit_bytes
        self.assertEqual((sizes.oracle_primary, sizes.oracle_repeat, sizes.reference), (5, 5, 6))
        a = r.SubsetCounts(1000, 400, 7, 2, b'x'*32)
        b = replace(a, i_ok=9)
        self.assertEqual(r.project_archive(1000, values, a), r.project_archive(1000, values, b))
        self.assertEqual(r.project_execution(1000, values[0], b) - r.project_execution(1000, values[0], a), 14)
        expected = Fraction(3, 2) * Fraction(64*1000 + 64*256 + 129*(128+7) + 64*256 + 193*400, 64)
        self.assertEqual(r.project_archive(1000, values, a), expected + identity.FIXED_REPORT_RECEIPT_ALLOWANCE)

    def test_missing_route_and_each_containment_route_cannot_disappear(self):
        for route in r.CALIBRATION_ROUTES:
            values = _measurements()
            facts = tuple(v for v in values[0].containment if v.route != route)
            with self.subTest(route=route), self.assertRaises(ValueError):
                replace(values[0], containment=facts)
            facts = tuple(replace(v, max_combined_memory_bytes=301) if v.route == route else v
                          for v in values[0].containment)
            with self.subTest(route=route), self.assertRaisesRegex(ValueError, 'CONTAINMENT_MAXIMUM_OMITTED'):
                replace(values[0], containment=facts)
            facts = tuple(replace(v, cleanup_complete=False) if v.route == route else v
                          for v in values[0].containment)
            with self.subTest(route=route), self.assertRaisesRegex(ValueError, 'R0A_ROUTE_INCOMPLETE'):
                r.validate_r0a_measurements((replace(values[0], containment=facts),) + values[1:])
        self.assertEqual(_containment('P', max_decision_wall_ns=0).max_shadow_wall_ns, 0)
        with self.assertRaises(ValueError):
            replace(_measurement(), oracle_k_bind=None)
        with self.assertRaises(ValueError):
            r.validate_r0a_measurements(_measurements(oracle_k_bind=r.WallRouteMeasurement(1, 63)))

    def test_route_payload_launcher_caps_reject_candidate(self):
        for changes in ({'max_payload_bytes': 67_108_865}, {'launcher_wall_ns': 43_200_000_000_000},
                        {'launcher_wall_ns': 900_000_000_000}):
            values = _measurements()
            facts = tuple(replace(v, **changes) if v.route == 'O_D_SETUP' else v for v in values[0].containment)
            values = tuple(replace(v, containment=facts) for v in values)
            self.assertIsNone(_select(values).candidate)

    def test_synthetic_counts_reuse_exact_selector_without_boards(self):
        indices = tuple(range(r.SYNTHETIC_INDEX_LOW, r.SYNTHETIC_INDEX_LOW + 1000))
        with patch('benchmark_board.generate_board', side_effect=AssertionError('no board generation')):
            counts = r.target_counts(_SEED, 1000, indices)
        digest = identity.corpus_digest(_SEED, 1000, indices)
        k, o, d = (set(identity.select_subset_positions(label, _SEED, digest, 1000, cap))
                   for label, cap in ((identity.KCONTROL_LABEL, 256), (identity.ORACLE_B_LABEL, 128),
                                      (identity.DETERMINISM_LABEL, 256)))
        self.assertEqual((counts.u_kd, counts.i_od, counts.i_ok), (len(k|d), len(o&d), len(o&k)))
        r.validate_final_corpus_digest(counts, _SEED, indices)
        with self.assertRaises(ValueError):
            r.validate_final_corpus_digest(counts, _SEED, indices[::-1])
        for n in (999, True, 0):
            with self.assertRaises(ValueError):
                r.target_counts(_SEED, n, indices)

    def test_search_first_next_final_enumeration_and_domain_hygiene(self):
        for ordinal in (0, 1, r.SYNTHETIC_SEARCH_LIMIT-1):
            indices = r.synthetic_candidate_indices(ordinal)
            self.assertEqual(len(indices), 10000)
            self.assertEqual(indices[0], r.SYNTHETIC_INDEX_LOW + ordinal * 10000)
            self.assertEqual(indices[-1], indices[0] + 9999)
            for entry in identity.DOCUMENTED_EXPOSURE_REGISTRY:
                if entry.domain:
                    self.assertTrue(indices[-1] < entry.domain[0] or indices[0] >= entry.domain[1])
                self.assertTrue(set(indices).isdisjoint(entry.indices))
        for ordinal in (-1, True, r.SYNTHETIC_SEARCH_LIMIT):
            with self.assertRaises(ValueError):
                r.synthetic_candidate_indices(ordinal)
        for low in (identity.PRIMARY_LOW, identity.REHEARSAL_LOW, 2_010_000, 0):
            with self.assertRaises(ValueError):
                r._synthetic_domain(low, low+10000)

    def test_search_first_match_repeatability_and_tiny_finite_failure(self):
        with patch('benchmark_board.generate_board', side_effect=AssertionError('no board generation')):
            first = r.search_synthetic_corpus(256, 0, 0, protocol_seed=_SEED, attempt_limit=2)
            second = r.search_synthetic_corpus(256, 0, 0, protocol_seed=_SEED, attempt_limit=2)
            absent = r.search_synthetic_corpus(512, 128, 128, protocol_seed=_SEED, attempt_limit=2)
        self.assertEqual(first, second)
        self.assertEqual(first.ordinal, 0)
        self.assertGreaterEqual(first.counts.i_od, 1)
        self.assertGreaterEqual(first.counts.i_ok, 1)
        self.assertIsNone(absent)
        with self.assertRaises(ValueError):
            r.search_synthetic_corpus(256, 0, 0, protocol_seed=_SEED, attempt_limit=100001)

    def test_forged_counts_and_selection_are_revalidated(self):
        selected = _workload().selection
        with self.assertRaisesRegex(ValueError, 'SYNTHETIC_MEMBERSHIP_MISMATCH'):
            replace(selected, counts=replace(selected.counts, corpus_digest=b'0'*32))
        with self.assertRaises(ValueError):
            replace(selected.counts, u_kd=True)
        with self.assertRaises(ValueError):
            replace(_workload(), target=replace(_TARGETS[-1], i_ok=128))
        with self.assertRaises(ValueError):
            replace(_select(), realized_synthetic_counts=_counts(1000))

    def test_actual_topology_fits_composite_units_and_never_splits(self):
        workload = _workload()
        sizes = r.ComponentSizes(10, 13, 5, 7, 11, 3)
        payloads = r.synthetic_unit_payloads(workload, sizes)
        combinations = {v[2] for v in payloads}
        for expected in (('primary',), ('primary', 'reference'), ('primary', 'oracle_primary'),
                         ('primary', 'reference', 'oracle_primary'),
                         ('determinism',), ('determinism', 'oracle_repeat'), ('k_control',)):
            self.assertIn(expected, combinations)
        self.assertEqual(len(payloads), 10000+256+256)
        r.validate_payload_fit(workload, sizes, 18)
        with self.assertRaisesRegex(ValueError, 'R0B_COMPOSITE_PAYLOAD_CAP'):
            r.validate_payload_fit(workload, sizes, 17)
        for maximum in (1, 67_108_865):
            with self.assertRaisesRegex(ValueError, 'R0B_REALIZED_PAYLOAD_CAP'):
                r.validate_r0b_measurement(_r0b(realized_max_unit_payload_bytes=maximum), _measurements())
        with self.assertRaises(ValueError):
            r.validate_r0b_measurement(_r0b(unit_bytes=r.ComponentSizes(40_000_000, 2, 2, 2, 2, 30_000_000),
                archive_bytes=1_000_000_000_000), _measurements())

    def test_target_and_realized_counts_remain_separate_and_archive_uses_realized(self):
        measured = _r0b()
        realized = measured.workload.selection.counts
        self.assertGreater(realized.u_kd, measured.workload.target.u_kd)
        self.assertEqual(measured.workload.unit_counts, (10000, 256, 128, realized.i_od, 256, realized.u_kd))
        lower = measured.archive_bytes - (realized.u_kd - measured.workload.target.u_kd) * measured.unit_bytes.reference
        with self.assertRaisesRegex(ValueError, 'R0B_ARCHIVE_ACCOUNTING'):
            r.validate_r0b_measurement(replace(measured, archive_bytes=lower), _measurements())

    def test_fixed_allowance_boundary_and_supporting_structure(self):
        measured = _r0b()
        allowance = identity.FIXED_REPORT_RECEIPT_ALLOWANCE
        at = replace(measured, realized_fixed_allowance_bytes=allowance,
                     archive_bytes=measured.archive_bytes + allowance-4)
        r.validate_r0b_measurement(at, _measurements())
        with self.assertRaisesRegex(ValueError, 'R0B_FIXED_ALLOWANCE_CAP'):
            r.validate_r0b_measurement(replace(at, realized_fixed_allowance_bytes=allowance+1), _measurements())
        for field in ('receipts_complete', 'status_complete', 'work_plan_revalidated',
                      'qualification_complete', 'resources_complete', 'cleanup_complete'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(measured.supporting, **{field: False})
        with self.assertRaises(ValueError):
            replace(measured.supporting, streams=measured.supporting.streams[:-1])
        with self.assertRaisesRegex(ValueError, 'R0B_POSTPROCESS_WALL_CAP'):
            r.project_postprocess(replace(measured, complete_wall_ns=21_600_000_000_001))
        report = replace(measured.phases[-1], output_bytes=allowance+1)
        with self.assertRaisesRegex(ValueError, 'R0B_SUPPORTING_BYTE_ACCOUNTING'):
            r.validate_r0b_measurement(replace(measured, phases=measured.phases[:-1]+(report,),
                archive_bytes=allowance+100_000), _measurements())

    def test_postprocessing_memory_is_retained_in_proposal_caps(self):
        values = _measurements()
        measured = _r0b(values, max_combined_memory_bytes=1_000_000)
        proposed = _select(values, measured).candidate
        self.assertEqual(proposed.projection.memory_bytes, Fraction(1_500_000))
        self.assertEqual(proposed.envelope.memory_cap_bytes, 1_500_000)
        self.assertEqual(proposed.envelope.coordinator_memory_cap_bytes, 1_500_000)

    def test_auxiliary_zero_route_coverage_does_not_invent_scale_payload(self):
        # Selector is replaced only for this value-model structural-fixture test;
        # production selection/work-plan always rederive unchanged memberships.
        empty = r.SubsetCounts(10000, 256, 0, 0, b'x'*32)
        with patch.object(r, 'subset_counts', return_value=empty):
            selection = r.SyntheticCorpusSelection(_SEED, 0, empty)
            with self.assertRaisesRegex(ValueError, 'ORACLE_STRUCTURAL_COVERAGE_REQUIRED'):
                r.SyntheticWorkload(selection, _TARGETS[-1])
            value = r.SyntheticWorkload(selection, _TARGETS[-1], True, True)
            self.assertEqual(value.unit_counts[3], 0)
            self.assertEqual(value.unit_counts[5], 256)

    def test_work_plan_validation_calls_preserved_i7_boundary(self):
        with patch.object(q, '_plan', side_effect=ValueError('I7 guard retained')) as validate:
            with self.assertRaisesRegex(ValueError, 'I7 guard retained'):
                r.validate_synthetic_work_plan((), _workload())
        validate.assert_called_once_with(())


class SourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol_bytes = (r._ROOT / identity.PROTOCOL_PATH).read_bytes()
        cls.amendment_bytes = (r._ROOT / r.AMENDMENT_PATH).read_bytes()

    @contextmanager
    def source_capture(self, *, status=None, branch=b'main\n', drift=None, race=None):
        """Explicit historical amendment-review state, never today's worktree.

        The accepted guard owns AMENDMENT_REVIEW_PATHS and I8 ancestry. Later
        harness candidates belong to a separate source-capture responsibility.
        """
        state = ''.join(' M ' + p + '\n' for p in _CANDIDATES) if status is None else status
        calls, reads = {}, {}
        def git(*args, data=None):
            calls[args] = calls.get(args, 0) + 1
            if args[:2] == ('merge-base', '--is-ancestor'):
                return b''
            if args == ('branch', '--show-current'):
                return branch
            if args == ('status', '--porcelain=v1', '--untracked-files=all'):
                return (state + '?? unrelated.py\n' if race == 'status' and calls[args] > 1
                        else state).encode()
            if args in (('rev-parse', 'HEAD'), ('rev-parse', 'origin/main')):
                return (b'f'*40 if race == 'head' and calls[args] > 1 else b'e'*40) + b'\n'
            raise AssertionError(args)
        def source(path):
            if path == identity.PROTOCOL_PATH:
                return self.protocol_bytes
            if path == r.AMENDMENT_PATH:
                return self.amendment_bytes
            return b'mock committed ' + path.encode() + b'\n'
        def blobs(refs):
            result = []
            for ref in refs:
                commit, path = ref.split(':', 1)
                oid = identity.PROTOCOL_BLOB_ID if path == identity.PROTOCOL_PATH else '1'*40
                data = source(path)
                if drift == 'protected' and path == q._PROTECTED[0] and commit == 'e'*40:
                    oid = '2'*40
                result.append((oid, data))
            return tuple(result)
        def read(path):
            name = path.relative_to(r._ROOT).as_posix()
            reads[name] = reads.get(name, 0) + 1
            data = b'exact candidate ' + name.encode() if name in _CANDIDATES else source(name)
            if (drift == 'amendment' and name == r.AMENDMENT_PATH
                    or drift == 'working' and name == q._E2[0]
                    or race == name and reads[name] > 1):
                data += b'drift'
            return data
        with patch.object(r, '_git', side_effect=git), patch.object(r, '_blobs', side_effect=blobs), \
                patch.object(Path, 'read_bytes', new=read):
            yield

    def test_historical_review_fixture_binds_exact_candidates_and_amendment_without_git_mutation(self):
        with self.source_capture():
            value = r.capture_review_sources()
            self.assertEqual(value.status, ''.join(' M ' + p + '\n' for p in _CANDIDATES))
            self.assertEqual(value.provenance, r.AmendmentProvenance())
            self.assertEqual(tuple(v.path for v in value.candidates), tuple(sorted(_CANDIDATES)))
            for candidate in value.candidates:
                data = (r._ROOT / candidate.path).read_bytes()
                self.assertEqual((candidate.sha256, candidate.byte_length), (sha256(data).hexdigest(), len(data)))

    def test_later_harness_worktree_is_rejected_by_historical_guard(self):
        historical = ''.join(' M ' + p + '\n' for p in _CANDIDATES)
        harness_paths = ('experiments/program_k_e2_r0_harness.py',
                         'tests/test_program_k_e2_r0_harness.py')
        current_candidate = (' M experiments/program_k_e2_qualification.py\n'
                             ' M tests/test_program_k_e2_qualification.py\n'
                             + ''.join('?? ' + p + '\n' for p in harness_paths))
        states = (current_candidate,) + tuple(historical + status + ' ' + path + '\n'
            for path in harness_paths for status in ('??', ' M', 'M '))
        for status in states:
            with self.subTest(status=status), self.source_capture(status=status), \
                    self.assertRaisesRegex(ValueError, 'UNAUTHORIZED_WORKTREE_OR_INDEX_CHANGE'):
                r.capture_review_sources()

    def test_later_descendant_head_and_clean_committed_state_are_supported(self):
        with self.source_capture(status=''):
            value = r.capture_review_sources()
        self.assertEqual(value.baseline_head, 'e'*40)
        self.assertEqual(value.status, '')
        self.assertEqual(value.provenance.byte_length, 58052)

    def test_unrelated_staged_deleted_renamed_or_untracked_changes_rejected(self):
        for status in ('?? unrelated.py\n', ' M core_engine.py\n', 'M  '+_CANDIDATES[0]+'\n',
                       ' D '+_CANDIDATES[0]+'\n', 'R  old.py -> new.py\n', '?? '+_CANDIDATES[0]+'\n'):
            with self.subTest(status=status), self.source_capture(status=status), self.assertRaises(ValueError):
                r.capture_review_sources()

    def test_protected_and_frozen_authority_drift_rejected(self):
        for drift in ('protected', 'amendment', 'working'):
            with self.subTest(drift=drift), self.source_capture(drift=drift), self.assertRaises(ValueError):
                r.capture_review_sources()
        with self.source_capture(branch=b'other\n'), self.assertRaises(ValueError):
            r.capture_review_sources()

    def test_source_and_head_races_rejected(self):
        for race in ('head', 'status', r.AMENDMENT_PATH, *_CANDIDATES):
            with self.subTest(race=race), self.source_capture(race=race), self.assertRaises(ValueError):
                r.capture_review_sources()


_V2_FAMILIES = ('primary', 'k_control', 'oracle_primary', 'oracle_repeat', 'determinism', 'reference')
_V2_TEXT_FAMILIES = _V2_FAMILIES[:-1]
_V2_COUNTS = (10000, 256, 128, 1, 256, 256)  # Supplied synthetic policy fixture, not measured counts.


def _v2_sizes(*values):
    return r.ComponentSizes(*(values or (2, 3, 0, 0, 5, 7)))


def _v2_observation(family='primary', physical_excess=0, logical_excess=0):
    return r.evaluate_family_size(family, 2, 3, 2 + physical_excess, 3 + logical_excess)


def _v2_minimum_totals(targets, counts=_V2_COUNTS):
    return r.ComponentSizes(*(getattr(targets, name) * count for name, count in zip(_V2_FAMILIES, counts)))


def _v2_zero_budget_targets():
    # Scalar arithmetic only. The unit coefficient on oracle_repeat permits an
    # exact archive boundary without allocating a payload or constructing a run.
    return r.ComponentSizes(1, 1, 1, 16_911_433_728 - 10_896, 1, 1)


class DualSizingPolicyTests(unittest.TestCase):
    """Supplied synthetic policy maxima only; no fresh R0 measurement adapter."""

    def test_exact_family_order_and_immutable_dual_maxima_and_targets(self):
        maxima = r.DualComponentSizes(_v2_sizes(), _v2_sizes(11, 13, 0, 0, 17, 19))
        targets = r.derive_dual_targets(maxima)
        self.assertEqual(tuple(field.name for field in fields(r.ComponentSizes)), _V2_FAMILIES)
        self.assertEqual(tuple(field.name for field in fields(r.DualComponentSizes)), ('physical', 'logical'))
        for dual in (maxima, targets):
            self.assertFalse(hasattr(dual, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                dual.physical = _v2_sizes()
            with self.assertRaises(FrozenInstanceError):
                dual.logical.primary = 99

    def test_exact_ceil_three_halves_zero_small_and_large_integers(self):
        for value, expected in ((1, 2), (2, 3), (3, 5), (10_000_000_000_000_001, 15_000_000_000_000_002)):
            maxima = r.DualComponentSizes(_v2_sizes(value, value, 0, value, value, value),
                                          _v2_sizes(value, value, 0, value, value, value))
            with self.subTest(maximum=value):
                target = r.derive_dual_targets(maxima)
                wanted = r.ComponentSizes(expected, expected, 0, expected, expected, expected)
                self.assertEqual(target.physical, wanted)
                self.assertEqual(target.logical, wanted)
                self.assertTrue(all(type(getattr(target.physical, name)) is int for name in _V2_FAMILIES))

    def test_physical_and_logical_maxima_are_independent(self):
        maxima = r.DualComponentSizes(_v2_sizes(), _v2_sizes(11, 13, 0, 0, 17, 19))
        baseline = r.derive_dual_targets(maxima)
        changed_logical = r.derive_dual_targets(replace(maxima, logical=replace(maxima.logical, primary=101)))
        changed_physical = r.derive_dual_targets(replace(maxima, physical=replace(maxima.physical, primary=103)))
        self.assertEqual(changed_logical.physical, baseline.physical)
        self.assertNotEqual(changed_logical.logical, baseline.logical)
        self.assertEqual(changed_physical.logical, baseline.logical)
        self.assertNotEqual(changed_physical.physical, baseline.physical)

    def test_dual_model_rejects_impostors_subclasses_and_corrupt_integer_fields(self):
        class SizesSubclass(r.ComponentSizes):
            pass
        class DualSubclass(r.DualComponentSizes):
            pass
        class IntegerSubclass(int):
            pass
        good = _v2_sizes()
        impostors = (list(_V2_FAMILIES), {name: getattr(good, name) for name in _V2_FAMILIES},
                     SimpleNamespace(**{name: getattr(good, name) for name in _V2_FAMILIES}),
                     SizesSubclass(2, 3, 0, 0, 5, 7))
        for value in impostors:
            with self.subTest(input_type=type(value)), self.assertRaises(r.ReadinessError):
                r.DualComponentSizes(value, good)
        for value in (True, 1.0, IntegerSubclass(2), -1):
            corrupted = replace(good)
            object.__setattr__(corrupted, 'primary', value)
            with self.subTest(integer=value), self.assertRaises(r.ReadinessError):
                r.DualComponentSizes(good, corrupted)
        for value in (good, _measurement(), (good, good), DualSubclass(good, good)):
            with self.subTest(input_type=type(value)), self.assertRaises(r.ReadinessError):
                r.derive_dual_targets(value)

    def test_zero_row_oracle_bases_must_agree_and_uint64_overflow_fails_closed(self):
        for name in ('oracle_primary', 'oracle_repeat'):
            for physical, logical in ((0, 1), (1, 0)):
                with self.subTest(family=name, bases=(physical, logical)), self.assertRaises(r.ReadinessError):
                    r.DualComponentSizes(replace(_v2_sizes(), **{name: physical}),
                                         replace(_v2_sizes(), **{name: logical}))
        maximum = replace(_v2_sizes(), primary=identity.UINT64_MAX)
        with self.assertRaises(r.ReadinessError):
            r.derive_dual_targets(r.DualComponentSizes(maximum, maximum))

    def test_factor_and_text_window_cannot_be_configured(self):
        maxima = r.DualComponentSizes(_v2_sizes(), _v2_sizes())
        with self.assertRaises(TypeError):
            r.derive_dual_targets(maxima, safety_factor=Fraction(2))
        with self.assertRaises(TypeError):
            r.evaluate_family_size('primary', 2, 3, 2, 3, window=8192)
        self.assertEqual(tuple(inspect.signature(r.derive_dual_targets).parameters), ('maxima',))


class FamilySizingPolicyTests(unittest.TestCase):
    def test_each_text_family_accepts_inclusive_window_and_rejects_one_byte_over(self):
        for family in _V2_TEXT_FAMILIES:
            for extra in (0, 4096):
                with self.subTest(family=family, extra=extra):
                    value = r.evaluate_family_size(family, 10, 20, 10 + extra, 20)
                    self.assertTrue(value.eligible)
                    self.assertIsNone(value.rejection_reason)
                    self.assertTrue(value.text_window_applies)
                    self.assertEqual(value.text_window_upper_bound, 4106)
                    self.assertEqual((value.physical_margin, value.logical_margin), (extra, 0))
                    self.assertEqual((value.physical_excess, value.logical_excess), (extra, 0))
            rejected = r.evaluate_family_size(family, 10, 20, 4107, 20)
            self.assertFalse(rejected.eligible)
            self.assertEqual(rejected.rejection_reason, 'SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT')

    def test_each_text_family_rejects_independent_shortfalls_before_window_policy(self):
        cases = ((10, 19, 'SYNTHETIC_LOGICAL_MINIMUM_SHORTFALL'),
                 (9, 20, 'SYNTHETIC_PHYSICAL_MINIMUM_SHORTFALL'),
                 (9, 19, 'SYNTHETIC_BOTH_MINIMA_SHORTFALL'),
                 (9, 10**12, 'SYNTHETIC_PHYSICAL_MINIMUM_SHORTFALL'),
                 (10**12, 19, 'SYNTHETIC_LOGICAL_MINIMUM_SHORTFALL'),
                 (4107, 19, 'SYNTHETIC_LOGICAL_MINIMUM_SHORTFALL'))
        for family in _V2_TEXT_FAMILIES:
            for physical, logical, reason in cases:
                with self.subTest(family=family, actual=(physical, logical)):
                    value = r.evaluate_family_size(family, 10, 20, physical, logical)
                    self.assertFalse(value.eligible)
                    self.assertEqual(value.rejection_reason, reason)
                    self.assertEqual((value.physical_margin, value.logical_margin), (physical - 10, logical - 20))

    def test_reference_has_no_text_window_but_keeps_both_floors(self):
        value = r.evaluate_family_size('reference', 10, 20, 4107, 20)
        self.assertTrue(value.eligible)
        self.assertFalse(value.text_window_applies)
        self.assertIsNone(value.text_window_upper_bound)
        self.assertEqual(value.physical_excess, 4097)
        for physical, logical, reason in ((9, 20, 'SYNTHETIC_PHYSICAL_MINIMUM_SHORTFALL'),
                                          (10, 19, 'SYNTHETIC_LOGICAL_MINIMUM_SHORTFALL'),
                                          (9, 19, 'SYNTHETIC_BOTH_MINIMA_SHORTFALL')):
            self.assertEqual(r.evaluate_family_size('reference', 10, 20, physical, logical).rejection_reason, reason)

    def test_zero_row_oracle_accepts_only_exact_zero_without_window_or_filler(self):
        for family in ('oracle_primary', 'oracle_repeat'):
            value = r.evaluate_family_size(family, 0, 0, 0, 0)
            self.assertTrue(value.eligible)
            self.assertIsNone(value.rejection_reason)
            self.assertFalse(value.text_window_applies)
            self.assertIsNone(value.text_window_upper_bound)
            self.assertEqual((value.physical_excess, value.logical_excess), (0, 0))
            for actual in ((1, 0), (0, 1), (4096, 4096)):
                with self.subTest(family=family, actual=actual), self.assertRaises(r.ReadinessError):
                    r.evaluate_family_size(family, 0, 0, *actual)
            for targets in ((0, 1), (1, 0)):
                with self.assertRaises(r.ReadinessError):
                    r.evaluate_family_size(family, *targets, 0, 0)

    def test_family_facts_are_immutable_closed_and_exactly_typed(self):
        class IntegerSubclass(int):
            pass
        class StringSubclass(str):
            pass
        value = _v2_observation()
        self.assertFalse(hasattr(value, '__dict__'))
        with self.assertRaises(FrozenInstanceError):
            value.actual_physical_bytes = 0
        for family in ('P', 'oracle', 'PRIMARY', '', None, StringSubclass('primary')):
            with self.subTest(family=family), self.assertRaises(r.ReadinessError):
                r.evaluate_family_size(family, 2, 3, 2, 3)
        for index in range(4):
            for bad in (True, 2.0, IntegerSubclass(2), -1):
                args = [2, 3, 2, 3]
                args[index] = bad
                with self.subTest(index=index, bad=bad), self.assertRaises(r.ReadinessError):
                    r.evaluate_family_size('primary', *args)
        for family in ('primary', 'k_control', 'determinism', 'reference'):
            with self.assertRaises(r.ReadinessError):
                r.evaluate_family_size(family, 0, 0, 0, 0)


class DualCompositePolicyTests(unittest.TestCase):
    def test_physical_composite_exact_cap_and_cap_plus_one_preserve_v1_reason(self):
        workload = _workload()
        physical = _v2_sizes(10, 13, 5, 7, 11, 3)
        logical = _v2_sizes(1, 1, 1, 1, 1, 1)
        targets = r.DualComponentSizes(physical, logical)
        self.assertIsNone(r.validate_dual_payload_fit(workload, targets, 18))
        with self.assertRaisesRegex(r.ReadinessError, '^R0B_COMPOSITE_PAYLOAD_CAP$'):
            r.validate_dual_payload_fit(workload, targets, 17)
        for changed in (logical, replace(logical, primary=17)):
            with self.assertRaisesRegex(r.ReadinessError, '^R0B_COMPOSITE_PAYLOAD_CAP$'):
                r.validate_dual_payload_fit(workload, r.DualComponentSizes(physical, changed), 17)

    def test_logical_composite_exact_cap_and_one_over_are_independent(self):
        workload = _workload()
        physical = _v2_sizes(1, 1, 1, 1, 1, 1)
        logical = _v2_sizes(20, 21, 4, 6, 14, 2)
        self.assertIsNone(r.validate_dual_payload_fit(workload, r.DualComponentSizes(physical, logical), 26))
        with self.assertRaisesRegex(r.ReadinessError, '^LOGICAL_MINIMUM_COMPOSITE_CAP$'):
            r.validate_dual_payload_fit(workload, r.DualComponentSizes(physical, logical), 25)
        with self.assertRaisesRegex(r.ReadinessError, '^LOGICAL_MINIMUM_COMPOSITE_CAP$'):
            r.validate_dual_payload_fit(workload, r.DualComponentSizes(replace(physical, primary=10), logical), 25)

    def test_zero_oracle_contributes_no_bytes_and_topology_is_existing_ownership(self):
        workload = _workload()
        sizes = _v2_sizes(10, 13, 0, 0, 11, 3)
        targets = r.DualComponentSizes(sizes, sizes)
        payloads = r.synthetic_unit_payloads(workload, sizes)
        self.assertEqual(max(row[3] for row in payloads), 13)
        self.assertEqual(sum('oracle_primary' in row[2] for row in payloads), 128)
        self.assertEqual(sum('reference' in row[2] for row in payloads), workload.unit_counts[-1])
        self.assertIsNone(r.validate_dual_payload_fit(workload, targets, 13))
        for row in payloads:
            self.assertEqual(row[3], sum(getattr(sizes, name) for name in row[2]))
            if row[1] == 'K_CONTROL':
                self.assertEqual(row[2], ('k_control',))

    def test_composite_requires_closed_inputs_and_exact_positive_cap(self):
        targets = r.DualComponentSizes(_v2_sizes(), _v2_sizes())
        for bad in (True, 1.0, 0, -1):
            with self.assertRaises(r.ReadinessError):
                r.validate_dual_payload_fit(_workload(), targets, bad)
        with self.assertRaises(r.ReadinessError):
            r.validate_dual_payload_fit(_workload(), targets.physical, 100)
        with self.assertRaises(r.ReadinessError):
            r.validate_dual_payload_fit(SimpleNamespace(unit_counts=_V2_COUNTS), targets, 100)


class ArchiveAndProceduralBudgetTests(unittest.TestCase):
    def test_minimum_archive_support_zero_exact_cap_and_cap_plus_one(self):
        targets = _v2_sizes()
        minimum = sum(count * getattr(targets, name) for name, count in zip(_V2_FAMILIES, _V2_COUNTS))
        self.assertEqual(r.minimum_archive_preflight(targets, _V2_COUNTS, 0), minimum)
        support = identity.MAX_ARCHIVE_BYTES - minimum
        self.assertEqual(r.minimum_archive_preflight(targets, _V2_COUNTS, support), identity.MAX_ARCHIVE_BYTES)
        with self.assertRaises(r.ReadinessError):
            r.minimum_archive_preflight(targets, _V2_COUNTS, support + 1)
        for bad in (-1, True, 1.0):
            with self.assertRaises(r.ReadinessError):
                r.minimum_archive_preflight(targets, _V2_COUNTS, bad)

    def test_procedural_full_reservation_is_distinct_from_proven_support_lower_bound(self):
        targets = _v2_zero_budget_targets()
        self.assertEqual(identity.MAX_ARCHIVE_BYTES - identity.FIXED_REPORT_RECEIPT_ALLOWANCE, 16_911_433_728)
        self.assertEqual(r.minimum_archive_preflight(targets, _V2_COUNTS), 16_911_433_728)
        self.assertEqual(r.procedural_excess_capacity(targets, _V2_COUNTS), 0)
        too_large = replace(targets, oracle_repeat=targets.oracle_repeat + 1)
        self.assertEqual(r.minimum_archive_preflight(too_large, _V2_COUNTS), 16_911_433_729)
        with self.assertRaises(r.ReadinessError) as caught:
            r.procedural_excess_capacity(too_large, _V2_COUNTS)
        self.assertIn('RESERVATION', str(caught.exception))
        self.assertNotIn('R0B_', str(caught.exception))

    def test_logical_target_changes_never_change_archive_or_procedural_capacity(self):
        base = r.DualComponentSizes(_v2_sizes(), _v2_sizes())
        changed = replace(base, logical=_v2_sizes(10**9, 10**8, 0, 0, 10**7, 10**6))
        expected_minimum = 23_840
        for targets in (base, changed):
            self.assertEqual(r.minimum_archive_preflight(targets.physical, _V2_COUNTS), expected_minimum)
            self.assertEqual(r.procedural_excess_capacity(targets.physical, _V2_COUNTS), 16_911_433_728 - expected_minimum)
        for function in (r.minimum_archive_preflight, r.procedural_excess_capacity):
            with self.assertRaises(r.ReadinessError):
                function(base, _V2_COUNTS)

    def test_counts_are_exact_closed_order_and_preserve_workload_counts(self):
        counts = _workload().unit_counts
        self.assertEqual(counts[:3], (10000, 256, 128))
        self.assertEqual(counts[4], 256)
        self.assertEqual(r.minimum_archive_preflight(_v2_sizes(), counts),
                         sum(count * getattr(_v2_sizes(), name) for name, count in zip(_V2_FAMILIES, counts)))
        invalid = (list(_V2_COUNTS), _V2_COUNTS[:-1], _V2_COUNTS + (0,),
                   (9999,) + _V2_COUNTS[1:], (10000, 256, 128, True, 256, 256),
                   (10000, 256, 128, 129, 256, 256), (10000, 256, 128, 1, 256, 255),
                   (10000, 256, 128, 1, 256, 513))
        for value in invalid:
            with self.subTest(counts=value), self.assertRaises(r.ReadinessError):
                r.procedural_excess_capacity(_v2_sizes(), value)

    def test_archive_fixed_constants_cannot_be_enlarged_or_supplied_by_caller(self):
        targets = _v2_sizes()
        for function in (r.minimum_archive_preflight, r.procedural_excess_capacity):
            with self.assertRaises(TypeError):
                function(targets, _V2_COUNTS, archive_cap=identity.MAX_ARCHIVE_BYTES + 1)
            with self.assertRaises(TypeError):
                function(targets, _V2_COUNTS, fixed_allowance=0)
            for name, replacement in (('MAX_ARCHIVE_BYTES', identity.MAX_ARCHIVE_BYTES + 1),
                                      ('FIXED_REPORT_RECEIPT_ALLOWANCE', 0)):
                with self.subTest(function=function.__name__, name=name), patch.object(identity, name, replacement):
                    with self.assertRaises(r.ReadinessError):
                        function(targets, _V2_COUNTS)


class ProceduralLedgerPolicyTests(unittest.TestCase):
    def test_complete_unit_reserve_then_commit_is_immutable_and_not_implicitly_durable(self):
        original = r.ProceduralLedger(10)
        observations = (_v2_observation('primary', 3), _v2_observation('reference', 4))
        self.assertEqual(r.unit_physical_excess(observations), 7)
        self.assertEqual((original.committed_excess, original.reserved_excess, original.reservation_pending), (0, 0, False))
        reserved = r.reserve_procedural_unit(original, observations)
        self.assertEqual((reserved.committed_excess, reserved.reserved_excess, reserved.reservation_pending), (0, 7, True))
        committed = r.commit_procedural_unit(reserved)
        self.assertEqual((committed.committed_excess, committed.reserved_excess, committed.reservation_pending), (7, 0, False))
        self.assertEqual((original.committed_excess, original.reserved_excess), (0, 0))
        self.assertEqual((reserved.committed_excess, reserved.reserved_excess), (0, 7))
        for value in (original, reserved, committed):
            self.assertFalse(hasattr(value, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                value.capacity = 11

    def test_capacity_and_capacity_plus_one_use_exact_budget_boundary(self):
        state = r.commit_procedural_unit(r.reserve_procedural_unit(r.ProceduralLedger(10), (_v2_observation(physical_excess=7),)))
        at = r.reserve_procedural_unit(state, (_v2_observation(physical_excess=3),))
        self.assertEqual(r.commit_procedural_unit(at).committed_excess, 10)
        with self.assertRaisesRegex(r.ReadinessError, '^SYNTHETIC_PROCEDURAL_EXCESS_BUDGET$'):
            r.reserve_procedural_unit(state, (_v2_observation(physical_excess=4),))

    def test_complete_unit_sum_beyond_uint64_rejects_with_budget_reason(self):
        observations = (r.evaluate_family_size('primary', 1, 1, 3, 1),
                        r.evaluate_family_size('reference', 1, 1, (1 << 64) - 1, 1))
        self.assertTrue(all(value.eligible for value in observations))
        self.assertEqual(r.unit_physical_excess(observations), 1 << 64)
        with self.assertRaisesRegex(r.ReadinessError, '^SYNTHETIC_PROCEDURAL_EXCESS_BUDGET$'):
            r.reserve_procedural_unit(r.ProceduralLedger(0), observations)

    def test_zero_capacity_zero_delta_reservation_remains_pending_until_commit(self):
        state = r.ProceduralLedger(0)
        pending = r.reserve_procedural_unit(state, (_v2_observation(),))
        self.assertEqual(pending.reserved_excess, 0)
        self.assertTrue(pending.reservation_pending)
        with self.assertRaises(r.ReadinessError):
            r.reserve_procedural_unit(pending, (_v2_observation(),))
        final = r.commit_procedural_unit(pending)
        self.assertEqual(final, state)
        with self.assertRaises(r.ReadinessError):
            r.commit_procedural_unit(final)
        with self.assertRaisesRegex(r.ReadinessError, '^SYNTHETIC_PROCEDURAL_EXCESS_BUDGET$'):
            r.reserve_procedural_unit(state, (_v2_observation(physical_excess=1),))

    def test_only_eligible_physical_excess_counts_without_logical_or_unused_allowance_credit(self):
        logical_only = _v2_observation(logical_excess=10**12)
        self.assertEqual(r.unit_physical_excess((logical_only,)), 0)
        zero = r.reserve_procedural_unit(r.ProceduralLedger(0), (logical_only,))
        self.assertEqual(zero.reserved_excess, 0)
        with self.assertRaisesRegex(r.ReadinessError, '^SYNTHETIC_PROCEDURAL_EXCESS_BUDGET$'):
            r.reserve_procedural_unit(r.ProceduralLedger(0), (_v2_observation(physical_excess=1, logical_excess=10**12),))
        for unsupported in (-1, logical_only.logical_excess, [], (), (logical_only, logical_only)):
            with self.subTest(input_type=type(unsupported)), self.assertRaises(r.ReadinessError):
                r.reserve_procedural_unit(r.ProceduralLedger(10), unsupported)
        with self.assertRaises(TypeError):
            r.reserve_procedural_unit(r.ProceduralLedger(0), (logical_only,), logical_credit=logical_only.logical_excess)

    def test_rejected_family_cannot_offset_another_family_or_contribute_budget(self):
        shortfall = r.evaluate_family_size('primary', 10, 20, 9, 20)
        overshoot = r.evaluate_family_size('primary', 10, 20, 4107, 20)
        surplus = r.evaluate_family_size('reference', 10, 20, 10_000, 20)
        for rejected in (shortfall, overshoot):
            with self.assertRaises(r.ReadinessError):
                r.unit_physical_excess((rejected, surplus))
        class ObservationSubclass(r.FamilySizeEvaluation):
            pass
        with self.assertRaises(r.ReadinessError):
            r.unit_physical_excess((ObservationSubclass('primary', 2, 3, 2, 3),))

    def test_invalid_ledger_states_and_negative_or_mutable_reservations_are_rejected(self):
        for changes in ({'capacity': True}, {'capacity': -1}, {'committed_excess': -1},
                        {'reserved_excess': -1}, {'reserved_excess': 1}, {'reservation_pending': 1},
                        {'committed_excess': 11}):
            with self.subTest(changes=changes), self.assertRaises(r.ReadinessError):
                replace(r.ProceduralLedger(10), **changes)
        for value in (SimpleNamespace(capacity=10, committed_excess=0, reserved_excess=0), None):
            with self.assertRaises(r.ReadinessError):
                r.reserve_procedural_unit(value, (_v2_observation(),))
        for name in ('refund', 'release', 'retry', 'cancel'):
            self.assertFalse(hasattr(r.ProceduralLedger, name))
            self.assertFalse(hasattr(r, name + '_procedural_unit'))


class ProceduralReconciliationTests(unittest.TestCase):
    def test_exact_minima_reconcile_to_zero(self):
        targets = _v2_sizes()
        capacity = r.procedural_excess_capacity(targets, _V2_COUNTS)
        self.assertEqual(r.reconcile_procedural_excess(targets, _V2_COUNTS,
            _v2_minimum_totals(targets), r.ProceduralLedger(capacity)), 0)

    def test_exact_positive_sum_and_large_reference_excess_reconcile(self):
        targets = _v2_sizes()
        ledger = r.ProceduralLedger(r.procedural_excess_capacity(targets, _V2_COUNTS))
        observations = (_v2_observation('primary', 3), _v2_observation('reference', 5001))
        ledger = r.commit_procedural_unit(r.reserve_procedural_unit(ledger, observations))
        minima = _v2_minimum_totals(targets)
        totals = replace(minima, primary=minima.primary + 3, reference=minima.reference + 5001)
        self.assertEqual(r.reconcile_procedural_excess(targets, _V2_COUNTS, totals, ledger), 5004)
        with self.assertRaises(r.ReadinessError):
            r.reconcile_procedural_excess(targets, _V2_COUNTS, totals, replace(ledger, committed_excess=5003))

    def test_final_excess_over_budget_or_one_family_shortfall_cannot_be_offset(self):
        targets = _v2_zero_budget_targets()
        totals = _v2_minimum_totals(targets)
        with self.assertRaises(r.ReadinessError):
            r.reconcile_procedural_excess(targets, _V2_COUNTS, replace(totals, primary=totals.primary + 1), r.ProceduralLedger(0))
        targets = _v2_sizes()
        minimum = _v2_minimum_totals(targets)
        ledger = r.ProceduralLedger(r.procedural_excess_capacity(targets, _V2_COUNTS), committed_excess=1)
        with self.assertRaises(r.ReadinessError):
            r.reconcile_procedural_excess(targets, _V2_COUNTS,
                replace(minimum, primary=minimum.primary - 1, reference=minimum.reference + 2), ledger)

    def test_pending_zero_reservation_and_capacity_drift_prevent_final_reconciliation(self):
        targets = _v2_sizes()
        ledger = r.ProceduralLedger(r.procedural_excess_capacity(targets, _V2_COUNTS))
        pending = r.reserve_procedural_unit(ledger, (_v2_observation(),))
        with self.assertRaises(r.ReadinessError):
            r.reconcile_procedural_excess(targets, _V2_COUNTS, _v2_minimum_totals(targets), pending)
        with self.assertRaises(r.ReadinessError):
            r.reconcile_procedural_excess(targets, _V2_COUNTS, _v2_minimum_totals(targets), replace(ledger, capacity=ledger.capacity + 1))

    def test_zero_target_and_zero_count_families_cannot_gain_final_bytes(self):
        targets = _v2_sizes()
        minimum = _v2_minimum_totals(targets)
        ledger = r.ProceduralLedger(r.procedural_excess_capacity(targets, _V2_COUNTS), committed_excess=1)
        with self.assertRaises(r.ReadinessError):
            r.reconcile_procedural_excess(targets, _V2_COUNTS, replace(minimum, oracle_primary=1), ledger)
        counts = (10000, 256, 128, 0, 256, 256)
        targets = replace(targets, oracle_repeat=3)
        minimum = _v2_minimum_totals(targets, counts)
        ledger = r.ProceduralLedger(r.procedural_excess_capacity(targets, counts))
        self.assertEqual(r.reconcile_procedural_excess(targets, counts, minimum, ledger), 0)
        with self.assertRaises(r.ReadinessError):
            r.reconcile_procedural_excess(targets, counts, replace(minimum, oracle_repeat=1), replace(ledger, committed_excess=1))

    def test_logical_fixed_and_support_totals_are_not_reconciliation_inputs(self):
        targets = _v2_sizes()
        ledger = r.ProceduralLedger(r.procedural_excess_capacity(targets, _V2_COUNTS))
        for name in ('logical_totals', 'fixed_bytes', 'support_bytes'):
            with self.assertRaises(TypeError):
                r.reconcile_procedural_excess(targets, _V2_COUNTS, _v2_minimum_totals(targets), ledger, **{name: 10**12})


class V2PolicyIsolationTests(unittest.TestCase):
    def test_v1_sizing_measurement_and_component_contracts_are_unchanged(self):
        values = _measurements()
        values = (replace(values[0], primary=_component(durable_bytes=65)),
                  replace(values[1], k_control=_component(durable_bytes=129)),
                  replace(values[2], oracle_primary=_oracle(durable_bytes=193)))
        expected = r.R0BSizingPlan(_SEED, r.ComponentSizes(3, 5, 6, 6, 2, 2))
        self.assertEqual(r.derive_r0b_sizing_plan(values), expected)
        measured = _r0b(values)
        self.assertIs(r.validate_r0b_measurement(measured, values), measured)
        self.assertEqual(r.ComponentSizes(1, 1, 0, 0, 1, 1).oracle_repeat, 0)
        for name in ('primary', 'k_control', 'determinism', 'reference'):
            with self.assertRaises(r.ReadinessError):
                replace(_v2_sizes(), **{name: 0})
        r.derive_dual_targets(r.DualComponentSizes(_v2_sizes(), _v2_sizes(99, 98, 0, 0, 97, 96)))
        self.assertEqual(r.derive_r0b_sizing_plan(values), expected)

    def test_v1_closed_fact_registry_does_not_admit_new_policy_types(self):
        from experiments import program_k_e2_r0_evidence as evidence
        values = (r.DualComponentSizes(_v2_sizes(), _v2_sizes()), _v2_observation(), r.ProceduralLedger(0))
        for value in values:
            with self.subTest(value=type(value).__name__):
                self.assertNotIn(type(value).__name__, evidence._FACT_TYPES)
                with self.assertRaises(evidence.EvidenceError):
                    evidence.fact_node_v1(value)
                with self.assertRaises(evidence.EvidenceError):
                    evidence.fact_read_v1({'fact': type(value).__name__, 'fields': {}})
        legacy = _v2_sizes()
        node = evidence.fact_node_v1(legacy)
        self.assertEqual(node, {'fact': 'ComponentSizes', 'fields': dict(zip(_V2_FAMILIES, (2, 3, 0, 0, 5, 7)))})
        self.assertEqual(evidence.fact_read_v1(node), legacy)

    def test_pure_policy_functions_introduce_no_io_capture_or_operational_side_effects(self):
        workload = _workload()
        targets = r.DualComponentSizes(_v2_sizes(), _v2_sizes())
        with ExitStack() as stack:
            for owner, names in ((builtins, ('open',)), (Path, ('open', 'read_bytes', 'write_bytes', 'mkdir')),
                                 (r, ('capture_review_sources', 'search_synthetic_corpus', 'target_counts', '_git', '_blobs')),
                                 (op, ('coordinate', 'measure_r0_component', '_fresh_wb02_context')),
                                 (op.store, ('StreamWriter', 'FramedStreamWriter', 'scan_stream', 'scan_framed_stream')),
                                 (q.execution, ('execute_primary', 'execute_repeat', 'execute_k_control'))):
                for name in names:
                    stack.enter_context(patch.object(owner, name, side_effect=AssertionError('policy performed an effect')))
            derived = r.derive_dual_targets(targets)
            r.validate_dual_payload_fit(workload, derived, 100)
            r.minimum_archive_preflight(derived.physical, workload.unit_counts)
            capacity = r.procedural_excess_capacity(derived.physical, workload.unit_counts)
            observations = (_v2_observation(physical_excess=3),)
            state = r.commit_procedural_unit(r.reserve_procedural_unit(r.ProceduralLedger(capacity), observations))
            minimum = _v2_minimum_totals(derived.physical, workload.unit_counts)
            self.assertEqual(r.reconcile_procedural_excess(derived.physical, workload.unit_counts,
                replace(minimum, primary=minimum.primary + 3), state), 3)

    def test_readiness_import_remains_side_effect_free_and_new_policy_adds_no_imports(self):
        source = inspect.getsource(r)
        code = compile(source, r.__file__, 'exec')
        name = '_slice1e_readiness_import_probe'
        module = types.ModuleType(name)
        blocked = ((builtins, 'open'), (io, 'open'), (os, 'open'), (os, 'stat'), (os, 'lstat'),
                   (os, 'mkdir'), (os, 'makedirs'), (os, 'getenv'), (os, 'urandom'),
                   (Path, 'open'), (Path, 'resolve'), (Path, 'read_bytes'), (Path, 'write_bytes'),
                   (Path, 'mkdir'), (subprocess, 'run'), (subprocess, 'Popen'),
                   (op, 'coordinate'), (op, 'measure_r0_component'))
        with patch.dict(sys.modules, {name: module}), ExitStack() as stack:
            for owner, attribute in blocked:
                stack.enter_context(patch.object(owner, attribute, side_effect=AssertionError('import side effect')))
            exec(code, module.__dict__)
        imports = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imports, {'dataclasses', 'enum', 'fractions', 'hashlib', 'experiments'})


class R0ACalibrationSizingV2Tests(unittest.TestCase):
    """Supplied scalar calibration claims only; no collection or authentication."""

    PAIRS = (('primary', 'P'), ('k_control', 'K'), ('oracle_primary', 'O'),
             ('oracle_repeat', 'O_D_REPEAT'), ('determinism', 'D'),
             ('reference', 'K'), ('reference', 'D'),
             ('reference', 'O_K_SETUP'), ('reference', 'O_D_SETUP'))

    def summary(self, index=0, physical=11, logical=101):
        family, route = self.PAIRS[index]
        return r.R0AFamilySummaryV2(family, route, 64, 64, physical * 64, logical * 64,
                                    physical, logical)

    def claims(self):
        return tuple((c, tuple(self.summary(index, 10 + index + c, 100 + index + c)
                               for index in range(9))) for c in (1, 2, 4))

    def changed(self, claims, concurrency_index, summary_index, **changes):
        output = list(claims)
        c, summaries = output[concurrency_index]
        changed = list(summaries)
        changed[summary_index] = replace(changed[summary_index], **changes)
        output[concurrency_index] = (c, tuple(changed))
        return tuple(output)

    def test_exact_fields_pairs_and_immutable_summary(self):
        self.assertEqual(r.R0A_FAMILY_ROUTES_V2, self.PAIRS)
        self.assertEqual(tuple(field.name for field in fields(r.R0AFamilySummaryV2)), (
            'family', 'route', 'completed_units', 'record_count', 'physical_total_bytes',
            'logical_total_bytes', 'physical_max_unit_bytes', 'logical_max_unit_bytes'))
        summary = self.summary()
        self.assertFalse(hasattr(summary, '__dict__'))
        with self.assertRaises(FrozenInstanceError):
            summary.route = 'K'

    def test_exact_maxima_use_unit_maxima_not_totals_and_do_not_apply_floors(self):
        observed = r.derive_r0a_dual_maxima_v2(self.claims())
        self.assertEqual(observed.physical, r.ComponentSizes(14, 15, 17, 17, 18, 22))
        self.assertEqual(observed.logical, r.ComponentSizes(104, 105, 107, 107, 108, 112))

    def test_physical_and_logical_witnesses_may_be_different_concurrencies(self):
        claims = self.changed(self.claims(), 0, 0,
            physical_total_bytes=1001 * 64, physical_max_unit_bytes=1001)
        claims = self.changed(claims, 1, 0,
            logical_total_bytes=2003 * 64, logical_max_unit_bytes=2003)
        observed = r.derive_r0a_dual_maxima_v2(claims)
        self.assertEqual(observed.physical.primary, 1001)
        self.assertEqual(observed.logical.primary, 2003)
        self.assertEqual(observed.physical.reference, 22)
        self.assertEqual(observed.logical.reference, 112)

    def test_physical_only_and_logical_only_mutations_have_no_cross_credit(self):
        claims = self.claims()
        before = r.derive_r0a_dual_maxima_v2(claims)
        physical = r.derive_r0a_dual_maxima_v2(self.changed(claims, 0, 1,
            physical_total_bytes=1009 * 64, physical_max_unit_bytes=1009))
        logical = r.derive_r0a_dual_maxima_v2(self.changed(claims, 1, 4,
            logical_total_bytes=2011 * 64, logical_max_unit_bytes=2011))
        self.assertEqual(physical.logical, before.logical)
        self.assertEqual(physical.physical.k_control, 1009)
        self.assertEqual(logical.physical, before.physical)
        self.assertEqual(logical.logical.determinism, 2011)

    def test_both_oracle_routes_participate_with_independent_axis_witnesses(self):
        claims = self.changed(self.claims(), 0, 2,
            physical_total_bytes=1103 * 64, physical_max_unit_bytes=1103)
        claims = self.changed(claims, 1, 3,
            logical_total_bytes=2203 * 64, logical_max_unit_bytes=2203)
        observed = r.derive_r0a_dual_maxima_v2(claims)
        self.assertEqual((observed.physical.oracle_primary, observed.physical.oracle_repeat), (1103, 1103))
        self.assertEqual((observed.logical.oracle_primary, observed.logical.oracle_repeat), (2203, 2203))

    def test_each_reference_route_and_concurrency_can_supply_the_maximum(self):
        for c_index in range(3):
            for index in range(5, 9):
                with self.subTest(concurrency=c_index, route=self.PAIRS[index][1]):
                    claims = self.changed(self.claims(), c_index, index,
                        physical_total_bytes=1201 * 64, physical_max_unit_bytes=1201,
                        logical_total_bytes=2309 * 64, logical_max_unit_bytes=2309)
                    observed = r.derive_r0a_dual_maxima_v2(claims)
                    self.assertEqual(observed.physical.reference, 1201)
                    self.assertEqual(observed.logical.reference, 2309)

    def test_k_and_d_target_copies_do_not_supply_reference_maximum(self):
        claims = self.changed(self.claims(), 0, 1,
            physical_total_bytes=4001 * 64, physical_max_unit_bytes=4001)
        claims = self.changed(claims, 1, 4,
            logical_total_bytes=5003 * 64, logical_max_unit_bytes=5003)
        observed = r.derive_r0a_dual_maxima_v2(claims)
        self.assertEqual(observed.physical.reference, 22)
        self.assertEqual(observed.logical.reference, 112)

    def test_zero_oracle_is_complete_and_distinct_from_missing_summary(self):
        claims = self.claims()
        for c_index in range(3):
            for index in (2, 3):
                claims = self.changed(claims, c_index, index, record_count=0,
                    physical_total_bytes=0, logical_total_bytes=0,
                    physical_max_unit_bytes=0, logical_max_unit_bytes=0)
        observed = r.derive_r0a_dual_maxima_v2(claims)
        self.assertEqual(observed.physical.oracle_primary, 0)
        self.assertEqual(observed.logical.oracle_repeat, 0)
        self.assertEqual(claims[0][1][2].completed_units, 64)
        missing = ((1, claims[0][1][:2] + claims[0][1][3:]),) + claims[1:]
        with self.assertRaises(r.ReadinessError):
            r.derive_r0a_dual_maxima_v2(missing)

    def test_summary_rejects_wrong_pairs_partial_counts_and_inconsistent_zero(self):
        invalid = ({'family': 'reference', 'route': 'O'}, {'route': 'O_K_BIND'},
                   {'family': 'PRIMARY'}, {'completed_units': 63}, {'completed_units': 65},
                   {'record_count': 0}, {'physical_total_bytes': 0},
                   {'logical_max_unit_bytes': 0}, {'physical_max_unit_bytes': 1000},
                   {'physical_total_bytes': 11 * 64 + 1})
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(r.ReadinessError):
                replace(self.summary(), **changes)
        for index in (2, 3):
            with self.assertRaises(r.ReadinessError):
                replace(self.summary(index), record_count=0, physical_total_bytes=0,
                        physical_max_unit_bytes=0)
            with self.assertRaises(r.ReadinessError):
                replace(self.summary(index), physical_total_bytes=0, logical_total_bytes=0,
                        physical_max_unit_bytes=0, logical_max_unit_bytes=0)

    def test_summary_rejects_inexact_numeric_and_vocabulary_types(self):
        class IntegerSubclass(int):
            pass
        class StringSubclass(str):
            pass
        for name in ('completed_units', 'record_count', 'physical_total_bytes', 'logical_total_bytes',
                     'physical_max_unit_bytes', 'logical_max_unit_bytes'):
            for value in (True, -1, 1.0, IntegerSubclass(64), identity.UINT64_MAX + 1):
                with self.subTest(field=name, value=value), self.assertRaises(r.ReadinessError):
                    replace(self.summary(), **{name: value})
        for changes in ({'family': StringSubclass('primary')}, {'route': StringSubclass('P')},
                        {'family': 1}, {'route': None}):
            with self.subTest(changes=changes), self.assertRaises(r.ReadinessError):
                replace(self.summary(), **changes)

    def test_concurrency_shape_and_order_are_rejected_without_normalization(self):
        claims = self.claims()
        invalid = (list(claims), claims[::-1], claims[:2], claims + claims[:1],
                   ([1, claims[0][1]],) + claims[1:],
                   ((True, claims[0][1]),) + claims[1:],
                   ((1.0, claims[0][1]),) + claims[1:],
                   ((1, list(claims[0][1])),) + claims[1:],
                   ((1, claims[0][1][::-1]),) + claims[1:],
                   ((1, (claims[0][1][0],) * 9),) + claims[1:])
        for value in invalid:
            with self.subTest(input=value), self.assertRaises(r.ReadinessError):
                r.derive_r0a_dual_maxima_v2(value)

    def test_helper_revalidates_exact_summary_type_and_forged_fields(self):
        class SummarySubclass(r.R0AFamilySummaryV2):
            pass
        original = self.summary()
        subclass = SummarySubclass(original.family, original.route, original.completed_units,
            original.record_count, original.physical_total_bytes, original.logical_total_bytes,
            original.physical_max_unit_bytes, original.logical_max_unit_bytes)
        corrupt = replace(original)
        object.__setattr__(corrupt, 'physical_max_unit_bytes', True)
        for wrong in (subclass, corrupt, SimpleNamespace(family='primary', route='P'), original.__class__):
            claims = self.claims()
            claims = ((1, (wrong,) + claims[0][1][1:]),) + claims[1:]
            with self.subTest(value=wrong), self.assertRaises(r.ReadinessError):
                r.derive_r0a_dual_maxima_v2(claims)

    def test_exact_ceil_targets_remain_owned_by_unchanged_dual_derivation(self):
        maxima = r.derive_r0a_dual_maxima_v2(self.claims())
        targets = r.derive_dual_targets(maxima)
        self.assertEqual(targets.physical, r.ComponentSizes(21, 23, 26, 26, 27, 33))
        self.assertEqual(targets.logical, r.ComponentSizes(156, 158, 161, 161, 162, 168))

    def test_large_integer_maximum_stays_exact_and_target_overflow_fails_closed(self):
        huge = identity.UINT64_MAX
        claims = self.changed(self.claims(), 0, 0,
            physical_total_bytes=huge, physical_max_unit_bytes=huge)
        maxima = r.derive_r0a_dual_maxima_v2(claims)
        self.assertEqual(maxima.physical.primary, huge)
        with self.assertRaises(r.ReadinessError):
            r.derive_dual_targets(maxima)

    def test_v1_sizing_does_not_activate_new_vocabulary_or_derivation(self):
        historical = _measurements()
        expected = r.derive_r0b_sizing_plan(historical)
        with patch.object(r, 'derive_r0a_dual_maxima_v2', side_effect=AssertionError('V2 activated')), \
             patch.object(r, 'R0AFamilySummaryV2', side_effect=AssertionError('V2 activated')):
            self.assertEqual(r.derive_r0b_sizing_plan(historical), expected)
            self.assertEqual(r.validate_r0a_measurements(historical), historical)

    def test_derivation_has_no_capture_filesystem_measurement_or_persistence(self):
        claims = self.claims()
        expected = r.derive_r0a_dual_maxima_v2(claims)
        blocked = ((builtins, 'open'), (io, 'open'), (os, 'open'), (os, 'stat'), (os, 'lstat'),
                   (Path, 'open'), (Path, 'resolve'), (Path, 'read_bytes'), (Path, 'write_bytes'),
                   (Path, 'mkdir'), (subprocess, 'run'), (subprocess, 'Popen'),
                   (q, 'capture_sources'), (q, 'capture_sources_v2'), (r, 'capture_review_sources'),
                   (op, 'coordinate'), (op, 'measure_r0_component'))
        with ExitStack() as stack:
            for owner, attribute in blocked:
                stack.enter_context(patch.object(owner, attribute, side_effect=AssertionError('impure call')))
            self.assertEqual(r.derive_r0a_dual_maxima_v2(claims), expected)
            r.derive_dual_targets(expected)


if __name__ == '__main__':
    unittest.main()
