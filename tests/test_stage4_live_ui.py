"""Main/Replay integration. Fake jobs and archived DTO injections are CONTROLLED."""
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt,QTimer
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from core_engine import MinesweeperEngine,GameStatus,Action
from ui_manager import MinesweeperUI
from stage4_live_job import Stage4LiveJob
from stage4_live_contract import Snapshot,Settings,digest
from stage4_live_worker import Session
from stage4_runtime_policy import RuntimeHistory,RuntimeResult,POLICY_ID
from stage4_runtime_model import RuntimeUsage
from replay_json import save_replay_json,load_replay_json
from replay_player import ReplayPlayer
from tests.ui_settings import isolate_ui_settings
from tests.test_stage4_live_worker import pump

AUDIT=lambda *args:None
# Archived Unit29 G01/M final decision SHA256 b19d8820b5f1fcc9e73ae7ccff9227bd500f422bf6c29dfd69e35da17352f51e
ARCHIVED_LIMIT=json.loads(r'''{"request":{"observation":[[1,1,0,0,0,0,1,-2,1,0,1,-2,1,1,-2,-2,2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,1],[-2,2,0,0,0,0,1,1,2,1,2,-2,1,1,3,3,3,-2,2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2],[-3,2,1,1,1,1,1,1,1,-2,2,1,1,0,2,-2,3,1,1,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2],[1,1,1,-2,2,3,-3,3,3,3,3,-2,2,1,4,-2,-2,-2,1,1,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2],[0,0,1,2,-2,4,-2,4,-2,-2,3,-2,3,-2,4,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2],[0,1,1,2,2,-2,3,5,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,2,1,2,-2,4,-2,-2,-2,-2],[0,1,-3,1,1,1,2,-2,-2,4,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,1,0,1,2,3,-2,-2,-2,-2],[0,2,3,3,1,0,2,3,4,-2,2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,2,1,0,1,-2,3,-2,-2,-2],[0,1,-2,-3,2,1,3,-2,3,2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,3,1,2,1,2,2,3,2],[0,2,3,3,3,-2,4,-2,3,2,-2,-2,1,-2,-2,-2,-2,-2,-2,-2,3,-3,4,-3,3,1,0,0,1,-2],[1,2,-3,1,2,-3,4,2,3,-2,2,1,1,-2,-2,-2,-2,-2,-2,-2,2,1,4,-3,-2,1,0,1,3,-2],[-2,-2,2,1,1,1,3,-2,3,1,1,0,1,-2,-2,-2,-2,-2,-2,-2,2,1,2,-3,3,1,0,1,-2,-2],[-2,-2,3,1,1,0,3,-2,3,0,0,0,1,-2,-2,-2,-2,-2,-2,-2,-2,2,2,1,2,1,1,1,2,2],[-2,-2,3,-2,1,0,2,-3,2,1,2,3,3,-2,-2,-2,-2,-2,-2,-2,3,-3,1,0,1,-3,1,0,0,0],[-2,-2,3,2,2,1,1,1,1,1,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,2,1,1,2,2,1,0,0,0],[-2,-2,1,1,-2,1,0,0,0,1,2,3,3,-2,-2,-2,-2,-2,-2,-2,-2,1,0,1,-2,1,0,0,0,0]],"num_mines":99,"counted_inputs":105,"mode":"M","allow_guess":true,"target":null},"result":{"policy_id":"UNCONNECTED_RUNTIME_SMR_V1","request_id":"68429de74acfc9bcfcc855dbc59593d07c20acd4d08d03128df94294c5e4a273","status":"RESOURCE_LIMIT","reason":"F_BLOCKED:Q_BASE_WORK_LIMIT","sequence":[],"decision_source":null,"model_status":"SKIPPED","model_attempted":false,"model_attempts_used":7,"usage":{"kernel_calls":1,"kernel_work":99906,"q_calls":1,"q_local":2871,"unit10_calls":1,"unit10_units":199998,"unit4_calls":0,"unit4_work":0,"sampler_work":0,"f_lookups":0,"f_misses":0,"f_hits":0,"cache_peak":0,"virtual_inputs":0,"started_rows":0,"accounting_complete":true},"proposal_id":null,"session_id":"301bd7d71368458f878a2200cf75c975","settings_fingerprint":"990e5b260d9ff570a53f1e1f02062c6ef0ed63583fc0efbd0ad7ea0509b59fb2","expires_at":1291435.6934358,"elapsed_seconds":0.10866339993663132,"error":null,"model":null,"followup":{"stream":"runtime_calls.jsonl.gz","record_id":"92:F:0","field":"result"}}}''')


