"""Stage-3 semantic V2 checks from public evidence and small production traces.

Handwritten immutable evidence isolates adaptation from planning. Fixed layouts
only arrange runner fixtures; no answer, observation or engine enters the
adapter. Positive clue values and observation freshness remain runner checks
because Stage3ActionTrace and Constraint do not retain the original clue value.
"""

import ast
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
import inspect
import runpy
import sys
import types
import unittest
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from simple_algorithm import Constraint, InferenceResult, SimpleMove
from simple_decision import DecisionKind, SimpleDecision, analyze_position
from simple_probability import CellProbability, ProbabilityResult
from stage3_physical import load_timing_table
from stage3_planner import RevealPlan, Stage3Decision, plan_position
from stage3_runner import Stage3ActionTrace, Stage3RunnerError, _validate_execution, run_stage3
import stage3_telemetry
from stage3_telemetry import Stage3ActionTelemetry, trace_to_telemetry
from telemetry_model import ActionEvent, InferenceCategory


H, F = CellState.HIDDEN, CellState.FLAGGED


def local_evidence(move, *, safe=(), mines=(), constraints=()):
    return SimpleDecision(
        DecisionKind.LOCAL_DETERMINISTIC, move, constraints,
        InferenceResult(safe, mines), None,
    )


def probability_evidence(kind, move, counts, *, total=12, floating=()):
    return SimpleDecision(
        kind, move, (), InferenceResult((), ()),
        ProbabilityResult(
            total,
            tuple(CellProbability(cell, count, total) for cell, count in counts),
            tuple(cell for cell, _ in counts if cell not in floating),
            floating,
        ),
    )


def trace_for(evidence, *, move=None, plan=None, timing=37):
    move = evidence.move if move is None else move
    return Stage3ActionTrace(
        move, Stage3Decision(evidence, move, plan), timing, (0, 0), 126005,
        GameStatus.PLAYING, 0, int(move.action == Action.FLAG),
    )


def policy_trace():
    return Stage3ActionTrace(
        SimpleMove(Action.OPEN, 0, 0), None, None, (0, 0), 126005,
        GameStatus.PLAYING, 1, 0,
    )


def certainty_traces():
    """Each actual target differs from the Stage-2 recommendation's target."""
    return (
        trace_for(
            local_evidence(SimpleMove(Action.FLAG, 1, 0),
                           safe=((2, 0), (3, 0)), mines=((1, 0),)),
            move=SimpleMove(Action.OPEN, 3, 0),
        ),
        trace_for(
            local_evidence(SimpleMove(Action.FLAG, 1, 0), mines=((1, 0), (3, 0))),
            move=SimpleMove(Action.FLAG, 3, 0),
        ),
        trace_for(
            probability_evidence(
                DecisionKind.GLOBAL_CERTAINTY, SimpleMove(Action.FLAG, 1, 0),
                (((1, 0), 12), ((2, 0), 0), ((3, 0), 0)),
            ),
            move=SimpleMove(Action.OPEN, 3, 0),
        ),
        trace_for(
            probability_evidence(
                DecisionKind.GLOBAL_CERTAINTY, SimpleMove(Action.FLAG, 1, 0),
                (((1, 0), 12), ((2, 0), 0), ((3, 0), 12)),
            ),
            move=SimpleMove(Action.FLAG, 3, 0),
        ),
    )


def guess_trace():
    return trace_for(probability_evidence(
        DecisionKind.PROBABILITY_GUESS, SimpleMove(Action.OPEN, 2, 0),
        (((0, 0), 6), ((1, 0), 6), ((2, 0), 4), ((3, 0), 4)),
        floating=((2, 0), (3, 0)),
    ))


def chord_trace():
    safe = ((2, 0), (2, 1))
    move = SimpleMove(Action.CHORD, 1, 0)
    evidence = local_evidence(
        SimpleMove(Action.OPEN, 2, 0), safe=safe,
        constraints=(Constraint((1, 0), 0, safe),),
    )
    return trace_for(evidence, move=move, plan=RevealPlan((move,), 126005, 2))


