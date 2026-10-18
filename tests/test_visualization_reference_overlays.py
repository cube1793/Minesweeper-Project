"""Reference-only painters with literal geometry/style oracles."""
import ast
import os
from pathlib import Path
import unittest
from unittest.mock import Mock

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()
try:
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QFont
    import visualization_reference_overlays as overlays
except ImportError:
    overlays = None


@unittest.skipIf(overlays is None, 'PyQt5 unavailable')
class ReferenceOverlayTests(unittest.TestCase):
    def test_clues_are_literal_immutable_copy_of_supplied_coordinates(self):
        mines = [[0, 0], [2, 1]]
        clues = overlays.derive_answer_clues(4, 3, mines)
        self.assertEqual(clues, ((-1, 2, 1, 1), (1, 2, -1, 1), (0, 1, 1, 1)))
        mines[0][0] = 3
        mines.clear()
        self.assertEqual(clues[0][0], -1)
        with self.assertRaises(TypeError):
            clues[0][0] = 0
        self.assertEqual(overlays.derive_answer_clues(2, 1, ()), ((0, 0),))

    def test_invalid_reference_inputs_fail_without_sanitizing_or_generating(self):
        for width, height, mines in ((0, 2, ()), (2, True, ()), (2.0, 2, ()),
                (2, 2, ((0, 0), (0, 0))), (2, 2, ((2, 0),)),
                (2, 2, ((-1, 0),)), (2, 2, ((True, 0),)), (2, 2, ((0,),))):
            with self.subTest(width=width, height=height, mines=mines), self.assertRaises(ValueError):
                overlays.derive_answer_clues(width, height, mines)

    def test_answer_painter_obeys_only_supplied_public_mask_and_zero_is_blank(self):
        painter = Mock()
        font = QFont()
        overlays.paint_hidden_answers(painter, ((-1, 1, 0, 3),),
                                       ((True, True, True, False),), 28, font)
        calls = painter.drawText.call_args_list
        self.assertEqual([call.args[2] for call in calls], ['✹', '1'])
        self.assertEqual([(c.args[0].x(), c.args[0].y(), c.args[0].width()) for c in calls],
                         [(0, 0, 28), (28, 0, 28)])
        painter.setOpacity.assert_called_once_with(0.35)
        painter.setFont.assert_called_once_with(font)
        painter.save.assert_called_once()
        painter.restore.assert_called_once()
        painter.reset_mock()
        overlays.paint_hidden_answers(painter, ((-1, 8, 0),), ((False, False, True),), 28, font)
        painter.drawText.assert_not_called()

    def test_zero_or_one_route_point_has_no_invented_origin_segment(self):
        for points in ([], [QPointF(42, 14)]):
            painter = Mock()
            overlays.paint_action_target_route(painter, points)
            painter.drawPolyline.assert_not_called()
            painter.drawLine.assert_not_called()

    def test_route_preserves_exact_sequence_repetitions_and_style_order(self):
        points = [QPointF(42, 14), QPointF(42, 14), QPointF(98, 70)]
        painter = Mock()
        overlays.paint_action_target_route(painter, points)
        self.assertEqual(painter.drawPolyline.call_count, 2)
        for call in painter.drawPolyline.call_args_list:
            self.assertEqual(list(call.args[0]), points)
        pens = [call.args[0] for call in painter.setPen.call_args_list]
        self.assertEqual([(p.color().getRgb(), p.widthF()) for p in pens],
                         [((255, 255, 255, 100), 3.5), ((90, 70, 115, 165), 2.0)])
        painter.restore.assert_called_once()

    def test_painters_restore_callers_painter_even_on_failure(self):
        painter = Mock()
        painter.drawText.side_effect = RuntimeError('paint failure')
        with self.assertRaises(RuntimeError):
            overlays.paint_hidden_answers(painter, ((1,),), ((True,),), 28, QFont())
        painter.restore.assert_called_once()

    def test_helper_imports_only_qt_presentation_and_never_owns_prefix_or_clock(self):
        tree = ast.parse(Path(overlays.__file__).read_text(encoding='utf-8'))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imports, {'PyQt5.QtCore', 'PyQt5.QtGui'})
        self.assertFalse(any(isinstance(node, (ast.ClassDef, ast.Import)) for node in ast.walk(tree)))


if __name__ == '__main__':
    unittest.main()
