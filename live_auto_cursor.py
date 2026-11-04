"""Draw-only Live Auto cursor. No engine, policy, input or trace dependencies."""

from time import perf_counter

from PyQt5.QtCore import QPointF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget


class LiveAutoCursorOverlay(QWidget):
    """Interpolate in cell coordinates without changing the logical cursor.

    The owner supplies an already authorized reservation and its existing
    viewing interval. The repaint timer can neither approve nor execute input.
    Before the first input an active owner uses the canonical (0, 0) anchor;
    without an owner the overlay is hidden.
    """

    def __init__(self, parent, *, clock=perf_counter):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self._clock = clock
        self._cell_size = 1
        self._actual = (0, 0)
        self._position = (0, 0)
        self._motion = None
        self._reservation = None
        self._generation = 0
        self._available = False
        self._display_enabled = True
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timeout_slot = None
        self.hide()

    @property
    def position(self):
        if self._motion is None:
            return self._position
        start, target, began, duration = self._motion
        fraction = min(1.0, max(0.0, (self._clock() - began) / duration))
        return tuple(a + (b - a) * fraction for a, b in zip(start, target))

    @property
    def pixel_position(self):
        x, y = self.position
        return QPointF((x + .5) * self._cell_size, (y + .5) * self._cell_size)

    def set_cell_size(self, size):
        self._cell_size = size
        self.update()

    def set_display_enabled(self, enabled):
        # A display toggle never cancels/restarts even the visual reservation.
        self._display_enabled = bool(enabled)
        self.setVisible(self._display_enabled and self._available)
        self.update()

    def set_available(self, available):
        available = bool(available)
        if self._available and not available:
            self.cancel()
        self._available = available
        self.setVisible(self._display_enabled and self._available)

    def cancel(self):
        self._generation += 1
        self._timer.stop()
        self._motion = self._reservation = None
        self._position = self._actual
        self.update()

    def clear(self):
        self.cancel()
        self.set_available(False)

    def set_actual(self, coordinate):
        self._actual = tuple(coordinate)
        self.cancel()

    def reserve(self, reservation, actual, target, interval_ms):
        self.set_actual(actual)
        self._reservation = reservation
        target = tuple(target)
        if interval_ms <= 0:
            self._position = target
        else:
            self._motion = (self._actual, target, self._clock(), interval_ms / 1000)
            if self._timeout_slot is not None:
                self._timer.timeout.disconnect(self._timeout_slot)
            generation = self._generation
            self._timeout_slot = lambda: self._tick(generation)
            self._timer.timeout.connect(self._timeout_slot)
            self._timer.start()
        self.update()

    def _tick(self, generation):
        if generation != self._generation or self._motion is None:
            return
        self._position = self.position
        _, target, began, duration = self._motion
        if self._clock() - began >= duration:
            self._position = target
            self._motion = None
            self._timer.stop()
        self.update()

    def paintEvent(self, event):
        if not self._available or not self._display_enabled:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        radius = max(4.0, min(12.0, self._cell_size * .32))
        center = self.pixel_position
        # An unfilled thin ring keeps the underlying number/flag readable.
        painter.setPen(QPen(QColor(255, 255, 255, 220), 2.8))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(QPen(QColor('#125ca4'), 1.3))
        painter.drawEllipse(center, radius, radius)
