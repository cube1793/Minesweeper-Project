"""Pure experimental K-P0 selection from detached current K decision evidence.

Slice 3 implements candidate construction and unit-verifiable physical choice,
not execution, initialization, a runner, or research qualification. Inference
belongs to K-C; routing, dominance and E-FIRST belong to the frozen helpers.
Only the actual observation supplies physical HIDDEN/FLAGGED/clue geometry.

The result retains its immutable decision premises and cursor for a later
validator. This stateless interface cannot authenticate freshness, game identity
or live PLAYING status. The runner must bind these premises to its current state,
validate the first input separately, and expire the entire result after input.
Canonical POLICY_INITIAL_OPEN also belongs to that runner boundary.

Generating/pruning SETUP_OPEN here does not qualify P-8. Research execution must
first pass the separately authorized exhaustive authenticated P-8 check. Any
nonempty SETUP_OPEN surviving ordinary dominance is exposed and fails closed.
"""

from dataclasses import dataclass
from fractions import Fraction

from core_engine import Action, CellState
from experiments.program_k_capability import (
    Accounting, Coordinate, DecisionAnalysis, ExactAnalysis, KIntegrityError,
    LocalAnalysis, reading_order,
)
from simple_algorithm import SimpleMove
from stage3_physical import TimingTable, validate_timing_table
from stage3_planner import RevealPlan, exact_route, prune_dominated, select_reveal_plan


@dataclass(frozen=True)
class KCandidate:
    """A physical sequence plus its current setup B and guaranteed reveal set.

    For CHORD, reveal_cells is the whole V; for OPEN it is only the target.
    SETUP_OPEN's originating clue/V can be reconstructed from the decision.
    Neither a safe flood nor a later reveal is credited.
    """

    plan: RevealPlan
    category: str
    setup_cells: frozenset[Coordinate]
    reveal_cells: frozenset[Coordinate]


@dataclass(frozen=True)
class PolicySelection:
    """One intended input, or immutable failure diagnostics on an exception.

    Candidate order is deterministic construction order, not a ranking. The
    frozen selector owns all ranking/ties. No plan suffix is execution authority.
    """

    evidence: DecisionAnalysis
    cursor: Coordinate
    move: SimpleMove | None
    plan: RevealPlan | None
    category: str | None
    candidates: tuple[KCandidate, ...]
    survivors: tuple[KCandidate, ...]
    failure_code: str | None = None

    @property
    def continuation(self) -> str:
        return self.evidence.continuation

    @property
    def setup_open_generated(self) -> bool:
        return any(item.category == "SETUP_OPEN" for item in self.candidates)

    @property
    def setup_open_pruned(self) -> bool:
        """True only when generated nonempty SETUP_OPENs were all dominated."""
        return self.setup_open_generated and not any(
            item.category == "SETUP_OPEN" for item in self.survivors
        )


class KPolicyIntegrityError(KIntegrityError):
    """No physical input is selected on failure; retain available diagnostics."""

    def __init__(self, code: str, detail: str, result: PolicySelection | None = None):
        self.result = result
        super().__init__(code, detail)


def _coordinate(cell: object, width: int, height: int) -> bool:
    return (
        type(cell) is tuple and len(cell) == 2
        and all(type(value) is int for value in cell)
        and 0 <= cell[0] < width and 0 <= cell[1] < height
    )


