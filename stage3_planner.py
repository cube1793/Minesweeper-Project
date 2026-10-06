"""Frozen Stage-3 V1 E-FIRST planning from current public information only.

The Stage-2 analyzer owns the inference boundary. Plans end at the first
reveal; only ``decision.move`` is executable before a fresh observation.
No inference facts or action suffix are retained between calls.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from functools import cmp_to_key
from itertools import groupby

from core_engine import Action
from simple_algorithm import Coordinate, Observation, SimpleMove
from simple_decision import DecisionKind, SimpleDecision, analyze_position
from stage3_physical import TimingTable, action_cost, validate_timing_table


class Stage3PlanningError(RuntimeError):
    """The current public evidence cannot supply an admissible action."""


def _reading_order(cell: Coordinate) -> tuple[int, int]:
    return cell[1], cell[0]


@dataclass(frozen=True)
class RevealPlan:
    """Current-certain FLAG setup followed by one guaranteed safe reveal."""

    actions: tuple[SimpleMove, ...]
    latency_us: int
    reveals: int

    def __post_init__(self):
        object.__setattr__(self, "actions", tuple(self.actions))
        if not self.actions:
            raise ValueError("A reveal plan must contain an action.")
        if type(self.latency_us) is not int or self.latency_us <= 0:
            raise ValueError("Plan latency must be a positive integer.")
        if type(self.reveals) is not int or self.reveals <= 0:
            raise ValueError("Guaranteed reveals must be a positive integer.")


@dataclass(frozen=True)
class Stage3Decision:
    """One physical move with its current inference and optional scored plan.

    ``plan`` explains selection, not permission to execute its suffix. Guess
    and FLAG-only fallback decisions have no guaranteed reveal plan.
    """

    evidence: SimpleDecision
    move: SimpleMove
    plan: RevealPlan | None


def certainty_pool(
    evidence: SimpleDecision,
) -> tuple[frozenset[Coordinate], frozenset[Coordinate]]:
    """Use only facts from the inference layer Stage 2 actually reached."""
    if evidence.kind == DecisionKind.LOCAL_DETERMINISTIC:
        if evidence.probability_result is not None:
            raise Stage3PlanningError("LOCAL evidence must not include probability.")
        facts = evidence.deterministic_result
        return facts.safe_cells, facts.mine_cells

    result = evidence.probability_result
    if result is None:
        raise Stage3PlanningError("Probability-path evidence is missing.")
    safe = frozenset(
        cell.coordinate for cell in result.probabilities if cell.mine_worlds == 0
    )
    mines = frozenset(
        cell.coordinate for cell in result.probabilities
        if cell.mine_worlds == cell.total_worlds
    )
    return safe, mines


def exact_route(
    table: TimingTable, cursor: Coordinate, flags: Iterable[Coordinate],
    terminal: SimpleMove,
) -> tuple[tuple[SimpleMove, ...], int]:
    """Held-Karp route through the required local FLAG set, then terminal.

    State values include the reading-order index sequence so equal-cost
    prefixes, and ultimately complete routes, have exact lexicographic ties.
    The terminal movement AND input cost is included in the returned latency.
    """
    cells = tuple(sorted(set(flags), key=_reading_order))
    if len(cells) > 7:
        raise ValueError("A first-reveal clue setup can contain at most 7 FLAGs.")
    destination = (terminal.x, terminal.y)
    if not cells:
        return (terminal,), action_cost(table, cursor, destination)

    # Indexed by visited subset and its last FLAG. Every transition adds one
    # positive-cost physical input; the final reveal is added below.
    paths: dict[tuple[int, int], tuple[int, tuple[int, ...]]] = {}
    for index, cell in enumerate(cells):
        paths[1 << index, index] = (action_cost(table, cursor, cell), (index,))
    full = (1 << len(cells)) - 1
    for visited in range(1, full + 1):
        for last in range(len(cells)):
            if not visited & (1 << last):
                continue
            previous = visited ^ (1 << last)
            if previous == 0:
                continue
            paths[visited, last] = min(
                (
                    paths[previous, prior][0]
                    + action_cost(table, cells[prior], cells[last]),
                    paths[previous, prior][1] + (last,),
                )
                for prior in range(len(cells)) if previous & (1 << prior)
            )
    latency, order = min(
        (
            paths[full, last][0] + action_cost(table, cell, destination),
            paths[full, last][1],
        )
        for last, cell in enumerate(cells)
    )
    actions = tuple(SimpleMove(Action.FLAG, *cells[index]) for index in order)
    return actions + (terminal,), latency


def _final_tie_key(plan: RevealPlan) -> tuple:
    terminal = plan.actions[-1]
    rank = {Action.OPEN: 0, Action.FLAG: 1, Action.CHORD: 2}
    return (
        terminal.y, terminal.x, rank[terminal.action],
        tuple((move.y, move.x) for move in plan.actions[:-1]),
    )


def generate_reveal_plans(
    observation: Observation, evidence: SimpleDecision, cursor: Coordinate,
    table: TimingTable,
) -> tuple[RevealPlan, ...]:
    """Enumerate exactly the direct and whole-clue-setup plans in spec §12.

    Empty setup also covers direct satisfied positive CHORDs. No hypothetical
    observation is analyzed, and no newly inferred virtual mine is added.
    """
    safe, mines = certainty_pool(evidence)
    by_actions: dict[tuple[SimpleMove, ...], RevealPlan] = {}

    def add(setup: Iterable[Coordinate], terminal: SimpleMove, reveals: int):
        actions, latency = exact_route(table, cursor, setup, terminal)
        by_actions.setdefault(actions, RevealPlan(actions, latency, reveals))

    for x, y in sorted(safe, key=_reading_order):
        add((), SimpleMove(Action.OPEN, x, y), 1)

    for clue in evidence.constraints:
        setup = clue.hidden_cells.intersection(mines)
        remaining = clue.hidden_cells.difference(setup)
        if len(setup) != clue.remaining_mines or not remaining:
            continue
        x, y = clue.source
        if 1 <= observation[y][x] <= 8:
            add(setup, SimpleMove(Action.CHORD, x, y), len(remaining))
        for rx, ry in sorted(remaining, key=_reading_order):
            add(setup, SimpleMove(Action.OPEN, rx, ry), 1)

    # Only identical physical sequences were deduplicated. Equal metrics,
    # terminals, or first actions do not merge distinct plans.
    return tuple(sorted(by_actions.values(), key=_final_tie_key))


def prune_dominated(plans: Iterable[RevealPlan]) -> tuple[RevealPlan, ...]:
    """Remove strict (L <=, R >=) dominance, retaining equal-(L,R) plans."""
    original = tuple(plans)
    ordered = sorted(original, key=lambda plan: plan.latency_us)
    survivors: set[RevealPlan] = set()
    earlier_max_reveals = 0
    for _, same_latency in groupby(ordered, key=lambda plan: plan.latency_us):
        group = tuple(same_latency)
        group_max_reveals = max(plan.reveals for plan in group)
        if group_max_reveals > earlier_max_reveals:
            survivors.update(plan for plan in group if plan.reveals == group_max_reveals)
        earlier_max_reveals = max(earlier_max_reveals, group_max_reveals)
    return tuple(plan for plan in original if plan in survivors)


def compare_efficiency(left: RevealPlan, right: RevealPlan) -> int:
    """Compare L/R exactly; no floating point division or tolerance."""
    a = left.latency_us * right.reveals
    b = right.latency_us * left.reveals
    return (a > b) - (a < b)


def select_reveal_plan(plans: Iterable[RevealPlan]) -> RevealPlan:
    """Frozen E-FIRST ordering, including all deterministic tie breakers."""
    def compare(left: RevealPlan, right: RevealPlan) -> int:
        efficiency = compare_efficiency(left, right)
        if efficiency:
            return efficiency
        a = (left.latency_us, _final_tie_key(left))
        b = (right.latency_us, _final_tie_key(right))
        return (a > b) - (a < b)

    return min(plans, key=cmp_to_key(compare))


def plan_position(
    observation: Observation, num_mines: int, cursor: Coordinate,
    table: TimingTable,
) -> Stage3Decision:
    """Analyze and select one action using only the four public inputs.

    Call anew after every actual action, including a setup FLAG. The table is
    checked against the frozen identity; the caller supplies no policy toggle.
    Stage-2 validation and inference errors propagate unchanged.
    """
    table = validate_timing_table(table)
    evidence = analyze_position(observation, num_mines)
    if len(observation) > 16 or len(observation[0]) > 30:
        raise ValueError("Observation exceeds the frozen 30 x 16 physical grid.")
    if (
        not isinstance(cursor, (tuple, list)) or len(cursor) != 2
        or any(type(value) is not int for value in cursor)
        or not 0 <= cursor[0] < len(observation[0])
        or not 0 <= cursor[1] < len(observation)
    ):
        raise ValueError("Cursor must be a current board cell (x, y).")
    if evidence is None:
        raise Stage3PlanningError("Stage-2 analysis returned no selectable HIDDEN cell.")

    if evidence.kind == DecisionKind.PROBABILITY_GUESS:
        # Stage 2 already minimized exact risk over ALL hidden cells, including
        # floating cells, and broke the tie by (y,x). Do not reroute this OPEN.
        return Stage3Decision(evidence, evidence.move, None)

    candidates = generate_reveal_plans(observation, evidence, cursor, table)
    survivors = prune_dominated(candidates)
    if survivors:
        plan = select_reveal_plan(survivors)
        return Stage3Decision(evidence, plan.actions[0], plan)

    _, mines = certainty_pool(evidence)
    if not mines:
        raise Stage3PlanningError("Certainty has no reveal plan or certain FLAG.")
    x, y = min(
        mines, key=lambda cell: (action_cost(table, cursor, cell), _reading_order(cell)),
    )
    return Stage3Decision(evidence, SimpleMove(Action.FLAG, x, y), None)
