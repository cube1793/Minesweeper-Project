"""Independent, small complete-board oracle using only visible observations."""

import random
import unittest
from fractions import Fraction
from itertools import combinations, product

from core_engine import CellState
from simple_algorithm import InconsistentObservationError
from simple_probability import calculate_probabilities


H = CellState.HIDDEN.value
F = CellState.FLAGGED.value


def brute_force_visible_worlds(observation, num_mines):
    """Directly count complete boards, without any production solver helpers.

    Opened cells are safe and flags are mines. Every subset of HIDDEN cells
    of the required size is examined against every visible clue directly.
    The fixture and oracle do not need an engine or a supplied mine layout.
    """
    hidden = tuple(
        (x, y)
        for y, row in enumerate(observation)
        for x, value in enumerate(row)
        if value == H
    )
    flags = {
        (x, y)
        for y, row in enumerate(observation)
        for x, value in enumerate(row)
        if value == F
    }
    clues = {
        (x, y): value
        for y, row in enumerate(observation)
        for x, value in enumerate(row)
        if 0 <= value <= 8
    }
    mine_worlds = dict.fromkeys(hidden, 0)
    remaining = num_mines - len(flags)
    if not 0 <= remaining <= len(hidden):
        return 0, mine_worlds

    total_worlds = 0
    for selected in combinations(hidden, remaining):
        candidate_mines = flags.union(selected)
        if any(
            sum(
                abs(mx - x) <= 1 and abs(my - y) <= 1
                for mx, my in candidate_mines
            ) != number
            for (x, y), number in clues.items()
        ):
            continue
        total_worlds += 1
        for cell in selected:
            mine_worlds[cell] += 1
    return total_worlds, mine_worlds


class SimpleProbabilityOracleTests(unittest.TestCase):
    def assert_matches_oracle(self, observation, num_mines):
        total_worlds, mine_worlds = brute_force_visible_worlds(
            observation, num_mines
        )
        if total_worlds == 0:
            with self.assertRaises(InconsistentObservationError):
                calculate_probabilities(observation, num_mines)
            return False

        result = calculate_probabilities(observation, num_mines)
        self.assertEqual(result.total_worlds, total_worlds)
        self.assertIs(type(result.total_worlds), int)
        self.assertEqual(
            tuple(item.coordinate for item in result.probabilities),
            tuple(mine_worlds),
        )
        self.assertEqual(
            {item.coordinate: item.mine_worlds for item in result.probabilities},
            mine_worlds,
        )
        for item in result.probabilities:
            self.assertEqual(item.total_worlds, total_worlds)
            self.assertIs(type(item.mine_worlds), int)
            self.assertIs(type(item.total_worlds), int)
            self.assertIsInstance(item.probability, Fraction)
            self.assertEqual(
                item.probability,
                Fraction(mine_worlds[item.coordinate], total_worlds),
            )

        # Verify the public partition independently from build_constraints.
        opened = [
            (x, y)
            for y, row in enumerate(observation)
            for x, value in enumerate(row)
            if 0 <= value <= 8
        ]
        frontier = tuple(
            (x, y)
            for x, y in mine_worlds
            if any(abs(x - ox) <= 1 and abs(y - oy) <= 1 for ox, oy in opened)
        )
        self.assertEqual(result.frontier_cells, frontier)
        self.assertEqual(
            result.unconstrained_cells,
            tuple(cell for cell in mine_worlds if cell not in frontier),
        )
        self.assertEqual(
            sum(mine_worlds.values()),
            total_worlds * (num_mines - sum(row.count(F) for row in observation)),
        )
        return True

    def test_explicit_public_observations_at_every_total_mine_count(self):
        cases = {
            "unopened": ((H, H),),
            "flags_and_floating": ((F, H, H, H, H),),
            "fifty_fifty": ((H, 1, H),),
            "satisfied_without_hidden": ((1, F, 1),),
            "contradictory_clues": ((0, H, 1),),
            "overlap_with_variable_mine_count": ((1, H, 1), (H, H, H)),
            "overlap_with_floating_weight": (
                (H, 2, 2, H, H, H),
                (F, H, H, F, H, H),
            ),
            "two_components_and_floating": ((H, 1, H, H, H, 1, H),),
            "two_variable_components_and_floating": (
                (H, 2, 2, H, H, H, 2, 2, H),
                (F, H, H, F, H, F, H, H, F),
            ),
            "safe_and_mine_extremes": ((0, H, H, 3), (H, H, H, H)),
        }
        for name, observation in cases.items():
            area = len(observation) * len(observation[0])
            for num_mines in range(area + 1):
                with self.subTest(case=name, num_mines=num_mines):
                    self.assert_matches_oracle(observation, num_mines)

    def test_exhaustive_single_row_visible_states(self):
        # 125 visible observations x 4 totals = 500 oracle comparisons.
        for cells in product((H, F, 0, 1, 2), repeat=3):
            for num_mines in range(4):
                with self.subTest(cells=cells, num_mines=num_mines):
                    self.assert_matches_oracle((cells,), num_mines)

    def test_exhaustive_two_by_two_visible_states(self):
        # All possible supported, geometrically plausible values on 2x2:
        # 1,296 observations x 5 totals = 6,480 oracle comparisons.
        for cells in product((H, F, 0, 1, 2, 3), repeat=4):
            observation = (cells[:2], cells[2:])
            for num_mines in range(5):
                with self.subTest(cells=cells, num_mines=num_mines):
                    self.assert_matches_oracle(observation, num_mines)

    def test_seeded_small_public_observations_at_every_total(self):
        # Generate public states directly, including locally valid clues whose
        # overlap may be impossible. No answer board is used to obtain clues.
        rng = random.Random(2202)
        consistent = inconsistent = 0
        for case_index in range(160):
            width, height = ((5, 1), (4, 2), (3, 3), (4, 3))[case_index % 4]
            observation = [[H] * width for _ in range(height)]
            coordinates = [(x, y) for y in range(height) for x in range(width)]
            rng.shuffle(coordinates)
            flag_count = rng.randrange(3)
            for x, y in coordinates[:flag_count]:
                observation[y][x] = F
            opened_count = rng.randrange(1, min(4, len(coordinates) - flag_count) + 1)
            opened = coordinates[flag_count:flag_count + opened_count]
            for x, y in opened:
                observation[y][x] = 0
            for x, y in opened:
                neighbors = [
                    value
                    for ny, row in enumerate(observation)
                    for nx, value in enumerate(row)
                    if (nx, ny) != (x, y)
                    and abs(nx - x) <= 1
                    and abs(ny - y) <= 1
                ]
                adjacent_flags = neighbors.count(F)
                observation[y][x] = adjacent_flags + rng.randrange(
                    neighbors.count(H) + 1
                )
            for num_mines in range(width * height + 1):
                with self.subTest(case=case_index, num_mines=num_mines):
                    if self.assert_matches_oracle(observation, num_mines):
                        consistent += 1
                    else:
                        inconsistent += 1

        # Keep this corpus useful if fixture-generation code changes later.
        self.assertGreater(consistent, 100)
        self.assertGreater(inconsistent, 100)


if __name__ == "__main__":
    unittest.main()
