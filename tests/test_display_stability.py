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
from simple_probability import CellProbability
from tests import test_live_k_ui as base
from tests.test_live_k_lc0_ui import FamilyFakeJob
from tests.test_replay_analysis_ui import ReplayAnalysisUITests
from tests.live_k_lc1_fixtures import install_singleton
import ui_manager
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

    def test_carried_proofs_join_a_new_capture_only_in_the_same_context_without_disagreement(self):
        c = DisplayContext('g', 'p', 'r', 1, 3, 2, 'h', 'o')
        obs = [[-2, -2, -2, -2, 1, -3]]
        # (4, 0) was opened and (5, 0) flagged since the carried frame was made.
        carried = CertaintyFrame(c, frozenset({(0, 0), (4, 0)}), frozenset({(1, 0), (5, 0)}))
        fresh = {(2, 0): CellOverlay(OverlayKind.SAFE, True)}
        plain = CertaintyFrame.capture(c, fresh, obs)
        self.assertEqual((plain.safe, plain.mines), ({(2, 0)}, frozenset()))
        kept = CertaintyFrame.capture(c, fresh, obs, carried=carried)
        self.assertEqual((kept.safe, kept.mines), ({(0, 0), (2, 0)}, {(1, 0)}))
        agreeing = {**fresh, (0, 0): CellOverlay(OverlayKind.SAFE), (1, 0): CellOverlay(OverlayKind.MINE)}
        self.assertEqual(CertaintyFrame.capture(c, agreeing, obs, carried=carried), kept)
        chance = CellProbability((0, 0), 1, 2)
        for name, stated in (('safe became mine', {(0, 0): CellOverlay(OverlayKind.MINE)}),
                             ('safe became uncertain', {(0, 0): CellOverlay(OverlayKind.UNCERTAIN, False, chance)}),
                             ('safe became guess', {(0, 0): CellOverlay(OverlayKind.GUESS_CANDIDATE, False, chance)}),
                             ('mine became safe', {(1, 0): CellOverlay(OverlayKind.SAFE)})):
            with self.subTest(disagreement=name):
                # One contradiction discredits the whole carried epoch, not just that cell.
                overlays = {**fresh, **stated}
                self.assertEqual(CertaintyFrame.capture(c, overlays, obs, carried=carried),
                                 CertaintyFrame.capture(c, overlays, obs))
        for field, value in [('game', 'g2'), ('policy', 'p2'), ('run', 'r2'), ('generation', 2),
                             ('owner', 4), ('revision', 3), ('history_digest', 'h2'),
                             ('observation_digest', 'o2')]:
            with self.subTest(context=field):
                other = replace(c, **{field: value})
                self.assertEqual(CertaintyFrame.capture(other, fresh, obs, carried=carried),
                                 CertaintyFrame.capture(other, fresh, obs))
        for name, bad in (('absent', None), ('foreign', object()), ('dict', {'safe': {(0, 0)}}),
                          ('mutable', CertaintyFrame(c, {(0, 0)}, frozenset())),
                          ('overlapping', CertaintyFrame(c, frozenset({(0, 0)}), frozenset({(0, 0)}))),
                          ('no context', CertaintyFrame(None, frozenset({(0, 0)}), frozenset()))):
            with self.subTest(carried=name):
                context = None if name == 'no context' else c
                self.assertEqual(CertaintyFrame.capture(context, fresh, obs, carried=bad),
                                 CertaintyFrame.capture(context, fresh, obs))

    def test_carried_proofs_survive_several_recorded_inputs_until_opened_or_flagged(self):
        c = DisplayContext('g', 'p', 'r', 1, 3, 2, 'h', 'o')
        frame = CertaintyFrame.capture(c, {(0, 0): CellOverlay(OverlayKind.SAFE),
                                           (1, 0): CellOverlay(OverlayKind.SAFE),
                                           (2, 0): CellOverlay(OverlayKind.MINE)}, [[-2, -2, -2, -2]])
        steps = (([[-2, -2, -2, 1]], {(0, 0), (1, 0)}, {(2, 0)}),   # local result knows none of them
                 ([[-2, -2, -3, 1]], {(0, 0), (1, 0)}, set()),      # the mine was physically flagged
                 ([[1, -2, -3, 1]], {(1, 0)}, set()))               # one safe cell was opened
        for revision, (obs, safe, mines) in enumerate(steps, start=3):
            current = replace(c, revision=revision, history_digest=f'h{revision}',
                              observation_digest=f'o{revision}')
            carried = frame.advance(frame.context, current, obs)
            frame = CertaintyFrame.capture(current, {(3, 0): CellOverlay(None, True)}, obs, carried=carried)
            self.assertEqual((frame.safe, frame.mines), (safe, mines))

    def test_kept_colors_fill_only_cells_the_current_result_leaves_uncolored(self):
        c = DisplayContext('g', 'p', 'r', 1, 3, 2, 'h', 'o')
        frame = CertaintyFrame(c, frozenset({(0, 0), (2, 0), (4, 0)}), frozenset({(1, 0)}))
        chance = CellProbability((3, 0), 1, 2)
        current = {(2, 0): CellOverlay(OverlayKind.SAFE, True),
                   (3, 0): CellOverlay(OverlayKind.GUESS_CANDIDATE, False, chance),
                   (4, 0): CellOverlay(None, True), (5, 0): CellOverlay(None, True)}
        merged = frame.overlays_with(current)
        self.assertEqual(merged, {(0, 0): CellOverlay(OverlayKind.SAFE), (1, 0): CellOverlay(OverlayKind.MINE),
                                  (2, 0): current[(2, 0)], (3, 0): current[(3, 0)],
                                  (4, 0): CellOverlay(OverlayKind.SAFE, True), (5, 0): current[(5, 0)]})
        self.assertEqual({k for k, o in merged.items() if o.recommended}, {(2, 0), (4, 0), (5, 0)})
        self.assertEqual({k for k, o in merged.items() if o.probability}, {(3, 0)})
        self.assertEqual(set(current), {(2, 0), (3, 0), (4, 0), (5, 0)})  # the result itself is untouched
        self.assertEqual(CertaintyFrame(c, {(0, 0)}, frozenset()).overlays_with(current), current)


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

    def later_results(self, later):
        """Display seam: reshape what later V1/K/Simple presentations show, never the proposals.

        The first presentation after ``self.presented`` is emptied stays as produced.
        """
        self.presented, self.later = [], later
        if getattr(self, 'presentation_seam', False):
            return
        self.presentation_seam = True

        def wrap(original):
            def present(*args):
                result = original(*args)
                change = self.later if self.presented else None
                self.presented.append(result)
                return result if change is None else replace(result, overlays=change(dict(result.overlays)))
            return present

        for name in ('present_v1_proposal', 'present_k_proposal', 'present_decision'):
            patcher = patch.object(ui_manager, name, wrap(getattr(ui_manager, name)))
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def local_only(overlays):
        """A later local result: only the recommended cell keeps its SAFE color."""
        return {c: o for c, o in overlays.items() if o.kind != OverlayKind.SAFE or o.recommended}

    def advance_to_next_result(self, policy=POLICY_K_LC1):
        self.apply(policy)
        if policy != POLICY_SIMPLE:
            self.job.deliver_ack()
            self.job.compute()
        return self.ui._analysis_result

    def raw(self, result=None):
        result = self.ui._analysis_result if result is None else result
        return {c: o.kind for c, o in result.overlays.items() if o.kind in (OverlayKind.SAFE, OverlayKind.MINE)}

    def test_proven_colors_stay_on_real_cells_through_later_local_results(self):
        self.later_results(self.local_only)
        for policy, expected_steps in ((POLICY_V1, 1), (POLICY_K_LC1, 2), (POLICY_K, 1), (POLICY_K_LC0, 1)):
            with self.subTest(policy=policy):
                self.presented.clear()
                requests, applied = len(self.job.requests), len(self.job.applied)
                self.prepare(policy)
                shown, omitted_steps = self.certainty(), 0
                self.assertEqual(shown, self.raw())
                for _ in range(2):
                    result = self.advance_to_next_result(policy)
                    pending = self.ui._v1_pending
                    hidden = hidden_cells(self.engine.get_observation())
                    remaining = {c: kind for c, kind in shown.items() if c in hidden}
                    raw = self.raw(result)
                    omitted = set(remaining) - set(raw)
                    omitted_steps += bool(omitted)
                    # Actual cells: every still-hidden proof stays, the new result is added.
                    self.assertEqual(self.certainty(), {**remaining, **raw})
                    self.assertTrue(set(self.certainty()) <= hidden)
                    for cell in omitted:
                        button = self.ui._buttons[cell]
                        self.assertEqual(button.analysis_overlay, CellOverlay(remaining[cell]))
                        self.assertEqual(button.probability_text, '')
                        self.assertNotIn('추천', button.toolTip())
                    # Recommendation, probabilities and status come from the current result only.
                    self.assertEqual({c for c, b in self.ui._buttons.items()
                                      if b.analysis_overlay and b.analysis_overlay.recommended},
                                     {(pending.x, pending.y)})
                    self.assertEqual({c: b.analysis_overlay.probability for c, b in self.ui._buttons.items()
                                      if b.analysis_overlay and b.analysis_overlay.probability},
                                     {c: o.probability for c, o in result.overlays.items() if o.probability})
                    self.assertEqual(self.ui.analysis_status_label.text(), result.status_text)
                    # The proposal and the presented result never receive the kept cells.
                    self.assertFalse(omitted & set(result.overlays))
                    self.assertIs(self.ui._v1_pending, self.job.pending)
                    if policy != POLICY_V1:
                        self.assertEqual(pending.safe_cells,
                                         tuple(sorted(self.job.owner.decision.selection_safe_cells,
                                                      key=lambda c: (c[1], c[0]))))
                    shown = self.certainty()
                self.assertEqual(omitted_steps, expected_steps)
                # One request per shown result and one consumed token per input: no extra analysis.
                self.assertEqual(len(self.job.requests) - requests, 3)
                self.assertEqual(len(self.job.applied) - applied, 2)

    def test_disagreeing_result_discards_every_carried_color(self):
        chance = CellProbability((1, 10), 1, 2)
        for name, stated in (('mine', CellOverlay(OverlayKind.MINE)),
                             ('uncertain', CellOverlay(OverlayKind.UNCERTAIN, False, chance))):
            with self.subTest(stated=name):
                self.later_results(lambda overlays: {**self.local_only(overlays), (1, 10): stated})
                self.prepare()
                self.assertEqual(self.certainty().get((1, 10)), OverlayKind.SAFE)
                result = self.advance_to_next_result()
                self.assertEqual(self.certainty(), self.raw(result))
                self.assertNotIn((2, 10), self.certainty())
                self.assertEqual(self.ui._buttons[(1, 10)].analysis_overlay, stated)
                frame = self.ui._certainty_frame
                self.assertEqual((frame.safe, frame.mines),
                                 ({c for c, kind in self.raw(result).items() if kind == OverlayKind.SAFE},
                                  {c for c, kind in self.raw(result).items() if kind == OverlayKind.MINE}))

    def test_carried_colors_need_the_exact_current_context_when_the_result_arrives(self):
        self.later_results(self.local_only)
        for field, value in (('game', 'other'), ('policy', POLICY_K_LC0), ('run', 'other'),
                             ('generation', 987), ('owner', 1), ('revision', 99),
                             ('history_digest', 'other'), ('observation_digest', 'other')):
            with self.subTest(field=field):
                self.presented.clear()
                self.prepare()
                self.apply()
                frame = self.ui._certainty_frame
                self.assertIn((2, 10), frame.safe)
                self.ui._certainty_frame = replace(frame, context=replace(frame.context, **{field: value}))
                self.job.deliver_ack()
                self.job.compute()
                self.assertEqual(self.certainty(), self.raw())
                self.assertNotIn((2, 10), self.certainty())

    def test_hard_invalidations_and_context_changes_drop_kept_colors_under_a_result(self):
        self.later_results(self.local_only)
        actions = {
            'manual press': lambda: QTest.mousePress(self.ui._buttons[(3, 3)], Qt.LeftButton),
            'manual flag': lambda: self.ui.on_right_click(2, 10),
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
                self.presented.clear()
                self.prepare()
                self.advance_to_next_result()
                self.assertEqual(self.certainty().get((2, 10)), OverlayKind.SAFE)
                self.assertNotIn((2, 10), self.ui._analysis_result.overlays)
                action()
                self.assertIsNone(self.ui._certainty_frame)
                if not self.ui._replay_mode:
                    self.assertEqual(self.certainty(), {})
                if name == 'manual press':
                    QTest.mouseRelease(self.ui._buttons[(3, 3)], Qt.LeftButton)
                if self.ui._replay_mode:
                    self.ui.analysis_checkbox.setChecked(False)
                    self.ui._exit_replay_mode()
        for field, value in (('_live_game_id', 'other'), ('_live_run_id', 'other'),
                             ('_live_board_generation', 987), ('_live_input_uncertain', True),
                             ('_v1_owned', False), ('_live_policy', POLICY_K_LC0)):
            with self.subTest(field=field):
                self.presented.clear()
                self.prepare()
                result = self.advance_to_next_result()
                setattr(self.ui, field, value)
                self.ui._render_live_analysis()
                self.assertIsNone(self.ui._certainty_frame)
                # The retained current result is still drawn; only the kept colors expire.
                self.assertEqual(self.certainty(), self.raw(result))
        self.presented.clear()
        self.prepare()
        self.advance_to_next_result()
        self.ui.live_input_records[0]['x'] = 5
        self.ui._render_live_analysis()
        self.assertIsNone(self.ui._certainty_frame)
        self.assertNotIn((2, 10), self.certainty())

    def test_pause_and_redisplay_keep_colors_without_another_request(self):
        self.later_results(self.local_only)
        self.prepare()
        self.advance_to_next_result()
        kept, pending = self.certainty(), self.ui._v1_pending
        self.assertEqual(kept.get((2, 10)), OverlayKind.SAFE)
        requests = len(self.job.requests)
        with patch('ui_manager.analyze_position', side_effect=AssertionError('extra analysis')):
            self.ui.simple_auto_checkbox.setChecked(False)
            self.assertEqual(self.certainty(), kept)
            self.ui.probability_checkbox.toggle()
            self.assertEqual(self.certainty(), kept)
            self.ui.simple_auto_checkbox.setChecked(True)
            self.assertEqual(self.certainty(), kept)
        self.assertIs(self.ui._v1_pending, pending)
        self.assertEqual(len(self.job.requests), requests)

    def test_absent_or_tampered_cache_at_result_time_changes_only_the_kept_colors(self):
        self.later_results(self.local_only)
        outcomes = {}
        for name in ('valid', 'absent', 'foreign', 'mutable fields'):
            with self.subTest(cache=name):
                self.presented.clear()
                self.prepare()
                self.apply()
                frame = self.ui._certainty_frame
                if name != 'valid':
                    self.ui._certainty_frame = {'absent': None, 'foreign': object(),
                                                'mutable fields': CertaintyFrame(frame.context, set(frame.safe),
                                                                                 list(frame.mines))}[name]
                requests = len(self.job.requests)
                self.job.deliver_ack()
                self.job.compute()
                self.assertEqual(len(self.job.requests), requests + 1)
                pending = self.ui._v1_pending
                self.assertIs(pending, self.job.pending)
                if name != 'valid':
                    self.assertEqual(self.certainty(), self.raw())
                applied = len(self.job.applied)
                self.apply()
                self.assertEqual(len(self.job.applied), applied + 1)
                self.assertEqual(len(self.job.requests), requests + 1)
                record = self.ui.live_action_records[-1]
                self.assertEqual((record['token'], record['action'], record['x'], record['y']),
                                 (pending.token, pending.action, pending.x, pending.y))
                outcomes[name] = [(r['action'], r['x'], r['y']) for r in self.ui.live_action_records]
        self.assertEqual(len(set(map(tuple, outcomes.values()))), 1)

    def test_simple_results_still_replace_the_previous_colors(self):
        self.later_results(self.local_only)
        self.prepare(POLICY_SIMPLE)
        shown = self.certainty()
        result = self.advance_to_next_result(POLICY_SIMPLE)
        hidden = hidden_cells(self.engine.get_observation())
        self.assertTrue({c for c in shown if c in hidden} - set(self.raw(result)))
        self.assertEqual(self.certainty(), self.raw(result))
