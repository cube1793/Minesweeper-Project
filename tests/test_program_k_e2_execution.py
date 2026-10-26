"""I6 execution contracts on tiny literal boards; no indexed generation or corpus.

Only the private materialization seam is replaced in these unit tests. Production
entry points retain their authenticated generator boundary and expose no layout
option. Process/Job ownership is exercised separately by operational tests.
"""

import ast
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from enum import Enum
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import runpy
import tempfile
import threading
import unittest
from unittest.mock import patch

import benchmark_board
from core_engine import CellState, GameStatus
from experiments import program_k_e2_execution as execution
from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_records as records
from experiments import program_k_e2_game as game
from experiments import program_k_e2_audit as audit
from experiments import program_k_e2_evaluator as evaluator
from experiments import program_k_runner as runner
from experiments import program_k_evidence as evidence
from stage3_physical import action_cost, load_timing_table


def _literal_work(index=42_424_242, *, width=4, mines=frozenset({(1, 0)}), **flags):
    board = records.BoardIdentity(index,
        benchmark_board.calculate_board_fingerprint(width, 1, len(mines), mines),
        width, 1, len(mines), (0, 0), "literal-test-layout", "I6-synthetic")
    selected = dict(oracle_b_selected=True, determinism_selected=True, k_control_selected=True)
    selected.update(flags)
    return execution.BoardWork(0, board, b"\x17" * 32, "i6-literal", **selected)


def _literal_context(work, mines=frozenset({(1, 0)})):
    stack = ExitStack()
    stack.enter_context(patch.object(benchmark_board, "generate_board",
                                    side_effect=AssertionError("Indexed board generation forbidden")))
    stack.enter_context(patch.object(execution, "_materialize_board",
                                    return_value=execution._BoardOwner(work.board, mines)))
    return stack


def _streams(bundle):
    return {name: tuple(records.decode(data) for data in values) for name, values in bundle.streams}


def _replace_stream(bundle, name, values):
    return replace(bundle, streams=tuple((key, tuple(records.encode(v) for v in values) if key == name else data)
                                         for key, data in bundle.streams))


class WorkPlanTests(unittest.TestCase):
    def test_frozen_selection_caps_and_labels_on_invented_identities(self):
        boards = tuple(_literal_work(42_424_242 + n).board for n in range(300))
        plan = execution.make_work_plan(boards, protocol_seed=b"\x17" * 32, run_id="synthetic-selection")
        self.assertEqual(plan, execution.make_work_plan(boards, protocol_seed=b"\x17" * 32,
                                                       run_id="synthetic-selection"))
        digest = identity.corpus_digest(b"\x17" * 32, len(boards), tuple(board.game_index for board in boards))
        for field, label, count in (("oracle_b_selected", identity.ORACLE_B_LABEL, 128),
                                    ("determinism_selected", identity.DETERMINISM_LABEL, 256),
                                    ("k_control_selected", identity.KCONTROL_LABEL, 256)):
            expected = identity.select_subset_positions(label, b"\x17" * 32, digest, 300, count)
            self.assertEqual(tuple(w.position for w in plan if getattr(w, field)), tuple(sorted(expected)))
        execution.revalidate_work_plan(plan)

    def test_both_frozen_balanced_orders_occur_without_execution(self):
        works = tuple(_literal_work(42_424_242 + n) for n in range(32))
        self.assertEqual({w.arm_order for w in works}, set(identity.ArmOrder))
        for work in works:
            self.assertIs(work.arm_order, identity.arm_order(work.protocol_seed, work.board.game_index))

    def test_plan_rejects_duplicate_gap_order_and_modified_selection(self):
        boards = tuple(_literal_work(42_424_242 + n).board for n in range(3))
        plan = execution.make_work_plan(boards, protocol_seed=b"\x17" * 32, run_id="synthetic-selection")
        for bad in ((plan[0], plan[0]), plan[::-1], (plan[0], plan[2]),
                    (replace(plan[0], oracle_b_selected=False),) + plan[1:]):
            with self.subTest(plan=bad), self.assertRaises(ValueError):
                execution.revalidate_work_plan(bad)

    def test_exact_immutable_work_and_fingerprint_ownership(self):
        work = _literal_work()
        for field, value in (("position", True), ("oracle_b_selected", 1), ("protocol_seed", bytearray(32))):
            with self.assertRaises(ValueError):
                replace(work, **{field: value})
        with self.assertRaises(FrozenInstanceError):
            work.position = 1
        with self.assertRaises(ValueError):
            execution._BoardOwner(work.board, frozenset({(2, 0)}))
        self.assertNotIn("(1, 0)", repr(execution._BoardOwner(work.board, frozenset({(1, 0)}))))

    def test_production_rejects_literal_identity_before_generator(self):
        with patch.object(benchmark_board, "generate_board", side_effect=AssertionError("Must reject before generation")):
            with self.assertRaisesRegex(execution.E2IdentityMismatch, "IDENTITY"):
                execution.execute_primary(_literal_work())


class PrimaryPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = _literal_work()
        cls.table = load_timing_table()
        with _literal_context(cls.work):
            cls.primary = execution.execute_primary(cls.work)

    def _observe_adjacent_pair(self, work):
        events, ended, raw, ports = [], set(), {}, []
        originals = (runner.run_control_capture, runner.run_k_p0)

        def observe(name, arm):
            if name in ("ARM_START", "ARM_END"):
                events.append((name, arm))
            if name == "ARM_END":
                ended.add(arm)

        def run(kind, accepted, port, **kwargs):
            ports.append(port)
            self.assertIs(port.status, GameStatus.PLAYING)
            self.assertEqual(tuple(tuple(row) for row in port.get_observation()),
                             ((int(CellState.HIDDEN),) * work.board.width,))
            events.append(("RUNNER_ENTER", kind))
            raw[kind] = accepted(port, **kwargs)
            events.append(("RUNNER_RETURN", kind))
            return raw[kind]

        def guarded(accepted, label, raw_kind=None):
            def call(*args, **kwargs):
                self.assertEqual(ended, {"CONTROL", "K_P0"}, label + " preceded both ARM_ENDs")
                if raw_kind is not None:
                    self.assertIs(args[0], raw[raw_kind])
                events.append((label, None))
                return accepted(*args, **kwargs)
            return call

        with ExitStack() as stack:
            stack.enter_context(_literal_context(work))
            stack.enter_context(patch.object(runner, "run_control_capture",
                side_effect=lambda port, **kw: run("CONTROL", originals[0], port, **kw)))
            stack.enter_context(patch.object(runner, "run_k_p0",
                side_effect=lambda port, **kw: run("K_P0", originals[1], port, **kw)))
            for module, name, label, raw_kind in (
                    (game, "project_control", "PROJECT_CONTROL", "CONTROL"),
                    (game, "project_k_p0", "PROJECT_KP0", "K_P0"),
                    (audit, "audit_k_p0", "AUDIT", "K_P0"),
                    (audit, "_oracle_b", "ORACLE_B", None),
                    (game, "pair_projections", "PAIR", None),
                    (records, "encode", "SERIALIZE", None)):
                stack.enter_context(patch.object(module, name,
                    side_effect=guarded(getattr(module, name), label, raw_kind)))
            evaluated = stack.enter_context(patch.object(evaluator, "evaluate_k_p0",
                side_effect=guarded(evaluator.evaluate_k_p0, "EVALUATOR", "K_P0")))
            result = execution.execute_primary(work, observer=observe)
        evaluated.assert_called_once()
        self.assertIsNot(ports[0], ports[1])
        return result, events

    def test_primary_arms_execute_adjacent_before_any_projection_or_audit(self):
        for order in identity.ArmOrder:
            work = next(_literal_work(42_424_242 + n) for n in range(32)
                        if _literal_work(42_424_242 + n).arm_order is order)
            with self.subTest(order=order):
                result, events = self._observe_adjacent_pair(work)
                arms = ("CONTROL", "K_P0") if order is identity.ArmOrder.CONTROL_THEN_KP0 else ("K_P0", "CONTROL")
                expected = [(event, arm) for arm in arms
                            for event in ("ARM_START", "RUNNER_ENTER", "RUNNER_RETURN", "ARM_END")]
                self.assertEqual(events[:8], expected)
                self.assertEqual(events[8], ("PROJECT_CONTROL", None))
                self.assertIs(result.status, records.AuditStatus.PASS)
                with _literal_context(work):
                    reference = execution.execute_primary(work)
                for role in ("control", "kp0"):
                    a, b = execution.restore_projection(result, role), execution.restore_projection(reference, role)
                    self.assertEqual(a.physical_inputs, b.physical_inputs)
                    self.assertEqual(a.decisions, b.decisions)
                    self.assertEqual((a.outcome, a.total_model_us), (b.outcome, b.total_model_us))

    def test_evaluator_and_oracle_work_never_runs_between_primary_solver_arms(self):
        _, events = self._observe_adjacent_pair(self.work)
        second_end = max(index for index, (name, _) in enumerate(events) if name == "ARM_END")
        for label in ("PROJECT_CONTROL", "PROJECT_KP0", "AUDIT", "ORACLE_B", "EVALUATOR", "PAIR", "SERIALIZE"):
            positions = [index for index, (name, _) in enumerate(events) if name == label]
            self.assertTrue(positions, label)
            self.assertTrue(all(index > second_end for index in positions), label)
        self.assertEqual(sum(name == "EVALUATOR" for name, _ in events), 1)

    def test_existing_runners_same_process_fresh_public_state_frozen_order(self):
        seen, ports, raw = [], [], {}
        accepted_control, accepted_kp0 = runner.run_control_capture, runner.run_k_p0
        def capture(kind, accepted, port, **kwargs):
            seen.append((kind, os.getpid()))
            ports.append(port)
            self.assertIs(port.status, GameStatus.PLAYING)
            self.assertEqual(tuple(tuple(row) for row in port.get_observation()), ((int(CellState.HIDDEN),) * 4,))
            raw[kind] = accepted(port, **kwargs)
            return raw[kind]
        with _literal_context(self.work), patch.object(runner, "run_control_capture",
                side_effect=lambda port, **kw: capture(records.Arm.CONTROL, accepted_control, port, **kw)), \
                patch.object(runner, "run_k_p0",
                side_effect=lambda port, **kw: capture(records.Arm.K_P0, accepted_kp0, port, **kw)):
            result = execution.execute_primary(self.work)
        expected = ((records.Arm.CONTROL, records.Arm.K_P0)
                    if self.work.arm_order is identity.ArmOrder.CONTROL_THEN_KP0
                    else (records.Arm.K_P0, records.Arm.CONTROL))
        self.assertEqual(tuple(kind for kind, _ in seen), expected)
        self.assertEqual({pid for _, pid in seen}, {os.getpid()})
        self.assertIsNot(ports[0], ports[1])
        self.assertIs(result.arm_order, self.work.arm_order)
        for role, kind in (("control", records.Arm.CONTROL), ("kp0", records.Arm.K_P0)):
            projection = execution.restore_projection(result, role)
            total = 0
            for source, item in zip(raw[kind].traces, projection.physical_inputs):
                total += action_cost(self.table, source.cursor_before, (source.move.x, source.move.y))
                self.assertEqual((item.action.value, item.target, item.input_us, item.cumulative_us, item.after_status.value),
                                 (source.move.action.name, (source.move.x, source.move.y), source.modeled_action_us,
                                  total, source.status_after.name))
            self.assertEqual(projection.total_model_us, raw[kind].total_modeled_us)

    def test_pair_is_exact_i4_output_and_no_actual_kcontrol_stream(self):
        parts = _streams(self.primary)
        paired = game.pair_projections(execution.restore_projection(self.primary, "control"),
                                       execution.restore_projection(self.primary, "kp0"))
        self.assertEqual(parts["pairs"], (paired.pair,))
        self.assertNotIn("kcontrol_maintenance", parts)
        self.assertNotIn("kcontrol_arms", parts)
        self.assertTrue(parts["control_maintenance"])
        self.assertTrue(all(item.arm.arm is records.Arm.CONTROL for item in parts["control_maintenance"]))

    def test_audit_and_one_evaluator_run_inside_raw_lifetime_before_publication(self):
        calls, raw_seen = [], []
        old_audit, old_eval, old_bundle = audit.audit_k_p0, evaluator.evaluate_k_p0, execution._bundle
        def public(raw, *args, **kw):
            calls.append("audit")
            raw_seen.append(raw)
            return old_audit(raw, *args, **kw)
        def private(raw, projection, answer, **kw):
            calls.append("evaluator")
            self.assertIs(raw, raw_seen[0])
            self.assertIs(type(answer), evaluator.PrivateFixedAnswer)
            self.assertEqual(answer.arm, projection.arm)
            return old_eval(raw, projection, answer, **kw)
        def publish(*args, **kw):
            calls.append("publish")
            return old_bundle(*args, **kw)
        with _literal_context(self.work), patch.object(audit, "audit_k_p0", side_effect=public), \
                patch.object(evaluator, "evaluate_k_p0", side_effect=private) as evaluated, \
                patch.object(execution, "_bundle", side_effect=publish):
            result = execution.execute_primary(self.work)
        evaluated.assert_called_once()
        self.assertEqual(calls, ["audit", "evaluator", "publish"])
        self.assertEqual(tuple(v.assertion for v in _streams(result)["evaluators"]), tuple(records.AssertionCategory))

    def test_oracle_disabled_makes_zero_maintenance_calls(self):
        work = replace(self.work, oracle_b_selected=False)
        with _literal_context(work), patch.object(audit, "_oracle_b", side_effect=AssertionError("Unselected B called")):
            result = execution.execute_primary(work)
        self.assertEqual(_streams(result)["oracle_b_audits"], ())

    def test_primary_without_selected_maintenance_has_no_reference_or_extra_runner(self):
        work = replace(self.work, oracle_b_selected=False, determinism_selected=False, k_control_selected=False)
        with _literal_context(work), patch.object(runner, "run_k_control", side_effect=AssertionError("Unselected")), \
                patch.object(evaluator, "evaluate_k_p0", wraps=evaluator.evaluate_k_p0) as evaluated:
            result = execution.execute_primary(work)
        evaluated.assert_called_once()
        parts = _streams(result)
        self.assertNotIn("control_maintenance", parts)
        self.assertFalse(any(name.startswith("repeat_") or name.startswith("kcontrol_") for name in parts))
        self.assertTrue(parts["certificate_audits"])

    def test_raw_evaluator_failure_cannot_be_upgraded_by_transport_header(self):
        values = _streams(self.primary)["evaluators"]
        failed = replace(values[0], status=records.EvaluationStatus.FAIL, reason_code="SYNTHETIC_FALSE_CLAIM")
        candidate = _replace_stream(self.primary, "evaluators", (failed,) + values[1:])
        with self.assertRaisesRegex(ValueError, "FAILURE_CANNOT_BE_UPGRADED"):
            execution.revalidate_bundle(candidate, self.work, execution.WorkerKind.PRIMARY)

    def test_every_acquisition_and_reached_oracle_phase_has_canonical_children(self):
        parts = _streams(self.primary)
        self.assertTrue(parts["certificate_audits"])
        self.assertTrue(parts["oracle_b_audits"])
        self.assertEqual(tuple(v.acquisition for v in parts["certificate_audits"]), parts["kp0_acquisitions"])
        for name, cls in (("certificate_audits", records.CertificateAuditRecord),
                          ("oracle_b_audits", records.OracleBAuditRecord), ("evaluators", records.EvaluatorRecord)):
            for value in parts[name]:
                self.assertIs(type(value), cls)
                self.assertEqual(records.decode(records.encode(value)), value)

    def test_parent_bundle_contains_only_closed_headers_and_canonical_bytes(self):
        allowed = (execution.WorkerBundle, execution.ProjectionHeader)
        def inspect_value(value):
            if is_dataclass(value):
                self.assertIn(type(value), allowed)
                self.assertFalse(hasattr(value, "__dict__"))
                for field in fields(value):
                    inspect_value(getattr(value, field.name))
            elif type(value) is tuple:
                for item in value:
                    inspect_value(item)
            else:
                self.assertTrue(value is None or type(value) in (str, int, bool, bytes)
                                or type(value) in (execution.WorkerKind, identity.ArmOrder, records.AuditStatus))
        inspect_value(self.primary)
        encoded = execution.encode_bundle(self.primary)
        for forbidden in (b"mine_positions", b"PrivateFixedAnswer", b"MinesweeperEngine", b"__dict__", b"pickle"):
            self.assertNotIn(forbidden, encoded)
        self.assertEqual(execution.decode_bundle(encoded), self.primary)
        self.assertNotIn("research_verdict", {field.name for field in fields(self.primary)})

    def test_input_cap_aborts_without_substitute_action(self):
        with _literal_context(self.work), self.assertRaisesRegex(ValueError, "INPUT_CAP"):
            execution.execute_primary(self.work, max_physical_inputs=1)

    def test_missing_comparable_duration_preserves_scope_and_classifies_incomplete(self):
        accepted = runner.run_control_capture
        def missing_timing(port, **kwargs):
            raw = accepted(port, **kwargs)
            return replace(raw, timings=tuple(replace(value, v1_plan_position_ns=None) for value in raw.timings),
                           control=replace(raw.control, traces=tuple(replace(value, decision_compute_ns=None)
                                                                     for value in raw.traces)))
        with _literal_context(self.work), patch.object(runner, "run_control_capture", side_effect=missing_timing):
            result = execution.execute_primary(self.work)
        self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
        projection = execution.restore_projection(result, "control")
        self.assertTrue(projection.decision_spans)
        self.assertIsNone(projection.comparable_compute_ns)
        with self.assertRaises(ValueError):
            execution.revalidate_bundle(replace(result, status=records.AuditStatus.PASS, reason_codes=()),
                                        self.work, execution.WorkerKind.PRIMARY)

    def test_parent_rejects_missing_audits_wrong_binding_and_size(self):
        for candidate in (_replace_stream(self.primary, "certificate_audits", ()),
                          _replace_stream(self.primary, "evaluators", ()),
                          replace(self.primary, work_position=1)):
            with self.assertRaises(ValueError):
                execution.revalidate_bundle(candidate, self.work, execution.WorkerKind.PRIMARY)
        with self.assertRaises(ValueError):
            execution.revalidate_bundle(self.primary, self.work, execution.WorkerKind.PRIMARY, max_payload_bytes=10)

    def test_transport_rejects_noncanonical_unknown_duplicate_and_float(self):
        data = execution.encode_bundle(self.primary)
        obj = json.loads(data)
        for bad in (data + b"\n", data.replace(b'"version":1', b'"version":1.0'),
                    b'{"unknown":0,' + data[1:], b'{"version":1,' + data[1:]):
            with self.assertRaises((ValueError, TypeError)):
                execution.decode_bundle(bad)
        self.assertEqual(obj["version"], 1)


class OracleTimingObserverTests(unittest.TestCase):
    """The optional operational observer cannot alter accepted worker evidence."""

    def _fixed_solver_clocks(self):
        # Solver duration noise is excluded from this exact evidence comparison;
        # the independent Oracle observer retains its real clock and intervals.
        stack = ExitStack()
        stack.enter_context(patch.object(runner, "perf_counter_ns", return_value=100))
        stack.enter_context(patch("stage3_runner.perf_counter_ns", return_value=100))
        return stack

    def _assert_fact(self, fact, arm):
        self.assertIs(type(fact), audit.OracleBTimingFact)
        self.assertEqual(tuple(field.name for field in fields(fact)),
                         ("arm", "applicability_checks", "actual_checks", "wall_ns", "intervals"))
        self.assertEqual(fact.arm, arm)
        self.assertFalse(hasattr(fact, "__dict__"))
        self.assertIs(type(fact.intervals), tuple)
        self.assertEqual(len(fact.intervals), fact.applicability_checks)
        self.assertEqual(sum(end - start for start, end in fact.intervals), fact.wall_ns)
        self.assertLessEqual(fact.actual_checks, fact.applicability_checks)
        for field in fields(fact):
            with self.subTest(field=field.name), self.assertRaises(FrozenInstanceError):
                setattr(fact, field.name, None)
        for name in ("private_answer", "mine_positions", "projection", "outcome", "pair",
                     "model_c_delta", "ww_wl_lw_ll", "g5_g8_g9", "mechanism_counts"):
            self.assertFalse(hasattr(fact, name))

    def test_primary_observer_preserves_exact_evidence_and_default_audit_keywords(self):
        work, facts = _literal_work(), []
        with _literal_context(work), self._fixed_solver_clocks(), \
                patch.object(runner, "run_control_capture", wraps=runner.run_control_capture) as control, \
                patch.object(runner, "run_k_p0", wraps=runner.run_k_p0) as kp0, \
                patch.object(runner, "run_k_control", side_effect=AssertionError("No K-CONTROL worker")), \
                patch.object(audit, "_oracle_b", wraps=audit._oracle_b) as oracle, \
                patch.object(audit, "audit_k_p0", wraps=audit.audit_k_p0) as audited, \
                patch.object(evaluator, "evaluate_k_p0", wraps=evaluator.evaluate_k_p0) as evaluated:
            with patch.object(audit, "perf_counter_ns", side_effect=AssertionError("Default audit has no observer clock")):
                baseline = execution.execute_primary(work)
            default_calls = oracle.call_count
            oracle.reset_mock()
            observed = execution.execute_primary(work, oracle_timing_observer=facts.append)
        self.assertEqual(set(audited.call_args_list[0].kwargs), {"raw_arm", "table", "oracle_b_enabled"})
        self.assertEqual(set(audited.call_args_list[1].kwargs),
                         {"raw_arm", "table", "oracle_b_enabled", "oracle_timing_observer"})
        self.assertEqual((control.call_count, kp0.call_count, evaluated.call_count), (2, 2, 2))
        self.assertGreater(default_calls, 0)
        self.assertEqual(oracle.call_count, default_calls)
        self.assertEqual(execution.encode_bundle(observed), execution.encode_bundle(baseline))
        self.assertIs(observed.status, records.AuditStatus.PASS)
        self.assertEqual(len(facts), 1)
        self._assert_fact(facts[0], execution.restore_projection(observed, "kp0").arm)

    def test_repeat_observer_preserves_full_first_repeat_evidence_and_identity(self):
        work, facts = _literal_work(), []
        with _literal_context(work), self._fixed_solver_clocks():
            first = execution.execute_primary(work)
            first_bytes = execution.encode_bundle(first)
            with patch.object(runner, "run_control_capture", wraps=runner.run_control_capture) as control, \
                    patch.object(runner, "run_k_p0", wraps=runner.run_k_p0) as kp0, \
                    patch.object(runner, "run_k_control", side_effect=AssertionError("No K-CONTROL worker")), \
                    patch.object(audit, "_oracle_b", wraps=audit._oracle_b) as oracle, \
                    patch.object(audit, "audit_k_p0", wraps=audit.audit_k_p0) as audited:
                baseline = execution.execute_repeat(work, first)
                default_calls = oracle.call_count
                oracle.reset_mock()
                observed = execution.execute_repeat(work, first, oracle_timing_observer=facts.append)
        self.assertEqual((control.call_count, kp0.call_count), (2, 2))
        self.assertEqual(oracle.call_count, default_calls)
        self.assertNotIn("oracle_timing_observer", audited.call_args_list[0].kwargs)
        self.assertIn("oracle_timing_observer", audited.call_args_list[1].kwargs)
        self.assertEqual(execution.encode_bundle(observed), execution.encode_bundle(baseline))
        self.assertEqual(execution.encode_bundle(first), first_bytes)
        self.assertEqual(len(facts), 1)
        repeat_arm = execution.restore_projection(observed, "repeat_kp0").arm
        self._assert_fact(facts[0], repeat_arm)
        self.assertNotEqual(repeat_arm.unit_id, execution.restore_projection(first, "kp0").arm.unit_id)
        parts = _streams(observed)
        for name in ("control_determinism", "kp0_determinism"):
            self.assertIs(parts[name][0].status, records.AuditStatus.PASS)
        execution.revalidate_bundle(observed, work, execution.WorkerKind.DETERMINISM)

    def test_observer_receives_only_closed_fact_after_both_solver_arms_end(self):
        work, ended, facts = _literal_work(), set(), []

        def boundary(name, arm):
            if name == "ARM_END":
                ended.add(arm)

        def observe(fact):
            self.assertEqual(ended, {"CONTROL", "K_P0"})
            self.assertIs(type(fact), audit.OracleBTimingFact)
            facts.append(fact)

        with _literal_context(work):
            observed = execution.execute_primary(work, observer=boundary, oracle_timing_observer=observe)
        self.assertEqual(len(facts), 1)
        self._assert_fact(facts[0], execution.restore_projection(observed, "kp0").arm)
        self.assertGreater(facts[0].actual_checks, 0)
        self.assertNotIn("oracle_timing", {name for name, _ in observed.streams})

    def test_observer_exception_propagates_without_evaluator_or_published_bundle(self):
        work = _literal_work()
        with _literal_context(work):
            first = execution.execute_primary(work)
        for repeat in (False, True):
            failure = RuntimeError("synthetic observer failure")
            with self.subTest(repeat=repeat), _literal_context(work), \
                    patch.object(evaluator, "evaluate_k_p0", side_effect=AssertionError("Observer already failed")), \
                    patch.object(execution, "_bundle", side_effect=AssertionError("No successful bundle after failure")), \
                    patch.object(audit, "OracleBTimingFact", wraps=audit.OracleBTimingFact) as made:
                def observe(fact):
                    raise failure
                with self.assertRaises(RuntimeError) as caught:
                    if repeat:
                        execution.execute_repeat(work, first, oracle_timing_observer=observe)
                    else:
                        execution.execute_primary(work, oracle_timing_observer=observe)
                self.assertIs(caught.exception, failure)
                self.assertEqual(made.call_count, 1)

    def test_disabled_oracle_does_not_measure_or_callback_for_primary_or_repeat(self):
        work = _literal_work(oracle_b_selected=False)
        with _literal_context(work), \
                patch.object(audit, "_oracle_b", side_effect=AssertionError("Disabled Oracle executed")), \
                patch.object(audit, "perf_counter_ns", side_effect=AssertionError("Disabled Oracle timed")):
            def forbidden(_):
                self.fail("Disabled Oracle emitted timing")
            first = execution.execute_primary(work, oracle_timing_observer=forbidden)
            repeated = execution.execute_repeat(work, first, oracle_timing_observer=forbidden)
        self.assertEqual(_streams(first)["oracle_b_audits"], ())
        self.assertEqual(_streams(repeated)["repeat_oracle_b_audits"], ())
        self.assertIs(first.status, records.AuditStatus.PASS)
        self.assertIs(repeated.status, records.AuditStatus.PASS)

    def test_initial_only_literal_reports_completed_zero_applicability_without_fake_wall(self):
        mines, facts = frozenset(), []
        work = _literal_work(width=1, mines=mines)
        with _literal_context(work, mines), \
                patch.object(audit, "_oracle_b", side_effect=AssertionError("Initial-only Oracle comparison")):
            result = execution.execute_primary(work, oracle_timing_observer=facts.append)
        self.assertEqual(len(facts), 1)
        self._assert_fact(facts[0], execution.restore_projection(result, "kp0").arm)
        self.assertEqual((facts[0].applicability_checks, facts[0].actual_checks,
                          facts[0].wall_ns, facts[0].intervals), (0, 0, 0, ()))
        self.assertEqual(_streams(result)["oracle_b_audits"], ())


