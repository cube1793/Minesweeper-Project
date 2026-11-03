"""Live transport/lifecycle checks; synthetic public states, no public games."""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
from PyQt5.QtCore import QTimer
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication

import live_policy_job as jobs
from core_engine import GameStatus
from live_policy import (
    PublicSnapshot, ack_to_dict, plan_snapshot, proposal_to_dict, snapshot_to_dict, validate_ack,
)
from live_policy_transport import message, read_next, write_once


def initial_snapshot(run_id="a" * 32, generation=1):
    return PublicSnapshot(
        run_id=run_id, board_generation=generation, input_seq=0, policy_id="STAGE3_V1",
        width=9, height=9, num_mines=10,
        observation=tuple(tuple(-2 for _ in range(9)) for _ in range(9)),
        cursor=(0, 0), status="PLAYING",
    )


class LivePolicyJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.now = 0.0
        self.job = jobs.LivePolicyJob(clock=lambda: self.now)
        self.finished = QSignalSpy(self.job.finished)
        self.proposals = QSignalSpy(self.job.proposal_ready)
        self.acks = QSignalSpy(self.job.acknowledged)
        self.addCleanup(self.job.shutdown)

    def launch(self, snapshot=None):
        snapshot = snapshot or initial_snapshot()
        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        with patch.object(jobs.subprocess, "Popen", return_value=process) as popen, \
                patch.object(jobs, "create_scope", return_value=None):
            token = self.job.start(snapshot)
        self.job.timer.stop()
        return token, process, self.job._directory, popen

    def publish(self, kind, payload, *, seq=None, run_id=None):
        seq = self.job._sequence if seq is None else seq
        write_once(self.job._directory, "worker", seq,
                   message(run_id or self.job.active_run_id, seq, kind, payload))

    def ready_proposal(self):
        token, process, directory, popen = self.launch()
        proposal = plan_snapshot(initial_snapshot())
        self.publish("PROPOSAL", proposal_to_dict(proposal))
        self.job.poll()
        self.assertEqual(self.job.state, "pending")
        return proposal, process, directory, popen

    def terminal_reply(self):
        proposal, process, directory, popen = self.ready_proposal()
        self.assertIs(self.job.mark_applying(proposal.token), self.job.pending)
        self.job.acknowledge("WON")
        self.publish("FINISHED", {"token": proposal.token, "input_seq": 0, "status": "WON"})
        self.job.poll()
        return proposal, process, directory, popen

    def exit(self, process, code=0):
        process.poll.return_value = code
        process.wait.return_value = code
        self.job.poll()

    def test_start_public_request_identity_and_environment(self):
        token, process, directory, popen = self.launch()
        self.assertEqual(token, initial_snapshot().run_id)
        envelope = read_next(directory, "parent", 0, token)
        self.assertEqual(envelope["kind"], "START")
        self.assertEqual(envelope["payload"], snapshot_to_dict(initial_snapshot()))
        self.assertIn("-B", popen.call_args.args[0])
        self.assertIn("live_policy_worker", popen.call_args.args[0])
        self.assertEqual(popen.call_args.kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(popen.call_args.kwargs["env"]["GIT_OPTIONAL_LOCKS"], "0")
        self.assertFalse(self.finished)
        with self.assertRaises(RuntimeError):
            self.job.start(initial_snapshot("b" * 32))

    def test_pending_has_no_deadline_and_does_not_plan_again(self):
        proposal, _, directory, _ = self.ready_proposal()
        self.now = 100000
        self.job.poll()
        self.assertIsNone(self.job._deadline)
        self.assertEqual(self.job.pending, proposal)
        self.assertEqual(len(self.proposals), 1)
        self.assertEqual(len(list(directory.glob("parent-*.json"))), 1)
        with self.assertRaises(ValueError):
            self.job.request(initial_snapshot())

    def test_mark_applying_returns_bound_action_and_consumes_once(self):
        proposal, _, _, _ = self.ready_proposal()
        with self.assertRaises(ValueError):
            self.job.mark_applying(True)
        with self.assertRaises(ValueError):
            self.job.mark_applying("b" * 32)
        selected = self.job.mark_applying(proposal.token)
        self.assertEqual((selected.action, selected.x, selected.y), ("OPEN", 0, 0))
        self.assertEqual(self.job.state, "applying")
        with self.assertRaises(ValueError):
            self.job.mark_applying(proposal.token)
        self.assertEqual(self.job._applied_count, 1)

    def test_ack_required_before_next_analysis_and_idle_after_ack(self):
        proposal, _, directory, _ = self.ready_proposal()
        with self.assertRaises(ValueError):
            self.job.acknowledge("WON")
        self.job.mark_applying(proposal.token)
        after = tuple((1,) + row[1:] if index == 0 else row
                      for index, row in enumerate(proposal.snapshot.observation))
        self.job.acknowledge("PLAYING", after)
        self.assertEqual(self.job.state, "acknowledging")
        with self.assertRaises(ValueError):
            self.job.request(replace(proposal.snapshot, input_seq=1, observation=after))
        sent_ack = self.job._sent_ack
        self.publish("ACKED", ack_to_dict(sent_ack))
        self.job.poll()
        self.assertEqual(self.job.state, "ready")
        self.assertEqual(len(self.acks), 1)
        self.now = 1000
        self.job.poll()
        self.assertEqual(len(list(directory.glob("parent-*.json"))), 2)
        next_state = validate_ack(proposal, sent_ack)
        with self.assertRaises(ValueError):
            self.job.request(replace(next_state, board_generation=2))
        self.job.request(next_state)
        self.assertEqual(self.job.state, "computing")
        self.assertEqual(read_next(directory, "parent", 2, proposal.snapshot.run_id)["kind"], "NEXT")

    def test_terminal_ack_has_no_public_terminal_truth(self):
        proposal, _, directory, _ = self.ready_proposal()
        self.job.mark_applying(proposal.token)
        self.job.acknowledge("LOST")
        payload = read_next(directory, "parent", 1, proposal.snapshot.run_id)["payload"]
        self.assertIsNone(payload["observation"])
        self.assertEqual(payload["status"], "LOST")
        self.assertEqual((payload["action"], payload["x"], payload["y"]), ("OPEN", 0, 0))

    def test_enum_status_normalizes_before_choosing_ack_response(self):
        proposal, _, _, _ = self.ready_proposal()
        self.job.mark_applying(proposal.token)
        after = tuple((1,) + row[1:] if index == 0 else row
                      for index, row in enumerate(proposal.snapshot.observation))
        self.job.acknowledge(GameStatus.PLAYING, after)
        self.assertEqual(self.job.state, "acknowledging")
        self.assertEqual(self.job._awaiting, "ACKED")
        self.assertEqual(self.job._sent_ack.status, "PLAYING")

    def test_failed_ack_cannot_reapply_consumed_token(self):
        proposal, _, _, _ = self.ready_proposal()
        self.job.mark_applying(proposal.token)
        with self.assertRaises(Exception):
            self.job.acknowledge("PLAYING", proposal.snapshot.observation)
        self.assertEqual(self.job.state, "cancelling")
        with self.assertRaises(ValueError):
            self.job.mark_applying(proposal.token)
        self.assertEqual(self.job._applied_count, 1)

    def test_stale_run_generation_and_policy_reply_fail_closed(self):
        _, process, _, _ = self.launch()
        proposal = plan_snapshot(initial_snapshot(generation=2))
        self.publish("PROPOSAL", proposal_to_dict(proposal))
        self.job.poll()
        self.assertFalse(self.proposals)
        self.exit(process, 1)
        self.assertEqual(self.finished[0][0]["status"], "FAILED")
        self.assertIn("public snapshot", self.job.last_record["error"])

    def test_wrong_run_identity_rejected(self):
        _, process, _, _ = self.launch()
        self.publish("PROPOSAL", proposal_to_dict(plan_snapshot(initial_snapshot())), run_id="b" * 32)
        self.job.poll()
        self.exit(process, 1)
        self.assertFalse(self.proposals)
        self.assertEqual(self.job.last_record["status"], "FAILED")

    def test_unexpected_reply_and_duplicate_reply_rejected(self):
        proposal, process, _, _ = self.ready_proposal()
        self.publish("PROPOSAL", proposal_to_dict(proposal))
        self.job.poll()
        self.exit(process, 1)
        self.assertEqual(len(self.proposals), 1)
        self.assertIn("Unsolicited", self.job.last_record["error"])

    def test_ack_action_token_tamper_rejected(self):
        proposal, process, _, _ = self.ready_proposal()
        self.job.mark_applying(proposal.token)
        after = tuple((1,) + row[1:] if index == 0 else row
                      for index, row in enumerate(proposal.snapshot.observation))
        self.job.acknowledge("PLAYING", after)
        payload = ack_to_dict(self.job._sent_ack)
        payload["x"] = 1
        self.publish("ACKED", payload)
        self.job.poll()
        self.exit(process, 1)
        self.assertFalse(self.acks)
        self.assertEqual(self.job.last_record["status"], "FAILED")

    def test_cancel_intent_wins_over_already_published_reply(self):
        _, process, directory, _ = self.launch()
        self.publish("PROPOSAL", proposal_to_dict(plan_snapshot(initial_snapshot())))
        self.job.cancel("reset")
        with patch.object(self.job, "_read_reply", side_effect=AssertionError("late admission")):
            self.exit(process, -1)
        self.assertFalse(self.proposals)
        self.assertEqual(self.job.last_record["status"], "CANCELLED")
        self.assertEqual(self.job.last_record["intent_reason"], "reset")
        self.assertFalse(directory.exists())

    def test_compute_deadline_is_not_paused_and_preempts_reply(self):
        _, process, _, _ = self.launch()
        self.publish("PROPOSAL", proposal_to_dict(plan_snapshot(initial_snapshot())))
        self.now = jobs.COMPUTE_CAP_SECONDS
        self.exit(process, -1)
        self.assertFalse(self.proposals)
        self.assertEqual(self.job.last_record["status"], "TIMEOUT")
        self.assertEqual(self.job.last_record["intent_reason"], "computing")

    def test_applying_and_ack_response_deadlines(self):
        proposal, process, _, _ = self.ready_proposal()
        self.job.mark_applying(proposal.token)
        self.now = jobs.RESPONSE_CAP_SECONDS
        self.exit(process, -1)
        self.assertEqual(self.job.last_record["status"], "TIMEOUT")
        self.assertEqual(self.job.last_record["intent_reason"], "applying")

    def test_ack_response_timeout_does_not_reuse_consumed_input(self):
        proposal, process, directory, _ = self.ready_proposal()
        self.job.mark_applying(proposal.token)
        after = tuple((1,) + row[1:] if index == 0 else row
                      for index, row in enumerate(proposal.snapshot.observation))
        self.job.acknowledge("PLAYING", after)
        with self.assertRaises(ValueError):
            self.job.acknowledge("PLAYING", after)
        self.assertEqual(len(list(directory.glob("parent-*.json"))), 2)
        self.now = jobs.RESPONSE_CAP_SECONDS
        self.exit(process, -1)
        self.assertEqual(self.job.last_record["status"], "TIMEOUT")
        self.assertEqual(self.job.last_record["intent_reason"], "acknowledging")
        self.assertEqual(self.job.last_record["consumed_token_count"], 1)
        self.assertEqual(self.job.last_record["ack_count"], 0)
        self.assertFalse(self.acks)

    def test_shutdown_inside_proposal_callback_has_no_late_finish(self):
        _, process, directory, _ = self.launch()
        self.job.proposal_ready.connect(lambda _proposal: self.job.shutdown())
        self.publish("PROPOSAL", proposal_to_dict(plan_snapshot(initial_snapshot())))
        self.job.poll()
        self.job.poll()
        self.assertEqual(self.job.state, "closed")
        self.assertFalse(self.finished)
        self.assertFalse(directory.exists())
        self.assertEqual(self.job.last_record["status"], "CLOSED")
        self.assertEqual(len(self.job.records), 1)

    def test_success_only_after_reap_zero_tree_and_cleanup(self):
        _, process, directory, _ = self.terminal_reply()
        self.assertFalse(self.finished)
        scope = Mock(active_count=1)
        self.job._scope = scope
        self.addCleanup(lambda: setattr(scope, "active_count", 0))
        self.exit(process)
        self.assertFalse(self.finished)
        deadline = self.job._exit_drain_deadline
        self.now = deadline - .001
        self.job.poll()
        self.assertEqual(self.job._exit_drain_deadline, deadline)
        scope.active_count = 0
        at_signal = []
        self.job.finished.connect(lambda receipt: at_signal.append(
            (self.job._process, self.job._scope, directory.exists())))
        self.job.poll()
        self.job.poll()
        self.assertEqual(at_signal, [(None, None, False)])
        self.assertEqual(self.job.last_record["status"], "SUCCEEDED")
        self.assertTrue(self.job.last_record["cleanup_complete"])
        self.assertEqual(self.job.last_record["ack_count"], 1)
        self.assertTrue(all(call.kwargs == {"timeout": 0} for call in process.wait.call_args_list))

    def test_persistent_descendant_after_fixed_drain_is_failure(self):
        _, process, _, _ = self.terminal_reply()
        scope = Mock(active_count=1)
        self.job._scope = scope
        self.addCleanup(lambda: setattr(scope, "active_count", 0))
        self.exit(process)
        deadline = self.job._exit_drain_deadline
        self.now = deadline
        self.job.poll()
        self.assertEqual(self.job._exit_drain_deadline, deadline)
        scope.terminate.assert_called()
        scope.active_count = 0
        self.job.poll()
        self.assertEqual(self.job.last_record["status"], "FAILED")
        self.assertIn("DESCENDANT_REAP", self.job.last_record["error"])

    def late_terminal_reply(self):
        proposal, process, directory, _ = self.ready_proposal()
        self.job.mark_applying(proposal.token)
        self.job.acknowledge("WON")
        self.assertEqual(self.job.state, "finishing")
        self.assertIsNone(self.job._terminal_reply)
        self.assertIsNone(self.job._finish_exit_deadline)
        self.now = 4.99
        self.publish("FINISHED", {"token": proposal.token, "input_seq": 0, "status": "WON"})
        self.job.poll()
        self.assertIsNone(self.job._deadline)
        self.assertEqual(self.job._finish_exit_deadline, self.now + jobs.EXIT_CAP_SECONDS)
        return process, directory

    def test_late_finished_then_exit_at_old_ack_cap_succeeds(self):
        process, directory = self.late_terminal_reply()
        self.now = 5.0
        self.exit(process)
        self.assertEqual(self.job.last_record["status"], "SUCCEEDED")
        self.assertEqual(self.job.last_record["ack_count"], 1)
        self.assertIsNone(self.job._finish_exit_deadline)
        self.assertFalse(directory.exists())
        process.terminate.assert_not_called()

    def test_late_finished_then_drain_crosses_old_ack_cap(self):
        process, _ = self.late_terminal_reply()
        scope = Mock(active_count=1)
        self.job._scope = scope
        self.addCleanup(lambda: setattr(scope, "active_count", 0))
        self.now = 4.995
        self.exit(process)
        drain = self.job._exit_drain_deadline
        self.assertIsNone(self.job._finish_exit_deadline)
        self.now = 5.2
        scope.active_count = 0
        self.job.poll()
        self.assertEqual(self.job.last_record["status"], "SUCCEEDED")
        self.assertEqual(self.job._exit_drain_deadline, drain)
        scope.terminate.assert_not_called()

    def test_missing_finished_keeps_terminal_ack_response_timeout(self):
        proposal, process, _, _ = self.ready_proposal()
        self.job.mark_applying(proposal.token)
        self.job.acknowledge("LOST")
        self.assertEqual(self.job.state, "finishing")
        self.assertIsNone(self.job._finish_exit_deadline)
        self.publish("FINISHED", {"token": proposal.token, "input_seq": 0, "status": "LOST"})
        self.now = jobs.RESPONSE_CAP_SECONDS
        self.exit(process)
        self.assertEqual(self.job.last_record["status"], "TIMEOUT")
        self.assertEqual(self.job.last_record["intent_reason"], "finishing")
        self.assertIsNone(self.job.last_record["terminal"])
        self.assertEqual(self.job.last_record["ack_count"], 0)

    def test_finish_exit_cap_fixed_and_exact_boundary_forces_cleanup(self):
        process, directory = self.late_terminal_reply()
        deadline = self.job._finish_exit_deadline
        (directory / "unrelated.txt").write_text("no extension", encoding="utf-8")
        for instant in (5.0, 8.0, deadline - .001):
            self.now = instant
            self.job.poll()
            self.assertEqual(self.job._finish_exit_deadline, deadline)
            process.terminate.assert_not_called()
        self.now = deadline
        self.job.poll()
        process.terminate.assert_called_once()
        self.assertIn("FINISH_EXIT_TIMEOUT", self.job._failure)
        self.assertIsNone(self.job._finish_exit_deadline)
        self.assertFalse(self.finished)
        self.now = self.job._stop_deadline
        self.job.poll()
        process.kill.assert_called_once()
        self.exit(process, -1)
        self.assertEqual(self.job.last_record["status"], "FAILED")
        self.assertIn("FINISH_EXIT_TIMEOUT", self.job.last_record["error"])
        self.assertTrue(self.job.last_record["cleanup_complete"])
        self.assertEqual(self.job.last_record["tree_active_count"], 0)
        self.assertEqual(self.job.last_record["terminal"]["status"], "WON")
        self.assertFalse(directory.exists())

    def test_exit_just_before_cap_gets_full_fixed_drain(self):
        process, _ = self.late_terminal_reply()
        deadline = self.job._finish_exit_deadline
        scope = Mock(active_count=1)
        self.job._scope = scope
        self.addCleanup(lambda: setattr(scope, "active_count", 0))
        self.now = deadline - .001
        self.exit(process)
        drain = self.now + jobs.EXIT_DRAIN_SECONDS
        self.assertEqual(self.job._exit_drain_deadline, drain)
        self.assertIsNone(self.job._finish_exit_deadline)
        for instant in (deadline, drain - .001):
            self.now = instant
            self.job.poll()
            self.assertEqual(self.job._exit_drain_deadline, drain)
            self.assertIsNone(self.job._failure)
        scope.active_count = 0
        self.job.poll()
        self.assertEqual(self.job.last_record["status"], "SUCCEEDED")
        scope.terminate.assert_not_called()

    def test_exit_just_before_cap_drain_still_expires(self):
        process, _ = self.late_terminal_reply()
        scope = Mock(active_count=1)
        self.job._scope = scope
        self.addCleanup(lambda: setattr(scope, "active_count", 0))
        self.now = self.job._finish_exit_deadline - .001
        self.exit(process)
        drain = self.job._exit_drain_deadline
        self.now = drain
        self.job.poll()
        self.assertEqual(self.job._exit_drain_deadline, drain)
        self.assertIn("DESCENDANT_REAP", self.job._failure)
        self.assertNotIn("FINISH_EXIT_TIMEOUT", self.job._failure)
        scope.active_count = 0
        self.job.poll()
        self.assertEqual(self.job.last_record["status"], "FAILED")

    def test_finish_exit_cap_includes_nonblocking_reap_confirmation(self):
        process, _ = self.late_terminal_reply()
        deadline = self.job._finish_exit_deadline
        process.poll.return_value = 0
        process.wait.side_effect = subprocess.TimeoutExpired("worker", 0)
        self.now = deadline - .001
        self.job.poll()
        self.assertEqual(self.job._finish_exit_deadline, deadline)
        self.assertIsNone(self.job._exit_drain_deadline)
        process.wait.side_effect = None
        self.now = deadline
        self.job.poll()
        self.assertEqual(self.job.last_record["status"], "FAILED")
        self.assertIn("FINISH_EXIT_TIMEOUT", self.job.last_record["error"])

    def test_reap_return_crossing_finish_exit_cap_is_failure(self):
        process, _ = self.late_terminal_reply()
        deadline = self.job._finish_exit_deadline
        self.now = deadline - .001
        process.poll.return_value = 0
        def reap(*, timeout):
            self.assertEqual(timeout, 0)
            self.now = deadline
            return 0
        process.wait.side_effect = reap
        self.job.poll()
        self.assertEqual(self.job.last_record["status"], "FAILED")
        self.assertIn("FINISH_EXIT_TIMEOUT", self.job.last_record["error"])
        self.assertTrue(self.job.last_record["cleanup_complete"])

    def test_duplicate_finished_never_extends_exit_cap_or_succeeds(self):
        process, _ = self.late_terminal_reply()
        self.now = 5.5
        self.publish("FINISHED", dict(self.job._terminal_reply))
        self.job.poll()
        self.assertIsNone(self.job._finish_exit_deadline)
        self.exit(process)
        self.assertEqual(self.job.last_record["status"], "FAILED")
        self.assertIn("Unsolicited", self.job.last_record["error"])
        self.assertEqual(self.job.last_record["ack_count"], 1)

    def test_cancel_at_finish_exit_cap_keeps_cancel_priority(self):
        process, _ = self.late_terminal_reply()
        self.now = self.job._finish_exit_deadline
        self.job.cancel("reset")
        self.assertIsNone(self.job._finish_exit_deadline)
        self.exit(process, -1)
        self.assertEqual(self.job.last_record["status"], "CANCELLED")
        self.assertIsNone(self.job.last_record["error"])

    def test_close_at_finish_exit_cap_suppresses_final_signal(self):
        _, directory = self.late_terminal_reply()
        self.now = self.job._finish_exit_deadline
        self.job.shutdown()
        self.assertEqual(self.job.state, "closed")
        self.assertIsNone(self.job._finish_exit_deadline)
        self.assertEqual(self.job.last_record["status"], "CLOSED")
        self.assertFalse(self.finished)
        self.assertFalse(directory.exists())

    def test_finish_exit_deadline_cleared_for_reuse_and_startup_failure(self):
        process, _ = self.late_terminal_reply()
        self.exit(process)
        self.assertIsNone(self.job._finish_exit_deadline)
        self.job._finish_exit_deadline = -1  # Stale prior-run state cannot leak into start.
        _, process, _, _ = self.launch(initial_snapshot("b" * 32))
        self.assertIsNone(self.job._finish_exit_deadline)
        self.assertEqual(self.job._deadline, self.now + jobs.COMPUTE_CAP_SECONDS)
        self.job.cancel("reset")
        self.exit(process, -1)
        self.job._finish_exit_deadline = -1
        with patch.object(jobs.subprocess, "Popen", side_effect=OSError("startup")), \
                patch.object(jobs, "create_scope", return_value=None):
            self.job.start(initial_snapshot("c" * 32))
        self.assertIsNone(self.job._finish_exit_deadline)
        self.job.poll()
        self.assertIn("STARTUP", self.job.last_record["error"])

    def test_finish_exit_timeout_cleanup_failure_retains_owner(self):
        process, directory = self.late_terminal_reply()
        self.now = self.job._finish_exit_deadline
        self.job.poll()
        with patch.object(jobs.shutil, "rmtree", side_effect=PermissionError("busy")):
            self.exit(process, -1)
            self.assertEqual(self.job.state, "blocked")
            self.assertIn("FINISH_EXIT_TIMEOUT", self.job.last_record["error"])
            self.assertIn("CLEANUP", self.job.last_record["error"])
            self.assertFalse(self.job.last_record["cleanup_complete"])
            with self.assertRaises(RuntimeError):
                self.job.start(initial_snapshot("b" * 32))
            with self.assertRaisesRegex(RuntimeError, "SHUTDOWN_CLEANUP"):
                self.job.shutdown()
        self.assertIsNone(self.job._finish_exit_deadline)
        self.assertEqual(self.job._directory, directory)
        self.job.shutdown()
        self.assertFalse(directory.exists())

    def test_terminal_token_type_bool_is_rejected(self):
        proposal, process, _, _ = self.ready_proposal()
        self.job.mark_applying(proposal.token)
        self.job.acknowledge("WON")
        self.publish("FINISHED", {"token": proposal.token, "input_seq": False, "status": "WON"})
        self.job.poll()
        self.exit(process, 1)
        self.assertEqual(self.job.last_record["status"], "FAILED")

    def test_normal_exit_without_terminal_receipt_is_failure(self):
        _, process, _, _ = self.launch()
        self.exit(process)
        self.assertEqual(self.job.last_record["status"], "FAILED")
        self.assertIn("UNEXPECTED_EXIT", self.job.last_record["error"])

    def late_publish_on_exit(self, *, reap_at=None, malformed=False):
        proposal, process, directory, _ = self.ready_proposal()
        self.job.mark_applying(proposal.token)
        self.job.acknowledge("WON")
        self.now = 4.9
        def exit_after_first_read():
            self.publish("FINISHED", {"token": "b" * 32 if malformed else proposal.token,
                                      "input_seq": 0, "status": "WON"})
            process.poll.side_effect = None
            process.poll.return_value = 0
            return 0
        process.poll.side_effect = exit_after_first_read
        if reap_at is not None:
            def reap(*, timeout):
                self.assertEqual(timeout, 0)
                self.now = reap_at
                return 0
            process.wait.side_effect = reap
        return proposal, process, directory

    def test_last_finished_read_after_reap_accepts_only_before_ack_cap(self):
        _, process, directory = self.late_publish_on_exit()
        with patch.object(self.job, "_read_reply", wraps=self.job._read_reply) as reads:
            self.job.poll()
        self.assertEqual(reads.call_count, 2)
        self.assertEqual(self.job.last_record["status"], "SUCCEEDED")
        self.assertEqual(self.job.last_record["ack_count"], 1)
        self.assertIsNone(self.job._finish_exit_deadline)
        self.assertFalse(directory.exists())
        process.terminate.assert_not_called()

    def test_last_finished_read_does_not_rescue_reap_at_ack_boundary(self):
        self.late_publish_on_exit(reap_at=5.0)
        with patch.object(self.job, "_read_reply", wraps=self.job._read_reply) as reads:
            self.job.poll()
        self.assertEqual(reads.call_count, 1)
        self.assertEqual(self.job.last_record["status"], "TIMEOUT")
        self.assertIsNone(self.job.last_record["terminal"])
        self.assertEqual(self.job.last_record["ack_count"], 0)

    def test_last_finished_read_is_strict_and_never_hides_tampering(self):
        self.late_publish_on_exit(malformed=True)
        self.job.poll()
        self.assertEqual(self.job.last_record["status"], "FAILED")
        self.assertTrue(self.job.last_record["error"].startswith("REPLY_TRANSPORT:"))
        self.assertEqual(self.job.last_record["ack_count"], 0)

    def test_last_finished_read_never_extends_fixed_drain(self):
        self.late_publish_on_exit()
        scope = Mock(active_count=1)
        self.job._scope = scope
        self.addCleanup(lambda: setattr(scope, "active_count", 0))
        self.job.poll()
        deadline = 4.9 + jobs.EXIT_DRAIN_SECONDS
        self.assertEqual(self.job._exit_drain_deadline, deadline)
        self.assertIsNone(self.job._finish_exit_deadline)
        self.now = deadline
        self.job.poll()
        self.assertIn("DESCENDANT_REAP", self.job._failure)
        self.assertEqual(self.job._exit_drain_deadline, deadline)
        scope.active_count = 0
        self.job.poll()
        self.assertEqual(self.job.last_record["status"], "FAILED")

    def test_last_finished_read_cancel_intent_cannot_revive_response(self):
        _, process, _ = self.late_publish_on_exit()
        self.job.cancel("manual")
        with patch.object(self.job, "_read_reply", side_effect=AssertionError("late read")):
            self.job.poll()
        self.assertEqual(self.job.last_record["status"], "CANCELLED")
        self.assertEqual(self.job.last_record["ack_count"], 0)

    def test_last_finished_read_crossing_ack_cap_cannot_rescue_receipt(self):
        self.late_publish_on_exit()
        original = self.job._read_reply
        calls = []
        def read():
            calls.append(True)
            original()
            if len(calls) == 2:
                self.now = 5.0
        with patch.object(self.job, "_read_reply", side_effect=read):
            self.job.poll()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.job.last_record["status"], "TIMEOUT")
        self.assertEqual(self.job.last_record["consumed_token_count"], 1)
        self.assertIsNone(self.job._finish_exit_deadline)

    def test_close_during_reap_preempts_last_read_and_finished_signal(self):
        _, process, directory = self.late_publish_on_exit()
        def reap(*, timeout):
            process.wait.side_effect = None
            self.job.shutdown()
            return 0
        process.wait.side_effect = reap
        with patch.object(self.job, "_read_reply", wraps=self.job._read_reply) as reads:
            self.job.poll()
        self.assertEqual(reads.call_count, 1)
        self.assertEqual(self.job.state, "closed")
        self.assertFalse(self.finished)
        self.assertFalse(directory.exists())
        self.assertEqual(self.job.last_record["status"], "CLOSED")

    def test_flag_review_ack_advances_phase_revision_and_prep_count(self):
        snapshot = replace(initial_snapshot(), width=3, height=1, num_mines=1,
                           observation=((-3, 1, -2),), cursor=(2, 0),
                           entry_mode="ADOPT_CURRENT", input_revision=503,
                           phase="FLAG_REVIEW", initial_flag_count=1)
        _, process, _, _ = self.launch(snapshot)
        proposal = plan_snapshot(snapshot)
        self.assertEqual((proposal.phase, proposal.action, proposal.kind),
                         ("FLAG_REVIEW", "FLAG", "flag_review"))
        self.publish("PROPOSAL", proposal_to_dict(proposal))
        self.job.poll()
        self.job.mark_applying(proposal.token)
        self.job.acknowledge("PLAYING", ((-2, 1, -2),))
        ack = self.job._sent_ack
        self.publish("ACKED", ack_to_dict(ack))
        self.job.poll()
        expected = validate_ack(proposal, ack)
        self.assertEqual(self.job._expected_snapshot, expected)
        self.assertEqual((expected.input_seq, expected.input_revision,
                          expected.review_inputs, expected.phase), (1, 504, 1, "V1"))
        self.assertEqual(self.job._review_proposal_count, 1)
        self.assertEqual(self.job._v1_proposal_count, 0)
        self.job.request(expected)
        self.assertEqual(self.job.state, "computing")
        self.job.cancel("manual")
        self.exit(process, -1)
        self.assertEqual(self.job.last_record["entry_mode"], "ADOPT_CURRENT")
        self.assertEqual(self.job.last_record["start_input_revision"], 503)

    def test_flag_review_compute_timeout_never_publishes_late_result(self):
        snapshot = replace(initial_snapshot(), width=3, height=1, num_mines=1,
                           observation=((-3, 1, -2),), entry_mode="ADOPT_CURRENT",
                           input_revision=1, phase="FLAG_REVIEW", initial_flag_count=1)
        _, process, _, _ = self.launch(snapshot)
        self.publish("PROPOSAL", proposal_to_dict(plan_snapshot(snapshot)))
        self.now = jobs.COMPUTE_CAP_SECONDS
        self.exit(process, -1)
        self.assertEqual(self.job.last_record["status"], "TIMEOUT")
        self.assertFalse(self.proposals)
        self.assertEqual(self.job.last_record["consumed_token_count"], 0)

    def test_worker_error_diagnostic_is_preserved_not_game_loss(self):
        _, process, directory, _ = self.launch()
        self.publish("ERROR", {"code": "POLICY", "detail": "synthetic error"})
        (directory / "stderr.txt").write_text("x" * 20000 + "root cause", encoding="utf-8")
        self.job.poll()
        self.exit(process, 1)
        self.assertEqual(self.job.last_record["status"], "FAILED")
        self.assertIn("synthetic error", self.job.last_record["error"])
        self.assertIn("root cause", self.job.last_record["stderr"])
        self.assertLessEqual(len(self.job.last_record["stderr"].encode()), 16384)
        self.assertIsNone(self.job.last_record["terminal"])

    def test_cleanup_failure_retains_ownership_and_blocks_new_run(self):
        _, process, directory, _ = self.terminal_reply()
        with patch.object(jobs.shutil, "rmtree", side_effect=PermissionError("busy")):
            self.exit(process)
        self.assertEqual(self.job.state, "blocked")
        self.assertTrue(directory.exists())
        self.assertFalse(self.job.last_record["cleanup_complete"])
        with self.assertRaises(RuntimeError):
            self.job.start(initial_snapshot("b" * 32))
        self.job.shutdown()
        self.assertFalse(directory.exists())

    def test_startup_failure_emits_only_after_return(self):
        with patch.object(jobs.subprocess, "Popen", side_effect=OSError("startup")), \
                patch.object(jobs, "create_scope", return_value=None):
            run_id = self.job.start(initial_snapshot())
        self.assertEqual(run_id, initial_snapshot().run_id)
        self.assertFalse(self.finished)
        self.job.poll()
        self.assertEqual(self.job.last_record["status"], "FAILED")
        self.assertTrue(self.job.last_record["cleanup_complete"])

    def test_shutdown_reap_failure_keeps_owner_and_suppresses_reply(self):
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

    def test_kill_escalation_then_reap(self):
        _, process, directory, _ = self.launch()
        self.job.cancel()
        self.now = .49
        self.job.poll()
        process.kill.assert_not_called()
        self.now = .5
        self.job.poll()
        process.kill.assert_called_once()
        self.assertTrue(directory.exists())
        self.exit(process, -1)
        self.assertTrue(self.job.last_record["reaped"])


