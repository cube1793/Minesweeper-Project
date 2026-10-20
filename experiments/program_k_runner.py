"""Slice-4 K-P0 execution core, for implementation/unit verification only.

The synchronous caller gives this runner exclusive ownership of physical inputs.
Only public metadata, status, PLAYING observations and one-input application cross
the Engine port. Step return payloads are discarded without inspection. A-E1
qualification remains prospective; this is not an E0/E1 research entry point.

K-C owns inference and K-P0 owns selection. The separate validator below checks
their current execution boundary, never calls V1 validation, and never chooses a
replacement. Archived selections explain inputs; they grant no suffix authority.
SETUP_OPEN uses the normal policy vocabulary; P-8 is still unqualified.
"""

from dataclasses import dataclass
from fractions import Fraction

from core_engine import Action, CellState, GameStatus
from experiments.program_k_capability import (
    Accounting, Coordinate, DecisionAnalysis, ExactAnalysis, KIntegrityError,
    KLocalSession, LocalAnalysis, Observation, reading_order,
)
from experiments.program_k_policy import KCandidate, PolicySelection, select_policy
from simple_algorithm import SimpleMove
from stage3_physical import TimingTable, action_cost, load_timing_table, validate_timing_table
from stage3_planner import RevealPlan


class KExecutionError(KIntegrityError):
    """Stop this invocation; never repair, retry, or convert an error to LOSS."""


def _require(condition, code, detail):
    if not condition:
        raise KExecutionError(code, detail)


def _coordinate(cell, width, height):
    return (
        type(cell) is tuple and len(cell) == 2
        and all(type(value) is int for value in cell)
        and 0 <= cell[0] < width and 0 <= cell[1] < height
    )


def _public_grid(observation, num_mines) -> Observation:
    _require(type(observation) in (list, tuple) and 1 <= len(observation) <= 16,
             "PUBLIC_SHAPE", "Expected public rows within the frozen 30-by-16 grid.")
    _require(type(observation[0]) in (list, tuple) and 1 <= len(observation[0]) <= 30,
             "PUBLIC_SHAPE", "Expected nonempty public rows within 30-by-16.")
    width = len(observation[0])
    _require(all(type(row) in (list, tuple) and len(row) == width for row in observation),
             "PUBLIC_SHAPE", "Public rows must be rectangular.")
    _require(all(type(value) in (int, CellState) and (
        value in (CellState.HIDDEN, CellState.FLAGGED) or 0 <= value <= 8
    ) for row in observation for value in row),
        "PUBLIC_GLYPH", "Only public PLAYING glyphs may enter execution validation.")
    _require(type(num_mines) is int and 0 <= num_mines < width * len(observation),
             "PUBLIC_METADATA", "Invalid public mine total.")
    return tuple(tuple(int(value) for value in row) for row in observation)


def _cells(observation, glyph):
    return frozenset((x, y) for y, row in enumerate(observation)
                     for x, value in enumerate(row) if value == glyph)


def _neighbors(cell, observation):
    x, y = cell
    return frozenset(
        (nx, ny)
        for ny in range(max(0, y - 1), min(len(observation), y + 2))
        for nx in range(max(0, x - 1), min(len(observation[0]), x + 2))
        if (nx, ny) != cell
    )


def _valid_move(move, width, height):
    return (type(move) is SimpleMove and type(move.action) is Action
            and _coordinate((move.x, move.y), width, height))


def _exact_counts(exact, domain, width, height):
    """Check stored exact evidence, without another enumeration or inference."""
    _require(type(exact) is ExactAnalysis, "EXACT_EVIDENCE", "Missing reached exact evidence.")
    Z = exact.total_worlds
    _require(type(Z) is int and Z > 0 and type(exact.mine_worlds) is tuple,
             "EXACT_COUNTS", "Exact evidence requires positive integer Z and immutable counts.")
    counts = {}
    for item in exact.mine_worlds:
        _require(type(item) is tuple and len(item) == 2,
                 "EXACT_COUNTS", "Malformed exact marginal.")
        cell, count = item
        _require(_coordinate(cell, width, height) and cell in domain and cell not in counts
                 and type(count) is int and 0 <= count <= Z,
                 "EXACT_COUNTS", "Invalid or duplicate exact marginal.")
        counts[cell] = count
    _require(bool(counts) and counts.keys() == domain
             and tuple(counts) == exact.unresolved_cells,
             "EXACT_DOMAIN", "Exact counts must cover the complete unresolved domain.")
    minimum = min(counts.values())
    _require(exact.G0 == frozenset(c for c, n in counts.items() if n == 0)
             and exact.G1 == frozenset(c for c, n in counts.items() if n == Z)
             and type(exact.minimum_risk) is Fraction
             and exact.minimum_risk == Fraction(minimum, Z)
             and exact.minimum_risk_cells == frozenset(c for c, n in counts.items() if n == minimum),
             "EXACT_RISK", "Exact certainty, minimum risk or complete tie set disagrees.")
    return counts


