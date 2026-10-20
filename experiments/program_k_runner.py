"""Experimental K-P0 and K-CONTROL implementation/unit execution cores.

The synchronous caller gives this runner exclusive ownership of physical inputs.
Only public metadata, status, PLAYING observations and one-input application cross
the Engine port. Step return payloads are discarded without inspection. A-E1
qualification remains prospective; this is not an E0/E1 research entry point.

K-C owns inference and K-P0 owns selection. The separate validator below checks
their current execution boundary, never calls V1 validation, and never chooses a
replacement. Archived selections explain inputs; they grant no suffix authority.
SETUP_OPEN uses the normal policy vocabulary; P-8 is still unqualified.

K-CONTROL seals frozen V1 authority before detached, bounded K-C shadow work.
CONTROL remains production run_stage3, with an optional experimental capture
facade. Slice-6 evidence and timing are implementation foundations, not O-4 or
A-E qualification. Terminal effects are opt-in archival data only.
"""

from dataclasses import dataclass, field, fields, replace
from fractions import Fraction
from math import isfinite
from queue import Empty, Queue
from threading import Thread
from time import monotonic, perf_counter_ns

from core_engine import Action, CellState, GameStatus
from experiments.program_k_capability import (
    Accounting, ClueAccounting, Coordinate, CurrentPhysicalFlagAdmission,
    DecisionAnalysis, ExactAnalysis, KIntegrityError, KLocalSession, LocalAnalysis,
    Observation, _account, reading_order,
)
from experiments.program_k_oracles import (
    ExactGlobalMineCertificate, LocalMineCertificate, PublicProofError,
)
from experiments.program_k_policy import KCandidate, PolicySelection, select_policy
from experiments.program_k_evidence import (
    ArchivalObservation, DecisionTimings, ExternalV1FlagProvenance,
    PublicEffectRecord, ShadowSoundnessEvidence, compare_shadow_soundness,
    make_public_effect, make_v1_flag_provenance, project_v1_decision,
)
from simple_algorithm import SimpleMove
from stage3_physical import TimingTable, action_cost, load_timing_table, validate_timing_table
from stage3_planner import RevealPlan, Stage3Decision, plan_position
from stage3_runner import Stage3RunResult, Stage3RunnerError, _validate_execution, run_stage3


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


class _EffectArchive:
    """Separate archival reader, never supplied to K/shadow/public proof.

    PLAYING rows come from the status-gated execution prefix. A terminal read
    is made only here and immediately wrapped by make_public_effect. Its result
    is appended to the trace; it cannot replace the next live observation.
    """

    __slots__ = ("__engine",)

    def __init__(self, engine):
        self.__engine = engine

    def capture(self, before, move, *, after_playing, status_after, input_index,
                cursor_before, modeled_action_us):
        _require(self.__engine.status is status_after, "ARCHIVE_STATUS",
                 "Effect capture crossed a status boundary.")
        if status_after is GameStatus.PLAYING:
            _require(after_playing is not None, "ARCHIVE_PREFIX", "Missing PLAYING postinput capture.")
            after = after_playing
        else:
            _require(after_playing is None, "ARCHIVE_TERMINAL", "Terminal effects are archival only.")
            after = self.__engine.get_observation()
        _require(self.__engine.status is status_after, "ARCHIVE_STATUS",
                 "Effect observation capture crossed a status boundary.")
        return make_public_effect(
            before, move, after, input_index=input_index, status_after=status_after,
            cursor_before=cursor_before, modeled_action_us=modeled_action_us,
        )


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
    timings: DecisionTimings = field(default_factory=DecisionTimings, compare=False)
    public_effect: PublicEffectRecord | None = None
    public_effect_status: str = "NOT_EVALUATED"


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


