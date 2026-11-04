"""Display-only state and offscreen Main boundaries; no real child processes."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from core_engine import CellState, GameStatus
from live_analysis import CellOverlay, OverlayKind
from live_display_state import CertaintyFrame, DisplayContext, hidden_cells
from live_policy import POLICY_SIMPLE, POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1
from replay_analysis import analyze_replay_step, ReplayComparisonKind
from replay_display import recorded_input, reference_overlays
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from tests import test_live_k_ui as base
from tests.test_live_k_lc0_ui import FamilyFakeJob
from tests.test_replay_analysis_ui import ReplayAnalysisUITests
from tests.live_k_lc1_fixtures import install_singleton
from ui_manager import CellButton


class CertaintyFrameTests(unittest.TestCase):
    def test_only_hidden_certainties_survive_single_recorded_transition(self):
        c = DisplayContext('g', 'p', 'r', 1, 3, 2, 'h', 'o')
        obs = [[-2, -2, -2, -2, 1, -3]]
        overlays = {i: CellOverlay(kind, True) for i, kind in (
            ((0, 0), OverlayKind.SAFE), ((1, 0), OverlayKind.MINE),
            ((2, 0), OverlayKind.GUESS_CANDIDATE), ((3, 0), OverlayKind.UNCERTAIN),
            ((4, 0), OverlayKind.SAFE), ((5, 0), OverlayKind.MINE))}
        frame = CertaintyFrame.capture(c, overlays, obs)
        self.assertEqual(frame.safe, {(0, 0)})
        self.assertEqual(frame.mines, {(1, 0)})
        current = replace(c, revision=3, history_digest='h2', observation_digest='o2')
        kept = frame.advance(c, current, obs)
        self.assertEqual(set(kept.overlays()), {(0, 0), (1, 0)})
        self.assertTrue(all(not o.recommended and o.probability is None for o in kept.overlays().values()))
        self.assertEqual(frame.advance(c, current, [[1, -3, -2, -2, 1, -3]]).overlays(), {})
        fresh = CertaintyFrame.capture(current, {(2, 0): CellOverlay(OverlayKind.SAFE)}, obs)
        self.assertEqual(fresh.safe, {(2, 0)})

    def test_different_epochs_history_and_nonconsecutive_revisions_are_rejected(self):
        c = DisplayContext('g', 'p', 'r', 1, 3, 2, 'h', 'o')
        frame = CertaintyFrame(c, frozenset({(0, 0)}), frozenset())
        for field, value in [('game', 'g2'), ('policy', 'p2'), ('run', 'r2'),
                             ('generation', 2), ('owner', 4), ('revision', 8),
                             ('history_digest', 'h2'), ('observation_digest', 'o2')]:
            with self.subTest(field=field):
                self.assertIsNone(frame.advance(replace(c, **{field: value}),
                                                replace(c, revision=3), [[-2]]))
        for field, value in [('game', 'g2'), ('policy', 'p2'), ('run', 'r2'),
                             ('generation', 2), ('owner', 4), ('revision', 8)]:
            with self.subTest(current=field):
                self.assertIsNone(frame.advance(c, replace(c, revision=3, **({field: value} if field != 'revision' else {}))
                                               if field != 'revision' else replace(c, revision=value), [[-2]]))


class ReplayDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    setUp = ReplayAnalysisUITests.setUp
    close_ui = ReplayAnalysisUITests.close_ui
    enter = ReplayAnalysisUITests.enter

    def assert_actual(self, text, target):
        self.assertEqual(self.ui.analysis_status_label.text().splitlines()[0], text)
        self.assertEqual({c for c, b in self.ui._buttons.items() if b.recorded_target},
                         {target} if target is not None else set())
        for b in self.ui._buttons.values():
            self.assertFalse(b.analysis_overlay and b.analysis_overlay.recommended)
        visible = self.ui.analysis_status_label.text() + self.ui.analysis_status_label.toolTip()
        for forbidden in ('추천과 일치', '추천과 다름', '동등한', '비교 대상 아님'):
            self.assertNotIn(forbidden, visible)

    def test_actual_input_survives_off_failure_chord_unflag_and_terminal(self):
        self.enter(2)
        self.assert_actual('녹화된 다음 입력: UNFLAG (1, 1)', (1, 1))
        with patch('ui_manager.analyze_replay_step', side_effect=AssertionError('OFF analysis')):
            self.ui.on_analyze_current()
            self.ui._refresh_replay_view_after_move()
            self.ui.probability_checkbox.setChecked(False)
        with patch('ui_manager.analyze_replay_step', side_effect=RuntimeError('reference failed')):
            self.ui.analysis_checkbox.setChecked(True)
        self.assert_actual('녹화된 다음 입력: UNFLAG (1, 1)', (1, 1))
        self.assertIn('분석 불가', self.ui.analysis_status_label.text())
        self.ui.analysis_checkbox.setChecked(False)
        self.player = ReplayPlayer(ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), (
            ReplayEvent(1, 0, 0, 'OPEN'), ReplayEvent(2, 0, 0, 'CHORD'))))
        self.enter(1)
        self.assert_actual('녹화된 다음 입력: CHORD (0, 0)', (0, 0))
        self.assertEqual(self.player.get_observation()[0][0], 1)
        self.player = ReplayPlayer(ReplayData(ReplayBoard(2, 1, 1, {(1, 0)}), (
            ReplayEvent(1, 0, 0, 'OPEN'), ReplayEvent(2, 1, 0, 'FLAG'))))
        self.enter(1, continuous=True)
        self.assertEqual(self.player.engine.status, GameStatus.WON)
        self.assert_actual('녹화된 다음 입력: FLAG (1, 0)', (1, 0))
        self.player.go_to(2)
        self.ui._refresh_replay_view_after_move()
        self.assert_actual('녹화된 다음 입력: 없음', None)

    def test_actual_changes_do_not_influence_simple_or_internal_comparison(self):
        observation = [[1, -2, -2], [-2, -2, -2], [-2, -2, -2]]
        results = [analyze_replay_step(observation, 1, current_index=1,
                    events=(ReplayEvent(1, 0, 0, 'OPEN'), event), status=GameStatus.PLAYING)
                   for event in (ReplayEvent(2, 2, 0, 'OPEN'), ReplayEvent(2, 0, 0, 'CHORD'))]
        self.assertEqual(results[0].presentation, results[1].presentation)
        self.assertEqual(results[1].comparison_kind, ReplayComparisonKind.UNSUPPORTED_ACTUAL)
        self.assertIn('비교 대상 아님', results[1].comparison_text)
        self.assertEqual(reference_overlays(results[0].presentation), reference_overlays(results[1].presentation))
        self.assertEqual(recorded_input((), 0, observation), ('녹화된 다음 입력: 없음', None))
        # Invalid records can be formatted safely even though ReplayData rejects them.
        from types import SimpleNamespace
        for x, y in ((-1, 0), (3, 0), (0, -1), (0, 3)):
            self.assertIsNone(recorded_input((SimpleNamespace(action='OPEN', x=x, y=y),), 0, observation)[1])

    def test_same_index_toggles_are_read_only_and_exit_removes_replay_marks(self):
        self.enter(3, continuous=True)
        before = (self.player.current_index, tuple(self.player.replay_data.events), self.ui._replay_analysis_result)
        with patch('ui_manager.analyze_replay_step', side_effect=AssertionError('extra analysis')):
            for _ in range(3):
                self.ui._refresh_replay_view_after_move()
                self.ui.probability_checkbox.toggle()
                self.ui.reduction_checkbox.toggle()
        self.assertEqual(before, (self.player.current_index, tuple(self.player.replay_data.events), self.ui._replay_analysis_result))
        self.assert_actual('녹화된 다음 입력: OPEN (2, 0)', (2, 0))
        self.ui._exit_replay_mode()
        self.assertNotIn('녹화된', self.ui.analysis_status_label.text())
        self.assertFalse(any(b.recorded_target for b in self.ui._buttons.values()))


class LiveDisplayTests(unittest.TestCase):
    close_ui = base.LiveKUITests.close_ui
    tick = base.LiveKUITests.tick

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(base, 'KUIFakeJob', FamilyFakeJob):
            base.LiveKUITests.setUp(self)

    def prepare(self, policy=POLICY_K_LC1, interval=2000):
        if self.job.active_run_id is not None:
            self.ui._invalidate_v1_run('test fixture reset')
            self.job.complete_cancel()
        self.ui.analysis_checkbox.setChecked(False)
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))
        self.ui.on_reset()
        install_singleton(self.engine)  # Declared synthetic public prefix; actual later inputs.
        self.ui._reset_replay_recorder()
        self.ui._build_grid()
        self.ui._v1_supported = lambda: True  # Small board test gate only.
        self.ui.show()
        self.app.processEvents()
        self.ui.on_left_click(0, 0)  # Actual wasted CHORD on an opened anchor.
        self.ui.simple_auto_interval_spin.setValue(interval)
        self.ui.simple_auto_checkbox.setChecked(True)
        if policy != POLICY_SIMPLE:
            self.job.compute()
        return self.ui._analysis_result

    def apply(self, policy=POLICY_K_LC1):
        self.tick()
        if policy not in (POLICY_SIMPLE, POLICY_V1):
            self.job.deliver_admission()

    def certainty(self):
        return {c: b.analysis_overlay.kind for c, b in self.ui._buttons.items()
                if b.analysis_overlay and b.analysis_overlay.kind in (OverlayKind.SAFE, OverlayKind.MINE)}

    def test_five_policies_keep_hidden_colors_without_blank_then_replace(self):
        for policy in (POLICY_SIMPLE, POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            for interval in (0, 10, 2000):
                with self.subTest(policy=policy, interval=interval):
                    result = self.prepare(policy, interval)
                    old = self.certainty()
                    self.assertTrue(old)
                    frames = []
                    original = self.ui._render_live_analysis
                    def render():
                        original()
                        frames.append((self.ui._analysis_result is None, self.certainty()))
                    with patch.object(self.ui, '_render_live_analysis', side_effect=render):
                        self.apply(policy)
                    remaining = {c: kind for c, kind in old.items() if c in hidden_cells(self.engine.get_observation())}
                    waiting = [colors for empty, colors in frames if empty]
                    self.assertTrue(waiting)
                    self.assertTrue(remaining)
                    self.assertTrue(all(colors == remaining for colors in waiting))
                    self.assertEqual(self.ui.live_auto_totals['auto_inputs'], 1)
                    self.assertEqual(len(self.ui._replay_recorder.events), 2)
                    self.assertEqual(self.ui._replay_recorder.source_type, 'algorithm')
                    if policy != POLICY_SIMPLE:
                        self.assertIsNone(self.ui._analysis_result)
                        self.assertTrue(all(not b.analysis_overlay or
                            (not b.analysis_overlay.recommended and b.analysis_overlay.probability is None)
                            for b in self.ui._buttons.values()))
                        self.ui.probability_checkbox.toggle()
                        self.assertEqual(self.certainty(), remaining)
                        self.ui.grab()  # Exercise actual offscreen paint, without processing worker callbacks.
                        self.job.deliver_ack()
                        self.assertEqual(self.certainty(), remaining)
                        self.job.compute()
                        self.assertIsNot(self.ui._analysis_result, result)
                    expected = {c: o.kind for c, o in self.ui._analysis_result.overlays.items()
                                if o.kind in (OverlayKind.SAFE, OverlayKind.MINE)}
                    self.assertEqual(self.certainty(), expected)

    def test_all_hard_invalidations_discard_cached_colors(self):
        actions = {
            'manual press': lambda: QTest.mousePress(self.ui._buttons[(3, 3)], Qt.LeftButton),
            'policy': lambda: self.ui.live_policy_combo.setCurrentIndex(0),
            'reset': self.ui.on_reset,
            'analysis off': lambda: self.ui.analysis_checkbox.setChecked(False),
            'failure': lambda: self.ui._fail_v1('display test failure'),
            'owner disposal': lambda: self.ui._invalidate_v1_run('display test disposal'),
            'Replay': lambda: self.ui._enter_replay_mode(ReplayPlayer(ReplayData(
                ReplayBoard(2, 1, 1, {(1, 0)}), (ReplayEvent(1, 0, 0, 'OPEN'),)))),
        }
        for name, action in actions.items():
            with self.subTest(boundary=name):
                self.prepare()
                self.apply()
                self.assertTrue(self.certainty())
                action()
                self.assertIsNone(self.ui._certainty_frame)
                if not self.ui._replay_mode:
                    self.assertEqual(self.certainty(), {})
                if name == 'manual press':
                    QTest.mouseRelease(self.ui._buttons[(3, 3)], Qt.LeftButton)
                if self.ui._replay_mode:
                    self.ui.analysis_checkbox.setChecked(False)
                    self.ui._exit_replay_mode()

    def test_same_looking_context_change_expires_display_without_new_analysis(self):
        for field, value in (('_live_game_id', 'other'), ('_live_run_id', 'other'),
                             ('_live_board_generation', 987), ('_live_input_uncertain', True),
                             ('_v1_owned', False), ('_live_policy', POLICY_K_LC0)):
            with self.subTest(field=field):
                self.prepare()
                self.apply()
                setattr(self.ui, field, value)
                self.ui._render_live_analysis()
                self.assertIsNone(self.ui._certainty_frame)
                self.assertEqual(self.certainty(), {})

    def test_history_mutation_terminal_difficulty_and_close_drop_waiting_frame(self):
        self.prepare()
        self.apply()
        self.ui.live_input_records[0]['x'] = 5
        self.ui._render_live_analysis()
        self.assertEqual(self.certainty(), {})
        self.prepare()
        self.apply()
        self.ui.difficulty_combo.setCurrentIndex(1)
        self.assertIsNone(self.ui._certainty_frame)
        self.prepare()
        self.apply()
        self.engine.status = GameStatus.LOST
        self.ui.render_board()
        self.assertIsNone(self.ui._certainty_frame)
        self.assertEqual(self.certainty(), {})
        self.prepare()
        self.apply()
        self.ui.close()
        self.assertIsNone(self.ui._certainty_frame)

    def test_absent_or_tampered_cache_never_changes_input_ack_or_selection_count(self):
        for cache in (None, object(), 'valid'):
            with self.subTest(cache=str(cache)):
                self.prepare()
                if cache != 'valid':
                    self.ui._certainty_frame = cache
                requests = len(self.job.requests)
                applied = len(self.job.applied)
                self.apply()
                self.assertEqual(len(self.job.applied), applied + 1)
                self.assertEqual(len(self.job.requests), requests)
                self.assertEqual(self.ui.live_auto_totals['auto_inputs'], 1)
                self.assertEqual(self.ui.live_action_records[-1]['status'], 'PLAYING')
                self.job.deliver_ack()
                self.assertEqual(len(self.job.requests), requests + 1)

    def test_pause_retains_frame_and_duplicate_overlay_skips_update(self):
        self.prepare()
        self.apply()
        old = self.certainty()
        self.ui.simple_auto_checkbox.setChecked(False)
        self.assertEqual(self.certainty(), old)
        self.job.deliver_ack()
        self.assertEqual(self.certainty(), old)
        button = next(b for b in self.ui._buttons.values() if b.analysis_overlay)
        with patch.object(button, 'update') as update:
            button.set_analysis_overlay(button.analysis_overlay)
            update.assert_not_called()
        self.assertIsNone(self.ui._analysis_result)
