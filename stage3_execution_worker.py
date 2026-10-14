"""PyQt-independent Stage-3 subprocess boundary for trusted-local pickle files.

The parent owns process lifetime and request/result paths. This worker executes
one requested expert index and publishes the complete execution without a live
engine, result conversion, or retries.
"""

from __future__ import annotations

import os
import pickle
import sys
import tempfile

from stage3_execution import run_expert_stage3_execution


def calculate_stage3_execution(payload: dict) -> dict:
    """Keep transport identity separate from the single Stage-3 execution."""
    token = payload["token"]
    game_index = payload["game_index"]
    try:
        execution = run_expert_stage3_execution(game_index)
        return {"token": token, "execution": execution, "error": None}
    except Exception as exc:
        return {"token": token, "execution": None, "error": repr(exc)}


def write_result_atomic(result_path: str, result: dict) -> None:
    """Publish only after the complete pickle has been written and closed."""
    result_dir = os.path.dirname(os.path.abspath(result_path))
    fd, temp_path = tempfile.mkstemp(
        prefix=".minesweeper_stage3_result_",
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
    """Worker CLI: stage3_execution_worker.py payload.pkl result.pkl."""
    if len(argv) != 3:
        print(
            "usage: stage3_execution_worker.py <payload.pkl> <result.pkl>",
            file=sys.stderr,
        )
        return 2

    with open(argv[1], "rb") as payload_file:
        payload = pickle.load(payload_file)

    write_result_atomic(argv[2], calculate_stage3_execution(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