class Stage3TelemetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def test_certainty_validates_actual_target_and_preserves_exact_probabilities(self):
        expected = (
            (InferenceCategory.LOCAL_DETERMINISTIC, Fraction(0, 1)),
            (InferenceCategory.LOCAL_DETERMINISTIC, Fraction(1, 1)),
            (InferenceCategory.GLOBAL_CERTAINTY, Fraction(0, 1)),
            (InferenceCategory.GLOBAL_CERTAINTY, Fraction(1, 1)),
        )
        for trace, (category, probability) in zip(certainty_traces(), expected):
            with self.subTest(category=category, action=trace.move.action):
                self.assertNotEqual(trace.move, trace.decision.evidence.move)
                actual = trace_to_telemetry(trace)
                self.assertEqual(actual, Stage3ActionTelemetry(
                    category, None, probability, None, 37,
                ))
                self.assertIs(type(actual.target_mine_probability), Fraction)

    def test_guess_minimum_includes_safer_unconstrained_cells(self):
        trace = guess_trace()
        self.assertEqual(trace.move, trace.decision.evidence.move)
        actual = trace_to_telemetry(trace)
        self.assertEqual(actual, Stage3ActionTelemetry(
            InferenceCategory.PROBABILITY_GUESS, None, Fraction(1, 3), Fraction(1, 3), 37,
        ))
        self.assertIs(type(actual.target_mine_probability), Fraction)
        self.assertIs(type(actual.minimum_available_mine_probability), Fraction)

    def test_guess_all_floating_and_frontier_floating_ties_keep_stage2_reading_order(self):
        counts = (((0, 1), 4), ((3, 0), 4), ((1, 0), 4))
        for floating in (((0, 1),), tuple(cell for cell, _ in counts)):
            with self.subTest(floating=floating):
                evidence = probability_evidence(
                    DecisionKind.PROBABILITY_GUESS, SimpleMove(Action.OPEN, 1, 0),
                    counts, floating=floating,
                )
                self.assertEqual(trace_to_telemetry(trace_for(evidence)).target_mine_probability,
                                 Fraction(1, 3))
                for x, y in ((0, 1), (3, 0)):
                    with self.assertRaises(ValueError):
                        trace_to_telemetry(trace_for(replace(
                            evidence, move=SimpleMove(Action.OPEN, x, y),
                        )))

    def test_large_world_counts_preserve_exact_risk_and_reject_near_minimum(self):
        total = 10**400
        count = total // 3
        evidence = probability_evidence(
            DecisionKind.PROBABILITY_GUESS, SimpleMove(Action.OPEN, 1, 0),
            (((0, 0), count + 1), ((1, 0), count)), total=total,
        )
        with patch.object(Fraction, "__float__", side_effect=AssertionError("float conversion")):
            actual = trace_to_telemetry(trace_for(evidence))
            self.assertEqual(actual.target_mine_probability, Fraction(count, total))
            self.assertEqual(actual.minimum_available_mine_probability, Fraction(count, total))
            with self.assertRaises(ValueError):
                trace_to_telemetry(trace_for(replace(evidence, move=SimpleMove(Action.OPEN, 0, 0))))

    def test_local_chord_probabilities_are_not_applicable_and_timing_is_retained(self):
        self.assertEqual(trace_to_telemetry(chord_trace()), Stage3ActionTelemetry(
            InferenceCategory.LOCAL_DETERMINISTIC, None, None, None, 37,
        ))

    def test_canonical_policy_open_has_only_null_metadata(self):
        actual = trace_to_telemetry(policy_trace())
        self.assertEqual(actual, Stage3ActionTelemetry(None, None, None, None, None))

    def test_policy_rejects_other_moves_or_any_compute_timing(self):
        trace = policy_trace()
        for move in (SimpleMove(Action.OPEN, 1, 0), SimpleMove(Action.OPEN, 0, 1),
                     SimpleMove(Action.FLAG, 0, 0), SimpleMove(Action.CHORD, 0, 0)):
            with self.subTest(move=move), self.assertRaises(ValueError):
                trace_to_telemetry(replace(trace, move=move))
        for timing in (0, 1, False):
            with self.subTest(timing=timing), self.assertRaises(ValueError):
                trace_to_telemetry(replace(trace, decision_compute_ns=timing))

    def test_analyzed_timing_required_nonnegative_integer_and_zero_preserved(self):
        for trace in (*certainty_traces(), guess_trace(), chord_trace()):
            with self.subTest(action=trace.move.action, kind=trace.decision.evidence.kind):
                self.assertEqual(trace_to_telemetry(replace(trace, decision_compute_ns=0))
                                 .decision_compute_ns, 0)
                for timing in (None, True, False, -1, 1.5, "37"):
                    with self.subTest(timing=timing), self.assertRaises(ValueError):
                        trace_to_telemetry(replace(trace, decision_compute_ns=timing))

    def test_unsupported_decision_kind_fails_closed(self):
        trace = certainty_traces()[0]
        for kind in (None, "local_deterministic", "future_kind"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                trace_to_telemetry(replace(trace, decision=replace(
                    trace.decision, evidence=replace(trace.decision.evidence, kind=kind),
                )))

    def test_trace_move_and_plan_first_action_must_match_executed_decision(self):
        trace = certainty_traces()[0]
        wrong = SimpleMove(Action.OPEN, 2, 0)
        with self.assertRaises(ValueError):
            trace_to_telemetry(replace(trace, move=wrong))
        with self.assertRaises(ValueError):
            trace_to_telemetry(replace(trace, decision=replace(
                trace.decision, plan=RevealPlan((wrong, trace.move), 252010, 1),
            )))

    def test_invalid_move_types_and_coordinates_fail_closed(self):
        for move in (SimpleMove("OPEN", 0, 0), SimpleMove(True, 0, 0),
                     SimpleMove(Action.OPEN, True, 0), SimpleMove(Action.OPEN, 0, False),
                     SimpleMove(Action.OPEN, -1, 0), SimpleMove(Action.OPEN, 0, 1.5)):
            with self.subTest(move=move), self.assertRaises(ValueError):
                trace_to_telemetry(replace(policy_trace(), move=move))

    def test_certainty_rejects_actual_target_without_public_support(self):
        for trace in certainty_traces():
            wrong = SimpleMove(trace.move.action, 99, 99)
            with self.subTest(kind=trace.decision.evidence.kind, action=wrong.action):
                self.assertNotEqual(trace.move, trace.decision.evidence.move)
                with self.assertRaises(ValueError):
                    trace_to_telemetry(replace(
                        trace, move=wrong, decision=replace(trace.decision, move=wrong),
                    ))

    def test_local_cannot_include_probability_and_global_cannot_bypass_local_facts(self):
        local, _, global_trace, _ = certainty_traces()
        with self.assertRaises(ValueError):
            trace_to_telemetry(replace(local, decision=replace(
                local.decision, evidence=replace(
                    local.decision.evidence,
                    probability_result=global_trace.decision.evidence.probability_result,
                ),
            )))
        for facts in (InferenceResult(((5, 5),), ()), InferenceResult((), ((5, 5),))):
            with self.subTest(facts=facts), self.assertRaises(ValueError):
                trace_to_telemetry(replace(global_trace, decision=replace(
                    global_trace.decision, evidence=replace(
                        global_trace.decision.evidence, deterministic_result=facts,
                    ),
                )))

    def test_probability_paths_require_nonempty_probability_evidence(self):
        for trace in (*certainty_traces()[2:], guess_trace()):
            for result in (None, ProbabilityResult(1, (), (), ())):
                with self.subTest(kind=trace.decision.evidence.kind, result=result):
                    with self.assertRaises(ValueError):
                        trace_to_telemetry(replace(trace, decision=replace(
                            trace.decision, evidence=replace(
                                trace.decision.evidence, probability_result=result,
                            ),
                        )))

    def test_probability_paths_reject_duplicate_coordinates_instead_of_collapsing_evidence(self):
        for kind, counts in (
            (DecisionKind.GLOBAL_CERTAINTY, (((0, 0), 0), ((0, 0), 12))),
            (DecisionKind.GLOBAL_CERTAINTY, (((0, 0), 0), ((0, 0), 6))),
            (DecisionKind.PROBABILITY_GUESS, (((0, 0), 6), ((0, 0), 4))),
        ):
            with self.subTest(kind=kind, counts=counts), self.assertRaises(ValueError):
                trace_to_telemetry(trace_for(probability_evidence(
                    kind, SimpleMove(Action.OPEN, 0, 0), counts,
                )))

    def test_guess_rejects_non_open_different_stage2_move_and_reveal_plan(self):
        trace = guess_trace()
        for move in (SimpleMove(Action.FLAG, 2, 0), SimpleMove(Action.CHORD, 2, 0),
                     SimpleMove(Action.OPEN, 3, 0)):
            with self.subTest(move=move), self.assertRaises(ValueError):
                trace_to_telemetry(replace(
                    trace, move=move, decision=replace(trace.decision, move=move),
                ))
        with self.assertRaises(ValueError):
            trace_to_telemetry(replace(trace, decision=replace(
                trace.decision, plan=RevealPlan((trace.move,), 126005, 1),
            )))

    def test_guess_rejects_absent_target_or_target_above_exact_global_minimum(self):
        evidence = guess_trace().decision.evidence
        for coordinate in ((99, 99), (0, 0)):
            with self.subTest(coordinate=coordinate), self.assertRaises(ValueError):
                trace_to_telemetry(trace_for(replace(
                    evidence, move=SimpleMove(Action.OPEN, *coordinate),
                )))

    def test_guess_cannot_bypass_local_or_probability_certainty(self):
        evidence = guess_trace().decision.evidence
        for facts in (InferenceResult(((9, 9),), ()), InferenceResult((), ((9, 9),))):
            with self.subTest(facts=facts), self.assertRaises(ValueError):
                trace_to_telemetry(trace_for(replace(evidence, deterministic_result=facts)))
        for certain_count in (0, 12):
            with self.subTest(certain_count=certain_count), self.assertRaises(ValueError):
                trace_to_telemetry(trace_for(probability_evidence(
                    DecisionKind.PROBABILITY_GUESS, SimpleMove(Action.OPEN, 0, 0),
                    (((0, 0), 4), ((1, 0), certain_count)),
                )))

    def test_chord_rejects_missing_unsatisfied_empty_or_unsupported_clue_evidence(self):
        trace = chord_trace()
        constraint = trace.decision.evidence.constraints[0]
        invalid_constraints = (
            (), (replace(constraint, source=(0, 0)),),
            (replace(constraint, remaining_mines=1),),
            (Constraint(constraint.source, 0, ()),),
            (Constraint(constraint.source, 0, ((9, 9),)),),
            (constraint, constraint),
        )
        for constraints in invalid_constraints:
            with self.subTest(constraints=constraints), self.assertRaises(ValueError):
                trace_to_telemetry(replace(trace, decision=replace(
                    trace.decision, evidence=replace(trace.decision.evidence, constraints=constraints),
                )))
        with self.assertRaises(ValueError):
            trace_to_telemetry(replace(trace, decision=replace(trace.decision, plan=None)))

    def test_chord_cannot_target_a_hidden_certainty_cell_or_use_probability_path(self):
        trace = chord_trace()
        for facts in (InferenceResult(((1, 0), (2, 0), (2, 1)), ()),
                      InferenceResult(((2, 0), (2, 1)), ((1, 0),))):
            with self.subTest(facts=facts), self.assertRaises(ValueError):
                trace_to_telemetry(replace(trace, decision=replace(
                    trace.decision, evidence=replace(trace.decision.evidence, deterministic_result=facts),
                )))
        # Deliberately inconsistent negative evidence, not a reachable GLOBAL CHORD fixture.
        for kind in (DecisionKind.GLOBAL_CERTAINTY, DecisionKind.PROBABILITY_GUESS):
            evidence = probability_evidence(kind, trace.move, (((2, 0), 0), ((2, 1), 0)))
            evidence = replace(evidence, constraints=trace.decision.evidence.constraints)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                trace_to_telemetry(replace(trace, decision=replace(trace.decision, evidence=evidence)))

    def test_real_public_planner_preserves_speed_selected_open_over_stage2_flag(self):
        observation = [[0, H, H, 3], [H, H, H, H]]
        decision = plan_position(observation, 3, (0, 0), self.table)
        self.assertEqual(decision.evidence.move, SimpleMove(Action.FLAG, 2, 0))
        self.assertEqual(decision.move, SimpleMove(Action.OPEN, 1, 0))
        trace = trace_for(decision.evidence, move=decision.move, plan=decision.plan)
        self.assertEqual(trace_to_telemetry(trace).target_mine_probability, Fraction(0, 1))

    def test_real_public_planner_global_safe_and_global_mine_fallback(self):
        for observation, mines, cursor, action, probability in (
            ([[H, 2, 2, H], [F, H, H, F]], 4, (1, 1), Action.OPEN, Fraction(0, 1)),
            ([[H, H]], 2, (1, 0), Action.FLAG, Fraction(1, 1)),
        ):
            with self.subTest(action=action):
                decision = plan_position(observation, mines, cursor, self.table)
                self.assertEqual(decision.evidence.kind, DecisionKind.GLOBAL_CERTAINTY)
                self.assertEqual(decision.move.action, action)
                actual = trace_to_telemetry(trace_for(
                    decision.evidence, move=decision.move, plan=decision.plan,
                ))
                self.assertEqual(actual.target_mine_probability, probability)
                self.assertIsNone(actual.selection_candidate_count)

    def test_only_executed_first_action_is_adapted_from_a_multi_action_plan(self):
        decision = plan_position([[1, H, 1, H]], 1, (0, 0), self.table)
        self.assertGreater(len(decision.plan.actions), 1)
        self.assertEqual(decision.move, SimpleMove(Action.FLAG, 1, 0))
        self.assertIn(decision.plan.actions[-1].action, (Action.OPEN, Action.CHORD))
        actual = trace_to_telemetry(trace_for(
            decision.evidence, move=decision.move, plan=decision.plan,
        ))
        self.assertIsInstance(actual, Stage3ActionTelemetry)
        self.assertEqual(actual.target_mine_probability, Fraction(1, 1))
        self.assertIsNone(actual.minimum_available_mine_probability)

    def test_real_runner_policy_flag_global_open_and_local_chord_fit_generic_events(self):
        engine = MinesweeperEngine(4, 1, 1)
        engine.reset_with_mines(4, 1, 1, {(1, 0)})
        result = run_stage3(engine, table=self.table)
        self.assertEqual(result.moves, (
            SimpleMove(Action.OPEN, 0, 0), SimpleMove(Action.FLAG, 1, 0),
            SimpleMove(Action.OPEN, 2, 0), SimpleMove(Action.CHORD, 2, 0),
        ))
        expected = (
            (None, None), (InferenceCategory.LOCAL_DETERMINISTIC, Fraction(1, 1)),
            (InferenceCategory.GLOBAL_CERTAINTY, Fraction(0, 1)),
            (InferenceCategory.LOCAL_DETERMINISTIC, None),
        )
        events = []
        for index, (trace, (category, probability)) in enumerate(zip(result.traces, expected)):
            metadata = trace_to_telemetry(trace)
            self.assertEqual(metadata.inference_category, category)
            self.assertEqual(metadata.target_mine_probability, probability)
            self.assertIsNone(metadata.minimum_available_mine_probability)
            self.assertIsNone(metadata.selection_candidate_count)
            self.assertEqual(metadata.decision_compute_ns, trace.decision_compute_ns)
            events.append(ActionEvent(
                action_index=index,
                **{field.name: getattr(metadata, field.name) for field in fields(metadata)},
                action_type=trace.move.action, x=trace.move.x, y=trace.move.y,
                status_after=trace.status_after,
                safe_cells_opened_delta=trace.safe_cells_opened_delta,
                explicit_flag_delta=trace.explicit_flag_delta,
            ))
        self.assertEqual(len(events), len(result.traces))
        self.assertEqual(events[-1].status_after, GameStatus.WON)

    def test_runner_retains_positive_clue_and_fresh_observation_checks(self):
        # A zero clue and a satisfied positive clue can both yield zero-remaining
        # constraints. The original clue value is validated before trace creation.
        observation = [[0, H]]
        evidence = analyze_position(observation, 0)
        move = SimpleMove(Action.CHORD, 0, 0)
        decision = Stage3Decision(evidence, move, RevealPlan((move,), 126005, 1))
        with self.assertRaises(Stage3RunnerError):
            _validate_execution(observation, move, decision)
        observation = [[F, 1, H]]
        decision = plan_position(observation, 1, (1, 0), self.table)
        self.assertEqual(decision.move.action, Action.CHORD)
        _validate_execution(observation, decision.move, decision)
        with self.assertRaises(Stage3RunnerError):
            _validate_execution([[F, 1, 0]], decision.move, decision)

    def test_real_terminal_guess_uses_evidence_not_outcome(self):
        engine = MinesweeperEngine(5, 1, 2)
        engine.reset_with_mines(5, 1, 2, {(1, 0), (2, 0)})
        result = run_stage3(engine, table=self.table)
        trace = result.traces[-1]
        self.assertEqual(trace.status_after, GameStatus.LOST)
        self.assertEqual(trace.decision.evidence.kind, DecisionKind.PROBABILITY_GUESS)
        expected = trace_to_telemetry(trace)
        self.assertEqual(expected.target_mine_probability, Fraction(1, 3))
        for status in GameStatus:
            self.assertEqual(trace_to_telemetry(replace(
                trace, status_after=status, safe_cells_opened_delta=999,
                explicit_flag_delta=-1, cursor_before=(99, 99), modeled_action_us=1,
            )), expected)

    def test_adapter_accepts_only_one_trace_and_metadata_is_immutable(self):
        self.assertEqual(tuple(inspect.signature(trace_to_telemetry).parameters), ("trace",))
        trace = guess_trace()
        for argument in ("engine", "observation", "board_snapshot", "future_action"):
            with self.subTest(argument=argument), self.assertRaises(TypeError):
                trace_to_telemetry(trace, **{argument: object()})
        actual = trace_to_telemetry(trace)
        self.assertEqual({field.name for field in fields(actual)}, {
            "inference_category", "selection_candidate_count", "target_mine_probability",
            "minimum_available_mine_probability", "decision_compute_ns",
        })
        for field in fields(actual):
            with self.subTest(field=field.name), self.assertRaises(FrozenInstanceError):
                setattr(actual, field.name, None)

    def test_source_import_and_attribute_boundary_excludes_hidden_or_future_information(self):
        tree = ast.parse(inspect.getsource(stage3_telemetry))
        imports, names, attributes = set(), set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                attributes.add(node.attr)
        self.assertFalse(imports.intersection({
            "board_snapshot", "board_analyzer", "benchmark_board", "benchmark_runner",
            "telemetry_repository", "replay_model", "replay_player", "replay_recorder", "sqlite3",
        }))
        self.assertFalse((names | attributes).intersection({
            "BoardSnapshot", "MinesweeperEngine", "get_board_snapshot", "mine_positions", "_mines",
            "board_fingerprint", "fingerprint", "board_3bv", "board_ops", "status_after",
            "safe_cells_opened_delta", "explicit_flag_delta", "get_observation", "get_stats",
            "step", "analyze_position", "calculate_probabilities", "infer_deterministic", "float",
        }))

    def test_adapter_never_reanalyzes_executes_or_reads_engine_and_preserves_inputs(self):
        traces = (policy_trace(), *certainty_traces(), guess_trace(), chord_trace())
        originals = deepcopy(traces)
        expected = tuple(trace_to_telemetry(trace) for trace in traces)
        public_types = types.ModuleType("core_engine")
        public_types.Action = Action
        blocked = dict.fromkeys((
            "board_snapshot", "board_analyzer", "benchmark_runner", "replay_model",
            "replay_player", "replay_recorder", "telemetry_repository", "sqlite3",
        ))
        with ExitStack() as stack:
            for module, names in (
                ("simple_algorithm", ("build_constraints", "infer_deterministic", "choose_deterministic_move")),
                ("simple_probability", ("build_constraints", "calculate_probabilities", "choose_probability_move")),
                ("simple_decision", (
                    "analyze_position", "build_constraints", "infer_deterministic",
                    "choose_deterministic_move", "calculate_probabilities", "choose_probability_move",
                )),
                ("stage3_planner", ("analyze_position", "plan_position", "generate_reveal_plans")),
                ("stage3_runner", ("plan_position", "run_stage3", "_validate_execution")),
            ):
                for name in names:
                    stack.enter_context(patch(f"{module}.{name}", side_effect=AssertionError("reanalysis")))
            for name in ("step", "get_observation", "get_board_snapshot", "get_counter_snapshot", "get_stats"):
                stack.enter_context(patch.object(MinesweeperEngine, name, side_effect=AssertionError("engine access")))
            stack.enter_context(patch.object(Fraction, "__float__", side_effect=AssertionError("float conversion")))
            stack.enter_context(patch.dict(sys.modules, {"core_engine": public_types, **blocked}))
            # Loading after patching also catches imports of forbidden function aliases.
            isolated = runpy.run_path(stage3_telemetry.__file__)
            for trace, metadata in zip(traces, expected):
                actual = isolated["trace_to_telemetry"](trace)
                self.assertEqual(
                    tuple(getattr(actual, field.name) for field in fields(metadata)),
                    tuple(getattr(metadata, field.name) for field in fields(metadata)),
                )
        self.assertEqual(traces, originals)


if __name__ == "__main__":
    unittest.main()
