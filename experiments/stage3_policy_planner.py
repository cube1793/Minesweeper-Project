"""EXPERIMENTAL E/L pilot planner; NOT a production Stage-3 solver.

Inputs are public observation, public mine count, cursor and frozen table only.
No engine, board identity, retained facts, virtual probability, or action queue.
"""

from dataclasses import dataclass
from functools import cmp_to_key
import hashlib
import json
from pathlib import Path

from core_engine import Action
from simple_algorithm import SimpleMove
from simple_decision import DecisionKind, analyze_position


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "calibration/stage3_physical_profile_v1.json"
PROFILE_SHA256 = "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b"
TABLE_SHA256 = "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b"
POLICIES = ("E-FIRST", "L-FIRST")


class PilotInvalid(RuntimeError):
    """Fail closed: no authoritative policy comparison may be published."""


def require(condition, message):
    if not condition:
        raise PilotInvalid(message)


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def load_table(path=PROFILE_PATH):
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == PROFILE_SHA256, "profile SHA-256 mismatch")
    profile = json.loads(raw)
    require(canonical_bytes(profile) == raw, "noncanonical physical profile")
    require(profile["model_id"] == "overlap_floor_log2_distance_v1" and
            profile["table_order"] == "dx_major_dy_minor" and
            profile["timing_tick_unit"] == "1_us" and
            profile["table_dimensions"] == [30, 16], "physical table contract mismatch")
    table = profile["timing_table_us"]
    require(len(table) == 30 and all(len(row) == 16 for row in table), "table shape")
    require(all(type(t) is int and t > 0 for row in table for t in row), "table ticks")
    encoded = ",".join(str(t) for row in table for t in row).encode("ascii")
    require(profile["table_sha256"] == TABLE_SHA256 and
            hashlib.sha256(encoded).hexdigest() == TABLE_SHA256, "table SHA-256 mismatch")
    # Fitted Model C parameters are deliberately never read or recomputed.
    return tuple(tuple(row) for row in table)


def reading(cell):
    return cell[1], cell[0]


def cost(table, start, end):
    return table[abs(start[0] - end[0])][abs(start[1] - end[1])]


def target(move):
    return move.x, move.y


@dataclass(frozen=True)
class Plan:
    actions: tuple[SimpleMove, ...]
    latency_us: int
    reveals: int

    @property
    def fallback(self):
        # Terminal (y,x,semantic action), then setup coordinate sequence.
        # No action-count preference. Route ties use the same reading order.
        terminal = self.actions[-1]
        return (terminal.y, terminal.x, int(terminal.action),
                tuple((m.y, m.x) for m in self.actions[:-1]))


def exact_route(table, cursor, flags, terminal):
    """Held-Karp over the local required set, including the terminal input cost.

    Equal-cost paths choose lexicographic (y,x) setup order. No greedy routing,
    Euclidean objective, time budget, or candidate cap is used.
    """
    cells = tuple(sorted(flags, key=reading))
    if not cells:
        return (terminal,), cost(table, cursor, target(terminal))
    n = len(cells)
    dp = {(1 << i, i): (cost(table, cursor, cell), (i,))
          for i, cell in enumerate(cells)}
    for mask in range(1, 1 << n):
        for last in range(n):
            if (mask, last) not in dp:
                continue
            length, route = dp[mask, last]
            for nxt in range(n):
                if mask & (1 << nxt):
                    continue
                key = (mask | (1 << nxt), nxt)
                candidate = (length + cost(table, cells[last], cells[nxt]), route + (nxt,))
                if key not in dp or candidate < dp[key]:
                    dp[key] = candidate
    length, route = min(
        (dp[(1 << n) - 1, last][0] + cost(table, cells[last], target(terminal)),
         dp[(1 << n) - 1, last][1]) for last in range(n)
    )
    return tuple(SimpleMove(Action.FLAG, *cells[i]) for i in route) + (terminal,), length


def certainty_pool(decision):
    if decision.kind == DecisionKind.LOCAL_DETERMINISTIC:
        require(decision.probability_result is None, "probability used on local path")
        facts = decision.deterministic_result
        return facts.safe_cells, facts.mine_cells
    probabilities = decision.probability_result
    require(probabilities is not None, "missing exact probabilities")
    return (frozenset(c.coordinate for c in probabilities.probabilities if c.mine_worlds == 0),
            frozenset(c.coordinate for c in probabilities.probabilities
                      if c.mine_worlds == c.total_worlds))


