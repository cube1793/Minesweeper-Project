"""GUI-free private child transport. User-selected files are handled as JSON."""

import os
import pickle
import sys
import traceback

from experiments.k_lc0_exhibition_model import POLICIES
from experiments.k_lc0_exhibition_store import validate_request
from experiments.random_expert_exhibition_worker import write_atomic
from experiments.random_expert_exhibition_process import verify_worker_scope


def calculate(payload, progress_path=None):
    token = payload.get("token") if type(payload) is dict else None
    request = payload.get("request") if type(payload) is dict else None
    index = request.get("index") if type(request) is dict else None
    run_id = request.get("run_id") if type(request) is dict else None
    result = dict(token=token,index=index,run_id=run_id,policies=POLICIES,pair=None,error=None)
    stage, completed = "VALIDATING", []
    def progress(phase, summary):
        nonlocal stage
        stage = phase
        if summary is not None: completed.append(summary)
        if progress_path is not None:
            try:
                write_atomic(progress_path,dict(token=token,index=index,run_id=run_id,policies=POLICIES,
                             phase=phase,completed=completed,worker_pid=os.getpid(),python=sys.executable),json_text=True)
            except OSError:
                pass
    try:
        if type(payload) is not dict or set(payload) != {"token","request"} or type(token) is not int or token < 1:
            raise ValueError("Invalid private worker request.")
        validate_request(request)
        progress("PREPARING",None)
        from experiments.k_lc0_exhibition_execution import run_pair
        result["pair"] = run_pair(request,progress=progress)
    except Exception:
        result["error"] = f"{stage}: {traceback.format_exc()}"
    return result


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 4:
        print("Private child requires payload/result/progress/scope.",file=sys.stderr)
        return 2
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        verify_worker_scope(args[3])
        with open(args[0],"rb") as stream:
            payload = pickle.load(stream)
            if stream.read(1): raise ValueError("Trailing private request bytes.")
        result = calculate(payload,args[2])
    except Exception:
        error = "REQUEST_TRANSPORT: " + traceback.format_exc()
        print(error,file=sys.stderr,flush=True)
        result = dict(token=None,index=None,run_id=None,policies=POLICIES,pair=None,error=error)
    try:
        write_atomic(args[1],result)
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__": raise SystemExit(main())
