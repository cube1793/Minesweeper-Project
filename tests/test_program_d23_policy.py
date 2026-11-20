"""S3D23-A selection: one K-LC1 record, then the accepted S3D2-A or S3D3-A adapter by the kind of decision.

Kinds of material, kept apart on purpose:
  * real K decisions on tiny DECLARED public observations (a fresh KLocalSession analyses the
    grid; no Engine, no M injection): X01 (LOCAL_SAFE) and X02 (EXACT_SAFE) of the accepted S3D2-A
    tests, and GUESS_8X2, the public state before the guess of the 8x2 game of test_b02;
  * declared native records of the accepted S3D2-A tests (s1): arithmetic fixtures, no K inference.
The comparison unit is ONE decision: the same original K-LC1 record handed to the combined
selection and to the accepted adapter directly. Whole games are in the execution tests.
No Engine is built here (planned engine builds: 0). Results are functional checks, not evidence
about win rate.
"""

import ast
from dataclasses import replace
from fractions import Fraction
import inspect
import unittest
from unittest.mock import patch

from core_engine import GameStatus
from experiments import program_d23_policy as P
from experiments import program_d2_opening_policy as d2
from experiments import program_d3_lookahead_policy as d3
from experiments import program_k_lc1_policy as lc1
from experiments.program_k_capability import KLocalSession
from experiments.program_k_policy import KPolicyIntegrityError
from stage3_physical import load_timing_table
from tests import test_program_d2_opening as D2T


H, PLAYING, O = D2T.H, GameStatus.PLAYING, D2T.O
HALF = Fraction(1, 2)
# The public state right before the guess of the 8x2 game with one mine in column 3 (declared).
GUESS_8X2 = ((0, 0, 1, H, 1, 0, 0, 0), (0, 0, 1, H, 1, 0, 0, 0))
ENGINES_PLANNED = 0


class CombinedPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def decide(self, observation, mines, cursor):
        """A fresh session's decision and ONE K-LC1 record of it."""
        session = KLocalSession(len(observation[0]), len(observation), mines)
        decision = session.analyze_decision(observation, status=PLAYING)
        return session, decision, lc1.select_singleton_policy(decision, cursor, self.table)

    def certain(self):
        return self.decide(D2T.X02, 1, (0, 0))

    def guess(self):
        return self.decide(GUESS_8X2, 1, (5, 0))

    def refused(self, value, code="COMBINED_SELECTION"):
        with self.assertRaises(KPolicyIntegrityError) as caught:
            P.validate_combined_selection(value, self.table)
        self.assertEqual(caught.exception.code, code)

    def test_p01_a_certain_decision_takes_the_d2_branch_with_the_d2_adapter_result(self):
        for observation, mines, cursor, continuation, move in (
                (D2T.X01, 1, (0, 1), "LOCAL_SAFE", O(2, 1)), (D2T.X02, 1, (0, 0), "EXACT_SAFE", O(5, 0))):
            with self.subTest(continuation=continuation):
                _, decision, inner = self.decide(observation, mines, cursor)
                c = P.apply_combined(inner, self.table)
                self.assertEqual((decision.continuation, c.branch, c.guess), (continuation, P.BRANCH_CERTAIN, None))
                # The same original record handed to the accepted adapter gives the same record.
                self.assertEqual(c.opening, d2.apply_proven_opening(inner))
                self.assertIs(c.opening.inner, inner)
                self.assertEqual((c.move, c.category, c.opening.reason),
                                 (move, "PROVEN_OPENING_OPEN", "PROVEN_OPENING_OVERRIDE"))
                self.assertIs(c.record, c.opening)
                P.validate_combined_selection(c, self.table)

    def test_p02_a_guess_decision_takes_the_d3_branch_with_the_d3_adapter_result(self):
        _, decision, inner = self.guess()
        c = P.apply_combined(inner, self.table)
        self.assertEqual((decision.continuation, decision.guess_target, c.branch, c.opening),
                         ("EXACT_GUESS", (3, 0), P.BRANCH_GUESS, None))
        self.assertEqual(c.guess, d3.apply_lookahead(inner, self.table))
        self.assertIs(c.guess.inner, inner)
        self.assertIs(c.record, c.guess)
        g = c.guess
        # Three different things: the D3 branch was taken, the pair pre-emption rule decided,
        # and the actual target did NOT change (it is the K-LC1 target).
        self.assertEqual((g.selection_reason, g.evidence.kind, g.target, g.original_target, g.target_changed),
                         ("FORCED_5050_FIRST", "FORCED_5050", (3, 0), (3, 0), False))
        self.assertEqual((g.lookahead_status, g.lookahead_set, g.lookahead_cells, g.planned_calls, g.actual_calls,
                          g.rank_basis), ("COMPUTED", "FORCED_PAIR_CELLS", ((3, 0), (3, 1)), 4, 4, "S_COST_READING"))
        self.assertEqual(g.ranking, (((3, 0), HALF, 180604), ((3, 1), HALF, 193056)))
        self.assertEqual([(p.a, p.b, p.verdict) for p in g.pair_proofs], [((3, 0), (3, 1), "FORCED_5050")])
        self.assertEqual((c.move, c.category), (inner.selected.move, "EXACT_MINIMUM_RISK_GUESS"))
        P.validate_combined_selection(c, self.table)

    def test_p03_one_original_selection_and_one_adapter_per_decision(self):
        again = AssertionError("a second K-LC1 selection of the same decision")
        for name, (observation, mines, cursor), expected in (
                ("certain", (D2T.X02, 1, (0, 0)), (1, 1, 0)), ("guess", (GUESS_8X2, 1, (5, 0)), (1, 0, 1))):
            with self.subTest(decision=name):
                session = KLocalSession(len(observation[0]), len(observation), mines)
                decision = session.analyze_decision(observation, status=PLAYING)
                with patch.object(P, "select_singleton_policy", wraps=P.select_singleton_policy) as original, \
                        patch.object(d2, "apply_proven_opening", wraps=d2.apply_proven_opening) as opening, \
                        patch.object(d3, "apply_lookahead", wraps=d3.apply_lookahead) as lookahead, \
                        patch.object(d2, "select_singleton_policy", side_effect=again), \
                        patch.object(d3, "select_singleton_policy", side_effect=again), \
                        patch.object(d2, "select_opening_policy", side_effect=again), \
                        patch.object(d3, "select_lookahead_policy", side_effect=again), \
                        patch.object(KLocalSession, "analyze_decision",
                                     side_effect=AssertionError("the selection must not analyse")):
                    c = P.select_combined_policy(decision, cursor, self.table)
                self.assertEqual((original.call_count, opening.call_count, lookahead.call_count), expected)
                self.assertIs(c.inner.native.evidence, decision)
                self.assertIs(c.record.inner, c.inner)

    def test_p04_the_original_selection_is_kept_apart_from_the_actual_input(self):
        _, decision, inner = self.certain()
        before = (inner.native, inner.baseline, inner.selected, inner.assessments, inner.reason)
        c = P.apply_combined(inner, self.table)
        self.assertIs(c.inner, inner)
        self.assertEqual((inner.native, inner.baseline, inner.selected, inner.assessments, inner.reason), before)
        lc1.validate_singleton_selection(c.inner)  # the K-LC1 record is untouched
        # The original K-LC1 input and the actual input are two different things.
        self.assertEqual((c.inner.selected.move, c.move), (O(4, 0), O(5, 0)))
        self.assertTrue(c.input_changed)
        self.assertIsNone(c.selected)
        self.assertEqual((c.policy_id, c.policy_definition, c.inner.policy_id),
                         ("S3D23-A", "K_LC1_THEN_D2_CERTAIN_OR_D3_GUESS_V1", "K-LC1"))

    def test_p05_a_kept_choice_is_the_k_lc1_selection_object_itself(self):
        native, _ = D2T.s1(140, 500, 510)  # declared arithmetic: the gain condition fails
        inner = lc1.apply_singleton_band(native)
        kept = P.apply_combined(inner, self.table)
        self.assertEqual((kept.branch, kept.opening.applied, kept.opening.reason, kept.input_changed),
                         (P.BRANCH_CERTAIN, None, "NO_ELIGIBLE_OPENING", False))
        self.assertIs(kept.selected, inner.selected)
        self.assertIs(kept.move, inner.selected.move)
        _, _, guess_inner = self.guess()
        g = P.apply_combined(guess_inner, self.table)
        self.assertFalse(g.input_changed)
        self.assertIs(g.selected, guess_inner.selected)
        self.assertIs(g.move, guess_inner.selected.move)

    def test_p06_a_pruned_native_candidate_may_be_the_actual_input(self):
        _, decision, inner = self.certain()  # a real EXACT_SAFE decision
        c = P.apply_combined(inner, self.table)
        applied = c.opening.applied
        self.assertFalse(applied.native_survivor)
        self.assertNotIn(applied.candidate, inner.native.survivors)
        self.assertIn(applied.candidate, inner.native.candidates)  # an ORIGINAL candidate, before pruning
        P.validate_combined_selection(c, self.table)
        native, (o4, o5, o6) = D2T.s1()  # declared arithmetic
        declared = P.apply_combined(lc1.apply_singleton_band(native), self.table)
        self.assertEqual((declared.opening.applied.candidate, declared.move), (o5, O(5, 0)))
        self.assertNotIn(o5, native.survivors)
        self.assertEqual(declared.inner.native.candidates, native.candidates)

    def test_p07_mismatched_branch_record_inner_move_or_category_is_rejected(self):
        _, decision, inner = self.certain()
        c = P.apply_combined(inner, self.table)
        _, _, guess_inner = self.guess()
        g = P.apply_combined(guess_inner, self.table)
        twin = lc1.select_singleton_policy(decision, (0, 0), self.table)  # equal, but another object
        self.assertIsNot(twin, inner)
        wrong = {
            "branch of the other kind": replace(c, branch=P.BRANCH_GUESS),
            "unknown branch": replace(c, branch="OTHER"),
            "no record at all": replace(c, opening=None),
            "two records (certain)": replace(c, guess=g.guess),
            "two records (guess)": replace(g, opening=c.opening),
            "guess without its record": replace(g, guess=None),
            "record of the other branch": replace(c, opening=None, guess=g.guess),
            "record made from another original selection": replace(c, inner=twin),
            "another move": replace(c, move=O(4, 0)),
            "another category": replace(c, category="DIRECT_SAFE_OPEN"),
            "guess with another move": replace(g, move=O(3, 1)),
            "not a combined record": c.opening,
        }
        for name, value in wrong.items():
            with self.subTest(case=name):
                self.refused(value)
        self.assertEqual(len(wrong), 12)
        P.validate_combined_selection(c, self.table)  # the untouched records still pass
        P.validate_combined_selection(g, self.table)

    def test_p08_an_unknown_continuation_is_an_error_and_calls_no_adapter(self):
        _, decision, inner = self.certain()
        odd = replace(inner, native=replace(inner.native, evidence=replace(decision, continuation="NOT_REACHED")))
        self.assertEqual(odd.native.continuation, "NOT_REACHED")
        called = AssertionError("no adapter may be called")
        with patch.object(d2, "apply_proven_opening", side_effect=called), \
                patch.object(d3, "apply_lookahead", side_effect=called):
            for value in (odd, inner.native, None, "EXACT_GUESS"):
                with self.subTest(value=type(value).__name__):
                    with self.assertRaises(KPolicyIntegrityError) as caught:
                        P.apply_combined(value, self.table)
                    self.assertEqual(caught.exception.code, "COMBINED_SELECTION")

    def test_p09_adapter_errors_propagate_and_are_not_replaced_by_k_lc1(self):
        _, _, inner = self.certain()
        _, _, guess_inner = self.guess()
        fault = KPolicyIntegrityError("PROVEN_OPENING_SELECTION", "fault")
        with patch.object(d2, "apply_proven_opening", side_effect=fault):
            with self.assertRaises(KPolicyIntegrityError) as caught:
                P.apply_combined(inner, self.table)
        self.assertIs(caught.exception, fault)
        with patch.object(d3, "apply_lookahead", side_effect=RuntimeError("fault")):
            with self.assertRaises(RuntimeError):
                P.apply_combined(guess_inner, self.table)
        # A broken original record is refused by the adapter's own validation, not kept.
        broken = replace(inner, baseline=None)
        with self.assertRaises(KPolicyIntegrityError):
            P.apply_combined(broken, self.table)

    def test_p10_the_composition_identifier_is_its_own(self):
        self.assertEqual((P.COMPOSITION_ID, P.COMPOSITION_DEFINITION),
                         ("S3D23-A", "K_LC1_THEN_D2_CERTAIN_OR_D3_GUESS_V1"))
        self.assertNotIn(P.COMPOSITION_ID, (lc1.POLICY_ID, d2.CANDIDATE_ID, d3.CANDIDATE_ID, "K", "K-P0", "K-LC0"))
        self.assertEqual((lc1.POLICY_ID, d2.CANDIDATE_ID, d3.CANDIDATE_ID), ("K-LC1", "S3D2-A", "S3D3-A"))
        self.assertEqual(P.PARTS, (
            ("CERTAIN_D2", "S3D2-A", "PROVEN_OPENING_V1", None),
            ("GUESS_D3", "S3D3-A", "GUESS_STRUCTURE_V1", "FORCED_PAIR_AND_TIE_LOOKAHEAD_V1")))
        # The accepted limits are those of the accepted modules; this module defines none.
        self.assertEqual((d3.CELL_LIMIT, d3.CALL_LIMIT), (8, 72))
        self.assertFalse(any(name in vars(P) for name in ("CELL_LIMIT", "CALL_LIMIT", "PSEUDO_CALL_LIMIT")))

    def test_p11_the_module_selects_through_the_two_adapters_only(self):
        tree = ast.parse(inspect.getsource(P))
        used = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in ("d2", "d3"):
                used.setdefault(node.value.id, set()).add(node.attr)
        self.assertEqual(used, {
            "d2": {"CANDIDATE_ID", "CANDIDATE_DEFINITION", "OpeningSelection", "apply_proven_opening",
                   "validate_opening_selection"},
            "d3": {"CANDIDATE_ID", "CANDIDATE_DEFINITION", "IMPLEMENTATION_SCOPE", "LookaheadSelection",
                   "apply_lookahead", "validate_lookahead_selection"}})
        imported = sorted(alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                          for alias in node.names)
        self.assertEqual(imported, sorted([
            "dataclass", "program_d2_opening_policy", "program_d3_lookahead_policy", "SingletonSelection",
            "select_singleton_policy", "KPolicyIntegrityError", "SimpleMove"]))
        self.assertFalse([node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.Global, ast.Nonlocal))])
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertFalse(names & {"select_opening_policy", "select_lookahead_policy", "KLocalSession",
                                  "calculate_probabilities", "MinesweeperEngine"})
        functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
        self.assertEqual(functions, ["_require", "branch_of", "apply_combined", "select_combined_policy",
                                     "check_combined_shape", "validate_combined_selection"])


if __name__ == "__main__":
    unittest.main()
