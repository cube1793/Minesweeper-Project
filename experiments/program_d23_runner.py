"""Thin execution loop of the experimental composition S3D23-A over the unchanged K seams.

Same order as run_k_lc1, the S3D2-A runner and the diagnosing S3D3-A runner:

    K decision (one session analysis) -> ONE K-LC1 selection -> its one branch
    -> execution validation of that branch
    -> [guess decision only] pair mirror diagnosis + its validation
    -> guess OFF block -> input -> status FIRST -> progress check
    -> [applied opening, still PLAYING] guaranteed-set check

Each decision, its branch record and its diagnosis expire after the first
actual input; only session M persists. There is one session; nothing is
injected into it and nothing is resumed.

Validation is the accepted one of the branch, called unchanged: for a certain
decision ``validate_opening_execution``, for a guess decision
``validate_lookahead_execution``. Each of them first calls the unchanged K
execution validator for the K-LC1 record and ITS move (which binds decision,
live observation, cursor and M) and then checks the actual input. Nothing
claims the old validator authorised a changed input.

``allow_guess`` is the experimental boundary of the S3D3-A runners: when it is
False a guess proposal is still selected, validated and DIAGNOSED, never
reaches the Engine, and the run stops with GUESS_BLOCKED. Guess OFF does not
skip the diagnosis. Certain inputs (including an applied opening) are not
affected by it. Any error of a decision, of a validation, of a diagnosis or of
the guaranteed-set check propagates; nothing falls back to the K-LC1 input.
Evidence lives in the returned in-memory records only. Experimental copy only.
"""

from dataclasses import dataclass

from core_engine import Action, GameStatus
from experiments.program_d2_opening_policy import APPLIED_CATEGORY
from experiments.program_d2_opening_runner import validate_opening_effect, validate_opening_execution
from experiments.program_d23_policy import (
    BRANCH_CERTAIN, BRANCH_GUESS, COMPOSITION_DEFINITION, COMPOSITION_ID, CombinedSelection,
    check_combined_shape, select_combined_policy,
)
from experiments.program_d3_lookahead_policy import LookaheadEvidence
from experiments.program_d3_lookahead_runner import validate_lookahead_execution
from experiments.program_d3_pseudo_diagnosis import PseudoDiagnosis
from experiments.program_d3_pseudo_runner import diagnose_before_input
from experiments.program_k_capability import KLocalSession
from experiments.program_k_runner import (
    KActionTrace, _EffectArchive, _PublicEnginePort, _require, _validate_progress, validate_k_p0_execution,
)
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, load_timing_table, validate_timing_table


STOP_REASONS = ("TERMINAL", "GUESS_BLOCKED")
GUARANTEE_STATUSES = ("NOT_APPLICABLE", "PASS", "NOT_EVALUATED_TERMINAL")


@dataclass(frozen=True)
class CombinedActionTrace:
    """One executed input.

    ``action.selection`` is None when the actual input differs from the K-LC1
    input (an applied opening or a changed guess target). ``evidence`` is the
    pre-input evidence of a guess input (None otherwise). ``guarantee_status``
    belongs to an applied opening (NOT_APPLICABLE otherwise).
    """

    action: KActionTrace
    choice: CombinedSelection | None
    evidence: LookaheadEvidence | None
    guarantee_status: str

    @property
    def policy_id(self):
        return COMPOSITION_ID


@dataclass(frozen=True)
class BlockedCombinedGuess:
    """A validated and diagnosed guess proposal that was NOT sent to the Engine."""

    input_index: int
    cursor: tuple
    choice: CombinedSelection
    evidence: LookaheadEvidence


@dataclass(frozen=True)
class CombinedRunResult:
    """Result of one run. ``diagnoses`` has one entry per executed input: the diagnosis fixed
    before a guess input, None before any other input. ``blocked_diagnosis`` belongs to a guess
    proposal that was not sent. A diagnosis is no game result, selection reason or classification."""

    status: GameStatus
    stop_reason: str
    traces: tuple
    final_M: frozenset
    blocked: BlockedCombinedGuess | None
    diagnoses: tuple
    blocked_diagnosis: PseudoDiagnosis | None

    @property
    def policy_id(self):
        return COMPOSITION_ID

    @property
    def policy_definition(self):
        return COMPOSITION_DEFINITION

    @property
    def moves(self):
        return tuple(t.action.move for t in self.traces)

    @property
    def total_modeled_us(self):
        return sum(t.action.modeled_action_us for t in self.traces)

    @property
    def openings_applied(self):
        """Input numbers of the applied S3D2-A openings."""
        return tuple(t.action.input_index for t in self.traces
                     if t.choice is not None and t.choice.branch == BRANCH_CERTAIN
                     and t.choice.opening.applied is not None)

    @property
    def added_hypothetical_calls(self):
        """S3D3-A's additional look-ahead calls of the executed guess inputs and of a blocked proposal."""
        guesses = [t.choice.guess for t in self.traces if t.choice is not None and t.choice.branch == BRANCH_GUESS]
        if self.blocked is not None:
            guesses.append(self.blocked.choice.guess)
        return sum(guess.actual_calls for guess in guesses)

    @property
    def pseudo_calls(self):
        """Conditional kernel calls of this run's diagnoses (executed inputs and a blocked proposal)."""
        made = [d for d in self.diagnoses if d is not None]
        if self.blocked_diagnosis is not None:
            made.append(self.blocked_diagnosis)
        return sum(d.actual_calls for d in made)


