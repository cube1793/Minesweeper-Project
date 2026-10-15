"""Static board presentation of an immutable human trace and linked Replay events."""

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QWidget

from mouse_trace import MouseTraceData
from replay_model import ACTION_CHORD, ACTION_FLAG, ACTION_OPEN, ReplayEvent


_ACTION_COLORS = {
    ACTION_OPEN: "#2563eb",
    ACTION_FLAG: "#16a34a",
    ACTION_CHORD: "#9333ea",
}


class MouseTraceOverlay(QWidget):
    """Draw only; the owner decides when finished-Live data may be displayed."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self._trace = None
        self._events = ()
        self._cell_size = 1
        self.hide()

    def set_trace(self, trace: MouseTraceData | None, events: tuple[ReplayEvent, ...]):
        self._trace = trace
        self._events = tuple(events)
        self.update()

    def set_cell_size(self, cell_size: int):
        self._cell_size = cell_size
        self.update()

    def paintEvent(self, event):
        if self._trace is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(210, 120, 15, 190), 1.6, Qt.SolidLine,
                            Qt.RoundCap, Qt.RoundJoin))
        # Each draw call is one observed segment. A singleton has no line.
        for segment in self._trace.segments:
            if len(segment.points) > 1:
                scale = self._cell_size / segment.cell_size
                painter.drawPolyline(QPolygonF([
                    QPointF(point.x * scale, point.y * scale)
                    for point in segment.points
                ]))

        # Paint markers last, only at linked observed positions. The existing
        # Replay event supplies the action; unlinked events add nothing here.
        painter.setPen(QPen(QColor("white"), 1.0))
        for segment in self._trace.segments:
            scale = self._cell_size / segment.cell_size
            for point in segment.points:
                index = point.replay_event_index
                if index is None or index >= len(self._events):
                    continue
                color = _ACTION_COLORS.get(self._events[index].action)
                if color is not None:
                    painter.setBrush(QColor(color))
                    painter.drawEllipse(QPointF(point.x * scale, point.y * scale), 3.5, 3.5)
        painter.end()
