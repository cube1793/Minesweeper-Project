"""Inspection of already authenticated, immutable exemplar evidence.

No loading, reconstruction, decisions or ZiNi calculation belongs here.
The shared job owns asynchronous ZiNi work; this UI owns board selection/cache.
Index and Model C Time playback are presentation timing only.
The answer layer is a renderer-only reference; all ordinary cell text describes
the stored public frame. Each game/solver pair owns one inspection position.
"""

from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction

from PyQt5.QtCore import QElapsedTimer, QEvent, QPointF, QRectF, QSize, Qt, QSignalBlocker, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygonF, QValidator
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGraphicsOpacityEffect, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QSlider, QSpinBox, QDoubleSpinBox, QStyle, QStyleOptionSlider, QStyleOptionSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)

from core_engine import CellState, GameStatus
from exemplar_board_evidence import AcceptedExemplarEvidence, LoadedExemplar
from zini_metric_job import ZiniMetricJob


CELL_SIZE = 28
INDEX_MODE = 'Index'
MODEL_TIME_MODE = 'Model C Time'
PRESENTATION_TICK_MS = 16
QT_SLIDER_MAX = 2**31 - 1
NUMBER_COLORS = {1: '#0000ff', 2: '#008000', 3: '#ff0000', 4: '#000080',
                 5: '#800000', 6: '#008080', 7: '#000000', 8: '#808080'}
COUNTER_ROWS = ('Time (Model C)', 'Est Time (Model C)', '3BV', '3BV/s (Model C)', 'Clicks', 'Left', 'Right',
                'Chord', 'CPS (Model C)', 'Efficiency', 'IOE', 'Ops', 'Thrp', 'Corr',
                'ZiNi', 'ZNE', 'ZNT')
TRANSITION_NOTE = 'Action-target transition — not recorded cursor trajectory'
ROUTE_NOTE = 'Action-target route — not recorded cursor trajectory'
CURSOR_NOTE = (
    'Synthetic smooth interpolation between executed action targets. '
    'Not recorded mouse motion or an actual OS cursor trajectory. '
    'Smoothstep is presentation easing, not calibrated acceleration. '
    'Model C action duration is not measured movement-only duration; Model C timing remains unchanged.'
)
ZINI_NOTE = ('Bounded best-so-far board reference, not an exact minimum. '
             'ZNE/ZNT use displayed-frame total/active clicks for final WIN runs only.')
MODEL_NOTE = (
    'Both timelines are post-hoc Model C evaluations of persisted actions. '
    'Stage 2 did not natively declare Model C; Stage 3 declared it during collection, '
    'but these events retain no native per-action cost/cursor fields. '
    'This is modeled physical execution time, not Replay elapsed, CPU decision '
    'time or recorded cursor trajectory.'
)
ESTIMATE_NOTE = (
    "Current modeled estimate extrapolates total 3BV from the displayed prefix's "
    'Model C 3BV/s; it is not observed gameplay time or a predicted solver finish. '
    'It is not time-to-win, including on LOSS.'
)
COMPUTE_NOTE = (
    'Stage 2: analysis diagnostic. Stage 3: analysis + planning diagnostic. '
    'Historical scopes/environments differ; no cross-stage compute-speed winner.'
)
CANDIDATE_NOTE = (
    'Stage-2 probability-guess candidate count is the persisted exact-minimum-risk '
    'tie multiplicity / final selector pool size. Missing Stage-3 count remains unavailable.'
)


@dataclass(frozen=True)
class _ModeledPrefix:
    seconds: Fraction
    estimated_seconds: Fraction | None
    bbbv_per_second: Fraction | None
    clicks_per_second: Fraction | None


def _modeled_prefix(cumulative_us, completed_3bv, total_3bv, frame_index):
    """One exact presentation calculation; integer Model C us remain authority."""
    return _ModeledPrefix(
        Fraction(cumulative_us, 1_000_000),
        Fraction(total_3bv * cumulative_us, completed_3bv * 1_000_000)
        if cumulative_us and completed_3bv else None,
        Fraction(completed_3bv * 1_000_000, cumulative_us) if cumulative_us else None,
        Fraction(frame_index * 1_000_000, cumulative_us) if cumulative_us else None,
    )


def _decimal(value, places):
    if value is None:
        return '-'
    # Exact rational rounding, including ties to even; no binary float authority.
    whole, fraction = divmod(round(value * 10 ** places), 10 ** places)
    return f'{whole}.{fraction:0{places}d}'


@dataclass(frozen=True)
class _Position:
    action_ordinal: int | None = None
    before: bool = False

    @property
    def frame_index(self):
        return 0 if self.action_ordinal is None else self.action_ordinal - int(self.before)


def _label(text=''):
    label = QLabel(text)
    label.setTextFormat(Qt.PlainText)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    return label


def _fact(value):
    if value is None:
        return 'unavailable'
    if isinstance(value, Fraction):
        return f'{value.numerator}/{value.denominator}'
    return str(value)


def _modeled_time(microseconds):
    """Exact seconds presentation; the integer microseconds remain authority."""
    return f'{microseconds} us ({_seconds(microseconds)} s)'


def _seconds(microseconds):
    seconds, remainder = divmod(microseconds, 1_000_000)
    return f'{seconds}.{remainder:06d}'


