"""Slice-4/5/6/7 implementation/unit integration only; no E0/E1 or P-8 claim.

Tiny explicit layouts are confined to Engine construction below. Solver-facing
fixtures are raw public observations; no answer, fingerprint, evaluator or ZiNi
payload is passed to K. Synthetic status faults are labeled separately from
reachable Engine outcomes. Ordinary calls retain default SETUP_OPEN vocabulary.
"""

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction
from pathlib import Path
import pickle
import sys
import threading
from threading import Event, Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from experiments import program_k_runner as runner
from experiments import program_k_evidence as evidence_records
from experiments import program_k_oracles as public_oracles
from experiments import program_k_evaluator as evaluator
from experiments.program_k_capability import KIntegrityError, KLocalSession
from experiments.program_k_policy import KCandidate, select_policy
from simple_algorithm import Constraint, InferenceResult, SimpleMove
from simple_decision import DecisionKind
from stage3_physical import PROFILE_PATH, PROFILE_SHA256, TABLE_SHA256, load_timing_table
from stage3_planner import RevealPlan, Stage3Decision, plan_position
from stage3_runner import Stage3RunnerError, _validate_execution, run_stage3


H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)
PLAYING = GameStatus.PLAYING
HISTORICAL = ((1, H, 1, H),)
ONE_SETUP = ((1, H, 1, H), (1, 1, 1, H))
FLAGGED_PREFIX = ((1, F, 1, H), (1, 1, 1, H))
EXACT_TIE = ((1, H, H), (H, H, H))


def fixed_engine(width=4, height=1, mines=frozenset({(1, 0)})):
    """Answer layout belongs only to this test harness/Engine construction."""
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), mines)
    return engine


def public_decision(observation, mines):
    owner = KLocalSession(len(observation[0]), len(observation), mines)
    evidence = owner.analyze_decision(observation, status=PLAYING)
    return owner, evidence


def materialized_decision():
    owner, _ = public_decision(ONE_SETUP, 1)
    return owner, owner.analyze_decision(FLAGGED_PREFIX, status=PLAYING)


class Untouchable:
    """Any use of an answer-bearing step return is an isolation failure."""

    def __getattribute__(self, name):
        raise AssertionError("Program K consumed the Engine step return")

    def __getitem__(self, key):
        raise AssertionError("Program K indexed the Engine step return")

    def __iter__(self):
        raise AssertionError("Program K iterated the Engine step return")

    def __bool__(self):
        raise AssertionError("Program K tested the Engine step return")


class PublicPort:
    """Expose only allowed Engine inputs; log external status/observation order.

    Engine.step may internally create statistics and terminal observations.
    They are discarded here; the runner gets an untouchable return sentinel.
    The raw Engine is retained only by this harness adapter.
    """

    __slots__ = ("__engine", "events", "inputs", "override_status", "observation_fault")

    def __init__(self, engine):
        self.__engine = engine
        self.events = []
        self.inputs = []
        self.override_status = None
        self.observation_fault = None

    @property
    def width(self):
        return self.__engine.width

    @property
    def height(self):
        return self.__engine.height

    @property
    def num_mines(self):
        return self.__engine.num_mines

    @property
    def status(self):
        value = self.override_status or self.__engine.status
        self.events.append(("status", value))
        return value

    def get_observation(self):
        value = self.override_status or self.__engine.status
        if value is not PLAYING:
            raise AssertionError("Terminal observation must remain untouchable")
        observation = self.__engine.get_observation()
        if self.observation_fault is not None:
            observation = self.observation_fault(observation)
        self.events.append(("observation", tuple(tuple(row) for row in observation)))
        return observation

    def step(self, x, y, action):
        move = SimpleMove(action, x, y)
        self.events.append(("step", move))
        self.inputs.append(move)
        self.__engine.step(x, y, action)
        return Untouchable()

    def __getattr__(self, name):
        raise AssertionError(f"Program K accessed forbidden Engine channel: {name}")


class SyntheticSetupPrefixPort:
    """Declared public-prefix fixture for the two-FLAG dispatch boundary only.

    The first dispatch installs a public premise; it is NOT a claim that a
    positive OPEN floods to that premise in Engine. The outside clues (0,0)
    and (4,0) independently prove the two HIDDEN mines. The center clue (2,1)
    has three remaining safe HIDDEN neighbors. Later FLAG effects are physical
    one-cell transitions. Tests stop before any synthetic reveal continuation.
    """

    width, height, num_mines = 5, 3, 2
    status = PLAYING

    def __init__(self):
        self.observation = ((H,) * self.width,) * self.height
        self.inputs = []

    def get_observation(self):
        return self.observation

    def step(self, x, y, action):
        move = SimpleMove(action, x, y)
        if not self.inputs:
            if move != SimpleMove(Action.OPEN, 0, 0):
                raise AssertionError("Expected canonical initial dispatch")
            self.observation = ((1, 1, 2, 1, 1), (1, H, 2, H, 1), (1, H, H, H, 1))
        else:
            if action is not Action.FLAG or self.observation[y][x] != H:
                raise AssertionError("Only the first fresh setup FLAG is expected")
            self.observation = tuple(tuple(F if (cx, cy) == (x, y) else value
                                           for cx, value in enumerate(row))
                                     for cy, row in enumerate(self.observation))
        self.inputs.append(move)
        return Untouchable()

    def __getattr__(self, name):
        raise AssertionError(f"Forbidden synthetic port access: {name}")


class ProgramKExecutionValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def selection(self, observation=HISTORICAL, mines=1, cursor=(0, 0)):
        owner, evidence = public_decision(observation, mines)
        return owner, select_policy(evidence, cursor, self.table)

    def validate(self, selection, *, observation=None, move=None, **changes):
        evidence = selection.evidence
        kwargs = dict(status=PLAYING, num_mines=evidence.num_mines,
                      cursor=selection.cursor, current_mines=evidence.after.M,
                      decision=evidence, selection=selection)
        kwargs.update(changes)
        return runner.validate_k_p0_execution(
            evidence.observation if observation is None else observation,
            selection.move if move is None else move, **kwargs,
        )

    def forged_plan(self, selection, move, category, *, reveals=()):
        """Deliberately malformed authority for negative validator tests only."""
        plan = RevealPlan((move,), 126005, len(reveals))
        item = KCandidate(plan, category, frozenset(), frozenset(reveals))
        return replace(selection, move=move, plan=plan, category=category,
                       candidates=(item,), survivors=(item,))

    def test_a_initial_validator_accepts_only_canonical_public_start(self):
        kwargs = dict(status=PLAYING, num_mines=1, cursor=(0, 0),
                      current_mines=frozenset(), initial=True)
        runner.validate_k_p0_execution(((H, H, H),), SimpleMove(Action.OPEN, 0, 0), **kwargs)
        cases = (
            (((0, H, H),), SimpleMove(Action.OPEN, 0, 0), {}),
            (((H, H, H),), SimpleMove(Action.OPEN, 1, 0), {}),
            (((H, H, H),), SimpleMove(Action.FLAG, 0, 0), {}),
            (((H, H, H),), SimpleMove(Action.OPEN, 0, 0), {"cursor": (1, 0)}),
            (((H, H, H),), SimpleMove(Action.OPEN, 0, 0),
             {"current_mines": frozenset({(1, 0)})}),
        )
        for observation, move, changed in cases:
            with self.subTest(observation=observation, move=move, changed=changed):
                with self.assertRaises(runner.KExecutionError):
                    runner.validate_k_p0_execution(observation, move, **(kwargs | changed))

    def test_d_historical_direct_open_retains_logical_mine_without_flag(self):
        owner, selected = self.selection()
        self.assertEqual(owner.M, {(1, 0)})
        self.assertEqual(selected.evidence.after.P, frozenset())
        self.assertEqual(selected.move, SimpleMove(Action.OPEN, 3, 0))
        self.assertEqual(selected.category, "DIRECT_SAFE_OPEN")
        self.validate(selected, current_mines=owner.M)
        self.assertEqual(owner.M, {(1, 0)})

    def test_f_stale_observation_and_unrelated_decision_are_rejected(self):
        _, selected = self.selection()
        for observation in (((1, F, 1, H),), ((1, H, 1, 0),), ((H, H, 1, H),)):
            with self.subTest(observation=observation), self.assertRaises(runner.KExecutionError):
                self.validate(selected, observation=observation)
        _, other = public_decision(((1, H, H, H),), 2)
        with self.assertRaises(runner.KExecutionError):
            self.validate(selected, decision=other)
        # Equal public values do not make an archived policy the policy of a
        # newly produced decision. The runner passes its fresh object separately.
        _, equal_fresh = public_decision(HISTORICAL, 1)
        self.assertEqual(equal_fresh, selected.evidence)
        self.assertIsNot(equal_fresh, selected.evidence)
        with self.assertRaises(runner.KExecutionError):
            self.validate(selected, decision=equal_fresh)

    def test_g_cursor_mismatch_rejected(self):
        _, selected = self.selection()
        with self.assertRaises(runner.KExecutionError):
            self.validate(selected, cursor=(3, 0))
        with self.assertRaises(runner.KExecutionError):
            self.validate(replace(selected, cursor=(False, 0)), cursor=(0, 0))

    def test_h_current_m_mismatch_even_with_identical_public_observation(self):
        _, selected = self.selection()
        for current in (frozenset(), frozenset({(1, 0), (3, 0)})):
            with self.subTest(current=current), self.assertRaises(runner.KExecutionError):
                self.validate(selected, current_mines=current)

    def test_i_safe_open_requires_actual_hidden_current_safe_target(self):
        _, selected = self.selection()
        self.validate(selected)
        for cell in ((0, 0), (1, 0), (2, 0)):
            bad = self.forged_plan(selected, SimpleMove(Action.OPEN, *cell),
                                   "DIRECT_SAFE_OPEN", reveals={cell})
            with self.subTest(cell=cell), self.assertRaises(runner.KExecutionError):
                self.validate(bad)
        _, evidence = materialized_decision()
        selected = select_policy(evidence, (0, 0), self.table)
        bad = self.forged_plan(selected, SimpleMove(Action.OPEN, 1, 0),
                               "DIRECT_SAFE_OPEN", reveals={(1, 0)})
        with self.assertRaises(runner.KExecutionError):
            self.validate(bad)

    def test_j_exact_guess_accepts_complete_minimum_and_cursor_cannot_change_winner(self):
        owner, evidence = public_decision(EXACT_TIE, 2)
        for cursor in ((0, 0), (0, 1), (2, 1)):
            selected = select_policy(evidence, cursor, self.table)
            self.assertEqual(selected.move, SimpleMove(Action.OPEN, 1, 0))
            self.assertEqual(evidence.phase_e.minimum_risk, Fraction(1, 3))
            self.assertEqual(evidence.phase_e.minimum_risk_cells, {(1, 0), (0, 1), (1, 1)})
            self.assertIsNone(selected.plan)
            self.validate(selected, current_mines=owner.M)

    def test_j_exact_guess_rejects_changed_winner_incomplete_minimum_and_risk_zero_one(self):
        _, selected = self.selection(EXACT_TIE, 2)
        evidence = selected.evidence
        malformed = (
            replace(evidence, guess_target=(0, 1)),
            replace(evidence, phase_e=replace(evidence.phase_e,
                                             minimum_risk_cells=frozenset({(1, 0)}))),
            replace(evidence, phase_e=replace(evidence.phase_e, minimum_risk=Fraction(0))),
            replace(evidence, phase_e=replace(evidence.phase_e, minimum_risk=Fraction(1))),
            replace(evidence, phase_d=None),
            replace(evidence, selection_safe_cells=frozenset({(1, 0)})),
        )
        for bad in malformed:
            with self.subTest(evidence=bad), self.assertRaises(runner.KExecutionError):
                self.validate(replace(selected, evidence=bad))
        for changed in (
            {"move": SimpleMove(Action.OPEN, 0, 1)},
            {"move": SimpleMove(Action.OPEN, 2, 0)},
            {"plan": RevealPlan((selected.move,), 126005, 1)},
            {"candidates": (object(),)},
            {"survivors": (object(),)},
        ):
            with self.subTest(changed=changed), self.assertRaises(runner.KExecutionError):
                self.validate(replace(selected, **changed))

    def test_j_exact_guess_rejects_missing_duplicate_or_noninteger_marginals(self):
        _, selected = self.selection(EXACT_TIE, 2)
        evidence = selected.evidence
        exact = evidence.phase_e
        for counts in (exact.mine_worlds[:-1], exact.mine_worlds + exact.mine_worlds[:1],
                       (((1, 0), 0),) + exact.mine_worlds[1:],
                       (((1, 0), exact.total_worlds),) + exact.mine_worlds[1:],
                       (((1, 0), True),) + exact.mine_worlds[1:]):
            bad = replace(evidence, phase_e=replace(exact, mine_worlds=counts))
            with self.subTest(counts=counts), self.assertRaises(runner.KExecutionError):
                self.validate(replace(selected, evidence=bad))

    def test_k_flag_requires_hidden_current_m_first_surviving_setup_chord(self):
        owner, selected = self.selection(ONE_SETUP, 1)
        self.assertEqual(selected.category, "SETUP_CHORD")
        self.assertEqual(selected.move, SimpleMove(Action.FLAG, 1, 0))
        self.assertEqual(selected.plan.actions[0], selected.move)
        self.assertIn(selected.plan, tuple(item.plan for item in selected.survivors))
        self.validate(selected, current_mines=owner.M)
        malformed = (
            replace(selected, survivors=()),
            replace(selected, candidates=()),
            replace(selected, category="V1_FLAG_FALLBACK"),
            replace(selected, category="DIRECT_SAFE_OPEN"),
            replace(selected, plan=None),
            replace(selected, move=selected.plan.actions[-1]),
            replace(selected, move=SimpleMove(Action.FLAG, 3, 0)),
        )
        for bad in malformed:
            with self.subTest(selection=bad), self.assertRaises(runner.KExecutionError):
                self.validate(bad)
        standalone = self.forged_plan(selected, selected.move, "SETUP_CHORD", reveals={(3, 0)})
        with self.assertRaises(runner.KExecutionError):
            self.validate(standalone)

    def test_l_actual_physical_flags_enable_productive_chord(self):
        owner, evidence = materialized_decision()
        selected = select_policy(evidence, (0, 0), self.table)
        self.assertEqual(selected.move, SimpleMove(Action.CHORD, 2, 0))
        self.assertEqual(evidence.after.P, {(1, 0)})
        self.assertEqual(evidence.selection_safe_cells, {(3, 0), (3, 1)})
        self.validate(selected, current_mines=owner.M)

    def test_l_logical_unmaterialized_mine_is_not_a_physical_flag(self):
        _, selected = self.selection(ONE_SETUP, 1)
        attempted_chord = self.forged_plan(selected, SimpleMove(Action.CHORD, 2, 0),
                                          "DIRECT_CHORD", reveals={(3, 0), (3, 1)})
        self.assertEqual(selected.evidence.after.P, frozenset())
        with self.assertRaises(runner.KExecutionError):
            self.validate(attempted_chord)

    def test_l_chord_requires_positive_revealed_clue_and_nonempty_safe_hidden_set(self):
        _, evidence = materialized_decision()
        selected = select_policy(evidence, (0, 0), self.table)
        for cell in ((1, 0), (3, 0), (0, 0)):
            bad = self.forged_plan(selected, SimpleMove(Action.CHORD, *cell),
                                   "DIRECT_CHORD", reveals={(3, 0), (3, 1)})
            with self.subTest(cell=cell), self.assertRaises(runner.KExecutionError):
                self.validate(bad)
        _, zero = self.selection(((0, H),), 0)
        bad = self.forged_plan(zero, SimpleMove(Action.CHORD, 0, 0),
                               "DIRECT_CHORD", reveals={(1, 0)})
        with self.assertRaises(runner.KExecutionError):
            self.validate(bad)
        bad_evidence = replace(evidence, selection_safe_cells=frozenset({(3, 0)}))
        with self.assertRaises(runner.KExecutionError):
            self.validate(replace(selected, evidence=bad_evidence))

    def test_common_action_status_metadata_and_selected_input_checks_fail_closed(self):
        _, selected = self.selection()
        for move in (SimpleMove(Action.OPEN, -1, 0), SimpleMove(Action.OPEN, 4, 0),
                     SimpleMove(Action.OPEN, True, 0), SimpleMove(99, 3, 0), None):
            bad = replace(selected, move=move)
            with self.subTest(move=move), self.assertRaises(runner.KExecutionError):
                self.validate(bad)
        with self.assertRaises(runner.KExecutionError):
            self.validate(selected, move=SimpleMove(Action.OPEN, 1, 0))
        for status in (GameStatus.WON, GameStatus.LOST, 0, None):
            with self.subTest(status=status), self.assertRaises(runner.KExecutionError):
                self.validate(selected, status=status)
        with self.assertRaises(runner.KExecutionError):
            self.validate(selected, num_mines=2)


class ProgramKTreatmentRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def assert_status_first(self, port):
        for index, event in enumerate(port.events):
            if event[0] == "step":
                self.assertEqual(port.events[index + 1][0], "status")
                if port.events[index + 1][1] is not PLAYING:
                    self.assertFalse(any(item[0] in ("observation", "analysis", "policy", "step")
                                         for item in port.events[index + 2:]))

    def traced_run(self, port):
        original_analysis = KLocalSession.analyze_decision
        analyses, selections = [], []

        def analyze(owner, observation, *, status):
            self.assertTrue(port.inputs, "K analysis preceded canonical OPEN")
            self.assertIs(status, PLAYING)
            public_reads = [item[1] for item in port.events if item[0] == "observation"]
            self.assertEqual(tuple(tuple(row) for row in observation), public_reads[-1])
            port.events.append(("analysis", tuple(tuple(row) for row in observation)))
            evidence = original_analysis(owner, observation, status=status)
            analyses.append(evidence)
            return evidence

        def select(evidence, cursor, table, **kwargs):
            self.assertIs(evidence, analyses[-1])
            self.assertEqual(cursor, (port.inputs[-1].x, port.inputs[-1].y))
            self.assertNotEqual(kwargs.get("include_setup_open"), False)
            port.events.append(("policy", cursor))
            chosen = select_policy(evidence, cursor, table, **kwargs)
            selections.append(chosen)
            return chosen

        with patch.object(KLocalSession, "analyze_decision", new=analyze), \
                patch.object(runner, "select_policy", side_effect=select):
            result = runner.run_k_p0(port, table=self.table)
        self.assertEqual(len(analyses), len(result.traces) - 1)
        self.assertEqual(len(selections), len(analyses))
        self.assertEqual(tuple(port.inputs), result.moves)
        for index, trace in enumerate(result.traces[1:]):
            self.assertIs(trace.selection, selections[index])
            self.assertIs(trace.selection.evidence, analyses[index])
            self.assertEqual(trace.move, selections[index].move)
            self.assertEqual(trace.preinput_M, analyses[index].after.M)
        self.assert_status_first(port)
        return result

    def test_a_canonical_initial_input_empty_m_cursor_marker_and_frozen_cost(self):
        port = PublicPort(fixed_engine())
        result = self.traced_run(port)
        first = result.traces[0]
        self.assertEqual(first.input_index, 0)
        self.assertEqual(first.move, SimpleMove(Action.OPEN, 0, 0))
        self.assertEqual(first.category, "POLICY_INITIAL_OPEN")
        self.assertEqual(first.cursor_before, (0, 0))
        self.assertEqual(first.M_before, frozenset())
        self.assertEqual(first.preinput_M, frozenset())
        self.assertIsNone(first.selection)
        self.assertEqual(first.modeled_action_us, 126005)
        initial_observation = next(item[1] for item in port.events if item[0] == "observation")
        self.assertEqual(initial_observation, ((H, H, H, H),))

    def test_b_progressed_playing_start_rejected_without_any_input(self):
        engine = fixed_engine()
        engine.step(0, 0, Action.OPEN)
        port = PublicPort(engine)
        with patch.object(runner, "select_policy", side_effect=AssertionError("policy")), \
                patch.object(KLocalSession, "analyze_decision", side_effect=AssertionError("analysis")):
            with self.assertRaises(KIntegrityError):
                runner.run_k_p0(port, table=self.table)
        self.assertEqual(port.inputs, [])

    def test_c_initial_won_and_lost_status_stop_before_any_solver_or_terminal_observation(self):
        cases = ((3, {(2, 0)}, GameStatus.WON), (2, {(0, 0)}, GameStatus.LOST))
        for width, mines, expected in cases:
            port = PublicPort(fixed_engine(width, 1, frozenset(mines)))
            with self.subTest(expected=expected), \
                    patch.object(runner, "select_policy", side_effect=AssertionError("policy")), \
                    patch.object(KLocalSession, "analyze_decision", side_effect=AssertionError("analysis")), \
                    patch.object(KLocalSession, "analyze_local", side_effect=AssertionError("local")):
                result = runner.run_k_p0(port, table=self.table)
            self.assertIs(result.status, expected)
            self.assertEqual(result.moves, (SimpleMove(Action.OPEN, 0, 0),))
            self.assertEqual(result.final_M, frozenset())
            self.assertEqual(result.total_modeled_us, 126005)
            self.assert_status_first(port)

    def test_d_real_complete_run_directly_opens_without_materializing_m(self):
        result = self.traced_run(PublicPort(fixed_engine()))
        self.assertIs(result.status, GameStatus.WON)
        self.assertEqual(result.moves, (SimpleMove(Action.OPEN, 0, 0),
                                       SimpleMove(Action.OPEN, 2, 0),
                                       SimpleMove(Action.OPEN, 3, 0)))
        self.assertEqual(result.final_M, {(1, 0)})
        self.assertTrue(all(move.action is Action.OPEN for move in result.moves))
        self.assertEqual(result.traces[1].category, "DIRECT_SAFE_OPEN")
        self.assertEqual(result.traces[1].preinput_M, {(1, 0)})

    def test_e_n_o_real_setup_execution_always_reanalyzes_before_next_input(self):
        # Explicit small geometry chosen to expose a two-mine neighborhood;
        # no generator/corpus/holdout search or official identity is involved.
        port = PublicPort(fixed_engine(5, 4, frozenset({(1, 2), (3, 2)})))
        result = self.traced_run(port)
        setups = [trace for trace in result.traces if trace.category == "SETUP_CHORD"]
        self.assertTrue(setups, "Declared mechanism fixture must exercise setup")
        for trace in setups:
            self.assertEqual(trace.move, trace.selection.plan.actions[0])
            self.assertIs(trace.move.action, Action.FLAG)
        for previous, fresh in zip(result.traces, result.traces[1:]):
            self.assertEqual(fresh.cursor_before, (previous.move.x, previous.move.y))
            self.assertEqual(fresh.M_before, previous.preinput_M)
            self.assertIsNot(fresh.selection, previous.selection)
        step_indices = [index for index, item in enumerate(port.events) if item[0] == "step"]
        for left, right in zip(step_indices, step_indices[1:]):
            interval = [item[0] for item in port.events[left + 1:right]]
            self.assertIn("observation", interval)
            self.assertEqual(interval.count("analysis"), 1)
            self.assertEqual(interval.count("policy"), 1)

    def test_n_multi_flag_plan_suffix_has_no_authority_when_fresh_analysis_fails(self):
        port = SyntheticSetupPrefixPort()
        original = KLocalSession.analyze_decision
        selected_multi = []

        def analyze(owner, observation, *, status):
            if selected_multi:
                raise RuntimeError("fresh analysis stopped before any suffix")
            return original(owner, observation, status=status)

        def choose(evidence, cursor, table):
            selected = select_policy(evidence, cursor, table)
            if selected.category == "SETUP_CHORD" and len(selected.plan.actions) >= 3:
                selected_multi.append((selected, len(port.inputs)))
            return selected

        with patch.object(KLocalSession, "analyze_decision", new=analyze), \
                patch.object(runner, "select_policy", side_effect=choose):
            with self.assertRaisesRegex(RuntimeError, "fresh analysis stopped"):
                runner.run_k_p0(port, table=self.table)
        self.assertEqual(len(selected_multi), 1)
        selected, index = selected_multi[0]
        self.assertEqual(port.inputs[index:], [selected.plan.actions[0]])
        self.assertIs(port.inputs[-1].action, Action.FLAG)
        self.assertIs(port.status, PLAYING)

    def test_f_live_observation_change_during_selection_rejects_before_next_input(self):
        port = PublicPort(fixed_engine())

        def intervene(evidence, cursor, table):
            selected = select_policy(evidence, cursor, table)
            # Inject a current public-state change after the bound decision.
            # No hidden truth or alternate action is given to the runner.
            port.observation_fault = lambda rows: [[1, H, 1, H]]
            return selected

        with patch.object(runner, "select_policy", side_effect=intervene):
            with self.assertRaises(runner.KExecutionError):
                runner.run_k_p0(port, table=self.table)
        self.assertEqual(port.inputs, [SimpleMove(Action.OPEN, 0, 0)])

    def test_g_m_policy_cursor_fault_performs_zero_additional_engine_inputs(self):
        port = PublicPort(fixed_engine())

        def wrong_cursor(evidence, cursor, table):
            return replace(select_policy(evidence, cursor, table), cursor=(3, 0))

        with patch.object(runner, "select_policy", side_effect=wrong_cursor):
            with self.assertRaises(runner.KExecutionError):
                runner.run_k_p0(port, table=self.table)
        self.assertEqual(port.inputs, [SimpleMove(Action.OPEN, 0, 0)])

    def test_preinput_status_change_rejects_without_observation_or_second_input(self):
        for terminal in (GameStatus.WON, GameStatus.LOST):
            port = PublicPort(fixed_engine())

            def terminate_during_selection(evidence, cursor, table):
                selected = select_policy(evidence, cursor, table)
                port.override_status = terminal  # Synthetic concurrent-status fault.
                return selected

            with self.subTest(terminal=terminal), \
                    patch.object(runner, "select_policy", side_effect=terminate_during_selection):
                with self.assertRaises(runner.KExecutionError):
                    runner.run_k_p0(port, table=self.table)
            self.assertEqual(port.inputs, [SimpleMove(Action.OPEN, 0, 0)])

    def test_h_live_owner_m_mismatch_stops_before_policy_action(self):
        port = PublicPort(fixed_engine())
        original = KLocalSession.analyze_decision

        def mismatched(owner, observation, *, status):
            evidence = original(owner, observation, status=status)
            owner._M = frozenset()  # Deliberate ownership fault, not repaired.
            return evidence

        with patch.object(KLocalSession, "analyze_decision", new=mismatched):
            with self.assertRaises(runner.KExecutionError):
                runner.run_k_p0(port, table=self.table)
        self.assertEqual(port.inputs, [SimpleMove(Action.OPEN, 0, 0)])

    def test_m_initial_validation_failure_executes_zero_inputs(self):
        port = PublicPort(fixed_engine())
        with patch.object(runner, "validate_k_p0_execution",
                          side_effect=runner.KExecutionError("FAULT", "injected validator failure")):
            with self.assertRaises(runner.KExecutionError):
                runner.run_k_p0(port, table=self.table)
        self.assertEqual(port.inputs, [])

    def test_p_terminal_later_open_archives_last_legitimate_m(self):
        result = self.traced_run(PublicPort(fixed_engine()))
        self.assertIs(result.traces[-1].move.action, Action.OPEN)
        self.assertIs(result.status, GameStatus.WON)
        self.assertEqual(result.final_M, result.traces[-1].preinput_M)
        self.assertEqual(result.final_M, {(1, 0)})

    def test_p_terminal_override_after_real_valid_chord_stops_before_any_inference(self):
        # Status fault only: the real fixture's CHORD is ordinarily nonterminal.
        # The actual physical CHORD still uses real flags and current K safety.
        port = PublicPort(fixed_engine(5, 4, frozenset({(1, 2), (3, 2)})))
        original_step = PublicPort.step

        def terminal_chord(view, x, y, action):
            payload = original_step(view, x, y, action)
            if action is Action.CHORD:
                view.override_status = GameStatus.WON
            return payload

        with patch.object(PublicPort, "step", new=terminal_chord):
            result = self.traced_run(port)
        self.assertIs(result.status, GameStatus.WON)
        self.assertIs(result.traces[-1].move.action, Action.CHORD)
        self.assertEqual(result.final_M, {(1, 2), (3, 2)})
        self.assertEqual(result.final_M, result.traces[-1].preinput_M)

    def test_p_synthetic_terminal_flag_barrier_archives_m_without_inference(self):
        # A valid physical FLAG cannot newly win/lose an ordinary PLAYING Engine.
        # This injected port status tests the unconditional terminal guard only;
        # it is not claimed as a naturally reachable game or research outcome.
        original_step = PublicPort.step
        for terminal in (GameStatus.WON, GameStatus.LOST):
            port = PublicPort(fixed_engine(5, 4, frozenset({(1, 2), (3, 2)})))

            def terminal_flag(view, x, y, action):
                payload = original_step(view, x, y, action)
                if action is Action.FLAG:
                    view.override_status = terminal
                return payload

            with self.subTest(terminal=terminal), patch.object(PublicPort, "step", new=terminal_flag):
                result = self.traced_run(port)
            self.assertIs(result.status, terminal)
            self.assertIs(result.traces[-1].move.action, Action.FLAG)
            self.assertTrue(result.final_M)
            self.assertEqual(result.final_M, result.traces[-1].preinput_M)

    def test_q_fixed_small_board_complete_run_is_deterministic_on_fresh_engines(self):
        first = runner.run_k_p0(PublicPort(fixed_engine()), table=self.table)
        second = runner.run_k_p0(PublicPort(fixed_engine()), table=self.table)
        self.assertEqual(first, second)
        self.assertIs(first.status, GameStatus.WON)
        self.assertEqual(first.moves, second.moves)
        self.assertEqual(first.traces, second.traces)

    def test_r_legitimate_exact_guess_loss_is_preserved_without_retry(self):
        port = PublicPort(fixed_engine(5, 1, frozenset({(1, 0), (2, 0)})))
        result = self.traced_run(port)
        self.assertIs(result.status, GameStatus.LOST)
        self.assertEqual(result.moves, (SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.OPEN, 2, 0)))
        last = result.traces[-1]
        self.assertEqual(last.category, "EXACT_MINIMUM_RISK_GUESS")
        self.assertEqual(last.selection.evidence.phase_e.minimum_risk, Fraction(1, 3))
        self.assertEqual(result.final_M, {(1, 0)})
        self.assertEqual(result.final_M, last.preinput_M)

    def test_s_t_authenticated_costs_use_actual_cursor_and_sum_only_executed_inputs(self):
        engines = (fixed_engine(), fixed_engine(5, 4, frozenset({(1, 2), (3, 2)})))
        actions = set()
        saw_setup = False
        for engine in engines:
            result = runner.run_k_p0(PublicPort(engine), table=self.table)
            cursor, total = (0, 0), 0
            for index, trace in enumerate(result.traces):
                self.assertEqual(trace.input_index, index)
                self.assertEqual(trace.cursor_before, cursor)
                expected = self.table[abs(trace.move.x - cursor[0])][abs(trace.move.y - cursor[1])]
                self.assertIs(type(trace.modeled_action_us), int)
                self.assertEqual(trace.modeled_action_us, expected)
                actions.add(trace.move.action)
                if trace.category == "SETUP_CHORD":
                    saw_setup = True
                    self.assertLess(trace.modeled_action_us, trace.selection.plan.latency_us)
                total += expected
                cursor = (trace.move.x, trace.move.y)
            self.assertEqual(result.total_modeled_us, total)
            self.assertEqual(result.total_modeled_us, sum(trace.modeled_action_us for trace in result.traces))
        self.assertTrue(saw_setup)
        self.assertEqual(actions, {Action.OPEN, Action.FLAG, Action.CHORD})

    def test_s_changed_or_malformed_timing_table_rejected_before_initial_input(self):
        changed = [list(row) for row in self.table]
        changed[0][0] += 1
        for table in (changed, (), ((True,),)):
            port = PublicPort(fixed_engine())
            with self.subTest(table=table), self.assertRaises(ValueError):
                runner.run_k_p0(port, table=table)
            self.assertEqual(port.inputs, [])

    def test_progress_failure_stops_without_retry_or_error_to_loss_conversion(self):
        port = PublicPort(fixed_engine())
        with patch.object(PublicPort, "step", return_value=Untouchable()) as step:
            with self.assertRaises(KIntegrityError):
                runner.run_k_p0(port, table=self.table)
        self.assertEqual(step.call_count, 1)
        self.assertIs(port.status, PLAYING)
        port = PublicPort(fixed_engine())
        with patch.object(runner, "select_policy", side_effect=RuntimeError("planning defect")):
            with self.assertRaisesRegex(RuntimeError, "planning defect"):
                runner.run_k_p0(port, table=self.table)
        self.assertEqual(port.inputs, [SimpleMove(Action.OPEN, 0, 0)])

    def test_u_narrow_public_port_step_sentinel_and_source_import_boundary(self):
        port = PublicPort(fixed_engine())
        result = runner.run_k_p0(port, table=self.table)
        self.assertIs(result.status, GameStatus.WON)
        source = Path(runner.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        forbidden_attributes = {"get_board_snapshot", "get_counter_snapshot", "get_stats",
                                "_mines", "_adjacent", "fingerprint", "zini", "evaluator"}
        self.assertFalse(attributes & forbidden_attributes)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        self.assertFalse(imports & {"simple_runner", "board_snapshot", "zini_core",
                                    "benchmark_board", "benchmark_runner", "experiments.program_k_evaluator"})
        # Slice 5 permits frozen V1 APIs only for K-CONTROL. K-P0's authority
        # remains its existing capability, policy and separate validator.
        for function in ("run_k_p0", "validate_k_p0_execution"):
            body = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == function)
            calls = {node.id for node in ast.walk(body) if isinstance(node, ast.Name)}
            self.assertFalse(calls & {"_validate_execution", "plan_position", "run_stage3"})

    def test_v_results_trace_and_all_nested_evidence_are_immutable_detached_values(self):
        port = PublicPort(fixed_engine())
        result = runner.run_k_p0(port, table=self.table)
        self.assertIs(type(result.traces), tuple)
        self.assertIs(type(result.final_M), frozenset)
        with self.assertRaises(FrozenInstanceError):
            result.status = PLAYING
        with self.assertRaises(FrozenInstanceError):
            result.traces[0].category = "OTHER"
        with self.assertRaises(FrozenInstanceError):
            result.traces[1].selection.evidence.after.b = 999

        def verify_detached(value):
            self.assertNotIsInstance(value, (MinesweeperEngine, PublicPort, KLocalSession))
            if is_dataclass(value):
                self.assertTrue(type(value).__dataclass_params__.frozen)
                for field in fields(value):
                    verify_detached(getattr(value, field.name))
            elif isinstance(value, (tuple, frozenset)):
                for item in value:
                    verify_detached(item)
            else:
                self.assertIsInstance(value, (str, int, Fraction, type(None)))

        verify_detached(result)


