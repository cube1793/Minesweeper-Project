"""Registered Unit 2 checks. Hidden data stays in the evaluator records."""

from dataclasses import fields, replace
from fractions import Fraction
import json
import types
import unittest
from unittest.mock import patch

from core_engine import Action, GameStatus, MinesweeperEngine
import stage4_opening
import stage4_planning as planning
import stage4_planning_oracle as oracle


H, F = -2, -3
PUBLIC_CORPUS = [
    {"name": "opening_five", "observation": [[H, 1, H, H, H]], "mines": 1, "prefix": 1},
    {"name": "blind_triplet", "observation": [[H, H, H]], "mines": 1, "prefix": 0},
    {"name": "two_ends", "observation": [[H, 1, H]], "mines": 1, "prefix": 1},
    {"name": "guess_blocked", "observation": [[H, H, 1], [H, H, 1]], "mines": 1, "prefix": 2},
    {"name": "leak_flags", "observation": [[F, 1, H, H, H]], "mines": 1, "prefix": 2},
    {"name": "leak_progress", "observation": [[H, H, 1, H, H]], "mines": 2, "prefix": 1},
    {"name": "flagged_minimum", "observation": [[H, 1, H, F, F, F, F, F]], "mines": 2, "prefix": 6},
    {"name": "existing_chord", "observation": [[1, F, H], [1, 1, 1], [H, H, H]], "mines": 1, "prefix": 5},
    {"name": "shared_flag", "observation": [[1, H, 1], [H, H, H], [1, H, 1]], "mines": 1, "prefix": 4},
    {"name": "shared_flag_existing", "observation": [[1, H, 1], [H, F, H], [1, H, 1]], "mines": 1, "prefix": 5},
    {"name": "correlated_chord", "observation": [[F, H, H], [H, 1, H], [H, H, H]], "mines": 1, "prefix": 2},
]
TRANSITION_EXTRAS = [
    {"name": "opened_zero_barrier", "observation": [[H, 0, H]], "mines": 0, "prefix": 1},
    {"name": "flood_clears_safe_flag", "observation": [[H, F, H]], "mines": 0, "prefix": 1},
    {"name": "flag_repair", "observation": [[1, F, 1], [H, H, H], [1, H, 1]], "mines": 1, "prefix": 5},
]
FIXTURES = {item["name"]: item for item in PUBLIC_CORPUS}
PUBLIC_RUNS = []
PRIVATE_TRANSITIONS = []
PRIVATE_RUNS = []
ORACLE_COMPARISONS = []
BOUNDARIES = {}
PLAN_CALLS = 0


def as_fraction(value):
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def score_tuple(score):
    return tuple(as_fraction(score[field.name]) for field in fields(planning.Score))


def move_tuple(move):
    return None if move is None else (move["action"], int(move["x"]), int(move["y"]))


def request_for(name, mode="S", guess=True, target=None, **changes):
    item = FIXTURES[name]
    grid = item["observation"]
    opened = next(((x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v >= 0), (0, 0))
    identity = planning.public_observation_id(grid, item["mines"])
    # Public fixture prefixes are registered counts, with no engine stats.
    ledger = tuple(planning.PublicInput("OPEN", *opened, True, identity) for _ in range(item["prefix"]))
    request = planning.PlanningRequest(grid, item["mines"], ledger, mode, guess, target)
    return replace(request, **changes) if changes else request


def run_plan(request, label):
    global PLAN_CALLS
    PLAN_CALLS += 1
    if PLAN_CALLS > 256:
        raise RuntimeError("Registered plan-call budget exceeded")
    result = planning.plan_next(request)
    PUBLIC_RUNS.append({"label": label, "request": planning.exact_json(request), "result": result})
    return result


def stable(result):
    copy = dict(result)
    copy["resources"] = {key: value for key, value in result["resources"].items() if key != "elapsed_seconds"}
    return copy


def make_engine(width, height, mines):
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), mines)
    return engine


