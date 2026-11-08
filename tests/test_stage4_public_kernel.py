"""Public-API tests; independent complete-layout bitmask soundness oracle."""
import unittest
from dataclasses import replace
from contextlib import nullcontext

from stage4_public_kernel import KernelRequest, KernelLimits, infer_public, verify_facts

AUDIT = None


def oracle(test, grid, total, result):
    h, w = len(grid), len(grid[0])
    n = h * w
    lease = AUDIT.reserve("oracle_masks", 1 << n) if AUDIT else nullcontext()
    worlds = []
    with lease as reservation:
        for mask in range(1 << n):
            if AUDIT:
                reservation.spend()
            if mask.bit_count() != total:
                continue
            valid = True
            for y, row in enumerate(grid):
                for x, clue in enumerate(row):
                    if clue < 0:
                        continue
                    if mask & (1 << (y * w + x)):
                        valid = False
                        break
                    count = 0
                    for yy in range(h):
                        for xx in range(w):
                            if (xx, yy) != (x, y) and abs(xx-x) <= 1 and abs(yy-y) <= 1:
                                count += bool(mask & (1 << (yy*w+xx)))
                    if count != clue:
                        valid = False
                        break
                if not valid:
                    break
            if valid:
                worlds.append(mask)
    if result.status == "COMPLETE":
        test.assertTrue(worlds)
        for mask in worlds:
            test.assertTrue(all(not mask & (1 << c) for c in result.proven_safe))
            test.assertTrue(all(mask & (1 << c) for c in result.proven_mines))
        test.assertTrue(verify_facts(KernelRequest(grid, total), result))
    if AUDIT:
        AUDIT.emit("oracle_masks", {"grid": grid, "total": total, "consistent_masks": worlds,
                                    "result": result, "all_masks": 1 << n})
    return worlds


class PublicKernelTests(unittest.TestCase):
    def test_zero_and_all_mines(self):
        for total, safe, mines in ((0, (0, 1, 2), ()), (3, (), (0, 1, 2))):
            grid = ((-2, -3, -2),)
            result = infer_public(KernelRequest(grid, total))
            self.assertEqual((result.proven_safe, result.proven_mines), (safe, mines))
            oracle(self, grid, total, result)

    def test_chained_strict_subset_safe_and_mines(self):
        for top, total, safe, mines in (((1, 1, 1), 1, (3, 5), (4,)),
                                      ((1, 2, 1), 2, (4,), (3, 5))):
            grid = (top, (-2, -3, -2))
            result = infer_public(KernelRequest(grid, total))
            self.assertEqual(result.status, "COMPLETE")
            self.assertEqual((result.proven_safe, result.proven_mines), (safe, mines))
            self.assertTrue(any(p.rule == "SUBSET" for p in result.constraints))
            oracle(self, grid, total, result)

    def test_duplicates_empty_and_conflicting_constraints(self):
        result = infer_public(KernelRequest(((1, 1), (-2, -2)), 1))
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(len(result.constraints), 1)
        self.assertTrue(verify_facts(KernelRequest(((1, 1), (-2, -2)), 1), result))
        for grid, total in ((((0,),), 0), (((0, 0),), 0)):
            r = infer_public(KernelRequest(grid, total))
            self.assertEqual(r.status, "COMPLETE")
            oracle(self, grid, total, r)
        for grid, total in ((((0, 1), (-2, -2)), 1), (((1,),), 0), (((0,),), 1)):
            r = infer_public(KernelRequest(grid, total))
            self.assertEqual(r.status, "INCONSISTENT")
            self.assertEqual(r.proven_safe + r.proven_mines + r.constraints, ())

    def test_overlap_is_never_treated_as_subset(self):
        grid = ((1, -2, 1, -2), (-3, -2, -2, -2))
        r = infer_public(KernelRequest(grid, 2))
        oracle(self, grid, 2, r)
        for p in r.constraints:
            if p.rule == "SUBSET":
                a, b = (r.constraints[i] for i in p.parents)
                self.assertLess(set(a.cells), set(b.cells))

    def test_independent_small_public_corpus(self):
        # Fixed enumeration, not screened by the kernel's result or fact count.
        for actual in range(0, 512, 7):
            grid = []
            for y in range(3):
                row = []
                for x in range(3):
                    c = 3*y+x
                    opened = not actual & (1 << c) and (c + actual) % 3 == 0
                    if opened:
                        value = sum(bool(actual & (1 << (3*yy+xx)))
                            for yy in range(3) for xx in range(3)
                            if (xx, yy) != (x, y) and abs(xx-x) <= 1 and abs(yy-y) <= 1)
                    else:
                        value = -3 if (c + actual) % 4 == 0 else -2
                    row.append(value)
                grid.append(tuple(row))
            grid = tuple(grid)
            r = infer_public(KernelRequest(grid, actual.bit_count()))
            self.assertEqual(r.status, "COMPLETE")
            oracle(self, grid, actual.bit_count(), r)

    def test_limits_cancellation_and_atomic_publication(self):
        g = ((1, 1, 1), (-2, -2, -2))
        for changes, expected in (({"max_work": 0}, "WORK_LIMIT"),
                ({"max_cells": 0}, "CELL_LIMIT"), ({"max_constraints": 0}, "CONSTRAINT_LIMIT"),
                ({"max_derived": 0}, "DERIVED_LIMIT"), ({"max_seconds": 0}, "TIME_LIMIT"),
                ({"max_work": 70}, "WORK_LIMIT")):
            r = infer_public(KernelRequest(g, 1, limits=KernelLimits(**changes)))
            self.assertEqual(r.status, expected)
            self.assertEqual(r.proven_safe + r.proven_mines + r.constraints, ())
            self.assertIsNone(r.proof_id)
        r = infer_public(KernelRequest(g, 1), cancelled=lambda: True)
        self.assertEqual(r.status, "CANCELLED")
        self.assertEqual(r.work, 0)
        r = infer_public(KernelRequest(g, 1), cancelled=lambda: "yes")
        self.assertEqual(r.status, "ERROR")
        self.assertEqual(r.proven_safe, ())
        calls = [0]
        def cancel_later():
            calls[0] += 1
            return calls[0] > 20
        self.assertEqual(infer_public(KernelRequest(g, 1), cancelled=cancel_later).status, "CANCELLED")

    def test_identity_immutability_and_payload(self):
        g = [[1, 1], [-3, -2]]
        r = KernelRequest(g, 1, 2**63+7)
        before = r.identity
        g[1][0] = -2
        self.assertEqual(r.identity, before)
        self.assertEqual(KernelRequest.from_payload(r.to_payload()), r)
        self.assertNotEqual(replace(r, counted_inputs=r.counted_inputs+1).identity, before)
        self.assertNotEqual(replace(r, observation=((1, 1), (-2, -2))).identity, before)
        self.assertNotEqual(replace(r, limits=KernelLimits(max_work=100)).identity, before)
        with self.assertRaises(ValueError):
            KernelRequest(((True,),), 0)
        with self.assertRaises(ValueError):
            KernelRequest.from_payload({**r.to_payload(), "engine": {}})
        self.assertEqual(infer_public(replace(r, version="other")).status, "UNSUPPORTED")

    def test_forged_facts_and_proof_binding_are_rejected(self):
        req = KernelRequest(((1, 1), (-2, -2)), 1)
        r = infer_public(req)
        for fake in (replace(r, proven_safe=(2,)), replace(r, producer="Q"),
                     replace(r, request_id="0"*64), replace(r, proof_id="0"*64)):
            with self.assertRaises(ValueError):
                verify_facts(req, fake)


if __name__ == "__main__":
    unittest.main()
