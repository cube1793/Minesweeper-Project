"""Pure Stage-3 calibration V1 protocol, with no UI or measurement dependencies.

Generation is an explicit preparation step. It never reads measurements or
writes a manifest; collection must later read a reviewed, frozen manifest.
V1 uses CPython's local random.Random(seed), as does the benchmark generator.
Canonical serialization is compact, key-sorted, ASCII-escaped JSON without a
trailing newline. Trial array order is the presentation order and is hashed.
"""

import hashlib
import json
import random
from collections import Counter
from dataclasses import asdict, dataclass


Coordinate = tuple[int, int]
PROTOCOL_VERSION = "STAGE3_CALIBRATION_V1"
GRID_WIDTH = 30
GRID_HEIGHT = 16
CELL_SIZE_PX = 28
BLOCK_COUNT = 3
TRIALS_PER_BLOCK = 128
OFFICIAL_TRIAL_COUNT = 384
WARMUP_TRIAL_COUNT = 24
REPETITIONS_PER_TRANSITION = 6
REPETITIONS_PER_BLOCK = 2
WARMUP = "WARMUP"
OFFICIAL = "OFFICIAL"
OFFSET_FAMILIES = (
    ("O00", 0, 0), ("O01", 1, 0), ("O02", 1, 1), ("O03", 2, 0),
    ("O04", 2, 1), ("O05", 3, 1), ("O06", 4, 3), ("O07", 6, 0),
    ("O08", 6, 4), ("O09", 8, 6), ("O10", 10, 0), ("O11", 12, 5),
    ("O12", 15, 8), ("O13", 20, 10), ("O14", 24, 12), ("O15", 29, 15),
)
BUTTON_TRANSITIONS = (
    ("LEFT", "LEFT"), ("LEFT", "RIGHT"),
    ("RIGHT", "LEFT"), ("RIGHT", "RIGHT"),
)


def _require_integer(name: str, value: int, minimum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}.")


def _freeze_sequence(name: str, value) -> tuple:
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be a list or tuple.")
    return tuple(value)


def _freeze_cell(name: str, value) -> Coordinate:
    cell = _freeze_sequence(name, value)
    if len(cell) != 2:
        raise ValueError(f"{name} must be an (x, y) pair.")
    for axis, limit, coordinate in zip(("x", "y"), (GRID_WIDTH, GRID_HEIGHT), cell):
        _require_integer(f"{name}.{axis}", coordinate, 0)
        if coordinate >= limit:
            raise ValueError(f"{name} is out of board bounds.")
    return cell


def enumerate_feasible_orientations(abs_dx: int, abs_dy: int) -> tuple[Coordinate, ...]:
    """Return distinct legal signed/swapped deltas, sorted by (dx, dy).

    The V1 board is fixed at 30x16. An oversized offset can have no feasible
    orientation; zeros and equal components do not create duplicate entries.
    """
    _require_integer("abs_dx", abs_dx, 0)
    _require_integer("abs_dy", abs_dy, 0)
    return tuple(sorted({
        (sx * x, sy * y)
        for x, y in ((abs_dx, abs_dy), (abs_dy, abs_dx))
        for sx in (-1, 1)
        for sy in (-1, 1)
        if x < GRID_WIDTH and y < GRID_HEIGHT
    }))


def feasible_start_cells(dx: int, dy: int) -> tuple[Coordinate, ...]:
    """Return all starts whose start + delta is in bounds, in row-major order."""
    _require_integer("dx", dx)
    _require_integer("dy", dy)
    return tuple(
        (x, y)
        for y in range(max(0, -dy), min(GRID_HEIGHT, GRID_HEIGHT - dy))
        for x in range(max(0, -dx), min(GRID_WIDTH, GRID_WIDTH - dx))
    )


@dataclass(frozen=True)
class CalibrationTrial:
    """One planned press-to-press trial; cells and deltas use board units.

    Official block indices are 1..3; warm-up has block_index=None. Absolute
    components identify the canonical family, including for swapped deltas.
    No timing, actual click pixels, or observed result belongs in this model.
    """

    trial_id: str
    phase: str
    block_index: int | None
    offset_id: str
    abs_dx: int
    abs_dy: int
    dx: int
    dy: int
    start_cell: Coordinate
    target_cell: Coordinate
    start_button: str
    target_button: str

    def __post_init__(self):
        if not isinstance(self.trial_id, str) or not self.trial_id.strip():
            raise ValueError("trial_id must be a nonempty string.")
        if self.phase not in (WARMUP, OFFICIAL):
            raise ValueError("phase must be WARMUP or OFFICIAL.")
        if self.phase == WARMUP:
            if self.block_index is not None:
                raise ValueError("WARMUP block_index must be None.")
        else:
            _require_integer("block_index", self.block_index, 1)
            if self.block_index > BLOCK_COUNT:
                raise ValueError("Official block_index must be 1..3.")
        for name in ("abs_dx", "abs_dy"):
            _require_integer(name, getattr(self, name), 0)
        for name in ("dx", "dy"):
            _require_integer(name, getattr(self, name))
        if (self.offset_id, self.abs_dx, self.abs_dy) not in OFFSET_FAMILIES:
            raise ValueError("offset_id and absolute components must match a V1 offset family.")
        if (self.dx, self.dy) not in enumerate_feasible_orientations(self.abs_dx, self.abs_dy):
            raise ValueError("Declared delta is not a feasible orientation of the offset family.")
        for name in ("start_cell", "target_cell"):
            object.__setattr__(self, name, _freeze_cell(name, getattr(self, name)))
        actual = tuple(target - start for start, target in zip(self.start_cell, self.target_cell))
        if actual != (self.dx, self.dy):
            raise ValueError("Actual target - start delta must match the declared delta.")
        if (self.start_button, self.target_button) not in BUTTON_TRANSITIONS:
            raise ValueError("Unsupported button transition.")