def _validate_continuation(decision, width, height):
    local = decision.local
    _require(type(local) is LocalAnalysis and type(local.after) is Accounting,
             "DECISION_EVIDENCE", "Missing current local evidence.")
    if decision.continuation == "LOCAL_SAFE":
        _require(decision.phase_d is None and decision.phase_e is None
                 and decision.phase_e_status == "NOT_REACHED"
                 and decision.after == local.after and not decision.exact_certificates
                 and decision.selection_safe_cells == local.S_current
                 and bool(decision.selection_safe_cells) and decision.guess_target is None,
                 "CONTINUATION", "Local-safe continuation disagrees with current evidence.")
        return
    _require(decision.continuation in ("EXACT_SAFE", "EXACT_GUESS") and not local.S_current,
             "CONTINUATION", "Exact requires exhausted local safety.")
    d, e = decision.phase_d, decision.phase_e
    d_counts = _exact_counts(d, local.after.U, width, height)
    e_counts = _exact_counts(e, decision.after.U, width, height)
    _require(decision.phase_e_status == ("REACHED_CHANGED" if d.G1 else "REACHED_NO_CHANGE")
             and decision.after.M == local.after.M | d.G1
             and decision.after.U == local.after.U - d.G1
             and e.total_worlds == d.total_worlds
             and e_counts == {c: n for c, n in d_counts.items() if c not in d.G1}
             and decision.selection_safe_cells == d.G0 == e.G0 and not e.G1,
             "EXACT_RESTRICTION", "Current M, safe pool or D/E restriction disagrees.")
    if decision.continuation == "EXACT_SAFE":
        _require(bool(decision.selection_safe_cells) and decision.guess_target is None,
                 "CONTINUATION", "Exact-safe continuation needs current safety and no guess.")
    else:
        _require(not decision.selection_safe_cells and 0 < e.minimum_risk < 1
                 and all(0 < n < e.total_worlds for n in e_counts.values())
                 and decision.guess_target == min(e.minimum_risk_cells, key=reading_order),
                 "EXACT_GUESS", "Guess must exhaust certainty and use the exact (y,x) winner.")


