"""Thin S3D2-A execution loop over the unchanged K public/physical/archive seams.

Same order as run_k_lc1. Each decision, its opening proof and its guaranteed
set expire after the first actual input; only session M persists.

An applied opening may be a native direct OPEN that pruning removed, which the
unchanged K execution validator rejects by design. That validator is therefore
called, unmodified, for the K-LC1 record and its own move: it binds decision,
live observation, cursor and M. The applied OPEN is then checked here against
the live observation. Nothing claims the old validator authorised that OPEN.
Experimental copy only.
"""

from dataclasses import dataclass

from core_engine import Action, CellState, GameStatus
from experiments.program_d2_opening_policy import (
    APPLIED_CATEGORY, CANDIDATE_DEFINITION, CANDIDATE_ID, OpeningAssessment,
    OpeningSelection, opening_regions, select_opening_policy,
    validate_opening_selection,
)
from experiments.program_k_capability import KLocalSession
from experiments.program_k_runner import (
    KActionTrace, KExecutionError, _EffectArchive, _PublicEnginePort, _public_grid,
    _require, _valid_move, _validate_progress, validate_k_p0_execution,
)
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, load_timing_table, validate_timing_table


GUARANTEE_STATUSES = ("NOT_APPLICABLE", "PASS", "NOT_EVALUATED_TERMINAL")


@dataclass(frozen=True)
class OpeningActionTrace:
    """One executed input. ``action.selection`` is None for an applied opening."""

    action: KActionTrace
    choice: OpeningSelection | None
    guarantee_status: str

    @property
    def policy_id(self):
        return CANDIDATE_ID


@dataclass(frozen=True)
class OpeningRunResult:
    status: GameStatus
    traces: tuple[OpeningActionTrace, ...]
    final_M: frozenset[tuple[int, int]]

    @property
    def policy_id(self):
        return CANDIDATE_ID

    @property
    def policy_definition(self):
        return CANDIDATE_DEFINITION

    @property
    def moves(self):
        return tuple(t.action.move for t in self.traces)

    @property
    def total_modeled_us(self):
        return sum(t.action.modeled_action_us for t in self.traces)


def validate_opening_execution(observation, move, *, status, num_mines, cursor, current_mines,
                               decision=None, choice=None, table=None, initial=False) -> None:
    """Validate one input from actual pre-input public state; execute nothing.

    ``table`` is the runner's already authenticated timing table. The unchanged
    K validator runs first on the K-LC1 record. A retained choice ends there.
    """
    if initial is True:
        _require(choice is None, "OPENING_EXECUTION", "The canonical initial OPEN has no choice record.")
        validate_k_p0_execution(observation, move, status=status, num_mines=num_mines, cursor=cursor,
                                current_mines=current_mines, decision=None, selection=None, initial=True)
        return
    _require(initial is False and type(choice) is OpeningSelection,
             "OPENING_EXECUTION", "A fresh S3D2-A choice record is required.")
    validate_opening_selection(choice)
    _require(choice.inner.native.evidence is decision,
             "OPENING_EXECUTION", "The choice must reference this fresh decision.")
    kept = choice.inner.selected
    # Unchanged K validator on the K-LC1 record and ITS move: status, live
    # observation, cursor, M, accounting and continuation bindings.
    validate_k_p0_execution(observation, kept.move, status=status, num_mines=num_mines, cursor=cursor,
                            current_mines=current_mines, decision=decision, selection=kept)
    # The actual input is passed apart from the K-LC1 move validated above: its own type, action and
    # coordinates (exact int, inside the board) are checked here with the accepted check, before it is
    # used as an index or a cost-table key. An equal value of another type is not accepted.
    _require(_valid_move(move, len(observation[0]), len(observation)) and move == choice.move,
             "OPENING_EXECUTION", "Physical input must equal the recorded choice.")
    applied = choice.applied
    if applied is None:
        _require(move == kept.move, "OPENING_EXECUTION", "A retained choice executes the K-LC1 move.")
        return
    current = _public_grid(observation, num_mines)
    target = (move.x, move.y)
    safe = decision.selection_safe_cells
    _require(type(applied) is OpeningAssessment and applied.target == target
             and move.action is Action.OPEN
             and current[target[1]][target[0]] == CellState.HIDDEN
             and target in safe and target not in current_mines,
             "OPENING_EXECUTION", "Opening OPEN needs an actual HIDDEN current K-safe target outside M.")
    c = applied.candidate
    _require(any(c == item for item in choice.inner.native.candidates)
             and c.category == "DIRECT_SAFE_OPEN" and c.plan.actions == (move,)
             and not c.setup_cells and c.reveal_cells == frozenset({target}) and c.plan.reveals == 1,
             "OPENING_EXECUTION", "Opening must be one original native direct-safe OPEN.")
    _require(table is not None and c.plan.latency_us == action_cost(table, cursor, target),
             "OPENING_EXECUTION", "Opening cost differs from the actual cursor/table cost.")
    # Re-derive the zero proof from the LIVE observation and the owner's current M.
    regions, _, _ = opening_regions(current, safe, current_mines)
    _require(any(target in region.cells and region == applied.region for region in regions),
             "OPENING_EXECUTION", "Zero proof/guaranteed set is not valid for the actual current state.")


