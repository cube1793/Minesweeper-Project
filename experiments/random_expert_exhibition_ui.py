"""Small Korean exhibition UI. Playback reads immutable results, never solvers."""

from dataclasses import asdict
from fractions import Fraction
import json
import re
from time import monotonic_ns

from PyQt5.QtCore import QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QComboBox, QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSlider, QSpinBox, QStyle, QStyleOptionSlider, QVBoxLayout, QWidget,
)

from experiments.random_expert_exhibition_job import ExhibitionJob
from experiments.random_expert_exhibition_model import (
    HIDDEN, FLAGGED, EXPLODED, MINE, FALSE_FLAG, draw_index, validate_index,
)
from experiments.random_expert_exhibition_playback import (
    ExhibitionPlayer, ExhibitionPlayback, INTERVAL_MODE, MODEL_C_MODE, INTERVALS_MS, SUPPORTED_SPEEDS,
    MIN_INTERVAL_MS, MAX_INTERVAL_MS,
)
from visualization_reference_overlays import NUMBER_COLORS, paint_action_target_route


CELL = 28
STATUS = {"PLAYING": "진행 중", "WON": "승리", "LOST": "패배"}
PHASE = {"PREPARING": "보드·실행 환경 준비", "V1_RUNNING": "frozen V1 계산 중",
         "K_P0_RUNNING": "Program K (K-P0) 계산 중", "PROJECTED": "결과 검증·전달 중"}
TITLE = "새 Expert 보드 전시 — frozen V1 · Program K"
LIMITATION = "새 보드 전시 시연이며 통계적 효과성 증거가 아닙니다. 좌우 입력 번호·진행률은 같은 보드 진척을 뜻하지 않습니다."
TIME_NOTE = "관람 속도는 설명을 위한 설정이며 Model C·실제 인간 시간과 다릅니다. 파란 커서의 직선 이동은 합성이며 실제 마우스 기록이 아닙니다."


class PublicBoard(QWidget):
    """Public glyphs + committed M, route; only cursor/target may be pending."""

    def __init__(self, width=30, height=16):
        super().__init__()
        self.setFixedSize(width * CELL, height * CELL)
        self.width_cells, self.height_cells = width, height
        self.frame = None
        self.route = ()
        self.cursor = (0, 0)
        self.target = None
        self.setMouseTracking(True)

    def present(self, player, playback):
        self.frame = player.current_frame
        self.route = player.completed_route
        self.cursor, self.target = playback.cursor, playback.target
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(QFont("Arial", 14, QFont.Bold))
        rows = self.frame.observation if self.frame else None
        logical = self.frame.hidden_logical_mines if self.frame else frozenset()
        for y in range(self.height_cells):
            for x in range(self.width_cells):
                value = rows[y][x] if rows else HIDDEN
                rect = QRect(x * CELL, y * CELL, CELL, CELL)
                background = "#ff7777" if value == EXPLODED else "#c5c9cd" if value in (HIDDEN, FLAGGED) else "#e5e7e9"
                painter.fillRect(rect, QColor(background))
                painter.setPen(QColor("#f7f7f7" if value in (HIDDEN, FLAGGED) else "#b1b5b9"))
                painter.drawRect(rect.adjusted(0, 0, -1, -1))
                text = "⚑" if value == FLAGGED else "✹" if value in (MINE, EXPLODED) else "×" if value == FALSE_FLAG else str(value) if value > 0 else ""
                painter.setPen(QColor("#c02020" if value in (FLAGGED, FALSE_FLAG) else NUMBER_COLORS.get(value, "#202327")))
                painter.drawText(rect, Qt.AlignCenter, text)
                if (x, y) in logical:  # physical FLAG has glyph priority; only HIDDEN M is a diamond
                    cx, cy = (x + .5) * CELL, (y + .5) * CELL
                    painter.setPen(QPen(QColor("#17663f"), 2))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawPolygon(QPolygonF([QPointF(cx, cy - 6), QPointF(cx + 6, cy),
                                                  QPointF(cx, cy + 6), QPointF(cx - 6, cy)]))
        paint_action_target_route(painter, [QPointF((x + .5) * CELL, (y + .5) * CELL) for x, y in self.route])
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        if self.target is not None:
            x, y = self.target
            painter.setPen(QPen(QColor("#e58612"), 2.5))
            painter.drawRect(QRectF(x * CELL + 2, y * CELL + 2, CELL - 4, CELL - 4))
        painter.setPen(QPen(QColor("#1679c4"), 2.5))
        painter.drawEllipse(QPointF((self.cursor[0] + .5) * CELL, (self.cursor[1] + .5) * CELL), 8, 8)

    def mouseMoveEvent(self, event):
        x, y = event.x() // CELL, event.y() // CELL
        if self.frame is None or not (0 <= x < self.width_cells and 0 <= y < self.height_cells):
            return
        cell, frame = (x, y), self.frame
        value = frame.observation[y][x]
        facts = [f"({x}, {y}) · 공개 값 {value}"]
        if cell in frame.logical_mines:
            facts.append("K가 완료 입력 경계까지 논리적으로 기억한 지뢰")
        if cell in frame.explicit_flags:
            facts.append("실제 FLAG 입력")
        if cell in frame.automatic_flags:
            facts.append("자동 WIN 깃발 · 추가 physical input 아님")
        if value in (MINE, EXPLODED):
            facts.append("종료 후 공개된 지뢰")
        self.setToolTip("\n".join(facts))


