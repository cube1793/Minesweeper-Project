"""PyQt-independent Same-board worker for trusted-local private pickle files.

Only a token and fixed ReplayBoard cross into the child. The Human recording
stays with the parent. Execute both solvers once and atomically publish complete
solver-only evidence or a diagnostic; never fabricate a game outcome on failure.
Pickle is private process transport, not a format for untrusted imported files.
"""

import os
import pickle
import sys
import tempfile

from replay_model import ReplayBoard
from same_board_runner import SolverExecution, run_fixed_layout_solvers


WORKER_SCRIPT = os.path.abspath(__file__)
WORKER_FLAG = "--same-board-execution-worker"


def build_worker_command(payload_path: str, result_path: str) -> list[str]:
    """Source uses this module's absolute path; bundles re-enter the executable."""
    return [sys.executable, WORKER_FLAG if getattr(sys, "frozen", False) else WORKER_SCRIPT,
            os.fspath(payload_path), os.fspath(result_path)]


def calculate_same_board_execution(payload: dict) -> dict:
    """Validate the closed request, then execute once without Human history."""
    token = payload.get("token") if type(payload) is dict else None
    if type(token) is not int or token < 0:
        token = None
    try:
        if type(payload) is not dict or set(payload) != {"token", "board"}:
            raise ValueError("Worker payload must contain exactly token and board.")
        if token is None:
            raise ValueError("Worker token must be a nonnegative integer, excluding bool.")
        if type(payload["board"]) is not ReplayBoard:
            raise ValueError("Worker board must be a ReplayBoard.")
    except Exception as exc:
        return {"token": token, "solver_execution": None, "error": f"Transport failed: {exc!r}"}
    try:
        # The pure entry point revalidates the unpickled board and recomputes
        # canonical layout identity before creating any solver engine.
        execution = run_fixed_layout_solvers(payload["board"])
        if type(execution) is not SolverExecution:
            raise ValueError("Expected complete solver-only execution evidence.")
        return {"token": token, "solver_execution": execution, "error": None}
    except Exception as exc:
        return {"token": token, "solver_execution": None, "error": f"Execution failed: {exc!r}"}


def write_result_atomic(result_path: str, result: dict) -> None:
    """Publish only after writing and closing the complete result in its directory."""
    fd, temp_path = tempfile.mkstemp(
        prefix=".minesweeper_same_board_result_", suffix=".tmp",
        dir=os.path.dirname(os.path.abspath(result_path)),
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
    """Worker CLI; transport/publication failure is distinct from solver failure."""
    if len(argv) != 3:
        print("usage: same_board_execution_worker.py <payload.pkl> <result.pkl>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], "rb") as payload_file:
            payload = pickle.load(payload_file)
            if payload_file.read(1):
                raise ValueError("Unexpected data after worker payload.")
    except Exception as exc:
        result = {"token": None, "solver_execution": None, "error": f"Transport failed: {exc!r}"}
    else:
        result = calculate_same_board_execution(payload)
    try:
        write_result_atomic(argv[2], result)
    except Exception as exc:
        print(f"Result publication failed: {exc!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
