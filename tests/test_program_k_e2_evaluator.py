"""I5 evaluator: tiny literal boards and detached private fault injection only."""

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from enum import Enum
import hashlib
import inspect
import struct
import unittest
from unittest.mock import patch

from core_engine import MinesweeperEngine
from experiments import program_k_e2_evaluator as adapter
from experiments import program_k_e2_game as game
from experiments import program_k_e2_records as records
from experiments import program_k_evaluator as primitive
from experiments import program_k_runner as runner
from stage3_physical import load_timing_table


def _fingerprint(width, height, mines):
    # Independent literal construction of the documented MSLAYOUT1 identity.
    cells = sorted(mines, key=lambda cell: (cell[1], cell[0]))
    raw = b"MSLAYOUT1\0" + struct.pack(">III", width, height, len(cells))
    return hashlib.sha256(raw + b"".join(struct.pack(">II", *cell) for cell in cells)).hexdigest()


def _arm(width, height, mines, index=1):
    board = records.BoardIdentity(index, _fingerprint(width, height, mines), width, height,
                                 len(mines), (0, 0), "literal-fixture", "I5-synthetic")
    return records.ArmIdentity(records.Arm.K_P0, board, "I5-fixture", "unit-" + str(index))


def _corrupt(value, **changes):
    result = deepcopy(value)
    for name, changed in changes.items():
        object.__setattr__(result, name, changed)
    return result


class _PublicPort:
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

    @property
    def mines(self):
        raise AssertionError("Private Engine truth must never be read")


