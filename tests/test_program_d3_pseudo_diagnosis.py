"""S3D3-A stage 4, diagnosis only (PAIR_MIRROR_DIAGNOSIS_V1): definition, counts, limits, errors.

Kinds of evidence, kept apart on purpose:
  * declared premises (PC*, RK*_DECLARED) -> a hand-written grid AND a
    hand-declared M and hand-declared exact counts go into the unchanged
    stage-2 ``decide`` and then into the diagnosis. The probability kernel is
    the real one; no session and no Engine is involved. A declared M was not
    obtained from a real game. 'M' in a picture is a hidden cell of that M.
  * kernel stand-ins -> the diagnosis module's single seam is replaced by a
    declared result or exception. Error tests only.
  * tampered records -> a real diagnosis with one value changed.
Expected values were fixed by hand beforehand (fixed/PSEUDO_CASES_FROM_DESIGN_01.json,
fixed/EXPECTED_ADDITIONS.json). ``Oracle`` is an independent check for these
tiny grids only: it tries every subset of the unresolved cells against every
revealed number and shares no code with the kernel. Whole-game win rates of
the design cases are NOT outputs of the module and are not tested here.
"""

import ast
from dataclasses import fields, replace
from itertools import combinations
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import simple_probability
from core_engine import CellState
from experiments import program_d3_forced_pair_policy as stage1
from experiments import program_d3_guess_record as record
from experiments import program_d3_lookahead_policy as policy
from experiments import program_d3_pseudo_diagnosis as pseudo
from experiments.program_k_policy import KPolicyIntegrityError
from simple_algorithm import InconsistentObservationError
from stage3_physical import load_timing_table


H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)
MINE, NUMBER, OPENABLE = "PROVEN_MINE", "REVEALED_NUMBER", "UNRESOLVED_HIDDEN"
PROVEN, FAILED, WAITING = "MIRROR_PROVEN", "CONDITION_FAILED", "NOT_EXAMINED_CALL_LIMIT"
P2_NONE, P2_OK, P2_BAD, P2_MARGIN = (
    "HOLDS_NO_UNRESOLVED_CELL", "HOLDS_BY_WORLD_COUNT", "FAILS_BY_WORLD_COUNT", "FAILS_BY_MARGINAL")
P3_OK, P3_BAD, P3_MARGIN = "HOLDS_BY_WORLD_COUNT", "FAILS_BY_WORLD_COUNT", "FAILS_BY_MARGINAL"
COUNTED, MARGINALS, GEOMETRY = "CONDITIONAL_COUNTS", "MARGINALS", "GEOMETRY"
REFUTED, UNDECIDED, NO_PAIR = "REFUTED_IN_SUPPORTED_RANGE", "UNDECIDED_CALL_LIMIT", "NO_PAIR_IN_RANGE"


def reading(cell):
    return cell[1], cell[0]


def declared(rows, num_mines, counts, total, g0, cursor=(0, 0)):
    """Declared premises: 'H' an unresolved hidden cell, 'M' a hidden cell of the declared M."""
    pictures = [row.split() for row in rows]
    observation = tuple(tuple(H if v in ("H", "M") else int(v) for v in row) for row in pictures)
    mines = frozenset((x, y) for y, row in enumerate(pictures) for x, v in enumerate(row) if v == "M")
    hidden = frozenset((x, y) for y, row in enumerate(observation) for x, v in enumerate(row) if v == H)
    ordered = tuple(sorted(hidden - mines, key=reading))
    table = counts if isinstance(counts, dict) else {cell: counts for cell in ordered}
    return policy.GuessPremises(observation, num_mines, mines, hidden - mines, total,
                                tuple((cell, table[cell]) for cell in ordered), g0, cursor)


# Hand-declared cases (grid, mine total, exact counts, Z, K-LC1 target).
PC01 = declared(("H H M", "1 H M"), 3, 1, 3, (0, 0))
PC02 = declared(("H H M", "1 3 M"), 3, 1, 2, (0, 0), cursor=(0, 1))
PC03 = declared(("H 1 H 1 H M H",), 3, 1, 2, (0, 0))
PC04 = declared(("H M H M M", "M 5 M H H", "M H 3 M M"), 10,
                {(0, 0): 1, (2, 0): 1, (3, 1): 2, (4, 1): 1, (1, 2): 1}, 3, (0, 0))
PC05 = declared(("M H M", "H 3 H"), 3, 1, 3, (1, 0))
PC06 = declared(("H H H", "H 3 M"), 3, 3, 6, (0, 0))
PC06B = declared(("H H M", "2 H M"), 4, 2, 3, (0, 0))
PC09 = declared(("H H H M 2 M",), 3, 1, 3, (0, 0))
PC09_FOUR = declared(("H H H M 2 M",), 4, 2, 3, (0, 0))
PC10A = declared(("H H H H H H H H H M 2 M",), 3, 1, 9, (0, 0))
PC10B = declared(("H H H H H H H H H H M 2 M",), 3, 1, 10, (0, 0))
PC13 = declared(("H M 2 M H",), 3, 1, 2, (0, 0), cursor=(2, 0))
# The public states of two real decisions, DECLARED here (the real ones are in the runner tests).
RK02_DECLARED = declared(("0 0 1 H H H", "0 0 1 H H H"), 2,
                         {(3, 0): 4, (4, 0): 2, (5, 0): 2, (3, 1): 4, (4, 1): 2, (5, 1): 2}, 8, (4, 0))
RK04_DECLARED = declared(("M 3 1", "M H H", "H H H"), 4,
                         {(1, 1): 3, (2, 1): 3, (0, 2): 2, (1, 2): 2, (2, 2): 2}, 6, (0, 2), cursor=(2, 0))
ALL_CASES = {"PC01": PC01, "PC02": PC02, "PC03": PC03, "PC04": PC04, "PC05": PC05, "PC06": PC06,
             "PC06B": PC06B, "PC09": PC09, "PC09_FOUR": PC09_FOUR, "PC10A": PC10A, "PC10B": PC10B,
             "PC13": PC13, "RK02_DECLARED": RK02_DECLARED, "RK04_DECLARED": RK04_DECLARED}


class Oracle:
    """Independent enumeration for a tiny declared grid. Every subset of the unresolved cells
    with the right size is tried against every revealed number; nothing of the kernel is used."""

    def __init__(self, premises):
        self.grid = premises.observation
        self.height, self.width = len(self.grid), len(self.grid[0])
        self.mines = premises.mines
        self.cells = sorted(premises.unresolved, key=reading)
        budget = premises.num_mines - len(self.mines)
        self.worlds = [frozenset(world) for world in combinations(self.cells, budget)
                       if self.fits(frozenset(world))]

    def near(self, cell):
        x, y = cell
        return [(x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dx, dy) != (0, 0) and 0 <= x + dx < self.width and 0 <= y + dy < self.height]

    def fits(self, world):
        for y, row in enumerate(self.grid):
            for x, value in enumerate(row):
                if 0 <= value <= 8:
                    if sum(1 for cell in self.near((x, y)) if cell in world or cell in self.mines) != value:
                        return False
        return True

    def count(self, *mine_cells, safe=()):
        return sum(1 for world in self.worlds
                   if all(cell in world for cell in mine_cells) and not any(cell in world for cell in safe))

    def distinguishing(self, g, h):
        return [(x, y) for y in range(self.height) for x in range(self.width)
                if (x, y) not in (g, h) and ((x, y) in self.near(g)) != ((x, y) in self.near(h))]

    def mirror(self, g, h):
        """(P1, P2, P3) of the definition, read off the list of worlds."""
        cells = self.distinguishing(g, h)
        p1 = not any(0 <= self.grid[y][x] <= 8 for x, y in cells)
        p2 = all(self.count(g, safe=(cell,)) == 0 for cell in cells if cell in self.cells)
        return p1, p2, self.count(g, h) == 0


