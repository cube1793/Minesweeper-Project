"""I5 public audits over tiny literal runs and detached fault-injection fixtures.

No corpus, subset scheduling, E1 suite, persistence, or research verdict is run.
"""

import ast
import builtins
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from enum import Enum
from fractions import Fraction
import inspect
import io
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from core_engine import Action, GameStatus
from experiments import program_k_e2_audit as audit
from experiments import program_k_e2_game as game
from experiments import program_k_e2_records as records
from experiments import program_k_harness as harness
from experiments import program_k_oracles as oracles
from experiments import program_k_runner as runner
from stage3_physical import load_timing_table
from tests.test_program_k_e2_game import (
    _PublicPort, _arm, _board, _corrupt, _engine, _literal_setup_capture,
)


def _with_decision(raw, index, **changes):
    trace = raw.traces[index]
    decision = replace(trace.selection.evidence, **changes)
    changed = replace(trace, selection=replace(trace.selection, evidence=decision))
    return replace(raw, traces=raw.traces[:index] + (changed,) + raw.traces[index + 1:])


def _replace_item(projection, stream, index, **changes):
    items = getattr(projection, stream)
    item = replace(items[index], **changes)
    return _corrupt(projection, **{stream: items[:index] + (item,) + items[index + 1:]})


class AuditFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()
        cls.raw = runner.run_k_p0(_PublicPort(_engine()), table=cls.table, capture_effects=True)
        cls.projection = game.project_k_p0(
            cls.raw, _arm(records.Arm.K_P0, _board()), table=cls.table)
        cls.exact_raw, cls.exact_projection = _literal_setup_capture(cls.table)
        cls.guess_raw = runner.run_k_p0(
            _PublicPort(_engine(5, frozenset({(1, 0), (2, 0)}))),
            table=cls.table, capture_effects=True)
        cls.guess_projection = game.project_k_p0(
            cls.guess_raw, _arm(records.Arm.K_P0, _board(5, 2, 102)), table=cls.table)

    def run_audit(self, raw=None, projection=None, *, enabled=True, raw_arm=None,
                  oracle_timing_observer=None):
        raw = self.raw if raw is None else raw
        projection = self.projection if projection is None else projection
        return audit.audit_k_p0(raw, projection,
                               raw_arm=projection.arm if raw_arm is None else raw_arm,
                               table=self.table, oracle_b_enabled=enabled,
                               oracle_timing_observer=oracle_timing_observer)

    def assert_status(self, value, expected):
        self.assertIs(value.status, getattr(audit.AuditStatus, expected))


