"""K_D23 on the real offscreen Main window, real Engine and recorder, with the accepted UI job seam.

The job is the fake of tests/test_live_k_ui.py (a real KOwner in this process, no subprocess) extended with
the worker's info and basis writers and the parent's receive rules, so the window gets exactly the records
the real job would keep. The boards are the accepted small fixed layouts of INTEGRATION_TEST_PLAN.json; only
these tiny test windows open the preset gate (the product gate is unchanged, as in the accepted process
test). This is no check of the display or of the input on the exhibition machine.
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtWidgets import QApplication

import live_k_basis as b
import live_k_policy as k
import live_policy_worker as worker
import ui_help
from core_engine import GameStatus, MinesweeperEngine
from experiments.program_k_capability import KLocalSession
from live_k_d23 import KD23Explainer
from live_k_info import KInfoSupplement
from live_policy import POLICY_K_D23, POLICY_K_LC1
from tests import test_live_k_ui as fixtures
from tests.ui_settings import isolate_ui_settings
from ui_manager import MinesweeperUI


PLAN = json.loads((Path(__file__).resolve().parent / "fixtures" / "live_k_d23_test_plan_v1.json").read_text(encoding="utf-8"))
BOARDS = PLAN["fixed_boards"]
FORCED_SHORT = PLAN["fixed_states"]["FORCED_ABOVE_MINIMUM"]["expected"]["short"]
LOST_FIRST_LINE = PLAN["connection_runs"]["cases"]["new_lost"]["expected"]["end_first_line"]
NOTHING = "표시할 K 설명이 없습니다."


class D23UIFakeJob(fixtures.KUIFakeJob):
    """UI seam only. The proposal comes from a real KOwner; its info and basis are written by the worker's
    writers, pass the wire form and are accepted by the parent's own rules before the window sees them."""

    diagnosis = "PSEUDO"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._info_writer = self._basis_writer = None
        self._info = self._basis = None

    @property
    def pending_info(self):
        info = self._info
        return info if self.pending is not None and info is not None and info.token == self.pending.token else None

    @property
    def pending_basis(self):
        basis = self._basis
        return basis if self.pending is not None and basis is not None and basis.token == self.pending.token else None

    def start(self, snapshot):
        run = super().start(snapshot)
        self._info = self._basis = self._info_writer = self._basis_writer = None
        if type(snapshot) is k.KSnapshot and snapshot.policy_id in (POLICY_K_LC1, POLICY_K_D23):
            self._info_writer = KInfoSupplement()
        if type(snapshot) is k.KSnapshot and snapshot.policy_id == POLICY_K_D23:
            self._basis_writer = KD23Explainer(self.diagnosis)
        return run

    def compute(self):
        proposal = self.owner.propose(self.requests[-1])
        payload = json.loads(json.dumps(
            worker._k_proposal_payload(proposal, self._info_writer, self.owner, self._basis_writer)))
        received, has_info, raw_info, has_basis, raw_basis = b.split_payload(payload)
        assert received == proposal
        self._info = k.receive_info(received, has_info, raw_info)
        self._basis = (b.receive_basis(received, has_basis, raw_basis, self.diagnosis)
                       if self._basis_writer is not None else None)
        self.deliver(proposal)


