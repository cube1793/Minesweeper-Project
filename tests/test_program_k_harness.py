"""Slice-4 implementation/unit integration only; no E0/E1 or P-8 claim.

Tiny explicit layouts are confined to Engine construction below. Solver-facing
fixtures are raw public observations; no answer, fingerprint, evaluator or ZiNi
payload is passed to K. Synthetic status faults are labeled separately from
reachable Engine outcomes. Ordinary calls retain default SETUP_OPEN vocabulary.
"""

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction
from pathlib import Path
import unittest
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from experiments import program_k_runner as runner
from experiments.program_k_capability import KIntegrityError, KLocalSession
from experiments.program_k_policy import KCandidate, select_policy
from simple_algorithm import SimpleMove
from stage3_physical import load_timing_table
from stage3_planner import RevealPlan


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
        self.assertFalse(imports & {"stage3_runner", "simple_runner", "board_snapshot", "zini_core",
                                    "benchmark_board", "benchmark_runner", "experiments.program_k_evaluator"})
        self.assertFalse(any(isinstance(node, ast.Name) and node.id == "_validate_execution"
                             for node in ast.walk(tree)))

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


if __name__ == "__main__":
    unittest.main()