def _selected_candidate(selection, observation, mines, safe):
    """Check the selected surviving plan against actual current physical cells."""
    plan = selection.plan
    _require(type(plan) is RevealPlan and type(selection.candidates) is tuple
             and type(selection.survivors) is tuple,
             "SELECTED_PLAN", "Certainty input requires a surviving reveal plan.")
    _require(all(type(c) is KCandidate for c in selection.candidates + selection.survivors)
             and all(c in selection.candidates for c in selection.survivors),
             "SELECTED_PLAN", "Survivors must belong to the current candidate record.")
    _require(not any(c.category == "SETUP_OPEN" for c in selection.survivors),
             "SETUP_OPEN_SURVIVED", "Nonempty SETUP_OPEN may not survive or execute.")
    matches = tuple(c for c in selection.survivors
                    if c.plan == plan and c.category == selection.category)
    _require(len(matches) == 1, "SELECTED_PLAN", "Selected plan is not a current survivor.")
    candidate = matches[0]
    width, height = len(observation[0]), len(observation)
    _require(type(plan.actions) is tuple and bool(plan.actions)
             and all(_valid_move(m, width, height) for m in plan.actions)
             and selection.move == plan.actions[0],
             "FIRST_INPUT", "Only the selected plan's first physical input is authorized.")
    terminal = plan.actions[-1]
    target = (terminal.x, terminal.y)
    hidden = _cells(observation, CellState.HIDDEN)
    flags = _cells(observation, CellState.FLAGGED)
    if selection.category == "DIRECT_SAFE_OPEN":
        _require(len(plan.actions) == 1 and terminal.action is Action.OPEN
                 and target in hidden & safe and not candidate.setup_cells
                 and candidate.reveal_cells == frozenset({target}) and plan.reveals == 1,
                 "SAFE_OPEN", "Direct OPEN needs a current HIDDEN K-safe target.")
    elif selection.category in ("DIRECT_CHORD", "SETUP_CHORD"):
        adjacent = _neighbors(target, observation)
        setup = adjacent & hidden & mines
        reveals = (adjacent & hidden) - setup
        _require(terminal.action is Action.CHORD and 1 <= observation[target[1]][target[0]] <= 8
                 and len(adjacent & flags) + len(setup) == observation[target[1]][target[0]]
                 and bool(reveals) and reveals <= safe
                 and candidate.setup_cells == setup and candidate.reveal_cells == reveals
                 and plan.reveals == len(reveals),
                 "CHORD_PLAN", "Whole-clue plan disagrees with current physical state/safety.")
        if selection.category == "DIRECT_CHORD":
            _require(not setup and len(plan.actions) == 1,
                     "CHORD_PLAN", "Direct CHORD cannot contain materialization.")
        else:
            prefix = plan.actions[:-1]
            _require(1 <= len(setup) <= 7 and len(prefix) == len(setup)
                     and all(m.action is Action.FLAG for m in prefix)
                     and frozenset((m.x, m.y) for m in prefix) == setup,
                     "FLAG_PLAN", "SETUP_CHORD must materialize exactly its HIDDEN M setup.")
    else:
        raise KExecutionError("POLICY_CATEGORY", "No standalone FLAG or other fallback is authorized.")


def validate_k_p0_execution(
    observation, move, *, status, num_mines, cursor, current_mines,
    decision=None, selection=None, initial=False,
) -> None:
    """Validate one input from actual pre-input public state; execute nothing.

    ``current_mines`` must be read from the runner-owned session now, not from
    an archived decision. The runner supplies its freshly produced ``decision``
    separately from the policy record and re-reads the Engine before this call.
    This pure function cannot authenticate an Engine/history on its own.
    """
    _require(status is GameStatus.PLAYING, "PUBLIC_STATUS", "Execution requires PLAYING.")
    current = _public_grid(observation, num_mines)
    width, height = len(current[0]), len(current)
    _require(_coordinate(cursor, width, height), "CURSOR", "Invalid actual cursor.")
    _require(_valid_move(move, width, height), "PHYSICAL_INPUT", "Invalid action/type/target.")
    _require(type(current_mines) is frozenset and all(
        _coordinate(c, width, height) for c in current_mines
    ), "CURRENT_M", "Current owned M must be an immutable coordinate set.")
    _require(type(initial) is bool, "INITIAL_POLICY", "Initial marker must be boolean.")
    hidden, flags = _cells(current, CellState.HIDDEN), _cells(current, CellState.FLAGGED)
    if initial:
        _require(decision is None and selection is None and not current_mines
                 and cursor == (0, 0) and len(hidden) == width * height
                 and move == SimpleMove(Action.OPEN, 0, 0),
                 "INITIAL_POLICY", "Canonical initial OPEN needs all HIDDEN, empty M and origin cursor.")
        return
    _require(type(decision) is DecisionAnalysis and type(selection) is PolicySelection,
             "DECISION_EVIDENCE", "A fresh decision and selection are required.")
    _require(type(decision.observation) is tuple
             and all(type(row) is tuple and all(type(v) is int for v in row)
                     for row in decision.observation)
             and decision.observation == current
             and type(decision.num_mines) is int and decision.num_mines == num_mines,
             "STALE_OBSERVATION", "Decision is not bound to the actual current public state.")
    _require(selection.evidence is decision, "STALE_SELECTION", "Policy must reference this fresh decision.")
    _require(_coordinate(selection.cursor, width, height) and selection.cursor == cursor,
             "CURSOR_MISMATCH", "Policy cursor differs from actual cursor.")
    _require(selection.failure_code is None and _valid_move(selection.move, width, height)
             and selection.move == move,
             "SELECTED_INPUT", "Physical input must equal the successful selected move.")
    after = decision.after
    _require(type(after) is Accounting and current_mines == after.M,
             "M_MISMATCH", "Owned current M differs from DecisionAnalysis.after.M.")
    _require(current_mines <= hidden | flags and flags <= current_mines
             and after.H == hidden and after.P == flags and after.J == flags | current_mines
             and after.U == hidden - current_mines and bool(after.U)
             and type(after.b) is int and after.b == num_mines - len(after.J)
             and 0 <= after.b <= len(after.U),
             "PHYSICAL_ACCOUNTING", "Current public cells disagree with K-P0 accounting.")
    safe = decision.selection_safe_cells
    _require(type(safe) is frozenset and safe <= after.U,
             "SAFE_DOMAIN", "K-safe evidence must be current HIDDEN unresolved cells.")
    _validate_continuation(decision, width, height)
    coordinate = (move.x, move.y)
    if decision.continuation == "EXACT_GUESS":
        _require(selection.category == "EXACT_MINIMUM_RISK_GUESS"
                 and selection.plan is None and selection.candidates == () and selection.survivors == ()
                 and move.action is Action.OPEN and coordinate in hidden & after.U
                 and coordinate == decision.guess_target,
                 "EXACT_GUESS", "Only the exact winner OPEN is allowed, with no preceding setup.")
        return
    _selected_candidate(selection, current, current_mines, safe)
    if move.action is Action.OPEN:
        _require(coordinate in hidden & safe and selection.category == "DIRECT_SAFE_OPEN",
                 "SAFE_OPEN", "OPEN requires an actual HIDDEN current K-safe target.")
    elif move.action is Action.FLAG:
        _require(coordinate in hidden & current_mines and selection.category == "SETUP_CHORD",
                 "FLAG_INPUT", "FLAG requires prior M and first input of surviving SETUP_CHORD.")
    else:
        adjacent = _neighbors(coordinate, current)
        to_open = adjacent & hidden
        _require(1 <= current[move.y][move.x] <= 8
                 and len(adjacent & flags) == current[move.y][move.x]
                 and bool(to_open) and to_open <= safe and selection.category == "DIRECT_CHORD",
                 "CHORD_INPUT", "CHORD requires actual flags and nonempty, entirely K-safe HIDDEN neighbors.")


