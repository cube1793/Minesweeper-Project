"""Thin S3D3-A stage-2 (FORCED_PAIR_AND_TIE_LOOKAHEAD_V1) execution loop over the unchanged K seams.

Same order as run_k_lc1 and the stage-1 runner. Each decision, its pair proof
and its look-ahead values expire after the first actual input; only session M
persists. Look-ahead values are never carried into a later decision.

A changed guess target is not K-LC1's guess_target, which the unchanged K
execution validator rejects by design. That validator is therefore called,
unmodified, for the K-LC1 record and its own move: it binds decision, live
observation, cursor and M. The changed OPEN is then checked here against the
live observation, the premises rebuilt from it, and the recorded look-ahead
arithmetic. No hypothetical probability call is made while validating, and
nothing claims the old validator authorised the changed OPEN.

``allow_guess`` is an explicit experimental boundary of this runner: when it
is False a guess proposal is still computed and validated under the same
limits, but never reaches the Engine, and the run stops with GUESS_BLOCKED.
It is not the product's Live guess switch and proves nothing about it.
Evidence lives in the returned in-memory records only. Experimental copy only.
"""

from dataclasses import dataclass

from core_engine import Action, CellState, GameStatus
from experiments.program_d3_lookahead_policy import (
    CANDIDATE_DEFINITION, CANDIDATE_ID, FORCED_CATEGORY, FORCED_FIRST, IMPLEMENTATION_SCOPE,
    TIE_CATEGORY, TIE_LOOKAHEAD, LookaheadEvidence, LookaheadSelection, _decide,
    _premises_for_state, _same, select_lookahead_policy, validate_lookahead_selection,
)
from experiments.program_k_capability import KLocalSession
from experiments.program_k_runner import (
    KActionTrace, _EffectArchive, _PublicEnginePort, _public_grid, _require,
    _valid_move, _validate_progress, validate_k_p0_execution,
)
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, load_timing_table, validate_timing_table


STOP_REASONS = ("TERMINAL", "GUESS_BLOCKED")


@dataclass(frozen=True)
class LookaheadActionTrace:
    """One executed input. ``action.selection`` is None for a changed target.

    ``evidence`` is the pre-input evidence of a guess input (None otherwise).
    """

    action: KActionTrace
    choice: LookaheadSelection | None
    evidence: LookaheadEvidence | None

    @property
    def policy_id(self):
        return CANDIDATE_ID


@dataclass(frozen=True)
class BlockedLookaheadGuess:
    """A validated guess proposal that was NOT sent to the Engine."""

    input_index: int
    cursor: tuple[int, int]
    choice: LookaheadSelection
    evidence: LookaheadEvidence


@dataclass(frozen=True)
class LookaheadRunResult:
    status: GameStatus
    stop_reason: str
    traces: tuple[LookaheadActionTrace, ...]
    final_M: frozenset[tuple[int, int]]
    blocked: BlockedLookaheadGuess | None

    @property
    def policy_id(self):
        return CANDIDATE_ID

    @property
    def policy_definition(self):
        return CANDIDATE_DEFINITION

    @property
    def implementation_scope(self):
        return IMPLEMENTATION_SCOPE

    @property
    def moves(self):
        return tuple(t.action.move for t in self.traces)

    @property
    def total_modeled_us(self):
        return sum(t.action.modeled_action_us for t in self.traces)

    @property
    def added_hypothetical_calls(self):
        """D3's additional calls of the executed inputs and of a blocked proposal."""
        choices = [t.choice for t in self.traces if t.choice is not None]
        if self.blocked is not None:
            choices.append(self.blocked.choice)
        return sum(choice.actual_calls for choice in choices)


