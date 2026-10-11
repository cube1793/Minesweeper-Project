"""Manually freeze V1 output only for an intentional, reviewed baseline change.

From the repository root: python -m tests.generate_zini_v1_golden --write
Never run this to make a TYPE S regression failure pass. Ordinary unittest
discovery neither imports this module nor writes the golden file. No 1000-eval
Expert workload is included.
"""

import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import platform
from pprint import pformat
import subprocess
import sys

from benchmark_board import calculate_board_fingerprint
from tests.zini_fixtures import _replay_zini_result
from tests.zini_golden_helpers import (
    WORKLOADS,
    canonical_output,
    run_workload,
    workload_snapshot,
)
from zini_calculator import ZiniResult


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = Path(__file__).with_name("zini_v1_golden.py")
SOURCE_FILES = (
    "zini_calculator.py", "zini_core.py", "zini_min_ties.py", "zini_advanced.py",
    "board_snapshot.py", "board_analyzer.py", "benchmark_board.py", "core_engine.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true",
        help="Explicitly replace the frozen baseline; requires review of the diff.",
    )
    args = parser.parse_args()
    if not args.write:
        parser.error("Golden generation requires the explicit --write flag.")

    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
    ).strip()
    changed_sources = subprocess.check_output(
        ["git", "diff", "HEAD", "--name-only", "--", *SOURCE_FILES],
        cwd=ROOT, text=True,
    ).strip()
    if changed_sources:
        parser.error(f"Cannot attribute modified source to HEAD:\n{changed_sources}")

    fingerprints = {}
    cases = {}
    for name, inputs in WORKLOADS.items():
        output = run_workload(inputs)
        result = output if isinstance(output, ZiniResult) else output.result
        snapshot = workload_snapshot(inputs["board"])
        # Validate once during generation; the regression tests compare fresh
        # algorithm output to literals and do not just replay these moves.
        state = _replay_zini_result(snapshot, result)
        if (
            not state.all_safe_cells_revealed()
            or not state.flagged_mines <= snapshot.mines
            or result.clicks != sum(move.clicks_added for move in result.moves)
        ):
            raise RuntimeError(f"Invalid generated result: {name}")
        fingerprints[inputs["board"]] = calculate_board_fingerprint(
            snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines,
        )
        cases[name] = {"inputs": inputs, "expected": canonical_output(output)}
        expected = cases[name]["expected"]
        print(
            f"{name}: clicks={result.clicks}, moves={len(result.moves)}, "
            f"metadata={expected['metadata']}", flush=True,
        )

    provenance = {
        "baseline_commit": commit,
        "source_files_clean_at_generation": SOURCE_FILES,
        "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_build": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", "unset"),
        "generation_command": "python -m tests.generate_zini_v1_golden --write",
        "move_fields": ("action", "x", "y", "premium", "clicks_added"),
        "excluded_fields": ("elapsed_seconds",),
        "boards": {
            "board_c": "tests.zini_fixtures._board_c_snapshot",
            "expert1003": "tests.zini_fixtures._expert_seed1003_snapshot",
            "general0": "EXPERT_GENERAL_V1 game_index=0 (Engine snapshot)",
            "general42": "EXPERT_GENERAL_V1 game_index=42 (Engine snapshot)",
        },
        "board_fingerprints": fingerprints,
        "scope": (
            "Algorithm output from fresh calculations; not the historical "
            "120-click replay witness. All advanced runs have seed=0, "
            "max_evaluations=20, max_seconds=None, stall_seconds=None. "
            "The UI-default 1000-eval Expert run is excluded."
        ),
    }
    # Format each workload separately so long case names do not force every
    # canonical move tuple across several lines.
    case_lines = ["GOLDEN = {"]
    for name, case in cases.items():
        case_lines.append(f"    {name!r}: {{")
        for key, value in case.items():
            prefix = f"        {key!r}: "
            formatted = pformat(value, width=100 - len(prefix), sort_dicts=False)
            case_lines.append(
                prefix + formatted.replace("\n", "\n" + " " * len(prefix)) + ","
            )
        case_lines.append("    },")
    case_lines.append("}")
    text = (
        '"""Frozen ZiNi V1 algorithm outputs; test data, not live expectations.\n\n'
        'Update only via the explicit generator for a reviewed baseline change.\n'
        'Moves use (action, x, y, premium, clicks_added); time is excluded.\n'
        '"""\n\n'
        f"PROVENANCE = {pformat(provenance, width=100, sort_dicts=False)}\n\n"
        + "\n".join(case_lines) + "\n"
    )
    DESTINATION.write_text(text, encoding="utf-8")
    print(f"Written: {DESTINATION}")


if __name__ == "__main__":
    main()