class AbsoluteSeekSlider(QSlider):
    """Absolute groove clicks; native Qt handle dragging and keyboard navigation."""

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self._track_press = False

    def mousePressEvent(self, event):
        self._track_press = False
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
        groove = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, self)
        if (self.isEnabled() and event.button() == Qt.LeftButton and self.minimum() < self.maximum()
                and groove.contains(event.pos()) and not handle.contains(event.pos())):
            span = groove.width() - handle.width()
            if span > 0:
                position = event.x() - groove.x() - handle.width() // 2
                value = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), position, span, option.upsideDown)
                self._track_press = True
                self.setFocus(Qt.MouseFocusReason)
                self.setValue(value)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._track_press:
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._track_press and event.button() == Qt.LeftButton:
            self._track_press = False
            event.accept()  # no native page-step/repeat after an absolute click
        else:
            super().mouseReleaseEvent(event)


class TracePanel(QGroupBox):
    state_changed = pyqtSignal()

    def __init__(self, title, *, clock=monotonic_ns):
        super().__init__(title)
        self._clock = clock
        self.player = self.playback = None
        self._saved_interval_ms = Fraction(250)
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        self.summary = QLabel("보드를 실행하면 완료된 기록이 표시됩니다.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.position = QLabel("완료 입력 0 · 누적 Model C 0 µs")
        layout.addWidget(self.position)
        self.board = PublicBoard()
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.board)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setMinimumSize(100, 120)
        layout.addWidget(self.scroll, 1)
        nav = QHBoxLayout()
        self.first = QPushButton("처음")
        self.previous = QPushButton("이전")
        self.play_button = QPushButton("재생")
        self.next_button = QPushButton("다음")
        self.last = QPushButton("끝")
        for button in (self.first, self.previous, self.play_button, self.next_button, self.last):
            nav.addWidget(button)
        layout.addLayout(nav)
        seek = QHBoxLayout()
        self.slider = AbsoluteSeekSlider()
        self.seek_box = QSpinBox()
        self.seek_box.setPrefix("입력 ")
        seek.addWidget(self.slider, 1)
        seek.addWidget(self.seek_box)
        layout.addLayout(seek)
        timing = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem("관람 간격", INTERVAL_MODE)
        self.mode.addItem("Model C 시간", MODEL_C_MODE)
        self.interval = QComboBox()
        for value in INTERVALS_MS:
            self.interval.addItem(f"{value}ms · {1000 // value} CPS", value)
        self.interval.addItem("직접 입력", None)
        self.speed = QComboBox()
        for value in SUPPORTED_SPEEDS:
            self.speed.addItem(f"{float(value):g}배", value)
        self.speed.setCurrentIndex(2)
        for widget in (self.mode, self.interval, self.speed):
            timing.addWidget(widget)
        layout.addLayout(timing)
        manual = QHBoxLayout()
        self.interval_ms_box = QDoubleSpinBox()
        self.interval_ms_box.setRange(MIN_INTERVAL_MS, MAX_INTERVAL_MS)
        self.interval_ms_box.setSuffix(" ms")
        self.interval_ms_box.setSingleStep(10)
        self.interval_ms_box.setAccessibleName("관람 간격 ms")
        self.cps_box = QDoubleSpinBox()
        self.cps_box.setRange(.1, 50)
        self.cps_box.setSuffix(" CPS")
        self.cps_box.setSingleStep(.1)
        self.cps_box.setAccessibleName("관람 속도 CPS")
        for box in (self.interval_ms_box, self.cps_box):
            box.setDecimals(3)
            box.setKeyboardTracking(False)
            box.setToolTip("20~10000 ms / 0.1~50 CPS · 입력 확정 또는 화살표 조절 시 적용\n"
                           "표시는 소수 셋째 자리까지이며 ≈는 환산 반올림입니다. 관람용 입력 진행률입니다.")
            manual.addWidget(box, 1)
        layout.addLayout(manual)
        self.pacing_note = QLabel()
        self.pacing_note.setWordWrap(True)
        layout.addWidget(self.pacing_note)
        self._sync_interval_controls()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.first.clicked.connect(lambda: self.seek(0))
        self.previous.clicked.connect(lambda: self.seek(max(0, self.player.current_index - 1)))
        self.next_button.clicked.connect(lambda: self.seek(min(self.player.step_count, self.player.current_index + 1)))
        self.last.clicked.connect(lambda: self.seek(self.player.step_count))
        self.play_button.clicked.connect(self.toggle)
        self.slider.valueChanged.connect(self.seek)
        self.seek_box.valueChanged.connect(self.seek)
        self.mode.currentIndexChanged.connect(self.change_timing)
        self.interval.currentIndexChanged.connect(self.choose_interval)
        self.interval_ms_box.valueChanged.connect(self.change_interval)
        self.cps_box.valueChanged.connect(self.change_cps)
        self.speed.currentIndexChanged.connect(self.change_timing)
        self.clear()

    def clear(self):
        self.timer.stop()
        if self.playback:
            self._saved_interval_ms = self.playback.interval_ms
            self.playback.cancel_partial()
        self.player = self.playback = None
        self.board.frame, self.board.route, self.board.target = None, (), None
        self.board.cursor = (0, 0)
        self.board.update()
        self.summary.setText("완료된 실행 기록 대기 중")
        self.position.setText("완료 입력 0 · 누적 Model C 0 µs")
        for widget in (self.slider, self.seek_box):
            blocked = widget.blockSignals(True)
            widget.setRange(0, 0)
            widget.blockSignals(blocked)
        self.refresh()

    def install(self, trace):
        self.clear()
        self.player = ExhibitionPlayer(trace)
        self.playback = ExhibitionPlayback(self.player, clock=self._clock)
        self.playback.set_mode(self.mode.currentData())
        self.playback.set_interval(self._saved_interval_ms)
        self.playback.set_speed(self.speed.currentData())
        self.slider.setRange(0, self.player.step_count)
        self.seek_box.setRange(0, self.player.step_count)
        op, flag, chord = trace.counts
        self.summary.setText(f"실제 결과: {STATUS[trace.outcome]} ({trace.outcome}) · 총 {self.player.step_count} 입력\n"
                             f"OPEN {op} / FLAG {flag} / CHORD {chord} · 종료까지 Model C {trace.total_modeled_us:,} µs")
        self._sync_interval_controls()
        self.refresh()

    def seek(self, index):
        if self.playback is None:
            return
        self.timer.stop()
        self.playback.seek(index)
        self.refresh()

    def toggle(self):
        if self.playback is None:
            return
        if self.playback.running:
            self.pause()
        else:
            self.play()

    def play(self):
        if self.playback is None:
            return
        self.playback.play()  # idempotent; an ended trace never rewinds
        if self.playback.running and not self.timer.isActive():
            self.timer.start()
        self.refresh()

    def pause(self):
        if self.playback is None:
            return
        self.playback.pause()
        self.timer.stop()
        self.refresh()

    def change_timing(self):
        if self.playback is not None:
            self.playback.set_mode(self.mode.currentData())
            self.playback.set_speed(self.speed.currentData())
        self.refresh()

    def choose_interval(self):
        value = self.interval.currentData()
        if value is not None:
            self.change_interval(value)

    def change_interval(self, value):
        if self.playback is not None:
            self.playback.set_interval(value)
            self._sync_interval_controls()
            self.refresh()

    def change_cps(self, value):
        if self.playback is not None:
            self.playback.set_cps(value)
            self._sync_interval_controls()
            self.refresh()

    def _sync_interval_controls(self):
        # The exact duration is authoritative; rounded reciprocal displays never feed it back.
        ms = self.playback.interval_ms if self.playback else self._saved_interval_ms
        cps = 1000 / ms
        preset = self.interval.findData(int(ms)) if ms.denominator == 1 else -1
        for widget, value in ((self.interval, preset if preset >= 0 else len(INTERVALS_MS)),
                              (self.interval_ms_box, float(ms)), (self.cps_box, float(cps))):
            blocked = widget.blockSignals(True)
            if widget is self.interval:
                widget.setCurrentIndex(value)
            else:
                widget.setValue(value)
            widget.blockSignals(blocked)
        def shown(value):
            rounded = f"{float(value):.3f}".rstrip("0").rstrip(".")
            return ("≈" if Fraction(rounded) != value else "") + rounded
        self.pacing_note.setText(f"관람용 {shown(ms)} ms · {shown(cps)} CPS\n"
                                 "범위 20~10000 ms / 0.1~50 CPS · ≈는 반올림 표시")

    def tick(self):
        try:
            self.playback.update()
        except Exception as exc:
            self.timer.stop()
            self.position.setText(f"재생 오류: {exc}")
            self.play_button.setText("재생")
            return
        self.refresh()

    def refresh(self):
        ready = self.player is not None
        for widget in (self.first, self.previous, self.next_button, self.last, self.slider, self.seek_box,
                       self.play_button, self.mode):
            widget.setEnabled(ready)
        self.interval.setEnabled(ready and self.mode.currentData() == INTERVAL_MODE)
        for widget in (self.interval_ms_box, self.cps_box):
            widget.setEnabled(ready and self.mode.currentData() == INTERVAL_MODE)
        self.speed.setEnabled(ready and self.mode.currentData() == MODEL_C_MODE)
        if not ready:
            self.play_button.setText("재생")
            self.state_changed.emit()
            return
        index, count = self.player.current_index, self.player.step_count
        for widget in (self.slider, self.seek_box):
            widget.blockSignals(True)
            widget.setValue(index)
            widget.blockSignals(False)
        self.first.setEnabled(index > 0 or bool(self.playback.partial_modeled_us))
        self.previous.setEnabled(index > 0)
        self.next_button.setEnabled(index < count)
        self.last.setEnabled(index < count)
        self.play_button.setEnabled(index < count)
        self.play_button.setText("일시정지" if self.playback.running else "재생")
        if not self.playback.running:
            self.timer.stop()
        frame = self.player.current_frame
        self.position.setText(f"완료 입력 {index} / {count} · {STATUS[frame.status]} · 누적 Model C {frame.cumulative_modeled_us:,} µs")
        self.board.present(self.player, self.playback)
        self.state_changed.emit()


