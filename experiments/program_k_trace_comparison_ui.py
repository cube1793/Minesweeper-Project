"""D4.2: two independent presentations of an admitted completed E1 pair.

No evidence IO, gameplay, shared playhead, normalized progress, or answer lookup.
The only cross-panel operation is selecting another already-admitted pair.
"""

from time import monotonic_ns

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSpinBox, QStyle, QVBoxLayout, QWidget,
)

from experiments.program_k_control_trace_adapter import (
    ControlActionView, ControlTraceFrame, ControlTracePresentation,
)
from experiments.program_k_trace_comparison import ProgramKComparisonPair
from experiments.program_k_trace_viewer import (
    CELL_SIZE, INDEX_MODE, MODEL_C_MODE, SUPPORTED_SPEEDS, TICK_MS,
    INDEX_INTERVAL_MIN_MS, INDEX_INTERVAL_MAX_MS, INDEX_INTERVAL_DEFAULT_MS,
    KTracePlayer, KTracePlayback, KPublicCell, _PublicBoard, _MotionOverlay, _FrameSlider, _label,
)


TITLE = "지뢰찾기 알고리즘 비교 — 기존 방식 vs 개선 방식 (Program K)"
FIXED_PAIR_INDICES = ((6, 8), (12, 14), (18, 20), (24, 26))
CASE_LABELS = {"S-LIFECYCLE": "기본 예제", "S-REPLAN": "복합 동작 예제",
               "S-LOSS": "패배 예제", "X-0": "상급 보드 예제"}
STATUS_TEXT = {"PLAYING": "진행 중", "WON": "승리", "LOST": "패배"}
ACTION_TEXT = {"OPEN": "열기 (OPEN)", "FLAG": "깃발 (FLAG)", "CHORD": "동시 열기 (CHORD)"}
PROVENANCE_TEXT = "같은 지뢰 배치에서 기존 방식과 개선 방식의 기록을 비교합니다. 좌우 기록은 각각 독립적으로 재생할 수 있습니다."
LIMITATION_TEXT = "저장된 연구 사례를 보여주는 화면이며, 통계적 성능 검증 결과는 아닙니다."
DIFFERENCE_NOTE = "음수는 개선 방식의 기록값이 기존 방식보다 작다는 뜻입니다."
PROGRAM_K_NOTE = (
    "Program K는 확정한 지뢰를 반드시 즉시 깃발로 표시하지 않고, 필요할 때까지 논리적으로 기억할 수 있습니다."
)
KNOWLEDGE_NOTE = "초록 ◇ = Program K가 지뢰로 확정했지만 아직 깃발을 놓지 않은 칸"
CHORD_NOTE = "동시 열기(CHORD): 숫자 칸 주변의 깃발 수가 숫자와 같을 때 주변 숨은 칸을 한 번에 여는 동작입니다."
LOSS_TIME_NOTE = (
    "양쪽 모두 패배한 사례이므로 승리 시간 비교에는 사용하지 않습니다. "
    "각 실행의 종료 시점 Model C 시간은 좌우에 별도로 표시합니다."
)
MODEL_C_NOTE = (
    "Model C 시간은 마우스 이동과 입력을 모델링한 시간이며, 실제 경과 시간이나 CPU 계산 시간이 아닙니다. "
    "단위 µs는 마이크로초(100만 분의 1초)입니다."
)
CURSOR_DETAIL = (
    "경로는 완료한 입력의 대상 좌표만 연결합니다. 커서의 직선 이동은 표시용 합성이며, "
    "실제 마우스 궤적 기록이 아닙니다. 주황 테두리는 이동 중에는 다음 입력 대상, "
    "그 외에는 마지막 완료 입력 대상입니다."
)


