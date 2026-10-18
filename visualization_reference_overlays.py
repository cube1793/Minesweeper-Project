"""Small reference painters; callers own truth, public masks and route prefixes.

No board acquisition, execution, timing or prefix selection belongs here.
"""

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF


ANSWER_OPACITY = 0.35
NUMBER_COLORS = {
    1: '#0000ff', 2: '#008000', 3: '#ff0000', 4: '#000080',
    5: '#800000', 6: '#008080', 7: '#000000', 8: '#808080',
}
ROUTE_COLOR = QColor(90, 70, 115, 165)
ROUTE_WIDTH = 2.0
ROUTE_UNDER_COLOR = QColor(255, 255, 255, 100)
ROUTE_UNDER_WIDTH = 3.5


def derive_answer_clues(width, height, mine_coordinates):
    """Copy/validate supplied fixed coordinates and return immutable clue rows.

    -1 denotes a mine. This is reference arithmetic, not board generation or
    inference; no source object is retained or changed.
    """
    if any(type(n) is not int or n <= 0 for n in (width, height)):
        raise ValueError('Reference dimensions must be positive integers.')
    mines = set()
    for coordinate in mine_coordinates:
        if (not isinstance(coordinate, (tuple, list)) or len(coordinate) != 2
                or any(type(n) is not int for n in coordinate)):
            raise ValueError('Mine coordinates must be integer pairs.')
        x, y = coordinate
        if not (0 <= x < width and 0 <= y < height) or (x, y) in mines:
            raise ValueError('Mine coordinates must be distinct and in bounds.')
        mines.add((x, y))
    return tuple(tuple(-1 if (x, y) in mines else sum(
        (x + dx, y + dy) in mines for dx in (-1, 0, 1) for dy in (-1, 0, 1)
        if dx or dy) for x in range(width)) for y in range(height))


def paint_hidden_answers(painter, answers, hidden_mask, cell_size, font):
    """The caller supplies the CURRENT public HIDDEN mask, independent of truth."""
    painter.save()
    try:
        painter.setOpacity(ANSWER_OPACITY)
        painter.setFont(font)
        for y, row in enumerate(answers):
            for x, answer in enumerate(row):
                if not hidden_mask[y][x] or answer == 0:
                    continue
                painter.setPen(QColor(NUMBER_COLORS.get(answer, '#000000')))
                painter.drawText(QRect(x * cell_size, y * cell_size, cell_size, cell_size),
                                 Qt.AlignCenter, '✹' if answer == -1 else str(answer))
    finally:
        painter.restore()


def paint_action_target_route(painter, points):
    """Paint precisely the supplied pixel centers, including repeated points.

    No origin is inserted; zero/one point has no target-to-target segment.
    """
    if len(points) < 2:
        return
    painter.save()
    try:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.NoBrush)
        polygon = QPolygonF(points)
        painter.setPen(QPen(ROUTE_UNDER_COLOR, ROUTE_UNDER_WIDTH))
        painter.drawPolyline(polygon)
        painter.setPen(QPen(ROUTE_COLOR, ROUTE_WIDTH))
        painter.drawPolyline(polygon)
    finally:
        painter.restore()