def _validate_inputs(evidence: DecisionAnalysis, cursor: Coordinate) -> None:
    """Check detached input consistency, without inference or live binding.

    This is deliberately not the later physical execution validator or a new
    proof checker. Accepted K-C evidence remains the source of safe/mine facts.
    """
    if type(evidence) is not DecisionAnalysis:
        raise KPolicyIntegrityError("DECISION_INPUT", "Expected detached DecisionAnalysis.")
    observation = evidence.observation
    if (
        type(observation) is not tuple or not 1 <= len(observation) <= 16
        or type(observation[0]) is not tuple or not 1 <= len(observation[0]) <= 30
    ):
        raise KPolicyIntegrityError("PUBLIC_SHAPE", "Expected an immutable grid within 30 x 16.")
    height, width = len(observation), len(observation[0])
    if any(type(row) is not tuple or len(row) != width for row in observation):
        raise KPolicyIntegrityError("PUBLIC_SHAPE", "Public rows must be rectangular tuples.")
    if any(
        type(value) is not int
        or (value not in (CellState.HIDDEN, CellState.FLAGGED) and not 0 <= value <= 8)
        for row in observation for value in row
    ):
        raise KPolicyIntegrityError("PUBLIC_GLYPH", "Only current public PLAYING glyphs are valid.")
    if not _coordinate(cursor, width, height):
        raise KPolicyIntegrityError("CURSOR", "Cursor must be a current board (x, y) integer tuple.")
    if type(evidence.num_mines) is not int or not 0 <= evidence.num_mines <= width * height:
        raise KPolicyIntegrityError("PUBLIC_METADATA", "Invalid public mine count.")
    after = evidence.after
    if type(after) is not Accounting or type(evidence.local) is not LocalAnalysis:
        raise KPolicyIntegrityError("DECISION_INPUT", "Missing accepted K accounting/local evidence.")
    for cells in (after.P, after.H, after.M, after.J, after.U, evidence.selection_safe_cells):
        if type(cells) is not frozenset or any(
            not _coordinate(cell, width, height) for cell in cells
        ):
            raise KPolicyIntegrityError("DECISION_DOMAIN", "Invalid immutable coordinate set.")
    hidden = frozenset(
        (x, y) for y, row in enumerate(observation)
        for x, value in enumerate(row) if value == CellState.HIDDEN
    )
    flags = frozenset(
        (x, y) for y, row in enumerate(observation)
        for x, value in enumerate(row) if value == CellState.FLAGGED
    )
    if (
        after.H != hidden or after.P != flags or not after.M <= hidden | flags
        or not flags <= after.M or after.J != flags | after.M
        or after.U != hidden - after.M or not after.U
        or type(after.b) is not int or after.b != evidence.num_mines - len(after.J)
        or not 0 <= after.b <= len(after.U)
    ):
        raise KPolicyIntegrityError("PHYSICAL_ACCOUNTING", "K domains disagree with actual physical state.")
    if not evidence.selection_safe_cells <= after.U:
        raise KPolicyIntegrityError("SAFE_DOMAIN", "A current safe must be physically HIDDEN and outside M.")

    if evidence.continuation == "LOCAL_SAFE":
        if (
            evidence.phase_d is not None or evidence.phase_e is not None
            or evidence.phase_e_status != "NOT_REACHED"
            or evidence.after != evidence.local.after
            or evidence.selection_safe_cells != evidence.local.S_current
            or evidence.guess_target is not None or evidence.exact_certificates
        ):
            raise KPolicyIntegrityError("CONTINUATION", "Local continuation disagrees with K evidence.")
    elif evidence.continuation in ("EXACT_SAFE", "EXACT_GUESS"):
        d, e = evidence.phase_d, evidence.phase_e
        if type(d) is not ExactAnalysis or type(e) is not ExactAnalysis:
            raise KPolicyIntegrityError("CONTINUATION", "Exact continuation requires D/E evidence.")
        if (
            evidence.local.S_current
            or evidence.phase_e_status != ("REACHED_CHANGED" if d.G1 else "REACHED_NO_CHANGE")
            or after.M != evidence.local.after.M | d.G1
            or evidence.selection_safe_cells != d.G0 or e.G0 != d.G0 or e.G1
            or e.total_worlds != d.total_worlds
            or e.mine_worlds != tuple(item for item in d.mine_worlds if item[0] in after.U)
            or frozenset(e.unresolved_cells) != after.U
        ):
            raise KPolicyIntegrityError("CONTINUATION", "Exact continuation/restriction disagrees with K evidence.")
        if evidence.continuation == "EXACT_SAFE" and evidence.guess_target is not None:
            raise KPolicyIntegrityError("CONTINUATION", "Exact-safe continuation cannot also guess.")
        if evidence.continuation == "EXACT_GUESS" and evidence.selection_safe_cells:
            raise KPolicyIntegrityError("CONTINUATION", "A guess cannot bypass current safe certainty.")
    else:
        raise KPolicyIntegrityError("CONTINUATION", "Unsupported K continuation kind.")


def _generate_candidates(
    evidence: DecisionAnalysis, cursor: Coordinate, table: TimingTable,
    include_setup_open: bool,
) -> tuple[KCandidate, ...]:
    """Construct K-admissible plans; caller validates inputs and frozen table.

    This private cost seam allows unit fault tables without relaxing the public
    entry point's authentication. It is not a research execution entry point.
    """
    observation = evidence.observation
    height, width = len(observation), len(observation[0])
    safe, mines = evidence.selection_safe_cells, evidence.after.M
    by_actions: dict[tuple[SimpleMove, ...], KCandidate] = {}

    def add(setup, terminal, reveals, category):
        actions, latency = exact_route(table, cursor, setup, terminal)
        plan = RevealPlan(actions, latency, len(reveals))
        by_actions.setdefault(actions, KCandidate(plan, category, setup, reveals))

    for x, y in sorted(safe, key=reading_order):
        if observation[y][x] == CellState.HIDDEN:
            add(frozenset(), SimpleMove(Action.OPEN, x, y), frozenset({(x, y)}),
                "DIRECT_SAFE_OPEN")

    for y, row in enumerate(observation):
        for x, value in enumerate(row):
            if not 1 <= value <= 8:
                continue
            adjacent = frozenset(
                (nx, ny)
                for ny in range(max(0, y - 1), min(height, y + 2))
                for nx in range(max(0, x - 1), min(width, x + 2))
                if (nx, ny) != (x, y)
            )
            physical_flags = sum(observation[ny][nx] == CellState.FLAGGED
                                 for nx, ny in adjacent)
            hidden = frozenset((nx, ny) for nx, ny in adjacent
                               if observation[ny][nx] == CellState.HIDDEN)
            setup = hidden & mines
            remaining = hidden - setup
            if len(setup) != value - physical_flags or not remaining or not remaining <= safe:
                continue
            add(setup, SimpleMove(Action.CHORD, x, y), remaining,
                "SETUP_CHORD" if setup else "DIRECT_CHORD")
            if include_setup_open:
                for vx, vy in sorted(remaining, key=reading_order):
                    add(setup, SimpleMove(Action.OPEN, vx, vy), frozenset({(vx, vy)}),
                        "SETUP_OPEN" if setup else "DIRECT_SAFE_OPEN")

    # No metric, common terminal, or common first-input deduplication.
    return tuple(by_actions.values())