def run_k_p0(engine, *, table: TimingTable | None = None,
             capture_effects: bool = False) -> KRunResult:
    """Canonical complete K-P0 unit run; no research stages, retries or resume.

    Analysis+planning runs from K decision entry through selected policy return;
    execution validation and optional archival effects have separate ns spans.
    Model C sums executed lookups, including initial and terminal inputs.
    Progress bounds the number of inputs by board area without a move fallback.
    """
    _require(type(capture_effects) is bool, "ARCHIVE_OPTION", "Expected boolean capture option.")
    port = _PublicEnginePort(engine)
    archive = _EffectArchive(engine) if capture_effects else None
    table = load_timing_table() if table is None else validate_timing_table(table)
    session = KLocalSession(port.width, port.height, port.num_mines)
    cursor = (0, 0)
    observation = port.observe_playing()
    traces = []
    while True:
        initial = not traces
        M_before = session.M
        decision = selection = None
        analysis_ns = None
        if initial:
            move = SimpleMove(Action.OPEN, 0, 0)
            category = "POLICY_INITIAL_OPEN"
        else:
            started_ns = perf_counter_ns()
            decision = session.analyze_decision(observation, status=GameStatus.PLAYING)
            selection = select_policy(decision, cursor, table)
            analysis_ns = perf_counter_ns() - started_ns
            _require(type(selection) is PolicySelection, "DECISION_EVIDENCE", "Policy returned no valid selection.")
            move, category = selection.move, selection.category
        # Re-read actual state after planning; cached analysis input cannot
        # detect an intervening public mutation. No policy result proves this.
        current = port.observe_playing()
        status_before = port.status()
        current_mines = session.M
        started_ns = perf_counter_ns()
        validate_k_p0_execution(
            current, move, status=status_before, num_mines=port.num_mines,
            cursor=cursor, current_mines=current_mines, decision=decision,
            selection=selection, initial=initial,
        )
        validation_ns = perf_counter_ns() - started_ns
        preinput_M = session.M
        cost = action_cost(table, cursor, (move.x, move.y))
        port.apply(move)
        status_after = port.status()  # FIRST read after physical input.
        after_playing = None
        if status_after is GameStatus.PLAYING:
            after_playing = port.observe_playing()
            _validate_progress(current, after_playing, move)
        effect = evidence_ns = None
        if archive is not None:
            started_ns = perf_counter_ns()
            effect = archive.capture(
                current, move, after_playing=after_playing, status_after=status_after,
                input_index=len(traces), cursor_before=cursor, modeled_action_us=cost,
            )
            evidence_ns = perf_counter_ns() - started_ns
        traces.append(KActionTrace(len(traces), move, category, selection, cursor,
                                   cost, status_after, M_before, preinput_M,
                                   DecisionTimings(k_analysis_planning_ns=analysis_ns,
                                                   k_execution_validation_ns=validation_ns,
                                                   evidence_ns=evidence_ns),
                                   effect, "CAPTURED" if effect is not None else "NOT_EVALUATED"))
        # Only the archive holds these records now. No suffix/evidence is read
        # by the next decision, and terminal state never enters K reasoning.
        decision = selection = None
        if status_after is not GameStatus.PLAYING:
            return KRunResult(status_after, tuple(traces), session.M)
        observation = after_playing
        cursor = (move.x, move.y)


@dataclass(frozen=True)
class _SealedV1Input:
    observation: Observation
    decision: Stage3Decision | None
    move: SimpleMove
    cursor_before: Coordinate
    modeled_action_us: int


@dataclass(frozen=True)
class ShadowInput:
    """Only current detached public values and the run's last accepted M.

    No V1 decision, Engine, callback, timing-dependent selection or future state
    crosses this boundary. K-C analysis needs no physical timing table.
    """

    observation: Observation
    width: int
    height: int
    num_mines: int
    cursor: Coordinate
    M: frozenset[Coordinate]
    physical_flag_admission: CurrentPhysicalFlagAdmission


class ShadowComparisonError(ValueError):
    """A comparison confined to the detached shadow path failed."""


class ShadowSoundnessViolation(ShadowComparisonError):
    """Public semantic discrepancy/fault hook; never a hidden-truth audit."""


class _MalformedShadowOutput(ValueError):
    pass


@dataclass(frozen=True)
class ShadowFailure:
    failure_class: str
    detected_boundary: int
    last_valid_boundary: int | None
    detail: str
    implicated_boundary: int | None = None
    invalidation_scope: str = "WHOLE_SHADOW_STREAM"


