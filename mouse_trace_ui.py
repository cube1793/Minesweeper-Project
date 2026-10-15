"""Static board presentation of an immutable human trace and linked Replay events."""

from math import ceil, floor

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QWidget

from mouse_trace import MouseTraceData
from replay_model import ACTION_CHORD, ACTION_FLAG, ACTION_OPEN, ReplayEvent


_ACTION_COLORS = {
    ACTION_OPEN: "#2563eb",
    ACTION_FLAG: "#16a34a",
    ACTION_CHORD: "#9333ea",
}

# One retained ARGB32 raster, including physical pixels at devicePixelRatioF.
# bytes = physical_width * physical_height * 4 (including the rounding pixel
# needed at fractional device origins). Release the old image before
# allocating its replacement. Geometry is proportional to the input trace;
# this budget specifically bounds raster memory, regardless of board dimensions.
RASTER_CACHE_BYTES = 16 * 1024 * 1024


class MouseTraceOverlay(QWidget):
    """Draw only; the owner decides when Live or Replay data may be displayed."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self._trace = None
        self._events = ()
        self._cell_size = 1
        self._geometry = None
        self._raster = None
        self._raster_key = None
        self.hide()

    def set_trace(self, trace: MouseTraceData | None, events: tuple[ReplayEvent, ...]):
        events = tuple(events)
        # Immutable attachment identity is sufficient; never compare all points
        # to decide whether an unchanged paint can reuse cached work.
        if self._trace is trace and self._events is events:
            return
        self._trace = trace
        self._events = events
        self._geometry = None
        self._invalidate_raster()
        self.update()

    def set_cell_size(self, cell_size: int):
        if self._cell_size == cell_size:
            return
        self._cell_size = cell_size
        self._geometry = None
        self._invalidate_raster()
        self.update()

    def _invalidate_raster(self):
        self._raster = None
        self._raster_key = None

    def resizeEvent(self, event):
        self._invalidate_raster()
        super().resizeEvent(event)

    def _presentation_geometry(self):
        if self._geometry is None:
            polygons, markers = [], []
            if self._trace is not None:
                for segment in self._trace.segments:
                    scale = self._cell_size / segment.cell_size
                    positions = []
                    for point in segment.points:
                        position = QPointF(point.x * scale, point.y * scale)
                        positions.append(position)
                        index = point.replay_event_index
                        if index is not None and index < len(self._events):
                            color = _ACTION_COLORS.get(self._events[index].action)
                            if color is not None:
                                markers.append((position, QColor(color)))
                    if len(positions) > 1:
                        polygons.append(QPolygonF(positions))
            self._geometry = polygons, markers
        return self._geometry

    def _draw_geometry(self, painter):
        polygons, markers = self._presentation_geometry()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(210, 120, 15, 190), 1.6, Qt.SolidLine,
                            Qt.RoundCap, Qt.RoundJoin))
        # Each draw call is one observed segment. A singleton has no line.
        for polygon in polygons:
            painter.drawPolyline(polygon)

        # Paint markers last, only at linked observed positions. The existing
        # Replay event supplies the action; unlinked events add nothing here.
        painter.setPen(QPen(QColor("white"), 1.0))
        for position, color in markers:
            painter.setBrush(color)
            painter.drawEllipse(position, 3.5, 3.5)

    def _raster_region(self, event, dpr, phase_x, phase_y):
        rect = self.rect()
        width = ceil(rect.width() * dpr + phase_x)
        height = ceil(rect.height() * dpr + phase_y)
        if width * height * 4 <= RASTER_CACHE_BYTES:
            return 0, 0, width, height
        # For oversized boards, visibleRegion is clipped by the scroll viewport.
        # Its entire bounding rectangle (not just this paint's damaged strip)
        # gives subsequent Replay refreshes at the same scroll offset a cache hit.
        visible = self.visibleRegion().boundingRect().intersected(rect)
        if visible.isEmpty():
            visible = event.rect().intersected(rect)
        # Align the cache origin to physical pixels, including fractional DPR,
        # so regional rasterization does not introduce a subpixel translation.
        left = floor(visible.x() * dpr + phase_x)
        top = floor(visible.y() * dpr + phase_y)
        right = ceil((visible.x() + visible.width()) * dpr + phase_x)
        bottom = ceil((visible.y() + visible.height()) * dpr + phase_y)
        return left, top, right - left, bottom - top

    def paintEvent(self, event):
        if self._trace is None:
            return
        painter = QPainter(self)
        dpr = self.devicePixelRatioF()
        # At fractional DPR a child's origin can lie between physical pixels.
        # Preserve that phase in the raster and blit at an integer physical
        # origin; otherwise an unchanged curve shifts on the antialiasing grid.
        transform = painter.deviceTransform()
        phase_x = transform.dx() - floor(transform.dx())
        phase_y = transform.dy() - floor(transform.dy())
        left, top, width, height = self._raster_region(event, dpr, phase_x, phase_y)
        origin = QPointF((left - phase_x) / dpr, (top - phase_y) / dpr)
        key = (self.width(), self.height(), dpr, left, top, width, height, phase_x, phase_y)
        if key != self._raster_key:
            self._invalidate_raster()
            if width > 0 and height > 0 and width * height * 4 <= RASTER_CACHE_BYTES:
                raster = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
                if not raster.isNull():
                    raster.setDevicePixelRatio(dpr)
                    raster.fill(Qt.transparent)
                    raster_painter = QPainter(raster)
                    raster_painter.translate(-origin.x(), -origin.y())
                    self._draw_geometry(raster_painter)
                    raster_painter.end()
                    self._raster = raster
            self._raster_key = key
        if self._raster is not None:
            painter.drawImage(origin, self._raster)
        else:
            # An unusually large viewport/DPR or failed allocation still paints
            # correctly, using cached geometry without retaining a huge raster.
            self._draw_geometry(painter)
        painter.end()
