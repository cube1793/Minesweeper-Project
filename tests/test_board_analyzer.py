import unittest

from board_analyzer import CellClass, analyze_board
from board_snapshot import BoardSnapshot


class BoardAnalyzerTests(unittest.TestCase):
    def test_unplaced_snapshot_is_not_analyzable(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=False,
            mines=frozenset(),
            adjacent=((0, 0), (0, 0)),
        )

        with self.assertRaises(ValueError):
            analyze_board(snapshot)

    def test_empty_board_is_one_opening(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0, 0, 0), (0, 0, 0), (0, 0, 0)),
        )

        analysis = analyze_board(snapshot)

        self.assertEqual(analysis.total_ops, 1)
        self.assertEqual(analysis.total_3bv, 1)
        self.assertEqual(analysis.opening_id, ((0, 0, 0), (0, 0, 0), (0, 0, 0)))
        self.assertTrue(
            all(
                cell_class == CellClass.OPENING
                for row in analysis.cell_class
                for cell_class in row
            )
        )

    def test_center_mine_creates_eight_isolated_numbers(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )

        analysis = analyze_board(snapshot)

        self.assertEqual(analysis.total_ops, 0)
        self.assertEqual(analysis.total_3bv, 8)
        self.assertEqual(analysis.opening_id, ((-1, -1, -1), (-1, -1, -1), (-1, -1, -1)))
        self.assertIsNone(analysis.cell_class[1][1])
        safe_classes = [
            cell_class
            for row in analysis.cell_class
            for cell_class in row
            if cell_class is not None
        ]
        self.assertEqual(safe_classes.count(CellClass.ISOLATED), 8)

    def test_corner_mine_creates_one_opening_with_border_numbers(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )

        analysis = analyze_board(snapshot)

        self.assertEqual(analysis.total_ops, 1)
        self.assertEqual(analysis.total_3bv, 1)
        self.assertIsNone(analysis.cell_class[0][0])

        safe_classes = [
            cell_class
            for row in analysis.cell_class
            for cell_class in row
            if cell_class is not None
        ]
        self.assertEqual(safe_classes.count(CellClass.OPENING), 5)
        self.assertEqual(safe_classes.count(CellClass.BORDER), 3)
        self.assertEqual(safe_classes.count(CellClass.ISOLATED), 0)


if __name__ == "__main__":
    unittest.main()