@dataclass(frozen=True)
class CalibrationManifest:
    """Complete immutable schedule, including the 24 leading warm-up trials.

    Construction validates the entire V1 protocol. Only seed varies in the
    generator; dimensions, families, transitions and counts are fixed in V1.
    """

    seed: int
    trials: tuple[CalibrationTrial, ...]
    protocol_version: str = PROTOCOL_VERSION
    grid_width: int = GRID_WIDTH
    grid_height: int = GRID_HEIGHT
    cell_size_px: int = CELL_SIZE_PX
    offsets: tuple[tuple[str, int, int], ...] = OFFSET_FAMILIES
    button_transitions: tuple[tuple[str, str], ...] = BUTTON_TRANSITIONS

    def __post_init__(self):
        object.__setattr__(self, "trials", _freeze_sequence("trials", self.trials))
        for name in ("offsets", "button_transitions"):
            rows = _freeze_sequence(name, getattr(self, name))
            object.__setattr__(self, name, tuple(_freeze_sequence(name, row) for row in rows))
        validate_manifest(self)


def validate_manifest(manifest: CalibrationManifest) -> None:
    """Raise ValueError for any invalid protocol fact or schedule invariant.

    Spatial dispersion and pair uniqueness are generation preferences, not
    validity requirements: O15 necessarily repeats its four corner pairs.
    """
    if not isinstance(manifest, CalibrationManifest):
        raise ValueError("manifest must be a CalibrationManifest.")
    _require_integer("seed", manifest.seed, 0)
    if manifest.protocol_version != PROTOCOL_VERSION:
        raise ValueError("Unsupported protocol_version.")
    for name, expected in (("grid_width", GRID_WIDTH), ("grid_height", GRID_HEIGHT),
                           ("cell_size_px", CELL_SIZE_PX)):
        value = getattr(manifest, name)
        _require_integer(name, value)
        if value != expected:
            raise ValueError(f"V1 {name} must be {expected}.")
    for offset in manifest.offsets:
        if len(offset) != 3:
            raise ValueError("Each offset must contain its ID and two absolute components.")
        _require_integer("offset abs_dx", offset[1], 0)
        _require_integer("offset abs_dy", offset[2], 0)
    if manifest.offsets != OFFSET_FAMILIES:
        raise ValueError("V1 requires the exact ordered 16 offset families.")
    if manifest.button_transitions != BUTTON_TRANSITIONS:
        raise ValueError("V1 requires the exact ordered four button transitions.")
    if len(manifest.trials) != WARMUP_TRIAL_COUNT + OFFICIAL_TRIAL_COUNT:
        raise ValueError("V1 requires 24 warm-up and 384 official trials.")

    trial_ids = set()
    block_counts = Counter()
    repetition_counts = Counter()
    orientation_counts = Counter()
    transition_orientation_counts = Counter()
    for index, trial in enumerate(manifest.trials):
        if not isinstance(trial, CalibrationTrial):
            raise ValueError("Every trial must be a CalibrationTrial.")
        if trial.trial_id in trial_ids:
            raise ValueError("Duplicate trial_id.")
        trial_ids.add(trial.trial_id)
        if index < WARMUP_TRIAL_COUNT:
            if trial.phase != WARMUP:
                raise ValueError("The first 24 trials must be WARMUP.")
            continue
        if trial.phase != OFFICIAL:
            raise ValueError("Warm-up must be separated before all official trials.")
        expected_block = (index - WARMUP_TRIAL_COUNT) // TRIALS_PER_BLOCK + 1
        if trial.block_index != expected_block:
            raise ValueError("Official blocks must be consecutive, ordered, and contain 128 trials.")
        block_counts[trial.block_index] += 1
        repetition_counts[(trial.block_index, trial.offset_id,
                           trial.start_button, trial.target_button)] += 1
        orientation_counts[(trial.offset_id, trial.dx, trial.dy)] += 1
        transition_orientation_counts[(trial.offset_id, trial.start_button,
                                       trial.target_button, trial.dx, trial.dy)] += 1

    if block_counts != Counter({block: TRIALS_PER_BLOCK for block in range(1, BLOCK_COUNT + 1)}):
        raise ValueError("V1 requires exactly three official blocks of 128 trials.")
    for offset_id, abs_dx, abs_dy in OFFSET_FAMILIES:
        orientations = enumerate_feasible_orientations(abs_dx, abs_dy)
        for start_button, target_button in BUTTON_TRANSITIONS:
            for block in range(1, BLOCK_COUNT + 1):
                if repetition_counts[(block, offset_id, start_button, target_button)] != REPETITIONS_PER_BLOCK:
                    raise ValueError("Each offset/transition/block must have exactly two trials.")
            counts = [transition_orientation_counts[(offset_id, start_button, target_button, dx, dy)]
                      for dx, dy in orientations]
            if max(counts) - min(counts) > 1:
                raise ValueError(f"Official transition orientation counts are unbalanced for "
                                 f"{offset_id} {start_button}->{target_button}.")
        counts = [orientation_counts[(offset_id, dx, dy)]
                  for dx, dy in orientations]
        if max(counts) - min(counts) > 1:
            raise ValueError(f"Official orientation counts are unbalanced for {offset_id}.")


