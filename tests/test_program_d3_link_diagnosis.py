"""PAIR_BUNDLE_RESOLUTION_DIAGNOSIS_V1: the linked resolution diagnosis against hand-written cases.

Kinds of evidence, kept apart on purpose:
  * DECLARED PREMISES (c, s, i, m01, m03, m04): grid, M and mine total of a hand-written case are
    declared; the diagnosis and the accepted exact kernel calculate on them. This is no K inference.
    The cases are the byte copy of the design's LINKED_CASES.json (LC01..LC09) and the addendum
    written before this module (LA01, LA02), read from <output root>/cases. Every expected value
    was fixed by hand beforehand; none was taken from a run.
  * REAL K DECISIONS ON PREFIX STATES (m02, r01, r03): legal public OPEN inputs are sent through the
    input-cap proxy to a fixed tiny Engine, a fresh KLocalSession analyses the resulting grid, and
    the unchanged policies select. Neither Engine state nor M is injected. They are not autonomous
    runs from the first input.
  * ENGINE FLOOD ROWS (r02): what a real Engine reveals with ONE input, compared with the number 0
    hypothesis. The calculation on those rows keeps the declared M.
  * FAKE SEAM (i01..i03): the module's one kernel seam is replaced to reach the error boundaries.
The hidden layout is used only to build an Engine. Every Engine is built by ``self.build`` and each
test asserts the number of Engines it built (tearDown). No seed search, no generated board, no public
Expert board. Results are functional checks and no evidence about win rate.
"""

import ast
from dataclasses import fields, replace
from fractions import Fraction
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import simple_probability
from core_engine import Action, CellState, GameStatus
from experiments import program_d23_policy as P
from experiments import program_d3_forced_pair_policy as stage1
from experiments import program_d3_link_diagnosis as L
from experiments import program_d3_lookahead_policy as d3
from experiments import program_d3_pseudo_diagnosis as pseudo
from experiments.program_k_capability import KLocalSession, reading_order
from experiments.program_k_policy import KPolicyIntegrityError
from simple_algorithm import InconsistentObservationError
from stage3_physical import load_timing_table
from tests import test_program_d3_recorded_runner as RR


# 손 사례는 제품 저장소 안의 고정 자료 폴더에 있다(출력 폴더의 cases에서 옮겼다).
CASE_FOLDER = Path(__file__).resolve().parent / "fixtures" / "program_d3_explanation"
H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)
PLAYING = GameStatus.PLAYING
FORCED_FIRST, TIE, KEPT = "FORCED_5050_FIRST", "TIE_LOOKAHEAD", "K_LC1_GUESS_KEPT"
ALL = ("LC01", "LC02", "LC03", "LC04", "LC05", "LC06", "LC07", "LC08", "LC09", "LA01", "LA02")
WITH_WORLDS = tuple(name for name in ALL if name != "LC08")
# The declared selection reason of each case (an input of the diagnosis, not an expectation of it).
REASONS = {"LC01": TIE, "LC02": FORCED_FIRST, "LC03": FORCED_FIRST, "LC04": KEPT, "LC05": TIE, "LC06": TIE,
           "LC07": KEPT, "LC08": KEPT, "LC09": KEPT, "LA01": KEPT, "LA02": KEPT}
RECORD_CODES = ("LINK_RECORD", "LINK_WORLD_COUNT", "LINK_CALL_COUNT")
ENGINES = {
    "test_m02_a_real_session_does_not_guess_when_the_mine_total_reveals_a_safe_cell": 3,
    "test_r01_lc09_as_a_real_k_decision_gives_the_declared_premises_and_the_hand_plan": 1,
    "test_r02_the_real_flood_shows_more_than_the_number_zero_hypothesis": 4,
    "test_r03_a_decision_that_is_no_guess_gets_no_diagnosis": 1,
}
FIX = {}


def setUpModule():
    original = json.loads((CASE_FOLDER / "LINKED_CASES.json").read_text(encoding="utf-8"))
    addendum = json.loads((CASE_FOLDER / "LINKED_CASES_ADDENDUM.json").read_text(encoding="utf-8"))
    FIX["cases"] = {case["id"]: case for case in original["cases"] + addendum["cases"]}
    FIX["addendum"] = addendum
    FIX["table"] = load_timing_table()


def cell(value):
    return (value[0], value[1])


def O(x, y):
    return RR.O(x, y)


def grid_of(case):
    """The declared grid: H hidden, F a declared mine shown as a flag, digits revealed numbers."""
    return tuple(tuple(H if token == "H" else F if token == "F" else int(token) for token in row.split())
                 for row in case["grid"])


def public_grid(case):
    """What a real Engine shows for the same state: the declared mines are still hidden."""
    return tuple(tuple(H if token in ("H", "F") else int(token) for token in row.split()) for row in case["grid"])


def rows_grid(rows):
    return tuple(tuple(H if token == "H" else int(token) for token in row.split()) for row in rows)


def named(case):
    return {name: cell(value) for name, value in case["cells"].items()}


def declared_counts(case):
    cells = named(case)
    return {cells[name]: count for name, count in case["mine_worlds"].items()}


def premises_of(case, num_mines=None, total=None, counts=None):
    unresolved = frozenset(named(case).values())
    counts = declared_counts(case) if counts is None else counts
    original = cell(case["plan_expected"]["original_target"])
    return d3.GuessPremises(
        grid_of(case), case["num_mines"] if num_mines is None else num_mines,
        frozenset(cell(value) for value in case["declared_M"]), unresolved,
        case["total_worlds"] if total is None else total,
        tuple((c, counts[c]) for c in sorted(unresolved, key=reading_order)), original, original)


def proofs_of(premises):
    return stage1.pair_proofs_for_state(premises.observation, premises.mines, premises.num_mines, premises)


def target_of(case):
    return cell(case["plan_expected"]["actual_target"])


def setup(name):
    case = FIX["cases"][name]
    premises = premises_of(case)
    return case, premises, proofs_of(premises)


def diagnose(name):
    case, premises, proofs = setup(name)
    return L.diagnose_premises_links(premises, proofs, actual_target=target_of(case), selection_reason=REASONS[name])


def kernel_counts(grid, num_mines):
    """Reference call of the accepted exact kernel made by a test (not through the module's seam)."""
    result = simple_probability.calculate_probabilities(grid, num_mines)
    return result.total_worlds, {item.coordinate: item.mine_worlds for item in result.probabilities}


def counting():
    return patch.object(L, "_kernel", wraps=L._kernel)


def forbidden():
    return patch.object(L, "_kernel", side_effect=AssertionError("an exact call left the module"))


def number_cells(case):
    return [(x, y) for y, row in enumerate(case["grid"]) for x, token in enumerate(row.split()) if token.isdigit()]


def board_of(case, mines):
    rows = case["grid"]
    return (len(rows[0].split()), len(rows), tuple(mines))


def status_rows(result):
    return {str(number): status for number, status in result.per_outcome}


def tally_row(tally):
    return {"certain_cells": tally.certain_cells, "certain_pair_cells": tally.certain_pair_cells,
            "certain_other_cells": tally.certain_other_cells, "resolved_pairs": tally.resolved_pairs,
            "resolved_bundles": tally.resolved_bundles, "all_cells_certain": tally.all_cells_certain}


class Base(unittest.TestCase):
    def setUp(self):
        self.built = 0

    def tearDown(self):
        # The planned number of Engines of this test, counted where they are built.
        self.assertEqual(self.built, ENGINES.get(self._testMethodName, 0))

    def build(self, board, cap=480):
        self.built += 1
        return RR.build(board, cap)

    def refused(self, codes, function, *arguments, **keywords):
        with self.assertRaises(KPolicyIntegrityError) as caught:
            function(*arguments, **keywords)
        self.assertIn(caught.exception.code, codes if type(codes) is tuple else (codes,))
        return caught.exception

    def prefix_state(self, case, mines):
        """The number cells of the case opened one by one (all are 1 or more: no flood), through the cap channel."""
        engine, guard = self.build(board_of(case, mines))
        cells = number_cells(case)
        for x, y in cells:
            guard.step(x, y, Action.OPEN)
            self.assertIs(guard.status, PLAYING)
        self.assertEqual((RR.public(guard), engine.steps), (public_grid(case), len(cells)))
        return engine, guard, cells[-1]

    def tallies_of(self, name, examined):
        """The hand-written tally rows of one case against the examined cells {cell: CellExamination}."""
        rows = [row for row in FIX["addendum"]["tallies"]["rows"] if row["case"] == name]
        self.assertTrue(rows)
        for row in rows:
            candidate = examined[cell(row["cell"])].candidate
            tally = next(item for item in candidate.tallies if item.number == row["number"])
            self.assertEqual(tally_row(tally), {key: row[key] for key in tally_row(tally)}, (name, row["cell"]))
        return rows