def validate_lookahead_execution(observation, move, *, status, num_mines, cursor, current_mines,
                                 decision=None, choice=None, table=None, initial=False) -> None:
    """Validate one input from actual pre-input public state; execute nothing.

    ``table`` is the runner's already authenticated timing table. The unchanged
    K validator runs first on the K-LC1 record and ITS move. No probability
    call is made here: the recorded number outcomes are re-checked
    arithmetically against premises rebuilt from the live state.
    """
    if initial is True:
        _require(choice is None, "LOOKAHEAD_EXECUTION", "The canonical initial OPEN has no choice record.")
        validate_k_p0_execution(observation, move, status=status, num_mines=num_mines, cursor=cursor,
                                current_mines=current_mines, decision=None, selection=None, initial=True)
        return
    _require(initial is False and type(choice) is LookaheadSelection and table is not None,
             "LOOKAHEAD_EXECUTION", "A fresh stage-2 choice record and the timing table are required.")
    validate_lookahead_selection(choice, table)
    _require(choice.inner.native.evidence is decision,
             "LOOKAHEAD_EXECUTION", "The choice must reference this fresh decision.")
    kept = choice.inner.selected
    # Unchanged K validator on the K-LC1 record and ITS move: status, live
    # observation, cursor, M, accounting, exact evidence and continuation bindings.
    validate_k_p0_execution(observation, kept.move, status=status, num_mines=num_mines, cursor=cursor,
                            current_mines=current_mines, decision=decision, selection=kept)
    # The actual input is passed apart from the K-LC1 move validated above: its own type, action and
    # coordinates (exact int, inside the board) are checked here with the accepted check, before it is
    # used as an index or a cost-table key. An equal value of another type is not accepted.
    _require(_valid_move(move, len(observation[0]), len(observation)) and move == choice.move,
             "LOOKAHEAD_EXECUTION", "Physical input must equal the recorded choice.")
    if decision.continuation != "EXACT_GUESS":
        _require(move == kept.move and not choice.target_changed and choice.evidence is None
                 and choice.premises is None and not choice.lookaheads,
                 "LOOKAHEAD_EXECUTION", "A certainty decision executes the K-LC1 move unchanged.")
        return
    # Premises rebuilt from the LIVE observation, the owner's current M and the actual cursor.
    current = _public_grid(observation, num_mines)
    live = _premises_for_state(current, current_mines, num_mines, decision.phase_e,
                               decision.guess_target, cursor)
    _require(_same(live, choice.premises), "LOOKAHEAD_EXECUTION",
             "Recorded premises are not the actual current state.")
    # Pair geometry, world-count agreement, candidate set, limits, recorded
    # number outcomes, rank and target again, from the live premises.
    expected = _decide(live, table, choice.inner, recorded=choice.lookaheads)
    _require(_same(expected, choice, choice.inner), "LOOKAHEAD_EXECUTION",
             "Judgement, look-ahead, rank or target is not valid for the actual current state.")
    target = (move.x, move.y)
    _require(choice.evidence is not None and choice.evidence.target == target == choice.target,
             "LOOKAHEAD_EXECUTION", "Evidence must describe the actual target.")
    if not choice.target_changed:
        _require(move == kept.move, "LOOKAHEAD_EXECUTION", "An unchanged target executes the K-LC1 move.")
        return
    _require(move.action is Action.OPEN and current[target[1]][target[0]] == CellState.HIDDEN
             and target in decision.after.U and target not in current_mines
             and target in choice.lookahead_cells,
             "LOOKAHEAD_EXECUTION",
             "A changed guess needs one OPEN on an actual HIDDEN unresolved cell of the candidate set.")
    _require((choice.selection_reason, choice.category) in (
        (FORCED_FIRST, FORCED_CATEGORY), (TIE_LOOKAHEAD, TIE_CATEGORY)),
             "LOOKAHEAD_EXECUTION", "A changed target needs a forced-pair or tie look-ahead reason.")


def run_s3d3_stage2(engine, *, allow_guess, table=None, capture_effects: bool = False,
                    observer=None) -> LookaheadRunResult:
    """Fresh canonical game. No resume, retries or suffix execution.

    With ``allow_guess`` False the run stops, still PLAYING, right before the
    first guess input; that proposal is returned as ``blocked`` and is not an
    executed input. Any error of a decision propagates with no input sent.
    """
    _require(type(allow_guess) is bool, "GUESS_OPTION", "An explicit boolean guess permission is required.")
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
            choice = select_lookahead_policy(decision, cursor, table)
            move, category = choice.move, choice.category
        current = port.observe_playing()
        validate_lookahead_execution(
            current, move, status=port.status(), num_mines=port.num_mines, cursor=cursor,
            current_mines=session.M, decision=decision, choice=choice, table=table, initial=initial,
        )
        evidence = None if choice is None else choice.evidence
        if evidence is not None and not allow_guess:
            # Guess OFF: nothing is sent. The proposal is not an input or a click.
            return LookaheadRunResult(port.status(), "GUESS_BLOCKED", tuple(traces), session.M,
                                      BlockedLookaheadGuess(len(traces), cursor, choice, evidence))
        preinput_M = session.M
        cost = action_cost(table, cursor, (move.x, move.y))
        port.apply(move)
        status_after = port.status()  # FIRST access after physical input.
        after_playing = None
        if status_after is GameStatus.PLAYING:
            after_playing = port.observe_playing()
            _validate_progress(current, after_playing, move)
        effect = None
        if archive is not None:
            effect = archive.capture(
                current, move, after_playing=after_playing, status_after=status_after,
                input_index=len(traces), cursor_before=cursor, modeled_action_us=cost,
            )
        selection = None if choice is None or choice.target_changed else choice.inner.selected
        record = LookaheadActionTrace(KActionTrace(
            len(traces), move, category, selection, cursor, cost, status_after,
            M_before, preinput_M, public_effect=effect,
            public_effect_status="CAPTURED" if effect is not None else "NOT_EVALUATED",
        ), choice, evidence)
        traces.append(record)
        decision = choice = evidence = None
        if observer is not None:
            observer(record)
        if status_after is not GameStatus.PLAYING:
            return LookaheadRunResult(status_after, "TERMINAL", tuple(traces), session.M, None)
        observation, cursor = after_playing, (move.x, move.y)
