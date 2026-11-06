"""Presentation-only distance deadlines and actual Qt/fake-owner lifecycle."""
from decimal import Decimal, localcontext
from fractions import Fraction
import unittest
from unittest.mock import patch
from live_distance_pacing import (base_ms, target_distance, DistanceWait, PROFILE_ID,
                                   LOWER_MS, UPPER_MS)
from live_pacing import PacingRate, FIXED, MODEL_C
from live_distance_pacing import DISTANCE
from live_policy import POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1
from tests.test_live_pacing_ui import FamilyPacingUITests, SimplePacingUITests, edit, mode
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from replay_model import ReplayBoard, ReplayData
from replay_player import ReplayPlayer


def select_distance(ui):
    mode(ui, DISTANCE)
    if ui._v1_job.state == "validating" and ui._k_validation_nonce is None:
        ui._v1_job.deliver_admission()


class DistanceMathTests(unittest.TestCase):
    def test_positive_monotone_cap_and_inverse_rate(self):
        for rate in ("0.05", "1", "2", "8"):
            values = [DistanceWait(Decimal(n)/10, PacingRate(rate), 123).duration_ns
                      for n in range(201)]
            self.assertTrue(all(0 < a <= b for a,b in zip(values,values[1:])))
            self.assertEqual(values[160], values[200])
        for d in (0, 1, 5, 16, 100):
            values=[DistanceWait(d,PacingRate(r),0).duration_ns for r in ("0.05","1","2","8")]
            self.assertEqual(values,sorted(values,reverse=True))

    def test_frozen_endpoints_exact_ceil_and_early_deadline(self):
        self.assertEqual(base_ms(0), LOWER_MS)
        self.assertEqual(base_ms(16), UPPER_MS)
        wait=DistanceWait(16,PacingRate("0.05"),123)
        self.assertEqual(wait.duration_ns,11_000_000_000)
        self.assertEqual(wait.deadline_ns,11_000_000_123)
        self.assertEqual(wait.remaining_ms(wait.deadline_ns-1),1)
        self.assertEqual(wait.remaining_ms(wait.deadline_ns),0)
        for d in (0,1,3,10,16):
            with localcontext() as ctx:
                ctx.prec=80
                v=min(Decimal("550"),max(Decimal("91.66666666666667"),
                    Decimal("37.55779754656098")+Decimal("189.88338306970934")*(1+Decimal(d)).ln()))
                expected=Fraction(v)*1_000_000/Fraction("1.7")
                want=-(-expected.numerator//expected.denominator)
            self.assertEqual(DistanceWait(d,PacingRate("1.7"),0).duration_ns,want)

    def test_coordinates_fallback_and_invalid_values(self):
        self.assertEqual(target_distance((1,2),(4,6)),(Decimal(5),None))
        self.assertEqual(target_distance(None,(4,6)),(Decimal(0),"public_actual_cursor_absent"))
        for bad in (-1,True,float("nan"),float("inf"),"1",None):
            with self.assertRaises(ValueError):base_ms(bad)
        for bad in ((-1,0),(True,0),(1,),("1",2)):
            with self.assertRaises(ValueError):target_distance(bad,(0,0))
        for rate in ("0","0.049","8.01","nan"):
            with self.assertRaises(ValueError):PacingRate(rate)
        for now in (-1,True,1.5):
            with self.assertRaises(ValueError):DistanceWait(1,PacingRate(),now)


class DistanceFamilyTests(unittest.TestCase):
    setUpClass=classmethod(FamilyPacingUITests.setUpClass.__func__)
    setUp=FamilyPacingUITests.setUp
    close_ui=FamilyPacingUITests.close_ui
    prepare=FamilyPacingUITests.prepare
    certainty=FamilyPacingUITests.certainty

    def test_distance_unsupported_family_fallback_and_return(self):
        # Exercise the real supported-board predicate, not prepare()'s small
        # synthetic-board override. No fake actor needs to start in this case.
        ui = self.ui
        for policy in (POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1):
            with self.subTest(policy=policy):
                ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
                ui._rebuild_game(9, 9, 10)
                self.assertTrue(ui._v1_supported())
                mode(ui, FIXED)
                edit(ui, '6', True)
                mode(ui, MODEL_C)
                edit(ui, '3')
                select_distance(ui)
                edit(ui, '2')
                self.assertTrue(ui._distance_pacing_active())
                requests = len(self.job.requests)

                ui._rebuild_game(9, 9, 11)  # Legal board, outside the existing presets.
                self.assertFalse(ui._v1_supported())
                self.assertEqual(ui._pacing_mode, DISTANCE)
                self.assertTrue(ui._fixed_pacing_active())
                self.assertFalse(ui._distance_pacing_active())
                self.assertEqual(ui.pacing_mode_combo.currentData(), FIXED)
                self.assertFalse(ui.pacing_mode_combo.model().item(
                    ui.pacing_mode_combo.findData(DISTANCE)).isEnabled())
                self.assertTrue(ui.simple_auto_interval_spin.isEnabled())
                self.assertFalse(ui.pacing_rate_edit.isEnabled())
                edit(ui, '7')  # Even a delivered edit signal must not alter a disabled rate.
                ui.simple_auto_interval_spin.setValue(250)
                self.assertEqual(ui._fixed_period.target_cps, Fraction(4))
                self.assertEqual(ui._pacing_rate, PacingRate('3'))
                self.assertEqual(ui._distance_rate, PacingRate('2'))
                self.assertFalse(ui.simple_auto_checkbox.isEnabled())
                ui.simple_auto_checkbox.setChecked(True)
                self.assertFalse(ui.simple_auto_checkbox.isChecked())
                self.assertEqual(len(self.job.requests), requests)
                self.assertIsNone(self.job.active_run_id)
                self.assertIsNone(ui._pacing_wait)

                ui._rebuild_game(9, 9, 10)
                self.assertTrue(ui._v1_supported())
                self.assertTrue(ui._distance_pacing_active())
                self.assertEqual(ui.pacing_mode_combo.currentData(), DISTANCE)
                self.assertTrue(ui.pacing_mode_combo.model().item(
                    ui.pacing_mode_combo.findData(DISTANCE)).isEnabled())
                self.assertEqual(ui.pacing_rate_edit.text(), '2')
                self.assertEqual(ui._pacing_rate, PacingRate('3'))
                self.assertEqual(ui._fixed_period.target_cps, Fraction(4))
                self.assertFalse(ui.simple_auto_checkbox.isChecked())
                self.assertEqual(len(self.job.requests), requests)

    def test_distance_replay_roundtrip_three_preferences_and_stale_callbacks(self):
        for phase in ('view', 'validation'):
            for same_board in (False, True):
                with self.subTest(phase=phase, same_board=same_board):
                    case = type(self)()
                    case.setUp()
                    try:
                        case.prepare(POLICY_K_LC1)
                        ui = case.ui
                        # Stop before assigning the three independent preferences.
                        ui.simple_auto_checkbox.setChecked(False)
                        if case.job.state == 'validating' and ui._k_validation_nonce is None:
                            case.job.deliver_admission()
                        mode(ui, FIXED)
                        edit(ui, '6', True)
                        mode(ui, MODEL_C)
                        edit(ui, '3')
                        select_distance(ui)
                        edit(ui, '2')
                        ui.simple_auto_checkbox.setChecked(True)
                        self.assertIsInstance(ui._pacing_wait, DistanceWait)
                        old_slot = ui._simple_auto_timeout_slot
                        old_nonce = ui._v1_timer_nonce
                        old_permit = None
                        if phase == 'validation':
                            case.now[0] = ui._pacing_wait.deadline_ns
                            old_slot()
                            self.assertEqual(case.job.state, 'validating')
                            # One legitimate response computed by the fake actor,
                            # held in flight across cancellation; no forged nonce.
                            old_permit = case.job.owner.validate(case.job.validation)
                        fixed, model_rate, distance_rate = (
                            ui._fixed_period, ui._pacing_rate, ui._distance_rate)
                        prior_game, generation = ui._live_game_id, ui._live_board_generation
                        mines = {(x, 8) for x in range(9)} | {(8, 7)}
                        data = ReplayData(ReplayBoard(9, 9, 10, mines), ())
                        self.assertTrue(ui._enter_replay_mode(ReplayPlayer(data)))
                        self.assertFalse(ui.simple_auto_checkbox.isChecked())
                        self.assertEqual(case.job.state, 'cancelling')
                        case.job.complete_cancel()
                        case.app.processEvents()
                        self.assertTrue(ui._replay_mode)
                        self.assertIsNone(ui._replay_entry_pending)
                        count = ui._live_action_count
                        old_slot()
                        if old_permit is not None:
                            ui._on_k_admitted(old_permit)
                        self.assertEqual(ui._live_action_count, count)
                        for editor in (ui.pacing_mode_combo, ui.pacing_rate_edit,
                                       ui.pacing_cps_edit, ui.simple_auto_interval_spin):
                            self.assertFalse(editor.isEnabled())
                        edit(ui, '7')
                        edit(ui, '8', True)
                        ui.simple_auto_interval_spin.setValue(250)
                        mode(ui, FIXED)
                        self.assertEqual(ui._pacing_mode, DISTANCE)
                        self.assertIs(ui._fixed_period, fixed)
                        self.assertIs(ui._pacing_rate, model_rate)
                        self.assertIs(ui._distance_rate, distance_rate)
                        self.assertEqual(ui._replay_player.replay_data, data)

                        returned = (ui.on_same_board_retry() if same_board
                                    else ui.on_exit_replay())
                        self.assertTrue(returned)
                        self.assertFalse(ui._replay_mode)
                        self.assertNotEqual(ui._live_game_id, prior_game)
                        self.assertGreater(ui._live_board_generation, generation)
                        self.assertNotEqual(ui._v1_timer_nonce, old_nonce)
                        self.assertEqual(ui._pacing_mode, DISTANCE)
                        self.assertEqual(ui.pacing_mode_combo.currentData(), DISTANCE)
                        self.assertEqual(ui.pacing_rate_edit.text(), '2')
                        self.assertTrue(ui.pacing_rate_edit.isEnabled())
                        self.assertIs(ui._fixed_period, fixed)
                        self.assertIs(ui._pacing_rate, model_rate)
                        self.assertIs(ui._distance_rate, distance_rate)
                        self.assertFalse(ui.simple_auto_checkbox.isChecked())
                        self.assertFalse(ui.allow_guess_checkbox.isChecked())
                        snapshot = ui.engine.get_board_snapshot()
                        self.assertEqual(snapshot.mines_placed, same_board)
                        if same_board:
                            self.assertIsNotNone(ui._live_fixed_origin)
                            self.assertEqual(set(snapshot.mines), mines)
                        else:
                            self.assertIsNone(ui._live_fixed_origin)
                        count = ui._live_action_count
                        old_slot()
                        if old_permit is not None:
                            ui._on_k_admitted(old_permit)
                        self.assertEqual(ui._live_action_count, count)
                        self.assertIsNone(ui._pacing_wait)
                        self.assertIsNone(ui._k_validation_nonce)
                        self.assertIsNone(ui._k_deferred_permit)
                        self.assertIsNone(ui.auto_cursor_overlay._reservation)
                        self.assertIsNone(ui._live_first_failure)
                        mode(ui, FIXED)
                        self.assertEqual(ui.pacing_cps_edit.text(), '6')
                        mode(ui, MODEL_C)
                        self.assertEqual(ui.pacing_rate_edit.text(), '3')
                        select_distance(ui)
                        self.assertEqual(ui.pacing_rate_edit.text(), '2')
                        self.assertFalse(ui.simple_auto_checkbox.isChecked())
                        self.assertEqual(ui._live_action_count, count)
                    finally:
                        case.doCleanups()

    def test_hard_boundaries_during_view_and_validation_reject_old_callbacks(self):
        for phase in ('view', 'validation'):
            for boundary in ('manual','reset','policy','difficulty','replay','failure','close'):
                with self.subTest(phase=phase,boundary=boundary):
                    case=type(self)()
                    case.setUp()
                    try:
                        case.prepare(POLICY_K_LC1)
                        ui=case.ui
                        select_distance(ui)
                        edit(ui,'0.05')
                        old=ui._simple_auto_timeout_slot
                        if phase=='validation':
                            case.now[0]=ui._pacing_wait.deadline_ns
                            old()
                            self.assertEqual(case.job.state,'validating')
                        if boundary=='manual':
                            QTest.mousePress(ui._buttons[(3,3)],Qt.LeftButton)
                        elif boundary=='reset':ui.on_reset()
                        elif boundary=='policy':ui.live_policy_combo.setCurrentIndex(0)
                        elif boundary=='difficulty':ui.difficulty_combo.setCurrentIndex(1)
                        elif boundary=='replay':
                            ui._enter_replay_mode(ReplayPlayer(ReplayData(ReplayBoard(2,1,1,{(1,0)}),())))
                            self.assertEqual(ui._distance_rate,PacingRate('0.05'))
                        elif boundary=='failure':ui._fail_v1('distance test boundary')
                        else:ui.close()
                        count=ui._live_action_count
                        old()
                        if (phase=='validation' and case.job.owner is not None
                                and case.job.validation is not None):
                            ui._on_k_admitted(case.job.owner.validate(case.job.validation))
                        self.assertEqual(ui._live_action_count,count)
                        self.assertIsNone(ui._pacing_wait)
                        self.assertIsNone(ui._k_deferred_permit)
                        self.assertIsNone(ui.auto_cursor_overlay._reservation)
                        if boundary=='manual':
                            self.assertFalse(ui.simple_auto_checkbox.isChecked())
                            QTest.mouseRelease(ui._buttons[(3,3)],Qt.LeftButton)
                    finally:case.doCleanups()

    def test_all_families_wait_then_admit_preserving_selection_cost_and_ack(self):
        for policy in (POLICY_V1,POLICY_K,POLICY_K_LC0,POLICY_K_LC1):
            with self.subTest(policy=policy):
                self.prepare(policy)
                ui=self.ui
                select_distance(ui)
                edit(ui,"0.05")
                proposal=ui._v1_pending
                wait=ui._pacing_wait
                self.assertIsInstance(wait,DistanceWait)
                self.assertIsNone(ui._fixed_cadence)
                self.assertEqual(self.job.state,"pending")
                self.assertIsNone(ui._k_deferred_permit)
                self.assertAlmostEqual(ui.auto_cursor_overlay._motion[3],wait.duration_ns/1e9)
                before=ui._live_action_count
                self.now[0]=wait.deadline_ns-1
                ui._simple_auto_timeout_slot()
                self.assertEqual(ui._live_action_count,before)
                self.assertEqual(self.job.state,"pending")
                self.now[0]=wait.deadline_ns
                slot=ui._simple_auto_timeout_slot
                slot()
                if policy!=POLICY_V1:
                    self.assertEqual(self.job.state,"validating")
                    self.assertEqual(ui._live_action_count,before)
                    self.job.deliver_admission()
                slot()
                self.assertEqual(ui._live_action_count,before+1)
                self.assertEqual(ui.live_action_records[-1]["modeled_action_us"],proposal.modeled_action_us)
                self.assertEqual(ui.live_input_records[-1]["distance_view"]["profile_id"],PROFILE_ID)
                self.assertEqual(ui.live_input_records[-1]["distance_view"]["deadline_ns"],wait.deadline_ns)
                ui.simple_auto_checkbox.setChecked(False)
                self.job.deliver_ack()
                self.assertIsNone(ui._live_first_failure)

    def test_rate_change_drains_old_permit_and_stale_callbacks(self):
        self.prepare(POLICY_K_LC1)
        ui=self.ui
        select_distance(ui)
        wait=ui._pacing_wait
        slot=ui._simple_auto_timeout_slot
        self.now[0]=wait.deadline_ns
        slot()
        self.assertEqual(self.job.state,"validating")
        before=ui._live_action_count
        edit(ui,"2")
        self.assertIsNone(ui._k_validation_nonce)
        self.job.deliver_admission()
        fresh=ui._pacing_wait
        self.assertIsInstance(fresh,DistanceWait)
        slot()
        self.assertIs(ui._pacing_wait,fresh)
        self.assertEqual(ui._live_action_count,before)
        same_nonce=ui._v1_timer_nonce
        edit(ui,"2")
        self.assertEqual(ui._v1_timer_nonce,same_nonce)
        ui.simple_auto_checkbox.setChecked(False)
        fresh_slot=ui._simple_auto_timeout_slot
        if fresh_slot:fresh_slot()
        self.assertEqual(ui._live_action_count,before)
        ui.simple_auto_checkbox.setChecked(True)
        self.assertGreater(ui._pacing_wait.deadline_ns,self.now[0])

    def test_mode_preferences_and_reset_preserve_separate_rates(self):
        self.prepare(POLICY_V1)
        ui=self.ui
        mode(ui,MODEL_C);edit(ui,"3")
        select_distance(ui);edit(ui,"2")
        slot=ui._simple_auto_timeout_slot
        mode(ui,FIXED);edit(ui,"6",True)
        select_distance(ui)
        self.assertEqual(ui.pacing_rate_edit.text(),"2")
        mode(ui,MODEL_C)
        self.assertEqual(ui.pacing_rate_edit.text(),"3")
        select_distance(ui)
        before=ui._live_action_count
        slot()
        self.assertEqual(ui._live_action_count,before)
        ui.on_reset()
        self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertEqual(ui._distance_rate,PacingRate("2"))
        self.assertEqual(ui._pacing_rate,PacingRate("3"))
        self.assertEqual(ui._fixed_period.target_cps,Fraction(6))
        slot()
        self.assertEqual(ui._live_action_count,0)


class DistanceSimpleTests(unittest.TestCase):
    setUpClass=classmethod(SimplePacingUITests.setUpClass.__func__)
    setUp=SimplePacingUITests.setUp
    close_ui=SimplePacingUITests.close_ui
    prepare_board=SimplePacingUITests.prepare_board

    def test_distance_unsupported_simple_fallback_and_return(self):
        ui = self.ui
        for width, height in ((31, 16), (30, 17)):
            with self.subTest(width=width, height=height):
                mode(ui, FIXED)
                edit(ui, '6', True)
                mode(ui, MODEL_C)
                edit(ui, '3')
                select_distance(ui)
                edit(ui, '2')
                self.assertTrue(ui._distance_pacing_active())
                ui._rebuild_game(width, height, 10)
                self.assertEqual(ui._pacing_mode, DISTANCE)
                self.assertTrue(ui._fixed_pacing_active())
                self.assertFalse(ui._distance_pacing_active())
                self.assertEqual(ui.pacing_mode_combo.currentData(), FIXED)
                self.assertFalse(ui.pacing_mode_combo.model().item(
                    ui.pacing_mode_combo.findData(DISTANCE)).isEnabled())
                self.assertTrue(ui.simple_auto_interval_spin.isEnabled())
                self.assertTrue(ui.pacing_cps_edit.isEnabled())
                self.assertFalse(ui.pacing_rate_edit.isEnabled())
                edit(ui, '7')
                self.assertEqual(ui._distance_rate, PacingRate('2'))
                self.assertEqual(ui._pacing_rate, PacingRate('3'))
                with patch('ui_manager.load_timing_table', side_effect=AssertionError('outside Model C table')), \
                     patch('ui_manager.DistanceWait.from_targets', side_effect=AssertionError('distance fallback')):
                    edit(ui, '4', True)
                    self.assertEqual(ui._fixed_period.period_ns, 250_000_000)
                    ui.simple_auto_checkbox.setChecked(True)
                    self.assertTrue(ui._simple_auto_pending)
                    self.assertIsNone(ui._pacing_wait)
                    self.assertEqual(ui._fixed_cadence.period_ns, 250_000_000)
                    count, events = ui._live_action_count, len(ui._replay_recorder.events)
                    slot = ui._simple_auto_timeout_slot
                    self.now[0] = ui._fixed_cadence.deadline_ns
                    slot()
                    self.assertEqual(ui._live_action_count, count + 1)
                    self.assertEqual(len(ui._replay_recorder.events), events + 1)
                    self.assertNotIn('distance_view', ui.live_input_records[-1])
                    ui.simple_auto_checkbox.setChecked(False)
                    slot()
                    self.assertEqual(ui._live_action_count, count + 1)
                ui._rebuild_game(30, 16, 99)
                self.assertTrue(ui._distance_pacing_active())
                self.assertEqual(ui.pacing_mode_combo.currentData(), DISTANCE)
                self.assertTrue(ui.pacing_mode_combo.model().item(
                    ui.pacing_mode_combo.findData(DISTANCE)).isEnabled())
                self.assertEqual(ui.pacing_rate_edit.text(), '2')
                self.assertEqual(ui._pacing_rate, PacingRate('3'))
                self.assertEqual(ui._fixed_period.target_cps, Fraction(4))
                self.assertFalse(ui.simple_auto_checkbox.isChecked())

    def test_default_and_simple_early_cancel(self):
        ui=self.ui
        self.assertEqual(ui._pacing_mode,FIXED)
        self.assertEqual(ui._fixed_period.period_ns,200_000_000)
        self.assertFalse(ui.simple_auto_checkbox.isChecked())
        select_distance(ui)
        ui.simple_auto_checkbox.setChecked(True)
        wait=ui._pacing_wait
        self.assertIsInstance(wait,DistanceWait)
        before=ui._live_action_count
        self.now[0]=wait.deadline_ns-1
        ui._simple_auto_timeout_slot()
        self.assertEqual(ui._live_action_count,before)
        slot=ui._simple_auto_timeout_slot
        ui.simple_auto_checkbox.setChecked(False)
        self.now[0]=wait.deadline_ns+100
        slot()
        self.assertEqual(ui._live_action_count,before)

