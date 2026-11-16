"""Kernel digest memos and the shared neighbour table must equal the unmemoized expressions.

EquivalenceTests hold for any implementation of the three functions (memoized or not).
MemoTests additionally assert that the memo paths are used and stay bounded.
"""
from decimal import Decimal
from fractions import Fraction
import unittest
from unittest.mock import patch

import stage4_posterior as sp
import stage4_public_kernel as pk
from stage4_runtime_kernel import infer_public_indexed

# 4x4, mines (0,0) (1,0) (1,2), first input (3,3): proves cells 5 and 13 safe, 1 and 9 mines.
OBS = ((-2, -2, 1, 0), (-2, -2, 2, 0), (-2, -2, 1, 0), (-2, -2, 1, 0))
MINES, COUNTED = 3, 1


def reference_neighbors(width, height):
    return tuple(
        tuple(ny * width + nx
              for ny in range(max(0, y - 1), min(height, y + 2))
              for nx in range(max(0, x - 1), min(width, x + 2))
              if (nx, ny) != (x, y))
        for y in range(height) for x in range(width)
    )


def tagged(value):
    """Structure with exact types, so 1, True and 1.0 never compare equal."""
    if type(value) is tuple:
        return ("tuple", tuple(tagged(v) for v in value))
    return (type(value).__name__, repr(value))


def outcome(function, *args, **kwargs):
    try:
        return ("value", tagged(function(*args, **kwargs)))
    except Exception as exc:
        return ("error", type(exc).__name__, str(exc).replace("reference_neighbors", "neighbor_indices"))


def fresh_request_id(request):
    return sp.public_digest((pk.PRODUCER, request.to_payload()))


def fresh_proof_id(request, result):
    return sp.public_digest((pk.PRODUCER, pk.VERSION, fresh_request_id(request), result.proven_safe,
                             result.proven_mines, result.constraints))


def verdict(request, result):
    try:
        return "OK" if pk.verify_facts(request, result) is True else "FALSE"
    except ValueError as exc:
        return str(exc)


def solved(counted=COUNTED):
    request = pk.KernelRequest(OBS, MINES, counted, limits=pk.KernelLimits())
    result = infer_public_indexed(request)
    assert result.status == "COMPLETE", result.status
    return request, result


def put(target, name, value):
    object.__setattr__(target, name, value)


class OddInt(int):
    """An int subclass whose multiplication is not integer multiplication."""
    def __mul__(self, other):
        return 1000
    __rmul__ = __mul__


class IndexOnly:
    __hash__ = None

    def __index__(self):
        return 3