class CertificateAuditTests(AuditFixtures):
    def test_canonical_aliases_and_every_certificate_child_roundtrip(self):
        self.assertIs(audit.AuditStatus, records.AuditStatus)
        self.assertIs(audit.CertificateAuditRecord, records.CertificateAuditRecord)
        for raw, projection in ((self.raw, self.projection),
                                (self.exact_raw, self.exact_projection)):
            result = self.run_audit(raw, projection)
            self.assertTrue(result.certificate_audits)
            for child in result.certificate_audits:
                with self.subTest(source=child.acquisition.source):
                    self.assertIs(type(child), records.CertificateAuditRecord)
                    encoded = records.encode(child)
                    decoded = records.decode(encoded)
                    self.assertIs(type(decoded), records.CertificateAuditRecord)
                    self.assertEqual(decoded, child)
                    self.assertEqual(records.encode(decoded), encoded)
                    self.assertTrue(decoded.certificate_premises)
                    self.assertTrue(decoded.verifier_facts)

    def test_every_local_and_exact_acquisition_has_one_detached_audit(self):
        sources = set()
        for raw, projection in ((self.raw, self.projection),
                                (self.exact_raw, self.exact_projection)):
            with self.subTest(acquisitions=len(projection.acquisitions)):
                result = self.run_audit(raw, projection)
                self.assert_status(result, "PASS")
                self.assertEqual(tuple(item.acquisition for item in result.certificate_audits),
                                 projection.acquisitions)
                sources.update(item.acquisition.source for item in result.certificate_audits)
        self.assertEqual(sources, {records.AcquisitionSource.LOCAL,
                                  records.AcquisitionSource.EXACT_GLOBAL})

    def test_low_level_verifier_binding_and_chronological_history_are_exact(self):
        accepted = harness.audit_acquisition
        retained = []
        def capture(certificate, **kwargs):
            result = accepted(certificate, **kwargs)
            retained.append(result)
            return result
        with patch.object(harness, "audit_acquisition", side_effect=capture):
            result = self.run_audit(self.exact_raw, self.exact_projection)
        self.assertEqual(len(retained), len(self.exact_projection.acquisitions))
        history = ()
        for actual, original in zip(result.certificate_audits, retained):
            self.assertEqual(original.prior_certificates, history)
            self.assertEqual(original.external_flags, ())
            self.assertEqual(actual.action_ordinal, original.boundary)
            self.assertEqual(actual.acquisition.certificate_sha256,
                             harness.content_digest(original.certificate))
            self.assertEqual(actual.acquisition.certificate_ref,
                             "sha256:" + actual.acquisition.certificate_sha256)
            self.assertEqual(actual.prior_certificate_sha256s,
                             tuple(harness.content_digest(item) for item in history))
            self.assertEqual(actual.verifier_status, original.status)
            self.assertEqual(actual.detail, original.detail)
            self.assertEqual(frozenset(actual.owned_m_before), original.owned_M_before)
            self.assertEqual(frozenset(actual.owned_m_after), original.owned_M_after)
            self.assert_status(actual, "PASS")
            history += (original.certificate,)

    def test_verifier_failure_stays_failure_and_cannot_authorize_phase_d(self):
        accepted = harness.audit_acquisition
        def failed(*args, **kwargs):
            return replace(accepted(*args, **kwargs), status="FAIL", detail="PUBLIC_PROOF_REJECTED")
        with patch.object(harness, "audit_acquisition", side_effect=failed):
            result = self.run_audit()
        self.assert_status(result, "FAIL")
        self.assertTrue(result.failure_reasons)
        self.assertTrue(all(item.status is audit.AuditStatus.FAIL for item in result.certificate_audits))
        for child in result.certificate_audits:
            self.assertIs(type(child), records.CertificateAuditRecord)
            self.assertEqual(records.decode(records.encode(child)), child)
        self.assertFalse(any(item.status is audit.AuditStatus.PASS for item in result.oracle_b_audits))

    def test_failed_exact_certificate_does_not_qualify_phase_e_or_history(self):
        accepted = harness.audit_acquisition
        calls = []
        def failed_first(*args, **kwargs):
            calls.append(kwargs)
            result = accepted(*args, **kwargs)
            return replace(result, status="FAIL", detail="FIRST_REJECTED") if len(calls) == 1 else result
        with patch.object(harness, "audit_acquisition", side_effect=failed_first):
            result = self.run_audit(self.exact_raw, self.exact_projection)
        self.assert_status(result, "FAIL")
        self.assertEqual(len(result.certificate_audits), len(self.exact_projection.acquisitions))
        for child in result.certificate_audits:
            self.assertIs(type(child), records.CertificateAuditRecord)
            self.assertEqual(records.decode(records.encode(child)), child)
        self.assertEqual(calls[1]["prior_certificates"], ())
        self.assertTrue(any(item.phase == "D" and item.status is audit.AuditStatus.PASS
                            for item in result.oracle_b_audits))
        self.assertFalse(any(item.phase == "E" and item.status is audit.AuditStatus.PASS
                             for item in result.oracle_b_audits))

    def test_bad_verifier_certificate_boundary_history_owned_m_or_flags_is_error(self):
        accepted = harness.audit_acquisition
        changes = (
            {"boundary": 999}, {"certificate": None}, {"prior_certificates": (None,)},
            {"external_flags": (None,)}, {"owned_M_before": frozenset({(3, 0)})},
            {"owned_M_after": frozenset()}, {"status": "MADE_UP"}, {"detail": None},
        )
        for change in changes:
            with self.subTest(change=change):
                def incorrect(*args, **kwargs):
                    return replace(accepted(*args, **kwargs), **change)
                with patch.object(harness, "audit_acquisition", side_effect=incorrect):
                    with self.assertRaises(audit.E2AuditError):
                        self.run_audit()

    def test_forged_pass_with_wrong_local_verifier_facts_is_rejected(self):
        accepted = harness.audit_acquisition
        for changes in ({"target": (3, 0)}, {"clue": (3, 0)}, {"clue_value": 8},
                        {"clue_value": True}, {"physical_flags": set()},
                        {"logical_mines": set()}, {"unresolved": set()},
                        {"antecedents": []}, {"residual": True}):
            with self.subTest(changes=changes):
                def forged(*args, **kwargs):
                    original = accepted(*args, **kwargs)
                    return replace(original, certificate_check=replace(original.certificate_check, **changes))
                with patch.object(harness, "audit_acquisition", side_effect=forged):
                    with self.assertRaises(audit.E2AuditError):
                        self.run_audit()

    def test_forged_pass_with_wrong_exact_verifier_facts_is_rejected(self):
        accepted = harness.audit_acquisition
        for changes in ({"total_worlds": 999}, {"mine_worlds": 0},
                        {"total_worlds": True}, {"mine_worlds": True},
                        {"antecedents": []}, {"oracle_a_variable_count": True}):
            with self.subTest(changes=changes):
                def forged(*args, **kwargs):
                    original = accepted(*args, **kwargs)
                    return replace(original, certificate_check=replace(original.certificate_check, **changes))
                with patch.object(harness, "audit_acquisition", side_effect=forged):
                    with self.assertRaises(audit.E2AuditError):
                        self.run_audit(self.exact_raw, self.exact_projection)

    def test_forged_board_pass_cannot_drop_failed_or_incomplete_children(self):
        accepted = harness.audit_acquisition
        def failed(*args, **kwargs):
            return replace(accepted(*args, **kwargs), status="FAIL", detail="REJECTED")
        with patch.object(harness, "audit_acquisition", side_effect=failed):
            result = self.run_audit()
        with self.assertRaises(audit.E2AuditError):
            replace(result, status=audit.AuditStatus.PASS, failure_reasons=(), incomplete_reasons=())
        incomplete_child = next(item for item in result.oracle_b_audits
                                if item.status is audit.AuditStatus.INCOMPLETE)
        passing = self.run_audit()
        with self.assertRaises(audit.E2AuditError):
            replace(passing, oracle_b_audits=(incomplete_child,))

    def test_missing_duplicate_or_extra_raw_certificate_is_not_silently_dropped(self):
        trace = self.raw.traces[1]
        local = trace.selection.evidence.local
        certificate = local.certificates[0]
        for certificates in ((), (certificate, certificate),
                             (certificate, replace(certificate, target=(3, 0)))):
            with self.subTest(certificates=len(certificates)):
                raw = _with_decision(self.raw, 1, local=replace(local, certificates=certificates))
                with self.assertRaises(audit.E2AuditError):
                    self.run_audit(raw)

    def test_acquisition_digest_ref_source_target_and_boundary_bind_exactly(self):
        item = self.projection.acquisitions[0]
        changes = ({"certificate_sha256": "0" * 64, "certificate_ref": "sha256:" + "0" * 64},
                   {"certificate_ref": "sha256:" + "1" * 64},
                   {"source": records.AcquisitionSource.EXACT_GLOBAL},
                   {"cell": (3, 0)}, {"action_ordinal": item.action_ordinal + 1},
                   {"decision_ordinal": item.decision_ordinal + 1})
        for change in changes:
            with self.subTest(change=change):
                projection = _corrupt(self.projection, acquisitions=(_corrupt(item, **change),))
                with self.assertRaises(audit.E2AuditError):
                    self.run_audit(projection=projection)

    def test_raw_identity_arm_board_and_transport_binding_is_explicit(self):
        for arm in (replace(self.projection.arm, arm=records.Arm.CONTROL),
                    replace(self.projection.arm, board=replace(self.projection.arm.board, fingerprint="other")),
                    replace(self.projection.arm, run_id="another-run")):
            with self.subTest(arm=arm):
                with self.assertRaises(audit.E2AuditError):
                    self.run_audit(raw_arm=arm)

    def test_raw_input_count_model_cost_selection_m_and_final_m_are_bound(self):
        raw_faults = (
            replace(self.raw, traces=self.raw.traces[:-1]),
            replace(self.raw, final_M=frozenset()),
            replace(self.raw, traces=(replace(self.raw.traces[0], modeled_action_us=1),) + self.raw.traces[1:]),
            replace(self.raw, traces=self.raw.traces[:1] +
                    (replace(self.raw.traces[1], category="WRONG"),) + self.raw.traces[2:]),
        )
        for raw in raw_faults:
            with self.subTest(raw=raw):
                with self.assertRaises(audit.E2AuditError):
                    self.run_audit(raw)