class Calls:
    """Counts the calls that leave through one module's kernel seam."""

    def __init__(self, module):
        self.count, self.grids, self.original = 0, [], module._kernel

    def __call__(self, observation, num_mines):
        self.count += 1
        self.grids.append((observation, num_mines))
        return self.original(observation, num_mines)


def pseudo_calls():
    return patch.object(pseudo, "_kernel", Calls(pseudo))


def lookahead_calls():
    return patch.object(policy, "_kernel", Calls(policy))


def fake(total, rows):
    """A kernel stand-in result: declared numbers, no validation of its own."""
    return SimpleNamespace(total_worlds=total, probabilities=tuple(
        SimpleNamespace(coordinate=cell, mine_worlds=count, total_worlds=total) for cell, count in rows))


class DiagnosisCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def diag(self, premises):
        """The unchanged stage-2 decision of declared premises, then its diagnosis."""
        selection = policy.decide(premises, self.table)
        return selection, pseudo.diagnose_pseudo(selection)

    def check(self, diagnosis, a, b):
        return next(c for c in diagnosis.checks if (c.a, c.b) == (a, b))

    def cell(self, diagnosis, cell):
        return next(row for row in diagnosis.cells if row.cell == cell)

    def code(self, function, *args, **kwargs):
        with self.assertRaises(KPolicyIntegrityError) as caught:
            function(*args, **kwargs)
        return caught.exception.code