@dataclass(frozen=True)
class ShadowCheckpoint:
    """One run-owned snapshot; a disabled snapshot is archival only.

    Boundaries are zero-based physical input indices, at preinput checkpoints.
    The current decision expires after its input; only last_valid_M is fed into
    another call. Failure invalidates current/dependent evidence, never V1.
    """

    enabled: bool = True
    last_valid_M: frozenset[Coordinate] = frozenset()
    decision: DecisionAnalysis | None = None
    failure: ShadowFailure | None = None
    last_valid_boundary: int | None = None
    evidence_valid: bool = False
    v1_continues: bool = True


@dataclass(frozen=True)
class KControlActionTrace:
    input_index: int
    observation: Observation
    decision: Stage3Decision | None
    move: SimpleMove
    cursor_before: Coordinate
    modeled_action_us: int
    status_after: GameStatus
    shadow: ShadowCheckpoint
    M_before: frozenset[Coordinate]
    preinput_M: frozenset[Coordinate]
    timings: DecisionTimings = field(default_factory=DecisionTimings, compare=False)
    public_effect: PublicEffectRecord | None = None
    public_effect_status: str = "NOT_EVALUATED"
    soundness: ShadowSoundnessEvidence | None = None
    external_flag: ExternalV1FlagProvenance | None = None
    external_flag_antecedents: tuple[ExternalV1FlagProvenance, ...] = ()


@dataclass(frozen=True)
class KControlRunResult:
    status: GameStatus
    traces: tuple[KControlActionTrace, ...]
    shadow: ShadowCheckpoint

    @property
    def moves(self):
        return tuple(trace.move for trace in self.traces)

    @property
    def total_modeled_us(self):
        return sum(trace.modeled_action_us for trace in self.traces)

    @property
    def final_M(self):
        return self.shadow.last_valid_M


def _shadow_input(observation, width, height, num_mines, cursor, M, executed_v1_flags):
    detached = tuple(tuple(value for value in row) for row in observation)
    flags = _cells(detached, CellState.FLAGGED)
    # Only identities recorded after successful validated V1 FLAG execution
    # receive admission. K-C rejects any remaining P outside M before inference.
    admission = CurrentPhysicalFlagAdmission(detached, flags & executed_v1_flags)
    return ShadowInput(detached, width, height, num_mines, cursor, M, admission)


def _analyze_shadow(inputs: ShadowInput) -> DecisionAnalysis:
    # This is a scratch computation, not a new authoritative run/session. Only
    # the runner's accepted immutable M is seeded; it starts empty for each run.
    # Physical public-history/progress guards stay with the input owner. The
    # scratch object is never returned, shared with the owner, repaired or resumed.
    scratch = KLocalSession(inputs.width, inputs.height, inputs.num_mines)
    scratch._M = inputs.M
    return scratch.analyze_decision(
        inputs.observation, status=GameStatus.PLAYING,
        physical_flag_admission=inputs.physical_flag_admission,
    )


def _shadow_require(condition, detail):
    if not condition:
        raise _MalformedShadowOutput(detail)


def _immutable_shadow_value(value):
    """Reject mutable/custom nested payloads before any result is accepted.

    This check itself runs inside the timeout boundary. It is shape validation,
    not an independent acquisition-soundness or materialized-equivalence oracle.
    """
    if type(value) in (str, int, bool, Fraction, GameStatus, type(None)):
        return
    if type(value) in (tuple, frozenset):
        for item in value:
            _immutable_shadow_value(item)
        return
    if type(value) in (DecisionAnalysis, LocalAnalysis, Accounting, ClueAccounting,
                       ExactAnalysis, LocalMineCertificate, ExactGlobalMineCertificate):
        for field in fields(value):
            _immutable_shadow_value(getattr(value, field.name))
        return
    raise _MalformedShadowOutput("Shadow output contains a mutable or unsupported value.")


