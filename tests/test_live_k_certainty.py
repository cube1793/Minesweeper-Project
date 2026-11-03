"""Current K certainty projection and Main display contracts; no real children."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from core_engine import Action, GameStatus
from experiments.program_k_capability import KLocalSession
from live_analysis import OverlayKind, present_k_proposal
import live_k_policy as k
from live_policy import LivePolicyError, POLICY_SIMPLE
import live_policy_transport as transport
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from stage3_physical import load_timing_table
from ui_manager import ChordMode
import tests.test_live_k_policy as fixtures
import tests.test_live_k_job as job_fixtures
import tests.test_live_auto_cursor as ui_fixtures


def certain_owner():
    owner, state = fixtures.after_initial()
    return owner, owner.propose(state)


class KCertaintyProjectionTests(unittest.TestCase):
    def test_initial_has_border_only_and_no_native_calls(self):
        state = fixtures.initial()
        owner = k.KOwner(state, load_timing_table())
        with patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('analyze')), \
                patch.object(owner, '_select', side_effect=AssertionError('select')):
            p = owner.propose(state)
            self.assertEqual(p.safe_cells, ())
            self.assertEqual(p.preinput_m, ())
            result = present_k_proposal(p)
            self.assertEqual(set(result.overlays), {(0, 0)})
            self.assertIsNone(result.overlays[(0, 0)].kind)
            self.assertIsNone(result.overlays[(0, 0)].probability)
            self.assertTrue(result.overlays[(0, 0)].recommended)

    def test_local_safe_is_original_set_not_all_remaining_hidden(self):
        observation = ((1, -2, 1, -2, -2), (1, 1, 1, -2, -2))
        owner, state = fixtures.after_initial(observation)
        original = KLocalSession.analyze_decision
        with patch.object(KLocalSession, 'analyze_decision', autospec=True, side_effect=original) as analyze:
            owner._select = Mock(wraps=owner._select)
            p = owner.propose(state)
            graph, decision = owner.selection, owner.decision
            self.assertEqual(p.continuation, 'LOCAL_SAFE')
            self.assertEqual(p.safe_cells, ((3, 0), (3, 1)))
            self.assertEqual(set(p.safe_cells), decision.selection_safe_cells)
            self.assertEqual(set(p.preinput_m), decision.after.M)
            self.assertIs(graph.evidence, decision)
            for _ in range(4):
                result = present_k_proposal(p)
                fixtures.permit(owner, p)
                k.from_dict(k.to_dict(p), k.KProposal)
            self.assertNotIn((4, 0), result.overlays)
            self.assertNotIn((4, 1), result.overlays)
            self.assertTrue(all(result.overlays[c].kind == OverlayKind.SAFE for c in p.safe_cells))
            self.assertEqual(result.overlays[(p.x, p.y)].kind, OverlayKind.MINE)
            self.assertTrue(result.overlays[(p.x, p.y)].recommended)
            self.assertTrue(all(o.probability is None for o in result.overlays.values()))
            self.assertIsNone(decision.phase_e)
            self.assertEqual(analyze.call_count, 1)
            self.assertEqual(owner._select.call_count, 1)
            self.assertEqual(owner._select.call_args.kwargs, {})
            self.assertIs(owner.selection, graph)

    def test_exact_safe_uses_existing_phase_e_and_selected_open(self):
        owner, state = fixtures.after_initial(((1, -2, -2, -2, -2),), mines=1)
        owner._select = Mock(wraps=owner._select)
        p = owner.propose(state)
        self.assertEqual(p.continuation, 'EXACT_SAFE')
        self.assertEqual(p.safe_cells, ((2, 0), (3, 0), (4, 0)))
        self.assertEqual(set(p.safe_cells), owner.decision.phase_e.G0)
        self.assertEqual(set(p.safe_cells), owner.decision.selection_safe_cells)
        self.assertEqual(p.move, owner.selection.move)
        with patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('extra analysis')):
            for _ in range(3):
                result = present_k_proposal(p)
                fixtures.permit(owner, p)
        self.assertEqual(owner._select.call_count, 1)
        self.assertIsNone(p.probabilities)
        self.assertEqual(result.overlays[(p.x, p.y)].kind, OverlayKind.SAFE)
        self.assertTrue(result.overlays[(p.x, p.y)].recommended)

    def test_guess_has_no_safes_and_disjoint_mine_and_exact_probability_cells(self):
        owner, state = fixtures.after_initial(((1, -2, -2, -2, -2),), mines=2)
        p = owner.propose(state)
        result = present_k_proposal(p)
        self.assertEqual(p.safe_cells, ())
        self.assertEqual(result.overlays[(1, 0)].kind, OverlayKind.MINE)
        self.assertIsNone(result.overlays[(1, 0)].probability)
        self.assertEqual({c for c, o in result.overlays.items() if o.probability}, {(2, 0), (3, 0), (4, 0)})
        self.assertFalse(any(o.kind == OverlayKind.SAFE for o in result.overlays.values()))
        self.assertIn('지뢰 확률 33.3%', result.status_text)
        self.assertEqual((p.x, p.y), owner.decision.guess_target)

    def test_physical_flag_then_new_chord_has_no_flag_or_number_fill(self):
        owner, p = certain_owner()
        self.assertEqual(p.action, 'FLAG')
        selected = present_k_proposal(p).overlays[(p.x, p.y)]
        self.assertEqual(selected.kind, OverlayKind.MINE)
        self.assertTrue(selected.recommended)
        next_state = owner.acknowledge(k.make_ack(fixtures.permit(owner, p), 'PLAYING',
                                                 ((1, -3, 1, -2), (1, 1, 1, -2))))
        new = owner.propose(next_state)
        self.assertEqual(new.action, 'CHORD')
        fixtures.permit(owner, new)
        result = present_k_proposal(new)
        self.assertNotIn((1, 0), result.overlays)  # Actual FLAG remains an actual FLAG.
        self.assertEqual(set(new.safe_cells), owner.decision.selection_safe_cells)
        self.assertIsNone(result.overlays[(new.x, new.y)].kind)
        self.assertTrue(result.overlays[(new.x, new.y)].recommended)
        self.assertTrue(all(new.snapshot.observation[y][x] == -2
                            for (x, y), o in result.overlays.items() if o.kind is not None))

    def test_immutable_detached_projection_and_nested_roundtrips(self):
        owner, p = certain_owner()
        with self.assertRaises(FrozenInstanceError):
            p.safe_cells = ()
        raw = k.to_dict(p)
        raw['safe_cells'][0][0] = 0
        self.assertEqual(p.safe_cells[0], (3, 0))
        permit = fixtures.permit(owner, p)
        terminal = k.make_ack(permit, 'WON')
        for value in (p, permit, terminal):
            with self.subTest(type=type(value).__name__):
                self.assertEqual(k.from_dict(json.loads(json.dumps(k.to_dict(value))), type(value)), value)
        self.assertIsNone(terminal.observation)

    def test_strict_safe_wire_keys_types_order_length_and_public_observation(self):
        _, p = certain_owner()
        original = k.to_dict(p)
        invalid = [None, True, 1, 1.0, {}, 'safe', (), [[3, 0]] * 481, [],
                   [[3, 0], [3, 0]], [[3, 1], [3, 0]], [[3]], [[3, 0, 0]],
                   [[True, 0]], [[3.0, 0]], [[3, False]], [[3, 0.0]],
                   [[-1, 0]], [[4, 0]], [[3, 2]], [[1, 0]], [[0, 0]], [[[], 0]]]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(LivePolicyError):
                k.from_dict({**original, 'safe_cells': value}, k.KProposal)
        for field in ('safe_cells', 'probabilities'):
            with self.subTest(missing=field), self.assertRaises(LivePolicyError):
                k.from_dict({key: value for key, value in original.items() if key != field}, k.KProposal)
        with self.assertRaises(LivePolicyError):
            k.from_dict({**original, 'native_safe_proof': []}, k.KProposal)
        with self.assertRaises(LivePolicyError):
            replace(p, safe_cells=([3, 0],))
        flagged = replace(p.snapshot, observation=((1, -3, 1, -2), (1, 1, 1, -2)), base_m=((1, 0),))
        with self.assertRaises(LivePolicyError):
            replace(p, snapshot=flagged, safe_cells=((1, 0),))

    def test_safe_set_consistency_initial_guess_open_and_chord(self):
        state = fixtures.initial()
        initial = k.KOwner(state, load_timing_table()).propose(state)
        with self.assertRaises(LivePolicyError):
            replace(initial, safe_cells=((1, 0),))
        owner, state = fixtures.after_initial(((1, -2, -2, -2, -2),), mines=2)
        with self.assertRaises(LivePolicyError):
            replace(owner.propose(state), safe_cells=((2, 0),))
        owner, state = fixtures.after_initial(((1, -2, -2, -2, -2),), mines=1)
        opened = owner.propose(state)
        with self.assertRaises(LivePolicyError):
            replace(opened, safe_cells=tuple(c for c in opened.safe_cells if c != (opened.x, opened.y)))
        owner, p = certain_owner()
        state = owner.acknowledge(k.make_ack(fixtures.permit(owner, p), 'PLAYING',
                                            ((1, -3, 1, -2), (1, 1, 1, -2))))
        chord = owner.propose(state)
        with self.assertRaises(LivePolicyError):
            replace(chord, safe_cells=chord.safe_cells[:1])

    def test_structurally_valid_safe_subset_is_not_native_proof(self):
        owner, p = certain_owner()
        alternate = replace(p, safe_cells=p.safe_cells[:1])
        # A public DTO can validate shape, not recreate or replace native proof.
        self.assertEqual(k.from_dict(k.to_dict(alternate), k.KProposal), alternate)
        owner.pending = alternate
        with self.assertRaisesRegex(LivePolicyError, 'safe projection differs'):
            fixtures.permit(owner, alternate)
        owner.pending = p
        self.assertEqual(fixtures.permit(owner, p).proposal, p)

    def test_original_graph_must_own_projection_before_publication(self):
        owner, state = fixtures.after_initial()
        select = owner._select
        owner._select = lambda *args: replace(select(*args), evidence=deepcopy(args[0]))
        with self.assertRaisesRegex(LivePolicyError, 'original owned decision'):
            owner.propose(state)

    def test_alternative_safe_set_cannot_replace_playing_or_terminal_ack(self):
        owner, p = certain_owner()
        permit = fixtures.permit(owner, p)
        alternate = replace(permit, proposal=replace(p, safe_cells=p.safe_cells[:1]))
        for status, observation in (('PLAYING', ((1, -3, 1, -2), (1, 1, 1, -2))),
                                    ('WON', None), ('LOST', None)):
            with self.subTest(status=status):
                ack = k.make_ack(alternate, status, observation)
                with self.assertRaises(LivePolicyError):
                    owner.acknowledge(ack)
                with self.assertRaises(LivePolicyError):
                    k.next_snapshot(p, ack)
                self.assertIs(owner.pending, p)

    def test_same_grid_new_revision_or_token_cannot_reuse_projection(self):
        owner, p = certain_owner()
        for current in (replace(p.snapshot, board_generation=2),
                        replace(p.snapshot, input_seq=2, input_revision=2, base_m_revision=1),
                        replace(p.snapshot, run_id='b' * 32)):
            with self.subTest(current=current), self.assertRaises(LivePolicyError):
                k.admit_proposal(p, current)
        with self.assertRaises(LivePolicyError):
            owner.validate(k.KValidation(p.snapshot, 'c' * 32, 'd' * 32, p.pending_m_revision))

    def test_max_board_safe_projection_and_finite_v5_wire_bounds(self):
        # Structural stress only: this public DTO does not claim a native proof.
        state = replace(fixtures.initial(30, 16, 0), input_seq=1, input_revision=1,
                        observation=((0,) + (-2,) * 29,) + ((-2,) * 30,) * 15)
        safes = tuple((x, y) for y in range(16) for x in range(30) if (x, y) != (0, 0))
        p = k.KProposal(state, 'b' * 32, 'OPEN', 1, 0, 'certain', 'DIRECT_SAFE_OPEN',
                        'EXACT_SAFE', 1, 1, 1, (), safe_cells=safes)
        ack = k.make_ack(k.KPermit(p, 'c' * 32), 'WON')
        envelope = transport.message(state.run_id, k.MAX_K_SEQUENCE, 'FINISHED', k.to_dict(ack))
        self.assertEqual(envelope['version'], 5)
        with TemporaryDirectory() as directory:
            path = transport.write_once(Path(directory), 'worker', k.MAX_K_SEQUENCE, envelope)
            self.assertLess(path.stat().st_size, transport.MAX_MESSAGE_BYTES)
            decoded = transport.read_next(Path(directory), 'worker', k.MAX_K_SEQUENCE, state.run_id)
            self.assertEqual(k.from_dict(decoded['payload'], k.KAck), ack)
        with self.assertRaises(LivePolicyError):
            transport.message(state.run_id, k.MAX_K_SEQUENCE + 1, 'FINISHED', k.to_dict(ack))


class KCertaintyJobTests(unittest.TestCase):
    setUp = job_fixtures.LiveKJobTests.setUp
    publish = job_fixtures.LiveKJobTests.publish
    pending = job_fixtures.LiveKJobTests.pending
    validate = job_fixtures.LiveKJobTests.validate

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def certain_pending(self):
        p = self.pending()
        permit = self.validate(p)
        self.publish('ADMITTED', k.to_dict(permit))
        self.job.mark_applying(p.token, permit.nonce)
        self.job.acknowledge('PLAYING', fixtures.ONE_SETUP)
        ack = self.job._sent_ack
        state = self.owner.acknowledge(ack)
        self.publish('ACKED', k.to_dict(ack))
        self.job.request(state)
        p = self.owner.propose(state)
        self.publish('PROPOSAL', k.to_dict(p))
        return p

    def test_alternative_safe_admission_is_rejected_before_consumption(self):
        p = self.certain_pending()
        permit = self.validate(p)
        alternate = replace(permit, proposal=replace(p, safe_cells=p.safe_cells[:1]))
        self.publish('ADMITTED', k.to_dict(alternate))
        self.assertEqual(self.job.state, 'cancelling')
        self.assertTrue(self.job._failure.startswith('REPLY_TRANSPORT:'))
        self.assertEqual(self.job._applied_count, 1)  # Initial only.

    def test_alternative_safe_terminal_reply_cannot_finalize_success(self):
        p = self.certain_pending()
        permit = self.validate(p)
        self.publish('ADMITTED', k.to_dict(permit))
        self.job.mark_applying(p.token, permit.nonce)
        self.job.acknowledge('WON')  # Wire-binding fixture, not a claim FLAG can win.
        ack = self.job._sent_ack
        alternate = replace(ack, permit=replace(permit, proposal=replace(p, safe_cells=p.safe_cells[:1])))
        self.publish('FINISHED', k.to_dict(alternate))
        self.assertEqual(self.job.state, 'cancelling')
        self.assertIsNone(self.job._terminal_reply)


class KCertaintyUITests(unittest.TestCase):
    setUp = ui_fixtures.KFeedbackUITests.setUp
    close_ui = ui_fixtures.KFeedbackUITests.close_ui
    start = ui_fixtures.KFeedbackUITests.start
    tick = ui_fixtures.KFeedbackUITests.tick
    apply_initial = ui_fixtures.KFeedbackUITests.apply_initial
    guess_pending = ui_fixtures.KFeedbackUITests.guess_pending

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def certain_pending(self):
        # Parent engine placement only. This fixed board yields LOCAL_SAFE at
        # (8, 7), then (8, 8); the enclosed (4, 4) is not locally proved yet.
        mines = ([(x, y) for y in range(3, 6) for x in range(3, 6) if (x, y) != (4, 4)]
                 + [(7, 7), (7, 8)])
        with patch('core_engine.random.sample', return_value=mines):
            self.apply_initial()
        self.job.deliver_ack()
        self.job.compute()
        p = self.job.pending
        self.assertEqual(p.kind, 'certain')
        self.assertTrue(p.safe_cells)
        return p

    def assert_colors(self, p):
        for cell in p.safe_cells:
            self.assertEqual(self.ui._buttons[cell].analysis_overlay.kind, OverlayKind.SAFE)
        for x, y in p.preinput_m:
            if p.snapshot.observation[y][x] == -2:
                self.assertEqual(self.ui._buttons[(x, y)].analysis_overlay.kind, OverlayKind.MINE)

    def assert_empty(self):
        self.assertIsNone(self.ui._analysis_result)
        self.assertTrue(all(b.analysis_overlay is None and not b.probability_text
                            for b in self.ui._buttons.values()))

    def test_colors_are_visible_without_fake_probabilities_or_input_changes(self):
        p = self.certain_pending()
        self.ui.simple_auto_checkbox.setChecked(False)
        before = (self.engine.get_observation(), self.ui._live_action_count,
                  self.ui._v1_cursor, dict(self.ui.live_auto_totals), len(self.job.requests))
        self.assert_colors(p)
        self.assertEqual(sum(v == -3 for row in self.engine.get_observation() for v in row), 0)
        self.ui.show()
        self.app.processEvents()
        safe = self.ui._buttons[p.safe_cells[0]]
        mine = self.ui._buttons[next(c for c in p.preinput_m if p.snapshot.observation[c[1]][c[0]] == -2)]
        self.assertIn('안전 확정', safe.toolTip())
        self.assertIn('지뢰 확정', mine.toolTip())
        self.assertFalse(safe.probability_text or mine.probability_text)
        for button, green in ((safe, True), (mine, False)):
            color = button.grab().toImage().pixelColor(button.width() // 3, button.height() // 3)
            self.assertGreater(color.green() if green else color.red(), color.red() if green else color.green())
        self.assertEqual(before, (self.engine.get_observation(), self.ui._live_action_count,
                                 self.ui._v1_cursor, dict(self.ui.live_auto_totals), len(self.job.requests)))

    def test_display_toggles_keep_safe_colors_nonce_timer_and_original_graph(self):
        p = self.certain_pending()
        self.tick()
        before = (self.ui._k_validation_nonce, self.ui._v1_timer_nonce, len(self.job.requests),
                  len(self.job.validations), self.ui._live_action_count, self.ui._v1_cursor,
                  dict(self.ui.live_auto_totals), self.overlay._generation)
        graph, result = self.job.owner.selection, self.ui._analysis_result
        with patch.object(KLocalSession, 'analyze_decision', side_effect=AssertionError('extra analyze')), \
                patch.object(self.job.owner, '_select', side_effect=AssertionError('extra select')):
            for enabled in (False, True, False, True):
                self.ui.probability_checkbox.setChecked(enabled)
                self.ui.auto_cursor_checkbox.setChecked(enabled)
                self.assert_colors(p)
                self.assertIs(self.ui._analysis_result, result)
        self.assertIs(self.job.owner.selection, graph)
        self.assertEqual(before, (self.ui._k_validation_nonce, self.ui._v1_timer_nonce, len(self.job.requests),
                                 len(self.job.validations), self.ui._live_action_count, self.ui._v1_cursor,
                                 dict(self.ui.live_auto_totals), self.overlay._generation))

    def test_guess_wait_probability_off_keeps_red_m_and_candidate_border(self):
        p = self.guess_pending()
        self.ui.probability_checkbox.setChecked(False)
        self.assert_colors(p)
        self.assertEqual(p.safe_cells, ())
        self.assertTrue(self.ui._buttons[(p.x, p.y)].analysis_overlay.recommended)
        self.assertEqual(self.ui._buttons[(p.x, p.y)].analysis_overlay.kind, OverlayKind.GUESS_CANDIDATE)
        self.assertTrue(all(not b.probability_text for b in self.ui._buttons.values()))
        self.assertEqual(len(self.job.validations), 1)  # Initial validation only.
        self.assertEqual(self.ui._live_action_count, 1)

    def test_pause_inflight_keeps_colors_then_resume_applies_once_and_expires(self):
        p = self.certain_pending()
        self.tick()
        old_nonce = self.ui._k_validation_nonce
        self.ui.simple_auto_checkbox.setChecked(False)
        self.job.deliver_admission()
        self.assert_colors(p)
        self.assertIs(self.ui._v1_pending, p)
        before = self.ui._live_action_count
        cost = self.ui.live_auto_totals['k_modeled_us']
        self.ui.simple_auto_checkbox.setChecked(True)
        self.tick()
        self.assertNotEqual(self.ui._k_validation_nonce, old_nonce)
        permit = self.job.deliver_admission()
        self.assert_empty()
        self.assertEqual(self.ui._live_action_count, before + 1)
        self.assertEqual(self.ui.live_auto_totals['k_modeled_us'], cost + p.modeled_action_us)
        self.assertEqual(len(self.ui._replay_recorder.events), before + 1)
        self.ui._on_k_admitted(permit)
        self.assertEqual(self.ui._live_action_count, before + 1)
        self.job.deliver_ack()
        self.job.compute()
        new = self.job.pending
        self.assertEqual(set(new.safe_cells), self.job.owner.decision.selection_safe_cells)
        self.assertTrue(set(p.safe_cells).isdisjoint(new.safe_cells))
        self.assertNotIn((4, 4), new.safe_cells)  # No global/Simple fill-in.
        self.assert_colors(new)
        if new.action == 'CHORD':
            self.assertIsNone(self.ui._buttons[(new.x, new.y)].analysis_overlay.kind)
        for c in new.preinput_m:
            if new.snapshot.observation[c[1]][c[0]] == -3:
                self.assertIsNone(self.ui._buttons[c].analysis_overlay)

    def _expire(self, action):
        p = self.certain_pending()
        self.assert_colors(p)
        live_result = self.ui._analysis_result
        old_timeout, old_draw = self.ui._simple_auto_timeout_slot, self.overlay._timeout_slot
        self.tick()
        action()
        after = self.ui._live_action_count
        def expired():
            if self.ui._replay_mode:
                # Replay's own fresh-board analysis may show its initial border.
                # The old K projection must not carry into that separate view.
                self.assertIsNot(self.ui._analysis_result, live_result)
                self.assertIsNone(self.ui._v1_pending)
                self.assertTrue(all(b.analysis_overlay is None or
                                    (b.analysis_overlay.kind is None and b.analysis_overlay.probability is None)
                                    for b in self.ui._buttons.values()))
            else:
                self.assert_empty()
        expired()
        old_timeout()
        old_draw()
        self.job.deliver_admission()
        expired()
        self.assertEqual(self.ui._live_action_count, after)

    def test_structurally_valid_alternate_safe_permit_is_zero_gui_input(self):
        p = self.certain_pending()
        self.tick()
        permit = self.job.owner.validate(self.job.validation)
        self.job.permit, self.job.state = permit, 'admitted'
        alternate = replace(permit, proposal=replace(p, safe_cells=((4, 4),) + p.safe_cells))
        before = self.ui._live_action_count
        self.job.admitted.emit(alternate)
        self.assertEqual(self.ui._live_action_count, before)
        self.assertTrue(self.ui._k_retired)
        self.assert_empty()

    def test_terminal_safe_open_expires_colors_without_promoting_win_flags_to_inputs(self):
        p = self.certain_pending()
        total = self.ui.live_auto_totals['k_modeled_us']
        expected = ((8, 7, 'LOCAL_SAFE'), (8, 8, 'LOCAL_SAFE'), (4, 4, 'EXACT_SAFE'))
        for index, (x, y, continuation) in enumerate(expected):
            self.assertEqual((p.x, p.y, p.continuation), (x, y, continuation))
            self.assertEqual(p.safe_cells, ((x, y),))
            self.assert_colors(p)
            total += p.modeled_action_us
            self.tick()
            self.job.deliver_admission()
            self.assert_empty()
            if index < 2:
                self.job.deliver_ack()
                self.job.compute()
                p = self.job.pending
        self.assertEqual(self.engine.status, GameStatus.WON)
        self.assertIsNone(self.job.acks[-1].observation)
        self.assertEqual(self.ui.live_auto_totals['k_modeled_us'], total)
        self.assertEqual(self.ui.live_auto_totals['k_inputs'], 4)
        self.assertEqual(self.ui._live_action_count, 4)
        self.assertEqual(len(self.ui._replay_recorder.events), 4)
        self.assertEqual(len(self.job.requests), 4)
        self.assertEqual(sum(v == -3 for row in self.engine.get_observation() for v in row), 10)

    def test_reset_clears_colors_and_old_callbacks(self):
        self._expire(self.ui.on_reset)

    def test_policy_change_clears_colors_and_old_callbacks(self):
        self._expire(lambda: self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(POLICY_SIMPLE)))

    def test_hard_retire_clears_colors_and_old_callbacks(self):
        self._expire(self.ui.on_live_takeover)

    def test_error_clears_colors_and_old_callbacks(self):
        self._expire(lambda: self.ui._fail_v1('certainty fixture'))

    def test_replay_clears_colors_and_old_callbacks(self):
        data = ReplayData(ReplayBoard(3, 3, 1, {(1, 1)}), (ReplayEvent(1, 0, 0, 'OPEN'),))
        self._expire(lambda: self.ui._enter_replay_mode(ReplayPlayer(data)))

    def test_close_clears_colors_and_old_callbacks(self):
        self._expire(self.ui.close)

    def _manual(self, buttons, mode, expected):
        p = self.certain_pending()
        self.ui.on_chord_mode_changed(mode)
        self.ui.show()
        self.app.processEvents()
        self.tick()
        cell = self.ui._buttons[p.safe_cells[0]]
        position = self.ui.mapFromGlobal(cell.mapToGlobal(cell.rect().center()))
        old_count = self.ui._live_action_count
        step = self.engine.step
        def observed_step(*args):
            self.assert_empty()
            self.assertFalse(self.ui._v1_owned)
            return step(*args)
        with patch.object(self.engine, 'step', side_effect=observed_step) as called:
            for button in buttons:
                QTest.mousePress(self.ui.windowHandle(), button, pos=position)
            for button in reversed(buttons):
                QTest.mouseRelease(self.ui.windowHandle(), button, pos=position)
        self.assertEqual(called.call_count, 1)
        self.assertEqual(called.call_args.args, (*p.safe_cells[0], expected))
        self.assertEqual(self.ui._live_action_count, old_count + 1)
        self.job.deliver_admission()
        self.assertEqual(self.ui._live_action_count, old_count + 1)
        self.assert_empty()

    def test_manual_left_passes_and_clears_before_step(self):
        self._manual((Qt.LeftButton,), ChordMode.LEFT_CLICK, Action.OPEN)

    def test_manual_right_passes_and_clears_before_step(self):
        self._manual((Qt.RightButton,), ChordMode.LEFT_CLICK, Action.FLAG)

    def test_manual_both_passes_and_clears_before_step(self):
        self._manual((Qt.LeftButton, Qt.RightButton), ChordMode.BOTH_CLICK, Action.CHORD)
