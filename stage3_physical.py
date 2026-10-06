"""Frozen Stage-3 V1 integer movement-plus-input costs, in microseconds.

The profile and its table are independently authenticated. Calibration metadata
is provenance only: execution uses the stored table without coefficient fitting
or formula evaluation. Table indices are [absolute dx][absolute dy].
"""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from simple_algorithm import Coordinate


PROFILE_PATH = Path(__file__).resolve().parent / "calibration" / "stage3_physical_profile_v1.json"
PROFILE_SHA256 = "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b"
TABLE_SHA256 = "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b"
TimingTable = tuple[tuple[int, ...], ...]


def validate_timing_table(table: Sequence[Sequence[int]]) -> TimingTable:
    """Return an immutable, positive-int 30-by-16 table with the frozen hash."""
    if not isinstance(table, (tuple, list)) or len(table) != 30:
        raise ValueError("Timing table must have 30 dx rows.")
    if any(not isinstance(row, (tuple, list)) or len(row) != 16 for row in table):
        raise ValueError("Timing table must have 16 dy entries per dx row.")
    if any(type(value) is not int or value <= 0 for row in table for value in row):
        raise ValueError("Timing table entries must be positive integers.")
    normalized = tuple(tuple(row) for row in table)
    encoded = ",".join(str(value) for row in normalized for value in row).encode("ascii")
    if hashlib.sha256(encoded).hexdigest() != TABLE_SHA256:
        raise ValueError("Frozen timing table SHA-256 mismatch.")
    return normalized


def load_timing_table(path: str | Path = PROFILE_PATH) -> TimingTable:
    """Authenticate exact profile bytes, required metadata, and stored table."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROFILE_SHA256:
        raise ValueError("Frozen physical profile SHA-256 mismatch.")
    profile = json.loads(raw)
    required = {
        "model_id": "overlap_floor_log2_distance_v1",
        "timing_tick_unit": "1_us",
        "timing_unit": "us",
        "distance_unit": "cell_width",
        "grid_width": 30,
        "grid_height": 16,
        "table_dimensions": [30, 16],
        "table_order": "dx_major_dy_minor",
        "table_encoding": "ASCII decimal integers, comma-separated, no whitespace or trailing comma",
        "table_sha256": TABLE_SHA256,
    }
    if not isinstance(profile, dict):
        raise ValueError("Physical profile must be a JSON object.")
    for name, expected in required.items():
        value = profile.get(name)
        if value != expected or type(value) is not type(expected):
            raise ValueError(f"Unsupported physical profile metadata: {name}.")
    return validate_timing_table(profile.get("timing_table_us"))


def action_cost(table: TimingTable, start: Coordinate, end: Coordinate) -> int:
    """Read exact movement plus target-input cost from an already valid table.

    The caller authenticates the table once at its public entry point; routing
    may then make many constant-time lookups without rehashing the same table.
    Coordinates are cell centers inside the frozen 30-by-16 grid.
    """
    for coordinate in (start, end):
        if (
            not isinstance(coordinate, (tuple, list))
            or len(coordinate) != 2
            or any(type(value) is not int for value in coordinate)
            or not 0 <= coordinate[0] < 30
            or not 0 <= coordinate[1] < 16
        ):
            raise ValueError("Action coordinates must lie in the frozen 30-by-16 grid.")
    return table[abs(end[0] - start[0])][abs(end[1] - start[1])]