class PriorBindingObserverTests(unittest.TestCase):
    def _fixed_solver_clocks(self):
        stack = ExitStack()
        stack.enter_context(patch.object(runner, "perf_counter_ns", return_value=100))
        stack.enter_context(patch("stage3_runner.perf_counter_ns", return_value=100))
        return stack

    def test_both_downstream_callbacks_end_before_target_setup_and_solver(self):
        work = _literal_work()
        with _literal_context(work):
            first = execution.execute_primary(work)
        accepted = execution.revalidate_bundle
        for kind, invoke in ((execution.WorkerKind.K_CONTROL, execution.execute_k_control),
                             (execution.WorkerKind.DETERMINISM, execution.execute_repeat)):
            events, facts = [], []

            def validate(bundle, bound_work, bound_kind, **kwargs):
                if bundle is first:
                    self.assertEqual(events, ["CLOCK"])
                    events.append("VALIDATE_PRIOR")
                return accepted(bundle, bound_work, bound_kind, **kwargs)

            def clock():
                events.append("CLOCK")
                return 100 if len(events) == 1 else 175

            def observed(fact):
                self.assertEqual(events, ["CLOCK", "VALIDATE_PRIOR", "CLOCK"])
                facts.append(fact)
                events.append("BOUND")

            def materialize(bound_work):
                self.assertEqual(events[-1], "BOUND")
                events.append("TARGET_SETUP")
                return execution._BoardOwner(bound_work.board, frozenset({(1, 0)}))

            def boundary(name, arm):
                if name == "ARM_START":
                    self.assertEqual(events[-1], "TARGET_SETUP")

            with self.subTest(kind=kind), _literal_context(work), \
                    patch.object(execution, "revalidate_bundle", side_effect=validate), \
                    patch.object(execution, "perf_counter_ns", side_effect=clock) as timed, \
                    patch.object(execution, "_materialize_board", side_effect=materialize):
                result = invoke(work, first, prior_binding_observer=observed, observer=boundary)
            self.assertIs(result.status, records.AuditStatus.PASS)
            self.assertEqual(timed.call_count, 2)
            self.assertEqual(facts, [execution.PriorBindingTimingFact(work.position, kind, 100, 175)])
            self.assertEqual(facts[0].wall_ns, 75)
            self.assertNotIn("prior_binding", {name for name, _ in result.streams})

    def test_observer_preserves_exact_bundles_and_prior_bytes(self):
        work = _literal_work()
        with _literal_context(work), self._fixed_solver_clocks():
            first = execution.execute_primary(work)
            before = execution.encode_bundle(first)
            for invoke in (execution.execute_k_control, execution.execute_repeat):
                facts = []
                with self.subTest(invoke=invoke.__name__):
                    with patch.object(execution, "perf_counter_ns", side_effect=AssertionError("Default clock")):
                        baseline = invoke(work, first)
                    observed = invoke(work, first, prior_binding_observer=facts.append)
                    self.assertEqual(execution.encode_bundle(observed), execution.encode_bundle(baseline))
                    self.assertEqual(execution.encode_bundle(first), before)
                    self.assertEqual(len(facts), 1)

    def test_unselected_target_never_observes_or_reads_clock(self):
        work = _literal_work(determinism_selected=False, k_control_selected=False)
        with patch.object(execution, "perf_counter_ns", side_effect=AssertionError("Unselected clock")), \
                patch.object(execution, "_materialize_board", side_effect=AssertionError("Unselected setup")):
            for invoke in (execution.execute_k_control, execution.execute_repeat):
                self.assertIsNone(invoke(work, None, prior_binding_observer=lambda _: self.fail("Unselected callback")))

    def test_callback_failure_and_invalid_prior_cannot_enter_target(self):
        work = _literal_work()
        with _literal_context(work):
            first = execution.execute_primary(work)
        for invoke in (execution.execute_k_control, execution.execute_repeat):
            with self.subTest(invoke=invoke.__name__), \
                    patch.object(execution, "_materialize_board", side_effect=AssertionError("No target after failure")):
                failure = RuntimeError("synthetic binding observer failure")

                def reject(_):
                    raise failure

                with self.assertRaises(RuntimeError) as caught:
                    invoke(work, first, prior_binding_observer=reject)
                self.assertIs(caught.exception, failure)
                with self.assertRaises(ValueError):
                    invoke(work, replace(first, work_position=1),
                           prior_binding_observer=lambda _: self.fail("Invalid prior callback"))
                with self.assertRaisesRegex(ValueError, "PRIOR_BINDING_OBSERVER_REQUIRED"):
                    invoke(work, first, prior_binding_observer=42)

    def test_timing_fact_is_closed_immutable_and_strict(self):
        fact = execution.PriorBindingTimingFact(0, execution.WorkerKind.K_CONTROL, 7, 7)
        self.assertEqual(fact.wall_ns, 0)
        self.assertEqual(tuple(field.name for field in fields(fact)),
                         ("work_position", "kind", "start_ns", "end_ns"))
        self.assertFalse(hasattr(fact, "__dict__"))
        for field in fields(fact):
            with self.assertRaises(FrozenInstanceError):
                setattr(fact, field.name, None)
        for changes in ({"work_position": True}, {"kind": execution.WorkerKind.PRIMARY},
                        {"kind": "K_CONTROL"}, {"start_ns": -1}, {"end_ns": 6},
                        {"start_ns": 1.0}, {"end_ns": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(fact, **changes)


class OracleCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = _literal_work()
        cls.raw_results = []
        accepted = runner.run_k_p0
        def capture(port, **kwargs):
            raw = accepted(port, **kwargs)
            cls.raw_results.append(raw)
            return raw
        with _literal_context(cls.work), patch.object(runner, "run_k_p0", side_effect=capture):
            cls.primary = execution.execute_primary(cls.work)
            cls.repeat = execution.execute_repeat(cls.work, cls.primary)

    def _cases(self):
        return ((self.primary, execution.WorkerKind.PRIMARY, ""),
                (self.repeat, execution.WorkerKind.DETERMINISM, "repeat_"))

    def test_selected_zero_applicable_phases_is_explicit_and_makes_zero_oracle_calls(self):
        work = _literal_work(42_424_244, width=1, mines=frozenset())
        facts, bindings = [], []
        with _literal_context(work, frozenset()), patch.object(audit, "_oracle_b",
                side_effect=AssertionError("No reached phase can invoke Oracle-B")):
            result = execution.execute_primary(work)
            repeated = execution.execute_repeat(work, result, oracle_timing_observer=facts.append,
                                                 prior_binding_observer=bindings.append)
        for bundle, prefix in ((result, ""), (repeated, "repeat_")):
            coverage, = _streams(bundle)[prefix + "oracle_b_coverage"]
            self.assertTrue(coverage.selected)
            self.assertEqual(coverage.applicable, ())
            self.assertEqual(_streams(bundle)[prefix + "oracle_b_audits"], ())
            self.assertIs(bundle.status, records.AuditStatus.PASS)
        self.assertEqual(len(bindings), 1)  # No audit rows still consumes/binds the prior.
        self.assertEqual(len(facts), 1)
        self.assertEqual((facts[0].applicability_checks, facts[0].actual_checks, facts[0].wall_ns), (0, 0, 0))

    def test_raw_applicability_d_only_d_and_e_and_chronological_boundaries(self):
        raw = self.raw_results[0]
        source = next(t for t in raw.traces if t.selection is not None)
        snapshot = next(phase for t in raw.traces if t.selection is not None
                        for phase in (t.selection.evidence.phase_d, t.selection.evidence.phase_e) if phase is not None)
        arm = execution._arm(self.work, records.Arm.K_P0)
        # These detached fixtures exercise reached-phase presence only. They are
        # never executed, projected as solver results or admitted as exact proofs.
        for phases, expected in (((None, None), ()), ((snapshot, None), ((1, "D"),)),
                                 ((snapshot, snapshot), ((1, "D"), (1, "E")))):
            decision = replace(source.selection.evidence, phase_d=phases[0], phase_e=phases[1])
            trace = replace(source, input_index=1, selection=replace(source.selection, evidence=decision))
            fixture = replace(raw, traces=(raw.traces[0], trace))
            with self.subTest(expected=expected):
                value = execution._oracle_b_coverage(fixture, arm, True)
                self.assertEqual(value.applicable, expected)
        first = replace(source, input_index=1, selection=replace(source.selection,
            evidence=replace(source.selection.evidence, phase_d=snapshot, phase_e=snapshot)))
        second = replace(source, input_index=2, selection=replace(source.selection,
            evidence=replace(source.selection.evidence, phase_d=snapshot, phase_e=None)))
        fixture = replace(raw, traces=(raw.traces[0], first, second))
        self.assertEqual(execution._oracle_b_coverage(fixture, arm, True).applicable,
                         ((1, "D"), (1, "E"), (2, "D")))

    def test_unselected_retains_raw_applicability_without_oracle_children_or_calls(self):
        work = replace(self.work, oracle_b_selected=False)
        with _literal_context(work), patch.object(audit, "_oracle_b",
                side_effect=AssertionError("Unselected Oracle-B invoked")):
            primary = execution.execute_primary(work)
            repeat = execution.execute_repeat(work, primary)
        for bundle, prefix in ((primary, ""), (repeat, "repeat_")):
            coverage, = _streams(bundle)[prefix + "oracle_b_coverage"]
            self.assertFalse(coverage.selected)
            self.assertTrue(coverage.applicable)
            self.assertEqual(_streams(bundle)[prefix + "oracle_b_audits"], ())

    def test_primary_and_repeat_independently_bind_raw_phase_coverage(self):
        for (bundle, kind, prefix), raw in zip(self._cases(), self.raw_results):
            with self.subTest(kind=kind):
                parts = _streams(bundle)
                coverage, = parts[prefix + "oracle_b_coverage"]
                expected = tuple((t.input_index, phase) for t in raw.traces[1:] if t.selection is not None
                    for phase, state in (("D", t.selection.evidence.phase_d), ("E", t.selection.evidence.phase_e))
                    if state is not None)
                self.assertEqual(coverage.applicable, expected)
                self.assertEqual(coverage.arm, execution.restore_projection(bundle, prefix + "kp0").arm)
                self.assertEqual(expected, tuple((v.action_ordinal, v.phase) for v in parts[prefix + "oracle_b_audits"]))
                self.assertIs(execution.revalidate_bundle(bundle, self.work, kind), bundle)
        first = _streams(self.primary)["oracle_b_coverage"][0]
        repeat = _streams(self.repeat)["repeat_oracle_b_coverage"][0]
        self.assertNotEqual(first.arm.unit_id, repeat.arm.unit_id)
        with self.assertRaisesRegex(ValueError, "COVERAGE_IDENTITY"):
            execution.revalidate_bundle(_replace_stream(self.repeat, "repeat_oracle_b_coverage", (first,)),
                                        self.work, execution.WorkerKind.DETERMINISM)

    def test_producer_coverage_is_not_derived_from_omitted_i5_children(self):
        accepted = audit.audit_k_p0
        def drop_children(*args, **kwargs):
            value = accepted(*args, **kwargs)
            self.assertTrue(value.oracle_b_audits)
            return replace(value, oracle_b_audits=())
        with _literal_context(self.work), patch.object(audit, "audit_k_p0", side_effect=drop_children):
            with self.assertRaisesRegex(ValueError, "ORACLE_B_COVERAGE_MISMATCH"):
                execution.execute_primary(self.work)
            with self.assertRaisesRegex(ValueError, "ORACLE_B_COVERAGE_MISMATCH"):
                execution.execute_repeat(self.work, self.primary)

    def test_parent_rejects_absent_duplicate_unbound_or_misselected_coverage(self):
        for bundle, kind, prefix in self._cases():
            name = prefix + "oracle_b_coverage"
            coverage, = _streams(bundle)[name]
            bad_records = ((), (coverage, coverage),
                (replace(coverage, arm=replace(coverage.arm, unit_id="wrong-unit")),),
                (replace(coverage, selected=False),))
            candidates = [_replace_stream(bundle, name, values) for values in bad_records]
            candidates.append(replace(bundle, streams=tuple(item for item in bundle.streams if item[0] != name)))
            for candidate in candidates:
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    execution.revalidate_bundle(candidate, self.work, kind)

    def test_parent_rejects_dropped_extra_duplicate_wrong_phase_and_ordinal_children(self):
        for bundle, kind, prefix in self._cases():
            name = prefix + "oracle_b_audits"
            children = _streams(bundle)[name]
            self.assertTrue(children)
            first = children[0]
            malformed = ((), children[1:], children + (first,), (first,) + children,
                (replace(first, phase="E" if first.phase == "D" else "D"),) + children[1:],
                (replace(first, action_ordinal=first.action_ordinal + 100),) + children[1:])
            for values in malformed:
                with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "ORACLE_B_COVERAGE"):
                    execution.revalidate_bundle(_replace_stream(bundle, name, values), self.work, kind)

    def test_parent_rejects_reordered_children_and_jointly_out_of_range_keys(self):
        for bundle, kind, prefix in self._cases():
            parts = _streams(bundle)
            coverage, = parts[prefix + "oracle_b_coverage"]
            child = parts[prefix + "oracle_b_audits"][0]
            d, e = replace(child, phase="D"), replace(child, phase="E")
            chronological = replace(coverage, applicable=((child.action_ordinal, "D"), (child.action_ordinal, "E")))
            candidate = _replace_stream(bundle, prefix + "oracle_b_coverage", (chronological,))
            candidate = _replace_stream(candidate, prefix + "oracle_b_audits", (e, d))
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "ORACLE_B_COVERAGE"):
                execution.revalidate_bundle(candidate, self.work, kind)
            impossible = replace(coverage, applicable=((9999, "D"),))
            candidate = _replace_stream(bundle, prefix + "oracle_b_coverage", (impossible,))
            candidate = _replace_stream(candidate, prefix + "oracle_b_audits", (replace(d, action_ordinal=9999),))
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "COVERAGE_BOUNDARY"):
                execution.revalidate_bundle(candidate, self.work, kind)

    def test_parent_rejects_any_child_on_unselected_primary_and_repeat(self):
        work = replace(self.work, oracle_b_selected=False)
        with _literal_context(work):
            primary = execution.execute_primary(work)
            repeat = execution.execute_repeat(work, primary)
        child = _streams(self.primary)["oracle_b_audits"][0]
        for bundle, kind, prefix in ((primary, execution.WorkerKind.PRIMARY, ""),
                                     (repeat, execution.WorkerKind.DETERMINISM, "repeat_")):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "UNSELECTED_ORACLE"):
                execution.revalidate_bundle(_replace_stream(bundle, prefix + "oracle_b_audits", (child,)), work, kind)


class DeterminismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = _literal_work()
        with _literal_context(cls.work):
            cls.first = execution.execute_primary(cls.work)
            cls.repeat = execution.execute_repeat(cls.work, cls.first)

    def test_selected_repeat_runs_both_fresh_arms_with_new_transport_identity(self):
        with _literal_context(self.work), patch.object(runner, "run_control_capture", wraps=runner.run_control_capture) as c, \
                patch.object(runner, "run_k_p0", wraps=runner.run_k_p0) as k, \
                patch.object(audit, "compare_determinism", wraps=audit.compare_determinism) as compared:
            result = execution.execute_repeat(self.work, self.first)
        self.assertEqual((c.call_count, k.call_count), (1, 1))
        self.assertGreaterEqual(compared.call_count, 1)
        for name in ("control", "kp0"):
            first, repeat = execution.restore_projection(result, name), execution.restore_projection(result, "repeat_" + name)
            self.assertNotEqual(first.arm.unit_id, repeat.arm.unit_id)
            self.assertEqual(first.arm.board, repeat.arm.board)
            self.assertEqual(first.physical_inputs, repeat.physical_inputs)
        self.assertIs(result.status, records.AuditStatus.PASS)

    def test_nonselected_repeat_never_materializes_or_executes(self):
        with patch.object(execution, "_materialize_board", side_effect=AssertionError("Not selected")), \
                patch.object(runner, "run_k_p0", side_effect=AssertionError("Not selected")):
            self.assertIsNone(execution.execute_repeat(replace(self.work, determinism_selected=False), None))

    def test_full_first_repeat_premises_include_decision_spans_and_canonical_summaries(self):
        parts = _streams(self.repeat)
        for role in ("control", "kp0", "repeat_control", "repeat_kp0"):
            for component in ("arms", "physical_inputs", "public_effects", "terminal_effects", "decision_spans",
                              "decisions", "guess_checkpoints", "acquisitions"):
                self.assertIn(role + "_" + component, parts)
            self.assertTrue(parts[role + "_decision_spans"])
        for role in ("control", "kp0"):
            summary, = parts[role + "_determinism"]
            self.assertIs(type(summary), records.DeterminismAuditRecord)
            self.assertIs(summary.status, records.AuditStatus.PASS)
        for name, values in self.first.streams:
            if name.startswith(("control_", "kp0_")):
                self.assertEqual(dict(self.repeat.streams)[name], values)

    def test_duration_noise_excluded_but_span_scope_is_semantic(self):
        parts = _streams(self.repeat)
        for role in ("control", "kp0"):
            first = execution.restore_projection(self.repeat, role)
            repeated = execution.restore_projection(self.repeat, "repeat_" + role)
            changed = replace(repeated, decision_spans=tuple(replace(s, duration_ns=1234567)
                                                            for s in repeated.decision_spans),
                              comparable_compute_ns=1234567 * len(repeated.decision_spans))
            if role == "kp0":
                summary = audit.compare_determinism(first, changed, selected=True)
            else:
                summary = execution._control_determinism(first, changed,
                    dict(self.repeat.streams)["control_maintenance"], dict(self.repeat.streams)["repeat_control_maintenance"])
            self.assertIs(summary.status, records.AuditStatus.PASS)
        missing = _replace_stream(self.repeat, "repeat_kp0_decision_spans", ())
        with self.assertRaises(ValueError):
            execution.revalidate_bundle(missing, self.work, execution.WorkerKind.DETERMINISM)


class KControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = _literal_work()
        cls.table = load_timing_table()
        with _literal_context(cls.work):
            cls.primary = execution.execute_primary(cls.work)
            cls.actual = execution.execute_k_control(cls.work, cls.primary)

    def test_kcontrol_arm_end_immediately_follows_runner_before_projection(self):
        events = []
        accepted_run, accepted_project = runner.run_k_control, execution.project_k_control
        def observe(name, arm):
            if name in ("ARM_START", "ARM_END"):
                events.append(name)
                self.assertEqual(arm, "K_CONTROL")
        def run(*args, **kwargs):
            value = accepted_run(*args, **kwargs)
            events.append("RUNNER_RETURN")
            return value
        def project(*args, **kwargs):
            self.assertEqual(events, ["ARM_START", "RUNNER_RETURN", "ARM_END"])
            events.append("PROJECT")
            return accepted_project(*args, **kwargs)
        with _literal_context(self.work), patch.object(runner, "run_k_control", side_effect=run), \
                patch.object(execution, "project_k_control", side_effect=project):
            result = execution.execute_k_control(self.work, self.primary, observer=observe)
        self.assertEqual(events, ["ARM_START", "RUNNER_RETURN", "ARM_END", "PROJECT"])
        self.assertIs(result.status, records.AuditStatus.PASS)

    def test_selected_calls_existing_runner_nonselected_calls_nothing(self):
        with _literal_context(self.work), patch.object(runner, "run_k_control", wraps=runner.run_k_control) as called:
            result = execution.execute_k_control(self.work, self.primary)
        called.assert_called_once()
        self.assertIs(result.kind, execution.WorkerKind.K_CONTROL)
        self.assertIs(result.status, records.AuditStatus.PASS)
        with patch.object(execution, "_materialize_board", side_effect=AssertionError("Not selected")), \
                patch.object(runner, "run_k_control", side_effect=AssertionError("Not selected")):
            self.assertIsNone(execution.execute_k_control(replace(self.work, k_control_selected=False), None))

    def test_full_o4_p5_evidence_and_final_checkpoint_are_detached(self):
        parts = _streams(self.actual)
        reference, actual = parts["control_maintenance"], parts["kcontrol_maintenance"]
        self.assertEqual(len(reference), len(actual))
        for expected, item in zip(reference, actual):
            self.assertEqual(execution._control_identity(expected), execution._control_identity(item))
            self.assertIs(item.arm.arm, records.Arm.K_CONTROL)
            self.assertIs(type(item), records.KControlMaintenanceRecord)
            self.assertEqual(records.decode(records.encode(item)), item)
            if item.physical.action_ordinal:
                self.assertIsNotNone(item.v1_decision)
                self.assertTrue(item.shadow.evidence_valid)
                self.assertEqual(item.shadow.last_valid_boundary, item.physical.action_ordinal)
                self.assertIsNotNone(item.shadow.decision)
        final = actual[-1].final_shadow
        self.assertFalse(final.evidence_valid)
        self.assertIsNone(final.decision)
        self.assertEqual(final.last_valid_M, actual[-1].shadow.last_valid_M)
        self.assertNotIn("pairs", parts)
        self.assertNotIn("kp0_decision_spans", parts)

    def test_exception_failure_keeps_control_stream_incomplete_and_sanitizes_detail(self):
        with _literal_context(self.work), patch.object(runner, "_analyze_shadow",
                side_effect=RuntimeError("PRIVATE_SENTINEL {(99, 88)}")):
            result = execution.execute_k_control(self.work, self.primary)
        self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
        self.assertNotIn(b"PRIVATE_SENTINEL", execution.encode_bundle(result))
        actual = _streams(result)["kcontrol_maintenance"]
        self.assertTrue(any(item.shadow.failure for item in actual))
        self.assertTrue(all(item.shadow.decision is None for item in actual if item.shadow.failure))
        self.assertEqual(tuple(v.physical for v in actual), tuple(v.physical for v in _streams(self.primary)["control_maintenance"]))

    def test_shadow_timeout_is_incomplete_with_valid_sealed_control_and_no_live_test_thread(self):
        release, entered, threads = threading.Event(), threading.Event(), []
        def stalled(_):
            threads.append(threading.current_thread())
            entered.set()
            release.wait(1)
            raise RuntimeError("Discarded late shadow result")
        try:
            with _literal_context(self.work), patch.object(runner, "_analyze_shadow", side_effect=stalled):
                result = execution.execute_k_control(self.work, self.primary, shadow_timeout_ms=5)
            self.assertTrue(entered.is_set())
            self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
            actual = _streams(result)["kcontrol_maintenance"]
            failures = [dict(v.shadow.failure) for v in actual if v.shadow.failure]
            self.assertTrue(failures)
            self.assertTrue(all(v["failure_class"] == "SHADOW_TIMEOUT" for v in failures))
            self.assertEqual(tuple(v.physical for v in actual),
                             tuple(v.physical for v in _streams(self.primary)["control_maintenance"]))
        finally:
            release.set()
            for thread in threads:
                thread.join(timeout=1)
                self.assertFalse(thread.is_alive())

    def test_diagnosed_shadow_soundness_violation_remains_fail(self):
        with _literal_context(self.work), patch.object(runner, "_analyze_shadow",
                side_effect=runner.ShadowSoundnessViolation("Synthetic diagnosed contradiction")):
            result = execution.execute_k_control(self.work, self.primary)
        self.assertIs(result.status, records.AuditStatus.FAIL)
        self.assertIn("SHADOW_IMPLEMENTATION_IDENTITY_FAIL", result.reason_codes)
        actual = _streams(result)["kcontrol_maintenance"]
        self.assertTrue(any(v.classification == "IMPLEMENTATION_IDENTITY_FAIL" for v in actual))

    def test_uncertain_guesses_and_terminal_effects_keep_exact_o4_premises(self):
        mines = frozenset({(1, 0), (2, 0)})
        work = _literal_work(42_424_243, width=5, mines=mines)
        with _literal_context(work, mines):
            primary = execution.execute_primary(work)
            actual = execution.execute_k_control(work, primary)
        parts = _streams(actual)
        self.assertTrue(any(v.guess_checkpoint is not None for v in parts["kcontrol_maintenance"]))
        self.assertEqual(execution.compare_k_control(parts["control_maintenance"], parts["kcontrol_maintenance"]),
                         (records.AuditStatus.PASS, ()))
        for value in parts["kcontrol_maintenance"]:
            if value.guess_checkpoint is not None:
                self.assertEqual(value.guess_checkpoint.chosen_target, value.physical.target)
                self.assertEqual(value.v1_decision.evidence_kind, "PROBABILITY_GUESS")
        self.assertIsNotNone(parts["kcontrol_maintenance"][-1].terminal_effect)

    def test_raw_final_checkpoint_mismatch_is_not_admitted(self):
        owner = execution._BoardOwner(self.work.board, frozenset({(1, 0)}))
        port = execution._fresh_engine(owner, 20, None, None, "K_CONTROL")
        raw = runner.run_k_control(port, table=self.table, capture_effects=True)
        bad = replace(raw, shadow=replace(raw.shadow, evidence_valid=True))
        with self.assertRaisesRegex(ValueError, "FINAL_SHADOW"):
            execution.project_k_control(bad, execution._arm(self.work, records.Arm.K_CONTROL), table=self.table)

    def test_missing_guess_premises_are_incomplete_not_a_semantic_failure(self):
        owner = execution._BoardOwner(self.work.board, frozenset({(1, 0)}))
        raw = runner.run_k_control(execution._fresh_engine(owner, 20, None, None, "K_CONTROL"),
                                   table=self.table, capture_effects=True)
        with patch.object(game, "_control_checkpoints", return_value=((), True)):
            with self.assertRaisesRegex(execution.E2EvidenceIncomplete, "EVIDENCE_INCOMPLETE"):
                execution.project_k_control(raw, execution._arm(self.work, records.Arm.K_CONTROL), table=self.table)

    def test_stale_raw_shadow_decision_is_detached_not_accepted_as_current(self):
        owner = execution._BoardOwner(self.work.board, frozenset({(1, 0)}))
        raw = runner.run_k_control(execution._fresh_engine(owner, 20, None, None, "K_CONTROL"),
                                   table=self.table, capture_effects=True)
        current = next(t for t in raw.traces if t.shadow.evidence_valid)
        stale = replace(current.shadow, evidence_valid=False)
        projected = execution._shadow_state(stale, current.input_index)
        self.assertFalse(projected.evidence_valid)
        self.assertIsNone(projected.decision)

    def test_o4_identity_mismatch_cannot_become_pass(self):
        parts = _streams(self.actual)
        actual = parts["kcontrol_maintenance"]
        item = actual[-1]
        changed = replace(item, physical=replace(item.physical, input_us=item.physical.input_us + 1,
                                                 cumulative_us=item.physical.cumulative_us + 1))
        status, reasons = execution.compare_k_control(parts["control_maintenance"], actual[:-1] + (changed,))
        self.assertIs(status, records.AuditStatus.FAIL)
        self.assertIn("KCONTROL_IMPLEMENTATION_IDENTITY_FAIL", reasons)

    def test_missing_public_premise_is_incomplete_while_present_contradiction_still_fails(self):
        parts = _streams(self.actual)
        actual = parts["kcontrol_maintenance"]
        missing = replace(actual[0], public_effect=None, classification="INCOMPLETE")
        status, _ = execution.compare_k_control(parts["control_maintenance"], (missing,) + actual[1:])
        self.assertIs(status, records.AuditStatus.INCOMPLETE)
        last = actual[-1]
        changed = replace(last, physical=replace(last.physical, input_us=last.physical.input_us + 1,
                                                 cumulative_us=last.physical.cumulative_us + 1))
        status, _ = execution.compare_k_control(parts["control_maintenance"], (missing,) + actual[1:-1] + (changed,))
        self.assertIs(status, records.AuditStatus.FAIL)


class ImportBoundaryTests(unittest.TestCase):
    def test_execution_import_has_no_operational_effect(self):
        with ExitStack() as stack:
            for target in ("benchmark_board.generate_board", "stage3_physical.load_timing_table",
                           "experiments.program_k_runner.run_control_capture",
                           "experiments.program_k_runner.run_k_p0", "experiments.program_k_runner.run_k_control",
                           "multiprocessing.Process.start", "threading.Thread.start", "os.getenv"):
                stack.enter_context(patch(target, side_effect=AssertionError("Import side effect: " + target)))
            namespace = runpy.run_path(execution.__file__)
        self.assertIn("execute_primary", namespace)

    def test_dependencies_and_watchdog_targets_preserve_frozen_boundaries(self):
        tree = ast.parse(Path(execution.__file__).read_text(encoding="utf-8"))
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        imports += [name.name for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names]
        self.assertFalse(any(any(word in name for word in ("program_k_e1", "e2_report", "e2_analysis", "PyQt", "sqlite", "zini"))
                             for name in imports))
        codes, regions = execution.decision_watchdog_targets()
        self.assertIn(execution.stage3_planner.plan_position.__code__, codes)
        self.assertIn(execution.capability.KLocalSession.analyze_decision.__code__, codes)
        self.assertIn(execution.policy.select_policy.__code__, codes)
        self.assertEqual(len(regions), 1)
        self.assertIs(regions[0][0], runner.run_k_p0.__code__)
        self.assertLess(regions[0][1], regions[0][2])
        source = inspect.getsource(execution.decision_watchdog_targets)
        self.assertNotIn("settrace", source)
        self.assertNotIn("setprofile", source)


class PersistencePremiseTests(unittest.TestCase):
    def test_real_literal_bundles_roundtrip_all_i2_component_streams(self):
        from experiments import program_k_e2_operational as op
        from experiments import program_k_e2_store as store
        from tests.test_program_k_e2_operational import _envelope
        work = _literal_work()
        with _literal_context(work):
            primary = execution.execute_primary(work)
            repeat = execution.execute_repeat(work, primary)
            kcontrol = execution.execute_k_control(work, primary)
        with tempfile.TemporaryDirectory(prefix="i6-literal-components-") as directory:
            sink = op._EvidenceSink(directory, _envelope(), 3)
            expected = {}
            try:
                for rank, bundle in enumerate((primary, repeat, kcontrol)):
                    receipt = op.UnitReceipt(0, bundle.kind, bundle.status, "ADMITTED", 1, 0)
                    sink.admit(op._OperationResult(receipt, bundle, ()))
                    for name, values in bundle.streams:
                        expected.setdefault(name, []).extend(((0, rank, index), data)
                                                             for index, data in enumerate(values))
                digests = sink.seal()
                for name, values in expected.items():
                    actual = []
                    checked = store.scan_stream(directory, name,
                        visit=lambda key, value: actual.append((key, records.encode(value))))
                    self.assertEqual(actual, values, name)
                    self.assertEqual(checked, next(value for value in digests if value.name == name))
                self.assertEqual(sink.durable_units, 3)
                self.assertEqual(sink.durable_boards, 1)
                self.assertTrue(expected["kp0_decision_spans"])
                self.assertTrue(expected["repeat_kp0_decision_spans"])
                self.assertTrue(expected["oracle_b_coverage"])
                self.assertTrue(expected["repeat_oracle_b_coverage"])
                self.assertTrue(expected["kcontrol_maintenance"])
                self.assertFalse(any(path.name.startswith("complete") for path in Path(directory).iterdir()))
            finally:
                sink.close()


