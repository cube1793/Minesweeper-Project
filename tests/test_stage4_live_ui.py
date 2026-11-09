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


class UsabilityUITests(UIBase):
    def test_reference_compute_auto_adopts_owner_and_progress_is_display_only(self):
        ui=self.make_ui();self.select(ui)
        ui.analysis_checkbox.setChecked(True);ui.on_analyze_current()
        job=ui._stage4.job;run=job.active_run_id;owner=ui._stage4.owner_id
        self.assertEqual(job.state,'computing');self.assertFalse(ui.allow_guess_checkbox.isChecked())
        ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual((job.starts,job.active_run_id,ui._stage4.owner_id),(1,run,owner))
        self.assertFalse(ui.allow_guess_checkbox.isChecked())
        clock=[20.];ui._stage4._progress_clock=lambda:clock[0];ui._stage4._compute_started=20.
        before=(job.starts,len(job.operations),ui._live_action_count,ui._stage4.reservation)
        for i in range(1,21):clock[0]=20.+i/4;ui._stage4._refresh_progress()
        self.assertIn('경과 5.0초',ui.live_policy_status_label.text())
        self.assertEqual((job.starts,len(job.operations),ui._live_action_count,ui._stage4.reservation),before)
        self.assertNotIn('%',ui.live_policy_status_label.text())

    def test_guess_toggles_coalesce_keep_quota_and_off_stays_off(self):
        ui=self.make_ui();self.select(ui);ui.simple_auto_checkbox.setChecked(True)
        controller=ui._stage4;job=controller.job
        history=RuntimeHistory(scope=(ui._live_game_id,ui._live_game_id),attempts=8,last_attempt_count=1)
        job.history=history;old_run=job.active_run_id;old_generation=ui._live_board_generation
        ui.allow_guess_checkbox.setChecked(True)
        ui.allow_guess_checkbox.setChecked(False)
        ui.allow_guess_checkbox.setChecked(True)
        self.assertTrue(ui.simple_auto_checkbox.isChecked());self.assertEqual(job.starts,1)
        self.app.processEvents()
        self.assertEqual(job.starts,2);self.assertNotEqual(job.active_run_id,old_run)
        self.assertTrue(job._start_snapshot.settings.allow_guess);self.assertIs(job.history,history)
        self.assertEqual(job.history.attempts,8);self.assertGreater(ui._live_board_generation,old_generation)
        self.assertIsNone(controller._guess_resume)
        ui.simple_auto_checkbox.setChecked(False);starts=job.starts
        ui.allow_guess_checkbox.setChecked(False);self.app.processEvents()
        self.assertFalse(ui.simple_auto_checkbox.isChecked());self.assertEqual(job.starts,starts)

    def test_guess_resume_cancelled_by_hard_boundaries_and_target_change(self):
        for boundary in ('off','reset','policy','replay','error','target'):
            with self.subTest(boundary=boundary):
                ui=self.make_ui();self.select(ui,'STAGE4_R');ui.stage4_target_edit.setText('120')
                ui.simple_auto_checkbox.setChecked(True);job=ui._stage4.job
                ui.allow_guess_checkbox.setChecked(True)
                if boundary=='off':ui.simple_auto_checkbox.setChecked(False)
                elif boundary=='reset':ui.on_reset()
                elif boundary=='policy':ui.live_policy_combo.setCurrentIndex(0)
                elif boundary=='replay':ui._invalidate_v1_run('Replay 진입',drain_ack=True)
                elif boundary=='error':ui._stage4.fail('CONTROLLED_SETTING_ERROR')
                else:ui.stage4_target_edit.setText('121')
                self.app.processEvents()
                self.assertEqual(job.starts,1);self.assertIsNone(ui._stage4._guess_resume)
                self.assertFalse(ui.simple_auto_checkbox.isChecked())

    def test_expert_full_board_logical_screens_initial_policy_and_replay(self):
        from PyQt5.QtCore import QRect
        from replay_model import ReplayBoard,ReplayData,ReplayEvent
        evidence=[]
        for width,height in ((1280,1024),(1920,1080),(1024,768)):
            with self.subTest(screen=(width,height)),patch.object(MinesweeperUI,'_board_available_geometry',return_value=QRect(0,0,width,height)):
                ui=self.make_ui(width=30,height=16,mines=99)
                for policy in ('STAGE4_S','STAGE4_M','STAGE4_R','SIMPLE'):
                    if policy=='SIMPLE':ui.live_policy_combo.setCurrentIndex(0)
                    else:self.select(ui,policy)
                    self.app.processEvents();self.app.processEvents()
                    record=dict(ui._board_fit_record,policy=policy,viewport=(ui.scroll_area.viewport().width(),ui.scroll_area.viewport().height()),
                                scroll_max=(ui.scroll_area.horizontalScrollBar().maximum(),ui.scroll_area.verticalScrollBar().maximum()))
                    evidence.append(record)
                    self.assertEqual(ui._cell_size,28);self.assertEqual((ui.board_container.width(),ui.board_container.height()),(840,448))
                    if width>=1280:
                        self.assertFalse(record['physical_limit'],record)
                        self.assertEqual(record['scroll_max'],(0,0),record)
                        self.assertGreaterEqual(record['viewport'][0],840);self.assertGreaterEqual(record['viewport'][1],448)
                    else:self.assertTrue(record['physical_limit'],record)
                # The small fixture supplies only a saved Replay; no board game is run.
                ui.on_left_click(0,0)
                data=ui._build_current_replay_data('logical sizing fixture')
                self.assertTrue(ui._enter_replay_mode(ReplayPlayer(data)))
                self.app.processEvents();self.app.processEvents()
                if width>=1280:self.assertEqual((ui.scroll_area.horizontalScrollBar().maximum(),ui.scroll_area.verticalScrollBar().maximum()),(0,0))
                self.assertTrue(ui._exit_replay_mode());self.app.processEvents();self.app.processEvents()
                if width>=1280:self.assertEqual((ui.scroll_area.horizontalScrollBar().maximum(),ui.scroll_area.verticalScrollBar().maximum()),(0,0))
        AUDIT('logical_board_fit',dict(classification='OFFSCREEN_LOGICAL_LAYOUT_NOT_NATIVE_DPI',screens=evidence))