class LivePolicyRealWorkerTests(unittest.TestCase):
    """Six small worker launches per suite invocation; zero public games."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.job = jobs.LivePolicyJob()
        self.finished = QSignalSpy(self.job.finished)
        self.proposals = QSignalSpy(self.job.proposal_ready)
        self.addCleanup(self.job.shutdown)

    def wait_until(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition(), self.job.last_record)

    def fixture(self, mode="tree"):
        fixture = Path(__file__).parent / "fixtures" / "live_policy_worker.py"
        def command(directory, run_id, scope_name):
            return [sys.executable, "-B", str(fixture), str(directory), run_id, scope_name, mode]
        with patch.object(jobs, "build_worker_command", side_effect=command):
            self.job.start(initial_snapshot())
        directory = self.job._directory
        self.wait_until(lambda: (directory / "fixture-ready.json").exists())
        ready = json.loads((directory / "fixture-ready.json").read_text())
        self.assertIsInstance(ready["pid"], int)
        print("SYNTHETIC_WORKER_START " + json.dumps({"mode": mode, **ready}), flush=True)
        if mode == "tree":
            self.assertIsInstance(ready["descendant_pid"], int)
            if os.name == "nt":
                self.assertGreaterEqual(self.job._scope.active_count, 2)
        return self.job._process, directory

    def assert_clean(self, process, directory):
        self.assertIsNotNone(process.poll())
        self.assertFalse(directory.exists())
        self.assertTrue(self.job.last_record["reaped"])
        self.assertEqual(self.job.last_record["tree_active_count"], 0)
        self.assertTrue(self.job.last_record["cleanup_complete"])
        print("SYNTHETIC_WORKER_CLEANUP " + json.dumps(self.job.last_record), flush=True)

    def test_actual_worker_public_initial_and_terminal_protocol(self):
        self.job.start(initial_snapshot())
        process, directory = self.job._process, self.job._directory
        print("SYNTHETIC_WORKER_START " + json.dumps(
            {"mode": "actual_initial_terminal_protocol", "launcher_pid": process.pid}), flush=True)
        self.wait_until(lambda: bool(self.proposals))
        proposal = self.proposals[0][0]
        self.assertEqual((proposal.action, proposal.x, proposal.y), ("OPEN", 0, 0))
        self.assertEqual(proposal.compute_ns, 0)
        QTest.qWait(100)
        self.assertEqual(len(self.proposals), 1)
        self.job.mark_applying(proposal.token)
        self.job.acknowledge("WON")  # Explicit synthetic terminal ACK; no engine game.
        self.wait_until(lambda: bool(self.finished))
        self.assertEqual(self.job.last_record["status"], "SUCCEEDED")
        self.assert_clean(process, directory)

    def test_actual_worker_adopt_review_unflag_then_frozen_guess(self):
        snapshot = replace(initial_snapshot(), width=3, height=1, num_mines=1,
                           observation=((-3, 1, -2),), cursor=(0, 0),
                           entry_mode="ADOPT_CURRENT", input_revision=501,
                           phase="FLAG_REVIEW", initial_flag_count=1)
        self.job.start(snapshot)
        process, directory = self.job._process, self.job._directory
        print("SYNTHETIC_WORKER_START " + json.dumps(
            {"mode": "actual_adopt_review", "launcher_pid": process.pid}), flush=True)
        self.wait_until(lambda: bool(self.proposals))
        preparation = self.proposals[0][0]
        self.assertEqual((preparation.phase, preparation.action, preparation.x, preparation.y),
                         ("FLAG_REVIEW", "FLAG", 0, 0))
        self.assertEqual(preparation.review.unverified, ((0, 0),))
        self.assertEqual(preparation.compute_ns, 0)
        self.job.mark_applying(preparation.token)
        self.job.acknowledge("PLAYING", ((-2, 1, -2),))
        self.wait_until(lambda: self.job.state == "ready")
        self.assertEqual(self.job._expected_snapshot.input_revision, 502)
        self.assertEqual(self.job._expected_snapshot.phase, "V1")
        self.job.request(self.job._expected_snapshot)
        self.wait_until(lambda: len(self.proposals) == 2)
        guess = self.proposals[1][0]
        self.assertEqual((guess.phase, guess.kind, guess.action), ("V1", "guess", "OPEN"))
        self.assertEqual(guess.snapshot.review_inputs, 1)
        self.assertEqual(self.job._applied_count, 1)
        self.job.cancel("synthetic_guess_off_no_open")
        self.wait_until(lambda: bool(self.finished))
        self.assertEqual(self.job.last_record["status"], "CANCELLED")
        self.assertEqual(self.job.last_record["consumed_token_count"], 1)
        self.assertEqual(self.job.last_record["preparation_proposal_count"], 1)
        self.assertEqual(self.job.last_record["v1_proposal_count"], 1)
        self.assert_clean(process, directory)

    def test_actual_tree_cancel_keeps_qt_heartbeat_and_reaps(self):
        ticks = []
        timer = QTimer()
        timer.setInterval(5)
        timer.timeout.connect(lambda: ticks.append(time.monotonic()))
        timer.start()
        self.addCleanup(timer.stop)
        process, directory = self.fixture()
        QTest.qWait(50)
        self.assertGreater(len(ticks), 1)
        self.job.cancel("synthetic_cancel")
        self.wait_until(lambda: bool(self.finished))
        self.assertEqual(self.job.last_record["status"], "CANCELLED")
        self.assert_clean(process, directory)

    def test_actual_tree_timeout_reaps(self):
        process, directory = self.fixture()
        self.job._deadline = time.monotonic() - 1  # Inject clock boundary, do not wait30s.
        self.wait_until(lambda: bool(self.finished))
        self.assertEqual(self.job.last_record["status"], "TIMEOUT")
        self.assert_clean(process, directory)

    def test_actual_tree_close_reaps_without_late_signal(self):
        process, directory = self.fixture()
        self.job.shutdown()
        QTest.qWait(30)
        self.assertFalse(self.finished)
        self.assertEqual(self.job.state, "closed")
        self.assert_clean(process, directory)

    def test_actual_wrong_identity_never_admitted(self):
        process, directory = self.fixture("wrong_identity")
        self.wait_until(lambda: bool(self.finished))
        self.assertFalse(self.proposals)
        self.assertEqual(self.job.last_record["status"], "FAILED")
        self.assert_clean(process, directory)


if __name__ == "__main__":
    unittest.main()