class E2EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()
        cls.fixtures = {}
        layouts = (
            ("direct", 4, 1, frozenset({(1, 0)})),
            ("guess", 5, 1, frozenset({(1, 0), (2, 0)})),
            ("chord", 5, 4, frozenset({(1, 2), (3, 2)})),
            ("initial_loss", 4, 1, frozenset({(0, 0), (3, 0)})),
        )
        for index, (name, width, height, mines) in enumerate(layouts, 1):
            engine = MinesweeperEngine(width, height, len(mines))
            engine.reset_with_mines(width, height, len(mines), mines)
            raw = runner.run_k_p0(_PublicPort(engine), table=cls.table, capture_effects=True)
            arm = _arm(width, height, mines, index)
            projected = game.project_k_p0(raw, arm, table=cls.table)
            cls.fixtures[name] = raw, projected, adapter.PrivateFixedAnswer(arm, mines)

    def evaluate(self, name="direct"):
        raw, projected, answer = self.fixtures[name]
        return adapter.evaluate_k_p0(raw, projected, answer, raw_arm=projected.arm, table=self.table)

    def forged_identity(self, name, mines):
        """A false run declaration still binds internally; only truth refutes it."""
        raw, original, _ = self.fixtures[name]
        board = original.arm.board
        arm = _arm(board.width, board.height, mines, board.game_index)
        projected = game.project_k_p0(raw, arm, table=self.table)
        answer = adapter.PrivateFixedAnswer(arm, mines)
        return adapter.evaluate_k_p0(raw, projected, answer, raw_arm=arm, table=self.table)

    def category(self, result, category):
        return next(item for item in result if item.assertion is category)

    def test_complete_three_category_family_and_single_primitive_invocation(self):
        with patch.object(primitive, "evaluate_falsification", wraps=primitive.evaluate_falsification) as called:
            result = self.evaluate()
        self.assertEqual(called.call_count, 1)
        self.assertEqual(tuple(item.assertion for item in result), tuple(records.AssertionCategory))
        self.assertTrue(all(type(item) is records.EvaluatorRecord for item in result))
        sealed, answer = called.call_args.args
        self.assertEqual(answer.mines, self.fixtures["direct"][2].mines)
        self.assertEqual(answer.archive_digest, sealed.archive_digest)

    def test_logical_m_true_pass(self):
        result = self.category(self.evaluate(), records.AssertionCategory.LOGICAL_M)
        self.assertEqual(result.status, records.EvaluationStatus.PASS)
        self.assertEqual(result.targets, ((1, 0),))

    def test_logical_m_false_fails_without_upgrading(self):
        result = self.forged_identity("direct", frozenset({(3, 0)}))
        item = self.category(result, records.AssertionCategory.LOGICAL_M)
        self.assertEqual(item.status, records.EvaluationStatus.FAIL)
        self.assertEqual(item.reason_code, "ASSERTION_FALSIFIED")

    def test_certainty_open_safe_pass(self):
        item = self.category(self.evaluate(), records.AssertionCategory.CERTAINTY_OPEN)
        self.assertEqual(item.status, records.EvaluationStatus.PASS)

    def test_certainty_open_on_mine_fails(self):
        target = self.category(self.evaluate(), records.AssertionCategory.CERTAINTY_OPEN).targets[0]
        result = self.forged_identity("direct", frozenset({target}))
        self.assertEqual(self.category(result, records.AssertionCategory.CERTAINTY_OPEN).status,
                         records.EvaluationStatus.FAIL)

    def test_probability_guess_is_explicitly_excluded_from_certainty(self):
        raw, projected, _ = self.fixtures["guess"]
        guesses = tuple(trace for trace in raw.traces if trace.category == "EXACT_MINIMUM_RISK_GUESS")
        self.assertTrue(guesses)
        with patch.object(primitive, "evaluate_falsification", wraps=primitive.evaluate_falsification) as called:
            result = self.evaluate("guess")
        sealed = called.call_args.args[0]
        for trace in guesses:
            matching = tuple(item.assertion_type for item in sealed.assertions
                             if item.physical_input_boundary == trace.input_index)
            self.assertEqual(matching, ("LOGICAL_M", "EXACT_MINIMUM_RISK_GUESS"))
        targets = self.category(result, records.AssertionCategory.CERTAINTY_OPEN).targets
        self.assertTrue(all((t.move.x, t.move.y) not in targets for t in guesses))

    def test_chord_opened_safe_set_pass(self):
        result = self.category(self.evaluate("chord"), records.AssertionCategory.CERTAINTY_CHORD_OPENED)
        self.assertTrue(result.targets)
        self.assertEqual(result.status, records.EvaluationStatus.PASS)

    def test_corrupted_claimed_chord_safe_cell_fails(self):
        targets = self.category(self.evaluate("chord"), records.AssertionCategory.CERTAINTY_CHORD_OPENED).targets
        old = self.fixtures["chord"][2].mines
        mines = frozenset({next(iter(old)), targets[0]})
        result = self.forged_identity("chord", mines)
        self.assertEqual(self.category(result, records.AssertionCategory.CERTAINTY_CHORD_OPENED).status,
                         records.EvaluationStatus.FAIL)

    def test_initial_loss_still_calls_evaluator_and_returns_all_not_evaluated(self):
        with patch.object(primitive, "evaluate_falsification", wraps=primitive.evaluate_falsification) as called:
            result = self.evaluate("initial_loss")
        called.assert_called_once()
        self.assertEqual(len(result), 3)
        self.assertTrue(all(item.status is records.EvaluationStatus.NOT_EVALUATED for item in result))
        self.assertTrue(all(item.reason_code == "NO_ASSERTED_COORDINATES" for item in result))

    def test_terminal_answer_display_is_not_assertion_input(self):
        raw, _, _ = self.fixtures["initial_loss"]
        self.assertTrue(any(cell < 0 for row in raw.traces[-1].public_effect.after_observation.rows for cell in row))
        result = self.evaluate("initial_loss")
        self.assertTrue(all(not item.targets for item in result))

    def test_private_coordinates_and_truth_fields_absent_from_output(self):
        result = self.evaluate("initial_loss")
        text = repr(result) + b"".join(records.encode(item) for item in result).decode("utf-8")
        for forbidden in ("(3, 0)", "[3,0]", "hidden_mine", "answer_digest", "comparisons"):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("(3, 0)", repr(self.fixtures["initial_loss"][2]))

    def test_reason_codes_and_details_do_not_disclose_counterexample_coordinates(self):
        result = self.forged_identity("direct", frozenset({(3, 0)}))
        for item in result:
            self.assertNotIn("(3, 0)", item.detail)
            self.assertIn(item.reason_code, ("NO_COUNTEREXAMPLE", "ASSERTION_FALSIFIED", "NO_ASSERTED_COORDINATES"))

    def test_exact_arm_board_binding_and_deep_detachment(self):
        projected = self.fixtures["direct"][1]
        for item in self.evaluate():
            self.assertEqual(item.arm, projected.arm)
            self.assertIsNot(item.arm, projected.arm)
            self.assertIsNot(item.arm.board, projected.arm.board)
            self.assertEqual(records.decode(records.encode(item)), item)

    def test_frozen_slotted_closed_output_graph(self):
        def visit(value):
            if is_dataclass(value):
                self.assertTrue(type(value).__dataclass_params__.frozen)
                self.assertIn("__slots__", type(value).__dict__)
                self.assertFalse(hasattr(value, "__dict__"))
                for slot in fields(value):
                    visit(getattr(value, slot.name))
            elif type(value) in (tuple, frozenset):
                for item in value:
                    visit(item)
            else:
                self.assertTrue(type(value) in (str, int, bool, type(None)) or isinstance(value, Enum))
        result = self.evaluate("chord")
        visit(result)
        with self.assertRaises(FrozenInstanceError):
            result[0].detail = "changed"

    def test_explicit_private_answer_is_mandatory(self):
        raw, projected, _ = self.fixtures["direct"]
        for answer in (None, {}, frozenset({(1, 0)}), raw):
            with self.subTest(answer_type=type(answer)), self.assertRaises(adapter.E2EvaluatorError):
                adapter.evaluate_k_p0(raw, projected, answer, raw_arm=projected.arm, table=self.table)

    def test_private_answer_rejects_mutable_wrong_type_and_bad_coordinates(self):
        arm = self.fixtures["direct"][1].arm
        for mines in ({(1, 0)}, ((1, 0),), frozenset({(True, 0)}), frozenset({(-1, 0)}),
                      frozenset({(4, 0)}), frozenset({(1, 1)})):
            with self.subTest(mines=mines), self.assertRaises(adapter.E2EvaluatorError):
                adapter.PrivateFixedAnswer(arm, mines)

    def test_private_answer_count_mismatch_fails_closed(self):
        arm = self.fixtures["direct"][1].arm
        for mines in (frozenset(), frozenset({(1, 0), (2, 0)})):
            with self.assertRaisesRegex(adapter.E2EvaluatorError, "ANSWER_MINE_COUNT"):
                adapter.PrivateFixedAnswer(arm, mines)

    def test_private_answer_fingerprint_mismatch_fails_closed(self):
        arm = self.fixtures["direct"][1].arm
        with self.assertRaisesRegex(adapter.E2EvaluatorError, "ANSWER_FINGERPRINT_MISMATCH"):
            adapter.PrivateFixedAnswer(arm, frozenset({(2, 0)}))

    def test_private_answer_dimension_binding_fails_closed(self):
        _, projected, answer = self.fixtures["direct"]
        for dimension in ({"width": 5}, {"height": 2}):
            with self.assertRaisesRegex(adapter.E2EvaluatorError, "ANSWER_FINGERPRINT_MISMATCH"):
                adapter.PrivateFixedAnswer(replace(projected.arm, board=replace(projected.arm.board, **dimension)),
                                           answer.mines)

    def test_private_answer_arm_and_run_identity_must_match(self):
        raw, projected, answer = self.fixtures["direct"]
        for changed in ({"run_id": "another"}, {"unit_id": "another"},
                        {"board": replace(projected.arm.board, game_index=99)}):
            supplied = adapter.PrivateFixedAnswer(replace(answer.arm, **changed), answer.mines)
            with self.subTest(changed=changed), self.assertRaisesRegex(adapter.E2EvaluatorError, "ANSWER_EXECUTION"):
                adapter.evaluate_k_p0(raw, projected, supplied, raw_arm=projected.arm, table=self.table)

    def test_corrupted_private_answer_is_revalidated_at_use(self):
        raw, projected, answer = self.fixtures["direct"]
        bad = _corrupt(answer, mines=frozenset({(2, 0)}))
        with self.assertRaisesRegex(adapter.E2EvaluatorError, "ANSWER_FINGERPRINT"):
            adapter.evaluate_k_p0(raw, projected, bad, raw_arm=projected.arm, table=self.table)

    def test_control_and_other_arms_rejected(self):
        arm = self.fixtures["direct"][1].arm
        for other in (records.Arm.CONTROL, records.Arm.K_CONTROL):
            with self.assertRaises(adapter.E2EvaluatorError):
                adapter.PrivateFixedAnswer(replace(arm, arm=other), frozenset({(1, 0)}))

    def test_raw_identity_mandatory_and_exact(self):
        raw, projected, answer = self.fixtures["direct"]
        for arm in (None, answer, replace(projected.arm, unit_id="other"),
                    replace(projected.arm, board=replace(projected.arm.board, game_index=88))):
            with self.assertRaises(adapter.E2EvaluatorError):
                adapter.evaluate_k_p0(raw, projected, answer, raw_arm=arm, table=self.table)

    def test_raw_projection_rebinding_is_reused_without_solver_execution(self):
        raw, projected, answer = self.fixtures["direct"]
        with patch.object(game, "project_k_p0", wraps=game.project_k_p0) as called, \
                patch.object(runner, "run_k_p0", side_effect=AssertionError("reran solver")), \
                patch.object(game, "run_k_p0", side_effect=AssertionError("reran solver")):
            self.evaluate()
        called.assert_called_once_with(raw, projected.arm, table=self.table)

    def test_different_raw_result_cannot_bind(self):
        _, projected, answer = self.fixtures["direct"]
        raw = self.fixtures["guess"][0]
        with self.assertRaises(adapter.E2EvaluatorError):
            adapter.evaluate_k_p0(raw, projected, answer, raw_arm=projected.arm, table=self.table)

    def test_corrupted_raw_model_m_and_input_are_rejected(self):
        raw, projected, answer = self.fixtures["direct"]
        changes = (
            replace(raw, final_M=frozenset()),
            replace(raw, traces=(replace(raw.traces[0], modeled_action_us=1),) + raw.traces[1:]),
            replace(raw, traces=(replace(raw.traces[0], input_index=1),) + raw.traces[1:]),
        )
        for supplied in changes:
            with self.subTest(raw=supplied.status), self.assertRaises(adapter.E2EvaluatorError):
                adapter.evaluate_k_p0(supplied, projected, answer, raw_arm=projected.arm, table=self.table)

    def test_malformed_projection_does_not_reach_private_primitive(self):
        raw, projected, answer = self.fixtures["direct"]
        with patch.object(primitive, "evaluate_falsification", side_effect=AssertionError("should not evaluate")):
            for bad in (None, _corrupt(projected, total_model_us=1), _corrupt(projected, acquisitions=())):
                with self.assertRaises(adapter.E2EvaluatorError):
                    adapter.evaluate_k_p0(raw, bad, answer, raw_arm=projected.arm, table=self.table)

    def test_missing_effect_evidence_is_not_a_pass(self):
        raw, projected, answer = self.fixtures["direct"]
        missing = replace(raw, traces=tuple(replace(t, public_effect=None, public_effect_status="NOT_EVALUATED")
                                           for t in raw.traces))
        incomplete = game.project_k_p0(missing, projected.arm, table=self.table)
        self.assertFalse(incomplete.effect_evidence_complete)
        with self.assertRaisesRegex(adapter.E2EvaluatorError, "COMPLETE_EXECUTION_REQUIRED"):
            adapter.evaluate_k_p0(missing, incomplete, answer, raw_arm=projected.arm, table=self.table)

    def test_assertion_extraction_matches_accepted_harness_semantics(self):
        # Compare the actual accepted single-archive sealing primitive, without
        # any E1 suite, schedule, qualification or persistence reconstruction.
        from experiments import program_k_harness as harness
        for raw, _, _ in self.fixtures.values():
            archive = harness.ExecutionArchive("I5-differential-literal", "K-P0", raw)
            sealed = harness.seal_execution_archive(archive, run_id="I5-differential-literal")
            self.assertEqual(adapter._assertions(raw), sealed.assertions)

    def test_bad_primitive_result_binding_is_rejected(self):
        raw, projected, answer = self.fixtures["direct"]
        with patch.object(primitive, "evaluate_falsification", return_value=None):
            with self.assertRaises(adapter.E2EvaluatorError):
                adapter.evaluate_k_p0(raw, projected, answer, raw_arm=projected.arm, table=self.table)

    def test_primitive_returned_false_truth_bits_are_rejected(self):
        real = primitive.evaluate_falsification
        def corrupted(sealed, answer):
            finding = real(sealed, answer)
            items = list(finding.findings)
            index = next(i for i, item in enumerate(items) if item.comparisons)
            first = items[index].comparisons[0]
            changed = replace(first, hidden_mine=not first.hidden_mine)
            items[index] = replace(items[index], comparisons=(changed,) + items[index].comparisons[1:])
            return replace(finding, findings=tuple(items))
        with patch.object(primitive, "evaluate_falsification", side_effect=corrupted):
            with self.assertRaises(adapter.E2EvaluatorError):
                self.evaluate()

    def test_private_exception_text_is_not_forwarded(self):
        with patch.object(primitive, "evaluate_falsification", side_effect=ValueError("secret mine (3, 0)")):
            with self.assertRaisesRegex(adapter.E2EvaluatorError, "^MALFORMED_EVALUATOR_EVIDENCE$") as caught:
                self.evaluate()
        self.assertNotIn("secret", str(caught.exception))

    def test_no_scientific_verdict_is_exposed(self):
        for item in self.evaluate("chord"):
            self.assertFalse(hasattr(item, "progression_allowed"))
            self.assertFalse(hasattr(item, "research_progression_must_stop"))
            self.assertIn(item.status.value, {"PASS", "FAIL", "NOT_EVALUATED"})

    def test_exact_fingerprint_bytes_and_private_answer_repr(self):
        arm = _arm(4, 1, frozenset({(1, 0)}))
        self.assertEqual(adapter._layout_fingerprint(arm.board, frozenset({(1, 0)})), arm.board.fingerprint)
        answer = adapter.PrivateFixedAnswer(arm, frozenset({(1, 0)}))
        self.assertNotIn("mines=frozenset", repr(answer))

    def test_ast_dependency_and_purity_boundary(self):
        tree = ast.parse(inspect.getsource(adapter))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module)
                if node.module == "experiments":
                    self.assertTrue(all(item.name in {"program_k_e2_game", "program_k_e2_records",
                                                     "program_k_evaluator"} for item in node.names))
            elif isinstance(node, ast.Call):
                target = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else "")
                self.assertNotIn(target, {"open", "write", "write_text", "write_bytes", "Popen", "run_k_p0",
                                          "reset_with_mines", "generate_board", "connect", "system", "eval", "exec"})
        self.assertEqual(modules, {"dataclasses", "hashlib", "json", "struct", "core_engine", "experiments"})


if __name__ == "__main__":
    unittest.main()