class _DirectEntry(QSpinBox):
    """Own Return/Enter explicitly; focus loss only edits the displayed value."""

    commit_requested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.commit_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class _IndexInterval(QSpinBox):
    """Keep out-of-range integer edits intact until Qt commits and clamps them."""

    def validate(self, text, pos):
        value = text.removesuffix(self.suffix()).strip()
        try:
            integer = int(value)
        except ValueError:
            if value in ('-', '+'):
                return QValidator.Intermediate, text, pos
        else:
            if not self.minimum() <= integer <= self.maximum():
                return QValidator.Intermediate, text, pos
        return super().validate(text, pos)

    def fixup(self, text):
        try:
            value = int(text.removesuffix(self.suffix()).strip())
        except ValueError:
            return super().fixup(text)
        return str(max(self.minimum(), min(self.maximum(), value))) + self.suffix()

    def fit_text_width(self):
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        metrics = self.fontMetrics()
        text_width = max(metrics.horizontalAdvance(self.specialValueText()),
                         metrics.horizontalAdvance(str(self.maximum()) + self.suffix()))
        margin = metrics.horizontalAdvance('  ') + self.style().pixelMetric(QStyle.PM_DefaultFrameWidth, option, self)
        content = QSize(text_width + margin, metrics.height())
        size = self.style().sizeFromContents(QStyle.CT_SpinBox, option, content, self)
        self.setFixedWidth(size.width())

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.StyleChange, QEvent.ApplicationFontChange):
            self.fit_text_width()


class _FrameSlider(QSlider):
    """Viewer-local track seeking; Qt retains ordinary handle dragging."""

    manual_seek = pyqtSignal()
    track_seek = pyqtSignal(int)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.manual_seek.emit()
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            handle = self.style().subControlRect(
                QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
            if not handle.contains(event.pos()):
                span = max(1, self.width() - handle.width())
                position = max(0, min(span, event.x() - handle.width() // 2))
                self.track_seek.emit(QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), position, span, option.upsideDown))
                event.accept()
                return
        super().mousePressEvent(event)


class _AnswerGlyph(QWidget):
    """Painted glyph, with no QLabel text exposed to ordinary accessibility."""

    def __init__(self, parent):
        super().__init__(parent)
        self.glyph = ''
        self.color = '#000000'
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAccessibleName('')
        self.setAccessibleDescription('')
        opacity = QGraphicsOpacityEffect(self)
        opacity.setOpacity(0.35)
        self.setGraphicsEffect(opacity)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.parentWidget().font())
        painter.setPen(QColor(self.color))
        painter.drawText(self.rect(), Qt.AlignCenter, self.glyph)


class ExemplarViewerCell(QLabel):
    """Public cell plus independent, optional hidden-answer decoration."""

    def __init__(self, x, y, parent=None):
        super().__init__(parent)
        self.coordinate = (x, y)
        self.setFixedSize(CELL_SIZE, CELL_SIZE)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont('Arial', 14, QFont.Bold))
        self.setTextFormat(Qt.PlainText)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.NoFocus)
        self.answer_layer = _AnswerGlyph(self)
        self.answer_layer.setGeometry(self.rect())
        self.render_state(CellState.HIDDEN)

    def render_state(self, value, *, newly_safe=False, answer=None):
        self.logical_state = value
        self.newly_safe = newly_safe
        background, color, border = '#c0c0c0', '#000000', '2px outset #ffffff'
        if value == CellState.HIDDEN:
            text, description = '', 'HIDDEN'
        elif value == CellState.FLAGGED:
            text, description, color = '⚑', 'FLAGGED', '#c00000'
        elif value == CellState.EXPLODED:
            text, description, background = '✹', 'EXPLODED', '#ff5555'
            border = '1px solid #a0a0a0'
        elif value == CellState.MINE:
            text, description, border = '✹', 'MINE', '1px solid #a0a0a0'
        elif value == CellState.FALSE_FLAG:
            text, description, color = '×', 'FALSE_FLAG', '#c00000'
            background, border = '#e0e0e0', '1px solid #a0a0a0'
        elif 0 <= value <= 8:
            text, description = str(value) if value else '', f'Revealed {value}'
            color = NUMBER_COLORS.get(value, '#000000')
            background, border = '#d8f0dd' if newly_safe else '#e0e0e0', '1px solid #a0a0a0'
        else:
            raise ValueError(f'Unsupported public cell state: {value}')
        self.setText(text)
        self.setToolTip(f'{self.coordinate}: {description}')
        self.setAccessibleName(self.toolTip())
        self.setStyleSheet(f'QLabel {{ background: {background}; color: {color}; '
                          f'border: {border}; margin: 0px; padding: 0px; }}')
        glyph = ''
        if value == CellState.HIDDEN and answer is not None:
            glyph = '✹' if answer == -1 else str(answer) if answer else ''
        self.answer_layer.glyph = glyph
        self.answer_layer.color = NUMBER_COLORS.get(answer, '#000000')
        self.answer_layer.setVisible(bool(glyph))
        self.answer_layer.update()


