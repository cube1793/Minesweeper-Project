"""Low-load acceptance harness; detailed profiling remains a separate harness.

Every per-input/message observation is an in-memory append. Files are saved
only after the inherited owned-process cleanup and patch restoration finish.
The original fixture, real engine, wire protocol, and Job ownership stay in use.
"""
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

from PyQt5.QtCore import QEventLoop, QTimer, Qt
from PyQt5.QtTest import QTest
from core_engine import MinesweeperEngine, GameStatus
from live_pacing import FIXED, MODEL_C
from live_policy import POLICY_V1, POLICY_K_LC1
from tests import test_live_k_lc1_process as ownership
from tests.test_live_fixed_cadence_process import _campaign_type
from ui_manager import MinesweeperUI


class MemoryRecorder:
    """No file access or worker introspection in the measured callbacks."""
    def __init__(self, observer):
        self.observer = observer
        self.events = []
        self.wire = []

    def event(self, event, ui=None, **fields):
        row = dict(event=event, perf_counter_ns=time.perf_counter_ns(), qpc_ticks=self.observer.read())
        if ui is not None:
            cadence = ui._fixed_cadence
            row.update(run_id=ui._live_run_id,game_id=ui._live_game_id,
                anchor_ns=None if cadence is None else cadence.started_ns,
                deadline_ns=None if cadence is None else cadence.deadline_ns)
        row.update(fields)
        self.events.append(row)
        return row

    def message(self, direction, envelope):
        row = dict(perf_counter_ns=time.perf_counter_ns(),direction=direction,envelope=envelope)
        self.wire.append(row)
        return row


