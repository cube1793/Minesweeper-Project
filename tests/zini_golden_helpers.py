"""Test-only V1 workloads, canonical output, and first-divergence diagnostics.

Expected outputs live in zini_v1_golden.py; nothing here regenerates them.
These workloads lock algorithm output, unlike the historical 120-click witness
in zini_fixtures.py, which checks replay semantics.
"""

from dataclasses import asdict, fields
from itertools import zip_longest

from benchmark_board import EXPERT_GENERAL_V1, generate_board
from core_engine import MinesweeperEngine
from tests.zini_fixtures import (
    _board_c_snapshot,
    _expert_seed1003_snapshot,
    _move_signature,
)
from zini_calculator import (
    ZiniAdvancedSearchResult,
    ZiniNeighborhoodBeamConfig,
    ZiniResult,
    calculate_g_zini,
    calculate_g_zini_min_ties_bounded,
    calculate_g_zini_neighborhood_beam_bounded,
)


# Pin every V1 search parameter, including defaults, for future TYPE S checks.
_ADVANCED_CONFIG = {
    "premium_window": 2,
    "beam_size": 8,
    "max_decision_points": 6,
    "max_alternatives_per_point": 3,
    "prefix_diversity_length": 20,
    "retain_click_margin": 3,
    "max_seconds": None,
    "max_evaluations": 20,
    "stall_seconds": None,
    "seed": 0,
    "chain_depth": 2,
    "chain_branching": 2,
    "standard_phase_evaluations": None,
}

WORKLOADS = {
    f"deterministic/{board}": {"board": board, "method": "deterministic"}
    for board in ("board_c", "expert1003", "general0", "general42")
}
for _policy in ("standard_v1", "chain_v1", "standard_seeded_chain_v1"):
    WORKLOADS[f"advanced/expert1003/{_policy}"] = {
        "board": "expert1003",
        "method": "advanced",
        "config": {
            **_ADVANCED_CONFIG,
            "ranking_policy": _policy,
            "standard_phase_evaluations": (
                10 if _policy == "standard_seeded_chain_v1" else None
            ),
        },
    }
for _board, _label, _states in (
    ("expert1003", "states_200", 200),
    ("board_c", "exact", None),
    ("board_c", "states_200", 200),
):
    WORKLOADS[f"min_ties/{_board}/{_label}"] = {
        "board": _board,
        "method": "min_ties",
        "limits": {"max_seconds": None, "max_states": _states},
    }


def workload_snapshot(board):
    if board == "board_c":
        return _board_c_snapshot()
    if board == "expert1003":
        return _expert_seed1003_snapshot()
    index = {"general0": 0, "general42": 42}[board]
    spec = EXPERT_GENERAL_V1
    generated = generate_board(spec, index)
    engine = MinesweeperEngine(spec.width, spec.height, spec.num_mines)
    engine.reset_with_mines(
        spec.width, spec.height, spec.num_mines, generated.mine_positions,
    )
    return engine.get_board_snapshot()


def run_workload(inputs):
    """Calculate a fresh actual result, never an expected result during tests."""
    snapshot = workload_snapshot(inputs["board"])
    method = inputs["method"]
    if method == "deterministic":
        return calculate_g_zini(snapshot)
    if method == "advanced":
        return calculate_g_zini_neighborhood_beam_bounded(
            snapshot, config=ZiniNeighborhoodBeamConfig(**inputs["config"]),
        )
    if method == "min_ties":
        return calculate_g_zini_min_ties_bounded(snapshot, **inputs["limits"])
    raise ValueError(f"Unknown golden method: {method}")


def canonical_output(output):
    """Keep full moves and all public search metadata except elapsed time."""
    if isinstance(output, ZiniResult):
        result = output
        metadata = {}
    else:
        result = output.result
        metadata = {
            field.name: getattr(output, field.name)
            for field in fields(output)
            if field.name not in ("result", "elapsed_seconds", "config")
        }
        if isinstance(output, ZiniAdvancedSearchResult):
            metadata["termination_reason"] = output.termination_reason.value
            metadata["config"] = asdict(output.config)
    return {
        "clicks": result.clicks,
        "moves": _move_signature(result),
        "metadata": metadata,
    }


_MISSING = object()


def _display(value):
    return "<missing>" if value is _MISSING else repr(value)


def _field_differences(expected, actual, prefix):
    for key in sorted(expected.keys() | actual.keys()):
        before = expected.get(key, _MISSING)
        after = actual.get(key, _MISSING)
        field = f"{prefix}.{key}" if prefix else key
        if isinstance(before, dict) and isinstance(after, dict):
            yield from _field_differences(before, after, field)
        elif before != after:
            yield (
                f"{field}: expected={_display(before)}, actual={_display(after)}"
            )


def assert_golden_equal(test_case, expected, actual, *, workload):
    """Report one move divergence plus every differing metadata field.

    Step indices are zero-based. A strict prefix (including an empty sequence)
    differs at the first missing step, rendered as <end of sequence>.
    """
    differences = []
    expected_moves = expected["moves"]
    actual_moves = actual["moves"]
    for index, (before, after) in enumerate(zip_longest(
        expected_moves, actual_moves, fillvalue=_MISSING,
    )):
        if before != after:
            before_text = (
                "<end of sequence>" if before is _MISSING else repr(before)
            )
            after_text = (
                "<end of sequence>" if after is _MISSING else repr(after)
            )
            differences.extend((
                f"expected move count: {len(expected_moves)}",
                f"actual move count: {len(actual_moves)}",
                f"first differing step index (0-based): {index}",
                f"expected move: {before_text}",
                f"actual move: {after_text}",
            ))
            break
    differences.extend(_field_differences(
        {key: value for key, value in expected.items() if key != "moves"},
        {key: value for key, value in actual.items() if key != "moves"},
        "",
    ))
    if differences:
        test_case.fail(f"ZiNi V1 golden mismatch [{workload}]\n" + "\n".join(differences))
