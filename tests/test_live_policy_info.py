"""Display-only certainty supplement of Live V1 proposals (S3X_INFO_A1).

Layouts stay on the evaluator side: they build the engine and judge what was
stated. A policy, planner or supplement only ever receives the public snapshot.
"""

from dataclasses import fields, replace
from itertools import combinations
import json
import os
import random
import tempfile
from threading import Thread
from time import sleep
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtWidgets import QApplication

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from live_analysis import CellOverlay, OverlayKind, present_v1_proposal
import live_k_policy as k_live
import live_policy as policy
import live_policy_info as supplement
import live_policy_transport as transport
import live_policy_worker as worker
import simple_decision
from simple_algorithm import InconsistentObservationError, build_constraints
from simple_probability import _enumerate_component, _split_components, calculate_probabilities
from stage3_physical import load_timing_table
import stage3_planner
from stage3_planner import Stage3PlanningError, plan_position
from tests.live_k_lc1_fixtures import singleton_start
from tests.test_live_auto import SyntheticLivePolicyJob, advance_auto_timer
from tests.ui_settings import isolate_ui_settings
from tests.zini_fixtures import _EXPERT_SEED1003_MINES
from ui_manager import MinesweeperUI


H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)
RUN = "0123456789abcdef0123456789abcdef"
TABLE = load_timing_table()
UNBOUNDED = 10 ** 9
# (width, height, mines, first OPEN). Existing test fixtures, plus fixed pseudo-random layouts.
CASE_A = (9, 9, [(1, 0), (4, 0), (7, 0), (8, 0), (7, 1), (8, 1), (7, 2), (8, 2), (7, 3), (8, 3)], (0, 8))
CASE_B = (30, 16, sorted(_EXPERT_SEED1003_MINES), (5, 0))
CASE_C = (9, 9, sorted({(1, 0)} | {(x, 8) for x in range(9)}), (4, 4))


def random_board(seed, width, height, count):
    rng = random.Random(seed)
    first = (rng.randrange(width), rng.randrange(height))
    cells = [(x, y) for y in range(height) for x in range(width) if (x, y) != first]
    return width, height, sorted(rng.sample(cells, count)), first


BOARDS = (CASE_C, CASE_A, CASE_B, *(random_board(seed, 9, 9, 10) for seed in (11, 12, 13, 14)),
          random_board(21, 16, 16, 40))


def opened(board, flags=()):
    width, height, mines, first = board
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), mines)
    observation, *_ = engine.step(first[0], first[1], Action.OPEN)
    for x, y in flags:
        observation, *_ = engine.step(x, y, Action.FLAG)
    return engine, observation


def adopt(board, observation, *, flags=0, run=RUN, generation=1):
    width, height, mines, first = board
    return policy.make_snapshot(
        run_id=run, board_generation=generation, input_seq=0, width=width, height=height,
        num_mines=len(mines), observation=observation, cursor=first,
        entry_mode=policy.ADOPT_CURRENT, input_revision=1 + flags,
        phase=policy.PHASE_FLAG_REVIEW if flags else policy.PHASE_V1, initial_flag_count=flags)


def play(board, info=None, cap=400, flags=()):
    """Yield (snapshot, proposal) for each proposal of one game, then apply that one input."""
    engine, observation = opened(board, flags)
    if engine.status != GameStatus.PLAYING:
        return
    state, review = adopt(board, observation, flags=len(flags)), None
    for _ in range(cap):
        proposal = policy.plan_snapshot(state, table=TABLE, review=review, info=info)
        yield state, proposal
        observation, *_ = engine.step(proposal.x, proposal.y, Action[proposal.action])
        if engine.status != GameStatus.PLAYING:
            return
        state = policy.validate_ack(proposal, policy.make_ack(proposal, engine.status, observation))
        review = proposal.review if state.phase == policy.PHASE_FLAG_REVIEW else None


def frozen_certain(observation, count):
    result = calculate_probabilities(observation, count)
    return (frozenset(c.coordinate for c in result.probabilities if c.mine_worlds == 0),
            frozenset(c.coordinate for c in result.probabilities if c.mine_worlds == c.total_worlds))


def stated(proposal):
    safe = {(c.x, c.y) for c in proposal.overlays if c.kind == "safe"}
    mines = {(c.x, c.y) for c in proposal.overlays if c.kind == "mine"}
    if proposal.info is not None:
        safe |= set(proposal.info.safe)
        mines |= set(proposal.info.mines)
    return safe, mines


def decision_of(proposal):
    return (proposal.snapshot, proposal.action, proposal.x, proposal.y, proposal.kind, proposal.phase,
            proposal.modeled_action_us, proposal.overlays, proposal.review)


def brute_certain(observation, count):
    """Every layout by exhaustion; None when the public state has no layout."""
    height, width = len(observation), len(observation[0])
    hidden = [(x, y) for y in range(height) for x in range(width) if observation[y][x] == H]
    flags = {(x, y) for y in range(height) for x in range(width) if observation[y][x] == F}
    clues = [(x, y, observation[y][x]) for y in range(height) for x in range(width)
             if 0 <= observation[y][x] <= 8]
    worlds = []
    for chosen in combinations(hidden, count - len(flags)) if 0 <= count - len(flags) <= len(hidden) else ():
        mines = flags | set(chosen)
        if all(sum((nx, ny) in mines for ny in range(y - 1, y + 2) for nx in range(x - 1, x + 2)) == n
               for x, y, n in clues):
            worlds.append(set(chosen))
    if not worlds:
        return None
    return (frozenset(c for c in hidden if not any(c in w for w in worlds)),
            frozenset(c for c in hidden if all(c in w for w in worlds)))


