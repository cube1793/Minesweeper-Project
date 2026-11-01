"""Small source comparison app; renderer, navigation and clocks are reused."""

from fractions import Fraction
import json
from pathlib import Path
import re
import secrets

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QFileDialog,
    QMessageBox, QSizePolicy,
)
from experiments.random_expert_exhibition_ui import TracePanel, STATUS, LIMITATION, TIME_NOTE
from experiments.random_expert_exhibition_playback import ExhibitionPlayer, ExhibitionPlayback
from experiments.k_lc0_exhibition_model import CompareTrace, ComparePair, distance
from experiments.k_lc0_exhibition_store import DEFAULT_RUNS, load_pair, save_pair, publish_json, plain
from experiments.k_lc0_exhibition_job import CompareJob
from experiments.random_expert_exhibition_model import validate_index

TITLE = "새 Expert 비교 — actual K-P0 / K-LC0"
PHASE = {"PREPARING":"보드·source 준비", "K_P0_RUNNING":"왼쪽 actual K-P0 계산 중",
         "K_LC0_RUNNING":"오른쪽 active K-LC0 계산 중", "PROJECTED":"완료 pair 검증·전달 중"}


class ComparePlayer(ExhibitionPlayer):
    """Exact new type admission; inherited position-only protocol is unchanged."""
    def __init__(self, trace):
        if type(trace) is not CompareTrace: raise TypeError("Expected completed CompareTrace.")
        self.trace,self._current_index = trace,0


class ComparePanel(TracePanel):
    def __init__(self,title,**kwargs):
        self.choice_label = None
        super().__init__(title,**kwargs)
        self.choice_label = QLabel("다음 선택의 기록: 대기")
        self.choice_label.setWordWrap(True)
        self.layout().insertWidget(2,self.choice_label)
        for label in (self.summary,self.position,self.choice_label,self.pacing_note):
            label.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Maximum)
        self.position.setWordWrap(True)
        self.scroll.setMinimumHeight(150)

    def install(self,trace):
        if type(trace) is not CompareTrace: raise TypeError("Actual CompareTrace required.")
        self.clear()
        self.player = ComparePlayer(trace)
        self.playback = ExhibitionPlayback(self.player,clock=self._clock)
        self.playback.set_mode(self.mode.currentData())
        self.playback.set_interval(self._saved_interval_ms)
        self.playback.set_speed(self.speed.currentData())
        self.slider.setRange(0,self.player.step_count)
        self.seek_box.setRange(0,self.player.step_count)
        op,flag,chord = trace.counts
        self.summary.setText(f"전체 {trace.policy_id}: {STATUS[trace.outcome]} ({trace.outcome}) · {self.player.step_count} 입력 · O/F/C {op}/{flag}/{chord}\n"
                             f"종료 비용 {trace.total_modeled_us:,} µs · 실제 총 이동 {distance(trace.actions):.3f}칸")
        self._sync_interval_controls()
        self.refresh()

    def refresh(self):
        super().refresh()
        if self.choice_label is None: return
        if self.player is None:
            self.choice_label.setText("다음 선택의 기록: 대기")
            return
        p = self.player
        f = p.current_frame
        self.position.setText(f"현재 완료 {p.current_index}/{p.step_count} · {STATUS[f.status]} · M {len(f.logical_mines)} · 물리 ⚑ {len(f.explicit_flags|f.automatic_flags)}\n"
                              f"누적 비용 {f.cumulative_modeled_us:,} µs · 누적 이동 {distance(p.trace.actions[:p.current_index]):.3f}칸")
        if p.pending_action is None:
            self.choice_label.setText("다음 선택의 기록: 없음 (종료)")
            self.choice_label.setToolTip("")
        else:
            c = p.trace.choices[p.current_index]
            def note(plan): return f"L/R {plan.L}/{plan.R}, D {plan.D:.3f}" if plan else "계획 없음"
            self.choice_label.setText(f"다음 선택의 기록: {c.phase} · {c.reason}\n"
                                      f"g {note(c.g)} → 선택 {note(c.selected)}")
            self.choice_label.setToolTip(json.dumps(plain(c),ensure_ascii=False,indent=2)+"\n계획 suffix는 완료 경로가 아닙니다.")