class _TargetOverlay(QWidget):
    ROUTE_COLOR = QColor(90, 70, 115, 165)
    ROUTE_WIDTH = 2.0

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.previous_target = self.current_target = None
        self.route_targets = ()
        self.show_route = False
        self.cursor_center = QPointF()

    @property
    def transition_line(self):
        if self.previous_target is None or self.previous_target == self.current_target:
            return None
        return self.previous_target, self.current_target

    @staticmethod
    def center(target):
        return QPointF((target[0] + 0.5) * CELL_SIZE, (target[1] + 0.5) * CELL_SIZE)

    @classmethod
    def interpolated_center(cls, start, target, progress):
        # Same rendering-edge smoothstep as the accepted Stage-3 Visualizer.
        # This floating-point geometry never feeds back into either timing mode.
        u = max(0.0, min(1.0, float(progress)))
        q = u * u * (3 - 2 * u)
        a, b = cls.center(start), cls.center(target)
        return a + (b - a) * q

    def set_cursor_center(self, point):
        if point == self.cursor_center:
            return
        previous, self.cursor_center = self.cursor_center, point
        # Qt unions these small dirty rectangles. The historical route and
        # underlying cells outside them need no repaint during partial motion.
        for center in (previous, point):
            self.update(QRectF(center.x() - 12, center.y() - 12, 24, 24).toAlignedRect())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        if self.show_route and len(self.route_targets) > 1:
            # Subdued sequence geometry, below the selected transition/markers.
            # Repeated points stay repeated; there is no synthetic origin or detour.
            route = QPolygonF([self.center(target) for target in self.route_targets])
            painter.setPen(QPen(QColor(255, 255, 255, 100), 3.5))
            painter.drawPolyline(route)
            painter.setPen(QPen(self.ROUTE_COLOR, self.ROUTE_WIDTH))
            painter.drawPolyline(route)
        if self.transition_line is not None:
            start, end = map(self.center, self.transition_line)
            painter.setPen(QPen(QColor('#ffffff'), 4))
            painter.drawLine(start, end)
            painter.setPen(QPen(QColor('#2463c5'), 2))
            painter.drawLine(start, end)
        if self.previous_target is not None:
            painter.setPen(QPen(QColor('#2463c5'), 2))
            painter.drawEllipse(self.center(self.previous_target), 8, 8)
        if self.current_target is not None:
            x, y = self.current_target
            painter.setPen(QPen(QColor('#cc7000'), 2))
            painter.drawRect(x * CELL_SIZE + 2, y * CELL_SIZE + 2, CELL_SIZE - 4, CELL_SIZE - 4)
        # Accepted small hollow-ring convention; teal distinguishes it from
        # the blue previous-target marker. Draw last, above both route/context.
        painter.setPen(QPen(QColor('#ffffff'), 4))
        painter.drawEllipse(self.cursor_center, 9, 9)
        painter.setPen(QPen(QColor('#007a58'), 2))
        painter.drawEllipse(self.cursor_center, 9, 9)


class _PublicBoard(QWidget):
    def __init__(self):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(0)
        self.cells = {}
        self._shape = None
        self.targets = _TargetOverlay(self)

    def present(self, snapshot, frame, new_safe, previous, current, show_answers,
                route_targets=(), show_route=False):
        shape = snapshot.width, snapshot.height
        if self._shape != shape:
            for cell in self.cells.values():
                self.grid.removeWidget(cell)
                cell.hide()
                cell.deleteLater()
            self.cells = {}
            for y in range(snapshot.height):
                for x in range(snapshot.width):
                    cell = ExemplarViewerCell(x, y, self)
                    self.cells[x, y] = cell
                    self.grid.addWidget(cell, y, x)
            self._shape = shape
            self.setFixedSize(snapshot.width * CELL_SIZE, snapshot.height * CELL_SIZE)
            self.targets.setGeometry(self.rect())
        for (x, y), cell in self.cells.items():
            value = frame.observation[y][x]
            answer = None
            if show_answers and value == CellState.HIDDEN:
                answer = -1 if (x, y) in snapshot.mines else snapshot.adjacent[y][x]
            cell.render_state(value, newly_safe=(x, y) in new_safe, answer=answer)
        self.targets.previous_target, self.targets.current_target = previous, current
        self.targets.route_targets, self.targets.show_route = route_targets, show_route
        self.targets.raise_()
        self.targets.update()