def generate_manifest_v1(seed: int) -> CalibrationManifest:
    """Build the complete schedule with a required, nonnegative integer seed.

    Each family's shuffled orientation cycle is split into four six-trial
    slices, assigned to shuffled transitions. Each slice contributes two trials
    per block. Thus directions are balanced both overall and within each
    transition (including unused orientations), without tying a button to one
    direction. Each block's presentation order is then independently shuffled.

    Placement consumes shuffled start pools without replacement per signed
    delta, preferring the least-used feasible board quadrant. A pool is refilled
    only when exhausted; repeated corner-to-corner pairs are unavoidable.
    """
    _require_integer("seed", seed, 0)
    rng = random.Random(seed)
    pools = {}
    quadrant_uses = Counter()

    def take_start(dx, dy):
        delta = (dx, dy)
        if not pools.get(delta):
            pools[delta] = list(feasible_start_cells(dx, dy))
            rng.shuffle(pools[delta])
        pool = pools[delta]

        def quadrant(cell):
            return (delta, cell[0] * 2 // GRID_WIDTH, cell[1] * 2 // GRID_HEIGHT)

        index = min(range(len(pool)), key=lambda i: quadrant_uses[quadrant(pool[i])])
        start = pool.pop(index)
        quadrant_uses[quadrant(start)] += 1
        return start

    def make_trial(trial_id, phase, block, family, delta, transition):
        offset_id, abs_dx, abs_dy = family
        dx, dy = delta
        start = take_start(dx, dy)
        target = (start[0] + dx, start[1] + dy)
        return CalibrationTrial(trial_id, phase, block, offset_id, abs_dx, abs_dy,
                                dx, dy, start, target, *transition)

    # Warm-up covers all families and gives six trials to each transition.
    warmup_families = list(OFFSET_FAMILIES)
    rng.shuffle(warmup_families)
    warmup_transitions = list(BUTTON_TRANSITIONS) * REPETITIONS_PER_TRANSITION
    rng.shuffle(warmup_transitions)
    trials = []
    for index, transition in enumerate(warmup_transitions):
        family = warmup_families[index % len(warmup_families)]
        delta = rng.choice(enumerate_feasible_orientations(*family[1:]))
        trials.append(make_trial(f"W{index + 1:03d}", WARMUP, None, family, delta, transition))

    blocks = [[] for _ in range(BLOCK_COUNT)]
    for family in OFFSET_FAMILIES:
        orientations = list(enumerate_feasible_orientations(*family[1:]))
        rng.shuffle(orientations)
        transitions = list(BUTTON_TRANSITIONS)
        rng.shuffle(transitions)
        for rank, transition in enumerate(transitions):
            for repetition in range(REPETITIONS_PER_TRANSITION):
                delta = orientations[(rank * REPETITIONS_PER_TRANSITION + repetition) % len(orientations)]
                blocks[repetition // REPETITIONS_PER_BLOCK].append((family, delta, transition))
    for block_index, block in enumerate(blocks, 1):
        rng.shuffle(block)
        for index, (family, delta, transition) in enumerate(block, 1):
            trials.append(make_trial(f"B{block_index}-T{index:03d}", OFFICIAL,
                                     block_index, family, delta, transition))
    return CalibrationManifest(seed=seed, trials=tuple(trials))


def canonical_manifest_bytes(manifest: CalibrationManifest) -> bytes:
    """Validate and serialize every manifest fact, preserving trial order."""
    validate_manifest(manifest)
    return json.dumps(asdict(manifest), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def calculate_manifest_sha256(manifest: CalibrationManifest) -> str:
    """Hash exactly canonical_manifest_bytes(), with no self-referential field."""
    return hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest()
