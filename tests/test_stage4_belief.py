"""New Unit 4 tests, runnable separately from all earlier Stage 4 suites."""

from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import json
from math import comb
import unittest
from unittest.mock import patch

import stage4_belief as belief
from tests.stage4_belief_oracle import OracleBudget, count_small


H, F = -2, -3
ORACLE_RECORDS = []
ANALYTIC_RECORDS = []
BOUNDARY_RECORDS = []
ORACLE_BUDGET = OracleBudget()


def small_corpus():
    """Fixed public states, with no random layouts or replay-derived examples."""
    return [
        ([[H]], 0), ([[H]], 1), ([[F]], 0), ([[F]], 1), ([[0]], 0), ([[1]], 0),
        ([[H, 1, H]], 1), ([[F, 1, H]], 1), ([[H, 0, F]], 0), ([[H, 2, H]], 2),
        ([[H, 1, H, H, 1, H]], 2), ([[H, 1, H, H, 1, H]], 1),
        ([[H, 1, H, 1, H, H, H]], 2), ([[H, 1, H, 1, H, H, H]], 3),
        ([[H, 0, H, 1, H]], 1), ([[H, 0, H, 2, H]], 2),
        ([[0, H], [H, H]], 0), ([[1, H], [F, H]], 1),
        ([[2, H], [H, H]], 2), ([[3, H], [H, H]], 1),
        ([[F, H, H], [H, 1, H], [H, H, H]], 1),
        ([[H, H, H], [H, 0, H], [H, H, H]], 0),
        ([[H, H, H], [H, 2, H], [H, H, H]], 2),
        ([[H] * 12], 6), ([[H, 1, H], [1, H, 1], [H, 1, H]], 2),
        ([[F, 1, H], [1, F, 1], [H, 1, F]], 2),
        ([[1, H, 1], [H, 2, H], [1, H, 1]], 2), ([[0, 0], [0, 0]], 0),
        ([[H, 1, H, 1, H] * 2], 3), ([[F, 1, H, 1, H] * 2 + [H, H]], 4),
        ([[H] * 4 for _ in range(3)], 0), ([[H] * 4 for _ in range(3)], 12),
    ]


