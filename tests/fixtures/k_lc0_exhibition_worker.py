"""Controlled lifecycle fixture: real venv Python plus a contained descendant.

No board, runner, inference, planner or GUI. Parent-owned Job ends both sleeps.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.random_expert_exhibition_process import verify_worker_scope

verify_worker_scope(sys.argv[4])
child=subprocess.Popen([sys.executable,"-B","-c","import time; time.sleep(30)"],
                       creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
(Path(sys.argv[1]).parent/"ready.json").write_text(json.dumps(dict(worker=os.getpid(),descendant=child.pid)),encoding="utf-8")
time.sleep(30)