class ExhibitionWindow(QWidget):
    def __init__(self, *, job=None):
        super().__init__()
        self.setWindowTitle(TITLE)
        self.resize(1840, 900)
        self.setMinimumSize(800, 650)
        self.job = job if job is not None else ExhibitionJob(self)
        self._active_token = None
        self._accept_result = False
        self._closed = False
        self._busy = False
        self.current_index = None
        self.pair = None
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.draw_button = QPushButton("새 보드 추첨")
        self.index_edit = QLineEdit("11")
        self.index_edit.setPlaceholderText("0..99999")
        self.index_edit.setMaximumWidth(120)
        self.run_button = QPushButton("index 지정 실행")
        self.cancel_button = QPushButton("실행 취소")
        self.info_button = QPushButton("실행 정보 / 진단")
        controls.addWidget(QLabel("Expert 30×16 / 99 · 기존 corpus에서 새로 추첨"))
        for widget in (self.draw_button, self.index_edit, self.run_button, self.cancel_button, self.info_button):
            controls.addWidget(widget)
        controls.addStretch()
        layout.addLayout(controls)
        self.status = QLabel("새 보드를 추첨하거나 index를 지정하세요. 계산 완료 후 좌우를 각각 재생할 수 있습니다.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.identity = QLabel("index / seed / fingerprint: 실행 대기")
        self.identity.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.identity.setWordWrap(True)
        layout.addWidget(self.identity)
        note = QLabel(LIMITATION + "\n" + TIME_NOTE)
        note.setWordWrap(True)
        layout.addWidget(note)
        together = QHBoxLayout()
        self.play_all_button = QPushButton("함께 재생")
        self.pause_all_button = QPushButton("함께 일시정지")
        self.reset_all_button = QPushButton("함께 처음으로")
        for button in (self.play_all_button, self.pause_all_button, self.reset_all_button):
            together.addWidget(button)
        together.addStretch()
        layout.addLayout(together)
        panels = QHBoxLayout()
        self.left = TracePanel("frozen Stage-3 V1")
        self.right = TracePanel("Program K · K-P0 (연구용)")
        panels.addWidget(self.left, 1)
        panels.addWidget(self.right, 1)
        layout.addLayout(panels, 1)
        self.left.state_changed.connect(self.refresh_common_controls)
        self.right.state_changed.connect(self.refresh_common_controls)
        self.play_all_button.clicked.connect(self.play_all)
        self.pause_all_button.clicked.connect(self.pause_all)
        self.reset_all_button.clicked.connect(self.reset_all)
        self.difference = QLabel("이 보드의 K-P0 − V1 차이: 실행 대기")
        self.difference.setWordWrap(True)
        layout.addWidget(self.difference)
        legend = QLabel("초록 ◇: 숨은 논리 지뢰 M · 빨간 ⚑: 물리 깃발 · 주황 테두리: 입력 대상 · 보라 경로: 완료 입력만\n"
                        "CHORD는 숫자 주변의 깃발 수가 맞을 때 주변 숨은 칸을 함께 여는 입력입니다. 자동 WIN 깃발은 입력 수에 포함하지 않습니다.")
        legend.setWordWrap(True)
        layout.addWidget(legend)
        self.draw_button.clicked.connect(lambda: self.run_index(draw_index(self.current_index)))
        self.run_button.clicked.connect(self.run_entered_index)
        self.index_edit.returnPressed.connect(self.run_entered_index)
        self.cancel_button.clicked.connect(self.cancel)
        self.info_button.clicked.connect(self.show_info)
        self.job.finished.connect(self.completed)
        self.job.progressed.connect(self.progressed)
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(100)
        self.status_timer.timeout.connect(self.refresh_status)
        self.set_busy(False)

    def set_busy(self, busy):
        self._busy = busy
        ready = not busy and self.job.state == "idle" and not self._closed
        for widget in (self.draw_button, self.run_button, self.index_edit):
            widget.setEnabled(ready)
        self.cancel_button.setEnabled(busy and self.job.state == "running")
        self.refresh_common_controls()

    def common_ready(self):
        return (not self._closed and not self._busy and self._active_token is None
                and self.job.state == "idle" and self.pair is not None
                and all(p.playback is not None for p in (self.left, self.right)))

    def refresh_common_controls(self):
        ready = self.common_ready()
        panels = (self.left, self.right)
        self.play_all_button.setEnabled(ready and any(
            p.player.current_index < p.player.step_count and not p.playback.running for p in panels))
        self.pause_all_button.setEnabled(ready and any(p.playback.running for p in panels))
        self.reset_all_button.setEnabled(ready and any(
            p.player.current_index or p.playback.partial_modeled_us or p.playback.running for p in panels))

    def play_all(self):
        if self.common_ready():
            for panel in (self.left, self.right):
                panel.play()

    def pause_all(self):
        if self.common_ready():
            for panel in (self.left, self.right):
                panel.pause()

    def reset_all(self):
        if self.common_ready():
            for panel in (self.left, self.right):
                panel.seek(0)

    def run_entered_index(self):
        text = self.index_edit.text().strip()
        if not re.fullmatch(r"[0-9]{1,5}", text):
            self.status.setText("입력 오류: index는 0..99999 정수만 가능합니다. 실행하지 않았습니다.")
            return
        self.run_index(int(text))

    def run_index(self, index):
        if self._closed or self._active_token is not None:
            return
        try:
            validate_index(index)
            token = self.job.start(index)
        except Exception as exc:
            self.status.setText(f"실행 시작 실패: {exc}")
            self.set_busy(False)
            return
        self.current_index = index
        self.index_edit.setText(str(index))
        self._active_token, self._accept_result = token, True
        self.pair = None
        self.left.clear()
        self.right.clear()
        self.identity.setText(f"새 전시 실행 · index {index} · seed {index} · fingerprint는 설치 검증 후 표시")
        self.difference.setText("두 실행의 완료 기록을 기다리는 중입니다.")
        self.set_busy(True)
        self.status_timer.start()
        self.refresh_status()

    def cancel(self):
        self._accept_result = False  # UI cancellation intent precedes all completion delivery
        self.job.cancel()
        self.refresh_status()

    def progressed(self, token, value):
        if token == self._active_token and not self._closed:
            self.refresh_status()

    def refresh_status(self):
        if self._active_token is None:
            return
        if self.job.state == "blocked":
            description = "worker 정리 실패/지연 · 새 실행 차단 · 닫기로 정리 재시도"
        elif self.job.state == "cancelling":
            description = "미완료 · 취소/시간 제한으로 worker 정리 중"
        else:
            value = self.job._phase or {}
            description = PHASE.get(value.get("phase"), "실행 준비 중")
        self.status.setText(f"{description} · 계산 경과 {self.job.elapsed:.1f}s / pair wall cap 120s (관람 시간·Model C와 별개)")
        self.set_busy(True)

    def completed(self, token, status, value):
        if self._closed or type(token) is not int or token != self._active_token:
            return
        accepted = self._accept_result
        self._active_token = None
        self._accept_result = False
        self.status_timer.stop()
        self.set_busy(False)
        if status != "SUCCEEDED" or not accepted:
            labels = {"CANCELLED": "취소됨", "TIMEOUT": "120초 wall cap 초과", "FAILED": "실행/전달/정리 오류"}
            self.status.setText(f"미완료 · {labels.get(status, '결과 설치 취소')} · 승패·승리 시간으로 처리하지 않습니다. 실행 정보 / 진단을 확인하세요.")
            self.difference.setText("비교 결과 N/A · 미완료 요청")
            return
        self.pair = value
        self.left.install(value.v1)
        self.right.install(value.k)
        board = value.board
        self.identity.setText(f"새 전시 실행 · EXPERT_GENERAL_V1 · index {board.index} · seed {board.seed}\n"
                              f"fingerprint: {board.fingerprint}")
        self.identity.setToolTip("새 추첨은 기존 공개 corpus 안의 선택입니다. unseen/holdout·승리·zero opening을 보장하지 않습니다.")
        self.status.setText("계산 완료 · 좌우 재생 버튼으로 독립 관람하세요. 각 패널은 완료 입력 경계에서만 보드·M·비용을 갱신합니다.")
        diff = value.time_to_win_difference_us
        time_text = f"{diff:+,} µs" if diff is not None else "N/A (양쪽 WON이 아님)"
        counts = tuple(k - v for k, v in zip(value.k.counts, value.v1.counts))
        self.difference.setText(f"이 보드의 K-P0 − V1: 입력 {len(value.k.actions) - len(value.v1.actions):+d} · "
                                f"OPEN {counts[0]:+d} / FLAG {counts[1]:+d} / CHORD {counts[2]:+d} · "
                                f"Model C 승리 시간 차이 {time_text}")
        self.info_button.setToolTip("새 실행 source: " + value.source.head +
                                    (" · 미커밋 파일/변경 포함" if value.source.dirty else " · clean"))

    def show_info(self):
        detail = {"request": self.job.last_record, "session_diagnostics": self.job.records,
                  "current_phase": self.job._phase}
        if self.pair is not None:
            detail.update(board=asdict(self.pair.board), source=asdict(self.pair.source))
        box = QMessageBox(self)
        box.setWindowTitle("새 전시 실행 정보 / 진단")
        box.setText("새 전시 실행의 source·보드 식별자 및 계산 진단입니다.\n"
                    "미커밋 구현은 HEAD 커밋의 일부가 아닙니다. 과거 D5 패키지 실행 identity와 구분합니다.")
        box.setDetailedText(json.dumps(detail, ensure_ascii=False, indent=2))
        box.exec_()

    def closeEvent(self, event):
        self._accept_result = False
        self.left.timer.stop()
        self.right.timer.stop()
        for panel in (self.left, self.right):
            if panel.playback:
                panel.playback.cancel_partial()
        self.status_timer.stop()
        try:
            self.job.shutdown()
        except RuntimeError as exc:
            self.status.setText(f"닫기 보류: 소유 worker 정리 실패. 새 실행 차단. 닫기로 재시도하세요. {exc}")
            self.set_busy(False)
            event.ignore()
            return
        self._closed = True
        self._active_token = None
        self.refresh_common_controls()
        event.accept()
