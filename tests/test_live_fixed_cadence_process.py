"""Opt-in actual cadence campaign and explicitly synthetic public fixture.

No unittest entry points: the real process runner must opt in and register
every owner. Public reveals are not a natural flood or preset completion.
"""
from random import Random

from core_engine import MinesweeperEngine


def cadence_fixture():
    width, height = 30, 16
    cells = [(x, y) for y in range(height) for x in range(width)]
    mines = frozenset(Random(7305).sample(cells, 99))
    numbered = [c for c in cells if c not in mines and any(
        (c[0] + dx, c[1] + dy) in mines
        for dx in (-1, 0, 1) for dy in (-1, 0, 1))]
    hidden_safe = frozenset(Random(19).sample(numbered, 75))
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), mines)
    engine._revealed = [[(x, y) not in mines | hidden_safe for x in range(width)] for y in range(height)]
    anchor = next(c for c in reversed(cells) if c not in mines | hidden_safe)
    return engine, mines, hidden_safe, anchor


def run_registered_campaign(root, label, manifest):
    """Run once from a preregistered private runner, with bounded real owners."""
    import os
    if os.environ.get('MINESWEEPER_FIXED_CADENCE_REAL_OPT_IN') != 'REGISTERED_PRIVATE_RUN':
        raise RuntimeError('Use the registered fixed-cadence process runner.')
    campaign = _campaign_type()(root, label, manifest)
    campaign.run()
    return campaign.ledger


