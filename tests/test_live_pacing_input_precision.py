"""Exact input and actual Qt edit events; worker-free and independent oracles."""
from fractions import Fraction
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtTest import QTest, QSignalSpy
from PyQt5.QtWidgets import QApplication

from live_fixed_cadence import FixedCadence
from live_pacing import FixedPeriod, FIXED, MODEL_C
from live_policy import POLICY_K_LC1
from replay_model import ReplayBoard, ReplayData
from replay_player import ReplayPlayer
from tests.test_live_pacing_ui import SimplePacingUITests, edit, mode
from tests.test_live_fixed_rate import FixedRateUITests


def enter(editor, text):
    editor.setFocus()
    QTest.keyClick(editor, Qt.Key_A, Qt.ControlModifier)
    QTest.keyClicks(editor, text)
    QTest.keyClick(editor, Qt.Key_Return)


class FixedPeriodTests(unittest.TestCase):
    def test_cps_exact_inverse_ceil_independent_oracle(self):
        for value in ('0.5', '3', '4', '5', '6', '7', '12', '1000', '6.000000001'):
            with self.subTest(cps=value):
                requested = Fraction(value)
                numerator = 1000000000 * requested.denominator
                expected = numerator // requested.numerator + bool(numerator % requested.numerator)
                actual = FixedPeriod('cps', value)
                self.assertEqual(actual.period_ns, expected)
                self.assertEqual(actual.requested, requested)
                self.assertEqual(actual.target_cps, requested)
                self.assertEqual(actual.source, 'cps')
                self.assertGreaterEqual(Fraction(expected), Fraction(1000000000, 1) / requested)
                self.assertLess(Fraction(expected) - Fraction(1000000000, 1) / requested, 1)

    def test_ms_decimal_zero_and_sub_ns_quantization(self):
        for value in ('0', '1', '2.5', '166.666667', '166.6666667', '200', '250', '500', '2000'):
            with self.subTest(ms=value):
                raw = Fraction(value)*1000000
                expected = raw.numerator//raw.denominator + bool(raw.numerator%raw.denominator)
                actual = FixedPeriod('ms', value)
                self.assertEqual(actual.period_ns, expected)
                self.assertEqual(actual.requested, Fraction(value))
                self.assertEqual(actual.interval_ms, Fraction(expected,1000000))
        for ms,cps in ((200,5),(250,4),(500,2)):
            self.assertEqual(FixedPeriod('ms',ms).target_cps,cps)
        self.assertIsNone(FixedPeriod('ms',0).target_cps)

    def test_invalid_inputs_do_not_expand_ranges(self):
        for source, values in (
                ('cps', ('0','-1','0.499999','1000.000001','','NaN','inf',None,True,6.0)),
                ('ms', ('-1','0.1','0.999999','2000.000001','','NaN','inf',None,True,1.5)),
                ('other', ('1',))):
            for value in values:
                with self.subTest(source=source,value=value), self.assertRaises(ValueError):
                    FixedPeriod(source,value)

    def test_fractional_period_bounded_targets_and_remaining_ceil(self):
        for cps in ('0.5','3','4','5','6','7','12','1000'):
            p=FixedPeriod('cps',cps).period_ns
            for lateness in (-1,0,p//10-1,p//10,p//10+1,p*5):
                with self.subTest(cps=cps,lateness=lateness):
                    old=FixedCadence.from_period_ns(p,1000000000)
                    actual=old.target_ns+lateness
                    keep=0<=10*lateness<=p
                    new=old.after_input(actual)
                    self.assertEqual(new.period_ns,p)
                    self.assertEqual(new.target_ns, old.target_ns+p if keep else actual+p)
                    self.assertEqual(new.started_ns,actual)
                    self.assertGreaterEqual(10*(new.target_ns-actual),9*p)
                    self.assertEqual(new.remaining_ms(new.target_ns-1),1)
                    self.assertEqual(new.remaining_ms(new.target_ns),0)
                    self.assertEqual(new.transition_reason=='phase_kept',keep)

    def test_repeated_small_lateness_preserves_fractional_phase(self):
        for cps in ('3','6','7','12'):
            p=FixedPeriod('cps',cps).period_ns
            state=FixedCadence.from_period_ns(p,1000000000)
            for index in range(1,61):
                with self.subTest(cps=cps,index=index):
                    target=1000000000+index*p
                    self.assertEqual(state.target_ns,target)
                    state=state.after_input(target+(p//10 if index%2 else 0))
                    self.assertEqual(state.target_ns,target+p)

    def test_ns_entry_validates_and_legacy_ms_api_is_preserved(self):
        for value in (-1,1,999999,2000000001,1.0,True,None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                FixedCadence.from_period_ns(value,1)
        for ms in (0,1,199,200,201,2000):
            with self.subTest(ms=ms):
                self.assertEqual(FixedCadence(ms,123).period_ns,ms*1000000)
                self.assertEqual(FixedCadence(ms,123).interval_ms,ms)


class PrecisionUITests(unittest.TestCase):
    setUp = SimplePacingUITests.setUp
    close_ui = SimplePacingUITests.close_ui

    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def show(self):
        self.ui.show()
        self.ui.activateWindow()
        self.app.processEvents()

    def test_keyboard_cps_six_keeps_request_and_precise_period(self):
        self.show()
        ui=self.ui
        enter(ui.pacing_cps_edit,'6')
        self.assertEqual(ui.pacing_cps_edit.text(),'6')
        self.assertEqual(ui._fixed_period.period_ns,166666667)
        self.assertEqual(ui._fixed_period.source,'cps')
        self.assertEqual(ui.simple_auto_interval_spin.text(),'166.667 ms')
        self.assertIn('≈',ui.simple_auto_interval_spin.toolTip())
        ui.simple_auto_checkbox.setChecked(True)
        cadence,nonce=ui._fixed_cadence,ui._v1_timer_nonce
        with patch.object(ui,'on_reset',side_effect=AssertionError('editor reset')):
            for text in ('6','6.000','6'):
                enter(ui.pacing_cps_edit,text)
                self.assertIs(ui._fixed_cadence,cadence)
                self.assertEqual(ui._v1_timer_nonce,nonce)
            for _ in range(4):
                ui.simple_auto_interval_spin.setFocus()
                QTest.keyClick(ui.simple_auto_interval_spin,Qt.Key_Return)
                enter(ui.simple_auto_interval_spin,'166.667')
                ui.pacing_cps_edit.setFocus()
                self.assertEqual(ui._fixed_period.period_ns,166666667)
                self.assertEqual(ui._fixed_period.source,'cps')
                self.assertIs(ui._fixed_cadence,cadence)
        self.assertEqual(ui._live_action_count,0)

    def test_ms_explicit_commit_and_spin_actions_apply_once(self):
        self.show()
        ui=self.ui
        enter(ui.pacing_cps_edit,'6')
        spin=ui.simple_auto_interval_spin
        changes=QSignalSpy(spin.valueChanged)
        enter(spin,'166.5')
        self.assertEqual(ui._fixed_period.period_ns,166500000)
        self.assertEqual(ui._fixed_period.source,'ms')
        self.assertEqual(len(changes),1)
        QTest.keyClick(spin,Qt.Key_Up)
        self.assertEqual(ui._fixed_period.period_ns,176500000)
        QTest.mouseClick(spin,Qt.LeftButton,pos=QPoint(spin.width()-8,spin.height()//4))
        self.assertEqual(ui._fixed_period.period_ns,186500000)
        self.assertEqual(len(changes),3)
        for value,cps in (('200','5'),('250','4'),('500','2'),('0','최대')):
            enter(spin,value)
            self.assertEqual(ui.pacing_cps_edit.text(),cps)
        enter(ui.pacing_cps_edit,'6')
        self.assertEqual(ui._fixed_period.period_ns,166666667)

    def test_focus_out_and_pending_text_spin_commit_once(self):
        self.show()
        ui=self.ui
        spin=ui.simple_auto_interval_spin
        changes=QSignalSpy(spin.valueChanged)
        spin.setFocus()
        QTest.keyClick(spin,Qt.Key_A,Qt.ControlModifier)
        QTest.keyClicks(spin,'250.5')
        self.assertEqual(ui._fixed_period.period_ns,200000000)
        ui.pacing_cps_edit.setFocus()
        self.assertEqual(ui._fixed_period.period_ns,250500000)
        self.assertEqual(len(changes),1)
        spin.setFocus()
        QTest.keyClick(spin,Qt.Key_A,Qt.ControlModifier)
        QTest.keyClicks(spin,'300.5')
        QTest.keyClick(spin,Qt.Key_Up)
        self.assertEqual(ui._fixed_period.period_ns,310500000)
        self.assertEqual(len(changes),2)

    def test_invalid_keyboard_inputs_restore_both_editors(self):
        self.show()
        ui=self.ui
        enter(ui.pacing_cps_edit,'7')
        original=ui._fixed_period
        for editor,values in ((ui.pacing_cps_edit,('0','-1','','NaN','inf','0.499','1001')),
                              (ui.simple_auto_interval_spin,('-1','','NaN','inf','0.5','2001'))):
            for value in values:
                with self.subTest(editor=type(editor).__name__,value=value):
                    enter(editor,value)
                    self.assertIs(ui._fixed_period,original)
                    self.assertEqual(ui.pacing_cps_edit.text(),'7')
                    self.assertEqual(ui.simple_auto_interval_spin.text(),'142.857 ms')

    def test_decimal_ms_more_than_display_precision_is_not_fed_back(self):
        self.show()
        ui=self.ui
        enter(ui.simple_auto_interval_spin,'166.6666667')
        self.assertEqual(ui._fixed_period.period_ns,166666667)
        self.assertEqual(ui._fixed_period.requested,Fraction('166.6666667'))
        state=ui._fixed_period
        for _ in range(10):
            enter(ui.simple_auto_interval_spin,'166.667')
            enter(ui.pacing_cps_edit,ui.pacing_cps_edit.text())
            self.assertIs(ui._fixed_period,state)

    def test_mode_groups_replay_reset_and_close_keep_both_values(self):
        self.show()
        ui=self.ui
        enter(ui.pacing_cps_edit,'6')
        fixed=ui._fixed_period
        self.assertTrue(ui.pacing_fixed_group.isVisible())
        self.assertFalse(ui.pacing_rate_label.isVisible())
        mode(ui)
        enter(ui.pacing_rate_edit,'0.5')
        rate=ui._pacing_rate
        self.assertFalse(ui.pacing_fixed_group.isVisible())
        self.assertTrue(ui.pacing_rate_label.isVisible())
        ui.simple_auto_interval_spin.setValue(250)
        self.assertIs(ui._fixed_period,fixed)
        ui.on_reset()
        ui._enter_replay_mode(ReplayPlayer(ReplayData(ReplayBoard(2,1,1,{(1,0)}),())))
        self.assertFalse(ui.pacing_bar.isVisible())
        edit(ui,'8',True)
        self.assertIs(ui._fixed_period,fixed)
        ui._exit_replay_mode()
        mode(ui,FIXED)
        self.assertEqual(ui.pacing_cps_edit.text(),'6')
        self.assertIs(ui._pacing_rate,rate)
        ui.close()
        enter(ui.simple_auto_interval_spin,'250')
        edit(ui,'4',True)
        self.assertIs(ui._fixed_period,fixed)

    def test_mode_layout_narrow_window_font_and_cell_size(self):
        self.show()
        ui=self.ui
        enter(ui.pacing_cps_edit,'6')
        root=os.environ.get('PACING_RUN_ROOT')
        font_path=os.environ.get('PACING_TEST_FONT')
        family=ui.font().family()
        if font_path:
            font_id=QFontDatabase.addApplicationFont(font_path)
            self.assertGreaterEqual(font_id,0)
            self.addCleanup(lambda: QFontDatabase.removeApplicationFont(font_id))
            family=QFontDatabase.applicationFontFamilies(font_id)[0]
        evidence=[]
        for point_size in (9,14):
            font=QFont(ui.font())
            font.setFamily(family)
            font.setPointSize(point_size)
            ui.setFont(font)
            for mode_value in (FIXED,MODEL_C):
                mode(ui,mode_value)
                ui.resize(480,600)
                ui.cell_size_spin.setValue(10 if mode_value==FIXED else 40)
                self.app.processEvents()
                group=ui.pacing_fixed_group if mode_value==FIXED else ui.pacing_rate_group
                controls=(ui.auto_interval_label,ui.simple_auto_interval_spin,ui.pacing_cps_label,ui.pacing_cps_edit) if mode_value==FIXED else (ui.pacing_rate_label,ui.pacing_rate_edit)
                for left,right in zip(controls,controls[1:]):
                    self.assertLess(left.geometry().right(),right.geometry().left())
                self.assertLessEqual(controls[-1].geometry().right(),group.width())
                self.assertGreater(ui.scroll_area.geometry().top(),ui.pacing_bar.geometry().bottom())
                self.assertGreaterEqual(ui.pacing_cps_edit.width(),ui.pacing_cps_edit.sizeHint().width())
                evidence.append(dict(font_family=family,font_points=point_size,mode=mode_value,actual_width=ui.width(),group_width=group.width(),font_fixture=font_path))
                if root:
                    self.assertTrue(ui.grab().save(str(Path(root)/f'precision-{mode_value}-{point_size}.png')))
        if root:
            (Path(root)/'UI_GEOMETRY.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')


class PrecisionFamilyUITests(unittest.TestCase):
    setUp=FixedRateUITests.setUp
    close_ui=FixedRateUITests.close_ui
    advance=FixedRateUITests.advance
    due=FixedRateUITests.due
    arm=FixedRateUITests.arm
    setUpClass=classmethod(lambda cls: setattr(cls,'app',QApplication.instance() or QApplication([])))

    def test_fractional_period_permit_drain_and_bounded_input(self):
        self.arm(POLICY_K_LC1)
        ui=self.ui
        old=ui._simple_auto_timeout_slot
        edit(ui,'6',True)
        period=166666667
        self.assertEqual(ui._fixed_cadence.period_ns,period)
        self.job.deliver_admission()  # Cancelled 200ms validation drains.
        self.job.deliver_admission()  # New 6 CPS validation is held.
        target=ui._fixed_cadence.target_ns
        self.now[0]=target-1
        old()
        self.due()
        self.assertEqual(self.steps,[])
        self.now[0]=target+period//10
        self.due()
        self.assertEqual(len(self.steps),1)
        self.assertEqual(ui._fixed_cadence.target_ns,target+period)
        phase=ui._fixed_cadence
        self.job.deliver_ack()
        edit(ui,'6.000',True)
        self.assertIs(ui._fixed_cadence,phase)
        self.job.compute()
        mode(ui,MODEL_C)
        self.assertIsNone(ui._fixed_cadence)
        mode(ui,FIXED)
        self.assertEqual(ui._fixed_cadence.target_ns,self.now[0]+period)
        self.assertIsNone(ui._live_first_failure)

    def test_fractional_hard_boundaries_revoke_old_permit(self):
        for boundary in ('manual','reset','policy','replay','close'):
            with self.subTest(boundary=boundary):
                case=type(self)()
                case.setUp()
                try:
                    case.ui.show()
                    self.app.processEvents()
                    case.arm(POLICY_K_LC1)
                    ui=case.ui
                    edit(ui,'7',True)
                    case.job.deliver_admission()
                    permit=case.job.deliver_admission()
                    old=ui._simple_auto_timeout_slot
                    if boundary=='manual':
                        QTest.mousePress(ui._buttons[(2,2)],Qt.LeftButton)
                        self.assertFalse(ui.simple_auto_checkbox.isChecked())
                    elif boundary=='reset':
                        ui.on_reset()
                    elif boundary=='policy':
                        ui.live_policy_combo.setCurrentIndex(0)
                    elif boundary=='replay':
                        ui._enter_replay_mode(ReplayPlayer(ReplayData(ReplayBoard(2,1,1,{(1,0)}),())))
                    else:
                        ui.close()
                    count=len(case.steps)
                    case.now[0]+=5000000000
                    old()
                    ui._on_k_admitted(permit)
                    self.assertEqual(len(case.steps),count)
                    self.assertIsNone(ui._fixed_cadence)
                    self.assertIsNone(ui.auto_cursor_overlay._reservation)
                    self.assertEqual(ui._fixed_period.period_ns,142857143)
                    if boundary=='manual':
                        QTest.mouseRelease(ui._buttons[(2,2)],Qt.LeftButton)
                finally:
                    case.doCleanups()
