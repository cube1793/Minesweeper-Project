"""Parent-owned sequential runner for additional Same-board algorithms.

One child process per algorithm, one at a time, in the fixed registry order.
Each child has its own limit (``LIMIT_SECONDS``) and the whole queue the sum of
the selected limits; a child past its limit is terminated and recorded as
LIMIT. Cancellation terminates the current child and records it and every
pending algorithm as CANCELLED; finished results are kept. Normal execution and
cancellation only poll; bounded waits belong to final shutdown.

Every outcome, including LIMIT/CANCELLED/ERROR, arrives as an ``AlgorithmRun``
through ``run_finished(token, run)``; played runs are validated in the parent
with ``validate_run`` before they are emitted.
"""

from dataclasses import replace
import os
import pickle
import shutil
import subprocess
import tempfile
import time

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from replay_model import ReplayBoard
from same_board_algorithm_worker import build_worker_command
from same_board_algorithms import (
    ALGORITHMS, LIMIT_SECONDS, AlgorithmRun, not_run, settings_for, validate_run,
)


WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "same_board_algorithm_worker.py")
POLL_INTERVAL_MS = 100
TERMINATE_GRACE_SECONDS = 0.5
SHUTDOWN_TERMINATE_SECONDS = 0.5
SHUTDOWN_KILL_SECONDS = 1.0


