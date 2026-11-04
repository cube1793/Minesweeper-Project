"""Independent integer oracle for bounded phase carry and UI epoch boundaries."""
import unittest
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication

from live_fixed_cadence import FixedCadence
from live_pacing import FIXED, MODEL_C
from live_policy import POLICY_V1, POLICY_K, POLICY_K_LC0, POLICY_K_LC1
from tests.test_live_fixed_cadence_ui import FixedCadenceUITests
from tests.test_live_pacing_ui import edit, mode


class FixedRateTests(unittest.TestCase):
    def test_integer_oracle_at_all_period_and_lateness_boundaries(self):
        for ms in (0, 1, 199, 200, 201, 2000):
            period = ms*1000000
            for lateness in sorted({-1, 0, max(0,period//10-1), period//10, period//10+1, period, 5*period+1}):
                with self.subTest(ms=ms, lateness=lateness):
                    old = FixedCadence(ms, 1000000000)
                    target = 1000000000+period
                    actual = target+lateness
                    keep = period>0 and 0<=lateness*10<=period
                    expected = target+period if keep else actual+period
                    new = old.after_input(actual)
                    self.assertEqual(new.target_ns, expected)
                    self.assertEqual(new.deadline_ns, expected)
                    self.assertEqual(new.started_ns, actual)
                    self.assertEqual(new.last_actual_ns, actual)
                    self.assertEqual(new.transition_reason=='phase_kept', keep)
                    self.assertGreaterEqual((new.target_ns-actual)*10, period*9)
                    remaining = max(0,expected-actual)
                    self.assertEqual(new.remaining_ms(actual),(remaining+999999)//1000000)
                    self.assertEqual(old.target_ns,target)

    def test_small_lateness_never_accumulates_and_minimum_gap_is_nine_tenths(self):
        for ms in (1, 199, 200, 201, 2000):
            period, start = ms*1000000, 1000000000
            cadence = FixedCadence(ms,start)
            previous = None
            for index in range(1,61):
                lateness = period//10 if index%2 else 0
                actual = start+index*period+lateness
                with self.subTest(ms=ms,index=index):
                    self.assertEqual(cadence.target_ns,start+index*period)
                    if previous is not None:
                        self.assertGreaterEqual((actual-previous)*10,9*period)
                    cadence = cadence.after_input(actual)
                    self.assertEqual(cadence.target_ns,start+(index+1)*period)
                    self.assertEqual(cadence.transition_reason,'phase_kept')
                    previous = actual

    def test_large_delay_drops_all_missed_targets(self):
        old = FixedCadence(200,1000000000)
        actual = old.target_ns+1400000000
        new = old.after_input(actual)
        self.assertEqual(new.target_ns,actual+200000000)
        self.assertEqual(new.remaining_ms(actual),200)
        self.assertEqual(new.transition_reason,'late_restart')
        self.assertEqual(new.after_input(new.target_ns).target_ns,actual+400000000)

    def test_missing_phase_and_zero_use_actual_input_without_backlog(self):
        for ms in (0,1,200,2000):
            with self.subTest(ms=ms):
                new = FixedCadence.from_input(ms,123456789)
                self.assertEqual(new.target_ns,123456789+ms*1000000)
                self.assertEqual(new.last_actual_ns,123456789)
                self.assertEqual(new.transition_reason,'missing_target_restart')
        zero = FixedCadence(0,1).after_input(9000000000)
        self.assertEqual(zero.target_ns,9000000000)
        self.assertEqual(zero.remaining_ms(9000000000),0)
        self.assertEqual(zero.transition_reason,'zero_interval')

    def test_invalid_actual_times_rejected_without_mutating_current_target(self):
        old = FixedCadence(200,1000000000)
        for value in (-1,None,True,1.2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                old.after_input(value)
        self.assertEqual(old.target_ns,1200000000)


class FixedRateUITests(unittest.TestCase):
    setUp = FixedCadenceUITests.setUp
    close_ui = FixedCadenceUITests.close_ui
    advance = FixedCadenceUITests.advance
    due = FixedCadenceUITests.due

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def arm(self, policy=POLICY_K, prepare_ms=80):
        # Each subcase ends the previous fake owner's real ACK/cancel path.
        # Reset alone deliberately cannot finish an asynchronous fake job.
        if self.job.active_run_id is not None:
            self.ui.simple_auto_checkbox.setChecked(False)
            if self.job.state == 'acknowledging':
                self.job.deliver_ack()
            self.ui._invalidate_v1_run('independent test variant')
            self.job.complete_cancel()
        return FixedCadenceUITests.arm(self, policy, prepare_ms)

    def test_small_and_large_callback_delays_across_all_four_policies(self):
        for policy in (POLICY_V1,POLICY_K,POLICY_K_LC0,POLICY_K_LC1):
            for lateness in (0,19999999,20000000,20000001):
                with self.subTest(policy=policy,lateness=lateness):
                    self.arm(policy)
                    target = self.start_ns+200000000
                    if policy!=POLICY_V1:
                        self.job.deliver_admission()
                    count = len(self.steps)
                    self.now[0] = target+lateness
                    stale = self.ui._simple_auto_timeout_slot
                    self.due()
                    self.assertEqual(len(self.steps),count+1)
                    self.assertEqual(self.ui._fixed_cadence.last_actual_ns,self.now[0])
                    expected = target+200000000 if lateness<=20000000 else self.now[0]+200000000
                    self.assertEqual(self.ui._fixed_cadence.target_ns,expected)
                    previous_actual = self.now[0]
                    stale()
                    self.assertEqual(len(self.steps),count+1)
                    self.job.deliver_ack()
                    self.job.compute()
                    if policy!=POLICY_V1:
                        self.job.deliver_admission()
                    self.now[0] = expected-1
                    self.due()
                    self.assertEqual(len(self.steps),count+1)
                    self.now[0] = expected
                    self.due()
                    self.assertEqual(len(self.steps),count+2)
                    self.assertGreaterEqual(self.steps[-1][0]-previous_actual,
                                            180000000 if lateness<=20000000 else 200000000)
                    self.assertIsNone(self.ui._live_first_failure)

    def test_late_permit_uses_same_bound_and_long_pause_drops_phase(self):
        for lateness in (10000000,20000000,20000001,1000000000):
            with self.subTest(lateness=lateness):
                self.arm(POLICY_K_LC1,prepare_ms=180)
                target = self.start_ns+200000000
                self.now[0]=target
                self.due()
                count = len(self.steps)
                self.now[0]=target+lateness
                self.job.deliver_admission()
                self.assertEqual(len(self.steps),count+1)
                expected=target+200000000 if lateness<=20000000 else self.now[0]+200000000
                self.assertEqual(self.ui._fixed_cadence.target_ns,expected)

    def test_same_edits_keep_phase_but_modes_off_on_and_speed_restart(self):
        self.arm(POLICY_K_LC1)
        self.job.deliver_admission()
        self.now[0]=self.start_ns+210000000
        self.due()
        phase=self.ui._fixed_cadence
        self.assertEqual(phase.transition_reason,'phase_kept')
        edit(self.ui,'5',True)
        self.ui.auto_cursor_checkbox.setChecked(not self.ui.auto_cursor_checkbox.isChecked())
        self.assertIs(self.ui._fixed_cadence,phase)
        mode(self.ui,MODEL_C)
        self.assertIsNone(self.ui._fixed_cadence)
        self.assertIsNone(self.ui._fixed_cadence_context)
        mode(self.ui,FIXED)
        self.assertEqual(self.ui._fixed_cadence.target_ns,self.now[0]+200000000)
        self.assertIsNone(self.ui._fixed_cadence.last_actual_ns)
        self.ui.simple_auto_checkbox.setChecked(False)
        self.assertIsNone(self.ui._fixed_cadence_context)
        self.advance(300)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(self.ui._fixed_cadence.target_ns,self.now[0]+200000000)
        edit(self.ui,'4',True)
        self.assertEqual(self.ui._fixed_cadence.target_ns,self.now[0]+250000000)

    def test_reservation_rejects_stale_phase_binding_in_each_component(self):
        # Component seam: changing a binding field alone is not a natural input.
        for field in ('_live_game_id','_live_board_generation','_live_policy','_live_run_id','_live_action_count'):
            with self.subTest(field=field):
                self.arm(POLICY_K_LC1)
                self.job.deliver_admission()
                self.now[0]=self.start_ns+210000000
                self.due()
                old=self.ui._fixed_cadence
                value=getattr(self.ui,field)
                changed=value+1 if type(value) is int else value+'_stale_component'
                with patch.object(self.ui,field,changed):
                    self.ui._start_auto_pacing(126005)
                    self.assertIsNot(self.ui._fixed_cadence,old)
                    self.assertEqual(self.ui._fixed_cadence.target_ns,self.now[0]+200000000)
                    self.assertIsNone(self.ui._fixed_cadence.last_actual_ns)

    def test_mode_switch_during_validate_and_ack_never_restores_old_phase(self):
        self.arm(POLICY_K_LC1)
        old_fixed_slot = self.ui._simple_auto_timeout_slot
        old_fixed_target = self.ui._fixed_cadence.target_ns
        self.ui.pacing_mode_combo.setCurrentIndex(self.ui.pacing_mode_combo.findData(MODEL_C))
        self.assertIsNone(self.ui._fixed_cadence)
        self.job.deliver_admission()  # Revoked fixed nonce drains, never applies.
        self.assertEqual(self.steps,[])
        self.assertIsNotNone(self.ui._pacing_wait)
        old_fixed_slot()
        self.assertEqual(self.steps,[])
        self.now[0]=self.ui._pacing_wait.deadline_ns
        old_model_slot=self.ui._simple_auto_timeout_slot
        self.due()
        self.job.deliver_admission()
        self.assertEqual(len(self.steps),1)
        self.assertIsNone(self.ui._fixed_cadence)
        self.ui.pacing_mode_combo.setCurrentIndex(self.ui.pacing_mode_combo.findData(FIXED))
        fresh=self.ui._fixed_cadence
        self.assertNotEqual(fresh.target_ns,old_fixed_target)
        self.assertIsNone(fresh.last_actual_ns)
        self.job.deliver_ack()
        self.assertIs(self.ui._fixed_cadence,fresh)
        self.assertEqual(len(self.steps),1)
        self.job.compute()
        self.job.deliver_admission()
        old_model_slot()
        self.assertEqual(len(self.steps),1)
        self.now[0]=fresh.target_ns-1
        self.due()
        self.assertEqual(len(self.steps),1)
        self.now[0]=fresh.target_ns
        self.due()
        self.assertEqual(len(self.steps),2)
        self.assertIsNone(self.ui._live_first_failure)