class MirrorDefinitionTests(DiagnosisCase):
    def test_m01_m6_cells_are_mirror_proven_with_both_partners(self):
        g, h, x = (0, 0), (1, 0), (1, 1)
        selection, d = self.diag(PC01)
        self.assertEqual((selection.target, selection.selection_reason, selection.evidence.kind),
                         (g, "K_LC1_GUESS_KEPT", "MIN_RISK"))
        self.assertEqual((d.scope, d.actual_target, d.original_target, d.limits, d.anchors, d.planned_calls,
                          d.actual_calls, d.search_status),
                         ("PAIR_MIRROR_DIAGNOSIS_V1", g, g, (2, 8, 8), (g, h), 2, 2, "COMPLETE_SUPPORTED_RANGE"))
        self.assertEqual(d.counts, pseudo.PairCounts(3, 0, 0, 3, 3, 0))
        self.assertEqual(d.conditionals, (pseudo.ConditionalCounts(g, 1, ((h, 0), (x, 0))),
                                          pseudo.ConditionalCounts(h, 1, ((g, 0), (x, 0)))))
        walls = (((2, 0), MINE), ((2, 1), MINE))
        self.assertEqual(d.checks, (
            pseudo.MirrorCheck(g, h, walls, True, "HOLDS", P2_NONE, P3_OK, COUNTED, g, 0, (), PROVEN),
            pseudo.MirrorCheck(g, x, walls, True, "HOLDS", P2_NONE, P3_OK, COUNTED, g, 0, (), PROVEN),
            pseudo.MirrorCheck(h, x, (), True, "HOLDS", P2_NONE, P3_OK, COUNTED, h, 0, (), PROVEN)))
        self.assertEqual(d.cells, (
            pseudo.CellDiagnosis(g, 1, False, PROVEN, (h, x), 2, 2, 0, 0),
            pseudo.CellDiagnosis(h, 1, False, PROVEN, (g, x), 2, 2, 0, 0),
            pseudo.CellDiagnosis(x, 1, False, PROVEN, (g, h), 2, 2, 0, 0)))
        self.assertEqual((d.target_status, d.target_bound, d.forced_pairs), (PROVEN, (1, 3), ()))

    def test_m02_m12_an_open_number_next_to_one_cell_fails_p1_and_costs_no_call(self):
        g, h, k, z = (0, 0), (2, 0), (4, 0), (6, 0)
        with pseudo_calls() as calls:
            selection, d = self.diag(PC03)
            self.assertEqual(calls.count, 0)
        self.assertEqual((d.counts, d.anchors, d.conditionals, d.planned_calls, d.actual_calls, d.search_status),
                         (pseudo.PairCounts(3, 3, 0, 0, 0, 0), (), (), 0, 0, "NO_CANDIDATE_PAIR"))
        self.assertEqual(self.check(d, g, h), pseudo.MirrorCheck(
            g, h, (((3, 0), NUMBER),), False, "FAILS", "NOT_EVALUATED", "NOT_EVALUATED", GEOMETRY, None, None,
            (), FAILED))
        self.assertTrue(d.checks and all(c.p1 == "FAILS" and c.decided_by == GEOMETRY for c in d.checks))
        self.assertEqual([(row.cell, row.status, row.pairs_in_range, row.floating,
                           row.floating_cells_out_of_range) for row in d.cells],
                         [(g, REFUTED, 1, False, 0), (h, REFUTED, 2, False, 0), (k, REFUTED, 2, False, 0),
                          (z, REFUTED, 1, True, 0)])
        self.assertEqual((d.target_status, d.target_bound), (REFUTED, None))
        # By the definition alone: only P1 fails for (g, h); P2 has nothing to check and P3 holds.
        self.assertEqual(Oracle(PC03).mirror(g, h), (False, True, True))

    def test_m03_a_distinguishing_cell_that_can_be_safe_fails_p2(self):
        p, q, r = (1, 0), (0, 1), (2, 1)
        selection, d = self.diag(PC05)
        self.assertEqual((selection.target, selection.selection_reason, selection.original_target),
                         (q, "TIE_LOOKAHEAD", p))
        self.assertEqual((d.anchors, d.planned_calls, d.counts, d.search_status),
                         ((q, p), 2, pseudo.PairCounts(3, 0, 0, 3, 3, 0), "COMPLETE_SUPPORTED_RANGE"))
        self.assertEqual(d.conditionals, (pseudo.ConditionalCounts(q, 1, ((p, 0), (r, 0))),
                                          pseudo.ConditionalCounts(p, 1, ((q, 0), (r, 0)))))
        self.assertEqual(d.checks, (
            pseudo.MirrorCheck(p, q, (((2, 0), MINE), (r, OPENABLE)), False, "HOLDS", P2_BAD, P3_OK, COUNTED,
                               q, 0, ((r, 0, 1),), FAILED),
            pseudo.MirrorCheck(p, r, (((0, 0), MINE), (q, OPENABLE)), False, "HOLDS", P2_BAD, P3_OK, COUNTED,
                               p, 0, ((q, 0, 1),), FAILED),
            pseudo.MirrorCheck(q, r, (((0, 0), MINE), ((2, 0), MINE)), True, "HOLDS", P2_NONE, P3_OK, COUNTED,
                               q, 0, (), PROVEN)))
        self.assertEqual([(row.cell, row.status, row.partners) for row in d.cells],
                         [(p, REFUTED, ()), (q, PROVEN, (r,)), (r, PROVEN, (q,))])
        self.assertEqual((d.target_status, d.target_bound), (PROVEN, (1, 3)))

    def test_m04_m13_a_joint_mine_world_fails_p3_by_count_or_by_marginal(self):
        g, h, y, x = (0, 0), (1, 0), (2, 0), (0, 1)
        with pseudo_calls() as calls:
            selection, d = self.diag(PC06)
            self.assertEqual(calls.count, 3)
        self.assertEqual((d.counts, d.planned_calls, len(d.anchors), d.search_status),
                         (pseudo.PairCounts(6, 0, 0, 6, 6, 0), 3, 3, "COMPLETE_SUPPORTED_RANGE"))
        self.assertEqual(len(d.checks), 6)
        for check in d.checks:
            self.assertEqual((check.p1, check.p3, check.joint_mine_worlds, check.decided_by, check.verdict),
                             ("HOLDS", P3_BAD, 1, COUNTED, FAILED))
        only_p3 = self.check(d, g, x)  # nothing distinguishes g and x: P2 has no cell, P3 alone fails
        self.assertEqual((only_p3.distinguishing, only_p3.isolated, only_p3.p2, only_p3.p2_rows),
                         ((), True, P2_NONE, ()))
        self.assertEqual(self.check(d, g, h).p2, P2_BAD)
        for conditional in d.conditionals:
            self.assertEqual((conditional.total_worlds, sorted(count for _, count in conditional.mine_worlds)),
                             (3, [1, 1, 1]))
        self.assertEqual({row.status for row in d.cells}, {REFUTED})
        # The same failure decided by the marginal counts alone: no call at all.
        with pseudo_calls() as calls:
            selection, marginal = self.diag(PC06B)
            self.assertEqual(calls.count, 0)
        self.assertEqual((marginal.counts, marginal.planned_calls, marginal.search_status),
                         (pseudo.PairCounts(3, 0, 3, 0, 0, 0), 0, "NO_CANDIDATE_PAIR"))
        self.assertEqual([(c.p1, c.p2, c.p3, c.decided_by, c.anchor, c.joint_mine_worlds, c.verdict)
                          for c in marginal.checks],
                         [("HOLDS", "NOT_EVALUATED", P3_MARGIN, MARGINALS, None, None, FAILED)] * 3)
        oracle = Oracle(PC06B)
        self.assertEqual([oracle.count(c.a, c.b) for c in marginal.checks], [1, 1, 1])

    def test_m05_a_forced_pair_in_range_is_proven_and_marked_as_the_same_pair(self):
        a, b = (0, 0), (1, 0)
        selection, d = self.diag(PC02)
        self.assertEqual((selection.selection_reason, selection.evidence.kind,
                          [(p.a, p.b, p.verdict) for p in selection.pair_proofs]),
                         ("FORCED_5050_FIRST", "FORCED_5050", [(a, b, "FORCED_5050")]))
        self.assertEqual((d.anchors, d.planned_calls, d.counts),
                         ((selection.target,), 1, pseudo.PairCounts(1, 0, 0, 1, 1, 0)))
        check = self.check(d, a, b)
        self.assertEqual((check.distinguishing, check.isolated, check.p2, check.p3, check.joint_mine_worlds,
                          check.verdict),
                         ((((2, 0), MINE), ((2, 1), MINE)), True, P2_NONE, P3_OK, 0, PROVEN))
        self.assertEqual((d.forced_pairs, d.target_status, d.target_bound),
                         (((a, b, "SAME_PAIR_MIRROR_PROVEN"),), PROVEN, (1, 2)))
        self.assertEqual((d.actual_selection_reason, d.actual_kind), ("FORCED_5050_FIRST", "FORCED_5050"))
        self.assertEqual([row.status for row in d.cells], [PROVEN, PROVEN])

    def test_m05_a_far_forced_pair_stays_forced_but_is_neither_examined_nor_proven(self):
        g, h = (0, 0), (4, 0)
        with pseudo_calls() as calls:
            selection, d = self.diag(PC13)
            self.assertEqual(calls.count, 0)
        # The existing judgement is untouched: LAST_MINE ground, both distinguishing cells in M.
        proof = selection.pair_proofs[0]
        self.assertEqual((len(selection.pair_proofs), proof.a, proof.b, proof.bases, proof.distinguishing,
                          proof.verdict, selection.selection_reason, selection.evidence.kind),
                         (1, g, h, (stage1.LAST_MINE,), (((1, 0), MINE), ((3, 0), MINE)), "FORCED_5050",
                          "FORCED_5050_FIRST", "FORCED_5050"))
        # The diagnosis does not examine a pair at distance 4 and records that, not a verdict.
        self.assertEqual((d.checks, d.counts, d.anchors, d.conditionals, d.planned_calls, d.search_status),
                         ((), pseudo.PairCounts(0, 0, 0, 0, 0, 0), (), (), 0, "NO_CANDIDATE_PAIR"))
        self.assertEqual(d.cells, (pseudo.CellDiagnosis(g, 1, True, NO_PAIR, (), 0, 0, 0, 1),
                                   pseudo.CellDiagnosis(h, 1, True, NO_PAIR, (), 0, 0, 0, 1)))
        self.assertEqual((d.target_status, d.target_bound, d.forced_pairs),
                         (NO_PAIR, None, ((g, h, "OUT_OF_RANGE_NOT_EXAMINED"),)))
        self.assertEqual((d.actual_selection_reason, d.actual_kind, pseudo.PSEUDO_RANGE),
                         ("FORCED_5050_FIRST", "FORCED_5050", 2))

    def test_m06_the_bound_is_a_lower_bound_and_no_win_rate_is_computed(self):
        selection, d = self.diag(PC01)
        self.assertEqual((d.target_bound, pseudo.BOUND_MEANING, pseudo.RISK_MEANING),
                         ((1, 3), "WHOLE_GAME_NOT_WIN_LOWER_BOUND_NOT_OPTIMALITY", "CURRENT_INPUT_RISK"))
        # PC04: both cells of the pair carry the same bound; nothing ranks one above the other.
        g, h = (0, 0), (2, 0)
        selection, d4 = self.diag(PC04)
        rows = {row.cell: row for row in d4.cells}
        self.assertEqual((rows[g].status, rows[h].status, rows[g].mine_worlds, rows[h].mine_worlds,
                          d4.target_bound), (PROVEN, PROVEN, 1, 1, (1, 3)))
        names = [field.name for kind in (pseudo.PseudoDiagnosis, pseudo.CellDiagnosis, pseudo.MirrorCheck,
                                         pseudo.ConditionalCounts, pseudo.PairCounts, pseudo.PseudoPlan)
                 for field in fields(kind)]
        self.assertFalse([name for name in names
                          if any(word in name for word in ("win", "rate", "optimal", "score", "s_c", "s_v"))])

    def test_m07_adjacent_cells_are_not_their_own_distinguishing_cells(self):
        g, h = (0, 0), (1, 0)
        selection, d = self.diag(PC01)
        check = self.check(d, g, h)
        self.assertEqual(max(abs(g[0] - h[0]), abs(g[1] - h[1])), 1)
        self.assertNotIn(g, [cell for cell, _ in check.distinguishing])
        self.assertNotIn(h, [cell for cell, _ in check.distinguishing])
        self.assertEqual((check.p2, check.verdict), (P2_NONE, PROVEN))
        # Had h been taken as a cell next to g only, P2 would ask for "g mine implies h mine":
        conditional = d.conditionals[0]
        self.assertEqual((conditional.anchor, conditional.total_worlds - dict(conditional.mine_worlds)[h]), (g, 1))

    def test_m11_an_unresolved_distinguishing_cell_can_satisfy_p2_by_world_count(self):
        g, h, d_cell, z, a = (0, 0), (2, 0), (3, 1), (4, 1), (1, 2)
        selection, d = self.diag(PC04)
        self.assertEqual((selection.target, selection.selection_reason, selection.original_target),
                         (h, "TIE_LOOKAHEAD", g))
        self.assertEqual((d.anchors, d.planned_calls, d.counts, d.search_status),
                         ((h,), 1, pseudo.PairCounts(7, 6, 0, 1, 1, 0), "COMPLETE_SUPPORTED_RANGE"))
        self.assertEqual(d.conditionals,
                         (pseudo.ConditionalCounts(h, 1, ((g, 0), (d_cell, 1), (z, 0), (a, 0))),))
        self.assertEqual(self.check(d, g, h), pseudo.MirrorCheck(
            g, h, (((3, 0), MINE), ((0, 1), MINE), ((2, 1), MINE), (d_cell, OPENABLE)), False, "HOLDS", P2_OK,
            P3_OK, COUNTED, h, 0, ((d_cell, 1, 0),), PROVEN))
        self.assertEqual(len(d.checks), 5)  # (g,h) and the four P1 failures that touch the target or g0
        self.assertEqual([(row.cell, row.status, row.partners, row.pairs_in_range, row.candidate_pairs,
                           row.floating) for row in d.cells],
                         [(g, PROVEN, (h,), 2, 1, False), (h, PROVEN, (g,), 4, 1, False),
                          (d_cell, REFUTED, (), 3, 0, False), (z, REFUTED, (), 2, 0, True),
                          (a, REFUTED, (), 3, 0, False)])
        self.assertEqual((d.target_status, d.target_bound, d.forced_pairs), (PROVEN, (1, 3), ()))

    def test_m14_the_total_mine_count_decides_the_verdict(self):
        g, h, w = (0, 0), (1, 0), (2, 0)
        selection, d = self.diag(PC09)
        self.assertEqual((selection.target, selection.selection_reason, d.anchors, d.planned_calls),
                         (g, "K_LC1_GUESS_KEPT", (g, h), 2))
        self.assertEqual(d.checks, (
            pseudo.MirrorCheck(g, h, ((w, OPENABLE),), False, "HOLDS", P2_BAD, P3_OK, COUNTED, g, 0,
                               ((w, 0, 1),), FAILED),
            pseudo.MirrorCheck(g, w, (((3, 0), MINE),), True, "HOLDS", P2_NONE, P3_OK, COUNTED, g, 0, (), PROVEN),
            pseudo.MirrorCheck(h, w, ((g, OPENABLE), ((3, 0), MINE)), False, "HOLDS", P2_BAD, P3_OK, COUNTED,
                               h, 0, ((g, 0, 1),), FAILED)))
        self.assertEqual([(row.cell, row.status, row.partners, row.floating) for row in d.cells],
                         [(g, PROVEN, (w,), True), (h, REFUTED, (), True), (w, PROVEN, (g,), True)])
        self.assertEqual((d.target_status, d.target_bound), (PROVEN, (1, 3)))
        # The same public grid with one more mine: every pair fails P3, known from the marginals.
        with pseudo_calls() as calls:
            selection, four = self.diag(PC09_FOUR)
            self.assertEqual(calls.count, 0)
        self.assertEqual(PC09_FOUR.observation, PC09.observation)
        self.assertEqual((four.counts, four.search_status, four.target_status, four.target_bound,
                          {c.p3 for c in four.checks}, {row.status for row in four.cells}),
                         (pseudo.PairCounts(3, 0, 3, 0, 0, 0), "NO_CANDIDATE_PAIR", REFUTED, None, {P3_MARGIN},
                          {REFUTED}))


