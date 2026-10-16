"""Pure Human admission for the Same-board Comparison contract (Slice 1).

The original Replay is the sole action/Mouse Trace authority. Admission proves
execution to terminal state on its fixed layout, not historical Human provenance.
No solver, physical model, worker, persistence or presentation is involved.
"""

from dataclasses import dataclass, field

from benchmark_board import calculate_board_fingerprint
from core_engine import GameStatus
from replay_model import ACTION_OPEN, SOURCE_HUMAN, ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer


# (Replay action, x, y): declarations of the later runs' required first inputs,
# not executed actions or synthetic Replay events (which would need timestamps).
STAGE2_CANONICAL_FIRST_ACTION = (ACTION_OPEN, 0, 0)
STAGE3_CANONICAL_FIRST_ACTION = (ACTION_OPEN, 0, 0)


class ComparisonAdmissionError(ValueError):
    """Comparison rejection only; ordinary Replay validity is unchanged."""


@dataclass(frozen=True)
class ComparisonLayout:
    """Exact layout identity, retaining the immutable board without copying it.

    Equality includes ReplayBoard's dimensions, mine count and exact mine set,
    plus the recomputed canonical fingerprint. No benchmark provenance is implied.
    Callers cannot supply a claimed fingerprint in place of recomputation.
    """

    board: ReplayBoard
    board_fingerprint: str = field(init=False)

    def __post_init__(self):
        if not isinstance(self.board, ReplayBoard):
            raise ComparisonAdmissionError("Comparison layout requires a ReplayBoard.")
        board = self.board
        object.__setattr__(self, "board_fingerprint", calculate_board_fingerprint(
            board.width, board.height, board.num_mines, board.mine_positions,
        ))


def _verify_installed_layout(player: ReplayPlayer, layout: ComparisonLayout) -> None:
    """Check actual Engine layout truth at the reconstruction boundary only."""
    snapshot = player.engine.get_board_snapshot()
    board = layout.board
    fingerprint = calculate_board_fingerprint(
        snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines,
    )
    if (
        not snapshot.mines_placed
        or (snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines)
        != (board.width, board.height, board.num_mines, board.mine_positions)
        or fingerprint != layout.board_fingerprint
    ):
        raise ComparisonAdmissionError("Reconstructed layout differs from the Human Replay.")


@dataclass(frozen=True)
class HumanComparisonContext:
    """Admit a declared full-game Human Replay and retain immutable facts.

    Construction requires both ``source_type == SOURCE_HUMAN`` as a necessary
    metadata eligibility condition and ``declared_full_game_human is True`` as
    explicit caller intent. Neither proves exclusively-Human provenance: a
    Human-labeled Replay may historically contain Auto input. Successful
    full-stream reconstruction proves structural execution/completion, not
    historical provenance. Existing Replay validation owns numeric/event
    structure; comparison adds eligibility, dimension, completion and
    post-terminal checks without changing ordinary Replay use.

    Event indices are zero-based positions in the original stream, NOT playback
    indices (counts of applied events). Terminal observation is a tuple of rows
    from Engine.get_observation(), not a second stream or a mutable/live engine.
    Reconstruction's wall clock is discarded; Replay timestamps stay untouched.
    """

    human_replay: ReplayData
    declared_full_game_human: bool = field(kw_only=True)
    layout: ComparisonLayout = field(init=False)
    terminal_status: GameStatus = field(init=False)
    terminal_observation: tuple[tuple[int, ...], ...] = field(init=False)
    first_open_event_index: int | None = field(init=False)

    def __post_init__(self):
        replay = self.human_replay
        # ReplayData does not enforce these nested model types. Require the
        # immutable authorities rather than accepting mutable duck-typed data.
        if (
            not isinstance(replay, ReplayData)
            or not isinstance(replay.board, ReplayBoard)
            or any(not isinstance(event, ReplayEvent) for event in replay.events)
        ):
            raise ComparisonAdmissionError(
                "Comparison requires ReplayData with ReplayBoard and ReplayEvent instances."
            )
        if replay.source_type != SOURCE_HUMAN:
            raise ComparisonAdmissionError(
                "Comparison requires source_type=SOURCE_HUMAN as metadata eligibility; "
                "a caller declaration cannot override an algorithm or AI source label."
            )
        if self.declared_full_game_human is not True:
            raise ComparisonAdmissionError(
                "Comparison requires declared_full_game_human=True; this is caller intent, "
                "not proof of historical Human provenance."
            )
        board = replay.board
        if not (1 <= board.width <= 30 and 1 <= board.height <= 16):
            raise ComparisonAdmissionError(
                "Comparison dimensions must fit frozen Stage-3 V1: width 1..30, height 1..16."
            )

        layout = ComparisonLayout(board)
        # ReplayPlayer installs the fixed all-HIDDEN layout with reset_with_mines.
        # Step individually: go_to(final) would silently ignore terminal tails.
        player = ReplayPlayer(replay)
        _verify_installed_layout(player, layout)
        first_open_index = None
        for index, event in enumerate(replay.events):
            if player.engine.status in (GameStatus.WON, GameStatus.LOST):
                raise ComparisonAdmissionError(
                    f"Replay event {index} follows terminal event {index - 1} "
                    f"({player.engine.status.name}); event indices are zero-based."
                )
            if first_open_index is None and event.action == ACTION_OPEN:
                first_open_index = index
            player.next()

        if player.engine.status not in (GameStatus.WON, GameStatus.LOST):
            raise ComparisonAdmissionError(
                "Human stream is incomplete: reconstruction did not reach WON or LOST."
            )
        _verify_installed_layout(player, layout)
        object.__setattr__(self, "layout", layout)
        object.__setattr__(self, "terminal_status", player.engine.status)
        object.__setattr__(self, "terminal_observation", tuple(
            tuple(row) for row in player.get_observation()
        ))
        object.__setattr__(self, "first_open_event_index", first_open_index)

    @property
    def terminal_event_index(self) -> int:
        """The first terminal transition, necessarily the last admitted event."""
        return len(self.human_replay.events) - 1

    @property
    def first_event(self) -> ReplayEvent | None:
        """Reference the original first event without normalizing it."""
        return self.human_replay.events[0] if self.human_replay.events else None

    @property
    def first_open_event(self) -> ReplayEvent | None:
        """Reference the first OPEN, including a blocked/wasted OPEN if recorded."""
        index = self.first_open_event_index
        return None if index is None else self.human_replay.events[index]

    @property
    def has_prelude_events(self) -> bool:
        """Any events before the first OPEN (all events if there is no OPEN)."""
        return bool(self.human_replay.events) and self.first_open_event_index != 0

    @property
    def solver_origin_is_mine(self) -> bool:
        """Fixed-layout qualification only, never a solver decision input."""
        return (0, 0) in self.layout.board.mine_positions

    @property
    def matches_canonical_recorded_start(self) -> bool:
        """Event zero is OPEN(0,0) on the reconstructed all-HIDDEN fixed board.

        This does not establish historical placement policy, execution semantics,
        timing authority, exclusively-Human provenance or experimental control.
        A mined origin can match this start and legitimately lose immediately.
        """
        event = self.first_open_event
        return (
            self.first_open_event_index == 0
            and event is not None
            and (event.x, event.y) == (0, 0)
        )
