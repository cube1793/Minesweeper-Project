"""Thin K-LC1 execution loop using the accepted K public/physical/archive seams.

No selector injection into accepted source. Each decision expires after its
first actual input; only session M persists. Observer receives completed archives.
"""

from dataclasses import dataclass

from core_engine import Action, GameStatus
from experiments.program_k_capability import KLocalSession
from experiments.program_k_lc1_policy import (
    POLICY_DEFINITION, POLICY_ID, SingletonSelection,
    select_singleton_policy, validate_singleton_selection,
)
from experiments.program_k_runner import (
    KActionTrace, _EffectArchive, _PublicEnginePort, _require,
    _validate_progress, validate_k_p0_execution,
)
from simple_algorithm import SimpleMove
from stage3_physical import action_cost, load_timing_table, validate_timing_table


@dataclass(frozen=True)
class SingletonActionTrace:
    action: KActionTrace
    choice: SingletonSelection | None

    @property
    def policy_id(self):
        return POLICY_ID


@dataclass(frozen=True)
class SingletonRunResult:
    status: GameStatus
    traces: tuple[SingletonActionTrace, ...]
    final_M: frozenset[tuple[int, int]]

    @property
    def policy_id(self):
        return POLICY_ID

    @property
    def policy_definition(self):
        return POLICY_DEFINITION

    @property
    def moves(self):
        return tuple(t.action.move for t in self.traces)

    @property
    def total_modeled_us(self):
        return sum(t.action.modeled_action_us for t in self.traces)


def run_k_lc1(engine, *, table=None, capture_effects: bool = False,
              observer=None) -> SingletonRunResult:
    """Fresh canonical game. No CONTROL, resume, retries or suffix execution."""
    _require(type(capture_effects) is bool, "ARCHIVE_OPTION", "Expected boolean capture option.")
    port = _PublicEnginePort(engine)
    archive = _EffectArchive(engine) if capture_effects else None
    table = load_timing_table() if table is None else validate_timing_table(table)
    session = KLocalSession(port.width, port.height, port.num_mines)
    cursor, observation, traces = (0, 0), port.observe_playing(), []
    while True:
        initial, M_before = not traces, session.M
        decision = selection = choice = None
        if initial:
            move, category = SimpleMove(Action.OPEN, 0, 0), "POLICY_INITIAL_OPEN"
        else:
            decision = session.analyze_decision(observation, status=GameStatus.PLAYING)
            choice = select_singleton_policy(decision, cursor, table)
            validate_singleton_selection(choice)
            selection = choice.selected
            move, category = selection.move, selection.category
        current = port.observe_playing()
        validate_k_p0_execution(
            current, move, status=port.status(), num_mines=port.num_mines,
            cursor=cursor, current_mines=session.M, decision=decision,
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
        record = SingletonActionTrace(KActionTrace(
            len(traces), move, category, selection, cursor, cost, status_after,
            M_before, preinput_M, public_effect=effect,
            public_effect_status="CAPTURED" if effect is not None else "NOT_EVALUATED",
        ), choice)
        traces.append(record)
        decision = selection = choice = None
        if observer is not None:
            observer(record)
        if status_after is not GameStatus.PLAYING:
            return SingletonRunResult(status_after, tuple(traces), session.M)
        observation, cursor = after_playing, (move.x, move.y)