class WB02PrimitiveTests(unittest.TestCase):
    """Bounded canonical transport fixtures; no runner or board generation."""

    profile = b"\xa3" * 32

    @staticmethod
    def _bundle(text='literal "quote" \\ path', *, position=128, kind=execution.WorkerKind.PRIMARY):
        board = records.encode(records.BoardIdentity(42_424_242, "fixture", 4, 1, 1,
                                                     (0, 0), text, "WB02-test"))
        runtime = records.encode(records.RuntimeIdentity(text, "test", "test", "test", "test", None))
        header = execution.ProjectionHeader("control", "WIN", 7, None, True, False, True,
                                            ('diagnostic "x" \\ y',))
        return execution.WorkerBundle(position, kind, board, identity.ArmOrder.CONTROL_THEN_KP0,
            (("boards", (board,)), ("runtime", (runtime,)), ("oracle_b_audits", ()),
             ("oracle_b_coverage", ())), (header,), records.AuditStatus.PASS, ())

    @staticmethod
    def _parts(data):
        length = int.from_bytes(data[8:16], "big")
        return json.loads(data[16:16 + length]), data[16 + length:-32]

    def _rewrite(self, data, change):
        node, frames = self._parts(data)
        change(node)
        for _ in range(10):
            encoded = json.dumps(node, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=True).encode("ascii")
            total = 48 + len(encoded) + len(frames)
            if node["wire_bytes"] == total:
                break
            node["wire_bytes"] = total
        body = b"PKE2WB02" + len(encoded).to_bytes(8, "big") + encoded + frames
        return body + sha256(body).digest()

    def test_exact_magic_layout_arithmetic_sha_and_determinism(self):
        bundle = self._bundle()
        encoded = execution.encode_bundle_v2(bundle, self.profile)
        node, frames = self._parts(encoded)
        metadata_size = int.from_bytes(encoded[8:16], "big")
        self.assertEqual(encoded[:8], b"PKE2WB02")
        self.assertEqual(len(encoded), 48 + metadata_size + len(frames))
        self.assertEqual(len(encoded), node["wire_bytes"])
        self.assertEqual(node["frame_bytes"], len(frames))
        self.assertEqual(node["logical_bytes"], sum(len(v) for _, values in bundle.streams for v in values))
        self.assertEqual(node["legacy_bytes"], len(execution.encode_bundle(bundle)))
        self.assertEqual(encoded[-32:], sha256(encoded[:-32]).digest())
        self.assertEqual(encoded, execution.encode_bundle_v2(bundle, self.profile))
        self.assertEqual(encoded[16:16 + metadata_size],
                         json.dumps(node, sort_keys=True, separators=(",", ":")).encode("ascii"))

    def test_ordered_groups_keys_and_zero_row_oracle_have_no_filler(self):
        from experiments import program_k_e2_physical as physical
        for kind, rank in ((execution.WorkerKind.PRIMARY, 0), (execution.WorkerKind.DETERMINISM, 1),
                           (execution.WorkerKind.K_CONTROL, 2)):
            bundle = self._bundle(position=identity.UINT64_MAX, kind=kind)
            data = execution.encode_bundle_v2(bundle, self.profile)
            node, frames = self._parts(data)
            self.assertEqual(tuple(g[0] for g in node["streams"]), tuple(n for n, _ in bundle.streams))
            self.assertEqual(node["streams"][-2:], [["oracle_b_audits", 0, 0, 0],
                                                    ["oracle_b_coverage", 0, 0, 0]])
            offset = 0
            for name, values in bundle.streams:
                for index, logical in enumerate(values):
                    decoded, offset = physical.decode_frame_from(frames, offset,
                        physical.context_for(name, self.profile),
                        expected_key=(identity.UINT64_MAX, rank, index))
                    self.assertEqual(decoded.logical_bytes, logical)
            self.assertEqual(offset, len(frames))
            self.assertEqual(execution.decode_bundle_v2(data, self.profile), bundle)

    def test_no_logical_json_string_reembedding_and_immutable_result(self):
        bundle = self._bundle()
        data = execution.encode_bundle_v2(bundle, self.profile)
        node, _ = self._parts(data)
        self.assertNotIn("board", node)
        metadata = data[16:16 + int.from_bytes(data[8:16], "big")]
        for _, values in bundle.streams:
            for value in values:
                self.assertNotIn(json.dumps(value.decode("ascii")).encode("ascii"), metadata)
        decoded = execution.decode_bundle_v2(data, self.profile)
        self.assertIs(type(decoded), execution.WorkerBundle)
        self.assertIs(type(decoded.streams), tuple)
        self.assertTrue(all(type(value) is bytes for _, values in decoded.streams for value in values))
        with self.assertRaises(FrozenInstanceError):
            decoded.work_position = 3
        for function in (execution.encode_bundle_v2, execution.decode_bundle_v2):
            self.assertFalse(any("validat" in name for name in inspect.signature(function).parameters))
        with self.assertRaises(TypeError):
            execution.decode_bundle_v2(data, self.profile, validated=True)

    def test_corrupted_metadata_group_or_digest_rejected(self):
        data = execution.encode_bundle_v2(self._bundle(), self.profile)
        metadata_size = int.from_bytes(data[8:16], "big")
        for offset in (16, 16 + metadata_size + 10, len(data) - 1):
            bad = bytearray(data)
            bad[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_v2(bytes(bad), self.profile)
        # A correct outer digest must not conceal a corrupt RF02 group.
        bad = bytearray(data[:-32])
        bad[16 + metadata_size + 10] ^= 1
        with self.assertRaises(execution.E2ExecutionError):
            execution.decode_bundle_v2(bytes(bad) + sha256(bad).digest(), self.profile)

    def test_all_message_truncations_and_trailing_garbage_rejected(self):
        data = execution.encode_bundle_v2(self._bundle(), self.profile)
        for length in range(len(data)):
            with self.subTest(length=length), self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_v2(data[:length], self.profile)
        for bad in (data + b"x", data[:-32] + b"x" + sha256(data[:-32] + b"x").digest()):
            with self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_v2(bad, self.profile)

    def test_closed_metadata_rejects_unknown_missing_float_and_noncanonical(self):
        data = execution.encode_bundle_v2(self._bundle(), self.profile)
        changes = (lambda n: n.update(extra=0), lambda n: n.pop("legacy_bytes"),
                   lambda n: n.update(position=1.0), lambda n: n.update(position=True),
                   lambda n: n.update(position=float("nan")))
        for change in changes:
            with self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_v2(self._rewrite(data, change), self.profile)
        node, frames = self._parts(data)
        for metadata in (json.dumps(node, sort_keys=True).encode("ascii"),
                         b'{"position":128,' + data[17:16 + int.from_bytes(data[8:16], "big")]):
            body = b"PKE2WB02" + len(metadata).to_bytes(8, "big") + metadata + frames
            with self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_v2(body + sha256(body).digest(), self.profile)

    def test_profile_size_basis_container_identity_mixing_rejected(self):
        data = execution.encode_bundle_v2(self._bundle(), self.profile)
        for key, value in (("container", "PKE2WB01"), ("size_basis", "legacy"),
                           ("codec_profile_sha256", "00" * 32)):
            with self.subTest(key=key), self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_v2(self._rewrite(data, lambda n: n.update({key: value})), self.profile)
        with self.assertRaises(execution.E2ExecutionError):
            execution.decode_bundle_v2(data, b"\x00" * 32)
        with self.assertRaises(execution.E2ExecutionError):
            execution.decode_bundle_v2(execution.encode_bundle(self._bundle()), self.profile)
        with self.assertRaises(execution.E2ExecutionError):
            execution.decode_bundle(data)

    def test_declared_counts_order_sizes_and_frame_keys_rejected(self):
        data = execution.encode_bundle_v2(self._bundle(), self.profile)
        changes = (lambda n: n["streams"][0].__setitem__(1, 2),
                   lambda n: n["streams"][0].__setitem__(1, True),
                   lambda n: n["streams"].reverse(),
                   lambda n: n["streams"].append(n["streams"][-1][:]),
                   lambda n: n["streams"][0].__setitem__(0, "unknown"),
                   lambda n: n.update(logical_bytes=n["logical_bytes"] + 1),
                   lambda n: n.update(legacy_bytes=n["legacy_bytes"] + 1),
                   lambda n: n.update(frame_bytes=n["frame_bytes"] + 1),
                   lambda n: n.update(position=n["position"] + 1),
                   lambda n: n.update(kind="K_CONTROL"))
        for change in changes:
            with self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_v2(self._rewrite(data, change), self.profile)

    def test_bounds_precede_metadata_parse_and_frame_decode(self):
        from experiments import program_k_e2_physical as physical
        data = execution.encode_bundle_v2(self._bundle(), self.profile)
        huge = b"PKE2WB02" + identity.UINT64_MAX.to_bytes(8, "big") + bytes(32)
        with patch.object(json, "loads", side_effect=AssertionError("Must bound before parse")), \
                patch.object(physical, "decode_frame_from", side_effect=AssertionError("Must bound before inflate")):
            for candidate, kwargs in ((huge, {}), (data, {"max_payload_bytes": len(data) - 1}),
                                      (data, {"max_metadata_bytes": 1})):
                with self.assertRaises(execution.E2ExecutionError):
                    execution.decode_bundle_v2(candidate, self.profile, **kwargs)
        with patch.object(execution, "_json", side_effect=AssertionError("Must bound before allocation")):
            with self.assertRaises(execution.E2ExecutionError):
                execution.encode_bundle_v2(self._bundle(), self.profile, max_metadata_bytes=1)

    def test_invalid_limits_mutable_inputs_and_false_authority_rejected(self):
        bundle = self._bundle()
        data = execution.encode_bundle_v2(bundle, self.profile)
        for limit in (True, 0, -1, 67_108_865):
            with self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_v2(data, self.profile, max_payload_bytes=limit)
            with self.assertRaises(execution.E2ExecutionError):
                execution.encode_bundle_v2(bundle, self.profile, max_payload_bytes=limit)
        for bad in (bytearray(data), memoryview(data)):
            with self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_v2(bad, self.profile)
        for digest in ("00" * 32, bytes(31), bytearray(32), True):
            with self.assertRaises(execution.E2ExecutionError):
                execution.encode_bundle_v2(bundle, digest)

    def test_logical_legacy_and_wire_caps_are_independent(self):
        bundle = self._bundle("repeat" * 1024)
        logical_size = sum(len(v) for _, values in bundle.streams for v in values)
        legacy_size = execution.legacy_bundle_size(bundle)
        data = execution.encode_bundle_v2(bundle, self.profile)
        self.assertLess(len(data), logical_size)
        self.assertLess(logical_size, legacy_size)
        with self.assertRaisesRegex(execution.E2ExecutionError, "PAYLOAD_CAP"):
            execution.encode_bundle_v2(bundle, self.profile, max_payload_bytes=logical_size - 1)
        with self.assertRaisesRegex(execution.E2ExecutionError, "LEGACY_CAP"):
            execution.encode_bundle_v2(bundle, self.profile, max_payload_bytes=logical_size)
        with self.assertRaisesRegex(execution.E2ExecutionError, "DECLARED_SIZE_CAP"):
            execution.decode_bundle_v2(data, self.profile, max_payload_bytes=logical_size)
        sparse = self._bundle("x")
        sparse = replace(sparse, projection_headers=(), streams=tuple(
            (name, (sparse.board,) if name == "boards" else ()) for name in execution.STREAM_NAMES))
        wire = execution.encode_bundle_v2(sparse, self.profile)
        self.assertLess(execution.legacy_bundle_size(sparse), len(wire) - 1)
        with self.assertRaisesRegex(execution.E2ExecutionError, "WIRE_CAP"):
            execution.encode_bundle_v2(sparse, self.profile, max_payload_bytes=len(wire) - 1)

    def test_writer_rejects_mismatched_board_and_noncanonical_or_wrong_family(self):
        bundle = self._bundle()
        other = self._bundle("other")
        for candidate in (replace(bundle, board=other.board),
                          replace(bundle, streams=(("boards", (bundle.board + b" ",)),)),
                          replace(bundle, streams=(("boards", (bundle.board,)), ("runtime", (bundle.board,))))):
            with self.assertRaises(ValueError):
                execution.encode_bundle_v2(candidate, self.profile)

    def test_legacy_counter_exact_for_adversarial_valid_records_and_duplication(self):
        for text in ('x', '"' * 63, "\\" * 64, 'quote"slash\\' * 31,
                     "Korean-한글-emoji-😀", "a" * 4096):
            for kind in execution.WorkerKind:
                bundle = self._bundle(text, position=identity.UINT64_MAX, kind=kind)
                self.assertEqual(execution.legacy_bundle_size(bundle), len(execution.encode_bundle(bundle)))
                without_board_stream = replace(bundle, streams=bundle.streams[1:])
                self.assertEqual(execution.legacy_bundle_size(without_board_stream),
                                 len(execution.encode_bundle(without_board_stream)))
                multiple = replace(bundle, streams=tuple(
                    (name, values * 3 if name == "runtime" else values) for name, values in bundle.streams))
                self.assertEqual(execution.legacy_bundle_size(multiple), len(execution.encode_bundle(multiple)))
                self.assertEqual(execution.decode_bundle_v2(
                    execution.encode_bundle_v2(multiple, self.profile), self.profile), multiple)
                decoded = execution.decode_bundle_v2(execution.encode_bundle_v2(bundle, self.profile), self.profile)
                self.assertEqual(execution.encode_bundle(decoded), execution.encode_bundle(bundle))

    def test_legacy_string_domain_and_exact_quote_backslash_count(self):
        for data in (b"x", b'"', b"\\", bytes(range(32, 127)), b'"\\' * 128):
            self.assertEqual(execution.legacy_json_string_size(data),
                             len(json.dumps(data.decode("ascii"), ensure_ascii=True).encode("ascii")))
        for bad in (b"", b"\x1f", b"\x7f", b"\xff", b"line\n", bytearray(b"x"), "x"):
            with self.assertRaises(execution.E2ExecutionError):
                execution.legacy_json_string_size(bad)
        bundle = self._bundle()
        with self.assertRaises(ValueError):
            execution.legacy_bundle_size(replace(bundle, board=b'{"not":"a record"}'))

    def test_v1_default_encoder_path_remains_explicit_and_unchanged(self):
        bundle = self._bundle()
        with patch.object(execution, "encode_bundle_v2", side_effect=AssertionError("V2 invoked")), \
                patch.object(execution, "decode_bundle_v2", side_effect=AssertionError("V2 invoked")):
            data = execution.encode_bundle(bundle)
            self.assertEqual(execution.decode_bundle(data), bundle)
            self.assertTrue(data.startswith(b"{"))
            self.assertEqual(json.loads(data)["version"], 1)


class WB02DecodeViewTests(unittest.TestCase):
    """Exact representation facts only; no admission, profile capture or runner."""

    profile = WB02PrimitiveTests.profile
    _bundle = staticmethod(WB02PrimitiveTests._bundle)
    _parts = staticmethod(WB02PrimitiveTests._parts)
    _rewrite = WB02PrimitiveTests._rewrite

    def test_view_retains_exact_wire_rows_order_sizes_and_logical_bundle(self):
        from experiments import program_k_e2_physical as physical
        for kind, rank in ((execution.WorkerKind.PRIMARY, 0), (execution.WorkerKind.DETERMINISM, 1),
                           (execution.WorkerKind.K_CONTROL, 2)):
            bundle = self._bundle(position=identity.UINT64_MAX, kind=kind)
            bundle = replace(bundle, streams=tuple(
                (name, values * 3 if name == "runtime" else values) for name, values in bundle.streams))
            wire = execution.encode_bundle_v2(bundle, self.profile)
            node, frames = self._parts(wire)
            view = execution.decode_bundle_view_v2(wire, self.profile)
            with self.subTest(kind=kind):
                self.assertIs(type(view), execution.WB02DecodeView)
                self.assertIs(view.wire, wire)
                self.assertIs(type(view.bundle), execution.WorkerBundle)
                self.assertEqual(view.bundle, bundle)
                self.assertEqual(execution.decode_bundle_v2(wire, self.profile), view.bundle)
                self.assertEqual((view.logical_bytes, view.legacy_bytes, view.frame_bytes, view.wire_bytes),
                                 tuple(node[name] for name in ("logical_bytes", "legacy_bytes", "frame_bytes", "wire_bytes")))
                self.assertEqual(view.metadata_bytes, int.from_bytes(wire[8:16], "big"))
                self.assertEqual(view.wire_bytes, 48 + view.metadata_bytes + view.frame_bytes)
                self.assertEqual(view.legacy_bytes, len(execution.encode_bundle(bundle)))
                expected = [(name, (bundle.work_position, rank, index), logical)
                            for name, values in bundle.streams for index, logical in enumerate(values)]
                self.assertEqual([(row.stream_name, row.key, row.logical_bytes) for row in view.rows], expected)
                self.assertEqual(len(view.rows), sum(group[1] for group in node["streams"]))
                self.assertEqual(sum(len(row.logical_bytes) for row in view.rows), view.logical_bytes)
                self.assertEqual(sum(row.frame_length for row in view.rows), view.frame_bytes)
                self.assertEqual(b"".join(row.frame_bytes for row in view.rows), frames)
                offset = 16 + view.metadata_bytes
                for row in view.rows:
                    decoded, end = physical.decode_frame_from(wire, offset,
                        physical.context_for(row.stream_name, self.profile), expected_key=row.key)
                    self.assertEqual(row.frame_bytes, wire[offset:end])
                    self.assertEqual(row.frame_length, end - offset)
                    self.assertEqual(row.frame_length, len(row.frame_bytes))
                    self.assertEqual(row.logical_bytes, decoded.logical_bytes)
                    self.assertTrue(type(row.frame_bytes) is bytes and type(row.logical_bytes) is bytes)
                    offset = end
                self.assertEqual(offset, len(wire) - 32)

    def test_rich_decode_parses_metadata_and_each_frame_once_without_reencoding(self):
        from experiments import program_k_e2_physical as physical
        bundle = self._bundle()
        wire = execution.encode_bundle_v2(bundle, self.profile)
        metadata = wire[16:16 + int.from_bytes(wire[8:16], "big")].decode("ascii")
        real_loads = json.loads
        metadata_calls = []
        def observe_loads(data, *args, **kwargs):
            if data == metadata:
                metadata_calls.append(data)
            return real_loads(data, *args, **kwargs)
        with patch.object(execution.json, "loads", side_effect=observe_loads), \
                patch.object(physical, "decode_frame_from", wraps=physical.decode_frame_from) as decoded, \
                patch.object(physical, "encode_frame", side_effect=AssertionError("RF02 re-encoding forbidden")), \
                patch.object(execution, "decode_bundle_v2", side_effect=AssertionError("Logical-first double parse")):
            view = execution.decode_bundle_view_v2(wire, self.profile)
        self.assertEqual(metadata_calls, [metadata])
        self.assertEqual(decoded.call_count, len(view.rows))
        self.assertTrue(all(call.args[0] is wire for call in decoded.call_args_list))
        self.assertEqual(view.bundle, bundle)

    def test_both_entry_points_delegate_to_one_shared_decoder(self):
        bundle = self._bundle()
        wire = execution.encode_bundle_v2(bundle, self.profile)
        decoder = execution._decode_bundle_v2
        for function in (execution.decode_bundle_v2, execution.decode_bundle_view_v2):
            with self.subTest(function=function.__name__), \
                    patch.object(execution, "_decode_bundle_v2", wraps=decoder) as shared:
                result = function(wire, self.profile, max_payload_bytes=8192, max_metadata_bytes=4096)
            shared.assert_called_once_with(wire, self.profile, max_payload_bytes=8192, max_metadata_bytes=4096)
            self.assertEqual(result if type(result) is execution.WorkerBundle else result.bundle, bundle)
        self.assertEqual(tuple(inspect.signature(execution.decode_bundle_v2).parameters),
                         ("data", "codec_profile_sha256", "max_payload_bytes", "max_metadata_bytes"))

    def test_rich_view_and_rows_are_frozen_representation_not_authority(self):
        wire = execution.encode_bundle_v2(self._bundle(), self.profile)
        view = execution.decode_bundle_view_v2(wire, self.profile)
        self.assertIs(type(view.rows), tuple)
        self.assertFalse(hasattr(view, "__dict__"))
        self.assertFalse(hasattr(view.rows[0], "__dict__"))
        for value in (view, view.rows[0]):
            self.assertFalse({"validated", "trusted", "admitted", "qualified", "admission"}.intersection(dir(value)))
        with self.assertRaises(FrozenInstanceError):
            view.wire = b"forged"
        with self.assertRaises(FrozenInstanceError):
            view.rows[0].frame_bytes = b"forged"
        for candidate in (view, replace(view, wire=b"forged"), view.bundle, True, sha256(wire).digest()):
            with self.subTest(candidate=type(candidate)), self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_view_v2(candidate, self.profile)
        with self.assertRaises(TypeError):
            execution.decode_bundle_view_v2(wire, self.profile, validated=True)

    def test_rich_decode_rejects_mutability_profile_and_bounds_before_parsing(self):
        wire = execution.encode_bundle_v2(self._bundle(), self.profile)
        with patch.object(execution.json, "loads", side_effect=AssertionError("Invalid input reached metadata parser")):
            for candidate in (bytearray(wire), memoryview(wire)):
                with self.assertRaises(execution.E2ExecutionError):
                    execution.decode_bundle_view_v2(candidate, self.profile)
            for profile in (bytearray(self.profile), bytes(31), "a" * 64, True):
                with self.assertRaises(execution.E2ExecutionError):
                    execution.decode_bundle_view_v2(wire, profile)
            for limits in ({"max_payload_bytes": True}, {"max_payload_bytes": len(wire) - 1},
                           {"max_metadata_bytes": 1}, {"max_metadata_bytes": 0}):
                with self.assertRaises(execution.E2ExecutionError):
                    execution.decode_bundle_view_v2(wire, self.profile, **limits)
        with self.assertRaises(execution.E2ExecutionError):
            execution.decode_bundle_view_v2(wire, b"\x00" * 32)

    def test_rich_decode_fails_closed_for_sha_metadata_crc_truncation_and_group_sizes(self):
        wire = execution.encode_bundle_v2(self._bundle(), self.profile)
        metadata_size = int.from_bytes(wire[8:16], "big")
        candidates = [("SHA", wire[:-1] + bytes((wire[-1] ^ 1,))), ("truncation", wire[:-33])]
        bad_metadata = bytearray(wire[:-32])
        bad_metadata[16] = ord("!")
        candidates.append(("metadata", bytes(bad_metadata) + sha256(bad_metadata).digest()))
        node, _ = self._parts(wire)
        bad_crc = bytearray(wire[:-32])
        bad_crc[16 + metadata_size + node["streams"][0][3] - 1] ^= 1
        candidates.append(("CRC with correct outer SHA", bytes(bad_crc) + sha256(bad_crc).digest()))
        def shift_group_sizes(node):
            node["streams"][0][3] -= 1
            node["streams"][1][3] += 1
        candidates.append(("group boundary", self._rewrite(wire, shift_group_sizes)))
        truncated_body = wire[:-33]  # Remove one physical CRC byte before re-signing the container.
        def shorten_last_frame(node):
            node["frame_bytes"] -= 1
            next(group for group in reversed(node["streams"]) if group[1])[3] -= 1
        candidates.append(("frame truncation with corrected sizes and SHA", self._rewrite(
            truncated_body + sha256(truncated_body).digest(), shorten_last_frame)))
        for label, candidate in candidates:
            with self.subTest(corruption=label), self.assertRaises(execution.E2ExecutionError):
                execution.decode_bundle_view_v2(candidate, self.profile)


class WB02CachedCompositionTests(unittest.TestCase):
    """Cached slices remain untrusted inputs to a shared representation composer."""

    profile = WB02PrimitiveTests.profile
    _bundle = staticmethod(WB02PrimitiveTests._bundle)
    _parts = staticmethod(WB02PrimitiveTests._parts)

    def _view(self, bundle):
        return execution.decode_bundle_view_v2(execution.encode_bundle_v2(bundle, self.profile), self.profile)

    def test_exact_cached_composition_matches_full_encoder_for_all_ranks_and_keys(self):
        from experiments import program_k_e2_physical as physical
        for kind in execution.WorkerKind:
            for position in (0, 9999, identity.UINT64_MAX):
                bundle = self._bundle('quote"slash\\' * 20, kind=kind, position=position)
                view = self._view(bundle)
                with patch.object(physical, "encode_frame", side_effect=AssertionError("Cached row recompressed")):
                    wire = execution._compose_bundle_v2_from_rows(bundle, self.profile, view.rows)
                self.assertEqual(wire, view.wire)
                self.assertEqual(execution.decode_bundle_v2(wire, self.profile), bundle)
                self.assertEqual(self._parts(wire)[0]["streams"][-2:],
                                 [["oracle_b_audits", 0, 0, 0], ["oracle_b_coverage", 0, 0, 0]])

    def test_one_changed_row_preserves_exact_other_slices_and_canonical_wire(self):
        from experiments import program_k_e2_physical as physical
        bundle = self._bundle()
        view = self._view(bundle)
        runtime = records.decode(dict(bundle.streams)["runtime"][0])
        changed = records.encode(replace(runtime, python_version="changed " + "x" * 1024))
        candidate = replace(bundle, streams=tuple(
            (name, (changed,) if name == "runtime" else values) for name, values in bundle.streams))
        row = view.rows[1]
        with patch.object(physical, "encode_frame", wraps=physical.encode_frame) as encoded:
            frame = physical.encode_frame(changed, row.key, physical.context_for("runtime", self.profile))
            rows = (view.rows[0], replace(row, logical_bytes=changed, frame_bytes=frame, frame_length=len(frame)))
            wire = execution._compose_bundle_v2_from_rows(candidate, self.profile, rows)
        self.assertEqual(encoded.call_count, 1)
        self.assertIs(rows[0], view.rows[0])
        selected = execution.decode_bundle_view_v2(wire, self.profile)
        self.assertEqual(selected.rows[0].frame_bytes, view.rows[0].frame_bytes)
        self.assertEqual(wire, execution.encode_bundle_v2(candidate, self.profile))
        self.assertEqual((selected.logical_bytes, selected.legacy_bytes, selected.frame_bytes, selected.wire_bytes),
                         (sum(len(value) for _, values in candidate.streams for value in values),
                          len(execution.encode_bundle(candidate)), sum(len(row.frame_bytes) for row in rows), len(wire)))

    def test_full_and_cached_encoders_share_one_metadata_and_sha_composer(self):
        bundle = self._bundle()
        view = self._view(bundle)
        for encode in (lambda: execution.encode_bundle_v2(bundle, self.profile),
                       lambda: execution._compose_bundle_v2_from_rows(bundle, self.profile, view.rows)):
            with patch.object(execution, "_wb02_wire", wraps=execution._wb02_wire) as shared:
                wire = encode()
            self.assertEqual(shared.call_count, 1)
            self.assertEqual(wire, view.wire)
            self.assertEqual(wire[-32:], sha256(wire[:-32]).digest())

    def test_rows_are_not_authority_and_each_frame_is_independently_decoded(self):
        from experiments import program_k_e2_physical as physical
        bundle = self._bundle()
        view = self._view(bundle)
        with patch.object(physical, "decode_frame", wraps=physical.decode_frame) as decoded, \
                patch.object(physical, "encode_frame", side_effect=AssertionError("Recompression")):
            execution._compose_bundle_v2_from_rows(bundle, self.profile, view.rows)
        self.assertEqual(decoded.call_count, len(view.rows))
        for call, row in zip(decoded.call_args_list, view.rows):
            self.assertIs(call.args[0], row.frame_bytes)
            self.assertEqual(call.args[1], physical.context_for(row.stream_name, self.profile))
            self.assertEqual(call.kwargs["expected_key"], row.key)

    def test_cached_row_shape_order_count_and_claimed_fields_are_checked(self):
        bundle = self._bundle(position=0)
        view = self._view(bundle)
        row = view.rows[0]
        variants = (replace(row, stream_name="runtime"), replace(row, key=(0, 1, 0)),
                    replace(row, key=(False, 0, 0)), replace(row, key=[0, 0, 0]),
                    replace(row, logical_bytes=view.rows[1].logical_bytes),
                    replace(row, logical_bytes=bytearray(row.logical_bytes)),
                    replace(row, frame_bytes=bytearray(row.frame_bytes)),
                    replace(row, frame_length=row.frame_length + 1), replace(row, frame_length=True), object())
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(execution.E2ExecutionError):
                execution._compose_bundle_v2_from_rows(bundle, self.profile, (changed,) + view.rows[1:])
        for rows in (list(view.rows), view, view.rows[::-1], view.rows[:-1], view.rows + view.rows[:1]):
            with self.subTest(rows=type(rows)), self.assertRaises(execution.E2ExecutionError):
                execution._compose_bundle_v2_from_rows(bundle, self.profile, rows)

    def test_rewrapped_frame_cannot_substitute_profile_key_stream_or_logical_body(self):
        from experiments import program_k_e2_physical as physical
        bundle = self._bundle()
        view = self._view(bundle)
        row = view.rows[0]
        alternate = self._bundle("different logical identity").board
        frames = (
            physical.encode_frame(row.logical_bytes, row.key, physical.context_for("boards", b"z" * 32)),
            physical.encode_frame(row.logical_bytes, (129, 0, 0), physical.context_for("boards", self.profile)),
            physical.encode_frame(alternate, row.key, physical.context_for("boards", self.profile)),
            view.rows[1].frame_bytes,
            row.frame_bytes[:-1] + bytes((row.frame_bytes[-1] ^ 1,)),
            row.frame_bytes[:-1], row.frame_bytes + b"trailing",
        )
        for frame in frames:
            with self.subTest(length=len(frame)), self.assertRaises(ValueError):
                forged = replace(row, frame_bytes=frame, frame_length=len(frame))
                execution._compose_bundle_v2_from_rows(bundle, self.profile, (forged,) + view.rows[1:])
        for candidate in (replace(bundle, work_position=129), replace(bundle, kind=execution.WorkerKind.DETERMINISM)):
            with self.assertRaises(ValueError):
                execution._compose_bundle_v2_from_rows(candidate, self.profile, view.rows)

    def test_cached_composition_preserves_independent_expanded_and_metadata_caps(self):
        from experiments import program_k_e2_physical as physical
        bundle = self._bundle("x" * 2048)
        view = self._view(bundle)
        with patch.object(physical, "decode_frame", side_effect=AssertionError("Expanded bounds first")):
            for limit, reason in ((view.logical_bytes - 1, "PAYLOAD_CAP"),
                                  (view.logical_bytes, "LEGACY_CAP")):
                with self.assertRaisesRegex(execution.E2ExecutionError, reason):
                    execution._compose_bundle_v2_from_rows(bundle, self.profile, view.rows, max_payload_bytes=limit)
        with patch.object(execution, "_json", side_effect=AssertionError("Metadata cap before allocation")):
            with self.assertRaisesRegex(execution.E2ExecutionError, "METADATA_CAP"):
                execution._compose_bundle_v2_from_rows(bundle, self.profile, view.rows, max_metadata_bytes=1)
        for digest in (bytearray(self.profile), bytes(31), "x" * 32):
            with self.assertRaises(execution.E2ExecutionError):
                execution._compose_bundle_v2_from_rows(bundle, digest, view.rows)
        for limit in (True, 0, -1, physical.MAX_PAYLOAD_BYTES + 1):
            with self.assertRaises(execution.E2ExecutionError):
                execution._compose_bundle_v2_from_rows(bundle, self.profile, view.rows, max_payload_bytes=limit)

    def test_cached_composer_exposes_no_validation_or_trust_override(self):
        bundle = self._bundle()
        view = self._view(bundle)
        self.assertEqual(tuple(inspect.signature(execution._compose_bundle_v2_from_rows).parameters),
                         ("bundle", "codec_profile_sha256", "rows", "max_payload_bytes", "max_metadata_bytes"))
        for keyword in ("validated", "trusted", "admitted", "qualified"):
            with self.assertRaises(TypeError):
                execution._compose_bundle_v2_from_rows(bundle, self.profile, view.rows, **{keyword: True})

    def test_shared_layout_counts_exact_wire_and_overcap_preview_without_allocation(self):
        from experiments import program_k_e2_physical as physical
        bundle = self._bundle()
        view = self._view(bundle)
        metadata, _ = self._parts(view.wire)
        with patch.object(execution, "_json", side_effect=AssertionError("Preview allocated metadata")), \
                patch.object(physical, "encode_frame", side_effect=AssertionError("Preview encoded frame")), \
                patch.object(physical, "decode_frame", side_effect=AssertionError("Preview admitted frame")):
            node, size, total = execution._wb02_layout(bundle, self.profile, view.logical_bytes,
                view.legacy_bytes, metadata["streams"], view.frame_bytes)
            self.assertEqual((size, total), (view.metadata_bytes, len(view.wire)))
            # Scalar sizing only: no large frame/body is constructed or admitted.
            frame_size = physical.MAX_PAYLOAD_BYTES + 1
            groups = [[name, count, logical, physical_size]
                      for name, count, logical, physical_size in metadata["streams"]]
            groups[0][3] += frame_size - view.frame_bytes
            over_node, over_metadata, over_wire = execution._wb02_layout(bundle, self.profile,
                view.logical_bytes, view.legacy_bytes, groups, frame_size)
        self.assertEqual(json.loads(json.dumps(node)), metadata)
        self.assertGreater(over_wire, physical.MAX_PAYLOAD_BYTES)
        self.assertEqual(over_wire, 48 + over_metadata + frame_size)
        self.assertEqual(over_node["wire_bytes"], over_wire)
        self.assertEqual(len(json.dumps(over_node, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=True).encode("ascii")), over_metadata)


if __name__ == "__main__":
    unittest.main()
