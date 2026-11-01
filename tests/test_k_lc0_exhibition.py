"""Bounded adapters/storage/UI fixtures. No complete Expert solver is run here."""

from contextlib import redirect_stderr
from dataclasses import replace, FrozenInstanceError
from fractions import Fraction
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication

from benchmark_board import calculate_board_fingerprint
from experiments import k_lc0_exhibition_execution as execution
from experiments import k_lc0_exhibition_job as jobs
from experiments import k_lc0_exhibition_store as store
from experiments import k_lc0_exhibition_worker as worker
from experiments.k_lc0_exhibition_model import *
from experiments.k_lc0_exhibition_ui import ComparePlayer, ComparePanel, CompareWindow
from experiments.random_expert_exhibition_job import ExhibitionJob
from experiments.random_expert_exhibition_model import ExhibitionAction as A, ExhibitionFrame as F, ExhibitionBoard
from experiments.random_expert_exhibition_playback import ExhibitionPlayback, MODEL_C_MODE
from stage3_physical import action_cost, load_timing_table


def request_fixture(index=314):
    return dict(schema=SCHEMA,version=VERSION,run_id="a"*32,index=index,
                requested_at="2026-11-02T00:00:00+00:00",request_kind="index",policies=list(POLICIES))


def synthetic_pair(request=None):
    """Explicitly synthetic public linkage fixture; not an execution receipt."""
    request = request or request_fixture()
    mines = frozenset({(1,0)} | {(i%30,i//30) for i in range(382,480)})
    table = load_timing_table()
    empty = frozenset()
    m = frozenset({(1,0)})
    rows0 = tuple((HIDDEN,)*30 for _ in range(16))
    rows1 = tuple(tuple(1 if (x,y)==(0,0) else HIDDEN for x in range(30)) for y in range(16))
    rows2 = tuple(tuple(FLAGGED if (x,y)==(1,0) else rows1[y][x] for x in range(30)) for y in range(16))
    final = tuple(tuple(FLAGGED if (x,y) in mines else sum((xx,yy) in mines
                      for yy in range(max(0,y-1),min(16,y+2)) for xx in range(max(0,x-1),min(30,x+2))
                      if (xx,yy)!=(x,y)) for x in range(30)) for y in range(16))
    costs = [action_cost(table,(0,0),(0,0)),action_cost(table,(0,0),(1,0)),action_cost(table,(1,0),(0,1))]
    actions = (A(0,"OPEN",(0,0),(0,0),costs[0],"PLAYING",empty,empty,1),
               A(1,"FLAG",(1,0),(0,0),costs[1],"PLAYING",empty,m,0),
               A(2,"OPEN",(0,1),(1,0),costs[2],"WON",m,m,380))
    frames = (F(0,rows0,"PLAYING",(0,0),0,empty,empty,empty),
              F(1,rows1,"PLAYING",(0,0),costs[0],empty,empty,empty),
              F(2,rows2,"PLAYING",(1,0),sum(costs[:2]),m,m,empty),
              F(3,final,"WON",(0,1),sum(costs),m,m,mines-m))
    setup = PlanNote((("FLAG",1,0),("CHORD",0,0)),2*costs[1],1,2.0,"SETUP_CHORD")
    plan = PlanNote((("OPEN",0,1),),costs[2],1,2**.5,"SAFE_OPEN")
    choices = (ChoiceNote("INITIAL","NOT_REACHED","NOT_REACHED","POLICY_INITIAL_OPEN","INITIAL_OPEN",False,
                          ("OPEN",0,0),("OPEN",0,0),None,None),
               ChoiceNote("LOCAL_SAFE","NOT_REACHED","NOT_REACHED","SETUP_CHORD","NATIVE_G_RETAINED",False,
                          ("FLAG",1,0),("FLAG",1,0),setup,setup),
               ChoiceNote("LOCAL_SAFE","NOT_REACHED","NOT_REACHED","SAFE_OPEN","NATIVE_G_RETAINED",False,
                          ("OPEN",0,1),("OPEN",0,1),plan,plan))
    files = tuple((name,PROFILE_SHA256 if name.startswith("calibration/") else "0"*64) for name in (
        "experiments/program_k_runner.py","experiments/program_k_lc0_runner.py","experiments/program_k_lc0_policy.py",
        "experiments/k_lc0_exhibition_execution.py","calibration/stage3_physical_profile_v1.json"))
    source = CompareSource("0"*40,True,"synthetic fixture; NOT actual execution","fixture","fixture",files)
    return ComparePair(request["run_id"],request["requested_at"],request["requested_at"],request["requested_at"],
        request["request_kind"],ExhibitionBoard(request["index"],request["index"],calculate_board_fingerprint(30,16,99,mines)),
        CompareTrace("K-P0",DEFINITIONS[0],actions,frames,choices),
        CompareTrace("K-LC0",DEFINITIONS[1],actions,frames,choices),source,table)


class ExecutionTests(unittest.TestCase):
    def test_tiny_actual_pair_order_fresh_engines_table_and_effects(self):
        table = load_timing_table(); seen = []
        left,right = execution.run_k_p0,execution.run_k_lc0
        def kp(engine,**kw):
            seen.append(("K-P0",engine,kw)); return left(engine,**kw)
        def lc(engine,**kw):
            self.assertTrue(all(v == HIDDEN for row in engine.get_observation() for v in row))
            seen.append(("K-LC0",engine,kw)); return right(engine,**kw)
        mines = frozenset({(1,0)})
        with patch.object(execution,"run_k_p0",side_effect=kp),patch.object(execution,"run_k_lc0",side_effect=lc):
            traces = execution.run_layout(4,1,mines,calculate_board_fingerprint(4,1,1,mines),table)
        self.assertEqual([s[0] for s in seen],list(POLICIES))
        self.assertIsNot(seen[0][1],seen[1][1]); self.assertIs(seen[0][2]["table"],seen[1][2]["table"])
        self.assertEqual(seen[1][2],dict(table=table,control=False,capture_effects=True))
        for trace in traces:
            self.assertEqual(trace.outcome,"WON")
            self.assertEqual(len(trace.frames),len(trace.actions)+1)
            self.assertFalse(trace.frames[0].logical_mines)
            self.assertEqual(trace.actions[0].target,(0,0))

    def test_tiny_projection_includes_loss_flag_chord_and_choices(self):
        seen,outcomes = set(),set()
        for w,h,mines in ((4,1,frozenset({(1,0)})),(5,1,frozenset({(1,0),(2,0)})),(5,4,frozenset({(1,2),(3,2)}))):
            traces = execution.run_layout(w,h,mines,calculate_board_fingerprint(w,h,len(mines),mines),load_timing_table())
            for trace in traces:
                seen.update(a.action for a in trace.actions); outcomes.add(trace.outcome)
                self.assertEqual(trace.frames[-1].cumulative_modeled_us,sum(a.modeled_action_us for a in trace.actions))
                for a,f,c in zip(trace.actions,trace.frames[1:],trace.choices):
                    self.assertEqual(a.preinput_M,f.logical_mines)
                    self.assertEqual((a.action,*a.target),c.selected_move)
        self.assertEqual(seen,{"OPEN","FLAG","CHORD"}); self.assertEqual(outcomes,{"WON","LOST"})

    def test_invalid_request_rejected_before_source_generation(self):
        for index in (-1,100000,2010000,2010099,True,"314",1.5):
            with patch.object(execution,"capture_source") as source,patch.object(execution,"generate_board") as generate:
                with self.assertRaises(ValueError): execution.run_pair(request_fixture(index))
                source.assert_not_called(); generate.assert_not_called()

    def test_generation_once_and_native_failure_propagates(self):
        with patch.object(execution,"generate_board",wraps=execution.generate_board) as generate, \
             patch.object(execution,"run_layout",side_effect=RuntimeError("bounded seam")) as run:
            with self.assertRaisesRegex(RuntimeError,"bounded seam"): execution.run_pair(request_fixture())
        generate.assert_called_once_with(execution.EXPERT_GENERAL_V1,314)
        self.assertEqual(run.call_args.args[:2],(30,16)); self.assertEqual(len(run.call_args.args[2]),99)

    def test_left_failure_never_starts_right(self):
        with patch.object(execution,"run_k_p0",side_effect=RuntimeError("native fail")),patch.object(execution,"run_k_lc0") as right:
            with self.assertRaisesRegex(RuntimeError,"native fail"):
                execution.run_layout(4,1,frozenset({(1,0)}),calculate_board_fingerprint(4,1,1,{(1,0)}),load_timing_table())
        right.assert_not_called()

    def test_source_closure_includes_new_and_frozen_dependencies(self):
        source = execution.capture_source(); source.validate()
        paths = dict(source.files)
        for name in ("core_engine.py","stage3_planner.py","experiments/program_k_lc0_policy.py",
                     "experiments/k_lc0_exhibition_ui.py","experiments/random_expert_exhibition_process.py"):
            self.assertIn(name,paths)
        self.assertEqual(paths["experiments/program_k_lc0_policy.py"],"746ea59800238fbcef66aab4ea3f213dfa6aa5a07b3bf3563e227fee9a0dfe97")


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="klc0_store_test_"); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pair = synthetic_pair()
    def mutated(self,mutator):
        value = store.document(self.pair); mutator(value)
        value["sha256"] = sha256(store.canonical({k:v for k,v in value.items() if k!="sha256"})).hexdigest()
        return value
    def test_roundtrip_complete_immutable_and_no_solver_generation(self):
        request,directory = store.make_request(self.root,314)
        pair = synthetic_pair(request)
        with patch.object(execution,"run_pair",side_effect=AssertionError("solver")),patch.object(execution,"generate_board",side_effect=AssertionError("generator")):
            path = store.save_pair(directory,pair); loaded = store.load_pair(path)
        self.assertEqual(pair,loaded)
        with self.assertRaises(FrozenInstanceError): loaded.left.policy_id="V1"
    def test_repeat_index_new_run_id_and_no_overwrite(self):
        one,first = store.make_request(self.root,314); two,second = store.make_request(self.root,314)
        self.assertNotEqual(one["run_id"],two["run_id"])
        path = store.save_pair(first,synthetic_pair(one)); raw = path.read_bytes()
        with self.assertRaises(FileExistsError): store.save_pair(first,synthetic_pair(one))
        self.assertEqual(raw,path.read_bytes()); self.assertNotEqual(first,second)
    def test_json_only_duplicate_nonfinite_trailing_and_truncated_rejected(self):
        path = self.root/"bad.json"
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{}{}',b'{'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError): store.load_pair(path)
        path = self.root/"bad.pkl"; path.write_bytes(pickle.dumps(self.pair))
        with self.assertRaisesRegex(ValueError,"JSON"): store.load_pair(path)
    def test_bad_checksum_rejected(self):
        value = store.document(self.pair); value["pair"]["board"]["index"]+=1
        with self.assertRaisesRegex(ValueError,"checksum"): store.parse_document(value)
    def test_schema_version_completion_and_extra_keys_rejected(self):
        for key,value in (("schema","other"),("version",True),("version",2),("complete",False),("extra",1)):
            bad = self.mutated(lambda d:d.__setitem__(key,value))
            with self.assertRaises(ValueError): store.parse_document(bad)
    def test_board_seed_fingerprint_and_policy_swaps_rejected(self):
        mutations = [lambda d:d["pair"]["board"].__setitem__("seed",315),
                     lambda d:d["pair"]["board"].__setitem__("fingerprint","f"*64),
                     lambda d:d["pair"]["right"].__setitem__("policy_id","K-P0"),
                     lambda d:d["pair"]["right"].__setitem__("policy_id","K-LC0-CONTROL"),
                     lambda d:d["pair"]["right"].__setitem__("policy_definition","V1")]
        for mutate in mutations:
            with self.assertRaises(ValueError): store.parse_document(self.mutated(mutate))
    def test_action_frame_cost_status_ranges_and_bool_rejected(self):
        mutations = [lambda t:t["actions"][0].__setitem__("target",[30,0]),
                     lambda t:t["actions"][0].__setitem__("index",False),
                     lambda t:t["actions"][0].__setitem__("modeled_action_us",1),
                     lambda t:t["frames"][1].__setitem__("cursor",[1,0]),
                     lambda t:t["frames"][1].__setitem__("status","WON"),
                     lambda t:t["frames"].pop(),
                     lambda t:t["frames"][0]["observation"][0].__setitem__(0,True),
                     lambda t:t["actions"][2].__setitem__("safe_cells_opened_delta",1)]
        for mutate in mutations:
            with self.assertRaises(ValueError): store.parse_document(self.mutated(lambda d:mutate(d["pair"]["left"])))
    def test_M_early_commit_duplicate_outside_and_auto_flags_rejected(self):
        mutations = [lambda t:t["frames"][1].__setitem__("logical_mines",[[1,0]]),
                     lambda t:t["actions"][1].__setitem__("preinput_M",[[1,0],[1,0]]),
                     lambda t:t["actions"][1].__setitem__("preinput_M",[[30,0]]),
                     lambda t:t["frames"][1].__setitem__("automatic_flags",[[1,0]]),
                     lambda t:t["frames"][-1].__setitem__("explicit_flags",[])]
        for mutate in mutations:
            with self.assertRaises(ValueError): store.parse_document(self.mutated(lambda d:mutate(d["pair"]["right"])))
    def test_choice_metrics_first_input_reason_and_band_rejected(self):
        for key,value in (("D",100.0),("L",1),("R",0)):
            with self.assertRaises(ValueError):
                store.parse_document(self.mutated(lambda d:d["pair"]["right"]["choices"][1]["selected"].__setitem__(key,value)))
        for key,value in (("selected_move",["OPEN",0,0]),("override",True),("phase","invented"),("reason","CONTROL_NATIVE_G")):
            with self.assertRaises(ValueError):
                store.parse_document(self.mutated(lambda d:d["pair"]["right"]["choices"][1].__setitem__(key,value)))
    def test_table_source_timestamp_mismatch_rejected(self):
        mutations = [lambda d:d["pair"]["timing_table"][0].__setitem__(0,1),
                     lambda d:d["pair"]["source"].__setitem__("table_sha256","a"*64),
                     lambda d:d["pair"]["source"].__setitem__("files",[]),
                     lambda d:d["pair"].__setitem__("completed_at","2026-11-01T00:00:00+00:00")]
        for mutate in mutations:
            with self.assertRaises(ValueError): store.parse_document(self.mutated(mutate))
    def test_open_target_and_phase_reachability_are_bound(self):
        mutations = [lambda d:d["pair"]["right"]["actions"][2].__setitem__("target",[2,0]),
                     lambda d:d["pair"]["right"]["choices"][1].__setitem__("phase_d","REACHED")]
        for mutate in mutations:
            with self.assertRaises(ValueError): store.parse_document(self.mutated(mutate))
    def test_historical_source_identity_preserved_without_current_hash_gate(self):
        value = store.document(self.pair)
        self.assertEqual(store.parse_document(value).source,self.pair.source)
    def test_write_failure_is_not_success_and_partial_temp_removed(self):
        request,directory = store.make_request(self.root,314)
        with patch.object(store.os,"link",side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError): store.save_pair(directory,synthetic_pair(request))
        self.assertFalse((directory/"pair.json").exists()); self.assertEqual(list(directory.glob(".new_*")),[])
    def test_request_binding_wrong_run_index_and_kind(self):
        for key,value in (("run_id","b"*32),("index",1),("request_kind","draw")):
            request = request_fixture(); request[key]=value
            with self.assertRaises(ValueError): store.bind_request(self.pair,request)
    def test_distances_use_actual_cursor_not_plan_sum_and_win_flags_not_inputs(self):
        s = self.pair.right.summary()
        self.assertEqual(s["inputs"],3); self.assertEqual(s["flag"],1)
        self.assertEqual(s["total_distance_cells"],1+2**.5)
        self.assertEqual(len(self.pair.right.frames[-1].automatic_flags),98)
        self.assertEqual(s["long_moves_ge_8"],0)


class JobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="klc0_job_test_"); self.addCleanup(self.temp.cleanup)
        self.now=0.; self.job=jobs.CompareJob(runs_root=self.temp.name,clock=lambda:self.now)
        self.addCleanup(self.job.shutdown); self.finished=QSignalSpy(self.job.finished)
    def launch(self):
        process=Mock(); process.poll.return_value=None; process.wait.return_value=0
        with patch.object(jobs,"create_scope",return_value=None),patch.object(jobs.subprocess,"Popen",return_value=process) as popen:
            token=self.job.start(314)
        return token,process,popen
    def publish(self,**changes):
        value=dict(token=self.job._active_token,index=314,run_id=self.job.request["run_id"],policies=POLICIES,
                   pair=synthetic_pair(self.job.request),error=None)
        value.update(changes); worker.write_atomic(self.job._directory/"result.pkl",value)
    def finish(self,process):
        process.poll.return_value=0; self.job.poll()
    def test_inherits_RF_poll_cancel_drain_shutdown_and_cleanup_unmodified(self):
        for name in ("poll","cancel","_request_stop","_cleanup","_finish","shutdown"):
            self.assertIs(getattr(jobs.CompareJob,name),getattr(ExhibitionJob,name))
    def test_start_private_command_B_env_durable_request_before_child(self):
        token,process,popen=self.launch(); args=popen.call_args
        self.assertIn("experiments.k_lc0_exhibition_worker",args.args[0]); self.assertIn("-B",args.args[0])
        self.assertEqual(args.kwargs["env"]["PYTHONDONTWRITEBYTECODE"],"1")
        self.assertTrue((self.job.run_directory/"request.json").exists())
        self.assertEqual(pickle.loads((self.job._directory/"request.pkl").read_bytes()),dict(token=token,request=self.job.request))
    def test_success_after_cleanup_only(self):
        _,process,_=self.launch(); directory=self.job._directory; self.publish(); self.finish(process)
        self.assertEqual(self.finished[0][1],"SUCCEEDED"); self.assertFalse(directory.exists())
        self.assertTrue(self.job.last_record["reaped"] and self.job.last_record["cleanup_complete"])
    def test_token_index_run_policy_and_pair_identity_rejected(self):
        self.launch()
        for changes in (dict(token=True),dict(token=9),dict(index=1),dict(run_id="b"*32),dict(policies=("V1","K-LC0")),
                        dict(pair=synthetic_pair()),dict(pair=None,error=None)):
            self.publish(**changes)
            with self.assertRaises(ValueError): self.job._read_result()
    def test_startup_failure_returns_token_then_propagates(self):
        with patch.object(jobs,"create_scope",side_effect=OSError("scope root cause")),redirect_stderr(io.StringIO()) as err:
            token=self.job.start(314)
        self.assertEqual(token,1); self.assertFalse(self.finished)
        self.job.poll(); self.assertEqual(self.finished[0][1],"FAILED")
        self.assertIn("scope root cause",self.job.last_record["error"]); self.assertIn("scope root cause",err.getvalue())
    def test_cancel_precedes_completed_result(self):
        _,process,_=self.launch(); self.publish(); self.job.cancel(); self.finish(process)
        self.assertEqual(self.finished[0][1],"CANCELLED")
    def test_timeout_precedes_result_and_drain(self):
        _,process,_=self.launch(); self.publish(); self.now=120; self.finish(process)
        self.assertEqual(self.finished[0][1],"TIMEOUT")
    def test_fixed_exit_drain_deadline_and_no_poll_sleep(self):
        _,process,_=self.launch(); self.publish(); scope=Mock(active_count=1); self.job._scope=scope
        self.finish(process); deadline=self.job._exit_drain_deadline; self.assertEqual(deadline,.75)
        self.now=.74; self.job.poll(); self.assertEqual(self.job._exit_drain_deadline,deadline)
        self.assertFalse(self.finished); scope.active_count=0; self.job.poll()
        self.assertEqual(self.finished[0][1],"SUCCEEDED")
    def test_progress_wrong_identity_ignored_and_oserror_advisory(self):
        self.launch()
        value=dict(token=1,index=314,run_id="b"*32,policies=POLICIES,phase="K_LC0_RUNNING")
        worker.write_atomic(self.job._directory/"progress.json",value,json_text=True); self.job._read_progress()
        self.assertIsNone(self.job._phase)
        with patch.object(jobs.json,"loads",side_effect=OSError("sharing")): self.job._read_progress()
        self.assertIsNone(self.job._failure)
    def test_cleanup_failure_blocks_next_request(self):
        _,process,_=self.launch(); self.publish()
        with patch.object(self.job,"_cleanup",side_effect=OSError("cleanup denied")): self.finish(process)
        self.assertEqual(self.job.state,"blocked")
        with self.assertRaises(RuntimeError): self.job.start(2718)

    def sleeper(self):
        fixture=Path(__file__).with_name("fixtures")/"k_lc0_exhibition_worker.py"
        def command(payload,result,progress,scope): return [sys.executable,"-B",str(fixture),str(payload),str(result),str(progress),scope]
        with patch.object(jobs,"build_worker_command",side_effect=command): self.job.start(314)
        process,directory=self.job._process,self.job._directory
        deadline=time.monotonic()+5
        while not (directory/"ready.json").exists() and time.monotonic()<deadline: QTest.qWait(10)
        self.assertTrue((directory/"ready.json").exists())
        self.assertGreater(self.job._scope.active_count,0)
        return process,directory
    def stopped(self,process,directory):
        deadline=time.monotonic()+5
        while not self.finished and time.monotonic()<deadline: self.job.poll(); QTest.qWait(10)
        self.assertTrue(self.finished); self.assertIsNotNone(process.poll()); self.assertFalse(directory.exists())
        self.assertEqual(self.job.last_record["tree_active_count"],0)
        self.assertTrue(self.job.last_record["cleanup_complete"])
    def test_real_contained_fixture_cancel_reaps_tree(self):
        process,directory=self.sleeper(); self.job.cancel(); self.stopped(process,directory)
        self.assertEqual(self.finished[0][1],"CANCELLED")
    def test_real_contained_fixture_timeout_reaps_tree(self):
        process,directory=self.sleeper(); self.now=120; self.stopped(process,directory)
        self.assertEqual(self.finished[0][1],"TIMEOUT")
    def test_real_contained_fixture_close_reaps_tree(self):
        process,directory=self.sleeper(); self.job.shutdown()
        self.assertFalse(self.finished); self.assertIsNotNone(process.poll()); self.assertFalse(directory.exists())
        self.assertEqual(self.job.last_record["tree_active_count"],0)
    def test_real_new_worker_rejects_invalid_token_without_algorithm_start(self):
        original=jobs.build_worker_command
        def command(payload,result,progress,scope):
            value=pickle.loads(Path(payload).read_bytes()); value["token"]=0
            Path(payload).write_bytes(pickle.dumps(value))
            return original(payload,result,progress,scope)
        with patch.object(jobs,"build_worker_command",side_effect=command): self.job.start(314)
        self.stopped(self.job._process,self.job._directory)
        self.assertEqual(self.finished[0][1],"FAILED")
        self.assertIn("token",self.job.last_record["error"])
    def test_real_new_worker_tokenless_scope_cause_reaches_parent_stderr(self):
        original=jobs.build_worker_command
        def command(payload,result,progress,scope): return original(payload,result,progress,scope+"_missing")
        with patch.object(jobs,"build_worker_command",side_effect=command): self.job.start(314)
        self.stopped(self.job._process,self.job._directory)
        self.assertEqual(self.finished[0][1],"FAILED")
        self.assertIn("REQUEST_TRANSPORT",self.job.last_record["stderr"])
        self.assertIn("FileNotFoundError",self.job.last_record["stderr"])


class WorkerTests(unittest.TestCase):
    def test_progress_oserror_best_effort_but_final_pair_strict(self):
        pair=synthetic_pair()
        def run(request,*,progress):
            progress("K_P0_RUNNING",None); progress("K_LC0_RUNNING",pair.left.summary()); return pair
        with patch.object(worker,"write_atomic",side_effect=OSError("progress denied")),patch.object(execution,"run_pair",side_effect=run):
            result=worker.calculate(dict(token=1,request=request_fixture()),"unused")
        self.assertEqual(result["pair"],pair); self.assertIsNone(result["error"])
    def test_native_failure_has_phase_and_no_partial_pair(self):
        def run(request,*,progress):
            progress("K_LC0_RUNNING",dict(policy="K-P0")); raise RuntimeError("right failed")
        with patch.object(execution,"run_pair",side_effect=run): result=worker.calculate(dict(token=1,request=request_fixture()))
        self.assertIsNone(result["pair"]); self.assertIn("K_LC0_RUNNING",result["error"]); self.assertIn("right failed",result["error"])
    def test_invalid_payload_never_calls_runner(self):
        with patch.object(execution,"run_pair") as run:
            for payload in (None,{},dict(token=True,request=request_fixture()),dict(token=1,request=request_fixture(100000))):
                self.assertIsNotNone(worker.calculate(payload)["error"])
        run.assert_not_called()
    def test_pre_token_scope_and_transport_root_cause_in_stderr(self):
        with tempfile.TemporaryDirectory(prefix="klc0_scope_test_") as directory:
            paths=[str(Path(directory)/s) for s in ("request.pkl","result.pkl","progress.json")]+["bad"]
            for error in (OSError("scope missing"),None):
                stderr=io.StringIO()
                with patch.object(worker,"verify_worker_scope",side_effect=error),redirect_stderr(stderr):
                    self.assertEqual(worker.main(paths),0)
                self.assertIn("REQUEST_TRANSPORT",stderr.getvalue())
                self.assertIn("scope missing" if error else "FileNotFoundError",stderr.getvalue())
                self.assertIsNone(pickle.loads(Path(paths[1]).read_bytes())["token"])
    def test_final_write_failure_is_nonzero(self):
        with patch.object(worker,"verify_worker_scope",side_effect=OSError("fixture")), \
             patch.object(worker,"write_atomic",side_effect=OSError("final denied")),redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(worker.main(["a","b","c","d"]),1)
        self.assertIn("final denied",stderr.getvalue())


class PlaybackUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="klc0_ui_test_"); self.addCleanup(self.temp.cleanup)
        self.window=CompareWindow(runs_root=self.temp.name); self.addCleanup(self.window.close)
        self.pair=synthetic_pair(); self.window.show(); QApplication.processEvents()
    def install(self): self.window.install(self.pair,historical=True)
    def test_startup_never_executes_and_explicit_button_reaches_new_job(self):
        self.assertIsNone(self.window.pair); self.assertEqual(self.window.job.records,[])
        process=Mock(); process.poll.return_value=None; process.wait.return_value=0
        with patch.object(jobs,"create_scope",return_value=None),patch.object(jobs.subprocess,"Popen",return_value=process) as popen:
            QTest.mouseClick(self.window.run_button,Qt.LeftButton)
        self.assertIn("experiments.k_lc0_exhibition_worker",popen.call_args.args[0])
        self.assertTrue(self.window._busy); self.assertIsNone(self.window.pair)
    def test_draw_one_uniform_inclusive_public_range_and_duplicates_retained(self):
        with patch("experiments.k_lc0_exhibition_ui.secrets.randbelow",return_value=314) as draw,patch.object(self.window,"run_index") as run:
            QTest.mouseClick(self.window.draw_button,Qt.LeftButton)
        draw.assert_called_once_with(100000); run.assert_called_once_with(314,kind="draw")
    def test_actual_policy_labels_and_next_input_does_not_change_identity(self):
        self.install(); original=self.window.identity.text(); self.window.index_edit.setText("8191")
        self.assertEqual(original,self.window.identity.text()); self.assertIn("K-LC0",self.window.right.title())
        self.assertIn("K-P0",self.window.left.title()); self.assertIn("당시 source",original)
    def test_new_request_clears_previous_pair_failure_never_installs_old_success(self):
        self.install()
        with patch.object(jobs,"create_scope",side_effect=OSError("no scope")),redirect_stderr(io.StringIO()): self.window.run_index(2718)
        self.assertIsNone(self.window.pair); self.window.job.poll()
        self.assertIsNone(self.window.pair); self.assertIn("미완료",self.window.status.text()); self.assertIn("없음",self.window.storage.text())
    def test_cancel_stale_success_not_installed(self):
        self.window._active_token=2; self.window._accept_result=False
        self.window.completed(1,"SUCCEEDED",self.pair); self.assertEqual(self.window._active_token,2)
        self.window.completed(2,"SUCCEEDED",self.pair); self.assertIsNone(self.window.pair)
        self.assertIn("CANCELLED",self.window.status.text()); self.assertNotIn("SUCCEEDED",self.window.status.text())
    def test_open_roundtrip_without_generation_and_invalid_open_preserves_display(self):
        request,directory=store.make_request(self.temp.name,314); pair=synthetic_pair(request); path=store.save_pair(directory,pair)
        with patch.object(execution,"run_pair",side_effect=AssertionError("solver")):
            self.assertTrue(self.window.open_record(path))
            self.window.left.seek(1); self.window.reset_all()
        self.assertEqual(self.window.pair,pair)
        bad=Path(self.temp.name)/"bad.json"; bad.write_text("{}")
        self.assertFalse(self.window.open_record(bad)); self.assertEqual(self.window.pair,pair)
        self.assertIn("거부",self.window.status.text())
    def test_save_failure_visible_and_distinct_from_cleanup(self):
        self.window._active_token=1; self.window._accept_result=True
        with patch("experiments.k_lc0_exhibition_ui.save_pair",side_effect=OSError("disk full")):
            self.window.completed(1,"SUCCEEDED",self.pair)
        self.assertEqual(self.window.pair,self.pair); self.assertIn("저장 실패",self.window.storage.text())
        self.assertIn("미저장",self.window.status.text()); self.assertIsNone(self.window.saved_path)
    def test_M_observation_route_cost_commit_only_at_completion(self):
        trace=self.pair.right; player=ComparePlayer(trace); now=[0]
        playback=ExhibitionPlayback(player,clock=lambda:now[0]); playback.seek(1); before=player.current_frame
        playback.play(); now[0]=249_999_999; playback.update()
        self.assertIs(player.current_frame,before); self.assertFalse(player.current_frame.logical_mines)
        self.assertEqual(player.completed_route,((0,0),)); self.assertNotEqual(playback.cursor,before.cursor)
        now[0]=250_000_000; playback.update(); self.assertEqual(player.current_frame.logical_mines,frozenset({(1,0)}))
        self.assertEqual(player.current_index,2)
    def test_common_commands_preserve_independent_positions_rates_and_no_wrap(self):
        self.install(); left,right=self.window.left,self.window.right
        left.seek(1); right.seek(2); left.change_interval(500); right.change_cps(3)
        self.window.play_all(); self.window.pause_all()
        self.assertEqual((left.player.current_index,right.player.current_index),(1,2))
        self.window.reset_all(); self.assertEqual((left.player.current_index,right.player.current_index),(0,0))
        self.assertEqual(left.playback.interval_ms,500); self.assertEqual(right.playback.interval_ms,Fraction(1000,3))
        left.seek(3); self.window.play_all(); self.assertEqual(left.player.current_index,3)
    def test_model_C_half_speed_clock_and_cost_are_exact(self):
        player=ComparePlayer(self.pair.right); now=[0]; playback=ExhibitionPlayback(player,clock=lambda:now[0])
        playback.set_mode(MODEL_C_MODE); playback.set_speed(Fraction(1,2)); playback.play()
        cost=self.pair.right.actions[0].modeled_action_us; now[0]=cost*2000-1; playback.update()
        self.assertEqual(player.current_index,0); now[0]+=1; playback.update()
        self.assertEqual(player.current_index,1); self.assertEqual(player.current_frame.cumulative_modeled_us,cost)
    def test_seek_and_keyboard_are_independent_and_discard_partial(self):
        self.install(); left,right=self.window.left,self.window.right
        left.play(); left.seek(2); self.assertFalse(left.playback.running); self.assertEqual(left.playback.partial_modeled_us,0)
        QTest.keyClick(left.slider,Qt.Key_End); self.assertEqual(left.player.current_index,3); self.assertEqual(right.player.current_index,0)
        QTest.keyClick(left.slider,Qt.Key_Home); self.assertEqual(left.player.current_index,0)
        with self.assertRaises(ValueError): left.seek(4)
        self.assertEqual(left.player.current_index,0)
    def test_small_and_maximized_layout_keep_controls_and_scroll(self):
        self.install()
        for w,h in ((900,760),(1920,1000)):
            self.window.resize(w,h); QApplication.processEvents()
            for panel in (self.window.left,self.window.right):
                self.assertGreaterEqual(panel.scroll.viewport().height(),120)
                self.assertTrue(panel.play_button.isVisible()); self.assertTrue(panel.slider.isVisible())
                if w==900: self.assertGreater(panel.scroll.horizontalScrollBar().maximum(),0)
    def test_LOST_time_to_win_is_NA_and_close_stops_timers(self):
        trace=self.pair.right
        self.assertEqual(self.pair.time_to_win_difference_us,0)
        # A tiny genuine lost trace exercises the metric independently of Expert fixture.
        w,h,mines=5,1,frozenset({(1,0),(2,0)})
        left,right=execution.run_layout(w,h,mines,calculate_board_fingerprint(w,h,len(mines),mines),load_timing_table())
        fake=Mock(left=left,right=right)
        self.assertIsNone(ComparePair.time_to_win_difference_us.fget(fake))
        self.install(); self.window.play_all(); self.window.close()
        self.assertFalse(self.window.left.timer.isActive()); self.assertFalse(self.window.right.timer.isActive())


if __name__ == "__main__": unittest.main()
