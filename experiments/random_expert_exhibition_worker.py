"""Source-only, GUI-free worker. Private local pickle is NOT a file-import API."""

import json
import os
from pathlib import Path
import pickle
import sys
import tempfile
import traceback

from experiments.random_expert_exhibition_model import validate_index


def write_atomic(path, value, *, json_text=False):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".publish_", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            if json_text:
                stream.write(json.dumps(value, ensure_ascii=False).encode("utf-8"))
            else:
                pickle.dump(value, stream, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def calculate(payload, progress_path=None):
    token = payload.get("token") if type(payload) is dict else None
    index = payload.get("index") if type(payload) is dict else None
    stage, completed = "VALIDATING", []
    envelope = {"token": token, "index": index, "pair": None, "error": None}

    def progress(phase, summary):
        nonlocal stage
        stage = phase
        if summary is not None:
            completed.append(summary)
        if progress_path is not None:
            try:
                write_atomic(progress_path, {"token": token, "index": index, "phase": phase,
                                             "completed": completed, "worker_pid": os.getpid()}, json_text=True)
            except OSError:
                pass  # advisory only: Windows readers may temporarily prevent replacement

    try:
        if type(payload) is not dict or set(payload) != {"token", "index"}:
            raise ValueError("Worker request must contain exactly token and index.")
        if type(token) is not int or token < 1:
            raise ValueError("Worker request token must be a positive integer.")
        validate_index(index)
        progress("PREPARING", None)
        from experiments.random_expert_exhibition_execution import run_expert_pair

        envelope["pair"] = run_expert_pair(index, progress=progress)
    except Exception:
        envelope["error"] = f"{stage}: {traceback.format_exc()}"
    return envelope


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 4:
        print("Private worker requires payload/result/progress paths and parent scope.", file=sys.stderr)
        return 2
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        from experiments.random_expert_exhibition_process import verify_worker_scope

        verify_worker_scope(args[3])
        with open(args[0], "rb") as stream:
            payload = pickle.load(stream)
            if stream.read(1):
                raise ValueError("Trailing worker request data.")
        result = calculate(payload, args[2])
    except Exception:
        error = f"REQUEST_TRANSPORT: {traceback.format_exc()}"
        print(error, file=sys.stderr, flush=True)  # parent retains the cause even without a valid token
        result = {"token": None, "index": None, "pair": None,
                  "error": error}
    try:
        write_atomic(args[1], result)
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
