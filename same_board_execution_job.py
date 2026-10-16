"""Parent-owned Same-board subprocess and trusted-local result transport.

The original admitted Human context stays in the parent. Only its fixed board
and integer request token enter the private worker payload. Native solver
evidence is validated/composed with that same context after reaping.

Normal execution and cancellation only poll; bounded waits are reserved for
final shutdown. Files remain owned until the child is reaped and the complete
private directory has been removed.
"""

import os
import pickle
import shutil
import subprocess
import tempfile
import time

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from same_board_comparison import HumanComparisonContext
from same_board_runner import SolverExecution, compose_same_board_execution
from same_board_execution_worker import build_worker_command


WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "same_board_execution_worker.py")
POLL_INTERVAL_MS = 100
CANCEL_GRACE_SECONDS = 0.5
SHUTDOWN_TERMINATE_SECONDS = 0.5
SHUTDOWN_KILL_SECONDS = 1.0


class SameBoardExecutionJob(QObject):
    """Own at most one child; signal completion only after reaping/cleanup.

    ``start`` returns its token before any terminal signal, including startup
    errors. ``shutdown`` emits no terminal signals and raises on an OS cleanup
    or reap failure, retaining ownership so the caller can reject close/retry.
    A cleanup failure blocks start and retains its directory for shutdown retry.
    """

    succeeded = pyqtSignal(object, object)
    failed = pyqtSignal(object, str)
    cancelled = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = "idle"
        self.last_diagnostic = None
        self._next_token = 0
        self._active_token = None
        self._context = None
        self._process = None
        self._job_dir = None
        self._payload_path = None
        self._result_path = None
        self._failure = None
        self._cancel_requested = False
        self._terminate_requested = False
        self._kill_requested = False
        self._cancel_deadline = None
        self._shutting_down = False
        self._closed = False
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)

    def start(self, context: HumanComparisonContext) -> int:
        if self._closed or self._shutting_down:
            raise RuntimeError("Same-board job is shutting down.")
        if self.state != "idle" or self._process is not None:
            raise RuntimeError("A Same-board execution is already active.")
        self._next_token += 1
        self._active_token = self._next_token
        self.state = "running"
        self.last_diagnostic = None
        self._failure = None
        self._cancel_requested = False
        self._terminate_requested = False
        self._kill_requested = False
        self._cancel_deadline = None
        try:
            # No new directory is allocated while any earlier path is owned.
            self._cleanup_directory()
            if not isinstance(context, HumanComparisonContext):
                raise ValueError("An admitted HumanComparisonContext is required.")
            self._context = context
            self._job_dir = tempfile.mkdtemp(prefix="minesweeper_same_board_job_")
            self._payload_path = os.path.join(self._job_dir, "payload.pkl")
            self._result_path = os.path.join(self._job_dir, "result.pkl")
            with open(self._payload_path, "wb") as payload_file:
                pickle.dump({"token": self._active_token, "board": context.layout.board},
                            payload_file, protocol=pickle.HIGHEST_PROTOCOL)
            self._process = subprocess.Popen(
                build_worker_command(self._payload_path, self._result_path),
                cwd=os.path.dirname(WORKER_SCRIPT),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as exc:
            self._failure = f"Same-board worker start failed: {exc!r}"
        self._poll_timer.start()
        return self._active_token

    def cancel(self):
        """Record user intent before requesting termination; never wait here."""
        if self.state != "running" or self._shutting_down:
            return
        self._cancel_requested = True
        self.state = "cancelling"
        self._request_terminate()

    def _request_terminate(self):
        if self._cancel_deadline is None:
            self._cancel_deadline = time.monotonic() + CANCEL_GRACE_SECONDS
        if self._process is not None and not self._terminate_requested:
            self._terminate_requested = True
            try:
                self._process.terminate()
            except OSError as exc:
                # The exit/terminate race is resolved by the next poll. A child
                # that remains alive still reaches the fixed kill deadline.
                self.last_diagnostic = f"Same-board terminate failed: {exc!r}"

    def _poll(self):
        if self._shutting_down or self._active_token is None:
            return
        process = self._process
        if process is None:
            self._finish("cancelled" if self._cancel_requested else "failed", self._failure)
            return
        try:
            exit_code = process.poll()
            if exit_code is None:
                if (self.state == "cancelling" and not self._kill_requested
                        and time.monotonic() >= self._cancel_deadline):
                    self._kill_requested = True
                    try:
                        process.kill()
                    except OSError as exc:
                        self.last_diagnostic = f"Same-board kill failed: {exc!r}"
                return
            # poll establishes exit; timeout=0 never blocks normal Qt work.
            exit_code = process.wait(timeout=0)
        except subprocess.TimeoutExpired:
            return
        except OSError as exc:
            self._failure = f"Same-board process reap failed: {exc!r}"
            self.last_diagnostic = self._failure
            self.state = "cancelling"
            self._request_terminate()
            return
        self._process = None  # Only after a successful reap.
        if self._cancel_requested:
            self._finish("cancelled")
        elif self._failure:
            self._finish("failed", self._failure)
        elif exit_code != 0:
            self._finish("failed", f"Same-board worker exited with code {exit_code}.")
        else:
            try:
                execution, error = self._read_result()
            except Exception as exc:
                self._finish("failed", f"Same-board result transport failed: {exc!r}")
            else:
                self._finish("failed", error) if error is not None else self._finish("succeeded", execution)

    def _read_result(self):
        with open(self._result_path, "rb") as result_file:
            envelope = pickle.load(result_file)
            if result_file.read(1):
                raise ValueError("Worker result must contain exactly one envelope.")
        if type(envelope) is not dict:
            raise ValueError("Worker result must be a dict.")
        if set(envelope) != {"token", "solver_execution", "error"}:
            raise ValueError("Worker result has invalid fields.")
        # bool/float equality must not impersonate the integer transport token.
        token = envelope["token"]
        if type(token) is not int or token != self._active_token:
            raise ValueError("Worker result token does not match the active request.")
        execution, error = envelope["solver_execution"], envelope["error"]
        if isinstance(execution, SolverExecution) and error is None:
            return compose_same_board_execution(self._context, execution), None
        if execution is None and isinstance(error, str) and error.strip():
            return None, error
        raise ValueError("Worker result has an invalid execution/error combination.")

    def _cleanup_directory(self):
        """Never abandon a path on failure or delete before successful reap."""
        if self._process is not None:
            raise RuntimeError("Cannot clean Same-board files before the child is reaped.")
        if self._job_dir is not None:
            try:
                shutil.rmtree(self._job_dir)
            except FileNotFoundError as exc:
                if os.path.exists(self._job_dir):
                    raise RuntimeError(f"Same-board temp cleanup failed ({self._job_dir}): {exc!r}") from exc
            except OSError as exc:
                raise RuntimeError(f"Same-board temp cleanup failed ({self._job_dir}): {exc!r}") from exc
        self._job_dir = None
        self._payload_path = None
        self._result_path = None

    def _finish(self, outcome, value=None):
        token = self._active_token
        if token is None:
            return
        self._poll_timer.stop()
        try:
            self._cleanup_directory()
        except RuntimeError as exc:
            outcome, value = "failed", f"{value}; {exc}" if outcome == "failed" and value else str(exc)
        self._active_token = None
        self._context = None
        self.state = "cancelling" if self._job_dir is not None else "idle"
        self.last_diagnostic = value if outcome == "failed" else self.last_diagnostic
        if self._shutting_down:
            return
        if outcome == "succeeded":
            self.succeeded.emit(token, value)
        elif outcome == "cancelled":
            self.cancelled.emit(token)
        else:
            self.failed.emit(token, value or "Same-board worker failed.")

    def shutdown(self):
        """Bounded final reaping; a failed close retains ownership for retry.

        At most 0.5 s terminate grace plus 1.0 s kill/reap grace per call.
        If the OS refuses reaping, the owning window must reject its close.
        """
        self._shutting_down = True
        self._poll_timer.stop()
        process = self._process
        if process is not None:
            self.state = "cancelling"
            self._cancel_requested = True
            self._request_terminate()
            try:
                process.wait(timeout=SHUTDOWN_TERMINATE_SECONDS)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    process.kill()
                except OSError as exc:
                    self.last_diagnostic = f"Same-board shutdown kill failed: {exc!r}"
                try:
                    process.wait(timeout=SHUTDOWN_KILL_SECONDS)
                except (subprocess.TimeoutExpired, OSError) as exc:
                    self.last_diagnostic = f"Same-board shutdown could not reap owned child: {exc!r}"
                    raise RuntimeError(self.last_diagnostic) from exc
            self._process = None
        try:
            self._cleanup_directory()
        except RuntimeError as exc:
            self.last_diagnostic = str(exc)
            raise
        self._active_token = None
        self._context = None
        self.state = "idle"
        self._closed = True
