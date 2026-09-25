"""Independent decision evidence fixtures plus real Stage 2 adapter cases."""

import inspect
import runpy
import sys
import types
import unittest
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
from typing import get_type_hints
from unittest.mock import patch

import simple_telemetry
import telemetry_model
from core_engine import Action, CellState
from simple_algorithm import InferenceResult, SimpleMove
from simple_decision import DecisionKind, SimpleDecision, analyze_position
from simple_probability import CellProbability, ProbabilityResult
from simple_telemetry import DecisionTelemetry, decision_to_telemetry
from telemetry_model import InferenceCategory


H = CellState.HIDDEN.value
F = CellState.FLAGGED.value
# Deliberately not sorted: row priority and then column priority both matter.
TIED_CELLS = ((0, 2), (3, 0), (1, 0))


def local_decision(move, *, safe=(), mines=()):
    return SimpleDecision(
        kind=DecisionKind.LOCAL_DETERMINISTIC,
        move=move,
        constraints=(),
        deterministic_result=InferenceResult(safe, mines),
        probability_result=None,
    )


def probability_decision(kind, move, counts, *, total=12, floating=()):
    """Build immutable evidence without asking a production selector for a move."""
    return SimpleDecision(
        kind=kind,
        move=move,
        constraints=(),
        deterministic_result=InferenceResult((), ()),
        probability_result=ProbabilityResult(
            total_worlds=total,
            probabilities=tuple(
                CellProbability(coordinate, count, total) for coordinate, count in counts
            ),
            frontier_cells=tuple(cell for cell, _ in counts if cell not in floating),
            unconstrained_cells=floating,
        ),
    )


def selector_cases():
    """All five selector classes, each with an independent three-cell tie."""
    return (
        local_decision(SimpleMove(Action.OPEN, 1, 0), safe=TIED_CELLS),
        local_decision(SimpleMove(Action.FLAG, 1, 0), mines=TIED_CELLS),
        probability_decision(
            DecisionKind.GLOBAL_CERTAINTY, SimpleMove(Action.OPEN, 1, 0),
            tuple((cell, 0) for cell in TIED_CELLS) + (((0, 0), 6),),
        ),
        probability_decision(
            DecisionKind.GLOBAL_CERTAINTY, SimpleMove(Action.FLAG, 1, 0),
            tuple((cell, 12) for cell in TIED_CELLS) + (((0, 0), 6),),
        ),
        probability_decision(
            DecisionKind.PROBABILITY_GUESS, SimpleMove(Action.OPEN, 1, 0),
            tuple((cell, 4) for cell in TIED_CELLS) + (((0, 0), 6),),
            floating=((0, 2),),
        ),
    )