class LinkCaseTests(Base):
    """Declared premises of the hand cases against the real exact calculation."""

    def test_c01_the_declared_world_counts_of_every_hand_case_equal_the_real_exact_counts(self):
        # The evidence that a hand-written world list is complete: the accepted kernel, called once on
        # the declared grid, gives the same total and the same count of every unresolved cell.
        for name in ALL:
            with self.subTest(case=name):
                case = FIX["cases"][name]
                total, counts = kernel_counts(grid_of(case), case["num_mines"])
                self.assertEqual((total, counts), (case["total_worlds"], declared_counts(case)))
                if case["worlds"] is not None:
                    self.assertEqual(len(case["worlds"]), total)

    def test_c02_pairs_bundles_shares_and_links_are_the_hand_written_ones(self):
        for name in ALL:
            with self.subTest(case=name):
                case, premises, proofs = setup(name)
                number = {pair["id"]: index for index, pair in enumerate(case["pairs"])}
                self.assertEqual(
                    [(p.a, p.b, p.verdict, p.bases, p.distinguishing) for p in proofs],
                    [(cell(pair["a"]), cell(pair["b"]), pair["verdict"],
                      tuple((kind, None if source is None else cell(source)) for kind, source in pair["bases"]),
                      tuple((cell(c), state) for c, state in pair["distinguishing"])) for pair in case["pairs"]])
                plan = L.plan_links(premises, proofs, target_of(case))
                self.assertEqual([(p.a, p.b, p.verdict, p.distinguishing) for p in plan.pairs],
                                 [(p.a, p.b, p.verdict, p.distinguishing) for p in proofs])
                self.assertEqual([(bundle.cells, bundle.pairs) for bundle in plan.bundles],
                                 [(tuple(cell(c) for c in bundle["cells"]), tuple(number[p] for p in bundle["pairs"]))
                                  for bundle in case["bundles"]])
                self.assertEqual([plan.bundles[pair.bundle].pairs.count(index) for index, pair in enumerate(plan.pairs)],
                                 [1] * len(plan.pairs))
                self.assertEqual(list(plan.shares), [(number[p], number[q], cell(c)) for p, q, c in case["shares"]])
                self.assertEqual([(link.source, link.target, link.cells, link.same_bundle) for link in plan.links],
                                 [(number[link["from"]], number[link["to"]], tuple(cell(c) for c in link["cells"]),
                                   link["same_bundle"]) for link in case["links"]])

    def test_c03_the_anchor_plan_is_the_hand_written_one(self):
        statuses = FIX["addendum"]["plan_statuses"]
        with forbidden() as seam:
            for name in ALL:
                with self.subTest(case=name):
                    case, premises, proofs = setup(name)
                    expected = case["plan_expected"]
                    plan = L.plan_links(premises, proofs, target_of(case))
                    self.assertEqual([(a.cell, a.role, a.calls) for a in plan.anchors],
                                     [(cell(a["cell"]), a["role"], a["calls"]) for a in expected["anchors"]])
                    self.assertEqual((plan.planned_calls, list(plan.not_examined_limit), list(plan.out_of_scope),
                                      plan.status),
                                     (expected["planned_calls"], [cell(c) for c in expected["not_examined_limit"]],
                                      [(cell(item["cell"]), item["reason"]) for item in expected["out_of_scope"]],
                                      statuses[name]))
                    # The call order is fixed in the plan: every number m..m+u of every anchor, in anchor order.
                    self.assertEqual(list(plan.calls),
                                     [(a.cell, k) for a in plan.anchors
                                      for k in range(a.mine_neighbors, a.mine_neighbors + a.unresolved_neighbors + 1)])
                    self.assertTrue(all(a.calls == a.unresolved_neighbors + 1 for a in plan.anchors))
                    self.assertTrue(len(plan.anchors) <= 6 and plan.planned_calls == len(plan.calls) <= 54)
        self.assertEqual(seam.call_count, 0)  # planning makes no exact call
        # Actual and original target differ in LC01, LC05 and LC06: actual first, then the original one.
        for name in ("LC01", "LC05", "LC06"):
            case, premises, proofs = setup(name)
            plan = L.plan_links(premises, proofs, target_of(case))
            self.assertEqual([(a.cell, a.role) for a in plan.anchors[:2]],
                             [(target_of(case), "ACTUAL_TARGET"), (premises.original_target, "ORIGINAL_TARGET")])

    def test_c04_every_hand_candidate_gives_the_hand_written_outcomes_and_bundle_results(self):
        for name in WITH_WORLDS:
            case, premises, proofs = setup(name)
            cells, total = named(case), case["total_worlds"]
            bundle_number = {bundle["id"]: index for index, bundle in enumerate(case["bundles"])}
            for row in case["candidates"]:
                with self.subTest(case=name, candidate=row["name"]):
                    g = cell(row["cell"])
                    with counting() as seam:
                        examined = L.examine_cell(premises, proofs, g)
                    candidate = examined.candidate
                    self.assertEqual((candidate.cell, candidate.role, candidate.mine_neighbors,
                                      candidate.unresolved_neighbors, candidate.mine_worlds, candidate.total_worlds,
                                      candidate.calls, seam.call_count),
                                     (g, "EXAMINED_CELL", row["mine_neighbors"], row["unresolved_neighbors"],
                                      declared_counts(case)[g], total, row["unresolved_neighbors"] + 1,
                                      row["unresolved_neighbors"] + 1))
                    self.assertEqual(candidate.own_bundle,
                                     None if row["own_bundle"] is None else bundle_number[row["own_bundle"]])
                    self.assertEqual([(o.number, o.worlds, o.flood) for o in candidate.outcomes],
                                     [(o["number"], o["worlds"], o["flood"]) for o in row["outcomes"]])
                    others = tuple(sorted(premises.unresolved - {g}, key=reading_order))
                    for outcome, written in zip(candidate.outcomes, row["outcomes"]):
                        if written["worlds"] == 0:
                            self.assertEqual(outcome, L.LinkOutcome(written["number"], 0, written["flood"], (), (), (), None))
                            continue
                        # Every other unresolved cell, cells of no pair included, in reading order.
                        self.assertEqual(tuple(c for c, _ in outcome.mine_worlds), others)
                        counts = {cells[n]: value for n, value in written["mine_worlds"].items()}
                        self.assertEqual(dict(outcome.mine_worlds), counts)
                        self.assertEqual((outcome.safe_cells, outcome.mine_cells, outcome.minimum_mine_worlds),
                                         (tuple(c for c in others if counts[c] == 0),
                                          tuple(c for c in others if counts[c] == written["worlds"]),
                                          min(counts.values())))
                    self.assertEqual(sum(o.worlds for o in candidate.outcomes), total - declared_counts(case)[g])
                    self.assertEqual(
                        [(r.anchor, r.bundle, status_rows(r), r.resolved_worlds, r.unresolved_worlds,
                          r.flood_undetermined_worlds, r.survival_worlds, r.label, str(r.conditional),
                          str(r.unconditional), type(r.conditional), type(r.unconditional))
                         for r in examined.results],
                        [(g, bundle_number[r["bundle"]], r["per_outcome"], r["resolved_worlds"], r["unresolved_worlds"],
                          r["flood_undetermined_worlds"], r["survival_worlds"], r["label"], r["conditional"],
                          r["unconditional"], Fraction, Fraction) for r in row["bundle_results"]])
                    # Tallies exist for the surviving outcomes only.
                    self.assertEqual([t.number for t in candidate.tallies],
                                     [o["number"] for o in row["outcomes"] if o["worlds"]])

    def test_c05_a_diagnosis_makes_exactly_its_planned_calls_and_labels_the_actual_target(self):
        planned, labels = FIX["addendum"]["planned_calls"], FIX["addendum"]["target_labels"]
        for name in ALL:
            with self.subTest(case=name):
                case, premises, proofs = setup(name)
                target = target_of(case)
                with counting() as seam:
                    diagnosis = L.diagnose_premises_links(premises, proofs, actual_target=target,
                                                          selection_reason=REASONS[name])
                self.assertEqual((seam.call_count, diagnosis.planned_calls, diagnosis.actual_calls,
                                  diagnosis.plan.planned_calls), (planned[name],) * 4)
                self.assertEqual((diagnosis.scope, diagnosis.premise_source, diagnosis.limits, diagnosis.actual_target,
                                  diagnosis.original_target, diagnosis.selection_reason, diagnosis.lookahead_checked),
                                 ("PAIR_BUNDLE_RESOLUTION_DIAGNOSIS_V1", "DECLARED_PREMISES", (6, 54), target,
                                  premises.original_target, REASONS[name], ()))
                self.assertIs(diagnosis.premises, premises)
                self.assertEqual([(c.cell, c.role, c.calls) for c in diagnosis.candidates],
                                 [(a.cell, a.role, a.calls) for a in diagnosis.plan.anchors])
                # One row per anchor and bundle that does not contain it: anchor order, then bundle order.
                self.assertEqual([(r.anchor, r.bundle) for r in diagnosis.results],
                                 [(a.cell, index) for a in diagnosis.plan.anchors
                                  for index, bundle in enumerate(diagnosis.plan.bundles) if a.cell not in bundle.cells])
                if name in labels:
                    self.assertEqual(diagnosis.target_label, labels[name])
                # The planned anchors that are hand candidates give the hand-written labels.
                written = {cell(row["cell"]): [r["label"] for r in row["bundle_results"]] for row in case["candidates"]}
                for anchor in diagnosis.plan.anchors:
                    if anchor.cell in written:
                        self.assertEqual([r.label for r in diagnosis.results if r.anchor == anchor.cell],
                                         written[anchor.cell])

    def test_c06_lc08_keeps_cells_left_out_by_the_limit_apart_from_impossible_numbers(self):
        case, premises, proofs = setup("LC08")
        with counting() as seam:
            diagnosis = L.diagnose_premises_links(premises, proofs, actual_target=(0, 0), selection_reason=KEPT)
        plan = diagnosis.plan
        self.assertEqual((seam.call_count, diagnosis.actual_calls, len(plan.anchors), plan.not_examined_limit,
                          plan.out_of_scope, plan.status), (17, 17, 6, ((2, 6),), (), "PLANNED"))
        # Left out by the limit: no anchor, no outcome, no result, no status. It is a cross-bundle link cell.
        self.assertNotIn((2, 6), [c.cell for c in diagnosis.candidates])
        self.assertNotIn((2, 6), [r.anchor for r in diagnosis.results])
        self.assertIn((2, 6), [c for link in plan.links if not link.same_bundle for c in link.cells])
        # An impossible number is something else: it WAS called, belongs to an anchor and has Z = 0.
        outcomes = [(c.cell, o) for c in diagnosis.candidates for o in c.outcomes]
        self.assertEqual(len(outcomes), 17)
        for anchor, outcome in outcomes:
            if outcome.worlds == 0:
                self.assertEqual(outcome, L.LinkOutcome(outcome.number, 0, outcome.flood, (), (), (), None))
        self.assertTrue(all(sum(o.worlds for o in c.outcomes) == 32 for c in diagnosis.candidates))
        # The cell left out is not impossible: examined on its own it has surviving outcomes.
        with counting() as seam:
            alone = L.examine_cell(premises, proofs, (2, 6)).candidate
        self.assertEqual((seam.call_count, alone.calls, sum(o.worlds for o in alone.outcomes)),
                         (alone.unresolved_neighbors + 1, alone.unresolved_neighbors + 1, 32))

    def test_c07_lc09_records_the_difference_between_the_target_and_the_link_cells_and_selects_nothing(self):
        case, premises, proofs = setup("LC09")
        # The existing rule on the same declared premises (a calculation, not K inference): the target stays.
        with patch.object(d3, "_kernel", wraps=d3._kernel) as lookahead:
            selection = d3.decide(premises, FIX["table"])
        self.assertEqual((selection.selection_reason, selection.original_target, selection.target,
                          selection.target_changed, selection.planned_calls, lookahead.call_count),
                         (KEPT, (2, 2), (2, 2), False, 34, 34))
        before = (selection.move, selection.category, selection.selection_reason, selection.evidence)
        with counting() as seam:
            diagnosis = L.diagnose_links(selection)
        L.validate_link_diagnosis(diagnosis, selection)
        self.assertEqual((seam.call_count, diagnosis.premise_source, diagnosis.actual_target, diagnosis.target_label,
                          diagnosis.lookahead_checked),
                         (14, "DECLARED_PREMISES", (2, 2), "NOT_OBSERVED", ((2, 2), (2, 3), (1, 4))))
        self.assertEqual([(a.cell, a.role, a.calls) for a in diagnosis.plan.anchors],
                         [((2, 2), "ACTUAL_TARGET", 4), ((2, 3), "CROSS_BUNDLE_LINK", 5), ((1, 4), "CROSS_BUNDLE_LINK", 5)])
        # The actual target leaves the other bundle open; each link cell settles the other bundle.
        self.assertEqual([(r.anchor, r.bundle, r.per_outcome, r.label, r.conditional, r.unconditional)
                          for r in diagnosis.results],
                         [((2, 2), 1, ((3, "UNRESOLVED_OTHER"),), "NOT_RESOLVED_EXAMINED", Fraction(0), Fraction(0)),
                          ((2, 3), 1, ((2, "RESOLVED"), (3, "RESOLVED")), "RESOLVED_ALL", Fraction(1), Fraction(1, 2)),
                          ((1, 4), 0, ((2, "RESOLVED"), (3, "RESOLVED")), "RESOLVED_ALL", Fraction(1), Fraction(1, 2))])
        # Nothing was selected here: the selection record is untouched and the diagnosis has no input field.
        self.assertEqual((selection.move, selection.category, selection.selection_reason, selection.evidence), before)
        self.assertEqual([field.name for field in fields(L.LinkDiagnosis)],
                         ["scope", "premise_source", "premises", "actual_target", "original_target", "selection_reason",
                          "limits", "plan", "candidates", "results", "target_label", "planned_calls", "actual_calls",
                          "lookahead_checked"])
        # The same content as the diagnosis of the declared premises without a selection record.
        declared = diagnose("LC09")
        self.assertEqual((declared.plan, declared.candidates, declared.results, declared.target_label,
                          declared.lookahead_checked),
                         (diagnosis.plan, diagnosis.candidates, diagnosis.results, "NOT_OBSERVED", ()))

    def test_c08_lc04_counts_bundle_cells_and_settled_cells_apart(self):
        case, premises, proofs = setup("LC04")
        plan = L.plan_links(premises, proofs, (1, 0))
        dedup = case["dedup_expected"]
        self.assertEqual((len(plan.pairs), len(plan.bundles), len(plan.bundles[0].cells),
                          sum(len((pair.a, pair.b)) for pair in plan.pairs), len(plan.shares)),
                         (dedup["pairs"], dedup["bundles"], dedup["distinct_pair_cells"],
                          dedup["sum_of_pair_cells_if_counted_per_pair"], 2))
        self.assertEqual((plan.status, plan.anchors, plan.planned_calls), ("NO_OTHER_BUNDLE", (), 0))
        examined = {(1, 0): L.examine_cell(premises, proofs, (1, 0))}
        rows = self.tallies_of("LC04", examined)
        candidate = examined[(1, 0)].candidate
        # Four cells make the bundle; three other cells are settled after the one input; never six.
        self.assertEqual((rows[0]["bundle_cells_total"], len(plan.bundles[candidate.own_bundle].cells),
                          candidate.tallies[0].certain_cells, candidate.tallies[0].resolved_pairs,
                          candidate.tallies[0].resolved_bundles, examined[(1, 0)].results), (4, 4, 3, 3, 1, ()))
        # A whole diagnosis of this decision plans nothing and labels nothing.
        with forbidden() as seam:
            diagnosis = diagnose("LC04")
        self.assertEqual((seam.call_count, diagnosis.candidates, diagnosis.results, diagnosis.target_label,
                          diagnosis.actual_calls), (0, (), (), "NOT_APPLICABLE", 0))

    def test_c09_cells_outside_every_pair_keep_their_counts_in_every_outcome(self):
        cases = {"LC06": ("a", "e"), "LC07": ("g", "n"), "LC09": ("a", "c"), "LA01": ("g", "n")}
        for name, candidates in cases.items():
            case, premises, proofs = setup(name)
            cells = named(case)
            pair_cells = {c for pair in case["pairs"] for c in (cell(pair["a"]), cell(pair["b"]))}
            outside = set(cells.values()) - pair_cells
            self.assertTrue(outside)
            for row in case["candidates"]:
                if row["name"] not in candidates:
                    continue
                with self.subTest(case=name, candidate=row["name"]):
                    g = cell(row["cell"])
                    candidate = L.examine_cell(premises, proofs, g).candidate
                    for outcome, written in zip(candidate.outcomes, row["outcomes"]):
                        if written["worlds"] == 0:
                            continue
                        counts = dict(outcome.mine_worlds)
                        self.assertEqual(set(counts), set(cells.values()) - {g})
                        self.assertEqual({c: counts[c] for c in outside - {g}},
                                         {cells[n]: v for n, v in written["mine_worlds"].items() if cells[n] in outside})

    def test_c10_a_number_zero_outcome_is_left_open_or_already_resolved(self):
        examined = {}
        for name, g in (("LC07", (0, 0)), ("LA01", (0, 0)), ("LA01", (1, 0)), ("LA02", (0, 0)), ("LA02", (1, 0))):
            case, premises, proofs = setup(name)
            examined[(name, g)] = L.examine_cell(premises, proofs, g)
        # LC07: the number 0 would flood and the hypothesis leaves the pair open: nothing is claimed.
        result = examined[("LC07", (0, 0))].results[0]
        zero = examined[("LC07", (0, 0))].candidate.outcomes[0]
        self.assertEqual((zero.number, zero.worlds, zero.flood, dict(zero.mine_worlds)[(2, 1)], result.per_outcome,
                          result.label, result.resolved_worlds, result.unresolved_worlds,
                          result.flood_undetermined_worlds, result.survival_worlds),
                         (0, 2, True, 1, ((0, "FLOOD_NOT_DETERMINED"), (1, "UNRESOLVED_ISOLATED")),
                          "UNDETERMINED_FLOOD", 0, 2, 2, 4))
        # LA01, cell g: resolved in the other outcome, open only in the number 0 outcome.
        result = examined[("LA01", (0, 0))].results[0]
        self.assertEqual((result.per_outcome, result.label, result.resolved_worlds, result.unresolved_worlds,
                          result.flood_undetermined_worlds, result.survival_worlds, result.conditional,
                          result.unconditional),
                         (((0, "FLOOD_NOT_DETERMINED"), (1, "RESOLVED")), "RESOLVED_SOME_FLOOD_OPEN", 1, 0, 2, 3,
                          Fraction(1, 3), Fraction(1, 5)))
        # LA01, cell n: its number 0 would flood too, but the hypothesis alone already settles the pair.
        candidate, result = examined[("LA01", (1, 0))].candidate, examined[("LA01", (1, 0))].results[0]
        self.assertEqual((candidate.outcomes[0].flood, candidate.outcomes[0].worlds, result.per_outcome, result.label),
                         (True, 1, ((0, "RESOLVED"), (1, "UNRESOLVED_OTHER"), (2, "RESOLVED")), "RESOLVED_SOME"))
        # LA02, cell g: every outcome, the number 0 included, settles the bundle.
        candidate, result = examined[("LA02", (0, 0))].candidate, examined[("LA02", (0, 0))].results[0]
        self.assertEqual(([(o.number, o.flood, o.worlds) for o in candidate.outcomes], result.per_outcome,
                          result.label, result.flood_undetermined_worlds, result.conditional, result.unconditional),
                         ([(0, True, 1), (1, False, 1)], ((0, "RESOLVED"), (1, "RESOLVED")), "RESOLVED_ALL", 0,
                          Fraction(1), Fraction(2, 3)))
        # LA02, cell n: a cell of the bundle itself; its number 0 is impossible and has the one normal form.
        candidate = examined[("LA02", (1, 0))].candidate
        self.assertEqual((candidate.own_bundle, candidate.outcomes[0], examined[("LA02", (1, 0))].results,
                          [t.number for t in candidate.tallies]),
                         (0, L.LinkOutcome(0, 0, True, (), (), (), None), (), [1, 2]))
        self.tallies_of("LC07", {(0, 0): examined[("LC07", (0, 0))]})
        self.tallies_of("LA01", {(0, 0): examined[("LA01", (0, 0))]})


