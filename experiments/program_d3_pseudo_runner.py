"""S3D3-A stage-2 execution loop with ONE inserted step: the pair mirror diagnosis before a guess input.

The accepted stage-2 runner has no hook before an input (its observer is
called after it) and is not modified. This loop therefore calls the same
unchanged parts in the same order -

    K decision -> stage-2 selection -> stage-2 execution validation
    -> [guess decision only] diagnosis + diagnosis validation
    -> guess OFF block -> input

- and returns the stage-2 run result, untouched in type and content, wrapped
together with the diagnoses. The first input, certainty inputs, the stop right
after a terminal status, the cursor update and the observer call are those of
stage 2.

The diagnosis selects nothing and authorises nothing: target, reason, category
and classification are the stage-2 ones. It does add up to 8 conditional
kernel calls per guess decision, and when the diagnosis or its validation
fails the run stops BEFORE that input reaches the Engine. That means only
that the diagnosis required by this experiment was not completed; it is no
statement about the stage-2 selection. The original exception propagates
unchanged and is never turned into a verdict, a skip or a fallback.

Diagnoses live in the returned in-memory result only: no file format, storage
or reader exists here. Nothing hidden is passed to the policy or to the
diagnosis; the Engine is reached through the K runner's public port alone.
Experimental copy only.
"""

from dataclasses import dataclass

from core_engine import Action, GameStatus
from experiments.program_d3_lookahead_policy import LookaheadSelection, select_lookahead_policy
from experiments.program_d3_lookahead_runner import (
    BlockedLookaheadGuess, LookaheadActionTrace, LookaheadRunResult, validate_lookahead_execution,
)
from experiments.program_d3_pseudo_diagnosis import (
    PseudoDiagnosis, diagnose_pseudo, validate_pseudo_diagnosis,
)
from experiments.program_k_capability import KLocalSession
from experiments.program_k_runner import (
    KActionTrace, _EffectArchive, _PublicEnginePort, _require, _validate_progress,
)
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, load_timing_table, validate_timing_table


@dataclass(frozen=True)
class PseudoRunResult:
    """The unchanged stage-2 run result and, apart from it, the diagnoses.

    ``diagnoses`` has one entry per executed input: the diagnosis fixed before
    a guess input, None before any other input. ``blocked_diagnosis`` belongs
    to a guess proposal that was not sent (guess OFF). None of them is a game
    result, a selection reason or a loss classification.
    """

    run: LookaheadRunResult
    diagnoses: tuple
    blocked_diagnosis: PseudoDiagnosis | None

    @property
    def pseudo_calls(self) -> int:
        """Conditional kernel calls of this run's diagnoses (executed inputs and a blocked proposal)."""
        made = [d for d in self.diagnoses if d is not None]
        if self.blocked_diagnosis is not None:
            made.append(self.blocked_diagnosis)
        return sum(d.actual_calls for d in made)


def diagnose_before_input(choice) -> PseudoDiagnosis | None:
    """Diagnosis and its validation for one stage-2 choice that has already passed the
    stage-2 execution validation. None for a certainty decision. Authorises no input."""
    _require(type(choice) is LookaheadSelection, "PSEUDO_EXECUTION", "Expected a stage-2 choice record.")
    if choice.evidence is None:
        return None
    diagnosis = diagnose_pseudo(choice)
    validate_pseudo_diagnosis(diagnosis, choice)
    return diagnosis


def run_s3d3_pseudo(engine, *, allow_guess, table=None, capture_effects: bool = False,
                    observer=None) -> PseudoRunResult:
    """Fresh canonical game, exactly as ``run_s3d3_stage2``, plus the diagnosis of each guess decision.

    With ``allow_guess`` False the run stops, still PLAYING, right before the
    first guess input; the proposal is diagnosed like an actual guess and is
    not an executed input. Any error of a decision or of its diagnosis
    propagates with no input sent.
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
            choice = select_lookahead_policy(decision, cursor, table)
            move, category = choice.move, choice.category
        current = port.observe_playing()
        validate_lookahead_execution(
            current, move, status=port.status(), num_mines=port.num_mines, cursor=cursor,
            current_mines=session.M, decision=decision, choice=choice, table=table, initial=initial,
        )
        evidence = None if choice is None else choice.evidence
        # The one inserted step: only for a guess decision, after the stage-2 validation,
        # before the guess OFF block and before the input. An error here sends nothing.
        diagnosis = None if choice is None else diagnose_before_input(choice)
        if evidence is not None and not allow_guess:
            # Guess OFF: nothing is sent. The proposal is not an input or a click.
            return PseudoRunResult(
                LookaheadRunResult(port.status(), "GUESS_BLOCKED", tuple(traces), session.M,
                                   BlockedLookaheadGuess(len(traces), cursor, choice, evidence)),
                tuple(diagnoses), diagnosis)
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
        diagnoses.append(diagnosis)
        decision = choice = evidence = diagnosis = None
        if observer is not None:
            observer(record)
        if status_after is not GameStatus.PLAYING:
            return PseudoRunResult(
                LookaheadRunResult(status_after, "TERMINAL", tuple(traces), session.M, None),
                tuple(diagnoses), None)
        observation, cursor = after_playing, (move.x, move.y)