class _PublicEnginePort:
    """Narrow input owner; never passes its Engine reference into K evidence."""

    __slots__ = ("__engine", "width", "height", "num_mines")

    def __init__(self, engine):
        self.__engine = engine
        _require(self.status() is GameStatus.PLAYING, "INITIAL_STATUS", "Canonical start must be PLAYING.")
        self.width, self.height, self.num_mines = engine.width, engine.height, engine.num_mines
        _require(all(type(v) is int for v in (self.width, self.height, self.num_mines))
                 and 1 <= self.width <= 30 and 1 <= self.height <= 16
                 and 0 <= self.num_mines < self.width * self.height,
                 "PUBLIC_METADATA", "Board must fit the frozen 30-by-16 grid.")

    def status(self):
        status = self.__engine.status
        _require(type(status) is GameStatus, "PUBLIC_STATUS", "Expected an explicit Engine status.")
        return status

    def observe_playing(self):
        _require(self.status() is GameStatus.PLAYING, "PUBLIC_STATUS", "No terminal observation access.")
        metadata = (self.__engine.width, self.__engine.height, self.__engine.num_mines)
        _require(all(type(v) is int for v in metadata)
                 and metadata == (self.width, self.height, self.num_mines),
                 "PUBLIC_METADATA", "Public board metadata changed during the run.")
        payload = self.__engine.get_observation()
        _require(self.status() is GameStatus.PLAYING, "PUBLIC_STATUS", "Observation capture crossed termination.")
        observation = _public_grid(payload, self.num_mines)
        _require(len(observation) == self.height and len(observation[0]) == self.width,
                 "PUBLIC_SHAPE", "Observation dimensions changed during the run.")
        return observation

    def apply(self, move):
        _require(self.status() is GameStatus.PLAYING, "PUBLIC_STATUS", "No postterminal input.")
        # Engine internally produces observations/statistics; discard the entire
        # return object. Nothing from it is solver input or public proof.
        self.__engine.step(move.x, move.y, move.action)