class SameBoardAlgorithmQueue(QObject):
    run_finished = pyqtSignal(object, object)
    finished = pyqtSignal(object)

    def __init__(self, parent=None, *, clock=time.monotonic):
        super().__init__(parent)
        self.state = "idle"
        self.last_diagnostic = None
        self._clock = clock
        self._next_token = 0
        self._active_token = None
        self._board = None
        self._r_target = None
        self._pending = []
        self._current = None
        self._process = None
        self._job_dir = None
        self._result_path = None
        self._deadline = None
        self._overall_deadline = None
        self._started = None
        self._limit_detail = None
        self._cancel_requested = False
        self._terminate_requested = False
        self._kill_requested = False
        self._kill_deadline = None
        self._closed = False
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)

    @property
    def active_token(self):
        return self._active_token

    @property
    def current_algorithm(self):
        return self._current

    def start(self, board: ReplayBoard, algorithms, r_target: str | None = None) -> int:
        if self._closed:
            raise RuntimeError("Same-board algorithm queue is closed.")
        if self.state != "idle" or self._process is not None:
            raise RuntimeError("A Same-board algorithm run is already active.")
        if type(board) is not ReplayBoard:
            raise ValueError("A ReplayBoard is required.")
        selected = tuple(algorithms)
        if not selected or len(set(selected)) != len(selected) or not set(selected) <= set(ALGORITHMS):
            raise ValueError("Select distinct known algorithms.")
        self._next_token += 1
        self._active_token = self._next_token
        self._board = board
        self._r_target = r_target
        self._pending = [name for name in ALGORITHMS if name in selected]
        self._overall_deadline = self._clock() + sum(LIMIT_SECONDS[name] for name in selected)
        self._cancel_requested = False
        self.last_diagnostic = None
        self.state = "running"
        self._poll_timer.start()
        token = self._active_token
        self._start_next()
        return token

    def cancel(self):
        """Record intent first; the next poll terminates and accounts the child."""
        if self.state != "running":
            return
        self._cancel_requested = True
        self.state = "cancelling"
        if self._process is not None:
            self._request_terminate()
        else:
            self._start_next()

    def _settings(self, algorithm):
        try:
            return settings_for(algorithm, self._r_target if algorithm == "S4_R" else None)
        except Exception:
            return ()

    def _emit(self, run: AlgorithmRun):
        self.run_finished.emit(self._active_token, run)

    def _start_next(self):
        while self._active_token is not None and self._process is None:
            if not self._pending:
                token = self._active_token
                self._finish_queue()
                self.finished.emit(token)
                return
            algorithm = self._pending.pop(0)
            if self._cancel_requested:
                self._emit(not_run(algorithm, "CANCELLED", "Cancelled before start.",
                                   settings=self._settings(algorithm)))
                continue
            now = self._clock()
            if now >= self._overall_deadline:
                self._emit(not_run(algorithm, "LIMIT", "Overall limit reached before start.",
                                   settings=self._settings(algorithm)))
                continue
            try:
                self._launch(algorithm)
            except Exception as exc:
                self._process = None
                detail = f"Worker start failed: {exc!r}"
                try:
                    self._cleanup_directory()
                except RuntimeError as cleanup:
                    detail += f"; {cleanup}"
                self._current = None
                self._emit(not_run(algorithm, "ERROR", detail, settings=self._settings(algorithm)))
                continue
            limit = LIMIT_SECONDS[algorithm]
            if now + limit <= self._overall_deadline:
                self._deadline, self._limit_detail = now + limit, f"Algorithm limit {limit:g} s reached."
            else:
                self._deadline, self._limit_detail = self._overall_deadline, "Overall limit reached."
            self._started = now
            return

    def _launch(self, algorithm):
        self._current = algorithm
        self._terminate_requested = self._kill_requested = False
        self._kill_deadline = None
        self._job_dir = tempfile.mkdtemp(prefix="minesweeper_same_board_algorithm_")
        payload_path = os.path.join(self._job_dir, "payload.pkl")
        self._result_path = os.path.join(self._job_dir, "result.pkl")
        with open(payload_path, "wb") as payload_file:
            pickle.dump({"token": self._active_token, "board": self._board, "algorithm": algorithm,
                         "r_target": self._r_target if algorithm == "S4_R" else None},
                        payload_file, protocol=pickle.HIGHEST_PROTOCOL)
        self._process = subprocess.Popen(
            build_worker_command(payload_path, self._result_path),
            cwd=os.path.dirname(WORKER_SCRIPT),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _request_terminate(self):
        if self._process is not None and not self._terminate_requested:
            self._terminate_requested = True
            self._kill_deadline = self._clock() + TERMINATE_GRACE_SECONDS
            try:
                self._process.terminate()
            except OSError as exc:
                self.last_diagnostic = f"Terminate failed: {exc!r}"

    def _poll(self):
        process = self._process
        if process is None or self._active_token is None:
            return
        try:
            exit_code = process.poll()
            if exit_code is None:
                now = self._clock()
                if not self._terminate_requested and now >= self._deadline:
                    self._request_terminate()
                elif (self._terminate_requested and not self._kill_requested
                      and now >= self._kill_deadline):
                    self._kill_requested = True
                    try:
                        process.kill()
                    except OSError as exc:
                        self.last_diagnostic = f"Kill failed: {exc!r}"
                return
            exit_code = process.wait(timeout=0)
        except subprocess.TimeoutExpired:
            return
        except OSError as exc:
            self.last_diagnostic = f"Reap failed: {exc!r}"
            self._request_terminate()
            return
        self._process = None  # Only after a successful reap.
        algorithm, elapsed = self._current, round(self._clock() - self._started, 3)
        settings = self._settings(algorithm)
        if self._cancel_requested:
            run = not_run(algorithm, "CANCELLED", "Cancelled while running.", settings=settings,
                          elapsed_seconds=elapsed)
        elif self._terminate_requested:
            run = not_run(algorithm, "LIMIT", self._limit_detail, settings=settings, elapsed_seconds=elapsed)
        elif exit_code != 0:
            run = not_run(algorithm, "ERROR", f"Worker exited with code {exit_code}.",
                          settings=settings, elapsed_seconds=elapsed)
        else:
            try:
                run = self._read_result(algorithm, elapsed)
            except Exception as exc:
                run = not_run(algorithm, "ERROR", f"Result rejected: {exc!r}"[:2048],
                              settings=settings, elapsed_seconds=elapsed)
        try:
            self._cleanup_directory()
        except RuntimeError as exc:
            self.last_diagnostic = str(exc)
        self._current = None
        self._emit(run)
        self._start_next()

    def _read_result(self, algorithm, elapsed):
        with open(self._result_path, "rb") as result_file:
            envelope = pickle.load(result_file)
            if result_file.read(1):
                raise ValueError("Worker result must contain exactly one envelope.")
        if type(envelope) is not dict or set(envelope) != {"token", "run", "error"}:
            raise ValueError("Worker result has invalid fields.")
        token = envelope["token"]
        if type(token) is not int or token != self._active_token:
            raise ValueError("Worker result token does not match the active request.")
        run, error = envelope["run"], envelope["error"]
        if run is None and isinstance(error, str) and error.strip():
            return not_run(algorithm, "ERROR", error[:2048], settings=self._settings(algorithm),
                           elapsed_seconds=elapsed)
        if type(run) is not AlgorithmRun or error is not None or run.algorithm != algorithm:
            raise ValueError("Worker result has an invalid run/error combination.")
        return replace(validate_run(self._board, run), elapsed_seconds=elapsed)

    def _cleanup_directory(self):
        if self._process is not None:
            raise RuntimeError("Cannot clean algorithm files before the child is reaped.")
        if self._job_dir is not None:
            try:
                shutil.rmtree(self._job_dir)
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise RuntimeError(f"Algorithm temp cleanup failed ({self._job_dir}): {exc!r}") from exc
        self._job_dir = None
        self._result_path = None

    def _finish_queue(self):
        self._poll_timer.stop()
        self._active_token = None
        self._board = None
        self._pending = []
        self._current = None
        self.state = "idle"

    def shutdown(self):
        """Bounded final reaping without terminal signals; raises if a child survives."""
        self._closed = True
        self._poll_timer.stop()
        process = self._process
        if process is not None:
            try:
                process.terminate()
            except OSError:
                pass
            try:
                process.wait(timeout=SHUTDOWN_TERMINATE_SECONDS)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    process.kill()
                except OSError as exc:
                    self.last_diagnostic = f"Shutdown kill failed: {exc!r}"
                try:
                    process.wait(timeout=SHUTDOWN_KILL_SECONDS)
                except (subprocess.TimeoutExpired, OSError) as exc:
                    self.last_diagnostic = f"Shutdown could not reap owned child: {exc!r}"
                    raise RuntimeError(self.last_diagnostic) from exc
            self._process = None
        self._cleanup_directory()
        self._finish_queue()
