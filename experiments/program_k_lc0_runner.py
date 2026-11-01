"""Minimal experimental K-LC0 runner; CONTROL uses native g on this same path.

No V1/K-P0 source injection. Reuse the accepted public port, session, physical
validator, progress and archival boundary. Every decision expires after its
first input. The optional observer receives completed immutable archives only.
"""

from dataclasses import dataclass

from core_engine import Action, GameStatus
from experiments.program_k_capability import KLocalSession
from experiments.program_k_lc0_policy import (
    CONTROL_ID, POLICY_DEFINITION, POLICY_ID, DistanceSelection,
    select_distance_policy, validate_distance_selection,
)
from experiments.program_k_runner import (
    KActionTrace, _EffectArchive, _PublicEnginePort, _require,
    _validate_progress, validate_k_p0_execution,
)
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, load_timing_table, validate_timing_table


@dataclass(frozen=True)
class DistanceActionTrace:
    action: KActionTrace
    choice: DistanceSelection | None


@dataclass(frozen=True)
class DistanceRunResult:
    policy_id: str
    status: GameStatus
    traces: tuple[DistanceActionTrace, ...]
    final_M: frozenset[tuple[int, int]]
    policy_definition: str = POLICY_DEFINITION

    @property
    def moves(self):
        return tuple(t.action.move for t in self.traces)

    @property
    def total_modeled_us(self):
        return sum(t.action.modeled_action_us for t in self.traces)


def run_k_lc0(engine, *, table=None, control: bool = False,
              capture_effects: bool = False, observer=None) -> DistanceRunResult:
    """Fresh canonical game; no resume, retries, standalone FLAG or suffix input."""
    _require(type(control) is bool, "POLICY_OPTION", "CONTROL must be boolean.")
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
        decision = selection = choice = None
        if initial:
            move = SimpleMove(Action.OPEN, 0, 0)
            category = "POLICY_INITIAL_OPEN"
        else:
            decision = session.analyze_decision(observation, status=GameStatus.PLAYING)
            choice = select_distance_policy(decision, cursor, table, control=control)
            validate_distance_selection(choice)
            selection = choice.selected
            move, category = selection.move, selection.category
        current = port.observe_playing()
        status_before = port.status()
        current_mines = session.M
        validate_k_p0_execution(
            current, move, status=status_before, num_mines=port.num_mines,
            cursor=cursor, current_mines=current_mines, decision=decision,
            selection=selection, initial=initial,
        )
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
        record = DistanceActionTrace(KActionTrace(
            len(traces), move, category, selection, cursor, cost, status_after,
            M_before, preinput_M, public_effect=effect,
            public_effect_status="CAPTURED" if effect is not None else "NOT_EVALUATED",
        ), choice)
        traces.append(record)
        decision = selection = choice = None
        if observer is not None:
            observer(record)
        if status_after is not GameStatus.PLAYING:
            return DistanceRunResult(CONTROL_ID if control else POLICY_ID,
                                     status_after, tuple(traces), session.M)
        observation = after_playing
        cursor = (move.x, move.y)
