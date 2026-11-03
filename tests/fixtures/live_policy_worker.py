"""Contained lifecycle fixture: no engine, board generator, or solver execution."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiments.random_expert_exhibition_process import verify_worker_scope
from live_policy_transport import message, write_once


def main(argv):
    directory, run_id, scope_name, mode = argv
    directory = Path(directory)
    verify_worker_scope(scope_name)
    descendant = None
    if mode == "tree":
        descendant = subprocess.Popen(
            [sys.executable, "-B", "-c", "import time; time.sleep(30)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    ready = directory / "fixture-ready.part"
    ready.write_text(
        json.dumps({"pid": os.getpid(), "descendant_pid": descendant.pid if descendant else None}),
        encoding="utf-8",
    )
    os.link(ready, directory / "fixture-ready.json")
    ready.unlink()
    if mode == "wrong_identity":
        time.sleep(.1)
        write_once(directory, "worker", 0,
                   message("f" * 32 if run_id != "f" * 32 else "e" * 32, 0, "ERROR",
                           {"code": "SYNTHETIC", "detail": "wrong run identity"}))
    elif mode == "exit":
        return 7
    elif mode not in ("tree", "sleep"):
        raise ValueError("Unknown synthetic fixture mode.")
    time.sleep(30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