class CountAndSymmetryTests(DiagnosisCase):
    def test_m08_conditional_counts_equal_an_independent_enumeration(self):
        self.assertEqual(len(ALL_CASES), 14)
        for name, premises in ALL_CASES.items():
            with self.subTest(case=name):
                oracle = Oracle(premises)
                self.assertEqual((len(oracle.worlds), tuple((c, oracle.count(c)) for c in oracle.cells)),
                                 (premises.total_worlds, premises.mine_worlds))
                selection, d = self.diag(premises)
                budget = premises.num_mines - len(premises.mines)
                marginal = dict(premises.mine_worlds)
                for conditional in d.conditionals:
                    g = conditional.anchor
                    self.assertEqual(conditional.total_worlds, oracle.count(g))  # Z' = Z_g
                    self.assertEqual(conditional.mine_worlds,
                                     tuple((c, oracle.count(g, c)) for c in oracle.cells if c != g))
                    self.assertEqual(sum(count for _, count in conditional.mine_worlds),
                                     (budget - 1) * conditional.total_worlds)
                    self.assertTrue(all(count <= marginal[c] for c, count in conditional.mine_worlds))

    def test_m09_one_conditional_call_serves_every_pair_of_its_anchor(self):
        expected = {"PC01": (2, 3), "PC09": (2, 3), "RK02_DECLARED": (4, 7)}
        self.assertEqual(len(expected), 3)
        for name, (anchors, decided) in expected.items():
            with self.subTest(case=name):
                with pseudo_calls() as calls:
                    selection, d = self.diag(ALL_CASES[name])
                    made = calls.count
                self.assertEqual((made, d.planned_calls, d.actual_calls, len(d.anchors), len(d.conditionals),
                                  d.counts.decided), (anchors, anchors, anchors, anchors, anchors, decided))
        selection, d = self.diag(RK02_DECLARED)
        self.assertEqual((selection.target, d.anchors), ((3, 0), ((3, 0), (4, 0), (5, 0), (4, 1))))
        self.assertEqual([(c.a, c.b, c.verdict) for c in d.checks if c.anchor == (4, 0)],
                         [((4, 0), (5, 0), FAILED), ((4, 0), (4, 1), PROVEN), ((4, 0), (5, 1), FAILED)])

    def test_m10_marginal_exclusions_agree_with_the_enumeration(self):
        self.assertEqual(len(ALL_CASES), 14)
        by_marginal = {}
        for name, premises in ALL_CASES.items():
            with self.subTest(case=name):
                oracle = Oracle(premises)
                selection, d = self.diag(premises)
                plan = pseudo.plan_pseudo(premises, selection.target)
                recorded = {(c.a, c.b): c for c in d.checks}
                for planned in plan.pairs:
                    truth = oracle.mirror(planned.a, planned.b)
                    self.assertEqual(planned.p1 == "HOLDS", truth[0])  # geometry, both ways
                    final = recorded.get((planned.a, planned.b), planned)
                    if final.decided_by == MARGINALS:
                        by_marginal.setdefault(name, []).append((final.p2, final.p3))
                        self.assertFalse(all(truth))
                        self.assertFalse(final.p3 == P3_MARGIN and truth[2])
                        self.assertFalse(final.p2 == P2_MARGIN and truth[1])
                    elif final.decided_by == COUNTED:
                        self.assertEqual(final.verdict == PROVEN, all(truth))
                        self.assertEqual((final.p2 in (P2_NONE, P2_OK), final.p3 == P3_OK), truth[1:])
                    elif final.decided_by == GEOMETRY:
                        self.assertFalse(truth[0])
        self.assertEqual(by_marginal, {"PC06B": [("NOT_EVALUATED", P3_MARGIN)] * 3,
                                       "PC09_FOUR": [("NOT_EVALUATED", P3_MARGIN)] * 3,
                                       "RK04_DECLARED": [(P2_MARGIN, "NOT_EVALUATED")]})

    def test_m17_verdicts_do_not_depend_on_which_cell_is_the_anchor(self):
        names = ("PC01", "PC02", "PC04", "PC05", "PC06", "PC09", "PC10A", "RK02_DECLARED", "RK04_DECLARED")
        self.assertEqual(len(names), 9)
        for name in names:
            with self.subTest(case=name):
                premises, seen, anchors = ALL_CASES[name], {}, {}
                for target in sorted(premises.unresolved, key=reading):
                    d = pseudo.diagnose_premises(premises, actual_target=target, selection_reason="DECLARED",
                                                 kind="DECLARED")
                    for c in d.checks:
                        if c.decided_by == COUNTED:
                            anchors.setdefault((c.a, c.b), set()).add(c.anchor)
                            verdict = (c.verdict, c.joint_mine_worlds, c.p2, c.p3)
                            self.assertEqual(seen.setdefault((c.a, c.b), verdict), verdict)
                    marginal = dict(premises.mine_worlds)
                    self.assertTrue(all(marginal[c.a] == marginal[c.b] for c in d.checks if c.p1 == "HOLDS"))
                self.assertTrue(seen)
                # Every candidate pair was judged from both of its cells at least once.
                self.assertTrue(all(found == {pair[0], pair[1]} for pair, found in anchors.items()))

    def test_m17_the_representative_anchor_is_the_first_in_call_order(self):
        g, h, x = (0, 0), (1, 0), (1, 1)
        with pseudo_calls() as calls:
            first = pseudo.diagnose_premises(PC01, actual_target=g, selection_reason="DECLARED", kind="DECLARED")
            again = pseudo.diagnose_premises(PC01, actual_target=g, selection_reason="DECLARED", kind="DECLARED")
            other = pseudo.diagnose_premises(PC01, actual_target=h, selection_reason="DECLARED", kind="DECLARED")
            self.assertEqual(calls.count, 6)  # two anchors each time; the cross-check costs no call
        self.assertEqual((first, first.anchors, [(c.a, c.b, c.anchor) for c in first.checks]),
                         (again, (g, h), [(g, h, g), (g, x, g), (h, x, h)]))
        self.assertEqual((other.anchors, [(c.a, c.b, c.anchor) for c in other.checks]),
                         ((h, g), [(g, h, h), (g, x, g), (h, x, h)]))
        self.assertEqual([c.verdict for c in other.checks], [c.verdict for c in first.checks])
        # Both cells of (g, h) are anchors in PC06 with target g. If the second count tells another
        # story, that is an error; the record is not adjusted to either side.
        g, h, y, x = (0, 0), (1, 0), (2, 0), (0, 1)
        real = pseudo._kernel

        def lopsided(observation, num_mines):
            if observation[h[1]][h[0]] == F:  # the call that has h as its flagged anchor
                return fake(3, ((g, 0), (y, 2), (x, 1)))
            return real(observation, num_mines)

        with patch.object(pseudo, "_kernel", lopsided):
            self.assertEqual(self.code(pseudo.diagnose_premises, PC06, actual_target=g,
                                       selection_reason="DECLARED", kind="DECLARED"), "PSEUDO_WORLD_COUNT")


