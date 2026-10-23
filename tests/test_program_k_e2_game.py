"""I4 tiny literal execution and detached public-evidence projection tests only.

No indexed board generation, corpus selection, evaluator, Oracle qualification,
E1 schedule, persistence, or I5 orchestration is exercised here.
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

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from experiments import program_k_capability as capability
from experiments import program_k_e2_game as game
from experiments import program_k_e2_records as records
from experiments import program_k_evidence as evidence
from experiments import program_k_harness as harness
from experiments import program_k_policy as policy
from experiments import program_k_runner as runner
from simple_algorithm import InferenceResult, SimpleMove
from simple_decision import DecisionKind, SimpleDecision
from stage3_physical import action_cost, load_timing_table
from stage3_planner import RevealPlan, Stage3Decision
from stage3_runner import Stage3ActionTrace


H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)


def _engine(width=4, mines=frozenset({(1, 0)})):
    engine = MinesweeperEngine(width, 1, len(mines))
    engine.reset_with_mines(width, 1, len(mines), mines)
    return engine


class _PublicPort:
    """The adapter can reach only public fields/methods; hidden reads fail."""

    __slots__ = ("_engine",)

    def __init__(self, engine):
        self._engine = engine

    @property
    def width(self):
        return self._engine.width

    @property
    def height(self):
        return self._engine.height

    @property
    def num_mines(self):
        return self._engine.num_mines

    @property
    def status(self):
        return self._engine.status

    def get_observation(self):
        return self._engine.get_observation()

    def step(self, x, y, action):
        self._engine.step(x, y, action)
        return None

    @property
    def mines(self):
        raise AssertionError("Projection/runner read hidden mines")


def _board(width=4, mines=1, index=101):
    return records.BoardIdentity(index, "synthetic-inert-identity", width, 1, mines,
                                 (0, 0), "literal-test-layout", "I4-synthetic")


def _arm(kind, board):
    return records.ArmIdentity(kind, board, "synthetic-run", "synthetic-unit")


def _corrupt(value, **changes):
    result = deepcopy(value)
    for name, supplied in changes.items():
        object.__setattr__(result, name, supplied)
    return result


def _decision_record(arm, ordinal, action, target, *, category=None, semantic=None,
                     plan=(), model=None, reveals=None, setup=(), opened=(), before=(), after=()):
    initial = ordinal == 0
    if category is None:
        category = (("CONTROL_INITIAL_OPEN" if arm.arm is records.Arm.CONTROL else "POLICY_INITIAL_OPEN")
                    if initial else "local_deterministic")
    if semantic is None:
        semantic = "INITIAL" if initial else "local_deterministic"
    return records.ActionDecisionRecord(arm, ordinal, category, semantic, action, target,
                                         plan, model, reveals, setup, opened, before, after)


class ExecutionProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()
        cls.board = _board()
        cls.control_raw = runner.run_control_capture(_PublicPort(_engine()), table=cls.table)
        cls.kp0_raw = runner.run_k_p0(_PublicPort(_engine()), table=cls.table, capture_effects=True)
        cls.control = game.project_control(cls.control_raw, _arm(records.Arm.CONTROL, cls.board), table=cls.table)
        cls.kp0 = game.project_k_p0(cls.kp0_raw, _arm(records.Arm.K_P0, cls.board), table=cls.table)
        cls.guess_board = _board(5, 2, 102)
        layout = frozenset({(1, 0), (2, 0)})
        cls.guess_control_raw = runner.run_control_capture(_PublicPort(_engine(5, layout)), table=cls.table)
        cls.guess_kp0_raw = runner.run_k_p0(_PublicPort(_engine(5, layout)), table=cls.table, capture_effects=True)
        cls.guess_control = game.project_control(cls.guess_control_raw,
                                                  _arm(records.Arm.CONTROL, cls.guess_board), table=cls.table)
        cls.guess_kp0 = game.project_k_p0(cls.guess_kp0_raw,
                                          _arm(records.Arm.K_P0, cls.guess_board), table=cls.table)

    def test_thin_entry_points_call_only_existing_runners(self):
        port = _PublicPort(_engine())
        with patch.object(runner, "run_control_capture", return_value=self.control_raw) as called:
            result = game.run_control(port, self.board, run_id="synthetic-run", unit_id="synthetic-unit", table=self.table)
        called.assert_called_once_with(port, table=self.table)
        self.assertEqual(result, self.control)
        port = _PublicPort(_engine())
        with patch.object(runner, "run_k_p0", return_value=self.kp0_raw) as called:
            result = game.run_k_p0(port, self.board, run_id="synthetic-run", unit_id="synthetic-unit", table=self.table)
        called.assert_called_once_with(port, table=self.table, capture_effects=True)
        self.assertEqual(result, self.kp0)

    def test_identity_dimension_first_click_and_arm_rejection(self):
        for board in (replace(self.board, width=5), replace(self.board, first_click=(1, 0)), {}, None):
            with patch.object(runner, "run_control_capture", side_effect=AssertionError("invalid identity executed")):
                with self.assertRaises(game.GameProjectionError):
                    game.run_control(_PublicPort(_engine()), board, run_id="r", unit_id="u", table=self.table)
        for arm in (_arm(records.Arm.K_P0, self.board), _arm(records.Arm.K_CONTROL, self.board), self.board):
            with self.assertRaises(game.GameProjectionError):
                game.project_control(self.control_raw, arm, table=self.table)
        with self.assertRaises(game.GameProjectionError):
            game.project_k_p0(self.kp0_raw, _arm(records.Arm.CONTROL, self.board), table=self.table)

    def test_physical_projection_exact_order_actions_cursors_and_model_c(self):
        for raw, projection in ((self.control_raw, self.control), (self.kp0_raw, self.kp0),
                                (self.guess_control_raw, self.guess_control), (self.guess_kp0_raw, self.guess_kp0)):
            total = 0
            self.assertEqual(len(raw.traces), len(projection.physical_inputs))
            for index, (trace, projected) in enumerate(zip(raw.traces, projection.physical_inputs)):
                total += action_cost(self.table, trace.cursor_before, (trace.move.x, trace.move.y))
                self.assertEqual(projected.action_ordinal, index)
                self.assertEqual(projected.action.value, trace.move.action.name)
                self.assertEqual(projected.target, (trace.move.x, trace.move.y))
                self.assertEqual(projected.cursor_before, trace.cursor_before)
                self.assertEqual(projected.input_us, trace.modeled_action_us)
                self.assertEqual(projected.cumulative_us, total)
                self.assertEqual(projected.after_status.value, trace.status_after.name)
            self.assertEqual(total, raw.total_modeled_us)
            self.assertEqual(total, projection.total_model_us)

    def test_public_effects_validate_and_replay_without_hidden_truth(self):
        for raw, projection in ((self.control_raw, self.control), (self.kp0_raw, self.kp0),
                                (self.guess_control_raw, self.guess_control), (self.guess_kp0_raw, self.guess_kp0)):
            original = raw.effects if type(raw) is runner.ControlCaptureResult else tuple(t.public_effect for t in raw.traces)
            self.assertEqual(evidence.validate_public_effect_stream(original, complete=True).status, "PASS")
            self.assertTrue(projection.effect_evidence_complete)
            self.assertEqual(len(projection.public_effects), len(projection.physical_inputs))
            public = {(x, y): "HIDDEN" for y in range(projection.arm.board.height) for x in range(projection.arm.board.width)}
            for index, effect in enumerate(projection.public_effects):
                self.assertEqual(effect.action_ordinal, index)
                self.assertEqual(effect.before_status, records.Status.PLAYING)
                for change in effect.changes:
                    self.assertEqual(public[change.cell], change.before)
                    self.assertTrue(change.after in ("HIDDEN", "FLAGGED") or change.after.startswith("CLUE_"))
                    self.assertNotIn(change.after, {p.value for p in records.TerminalPresentation})
                    public[change.cell] = change.after
            self.assertNotEqual(projection.public_effects[-1].after_status, records.Status.PLAYING)

    def test_terminal_records_segregated_and_no_later_input(self):
        for projection in (self.control, self.kp0, self.guess_control, self.guess_kp0):
            self.assertTrue(projection.terminal_effects)
            terminal = projection.terminal_effects[-1]
            self.assertEqual(terminal.action_ordinal, len(projection.physical_inputs) - 1)
            self.assertEqual(terminal.terminal_status, projection.physical_inputs[-1].after_status)
            for change in terminal.changes:
                self.assertIs(type(change), records.TerminalCellChange)
            self.assertTrue(all(item.after_status is records.Status.PLAYING for item in projection.physical_inputs[:-1]))

    def test_winning_automatic_flags_are_terminal_presentation_only(self):
        checked = 0
        for raw, projected in ((self.control_raw, self.control), (self.kp0_raw, self.kp0)):
            effect = raw.effects[-1] if type(raw) is runner.ControlCaptureResult else raw.traces[-1].public_effect
            terminal = {change.cell: change.presentation for change in projected.terminal_effects[-1].changes}
            public = {change.cell: change.after for change in projected.public_effects[-1].changes}
            for y, row in enumerate(effect.after_observation.rows):
                for x, glyph in enumerate(row):
                    if glyph == F and effect.before_observation[y][x] == H:
                        is_physical_flag = effect.move.action is Action.FLAG and (x, y) == (effect.move.x, effect.move.y)
                        if not is_physical_flag:
                            checked += 1
                            self.assertEqual(terminal[(x, y)], records.TerminalPresentation.CORRECT_FLAG)
                            self.assertNotIn((x, y), public)
        self.assertGreater(checked, 0)

    def test_malformed_cost_cursor_index_and_postterminal_inputs_fail_closed(self):
        for changes in (dict(input_index=99), dict(modeled_action_us=1), dict(cursor_before=(1, 0))):
            traces = (_corrupt(self.kp0_raw.traces[0], **changes),) + self.kp0_raw.traces[1:]
            with self.assertRaises(game.GameProjectionError):
                game.project_k_p0(_corrupt(self.kp0_raw, traces=traces), self.kp0.arm, table=self.table)
        raw = _corrupt(self.kp0_raw, traces=self.kp0_raw.traces + (self.kp0_raw.traces[0],))
        with self.assertRaises(game.GameProjectionError):
            game.project_k_p0(raw, self.kp0.arm, table=self.table)

    def test_corrupt_public_effect_raises_missing_effect_marks_incomplete(self):
        trace = self.guess_kp0_raw.traces[-1]
        bad_effect = _corrupt(trace.public_effect, input_index=77)
        corrupt = replace(self.guess_kp0_raw, traces=self.guess_kp0_raw.traces[:-1] + (replace(trace, public_effect=bad_effect),))
        with self.assertRaises(game.GameProjectionError):
            game.project_k_p0(corrupt, self.guess_kp0.arm, table=self.table)
        missing = replace(self.guess_kp0_raw, traces=self.guess_kp0_raw.traces[:-1] + (
            replace(trace, public_effect=None, public_effect_status="NOT_EVALUATED"),))
        projected = game.project_k_p0(missing, self.guess_kp0.arm, table=self.table)
        self.assertFalse(projected.effect_evidence_complete)
        self.assertFalse(projected.p3_evidence_complete)
        self.assertEqual(len(projected.physical_inputs), len(missing.traces))
        self.assertEqual(game.pair_projections(self.guess_control, projected).p3.status, records.P3Status.INCOMPLETE)

    def test_compute_sums_comparable_spans_and_excludes_other_work(self):
        for raw, projection in ((self.control_raw, self.control), (self.kp0_raw, self.kp0)):
            expected = (sum(t.decision_compute_ns for t in raw.traces[1:])
                        if type(raw) is runner.ControlCaptureResult
                        else sum(t.timings.k_analysis_planning_ns for t in raw.traces[1:]))
            self.assertEqual(projection.comparable_compute_ns, expected)
        altered = replace(self.kp0_raw, traces=tuple(replace(t, timings=replace(t.timings,
            evidence_ns=10**15, k_execution_validation_ns=10**15, evaluator_ns=10**15)) for t in self.kp0_raw.traces))
        self.assertEqual(game.project_k_p0(altered, self.kp0.arm, table=self.table).comparable_compute_ns,
                         self.kp0.comparable_compute_ns)
        self.assertTrue(all(t.scope is records.DecisionScope.K_ANALYZE_DECISION_THROUGH_SELECT_POLICY
                            for t in self.kp0.decision_spans))
        self.assertTrue(all(t.scope is records.DecisionScope.CONTROL_PLAN_POSITION for t in self.control.decision_spans))

    def test_missing_required_compute_stays_none(self):
        traces = list(self.kp0_raw.traces)
        traces[1] = replace(traces[1], timings=replace(traces[1].timings, k_analysis_planning_ns=None))
        projected = game.project_k_p0(replace(self.kp0_raw, traces=tuple(traces)), self.kp0.arm, table=self.table)
        self.assertIsNone(projected.comparable_compute_ns)
        control_traces = list(self.control_raw.traces)
        control_traces[1] = replace(control_traces[1], decision_compute_ns=None)
        timings = list(self.control_raw.timings)
        timings[1] = replace(timings[1], v1_plan_position_ns=None)
        raw = replace(self.control_raw, control=replace(self.control_raw.control, traces=tuple(control_traces)), timings=tuple(timings))
        self.assertIsNone(game.project_control(raw, self.control.arm, table=self.table).comparable_compute_ns)

    def test_initial_only_run_has_no_comparable_decision_span(self):
        board = _board(1, 0, 103)
        for function in (game.run_control, game.run_k_p0):
            projection = function(_PublicPort(_engine(1, frozenset())), board,
                                  run_id="initial-only", unit_id="initial-only", table=self.table)
            self.assertEqual(len(projection.physical_inputs), 1)
            self.assertEqual(projection.decision_spans, ())
            self.assertEqual(projection.comparable_compute_ns, 0)

    def test_no_guess_pair_pass_and_ww_delta_exact(self):
        paired = game.pair_projections(self.control, self.kp0)
        self.assertEqual((self.control.guess_checkpoints, self.kp0.guess_checkpoints), ((), ()))
        self.assertEqual(paired.p3.status, records.P3Status.PASS)
        self.assertIsNone(paired.p3.divergence)
        self.assertEqual(paired.pair.ww_delta_us, self.kp0.total_model_us - self.control.total_model_us)
        self.assertEqual(paired.pair.g5, game.summarize_g5(self.control.flag_provenance))
        self.assertFalse(hasattr(paired, "verdict"))

    def test_one_guess_uses_ordinal_not_physical_input_index(self):
        control, kp0 = self.guess_control.guess_checkpoints, self.guess_kp0.guess_checkpoints
        self.assertEqual((len(control), len(kp0)), (1, 1))
        self.assertEqual(control[0].guess_ordinal, 1)
        self.assertEqual(kp0[0].guess_ordinal, 1)
        self.assertEqual(control[0].physical_p, ((1, 0),))
        self.assertEqual(kp0[0].physical_p, ())
        self.assertEqual(kp0[0].effective_p_union_m, ((1, 0),))
        self.assertEqual((control[0].unreduced_z, control[0].mine_budget), (3, 1))
        self.assertEqual(control[0].mine_counts, (((2, 0), 1), ((3, 0), 1), ((4, 0), 1)))
        self.assertEqual(game.compare_p3(control, kp0).status, records.P3Status.PASS)
        ci = next(i for i, t in enumerate(self.guess_control_raw.traces)
                  if t.decision is not None and t.decision.evidence.kind is DecisionKind.PROBABILITY_GUESS)
        ki = next(t.input_index for t in self.guess_kp0_raw.traces if t.category == "EXACT_MINIMUM_RISK_GUESS")
        self.assertEqual((ci, ki), (2, 1))
        self.assertIsNone(game.pair_projections(self.guess_control, self.guess_kp0).pair.ww_delta_us)

    def test_differential_existing_harness_checkpoint_semantics(self):
        audits = []
        for kind, raw, projected in (("CONTROL", self.guess_control_raw, self.guess_control),
                                     ("K-P0", self.guess_kp0_raw, self.guess_kp0)):
            audit = harness.extract_guess_checkpoints(harness.ExecutionArchive("I4-synthetic", kind, raw), num_mines=2)
            self.assertEqual(audit.status, "COMPLETE")
            audits.append(audit)
            for old, new in zip(audit.checkpoints, projected.guess_checkpoints):
                self.assertEqual(old.guess_ordinal, new.guess_ordinal)
                self.assertEqual(old.revealed_clues, new.public_clues)
                self.assertEqual(old.fixed_mines, frozenset(new.effective_p_union_m))
                self.assertEqual(old.unresolved, frozenset(new.unresolved))
                self.assertEqual(old.remaining_mines, new.mine_budget)
                self.assertEqual(old.total_worlds, new.unreduced_z)
                self.assertEqual(old.mine_worlds, new.mine_counts)
                self.assertEqual(old.probabilities, new.probabilities)
                self.assertEqual(old.minimum_risk, new.minimum_risk)
                self.assertEqual(old.minimum_risk_cells, frozenset(new.minimum_ties))
                self.assertEqual(old.target, new.chosen_target)
        self.assertEqual(harness.compare_guess_checkpoints(*audits).status,
                         game.compare_p3(self.guess_control.guess_checkpoints, self.guess_kp0.guess_checkpoints).status.value)

    def test_detached_multiple_guesses_match_extra_missing_fail(self):
        c, k = self.guess_control.guess_checkpoints[0], self.guess_kp0.guess_checkpoints[0]
        control, kp0 = (c, replace(c, guess_ordinal=2)), (k, replace(k, guess_ordinal=2))
        self.assertEqual(game.compare_p3(control, kp0).status, records.P3Status.PASS)
        for other in ((), (k,), kp0 + (replace(k, guess_ordinal=3),)):
            result = game.compare_p3(control, other)
            self.assertEqual(result.status, records.P3Status.FAIL)
            self.assertIsNotNone(result.divergence)

    def test_p3_missing_evidence_and_ownership_fail_closed(self):
        for c_complete, k_complete in ((False, True), (True, False), (False, False)):
            self.assertEqual(game.compare_p3((), (), control_complete=c_complete, kp0_complete=k_complete).status,
                             records.P3Status.INCOMPLETE)
        for value in ([], (object(),), self.guess_control.guess_checkpoints[0]):
            with self.assertRaises(game.GameProjectionError):
                game.compare_p3(value, self.guess_kp0.guess_checkpoints)

    def test_missing_extraction_evidence_retains_run_and_pair_is_incomplete(self):
        last = self.guess_control_raw.traces[-1]
        decision = replace(last.decision, evidence=replace(last.decision.evidence, probability_result=None))
        traces = self.guess_control_raw.traces[:-1] + (replace(last, decision=decision),)
        raw = replace(self.guess_control_raw, control=replace(self.guess_control_raw.control, traces=traces))
        projected = game.project_control(raw, self.guess_control.arm, table=self.table)
        self.assertTrue(projected.effect_evidence_complete)
        self.assertFalse(projected.p3_evidence_complete)
        self.assertEqual(projected.physical_inputs, self.guess_control.physical_inputs)
        self.assertEqual(game.pair_projections(projected, self.guess_kp0).p3.status, records.P3Status.INCOMPLETE)
        last = self.guess_kp0_raw.traces[-1]
        selection = replace(last.selection, evidence=replace(last.selection.evidence, phase_e=None))
        raw = replace(self.guess_kp0_raw, traces=self.guess_kp0_raw.traces[:-1] + (replace(last, selection=selection),))
        projected = game.project_k_p0(raw, self.guess_kp0.arm, table=self.table)
        self.assertFalse(projected.p3_evidence_complete)
        self.assertTrue(projected.effect_evidence_complete)

    def test_missing_selected_postinitial_decision_is_now_rejected(self):
        last = self.guess_control_raw.traces[-1]
        raw = replace(self.guess_control_raw, control=replace(self.guess_control_raw.control,
            traces=self.guess_control_raw.traces[:-1] + (replace(last, decision=None),)))
        with self.assertRaises(game.GameProjectionError):
            game.project_control(raw, self.guess_control.arm, table=self.table)
        last = self.guess_kp0_raw.traces[-1]
        raw = replace(self.guess_kp0_raw, traces=self.guess_kp0_raw.traces[:-1] + (replace(last, selection=None),))
        with self.assertRaises(game.GameProjectionError):
            game.project_k_p0(raw, self.guess_kp0.arm, table=self.table)

    def test_control_guess_relabelled_as_local_certainty_is_rejected(self):
        trace = self.guess_control_raw.traces[-1]
        claimed = replace(trace.decision.evidence, kind=DecisionKind.LOCAL_DETERMINISTIC,
                          probability_result=None)
        changed = replace(trace, decision=replace(trace.decision, evidence=claimed))
        raw = replace(self.guess_control_raw,
                      control=replace(self.guess_control_raw.control,
                                      traces=self.guess_control_raw.traces[:-1] + (changed,)))
        with self.assertRaises(game.GameProjectionError):
            game.project_control(raw, self.guess_control.arm, table=self.table)

    def test_kp0_guess_relabelled_as_exact_safe_open_is_rejected(self):
        trace = self.guess_kp0_raw.traces[-1]
        claimed = replace(trace.selection.evidence, continuation="EXACT_SAFE")
        selection = replace(trace.selection, category="DIRECT_SAFE_OPEN", evidence=claimed)
        changed = replace(trace, category="DIRECT_SAFE_OPEN", selection=selection)
        raw = replace(self.guess_kp0_raw, traces=self.guess_kp0_raw.traces[:-1] + (changed,))
        with self.assertRaises(game.GameProjectionError):
            game.project_k_p0(raw, self.guess_kp0.arm, table=self.table)

    def test_each_p3_semantic_field_is_compared_without_a_both_win_waiver(self):
        control = replace(self.guess_control.guess_checkpoints[0], eventual_outcome=records.Outcome.WIN)
        kp0 = replace(self.guess_kp0.guess_checkpoints[0], eventual_outcome=records.Outcome.WIN)
        cases = {"guess_ordinal": 2, "public_clues": (((0, 0), 2),),
                 "effective_p_union_m": (), "unresolved": ((2, 0), (3, 0)), "mine_budget": 2,
                 "unreduced_z": 6, "mine_counts": (((2, 0), 2), ((3, 0), 1), ((4, 0), 1)),
                 "probabilities": (((2, 0), Fraction(1, 2)), ((3, 0), Fraction(1, 3)), ((4, 0), Fraction(1, 3))),
                 "minimum_risk": Fraction(1, 4), "minimum_ties": ((2, 0), (3, 0)),
                 "chosen_target": (3, 0), "eventual_outcome": records.Outcome.LOSS}
        # This isolated closed-field helper runs after public-entry schema validation.
        # Corruption isolates fields whose coupled I1 invariants forbid independent changes.
        for name, value in cases.items():
            with self.subTest(field=name):
                changed = _corrupt(kp0, **{name: value})
                difference = game._compare_checkpoint_fields(control, changed)
                self.assertIsNotNone(difference)
                self.assertEqual(difference.guess_ordinal, 1)
                self.assertEqual(difference.field, "physical_p" if name == "effective_p_union_m" else name)
                self.assertEqual(difference.kp0_value, value)
        changed = replace(kp0, public_clues=(((0, 0), 2),))
        result = game.compare_p3((control,), (changed,))
        self.assertEqual(result.status, records.P3Status.FAIL)
        self.assertEqual(result.divergence.field, "public_clues")

    def test_malformed_checkpoint_is_an_error_not_a_scientific_comparison(self):
        kp0 = _corrupt(self.guess_kp0.guess_checkpoints[0], unreduced_z=0)
        with self.assertRaises(game.GameProjectionError):
            game.compare_p3(self.guess_control.guess_checkpoints, (kp0,))

    def test_pair_arm_board_and_mutable_bundle_ownership_rejected(self):
        with self.assertRaises(game.GameProjectionError):
            game.pair_projections(self.kp0, self.control)
        changed_arm = replace(self.kp0.arm, board=replace(self.board, game_index=999))
        with self.assertRaises(game.GameProjectionError):
            game.pair_projections(self.control, replace(self.kp0, arm=changed_arm))
        with self.assertRaises((game.GameProjectionError, records.RecordError)):
            replace(self.control, physical_inputs=list(self.control.physical_inputs))

    def test_published_graph_is_deeply_frozen_slotted_and_has_no_live_objects(self):
        value = game.pair_projections(self.control, self.kp0)
        def inspect_value(item):
            self.assertNotIsInstance(item, (list, dict, set, MinesweeperEngine, capability.KLocalSession))
            if type(item) is tuple:
                for child in item:
                    inspect_value(child)
            elif is_dataclass(item):
                self.assertTrue(type(item).__dataclass_params__.frozen)
                self.assertFalse(hasattr(item, "__dict__"))
                for field in fields(item):
                    inspect_value(getattr(item, field.name))
            else:
                self.assertTrue(item is None or type(item) in (str, int, bool, Fraction) or isinstance(item, Enum))
        inspect_value(value)
        with self.assertRaises(FrozenInstanceError):
            value.control.total_model_us = 0
        self.assertEqual(self.control.acquisitions, ())
        self.assertEqual(self.kp0.flag_provenance, ())

    def test_every_control_input_retains_exact_decision_semantics_and_plan(self):
        for raw, projection in ((self.control_raw, self.control), (self.guess_control_raw, self.guess_control)):
            self.assertEqual(len(projection.decisions), len(raw.traces))
            self.assertEqual(projection.decisions,
                             game.project_control_decisions(raw.traces, projection.arm))
            for ordinal, (trace, decision) in enumerate(zip(raw.traces, projection.decisions)):
                self.assertEqual(decision.arm, projection.arm)
                self.assertEqual(decision.action_ordinal, ordinal)
                self.assertEqual((decision.action.value, decision.target), (trace.move.action.name, (trace.move.x, trace.move.y)))
                self.assertEqual((decision.logical_mines_before, decision.logical_mines_after), ((), ()))
                if ordinal == 0:
                    self.assertEqual((decision.category, decision.semantic_kind), ("CONTROL_INITIAL_OPEN", "INITIAL"))
                    self.assertEqual(decision.plan_actions, ())
                else:
                    self.assertEqual(decision.category, trace.decision.evidence.kind.value)
                    self.assertEqual(decision.semantic_kind, trace.decision.evidence.kind.value)
                    plan = trace.decision.plan
                    self.assertEqual(decision.plan_actions, () if plan is None else tuple(
                        (records.Action[item.action.name], (item.x, item.y)) for item in plan.actions))
                    self.assertEqual(decision.plan_model_us, None if plan is None else plan.latency_us)
                    self.assertEqual(decision.plan_safe_reveals, None if plan is None else plan.reveals)

    def test_every_k_input_retains_exact_category_plan_candidate_cells_and_m(self):
        for raw, projection in ((self.kp0_raw, self.kp0), (self.guess_kp0_raw, self.guess_kp0)):
            self.assertEqual(len(projection.decisions), len(raw.traces))
            self.assertEqual(projection.decisions, game.project_k_decisions(raw.traces, projection.arm))
            for ordinal, (trace, decision) in enumerate(zip(raw.traces, projection.decisions)):
                self.assertEqual(decision.action_ordinal, ordinal)
                self.assertEqual(decision.category, trace.category)
                self.assertEqual((decision.action.value, decision.target), (trace.move.action.name, (trace.move.x, trace.move.y)))
                self.assertEqual(frozenset(decision.logical_mines_before), trace.M_before)
                self.assertEqual(frozenset(decision.logical_mines_after), trace.preinput_M)
                if ordinal == 0:
                    self.assertEqual(decision.semantic_kind, "INITIAL")
                    self.assertEqual(decision.plan_actions, ())
                    continue
                self.assertEqual(decision.semantic_kind, trace.selection.evidence.continuation)
                plan = trace.selection.plan
                self.assertEqual(decision.plan_actions, () if plan is None else tuple(
                    (records.Action[item.action.name], (item.x, item.y)) for item in plan.actions))
                self.assertEqual(decision.plan_model_us, None if plan is None else plan.latency_us)
                self.assertEqual(decision.plan_safe_reveals, None if plan is None else plan.reveals)
                if plan is not None:
                    selected = tuple(item for item in trace.selection.survivors
                                     if item.plan == plan and item.category == trace.category)
                    self.assertEqual(len(selected), 1)
                    self.assertEqual(frozenset(decision.setup_cells), selected[0].setup_cells)
                    self.assertEqual(frozenset(decision.reveal_cells), selected[0].reveal_cells)

    def test_final_m_matches_last_decision_unique_acquisitions_and_durable_validation(self):
        for raw, projection in ((self.kp0_raw, self.kp0), (self.guess_kp0_raw, self.guess_kp0)):
            final = projection.decisions[-1].logical_mines_after
            self.assertEqual(frozenset(final), raw.final_M)
            self.assertEqual(frozenset(a.cell for a in projection.acquisitions), raw.final_M)
            self.assertEqual(len(projection.acquisitions), len(raw.final_M))
            self.assertEqual(game.validate_durable_decisions(projection.physical_inputs, projection.public_effects,
                                                              projection.decisions, projection.acquisitions), final)
            for decision in projection.decisions:
                acquired = frozenset(a.cell for a in projection.acquisitions if a.action_ordinal == decision.action_ordinal)
                self.assertEqual(acquired, frozenset(decision.logical_mines_after) - frozenset(decision.logical_mines_before))
        changed = replace(self.kp0_raw, final_M=frozenset())
        with self.assertRaises(game.GameProjectionError):
            game.project_k_p0(changed, self.kp0.arm, table=self.table)

    def test_decision_coverage_binding_and_acquisition_chronology_fail_closed(self):
        decisions = self.control.decisions
        for changed in (decisions[:-1], decisions + (decisions[-1],), decisions[::-1], list(decisions)):
            with self.assertRaises(game.GameProjectionError):
                replace(self.control, decisions=changed)
        changed = _corrupt(decisions[0], arm=self.kp0.arm)
        with self.assertRaises(game.GameProjectionError):
            replace(self.control, decisions=(changed,) + decisions[1:])
        changed = _corrupt(decisions[-1], target=(1, 0))
        with self.assertRaises(game.GameProjectionError):
            replace(self.control, decisions=decisions[:-1] + (changed,))
        acquisitions = self.kp0.acquisitions
        self.assertTrue(acquisitions)
        for changed in ((), acquisitions + (acquisitions[0],),
                        (replace(acquisitions[0], action_ordinal=0, decision_ordinal=0),) + acquisitions[1:]):
            with self.assertRaises(game.GameProjectionError):
                game.validate_durable_decisions(self.kp0.physical_inputs, self.kp0.public_effects,
                                                self.kp0.decisions, changed)


def _flag_decision(move, terminal=None):
    support = SimpleDecision(DecisionKind.LOCAL_DETERMINISTIC, move, (),
                             InferenceResult(frozenset(), frozenset({(move.x, move.y)})), None)
    plan = None if terminal is None else RevealPlan((move, terminal), 2, 1)
    return Stage3Decision(support, move, plan)


def _public_sequence(initial, actions):
    """Detached provenance fixture, deliberately no solver or Engine invocation.

    Each item is (move, after_grid, selected_terminal_or_None). The helper's
    ordinals are local to this synthetic public sequence, not a complete game.
    """
    traces, effects = [], []
    before, cursor = initial, (0, 0)
    for ordinal, (move, after, terminal) in enumerate(actions):
        effect = evidence.make_public_effect(before, move, after, input_index=ordinal,
                                              status_after=GameStatus.PLAYING,
                                              cursor_before=cursor, modeled_action_us=1)
        decision = _flag_decision(move, terminal) if move.action is Action.FLAG else None
        trace = Stage3ActionTrace(move, decision, 1, cursor, 1, GameStatus.PLAYING,
                                   effect.safe_cells_opened_delta, effect.explicit_flag_delta)
        traces.append(trace)
        effects.append(effect)
        before, cursor = after, (move.x, move.y)
    return tuple(traces), tuple(effects)


class FlagProvenanceTests(unittest.TestCase):
    def test_all_three_categories_exact_and_setup_diagnostic_only(self):
        first = ((H, H, 3, H, H), (H, H, H, H, H))
        a = ((H, H, 3, H, H), (H, F, H, H, H))
        b = ((H, H, 3, H, H), (H, F, F, H, H))
        c = ((H, H, 3, H, H), (H, F, F, F, H))
        after = ((H, 1, 3, 1, H), (H, F, F, F, H))
        chord = SimpleMove(Action.CHORD, 2, 0)
        traces, effects = _public_sequence(first, (
            (SimpleMove(Action.FLAG, 1, 1), a, None),
            (SimpleMove(Action.FLAG, 2, 1), b, SimpleMove(Action.OPEN, 1, 0)),
            (SimpleMove(Action.FLAG, 3, 1), c, chord), (chord, after, None)))
        provenance, complete = game.project_control_flags(traces, effects)
        self.assertTrue(complete)
        self.assertEqual(tuple(p.category for p in provenance), (records.FlagCategory.CONTROL_FALLBACK_FLAG,
                         records.FlagCategory.CONTROL_FLAG_TO_OPEN_SETUP, records.FlagCategory.CONTROL_SETUP_CHORD_FLAG))
        expected_neighbors = ((1, 1), (2, 1), (3, 1))
        for item in provenance:
            self.assertEqual(item.witness.action_ordinal, 3)
            self.assertEqual(item.witness.clue, (2, 0))
            self.assertEqual(item.witness.physical_flag_neighbors, expected_neighbors)
            self.assertEqual(item.witness.directly_opened_safe_cells, ((1, 0), (3, 0)))
        self.assertIsNone(provenance[0].selected_plan_ref)
        self.assertIsNone(provenance[0].terminal_reveal)
        self.assertEqual(provenance[1].terminal_reveal, records.Action.OPEN)
        self.assertEqual(provenance[2].terminal_reveal, records.Action.CHORD)
        self.assertTrue(provenance[1].selected_plan_ref)
        self.assertEqual(game.summarize_g5(provenance), records.G5ExposureSummary(1, 1, 1))
        setup_only = game.summarize_g5((provenance[2],))
        self.assertFalse(setup_only.is_exposed)
        self.assertEqual(setup_only.diagnostic_setup_chord_flags, 1)

    def test_fallback_without_later_chord_or_without_safe_reveal_is_not_exposed(self):
        before, flagged = ((1, H, H),), ((1, F, H),)
        flag, chord = SimpleMove(Action.FLAG, 1, 0), SimpleMove(Action.CHORD, 0, 0)
        for actions in (((flag, flagged, None),), ((flag, flagged, None), (chord, flagged, None))):
            traces, effects = _public_sequence(before, actions)
            provenance, complete = game.project_control_flags(traces, effects)
            self.assertTrue(complete)
            self.assertIsNone(provenance[0].witness)
            self.assertFalse(game.summarize_g5(provenance).is_exposed)

    def test_unflagged_before_chord_and_old_binding_after_reflag_not_credited(self):
        before = ((1, H), (H, H))
        flagged = ((1, F), (H, H))
        after_unflagged_chord = before  # mismatched flag count: actual CHORD is a no-op
        after_flagged_chord = ((1, F), (1, 1))
        flag, chord = SimpleMove(Action.FLAG, 1, 0), SimpleMove(Action.CHORD, 0, 0)
        for reflag in (False, True):
            actions = [(flag, flagged, None), (flag, before, None)]
            if reflag:
                actions.append((flag, flagged, None))
            actions.append((chord, after_flagged_chord if reflag else after_unflagged_chord, None))
            provenance, complete = game.project_control_flags(*_public_sequence(before, actions))
            self.assertTrue(complete)
            self.assertIsNone(provenance[0].witness)
            self.assertIsNone(provenance[1].witness)
            self.assertEqual(game.summarize_g5(provenance).qualifying_fallback_flags, int(reflag))
            if reflag:
                self.assertEqual(provenance[2].witness.action_ordinal, 3)

    def test_unrelated_flag_and_mismatched_count_noop_chord_do_not_qualify(self):
        # The far flag does not satisfy this clue's adjacent flag count, so this
        # CHORD is an unchanged no-op and cannot establish productive use.
        before = ((1, H, H, H, H), (H, H, H, H, H))
        flagged = ((1, H, H, H, F), (H, H, H, H, H))
        after = flagged
        provenance, complete = game.project_control_flags(*_public_sequence(before, (
            (SimpleMove(Action.FLAG, 4, 0), flagged, None),
            (SimpleMove(Action.CHORD, 0, 0), after, None))))
        self.assertTrue(complete)
        self.assertIsNone(provenance[0].witness)
        self.assertFalse(game.summarize_g5(provenance).is_exposed)

    def test_mismatched_adjacent_flag_count_reveal_rejected_but_noop_nonqualifying(self):
        before = ((2, H), (H, H))
        flagged = ((2, F), (H, H))
        revealed = ((2, F), (1, H))
        flag, chord = SimpleMove(Action.FLAG, 1, 0), SimpleMove(Action.CHORD, 0, 0)
        with self.assertRaises(game.GameProjectionError):
            game.project_control_flags(*_public_sequence(before, (
                (flag, flagged, None), (chord, revealed, None))))
        provenance, complete = game.project_control_flags(*_public_sequence(before, (
            (flag, flagged, None), (chord, flagged, None))))
        self.assertTrue(complete)
        self.assertIsNone(provenance[0].witness)
        self.assertFalse(game.summarize_g5(provenance).is_exposed)

    def test_published_witness_must_bind_an_actual_in_range_productive_chord(self):
        board = records.BoardIdentity(104, "synthetic-witness-projection", 2, 2, 1,
                                       (0, 0), "supplied", "synthetic")
        arm = _arm(records.Arm.CONTROL, board)
        playing, won = records.Status.PLAYING, records.Status.WON
        physical = (
            records.PhysicalInputRecord(0, records.Action.OPEN, (0, 0), (0, 0), 1, 1, playing),
            records.PhysicalInputRecord(1, records.Action.FLAG, (1, 0), (0, 0), 1, 2, playing),
            records.PhysicalInputRecord(2, records.Action.OPEN, (0, 1), (1, 0), 1, 3, playing),
            records.PhysicalInputRecord(3, records.Action.CHORD, (0, 0), (0, 1), 1, 4, won),
        )
        public = (
            records.PublicEffectRecord(0, (records.PublicCellChange((0, 0), "HIDDEN", "CLUE_1"),), playing, playing),
            records.PublicEffectRecord(1, (records.PublicCellChange((1, 0), "HIDDEN", "FLAGGED"),), playing, playing),
            records.PublicEffectRecord(2, (records.PublicCellChange((0, 1), "HIDDEN", "CLUE_1"),), playing, playing),
            records.PublicEffectRecord(3, (records.PublicCellChange((1, 1), "HIDDEN", "CLUE_1"),), playing, won),
        )
        witness = records.ProductiveChordWitness(3, (0, 0), ((1, 0),), ((1, 1),))
        provenance = records.ControlFlagProvenanceRecord(1, (1, 0), records.FlagCategory.CONTROL_FALLBACK_FLAG,
                                                         None, None, None, witness)
        decisions = tuple(_decision_record(arm, i, item.action, item.target) for i, item in enumerate(physical))
        projection = game.GameProjection(
            arm, records.Outcome.WIN, physical, public, (records.TerminalEffectRecord(3, (), won),),
            tuple(records.DecisionSpanRecord(i, records.DecisionScope.CONTROL_PLAN_POSITION, 0) for i in (1, 2, 3)),
            (), (provenance,), (), decisions, 4, 0, True, True, True)
        self.assertTrue(game.summarize_g5(projection.flag_provenance).is_exposed)
        for changed in (replace(witness, action_ordinal=2),  # OPEN, not CHORD
                        replace(witness, action_ordinal=4),  # outside the executed stream
                        replace(witness, clue=(0, 1)),  # wrong actual CHORD target
                        replace(witness, directly_opened_safe_cells=((0, 1),))):  # already open
            with self.subTest(witness=changed), self.assertRaises(game.GameProjectionError):
                replace(projection, flag_provenance=(replace(provenance, witness=changed),))

    def test_only_direct_neighbors_are_in_productive_chord_witness(self):
        before = ((1, H, H), (H, H, H))
        flagged = ((1, F, H), (H, H, H))
        after = ((1, F, 0), (1, 0, 0))  # remote (2,0)/(2,1) public flood excluded
        provenance, complete = game.project_control_flags(*_public_sequence(before, (
            (SimpleMove(Action.FLAG, 1, 0), flagged, None),
            (SimpleMove(Action.CHORD, 0, 0), after, None))))
        self.assertTrue(complete)
        self.assertEqual(provenance[0].witness.directly_opened_safe_cells, ((0, 1), (1, 1)))

    def test_unknown_selected_terminal_and_missing_flag_evidence_fail_closed(self):
        before, flagged = ((1, H, H),), ((1, F, H),)
        flag = SimpleMove(Action.FLAG, 1, 0)
        traces, effects = _public_sequence(before, ((flag, flagged, flag),))
        with self.assertRaises(game.GameProjectionError):
            game.project_control_flags(traces, effects)
        traces, effects = _public_sequence(before, ((flag, flagged, None),))
        missing = (replace(traces[0], decision=None),)
        with self.assertRaises(game.GameProjectionError):
            game.project_control_flags(missing, effects)
        provenance, complete = game.project_control_flags(traces, (None,))
        self.assertFalse(complete)
        self.assertFalse(game.summarize_g5(provenance).is_exposed)


def _acquisition_fixture():
    """Supplied public certificate claims; projection must not verify their truth."""
    obs, empty = ((1, H, H, H),), frozenset()
    local_cert = capability.LocalMineCertificate(obs, 2, (0, 0), (1, 0), empty, GameStatus.PLAYING)
    exact_cert = capability.ExactGlobalMineCertificate(obs, 2, (2, 0), frozenset({(1, 0)}),
                                                       GameStatus.PLAYING, 1, (((2, 0), 1), ((3, 0), 0)))
    hidden = frozenset({(1, 0), (2, 0), (3, 0)})
    before = capability.Accounting(empty, hidden, empty, empty, hidden, 2, ())
    local_after = capability.Accounting(empty, hidden, frozenset({(1, 0)}), frozenset({(1, 0)}),
                                        frozenset({(2, 0), (3, 0)}), 1, ())
    after = capability.Accounting(empty, hidden, frozenset({(1, 0), (2, 0)}), frozenset({(1, 0), (2, 0)}),
                                  frozenset({(3, 0)}), 0, ())
    local = capability.LocalAnalysis(before, local_after, frozenset({(1, 0)}), empty, empty, empty, empty, (local_cert,))
    exact = capability.ExactAnalysis(((2, 0), (3, 0)), (), ((2, 0), (3, 0)), 1,
                                     (((2, 0), 1), ((3, 0), 0)), frozenset({(3, 0)}), frozenset({(2, 0)}),
                                     Fraction(0), frozenset({(3, 0)}))
    decision = capability.DecisionAnalysis(obs, 2, local, exact, None, "NOT_REACHED", after,
                                           (exact_cert,), "DIRECT_OPEN", frozenset({(3, 0)}), None)
    move = SimpleMove(Action.OPEN, 3, 0)
    selection = policy.PolicySelection(decision, (0, 0), move, None, "DIRECT_OPEN", (), ())
    initial = runner.KActionTrace(0, SimpleMove(Action.OPEN, 0, 0), "POLICY_INITIAL_OPEN", None,
                                  (0, 0), 1, GameStatus.PLAYING, empty, empty)
    trace = runner.KActionTrace(1, move, "DIRECT_OPEN", selection, (0, 0), 1, GameStatus.PLAYING,
                                empty, after.M)
    return (initial, trace), (local_cert, exact_cert)


class AcquisitionReferenceTests(unittest.TestCase):
    def test_local_and_exact_global_sources_and_decision_boundaries(self):
        traces, certificates = _acquisition_fixture()
        projected = game.project_acquisitions(traces)
        self.assertEqual(tuple(a.cell for a in projected), ((1, 0), (2, 0)))
        self.assertEqual(tuple(a.source for a in projected),
                         (records.AcquisitionSource.LOCAL, records.AcquisitionSource.EXACT_GLOBAL))
        for item, certificate in zip(projected, certificates):
            self.assertEqual((item.action_ordinal, item.decision_ordinal), (1, 0))
            digest = harness.content_digest(certificate)
            self.assertEqual((item.certificate_ref, item.certificate_sha256), ("sha256:" + digest, digest))

    def test_certificate_reference_is_stable_without_truth_admission(self):
        traces, certificates = _acquisition_fixture()
        with patch.object(harness, "audit_acquisition", side_effect=AssertionError("I4 performed proof admission")), \
                patch.object(harness, "verify_fixture", side_effect=AssertionError("I4 performed Oracle qualification")):
            for certificate in certificates:
                first = game.certificate_reference(certificate)
                self.assertEqual(first, game.certificate_reference(deepcopy(certificate)))
                self.assertEqual(first, ("sha256:" + harness.content_digest(certificate), harness.content_digest(certificate)))
            self.assertEqual(len(game.project_acquisitions(traces)), 2)

    def test_unknown_certificate_missing_certificate_and_malformed_digest_fail_closed(self):
        traces, certificates = _acquisition_fixture()
        for value in (None, {}, object(), traces[1].selection):
            with self.assertRaises(game.GameProjectionError):
                game.certificate_reference(value)
        decision = replace(traces[1].selection.evidence, exact_certificates=())
        malformed = (traces[0], replace(traces[1], selection=replace(traces[1].selection, evidence=decision)))
        with self.assertRaises(game.GameProjectionError):
            game.project_acquisitions(malformed)
        for digest in (None, "bad", "A" * 64):
            with patch.object(game, "content_digest", return_value=digest):
                with self.assertRaises(game.GameProjectionError):
                    game.certificate_reference(certificates[0])

    def test_retained_acquisition_is_not_reissued_and_initial_has_none(self):
        traces, certificates = _acquisition_fixture()
        self.assertEqual(game.project_acquisitions((traces[0],)), ())
        decision = traces[1].selection.evidence
        unchanged_local = replace(decision.local, before=decision.after, after=decision.after,
                                   acquired_mines=frozenset(), certificates=())
        unchanged = replace(decision, local=unchanged_local, exact_certificates=())
        later = replace(traces[1], input_index=2, M_before=decision.after.M,
                         selection=replace(traces[1].selection, evidence=unchanged))
        self.assertEqual(len(game.project_acquisitions(traces + (later,))), 2)


def _literal_setup_capture(table):
    engine = MinesweeperEngine(5, 4, 2)
    engine.reset_with_mines(5, 4, 2, frozenset({(1, 2), (3, 2)}))
    board = records.BoardIdentity(105, "synthetic-5x4-setup", 5, 4, 2, (0, 0),
                                  "literal-test-layout", "I4-durable-synthetic")
    arm = _arm(records.Arm.K_P0, board)
    raw = runner.run_k_p0(_PublicPort(engine), table=table, capture_effects=True)
    return raw, game.project_k_p0(raw, arm, table=table)


def _detached_setup_streams(*, replanned=False, prefix=None, terminal_prefix=False):
    """Closed synthetic durable records for full-plan diagnostic semantics.

    Terminal-prefix status is a supplied diagnostic fixture, not a claim that
    frozen K physically terminates while executing a partial setup plan.
    """
    board = records.BoardIdentity(106, "detached-multiaction-setup", 4, 2, 2, (0, 0), "supplied", "synthetic")
    arm = _arm(records.Arm.K_P0, board)
    mines = ((1, 0), (2, 0))
    chord = (records.Action.CHORD, (1, 1))
    full = ((records.Action.FLAG, (1, 0)), (records.Action.FLAG, (2, 0)), chord)
    actions = ((records.Action.OPEN, (0, 0)),) + full
    if replanned:
        actions = actions[:2] + ((records.Action.OPEN, (3, 1)),) + actions[3:]
    decisions = [_decision_record(arm, 0, *actions[0])]
    decisions.append(_decision_record(arm, 1, *actions[1], category="SETUP_CHORD", semantic="LOCAL_SAFE",
                                       plan=full, model=3, reveals=2, setup=mines, opened=((0, 1), (2, 1)), after=mines))
    if replanned:
        decisions.append(_decision_record(arm, 2, *actions[2], category="DIRECT_SAFE_OPEN", semantic="LOCAL_SAFE",
                                           plan=(actions[2],), model=1, reveals=1, opened=((3, 1),), before=mines, after=mines))
    else:
        decisions.append(_decision_record(arm, 2, *actions[2], category="SETUP_CHORD", semantic="LOCAL_SAFE",
                                           plan=full[1:], model=2, reveals=2, setup=((2, 0),),
                                           opened=((0, 1), (2, 1)), before=mines, after=mines))
    decisions.append(_decision_record(arm, 3, *actions[3], category="DIRECT_CHORD", semantic="LOCAL_SAFE",
                                       plan=(chord,), model=1, reveals=2, opened=((0, 1), (2, 1)), before=mines, after=mines))
    length = len(actions) if prefix is None else prefix
    physical = tuple(records.PhysicalInputRecord(i, action, target, (0, 0) if i == 0 else actions[i - 1][1],
                                                 1, i + 1,
                                                 records.Status.WON if i == length - 1 and (prefix is None or terminal_prefix)
                                                 else records.Status.PLAYING)
                     for i, (action, target) in enumerate(actions[:length]))
    acquisitions = tuple(records.AcquisitionRecord(1, 0, cell, records.AcquisitionSource.LOCAL,
                                                    "sha256:" + digest, digest)
                         for cell, digest in zip(mines, ("c" * 64, "d" * 64)))
    return physical, tuple(decisions[:length]), acquisitions


class DurableDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()
        cls.raw, cls.projection = _literal_setup_capture(cls.table)

    def test_selected_setup_survivor_has_exact_unique_match(self):
        setups = [(i, t) for i, t in enumerate(self.raw.traces) if t.category == "SETUP_CHORD"]
        self.assertTrue(setups, "The declared tiny literal fixture must exercise SETUP_CHORD.")
        ordinal, trace = setups[0]
        projected = self.projection.decisions[ordinal]
        self.assertGreaterEqual(len(projected.plan_actions), 2)
        self.assertEqual(projected.plan_actions, tuple((records.Action[m.action.name], (m.x, m.y))
                                                       for m in trace.selection.plan.actions))
        matching = tuple(c for c in trace.selection.survivors
                         if c.plan == trace.selection.plan and c.category == trace.category)
        self.assertEqual(len(matching), 1)
        without = tuple(c for c in trace.selection.survivors if c not in matching)
        for survivors in (without, trace.selection.survivors + matching):
            changed = replace(trace, selection=replace(trace.selection, survivors=survivors))
            traces = self.raw.traces[:ordinal] + (changed,) + self.raw.traces[ordinal + 1:]
            with self.assertRaises(game.GameProjectionError):
                game.project_k_decisions(traces, self.projection.arm)

    def test_selection_move_category_and_plan_first_input_mismatches_rejected(self):
        ordinal = next(i for i, t in enumerate(self.raw.traces) if t.category == "SETUP_CHORD")
        trace = self.raw.traces[ordinal]
        alternative = SimpleMove(Action.OPEN, 4, 3)
        wrong_plan = replace(trace.selection.plan, actions=(alternative,) + trace.selection.plan.actions[1:])
        for selection in (replace(trace.selection, move=alternative),
                          replace(trace.selection, category="UNMATCHED_CATEGORY"),
                          replace(trace.selection, plan=wrong_plan)):
            traces = self.raw.traces[:ordinal] + (replace(trace, selection=selection),) + self.raw.traces[ordinal + 1:]
            with self.assertRaises(game.GameProjectionError):
                game.project_k_decisions(traces, self.projection.arm)

    def test_final_m_mismatch_duplicate_cells_and_snapshot_regression_rejected(self):
        self.assertTrue(self.raw.final_M)
        changed = replace(self.raw, final_M=frozenset())
        with self.assertRaises(game.GameProjectionError):
            game.project_k_p0(changed, self.projection.arm, table=self.table)
        projection = self.projection
        with self.assertRaises(game.GameProjectionError):
            replace(projection, acquisitions=projection.acquisitions + (projection.acquisitions[0],))
        ordinal = next(i for i, d in enumerate(projection.decisions) if d.logical_mines_before)
        changed = _corrupt(projection.decisions[ordinal], logical_mines_after=())
        with self.assertRaises(game.GameProjectionError):
            replace(projection, decisions=projection.decisions[:ordinal] + (changed,) + projection.decisions[ordinal + 1:])

    def test_decoded_four_streams_are_sufficient_without_raw_runner_objects(self):
        def capture_and_encode():
            raw, projection = _literal_setup_capture(self.table)
            streams = (projection.physical_inputs, projection.public_effects, projection.decisions, projection.acquisitions)
            return (tuple(tuple(records.encode(item) for item in stream) for stream in streams),
                    tuple(sorted(raw.final_M, key=lambda cell: (cell[1], cell[0]))),
                    game.derive_k_setup_facts(projection))

        encoded, expected_final_m, expected_facts = capture_and_encode()
        # The local raw result, live Engine adapter, selections and projection
        # are gone. This validation boundary receives only four decoded streams.
        physical, public, decisions, acquisitions = tuple(
            tuple(records.decode(item) for item in stream) for stream in encoded)
        with patch.object(runner, "run_k_p0", side_effect=AssertionError("durable validation reran solver")), \
                patch.object(harness, "extract_guess_checkpoints", side_effect=AssertionError("durable validation read raw archive")), \
                patch.object(game, "project_k_p0", side_effect=AssertionError("durable validation requires raw result")):
            final_m = game.validate_durable_decisions(physical, public, decisions, acquisitions)
            facts = game.derive_k_setup_facts_from_records(physical, decisions, acquisitions)
        self.assertEqual(final_m, expected_final_m)
        self.assertEqual(decisions[-1].logical_mines_after, expected_final_m)
        self.assertEqual(frozenset(item.cell for item in acquisitions), frozenset(expected_final_m))
        self.assertEqual(len({item.cell for item in acquisitions}), len(acquisitions))
        self.assertEqual(facts, expected_facts)
        self.assertEqual(len(decisions), len(physical))
        for action, decision in zip(physical, decisions):
            self.assertEqual((action.action_ordinal, action.action, action.target),
                             (decision.action_ordinal, decision.action, decision.target))
            if decision.plan_actions:
                self.assertEqual(decision.plan_actions[0], (action.action, action.target))
            self.assertFalse(hasattr(decision, "selection"))
            self.assertFalse(hasattr(decision, "candidates"))
            self.assertFalse(hasattr(decision, "survivors"))

    def test_full_multiaction_plan_and_overlapping_realized_suffixes(self):
        physical, decisions, acquisitions = _detached_setup_streams()
        self.assertEqual(len(decisions[1].plan_actions), 3)
        self.assertEqual(records.decode(records.encode(decisions[1])).plan_actions, decisions[1].plan_actions)
        facts = game.derive_k_setup_facts_from_records(physical, decisions, acquisitions)
        self.assertEqual(facts.executed_setup_flags, 2)
        self.assertEqual(facts.selected_setup_ordinals, (1, 2))
        self.assertEqual(facts.realized_setup_ordinals, (1, 2))
        self.assertEqual(facts.abandoned_setup_ordinals, ())
        self.assertEqual(facts.terminated_setup_ordinals, ())
        self.assertEqual(facts.incomplete_setup_ordinals, ())

    def test_changed_prefix_is_abandoned_even_when_same_terminal_chord_occurs(self):
        physical, decisions, acquisitions = _detached_setup_streams(replanned=True)
        self.assertEqual(decisions[1].plan_actions[-1], (physical[-1].action, physical[-1].target))
        facts = game.derive_k_setup_facts_from_records(physical, decisions, acquisitions)
        self.assertEqual(facts.executed_setup_flags, 1)
        self.assertEqual(facts.selected_setup_ordinals, (1,))
        self.assertEqual(facts.abandoned_setup_ordinals, (1,))
        self.assertEqual(facts.realized_setup_ordinals, ())
        self.assertEqual(facts.terminated_setup_ordinals, ())
        self.assertEqual(facts.incomplete_setup_ordinals, ())

    def test_matching_short_prefix_distinguishes_terminal_from_incomplete(self):
        for terminal in (False, True):
            physical, decisions, acquisitions = _detached_setup_streams(prefix=2, terminal_prefix=terminal)
            facts = game.derive_k_setup_facts_from_records(physical, decisions, acquisitions)
            self.assertEqual(facts.selected_setup_ordinals, (1,))
            self.assertEqual(facts.realized_setup_ordinals, ())
            self.assertEqual(facts.abandoned_setup_ordinals, ())
            self.assertEqual(facts.terminated_setup_ordinals, (1,) if terminal else ())
            self.assertEqual(facts.incomplete_setup_ordinals, () if terminal else (1,))

    def test_setup_diagnostics_identical_after_only_record_encode_decode(self):
        for kwargs in ({}, {"replanned": True}, {"prefix": 2}, {"prefix": 2, "terminal_prefix": True}):
            streams = _detached_setup_streams(**kwargs)
            expected = game.derive_k_setup_facts_from_records(*streams)
            decoded = tuple(tuple(records.decode(records.encode(value)) for value in stream) for stream in streams)
            actual = game.derive_k_setup_facts_from_records(*decoded)
            self.assertEqual(actual, expected)
            self.assertFalse(hasattr(actual, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                actual.executed_setup_flags = 0


class BoundaryTests(unittest.TestCase):
    def test_ast_dependencies_and_no_new_solver_execution_loop(self):
        tree = ast.parse(inspect.getsource(game))
        allowed_projects = {"core_engine", "stage3_physical", "stage3_planner", "stage3_runner"}
        allowed_experiments = {"program_k_e2_records", "program_k_runner", "program_k_evidence",
                               "program_k_capability", "program_k_policy", "program_k_harness"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(n.name.split(".")[0] in sys.stdlib_module_names for n in node.names))
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                if node.module == "experiments":
                    self.assertTrue(all(n.name in allowed_experiments for n in node.names))
                elif node.module.startswith("experiments."):
                    self.assertIn(node.module.split(".")[1], allowed_experiments)
                    if node.module == "experiments.program_k_harness":
                        self.assertEqual(tuple(n.name for n in node.names), ("content_digest",))
                else:
                    self.assertTrue(node.module in allowed_projects or node.module.split(".")[0] in sys.stdlib_module_names)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, {"step", "generate_board", "extract_guess_checkpoints", "reconstruct",
                                                     "audit_acquisition", "run_k_control", "evaluate_execution_archives"})
                elif isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"eval", "exec", "__import__", "open", "generate_board",
                                                    "extract_guess_checkpoints", "run_stage3", "KLocalSession"})
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, {"mine_positions", "board_layout", "hidden_answer"})
                if isinstance(node.value, ast.Name) and node.value.id == "engine":
                    self.assertNotEqual(node.attr, "mines")

    def test_import_has_no_io_execution_process_or_host_capture(self):
        name = "_e2_i4_game_import_probe"
        source = compile(inspect.getsource(game), game.__file__, "exec")
        probe = types.ModuleType(name)
        with patch.dict(sys.modules, {name: probe}), ExitStack() as stack:
            for owner, attribute in ((builtins, "open"), (io, "open"), (os, "open"), (os, "getcwd"),
                                     (os, "getenv"), (Path, "read_bytes"), (Path, "write_bytes"),
                                     (subprocess, "Popen"), (subprocess, "run"),
                                     (runner, "run_control_capture"), (runner, "run_k_p0")):
                stack.enter_context(patch.object(owner, attribute, side_effect=AssertionError("import side effect")))
            exec(source, probe.__dict__)
        self.assertTrue(callable(probe.project_control))


if __name__ == "__main__":
    unittest.main()
