"""S3D23-A execution loop with ONE more inserted step: the linked resolution diagnosis before a guess input.

The accepted combined runner (``program_d23_runner.run_d23``) has no hook
before an input and is not modified. This loop calls the same unchanged parts
in the same order -

    K decision (one session analysis) -> ONE combined selection -> its one branch
    -> the accepted combined execution validation
    -> [guess decision only] pair mirror diagnosis + its validation        (as run_d23)
    -> [guess decision only] linked diagnosis + its validation + binding   (the one new step)
    -> guess OFF block -> input -> status FIRST -> progress check
    -> [applied opening, still PLAYING] guaranteed-set check

- and returns the real ``CombinedRunResult`` of that game, untouched in type
and content, beside the linked diagnoses. The first input, certain inputs, an
applied opening, the stop right after a terminal status, the cursor update and
the observer call are those of ``run_d23``; they get no linked diagnosis.

The linked diagnosis selects nothing and authorises nothing: target, reason,
category and classification are those of the selection record. It does add up
to 54 exact calls per guess decision, and when the diagnosis, its validation
or its binding fails the run stops BEFORE that input reaches the Engine. That
means only that the diagnosis required by this experiment was not completed;
the original exception propagates unchanged and is never turned into a
verdict, a skip, "no link" or a fallback. Guess OFF does not skip the
diagnosis and the diagnosis never lifts the guess OFF block.

Results live in the returned in-memory value only: no file format, storage,
save path or reader exists here. The accepted record converters take
``base_result``; the new result type is not a ``CombinedRunResult`` and is
refused by them. Nothing hidden is passed to the policy or to a diagnosis;
the Engine is reached through the K runner's public port alone.
Experimental copy only.
"""

from dataclasses import dataclass

from core_engine import Action, GameStatus
from experiments.program_d2_opening_policy import APPLIED_CATEGORY
from experiments.program_d2_opening_runner import validate_opening_effect
from experiments.program_d23_policy import BRANCH_CERTAIN, BRANCH_GUESS, CombinedSelection, select_combined_policy
from experiments.program_d23_runner import (
    BlockedCombinedGuess, CombinedActionTrace, CombinedRunResult, validate_combined_execution,
)
from experiments.program_d3_link_diagnosis import (
    SOURCE_RECORD, UNSUPPORTED, LinkDiagnosis, diagnose_links, validate_link_diagnosis,
)
from experiments.program_d3_lookahead_policy import LookaheadSelection
from experiments.program_d3_pseudo_runner import diagnose_before_input
from experiments.program_k_capability import KLocalSession
from experiments.program_k_runner import (
    KActionTrace, _EffectArchive, _PublicEnginePort, _require, _validate_progress,
)
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, load_timing_table, validate_timing_table


@dataclass(frozen=True)
class LinkedRunResult:
    """The unchanged combined run result and, apart from it, the linked diagnoses.

    ``link_diagnoses`` has one entry per executed input: the diagnosis fixed
    before a guess input, None before any other input (no diagnosis exists for
    the first OPEN and for certain inputs). ``blocked_link_diagnosis`` belongs
    to a guess proposal that was not sent (guess OFF). None of them is a game
    result, a selection reason or a loss classification.
    """

    base_result: CombinedRunResult
    link_diagnoses: tuple
    blocked_link_diagnosis: LinkDiagnosis | None

    @property
    def link_calls(self) -> int:
        """Exact calls of this run's linked diagnoses (executed inputs and a blocked proposal)."""
        made = [diagnosis for diagnosis in self.link_diagnoses if diagnosis is not None]
        if self.blocked_link_diagnosis is not None:
            made.append(self.blocked_link_diagnosis)
        return sum(diagnosis.actual_calls for diagnosis in made)

    @property
    def link_states(self) -> tuple:
        """The plan status before each executed input; UNSUPPORTED where no diagnosis exists."""
        return tuple(UNSUPPORTED if diagnosis is None else diagnosis.plan.status
                     for diagnosis in self.link_diagnoses)


def link_before_input(choice, move) -> LinkDiagnosis:
    """Linked diagnosis, its validation and its binding for ONE guess choice that has already passed
    the combined execution validation. Authorises no input.

    The diagnosis is validated against the guess record of THIS choice, so a diagnosis of another
    decision or of another target is refused here, before the input.
    """
    _require(type(choice) is CombinedSelection and choice.branch == BRANCH_GUESS
             and type(choice.guess) is LookaheadSelection and choice.guess.evidence is not None,
             "LINK_EXECUTION", "Expected the combined choice record of a guess decision.")
    _require(type(move) is SimpleMove and move == choice.move,
             "LINK_EXECUTION", "The input must be the recorded input of this choice.")
    diagnosis = diagnose_links(choice.guess)
    _require(type(diagnosis) is LinkDiagnosis, "LINK_EXECUTION", "A guess decision needs its linked diagnosis.")
    validate_link_diagnosis(diagnosis, choice.guess)
    _require(diagnosis.premise_source == SOURCE_RECORD and diagnosis.actual_target == (move.x, move.y),
             "LINK_EXECUTION", "The linked diagnosis is not that of this input.")
    return diagnosis


def run_d23_linked(engine, *, allow_guess, table=None, capture_effects: bool = False,
                   observer=None) -> LinkedRunResult:
    """Fresh canonical game, exactly as ``run_d23``, plus the linked diagnosis of each guess decision.

    With ``allow_guess`` False the run stops, still PLAYING, right before the
    first guess input; that proposal gets both diagnoses like an actual guess
    and is not an executed input. Any error of a decision, of its validation,
    of a diagnosis or of the guaranteed-set check propagates with no further
    input. No resume, retries or suffix execution.
    """
    _require(type(allow_guess) is bool, "GUESS_OPTION", "An explicit boolean guess permission is required.")
    _require(type(capture_effects) is bool, "ARCHIVE_OPTION", "Expected boolean capture option.")
    port = _PublicEnginePort(engine)
    archive = _EffectArchive(engine) if capture_effects else None
    table = load_timing_table() if table is None else validate_timing_table(table)
    session = KLocalSession(port.width, port.height, port.num_mines)
    cursor, observation, traces, diagnoses, links = (0, 0), port.observe_playing(), [], [], []
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
        # before the input. Guess OFF skips neither diagnosis. An error here sends nothing.
        diagnosis = diagnose_before_input(choice.guess) if guess else None
        link = link_before_input(choice, move) if guess else None
        if guess and not allow_guess:
            # Guess OFF: nothing is sent. The proposal is not an input or a click.
            return LinkedRunResult(
                CombinedRunResult(port.status(), "GUESS_BLOCKED", tuple(traces), session.M,
                                  BlockedCombinedGuess(len(traces), cursor, choice, evidence),
                                  tuple(diagnoses), diagnosis),
                tuple(links), link)
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
        links.append(link)
        decision = choice = evidence = applied = diagnosis = link = None
        if observer is not None:
            observer(record)
        if status_after is not GameStatus.PLAYING:
            return LinkedRunResult(
                CombinedRunResult(status_after, "TERMINAL", tuple(traces), session.M, None,
                                  tuple(diagnoses), None),
                tuple(links), None)
        observation, cursor = after_playing, (move.x, move.y)
