"""Frozen V1 oracles, independent byte fixtures, and real Engine equivalence."""

import hashlib
import inspect
import random
import runpy
import sys
import unittest
from dataclasses import FrozenInstanceError, fields, replace
from unittest.mock import Mock, patch

import benchmark_board
from benchmark_board import (
    EXPERT_GENERAL_V1,
    BenchmarkBoard,
    BenchmarkSetSpec,
    calculate_board_fingerprint,
    generate_board,
)


# Literal authoritative oracles from the frozen SPEC, never regenerated here.
GOLDEN_FINGERPRINTS = {
    0: "fbd8b8069ef4f449bbc844329579b6538d2b175c1cf99eb22c49c0585322e053",
    1: "007b8d203106dd32d1b5b6c46052bbeeeb9fde2be89c81023b01519fba1bee9e",
    2: "58b8e6399a435371a430a75bd0a51035614242662b53015c61eb61292ccdd28a",
    42: "9a86f62d6fcc7bd8a19f53308a84d0710c8238b5fbf72ea5041fa38e4603f2ac",
    999: "45f1236c061ece7041aba1312f16137ee68f2c43da2d7c0b9f2065c37877cace",
    99999: "9a5903f41835faa195d0c1e457ee5721cd93f514c503043b6b08492b4425a0af",
}
GOLDEN_PREFIX_DIGEST = "93852d335a46af9420dbdcdf0e256bb9149778f33602f6a4facdf0295677777c"


def small_spec(**overrides):
    values = dict(
        benchmark_set_id="SMALL_GENERAL_V1", width=4, height=3, num_mines=3,
        first_click_x=1, first_click_y=1, board_generator_version="V1",
        seed_scheme="game_index",
    )
    values.update(overrides)
    return BenchmarkSetSpec(**values)


