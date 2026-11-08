"""Public-API costs checked by atomic state-space BFS, not the cover formula."""
import unittest
from collections import deque
from contextlib import nullcontext
from dataclasses import replace
from fractions import Fraction

from stage4_public_kernel import KernelRequest, infer_public
from stage4_efficiency_plan import PlanLimits, plan_safe, plan_identity

AUDIT = None


def atomic_bfs(grid, component, safe, mines):
    w = len(grid[0])
    flat = sum(grid, ())
    u = set(component.targets)
    pivots = []
    relevant = set(u)
    for p in component.pivots:
        x, y = p % w, p // w
        closed = {yy*w+xx for yy in range(len(grid)) for xx in range(w)
                  if (xx, yy) != (x, y) and abs(xx-x) <= 1 and abs(yy-y) <= 1 and grid[yy][xx] < 0}
        f, t = closed & mines, closed & safe
        pivots.append((f, t))
        relevant.update(f)
    initial_flags = frozenset(c for c in relevant if flat[c] == -3)
    start = (frozenset(), initial_flags)
    queue, visited = deque([(start, 0)]), {start}
    ceiling = (3 ** len(u)) * (2 ** len(relevant - u))
    lease = AUDIT.reserve("oracle_states", ceiling) if AUDIT else nullcontext()
    expanded = 0
    with lease as reservation:
        while queue:
            (opened, flags), cost = queue.popleft()
            if AUDIT:
                reservation.spend()
            expanded += 1
            if opened == u:
                if AUDIT:
                    AUDIT.emit("oracle_states", {"grid": grid, "component": component,
                        "minimal_atomic_cost": cost, "expanded": expanded, "ceiling": ceiling})
                return cost
            next_states = []
            for c in relevant - opened:
                next_states.append((opened, flags ^ {c}))
            for c in u - opened - flags:
                next_states.append((opened | {c}, flags))
            for f, t in pivots:
                remaining = t - opened
                if f <= flags and not remaining & flags and remaining:
                    next_states.append((opened | remaining, flags))
            for state in next_states:
                state = tuple(map(frozenset, state))
                if state not in visited:
                    visited.add(state)
                    queue.append((state, cost+1))
    raise AssertionError("No finite safe cover")


class EfficiencyPlanTests(unittest.TestCase):
    def test_atomic_bfs_shared_flags_overlap_and_safe_flag_release(self):
        for mine_bits in (1, 2, 5, 10):
            for flag_bits in (0, 5, 15):
                top = tuple(sum(bool(mine_bits & (1 << xx)) for xx in range(4) if abs(xx-x) <= 1)
                            for x in range(4))
                grid = (top, tuple(-3 if flag_bits & (1 << x) else -2 for x in range(4)))
                req = KernelRequest(grid, mine_bits.bit_count())
                facts = infer_public(req)
                self.assertEqual(facts.status, "COMPLETE")
                plan = plan_safe(req, facts)
                self.assertEqual(plan.status, "READY")
                for component in plan.components:
                    self.assertEqual(component.status, "EXACT")
                    best = atomic_bfs(grid, component, set(facts.proven_safe), set(facts.proven_mines))
                    self.assertEqual(component.optimal_cost, best)
                    self.assertEqual(sum(len(g.sequence) for g in component.audit_groups), best)
                    self.assertGreaterEqual(component.greedy_cost, best)
                self.assertEqual(plan.plan_id, plan_identity(plan.request_id, plan.proof_id, plan.limits,
                    plan.status, plan.reason, plan.provenance, plan.group, plan.candidates, plan.components))

    def test_all_safe_ratio_zero_and_wrong_flag(self):
        req = KernelRequest(((-3, -2, -2),), 0)
        facts = infer_public(req)
        plan = plan_safe(req, facts)
        self.assertEqual(plan.status, "READY")
        self.assertEqual((plan.group.kind, plan.group.pivot), ("OPEN", 1))
        self.assertTrue(plan.candidates[0].contains_proven_zero)
        self.assertEqual(plan.candidates[0].target_per_input, Fraction(1))
        flagged = next(c for c in plan.candidates if c.group.pivot == 0)
        self.assertEqual(tuple(m.action for m in flagged.group.sequence), ("FLAG", "OPEN"))

    def test_no_safe_progress(self):
        req = KernelRequest(((-2, -3),), 1)
        self.assertEqual(plan_safe(req, infer_public(req)).status, "NO_SAFE_PROGRESS")

    def test_large_components_are_not_split(self):
        req = KernelRequest(((1, 2, 1), (-2, -2, -2)), 2)
        facts = infer_public(req)
        plan = plan_safe(req, facts, limits=PlanLimits(max_pivots=0))
        self.assertEqual(plan.status, "READY")
        self.assertTrue(plan.components)
        for component in plan.components:
            self.assertEqual(component.status, "UNSUPPORTED_SIZE")
            self.assertIsNone(component.optimal_cost)
            self.assertEqual(component.subsets, 0)
        self.assertEqual(plan.provenance, "GLOBAL_RATIO_LARGE_COMPONENT")

    def test_multiple_components_are_included(self):
        # Two distant unknown islands separated by opened public numbers.
        req = KernelRequest(((1, 1, 1, 0, 1, 1, 1), (-2, -2, 1, 0, 1, -2, -2)), 2)
        facts = infer_public(req)
        self.assertEqual(facts.status, "COMPLETE")
        plan = plan_safe(req, facts)
        # If the facts classify the islands, every eligible pivot is represented.
        represented = {p for c in plan.components for p in c.pivots}
        eligible = {c.group.pivot for c in plan.candidates if c.group.kind == "CHORD"}
        self.assertEqual(represented, eligible)
        self.assertGreaterEqual(len(plan.components), 2)

    def test_limits_and_cancel_never_publish_partial_plan(self):
        req = KernelRequest(((1, 1, 1), (-2, -2, -2)), 1)
        facts = infer_public(req)
        for limits, expected in ((PlanLimits(max_subsets=0), "SUBSET_LIMIT"),
                                 (PlanLimits(max_seconds=0), "TIME_LIMIT")):
            r = plan_safe(req, facts, limits=limits)
            self.assertEqual(r.status, expected)
            self.assertIsNone(r.group)
            self.assertEqual(r.components, ())
        self.assertEqual(plan_safe(req, facts, cancelled=lambda: True).status, "CANCELLED")
        self.assertEqual(plan_safe(req, facts, cancelled=lambda: 1).status, "ERROR")
        self.assertEqual(plan_safe(req, replace(facts, proven_safe=(3, 4, 5))).status, "ERROR")
        self.assertEqual(plan_safe(replace(req, counted_inputs=1), facts).status, "ERROR")


if __name__ == "__main__":
    unittest.main()
