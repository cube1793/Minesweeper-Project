"""Replay entry transaction: real Qt/engine/ACK handlers, explicitly fake jobs."""
from dataclasses import replace
from unittest.mock import patch

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest

from core_engine import GameStatus, MinesweeperEngine
import live_k_policy as k
from live_policy import POLICY_SIMPLE, POLICY_V1, plan_snapshot
from live_same_board import CompletedLiveGame, FixedLayout
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from tests.test_live_auto import SyntheticLivePolicyJob, advance_auto_timer
from tests.test_live_same_board_history_ui import SameBoardHistoryUI
from tests.test_live_same_board_ui import MixedFakeJob
from ui_manager import MinesweeperUI


MINES = frozenset({(1, 0)} | {(x, 8) for x in range(9)})


class EntryJob(MixedFakeJob):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cancel_reasons = []
        self.sync_cancel = False

    def cancel(self, reason='CANCELLED'):
        self.cancel_reasons.append(reason)
        super().cancel(reason)
        if self.sync_cancel:
            self.complete_cancel()

    def deliver_ack(self):
        if self.owner is None:
            SyntheticLivePolicyJob.deliver_ack(self)
        else:
            super().deliver_ack()

    def finish_record(self, *, cleanup=True, error=None, terminal=False):
        ack = self.acks[-1] if self.acks else None
        record = dict(run_id=self.active_run_id, policy_id=self.requests[-1].policy_id,
                      status='SUCCEEDED' if terminal else 'FAILED' if error else 'CANCELLED',
                      cleanup_complete=cleanup, reaped=True, tree_active_count=0, error=error)
        if terminal:
            if type(ack) is k.KAck:
                record['last_k_ack'] = k.to_dict(ack)
            else:
                record['terminal'] = dict(token=ack.token, input_seq=ack.input_seq, status=ack.status)
        self.active_run_id = None
        self.state = 'idle' if cleanup else 'blocked'
        self.records.append(record)
        self.last_record = record
        self.finished.emit(record)
        return record


