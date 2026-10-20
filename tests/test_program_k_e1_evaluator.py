"""E1 evaluator unit tests over manually declared 54-run public records.

No frozen scheduled entry is executed. Fixed-answer generation here exercises
only the adapter against invented archive/audit records, never research evidence.
"""

import ast
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
import hashlib
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

import benchmark_board as board
from core_engine import GameStatus, MinesweeperEngine
from experiments import program_k_capability as capability
from experiments import program_k_e1_audit as audit
from experiments import program_k_e1_evaluator as adapter
from experiments import program_k_e1_execution as execution
from experiments import program_k_e1_harness as e1
from experiments import program_k_e1_suite as suite
from experiments import program_k_evaluator as evaluator
from experiments import program_k_harness as harness
from experiments import program_k_policy as policy
from experiments import program_k_runner as runner
from tests.test_program_k_e1_audit import _corrupt
from tests.test_program_k_e1_suite import _data, _index, _manual_audit, _set


def _blocked_execution():
    stack = ExitStack()
    for module, name in (
            (execution, "execute_scheduled_entry"),
            (audit, "audit_scheduled_run"),
            (runner, "run_control_capture"), (runner, "run_k_control"),
            (runner, "run_k_p0"), (runner, "plan_position"),
            (policy, "select_policy"), (capability.KLocalSession, "analyze_decision"),
            (MinesweeperEngine, "__init__"), (MinesweeperEngine, "step")):
        stack.enter_context(patch.object(
            module, name, side_effect=AssertionError("Forbidden execution callback: " + name)))
    return stack