class ExemplarBoardViewerWindow(QWidget):
    """One immutable evidence bundle; eight independent inspection positions."""

    def __init__(self, evidence: AcceptedExemplarEvidence, parent=None):
        if not isinstance(evidence, AcceptedExemplarEvidence):
            raise ValueError('An already-loaded AcceptedExemplarEvidence bundle is required.')
        if (not isinstance(evidence.exemplars, tuple) or len(evidence.exemplars) != 4
                or any(not isinstance(game, LoadedExemplar) for game in evidence.exemplars)
                or len({game.reference.game_index for game in evidence.exemplars}) != 4):
            raise ValueError('Exactly four distinct loaded exemplars are required.')
        super().__init__(parent, Qt.Window)
        self.evidence = evidence
        self._games = {game.reference.game_index: game for game in evidence.exemplars}
        self._positions = {(index, solver): _Position() for index in self._games
                           for solver in ('stage2', 'stage3')}
        self._cumulative = {}
        self._targets = {}
        for pair in self._positions:
            timeline = getattr(self._games[pair[0]], pair[1]).timeline
            times = tuple(action.cumulative_modeled_us for action in timeline.actions)
            if (type(timeline.total_modeled_us) is not int
                    or not 0 < timeline.total_modeled_us <= QT_SLIDER_MAX
                    or not times or times[-1] != timeline.total_modeled_us
                    or any(type(t) is not int or not 0 < t <= QT_SLIDER_MAX for t in times)
                    or any(left >= right for left, right in zip(times, times[1:]))):
                raise ValueError('Model C completion times must increase within the Qt integer slider range.')
            self._cumulative[pair] = times
            self._targets[pair] = tuple((action.event.x, action.event.y) for action in timeline.actions)
        self._playheads = dict.fromkeys(self._positions, 0)
        self._playback_mode = INDEX_MODE
        self._speed_quarters = 4
        self._wall_clock = QElapsedTimer()
        self._anchor_model_us = 0
        self._index_interval_ms = 200
        self._index_partial = Fraction(0)
        self._anchor_index = Fraction(0)
        self._play_pair = None
        self._zini_job = ZiniMetricJob()
        self._zini_cache = {}
        self._zini_key = None
        self._zini_token = 0
        self._zini_failed = False
        self._zini_timer = QTimer(self)
        self._zini_timer.setInterval(100)
        self._zini_timer.timeout.connect(self._poll_zini)
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(PRESENTATION_TICK_MS)
        self.play_timer.setTimerType(Qt.PreciseTimer)
        self.play_timer.timeout.connect(self._advance_playback)
        self.setWindowTitle('Selected Exemplar Board-State Viewer — human interpretation')
        # Only very small screens need to scroll the controls as well as facts.
        # A viewport prevents the content's minimum size exceeding the screen.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.content_scroll = QScrollArea()
        self.content_scroll.setFrameShape(QScrollArea.NoFrame)
        self.content_scroll.setWidgetResizable(True)
        content = QWidget()
        self.content_scroll.setWidget(content)
        outer.addWidget(self.content_scroll)
        layout = QHBoxLayout(content)
        self.fact_tabs = QTabWidget()
        self.fact_tabs.setMinimumWidth(330)
        self.fact_tabs.setMaximumWidth(450)
        self.fact_scrolls = {}
        reference = self._fact_tab('Reference')
        self.reference_values = self._group(reference, 'Board / Solver Reference', (
            'Game index', 'Accepted category', 'Solver', 'Final recorded outcome',
            'Action count', 'Board fingerprint', 'Total 3BV', 'Total Ops', 'Isolated-number count'))
        self.policy_note = _label()
        reference.addWidget(self.policy_note)
        reference.addWidget(_label('3BV / Ops / isolated number count = answer-derived board references, '
                              'not solver-visible evidence.'))
        reference.addStretch()
        counters = self._fact_tab('Counters')
        self.counter_values = self._group(counters, 'Classic Counters', COUNTER_ROWS,
            'Reconstructed Counters — displayed frame; current Engine semantics')
        counters.addWidget(_label('Time rows use Model C, not historical elapsed time.'))
        counters.addWidget(_label('Active/wasted is mechanical, not a strategy grade.'))
        self.zini_status = _label()
        self.zini_status.setToolTip(ZINI_NOTE)
        counters.addWidget(self.zini_status)
        counters.addStretch()
        model = self._fact_tab('Model C')
        self.model_values = self._group(model, 'Model C', (
            'Selected Action Model C Cost', 'Cumulative Model C Time',
            'Current Modeled Est Time', 'Current Modeled 3BV/s', 'Current Modeled CPS', 'Final Model C Time',
            'Final Modeled 3BV/s', 'Final Modeled CPS', 'Initial Model C cursor'))
        self.model_values['Current Modeled Est Time'].setToolTip(ESTIMATE_NOTE)
        self.cost_note = _label()
        model.addWidget(self.cost_note)
        model_note = _label('Model C = modeled physical execution cost; not Replay time or recorded cursor motion.')
        model_note.setToolTip(MODEL_NOTE)
        model.addWidget(model_note)
        model.addWidget(_label('Selected cost: selected action. Cumulative/current: displayed frame. '
                               'Final total/rates: complete recorded run.'))
        model.addStretch()
        action = self._fact_tab('Action')
        self.action_values = self._group(action, 'Action Context', (
            'Selected ordinal', 'Displayed frame', 'Action type', 'Current target',
            'Previous recorded target', 'Current reconstructed status', 'Recorded final outcome',
            'dx', 'dy', 'd²', 'Selected Model C action us', 'Cumulative Model C us',
            'Inference category', 'Target mine probability', 'Minimum available mine probability',
            'Candidate count', 'Decision compute (ns)', 'Recorded safe reveal delta',
            'Reconstructed new-safe count', 'Explicit flag delta'))
        self.action_values['Candidate count'].setToolTip(CANDIDATE_NOTE)
        self.action_values['Decision compute (ns)'].setToolTip(COMPUTE_NOTE)
        action.addStretch()
        layout.addWidget(self.fact_tabs, 1)

        main = QVBoxLayout()
        layout.addLayout(main, 3)
        selectors = QHBoxLayout()
        self.game_selector, self.solver_selector = QComboBox(), QComboBox()
        for index in self._games:
            self.game_selector.addItem(str(index), index)
        for text, role in (('Stage 2', 'stage2'), ('Stage 3', 'stage3')):
            self.solver_selector.addItem(text, role)
        selectors.addWidget(QLabel('Exemplar'))
        selectors.addWidget(self.game_selector)
        selectors.addWidget(QLabel('Solver'))
        selectors.addWidget(self.solver_selector)
        selectors.addStretch()
        main.addLayout(selectors)
        self.frame_label, self.action_label, self.inspection_label = _label(), _label(), _label()
        position_labels = QHBoxLayout()
        for label in (self.frame_label, self.action_label):
            position_labels.addWidget(label)
        main.addLayout(position_labels)
        main.addWidget(self.inspection_label)
        self.status_label = _label()
        main.addWidget(self.status_label)
        sequence_note = _label('Independent sequences — equal indices do not mean equal progress.')
        sequence_note.setMaximumHeight(sequence_note.fontMetrics().lineSpacing() * 2)
        sequence_note.setToolTip('No shared execution clock or normalized progress. '
                                'Index intervals and Model C Time speed are presentation scaling only.')
        main.addWidget(sequence_note)
        board_group = QGroupBox('Board Presentation — Public View')
        board_layout = QVBoxLayout(board_group)
        self.board = _PublicBoard()
        self.board_scroll = QScrollArea()
        self.board_scroll.setWidget(self.board)
        self.board_scroll.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        board_layout.addWidget(self.board_scroll)
        main.addWidget(board_group, 1)
        controls = QHBoxLayout()
        self.first_button = QPushButton('First')
        self.previous_button = QPushButton('Previous')
        self.play_button = QPushButton('Play')
        self.play_button.setToolTip('Play/Pause the selected presentation mode; no domain execution.')
        self.next_button = QPushButton('Next')
        self.last_button = QPushButton('Last')
        self.before_button, self.after_button = QPushButton('Before'), QPushButton('After')
        for button in (self.first_button, self.previous_button, self.play_button, self.next_button,
                       self.last_button):
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            button.setMinimumWidth(button.fontMetrics().horizontalAdvance(
                'Pause' if button is self.play_button else button.text()) + 20)
            controls.addWidget(button)
        main.addLayout(controls)
        playback = QHBoxLayout()
        self.playback_mode = QComboBox()
        self.playback_mode.addItems((INDEX_MODE, MODEL_TIME_MODE))
        self.playback_mode.setAccessibleName('Playback mode')
        self.index_interval = _IndexInterval()
        self.index_interval.setRange(20, 5000)
        self.index_interval.setValue(200)
        self.index_interval.setSuffix(' ms')
        self.index_interval.setSpecialValueText('Max (20 ms)')
        self.index_interval.setKeyboardTracking(False)
        self.index_interval.setCorrectionMode(QSpinBox.CorrectToNearestValue)
        self.index_interval.fit_text_width()
        self.index_interval.setToolTip('Index interval per completed action. Max = fastest supported interval, 20 ms.')
        self.playback_speed = QDoubleSpinBox()
        self.playback_speed.setRange(0.25, 8.00)
        self.playback_speed.setSingleStep(0.25)
        self.playback_speed.setDecimals(2)
        self.playback_speed.setValue(1.00)
        self.playback_speed.setSuffix('x')
        self.playback_speed.setToolTip('Model C Time presentation speed, in quarter-speed steps.')
        self.playback_speed.setEnabled(False)
        for title, widget in (('Mode', self.playback_mode), ('Interval', self.index_interval),
                              ('Speed', self.playback_speed)):
            playback.addWidget(QLabel(title))
            playback.addWidget(widget)
        playback.addStretch()
        main.addLayout(playback)
        self.playback_status = _label()
        self.playback_status.setMaximumHeight(self.playback_status.fontMetrics().lineSpacing() * 2)
        self.playback_status.setToolTip(
            'Model C playhead may lie between actions. The board, Cumulative Model C Time and '
            'Counter Time (Model C) remain at the last completed frame; no intermediate board is invented.')
        main.addWidget(self.playback_status)
        self.frame_slider = _FrameSlider(Qt.Horizontal)
        self.frame_slider.setAccessibleName('Completed frame index')
        main.addWidget(self.frame_slider)
        entries = QHBoxLayout()
        self.action_entry = _DirectEntry()
        self.action_entry.setKeyboardTracking(False)
        self.action_go = QPushButton('Go action')
        entries.addWidget(QLabel('Action ordinal'))
        entries.addWidget(self.action_entry)
        entries.addWidget(self.action_go)
        entries.addWidget(self.before_button)
        entries.addWidget(self.after_button)
        entries.addStretch()
        main.addLayout(entries)
        self.answer_checkbox = QCheckBox('Show hidden answers — reference overlay')
        self.answer_checkbox.setChecked(False)
        self.route_checkbox = QCheckBox('Show action-target route')
        self.route_checkbox.setChecked(False)
        self.route_checkbox.setToolTip(ROUTE_NOTE + '. Completed action targets only; no future targets.')
        overlays = QHBoxLayout()
        overlays.addWidget(self.answer_checkbox)
        overlays.addWidget(self.route_checkbox)
        overlays.addStretch()
        main.addLayout(overlays)
        transition_note = _label(TRANSITION_NOTE + '\nSynthetic action-target cursor — teal ring')
        transition_note.setMaximumHeight(transition_note.fontMetrics().lineSpacing() * 2)
        transition_note.setToolTip('Orange outline: selected target; blue ring: previous recorded target; '
                                  'green: newly revealed safe cells AFTER. ' + CURSOR_NOTE)
        main.addWidget(transition_note)

        self.game_selector.currentIndexChanged.connect(self._pair_changed)
        self.solver_selector.currentIndexChanged.connect(self._pair_changed)
        self.first_button.clicked.connect(lambda: self.select_frame(0))
        self.previous_button.clicked.connect(lambda: self.select_frame(max(0, self.position.frame_index - 1)))
        self.next_button.clicked.connect(lambda: self.select_frame(min(self.action_count, self.position.frame_index + 1)))
        self.last_button.clicked.connect(lambda: self.select_frame(self.action_count))
        self.before_button.clicked.connect(lambda: self.set_before(True))
        self.after_button.clicked.connect(lambda: self.set_before(False))
        self.play_button.clicked.connect(self._toggle_playback)
        self.playback_mode.currentTextChanged.connect(self._mode_changed)
        self.index_interval.valueChanged.connect(self._interval_changed)
        self.playback_speed.valueChanged.connect(self._speed_changed)
        self.frame_slider.manual_seek.connect(self._pause_playback)
        self.frame_slider.track_seek.connect(self._seek_slider)
        self.frame_slider.sliderPressed.connect(self._pause_playback)
        self.frame_slider.valueChanged.connect(self._seek_slider)
        # Focus loss is not navigation: these entries also mirror inspection state.
        self.action_entry.commit_requested.connect(self._commit_action_entry)
        self.action_go.clicked.connect(self._commit_action_entry)
        self.answer_checkbox.toggled.connect(self._refresh)
        self.route_checkbox.toggled.connect(self._refresh)
        self._ensure_board_zini()
        self._refresh()
        available = self.screen().availableGeometry()
        # Leave room for native window decorations, even on small screens.
        self.resize(min(1360, max(1, available.width() - 32)),
                    min(920, max(1, available.height() - 64)))

    def _fact_tab(self, title):
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.fact_tabs.addTab(scroll, title)
        self.fact_scrolls[title] = scroll
        return layout

    @staticmethod
    def _group(layout, title, names, note=None):
        group = QGroupBox(title)
        form = QFormLayout(group)
        if note:
            form.addRow(_label(note))
        values = {}
        for name in names:
            label = _label()
            form.addRow(QLabel(name), label)
            values[name] = label
        layout.addWidget(group)
        return values

    @property
    def pair(self):
        return self.game_selector.currentData(), self.solver_selector.currentData()

    @property
    def position(self):
        return self._positions[self.pair]

    @property
    def reconstruction(self):
        index, solver = self.pair
        return getattr(self._games[index], solver)

    @property
    def action_count(self):
        return len(self.reconstruction.timeline.actions)

    @property
    def playhead_us(self):
        return self._playheads[self.pair]

    def _frame_time(self, pair, index):
        return self._cumulative[pair][index - 1] if index else 0

    def _align_playhead(self):
        self._playheads[self.pair] = self._frame_time(self.pair, self.position.frame_index)
        self._index_partial = Fraction(0)

    def _set_playhead(self, pair, microseconds, *, preserve_before=False):
        self._playheads[pair] = microseconds
        index = bisect_right(self._cumulative[pair], microseconds)
        position = self._positions[pair]
        # Manual BEFORE remains the selected action until that action completes.
        if not (preserve_before and position.before and position.frame_index == index):
            self._positions[pair] = _Position(index if index else None)

    def select_time(self, microseconds):
        if type(microseconds) is not int or not 0 <= microseconds <= self._cumulative[self.pair][-1]:
            raise ValueError('Model C playhead must be integer microseconds in 0..total, excluding bool.')
        self._stop_playback()
        self._index_partial = Fraction(0)
        self._set_playhead(self.pair, microseconds)
        self._refresh()

    def _seek_slider(self, value):
        if self._playback_mode == MODEL_TIME_MODE:
            self.select_time(value)
        else:
            self.select_frame(value)

    def select_pair(self, game_index, solver):
        if type(game_index) is not int or game_index not in self._games or solver not in ('stage2', 'stage3'):
            raise ValueError('Select one loaded exemplar and stage2/stage3.')
        self._stop_playback()
        self._index_partial = Fraction(0)
        blockers = [QSignalBlocker(self.game_selector), QSignalBlocker(self.solver_selector)]
        self.game_selector.setCurrentIndex(self.game_selector.findData(game_index))
        self.solver_selector.setCurrentIndex(self.solver_selector.findData(solver))
        del blockers
        self._ensure_board_zini()
        self._refresh()

    def select_frame(self, index):
        if type(index) is not int or not 0 <= index <= self.action_count:
            raise ValueError('Frame index must be an integer in 0..N, excluding bool.')
        self._stop_playback()
        self._positions[self.pair] = _Position(index if index else None)
        self._align_playhead()
        self._refresh()

    def _commit_action_entry(self):
        self.action_entry.interpretText()
        self.select_action(self.action_entry.value())

    def select_action(self, ordinal):
        if type(ordinal) is not int or not 1 <= ordinal <= self.action_count:
            raise ValueError('Action ordinal must be an integer in 1..N, excluding bool.')
        self._stop_playback()
        self._positions[self.pair] = _Position(ordinal)
        self._align_playhead()
        self._refresh()

    def set_before(self, before):
        if type(before) is not bool:
            raise ValueError('Before/After requires a bool.')
        ordinal = self.position.action_ordinal
        self._stop_playback()
        if ordinal is not None:
            self._positions[self.pair] = _Position(ordinal, before)
            self._align_playhead()
        self._refresh()

    def _pair_changed(self, *_args):
        self._stop_playback()
        self._index_partial = Fraction(0)
        self._ensure_board_zini()
        self._refresh()

    def _stop_playback(self, *, capture=True):
        if capture and self.play_timer.isActive():
            self._capture_playback()
        self.play_timer.stop()
        self._wall_clock.invalidate()
        self.play_button.setText('Play')

    def _pause_playback(self):
        self._stop_playback()
        # Slider interaction is manual navigation, even before the handle moves.
        self._index_partial = Fraction(0)
        self._refresh()

    def _start_playback(self):
        if self.position.frame_index == self.action_count:
            return
        self._play_pair = self.pair
        self._anchor_model_us = self.playhead_us
        self._anchor_index = self.position.frame_index + self._index_partial
        self._wall_clock.start()
        self.play_timer.start()
        self.play_button.setText('Pause')

    def _toggle_playback(self):
        before = self.position
        if self.play_timer.isActive():
            self._stop_playback()
        else:
            self._start_playback()
        if self.position != before:
            self._refresh()
        else:
            self._refresh_playhead()

    def _capture_model_playhead(self):
        # UI wall time is only a driver. Exact quarter-speed scaling produces
        # integer us; all domain boundaries still come from the loaded timeline.
        delta_us = self._wall_clock.nsecsElapsed() * self._speed_quarters // 4000
        target = min(self._cumulative[self._play_pair][-1], self._anchor_model_us + delta_us)
        self._set_playhead(self._play_pair, target, preserve_before=True)

    def _capture_playback(self):
        if self._playback_mode == MODEL_TIME_MODE:
            self._capture_model_playhead()
            return
        pair = self._play_pair
        n = len(self._targets[pair])
        elapsed = Fraction(self._wall_clock.nsecsElapsed(), self._index_interval_ms * 1_000_000)
        progress = min(Fraction(n), self._anchor_index + elapsed)
        index = progress.numerator // progress.denominator
        self._index_partial = progress - index
        if index != self._positions[pair].frame_index:
            self._positions[pair] = _Position(index if index else None)
            self._playheads[pair] = self._frame_time(pair, index)

    def _advance_playback(self):
        if not self.play_timer.isActive():
            return
        previous_position = self.position
        self._capture_playback()
        if self.position.frame_index == self.action_count:
            self._stop_playback(capture=False)
        if self.position == previous_position:
            self._refresh_playhead()
        else:
            self._refresh()

    def _mode_changed(self, mode):
        running = self.play_timer.isActive()
        self._stop_playback()  # Capture the old mode before changing its authority.
        if running and self._playback_mode == MODEL_TIME_MODE:
            index = self.position.frame_index
            self._positions[self.pair] = _Position(index if index else None)
        self._index_partial = Fraction(0)
        self._playback_mode = mode
        self.index_interval.setEnabled(mode == INDEX_MODE)
        self.playback_speed.setEnabled(mode == MODEL_TIME_MODE)
        if running:
            self._start_playback()
        self._refresh()

    def _interval_changed(self, value):
        before = self.position
        running = self.play_timer.isActive() and self._playback_mode == INDEX_MODE
        if running:
            self._capture_playback()  # Account for elapsed time at the OLD interval.
        self._index_interval_ms = value
        if running:
            # Preserve normalized segment progress; apply the new interval to
            # its remainder. The accepted Visualizer has no partial Index policy.
            self._anchor_index = self.position.frame_index + self._index_partial
            self._wall_clock.start()
            if self.position.frame_index == self.action_count:
                self._stop_playback(capture=False)
        if self.position != before:
            self._refresh()
        else:
            self._refresh_playhead()

    def _speed_changed(self, value):
        before = self.position
        running = self.play_timer.isActive() and self._playback_mode == MODEL_TIME_MODE
        if running:
            self._capture_model_playhead()  # Elapsed time still uses the old speed.
        self._speed_quarters = max(1, min(32, round(value * 4)))
        blocker = QSignalBlocker(self.playback_speed)
        self.playback_speed.setValue(self._speed_quarters / 4)
        del blocker
        if running:
            self._anchor_model_us = self.playhead_us
            self._wall_clock.start()
            if self.position.frame_index == self.action_count:
                self._stop_playback(capture=False)
        if self.position != before:
            self._refresh()
        else:
            self._refresh_playhead()

    def _ensure_board_zini(self):
        key = (self.pair[0], self.reconstruction.timeline.record.board_fingerprint)
        if key == self._zini_key:
            return
        self._zini_timer.stop()
        self._zini_job.close()
        self._zini_key = key
        self._zini_token += 1
        self._zini_failed = False
        if key not in self._zini_cache:
            self._zini_job.start(self.reconstruction.board_snapshot, self._zini_token)
            self._zini_timer.start()

    def _poll_zini(self):
        result = self._zini_job.poll()
        if result is None:
            return
        self._zini_timer.stop()
        valid = (type(result) is dict
                 and type(result.get('token')) is int
                 and result['token'] == self._zini_token
                 and 'error' in result and result['error'] is None
                 and type(result.get('clicks')) is int and result['clicks'] >= 0)
        if valid:
            self._zini_cache[self._zini_key] = result['clicks']
        self._zini_failed = not valid
        self._refresh()

    def closeEvent(self, event):
        self._stop_playback()
        self._zini_timer.stop()
        self._zini_job.close()
        super().closeEvent(event)

    def _refresh_playhead(self):
        """Partial refresh: slider/status/cursor only, never cells or Counters."""
        n, k = self.action_count, self.position.frame_index
        total = self._cumulative[self.pair][-1]
        time_mode = self._playback_mode == MODEL_TIME_MODE
        blocker = QSignalBlocker(self.frame_slider)
        self.frame_slider.setRange(0, total if time_mode else n)
        self.frame_slider.setValue(self.playhead_us if time_mode else k)
        self.frame_slider.setAccessibleName('Model C playhead (microseconds)' if time_mode else 'Completed frame index')
        del blocker
        self.first_button.setEnabled(self.playhead_us > 0 or self.position.action_ordinal is not None)
        self.previous_button.setEnabled(k > 0 or self.playhead_us > 0)
        speed = _decimal(Fraction(self._speed_quarters, 4), 2).rstrip('0').rstrip('.')
        self.playback_status.setText(
            f'Model C Time — {speed}x — {_seconds(self.playhead_us)} / {_seconds(total)} s'
            if time_mode else 'Index — Max (20 ms/action)' if self.index_interval.value() == 20
            else f'Index — {self.index_interval.value()} ms/action')
        self._refresh_cursor()

    def _refresh_cursor(self):
        k = self.position.frame_index
        targets = self._targets[self.pair]
        start = targets[k - 1] if k else self.reconstruction.timeline.evaluation.initial_cursor
        target, progress = start, Fraction(0)
        if k < len(targets):
            target = targets[k]
            if self._playback_mode == MODEL_TIME_MODE:
                begin = self._frame_time(self.pair, k)
                progress = Fraction(self.playhead_us - begin, self._cumulative[self.pair][k] - begin)
            else:
                progress = self._index_partial
        self.board.targets.set_cursor_center(self.board.targets.interpolated_center(start, target, progress))

    def _refresh(self, *_signal_args):
        game = self._games[self.pair[0]]
        rebuilt = self.reconstruction
        timeline, position = rebuilt.timeline, self.position
        n, k, j = self.action_count, position.frame_index, position.action_ordinal
        frame = rebuilt.frames[k]
        item = timeline.actions[j - 1] if j is not None else None
        event = item.event if item is not None else None
        previous_event = timeline.actions[j - 2].event if j is not None and j > 1 else None
        previous = (previous_event.x, previous_event.y) if previous_event else None
        target = (event.x, event.y) if event else None
        new_safe = rebuilt.newly_revealed_safe_by_action[j - 1] if j is not None and not position.before else frozenset()
        self.board.present(rebuilt.board_snapshot, frame, new_safe, previous, target,
                           self.answer_checkbox.isChecked(), self._targets[self.pair][:k],
                           self.route_checkbox.isChecked())
        self.frame_label.setText(f'Displayed frame {k} / {n}')
        self.action_label.setText(f'Selected action {j} / {n}' if j is not None else 'Selected action = none')
        self.inspection_label.setText('Initial frame — no selected action' if j is None else
            f'Selected recorded action {j} — ' + ('not yet applied (BEFORE)' if position.before else 'applied (AFTER)'))
        terminal = ' — Terminal Engine feedback' if frame.status != GameStatus.PLAYING else ''
        self.status_label.setText(f'Current reconstructed status: {frame.status.name}{terminal}; '
                                  f'final recorded outcome: {timeline.record.result}')
        self._refresh_playhead()
        blocker = QSignalBlocker(self.action_entry)
        self.action_entry.setRange(1, n)
        self.action_entry.setValue(j or 1)
        del blocker
        self.next_button.setEnabled(k < n)
        self.last_button.setEnabled(k < n)
        self.play_button.setEnabled(k < n)
        self.before_button.setEnabled(j is not None and not position.before)
        self.after_button.setEnabled(j is not None and position.before)

        ref = rebuilt.board_reference
        values = (game.reference.game_index, game.reference.category, self.solver_selector.currentText(),
                  timeline.record.result, n, timeline.record.board_fingerprint,
                  ref.total_3bv, ref.total_ops, ref.isolated_number_count)
        for label, value in zip(self.reference_values.values(), values):
            label.setText(str(value))
        self.policy_note.setText('Stage 2 action contract: OPEN / FLAG only — CHORD is not selected by this solver.'
            if self.pair[1] == 'stage2' else 'Stage 3 recorded action space: OPEN / FLAG / CHORD.')
        final = rebuilt.final_counters
        current = rebuilt.frame_counters[k]
        a, w, b = current.active_clicks, current.wasted_clicks, current.completed_3bv
        total = a + w
        cumulative = timeline.actions[k - 1].cumulative_modeled_us if k else 0
        prefix = _modeled_prefix(cumulative, b, ref.total_3bv, k)
        zini = self._zini_cache.get(self._zini_key)
        won = timeline.record.result == 'WIN'
        self.zini_status.setText('ZiNi: ready — bounded best-so-far board reference' if zini is not None
            else 'ZiNi: unavailable — calculation failed' if self._zini_failed else 'ZiNi: calculating...')
        counters = {name: '-' for name in COUNTER_ROWS}
        counters.update({'Time (Model C)': _decimal(prefix.seconds, 3),
                         'Est Time (Model C)': _decimal(prefix.estimated_seconds, 3),
                         '3BV/s (Model C)': _decimal(prefix.bbbv_per_second, 4),
                         'CPS (Model C)': _decimal(prefix.clicks_per_second, 4),
                         'ZiNi': str(zini) if zini is not None else '-',
                         'ZNE': f'{zini / total:.4f}' if zini is not None and won and total else '-',
                         'ZNT': f'{zini / a:.4f}' if zini is not None and won and a else '-',
                         '3BV': f'{b}/{ref.total_3bv}',
                         'Ops': f'{current.completed_ops}/{ref.total_ops}', 'Clicks': current.clicks_text,
                         'Left': current.left_text, 'Right': current.right_text, 'Chord': current.chord_text,
                         'Efficiency': f'{b / total:.0%}' if total else '-',
                         'IOE': f'{b / total:.4f}' if total else '-',
                         'Thrp': f'{b / a:.4f}' if a else '-',
                         'Corr': f'{a / total:.4f}' if total else '-'})
        for name, label in self.counter_values.items():
            label.setText(counters[name])
            label.setToolTip(ESTIMATE_NOTE if name == 'Est Time (Model C)' else
                'Model C cost through this frame; LOSS is cost through termination, not time-to-win.'
                if name in ('Time (Model C)', '3BV/s (Model C)', 'CPS (Model C)') else
                ZINI_NOTE if name in ('ZiNi', 'ZNE', 'ZNT') else '')
        cost = timeline.total_modeled_us
        current_estimate = (_decimal(prefix.estimated_seconds, 6) + ' s'
                            if prefix.estimated_seconds is not None else '-')
        current_bbbv_rate = _decimal(prefix.bbbv_per_second, 4)
        current_cps = _decimal(prefix.clicks_per_second, 4)
        b = final.completed_3bv
        final_prefix = _modeled_prefix(cost, b, ref.total_3bv, n)
        modeled_values = (_fact(item.modeled_action_us) + ' us' if item else 'unavailable',
                          _modeled_time(cumulative), current_estimate, current_bbbv_rate, current_cps,
                          _modeled_time(cost),
                          f'{b * 1000000}/{cost} = {_decimal(final_prefix.bbbv_per_second, 4)} (presentation)',
                          f'{n * 1000000}/{cost} = {_decimal(final_prefix.clicks_per_second, 4)} (presentation)',
                          str(timeline.evaluation.initial_cursor))
        for label, value in zip(self.model_values.values(), modeled_values):
            label.setText(value)
        self.cost_note.setText('Modeled cost through termination — not time-to-win' if timeline.record.result == 'LOSS'
                              else 'Final modeled cost through WIN; final rates describe this completed run.')
        values = (j, k, event.action_type.name if event else None, target, previous, frame.status.name,
                  timeline.record.result, item.dx if item else None, item.dy if item else None,
                  item.squared_displacement if item else None, item.modeled_action_us if item else None,
                  cumulative, event.inference_category.name if event and event.inference_category is not None else None,
                  event.target_mine_probability if event else None,
                  event.minimum_available_mine_probability if event else None,
                  event.selection_candidate_count if event else None, event.decision_compute_ns if event else None,
                  event.safe_cells_opened_delta if event else None,
                  len(rebuilt.newly_revealed_safe_by_action[j - 1]) if j is not None else None,
                  event.explicit_flag_delta if event else None)
        for label, value in zip(self.action_values.values(), values):
            label.setText(_fact(value))