class EquivalenceTests(unittest.TestCase):
    def test_neighbor_table_equals_the_unmemoized_body_for_every_argument_form(self):
        n = sp.neighbor_indices
        for shape in ((9, 9), (30, 16), (1, 1), (0, 3), (2, 3)):  # prime exact-int shapes first
            self.assertEqual(outcome(n, *shape), outcome(reference_neighbors, *shape))
        forms = [((9.0, 9), {}), ((9, 9.0), {}), ((True, 1), {}), ((1, True), {}), ((False, 3), {}),
                 ((), dict(width=9, height=9)), ((9,), dict(height=9)), ((), dict(height=9, width=9)),
                 ((), dict(width=9.0, height=9)), (("9", 9), {}), ((None, 9), {}), (([9], 9), {}),
                 ((Fraction(9), 9), {}), ((Decimal(9), 9), {}), ((9 + 0j, 9), {}),
                 ((OddInt(9), 9), {}), ((9, OddInt(9)), {}), ((IndexOnly(), 3), {}),
                 ((9,), {}), ((9, 9, 9), {}), ((9, 9), dict(depth=1)), ((9,), dict(width=9)),
                 ((0, 0), {}), ((-3, 4), {}), ((4, -3), {}), ((40, 30), {}), ((481, 1), {})]
        for args, kwargs in forms:
            with self.subTest(args=args, kwargs=kwargs):
                self.assertEqual(outcome(n, *args, **kwargs), outcome(reference_neighbors, *args, **kwargs))
        # a non-int caller must not leave a table behind for the int callers of the same shape
        for odd, plain in (((OddInt(5), 7), (5, 7)), ((True, 2), (1, 2)), ((OddInt(6), OddInt(4)), (6, 4))):
            with self.subTest(odd_first=odd):
                self.assertEqual(outcome(n, *odd), outcome(reference_neighbors, *odd))
                self.assertEqual(outcome(n, *plain), outcome(reference_neighbors, *plain))
        for shape in ((9, 9), (30, 16), (1, 1), (0, 3), (2, 3)):
            self.assertEqual(outcome(n, *shape), outcome(reference_neighbors, *shape))

    def test_request_identity_follows_every_field_and_limit_change(self):
        flagged = ((-3,) + OBS[0][1:],) + OBS[1:]
        changes = [
            ("counted_inputs", lambda q: put(q, "counted_inputs", COUNTED + 7), "FACT_IDENTITY"),
            ("num_mines", lambda q: put(q, "num_mines", MINES - 1), "FACT_IDENTITY"),
            ("prior_id", lambda q: put(q, "prior_id", "other"), "FACT_IDENTITY"),
            ("version", lambda q: put(q, "version", "other"), "FACT_IDENTITY"),
            ("observation", lambda q: put(q, "observation", flagged), "FACT_IDENTITY"),
            ("limits object", lambda q: put(q, "limits", pk.KernelLimits(max_work=400_000)), "FACT_IDENTITY"),
            ("limits.max_cells", lambda q: put(q.limits, "max_cells", 479), "FACT_IDENTITY"),
            ("limits.max_constraints", lambda q: put(q.limits, "max_constraints", 2047), "FACT_IDENTITY"),
            ("limits.max_derived", lambda q: put(q.limits, "max_derived", 1023), "FACT_IDENTITY"),
            ("limits.max_work", lambda q: put(q.limits, "max_work", 499_999), "FACT_IDENTITY"),
            ("limits.max_seconds", lambda q: put(q.limits, "max_seconds", 1.5), "FACT_IDENTITY"),
            ("counted bool, equal value", lambda q: put(q, "counted_inputs", True), "FACT_IDENTITY"),
            ("num_mines float, equal value", lambda q: put(q, "num_mines", float(MINES)), "FACT_IDENTITY"),
            ("max_work float, equal value", lambda q: put(q.limits, "max_work", 500_000.0), "FACT_IDENTITY"),
            ("max_seconds int, equal value", lambda q: put(q.limits, "max_seconds", 2), "FACT_IDENTITY"),
            ("equal new observation tuples", lambda q: put(q, "observation", tuple(tuple(r) for r in OBS)), "OK"),
            ("equal new limits object", lambda q: put(q, "limits", pk.KernelLimits()), "OK"),
        ]
        for name, change, expected in changes:
            with self.subTest(change=name):
                request, result = solved()
                first = request.identity
                self.assertEqual((first, request.identity, verdict(request, result)),
                                 (fresh_request_id(request), first, "OK"))
                change(request)
                self.assertEqual(request.identity, fresh_request_id(request))
                self.assertEqual(request.identity, fresh_request_id(request))
                self.assertEqual(request.identity == first, expected == "OK")
                self.assertEqual(verdict(request, result), expected)
        # a list-backed observation changed in place after its identity was read
        request, _result = solved()
        rows = [list(r) for r in OBS]
        put(request, "observation", rows)
        before = request.identity
        rows[0][0] = -3
        self.assertNotEqual(request.identity, before)
        self.assertEqual(request.identity, fresh_request_id(request))
        # changed, read, then changed back: the original digest and acceptance return
        request, result = solved()
        first = request.identity
        put(request, "counted_inputs", COUNTED + 1)
        self.assertNotEqual(request.identity, first)
        put(request, "counted_inputs", COUNTED)
        self.assertEqual((request.identity, verdict(request, result)), (first, "OK"))
        # the default limits object is shared by every request built without limits
        a, b = pk.KernelRequest(OBS, MINES, COUNTED), pk.KernelRequest(OBS, MINES, COUNTED + 1)
        self.assertIs(a.limits, b.limits)
        ids = (a.identity, b.identity)
        put(a.limits, "max_work", 123_456)
        try:
            self.assertEqual((a.identity, b.identity), (fresh_request_id(a), fresh_request_id(b)))
            self.assertTrue(a.identity != ids[0] and b.identity != ids[1])
        finally:
            put(a.limits, "max_work", 500_000)
        self.assertEqual((a.identity, b.identity), ids)
        # a deleted field raises the same error as the unmemoized expression
        request, _result = solved()
        _ = request.identity
        object.__delattr__(request, "counted_inputs")
        with self.assertRaisesRegex(AttributeError, "counted_inputs"):
            request.identity

    def test_request_identity_of_many_live_requests(self):
        requests = [pk.KernelRequest(OBS, MINES, COUNTED + i, limits=pk.KernelLimits()) for i in range(40)]
        for order in (requests, requests[::-1], requests):
            for request in order:
                self.assertEqual(request.identity, fresh_request_id(request))
        put(requests[5], "counted_inputs", COUNTED + 500)
        self.assertEqual([r.identity for r in requests], [fresh_request_id(r) for r in requests])
        self.assertEqual(len({r.identity for r in requests}), 40)

    def test_proof_digest_follows_changes_inside_the_proof_nodes(self):
        def node(result, wanted):
            found = [p for p in result.constraints if wanted(p)]
            self.assertTrue(found)
            return found[0]
        swap = lambda p: p.rule == "NORMALIZE" and len(p.parents) >= 3 and p.parents[-1] != p.parents[-2]
        changes = [
            ("duplicate NORMALIZE parent", lambda p: p.rule == "NORMALIZE" and len(p.parents) >= 2,
             lambda p: put(p, "parents", p.parents + (p.parents[-1],)), "PROOF_HASH"),
            ("swap NORMALIZE fact parents", swap,
             lambda p: put(p, "parents", p.parents[:-2] + (p.parents[-1], p.parents[-2])), "PROOF_HASH"),
            ("bool cell, equal value", lambda p: p.cells and p.cells[0] in (0, 1),
             lambda p: put(p, "cells", (bool(p.cells[0]),) + p.cells[1:]), "PROOF_HASH"),
            ("clue mines", lambda p: p.rule == "CLUE" and p.cells,
             lambda p: put(p, "mines", p.mines + 1), "CLUE_PROOF"),
            ("equal new cells tuple", lambda p: p.rule == "CLUE" and p.cells,
             lambda p: put(p, "cells", tuple(int(str(c)) for c in p.cells)), "OK"),
            ("equal new parents tuple", lambda p: p.rule == "SUBSET",
             lambda p: put(p, "parents", tuple(int(str(j)) for j in p.parents)), "OK"),
        ]
        for name, wanted, change, expected in changes:
            with self.subTest(change=name):
                request, result = solved()
                self.assertEqual((verdict(request, result), verdict(request, result)), ("OK", "OK"))
                target = node(result, wanted)
                original = {f: getattr(target, f) for f in ("cells", "mines", "rule", "parents", "source")}
                change(target)
                self.assertEqual((verdict(request, result), verdict(request, result)), (expected, expected))
                digest = pk._proof_identity(request, result.proven_safe, result.proven_mines, result.constraints)
                self.assertEqual(digest, fresh_proof_id(request, result))
                self.assertEqual(digest == result.proof_id, expected == "OK")
                for field, value in original.items():
                    put(target, field, value)
                self.assertEqual(verdict(request, result), "OK")
        # the request changes while the proof objects stay the same
        request, result = solved()
        self.assertEqual(verdict(request, result), "OK")
        put(request, "counted_inputs", COUNTED + 7)
        self.assertEqual(verdict(request, result), "FACT_IDENTITY")
        rebound = pk.KernelResult(**{f: (fresh_request_id(request) if f == "request_id" else getattr(result, f))
                                     for f in result.__dataclass_fields__})
        self.assertEqual(verdict(request, rebound), "PROOF_HASH")
        # two proofs alternate; a twin request with equal content accepts the same proof
        (qa, ra), (qb, rb) = solved(COUNTED), solved(COUNTED + 1)
        for _ in range(3):
            self.assertEqual((verdict(qa, ra), verdict(qb, rb)), ("OK", "OK"))
        self.assertEqual((verdict(qa, rb), verdict(qb, ra)), ("FACT_IDENTITY", "FACT_IDENTITY"))
        twin = pk.KernelRequest(OBS, MINES, COUNTED, limits=pk.KernelLimits())
        self.assertEqual(verdict(twin, ra), "OK")

    def test_kernel_result_and_work_do_not_depend_on_repeated_calls(self):
        request, first = solved()
        second = infer_public_indexed(request)
        twin = infer_public_indexed(pk.KernelRequest(OBS, MINES, COUNTED, limits=pk.KernelLimits()))
        key = lambda r: (r.status, r.reason, r.request_id, r.proof_id, r.work, r.work_by_family,
                         r.proven_safe, r.proven_mines, r.constraints, r.constraint_count, r.derived_count)
        self.assertEqual(key(first), key(second))
        self.assertEqual(key(first), key(twin))
        self.assertEqual((first.proven_safe, first.proven_mines), ((5, 13), (1, 9)))
        ticks = []
        pk.verify_facts(request, first, checkpoint=ticks.append)
        again = []
        pk.verify_facts(request, first, checkpoint=again.append)
        self.assertEqual(ticks, again)