class LinkStructureTests(Base):
    """Order, repetition, sharing and the pure label functions."""

    def test_s01_the_order_of_the_input_pairs_changes_nothing(self):
        for name in ("LC05", "LC09"):
            case, premises, proofs = setup(name)
            target = target_of(case)
            plan = L.plan_links(premises, proofs, target)
            diagnosis = L.diagnose_premises_links(premises, proofs, actual_target=target, selection_reason=REASONS[name])
            orders = (tuple(reversed(proofs)), proofs[1:] + proofs[:1], proofs[::2] + proofs[1::2])
            for index, order in enumerate(orders):
                with self.subTest(case=name, order=index):
                    self.assertNotEqual(order, proofs)
                    self.assertEqual(sorted((p.a, p.b) for p in order), sorted((p.a, p.b) for p in proofs))
                    again = L.plan_links(premises, order, target)
                    self.assertTrue(L._same(again, plan))
                    self.assertEqual((again.pairs, again.bundles, again.shares, again.links, again.anchors, again.calls),
                                     (plan.pairs, plan.bundles, plan.shares, plan.links, plan.anchors, plan.calls))
            # The whole diagnosis, value and exact types, from the reversed list.
            other = L.diagnose_premises_links(premises, orders[0], actual_target=target, selection_reason=REASONS[name])
            self.assertTrue(L._same(other, diagnosis, premises))
            cross = diagnosis.plan.anchors[-1].cell
            self.assertEqual(L.examine_cell(premises, orders[1], cross), L.examine_cell(premises, proofs, cross))

    def test_s02_a_repeated_pair_is_refused_and_shared_cells_are_not(self):
        case, premises, proofs = setup("LC04")
        first = proofs[0]
        with forbidden() as seam:
            # Sharing a cell is normal: LC04's three pairs share two cells and make one bundle.
            plan = L.plan_links(premises, proofs, (1, 0))
            self.assertEqual((len(plan.shares), len(plan.bundles)), (2, 1))
            self.assertEqual(len(L.plan_links(*setup("LC09")[1:], (2, 2)).shares), 5)
            # The same normal pair twice is an error, also when one copy is written the other way round.
            self.refused("LINK_PAIR_DUPLICATE", L.plan_links, premises, proofs + (first,), (1, 0))
            self.refused("LINK_PAIR_DUPLICATE", L.plan_links, premises, (first,) + proofs, (1, 0))
            self.refused("LINK_PAIR_DUPLICATE", L.plan_links, premises,
                         proofs + (replace(first, a=first.b, b=first.a),), (1, 0))
            self.refused("LINK_PAIR_DUPLICATE", L.diagnose_premises_links, premises, proofs + (first,),
                         actual_target=(1, 0), selection_reason=KEPT)
            self.refused("LINK_PAIR_DUPLICATE", L.examine_cell, premises, proofs + (first,), (1, 0))
        self.assertEqual(seam.call_count, 0)

    def test_s03_pairs_that_are_not_the_judgement_of_this_state_are_refused(self):
        case, premises, proofs = setup("LC06")
        first, target = proofs[0], target_of(case)
        foreign = setup("LC01")[2]
        cases = {
            "one pair missing": proofs[1:],
            "no pair at all": (),
            "pairs of another state": foreign,
            "a pair written the other way round": (replace(first, a=first.b, b=first.a),) + proofs[1:],
            "another verdict": (replace(first, verdict="FORCED_5050"),) + proofs[1:],
            "other distinguishing cells": (replace(first, distinguishing=()),) + proofs[1:],
            "other grounds": (replace(first, bases=()),) + proofs[1:],
            "other world counts": (replace(first, total_worlds=first.total_worlds + 1),) + proofs[1:],
            "a float count of equal value": (replace(first, mine_worlds=(float(first.mine_worlds[0]),
                                                                          first.mine_worlds[1])),) + proofs[1:],
            "a list instead of the tuple": list(proofs),
            "a cell written as a list": (replace(first, a=list(first.a)),) + proofs[1:],
            "an element that is no pair judgement": ((first.a, first.b),) + proofs[1:],
        }
        with forbidden() as seam:
            for name, pairs in cases.items():
                with self.subTest(case=name):
                    self.refused("LINK_PAIR_INPUT", L.plan_links, premises, pairs, target)
                    self.refused("LINK_PAIR_INPUT", L.diagnose_premises_links, premises, pairs, actual_target=target,
                                 selection_reason=REASONS["LC06"])
            L.plan_links(premises, proofs, target)  # the accepted judgement itself passes
        self.assertEqual((len(cases), seam.call_count), (12, 0))

    def test_s04_every_arithmetic_boundary_of_the_summary_label(self):
        rows = {(2, 0, 0): "RESOLVED_ALL", (1, 1, 0): "RESOLVED_SOME", (1, 1, 1): "RESOLVED_SOME",
                (1, 0, 1): "RESOLVED_SOME_FLOOD_OPEN", (0, 1, 0): "NOT_RESOLVED_EXAMINED",
                (0, 0, 1): "UNDETERMINED_FLOOD", (0, 1, 1): "UNDETERMINED_FLOOD"}
        for counts, label in rows.items():
            with self.subTest(counts=counts):
                self.assertEqual(L.summary_label(*counts), label)
                self.assertEqual(L.summary_label(*(7 * value for value in counts)), label)
        # Every combination of "zero or not" of R, N, F except all zero is one of the seven rows.
        self.assertEqual(sorted(rows), sorted((r, n, f) for r in (0, 1, 2) for n in (0, 1) for f in (0, 1)
                                              if (r, n, f) != (0, 0, 0) and (r < 2 or (n, f) == (0, 0))
                                              and not (r == 1 and (n, f) == (0, 0))))
        self.assertEqual(L.summary_label(1, 0, 0), "RESOLVED_ALL")
        for counts in ((0, 0, 0), (-1, 1, 0), (1, -1, 0), (1.0, 0, 0), (True, 0, 0), ("1", 0, 0), (1, None, 0)):
            with self.subTest(refused=counts):
                self.refused("LINK_WORLD_COUNT", L.summary_label, *counts)

    def test_s05_the_target_label_reads_only_the_results_of_the_actual_target(self):
        rows = {(): "NOT_APPLICABLE",
                ("RESOLVED_ALL",): "LINKED_ALL", ("NOT_RESOLVED_EXAMINED", "RESOLVED_ALL"): "LINKED_ALL",
                ("RESOLVED_SOME", "RESOLVED_ALL", "UNDETERMINED_FLOOD"): "LINKED_ALL",
                ("RESOLVED_SOME",): "LINKED_SOME", ("RESOLVED_SOME_FLOOD_OPEN",): "LINKED_SOME",
                ("UNDETERMINED_FLOOD", "RESOLVED_SOME"): "LINKED_SOME",
                ("UNDETERMINED_FLOOD",): "UNDETERMINED", ("NOT_RESOLVED_EXAMINED", "UNDETERMINED_FLOOD"): "UNDETERMINED",
                ("NOT_RESOLVED_EXAMINED",): "NOT_OBSERVED",
                ("NOT_RESOLVED_EXAMINED", "NOT_RESOLVED_EXAMINED"): "NOT_OBSERVED"}
        for labels, expected in rows.items():
            with self.subTest(labels=labels):
                self.assertEqual(L.target_label(labels), expected)
        for labels in (["RESOLVED_ALL"], ("LINKED_ALL",), ("RESOLVED",), (None,), "RESOLVED_ALL"):
            with self.subTest(refused=labels):
                self.refused("LINK_RECORD", L.target_label, labels)
        self.assertEqual((L.UNSUPPORTED, L.SUMMARY_LABELS),
                         ("UNSUPPORTED", ("RESOLVED_ALL", "RESOLVED_SOME", "RESOLVED_SOME_FLOOD_OPEN",
                                          "NOT_RESOLVED_EXAMINED", "UNDETERMINED_FLOOD")))

    def test_s06_wrong_types_and_values_of_premises_targets_and_reason_are_refused(self):
        case, premises, proofs = setup("LC01")
        grid, counts, target = premises.observation, premises.mine_worlds, target_of(case)
        first = counts[0]
        bad_premises = {
            "not premises": dict(observation=grid),
            "rows as lists": replace(premises, observation=tuple(list(row) for row in grid)),
            "grid as a list": replace(premises, observation=list(grid)),
            "a float in the grid": replace(premises, observation=((float(H),) + grid[0][1:],) + grid[1:]),
            "a value that is no public cell": replace(premises, observation=((9,) + grid[0][1:],) + grid[1:]),
            "a float mine total": replace(premises, num_mines=float(premises.num_mines)),
            "a boolean mine total": replace(premises, num_mines=True),
            "M as a set": replace(premises, mines=set(premises.mines)),
            "unresolved as a tuple": replace(premises, unresolved=tuple(premises.unresolved)),
            "an unresolved cell missing": replace(premises, unresolved=premises.unresolved - {(3, 0)}),
            "a flag outside M": replace(premises, mines=premises.mines - {(1, 1)}),
            "a float world total": replace(premises, total_worlds=float(premises.total_worlds)),
            "counts as a list": replace(premises, mine_worlds=list(counts)),
            "a float count": replace(premises, mine_worlds=((first[0], float(first[1])),) + counts[1:]),
            "a boolean count": replace(premises, total_worlds=2, mine_worlds=tuple((c, True) for c, _ in counts)),
            "a cell written as a list": replace(premises, mine_worlds=((list(first[0]), first[1]),) + counts[1:]),
            "counts in another order": replace(premises, mine_worlds=tuple(reversed(counts))),
            "a certain cell among the counts": replace(premises, mine_worlds=((first[0], 0),) + counts[1:]),
            "counts that do not add up": replace(premises, mine_worlds=((first[0], 1),) + counts[1:]),
            "an original target that is a mine": replace(premises, original_target=(1, 1)),
            "an original target written as a list": replace(premises, original_target=[0, 0]),
            "a cursor outside the board": replace(premises, cursor=(9, 9)),
        }
        bad_targets = ((9, 9), (1, 1), [1, 0], (1.0, 0), (True, 0), (1, 0, 0), None)
        bad_reasons = ("OTHER", None, 3, KEPT, FORCED_FIRST.lower())  # KEPT: this target is not the original one
        with forbidden() as seam:
            for name, bad in bad_premises.items():
                with self.subTest(premises=name):
                    self.refused(("LINK_PREMISES", "LINK_WORLD_COUNT"), L.plan_links, bad, proofs, target)
                    self.refused(("LINK_PREMISES", "LINK_WORLD_COUNT"), L.examine_cell, bad, proofs, target)
            for bad in bad_targets:
                with self.subTest(target=bad):
                    self.refused("LINK_PREMISES", L.plan_links, premises, proofs, bad)
                    self.refused("LINK_PREMISES", L.examine_cell, premises, proofs, bad)
            for bad in bad_reasons:
                with self.subTest(reason=bad):
                    self.refused("LINK_PREMISES", L.diagnose_premises_links, premises, proofs, actual_target=target,
                                 selection_reason=bad)
            # TIE_LOOKAHEAD needs a changed target, K_LC1_GUESS_KEPT an unchanged one.
            self.refused("LINK_PREMISES", L.diagnose_premises_links, premises, proofs,
                         actual_target=premises.original_target, selection_reason=TIE)
        self.assertEqual((len(bad_premises), seam.call_count), (22, 0))
        self.assertEqual(L.plan_links(premises, proofs, target).planned_calls, 8)  # the untouched premises pass