class BenchmarkModelTests(unittest.TestCase):
    def test_primary_set_has_exact_frozen_fields_and_values(self):
        self.assertEqual(
            tuple(field.name for field in fields(BenchmarkSetSpec)),
            ("benchmark_set_id", "width", "height", "num_mines", "first_click_x",
             "first_click_y", "board_generator_version", "seed_scheme"),
        )
        self.assertEqual(EXPERT_GENERAL_V1, BenchmarkSetSpec(
            "EXPERT_GENERAL_V1", 30, 16, 99, 0, 0, "V1", "game_index",
        ))

    def test_board_has_only_identity_fields_and_both_models_are_frozen(self):
        board = generate_board(EXPERT_GENERAL_V1, 42)
        self.assertEqual(tuple(field.name for field in fields(board)), (
            "game_index", "seed", "mine_positions", "board_fingerprint",
        ))
        self.assertIsInstance(board.mine_positions, frozenset)
        for model in (EXPERT_GENERAL_V1, board):
            for field in fields(model):
                with self.subTest(model=type(model), field=field.name):
                    with self.assertRaises(FrozenInstanceError):
                        setattr(model, field.name, None)
        with self.assertRaises(AttributeError):
            board.mine_positions.add((0, 0))

    def test_board_copies_mutable_containers_and_nested_coordinates(self):
        fingerprint = calculate_board_fingerprint(3, 2, 1, [(1, 0)])
        for positions in ({(1, 0)}, [[1, 0]]):
            with self.subTest(positions=positions):
                board = BenchmarkBoard(0, 0, positions, fingerprint)
                if isinstance(positions, list):
                    positions[0][0] = 2
                positions.clear()
                self.assertEqual(board.mine_positions, frozenset({(1, 0)}))

    def test_spec_rejects_invalid_integers_and_uint32_overflow(self):
        for name in ("width", "height", "num_mines", "first_click_x", "first_click_y"):
            for value in (True, False, 1.0, "1", None, -1, 1 << 32):
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    small_spec(**{name: value})

    def test_spec_rejects_invalid_dimensions_count_and_first_click(self):
        for overrides in (
            dict(width=0), dict(height=0), dict(num_mines=12), dict(num_mines=13),
            dict(first_click_x=4), dict(first_click_y=3),
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                small_spec(**overrides)

    def test_spec_rejects_invalid_or_unsupported_metadata(self):
        for name, values in (
            ("benchmark_set_id", ("", "  ", None, True, [])),
            ("board_generator_version", ("V2", "v1", 1, True, None, [])),
            ("seed_scheme", ("random", "seed+1", 0, False, None, [])),
        ):
            for value in values:
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    small_spec(**{name: value})

    def test_zero_mines_and_last_safe_cell_are_valid(self):
        for spec in (
            small_spec(width=1, height=1, num_mines=0, first_click_x=0, first_click_y=0),
            small_spec(num_mines=11),
        ):
            board = generate_board(spec, 0)
            self.assertEqual(len(board.mine_positions), spec.num_mines)
            self.assertNotIn((spec.first_click_x, spec.first_click_y), board.mine_positions)

    def test_uint32_boundary_dimensions_need_no_allocation_during_validation(self):
        maximum = (1 << 32) - 1
        spec = small_spec(width=maximum, height=maximum, num_mines=maximum,
                          first_click_x=maximum - 1, first_click_y=maximum - 1)
        self.assertEqual(spec.width, maximum)

    def test_generation_rejects_invalid_spec_or_game_index(self):
        for spec in (None, {}, "EXPERT_GENERAL_V1"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                generate_board(spec, 0)
        for index in (-1, True, False, 1.0, "1", None):
            with self.subTest(index=index), self.assertRaises(ValueError):
                generate_board(EXPERT_GENERAL_V1, index)

    def test_board_rejects_invalid_indices_seeds_and_fingerprint_format(self):
        board = generate_board(EXPERT_GENERAL_V1, 0)
        for name in ("game_index", "seed"):
            for value in (-1, True, False, 1.0, "1", None):
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    replace(board, **{name: value})
        for value in (None, [], 123, "", "a" * 63, "a" * 65, "A" * 64,
                      "g" * 64, "a" * 63 + "\n", "\u0661" * 64):
            with self.subTest(fingerprint=value), self.assertRaises(ValueError):
                replace(board, board_fingerprint=value)

    def test_board_rejects_malformed_or_duplicate_coordinates(self):
        for mines in (None, [None], [(True, 0)], [(0, 1.5)], [(1,)],
                      [(-1, 0)], [(1 << 32, 0)], [(0, 0), (0, 0)]):
            with self.subTest(mines=mines), self.assertRaises(ValueError):
                BenchmarkBoard(0, 0, mines, "0" * 64)


class GeneratorV1Tests(unittest.TestCase):
    def test_representative_goldens(self):
        for seed, expected in GOLDEN_FINGERPRINTS.items():
            with self.subTest(seed=seed):
                board = generate_board(EXPERT_GENERAL_V1, seed)
                self.assertEqual((board.game_index, board.seed), (seed, seed))
                self.assertEqual(board.board_fingerprint, expected)
                self.assertRegex(board.board_fingerprint, r"\A[0-9a-f]{64}\Z")
                self.assertEqual(len(board.mine_positions), 99)
                self.assertNotIn((0, 0), board.mine_positions)

    def test_first_1000_prefix_digest(self):
        boards = [generate_board(EXPERT_GENERAL_V1, index) for index in range(1000)]
        self.assertEqual([board.game_index for board in boards], list(range(1000)))
        self.assertEqual([board.seed for board in boards], list(range(1000)))
        fingerprints = [board.board_fingerprint for board in boards]
        for fingerprint in fingerprints:
            self.assertRegex(fingerprint, r"\A[0-9a-f]{64}\Z")
        payload = b"\n".join(fingerprint.encode("ascii") for fingerprint in fingerprints)
        self.assertEqual(len(fingerprints), 1000)
        self.assertEqual(payload.count(b"\n"), 999)
        self.assertEqual(len(payload), 64999)
        self.assertFalse(payload.endswith(b"\n"))
        self.assertEqual(hashlib.sha256(payload).hexdigest(), GOLDEN_PREFIX_DIGEST)

    def test_generation_order_and_unrelated_calls_do_not_change_boards(self):
        originals = {index: generate_board(EXPERT_GENERAL_V1, index) for index in (0, 42, 999)}
        state = random.getstate()
        try:
            for index in (999, 42, 0, 42):
                random.random()
                generate_board(small_spec(), index + 17)
                duplicate = generate_board(EXPERT_GENERAL_V1, index)
                self.assertEqual(duplicate, originals[index])
                self.assertIsNot(duplicate, originals[index])
        finally:
            random.setstate(state)

    def test_generation_preserves_global_rng_state_and_avoids_global_sampler(self):
        state = random.getstate()
        try:
            with patch("random.seed", side_effect=AssertionError("Global seed forbidden")), \
                 patch("random.sample", side_effect=AssertionError("Global sample forbidden")):
                for index in GOLDEN_FINGERPRINTS:
                    generate_board(EXPERT_GENERAL_V1, index)
                    self.assertEqual(random.getstate(), state)
        finally:
            random.setstate(state)

    def test_exact_candidate_order_local_seed_and_single_sample_without_retries(self):
        candidates = [
            (0, 0), (1, 0), (2, 0), (3, 0),
            (0, 1), (2, 1), (3, 1),
            (0, 2), (1, 2), (2, 2), (3, 2),
        ]
        for seed in (0, 1, 42, (1 << 80) + 123):
            with self.subTest(seed=seed):
                expected = frozenset(random.Random(seed).sample(candidates, 3))
                sampler = Mock(wraps=random.Random(seed))
                with patch("benchmark_board.random.Random", return_value=sampler) as factory:
                    board = generate_board(small_spec(), seed)
                factory.assert_called_once_with(seed)
                sampler.sample.assert_called_once_with(candidates, 3)
                self.assertEqual(board.mine_positions, expected)
                self.assertEqual((board.game_index, board.seed), (seed, seed))

    def test_primary_corner_neighbors_can_each_contain_mines(self):
        neighbors = {(1, 0), (0, 1), (1, 1)}
        mined_neighbors = set()
        for seed in range(100):
            board = generate_board(EXPERT_GENERAL_V1, seed)
            self.assertNotIn((0, 0), board.mine_positions)
            mined_neighbors.update(board.mine_positions & neighbors)
        self.assertEqual(mined_neighbors, neighbors)

    def test_all_eight_neighbors_remain_eligible_at_an_interior_first_click(self):
        spec = small_spec(width=3, height=3, num_mines=8)
        neighbors = frozenset({(0, 0), (1, 0), (2, 0), (0, 1),
                               (2, 1), (0, 2), (1, 2), (2, 2)})
        for seed in (0, 42, 999):
            self.assertEqual(generate_board(spec, seed).mine_positions, neighbors)

    def test_duplicate_layouts_remain_separate_entries_with_equal_fingerprints(self):
        spec = small_spec(num_mines=11)
        first = generate_board(spec, 0)
        second = generate_board(spec, 1)
        self.assertNotEqual(first.game_index, second.game_index)
        self.assertEqual(first.mine_positions, second.mine_positions)
        self.assertEqual(first.board_fingerprint, second.board_fingerprint)

    def test_generation_metadata_does_not_enter_fingerprint(self):
        first = generate_board(small_spec(num_mines=0), 0)
        second = generate_board(small_spec(
            benchmark_set_id="OTHER_GENERAL_V1", num_mines=0,
            first_click_x=3, first_click_y=2,
        ), 999)
        self.assertEqual(first.mine_positions, second.mine_positions)
        self.assertEqual(first.board_fingerprint, second.board_fingerprint)
        self.assertEqual(tuple(inspect.signature(calculate_board_fingerprint).parameters),
                         ("width", "height", "num_mines", "mine_positions"))


class FingerprintTests(unittest.TestCase):
    def test_canonical_bytes_match_independent_fixture_in_any_input_order(self):
        # Manually encoded unsigned big-endian words; no production serializer
        # or sorting creates this oracle. x=256/257 also checks byte order.
        payload = b"MSLAYOUT1\0" + bytes.fromhex(
            "00000102 00000003 00000004 "  # width=258, height=3, mines=4
            "00000100 00000000 "           # (256, 0)
            "00000101 00000000 "           # (257, 0)
            "00000001 00000001 "           # (1, 1)
            "00000000 00000002"            # (0, 2)
        )
        self.assertEqual(len(payload), 10 + 12 + 4 * 8)
        expected = hashlib.sha256(payload).hexdigest()
        mines = [(0, 2), (257, 0), (1, 1), (256, 0)]
        for positions in (mines, reversed(mines), set(mines), frozenset(mines),
                          (list(cell) for cell in mines)):
            with self.subTest(container=type(positions)):
                actual = calculate_board_fingerprint(258, 3, 4, positions)
                self.assertEqual(actual, expected)
                self.assertRegex(actual, r"\A[0-9a-f]{64}\Z")

    def test_empty_and_fully_mined_layouts_have_no_first_click_restriction(self):
        for count, mines, encoded in (
            (0, (), "00000001 00000001 00000000"),
            (1, [(0, 0)], "00000001 00000001 00000001 00000000 00000000"),
        ):
            expected = hashlib.sha256(b"MSLAYOUT1\0" + bytes.fromhex(encoded)).hexdigest()
            self.assertEqual(calculate_board_fingerprint(1, 1, count, mines), expected)

    def test_changed_layout_or_dimensions_change_fingerprint(self):
        original = calculate_board_fingerprint(3, 2, 1, [(1, 0)])
        for dimensions, mines in (((3, 2), [(2, 0)]), ((2, 3), [(1, 0)])):
            self.assertNotEqual(original, calculate_board_fingerprint(*dimensions, 1, mines))

    def test_uint32_boundary_is_encoded_without_wrapping(self):
        maximum = (1 << 32) - 1
        payload = b"MSLAYOUT1\0" + bytes.fromhex(
            "ffffffff ffffffff 00000001 fffffffe fffffffe"
        )
        self.assertEqual(
            calculate_board_fingerprint(maximum, maximum, 1, [(maximum - 1, maximum - 1)]),
            hashlib.sha256(payload).hexdigest(),
        )

    def test_rejects_invalid_header_values(self):
        for name in ("width", "height", "num_mines"):
            for value in (True, False, 1.0, "1", None, -1, 1 << 32):
                inputs = dict(width=3, height=2, num_mines=1, mine_positions=[(1, 0)])
                inputs[name] = value
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    calculate_board_fingerprint(**inputs)
        for width, height, count in ((0, 2, 1), (3, 0, 1), (3, 2, 7)):
            with self.subTest(header=(width, height, count)), self.assertRaises(ValueError):
                calculate_board_fingerprint(width, height, count, [])

    def test_rejects_malformed_coordinate_containers(self):
        for mines in (None, 3, "12", [None], [3], [(1,)], [(1, 0, 2)],
                      ["10"], [{"x": 1, "y": 0}], [{0, 1}]):
            with self.subTest(mines=mines), self.assertRaises(ValueError):
                calculate_board_fingerprint(3, 2, 1, mines)

    def test_rejects_invalid_coordinate_values(self):
        for value in (True, False, 1.0, "1", None, -1, 1 << 32):
            for position in ((value, 0), (0, value)):
                with self.subTest(position=position), self.assertRaises(ValueError):
                    calculate_board_fingerprint(3, 2, 1, [position])

    def test_rejects_out_of_bounds_positions(self):
        for position in ((3, 0), (0, 2), ((1 << 32) - 1, 0)):
            with self.subTest(position=position), self.assertRaises(ValueError):
                calculate_board_fingerprint(3, 2, 1, [position])

    def test_rejects_duplicates_before_set_conversion_even_with_matching_distinct_count(self):
        for count in (1, 2):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "Duplicate"):
                calculate_board_fingerprint(3, 2, count, [(1, 0), [1, 0]])

    def test_rejects_wrong_mine_counts(self):
        for count, mines in ((0, [(1, 0)]), (1, []), (2, [(1, 0)])):
            with self.subTest(count=count, mines=mines), self.assertRaises(ValueError):
                calculate_board_fingerprint(3, 2, count, mines)


class BenchmarkBoundaryTests(unittest.TestCase):
    def test_generation_and_fingerprinting_work_without_other_project_layers(self):
        blocked = dict.fromkeys((
            "core_engine", "simple_algorithm", "simple_probability", "simple_decision",
            "simple_runner", "simple_telemetry", "telemetry_collector", "telemetry_model",
            "board_snapshot", "board_analyzer", "benchmark_runner", "sqlite3", "PyQt5",
        ))
        with patch.dict(sys.modules, blocked):
            namespace = runpy.run_path(benchmark_board.__file__)
            board = namespace["generate_board"](namespace["EXPERT_GENERAL_V1"], 42)
            fingerprint = namespace["calculate_board_fingerprint"](
                30, 16, 99, board.mine_positions,
            )
        self.assertEqual(board.board_fingerprint, GOLDEN_FINGERPRINTS[42])
        self.assertEqual(fingerprint, GOLDEN_FINGERPRINTS[42])

    def test_real_engine_fresh_open_matches_v1_candidate_order_and_layout(self):
        from core_engine import Action, GameStatus, MinesweeperEngine

        specs = (
            EXPERT_GENERAL_V1,
            small_spec(),
            small_spec(width=5, height=4, num_mines=6, first_click_x=4, first_click_y=3),
            small_spec(width=3, height=3, num_mines=8),
            small_spec(width=1, height=1, num_mines=0, first_click_x=0, first_click_y=0),
        )
        for spec in specs:
            click = (spec.first_click_x, spec.first_click_y)
            # Independent linear-cell traversal checks the complete population.
            candidates = []
            for offset in range(spec.width * spec.height):
                y, x = divmod(offset, spec.width)
                if (x, y) != click:
                    candidates.append((x, y))
            neighbors = {
                (click[0] + dx, click[1] + dy)
                for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0),
                               (1, 0), (-1, 1), (0, 1), (1, 1))
                if 0 <= click[0] + dx < spec.width and 0 <= click[1] + dy < spec.height
            }
            for seed in GOLDEN_FINGERPRINTS:
                with self.subTest(spec=spec, seed=seed):
                    board = generate_board(spec, seed)
                    engine = MinesweeperEngine(spec.width, spec.height, spec.num_mines)
                    self.assertFalse(engine.get_board_snapshot().mines_placed)
                    # Patch only the existing global sample boundary. OPEN,
                    # placement, adjacency, reveal, and snapshot all stay real.
                    with patch("core_engine.random.sample", side_effect=random.Random(seed).sample) as sample:
                        observation, _, _, _, _ = engine.step(*click, Action.OPEN)
                    sample.assert_called_once_with(candidates, spec.num_mines)
                    self.assertTrue(neighbors.issubset(sample.call_args.args[0]))
                    snapshot = engine.get_board_snapshot()
                    self.assertTrue(snapshot.mines_placed)
                    self.assertEqual(len(snapshot.mines), spec.num_mines)
                    self.assertEqual(snapshot.mines, board.mine_positions)
                    self.assertNotIn(click, snapshot.mines)
                    self.assertNotEqual(engine.status, GameStatus.LOST)
                    self.assertEqual(observation[click[1]][click[0]], len(neighbors & snapshot.mines))
                    if spec.width == spec.height == 3 and spec.num_mines == 8:
                        self.assertEqual(observation[click[1]][click[0]], 8)


if __name__ == "__main__":
    unittest.main()
