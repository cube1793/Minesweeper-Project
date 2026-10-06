"""Pure benchmark corpus generation and canonical layout identity.

Generator V1 follows PRE_STAGE3_TELEMETRY_SPEC_v2.md, with CPython 3.12.14
as its reference runtime. Layouts and fingerprints are evaluation information;
they must never be supplied to solver inference or move selection.
"""

import hashlib
import random
import struct
from collections.abc import Iterable
from dataclasses import dataclass


Coordinate = tuple[int, int]
_UINT32_MAX = (1 << 32) - 1


def _require_integer(name: str, value: int, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")


def _require_uint32(name: str, value: int, minimum: int = 0) -> None:
    _require_integer(name, value, minimum)
    if value > _UINT32_MAX:
        raise ValueError(f"{name} must fit in an unsigned 32-bit integer.")


def _validate_dimensions(width: int, height: int, num_mines: int) -> None:
    _require_uint32("width", width, 1)
    _require_uint32("height", height, 1)
    _require_uint32("num_mines", num_mines)
    if num_mines > width * height:
        raise ValueError("num_mines must not exceed the number of cells.")


def _freeze_mines(mine_positions: Iterable[Coordinate]) -> frozenset[Coordinate]:
    try:
        positions = iter(mine_positions)
    except TypeError as exc:
        raise ValueError("mine_positions must be an iterable of coordinate pairs.") from exc

    mines = set()
    for position in positions:
        if not isinstance(position, (tuple, list)) or len(position) != 2:
            raise ValueError("Each mine position must be an (x, y) pair.")
        x, y = position
        _require_uint32("mine x", x)
        _require_uint32("mine y", y)
        coordinate = (x, y)
        if coordinate in mines:
            raise ValueError("Duplicate mine positions are not allowed.")
        mines.add(coordinate)
    return frozenset(mines)


@dataclass(frozen=True)
class BenchmarkSetSpec:
    """Unfiltered V1 corpus definition; seed_scheme='game_index' means equality."""

    benchmark_set_id: str
    width: int
    height: int
    num_mines: int
    first_click_x: int
    first_click_y: int
    board_generator_version: str
    seed_scheme: str

    def __post_init__(self):
        if not isinstance(self.benchmark_set_id, str) or not self.benchmark_set_id.strip():
            raise ValueError("benchmark_set_id must be a nonempty string.")
        _validate_dimensions(self.width, self.height, self.num_mines)
        if self.num_mines > self.width * self.height - 1:
            raise ValueError("Generation requires at least one safe first-click cell.")
        _require_uint32("first_click_x", self.first_click_x)
        _require_uint32("first_click_y", self.first_click_y)
        if self.first_click_x >= self.width or self.first_click_y >= self.height:
            raise ValueError("The first click must be within the board.")
        if self.board_generator_version != "V1":
            raise ValueError("Only board_generator_version='V1' is supported.")
        if self.seed_scheme != "game_index":
            raise ValueError("Only seed_scheme='game_index' is supported.")


@dataclass(frozen=True)
class BenchmarkBoard:
    """Immutable generated identity, retaining no Engine or RNG state.

    Construction copies coordinates and checks their structure and fingerprint
    format. generate_board owns dimension/count checks and the correspondence
    between the layout and its fingerprint, using its BenchmarkSetSpec.
    """

    game_index: int
    seed: int
    mine_positions: frozenset[Coordinate]
    board_fingerprint: str

    def __post_init__(self):
        _require_integer("game_index", self.game_index)
        _require_integer("seed", self.seed)
        object.__setattr__(self, "mine_positions", _freeze_mines(self.mine_positions))
        fingerprint = self.board_fingerprint
        if (
            not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in fingerprint)
        ):
            raise ValueError("board_fingerprint must be 64 lowercase hexadecimal characters.")


EXPERT_GENERAL_V1 = BenchmarkSetSpec(
    benchmark_set_id="EXPERT_GENERAL_V1",
    width=30,
    height=16,
    num_mines=99,
    first_click_x=0,
    first_click_y=0,
    board_generator_version="V1",
    seed_scheme="game_index",
)


def calculate_board_fingerprint(
    width: int,
    height: int,
    num_mines: int,
    mine_positions: Iterable[Coordinate],
) -> str:
    """Validate and hash a layout, independent of all generation metadata.

    Duplicate coordinates are rejected before freezing. Unlike generation,
    fingerprinting does not impose a safe first cell or any first-click policy.
    """
    _validate_dimensions(width, height, num_mines)
    mines = _freeze_mines(mine_positions)
    if len(mines) != num_mines:
        raise ValueError("The number of distinct mine positions must equal num_mines.")
    if any(x >= width or y >= height for x, y in mines):
        raise ValueError("Mine positions must be within the board.")

    payload = (
        b"MSLAYOUT1\0"
        + struct.pack(">III", width, height, num_mines)
        + b"".join(
            struct.pack(">II", x, y)
            for x, y in sorted(mines, key=lambda coordinate: (coordinate[1], coordinate[0]))
        )
    )
    return hashlib.sha256(payload).hexdigest()


def generate_board(spec: BenchmarkSetSpec, game_index: int) -> BenchmarkBoard:
    """Return one entry in a V1 prefix stream, without filtering or retries.

    The primary set uses FIRST_CLICK_FIXED_0_0. Only the specified first cell
    is excluded; neighbors remain eligible, so no zero opening is guaranteed.
    Integer seeds are passed through exactly, with no uint32 limit on indices.
    """
    if not isinstance(spec, BenchmarkSetSpec):
        raise ValueError("spec must be a BenchmarkSetSpec.")
    _require_integer("game_index", game_index)
    seed = game_index
    rng = random.Random(seed)
    first_click = (spec.first_click_x, spec.first_click_y)
    candidates = [
        (x, y)
        for y in range(spec.height)
        for x in range(spec.width)
        if (x, y) != first_click
    ]
    mines = rng.sample(candidates, spec.num_mines)
    fingerprint = calculate_board_fingerprint(spec.width, spec.height, spec.num_mines, mines)
    return BenchmarkBoard(game_index, seed, frozenset(mines), fingerprint)