class ControlledJob(Stage4LiveJob):
    """No subprocess and no policy evaluation; actual Main handlers remain active."""
    def __init__(self,parent=None):
        super().__init__(parent);self.starts=0
    def start(self,state,history=None):
        self.starts+=1;self._start_snapshot=self._expected_snapshot=state
        self._active_run_id=state.run_id;self.history=history or RuntimeHistory();self.state="computing"
        return state.run_id
    def cancel(self,reason="CANCELLED"):
        if self._active_run_id is None:return
        record=dict(run_id=self._active_run_id,policy_id="STAGE4_LIVE_SMR_V1",status="CANCELLED",error=None,
                    reaped=True,tree_active_count=0,cleanup_complete=True,history=self.history.to_payload())
        self._active_run_id=None;self._pending=None;self.state="idle";self.last_record=record
        self.records.append(record);self.finished.emit(record)
    def shutdown(self):
        self.cancel("CLOSED");self.state="closed"
    def deliver_stop(self,status,reason,model_status="SKIPPED"):
        state=self._expected_snapshot
        def choose(request):
            return RuntimeResult(POLICY_ID,request.identity,status,reason,(),None,model_status,False,
                self.history.attempts,None,None,RuntimeUsage(),None,"controlled-session",request.settings_fingerprint,1000.,0.)
        policy=SimpleNamespace(choose=choose,attempts_used=self.history.attempts,close=lambda:None)
        session=Session(state,self.history,lambda h:None,policy=policy)
        self._pending=session.propose(state);self.state="pending"
        self.proposal_ready.emit(self._pending)


class UIBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        isolate_ui_settings(self);self.uis=[]
        zini=patch.object(MinesweeperUI,"_ensure_zini_metric_job");zini.start();self.addCleanup(zini.stop)
        self.addCleanup(self.close_all)
    def close_all(self):
        for ui in self.uis:
            ui.close();ui.deleteLater()
        self.app.processEvents()
    def make_ui(self,*,fake=True,width=9,height=9,mines=10):
        if fake:
            with patch("stage4_live_ui.Stage4LiveJob",ControlledJob):ui=MinesweeperUI(MinesweeperEngine(width,height,mines))
        else:ui=MinesweeperUI(MinesweeperEngine(width,height,mines))
        self.uis.append(ui);ui.show();self.app.processEvents();return ui
    def select(self,ui,policy="STAGE4_M"):
        ui.live_policy_combo.setCurrentIndex(ui.live_policy_combo.findData(policy))


