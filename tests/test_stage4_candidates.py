"""Unit 5 public-boundary, independent-oracle and fixed-engine checks."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
from fractions import Fraction
import unittest
from unittest.mock import patch

import stage4_candidates as candidates
from stage4_belief import BaseResult, count_public as real_count_public
from tests.stage4_candidates_oracle import FIXTURES, PREFIXES, analyze_grid


CONSUME = lambda name, count: None
EMIT = lambda lane, value: None
ENGINE_INPUTS = None
COORDINATOR_FIXTURES = None
CENTER = FIXTURES[0][1]


def counted_backend(function):
    def run(request, *, cancelled=None):
        CONSUME("count_public_calls", 1)
        result = function(request, cancelled=cancelled)
        EMIT("backend", {"request": request.to_payload(), "result": result})
        return result
    return run


@contextmanager
def backend(function):
    with patch.object(candidates, "count_public", counted_backend(function)):
        yield


def call(request, label="test", **kwargs):
    CONSUME("consumer_calls", 1)
    EMIT("consumer_inputs", {"label": label, "request": request.to_payload()})
    result = candidates.analyze_candidates(request, **kwargs)
    EMIT("consumer_results", {"label": label, "result": result})
    return result


def profile(row):
    return {"kind": row.kind, "pivot": row.pivot, "final_flags": row.final_flags,
            "targets": row.targets, "sequence": tuple(asdict(move) for move in row.sequence),
            "cost": row.immediate_input_cost, "survival_worlds": row.survival.worlds,
            "survival_probability": row.survival_probability,
            "zero_targets": tuple({"cell": zero.cell, "safe_cells": zero.event.safe_cells,
                                    "worlds": zero.event.worlds,
                                    "joint": zero.zero_and_survive_probability,
                                    "conditional": zero.zero_given_survival_probability}
                                   for zero in row.zero_targets),
            "target_count": row.target_count,
            "floor": row.survival_weighted_target_floor_per_input,
            "eligibility": asdict(row.eligibility)}


class CandidateTests(unittest.TestCase):
    def test_oracle_24_public_observations(self):
        self.assertEqual(len(FIXTURES), 24)
        for name, grid, mines in FIXTURES:
            with self.subTest(name=name):
                oracle = analyze_grid(grid, mines, CONSUME)
                result = call(candidates.CandidateRequest(grid, mines), "oracle:" + name)
                EMIT("oracle", {"id": name, "observation": grid, "num_mines": mines, "oracle": oracle})
                self.assertEqual(result.base.total_worlds, oracle["D"])
                if not oracle["D"]:
                    self.assertEqual(result.status, "INCONSISTENT_INPUT")
                    self.assertEqual(result.candidates, ())
                    continue
                self.assertEqual(result.status, "COMPLETE")
                self.assertTrue(result.catalogue_complete and result.evidence_complete)
                self.assertEqual({row.coordinate: row.mine_worlds for row in result.base.marginals}, oracle["M"])
                self.assertEqual(result.has_proven_safe_cell, oracle["has_proven_safe_cell"])
                self.assertEqual(tuple(map(profile, result.candidates)), oracle["candidates"])
                self.assertEqual(result.diagnostics.generated, oracle["generated"])
                self.assertEqual(result.diagnostics.excluded_empty_targets, oracle["empty_excluded"])
                self.assertEqual(result.diagnostics.excluded_edited_single_target, oracle["single_excluded"])
                self.assertEqual(len({r.candidate_id for r in result.candidates}), len(result.candidates))
                for row in result.candidates:
                    self.assertTrue(all(z.event.worlds <= row.survival.worlds for z in row.zero_targets))
                    self.assertEqual(row.survival.safe_cells, row.targets)
                if COORDINATOR_FIXTURES is not None:
                    fixture = next((f for f in COORDINATOR_FIXTURES if f["id"] == name), None)
                    if fixture is not None:
                        self.check_coordinator(result, fixture["expected"])

    def check_coordinator(self, result, expected):
        self.assertEqual(str(result.base.total_worlds), expected["D"])
        self.assertEqual(len(result.candidates), expected["candidate_count"])
        self.assertEqual(result.has_proven_safe_cell, expected["has_proven_safe_cell"])
        for actual, wanted in zip(result.candidates, expected["candidates"]):
            self.assertEqual(actual.kind, wanted["kind"])
            self.assertEqual(list(actual.pivot), wanted["pivot"])
            self.assertEqual([list(c) for c in actual.final_flags], wanted["final_flags"])
            self.assertEqual([list(c) for c in actual.targets], wanted["targets"])
            self.assertEqual([asdict(m) for m in actual.sequence], wanted["sequence"])
            self.assertEqual(actual.immediate_input_cost, wanted["cost"])
            self.assertEqual(str(actual.survival.worlds), wanted["survival_worlds"])
            self.assertEqual(asdict(actual.eligibility), wanted["eligibility"])
            self.assertEqual(actual.target_count, wanted["target_floor"])
            self.assertEqual(actual.survival_probability, fraction(wanted["survival_probability"]))
            self.assertEqual(actual.survival_weighted_target_floor_per_input,
                             fraction(wanted["survival_weighted_target_floor_per_input"]))
            for zero, expected_zero in zip(actual.zero_targets, wanted["zero_targets"]):
                self.assertEqual(list(zero.cell), expected_zero["cell"])
                self.assertEqual(str(zero.event.worlds), expected_zero["zero_and_survive_worlds"])
                self.assertEqual(zero.zero_and_survive_probability, fraction(expected_zero["joint_probability"]))
                self.assertEqual(zero.zero_given_survival_probability, fraction(expected_zero["conditional_probability"]))

    def test_strict_public_payload(self):
        public = {"observation": CENTER, "num_mines": 1}
        for key in ("layout", "actual_layout", "seed", "3BV", "active", "wasted", "clock",
                    "future_inputs", "private_id", "ledger", "mode", "target", "C"):
            with self.assertRaises((TypeError, ValueError)):
                candidates.CandidateRequest.from_payload(dict(public, **{key: 0}))
        for payload in (dict(public, limits={"private": 0}),
                        dict(public, observation=[[{"value": -2}]]),
                        dict(public, observation=[[True]]), dict(public, num_mines=True),
                        dict(public, observation=[[-4]]), dict(public, observation=[[]]),
                        dict(public, observation=[[-2], [-2, -2]])):
            with self.assertRaises((TypeError, ValueError)):
                candidates.CandidateRequest.from_payload(payload)
        with self.assertRaises(TypeError):
            candidates.analyze_candidates(public)

    def test_limits_validation(self):
        defaults = asdict(candidates.CandidateLimits())
        for name, cap in defaults.items():
            for value in (-1, cap + 1, True, float("nan"), "0"):
                with self.assertRaises(ValueError):
                    candidates.CandidateLimits(**{name: value})
        unsupported = call(candidates.CandidateRequest(CENTER, 1, prior_id="another_prior"))
        self.assertEqual(unsupported.status, "UNSUPPORTED")
        self.assertEqual(unsupported.diagnostics.backend_calls, 0)

    def test_immutable_dtos_and_exact_serialization(self):
        grid = [list(row) for row in CENTER]
        request = candidates.CandidateRequest(grid, 1)
        grid[0][0] = -3
        self.assertEqual(request.observation, CENTER)
        with self.assertRaises(FrozenInstanceError):
            request.num_mines = 0
        result = call(request)
        with self.assertRaises(FrozenInstanceError):
            result.candidates[0].immediate_input_cost = 8
        self.assertEqual(result.to_dict()["base"]["total_worlds"], "8")
        self.assertEqual(result.to_dict()["candidates"][0]["survival_probability"],
                         {"numerator": "7", "denominator": "8"})
        self.assertFalse({"selected_action", "terminal_outcome", "score", "E[X]", "target_probability"}
                         & set(result.to_dict()))

    def test_same_public_different_layout_and_identity(self):
        grids = []
        for layout in ({(0, 0)}, {(2, 2)}):
            grid = [[-2] * 3 for _ in range(3)]
            grid[1][1] = sum(max(abs(x - 1), abs(y - 1)) == 1 for x, y in layout)
            grids.append(grid)
        left = candidates.CandidateRequest(grids[0], 1)
        right = candidates.CandidateRequest(grids[1], 1)
        self.assertEqual(left.identity, right.identity)
        self.assertEqual(left.to_payload(), right.to_payload())
        first = call(left)
        limited = call(replace(right, limits=candidates.CandidateLimits(max_generated=100)))
        self.assertNotEqual(first.request_id, limited.request_id)
        self.assertEqual([c.candidate_id for c in first.candidates], [c.candidate_id for c in limited.candidates])
        flagged = candidates.CandidateRequest(FIXTURES[1][1], 1)
        self.assertNotEqual(left.observation_id, flagged.observation_id)

    def test_flag_preparation_recall_cost(self):
        before = call(candidates.CandidateRequest(CENTER, 1))
        after = call(candidates.CandidateRequest(FIXTURES[1][1], 1))
        self.assertEqual(before.candidates[8].immediate_input_cost, 2)
        self.assertEqual(after.candidates[8].immediate_input_cost, 1)
        self.assertEqual(after.candidates[9].immediate_input_cost, 3)
        self.assertEqual(after.candidates[0].immediate_input_cost, 2)
        self.assertEqual(before.base, after.base)

    def test_zero_overlap_and_joint_survival(self):
        result = call(candidates.CandidateRequest(FIXTURES[1][1], 1))
        chord = result.candidates[8]
        self.assertEqual(chord.survival_probability, Fraction(1, 8))
        self.assertNotEqual(chord.survival_probability, Fraction(7, 8) ** 7)
        self.assertEqual(sum(z.event.worlds for z in chord.zero_targets), 5)
        self.assertEqual(chord.target_count, 7)

    def test_zero_limits_base(self):
        for field, expected in (("max_cells", "UNSUPPORTED"), ("max_backend_calls", "INSUFFICIENT"),
                                ("max_total_backend_work", "INSUFFICIENT"), ("max_seconds", "INSUFFICIENT")):
            result = call(candidates.CandidateRequest(CENTER, 1, candidates.CandidateLimits(**{field: 0})))
            self.assertEqual(result.status, expected)
            self.assertEqual(result.diagnostics.backend_calls, 0)
            self.assertIsNone(result.base.total_worlds)
            self.assertIsNone(result.has_proven_safe_cell)
            self.assertFalse(result.catalogue_complete)

    def test_zero_catalogue_and_event_limits(self):
        for field in ("max_generated", "max_candidates", "max_distinct_events"):
            result = call(candidates.CandidateRequest(CENTER, 1, candidates.CandidateLimits(**{field: 0})))
            self.assertEqual(result.status, "PARTIAL")
            self.assertEqual(result.base.total_worlds, 8)
            self.assertFalse(result.evidence_complete)
            self.assertEqual(result.diagnostics.backend_calls, 1)
        complete = call(candidates.CandidateRequest(((-2, -2),), 0,
                                                   candidates.CandidateLimits(max_distinct_events=0)))
        self.assertEqual(complete.status, "COMPLETE")

    def test_generation_and_candidate_limits(self):
        for field, generated in (("max_generated", 3), ("max_candidates", 4)):
            result = call(candidates.CandidateRequest(CENTER, 1, candidates.CandidateLimits(**{field: 3})))
            self.assertEqual(result.status, "PARTIAL")
            self.assertEqual(len(result.candidates), 3)
            self.assertEqual(result.diagnostics.generated, generated)
            self.assertFalse(result.catalogue_complete)
            self.assertTrue(all(c.survival.worlds == 7 for c in result.candidates))

    def test_event_limit_preserves_survival_unknowns(self):
        result = call(candidates.CandidateRequest(CENTER, 1, candidates.CandidateLimits(max_distinct_events=1)))
        self.assertEqual(result.status, "PARTIAL")
        self.assertTrue(result.catalogue_complete)
        self.assertFalse(result.event_collection_complete)
        self.assertEqual(result.diagnostics.queued_events, 1)
        self.assertEqual(result.candidates[0].survival.worlds, 7)
        self.assertIsNone(result.candidates[0].zero_targets[0].event.worlds)
        self.assertIsNone(result.candidates[8].survival.worlds)
        self.assertEqual(asdict(result.candidates[8].eligibility), dict.fromkeys(asdict(result.candidates[8].eligibility)))

    def test_total_work_and_call_caps(self):
        for limits in (candidates.CandidateLimits(max_backend_calls=1),
                       candidates.CandidateLimits(max_total_backend_work=1),
                       candidates.CandidateLimits(max_total_backend_work=150)):
            result = call(candidates.CandidateRequest(CENTER, 1, limits))
            self.assertIn(result.status, ("PARTIAL", "INSUFFICIENT"))
            self.assertLessEqual(result.diagnostics.backend_calls, limits.max_backend_calls)
            self.assertLessEqual(result.diagnostics.backend_work, limits.max_total_backend_work)
            spent = 0
            for row in result.diagnostics.backend_trace:
                self.assertLessEqual(row.work_limit, limits.max_total_backend_work - spent)
                self.assertLessEqual(row.work_limit, 200000)
                self.assertLessEqual(row.seconds_limit, 2)
                self.assertLessEqual(row.event_count, 16)
                spent += row.work

    def test_backend_reordering_and_event_deduplication(self):
        seen = []
        def reversed_events(request, **kwargs):
            seen.extend(request.events)
            result = real_count_public(request, **kwargs)
            return replace(result, events=tuple(reversed(result.events)))
        with backend(reversed_events):
            result = call(candidates.CandidateRequest(CENTER, 1))
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(len(set(seen)), len(seen))
        self.assertGreater(result.diagnostics.duplicate_event_references, 0)
        self.assertEqual(result.candidates[8].survival.worlds, 1)
        self.assertEqual([z.event.worlds for z in result.candidates[8].zero_targets], [0, 1, 0, 1, 1, 1, 1])

    def test_backend_public_binding_mismatch(self):
        def wrong(request, **kwargs):
            result = real_count_public(request, **kwargs)
            return replace(result, request_id="0" * 64) if request.events else result
        with backend(wrong):
            result = call(candidates.CandidateRequest(CENTER, 1))
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.base.total_worlds, 8)
        self.assertEqual(result.diagnostics.backend_calls, 2)
        self.assertTrue(all(row.survival.worlds == 7 for row in result.candidates[:8]))

    def test_backend_base_mismatch(self):
        def wrong(request, **kwargs):
            result = real_count_public(request, **kwargs)
            if request.events:
                base = replace(result.base, total_worlds=16,
                               marginals=tuple(replace(m, mine_worlds=m.mine_worlds * 2) for m in result.base.marginals))
                return replace(result, base=base)
            return result
        with backend(wrong):
            result = call(candidates.CandidateRequest(CENTER, 1))
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.base.total_worlds, 8)
        self.assertEqual(result.diagnostics.backend_calls, 2)

    def test_backend_duplicate_missing_and_invalid_events(self):
        for defect in ("duplicate", "missing", "numeric"):
            def wrong(request, **kwargs):
                result = real_count_public(request, **kwargs)
                if not request.events:
                    return result
                rows = result.events
                if defect == "duplicate":
                    rows = rows + (rows[0],)
                elif defect == "missing":
                    rows = rows[1:]
                else:
                    rows = (replace(rows[0], event_worlds=result.base.total_worlds + 1),) + rows[1:]
                return replace(result, events=rows)
            with backend(wrong):
                result = call(candidates.CandidateRequest(CENTER, 1))
            self.assertEqual(result.status, "ERROR")
            self.assertEqual(result.diagnostics.backend_calls, 2)
            self.assertEqual(result.base.total_worlds, 8)

    def test_backend_malformed_response_and_exception(self):
        def raises(request, **kwargs):
            raise RuntimeError("deliberate backend fault")
        for function in (lambda request, **kwargs: None, raises):
            with backend(function):
                result = call(candidates.CandidateRequest(CENTER, 1))
            self.assertEqual(result.status, "ERROR")
            self.assertEqual(result.diagnostics.backend_calls, 1)
            self.assertFalse(result.diagnostics.work_accounting_complete)

    def test_backend_partial_event_batch(self):
        def partial(request, **kwargs):
            result = real_count_public(request, **kwargs)
            if request.events:
                rows = (result.events[0],) + tuple(replace(r, status="NOT_EVALUATED", reason="TEST_STOP",
                                                          event_worlds=None, probability=None) for r in result.events[1:])
                return replace(result, status="PARTIAL", reason="TEST_STOP", events=rows)
            return result
        with backend(partial):
            result = call(candidates.CandidateRequest(CENTER, 1))
        self.assertEqual(result.status, "PARTIAL")
        self.assertTrue(result.catalogue_complete)
        self.assertTrue(result.event_collection_complete)
        self.assertEqual(result.candidates[0].survival.worlds, 7)
        self.assertTrue(any(e.reason == "TEST_STOP" and e.worlds is None for e in result.events))
        self.assertTrue(any(e.status == "EXACT" and not e.reason.startswith("BASE_") for e in result.events))

    def test_backend_later_base_failure(self):
        def stopped(request, **kwargs):
            result = real_count_public(request, **kwargs)
            if request.events:
                return replace(result, status="INSUFFICIENT", reason="WORK_LIMIT",
                               base=BaseResult("INSUFFICIENT", "WORK_LIMIT"))
            return result
        with backend(stopped):
            result = call(candidates.CandidateRequest(CENTER, 1))
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.base.total_worlds, 8)
        self.assertEqual(result.diagnostics.backend_calls, 2)

    def test_controlled_clock_stop_stages(self):
        original = candidates._Budget.check
        for target in ("request", "base", "base.after", "catalogue", "events.collect",
                       "batch.0", "batch.0.after", "publish.before", "publish.after"):
            clock = [0.0]
            def check(budget, stage=None):
                if stage == target:
                    clock[0] = 20.0
                return original(budget, stage)
            with patch.object(candidates, "perf_counter", lambda: clock[0]), patch.object(candidates._Budget, "check", check):
                result = call(candidates.CandidateRequest(CENTER, 1), "clock:" + target)
            self.assertEqual(result.reason, "TIME_LIMIT")
            self.assertEqual(result.status, "INSUFFICIENT" if target in ("request", "base") else "PARTIAL")
            if target == "publish.after":
                self.assertTrue(all(row.status == "EXACT" for row in result.candidates))
                self.assertFalse(result.evidence_complete)

    def test_cancellation_at_boundaries(self):
        original = candidates._Budget.check
        for target in ("request", "base.after", "catalogue", "events.collect", "batch.0.after", "publish.after"):
            current = [None]
            def check(budget, stage=None):
                if stage is not None:
                    current[0] = stage
                return original(budget, stage)
            with patch.object(candidates._Budget, "check", check):
                result = call(candidates.CandidateRequest(CENTER, 1), "cancel:" + target,
                              cancelled=lambda: current[0] == target)
            self.assertEqual(result.status, "CANCELLED" if target == "request" else "PARTIAL")
            self.assertEqual(result.reason, "CANCELLED")

    def test_callback_errors_before_and_after_base(self):
        original = candidates._Budget.check
        for target in ("request", "base.after", "batch.0", "publish.after"):
            for response in (None, "exception"):
                current = [None]
                def check(budget, stage=None):
                    if stage is not None:
                        current[0] = stage
                    return original(budget, stage)
                def cancel():
                    if current[0] != target:
                        return False
                    if response == "exception":
                        raise RuntimeError("deliberate callback fault")
                    return response
                with patch.object(candidates._Budget, "check", check):
                    result = call(candidates.CandidateRequest(CENTER, 1), cancelled=cancel)
                self.assertEqual(result.status, "ERROR")
                self.assertEqual(result.reason, "CANCEL_CALLBACK_ERROR")

    def test_callback_failure_inside_backend(self):
        callbacks = [0]
        def bad_callback():
            callbacks[0] += 1
            return None if callbacks[0] == 20 else False
        result = call(candidates.CandidateRequest(CENTER, 1), cancelled=bad_callback)
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.reason, "CANCEL_CALLBACK_ERROR")
        self.assertEqual(result.diagnostics.backend_calls, 1)
        self.assertGreater(result.diagnostics.backend_work, 0)

    def test_repeat_call_state_and_no_global_cache(self):
        request = candidates.CandidateRequest(CENTER, 1)
        payload = deepcopy(request.to_payload())
        replies = [call(request) for _ in range(2)]
        self.assertEqual(request.to_payload(), payload)
        self.assertEqual(replies[0].candidates, replies[1].candidates)
        self.assertGreater(replies[0].diagnostics.backend_calls, 1)
        self.assertEqual(replies[0].diagnostics.backend_calls, replies[1].diagnostics.backend_calls)
        self.assertEqual(replies[0].diagnostics.backend_work, replies[1].diagnostics.backend_work)

    def test_no_candidates_no_lifecycle_and_fatal_evidence(self):
        empty = call(candidates.CandidateRequest(((0, 0),), 0))
        self.assertEqual(empty.status, "COMPLETE")
        self.assertEqual(empty.candidates, ())
        self.assertFalse(empty.has_proven_safe_cell)
        fatal = call(candidates.CandidateRequest(((-2, -3),), 2))
        self.assertEqual(len(fatal.candidates), 2)
        for row in fatal.candidates:
            self.assertEqual(row.survival.worlds, 0)
            self.assertEqual(row.zero_targets[0].event.worlds, 0)
            self.assertIsNone(row.zero_targets[0].zero_given_survival_probability)
            self.assertFalse(any(asdict(row.eligibility).values()))


def fraction(value):
    if value is None:
        return None
    return Fraction(int(value["numerator"]), int(value["denominator"]))


class EngineTests(unittest.TestCase):
    def test_fixed_engine_candidate_layout_matrix(self):
        from core_engine import Action, GameStatus, MinesweeperEngine
        engine_inputs = ENGINE_INPUTS
        if engine_inputs is None:
            engine_inputs = {name: (analyze_grid(grid, mines, CONSUME),
                                   call(candidates.CandidateRequest(grid, mines)).to_dict())
                             for name, grid, mines in FIXTURES[:5]}
        coverage = {"macros": 0, "loss_with_partial_open": 0, "safe_flag_flood": 0,
                    "auto_flag_win": 0, "zero_overlap": 0, "flag_removal": 0, "flag_preparation": 0}
        for name, grid, mine_count in FIXTURES[:5]:
            oracle, result = engine_inputs[name]
            width, height = len(grid[0]), len(grid)
            self.assertEqual(len(result["candidates"]), len(oracle["candidates"]))
            for candidate in result["candidates"]:
                targets = {tuple(map(int, cell)) for cell in candidate["targets"]}
                survival_count = 0
                zero_counts = {cell: 0 for cell in targets}
                for layout_values in oracle["layouts"]:
                    CONSUME("engine_macros", 1)
                    coverage["macros"] += 1
                    layout = {tuple(map(int, cell)) for cell in layout_values}
                    engine = MinesweeperEngine(width, height, mine_count)
                    engine.reset_with_mines(width, height, mine_count, layout)
                    rows = []
                    def step(action, x, y, phase):
                        CONSUME("engine_atomic_inputs", 1)
                        before = engine.get_observation()
                        engine.step(x, y, getattr(Action, action))
                        after = engine.get_observation()
                        counter = engine.get_counter_snapshot()
                        rows.append({"phase": phase, "action": action, "x": x, "y": y,
                                     "before": before, "after": after,
                                     "counted_total": counter["active_clicks"] + counter["wasted_clicks"],
                                     "status": engine.status.name})
                    for action, x, y in PREFIXES[name]:
                        self.assertEqual(engine.status, GameStatus.PLAYING)
                        step(action, x, y, "prefix")
                    self.assertEqual(engine.get_observation(), [list(row) for row in grid])
                    self.assertEqual(engine.status, GameStatus.PLAYING)
                    start_counter = engine.get_counter_snapshot()
                    before_count = start_counter["active_clicks"] + start_counter["wasted_clicks"]
                    original_open = {(x, y) for y, row in enumerate(grid) for x, value in enumerate(row) if value >= 0}
                    for move in candidate["sequence"]:
                        x, y, action = int(move["x"]), int(move["y"]), move["action"]
                        self.assertEqual(engine.status, GameStatus.PLAYING)
                        if action == "FLAG":
                            key = "flag_removal" if engine.get_observation()[y][x] == -3 else "flag_preparation"
                            coverage[key] += 1
                        step(action, x, y, "candidate")
                    after = engine.get_observation()
                    end_counter = engine.get_counter_snapshot()
                    counted_delta = end_counter["active_clicks"] + end_counter["wasted_clicks"] - before_count
                    self.assertEqual(counted_delta, int(candidate["immediate_input_cost"]))
                    survival = not (targets & layout)
                    self.assertEqual(engine.status != GameStatus.LOST, survival)
                    new_safe = {(x, y) for y, row in enumerate(after) for x, value in enumerate(row) if value >= 0} - original_open
                    if survival:
                        survival_count += 1
                        self.assertGreaterEqual(len(new_safe), len(targets))
                        self.assertTrue(targets <= new_safe)
                        for x, y in targets:
                            zero_counts[(x, y)] += after[y][x] == 0
                    elif candidate["kind"] == "CHORD" and new_safe:
                        coverage["loss_with_partial_open"] += 1
                    last_before = rows[-1]["before"]
                    coverage["safe_flag_flood"] += sum(last_before[y][x] == -3 and (x, y) not in layout for x, y in new_safe)
                    if engine.status == GameStatus.WON:
                        coverage["auto_flag_win"] += sum(last_before[y][x] != -3 and after[y][x] == -3 for x, y in layout)
                    zero_targets = {cell for cell in targets if after[cell[1]][cell[0]] == 0}
                    if survival and len(zero_targets) > 1:
                        coverage["zero_overlap"] += 1
                    EMIT("engine", {"fixture": name, "candidate_id": candidate["candidate_id"],
                                    "layout": sorted(layout), "prefix": PREFIXES[name], "rows": rows,
                                    "counted_delta": counted_delta, "survival": survival,
                                    "target_count": len(targets), "new_safe_count": len(new_safe), "match": True})
                self.assertEqual(survival_count, int(candidate["survival"]["worlds"]))
                for zero in candidate["zero_targets"]:
                    self.assertEqual(zero_counts[tuple(map(int, zero["cell"]))], int(zero["event"]["worlds"]))
                EMIT("engine_counts", {"fixture": name, "candidate_id": candidate["candidate_id"],
                                       "survival_worlds": survival_count,
                                       "zero_worlds": {str(cell): value for cell, value in zero_counts.items()},
                                       "match": True})
        self.assertEqual(coverage["macros"], 339)
        for key in coverage:
            self.assertGreater(coverage[key], 0, key)
        EMIT("engine_coverage", coverage)


if __name__ == "__main__":
    unittest.main()