class LowLoadCampaign(_campaign_type()):
    def __init__(self, *args):
        if os.environ.get('MINESWEEPER_LOWLOAD_OPT_IN') != 'REGISTERED_PRIVATE_RUN':
            raise RuntimeError('Registered private measurement runner required')
        super().__init__(*args)
        self.recorder = MemoryRecorder(self.observer)
        self.events = self.recorder.events
        self.steps = []
        self.apply_starts = {}
        self.schedules = {}
        self.real_popen = self.original_popen
        self.original_popen = self.clean_popen
        self.ledger.update(identity='CADENCE_LOWLOAD_ACCEPTANCE_2026_11_05',
            helper_sha256=ownership.sha(Path(__file__)),timing=self.events,
            collection='memory only during inputs/messages; batch save after cleanup',
            worker_internal_calls_measured=False,profile_installed=False,trace_installed=False,
            parent_profile_before=sys.getprofile() is None,parent_trace_before=sys.gettrace() is None)

    def save(self):
        # The parent helper calls save at wire/owner boundaries. Keep all those
        # updates in memory; the separate runner already registered this run.
        self.ledger['elapsed_seconds'] = time.monotonic()-self.started

    def log(self, event, ui=None, **fields):
        return self.recorder.event(event,ui,**fields)

    def tap(self, direction, envelope):
        self.recorder.message(direction,envelope)

    def clean_popen(self, command, **kwargs):
        env = dict(kwargs['env'])
        for key in ('MINESWEEPER_LC1_TRACE_DIRECTORY','MINESWEEPER_PACING_REAL_OPT_IN',
                    'MINESWEEPER_FIXED_CADENCE_REAL_OPT_IN','PACING_RUN_ROOT'):
            env.pop(key,None)
        env['PYTHONPATH'] = self.plan['process']['profile_helper_directory']
        env['PYTHONNOUSERSITE'] = '1'
        env['MINESWEEPER_LOWLOAD_STARTUP_DIRECTORY'] = str(self.root/'startup')
        kwargs['env'] = env
        self.active['controlled_environment'] = {k:env.get(k) for k in (
            'PYTHONPATH','PYTHONNOUSERSITE','MINESWEEPER_LC1_TRACE_DIRECTORY',
            'MINESWEEPER_LOWLOAD_STARTUP_DIRECTORY','TMP','TEMP','TMPDIR')}
        return self.real_popen(command,**kwargs)

    def capture_traces(self, entry):
        # This is called after the owner has been reaped, not during a step.
        pids = {r['pid'] for r in entry['owned_processes']} | {entry['launcher_pid']}
        rows = [json.loads((self.root/'startup'/f'{pid}.json').read_text('utf-8'))
                for pid in pids if (self.root/'startup'/f'{pid}.json').exists()]
        assert rows and all(r['profile_is_none'] and r['trace_is_none'] for r in rows)
        assert all(r['recurring_callbacks_installed']==0 and r['no_user_site']==1 for r in rows)
        entry['worker_startup_checks'] = rows
        entry['worker_internal_call_counts'] = 'NOT_MEASURED_IN_ACCEPTANCE_RUN'

    def install(self):
        assert sys.getprofile() is None and sys.gettrace() is None
        # Only inherited security/ownership hooks. Do not invoke the detailed
        # cadence harness's install(), which uses sys.setprofile.
        ownership.Campaign.install(self)
        apply, restart = MinesweeperUI._apply_live_action, MinesweeperUI._restart_fixed_cadence
        step = MinesweeperEngine.step
        proposal, admitted = MinesweeperUI._on_v1_proposal, MinesweeperUI._on_k_admitted
        acked, due = MinesweeperUI._on_v1_acknowledged, MinesweeperUI._on_v1_auto_timeout
        validate, refresh = ownership.jobs.LivePolicyJob.validate_pending, MinesweeperUI._refresh_live_board
        start_pacing = MinesweeperUI._start_auto_pacing

        def scheduled(ui, cost=None):
            before = self.observer.read()
            result = start_pacing(ui, cost)
            after = self.observer.read()
            wait = ui._pacing_wait or ui._fixed_cadence
            model_c = ui._model_c_pacing_active()
            row = self.log('schedule', ui, mode=MODEL_C if model_c else FIXED,
                token=None if ui._v1_pending is None else ui._v1_pending.token,
                original_cost=cost, rate=str(ui._pacing_rate.rate),
                exact_us=str(wait.exact_us) if model_c else None,
                delay_ms=ui._simple_auto_timer.interval(), timer_type=int(ui._simple_auto_timer.timerType()),
                anchor_ns=wait.started_ns, deadline_ns=wait.deadline_ns,
                target_ns=wait.deadline_ns,
                period_ns=None if model_c else wait.period_ns,
                input_source=ui._fixed_period.source, requested_input=str(ui._fixed_period.requested),
                last_actual_ns=None if model_c else wait.last_actual_ns,
                transition_reason='model_c_wait' if model_c else wait.transition_reason,
                phase_binding=None if model_c else ui._fixed_cadence_context,
                clock_bracket=dict(before_qpc=before, after_qpc=after, anchor_ns=wait.started_ns))
            if not model_c and (id(ui) not in self.anchors or self.anchors[id(ui)]['anchor_ns'] != wait.started_ns):
                self.anchors[id(ui)] = row['clock_bracket']
            self.schedules[id(ui)] = row
            return result

        def restarted(ui):
            before = self.observer.read()
            result = restart(ui)
            after = self.observer.read()
            if ui._fixed_cadence is not None:
                self.anchors[id(ui)] = dict(before_qpc=before,after_qpc=after,anchor_ns=ui._fixed_cadence.started_ns)
                self.log('period_restart',ui,clock_bracket=self.anchors[id(ui)])
            return result

        def applying(ui,x,y,action,**kwargs):
            self.apply_starts[id(ui)] = self.observer.read()
            self.context[id(ui.engine)] = kwargs.get('auto_observation') is not None
            try:
                result = apply(ui,x,y,action,**kwargs)
                if self.context[id(ui.engine)] and self.steps:
                    following = ui._fixed_cadence
                    self.steps[-1].update(next_target_ns=None if following is None else following.target_ns,
                        next_transition_reason=None if following is None else following.transition_reason)
                return result
            finally:
                self.context.pop(id(ui.engine),None)

        def stepped(engine,x,y,action):
            entered,observed = time.perf_counter_ns(),self.observer.read()
            ui = self.by_engine.get(id(engine))
            automatic = self.context.get(id(engine),False)
            before = engine.get_counter_snapshot()
            if automatic:
                assert self.auto_inputs < self.plan['process']['remaining_auto_input_limit']
                schedule = self.schedules[id(ui)]
                model_c = schedule['mode'] == MODEL_C
                cadence = ui._fixed_cadence
                anchor = schedule['clock_bracket'] if model_c else self.anchors[id(ui)]
                deadline = schedule['deadline_ns'] if model_c else cadence.deadline_ns
                input_ns = sys._getframe(1).f_locals['input_started_ns']
                assert entered >= deadline
            result = step(engine,x,y,action)
            after,elapsed = engine.get_counter_snapshot(),engine.get_elapsed_time()
            delta = after['active_clicks']+after['wasted_clicks']-before['active_clicks']-before['wasted_clicks']
            if automatic:
                self.auto_inputs += 1
                original = self.proposals[ui._live_run_id]
                bracket = dict(before_qpc=self.apply_starts[id(ui)],after_qpc=observed,anchor_ns=input_ns)
                row = self.log('actual_step',ui,perf_counter_ns=entered,qpc_ticks=observed,
                    token=original.token,action=action.name,target=[x,y],original_cost=original.modeled_action_us,
                    mode=schedule['mode'], timer_type=schedule['timer_type'],
                    interval_ms=schedule['delay_ms'] if model_c else float(cadence.interval_ms),
                    period_ns=None if model_c else cadence.period_ns,
                    input_source=ui._fixed_period.source, requested_input=str(ui._fixed_period.requested),
                    target_ns=deadline, last_actual_ns=None if model_c else cadence.last_actual_ns,
                    transition_reason='model_c_wait' if model_c else cadence.transition_reason,
                    minimum_gap_ns=(schedule['delay_ms']*1000000 if model_c else
                                    (cadence.period_ns*9+9)//10 if cadence.transition_reason=='phase_kept'
                                    else cadence.period_ns),
                    anchor_ns=anchor['anchor_ns'], deadline_ns=deadline,
                    input_clock_ns=input_ns,input_clock_bracket=bracket,
                    previous_anchor_bracket=anchor,counter_delta=delta,
                    active_clicks=after['active_clicks'],wasted_clicks=after['wasted_clicks'],
                    engine_elapsed_seconds=elapsed,auto_sequence=self.auto_inputs)
                self.steps.append(row)
                self.anchors[id(ui)] = bracket
            elif ui is not None:
                self.log('manual_step',ui,action=action.name,target=[x,y],counter_delta=delta)
            return result

        def proposed(ui,p):
            self.by_run[ui._live_run_id] = ui
            self.proposals[ui._live_run_id] = p
            self.log('proposal_received',ui,token=p.token,action=p.action,target=[p.x,p.y],
                original_cost=p.modeled_action_us,compute_ns=p.compute_ns)
            return proposal(ui,p)

        def permitted(ui,permit):
            key = (permit.proposal.snapshot.run_id,permit.nonce)
            event = 'admitted_recheck' if key in self.seen_permits else 'admitted_received'
            self.seen_permits.add(key)
            self.log(event,ui,token=permit.proposal.token,nonce=permit.nonce)
            return admitted(ui,permit)

        def acknowledged(ui,ack):
            self.log('ack_received',ui,token=ack.token)
            return acked(ui,ack)

        def timed_out(ui,reservation=None):
            wait = ui._pacing_wait or ui._fixed_cadence
            self.log('timer_due_callback',ui,reservation=reservation,
                mode=MODEL_C if ui._model_c_pacing_active() else FIXED,
                timer_type=int(ui._simple_auto_timer.timerType()),
                deadline_ns=None if wait is None else wait.deadline_ns,
                early=bool(wait is not None and time.perf_counter_ns()<wait.deadline_ns))
            return due(ui,reservation)

        def validated(job,snapshot,nonce):
            self.log('validate_entry',self.by_run[snapshot.run_id],token=job.pending.token,nonce=nonce)
            result = validate(job,snapshot,nonce)
            ui = self.by_run[snapshot.run_id]
            switch = getattr(self, 'pending_mode_switch', None)
            if switch is not None and ui.live_auto_totals['auto_inputs']==2:
                self.pending_mode_switch = None
                switch(ui, nonce)
            return result

        def refreshed(ui,*args,**kwargs):
            start = time.perf_counter_ns()
            result = refresh(ui,*args,**kwargs)
            self.log('refresh_finished',ui,started_ns=start)
            return result

        for target,name,value in ((MinesweeperUI,'_restart_fixed_cadence',restarted),
                (MinesweeperUI,'_apply_live_action',applying),(MinesweeperEngine,'step',stepped),
                (MinesweeperUI,'_on_v1_proposal',proposed),(MinesweeperUI,'_on_k_admitted',permitted),
                (MinesweeperUI,'_on_v1_acknowledged',acknowledged),(MinesweeperUI,'_on_v1_auto_timeout',timed_out),
                (MinesweeperUI,'_start_auto_pacing',scheduled),
                (ownership.jobs.LivePolicyJob,'validate_pending',validated),(MinesweeperUI,'_refresh_live_board',refreshed)):
            self.stack.enter_context(patch.object(target,name,value))

    def continuous(self,policy):
        ui = self.fixture(policy)
        loop,guard = QEventLoop(),QTimer()
        guard.setSingleShot(True)
        expired = []
        def timeout():
            expired.append(True)
            loop.quit()
        def limit(_record):
            if ui.live_auto_totals['auto_inputs']>=60 or ui._live_input_uncertain or ui.engine.status!=GameStatus.PLAYING:
                ui.simple_auto_checkbox.setChecked(False)
                loop.quit()
        guard.timeout.connect(timeout)
        ui.live_action_applied.connect(limit)
        try:
            guard.start(self.plan['process']['case_cap_seconds']*1000)
            ui.simple_auto_checkbox.setChecked(True)
            loop.exec_()  # Ordinary Qt dispatch; no timeout.emit or polling sleep.
        finally:
            guard.stop()
            ui.live_action_applied.disconnect(limit)
            ui.simple_auto_checkbox.setChecked(False)
        assert not expired and not ui._live_input_uncertain
        assert ui.live_auto_totals['auto_inputs']==60
        self.wait(lambda: ui._v1_job.state=='ready' or ui._live_input_uncertain,'last exact ACK')
        assert not ui._live_input_uncertain
        rows = [r for r in self.steps if r['run_id']==ui._live_run_id]
        assert len(rows)==60
        cps = self.summarize_inputs(rows)
        self.current_case['cps'] = cps
        assert all(cps['action_counts'].values())
        self.validate_memory()
        self.retire_ui(ui)
        # A performance miss is retained, but does not skip the remaining
        # authorized cases. Ownership/protocol failures still abort at once.

    @staticmethod
    def summarize_inputs(rows):
        assert len(rows) >= 2
        elapsed = rows[-1]['engine_elapsed_seconds']
        count = rows[-1]['active_clicks']+rows[-1]['wasted_clicks']
        cps = dict(automatic_inputs=len(rows),counter_inputs=count,manual_prefix_inputs=1,
            engine_elapsed_seconds=elapsed,N_over_engine_seconds=count/elapsed,
            auto_N_over_engine_seconds=len(rows)/elapsed,
            N_minus_one_over_last_minus_first=(len(rows)-1)*1e9/(rows[-1]['perf_counter_ns']-rows[0]['perf_counter_ns']),
            target_cps=5,acceptance_range=[4.75,5.25],
            acceptance_metric='N_minus_one_over_last_minus_first', tolerance_author='coordinator',
            action_counts={a:sum(r['action']==a for r in rows) for a in ('OPEN','FLAG','CHORD')})
        cps['accepted'] = 4.75<=cps['N_minus_one_over_last_minus_first']<=5.25
        return cps

    def p04_v1_precision(self):
        """10 at 6 CPS, 10 at 250ms, 10 back at 6; separate measured segments."""
        ui = self.fixture(POLICY_V1)
        loop, guard, expired = QEventLoop(), QTimer(), []
        guard.setSingleShot(True)
        guard.timeout.connect(lambda: (expired.append(True), loop.quit()))

        def edit_control(editor, text):
            editor.setFocus()
            QTest.keyClick(editor, Qt.Key_A, Qt.ControlModifier)
            QTest.keyClicks(editor, text)
            QTest.keyClick(editor, Qt.Key_Return)
            self.log('precision_edit', ui, input_source=ui._fixed_period.source,
                     requested_input=str(ui._fixed_period.requested), period_ns=ui._fixed_period.period_ns)

        edit_control(ui.pacing_cps_edit, '6')
        assert ui._fixed_period.period_ns == 166666667 and ui.pacing_cps_edit.text() == '6'

        def applied(_record):
            count = ui.live_auto_totals['auto_inputs']
            if count == 10:
                edit_control(ui.simple_auto_interval_spin, '250')
                assert ui._fixed_period.period_ns == 250000000
            elif count == 20:
                edit_control(ui.pacing_cps_edit, '6')
                assert ui._fixed_period.period_ns == 166666667
            elif count >= 30:
                ui.simple_auto_checkbox.setChecked(False)
                loop.quit()
        ui.live_action_applied.connect(applied)
        try:
            guard.start(self.plan['process']['case_cap_seconds']*1000)
            ui.simple_auto_checkbox.setChecked(True)
            loop.exec_()
        finally:
            guard.stop()
            ui.live_action_applied.disconnect(applied)
            ui.simple_auto_checkbox.setChecked(False)
        assert not expired and not ui._live_input_uncertain
        self.wait(lambda: ui._v1_job.state == 'ready' or ui._live_input_uncertain, 'precision final ACK')
        assert not ui._live_input_uncertain
        rows = [r for r in self.steps if r['run_id']==ui._live_run_id]
        assert len(rows) == 30
        segments = []
        for start, source, requested, period in ((0,'cps','6',166666667),
                (10,'ms','250',250000000),(20,'cps','6',166666667)):
            segment = rows[start:start+10]
            assert all((r['input_source'],r['requested_input'],r['period_ns']) ==
                       (source,requested,period) for r in segment)
            summary = self.summarize_inputs(segment)
            summary.update(target_cps=1000000000/period, accepted=None, acceptance_range=None,
                           acceptance_metric='OBSERVATION_ONLY', sample_start=start+1,
                           input_source=source,requested_input=requested,period_ns=period)
            segments.append(summary)
        self.current_case['segments'] = segments
        self.current_case['run_id'] = ui._live_run_id
        self.validate_memory()
        self.retire_ui(ui)

    def p03_mode_roundtrip(self):
        ui = self.fixture(POLICY_K_LC1)
        loop, guard, expired = QEventLoop(), QTimer(), []
        guard.setSingleShot(True)
        guard.timeout.connect(lambda: (expired.append(True), loop.quit()))
        modes = []
        def switch_pending(ui, nonce):
            assert ui._v1_job.state=='validating'
            self.log('mode_change',ui,from_mode=FIXED,to_mode=MODEL_C,old_nonce=nonce,at_boundary='VALIDATE sent')
            ui.pacing_mode_combo.setCurrentIndex(ui.pacing_mode_combo.findData(MODEL_C))
            ui.pacing_rate_edit.setText('8')
            ui.pacing_rate_edit.setModified(True)
            ui.pacing_rate_edit.editingFinished.emit()
            assert ui._fixed_cadence is None
        self.pending_mode_switch = switch_pending
        def applied(_record):
            count = ui.live_auto_totals['auto_inputs']
            modes.append(MODEL_C if ui._model_c_pacing_active() else FIXED)
            if count == 4:
                self.log('mode_change',ui,from_mode=MODEL_C,to_mode=FIXED,at_boundary='ACK sent',
                         ack_pending=ui._v1_expected_ack is not None)
                ui.pacing_mode_combo.setCurrentIndex(ui.pacing_mode_combo.findData(FIXED))
                assert ui._fixed_cadence.last_actual_ns is None
            elif count >= 6:
                ui.simple_auto_checkbox.setChecked(False)
                loop.quit()
        ui.live_action_applied.connect(applied)
        try:
            guard.start(self.plan['process']['case_cap_seconds']*1000)
            ui.simple_auto_checkbox.setChecked(True)
            loop.exec_()
        finally:
            guard.stop()
            ui.live_action_applied.disconnect(applied)
            ui.simple_auto_checkbox.setChecked(False)
        assert not expired and not ui._live_input_uncertain
        assert modes == [FIXED, FIXED, MODEL_C, MODEL_C, FIXED, FIXED]
        assert self.pending_mode_switch is None
        self.wait(lambda: ui._v1_job.state=='ready' or ui._live_input_uncertain, 'roundtrip exact ACK')
        assert not ui._live_input_uncertain
        self.validate_memory()
        rows = [row for row in self.steps if row['run_id']==ui._live_run_id]
        assert len(rows)==6
        for row in rows:
            expected = ui._model_c_timer_type if row['mode']==MODEL_C else Qt.PreciseTimer
            assert row['timer_type']==expected
        self.current_case['modes'] = modes
        self.current_case['run_id'] = ui._live_run_id
        self.retire_ui(ui)

    def validate_memory(self):
        for row in self.steps:
            assert row['counter_delta']==1
            lower = self.observer.ns(row['qpc_ticks']-row['previous_anchor_bracket']['after_qpc'])
            row['qpc_elapsed_lower_ns'] = lower
            row['qpc_elapsed_upper_ns'] = self.observer.ns(row['qpc_ticks']-row['previous_anchor_bracket']['before_qpc'])
            assert lower>=row['minimum_gap_ns']
            assert row['perf_counter_ns']>=row['target_ns']
            wire = [w['envelope'] for w in self.recorder.wire if w['envelope']['run_id']==row['run_id']]
            proposals = [w['payload'] for w in wire if w['kind']=='PROPOSAL' and w['payload']['token']==row['token']]
            assert len(proposals)==1
            p = proposals[0]
            assert (p['action'],p['x'],p['y'],p['modeled_action_us'])==(row['action'],*row['target'],row['original_cost'])
            def token(payload):
                return payload.get('token') or payload['permit']['proposal']['token']
            acks = [w['payload'] for w in wire if w['kind']=='ACK' and token(w['payload'])==row['token']]
            acked = [w['payload'] for w in wire if w['kind']=='ACKED' and token(w['payload'])==row['token']]
            assert len(acks)==len(acked)==1 and acks[0]==acked[0]

    def run(self):
        try:
            super().run()
            failed = [case for case in self.ledger['cases']
                      if 'cps' in case and not case['cps']['accepted']]
            if failed:
                for case in failed:
                    case['status'] = 'PERFORMANCE_FAIL'
                self.ledger['status'] = 'PERFORMANCE_FAIL'
                raise AssertionError('Actual inter-input CPS outside coordinator range: '
                                     + ', '.join(case['name'] for case in failed))
        finally:
            self.ledger.update(parent_profile_after=sys.getprofile() is None,parent_trace_after=sys.gettrace() is None,
                wire=self.recorder.wire,actual_auto_inputs=self.auto_inputs,batch_saved_after_cleanup=True)
            assert sys.getprofile() is None and sys.gettrace() is None
            # All real owners have passed the inherited cleanup before this IO.
            ownership.dump(self.path,self.ledger)
            ownership.dump(self.root/'TIMING_EVENTS.json',self.events)
            ownership.dump(self.root/'WIRE_EVENTS.json',self.recorder.wire)


