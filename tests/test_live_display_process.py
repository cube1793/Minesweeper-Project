"""Two registered display cases; reuse only read-only containment test plumbing."""
from dataclasses import asdict
from pathlib import Path
import json
import time
from unittest.mock import patch

from live_analysis import OverlayKind
from live_display_state import hidden_cells
from live_policy import POLICY_V1, POLICY_K_LC1
from tests import test_live_k_lc1_process as base
from tests.live_k_lc1_fixtures import SINGLETON_MINES, install_singleton


def probe_actions():
    from tests.test_display_stability import LiveDisplayTests
    results = {}
    for policy in (POLICY_K_LC1, POLICY_V1):
        test = LiveDisplayTests('test_pause_retains_frame_and_duplicate_overlay_skips_update')
        test.setUpClass()
        test.setUp()
        try:
            test.prepare(policy)
            actions = []
            for i in range(2):
                p = test.ui._v1_pending
                actions.append([p.action, p.x, p.y])
                test.apply(policy)
                test.job.deliver_ack()
                if i == 0:
                    test.job.compute()
            results[policy] = actions
        finally:
            test.doCleanups()
    return results


class DisplayCampaign(base.Campaign):
    def __init__(self, *args):
        super().__init__(*args)
        recoveries = json.loads((self.root/'EXECUTION_LEDGER.json').read_text('utf-8'))['helper_recoveries']
        self.ledger.update(identity='MAIN_LIVE_DISPLAY_STABILITY_2026_11_04',
                           helper_recoveries_prior=recoveries, helper_recoveries_remaining=1-recoveries,
                           helper_sha256=base.sha(Path(__file__)))
        self.save()

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
        assert len(proposals) == 2
        for i, row in enumerate(proposals, 1):
            if entry['start_snapshot']['policy_id'] == POLICY_K_LC1:
                assert all(row['counts'][key] == i for key in
                           ('analyze_decision', 'select_policy', 'apply_singleton_band', 'apply_distance_band'))
            else:
                assert row['counts']['plan_snapshot'] == i
        entry['trace_proposals'] = proposals
        for row in (r for r in traces if r['event'] == 'validated'):
            before = next(p for p in proposals if p['token'] == row['token'])
            assert before['counts'] == row['counts']

    @staticmethod
    def colors(ui):
        return {c: b.analysis_overlay.kind.value for c, b in ui._buttons.items()
                if b.analysis_overlay and b.analysis_overlay.kind in (OverlayKind.SAFE, OverlayKind.MINE)}

    def display_case(self, policy):
        ui = self.make_ui(6, 14, SINGLETON_MINES, policy)
        install_singleton(ui.engine)
        ui._reset_replay_recorder()
        ui.on_left_click(0, 0)  # Real wasted CHORD; prefix reveals above are synthetic.
        ui.analysis_checkbox.setChecked(True)
        ui.on_analyze_current()
        self.wait(lambda: ui._v1_pending is not None, 'initial normal proposal')
        samples = []
        original_render = ui._render_live_analysis
        def render():
            original_render()
            samples.append(dict(revision=ui._live_action_count, waiting=ui._analysis_result is None,
                                colors={str(c): v for c, v in self.colors(ui).items()},
                                recommendations=sum(bool(b.analysis_overlay and b.analysis_overlay.recommended)
                                                    for b in ui._buttons.values()),
                                probabilities=sum(bool(b.probability_text) for b in ui._buttons.values())))
        expected = self.current_case['plan']['expected_actions']
        with patch.object(ui, '_render_live_analysis', side_effect=render):
            for i in range(2):
                p = ui._v1_pending
                assert [p.action, p.x, p.y] == expected[i]
                old = self.colors(ui)
                assert old
                def pause(_):
                    ui.simple_auto_checkbox.setChecked(False)
                ui.live_action_applied.connect(pause)
                try:
                    ui.simple_auto_checkbox.setChecked(True)
                    ui._simple_auto_timer.timeout.emit()
                    self.wait(lambda: len(ui.live_action_records) == i+1, 'actual input')
                    self.wait(lambda: ui._v1_expected_ack is None, 'exact ACK')
                finally:
                    ui.live_action_applied.disconnect(pause)
                assert not ui._live_input_uncertain
                remaining = {c:v for c,v in old.items() if c in hidden_cells(ui.engine.get_observation())}
                assert remaining and self.colors(ui) == remaining
                assert ui._analysis_result is None
                ui.probability_checkbox.toggle()
                ui.grab()
                event = ui._replay_recorder.events[-1]
                assert [event.action,event.x,event.y] == expected[i]
                assert ui._replay_recorder.source_type == 'algorithm'
                if i == 0:
                    ui.on_analyze_current()
                    self.wait(lambda: ui._v1_pending is not None, 'fresh second proposal')
                    fresh = {c:o.kind.value for c,o in ui._analysis_result.overlays.items()
                             if o.kind in (OverlayKind.SAFE,OverlayKind.MINE)}
                    assert self.colors(ui) == fresh
        waiting = [s for s in samples if s['waiting'] and s['revision'] in (2,3)]
        assert waiting and all(s['colors'] and s['recommendations']==s['probabilities']==0 for s in waiting)
        self.current_case['display_samples'] = samples
        self.current_case['waiting_samples_without_blank'] = len(waiting)
        self.current_case['real_auto_inputs'] = len(ui.live_action_records)
        self.current_case['records'] = base.plain(ui.live_action_records)
        self.current_case['events'] = [vars(event) for event in ui._replay_recorder.events]
        self.retire_ui(ui)

    def p01_lc1_display(self):
        self.display_case(POLICY_K_LC1)

    def p02_v1_display(self):
        self.display_case(POLICY_V1)


if __name__ == '__main__':
    raise RuntimeError('Use the registered fresh-root private-environment wrapper.')