class WindowRetentionTests(UIBase):
    POLICIES = ('S2_SIMPLE', 'STAGE3_V1', 'K_P0', 'K_LC0', 'K_LC1',
                'STAGE4_S', 'STAGE4_M', 'STAGE4_R')

    def settle(self):
        self.app.processEvents()
        self.app.processEvents()

    def test_enlarged_window_survives_all_policies_replay_and_show(self):
        from PyQt5.QtCore import QRect
        with patch.object(MinesweeperUI, '_board_available_geometry',
                          return_value=QRect(0, 0, 1920, 1080)):
            ui = self.make_ui(width=30, height=16, mines=99)
            ui.on_left_click(0, 0)
            ui.resize(1800, 980)
            self.settle()
            enlarged = ui.size()
            observation = ui.engine.get_observation()
            inputs = ui._live_action_count
            combo = ui.live_policy_combo
            self.assertEqual(tuple(combo.itemData(i) for i in range(combo.count())),
                             self.POLICIES)
            for policy in self.POLICIES:
                combo.setCurrentIndex(combo.findData(policy))
                self.settle()
                self.assertEqual(combo.currentData(), policy)
                self.assertNotIn('(실험적)', combo.currentText())
                self.assertEqual(ui.size(), enlarged)
                self.assertEqual(ui._cell_size, 28)
            self.assertEqual(ui.engine.get_observation(), observation)
            self.assertEqual(ui._live_action_count, inputs)
            data = ui._build_current_replay_data('window retention fixture')
            self.assertTrue(ui._enter_replay_mode(ReplayPlayer(data)))
            self.settle()
            self.assertEqual(ui.size(), enlarged)
            self.assertTrue(ui._exit_replay_mode())
            self.settle()
            ui.hide()
            ui.show()
            self.settle()
            self.assertEqual(ui.size(), enlarged)
            self.assertEqual(ui._live_action_count, 0)  # Existing canonical exit starts a new game.
            self.assertFalse(ui.simple_auto_checkbox.isChecked())
            self.assertEqual(ui._stage4.job.starts, 0)
            self.assertEqual((ui.scroll_area.horizontalScrollBar().maximum(),
                              ui.scroll_area.verticalScrollBar().maximum()), (0, 0))
            AUDIT('enlarged_window', dict(classification='OFFSCREEN_NOT_NATIVE',
                  width=ui.width(), height=ui.height(), inputs=inputs,
                  policies=list(self.POLICIES), fit=ui._board_fit_record))

    def test_maximized_state_and_restore_geometry_survive_transitions(self):
        from PyQt5.QtCore import QRect
        with patch.object(MinesweeperUI, '_board_available_geometry',
                          return_value=QRect(0, 0, 1920, 1080)):
            ui = self.make_ui(width=30, height=16, mines=99)
            ui.on_left_click(0, 0)
            ui.resize(1500, 900)
            self.settle()
            normal = ui.size()
            ui.showMaximized()
            self.settle()
            self.assertTrue(ui.isMaximized())
            with patch.object(ui, 'resize', wraps=ui.resize) as resize:
                for policy in self.POLICIES:
                    self.select(ui, policy)
                    self.settle()
                    self.assertTrue(ui.isMaximized())
                data = ui._build_current_replay_data('maximized retention fixture')
                self.assertTrue(ui._enter_replay_mode(ReplayPlayer(data)))
                self.settle()
                self.assertTrue(ui.isMaximized())
                self.assertTrue(ui._exit_replay_mode())
                self.settle()
                self.assertTrue(ui.isMaximized())
                resize.assert_not_called()
            ui.showNormal()
            self.settle()
            self.assertEqual(ui.size(), normal)
            ui.showMaximized()
            self.settle()
            with patch.object(ui, 'resize', wraps=ui.resize) as resize:
                ui.hide()
                ui.show()
                self.settle()
                self.assertTrue(ui.isMaximized())
                self.assertTrue(ui._board_fit_record['window_state_preserved'])
                resize.assert_not_called()
            AUDIT('maximized_window', dict(classification='OFFSCREEN_NOT_NATIVE',
                  restored=(normal.width(), normal.height()), fit=ui._board_fit_record,
                  hidden_restore_geometry='NATIVE_PENDING'))

    def test_available_screen_and_dpi_change_refits_with_scroll_access(self):
        from PyQt5.QtCore import QRect
        available = QRect(0, 0, 1920, 1080)
        with patch.object(MinesweeperUI, '_board_available_geometry',
                          side_effect=lambda: available):
            ui = self.make_ui(width=30, height=16, mines=99)
            ui.resize(1800, 980)
            self.settle()
            # Exercise the connected signals without changing the host monitor.
            screen = ui.screen()
            available = QRect(0, 0, 1024, 768)
            screen.availableGeometryChanged.emit(available)
            screen.logicalDotsPerInchChanged.emit(144.0)
            self.settle()
            record = ui._board_fit_record
            self.assertTrue(record['physical_limit'])
            self.assertLessEqual(ui.width() + record['decoration'][0], 1024)
            self.assertLessEqual(ui.height() + record['decoration'][1], 768)
            self.assertEqual(ui._cell_size, 28)
            self.assertEqual((ui.board_container.width(), ui.board_container.height()),
                             (840, 448))
            self.assertGreater(ui.scroll_area.horizontalScrollBar().maximum() +
                               ui.scroll_area.verticalScrollBar().maximum(), 0)
            viewport = ui.scroll_area.viewport()
            self.assertTrue(ui.rect().contains(viewport.mapTo(ui, viewport.rect().bottomRight())))
            available = QRect(0, 0, 1920, 1080)
            screen.availableGeometryChanged.emit(available)
            self.settle()
            self.assertFalse(ui._board_fit_record['physical_limit'])
            self.assertEqual((ui.scroll_area.horizontalScrollBar().maximum(),
                              ui.scroll_area.verticalScrollBar().maximum()), (0, 0))
            AUDIT('screen_dpi_refit', dict(classification='CONTROLLED_LOGICAL_SIGNALS',
                  small=record, restored=ui._board_fit_record))

    def test_larger_board_grows_and_smaller_board_retains_user_space(self):
        from PyQt5.QtCore import QRect
        with patch.object(MinesweeperUI, '_board_available_geometry',
                          return_value=QRect(0, 0, 1920, 1080)):
            ui = self.make_ui()
            ui.difficulty_combo.setCurrentIndex(0)
            ui.difficulty_combo.setCurrentIndex(2)
            self.settle()
            self.assertEqual((ui.engine.width, ui.engine.height), (30, 16))
            self.assertEqual((ui.scroll_area.horizontalScrollBar().maximum(),
                              ui.scroll_area.verticalScrollBar().maximum()), (0, 0))
            large = ui.size()
            ui.difficulty_combo.setCurrentIndex(0)
            self.settle()
            self.assertEqual(ui.size(), large)
            self.assertEqual(ui._cell_size, 28)


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