class OracleBAuditTests(AuditFixtures):
    def test_disabled_subset_makes_no_oracle_b_adapter_call(self):
        # The independent public certificate verifier remains enabled. Use the
        # local-only fixture so its low-level proof does not need exact arithmetic.
        with patch.object(oracles, "materialized_exact_reference",
                          side_effect=AssertionError("subset-disabled Oracle-B called")):
            result = self.run_audit(enabled=False)
        self.assertFalse(result.oracle_b_selected)
        self.assertEqual(result.oracle_b_audits, ())
        self.assertEqual(len(result.certificate_audits), len(self.projection.acquisitions))

    def test_enabled_initial_only_board_has_empty_applicable_audit(self):
        raw = runner.run_k_p0(_PublicPort(_engine(2)), table=self.table, capture_effects=True)
        projection = game.project_k_p0(raw, _arm(records.Arm.K_P0, _board(2)), table=self.table)
        with patch.object(oracles, "materialized_exact_reference") as reference:
            result = self.run_audit(raw, projection)
        reference.assert_not_called()
        self.assertTrue(result.oracle_b_selected)
        self.assertEqual(result.oracle_b_audits, ())
        self.assert_status(result, "PASS")

    def test_every_reached_phase_retained_and_differentially_matches_reference(self):
        result = self.run_audit(self.exact_raw, self.exact_projection)
        expected_phases = tuple((trace.input_index, phase)
                                for trace in self.exact_raw.traces if trace.selection is not None
                                for phase, value in (("D", trace.selection.evidence.phase_d),
                                                     ("E", trace.selection.evidence.phase_e))
                                if value is not None)
        self.assertEqual(tuple((item.action_ordinal, item.phase) for item in result.oracle_b_audits),
                         expected_phases)
        self.assertEqual(tuple(item.phase for item in result.oracle_b_audits), ("D", "E"))
        decision = self.exact_raw.traces[1].selection.evidence
        for item, mines, proofs in zip(result.oracle_b_audits,
                                      (decision.local.after.M, decision.after.M),
                                      (decision.local.certificates,
                                       decision.local.certificates + decision.exact_certificates)):
            actual = oracles.materialized_exact_reference(
                decision.observation, decision.num_mines, status=GameStatus.PLAYING,
                logical_mines=mines, proofs=proofs)
            self.assert_status(item, "PASS")
            self.assertEqual(frozenset(item.logical_mines), mines)
            self.assertEqual(item.public_observation, decision.observation)
            self.assertEqual(item.prior_certificate_sha256s,
                             tuple(harness.content_digest(certificate) for certificate in proofs))
            self.assertEqual(item.differences, ())
            self.assertEqual(item.expected_digest, item.actual_digest)
            self.assertIs(type(item.expected), records.OracleBExactSnapshot)
            self.assertIs(type(item.actual), records.OracleBExactSnapshot)
            detached = item.actual
            for field in ("unresolved_cells", "frontier_cells", "unconstrained_cells",
                          "total_worlds", "mine_worlds", "shared_kernel_evidence", "kernel",
                          "materialized_observation"):
                self.assertEqual(getattr(detached, field), getattr(actual, field))
            for field in ("G0", "G1", "minimum_risk_cells"):
                self.assertEqual(frozenset(getattr(detached, field)), getattr(actual, field))
            self.assertEqual(detached.minimum_risk, actual.minimum_risk)
            self.assertTrue(detached.minimum_risk is None or type(detached.minimum_risk) is Fraction)
            self.assertEqual(item.input_digest, oracles.oracle_b_input_digest(
                decision.observation, decision.num_mines, mines))

    def test_each_exact_semantic_field_and_materialization_is_compared(self):
        accepted = oracles.materialized_exact_reference
        changes = (
            ("unresolved_cells", ()), ("frontier_cells", ((0, 0),)),
            ("unconstrained_cells", ((0, 0),)), ("total_worlds", 999),
            ("mine_worlds", ()), ("G0", frozenset({(0, 0)})),
            ("G1", frozenset({(0, 0)})), ("minimum_risk", Fraction(1, 7)),
            ("minimum_risk_cells", frozenset({(0, 0)})),
            ("shared_kernel_evidence", "CHANGED"), ("kernel", "OTHER_KERNEL"),
            ("materialized_observation", ((0,),)),
        )
        for field, value in changes:
            with self.subTest(field=field):
                def altered(*args, **kwargs):
                    return replace(accepted(*args, **kwargs), **{field: value})
                with patch.object(oracles, "materialized_exact_reference", side_effect=altered):
                    result = self.run_audit()
                self.assert_status(result, "FAIL")
                first = result.oracle_b_audits[0]
                self.assert_status(first, "FAIL")
                self.assertTrue(first.differences)
                self.assertFalse(any(item.phase == "E" and item.status is audit.AuditStatus.PASS
                                     for item in result.oracle_b_audits))

    def test_total_worlds_rejects_bool_zero_negative_and_noninteger(self):
        accepted = oracles.materialized_exact_reference
        for value in (True, 0, -1, Fraction(1), 1.0):
            with self.subTest(value=value):
                def altered(*args, **kwargs):
                    return replace(accepted(*args, **kwargs), total_worlds=value)
                with patch.object(oracles, "materialized_exact_reference", side_effect=altered):
                    result = self.run_audit()
                self.assert_status(result, "FAIL")
                self.assertNotEqual(result.oracle_b_audits[0].status, audit.AuditStatus.PASS)

    def test_oracle_exception_or_invalid_result_never_becomes_pass(self):
        for value in (None, (), object()):
            with self.subTest(value=type(value)):
                with patch.object(oracles, "materialized_exact_reference", return_value=value):
                    result = self.run_audit()
                self.assertNotEqual(result.status, audit.AuditStatus.PASS)
        with patch.object(oracles, "materialized_exact_reference", side_effect=ValueError("unavailable")):
            result = self.run_audit()
        self.assertNotEqual(result.status, audit.AuditStatus.PASS)

    def test_forged_oracle_pass_requires_semantics_even_if_digests_collide(self):
        item = self.run_audit().oracle_b_audits[0]
        altered = replace(item.actual, total_worlds=item.actual.total_worlds + 1)
        with patch.object(records, "oracle_b_snapshot_digest", return_value="0" * 64):
            with self.assertRaises(records.RecordError):
                replace(item, actual=altered, expected_digest="0" * 64,
                        actual_digest="0" * 64, differences=(), status=audit.AuditStatus.PASS)

    def test_canonical_oracle_children_keep_complete_snapshots_through_codec(self):
        self.assertIs(audit.OracleBAuditRecord, records.OracleBAuditRecord)
        passing = self.run_audit(self.exact_raw, self.exact_projection)
        with patch.object(oracles, "materialized_exact_reference", side_effect=ValueError("unavailable")):
            failed = self.run_audit()
        seen = set()
        for result in (passing, failed):
            self.assertTrue(result.oracle_b_audits)
            for child in result.oracle_b_audits:
                self.assertIs(type(child), records.OracleBAuditRecord)
                encoded = records.encode(child)
                decoded = records.decode(encoded)
                self.assertIs(type(decoded), records.OracleBAuditRecord)
                self.assertEqual(decoded, child)
                self.assertEqual(records.encode(decoded), encoded)
                self.assertEqual(decoded.expected, child.expected)
                self.assertEqual(decoded.actual, child.actual)
                seen.add(decoded.status)
        self.assertIn(records.AuditStatus.PASS, seen)
        self.assertIn(records.AuditStatus.FAIL, seen)

    def test_incomplete_oracle_child_remains_canonical_without_actual(self):
        raw = replace(self.raw, traces=self.raw.traces[:1] +
                      (replace(self.raw.traces[1], public_effect=None, public_effect_status="NOT_EVALUATED"),)
                      + self.raw.traces[2:])
        projection = game.project_k_p0(raw, self.projection.arm, table=self.table)
        result = self.run_audit(raw, projection)
        for child in result.oracle_b_audits:
            self.assertIs(type(child), records.OracleBAuditRecord)
            self.assertIs(child.status, records.AuditStatus.INCOMPLETE)
            self.assertIsNone(child.actual)
            self.assertIsNone(child.actual_digest)
            self.assertEqual(records.decode(records.encode(child)), child)

    def test_subset_membership_requires_exact_boolean(self):
        for enabled in (None, 0, 1, "yes"):
            with self.subTest(enabled=enabled):
                with self.assertRaises(audit.E2AuditError):
                    self.run_audit(enabled=enabled)

    def test_missing_public_prerequisite_is_incomplete_and_all_phases_retained(self):
        raw = replace(self.raw, traces=self.raw.traces[:1] +
                      (replace(self.raw.traces[1], public_effect=None, public_effect_status="NOT_EVALUATED"),)
                      + self.raw.traces[2:])
        projection = game.project_k_p0(raw, self.projection.arm, table=self.table)
        result = self.run_audit(raw, projection)
        self.assert_status(result, "INCOMPLETE")
        self.assertEqual(len(result.oracle_b_audits), 2)
        self.assertTrue(all(item.status is not audit.AuditStatus.PASS for item in result.oracle_b_audits))