class LinkIntegrityTests(Base):
    """The one kernel seam, the call limit, the impossible number and the validation."""

    @staticmethod
    def mutated(change):
        """The real answer of the seam with its rows changed: (total, [(cell, count, row total)]) -> the same."""
        real = L._kernel

        def fake(observation, num_mines):
            result = real(observation, num_mines)  # a no-world answer propagates untouched
            total, rows = change(result.total_worlds,
                                 [(item.coordinate, item.mine_worlds, item.total_worlds) for item in result.probabilities])
            return SimpleNamespace(total_worlds=total, probabilities=tuple(
                SimpleNamespace(coordinate=c, mine_worlds=count, total_worlds=each) for c, count, each in rows))
        return fake

    def selection(self, name="LC01"):
        """The existing rule on declared premises: a selection record without a K-LC1 record."""
        case, premises, proofs = setup(name)
        return d3.decide(premises, FIX["table"])

    def test_i01_the_55th_call_is_refused_before_it_leaves(self):
        case, premises, proofs = setup("LC01")
        self.assertEqual((L.LINK_ANCHOR_LIMIT, L.LINK_CALL_LIMIT, L.LINK_ANCHOR_LIMIT * 9), (6, 54, 54))
        budget = L._CallBudget()
        for _ in range(54):
            budget.spend()
        with forbidden() as seam:
            error = self.refused("LINK_CALL_LIMIT", L._call, premises, (1, 0), 3, 2, budget)
        self.assertEqual((seam.call_count, budget.used), (0, 54))
        self.assertIn("55", str(error))
        # One call below the limit still leaves, and it is counted where it leaves.
        budget = L._CallBudget()
        budget.used = 53
        with counting() as seam:
            outcome = L._call(premises, (1, 0), 3, 2, budget)
        self.assertEqual((seam.call_count, budget.used, outcome.worlds), (1, 54, 1))
        # A plan above the limit is refused while planning, before any call.
        with patch.object(L, "LINK_CALL_LIMIT", 7), forbidden() as seam:
            self.refused("LINK_CALL_LIMIT", L.plan_links, premises, proofs, (1, 0))
            self.refused("LINK_CALL_LIMIT", L.diagnose_premises_links, premises, proofs, actual_target=(1, 0),
                         selection_reason=TIE)
        self.assertEqual(seam.call_count, 0)

    def test_i02_only_a_no_world_answer_becomes_an_impossible_number(self):
        case, premises, proofs = setup("LC03")
        seen, real = [], L._kernel

        def spy(observation, num_mines):
            try:
                return real(observation, num_mines)
            except Exception as error:
                seen.append(type(error))
                raise

        with patch.object(L, "_kernel", side_effect=spy) as seam:
            candidate = L.examine_cell(premises, proofs, (0, 0)).candidate
        self.assertEqual((seam.call_count, seen, [o.worlds for o in candidate.outcomes]),
                         (2, [InconsistentObservationError], [0, 2]))
        # Any other failure of a call is an error of the decision: the very exception, after the first call.
        for fault in (RuntimeError("boom"), ValueError("invalid grid"), KPolicyIntegrityError("OTHER", "fault")):
            with self.subTest(fault=type(fault).__name__):
                with patch.object(L, "_kernel", side_effect=fault) as seam:
                    with self.assertRaises(type(fault)) as caught:
                        L.diagnose_premises_links(premises, proofs, actual_target=(0, 0), selection_reason=FORCED_FIRST)
                self.assertIs(caught.exception, fault)
                self.assertEqual(seam.call_count, 1)
        # "No world" for every number contradicts the premises: an error, never an empty diagnosis.
        with patch.object(L, "_kernel", side_effect=InconsistentObservationError("none")) as seam:
            self.refused("LINK_WORLD_COUNT", L.diagnose_premises_links, premises, proofs, actual_target=(0, 0),
                         selection_reason=FORCED_FIRST)
        self.assertEqual(seam.call_count, 2)

    def test_i03_kernel_answers_with_a_wrong_cell_set_sum_or_type_are_errors(self):
        # LC01, cell (1,0): number 2 has no world, number 3 is the world {b, d}, number 4 the world {b, c}.
        case, premises, proofs = setup("LC01")
        b, c, d = (0, 0), (2, 0), (3, 0)
        K, W = "LINK_KERNEL_RESULT", "LINK_WORLD_COUNT"
        changes = {
            "a cell missing": (K, lambda total, rows: (total, rows[1:])),
            "a foreign cell": (K, lambda total, rows: (total, rows + [((9, 9), 0, total)])),
            "the opened cell itself": (K, lambda total, rows: (total, rows + [((1, 0), 0, total)])),
            "a cell twice": (K, lambda total, rows: (total, rows + rows[:1])),
            "a float count": (K, lambda total, rows: (total, [(x, float(n), t) for x, n, t in rows])),
            "a boolean count": (K, lambda total, rows: (total, [(x, bool(n), t) for x, n, t in rows])),
            "a count above the total": (K, lambda total, rows: (total, [(x, total + 1, t) for x, n, t in rows])),
            "a negative count": (K, lambda total, rows: (total, [(x, -1, t) for x, n, t in rows])),
            "another total in a row": (K, lambda total, rows: (total, [(x, n, t + 1) for x, n, t in rows])),
            "a float total": (K, lambda total, rows: (float(total), rows)),
            "a zero total": (K, lambda total, rows: (0, rows)),
            "a cell written as a list": (K, lambda total, rows: (total, [(list(x), n, t) for x, n, t in rows])),
            "counts that add up to no mine": (W, lambda total, rows: (total, [(x, 0, t) for x, n, t in rows])),
            "counts that add up to too many": (W, lambda total, rows: (total, [(x, total, t) for x, n, t in rows])),
            "a partner that is not a certain mine": (W, lambda total, rows: (total, [(b, 0, total), (c, total, total),
                                                                                     (d, total, total)])),
            "a pair with two mines": (W, lambda total, rows: (total, [(b, total, total), (c, total, total),
                                                                      (d, total, total)])),
            "twice the worlds": (W, lambda total, rows: (2 * total, [(x, 2 * n, 2 * t) for x, n, t in rows])),
        }
        # The two answers written out for the cells b, c, d fit the opened cell (1,0) only.
        one_cell_only = ("a partner that is not a certain mine", "a pair with two mines")
        for name, (code, change) in changes.items():
            with self.subTest(answer=name):
                with patch.object(L, "_kernel", side_effect=self.mutated(change)):
                    self.refused(code, L.examine_cell, premises, proofs, (1, 0))
                if name in one_cell_only:
                    continue
                with patch.object(L, "_kernel", side_effect=self.mutated(change)):
                    self.refused(code, L.diagnose_premises_links, premises, proofs, actual_target=(1, 0),
                                 selection_reason=TIE)
        self.assertEqual(len(changes), 17)
        # The unchanged answer through the same wrapper passes.
        with patch.object(L, "_kernel", side_effect=self.mutated(lambda total, rows: (total, rows))):
            candidate = L.examine_cell(premises, proofs, (1, 0)).candidate
        self.assertEqual([(o.number, o.worlds, dict(o.mine_worlds)) for o in candidate.outcomes],
                         [(2, 0, {}), (3, 1, {b: 1, c: 0, d: 1}), (4, 1, {b: 1, c: 1, d: 0})])

    def test_i04_the_impossible_number_has_one_normal_form(self):
        case, premises, proofs = setup("LC03")
        structure = L._structure(premises, proofs)
        examined = L.examine_cell(premises, proofs, (0, 0))
        candidate = examined.candidate
        zero, one = candidate.outcomes
        self.assertEqual(zero, L.LinkOutcome(0, 0, True, (), (), (), None))
        self.assertEqual([type(v) for v in (zero.number, zero.worlds, zero.flood, zero.mine_worlds, zero.safe_cells,
                                            zero.mine_cells)], [int, int, bool, tuple, tuple, tuple])
        # No tally, no status and no share of the denominator for the impossible number.
        self.assertEqual(([t.number for t in candidate.tallies], examined.results[0].per_outcome,
                          examined.results[0].survival_worlds, one.worlds), ([1], ((1, "UNRESOLVED_ISOLATED"),), 2, 2))
        others = tuple(c for c, _ in one.mine_worlds)
        invented = {
            "counts filled with zeros": replace(zero, mine_worlds=tuple((c, 0) for c in others)),
            "certain safe cells": replace(zero, safe_cells=others),
            "certain mines": replace(zero, mine_cells=others[:1]),
            "a minimum": replace(zero, minimum_mine_worlds=0),
            "no flood mark": replace(zero, flood=False),
            "lists instead of tuples": replace(zero, mine_worlds=[]),
            "a boolean world count": replace(zero, worlds=False),
            "another number": replace(zero, number=2),
        }
        with forbidden() as seam:
            for name, outcome in invented.items():
                with self.subTest(form=name):
                    self.refused("LINK_RECORD", L._candidate, premises, structure, (0, 0), "EXAMINED_CELL",
                                 (outcome, one))
            self.assertEqual(L._candidate(premises, structure, (0, 0), "EXAMINED_CELL", (zero, one)), candidate)
            # A surviving number cannot be written as impossible: the outcomes no longer add up.
            self.refused("LINK_WORLD_COUNT", L._candidate, premises, structure, (0, 0), "EXAMINED_CELL",
                         (zero, L.LinkOutcome(1, 0, False, (), (), (), None)))
        self.assertEqual(seam.call_count, 0)

    def test_i05_validation_rebuilds_the_record_without_a_kernel_call(self):
        selection = self.selection()
        self.assertEqual((selection.inner, selection.selection_reason, selection.original_target, selection.target),
                         (None, TIE, (0, 0), (1, 0)))
        with counting() as seam:
            diagnosis = L.diagnose_links(selection)
        self.assertEqual((seam.call_count, diagnosis.actual_calls, diagnosis.premise_source,
                          [(a.cell, a.role, a.calls) for a in diagnosis.plan.anchors], diagnosis.lookahead_checked,
                          diagnosis.target_label),
                         (8, 8, "DECLARED_PREMISES", [((1, 0), "ACTUAL_TARGET", 3), ((0, 0), "ORIGINAL_TARGET", 2),
                                                      ((2, 0), "CROSS_BUNDLE_LINK", 3)], ((1, 0), (0, 0), (2, 0)),
                          "LINKED_ALL"))
        self.assertIs(diagnosis.premises, selection.premises)
        with patch("simple_probability.calculate_probabilities", side_effect=AssertionError("kernel")) as kernel, \
                forbidden() as seam, patch.object(d3, "_kernel", side_effect=AssertionError("look-ahead")) as other:
            L.validate_link_diagnosis(diagnosis, selection)
            L.validate_link_diagnosis(diagnosis, selection)  # a second time: nothing was consumed or kept
        self.assertEqual((kernel.call_count, seam.call_count, other.call_count), (0, 0, 0))
        # The validator's own source names no call path.
        names = {node.id for node in ast.walk(ast.parse(inspect.getsource(L.validate_link_diagnosis).lstrip()))
                 if isinstance(node, ast.Name)}
        self.assertFalse(names & {"_call", "_kernel", "_diagnose", "examine_cell", "diagnose_links", "_CallBudget"})

    def test_i06_validation_refuses_changed_counts_lists_labels_and_types(self):
        selection = self.selection()
        diagnosis = L.diagnose_links(selection)
        first, result = diagnosis.candidates[0], diagnosis.results[0]
        three = first.outcomes[1]  # cell (1,0), number 3: the world {b, d}
        self.assertEqual((three.number, three.worlds, dict(three.mine_worlds)), (3, 1, {(0, 0): 1, (2, 0): 0, (3, 0): 1}))

        def with_outcome(outcome):
            return replace(diagnosis, candidates=(replace(first, outcomes=(first.outcomes[0], outcome,
                                                                           first.outcomes[2])),)
                           + diagnosis.candidates[1:])

        changed = {
            "another count": with_outcome(replace(three, mine_worlds=(((0, 0), 1), ((2, 0), 1), ((3, 0), 0)))),
            "a count dropped": with_outcome(replace(three, mine_worlds=three.mine_worlds[1:])),
            "a safe cell dropped": with_outcome(replace(three, safe_cells=())),
            "a certain mine added": with_outcome(replace(three, mine_cells=three.mine_cells + ((2, 0),))),
            "another minimum": with_outcome(replace(three, minimum_mine_worlds=1)),
            "another world count": with_outcome(replace(three, worlds=2)),
            "a boolean world count": with_outcome(replace(three, worlds=True)),
            "a float count of equal value": with_outcome(replace(three, mine_worlds=(((0, 0), 1.0),)
                                                                 + three.mine_worlds[1:])),
            "a float minimum of equal value": with_outcome(replace(three, minimum_mine_worlds=0.0)),
            "counts as a list": with_outcome(replace(three, mine_worlds=list(three.mine_worlds))),
            "safe cells as a list": with_outcome(replace(three, safe_cells=list(three.safe_cells))),
            "a number written as impossible": with_outcome(L.LinkOutcome(3, 0, False, (), (), (), None)),
            "outcomes as a list": replace(diagnosis, candidates=(replace(first, outcomes=list(first.outcomes)),)
                                          + diagnosis.candidates[1:]),
            "an outcome missing": replace(diagnosis, candidates=(replace(first, outcomes=first.outcomes[1:]),)
                                          + diagnosis.candidates[1:]),
            "candidates in another order": replace(diagnosis, candidates=tuple(reversed(diagnosis.candidates))),
            "a candidate missing": replace(diagnosis, candidates=diagnosis.candidates[1:]),
            "candidates as a list": replace(diagnosis, candidates=list(diagnosis.candidates)),
            "tallies as a list": replace(diagnosis, candidates=(replace(first, tallies=list(first.tallies)),)
                                         + diagnosis.candidates[1:]),
            "another role": replace(diagnosis, candidates=(replace(first, role="CROSS_BUNDLE_LINK"),)
                                    + diagnosis.candidates[1:]),
            "another label": replace(diagnosis, results=(replace(result, label="RESOLVED_SOME"),) + diagnosis.results[1:]),
            "another resolved count": replace(diagnosis, results=(replace(result, resolved_worlds=1),)
                                              + diagnosis.results[1:]),
            "a status changed": replace(diagnosis, results=(replace(result, per_outcome=((3, "RESOLVED"),
                                                                                         (4, "UNRESOLVED_OTHER"))),)
                                        + diagnosis.results[1:]),
            "a float fraction of equal value": replace(diagnosis, results=(replace(result, conditional=1.0),)
                                                       + diagnosis.results[1:]),
            "a result missing": replace(diagnosis, results=diagnosis.results[1:]),
            "another target label": replace(diagnosis, target_label="NOT_OBSERVED"),
            "another call count": replace(diagnosis, actual_calls=7),
            "a float call count of equal value": replace(diagnosis, planned_calls=8.0),
            "limits as a list": replace(diagnosis, limits=[6, 54]),
            "other limits": replace(diagnosis, limits=(8, 72)),
            "another scope": replace(diagnosis, scope="PAIR_MIRROR_DIAGNOSIS_V1"),
            "another premise source": replace(diagnosis, premise_source="K_DECISION_RECORD"),
            "no look-ahead comparison": replace(diagnosis, lookahead_checked=()),
            "another plan": replace(diagnosis, plan=replace(diagnosis.plan, not_examined_limit=((3, 0),))),
        }
        with patch("simple_probability.calculate_probabilities", side_effect=AssertionError("kernel")) as kernel:
            L.validate_link_diagnosis(diagnosis, selection)
            for name, record in changed.items():
                with self.subTest(record=name):
                    self.refused(RECORD_CODES, L.validate_link_diagnosis, record, selection)
        self.assertEqual((len(changed), kernel.call_count), (33, 0))

    def test_i07_a_diagnosis_of_another_decision_or_target_is_refused(self):
        selection = self.selection()
        twin = self.selection()  # the same declared state, decided again: equal in value, another decision
        diagnosis = L.diagnose_links(selection)
        self.assertEqual(twin.premises, selection.premises)
        self.assertIsNot(twin.premises, selection.premises)
        other_target = L.diagnose_premises_links(selection.premises, selection.pair_proofs, actual_target=(2, 0),
                                                 selection_reason=TIE)
        other_case = diagnose("LC06")
        with patch("simple_probability.calculate_probabilities", side_effect=AssertionError("kernel")) as kernel:
            L.validate_link_diagnosis(diagnosis, selection)
            self.refused("LINK_BINDING", L.validate_link_diagnosis, diagnosis, twin)
            self.refused("LINK_BINDING", L.validate_link_diagnosis, diagnosis,
                         replace(selection, premises=twin.premises))
            self.refused("LINK_BINDING", L.validate_link_diagnosis, other_target, selection)
            self.refused("LINK_BINDING", L.validate_link_diagnosis, other_case, selection)
            self.refused("LINK_BINDING", L.validate_link_diagnosis, replace(diagnosis, actual_target=(2, 0)), selection)
            self.refused("LINK_BINDING", L.validate_link_diagnosis, replace(diagnosis, original_target=(3, 0)),
                         selection)
            self.refused("LINK_BINDING", L.validate_link_diagnosis,
                         replace(diagnosis, selection_reason=FORCED_FIRST), selection)
            self.refused("LINK_BINDING", L.validate_link_diagnosis, replace(diagnosis, actual_target=[1, 0]),
                         selection)
            # The comparison is with the selection record, not with the diagnosis itself.
            self.refused("LINK_BINDING", L.validate_link_diagnosis, diagnosis, replace(selection, target=(2, 0)))
            self.refused("LINK_BINDING", L.validate_link_diagnosis, diagnosis,
                         replace(selection, selection_reason=FORCED_FIRST))
            for record, choice in ((None, selection), ((), selection), (diagnosis, None), (diagnosis, diagnosis),
                                   (selection, selection)):
                self.refused("LINK_RECORD", L.validate_link_diagnosis, record, choice)
        self.assertEqual(kernel.call_count, 0)
        self.assertEqual(other_target.actual_target, (2, 0))

    def test_i08_the_existing_lookahead_values_of_the_same_cell_must_agree(self):
        selection = self.selection()
        diagnosis = L.diagnose_links(selection)
        self.assertEqual(([v.cell for v in selection.lookaheads], diagnosis.lookahead_checked),
                         ([(0, 0), (1, 0), (2, 0), (3, 0)], ((1, 0), (0, 0), (2, 0))))
        value = selection.lookaheads[1]  # cell (1,0): numbers 2 (no world), 3 and 4
        self.assertEqual([(o.number, o.worlds, o.safe_cells, o.minimum_mine_worlds) for o in value.outcomes],
                         [(2, 0, 0, None), (3, 1, 1, 0), (4, 1, 1, 0)])

        def with_outcome(index, **changes):
            outcomes = tuple(replace(o, **changes) if i == index else o for i, o in enumerate(value.outcomes))
            return replace(selection, lookaheads=(selection.lookaheads[0], replace(value, outcomes=outcomes))
                           + selection.lookaheads[2:])

        tampered = {
            "another world count": with_outcome(1, worlds=2),
            "another number of safe cells": with_outcome(1, safe_cells=2),
            "another minimum": with_outcome(2, minimum_mine_worlds=1),
            "another flood mark": with_outcome(0, flood=True),
            "an outcome missing": replace(selection, lookaheads=(selection.lookaheads[0],
                                                                 replace(value, outcomes=value.outcomes[1:]))
                                          + selection.lookaheads[2:]),
            "other neighbours": replace(selection, lookaheads=(selection.lookaheads[0],
                                                               replace(value, unresolved_neighbors=3))
                                        + selection.lookaheads[2:]),
        }
        for name, record in tampered.items():
            with self.subTest(lookahead=name):
                # The calls are made, the comparison fails, and no diagnosis comes back.
                with counting() as seam:
                    self.refused("LINK_LOOKAHEAD_MISMATCH", L.diagnose_links, record)
                self.assertEqual(seam.call_count, 8)
                with forbidden():
                    self.refused("LINK_LOOKAHEAD_MISMATCH", L.validate_link_diagnosis, diagnosis, record)
        # Values that are no look-ahead values are refused before the first call.
        with forbidden() as seam:
            self.refused("LINK_PREMISES", L.diagnose_links, replace(selection, lookaheads=list(selection.lookaheads)))
            self.refused("LINK_PREMISES", L.diagnose_links, replace(selection, lookaheads=(value, value)))
            self.refused("LINK_PREMISES", L.diagnose_links, replace(selection, lookaheads=(value.outcomes[0],)))
        self.assertEqual(seam.call_count, 0)
        # A cell the look-ahead did not compute is simply not compared.
        fewer = replace(selection, lookaheads=selection.lookaheads[:1])
        self.assertEqual(L.diagnose_links(fewer).lookahead_checked, ((0, 0),))

    def test_i09_one_kernel_seam_and_no_state_between_two_diagnoses(self):
        tree = ast.parse(inspect.getsource(L))
        names = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)]
        imported = [alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names]
        kernel = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_kernel")
        inside = [node.id for node in ast.walk(kernel) if isinstance(node, ast.Name)]
        self.assertEqual((imported.count("calculate_probabilities"), names.count("calculate_probabilities"),
                          inside.count("calculate_probabilities")), (1, 1, 1))
        seam_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Name) and node.func.id == "_kernel"]
        caller = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_call")
        self.assertEqual((len(seam_calls), len([n for n in ast.walk(caller) if n in seam_calls])), (1, 1))
        # The only try statement turns "no world" into the impossible number; nothing else is caught.
        tries = [node for node in ast.walk(tree) if isinstance(node, ast.Try)]
        self.assertEqual([[handler.type.id for handler in node.handlers] for node in tries],
                         [["InconsistentObservationError"]])
        self.assertFalse([node for node in ast.walk(tree) if isinstance(node, (ast.Global, ast.Nonlocal))])
        # Module level: constants only (upper-case names); no mutable state, no file or storage access.
        targets = [target for node in tree.body if isinstance(node, ast.Assign) for target in node.targets]
        assigned = [item.id for target in targets
                    for item in (target.elts if isinstance(target, ast.Tuple) else [target])]
        self.assertTrue(assigned and all(name == name.upper() for name in assigned))
        self.assertFalse(set(names) & {"open", "json", "pickle", "os", "Path", "select_singleton_policy", "SimpleMove",
                                       "action_cost", "apply_lookahead"})
        # Behaviour: a diagnosis made between two others changes nothing and nothing is reused.
        with counting() as seam:
            first, between, again = diagnose("LC05"), diagnose("LC01"), diagnose("LC05")
        self.assertEqual((seam.call_count, first == again, first.actual_calls, between.actual_calls), (46, True, 19, 8))
        self.assertIsNot(first.candidates[0].outcomes[1], again.candidates[0].outcomes[1])


