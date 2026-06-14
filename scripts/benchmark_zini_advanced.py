"""Benchmark deterministic, min-tie, and advanced G.ZiNi calculations."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from board_snapshot import BoardSnapshot
from zini_calculator import (
    ZiniNeighborhoodBeamConfig,
    ZiniResult,
    _ZiniBoardState,
    _apply_premium_candidate,
    _build_premium_context,
    _click_fallback_cell,
    _find_fallback_click_targets,
    _find_premium_candidates,
    calculate_g_zini,
    calculate_g_zini_min_ties_bounded,
    calculate_g_zini_neighborhood_beam_bounded,
)


_BOARD_C_MINES = frozenset(
    {
        (1, 0),
        (6, 0),
        (3, 1),
        (8, 2),
        (0, 3),
        (5, 4),
        (2, 5),
        (7, 6),
        (4, 7),
        (0, 8),
    }
)

_EXPERT_SEED1003_MINES = frozenset(
    {
        (0, 0), (12, 0), (13, 0), (16, 0), (0, 1), (1, 1),
        (2, 1), (3, 1), (14, 1), (19, 1), (7, 2), (8, 2),
        (9, 2), (11, 2), (16, 2), (2, 3), (10, 3), (11, 3),
        (13, 3), (23, 3), (26, 3), (27, 3), (2, 4), (3, 4),
        (8, 4), (10, 4), (11, 4), (17, 4), (18, 4), (1, 5),
        (13, 5), (21, 5), (23, 5), (24, 5), (25, 5), (4, 6),
        (6, 6), (13, 6), (14, 6), (17, 6), (18, 6), (20, 6),
        (26, 6), (27, 6), (8, 7), (10, 7), (11, 7), (12, 7),
        (18, 7), (21, 7), (22, 7), (27, 7), (3, 8), (14, 8),
        (17, 8), (19, 8), (20, 8), (21, 8), (5, 9), (6, 9),
        (9, 9), (11, 9), (12, 9), (16, 9), (27, 9), (28, 9),
        (17, 10), (26, 10), (29, 10), (13, 11), (16, 11),
        (19, 11), (20, 11), (22, 11), (25, 11), (27, 11),
        (7, 12), (9, 12), (12, 12), (20, 12), (26, 12),
        (1, 13), (4, 13), (17, 13), (26, 13), (1, 14),
        (11, 14), (25, 14), (27, 14), (1, 15), (9, 15),
        (12, 15), (13, 15), (14, 15), (18, 15), (21, 15),
        (22, 15), (23, 15), (28, 15),
    }
)

_COLUMNS = (
    "board",
    "method",
    "seed",
    "premium_window",
    "beam_size",
    "max_evaluations",
    "clicks",
    "moves",
    "flags",
    "termination",
    "evaluations",
    "generations",
    "elapsed_seconds",
    "safe_revealed",
    "safe_total",
    "valid_flags",
    "click_sum_ok",
    "replay_valid",
)

_BASE_ADVANCED_CONFIG = {
    "premium_window": 2,
    "beam_size": 8,
    "max_decision_points": 6,
    "max_alternatives_per_point": 3,
    "prefix_diversity_length": 20,
    "retain_click_margin": 3,
    "max_seconds": None,
    "stall_seconds": None,
    "seed": 0,
}

_QUICK_EVALUATIONS = {
    "board_c": (25, 50, 100),
    "expert1003": (100,),
}

_FULL_EVALUATIONS = {
    "board_c": (25, 50, 100),
    "expert1003": (100, 250, 500, 1000, 1500),
}

_FULL_SEEDS = (0, 7, 1234, 614003)


@dataclass(frozen=True)
class _ReplayValidation:
    flags: int
    safe_revealed: int
    safe_total: int
    valid_flags: bool
    click_sum_ok: bool
    replay_valid: bool
    errors: tuple[str, ...]


def _snapshot_from_mines(
    width: int,
    height: int,
    mines: frozenset[tuple[int, int]],
) -> BoardSnapshot:
    adjacent = tuple(
        tuple(
            0
            if (x, y) in mines
            else sum(
                (nx, ny) in mines
                for ny in range(max(0, y - 1), min(height, y + 2))
                for nx in range(max(0, x - 1), min(width, x + 2))
                if (nx, ny) != (x, y)
            )
            for x in range(width)
        )
        for y in range(height)
    )
    return BoardSnapshot(
        width=width,
        height=height,
        num_mines=len(mines),
        mines_placed=True,
        mines=mines,
        adjacent=adjacent,
    )


def _boards() -> dict[str, BoardSnapshot]:
    if len(_EXPERT_SEED1003_MINES) != 99:
        raise RuntimeError("Expert seed 1003 fixture must contain 99 mines.")
    return {
        "board_c": _snapshot_from_mines(9, 9, _BOARD_C_MINES),
        "expert1003": _snapshot_from_mines(
            30,
            16,
            _EXPERT_SEED1003_MINES,
        ),
    }


def _validate_result(
    snapshot: BoardSnapshot,
    result: ZiniResult,
) -> _ReplayValidation:
    state = _ZiniBoardState.create(snapshot)
    context = _build_premium_context(snapshot)
    errors = []

    for step, expected in enumerate(result.moves, start=1):
        candidates = _find_premium_candidates(state, context)
        best_premium = max(
            (candidate.premium for candidate in candidates),
            default=None,
        )
        coord = (expected.x, expected.y)

        try:
            if expected.action == "fallback_click":
                if best_premium is not None and best_premium >= 0:
                    errors.append(
                        f"step {step}: fallback used with Premium "
                        f"{best_premium}"
                    )
                if coord not in _find_fallback_click_targets(state, context):
                    errors.append(
                        f"step {step}: unavailable fallback target {coord}"
                    )
                actual = _click_fallback_cell(state, coord, context)
            else:
                matching = tuple(
                    candidate
                    for candidate in candidates
                    if candidate.coord == coord
                )
                if len(matching) != 1:
                    errors.append(
                        f"step {step}: unavailable Premium target {coord}"
                    )
                    break
                if matching[0].premium != expected.premium:
                    errors.append(
                        f"step {step}: Premium {matching[0].premium} != "
                        f"{expected.premium}"
                    )
                actual = _apply_premium_candidate(
                    state,
                    matching[0],
                    context,
                )
            if actual != expected:
                errors.append(
                    f"step {step}: replayed move {actual} != {expected}"
                )
        except (RuntimeError, ValueError) as error:
            errors.append(f"step {step}: {type(error).__name__}: {error}")
            break

    safe_total = snapshot.width * snapshot.height - len(snapshot.mines)
    click_sum_ok = result.clicks == sum(
        move.clicks_added for move in result.moves
    )
    valid_flags = state.flagged_mines <= snapshot.mines
    replay_valid = (
        not errors
        and state.all_safe_cells_revealed()
        and valid_flags
        and click_sum_ok
    )
    return _ReplayValidation(
        flags=len(state.flagged_mines),
        safe_revealed=len(state.revealed),
        safe_total=safe_total,
        valid_flags=valid_flags,
        click_sum_ok=click_sum_ok,
        replay_valid=replay_valid,
        errors=tuple(errors),
    )


def _row(
    *,
    board: str,
    method: str,
    result: ZiniResult,
    validation: _ReplayValidation,
    elapsed_seconds: float,
    seed: int | str = "-",
    premium_window: int | str = "-",
    beam_size: int | str = "-",
    max_evaluations: int | str = "-",
    termination: str = "-",
    evaluations: int | str = "-",
    generations: int | str = "-",
) -> dict[str, object]:
    return {
        "board": board,
        "method": method,
        "seed": seed,
        "premium_window": premium_window,
        "beam_size": beam_size,
        "max_evaluations": max_evaluations,
        "clicks": result.clicks,
        "moves": len(result.moves),
        "flags": validation.flags,
        "termination": termination,
        "evaluations": evaluations,
        "generations": generations,
        "elapsed_seconds": f"{elapsed_seconds:.6f}",
        "safe_revealed": validation.safe_revealed,
        "safe_total": validation.safe_total,
        "valid_flags": validation.valid_flags,
        "click_sum_ok": validation.click_sum_ok,
        "replay_valid": validation.replay_valid,
    }


def _benchmark_board(
    name: str,
    snapshot: BoardSnapshot,
    mode: str,
) -> list[dict[str, object]]:
    rows = []

    started_at = perf_counter()
    deterministic = calculate_g_zini(snapshot)
    elapsed = perf_counter() - started_at
    validation = _validate_result(snapshot, deterministic)
    rows.append(
        _row(
            board=name,
            method="deterministic",
            result=deterministic,
            validation=validation,
            elapsed_seconds=elapsed,
        )
    )

    if name == "board_c":
        started_at = perf_counter()
        min_ties = calculate_g_zini_min_ties_bounded(snapshot)
        elapsed = perf_counter() - started_at
        validation = _validate_result(snapshot, min_ties.result)
        termination = "exact" if min_ties.exact else "bounded"
        rows.append(
            _row(
                board=name,
                method="min_ties",
                result=min_ties.result,
                validation=validation,
                elapsed_seconds=elapsed,
                termination=termination,
                evaluations=min_ties.search_calls,
            )
        )

    evaluations_by_board = (
        _QUICK_EVALUATIONS if mode == "quick" else _FULL_EVALUATIONS
    )
    advanced_runs = [
        (0, max_evaluations)
        for max_evaluations in evaluations_by_board[name]
    ]
    if mode == "full":
        advanced_runs.extend((seed, 500) for seed in _FULL_SEEDS)

    seen_runs = set()
    for seed, max_evaluations in advanced_runs:
        run_key = seed, max_evaluations
        if run_key in seen_runs:
            continue
        seen_runs.add(run_key)

        config_values = dict(_BASE_ADVANCED_CONFIG)
        config_values.update(
            seed=seed,
            max_evaluations=max_evaluations,
        )
        config = ZiniNeighborhoodBeamConfig(**config_values)
        started_at = perf_counter()
        advanced = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=config,
        )
        elapsed = perf_counter() - started_at
        validation = _validate_result(snapshot, advanced.result)
        rows.append(
            _row(
                board=name,
                method="neighborhood_beam",
                result=advanced.result,
                validation=validation,
                elapsed_seconds=elapsed,
                seed=seed,
                premium_window=config.premium_window,
                beam_size=config.beam_size,
                max_evaluations=max_evaluations,
                termination=advanced.termination_reason.value,
                evaluations=advanced.evaluations,
                generations=advanced.generations,
            )
        )

    return rows


def _print_table(rows: list[dict[str, object]]):
    widths = {
        column: max(
            len(column),
            *(len(str(row[column])) for row in rows),
        )
        for column in _COLUMNS
    }
    print("  ".join(column.ljust(widths[column]) for column in _COLUMNS))
    print("  ".join("-" * widths[column] for column in _COLUMNS))
    for row in rows:
        print(
            "  ".join(
                str(row[column]).ljust(widths[column])
                for column in _COLUMNS
            )
        )


def _write_csv(path: Path, rows: list[dict[str, object]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark bounded advanced G.ZiNi calculations.",
    )
    parser.add_argument(
        "--board",
        choices=("board_c", "expert1003", "all"),
        default="all",
        help="Board fixture to benchmark (default: all).",
    )
    parser.add_argument(
        "--mode",
        choices=("quick", "full"),
        default="quick",
        help="Benchmark breadth; full can take several minutes.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional path for CSV output.",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    boards = _boards()
    selected = (
        tuple(boards)
        if args.board == "all"
        else (args.board,)
    )
    rows = []
    for name in selected:
        rows.extend(_benchmark_board(name, boards[name], args.mode))

    _print_table(rows)
    if args.csv is not None:
        _write_csv(args.csv, rows)
        print(f"\nCSV written to {args.csv}")

    invalid = [row for row in rows if not row["replay_valid"]]
    if invalid:
        raise SystemExit("One or more benchmark traces failed replay validation.")


if __name__ == "__main__":
    main()