class LimitTests(DiagnosisCase):
    def test_m15_eight_anchors_exactly_then_one_pair_left_unexamined(self):
        eight = tuple((x, 0) for x in range(8))
        with pseudo_calls() as calls:
            selection, nine = self.diag(PC10A)
            self.assertEqual(calls.count, 8)
        self.assertEqual((selection.lookahead_status, selection.target),
                         ("NOT_COMPUTED_CANDIDATE_LIMIT", (0, 0)))
        self.assertEqual((nine.anchors, nine.planned_calls, nine.actual_calls, nine.counts, nine.search_status),
                         (eight, 8, 8, pseudo.PairCounts(15, 0, 0, 15, 15, 0), "COMPLETE_SUPPORTED_RANGE"))
        self.assertEqual({(c.p3, c.p2, c.verdict) for c in nine.checks}, {(P3_OK, P2_BAD, FAILED)})
        self.assertEqual([row.status for row in nine.cells], [REFUTED] * 9)
        self.assertNotIn((8, 0), nine.anchors)  # decided through its partners' calls
        self.assertEqual((self.cell(nine, (0, 0)).floating_cells_out_of_range, nine.target_status,
                          nine.target_bound), (6, REFUTED, None))
        with pseudo_calls() as calls:
            selection, ten = self.diag(PC10B)
            self.assertEqual(calls.count, 8)  # never a ninth
        self.assertEqual((ten.anchors, ten.planned_calls, ten.actual_calls, ten.counts, ten.search_status),
                         (eight, 8, 8, pseudo.PairCounts(17, 0, 0, 17, 16, 1), "PARTIAL_CALL_LIMIT"))
        self.assertEqual(self.check(ten, (8, 0), (9, 0)), pseudo.MirrorCheck(
            (8, 0), (9, 0), (((7, 0), OPENABLE), ((10, 0), MINE)), False, "HOLDS", "NOT_EVALUATED",
            "NOT_EVALUATED", "NOT_DECIDED", None, None, (), WAITING))
        self.assertEqual([row.status for row in ten.cells], [REFUTED] * 8 + [UNDECIDED, UNDECIDED])
        self.assertEqual([(row.not_examined_pairs, row.candidate_pairs) for row in ten.cells[8:]],
                         [(1, 3), (1, 2)])
        self.assertEqual(self.cell(ten, (0, 0)).floating_cells_out_of_range, 7)

    def test_m16_unexamined_and_out_of_range_are_not_condition_failures(self):
        selection, ten = self.diag(PC10B)
        waiting = self.check(ten, (8, 0), (9, 0))
        self.assertNotEqual(waiting.verdict, FAILED)
        self.assertEqual((waiting.p2, waiting.p3, waiting.joint_mine_worlds, waiting.p2_rows),
                         ("NOT_EVALUATED", "NOT_EVALUATED", None, ()))
        # By the definition the unexamined pair is in fact no mirror; the record still says "not examined".
        self.assertFalse(all(Oracle(PC10B).mirror((8, 0), (9, 0))))
        self.assertEqual((self.cell(ten, (9, 0)).status, ten.search_status), (UNDECIDED, "PARTIAL_CALL_LIMIT"))
        selection, far = self.diag(PC13)
        self.assertEqual(([row.status for row in far.cells], far.checks, far.forced_pairs[0][2]),
                         ([NO_PAIR, NO_PAIR], (), "OUT_OF_RANGE_NOT_EXAMINED"))
        self.assertEqual(len({pseudo.CELL_PROVEN, pseudo.CELL_REFUTED, pseudo.CELL_UNDECIDED,
                              pseudo.CELL_NO_PAIR}), 4)
        self.assertEqual(len({pseudo.MIRROR_PROVEN, pseudo.CONDITION_FAILED, pseudo.NOT_EXAMINED}), 3)
        self.assertEqual(len({pseudo.FORCED_SAME, pseudo.FORCED_OUT_OF_RANGE, pseudo.FORCED_NOT_EXAMINED}), 3)
        texts = [value for name, value in vars(pseudo).items() if name.isupper() and isinstance(value, str)]
        self.assertFalse([text for text in texts if "NOT_PSEUDO" in text or "NOT_A_MIRROR" in text])
        # A refuted cell with floating cells beyond the range is refuted in the supported range only.
        self.assertEqual((self.cell(ten, (0, 0)).status, self.cell(ten, (0, 0)).floating_cells_out_of_range),
                         (REFUTED, 7))

    def test_m26_planned_calls_are_fixed_before_the_first_call_and_counted_apart(self):
        with lookahead_calls() as stage2, pseudo_calls() as stage4, \
                patch("simple_probability.calculate_probabilities",
                      wraps=simple_probability.calculate_probabilities) as kernel:
            selection = policy.decide(PC04, self.table)
            self.assertEqual((stage2.count, stage4.count, kernel.call_count, selection.planned_calls,
                              selection.actual_calls), (6, 0, 6, 6, 6))
            plan = pseudo.plan_pseudo(PC04, selection.target)
            self.assertEqual((plan.anchors, plan.planned_calls, stage2.count, stage4.count, kernel.call_count),
                             (((2, 0),), 1, 6, 0, 6))
            d = pseudo.diagnose_pseudo(selection)
            self.assertEqual((stage2.count, stage4.count, kernel.call_count, d.planned_calls, d.actual_calls),
                             (6, 1, 7, 1, 1))
            pseudo.validate_pseudo_diagnosis(d, selection)
            self.assertEqual((stage2.count, stage4.count, kernel.call_count), (6, 1, 7))
        self.assertTrue(d.planned_calls <= pseudo.PSEUDO_CALL_LIMIT == 8 and selection.planned_calls <= 72)
        with patch.object(pseudo, "_kernel", side_effect=AssertionError("a call before the plan is fixed")):
            self.assertEqual(pseudo.plan_pseudo(PC10B, (0, 0)).planned_calls, 8)


