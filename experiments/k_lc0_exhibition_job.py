"""Narrow start/admission adapter; inherited RF lifecycle is unchanged.

Copied start skeleton changes only durable request identity and worker command.
poll/cancel/stop/drain/reap/cleanup/shutdown remain ExhibitionJob methods.
"""

import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile

from experiments.random_expert_exhibition_job import ExhibitionJob, PREFIX, ROOT
from experiments.random_expert_exhibition_process import CREATE_SUSPENDED, create_scope
from experiments.random_expert_exhibition_model import validate_index
from experiments.k_lc0_exhibition_model import ComparePair, POLICIES
from experiments.k_lc0_exhibition_store import DEFAULT_RUNS, make_request, bind_request


def build_worker_command(payload,result,progress,scope_name=""):
    if getattr(sys,"frozen",False): raise RuntimeError("Source Python only.")
    return [sys.executable,"-B","-m","experiments.k_lc0_exhibition_worker",
            str(payload),str(result),str(progress),scope_name]


class CompareJob(ExhibitionJob):
    def __init__(self,parent=None,*,runs_root=DEFAULT_RUNS,**kwargs):
        super().__init__(parent,**kwargs)
        self.runs_root = Path(runs_root)
        self.request = None
        self.run_directory = None

    def start(self,index,kind="index"):
        validate_index(index)
        if kind not in ("index","draw"): raise ValueError("Invalid request kind.")
        if self.state != "idle" or self._process is not None or self._scope is not None or self._directory is not None or self._shutting_down:
            raise RuntimeError("실행 중이거나 이전 worker 정리가 끝나지 않았습니다.")
        self._next_token += 1
        self._active_token,self._index = self._next_token,index
        self._intent = self._failure = self._phase = self._stop_deadline = None
        self._exit_drain_deadline = None
        self._kill_requested = False
        self._started = self._clock()
        self.last_record = None
        self.request = self.run_directory = None
        self.state = "running"
        try:
            self.request,self.run_directory = make_request(self.runs_root,index,kind)
            self._temp_parent = Path(tempfile.gettempdir()).resolve()
            # Inherited cleanup checks this exact PREFIX and absolute temp parent.
            self._directory = Path(tempfile.mkdtemp(prefix=PREFIX+"klc0_",dir=self._temp_parent)).resolve()
            (self._directory/"request.pkl").write_bytes(pickle.dumps(
                dict(token=self._active_token,request=self.request),protocol=pickle.HIGHEST_PROTOCOL))
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            self._scope = create_scope()
            command = build_worker_command(*(self._directory/name for name in ("request.pkl","result.pkl","progress.json")),
                                           self._scope.name if self._scope else "")
            with (self._directory/"stderr.txt").open("wb") as stderr:
                self._process = subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,stderr=stderr,
                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0) | (CREATE_SUSPENDED if self._scope else 0))
            if self._scope: self._scope.assign_and_resume(self._process)
        except Exception as exc:
            self._failure = f"STARTUP: {exc!r}"
            print(self._failure,file=sys.stderr,flush=True)
            if self._process is not None: self._request_stop()
        self.timer.start()  # token is returned before any terminal signal
        return self._active_token

    def _read_progress(self):
        if self._directory is None or self.request is None: return
        try:
            path = self._directory/"progress.json"
            if not path.exists() or path.stat().st_size > 16_384: return
            value = json.loads(path.read_text(encoding="utf-8"))
            if (type(value) is dict and type(value.get("token")) is int and value["token"] == self._active_token
                and type(value.get("index")) is int and value["index"] == self._index
                and value.get("run_id") == self.request["run_id"] and value.get("policies") == list(POLICIES)
                and value != self._phase):
                self._phase = value
                if not self._shutting_down: self.progressed.emit(self._active_token,value)
        except (OSError,ValueError): pass

    def _read_result(self):
        path = self._directory/"result.pkl"
        if path.stat().st_size > 8*1024*1024: raise ValueError("Private result exceeds limit.")
        with path.open("rb") as stream:
            value = pickle.load(stream)  # only our contained child, never a user file
            if stream.read(1): raise ValueError("Trailing result bytes.")
        if type(value) is not dict or set(value) != {"token","index","run_id","policies","pair","error"}:
            raise ValueError("Invalid result envelope.")
        if type(value["token"]) is not int or value["token"] != self._active_token:
            raise ValueError("Stale/malformed token.")
        if type(value["index"]) is not int or value["index"] != self._index:
            raise ValueError("Wrong result index.")
        if value["run_id"] != self.request["run_id"] or type(value["policies"]) is not tuple or value["policies"] != POLICIES:
            raise ValueError("Wrong run/policy identity.")
        pair,error = value["pair"],value["error"]
        if type(pair) is ComparePair and error is None:
            pair.__post_init__()
            bind_request(pair,self.request)
            return pair,None
        if pair is None and type(error) is str and error.strip(): return None,error
        raise ValueError("Invalid pair/error combination.")

    def _record(self,status,error,exit_code):
        return {**super()._record(status,error,exit_code),"request":self.request,
                "run_directory":str(self.run_directory) if self.run_directory else None,
                "policies":list(POLICIES)}