class OracleBTimingTests(AuditFixtures):
    def test_default_and_unselected_paths_never_read_clock_or_emit_timing(self):
        observed = []
        with patch.object(audit, "perf_counter_ns", side_effect=AssertionError("unexpected timing")):
            default = self.run_audit()
            unselected = self.run_audit(enabled=False, oracle_timing_observer=observed.append)
        self.assert_status(default, "PASS")
        self.assert_status(unselected, "PASS")
        self.assertEqual(observed, [])

    def test_observer_on_off_preserve_every_record_and_exact_reference_count(self):
        baseline = self.run_audit(self.exact_raw, self.exact_projection)
        probes = 2 * sum(trace.selection is not None for trace in self.exact_raw.traces[1:])
        observed = []
        bounds = tuple(value for index in range(probes) for value in (100 + index * 20, 107 + index * 20))
        with patch.object(audit, "perf_counter_ns", side_effect=bounds) as clock, \
                patch.object(oracles, "materialized_exact_reference",
                             wraps=oracles.materialized_exact_reference) as reference:
            timed = self.run_audit(self.exact_raw, self.exact_projection,
                                   oracle_timing_observer=observed.append)
        self.assertEqual(timed, baseline)
        self.assertEqual(clock.call_count, probes * 2)
        fact, = observed
        self.assertEqual(fact.arm, self.exact_projection.arm)
        self.assertEqual(fact.applicability_checks, probes)
        self.assertEqual(fact.actual_checks, reference.call_count)
        self.assertEqual(fact.actual_checks, len(timed.oracle_b_audits))
        self.assertEqual(fact.wall_ns, 7 * probes)
        self.assertEqual(fact.intervals, tuple(zip(bounds[::2], bounds[1::2])))
        repeated = []
        with patch.object(audit, "perf_counter_ns", side_effect=bounds):
            self.assertEqual(self.run_audit(self.exact_raw, self.exact_projection,
                             oracle_timing_observer=repeated.append), baseline)
        self.assertEqual(repeated, observed)

    def test_clock_blocks_exclude_certificate_work_and_callback_runs_after_final_semantics(self):
        now, events, observed = [0], [], []
        certificate_call, oracle_call = audit._audit_certificate, audit._oracle_b
        final_validation = audit.KBoardPublicAudit.__post_init__

        def certificate(*args, **kwargs):
            events.append("CERTIFICATE")
            now[0] += 1_000_000
            return certificate_call(*args, **kwargs)

        def oracle(*args, **kwargs):
            events.append("ORACLE")
            now[0] += 11
            return oracle_call(*args, **kwargs)

        def validate(value):
            final_validation(value)
            events.append("FINAL_AUDIT_VALIDATED")

        def observe(fact):
            self.assertEqual(events[-1], "FINAL_AUDIT_VALIDATED")
            observed.append(fact)

        with patch.object(audit, "perf_counter_ns", side_effect=lambda: now[0]), \
                patch.object(audit, "_audit_certificate", side_effect=certificate), \
                patch.object(audit, "_oracle_b", side_effect=oracle), \
                patch.object(audit.KBoardPublicAudit, "__post_init__", validate):
            result = self.run_audit(self.exact_raw, self.exact_projection,
                                    oracle_timing_observer=observe)
        self.assert_status(result, "PASS")
        self.assertIn("CERTIFICATE", events)
        self.assertEqual(observed[0].wall_ns, 11 * events.count("ORACLE"))
        self.assertGreater(now[0], observed[0].wall_ns)

    def test_selected_initial_only_board_emits_honest_zero_fact(self):
        raw = runner.run_k_p0(_PublicPort(_engine(2)), table=self.table, capture_effects=True)
        projection = game.project_k_p0(raw, _arm(records.Arm.K_P0, _board(2)), table=self.table)
        observed = []
        with patch.object(audit, "perf_counter_ns", side_effect=AssertionError("no applicability probe")), \
                patch.object(oracles, "materialized_exact_reference", side_effect=AssertionError("no exact phase")):
            result = self.run_audit(raw, projection, oracle_timing_observer=observed.append)
        self.assert_status(result, "PASS")
        self.assertEqual(observed, [audit.OracleBTimingFact(projection.arm, 0, 0, 0)])

    def test_absent_phase_applicability_is_measured_without_fabricated_minimum(self):
        # Isolate the no-exact-phase branch with a detached synthetic decision.
        # The mocked raw binder makes no claim that this is an executed board.
        raw = self.raw
        for index in range(1, len(raw.traces)):
            if raw.traces[index].selection is not None:
                raw = _with_decision(raw, index, phase_d=None, phase_e=None)
        probes = 2 * sum(trace.selection is not None for trace in raw.traces[1:])
        observed = []
        with patch.object(audit, "_bind_raw"), \
                patch.object(audit, "perf_counter_ns", return_value=100) as clock, \
                patch.object(oracles, "materialized_exact_reference", side_effect=AssertionError("unreached phase")):
            result = self.run_audit(raw, oracle_timing_observer=observed.append)
        self.assertEqual(result.oracle_b_audits, ())
        self.assertEqual(clock.call_count, probes * 2)
        self.assertEqual(observed, [audit.OracleBTimingFact(self.projection.arm, probes, 0, 0,
                                                          ((100, 100),) * probes)])

    def test_failed_reference_and_unready_prerequisites_retain_semantics_and_counts(self):
        with patch.object(oracles, "materialized_exact_reference", side_effect=ValueError("unavailable")):
            baseline = self.run_audit()
            observed = []
            with patch.object(oracles, "materialized_exact_reference", side_effect=ValueError("unavailable")) as reference:
                timed = self.run_audit(oracle_timing_observer=observed.append)
        self.assertEqual(timed, baseline)
        self.assert_status(timed, "FAIL")
        self.assertEqual(observed[0].actual_checks, reference.call_count)
        self.assertEqual(reference.call_count, 1)  # Failing D cannot authorize E.
        raw = replace(self.raw, traces=self.raw.traces[:1] +
                      (replace(self.raw.traces[1], public_effect=None, public_effect_status="NOT_EVALUATED"),)
                      + self.raw.traces[2:])
        projection = game.project_k_p0(raw, self.projection.arm, table=self.table)
        baseline = self.run_audit(raw, projection)
        observed = []
        with patch.object(oracles, "materialized_exact_reference", side_effect=AssertionError("unqualified")):
            timed = self.run_audit(raw, projection, oracle_timing_observer=observed.append)
        self.assertEqual(timed, baseline)
        self.assert_status(timed, "INCOMPLETE")
        self.assertEqual(observed[0].actual_checks, 0)
        self.assertGreater(observed[0].applicability_checks, 0)

    def test_observer_exception_propagates_unchanged_and_bad_binding_never_emits(self):
        error = ValueError("synthetic observer failure")
        with self.assertRaises(ValueError) as raised:
            self.run_audit(oracle_timing_observer=lambda _: (_ for _ in ()).throw(error))
        self.assertIs(raised.exception, error)
        observed = []
        with self.assertRaises(audit.E2AuditError):
            self.run_audit(raw_arm=replace(self.projection.arm, run_id="wrong"),
                           oracle_timing_observer=observed.append)
        self.assertEqual(observed, [])
        for bad in (False, 0, 1.0, "observer", ()):
            with self.subTest(observer=bad), self.assertRaises(audit.E2AuditError):
                self.run_audit(oracle_timing_observer=bad)

    def test_fact_is_closed_immutable_and_rejects_bad_integer_or_interval_evidence(self):
        fact = audit.OracleBTimingFact(self.projection.arm, 2, 1, 9, ((10, 13), (20, 26)))
        self.assertFalse(hasattr(fact, "__dict__"))
        self.assertEqual({item.name for item in fields(fact)},
                         {"arm", "applicability_checks", "actual_checks", "wall_ns", "intervals"})
        self.assertTrue(fact.__dataclass_params__.frozen)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            fact.wall_ns = 0
        for name in ("applicability_checks", "actual_checks", "wall_ns"):
            for value in (True, False, -1, 1.0, Fraction(1)):
                with self.subTest(field=name, value=value), self.assertRaises(audit.E2AuditError):
                    replace(fact, **{name: value})
        for intervals in ([], ((10, 13),), ((10, 13), [20, 26]),
                          ((True, 13), (20, 26)), ((10, 13), (20, 26.0)),
                          ((-1, 13), (20, 26)), ((13, 10), (20, 26)),
                          ((10, 23), (20, 26)), ((20, 26), (10, 13)),
                          ((10, 13), (20, 27))):
            with self.subTest(intervals=intervals), self.assertRaises(audit.E2AuditError):
                replace(fact, intervals=intervals)
        for changes in ({"actual_checks": 3}, {"wall_ns": 10},
                        {"arm": replace(fact.arm, arm=records.Arm.CONTROL)}):
            with self.subTest(changes=changes), self.assertRaises(audit.E2AuditError):
                replace(fact, **changes)
        for forbidden in ("outcome", "effect", "private", "expected", "actual_digest", "certificate"):
            self.assertNotIn(forbidden, {item.name for item in fields(fact)})


