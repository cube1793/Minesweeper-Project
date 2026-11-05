"""Real Qt/engine/Replay with fake transport; never native or IPC evidence."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication
from core_engine import Action, GameStatus, MinesweeperEngine
import live_k_policy as k
from live_policy import POLICY_SIMPLE, POLICY_V1, FIXED_BOARD, plan_snapshot
from live_same_board import FixedOrigin, FixedLayout
from tests.ui_settings import isolate_ui_settings
from tests.test_live_auto import SyntheticLivePolicyJob, advance_auto_timer
from tests.test_live_k_ui import KUIFakeJob
from ui_manager import MinesweeperUI


class MixedFakeJob(KUIFakeJob):
    def start(self, snapshot):
        self.owner = None
        return super().start(snapshot)

    def mark_applying(self, token, nonce=None):
        if self.owner is None:
            return SyntheticLivePolicyJob.mark_applying(self, token)
        return super().mark_applying(token, nonce)

    def acknowledge(self, status, observation=None):
        if self.owner is None:
            return SyntheticLivePolicyJob.acknowledge(self, status, observation)
        return super().acknowledge(status, observation)


class SameBoardUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        isolate_ui_settings(self)
        for target in ('_ensure_zini_metric_job',):
            p = patch.object(MinesweeperUI, target, return_value=None)
            p.start()
            self.addCleanup(p.stop)
        self.uis = []
        self.addCleanup(self.close_all)

    def close_all(self):
        for ui in self.uis:
            ui.close()
            ui.deleteLater()
        self.app.processEvents()

    def create(self, policy=POLICY_SIMPLE, mines=((2, 0),), dims=(5, 1, 1), seam=False):
        with patch('ui_manager.LivePolicyJob', MixedFakeJob):
            ui = MinesweeperUI(MinesweeperEngine(*dims))
        self.uis.append(ui)
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
        ui.on_reset()
        if seam:
            ui._v1_supported = lambda: True  # Explicit 5x1 synthetic contract fixture only.
        ui.engine.reset_with_mines(*dims, mines)
        ui.on_left_click(*next(iter(mines)))
        self.assertEqual(ui.engine.status, GameStatus.LOST)
        ui.on_same_board_retry()
        self.assertEqual(ui.engine.status, GameStatus.PLAYING)
        return ui

    def test_lost_repeat_twice_new_identity_and_detached_records(self):
        ui = self.create()
        first = ui._same_board_completed_games[0]
        ids = {first.game_id, ui._live_game_id}
        for _ in range(2):
            old_game, old_run, old_generation = ui._live_game_id, ui._live_run_id, ui._live_board_generation
            ui.on_left_click(2, 0)
            self.assertTrue(ui.same_board_retry_button.isEnabled())
            ui.on_same_board_retry()
            self.assertNotIn(ui._live_game_id, ids)
            ids.add(ui._live_game_id)
            self.assertNotEqual(ui._live_run_id, old_run)
            self.assertGreater(ui._live_board_generation, old_generation)
            self.assertEqual(ui.live_input_records, [])
            self.assertEqual(ui.live_action_records, [])
            self.assertEqual(ui.live_owner_records, [])
            self.assertEqual(ui._replay_recorder.events, ())
            self.assertTrue(all(v == 0 for v in ui.live_auto_totals.values()))
            self.assertEqual(ui.engine.get_elapsed_time(), 0)
            self.assertEqual(ui._k_base_m, ())
            self.assertEqual(ui._k_m_revision, 0)
            self.assertIsNone(ui._k_deferred_permit)
            self.assertIsNone(ui._fixed_cadence)
            self.assertEqual(ui._same_board_completed_games[-1].game_id, old_game)
        self.assertEqual(len(first.replay.events), 1)
        self.assertEqual(len(json.loads(first.evidence_json)['inputs']), 1)

    def test_won_retry_preserves_preferences_and_layout(self):
        ui = self.create()
        ui.simple_auto_interval_spin.setValue(125)
        ui.probability_checkbox.setChecked(False)
        ui.auto_cursor_checkbox.setChecked(False)
        ui.on_left_click(0, 0)
        ui.on_left_click(4, 0)
        self.assertEqual(ui.engine.status, GameStatus.WON)
        ui.on_same_board_retry()
        self.assertEqual(ui._same_board_completed_games[-1].status, 'WON')
        self.assertEqual(ui.engine.get_board_snapshot().mines, frozenset({(2, 0)}))
        self.assertEqual(ui._fixed_period.period_ns, 125000000)
        self.assertFalse(ui.probability_checkbox.isChecked())
        self.assertFalse(ui.auto_cursor_checkbox.isChecked())
        self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertFalse(ui.allow_guess_checkbox.isChecked())

    def test_simple_fixed_guess_wait_then_first_auto_can_lose_or_open(self):
        for mine, terminal in ((0, GameStatus.LOST), (2, GameStatus.PLAYING)):
            with self.subTest(mine=mine):
                ui = self.create(mines=((mine, 0),))
                ui.simple_auto_checkbox.setChecked(True)
                self.assertFalse(ui._analysis_first_click)
                self.assertEqual(ui._live_action_count, 0)
                self.assertFalse(ui._simple_auto_pending)
                ui.allow_guess_checkbox.setChecked(True)
                advance_auto_timer(ui)
                self.assertEqual(ui._live_action_count, 1)
                self.assertEqual(ui.engine.status, terminal)
                self.assertEqual(ui._replay_recorder.source_type, 'algorithm')

    def test_v1_fixed_start_from_zero_is_guess_and_stale_proposal_is_ignored(self):
        ui = self.create(POLICY_V1, mines=((0, 0),), seam=True)
        ui.simple_auto_checkbox.setChecked(True)
        job = ui._v1_job
        proposal = plan_snapshot(job.requests[-1])
        self.assertEqual(proposal.snapshot.entry_mode, FIXED_BOARD)
        self.assertEqual(proposal.snapshot.fixed_game_id, ui._live_game_id)
        job.deliver(proposal)
        self.assertTrue(proposal.is_guess)
        self.assertFalse(ui._simple_auto_pending)
        ui.allow_guess_checkbox.setChecked(True)
        advance_auto_timer(ui)
        self.assertEqual(ui.engine.status, GameStatus.LOST)
        self.assertFalse(ui.same_board_retry_button.isEnabled())
        record = dict(run_id=proposal.snapshot.run_id, status='SUCCEEDED', cleanup_complete=True,
                      reaped=True, tree_active_count=0, error=None)
        job.state = 'idle'
        job.finished.emit(record)
        ui.on_same_board_retry()
        job.proposal_ready.emit(proposal)
        self.assertEqual(ui._live_action_count, 0)
        self.assertIsNone(ui._v1_pending)
        self.assertIsNone(ui._certainty_frame)

    def test_all_k_fixed_first_auto_wait_validate_safe_and_lost(self):
        for policy in (k.POLICY_K, k.POLICY_K_LC0, k.POLICY_K_LC1):
            for mine in (0, 2):
                with self.subTest(policy=policy, mine=mine):
                    ui = self.create(policy, mines=((mine, 0),), seam=True)
                    ui.simple_auto_checkbox.setChecked(True)
                    job = ui._v1_job
                    job.compute()
                    p = job.pending
                    self.assertEqual(p.snapshot.entry_mode, FIXED_BOARD)
                    self.assertTrue(p.is_guess)
                    self.assertFalse(p.initial)
                    self.assertEqual(job.validations, [])
                    self.assertEqual(ui._live_action_count, 0)
                    ui.allow_guess_checkbox.setChecked(True)
                    advance_auto_timer(ui)
                    permit = job.deliver_admission()
                    self.assertEqual(ui._live_action_count, 1)
                    self.assertEqual(len(job.acks), 1)
                    self.assertEqual(ui.engine.status, GameStatus.LOST if mine == 0 else GameStatus.PLAYING)
                    self.assertEqual(ui.engine.get_board_snapshot().mines, frozenset({(mine, 0)}))
                    if mine == 0:
                        record = dict(run_id=p.snapshot.run_id, policy_id=policy, status='SUCCEEDED',
                                      cleanup_complete=True, reaped=True, tree_active_count=0,
                                      error=None, last_k_ack=k.to_dict(job.acks[-1]))
                        job.state = 'idle'
                        job.finished.emit(record)
                        ui.on_same_board_retry()
                        job.admitted.emit(permit)
                        self.assertEqual(ui._live_action_count, 0)
                        self.assertIsNone(ui._k_deferred_permit)
                    else:
                        job.deliver_ack()
                        self.assertEqual(ui._k_m_revision, 1)

    def test_fixed_origin_rejects_wrong_id_changed_layout_and_nonempty_history(self):
        ui = self.create(POLICY_V1, seam=True)
        origin = ui._live_fixed_origin
        for bad in (FixedOrigin('f'*32, origin.layout),
                    FixedOrigin(origin.game_id, FixedLayout(5, 1, 1, {(4, 0)}))):
            ui._live_fixed_origin = bad
            self.assertFalse(ui._fixed_board_start())
        ui._live_fixed_origin = origin
        self.assertTrue(ui._fixed_board_start())
        ui.live_input_records.append({'forged': True})
        self.assertFalse(ui._fixed_board_start())
        ui.live_input_records.clear()
        ui._v1_cursor = (1, 0)
        self.assertFalse(ui._fixed_board_start())

    def test_retry_disabled_for_progress_replay_closing_uncertainty_and_cleanup(self):
        ui = self.create()
        original = ui._live_game_id
        ui.on_same_board_retry()
        self.assertEqual(ui._live_game_id, original)
        ui.on_left_click(2, 0)
        for field, bad in (('_replay_mode', True), ('_live_closing', True),
                           ('_live_input_uncertain', True), ('_k_retiring', object())):
            with self.subTest(field=field):
                old = getattr(ui, field)
                setattr(ui, field, bad)
                self.assertIsNone(ui._same_board_retry_layout())
                setattr(ui, field, old)
        for state in ('computing', 'cancelling', 'blocked', 'closed'):
            ui._v1_job.state = state
            self.assertIsNone(ui._same_board_retry_layout())
        ui._v1_job.state = 'idle'
        self.assertIsNotNone(ui._same_board_retry_layout())

    def test_custom_remains_manual_simple_and_presets_supported(self):
        ui = self.create()
        for policy in (POLICY_V1, k.POLICY_K, k.POLICY_K_LC0, k.POLICY_K_LC1):
            ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
            self.assertFalse(ui.simple_auto_checkbox.isEnabled())
        for dims in ((9, 9, 10), (16, 16, 40), (30, 16, 99)):
            mines = tuple((x % dims[0], x // dims[0]) for x in range(dims[2]))
            other = self.create(k.POLICY_K, mines=mines, dims=dims)
            self.assertTrue(other._fixed_board_start())
            self.assertTrue(other.simple_auto_checkbox.isEnabled())

    def test_policy_switch_and_reset_replay_clear_fixed_provenance(self):
        ui = self.create()
        origin = ui._live_fixed_origin
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(POLICY_V1))
        self.assertIs(ui._live_fixed_origin, origin)
        self.assertTrue(ui._fixed_board_start())
        ui._view_completed_live_game(ui._same_board_completed_games[0])
        self.assertTrue(ui._replay_mode)
        self.assertTrue(ui.same_board_retry_button.isEnabled())
        ui._exit_replay_mode()
        self.assertIsNone(ui._live_fixed_origin)
        self.assertFalse(ui._fixed_board_start())
        self.assertFalse(ui.engine.get_board_snapshot().mines_placed)
        self.assertEqual(ui._same_board_completed_games, [])
        self.assertIsNone(ui._same_board_history_layout)
        self.assertEqual(ui.same_board_history_menu.actions(), [])

    def test_retry_controls_use_separate_layout_row(self):
        ui = self.create()
        ui.show()
        self.app.processEvents()
        retry = ui.same_board_retry_button.geometry()
        policy = ui.live_policy_new_game_button.geometry()
        pacing = ui.pacing_bar.geometry()
        self.assertFalse(retry.intersects(policy))
        self.assertFalse(retry.intersects(pacing))
        self.assertIn('첫 클릭도 지뢰', ui.same_board_retry_button.toolTip())


if __name__ == '__main__':
    unittest.main()
