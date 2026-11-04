"""One finite campaign using production LivePolicyJob and Windows containment.

Adapted from the accepted LC0 campaign helper; this is a new LC1 campaign.
No external window control. Main is offscreen, metrics/dialogs are suppressed,
and only its tiny test instances override the UI preset gate. The product gate
is unchanged. Every production Popen attempt is counted before launch. No next
owner is allowed before the prior job proves reap/tree0/private cleanup.
"""
import copy
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from unittest.mock import patch
from uuid import uuid4

from PyQt5.QtCore import QCoreApplication, QEvent, QSettings
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from core_engine import Action, GameStatus, MinesweeperEngine
import live_k_policy as k
import live_policy_job as jobs
from live_policy import POLICY_K, POLICY_K_LC0, POLICY_K_LC1
from tests.test_live_feedback_process import process_identity, owned_processes
from tests.live_k_lc1_fixtures import SINGLETON_MINES, install_singleton, LC1_FIRST, BASELINE_FIRST
from tests.test_live_k_flag_adopt_ui import UI_MINES
from ui_manager import MinesweeperUI


ROOT = Path(__file__).resolve().parents[1]


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")


def sha(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def executable_path(handle):
    import ctypes as C
    from ctypes import wintypes as W
    api = C.WinDLL('kernel32', use_last_error=True)
    api.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
    api.QueryFullProcessImageNameW.restype = W.BOOL
    size = W.DWORD(32768)
    buffer = C.create_unicode_buffer(size.value)
    if not api.QueryFullProcessImageNameW(handle, 0, buffer, C.byref(size)):
        raise C.WinError(C.get_last_error())
    return buffer.value


def enrich_processes(scope, launcher_pid):
    import ctypes as C
    rows = owned_processes(scope, launcher_pid)
    for row in rows:
        handle = scope.api.OpenProcess(0x1000, False, row['pid'])
        if not handle:
            raise C.WinError(C.get_last_error())
        try:
            row['executable'] = executable_path(handle)
            row['executable_kind'] = 'python'
        finally:
            scope.api.CloseHandle(handle)
    return rows


def plain(value):
    return json.loads(json.dumps(value, allow_nan=False))


class Campaign:
    def __init__(self, root, run_id, manifest):
        self.root = Path(root).resolve()
        self.run_id = run_id
        self.plan = json.loads((self.root/'AUTHORIZED_EXECUTION_PLAN.json').read_text('utf-8'))
        assert self.plan['process']['enabled'] is True
        assert os.name == 'nt'
        self.path = self.root/'PROCESS_LEDGER.json'
        assert not self.path.exists(), 'Campaign already exists; preserve it, never reset budget.'
        self.started = time.monotonic()
        self.deadline = self.started + self.plan['process']['campaign_wall_cap_seconds']
        self.ledger = dict(identity='MAIN_LIVE_K_LC1_UNIT1_2026_11_04', plan_sha256=sha(self.root/'AUTHORIZED_EXECUTION_PLAN.json'),
            helper_sha256=sha(Path(__file__)), helper_pid=os.getpid(), helper_parent_pid=os.getppid(),
            started_epoch=time.time(), owner_start_attempts=0, popen_attempts=0, failed_popen_attempts=0,
            owner_starts=0, helper_recoveries_prior=1, helper_recoveries_remaining=0, stop_further_starts=False, owners=[], cases=[])
        self.current_case = self.active = None
        self.handles = {}
        self.failure = None
        self.launching = False
        self.stack = ExitStack()
        self.original_start = jobs.LivePolicyJob.start
        self.original_popen = subprocess.Popen
        self.original_read, self.original_write = jobs.read_next, jobs.write_once
        self.app = QApplication.instance() or QApplication([])
        self.save()
        dump(self.root/'logs'/ (run_id+'_SOURCE.json'), manifest())
        (self.root/'worker_traces').mkdir(exist_ok=True)
        assert not list((self.root/'worker_traces').iterdir()), 'Preserve existing worker traces'

    def save(self):
        self.ledger['elapsed_seconds'] = time.monotonic() - self.started
        dump(self.path, self.ledger)

    def install(self):
        def audit(event, args):
            if event == 'subprocess.Popen' and not self.launching:
                raise RuntimeError('Unregistered child start blocked')
            if event in ('os.system', 'os.posix_spawn', 'os.startfile'):
                raise RuntimeError('Unregistered process entry blocked')
        sys.addaudithook(audit)
        self.stack.enter_context(patch.object(jobs.subprocess, 'Popen', self.popen))
        self.stack.enter_context(patch.object(jobs.LivePolicyJob, 'start', lambda job, state: self.start(job, state)))
        self.stack.enter_context(patch.object(jobs, 'read_next', self.read))
        self.stack.enter_context(patch.object(jobs, 'write_once', self.write))
        self.stack.enter_context(patch.object(MinesweeperUI, '_ensure_zini_metric_job', return_value=None))
        for method in ('information', 'warning'):
            self.stack.enter_context(patch('ui_manager.QMessageBox.'+method, return_value=None))
        for method in ('getOpenFileName', 'getSaveFileName', 'getExistingDirectory'):
            self.stack.enter_context(patch('ui_manager.QFileDialog.'+method, side_effect=AssertionError('No dialogs authorized')))

    def popen(self, command, **kwargs):
        assert self.active is not None and not self.ledger['stop_further_starts']
        assert Path(command[0]).resolve() == Path(sys.executable).resolve()
        assert command[1:4] == ['-B', '-m', 'live_policy_worker']
        assert len(command) == 7 and command[5] == self.active['run_id']
        directory = Path(command[4]).resolve()
        assert directory.parent == (self.root/'tmp').resolve()
        assert Path(kwargs['cwd']).resolve() == ROOT.resolve()
        assert kwargs['creationflags'] & jobs.CREATE_SUSPENDED
        assert self.ledger['popen_attempts'] < self.plan['process']['total_owner_start_limit']
        for key in ('TMP', 'TEMP', 'TMPDIR'):
            assert Path(kwargs['env'][key]).resolve() == self.root/'tmp'
        kwargs['env']['MINESWEEPER_LC1_TRACE_DIRECTORY'] = str(self.root/'worker_traces')
        kwargs['env']['PYTHONPATH'] = str(Path(self.plan['process']['profile_helper_directory']).resolve())
        self.ledger['popen_attempts'] += 1
        self.active['popen_attempts'] += 1
        self.save()
        self.launching = True
        try:
            result = self.original_popen(command, **kwargs)
        except Exception:
            self.ledger['failed_popen_attempts'] += 1
            self.active['failed_popen_attempts'] += 1
            self.save()
            raise
        finally:
            self.launching = False
        self.ledger['owner_starts'] += 1
        self.active['launcher_pid'] = result.pid
        self.save()
        return result

    def start(self, job, state):
        assert not self.ledger['stop_further_starts'] and self.failure is None
        assert time.monotonic() < self.deadline
        assert self.current_case is not None
        if self.active is not None:
            assert self.active.get('ownership_cleanup_verified') is True, 'Prior owner cleanup is not established'
        assert self.current_case['owner_attempts'] < self.current_case['plan']['owners']
        assert self.ledger['owner_start_attempts'] < self.plan['process']['planned_max_owner_starts']
        assert self.ledger['owner_start_attempts'] < self.plan['process']['total_owner_start_limit']
        self.ledger['owner_start_attempts'] += 1
        self.current_case['owner_attempts'] += 1
        entry = dict(case=self.current_case['name'], run_id=state.run_id,
                     start_snapshot=k.to_dict(state), popen_attempts=0, failed_popen_attempts=0,
                     wire=[], owned_processes=[], ownership_cleanup_verified=False)
        self.ledger['owners'].append(entry)
        self.active = entry
        self.save()
        job.finished.connect(lambda record, entry=entry, job=job: self.finished(job, entry, record))
        result = self.original_start(job, state)
        process, scope, directory = job._process, job._scope, job._directory
        self.handles[state.run_id] = (job, process, scope, directory)
        if process is None or scope is None:
            self.failure = 'Startup did not return an owned process/scope: '+str(job._failure)
            self.ledger['stop_further_starts'] = True
            self.save()
            raise RuntimeError(self.failure)
        entry.update(launcher=dict(process_identity(int(process._handle), process.pid), executable=executable_path(int(process._handle))),
                     scope_name=scope.name, private_directory=str(directory))
        self.observe(entry)
        return result

    def observe(self, entry):
        if entry['run_id'] not in self.handles or entry.get('ownership_cleanup_verified'):
            return
        job, process, scope, directory = self.handles[entry['run_id']]
        if scope is not None and scope.handle is not None and process is not None:
            members = enrich_processes(scope, process.pid)
            known = {(r['pid'], r['creation_filetime_100ns']) for r in entry['owned_processes']}
            entry['owned_processes'].extend(r for r in members if (r['pid'],r['creation_filetime_100ns']) not in known)
            entry['last_observed_active_tree'] = scope.active_count
        self.save()

    def read(self, directory, direction, sequence, run_id):
        result = self.original_read(directory, direction, sequence, run_id)
        if result is not None:
            self.tap(direction, result)
        return result

    def write(self, directory, direction, sequence, envelope):
        result = self.original_write(directory, direction, sequence, envelope)
        self.tap(direction, envelope)
        return result

    def tap(self, direction, envelope):
        entry = next(e for e in self.ledger['owners'] if e['run_id'] == envelope['run_id'])
        key = (direction, envelope['seq'])
        if not any((row['direction'],row['message']['seq']) == key for row in entry['wire']):
            entry['wire'].append(dict(direction=direction, message=plain(envelope)))
            self.save()

    def finished(self, job, entry, record):
        if record.get('run_id') != entry['run_id']:
            return
        try:
            _, process, scope, directory = self.handles[entry['run_id']]
            entry['job_record'] = plain(record)
            entry['launcher_returncode'] = process.poll() if process is not None else None
            entry['private_directory_removed'] = directory is None or not directory.exists()
            entry['scope_handle_closed'] = scope is None or scope.handle is None
            clean = (record.get('reaped') is True and record.get('tree_active_count') == 0
                     and record.get('cleanup_complete') is True and entry['private_directory_removed']
                     and entry['scope_handle_closed'] and entry['launcher_returncode'] is not None
                     and job._process is None and job._scope is None and job._directory is None)
            if clean:
                process._handle.Close()
                entry['process_handle_closed'] = True
                self.capture_traces(entry)
            entry['ownership_cleanup_verified'] = clean and entry.get('process_handle_closed', False)
            if not clean:
                self.failure = 'Owned process cleanup not established: '+entry['run_id']
                self.ledger['stop_further_starts'] = True
        except Exception:
            self.failure = traceback.format_exc()
            self.ledger['stop_further_starts'] = True
        self.save()

    def capture_traces(self, entry):
        traces = []
        pids = {row['pid'] for row in entry['owned_processes']} | {entry['launcher_pid']}
        for pid in sorted(pids):
            path = self.root/'worker_traces'/f'{pid}.jsonl'
            if path.exists():
                traces.extend(json.loads(line) for line in path.read_text('utf-8').splitlines())
        entry['worker_trace'] = traces
        assert any(row.get('event') == 'startup' for row in traces), 'Missing real worker profile evidence'
        entry['trace_proposals'] = [row for row in traces if row.get('event') == 'proposal']
        entry['trace_validations'] = [row for row in traces if row.get('event') == 'validated']
        entry['trace_acknowledgements'] = [row for row in traces if row.get('event') == 'acknowledged']
        for validation in entry['trace_validations']:
            proposal = next(row for row in entry['trace_proposals'] if row['token'] == validation['token'])
            for counter in ('analyze_local', 'analyze_decision', 'select_policy',
                            'apply_singleton_band', 'apply_distance_band'):
                assert validation['counts'][counter] == proposal['counts'][counter]
        for proposal in entry['trace_proposals']:
            if proposal['kind'] == 'initial':
                assert all(count == 0 for count in proposal['counts'].values())
            if proposal['kind'] == 'guess':
                assert not proposal['assessments']

    def wait(self, condition, detail):
        while not condition():
            if self.failure:
                raise RuntimeError(self.failure)
            assert time.monotonic() < self.deadline, 'Campaign wall cap'
            assert time.monotonic() < self.case_deadline, 'Case cap: '+detail
            QTest.qWait(10)
        if self.failure:
            raise RuntimeError(self.failure)
        if self.active is not None and not self.active.get('ownership_cleanup_verified'):
            self.observe(self.active)

    def record_ui(self, ui):
        return plain(dict(game_id=ui._live_game_id, revision=ui._live_action_count,
                     cursor=ui._v1_cursor, observation=ui.engine.get_observation() if ui.engine.status==GameStatus.PLAYING else None,
                     status=ui.engine.status.name, source_type=ui._replay_recorder.source_type,
                     events=[vars(event) for event in ui._replay_recorder.events],
                     actions=ui.live_action_records, owners=ui.live_owner_records,
                     failures=ui.live_failure_records, totals=ui.live_auto_totals))

    def make_ui(self, width, height, mines, policy=POLICY_K_LC1):
        assert (width,height,len(mines)) in ((6,14,2),(5,1,3),(9,9,10))
        settings_path=self.root/'qsettings'/(self.current_case['name']+'_'+uuid4().hex+'.ini')
        def settings(*args):
            value=QSettings(str(settings_path),QSettings.IniFormat)
            value.setFallbacksEnabled(False)
            return value
        with patch('ui_manager.QSettings',side_effect=settings):
            ui=MinesweeperUI(MinesweeperEngine(width,height,len(mines)))
        # Test-only tiny geometry. Production preset domain is covered by focused tests.
        if (width,height)!=(9,9):
            ui._v1_supported=lambda: (ui.engine.width,ui.engine.height,ui.engine.num_mines)==(width,height,len(mines))
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))
        ui.on_reset()
        ui.simple_auto_interval_spin.setValue(2000)
        assert (ui.engine.width,ui.engine.height,ui.engine.num_mines)==(width,height,len(mines))
        return ui

    def start_ui(self, ui):
        ui.on_analyze_current()
        self.wait(lambda: ui._v1_job.state in ('pending','idle','blocked') and ui._v1_job.active_run_id is not None,
                  'Main proposal')
        assert ui._v1_job.state=='pending',ui._v1_job.last_record
        assert ui._v1_pending is ui._v1_job.pending
        assert not ui._live_input_uncertain
        return ui._v1_pending

    def apply_ui(self, ui, expected, manual=None):
        p=ui._v1_pending
        assert (p.action,p.x,p.y)==tuple(expected)
        count=len(ui.live_action_records)
        def pause_after_input(_record):
            try:
                ui.simple_auto_checkbox.setChecked(False)
                if manual is not None:
                    manual()
            except Exception:
                self.failure=traceback.format_exc()
        ui.live_action_applied.connect(pause_after_input)
        try:
            ui.simple_auto_checkbox.setChecked(True)
            if p.is_guess:
                ui.allow_guess_checkbox.setChecked(True)
            ui._simple_auto_timer.timeout.emit()
            self.wait(lambda: len(ui.live_action_records)==count+1,'Main actual input')
            record=ui.live_action_records[-1]
            self.wait(lambda: record['ack_state']=='ACKED' or ui._live_input_uncertain,'Main exact ACK')
            assert record['ack_state']=='ACKED' and not ui._live_input_uncertain,record
            assert record['actual_input_confirmed'] and record['policy_id']==p.snapshot.policy_id
            assert record['definition']==p.snapshot.definition and record['game_id']==p.snapshot.game_id
            event=ui._replay_recorder.events[record['event_index']]
            assert (event.action,event.x,event.y)==tuple(expected)
            assert ui._replay_recorder.source_type=='algorithm'
            return record
        finally:
            ui.live_action_applied.disconnect(pause_after_input)

    def retire_ui(self, ui):
        if ui._v1_job.active_run_id is not None:
            ui._invalidate_v1_run('campaign complete',drain_ack=True)
            self.wait(lambda: ui._v1_job.state in ('idle','blocked'),'Main owner cleanup')
        assert ui._v1_job.state=='idle',ui._v1_job.last_record
        self.current_case.setdefault('main_results',[]).append(self.record_ui(ui))
        assert ui.close() is True
        ui.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def direct_start(self, engine, prefix, entry, cursor):
        state=k.make_snapshot(run_id=uuid4().hex,game_id=uuid4().hex,board_generation=1,input_seq=0,
            width=engine.width,height=engine.height,num_mines=engine.num_mines,
            observation=engine.get_observation(),cursor=cursor,input_revision=len(prefix),
            start_input_revision=len(prefix),entry_mode=entry,policy_id=POLICY_K_LC1,
            definition=k.definition_for_entry(entry,POLICY_K_LC1),
            phase=k.PHASE_BOOTSTRAP if entry==k.FLAG_ADOPT else k.PHASE_LC1)
        job=jobs.LivePolicyJob()
        job.start(state)
        if entry==k.FLAG_ADOPT:
            self.wait(lambda: job.state in ('ready','idle','blocked'),'direct bootstrap')
            assert job.state=='ready',job.last_record
            state=k.after_bootstrap(state,job._k_bootstrap)
            job.request(state)
        self.wait(lambda: job.state in ('pending','idle','blocked'),'direct pending')
        assert job.state=='pending',job.last_record
        return job

    def direct_input(self, job, engine, expected):
        p=job.pending
        assert (p.action,p.x,p.y)==tuple(expected)
        nonce=uuid4().hex
        job.validate_pending(p.snapshot,nonce)
        self.wait(lambda: job.state in ('admitted','idle','blocked'),'direct admission')
        assert job.state=='admitted',job.last_record
        admitted=job._permit
        job.mark_applying(p.token,nonce)
        engine.step(p.x,p.y,p.move.action)
        status=engine.status
        observation=engine.get_observation() if status==GameStatus.PLAYING else None
        job.acknowledge(status.name,observation)
        ack=job._sent_ack
        self.current_case.setdefault('direct_actions',[]).append(dict(proposal=k.to_dict(p),ack=k.to_dict(ack)))
        self.wait(lambda: job.state in ('ready','idle','blocked'),'direct ACK/finish')
        assert job.state==('ready' if status==GameStatus.PLAYING else 'idle'),job.last_record
        if status!=GameStatus.PLAYING:
            assert job.last_record['status']=='SUCCEEDED'
        return k.next_snapshot(p,ack)

    def retire_direct(self,job):
        if job.active_run_id is not None:
            job.cancel('campaign complete')
            self.wait(lambda: job.state in ('idle','blocked'),'direct cleanup')
        assert job.state=='idle',job.last_record
        job.shutdown()
        job.deleteLater()

    def p01_singleton_and_actual_lc0(self):
        for policy, expected in ((POLICY_K_LC1, LC1_FIRST), (POLICY_K_LC0, BASELINE_FIRST)):
            ui = self.make_ui(6,14,SINGLETON_MINES,policy)
            # Declared synthetic public reveal state, not an Engine flood.
            # The following wasted OPEN is an actual input with real counters
            # and Replay event. No UI history predicate or native function stub.
            install_singleton(ui.engine)
            ui._reset_replay_recorder()
            ui.on_left_click(0,0)
            assert ui._known_live_history() and ui._live_action_count == 1
            p = self.start_ui(ui)
            assert p.snapshot.entry_mode == k.ADOPT_CURRENT
            assert ui._analysis_result.move == p.move
            self.apply_ui(ui,expected)
            self.retire_ui(ui)
            trace = self.active['trace_proposals']
            assert len(trace) == 1
            row = trace[0]
            assert row['counts']['analyze_decision'] == row['counts']['select_policy'] == 1
            assert row['counts']['apply_distance_band'] == 1
            assert row['counts']['apply_singleton_band'] == int(policy == POLICY_K_LC1)
            assert row['final']['action'] == expected[0] and row['final']['target'] == list(expected[1:])
            if policy == POLICY_K_LC1:
                assert row['reason'] == 'SINGLETON_BAND_OVERRIDE'
                assert row['baseline']['action'] == 'FLAG' and row['baseline']['target'] == [0,11]
                assert row['identity_bound'] is True
            assert len(self.active['trace_validations']) == len(self.active['trace_acknowledgements']) == 1
            assert self.active['trace_acknowledgements'][0]['cleared'] is True
        rows = self.current_case['main_results']
        assert rows[0]['actions'][0]['before'] == rows[1]['actions'][0]['before']
        assert rows[0]['actions'][0]['preinput_M'] == rows[1]['actions'][0]['preinput_M']
        assert rows[0]['actions'][0]['cursor_before'] == rows[1]['actions'][0]['cursor_before']
        self.current_case['synthetic_seam'] = 'Direct public reveal installation; real wasted manual prefix and Auto events. Replay event/ACK binding tested, not equivalence of synthetic initial state playback.'

    def p02_adopt_nonzero(self):
        prefix=[('OPEN',0,0)]
        engine=MinesweeperEngine(5,1,2)
        engine.reset_with_mines(5,1,2,{(1,0),(4,0)})
        engine.step(0,0,Action.OPEN)
        job=self.direct_start(engine,prefix,k.ADOPT_CURRENT,(0,0))
        self.direct_input(job,engine,('OPEN',2,0))
        self.retire_direct(job)

    def p03_mixed_flags(self):
        prefix=self.current_case['plan']['prefix']
        engine=MinesweeperEngine(5,1,2)
        engine.reset_with_mines(5,1,2,{(1,0),(4,0)})
        for action,x,y in prefix: engine.step(x,y,Action[action])
        job=self.direct_start(engine,prefix,k.FLAG_ADOPT,(4,0))
        for expected in self.current_case['plan']['expected']:
            following=self.direct_input(job,engine,expected)
            if following is not None:
                job.request(following)
                self.wait(lambda: job.state in ('pending','idle','blocked'),'next preparation/normal')
                assert job.state=='pending',job.last_record
        assert engine.status==GameStatus.WON
        record=job.last_record
        assert (record['k_preparation_input_count'],record['k_input_count'],record['k_decision_count'])==(2,1,1)
        self.retire_direct(job)

    def p04_ack_manual_readopt(self):
        with patch('core_engine.random.sample',return_value=UI_MINES):
            ui=self.make_ui(9,9,UI_MINES)
            for x,y in ((0,0),(0,1),(1,1),(2,0),(2,1)): ui.on_left_click(x,y)
            for x in (1,3,4): ui.on_right_click(x,0)
            p=self.start_ui(ui)
            old_run=p.snapshot.run_id
            record=self.apply_ui(ui,('FLAG',3,0),manual=lambda: ui.on_right_click(5,0))
            current=(ui.engine.get_observation(),ui._v1_cursor,ui._live_action_count)
            self.wait(lambda: ui._v1_job.state in ('idle','blocked'),'manual old owner cleanup')
            assert ui._v1_job.state=='idle' and not ui._live_input_uncertain
            assert (ui.engine.get_observation(),ui._v1_cursor,ui._live_action_count)==current
            assert current[1:]==((5,0),10)
            old=next(e for e in self.ledger['owners'] if e['run_id']==old_run)
            assert old['ownership_cleanup_verified'] and old['job_record']['proposal_count']==1
            ui.simple_auto_checkbox.setChecked(True)  # Explicit ON only after old cleanup.
            self.wait(lambda: ui._v1_job.state in ('pending','idle','blocked') and ui._v1_job.active_run_id is not None, 'fresh explicit ON')
            assert ui._v1_job.state == 'pending'
            fresh = ui._v1_pending
            assert fresh.snapshot.run_id!=old_run and fresh.snapshot.start_input_revision==10
            assert self.active['start_snapshot']['base_m']==[]
            self.apply_ui(ui,('FLAG',4,0))
            assert record['ack_state']=='ACKED'
            self.retire_ui(ui)

    def p05_pause_guess(self):
        mines=[(1,0),(3,0),(4,0)]
        with patch('core_engine.random.sample',return_value=mines):
            ui=self.make_ui(5,1,mines)
            self.start_ui(ui)
            self.apply_ui(ui,('OPEN',0,0))
            p=self.start_ui(ui)
            assert p.is_guess and (p.x,p.y)==(2,0)
            assert (p.probabilities.selected_mine_worlds,p.probabilities.total_worlds)==(2,3)
            run=p.snapshot.run_id
            ui.simple_auto_checkbox.setChecked(True)
            ui._simple_auto_timer.timeout.emit()
            assert ui._live_action_count==1 and ui._v1_job.pending is p
            ui.simple_auto_checkbox.setChecked(False)
            ui.simple_auto_interval_spin.setValue(500)
            ui.probability_checkbox.setChecked(False)
            ui.auto_cursor_checkbox.setChecked(False)
            ui.auto_cursor_checkbox.setChecked(True)
            assert ui._v1_job.pending is p
            ui._v1_job.validate_pending(p.snapshot,uuid4().hex)
            ui._v1_job.invalidate_admission()
            self.wait(lambda: ui._v1_job.state in ('pending','idle','blocked'),'revoked validation drain')
            assert ui._v1_job.state=='pending' and ui._live_action_count==1
            assert ui._v1_job.pending is p and ui._v1_job.active_run_id==run
            self.apply_ui(ui,('OPEN',2,0))
            self.wait(lambda: ui._v1_job.state=='idle','guess terminal cleanup')
            assert ui._v1_job.last_record['proposal_count']==2
            assert ui._v1_job.last_record['validation_count']==3
            self.retire_ui(ui)

    def p06_policy_late_negative(self):
        with patch('core_engine.random.sample',return_value=UI_MINES):
            ui=self.make_ui(9,9,UI_MINES)
            p=self.start_ui(ui)
            from dataclasses import replace
            wrong=replace(p.snapshot,policy_id=POLICY_K_LC0,definition=k.LC0_DEFINITION,phase=k.PHASE_LC0)
            before=self.ledger['popen_attempts']
            try: ui._v1_job.validate_pending(wrong,uuid4().hex)
            except ValueError as exc: self.current_case['negative_rejection']=str(exc)
            else: raise AssertionError('Other-policy validation accepted')
            ui.simple_auto_checkbox.setChecked(True)
            ui._simple_auto_timer.timeout.emit()
            nonce=ui._k_validation_nonce
            assert ui._v1_job.state=='validating'
            ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(POLICY_K_LC0))
            ui._on_k_admitted(k.KPermit(p,nonce))
            assert ui._live_action_count==0 and ui._v1_pending is None
            assert self.ledger['popen_attempts']==before
            self.wait(lambda: ui._v1_job.state in ('idle','blocked'),'policy cancelled owner cleanup')
            assert ui._v1_job.state=='idle' and not ui._live_input_uncertain
            self.retire_ui(ui)

    def cleanup_all(self):
        for entry in self.ledger['owners']:
            if entry.get('ownership_cleanup_verified') or entry['run_id'] not in self.handles:
                continue
            job,process,scope,directory=self.handles[entry['run_id']]
            try:
                job.shutdown()
                if job.last_record is not None: self.finished(job,entry,job.last_record)
            except Exception:
                entry['cleanup_exception']=traceback.format_exc()
                self.ledger['stop_further_starts']=True
        self.save()

    def run(self):
        self.install()
        try:
            for case in self.plan['process']['cases']:
                self.current_case=dict(name=case['name'],plan=case,owner_attempts=0,status='RUNNING')
                self.ledger['cases'].append(self.current_case)
                self.case_deadline=time.monotonic()+self.plan['process']['case_cap_seconds']
                self.save()
                getattr(self,case['name'])()
                assert self.current_case['owner_attempts']==case['owners']
                owners=[e for e in self.ledger['owners'] if e['case']==case['name']]
                assert all(e['ownership_cleanup_verified'] for e in owners)
                applied=sum(e['job_record']['consumed_token_count'] for e in owners)
                assert applied<=case['auto_input_cap']
                self.current_case.update(status='PASS',actual_auto_inputs=applied)
                self.save()
                print(case['name']+' PASS',flush=True)
            self.ledger['status']='PASS'
        except Exception:
            self.ledger['status']='FAIL'
            self.ledger['error']=traceback.format_exc()
            if self.current_case is not None:
                self.current_case['status']='FAIL'
            self.ledger['stop_further_starts']=True
            raise
        finally:
            self.cleanup_all()
            self.stack.close()
            self.ledger['completed_epoch']=time.time()
            self.save()


if __name__=='__main__':
    raise RuntimeError('Use the registered private-environment LC1 runner and an unused evidence root.')