class RecoveryUITests(UIBase):
    def delivered(self,outcome="PLAYING"):
        """Real UI input/recording; explicit controlled permit and wire ACK publisher."""
        from stage4_live_contract import exact
        ui=self.make_ui();self.select(ui)
        ui.engine.reset_with_mines(9,9,10,{(x,8) for x in range(9)}|{(8,7)})
        ui._reset_replay_recorder();ui.allow_guess_checkbox.setChecked(True)
        ui.simple_auto_checkbox.setChecked(True)
        controller=ui._stage4;job=controller.job;before=controller.snapshot()
        directory=TemporaryDirectory(prefix="minesweeper_live_policy_stage4_");self.addCleanup(directory.cleanup)
        job._directory=Path(directory.name).resolve();job._temp_parent=job._directory.parent
        job._owner_record=dict(run_id=before.run_id,policy_id="STAGE4_LIVE_SMR_V1")
        point={"WON":(0,0),"LOST":(8,8),"PLAYING":(7,7)}[outcome]
        proposal=dict(state_id=before.identity,request_id=before.runtime_request().identity,token="c"*64,
            move=dict(action="OPEN",x=point[0],y=point[1]),position=0,source="MODEL",status="MODEL_SELECTED",
            reason="CONTROLLED_TERMINAL_DELIVERY",is_guess=True,desired_flag=None,model_status="COMPLETE",
            attempts=0,survival=exact(Fraction(1,2)))
        nonce="controlled-terminal-nonce"
        permit=dict(proposal=proposal,nonce=nonce,deadline_ns=int((job._clock()+5)*1_000_000_000))
        controller.pending=job._pending=proposal;controller.nonce=job._accepted_nonce=nonce
        job._permit=permit;job._awaiting=None;job._sequence=0;job.state="admitted"
        controller.on_admitted(permit)
        self.assertEqual(ui.engine.status.name,outcome,controller.last_error)
        self.assertIsNotNone(controller.expected_ack,controller.last_error)
        self.assertEqual(ui.live_action_records[-1]["ack_state"],"SENT")
        self.assertIn("ACK 대기",controller.status)
        return ui,job,controller.expected_ack,permit

    def receive(self,job,ack):
        from stage4_live_contract import envelope,write_once
        kind="ACKED" if ack.status=="PLAYING" else "FINISHED"
        write_once(job._directory,"worker",0,envelope(ack.run_id,0,kind,ack.to_dict()))
        job._read_reply()

    def test_terminal_ack_auto_off_status_and_cleanup(self):
        for outcome in ("WON","LOST"):
            for retired in (False,True):
                with self.subTest(outcome=outcome,retired=retired):
                    ui,job,ack,permit=self.delivered(outcome);controller=ui._stage4
                    self.assertFalse(ui.simple_auto_checkbox.isChecked())
                    self.assertEqual(job.state,"finishing");controller.retired=retired
                    self.receive(job,ack)
                    ack_status=controller.status;ack_label=ui.live_policy_status_label.text()
                    self.assertIsNone(controller.expected_ack)
                    self.assertEqual(ui.live_action_records[-1]["ack_state"],"ACKED")
                    self.assertEqual((job.state,job.last_ack),("finishing",ack))
                    job._finish("CANCELLED" if retired else "SUCCEEDED",None,0)
                    AUDIT("terminal_ack_status",dict(outcome=outcome,retired=retired,ack_status=ack_status,
                        ack_label=ack_label,finished_status=controller.status,finished_label=ui.live_policy_status_label.text(),
                        ack_state=ui.live_action_records[-1]["ack_state"],expected_ack=controller.expected_ack,
                        job_state=job.state,cleanup=job.last_record))
                    self.assertIn("ACK 확인 완료",ack_status);self.assertIn("정리 중",ack_status)
                    self.assertIn("ACK 확인 완료",ack_label)
                    self.assertIn("게임 종료",controller.status);self.assertIn("정리 완료",controller.status)
                    self.assertIn("정리 완료",ui.live_policy_status_label.text());self.assertTrue(controller.clean)

    def test_missing_ack_clean_owner_recovers_new_game(self):
        ui,job,ack,permit=self.delivered();controller=ui._stage4
        data=ui._build_current_replay_data("controlled recovery")
        before=ui._live_action_count
        job._finish("FAILED","CONTROLLED_ACK_EXIT",1)
        AUDIT("missing_ack_recovery",dict(expected_ack_retained=controller.expected_ack is not None,
            status=controller.status,ack_state=ui.live_action_records[-1]["ack_state"],job_state=job.state,
            cleanup=job.last_record,current_failure=ui._live_first_failure))
        self.assertIsNotNone(ui._live_first_failure);self.assertTrue(ui._live_input_uncertain)
        self.assertEqual(ui.live_action_records[-1]["ack_state"],"UNCONFIRMED")
        self.assertIsNone(controller.expected_ack);self.assertTrue(controller.clean)
        controller.on_ack(ack);controller.on_admitted(permit)
        self.assertEqual(ui._live_action_count,before);self.assertNotIn("정리 완료",controller.status)
        failed_record=job.last_record;ui.on_reset()
        self.assertTrue(controller.clean);self.assertIsNone(ui._live_first_failure)
        ui.stage4_target_edit.setText("120")
        for index in range(ui.live_policy_combo.count()):
            ui.live_policy_combo.setCurrentIndex(index)
            self.assertTrue(ui._same_board_transition_ready())
            self.assertTrue(ui.simple_auto_checkbox.isEnabled())
        ui.simple_auto_checkbox.setChecked(True)
        self.assertNotEqual(job.active_run_id,ack.run_id)
        status=controller.status
        controller.on_ack(ack);controller.on_finished(failed_record);controller.on_admitted(permit)
        self.assertEqual(ui._live_action_count,0);self.assertEqual(controller.status,status)
        self.assertIsNone(ui._live_first_failure)
        ui.simple_auto_checkbox.setChecked(False)
        self.assertTrue(controller.clean)
        self.assertTrue(ui._enter_replay_mode(ReplayPlayer(data)))
        self.assertTrue(ui._exit_replay_mode())
        self.assertTrue(controller.clean);self.assertFalse(ui.simple_auto_checkbox.isChecked())

    def test_unreaped_and_cleanup_failure_still_block_and_never_reapply(self):
        ui,job,ack,permit=self.delivered();controller=ui._stage4;before=ui._live_action_count
        forged=dict(run_id=ack.run_id,status="FAILED",error="CONTROLLED_STILL_ALIVE",reaped=True,
            tree_active_count=0,cleanup_complete=True)
        job.last_record=forged;job._process=SimpleNamespace(pid=-1);job.state="idle"
        controller.on_finished(forged)
        self.assertFalse(controller.clean);self.assertIsNotNone(controller.expected_ack)
        controller.on_admitted(permit);self.assertEqual(ui._live_action_count,before)
        job._process=None
        with patch.object(job,"_cleanup",side_effect=OSError("CONTROLLED_CLEANUP_FAILURE")):
            job._finish("FAILED","CONTROLLED_ACK_EXIT",1)
        self.assertEqual(job.state,"blocked");self.assertFalse(controller.clean)
        self.assertIsNotNone(controller.expected_ack);self.assertNotIn("정리 완료",controller.status)
        self.assertFalse(ui._same_board_transition_ready())
        controller.on_admitted(permit);self.assertEqual(ui._live_action_count,before)
        job._finish("FAILED","CONTROLLED_ACK_EXIT",1)
        self.assertTrue(controller.clean);self.assertIsNone(controller.expected_ack)
        self.assertIsNotNone(ui._live_first_failure)

    def test_error_after_terminal_ack_does_not_display_success(self):
        ui,job,ack,permit=self.delivered("WON");controller=ui._stage4
        self.receive(job,ack);self.assertEqual(ui.live_action_records[-1]["ack_state"],"ACKED")
        job._finish("FAILED","CONTROLLED_EXIT_ERROR",1)
        self.assertIn("CONTROLLED_EXIT_ERROR",controller.status)
        self.assertNotIn("정리 완료",controller.status);self.assertIsNone(controller.expected_ack)
        self.assertIsNotNone(ui._live_first_failure)
        ui,job,ack,permit=self.delivered("LOST");controller=ui._stage4
        self.receive(job,ack);ui._record_live_failure("CONTROLLED_GUI_ERROR",stage="Stage4 input")
        job._finish("SUCCEEDED",None,0)
        self.assertIn("CONTROLLED_GUI_ERROR",controller.status);self.assertNotIn("정리 완료",controller.status)

    def test_closed_owner_is_settled_before_close_refusal_replacement(self):
        ui,job,ack,permit=self.delivered();controller=ui._stage4;before=ui._live_action_count
        job.state="cancelling";job._intent="CANCELLED"
        Stage4LiveJob.shutdown(job)
        self.assertEqual(job.state,"closed");self.assertTrue(job.last_record["cleanup_complete"])
        self.assertEqual(job.last_record["unconfirmed_ack"],ack.to_dict())
        self.assertIsNotNone(controller.expected_ack)
        controller.restore_after_close_refusal()
        self.assertIsNot(controller.job,job);self.assertIsNone(controller.expected_ack)
        self.assertTrue(controller.clean);self.assertEqual(ui.live_action_records[-1]["ack_state"],"UNCONFIRMED")
        self.assertIsNotNone(ui._live_first_failure)
        job.acknowledged.emit(ack);job.admitted.emit(permit);job.finished.emit(job.last_record)
        self.assertEqual(ui._live_action_count,before)
        ui.on_reset();self.assertTrue(controller.clean);self.assertIsNone(ui._live_first_failure)

    def test_failure_before_terminal_ack_never_flashes_success_and_uses_stage4_owner(self):
        ui,job,ack,permit=self.delivered('WON');controller=ui._stage4
        controller.fail('CONTROLLED_BEFORE_ACK_FAILURE')
        failure=ui._live_first_failure
        self.assertTrue(failure['ack_pending']);self.assertEqual(failure['cleanup_state'],'finishing')
        self.assertEqual(ui._v1_job.state,'idle')
        self.receive(job,ack)
        self.assertIn('CONTROLLED_BEFORE_ACK_FAILURE',controller.status)
        self.assertIn('CONTROLLED_BEFORE_ACK_FAILURE',ui.live_policy_status_label.text())
        self.assertNotIn('ACK 확인 완료',controller.status)
        job._finish('SUCCEEDED',None,0)
        self.assertIn('CONTROLLED_BEFORE_ACK_FAILURE',controller.status)
        self.assertNotIn('정리 완료',controller.status)

    def test_guess_change_waits_for_original_ack_and_ignores_old_permit(self):
        ui,job,ack,permit=self.delivered();controller=ui._stage4
        before=ui._live_action_count;starts=job.starts;old=job.active_run_id
        ui.allow_guess_checkbox.setChecked(False)
        self.assertTrue(controller.retired);self.assertIs(controller.expected_ack,ack)
        self.assertEqual(job.active_run_id,old);self.assertEqual(job.starts,starts)
        controller.on_admitted(permit);self.assertEqual(ui._live_action_count,before)
        with patch.object(job,'cancel',side_effect=lambda reason:job._finish('CANCELLED',None,0)):
            self.receive(job,ack)
        self.assertEqual(ui.live_action_records[-1]['ack_state'],'ACKED')
        self.app.processEvents()
        self.assertEqual(job.starts,starts+1);self.assertFalse(job._start_snapshot.settings.allow_guess)
        self.assertIsNone(controller.expected_ack);self.assertEqual(ui._live_action_count,before)
        controller.on_admitted(permit);self.assertEqual(ui._live_action_count,before)