class DeterminismAuditTests(AuditFixtures):
    def compare(self, first=None, repeat=None, *, selected=True):
        return audit.compare_determinism(self.projection if first is None else first,
                                         repeat, selected=selected)

    def test_independent_tiny_executions_have_equal_semantics(self):
        raw = runner.run_k_p0(_PublicPort(_engine()), table=self.table, capture_effects=True)
        repeat = game.project_k_p0(raw, self.projection.arm, table=self.table)
        result = self.compare(repeat=repeat)
        self.assert_status(result, "PASS")
        self.assertEqual(result.first_digest, result.repeat_digest)
        self.assertEqual(result.first_semantics, result.repeat_semantics)
        self.assertIsNone(result.first_difference_path)

    def test_transport_identity_and_decision_compute_are_not_semantics(self):
        arm = replace(self.projection.arm, run_id="independent-run", unit_id="independent-unit")
        spans = tuple(replace(item, duration_ns=17) for item in self.projection.decision_spans)
        repeat = replace(self.projection, arm=arm,
                         decisions=tuple(replace(item, arm=arm) for item in self.projection.decisions),
                         guess_checkpoints=tuple(replace(item, arm=arm) for item in self.projection.guess_checkpoints),
                         decision_spans=spans, comparable_compute_ns=17 * len(spans))
        self.assert_status(self.compare(repeat=repeat), "PASS")

    def test_not_selected_is_explicit_and_missing_selected_repeat_is_incomplete(self):
        disabled = self.compare(selected=False)
        self.assertFalse(disabled.selected)
        self.assertIsNone(disabled.status)
        missing = self.compare()
        self.assertTrue(missing.selected)
        self.assert_status(missing, "INCOMPLETE")

    def test_malformed_durable_join_fails_closed_before_comparison(self):
        repeat = _replace_item(self.projection, "physical_inputs", 1, action=records.Action.FLAG)
        with self.assertRaises(audit.E2AuditError):
            self.compare(repeat=repeat)

    def test_missing_compute_diagnostic_alone_is_excluded(self):
        spans = tuple(replace(item, duration_ns=None) for item in self.projection.decision_spans)
        repeat = replace(self.projection, decision_spans=spans, comparable_compute_ns=None,
                         diagnostics=self.projection.diagnostics + tuple(
                             "MISSING_COMPARABLE_COMPUTE:" + str(item.action_ordinal) for item in spans))
        self.assert_status(self.compare(repeat=repeat), "PASS")

    def test_board_fingerprint_and_outcome_differences_fail(self):
        changed_arm = replace(self.projection.arm,
                              board=replace(self.projection.arm.board, fingerprint="different"))
        changed_board = _corrupt(
            self.projection, arm=changed_arm,
            decisions=tuple(replace(item, arm=changed_arm) for item in self.projection.decisions),
            guess_checkpoints=tuple(replace(item, arm=changed_arm)
                                    for item in self.projection.guess_checkpoints))
        for repeat in (_corrupt(self.projection, outcome=records.Outcome.LOSS), changed_board):
            with self.subTest(repeat=repeat.outcome):
                facts = game.derive_k_setup_facts(self.projection)
                with patch.object(game, "derive_k_setup_facts_from_records", return_value=facts):
                    result = self.compare(repeat=repeat)
                self.assert_status(result, "FAIL")
                self.assertIsNotNone(result.first_difference_path)

    def test_physical_action_target_cursor_and_model_stream_fields_are_compared(self):
        item = self.projection.physical_inputs[1]
        changes = ({"action": records.Action.FLAG}, {"target": (3, 0)},
                   {"cursor_before": (1, 0)}, {"input_us": item.input_us + 1},
                   {"cumulative_us": item.cumulative_us + 1})
        facts = game.derive_k_setup_facts(self.projection)
        for change in changes:
            with self.subTest(change=change):
                repeat = _replace_item(self.projection, "physical_inputs", 1, **change)
                with patch.object(game, "derive_k_setup_facts_from_records", return_value=facts):
                    result = self.compare(repeat=repeat)
                self.assert_status(result, "FAIL")
                self.assertIsNotNone(result.first_difference_path)

    def test_public_effects_and_terminal_effects_are_compared(self):
        public = self.projection.public_effects[0]
        change = public.changes[0]
        altered = replace(change, after="CLUE_2" if change.after != "CLUE_2" else "CLUE_3")
        repeat = _replace_item(self.projection, "public_effects", 0,
                               changes=(altered,) + public.changes[1:])
        self.assert_status(self.compare(repeat=repeat), "FAIL")
        terminal = self.projection.terminal_effects[0]
        self.assertTrue(terminal.changes)
        altered = replace(terminal.changes[0], presentation=records.TerminalPresentation.WRONG_FLAG)
        repeat = _replace_item(self.projection, "terminal_effects", 0,
                               changes=(altered,) + terminal.changes[1:])
        self.assert_status(self.compare(repeat=repeat), "FAIL")

    def test_decision_category_kind_plan_metrics_cells_and_m_are_compared(self):
        base = self.exact_projection
        index = next(i for i, item in enumerate(base.decisions) if item.category == "SETUP_CHORD")
        item = base.decisions[index]
        changes = ({"category": "DIRECT_CHORD"}, {"semantic_kind": "OTHER_SEMANTIC"},
                   {"plan_actions": item.plan_actions + (item.plan_actions[-1],)},
                   {"plan_model_us": item.plan_model_us + 1},
                   {"plan_safe_reveals": item.plan_safe_reveals + 1},
                   {"setup_cells": ()}, {"reveal_cells": ()},
                   {"logical_mines_before": item.logical_mines_after},)
        facts = game.derive_k_setup_facts(base)
        for change in changes:
            with self.subTest(change=change):
                self.assertNotEqual(next(iter(change.values())), getattr(item, next(iter(change))))
                repeat = _replace_item(base, "decisions", index, **change)
                with patch.object(game, "derive_k_setup_facts_from_records", return_value=facts):
                    result = self.compare(base, repeat)
                self.assert_status(result, "FAIL")

    def test_checkpoint_unreduced_counts_are_not_reduced_away(self):
        base = self.guess_projection
        checkpoint = base.guess_checkpoints[0]
        repeat = _replace_item(base, "guess_checkpoints", 0,
                               unreduced_z=checkpoint.unreduced_z * 2,
                               mine_counts=tuple((cell, count * 2) for cell, count in checkpoint.mine_counts))
        self.assert_status(self.compare(base, repeat), "FAIL")

    def test_acquisition_digest_and_reference_are_semantic(self):
        base = self.projection
        repeat = _replace_item(base, "acquisitions", 0, certificate_sha256="0" * 64,
                               certificate_ref="sha256:" + "0" * 64)
        self.assert_status(self.compare(base, repeat), "FAIL")

    def test_final_setup_realized_and_abandoned_facts_are_compared(self):
        base = self.exact_projection
        facts = game.derive_k_setup_facts(base)
        self.assertTrue(facts.realized_setup_ordinals)
        changed = replace(facts, realized_setup_ordinals=(),
                          abandoned_setup_ordinals=facts.realized_setup_ordinals)
        with patch.object(game, "derive_k_setup_facts_from_records", side_effect=(facts, changed)):
            result = self.compare(base, deepcopy(base))
        self.assert_status(result, "FAIL")
        self.assertIsNotNone(result.first_difference_path)

    def test_digest_collision_cannot_hide_exact_semantic_difference(self):
        repeat = _replace_item(self.projection, "acquisitions", 0, certificate_sha256="0" * 64,
                               certificate_ref="sha256:" + "0" * 64)
        with patch.object(audit, "_semantic_digest", return_value="f" * 64):
            result = self.compare(repeat=repeat)
        self.assertEqual(result.first_digest, result.repeat_digest)
        self.assert_status(result, "FAIL")
        self.assertNotEqual(result.left_value, result.right_value)
        summary = audit.determinism_record(result)
        self.assertIs(type(summary), records.DeterminismAuditRecord)
        self.assertIs(summary.status, records.AuditStatus.FAIL)
        self.assertEqual(summary.first_digest, summary.repeat_digest)
        self.assertEqual(summary.first_difference_path, result.first_difference_path)
        self.assertEqual(records.decode(records.encode(summary)), summary)

    def test_rich_results_project_to_canonical_summary_for_every_selection_state(self):
        changed = _replace_item(self.projection, "acquisitions", 0, certificate_sha256="0" * 64,
                                certificate_ref="sha256:" + "0" * 64)
        cases = ((self.compare(selected=False), None),
                 (self.compare(), records.AuditStatus.INCOMPLETE),
                 (self.compare(repeat=deepcopy(self.projection)), records.AuditStatus.PASS),
                 (self.compare(repeat=changed), records.AuditStatus.FAIL))
        for rich, expected_status in cases:
            with self.subTest(status=expected_status):
                summary = audit.determinism_record(rich)
                self.assertIs(type(summary), records.DeterminismAuditRecord)
                self.assertIs(summary.status, expected_status)
                for name in ("selected", "first_digest", "repeat_digest", "status", "first_difference_path"):
                    self.assertEqual(getattr(summary, name), getattr(rich, name))
                encoded = records.encode(summary)
                self.assertEqual(records.decode(encoded), summary)
                self.assertEqual(records.encode(records.decode(encoded)), encoded)

    def test_summary_helper_revalidates_exact_semantics_before_pass(self):
        passing = self.compare(repeat=deepcopy(self.projection))
        changed = _replace_item(self.projection, "acquisitions", 0, certificate_sha256="0" * 64,
                                certificate_ref="sha256:" + "0" * 64)
        failed = self.compare(repeat=changed)
        forged = _corrupt(passing, repeat_semantics=failed.repeat_semantics)
        with self.assertRaises(audit.E2AuditError):
            audit.determinism_record(forged)
        for invalid in (None, (), records.DeterminismAuditRecord(False, None, None, None, None)):
            with self.subTest(invalid=type(invalid)):
                with self.assertRaises(audit.E2AuditError):
                    audit.determinism_record(invalid)

    def test_selected_determinism_requires_first_and_repeat_full_i1_stream_premises(self):
        # I6 must persist BOTH first and repeat identities and full I1 component
        # streams below. The durable summary's digests alone are not the premises.
        # This exercises the existing component codecs, not I6 orchestration.
        required = (("physical_inputs", records.PhysicalInputRecord),
                    ("public_effects", records.PublicEffectRecord),
                    ("terminal_effects", records.TerminalEffectRecord),
                    ("decisions", records.ActionDecisionRecord),
                    ("guess_checkpoints", records.GuessCheckpointRecord),
                    ("acquisitions", records.AcquisitionRecord))
        seen = set()
        for first in (self.exact_projection, self.guess_projection):
            arm = replace(first.arm, run_id="repeat-run", unit_id="repeat-unit")
            repeat = replace(first, arm=arm,
                             decisions=tuple(replace(item, arm=arm) for item in first.decisions),
                             guess_checkpoints=tuple(replace(item, arm=arm)
                                                     for item in first.guess_checkpoints))
            rich = self.compare(first, repeat)
            summary = audit.determinism_record(rich)
            self.assertIs(summary.status, records.AuditStatus.PASS)
            self.assertIsNotNone(rich.first_semantics)
            self.assertIsNotNone(rich.repeat_semantics)
            self.assertNotEqual(first.arm, repeat.arm)
            for projection in (first, repeat):
                components = [projection.arm.board, projection.arm]
                for name, cls in required:
                    for child in getattr(projection, name):
                        self.assertIs(type(child), cls)
                        components.append(child)
                        seen.add(name)
                canonical = tuple(records.encode(item) for item in components)
                decoded = tuple(records.decode(data) for data in canonical)
                self.assertEqual(decoded, tuple(components))
                self.assertEqual(tuple(records.encode(item) for item in decoded), canonical)
            self.assertEqual({item.name for item in fields(summary)},
                             {"selected", "first_digest", "repeat_digest", "status", "first_difference_path"})
        self.assertEqual(seen, {name for name, _ in required})

    def test_first_difference_is_stable_and_runtime_metadata_is_absent(self):
        repeat = _replace_item(self.projection, "acquisitions", 0, certificate_sha256="0" * 64,
                               certificate_ref="sha256:" + "0" * 64)
        first = self.compare(repeat=repeat)
        second = self.compare(repeat=deepcopy(repeat))
        self.assertEqual(first.first_difference_path, second.first_difference_path)
        self.assertEqual((first.left_value, first.right_value), (second.left_value, second.right_value))
        names = repr(first.first_semantics)
        for forbidden in ("duration_ns", "compute_ns", "timestamp", "resource_sample", "run_id", "unit_id"):
            self.assertNotIn(forbidden, names)


