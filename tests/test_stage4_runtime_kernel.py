"""Independent tiny closure/oracle checks; never invokes the game engine."""
import itertools
import unittest
from dataclasses import replace
from unittest.mock import patch

from stage4_belief import HIDDEN, FLAGGED
from stage4_public_kernel import KernelLimits, KernelRequest, infer_public, verify_facts
from stage4_runtime_kernel import WORK_VERSION, infer_public_indexed


def adjacent(c, width, height):
    x, y = c % width, c // width
    return {ny * width + nx for ny in range(height) for nx in range(width)
            if max(abs(nx - x), abs(ny - y)) == 1}


def oracle(grid, total):
    width, height = len(grid[0]), len(grid)
    flat = sum(grid, ())
    unknown = {i for i, v in enumerate(flat) if v < 0}
    equations = {frozenset(unknown): total}
    for c, clue in enumerate(flat):
        if clue >= 0:
            key = frozenset(adjacent(c, width, height) & unknown)
            if key in equations and equations[key] != clue:
                raise ValueError("contradiction")
            equations[key] = clue
    safe, mines = set(), set()
    while True:
        before = (dict(equations), set(safe), set(mines))
        for cells, k in list(equations.items()):
            if k == 0:
                safe.update(cells)
            if k == len(cells):
                mines.update(cells)
        for cells, k in list(equations.items()):
            equations[frozenset(cells - safe - mines)] = k - len(cells & mines)
        current = [(cells - safe - mines, k - len(cells & mines)) for cells, k in equations.items()]
        for a, ka in current:
            for b, kb in current:
                if a and a < b:
                    equations[frozenset(b - a)] = kb - ka
        if before == (equations, safe, mines):
            return tuple(sorted(safe)), tuple(sorted(mines))


class IndexedKernelTests(unittest.TestCase):
    def test_independent_closure_and_layout_oracle(self):
        cases = masks = 0
        width, height = 3, 2
        for total in (1, 2):
            layouts = list(itertools.combinations(range(6), total))
            for layout in layouts:
                for reveal_count in (1, 2, 3):
                    opened = [c for c in range(6) if c not in layout][:reveal_count]
                    flat = [len(adjacent(c, width, height) & set(layout)) if c in opened
                            else (FLAGGED if c % 2 == 0 else HIDDEN) for c in range(6)]
                    grid = (tuple(flat[:3]), tuple(flat[3:]))
                    query = KernelRequest(grid, total, 1)
                    indexed, old = infer_public_indexed(query), infer_public(query)
                    self.assertEqual(indexed.status, "COMPLETE", indexed.error)
                    self.assertEqual(old.status, "COMPLETE")
                    expected = oracle(grid, total)
                    self.assertEqual((indexed.proven_safe, indexed.proven_mines), expected)
                    self.assertEqual((old.proven_safe, old.proven_mines), expected)
                    for candidate in layouts:
                        masks += 1
                        if set(candidate) & set(opened):
                            continue
                        if any(len(adjacent(c, width, height) & set(candidate)) != flat[c] for c in opened):
                            continue
                        self.assertFalse(set(indexed.proven_safe) & set(candidate))
                        self.assertTrue(set(indexed.proven_mines) <= set(candidate))
                    self.assertTrue(verify_facts(query, indexed))
                    cases += 1
        self.assertEqual(cases, 63)
        self.assertEqual(masks, 783)

    def test_normalization_reindexes_new_relationships(self):
        # Global residuals change repeatedly as local extremes arrive.
        grids = (((0, HIDDEN, HIDDEN, HIDDEN), (1, HIDDEN, 2, HIDDEN), (HIDDEN, HIDDEN, HIDDEN, HIDDEN)),
                 ((0, 1, HIDDEN, HIDDEN), (0, 2, HIDDEN, HIDDEN), (0, 1, HIDDEN, HIDDEN)))
        for grid, total in zip(grids, (3, 2)):
            query = KernelRequest(grid, total)
            result = infer_public_indexed(query)
            reference = infer_public(query)
            self.assertEqual(result.status, reference.status, result.error)
            if result.status == "COMPLETE":
                self.assertTrue(verify_facts(query, result))
                self.assertEqual((result.proven_safe, result.proven_mines), oracle(grid, total))

    def test_physical_wrong_flag_is_unknown(self):
        query = KernelRequest(((0, FLAGGED, HIDDEN),), 0)
        result = infer_public_indexed(query)
        self.assertEqual(result.proven_safe, (1, 2))
        self.assertEqual(result.proven_mines, ())
        self.assertTrue(verify_facts(query, result))

    def test_zero_limits_cancel_and_atomic_publication(self):
        query = KernelRequest(((1, HIDDEN, HIDDEN),), 1)
        for field in ("max_cells", "max_constraints", "max_work", "max_seconds"):
            result = infer_public_indexed(replace(query, limits=replace(KernelLimits(), **{field: 0})))
            self.assertNotEqual(result.status, "COMPLETE")
            self.assertEqual((result.proven_safe, result.proven_mines, result.constraints, result.proof_id),
                             ((), (), (), None))
        self.assertEqual(infer_public_indexed(query, cancelled=lambda: True).status, "CANCELLED")
        self.assertEqual(infer_public_indexed(query, cancelled=lambda: 1).status, "ERROR")
        complete = infer_public_indexed(query)
        result = infer_public_indexed(replace(query, limits=replace(KernelLimits(), max_work=complete.work - 1)))
        self.assertEqual(result.status, "WORK_LIMIT")
        self.assertEqual(result.constraints, ())
        self.assertEqual(result.work, sum(v for _, v in result.work_by_family))

    def test_contradictions_and_unknown_prior(self):
        for grid, total in ((((0, HIDDEN), (1, HIDDEN)), 1), (((0,),), 1)):
            result = infer_public_indexed(KernelRequest(grid, total))
            self.assertEqual(result.status, "INCONSISTENT")
            self.assertEqual(result.proven_safe, ())
        result = infer_public_indexed(KernelRequest(((HIDDEN,),), 0, version="unknown"))
        self.assertEqual(result.status, "UNSUPPORTED")

    def test_work_versions_and_old_caller(self):
        query = KernelRequest(((1, HIDDEN, HIDDEN),), 1)
        new, old = infer_public_indexed(query), infer_public(query)
        self.assertEqual(new.work_version, WORK_VERSION)
        for result in (old, new):
            self.assertTrue(verify_facts(query, result))
            with self.assertRaises(ValueError):
                verify_facts(query, replace(result, work_version="unknown"))
            with self.assertRaises(ValueError):
                verify_facts(replace(query, counted_inputs=1), result)
        from stage4_efficiency_plan import plan_safe
        self.assertEqual(plan_safe(query, new).status, plan_safe(query, old).status)

    def test_certificate_gate_failure_is_atomic(self):
        query = KernelRequest(((0, HIDDEN),), 0)
        with patch("stage4_runtime_kernel.verify_facts", side_effect=ValueError("bad closure")):
            result = infer_public_indexed(query)
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.constraints, ())
        self.assertIsNone(result.proof_id)


if __name__ == "__main__":
    unittest.main()