def generate_candidates(observation, decision, cursor, table):
    safe, mines = certainty_pool(decision)
    plans = {}

    def add(flags, terminal, reveals):
        actions, latency = exact_route(table, cursor, flags, terminal)
        plans[actions] = Plan(actions, latency, reveals)

    for cell in sorted(safe, key=reading):
        add((), SimpleMove(Action.OPEN, *cell), 1)
    for clue in decision.constraints:
        setup = clue.hidden_cells & mines
        remaining = clue.hidden_cells - setup
        # Flagging this entire local current-certain set makes N-F exactly zero.
        # A proper subset cannot unlock this clue. No new virtual mines needed.
        if len(setup) != clue.remaining_mines or not remaining:
            continue
        x, y = clue.source
        if observation[y][x] > 0:  # Engine CHORD on zero is explicitly a no-op.
            add(setup, SimpleMove(Action.CHORD, x, y), len(remaining))
        for cell in sorted(remaining, key=reading):
            add(setup, SimpleMove(Action.OPEN, *cell), 1)
    return tuple(sorted(plans.values(), key=lambda p: p.fallback))


def remove_dominated(plans):
    best_by_r = {}
    for p in plans:
        best_by_r[p.reveals] = min(best_by_r.get(p.reveals, p.latency_us), p.latency_us)
    return tuple(p for p in plans if not any(
        r >= p.reveals and length <= p.latency_us and
        (r > p.reveals or length < p.latency_us) for r, length in best_by_r.items()))


def compare_e(a, b):
    left, right = a.latency_us * b.reveals, b.latency_us * a.reveals
    return (left > right) - (left < right)


def select_plan(plans, policy):
    require(policy in POLICIES and bool(plans), "invalid policy or empty selection")
    candidates = plans
    if policy == "L-FIRST":
        best_l = min(p.latency_us for p in candidates)
        candidates = tuple(p for p in candidates if p.latency_us == best_l)
    best_e = min(candidates, key=cmp_to_key(compare_e))
    candidates = tuple(p for p in candidates if compare_e(p, best_e) == 0)
    e_tie = len(candidates) > 1
    best_l = min(p.latency_us for p in candidates)
    candidates = tuple(p for p in candidates if p.latency_us == best_l)
    return min(candidates, key=lambda p: p.fallback), {
        "exact_e_tie": e_tie, "final_fallback": len(candidates) > 1,
        "final_fallback_candidates": len(candidates),
    }


@dataclass(frozen=True)
class PlanningDecision:
    evidence: object
    move: SimpleMove
    reason: str
    candidates: tuple[Plan, ...]
    survivors: tuple[Plan, ...]
    choices: dict
    selection_diagnostics: dict


def plan_position(observation, num_mines, cursor, table, policy):
    require(policy in POLICIES, "unknown policy")
    evidence = analyze_position(observation, num_mines)
    require(evidence is not None, "no move while PLAYING")
    if evidence.kind == DecisionKind.PROBABILITY_GUESS:
        # Preserve the frozen selector, including its (y,x) min-risk tie.
        return PlanningDecision(evidence, evidence.move, "guess", (), (), {}, {})
    candidates = generate_candidates(observation, evidence, cursor, table)
    survivors = remove_dominated(candidates)
    if survivors:
        selections = {name: select_plan(survivors, name) for name in POLICIES}
        choices = {name: result[0] for name, result in selections.items()}
        diagnostics = {name: result[1] for name, result in selections.items()}
        return PlanningDecision(evidence, choices[policy].actions[0], "reveal_plan",
                                candidates, survivors, choices, diagnostics)
    _, mines = certainty_pool(evidence)
    require(bool(mines), "certainty without a reveal plan or certain FLAG")
    nearest = min(mines, key=lambda c: (cost(table, cursor, c), *reading(c)))
    tie_count = sum(cost(table, cursor, c) == cost(table, cursor, nearest) for c in mines)
    return PlanningDecision(evidence, SimpleMove(Action.FLAG, *nearest), "flag_fallback",
                            candidates, survivors, {}, {"flag_fallback_ties": tie_count})