def _validate_shadow_result(inputs, result):
    """Bind current output and monotonic M; never validate a physical V1 move."""
    _shadow_require(type(result) is DecisionAnalysis, "Expected DecisionAnalysis.")
    _immutable_shadow_value(result)
    _shadow_require(type(result.observation) is tuple
                    and all(type(row) is tuple and all(type(v) is int for v in row)
                            for row in result.observation)
                    and result.observation == inputs.observation
                    and type(result.num_mines) is int and result.num_mines == inputs.num_mines,
                    "Shadow output is not bound to this public checkpoint.")
    local = result.local
    _shadow_require(type(local) is LocalAnalysis and type(local.before) is Accounting
                    and type(local.after) is Accounting and type(result.after) is Accounting,
                    "Missing shadow phase accounting.")
    for accounting in (local.before, local.after, result.after):
        for cells in (accounting.P, accounting.H, accounting.M, accounting.J, accounting.U):
            _shadow_require(type(cells) is frozenset and all(
                _coordinate(c, inputs.width, inputs.height) for c in cells
            ), "Malformed accounting coordinate set.")
        _shadow_require(type(accounting.b) is int and type(accounting.constraints) is tuple,
                        "Malformed budget or constraints.")
        for clue in accounting.constraints:
            _shadow_require(type(clue) is ClueAccounting
                            and _coordinate(clue.source, inputs.width, inputs.height)
                            and type(clue.clue_value) is int and type(clue.rc) is int
                            and type(clue.fixed_mines) is frozenset and type(clue.Uc) is frozenset
                            and all(_coordinate(c, inputs.width, inputs.height)
                                    for c in clue.fixed_mines | clue.Uc),
                            "Malformed clue accounting.")
        expected = _account(inputs.observation, inputs.num_mines, accounting.M,
                            inputs.physical_flag_admission)
        _shadow_require(accounting == expected and bool(accounting.U),
                        "Shadow phase accounting disagrees with current public inputs.")
    for cells in (local.acquired_mines, local.S_first, local.S_second_all,
                  local.S_new, local.S_current, result.selection_safe_cells):
        _shadow_require(type(cells) is frozenset and all(
            _coordinate(c, inputs.width, inputs.height) for c in cells
        ), "Malformed shadow classification set.")
    _shadow_require(local.before.M == inputs.M
                    and inputs.M <= local.after.M <= result.after.M
                    and local.acquired_mines == local.after.M - inputs.M
                    and local.acquired_mines <= local.before.U
                    and local.S_first <= local.S_second_all
                    and local.S_new == local.S_second_all - local.S_first
                    and local.S_current == local.S_first | local.S_second_all
                    and local.S_current <= local.after.U
                    and result.selection_safe_cells <= result.after.U,
                    "Shadow M or local-safe phase relationships are malformed.")
    _shadow_require(type(local.certificates) is tuple
                    and len(local.certificates) == len(local.acquired_mines)
                    and all(type(c) is LocalMineCertificate for c in local.certificates)
                    and frozenset(c.target for c in local.certificates) == local.acquired_mines,
                    "Local acquisition certificate identities disagree.")
    for certificate in local.certificates:
        _shadow_require(certificate.observation == inputs.observation
                        and certificate.num_mines == inputs.num_mines
                        and certificate.status is GameStatus.PLAYING
                        and certificate.retained_mines == inputs.M,
                        "Local certificate is not from the pre-acquisition checkpoint.")
    _validate_continuation(result, inputs.width, inputs.height)
    acquired_exact = frozenset() if result.phase_d is None else result.phase_d.G1
    _shadow_require(type(result.exact_certificates) is tuple
                    and len(result.exact_certificates) == len(acquired_exact)
                    and all(type(c) is ExactGlobalMineCertificate for c in result.exact_certificates)
                    and frozenset(c.target for c in result.exact_certificates) == acquired_exact,
                    "Exact acquisition certificate identities disagree.")
    for certificate in result.exact_certificates:
        _shadow_require(certificate.observation == inputs.observation
                        and certificate.num_mines == inputs.num_mines
                        and certificate.status is GameStatus.PLAYING
                        and certificate.retained_mines == local.after.M
                        and certificate.exact_reached is True
                        and certificate.total_worlds == result.phase_d.total_worlds
                        and certificate.mine_worlds == result.phase_d.mine_worlds,
                        "Exact certificate is not from this pre-acquisition D phase.")