class ActualUsabilityTests(UIBase):
    def test_actual_reference_compute_auto_adopts_same_owner(self):
        ui=self.make_ui(fake=False);self.select(ui)
        ui.engine.reset_with_mines(9,9,10,{(x,8) for x in range(9)}|{(8,7)})
        ui._reset_replay_recorder();ui.on_left_click(7,7)
        ui.simple_auto_interval_spin.setValue(5000);ui.analysis_checkbox.setChecked(True);ui.on_analyze_current()
        job=ui._stage4.job;owner=ui._stage4.owner_id;run=job.active_run_id;process=job._process
        self.assertEqual(job.state,'computing');ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual((ui._stage4.owner_id,job.active_run_id,job._process),(owner,run,process))
        self.assertFalse(ui.allow_guess_checkbox.isChecked())
        pump(self.app,lambda:job.history.attempts>=1 or job.state in ('idle','blocked'),15)
        self.assertEqual(job.history.attempts,1,job.last_record)
        ui.simple_auto_checkbox.setChecked(False)
        pump(self.app,lambda:ui._stage4.clean or job.state=='blocked',10)
        self.assertTrue(ui._stage4.clean,job.last_record);self.assertEqual(ui._live_action_count,1)
        AUDIT('G01_actual_owner_adoption',dict(classification='ACTUAL_SUBPROCESS_PUBLIC_9X9_BOUNDED_NO_AUTO_INPUT',owner=owner,run_id=run,record=job.last_record))

    def test_actual_terminal_ack_then_replay_roundtrip_small_engine_fixture(self):
        ui=self.make_ui(fake=False,width=3,height=2,mines=1);self.select(ui,'STAGE4_S')
        ui.engine.reset_with_mines(3,2,1,{(2,1)});ui._reset_replay_recorder()
        ui.on_left_click(1,0);ui.on_right_click(2,1);ui.simple_auto_interval_spin.setValue(1)
        # Explicit small engine support fixture; production preset gating stays intact.
        with patch.object(ui._stage4,'support_reason',return_value=None):
            ui.allow_guess_checkbox.setChecked(True);ui.simple_auto_checkbox.setChecked(True)
            pump(self.app,lambda:ui.engine.status!=GameStatus.PLAYING or ui._live_first_failure is not None,20)
            self.assertNotEqual(ui.engine.status,GameStatus.PLAYING,ui._stage4.status)
            pump(self.app,lambda:ui._stage4.clean or ui._stage4.job.state=='blocked',10)
            self.assertTrue(ui._stage4.clean,ui._stage4.job.last_record)
        ack=ui._stage4.job.last_ack;self.assertIsNotNone(ack);self.assertNotEqual(ack.status,'PLAYING')
        self.assertEqual(ui.live_action_records[-1]['ack_state'],'ACKED')
        data=ui._build_current_replay_data('actual terminal fixture');records=len(ui._stage4.job.records)
        self.assertTrue(ui._enter_replay_mode(ReplayPlayer(data)));self.assertTrue(ui._exit_replay_mode(same_board=True))
        self.assertTrue(ui._enter_replay_mode(ReplayPlayer(data)));self.assertTrue(ui._exit_replay_mode())
        self.assertEqual(len(ui._stage4.job.records),records);self.assertFalse(ui.simple_auto_checkbox.isChecked())
        AUDIT('G02_actual_terminal_replay',dict(classification='ACTUAL_MODEL_AND_SUBPROCESS_SMALL_3X2_ENGINE_FIXTURE',ack=ack.to_dict(),record=ui._stage4.job.last_record,exits=['same_board','canonical']))

    def test_actual_owned_cleanup_retry_after_transient_directory_error(self):
        ui=self.make_ui(fake=False);self.select(ui);ui.analysis_checkbox.setChecked(True);ui.on_analyze_current()
        job=ui._stage4.job
        pump(self.app,lambda:job.state in ('pending','idle','blocked'),10)
        self.assertEqual(job.state,'pending',job.last_record)
        with patch.object(job,'_cleanup',side_effect=PermissionError('CONTROLLED_TRANSIENT_DIRECTORY_DENIAL')):
            ui._stage4.invalidate('registered cleanup retry')
            pump(self.app,lambda:job.state in ('idle','blocked'),10)
        self.assertEqual(job.state,'blocked');self.assertFalse(job.last_record['cleanup_complete'])
        self.assertTrue(job._cleanup_retry_owned())
        ui.on_reset()
        self.assertTrue(ui._stage4.clean,job.last_record);self.assertTrue(job.last_record['cleanup_retry_complete'])
        self.assertEqual(job.last_record['status'],'FAILED');self.assertIsNone(ui._live_first_failure)
        self.assertTrue(ui.simple_auto_checkbox.isEnabled())
        AUDIT('actual_owned_retry',dict(record=job.last_record,new_game=ui._live_game_id))