def validate_combined_execution(observation, move, *, status, num_mines, cursor, current_mines,
                                decision=None, choice=None, table=None, initial=False) -> None:
    """Validate one input from actual pre-input public state; execute nothing.

    The structure of the combined record is checked here; the record and the
    actual input are then validated by the accepted execution validator of the
    branch, which itself runs the unchanged K validator on the K-LC1 record
    and its own move. No probability call is made.
    """
    if initial is True:
        _require(choice is None, "COMBINED_EXECUTION", "The canonical initial OPEN has no choice record.")
        validate_k_p0_execution(observation, move, status=status, num_mines=num_mines, cursor=cursor,
                                current_mines=current_mines, decision=None, selection=None, initial=True)
        return
    _require(initial is False and type(choice) is CombinedSelection and table is not None,
             "COMBINED_EXECUTION", "A fresh combined choice record and the timing table are required.")
    check_combined_shape(choice)
    _require(choice.inner.native.evidence is decision,
             "COMBINED_EXECUTION", "The choice must reference this fresh decision.")
    _require((decision.continuation == "EXACT_GUESS") == (choice.branch == BRANCH_GUESS),
             "COMBINED_EXECUTION", "The branch is not that of this decision.")
    _require(type(move) is SimpleMove and move == choice.move,
             "COMBINED_EXECUTION", "Physical input must equal the recorded choice.")
    common = dict(status=status, num_mines=num_mines, cursor=cursor, current_mines=current_mines,
                  decision=decision, table=table)
    if choice.branch == BRANCH_GUESS:
        validate_lookahead_execution(observation, move, choice=choice.guess, **common)
    else:
        validate_opening_execution(observation, move, choice=choice.opening, **common)


def run_d23(engine, *, allow_guess, table=None, capture_effects: bool = False,
            observer=None) -> CombinedRunResult:
    """Fresh canonical game. No resume, retries or suffix execution.

    With ``allow_guess`` False the run stops, still PLAYING, right before the
    first guess input; that proposal is diagnosed like an actual guess, is
    returned as ``blocked`` and is not an executed input. Any error of a
    decision, of its validation, of its diagnosis or of the guaranteed-set
    check propagates with no further input.
    """
    _require(type(allow_guess) is bool, "GUESS_OPTION", "An explicit boolean guess permission is required.")
    _require(type(capture_effects) is bool, "ARCHIVE_OPTION", "Expected boolean capture option.")
    port = _PublicEnginePort(engine)
    archive = _EffectArchive(engine) if capture_effects else None
    table = load_timing_table() if table is None else validate_timing_table(table)
    session = KLocalSession(port.width, port.height, port.num_mines)
    cursor, observation, traces, diagnoses = (0, 0), port.observe_playing(), [], []
    while True:
        initial, M_before = not traces, session.M
        decision = choice = None
        if initial:
            move, category = SimpleMove(Action.OPEN, 0, 0), "POLICY_INITIAL_OPEN"
        else:
            decision = session.analyze_decision(observation, status=GameStatus.PLAYING)
            choice = select_combined_policy(decision, cursor, table)
            move, category = choice.move, choice.category
        current = port.observe_playing()
        validate_combined_execution(
            current, move, status=port.status(), num_mines=port.num_mines, cursor=cursor,
            current_mines=session.M, decision=decision, choice=choice, table=table, initial=initial,
        )
        guess = choice is not None and choice.branch == BRANCH_GUESS
        evidence = choice.guess.evidence if guess else None
        applied = choice.opening.applied if choice is not None and choice.branch == BRANCH_CERTAIN else None
        _require(not guess or evidence is not None,
                 "COMBINED_EXECUTION", "A guess decision needs its pre-input evidence.")
        # Only for a guess decision, after the execution validation, before the guess OFF block and
        # before the input. Guess OFF does not skip it. An error here sends nothing.
        diagnosis = diagnose_before_input(choice.guess) if guess else None
        if guess and not allow_guess:
            # Guess OFF: nothing is sent. The proposal is not an input or a click.
            return CombinedRunResult(port.status(), "GUESS_BLOCKED", tuple(traces), session.M,
                                     BlockedCombinedGuess(len(traces), cursor, choice, evidence),
                                     tuple(diagnoses), diagnosis)
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
        selection = None if choice is None else choice.selected
        _require(applied is None or category == APPLIED_CATEGORY,
                 "COMBINED_EXECUTION", "Applied opening must carry its own category.")
        record = CombinedActionTrace(KActionTrace(
            len(traces), move, category, selection, cursor, cost, status_after,
            M_before, preinput_M, public_effect=effect,
            public_effect_status="CAPTURED" if effect is not None else "NOT_EVALUATED",
        ), choice, evidence, guarantee)
        traces.append(record)
        diagnoses.append(diagnosis)
        decision = choice = evidence = applied = diagnosis = None
        if observer is not None:
            observer(record)
        if status_after is not GameStatus.PLAYING:
            return CombinedRunResult(status_after, "TERMINAL", tuple(traces), session.M, None,
                                     tuple(diagnoses), None)
        observation, cursor = after_playing, (move.x, move.y)