class SimpleTelemetryTests(unittest.TestCase):
    def test_generic_enum_is_distinct_and_mapping_covers_every_decision_kind(self):
        expected = {
            DecisionKind.LOCAL_DETERMINISTIC: InferenceCategory.LOCAL_DETERMINISTIC,
            DecisionKind.GLOBAL_CERTAINTY: InferenceCategory.GLOBAL_CERTAINTY,
            DecisionKind.PROBABILITY_GUESS: InferenceCategory.PROBABILITY_GUESS,
        }
        self.assertIsNot(InferenceCategory, DecisionKind)
        self.assertEqual(set(expected), set(DecisionKind))
        self.assertEqual(set(expected.values()), set(InferenceCategory))
        self.assertEqual(set(simple_telemetry._INFERENCE_CATEGORIES), set(DecisionKind))
        self.assertEqual({case.kind for case in selector_cases()}, set(DecisionKind))
        for decision in selector_cases():
            with self.subTest(kind=decision.kind, action=decision.move.action):
                category = decision_to_telemetry(decision).inference_category
                self.assertIs(category, expected[decision.kind])
                self.assertNotIsInstance(category, DecisionKind)

    def test_generic_model_loads_without_stage_two_or_engine(self):
        blocked = dict.fromkeys((
            "simple_algorithm", "simple_probability", "simple_decision",
            "simple_runner", "simple_telemetry", "core_engine",
        ))
        with patch.dict(sys.modules, blocked):
            model = runpy.run_path(telemetry_model.__file__)
        self.assertEqual(
            {member.name for member in model["InferenceCategory"]},
            {"LOCAL_DETERMINISTIC", "GLOBAL_CERTAINTY", "PROBABILITY_GUESS"},
        )
        self.assertNotIn("DecisionKind", model)

    def test_local_safe_open_counts_only_safe_candidates(self):
        decision = local_decision(SimpleMove(Action.OPEN, 1, 0), safe=TIED_CELLS)
        self.assertEqual(
            decision_to_telemetry(decision),
            DecisionTelemetry(InferenceCategory.LOCAL_DETERMINISTIC, 3, Fraction(0, 1), None),
        )

    def test_local_mine_flag_counts_only_mine_candidates(self):
        decision = local_decision(SimpleMove(Action.FLAG, 1, 0), mines=TIED_CELLS)
        self.assertEqual(
            decision_to_telemetry(decision),
            DecisionTelemetry(InferenceCategory.LOCAL_DETERMINISTIC, 3, Fraction(1, 1), None),
        )

    def test_local_mines_take_priority_over_earlier_safe_cells(self):
        decision = local_decision(
            SimpleMove(Action.FLAG, 1, 0), safe=((0, 0), (0, 1)), mines=TIED_CELLS,
        )
        self.assertEqual(decision_to_telemetry(decision).selection_candidate_count, 3)
        with self.assertRaisesRegex(ValueError, "selector action"):
            decision_to_telemetry(replace(decision, move=SimpleMove(Action.OPEN, 0, 0)))

    def test_global_safe_open_counts_only_zero_probability_cells(self):
        decision = selector_cases()[2]
        self.assertEqual(
            decision_to_telemetry(decision),
            DecisionTelemetry(InferenceCategory.GLOBAL_CERTAINTY, 3, Fraction(0, 1), None),
        )

    def test_global_mine_flag_counts_only_certain_mines(self):
        decision = selector_cases()[3]
        self.assertEqual(
            decision_to_telemetry(decision),
            DecisionTelemetry(InferenceCategory.GLOBAL_CERTAINTY, 3, Fraction(1, 1), None),
        )

    def test_global_mines_take_priority_over_earlier_safe_cells(self):
        decision = probability_decision(
            DecisionKind.GLOBAL_CERTAINTY, SimpleMove(Action.FLAG, 1, 0),
            (((0, 0), 0), ((0, 1), 0), ((1, 0), 12), ((2, 0), 12), ((3, 0), 6)),
        )
        self.assertEqual(
            decision_to_telemetry(decision),
            DecisionTelemetry(InferenceCategory.GLOBAL_CERTAINTY, 2, Fraction(1, 1), None),
        )
        with self.assertRaisesRegex(ValueError, "selector action"):
            decision_to_telemetry(replace(decision, move=SimpleMove(Action.OPEN, 0, 0)))

    def test_guess_exact_minimum_tie_includes_frontier_and_floating_cells(self):
        decision = selector_cases()[4]
        self.assertEqual(
            decision_to_telemetry(decision),
            DecisionTelemetry(InferenceCategory.PROBABILITY_GUESS, 3, Fraction(1, 3), Fraction(1, 3)),
        )

    def test_guess_selects_safer_floating_pool(self):
        decision = probability_decision(
            DecisionKind.PROBABILITY_GUESS, SimpleMove(Action.OPEN, 2, 0),
            (((0, 0), 6), ((1, 0), 6), ((2, 0), 4), ((3, 0), 4)),
            floating=((2, 0), (3, 0)),
        )
        telemetry = decision_to_telemetry(decision)
        self.assertEqual(telemetry.selection_candidate_count, 2)
        self.assertEqual(telemetry.target_mine_probability, Fraction(1, 3))
        self.assertEqual(telemetry.target_mine_probability, telemetry.minimum_available_mine_probability)

    def test_guess_with_only_floating_cells(self):
        decision = probability_decision(
            DecisionKind.PROBABILITY_GUESS, SimpleMove(Action.OPEN, 1, 0),
            tuple((cell, 4) for cell in TIED_CELLS), floating=TIED_CELLS,
        )
        self.assertEqual(decision_to_telemetry(decision).selection_candidate_count, 3)

    def test_probability_values_are_fractions_without_float_conversion(self):
        with patch.object(Fraction, "__float__", side_effect=AssertionError("No float conversion")):
            for decision in selector_cases():
                with self.subTest(kind=decision.kind, action=decision.move.action):
                    telemetry = decision_to_telemetry(decision)
                    self.assertIs(type(telemetry.target_mine_probability), Fraction)
                    if decision.kind == DecisionKind.PROBABILITY_GUESS:
                        self.assertIs(type(telemetry.minimum_available_mine_probability), Fraction)
                        self.assertEqual(telemetry.target_mine_probability, Fraction(4, 12))
                    else:
                        self.assertIsNone(telemetry.minimum_available_mine_probability)

    def test_large_world_counts_preserve_exact_risk_and_distinct_near_ties(self):
        total = 10**400
        for numerator in (1, total // 3, total - 2):
            with self.subTest(numerator=numerator):
                decision = probability_decision(
                    DecisionKind.PROBABILITY_GUESS, SimpleMove(Action.OPEN, 1, 0),
                    (((0, 0), numerator + 1), ((1, 0), numerator), ((2, 0), numerator)),
                    total=total, floating=((2, 0),),
                )
                telemetry = decision_to_telemetry(decision)
                self.assertEqual(telemetry.selection_candidate_count, 2)
                self.assertEqual(telemetry.target_mine_probability, Fraction(numerator, total))
                self.assertEqual(telemetry.minimum_available_mine_probability, Fraction(numerator, total))

    def test_global_certainty_uses_exact_world_counts_at_large_boundaries(self):
        total = 10**400
        for action, certain_count, nearby_count in (
            (Action.OPEN, 0, 1), (Action.FLAG, total, total - 1),
        ):
            with self.subTest(action=action):
                decision = probability_decision(
                    DecisionKind.GLOBAL_CERTAINTY, SimpleMove(action, 1, 0),
                    (((0, 0), nearby_count), ((1, 0), certain_count), ((2, 0), certain_count)),
                    total=total,
                )
                telemetry = decision_to_telemetry(decision)
                self.assertEqual(telemetry.selection_candidate_count, 2)
                self.assertEqual(telemetry.target_mine_probability, Fraction(certain_count, total))

    def test_drift_rejects_wrong_action_for_every_selector_class(self):
        for decision in selector_cases():
            wrong_action = Action.FLAG if decision.move.action == Action.OPEN else Action.OPEN
            with self.subTest(kind=decision.kind, action=decision.move.action):
                with self.assertRaisesRegex(ValueError, "selector action"):
                    decision_to_telemetry(replace(
                        decision, move=replace(decision.move, action=wrong_action),
                    ))

    def test_drift_rejects_coordinates_outside_final_pool(self):
        for decision in selector_cases():
            with self.subTest(kind=decision.kind, action=decision.move.action):
                with self.assertRaises(ValueError):
                    decision_to_telemetry(replace(
                        decision, move=replace(decision.move, x=99, y=99),
                    ))
        # A known probability cell also fails when it is outside the certainty pool.
        for decision in selector_cases()[2:4]:
            with self.subTest(action=decision.move.action):
                with self.assertRaisesRegex(ValueError, "outside the derived final pool"):
                    decision_to_telemetry(replace(
                        decision, move=replace(decision.move, x=0, y=0),
                    ))

    def test_drift_rejects_nonminimum_row_or_column_within_every_tied_pool(self):
        for decision in selector_cases():
            for x, y in ((0, 2), (3, 0)):
                with self.subTest(kind=decision.kind, action=decision.move.action, cell=(x, y)):
                    with self.assertRaisesRegex(ValueError, r"\(y, x\) tie-break"):
                        decision_to_telemetry(replace(
                            decision, move=replace(decision.move, x=x, y=y),
                        ))

    def test_guess_drift_rejects_target_above_exact_minimum(self):
        total = 10**400
        decision = probability_decision(
            DecisionKind.PROBABILITY_GUESS, SimpleMove(Action.OPEN, 0, 0),
            (((0, 0), total // 2 + 1), ((1, 0), total // 2)), total=total,
        )
        with self.assertRaisesRegex(ValueError, "does not equal the exact minimum"):
            decision_to_telemetry(decision)

    def test_drift_rejects_empty_local_or_global_certainty_pool(self):
        decisions = (
            local_decision(SimpleMove(Action.OPEN, 0, 0)),
            probability_decision(
                DecisionKind.GLOBAL_CERTAINTY, SimpleMove(Action.OPEN, 0, 0),
                (((0, 0), 6),),
            ),
        )
        for decision in decisions:
            with self.subTest(kind=decision.kind):
                with self.assertRaisesRegex(ValueError, "no candidates"):
                    decision_to_telemetry(decision)

    def test_probability_decisions_require_nonempty_probability_evidence(self):
        for decision in selector_cases()[2:]:
            for result in (None, ProbabilityResult(1, (), (), ())):
                with self.subTest(kind=decision.kind, result=result):
                    with self.assertRaisesRegex(ValueError, "nonempty probability evidence"):
                        decision_to_telemetry(replace(decision, probability_result=result))

    def test_probability_decisions_cannot_bypass_local_candidates(self):
        for decision in selector_cases()[2:]:
            for inference in (InferenceResult(((5, 5),), ()), InferenceResult((), ((5, 5),))):
                with self.subTest(kind=decision.kind, inference=inference):
                    with self.assertRaisesRegex(ValueError, "Local candidates must take priority"):
                        decision_to_telemetry(replace(decision, deterministic_result=inference))

    def test_guess_cannot_bypass_certainty_candidates(self):
        for certain_count in (0, 12):
            with self.subTest(certain_count=certain_count):
                decision = probability_decision(
                    DecisionKind.PROBABILITY_GUESS, SimpleMove(Action.OPEN, 0, 0),
                    (((0, 0), 4), ((1, 0), certain_count)),
                )
                with self.assertRaisesRegex(ValueError, "cannot bypass certainty candidates"):
                    decision_to_telemetry(decision)

    def test_unknown_decision_kind_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "Unsupported decision kind"):
            decision_to_telemetry(replace(selector_cases()[0], kind="future_kind"))

    def test_adapter_uses_only_existing_evidence_without_analysis_or_engine(self):
        decisions = selector_cases()
        originals = deepcopy(decisions)
        expected = tuple(decision_to_telemetry(decision) for decision in decisions)
        public_types = types.ModuleType("core_engine")
        public_types.Action = Action
        blocked = dict.fromkeys((
            "board_snapshot", "board_analyzer", "replay_model", "replay_recorder",
            "replay_player", "simple_runner", "sqlite3",
        ))
        with ExitStack() as stack:
            for module, names in (
                ("simple_algorithm", ("build_constraints", "infer_deterministic", "choose_deterministic_move")),
                ("simple_probability", ("build_constraints", "calculate_probabilities", "choose_probability_move")),
                ("simple_decision", (
                    "analyze_position", "build_constraints", "infer_deterministic",
                    "choose_deterministic_move", "calculate_probabilities", "choose_probability_move",
                )),
            ):
                for name in names:
                    stack.enter_context(patch(
                        f"{module}.{name}", side_effect=AssertionError("Analysis must not run"),
                    ))
            stack.enter_context(patch.dict(sys.modules, {"core_engine": public_types, **blocked}))
            # Load after patching so imported solver aliases would also fail.
            adapter = runpy.run_path(simple_telemetry.__file__)
            for decision, telemetry in zip(decisions, expected):
                actual = adapter["decision_to_telemetry"](decision)
                for field in fields(DecisionTelemetry):
                    self.assertEqual(getattr(actual, field.name), getattr(telemetry, field.name))
        self.assertEqual(decisions, originals)

    def test_public_api_accepts_only_a_decision(self):
        self.assertEqual(tuple(inspect.signature(decision_to_telemetry).parameters), ("decision",))
        self.assertEqual(get_type_hints(decision_to_telemetry), {
            "decision": SimpleDecision, "return": DecisionTelemetry,
        })
        with self.assertRaises(TypeError):
            decision_to_telemetry(selector_cases()[0], engine=object())

    def test_telemetry_is_immutable_and_has_only_the_four_semantic_fields(self):
        telemetry = decision_to_telemetry(selector_cases()[4])
        self.assertEqual(get_type_hints(DecisionTelemetry), {
            "inference_category": InferenceCategory,
            "selection_candidate_count": int,
            "target_mine_probability": Fraction | None,
            "minimum_available_mine_probability": Fraction | None,
        })
        self.assertEqual(
            {field.name for field in fields(DecisionTelemetry)},
            set(get_type_hints(DecisionTelemetry)),
        )
        self.assertFalse(hasattr(telemetry, "decision_compute_ns"))
        for field in fields(DecisionTelemetry):
            with self.subTest(field=field.name):
                with self.assertRaises(FrozenInstanceError):
                    setattr(telemetry, field.name, None)

    def test_real_analysis_outputs_preserve_expected_telemetry_and_decision(self):
        cases = (
            ([[0, H], [H, H]], 0, SimpleMove(Action.OPEN, 1, 0),
             InferenceCategory.LOCAL_DETERMINISTIC, 3, Fraction(0, 1), None),
            ([[0, H, H, 3], [H, H, H, H]], 3, SimpleMove(Action.FLAG, 2, 0),
             InferenceCategory.LOCAL_DETERMINISTIC, 3, Fraction(1, 1), None),
            ([[H, 1, H, H, H]], 1, SimpleMove(Action.OPEN, 3, 0),
             InferenceCategory.GLOBAL_CERTAINTY, 2, Fraction(0, 1), None),
            (((H, 2, 2, H), (F, H, H, F)), 4, SimpleMove(Action.FLAG, 0, 0),
             InferenceCategory.GLOBAL_CERTAINTY, 2, Fraction(1, 1), None),
            ([[H, 1, H, H, H, H]], 2, SimpleMove(Action.OPEN, 3, 0),
             InferenceCategory.PROBABILITY_GUESS, 3, Fraction(1, 3), Fraction(1, 3)),
            ([[H, 1, H, H, H]], 2, SimpleMove(Action.OPEN, 0, 0),
             InferenceCategory.PROBABILITY_GUESS, 4, Fraction(1, 2), Fraction(1, 2)),
            ([[H, H], [H, H]], 1, SimpleMove(Action.OPEN, 0, 0),
             InferenceCategory.PROBABILITY_GUESS, 4, Fraction(1, 4), Fraction(1, 4)),
        )
        for observation, mines, move, category, count, target, minimum in cases:
            with self.subTest(observation=observation, mines=mines):
                decision = analyze_position(observation, mines)
                original = deepcopy(decision)
                self.assertIsNotNone(decision)
                self.assertEqual(decision.move, move)
                self.assertEqual(
                    decision_to_telemetry(decision),
                    DecisionTelemetry(category, count, target, minimum),
                )
                self.assertEqual(decision, original)


if __name__ == "__main__":
    unittest.main()