class IntegrityTests(DiagnosisCase):
    def test_m20_wrong_conditional_results_are_errors_not_verdicts(self):
        g, h, x = (0, 0), (1, 0), (1, 1)
        zero = InconsistentObservationError("declared: no world")
        boom = ValueError("declared: another failure")
        cases = {
            "the total is not Z_g": (PC01, fake(2, ((h, 0), (x, 0))), "PSEUDO_WORLD_COUNT"),
            "a cell is missing": (PC01, fake(1, ((h, 0),)), "PSEUDO_KERNEL_RESULT"),
            "the flagged anchor is listed": (PC01, fake(1, ((g, 0), (h, 0), (x, 0))), "PSEUDO_KERNEL_RESULT"),
            "a count is a float": (PC01, fake(1, ((h, 0.0), (x, 0))), "PSEUDO_KERNEL_RESULT"),
            "a count is a boolean": (PC01, fake(1, ((h, False), (x, 0))), "PSEUDO_KERNEL_RESULT"),
            "the total is a float": (PC01, fake(1.0, ((h, 0), (x, 0))), "PSEUDO_KERNEL_RESULT"),
            "a count above the conditional total": (PC01, fake(1, ((h, 2), (x, 0))), "PSEUDO_KERNEL_RESULT"),
            "a negative count": (PC01, fake(1, ((h, -1), (x, 0))), "PSEUDO_KERNEL_RESULT"),
            "a cell twice": (PC01, fake(1, ((h, 0), (h, 0), (x, 0))), "PSEUDO_KERNEL_RESULT"),
            "a coordinate as a list": (PC01, fake(1, (([1, 0], 0), (x, 0))), "PSEUDO_KERNEL_RESULT"),
            "the sum is wrong": (PC04, fake(1, (((0, 0), 0), ((3, 1), 0), ((4, 1), 0), ((1, 2), 0))),
                                 "PSEUDO_WORLD_COUNT"),
            "a joint count above the marginal": (
                RK02_DECLARED, fake(4, (((4, 0), 3), ((5, 0), 1), ((3, 1), 0), ((4, 1), 0), ((5, 1), 0))),
                "PSEUDO_WORLD_COUNT"),
        }
        self.assertEqual(len(cases), 12)
        for name, (premises, result, code) in cases.items():
            with self.subTest(case=name):
                selection = policy.decide(premises, self.table)
                with patch.object(pseudo, "_kernel", return_value=result) as kernel:
                    self.assertEqual(self.code(pseudo.diagnose_pseudo, selection), code)
                    self.assertEqual(kernel.call_count, 1)  # stopped at the first wrong result
        selection = policy.decide(PC01, self.table)
        with patch.object(pseudo, "_kernel", side_effect=zero):
            with self.assertRaises(KPolicyIntegrityError) as caught:
                pseudo.diagnose_pseudo(selection)
        self.assertEqual((caught.exception.code, caught.exception.__cause__), ("PSEUDO_ZERO_WORLDS", zero))
        with patch.object(pseudo, "_kernel", side_effect=boom):
            with self.assertRaises(ValueError) as caught:
                pseudo.diagnose_pseudo(selection)
        self.assertIs(caught.exception, boom)  # any other failure propagates as it is

    def test_m20_a_ninth_call_or_a_call_count_mismatch_is_refused(self):
        budget = pseudo._CallBudget()
        for _ in range(8):
            budget.spend()
        self.assertEqual((budget.used, pseudo.PSEUDO_CALL_LIMIT, pseudo.PSEUDO_ANCHOR_LIMIT), (8, 8, 8))
        self.assertEqual(self.code(budget.spend), "PSEUDO_CALL_LIMIT")
        self.assertEqual(budget.used, 8)
        self.assertEqual(len(pseudo.plan_pseudo(PC10B, (0, 0)).anchors), 8)
        with pseudo_calls() as calls, patch.object(pseudo._CallBudget, "spend", lambda self: None):
            self.assertEqual(self.code(pseudo.diagnose_premises, PC01, actual_target=(0, 0),
                                       selection_reason="DECLARED", kind="DECLARED"), "PSEUDO_CALL_COUNT")
        # With a smaller limit the plan itself is refused, before any call leaves.
        with pseudo_calls() as calls, patch.object(pseudo, "PSEUDO_CALL_LIMIT", 1):
            self.assertEqual(self.code(pseudo.plan_pseudo, PC01, (0, 0)), "PSEUDO_CALL_LIMIT")
            self.assertEqual(calls.count, 0)

    def test_m20_premises_that_break_the_accounting_are_refused(self):
        g, h, x = (0, 0), (1, 0), (1, 1)
        flagged = tuple(tuple(F if (cx, cy) == (2, 0) else v for cx, v in enumerate(row))
                        for cy, row in enumerate(PC01.observation))
        ok = replace(PC01, observation=flagged)  # a flag that IS in M: same judgement as a hidden M cell
        d = pseudo.diagnose_premises(ok, actual_target=g, selection_reason="DECLARED", kind="DECLARED")
        self.assertEqual(([c.verdict for c in d.checks], d.checks[0].distinguishing),
                         ([PROVEN] * 3, (((2, 0), MINE), ((2, 1), MINE))))
        plan = lambda premises, target=g: pseudo.plan_pseudo(premises, target)
        cases = {
            "a flag that is not in M": (plan, replace(ok, mines=frozenset({(2, 1)})), "PSEUDO_ACCOUNTING"),
            "an unresolved set that is not the grid's": (plan, replace(PC01, unresolved=frozenset({g, h})),
                                                         "PSEUDO_ACCOUNTING"),
            "a mine total without a remaining mine": (plan, replace(PC01, num_mines=2), "PSEUDO_ACCOUNTING"),
            "a cell that is certainly safe": (plan, replace(PC01, mine_worlds=((g, 0), (h, 1), (x, 2))),
                                              "PSEUDO_PREMISES"),
            "a cell that is certainly a mine": (plan, replace(PC01, mine_worlds=((g, 3), (h, 1), (x, 1))),
                                                "PSEUDO_PREMISES"),
            "counts that do not add up": (plan, replace(PC01, mine_worlds=((g, 1), (h, 1), (x, 2))),
                                          "PSEUDO_WORLD_COUNT"),
            "a P1 pair with different counts": (
                plan, replace(PC06, mine_worlds=(((0, 0), 2), ((1, 0), 4), ((2, 0), 3), ((0, 1), 3))),
                "PSEUDO_WORLD_COUNT"),
            "a float count": (plan, replace(PC01, mine_worlds=((g, 1.0), (h, 1), (x, 1))), "PSEUDO_PREMISES"),
            "a boolean total": (plan, replace(PC02, total_worlds=True), "PSEUDO_PREMISES"),
            "a grid of lists": (plan, replace(PC01, observation=[list(row) for row in PC01.observation]),
                                "PSEUDO_PREMISES"),
            "no premises": (plan, None, "PSEUDO_PREMISES"),
        }
        self.assertEqual(len(cases), 11)
        for name, (function, premises, code) in cases.items():
            with self.subTest(case=name):
                with pseudo_calls() as calls:
                    self.assertEqual(self.code(function, premises), code)
                    self.assertEqual(calls.count, 0)
        declare = dict(selection_reason="DECLARED", kind="DECLARED")
        self.assertEqual(self.code(pseudo.diagnose_premises, PC01, actual_target=(2, 0), **declare),
                         "PSEUDO_PREMISES")  # the target is a cell of M
        self.assertEqual(self.code(pseudo.diagnose_premises, PC01, actual_target=g, forced_pairs=((h, g),),
                                   **declare), "PSEUDO_PREMISES")  # not in reading order
        # An existing forced pair that this diagnosis examined and found no mirror: a contradiction.
        self.assertEqual(self.code(pseudo.diagnose_premises, PC05, actual_target=(0, 1),
                                   forced_pairs=(((1, 0), (0, 1)),), **declare), "PSEUDO_FORCED_PAIR")


