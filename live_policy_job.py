"""Parent-owned public Live V1 worker and single-use input admission."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from time import monotonic, sleep

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from experiments.random_expert_exhibition_process import CREATE_SUSPENDED, create_scope
from live_policy import (
    PublicSnapshot, ack_from_dict, ack_to_dict, make_ack, proposal_from_dict,
    snapshot_from_dict, snapshot_to_dict, validate_ack, validate_start_snapshot,
)
from live_policy_transport import MAX_V1_SEQUENCE, message, read_next, write_once
import live_k_policy as k_live


ROOT = Path(__file__).resolve().parent
PREFIX = "minesweeper_live_policy_"
COMPUTE_CAP_SECONDS = 30.0
RESPONSE_CAP_SECONDS = 5.0
EXIT_CAP_SECONDS = 5.0
CANCEL_GRACE_SECONDS = 0.5
EXIT_DRAIN_SECONDS = 0.75


def build_worker_command(directory, run_id, scope_name=""):
    if getattr(sys, "frozen", False):
        return [sys.executable, "--live-policy-worker", str(directory), run_id, scope_name]
    return [sys.executable, "-B", "-m", "live_policy_worker", str(directory), run_id, scope_name]


class LivePolicyJob(QObject):
    proposal_ready = pyqtSignal(object)
    admitted = pyqtSignal(object)
    acknowledged = pyqtSignal(object)
    finished = pyqtSignal(object)

    def __init__(self, parent=None, *, clock=monotonic):
        super().__init__(parent)
        self._clock = clock
        self.state = "idle"
        self.last_record = None
        self.records = []
        self._active_run_id = None
        self._process = self._scope = self._directory = self._temp_parent = None
        self._pending = self._sent_ack = self._expected_snapshot = None
        self._start_snapshot = None
        self._sequence = 0
        self._awaiting = None
        self._intent = self._intent_reason = self._failure = None
        self._deadline = self._stop_deadline = self._exit_drain_deadline = None
        self._finish_exit_deadline = None
        self._terminal_reply = None
        self._started = 0.0
        self._kill_requested = self._shutting_down = False
        self._proposal_count = self._applied_count = self._ack_count = 0
        self._review_proposal_count = self._v1_proposal_count = 0
        self._k_proposal_count = self._validation_count = 0
        self._sent_validation = self._permit = self._accepted_nonce = None
        self.timer = QTimer(self)
        self.timer.setInterval(25)
        self.timer.timeout.connect(self.poll)

    @property
    def pending(self):
        return self._pending

    @property
    def active_run_id(self):
        return self._active_run_id

    @property
    def elapsed(self):
        return max(0.0, self._clock() - self._started) if self._active_run_id else 0.0

    def start(self, snapshot):
        if type(snapshot) is k_live.KSnapshot:
            snapshot = k_live.from_dict(k_live.to_dict(snapshot), k_live.KSnapshot)
            k_live.validate_start_snapshot(snapshot)
        else:
            snapshot = snapshot_from_dict(snapshot_to_dict(snapshot))
            validate_start_snapshot(snapshot)
        if (self.state != "idle" or self._process is not None or self._scope is not None
                or self._directory is not None or self._shutting_down):
            raise RuntimeError("이전 자동 실행 worker의 정리가 끝나지 않았습니다.")
        self._active_run_id = snapshot.run_id
        self._expected_snapshot = snapshot
        self._start_snapshot = snapshot
        self._pending = self._sent_ack = self._terminal_reply = None
        self._intent = self._intent_reason = self._failure = None
        self._stop_deadline = self._exit_drain_deadline = None
        self._finish_exit_deadline = None
        self._kill_requested = False
        self._sequence = 0
        self._awaiting = "PROPOSAL"
        self._proposal_count = self._applied_count = self._ack_count = 0
        self._review_proposal_count = self._v1_proposal_count = 0
        self._k_proposal_count = self._validation_count = 0
        self._sent_validation = self._permit = self._accepted_nonce = None
        self._started = self._clock()
        self._deadline = self._clock() + COMPUTE_CAP_SECONDS
        self.last_record = None
        self.state = "computing"
        try:
            self._temp_parent = Path(tempfile.gettempdir()).resolve()
            self._directory = Path(tempfile.mkdtemp(prefix=PREFIX, dir=self._temp_parent)).resolve()
            write_once(self._directory, "parent", 0,
                       message(snapshot.run_id, 0, "START", self._snapshot_dict(snapshot)))
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["GIT_OPTIONAL_LOCKS"] = "0"
            self._scope = create_scope()
            command = build_worker_command(self._directory, snapshot.run_id,
                                           self._scope.name if self._scope else "")
            with (self._directory / "stderr.txt").open("wb") as stderr:
                self._process = subprocess.Popen(
                    command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=stderr,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    | (CREATE_SUSPENDED if self._scope else 0),
                )
            if self._scope:
                self._scope.assign_and_resume(self._process)
        except Exception as exc:
            self._failure = f"STARTUP: {exc!r}"
            self._request_stop()
        self.timer.start()  # Do not emit before start returns its run identity.
        return snapshot.run_id

    def request(self, snapshot):
        snapshot = (k_live.from_dict(k_live.to_dict(snapshot), k_live.KSnapshot)
                    if self._is_k else snapshot_from_dict(snapshot_to_dict(snapshot)))
        if (self.state != "ready" or self._intent is not None or self._failure
                or self._shutting_down or snapshot != self._expected_snapshot):
            raise ValueError("Fresh request is not the acknowledged current public state.")
        self._send("NEXT", self._snapshot_dict(snapshot), "PROPOSAL", COMPUTE_CAP_SECONDS)
        self.state = "computing"

    @property
    def _is_k(self):
        return type(self._start_snapshot) is k_live.KSnapshot

    @staticmethod
    def _snapshot_dict(snapshot):
        return k_live.to_dict(snapshot) if type(snapshot) is k_live.KSnapshot else snapshot_to_dict(snapshot)

    def validate_pending(self, snapshot, nonce):
        if (not self._is_k or self.state != "pending" or self._pending is None
                or self._intent is not None or self._failure or self._shutting_down):
            raise ValueError("K validation requires an unconsumed pending proposal.")
        k_live.admit_proposal(self._pending, snapshot)
        request = k_live.KValidation(snapshot, self._pending.token, nonce, self._pending.pending_m_revision)
        self._sent_validation = request
        self._accepted_nonce = nonce
        self._permit = None
        self._send("VALIDATE", k_live.to_dict(request), "ADMITTED", RESPONSE_CAP_SECONDS)
        self._validation_count += 1
        self.state = "validating"

    def invalidate_admission(self):
        # Keep the single pending decision and any in-flight deadline. A late
        # response must be drained, but cannot authorize an input after pause.
        if self._is_k:
            self._accepted_nonce = None
            if self.state == "admitted":
                self._permit = None
                self.state = "pending"

    def mark_applying(self, token, nonce=None):
        if (self.state != ("admitted" if self._is_k else "pending") or self._intent is not None or self._failure
                or self._shutting_down or self._pending is None
                or type(token) is not str or token != self._pending.token):
            raise ValueError("Proposal is absent, stale, or already consumed.")
        if self._is_k and (self._permit is None or type(nonce) is not str
                           or nonce != self._accepted_nonce or nonce != self._permit.nonce):
            raise ValueError("K input requires the current worker-admitted nonce.")
        self.state = "applying"
        self._deadline = self._clock() + RESPONSE_CAP_SECONDS
        self._applied_count += 1
        return self._pending

    def acknowledge(self, status, observation=None):
        if (self.state != "applying" or self._intent is not None or self._failure
                or self._shutting_down or self._pending is None):
            raise ValueError("Only a consumed proposal can be acknowledged.")
        try:
            ack = (k_live.make_ack(self._permit, status=status, observation=observation) if self._is_k
                   else make_ack(self._pending, status=status, observation=observation))
            self._sent_ack = ack
            self._send("ACK", k_live.to_dict(ack) if self._is_k else ack_to_dict(ack),
                       "ACKED" if ack.status == "PLAYING" else "FINISHED",
                       RESPONSE_CAP_SECONDS)
            self.state = "acknowledging" if ack.status == "PLAYING" else "finishing"
        except Exception as exc:
            self._fail(f"ACK: {exc!r}")
            raise

    def _send(self, kind, payload, awaiting, cap):
        if self._directory is None or self._awaiting is not None:
            raise RuntimeError("Cannot send while another response is outstanding.")
        try:
            if not self._is_k and self._sequence > MAX_V1_SEQUENCE:
                raise ValueError("V1 transport sequence bound exceeded.")
            write_once(self._directory, "parent", self._sequence,
                       message(self._active_run_id, self._sequence, kind, payload))
        except Exception as exc:
            self._fail(f"REQUEST_TRANSPORT: {exc!r}")
            raise
        self._awaiting = awaiting
        self._deadline = self._clock() + cap

    def cancel(self, reason="CANCELLED"):
        if type(reason) is not str or not reason or len(reason) > 128:
            raise ValueError("Cancellation reason must be a short string.")
        if self._active_run_id is None or self._shutting_down:
            return
        if self._intent is None:
            self._intent, self._intent_reason = "CANCELLED", reason
        self._request_stop()

    def _fail(self, error):
        self._failure = self._failure or error
        self._request_stop()

    def _request_stop(self):
        self.state = "cancelling"
        self._pending = None
        self._permit = self._accepted_nonce = self._sent_validation = None
        self._awaiting = None
        self._deadline = None
        self._finish_exit_deadline = None
        if self._stop_deadline is None:
            self._stop_deadline = self._clock() + CANCEL_GRACE_SECONDS
            if self._process is not None:
                try:
                    self._process.terminate()
                except OSError as exc:
                    self._failure = self._failure or f"TERMINATE: {exc!r}"
            if self._scope is not None:
                try:
                    self._scope.terminate()
                except OSError as exc:
                    self._failure = self._failure or f"TREE_TERMINATE: {exc!r}"

    def _read_reply(self):
        if self._awaiting is None:
            # No child reply is allowed while the owner is choosing when to apply.
            unexpected = read_next(self._directory, "worker", self._sequence, self._active_run_id)
            if unexpected is not None:
                raise ValueError("Unsolicited or duplicate worker reply.")
            return
        value = read_next(self._directory, "worker", self._sequence, self._active_run_id)
        if value is None:
            return
        kind, payload = value["kind"], value["payload"]
        if kind == "ERROR":
            if (type(payload) is not dict or set(payload) != {"code", "detail"}
                    or type(payload["code"]) is not str or not payload["code"]
                    or type(payload["detail"]) is not str or not payload["detail"]
                    or len(payload["code"]) > 128 or len(payload["detail"]) > 16384):
                raise ValueError("Invalid worker error envelope.")
            raise ValueError(f"{payload['code']}: {payload['detail']}")
        if kind != self._awaiting:
            raise ValueError("Worker reply is out of sequence.")
        self._sequence += 1
        self._awaiting = None
        if kind == "PROPOSAL":
            proposal = (k_live.from_dict(payload, k_live.KProposal) if self._is_k else proposal_from_dict(payload))
            if proposal.snapshot != self._expected_snapshot:
                raise ValueError("Worker proposal differs from requested public snapshot.")
            self._pending = proposal
            self._proposal_count += 1
            if self._is_k:
                self._k_proposal_count += 1
            elif proposal.phase == "FLAG_REVIEW":
                self._review_proposal_count += 1
            else:
                self._v1_proposal_count += 1
            self._deadline = None
            self.state = "pending"
            self.proposal_ready.emit(proposal)
        elif kind == "ADMITTED":
            if not self._is_k or self._pending is None or self._sent_validation is None:
                raise ValueError("Unexpected K permit.")
            permit = k_live.from_dict(payload, k_live.KPermit)
            if permit.proposal != self._pending or permit.nonce != self._sent_validation.nonce:
                raise ValueError("K permit differs from requested proposal/nonce.")
            self._sent_validation = None
            self._deadline = None
            self._permit = permit if permit.nonce == self._accepted_nonce else None
            self.state = "admitted" if self._permit is not None else "pending"
            self.admitted.emit(permit)
        elif kind == "ACKED":
            ack = k_live.from_dict(payload, k_live.KAck) if self._is_k else ack_from_dict(payload)
            if ack != self._sent_ack or ack.status != "PLAYING" or self._pending is None:
                raise ValueError("Worker ACK differs from the applied action/target/token.")
            self._expected_snapshot = (k_live.next_snapshot(self._pending, ack) if self._is_k
                                       else validate_ack(self._pending, ack))
            self._pending = self._sent_ack = None
            self._permit = self._accepted_nonce = None
            self._ack_count += 1
            self._deadline = None
            self.state = "ready"
            self.acknowledged.emit(ack)
        else:
            if self._is_k:
                ack = k_live.from_dict(payload, k_live.KAck)
                if self._sent_ack is None or ack != self._sent_ack or ack.status == "PLAYING":
                    raise ValueError("K FINISHED differs from actual terminal ACK.")
            elif (type(payload) is not dict or set(payload) != {"token", "input_seq", "status"}
                    or self._sent_ack is None or self._sent_ack.status == "PLAYING"
                    or type(payload["token"]) is not str
                    or payload["token"] != self._sent_ack.token
                    or type(payload["input_seq"]) is not int
                    or payload["input_seq"] != self._sent_ack.input_seq
                    or type(payload["status"]) is not str
                    or payload["status"] != self._sent_ack.status):
                raise ValueError("Worker terminal receipt differs from the actual terminal ACK.")
            self._terminal_reply = payload
            self._pending = self._sent_ack = None
            self._permit = self._accepted_nonce = None
            self._ack_count += 1
            self._deadline = None
            self._finish_exit_deadline = self._clock() + EXIT_CAP_SECONDS
            self.state = "finishing"

    def poll(self):
        if self._active_run_id is None or self._shutting_down:
            return
        if (self._intent is None and not self._failure and self._deadline is not None
                and self._clock() >= self._deadline):
            self._intent, self._intent_reason = "TIMEOUT", self.state
            self._request_stop()
        if (self._intent is None and not self._failure and self._finish_exit_deadline is not None
                and self._clock() >= self._finish_exit_deadline):
            self._fail("FINISH_EXIT_TIMEOUT: terminal reply received but launcher not reaped.")
        if self._intent is None and not self._failure and self._directory is not None:
            try:
                self._read_reply()
            except Exception as exc:
                self._fail(f"REPLY_TRANSPORT: {exc!r}")
        if self._active_run_id is None or self._shutting_down:
            return
        process = self._process
        if process is None:
            self._finish(self._intent or "FAILED", self._failure or "STARTUP: no child", None)
            return
        try:
            if (self._stop_deadline is not None and self._clock() >= self._stop_deadline
                    and not self._kill_requested):
                self._kill_requested = True
                try:
                    process.kill()
                except OSError as exc:
                    self._failure = self._failure or f"KILL: {exc!r}"
                if self._scope is not None:
                    self._scope.terminate()
            code = process.poll()
            if code is None:
                if self._kill_requested and self._clock() >= self._stop_deadline + 1.0:
                    self.state = "blocked"
                    self._failure = self._failure or "REAP_PENDING: worker ownership retained."
                return
            process.wait(timeout=0)
            if self._active_run_id is None or self._shutting_down:
                return
            reaped_at = self._clock()
            if self._finish_exit_deadline is not None:
                if reaped_at >= self._finish_exit_deadline:
                    self._fail("FINISH_EXIT_TIMEOUT: launcher reap exceeded exit cap.")
                self._finish_exit_deadline = None
            if self._exit_drain_deadline is None:
                self._exit_drain_deadline = reaped_at + EXIT_DRAIN_SECONDS
                # FINISHED can be published between the first read and exit.
                # One last strict read is allowed only before the original ACK
                # deadline, after actual reap, with no stop/failure intent.
                if (self._intent is None and not self._failure
                        and self._awaiting == "FINISHED" and self._terminal_reply is None):
                    ack_deadline = self._deadline
                    if ack_deadline is None or reaped_at >= ack_deadline:
                        self._intent, self._intent_reason = "TIMEOUT", self.state
                        self._request_stop()
                    else:
                        try:
                            self._read_reply()
                        except Exception as exc:
                            self._fail(f"REPLY_TRANSPORT: {exc!r}")
                        if self._intent is None and not self._failure and self._clock() >= ack_deadline:
                            self._intent, self._intent_reason = "TIMEOUT", "finishing"
                            self._request_stop()
                    # This process is already reaped. A last-read receipt may
                    # not start another exit cap or extend the fixed drain.
                    self._finish_exit_deadline = None
            if self._scope is not None and self._scope.active_count:
                if self._clock() >= self._exit_drain_deadline:
                    self._fail("DESCENDANT_REAP: processes remain after fixed exit drain.")
                return
        except subprocess.TimeoutExpired:
            return
        except OSError as exc:
            self._fail(f"REAP: {exc!r}")
            return
        self._process = None
        if self._intent:
            self._finish(self._intent, self._failure, code)
        elif self._failure:
            self._finish("FAILED", self._failure, code)
        elif code != 0:
            self._finish("FAILED", f"WORKER_EXIT: {code}", code)
        elif self._terminal_reply is None:
            self._finish("FAILED", "UNEXPECTED_EXIT: no terminal acknowledgement.", code)
        else:
            self._finish("SUCCEEDED", None, code)

    def _cleanup(self):
        if self._process is not None:
            raise RuntimeError("Cannot clean before child reap.")
        if self._scope is not None:
            if self._scope.active_count:
                raise RuntimeError("Cannot clean while owned descendants remain.")
            self._scope.close()
            self._scope = None
        if self._directory is None:
            return
        directory = self._directory
        if (directory.resolve() != directory or directory.parent != self._temp_parent
                or not directory.name.startswith(PREFIX) or directory.is_symlink()):
            raise RuntimeError(f"Private cleanup path failed containment: {directory}")
        if directory.exists():
            shutil.rmtree(directory)
        self._directory = None

    def _record(self, status, error, exit_code):
        stderr = ""
        if self._directory is not None:
            path = self._directory / "stderr.txt"
            try:
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 16384))
                    stderr = stream.read().decode("utf-8", errors="replace")
            except OSError:
                pass
        try:
            tree_count = self._scope.active_count if self._scope is not None else 0
        except OSError as exc:
            tree_count = None
            error = f"{error or ''}\nTREE_QUERY: {exc!r}"
        return {
            "run_id": self._active_run_id, "status": status, "intent_reason": self._intent_reason,
            "policy_id": self._start_snapshot.policy_id if self._start_snapshot else None,
            "definition": k_live.DEFINITION if self._is_k else "STAGE3_V1",
            "entry_mode": "CANONICAL_NEW" if self._is_k else (self._start_snapshot.entry_mode if self._start_snapshot else None),
            "start_phase": "K_P0" if self._is_k else (self._start_snapshot.phase if self._start_snapshot else None),
            "start_input_revision": self._start_snapshot.input_revision if self._start_snapshot else None,
            "board_generation": self._start_snapshot.board_generation if self._start_snapshot else None,
            "initial_flag_count": 0 if self._is_k else (self._start_snapshot.initial_flag_count if self._start_snapshot else None),
            "wall_seconds": self.elapsed, "error": error, "stderr": stderr,
            "exit_code": exit_code, "reaped": self._process is None,
            "tree_active_count": tree_count, "cleanup_complete": False,
            "proposal_count": self._proposal_count, "consumed_token_count": self._applied_count,
            "preparation_proposal_count": self._review_proposal_count,
            "v1_proposal_count": self._v1_proposal_count,
            "k_proposal_count": self._k_proposal_count, "validation_count": self._validation_count,
            "ack_count": self._ack_count, "terminal": self._terminal_reply,
            "compute_cap_seconds": COMPUTE_CAP_SECONDS,
            "response_cap_seconds": RESPONSE_CAP_SECONDS,
            "finish_exit_cap_seconds": EXIT_CAP_SECONDS,
        }

    def _finish(self, status, error, exit_code):
        self.timer.stop()
        record = self._record(status, error, exit_code)
        try:
            self._cleanup()
        except Exception as exc:
            record.update(status="FAILED", error=f"{error or ''}\nCLEANUP: {exc!r}")
        else:
            record["cleanup_complete"] = True
        self.last_record = record
        self.records.append(record)
        self._active_run_id = None
        self._pending = self._sent_ack = self._expected_snapshot = None
        self._awaiting = self._deadline = None
        self._finish_exit_deadline = None
        self.state = "blocked" if self._directory is not None or self._scope is not None else "idle"
        if not self._shutting_down:
            self.finished.emit(record)

    def shutdown(self):
        """Bounded final teardown; failure retains ownership and prevents close."""
        self._shutting_down = True
        self.timer.stop()
        self._intent, self._intent_reason = "CLOSED", "close"
        self._pending = self._awaiting = None
        self._deadline = self._finish_exit_deadline = None
        process = self._process
        if process is not None:
            self._request_stop()
            try:
                process.wait(timeout=.5)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    process.kill()
                    if self._scope is not None:
                        self._scope.terminate()
                except OSError:
                    pass
                try:
                    process.wait(timeout=1.0)
                except (subprocess.TimeoutExpired, OSError) as exc:
                    self.state = "blocked"
                    self.last_record = self._record("FAILED", f"SHUTDOWN_REAP: {exc!r}", None)
                    raise RuntimeError(self.last_record["error"]) from exc
            self._process = None
        if self._scope is not None:
            try:
                if self._scope.active_count:
                    self._scope.terminate()
                deadline = monotonic() + 1.0
                while self._scope.active_count and monotonic() < deadline:
                    sleep(.01)
                if self._scope.active_count:
                    raise RuntimeError("Owned descendants did not exit.")
            except (OSError, RuntimeError) as exc:
                self.state = "blocked"
                self.last_record = self._record("FAILED", f"SHUTDOWN_TREE_REAP: {exc!r}", None)
                raise RuntimeError(self.last_record["error"]) from exc
        active = self._active_run_id is not None
        record = self._record("CLOSED", self._failure, None) if active else self.last_record
        try:
            self._cleanup()
        except Exception as exc:
            self.state = "blocked"
            self.last_record = self._record("FAILED", f"SHUTDOWN_CLEANUP: {exc!r}", None)
            raise RuntimeError(self.last_record["error"]) from exc
        if record is not None:
            record["cleanup_complete"] = True
            self.last_record = record
            if active:
                self.records.append(record)
        self._active_run_id = None
        self.state = "closed"