def input_engine(engine, ledger, action, x, y, *, delivered=True):
    playing = engine.status == GameStatus.PLAYING
    if delivered:
        engine.step(x, y, getattr(Action, action, 99))
    observation = engine.get_observation()
    ledger = planning.record_input(ledger, action, x, y, observation, engine.num_mines,
                                   playing=playing, delivered=delivered)
    return ledger


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.clock_patch = patch("core_engine.time", types.SimpleNamespace(perf_counter=lambda: 0.0))
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)

    def test_public_dto_allowlist_and_identity(self):
        request = request_for("opening_five")
        self.assertEqual(request.total_c, 1)
        self.assertEqual({f.name for f in fields(planning.PublicInput)},
                         {"action", "x", "y", "counted", "observation_id"})
        forbidden = ("active", "wasted", "seed", "snapshot", "stats", "completed_3bv",
                     "completed_ops", "ioe", "efficiency", "zini", "hidden_classes")
        payload = {"observation": [[H, 1, H]], "num_mines": 1}
        for name in forbidden:
            with self.assertRaises(ValueError):
                planning.PlanningRequest.from_payload({**payload, name: 1})
            with self.assertRaises(TypeError):
                planning.PublicInput("OPEN", 0, 0, True, request.observation_id, **{name: 1})
        with self.assertRaises(ValueError):
            replace(request, observation_id="0" * 64)
        with self.assertRaises(TypeError):
            planning.plan_next(object())
        for grid in ([[True]], [[-4]], [[9]], [[0], [0, 1]], []):
            with self.assertRaises(ValueError):
                planning.PlanningRequest(grid, 0)
        for target in (0, -1, 0.5, "0/1", "1/0"):
            with self.assertRaises(ValueError):
                replace(request, target=target)
        for limit in ({"max_closed": 9}, {"max_depth": 13}, {"max_seconds": float("nan")}):
            with self.assertRaises(ValueError):
                planning.Limits(**limit)
        BOUNDARIES["dto"] = {"unknown_fields_rejected": forbidden, "only_public_receipts": True}

    def test_counterexample_pairs_have_identical_public_policy(self):
        pairs = [
            ("flag_split", 1, [[(0, 0)], [(2, 0)]], [("OPEN", 1, 0), ("FLAG", 0, 0)]),
            ("progress_split", 2, [[(1, 0), (4, 0)], [(0, 0), (1, 0)]], [("OPEN", 2, 0)]),
        ]
        for name, mines, layouts, inputs in pairs:
            results, requests, private = [], [], []
            for layout in layouts:
                engine = make_engine(5, 1, layout)
                ledger = ()
                for action in inputs:
                    ledger = input_engine(engine, ledger, *action)
                request = planning.PlanningRequest(engine.get_observation(), mines, ledger, "M", True)
                requests.append(request)
                results.append(run_plan(request, name))
                private.append({"layout": layout, "counters": engine.get_counter_snapshot()})
            self.assertEqual(requests[0], requests[1])
            self.assertEqual(requests[0].identity, requests[1].identity)
            self.assertEqual(stable(results[0]), stable(results[1]))
            self.assertEqual(results[0]["status"], "OK")
            if name == "flag_split":
                self.assertNotEqual(private[0]["counters"]["active_clicks"], private[1]["counters"]["active_clicks"])
            else:
                self.assertEqual([row["counters"]["completed_3bv"] for row in private], [1, 0])
            PRIVATE_RUNS.append({"name": name, "private_evaluators": private})

    def test_exact_tree_and_selection_against_independent_oracle(self):
        names = ("blind_triplet", "two_ends", "opening_five", "guess_blocked", "leak_progress",
                 "shared_flag", "existing_chord")
        for name in names:
            for mode in ("S", "M", "R"):
                with self.subTest(name=name, mode=mode):
                    target = Fraction(1) if mode == "R" else None
                    request = request_for(name, mode, name != "guess_blocked", target)
                    actual = run_plan(request, "oracle_" + name)
                    reference = oracle.Oracle(request.observation, request.num_mines, mode,
                                              request.allow_guess, target).solve(request.total_c)
                    self.assertEqual(actual["status"], "OK", actual["resources"])
                    self.assertEqual(actual["exactness"], "EXACT_WITHIN_DECLARED_FAMILY")
                    self.assertEqual(score_tuple(actual["score"]), reference["score"])
                    self.assertEqual(move_tuple(actual["action"]), reference["action"])
                    candidates = actual["trace"][actual["root"]]["candidates"]
                    actual_values = {move_tuple(row["move"]): (score_tuple(row["score"]), as_fraction(row["survival"]))
                                     for row in candidates}
                    expected_values = {key: (row["score"], row["survival"])
                                       for key, row in reference["candidates"].items()}
                    self.assertEqual(actual_values, expected_values)
                    ORACLE_COMPARISONS.append({"fixture": name, "mode": mode, "action": reference["action"],
                                               "score": planning.exact_json(reference["score"]),
                                               "candidates": planning.exact_json([
                                                   {"move": key, "score": row["score"], "survival": row["survival"]}
                                                   for key, row in reference["candidates"].items()]), "match": True})

    def test_public_branches_merge_and_diverge_without_clairvoyance(self):
        request = request_for("blind_triplet", "M")
        actual = run_plan(request, "nonanticipation")
        self.assertEqual(actual["status"], "OK")
        root = actual["trace"][actual["root"]]
        route = next(row for row in root["routes"] if [move_tuple(m) for m in row["inputs"]] == [("OPEN", 1, 0)])
        self.assertEqual(as_fraction(route["score"]["expected_x"]), Fraction(1, 6))
        self.assertEqual(as_fraction(route["score"]["win_probability"]), Fraction(1, 3))
        living = [branch for branch in route["branches"] if branch["outcome"] is None]
        self.assertEqual(len(living), 1)
        self.assertEqual(actual["trace"][living[0]["child"]]["world_count"], "2")
        wrong = Fraction(0)
        reference = oracle.Oracle(request.observation, 1)
        for board in reference.boards:
            after, outcome = reference.step(reference.initial, board, ("OPEN", 1, 0))
            if outcome != "LOST":
                clairvoyant = oracle.Oracle(request.observation, 1)
                wrong += clairvoyant.solve(1, after, (board,), 11)["score"][0] / len(reference.boards)
        self.assertEqual(wrong, Fraction(1, 3))
        self.assertGreater(wrong, as_fraction(route["score"]["expected_x"]))
        five = run_plan(request_for("opening_five", "M"), "divergent_numbers")
        split = next(row for row in five["trace"][five["root"]]["routes"]
                     if [move_tuple(m) for m in row["inputs"]] == [("OPEN", 3, 0)])
        self.assertEqual(len(split["branches"]), 2)
        self.assertNotEqual(split["branches"][0]["observation"], split["branches"][1]["observation"])
        BOUNDARIES["nonanticipation"] = {"public_expected_x": planning.exact_json(Fraction(1, 6)),
                                         "clairvoyant_expected_x": planning.exact_json(wrong),
                                         "merged_worlds": "2", "divergent_public_results": "2"}

    def test_guess_disabled_progress_then_distinct_blocked_terminal(self):
        for mode in ("S", "M", "R"):
            engine = make_engine(3, 2, [(1, 0)])
            ledger = input_engine(engine, (), "OPEN", 2, 0)
            ledger = input_engine(engine, ledger, "OPEN", 2, 1)
            actions = []
            for expected in (("OPEN", 0, 0), ("OPEN", 0, 1), None):
                request = planning.PlanningRequest(engine.get_observation(), 1, ledger, mode, False,
                                                   Fraction(1) if mode == "R" else None)
                result = run_plan(request, "blocked_progress_" + mode)
                self.assertEqual(move_tuple(result["action"]), expected)
                if expected is None:
                    self.assertEqual((result["status"], result["reason"], result["terminal_outcome"]),
                                     ("DEFER", "GUESS_DISABLED", "GUESS_BLOCKED"))
                    self.assertIsNone(result["score"]["conditional_ioe"])
                    self.assertEqual(score_tuple(result["score"]), (0, 0, 0, 0, 1))
                else:
                    actions.append(expected)
                    ledger = input_engine(engine, ledger, *expected)
            self.assertEqual(engine.status, GameStatus.PLAYING)
            self.assertEqual(sum(entry.counted for entry in ledger), 4)
            PRIVATE_RUNS.append({"name": "guess_blocked", "mode": mode, "actions": actions,
                                 "attempts": 1, "WON": 0, "LOST": 0, "GUESS_BLOCKED": 1, "UNRESOLVED": 0})

    def test_s_minimum_risk_includes_flagged_cells_and_replans(self):
        request = request_for("flagged_minimum", "S")
        result = run_plan(request, "all_closed_minimum")
        self.assertEqual(result["status"], "OK", result["resources"])
        self.assertEqual(result["world_count"], "10")
        evidence = {tuple(int(v) for v in row["coordinate"]): row for row in result["evidence"]}
        for x in (0, 2):
            self.assertEqual(evidence[(x, 0)]["mine_worlds"], "5")
        for x in range(3, 8):
            self.assertEqual(evidence[(x, 0)]["mine_worlds"], "2")
        first = move_tuple(result["action"])
        self.assertEqual(first[0], "FLAG")
        self.assertIn(first[1], range(3, 8))
        after = [list(row) for row in request.observation]
        after[0][first[1]] = H
        ledger = planning.record_input(request.ledger, *first, after, 2, playing=True)
        second = run_plan(planning.PlanningRequest(after, 2, ledger, "S", True), "minimum_after_unflag")
        self.assertEqual(second["status"], "OK", second["resources"])
        self.assertEqual(move_tuple(second["action"]), ("OPEN", first[1], 0))
        self.assertEqual(second["prefix_c"], "7")
        old = stage4_opening.analyze_openings(request.observation, 2, [(0, 0), (2, 0)], mode=stage4_opening.SAFETY_PRESERVING,
                                              allow_guess=True)
        self.assertEqual(old.global_minimum_risk, Fraction(1, 2))
        for row in result["trace"][result["root"]]["routes"]:
            endpoint = move_tuple(row["inputs"][-1])
            self.assertEqual(endpoint[0], "OPEN")
            self.assertIn(endpoint[1], range(3, 8))
            self.assertEqual(row["atomic_cost"], "2")

    def test_atomic_transitions_and_bbbv_match_engine(self):
        comparisons = 0
        for item in PUBLIC_CORPUS + TRANSITION_EXTRAS:
            grid = item["observation"]
            width, height = len(grid[0]), len(grid)
            reference = oracle.Oracle(grid, item["mines"])
            neighbors = planning._neighbors(width, height)
            for board in reference.boards:
                mines = [(i % width, i // width) for i in oracle.indices(board[0])]
                virtual = planning._make_world(oracle.indices(board[0]), neighbors)
                self.assertEqual(virtual.bbbv, board[2])
                for kind in ("OPEN", "FLAG", "CHORD"):
                    for x, y in [(i % width, i // width) for i in range(width * height)] + [(-1, 0), (width, 0)]:
                        engine = make_engine(width, height, mines)
                        for yy, row in enumerate(grid):
                            for xx, value in enumerate(row):
                                engine._revealed[yy][xx] = value >= 0
                                engine._flagged[yy][xx] = value == F
                        self.assertEqual(engine.get_observation(), grid)
                        self.assertEqual(virtual.bbbv, engine._total_3bv)
                        expected = planning._transition(reference.initial, virtual, planning.Move(kind, x, y),
                                                        neighbors, width)
                        ledger = input_engine(engine, (), kind, x, y)
                        observed = tuple(v for row in engine.get_observation() for v in row)
                        actual_outcome = None if engine.status == GameStatus.PLAYING else engine.status.name
                        self.assertEqual((expected.observation, expected.outcome), (observed, actual_outcome),
                                         (item["name"], mines, kind, x, y))
                        counter = engine.get_counter_snapshot()
                        counted = counter["active_clicks"] + counter["wasted_clicks"]
                        self.assertEqual(counted, int(expected.counted))
                        self.assertEqual(counted, sum(v.counted for v in ledger))
                        PRIVATE_TRANSITIONS.append({"fixture": item["name"], "mines": mines,
                                                    "input": [kind, x, y], "before": grid,
                                                    "after": engine.get_observation(), "outcome": actual_outcome,
                                                    "public_ledger": planning.exact_json(ledger),
                                                    "engine_counters": counter, "virtual_bbbv": str(virtual.bbbv),
                                                    "match": True})
                        comparisons += 1
        BOUNDARIES["transition_comparisons"] = comparisons

    def test_public_ledger_counts_noops_rejections_and_terminal_requests(self):
        engine = make_engine(3, 1, [(1, 0)])
        ledger = ()
        operations = [("FLAG", 0, 0, True), ("OPEN", 0, 0, True), ("FLAG", 0, 0, True),
                      ("CHORD", 0, 0, True), ("OPEN", -1, 0, True), ("OTHER", 0, 0, True),
                      ("OPEN", 0, 0, False), ("OPEN", 0, 0, True), ("OPEN", 0, 0, True),
                      ("OPEN", 1, 0, True), ("FLAG", 2, 0, True)]
        expected_counts = [1, 2, 3, 4, 4, 4, 4, 5, 6, 7, 7]
        for (kind, x, y, delivered), total in zip(operations, expected_counts):
            ledger = input_engine(engine, ledger, kind, x, y, delivered=delivered)
            self.assertEqual(sum(entry.counted for entry in ledger), total)
            counter = engine.get_counter_snapshot()
            self.assertEqual(counter["active_clicks"] + counter["wasted_clicks"], total)
        self.assertEqual(engine.status, GameStatus.LOST)
        virtual = planning._make_world([1], planning._neighbors(3, 1))
        terminal = planning._transition(tuple(engine.get_observation()[0]), virtual,
                                        planning.Move("FLAG", 2, 0), planning._neighbors(3, 1), 3, "LOST")
        self.assertFalse(terminal.counted)
        self.assertEqual(terminal.outcome, "LOST")
        PRIVATE_RUNS.append({"name": "ledger_rejections", "operations": operations,
                             "expected_c": expected_counts, "ledger": planning.exact_json(ledger),
                             "private_counters": counter})

    def test_opening_five_actual_planner_cost_three_vs_four(self):
        totals = []
        for forced in (None, ("OPEN", 3, 0)):
            engine = make_engine(5, 1, [(2, 0)])
            ledger = input_engine(engine, (), "OPEN", 1, 0)
            initial = run_plan(planning.PlanningRequest(engine.get_observation(), 1, ledger, "S", True),
                               "five_initial")
            self.assertEqual(move_tuple(initial["action"]), ("OPEN", 4, 0))
            actions = []
            if forced:
                ledger = input_engine(engine, ledger, *forced)
                actions.append(forced)
            while engine.status == GameStatus.PLAYING:
                result = run_plan(planning.PlanningRequest(engine.get_observation(), 1, ledger, "S", True),
                                  "five_replan")
                self.assertEqual(result["status"], "OK")
                action = move_tuple(result["action"])
                actions.append(action)
                ledger = input_engine(engine, ledger, *action)
                self.assertLessEqual(len(actions), 4)
            self.assertEqual(engine.status, GameStatus.WON)
            totals.append(sum(item.counted for item in ledger))
            PRIVATE_RUNS.append({"name": "new_planner_five", "forced_first": forced, "actions": actions,
                                 "final_c": totals[-1], "bbbv": engine._total_3bv,
                                 "ledger": planning.exact_json(ledger), "outcome": "WON"})
        self.assertEqual(totals, [3, 4])

    def test_existing_chord_beats_certain_zero_priority(self):
        result = run_plan(request_for("existing_chord"), "chord_over_zero")
        self.assertEqual(result["status"], "OK")
        self.assertEqual(move_tuple(result["action"]), ("CHORD", 1, 1))
        root = result["trace"][result["root"]]
        chosen = as_fraction(result["score"]["expected_x"])
        zero = next(row for row in root["candidates"] if move_tuple(row["move"]) == ("OPEN", 1, 2))
        self.assertGreater(chosen, as_fraction(zero["score"]["expected_x"]))
        evidence = next(row for row in result["evidence"] if row["coordinate"] == ["1", "2"])
        self.assertEqual(evidence["zero_worlds"], evidence["total_worlds"])
        BOUNDARIES["high_pzero_counterexample"] = {"fixture": "existing_chord", "pzero": "1",
                                                   "zero_path_score": zero["score"], "chord_score": result["score"]}

    def test_shared_flag_preparation_and_reuse(self):
        engine = make_engine(3, 3, [(1, 1)])
        ledger = ()
        for x, y in ((0, 0), (2, 0), (0, 2), (2, 2)):
            ledger = input_engine(engine, ledger, "OPEN", x, y)
        actions = []
        while engine.status == GameStatus.PLAYING:
            result = run_plan(planning.PlanningRequest(engine.get_observation(), 1, ledger, "S", True),
                              "shared_flag_replan")
            self.assertEqual(result["status"], "OK")
            action = move_tuple(result["action"])
            actions.append(action)
            ledger = input_engine(engine, ledger, *action)
            self.assertLessEqual(len(actions), 3)
        self.assertEqual(actions[0], ("FLAG", 1, 1))
        self.assertEqual([action[0] for action in actions], ["FLAG", "CHORD", "CHORD"])
        self.assertEqual(sum(item.counted for item in ledger), 7)
        self.assertEqual(engine._total_3bv, 8)
        self.assertGreater(Fraction(8, 7), Fraction(8, 8))
        PRIVATE_RUNS.append({"name": "shared_flag", "actions": actions, "final_c": 7,
                             "direct_open_final_c": 8, "outcome": "WON", "ledger": planning.exact_json(ledger)})
        engine = make_engine(3, 3, [(1, 1)])
        ledger = ()
        for x, y in ((0, 0), (2, 0), (0, 2), (2, 2)):
            ledger = input_engine(engine, ledger, "OPEN", x, y)
        ledger = input_engine(engine, ledger, "FLAG", 1, 0)
        repairs = []
        while engine.status == GameStatus.PLAYING:
            result = run_plan(planning.PlanningRequest(engine.get_observation(), 1, ledger, "S", True), "flag_repair")
            self.assertEqual(result["status"], "OK")
            action = move_tuple(result["action"])
            repairs.append(action)
            ledger = input_engine(engine, ledger, *action)
            self.assertLessEqual(len(repairs), 4)
        self.assertEqual(sum(v.counted for v in ledger), 9)
        self.assertIn(("FLAG", 1, 0), repairs)
        self.assertIn(("FLAG", 1, 1), repairs)
        PRIVATE_RUNS.append({"name": "flag_repair", "actions": repairs, "final_c": 9,
                             "ledger": planning.exact_json(ledger), "outcome": "WON"})

    def test_chord_joint_probability_and_hypothetical_flags(self):
        request = request_for("correlated_chord", "M")
        search = planning._Search(request)
        observation, worlds = search.infer()
        routes, blocked, _ = search.routes(observation, worlds)
        self.assertFalse(blocked)
        self.assertIn((planning.Move("CHORD", 1, 1),), routes)
        transitions = [planning._transition(observation, world, planning.Move("CHORD", 1, 1),
                                             search.neighbors, 3) for world in worlds]
        joint = Fraction(sum(item.outcome != "LOST" for item in transitions), len(worlds))
        self.assertEqual(joint, Fraction(1, 8))
        self.assertNotEqual(joint, Fraction(7, 8) ** 7)
        unflagged = [list(row) for row in request.observation]
        unflagged[0][0] = H
        second = planning._Search(planning.PlanningRequest(unflagged, 1, (), "M", True))
        _, second_worlds = second.infer()
        self.assertEqual(worlds, second_worlds)
        self.assertTrue(any(item.outcome == "LOST" and sum(v >= 0 for v in item.observation) > 1
                            for item in transitions))
        BOUNDARIES["joint_chord"] = {"joint": planning.exact_json(joint),
                                     "individual_product": planning.exact_json(Fraction(7, 8) ** 7),
                                     "flagged_and_unflagged_worlds_identical": True}

    def test_modes_objectives_targets_and_exact_boundaries(self):
        a = planning.Score(Fraction(6, 5), Fraction(1), Fraction(0))
        b = planning.Score(Fraction(1), Fraction(1, 2), Fraction(1, 2), Fraction(1, 2))
        move = planning.Move("OPEN", 0, 0)
        self.assertGreater(planning.selection_key(a, Fraction(1), move, "M"),
                           planning.selection_key(b, Fraction(1, 2), move, "M"))
        self.assertGreater(planning.selection_key(b, Fraction(1, 2), move, "R"),
                           planning.selection_key(a, Fraction(1), move, "R"))
        missing = run_plan(request_for("opening_five", "R"), "target_required")
        self.assertEqual(missing["status"], "TARGET_REQUIRED")
        self.assertIsNone(missing["action"])
        actions = []
        for mode in ("S", "M", "R"):
            result = run_plan(request_for("opening_five", mode, True, Fraction(999) if mode == "R" else None),
                              "same_move_" + mode)
            self.assertEqual(result["status"], "OK")
            actions.append(move_tuple(result["action"]))
            if mode == "R":
                self.assertEqual(result["target_status"], "TARGET_UNREACHABLE")
        self.assertEqual(actions, [("OPEN", 4, 0)] * 3)
        exact = run_plan(request_for("shared_flag", "R", True, Fraction(8, 7)), "target_exact")
        above = run_plan(request_for("shared_flag", "R", True, Fraction(8, 7) + Fraction(1, 10 ** 20)), "target_above")
        self.assertEqual(as_fraction(exact["score"]["target_probability"]), 1)
        self.assertEqual(as_fraction(above["score"]["target_probability"]), 0)
        self.assertEqual(above["target_status"], "TARGET_UNREACHABLE")
        self.assertNotEqual(exact["identity"], above["identity"])
        BOUNDARIES["synthetic_objectives"] = {"A": a.to_dict(), "B": b.to_dict(), "M": "A", "R_tau_2": "B"}

    def test_safety_rules_and_risky_zero_impossible_candidates(self):
        safe = run_plan(request_for("guess_blocked", "S"), "safety_with_progress")
        risky = run_plan(request_for("guess_blocked", "M"), "risky_nonzero_candidates")
        self.assertEqual(safe["status"], "OK")
        self.assertEqual(risky["status"], "OK")
        safe_moves = {move_tuple(row["move"]) for row in safe["trace"][safe["root"]]["candidates"]}
        self.assertEqual(safe_moves, {("OPEN", 0, 0), ("OPEN", 0, 1)})
        risky_moves = {move_tuple(row["move"]) for row in risky["trace"][risky["root"]]["candidates"]}
        self.assertIn(("OPEN", 1, 0), risky_moves)
        evidence = next(row for row in risky["evidence"] if row["coordinate"] == ["1", "0"])
        self.assertEqual(evidence["zero_worlds"], "0")
        for mode in ("S", "M", "R"):
            off = run_plan(request_for("two_ends", mode, False, Fraction(1) if mode == "R" else None), "guess_off_" + mode)
            self.assertEqual(off["terminal_outcome"], "GUESS_BLOCKED")
            self.assertIsNone(off["action"])

    def test_limits_contradictions_exceptions_and_cache_separation(self):
        for grid in ([[H] * 65], [[H] * 9]):
            with patch.object(planning, "calculate_probabilities", side_effect=AssertionError("Must not infer")):
                result = run_plan(planning.PlanningRequest(grid, 1), "unsupported_size")
            self.assertEqual((result["status"], result["reason"]), ("INSUFFICIENT", "UNSUPPORTED_SIZE"))
            self.assertIsNone(result["terminal_outcome"])
        for limits, cutoff in ((planning.Limits(max_nodes=0), "NODES"), (planning.Limits(max_depth=0), "DEPTH"),
                               (planning.Limits(max_seconds=0), "TIME")):
            result = run_plan(request_for("opening_five", limits=limits), "forced_" + cutoff)
            self.assertEqual((result["status"], result["reason"]), ("INSUFFICIENT", "RESOURCE_LIMIT"))
            self.assertIsNone(result["action"])
            self.assertIsNone(result["score"])
            self.assertIsNone(result["terminal_outcome"])
            self.assertEqual(result["resources"]["cutoff"], cutoff)
        small = run_plan(request_for("blind_triplet", limits=planning.Limits(max_worlds=1)), "world_limit")
        self.assertEqual(small["reason"], "UNSUPPORTED_SIZE")
        inconsistent = run_plan(planning.PlanningRequest([[2, H]], 1), "contradiction")
        self.assertEqual(inconsistent["status"], "INCONSISTENT_INPUT")
        with patch.object(planning, "calculate_probabilities", side_effect=RuntimeError("private_text_must_not_leak")):
            failed = run_plan(request_for("opening_five"), "inference_exception")
        self.assertEqual((failed["status"], failed["reason"]), ("ERROR", "INFERENCE_FAILED"))
        self.assertNotIn("private_text", json.dumps(failed))
        request = request_for("opening_five")
        good = run_plan(request, "full_after_cutoff")
        higher_c = run_plan(replace(request, ledger=request.ledger + request.ledger), "different_c")
        prior = run_plan(replace(request, prior_id="unregistered_prior"), "different_prior")
        self.assertEqual(good["status"], "OK")
        self.assertEqual(higher_c["status"], "OK")
        self.assertNotEqual(good["score"], higher_c["score"])
        self.assertEqual(prior["reason"], "UNSUPPORTED_PRIOR")
        self.assertEqual(len({good["identity"], higher_c["identity"], prior["identity"]}), 3)

    def test_terminal_won_and_lossless_evidence(self):
        grid = [[0]]
        identity = planning.public_observation_id(grid, 0)
        ledger = (planning.PublicInput("OPEN", 0, 0, True, identity),)
        result = run_plan(planning.PlanningRequest(grid, 0, ledger), "already_won")
        self.assertEqual((result["status"], result["terminal_outcome"]), ("TERMINAL", "WON"))
        self.assertIsNone(result["action"])
        self.assertEqual(as_fraction(result["score"]["expected_x"]), 1)
        huge = 2 ** 70 + 1
        encoded = planning.exact_json({"D": huge, "ratio": Fraction(huge, huge + 2)})
        self.assertEqual(encoded["D"], str(huge))
        self.assertEqual(as_fraction(encoded["ratio"]), Fraction(huge, huge + 2))
        self.assertIsNone(planning.Score(blocked_probability=Fraction(1)).conditional_ioe)
        BOUNDARIES["large_integer_roundtrip"] = encoded

    def test_replanning_rollouts_equal_initial_public_scores(self):
        prefixes = {
            "blind_triplet": (),
            "two_ends": (("OPEN", 1, 0),),
            "opening_five": (("OPEN", 1, 0),),
            "guess_blocked": (("OPEN", 2, 0), ("OPEN", 2, 1)),
            "leak_progress": (("OPEN", 2, 0),),
            "shared_flag": (("OPEN", 0, 0), ("OPEN", 2, 0), ("OPEN", 0, 2), ("OPEN", 2, 2)),
            "existing_chord": (("OPEN", 0, 0), ("OPEN", 0, 1), ("OPEN", 1, 1),
                               ("OPEN", 2, 1), ("FLAG", 1, 0)),
        }
        comparisons = []
        for name, prefix in prefixes.items():
            item = FIXTURES[name]
            width, height = len(item["observation"][0]), len(item["observation"])
            boards = oracle.Oracle(item["observation"], item["mines"]).boards
            for mode in ("S", "M", "R"):
                target = Fraction(1) if mode == "R" else None
                average = [Fraction(0) for _ in range(5)]
                outcomes = {"WON": 0, "LOST": 0, "GUESS_BLOCKED": 0, "UNRESOLVED": 0}
                initial_score = None
                attempts = []
                for board in boards:
                    mines = [(i % width, i // width) for i in oracle.indices(board[0])]
                    engine = make_engine(width, height, mines)
                    ledger = ()
                    for action in prefix:
                        ledger = input_engine(engine, ledger, *action)
                    self.assertEqual(engine.get_observation(), item["observation"])
                    selected = []
                    outcome = None
                    while engine.status == GameStatus.PLAYING:
                        request = planning.PlanningRequest(engine.get_observation(), item["mines"], ledger,
                                                           mode, name != "guess_blocked", target)
                        result = run_plan(request, "rollout_" + name + "_" + mode)
                        if not selected:
                            initial_score = score_tuple(result["score"])
                        if result["terminal_outcome"] == "GUESS_BLOCKED":
                            outcome = "GUESS_BLOCKED"
                            break
                        self.assertEqual(result["status"], "OK", (name, mode, result["resources"]))
                        selected.append(move_tuple(result["action"]))
                        ledger = input_engine(engine, ledger, *selected[-1])
                        self.assertLessEqual(len(selected), 12)
                    if outcome is None:
                        outcome = engine.status.name
                    outcomes[outcome] += 1
                    c = sum(entry.counted for entry in ledger)
                    ioe = Fraction(engine._total_3bv, c) if outcome == "WON" else Fraction(0)
                    actual = (ioe, Fraction(outcome == "WON"),
                              Fraction(outcome == "WON" and target is not None and ioe >= target),
                              Fraction(outcome == "LOST"), Fraction(outcome == "GUESS_BLOCKED"))
                    average = [a + b / len(boards) for a, b in zip(average, actual)]
                    counter = engine.get_counter_snapshot()
                    self.assertEqual(counter["active_clicks"] + counter["wasted_clicks"], c)
                    attempts.append({"mines": mines, "actions": selected, "total_c": str(c),
                                     "outcome": outcome, "ioe": planning.exact_json(ioe)})
                self.assertEqual(tuple(average), initial_score, (name, mode))
                comparisons.append({"fixture": name, "mode": mode, "outcomes": outcomes,
                                    "attempts": attempts, "score": planning.exact_json(tuple(average)),
                                    "matches_initial_public_score": True})
        PRIVATE_RUNS.append({"name": "mode_rollout_comparisons", "comparisons": comparisons})

    def test_partial_search_cutoffs_never_return_an_action(self):
        for limits in (planning.Limits(max_depth=1), planning.Limits(max_nodes=2)):
            result = run_plan(request_for("opening_five", limits=limits), "partial_search_cutoff")
            self.assertEqual((result["status"], result["reason"]), ("INSUFFICIENT", "RESOURCE_LIMIT"))
            self.assertIsNone(result["action"])
            self.assertIsNone(result["score"])
            self.assertIsNone(result["terminal_outcome"])
            self.assertTrue(result["trace"])
        samples = 0

        def controlled_clock():
            nonlocal samples
            samples += 1
            return 0.0 if samples < 30 else 2.0

        with patch.object(planning, "monotonic", controlled_clock):
            result = run_plan(request_for("shared_flag", limits=planning.Limits(max_seconds=1)),
                              "partial_time_cutoff")
        self.assertEqual(result["resources"]["cutoff"], "TIME")
        self.assertEqual(result["reason"], "RESOURCE_LIMIT")
        self.assertIsNone(result["action"])
        self.assertIsNone(result["terminal_outcome"])
        BOUNDARIES["mid_search_cutoffs"] = {"depth": "PASS", "nodes": "PASS", "time": "PASS"}


if __name__ == "__main__":
    unittest.main()