def _campaign_type():
    import json
    from pathlib import Path
    import sys
    import time
    from unittest.mock import patch
    from uuid import uuid4

    from PyQt5.QtCore import QSettings, Qt
    from PyQt5.QtTest import QTest
    from core_engine import GameStatus
    import live_k_policy as k
    from live_policy import POLICY_V1, POLICY_K_LC1
    from tests import test_live_k_lc1_process as base
    from tests.test_live_pacing_process import PacingCampaign
    from tests.test_live_pacing_clock import QpcObserver
    from ui_manager import MinesweeperUI

    class FixedCadenceCampaign(base.Campaign):
        start = PacingCampaign.start
        observe = PacingCampaign.observe

        def __init__(self, *args):
            super().__init__(*args)
            self.observer = QpcObserver()
            self.events, self.uis = [], []
            self.by_engine, self.by_run, self.context = {}, {}, {}
            self.anchors, self.clock_reads, self.proposals = {}, {}, {}
            self.seen_permits = set()
            self.auto_inputs = 0
            self.ledger.update(identity='MAIN_LIVE_FIXED_ACTION_CADENCE_2026_11_05',
                helper_sha256=base.sha(Path(__file__)), helper_recoveries_prior=0,
                helper_recoveries_remaining=0, viewing_timeout_emit_count=0,
                clocks=self.observer.metadata(), timing=self.events)
            self.save()

        def log(self, event, ui=None, **data):
            row = dict(event=event, perf_counter_ns=time.perf_counter_ns(), qpc_ticks=self.observer.read())
            if ui is not None:
                cadence = ui._fixed_cadence
                row.update(run_id=ui._live_run_id, game_id=ui._live_game_id,
                           deadline_ns=None if cadence is None else cadence.deadline_ns,
                           anchor_ns=None if cadence is None else cadence.started_ns)
            row.update(data)
            self.events.append(row)
            with (self.root/'TIMING_EVENTS.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')
            return row

        def install(self):
            super().install()
            apply = MinesweeperUI._apply_live_action
            restart = MinesweeperUI._restart_fixed_cadence
            step = MinesweeperEngine.step
            proposal = MinesweeperUI._on_v1_proposal
            admitted = MinesweeperUI._on_k_admitted
            acked = MinesweeperUI._on_v1_acknowledged
            due = MinesweeperUI._on_v1_auto_timeout
            validate = base.jobs.LivePolicyJob.validate_pending
            clock_codes = {apply.__code__: 'input', restart.__code__: 'restart'}
            previous_profile = sys.getprofile()

            def profile(frame, event, arg):
                name = clock_codes.get(frame.f_code)
                if name and arg is time.perf_counter_ns and event in ('c_call', 'c_return'):
                    key = (id(frame.f_locals['self']), name)
                    if event == 'c_call':
                        self.clock_reads[key] = dict(before_qpc=self.observer.read())
                    else:
                        self.clock_reads[key]['after_qpc'] = self.observer.read()
                        # Stop immediately after this clock call. Profiling all
                        # rendering/Qt calls would perturb the cadence measured.
                        sys.setprofile(previous_profile)
            self.stack.callback(sys.setprofile, previous_profile)

            def restarted(ui):
                sys.setprofile(profile)
                try:
                    result = restart(ui)
                finally:
                    sys.setprofile(previous_profile)
                if ui._fixed_cadence is not None:
                    self.anchors[id(ui)] = dict(self.clock_reads[(id(ui), 'restart')],
                                               anchor_ns=ui._fixed_cadence.started_ns)
                    self.log('period_restart', ui, clock_bracket=self.anchors[id(ui)])
                return result

            def applying(ui, x, y, action, **kwargs):
                self.context[id(ui.engine)] = kwargs.get('auto_observation') is not None
                sys.setprofile(profile)
                try:
                    return apply(ui, x, y, action, **kwargs)
                finally:
                    sys.setprofile(previous_profile)
                    self.context.pop(id(ui.engine), None)

            def stepped(engine, x, y, action):
                ui = self.by_engine.get(id(engine))
                automatic = self.context.get(id(engine), False)
                before = engine.get_counter_snapshot()
                cadence = ui._fixed_cadence if automatic else None
                anchor = self.anchors.get(id(ui)) if automatic else None
                input_clock_ns = sys._getframe(1).f_locals.get('input_started_ns') if automatic else None
                bracket = dict(self.clock_reads[(id(ui), 'input')]) if automatic else None
                entered = time.perf_counter_ns()
                observed = self.observer.read()
                if automatic:
                    assert sys.getprofile() is previous_profile, 'Clock probe leaked into rendering'
                    assert self.auto_inputs < self.plan['process'].get('remaining_auto_input_limit', 200), 'Total real Auto input cap'
                    assert cadence is not None and anchor is not None
                    assert anchor['anchor_ns'] == cadence.started_ns
                    assert entered >= cadence.deadline_ns, 'Input before fixed deadline'
                    lower = self.observer.ns(observed - anchor['after_qpc'])
                    minimum_gap_ns = ((cadence.period_ns * 9 + 9)//10
                                      if cadence.transition_reason == 'phase_kept' else cadence.period_ns)
                    assert lower >= minimum_gap_ns, 'Independent QPC minimum gap'
                result = step(engine, x, y, action)
                after = engine.get_counter_snapshot()
                delta = after['active_clicks'] + after['wasted_clicks'] - before['active_clicks'] - before['wasted_clicks']
                if automatic:
                    assert delta == 1, 'OPEN/FLAG/CHORD must count once'
                    self.auto_inputs += 1
                    original = self.proposals[ui._live_run_id]
                    assert (original.action, original.x, original.y) == (action.name, x, y)
                    self.log('actual_step', ui, perf_counter_ns=entered, qpc_ticks=observed,
                        token=original.token, action=action.name, target=[x, y], original_cost=original.modeled_action_us,
                        interval_ms=float(cadence.interval_ms), period_ns=cadence.period_ns, input_clock_ns=input_clock_ns,
                        target_ns=cadence.target_ns, last_actual_ns=cadence.last_actual_ns,
                        transition_reason=cadence.transition_reason, minimum_gap_ns=minimum_gap_ns,
                        input_clock_bracket=bracket, previous_anchor_bracket=anchor,
                        qpc_elapsed_lower_ns=lower, qpc_elapsed_upper_ns=self.observer.ns(observed-anchor['before_qpc']),
                        counter_delta=delta, active_clicks=after['active_clicks'], wasted_clicks=after['wasted_clicks'],
                        engine_elapsed_seconds=engine.get_elapsed_time(), auto_sequence=self.auto_inputs)
                    self.anchors[id(ui)] = dict(bracket, anchor_ns=input_clock_ns)
                elif ui is not None:
                    self.log('manual_step', ui, action=action.name, target=[x, y], counter_delta=delta)
                return result

            def proposed(ui, p):
                self.by_run[ui._live_run_id] = ui
                self.proposals[ui._live_run_id] = p
                self.log('proposal_received', ui, token=p.token, original_cost=p.modeled_action_us,
                         action=p.action, target=[p.x, p.y], compute_ns=p.compute_ns)
                return proposal(ui, p)

            def permitted(ui, permit):
                key = (permit.proposal.snapshot.run_id, permit.nonce)
                event = 'admitted_recheck' if key in self.seen_permits else 'admitted_received'
                self.seen_permits.add(key)
                self.log(event, ui, token=permit.proposal.token, nonce=permit.nonce)
                return admitted(ui, permit)

            def acknowledged(ui, ack):
                self.log('ack_received', ui, token=ack.token)
                return acked(ui, ack)

            def timed_out(ui, reservation=None):
                self.log('timer_due_callback', ui, reservation=reservation)
                return due(ui, reservation)

            def validated(job, snapshot, nonce):
                self.log('validate_entry', self.by_run[snapshot.run_id], token=job.pending.token, nonce=nonce)
                return validate(job, snapshot, nonce)

            for target, name, value in ((MinesweeperUI, '_restart_fixed_cadence', restarted),
                    (MinesweeperUI, '_apply_live_action', applying), (MinesweeperEngine, 'step', stepped),
                    (MinesweeperUI, '_on_v1_proposal', proposed), (MinesweeperUI, '_on_k_admitted', permitted),
                    (MinesweeperUI, '_on_v1_acknowledged', acknowledged),
                    (MinesweeperUI, '_on_v1_auto_timeout', timed_out),
                    (base.jobs.LivePolicyJob, 'validate_pending', validated)):
                self.stack.enter_context(patch.object(target, name, value))

        def tap(self, direction, envelope):
            # Preserve full wire evidence as append-only records, avoiding
            # rewriting the growing transcript in the measured input path.
            row = self.log('wire_'+envelope['kind'], run_id=envelope['run_id'],
                           direction=direction, sequence=envelope['seq'])
            with (self.root/'WIRE_EVENTS.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(perf_counter_ns=row['perf_counter_ns'],
                                            direction=direction, envelope=envelope))+'\n')

        def capture_traces(self, entry):
            traces=[]
            pids={r['pid'] for r in entry['owned_processes']} | {entry['launcher_pid']}
            for pid in sorted(pids):
                trace=self.root/'worker_traces'/f'{pid}.jsonl'
                if trace.exists():
                    traces.extend(json.loads(line) for line in trace.read_text('utf-8').splitlines())
            assert any(r['event']=='startup' for r in traces)
            proposals=[r for r in traces if r['event']=='proposal']
            assert proposals and len({r['token'] for r in proposals})==len(proposals)
            for validation in (r for r in traces if r['event']=='validated'):
                original=next(r for r in proposals if r['token']==validation['token'])
                assert original['counts']==validation['counts'], 'Validation repeated inference/selection'
            for actual in (r for r in self.events if r['event']=='actual_step' and r['run_id']==entry['run_id']):
                original=next(r for r in proposals if r['token']==actual['token'])
                assert (original['action'],original['target'],original['cost'])==(actual['action'],actual['target'],actual['original_cost'])
            entry['worker_trace']=traces
            entry['trace_proposals']=proposals

        def fixture(self, policy):
            engine, mines, hidden, anchor = cadence_fixture()
            settings_path=self.root/'qsettings'/(self.current_case['name']+'_'+uuid4().hex+'.ini')
            def settings(*args):
                value=QSettings(str(settings_path),QSettings.IniFormat)
                value.setFallbacksEnabled(False)
                return value
            with patch('ui_manager.QSettings',side_effect=settings):
                ui=MinesweeperUI(engine)
            self.uis.append(ui)
            self.by_engine[id(engine)]=ui
            ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
            ui.on_reset()
            # Reinstall only the declared public reveal fixture after reset.
            engine.reset_with_mines(30,16,99,mines)
            engine._revealed=[[(x,y) not in mines | hidden for x in range(30)] for y in range(16)]
            ui._reset_replay_recorder()
            ui.on_left_click(*anchor)  # Real wasted CHORD establishes public history, no timer start.
            assert engine.get_counter_snapshot()['wasted_clicks']==1
            assert engine.get_elapsed_time()==0
            assert ui._v1_supported()
            assert ui.simple_auto_interval_spin.value()==200
            ui.show()
            self.current_case['synthetic_fixture']=dict(width=30,height=16,mines=sorted(mines),
                hidden_safe=sorted(hidden),manual_prefix=list(anchor),natural_flood=False,preset_completion=False)
            return ui

        def continuous(self, policy):
            ui=self.fixture(policy)
            def limit(_record):
                if ui.live_auto_totals['auto_inputs']==60:
                    ui.simple_auto_checkbox.setChecked(False)
            ui.live_action_applied.connect(limit)
            try:
                ui.simple_auto_checkbox.setChecked(True)
                self.wait(lambda: ui.live_auto_totals['auto_inputs']>=60 or ui._live_input_uncertain
                          or ui.engine.status!=GameStatus.PLAYING, '60 uninterrupted inputs')
                assert ui.live_auto_totals['auto_inputs']==60 and not ui._live_input_uncertain
                self.wait(lambda: ui._v1_job.state=='ready' or ui._live_input_uncertain, 'last exact ACK')
                assert not ui._live_input_uncertain
                rows=[r for r in self.events if r['event']=='actual_step' and r['run_id']==ui._live_run_id]
                assert len(rows)==60
                elapsed=rows[-1]['engine_elapsed_seconds']
                counter=rows[-1]['active_clicks']+rows[-1]['wasted_clicks']
                interval_cps=(len(rows)-1)*1000000000/(rows[-1]['perf_counter_ns']-rows[0]['perf_counter_ns'])
                left_cps=counter/elapsed
                self.current_case['cps']=dict(automatic_inputs=60,counter_inputs=counter,manual_prefix_inputs=1,
                    engine_elapsed_seconds=elapsed,N_over_engine_seconds=left_cps,auto_N_over_engine_seconds=60/elapsed,
                    N_minus_one_over_last_minus_first=interval_cps,target_cps=5,tolerance_fraction=0.05,
                    acceptance_metric='N_minus_one_over_last_minus_first', tolerance_author='coordinator',
                    action_counts={a:sum(r['action']==a for r in rows) for a in ('OPEN','FLAG','CHORD')})
                assert 4.75<=interval_cps<=5.25, self.current_case['cps']
                # Detailed profiling is diagnostic. Performance acceptance
                # uses LowLoadCampaign, with the same inter-input definition.
            finally:
                ui.live_action_applied.disconnect(limit)
            self.retire_ui(ui)

        def p01_v1_continuous(self):
            self.continuous(POLICY_V1)

        def p02_lc1_continuous(self):
            self.continuous(POLICY_K_LC1)

        def p03_held_cancel_readopt(self):
            ui=self.fixture(POLICY_K_LC1)
            ui.simple_auto_interval_spin.setValue(2000)
            ui.simple_auto_checkbox.setChecked(True)
            self.wait(lambda: ui._k_deferred_permit is not None or ui._live_input_uncertain, 'unconsumed held permit')
            assert not ui._live_input_uncertain and ui.live_auto_totals['auto_inputs']==0
            old_run,old_due=ui._live_run_id,ui._fixed_cadence.deadline_ns
            cell=ui._buttons[tuple(self.current_case['synthetic_fixture']['manual_prefix'])]
            count=ui._live_action_count
            QTest.mousePress(cell,Qt.LeftButton)
            assert not ui.simple_auto_checkbox.isChecked() and ui._k_deferred_permit is None
            assert ui._live_action_count==count
            self.wait(lambda: ui._v1_job.state=='idle', 'old held-owner cleanup')
            assert self.active['ownership_cleanup_verified']
            self.wait(lambda: time.perf_counter_ns()>old_due+10000000, 'old deadline with button held')
            assert ui.live_auto_totals['auto_inputs']==0
            QTest.mouseRelease(cell,Qt.LeftButton)
            ui.simple_auto_interval_spin.setValue(200)
            def pause(_record):
                ui.simple_auto_checkbox.setChecked(False)
            ui.live_action_applied.connect(pause)
            try:
                ui.simple_auto_checkbox.setChecked(True)
                self.wait(lambda: ui.live_auto_totals['auto_inputs']==1 or ui._live_input_uncertain, 'readopt one input')
                assert ui._live_run_id!=old_run and not ui._live_input_uncertain
                self.wait(lambda: ui._v1_job.state=='ready', 'readopt ACK')
            finally:
                ui.live_action_applied.disconnect(pause)
            self.current_case['held_cancel']=dict(old_run=old_run,new_run=ui._live_run_id,
                old_auto_inputs=0,new_auto_inputs=1,old_cleanup_before_readopt=True)
            self.retire_ui(ui)

        def cleanup_all(self):
            for ui in self.uis:
                try:
                    ui.close()
                except RuntimeError:
                    pass  # Already deleted after a completed case.
            super().cleanup_all()

    return FixedCadenceCampaign