class E1EvaluatorAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with _blocked_execution():
            cls.plan, cls.archives, cls.audits = _data()
            cls.aggregate = suite.aggregate_e1_suite(cls.plan, cls.archives, cls.audits)
            cls.binding = cls.aggregate.bindings[_index()]
            cls.retained = adapter.evaluate_scheduled_kp0(
                cls.plan, cls.aggregate, cls.binding, evaluation_run_id="manual-unit")

    def evaluate(self, aggregate=None, binding=None, run_id="manual-unit"):
        return adapter.evaluate_scheduled_kp0(
            self.plan, self.aggregate if aggregate is None else aggregate,
            self.binding if binding is None else binding, evaluation_run_id=run_id)

    def test_exact_plan_and_complete_aggregate_required_before_truth(self):
        class PlanSubclass(e1.E1Plan):
            pass
        bad_plan = PlanSubclass(**{f.name: getattr(self.plan, f.name) for f in fields(self.plan)})
        for plan, aggregate in (
                (None, self.aggregate), (bad_plan, self.aggregate),
                (self.plan, None), (self.plan, self.archives),
                (self.plan, replace(self.aggregate, bindings=self.aggregate.bindings[:-1])),
                (self.plan, replace(self.aggregate, bindings=tuple(reversed(self.aggregate.bindings))))):
            with self.subTest(kind=type(aggregate).__name__), \
                    patch.object(adapter, "_fixed_answer") as truth:
                with self.assertRaises(ValueError):
                    adapter.evaluate_scheduled_kp0(
                        plan, aggregate, self.binding, evaluation_run_id="manual-unit")
                truth.assert_not_called()

    def test_only_kp0_and_exact_aggregate_member(self):
        wrong = (
            self.aggregate.bindings[0],
            replace(self.binding, archive_content_digest="1" * 64),
            replace(self.binding, schedule_entry=self.plan.schedule[_index(repetition=2)]),
            replace(self.binding, case=self.plan.cases[0]),
            self.binding.archive,
        )
        with patch.object(adapter, "_fixed_answer") as truth:
            for binding in wrong:
                with self.subTest(binding=type(binding).__name__), self.assertRaises(ValueError):
                    self.evaluate(binding=binding)
            truth.assert_not_called()

    def test_arbitrary_case_or_archive_override_is_not_an_api(self):
        for name, value in (("archive", self.binding.archive), ("case", self.binding.case)):
            with self.subTest(name=name), self.assertRaises(TypeError):
                adapter.evaluate_scheduled_kp0(
                    self.plan, self.aggregate, self.binding,
                    evaluation_run_id="manual-unit", **{name: value})

    def test_summary_tampering_and_compare_false_timing_drift_rejected(self):
        trace = self.binding.archive.result.traces[1]
        altered_trace = replace(
            trace, timings=replace(trace.timings, k_analysis_planning_ns=999))
        changed_archive = replace(
            self.binding.archive, result=replace(
                self.binding.archive.result,
                traces=_set(self.binding.archive.result.traces, 1, altered_trace)))
        changed_binding = replace(self.binding, archive=changed_archive)
        for aggregate, binding in (
                (replace(self.aggregate, suite_status="INCOMPLETE"), self.binding),
                (replace(self.aggregate, coverage=replace(
                    self.aggregate.coverage, archive_count=53)), self.binding),
                (self.aggregate, changed_binding),
                (replace(self.aggregate, bindings=_set(
                    self.aggregate.bindings, self.binding.schedule_entry.schedule_index,
                    changed_binding)), changed_binding)):
            with self.subTest(kind=binding.archive_content_digest), self.assertRaises(ValueError):
                self.evaluate(aggregate=aggregate, binding=binding)

    def test_nonterminal_or_empty_archive_cannot_prove_sequence(self):
        bound = self.aggregate.bindings[0]
        for changes in ({"traces": ()}, {"status": GameStatus.PLAYING}):
            damaged = _corrupt(bound.archive.result, control=_corrupt(
                bound.archive.result.control, **changes))
            bad_archive = _corrupt(bound.archive, result=damaged)
            incomplete = replace(self.aggregate, bindings=_set(
                self.aggregate.bindings, 0, replace(bound, archive=bad_archive)))
            with self.subTest(changes=changes), patch.object(adapter, "_fixed_answer") as truth:
                with self.assertRaisesRegex(ValueError, "Malformed scheduled result structure"):
                    self.evaluate(aggregate=incomplete)
                truth.assert_not_called()

    def test_incomplete_semantic_coverage_still_admits_complete_family(self):
        changed = tuple(replace(a, incomplete_reasons=("Manual coverage absent.",),
                                audit_status="INCOMPLETE") for a in self.audits)
        aggregate = suite.aggregate_e1_suite(self.plan, self.archives, changed)
        self.assertEqual(aggregate.suite_status, "INCOMPLETE")
        finding = self.evaluate(
            aggregate=aggregate, binding=aggregate.bindings[self.binding.schedule_entry.schedule_index])
        self.assertEqual(finding.classification, "NO_COUNTEREXAMPLE")
        self.assertFalse(finding.proof_upgrade_allowed)
        self.assertEqual(aggregate.suite_status, "INCOMPLETE")

    def test_semantic_failure_is_not_admitted_as_an_eligible_suite(self):
        changed = tuple(replace(a, discrepancies=("Manual failure.",), audit_status="FAIL")
                        for a in self.audits)
        aggregate = suite.aggregate_e1_suite(self.plan, self.archives, changed)
        self.assertEqual(aggregate.suite_status, "FAIL")
        with patch.object(adapter, "_fixed_answer") as truth, self.assertRaises(ValueError):
            self.evaluate(aggregate=aggregate, binding=aggregate.bindings[_index()])
        truth.assert_not_called()

    def test_synthetic_exact_answer_and_existing_evaluator_reused(self):
        with patch.object(board, "generate_board", side_effect=AssertionError("Synthetic generation")), \
                patch.object(evaluator, "evaluate_falsification",
                             wraps=evaluator.evaluate_falsification) as compare, \
                patch.object(evaluator, "verify_bound_finding",
                             wraps=evaluator.verify_bound_finding) as verify:
            finding = self.evaluate()
        compare.assert_called_once()
        verify.assert_called_once()
        sealed, answer = compare.call_args.args
        self.assertEqual(answer.mines, frozenset(e1._definition("S-LIFECYCLE").mine_positions))
        self.assertEqual(answer.num_mines, self.binding.case.num_mines)
        self.assertEqual(answer.archive_digest, sealed.archive_digest)
        self.assertEqual(finding.answer_digest, answer.answer_digest)
        self.assertEqual(finding.archive_content_digest, self.binding.archive_content_digest)
        self.assertEqual(finding.board_fingerprint, self.binding.case.board_fingerprint)
        self.assertEqual(finding.classification, "NO_COUNTEREXAMPLE")
        self.assertFalse(finding.finding.proof_upgrade_allowed)

    def test_expert_exact_generator_index_seed_fingerprint_and_single_call(self):
        bound = self.aggregate.bindings[_index(case="X-100000")]
        with patch.object(board, "generate_board", wraps=board.generate_board) as generate, \
                patch.object(evaluator, "verify_bound_finding",
                             wraps=evaluator.verify_bound_finding) as verify:
            retained = self.evaluate(binding=bound)
        generate.assert_called_once_with(board.EXPERT_GENERAL_V1, 100000)
        answer = verify.call_args.args[2]
        self.assertEqual(len(answer.mines), 99)
        self.assertNotIn((0, 0), answer.mines)
        self.assertEqual(board.calculate_board_fingerprint(
            answer.width, answer.height, answer.num_mines, answer.mines), bound.case.board_fingerprint)
        self.assertEqual(retained.answer_digest, answer.answer_digest)

    def test_wrong_expert_seed_index_and_fingerprint_rejected_without_retry(self):
        bound = self.aggregate.bindings[_index(case="X-0")]
        generated = board.generate_board(board.EXPERT_GENERAL_V1, 0)
        for bad in (replace(generated, seed=1), replace(generated, game_index=1),
                    replace(generated, board_fingerprint="1" * 64)):
            with self.subTest(seed=bad.seed), patch.object(
                    board, "generate_board", return_value=bad) as generate, \
                    patch.object(evaluator, "evaluate_falsification") as compare:
                with self.assertRaises(ValueError):
                    self.evaluate(binding=bound)
                generate.assert_called_once_with(board.EXPERT_GENERAL_V1, 0)
                compare.assert_not_called()

    def test_wrong_same_size_expert_layout_rejected_even_with_expected_fingerprint(self):
        bound = self.aggregate.bindings[_index(case="X-0")]
        generated = board.generate_board(board.EXPERT_GENERAL_V1, 0)
        removed = next(iter(generated.mine_positions))
        added = next((x, y) for y in range(16) for x in range(30)
                     if (x, y) not in generated.mine_positions and (x, y) != (0, 0))
        wrong = replace(generated, mine_positions=(generated.mine_positions - {removed}) | {added})
        with patch.object(board, "generate_board", return_value=wrong) as generate, \
                patch.object(evaluator, "evaluate_falsification") as compare:
            with self.assertRaises(ValueError):
                self.evaluate(binding=bound)
            generate.assert_called_once()
            compare.assert_not_called()

    def test_expert_first_click_mine_and_count_and_spec_drift_rejected(self):
        bound = self.aggregate.bindings[_index(case="X-0")]
        generated = board.generate_board(board.EXPERT_GENERAL_V1, 0)
        removed = next(iter(generated.mine_positions))
        variants = (replace(generated, mine_positions=generated.mine_positions - {removed}),
                    replace(generated, mine_positions=(generated.mine_positions - {removed}) | {(0, 0)}))
        for bad in variants:
            with self.subTest(count=len(bad.mine_positions)), patch.object(
                    board, "generate_board", return_value=bad), self.assertRaises(ValueError):
                self.evaluate(binding=bound)
        with patch.object(board, "EXPERT_GENERAL_V1",
                          replace(board.EXPERT_GENERAL_V1, num_mines=98)), \
                patch.object(board, "generate_board") as generate, self.assertRaises(ValueError):
            self.evaluate(binding=bound)
        generate.assert_not_called()

    def test_synthetic_same_size_layout_and_first_click_drift_rejected(self):
        original = e1._definition
        for mines in (((2, 0),), ((0, 0),)):
            def altered(case_id):
                definition = original(case_id)
                return replace(definition, mine_positions=mines) if case_id == "S-LIFECYCLE" else definition
            with self.subTest(mines=mines), patch.object(e1, "_definition", side_effect=altered), \
                    patch.object(evaluator, "evaluate_falsification") as compare:
                with self.assertRaises(ValueError):
                    self.evaluate()
                compare.assert_not_called()

    def test_generator_failure_has_no_retry_or_substitution(self):
        bound = self.aggregate.bindings[_index(case="X-2")]
        with patch.object(board, "generate_board", side_effect=ValueError("Injected failure")) as generate:
            with self.assertRaises(adapter.E1EvaluatorError):
                self.evaluate(binding=bound)
        generate.assert_called_once_with(board.EXPERT_GENERAL_V1, 2)

    def test_g1_falsification_retained_using_accepted_comparator(self):
        archives, audits = self.archives, self.audits
        for repetition in (1, 2):
            index = _index(repetition=repetition)
            old = archives[index]
            owned = frozenset({(0, 0), (1, 0)})  # Deliberate false public assertion.
            traces = tuple(replace(t, M_before=owned, preinput_M=owned)
                           if t.input_index else t for t in old.result.traces)
            archive = replace(old, result=replace(old.result, traces=traces, final_M=owned))
            archives = _set(archives, index, archive)
            audits = _set(audits, index, _manual_audit(archive, audits[index].source_identity))
        aggregate = suite.aggregate_e1_suite(self.plan, archives, audits)
        finding = self.evaluate(aggregate=aggregate, binding=aggregate.bindings[_index()])
        self.assertEqual(finding.classification, "G1_FALSIFICATION")
        self.assertTrue(finding.finding.research_progression_must_stop)
        self.assertFalse(finding.proof_upgrade_allowed)
        self.assertEqual(aggregate.suite_status, "PASS")  # No public record repaired or upgraded.

    def test_not_evaluated_is_retained_without_a_proof_claim(self):
        finding = self.evaluate(binding=self.aggregate.bindings[_index(case="S-WIN")])
        self.assertEqual(finding.classification, "NOT_EVALUATED")
        self.assertEqual(finding.finding.evaluated_coordinate_count, 0)
        self.assertFalse(finding.proof_upgrade_allowed)

    def test_no_solver_engine_or_public_audit_callbacks_and_no_mutation(self):
        before = suite._content_digest(self.aggregate)
        with _blocked_execution():
            result = self.evaluate()
            adapter.verify_e1_finding(self.plan, self.aggregate, self.binding, result)
        self.assertEqual(suite._content_digest(self.aggregate), before)

    def test_no_execution_callback_after_truth_has_been_constructed(self):
        original = adapter._fixed_answer
        with ExitStack() as stack:
            def answer_then_block(case, sealed):
                answer = original(case, sealed)
                stack.enter_context(_blocked_execution())
                return answer
            stack.enter_context(patch.object(adapter, "_fixed_answer", side_effect=answer_then_block))
            finding = self.evaluate()
        self.assertEqual(finding.classification, "NO_COUNTEREXAMPLE")

    def test_truth_free_parent_verification_and_exact_run_identity(self):
        verified_digest = suite._content_digest(self.aggregate)
        with patch.object(board, "generate_board", side_effect=AssertionError("Parent truth")), \
                patch.object(adapter, "_fixed_answer", side_effect=AssertionError("Parent answer")), \
                patch.object(evaluator, "evaluate_falsification", side_effect=AssertionError("Parent evaluation")), \
                patch.object(evaluator, "verify_bound_finding", side_effect=AssertionError("Parent hidden check")):
            self.assertEqual(adapter.verify_e1_finding(
                self.plan, self.aggregate, self.binding, self.retained,
                evaluation_run_id="manual-unit"), self.retained)
            with self.assertRaises(ValueError):
                adapter.verify_e1_finding(
                    self.plan, self.aggregate, self.binding, self.retained,
                    evaluation_run_id="another-operation")
            with patch.object(suite, "_content_digest", side_effect=AssertionError("Repeated suite hashing")):
                self.assertEqual(adapter._verify_admitted_finding(
                    self.plan, self.aggregate, self.binding, self.retained, "manual-unit",
                    suite_content_digest=verified_digest), self.retained)
                with self.assertRaises(ValueError):
                    adapter._verify_admitted_finding(
                        self.plan, self.aggregate, self.binding, self.retained, "manual-unit",
                        suite_content_digest="1" * 64)

    def test_wrong_archive_answer_suite_source_and_schedule_digest_rejected(self):
        for changes in (
                {"archive_content_digest": "1" * 64},
                {"answer_digest": "1" * 64},
                {"sealed_archive_digest": "1" * 64},
                {"suite_content_digest": "1" * 64},
                {"suite_source_digest": "1" * 64},
                {"board_fingerprint": "1" * 64},
                {"evaluator_source_sha256": "1" * 64},
                {"schedule_index": _index(repetition=2), "repetition": 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                adapter.verify_e1_finding(
                    self.plan, self.aggregate, self.binding, _corrupt(self.retained, **changes))

    def test_diagnostic_coverage_and_accepted_verifier_failure_are_not_suppressed(self):
        for calls in ((), (self.retained.evaluator_calls[0],) * 2,
                      (replace(self.retained.evaluator_calls[0], answer_digest="1" * 64),)):
            with self.subTest(length=len(calls)), self.assertRaises(ValueError):
                adapter.canonical_bytes(_corrupt(self.retained, evaluator_calls=calls))
        with patch.object(evaluator, "verify_bound_finding", side_effect=ValueError("Wrong bound answer")) as verify:
            with self.assertRaises(adapter.E1EvaluatorError):
                self.evaluate()
        verify.assert_called_once()

    def test_finding_is_frozen_detached_and_contains_no_complete_answer(self):
        allowed = {adapter.E1EvaluatorFinding, evaluator.FalsificationResult,
                   evaluator.SealedEvaluatorInput, evaluator.ArchivedAssertion,
                   evaluator.AssertionFinding, evaluator.CoordinateComparison,
                   evaluator.EvaluatorCallDiagnostic}
        def visit(value):
            if type(value) in (str, int, bool, type(None)):
                return
            if type(value) is tuple:
                for item in value:
                    visit(item)
                return
            self.assertIn(type(value), allowed)
            self.assertTrue(is_dataclass(value))
            self.assertTrue(value.__dataclass_params__.frozen)
            self.assertFalse(hasattr(value, "__dict__"))
            for field in fields(value):
                self.assertNotIn(field.name, ("mines", "mine_positions", "engine", "callback"))
                visit(getattr(value, field.name))
        visit(self.retained)
        with self.assertRaises(FrozenInstanceError):
            self.retained.case_id = "different"
        with self.assertRaises(AttributeError):
            object.__setattr__(self.retained, "answer", object())

    def test_runtime_identity_exact_bytes_and_stable_integrity_encoding(self):
        source = Path(adapter.__file__).read_bytes()
        self.assertEqual((self.retained.evaluator_source_sha256,
                          self.retained.evaluator_source_size_bytes),
                         (hashlib.sha256(source).hexdigest(), len(source)))
        raw = adapter.canonical_bytes(self.retained)
        self.assertEqual(raw, adapter.canonical_bytes(replace(self.retained)))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), adapter.content_digest(self.retained))
        self.assertNotIn(b"tests/test_program_k_e1_evaluator.py", raw)
        with patch.object(adapter, "_source_identity", return_value=("1" * 64, len(source))):
            with self.assertRaises(ValueError):
                adapter.verify_e1_finding(self.plan, self.aggregate, self.binding, self.retained)

    def test_ast_has_no_execution_or_persistence_or_falsification_reimplementation(self):
        tree = ast.parse(inspect.getsource(adapter))
        calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        for forbidden in ("execute_scheduled_entry", "audit_scheduled_run", "run_k_p0",
                          "run_k_control", "run_control_capture", "select_policy",
                          "analyze_decision", "step", "write_bytes", "write_text"):
            self.assertFalse(any(name.split(".")[-1] == forbidden for name in calls), forbidden)
        self.assertIn("_evaluator.evaluate_falsification", calls)
        self.assertIn("_evaluator.verify_bound_finding", calls)
        self.assertNotIn("_evaluator.CoordinateComparison", calls)
        self.assertNotIn("_evaluator.AssertionFinding", calls)
        self.assertEqual(sum(name == "_board.generate_board" for name in calls), 1)


if __name__ == "__main__":
    unittest.main()
