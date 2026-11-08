"""Main's Stage4 controller: public snapshots, viewing waits and guarded input."""
from uuid import uuid4

from PyQt5.QtWidgets import QHBoxLayout, QLabel, QComboBox, QLineEdit, QWidget
from PyQt5.QtCore import QObject
from core_engine import Action, GameStatus
from live_analysis import LiveAnalysis, CellOverlay
from simple_algorithm import SimpleMove
from live_policy import supports_v1_board
from stage3_physical import action_cost, load_timing_table
from stage4_live_job import Stage4LiveJob
from stage4_live_contract import (POLICIES, Settings, Snapshot, Acknowledgement,
    target_percent, digest, require, guard_target)
from stage4_runtime_policy import RuntimeHistory


class Stage4Controller(QObject):
    def __init__(self,ui):
        super().__init__(ui)
        self.ui=ui;self.job=self._new_job()
        self.pending=None;self.expected_ack=None;self.reservation=None;self.nonce=None
        self.owner_id=uuid4().hex;self.retired=True;self.applying=False
        self.histories={};self.latches={};self.status="수동 · Auto OFF"
        self.last_error=None;self.controls=None;self.table=None

    def _new_job(self):
        job=Stage4LiveJob(self.ui)
        job.proposal_ready.connect(self.on_proposal)
        job.admitted.connect(self.on_admitted)
        job.acknowledged.connect(self.on_ack)
        job.acknowledged.connect(lambda ack:self.ui._on_replay_entry_ack(job,ack))
        job.finished.connect(lambda record:self.ui._guard_replay_entry_finish(job,record))
        job.finished.connect(self.on_finished)
        job.finished.connect(lambda record:self.ui._on_replay_entry_finished(job,record))
        return job

    @property
    def selected(self):
        return self.ui._live_policy in POLICIES

    @property
    def clean(self):
        return self.job.state=="idle" and self.job.active_run_id is None and self.expected_ack is None

    def build_controls(self,layout):
        ui=self.ui
        for key,label in (("STAGE4_S","Stage4 안전성 S"),("STAGE4_M","Stage4 평균 효율 M"),("STAGE4_R","Stage4 목표 기록 R")):
            ui.live_policy_combo.addItem(label,key)
        self.controls=QWidget(ui);row=QHBoxLayout(self.controls);row.setContentsMargins(0,0,0,0)
        row.addWidget(QLabel("Stage4 프로파일:"))
        ui.stage4_profile_combo=QComboBox()
        ui.stage4_profile_combo.addItem("기본 indexed · 표본 8 / 후보 4", "indexed")
        ui.stage4_profile_combo.addItem("제한 K100K · 표본 4 / 후보 2 / 행 8", "indexed_k100k")
        ui.stage4_profile_combo.setToolTip("K100K는 F 커널 한도 100,000과 작은 모델 폭을 명시적으로 선택합니다. 일반 효율·안정 처리 시간을 보장하지 않습니다.")
        row.addWidget(ui.stage4_profile_combo)
        self.target_label=QLabel("R 목표 IOE (%):")
        row.addWidget(self.target_label)
        ui.stage4_target_edit=QLineEdit();ui.stage4_target_edit.setMaximumWidth(145)
        ui.stage4_target_edit.setPlaceholderText("양의 백분율 입력")
        ui.stage4_target_edit.setToolTip("직접 정한 양의 목표를 입력하세요. 120%는 6/5라는 설명 예시이며 추천값이 아닙니다.")
        row.addWidget(ui.stage4_target_edit);row.addStretch()
        ui.stage4_profile_combo.currentIndexChanged.connect(self.settings_changed)
        ui.stage4_target_edit.textChanged.connect(self.settings_changed)
        layout.addWidget(self.controls)

    def settings(self):
        ui=self.ui;mode=POLICIES[ui._live_policy]
        target=target_percent(ui.stage4_target_edit.text()) if mode=="R" else None
        return Settings(mode,ui.stage4_profile_combo.currentData(),ui.allow_guess_checkbox.isChecked(),target)

    def support_reason(self):
        ui=self.ui
        if ui.engine.width*ui.engine.height>480:
            return "Stage4는 최대 480칸까지 지원합니다."
        if not supports_v1_board(ui.engine.width,ui.engine.height,ui.engine.num_mines) or ui.difficulty_combo.currentText()=="커스텀":
            return "Stage4는 초급·중급·상급 preset만 지원합니다. 커스텀 보드는 지원하지 않습니다."
        if not ui._known_live_history():
            return "공개 입력 원장과 실제 기록을 확인할 수 없습니다. 새 게임이 필요합니다."
        return None

    def snapshot(self,*,binding=None):
        ui=self.ui
        status=ui.engine.status.name
        observation=None if status!="PLAYING" else tuple(tuple(int(v) for v in r) for r in ui.engine.get_observation())
        counters=ui.engine.get_counter_snapshot()
        counted=counters["active_clicks"]+counters["wasted_clicks"]
        # Only this sum leaves Main; the split and all board secrets stay here.
        entry=("CANONICAL_NEW" if ui._live_fresh_reset and ui._live_action_count==0
               and not ui.engine.get_board_snapshot().mines_placed else
               "FIXED_BOARD" if ui._live_fixed_origin is not None else "CURRENT")
        ledger=digest([repr(event) for event in ui._replay_recorder.events])
        return Snapshot(ui._live_game_id,self.owner_id if binding is None else binding.owner_id,
            ui._live_run_id if binding is None else binding.run_id,
            ui._live_board_generation if binding is None else binding.generation,
            self.settings() if binding is None else binding.settings,observation,
            ui.engine.width,ui.engine.height,ui.engine.num_mines,counted,ui._live_action_count,
            len(ui._replay_recorder.events),ledger,ui._v1_cursor,entry,status)

    def settings_changed(self,*_args):
        if not self.selected or not hasattr(self.ui,"simple_auto_checkbox"):
            return
        self.latches.clear();self.ui._live_board_generation+=1
        self.invalidate("Stage4 설정 변경 · Auto OFF")
        self.ui._set_auto_off(clear_guess=False)
        self.ui._clear_live_analysis(self.status)
        self.ui._update_policy_controls()

    def invalidate(self,reason,*,drain_ack=True):
        self.retired=True;self.pending=None;self.cancel_wait();self.status=reason
        if self.job.active_run_id is not None and not (drain_ack and self.expected_ack is not None):
            self.job.cancel(reason[:128])

    def pause(self):
        self.ui._live_board_generation+=1
        self.invalidate("일시정지 · 모델 사용 이력 보존")
        self.ui._set_auto_off(clear_guess=False);self.ui._update_policy_controls()

    def cancel_wait(self):
        self.reservation=None;self.nonce=None
        self.job.invalidate_admission()

    def reset_episode(self):
        self.latches.clear();self.last_error=None;self.status="새 게임 · 수동 · Auto OFF"

    def restore_after_close_refusal(self):
        if self.job.state=="closed":
            records=list(self.job.records);self.job.deleteLater();self.job=self._new_job();self.job.records.extend(records)

    def update_controls(self):
        ui=self.ui
        if self.controls is None:
            return False
        self.controls.setVisible(self.selected and not ui._replay_mode)
        self.controls.setEnabled(not ui._live_closing and not ui._replay_mode)
        self.target_label.setVisible(self.selected and POLICIES[ui._live_policy]=="R")
        ui.stage4_target_edit.setVisible(self.selected and POLICIES[ui._live_policy]=="R")
        if not self.selected or ui._replay_mode:
            return False
        reason=self.support_reason()
        try:
            self.settings()
        except (ValueError,KeyError) as exc:
            reason=str(exc)
        ready=(self.job.state in ("idle","computing","pending","validating","admitted","ready","acknowledging")
               and ui._v1_job.state=="idle" and not ui._v1_owned and self.expected_ack is None)
        runnable=(not reason and ready and not ui._live_closing and not ui._live_input_uncertain
                  and ui._replay_entry_pending is None and ui.engine.status==GameStatus.PLAYING
                  and ui._live_first_failure is None and ui._live_close_error is None)
        # Auto remains clickable during computation so OFF is always available.
        ui.simple_auto_checkbox.setEnabled(bool(runnable or ui.simple_auto_checkbox.isChecked()))
        ui.simple_auto_checkbox.setText("Stage4 자동 진행")
        ui.analyze_button.setEnabled(bool(runnable))
        ui.allow_guess_checkbox.setEnabled(not ui._live_closing and ui._replay_entry_pending is None)
        ui.auto_cursor_checkbox.setEnabled(not ui._live_closing)
        ui.auto_cursor_overlay.set_available(not self.retired and not ui._live_closing)
        message=reason or self.status
        if ui._live_close_error is not None:
            message="종료 정리 실패: "+ui._live_close_error
        elif ui._replay_entry_pending is not None:
            message="Replay 준비 중 · 원 입력 ACK/Stage4 worker 정리 대기"
        elif self.job.state in ("cancelling","blocked"):
            message=("Stage4 worker 정리 실패: "+str(self.last_error) if self.job.state=="blocked" else "Stage4 worker 정리 중")
        ui.live_policy_status_label.setText(f"Stage4 {POLICIES[ui._live_policy]} | {message}")
        return True

    def start(self):
        ui=self.ui
        try:
            require(self.selected and not ui._replay_mode and not ui._live_closing and not ui._mouse_buttons
                    and ui._replay_entry_pending is None and not ui._live_input_uncertain
                    and ui._live_first_failure is None and ui.engine.status==GameStatus.PLAYING,"Stage4 시작 상태를 확인하세요.")
            reason=self.support_reason();require(reason is None,reason)
            self.settings()
            require(ui._v1_job.state=="idle" and not ui._v1_owned,"이전 V1/K worker 정리 중입니다.")
            if not self.retired and self.job.active_run_id is not None:
                require(self.snapshot()==self.job._expected_snapshot,"Stage4 공개 상태가 변경되었습니다.")
                self.schedule();return
            require(self.clean,"이전 Stage4 worker 정리 중입니다.")
            ui._live_run_id=uuid4().hex;self.owner_id=uuid4().hex
            state=self.snapshot()
            require(state.stop_key not in self.latches,self.latches.get(state.stop_key,""))
            self.retired=False;self.status="다음 수 계산 중";self.last_error=None
            history=self.histories.get(state.game_id,RuntimeHistory())
            self.job.start(state,history)
            ui.live_owner_records.append(dict(game_id=state.game_id,run_id=state.run_id,policy_id=ui._live_policy,
                board_generation=state.generation,start_revision=state.revision,end_reason=None,
                profile=state.settings.profile,history=history.to_payload()))
        except Exception as exc:
            self.status=str(exc);ui._set_auto_off(clear_guess=False)
        ui._update_policy_controls()

    def on_proposal(self,proposal):
        ui=self.ui
        if self.retired or ui._replay_mode or ui._live_closing:
            return
        try:
            state=self.snapshot()
            require(state==self.job._expected_snapshot,"Stage4 오래된 관측 응답")
            if proposal["move"] is None:
                self.status=f"{proposal['status']}: {proposal['reason']}"
                if proposal["status"]=="RESOURCE_LIMIT":
                    self.latches[state.stop_key]=self.status+" · 동일 상태 자동 재요청 차단"
                self.invalidate(self.status);ui._set_auto_off(clear_guess=False)
                ui._clear_live_analysis(self.status);ui._update_policy_controls();return
            guard_target(proposal,state)
            self.pending=proposal;self.status=f"{proposal['source']} · {proposal['model_status']} · 입력 대기"
            m=proposal["move"]
            if ui.analysis_checkbox.isChecked():
                ui._analysis_result=LiveAnalysis(None,SimpleMove(Action[m["action"]],m["x"],m["y"]),
                    self.status,{(m["x"],m["y"]):CellOverlay(recommended=True)})
                ui._analysis_observation=state.observation
                ui.analysis_status_label.setText(self.status);ui._render_live_analysis()
            self.schedule()
        except Exception as exc:
            self.fail(str(exc))
        ui._update_policy_controls()

    def schedule(self):
        ui=self.ui
        if (self.retired or self.pending is None or self.job.state!="pending" or not self.selected
                or ui._replay_mode or ui._live_closing or ui._mouse_buttons or ui._replay_entry_pending is not None
                or not ui.simple_auto_checkbox.isChecked()):
            return
        ui._cancel_simple_auto_step()
        p=self.pending;m=p["move"]
        self.reservation=(ui._live_run_id,ui._live_board_generation,ui._live_action_count,p["token"],ui._v1_timer_nonce)
        reservation=self.reservation
        ui._connect_auto_timeout(lambda:self.on_timeout(reservation))
        if self.table is None:
            self.table=load_timing_table()
        cost=action_cost(self.table,ui._v1_cursor,(m["x"],m["y"]))
        ui._start_auto_pacing(cost,(m["x"],m["y"]))
        ui.auto_cursor_overlay.reserve(reservation,ui._v1_cursor,(m["x"],m["y"]),ui._view_interval_ms())

    def on_timeout(self,reservation):
        ui=self.ui
        if reservation is None or reservation!=self.reservation:
            return
        if ui._defer_early_pacing_timeout():
            return
        ui._stop_auto_pacing_timer()
        if self.retired or not ui.simple_auto_checkbox.isChecked() or ui._replay_mode or ui._live_closing or ui._mouse_buttons:
            return
        try:
            self.nonce=uuid4().hex
            self.job.validate_pending(self.snapshot(),self.nonce)
            self.status="현재 한 입력 검증 중"
        except Exception as exc:
            self.fail(str(exc))
        ui._update_policy_controls()

    def on_admitted(self,permit):
        ui=self.ui
        if permit["nonce"]!=self.nonce or self.retired:
            if not self.retired and self.job.state=="pending":
                self.schedule()
            return
        record=None
        try:
            require(self.selected and not ui._replay_mode and not ui._live_closing and not ui._mouse_buttons
                    and ui._replay_entry_pending is None and ui.simple_auto_checkbox.isChecked()
                    and not ui._live_input_uncertain and self.support_reason() is None,"Stage4 입력 상태 변경")
            before=self.snapshot();p=self.pending
            require(p is not None and permit["proposal"]==p,"Stage4 제안/허가 불일치")
            guard_target(p,before)
            if p["source"]=="BOOTSTRAP":
                require(before.entry=="CANONICAL_NEW" and not ui.engine.get_board_snapshot().mines_placed
                        and ui._live_fixed_origin is None,"Stage4 첫 입력 권한 변경")
            # No event-loop yield/modal/await from this comparison to actual ACK.
            admitted=self.job.mark_applying(p["token"],permit["nonce"],before)
            m=admitted["move"];self.applying=True;self.pending=None
            event_index=ui._apply_live_action(m["x"],m["y"],Action[m["action"]],auto_observation=before.observation)
            after=self.snapshot(binding=before)
            require(event_index==before.event_count and after.event_count==before.event_count+1,
                    "Stage4 실제 Replay event 누락/중복")
            ack=Acknowledgement(before.run_id,p["token"],permit["nonce"],before.identity,after)
            record=dict(game_id=before.game_id,run_id=before.run_id,policy_id=ui._live_policy,
                board_generation=before.generation,token=p["token"],request_id=p["request_id"],
                proposal_position=p["position"],source=p["source"],action=m["action"],x=m["x"],y=m["y"],
                input_revision_before=before.revision,input_revision_after=after.revision,event_index=event_index,
                before=before.to_dict(),after=after.to_dict(),status=after.status,ack_state="SENT",ack_sent=False)
            ui.live_action_records.append(record)
            self.expected_ack=ack
            self.job.acknowledge(ack);record["ack_sent"]=True
            self.status="실제 입력 ACK 대기"
            if self.table is None:
                self.table=load_timing_table()
            cost=action_cost(self.table,before.cursor,after.cursor)
            ui.live_auto_totals["stage4_inputs"]=ui.live_auto_totals.get("stage4_inputs",0)+1
            ui.live_auto_totals["modeled_us"]+=cost
            ui.live_action_applied.emit(dict(record))
        except Exception as exc:
            if self.applying:
                ui._live_input_uncertain=True
            self.fail(str(exc))
        finally:
            self.applying=False
        ui._update_policy_controls()

    def on_ack(self,ack):
        ui=self.ui
        if self.job._start_snapshot is None or ack.run_id!=self.job._start_snapshot.run_id:
            return
        if self.expected_ack!=ack:
            self.fail("Stage4 원 입력 ACK 불일치");return
        self.expected_ack=None
        for record in reversed(ui.live_action_records):
            if record.get("run_id")==ack.run_id and record.get("token")==ack.token:
                record["ack_state"]="ACKED";break
        if self.retired or not self.selected or ui._replay_mode or not ui.simple_auto_checkbox.isChecked():
            if ack.status=="PLAYING":
                self.job.cancel("Stage4 원 입력 확인 후 정리")
            return
        if ack.status!="PLAYING":
            self.status="게임 종료 · Stage4 worker 정리 중";return
        try:
            current=self.snapshot()
            require(current==ack.after,"Stage4 ACK 후 공개 상태 변경")
            self.status="다음 수 계산 중";self.job.request(current)
        except Exception as exc:
            self.fail(str(exc))
        ui._update_policy_controls()

    def on_finished(self,record):
        ui=self.ui
        start=self.job._start_snapshot
        if start is not None and record.get("run_id")!=start.run_id:
            return
        if start is not None:
            self.histories[start.game_id]=self.job.history
        clean=record.get("cleanup_complete") is True and record.get("reaped") is True and record.get("tree_active_count")==0
        if not clean or record.get("error") or record.get("status") in ("FAILED","TIMEOUT"):
            self.last_error=record.get("error") or record.get("intent_reason") or "worker 정리 실패"
            self.status="Stage4 중단: "+str(self.last_error)
            ui._set_auto_off(clear_guess=False)
        if self.expected_ack is not None:
            self.last_error="Stage4 실제 입력 ACK 미확인"
            ui._record_live_failure(self.last_error,stage="Stage4 ACK")
        for owner in reversed(ui.live_owner_records):
            if owner["run_id"]==record.get("run_id"):
                owner.update(end_reason=self.status,cleanup_complete=clean,history=self.job.history.to_payload());break
        self.pending=None;self.retired=True;self.cancel_wait()
        ui._update_policy_controls()

    def fail(self,reason):
        self.last_error=reason;self.invalidate("Stage4 중단: "+reason)
        self.ui._set_auto_off(clear_guess=False)
        self.ui._clear_live_analysis(self.status)
