"""Real-clock pacing regression; in-process Qt only, no worker or fake clock.

Direct QPC readings independently bracket the product's unchanged default
callable. Only elapsed tick differences are converted; absolute clock origins
are never subtracted. The lower bound uses the AFTER-reading start boundary,
without a subtracted tolerance. These observers are test code only.
"""
import ctypes
from fractions import Fraction
import json
import os
from pathlib import Path
import sys
import time
import traceback
import unittest
from unittest.mock import patch

from PyQt5.QtCore import QEventLoop, QTimer, QT_VERSION_STR, PYQT_VERSION_STR
from PyQt5.QtWidgets import QApplication

from core_engine import GameStatus
from live_pacing import MODEL_C, PacingRate
from stage3_physical import load_timing_table
from tests import test_live_auto as simple


class QpcObserver:
    """Independent native QPC observer, never installed as the product clock."""
    def __init__(self):
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        for name in ('QueryPerformanceCounter', 'QueryPerformanceFrequency'):
            fn = getattr(self.api, name)
            fn.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
            fn.restype = ctypes.c_int
        value = ctypes.c_longlong()
        if not self.api.QueryPerformanceFrequency(ctypes.byref(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.frequency = value.value
        assert self.frequency > 0

    def read(self):
        value = ctypes.c_longlong()
        if not self.api.QueryPerformanceCounter(ctypes.byref(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        return value.value

    def ns(self, tick_difference):
        # Floor gives a conservative elapsed value, not a permissive tolerance.
        return tick_difference * 1_000_000_000 // self.frequency

    def metadata(self):
        def info(name, api, unit):
            value = time.get_clock_info(name)
            return dict(api=api, implementation=value.implementation,
                        resolution_seconds=value.resolution, monotonic=value.monotonic,
                        adjustable=value.adjustable, unit=unit)
        return dict(python=sys.version, executable=sys.executable,
                    qt=QT_VERSION_STR, pyqt=PYQT_VERSION_STR,
                    reservation=info('perf_counter', 'time.perf_counter_ns', 'integer ns'),
                    cursor=info('perf_counter', 'time.perf_counter', 'float seconds'),
                    prior_clock=info('monotonic', 'time.monotonic_ns', 'integer ns'),
                    observer=dict(api='kernel32.QueryPerformanceCounter',
                                  implementation='QueryPerformanceCounter()',
                                  frequency_hz=self.frequency, unit='integer ticks',
                                  resolution_seconds=1 / self.frequency,
                                  monotonic=True, adjustable=False),
                    comparison='Only QPC tick differences / QPC frequency; no cross-origin subtraction')

    def capture_call(self, operation, clock, *args):
        """Bracket the actual C clock call using profiling, without replacing it."""
        code = operation.__func__.__code__
        events = []
        def profile(frame, event, arg):
            if frame.f_code is code and arg is clock and event in ('c_call', 'c_return'):
                events.append((event, self.read()))
        previous = sys.getprofile()
        entry = self.read()
        sys.setprofile(profile)
        try:
            result = operation(*args)
        finally:
            sys.setprofile(previous)
        exit_tick = self.read()
        assert [e[0] for e in events] == ['c_call', 'c_return'], events
        return result, dict(reservation_entry_qpc=entry,
                            clock_call_before_qpc=events[0][1],
                            clock_call_after_qpc=events[1][1],
                            reservation_exit_qpc=exit_tick,
                            start_call_bracket_ns=self.ns(events[1][1] - events[0][1]),
                            reservation_bracket_ns=self.ns(exit_tick - entry))

    def elapsed(self, start, end_qpc):
        return dict(observed_qpc=end_qpc,
                    elapsed_lower_ns=self.ns(end_qpc - start['clock_call_after_qpc']),
                    elapsed_upper_ns=self.ns(end_qpc - start['clock_call_before_qpc']),
                    from_reservation_exit_ns=self.ns(end_qpc - start['reservation_exit_qpc']),
                    from_reservation_entry_ns=self.ns(end_qpc - start['reservation_entry_qpc']))


def write_evidence(name, data):
    root = os.environ.get('PACING_RUN_ROOT')
    if root:
        (Path(root)/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def real_loop(cap_ms):
    loop, guard, expired = QEventLoop(), QTimer(), []
    guard.setSingleShot(True)
    guard.timeout.connect(lambda: (expired.append(True), loop.quit()))
    guard.start(cap_ms)
    return loop, guard, expired


@unittest.skipUnless(os.name == 'nt', 'Direct Windows QPC observer')
class LivePacingClockTests(unittest.TestCase):
    close_ui = simple.LiveAutoUITests.close_ui

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        simple.LiveAutoUITests.setUp(self)
        self.observer = QpcObserver()
        self.assertIs(self.ui._pacing_clock_ns, time.perf_counter_ns)
        self.assertIs(self.ui.auto_cursor_overlay._clock, time.perf_counter)

    def model_c(self, rate):
        self.ui.pacing_mode_combo.setCurrentIndex(self.ui.pacing_mode_combo.findData(MODEL_C))
        editor = self.ui.pacing_rate_edit
        editor.setText(str(rate))
        editor.setModified(True)
        editor.editingFinished.emit()
        self.assertEqual(self.ui._pacing_rate, PacingRate(rate))

    def test_default_clock_identity_and_actual_resolution(self):
        data = self.observer.metadata()
        samples = [time.perf_counter_ns() for _ in range(256)]
        changes = [b - a for a, b in zip(samples, samples[1:]) if b > a]
        data['sample'] = dict(reads=len(samples), distinct=len(set(samples)),
                              minimum_positive_step_ns=min(changes),
                              maximum_step_ns=max(changes))
        data['product_default_callable_unchanged'] = True
        write_evidence('CLOCK_INFO.json', data)
        info = data['reservation']
        self.assertTrue(info['monotonic'])
        self.assertFalse(info['adjustable'])
        self.assertLess(info['resolution_seconds'], 0.001)
        self.assertGreater(len(set(samples)), 1)
        self.assertEqual(self.ui.auto_cursor_overlay._timer.interval(), 16)

    def test_real_qtimer_32_frozen_cost_trials_no_early_gate(self):
        ui, observer = self.ui, self.observer
        table = load_timing_table()
        # All costs are authentic frozen lookups. Exact and just-over 32ms
        # boundaries are obtained with exact rational rates within 0.05..8.
        plan = [((1, 0), Fraction(8), 16), ((1, 1), Fraction(8), 19),
                ((1, 0), Fraction(4), 32), ((7, 0), Fraction(8), 43),
                ((1, 0), Fraction(2), 64), ((1, 0), Fraction(1), 127),
                ((1, 0), Fraction(126005, 32000), 32),
                ((1, 0), Fraction(126005, 32001), 33)]
        trials = []
        for repeat in range(4):
            for (dx, dy), rate, expected_ms in plan:
                with self.subTest(repeat=repeat, offset=(dx, dy), rate=str(rate)):
                    self.model_c(rate)
                    cost = table[dx][dy]
                    row = dict(repeat=repeat, offset=[dx, dy], cost=cost,
                               rate=str(rate), synthetic_cost=False, deferrals=[], fires=0)
                    loop, guard, expired = real_loop(3000)
                    errors = []
                    def timeout():
                        try:
                            if ui._defer_early_pacing_timeout():
                                row['deferrals'].append(ui._simple_auto_timer.interval())
                                return
                            end = observer.read()
                            row.update(observer.elapsed(row, end))
                            row['fires'] += 1
                            ui._cancel_simple_auto_step()
                        except BaseException:
                            errors.append(traceback.format_exc())
                        loop.quit()
                    ui._connect_auto_timeout(timeout)
                    try:
                        _, start = observer.capture_call(ui._start_auto_pacing, time.perf_counter_ns, cost)
                        row.update(start)
                        wait = ui._pacing_wait
                        row.update(exact_us=str(wait.exact_us), delay_ms=wait.delay_ms,
                                   product_started_ns=wait.started_ns, product_deadline_ns=wait.deadline_ns,
                                   timer_type=int(ui._simple_auto_timer.timerType()))
                        loop.exec_()
                    finally:
                        guard.stop()
                        ui._cancel_simple_auto_step()
                    trials.append(row)
                    write_evidence('REAL_TIMER_TRIALS.json', dict(clocks=observer.metadata(),
                        scope='component input-equivalent gate, actual Qt event loop, worker0', trials=trials))
                    self.assertFalse(errors, errors)
                    self.assertFalse(expired)
                    self.assertEqual(row['fires'], 1)
                    self.assertEqual(row['delay_ms'], expected_ms)
                    self.assertGreaterEqual(row['elapsed_lower_ns'], expected_ms * 1_000_000)
        self.assertEqual(len(trials), 32)
        self.assertIs(ui._pacing_clock_ns, time.perf_counter_ns)

    def test_simple_actual_inputs_at_eight_x_no_early_input(self):
        ui, observer = self.ui, self.observer
        ui._rebuild_game(9, 9, 9)
        self.engine.reset_with_mines(9, 9, 9, {(7, y) for y in range(9)})
        ui.on_left_click(0, 0)
        self.model_c(Fraction(8))
        original_start, original_apply = ui._start_auto_pacing, ui._apply_live_action
        table, starts, inputs, errors = load_timing_table(), [], [], []
        loop, guard, expired = real_loop(6000)
        def start(cost=None):
            result, row = observer.capture_call(original_start, time.perf_counter_ns, cost)
            wait = ui._pacing_wait
            row.update(cost=cost, rate=str(wait.rate.rate), exact_us=str(wait.exact_us),
                       delay_ms=wait.delay_ms, product_started_ns=wait.started_ns,
                       product_deadline_ns=wait.deadline_ns, cursor=list(ui._v1_cursor))
            starts.append(row)
            return result
        def apply(x, y, action, **kwargs):
            end = observer.read()  # Before observer IO or original input work.
            try:
                if kwargs.get('auto_observation') is not None:
                    row = starts[-1]
                    sx, sy = row['cursor']
                    inputs.append(dict(start_index=len(starts)-1, target=[x, y], action=action.name,
                        oracle_cost=table[abs(x-sx)][abs(y-sy)], **observer.elapsed(row, end)))
                result = original_apply(x, y, action, **kwargs)
                if self.engine.status != GameStatus.PLAYING or len(inputs) >= 40:
                    loop.quit()
                return result
            except BaseException:
                errors.append(traceback.format_exc())
                loop.quit()
        try:
            with patch.object(ui, '_start_auto_pacing', start), patch.object(ui, '_apply_live_action', apply):
                ui.simple_auto_checkbox.setChecked(True)
                loop.exec_()
        finally:
            guard.stop()
            ui.simple_auto_checkbox.setChecked(False)
        write_evidence('SIMPLE_REAL_INPUTS.json', dict(clocks=observer.metadata(), starts=starts,
            inputs=inputs, errors=errors, expired=bool(expired), status=self.engine.status.name,
            scope='Public fixed 9x9 fixture, Simple actual input, worker0; not a random preset campaign'))
        self.assertFalse(errors, errors)
        self.assertFalse(expired)
        self.assertEqual(self.engine.status, GameStatus.WON)
        self.assertEqual(len(inputs), 18)
        for i, entry in enumerate(inputs):
            with self.subTest(input=i):
                row = starts[entry['start_index']]
                self.assertEqual(entry['oracle_cost'], row['cost'])
                self.assertGreaterEqual(entry['elapsed_lower_ns'], row['delay_ms'] * 1_000_000)
        self.assertIs(ui._pacing_clock_ns, time.perf_counter_ns)

    def test_cursor_default_seconds_clock_real_elapsed_and_frame_interval(self):
        overlay, observer = self.ui.auto_cursor_overlay, self.observer
        _, row = observer.capture_call(overlay.reserve, time.perf_counter, 'real-cursor', (0, 0), (8, 0), 127)
        row['motion_start_seconds'] = overlay._motion[2]
        loop, guard, expired = real_loop(2000)
        sample_timer = QTimer()
        sample_timer.setSingleShot(True)
        def sample():
            row.update(observer.elapsed(row, observer.read()))
            row['position'] = list(overlay.position)
            loop.quit()
        sample_timer.timeout.connect(sample)
        sample_timer.start(32)
        try:
            loop.exec_()
        finally:
            sample_timer.stop()
            guard.stop()
        write_evidence('CURSOR_REAL_CLOCK.json', dict(clocks=observer.metadata(), sample=row,
            frame_interval_ms=overlay._timer.interval(), minimum_fps_claimed=False))
        self.assertFalse(expired)
        self.assertGreater(row['elapsed_lower_ns'], 0)
        self.assertGreater(row['position'][0], 0)
        self.assertLessEqual(row['position'][0], 8)
        self.assertEqual(overlay._timer.interval(), 16)
        generation = overlay._generation
        overlay.set_display_enabled(False)
        overlay.set_display_enabled(True)
        self.assertEqual(overlay._generation, generation)
        self.assertIs(overlay._clock, time.perf_counter)
