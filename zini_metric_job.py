"""One cancellable Counter ZiNi subprocess; no Qt or presentation policy.

The worker retains calculation authority. Each consumer owns its timer and board
selection policy. Results are delivered once; private job directories also own
any interrupted atomic-result temporary file.
"""

import os
import pickle
from pathlib import Path
import subprocess
import sys
import tempfile

from board_snapshot import BoardSnapshot
from zini_calculator import ZiniNeighborhoodBeamConfig


ZINI_COUNTER_CONFIG = ZiniNeighborhoodBeamConfig(
    ranking_policy="standard_seeded_chain_v1",
    max_evaluations=1000,
    standard_phase_evaluations=500,
    max_seconds=None,
    stall_seconds=None,
    seed=0,
)
ZINI_WORKER_SCRIPT = str(Path(__file__).resolve().with_name("zini_metric_worker.py"))
ZINI_WORKER_TERMINATE_TIMEOUT_SECONDS = 1.0


class ZiniMetricJob:
    """Own at most one child and its files. ``poll`` returns None while pending.

    Callers supply a fresh integer token for each board job. Transport failures
    are result envelopes, not UI exceptions. A completed receipt is consumed
    exactly once. Always call close on board change and owner shutdown.
    """

    def __init__(self):
        self.process = None
        self.token = None
        self.payload_path = None
        self.result_path = None
        self._directory = None
        self._pending_result = None

    @property
    def active(self):
        return self.process is not None or self._pending_result is not None

    def _failure(self, message):
        return {"token": self.token, "clicks": None, "moves": None, "error": message}

    def start(self, snapshot: BoardSnapshot, token: int):
        cleanup_error = self.close()
        if cleanup_error:
            # Do not replace ownership of a child that could not be reaped.
            self.token = token
            self._pending_result = {"token": token, "clicks": None, "moves": None,
                                    "error": cleanup_error}
            return
        self.token = token
        try:
            if type(token) is not int or type(snapshot) is not BoardSnapshot or not snapshot.mines_placed:
                raise ValueError("A finalized BoardSnapshot and integer job token are required.")
            self._directory = tempfile.TemporaryDirectory(prefix="minesweeper_zini_job_")
            self.payload_path = str(Path(self._directory.name) / "payload.pkl")
            self.result_path = str(Path(self._directory.name) / "result.pkl")
            with open(self.payload_path, "wb") as stream:
                pickle.dump({"token": token, "snapshot": snapshot, "config": ZINI_COUNTER_CONFIG},
                            stream, protocol=pickle.HIGHEST_PROTOCOL)
            self.process = subprocess.Popen(
                [sys.executable, "--zini-metric-worker" if getattr(sys, "frozen", False)
                 else ZINI_WORKER_SCRIPT, self.payload_path, self.result_path],
                cwd=os.path.dirname(ZINI_WORKER_SCRIPT),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            result = self._failure(repr(exc))
            self.close()
            self.token = token
            self._pending_result = result

    def poll(self):
        if self._pending_result is not None:
            result, self._pending_result = self._pending_result, None
            if self.process is None:
                self.token = None
            return result
        if self.process is None:
            return None
        try:
            if self.result_path and os.path.exists(self.result_path):
                with open(self.result_path, "rb") as stream:
                    result = pickle.load(stream)
                if type(result) is not dict:
                    raise ValueError("ZiNi worker result must be a dict.")
                if type(result.get("token")) is not int or result["token"] != self.token:
                    raise ValueError("ZiNi worker result token does not match the active job.")
            elif self.process.poll() is None:
                return None
            else:
                result = self._failure(f"worker exited with code {self.process.returncode}")
        except Exception as exc:
            result = self._failure(repr(exc))
        # The atomic result exists before the child's final exit; allow it a
        # short grace period, then use the same bounded cancellation path.
        try:
            if self.process.poll() is None:
                self.process.wait(timeout=0.1)
                self.process = None
        except subprocess.TimeoutExpired:
            pass
        except OSError as exc:
            result = self._failure(repr(exc))
        cleanup_error = self.close()
        if cleanup_error:
            return {"token": result.get("token"), "clicks": None, "moves": None,
                    "error": cleanup_error}
        return result

    def close(self):
        """Cancel/reap before removing files. Safe to call repeatedly.

        If OS process cleanup fails, keep ownership so a later close can retry;
        never discard a possibly live child or remove its payload underneath it.
        """
        try:
            self._close()
        except (OSError, subprocess.TimeoutExpired) as exc:
            return repr(exc)
        return None

    def _close(self):
        process = self.process
        if process is not None:
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=ZINI_WORKER_TERMINATE_TIMEOUT_SECONDS)
                except (subprocess.TimeoutExpired, OSError):
                    process.kill()
                    process.wait(timeout=ZINI_WORKER_TERMINATE_TIMEOUT_SECONDS)
            else:
                process.wait(timeout=0)
        self.process = None
        if self._directory is not None:
            self._directory.cleanup()
        self._directory = None
        self.payload_path = self.result_path = self.token = None
        self._pending_result = None