@dataclass(frozen=True)
class KActionTrace:
    """Detached archival evidence for one executed input, never a pending plan."""

    input_index: int
    move: SimpleMove
    category: str
    selection: PolicySelection | None
    cursor_before: Coordinate
    modeled_action_us: int
    status_after: GameStatus
    M_before: frozenset[Coordinate]
    preinput_M: frozenset[Coordinate]


@dataclass(frozen=True)
class KRunResult:
    status: GameStatus
    traces: tuple[KActionTrace, ...]
    final_M: frozenset[Coordinate]

    def __post_init__(self):
        object.__setattr__(self, "traces", tuple(self.traces))
        object.__setattr__(self, "final_M", frozenset(self.final_M))

    @property
    def moves(self):
        return tuple(trace.move for trace in self.traces)

    @property
    def total_modeled_us(self):
        return sum(trace.modeled_action_us for trace in self.traces)


def _validate_progress(before, after, move):
    hidden = _cells(before, CellState.HIDDEN)
    remaining = _cells(after, CellState.HIDDEN)
    _require(len(remaining) < len(hidden), "NO_PROGRESS", "PLAYING input did not reduce HIDDEN count.")
    changed = frozenset((x, y) for y, row in enumerate(before)
                        for x, value in enumerate(row) if after[y][x] != value)
    _require(changed <= hidden, "PUBLIC_REGRESSION", "An existing clue or physical flag changed.")
    target = (move.x, move.y)
    if move.action is Action.FLAG:
        _require(changed == frozenset({target}) and after[move.y][move.x] == CellState.FLAGGED,
                 "PUBLIC_EFFECT", "FLAG must change only its HIDDEN target to FLAGGED.")
    else:
        required = frozenset({target}) if move.action is Action.OPEN else _neighbors(target, before) & hidden
        _require(required <= changed and all(0 <= after[y][x] <= 8 for x, y in changed),
                 "PUBLIC_EFFECT", "Reveal input must open its public targets and create no flags.")


def run_k_p0(engine, *, table: TimingTable | None = None) -> KRunResult:
    """Canonical complete K-P0 unit run; no research stages, retries or resume.

    Analysis/planning CPU time is unmeasured. Model C is exactly the sum of the
    executed movement-plus-input lookups, including initial and terminal inputs.
    Progress bounds the number of inputs by board area without a move fallback.
    """
    port = _PublicEnginePort(engine)
    table = load_timing_table() if table is None else validate_timing_table(table)
    session = KLocalSession(port.width, port.height, port.num_mines)
    cursor = (0, 0)
    observation = port.observe_playing()
    traces = []
    while True:
        initial = not traces
        M_before = session.M
        decision = selection = None
        if initial:
            move = SimpleMove(Action.OPEN, 0, 0)
            category = "POLICY_INITIAL_OPEN"
        else:
            decision = session.analyze_decision(observation, status=GameStatus.PLAYING)
            selection = select_policy(decision, cursor, table)
            _require(type(selection) is PolicySelection, "DECISION_EVIDENCE", "Policy returned no valid selection.")
            move, category = selection.move, selection.category
        # Re-read actual state after planning; cached analysis input cannot
        # detect an intervening public mutation. No policy result proves this.
        current = port.observe_playing()
        validate_k_p0_execution(
            current, move, status=port.status(), num_mines=port.num_mines,
            cursor=cursor, current_mines=session.M, decision=decision,
            selection=selection, initial=initial,
        )
        preinput_M = session.M
        cost = action_cost(table, cursor, (move.x, move.y))
        port.apply(move)
        status_after = port.status()  # FIRST read after physical input.
        traces.append(KActionTrace(len(traces), move, category, selection, cursor,
                                   cost, status_after, M_before, preinput_M))
        # Only the archive holds these records now. No suffix/evidence is read
        # by the next decision, and terminal state never enters K reasoning.
        decision = selection = None
        if status_after is not GameStatus.PLAYING:
            return KRunResult(status_after, tuple(traces), session.M)
        observation = port.observe_playing()
        _validate_progress(current, observation, move)
        cursor = (move.x, move.y)