def _shadow_worker(inputs, mailbox, v1_projection, boundary):
    """One disposable daemon operation; no reference to the active run owner.

    The mailbox is private to this checkpoint. A timeout abandons it permanently;
    a late publication cannot change active/archived M or start another call.
    """
    result = soundness = None
    failure_class, detail = None, ""
    started_ns = perf_counter_ns()
    try:
        result = _analyze_shadow(inputs)
    except ShadowSoundnessViolation as error:
        failure_class, detail = "SHADOW_SOUNDNESS_VIOLATION", str(error)
    except (ShadowComparisonError, PublicProofError) as error:
        failure_class, detail = "SHADOW_COMPARISON_EXCEPTION", str(error)
    except KIntegrityError as error:
        failure_class, detail = "SHADOW_SEMANTIC_EXCEPTION", str(error)
    except Exception as error:
        failure_class, detail = "SHADOW_EXCEPTION", f"{type(error).__name__}: {error}"
    else:
        try:
            _validate_shadow_result(inputs, result)
        except Exception as error:
            # Suspect objects never cross into the active state or diagnostics;
            # only a detached textual diagnosis is retained.
            failure_class, detail = "SHADOW_MALFORMED_OUTPUT", f"{type(error).__name__}: {error}"
    shadow_ns = perf_counter_ns() - started_ns
    comparison_ns = None
    if failure_class is None:
        # The separate public comparator sees a detached semantic projection,
        # never V1 ownership. It is within the same enforceable deadline, but
        # its measured span is disjoint from shadow analysis/output validation.
        started_ns = perf_counter_ns()
        try:
            soundness = compare_shadow_soundness(
                v1_projection, result.selection_safe_cells, boundary=boundary,
            )
            if (type(soundness) is not ShadowSoundnessEvidence
                    or soundness.boundary != boundary
                    or soundness.v1_decision != v1_projection
                    or soundness.safe_cells != tuple(sorted(result.selection_safe_cells,
                                                           key=reading_order))):
                raise ShadowComparisonError("Malformed or unbound public shadow comparison result.")
            # Reconstruct to enforce the immutable evidence invariants even if
            # a faulty comparator bypassed its dataclass constructor.
            soundness = replace(soundness)
            if soundness.classification == "SHADOW_SOUNDNESS_VIOLATION":
                failure_class = soundness.classification
                detail = "Current shadow safety contradicts the sealed frozen V1 probability guess."
            elif soundness.classification not in ("NO_DISCREPANCY", "NOT_EVALUATED"):
                raise ShadowComparisonError("Unsupported public shadow comparison result.")
        except Exception as error:
            failure_class, detail = "SHADOW_COMPARISON_EXCEPTION", f"{type(error).__name__}: {error}"
            soundness = None
        comparison_ns = perf_counter_ns() - started_ns
    mailbox.put((result if failure_class is None else None, failure_class, detail,
                 soundness, shadow_ns, comparison_ns))


def _advance_shadow(state, inputs, boundary, timeout_s, v1_projection):
    """Only this Engine-owner-side function can accept a new shadow snapshot."""
    if not state.enabled:
        return replace(state, decision=None, evidence_valid=False), None, None, None
    mailbox = Queue(maxsize=1)
    deadline = monotonic() + timeout_s
    worker = Thread(target=_shadow_worker, args=(inputs, mailbox, v1_projection, boundary), daemon=True,
                    name="program-k-shadow")
    worker.start()
    try:
        result, failure_class, detail, soundness, shadow_ns, comparison_ns = mailbox.get(
            timeout=max(0, deadline - monotonic()))
        if monotonic() > deadline:
            raise Empty
    except Empty:
        result, failure_class, detail = None, "SHADOW_TIMEOUT", "Shadow-only deadline expired."
        soundness = shadow_ns = comparison_ns = None
    if failure_class is not None:
        # The failed claim's checkpoint is exact. Earlier acquisition origin is
        # not established by this comparison, so dependent qualification of the
        # whole shadow stream is invalidated; last M remains archive only.
        failure = ShadowFailure(failure_class, boundary, state.last_valid_boundary, detail,
                                boundary if failure_class == "SHADOW_SOUNDNESS_VIOLATION" else None)
        checkpoint = ShadowCheckpoint(False, state.last_valid_M, None, failure,
                                      state.last_valid_boundary, False, True)
        return checkpoint, soundness, shadow_ns, comparison_ns
    return (ShadowCheckpoint(True, result.after.M, result, None, boundary, True, True),
            soundness, shadow_ns, comparison_ns)


