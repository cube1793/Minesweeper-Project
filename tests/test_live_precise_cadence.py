"""Fixed-mode timer selection, real input clocks, and valid anchor boundaries.

Real loops here use the real Simple engine/analyzer without starting workers.
Injected-clock tests are named separately; neither is a native acceptance run.
"""
import os
import sys
import time
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from core_engine import Action
from live_pacing import FIXED, MODEL_C
from tests import test_live_auto as simple
from tests.test_live_pacing_clock import QpcObserver, real_loop, write_evidence


@unittest.skipUnless(os.name == 'nt', 'Windows QPC observation')
class PreciseCadenceTests(unittest.TestCase):
    close_ui = simple.LiveAutoUITests.close_ui

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        simple.LiveAutoUITests.setUp(self)
        self.observer = QpcObserver()

    def mode(self, value):
        self.ui.pacing_mode_combo.setCurrentIndex(self.ui.pacing_mode_combo.findData(value))

    def test_type_is_selected_while_stopped_before_every_start_and_restored(self):
        ui, timer = self.ui, self.ui._simple_auto_timer
        original_type = timer.timerType()
        self.assertEqual(original_type, Qt.CoarseTimer)
        self.assertEqual(ui._model_c_timer_type, original_type)
        choose, start = timer.setTimerType, timer.start
        calls = []
        def selected(value):
            self.assertFalse(timer.isActive())
            calls.append(('type', int(value)))
            return choose(value)
        def started(delay):
            self.assertEqual(calls[-1], ('type', int(timer.timerType())))
            calls.append(('start', delay))
            return start(delay)
        with patch.object(timer, 'setTimerType', selected), patch.object(timer, 'start', started):
            for mode in (FIXED, MODEL_C, FIXED, MODEL_C):
                self.mode(mode)
                for repeat in range(2):
                    with self.subTest(mode=mode, repeat=repeat):
                        ui._start_auto_pacing(126005)
                        self.assertTrue(timer.isActive())
                        self.assertTrue(timer.isSingleShot())
                        self.assertEqual(timer.timerType(), original_type if mode==MODEL_C else Qt.PreciseTimer)
        ui._cancel_simple_auto_step()
        self.assertIs(ui._pacing_clock_ns, time.perf_counter_ns)

    def test_injected_early_callback_same_commit_off_on_and_mode_roundtrip(self):
        ui = self.ui
        now = [1000000000]
        ui._pacing_clock_ns = lambda: now[0]
        ui.simple_auto_checkbox.setChecked(True)
        first, nonce = ui._fixed_cadence, ui._v1_timer_nonce
        self.assertEqual(ui._simple_auto_timer.timerType(), Qt.PreciseTimer)
        with patch.object(self.engine, 'step') as step:
            now[0] += 120000000
            ui._simple_auto_timeout_slot()
            self.assertEqual(ui._simple_auto_timer.interval(), 80)
            self.assertEqual(ui._simple_auto_timer.timerType(), Qt.PreciseTimer)
            step.assert_not_called()
        ui.on_simple_auto_interval_changed(200)
        ui.pacing_cps_edit.setText('5')
        ui.pacing_cps_edit.setModified(True)
        ui.pacing_cps_edit.editingFinished.emit()
        self.assertIs(ui._fixed_cadence, first)
        self.assertEqual(ui._v1_timer_nonce, nonce)
        ui.simple_auto_checkbox.setChecked(False)
        self.assertFalse(ui._simple_auto_timer.isActive())
        now[0] += 500000000
        ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(ui._fixed_cadence.started_ns, now[0])
        self.assertEqual(ui._simple_auto_timer.interval(), 200)
        self.mode(MODEL_C)
        self.assertEqual(ui._simple_auto_timer.timerType(), ui._model_c_timer_type)
        self.assertIsNone(ui._fixed_cadence)
        self.mode(FIXED)
        self.assertEqual(ui._simple_auto_timer.timerType(), Qt.PreciseTimer)
        self.assertEqual(ui._simple_auto_timer.interval(), 200)

    def actual_inputs(self, interval, count):
        ui, engine, observer = self.ui, self.engine, self.observer
        if count > 18:
            from tests.test_live_fixed_cadence_process import cadence_fixture
            _, mines, hidden, prefix = cadence_fixture()
            ui._rebuild_game(30, 16, 99)
            engine.reset_with_mines(30, 16, 99, mines)
            engine._revealed = [[(x,y) not in mines | hidden for x in range(30)] for y in range(16)]
            ui._reset_replay_recorder()
            ui.on_left_click(*prefix)
        else:
            ui._rebuild_game(9, 9, 9)
            engine.reset_with_mines(9, 9, 9, {(7, y) for y in range(9)})
            ui.on_left_click(0, 0)
        ui.simple_auto_interval_spin.setValue(interval)
        rows, anchor, apply_start = [], {}, []
        original_restart, original_apply, original_step = ui._restart_fixed_cadence, ui._apply_live_action, engine.step
        loop, guard, expired = real_loop(10000)
        def restart():
            before = observer.read()
            result = original_restart()
            if ui._fixed_cadence is not None:
                anchor.update(before_qpc=before, after_qpc=observer.read())
            return result
        def apply(x, y, action, **kwargs):
            apply_start[:] = [observer.read()]
            result = original_apply(x, y, action, **kwargs)
            following = ui._fixed_cadence
            rows[-1].update(next_target_ns=None if following is None else following.target_ns,
                            next_reason=None if following is None else following.transition_reason)
            if len(rows) >= count:
                ui.simple_auto_checkbox.setChecked(False)
                loop.quit()
            return result
        def step(x, y, action):
            entered, qpc = time.perf_counter_ns(), observer.read()
            cadence = ui._fixed_cadence
            input_ns = sys._getframe(1).f_locals['input_started_ns']
            before = engine.get_counter_snapshot()
            result = original_step(x, y, action)
            after = engine.get_counter_snapshot()
            rows.append(dict(perf_counter_ns=entered, qpc_ticks=qpc, interval_ms=interval,
                anchor_ns=cadence.started_ns, deadline_ns=cadence.deadline_ns,
                target_ns=cadence.target_ns, last_actual_ns=cadence.last_actual_ns,
                transition_reason=cadence.transition_reason,
                independent_lower_ns=observer.ns(qpc-anchor['after_qpc']),
                independent_upper_ns=observer.ns(qpc-anchor['before_qpc']),
                input_clock_ns=input_ns, action=action.name, target=[x,y],
                timer_type=int(ui._simple_auto_timer.timerType()),
                counter_delta=after['active_clicks']+after['wasted_clicks']-before['active_clicks']-before['wasted_clicks']))
            anchor.update(before_qpc=apply_start[0], after_qpc=qpc)
            return result
        try:
            with patch.object(ui, '_restart_fixed_cadence', restart), patch.object(ui, '_apply_live_action', apply), \
                    patch.object(engine, 'step', step):
                ui.simple_auto_checkbox.setChecked(True)
                loop.exec_()
        finally:
            guard.stop()
            ui.simple_auto_checkbox.setChecked(False)
        self.assertFalse(expired)
        self.assertFalse(ui._live_input_uncertain)
        self.assertEqual(len(rows), count)
        for index, row in enumerate(rows):
            with self.subTest(interval=interval, index=index):
                self.assertGreaterEqual(row['perf_counter_ns'], row['deadline_ns'])
                minimum = interval*(900000 if row['transition_reason']=='phase_kept' else 1000000)
                self.assertGreaterEqual(row['independent_lower_ns'], minimum)
                self.assertEqual(row['counter_delta'], 1)
                self.assertEqual(row['timer_type'], Qt.PreciseTimer)
                lateness = row['input_clock_ns']-row['target_ns']
                keep = interval>0 and 0<=lateness*10<=interval*1000000
                expected = (row['target_ns'] if keep else row['input_clock_ns'])+interval*1000000
                self.assertEqual(row['next_target_ns'], expected)
        self.assertIs(ui._pacing_clock_ns, time.perf_counter_ns)
        return rows

    def test_real_200ms_continuous_actual_inputs(self):
        rows = self.actual_inputs(200, 30)
        write_evidence('PRECISE_200MS_INPUTS.json', dict(clocks=self.observer.metadata(), inputs=rows,
            actual_cps=29e9/(rows[-1]['perf_counter_ns']-rows[0]['perf_counter_ns'])))

    def test_real_short_long_and_zero_actual_inputs(self):
        cases = []
        for interval in (0, 16, 19, 20, 32, 43, 64, 127):
            cases.append(dict(interval_ms=interval, inputs=self.actual_inputs(interval, 2)))
        write_evidence('PRECISE_SHORT_LONG_INPUTS.json', dict(clocks=self.observer.metadata(), cases=cases))

    def test_valid_interval_real_timestamp_anchor_keeps_all_input_records(self):
        ui, engine = self.ui, self.engine
        rows = []
        for interval in (0, 1, 19, 20, 200, 2000):
            ui.on_reset()
            engine.reset_with_mines(3, 3, 1, {(1,1)})
            ui.simple_auto_interval_spin.setValue(interval)
            for action, target in ((Action.OPEN,(0,0)), (Action.FLAG,(1,1)), (Action.CHORD,(0,0))):
                with self.subTest(interval=interval, action=action):
                    events = len(ui._replay_recorder.events)
                    records = len(ui.live_input_records)
                    start = time.perf_counter_ns()
                    event = ui._apply_live_action(*target, action, auto_observation=engine.get_observation())
                    end = time.perf_counter_ns()
                    cadence = ui._fixed_cadence
                    self.assertGreaterEqual(cadence.started_ns, start)
                    self.assertLessEqual(cadence.started_ns, end)
                    self.assertGreaterEqual(cadence.target_ns, cadence.started_ns+interval*900000)
                    self.assertLessEqual(cadence.target_ns, cadence.started_ns+interval*1000000)
                    self.assertEqual(cadence.last_actual_ns, cadence.started_ns)
                    self.assertEqual(len(ui._replay_recorder.events), events+1)
                    self.assertEqual(len(ui.live_input_records), records+1)
                    self.assertEqual(event, events)
                    self.assertFalse(ui._live_input_uncertain)
                    rows.append(dict(interval_ms=interval, action=action.name, anchor_ns=cadence.started_ns,
                                     deadline_ns=cadence.deadline_ns, event_index=event))
        write_evidence('VALID_ANCHOR_RECORD_BOUNDARIES.json', rows)