class ControlTracePlayer:
    """CONTROL-only physical navigation; never masquerades as a D1 K model."""

    def __init__(self, presentation):
        if (type(presentation) is not ControlTracePresentation
                or type(presentation.actions) is not tuple or type(presentation.frames) is not tuple
                or not presentation.frames
                or not all(type(a) is ControlActionView for a in presentation.actions)
                or not all(type(f) is ControlTraceFrame for f in presentation.frames)):
            raise TypeError("Expected an admitted immutable CONTROL presentation.")
        self.presentation = presentation
        self._current_index = 0

    @property
    def current_index(self):
        return self._current_index

    @property
    def step_count(self):
        return len(self.presentation.actions)

    @property
    def current_frame(self):
        return self.presentation.frame(self.current_index)

    @property
    def current_action(self):
        return self.presentation.actions[self.current_index - 1] if self.current_index else None

    @property
    def pending_action(self):
        return self.presentation.actions[self.current_index] if self.current_index < self.step_count else None

    @property
    def completed_route(self):
        return self.presentation.completed_route(self.current_index)

    def go_to(self, index):
        frame = self.presentation.frame(index)
        self._current_index = index
        return frame

    def next(self):
        if self.current_index == self.step_count:
            return False
        self.go_to(self.current_index + 1)
        return True

    def previous(self):
        if self.current_index == 0:
            return False
        self.go_to(self.current_index - 1)
        return True