class EngineTests(unittest.TestCase):
    def test_bounded_enumerator_equals_the_frozen_one_and_stops_exactly_at_its_limit(self):
        checked = 0
        for board in BOARDS[:5]:
            for state, _proposal in play(board, cap=25):
                for component in _split_components(build_constraints(state.observation)):
                    counts, nodes = supplement.enumerate_component_bounded(component, UNBOUNDED)
                    self.assertEqual(counts, _enumerate_component(component))
                    self.assertEqual(supplement.enumerate_component_bounded(component, nodes)[1], nodes)
                    with self.assertRaises(supplement.BudgetExceeded) as stop:
                        supplement.enumerate_component_bounded(component, nodes - 1)
                    self.assertEqual(stop.exception.args, (nodes - 1,))
                    checked += 1
        self.assertGreater(checked, 50)

    def test_complete_pass_equals_frozen_exact_certainty_with_and_without_carried_proofs(self):
        states = 0
        for board in BOARDS:
            carried = supplement.CertaintyEngine()
            for state, _proposal in play(board, cap=60):
                expected = frozen_certain(state.observation, state.num_mines)
                for engine in (carried, supplement.CertaintyEngine()):
                    outcome = engine.analyze(state.observation, state.num_mines, node_budget=UNBOUNDED)
                    self.assertEqual((outcome.status, outcome.safe, outcome.mines),
                                     (supplement.COMPLETE, *expected), (board[3], state.input_seq))
                    self.assertEqual(outcome.skipped, 0)
                states += 1
        self.assertGreater(states, 120)

    def test_small_states_equal_exhaustive_enumeration_including_global_count_proofs(self):
        rng = random.Random(7)
        states = withheld = 0
        for seed in range(60):
            width, height, mines, first = board = random_board(1000 + seed, 5, 4, 3 + seed % 4)
            engine, observation = opened(board)
            carried = supplement.CertaintyEngine()
            while engine.status == GameStatus.PLAYING:
                expected = brute_certain(observation, len(mines))
                outcome = carried.analyze(observation, len(mines), node_budget=UNBOUNDED)
                self.assertEqual((outcome.safe, outcome.mines), expected)
                self.assertEqual(frozen_certain(observation, len(mines)), expected)
                limited = supplement.CertaintyEngine().analyze(observation, len(mines), node_budget=1)
                self.assertLessEqual(limited.safe, expected[0])
                self.assertLessEqual(limited.mines, expected[1])
                withheld += limited.status == supplement.PARTIAL and limited.safe | limited.mines != \
                    expected[0] | expected[1]
                states += 1
                safe = [(x, y) for y, row in enumerate(observation) for x, v in enumerate(row)
                        if v == H and (x, y) not in mines]
                if not safe:
                    break
                x, y = rng.choice(safe)
                observation, *_ = engine.step(x, y, Action.OPEN)
        self.assertGreater(states, 150)
        self.assertGreater(withheld, 0)

    def test_bounded_pass_states_only_finished_proofs_and_never_reports_completion(self):
        partial = 0
        for budget in (1, 30, 300):
            for board in BOARDS:
                mines = set(board[2])
                engine = supplement.CertaintyEngine()
                for state, _proposal in play(board, cap=40):
                    safe, mine = frozen_certain(state.observation, state.num_mines)
                    outcome = engine.analyze(state.observation, state.num_mines, node_budget=budget)
                    self.assertLessEqual(outcome.safe, safe)
                    self.assertLessEqual(outcome.mines, mine)
                    self.assertFalse(outcome.safe & mines)
                    self.assertLessEqual(outcome.mines, mines)
                    self.assertLessEqual(outcome.nodes, budget)
                    self.assertEqual(outcome.skipped > 0, outcome.status == supplement.PARTIAL)
                    if outcome.status == supplement.COMPLETE:
                        self.assertEqual((outcome.safe, outcome.mines), (safe, mine))
                    partial += outcome.status == supplement.PARTIAL
        self.assertGreater(partial, 100)

    def test_partial_pass_does_not_use_the_global_mine_count(self):
        # The clue leaves one mine between (2,0) and (4,0); with one mine in all, the two
        # cells no clue touches are safe only through the total count.
        grid = ((H, H, H, 1, H),)
        full = supplement.CertaintyEngine().analyze(grid, 1, node_budget=UNBOUNDED)
        self.assertEqual((full.status, full.safe, full.mines),
                         (supplement.COMPLETE, {(0, 0), (1, 0)}, frozenset()))
        self.assertEqual((full.safe, full.mines), brute_certain(grid, 1))
        short = supplement.CertaintyEngine().analyze(grid, 1, node_budget=5)
        self.assertEqual((short.status, short.safe, short.mines, short.nodes, short.skipped),
                         (supplement.PARTIAL, frozenset(), frozenset(), 5, 1))

    def test_component_known_to_exceed_the_bound_is_not_searched_again_without_more_budget(self):
        # Two separate pairs, one mine in each: each pair takes six nodes and proves nothing.
        grid = ((H, 1, 0, 1, H), (H, 1, 0, 1, H))
        left, right = ((0, 0), (0, 1)), ((4, 0), (4, 1))
        engine, calls = supplement.CertaintyEngine(), []
        original = supplement.enumerate_component_bounded

        def counted(component, limit):
            calls.append((component.cells, limit))
            return original(component, limit)

        with patch.object(supplement, "enumerate_component_bounded", counted):
            for budget, searched, status, nodes in (
                    (3, [(left, 3)], supplement.PARTIAL, 3),      # left exceeds, nothing is left for right
                    (3, [(right, 3)], supplement.PARTIAL, 3),     # left is known too large for 3
                    (3, [], supplement.PARTIAL, 0),               # both known: no search at all
                    (6, [(left, 6)], supplement.PARTIAL, 6),      # a larger bound is a new question
                    (6, [(right, 6)], supplement.COMPLETE, 6)):   # left comes from the memo
                calls.clear()
                outcome = engine.analyze(grid, 2, node_budget=budget)
                self.assertEqual((calls, outcome.status, outcome.nodes), (searched, status, nodes))
                self.assertFalse(outcome.safe | outcome.mines)
        # Skipping a known-too-large component leaves the bound to the next one.
        grid = ((H, 1, 0, 2, H), (H, 1, 0, 2, H))
        engine = supplement.CertaintyEngine()
        first = engine.analyze(grid, 3, node_budget=5)
        again = engine.analyze(grid, 3, node_budget=5)
        self.assertEqual((first.status, first.mines), (supplement.PARTIAL, frozenset()))
        self.assertEqual((again.status, again.mines, again.safe), (supplement.PARTIAL, set(right), frozenset()))

    def test_carried_proofs_are_dropped_on_any_non_monotone_transition(self):
        states = [state.observation for state, _p in play(CASE_B, cap=8)]
        engine = supplement.CertaintyEngine()
        first = engine.analyze(states[0], 99, node_budget=UNBOUNDED)
        self.assertTrue(first.safe or first.mines)
        engine.analyze(states[3], 99, node_budget=UNBOUNDED)
        self.assertTrue(engine.known_safe | engine.known_mines)
        for name, grid, count in (
                ("an earlier state", states[0], 99),
                ("flag on an unproven cell", tuple(tuple(F if (x, y) == (29, 15) else v for x, v in enumerate(row))
                                                   for y, row in enumerate(states[3])), 99),
                ("another mine count", states[3], 98),
                ("another board", opened(CASE_A)[1], 10)):
            with self.subTest(transition=name):
                engine.analyze(states[3], 99, node_budget=UNBOUNDED)
                self.assertTrue(engine._sync(tuple(tuple(int(v) for v in row) for row in grid), count))
                self.assertFalse(engine.known_safe | engine.known_mines)
                outcome = engine.analyze(grid, count, node_budget=UNBOUNDED)
                self.assertEqual((outcome.safe, outcome.mines), frozen_certain(grid, count))

    def test_seeded_transition_fuzz_never_differs_from_frozen_certainty(self):
        """One engine kept across arbitrary jumps: forward, back, other boards, flags, mine count.

        Whatever it carried, a finished pass must equal the frozen exact certainty of the
        state it is given (or fail where that fails), and a bounded pass must stay inside it.
        The owner discards an engine after any failure; the test does the same.
        """
        rng = random.Random(20261116)
        boards = (CASE_A, CASE_B, random_board(12, 9, 9, 10), random_board(13, 9, 9, 10))
        pools = [[state.observation for state, _p in play(board, cap=45)] for board in boards]
        full, bounded = supplement.CertaintyEngine(), supplement.CertaintyEngine()
        pool = index = 0
        visits = consistent = contradictory = carried = partial = 0
        for _ in range(1200):
            move = rng.choice(("next",) * 5 + ("skip", "back", "other", "flag", "flag", "count"))
            if move == "other":
                pool = rng.randrange(len(pools))
                index = rng.randrange(len(pools[pool]))
            else:
                index += {"next": 1, "skip": rng.randint(2, 5), "back": -rng.randint(1, 3)}.get(move, 0)
                index = max(0, min(len(pools[pool]) - 1, index))
            grid, count = pools[pool][index], len(boards[pool][2])
            if move == "flag":   # one or two flags anywhere: on a proven mine, an unproven cell or a safe one
                hidden = [(x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v == H]
                chosen = set(rng.sample(hidden, min(len(hidden), rng.randint(1, 2))))
                grid = tuple(tuple(F if (x, y) in chosen else v for x, v in enumerate(row))
                             for y, row in enumerate(grid))
            elif move == "count":
                count += rng.choice((-1, 1))
            carried += bool(full.known_safe | full.known_mines)
            try:
                expected = frozen_certain(grid, count)
            except InconsistentObservationError:
                expected = None
            try:
                outcome = full.analyze(grid, count, node_budget=UNBOUNDED)
                got = (outcome.safe, outcome.mines)
                self.assertEqual(outcome.status, supplement.COMPLETE)
            except InconsistentObservationError:
                got, full = None, supplement.CertaintyEngine()
            self.assertEqual(got, expected, (move, pool, index, count))
            try:
                limited = bounded.analyze(grid, count, node_budget=150)
            except InconsistentObservationError:
                self.assertIsNone(expected)       # a bounded pass never invents a contradiction
                bounded = supplement.CertaintyEngine()
            else:
                partial += limited.status == supplement.PARTIAL
                if expected is not None:
                    self.assertLessEqual(limited.safe, expected[0])
                    self.assertLessEqual(limited.mines, expected[1])
            visits += 1
            consistent += expected is not None
            contradictory += expected is None
        self.assertEqual(visits, 1200)
        self.assertGreater(consistent, 600)
        self.assertGreater(contradictory, 50)
        self.assertGreater(carried, 600)
        self.assertGreater(partial, 100)

    def test_contradictions_raise_instead_of_stating_cells(self):
        engine = supplement.CertaintyEngine
        # Locally (1,0) is safe, but two mines cannot fit the one cell left.
        with self.assertRaises(InconsistentObservationError):
            engine().analyze(((0, H, H),), 2, node_budget=UNBOUNDED, facts=({(1, 0)}, ()))
        # A proof carried from an earlier state is contradicted by a clue opened later.
        carried = engine()
        before = carried.analyze(((H, 1, H, H, H),), 1, node_budget=UNBOUNDED, facts=({(0, 0)}, ()))
        self.assertEqual((before.status, before.safe, before.mines),
                         (supplement.COMPLETE, {(0, 0), (3, 0), (4, 0)}, {(2, 0)}))
        with self.assertRaises(InconsistentObservationError):
            carried.analyze(((H, 1, H, H, 1),), 1, node_budget=UNBOUNDED)
        # The same fact cannot be both.
        with self.assertRaises(InconsistentObservationError):
            engine().analyze(((H, 1, H),), 1, node_budget=UNBOUNDED, facts=({(0, 0)}, {(0, 0)}))
        # Bounded pass: the finished component alone already contradicts the mine count.
        left = ((H, 2), (H, 2))                       # both cells of column 0 are mines
        strip = ((1, H, 1, H, 1, H, 1, H, 1, H), (1, H, 1, H, 1, H, 1, H, 1, H))
        grid = tuple(a + b for a, b in zip(left, strip))
        bounded = engine().analyze(grid, 5, node_budget=6)
        self.assertEqual((bounded.status, bounded.mines, bounded.safe),
                         (supplement.PARTIAL, {(0, 0), (0, 1)}, frozenset()))
        with self.assertRaises(InconsistentObservationError):
            engine().analyze(grid, 1, node_budget=6)
        one = ((H, 1), (H, 1))                        # exactly one of two, the rest all mines
        grid = tuple(a + b for a, b in zip(one, strip))
        with self.assertRaises(InconsistentObservationError):
            engine().analyze(grid, 12, node_budget=6)

    def test_inputs_are_validated(self):
        for count, budget in ((True, 5), (1.0, 5), (1, 0), (1, True), (1, None)):
            with self.subTest(count=count, budget=budget), self.assertRaises(ValueError):
                supplement.CertaintyEngine().analyze(((H, 1, H),), count, node_budget=budget)


class OwnerTests(unittest.TestCase):
    def evidence(self, state):
        return plan_position(state.observation, state.num_mines, state.cursor, TABLE).evidence

    def test_state_follows_only_the_owner_input_sequence(self):
        states = [state for state, _p in play(CASE_B, cap=6)]
        owner = supplement.InfoSupplement()
        owner.supplement(states[0], self.evidence(states[0]))
        engine = owner._engine
        owner.supplement(states[1], self.evidence(states[1]))
        self.assertIs(owner._engine, engine)
        self.assertTrue(engine.known_safe | engine.known_mines)
        for name, state in (("same input again", states[1]), ("skipped input", states[3]),
                            ("other run", replace(states[2], run_id="f" * 32)),
                            ("other generation", replace(states[2], board_generation=2)),
                            ("revision gap", replace(states[2], input_revision=states[2].input_revision + 1))):
            with self.subTest(change=name):
                owner = supplement.InfoSupplement()
                owner.supplement(states[0], self.evidence(states[0]))
                owner.supplement(states[1], self.evidence(states[1]))
                engine = owner._engine
                outcome = owner.supplement(state, self.evidence(state))
                self.assertIsNot(owner._engine, engine)
                if outcome is not None:
                    self.assertLessEqual(outcome.safe, frozen_certain(state.observation, 99)[0])

    @staticmethod
    def record(board):
        return [(decision_of(p), p.info.route, p.info.supplement, p.info.safe, p.info.mines)
                for _state, p in play(board, supplement.InfoSupplement(), cap=40)]

    def test_interleaved_and_threaded_runs_do_not_share_state(self):
        frozen_exact = simple_decision.calculate_probabilities
        boards = (CASE_A, CASE_C, random_board(12, 9, 9, 10), random_board(13, 9, 9, 10))
        alone = [self.record(board) for board in boards]
        # Step the same games in turn, each with its own owner.
        games = [play(board, supplement.InfoSupplement(), cap=40) for board in boards]
        mixed, live = [[] for _ in boards], list(range(len(boards)))
        while live:
            for index in list(live):
                step = next(games[index], None)
                if step is None:
                    live.remove(index)
                else:
                    p = step[1]
                    mixed[index].append((decision_of(p), p.info.route, p.info.supplement, p.info.safe, p.info.mines))
        self.assertEqual(mixed, alone)
        # And in threads: no shared function is replaced, no state crosses runs.
        threaded = [None] * len(boards)

        def work(index):
            threaded[index] = self.record(boards[index])

        threads = [Thread(target=work, args=(index,)) for index in range(len(boards))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(threaded, alone)
        self.assertIs(simple_decision.calculate_probabilities, frozen_exact)
        self.assertEqual({name for name, value in vars(supplement).items()
                          if not name.startswith("__") and isinstance(value, (dict, list, set))}, set())

    def test_any_failure_discards_the_state_and_propagates(self):
        state = next(state for state, _p in play(CASE_C, cap=1))
        for error in (RuntimeError("boom"), InconsistentObservationError("none"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                owner = supplement.InfoSupplement()
                owner.supplement(state, self.evidence(state))
                self.assertIsNotNone(owner._engine)
                following = replace(state, input_seq=1, input_revision=state.input_revision + 1)
                with patch.object(supplement.CertaintyEngine, "analyze", side_effect=error), \
                        self.assertRaises(type(error)):
                    owner.supplement(following, self.evidence(following))
                self.assertEqual((owner._engine, owner._owner, owner._step), (None, None, None))

    def test_exact_route_searches_nothing_and_only_notes_the_frozen_proofs(self):
        owner = supplement.InfoSupplement()
        exact = [(state, proposal) for state, proposal in play(CASE_A, cap=6)
                 if any(c.mine_worlds is not None for c in proposal.overlays)]
        self.assertTrue(exact)
        state = exact[0][0]
        with patch.object(supplement, "enumerate_component_bounded", side_effect=AssertionError("no search")):
            self.assertIsNone(owner.supplement(state, self.evidence(state)))
        self.assertEqual((owner._engine.known_safe, owner._engine.known_mines),
                         frozen_certain(state.observation, state.num_mines))


class PlanTests(unittest.TestCase):
    def test_decision_overlays_and_frozen_calls_equal_the_plain_path(self):
        frozen_exact = simple_decision.calculate_probabilities
        planned = 0
        for board in BOARDS:
            owner = supplement.InfoSupplement()
            for state, proposal in play(board, owner, cap=70):
                with patch("stage3_planner.plan_position", wraps=plan_position) as plain_planner, \
                        patch("simple_decision.calculate_probabilities", wraps=frozen_exact) as plain_exact:
                    plain = policy.plan_snapshot(state, table=TABLE)
                with patch("stage3_planner.plan_position", wraps=plan_position) as planner, \
                        patch("simple_decision.calculate_probabilities", wraps=frozen_exact) as exact:
                    rich = policy.plan_snapshot(state, table=TABLE, info=supplement.InfoSupplement())
                    self.assertIs(simple_decision.calculate_probabilities, exact)   # never replaced
                self.assertIs(simple_decision.calculate_probabilities, frozen_exact)
                self.assertEqual(decision_of(rich), decision_of(plain))
                self.assertEqual(decision_of(proposal), decision_of(plain))
                self.assertIsNone(plain.info)
                self.assertEqual(planner.call_args_list, plain_planner.call_args_list)
                self.assertEqual(planner.call_count, 1)
                self.assertEqual(exact.call_count, plain_exact.call_count)
                self.assertEqual(exact.call_count, int(rich.info.route == "exact"))
                planned += 1
        self.assertGreater(planned, 150)

    def test_local_route_information_completes_the_frozen_exact_certainty(self):
        local = exact = added = 0
        for board in BOARDS:
            mines = set(board[2])
            for state, proposal in play(board, supplement.InfoSupplement(), cap=70):
                info, expected = proposal.info, frozen_certain(state.observation, state.num_mines)
                self.assertEqual((info.candidate_id, info.node_budget), ("S3X_INFO_A1", 20000))
                overlaid = {(c.x, c.y) for c in proposal.overlays}
                self.assertFalse(overlaid & (set(info.safe) | set(info.mines)))
                safe, mine = stated(proposal)
                self.assertFalse(safe & mines)
                self.assertLessEqual(mine, mines)
                if info.route == "exact":
                    self.assertEqual((info.supplement, info.safe, info.mines, info.nodes), ("NOT_RUN", (), (), 0))
                    exact += 1
                else:
                    self.assertEqual(info.supplement, "COMPLETE")
                    self.assertTrue(all(c.mine_worlds is None for c in proposal.overlays))
                    local += 1
                    added += len(info.safe) + len(info.mines)
                self.assertEqual((safe, mine), expected)
                self.assertLessEqual(proposal.compute_ns + info.supplement_ns, info.plan_ns)
        self.assertGreater(local, 80)
        self.assertGreater(exact, 20)
        self.assertGreater(added, 100)

    def first(self, board=CASE_A, owner=None):
        state = next(state for state, _p in play(board, cap=1))
        return state, policy.plan_snapshot(state, table=TABLE, info=owner or supplement.InfoSupplement())

    def test_information_grants_no_input(self):
        state, proposal = self.first()
        self.assertEqual((proposal.info.safe, proposal.info.mines),
                         (((2, 0), (5, 0)), ((8, 0), (8, 1), (8, 2))))
        for action, (x, y) in (("OPEN", proposal.info.safe[0]), ("FLAG", proposal.info.mines[0])):
            with self.subTest(action=action), self.assertRaises(policy.LivePolicyError):
                replace(proposal, action=action, x=x, y=y)
        after =tuple(tuple(1 if (x, y) == (2, 0) else v for x, v in enumerate(row))
                      for y, row in enumerate(state.observation))
        ack = policy.make_ack(proposal, "PLAYING", tuple(
            tuple(F if (x, y) == (proposal.x, proposal.y) else v for x, v in enumerate(row))
            for y, row in enumerate(state.observation)))
        for forged in (replace(ack, action="OPEN", x=2, y=0, observation=after), replace(ack, observation=after)):
            with self.subTest(ack=forged.action), self.assertRaises(policy.LivePolicyError):
                policy.validate_ack(proposal, forged)

    def test_supplement_failure_keeps_the_frozen_decision_and_is_recorded(self):
        state = next(state for state, _p in play(CASE_A, cap=1))
        plain = policy.plan_snapshot(state, table=TABLE)

        class Odd(Exception):
            pass
        Odd.__name__ = "not an identifier"

        class Failing:
            def __init__(self, error):
                self.error, self.discarded = error, 0

            def supplement(self, snapshot, evidence):
                raise self.error

            def discard(self):
                self.discarded += 1

        for error, status, name in ((RuntimeError("boom"), "FAILED", "RuntimeError"),
                                    (MemoryError(), "FAILED", "MemoryError"),
                                    (Odd(), "FAILED", "Exception"),
                                    (InconsistentObservationError("none"), "INCONSISTENT", "")):
            with self.subTest(error=type(error).__name__):
                source = Failing(error)
                proposal = policy.plan_snapshot(state, table=TABLE, info=source)
                self.assertEqual(decision_of(proposal), decision_of(plain))
                info = proposal.info
                self.assertEqual((info.route, info.supplement, info.error, info.safe, info.mines, info.nodes),
                                 ("local", status, name, (), (), 0))
                self.assertEqual(source.discarded, 1)
                wire = json.loads(json.dumps(policy.proposal_to_dict(proposal)))
                self.assertEqual(policy.proposal_from_dict(wire), proposal)
        exact_state = next(s for s, p in play(CASE_A, cap=6) if any(c.mine_worlds is not None for c in p.overlays))
        proposal = policy.plan_snapshot(exact_state, table=TABLE,
                                        info=Failing(InconsistentObservationError("none")))
        self.assertEqual((proposal.info.route, proposal.info.supplement, proposal.info.error),
                         ("exact", "FAILED", "InconsistentObservationError"))

    def test_real_engine_failure_discards_the_state_and_the_next_input_starts_fresh(self):
        states = [state for state, _p in play(CASE_A, cap=3)]
        owner = supplement.InfoSupplement()
        policy.plan_snapshot(states[0], table=TABLE, info=owner)
        with patch.object(supplement, "_split_components", side_effect=ZeroDivisionError("injected")):
            failed = policy.plan_snapshot(states[1], table=TABLE, info=owner)
        self.assertEqual((failed.info.supplement, failed.info.error), ("FAILED", "ZeroDivisionError"))
        self.assertEqual(decision_of(failed), decision_of(policy.plan_snapshot(states[1], table=TABLE)))
        self.assertIsNone(owner._engine)
        recovered = policy.plan_snapshot(states[2], table=TABLE, info=owner)
        self.assertEqual(recovered.info.supplement, "COMPLETE")
        self.assertEqual(stated(recovered), frozen_certain(states[2].observation, 10))

    def test_planner_errors_and_interrupts_are_not_absorbed(self):
        state = next(state for state, _p in play(CASE_A, cap=1))

        class Source:
            called = 0

            def supplement(self, snapshot, evidence):
                Source.called += 1
                raise KeyboardInterrupt()

            def discard(self):
                raise AssertionError("an interrupt is not a recorded failure")

        for error in (Stage3PlanningError("frozen"), InconsistentObservationError("frozen"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__), \
                    patch("stage3_planner.plan_position", side_effect=error), self.assertRaises(type(error)):
                policy.plan_snapshot(state, table=TABLE, info=Source())
        self.assertEqual(Source.called, 0)
        with self.assertRaises(KeyboardInterrupt):
            policy.plan_snapshot(state, table=TABLE, info=Source())
        self.assertEqual(Source.called, 1)

    def test_contradictory_public_state_states_nothing_and_keeps_the_local_decision(self):
        grid = ((0, H, H),)   # frozen local inference answers; no layout has two mines here
        state = policy.make_snapshot(run_id=RUN, board_generation=1, input_seq=1, width=3, height=1,
                                     num_mines=2, observation=grid, cursor=(0, 0))
        owner = supplement.InfoSupplement()
        proposal = policy.plan_snapshot(state, table=TABLE, info=owner)
        self.assertEqual(decision_of(proposal), decision_of(policy.plan_snapshot(state, table=TABLE)))
        self.assertEqual((proposal.info.supplement, proposal.info.safe, proposal.info.mines),
                         ("INCONSISTENT", (), ()))
        self.assertIsNone(owner._engine)
        wrong_flag = policy.make_snapshot(run_id=RUN, board_generation=1, input_seq=1, width=3, height=1,
                                          num_mines=1, observation=((F, 2, H),), cursor=(1, 0))
        for info in (None, supplement.InfoSupplement()):   # the frozen call itself may still answer
            proposal = policy.plan_snapshot(wrong_flag, table=TABLE, info=info)
            self.assertEqual((proposal.action, proposal.x, proposal.y), ("FLAG", 2, 0))
        self.assertEqual((proposal.info.supplement, proposal.info.safe, proposal.info.mines),
                         ("INCONSISTENT", (), ()))

    def test_preparation_and_initial_proposals_carry_no_information(self):
        class Refusing:
            def supplement(self, snapshot, evidence):
                raise AssertionError("no supplement before a planned decision")
            discard = supplement

        initial = policy.make_snapshot(run_id=RUN, board_generation=1, input_seq=0, width=9, height=9,
                                       num_mines=10, observation=((H,) * 9,) * 9, cursor=(0, 0))
        self.assertIsNone(policy.plan_snapshot(initial, table=TABLE, info=Refusing()).info)
        engine, observation = opened(CASE_A)
        hidden = [(x, y) for y, row in enumerate(observation) for x, v in enumerate(row) if v == H]
        mines = set(CASE_A[2])
        flags = (next(c for c in hidden if c in mines), next(c for c in reversed(hidden) if c not in mines))
        owner = supplement.InfoSupplement()
        phases, reviewing = [], True
        for state, proposal in play(CASE_A, owner, flags=flags):
            phases.append(proposal.phase)
            if proposal.is_flag_review:
                self.assertTrue(reviewing)
                self.assertIsNone(proposal.info)
                self.assertIsNone(owner._engine)
                self.assertNotIn("info", policy.proposal_to_dict(proposal))
            else:
                reviewing = False
                self.assertIsNotNone(proposal.info)
                safe, mine = stated(proposal)
                self.assertFalse(safe & mines)
                self.assertLessEqual(mine, mines)
                self.assertEqual((safe, mine), frozen_certain(state.observation, 10))
        self.assertEqual(phases[:2], [policy.PHASE_FLAG_REVIEW, policy.PHASE_FLAG_REVIEW])
        self.assertIn(policy.PHASE_V1, phases)

    def test_compute_ns_stays_the_frozen_decision_time(self):
        class Slow(supplement.InfoSupplement):
            def supplement(self, snapshot, evidence):
                sleep(.03)
                return super().supplement(snapshot, evidence)

        _state, proposal = self.first(CASE_C, Slow())
        info = proposal.info
        self.assertGreaterEqual(info.supplement_ns, 30_000_000)
        self.assertLess(proposal.compute_ns, 20_000_000)
        self.assertGreaterEqual(info.plan_ns, proposal.compute_ns + info.supplement_ns)


class WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        states = [state for state, _p in play(CASE_A, cap=3)]
        owner = supplement.InfoSupplement()
        cls.states = states
        cls.proposals = [policy.plan_snapshot(state, table=TABLE, info=owner) for state in states]
        cls.plain = policy.plan_snapshot(states[0], table=TABLE)
        cls.wire = json.loads(json.dumps(policy.proposal_to_dict(cls.proposals[0])))

    def test_exactly_two_wire_forms_roundtrip(self):
        legacy = {field.name for field in fields(policy.Proposal)} - {"info"}
        self.assertEqual(set(self.wire), legacy | {"info"})
        self.assertEqual(set(self.wire["info"]), {field.name for field in fields(policy.ProposalInfo)})
        self.assertEqual(policy.proposal_from_dict(self.wire), self.proposals[0])
        plain_wire = json.loads(json.dumps(policy.proposal_to_dict(self.plain)))
        self.assertEqual(set(plain_wire), legacy)
        self.assertEqual(policy.proposal_from_dict(plain_wire), self.plain)
        # The plain form of the same proposal is the same decision without information.
        without = dict(self.wire)
        del without["info"]
        parsed = policy.proposal_from_dict(without)
        self.assertIsNone(parsed.info)
        self.assertEqual(parsed, replace(self.proposals[0], info=None))
        self.assertEqual(decision_of(parsed), decision_of(self.plain))

    def test_unknown_missing_or_null_fields_are_rejected(self):
        for name, value in (("extra", {**self.wire, "extra": 1}), ("null info", {**self.wire, "info": None}),
                            ("list info", {**self.wire, "info": []}),
                            ("info key", {**self.wire, "info": {**self.wire["info"], "probability": 0}}),
                            ("renamed", {**{k: v for k, v in self.wire.items() if k != "info"},
                                         "information": self.wire["info"]})):
            with self.subTest(case=name), self.assertRaises(policy.LivePolicyError):
                policy.proposal_from_dict(value)
        for name in self.wire["info"]:
            info = dict(self.wire["info"])
            del info[name]
            with self.subTest(missing=name), self.assertRaises(policy.LivePolicyError):
                policy.proposal_from_dict({**self.wire, "info": info})

    def test_information_values_are_strict(self):
        info = self.wire["info"]
        self.assertEqual((info["route"], info["supplement"], info["safe"], info["mines"]),
                         ("local", "COMPLETE", [[2, 0], [5, 0]], [[8, 0], [8, 1], [8, 2]]))
        bad = {
            "candidate_id": ("S3X_INC_INFO", "", 1, None),
            "token": ("f" * 32, "x", 1),
            "state_sha256": ("0" * 64, info["state_sha256"].upper(), info["state_sha256"][:-1], 1),
            "route": ("exact", "other", 1),
            "supplement": ("NOT_RUN", "PARTIAL", "INCONSISTENT", "FAILED", "DONE", 1),
            "error": ("RuntimeError", 1, None),
            "node_budget": (20001, 40000, True, 20000.0, "20000"),
            "nodes": (-1, 20001, True, 1.5),
            "skipped": (1, -1, True),
            "supplement_ns": (-1, True, 1.0, info["plan_ns"] + 1),
            "plan_ns": (0, True, info["supplement_ns"], self.proposals[0].compute_ns + info["supplement_ns"] - 1),
            "safe": ([[5, 0], [2, 0]], [[2, 0], [2, 0]], [[2, 0], [0, 4]], [[2, 0], [7, 1]], [[2, 0], [30, 0]],
                     [[2]], ["2,0"], [[2, "0"]], [[True, 0]], [[2, 0], [8, 0]], "2,0", None),
            "mines": ([[8, 0], [8, 1], [2, 0]], [[8, 2], [8, 1]], [[8, 0, 0]], [[8.0, 0]], {}),
        }
        self.assertEqual(set(bad), set(info))
        for name, values in bad.items():
            for value in values:
                with self.subTest(field=name, value=value), self.assertRaises(policy.LivePolicyError):
                    policy.proposal_from_dict({**self.wire, "info": {**info, name: value}})
        failed = {**info, "supplement": "FAILED", "error": "RuntimeError", "nodes": 0, "safe": [], "mines": []}
        self.assertEqual(policy.proposal_from_dict({**self.wire, "info": failed}).info.error, "RuntimeError")
        for name, value in (("error", ""), ("error", "not an identifier"), ("error", "E" * 65),
                            ("nodes", 1), ("safe", [[2, 0]]), ("mines", [[8, 0]])):
            with self.subTest(failed=name, value=value), self.assertRaises(policy.LivePolicyError):
                policy.proposal_from_dict({**self.wire, "info": {**failed, name: value}})
        partial = {**info, "supplement": "PARTIAL", "skipped": 1}
        self.assertEqual(policy.proposal_from_dict({**self.wire, "info": partial}).info.skipped, 1)
        with self.assertRaises(policy.LivePolicyError):
            policy.proposal_from_dict({**self.wire, "info": {**partial, "skipped": 0}})

    def test_information_cannot_move_to_another_proposal_state_or_run(self):
        first, second, third = self.proposals
        self.assertEqual({p.info.route for p in self.proposals}, {"local"})
        with self.assertRaises(policy.LivePolicyError):
            replace(second, info=first.info)                                   # another proposal
        with self.assertRaises(policy.LivePolicyError):
            replace(second, info=replace(first.info, token=second.token))      # another public state
        for name, change in (("generation", dict(board_generation=2)), ("run", dict(run_id="f" * 32)),
                             ("input", dict(input_seq=1, input_revision=self.states[0].input_revision + 1)),
                             ("revision", dict(input_revision=self.states[0].input_revision + 1))):
            other = policy.plan_snapshot(replace(self.states[0], **change), table=TABLE)
            self.assertEqual(other.snapshot.observation, first.snapshot.observation)
            with self.subTest(same_grid_other=name), self.assertRaises(policy.LivePolicyError):
                replace(other, info=replace(first.info, token=other.token))
        # A stale proposal is refused as before, with or without information.
        with self.assertRaises(policy.LivePolicyError):
            policy.admit_proposal(first, self.states[1])
        # Only a planned V1 decision carries a record.
        review = next(p for _s, p in play(CASE_A, flags=((0, 0),)))
        self.assertTrue(review.is_flag_review)
        with self.assertRaises(policy.LivePolicyError):
            replace(review, info=replace(first.info, token=review.token))
        for value in ({}, "info", first):
            with self.subTest(type=type(value).__name__), self.assertRaises(policy.LivePolicyError):
                replace(first, info=value)

    def test_exact_route_information_must_match_the_overlays(self):
        exact = next(p for _s, p in play(CASE_A, supplement.InfoSupplement(), cap=6) if p.info.route == "exact")
        local = self.proposals[0]
        as_local = replace(exact.info, route="local", supplement="COMPLETE")
        as_exact = replace(local.info, route="exact", supplement="NOT_RUN", nodes=0, safe=(), mines=())
        for proposal, info in ((exact, as_local), (local, as_exact)):
            with self.subTest(route=info.route), self.assertRaises(policy.LivePolicyError):
                replace(proposal, info=info)
        with self.assertRaises(policy.LivePolicyError):
            replace(exact.info, safe=((0, 0),))            # NOT_RUN lists nothing
        wire = json.loads(json.dumps(policy.proposal_to_dict(exact)))
        self.assertEqual(policy.proposal_from_dict(wire), exact)

    def test_real_file_channel_roundtrip_keeps_the_record(self):
        with tempfile.TemporaryDirectory() as folder:
            proposal = self.proposals[0]
            transport.write_once(folder, "worker", 0, transport.message(RUN, 0, "PROPOSAL",
                                                                        policy.proposal_to_dict(proposal)))
            received = transport.read_next(folder, "worker", 0, RUN)
        self.assertEqual(policy.proposal_from_dict(received["payload"]), proposal)
        self.assertEqual(received["payload"]["info"]["candidate_id"], policy.INFO_ID)


def serve(board, *, flags=(), forge=None, stop_after=None):
    """Run live_policy_worker.serve over one game with a synthetic in-process parent."""
    engine, observation = opened(board, flags)
    start = adopt(board, observation, flags=len(flags))
    sent, kinds = [], []
    memory = {"state": start, "pending": None, "ack": None}

    def read(_directory, direction, seq, run_id):
        assert (direction, run_id) == ("parent", RUN)
        if seq == 0:
            kinds.append("START")
            return transport.message(RUN, seq, "START", policy.snapshot_to_dict(start))
        if stop_after is not None and len(sent) >= stop_after:
            raise RuntimeError("test stop")
        last = sent[-1]
        if last["kind"] == "PROPOSAL":
            proposal = policy.proposal_from_dict(last["payload"])
            policy.admit_proposal(proposal, memory["state"])
            if forge is not None:
                kinds.append("ACK")
                return transport.message(RUN, seq, "ACK", policy.ack_to_dict(forge(proposal)))
            after, *_ = engine.step(proposal.x, proposal.y, Action[proposal.action])
            ack = policy.make_ack(proposal, engine.status,
                                  after if engine.status == GameStatus.PLAYING else None)
            memory["pending"], memory["ack"] = proposal, ack
            kinds.append("ACK")
            return transport.message(RUN, seq, "ACK", policy.ack_to_dict(ack))
        memory["state"] = policy.validate_ack(memory["pending"], memory["ack"])
        kinds.append("NEXT")
        return transport.message(RUN, seq, "NEXT", policy.snapshot_to_dict(memory["state"]))

    def write(_directory, _direction, _seq, envelope):
        kinds.append(envelope["kind"])
        sent.append(envelope)

    with patch.object(worker, "read_next", side_effect=read), \
            patch.object(worker, "write_once", side_effect=write), \
            patch("stage3_planner.plan_position", wraps=plan_position) as planner:
        code = worker.serve("synthetic", RUN)
    proposals = [policy.proposal_from_dict(item["payload"]) for item in sent if item["kind"] == "PROPOSAL"]
    return code, kinds, proposals, sent, planner.call_count, engine.status


class WorkerTests(unittest.TestCase):
    def test_worker_keeps_inputs_order_and_messages_of_a_worker_without_supplement(self):
        for board, flags in ((CASE_C, ()), (CASE_A, ()), (CASE_A, ((0, 0), (2, 0))), (random_board(12, 9, 9, 10), ())):
            with self.subTest(first=board[3], flags=flags):
                code, kinds, rich, _sent, calls, status = serve(board, flags=flags)
                with patch.object(worker, "InfoSupplement", lambda: None):
                    plain_code, plain_kinds, plain, _s, plain_calls, plain_status = serve(board, flags=flags)
                self.assertEqual((code, kinds, calls, status), (plain_code, plain_kinds, plain_calls, plain_status))
                self.assertEqual(code, 0)
                self.assertEqual([decision_of(p) for p in rich], [decision_of(p) for p in plain])
                self.assertTrue(all(p.info is None for p in plain))
                for proposal in rich:
                    planned = proposal.kind in ("certain", "guess")
                    self.assertEqual(proposal.info is not None, planned)
                self.assertEqual(calls, sum(p.info is not None for p in rich))

    def test_one_supplement_per_v1_run_and_none_for_k(self):
        made = []

        def factory():
            made.append(supplement.InfoSupplement())
            return made[-1]

        with patch.object(worker, "InfoSupplement", factory):
            code, _kinds, proposals, _sent, _calls, _status = serve(CASE_A)
        self.assertEqual((code, len(made)), (0, 1))
        self.assertGreater(len(proposals), 5)
        # KLC1_INFO_D1 changes the K-LC1 display contract only: its decision proposal
        # now carries the K-specific info. The V1 supplement and V1 planner stay
        # unused for every K policy, and K-P0 / K-LC0 still send no info at all.
        for policy_id in (k_live.POLICY_K, k_live.POLICY_K_LC0, k_live.POLICY_K_LC1):
            with self.subTest(policy=policy_id):
                start = singleton_start(policy_id)
                sent = []
                requests = [transport.message(start.run_id, 0, "START", k_live.to_dict(start)), RuntimeError("stop")]
                with patch.object(worker, "read_next", side_effect=requests), \
                        patch.object(worker, "write_once", side_effect=lambda _d, _s, _q, item: sent.append(item)), \
                        patch.object(worker, "InfoSupplement", side_effect=AssertionError("K has no supplement")), \
                        patch.object(worker, "plan_snapshot", side_effect=AssertionError("K has no V1 plan")):
                    self.assertEqual(worker.serve("synthetic", start.run_id), 1)
                self.assertEqual([item["kind"] for item in sent], ["PROPOSAL", "ERROR"])
                if policy_id == k_live.POLICY_K_LC1:
                    self.assertEqual(sent[0]["payload"]["info"]["candidate_id"], "KLC1_INFO_D1")
                    self.assertNotIn("supplement", sent[0]["payload"]["info"])   # not the V1 info record
                else:
                    self.assertNotIn("info", sent[0]["payload"])
                self.assertIn("stop", sent[1]["payload"]["detail"])

    def test_ack_for_an_information_cell_is_rejected(self):
        def forge(proposal):
            x, y = proposal.info.safe[0]
            after = tuple(tuple(1 if (cx, cy) == (x, y) else v for cx, v in enumerate(row))
                          for cy, row in enumerate(proposal.snapshot.observation))
            real = policy.make_ack(proposal, "PLAYING", tuple(
                tuple(F if (cx, cy) == (proposal.x, proposal.y) else v for cx, v in enumerate(row))
                for cy, row in enumerate(proposal.snapshot.observation)))
            return replace(real, action="OPEN", x=x, y=y, observation=after)

        code, kinds, proposals, sent, _calls, _status = serve(CASE_A, forge=forge)
        self.assertEqual((code, kinds), (1, ["START", "PROPOSAL", "ACK", "ERROR"]))
        self.assertTrue(proposals[0].info.safe)
        self.assertIn("ACK does not match pending action/token", sent[-1]["payload"]["detail"])

    def test_failing_supplement_inside_the_worker_keeps_the_whole_sequence(self):
        code, kinds, plain, _sent, _calls, status = serve(CASE_A)
        with patch.object(supplement.CertaintyEngine, "analyze", side_effect=RuntimeError("injected")):
            failed_code, failed_kinds, failed, _s, _c, failed_status = serve(CASE_A)
        self.assertEqual((failed_code, failed_kinds, failed_status), (code, kinds, status))
        self.assertEqual([decision_of(p) for p in failed], [decision_of(p) for p in plain])
        local = [p.info for p in failed if p.info.route == "local"]
        self.assertTrue(local)
        self.assertTrue(all((i.supplement, i.error, i.safe, i.mines) == ("FAILED", "RuntimeError", (), ())
                            for i in local))


class PresentationTests(unittest.TestCase):
    def test_information_cells_are_colors_without_probability_or_recommendation(self):
        for board in (CASE_A, CASE_C):
            for state, proposal in play(board, supplement.InfoSupplement(), cap=12):
                rich, plain = present_v1_proposal(proposal), present_v1_proposal(replace(proposal, info=None))
                self.assertEqual((rich.move, rich.status_text, rich.decision),
                                 (plain.move, plain.status_text, plain.decision))
                extra = set(rich.overlays) - set(plain.overlays)
                self.assertEqual(extra, set(proposal.info.safe) | set(proposal.info.mines))
                self.assertEqual({c: o for c, o in rich.overlays.items() if c not in extra}, plain.overlays)
                for cell in extra:
                    kind = OverlayKind.SAFE if cell in proposal.info.safe else OverlayKind.MINE
                    self.assertEqual(rich.overlays[cell], CellOverlay(kind))
                self.assertEqual([c for c, o in rich.overlays.items() if o.recommended],
                                 [(proposal.x, proposal.y)])


class InfoJob(SyntheticLivePolicyJob):
    """UI seam: proposals planned as the worker plans them, with or without the supplement."""
    with_supplement = True

    def start(self, snapshot):
        self.info = supplement.InfoSupplement() if self.with_supplement else None
        return super().start(snapshot)

    def compute(self):
        self.deliver(policy.plan_snapshot(self.requests[-1], table=TABLE, info=self.info))


class DisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make(self, with_supplement):
        isolate_ui_settings(self)
        job = type("Job", (InfoJob,), {"with_supplement": with_supplement})
        for target, value in (('ui_manager.LivePolicyJob', job),
                              ('ui_manager.MinesweeperUI._ensure_zini_metric_job', None),
                              ('ui_manager.QMessageBox.information', None),
                              ('ui_manager.QMessageBox.warning', None)):
            p = patch(target, value) if target.endswith('LivePolicyJob') else patch(target, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.ui = MinesweeperUI(MinesweeperEngine(9, 9, 10))
        self.addCleanup(self.close_ui)
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy.POLICY_V1))
        self.ui.on_reset()
        self.job = self.ui._v1_job
        with patch('core_engine.random.sample', return_value=list(CASE_C[2])):
            self.ui.show()
            self.app.processEvents()
            self.ui.on_left_click(*CASE_C[3])            # one manual OPEN, then the current game is adopted
        self.ui.simple_auto_interval_spin.setValue(2000)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.job.compute()
        return self.ui._v1_pending

    def close_ui(self):
        self.ui._stop_timer()
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def colors(self):
        return {c: b.analysis_overlay.kind for c, b in self.ui._buttons.items()
                if b.analysis_overlay and b.analysis_overlay.kind in (OverlayKind.SAFE, OverlayKind.MINE)}

    def test_information_reaches_real_cells_and_only_the_proposed_input_is_applied(self):
        pending = self.make(True)
        self.assertEqual((pending.action, pending.x, pending.y), ("FLAG", 1, 0))
        self.assertEqual((pending.info.safe, pending.info.mines), (((0, 0),), ()))
        self.assertNotIn((0, 0), {(c.x, c.y) for c in pending.overlays})
        shown = self.colors()
        self.assertEqual(shown[(0, 0)], OverlayKind.SAFE)
        button = self.ui._buttons[(0, 0)]
        self.assertEqual(button.analysis_overlay, CellOverlay(OverlayKind.SAFE))
        self.assertEqual(button.probability_text, '')
        self.assertEqual({c for c, b in self.ui._buttons.items()
                          if b.analysis_overlay and b.analysis_overlay.recommended}, {(1, 0)})
        self.assertEqual(self.ui.analysis_status_label.text(), "Stage3 V1 | 확정 수: FLAG (1, 0)")
        advance_auto_timer(self.ui)
        # The one applied input is the frozen proposal's; the green cell was not opened.
        self.assertEqual(self.job.applied, [pending.token])
        record = self.ui.live_action_records[-1]
        self.assertEqual((record["action"], record["x"], record["y"]), ("FLAG", 1, 0))
        self.assertEqual(self.ui.engine.get_observation()[0][0], H)
        self.assertEqual(self.ui.live_auto_totals['auto_inputs'], 1)
        self.assertIsNone(self.ui._analysis_result)
        self.assertEqual(self.colors()[(0, 0)], OverlayKind.SAFE)           # kept while the next result is computed
        self.job.deliver_ack()
        self.job.compute()
        following = self.ui._v1_pending
        self.assertEqual((following.action, following.x, following.y), ("OPEN", 0, 0))
        self.assertIn((0, 0), {(c.x, c.y) for c in following.overlays})
        advance_auto_timer(self.ui)
        self.assertEqual(self.ui.engine.status, GameStatus.WON)

    def test_plain_proposal_shows_the_cell_one_input_later(self):
        pending = self.make(False)
        self.assertEqual((pending.action, pending.x, pending.y, pending.info), ("FLAG", 1, 0, None))
        self.assertNotIn((0, 0), self.colors())
        advance_auto_timer(self.ui)
        self.job.deliver_ack()
        self.job.compute()
        self.assertEqual(self.colors()[(0, 0)], OverlayKind.SAFE)

    def test_late_proposal_of_a_disposed_owner_colors_nothing(self):
        pending = self.make(True)
        stale = policy.plan_snapshot(pending.snapshot, table=TABLE, info=supplement.InfoSupplement())
        self.assertEqual(stale.info.safe, ((0, 0),))
        self.ui._invalidate_v1_run('info test disposal')
        self.job.proposal_ready.emit(stale)
        self.assertIsNone(self.ui._v1_pending)
        self.assertNotIn((0, 0), self.colors())
        self.assertEqual(self.job.applied, [])

    def test_information_colors_follow_the_existing_invalidations(self):
        for name, action in (("manual flag", lambda: self.ui.on_right_click(0, 0)),
                             ("owner disposal", lambda: self.ui._invalidate_v1_run('info test disposal')),
                             ("analysis off", lambda: self.ui.analysis_checkbox.setChecked(False)),
                             ("reset", lambda: self.ui.on_reset())):
            with self.subTest(boundary=name):
                self.make(True)
                self.assertEqual(self.colors()[(0, 0)], OverlayKind.SAFE)
                action()
                self.assertIsNone(self.ui._certainty_frame)
                self.assertNotIn((0, 0), self.colors())
                self.doCleanups()


if __name__ == "__main__":
    unittest.main()