# These component tests run without a real child. Performance acceptance is
# opt-in and is executed only by the registered low-load campaign runner.
import copy
import tempfile
import unittest
from types import SimpleNamespace


class MeasurementHarnessTests(unittest.TestCase):
    def test_primary_cps_excludes_manual_prefix_and_engine_elapsed(self):
        rows = [dict(perf_counter_ns=1000000000+i*220000000, engine_elapsed_seconds=12,
                     active_clicks=60, wasted_clicks=1, action='OPEN') for i in range(60)]
        summary = LowLoadCampaign.summarize_inputs(rows)
        self.assertGreater(summary['N_over_engine_seconds'], 4.75)
        self.assertAlmostEqual(summary['N_minus_one_over_last_minus_first'], 1000/220)
        self.assertFalse(summary['accepted'])
        rows[-1].update(active_clicks=600, engine_elapsed_seconds=1)
        self.assertEqual(LowLoadCampaign.summarize_inputs(rows)['accepted'], False)
        for index, row in enumerate(rows):
            row['perf_counter_ns'] = 1000000000+index*200000000
        summary = LowLoadCampaign.summarize_inputs(rows)
        self.assertEqual(summary['N_minus_one_over_last_minus_first'], 5)
        self.assertTrue(summary['accepted'])
        self.assertEqual(summary['acceptance_metric'], 'N_minus_one_over_last_minus_first')
        self.assertEqual(summary['tolerance_author'], 'coordinator')

    def test_memory_callbacks_do_not_open_files_or_mutate_input_state(self):
        observer=SimpleNamespace(read=lambda:123)
        recorder=MemoryRecorder(observer)
        cadence=SimpleNamespace(started_ns=100,deadline_ns=200)
        ui=SimpleNamespace(_fixed_cadence=cadence,_live_run_id='run',_live_game_id='game')
        envelope=dict(kind='PROPOSAL',run_id='run',seq=3,payload=dict(token='t',x=1,y=2))
        original=copy.deepcopy(envelope)
        with patch('builtins.open',side_effect=AssertionError('IO')), patch.object(Path,'open',side_effect=AssertionError('IO')):
            row=recorder.event('proposal_received',ui,token='t')
            wire=recorder.message('worker',envelope)
        self.assertEqual(envelope,original)
        self.assertIs(ui._fixed_cadence,cadence)
        self.assertEqual((row['anchor_ns'],row['deadline_ns']),(100,200))
        self.assertIs(wire['envelope'],envelope)
        self.assertEqual(len(recorder.events),1)
        self.assertEqual(len(recorder.wire),1)

    def test_save_keeps_growing_ledger_in_memory(self):
        campaign=LowLoadCampaign.__new__(LowLoadCampaign)
        campaign.started=time.monotonic()
        campaign.ledger={'wire':[{'token':'preserve'}]}
        with patch('builtins.open',side_effect=AssertionError('IO')), patch.object(Path,'open',side_effect=AssertionError('IO')):
            campaign.save()
        self.assertEqual(campaign.ledger['wire'],[{'token':'preserve'}])
        self.assertGreaterEqual(campaign.ledger['elapsed_seconds'],0)

    def test_opt_in_is_checked_before_campaign_initialization(self):
        with patch.dict(os.environ,{'MINESWEEPER_LOWLOAD_OPT_IN':''}), \
                patch.object(ownership.Campaign,'__init__',side_effect=AssertionError('Initialized')) as parent:
            with self.assertRaises(RuntimeError):
                LowLoadCampaign(None,None,None)
            parent.assert_not_called()

    def test_child_environment_sanitization_preserves_command_and_options(self):
        campaign=LowLoadCampaign.__new__(LowLoadCampaign)
        campaign.root=Path(os.environ['TMP'])/'component'
        campaign.plan={'process':{'profile_helper_directory':str(campaign.root/'startup_code')}}
        campaign.active={}
        calls=[]
        campaign.real_popen=lambda command,**kwargs:calls.append((command,kwargs)) or 'returned'
        command=['approved-python','-B','-m','live_policy_worker','private','run','0']
        env={'TMP':'private','MINESWEEPER_LC1_TRACE_DIRECTORY':'old','PYTHONPATH':'old',
             'MINESWEEPER_PACING_REAL_OPT_IN':'old','PACING_RUN_ROOT':'old'}
        original=dict(env)
        value=campaign.clean_popen(command,env=env,creationflags=4,cwd='unchanged')
        self.assertEqual(value,'returned')
        self.assertEqual(env,original)
        actual_command,kwargs=calls[0]
        self.assertIs(actual_command,command)
        self.assertEqual((kwargs['creationflags'],kwargs['cwd']),(4,'unchanged'))
        self.assertNotIn('MINESWEEPER_LC1_TRACE_DIRECTORY',kwargs['env'])
        self.assertNotIn('PACING_RUN_ROOT',kwargs['env'])
        self.assertEqual(kwargs['env']['PYTHONPATH'],campaign.plan['process']['profile_helper_directory'])
        self.assertEqual(kwargs['env']['PYTHONNOUSERSITE'],'1')

    def test_install_uses_no_profiler_and_restores_product_methods(self):
        original=MinesweeperUI._apply_live_action
        with tempfile.TemporaryDirectory(prefix='lowload_component_') as directory:
            root=Path(directory)
            plan={'process':dict(enabled=True,campaign_wall_cap_seconds=20,case_cap_seconds=10,
                  total_owner_start_limit=0,planned_max_owner_starts=0,remaining_auto_input_limit=0,cases=[])}
            (root/'AUTHORIZED_EXECUTION_PLAN.json').write_text(json.dumps(plan),encoding='utf-8')
            with patch.dict(os.environ,{'MINESWEEPER_LOWLOAD_OPT_IN':'REGISTERED_PRIVATE_RUN'}):
                campaign=LowLoadCampaign(root,'component',lambda:{})
            try:
                with patch.object(sys,'setprofile',side_effect=AssertionError('profile')), \
                        patch.object(sys,'settrace',side_effect=AssertionError('trace')):
                    campaign.install()
                self.assertIsNone(sys.getprofile())
                self.assertIsNone(sys.gettrace())
                self.assertIsNot(MinesweeperUI._apply_live_action,original)
                self.assertEqual(campaign.ledger['popen_attempts'],0)
            finally:
                campaign.cleanup_all()
                campaign.stack.close()
            self.assertIs(MinesweeperUI._apply_live_action,original)

    def test_batch_validation_rejects_bad_timing_selection_and_ack(self):
        campaign=LowLoadCampaign.__new__(LowLoadCampaign)
        campaign.observer=SimpleNamespace(ns=lambda ticks:ticks)
        step=dict(run_id='run',token='t',counter_delta=1,qpc_ticks=300000000,
             previous_anchor_bracket=dict(after_qpc=100000000,before_qpc=99999900),
             interval_ms=200,minimum_gap_ns=180000000,perf_counter_ns=300000000,target_ns=280000000,
             action='OPEN',target=[2,3],original_cost=126005)
        ack=dict(token='t',action='OPEN',x=2,y=3)
        envelopes=[dict(kind='PROPOSAL',run_id='run',payload=dict(token='t',action='OPEN',x=2,y=3,modeled_action_us=126005)),
                   dict(kind='ACK',run_id='run',payload=ack),dict(kind='ACKED',run_id='run',payload=dict(ack))]
        def reset():
            campaign.steps=[copy.deepcopy(step)]
            campaign.recorder=SimpleNamespace(wire=[dict(envelope=copy.deepcopy(e)) for e in envelopes])
        reset()
        campaign.validate_memory()
        mutations=[lambda:campaign.steps[0].update(counter_delta=0),
                   lambda:campaign.steps[0].update(qpc_ticks=279999999),
                   lambda:campaign.steps[0].update(perf_counter_ns=279999999),
                   lambda:campaign.steps[0].update(original_cost=1),
                   lambda:campaign.recorder.wire[-1]['envelope']['payload'].update(x=9),
                   lambda:campaign.recorder.wire.append(copy.deepcopy(campaign.recorder.wire[0]))]
        for index,mutate in enumerate(mutations):
            with self.subTest(invalid=index):
                reset();mutate()
                with self.assertRaises(AssertionError):
                    campaign.validate_memory()
