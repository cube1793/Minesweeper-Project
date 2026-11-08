"""Stage4 protocol atop the existing contained process cleanup lifecycle.

Only generic poll/reap/cleanup/shutdown mechanics are inherited. All wire,
start, state validation, admission and records below are Stage4-specific.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from time import monotonic

from PyQt5.QtCore import QFileSystemWatcher
from experiments.random_expert_exhibition_process import CREATE_SUSPENDED, create_scope
from live_policy_job import LivePolicyJob, ROOT
from stage4_live_contract import (Snapshot, Acknowledgement, POLICY_ID, MAX_SEQUENCE, MAX_INPUTS,
    require, fields, integer, text, envelope, read_next, write_once,
    validate_projection, guard_target, validate_ack)
from stage4_runtime_policy import RuntimeHistory

COMPUTE_RESPONSE_SECONDS=40.0  # RuntimeLimits 35s plus serialization/retrieval allowance.
CONTROL_RESPONSE_SECONDS=5.0
PREFIX="minesweeper_live_policy_stage4_"


def build_worker_command(directory,run_id,scope_name=""):
    tail=["--stage4-live-worker",str(directory),run_id,scope_name]
    return [sys.executable,*tail] if getattr(sys,"frozen",False) else [sys.executable,"-B",str(ROOT/"main.py"),*tail]


class Stage4LiveJob(LivePolicyJob):
    def __init__(self,parent=None,*,clock=monotonic):
        super().__init__(parent,clock=clock)
        self.history=RuntimeHistory()
        self.history_sequence=0
        self.operations=[]
        self.last_ack=None
        self._consumed_nonce=None
        self._owner_record={}

    @property
    def _is_k(self):
        return False

    def start(self,state,history=None):
        require(type(state) is Snapshot,"STAGE4_SNAPSHOT_REQUIRED")
        state=Snapshot.from_dict(state.to_dict())
        require(state.status=="PLAYING","STAGE4_START_TERMINAL")
        require(self.state=="idle" and self._process is None and self._scope is None
                and self._directory is None and not self._shutting_down,"STAGE4_OWNER_NOT_CLEAN")
        history=history or RuntimeHistory()
        require(type(history) is RuntimeHistory and history.scope in (None,(state.game_id,state.game_id)),"STAGE4_HISTORY_BINDING")
        self.history=history;self.history_sequence=0;self.operations=[];self.last_ack=None
        self._active_run_id=state.run_id; self._start_snapshot=self._expected_snapshot=state
        self._pending=self._sent_ack=self._terminal_reply=self._permit=None
        self._sent_validation=self._accepted_nonce=self._consumed_nonce=None
        self._intent=self._intent_reason=self._failure=None
        self._stop_deadline=self._exit_drain_deadline=self._finish_exit_deadline=None
        self._kill_requested=False;self._sequence=0;self._awaiting="PROPOSAL"
        self._proposal_count=self._applied_count=self._ack_count=self._validation_count=0
        self._started=self._clock();self._deadline=self._clock()+COMPUTE_RESPONSE_SECONDS
        self.last_record=None;self.state="computing"
        self._owner_record=dict(run_id=state.run_id,policy_id=POLICY_ID,
            started_utc=datetime.now(timezone.utc).isoformat(),pid=None,scope_name=None,
            suspended=False,assigned_and_resumed=False)
        try:
            self._temp_parent=Path(tempfile.gettempdir()).resolve()
            self._directory=Path(tempfile.mkdtemp(prefix=PREFIX,dir=self._temp_parent)).resolve()
            watcher=QFileSystemWatcher(self)
            if watcher.addPath(str(self._directory)):
                self._reply_watcher=watcher;watcher.directoryChanged.connect(self._on_channel_changed)
            else:
                watcher.deleteLater()
            payload=dict(state=state.to_dict(),history=history.to_payload())
            write_once(self._directory,"parent",0,envelope(state.run_id,0,"START",payload))
            self.operations.append(dict(direction="parent",seq=0,kind="START",payload=payload))
            env=os.environ.copy();env["PYTHONDONTWRITEBYTECODE"]="1";env["GIT_OPTIONAL_LOCKS"]="0"
            self._scope=create_scope()
            self._owner_record["scope_name"]=self._scope.name if self._scope else None
            command=build_worker_command(self._directory,state.run_id,self._scope.name if self._scope else "")
            with (self._directory/"stderr.txt").open("wb") as stderr:
                self._process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,stderr=stderr,
                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)|(CREATE_SUSPENDED if self._scope else 0))
            self._owner_record.update(pid=self._process.pid,suspended=self._scope is not None,command=command)
            if self._scope:
                self._scope.assign_and_resume(self._process)
                self._owner_record["assigned_and_resumed"]=True
        except Exception as exc:
            self._failure=f"STAGE4_STARTUP: {exc!r}";self._request_stop()
        self.timer.start()
        return state.run_id

    def _on_channel_changed(self,directory):
        if (self._directory==Path(directory) and self._awaiting is not None and self.timer.isActive()
                and not self._intent and not self._failure and not self._shutting_down):
            self.poll()

    def _check_sequence(self):
        integer(self._sequence,0,MAX_SEQUENCE)

    def _read_history(self):
        if self._directory is None:
            return
        while True:
            value=read_next(self._directory,"history",self.history_sequence,self._active_run_id)
            if value is None:
                return
            require(value["kind"]=="HISTORY","STAGE4_HISTORY_MESSAGE")
            history=RuntimeHistory.from_payload(value["payload"])
            require(history.scope in (None,(self._start_snapshot.game_id,self._start_snapshot.game_id))
                    and history.attempts>=self.history.attempts
                    and set(history.seen)>=set(self.history.seen),"STAGE4_HISTORY_ROLLBACK")
            if self.history.last_attempt_count is not None:
                require(history.last_attempt_count is not None and history.last_attempt_count>=self.history.last_attempt_count,
                        "STAGE4_HISTORY_COUNT_ROLLBACK")
            self.history=history;self.history_sequence+=1

    def _send(self,kind,payload,awaiting,cap):
        require(self._directory is not None and self._awaiting is None,"STAGE4_RESPONSE_OUTSTANDING")
        self._check_sequence()
        write_once(self._directory,"parent",self._sequence,envelope(self._active_run_id,self._sequence,kind,payload))
        self.operations.append(dict(direction="parent",seq=self._sequence,kind=kind,payload=payload))
        self._awaiting=awaiting;self._deadline=self._clock()+cap

    def request(self,state):
        require(self.state=="ready" and not self._intent and not self._failure and not self._shutting_down
                and state==self._expected_snapshot,"STAGE4_FRESH_ACK_REQUIRED")
        self._send("NEXT",dict(state=state.to_dict()),"PROPOSAL",COMPUTE_RESPONSE_SECONDS)
        self.state="computing"

    def validate_pending(self,state,nonce):
        require(self.state=="pending" and self._pending is not None and state==self._expected_snapshot
                and not self._intent and not self._failure,"STAGE4_PENDING_REQUIRED")
        require(self._sequence<MAX_SEQUENCE,"STAGE4_ACK_SEQUENCE_RESERVATION")
        require(max(state.counted,state.revision,state.event_count)<MAX_INPUTS,"STAGE4_INPUT_LIMIT")
        guard_target(self._pending,state);text(nonce)
        self._accepted_nonce=nonce;self._permit=None
        self._sent_validation=dict(state=state.to_dict(),token=self._pending["token"],nonce=nonce)
        self._send("VALIDATE",self._sent_validation,"ADMITTED",CONTROL_RESPONSE_SECONDS)
        self._validation_count+=1;self.state="validating"

    def invalidate_admission(self):
        self._accepted_nonce=None
        if self.state=="admitted":
            self._permit=None;self.state="pending"

    def mark_applying(self,token,nonce,state):
        require(self.state=="admitted" and self._pending is not None and self._permit is not None
                and not self._intent and not self._failure and not self._shutting_down
                and nonce==self._accepted_nonce==self._permit["nonce"]
                and token==self._pending["token"] and state==self._expected_snapshot,"STAGE4_PERMIT_BINDING")
        require(int(self._clock()*1_000_000_000)<self._permit["deadline_ns"],"STAGE4_PERMIT_EXPIRED")
        guard_target(self._pending,state)
        self._consumed_nonce=nonce;self._permit=None;self._accepted_nonce=None
        self.state="applying";self._applied_count+=1
        self._deadline=self._clock()+CONTROL_RESPONSE_SECONDS
        return self._pending

    def acknowledge(self,ack):
        require(self.state=="applying" and self._pending is not None and not self._intent,"STAGE4_APPLIED_REQUIRED")
        validate_ack(ack,self._expected_snapshot,self._pending,self._consumed_nonce)
        self._sent_ack=ack
        self._send("ACK",ack.to_dict(),"ACKED" if ack.status=="PLAYING" else "FINISHED",CONTROL_RESPONSE_SECONDS)
        self.state="acknowledging" if ack.status=="PLAYING" else "finishing"

    def _read_reply(self):
        self._check_sequence();self._read_history()
        value=read_next(self._directory,"worker",self._sequence,self._active_run_id)
        if value is None:
            return
        require(self._awaiting is not None,"STAGE4_UNSOLICITED_REPLY")
        kind,payload=value["kind"],value["payload"]
        self.operations.append(dict(direction="worker",seq=self._sequence,kind=kind,payload=payload))
        if kind=="ERROR":
            fields(payload,"code detail");text(payload["code"]);text(payload["detail"],2048)
            raise ValueError(payload["code"]+": "+payload["detail"])
        require(kind==self._awaiting,"STAGE4_REPLY_ORDER")
        self._sequence+=1;self._awaiting=None;self._deadline=None
        if kind=="PROPOSAL":
            self._pending=validate_projection(payload,self._expected_snapshot)
            require(payload["attempts"]==self.history.attempts,"STAGE4_HISTORY_NOT_SETTLED")
            self._proposal_count+=1;self.state="pending"
            self.proposal_ready.emit(payload)
        elif kind=="ADMITTED":
            fields(payload,"proposal nonce deadline_ns")
            require(payload["proposal"]==self._pending and self._sent_validation is not None
                    and payload["nonce"]==self._sent_validation["nonce"],"STAGE4_PERMIT_REPLY")
            integer(payload["deadline_ns"],1,2**63-1)
            require(payload["deadline_ns"]<=int((self._clock()+6)*1_000_000_000),"STAGE4_PERMIT_DEADLINE")
            self._permit=payload if payload["nonce"]==self._accepted_nonce else None
            self._sent_validation=None;self.state="admitted" if self._permit else "pending"
            self.admitted.emit(payload)
        else:
            ack=Acknowledgement.from_dict(payload)
            require(ack==self._sent_ack and self._pending is not None,"STAGE4_ACK_REPLY")
            self._expected_snapshot=validate_ack(ack,self._expected_snapshot,self._pending,self._consumed_nonce)
            self.last_ack=ack;self._ack_count+=1
            self._pending=self._sent_ack=self._permit=self._consumed_nonce=None
            if kind=="FINISHED":
                require(ack.status!="PLAYING","STAGE4_TERMINAL_ACK")
                self._terminal_reply=payload;self._finish_exit_deadline=self._clock()+5.0;self.state="finishing"
            else:
                require(ack.status=="PLAYING","STAGE4_PLAYING_ACK")
                self.state="ready"
            self.acknowledged.emit(ack)

    def _record(self,status,error,exit_code):
        try:
            self._read_history()
        except Exception as exc:
            error=f"{error or ''} HISTORY: {exc!r}"
        stderr=""
        if self._directory is not None and (self._directory/"stderr.txt").exists():
            with (self._directory/"stderr.txt").open("rb") as stream:
                stream.seek(max(0,(self._directory/"stderr.txt").stat().st_size-8192))
                stderr=stream.read().decode("utf-8",errors="replace")
        try:
            active=self._scope.active_count if self._scope else 0
        except OSError as exc:
            active=None;error=f"{error or ''} TREE: {exc!r}"
        return dict(self._owner_record,status=status,error=error,intent_reason=self._intent_reason,
            exit_code=exit_code,reaped=self._process is None,tree_active_count=active,
            cleanup_complete=False,stderr=stderr,history=self.history.to_payload(),
            operations=list(self.operations),proposal_count=self._proposal_count,
            consumed_token_count=self._applied_count,ack_count=self._ack_count,
            last_ack=None if self.last_ack is None else self.last_ack.to_dict(),
            wall_seconds=self.elapsed,compute_response_seconds=COMPUTE_RESPONSE_SECONDS)

    def _cleanup(self):
        self._read_history()  # A bad/missing history chain retains the channel, never resets quota.
        super()._cleanup()

    def shutdown(self):
        # The GUI first revokes future input. Drain an actual input's ACK before
        # generic shutdown; polling here does not yield Qt or create a new input.
        if self.state in ("acknowledging","finishing") and self._sent_ack is not None:
            from time import sleep
            deadline=monotonic()+CONTROL_RESPONSE_SECONDS
            while self._sent_ack is not None and self._active_run_id is not None and monotonic()<deadline:
                self.poll();sleep(.005)
            require(self._sent_ack is None,"STAGE4_CLOSE_ACK_UNCONFIRMED")
        super().shutdown()