class MemoTests(unittest.TestCase):
    def digests(self):
        calls = []
        real = pk.public_digest

        def counting(value):
            calls.append(1)
            return real(value)
        patcher = patch.object(pk, "public_digest", counting)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def test_unchanged_request_and_proof_are_hashed_once(self):
        calls = self.digests()
        request, result = solved()
        self.assertEqual(len(calls), 2)  # one request digest, one proof digest for kernel + self-verification
        self.assertEqual(verdict(request, result), "OK")
        _ = request.identity
        self.assertEqual(len(calls), 2)
        put(request.limits, "max_work", 499_999)
        self.assertEqual(verdict(request, result), "FACT_IDENTITY")
        self.assertEqual(len(calls), 3)
        put(request.limits, "max_work", 500_000)
        self.assertEqual(verdict(request, result), "OK")
        self.assertEqual(len(calls), 4)  # request digest again; the proof digest is keyed by its value
        target = next(p for p in result.constraints if p.rule == "NORMALIZE" and len(p.parents) >= 2)
        put(target, "parents", target.parents + (target.parents[-1],))
        self.assertEqual((verdict(request, result), verdict(request, result)), ("PROOF_HASH", "PROOF_HASH"))
        self.assertEqual(len(calls), 5)

    def test_values_that_can_change_in_place_are_never_memoized(self):
        calls = self.digests()
        request = pk.KernelRequest(OBS, MINES, COUNTED, limits=pk.KernelLimits())
        put(request, "observation", [list(r) for r in OBS])
        _ = request.identity, request.identity
        self.assertEqual(len(calls), 2)
        request = pk.KernelRequest(OBS, MINES, COUNTED, limits=pk.KernelLimits())
        put(request.limits, "max_work", 500_000.0)
        _ = request.identity, request.identity
        self.assertEqual(len(calls), 4)

    def test_memos_are_bounded(self):
        requests = [pk.KernelRequest(OBS, MINES, COUNTED + i, limits=pk.KernelLimits()) for i in range(40)]
        for request in requests:
            _ = request.identity
            self.assertLessEqual(len(pk._IDENTITY_MEMO), pk._IDENTITY_MEMO_MAX)
        self.assertEqual(len(pk._PROOF_MEMO), 1)
        for width in range(1, 60):
            sp.neighbor_indices(width, 3)
        info = sp._neighbor_table_cached.cache_info()
        self.assertEqual(info.maxsize, 32)
        self.assertLessEqual(info.currsize, 32)

    def test_neighbor_table_is_shared_only_for_exact_int_registered_shapes(self):
        n = sp.neighbor_indices
        self.assertIs(n(9, 9), n(9, 9))
        self.assertIs(n(30, 16), n(width=30, height=16))
        self.assertIs(n(24, 20), n(24, 20))
        self.assertIsNot(n(True, 2), n(1, 2))
        self.assertIsNot(n(40, 30), n(40, 30))
        self.assertIsNot(n(481, 1), n(481, 1))


if __name__ == "__main__":
    unittest.main()
