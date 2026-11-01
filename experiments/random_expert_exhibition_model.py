"""Compact, immutable results of NEW exhibition runs; no E1 admission claims.

These types contain public frames, physical inputs and committed logical M only.
They retain no engine, native selection/proof graph or hidden answer reference.
"""

from dataclasses import dataclass
from secrets import randbelow


INDEX_LIMIT = 100_000
HIDDEN, FLAGGED, EXPLODED, MINE, FALSE_FLAG = -2, -3, -4, -5, -6
Coord = tuple[int, int]
Rows = tuple[tuple[int, ...], ...]


def validate_index(index: int) -> int:
    if type(index) is not int or not 0 <= index < INDEX_LIMIT:
        raise ValueError("index는 0..99999 정수여야 합니다 (EXPERT_GENERAL_V1).")
    return index


def draw_index(current: int | None = None) -> int:
    """One uniform draw; only exclude the immediately preceding request."""
    if current is None:
        return randbelow(INDEX_LIMIT)
    validate_index(current)
    value = randbelow(INDEX_LIMIT - 1)
    return value + (value >= current)


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _coord(cell, width, height):
    return (type(cell) is tuple and len(cell) == 2
            and all(type(n) is int for n in cell)
            and 0 <= cell[0] < width and 0 <= cell[1] < height)


def _cells(rows, value):
    return frozenset((x, y) for y, row in enumerate(rows)
                     for x, glyph in enumerate(row) if glyph == value)


@dataclass(frozen=True, slots=True)
class ExhibitionAction:
    index: int
    action: str
    target: Coord
    cursor_before: Coord
    modeled_action_us: int
    status_after: str
    M_before: frozenset[Coord]
    preinput_M: frozenset[Coord]
    safe_cells_opened_delta: int


@dataclass(frozen=True, slots=True)
class ExhibitionFrame:
    index: int
    observation: Rows
    status: str
    cursor: Coord
    cumulative_modeled_us: int
    logical_mines: frozenset[Coord]
    explicit_flags: frozenset[Coord]
    automatic_flags: frozenset[Coord]

    @property
    def hidden_logical_mines(self):
        return frozenset((x, y) for x, y in self.logical_mines
                         if self.observation[y][x] == HIDDEN)