class _ControlBoard(QWidget):
    """Public cells and physical provenance only; no K knowledge layer exists."""

    def __init__(self, width, height):
        super().__init__()
        grid = QGridLayout(self)
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)
        self.cells = {}
        for y in range(height):
            for x in range(width):
                cell = KPublicCell(x, y, self)  # render_state is strictly public glyph presentation.
                self.cells[x, y] = cell
                grid.addWidget(cell, y, x)
        self.setFixedSize(width * CELL_SIZE, height * CELL_SIZE)
        self.overlay = _MotionOverlay(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()

    def render_frame(self, frame):
        self.observation = frame.observation
        for (x, y), cell in self.cells.items():
            cell.render_state(frame.observation[y][x])
            facts = [cell.public_description]
            if (x, y) in frame.explicit_flags:
                facts.append("explicit physical FLAG (executed CONTROL input)")
            if (x, y) in frame.automatic_flags:
                facts.append("automatic WIN flag; no executed FLAG input")
            if cell.public_state in (-4, -5):
                facts.append("terminal public disclosure")
            cell.setToolTip("; ".join(facts))
            cell.setAccessibleName(cell.toolTip())


class _TracePanel(QGroupBox):
    """Research-local physical panel; each instance owns its controller and timer."""

    def __init__(self, *, is_control, clock, parent=None):
        super().__init__("기존 방식" if is_control else "개선 방식 (Program K)", parent)
        self.is_control = is_control
        self.variant = "CONTROL" if is_control else "K-P0"
        identity_note = ("기술 식별자: CONTROL · 기존 Stage-3 V1 물리 실행" if is_control else
                         "기술 식별자: K-P0 · Program K 물리 실행. '개선 방식'은 프로젝트에서 개발한 변형을 뜻하며, 통계적 효과 입증을 뜻하지 않습니다.")
        self.setToolTip(identity_note)
        self.setAccessibleDescription(identity_note)
        self._clock, self._closed = clock, False
        self.player = self.playback = None
        self._rendered_frame = None
        self.setMinimumWidth(470)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self._advance_playback)
        layout = QVBoxLayout(self)
        self.summary_label = _label()
        self.summary_label.setToolTip(CHORD_NOTE)
        layout.addWidget(self.summary_label)
        self.status_label = _label()
        layout.addWidget(self.status_label)
        self.state_label = _label()
        self.state_label.setMinimumHeight(2 * self.state_label.fontMetrics().lineSpacing())
        layout.addWidget(self.state_label)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setMinimumHeight(150)
        self.scroll_area.setAccessibleName(self.variant + " 공개 보드 스크롤 영역")
        layout.addWidget(self.scroll_area, 1)
        toggles = QHBoxLayout()
        self.route_checkbox = QCheckBox("완료 이동 경로 표시")
        self.route_checkbox.setToolTip(CURSOR_DETAIL)
        self.route_checkbox.setChecked(True)
        self.route_checkbox.toggled.connect(self.refresh)
        toggles.addWidget(self.route_checkbox)
        self.knowledge_checkbox = None
        if not is_control:
            self.knowledge_checkbox = QCheckBox("확정한 지뢰 표시 (초록 ◇)")
            self.knowledge_checkbox.setChecked(True)
            self.knowledge_checkbox.toggled.connect(self._knowledge_changed)
            self.knowledge_checkbox.setToolTip(PROGRAM_K_NOTE + "\n" + KNOWLEDGE_NOTE)
            self.knowledge_checkbox.setAccessibleDescription(self.knowledge_checkbox.toolTip())
            toggles.addWidget(self.knowledge_checkbox)
        toggles.addStretch()
        layout.addLayout(toggles)
        navigation = QHBoxLayout()
        for name, caption, icon, callback in (
            ("first_button", "처음", QStyle.SP_MediaSkipBackward, self.on_first),
            ("previous_button", "이전", QStyle.SP_MediaSeekBackward, self.on_previous),
            ("play_button", "재생", QStyle.SP_MediaPlay, self.on_play_pause),
            ("next_button", "다음", QStyle.SP_MediaSeekForward, self.on_next),
            ("last_button", "끝", QStyle.SP_MediaSkipForward, self.on_last),
        ):
            button = QPushButton(caption)
            button.setIcon(self.style().standardIcon(icon))
            button.setAccessibleName(self.variant + " " + caption)
            button.clicked.connect(callback)
            setattr(self, name, button)
            navigation.addWidget(button)
        layout.addLayout(navigation)
        self.slider = _FrameSlider(Qt.Horizontal)
        self.slider.setAccessibleName(self.variant + " 완료한 입력 수")
        self.slider.valueChanged.connect(self.seek)
        self.slider.sliderPressed.connect(self.cancel_partial)
        self.slider.trackPressed.connect(self.cancel_partial)
        layout.addWidget(self.slider)
        timing = QHBoxLayout()
        self.mode_combo = QComboBox()
        for caption, mode in (("입력 순서", INDEX_MODE), ("Model C 시간", MODEL_C_MODE)):
            self.mode_combo.addItem(caption, mode)
        self.mode_combo.setAccessibleName(self.variant + " 재생 기준")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(INDEX_INTERVAL_MIN_MS, INDEX_INTERVAL_MAX_MS)
        self.interval_spin.setValue(INDEX_INTERVAL_DEFAULT_MS)
        self.interval_spin.setSuffix(" ms/입력")
        self.interval_spin.setKeyboardTracking(False)
        self.interval_spin.setAccessibleName(self.variant + " 입력 간격")
        self.speed_combo = QComboBox()
        for text, speed in zip(("0.25×", "0.5×", "1×", "2×", "4×", "8×"), SUPPORTED_SPEEDS):
            self.speed_combo.addItem(text, speed)
        self.speed_combo.setCurrentIndex(2)
        self.speed_combo.setAccessibleName(self.variant + " Model C 배속")
        for caption, widget in (("재생 기준", self.mode_combo), ("입력 간격", self.interval_spin), ("배속", self.speed_combo)):
            timing.addWidget(QLabel(caption))
            timing.addWidget(widget)
        layout.addLayout(timing)
        self.playback_label = _label()
        layout.addWidget(self.playback_label)
        layout.addWidget(_label("마지막 완료 입력 · 좌표는 0부터 시작"))
        details = QGridLayout()
        self.detail_labels = {}
        captions = [("ordinal", "순번"), ("action", "동작"), ("target", "대상 좌표"),
                    ("cursor_before", "이전 커서"), ("modeled_action_us", "동작 Model C 시간"),
                    ("cumulative_modeled_us", "누적 Model C 시간"), ("status_after", "실행 후 상태")]
        if not is_control:
            captions.append(("category", "동작 분류"))
        for i, (key, caption) in enumerate(captions):
            row, col = divmod(i, 2)
            details.addWidget(QLabel(caption + ":"), row, col * 2)
            label = _label()
            label.setMinimumWidth(55)
            self.detail_labels[key] = label
            details.addWidget(label, row, col * 2 + 1)
        layout.addLayout(details)
        self.error_label = _label()
        self.error_label.setStyleSheet("color: #b00000;")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.mode_combo.currentIndexChanged.connect(lambda _: self._operate(lambda: self.playback.set_mode(self.mode_combo.currentData())))
        self.interval_spin.valueChanged.connect(lambda value: self._operate(lambda: self.playback.set_index_interval(value)))
        self.speed_combo.currentIndexChanged.connect(lambda _: self._operate(lambda: self.playback.set_speed(self.speed_combo.currentData())))

    def load_trace(self, presentation, facts):
        self.cancel_partial()
        self.player = ControlTracePlayer(presentation) if self.is_control else KTracePlayer(presentation)
        # KTracePlayback's accepted physical timing bridge reads pending_action,
        # modeled_action_us, step_count/current_index/next only. No K state/labels.
        self.playback = KTracePlayback(self.player, clock=self._clock)
        self.playback.set_index_interval(self.interval_spin.value())
        self.playback.set_mode(self.mode_combo.currentData())
        self.playback.set_speed(self.speed_combo.currentData())
        self._rendered_frame = None
        old_board = self.scroll_area.takeWidget()
        if old_board is not None:
            old_board.deleteLater()
        self.board = (_ControlBoard if self.is_control else _PublicBoard)(presentation.case.width, presentation.case.height)
        self.scroll_area.setWidget(self.board)
        self.summary_label.setText(
            f"기록 결과: {STATUS_TEXT[facts.outcome]} · 입력 {facts.total_inputs} · "
            f"열기 {facts.open_inputs} · 깃발 {facts.flag_inputs} · 동시 열기 {facts.chord_inputs}\n"
            f"최종 Model C 시간: {facts.model_c_total_us:,} µs · 직접 깃발 {facts.explicit_physical_flags} · "
            f"승리 시 자동 깃발 {facts.automatic_win_flags}")
        self.refresh()

    def seek(self, index):
        if self._closed:
            return
        self.player.presentation.frame(index)
        self.cancel_partial()
        self.player.go_to(index)
        self.refresh()

    def on_first(self):
        self.seek(0)

    def on_previous(self):
        self.seek(max(0, self.player.current_index - 1))

    def on_next(self):
        self.seek(min(self.player.step_count, self.player.current_index + 1))

    def on_last(self):
        self.seek(self.player.step_count)

    def cancel_partial(self):
        self.timer.stop()
        if self.playback is not None:
            self.playback.cancel_partial()
            self.refresh()
        self.error_label.hide()

    def on_play_pause(self):
        if not self._closed:
            self._operate(self.playback.pause if self.playback.running else self.playback.play)

    def _advance_playback(self):
        if not self._closed and self.timer.isActive():
            self._operate(self.playback.update)

    def _operate(self, operation):
        if self._closed:
            return
        try:
            operation()
        except Exception as exc:
            self.timer.stop()
            self.error_label.setText(f"재생 중단: {exc}")
            self.error_label.show()
        else:
            self.error_label.hide()
        self.refresh()

    def _knowledge_changed(self, checked):
        if not self._closed and self.player is not None:
            self.board.show_knowledge(checked)  # Does not sample either clock or refresh motion.

    def refresh(self, *_):
        if self._closed or self.player is None:
            return
        player, playback = self.player, self.playback
        frame, action = player.current_frame, player.current_action
        index, count = player.current_index, player.step_count
        if self._rendered_frame is not frame:
            if self.is_control:
                self.board.render_frame(frame)
                state = ""
            else:
                self.board.render(frame.observation)
                self.board.render_knowledge(frame)
                self.board.show_knowledge(self.knowledge_checkbox.isChecked())
                state = (f"확정한 지뢰: {len(frame.logical_mines)} · "
                         f"그중 숨은 칸: {len(frame.hidden_logical_mines)}\n")
            self.state_label.setText(state + f"직접 깃발: {len(frame.explicit_flags)} · "
                                     f"승리 시 자동 깃발: {len(frame.automatic_flags)}")
            self.board.overlay.targets = player.completed_route
            self.status_label.setText(f"현재 프레임 {index} / {count} · 상태: {STATUS_TEXT[frame.status]}")
            values = {"cumulative_modeled_us": f"{frame.cumulative_modeled_us:,} µs"}
            if action is not None:
                values.update(ordinal=f"{action.input_index + 1} / {count}", action=ACTION_TEXT[action.action],
                              target=str(action.target), cursor_before=str(action.cursor_before),
                              modeled_action_us=f"{action.modeled_action_us:,} µs", status_after=STATUS_TEXT[action.status_after])
                if not self.is_control:
                    values["category"] = action.category
            for name, label in self.detail_labels.items():
                label.setText(values.get(name, "—"))
            blocked = self.slider.blockSignals(True)
            self.slider.setRange(0, count)
            self.slider.setValue(index)
            self.slider.blockSignals(blocked)
            self._rendered_frame = frame
        partial = playback.pending_trace is not None and (playback.running or playback.progress > 0)
        self.board.overlay.show_route = self.route_checkbox.isChecked()
        self.board.overlay.present(frame.cursor, playback.pending_trace if partial else action,
                                   playback.progress if partial else None)
        for button in (self.first_button, self.previous_button):
            button.setEnabled(index > 0)
        for button in (self.next_button, self.last_button, self.play_button):
            button.setEnabled(index < count)
        self.play_button.setText("일시정지" if playback.running else "재생")
        self.play_button.setAccessibleName(self.variant + " " + self.play_button.text())
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause if playback.running else QStyle.SP_MediaPlay))
        if playback.running:
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()
        modeled = playback.mode == MODEL_C_MODE
        self.interval_spin.setEnabled(not modeled)
        self.speed_combo.setEnabled(modeled)
        for widget, setter, value in (
            (self.mode_combo, self.mode_combo.setCurrentIndex, self.mode_combo.findData(playback.mode)),
            (self.interval_spin, self.interval_spin.setValue, playback.index_interval_ms),
            (self.speed_combo, self.speed_combo.setCurrentIndex, SUPPORTED_SPEEDS.index(playback.model_speed)),
        ):
            blocked = widget.blockSignals(True)
            setter(value)
            widget.blockSignals(blocked)
        rate = f"Model C 시간 · {self.speed_combo.currentText()}" if modeled else f"입력 순서 · {playback.index_interval_ms} ms/입력"
        self.playback_label.setText(f"{'재생 중' if playback.running else '일시정지'} · {rate} · 표시용 재생")

    def shutdown(self):
        self.timer.stop()
        if self.playback is not None:
            self.playback.cancel_partial()
        self._closed = True