def small_events(grid):
    closed = [(x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v < 0]
    opened = [(x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v >= 0]
    events = [belief.EventQuery()]
    if closed:
        first = closed[0]
        events.extend([belief.EventQuery([first, first]), belief.EventQuery((), [first]),
                       belief.EventQuery([first], [first]), belief.zero_event(grid, first)])
    if len(closed) >= 2:
        first, second = closed[:2]
        events.extend([belief.EventQuery([first, second]), belief.EventQuery((), [first, second]),
                       belief.EventQuery([first], [second]), belief.EventQuery([second], [first]),
                       belief.EventQuery(closed), belief.EventQuery((), closed)])
    if opened:
        events.extend([belief.EventQuery([opened[0]]), belief.EventQuery((), [opened[0]]),
                       belief.zero_event(grid, opened[0])])
    return events


def pair_request(events=(), **limits):
    return belief.BeliefRequest([[H, 1, H]], 1, events, belief.BeliefLimits(**limits))


class SmallOracleTests(unittest.TestCase):
    def test_registered_public_corpus(self):
        for index, (grid, mines) in enumerate(small_corpus()):
            with self.subTest(index=index):
                request = belief.BeliefRequest(grid, mines, small_events(grid))
                primitive_events = [(e.safe_cells, e.mine_cells) for e in request.events]
                expected = count_small(grid, mines, primitive_events, ORACLE_BUDGET)
                result = belief.count_public(request)
                ORACLE_RECORDS.append({"index": index, "request": request.to_payload(),
                                       "expected": {"D": str(expected["D"]),
                                                    "M": [[cell, str(n)] for cell, n in expected["M"].items()],
                                                    "W": [str(n) for n in expected["W"]]},
                                       "examined": expected["examined"], "result": result.to_dict()})
                self.assertEqual(result.base.total_worlds, expected["D"])
                if expected["D"] == 0:
                    self.assertEqual(result.status, "INCONSISTENT_INPUT")
                    self.assertIsNone(result.base.marginals)
                    self.assertTrue(all(e.event_worlds is None for e in result.events))
                    continue
                self.assertEqual(result.status, "COMPLETE")
                self.assertEqual({c.coordinate: c.mine_worlds for c in result.base.marginals}, expected["M"])
                self.assertEqual([e.event_worlds for e in result.events], expected["W"])
                self.assertEqual(sum(c.mine_worlds for c in result.base.marginals), mines * expected["D"])
                for row in result.events:
                    self.assertEqual(row.status, "EXACT")
                    self.assertTrue(0 <= row.event_worlds <= expected["D"])
                    self.assertEqual(row.probability, Fraction(row.event_worlds, expected["D"]))
                event_counts = {row.event: row.event_worlds for row in result.events}
                self.assertEqual(event_counts[belief.EventQuery()], expected["D"])
                closed = list(expected["M"])
                if len(closed) >= 2:
                    a, b = closed[:2]
                    self.assertEqual(event_counts[belief.EventQuery([a, b])] +
                                     event_counts[belief.EventQuery([a], [b])],
                                     event_counts[belief.EventQuery([a])])
        self.assertEqual(ORACLE_BUDGET.states, 32)
        self.assertLessEqual(ORACLE_BUDGET.placements_examined, 200_000)


class BoundaryTests(unittest.TestCase):
    def test_physical_flags_and_joint_correlation(self):
        events = [belief.EventQuery([(0, 0), (2, 0)]), belief.EventQuery([(0, 0)])]
        hidden = belief.count_public(pair_request(events))
        flagged_request = belief.BeliefRequest([[F, 1, H]], 1, events)
        flagged = belief.count_public(flagged_request)
        self.assertEqual(hidden.base, flagged.base)
        self.assertEqual(hidden.events, flagged.events)
        self.assertNotEqual(hidden.request_id, flagged.request_id)
        counts = {row.event: row.probability for row in hidden.events}
        self.assertEqual(counts[belief.EventQuery([(0, 0), (2, 0)])], 0)
        self.assertEqual(counts[belief.EventQuery([(0, 0)])], Fraction(1, 2))

    def test_input_freezing_identity_order_and_no_state_leak(self):
        grid, cells = [[H, 1, H]], [[0, 0], [0, 0]]
        safe = belief.EventQuery(cells)
        mine = belief.EventQuery((), [(2, 0)])
        request = belief.BeliefRequest(grid, 1, [mine, safe, safe])
        same = belief.BeliefRequest([[H, 1, H]], 1, [safe, mine])
        self.assertEqual(request, same)
        self.assertEqual(request.identity, same.identity)
        grid[0][0], cells[0][0] = F, 2
        self.assertEqual(request.observation, ((H, 1, H),))
        self.assertEqual(safe.safe_cells, ((0, 0),))
        with self.assertRaises(FrozenInstanceError):
            request.num_mines = 0
        first = belief.count_public(request)
        belief.count_public(belief.BeliefRequest([[H, 0, H]], 0))
        again = belief.count_public(same)
        self.assertEqual(first.base, again.base)
        self.assertEqual(first.events, again.events)
        self.assertEqual(first.diagnostics.work, again.diagnostics.work)
        payload = json.loads(json.dumps(request.to_payload()))
        self.assertEqual(belief.BeliefRequest.from_payload(payload), request)
        self.assertNotEqual(replace(request, limits=belief.BeliefLimits(max_work=100)).identity, request.identity)

    def test_malformed_public_values(self):
        for grid in ([], [[]], [[H], [H, H]], [[True]], [[1.0]], [[-3.0]], [[-4]], [[9]], "bad"):
            with self.subTest(grid=grid), self.assertRaises((TypeError, ValueError)):
                belief.BeliefRequest(grid, 0)
        for value in (True, 0.0, -1, 2):
            with self.subTest(mines=value), self.assertRaises((TypeError, ValueError)):
                belief.BeliefRequest([[H]], value)
        for cells in ([(True, 0)], [(0.0, 0)], [(0,)], "bad"):
            with self.subTest(cells=cells), self.assertRaises((TypeError, ValueError)):
                belief.EventQuery(cells)
        for cell in ((-1, 0), (1, 0), (0, 1)):
            with self.assertRaises(ValueError):
                belief.BeliefRequest([[H]], 0, [belief.EventQuery([cell])])
        BOUNDARY_RECORDS.append({"case": "malformed_public_values", "status": "EXPECTED_REJECTION"})

    def test_private_and_unknown_fields_rejected(self):
        payload = {"observation": [[H]], "num_mines": 0}
        for field in ("engine", "mine_positions", "seed", "bbbv", "active", "wasted", "future_events",
                      "elapsed_time", "evaluator_id", "observation_id"):
            with self.subTest(field=field), self.assertRaises((TypeError, ValueError)):
                belief.BeliefRequest.from_payload({**payload, field: None})
        for nested in ({"events": [{"safe_cells": [], "label": "private"}]},
                       {"limits": {"unlimited": True}}, {"events": [1]}, {"limits": None}):
            with self.assertRaises((TypeError, ValueError)):
                belief.BeliefRequest.from_payload({**payload, **nested})
        with self.assertRaises(TypeError):
            belief.count_public(payload)
        with self.assertRaises(TypeError):
            belief.count_public(pair_request(), cancelled=True)
        BOUNDARY_RECORDS.append({"case": "unknown_fields", "fields": list(payload), "status": "EXPECTED_REJECTION"})

    def test_limits_only_lower_and_unsupported(self):
        for field, value in (("max_cells", 481), ("max_events", 17), ("max_work", 200001),
                             ("max_seconds", 2.01), ("max_seconds", float("nan")),
                             ("max_seconds", True), ("max_work", -1), ("max_work", 1.0)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                belief.BeliefLimits(**{field: value})
        requests = [belief.BeliefRequest([[H] * 481], 1), pair_request(max_cells=2),
                    belief.BeliefRequest([[H] * 17], 1, [belief.EventQuery([(x, 0)]) for x in range(17)]),
                    replace(pair_request(), prior_id="other"), pair_request([belief.EventQuery()], max_events=0)]
        for request in requests:
            result = belief.count_public(request)
            self.assertEqual(result.status, "UNSUPPORTED")
            self.assertIsNone(result.base.total_worlds)
            self.assertTrue(all(row.event_worlds is None for row in result.events))

    def test_event_helpers_and_opened_cells(self):
        grid = [[F, H, H], [H, 1, H], [H, H, H]]
        chord = belief.existing_chord_event(grid, (1, 1))
        self.assertEqual(len(chord.safe_cells), 7)
        self.assertNotIn((0, 0), chord.safe_cells)
        self.assertIsNone(belief.existing_chord_event([[H, 1, H]], (1, 0)))
        self.assertIsNone(belief.existing_chord_event([[0]], (0, 0)))
        self.assertIsNone(belief.existing_chord_event([[F, 1]], (1, 0)))
        events = [belief.zero_event(grid, (0, 0)), belief.zero_event(grid, (1, 1)),
                  belief.EventQuery([(1, 1)]), belief.EventQuery((), [(1, 1)])]
        result = belief.count_public(belief.BeliefRequest(grid, 1, events))
        counts = {row.event: row.event_worlds for row in result.events}
        self.assertEqual(counts[events[1]], 0)
        self.assertEqual(counts[events[2]], 8)
        self.assertEqual(counts[events[3]], 0)

    def test_base_work_cutoff_is_unknown(self):
        result = belief.count_public(pair_request([belief.EventQuery()], max_work=3))
        self.assertEqual((result.status, result.reason), ("INSUFFICIENT", "WORK_LIMIT"))
        self.assertEqual(result.diagnostics.work, 3)
        self.assertIsNone(result.base.total_worlds)
        self.assertIsNone(result.base.marginals)
        self.assertIsNone(result.events[0].event_worlds)
        self.assertEqual(result.diagnostics.last_checkpoint, "base.component.0")

    def test_base_time_and_cancel_inside_enumeration(self):
        for mode in ("time", "cancel"):
            calls = 0

            def trigger():
                nonlocal calls
                calls += 1
                return calls >= 10

            if mode == "time":
                with patch.object(belief, "monotonic", side_effect=lambda: 3.0 if trigger() else 0.0):
                    result = belief.count_public(pair_request())
            else:
                result = belief.count_public(pair_request(), cancelled=trigger)
            self.assertEqual(result.status, "INSUFFICIENT" if mode == "time" else "CANCELLED")
            self.assertIsNone(result.base.total_worlds)
            self.assertEqual(result.diagnostics.last_checkpoint, "base.component.0")
            BOUNDARY_RECORDS.append({"case": "base_enumeration_" + mode, "trigger_calls": calls})

    def test_base_cancel_inside_dp(self):
        request = pair_request()
        reference = belief.count_public(request)
        start = next(row.checkpoints_start for row in reference.diagnostics.stages if row.stage == "base.combine")
        calls = 0

        def cancelled():
            nonlocal calls
            calls += 1
            return calls == start + 3

        result = belief.count_public(request, cancelled=cancelled)
        self.assertEqual(result.status, "CANCELLED")
        self.assertEqual(result.diagnostics.last_checkpoint, "base.combine")
        self.assertIsNone(result.base.total_worlds)

    def test_shared_work_budget_preserves_only_completed_rows(self):
        base = belief.count_public(pair_request())
        events = [belief.EventQuery(), belief.EventQuery([(0, 0)]), belief.EventQuery([(2, 0)])]
        result = belief.count_public(pair_request(events, max_work=base.diagnostics.work + 1))
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.base, base.base)
        self.assertEqual([row.status for row in result.events], ["EXACT", "INSUFFICIENT", "NOT_EVALUATED"])
        self.assertEqual(result.events[0].event_worlds, base.base.total_worlds)
        self.assertIsNone(result.events[1].probability)
        self.assertIsNone(result.events[2].event_worlds)

    def test_event_time_and_cancel(self):
        base = belief.count_public(pair_request())
        events = [belief.EventQuery(), belief.EventQuery([(0, 0)]), belief.EventQuery([(2, 0)])]
        for mode in ("time", "cancel"):
            calls = 0

            def trigger():
                nonlocal calls
                calls += 1
                return calls >= base.diagnostics.checkpoints + 8

            if mode == "time":
                with patch.object(belief, "monotonic", side_effect=lambda: 3.0 if trigger() else 0.0):
                    result = belief.count_public(pair_request(events))
            else:
                result = belief.count_public(pair_request(events), cancelled=trigger)
            self.assertEqual(result.status, "PARTIAL")
            self.assertEqual(result.base, base.base)
            self.assertEqual(result.events[0].status, "EXACT")
            self.assertEqual(result.events[1].status, "INSUFFICIENT" if mode == "time" else "CANCELLED")
            self.assertIsNone(result.events[1].probability)
            self.assertEqual(result.events[2].status, "NOT_EVALUATED")
            BOUNDARY_RECORDS.append({"case": "event_" + mode, "trigger_calls": calls})

    def test_callback_error_and_nonbool(self):
        def failure():
            raise RuntimeError("injected callback failure")

        for callback in (failure, lambda: 1):
            result = belief.count_public(pair_request(), cancelled=callback)
            self.assertEqual((result.status, result.reason), ("ERROR", "CANCEL_CALLBACK_ERROR"))
            self.assertIsNone(result.base.total_worlds)
            self.assertTrue(result.diagnostics.error)

    def test_event_callback_failure(self):
        base = belief.count_public(pair_request())
        calls = 0

        def failure():
            nonlocal calls
            calls += 1
            if calls > base.diagnostics.checkpoints:
                raise RuntimeError("injected event callback failure")
            return False

        result = belief.count_public(pair_request([belief.EventQuery()]), cancelled=failure)
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.base, base.base)
        self.assertEqual(result.events[0].status, "ERROR")
        self.assertIsNone(result.events[0].probability)

    def test_unexpected_internal_error_is_explicit(self):
        with patch.object(belief, "_convolve", side_effect=RuntimeError("injected DP error")):
            result = belief.count_public(pair_request())
        self.assertEqual((result.status, result.reason), ("ERROR", "INTERNAL_ERROR"))
        self.assertIsNone(result.base.total_worlds)
        self.assertIn("injected DP error", result.diagnostics.error)

    def test_zero_limits_and_final_publication_checkpoint(self):
        for request in (pair_request(max_seconds=0), pair_request(max_work=0)):
            result = belief.count_public(request)
            self.assertEqual(result.status, "INSUFFICIENT")
            self.assertIsNone(result.base.total_worlds)
        reference = belief.count_public(pair_request())
        calls = 0

        def cancelled():
            nonlocal calls
            calls += 1
            return calls == reference.diagnostics.checkpoints

        result = belief.count_public(pair_request(), cancelled=cancelled)
        self.assertEqual(result.status, "CANCELLED")
        self.assertEqual(result.diagnostics.last_checkpoint, "base.publish")
        self.assertIsNone(result.base.total_worlds)

    def test_raw_probabilities_and_counts_are_lossless(self):
        value = belief.exact_json({"n": 2**100, "p": Fraction(2**80 + 1, 2**100 + 3), "unknown": None})
        restored = json.loads(json.dumps(value))
        self.assertEqual(int(restored["n"]), 2**100)
        self.assertEqual(Fraction(int(restored["p"]["numerator"]), int(restored["p"]["denominator"])),
                         Fraction(2**80 + 1, 2**100 + 3))
        self.assertIsNone(restored["unknown"])


class AnalyticTests(unittest.TestCase):
    def check_counts(self, request, denominator, marginals, events, formula):
        result = belief.count_public(request)
        ANALYTIC_RECORDS.append({"formula": formula, "request": request.to_payload(),
                                 "expected_D": str(denominator),
                                 "expected_M": [[cell, str(count)] for cell, count in marginals.items()],
                                 "expected_W": [{"event": belief.exact_json(event), "W": str(count)}
                                                for event, count in events.items()], "result": result.to_dict()})
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.base.total_worlds, denominator)
        self.assertEqual({row.coordinate: row.mine_worlds for row in result.base.marginals}, marginals)
        self.assertEqual({row.event: row.event_worlds for row in result.events}, events)
        self.assertEqual(sum(marginals.values()), request.num_mines * denominator)
        return result

    def test_all_hidden_presets(self):
        for width, height, mines in ((9, 9, 10), (16, 16, 40), (30, 16, 99)):
            grid = [[H] * width for _ in range(height)]
            count = width * height
            zero_events = [belief.zero_event(grid, cell) for cell in ((0, 0), (1, 0), (1, 1))]
            mixed = belief.EventQuery([(0, 0), (1, 0), (2, 0)], [(3, 0), (4, 0)])
            overlap = belief.EventQuery([(0, 0)], [(0, 0)])
            events = {event: comb(count - safe, mines) for event, safe in zip(zero_events, (4, 6, 9))}
            events[mixed], events[overlap] = comb(count - 5, mines - 2), 0
            request = belief.BeliefRequest(grid, mines, list(events))
            marginals = {(x, y): comb(count - 1, mines - 1) for y in range(height) for x in range(width)}
            self.check_counts(request, comb(count, mines), marginals, events,
                              "Choose remaining mines after fixing distinct safe/mine cells; D=C(N,R)")

    def test_seventy_independent_pairs(self):
        grid = [[H, 1, H] * 70]
        events = {belief.EventQuery([(0, 0), (2, 0)]): 0,
                  belief.EventQuery([(0, 0), (3, 0), (6, 0)]): 2**67}
        request = belief.BeliefRequest(grid, 70, list(events))
        marginals = {(x, 0): 2**69 for x, value in enumerate(grid[0]) if value == H}
        result = self.check_counts(request, 2**70, marginals, events,
                                   "Each separated clue has two assignments with one mine; product (2z)^70")
        self.assertEqual(result.diagnostics.component_sizes, (2,) * 70)

    def test_variable_components_and_floating(self):
        grid = [[H, 1, H, 1, H] * 40 + [H] * 40]
        events = {belief.EventQuery([(0, 0), (4, 0)]): comb(79, 20),
                  belief.EventQuery((), [(0, 0), (4, 0)]): comb(79, 19)}
        marginals = {(x, 0): comb(79, 20) if x < 200 and x % 5 == 2 else comb(79, 19)
                     for x, value in enumerate(grid[0]) if value == H}
        request = belief.BeliefRequest(grid, 60, list(events))
        result = self.check_counts(request, comb(80, 20), marginals, events,
                                   "a+b=b+c=1 gives z+z^2; [z^60] z^40(1+z)^80=C(80,20)")
        self.assertEqual(result.diagnostics.component_sizes, (3,) * 40)
        self.assertEqual(result.diagnostics.unconstrained_count, 40)
        for x in (0, 2, 10, 202, 239):
            grid[0][x] = F
        flagged = self.check_counts(belief.BeliefRequest(grid, 60, list(events)), comb(80, 20),
                                    marginals, events, "Physical flag normalization of the same generating polynomial")
        self.assertEqual(flagged.base, result.base)

    def test_chord_joint_safety(self):
        grid = [[F, H, H], [H, 1, H], [H, H, H]]
        event = belief.existing_chord_event(grid, (1, 1))
        marginals = {(x, y): 1 for y, row in enumerate(grid) for x, v in enumerate(row) if v < 0}
        result = self.check_counts(belief.BeliefRequest(grid, 1, [event]), 8, marginals, {event: 1},
                                   "Eight equiprobable mine positions; seven safe CHORD targets leave the flagged corner")
        self.assertEqual(result.events[0].probability, Fraction(1, 8))
        self.assertNotEqual(result.events[0].probability, Fraction(7, 8)**7)


if __name__ == "__main__":
    unittest.main()
