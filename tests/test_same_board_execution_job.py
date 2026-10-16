"""Parent lifecycle tests with mocked races and one bounded source worker run."""

import builtins
from dataclasses import replace
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
try:
    from PyQt5.QtCore import QTimer
    from PyQt5.QtTest import QSignalSpy, QTest
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    import same_board_execution_job as job_module
    from same_board_execution_job import SameBoardExecutionJob

from core_engine import GameStatus
from mouse_trace import MouseTraceData, MouseTracePoint, MouseTraceSegment
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from same_board_comparison import HumanComparisonContext
from same_board_runner import SameBoardExecution, run_fixed_layout_solvers


def context_fixture():
    board = ReplayBoard(2, 1, 1, {(1, 0)})
    trace = MouseTraceData(2, 1, (MouseTraceSegment(20, (
        MouseTracePoint(0, 10.5, 10.5, 0),
        MouseTracePoint(100, 10.75, 10.5, None),
    )),))
    replay = ReplayData(board, (ReplayEvent(4.5, 0, 0, "OPEN"),),
                        schema_version=2, mouse_trace=trace)
    return HumanComparisonContext(replay, declared_full_game_human=True)


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class SameBoardExecutionJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.job = SameBoardExecutionJob()
        self.success = QSignalSpy(self.job.succeeded)
        self.failure = QSignalSpy(self.job.failed)
        self.cancelled = QSignalSpy(self.job.cancelled)
        self.context = context_fixture()
        self.execution = run_fixed_layout_solvers(self.context.layout.board)
        self.addCleanup(self.job.shutdown)

    def launch(self, context=None, frozen=False, popen_check=None):
        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0

        def create(command, **kwargs):
            if popen_check is not None:
                popen_check(command, kwargs)
            return process

        with patch.object(sys, "frozen", frozen, create=True), patch(
            "same_board_execution_job.subprocess.Popen", side_effect=create,
        ) as popen:
            token = self.job.start(self.context if context is None else context)
        return token, process, popen, Path(self.job._job_dir)

    def publish(self, **overrides):
        envelope = {"token": self.job._active_token, "solver_execution": self.execution, "error": None}
        envelope.update(overrides)
        Path(self.job._result_path).write_bytes(pickle.dumps(envelope))

    def complete(self, process, exit_code=0):
        process.poll.return_value = exit_code
        process.wait.return_value = exit_code
        self.job._poll()

    def assert_clean(self, process, directory):
        process.wait.assert_called_once_with(timeout=0)
        self.assertFalse(directory.exists())
        self.assertIsNone(self.job._process)
        self.assertIsNone(self.job._job_dir)
        self.assertIsNone(self.job._active_token)
        self.assertEqual(self.job.state, "idle")
        self.assertFalse(self.job._poll_timer.isActive())

    def test_start_payload_is_exact_closed_and_result_initially_absent(self):
        handles = []
        open_file = builtins.open

        def track_open(path, mode="r", *args, **kwargs):
            stream = open_file(path, mode, *args, **kwargs)
            if mode == "wb":
                handles.append(stream)
            return stream

        def inspect(command, kwargs):
            self.assertEqual(len(handles), 1)
            self.assertTrue(handles[0].closed)
            payload, result = map(Path, command[-2:])
            self.assertEqual(pickle.loads(payload.read_bytes()), {"token": 1, "board": self.context.layout.board})
            for human_authority in (b"HumanComparisonContext", b"ReplayData", b"ReplayEvent", b"MouseTraceData"):
                self.assertNotIn(human_authority, payload.read_bytes())
            self.assertIs(self.job._context, self.context)
            self.assertFalse(result.exists())
            self.assertEqual(payload.parent, result.parent)
            self.assertTrue(payload.parent.name.startswith("minesweeper_same_board_job_"))
            for stream in ("stdin", "stdout", "stderr"):
                self.assertEqual(kwargs[stream], subprocess.DEVNULL)

        with patch("builtins.open", side_effect=track_open):
            token, process, _, directory = self.launch(popen_check=inspect)
        self.assertEqual(token, 1)
        self.assertEqual(self.job.state, "running")
        self.assertTrue(self.job._poll_timer.isActive())
        self.assertFalse(self.success or self.failure or self.cancelled)
        process.wait.assert_not_called()
        self.assertTrue(directory.exists())

    def test_source_command_uses_absolute_file_relative_path_not_caller_cwd(self):
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as unrelated:
            try:
                os.chdir(unrelated)
                _, _, popen, _ = self.launch()
            finally:
                os.chdir(old_cwd)
        command = popen.call_args.args[0]
        expected_worker = Path(job_module.__file__).resolve().with_name("same_board_execution_worker.py")
        self.assertEqual(command[:2], [sys.executable, str(expected_worker)])
        self.assertTrue(Path(command[1]).is_absolute())
        self.assertEqual(command[-2:], [self.job._payload_path, self.job._result_path])
        self.assertEqual(popen.call_args.kwargs["cwd"], str(expected_worker.parent))

    def test_frozen_command_uses_executable_and_slice2_dispatch(self):
        _, _, popen, _ = self.launch(frozen=True)
        self.assertEqual(popen.call_args.args[0], [sys.executable, "--same-board-execution-worker",
                                                 self.job._payload_path, self.job._result_path])

    def test_tokens_increase_and_each_run_gets_a_unique_directory(self):
        first, process, _, first_dir = self.launch()
        self.publish()
        self.complete(process)
        second_context = context_fixture()
        second, process, _, second_dir = self.launch(second_context)
        self.assertGreater(second, first)
        self.assertNotEqual(first_dir, second_dir)
        self.publish()
        self.complete(process)
        self.assertFalse(first_dir.exists() or second_dir.exists())
        self.assertEqual([signal[0] for signal in self.success], [first, second])
        self.assertIs(self.success[0][1].context, self.context)
        self.assertIs(self.success[1][1].context, second_context)

    def test_large_parent_token_survives_qt_signal_without_int_truncation(self):
        self.job._next_token = 2**80
        token, process, _, _ = self.launch()
        self.publish()
        self.complete(process)
        self.assertEqual(self.success[0][0], token)
        self.assertEqual(token, 2**80 + 1)

    def test_stale_result_cannot_attach_to_new_parent_context(self):
        first_token, process, _, _ = self.launch()
        self.publish()
        self.complete(process)
        newer_context = context_fixture()
        self.assertIsNot(newer_context, self.context)
        token, process, _, directory = self.launch(newer_context)
        self.assertIs(self.job._context, newer_context)
        self.publish(token=first_token)
        self.complete(process)
        self.assertEqual(len(self.success), 1)
        self.assertEqual(self.failure[-1][0], token)
        self.assertIn("token", self.failure[-1][1])
        self.assertFalse(directory.exists())

    def test_success_callback_can_start_next_request_without_old_cleanup_touching_it(self):
        _, process, _, old_directory = self.launch()
        self.publish()
        next_context = context_fixture()
        next_launch = []

        def begin_next(token, execution):
            if not next_launch:
                next_launch.append(self.launch(next_context))

        self.job.succeeded.connect(begin_next)
        self.complete(process)
        self.assertEqual(len(next_launch), 1)
        token, next_process, _, directory = next_launch[0]
        self.assertFalse(old_directory.exists())
        self.assertTrue(directory.exists())
        self.assertIs(self.job._context, next_context)
        self.assertIs(self.job._process, next_process)
        self.assertEqual(self.job._active_token, token)
        self.publish()
        self.complete(next_process)
        self.assertEqual(len(self.success), 2)
        self.assertIs(self.success[-1][1].context, next_context)
        self.assertFalse(directory.exists())

    def test_parent_composition_rejects_inconsistent_solver_evidence(self):
        token, process, _, directory = self.launch()
        # A same-type native result is insufficient: its stream must actually
        # reconstruct to the claimed outcome on the parent's exact board.
        bad_stage3 = replace(self.execution.stage3_result, status=GameStatus.LOST)
        self.publish(solver_execution=replace(self.execution, stage3_result=bad_stage3))
        self.complete(process)
        self.assertFalse(self.success or self.cancelled)
        self.assertEqual(self.failure[0][0], token)
        self.assertIn("transport failed", self.failure[0][1])
        self.assert_clean(process, directory)

    def test_parent_composition_failure_never_publishes_partial_result(self):
        token, process, _, directory = self.launch()
        self.publish()
        with patch("same_board_execution_job.compose_same_board_execution",
                   side_effect=ValueError("mismatched fixed layout")) as compose:
            self.complete(process)
        compose.assert_called_once()
        self.assertIs(compose.call_args.args[0], self.context)
        self.assertEqual(self.failure[0][0], token)
        self.assertIn("mismatched fixed layout", self.failure[0][1])
        self.assertFalse(self.success or self.cancelled)
        self.assert_clean(process, directory)

    def test_other_fixed_layout_result_is_rejected_before_success(self):
        token, process, _, directory = self.launch()
        other_execution = run_fixed_layout_solvers(ReplayBoard(2, 1, 1, {(0, 0)}))
        self.publish(solver_execution=other_execution)
        self.complete(process)
        self.assertFalse(self.success or self.cancelled)
        self.assertEqual(self.failure[0][0], token)
        self.assertIn("layout", self.failure[0][1])
        self.assert_clean(process, directory)

    def test_invalid_contexts_fail_asynchronously_without_spawning(self):
        tokens = []
        for index in (-1, True, 0.0, "0", None):
            with self.subTest(index=index), patch("same_board_execution_job.subprocess.Popen") as popen:
                previous_failures = len(self.failure)
                tokens.append(self.job.start(index))
                self.assertEqual(len(self.failure), previous_failures)
                self.job._poll()
                self.assertIn("HumanComparisonContext", self.failure[-1][1])
                popen.assert_not_called()
                self.assertEqual(self.job.state, "idle")
        self.assertEqual(tokens, [1, 2, 3, 4, 5])

    def test_success_reaps_before_cleanup_and_emits_complete_execution_once(self):
        token, process, _, directory = self.launch()
        self.publish()
        orphan = directory / ".minesweeper_same_board_result_orphan.tmp"
        orphan.write_bytes(b"partial")
        self.job._poll()  # Published result is not proof of exit.
        self.assertTrue(directory.exists())
        self.assertFalse(self.success)
        process.wait.assert_not_called()
        process.wait.side_effect = lambda timeout: self.assertTrue(directory.exists()) or 0
        self.complete(process)
        self.assert_clean(process, directory)
        self.assertEqual(len(self.success), 1)
        self.assertEqual(self.success[0][0], token)
        received = self.success[0][1]
        self.assertIsInstance(received, SameBoardExecution)
        self.assertIs(received.context, self.context)
        self.assertIs(received.context.human_replay, self.context.human_replay)
        self.assertIs(received.context.human_replay.mouse_trace, self.context.human_replay.mouse_trace)
        self.assertEqual(received.stage2_result, self.execution.stage2_result)
        self.assertEqual(received.stage3_result, self.execution.stage3_result)
        self.job._poll()
        self.job._poll_timer.timeout.emit()
        self.assertEqual(len(self.success), 1)
        self.assertFalse(self.failure or self.cancelled)

    def test_matching_execution_failure_reports_original_diagnostic_and_cleans(self):
        token, process, _, directory = self.launch()
        self.publish(solver_execution=None, error="ValueError('execution failed')")
        self.complete(process)
        self.assertEqual(self.failure[0], [token, "ValueError('execution failed')"])
        self.assertFalse(self.success or self.cancelled)
        self.assert_clean(process, directory)

    def test_transported_origin_losses_emit_success_with_original_parent_context(self):
        from same_board_execution_worker import calculate_same_board_execution
        from simple_runner import run_simple
        from stage3_runner import run_stage3
        from tests.test_same_board_runner import human_context

        context = human_context(mined_origin=True, with_trace=True)
        token, process, _, directory = self.launch(context=context)
        with patch("same_board_runner.run_simple", wraps=run_simple) as stage2, \
             patch("same_board_runner.run_stage3", wraps=run_stage3) as stage3, \
             patch("core_engine.random.sample", side_effect=AssertionError("regeneration")):
            envelope = calculate_same_board_execution({"token": token, "board": context.layout.board})
            self.assertIsNone(envelope["error"])
            execution = envelope["solver_execution"]
            stage2.assert_called_once()
            stage3.assert_called_once()
        self.assertEqual(execution.stage2_result.status, GameStatus.LOST)
        self.assertEqual(execution.stage3_result.status, GameStatus.LOST)
        self.assertEqual(len(execution.stage2_traces), 1)
        self.assertEqual(len(execution.stage3_result.traces), 1)
        self.publish(solver_execution=execution)
        with patch("same_board_runner.run_simple", side_effect=AssertionError("retry")), \
             patch("same_board_runner.run_stage3", side_effect=AssertionError("retry")), \
             patch("core_engine.random.sample", side_effect=AssertionError("regeneration")):
            self.complete(process)
        self.assert_clean(process, directory)
        self.assertEqual(len(self.success), 1)
        self.assertFalse(self.failure or self.cancelled)
        received_token, received = self.success[0]
        self.assertEqual(received_token, token)
        self.assertIs(received.context, context)
        self.assertIs(received.context.human_replay.mouse_trace, context.human_replay.mouse_trace)
        self.assertEqual(received.human_metrics.outcome, GameStatus.WON)
        self.assertEqual(received.stage2_metrics.outcome, GameStatus.LOST)
        self.assertEqual(received.stage3_metrics.outcome, GameStatus.LOST)
        self.assertEqual(received.stage2_result.status, GameStatus.LOST)
        self.assertEqual(received.stage3_result.status, GameStatus.LOST)
        self.job._poll()
        self.assertEqual(len(self.success), 1)

    def test_nonzero_exit_never_accepts_success_envelope(self):
        token, process, _, directory = self.launch()
        self.publish()
        self.complete(process, 7)
        self.assertEqual(self.failure[0][0], token)
        self.assertIn("code 7", self.failure[0][1])
        self.assertFalse(self.success)
        self.assert_clean(process, directory)

    def test_missing_or_unreadable_result_fails_closed(self):
        for raw in (None, b"not a pickle", b""):
            with self.subTest(raw=raw):
                _, process, _, directory = self.launch()
                if raw is not None:
                    Path(self.job._result_path).write_bytes(raw)
                self.complete(process)
                self.assertIn("transport failed", self.failure[-1][1])
                self.assertFalse(self.success)
                self.assert_clean(process, directory)

    def test_trailing_data_after_result_envelope_is_rejected(self):
        for suffix in (b"trailing", pickle.dumps({"extra": "envelope"})):
            with self.subTest(suffix=suffix):
                token, process, _, directory = self.launch()
                self.publish()
                with open(self.job._result_path, "ab") as result_file:
                    result_file.write(suffix)
                self.complete(process)
                self.assertEqual(self.failure[-1][0], token)
                self.assertIn("exactly one envelope", self.failure[-1][1])
                self.assertFalse(self.success)
                self.assert_clean(process, directory)

    def test_malformed_envelopes_and_required_fields_fail_closed(self):
        cases = [None, [], {}, {"solver_execution": self.execution, "error": None},
                 {"token": "active", "solver_execution": self.execution},
                 {"token": "active", "error": "failure"},
                 {"token": "active", "solver_execution": self.execution, "error": "both"},
                 {"token": "active", "solver_execution": None, "error": None},
                 {"token": "active", "solver_execution": None, "error": " "},
                 {"token": "active", "solver_execution": None, "error": False},
                 {"token": "active", "solver_execution": "fake", "error": None},
                 {"token": "active", "solver_execution": self.execution, "error": None, "extra": 1}]
        for envelope in cases:
            with self.subTest(envelope=envelope):
                token, process, _, directory = self.launch()
                if isinstance(envelope, dict) and envelope.get("token") == "active":
                    envelope = dict(envelope, token=token)
                Path(self.job._result_path).write_bytes(pickle.dumps(envelope))
                before = len(self.failure)
                self.complete(process)
                self.assertEqual(len(self.failure), before + 1)
                self.assertFalse(self.success)
                self.assert_clean(process, directory)

    def test_stale_or_equal_but_noninteger_token_is_rejected(self):
        for token_kind in ("bool", "float", "stale"):
            with self.subTest(token_kind=token_kind):
                token, process, _, directory = self.launch()
                bad_token = token - 1 if token_kind == "stale" else bool(token) if token_kind == "bool" else float(token)
                self.publish(token=bad_token)
                self.complete(process)
                self.assertIn("token", self.failure[-1][1])
                self.assertFalse(self.success)
                self.assert_clean(process, directory)

    def test_running_poll_and_cancel_return_without_any_wait(self):
        token, process, _, directory = self.launch()
        self.publish()
        self.job._poll()
        self.job.cancel()
        self.assertEqual(self.job.state, "cancelling")
        process.terminate.assert_called_once_with()
        process.wait.assert_not_called()
        self.assertTrue(directory.exists())
        self.job._poll()
        process.wait.assert_not_called()
        self.complete(process)
        self.assert_clean(process, directory)
        self.assertEqual(list(self.cancelled), [[token]])
        self.assertFalse(self.success or self.failure)

    def test_cancel_intent_wins_when_child_already_exited_with_result(self):
        token, process, _, directory = self.launch()
        self.publish()
        process.poll.return_value = 0
        self.job.cancel()
        self.job._poll()
        self.assertEqual(list(self.cancelled), [[token]])
        self.assertFalse(self.success or self.failure)
        self.assert_clean(process, directory)

    def test_repeated_cancel_is_harmless_and_emits_once(self):
        token, process, _, directory = self.launch()
        for _ in range(4):
            self.job.cancel()
        process.terminate.assert_called_once_with()
        self.complete(process)
        self.job.cancel()
        self.job._poll()
        self.assertEqual(list(self.cancelled), [[token]])
        self.assert_clean(process, directory)

    def test_kill_escalates_once_after_fixed_grace_without_waiting(self):
        token, process, _, directory = self.launch()
        with patch("same_board_execution_job.time.monotonic", return_value=10):
            self.job.cancel()
        with patch("same_board_execution_job.time.monotonic", return_value=10.1):
            self.job._poll()
        process.kill.assert_not_called()
        with patch("same_board_execution_job.time.monotonic", return_value=11):
            self.job._poll()
            self.job._poll()
        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        process.wait.assert_not_called()
        self.assertTrue(directory.exists())
        self.complete(process, -9)
        self.assertEqual(list(self.cancelled), [[token]])
        self.assert_clean(process, directory)

    def test_terminate_os_error_still_reaches_kill_then_cancel(self):
        token, process, _, directory = self.launch()
        process.terminate.side_effect = OSError("terminate race")
        self.job.cancel()
        with patch("same_board_execution_job.time.monotonic", return_value=float("inf")):
            self.job._poll()
        process.kill.assert_called_once()
        self.complete(process)
        self.assertEqual(list(self.cancelled), [[token]])
        self.assert_clean(process, directory)

    def test_cannot_start_another_process_while_running_or_cancelling(self):
        _, _, _, _ = self.launch()
        for cancel in (False, True):
            if cancel:
                self.job.cancel()
            with patch("same_board_execution_job.subprocess.Popen") as popen:
                with self.assertRaisesRegex(RuntimeError, "already active"):
                    self.job.start(self.context)
                popen.assert_not_called()

    def test_popen_failure_cleans_before_one_deferred_failure_signal(self):
        directories = []

        def fail(command, **kwargs):
            directories.append(Path(command[-1]).parent)
            raise OSError("cannot launch")

        with patch("same_board_execution_job.subprocess.Popen", side_effect=fail):
            token = self.job.start(self.context)
        self.assertFalse(self.failure)
        self.assertEqual(self.job.state, "running")
        deadline = time.monotonic() + 2
        while not self.failure and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertEqual(len(self.failure), 1)
        self.assertEqual(self.failure[0][0], token)
        self.assertIn("cannot launch", self.failure[0][1])
        self.assertFalse(directories[0].exists())
        self.assertEqual(self.job.state, "idle")
        self.assertFalse(self.job._poll_timer.isActive())

    def test_payload_write_failure_cleans_whole_directory_without_spawn(self):
        with patch("same_board_execution_job.pickle.dump", side_effect=OSError("disk full")), patch(
            "same_board_execution_job.subprocess.Popen",
        ) as popen:
            token = self.job.start(self.context)
            directory = Path(self.job._job_dir)
            self.job._poll()
        popen.assert_not_called()
        self.assertEqual(self.failure[0][0], token)
        self.assertIn("disk full", self.failure[0][1])
        self.assertFalse(directory.exists())

    def test_temp_creation_failure_and_cancel_before_start_failure_delivery(self):
        with patch("same_board_execution_job.tempfile.mkdtemp", side_effect=OSError("temp unavailable")):
            token = self.job.start(self.context)
        self.job.cancel()
        self.job._poll()
        self.assertEqual(list(self.cancelled), [[token]])
        self.assertFalse(self.success or self.failure)
        self.assertEqual(self.job.state, "idle")

    def test_shutdown_terminates_reaps_removes_orphan_and_suppresses_callbacks(self):
        _, process, _, directory = self.launch()
        self.publish()
        (directory / ".minesweeper_same_board_result_orphan.tmp").write_bytes(b"partial")
        self.job.shutdown()
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=job_module.SHUTDOWN_TERMINATE_SECONDS)
        process.kill.assert_not_called()
        self.assertFalse(directory.exists())
        self.assertFalse(self.job._poll_timer.isActive())
        self.assertIsNone(self.job._process)
        self.job._poll_timer.timeout.emit()
        self.job.shutdown()
        self.assertFalse(self.success or self.failure or self.cancelled)
        with self.assertRaises(RuntimeError):
            self.job.start(self.context)

    def test_shutdown_kill_fallback_has_only_short_bounded_waits(self):
        _, process, _, directory = self.launch()
        process.wait.side_effect = [subprocess.TimeoutExpired("same-board", .5), 0]
        self.job.shutdown()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual([call.kwargs["timeout"] for call in process.wait.call_args_list],
                         [job_module.SHUTDOWN_TERMINATE_SECONDS, job_module.SHUTDOWN_KILL_SECONDS])
        self.assertFalse(directory.exists())
        self.assertFalse(self.success or self.failure or self.cancelled)

    def test_shutdown_reap_failure_retains_child_directory_and_allows_retry(self):
        _, process, _, directory = self.launch()
        process.wait.side_effect = subprocess.TimeoutExpired("same-board", 1)
        with self.assertRaisesRegex(RuntimeError, "could not reap"):
            self.job.shutdown()
        self.assertIs(self.job._process, process)
        self.assertIs(self.job._context, self.context)
        self.assertEqual(Path(self.job._job_dir), directory)
        self.assertTrue(directory.exists())
        self.assertEqual(self.job.state, "cancelling")
        self.assertFalse(self.job._poll_timer.isActive())
        self.assertFalse(self.success or self.failure or self.cancelled)
        process.wait.side_effect = None
        process.wait.return_value = 0
        self.job.shutdown()
        self.assertFalse(directory.exists())
        self.assertIsNone(self.job._process)

    def test_poll_reap_timeout_preserves_directory_until_later_reap(self):
        _, process, _, directory = self.launch()
        self.publish()
        process.poll.return_value = 0
        process.wait.side_effect = subprocess.TimeoutExpired("same-board", 0)
        self.job._poll()
        self.assertTrue(directory.exists())
        self.assertIs(self.job._process, process)
        self.assertFalse(self.success or self.failure or self.cancelled)
        process.wait.side_effect = None
        self.job._poll()
        self.assertFalse(directory.exists())
        self.assertEqual(len(self.success), 1)

    def test_poll_reap_os_error_retains_ownership_then_reports_failure_after_reap(self):
        token, process, _, directory = self.launch()
        self.publish()
        process.poll.return_value = 0
        process.wait.side_effect = OSError("reap unavailable")
        self.job._poll()
        self.assertIs(self.job._process, process)
        self.assertIs(self.job._context, self.context)
        self.assertTrue(directory.exists())
        self.assertFalse(self.success or self.failure or self.cancelled)
        process.wait.side_effect = None
        self.job._poll()
        self.assertIsNone(self.job._process)
        self.assertFalse(directory.exists())
        self.assertEqual(self.failure[0][0], token)
        self.assertIn("reap unavailable", self.failure[0][1])
        self.assertFalse(self.success or self.cancelled)

    def test_cleanup_failure_reports_retains_path_and_blocks_run_until_shutdown(self):
        for cleanup_error in (PermissionError("locked"), FileNotFoundError("nested entry vanished")):
            with self.subTest(error=cleanup_error):
                if self.job._closed:
                    self.job = SameBoardExecutionJob()
                    self.addCleanup(self.job.shutdown)
                    self.failure = QSignalSpy(self.job.failed)
                    self.success = QSignalSpy(self.job.succeeded)
                token, process, _, directory = self.launch()
                self.publish()
                with patch("same_board_execution_job.shutil.rmtree", side_effect=cleanup_error):
                    self.complete(process)
                self.assertFalse(self.success)
                self.assertEqual(self.failure[-1][0], token)
                self.assertIn("cleanup failed", self.failure[-1][1])
                self.assertEqual(self.job.last_diagnostic, self.failure[-1][1])
                self.assertEqual(Path(self.job._job_dir), directory)
                self.assertIsNone(self.job._process)
                self.assertEqual(self.job.state, "cancelling")
                with self.assertRaises(RuntimeError):
                    self.job.start(self.context)
                self.job.shutdown()
                self.assertFalse(directory.exists())

    def test_shutdown_cleanup_failure_retains_owned_path_and_raises_for_retry(self):
        _, process, _, directory = self.launch()
        with patch("same_board_execution_job.shutil.rmtree", side_effect=PermissionError("locked")):
            with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
                self.job.shutdown()
        self.assertIsNone(self.job._process)
        self.assertEqual(Path(self.job._job_dir), directory)
        self.assertFalse(self.success or self.failure or self.cancelled)
        self.job.shutdown()
        self.assertFalse(directory.exists())

    def test_cancellation_cleanup_failure_never_emits_success_or_hides_diagnostic(self):
        _, process, _, directory = self.launch()
        self.publish()
        self.job.cancel()
        with patch("same_board_execution_job.shutil.rmtree", side_effect=PermissionError("locked")):
            self.complete(process)
        self.assertFalse(self.success or self.cancelled)
        self.assertEqual(len(self.failure), 1)
        self.assertIn("cleanup failed", self.failure[0][1])
        self.assertTrue(directory.exists())

    def test_real_source_parent_worker_result_path_is_bounded_and_keeps_qt_responsive(self):
        heartbeat_count = []
        heartbeat = QTimer()
        heartbeat.setInterval(10)
        heartbeat.timeout.connect(lambda: heartbeat_count.append(1))
        heartbeat.start()
        self.addCleanup(heartbeat.stop)
        token = self.job.start(self.context)
        process, directory = self.job._process, Path(self.job._job_dir)
        deadline = time.monotonic() + 30
        while self.job.state != "idle" and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertEqual(self.job.state, "idle", "Real Same-board parent job exceeded 30 s.")
        self.assertFalse(self.failure, list(self.failure))
        self.assertEqual(len(self.success), 1)
        received_token, execution = self.success[0]
        self.assertEqual(received_token, token)
        self.assertIsInstance(execution, SameBoardExecution)
        self.assertIs(execution.context, self.context)
        self.assertIs(execution.context.human_replay.mouse_trace, self.context.human_replay.mouse_trace)
        self.assertEqual(execution.stage2_result.replay_data.board, self.context.layout.board)
        self.assertEqual(execution.stage2_result.status, GameStatus.WON)
        self.assertEqual(execution.stage3_result.status, GameStatus.WON)
        self.assertEqual(len(execution.stage2_traces), 1)
        self.assertEqual(len(execution.stage3_result.traces), 1)
        self.assertEqual(process.poll(), 0)
        self.assertFalse(directory.exists())
        self.assertTrue(heartbeat_count)
        self.assertIsNone(self.job._process)


if __name__ == "__main__":
    unittest.main()
