"""Subprocess worker for Counters ZiNi calculation.

This module intentionally has no PyQt dependency. The UI launches it as a
separate Python process so long-running advanced ZiNi searches can be
terminated when the board changes.
"""

from __future__ import annotations

import os
import pickle
import sys
import tempfile

from zini_calculator import calculate_g_zini_neighborhood_beam_bounded


def calculate_counter_zini(payload: dict) -> dict:
    """Calculate bounded best-so-far ZiNi for one serialized UI payload."""
    token = payload["token"]
    snapshot = payload["snapshot"]
    config = payload["config"]
    try:
        result = calculate_g_zini_neighborhood_beam_bounded(
            snapshot,
            config=config,
        )
        return {
            "token": token,
            "clicks": result.best_clicks,
            "error": None,
        }
    except Exception as exc:
        return {
            "token": token,
            "clicks": None,
            "error": repr(exc),
        }


def write_result_atomic(result_path: str, result: dict) -> None:
    """Write the result by replacing the target path after pickle completes."""
    result_dir = os.path.dirname(os.path.abspath(result_path))
    fd, temp_path = tempfile.mkstemp(
        prefix=".minesweeper_zini_result_",
        suffix=".tmp",
        dir=result_dir,
    )
    try:
        with os.fdopen(fd, "wb") as result_file:
            pickle.dump(result, result_file, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temp_path, result_path)
    except Exception:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str]) -> int:
    """Worker CLI: zini_metric_worker.py payload.pkl result.pkl."""
    if len(argv) != 3:
        print(
            "usage: zini_metric_worker.py <payload.pkl> <result.pkl>",
            file=sys.stderr,
        )
        return 2

    payload_path = argv[1]
    result_path = argv[2]
    with open(payload_path, "rb") as payload_file:
        payload = pickle.load(payload_file)

    write_result_atomic(result_path, calculate_counter_zini(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