class ControlledUITests(UIBase):
    def test_display_off_cleanup_reason_and_stale_owner_callbacks(self):
        from stage4_live_contract import Acknowledgement
        ui=self.make_ui();self.select(ui)
        ui.analysis_checkbox.setChecked(True);ui.simple_auto_checkbox.setChecked(True)
        state=ui._stage4.job._start_snapshot
        ui._stage4.on_finished(dict(run_id="old-run",cleanup_complete=False,error="old"))
        ui._stage4.on_ack(Acknowledgement("old-run","a"*64,"old",state.identity,state))
        self.assertFalse(ui._stage4.retired);self.assertIsNone(ui._stage4.last_error)
        ui.analysis_checkbox.setChecked(False)
        self.assertTrue(ui._stage4.retired);self.assertFalse(ui.simple_auto_checkbox.isChecked())
        ui._stage4.job.state="blocked";ui._stage4.last_error="CONTROLLED_CLEANUP_DENIED"
        ui.live_policy_combo.setCurrentIndex(0)
        self.assertIn("CONTROLLED_CLEANUP_DENIED",ui.live_policy_status_label.text())
        self.assertFalse(ui.simple_auto_checkbox.isEnabled())
        ui._stage4.job.state="idle";self.select(ui)
        with patch.object(ui._stage4.job,"shutdown",side_effect=RuntimeError("CONTROLLED_CLOSE_DENIED")):
            self.assertFalse(ui.close())
            self.assertIn("CONTROLLED_CLOSE_DENIED",ui.live_policy_status_label.text())

    def test_real_controls_target_profiles_unsupported_boards_and_manual_press(self):
        ui=self.make_ui();self.select(ui,"STAGE4_R")
        for invalid in ("","0","-1","NaN"):
            ui.stage4_target_edit.setText(invalid);ui.simple_auto_checkbox.setChecked(True)
            self.assertFalse(ui.simple_auto_checkbox.isChecked());self.assertEqual(ui._stage4.job.starts,0)
        ui.stage4_target_edit.setText("120");ui.stage4_profile_combo.setCurrentIndex(1)
        ui.allow_guess_checkbox.setChecked(True);ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(ui._stage4.job._start_snapshot.settings,Settings("R","indexed_k100k",True,Fraction(6,5)))
        count=ui._live_action_count
        QTest.mousePress(ui._buttons[(0,0)],Qt.LeftButton)
        self.assertTrue(ui._stage4.retired);self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertEqual(ui._live_action_count,count)
        QTest.mouseRelease(ui._buttons[(0,0)],Qt.LeftButton)
        self.assertEqual(ui._live_action_count,count+1)
        ui._rebuild_game(31,16,99);ui.simple_auto_checkbox.setChecked(True)
        self.assertFalse(ui.simple_auto_checkbox.isChecked());self.assertIn("480",ui.live_policy_status_label.text())
        ui._rebuild_game(15,15,20);ui.simple_auto_checkbox.setChecked(True)
        self.assertFalse(ui.simple_auto_checkbox.isChecked());self.assertIn("preset",ui.live_policy_status_label.text())

    def test_typed_stop_reasons_no_input_latch_and_explicit_settings_release(self):
        ui=self.make_ui();self.select(ui);ui.on_left_click(0,0)
        job=ui._stage4.job
        cases=(("RESOURCE_LIMIT","F_BLOCKED:Q_BASE_WORK_LIMIT"),("RESOURCE_LIMIT","F_TIME_RESERVATION"),
               ("RESOURCE_LIMIT","REQUEST_ALREADY_DECIDED_NO_NEW_QUOTA"),("BUSY","ANOTHER_DECISION_ACTIVE"),
               ("CANCELLED","CANCELLED"),("ERROR","MODEL_BLOCKED:CONTRADICTION"),
               ("NO_INFORMATION","GUESS_BLOCKED"),("RESOURCE_LIMIT","PARENT_EXPIRED"))
        for status,reason in cases:
            ui.stage4_profile_combo.setCurrentIndex(1-ui.stage4_profile_combo.currentIndex())
            ui.simple_auto_checkbox.setChecked(True)
            before=(ui._live_action_count,tuple(ui._replay_recorder.events),ui.engine.status)
            job.deliver_stop(status,reason,"TIME_LIMIT" if reason=="F_TIME_RESERVATION" else "SKIPPED")
            self.assertFalse(ui.simple_auto_checkbox.isChecked())
            self.assertEqual((ui._live_action_count,tuple(ui._replay_recorder.events),ui.engine.status),before)
            self.assertIn(reason,ui.live_policy_status_label.text())
            if status=="RESOURCE_LIMIT":
                calls=job.starts;ui.simple_auto_checkbox.setChecked(True)
                self.assertEqual(job.starts,calls);self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertEqual(ui.engine.status,GameStatus.PLAYING)
        ui.stage4_profile_combo.setCurrentIndex(1-ui.stage4_profile_combo.currentIndex())
        calls=job.starts;ui.simple_auto_checkbox.setChecked(True);self.assertEqual(job.starts,calls+1)

    def test_archived_unit29_q_limit_caller_no_retry(self):
        self.assertIsNotNone(ARCHIVED_LIMIT,"Registered Unit29 public DTO fixture must be supplied by evidence runner")
        ui=self.make_ui(width=30,height=16,mines=99);self.select(ui)
        req=ARCHIVED_LIMIT["request"];res=ARCHIVED_LIMIT["result"]
        self.assertEqual((res["status"],res["reason"]),("RESOURCE_LIMIT","F_BLOCKED:Q_BASE_WORK_LIMIT"))
        ui.stage4_profile_combo.setCurrentIndex(1);ui.allow_guess_checkbox.setChecked(True)
        # Explicit archived public-state injection, not an engine reconstruction,
        # policy rerun or support-check bypass. Main's actual board is untouched.
        def archived_snapshot(**_kwargs):
            return Snapshot(ui._live_game_id,ui._stage4.owner_id,ui._live_run_id,ui._live_board_generation,
                ui._stage4.settings(),tuple(tuple(r) for r in req["observation"]),30,16,99,105,105,105,
                digest(["Unit29","G01","M",105]),(0,0))
        before=ui.engine.get_observation();events=ui._replay_recorder.events
        with patch.object(ui._stage4,"snapshot",side_effect=archived_snapshot):
            ui.simple_auto_checkbox.setChecked(True)
            ui._stage4.job.deliver_stop(res["status"],res["reason"])
            starts=ui._stage4.job.starts
            ui.simple_auto_checkbox.setChecked(True)
            self.assertEqual(ui._stage4.job.starts,starts)
            self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertEqual(ui.engine.get_observation(),before);self.assertEqual(ui._replay_recorder.events,events)
        self.assertEqual(ui.engine.status,GameStatus.PLAYING)
        AUDIT("archived_unit29_limit",dict(classification="CONTROLLED_ARCHIVED_PUBLIC_DTO",original_request=req,
            original_result=res,additional_engine_inputs=0,retry_starts=0,status=ui.live_policy_status_label.text()))


