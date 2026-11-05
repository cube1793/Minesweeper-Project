"""GUI-only immutable layout and completed Live records; never policy input."""

from dataclasses import dataclass
from hashlib import sha256
import json

from core_engine import GameStatus
from replay_model import ReplayBoard, ReplayData


@dataclass(frozen=True)
class FixedLayout:
    width: int
    height: int
    num_mines: int
    mines: frozenset

    def __post_init__(self):
        board = ReplayBoard(self.width, self.height, self.num_mines, self.mines)
        object.__setattr__(self, 'mines', board.mine_positions)

    @classmethod
    def from_finished_engine(cls, engine):
        if engine.status not in (GameStatus.WON, GameStatus.LOST):
            raise ValueError('Same-board replay requires a finished Live game.')
        snapshot = engine.get_board_snapshot()
        if not snapshot.mines_placed:
            raise ValueError('The finished layout is not available.')
        return cls(snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines)

    @classmethod
    def from_replay_board(cls, board):
        return cls(board.width, board.height, board.num_mines, board.mine_positions)

    def matches(self, snapshot):
        return (snapshot.mines_placed and
                (snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines)
                == (self.width, self.height, self.num_mines, self.mines))

    @property
    def fingerprint(self):
        value = [self.width, self.height, self.num_mines, sorted(self.mines)]
        return sha256(json.dumps(value, separators=(',', ':')).encode('ascii')).hexdigest()

    def reset_engine(self, engine):
        engine.reset_with_mines(self.width, self.height, self.num_mines, self.mines)
        if not self.matches(engine.get_board_snapshot()):
            raise ValueError('Fixed layout changed while initializing the new game.')


@dataclass(frozen=True)
class FixedOrigin:
    game_id: str
    layout: FixedLayout


@dataclass(frozen=True)
class CompletedLiveGame:
    game_id: str
    status: str
    layout: FixedLayout
    replay: ReplayData
    evidence_json: str

    @classmethod
    def capture(cls, ui, layout, replay):
        if FixedLayout.from_finished_engine(ui.engine) != layout:
            raise ValueError('Completed Live game differs from the original layout.')
        if (replay.board.width, replay.board.height, replay.board.num_mines,
                replay.board.mine_positions) != (layout.width, layout.height,
                                                  layout.num_mines, layout.mines):
            raise ValueError('Completed Replay differs from the original layout.')
        evidence = dict(inputs=ui.live_input_records, actions=ui.live_action_records,
                        owners=[r for r in ui.live_owner_records if r['game_id'] == ui._live_game_id],
                        totals=ui.live_auto_totals, counters=ui.engine.get_counter_snapshot(),
                        elapsed=ui.engine.get_elapsed_time())
        return cls(ui._live_game_id, ui.engine.status.name, layout, replay,
                   json.dumps(evidence, ensure_ascii=False, allow_nan=False, sort_keys=True))
