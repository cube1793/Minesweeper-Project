"""Painter commands specify the static path without pixel-perfect screenshots."""

import os
import unittest
from unittest.mock import patch

from mouse_trace import MouseTraceData, MouseTracePoint, MouseTraceSegment
from replay_model import ReplayEvent

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtWidgets import QApplication, QPushButton, QWidget
except ImportError:
    QApplication = None
else:
    from mouse_trace_ui import MouseTraceOverlay


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class MouseTraceOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.board = QWidget()
        self.board.resize(120, 90)
        self.overlay = MouseTraceOverlay(self.board)
        self.overlay.setGeometry(self.board.rect())
        self.addCleanup(self.close_board)
        self.events = (
            ReplayEvent(0.0, 3, 2, "OPEN"),
            ReplayEvent(1.0, 3, 2, "FLAG"),
            ReplayEvent(2.0, 3, 2, "CHORD"),
            ReplayEvent(3.0, 3, 2, "FLAG"),  # No linked point: no marker.
        )
        self.data = MouseTraceData(4, 3, (
            MouseTraceSegment(10, (MouseTracePoint(0, 2, 3, 0), MouseTracePoint(10, 12, 13, 1))),
            MouseTraceSegment(20, (MouseTracePoint(20, 14, 16, 2), MouseTracePoint(30, 32, 22))),
            MouseTraceSegment(10, (MouseTracePoint(40, 20, 25),)),
        ))

    def close_board(self):
        self.board.close()
        self.board.deleteLater()
        self.app.processEvents()

    def paint(self):
        with patch("mouse_trace_ui.QPainter") as painter_class:
            self.overlay.paintEvent(None)
        return painter_class.return_value

    @staticmethod
    def polylines(painter):
        return [[(point.x(), point.y()) for point in call.args[0]]
                for call in painter.drawPolyline.call_args_list]

    def test_segments_are_independent_and_mixed_recording_sizes_scale(self):
        self.overlay.set_trace(self.data, self.events)
        self.overlay.set_cell_size(20)
        self.assertEqual(self.polylines(self.paint()), [
            [(4, 6), (24, 26)], [(14, 16), (32, 22)],
        ])
        self.overlay.set_cell_size(10)
        self.assertEqual(self.polylines(self.paint()), [
            [(2, 3), (12, 13)], [(7, 8), (16, 11)],
        ])

    def test_singleton_has_no_line_but_keeps_its_linked_marker(self):
        data = MouseTraceData(4, 3, (MouseTraceSegment(10, (MouseTracePoint(0, 2, 3, 0),)),))
        self.overlay.set_trace(data, self.events)
        self.overlay.set_cell_size(20)
        painter = self.paint()
        painter.drawPolyline.assert_not_called()
        painter.drawEllipse.assert_called_once()
        center, rx, ry = painter.drawEllipse.call_args.args
        self.assertEqual((center.x(), center.y(), rx, ry), (4, 6, 3.5, 3.5))

    def test_only_linked_events_supply_marker_colors_at_observed_positions(self):
        self.overlay.set_trace(self.data, self.events)
        self.overlay.set_cell_size(20)
        painter = self.paint()
        self.assertEqual([call.args[0].name() for call in painter.setBrush.call_args_list],
                         ["#2563eb", "#16a34a", "#9333ea"])
        self.assertEqual([(call.args[0].x(), call.args[0].y())
                          for call in painter.drawEllipse.call_args_list],
                         [(4, 6), (24, 26), (14, 16)])
        # None are the (3, 2) Replay action's cell center (70, 50).
        self.assertEqual(painter.drawEllipse.call_count, 3)

    def test_absent_event_reference_never_fabricates_a_marker(self):
        self.overlay.set_trace(self.data, self.events[:1])
        self.assertEqual(self.paint().drawEllipse.call_count, 1)

    def test_trace_and_event_inputs_are_retained_without_mutating_them(self):
        events = list(self.events)
        self.overlay.set_trace(self.data, events)
        events.clear()
        self.assertIs(self.overlay._trace, self.data)
        self.assertEqual(self.overlay._events, self.events)
        self.assertEqual(self.paint().drawEllipse.call_count, 3)
        self.overlay.set_trace(None, ())
        with patch("mouse_trace_ui.QPainter") as painter_class:
            self.overlay.paintEvent(None)
        painter_class.assert_not_called()

    def test_mouse_transparency_preserves_child_target_tooltip_and_preview(self):
        cell = QPushButton(self.board)
        cell.setGeometry(0, 0, 28, 28)
        cell.setToolTip("existing cell tooltip")
        cell.setDown(True)
        self.overlay.set_trace(self.data, self.events)
        self.overlay.set_cell_size(28)
        self.overlay.raise_()
        self.overlay.show()
        self.board.show()
        self.app.processEvents()
        self.assertTrue(self.overlay.testAttribute(Qt.WA_TransparentForMouseEvents))
        self.assertFalse(self.overlay.autoFillBackground())
        self.assertEqual(self.overlay.focusPolicy(), Qt.NoFocus)
        self.assertIs(self.board.childAt(QPoint(10, 10)), cell)
        self.assertEqual(cell.toolTip(), "existing cell tooltip")
        self.assertTrue(cell.isDown())
        self.assertFalse(self.overlay.grab().isNull())  # Real Qt paint smoke.


if __name__ == "__main__":
    unittest.main()