class ActualMainTests(UIBase):
    def test_normal_main_bootstrap_ack_replay_both_exits_and_stale_callbacks(self):
        import main
        made=[]
        def create(engine):
            ui=MinesweeperUI(engine);made.append(ui);self.uis.append(ui);return ui
        with patch("PyQt5.QtWidgets.QApplication",return_value=self.app),patch.object(self.app,"exec_",return_value=0),\
             patch("ui_manager.MinesweeperUI",side_effect=create),patch("sys.argv",["main.py"]):
            self.assertEqual(main.main(),0)
        ui=made[0];self.app.processEvents()
        self.assertEqual((ui.engine.width,ui.engine.height,ui.engine.num_mines),(30,16,99))
        ui.difficulty_combo.setCurrentIndex(0);self.select(ui,"STAGE4_R")
        ui.stage4_target_edit.setText("120");ui.stage4_profile_combo.setCurrentIndex(1)
        ui.simple_auto_interval_spin.setValue(1)
        captured={}
        def after_input(record):
            captured["record"]=record;captured["proposal"]=dict(ui._stage4.job._pending)
            captured["timer"]=ui._stage4.reservation
            data=ui._build_current_replay_data("test")
            captured["data"]=data
            self.assertTrue(ui._enter_replay_mode(ReplayPlayer(data)))
        ui.live_action_applied.connect(after_input)
        ui.simple_auto_checkbox.setChecked(True)
        pump(self.app,lambda:ui._replay_mode or ui._live_first_failure is not None,15)
        self.assertTrue(ui._replay_mode,ui._live_first_failure)
        self.assertTrue(ui._stage4.clean)
        self.assertEqual(len(captured["data"].events),1)
        self.assertEqual(captured["record"]["source"],"BOOTSTRAP")
        self.assertEqual(ui.live_action_records[0]["ack_state"],"ACKED")
        job_records=list(ui._stage4.job.records)
        with TemporaryDirectory() as d:
            path=Path(d)/"stage4.json";save_replay_json(captured["data"],path);loaded=load_replay_json(path)
            self.assertEqual(loaded,captured["data"])
        ui.on_replay_last();ui.on_replay_first();ui.on_replay_next()
        ui.replay_playback_mode_combo.setCurrentText("Time");ui.on_replay_slider_changed(0)
        self.assertTrue(ui._exit_replay_mode(same_board=True))
        self.assertIsNotNone(ui._live_fixed_origin)
        self.assertFalse(ui.simple_auto_checkbox.isChecked())
        self.assertEqual(ui._live_policy,"STAGE4_R")
        self.assertEqual(ui.stage4_target_edit.text(),"120");self.assertEqual(ui.stage4_profile_combo.currentData(),"indexed_k100k")
        before=ui._live_action_count
        ui._stage4.on_timeout(captured["timer"])
        ui._stage4.on_proposal(captured["proposal"])
        ui._stage4.on_admitted(dict(nonce="old",proposal=captured["proposal"],deadline_ns=2**62))
        self.assertEqual(ui._live_action_count,before)
        self.assertTrue(ui._enter_replay_mode(ReplayPlayer(loaded)))
        self.assertTrue(ui._exit_replay_mode())
        self.assertFalse(ui.engine.get_board_snapshot().mines_placed)
        self.assertFalse(ui.simple_auto_checkbox.isChecked());self.assertFalse(ui._same_board_completed_games)
        self.assertEqual(len(ui._stage4.job.records),len(job_records))
        AUDIT("actual_main_replay",dict(classification="ACTUAL_MAIN_QT_ENGINE_WORKER; bounded exec loop shim",
            jobs=job_records,input=captured["record"],events=[repr(e) for e in loaded.events],
            replay_exits=["same_board","canonical"],late_inputs=0,worker_starts_during_replay=0))

    def test_actual_calculation_ui_responsive_pause_and_settings_cleanup(self):
        ui=self.make_ui(fake=False);self.select(ui,"STAGE4_M")
        ui.on_left_click(0,0);ui.simple_auto_interval_spin.setValue(5000)
        ticks=[];timer=QTimer();timer.setInterval(5);timer.timeout.connect(lambda:ticks.append(1));timer.start()
        before=ui._live_action_count
        ui.simple_auto_checkbox.setChecked(True)
        pump(self.app,lambda:ui._stage4.job.history.attempts>=1 or ui._stage4.job.state in ("idle","blocked"),15)
        self.assertEqual(ui._stage4.job.history.attempts,1,ui._stage4.job.last_record)
        self.assertTrue(ticks);self.assertEqual(ui._live_action_count,before)
        ui.stage4_profile_combo.setCurrentIndex(1)
        self.assertFalse(ui.simple_auto_checkbox.isChecked())
        pump(self.app,lambda:ui._stage4.clean or ui._stage4.job.state=="blocked",10)
        timer.stop();self.assertTrue(ui._stage4.clean,ui._stage4.job.last_record)
        self.assertEqual(ui._stage4.histories[ui._live_game_id].attempts,1)
        self.assertEqual(ui._live_action_count,before)
        AUDIT("actual_ui_responsive",dict(ticks=len(ticks),additional_inputs=0,job=ui._stage4.job.last_record))