def run_k_control(engine, *, table: TimingTable | None = None,
                  shadow_timeout_s: float = 1.0,
                  capture_effects: bool = False) -> KControlRunResult:
    """Frozen V1 physical stream plus detached K-C, for bounded unit use only.

    The caller grants exclusive Engine/input ownership, just as for run_k_p0.
    The finite per-call limit is operational containment, not a qualified A-E
    machine envelope. A daemon may finish later, but it owns no live state.
    Planner/validator/Engine exceptions propagate as system/V1 failures.
    """
    if (type(shadow_timeout_s) not in (int, float) or not isfinite(shadow_timeout_s)
            or not 0 < shadow_timeout_s <= 60):
        raise ValueError("Shadow-only timeout must be finite and in (0, 60] seconds.")
    _require(type(capture_effects) is bool, "ARCHIVE_OPTION", "Expected boolean capture option.")
    shadow = ShadowCheckpoint()
    status = engine.status
    if status in (GameStatus.WON, GameStatus.LOST):
        return KControlRunResult(status, (), shadow)
    port = _PublicEnginePort(engine)
    archive = _EffectArchive(engine) if capture_effects else None
    table = load_timing_table() if table is None else validate_timing_table(table)
    observation = port.observe_playing()
    if len(_cells(observation, CellState.HIDDEN)) != port.width * port.height:
        raise Stage3RunnerError("Canonical K-CONTROL requires an entirely HIDDEN start.")
    cursor = (0, 0)
    executed_v1_flags = frozenset()
    flag_provenance = ()
    traces = []
    while True:
        decision = None
        planner_ns = shadow_ns = comparison_ns = None
        soundness = external_flag = None
        if not traces:
            move = SimpleMove(Action.OPEN, 0, 0)
        else:
            started_ns = perf_counter_ns()
            decision = plan_position(observation, port.num_mines, cursor, table)
            planner_ns = perf_counter_ns() - started_ns
            if decision is None:
                raise Stage3RunnerError("Planner returned no action while PLAYING.")
            move = decision.move
        started_ns = perf_counter_ns()
        _validate_execution(observation, move, decision)
        validation_ns = perf_counter_ns() - started_ns
        sealed = _SealedV1Input(observation, decision, move, cursor,
                                action_cost(table, cursor, (move.x, move.y)))
        M_before = shadow.last_valid_M
        started_ns = perf_counter_ns()
        v1_projection = project_v1_decision(decision) if decision is not None else None
        # Provenance is evidence about V1's validated physical FLAG, not an M
        # acquisition. Independent verification is post-hoc, outside selection.
        if move.action is Action.FLAG:
            external_flag = make_v1_flag_provenance(
                sealed.observation, sealed.decision, num_mines=port.num_mines,
                boundary=len(traces), prior_flags=flag_provenance,
            )
        antecedents = tuple(record for record in flag_provenance
                            if (record.move.x, record.move.y) in _cells(observation, CellState.FLAGGED))
        evidence_ns = perf_counter_ns() - started_ns
        if decision is not None and shadow.enabled:
            # Provenance comes only from successfully executed validated V1
            # FLAG inputs. Physical identity itself never promotes a mine to M.
            inputs = _shadow_input(sealed.observation, port.width, port.height,
                                   port.num_mines, sealed.cursor_before,
                                   shadow.last_valid_M, executed_v1_flags)
            shadow, soundness, shadow_ns, comparison_ns = _advance_shadow(
                shadow, inputs, len(traces), shadow_timeout_s, v1_projection,
            )
        # A shadow failure changes no action field. If exclusive ownership was
        # violated, abort as a V1/system failure; never replan a replacement.
        current = port.observe_playing()
        if current != sealed.observation:
            raise Stage3RunnerError("Public state changed after the V1 input was sealed.")
        started_ns = perf_counter_ns()
        _validate_execution(current, sealed.move, sealed.decision)
        # These are two disjoint frozen-validation calls, not nested spans.
        validation_ns += perf_counter_ns() - started_ns
        port.apply(sealed.move)
        status_after = port.status()  # FIRST access after Engine input.
        after_playing = None
        if status_after is GameStatus.PLAYING:
            after_playing = port.observe_playing()
            _validate_progress(sealed.observation, after_playing, sealed.move)
        effect = None
        if archive is not None:
            started_ns = perf_counter_ns()
            effect = archive.capture(
                sealed.observation, sealed.move, after_playing=after_playing,
                status_after=status_after, input_index=len(traces),
                cursor_before=sealed.cursor_before, modeled_action_us=sealed.modeled_action_us,
            )
            evidence_ns += perf_counter_ns() - started_ns
        traces.append(KControlActionTrace(
            len(traces), sealed.observation, sealed.decision, sealed.move,
            sealed.cursor_before, sealed.modeled_action_us, status_after,
            shadow, M_before, shadow.last_valid_M,
            DecisionTimings(v1_plan_position_ns=planner_ns,
                            v1_execution_validation_ns=validation_ns,
                            shadow_ns=shadow_ns, comparison_ns=comparison_ns,
                            evidence_ns=evidence_ns),
            effect, "CAPTURED" if effect is not None else "NOT_EVALUATED",
            soundness, external_flag, antecedents,
        ))
        # Optional terminal effects above are archive only. No further live
        # observation, capability call, public-proof comparison or shadow job.
        if status_after is not GameStatus.PLAYING:
            return KControlRunResult(status_after, tuple(traces),
                                     replace(shadow, decision=None, evidence_valid=False))
        if sealed.move.action is Action.FLAG:
            executed_v1_flags = executed_v1_flags | {(sealed.move.x, sealed.move.y)}
            flag_provenance += (external_flag,)
        observation = after_playing
        cursor = (sealed.move.x, sealed.move.y)
        shadow = replace(shadow, decision=None, evidence_valid=False)