@dataclass(frozen=True, slots=True)
class ExhibitionTrace:
    variant: str
    actions: tuple[ExhibitionAction, ...]
    frames: tuple[ExhibitionFrame, ...]

    def __post_init__(self):
        _need(self.variant in ("V1", "K-P0"), "Unknown exhibition variant.")
        _need(type(self.actions) is tuple and type(self.frames) is tuple
              and 0 < len(self.actions) <= 480 and len(self.frames) == len(self.actions) + 1,
              "Complete N physical inputs require N+1 immutable frames.")
        _need(all(type(f) is ExhibitionFrame for f in self.frames)
              and all(type(a) is ExhibitionAction for a in self.actions), "Invalid frame/action type.")
        first = self.frames[0]
        _need(type(first.observation) is tuple and bool(first.observation)
              and type(first.observation[0]) is tuple, "Immutable public rows required.")
        width, height = len(first.observation[0]), len(first.observation)
        _need(1 <= width <= 30 and 1 <= height <= 16, "Invalid public dimensions.")
        for i, f in enumerate(self.frames):
            _need(type(f.index) is int and f.index == i and type(f.observation) is tuple
                  and len(f.observation) == height and all(type(row) is tuple and len(row) == width
                  and all(type(v) is int and v in range(-6, 9) and v != -1 for v in row)
                  for row in f.observation), "Invalid immutable public frame.")
            _need(_coord(f.cursor, width, height) and type(f.cumulative_modeled_us) is int
                  and f.cumulative_modeled_us >= 0, "Invalid committed cursor/cost.")
            _need(all(type(s) is frozenset and all(_coord(c, width, height) for c in s)
                      for s in (f.logical_mines, f.explicit_flags, f.automatic_flags)),
                  "Immutable, in-bounds frame sets required.")
            _need(f.status in ("PLAYING", "WON", "LOST")
                  and (f.status == "PLAYING") == (i < len(self.actions)), "Premature/missing terminal.")
            if f.status != "LOST":
                _need(all(v >= 0 or v in (HIDDEN, FLAGGED) for row in f.observation for v in row),
                      "Terminal disclosure in a non-LOST frame.")
            flags = _cells(f.observation, FLAGGED)
            _need(not (f.explicit_flags & f.automatic_flags)
                  and flags == f.explicit_flags | f.automatic_flags
                  and (not f.automatic_flags or f.status == "WON"), "Physical flag provenance mismatch.")
        _need(all(v == HIDDEN for row in first.observation for v in row)
              and first.cursor == (0, 0) and first.cumulative_modeled_us == 0
              and not first.logical_mines and not first.explicit_flags and not first.automatic_flags,
              "Frame zero must be an entirely HIDDEN fresh start with empty M.")
        for i, a in enumerate(self.actions):
            before, after = self.frames[i:i + 2]
            _need(type(a.index) is int and a.index == i and a.action in ("OPEN", "FLAG", "CHORD")
                  and _coord(a.target, width, height) and a.cursor_before == before.cursor
                  and after.cursor == a.target and type(a.modeled_action_us) is int
                  and a.modeled_action_us > 0 and a.status_after == after.status
                  and after.cumulative_modeled_us == before.cumulative_modeled_us + a.modeled_action_us,
                  "Action/cursor/cost/frame binding mismatch.")
            _need(type(a.M_before) is frozenset and type(a.preinput_M) is frozenset
                  and a.M_before == before.logical_mines and a.M_before <= a.preinput_M
                  and after.logical_mines == a.preinput_M, "M must commit from exactly the completed input.")
            _need(all(before.observation[y][x] in (HIDDEN, FLAGGED) for x, y in a.preinput_M),
                  "Logical M cannot come from a revealed clue/terminal answer.")
            if self.variant == "V1" or i == 0:
                _need(not a.M_before and not a.preinput_M, "V1/initial input cannot invent K knowledge.")
            if i == 0:
                _need(a.action == "OPEN" and a.target == (0, 0), "Canonical first OPEN required.")
            expected_flags = before.explicit_flags | ({a.target} if a.action == "FLAG" else set())
            _need(after.explicit_flags == expected_flags, "Only physical FLAG inputs create explicit flags.")
            safe_delta = sum(old in (HIDDEN, FLAGGED) and 0 <= new <= 8
                             for oldrow, newrow in zip(before.observation, after.observation)
                             for old, new in zip(oldrow, newrow))
            _need(type(a.safe_cells_opened_delta) is int and a.safe_cells_opened_delta == safe_delta,
                  "Public reveal effect mismatch.")

    @property
    def width(self):
        return len(self.frames[0].observation[0])

    @property
    def height(self):
        return len(self.frames[0].observation)

    @property
    def outcome(self):
        return self.frames[-1].status

    @property
    def total_modeled_us(self):
        return self.frames[-1].cumulative_modeled_us

    @property
    def counts(self):
        return tuple(sum(a.action == name for a in self.actions) for name in ("OPEN", "FLAG", "CHORD"))

    def frame(self, index):
        _need(type(index) is int and 0 <= index <= len(self.actions), "Invalid frame index.")
        return self.frames[index]

    def summary(self):
        return {"variant": self.variant, "outcome": self.outcome, "inputs": len(self.actions),
                "open": self.counts[0], "flag": self.counts[1], "chord": self.counts[2],
                "model_c_us_to_terminal": self.total_modeled_us}


@dataclass(frozen=True, slots=True)
class ExhibitionBoard:
    index: int
    seed: int
    fingerprint: str
    generator: str = "EXPERT_GENERAL_V1 / V1 / game_index"

    def __post_init__(self):
        validate_index(self.index)
        _need(type(self.seed) is int and self.seed == self.index, "Seed/index mismatch.")
        _need(type(self.fingerprint) is str and len(self.fingerprint) == 64
              and all(c in "0123456789abcdef" for c in self.fingerprint), "Invalid fingerprint.")
        _need(self.generator == "EXPERT_GENERAL_V1 / V1 / game_index", "Unsupported generator.")


@dataclass(frozen=True, slots=True)
class ExhibitionSource:
    head: str
    dirty: bool
    git_status: str
    python_version: str
    files: tuple[tuple[str, str], ...]
    algorithm: tuple[tuple[str, str], ...]
    physical_model: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ExhibitionPair:
    board: ExhibitionBoard
    v1: ExhibitionTrace
    k: ExhibitionTrace
    source: ExhibitionSource

    def __post_init__(self):
        _need(type(self.board) is ExhibitionBoard and type(self.source) is ExhibitionSource,
              "Explicit board/source identity required.")
        self.board.__post_init__()
        _need(type(self.v1) is ExhibitionTrace and type(self.k) is ExhibitionTrace
              and self.v1.variant == "V1" and self.k.variant == "K-P0", "Actual V1/K-P0 pair required.")
        for trace in (self.v1, self.k):
            trace.__post_init__()
            _need((trace.width, trace.height) == (30, 16), "Exhibition accepts only Expert 30x16.")

    @property
    def time_to_win_difference_us(self):
        if self.v1.outcome == self.k.outcome == "WON":
            return self.k.total_modeled_us - self.v1.total_modeled_us
        return None