class ProgramKControlRunnerTests(unittest.TestCase):
    """Bounded implementation fixtures only, never the E1 scheduled suite.

    CONTROL is always the unchanged production run_stage3. Its terminal
    observations belong to that production runner and never feed K-CONTROL.
    The comparison below checks physical inputs/cursors/cost/outcome; full O-4
    persistence, public effects, qualification and hidden truth are excluded.
    """

    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def assert_physical_identity(self, actual, control):
        self.assertEqual(actual.moves, control.moves)
        self.assertEqual(actual.status, control.status)
        self.assertEqual(actual.total_modeled_us, control.total_modeled_us)
        self.assertEqual(
            tuple((t.cursor_before, t.modeled_action_us, t.status_after) for t in actual.traces),
            tuple((t.cursor_before, t.modeled_action_us, t.status_after) for t in control.traces),
        )

    def assert_status_first(self, port):
        for index, event in enumerate(port.events):
            if event[0] == "step":
                self.assertEqual(port.events[index + 1][0], "status")
                if port.events[index + 1][1] is not PLAYING:
                    self.assertFalse(any(item[0] in ("observation", "shadow", "step")
                                         for item in port.events[index + 2:]))

    def assert_disabled(self, result, failure_class, boundary=1, last_valid=None):
        shadow = result.shadow
        self.assertFalse(shadow.enabled)
        self.assertFalse(shadow.evidence_valid)
        self.assertIsNone(shadow.decision)
        self.assertTrue(shadow.v1_continues)
        self.assertEqual(shadow.failure.failure_class, failure_class)
        self.assertEqual(shadow.failure.detected_boundary, boundary)
        self.assertEqual(shadow.failure.last_valid_boundary, last_valid)
        self.assertEqual(shadow.last_valid_boundary, last_valid)
        for trace in result.traces[boundary:]:
            self.assertFalse(trace.shadow.enabled)
            self.assertFalse(trace.shadow.evidence_valid)
            self.assertIsNone(trace.shadow.decision)
            self.assertEqual(trace.shadow.failure, shadow.failure)

    def test_a_canonical_initial_input_matches_control_without_shadow_work(self):
        control = run_stage3(fixed_engine(), table=self.table)
        result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        actual, expected = result.traces[0], control.traces[0]
        self.assertEqual(actual.move, SimpleMove(Action.OPEN, 0, 0))
        self.assertEqual(actual.move, expected.move)
        self.assertEqual(actual.cursor_before, expected.cursor_before)
        self.assertEqual(actual.modeled_action_us, expected.modeled_action_us)
        self.assertEqual(actual.modeled_action_us, 126005)
        self.assertIsNone(actual.decision)
        self.assertEqual(actual.M_before, frozenset())
        self.assertEqual(actual.preinput_M, frozenset())
        self.assertIsNone(actual.shadow.decision)
        self.assertTrue(actual.shadow.enabled)

    def test_b_v1_planner_validator_cost_and_seal_precede_detached_shadow(self):
        port = PublicPort(fixed_engine())
        original = runner._analyze_shadow
        boundaries, sealed, inputs = [], [], []
        code_names = {
            plan_position.__code__: "plan",
            _validate_execution.__code__: "validate",
            runner.action_cost.__code__: "cost",
            runner._SealedV1Input.__init__.__code__: "seal",
        }

        def profile(frame, event, value):
            if event == "return" and frame.f_code in code_names:
                name = code_names[frame.f_code]
                boundaries.append(name)
                if name == "seal":
                    sealed.append(frame.f_locals["self"])

        def shadow(snapshot):
            self.assertTrue(sealed)
            self.assertEqual(boundaries[-1], "seal")
            latest = sealed[-1]
            self.assertEqual(latest.observation, snapshot.observation)
            self.assertEqual(latest.cursor_before, snapshot.cursor)
            self.assertEqual(latest.move, latest.decision.move)
            expected = self.table[abs(latest.move.x - snapshot.cursor[0])][
                abs(latest.move.y - snapshot.cursor[1])]
            self.assertEqual(latest.modeled_action_us, expected)
            seal_index = len(boundaries) - 1
            validation = max(i for i, name in enumerate(boundaries[:seal_index]) if name == "validate")
            self.assertIn("plan", boundaries[:validation])
            self.assertIn("cost", boundaries[validation + 1:seal_index])
            with self.assertRaises(FrozenInstanceError):
                latest.move = SimpleMove(Action.OPEN, 3, 0)
            inputs.append(snapshot)
            return original(snapshot)

        previous_profile = sys.getprofile()
        try:
            sys.setprofile(profile)
            with patch.object(runner, "_analyze_shadow", side_effect=shadow), \
                    patch.object(runner, "select_policy", side_effect=AssertionError("K-P0 authority")):
                result = runner.run_k_control(port, table=self.table)
        finally:
            sys.setprofile(previous_profile)
        self.assertTrue(result.shadow.enabled, result.shadow.failure)
        self.assertEqual(len(inputs), len(result.traces) - 1)
        noninitial = [item for item in sealed if item.decision is not None]
        self.assertEqual(len(noninitial), len(inputs))
        for seal, trace in zip(noninitial, result.traces[1:]):
            self.assertEqual(trace.move, seal.move)
            self.assertEqual(trace.decision, seal.decision)
            self.assertEqual(trace.cursor_before, seal.cursor_before)
            self.assertEqual(trace.modeled_action_us, seal.modeled_action_us)
        self.assertEqual(tuple(port.inputs), result.moves)
        self.assert_status_first(port)

    def test_c_e_g_executed_v1_flag_admission_accepts_empty_shadow_m(self):
        """Compose real V1 execution with the runner's admission boundary.

        The empty shadow is a deliberately supplied current unit snapshot. It
        does not claim a natural canonical run produced this scheduling gap.
        Every physical flag here comes from an actually executed, unchanged
        frozen planner/validator action; no shadow analysis is fabricated.
        """
        port = PublicPort(fixed_engine())
        initial = SimpleMove(Action.OPEN, 0, 0)
        observation = tuple(tuple(row) for row in port.get_observation())
        _validate_execution(observation, initial, None)
        port.step(initial.x, initial.y, initial.action)
        self.assertIs(port.status, PLAYING)
        observation = tuple(tuple(row) for row in port.get_observation())
        flag_decision = plan_position(observation, port.num_mines, (0, 0), self.table)
        flag = flag_decision.move
        self.assertEqual(flag, SimpleMove(Action.FLAG, 1, 0))
        self.assertIsNone(flag_decision.plan)  # Frozen V1 standalone fallback.
        _validate_execution(observation, flag, flag_decision)
        shadow_m = frozenset()
        self.assertNotIn((flag.x, flag.y), shadow_m)
        port.step(flag.x, flag.y, flag.action)
        self.assertIs(port.status, PLAYING)
        flagged = tuple(tuple(row) for row in port.get_observation())
        self.assertEqual(flagged, ((1, F, H, H),))
        executed = frozenset({(flag.x, flag.y)})

        next_v1 = plan_position(flagged, port.num_mines, (flag.x, flag.y), self.table)
        _validate_execution(flagged, next_v1.move, next_v1)
        seal = runner._SealedV1Input(
            flagged, next_v1, next_v1.move, (flag.x, flag.y),
            self.table[abs(next_v1.move.x - flag.x)][abs(next_v1.move.y - flag.y)],
        )
        snapshot = runner._shadow_input(flagged, port.width, port.height, port.num_mines,
                                        seal.cursor_before, shadow_m, executed)
        self.assertEqual(snapshot.physical_flag_admission.flags, executed)
        analysis = runner._analyze_shadow(snapshot)
        self.assertEqual(analysis.after.P, executed)
        self.assertEqual(analysis.after.J, executed)
        self.assertEqual(analysis.after.M, frozenset())
        self.assertEqual(analysis.after.b, 0)
        self.assertEqual(analysis.selection_safe_cells, {(2, 0), (3, 0)})
        self.assertEqual(analysis.local.acquired_mines, frozenset())
        self.assertEqual(analysis.exact_certificates, ())

        without_provenance = runner._shadow_input(
            flagged, port.width, port.height, port.num_mines, seal.cursor_before,
            shadow_m, frozenset(),
        )
        with self.assertRaises(KIntegrityError) as rejected:
            runner._analyze_shadow(without_provenance)
        self.assertEqual(rejected.exception.code, "UNSUPPORTED_FLAG")

        _validate_execution(flagged, seal.move, seal.decision)
        port.step(seal.move.x, seal.move.y, seal.move.action)
        self.assertIs(port.status, PLAYING)
        control = run_stage3(fixed_engine(), table=self.table)
        self.assertEqual(tuple(port.inputs), control.moves[:3])
        self.assertEqual(seal.move, control.traces[2].move)
        self.assertEqual(seal.modeled_action_us, control.traces[2].modeled_action_us)
        self.assertEqual(analysis.after.M, shadow_m)
        self.assert_status_first(port)

    def test_g_public_proof_history_has_real_v1_flag_outside_current_shadow_m(self):
        """Public semantic checkpoint, with a declared synthetic cursor.

        This is not a canonical trajectory: cursor (0,0) is supplied solely
        to exercise the frozen planner's cost choice. K's two retained mines
        have real earlier exact proof, and every subsequent result is computed
        without forged shadow evidence, hidden layout or evaluator input.
        """
        first = ((H, 1, H, H), (H, H, H, H))
        later = ((H, 1, H, H), (1, H, 2, H))
        owner = KLocalSession(4, 2, 3)
        prior = owner.analyze_decision(first, status=PLAYING)
        self.assertEqual(prior.after.M, {(3, 0), (3, 1)})
        self.assertEqual({proof.target for proof in prior.exact_certificates}, prior.after.M)
        v1 = plan_position(later, 3, (0, 0), self.table)
        _validate_execution(later, v1.move, v1)
        self.assertEqual(v1.move, SimpleMove(Action.FLAG, 0, 0))
        shadow = owner.analyze_decision(later, status=PLAYING)
        self.assertEqual(shadow.continuation, "LOCAL_SAFE")
        self.assertEqual(shadow.selection_safe_cells, {(2, 0), (1, 1)})
        self.assertEqual(shadow.after.M, prior.after.M)
        self.assertNotIn((v1.move.x, v1.move.y), shadow.after.M)
        # V1 validity remains unchanged by this benign schedule discrepancy.
        _validate_execution(later, v1.move, v1)
        self.assertEqual(v1.move, SimpleMove(Action.FLAG, 0, 0))

    def test_h_k_semantic_exception_disables_once_and_cannot_choose_or_skip(self):
        control = run_stage3(fixed_engine(), table=self.table)
        port = PublicPort(fixed_engine())
        with patch.object(runner, "_analyze_shadow",
                          side_effect=KIntegrityError("INJECTED", "shadow-only semantic fault")) as shadow, \
                patch.object(runner, "select_policy", side_effect=AssertionError("K-P0 substitute")):
            result = runner.run_k_control(port, table=self.table)
        self.assertEqual(shadow.call_count, 1)
        self.assert_disabled(result, "SHADOW_SEMANTIC_EXCEPTION")
        self.assertEqual(result.final_M, frozenset())
        self.assert_physical_identity(result, control)
        self.assertEqual(tuple(port.inputs), control.moves)
        self.assertIs(result.traces[1].move.action, Action.FLAG)
        self.assertIsNone(result.traces[1].decision.plan)  # Real V1 fallback.

    def test_shadow_comparison_exception_has_its_own_contained_class(self):
        control = run_stage3(fixed_engine(), table=self.table)
        with patch.object(runner, "_analyze_shadow",
                          side_effect=runner.ShadowComparisonError("injected oracle failure")) as shadow:
            result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        self.assertEqual(shadow.call_count, 1)
        self.assert_disabled(result, "SHADOW_COMPARISON_EXCEPTION")
        self.assert_physical_identity(result, control)

    def test_unexpected_shadow_only_exception_is_contained_without_retry(self):
        with patch.object(runner, "_analyze_shadow",
                          side_effect=RuntimeError("unexpected shadow-only defect")) as shadow:
            result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        self.assertEqual(shadow.call_count, 1)
        self.assert_disabled(result, "SHADOW_EXCEPTION")
        self.assert_physical_identity(result, run_stage3(fixed_engine(), table=self.table))

    def test_shadow_soundness_failure_hook_preserves_v1_stream(self):
        # Fault injection only: no evaluator or answer-based checking is added.
        with patch.object(runner, "_analyze_shadow",
                          side_effect=runner.ShadowSoundnessViolation("injected soundness failure")):
            result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        self.assert_disabled(result, "SHADOW_SOUNDNESS_VIOLATION")
        self.assert_physical_identity(result, run_stage3(fixed_engine(), table=self.table))

    def test_i_malformed_shadow_output_disables_without_substitution(self):
        control = run_stage3(fixed_engine(), table=self.table)
        for malformed in (None, object(), {"move": SimpleMove(Action.OPEN, 3, 0)}):
            with self.subTest(type=type(malformed)), \
                    patch.object(runner, "_analyze_shadow", return_value=malformed) as shadow:
                result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
            self.assertEqual(shadow.call_count, 1)
            self.assert_disabled(result, "SHADOW_MALFORMED_OUTPUT")
            self.assert_physical_identity(result, control)

    def test_i_q_inconsistent_shadow_record_preserves_last_valid_archive(self):
        original = runner._analyze_shadow
        calls = []

        def corrupt_second(snapshot):
            valid = original(snapshot)
            calls.append(valid)
            if len(calls) == 2:
                return replace(valid, after=replace(valid.after, M=frozenset()))
            return valid

        with patch.object(runner, "_analyze_shadow", side_effect=corrupt_second):
            result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        self.assertEqual(len(calls), 2)
        self.assert_disabled(result, "SHADOW_MALFORMED_OUTPUT", boundary=2, last_valid=1)
        self.assertEqual(result.final_M, {(1, 0)})
        self.assertEqual(result.final_M, calls[0].after.M)
        self.assertEqual(result.traces[1].shadow.decision, calls[0])
        self.assert_physical_identity(result, run_stage3(fixed_engine(), table=self.table))

    def test_i_malformed_current_binding_and_mutable_nested_output_are_contained(self):
        original = runner._analyze_shadow
        corruptions = (
            lambda value: replace(value, observation=((1, H, 1, H),)),
            lambda value: replace(value, num_mines=2),
            lambda value: replace(value, after=replace(value.after, b=False)),
            lambda value: replace(value, selection_safe_cells=set(value.selection_safe_cells)),
            lambda value: replace(value, continuation="SUBSTITUTE_V1_ACTION"),
        )
        for corruption in corruptions:
            def malformed(snapshot):
                return corruption(original(snapshot))

            with self.subTest(corruption=corruption), \
                    patch.object(runner, "_analyze_shadow", side_effect=malformed) as shadow:
                result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
            self.assertEqual(shadow.call_count, 1)
            self.assert_disabled(result, "SHADOW_MALFORMED_OUTPUT")
            self.assertEqual(result.final_M, frozenset())
            self.assert_physical_identity(result, run_stage3(fixed_engine(), table=self.table))

    def test_j_timeout_returns_while_worker_blocked_and_late_m_cannot_commit(self):
        entered, release, finished, completed = Event(), Event(), Event(), Event()
        original = runner._analyze_shadow
        late_outputs, results, errors = [], [], []

        def blocked(snapshot):
            entered.set()
            release.wait(3)
            try:
                output = original(snapshot)
                late_outputs.append(output)
                return output
            finally:
                finished.set()

        def execute():
            try:
                results.append(runner.run_k_control(PublicPort(fixed_engine()), table=self.table,
                                                    shadow_timeout_s=0.05))
            except BaseException as error:
                errors.append(error)
            finally:
                completed.set()

        with patch.object(runner, "_analyze_shadow", side_effect=blocked) as shadow:
            owner = Thread(target=execute, daemon=True)
            owner.start()
            try:
                self.assertTrue(entered.wait(2), "Shadow worker did not start")
                self.assertTrue(completed.wait(2), "Hung shadow blocked the V1 owner")
                self.assertFalse(errors, errors)
                self.assertFalse(release.is_set())
                self.assertFalse(finished.is_set())
                result = results[0]
                self.assert_disabled(result, "SHADOW_TIMEOUT")
                self.assertEqual(result.final_M, frozenset())
                self.assertEqual(shadow.call_count, 1)
                self.assert_physical_identity(result, run_stage3(fixed_engine(), table=self.table))
            finally:
                release.set()
                owner.join(2)
                self.assertTrue(finished.wait(2), "Released shadow did not exit")
            self.assertEqual(late_outputs[0].after.M, {(1, 0)})
            self.assertEqual(result.final_M, frozenset())
            self.assertEqual(result.shadow.last_valid_M, frozenset())
            self.assertEqual(shadow.call_count, 1)
            self.assert_disabled(result, "SHADOW_TIMEOUT")

    def test_j_shadow_output_validation_is_also_inside_the_timeout(self):
        entered, release, finished = Event(), Event(), Event()
        original = runner._validate_shadow_result

        def blocked_validation(snapshot, output):
            entered.set()
            release.wait(2)
            try:
                return original(snapshot, output)
            finally:
                finished.set()

        with patch.object(runner, "_validate_shadow_result", side_effect=blocked_validation) as validation:
            try:
                result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table,
                                             shadow_timeout_s=0.05)
                self.assertTrue(entered.is_set())
                self.assertFalse(finished.is_set(), "Output validation blocked V1 beyond its timeout")
                self.assert_disabled(result, "SHADOW_TIMEOUT")
                self.assertEqual(result.final_M, frozenset())
                self.assertEqual(validation.call_count, 1)
                self.assert_physical_identity(result, run_stage3(fixed_engine(), table=self.table))
            finally:
                release.set()
                self.assertTrue(finished.wait(2))
            self.assertEqual(result.final_M, frozenset())
            self.assertFalse(result.shadow.enabled)
            self.assertEqual(validation.call_count, 1)

    def test_l_v1_planner_exception_propagates_before_any_shadow(self):
        port = PublicPort(fixed_engine())
        error = RuntimeError("frozen planner defect")
        with patch.object(runner, "plan_position", side_effect=error), \
                patch.object(runner, "_analyze_shadow") as shadow:
            with self.assertRaises(RuntimeError) as caught:
                runner.run_k_control(port, table=self.table)
        self.assertIs(caught.exception, error)
        shadow.assert_not_called()
        self.assertEqual(port.inputs, [SimpleMove(Action.OPEN, 0, 0)])

    def test_m_frozen_validator_failure_is_not_a_shadow_failure(self):
        port = PublicPort(fixed_engine())

        def invalid_plan(*args):
            valid = plan_position(*args)
            return replace(valid, move=SimpleMove(Action.OPEN, 1, 0))

        # The real frozen validator rejects the unproved OPEN. It is neither
        # replaced nor wrapped by a monkeypatch in this or any Slice-5 test.
        with patch.object(runner, "plan_position", side_effect=invalid_plan), \
                patch.object(runner, "_analyze_shadow") as shadow:
            with self.assertRaises(Stage3RunnerError):
                runner.run_k_control(port, table=self.table)
        shadow.assert_not_called()
        self.assertEqual(port.inputs, [SimpleMove(Action.OPEN, 0, 0)])

    def test_n_engine_input_failure_propagates_after_shadow(self):
        port = PublicPort(fixed_engine())
        original_step = PublicPort.step
        error = RuntimeError("Engine owner input defect")

        def broken(view, x, y, action):
            if view.inputs:
                raise error
            return original_step(view, x, y, action)

        with patch.object(PublicPort, "step", new=broken), \
                patch.object(runner, "_analyze_shadow", wraps=runner._analyze_shadow) as shadow:
            with self.assertRaises(RuntimeError) as caught:
                runner.run_k_control(port, table=self.table)
        self.assertIs(caught.exception, error)
        self.assertEqual(shadow.call_count, 1)
        self.assertEqual(port.inputs, [SimpleMove(Action.OPEN, 0, 0)])

    def test_external_public_mutation_after_seal_aborts_without_replanning(self):
        port = PublicPort(fixed_engine())
        original = runner._analyze_shadow

        def change_public_state(snapshot):
            result = original(snapshot)
            # An Engine-owner contract fault, not information given to K.
            port.observation_fault = lambda rows: [[1, H, 1, H]]
            return result

        with patch.object(runner, "_analyze_shadow", side_effect=change_public_state) as shadow, \
                patch.object(runner, "plan_position", wraps=plan_position) as planner:
            with self.assertRaisesRegex(Stage3RunnerError, "sealed"):
                runner.run_k_control(port, table=self.table)
        self.assertEqual(shadow.call_count, 1)
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(port.inputs, [SimpleMove(Action.OPEN, 0, 0)])

    def test_o_initial_terminal_barrier_permits_no_k_or_shadow_call(self):
        for width, mines, outcome in ((3, {(2, 0)}, GameStatus.WON),
                                      (2, {(0, 0)}, GameStatus.LOST)):
            port = PublicPort(fixed_engine(width, 1, frozenset(mines)))
            with self.subTest(outcome=outcome), \
                    patch.object(runner, "_analyze_shadow", side_effect=AssertionError("shadow")) as shadow, \
                    patch.object(KLocalSession, "analyze_decision", side_effect=AssertionError("K")):
                result = runner.run_k_control(port, table=self.table)
            shadow.assert_not_called()
            self.assertIs(result.status, outcome)
            self.assertEqual(result.final_M, frozenset())
            self.assertEqual(result.moves, (SimpleMove(Action.OPEN, 0, 0),))
            self.assert_status_first(port)

    def test_o_terminal_after_noninitial_input_is_status_first_without_proof_read(self):
        for width, mines, outcome in ((4, {(1, 0)}, GameStatus.WON),
                                      (5, {(1, 0), (2, 0)}, GameStatus.LOST)):
            port = PublicPort(fixed_engine(width, 1, frozenset(mines)))
            original = runner._analyze_shadow

            def shadow(snapshot):
                self.assertIs(port.status, PLAYING)
                port.events.append(("shadow", snapshot.observation))
                return original(snapshot)

            with self.subTest(outcome=outcome), patch.object(runner, "_analyze_shadow", side_effect=shadow) as call:
                result = runner.run_k_control(port, table=self.table)
            self.assertTrue(result.shadow.enabled, result.shadow.failure)
            self.assertIs(result.status, outcome)
            self.assertEqual(call.call_count, len(result.traces) - 1)
            self.assertEqual(result.final_M, result.traces[-1].preinput_M)
            self.assert_status_first(port)

    def test_p_successful_shadow_acquisitions_are_monotonic_and_expire_decisions(self):
        port = PublicPort(fixed_engine(5, 4, frozenset({(1, 2), (3, 2)})))
        result = runner.run_k_control(port, table=self.table)
        self.assertTrue(result.shadow.enabled, result.shadow.failure)
        self.assertIsNone(result.shadow.failure)
        self.assertEqual(result.final_M, {(1, 2), (3, 2)})
        prior = frozenset()
        for index, trace in enumerate(result.traces[1:], start=1):
            self.assertEqual(trace.M_before, prior)
            self.assertLessEqual(prior, trace.preinput_M)
            self.assertEqual(trace.shadow.last_valid_M, trace.preinput_M)
            self.assertEqual(trace.shadow.last_valid_boundary, index)
            self.assertTrue(trace.shadow.evidence_valid)
            self.assertEqual(trace.shadow.decision.observation, trace.observation)
            self.assertEqual(trace.shadow.decision.after.M, trace.preinput_M)
            prior = trace.preinput_M
        self.assertEqual(result.final_M, prior)

    def test_r_shadow_receives_only_detached_immutable_public_values(self):
        original = runner._analyze_shadow
        snapshots = []
        allowed = {"observation", "width", "height", "num_mines", "cursor", "M",
                   "physical_flag_admission"}

        def verify(value):
            self.assertNotIsInstance(value, (MinesweeperEngine, PublicPort, KLocalSession, Stage3Decision))
            self.assertFalse(callable(value))
            if is_dataclass(value):
                self.assertTrue(type(value).__dataclass_params__.frozen)
                for field in fields(value):
                    verify(getattr(value, field.name))
            elif type(value) in (tuple, frozenset):
                for item in value:
                    verify(item)
            else:
                self.assertIsInstance(value, (int, str, type(None)))

        def shadow(snapshot):
            self.assertIs(type(snapshot), runner.ShadowInput)
            self.assertEqual({field.name for field in fields(snapshot)}, allowed)
            verify(snapshot)
            with self.assertRaises(FrozenInstanceError):
                snapshot.M = frozenset({(3, 0)})
            with self.assertRaises(TypeError):
                snapshot.observation[0][0] = 8
            snapshots.append(snapshot)
            return original(snapshot)

        with patch.object(runner, "_analyze_shadow", side_effect=shadow):
            result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        self.assertTrue(result.shadow.enabled, result.shadow.failure)
        self.assertTrue(snapshots)
        for snapshot, trace in zip(snapshots, result.traces[1:]):
            self.assertEqual(snapshot.observation, trace.observation)
            self.assertIsNot(snapshot.observation, trace.observation)
            self.assertEqual(snapshot.cursor, trace.cursor_before)
            self.assertEqual(snapshot.M, trace.M_before)
            self.assertEqual(snapshot.physical_flag_admission.observation, snapshot.observation)
            earlier_flags = frozenset((prior.move.x, prior.move.y)
                                      for prior in result.traces[:trace.input_index]
                                      if prior.move.action is Action.FLAG)
            self.assertLessEqual(snapshot.physical_flag_admission.flags, earlier_flags)

    def test_s_t_bounded_control_physical_stream_cost_and_outcome_identity(self):
        # Three explicit, independently fixed tiny layouts. No generation,
        # scan, benchmark tuple, research manifest, or E1 dispatcher is used.
        fixtures = ((4, 1, frozenset({(1, 0)})),
                    (5, 1, frozenset({(1, 0), (2, 0)})),
                    (5, 4, frozenset({(1, 2), (3, 2)})))
        seen_actions, seen_outcomes = set(), set()
        for width, height, mines in fixtures:
            with self.subTest(size=(width, height), mines=mines):
                control = run_stage3(fixed_engine(width, height, mines), table=self.table)
                result = runner.run_k_control(PublicPort(fixed_engine(width, height, mines)), table=self.table)
                self.assert_physical_identity(result, control)
                self.assertTrue(result.shadow.enabled, result.shadow.failure)
                seen_actions.update(move.action for move in result.moves)
                seen_outcomes.add(result.status)
                cursor, total = (0, 0), 0
                for trace in result.traces:
                    self.assertEqual(trace.cursor_before, cursor)
                    cost = self.table[abs(trace.move.x - cursor[0])][abs(trace.move.y - cursor[1])]
                    self.assertEqual(trace.modeled_action_us, cost)
                    total += cost
                    cursor = (trace.move.x, trace.move.y)
                self.assertEqual(result.total_modeled_us, total)
        self.assertEqual(seen_actions, {Action.OPEN, Action.FLAG, Action.CHORD})
        self.assertEqual(seen_outcomes, {GameStatus.WON, GameStatus.LOST})

    def test_u_real_v1_flag_fallback_survives_shadow_safe_disagreement(self):
        result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        fallback = result.traces[1]
        self.assertIs(fallback.move.action, Action.FLAG)
        self.assertIsNone(fallback.decision.plan)
        self.assertTrue(fallback.shadow.decision.selection_safe_cells)
        self.assertEqual(fallback.move, SimpleMove(Action.FLAG, 1, 0))
        self.assertTrue(fallback.shadow.enabled)
        self.assert_physical_identity(result, run_stage3(fixed_engine(), table=self.table))

    def test_v_repeated_fresh_runs_have_identical_full_internal_records(self):
        first = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        second = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        self.assertEqual(first, second)
        self.assertEqual(first.moves, second.moves)
        self.assertEqual(first.total_modeled_us, second.total_modeled_us)

    def test_invalid_timeout_and_table_are_rejected_before_physical_input(self):
        for timeout in (0, -1, True, float("inf"), float("nan"), 61, None):
            port = PublicPort(fixed_engine())
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                runner.run_k_control(port, table=self.table, shadow_timeout_s=timeout)
            self.assertEqual(port.inputs, [])
        changed = [list(row) for row in self.table]
        changed[0][0] += 1
        port = PublicPort(fixed_engine())
        with self.assertRaises(ValueError):
            runner.run_k_control(port, table=changed)
        self.assertEqual(port.inputs, [])


