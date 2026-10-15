"""Painter commands specify the static path without pixel-perfect screenshots."""

import os
from dataclasses import replace
from math import ceil
import unittest
from unittest.mock import patch

from mouse_trace import MouseTraceData, MouseTracePoint, MouseTraceSegment
from replay_model import ReplayEvent

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtCore import QPoint, QPointF, Qt
    from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
    from PyQt5.QtWidgets import QApplication, QPushButton, QScrollArea, QWidget
except ImportError:
    QApplication = None
else:
    from mouse_trace_ui import MouseTraceOverlay, RASTER_CACHE_BYTES


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
            self.overlay._draw_geometry(painter_class.return_value)
        return painter_class.return_value

    def render(self):
        image = QImage(self.overlay.size(), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        self.overlay.render(image)
        return image

    @staticmethod
    def original_raster(overlay):
        # Independent reference: the pre-cache paint commands, into the same
        # transparent target/physical origin. No cached geometry is consulted.
        _, _, dpr, left, top, width, height, phase_x, phase_y = overlay._raster_key
        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(dpr)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.translate((phase_x - left) / dpr, (phase_y - top) / dpr)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(210, 120, 15, 190), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for segment in overlay._trace.segments:
            if len(segment.points) > 1:
                scale = overlay._cell_size / segment.cell_size
                painter.drawPolyline(QPolygonF([QPointF(p.x * scale, p.y * scale) for p in segment.points]))
        painter.setPen(QPen(QColor("white"), 1.0))
        for segment in overlay._trace.segments:
            scale = overlay._cell_size / segment.cell_size
            for point in segment.points:
                index = point.replay_event_index
                if index is not None and index < len(overlay._events):
                    color = {"OPEN": "#2563eb", "FLAG": "#16a34a", "CHORD": "#9333ea"}.get(overlay._events[index].action)
                    if color:
                        painter.setBrush(QColor(color))
                        painter.drawEllipse(QPointF(point.x * scale, point.y * scale), 3.5, 3.5)
        painter.end()
        return image

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

    def test_real_first_and_repeated_renders_reuse_raster_and_match_reference(self):
        self.overlay.set_trace(self.data, self.events)
        self.overlay.set_cell_size(20)
        with patch.object(self.overlay, "_draw_geometry", wraps=self.overlay._draw_geometry) as draw:
            first = self.render()
            raster = self.overlay._raster
            geometry = self.overlay._geometry
            self.assertEqual(raster, self.original_raster(self.overlay))
            self.assertEqual(self.render(), first)
            self.overlay.set_trace(self.data, self.events)
            self.overlay.set_cell_size(20)
            self.assertEqual(self.render(), first)
            draw.assert_called_once()
            self.assertIs(self.overlay._raster, raster)
            self.assertIs(self.overlay._geometry, geometry)

    def test_trace_events_size_and_resize_invalidate_relevant_caches(self):
        self.overlay.set_trace(self.data, self.events)
        self.overlay.set_cell_size(20)
        self.render()
        for change in (
                lambda: self.overlay.set_trace(replace(self.data), self.events),
                lambda: self.overlay.set_trace(self.data, (replace(self.events[0], action="FLAG"),) + self.events[1:]),
                lambda: self.overlay.set_cell_size(10)):
            with self.subTest(change=change):
                change()
                self.assertIsNone(self.overlay._raster)
                self.assertIsNone(self.overlay._geometry)
                with patch.object(self.overlay, "_draw_geometry", wraps=self.overlay._draw_geometry) as draw:
                    self.render()
                    draw.assert_called_once()
                self.assertEqual(self.overlay._raster, self.original_raster(self.overlay))
        geometry = self.overlay._geometry
        self.overlay.resize(130, 100)
        self.render()
        self.assertEqual(self.overlay._raster.size(), self.overlay.size())
        self.assertIs(self.overlay._geometry, geometry)
        self.assertEqual(self.overlay._raster, self.original_raster(self.overlay))

    def test_dpr_changes_physical_allocation_and_invalidates_raster_only(self):
        self.overlay.set_trace(self.data, self.events)
        self.overlay.set_cell_size(20)
        self.render()
        geometry = self.overlay._geometry
        for dpr in (2., 1.25, 1.):
            with self.subTest(dpr=dpr), patch.object(self.overlay, "devicePixelRatioF", return_value=dpr):
                with patch.object(self.overlay, "_draw_geometry", wraps=self.overlay._draw_geometry) as draw:
                    self.render()
                    self.render()
                    draw.assert_called_once()
                raster = self.overlay._raster
                self.assertEqual(raster.devicePixelRatioF(), dpr)
                self.assertEqual((raster.width(), raster.height()),
                                 (ceil(self.overlay.width() * dpr), ceil(self.overlay.height() * dpr)))
                self.assertEqual(raster.sizeInBytes(), raster.width() * raster.height() * 4)
                self.assertLessEqual(raster.sizeInBytes(), RASTER_CACHE_BYTES)
                self.assertIs(self.overlay._geometry, geometry)
                self.assertEqual(raster, self.original_raster(self.overlay))

    def test_oversized_board_uses_bounded_region_and_scroll_reuses_fixed_region(self):
        scroll = QScrollArea()
        self.addCleanup(scroll.close)
        scroll.resize(260, 220)
        board = QWidget()
        board.resize(6000, 6000)  # 137 MiB at DPR1 if cached unconditionally.
        scroll.setWidget(board)
        overlay = MouseTraceOverlay(board)
        overlay.setGeometry(board.rect())
        overlay.set_cell_size(60)
        overlay.set_trace(MouseTraceData(100, 100, (
            MouseTraceSegment(60, (MouseTracePoint(0, 4, 5, 0), MouseTracePoint(1, 5000, 5000))),
            MouseTraceSegment(30, (MouseTracePoint(2, 60.25, 100.75, 1),)),
        )), self.events)
        overlay.show()
        scroll.show()
        self.app.processEvents()
        geometry = overlay._geometry
        for dpr, offset in ((1., 0), (1., 123), (2., 157), (1.25, 191)):
            with self.subTest(dpr=dpr, offset=offset), patch.object(overlay, "devicePixelRatioF", return_value=dpr):
                scroll.horizontalScrollBar().setValue(offset)
                scroll.verticalScrollBar().setValue(offset + 11)
                self.app.processEvents()
                scroll.viewport().grab()
                raster = overlay._raster
                self.assertIsNotNone(raster)
                self.assertLessEqual(raster.sizeInBytes(), RASTER_CACHE_BYTES)
                self.assertLess(raster.width(), board.width())
                self.assertIs(overlay._geometry, geometry)
                self.assertEqual(raster, self.original_raster(overlay))
                with patch.object(overlay, "_draw_geometry", wraps=overlay._draw_geometry) as draw:
                    first = scroll.viewport().grab().toImage()
                    self.assertEqual(first, scroll.viewport().grab().toImage())
                    draw.assert_not_called()
                self.assertIs(overlay._raster, raster)

    def test_raster_budget_fallback_keeps_geometry_and_does_not_allocate_image(self):
        self.overlay.set_trace(self.data, self.events)
        self.overlay.set_cell_size(20)
        self.board.show()
        self.overlay.show()
        self.app.processEvents()
        self.overlay._invalidate_raster()
        with patch("mouse_trace_ui.RASTER_CACHE_BYTES", 4), patch("mouse_trace_ui.QImage") as image:
            # Use real QPainter/widget rendering while forbidding raster allocation.
            first = self.render()
            self.assertEqual(first, self.render())
            image.assert_not_called()
        self.assertIsNone(self.overlay._raster)
        self.assertIsNotNone(self.overlay._geometry)

    def test_cached_pixels_leave_segment_gap_empty(self):
        data = MouseTraceData(4, 3, (
            MouseTraceSegment(30, (MouseTracePoint(0, 10, 10, 0), MouseTracePoint(1, 20, 20))),
            MouseTraceSegment(30, (MouseTracePoint(2, 80, 80), MouseTracePoint(3, 90, 80))),
        ))
        self.overlay.set_trace(data, self.events)
        self.overlay.set_cell_size(30)
        self.render()
        self.assertEqual(self.overlay._raster.pixelColor(50, 50).alpha(), 0)
        self.assertGreater(self.overlay._raster.pixelColor(85, 80).alpha(), 0)

    def test_fractional_device_origin_is_preserved_and_invalidates_on_move(self):
        container = QWidget()
        container.resize(160, 130)
        container.setAutoFillBackground(True)
        self.addCleanup(container.close)
        self.addCleanup(self.board.setParent, None)
        self.board.setParent(container)
        self.board.setGeometry(11, 17, 120, 90)
        self.overlay.set_trace(self.data, self.events)
        self.overlay.set_cell_size(20)
        self.overlay.show()
        container.show()
        self.app.processEvents()

        def render():
            target = QImage(200, 163, QImage.Format_ARGB32_Premultiplied)
            target.setDevicePixelRatio(1.25)
            target.fill(Qt.transparent)
            container.render(target)
            return target

        with patch.object(self.overlay, "devicePixelRatioF", return_value=1.25):
            cached = render()
            self.assertEqual(self.overlay._raster_key[-2:], (.75, .25))
            self.assertEqual(self.overlay._raster, self.original_raster(self.overlay))
            self.assertEqual(render(), cached)
            geometry = self.overlay._geometry
            self.overlay._invalidate_raster()
            with patch("mouse_trace_ui.RASTER_CACHE_BYTES", 0):
                direct = render()
            # Flattening transparent strokes adds integer-alpha rounding, but
            # must not move their edges on the physical antialiasing grid.
            a, b = cached.constBits(), direct.constBits()
            a.setsize(cached.sizeInBytes())
            b.setsize(direct.sizeInBytes())
            self.assertLessEqual(max(abs(x - y) for x, y in zip(bytes(a), bytes(b))), 2)
            # Restore the normal budget after the direct-paint comparison.
            self.overlay._invalidate_raster()
            render()
            old_raster = self.overlay._raster
            self.board.move(12, 18)
            render()
            self.assertEqual(self.overlay._raster_key[-2:], (0., .5))
            self.assertIsNot(self.overlay._raster, old_raster)
            self.assertIs(self.overlay._geometry, geometry)
            self.assertEqual(self.overlay._raster, self.original_raster(self.overlay))


if __name__ == "__main__":
    unittest.main()