class MineCountTests(Base):
    """What the mine total reveals and what it cannot reveal."""

    def test_m01_another_mine_total_reveals_safe_cells_on_the_same_public_numbers(self):
        case = FIX["cases"]["LC09"]
        cells, variants = named(case), FIX["addendum"]["mine_count_variants"]["declared"]
        grid = grid_of(case)
        seen = {}
        for mines in ("6", "7", "8"):
            with self.subTest(num_mines=mines):
                written = variants[mines]
                # A separate premise per mine total: the same grid and M, one fresh exact calculation each.
                total, counts = kernel_counts(grid, int(mines))
                self.assertEqual((total, counts), (written["total_worlds"],
                                                   {cells[n]: v for n, v in written["mine_worlds"].items()}))
                self.assertEqual((sorted(c for c, n in counts.items() if n == 0),
                                  sorted(c for c, n in counts.items() if n == total)),
                                 (sorted(cell(c) for c in written["safe_cells"]),
                                  sorted(cell(c) for c in written["certain_mines"])))
                seen[mines] = (total, counts)
        self.assertEqual(case["num_mines"], 7)
        # With the total of the case nothing is certain; one mine less or more makes cells certain.
        self.assertTrue(all(0 < n < seen["7"][0] for n in seen["7"][1].values()))
        # A state with a certain cell is no guess premise: the diagnosis refuses it instead of diagnosing.
        with forbidden() as seam:
            for mines in ("6", "8"):
                total, counts = seen[mines]
                premises = premises_of(case, num_mines=int(mines), total=total, counts=counts)
                self.refused("LINK_PREMISES", L.plan_links, premises, (), (2, 2))
        self.assertEqual(seam.call_count, 0)

    def test_m02_a_real_session_does_not_guess_when_the_mine_total_reveals_a_safe_cell(self):
        case = FIX["cases"]["LC09"]
        cells, sessions = named(case), FIX["addendum"]["mine_count_variants"]["real_sessions"]
        declared = [cell(c) for c in case["declared_M"]]
        continuations = {}
        for mines in ("6", "7", "8"):
            with self.subTest(num_mines=mines):
                written = sessions[mines]
                layout = declared + [cells[n] for n in written["layout_world"]]
                self.assertEqual(len(layout), int(mines))
                engine, guard, cursor = self.prefix_state(case, layout)
                session = KLocalSession(guard.width, guard.height, guard.num_mines)  # fresh; M is not injected
                decision = session.analyze_decision(RR.public(guard), status=PLAYING)
                continuations[mines] = decision.continuation
                self.assertEqual((decision.continuation, decision.selection_safe_cells, session.M,
                                  decision.local.S_current, decision.phase_d_status),
                                 (written["continuation"], frozenset(cell(c) for c in written["safe_cells"]),
                                  frozenset(cell(c) for c in written["M_after"]), frozenset(), "REACHED"))
                choice = P.select_combined_policy(decision, cursor, FIX["table"])
                if mines == "7":
                    self.assertEqual((decision.guess_target, choice.branch, choice.guess.selection_reason,
                                      choice.guess.target, choice.guess.planned_calls),
                                     (cell(written["guess_target"]), P.BRANCH_GUESS, written["selection_reason"],
                                      cell(written["target"]), written["lookahead_planned_calls"]))
                else:
                    # A safe cell exists: the decision is certain, not a guess, and gets no linked diagnosis.
                    self.assertEqual((decision.guess_target, choice.branch, choice.guess), (None, P.BRANCH_CERTAIN, None))
                self.assertEqual(engine.steps, 25)  # nothing was sent beyond the prefix
        # The safe cells come from the exact phase (the mine total), not from a local clue.
        self.assertEqual(continuations, {"6": "EXACT_SAFE", "7": "EXACT_GUESS", "8": "EXACT_SAFE"})

    def test_m03_a_forced_pair_stays_one_half_although_the_mine_total_is_known(self):
        written = FIX["addendum"]["forced_pair_with_known_mine_count"]
        other_cell = {"LC03": (4, 0), "LC02": (2, 1)}  # a cell of the OTHER bundle, opened in the hypothesis
        for name in ("LC03", "LC02"):
            case, premises, proofs = setup(name)
            counts, total = dict(premises.mine_worlds), premises.total_worlds
            examined = L.examine_cell(premises, proofs, other_cell[name])
            for a, b in ((cell(a), cell(b)) for a, b in written[name]["pairs"]):
                if other_cell[name] in (a, b):
                    continue
                with self.subTest(case=name, pair=(a, b)):
                    proof = next(p for p in proofs if (p.a, p.b) == (a, b))
                    self.assertEqual((proof.verdict, total, counts[a], counts[b]),
                                     ("FORCED_5050", written[name]["total_worlds"], written[name]["mine_worlds_each"],
                                      written[name]["mine_worlds_each"]))
                    self.assertEqual((Fraction(counts[a], total), Fraction(counts[b], total)),
                                     (Fraction(1, 2), Fraction(1, 2)))
                    # Both possibilities exist under the SAME mine total and in the same number of worlds.
                    for mine in (a, b):
                        hypothesis = pseudo.mine_hypothesis_observation(premises.observation, premises.mines, mine)
                        worlds, conditional = kernel_counts(hypothesis, premises.num_mines)
                        self.assertEqual((worlds, conditional[b if mine == a else a]),
                                         (written[name]["worlds_with_either_cell_as_the_mine"], 0))
                    # Opening a cell of the other bundle and surviving leaves this pair open in every outcome.
                    plan = L.plan_links(premises, proofs, premises.original_target)
                    bundle = next(i for i, item in enumerate(plan.bundles) if item.cells == (a, b))
                    result = next(r for r in examined.results if r.bundle == bundle)
                    self.assertEqual((set(status for _, status in result.per_outcome), result.label,
                                      result.resolved_worlds, result.conditional),
                                     ({"UNRESOLVED_ISOLATED"}, "NOT_RESOLVED_EXAMINED", 0, Fraction(0)))
                    for outcome in examined.candidate.outcomes:
                        if outcome.worlds:
                            rows = dict(outcome.mine_worlds)
                            self.assertTrue(0 < rows[a] < outcome.worlds and 0 < rows[b] < outcome.worlds)
                            self.assertFalse({a, b} & (set(outcome.safe_cells) | set(outcome.mine_cells)))

    def test_m04_lc09_keeps_the_other_bundle_and_the_floating_cell_as_separate_conclusions(self):
        case, premises, proofs = setup("LC09")
        floating = FIX["addendum"]["lc09_floating_cell"]
        spot = cell(floating["cell"])
        plan = L.plan_links(premises, proofs, (2, 2))
        self.assertFalse([bundle for bundle in plan.bundles if spot in bundle.cells])  # a cell of no pair
        examined = {g: L.examine_cell(premises, proofs, g) for g in ((2, 2), (2, 3), (1, 4))}
        self.tallies_of("LC09", examined)
        for key, g in (("after_cell_2_3", (2, 3)), ("after_cell_1_4", (1, 4)), ("after_cell_2_2", (2, 2))):
            with self.subTest(opened=g):
                states = {}
                for outcome in examined[g].candidate.outcomes:
                    if outcome.worlds:
                        states[str(outcome.number)] = ("CERTAIN_SAFE" if spot in outcome.safe_cells else
                                                       "CERTAIN_MINE" if spot in outcome.mine_cells else "UNCERTAIN")
                self.assertEqual(states, floating[key])
        # Three units, three places: the bundle (BundleResult), the cell of no pair (certain_other_cells and
        # the cell lists), the whole remaining area (all_cells_certain). A result row names bundles only.
        link = examined[(2, 3)]
        self.assertEqual(([(r.bundle, r.label) for r in link.results],
                          [(t.certain_other_cells, t.all_cells_certain) for t in link.candidate.tallies]),
                         ([(1, "RESOLVED_ALL")], [(1, True), (1, True)]))
        target = examined[(2, 2)]
        self.assertEqual(([(r.bundle, r.label) for r in target.results],
                          [(t.certain_other_cells, t.resolved_bundles, t.all_cells_certain)
                           for t in target.candidate.tallies]), ([(1, "NOT_RESOLVED_EXAMINED")], [(0, 1, False)]))