class CompareWindow(QWidget):
    def __init__(self,*,job=None,runs_root=DEFAULT_RUNS):
        super().__init__()
        self.setWindowTitle(TITLE)
        self.resize(1840,940)
        self.setMinimumSize(800,720)
        self.job = job if job is not None else CompareJob(self,runs_root=runs_root)
        self.pair = None
        self._active_token = None
        self._accept_result = self._closed = self._busy = False
        self.saved_path = None
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("다음 요청 index (0..99999)"))
        self.index_edit = QLineEdit("314")
        self.index_edit.setMaximumWidth(100)
        self.run_button = QPushButton("index 지정 실행")
        self.draw_button = QPushButton("새 추첨 실행")
        self.cancel_button = QPushButton("취소")
        self.open_button = QPushButton("저장 JSON 열기")
        self.info_button = QPushButton("실행 정보")
        for widget in (self.index_edit,self.run_button,self.draw_button,self.cancel_button,self.open_button,self.info_button): controls.addWidget(widget)
        controls.addStretch()
        layout.addLayout(controls)
        self.status = QLabel("실행 대기 · 지정 실행 또는 새 추첨 실행을 눌러 계산합니다.")
        self.identity = QLabel("표시 pair 없음 · Expert 30×16/99 · EXPERT_GENERAL_V1 / V1 / game_index")
        self.storage = QLabel("저장 root: " + str(self.job.runs_root))
        for label in (self.status,self.identity,self.storage):
            label.setWordWrap(True)
            label.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Maximum)
            layout.addWidget(label)
        self.identity.setToolTip("입력란은 다음 요청값입니다. 표시 중 보드는 아래 실제 pair identity를 따릅니다.")
        together = QHBoxLayout()
        self.play_all_button = QPushButton("함께 재생")
        self.pause_all_button = QPushButton("함께 일시정지")
        self.reset_all_button = QPushButton("함께 처음으로")
        for button in (self.play_all_button,self.pause_all_button,self.reset_all_button): together.addWidget(button)
        together.addStretch()
        layout.addLayout(together)
        panels = QHBoxLayout()
        self.left = ComparePanel("왼쪽 · actual K-P0")
        self.right = ComparePanel("오른쪽 · K-LC0 / DISTANCE_BAND_V1")
        panels.addWidget(self.left,1)
        panels.addWidget(self.right,1)
        layout.addLayout(panels,1)
        self.difference = QLabel("승리 시간 차이: N/A · 완료 pair 없음")
        self.difference.setWordWrap(True)
        layout.addWidget(self.difference)
        note = QLabel("초록 ◇ M · 빨간 ⚑ 물리 깃발 · 보라 경로는 완료 입력만 · 자동 WIN flags는 입력 수에서 제외\n"
                      + LIMITATION + "\n" + TIME_NOTE)
        note.setWordWrap(True)
        note.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Maximum)
        layout.addWidget(note)
        self.left.state_changed.connect(self.refresh_common)
        self.right.state_changed.connect(self.refresh_common)
        self.play_all_button.clicked.connect(self.play_all)
        self.pause_all_button.clicked.connect(self.pause_all)
        self.reset_all_button.clicked.connect(self.reset_all)
        self.run_button.clicked.connect(self.run_entered)
        self.index_edit.returnPressed.connect(self.run_entered)
        self.draw_button.clicked.connect(self.draw)
        self.cancel_button.clicked.connect(self.cancel)
        self.open_button.clicked.connect(self.choose_record)
        self.info_button.clicked.connect(self.show_info)
        self.job.finished.connect(self.completed)
        self.job.progressed.connect(lambda *args:self.refresh_status())
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(100)
        self.status_timer.timeout.connect(self.refresh_status)
        self.set_busy(False)

    def set_busy(self,value):
        self._busy = value
        ready = not value and not self._closed and self.job.state == "idle"
        for w in (self.run_button,self.draw_button,self.index_edit,self.open_button): w.setEnabled(ready)
        self.cancel_button.setEnabled(value and self.job.state == "running")
        self.refresh_common()

    def common_ready(self):
        return not self._busy and not self._closed and self.pair is not None and self.job.state == "idle"

    def refresh_common(self):
        ready = self.common_ready() and all(p.player is not None for p in (self.left,self.right))
        self.play_all_button.setEnabled(ready and any(not p.playback.running and p.player.pending_action is not None for p in (self.left,self.right)))
        self.pause_all_button.setEnabled(ready and any(p.playback.running for p in (self.left,self.right)))
        self.reset_all_button.setEnabled(ready and any(p.player.current_index or p.playback.partial_modeled_us or p.playback.running for p in (self.left,self.right)))

    def play_all(self):
        if self.common_ready():
            for panel in (self.left,self.right): panel.play()
    def pause_all(self):
        if self.common_ready():
            for panel in (self.left,self.right): panel.pause()
    def reset_all(self):
        if self.common_ready():
            for panel in (self.left,self.right): panel.seek(0)

    def run_entered(self):
        value = self.index_edit.text().strip()
        if not re.fullmatch(r"[0-9]{1,5}",value):
            self.status.setText("입력 오류 · 0..99999 정수만 허용 · 실행하지 않음")
            return
        self.run_index(int(value))

    def draw(self):
        if not self._busy and not self._closed and self.job.state == "idle":
            self.run_index(secrets.randbelow(100000),kind="draw")  # one draw, duplicates retained

    def run_index(self,index,kind="index"):
        if self._closed or self._busy or self.job.state != "idle": return
        try:
            validate_index(index)
            token = self.job.start(index,kind)
        except Exception as exc:
            self.status.setText(f"새 요청 시작 실패 (표시된 기록은 이전 pair): {exc}")
            return
        self._active_token,self._accept_result = token,True
        self.pair,self.saved_path = None,None
        self.left.clear(); self.right.clear()
        self.index_edit.setText(str(index))
        run_id = self.job.request["run_id"] if self.job.request else "request 저장 실패"
        self.identity.setText(f"표시 pair 없음 · 계산 요청 index {index} · run ID {run_id}")
        self.storage.setText("완료 pair는 아직 저장되지 않았습니다.")
        self.storage.setToolTip("")
        self.difference.setText("승리 시간 차이: N/A · 계산 중")
        self.set_busy(True)
        self.status_timer.start()
        self.refresh_status()

    def cancel(self):
        self._accept_result = False
        self.job.cancel()
        self.refresh_status()

    def refresh_status(self):
        if self._active_token is None: return
        phase = PHASE.get((self.job._phase or {}).get("phase"),"실행 준비 중")
        if self.job.state in ("cancelling","blocked"): phase = "미완료 · worker 정리 중 (새 실행 차단)"
        self.status.setText(f"{phase} · {self.job.elapsed:.1f}s / pair cap 120s")
        self.set_busy(True)

    def _save_lifecycle(self):
        if self.job.run_directory is None or self.job.last_record is None: return ""
        path = self.job.run_directory/"lifecycle.json"
        if path.exists(): return ""
        try: publish_json(path,self.job.last_record)
        except OSError as exc: return f" · 정리 진단 저장 실패: {exc}"
        return ""

    def completed(self,token,status,value):
        if self._closed or type(token) is not int or token != self._active_token: return
        accepted = self._accept_result
        self._active_token,self._accept_result = None,False
        self.status_timer.stop()
        self.set_busy(False)
        diagnostic = self._save_lifecycle()
        if status != "SUCCEEDED" or not accepted:
            label = "CANCELLED (완료 결과 설치 취소)" if status == "SUCCEEDED" else status
            self.status.setText(f"새 요청 미완료: {label} · 승패로 처리하지 않음"+diagnostic)
            self.difference.setText("승리 시간 차이: N/A · 미완료 요청")
            self.storage.setText("pair 저장 없음 · 실행 정보에서 오류와 worker 정리를 확인하세요.")
            return
        self.install(value,historical=False)
        try:
            self.saved_path = save_pair(self.job.run_directory,value)
        except Exception as exc:
            self.storage.setText(f"저장 실패 (계산 완료·worker 정리와 별개): {exc}")
            self.status.setText("계산 완료 · 미저장 결과 · 좌우 독립 관람 가능"+diagnostic)
        else:
            self.show_location("저장 성공",self.saved_path)
            self.status.setText("계산·worker 정리·JSON 저장 및 재독 확인 완료"+diagnostic)

    def install(self,pair,*,historical):
        if type(pair) is not ComparePair: raise TypeError("ComparePair required.")
        pair.__post_init__()
        self.pair = pair
        self.left.install(pair.left); self.right.install(pair.right)
        kind = "저장 재생 · 당시 source identity (현재 새 실행 아님)" if historical else "새 실행 완료"
        self.identity.setText(f"{kind} · 표시 index {pair.board.index} / seed {pair.board.seed} · run ID {pair.run_id}\n"
                              f"fingerprint {pair.board.fingerprint}")
        diff = pair.time_to_win_difference_us
        self.difference.setText("K-LC0 − K-P0: 승리 시간 차이 " + (f"{diff:+,} µs" if diff is not None else "N/A (양쪽 WON 아님)")
                                + " · LOST 종료 비용은 승리 시간이 아닙니다.")
        self.refresh_common()

    def choose_record(self):
        path,_ = QFileDialog.getOpenFileName(self,"완료 비교 JSON 열기",str(self.job.runs_root),"비교 JSON (*.json)")
        if path: self.open_record(path)

    def open_record(self,path):
        if self._busy or self._closed or self.job.state != "idle": return
        self.pause_all()
        try: pair = load_pair(path)
        except Exception as exc:
            self.status.setText(f"저장 열기 거부 · 기존 표시 pair 유지: {exc}")
            return False
        self.install(pair,historical=True)
        self.saved_path = Path(path).resolve()
        self.show_location("저장 기록 읽기 성공",self.saved_path)
        self.status.setText("저장 JSON 재생 · solver/보드 생성/planner 호출 없음")
        return True

    def show_location(self,label,path):
        path = Path(path).resolve()
        self.storage.setText(f"{label}: {path.name} · 폴더 {path.parent.name}\n상위 경로: {path.parent.parent}")
        self.storage.setToolTip(str(path))

    def show_info(self):
        detail = dict(lifecycle=self.job.last_record,session=self.job.records)
        if self.pair:
            detail.update(run_id=self.pair.run_id,source=plain(self.pair.source),board=plain(self.pair.board),
                          policies=[self.pair.left.policy_id,self.pair.right.policy_id],record_limits=self.pair.record_limits)
        box = QMessageBox(self)
        box.setWindowTitle("K-P0 / K-LC0 실행 정보")
        box.setText("실제 당시 source hash·미커밋 상태와 worker 정리 기록입니다.\n"
                    "JSON hash는 자체 일치 검사이며 외부 서명·독립 인증이 아닙니다.")
        box.setDetailedText(json.dumps(detail,ensure_ascii=False,indent=2))
        box.exec_()

    def closeEvent(self,event):
        self._accept_result = False
        self.status_timer.stop()
        for panel in (self.left,self.right):
            panel.timer.stop()
            if panel.playback: panel.playback.cancel_partial()
        try: self.job.shutdown()
        except RuntimeError as exc:
            self.status.setText(f"닫기 보류 · 소유 worker 정리 실패: {exc}")
            self.set_busy(False)
            event.ignore()
            return
        self._save_lifecycle()
        self._closed,self._active_token = True,None
        self.refresh_common()
        event.accept()
