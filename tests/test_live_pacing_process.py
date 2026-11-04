"""Opt-in, registered real Qt/IPC pacing campaign; never unittest-discovered.

Uses the accepted public singleton fixture and containment inspection helpers.
The small board/preset seam is synthetic and is not a natural flood or a game
completion. Viewing timers are always dispatched by the real Qt event loop.
"""
from dataclasses import asdict
import json
import os
from pathlib import Path
import time
import traceback
from unittest.mock import patch

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtTest import QTest

from live_pacing import MODEL_C
from live_policy import POLICY_V1, POLICY_K_LC0, POLICY_K_LC1
from tests import test_live_k_lc1_process as base
from tests.live_k_lc1_fixtures import SINGLETON_MINES, install_singleton
from tests.test_live_pacing_clock import QpcObserver
from ui_manager import MinesweeperUI


def fraction(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


class PacingCampaign(base.Campaign):
    def __init__(self, *args):
        if os.environ.get('MINESWEEPER_PACING_REAL_OPT_IN') != 'REGISTERED_PRIVATE_RUN':
            raise RuntimeError('Use the registered private-environment pacing runner.')
        super().__init__(*args)
        self.observer = QpcObserver()
        self.ledger.update(identity='MAIN_LIVE_MODEL_C_PACING_R1_FIX_2026_11_04',
                           helper_sha256=base.sha(Path(__file__)),
                           helper_recoveries_prior=0, helper_recoveries_remaining=1,
                           viewing_timeout_emit_count=0, timing=[], clocks=self.observer.metadata())
        self.last_schedule = {}
        self.save()

    def install(self):
        super().install()
        start = MinesweeperUI._start_auto_pacing
        apply = MinesweeperUI._apply_live_action
        validate = base.jobs.LivePolicyJob.validate_pending
        def scheduled(ui, cost=None):
            assert ui._pacing_clock_ns is time.perf_counter_ns
            result, observed = self.observer.capture_call(
                start.__get__(ui, type(ui)), time.perf_counter_ns, cost)
            wait = ui._pacing_wait
            assert wait is not None
            p = ui._v1_pending
            row = dict(event='schedule', run_id=ui._live_run_id, token=p.token,
                       action=p.action, target=[p.x, p.y], original_cost=cost,
                       rate=fraction(wait.rate.rate), exact_us=fraction(wait.exact_us),
                       delay_ms=wait.delay_ms, started_ns=wait.started_ns,
                       deadline_ns=wait.deadline_ns, nonce=ui._v1_timer_nonce, **observed)
            self.last_schedule[id(ui)] = row
            self.ledger['timing'].append(row)
            self.save()
            return result
        def applied(ui, x, y, action, **kwargs):
            observed_qpc = self.observer.read()
            if kwargs.get('auto_observation') is not None:
                row = self.last_schedule[id(ui)]
                now = time.perf_counter_ns()
                assert now >= row['deadline_ns'], 'Actual input before viewing deadline'
                elapsed = self.observer.elapsed(row, observed_qpc)
                assert elapsed['elapsed_lower_ns'] >= row['delay_ms'] * 1_000_000, 'Early actual input (QPC)'
                assert row['target'] == [x, y] and row['action'] == action.name
                self.ledger['timing'].append(dict(event='actual_input', run_id=ui._live_run_id,
                    token=row['token'], perf_counter_ns=now, deadline_ns=row['deadline_ns'],
                    original_cost=row['original_cost'], target=[x, y], action=action.name, **elapsed))
                self.save()
            return apply(ui, x, y, action, **kwargs)
        def validated(job, snapshot, nonce):
            observed_qpc = self.observer.read()  # True VALIDATE entry, before wire/file IO.
            now = time.perf_counter_ns()
            row = next(r for r in reversed(self.ledger['timing'])
                       if r['event'] == 'schedule' and r['run_id'] == snapshot.run_id)
            elapsed = self.observer.elapsed(row, observed_qpc)
            assert now >= row['deadline_ns'], 'VALIDATE entry before viewing deadline'
            assert elapsed['elapsed_lower_ns'] >= row['delay_ms'] * 1_000_000, 'Early VALIDATE entry (QPC)'
            self.ledger['timing'].append(dict(event='validate_entry', run_id=snapshot.run_id,
                token=row['token'], nonce=nonce, perf_counter_ns=now, **elapsed))
            self.save()
            return validate(job, snapshot, nonce)
        self.stack.enter_context(patch.object(MinesweeperUI, '_start_auto_pacing', scheduled))
        self.stack.enter_context(patch.object(MinesweeperUI, '_apply_live_action', applied))
        self.stack.enter_context(patch.object(base.jobs.LivePolicyJob, 'validate_pending', validated))

    def start(self, job, state):
        assert not self.ledger['stop_further_starts'] and self.failure is None
        assert time.monotonic() < self.deadline
        if self.active is not None:
            assert self.active.get('ownership_cleanup_verified') is True
        assert self.current_case['owner_attempts'] < self.current_case['plan']['owners']
        assert self.ledger['owner_start_attempts'] < self.plan['process']['planned_max_owner_starts']
        self.ledger['owner_start_attempts'] += 1
        self.current_case['owner_attempts'] += 1
        entry = dict(case=self.current_case['name'], run_id=state.run_id,
                     start_snapshot=asdict(state), popen_attempts=0, failed_popen_attempts=0,
                     wire=[], owned_processes=[], ownership_cleanup_verified=False)
        self.ledger['owners'].append(entry)
        self.active = entry
        self.save()
        job.finished.connect(lambda record: self.finished(job, entry, record))
        result = self.original_start(job, state)
        process, scope, directory = job._process, job._scope, job._directory
        self.handles[state.run_id] = (job, process, scope, directory)
        if process is None or scope is None:
            self.failure = 'Startup did not return owned process/scope: '+str(job._failure)
            self.ledger['stop_further_starts'] = True
            self.save()
            raise RuntimeError(self.failure)
        entry.update(launcher=dict(base.process_identity(int(process._handle), process.pid),
                                   executable=base.executable_path(int(process._handle))),
                     scope_name=scope.name, private_directory=str(directory))
        self.observe(entry)
        return result

    def observe(self, entry):
        if entry['run_id'] not in self.handles or entry.get('ownership_cleanup_verified'):
            return
        _, process, scope, _ = self.handles[entry['run_id']]
        if scope is not None and scope.handle is not None and process is not None:
            rows = base.enrich_processes(scope, process.pid)
            for row in rows:
                name = Path(row['executable']).name.lower()
                row['executable_kind'] = ('python' if name in ('python.exe', 'pythonw.exe')
                                          else 'console_host' if name == 'conhost.exe' else name)
            known = {(r['pid'], r['creation_filetime_100ns']) for r in entry['owned_processes']}
            entry['owned_processes'].extend(r for r in rows if (r['pid'], r['creation_filetime_100ns']) not in known)
            entry['last_observed_active_tree'] = scope.active_count
        self.save()

    def tap(self, direction, envelope):
        now = time.perf_counter_ns()
        super().tap(direction, envelope)
        kind = envelope['kind']
        if kind == 'VALIDATE':
            due = next(row for row in reversed(self.ledger['timing'])
                       if row['event'] == 'schedule' and row['run_id'] == envelope['run_id'])
            assert now >= due['deadline_ns'], 'VALIDATE before viewing deadline'
        self.ledger['timing'].append(dict(event='wire_'+kind, run_id=envelope['run_id'],
                                          direction=direction, perf_counter_ns=now))
        self.save()

    def capture_traces(self, entry):
        pids = {row['pid'] for row in entry['owned_processes']} | {entry['launcher_pid']}
        traces = []
        for pid in sorted(pids):
            path = self.root/'worker_traces'/f'{pid}.jsonl'
            if path.exists():
                traces.extend(json.loads(line) for line in path.read_text('utf-8').splitlines())
        entry['worker_trace'] = traces
        assert any(row['event'] == 'startup' for row in traces)
        proposals = [r for r in traces if r['event'] == 'proposal']
        assert proposals
        assert len({p['token'] for p in proposals}) == len(proposals)
        for row in (r for r in traces if r['event'] == 'validated'):
            original = next(p for p in proposals if p['token'] == row['token'])
            assert original['counts'] == row['counts'], 'Validation reselected a move'
        for row in (r for r in self.ledger['timing']
                    if r['run_id'] == entry['run_id'] and r['event'] == 'actual_input'):
            original = next(p for p in proposals if p['token'] == row['token'])
            assert (original['action'], original['target'], original['cost']) == (
                row['action'], row['target'], row['original_cost'])
        entry['trace_proposals'] = proposals

    @staticmethod
    def edit(ui, value, cps=False):
        editor = ui.pacing_cps_edit if cps else ui.pacing_rate_edit
        editor.setText(value)
        editor.setModified(True)
        editor.editingFinished.emit()

    def fixture(self, policy):
        ui = self.make_ui(6, 14, SINGLETON_MINES, policy)
        install_singleton(ui.engine)
        ui._reset_replay_recorder()
        ui.on_left_click(0, 0)  # Actual wasted CHORD after synthetic public reveals.
        ui.pacing_mode_combo.setCurrentIndex(ui.pacing_mode_combo.findData(MODEL_C))
        ui.show()
        self.start_ui(ui)
        return ui

    def wait_input(self, ui, *, manual=False):
        p = ui._v1_pending
        count = len(ui.live_action_records)
        def pause(_record):
            try:
                ui.simple_auto_checkbox.setChecked(False)
                if manual:
                    self.edit(ui, '0.25')  # While original ACK is still outstanding.
                    QTest.mousePress(ui._buttons[(0, 0)], Qt.LeftButton)
                    QTest.mouseRelease(ui._buttons[(0, 0)], Qt.LeftButton)
                    self.current_case['manual_before_ack'] = self.record_ui(ui)
            except Exception:
                self.failure = traceback.format_exc()
        ui.live_action_applied.connect(pause)
        try:
            ui.simple_auto_checkbox.setChecked(True)
            self.wait(lambda: len(ui.live_action_records) == count+1, 'real timer actual input')
            self.wait(lambda: ui._v1_expected_ack is None, 'original exact ACK')
            record = ui.live_action_records[-1]
            assert record['modeled_action_us'] == p.modeled_action_us
            assert (record['action'], record['x'], record['y']) == (p.action, p.x, p.y)
            assert ui._replay_recorder.source_type == 'algorithm'
            assert not ui._live_input_uncertain and ui._live_first_failure is None
            return record
        finally:
            ui.live_action_applied.disconnect(pause)

    def p01_v1_rates(self):
        ui = self.fixture(POLICY_V1)
        for index, rate in enumerate(('1', '0.5')):
            if index:
                ui.on_analyze_current()
                self.wait(lambda: ui._v1_pending is not None, 'next V1 proposal')
            self.edit(ui, rate)
            before = len(ui.live_action_records)
            self.wait_input(ui)
            assert len(ui.live_action_records) == before+1
        self.retire_ui(ui)

    def p02_lc1_cps_reservations(self):
        ui = self.fixture(POLICY_K_LC1)
        # Retain the historical case ID and exact rates after removing the
        # Model C reference-CPS editor. Process/permit/cleanup checks are unchanged.
        self.edit(ui, '0.50402')
        original = ui._v1_job.validate_pending
        validations = []
        def validate(snapshot, nonce):
            original(snapshot, nonce)
            validations.append(nonce)
            if len(validations) == 1:
                self.edit(ui, '0.25201')
                assert ui._k_validation_nonce is None
                self.current_case['changed_during_validate'] = True
        def pending_edit():
            try:
                self.edit(ui, '0.378015')
                self.current_case['changed_during_pending'] = True
            except Exception:
                self.failure = traceback.format_exc()
        QTimer.singleShot(30, pending_edit)
        with patch.object(ui._v1_job, 'validate_pending', validate):
            self.wait_input(ui)
        assert len(validations) == 2
        assert self.current_case['changed_during_pending']
        self.current_case['validation_nonces'] = validations
        self.retire_ui(ui)

    def p03_k_ack_manual_readopt(self):
        ui = self.fixture(POLICY_K_LC0)
        self.edit(ui, '0.5')
        old_run = ui._live_run_id
        self.wait_input(ui, manual=True)
        self.wait(lambda: ui._v1_job.state == 'idle', 'old owner cleanup before readopt')
        before = self.current_case['manual_before_ack']
        after = self.record_ui(ui)
        for key in ('revision', 'cursor', 'observation', 'events'):
            assert before[key] == after[key], 'ACK overwrote manual board/history'
        assert self.active['ownership_cleanup_verified']
        self.start_ui(ui)
        assert ui._live_run_id != old_run
        self.wait_input(ui)
        self.retire_ui(ui)


def run_registered_campaign(root, label, manifest):
    campaign = PacingCampaign(root, label, manifest)
    campaign.run()
    return campaign.ledger
