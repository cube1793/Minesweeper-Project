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
        with _literal_context(work, frozenset()), patch.object(audit, "_oracle_b",
                side_effect=AssertionError("No reached phase can invoke Oracle-B")):
            result = execution.execute_primary(work)
        coverage, = _streams(result)["oracle_b_coverage"]
        self.assertTrue(coverage.selected)
        self.assertEqual(coverage.applicable, ())
        self.assertEqual(_streams(result)["oracle_b_audits"], ())
        self.assertIs(result.status, records.AuditStatus.PASS)

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


if __name__ == "__main__":
    unittest.main()
