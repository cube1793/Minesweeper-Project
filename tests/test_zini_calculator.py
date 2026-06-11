import unittest

from board_snapshot import BoardSnapshot
from zini_calculator import ZiniResult, calculate_g_zini


class ZiniCalculatorTests(unittest.TestCase):
    def test_unplaced_snapshot_is_not_calculable(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=False,
            mines=frozenset(),
            adjacent=((0, 0), (0, 0)),
        )

        with self.assertRaises(ValueError):
            calculate_g_zini(snapshot)

    def test_finalized_snapshot_returns_result_shell(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        result = calculate_g_zini(snapshot)

        self.assertIsInstance(result, ZiniResult)
        self.assertIsInstance(result.clicks, int)
        self.assertIsInstance(result.moves, tuple)


if __name__ == "__main__":
    unittest.main()