class PurityAndImmutabilityTests(AuditFixtures):
    def test_all_published_graphs_are_frozen_slotted_and_deeply_detached(self):
        result = self.run_audit(self.exact_raw, self.exact_projection)
        deterministic = audit.compare_determinism(self.exact_projection,
                                                  deepcopy(self.exact_projection), selected=True)
        def visit(value):
            if type(value) in (str, int, bool, type(None), Fraction) or isinstance(value, Enum):
                return
            if type(value) in (tuple, frozenset):
                for child in value:
                    visit(child)
                return
            self.assertTrue(is_dataclass(value), type(value))
            self.assertTrue(value.__dataclass_params__.frozen)
            self.assertFalse(hasattr(value, "__dict__"), type(value))
            self.assertIn(type(value).__module__, {audit.__name__, records.__name__})
            for item in fields(value):
                visit(getattr(value, item.name))
        visit(result)
        visit(deterministic)
        visit(audit.determinism_record(deterministic))
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            result.status = audit.AuditStatus.FAIL

    def test_canonical_children_and_summary_cannot_be_mutated(self):
        result = self.run_audit(self.exact_raw, self.exact_projection)
        certificate = result.certificate_audits[0]
        oracle = result.oracle_b_audits[0]
        rich = audit.compare_determinism(self.exact_projection,
                                         deepcopy(self.exact_projection), selected=True)
        summary = audit.determinism_record(rich)
        for value, name, replacement in ((certificate, "detail", "mutated"),
                                         (oracle, "differences", ("mutated",)),
                                         (oracle.expected, "kernel", "mutated"),
                                         (summary, "status", records.AuditStatus.FAIL)):
            with self.subTest(record=type(value).__name__):
                self.assertFalse(hasattr(value, "__dict__"))
                with self.assertRaises((FrozenInstanceError, AttributeError)):
                    setattr(value, name, replacement)
        with self.assertRaises(TypeError):
            certificate.certificate_premises[0] = ("source", "mutated")
        with self.assertRaises(TypeError):
            oracle.expected.materialized_observation[0][0] = 0

    def test_runtime_audit_uses_no_engine_solver_evaluator_or_archive_reconstruction(self):
        with ExitStack() as stack:
            for owner, name in ((runner, "run_k_p0"), (runner, "run_k_control"),
                                (harness, "verify_fixture"), (harness, "reconstruct"),
                                (harness, "evaluate_execution_archives")):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError("forbidden runtime call")))
            result = self.run_audit()
        self.assert_status(result, "PASS")

    def test_ast_dependency_scope_and_no_io_solver_or_verdict_ownership(self):
        tree = ast.parse(inspect.getsource(audit))
        allowed = {"program_k_e2_records", "program_k_e2_game", "program_k_runner",
                   "program_k_capability", "program_k_policy", "program_k_harness",
                   "program_k_oracles", "program_k_evidence"}
        banned_calls = {"open", "run_k_p0", "run_k_control", "run_control_capture", "step",
                        "generate_board", "execute_e0", "verify_execution_archives", "reconstruct",
                        "evaluate_execution_archives", "enumerate_public_worlds", "KLocalSession",
                        "write_text", "write_bytes", "mkdir", "Popen", "system", "connect"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(item.name.split(".")[0] in sys.stdlib_module_names for item in node.names))
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                if node.module == "experiments":
                    self.assertTrue(all(item.name in allowed for item in node.names))
                elif node.module.startswith("experiments."):
                    self.assertIn(node.module.split(".")[1], allowed)
                else:
                    self.assertTrue(node.module == "core_engine" or node.module.split(".")[0] in sys.stdlib_module_names)
            elif isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
                self.assertNotIn(name, banned_calls)
            elif isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, {"hidden_answer", "mine_positions", "board_layout"})
        public_names = {item.name for item in fields(self.run_audit())}
        self.assertFalse(public_names & {"research_verdict", "progression_allowed", "e3_trigger"})

    def test_import_performs_no_io_process_environment_or_execution_work(self):
        name = "_e2_i5_audit_import_probe"
        source = compile(inspect.getsource(audit), audit.__file__, "exec")
        probe = types.ModuleType(name)
        with patch.dict(sys.modules, {name: probe}), ExitStack() as stack:
            for owner, attribute in ((builtins, "open"), (io, "open"), (os, "open"),
                                     (os, "getcwd"), (os, "getenv"), (Path, "read_bytes"),
                                     (Path, "write_bytes"), (subprocess, "Popen"),
                                     (subprocess, "run"), (runner, "run_k_p0"),
                                     (harness, "audit_acquisition"),
                                     (oracles, "materialized_exact_reference")):
                stack.enter_context(patch.object(owner, attribute, side_effect=AssertionError("import side effect")))
            exec(source, probe.__dict__)
        self.assertTrue(callable(probe.audit_k_p0))


if __name__ == "__main__":
    unittest.main()