class LiveKD23UITests(unittest.TestCase):
    tick = fixtures.LiveKUITests.tick

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        isolate_ui_settings(self)
        self.dialogs = []
        for target, value in (('ui_manager.LivePolicyJob', D23UIFakeJob),
                              ('ui_manager.MinesweeperUI._ensure_zini_metric_job', None),
                              ('ui_manager.QMessageBox.information', None),
                              ('ui_manager.QMessageBox.warning', None),
                              ('ui_manager.QFileDialog.getOpenFileName', ('', '')),
                              ('ui_manager.QFileDialog.getSaveFileName', ('', '')),
                              ('ui_manager.QFileDialog.getExistingDirectory', '')):
            p = patch(target, value) if target.endswith('LivePolicyJob') else patch(target, return_value=value)
            started = p.start()
            self.addCleanup(p.stop)
            if 'QMessageBox' in target:
                self.dialogs.append(started)

    def close(self, ui):
        ui._stop_timer()
        ui.close()
        ui.deleteLater()
        self.app.processEvents()

    def build(self, board, policy=POLICY_K_D23, mines=None):
        """A new game of ``policy`` on one accepted small layout. The layout is given to the Engine's
        placement only; the owner and its records never receive it."""
        spec = BOARDS[board]
        layout = [tuple(cell) for cell in (spec["mines"] if mines is None else mines)]
        engine = MinesweeperEngine(spec["width"], spec["height"], len(layout))
        ui = MinesweeperUI(engine)
        self.addCleanup(self.close, ui)
        ui._v1_supported = lambda: True  # test-only tiny geometry; the product gate is not changed
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
        ui.on_reset()
        ui.simple_auto_interval_spin.setValue(2000)
        placement = patch('core_engine.random.sample', return_value=layout)
        placement.start()
        self.addCleanup(placement.stop)
        self.engine, self.ui, self.job = engine, ui, ui._v1_job
        return ui

    def start(self):
        """Auto ON: the owner starts and its first proposal arrives."""
        self.ui.simple_auto_checkbox.setChecked(True)
        self.job.compute()
        return self.job.pending

    def apply(self):
        """One input through the product's permit path: due, VALIDATE, ADMITTED, the actual input."""
        self.tick()
        return self.job.deliver_admission()

    def following(self):
        """The acknowledgement of the last input; with Auto ON the window asks for the next decision."""
        self.job.deliver_ack()
        self.job.compute()
        return self.job.pending

    def detail(self):
        return tuple(self.ui.k_detail_view.toPlainText().split("\n"))

    def test_u01_catalog_shows_k_and_keeps_the_three_old_names(self):
        ui = self.build("S8W")
        combo = ui.live_policy_combo
        self.assertEqual([combo.itemData(index) for index in range(combo.count())],
                         ['S2_SIMPLE', 'STAGE3_V1', 'K_P0', 'K_LC0', 'K_LC1', 'K_D23',
                          'STAGE4_S', 'STAGE4_M', 'STAGE4_R'])
        for policy, label in (('K_P0', 'K-P0'), ('K_LC0', 'K-LC0'), ('K_LC1', 'K-LC1'), ('K_D23', 'K')):
            with self.subTest(policy=policy):
                index = combo.findData(policy)
                self.assertTrue(combo.model().item(index).isEnabled())
                self.assertEqual(combo.itemText(index), label)
                combo.setCurrentIndex(index)
                self.assertEqual(ui._live_policy, policy)
                self.assertTrue(ui.live_policy_status_label.text().startswith(f'현재: {label} | '))
                self.assertEqual(ui.simple_auto_checkbox.text(), f'{label} 자동 진행')
                # The folded K detail belongs to the new K only.
                self.assertEqual(ui.k_detail_button.isHidden(), policy != 'K_D23')
                self.assertTrue(ui.k_detail_view.isHidden())
        self.assertEqual(self.job.requests, [])
        self.assertEqual(ui._live_action_count, 0)

    def test_u02_status_line_shows_the_reason_and_the_actual_risk(self):
        ui = self.build("G5")
        self.start()
        self.assertEqual(ui.analysis_status_label.text(), "K | 첫 입력: OPEN (0, 0)")
        self.assertIsNone(self.job.pending_basis)
        self.apply()
        guess = self.following()
        basis = self.job.pending_basis
        self.assertEqual(basis.short, FORCED_SHORT)
        self.assertEqual(ui._analysis_result.status_text, "K | 추측: OPEN (3, 0) | " + FORCED_SHORT)
        self.assertEqual(ui.analysis_status_label.text(), "K | 추측: OPEN (3, 0) | " + FORCED_SHORT + " | 추측 대기")
        self.assertEqual(ui._analysis_result.move, guess.move)
        target = ui._analysis_result.overlays[(3, 0)]
        self.assertTrue(target.recommended)
        self.assertEqual((target.probability.mine_worlds, target.probability.total_worlds), (4, 8))
        self.assertEqual(basis.risk, (4, 8))
        # A certain decision: the reason only, no probability.
        ui = self.build("S8W")
        self.start()
        self.apply()
        self.following()
        basis = self.job.pending_basis
        self.assertTrue(basis.short.startswith("0이 증명된 칸 먼저 열기 · 최소 "))
        self.assertEqual(ui.analysis_status_label.text(), "K | 확정 수: OPEN (5, 0) | " + basis.short)
        # K-LC1 on the same board keeps its own line and has no basis.
        ui = self.build("G5", POLICY_K_LC1)
        self.start()
        self.apply()
        self.following()
        self.assertIsNone(self.job.pending_basis)
        self.assertIsNotNone(self.job.pending_info)
        self.assertTrue(ui._analysis_result.status_text.startswith("K-LC1 | 추측: OPEN (4, 0) | 지뢰 확률 "))

    def test_u03_detail_is_folded_by_default_and_shows_selection_and_diagnosis_apart(self):
        ui = self.build("G5")
        self.assertFalse(ui.k_detail_button.isHidden())
        self.assertTrue(ui.k_detail_view.isHidden())
        self.assertFalse(ui.k_detail_button.isChecked())
        self.assertEqual(ui.k_detail_button.text(), "K 설명 펼치기")
        self.assertTrue(ui.k_detail_view.isReadOnly())
        self.start()
        ui.allow_guess_checkbox.setChecked(True)
        self.apply()
        self.following()
        basis = self.job.pending_basis
        # A decision opens neither the detail nor a dialog by itself.
        self.assertTrue(ui.k_detail_view.isHidden())
        self.assertIsNone(ui._help_dialog)
        ui.k_detail_button.setChecked(True)
        self.assertFalse(ui.k_detail_view.isHidden())
        self.assertEqual(ui.k_detail_button.text(), "K 설명 접기")
        lines = self.detail()
        self.assertEqual(lines, b.detail_lines(basis, b.PROPOSED))
        at_selection, at_pseudo, at_linked = (lines.index(title) for title in
                                              (b.SELECTION_TITLE, b.PSEUDO_TITLE, b.LINKED_TITLE))
        self.assertEqual(at_selection, 0)
        self.assertLess(at_pseudo, at_linked)
        # The reason is in the selection part; each diagnosis has its own title below it.
        self.assertTrue(any(line.startswith("선택 이유: 증명된 불가피한 50/50 쌍을 먼저 처리한다.")
                            for line in lines[:at_pseudo]))
        self.assertFalse(any("pseudo 50/50 진단" in line or "linked 풀림 진단" in line for line in lines[:at_pseudo]))
        self.assertEqual(lines[at_pseudo + 1:at_linked], basis.pseudo)
        self.assertTrue(lines[at_pseudo + 1].startswith("pseudo 50/50 진단(별도 진단, 선택에 쓰지 않음)"))
        self.assertEqual(lines[at_linked + 1:], (b.NOT_COMPUTED,))  # not computed by this configuration
        ui.k_detail_button.setChecked(False)
        self.assertTrue(ui.k_detail_view.isHidden())
        self.assertEqual(ui.k_detail_button.text(), "K 설명 펼치기")
        for dialog in self.dialogs:
            dialog.assert_not_called()

    def test_u04_guess_off_shows_a_blocked_proposal_and_sends_no_input(self):
        ui = self.build("G5")
        self.start()
        self.apply()
        guess = self.following()
        basis = self.job.pending_basis
        self.assertTrue(guess.is_guess)
        self.assertFalse(ui.allow_guess_checkbox.isChecked())
        self.assertEqual(ui.analysis_status_label.text(), "K | 추측: OPEN (3, 0) | " + basis.short + " | 추측 대기")
        self.assertIn("추측 대기 · 추측 허용 꺼짐", ui.live_policy_status_label.text())
        self.assertEqual(len(self.job.validations), 1)  # the first input only; none for the guess
        for _ in range(3):
            self.tick()
        self.assertEqual(len(self.job.validations), 1)
        self.assertEqual((ui._live_action_count, len(ui.live_action_records), self.engine.status),
                         (1, 1, GameStatus.PLAYING))
        self.assertFalse(ui._simple_auto_pending)
        self.assertIs(ui._v1_pending, guess)
        ui.k_detail_button.setChecked(True)
        self.assertEqual(self.detail(), b.detail_lines(basis, b.BLOCKED))
        self.assertEqual(self.detail()[1], basis.head_blocked)
        self.assertNotIn("실제 입력 대상", ui.k_detail_view.toPlainText())
        # Nothing of the held proposal is recorded as an input.
        self.assertIsNone(ui.live_action_records[-1]["basis"])
        self.assertTrue(ui._k_last_basis["initial"])
        self.assertEqual(ui._k_end_lines(), ())
        # Guess allowed: the same proposal is worded as a proposal, and only the input as an input.
        ui.allow_guess_checkbox.setChecked(True)
        self.assertIs(ui._v1_pending, guess)
        self.assertEqual(self.detail()[1], basis.head_proposed)
        self.assertEqual(len(self.job.validations), 2)
        self.apply()
        self.assertEqual((ui._live_action_count, self.engine.status), (2, GameStatus.PLAYING))
        self.assertEqual(ui.live_action_records[-1]["basis"], b.basis_to_dict(basis))
        self.assertEqual(self.detail(), b.detail_lines(basis, b.EXECUTED))

    def test_u05_pause_keeps_pending_info_and_basis_and_resume_uses_them(self):
        original = KLocalSession.analyze_decision
        with patch.object(KLocalSession, "analyze_decision", autospec=True, side_effect=original) as analyze:
            ui = self.build("S8W")
            self.start()
            self.apply()
            decision = self.following()
            basis, info = self.job.pending_basis, self.job.pending_info
            self.assertIsNotNone(basis)
            self.assertIsNotNone(info)
            requests, analysed = len(self.job.requests), analyze.call_count
            self.tick()                                   # due: the validation of this proposal is outstanding
            ui.simple_auto_checkbox.setChecked(False)     # pause
            self.job.deliver_admission()                  # the late permit drains and authorises nothing
            self.assertEqual(ui._live_action_count, 1)
            self.assertIs(ui._v1_pending, decision)
            self.assertIs(self.job.pending, decision)
            self.assertIs(self.job.pending_basis, basis)
            self.assertIs(self.job.pending_info, info)
            self.assertIs(ui._k_pending_basis(), basis)
            self.assertEqual(ui._k_detail_text().split("\n")[1], basis.head_proposed)
            ui.simple_auto_checkbox.setChecked(True)      # resume: the kept proposal, not a new analysis
            self.assertIs(ui._v1_pending, decision)
            self.assertIn(basis.short, ui.analysis_status_label.text())
            self.apply()
            self.assertEqual(ui._live_action_count, 2)
            record = ui.live_action_records[-1]
            self.assertEqual((record["token"], record["basis"]), (decision.token, b.basis_to_dict(basis)))
            self.assertEqual((len(self.job.requests), analyze.call_count), (requests, analysed))

    def test_u06_basis_is_bound_to_the_input_record_only_after_the_actual_input(self):
        ui = self.build("S8W")
        self.start()
        self.assertEqual(ui.live_action_records, [])
        self.assertIsNone(ui._k_last_basis)
        self.apply()
        # The first input is no policy decision: it is recorded without a basis.
        self.assertEqual(len(ui.live_action_records), 1)
        self.assertIsNone(ui.live_action_records[0]["basis"])
        self.assertEqual((ui._k_last_basis["initial"], ui._k_last_basis["basis"]), (True, None))
        decision = self.following()
        basis = self.job.pending_basis
        first_token = ui._k_last_basis["token"]
        # Shown and scheduled, even due: still no record of this proposal and nothing bound.
        self.tick()
        self.assertEqual(len(ui.live_action_records), 1)
        self.assertEqual(ui._k_last_basis["token"], first_token)
        self.assertNotEqual(first_token, decision.token)
        self.assertEqual(ui._k_detail_text().split("\n")[1], basis.head_proposed)
        self.job.deliver_admission()                      # the actual input
        self.assertEqual(len(ui.live_action_records), 2)
        record = ui.live_action_records[-1]
        self.assertTrue(record["actual_input_confirmed"])
        self.assertEqual((record["token"], record["policy_id"]), (decision.token, POLICY_K_D23))
        self.assertEqual(record["basis"], b.basis_to_dict(basis))
        self.assertEqual(record["basis"]["token"], decision.token)
        self.assertEqual((record["action"], record["x"], record["y"], record["category"]),
                         ("OPEN", 5, 0, "PROVEN_OPENING_OPEN"))
        last = ui._k_last_basis
        self.assertIs(last["basis"], basis)
        self.assertEqual(last["input_revision"], ui._live_action_count)
        self.assertEqual(last["input_revision"], ui.live_input_records[-1]["input_revision"])
        self.assertTrue(ui.live_input_records[-1]["automatic"])
        self.assertEqual(ui._k_detail_text().split("\n")[1], basis.head_executed)
        self.assertEqual(record["info_status"], self.job._info.status)  # the existing info record is kept
        # K-LC1 inputs on the same board carry no basis at all.
        ui = self.build("S8W", POLICY_K_LC1)
        self.start()
        self.apply()
        self.following()
        self.apply()
        self.assertEqual([row["basis"] for row in ui.live_action_records], [None, None])
        self.assertIsNone(ui._k_last_basis)
        self.assertIsNone(ui._k_detail_text())

    def test_u07_manual_input_policy_change_and_new_game_drop_pending_and_shown_text(self):
        # Manual input over a held guess proposal.
        ui = self.build("G5")
        self.start()
        self.apply()
        guess = self.following()
        basis = self.job.pending_basis
        ui.k_detail_button.setChecked(True)
        self.assertEqual(self.detail()[1], basis.head_blocked)
        ui.on_left_click(4, 0)
        self.assertEqual((self.engine.status, ui._live_action_count), (GameStatus.PLAYING, 2))
        self.assertFalse(ui.live_input_records[-1]["automatic"])
        self.assertIsNone(ui._v1_pending)
        self.assertIsNone(self.job.pending)
        self.assertIsNone(self.job.pending_basis)
        self.assertIsNone(self.job.pending_info)
        self.assertIsNone(ui._k_pending_basis())
        self.assertEqual(self.detail(), (NOTHING,))
        self.assertNotIn(basis.short, ui.analysis_status_label.text())
        self.assertEqual((len(ui.live_action_records), len(self.job.validations)), (1, 1))
        self.job.proposal_ready.emit(guess)               # a late copy of the old proposal is not taken back
        self.assertIsNone(ui._v1_pending)
        self.assertEqual(self.detail(), (NOTHING,))
        # Policy change over a pending decision.
        ui = self.build("S8W")
        self.start()
        self.apply()
        self.following()
        basis = self.job.pending_basis
        self.assertIn(basis.short, ui.analysis_status_label.text())
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(POLICY_K_LC1))
        self.assertIsNone(ui._v1_pending)
        self.assertIsNone(self.job.pending)
        self.assertIsNone(self.job.pending_basis)
        self.assertEqual(ui.analysis_status_label.text(), "정책 선택 완료 · Auto OFF")
        self.assertTrue(ui.k_detail_button.isHidden())
        self.assertIsNone(ui._k_detail_text())
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(POLICY_K_D23))
        self.assertFalse(ui.k_detail_button.isHidden())
        self.assertEqual(ui._k_detail_text(), NOTHING)
        # New game after an executed decision and over a held guess.
        ui = self.build("S8W")
        self.start()
        self.apply()
        self.following()
        executed = self.job.pending_basis
        self.apply()
        self.following()
        held = self.job.pending_basis
        ui.k_detail_button.setChecked(True)
        self.assertIs(ui._k_last_basis["basis"], executed)
        self.assertEqual(self.detail()[1], held.head_blocked)
        game = ui._live_game_id
        ui.on_reset()
        self.assertNotEqual(ui._live_game_id, game)
        self.assertIsNone(ui._k_last_basis)
        self.assertIsNone(ui._v1_pending)
        self.assertEqual(ui.live_action_records, [])
        self.assertEqual(self.detail(), (NOTHING,))
        self.assertNotIn(held.short, ui.analysis_status_label.text())

    def test_u08_won_game_has_no_loss_note_and_lost_guess_shows_the_basic_note(self):
        for board, status in (("S8W", GameStatus.WON), ("G4", GameStatus.LOST)):
            with self.subTest(board=board):
                ui = self.build(board)
                self.start()
                ui.allow_guess_checkbox.setChecked(True)
                self.apply()
                self.following()
                self.apply()
                guess = self.following()
                basis = self.job.pending_basis
                self.assertEqual((guess.action, guess.x, guess.y, basis.reason), ("OPEN", 3, 0, b.FORCED))
                self.assertEqual(basis.loss[0], LOST_FIRST_LINE)
                self.apply()
                self.assertEqual(self.engine.status, status)   # the base result is the Engine's
                record = ui.live_action_records[-1]
                self.assertEqual((record["status"], record["basis"]), (status.name, b.basis_to_dict(basis)))
                self.assertEqual(ui.live_auto_totals["k_inputs"], 3)
                self.assertIn(f"게임 종료 ({status.name})", ui.live_policy_status_label.text())
                ui.k_detail_button.setChecked(True)
                if status == GameStatus.WON:
                    self.assertEqual(ui.analysis_status_label.text(), "게임 종료")
                    self.assertEqual(ui._k_end_lines(), ())
                    self.assertEqual(self.detail(), b.detail_lines(basis, b.EXECUTED))
                    self.assertNotIn("패배 보조 설명", ui.k_detail_view.toPlainText())
                else:
                    self.assertEqual(ui.analysis_status_label.text(), "게임 종료\n" + LOST_FIRST_LINE)
                    self.assertEqual(ui._k_end_lines(), basis.loss)
                    self.assertEqual(self.detail(), b.detail_lines(basis, b.EXECUTED) + basis.loss)
                    self.assertIn("기본 결과 LOST는 그대로다", self.detail()[-1])
        for dialog in self.dialogs:
            dialog.assert_not_called()

    def test_u09_loss_after_a_manual_input_or_the_first_input_says_unknown(self):
        unknown = (b.LOSS_NOT_RECORDED, b.LOSS_BASE)
        # A manual input loses while a certain K proposal is pending: that proposal is no cause.
        ui = self.build("G4")
        self.start()
        self.apply()
        self.following()
        ui.k_detail_button.setChecked(True)
        ui.on_left_click(3, 0)
        self.assertEqual(self.engine.status, GameStatus.LOST)
        self.assertEqual(ui.analysis_status_label.text(), "게임 종료\n" + b.LOSS_NOT_RECORDED)
        self.assertEqual(ui._k_end_lines(), unknown)
        self.assertEqual(self.detail(), unknown)
        # A manual input opens the very cell of a held guess proposal and loses: still not the K reason.
        ui = self.build("G4")
        self.start()
        self.apply()
        self.following()
        self.apply()
        held = self.following()
        basis = self.job.pending_basis
        self.assertEqual((held.x, held.y, ui.allow_guess_checkbox.isChecked()), (3, 0, False))
        ui.k_detail_button.setChecked(True)
        ui.on_left_click(3, 0)
        self.assertEqual(self.engine.status, GameStatus.LOST)
        self.assertFalse(ui.live_input_records[-1]["automatic"])
        self.assertEqual(ui.analysis_status_label.text(), "게임 종료\n" + b.LOSS_NOT_RECORDED)
        self.assertEqual(ui._k_end_lines(), unknown)
        self.assertEqual(self.detail(), unknown)
        self.assertNotIn(basis.loss[0], ui.k_detail_view.toPlainText())
        self.assertEqual(len(ui.live_action_records), 2)   # the held proposal never became an input record
        # The first input itself loses. A new game of the product never places a mine there; this declared
        # layout exists only to reach the fixed sentence of a first input.
        ui = self.build("S8W", mines=[[0, 0]])
        first = self.start()
        self.assertTrue(first.initial)
        self.apply()
        self.assertEqual(self.engine.status, GameStatus.LOST)
        self.assertEqual(ui.analysis_status_label.text(), "게임 종료\n" + b.LOSS_INITIAL)
        self.assertEqual(ui._k_end_lines(), (b.LOSS_INITIAL, b.LOSS_BASE))
        self.assertIsNone(ui.live_action_records[-1]["basis"])
        ui.k_detail_button.setChecked(True)
        self.assertEqual(self.detail(), (b.LOSS_INITIAL, b.LOSS_BASE))

    def test_u10_help_page_names_k_and_keeps_the_old_lines(self):
        ui = self.build("S8W")
        self.start()
        self.apply()
        pending = self.following()
        count = ui._live_action_count
        self.assertIsNone(ui._help_dialog)                 # help is opened by the user only
        ui.on_help()
        tabs = ui._help_dialog.tabs
        titles = [tabs.tabText(index) for index in range(tabs.count())]
        self.assertEqual(titles, [title for title, _ in ui_help.HELP_PAGES])
        self.assertEqual(titles[-1], "K 설명")
        text = tabs.widget(tabs.count() - 1).toPlainText()
        for line in b.HELP_LINES:
            self.assertIn(line, text)
        overview = "".join(tabs.widget(index).toPlainText() for index in range(tabs.count() - 1))
        self.assertIn("K-P0 / K-LC0 / K-LC1:", overview)
        self.assertIn("K: K-LC1의 선택에", overview)
        # Opening the help changes nothing of the game or of the pending proposal.
        self.assertEqual(ui._live_action_count, count)
        self.assertIs(ui._v1_pending, pending)
        ui._help_dialog.close()

    def test_u11_fixed_interval_wait_is_not_recorded_as_an_executed_input(self):
        ui = self.build("S8W")
        self.start()
        permit = self.job.deliver_admission()             # the permit arrives before the interval is due
        self.assertIs(ui._k_deferred_permit, permit)
        self.assertEqual((ui._live_action_count, ui.live_action_records, ui._k_last_basis), (0, [], None))
        self.assertEqual(self.engine.status, GameStatus.PLAYING)
        self.tick()                                       # due: the one actual input
        self.assertEqual((ui._live_action_count, len(ui.live_action_records)), (1, 1))
        decision = self.following()
        basis = self.job.pending_basis
        permit = self.job.deliver_admission()             # permitted, and still waiting for the interval
        self.assertIs(ui._k_deferred_permit, permit)
        self.assertEqual(self.job.state, "admitted")
        self.assertIs(ui._v1_pending, decision)
        self.assertEqual((ui._live_action_count, len(ui.live_action_records)), (1, 1))
        self.assertTrue(ui._k_last_basis["initial"])       # still the first input, not the permitted proposal
        self.assertIsNone(ui.live_action_records[-1]["basis"])
        self.assertEqual(ui._k_detail_text().split("\n")[1], basis.head_proposed)
        self.assertNotIn(basis.head_executed, ui._k_detail_text())
        self.tick()
        self.assertEqual((ui._live_action_count, len(ui.live_action_records)), (2, 2))
        self.assertEqual(ui.live_action_records[-1]["basis"], b.basis_to_dict(basis))
        self.assertEqual(ui._k_detail_text().split("\n")[1], basis.head_executed)


if __name__ == "__main__":
    unittest.main()
