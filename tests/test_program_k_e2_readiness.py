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
        state = ''.join(' M ' + p + '\n' for p in _CANDIDATES) if status is None else status
        calls, reads = {}, {}
        def git(*args, data=None):
            calls[args] = calls.get(args, 0) + 1
            if args[:2] == ('merge-base', '--is-ancestor'):
                return b''
            if args == ('branch', '--show-current'):
                return branch
            if args == ('status', '--porcelain=v1', '--untracked-files=all'):
                return state.encode()
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

    def test_live_review_binds_exact_candidates_and_amendment_without_git_mutation(self):
        value = r.capture_review_sources()
        self.assertEqual(value.provenance, r.AmendmentProvenance())
        self.assertEqual(tuple(v.path for v in value.candidates), tuple(sorted(_CANDIDATES)))
        for candidate in value.candidates:
            data = (r._ROOT / candidate.path).read_bytes()
            self.assertEqual((candidate.sha256, candidate.byte_length), (sha256(data).hexdigest(), len(data)))

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
        for race in ('head', r.AMENDMENT_PATH, *_CANDIDATES):
            with self.subTest(race=race), self.source_capture(race=race), self.assertRaises(ValueError):
                r.capture_review_sources()


if __name__ == '__main__':
    unittest.main()