class ReplayEntryUI(SameBoardHistoryUI):
    # Inherited helpers only; the runner registers explicit new method IDs.
    def make_ui(self, policy=POLICY_SIMPLE, layout=None):
        layout = layout or FixedLayout(9, 9, 10, MINES)
        with patch('ui_manager.LivePolicyJob', EntryJob):
            ui = MinesweeperUI(MinesweeperEngine(layout.width, layout.height, layout.num_mines))
        self.uis.append(ui)
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
        ui.on_reset()
        layout.reset_engine(ui.engine)
        return ui

    def pump(self):
        self.app.processEvents()
        self.app.processEvents()

    def pending_input(self, policy=k.POLICY_K_LC1, *, terminal=False):
        mines = frozenset({(0, 0)} | {(x, 8) for x in range(9)}) if terminal else MINES
        ui = self.make_ui(policy, FixedLayout(9, 9, 10, mines))
        old = self.activate(ui)
        ui.simple_auto_checkbox.setChecked(True)
        job = ui._v1_job
        if policy == POLICY_V1:
            job.deliver(plan_snapshot(job.requests[-1]))
        else:
            job.compute()
        self.assertTrue(job.pending.is_guess)
        ui.allow_guess_checkbox.setChecked(True)
        advance_auto_timer(ui)
        if policy != POLICY_V1:
            job.deliver_admission()
        self.assertEqual(job.state, 'acknowledging')
        self.assertEqual(ui._live_action_count, 1)
        self.assertEqual(len(ui._replay_recorder.events), 1)
        self.assertIsNotNone(ui._v1_expected_ack)
        return ui, job, old

    def assert_live_unchanged(self, ui, identity, events, group):
        self.assertFalse(ui._replay_mode)
        self.assertIsNone(ui._replay_player)
        self.assertEqual(ui._live_game_id, identity)
        self.assertEqual(ui._replay_recorder.events, events)
        self.assertEqual(ui._same_board_completed_games, group)

    def test_ack_then_cleanup_commits_once_and_blocks_auto_next_duplicates(self):
        for policy in (POLICY_V1, k.POLICY_K_LC1):
            with self.subTest(policy=policy):
                ui, job, old = self.pending_input(policy)
                identity, events = ui._live_game_id, ui._replay_recorder.events
                requests = len(job.requests)
                other = ReplayPlayer(ReplayData(ReplayBoard(5, 1, 1, {(2, 0)}), ()))
                with patch.object(ui, '_commit_replay_entry', wraps=ui._commit_replay_entry) as commit:
                    self.assertTrue(ui._enter_replay_mode(ReplayPlayer(old.replay)))
                    token = ui._replay_entry_pending.token
                    self.assertTrue(ui._enter_replay_mode(ReplayPlayer(old.replay)))
                    self.assertFalse(ui._enter_replay_mode(other))
                    self.assertEqual(ui._replay_entry_pending.token, token)
                    self.assertEqual(job.cancel_reasons, [])
                    self.assert_live_unchanged(ui, identity, events, [old])
                    self.assertIn('Replay 준비 중', ui.live_policy_status_label.text())
                    self.assertFalse(ui.allow_guess_checkbox.isChecked())
                    ui.simple_auto_checkbox.setChecked(True)
                    ui._analyze_v1_current()
                    self.assertFalse(ui.simple_auto_checkbox.isChecked())
                    self.assertEqual(len(job.requests), requests)
                    self.assertEqual(commit.call_count, 0)
                    job.deliver_ack()
                    self.pump()
                    self.assert_live_unchanged(ui, identity, events, [old])
                    self.assertEqual(job.state, 'cancelling')
                    self.assertEqual(len(job.cancel_reasons), 1)
                    self.assertEqual(commit.call_count, 0)
                    job.complete_cancel()
                    record = job.records[-1]
                    self.pump()
                    self.assertTrue(ui._replay_mode)
                    self.assertEqual(commit.call_count, 1)
                    job.finished.emit(record)
                    job.acknowledged.emit(job.acks[-1])
                    self.pump()
                    self.assertEqual(commit.call_count, 1)
                    self.assertEqual(len(job.requests), requests)
                    self.assertTrue(ui._exit_replay_mode())
                    self.assert_fresh_canonical(ui, (9, 9, 10), identity, 0)

    def test_ack_cancel_synchronous_finished_slot_order_commits_once(self):
        for policy in (POLICY_V1, k.POLICY_K_LC1):
            with self.subTest(policy=policy):
                ui, job, old = self.pending_input(policy)
                job.sync_cancel = True
                ui._enter_replay_mode(ReplayPlayer(old.replay))
                with patch.object(ui, '_commit_replay_entry', wraps=ui._commit_replay_entry) as commit:
                    job.deliver_ack()
                    self.pump()
                    self.assertTrue(ui._replay_mode)
                    self.assertEqual(commit.call_count, 1)
                    self.assertEqual(len(job.cancel_reasons), 1)
                    self.assertEqual(ui.live_failure_records, [])

    def test_missing_tampered_ack_worker_error_and_cleanup_failure_stay_live(self):
        for policy in (POLICY_V1, k.POLICY_K_LC1):
            for failure in ('missing', 'tampered', 'worker', 'cleanup'):
                with self.subTest(policy=policy, failure=failure):
                    ui, job, old = self.pending_input(policy)
                    identity, events = ui._live_game_id, ui._replay_recorder.events
                    ui._enter_replay_mode(ReplayPlayer(old.replay))
                    if failure == 'tampered':
                        ack = job.acks[-1]
                        # A structurally valid but unequal receipt; validators remain real.
                        job.acknowledged.emit(replace(ack, status='LOST', observation=None))
                    elif failure == 'cleanup':
                        job.deliver_ack()
                        self.pump()
                    record = job.finish_record(cleanup=failure != 'cleanup',
                                               error='ACK_TIMEOUT: original worker reason' if failure == 'worker' else None)
                    self.pump()
                    self.assert_live_unchanged(ui, identity, events, [old])
                    self.assertIsNone(ui._replay_entry_pending)
                    first = dict(ui._live_first_failure)
                    self.assertTrue(first['cause'])
                    if failure == 'worker':
                        self.assertIn('ACK_TIMEOUT', first['cause'])
                    elif failure == 'missing':
                        self.assertIn('ACK', first['cause'])
                    elif failure == 'cleanup':
                        self.assertIn('정리 실패', first['cause'])
                    self.assertIn(first['cause'], ui.live_policy_status_label.text())
                    job.finished.emit(record)
                    ui._enter_replay_mode(ReplayPlayer(old.replay))
                    ui.simple_auto_checkbox.setChecked(True)
                    self.pump()
                    self.assertEqual(ui._live_first_failure['cause'], first['cause'])
                    self.assertEqual(len(job.requests), 1)
                    self.assertFalse(ui._replay_mode)

    def test_v1_compute_ready_cancel_and_synchronous_finished_races(self):
        for phase in ('computing', 'ready', 'cancelling', 'sync'):
            with self.subTest(phase=phase):
                ui = self.make_ui(POLICY_V1)
                old = self.activate(ui)
                ui.simple_auto_checkbox.setChecked(True)
                job = ui._v1_job
                if phase == 'ready':
                    job.state = 'ready'
                elif phase == 'cancelling':
                    ui._invalidate_v1_run('existing retirement', drain_ack=True)
                elif phase == 'sync':
                    job.sync_cancel = True
                with patch.object(ui, '_commit_replay_entry', wraps=ui._commit_replay_entry) as commit:
                    ui._enter_replay_mode(ReplayPlayer(old.replay))
                    self.assertFalse(ui._replay_mode)
                    self.assertEqual(commit.call_count, 0)
                    if phase != 'sync':
                        job.complete_cancel()
                    self.pump()
                    self.assertTrue(ui._replay_mode)
                    self.assertEqual(commit.call_count, 1)
                    self.assertEqual(len(job.requests), 1)

    def test_pending_cancel_boundaries_and_late_finished_never_commit(self):
        for boundary in ('reset', 'difficulty', 'policy', 'manual_press', 'close', 'space', 'return'):
            with self.subTest(boundary=boundary):
                ui = self.make_ui(POLICY_V1)
                old = self.activate(ui)
                ui.simple_auto_checkbox.setChecked(True)
                job = ui._v1_job
                ui._enter_replay_mode(ReplayPlayer(old.replay))
                token = ui._replay_entry_pending.token
                if boundary == 'reset':
                    ui.on_reset()
                elif boundary == 'difficulty':
                    ui.on_difficulty_changed('중급 (16x16, 40)')
                elif boundary == 'policy':
                    ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(POLICY_SIMPLE))
                elif boundary in ('space', 'return', 'manual_press'):
                    ui.show()
                    ui.activateWindow()
                    ui.setFocus(Qt.OtherFocusReason)
                    self.pump()
                    if boundary == 'manual_press':
                        before = ui._live_action_count
                        QTest.mousePress(ui._buttons[(0, 0)], Qt.LeftButton, pos=QPoint(10, 10))
                        self.assertEqual(ui._live_action_count, before)  # Cancel on press, before release.
                    else:
                        QTest.keyClick(ui.windowHandle(), Qt.Key_Space if boundary == 'space' else Qt.Key_Return)
                else:
                    ui.close()
                self.assertIsNone(ui._replay_entry_pending)
                group = tuple(ui._same_board_completed_games)
                events = tuple(ui._replay_recorder.events)
                job.complete_cancel()
                ui._advance_replay_entry(token)
                self.pump()
                self.assertFalse(ui._replay_mode)
                self.assertEqual(tuple(ui._same_board_completed_games), group)
                self.assertEqual(ui._replay_recorder.events, events)
                self.assertEqual(len(job.requests), 1)

    def test_pending_k_ack_after_manual_press_does_not_open_or_mutate_current(self):
        ui, job, old = self.pending_input()
        ui._enter_replay_mode(ReplayPlayer(old.replay))
        ui._retire_v1_for_manual('manual press path')
        self.assertIsNone(ui._replay_entry_pending)
        ui.on_left_click(2, 0)
        history, events, cursor = tuple(ui.live_input_records), ui._replay_recorder.events, ui._v1_cursor
        job.deliver_ack()
        job.complete_cancel()
        self.pump()
        self.assertFalse(ui._replay_mode)
        self.assertEqual(tuple(ui.live_input_records), history)
        self.assertEqual(ui._replay_recorder.events, events)
        self.assertEqual(ui._v1_cursor, cursor)
        self.assertEqual(ui._same_board_completed_games, [old])

    def test_binding_change_without_hook_discards_request_and_target_is_detached(self):
        for mutation in ('game', 'generation', 'history', 'source'):
            with self.subTest(mutation=mutation):
                ui = self.make_ui(POLICY_V1)
                old = self.activate(ui)
                ui.simple_auto_checkbox.setChecked(True)
                ui._enter_replay_mode(ReplayPlayer(old.replay))
                if mutation == 'game':
                    ui._live_game_id = 'different-game'
                elif mutation == 'generation':
                    ui._live_board_generation += 1
                elif mutation == 'history':
                    ui.live_input_records.append({'foreign': True})
                else:
                    ui._replay_recorder.source_type = 'algorithm'
                ui._v1_job.complete_cancel()
                self.pump()
                self.assertFalse(ui._replay_mode)
                self.assertIsNone(ui._replay_entry_pending)
                self.assertEqual(ui._same_board_completed_games, [old])

    def test_pending_target_uses_captured_replay_and_rejects_missing_owner_identity(self):
        ui = self.make_ui(POLICY_V1)
        old = self.activate(ui)
        ui.simple_auto_checkbox.setChecked(True)
        player = ReplayPlayer(old.replay)
        ui._enter_replay_mode(player)
        player.replay_data = ReplayData(ReplayBoard(5, 1, 1, {(2, 0)}), ())
        ui._v1_job.complete_cancel()
        self.pump()
        self.assertTrue(ui._replay_mode)
        self.assertEqual(ui._replay_data, old.replay)
        self.assertIsNot(ui._replay_player, player)
        ui._exit_replay_mode()
        ui._v1_job.state = 'cancelling'
        self.assertFalse(ui._enter_replay_mode(ReplayPlayer(old.replay)))
        self.assertIsNone(ui._replay_entry_pending)
        self.assertFalse(ui._replay_mode)
        self.assertIn('identity', ui.live_policy_status_label.text())
        ui._v1_job.state = 'idle'

    def test_terminal_capture_only_after_ack_cleanup_and_deduplicated(self):
        for policy in (POLICY_V1, k.POLICY_K_LC1):
            with self.subTest(policy=policy):
                ui, job, old = self.pending_input(policy, terminal=True)
                current_id = ui._live_game_id
                frozen = (old.replay, old.evidence_json)
                ui._view_completed_live_game(old)
                self.assertFalse(ui._replay_mode)
                ui.same_board_history_menu.aboutToShow.emit()
                self.assertEqual(ui._same_board_completed_games, [old])
                job.finish_record(terminal=True)
                self.pump()
                self.assertTrue(ui._replay_mode)
                self.assertEqual([g.game_id for g in ui._same_board_completed_games], [old.game_id, current_id])
                current = ui._same_board_completed_games[1]
                self.assertEqual(current.replay.source_type, 'algorithm')
                self.assertIn('cleanup_complete', current.evidence_json)
                ui._view_completed_live_game(old)
                self.assertEqual(len(ui._same_board_completed_games), 2)
                self.assertEqual((old.replay, old.evidence_json), frozen)

    def test_capture_failure_keeps_specific_reason_and_foreign_group_until_commit(self):
        for failure in ('history', 'capture'):
            with self.subTest(failure=failure):
                ui = self.make_ui()
                old = self.activate(ui)
                self.finish(ui)
                foreign = ReplayPlayer(ReplayData(ReplayBoard(5, 1, 1, {(2, 0)}), ()))
                if failure == 'history':
                    ui._live_history_known = False
                    self.assertFalse(ui._enter_replay_mode(foreign))
                    text = '실제 입력 이력'
                else:
                    with patch.object(CompletedLiveGame, 'capture', side_effect=ValueError('specific detached evidence failure')):
                        self.assertFalse(ui._enter_replay_mode(foreign))
                    text = 'specific detached evidence failure'
                self.assertFalse(ui._replay_mode)
                self.assertEqual(ui._same_board_completed_games, [old])
                ui._update_policy_controls()
                self.assertIn(text, ui.live_policy_status_label.text())

    def test_foreign_pending_commit_success_failure_cancel_and_load_invalid(self):
        foreign = ReplayData(ReplayBoard(5, 1, 1, {(2, 0)}), (ReplayEvent(.1, 0, 0, 'OPEN'),))
        for outcome in ('success', 'failure', 'cancel'):
            with self.subTest(outcome=outcome):
                ui = self.make_ui(POLICY_V1)
                old = self.activate(ui)
                ui.simple_auto_checkbox.setChecked(True)
                self.load(ui, self.save_fixture(foreign, outcome+'.json'))
                self.assertFalse(ui._replay_mode)
                self.assertEqual(ui._same_board_completed_games, [old])
                if outcome == 'cancel':
                    ui._retire_v1_for_manual('manual')
                ui._v1_job.finish_record(error='cleanup original error' if outcome == 'failure' else None)
                self.pump()
                if outcome == 'success':
                    self.assertTrue(ui._replay_mode)
                    self.assert_empty_group(ui)
                    self.assertTrue(ui._exit_replay_mode())
                    self.assertEqual(ui._normal_game_config, (5, 1, 1))
                else:
                    self.assertFalse(ui._replay_mode)
                    self.assertEqual(ui._same_board_completed_games, [old])

    def test_simple_immediate_and_replay_to_replay_never_wait_or_capture_live(self):
        ui = self.make_ui()
        old = self.activate(ui)
        with patch.object(ui, '_capture_completed_for_history', wraps=ui._capture_completed_for_history) as capture:
            self.assertTrue(ui._enter_replay_mode(ReplayPlayer(old.replay)))
            self.assertTrue(ui._replay_mode)
            self.assertIsNone(ui._replay_entry_pending)
            with patch.object(ui, '_invalidate_v1_run', side_effect=AssertionError('Replay has no Live drain')):
                self.assertTrue(ui._enter_replay_mode(ReplayPlayer(old.replay)))
            self.assertEqual(len(ui._same_board_completed_games), 1)
            self.assertEqual(capture.call_count, 2)  # Second call is the explicit Replay no-op guard.