def validate_opening_effect(before, after, applied: OpeningAssessment) -> None:
    """After a PLAYING input: the guaranteed set must really have been opened."""
    region = applied.region
    changed = frozenset((x, y) for y, row in enumerate(before)
                        for x, value in enumerate(row) if after[y][x] != value)
    nonzero = region.guaranteed - region.cells - region.undetermined
    _require(all(after[y][x] == 0 for x, y in region.cells)
             and all(0 <= after[y][x] <= 8 for x, y in region.guaranteed)
             and all(after[y][x] >= 1 for x, y in nonzero)
             and region.guaranteed <= changed
             and (region.bound_kind != "EXACT" or changed == region.guaranteed),
             "OPENING_GUARANTEE", "Actual reveal differs from the proven guaranteed set.")


def run_s3d2(engine, *, table=None, capture_effects: bool = False,
             observer=None) -> OpeningRunResult:
    """Fresh canonical game. No resume, retries or suffix execution."""
    _require(type(capture_effects) is bool, "ARCHIVE_OPTION", "Expected boolean capture option.")
    port = _PublicEnginePort(engine)
    archive = _EffectArchive(engine) if capture_effects else None
    table = load_timing_table() if table is None else validate_timing_table(table)
    session = KLocalSession(port.width, port.height, port.num_mines)
    cursor, observation, traces = (0, 0), port.observe_playing(), []
    while True:
        initial, M_before = not traces, session.M
        decision = choice = None
        if initial:
            move, category = SimpleMove(Action.OPEN, 0, 0), "POLICY_INITIAL_OPEN"
        else:
            decision = session.analyze_decision(observation, status=GameStatus.PLAYING)
            choice = select_opening_policy(decision, cursor, table)
            move, category = choice.move, choice.category
        current = port.observe_playing()
        validate_opening_execution(
            current, move, status=port.status(), num_mines=port.num_mines, cursor=cursor,
            current_mines=session.M, decision=decision, choice=choice, table=table, initial=initial,
        )
        applied = None if choice is None else choice.applied
        preinput_M = session.M
        cost = action_cost(table, cursor, (move.x, move.y))
        port.apply(move)
        status_after = port.status()  # FIRST access after physical input.
        after_playing = None
        guarantee = "NOT_APPLICABLE"
        if status_after is GameStatus.PLAYING:
            after_playing = port.observe_playing()
            _validate_progress(current, after_playing, move)
            if applied is not None:
                validate_opening_effect(current, after_playing, applied)
                guarantee = "PASS"
        elif applied is not None:
            # Terminal rows are archival only; the guarantee is not read from them.
            guarantee = "NOT_EVALUATED_TERMINAL"
        effect = None
        if archive is not None:
            effect = archive.capture(
                current, move, after_playing=after_playing, status_after=status_after,
                input_index=len(traces), cursor_before=cursor, modeled_action_us=cost,
            )
        selection = None if choice is None or applied is not None else choice.inner.selected
        _require(applied is None or category == APPLIED_CATEGORY,
                 "OPENING_EXECUTION", "Applied opening must carry its own category.")
        record = OpeningActionTrace(KActionTrace(
            len(traces), move, category, selection, cursor, cost, status_after,
            M_before, preinput_M, public_effect=effect,
            public_effect_status="CAPTURED" if effect is not None else "NOT_EVALUATED",
        ), choice, guarantee)
        traces.append(record)
        decision = choice = applied = None
        if observer is not None:
            observer(record)
        if status_after is not GameStatus.PLAYING:
            return OpeningRunResult(status_after, tuple(traces), session.M)
        observation, cursor = after_playing, (move.x, move.y)
