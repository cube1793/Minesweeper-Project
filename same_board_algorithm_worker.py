"""PyQt-independent worker: run ONE comparison algorithm on a fixed board.

Only a token, the fixed ReplayBoard, the algorithm ID and (for Stage4 R) the
target percent text cross into the child. The Human recording stays with the
parent. The child publishes moves/settings or a diagnostic atomically; it never
fabricates an outcome. Pickle is private process transport, not a file format.
"""

import os
import pickle
import sys

from replay_model import ReplayBoard
from same_board_algorithms import ALGORITHMS, AlgorithmRun, execute_algorithm
from same_board_execution_worker import write_result_atomic


WORKER_SCRIPT = os.path.abspath(__file__)
WORKER_FLAG = "--same-board-algorithm-worker"
PAYLOAD_KEYS = {"token", "board", "algorithm", "r_target"}


def build_worker_command(payload_path: str, result_path: str) -> list[str]:
    """Source uses this module's absolute path; bundles re-enter the executable."""
    return [sys.executable, WORKER_FLAG if getattr(sys, "frozen", False) else WORKER_SCRIPT,
            os.fspath(payload_path), os.fspath(result_path)]


def calculate_algorithm_run(payload: dict) -> dict:
    """Validate the closed request, then execute exactly one algorithm once."""
    token = payload.get("token") if type(payload) is dict else None
    if type(token) is not int or token < 0:
        token = None
    try:
        if type(payload) is not dict or set(payload) != PAYLOAD_KEYS:
            raise ValueError("Worker payload must contain exactly token, board, algorithm and r_target.")
        if token is None:
            raise ValueError("Worker token must be a nonnegative integer, excluding bool.")
        if type(payload["board"]) is not ReplayBoard:
            raise ValueError("Worker board must be a ReplayBoard.")
        if type(payload["algorithm"]) is not str or payload["algorithm"] not in ALGORITHMS:
            raise ValueError("Unknown comparison algorithm.")
        if payload["r_target"] is not None and type(payload["r_target"]) is not str:
            raise ValueError("The R target must be text or None.")
    except Exception as exc:
        return {"token": token, "run": None, "error": f"전송 실패: {exc!r}"}
    try:
        run = execute_algorithm(payload["algorithm"], payload["board"], r_target=payload["r_target"])
        if type(run) is not AlgorithmRun:
            raise ValueError("Expected an AlgorithmRun.")
        return {"token": token, "run": run, "error": None}
    except Exception as exc:
        return {"token": token, "run": None, "error": f"실행 실패: {exc!r}"[:4096]}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: same_board_algorithm_worker.py <payload.pkl> <result.pkl>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], "rb") as payload_file:
            payload = pickle.load(payload_file)
            if payload_file.read(1):
                raise ValueError("Unexpected data after worker payload.")
    except Exception as exc:
        result = {"token": None, "run": None, "error": f"전송 실패: {exc!r}"}
    else:
        result = calculate_algorithm_run(payload)
    try:
        write_result_atomic(argv[2], result)
    except Exception as exc:
        print(f"Result publication failed: {exc!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
