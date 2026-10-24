"""I8 pure admission qualification using tiny literal operational measurements.

The synthetic seeds select indices only. No boards, solver, real rehearsal,
Nmax payloads, bootstrap calculation, official evidence or envelope is produced.
"""

from contextlib import contextmanager, ExitStack
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
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
_CANDIDATES = ("experiments/program_k_e2_readiness.py",
               "tests/test_program_k_e2_readiness.py",
               "tests/test_program_k_e2_qualification.py")


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


def _measurement(concurrency=1, **changes):
    value = r.R0AConcurrencyMeasurement(
        concurrency=concurrency, plan=r.build_r0a_plan(_SEED),
        primary=_component(), k_control=_component(), oracle_b=_component(),
        determinism=_component(), wall_accounting=r.WallAccounting.NON_OVERLAPPING,
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
        archive_bytes=sum(count * getattr(sizing.unit_bytes, field.name)
                          for count, field in zip(sizing.unit_counts, fields(sizing.unit_bytes))))
    return replace(value, **changes)


def _select(measurements=None, r0b=None):
    measurements = _measurements() if measurements is None else measurements
    return r.select_operating_candidate(measurements, _r0b(measurements) if r0b is None else r0b)


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
        for name in ("primary", "k_control", "oracle_b", "determinism"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                _select(_measurements(**{name: replace(_component(), completed_units=63)}))

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
        self.assertEqual(r.project_execution(1_000, _measurement()),
            r.project_execution(1_000, _measurement(
                wall_accounting=r.WallAccounting.CONSERVATIVE_STANDALONE)))

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
                  replace(values[2], oracle_b=_component(durable_bytes=193)))
        plan = r.derive_r0b_sizing_plan(values)
        self.assertEqual(plan.n_max, 10_000)
        self.assertEqual(plan.unit_counts, (10_000, 256, 128, 256))
        self.assertEqual(plan.unit_bytes, r.ComponentSizes(3, 5, 6, 2))
        self.assertEqual(plan, r.derive_r0b_sizing_plan(values[::-1]))

    def test_r0b_is_complete_nmax_shared_bootstrap_facts_only(self):
        values = _measurements()
        measured = _r0b(values)
        self.assertEqual(r.validate_r0b_measurement(measured, values), measured)
        self.assertEqual(r.project_postprocess(measured), Fraction(10))
        self.assertEqual(tuple(value.phase for value in measured.phases), _PHASES)

    def test_missing_r0b_wrong_identity_and_nmax_are_rejected(self):
        with self.assertRaises(ValueError):
            r.select_operating_candidate(_measurements(), None)
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
        for name in ("primary", "k_control", "oracle_b", "determinism"):
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
                                oracle_b=_component(7), determinism=_component(11))
        for n in (1, 63, 64, 127, 128, 129, 255, 256, 257, 1_000, 10_000):
            expected = Fraction(2 * (3*n + 5*min(n, 256) + 7*min(n, 128)
                                     + 11*min(n, 256)), 64)
            with self.subTest(n=n):
                self.assertEqual(r.project_execution(n, measured), expected)
                self.assertIs(type(r.project_execution(n, measured)), Fraction)

    def test_archive_uses_conservative_component_maxima_not_double_summing_runs(self):
        values = _measurements()
        values = (replace(values[0], primary=_component(durable_bytes=128)),
                  replace(values[1], k_control=_component(durable_bytes=192)),
                  replace(values[2], oracle_b=_component(durable_bytes=256)))
        expected = Fraction(3, 2) * Fraction(128*1000 + 192*256 + 256*128 + 64*256, 64)
        self.assertEqual(r.project_archive(1_000, values), expected + 268_435_456)

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
                               oracle_b=_component(32), determinism=_component(32))
        complete = (43_200_000_000_000 - 1_640) // 2
        result = _select(values, _r0b(values, complete_wall_ns=complete))
        self.assertEqual(result.candidate.n, 1_000)
        self.assertEqual(result.candidate.projection.launcher_wall_ns, Fraction(43_200_000_000_000))
        # Changes contribute +125 -120 -4 = exactly one projected nanosecond.
        changed = tuple(replace(value, primary=_component(36), k_control=_component(17),
                                oracle_b=_component(31)) for value in values)
        over = r.project_execution(1_000, changed[0]) + 2 * complete
        self.assertEqual(over, Fraction(43_200_000_000_001))
        self.assertIsNone(_select(changed, _r0b(changed, complete_wall_ns=complete)).candidate)

    def test_archive_exact_16gib_and_minimal_lattice_fraction_over(self):
        k_bytes = 2_818_571_910
        values = _measurements(primary=_component(durable_bytes=64),
            k_control=_component(durable_bytes=k_bytes), oracle_b=_component(durable_bytes=128),
            determinism=_component(durable_bytes=64))
        self.assertEqual(r.project_archive(1_000, values), Fraction(17_179_869_184))
        self.assertEqual(_select(values).candidate.n, 1_000)
        changed = _measurements(primary=_component(durable_bytes=69),
            k_control=_component(durable_bytes=k_bytes-20), oracle_b=_component(durable_bytes=129),
            determinism=_component(durable_bytes=64))
        self.assertEqual(r.project_archive(1_000, changed), Fraction(17_179_869_184) + Fraction(3, 16))
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
                r.project_execution(invalid, _measurement())

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
                r.select_operating_candidate(values, measured)

    def test_same_value_float_constants_do_not_become_authority(self):
        values, measured = _measurements(), _r0b()
        for name, value in (("EXECUTION_WALL_SAFETY_FACTOR", 2.0),
                             ("ARCHIVE_BYTES_SAFETY_FACTOR", 1.5),
                             ("MAX_COMBINED_MEMORY_BYTES", 4294967296.0),
                             ("R0_A_CONCURRENCY_CANDIDATES", (True, 2, 4))):
            with self.subTest(name=name), patch.object(identity, name, value), self.assertRaises(ValueError):
                r.select_operating_candidate(values, measured)

    def test_public_selection_revalidates_forged_frozen_measurement(self):
        values = _measurements()
        object.__setattr__(values[0], "max_combined_memory_bytes", True)
        with self.assertRaises(ValueError):
            r.select_operating_candidate(values, _r0b())

    def test_decision_rejects_wrong_priority_order_or_invented_admission(self):
        result = _select()
        smaller = next(value for value in result.projections if (value.n, value.concurrency) == (1000, 1))
        proposal = replace(result.candidate, n=1000, projection=smaller)
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
        baseline = r.select_operating_candidate(values, measured)
        for name, effects in (("model_c_delta", (10**100, -(10**100))),
                              ("ww_wl_lw_ll", ((10000, 0, 0, 0), (0, 0, 10000, 0))),
                              ("g5_g8_g9", (("PASS",)*3, ("FAIL",)*3)),
                              ("mechanism_counts", (0, 10**100))):
            for effect in effects:
                with self.subTest(name=name, effect=effect), self.assertRaises(TypeError):
                    replace(values[0], **{name: effect})
            self.assertEqual(r.select_operating_candidate(values, measured), baseline)

    def test_generic_payload_and_measurement_subclass_cannot_supply_outcomes(self):
        values = _measurements()
        forged = SimpleNamespace(**{field.name: getattr(values[0], field.name) for field in fields(values[0])},
                                 model_c_delta=10**100)
        with self.assertRaises(ValueError):
            r.select_operating_candidate((forged,) + values[1:], _r0b())
        with self.assertRaises(ValueError):
            r.select_operating_candidate({value.concurrency: value for value in values}, _r0b())

        class WithEffect(r.R0AConcurrencyMeasurement):
            pass

        subclass = WithEffect(**{field.name: getattr(values[0], field.name) for field in fields(values[0])})
        object.__setattr__(subclass, "effect", 10**100)
        with self.assertRaises(ValueError):
            r.select_operating_candidate((subclass,) + values[1:], _r0b())

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


class SourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol_bytes = q._git("cat-file", "blob", identity.PROTOCOL_BLOB_ID)

    @contextmanager
    def source_capture(self, *, statuses=None, heads=None, origins=None, branches=None,
                       drift=None, candidate_race=None):
        """Explicit mocked Git/file observations; never manufacture a clean tree."""
        status = b"".join(("?? " + path + "\n").encode("ascii") for path in _CANDIDATES[:2])
        status += (" M " + _CANDIDATES[2] + "\n").encode("ascii")
        streams = {
            ("rev-parse", "HEAD"): (r.I7_BASELINE.encode("ascii") + b"\n",) if heads is None else heads,
            ("rev-parse", "origin/main"): (r.I7_BASELINE.encode("ascii") + b"\n",) if origins is None else origins,
            ("branch", "--show-current"): (b"main\n",) if branches is None else branches,
            ("status", "--porcelain=v1", "--untracked-files=all"): (status,) if statuses is None else statuses,
        }
        calls, reads = {}, {}

        def git(*args, data=None):
            self.assertIn(args, streams)
            position = calls.get(args, 0)
            calls[args] = position + 1
            values = streams[args]
            return values[min(position, len(values)-1)]

        def source(path):
            return self.protocol_bytes if path == identity.PROTOCOL_PATH else b"mock committed " + path.encode("ascii") + b"\n"

        def blobs(refs):
            result = []
            for ref in refs:
                commit, path = ref.split(":", 1)
                oid, data = "1" * 40, source(path)
                if path == identity.PROTOCOL_PATH:
                    oid = identity.PROTOCOL_BLOB_ID
                    if drift == "protocol_oid":
                        oid = "f" * 40
                    if drift == "protocol_bytes":
                        data += b"drift"
                elif path == q._PROTECTED[0] and commit == r.I7_BASELINE and drift == "protected":
                    oid = "2" * 40
                result.append((oid, data))
            return tuple(result)

        def read(path):
            name = path.relative_to(r._ROOT).as_posix()
            reads[name] = reads.get(name, 0) + 1
            if name in _CANDIDATES:
                data = b"exact candidate " + name.encode("ascii") + b"\r\n"
                return data + b"changed" if candidate_race == name and reads[name] > 1 else data
            data = source(name)
            if drift == "working" and name == q._E2[0]:
                data += b"hidden working drift"
            return data

        with patch.object(r, "_git", side_effect=git), patch.object(r, "_blobs", side_effect=blobs), \
                patch.object(Path, "read_bytes", new=read):
            yield SimpleNamespace(status=status.decode("ascii"), calls=calls, reads=reads)

    def test_live_review_binds_exact_three_candidate_byte_identities(self):
        # This production guard deliberately owns only the I7-based pre-commit
        # review. A later user commit must test its refusal, not make ordinary
        # source regression depend forever on today's untracked candidate state.
        head = r._git("rev-parse", "HEAD").strip().decode("ascii")
        if head != r.I7_BASELINE:
            with self.assertRaisesRegex(ValueError, "ACCEPTED_I7_BASELINE_REQUIRED"):
                r.capture_review_sources()
            return
        value = r.capture_review_sources()
        self.assertEqual(value.baseline_head, r.I7_BASELINE)
        self.assertEqual(value.protocol.sha256, identity.PROTOCOL_SHA256)
        self.assertEqual(tuple(item.path for item in value.candidates), tuple(sorted(_CANDIDATES)))
        for candidate in value.candidates:
            data = (r._ROOT / candidate.path).read_bytes()
            self.assertEqual(candidate.sha256, sha256(data).hexdigest())
            self.assertEqual(candidate.byte_length, len(data))
        self.assertIn("?? " + _CANDIDATES[0], value.status)
        self.assertIn("?? " + _CANDIDATES[1], value.status)
        self.assertIn(" M " + _CANDIDATES[2], value.status)
        protected_paths = {item.path for item in value.committed}
        self.assertTrue(set(q._PROTECTED + q._E2) <= protected_paths)

    def test_later_committed_head_exercises_live_guard_rejection_without_skip(self):
        with self.source_capture(heads=(b"f" * 40 + b"\n",)):
            self.test_live_review_binds_exact_three_candidate_byte_identities()

    def test_mocked_review_preserves_dirty_status_and_candidate_bytes(self):
        with self.source_capture() as fixture:
            value = r.capture_review_sources()
        self.assertEqual(value.status, fixture.status)
        for candidate in value.candidates:
            data = b"exact candidate " + candidate.path.encode("ascii") + b"\r\n"
            self.assertEqual(candidate.sha256, sha256(data).hexdigest())
            self.assertEqual(candidate.byte_length, len(data))

    def test_wrong_head_origin_and_branch_are_rejected(self):
        for changes in ({"heads": (b"f"*40 + b"\n",)},
                        {"origins": (b"f"*40 + b"\n",)}, {"branches": (b"other\n",)}):
            with self.subTest(changes=changes), self.source_capture(**changes), self.assertRaisesRegex(
                    ValueError, "ACCEPTED_I7_BASELINE_REQUIRED"):
                r.capture_review_sources()

    def test_any_fourth_dirty_untracked_or_staged_path_is_rejected(self):
        base = b"".join(("?? " + path + "\n").encode("ascii") for path in _CANDIDATES[:2])
        for extra in (b"?? unrelated.py\n", b" M core_engine.py\n", b"M  core_engine.py\n",
                      b"?? experiments/program_k_e2_future.py\n", b" M experiments/program_k_e2_qualification.py\n"):
            with self.subTest(extra=extra), self.source_capture(statuses=(base + extra,)), self.assertRaisesRegex(
                    ValueError, "UNAUTHORIZED_WORKTREE_OR_INDEX_CHANGE"):
                r.capture_review_sources()

    def test_staging_rename_delete_missing_candidates_or_duplicate_status_is_rejected(self):
        lines = ["?? " + path + "\n" for path in _CANDIDATES[:2]]
        for status in ("", lines[0], "".join(lines) + lines[0],
                       "A  " + _CANDIDATES[0] + "\n" + lines[1],
                       "".join(lines) + "M  " + _CANDIDATES[2] + "\n",
                       "".join(lines) + " D " + _CANDIDATES[2] + "\n",
                       "".join(lines) + "R  old.py -> " + _CANDIDATES[2] + "\n"):
            with self.subTest(status=status), self.source_capture(statuses=(status.encode("ascii"),)), \
                    self.assertRaisesRegex(ValueError, "UNAUTHORIZED_WORKTREE_OR_INDEX_CHANGE"):
                r.capture_review_sources()

    def test_protected_protocol_and_hidden_working_content_drift_is_rejected(self):
        for drift in ("protected", "protocol_oid", "protocol_bytes", "working"):
            with self.subTest(drift=drift), self.source_capture(drift=drift), self.assertRaises(ValueError):
                r.capture_review_sources()

    def test_head_origin_branch_and_status_races_are_rejected(self):
        head = r.I7_BASELINE.encode("ascii") + b"\n"
        with self.source_capture() as fixture:
            status = fixture.status.encode("ascii")
        for changes in ({"heads": (head, b"f"*40+b"\n")},
                        {"origins": (head, b"f"*40+b"\n")},
                        {"branches": (b"main\n", b"other\n")},
                        {"statuses": (status, status + b"?? unrelated.py\n")}):
            with self.subTest(changes=changes), self.source_capture(**changes), self.assertRaisesRegex(
                    ValueError, "SOURCE_CHANGED_DURING_CAPTURE"):
                r.capture_review_sources()

    def test_each_of_three_candidate_byte_races_is_rejected(self):
        for path in _CANDIDATES:
            with self.subTest(path=path), self.source_capture(candidate_race=path), self.assertRaisesRegex(
                    ValueError, "SOURCE_CHANGED_DURING_CAPTURE"):
                r.capture_review_sources()


if __name__ == "__main__":
    unittest.main()