class RealStateTests(Base):
    """Real K decisions on prefix states and real Engine floods."""

    def test_r01_lc09_as_a_real_k_decision_gives_the_declared_premises_and_the_hand_plan(self):
        case, declared_premises, declared_proofs = setup("LC09")
        cells = named(case)
        written = FIX["addendum"]["mine_count_variants"]["real_sessions"]["7"]
        layout = [cell(c) for c in case["declared_M"]] + [cells[n] for n in written["layout_world"]]
        engine, guard, cursor = self.prefix_state(case, layout)
        session = KLocalSession(guard.width, guard.height, guard.num_mines)  # fresh; M is not injected
        decision = session.analyze_decision(RR.public(guard), status=PLAYING)
        choice = P.select_combined_policy(decision, cursor, FIX["table"])
        guess = choice.guess
        premises = guess.premises
        # The real decision derives exactly the declared M and the declared exact counts.
        self.assertEqual((decision.continuation, session.M, premises.mines, premises.unresolved, premises.total_worlds,
                          dict(premises.mine_worlds), premises.observation),
                         ("EXACT_GUESS", declared_premises.mines, declared_premises.mines,
                          declared_premises.unresolved, 4, declared_counts(case), public_grid(case)))
        self.assertEqual((guess.selection_reason, guess.original_target, guess.target, guess.target_changed,
                          choice.move, [p.verdict for p in guess.pair_proofs]),
                         (KEPT, (2, 2), (2, 2), False, O(2, 2), ["APPARENT_5050"] * 6))
        with counting() as seam:
            diagnosis = L.diagnose_links(guess)
        L.validate_link_diagnosis(diagnosis, guess)
        self.assertEqual((seam.call_count, diagnosis.premise_source, diagnosis.actual_calls, diagnosis.target_label,
                          diagnosis.lookahead_checked, diagnosis.plan.status),
                         (14, "K_DECISION_RECORD", 14, "NOT_OBSERVED", ((2, 2), (2, 3), (1, 4)), "PLANNED"))
        self.assertIs(diagnosis.premises, premises)
        # The same plan, outcomes and results as the declared case (whose grid shows the mines as flags).
        declared = L.diagnose_premises_links(declared_premises, declared_proofs, actual_target=(2, 2),
                                             selection_reason=KEPT)
        self.assertEqual((diagnosis.plan, diagnosis.candidates, diagnosis.results),
                         (declared.plan, declared.candidates, declared.results))
        self.assertEqual([(r.anchor, r.bundle, r.label) for r in diagnosis.results],
                         [((2, 2), 1, "NOT_RESOLVED_EXAMINED"), ((2, 3), 1, "RESOLVED_ALL"), ((1, 4), 0, "RESOLVED_ALL")])
        # The selection is the one made before the diagnosis and nothing was sent to the Engine.
        self.assertEqual((choice.move, choice.category, guess.selection_reason, engine.steps, guard.status),
                         (O(2, 2), "EXACT_MINIMUM_RISK_GUESS", KEPT, 25, PLAYING))

    def test_r02_the_real_flood_shows_more_than_the_number_zero_hypothesis(self):
        engines = FIX["addendum"]["flood_engines"]
        hypothesis = {}
        for key in ("LC07_c", "LC07_d", "LA01_c", "LA01_d"):
            with self.subTest(layout=key):
                written = engines[key]
                case, premises, proofs = setup(written["case"])
                cells, opened = named(case), cell(written["open"])
                if written["case"] not in hypothesis:
                    hypothesis[written["case"]] = L.examine_cell(premises, proofs, opened)
                examined = hypothesis[written["case"]]
                zero = examined.candidate.outcomes[0]
                pair = (cells["c"], cells["d"])
                # The hypothesis: only the opened cell shows 0; the pair stays open and nothing is claimed.
                self.assertEqual((zero.number, zero.flood, examined.results[0].per_outcome[0]),
                                 (0, True, (0, "FLOOD_NOT_DETERMINED")))
                self.assertTrue(all(0 < dict(zero.mine_worlds)[c] < zero.worlds for c in pair))
                # The real Engine: the same single input reveals more cells than the opened one.
                engine, guard, _ = self.prefix_state(case, [cell(c) for c in written["mines"]])
                before = RR.public(guard)
                guard.step(opened[0], opened[1], Action.OPEN)
                after = RR.public(guard)
                self.assertEqual((guard.status, after), (PLAYING, rows_grid(written["rows_after"])))
                revealed = [(x, y) for y, row in enumerate(after) for x, v in enumerate(row) if v != before[y][x]]
                self.assertGreater(len(revealed), 1)
                # The calculation on the real rows, with the declared M kept: the pair is certain now.
                flagged = tuple(tuple(F if v == H and (x, y) in premises.mines else v for x, v in enumerate(row))
                                for y, row in enumerate(after))
                total, counts = kernel_counts(flagged, case["num_mines"])
                expected = written["certain_after"]
                self.assertEqual(total, expected["total_worlds"])
                for name, value in expected.items():
                    if name != "total_worlds":
                        self.assertEqual(counts[cells[name]], value * total)
                self.assertTrue(all(counts[c] in (0, total) for c in pair if c in counts))

    def test_r03_a_decision_that_is_no_guess_gets_no_diagnosis(self):
        case = FIX["cases"]["LC09"]
        cells = named(case)
        written = FIX["addendum"]["mine_count_variants"]["real_sessions"]["6"]
        layout = [cell(c) for c in case["declared_M"]] + [cells[n] for n in written["layout_world"]]
        engine, guard, cursor = self.prefix_state(case, layout)
        session = KLocalSession(guard.width, guard.height, guard.num_mines)
        decision = session.analyze_decision(RR.public(guard), status=PLAYING)
        selection = d3.select_lookahead_policy(decision, cursor, FIX["table"])
        self.assertEqual((decision.continuation, selection.evidence, selection.premises, selection.selection_reason),
                         ("EXACT_SAFE", None, None, "NOT_A_GUESS"))
        with forbidden() as seam:
            self.assertIsNone(L.diagnose_links(selection))  # unsupported: no record at all, not "no link"
            self.refused("LINK_RECORD", L.validate_link_diagnosis, None, selection)
            self.refused("LINK_RECORD", L.validate_link_diagnosis, diagnose_free(), selection)
            for nothing in (None, decision, (), "selection"):
                self.refused("LINK_PREMISES", L.diagnose_links, nothing)
        self.assertEqual((seam.call_count, engine.steps), (0, 25))


def diagnose_free():
    """A diagnosis that needs no exact call (LC04 plans nothing); used where a kernel call is forbidden."""
    return diagnose("LC04")


if __name__ == "__main__":
    unittest.main()