@dataclass(frozen=True)
class ControlCaptureResult:
    """Unchanged frozen CONTROL result plus segregated experimental archives."""

    control: Stage3RunResult
    effects: tuple[PublicEffectRecord, ...]
    timings: tuple[DecisionTimings, ...] = field(compare=False)
    capture_method: str = "STATUS_GATED_ACTUAL_EXECUTION"

    def __post_init__(self):
        _require(type(self.control) is Stage3RunResult
                 and type(self.effects) is tuple and type(self.timings) is tuple
                 and len(self.control.traces) == len(self.effects) == len(self.timings)
                 and all(type(e) is PublicEffectRecord for e in self.effects)
                 and all(type(t) is DecisionTimings for t in self.timings)
                 and self.capture_method == "STATUS_GATED_ACTUAL_EXECUTION",
                 "ARCHIVE_SEQUENCE", "CONTROL capture needs complete immutable paired records.")
        for index, (trace, effect, timings) in enumerate(zip(
                self.control.traces, self.effects, self.timings)):
            _require(effect.input_index == index
                     and (effect.move.action, effect.move.x, effect.move.y)
                     == (trace.move.action, trace.move.x, trace.move.y)
                     and effect.status_after is trace.status_after
                     and effect.cursor_before == trace.cursor_before
                     and effect.modeled_action_us == trace.modeled_action_us
                     and timings.v1_plan_position_ns == trace.decision_compute_ns,
                     "ARCHIVE_SEQUENCE", "CONTROL trace/effect/timing bindings disagree.")

    @property
    def traces(self):
        return self.control.traces

    @property
    def moves(self):
        return self.control.moves

    @property
    def status(self):
        return self.control.status

    @property
    def total_modeled_us(self):
        return self.control.total_modeled_us

    @property
    def capture_status(self):
        if not self.effects:
            return "NOT_REACHED"
        return ("COMPLETE" if self.status in (GameStatus.WON, GameStatus.LOST)
                and self.effects[-1].status_after is self.status else "INCOMPLETE")


