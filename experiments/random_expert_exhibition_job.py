"""One parent-owned child, bounded wall time, atomic private-local transport.

Normal Qt polling never waits. Cancel intent wins over a completed result.
Reap precedes cleanup and delivery; cleanup failures retain ownership/block start.
"""

import json
import os
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import tempfile
from time import monotonic, sleep

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from experiments.random_expert_exhibition_model import ExhibitionPair, validate_index
from experiments.random_expert_exhibition_process import CREATE_SUSPENDED, create_scope


ROOT = Path(__file__).resolve().parents[1]
WALL_CAP_SECONDS = 120.0
CANCEL_GRACE_SECONDS = 0.5
EXIT_DRAIN_SECONDS = 0.75
PREFIX = "minesweeper_random_expert_"


def build_worker_command(payload, result, progress, scope_name=""):
    if getattr(sys, "frozen", False):
        raise RuntimeError("This exhibition launcher supports Python source only.")
    return [sys.executable, "-B", "-m", "experiments.random_expert_exhibition_worker",
            str(payload), str(result), str(progress), scope_name]


class ExhibitionJob(QObject):
    finished = pyqtSignal(object, str, object)
    progressed = pyqtSignal(object, object)

    def __init__(self, parent=None, *, clock=monotonic):
        super().__init__(parent)
        self._clock = clock
        self.state = "idle"
        self.last_record = None
        self.records = []  # small session diagnostics survive starting the next board
        self._next_token = 0
        self._active_token = None
        self._index = None
        self._process = None
        self._scope = None
        self._directory = None
        self._temp_parent = None
        self._intent = None
        self._failure = None
        self._phase = None
        self._started = 0
        self._stop_deadline = None
        self._exit_drain_deadline = None
        self._kill_requested = False
        self._shutting_down = False
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll)

    @property
    def elapsed(self):
        return max(0.0, self._clock() - self._started) if self._active_token is not None else 0.0

    def start(self, index):
        validate_index(index)
        if self.state != "idle" or self._process is not None or self._scope is not None or self._directory is not None or self._shutting_down:
            raise RuntimeError("실행 중이거나 이전 worker 정리가 끝나지 않았습니다.")
        self._next_token += 1
        self._active_token, self._index = self._next_token, index
        self._intent = self._failure = self._phase = self._stop_deadline = None
        self._exit_drain_deadline = None
        self._kill_requested = False
        self._started = self._clock()
        self.last_record = None
        self.state = "running"
        try:
            self._temp_parent = Path(tempfile.gettempdir()).resolve()
            self._directory = Path(tempfile.mkdtemp(prefix=PREFIX, dir=self._temp_parent)).resolve()
            (self._directory / "request.pkl").write_bytes(pickle.dumps(
                {"token": self._active_token, "index": index}, protocol=pickle.HIGHEST_PROTOCOL))
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            self._scope = create_scope()
            command = build_worker_command(*(self._directory / name for name in
                                             ("request.pkl", "result.pkl", "progress.json")),
                                           self._scope.name if self._scope else "")
            with (self._directory / "stderr.txt").open("wb") as stderr:
                self._process = subprocess.Popen(
                    command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=stderr,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | (CREATE_SUSPENDED if self._scope else 0),
                )
            if self._scope:
                self._scope.assign_and_resume(self._process)
        except Exception as exc:
            self._failure = f"STARTUP: {exc!r}"
            if self._process is not None:
                self._request_stop()
        self.timer.start()  # start returns the integer token BEFORE any terminal signal
        return self._active_token

    def cancel(self):
        if self._active_token is None or self._shutting_down:
            return
        self._intent = "CANCELLED"
        self._request_stop()

    def _request_stop(self):
        self.state = "cancelling"
        if self._stop_deadline is None:
            self._stop_deadline = self._clock() + CANCEL_GRACE_SECONDS
            if self._process is not None:
                try:
                    self._process.terminate()
                except OSError as exc:
                    self._failure = f"TERMINATE: {exc!r}"
            if self._scope is not None:
                try:
                    self._scope.terminate()  # Windows venv launcher termination alone leaves real Python alive
                except OSError as exc:
                    self._failure = f"TREE_TERMINATE: {exc!r}"

    def _read_progress(self):
        if self._directory is None:
            return
        path = self._directory / "progress.json"
        try:
            if not path.exists() or path.stat().st_size > 16_384:
                return
            value = json.loads(path.read_text(encoding="utf-8"))
            if (type(value) is dict and type(value.get("token")) is int
                    and value["token"] == self._active_token and type(value.get("index")) is int
                    and value["index"] == self._index and value != self._phase):
                self._phase = value
                if not self._shutting_down:
                    self.progressed.emit(self._active_token, value)
        except (OSError, ValueError):
            pass  # progress is advisory; atomic final result has strict admission

    def poll(self):
        if self._active_token is None or self._shutting_down:
            return
        self._read_progress()
        if self._intent is None and self.elapsed >= WALL_CAP_SECONDS:
            self._intent = "TIMEOUT"
            self._request_stop()
        process = self._process
        if process is None:
            self._finish(self._intent or "FAILED", error=self._failure or "STARTUP: no child")
            return
        try:
            if self._stop_deadline is not None and self._clock() >= self._stop_deadline and not self._kill_requested:
                self._kill_requested = True
                try:
                    process.kill()
                except OSError as exc:
                    self._failure = f"KILL: {exc!r}"
                if self._scope is not None:
                    self._scope.terminate()
            if self._kill_requested and self._clock() >= self._stop_deadline + 1.0:
                self.state = "blocked"
            code = process.poll()
            if code is None:
                if self._kill_requested and self._clock() >= self._stop_deadline + 1.0:
                    self._failure = self._failure or "REAP_PENDING: owned child did not exit after kill; new runs blocked."
                return
            process.wait(timeout=0)
            if self._exit_drain_deadline is None:
                self._exit_drain_deadline = self._clock() + EXIT_DRAIN_SECONDS
            if self._scope is not None and self._scope.active_count:
                # Windows accounting may retain exited members until references drain.
                # Poll without blocking; this fixed grace never extends the wall cap.
                # A genuinely surviving tree must still be terminated/reaped before delivery.
                if self._clock() >= self._exit_drain_deadline:
                    self._failure = self._failure or "DESCENDANT_REAP: contained processes still active after exit drain deadline."
                    self._request_stop()
                return
        except subprocess.TimeoutExpired:
            return
        except OSError as exc:
            self._failure = f"REAP: {exc!r}"
            self._request_stop()
            return
        self._process = None  # only after successful wait/reap
        if self._intent:
            self._finish(self._intent, error=self._failure, exit_code=code)
        elif self._failure:
            self._finish("FAILED", error=self._failure, exit_code=code)
        elif code != 0:
            self._finish("FAILED", error=f"WORKER_EXIT: {code}", exit_code=code)
        else:
            try:
                pair, error = self._read_result()
            except Exception as exc:
                self._finish("FAILED", error=f"RESULT_TRANSPORT: {exc!r}", exit_code=code)
            else:
                self._finish("FAILED" if error else "SUCCEEDED", pair=pair, error=error, exit_code=code)

    def _read_result(self):
        path = self._directory / "result.pkl"
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Exhibition transport exceeds the compact-result limit.")
        with path.open("rb") as stream:
            value = pickle.load(stream)  # owned private child only; never a user-selected path
            if stream.read(1):
                raise ValueError("Trailing result bytes.")
        if type(value) is not dict or set(value) != {"token", "index", "pair", "error"}:
            raise ValueError("Invalid result envelope.")
        if type(value["token"]) is not int or value["token"] != self._active_token:
            raise ValueError("Stale/malformed result token.")
        if type(value["index"]) is not int or value["index"] != self._index:
            raise ValueError("Wrong board index in result.")
        pair, error = value["pair"], value["error"]
        if type(pair) is ExhibitionPair and error is None:
            pair.__post_init__()  # compact structural checks; no engine/exact analysis/profile IO
            if pair.board.index != self._index:
                raise ValueError("Pair identity differs from request.")
            return pair, None
        if pair is None and type(error) is str and error.strip():
            return None, error
        raise ValueError("Invalid pair/error combination.")

    def _cleanup(self):
        if self._process is not None:
            raise RuntimeError("Cannot clean before successful child reap.")
        if self._scope is not None:
            if self._scope.active_count:
                raise RuntimeError("Cannot clean while contained worker descendants remain active.")
            self._scope.close()
            self._scope = None
        if self._directory is None:
            return
        directory = self._directory
        # Validate the final absolute target before recursive Windows deletion.
        if (directory.resolve() != directory or directory.parent != self._temp_parent
                or not directory.name.startswith(PREFIX) or directory.is_symlink()):
            raise RuntimeError(f"Private cleanup path failed containment check: {directory}")
        if directory.exists():
            shutil.rmtree(directory)
        self._directory = None

    def _record(self, status, error, exit_code):
        stderr = ""
        if self._directory is not None:
            path = self._directory / "stderr.txt"
            try:
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 16_384))
                    stderr = stream.read().decode("utf-8", errors="replace")
            except OSError:
                pass
        try:
            tree_count = self._scope.active_count if self._scope is not None else 0
        except OSError as exc:
            tree_count = None
            error = f"{error or ''}\nTREE_QUERY: {exc!r}"
        return {"token": self._active_token, "index": self._index, "status": status,
                "wall_seconds": self.elapsed, "wall_cap_seconds": WALL_CAP_SECONDS,
                "progress": self._phase, "error": error, "exit_code": exit_code,
                "stderr": stderr, "reaped": self._process is None,
                "tree_active_count": tree_count,
                "cleanup_complete": False}

    def _finish(self, status, *, pair=None, error=None, exit_code=None):
        token = self._active_token
        self.timer.stop()
        record = self._record(status, error, exit_code)
        try:
            self._cleanup()
        except Exception as exc:
            status, pair = "FAILED", None
            record.update(status=status, error=f"{error or ''}\nCLEANUP: {exc!r}")
        else:
            record["cleanup_complete"] = True
        self.last_record = record
        self.records.append(record)
        self._active_token = None
        self.state = "blocked" if self._directory is not None else "idle"
        if not self._shutting_down:
            self.finished.emit(token, status, pair if status == "SUCCEEDED" else record)

    def shutdown(self):
        """Final bounded terminate -> kill -> reap; caller rejects close on error."""
        self._shutting_down = True
        self.timer.stop()
        self._intent = "CLOSED"
        process = self._process
        if process is not None:
            self._request_stop()
            try:
                process.wait(timeout=0.5)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    process.kill()
                    if self._scope is not None:
                        self._scope.terminate()
                except OSError:
                    pass  # the following wait decides ownership; an exit race is harmless
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
                    raise RuntimeError("Contained Python descendants did not exit.")
            except (OSError, RuntimeError) as exc:
                self.state = "blocked"
                self.last_record = self._record("FAILED", f"SHUTDOWN_TREE_REAP: {exc!r}", None)
                raise RuntimeError(self.last_record["error"]) from exc
        self._read_progress()
        if self._active_token is not None:
            self.last_record = self._record("CLOSED", self._failure, None)
        try:
            self._cleanup()
        except Exception as exc:
            self.state = "blocked"
            self.last_record = self._record("FAILED", f"SHUTDOWN_CLEANUP: {exc!r}", None)
            raise RuntimeError(self.last_record["error"]) from exc
        if self.last_record is not None:
            self.last_record["cleanup_complete"] = True
        self._active_token = None
        self.state = "closed"