class ProgramKComparisonWindow(QWidget):
    """The pair selector owns identity only; both panels own their own clocks."""

    closed = pyqtSignal()

    def __init__(self, pairs, parent=None, *, control_clock=monotonic_ns, kp0_clock=monotonic_ns):
        if (type(pairs) is not tuple or not pairs or not all(type(p) is ProgramKComparisonPair for p in pairs)
                or len({p.control.case.schedule_index for p in pairs}) != len(pairs)
                or any((p.control.case.schedule_index, p.kp0.case.schedule_index) not in FIXED_PAIR_INDICES for p in pairs)):
            raise TypeError("Supply distinct admitted D4.1 ProgramKComparisonPair objects.")
        super().__init__(parent, Qt.Window)
        self.pairs = pairs
        self._closed = False
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(TITLE)
        layout = QVBoxLayout(self)
        title = _label(TITLE)
        title.setFont(QFont("Arial", 13, QFont.Bold))
        layout.addWidget(title)
        self.pair_selector = QComboBox()
        self.pair_selector.setAccessibleName("보존된 동일 보드 사례")
        for p in pairs:
            identity = p.identity
            self.pair_selector.addItem(f"{CASE_LABELS[identity.case_id]} · {identity.width}×{identity.height} / 지뢰 {identity.num_mines}", identity.case_id)
            provenance = (f"연구 기록 상세 정보\n내부 기록 ID: {identity.case_id}\n승인 E1: {identity.run_id}\n"
                          f"반복 {identity.repetition} · 최초 열기 {identity.first_click}\n"
                          f"CONTROL 기록 {identity.control_schedule_index} ↔ K-P0 기록 {identity.kp0_schedule_index}\n"
                          f"동일 보드 지문 (CONTROL = K-P0): {identity.board_fingerprint}")
            for role in (Qt.ToolTipRole, Qt.AccessibleDescriptionRole):
                self.pair_selector.setItemData(self.pair_selector.count() - 1, provenance, role)
        layout.addWidget(self.pair_selector)
        self.identity_label = _label(PROVENANCE_TEXT)
        layout.addWidget(self.identity_label)
        self.limitation_label = _label(LIMITATION_TEXT)
        self.limitation_label.setToolTip("Program K 효과는 입증되지 않았으며, Gate-P 자격이나 공식 Stage-3 교체를 의미하지 않습니다.")
        layout.addWidget(self.limitation_label)
        self.difference_heading, self.difference_label, self.difference_note = _label(), _label(), _label()
        self.difference_heading.setFont(QFont("Arial", 10, QFont.Bold))
        difference_header = QHBoxLayout()
        difference_header.addWidget(self.difference_heading)
        self.model_c_label = _label("Model C: 마우스 이동·입력의 모델 시간 ⓘ")
        self.model_c_label.setToolTip(MODEL_C_NOTE)
        self.model_c_label.setAccessibleDescription(MODEL_C_NOTE)
        difference_header.addWidget(self.model_c_label)
        layout.addLayout(difference_header)
        layout.addWidget(self.difference_label)
        layout.addWidget(self.difference_note)
        panels = QHBoxLayout()
        self.control_panel = _TracePanel(is_control=True, clock=control_clock, parent=self)
        self.kp0_panel = _TracePanel(is_control=False, clock=kp0_clock, parent=self)
        panels.addWidget(self.control_panel, 1)
        panels.addWidget(self.kp0_panel, 1)
        layout.addLayout(panels, 1)
        self.legend_label = _label(
            "표시 안내: 초록 ◇ = 개선 방식이 지뢰로 확정했지만 아직 깃발을 놓지 않은 칸 · 빨간 깃발 = 실제 깃발 · "
            "파란 원 = 합성 커서 · 주황 테두리 = 현재 대상 · 보라 선 = 완료된 이동 경로")
        self.legend_label.setToolTip(KNOWLEDGE_NOTE + "\n" + CURSOR_DETAIL)
        self.legend_label.setAccessibleDescription(self.legend_label.toolTip())
        layout.addWidget(self.legend_label)
        self.pair_selector.currentIndexChanged.connect(self.select_pair)
        self.select_pair(0)
        available = self.screen().availableGeometry()
        self.resize(min(1500, available.width()), min(1000, available.height()))

    def select_pair(self, index):
        if self._closed:
            return
        if type(index) is not int or not 0 <= index < len(self.pairs):
            raise ValueError("Invalid admitted pair index.")
        self.control_panel.cancel_partial()
        self.kp0_panel.cancel_partial()
        self.current_pair = self.pairs[index]
        p = self.current_pair
        self.control_panel.load_trace(p.control, p.control_facts)
        self.kp0_panel.load_trace(p.kp0, p.kp0_facts)
        blocked = self.pair_selector.blockSignals(True)
        self.pair_selector.setCurrentIndex(index)
        self.pair_selector.blockSignals(blocked)
        provenance = self.pair_selector.itemData(index, Qt.ToolTipRole)
        for widget in (self.identity_label, self.pair_selector):
            widget.setToolTip(provenance)
            widget.setAccessibleDescription(provenance)
        d = p.difference
        self.difference_heading.setText("이 사례의 기록상 차이 (개선 방식 − 기존 방식)")
        self.difference_heading.setToolTip(d.label + " — " + d.direction)
        self.difference_heading.setAccessibleDescription(self.difference_heading.toolTip())
        signed = lambda value: f"{value:+,}" if value else "0"
        cost = "비교하지 않음" if d.model_c_us is None else signed(d.model_c_us) + " µs"
        self.difference_label.setText(f"입력 수 차이 {signed(d.total_inputs)} · 열기 {signed(d.open_inputs)} · "
                                      f"깃발 {signed(d.flag_inputs)} · 동시 열기 {signed(d.chord_inputs)} · Model C 시간 차이: {cost}")
        self.difference_note.setText(DIFFERENCE_NOTE + ("\n" + LOSS_TIME_NOTE if d.model_c_us is None else ""))

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted() and not self._closed:
            self.control_panel.shutdown()
            self.kp0_panel.shutdown()
            self._closed = True
            self.closed.emit()