class RecordValidationTests(DiagnosisCase):
    def changed(self, d, index, **changes):
        return replace(d, checks=d.checks[:index] + (replace(d.checks[index], **changes),) + d.checks[index + 1:])

    def test_m21_a_changed_diagnosis_is_rejected(self):
        p, q, r = (1, 0), (0, 1), (2, 1)
        selection, d = self.diag(PC05)
        pseudo.validate_pseudo_diagnosis(d, selection)
        other_selection, other = self.diag(PC01)
        first, second = d.conditionals
        cases = {
            "a verdict": self.changed(d, 0, verdict=PROVEN),
            "P2 of a pair": self.changed(d, 0, p2=P2_OK),
            "P3 of a pair": self.changed(d, 2, p3=P3_BAD),
            "a joint count": self.changed(d, 2, joint_mine_worlds=1),
            "a P2 row": self.changed(d, 0, p2_rows=((r, 1, 0),)),
            "the anchor of a pair": self.changed(d, 0, anchor=p),
            "the isolated mark": self.changed(d, 2, isolated=False),
            "a distinguishing cell": self.changed(d, 0, distinguishing=(((2, 0), MINE),)),
            "the ground of a pair": self.changed(d, 2, decided_by=MARGINALS),
            "a pair removed": replace(d, checks=d.checks[:2]),
            "a pair twice": replace(d, checks=d.checks + d.checks[:1]),
            "the anchors": replace(d, anchors=(p, q)),
            "the order of the conditional records": replace(d, conditionals=(second, first)),
            "a conditional record removed": replace(d, conditionals=(first,)),
            "a conditional count": replace(d, conditionals=(replace(first, mine_worlds=((p, 1), (r, 0))),
                                                            second)),
            "a conditional total": replace(d, conditionals=(replace(first, total_worlds=2), second)),
            "a conditional cell": replace(d, conditionals=(replace(first, mine_worlds=((p, 0),)), second)),
            "the pair counts": replace(d, counts=replace(d.counts, decided=2)),
            "a cell status": replace(d, cells=(replace(d.cells[0], status=PROVEN),) + d.cells[1:]),
            "the partners of a cell": replace(d, cells=d.cells[:1] + (replace(d.cells[1], partners=()),)
                                              + d.cells[2:]),
            "the search status": replace(d, search_status="PARTIAL_CALL_LIMIT"),
            "the planned calls": replace(d, planned_calls=1),
            "the actual calls": replace(d, actual_calls=3),
            "the target status": replace(d, target_status=REFUTED),
            "the bound": replace(d, target_bound=(1, 2)),
            "the bound removed": replace(d, target_bound=None),
            "a forced pair added": replace(d, forced_pairs=((q, r, "SAME_PAIR_MIRROR_PROVEN"),)),
            "the scope": replace(d, scope="PAIR_MIRROR_DIAGNOSIS_V2"),
            "the limits": replace(d, limits=(3, 8, 8)),
            "the actual target": replace(d, actual_target=r),
            "the copied selection reason": replace(d, actual_selection_reason="PSEUDO_FIRST"),
            "the copied kind": replace(d, actual_kind="PSEUDO_5050"),
            "the original target": replace(d, original_target=q),
            "the premises": replace(d, premises=replace(d.premises, cursor=(1, 1))),
            "the diagnosis of another decision": other,
        }
        self.assertEqual(len(cases), 35)
        for name, bad in cases.items():
            with self.subTest(case=name):
                self.assertIn(self.code(pseudo.validate_pseudo_diagnosis, bad, selection),
                              ("PSEUDO_RECORD", "PSEUDO_WORLD_COUNT"))
        self.assertEqual(self.code(pseudo.validate_pseudo_diagnosis, self.changed(d, 0, verdict=PROVEN),
                                   selection), "PSEUDO_RECORD")
        self.assertEqual(self.code(pseudo.validate_pseudo_diagnosis, None, selection), "PSEUDO_RECORD")
        self.assertEqual(self.code(pseudo.validate_pseudo_diagnosis, d, None), "PSEUDO_RECORD")
        pseudo.validate_pseudo_diagnosis(d, selection)  # the untouched record still passes
        pseudo.validate_pseudo_diagnosis(other, other_selection)

    def test_m21_equal_values_of_another_type_are_rejected(self):
        p, q, r = (1, 0), (0, 1), (2, 1)
        selection, d = self.diag(PC05)
        first, second = d.conditionals
        cell = lambda **changes: replace(d, cells=(replace(d.cells[0], **changes),) + d.cells[1:])
        cases = {
            "planned calls as a float": replace(d, planned_calls=2.0),
            "actual calls as a float": replace(d, actual_calls=2.0),
            "a bound as a float": replace(d, target_bound=(1.0, 3)),
            "a bound as a boolean": replace(d, target_bound=(True, 3)),
            "a limit as a float": replace(d, limits=(2.0, 8, 8)),
            "a conditional total as a float": replace(d, conditionals=(replace(first, total_worlds=1.0), second)),
            "a conditional total as a boolean": replace(d, conditionals=(replace(first, total_worlds=True),
                                                                         second)),
            "a conditional count as a float": replace(d, conditionals=(
                replace(first, mine_worlds=((p, 0.0), (r, 0))), second)),
            "a conditional count as a boolean": replace(d, conditionals=(
                replace(first, mine_worlds=((p, False), (r, 0))), second)),
            "a conditional cell as floats": replace(d, conditionals=(
                replace(first, mine_worlds=(((1.0, 0), 0), (r, 0))), second)),
            "a joint count as a float": self.changed(d, 2, joint_mine_worlds=0.0),
            "a joint count as a boolean": self.changed(d, 2, joint_mine_worlds=False),
            "a P2 row as floats": self.changed(d, 0, p2_rows=((r, 0.0, 1.0),)),
            "a P2 row as booleans": self.changed(d, 0, p2_rows=((r, False, True),)),
            "the isolated mark as an integer": self.changed(d, 2, isolated=1),
            "a pair cell as floats": self.changed(d, 0, a=(1.0, 0)),
            "the anchor of a pair as floats": self.changed(d, 0, anchor=(0.0, 1)),
            "the anchors as floats": replace(d, anchors=((0.0, 1), p)),
            "the actual target as floats": replace(d, actual_target=(0.0, 1)),
            "the original target as booleans": replace(d, original_target=(True, False)),
            "a cell count as a float": cell(mine_worlds=1.0),
            "a cell count as a boolean": cell(mine_worlds=True),
            "a pair number of a cell as a float": cell(pairs_in_range=2.0),
            "the floating mark as an integer": cell(floating=0),
            "a pair count as a float": replace(d, counts=replace(d.counts, in_range=3.0)),
        }
        self.assertEqual(len(cases), 25)
        for name, bad in cases.items():
            with self.subTest(case=name):
                self.assertEqual(bad, d)  # equal in Python: only an exact type differs
                self.assertIn(self.code(pseudo.validate_pseudo_diagnosis, bad, selection),
                              ("PSEUDO_RECORD", "PSEUDO_WORLD_COUNT"))
        self.assertTrue(q == d.actual_target and (True, False) == p)

    def test_m21_validation_makes_no_probability_call(self):
        made = [self.diag(premises) for premises in (PC01, PC04, PC05, PC10B, PC13, RK02_DECLARED)]
        with patch.object(pseudo, "_kernel", side_effect=AssertionError("conditional call")), \
                patch.object(policy, "_kernel", side_effect=AssertionError("hypothetical call")), \
                patch("simple_probability.calculate_probabilities", side_effect=AssertionError("kernel")):
            for selection, d in made:
                pseudo.validate_pseudo_diagnosis(d, selection)
                pseudo.plan_pseudo(selection.premises, selection.target)
        self.assertEqual(len(made), 6)


