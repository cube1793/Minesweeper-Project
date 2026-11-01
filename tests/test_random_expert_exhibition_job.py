"""Transport races and real bounded child reap; no Expert solver pilot here."""

import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication
from experiments import random_expert_exhibition_job as jobs
from experiments import random_expert_exhibition_worker as worker
from tests.test_random_expert_exhibition_execution import synthetic_expert_pair


class ExhibitionJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.pair = synthetic_expert_pair()

    def setUp(self):
        self.now = 0.0
        self.job = jobs.ExhibitionJob(clock=lambda: self.now)
        self.finished = QSignalSpy(self.job.finished)
        self.addCleanup(self.job.shutdown)

    def launch(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        with patch.object(jobs.subprocess, "Popen", return_value=process) as popen, \
                patch.object(jobs, "create_scope", return_value=None):
            token = self.job.start(11)
        return token, process, self.job._directory, popen

    def publish(self, **overrides):
        value = {"token": self.job._active_token, "index": 11, "pair": self.pair, "error": None}
        value.update(overrides)
        worker.write_atomic(self.job._directory / "result.pkl", value)

    def finish(self, process, code=0):
        process.poll.return_value = code
        process.wait.return_value = code
        self.job.poll()

    def begin_drain(self):
        token, process, directory, _ = self.launch()
        self.publish()
        scope = Mock(active_count=1)
        self.job._scope = scope
        self.addCleanup(lambda: setattr(scope, "active_count", 0))
        self.finish(process)
        self.assertFalse(self.finished)
        self.assertTrue(directory.exists())
        self.assertIsNone(self.job._failure)
        return token, process, directory, scope

    def test_exit_accounting_drains_without_discarding_success(self):
        token, process, directory, scope = self.begin_drain()
        deadline = self.job._exit_drain_deadline
        self.assertEqual(deadline, jobs.EXIT_DRAIN_SECONDS)
        self.now = deadline - .001
        self.job.poll()
        self.assertEqual(self.job._exit_drain_deadline, deadline)
        scope.active_count = 0
        at_signal = []
        self.job.finished.connect(lambda *args: at_signal.append(
            (self.job._process, self.job._scope, directory.exists())))
        self.job.poll()
        self.job.poll()
        self.assertEqual(len(self.finished), 1)
        self.assertEqual(self.finished[0], [token, "SUCCEEDED", self.pair])
        self.assertEqual(at_signal, [(None, None, False)])
        scope.terminate.assert_not_called()
        process.terminate.assert_not_called()
        self.assertIsNone(self.job.last_record["error"])

    def test_persistent_tree_at_exact_drain_deadline_is_terminated_before_delivery(self):
        _, process, directory, scope = self.begin_drain()
        deadline = self.job._exit_drain_deadline
        with patch.object(self.job, "_read_result", side_effect=AssertionError("cannot install")):
            self.now = deadline - .001
            self.job.poll()
            scope.terminate.assert_not_called()
            self.now = deadline
            self.job.poll()
            self.assertIn("DESCENDANT_REAP", self.job._failure)
            scope.terminate.assert_called_once()
            process.terminate.assert_called_once()
            self.assertFalse(self.finished)
            self.assertTrue(directory.exists())
            self.assertIs(self.job._process, process)
            self.now += jobs.CANCEL_GRACE_SECONDS
            self.job.poll()
            process.kill.assert_called_once()
            self.assertEqual(scope.terminate.call_count, 2)
            self.assertFalse(self.finished)
            self.assertEqual(self.job._exit_drain_deadline, deadline)
            scope.active_count = 0
            self.job.poll()
        self.assertEqual(self.finished[0][1], "FAILED")
        self.assertEqual(self.job.last_record["tree_active_count"], 0)
        self.assertTrue(self.job.last_record["cleanup_complete"])
        self.assertFalse(directory.exists())
        self.assertTrue(all(call.kwargs == {"timeout": 0} for call in process.wait.call_args_list))

    def test_zero_count_at_exact_drain_deadline_still_succeeds(self):
        _, _, _, scope = self.begin_drain()
        self.now = self.job._exit_drain_deadline
        scope.active_count = 0
        self.job.poll()
        self.assertEqual(self.finished[0][1], "SUCCEEDED")
        scope.terminate.assert_not_called()

    def test_drain_preserves_original_worker_error(self):
        _, _, _, scope = self.begin_drain()
        self.publish(index=99999, pair=None, error="VALIDATING: invalid request")
        self.now = .05
        scope.active_count = 0
        self.job.poll()
        self.assertEqual(self.finished[0][1], "FAILED")
        self.assertIn("Wrong board index", self.job.last_record["error"])
        self.assertNotIn("DESCENDANT_REAP", self.job.last_record["error"])

    def test_cancel_during_drain_wins_once_over_completed_result(self):
        _, _, directory, scope = self.begin_drain()
        self.now = .1
        self.job.cancel()
        scope.terminate.assert_called_once()
        scope.active_count = 0
        with patch.object(self.job, "_read_result", side_effect=AssertionError("cannot install")):
            self.job.poll()
            self.job.poll()
        self.assertEqual(len(self.finished), 1)
        self.assertEqual(self.finished[0][1], "CANCELLED")
        self.assertIsNone(self.job.last_record["error"])
        self.assertFalse(directory.exists())

    def test_wall_cap_preempts_drain_and_cleanup_may_finish_after_cap(self):
        _, process, directory, _ = self.launch()
        self.publish()
        scope = Mock(active_count=1)
        self.job._scope = scope
        self.addCleanup(lambda: setattr(scope, "active_count", 0))
        self.now = 119.75
        self.finish(process)
        self.assertEqual(self.job._exit_drain_deadline, 120.5)
        self.now = 119.999
        self.job.poll()
        scope.terminate.assert_not_called()
        self.assertIsNone(self.job._intent)
        self.now = 120.0
        self.job.poll()
        self.assertEqual(self.job._intent, "TIMEOUT")
        scope.terminate.assert_called_once()
        self.assertFalse(self.finished)
        self.assertTrue(directory.exists())
        self.now = 120.05
        scope.active_count = 0
        with patch.object(self.job, "_read_result", side_effect=AssertionError("cannot install")):
            self.job.poll()
        self.assertEqual(self.finished[0][1], "TIMEOUT")
        self.assertEqual(self.job.last_record["wall_cap_seconds"], 120.0)
        self.assertEqual(self.job.last_record["wall_seconds"], 120.05)
        self.assertIsNone(self.job.last_record["error"])
        self.assertFalse(directory.exists())

    def test_shutdown_during_drain_cleans_without_completion(self):
        _, process, directory, scope = self.begin_drain()
        scope.terminate.side_effect = lambda: setattr(scope, "active_count", 0)
        self.job.shutdown()
        self.job.poll()
        self.assertFalse(self.finished)
        self.assertEqual(self.job.last_record["status"], "CLOSED")
        self.assertTrue(self.job.last_record["cleanup_complete"])
        self.assertEqual(self.job.state, "closed")
        self.assertFalse(directory.exists())
        process.wait.assert_called_with(timeout=.5)

    def test_next_start_resets_exit_drain_deadline(self):
        _, _, _, scope = self.begin_drain()
        scope.active_count = 0
        self.job.poll()
        self.now = 10.0
        _, process, _, _ = self.launch()
        self.assertIsNone(self.job._exit_drain_deadline)
        self.job.poll()
        self.assertIsNone(self.job._exit_drain_deadline)
        self.publish()
        self.finish(process)
        self.assertEqual(self.job._exit_drain_deadline, 10.0 + jobs.EXIT_DRAIN_SECONDS)
        self.assertEqual([item[1] for item in self.finished], ["SUCCEEDED", "SUCCEEDED"])

    def test_tokenless_failure_retains_bounded_stderr_cause_without_installing_pair(self):
        _, process, directory, _ = self.launch()
        cause = "REQUEST_TRANSPORT: verify_worker_scope: FileNotFoundError: [WinError 2]"
        self.publish(token=None, index=None, pair=None, error=cause)
        (directory / "stderr.txt").write_text("x" * 20_000 + "\n" + cause, encoding="utf-8")
        self.finish(process)
        self.assertEqual(self.finished[0][1], "FAILED")
        self.assertIn("Stale/malformed result token", self.job.last_record["error"])
        self.assertIn(cause, self.job.last_record["stderr"])
        self.assertEqual(len(self.job.last_record["stderr"].encode("utf-8")), 16_384)
        self.assertTrue(self.job.last_record["cleanup_complete"])

    def test_malformed_envelope_and_contradictory_pair_error_never_succeed(self):
        for value in ([], {"token": 1},
                      {"token": 0, "index": 11, "pair": self.pair, "error": "also error"},
                      {"token": 0, "index": 11, "pair": None, "error": None}):
            with self.subTest(value_type=type(value).__name__):
                _, process, directory, _ = self.launch()
                if type(value) is dict and set(value) == {"token", "index", "pair", "error"}:
                    value["token"] = self.job._active_token
                worker.write_atomic(directory / "result.pkl", value)
                self.finish(process)
                self.assertEqual(self.finished[-1][1], "FAILED")
                self.assertIn("RESULT_TRANSPORT", self.job.last_record["error"])
                self.assertTrue(self.job.last_record["cleanup_complete"])

    def test_one_worker_closed_request_B_flag_and_child_environment(self):
        token, process, directory, popen = self.launch()
        self.assertEqual(pickle.loads((directory / "request.pkl").read_bytes()), {"token": token, "index": 11})
        self.assertIn("-B", popen.call_args.args[0])
        self.assertEqual(popen.call_args.kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertIn("experiments.random_expert_exhibition_worker", popen.call_args.args[0])
        with self.assertRaises(RuntimeError):
            self.job.start(97)
        self.assertFalse(self.finished)

    def test_success_delivered_only_after_reap_and_cleanup(self):
        token, process, directory, _ = self.launch()
        self.publish()
        at_signal = []
        self.job.finished.connect(lambda *args: at_signal.append((self.job._process, directory.exists())))
        self.finish(process)
        self.assertEqual(self.finished[0][0:2], [token, "SUCCEEDED"])
        self.assertEqual(self.finished[0][2], self.pair)
        self.assertEqual(at_signal, [(None, False)])
        process.wait.assert_called_once_with(timeout=0)
        self.assertTrue(self.job.last_record["cleanup_complete"])

    def test_startup_failure_returns_token_before_signal(self):
        with patch.object(jobs.subprocess, "Popen", side_effect=OSError("startup failure")):
            token = self.job.start(11)
        self.assertFalse(self.finished)
        self.job.poll()
        self.assertEqual(self.finished[0][0:2], [token, "FAILED"])
        self.assertIn("STARTUP", self.finished[0][2]["error"])
        self.assertIsNone(self.job._directory)

    def test_stale_bool_token_wrong_index_and_trailing_bytes_rejected(self):
        for override in ({"token": 999}, {"token": True}, {"index": 97}, {"index": True}):
            token, process, directory, _ = self.launch()
            self.publish(**override)
            self.finish(process)
            self.assertEqual(self.finished[-1][1], "FAILED")
            self.assertIn("RESULT_TRANSPORT", self.finished[-1][2]["error"])
            self.assertFalse(directory.exists())
        _, process, directory, _ = self.launch()
        self.publish()
        with (directory / "result.pkl").open("ab") as stream:
            stream.write(b"trailing")
        self.finish(process)
        self.assertIn("Trailing", self.finished[-1][2]["error"])

    def test_cancel_wins_when_result_already_complete(self):
        token, process, directory, _ = self.launch()
        self.publish()
        self.job.cancel()
        with patch.object(self.job, "_read_result", side_effect=AssertionError("must not read")):
            self.finish(process)
        self.assertEqual(self.finished[0][1], "CANCELLED")
        self.assertFalse(directory.exists())
        self.assertIsNone(self.job.last_record["error"])

    def test_timeout_is_incomplete_and_does_not_install_completed_result(self):
        _, process, directory, _ = self.launch()
        self.publish()
        self.now = 120.0
        self.finish(process)
        self.assertEqual(self.finished[0][1], "TIMEOUT")
        self.assertEqual(self.job.last_record["wall_cap_seconds"], 120.0)
        self.assertNotIn("outcome", self.job.last_record)
        self.assertFalse(directory.exists())

    def test_terminate_kill_then_reap_cleanup_order(self):
        _, process, directory, _ = self.launch()
        self.job.cancel()
        process.terminate.assert_called_once()
        self.now = 0.49
        self.job.poll()
        process.kill.assert_not_called()
        self.now = .5
        self.job.poll()
        process.kill.assert_called_once()
        self.assertTrue(directory.exists())
        self.assertFalse(self.finished)
        self.finish(process, -1)
        self.assertFalse(directory.exists())

    def test_reap_failure_retains_owned_directory(self):
        _, process, directory, _ = self.launch()
        process.poll.return_value = 0
        process.wait.side_effect = OSError("cannot reap")
        self.job.poll()
        self.assertIs(self.job._process, process)
        self.assertTrue(directory.exists())
        self.assertFalse(self.finished)
        process.wait.side_effect = None
        self.job.cancel()
        self.finish(process)

    def test_cleanup_failure_blocks_new_start_and_can_retry_shutdown(self):
        _, process, directory, _ = self.launch()
        self.publish()
        with patch.object(jobs.shutil, "rmtree", side_effect=PermissionError("busy")):
            self.finish(process)
        self.assertEqual(self.job.state, "blocked")
        self.assertEqual(self.finished[0][1], "FAILED")
        self.assertTrue(directory.exists())
        with self.assertRaises(RuntimeError):
            self.job.start(97)
        self.job.shutdown()
        self.assertFalse(directory.exists())

    def test_shutdown_failure_retains_ownership_and_blocks_late_completion(self):
        _, process, directory, _ = self.launch()
        process.wait.side_effect = subprocess.TimeoutExpired("worker", 1)
        with self.assertRaisesRegex(RuntimeError, "SHUTDOWN_REAP"):
            self.job.shutdown()
        self.assertIs(self.job._process, process)
        self.assertTrue(directory.exists())
        self.job.poll()
        self.assertFalse(self.finished)
        process.wait.side_effect = None
        self.job.shutdown()
        self.assertFalse(directory.exists())

    def test_native_error_and_nonzero_exit_retain_diagnostic_not_loss(self):
        _, process, directory, _ = self.launch()
        self.publish(pair=None, error="K_P0_RUNNING: native failure")
        (directory / "stderr.txt").write_text("diagnostic stderr", encoding="utf-8")
        self.finish(process)
        self.assertIn("native failure", self.job.last_record["error"])
        self.assertIn("diagnostic stderr", self.job.last_record["stderr"])
        _, process, _, _ = self.launch()
        self.finish(process, 7)
        self.assertIn("WORKER_EXIT", self.job.last_record["error"])
        self.assertEqual(len(self.job.records), 2)
        self.assertIn("native failure", self.job.records[0]["error"])

    def test_progress_token_binding_and_completed_side_diagnostic(self):
        token, process, directory, _ = self.launch()
        phase = {"token": token + 1, "index": 11, "phase": "K_P0_RUNNING", "completed": [self.pair.v1.summary()]}
        worker.write_atomic(directory / "progress.json", phase, json_text=True)
        self.job.poll()
        self.assertIsNone(self.job._phase)
        phase["token"] = token
        worker.write_atomic(directory / "progress.json", phase, json_text=True)
        self.job.poll()
        self.assertEqual(self.job._phase, phase)
        self.job.cancel()
        self.finish(process)
        self.assertEqual(self.job.last_record["progress"]["completed"][0]["variant"], "V1")

    def test_atomic_publication_and_strict_worker_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.pkl"
            actual_replace = os.replace
            def observe(source, target):
                self.assertFalse(path.exists())
                self.assertEqual(pickle.loads(Path(source).read_bytes()), {"complete": True})
                actual_replace(source, target)
            with patch.object(worker.os, "replace", side_effect=observe):
                worker.write_atomic(path, {"complete": True})
            self.assertEqual(list(Path(temporary).iterdir()), [path])
        for payload in ({"token": True, "index": 11}, {"token": 1, "index": 2010000},
                        {"token": 1, "index": 11, "board": "extra"}, None):
            result = worker.calculate(payload)
            self.assertIsNone(result["pair"])
            self.assertTrue(result["error"])

    def test_real_worker_invalid_request_has_no_qt_and_reaps(self):
        code = ("import sys; from experiments.random_expert_exhibition_worker import calculate; "
                "r=calculate({'token':1,'index':2010000}); "
                "assert r['pair'] is None and r['error']; "
                "assert not any(m.startswith('PyQt5') for m in sys.modules); print('GUI_FREE_REJECTION')")
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=jobs.ROOT,
                                capture_output=True, text=True, timeout=10,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GUI_FREE_REJECTION", result.stdout)

    def real_sleeper(self):
        code = "import time,sys,os; from pathlib import Path; Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
        def command(payload, result, progress, scope_name):
            return [sys.executable, "-B", "-c", code, str(Path(payload).parent / "ready")]
        with patch.object(jobs, "build_worker_command", side_effect=command):
            self.job.start(11)
        directory, process = self.job._directory, self.job._process
        deadline = time.monotonic() + 5
        while not (directory / "ready").exists() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue((directory / "ready").exists())
        self.actual_worker_pid = int((directory / "ready").read_text())
        if os.name == "nt":
            import ctypes as C
            from ctypes import wintypes as W
            self.kernel = C.WinDLL("kernel32", use_last_error=True)
            self.kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
            self.kernel.OpenProcess.restype = W.HANDLE
            self.kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
            self.kernel.WaitForSingleObject.restype = W.DWORD
            self.kernel.CloseHandle.argtypes = [W.HANDLE]
            self.worker_handle = self.kernel.OpenProcess(0x100000, False, self.actual_worker_pid)
            self.assertTrue(self.worker_handle)
            self.addCleanup(lambda: self.kernel.CloseHandle(self.worker_handle))
            self.assertGreater(self.job._scope.active_count, 0)
        return process, directory

    def assert_actual_python_exited(self):
        if os.name == "nt":
            self.assertEqual(self.kernel.WaitForSingleObject(self.worker_handle, 0), 0)
        self.assertEqual(self.job.last_record["tree_active_count"], 0)

    def test_real_cancel_terminates_and_reaps_owned_child(self):
        process, directory = self.real_sleeper()
        self.job.cancel()
        deadline = time.monotonic() + 5
        while not self.finished and time.monotonic() < deadline:
            self.now += .05
            self.job.poll()
            QTest.qWait(10)
        self.assertTrue(self.finished)
        self.assertEqual(self.finished[0][1], "CANCELLED")
        self.assertIsNotNone(process.poll())
        self.assertFalse(directory.exists())
        self.assert_actual_python_exited()

    def test_real_timeout_reaps_owned_child(self):
        process, directory = self.real_sleeper()
        self.now = 120
        deadline = time.monotonic() + 5
        while not self.finished and time.monotonic() < deadline:
            self.job.poll()
            QTest.qWait(10)
        self.assertTrue(self.finished)
        self.assertEqual(self.finished[0][1], "TIMEOUT")
        self.assertIsNotNone(process.poll())
        self.assertFalse(directory.exists())
        self.assert_actual_python_exited()

    def test_real_close_reaps_without_emitting_completion(self):
        process, directory = self.real_sleeper()
        self.job.shutdown()
        self.assertFalse(self.finished)
        self.assertIsNotNone(process.poll())
        self.assertFalse(directory.exists())
        self.assertEqual(self.job.state, "closed")
        self.assert_actual_python_exited()

    def test_actual_worker_main_under_scope_rejects_bad_input_without_solver(self):
        build = jobs.build_worker_command
        def command(payload, result, progress, scope_name):
            request = pickle.loads(Path(payload).read_bytes())
            request["index"] = 2010000
            Path(payload).write_bytes(pickle.dumps(request))
            return build(payload, result, progress, scope_name)
        with patch.object(jobs, "build_worker_command", side_effect=command):
            self.job.start(11)
        process, directory = self.job._process, self.job._directory
        deadline = time.monotonic() + 5
        while not self.finished and time.monotonic() < deadline:
            self.job.poll()
            QTest.qWait(10)
        self.assertTrue(self.finished)
        self.assertEqual(self.finished[0][1], "FAILED")
        self.assertIn("Wrong board index", self.job.last_record["error"])
        self.assertIsNotNone(process.poll())
        self.assertFalse(directory.exists())
        self.assertEqual(self.job.last_record["tree_active_count"], 0)


if __name__ == "__main__":
    unittest.main()
