"""Manual inspection of already authenticated, immutable exemplar evidence.

No loading, reconstruction, clock, decisions or ZiNi calculation belongs here.
The answer layer is a renderer-only reference; all ordinary cell text describes
the stored public frame. Each game/solver pair owns one inspection position.
"""

from dataclasses import dataclass
from fractions import Fraction

from PyQt5.QtCore import QPointF, Qt, QSignalBlocker, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGraphicsOpacityEffect, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from core_engine import CellState, GameStatus
from exemplar_board_evidence import AcceptedExemplarEvidence, LoadedExemplar


CELL_SIZE = 28
NUMBER_COLORS = {1: '#0000ff', 2: '#008000', 3: '#ff0000', 4: '#000080',
                 5: '#800000', 6: '#008080', 7: '#000000', 8: '#808080'}
COUNTER_ROWS = ('Time', 'Est Time', '3BV', '3BV/s', 'Clicks', 'Left', 'Right',
                'Chord', 'CPS', 'Efficiency', 'IOE', 'Ops', 'Thrp', 'Corr',
                'ZiNi', 'ZNE', 'ZNT')
TRANSITION_NOTE = 'Action-target transition — not recorded cursor trajectory'
ZINI_NOTE = 'Optional answer-derived ZiNi reference is not calculated in this standalone viewer.'
MODEL_NOTE = (
    'Both timelines are post-hoc Model C evaluations of persisted actions. '
    'Stage 2 did not natively declare Model C; Stage 3 declared it during collection, '
    'but these events retain no native per-action cost/cursor fields. '
    'This is modeled physical execution time, not Replay elapsed, CPU decision '
    'time or recorded cursor trajectory.'
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


class _DirectEntry(QSpinBox):
    """Own Return/Enter explicitly; focus loss only edits the displayed value."""

    commit_requested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.commit_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


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
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.previous_target = self.current_target = None

    @property
    def transition_line(self):
        if self.previous_target is None or self.previous_target == self.current_target:
            return None
        return self.previous_target, self.current_target

    @staticmethod
    def center(target):
        return QPointF((target[0] + 0.5) * CELL_SIZE, (target[1] + 0.5) * CELL_SIZE)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
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


class _PublicBoard(QWidget):
    def __init__(self):
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(0)
        self.cells = {}
        self._shape = None
        self.targets = _TargetOverlay(self)

    def present(self, snapshot, frame, new_safe, previous, current, show_answers):
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
        self.targets.raise_()
        self.targets.update()


class ExemplarBoardViewerWindow(QWidget):
    """One immutable evidence bundle; eight independent manual positions."""

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
        self.setWindowTitle('Selected Exemplar Board-State Viewer — human interpretation')
        layout = QHBoxLayout(self)
        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        self.reference_values = self._group(side, 'Board / Solver Reference', (
            'Game index', 'Accepted category', 'Solver', 'Final recorded outcome',
            'Action count', 'Board fingerprint', 'Total 3BV', 'Total Ops', 'Isolated-number count'))
        self.policy_note = _label()
        side.addWidget(self.policy_note)
        side.addWidget(_label('3BV / Ops / isolated number count = answer-derived board references, '
                              'not solver-visible evidence.'))
        self.counter_values = self._group(side, 'Classic Counters / Final Run Summary', COUNTER_ROWS,
            'Reconstructed Counters — current Engine semantics; FINAL RUN SUMMARY')
        side.addWidget(_label('Historical elapsed time unavailable. Mechanical active/wasted '
                              'classification is not strategic quality.'))
        side.addWidget(_label(ZINI_NOTE))
        self.model_values = self._group(side, 'Model C', (
            'Selected Action Model C Cost', 'Cumulative Model C Time', 'Final Model C Time',
            'Modeled 3BV/s', 'Modeled CPS', 'Initial Model C cursor'))
        self.cost_note = _label()
        side.addWidget(self.cost_note)
        side.addWidget(_label(MODEL_NOTE))
        self.action_values = self._group(side, 'Action Context', (
            'Selected ordinal', 'Displayed frame', 'Action type', 'Current target',
            'Previous recorded target', 'Current reconstructed status', 'Recorded final outcome',
            'dx', 'dy', 'd²', 'Selected Model C action us', 'Cumulative Model C us',
            'Inference category', 'Target mine probability', 'Minimum available mine probability',
            'Candidate count', 'Decision compute (ns)', 'Recorded safe reveal delta',
            'Reconstructed new-safe count', 'Explicit flag delta'))
        side.addWidget(_label(CANDIDATE_NOTE))
        side.addWidget(_label(COMPUTE_NOTE))
        side.addStretch()
        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setWidget(sidebar)
        self.sidebar_scroll.setMinimumWidth(330)
        self.sidebar_scroll.setMaximumWidth(450)
        layout.addWidget(self.sidebar_scroll, 1)

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
        for label in (self.frame_label, self.action_label, self.inspection_label):
            main.addWidget(label)
        self.status_label = _label()
        main.addWidget(self.status_label)
        main.addWidget(_label('Independent action-count sequences: equal indices do not mean '
                              'equal board state or progress. No shared execution clock.'))
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
        self.next_button = QPushButton('Next')
        self.last_button = QPushButton('Last')
        self.before_button, self.after_button = QPushButton('Before'), QPushButton('After')
        for button in (self.first_button, self.previous_button, self.next_button,
                       self.last_button, self.before_button, self.after_button):
            controls.addWidget(button)
        main.addLayout(controls)
        self.frame_slider = QSlider(Qt.Horizontal)
        self.frame_slider.setAccessibleName('Completed frame index')
        main.addWidget(self.frame_slider)
        entries = QHBoxLayout()
        self.frame_entry, self.action_entry = _DirectEntry(), _DirectEntry()
        self.frame_entry.setKeyboardTracking(False)
        self.action_entry.setKeyboardTracking(False)
        self.frame_go, self.action_go = QPushButton('Go frame'), QPushButton('Go action')
        entries.addWidget(QLabel('Frame'))
        entries.addWidget(self.frame_entry)
        entries.addWidget(self.frame_go)
        entries.addWidget(QLabel('Action ordinal'))
        entries.addWidget(self.action_entry)
        entries.addWidget(self.action_go)
        main.addLayout(entries)
        self.answer_checkbox = QCheckBox('Show hidden answers — reference overlay')
        self.answer_checkbox.setChecked(False)
        main.addWidget(self.answer_checkbox)
        main.addWidget(_label(TRANSITION_NOTE + '. Orange outline: selected target; '
                              'blue ring: previous recorded target; green: newly revealed safe cells AFTER.'))

        self.game_selector.currentIndexChanged.connect(self._refresh)
        self.solver_selector.currentIndexChanged.connect(self._refresh)
        self.first_button.clicked.connect(lambda: self.select_frame(0))
        self.previous_button.clicked.connect(lambda: self.select_frame(max(0, self.position.frame_index - 1)))
        self.next_button.clicked.connect(lambda: self.select_frame(min(self.action_count, self.position.frame_index + 1)))
        self.last_button.clicked.connect(lambda: self.select_frame(self.action_count))
        self.before_button.clicked.connect(lambda: self.set_before(True))
        self.after_button.clicked.connect(lambda: self.set_before(False))
        self.frame_slider.valueChanged.connect(self.select_frame)
        # Focus loss is not navigation: these entries also mirror inspection state.
        self.frame_entry.commit_requested.connect(self._commit_frame_entry)
        self.action_entry.commit_requested.connect(self._commit_action_entry)
        self.frame_go.clicked.connect(self._commit_frame_entry)
        self.action_go.clicked.connect(self._commit_action_entry)
        self.answer_checkbox.toggled.connect(self._refresh)
        self.resize(1280, 850)
        self._refresh()

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

    def select_pair(self, game_index, solver):
        if type(game_index) is not int or game_index not in self._games or solver not in ('stage2', 'stage3'):
            raise ValueError('Select one loaded exemplar and stage2/stage3.')
        blockers = [QSignalBlocker(self.game_selector), QSignalBlocker(self.solver_selector)]
        self.game_selector.setCurrentIndex(self.game_selector.findData(game_index))
        self.solver_selector.setCurrentIndex(self.solver_selector.findData(solver))
        del blockers
        self._refresh()

    def select_frame(self, index):
        if type(index) is not int or not 0 <= index <= self.action_count:
            raise ValueError('Frame index must be an integer in 0..N, excluding bool.')
        self._positions[self.pair] = _Position(index if index else None)
        self._refresh()

    def _commit_frame_entry(self):
        self.frame_entry.interpretText()
        self.select_frame(self.frame_entry.value())

    def _commit_action_entry(self):
        self.action_entry.interpretText()
        self.select_action(self.action_entry.value())

    def select_action(self, ordinal):
        if type(ordinal) is not int or not 1 <= ordinal <= self.action_count:
            raise ValueError('Action ordinal must be an integer in 1..N, excluding bool.')
        self._positions[self.pair] = _Position(ordinal)
        self._refresh()

    def set_before(self, before):
        if type(before) is not bool:
            raise ValueError('Before/After requires a bool.')
        if self.position.action_ordinal is not None:
            self._positions[self.pair] = _Position(self.position.action_ordinal, before)
            self._refresh()

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
        self.board.present(rebuilt.board_snapshot, frame, new_safe, previous, target, self.answer_checkbox.isChecked())
        self.frame_label.setText(f'Displayed frame {k} / {n}')
        self.action_label.setText(f'Selected action {j} / {n}' if j is not None else 'Selected action = none')
        self.inspection_label.setText('Initial frame — no selected action' if j is None else
            f'Selected recorded action {j} — ' + ('not yet applied (BEFORE)' if position.before else 'applied (AFTER)'))
        terminal = ' — Terminal Engine feedback' if frame.status != GameStatus.PLAYING else ''
        self.status_label.setText(f'Current reconstructed status: {frame.status.name}{terminal}; '
                                  f'final recorded outcome: {timeline.record.result}')
        blockers = [QSignalBlocker(widget) for widget in (self.frame_slider, self.frame_entry, self.action_entry)]
        for widget in (self.frame_slider, self.frame_entry):
            widget.setRange(0, n)
            widget.setValue(k)
        self.action_entry.setRange(1, n)
        self.action_entry.setValue(j or 1)
        del blockers
        self.first_button.setEnabled(k > 0 or j is not None)
        self.previous_button.setEnabled(k > 0)
        self.next_button.setEnabled(k < n)
        self.last_button.setEnabled(k < n)
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
        a, w, b = final.active_clicks, final.wasted_clicks, final.completed_3bv
        total = a + w
        counters = {name: '-' for name in COUNTER_ROWS}
        counters.update({'3BV': final.bbbv_text, 'Ops': final.ops_text, 'Clicks': final.clicks_text,
                         'Left': final.left_text, 'Right': final.right_text, 'Chord': final.chord_text,
                         'Efficiency': f'{b / total:.0%}' if total else '-',
                         'IOE': f'{b / total:.4f}' if total else '-',
                         'Thrp': f'{b / a:.4f}' if a else '-',
                         'Corr': f'{a / total:.4f}' if total else '-'})
        for name, label in self.counter_values.items():
            label.setText(counters[name])
            label.setToolTip('historical elapsed time unavailable' if name in ('Time', 'Est Time', '3BV/s', 'CPS')
                             else ZINI_NOTE if name in ('ZiNi', 'ZNE', 'ZNT') else '')
        cumulative = timeline.actions[k - 1].cumulative_modeled_us if k else 0
        cost = timeline.total_modeled_us
        modeled_values = (_fact(item.modeled_action_us) + ' us' if item else 'unavailable',
                          f'{cumulative} us', f'{cost} us',
                          f'{b * 1000000}/{cost} = {b * 1000000 / cost:.4f} (presentation)',
                          f'{n * 1000000}/{cost} = {n * 1000000 / cost:.4f} (presentation)',
                          str(timeline.evaluation.initial_cursor))
        for label, value in zip(self.model_values.values(), modeled_values):
            label.setText(value)
        self.cost_note.setText('Modeled cost through termination — not time-to-win' if timeline.record.result == 'LOSS'
                              else 'Final modeled cost through WIN; rates describe this completed run.')
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