class ProgramKSlice6P8CheckerTests(unittest.TestCase):
    """Synthetic finite domains exercise the algorithm, never qualify P-8."""

    def test_a_b_exact_count_order_and_only_b_equals_v_is_excluded(self):
        cells = ((0, 1), (1, 0), (0, 0))
        ordered = ((0, 0), (1, 0), (0, 1))
        actual = tuple(public_oracles._iter_p8_triples(ordered))
        expected = tuple((c, b, v) for c in ordered for b in ordered for v in ordered if b != v)
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 3 * 3 * 2)
        self.assertEqual(sum(c == b for c, b, v in actual), 3 * 2)
        self.assertEqual(sum(c == v for c, b, v in actual), 3 * 2)
        self.assertTrue(all(b != v for c, b, v in actual))
        self.assertEqual(480 * 480 * 479, 110361600)
        bounded = public_oracles._check_p8_table(((7, 7), (7, 7)), cells=cells)
        self.assertEqual(bounded.cells, ordered)
        self.assertEqual(bounded.visited_triple_count, len(actual))
        self.assertEqual((bounded.minimum_gap_witness.c, bounded.minimum_gap_witness.b,
                          bounded.minimum_gap_witness.v), actual[0])

    def test_c_positive_private_table_pass_has_exact_minimum_and_no_p8_claim(self):
        result = public_oracles._check_p8_table(((7, 7), (7, 7)))
        self.assertEqual(result.scope, "PRIVATE_BOUNDED_CHECK")
        self.assertEqual(result.status, "PASS")
        self.assertTrue(result.complete)
        self.assertEqual(result.expected_triple_count, 4 * 4 * 3)
        self.assertEqual(result.visited_triple_count, result.expected_triple_count)
        self.assertEqual(result.minimum_gap, 7)
        witness = result.minimum_gap_witness
        self.assertEqual((witness.c, witness.b, witness.v), ((0, 0), (0, 0), (1, 0)))
        self.assertEqual(witness.displacements, ((0, 0), (1, 0), (1, 0)))
        self.assertEqual(witness.table_values, (7, 7, 7))
        self.assertEqual((result.zero_gap_count, result.negative_gap_count), (0, 0))
        self.assertEqual(result.counterexamples, ())
        self.assertTrue(result.checker_source_stable)
        self.assertEqual(result.checker_source_sha256, result.checker_source_end_sha256)

    def test_d_zero_and_negative_synthetic_gaps_report_exact_first_witness(self):
        for direct, gap in ((2, 0), (3, -1)):
            with self.subTest(direct=direct):
                result = public_oracles._check_p8_table(((1,), (1,), (direct,)))
                self.assertEqual(result.status, "FAIL")
                self.assertTrue(result.complete)
                self.assertEqual((result.expected_triple_count, result.visited_triple_count), (18, 18))
                self.assertEqual(result.minimum_gap, gap)
                witness = result.minimum_gap_witness
                self.assertEqual((witness.c, witness.b, witness.v), ((0, 0), (1, 0), (2, 0)))
                self.assertEqual(witness.displacements, ((1, 0), (1, 0), (2, 0)))
                self.assertEqual(witness.table_values, (1, 1, direct))
                self.assertEqual(witness.gap, gap)
                self.assertEqual(witness.triple_index, 3)
                self.assertEqual(result.counterexamples[0], witness)
                self.assertEqual(result.zero_gap_count, 2 if gap == 0 else 0)
                self.assertEqual(result.negative_gap_count, 2 if gap < 0 else 0)

    def test_e_private_partial_and_interrupted_scans_never_pass(self):
        for count in (0, 1, 17):
            with self.subTest(count=count):
                result = public_oracles._check_p8_table(((7,), (7,), (7,)), max_triples=count)
                self.assertEqual(result.status, "INCOMPLETE")
                self.assertFalse(result.complete)
                self.assertEqual(result.expected_triple_count, 18)
                self.assertEqual(result.visited_triple_count, count)
        calls = []

        def interrupt():
            calls.append(None)
            return len(calls) > 5

        result = public_oracles._check_p8_table(((7,), (7,), (7,)), interrupt_requested=interrupt)
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertFalse(result.complete)
        self.assertEqual(result.visited_triple_count, 5)

    def test_f_public_checker_fixes_full_count_and_can_only_interrupt_as_incomplete(self):
        # Authenticate, then stop BEFORE the first triple. The 110,361,600 scan
        # is expressly not executed by this test or anywhere in this slice.
        result = public_oracles.check_frozen_p8(interrupt_requested=lambda: True)
        self.assertEqual(result.scope, "FROZEN_P8")
        self.assertEqual(result.expected_triple_count, 110361600)
        self.assertEqual(result.visited_triple_count, 0)
        self.assertFalse(result.complete)
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertIsNone(result.minimum_gap)
        self.assertIsNone(result.minimum_gap_witness)
        self.assertEqual(result.authentication_status, "AUTHENTICATED")
        self.assertEqual(result.profile_sha256, PROFILE_SHA256)
        self.assertEqual(result.table_sha256, TABLE_SHA256)
        self.assertEqual(result.physical_model_id, "overlap_floor_log2_distance_v1")
        self.assertEqual(result.physical_profile_version, 1)
        self.assertEqual(result.timing_unit, "us")
        self.assertEqual(result.table_order, "dx_major_dy_minor")
        self.assertTrue(result.checker_identity)
        self.assertIs(type(result.checker_version), int)
        self.assertEqual(len(result.checker_source_sha256), 64)
        for unsupported in ("cells", "max_triples", "expected_triple_count", "width", "height"):
            with self.subTest(keyword=unsupported), self.assertRaises(TypeError):
                public_oracles.check_frozen_p8(**{unsupported: 1})

    def test_g_changed_or_malformed_table_rejected_before_any_scan(self):
        table = load_timing_table()
        changed = list(map(list, table))
        changed[0][0] += 1
        mutable = list(map(list, table))
        boolean = list(map(list, table))
        boolean[0][0] = True
        malformed = ((), ((1,),), mutable, tuple(map(tuple, changed)), tuple(map(tuple, boolean)))
        for value in malformed:
            with self.subTest(value_type=type(value)), \
                    patch.object(public_oracles, "_iter_p8_triples", side_effect=AssertionError("scan entered")):
                with self.assertRaises(ValueError):
                    public_oracles.check_frozen_p8(table=value, interrupt_requested=lambda: True)
        changed_profile = PROFILE_PATH.read_bytes() + b"\n"
        with patch("stage3_physical.Path.read_bytes", return_value=changed_profile), \
                patch.object(public_oracles, "_iter_p8_triples", side_effect=AssertionError("scan entered")):
            with self.assertRaises(ValueError):
                public_oracles.check_frozen_p8(interrupt_requested=lambda: True)

    def test_h_source_capture_follows_all_authentication_and_precedes_iterator_call(self):
        import stage3_physical
        events = []
        load = stage3_physical.load_timing_table
        validate = stage3_physical.validate_timing_table
        source = public_oracles._p8_checker_source_sha256
        triples = public_oracles._iter_p8_triples

        def authenticated_profile(path):
            value = load(path)
            events.append("PROFILE_BYTES_METADATA_TABLE_AUTHENTICATED")
            return value

        def authenticated_table(table):
            value = validate(table)
            events.append("TABLE_AUTHENTICATED")
            return value

        def capture_source():
            value = source()
            events.append("SOURCE_CAPTURED")
            return value

        def iterate(cells):
            # This is checked at invocation, before generator execution.
            self.assertIn("PROFILE_BYTES_METADATA_TABLE_AUTHENTICATED", events)
            self.assertIn("TABLE_AUTHENTICATED", events)
            self.assertEqual(events[-1], "SOURCE_CAPTURED")
            events.append("ITERATOR_INVOKED")
            return triples(cells)

        with patch.object(stage3_physical, "load_timing_table", side_effect=authenticated_profile), \
                patch.object(stage3_physical, "validate_timing_table", side_effect=authenticated_table), \
                patch.object(public_oracles, "_p8_checker_source_sha256", side_effect=capture_source), \
                patch.object(public_oracles, "_iter_p8_triples", side_effect=iterate):
            result = public_oracles.check_frozen_p8(interrupt_requested=lambda: True)
        first, second = [i for i, event in enumerate(events) if event == "SOURCE_CAPTURED"]
        self.assertLess(first, events.index("ITERATOR_INVOKED"))
        self.assertGreater(second, events.index("ITERATOR_INVOKED"))
        self.assertTrue(result.checker_source_stable)
        self.assertEqual(result.visited_triple_count, 0)

    def test_i_source_and_metadata_authentication_faults_prevent_iterator_invocation(self):
        for source_error in (OSError("unreadable source"), None, "", "g" * 64, "A" * 64, True):
            with self.subTest(source_error=source_error), \
                    patch.object(public_oracles, "_iter_p8_triples") as iterate:
                kwargs = ({"side_effect": source_error} if isinstance(source_error, Exception)
                          else {"return_value": source_error})
                with patch.object(public_oracles, "_p8_checker_source_sha256", **kwargs):
                    with self.assertRaises((OSError, ValueError)):
                        public_oracles.check_frozen_p8(interrupt_requested=lambda: True)
                iterate.assert_not_called()
        import json
        profile = json.loads(PROFILE_PATH.read_bytes())
        for field, bad in (("model_id", "wrong"), ("table_order", "dy_major_dx_minor"),
                           ("grid_width", True), ("timing_unit", "ns")):
            malformed = dict(profile, **{field: bad})
            with self.subTest(metadata=field), \
                    patch("stage3_physical.json.loads", return_value=malformed), \
                    patch.object(public_oracles, "_p8_checker_source_sha256") as source, \
                    patch.object(public_oracles, "_iter_p8_triples") as iterate:
                with self.assertRaisesRegex(ValueError, "metadata"):
                    public_oracles.check_frozen_p8(interrupt_requested=lambda: True)
                source.assert_not_called()
                iterate.assert_not_called()

    def test_j_post_scan_source_change_invalidates_identity_not_the_timing_premise(self):
        for table in (((7,), (7,), (7,)), ((1,), (1,), (3,))):
            with self.subTest(table=table), \
                    patch.object(public_oracles, "_p8_checker_source_sha256",
                                 side_effect=("a" * 64, "b" * 64)):
                result = public_oracles._check_p8_table(table)
            self.assertTrue(result.complete)
            self.assertEqual(result.visited_triple_count, 18)
            self.assertEqual(result.checker_source_sha256, "a" * 64)
            self.assertEqual(result.checker_source_end_sha256, "b" * 64)
            self.assertFalse(result.checker_source_stable)
            self.assertEqual(result.status, "IMPLEMENTATION_IDENTITY_FAIL")
            self.assertEqual(result.failure_kind, "CHECKER_SOURCE_IDENTITY_FAILURE")
            self.assertFalse(result.premise_failure)
            self.assertEqual(result.negative_gap_count, 2 if table[-1] == (3,) else 0)
            self.assertEqual(replace(result), result)

    def test_k_interruption_preserves_start_identity_and_end_read_failure_never_passes(self):
        for end in ("b" * 64, OSError("source disappeared"), None):
            with self.subTest(end=end), \
                    patch.object(public_oracles, "_p8_checker_source_sha256",
                                 side_effect=("a" * 64, end)):
                result = public_oracles.check_frozen_p8(interrupt_requested=lambda: True)
            self.assertEqual(result.status, "INCOMPLETE")
            self.assertEqual(result.visited_triple_count, 0)
            self.assertEqual(result.interruption_reason, "INTERRUPTED")
            self.assertEqual(result.checker_source_sha256, "a" * 64)
            self.assertEqual(result.checker_source_end_sha256, end if type(end) is str else None)
            self.assertEqual(result.failure_kind, "CHECKER_SOURCE_IDENTITY_FAILURE")
            self.assertFalse(result.premise_failure)
        with patch.object(public_oracles, "_p8_checker_source_sha256",
                          side_effect=("a" * 64, OSError("source disappeared"))):
            complete = public_oracles._check_p8_table(((7,), (7,)))
        self.assertTrue(complete.complete)
        self.assertEqual(complete.status, "IMPLEMENTATION_IDENTITY_FAIL")
        self.assertIsNone(complete.checker_source_end_sha256)

    def test_w_p8_results_are_immutable_and_losslessly_reconstructable(self):
        result = public_oracles._check_p8_table(((1,), (1,), (3,)))
        self.assertEqual(pickle.loads(pickle.dumps(result)), result)
        self.assertEqual(replace(result), result)
        self.assertEqual(len(result.evidence_sha256), 64)
        with self.assertRaises(FrozenInstanceError):
            result.status = "PASS"
        with self.assertRaises(FrozenInstanceError):
            result.minimum_gap_witness.gap = 1
        for changes in ({"complete": False}, {"minimum_gap_witness": None},
                        {"visited_triple_count": 17}, {"checker_identity": ""},
                        {"checker_source_end_sha256": "invalid"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(result, **changes)
        with self.assertRaises(FrozenInstanceError):
            result.checker_source_sha256 = "0" * 64
        with self.assertRaises(FrozenInstanceError):
            result.checker_source_end_sha256 = "0" * 64


class ProgramKSlice6O4ProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def rich_decision(self):
        """Synthetic semantic record, not a physically admissible policy claim.

        Every required optional branch has data so isolated mutations expose
        projection omissions. Actual execution equality is checked separately.
        """
        guess = plan_position(EXACT_TIE, 2, (0, 0), self.table)
        recommendation = guess.evidence.move
        selected = SimpleMove(Action.FLAG, 1, 1)
        analysis = replace(
            guess.evidence,
            constraints=(Constraint((1, 0), 1, frozenset({(0, 0), (2, 0)})),
                         Constraint((0, 1), 1, frozenset({(1, 1), (2, 1)}))),
            deterministic_result=InferenceResult(frozenset({(2, 0), (0, 1)}),
                                                 frozenset({(1, 1), (2, 1)})),
        )
        self.assertNotEqual(selected, recommendation)
        return Stage3Decision(analysis, selected,
                              RevealPlan((replace(selected), SimpleMove(Action.CHORD, 1, 0)), 252010, 2))

    @staticmethod
    def fault_field(value, chain, field, replacement):
        """Fault a single frozen source field, without invoking solver code."""
        result = deepcopy(value)
        target = result
        for segment in chain:
            target = target[segment] if type(segment) is int else getattr(target, segment)
        object.__setattr__(target, field, replacement)
        return result

    def test_h_bounded_control_k_control_semantic_identity_every_noninitial_boundary(self):
        control = run_stage3(fixed_engine(), table=self.table)
        shadow = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        self.assertEqual(len(control.traces), len(shadow.traces))
        for boundary, (left, right) in enumerate(zip(control.traces, shadow.traces)):
            if boundary == 0:
                self.assertIsNone(left.decision)
                self.assertIsNone(right.decision)
                continue
            comparison = evidence_records.compare_v1_decisions(
                left.decision, right.decision, boundary=boundary)
            self.assertEqual(comparison.status, "PASS")
            self.assertEqual(comparison.mismatches, ())
            self.assertEqual(comparison.boundary, boundary)

    def test_i_each_required_semantic_field_and_sequence_order_has_exact_mismatch_path(self):
        original = self.rich_decision()
        evidence = original.evidence
        probability = evidence.probability_result
        cases = (
            (("move",), "action", Action.OPEN, "move.action"),
            (("move",), "x", 2, "move.x"),
            (("move",), "y", 2, "move.y"),
            (("evidence",), "kind", DecisionKind.GLOBAL_CERTAINTY, "evidence.kind"),
            (("evidence", "move"), "action", Action.FLAG, "evidence.move.action"),
            (("evidence", "move"), "x", 2, "evidence.move.x"),
            (("evidence", "move"), "y", 1, "evidence.move.y"),
            (("evidence",), "constraints", evidence.constraints[::-1], "evidence.constraints[0].source[0]"),
            (("evidence", "constraints", 0), "source", (2, 0), "evidence.constraints[0].source[0]"),
            (("evidence", "constraints", 0), "source", (1, 1), "evidence.constraints[0].source[1]"),
            (("evidence", "constraints", 0), "remaining_mines", 0, "evidence.constraints[0].remaining_mines"),
            (("evidence", "constraints", 0), "hidden_cells", frozenset({(0, 0)}), "evidence.constraints[0].hidden_cells.length"),
            (("evidence", "deterministic_result"), "safe_cells", frozenset({(2, 0)}), "evidence.deterministic_result.safe_cells.length"),
            (("evidence", "deterministic_result"), "mine_cells", frozenset({(1, 1)}), "evidence.deterministic_result.mine_cells.length"),
            (("evidence",), "probability_result", None, "evidence.probability_result"),
            (("evidence", "probability_result"), "total_worlds", 7, "evidence.probability_result.total_worlds"),
            (("evidence", "probability_result"), "probabilities", probability.probabilities[::-1], "evidence.probability_result.probabilities[0].coordinate[0]"),
            (("evidence", "probability_result"), "probabilities", probability.probabilities[:-1], "evidence.probability_result.probabilities.length"),
            (("evidence", "probability_result", "probabilities", 0), "coordinate", (3, 0), "evidence.probability_result.probabilities[0].coordinate[0]"),
            (("evidence", "probability_result", "probabilities", 0), "coordinate", (1, 2), "evidence.probability_result.probabilities[0].coordinate[1]"),
            (("evidence", "probability_result", "probabilities", 0), "mine_worlds", 1, "evidence.probability_result.probabilities[0].mine_worlds"),
            (("evidence", "probability_result", "probabilities", 0), "total_worlds", 7, "evidence.probability_result.probabilities[0].total_worlds"),
            (("evidence", "probability_result"), "frontier_cells", probability.frontier_cells[::-1], "evidence.probability_result.frontier_cells[0][1]"),
            (("evidence", "probability_result"), "unconstrained_cells", probability.unconstrained_cells[::-1], "evidence.probability_result.unconstrained_cells[0][1]"),
            ((), "plan", None, "plan"),
            (("plan",), "actions", original.plan.actions[::-1], "plan.actions[0].action"),
            (("plan", "actions", 0), "action", Action.OPEN, "plan.actions[0].action"),
            (("plan", "actions", 0), "x", 2, "plan.actions[0].x"),
            (("plan", "actions", 0), "y", 2, "plan.actions[0].y"),
            (("plan",), "latency_us", 252011, "plan.latency_us"),
            (("plan",), "reveals", 3, "plan.reveals"),
        )
        for chain, field, replacement, expected_path in cases:
            changed = self.fault_field(original, chain, field, replacement)
            # Keep dependent structure valid so these cases test semantic
            # differences, independently of the malformed-record tests below.
            if chain == ("move",):
                changed = replace(changed, plan=replace(changed.plan,
                    actions=(replace(changed.move),) + changed.plan.actions[1:]))
            elif chain == ("plan", "actions", 0) or (chain == ("plan",) and field == "actions"):
                changed = replace(changed, move=replace(changed.plan.actions[0]))
            elif field == "total_worlds" and chain[:2] == ("evidence", "probability_result"):
                result = changed.evidence.probability_result
                result = replace(result, total_worlds=replacement,
                                 probabilities=tuple(replace(cell, total_worlds=replacement)
                                                     for cell in result.probabilities))
                changed = replace(changed, evidence=replace(changed.evidence, probability_result=result))
            elif chain == ("evidence", "probability_result", "probabilities", 0) and field == "coordinate":
                result = changed.evidence.probability_result
                previous = probability.probabilities[0].coordinate
                result = replace(result,
                    frontier_cells=tuple(replacement if cell == previous else cell
                                         for cell in result.frontier_cells),
                    unconstrained_cells=tuple(replacement if cell == previous else cell
                                              for cell in result.unconstrained_cells))
                changed = replace(changed, evidence=replace(changed.evidence, probability_result=result))
            elif chain == ("evidence", "probability_result") and field == "probabilities":
                result = changed.evidence.probability_result
                coordinates = {cell.coordinate for cell in result.probabilities}
                result = replace(result,
                    frontier_cells=tuple(cell for cell in result.frontier_cells if cell in coordinates),
                    unconstrained_cells=tuple(cell for cell in result.unconstrained_cells if cell in coordinates))
                changed = replace(changed, evidence=replace(changed.evidence, probability_result=result))
            with self.subTest(path=expected_path):
                comparison = evidence_records.compare_v1_decisions(original, changed, boundary=7)
                self.assertEqual(comparison.status, "FAIL")
                self.assertIn(expected_path, {item.path for item in comparison.mismatches})
                self.assertTrue(all(item.boundary == 7 for item in comparison.mismatches))
                self.assertTrue(all(item.expected != item.actual for item in comparison.mismatches))

    def test_j_equal_semantics_ignore_object_identity_and_set_construction_order(self):
        original = self.rich_decision()
        rebuilt = deepcopy(original)
        self.assertIsNot(original, rebuilt)
        self.assertIsNot(original.evidence, rebuilt.evidence)
        self.assertEqual(evidence_records.compare_v1_decisions(original, rebuilt, boundary=1).status, "PASS")
        projected = evidence_records.project_v1_decision(rebuilt)
        self.assertEqual(projected.evidence.deterministic_result.safe_cells, ((2, 0), (0, 1)))
        self.assertEqual(projected.evidence.constraints[0].hidden_cells, ((0, 0), (2, 0)))
        self.assertNotEqual(projected.move, projected.evidence.move)

    def test_k_candidate_pools_and_timing_are_not_required_semantics(self):
        original = self.rich_decision()
        augmented = deepcopy(original)
        # Extra diagnostics are deliberately uninspectable, and not frozen V1
        # fields. Projection must not traverse or require them.
        for field in ("candidates", "survivors", "compute_ns", "shadow_ns", "comparison_ns",
                      "oracle_ns", "evaluator_ns", "evidence_ns"):
            object.__setattr__(augmented, field, Untouchable())
        projected = evidence_records.project_v1_decision(augmented)
        self.assertEqual({field.name for field in fields(projected)}, {"move", "evidence", "plan"})
        self.assertEqual(evidence_records.compare_v1_decisions(original, augmented, boundary=1).status, "PASS")

    def test_missing_malformed_or_failed_comparison_cannot_pass(self):
        decision = self.rich_decision()
        for absent in (None, object(), {"move": decision.move}):
            with self.subTest(absent=type(absent)):
                self.assertEqual(evidence_records.compare_v1_decisions(decision, absent, boundary=1).status,
                                 "INCOMPLETE")
        changed = self.fault_field(decision, ("evidence", "probability_result"), "total_worlds", True)
        self.assertEqual(evidence_records.compare_v1_decisions(decision, changed, boundary=1).status,
                         "INCOMPLETE")
        mismatch = evidence_records.EvidenceMismatch(1, "move.x", 1, 2)
        with self.assertRaises(ValueError):
            evidence_records.EvidenceComparison("PASS", 1, (mismatch,))
        projection = evidence_records.project_v1_decision(decision)
        missing = deepcopy(projection)
        object.__setattr__(missing, "evidence", None)
        self.assertEqual(evidence_records.compare_v1_decisions(missing, deepcopy(missing), boundary=1).status,
                         "INCOMPLETE")
        invalid_integer = deepcopy(projection)
        object.__setattr__(invalid_integer.evidence.probability_result, "total_worlds", True)
        self.assertEqual(evidence_records.compare_v1_decisions(invalid_integer, deepcopy(invalid_integer), boundary=1).status,
                         "INCOMPLETE")

    def test_identically_malformed_probability_or_plan_records_cannot_pass(self):
        decision = self.rich_decision()
        projection = evidence_records.project_v1_decision(decision)
        for source in (decision, projection):
            probability = source.evidence.probability_result
            cases = (
                ("A_mine_worlds_exceeds_total", ("evidence", "probability_result", "probabilities", 0),
                 "mine_worlds", probability.total_worlds + 1),
                ("B_child_total_differs", ("evidence", "probability_result", "probabilities", 0),
                 "total_worlds", probability.total_worlds + 1),
                ("C_duplicate_probability_coordinate", ("evidence", "probability_result", "probabilities", 0),
                 "coordinate", probability.probabilities[1].coordinate),
                ("D_partition_overlap", ("evidence", "probability_result"),
                 "unconstrained_cells", probability.unconstrained_cells + (probability.frontier_cells[0],)),
                ("E_partition_missing_probability_coordinate", ("evidence", "probability_result"),
                 "frontier_cells", probability.frontier_cells[:-1]),
                ("F_extra_partition_coordinate", ("evidence", "probability_result"),
                 "unconstrained_cells", probability.unconstrained_cells + ((3, 1),)),
                ("G_selected_move_differs_from_first_action", ("plan", "actions", 0), "x", 3),
                ("duplicate_frontier_coordinate", ("evidence", "probability_result"),
                 "frontier_cells", probability.frontier_cells + (probability.frontier_cells[0],)),
                ("duplicate_unconstrained_coordinate", ("evidence", "probability_result"),
                 "unconstrained_cells", probability.unconstrained_cells + (probability.unconstrained_cells[0],)),
            )
            self.assertEqual(evidence_records.compare_v1_decisions(
                source, deepcopy(source), boundary=2).status, "PASS")
            for name, chain, field, replacement in cases:
                with self.subTest(representation=type(source).__name__, malformed=name):
                    malformed = self.fault_field(source, chain, field, replacement)
                    comparison = evidence_records.compare_v1_decisions(
                        malformed, deepcopy(malformed), boundary=2)
                    self.assertEqual(comparison.status, "INCOMPLETE")

    def test_w_projection_and_mismatch_are_immutable_reconstructable(self):
        source = self.rich_decision()
        projected = evidence_records.project_v1_decision(source)
        self.assertEqual(pickle.loads(pickle.dumps(projected)), projected)
        self.assertEqual(replace(projected), projected)
        with self.assertRaises(FrozenInstanceError):
            projected.move.x = 9
        changed = replace(projected, plan=None)
        comparison = evidence_records.compare_v1_decisions(projected, changed, boundary=5)
        self.assertEqual(pickle.loads(pickle.dumps(comparison)), comparison)
        with self.assertRaises(FrozenInstanceError):
            comparison.mismatches[0].boundary = 6


class ProgramKSlice6SoundnessAndFlagEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def test_l_public_safe_at_v1_guess_detected_at_exact_boundary_without_action_change(self):
        v1 = plan_position(EXACT_TIE, 2, (0, 0), self.table)
        _validate_execution(EXACT_TIE, v1.move, v1)
        sealed_move = v1.move
        result = evidence_records.compare_shadow_soundness(v1, frozenset({(0, 1), (1, 0)}), boundary=4)
        self.assertEqual(result.classification, "SHADOW_SOUNDNESS_VIOLATION")
        self.assertEqual(result.boundary, 4)
        self.assertEqual(result.implicated_boundary, 4)
        self.assertEqual(result.safe_cells, ((1, 0), (0, 1)))
        self.assertEqual(v1.move, sealed_move)
        self.assertIsNot(result.v1_decision, v1)

    def test_l_fault_safe_at_valid_v1_guess_disables_shadow_preserving_frozen_stream(self):
        width, mines = 5, frozenset({(1, 0), (2, 0)})
        control = run_stage3(fixed_engine(width, 1, mines), table=self.table)
        original = runner._analyze_shadow
        implicated = next(index for index, trace in enumerate(control.traces)
                          if trace.decision is not None
                          and trace.decision.evidence.kind is DecisionKind.PROBABILITY_GUESS)
        observed = []

        def inject_safe(snapshot):
            result = original(snapshot)
            if result.continuation != "EXACT_GUESS":
                return result
            # Deliberately false current public assertion, with structural phase
            # consistency. No hidden answer is used to manufacture a repair.
            safe = frozenset({min(result.after.U, key=lambda c: (c[1], c[0]))})
            local = replace(result.local, S_first=safe, S_second_all=safe,
                            S_new=frozenset(), S_current=safe)
            malformed = replace(result, local=local, phase_d=None, phase_e=None,
                                phase_e_status="NOT_REACHED", after=local.after,
                                exact_certificates=(), continuation="LOCAL_SAFE",
                                selection_safe_cells=safe, guess_target=None)
            observed.append(malformed)
            return malformed

        with patch.object(runner, "_analyze_shadow", side_effect=inject_safe):
            result = runner.run_k_control(PublicPort(fixed_engine(width, 1, mines)), table=self.table)
        self.assertTrue(observed)
        self.assertFalse(result.shadow.enabled)
        self.assertEqual(result.shadow.failure.failure_class, "SHADOW_SOUNDNESS_VIOLATION")
        self.assertEqual(result.shadow.failure.detected_boundary, implicated)
        self.assertEqual(result.shadow.failure.implicated_boundary, implicated)
        self.assertEqual(result.traces[implicated].soundness.classification, "SHADOW_SOUNDNESS_VIOLATION")
        self.assertEqual(result.moves, control.moves)
        self.assertEqual(result.status, control.status)
        self.assertEqual(result.total_modeled_us, control.total_modeled_us)
        self.assertEqual(result.traces[implicated].move, control.traces[implicated].move)
        self.assertEqual(result.final_M, result.traces[implicated].M_before)

    def test_m_non_guess_or_no_shadow_safe_does_not_trigger_discrepancy(self):
        guess = plan_position(EXACT_TIE, 2, (0, 0), self.table)
        local = plan_position(((1, H, H, H),), 1, (0, 0), self.table)
        for decision, safe in ((guess, frozenset()), (local, frozenset({(3, 0)}))):
            result = evidence_records.compare_shadow_soundness(decision, safe, boundary=1)
            self.assertEqual(result.classification, "NO_DISCREPANCY")
            self.assertIsNone(result.implicated_boundary)
            with self.assertRaises(ValueError):
                replace(result, implicated_boundary=99)
        self.assertEqual(evidence_records.compare_shadow_soundness(None, frozenset(), boundary=0).classification,
                         "NOT_EVALUATED")
        initial = evidence_records.compare_shadow_soundness(None, frozenset(), boundary=0)
        with self.assertRaises(ValueError):
            replace(initial, implicated_boundary=99)

    def test_n_public_local_and_exact_v1_flags_have_separate_provenance(self):
        fixtures = ((((1, H, H, H),), 1), (((H, 1, H, H, H),), 3))
        for observation, count in fixtures:
            with self.subTest(observation=observation):
                decision = plan_position(observation, count, (0, 0), self.table)
                self.assertIs(decision.move.action, Action.FLAG)
                _validate_execution(observation, decision.move, decision)
                record = evidence_records.make_v1_flag_provenance(
                    observation, decision, num_mines=count, boundary=1)
                check = evidence_records.verify_v1_flag_provenance(record)
                self.assertEqual(check.status, "PASS", check.detail)
                self.assertEqual(record.origin, "EXTERNAL_V1_PHYSICAL_FLAG")
                self.assertFalse(record.enters_M)
                self.assertEqual(record.input_index, record.boundary)
                self.assertEqual(record.observation, observation)
                self.assertEqual(record.decision, evidence_records.project_v1_decision(decision))
                self.assertNotIsInstance(record, public_oracles.LocalMineCertificate)

        observation = ((1, H, H, H),)
        decision = plan_position(observation, 1, (0, 0), self.table)
        record = evidence_records.make_v1_flag_provenance(observation, decision, num_mines=1, boundary=1)
        flagged = ((1, F, H, H),)
        inputs = runner._shadow_input(flagged, 4, 1, 1, (1, 0), frozenset(), frozenset({(1, 0)}))
        result = runner._analyze_shadow(inputs)
        self.assertEqual(result.after.P, {(1, 0)})
        self.assertEqual(result.after.M, frozenset())
        self.assertEqual(record.move.x, 1)

    def test_n_external_flag_antecedents_are_ordered_public_records_not_m_certificates(self):
        first_observation = ((1, H, H, H, H),)
        first_decision = plan_position(first_observation, 2, (0, 0), self.table)
        first = evidence_records.make_v1_flag_provenance(first_observation, first_decision,
                                                        num_mines=2, boundary=1)
        later = ((1, F, 2, H, H),)
        later_decision = plan_position(later, 2, (1, 0), self.table)
        current = evidence_records.make_v1_flag_provenance(later, later_decision,
                                                          num_mines=2, boundary=3, prior_flags=(first,))
        self.assertEqual(evidence_records.verify_v1_flag_provenance(current).status, "PASS")
        self.assertEqual(current.prior_flags, (first,))
        self.assertFalse(current.enters_M)
        self.assertEqual(current.move.x, 3)
        for altered in (replace(current, prior_flags=()), replace(current, prior_flags=(first, first)),
                        replace(current, boundary=1, input_index=1)):
            self.assertNotEqual(evidence_records.verify_v1_flag_provenance(altered).status, "PASS")

    def test_o_malformed_unsupported_and_absent_flag_evidence_fail(self):
        observation = ((1, H, H, H),)
        v1 = plan_position(observation, 1, (0, 0), self.table)
        record = evidence_records.make_v1_flag_provenance(observation, v1, num_mines=1, boundary=1)
        fake_move = evidence_records.MoveProjection(Action.FLAG, 3, 0)
        unsupported = replace(record, move=fake_move, decision=replace(record.decision, move=fake_move))
        no_flag = evidence_records.make_v1_flag_provenance(
            EXACT_TIE, plan_position(EXACT_TIE, 2, (0, 0), self.table), num_mines=2, boundary=1)
        malformed = (None, object(), unsupported, no_flag,
                     replace(record, observation=((0, H, H, H),)),
                     replace(record, input_index=2))
        for item in malformed:
            with self.subTest(item=type(item)):
                self.assertNotEqual(evidence_records.verify_v1_flag_provenance(item).status, "PASS")
        with self.assertRaises(ValueError):
            replace(record, enters_M=True)
        with self.assertRaises(TypeError):
            evidence_records.verify_v1_flag_provenance(record, hidden_truth=Untouchable())

    def test_n_large_exact_flag_check_is_explicitly_not_evaluated(self):
        observation = ((H, 1, H) + (H,) * 15,)
        v1 = plan_position(observation, 16, (0, 0), self.table)
        record = evidence_records.make_v1_flag_provenance(observation, v1, num_mines=16, boundary=1)
        check = evidence_records.verify_v1_flag_provenance(record)
        self.assertEqual(check.status, "NOT_EVALUATED")
        self.assertTrue(check.detail)

    def test_w_public_flag_proof_is_immutable_and_losslessly_reconstructable(self):
        observation = ((1, H, H, H),)
        v1 = plan_position(observation, 1, (0, 0), self.table)
        record = evidence_records.make_v1_flag_provenance(observation, v1, num_mines=1, boundary=1)
        reconstructed = pickle.loads(pickle.dumps(record))
        self.assertEqual(record, reconstructed)
        self.assertEqual(evidence_records.verify_v1_flag_provenance(reconstructed).status, "PASS")
        with self.assertRaises(FrozenInstanceError):
            record.enters_M = True


class Slice6ArchiveSentinelPort(PublicPort):
    """Harness-only terminal archival lane; solver still sees a narrow port.

    Every Engine step returns a poison object, even at termination. Terminal
    get_observation is available only to exercise the opt-in archive observer.
    Hidden Engine ownership remains confined to this test adapter.
    """

    def __init__(self, engine):
        super().__init__(engine)
        self.forbidden_attempts = []
        self.terminal_step_payloads = []
        self.terminal_archive_reads = []

    def get_observation(self):
        engine = object.__getattribute__(self, "_PublicPort__engine")
        if engine.status is PLAYING:
            return super().get_observation()
        self.terminal_archive_reads.append(engine.status)
        self.events.append(("archival_terminal_observation", engine.status))
        return engine.get_observation()

    def step(self, x, y, action):
        payload = super().step(x, y, action)
        engine = object.__getattribute__(self, "_PublicPort__engine")
        if engine.status is not PLAYING:
            self.terminal_step_payloads.append(engine.status)
        return payload

    def __getattr__(self, name):
        self.forbidden_attempts.append(name)
        raise AssertionError(f"Forbidden answer-channel sentinel: {name}")


class ProgramKSlice6InterfaceAndEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def test_p_q_runtime_interface_rejects_each_answer_channel_and_discards_terminal_payload(self):
        channels = ("get_board_snapshot", "get_counter_snapshot", "get_stats", "_active_clicks",
                    "_wasted_clicks", "_total_3bv", "_effective_3bv", "_mines", "_adjacent",
                    "hidden_layout", "fingerprint", "evaluator", "zini", "ZiNi")
        for channel in channels:
            port = Slice6ArchiveSentinelPort(fixed_engine())
            view = runner._PublicEnginePort(port)
            with self.subTest(channel=channel), self.assertRaises(AttributeError):
                getattr(view, channel)
            # A counterfactual accidental read trips an actual runtime sentinel.
            with self.assertRaisesRegex(AssertionError, "answer-channel sentinel"):
                getattr(port, channel)
            self.assertEqual(port.forbidden_attempts, [channel])

        for run in (runner.run_k_p0, runner.run_k_control, runner.run_control_capture):
            for width, mines, outcome in ((3, frozenset({(2, 0)}), GameStatus.WON),
                                          (2, frozenset({(0, 0)}), GameStatus.LOST)):
                with self.subTest(run=run.__name__, outcome=outcome):
                    port = Slice6ArchiveSentinelPort(fixed_engine(width, 1, mines))
                    kwargs = {} if run is runner.run_control_capture else {"capture_effects": True}
                    with patch.object(KLocalSession, "analyze_decision", side_effect=AssertionError("postterminal K")), \
                            patch.object(runner, "_analyze_shadow", side_effect=AssertionError("postterminal shadow")), \
                            patch.object(public_oracles, "enumerate_public_worlds", side_effect=AssertionError("postterminal oracle")):
                        result = run(port, table=self.table, **kwargs)
                    self.assertEqual(result.status, outcome)
                    self.assertEqual(result.moves, (SimpleMove(Action.OPEN, 0, 0),))
                    self.assertEqual(port.forbidden_attempts, [])
                    self.assertEqual(port.terminal_step_payloads, [outcome])
                    self.assertEqual(port.terminal_archive_reads, [outcome])
                    step_index = next(i for i, event in enumerate(port.events) if event[0] == "step")
                    self.assertEqual(port.events[step_index + 1][0], "status")

    def test_p_solver_and_public_proof_reject_engine_or_archival_objects_at_runtime(self):
        port = Slice6ArchiveSentinelPort(fixed_engine())
        for value in (port, Untouchable(), {"hidden_layout": Untouchable()}):
            with self.subTest(value_type=type(value)):
                with self.assertRaises(KIntegrityError):
                    KLocalSession(4, 1, 1).analyze_decision(value, status=PLAYING)
                with self.assertRaises(public_oracles.PublicProofError):
                    public_oracles.enumerate_public_worlds(value, 1, status=PLAYING)
        self.assertEqual(port.forbidden_attempts, [])

    def test_r_t_public_open_flag_chord_deltas_follow_frozen_convention(self):
        fixtures = (
            (((H, H, H),), SimpleMove(Action.OPEN, 0, 0), ((0, 1, F),), GameStatus.WON, 2, 0),
            (((1, H, H, H),), SimpleMove(Action.FLAG, 1, 0), ((1, F, H, H),), PLAYING, 0, 1),
            (FLAGGED_PREFIX, SimpleMove(Action.CHORD, 2, 0), ((1, F, 1, 0), (1, 1, 1, 0)), GameStatus.WON, 2, 0),
            # Flood-cleared FLAG contributes one opened safe, no FLAG input.
            (((0, F, H),), SimpleMove(Action.OPEN, 2, 0), ((0, 0, 0),), GameStatus.WON, 2, 0),
        )
        for before, move, after, status, safe, flag in fixtures:
            with self.subTest(action=move.action, before=before):
                effect = evidence_records.make_public_effect(before, move, after, input_index=0,
                    status_after=status, cursor_before=(0, 0), modeled_action_us=126005)
                self.assertEqual(effect.status_before, PLAYING)
                self.assertEqual(effect.status_after, status)
                self.assertEqual(effect.before_observation, before)
                self.assertEqual(effect.after_observation.rows, after)
                self.assertEqual(effect.safe_cells_opened_delta, safe)
                self.assertEqual(effect.explicit_flag_delta, flag)
                self.assertEqual(effect.cursor_after, (move.x, move.y))
                self.assertTrue(effect.archival_only)
                self.assertTrue(effect.after_observation.archival_only)
                self.assertEqual(effect.capture_method, "STATUS_GATED_ACTUAL_EXECUTION")
                self.assertEqual(evidence_records.compare_public_effects(effect, deepcopy(effect)).status, "PASS")
                with self.assertRaises(ValueError):
                    replace(effect, safe_cells_opened_delta=safe + 1)
                with self.assertRaises(ValueError):
                    replace(effect, explicit_flag_delta=flag + 1)

    def test_s_terminal_glyph_archive_cannot_become_k_shadow_or_oracle_input(self):
        effect = evidence_records.make_public_effect(
            ((1, H, H, F),), SimpleMove(Action.OPEN, 1, 0),
            ((1, int(CellState.EXPLODED), int(CellState.MINE), int(CellState.FALSE_FLAG)),),
            input_index=2, status_after=GameStatus.LOST, cursor_before=(0, 0), modeled_action_us=126005)
        archive = effect.after_observation
        self.assertEqual(effect.safe_cells_opened_delta, 0)
        self.assertEqual(effect.explicit_flag_delta, 0)
        self.assertTrue(archive.archival_only)
        for supplied in (archive, archive.rows):
            with self.subTest(type=type(supplied)):
                with self.assertRaises(KIntegrityError):
                    KLocalSession(4, 1, 2).analyze_decision(supplied, status=PLAYING)
                with self.assertRaises(public_oracles.PublicProofError):
                    public_oracles.enumerate_public_worlds(supplied, 2, status=PLAYING)
                with self.assertRaises(public_oracles.PublicProofError):
                    public_oracles.materialized_exact_reference(supplied, 2, status=PLAYING)
        normal = runner._shadow_input(((1, H, H, H),), 4, 1, 2, (0, 0), frozenset(), frozenset())
        with self.assertRaises(KIntegrityError):
            runner._analyze_shadow(replace(normal, observation=archive))
        with self.assertRaises(ValueError):
            evidence_records.make_public_effect(archive, SimpleMove(Action.OPEN, 0, 0), ((H,) * 4,),
                input_index=3, status_after=PLAYING, cursor_before=(1, 0), modeled_action_us=126005)

    def test_s_later_terminal_archive_cannot_resume_k_shadow_or_public_comparison(self):
        original_analysis = KLocalSession.analyze_decision
        original_comparison = runner.compare_shadow_soundness
        for run in (runner.run_k_p0, runner.run_k_control):
            port = Slice6ArchiveSentinelPort(fixed_engine())
            analyses, comparisons = [], []

            def analyze(owner, observation, **kwargs):
                self.assertIs(port.status, PLAYING)
                self.assertNotIsInstance(observation, evidence_records.ArchivalObservation)
                analyses.append(observation)
                return original_analysis(owner, observation, **kwargs)

            def compare(*args, **kwargs):
                self.assertIs(port.status, PLAYING)
                comparisons.append(kwargs["boundary"])
                return original_comparison(*args, **kwargs)

            with self.subTest(run=run.__name__), \
                    patch.object(KLocalSession, "analyze_decision", new=analyze), \
                    patch.object(runner, "compare_shadow_soundness", side_effect=compare):
                result = run(port, table=self.table, capture_effects=True)
            self.assertEqual(len(analyses), len(result.traces) - 1)
            self.assertEqual(len(comparisons), len(result.traces) - 1 if run is runner.run_k_control else 0)
            self.assertEqual(port.terminal_archive_reads, [GameStatus.WON])
            self.assertEqual(port.forbidden_attempts, [])
            self.assertIs(result.traces[-1].public_effect.status_after, GameStatus.WON)
            self.assertEqual(result.final_M, result.traces[-1].preinput_M)

    def test_r_t_actual_control_and_shadow_capture_exact_effects_and_initial_final_coverage(self):
        width, height, mines = 5, 4, frozenset({(1, 2), (3, 2)})
        control = runner.run_control_capture(Slice6ArchiveSentinelPort(fixed_engine(width, height, mines)),
                                             table=self.table)
        shadow = runner.run_k_control(Slice6ArchiveSentinelPort(fixed_engine(width, height, mines)),
                                       table=self.table, capture_effects=True)
        self.assertEqual(control.moves, shadow.moves)
        self.assertEqual(control.capture_method, "STATUS_GATED_ACTUAL_EXECUTION")
        self.assertEqual(len(control.effects), len(control.traces))
        effects = tuple(trace.public_effect for trace in shadow.traces)
        self.assertEqual({effect.move.action for effect in effects}, {Action.OPEN, Action.FLAG, Action.CHORD})
        self.assertEqual(evidence_records.validate_public_effect_stream(control.effects, complete=True).status, "PASS")
        self.assertEqual(evidence_records.validate_public_effect_stream(effects, complete=True).status, "PASS")
        for index, (left, right) in enumerate(zip(control.effects, effects)):
            self.assertEqual((left.input_index, right.input_index), (index, index))
            self.assertEqual(evidence_records.compare_public_effects(left, right).status, "PASS")
            self.assertEqual(left.safe_cells_opened_delta, control.traces[index].safe_cells_opened_delta)
            self.assertEqual(left.explicit_flag_delta, control.traces[index].explicit_flag_delta)
            self.assertEqual(left.modeled_action_us, self.table[abs(left.move.x - left.cursor_before[0])][
                abs(left.move.y - left.cursor_before[1])])
            trace = shadow.traces[index]
            if trace.move.action is Action.FLAG:
                self.assertEqual(trace.external_flag.boundary, index)
                self.assertEqual(trace.external_flag.input_index, index)
                self.assertFalse(trace.external_flag.enters_M)
                self.assertEqual(trace.external_flag.observation, trace.observation)
                self.assertEqual(evidence_records.verify_v1_flag_provenance(trace.external_flag).status, "PASS")
            else:
                self.assertIsNone(trace.external_flag)
            current_flags = frozenset((x, y) for y, row in enumerate(trace.observation)
                                      for x, value in enumerate(row) if value == F)
            self.assertEqual(frozenset((p.move.x, p.move.y) for p in trace.external_flag_antecedents), current_flags)
            self.assertTrue(all(p.input_index < index for p in trace.external_flag_antecedents))
        self.assertEqual(effects[0].input_index, 0)
        self.assertIs(effects[-1].status_after, GameStatus.WON)

    def test_missing_noncontiguous_and_postterminal_effects_never_pass(self):
        captured = runner.run_control_capture(fixed_engine(), table=self.table)
        effects = captured.effects
        invalid = (
            (), effects[:-1], effects[1:], effects + (effects[-1],),
            (effects[0], replace(effects[1], input_index=5)) + effects[2:],
            (effects[0], None) + effects[2:],
        )
        for stream in invalid:
            with self.subTest(length=len(stream)):
                self.assertNotEqual(evidence_records.validate_public_effect_stream(stream, complete=True).status, "PASS")
        self.assertEqual(evidence_records.validate_public_effect_stream(effects, complete=False).status, "INCOMPLETE")
        self.assertEqual(evidence_records.compare_public_effects(effects[0], None).status, "INCOMPLETE")
        changed = replace(effects[0], modeled_action_us=effects[0].modeled_action_us + 1)
        comparison = evidence_records.compare_public_effects(effects[0], changed)
        self.assertEqual(comparison.status, "FAIL")
        self.assertEqual(comparison.mismatches[0].path, "modeled_action_us")
        malformed = deepcopy(effects[0])
        object.__setattr__(malformed.move, "action", None)
        self.assertEqual(evidence_records.compare_public_effects(malformed, deepcopy(malformed)).status,
                         "INCOMPLETE")
        self.assertEqual(evidence_records.validate_public_effect_stream((malformed,) + effects[1:],
                                                                       complete=True).status, "FAIL")

    def test_w_effect_archives_detach_mutable_inputs_and_reconstruct_exactly(self):
        before, after = [[H, H, H]], [[0, 1, F]]
        effect = evidence_records.make_public_effect(before, SimpleMove(Action.OPEN, 0, 0), after,
            input_index=0, status_after=GameStatus.WON, cursor_before=(0, 0), modeled_action_us=126005)
        before[0][0], after[0][2] = 8, H
        self.assertEqual(effect.before_observation, ((H, H, H),))
        self.assertEqual(effect.after_observation.rows, ((0, 1, F),))
        self.assertEqual(pickle.loads(pickle.dumps(effect)), effect)
        self.assertEqual(replace(effect), effect)
        with self.assertRaises(FrozenInstanceError):
            effect.after_observation.archival_only = False


class ProgramKSlice6TimingAndContainmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def measured_fixture(self, run, **kwargs):
        """A semantic clock assigns work at real function returns.

        Frozen validation is observed through Python profiling, never patched
        or weakened. This tests span boundaries, not speed or wall-clock cost.
        """
        duration_by_code = {
            KLocalSession.analyze_decision.__code__: 7,
            select_policy.__code__: 11,
            runner.validate_k_p0_execution.__code__: 13,
            plan_position.__code__: 17,
            _validate_execution.__code__: 19,
            runner._analyze_shadow.__code__: 23,
            runner._validate_shadow_result.__code__: 29,
            evidence_records.compare_shadow_soundness.__code__: 31,
            evidence_records.make_public_effect.__code__: 37,
        }
        now = [1000]

        def profile(frame, event, value):
            if event == "return":
                now[0] += duration_by_code.get(frame.f_code, 0)

        def clock():
            return now[0]

        old_local, old_thread = sys.getprofile(), threading.getprofile()
        try:
            sys.setprofile(profile)
            threading.setprofile(profile)
            with patch.object(runner, "perf_counter_ns", new=clock), \
                    patch("stage3_runner.perf_counter_ns", new=clock):
                return run(Slice6ArchiveSentinelPort(fixed_engine()), table=self.table, **kwargs)
        finally:
            sys.setprofile(old_local)
            threading.setprofile(old_thread)

    def test_u_k_span_includes_analysis_and_policy_but_excludes_validator_and_archive(self):
        result = self.measured_fixture(runner.run_k_p0, capture_effects=True)
        for index, trace in enumerate(result.traces):
            timing = trace.timings
            self.assertEqual(timing.k_analysis_planning_ns, None if index == 0 else 7 + 11)
            self.assertEqual(timing.k_execution_validation_ns, 13)
            self.assertEqual(timing.evidence_ns, 37)
            self.assertIsNone(timing.v1_plan_position_ns)
            self.assertIsNone(timing.v1_execution_validation_ns)
            self.assertIsNone(timing.shadow_ns)
            self.assertIsNone(timing.comparison_ns)
            self.assertIsNone(timing.oracle_ns)
            self.assertIsNone(timing.evaluator_ns)

    def test_u_v1_planner_frozen_validation_shadow_and_public_comparison_are_disjoint(self):
        with patch.object(public_oracles, "enumerate_public_worlds",
                          side_effect=AssertionError("unexpected Oracle A invocation")) as oracle_a, \
                patch.object(public_oracles, "materialized_exact_reference",
                             side_effect=AssertionError("unexpected Oracle B invocation")) as oracle_b:
            result = self.measured_fixture(runner.run_k_control, capture_effects=True)
        # Fail even if an incorrectly invoked oracle's sentinel was contained.
        oracle_a.assert_not_called()
        oracle_b.assert_not_called()
        for index, trace in enumerate(result.traces):
            timing = trace.timings
            self.assertEqual(timing.v1_plan_position_ns, None if index == 0 else 17)
            self.assertEqual(timing.v1_execution_validation_ns, 19 + 19)
            self.assertEqual(timing.shadow_ns, None if index == 0 else 7 + 23 + 29)
            self.assertEqual(timing.comparison_ns, None if index == 0 else 31)
            self.assertIsNone(timing.oracle_ns)
            self.assertEqual(timing.evidence_ns, 37)
            self.assertIsNone(timing.k_analysis_planning_ns)
            self.assertIsNone(timing.k_execution_validation_ns)
            self.assertIsNone(timing.evaluator_ns)

    def test_u_control_reuses_frozen_planner_only_duration_without_inventing_validation(self):
        result = self.measured_fixture(runner.run_control_capture)
        for index, (trace, timing) in enumerate(zip(result.traces, result.timings)):
            self.assertEqual(timing.v1_plan_position_ns, trace.decision_compute_ns)
            self.assertEqual(timing.v1_plan_position_ns, None if index == 0 else 17)
            self.assertEqual(timing.evidence_ns, 37)
            self.assertIsNone(timing.v1_execution_validation_ns)
            self.assertIsNone(timing.k_analysis_planning_ns)
            self.assertIsNone(timing.k_execution_validation_ns)
            self.assertIsNone(timing.shadow_ns)
            self.assertIsNone(timing.comparison_ns)
            self.assertIsNone(timing.oracle_ns)
            self.assertIsNone(timing.evaluator_ns)

    def test_v_w_all_authoritative_timing_fields_are_true_integer_ns_or_unmeasured(self):
        names = {field.name for field in fields(evidence_records.DecisionTimings)}
        self.assertEqual(names, {"v1_plan_position_ns", "k_analysis_planning_ns",
                                "k_execution_validation_ns", "v1_execution_validation_ns",
                                "shadow_ns", "comparison_ns", "evidence_ns", "oracle_ns", "evaluator_ns"})
        empty = evidence_records.DecisionTimings()
        self.assertTrue(all(getattr(empty, name) is None for name in names))
        for name in names:
            for bad in (1.0, True, -1, "1"):
                with self.subTest(field=name, value=bad), self.assertRaises(ValueError):
                    evidence_records.DecisionTimings(**{name: bad})
            value = evidence_records.DecisionTimings(**{name: 2 ** 70})
            self.assertIs(type(getattr(value, name)), int)
            self.assertEqual(pickle.loads(pickle.dumps(value)), value)
            with self.assertRaises(FrozenInstanceError):
                setattr(value, name, 0)
        for run in (runner.run_k_p0, runner.run_k_control):
            for trace in run(PublicPort(fixed_engine()), table=self.table).traces:
                for name in names:
                    value = getattr(trace.timings, name)
                    self.assertTrue(value is None or type(value) is int)
                self.assertIsNone(trace.timings.oracle_ns)
                self.assertIsNone(trace.public_effect)
                self.assertEqual(trace.public_effect_status, "NOT_EVALUATED")

    def test_comparator_exception_disables_shadow_and_preserves_sealed_v1_stream(self):
        control = run_stage3(fixed_engine(), table=self.table)
        with patch.object(runner, "compare_shadow_soundness", side_effect=ValueError("public comparison fault")) as compare:
            result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
        self.assertEqual(compare.call_count, 1)
        self.assertEqual(result.shadow.failure.failure_class, "SHADOW_COMPARISON_EXCEPTION")
        self.assertFalse(result.shadow.enabled)
        self.assertEqual(result.shadow.failure.detected_boundary, 1)
        self.assertEqual(result.final_M, frozenset())
        self.assertEqual(result.moves, control.moves)
        self.assertEqual(result.status, control.status)

    def test_malformed_or_unbound_comparator_output_disables_without_action_change(self):
        original = runner.compare_shadow_soundness
        control = run_stage3(fixed_engine(), table=self.table)
        corruptions = (
            lambda value: SimpleNamespace(classification="NO_DISCREPANCY"),
            lambda value: replace(value, boundary=value.boundary + 1),
            lambda value: replace(value, safe_cells=()),
            lambda value: replace(value, v1_decision=replace(value.v1_decision,
                move=replace(value.v1_decision.move, x=3))),
        )
        for corrupt in corruptions:
            def compare(*args, **kwargs):
                return corrupt(original(*args, **kwargs))

            with self.subTest(corruption=corrupt), \
                    patch.object(runner, "compare_shadow_soundness", side_effect=compare) as patched:
                result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table)
            self.assertEqual(patched.call_count, 1)
            self.assertEqual(result.shadow.failure.failure_class, "SHADOW_COMPARISON_EXCEPTION")
            self.assertFalse(result.shadow.enabled)
            self.assertEqual(result.final_M, frozenset())
            self.assertEqual(result.moves, control.moves)
            self.assertEqual(result.status, control.status)

    def test_comparator_timeout_is_contained_and_late_result_cannot_commit(self):
        entered, release, finished = Event(), Event(), Event()
        original = runner.compare_shadow_soundness
        late_results = []

        def blocked(*args, **kwargs):
            entered.set()
            release.wait(2)
            try:
                value = original(*args, **kwargs)
                late_results.append(value)
                return value
            finally:
                finished.set()

        with patch.object(runner, "compare_shadow_soundness", side_effect=blocked) as compare:
            try:
                result = runner.run_k_control(PublicPort(fixed_engine()), table=self.table, shadow_timeout_s=0.05)
                self.assertTrue(entered.is_set())
                self.assertFalse(finished.is_set())
                self.assertEqual(result.shadow.failure.failure_class, "SHADOW_TIMEOUT")
                self.assertFalse(result.shadow.enabled)
                self.assertEqual(result.final_M, frozenset())
                self.assertIsNone(result.traces[1].timings.shadow_ns)
                self.assertIsNone(result.traces[1].timings.comparison_ns)
                self.assertIsNone(result.traces[1].timings.oracle_ns)
                self.assertEqual(result.moves, run_stage3(fixed_engine(), table=self.table).moves)
            finally:
                release.set()
                self.assertTrue(finished.wait(2))
            self.assertEqual(compare.call_count, 1)
            self.assertEqual(len(late_results), 1)
            self.assertEqual(result.final_M, frozenset())
            self.assertFalse(result.shadow.enabled)


class ProgramKSlice7EvaluatorTests(unittest.TestCase):
    """Post-hoc synthetic falsification only; never execution or public proof."""

    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def sealed(self, *assertions, width=4, height=2):
        # Explicit synthetic archive identity, not a real research artifact.
        return evaluator.SealedEvaluatorInput(
            "unit-evaluator-case", "unit-evaluator-run", width, height,
            tuple(assertions), "a" * 64,
        )

    def answer(self, mines, *, width=4, height=2):
        return evaluator.HiddenAnswer(
            "unit-evaluator-case", "unit-evaluator-run", width, height,
            frozenset(mines),
        )

    def check_one(self, kind, cells, mines):
        assertion = evaluator.ArchivedAssertion(kind, 2, tuple(cells))
        sealed = self.sealed(assertion)
        return evaluator.evaluate_falsification(sealed, self.answer(mines))

    def bound_archive(self, *, loss=False, variant="K-P0"):
        from experiments import program_k_harness as h
        mines = frozenset({(1, 0), (2, 0)}) if loss else frozenset({(1, 0)})
        engine = fixed_engine(5 if loss else 4, 1, mines)
        run = runner.run_k_p0 if variant == "K-P0" else runner.run_k_control
        produced = run(engine, table=self.table, capture_effects=True)
        archive = h.ExecutionArchive("terminal-binding-unit", variant, produced)
        sealed = h.seal_execution_archive(archive, run_id="terminal-binding-run")
        terminal = produced.traces[-1].public_effect.after_observation
        answer = evaluator.derive_terminal_answer(
            sealed, terminal_status=terminal.status.name, terminal_rows=terminal.rows,
            num_mines=len(mines))
        return archive, sealed, answer

    def test_bound_won_truth_exactly_reconstructs_automatic_and_existing_flags(self):
        from experiments import program_k_harness as h
        for variant in ("K-P0", "K-CONTROL"):
            with self.subTest(variant=variant):
                archive, sealed, answer = self.bound_archive(variant=variant)
                self.assertIs(archive.result.status, GameStatus.WON)
                self.assertEqual(answer.mines, frozenset({(1, 0)}))
                self.assertEqual(answer.num_mines, 1)
                self.assertEqual(answer.archive_digest, h.content_digest(archive))
                self.assertEqual((answer.case_id, answer.run_id, answer.width, answer.height),
                                 (sealed.case_id, sealed.run_id, 4, 1))
                finding = evaluator.evaluate_falsification(sealed, answer)
                evaluator.verify_bound_finding(finding, sealed, answer)
                self.assertEqual(finding.classification, "NO_COUNTEREXAMPLE")
                self.assertFalse(finding.proof_upgrade_allowed)
                self.assertEqual(archive.result.final_M, frozenset({(1, 0)}))

    def test_bound_lost_truth_includes_mine_exploded_flagged_and_excludes_false_flag(self):
        from experiments import program_k_harness as h
        # Deliberately incorrect physical flags are confined to this manual
        # Engine/effect fixture, not asserted to be a valid K policy execution.
        mines = frozenset({(1, 0), (3, 0), (5, 0)})
        engine = fixed_engine(6, 2, mines)
        effects, cursor = [], (0, 0)
        for index, move in enumerate((SimpleMove(Action.OPEN, 0, 0),
                                      SimpleMove(Action.FLAG, 1, 0),
                                      SimpleMove(Action.FLAG, 0, 1),
                                      SimpleMove(Action.OPEN, 3, 0))):
            before = engine.get_observation()
            engine.step(move.x, move.y, move.action)
            effects.append(evidence_records.make_public_effect(
                before, move, engine.get_observation(), input_index=index,
                status_after=engine.status, cursor_before=cursor,
                modeled_action_us=self.table[abs(move.x-cursor[0])][abs(move.y-cursor[1])]))
            cursor = (move.x, move.y)
        self.assertEqual(evidence_records.validate_public_effect_stream(
            tuple(effects), complete=True).status, "PASS")
        terminal = effects[-1].after_observation
        self.assertIs(terminal.status, GameStatus.LOST)
        for cell, glyph in (((1, 0), CellState.FLAGGED), ((3, 0), CellState.EXPLODED),
                            ((5, 0), CellState.MINE), ((0, 1), CellState.FALSE_FLAG)):
            self.assertEqual(terminal.rows[cell[1]][cell[0]], int(glyph))
        sealed = evaluator.SealedEvaluatorInput(
            "manual-terminal-glyph-unit", "terminal-binding-run", 6, 2,
            (evaluator.ArchivedAssertion("LOGICAL_M", 3, mines),),
            h.content_digest(tuple(effects)))
        answer = evaluator.derive_terminal_answer(
            sealed, terminal_status="LOST", terminal_rows=terminal.rows, num_mines=3)
        self.assertEqual(answer.mines, mines)
        self.assertNotIn((0, 1), answer.mines)
        self.assertNotIn((2, 1), answer.mines)  # A still HIDDEN safe cell.
        finding = evaluator.evaluate_falsification(sealed, answer)
        evaluator.verify_bound_finding(finding, sealed, answer)
        self.assertEqual(finding.classification, "NO_COUNTEREXAMPLE")

    def test_terminal_truth_rejects_malformed_ambiguous_outcome_and_wrong_count(self):
        _, sealed, _ = self.bound_archive()
        base = dict(terminal_status="WON", terminal_rows=((1, F, 1, 0),), num_mines=1)
        changes = (
            {"terminal_status": "PLAYING"}, {"terminal_status": GameStatus.WON},
            {"terminal_rows": ((1, F, 1),)}, {"terminal_rows": [[1, F, 1, 0]]},
            {"terminal_rows": ((True, F, 1, 0),)}, {"terminal_rows": ((9, F, 1, 0),)},
            {"terminal_rows": ((0, F, 1, 0),)}, {"terminal_rows": ((1, F, 1, H),)},
            {"terminal_rows": ((1, int(CellState.EXPLODED), 1, 0),)},
            {"terminal_rows": ((1, int(CellState.MINE), 1, 0),)},
            {"terminal_rows": ((1, F, 1, int(CellState.FALSE_FLAG)),)},
            {"terminal_status": "LOST"},  # No exploded mine.
            {"num_mines": 0}, {"num_mines": 2}, {"num_mines": True},
            {"num_mines": 1.0}, {"num_mines": None},
        )
        for changed in changes:
            with self.subTest(changed=changed), self.assertRaises(evaluator.EvaluatorInputError):
                evaluator.derive_terminal_answer(sealed, **(base | changed))

    def test_wrong_same_size_layout_and_unbound_matching_answer_cannot_qualify(self):
        _, sealed, answer = self.bound_archive(loss=True)
        self.assertEqual(answer.mines, frozenset({(1, 0), (2, 0)}))
        # The changed mine is an excluded uncertain guess, so the old unbound
        # comparison alone would report agreement with every certainty claim.
        wrong = replace(answer, mines=frozenset({(1, 0), (3, 0)}))
        unbound = replace(answer, archive_digest=None, num_mines=None)
        for supplied in (wrong, unbound):
            finding = evaluator.evaluate_falsification(sealed, supplied)
            self.assertEqual(finding.classification, "NO_COUNTEREXAMPLE")
            self.assertNotEqual(finding.answer_digest, answer.answer_digest)
            with self.assertRaises(evaluator.EvaluatorInputError):
                evaluator.verify_bound_finding(finding, sealed, answer)
        with self.assertRaises(evaluator.EvaluatorInputError):
            evaluator.verify_bound_finding(
                evaluator.evaluate_falsification(sealed, unbound), sealed, unbound)

    def test_bound_identity_mine_count_and_finding_sequence_fail_closed(self):
        _, sealed, answer = self.bound_archive()
        finding = evaluator.evaluate_falsification(sealed, answer)
        for changed in ({"case_id": "other-case"}, {"run_id": "other-run"},
                        {"width": 5}, {"height": 2}, {"archive_digest": "f"*64}):
            with self.subTest(changed=changed), self.assertRaises(evaluator.EvaluatorInputError):
                evaluator.evaluate_falsification(sealed, replace(answer, **changed))
        for changed in ({"num_mines": 2}, {"num_mines": True},
                        {"archive_digest": None}, {"num_mines": None},
                        {"mines": frozenset()}):
            with self.subTest(changed=changed), self.assertRaises(evaluator.EvaluatorInputError):
                replace(answer, **changed)
        for changed in (finding.findings[:-1], finding.findings + finding.findings[-1:],
                        finding.findings[::-1]):
            corrupted = deepcopy(finding)
            object.__setattr__(corrupted, "findings", changed)
            with self.subTest(length=len(changed)), self.assertRaises(evaluator.EvaluatorInputError):
                evaluator.verify_bound_finding(corrupted, sealed, answer)
        checked = next(item for item in finding.findings if item.comparisons)
        bad_comparison = replace(checked.comparisons[0], hidden_mine=not checked.comparisons[0].hidden_mine)
        forged = replace(finding, findings=tuple(
            replace(item, comparisons=(bad_comparison,) + item.comparisons[1:])
            if item is checked else item for item in finding.findings))
        # A correct answer hash cannot authenticate fabricated comparison bits.
        self.assertEqual(forged.answer_digest, answer.answer_digest)
        with self.assertRaises(evaluator.EvaluatorInputError):
            evaluator.verify_bound_finding(forged, sealed, answer)

    def test_bound_truth_and_findings_cannot_resume_or_mutate_archived_solver(self):
        from experiments import program_k_harness as h
        archive, sealed, answer = self.bound_archive()
        before = h.canonical_bytes(archive)
        terminal = archive.result.traces[-1].public_effect.after_observation
        blocked = AssertionError("Post-hoc truth must never resume solver/public proof")
        with patch.object(KLocalSession, "analyze_decision", side_effect=blocked), \
                patch.object(runner, "run_k_p0", side_effect=blocked), \
                patch.object(runner, "run_k_control", side_effect=blocked), \
                patch.object(runner, "select_policy", side_effect=blocked), \
                patch.object(public_oracles, "enumerate_public_worlds", side_effect=blocked), \
                patch.object(public_oracles, "materialized_exact_reference", side_effect=blocked), \
                patch.object(public_oracles, "verify_local_certificate", side_effect=blocked):
            derived = evaluator.derive_terminal_answer(
                sealed, terminal_status=terminal.status.name, terminal_rows=terminal.rows, num_mines=1)
            result = evaluator.evaluate_falsification(sealed, derived)
            evaluator.verify_bound_finding(result, sealed, answer)
        self.assertEqual(h.canonical_bytes(archive), before)
        with self.assertRaises(KIntegrityError):
            KLocalSession(4, 1, 1).analyze_decision(answer, status=PLAYING)
        with self.assertRaises(public_oracles.PublicProofError):
            public_oracles.enumerate_public_worlds(answer, 1, status=PLAYING)
        with self.assertRaises(KIntegrityError):
            select_policy(answer, (0, 0), self.table)

    def test_evaluator_call_durations_and_coverage_are_separate_from_semantics(self):
        _, sealed, answer = self.bound_archive()
        baseline = evaluator.evaluate_falsification(sealed, answer)
        with evaluator.collect_evaluator_diagnostics() as records:
            first = evaluator.evaluate_falsification(sealed, answer)
            second = evaluator.evaluate_falsification(sealed, answer)
        self.assertEqual(first, second)
        self.assertEqual(first, baseline)
        self.assertEqual(tuple(r.sequence for r in records), (0, 1))
        for record in records:
            self.assertIs(type(record.duration_ns), int)
            self.assertGreaterEqual(record.duration_ns, 0)
            self.assertEqual(record.sealed_input_digest, sealed.assertions_digest)
            self.assertEqual(record.answer_digest, answer.answer_digest)
            self.assertEqual(record.classification, first.classification)
            self.assertEqual(record.evaluated_coordinate_count, first.evaluated_coordinate_count)
            self.assertIsNone(record.error)
            self.assertEqual(pickle.loads(pickle.dumps(record)), record)
        self.assertNotIn("duration_ns", {field.name for field in fields(first)})
        with evaluator.collect_evaluator_diagnostics() as absent:
            evaluator.verify_bound_finding(first, sealed, answer)
        self.assertEqual(absent, [])  # Validation does not generate another evaluation.

    def test_evaluator_empty_error_and_nested_call_diagnostics_are_lossless(self):
        sealed = self.sealed(evaluator.ArchivedAssertion("LOGICAL_M", 0, ()))
        answer = self.answer({(1, 0)})
        with evaluator.collect_evaluator_diagnostics() as outer:
            with evaluator.collect_evaluator_diagnostics() as inner:
                result = evaluator.evaluate_falsification(sealed, answer)
                with self.assertRaises(evaluator.EvaluatorInputError):
                    evaluator.evaluate_falsification(sealed, None)
        self.assertEqual(inner, outer)
        self.assertEqual(len(outer), 2)  # One record per call, not nested-span sums.
        self.assertEqual(result.classification, "NOT_EVALUATED")
        self.assertEqual(outer[0].classification, "NOT_EVALUATED")
        self.assertEqual(outer[0].evaluated_coordinate_count, 0)
        self.assertEqual(outer[1].classification, "ERROR")
        self.assertIsNone(outer[1].evaluated_coordinate_count)
        self.assertIsNone(outer[1].answer_digest)
        self.assertTrue(outer[1].error)
        for change in ({"duration_ns": True}, {"duration_ns": -1},
                       {"duration_ns": None}, {"evaluated_coordinate_count": None},
                       {"classification": "NO_COUNTEREXAMPLE"}):
            with self.subTest(change=change), self.assertRaises(evaluator.EvaluatorInputError):
                replace(outer[0], **change)

    def test_j_correct_m_is_no_counterexample_only_and_never_a_proof_upgrade(self):
        owner, decision = public_decision(HISTORICAL, 1)
        assertion = evaluator.ArchivedAssertion("LOGICAL_M", 1, owner.M)
        sealed = self.sealed(assertion, height=1)
        result = evaluator.evaluate_falsification(sealed, self.answer({(1, 0)}, height=1))
        self.assertEqual(result.classification, "NO_COUNTEREXAMPLE")
        self.assertFalse(result.proof_upgrade_allowed)
        self.assertFalse(result.research_progression_must_stop)
        self.assertEqual(result.findings[0].counterexamples, ())
        self.assertEqual(result.evaluated_coordinate_count, 1)
        self.assertEqual(owner.M, {(1, 0)})
        self.assertEqual(result.sealed_input, sealed)
        self.assertNotIsInstance(result, public_oracles.LocalMineCertificate)
        self.assertEqual(public_oracles.verify_local_certificate(decision.local.certificates[0]).target,
                         (1, 0))

    def test_k_false_m_is_one_way_g1_falsification_with_exact_boundary_and_coordinates(self):
        result = self.check_one("LOGICAL_M", ((1, 0), (0, 1)), {(1, 0)})
        finding, = result.findings
        self.assertEqual(result.classification, "G1_FALSIFICATION")
        self.assertTrue(result.research_progression_must_stop)
        self.assertFalse(result.proof_upgrade_allowed)
        self.assertEqual(result.case_id, "unit-evaluator-case")
        self.assertEqual(result.run_id, "unit-evaluator-run")
        self.assertEqual(finding.assertion.physical_input_boundary, 2)
        self.assertEqual(finding.counterexamples, ((0, 1),))
        self.assertEqual(tuple((c.coordinate, c.asserted_mine, c.hidden_mine)
                               for c in finding.comparisons),
                         (((1, 0), True, True), ((0, 1), True, False)))

    def test_j_k_correct_and_false_certainty_open_are_compared_as_safe_assertions(self):
        for mines, expected in (({(1, 0)}, "NO_COUNTEREXAMPLE"),
                                ({(3, 0)}, "G1_FALSIFICATION")):
            with self.subTest(mines=mines):
                result = self.check_one("CERTAINTY_OPEN", ((3, 0),), mines)
                self.assertEqual(result.classification, expected)
                self.assertFalse(result.proof_upgrade_allowed)
                comparison, = result.findings[0].comparisons
                self.assertIs(comparison.asserted_mine, False)
                self.assertEqual(comparison.coordinate, (3, 0))
                self.assertEqual(result.findings[0].counterexamples,
                                 () if expected == "NO_COUNTEREXAMPLE" else ((3, 0),))

    def test_j_k_productive_chord_opened_safe_set_and_one_mine_falsification(self):
        for mines, expected in (({(1, 0)}, "NO_COUNTEREXAMPLE"),
                                ({(1, 0), (3, 1)}, "G1_FALSIFICATION")):
            with self.subTest(mines=mines):
                result = self.check_one("CERTAINTY_CHORD_OPENED", ((3, 1), (3, 0)), mines)
                finding, = result.findings
                self.assertEqual(result.classification, expected)
                self.assertEqual(finding.assertion.coordinates, ((3, 0), (3, 1)))
                self.assertEqual(result.evaluated_coordinate_count, 2)
                self.assertTrue(all(c.asserted_mine is False for c in finding.comparisons))
                self.assertEqual(finding.counterexamples,
                                 () if expected == "NO_COUNTEREXAMPLE" else ((3, 1),))

    def test_initial_open_and_uncertain_exact_guess_are_excluded_even_when_they_hit_mines(self):
        sealed = self.sealed(
            evaluator.ArchivedAssertion("POLICY_INITIAL_OPEN", 0, ((0, 0),)),
            evaluator.ArchivedAssertion("EXACT_MINIMUM_RISK_GUESS", 3, ((2, 0),)),
        )
        result = evaluator.evaluate_falsification(sealed, self.answer({(0, 0), (2, 0)}))
        self.assertEqual(result.classification, "NOT_EVALUATED")
        self.assertEqual(result.excluded_assertion_count, 2)
        self.assertEqual(result.evaluated_coordinate_count, 0)
        self.assertFalse(result.research_progression_must_stop)
        self.assertFalse(result.proof_upgrade_allowed)
        for finding in result.findings:
            self.assertEqual(finding.classification, "EXCLUDED_NONCERTAINTY")
            self.assertEqual(finding.comparisons, ())
            self.assertEqual(finding.counterexamples, ())

    def test_empty_m_is_explicitly_not_evaluated_and_initial_input_cannot_be_certainty(self):
        result = evaluator.evaluate_falsification(
            self.sealed(evaluator.ArchivedAssertion("LOGICAL_M", 0, ())), self.answer({(1, 0)}))
        self.assertEqual(result.classification, "NOT_EVALUATED")
        self.assertEqual(result.findings[0].classification, "NOT_EVALUATED")
        for kind in ("LOGICAL_M", "CERTAINTY_OPEN", "CERTAINTY_CHORD_OPENED",
                     "EXACT_MINIMUM_RISK_GUESS"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                evaluator.ArchivedAssertion(kind, 0, ((0, 0),))
        with self.assertRaises(ValueError):
            evaluator.ArchivedAssertion("POLICY_INITIAL_OPEN", 1, ((0, 0),))

    def test_l_result_answer_and_seal_are_rejected_by_capability_oracles_and_public_proof_apis(self):
        result = self.check_one("LOGICAL_M", ((1, 0),), {(1, 0)})
        owner, decision = public_decision(HISTORICAL, 1)
        proof = decision.local.certificates[0]
        forbidden = (result, result.sealed_input, self.answer({(1, 0)}))
        for value in forbidden:
            with self.subTest(type=type(value).__name__):
                with self.assertRaises(KIntegrityError):
                    owner.analyze_decision(value, status=PLAYING)
                with self.assertRaises(KIntegrityError):
                    select_policy(value, (0, 0), self.table)
                with self.assertRaises(public_oracles.PublicProofError):
                    public_oracles.enumerate_public_worlds(value, 1, status=PLAYING)
                with self.assertRaises(public_oracles.PublicProofError):
                    public_oracles.materialized_exact_reference(value, 1, status=PLAYING)
                with self.assertRaises(public_oracles.PublicProofError):
                    public_oracles.verify_local_certificate(value)
                with self.assertRaises(public_oracles.PublicProofError):
                    public_oracles.verify_exact_global_certificate(value)
                with self.assertRaises(public_oracles.PublicProofError):
                    public_oracles.verify_local_certificate(proof, prior_certificates=(value,))
                self.assertEqual(evidence_records.compare_v1_decisions(value, value, boundary=1).status,
                                 "INCOMPLETE")
        self.assertEqual(owner.M, {(1, 0)})

    def test_l_evaluator_keywords_cannot_be_attached_to_solver_or_public_proof_inputs(self):
        result = self.check_one("LOGICAL_M", ((1, 0),), {(1, 0)})
        owner, decision = public_decision(HISTORICAL, 1)
        proof = decision.local.certificates[0]
        for keyword in ("evaluator", "evaluator_result", "hidden_answer", "answer"):
            for function, args, kwargs in (
                (owner.analyze_decision, (HISTORICAL,), {"status": PLAYING}),
                (select_policy, (decision, (0, 0), self.table), {}),
                (public_oracles.enumerate_public_worlds, (HISTORICAL, 1), {"status": PLAYING}),
                (public_oracles.materialized_exact_reference, (HISTORICAL, 1), {"status": PLAYING}),
                (public_oracles.verify_local_certificate, (proof,), {}),
            ):
                with self.subTest(keyword=keyword, function=function.__name__), self.assertRaises(TypeError):
                    function(*args, **kwargs, **{keyword: result})

    def test_l_changing_truth_cannot_change_already_produced_or_next_public_decision(self):
        owner, decision = public_decision(HISTORICAL, 1)
        selected = select_policy(decision, (0, 0), self.table)
        before = pickle.dumps((decision, selected, owner.M))
        sealed = self.sealed(evaluator.ArchivedAssertion("LOGICAL_M", 1, owner.M), height=1)
        correct = evaluator.evaluate_falsification(sealed, self.answer({(1, 0)}, height=1))
        false = evaluator.evaluate_falsification(sealed, self.answer({(3, 0)}, height=1))
        self.assertEqual(correct.classification, "NO_COUNTEREXAMPLE")
        self.assertEqual(false.classification, "G1_FALSIFICATION")
        self.assertNotEqual(correct.answer_digest, false.answer_digest)
        self.assertEqual(pickle.dumps((decision, selected, owner.M)), before)
        # A repeated public-prefix call is a pure unit check, not a resumed run.
        fresh = owner.analyze_decision(HISTORICAL, status=PLAYING)
        control_owner, _ = public_decision(HISTORICAL, 1)
        control = control_owner.analyze_decision(HISTORICAL, status=PLAYING)
        self.assertEqual(fresh, control)
        self.assertEqual(select_policy(fresh, (0, 0), self.table),
                         select_policy(control, (0, 0), self.table))
        self.assertEqual(owner.M, {(1, 0)})

    def test_l_two_public_consistent_answers_do_not_change_exact_guess_or_proofs(self):
        # Both one-mine layouts satisfy the same single public clue.
        public = ((H, 1, H),)
        owner, decision = public_decision(public, 1)
        selected = select_policy(decision, (0, 0), self.table)
        sealed = self.sealed(evaluator.ArchivedAssertion(
            "EXACT_MINIMUM_RISK_GUESS", 1, ((selected.move.x, selected.move.y),)), width=3, height=1)
        prior = deepcopy((decision, selected))
        for mines in ({(0, 0)}, {(2, 0)}):
            result = evaluator.evaluate_falsification(sealed, self.answer(mines, width=3, height=1))
            self.assertEqual(result.classification, "NOT_EVALUATED")
            fresh = KLocalSession(3, 1, 1).analyze_decision(public, status=PLAYING)
            self.assertEqual((decision, selected), prior)
            self.assertEqual(fresh, decision)
            self.assertEqual(select_policy(fresh, (0, 0), self.table), selected)
            self.assertEqual(public_oracles.enumerate_public_worlds(public, 1, status=PLAYING).total_worlds, 2)
        self.assertEqual(owner.M, frozenset())

    def test_l_falsification_cannot_mutate_or_archive_repair_m_or_a_completed_unit_result(self):
        produced = runner.run_k_p0(PublicPort(fixed_engine()), table=self.table)
        archived_before = pickle.dumps(produced)
        sealed = self.sealed(evaluator.ArchivedAssertion(
            "LOGICAL_M", len(produced.traces) - 1, produced.final_M), height=1)
        for mines, classification in (({(1, 0)}, "NO_COUNTEREXAMPLE"),
                                      ({(3, 0)}, "G1_FALSIFICATION")):
            result = evaluator.evaluate_falsification(sealed, self.answer(mines, height=1))
            self.assertEqual(result.classification, classification)
            self.assertEqual(pickle.dumps(produced), archived_before)
            self.assertEqual(produced.final_M, {(1, 0)})
            self.assertFalse(result.proof_upgrade_allowed)
            with self.assertRaises((FrozenInstanceError, AttributeError, TypeError)):
                result.sealed_input.assertions[0].coordinates = ()

    def test_evaluator_requires_matching_case_run_dimensions_and_separate_answer_type(self):
        sealed = self.sealed(evaluator.ArchivedAssertion("LOGICAL_M", 1, ((1, 0),)))
        answer = self.answer({(1, 0)})
        for changes in ({"case_id": "other-case"}, {"run_id": "other-run"},
                        {"width": 5}, {"height": 3}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                evaluator.evaluate_falsification(sealed, replace(answer, **changes))
        for value in (fixed_engine(), Untouchable(), {}, None, sealed):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                evaluator.evaluate_falsification(sealed, value)
        for value in (fixed_engine(), Untouchable(), answer, (), None):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                evaluator.evaluate_falsification(value, answer)

    def test_sealed_coordinates_are_true_integer_xy_and_have_deterministic_screen_order(self):
        first = evaluator.ArchivedAssertion("LOGICAL_M", 2, ((0, 1), (3, 0), (1, 0)))
        second = evaluator.ArchivedAssertion("LOGICAL_M", 2, frozenset({(1, 0), (0, 1), (3, 0)}))
        self.assertEqual(first, second)
        self.assertEqual(first.coordinates, ((1, 0), (3, 0), (0, 1)))
        self.assertEqual(self.sealed(first).assertions_digest, self.sealed(second).assertions_digest)
        for cells in ([(1, 0)], ((True, 0),), ((1.0, 0),), ((-1, 0),),
                      ((30, 0),), ((1, 16),), ((1, 0), (1, 0)), Untouchable()):
            with self.subTest(cells=type(cells).__name__), self.assertRaises(ValueError):
                evaluator.ArchivedAssertion("LOGICAL_M", 1, cells)
        with self.assertRaises(ValueError):
            self.sealed(first, width=3)
        for bad in (True, 1.0, -1, "1"):
            with self.subTest(boundary=bad), self.assertRaises(ValueError):
                evaluator.ArchivedAssertion("LOGICAL_M", bad, ())

    def test_malformed_missing_or_reordered_sealed_evidence_is_rejected(self):
        a = evaluator.ArchivedAssertion("LOGICAL_M", 1, ((1, 0),))
        b = evaluator.ArchivedAssertion("CERTAINTY_OPEN", 2, ((3, 0),))
        sealed = self.sealed(a, b)
        for changes in ({"assertions": [a]}, {"assertions": (b, a)}, {"assertions": (a, a)},
                        {"archive_digest": ""}, {"archive_digest": "g" * 64},
                        {"case_id": " "}, {"width": True}, {"height": float("inf")}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(sealed, **changes)
        corrupted = deepcopy(sealed)
        object.__setattr__(corrupted.assertions[0], "coordinates", ((False, 0),))
        with self.assertRaises(ValueError):
            evaluator.evaluate_falsification(corrupted, self.answer({(1, 0)}))
        result = evaluator.evaluate_falsification(sealed, self.answer({(1, 0)}))
        with self.assertRaises(ValueError):
            replace(result, findings=result.findings[:-1])
        with self.assertRaises(ValueError):
            replace(result, findings=result.findings[::-1])

    def test_evaluator_records_are_recursively_immutable_detached_and_reconstructable(self):
        sealed = self.sealed(evaluator.ArchivedAssertion("LOGICAL_M", 1, ((1, 0),)))
        answer = self.answer({(1, 0)})
        result = evaluator.evaluate_falsification(sealed, answer)

        def inspect_record(value):
            self.assertNotIsInstance(value, (MinesweeperEngine, KLocalSession, PublicPort))
            self.assertFalse(callable(value))
            if is_dataclass(value):
                self.assertTrue(type(value).__dataclass_params__.frozen)
                self.assertFalse(hasattr(value, "__dict__"))
                for field in fields(value):
                    inspect_record(getattr(value, field.name))
            elif type(value) in (tuple, frozenset):
                for child in value:
                    inspect_record(child)
            else:
                self.assertIn(type(value), (str, int, bool, type(None)))

        for record in (sealed, answer, result):
            inspect_record(record)
            self.assertEqual(pickle.loads(pickle.dumps(record)), record)
        self.assertEqual(result.answer_digest, answer.answer_digest)
        self.assertEqual(len(sealed.assertions_digest), 64)
        self.assertEqual(replace(sealed).assertions_digest, sealed.assertions_digest)
        with self.assertRaises(FrozenInstanceError):
            result.findings[0].comparisons[0].hidden_mine = False
        self.assertNotIn("mines", {field.name for field in fields(result)})

    def test_y_evaluator_imports_no_engine_solver_or_oracle_and_no_production_imports_it(self):
        import runpy
        blocked = {name: None for name in (
            "core_engine", "simple_algorithm", "simple_probability", "simple_decision",
            "stage3_planner", "stage3_runner", "experiments.program_k_capability",
            "experiments.program_k_policy", "experiments.program_k_runner",
            "experiments.program_k_oracles", "experiments.program_k_evidence",
        )}
        with patch.dict(sys.modules, blocked):
            isolated = runpy.run_path(evaluator.__file__)
            assertion = isolated["ArchivedAssertion"]("LOGICAL_M", 1, ((1, 0),))
            sealed = isolated["SealedEvaluatorInput"]("unit", "unit", 4, 1, (assertion,), "b" * 64)
            answer = isolated["HiddenAnswer"]("unit", "unit", 4, 1, frozenset({(1, 0)}))
            result = isolated["evaluate_falsification"](sealed, answer)
        self.assertEqual(result.classification, "NO_COUNTEREXAMPLE")
        root = Path(__file__).resolve().parents[1]
        paths = tuple(root.glob("*.py")) + tuple((root / "scripts").rglob("*.py"))
        paths += tuple(root / "experiments" / ("program_k_" + name + ".py")
                       for name in ("capability", "policy", "runner", "oracles", "evidence"))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = tuple(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported = (node.module or "",) + tuple(alias.name for alias in node.names)
                else:
                    continue
                with self.subTest(source=str(path)):
                    self.assertFalse(any("program_k_evaluator" in name for name in imported))


class ProgramKSlice7ManifestTests(unittest.TestCase):
    """Literal A-E4 implementation checks; no E0 dispatcher or P-8 scan."""

    @classmethod
    def setUpClass(cls):
        from experiments import program_k_harness

        cls.harness = program_k_harness
        cls.manifest = program_k_harness.MANIFEST
        cls.results = tuple(program_k_harness.verify_fixture(f) for f in cls.manifest)
        cls.by_id = {r.fixture.fixture_id: r for r in cls.results}

    def test_a_manifest_and_all_nested_evidence_are_immutable_deterministic(self):
        harness = self.harness
        self.assertIs(type(self.manifest), tuple)
        before = harness.canonical_bytes(self.manifest)
        digest = harness.content_digest(self.manifest)
        for _ in range(3):
            self.assertEqual(harness.canonical_bytes(self.manifest), before)
            self.assertEqual(harness.content_digest(self.manifest), digest)
            self.assertEqual(harness.reconstruct(before, expected_digest=digest), self.manifest)
        self.assertEqual(len(digest), 64)

        def check_immutable(value):
            if is_dataclass(value):
                self.assertTrue(type(value).__dataclass_params__.frozen)
                for field in fields(value):
                    check_immutable(getattr(value, field.name))
            elif type(value) is tuple:
                for child in value:
                    check_immutable(child)
            else:
                self.assertIn(type(value), (str, int, type(None)))

        check_immutable(self.manifest)
        with self.assertRaises(FrozenInstanceError):
            self.manifest[0].num_mines = 2
        with self.assertRaises(FrozenInstanceError):
            self.manifest[0].expectations[0].Z = 7
        with self.assertRaises(TypeError):
            self.manifest[0].observation[0][0] = 0
        with self.assertRaises(TypeError):
            self.manifest[0].expectations[0].mine_worlds[0] = ((0, 0), 99)

    def test_b_required_fixture_identities_exist_exactly_once(self):
        names = tuple(f.fixture_id for f in self.manifest)
        self.assertEqual(names, self.harness.REQUIRED_FIXTURE_IDS)
        self.assertEqual(len(names), 30)
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue({
            "no-new-m", "historical-normalized-safe", "simultaneous-local-acquisition",
            "public-fixed-mine-basis", "frontier-only", "floating-only",
            "frontier-floating", "multiple-components-floating", "g0-only", "g1-only",
            "simultaneous-g1-g0", "g1-restriction", "empty-g1", "exact-equal-risk-tie",
            "empty-u-entry", "empty-u-local", "empty-u-global", "zero-world",
            "physical-logical-overlap", "arithmetic-extreme",
        } <= set(names))
        for fixture in self.manifest:
            self.assertEqual((len(fixture.observation[0]), len(fixture.observation)),
                             (fixture.width, fixture.height))
            self.assertEqual(len(fixture.expectations),
                             len({e.phase for e in fixture.expectations}))
            self.assertTrue(fixture.intended_check)
            self.assertTrue(fixture.rationale)

    def test_c_import_preregisters_literals_without_any_solver_or_oracle_call(self):
        from contextlib import ExitStack
        from dataclasses import asdict
        import runpy

        blocked = (
            "experiments.program_k_capability.KLocalSession.analyze_local",
            "experiments.program_k_capability.KLocalSession.analyze_decision",
            "experiments.program_k_oracles.enumerate_public_worlds",
            "experiments.program_k_oracles.materialized_exact_reference",
            "experiments.program_k_oracles.verify_local_certificate",
            "experiments.program_k_oracles.verify_exact_global_certificate",
            "simple_algorithm.build_constraints", "simple_algorithm.infer_deterministic",
            "simple_probability.calculate_probabilities", "simple_decision.analyze_position",
        )
        with ExitStack() as stack:
            sentinels = tuple(stack.enter_context(patch(name, side_effect=AssertionError(name)))
                              for name in blocked)
            imported = runpy.run_path(self.harness.__file__)
        for sentinel in sentinels:
            sentinel.assert_not_called()
        self.assertEqual(tuple(asdict(f) for f in imported["MANIFEST"]),
                         tuple(asdict(f) for f in self.manifest))
        self.assertIn("independent stdlib-only", imported["MANIFEST_DERIVATION"])
        # The import operation itself produces only declarations, never a
        # qualification result or a populated set of computed expectations.
        self.assertFalse(any(type(value) is self.harness.FixtureVerification
                             for value in imported.values()))

    def test_d_every_bounded_phase_matches_literal_complete_oracle_a_evidence(self):
        checked = 0
        for result in self.results:
            with self.subTest(fixture=result.fixture.fixture_id):
                self.assertEqual(result.status, "PASS", (result.discrepancies,
                                 tuple(p.discrepancies for p in result.phases)))
                self.assertEqual(tuple(p.expectation for p in result.phases),
                                 result.fixture.expectations)
                for phase in result.phases:
                    expectation = phase.expectation
                    self.assertEqual(phase.oracle_a_coverage.status, expectation.oracle_a_status)
                    if expectation.oracle_a_status == "ORACLE_A_NOT_EVALUATED":
                        self.assertIsNone(phase.oracle_a)
                        self.assertGreater(phase.oracle_a_coverage.variable_count, 16)
                        self.assertTrue(phase.oracle_a_coverage.reason)
                        continue
                    checked += 1
                    self.assertLessEqual(phase.oracle_a_coverage.variable_count, 16)
                    self.assertEqual(phase.oracle_a.total_worlds, expectation.Z)
                    self.assertEqual(phase.oracle_a.mine_worlds, expectation.mine_worlds)
                    self.assertEqual(phase.oracle_a.G0, frozenset(expectation.G0))
                    self.assertEqual(phase.oracle_a.G1, frozenset(expectation.G1))
                    self.assertEqual(phase.oracle_a_coverage.envelope, 16)
                    self.assertIsNone(phase.oracle_a_coverage.reason)
        self.assertEqual(checked, 71)

    def test_e_k_and_shared_kernel_b_compare_only_at_reached_exact_phases(self):
        for result in self.results:
            with self.subTest(fixture=result.fixture.fixture_id):
                for phase in result.phases:
                    expectation = phase.expectation
                    if expectation.phase in ("D", "E"):
                        self.assertIsNotNone(result.decision)
                        exact = (result.decision.phase_d if expectation.phase == "D"
                                 else result.decision.phase_e)
                        self.assertEqual(exact.total_worlds, expectation.Z)
                        self.assertEqual(exact.mine_worlds, expectation.mine_worlds)
                        self.assertEqual(exact.frontier_cells, expectation.frontier)
                        self.assertEqual(exact.unconstrained_cells, expectation.floating)
                        self.assertEqual(phase.oracle_b.total_worlds, expectation.Z)
                        self.assertEqual(phase.oracle_b.mine_worlds, expectation.mine_worlds)
                        self.assertEqual(phase.oracle_b_status, "SHARED-KERNEL REPRESENTATION EVIDENCE")
                        self.assertEqual(phase.oracle_b.kernel, "simple_probability.calculate_probabilities")
                    else:
                        self.assertIsNone(phase.oracle_b)
                        self.assertEqual(phase.oracle_b_status, "NOT_REACHED")
                if result.decision is not None and result.fixture.continuation == "LOCAL_SAFE":
                    self.assertIsNone(result.decision.phase_d)
                    self.assertIsNone(result.decision.phase_e)
                    self.assertEqual(result.decision.phase_e_status, "NOT_REACHED")
                self.assertTrue(all(a.status == "PASS" for a in result.acquisition_audits))
        with patch("simple_decision.analyze_position", side_effect=AssertionError("fresh scheduler")):
            self.assertEqual(self.harness.verify_fixture(
                self.by_id["g1-restriction"].fixture).status, "PASS")

    def test_f_transforms_freshly_pin_dimensions_order_winner_cursor_cost_and_route(self):
        expected = {
            "reflect-historical": ((4, 1), ((0, 0), (2, 0)), (0, 0), (0, 0, 126005),
                                   (("OPEN", (0, 0)),), 126005),
            "transpose-historical": ((1, 4), ((0, 1), (0, 3)), (0, 3), (0, 3, 227896),
                                     (("OPEN", (0, 3)),), 227896),
            "reflect-tie": ((3, 2), ((0, 0), (1, 0), (2, 0), (1, 1), (2, 1)),
                            (0, 0), (0, 0, 126005), None, None),
            "transpose-tie": ((2, 3), ((1, 0), (0, 1), (1, 1), (0, 2), (1, 2)),
                              (1, 0), (1, 0, 126005), None, None),
        }
        for name, (dimensions, order, target, lookup, route, latency) in expected.items():
            result = self.by_id[name]
            fixture = result.fixture
            with self.subTest(fixture=name):
                self.assertEqual((fixture.width, fixture.height), dimensions)
                self.assertEqual(fixture.screen_order, order)
                self.assertEqual(fixture.cursor, (0, 0))
                self.assertEqual(fixture.expected_target, target)
                self.assertEqual(fixture.model_c_lookup, lookup)
                self.assertEqual(fixture.expected_route, route)
                self.assertEqual(fixture.expected_latency_us, latency)
                self.assertEqual((result.selection.move.x, result.selection.move.y), target)
                if route is None:
                    self.assertIsNone(result.selection.plan)
                else:
                    self.assertEqual(tuple((m.action.name, (m.x, m.y))
                                           for m in result.selection.plan.actions), route)
                    self.assertEqual(result.selection.plan.latency_us, latency)
        # Both mapped old winners are explicitly wrong, despite valid geometry.
        for name, blindly_mapped in (("transpose-tie", (0, 1)), ("reflect-tie", (1, 1))):
            fixture = self.by_id[name].fixture
            self.assertNotEqual(fixture.tie_target, blindly_mapped)
            corrupted = replace(fixture, tie_target=blindly_mapped, expected_target=blindly_mapped)
            checked = self.harness.verify_fixture(corrupted)
            self.assertEqual(checked.status, "FAIL")
            self.assertTrue(any("tie" in d or "target" in d for d in checked.discrepancies))

    def test_g_variable_component_and_floating_weighting_pin_every_marginal(self):
        single = self.by_id["frontier-floating"].decision.phase_d
        self.assertEqual(single.total_worlds, 3)
        self.assertEqual(single.mine_worlds, (
            ((0, 0), 1), ((2, 0), 2), ((4, 0), 1), ((5, 0), 1), ((6, 0), 1)))
        self.assertEqual(single.frontier_cells, ((0, 0), (2, 0), (4, 0)))
        self.assertEqual(single.unconstrained_cells, ((5, 0), (6, 0)))
        multi = self.by_id["multiple-components-floating"].decision.phase_d
        self.assertEqual(multi.total_worlds, 10)
        self.assertEqual(multi.mine_worlds, (
            ((0, 0), 4), ((2, 0), 6), ((4, 0), 4), ((5, 0), 4), ((6, 0), 4),
            ((7, 0), 4), ((8, 0), 4), ((10, 0), 6), ((12, 0), 4)))
        self.assertEqual(multi.frontier_cells, ((0, 0), (2, 0), (4, 0), (8, 0), (10, 0), (12, 0)))
        self.assertEqual(multi.unconstrained_cells, ((5, 0), (6, 0), (7, 0)))
        # Sum of all mine indicators equals global mine total in every world.
        self.assertEqual(sum(n for _, n in single.mine_worlds), 2 * single.total_worlds)
        self.assertEqual(sum(n for _, n in multi.mine_worlds), 4 * multi.total_worlds)

    def test_h_arithmetic_extreme_preserves_unrepresentable_integer_counts(self):
        result = self.by_id["arithmetic-extreme"]
        expected_z, expected_m = 88004802264174740, 39602161018878633
        self.assertEqual((result.fixture.width, result.fixture.height, result.fixture.num_mines),
                         (30, 2, 27))
        for phase in result.phases:
            self.assertEqual(phase.expectation.Z, expected_z)
            self.assertEqual(len(phase.expectation.mine_worlds), 60)
            self.assertTrue(all(type(n) is int and n == expected_m
                                for _, n in phase.expectation.mine_worlds))
            self.assertEqual(phase.oracle_a_coverage.status, "ORACLE_A_NOT_EVALUATED")
            self.assertEqual(phase.oracle_a_coverage.variable_count, 60)
            self.assertIsNone(phase.oracle_a)
        exact = result.decision.phase_d
        self.assertIs(type(exact.total_worlds), int)
        self.assertEqual(exact.total_worlds, expected_z)
        self.assertEqual(exact.minimum_risk, Fraction(9, 20))
        self.assertNotEqual(int(float(expected_z)), expected_z)
        self.assertNotEqual(int(float(expected_m)), expected_m)
        self.assertEqual(exact.G0, frozenset())
        self.assertEqual(exact.G1, frozenset())
        self.assertEqual(result.decision.guess_target, (0, 0))

    def test_i_zero_world_and_each_empty_u_failure_are_registered_rejections(self):
        for name, code in (("zero-world", "ZERO_WORLDS"),
                           ("empty-u-entry", "EMPTY_U_PLAYING"),
                           ("empty-u-local", "EMPTY_U_PLAYING"),
                           ("empty-u-global", "EMPTY_U_PLAYING")):
            result = self.by_id[name]
            with self.subTest(fixture=name):
                self.assertEqual(result.status, "PASS")  # Detection test only.
                self.assertEqual(result.failure_code, code)
                self.assertIsNone(result.decision)
                self.assertIsNone(result.selection)
                self.assertEqual(result.final_M, frozenset())
                self.assertEqual(tuple(p.expectation.phase for p in result.phases), ("A",))
        zero = self.by_id["zero-world"].phases[0].oracle_a
        self.assertEqual(zero.total_worlds, 0)
        self.assertEqual(zero.mine_worlds, (((0, 0), 0), ((2, 0), 0)))
        self.assertEqual((zero.G0, zero.G1), (frozenset(), frozenset()))

    def test_j_changed_manifest_expectation_is_detected_and_original_not_modified(self):
        fixture = self.by_id["frontier-floating"].fixture
        before = self.harness.canonical_bytes(self.manifest)
        expected = fixture.expectations[0]
        changed = replace(expected, mine_worlds=(((0, 0), 2),) + expected.mine_worlds[1:])
        corrupted = replace(fixture, expectations=(changed,) + fixture.expectations[1:])
        checked = self.harness.verify_fixture(corrupted)
        self.assertEqual(checked.status, "FAIL")
        self.assertTrue(any("numerators" in d for p in checked.phases for d in p.discrepancies))
        changed_z = replace(expected, Z=4)
        checked = self.harness.verify_fixture(replace(
            fixture, expectations=(changed_z,) + fixture.expectations[1:]))
        self.assertEqual(checked.status, "FAIL")
        self.assertEqual(self.harness.canonical_bytes(self.manifest), before)
        self.assertEqual(self.harness.verify_fixture(fixture).status, "PASS")

    def test_k_public_provenance_and_overlap_preserve_owned_m_without_double_counting(self):
        for name in ("logical-fixed-mine", "physical-logical-overlap",
                     "local-physical-logical-overlap"):
            result = self.by_id[name]
            with self.subTest(fixture=name):
                self.assertTrue(result.fixture.public_prefix)
                self.assertTrue(result.fixture.provenance)
                self.assertTrue(result.prefix_decisions)
                self.assertEqual(result.prefix_decisions[-1].after.M,
                                 frozenset(result.fixture.pre_acquisition_M))
                self.assertEqual(result.final_M, frozenset({(1, 0)}))
                self.assertTrue(all(a.status == "PASS" for a in result.acquisition_audits))
        logical = self.by_id["logical-fixed-mine"].decision
        overlap = self.by_id["physical-logical-overlap"].decision
        self.assertEqual(overlap.after.P & overlap.after.M, frozenset({(1, 0)}))
        self.assertEqual(overlap.after.J, frozenset({(1, 0)}))
        self.assertEqual(overlap.after.b, 1)
        self.assertEqual(overlap.phase_d, logical.phase_d)



class ProgramKSlice7QualificationTests(unittest.TestCase):
    """Synthetic implementation readiness; never execute the E0 dispatcher."""

    @classmethod
    def setUpClass(cls):
        from experiments import program_k_harness as h
        cls.h = h
        cls.env = h.OperatingEnvelope(
            "synthetic-runtime", "synthetic-machine", "synthetic-python",
            10000, 30000, 120000, 1000, 1000, 1000000000, 100000000, 100,
            "UNIT_ONLY", "Explicit synthetic containment for unit verification.")
        public = h.collect_unit_readiness(run_id="slice7-unit", envelope=cls.env)
        cls.record = public

    def test_ready_except_execution_is_not_e0_pass(self):
        outcome = self.h.assess_qualification(self.record)
        self.assertEqual(outcome.verdict, "INCOMPLETE")
        self.assertEqual(outcome.readiness, "READY_EXCEPT_EXECUTION")
        self.assertFalse(outcome.progression_allowed)
        self.assertEqual(outcome.p8_gate.classification, "MISSING_P8")
        self.assertTrue(all(g.status == "PASS" for g in outcome.gates if g.gate_id != "P-8"))
        self.assertEqual(self.record.purpose, "IMPLEMENTATION_UNIT_READINESS")
        self.assertEqual(self.record.operational_receipts, ())

    def test_post_audit_fixed_p8_probe_is_bounded_and_cannot_release_p8_gate(self):
        h = self.h
        spec = next(p for p in h.PROBES if p.gate_id == "P-8-CHECKER")
        self.assertEqual(spec.test_classes, (
            "tests.test_program_k_harness.ProgramKSlice6P8CheckerTests",))
        actual = next(p for p in self.record.probe_results if p.gate_id == spec.gate_id)
        self.assertEqual(actual.status, "PASS")
        # The existing checker tests authenticate the public domain and cancel
        # before its first triple; private unit domains have at most 48 triples.
        self.assertTrue(any("public_checker" in name for name in actual.executed_tests))
        self.assertEqual(h.check_p8_gate(None).classification, "MISSING_P8")
        interrupted = public_oracles.check_frozen_p8(interrupt_requested=lambda: True)
        self.assertEqual(interrupted.visited_triple_count, 0)
        with patch.object(public_oracles.Path, "read_bytes", side_effect=OSError("unreadable source")):
            self.assertEqual(h.check_p8_gate(interrupted).classification, "IMPLEMENTATION_IDENTITY_FAIL")

    def test_post_audit_unbound_wrong_board_or_reordered_findings_never_qualify(self):
        h = self.h
        findings = self.record.evaluator_findings
        archive = next(a for a in self.record.execution_evidence.archives if a.variant == "K-CONTROL")
        sealed = h.seal_execution_archive(archive, run_id=self.record.run_id)
        bound = h._bound_archive_answer(archive, sealed)
        # Keep every asserted mine but add a wrong extra mine. A shadow-only
        # finding still says NO_COUNTEREXAMPLE, which is not board identity.
        extra = next((x,y) for y in range(bound.height) for x in range(bound.width)
                     if (x,y) not in bound.mines)
        wrong = evaluator.HiddenAnswer(bound.case_id, bound.run_id, bound.width, bound.height,
                                        bound.mines | {extra})
        finding = evaluator.evaluate_falsification(sealed, wrong)
        self.assertEqual(finding.classification, "NO_COUNTEREXAMPLE")
        altered = tuple(finding if f.sealed_input == sealed else f for f in findings)
        for supplied in (findings[:-1], findings + findings[:1], findings[::-1], altered):
            with self.subTest(count=len(supplied)):
                record = replace(self.record, evaluator_findings=supplied)
                self.assertNotEqual(h.assess_qualification(record).readiness, "READY_EXCEPT_EXECUTION")
                research_labeled = replace(record, purpose="E0_QUALIFICATION", unit_diagnostics=())
                self.assertNotEqual(h.assess_qualification(research_labeled).verdict, "E0_PASS")

    def test_post_audit_call_diagnostics_are_separate_complete_and_lossless(self):
        h = self.h
        self.assertEqual(tuple((d.kind, d.operation_id) for d in self.record.unit_diagnostics),
                         h._operation_catalog())
        self.assertEqual(h.verify_operation_diagnostics(self.record).status, "PASS")
        for diagnostic in self.record.unit_diagnostics:
            self.assertEqual(diagnostic.mode, "IMPLEMENTATION_UNIT")
            self.assertEqual(h.reconstruct(h.canonical_bytes(diagnostic)), diagnostic)
            for call in diagnostic.oracle_calls + diagnostic.evaluator_calls:
                self.assertIs(type(call.duration_ns), int)
                self.assertGreater(call.duration_ns, 0)
        extreme = next(d for d in self.record.unit_diagnostics
                       if d.kind == "FIXTURE" and d.operation_id == "arithmetic-extreme")
        skipped = tuple(c for c in extreme.oracle_calls if c.oracle == "A")
        self.assertTrue(skipped)
        self.assertTrue(all(c.status == "NOT_EVALUATED" and c.duration_ns > 0
                            and c.output_digest is None for c in skipped))
        no_calls = next(d for d in self.record.unit_diagnostics if d.operation_id == "P-8-CHECKER")
        self.assertEqual(no_calls.oracle_calls, ())
        self.assertIn("ORACLE_A_NOT_INVOKED", no_calls.not_invoked)
        posthoc = self.record.unit_diagnostics[-1]
        self.assertEqual(posthoc.oracle_calls, ())
        self.assertEqual(posthoc.evaluator_call_count, len(self.record.evaluator_findings))
        for call, result in zip(posthoc.evaluator_calls, self.record.evaluator_findings):
            self.assertEqual(call.sealed_input_digest, result.sealed_input.assertions_digest)
            self.assertEqual(call.evaluated_coordinate_count, result.evaluated_coordinate_count)
            self.assertEqual(call.classification, "NO_COUNTEREXAMPLE")
        self.assertEqual(self.record.manifest_digest, h.PINNED_MANIFEST_SHA256)
        for cls in (h.Fixture, h.FixtureExpectation, h.GuessCheckpoint, evidence_records.V1DecisionProjection):
            self.assertFalse(any("duration" in f.name or "diagnostic" in f.name for f in fields(cls)))

    def test_post_audit_diagnostic_omission_mutation_and_zero_duration_cannot_pass(self):
        h = self.h
        diagnostics = self.record.unit_diagnostics
        self.assertEqual(h.verify_operation_diagnostics(replace(self.record, unit_diagnostics=())).status,
                         "INCOMPLETE")
        for index in (0, next(i for i,d in enumerate(diagnostics)
                             if d.operation_id == "P-1/P-2/LOCAL/ACCOUNTING"),
                      len(diagnostics)-2, len(diagnostics)-1):
            old = diagnostics[index]
            empty = replace(old, oracle_calls=(), evaluator_calls=(),
                            oracle_a_call_count=0, oracle_b_call_count=0, evaluator_call_count=0,
                            not_invoked=("ORACLE_A_NOT_INVOKED", "ORACLE_B_NOT_INVOKED",
                                         "EVALUATOR_NOT_INVOKED"))
            record = replace(self.record, unit_diagnostics=diagnostics[:index]+(empty,)+diagnostics[index+1:])
            with self.subTest(operation=old.operation_id):
                self.assertEqual(h.verify_operation_diagnostics(record).status, "FAIL")
        first = diagnostics[0]
        for changed in (
                replace(first, result_digest="0"*64),
                replace(first, oracle_calls=tuple(replace(c, input_digest="0"*64)
                                                  for c in first.oracle_calls))):
            record = replace(self.record, unit_diagnostics=(changed,)+diagnostics[1:])
            self.assertEqual(h.verify_operation_diagnostics(record).status, "FAIL")
        with self.assertRaises(ValueError):
            replace(first, oracle_calls=(replace(first.oracle_calls[0], duration_ns=0),)
                    + first.oracle_calls[1:])
        with self.assertRaises(ValueError):
            replace(first, oracle_calls=first.oracle_calls[:-1])
        # Mutating sidecar durations has no effect on the retained semantic payload.
        before = h.canonical_bytes(self.record.fixture_results[0])
        replace(first, oracle_calls=tuple(replace(c, duration_ns=c.duration_ns+1) for c in first.oracle_calls))
        self.assertEqual(h.canonical_bytes(self.record.fixture_results[0]), before)

    def test_post_audit_primitive_calls_do_not_sum_parent_history_spans(self):
        observation = ((H, 1, H, H, H),)
        _, decision = public_decision(observation, 3)
        with public_oracles.collect_oracle_diagnostics() as calls:
            result = public_oracles.materialized_exact_reference(
                observation, 3, status=PLAYING, logical_mines=decision.after.M,
                proofs=decision.exact_certificates)
        # Two pre-acquisition public proofs each run A; B's exact kernel runs once.
        self.assertEqual(tuple(c.oracle for c in calls), ("A", "A", "B"))
        self.assertTrue(all(c.method in ("COMPLETE_WORLD_ENUMERATION", "MATERIALIZED_EXACT")
                            for c in calls))
        self.assertEqual(result.total_worlds, 2)
        self.assertFalse(hasattr(result, "duration_ns"))

    def test_required_envelope_and_all_limits_are_exact_positive(self):
        h = self.h
        with self.assertRaises(h.QualificationError):
            h.collect_unit_readiness(run_id="unit", envelope=None)
        with self.assertRaises(h.QualificationError):
            h.preflight_e0(envelope=None, source_identity=self.record.source_identity, p8=None)
        numeric = tuple(f.name for f in fields(self.env)
                        if type(getattr(self.env, f.name)) is int)
        for name in numeric:
            for invalid in (0, -1, True, 1.0, float("inf"), float("nan"), "10", None):
                with self.subTest(name=name, invalid=invalid), self.assertRaises(ValueError):
                    replace(self.env, **{name: invalid})
        for name in ("machine_identity", "runtime_identity", "python_identity",
                     "monitoring_policy", "rationale"):
            with self.assertRaises(ValueError):
                replace(self.env, **{name: " "})
        with self.assertRaises(FrozenInstanceError):
            self.env.max_case_wall_ms = 100

    def test_operational_system_abort_and_shadow_timeout_are_separate(self):
        h = self.h
        sample = h.ResourceSample(0, 0, 0, 0, 0, 0, 0)
        self.assertEqual(h.check_operating_limits(self.env, sample), "WITHIN_ENVELOPE")
        checks = (
            ("case_elapsed_ns", self.env.max_case_wall_ms*1000000, "SYSTEM_CASE_TIMEOUT"),
            ("job_elapsed_ns", self.env.max_job_wall_ms*1000000, "SYSTEM_JOB_TIMEOUT"),
            ("decision_elapsed_ns", self.env.max_decision_wall_ms*1000000, "SYSTEM_DECISION_TIMEOUT"),
            ("physical_inputs", self.env.max_physical_inputs_per_case+1, "SYSTEM_INPUT_CAP"),
            ("memory_bytes", self.env.memory_cap_bytes+1, "SYSTEM_MEMORY_CAP"),
            ("archive_bytes", self.env.archive_cap_bytes+1, "SYSTEM_ARCHIVE_CAP"),
            ("shadow_elapsed_ns", self.env.shadow_timeout_ms*1000000, "SHADOW_ONLY_TIMEOUT_P5"),
        )
        for name, value, expected in checks:
            with self.subTest(reason=expected):
                self.assertEqual(h.check_operating_limits(self.env, replace(sample, **{name:value})), expected)
        self.assertEqual(h.check_operating_limits(self.env, replace(sample,
            shadow_elapsed_ns=1000000000, case_elapsed_ns=30000000000)), "SYSTEM_CASE_TIMEOUT")

    def test_preflight_refuses_without_machine_identity_or_full_p8(self):
        p = self.h.preflight_e0(envelope=self.env, source_identity=self.record.source_identity, p8=None)
        self.assertEqual(p.status, "INCOMPLETE")
        self.assertIn("MISSING_P8", p.reasons)
        self.assertIn("MACHINE_RUNTIME_IDENTITY_NOT_PINNED", p.reasons)
        self.assertIn("ENFORCEABLE_MONITOR_UNAVAILABLE", p.reasons)

    def test_p8_missing_interrupted_private_never_satisfy_research_gate(self):
        h = self.h
        # Authenticates only, interrupted BEFORE the first triple. No full scan.
        interrupted = public_oracles.check_frozen_p8(interrupt_requested=lambda: True)
        self.assertEqual(interrupted.visited_triple_count, 0)
        self.assertEqual(interrupted.expected_triple_count, 110361600)
        private = public_oracles._check_p8_table(((7, 7), (7, 7)))
        self.assertEqual(private.status, "PASS")  # PRIVATE status, never research.
        private_bad = public_oracles._check_p8_table(((1,), (1,), (3,)))
        for result, classification in ((None, "MISSING_P8"), (interrupted, "INTERRUPTED_P8"),
                (private, "PRIVATE_CHECK_NOT_RESEARCH_EVIDENCE"),
                (private_bad, "PRIVATE_CHECK_NOT_RESEARCH_EVIDENCE")):
            with self.subTest(classification=classification):
                gate = h.check_p8_gate(result)
                self.assertEqual((gate.status, gate.classification), ("INCOMPLETE", classification))
                assessment = h.assess_qualification(replace(self.record, p8_reference=result))
                self.assertEqual(assessment.verdict, "INCOMPLETE")
                self.assertFalse(assessment.progression_allowed)
        with patch.object(public_oracles, "check_frozen_p8", side_effect=AssertionError("no scan")):
            self.assertEqual(h.check_p8_gate(interrupted).status, "INCOMPLETE")
        corrupt = deepcopy(interrupted)
        object.__setattr__(corrupt, "checker_source_sha256", "0"*64)
        self.assertEqual(h.check_p8_gate(corrupt).classification, "IMPLEMENTATION_IDENTITY_FAIL")
        self.assertEqual(h.check_p8_gate(object()).status, "FAIL")

    def test_external_flag_checked_before_k_local_certificate_without_entering_m(self):
        h = self.h
        prefix = ((1, H, H, H, H),)
        v1 = plan_position(prefix, 2, (0, 0), load_timing_table())
        flag = evidence_records.make_v1_flag_provenance(prefix, v1, num_mines=2, boundary=1)
        observation = ((1, F, 2, H, H),)
        inputs = runner._shadow_input(observation, 5, 1, 2, (1, 0),
                                       frozenset(), frozenset({(1, 0)}))
        decision = runner._analyze_shadow(inputs)
        certificate = decision.local.certificates[0]
        audit = h.audit_acquisition(certificate, boundary=3, external_flags=(flag,))
        self.assertEqual(audit.status, "PASS")
        self.assertEqual(audit.external_flags[0].verification.status, "PASS")
        self.assertIs(audit.external_flags[0].record, flag)
        self.assertEqual(audit.certificate, certificate)
        self.assertEqual(audit.owned_M_before, frozenset())
        self.assertEqual(audit.owned_M_after, frozenset({(3, 0)}))
        self.assertNotIn((1, 0), decision.after.M)
        self.assertFalse(flag.enters_M)
        self.assertEqual(h.audit_acquisition(certificate, boundary=3).status, "INCOMPLETE")
        self.assertEqual(h.audit_acquisition(certificate, boundary=3, external_flags=(object(),)).status, "FAIL")
        self.assertEqual(h.audit_acquisition(certificate, boundary=1, external_flags=(flag,)).status, "FAIL")

    def test_unbounded_external_exact_flag_is_not_evaluated(self):
        h = self.h
        observation = ((H, 1, H) + (H,)*15,)
        v1 = plan_position(observation, 16, (0, 0), load_timing_table())
        flag = evidence_records.make_v1_flag_provenance(observation, v1, num_mines=16, boundary=1)
        row = list(observation[0])
        row[flag.move.x] = F
        certificate = public_oracles.LocalMineCertificate(
            (tuple(row),), 16, (1, 0), (0, 0), frozenset(), PLAYING)
        audit = h.audit_acquisition(certificate, boundary=2, external_flags=(flag,))
        self.assertEqual(audit.status, "NOT_EVALUATED")
        self.assertIsNone(audit.certificate_check)
        self.assertEqual(audit.external_flags[0].public_support, ())

    def test_all_mandatory_fields_reconstruct_losslessly(self):
        h = self.h
        data = h.canonical_bytes(self.record)
        restored = h.reconstruct(data, expected_digest=h.content_digest(self.record))
        self.assertEqual(data, h.canonical_bytes(restored))
        self.assertEqual(restored, self.record)
        self.assertEqual(len(restored.fixture_results), 30)
        self.assertEqual(len(restored.probe_results), len(h.PROBES))
        self.assertEqual(len(restored.execution_evidence.archives), 6)
        self.assertEqual(len(restored.execution_evidence.guess_comparisons), 1)
        self.assertEqual(restored.execution_evidence.guess_comparisons[0].status, "PASS")
        self.assertTrue(restored.execution_evidence.o4_comparisons)
        self.assertTrue(restored.execution_evidence.acquisition_audits)
        self.assertTrue(restored.execution_evidence.timing_coverage)
        self.assertTrue(restored.evaluator_findings)
        self.assertIsNone(restored.p8_reference)
        self.assertEqual(h.assess_qualification(restored).verdict, "INCOMPLETE")
        with self.assertRaises(FrozenInstanceError):
            restored.fixture_results = ()

    def test_missing_mandatory_evidence_never_passes(self):
        h = self.h
        samples = (
            replace(self.record, fixture_results=self.record.fixture_results[:-1]),
            replace(self.record, probe_results=self.record.probe_results[:-1]),
            replace(self.record, evaluator_findings=()),
            replace(self.record, interruptions=("SYSTEM_CASE_TIMEOUT: incomplete physical stream",)),
            replace(self.record, fixture_results=(replace(self.record.fixture_results[0], phases=()),)
                    + self.record.fixture_results[1:]),
            replace(self.record, probe_results=(replace(self.record.probe_results[0],
                executed_tests=self.record.probe_results[0].executed_tests[:-1]),)+self.record.probe_results[1:]),
        )
        for record in samples:
            with self.subTest(kind=h.content_digest(record)):
                outcome = h.assess_qualification(record)
                self.assertFalse(outcome.progression_allowed)
                self.assertNotEqual(outcome.readiness, "READY_EXCEPT_EXECUTION")

    def test_corrupt_literal_source_receipt_and_same_id_fixture_are_detected(self):
        h = self.h
        first = self.record.fixture_results[0]
        altered_fixture = replace(first.fixture, rationale="Unregistered same-ID substitute")
        altered_result = h.verify_fixture(altered_fixture)
        samples = (
            replace(self.record, fixture_results=(altered_result,)+self.record.fixture_results[1:]),
            replace(self.record, manifest_digest="0"*64),
            replace(self.record, probe_results=(replace(self.record.probe_results[0],
                source_digest="0"*64),)+self.record.probe_results[1:]),
            replace(self.record, diagnosed_implementation_defects=("Diagnosed corrupted evidence",)),
        )
        for record in samples:
            self.assertEqual(h.assess_qualification(record).verdict, "IMPLEMENTATION_IDENTITY_FAIL")

    def test_execution_evidence_omission_and_relabeling_are_detected(self):
        h = self.h
        original = self.record.execution_evidence.archives
        treatments = [i for i,a in enumerate(original) if a.variant == "K-P0"]
        controls = [i for i,a in enumerate(original) if a.variant == "K-CONTROL"]
        def changed_archive(index, mapper):
            a = original[index]
            changed = replace(a, result=replace(a.result, traces=tuple(mapper(t) for t in a.result.traces)))
            return original[:index]+(changed,)+original[index+1:]
        for index in controls:
            archives = changed_archive(index, lambda t: replace(t, shadow=replace(t.shadow, decision=None)))
            self.assertNotEqual(h.verify_execution_archives(archives).status, "PASS")
        for index in treatments:
            def strip(t):
                if t.selection is None:
                    return t
                d = t.selection.evidence
                d = replace(d, local=replace(d.local, certificates=()), exact_certificates=())
                return replace(t, selection=replace(t.selection, evidence=d))
            self.assertNotEqual(h.verify_execution_archives(changed_archive(index, strip)).status, "PASS")
            if any(t.input_index and t.category != "EXACT_MINIMUM_RISK_GUESS"
                   for t in original[index].result.traces):
                self.assertNotEqual(h.verify_execution_archives(changed_archive(index,
                    lambda t: replace(t, category="EXACT_MINIMUM_RISK_GUESS") if t.input_index else t)).status, "PASS")
        flagged = next(i for i in controls if any(t.external_flag for t in original[i].result.traces))
        self.assertNotEqual(h.verify_execution_archives(changed_archive(flagged,
            lambda t: replace(t, external_flag=None))).status, "PASS")
        self.assertNotEqual(h.verify_execution_archives(original[:-1]).status, "PASS")

    def test_wrong_board_finding_is_implementation_failure_not_bound_falsification(self):
        h = self.h
        original = next(f for f in self.record.evaluator_findings if f.sealed_input.case_id.endswith(":K-P0"))
        sealed = original.sealed_input
        false_answer = evaluator.HiddenAnswer(sealed.case_id, sealed.run_id, 4, 1,
                                               frozenset({(3, 0)}))
        finding = evaluator.evaluate_falsification(sealed, false_answer)
        self.assertEqual(finding.classification, "G1_FALSIFICATION")
        altered = replace(self.record, evaluator_findings=tuple(
            finding if f is original else f for f in self.record.evaluator_findings))
        result = h.assess_qualification(altered)
        self.assertEqual(result.verdict, "IMPLEMENTATION_IDENTITY_FAIL")
        self.assertEqual(next(g.status for g in result.gates if g.gate_id == "EVALUATOR-BOARD-BINDING"), "FAIL")
        self.assertFalse(result.progression_allowed)
        self.assertEqual(altered.fixture_results, self.record.fixture_results)
        self.assertEqual(altered.execution_evidence, self.record.execution_evidence)

    def test_canonical_digest_strict_order_exact_ints_and_truth_exclusion(self):
        h = self.h
        value = (frozenset({(3, 0), (0, 1), (1, 0)}), Fraction(9, 20), 88004802264174740)
        self.assertEqual(h.canonical_bytes(value), h.canonical_bytes(
            (frozenset({(0, 1), (1, 0), (3, 0)}), Fraction(9, 20), 88004802264174740)))
        self.assertNotEqual(h.canonical_bytes(((1,0),(3,0))), h.canonical_bytes(((3,0),(1,0))))
        self.assertEqual(h.reconstruct(h.canonical_bytes(value)), value)
        with self.assertRaises(ValueError):
            h.reconstruct(h.canonical_bytes(value), expected_digest="0"*64)
        with self.assertRaises(ValueError):
            h.reconstruct(b'{"x":1,"x":2}')
        with self.assertRaises(ValueError):
            h.canonical_bytes(1.0)
        with self.assertRaises(ValueError):
            h.canonical_bytes(evaluator.HiddenAnswer("case", "run", 2, 1, frozenset({(1,0)})))

    def test_artifact_complete_write_no_overwrite_and_corruption_detection(self):
        from tempfile import TemporaryDirectory
        h = self.h
        with TemporaryDirectory() as tmp:
            receipt = h.persist_qualification(self.record, repository_root=tmp)
            folder = Path(tmp)/"results"/"program_k_research"/self.record.run_id
            restored, recovered, assessment = h.read_qualification_artifact(folder)
            self.assertEqual(h.canonical_bytes(restored), h.canonical_bytes(self.record))
            self.assertEqual(receipt, recovered)
            self.assertEqual(receipt.completion_marker, "COMPLETE")
            self.assertEqual(assessment.verdict, "INCOMPLETE")
            with self.assertRaises(FileExistsError):
                h.persist_qualification(self.record, repository_root=tmp)
            data = (folder/"qualification.json").read_bytes()
            (folder/"qualification.json").write_bytes(data+b" ")
            with self.assertRaises(ValueError):
                h.read_qualification_artifact(folder)
        with TemporaryDirectory() as tmp:
            small = replace(self.record, operating_envelope=replace(self.env, archive_cap_bytes=1))
            with self.assertRaises(ValueError):
                h.persist_qualification(small, repository_root=tmp)
            self.assertFalse((Path(tmp)/"results").exists())



    def test_p3_retained_comparator_and_registered_probe_are_mandatory(self):
        h = self.h
        self.assertIn("P-3", tuple(p.gate_id for p in h.PROBES))
        comparison = self.record.execution_evidence.guess_comparisons[0]
        self.assertEqual(comparison.status, "PASS")
        for evidence in ((), ("malformed",), (replace(comparison, control=None),)):
            with self.subTest(evidence=type(evidence[0]).__name__ if evidence else "absent"):
                execution = replace(self.record.execution_evidence, guess_comparisons=evidence)
                self.assertEqual(h.verify_retained_guess_comparisons(execution).status, "INCOMPLETE")
                outcome = h.assess_qualification(replace(self.record, execution_evidence=execution))
                self.assertFalse(outcome.progression_allowed)
                self.assertNotEqual(outcome.readiness, "READY_EXCEPT_EXECUTION")
        altered = replace(comparison, status="FAIL", differences=("fabricated divergence",))
        execution = replace(self.record.execution_evidence, guess_comparisons=(altered,))
        self.assertEqual(h.verify_retained_guess_comparisons(execution).status, "FAIL")
        record = replace(self.record, probe_results=tuple(
            p for p in self.record.probe_results if p.gate_id != "P-3"))
        self.assertFalse(h.assess_qualification(record).progression_allowed)


    def test_missing_physical_effect_is_incomplete_and_cannot_seal(self):
        h = self.h
        def omit(archive):
            if archive.variant != "K-P0":
                return archive
            result = archive.result
            traces = (replace(result.traces[0], public_effect=None),) + result.traces[1:]
            return replace(archive, result=replace(result, traces=traces))
        probes = tuple(replace(p, execution_archives=tuple(omit(a) for a in p.execution_archives))
                       for p in self.record.probe_results)
        execution = h.verify_execution_archives(tuple(a for p in probes for a in p.execution_archives))
        self.assertEqual(execution.status, "INCOMPLETE")
        altered = replace(self.record, probe_results=probes, execution_evidence=execution)
        assessment = h.assess_qualification(altered)
        self.assertIn(assessment.verdict, ("INCOMPLETE", "IMPLEMENTATION_IDENTITY_FAIL"))
        self.assertNotEqual(assessment.readiness, "READY_EXCEPT_EXECUTION")

    def test_research_receipt_assessment_never_dispatches_unmonitored_solver_replay(self):
        # A synthetic malformed research-labeled RECORD, not execution of E0.
        # No authorization, machine identity, operating receipts or P-8 exists.
        h = self.h
        record = replace(self.record, purpose="E0_QUALIFICATION", unit_diagnostics=())
        with patch.object(h, "verify_fixture", side_effect=AssertionError("unmonitored solver")), \
             patch.object(h, "verify_execution_archives", side_effect=AssertionError("unmonitored audit")):
            assessment = h.assess_qualification(record)
        self.assertEqual(assessment.verdict, "INCOMPLETE")
        self.assertFalse(assessment.progression_allowed)
        operating = next(g for g in assessment.gates if g.gate_id == "OPERATING-EXECUTION")
        self.assertEqual(operating.status, "INCOMPLETE")


    def test_failed_and_incomplete_attempts_are_preserved(self):
        from tempfile import TemporaryDirectory
        h = self.h
        failed = replace(self.record, run_id="unit-failed",
                         diagnosed_implementation_defects=("Synthetic diagnosed implementation fault",))
        with TemporaryDirectory() as tmp:
            receipt = h.persist_qualification(failed, repository_root=tmp)
            self.assertEqual(receipt.verdict, "IMPLEMENTATION_IDENTITY_FAIL")
            restored, _, _ = h.read_qualification_artifact(
                Path(tmp)/"results"/"program_k_research"/failed.run_id)
            self.assertEqual(restored.diagnosed_implementation_defects,
                             failed.diagnosed_implementation_defects)


class ProgramKSlice7SupervisorTests(unittest.TestCase):
    """Private fixed-operation unit verification; never dispatch actual E0."""

    @classmethod
    def setUpClass(cls):
        from experiments import program_k_harness as h
        cls.h = h
        cls.env = h.OperatingEnvelope(
            "synthetic-worker-runtime", "synthetic-worker-machine", "synthetic-worker-python",
            10000, 30000, 120000, 1000, 1000, 1000000000, 100000000, 10,
            h.OPERATIONAL_MONITOR_ID, "Explicit single-operation unit containment only.")

    def supervise(self, kind, identity, envelope=None):
        import time
        h = self.h
        return h._supervise_operation(kind, identity, envelope or self.env,
            h.capture_source_identity(), job_started_ns=time.monotonic_ns(), archive_used_bytes=0)

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object containment")
    def test_private_single_fixture_worker_completion_and_reconstruction(self):
        h = self.h
        receipt, result, received = self.supervise("FIXTURE", "no-new-m")
        self.assertEqual(receipt.status, "COMPLETE", receipt.reason)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(receipt.result_digest, h.content_digest(result))
        self.assertGreater(received, receipt.result_size_bytes)
        self.assertEqual(receipt.physical_inputs, 0)
        self.assertIn("DECISION_START", tuple(e.event for e in receipt.events))
        self.assertEqual(h.reconstruct(h.canonical_bytes(receipt)), receipt)
        self.assertFalse(hasattr(receipt, "research_pass"))
        memory = receipt.memory_evidence
        self.assertGreater(memory.peak_worker_tree_bytes, 0)
        self.assertGreaterEqual(memory.peak_combined_bytes, memory.peak_worker_tree_bytes)
        self.assertGreater(memory.sample_count, 0)
        self.assertLessEqual(memory.peak_combined_bytes, self.env.memory_cap_bytes)
        self.assertEqual(memory.measurement, h.MEMORY_MEASUREMENT)
        self.assertIn("not machine-wide", memory.measurement)
        self.assertEqual(receipt.diagnostics.result_digest, receipt.result_digest)
        self.assertEqual(receipt.diagnostics_digest, h.content_digest(receipt.diagnostics))
        # This is an isolated one-operation gate test, never an E0 record.
        unit = SimpleNamespace(
            run_id="unit-receipt", purpose="E0_QUALIFICATION", unit_diagnostics=(),
            operating_envelope=self.env, source_identity=h.capture_source_identity(),
            fixture_results=(result,), probe_results=(),
            execution_evidence=h.ExecutionVerification((), (), (), (), (), (), ("unit-only",)),
            evaluator_findings=(), operational_receipts=(receipt,))
        with patch.object(h, "_operation_catalog", return_value=(("FIXTURE", "no-new-m"),)):
            self.assertEqual(h.verify_operational_receipts(unit).status, "PASS")
            self.assertEqual(h.verify_operation_diagnostics(unit).status, "PASS")
            unit.operational_receipts = (replace(receipt, memory_evidence=None),)
            self.assertEqual(h.verify_operational_receipts(unit).status, "INCOMPLETE")
            excessive = replace(memory, peak_combined_bytes=self.env.memory_cap_bytes+1)
            unit.operational_receipts = (replace(receipt, memory_evidence=excessive),)
            self.assertEqual(h.verify_operational_receipts(unit).status, "FAIL")
            unit.operational_receipts = (replace(receipt, diagnostics=None, diagnostics_digest=None),)
            self.assertEqual(h.verify_operation_diagnostics(unit).status, "INCOMPLETE")
            with self.assertRaises(ValueError):
                replace(receipt, diagnostics_digest="0"*64)
        for changes in ({"peak_worker_tree_bytes": 0}, {"sample_count": 0},
                        {"peak_combined_bytes": True}, {"measurement": "machine-wide"}):
            with self.assertRaises(ValueError):
                replace(memory, **changes)
        self.assertEqual(h.check_p8_gate(None).status, "INCOMPLETE")

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object containment")
    def test_private_post_hoc_evaluator_worker_has_no_solver_admissions(self):
        import time
        h = self.h
        result = runner.run_k_p0(fixed_engine(), table=load_timing_table(), capture_effects=True)
        archive = h.ExecutionArchive(h._TREATMENT_ARCHIVE_CASE, "K-P0", result)
        sealed_before = h.canonical_bytes(archive)
        receipt, evaluated, _ = h._supervise_operation(
            "EVALUATOR", "POST_HOC_EXECUTION_ARCHIVES", self.env, h.capture_source_identity(),
            job_started_ns=time.monotonic_ns(), archive_used_bytes=0,
            archives=(archive,), evaluator_run_id="unit-post-hoc")
        self.assertEqual(receipt.status, "COMPLETE", receipt.reason)
        self.assertEqual(tuple(e.event for e in receipt.events), ("STARTED", "FINISHED"))
        self.assertEqual(receipt.physical_inputs, 0)
        self.assertEqual(receipt.diagnostics.oracle_calls, ())
        self.assertEqual(receipt.diagnostics.evaluator_call_count, 1)
        self.assertGreater(receipt.diagnostics.evaluator_calls[0].duration_ns, 0)
        self.assertEqual(evaluated.findings[0].classification, "NO_COUNTEREXAMPLE")
        self.assertEqual(h.canonical_bytes(archive), sealed_before)
        self.assertIsNone(h.check_p8_gate(None).evidence_digest)

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object containment")
    def test_private_tiny_case_deadline_aborts_without_fallback(self):
        env = replace(self.env, max_decision_wall_ms=1, max_case_wall_ms=1,
                      shadow_timeout_ms=1, monitor_interval_ms=1)
        receipt, result, _ = self.supervise("FIXTURE", "no-new-m", env)
        self.assertEqual(receipt.status, "INCOMPLETE")
        self.assertEqual(receipt.reason, "SYSTEM_CASE_TIMEOUT")
        self.assertIsNone(result)
        self.assertEqual(receipt.physical_inputs, 0)

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object containment")
    def test_private_probe_input_cap_stops_before_second_admission(self):
        receipt, result, _ = self.supervise("PROBE", "A-E1/A-E2",
            replace(self.env, max_physical_inputs_per_case=1))
        self.assertEqual(receipt.status, "INCOMPLETE", receipt.reason)
        self.assertEqual(receipt.reason, "SYSTEM_INPUT_CAP")
        self.assertEqual(receipt.physical_inputs, 1)
        self.assertEqual(sum(e.event == "BEFORE_INPUT" for e in receipt.events), 1)
        self.assertIsNone(result)

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object containment")
    def test_private_timing_probe_preserves_boundary_monitor(self):
        receipt, result, _ = self.supervise("PROBE", "A-E3")
        self.assertEqual(receipt.status, "COMPLETE", receipt.reason)
        self.assertEqual(result.status, "PASS", result.failures)
        self.assertGreater(receipt.physical_inputs, 0)
        events = tuple(e.event for e in receipt.events)
        self.assertEqual(events.count("DECISION_START"), events.count("DECISION_END"))
        self.assertGreater(events.count("DECISION_START"), 0)

    def test_receipt_rejects_missing_completion_and_corrupt_nested_counters(self):
        h = self.h
        start = h.OperationalEvent(0, "STARTED", 0, 0)
        end = h.OperationalEvent(1, "FINISHED", 1, 0)
        receipt = h.OperationReceipt("FIXTURE", "no-new-m", "a"*64, "b"*64,
            "COMPLETE", None, (start, end), 2, 0, "c"*64, 1, 0)
        for changes in ({"exit_code": 1}, {"result_digest": None},
                        {"events": (start,)}, {"physical_inputs": 1},
                        {"operation_id": "unregistered"}, {"elapsed_ns": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(receipt, **changes)
        corrupted = deepcopy(start)
        object.__setattr__(corrupted, "elapsed_ns", False)
        with self.assertRaises(ValueError):
            replace(receipt, events=(corrupted, end))


class ProgramKSlice7ReadinessMappingTests(unittest.TestCase):
    """Pure result-label tests; no P-8 result or research qualification exists."""

    def mapping(self, verdict, purpose="IMPLEMENTATION_UNIT_READINESS", complete=True):
        from experiments.program_k_harness import _readiness_for_verdict
        return _readiness_for_verdict(verdict, purpose=purpose, nonexecution_complete=complete)

    def test_ready_except_execution_requires_clean_nonexecution_incomplete(self):
        self.assertEqual(self.mapping("INCOMPLETE"), "READY_EXCEPT_EXECUTION")
        self.assertEqual(self.mapping("INCOMPLETE", complete=False), "NEEDS_CORRECTION")
        for complete in (False, True):
            with self.subTest(complete=complete):
                self.assertEqual(self.mapping("INCOMPLETE", "E0_QUALIFICATION", complete),
                                 "NEEDS_CORRECTION")

    def test_fail_verdicts_never_receive_a_ready_label(self):
        for verdict in ("IMPLEMENTATION_IDENTITY_FAIL", "PROGRAM_K_RESEARCH_FAIL"):
            for purpose in ("IMPLEMENTATION_UNIT_READINESS", "E0_QUALIFICATION"):
                for complete in (False, True):
                    with self.subTest(verdict=verdict, purpose=purpose, complete=complete):
                        self.assertEqual(self.mapping(verdict, purpose, complete), "NEEDS_CORRECTION")

    def test_e0_verdict_label_is_distinct_without_constructing_pass_evidence(self):
        # This exercises string mapping only. No E0 result, P8Result, Engine,
        # authorization, dispatcher or qualification evidence is constructed.
        self.assertEqual(self.mapping("E0_PASS", "E0_QUALIFICATION"), "E0_QUALIFIED")
        self.assertNotEqual(self.mapping("E0_PASS", "E0_QUALIFICATION"), "READY_EXCEPT_EXECUTION")

    def test_unknown_verdict_or_malformed_context_fails_closed(self):
        for verdict in ("PASS", "READY_EXCEPT_EXECUTION", None):
            with self.subTest(verdict=verdict), self.assertRaises(ValueError):
                self.mapping(verdict)
        with self.assertRaises(ValueError):
            self.mapping("INCOMPLETE", "E1")
        for complete in (0, 1, None, "True"):
            with self.subTest(complete=complete), self.assertRaises(ValueError):
                self.mapping("INCOMPLETE", complete=complete)


class ProgramKSlice7GuessCheckpointTests(unittest.TestCase):
    """P-3 archive projection/comparison only; no research qualification run."""

    @classmethod
    def setUpClass(cls):
        from experiments import program_k_harness as h
        cls.h = h
        cls.table = load_timing_table()
        cls.case_id = (__name__ + ".ProgramKSlice7GuessCheckpointTests.test_fixed_guess_pair")
        cls.control_archive, cls.kp0_archive = cls.capture_pair()
        cls.control = h.extract_guess_checkpoints(cls.control_archive, num_mines=2)
        cls.kp0 = h.extract_guess_checkpoints(cls.kp0_archive, num_mines=2)

    @classmethod
    def capture_pair(cls):
        # A declared tiny unit layout. CONTROL materializes the mine at (1,0)
        # before its guess; K retains that public fact in M and guesses earlier.
        layout = frozenset({(1, 0), (2, 0)})
        control = runner.run_control_capture(fixed_engine(5, 1, layout), table=cls.table)
        kp0 = runner.run_k_p0(fixed_engine(5, 1, layout), table=cls.table,
                             capture_effects=True)
        return (cls.h.ExecutionArchive(cls.case_id, "CONTROL", control),
                cls.h.ExecutionArchive(cls.case_id, "K-P0", kp0))

    def test_fixed_guess_pair(self):
        # Keep both actual captures in this exact test method: the fixed probe
        # recorder archives these returned public streams for the P-3 gate.
        control_archive, kp0_archive = self.capture_pair()
        h = self.h
        control = h.extract_guess_checkpoints(control_archive, num_mines=2)
        kp0 = h.extract_guess_checkpoints(kp0_archive, num_mines=2)
        self.assertEqual((control.status, kp0.status), ("COMPLETE", "COMPLETE"))
        self.assertEqual(len(control.checkpoints), 1)
        self.assertEqual(control.checkpoints, kp0.checkpoints)
        expected = control.checkpoints[0]
        self.assertEqual(expected.guess_ordinal, 1)
        self.assertEqual(expected.revealed_clues, (((0, 0), 1),))
        self.assertEqual(expected.fixed_mines, frozenset({(1, 0)}))
        self.assertEqual(expected.unresolved, frozenset({(2, 0), (3, 0), (4, 0)}))
        self.assertEqual(expected.remaining_mines, 1)
        self.assertEqual(expected.total_worlds, 3)
        self.assertEqual(expected.mine_worlds, (((2, 0), 1), ((3, 0), 1), ((4, 0), 1)))
        self.assertEqual(expected.probabilities, tuple(
            ((x, 0), Fraction(1, 3)) for x in (2, 3, 4)))
        self.assertEqual(expected.minimum_risk, Fraction(1, 3))
        self.assertEqual(expected.minimum_risk_cells, expected.unresolved)
        self.assertEqual(expected.target, (2, 0))
        self.assertIs(expected.terminal_outcome, GameStatus.LOST)
        control_index = next(i for i, t in enumerate(control_archive.result.traces)
            if t.decision is not None and t.decision.evidence.kind is DecisionKind.PROBABILITY_GUESS)
        kp0_index = next(t.input_index for t in kp0_archive.result.traces
                        if t.category == "EXACT_MINIMUM_RISK_GUESS")
        self.assertEqual((control_index, kp0_index), (2, 1))
        self.assertNotEqual(control_archive.result.effects[control_index].before_observation,
                            kp0_archive.result.traces[kp0_index].public_effect.before_observation)
        comparison = h.compare_guess_checkpoints(control, kp0)
        self.assertEqual(comparison.status, "PASS", comparison.differences)
        self.assertFalse(hasattr(expected, "action_index"))

    def test_initial_and_certainty_opens_are_excluded(self):
        h = self.h
        control = runner.run_control_capture(fixed_engine(), table=self.table)
        kp0 = runner.run_k_p0(fixed_engine(), table=self.table, capture_effects=True)
        audits = tuple(h.extract_guess_checkpoints(h.ExecutionArchive("certainty-only-unit", variant, run),
                                                   num_mines=1)
                       for variant, run in (("CONTROL", control), ("K-P0", kp0)))
        self.assertGreater(sum(t.move.action is Action.OPEN for t in kp0.traces), 1)
        for audit in audits:
            self.assertEqual(audit.status, "COMPLETE", audit.incomplete)
            self.assertEqual(audit.checkpoints, ())
        self.assertEqual(h.compare_guess_checkpoints(*audits).status, "PASS")

    def _different(self, changes, field):
        checkpoint = replace(self.kp0.checkpoints[0], **changes)
        audit = replace(self.kp0, checkpoints=(checkpoint,),
                        num_mines=checkpoint.remaining_mines + len(checkpoint.fixed_mines))
        comparison = self.h.compare_guess_checkpoints(self.control, audit)
        self.assertEqual(comparison.status, "FAIL", (field, comparison.differences))
        self.assertTrue(any(field in text for text in comparison.differences),
                        (field, comparison.differences))

    def test_every_required_semantic_field_detects_divergence(self):
        cells = ((2, 0), (3, 0), (4, 0))
        # Coupled exact fields remain internally coherent. Their disagreement
        # is a P-3 divergence, not malformed evidence accepted as a comparison.
        cases = (
            ("revealed_clues", {"revealed_clues": (((0, 0), 2),)}),
            ("fixed_mines", {"fixed_mines": frozenset({(1, 1)})}),
            ("unresolved", {"unresolved": frozenset({(2, 0), (3, 0), (5, 0)}),
                "mine_worlds": (((2, 0), 1), ((3, 0), 1), ((5, 0), 1)),
                "probabilities": tuple((c, Fraction(1, 3)) for c in ((2, 0), (3, 0), (5, 0))),
                "minimum_risk_cells": frozenset({(2, 0), (3, 0), (5, 0)})}),
            ("remaining_mines", {"remaining_mines": 2,
                "mine_worlds": tuple((c, 2) for c in cells),
                "probabilities": tuple((c, Fraction(2, 3)) for c in cells),
                "minimum_risk": Fraction(2, 3)}),
            ("total_worlds", {"total_worlds": 6, "mine_worlds": tuple((c, 2) for c in cells)}),
            ("mine_worlds", {"total_worlds": 4,
                "mine_worlds": (((2, 0), 1), ((3, 0), 1), ((4, 0), 2)),
                "probabilities": (((2, 0), Fraction(1, 4)), ((3, 0), Fraction(1, 4)), ((4, 0), Fraction(1, 2))),
                "minimum_risk": Fraction(1, 4), "minimum_risk_cells": frozenset({(2, 0), (3, 0)})}),
            ("probabilities", {"total_worlds": 4,
                "mine_worlds": (((2, 0), 1), ((3, 0), 1), ((4, 0), 2)),
                "probabilities": (((2, 0), Fraction(1, 4)), ((3, 0), Fraction(1, 4)), ((4, 0), Fraction(1, 2))),
                "minimum_risk": Fraction(1, 4), "minimum_risk_cells": frozenset({(2, 0), (3, 0)})}),
            ("minimum_risk", {"remaining_mines": 2,
                "mine_worlds": tuple((c, 2) for c in cells),
                "probabilities": tuple((c, Fraction(2, 3)) for c in cells),
                "minimum_risk": Fraction(2, 3)}),
            ("minimum_risk_cells", {"total_worlds": 5,
                "mine_worlds": (((2, 0), 2), ((3, 0), 2), ((4, 0), 1)),
                "probabilities": (((2, 0), Fraction(2, 5)), ((3, 0), Fraction(2, 5)), ((4, 0), Fraction(1, 5))),
                "minimum_risk": Fraction(1, 5), "minimum_risk_cells": frozenset({(4, 0)}), "target": (4, 0)}),
            ("target", {"total_worlds": 5,
                "mine_worlds": (((2, 0), 2), ((3, 0), 2), ((4, 0), 1)),
                "probabilities": (((2, 0), Fraction(2, 5)), ((3, 0), Fraction(2, 5)), ((4, 0), Fraction(1, 5))),
                "minimum_risk": Fraction(1, 5), "minimum_risk_cells": frozenset({(4, 0)}), "target": (4, 0)}),
            ("terminal_outcome", {"terminal_outcome": GameStatus.WON}),
        )
        for field, changes in cases:
            with self.subTest(field=field):
                self._different(changes, field)

    def test_ordinal_fault_is_detected_and_not_replaced_by_action_index(self):
        checkpoint = deepcopy(self.kp0.checkpoints[0])
        object.__setattr__(checkpoint, "guess_ordinal", 2)
        audit = deepcopy(self.kp0)
        object.__setattr__(audit, "checkpoints", (checkpoint,))
        self.assertIn(self.h.compare_guess_checkpoints(self.control, audit).status,
                      ("FAIL", "INCOMPLETE"))

    def test_missing_or_extra_actual_guess_is_divergence(self):
        for checkpoints in ((), (self.kp0.checkpoints[0],
                                  replace(self.kp0.checkpoints[0], guess_ordinal=2))):
            with self.subTest(count=len(checkpoints)):
                audit = replace(self.kp0, checkpoints=checkpoints)
                self.assertEqual(audit.status, "COMPLETE")
                self.assertEqual(self.h.compare_guess_checkpoints(self.control, audit).status, "FAIL")

    def test_missing_or_malformed_checkpoint_evidence_is_incomplete(self):
        h = self.h
        for value in (None, object(), self.kp0_archive, self.kp0.checkpoints[0]):
            with self.subTest(value=type(value).__name__):
                self.assertEqual(h.compare_guess_checkpoints(self.control, value).status, "INCOMPLETE")
        self.assertEqual(h.compare_guess_checkpoints(self.control,
            replace(self.kp0, incomplete=("Missing exact count evidence.",))).status, "INCOMPLETE")
        for field, value in (("mine_worlds", (((2, 0), 1),)),
                             ("probabilities", (((2, 0), Fraction(1, 3)),)),
                             ("total_worlds", True), ("minimum_risk", 1/3),
                             ("minimum_risk_cells", frozenset({(2, 0)})),
                             ("target", (3, 0)), ("terminal_outcome", GameStatus.PLAYING)):
            with self.subTest(field=field):
                checkpoint = deepcopy(self.kp0.checkpoints[0])
                object.__setattr__(checkpoint, field, value)
                audit = deepcopy(self.kp0)
                object.__setattr__(audit, "checkpoints", (checkpoint,))
                self.assertEqual(h.compare_guess_checkpoints(self.control, audit).status, "INCOMPLETE")

    def test_missing_public_effect_or_exact_evidence_does_not_hide_actual_guess(self):
        h = self.h
        trace = self.kp0_archive.result.traces[-1]
        without_effect = replace(trace, public_effect=None)
        without_selection = replace(trace, selection=None)
        without_exact = replace(trace, selection=replace(trace.selection,
            evidence=replace(trace.selection.evidence, phase_e=None)))
        for bad in (without_effect, without_selection, without_exact):
            with self.subTest(fault=repr(bad)[:100]):
                result = replace(self.kp0_archive.result,
                                 traces=self.kp0_archive.result.traces[:-1] + (bad,))
                audit = h.extract_guess_checkpoints(replace(self.kp0_archive, result=result), num_mines=2)
                self.assertEqual(audit.status, "INCOMPLETE", audit)
                self.assertEqual(h.compare_guess_checkpoints(self.control, audit).status, "INCOMPLETE")
        control_trace = self.control_archive.result.traces[-1]
        bad_control = replace(self.control_archive.result.control,
            traces=self.control_archive.result.traces[:-1] + (replace(control_trace, decision=None),))
        archive = replace(self.control_archive,
                          result=replace(self.control_archive.result, control=bad_control))
        audit = h.extract_guess_checkpoints(archive, num_mines=2)
        self.assertEqual(audit.status, "INCOMPLETE")
        self.assertEqual(h.compare_guess_checkpoints(audit, self.kp0).status, "INCOMPLETE")

    def test_extraction_uses_only_archived_public_evidence(self):
        h = self.h
        forbidden = AssertionError("P-3 must not manufacture a fresh decision or oracle result")
        with patch.object(KLocalSession, "analyze_decision", side_effect=forbidden), \
                patch("simple_decision.analyze_position", side_effect=forbidden), \
                patch("simple_probability.calculate_probabilities", side_effect=forbidden), \
                patch.object(public_oracles, "enumerate_public_worlds", side_effect=forbidden), \
                patch.object(public_oracles, "materialized_exact_reference", side_effect=forbidden), \
                patch.object(runner, "plan_position", side_effect=forbidden):
            control = h.extract_guess_checkpoints(self.control_archive, num_mines=2)
            kp0 = h.extract_guess_checkpoints(self.kp0_archive, num_mines=2)
            self.assertEqual(h.compare_guess_checkpoints(control, kp0).status, "PASS")
        self.assertEqual(control.archive_digest, h.content_digest(self.control_archive))
        self.assertEqual(kp0.archive_digest, h.content_digest(self.kp0_archive))

    def test_relabeling_both_uncertain_opens_cannot_hide_actual_guesses(self):
        h = self.h
        control_trace = self.control_archive.result.traces[-1]
        fake_control_evidence = replace(control_trace.decision.evidence,
            kind=DecisionKind.LOCAL_DETERMINISTIC, probability_result=None)
        fake_control_trace = replace(control_trace,
            decision=replace(control_trace.decision, evidence=fake_control_evidence))
        fake_control_run = replace(self.control_archive.result.control,
            traces=self.control_archive.result.traces[:-1] + (fake_control_trace,))
        fake_control = replace(self.control_archive,
            result=replace(self.control_archive.result, control=fake_control_run))
        kp0_trace = self.kp0_archive.result.traces[-1]
        fake_kp0_evidence = replace(kp0_trace.selection.evidence, continuation="LOCAL_REVEAL")
        fake_kp0_trace = replace(kp0_trace, category="DIRECT_OPEN",
            selection=replace(kp0_trace.selection, category="DIRECT_OPEN", evidence=fake_kp0_evidence))
        fake_kp0 = replace(self.kp0_archive, result=replace(self.kp0_archive.result,
            traces=self.kp0_archive.result.traces[:-1] + (fake_kp0_trace,)))
        control = h.extract_guess_checkpoints(fake_control, num_mines=2)
        kp0 = h.extract_guess_checkpoints(fake_kp0, num_mines=2)
        self.assertEqual(control.status, "INCOMPLETE")
        self.assertEqual(kp0.status, "INCOMPLETE")
        self.assertEqual(h.compare_guess_checkpoints(control, kp0).status, "INCOMPLETE")

        # Retaining probability data under a LOCAL label raises the frozen
        # planner's own malformed-evidence error; projection must contain it.
        mismatched = replace(control_trace.decision.evidence, kind=DecisionKind.LOCAL_DETERMINISTIC)
        malformed_trace = replace(control_trace, decision=replace(control_trace.decision, evidence=mismatched))
        malformed_run = replace(self.control_archive.result.control,
            traces=self.control_archive.result.traces[:-1] + (malformed_trace,))
        malformed_archive = replace(self.control_archive,
            result=replace(self.control_archive.result, control=malformed_run))
        self.assertEqual(h.extract_guess_checkpoints(malformed_archive, num_mines=2).status, "INCOMPLETE")

    def test_public_mine_total_and_case_identity_are_required(self):
        h = self.h
        for total in (True, -1, None, 2.0):
            with self.subTest(total=total), self.assertRaises(ValueError):
                h.extract_guess_checkpoints(self.kp0_archive, num_mines=total)
        for total in (0, 3):
            with self.subTest(total=total):
                audit = h.extract_guess_checkpoints(self.kp0_archive, num_mines=total)
                self.assertEqual(audit.status, "INCOMPLETE")
        other = replace(self.kp0, case_id="another-case",
                        checkpoints=(replace(self.kp0.checkpoints[0], case_id="another-case"),))
        self.assertNotEqual(h.compare_guess_checkpoints(self.control, other).status, "PASS")

    def test_records_are_immutable_exact_and_deterministically_reconstructable(self):
        h = self.h
        comparison = h.compare_guess_checkpoints(self.control, self.kp0)
        for value in (self.control, self.kp0, self.control.checkpoints[0], comparison):
            with self.subTest(kind=type(value).__name__):
                self.assertTrue(is_dataclass(value))
                self.assertTrue(value.__dataclass_params__.frozen)
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, fields(value)[0].name, None)
                raw = h.canonical_bytes(value)
                self.assertEqual(h.reconstruct(raw, expected_digest=h.content_digest(value)), value)
                self.assertEqual(h.canonical_bytes(pickle.loads(pickle.dumps(value))), raw)
        for _, numerator in self.control.checkpoints[0].mine_worlds:
            self.assertIs(type(numerator), int)
        for _, probability in self.control.checkpoints[0].probabilities:
            self.assertIs(type(probability), Fraction)
        self.assertNotIn(b"E0_PASS", h.canonical_bytes(comparison))


if __name__ == "__main__":
    unittest.main()