def _select_candidates(
    evidence: DecisionAnalysis, cursor: Coordinate, candidates: tuple[KCandidate, ...],
) -> PolicySelection:
    """Use frozen dominance/ranking unchanged and retain failure diagnostics."""
    surviving_plans = frozenset(prune_dominated(item.plan for item in candidates))
    survivors = tuple(item for item in candidates if item.plan in surviving_plans)

    def fail(code, detail):
        result = PolicySelection(evidence, cursor, None, None, None, candidates, survivors, code)
        raise KPolicyIntegrityError(code, detail, result)

    if any(len(item.plan.actions) > 1 and item.plan.actions[-1].action == Action.OPEN
           for item in survivors):
        fail("SETUP_OPEN_SURVIVED", "Nonempty SETUP_OPEN survived ordinary frozen dominance.")
    if not survivors:
        fail("NO_REVEAL_CANDIDATE", "Current safe continuation has no surviving reveal plan.")
    plan = select_reveal_plan(item.plan for item in survivors)
    selected = next(item for item in survivors if item.plan == plan)
    move = plan.actions[0]
    if move.action == Action.FLAG and selected.category != "SETUP_CHORD":
        fail("FLAG_SELECTION", "A K-P0 FLAG must begin a surviving SETUP_CHORD.")
    return PolicySelection(evidence, cursor, move, plan, selected.category, candidates, survivors)


def _guess_move(evidence: DecisionAnalysis) -> SimpleMove:
    """Verify the complete stored exact minimum and preserve K's (y,x) target."""
    exact = evidence.phase_e
    Z = exact.total_worlds
    if type(Z) is not int or Z <= 0:
        raise KPolicyIntegrityError("EXACT_GUESS", "Guess requires positive integer world count.")
    counts = {}
    if type(exact.mine_worlds) is not tuple:
        raise KPolicyIntegrityError("EXACT_GUESS", "Exact marginals must be immutable.")
    for item in exact.mine_worlds:
        if type(item) is not tuple or len(item) != 2:
            raise KPolicyIntegrityError("EXACT_GUESS", "Malformed exact marginal.")
        cell, count = item
        if (
            not _coordinate(cell, len(evidence.observation[0]), len(evidence.observation))
            or cell not in evidence.after.U or cell in counts
            or type(count) is not int or not 0 < count < Z
        ):
            raise KPolicyIntegrityError("EXACT_GUESS", "Guess marginals must cover uncertain U' exactly.")
        counts[cell] = count
    if counts.keys() != evidence.after.U or tuple(counts) != exact.unresolved_cells:
        raise KPolicyIntegrityError("EXACT_GUESS", "Missing/duplicate unresolved exact evidence.")
    minimum = min(counts.values())
    risk = Fraction(minimum, Z)
    minima = frozenset(cell for cell, count in counts.items() if count == minimum)
    target = evidence.guess_target
    if (
        type(exact.minimum_risk) is not Fraction or exact.minimum_risk != risk
        or exact.minimum_risk_cells != minima
        or not _coordinate(target, len(evidence.observation[0]), len(evidence.observation))
        or target not in evidence.after.U or target != min(minima, key=reading_order)
        or evidence.observation[target[1]][target[0]] != CellState.HIDDEN
    ):
        raise KPolicyIntegrityError("EXACT_GUESS", "Selected target/risk/tie disagrees with current exact evidence.")
    return SimpleMove(Action.OPEN, *target)


def select_policy(
    evidence: DecisionAnalysis, cursor: Coordinate, table: TimingTable, *,
    include_setup_open: bool = True,
) -> PolicySelection:
    """Select exactly one intended physical input; execute nothing.

    ``include_setup_open`` controls optional generated vocabulary only. Ordinary
    pruning still sees every generated plan; omitting that vocabulary is not
    evidence for P-8 and must not be used to conceal a dominance counterexample.
    No cursor routing or materialization precedes an exact uncertain guess.
    """
    _validate_inputs(evidence, cursor)
    table = validate_timing_table(table)
    if type(include_setup_open) is not bool:
        raise KPolicyIntegrityError("POLICY_OPTION", "SETUP_OPEN vocabulary option must be boolean.")
    if evidence.continuation == "EXACT_GUESS":
        return PolicySelection(
            evidence, cursor, _guess_move(evidence), None, "EXACT_MINIMUM_RISK_GUESS", (), (),
        )
    candidates = _generate_candidates(evidence, cursor, table, include_setup_open)
    return _select_candidates(evidence, cursor, candidates)