class BoundaryTests(DiagnosisCase):
    def test_m18_selection_reason_and_kind_are_copied_and_the_selection_is_untouched(self):
        expected = {"PC02": ("FORCED_5050_FIRST", "FORCED_5050", PROVEN),
                    "PC05": ("TIE_LOOKAHEAD", "TIE_LOOKAHEAD", PROVEN),
                    "PC04": ("TIE_LOOKAHEAD", "TIE_LOOKAHEAD", PROVEN),
                    "PC01": ("K_LC1_GUESS_KEPT", "MIN_RISK", PROVEN),
                    "PC10B": ("K_LC1_GUESS_KEPT", "MIN_RISK", REFUTED),
                    "RK04_DECLARED": ("TIE_LOOKAHEAD", "TIE_LOOKAHEAD", REFUTED)}
        self.assertEqual(len(expected), 6)
        for name, (reason, kind, status) in expected.items():
            with self.subTest(case=name):
                premises = ALL_CASES[name]
                selection = policy.decide(premises, self.table)
                untouched = policy.decide(premises, self.table)
                evidence = selection.evidence
                d = pseudo.diagnose_pseudo(selection)
                self.assertEqual((d.actual_target, d.actual_selection_reason, d.actual_kind, d.original_target,
                                  d.target_status),
                                 (selection.target, reason, kind, selection.original_target, status))
                self.assertEqual((selection, selection.selection_reason, selection.evidence.kind),
                                 (untouched, reason, kind))
                self.assertIs(selection.evidence, evidence)
                self.assertIs(d.premises, selection.premises)
        self.assertEqual(tuple(field.name for field in fields(pseudo.PseudoDiagnosis)), (
            "scope", "premises", "actual_target", "actual_selection_reason", "actual_kind", "original_target",
            "limits", "anchors", "conditionals", "checks", "counts", "cells", "search_status", "planned_calls",
            "actual_calls", "target_status", "target_bound", "forced_pairs"))
        self.assertEqual(record.EVIDENCE_KINDS, ("FORCED_5050", "TIE_LOOKAHEAD", "MIN_RISK"))

    def test_m23_the_hypothetical_grid_is_detached_and_changes_nothing(self):
        before = declared(("H M H M M", "M 5 M H H", "M H 3 M M"), 10,
                          {(0, 0): 1, (2, 0): 1, (3, 1): 2, (4, 1): 1, (1, 2): 1}, 3, (0, 0))
        made = pseudo.mine_hypothesis_observation(PC04.observation, PC04.mines, (2, 0))
        self.assertEqual(PC04, before)
        self.assertIsNot(made, PC04.observation)
        cells = [(x, y) for y in range(3) for x in range(5)]
        self.assertEqual({c for c in cells if made[c[1]][c[0]] == F}, PC04.mines | {(2, 0)})
        self.assertEqual([made[y][x] for x, y in cells if (x, y) not in PC04.mines | {(2, 0)}],
                         [PC04.observation[y][x] for x, y in cells if (x, y) not in PC04.mines | {(2, 0)}])
        self.assertEqual({c for c in cells if 0 <= made[c[1]][c[0]] <= 8},
                         {c for c in cells if 0 <= PC04.observation[c[1]][c[0]] <= 8})  # no number is made
        self.assertTrue(type(made) is tuple and all(type(row) is tuple and all(type(v) is int for v in row)
                                                    for row in made))
        refused = {"a cell of M": (1, 0), "a revealed number": (1, 1), "a cell outside": (5, 0),
                   "a list": [2, 0], "floats": (2.0, 0.0)}
        self.assertEqual(len(refused), 5)
        for name, bad in refused.items():
            with self.subTest(case=name):
                self.assertEqual(self.code(pseudo.mine_hypothesis_observation, PC04.observation, PC04.mines, bad),
                                 "PSEUDO_PREMISES")
        selection = policy.decide(PC04, self.table)
        with pseudo_calls() as calls:
            d = pseudo.diagnose_pseudo(selection)
            seen = list(calls.grids)
        self.assertEqual((PC04, selection.premises, len(seen)), (before, before, 1))
        grid, num_mines = seen[0]
        self.assertEqual((grid, num_mines), (made, PC04.num_mines))
        self.assertNotEqual(grid, PC04.observation)
        self.assertEqual(sum(v == F for row in grid for v in row), len(PC04.mines) + 1)
        self.assertEqual((d.premises.mines, d.premises.observation), (before.mines, before.observation))

    def test_p01_the_module_adds_no_selection_no_record_format_and_no_engine_use(self):
        with open(pseudo.__file__, encoding="utf-8") as stream:
            tree = ast.parse(stream.read())
        imported, from_engine = set(), []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                imported.add(node.module.split(".")[0])
                if node.module == "core_engine":
                    from_engine += [alias.name for alias in node.names]
        self.assertEqual((imported, from_engine),
                         ({"dataclasses", "core_engine", "experiments", "simple_algorithm", "simple_probability"},
                          ["CellState"]))
        own = [name for name, value in vars(pseudo).items()
               if callable(value) and getattr(value, "__module__", None) == pseudo.__name__]
        self.assertFalse([name for name in own if any(word in name.lower() for word in (
            "save", "load", "encode", "decode", "write", "select", "win", "engine", "session"))])
        self.assertEqual((pseudo.DIAGNOSIS_SCOPE, pseudo.PSEUDO_RANGE, pseudo.PSEUDO_ANCHOR_LIMIT,
                          pseudo.PSEUDO_CALL_LIMIT, policy.CELL_LIMIT, policy.CALL_LIMIT),
                         ("PAIR_MIRROR_DIAGNOSIS_V1", 2, 8, 8, 8, 72))
        self.assertNotIn("PSEUDO_5050", record.EVIDENCE_KINDS + (record.UNCLASSIFIED,))
        self.assertFalse({name for name in vars(policy) if "PSEUDO" in name})
        self.assertEqual((record.FORMAT, record.VERSION), ("S3D3_GUESS_OUTCOME_RECORD", 1))


if __name__ == "__main__":
    unittest.main()