class _ControlCapturePort:
    """Minimal facade for frozen run_stage3; no inference or action selection.

    Its PLAYING observations are the actual status-gated execution prefix.
    The one terminal get_observation call required by frozen run_stage3 is
    explicitly archival: V1 uses it for effect deltas, then exits on status.
    It is never installed as this facade's next PLAYING observation. No K or
    public-proof function receives this facade or its terminal archive.
    """

    __slots__ = ("__engine", "__port", "__playing", "__before", "__after",
                 "__move", "__status_after", "effects", "timings")

    def __init__(self, engine):
        self.__engine = engine
        self.__port = _PublicEnginePort(engine)
        self.__playing = self.__before = self.__after = self.__move = None
        self.__status_after = None
        self.effects, self.timings = [], []

    @property
    def width(self):
        return self.__port.width

    @property
    def height(self):
        return self.__port.height

    @property
    def num_mines(self):
        return self.__port.num_mines

    @property
    def status(self):
        return self.__port.status()

    def get_observation(self):
        status = self.__port.status()
        if self.__move is None:
            self.__playing = self.__port.observe_playing()
            return self.__playing
        _require(status is self.__status_after, "ARCHIVE_STATUS", "CONTROL capture status changed.")
        if self.__after is None:
            if status is GameStatus.PLAYING:
                rows = self.__port.observe_playing()
                self.__playing = rows
            else:
                rows = self.__engine.get_observation()
                self.__playing = None
            _require(self.__port.status() is status, "ARCHIVE_STATUS",
                     "CONTROL effect observation crossed a status boundary.")
            self.__after = ArchivalObservation(rows, status)
        # This terminal return belongs solely to frozen V1's existing effect
        # bookkeeping. It never becomes an observation in the K execution port.
        return self.__after.rows

    def step(self, x, y, action):
        _require(self.__move is None and self.__playing is not None,
                 "ARCHIVE_SEQUENCE", "CONTROL input needs its current PLAYING prefix.")
        current = self.__port.observe_playing()
        _require(current == self.__playing, "ARCHIVE_PREFIX", "CONTROL public prefix changed.")
        self.__before, self.__move = current, SimpleMove(action, x, y)
        self.__port.apply(self.__move)
        self.__status_after = self.__port.status()  # First access after input.
        # The complete Engine return payload has already been discarded.

    def record(self, trace):
        started_ns = perf_counter_ns()
        _require(self.__move == trace.move and self.__after is not None
                 and trace.status_after is self.__status_after,
                 "ARCHIVE_SEQUENCE", "Frozen CONTROL trace is not bound to the captured input.")
        effect = make_public_effect(
            self.__before, trace.move, self.__after.rows, input_index=len(self.effects),
            status_after=trace.status_after, cursor_before=trace.cursor_before,
            modeled_action_us=trace.modeled_action_us,
        )
        _require(effect.safe_cells_opened_delta == trace.safe_cells_opened_delta
                 and effect.explicit_flag_delta == trace.explicit_flag_delta,
                 "ARCHIVE_DELTA", "CONTROL deltas disagree with captured public effects.")
        self.effects.append(effect)
        self.__before = self.__after = self.__move = self.__status_after = None
        evidence_ns = perf_counter_ns() - started_ns
        self.timings.append(DecisionTimings(
            v1_plan_position_ns=trace.decision_compute_ns, evidence_ns=evidence_ns,
        ))


def run_control_capture(engine, *, table: TimingTable | None = None) -> ControlCaptureResult:
    """Observe unchanged CONTROL execution; no production monkeypatch or replay.

    Planner-only ns are copied from frozen decision_compute_ns exactly. Frozen
    validation is UNMEASURED. evidence_ns measures only observer record assembly
    and delta checks; observation capture is unmeasured. This is an implementation
    API and confers no A-E2 or O-4 research qualification.
    """
    if engine.status in (GameStatus.WON, GameStatus.LOST):
        return ControlCaptureResult(run_stage3(engine, table=table), (), ())
    port = _ControlCapturePort(engine)
    control = run_stage3(port, table=table, observer=port.record)
    _require(len(control.traces) == len(port.effects) == len(port.timings),
             "ARCHIVE_SEQUENCE", "Missing CONTROL input coverage.")
    return ControlCaptureResult(control, tuple(port.effects), tuple(port.timings))
