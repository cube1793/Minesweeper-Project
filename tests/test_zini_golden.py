"""Lock fresh V1 calculator/search output, independently of witness replay."""

from copy import deepcopy
import unittest

from benchmark_board import calculate_board_fingerprint
from tests.zini_golden_helpers import (
    WORKLOADS,
    assert_golden_equal,
    canonical_output,
    run_workload,
    workload_snapshot,
)
from tests.zini_v1_golden import GOLDEN, PROVENANCE


class ZiniV1GoldenTests(unittest.TestCase):
    def test_workload_inputs_and_board_identities_are_frozen(self):
        self.assertEqual(set(GOLDEN), set(WORKLOADS))
        for name, inputs in WORKLOADS.items():
            with self.subTest(workload=name):
                self.assertEqual(GOLDEN[name]["inputs"], inputs)
        for board, fingerprint in PROVENANCE["board_fingerprints"].items():
            with self.subTest(board=board):
                snapshot = workload_snapshot(board)
                self.assertEqual(calculate_board_fingerprint(
                    snapshot.width, snapshot.height, snapshot.num_mines,
                    snapshot.mines,
                ), fingerprint)

    def check_workload(self, name):
        actual = canonical_output(run_workload(WORKLOADS[name]))
        assert_golden_equal(self, GOLDEN[name]["expected"], actual, workload=name)

    def test_deterministic_board_c(self):
        self.check_workload("deterministic/board_c")

    def test_deterministic_expert1003(self):
        self.check_workload("deterministic/expert1003")

    def test_deterministic_general0(self):
        self.check_workload("deterministic/general0")

    def test_deterministic_general42(self):
        self.check_workload("deterministic/general42")

    def test_advanced_expert1003_standard_v1(self):
        self.check_workload("advanced/expert1003/standard_v1")

    def test_advanced_expert1003_chain_v1(self):
        self.check_workload("advanced/expert1003/chain_v1")

    def test_advanced_expert1003_standard_seeded_chain_v1(self):
        self.check_workload("advanced/expert1003/standard_seeded_chain_v1")

    def test_min_ties_expert1003_states_200(self):
        self.check_workload("min_ties/expert1003/states_200")

    def test_min_ties_board_c_exact(self):
        self.check_workload("min_ties/board_c/exact")

    def test_min_ties_board_c_states_200(self):
        self.check_workload("min_ties/board_c/states_200")


class ZiniGoldenComparatorTests(unittest.TestCase):
    def setUp(self):
        self.expected = {
            "clicks": 3,
            "moves": (("click", 1, 0, 2, 1), ("flag_chord", 1, 0, 2, 2)),
            "metadata": {"evaluations": 20, "generations": 2},
        }

    def mismatch(self, actual, expected=None):
        with self.assertRaises(AssertionError) as raised:
            assert_golden_equal(
                self, self.expected if expected is None else expected, actual,
                workload="comparator_probe",
            )
        return str(raised.exception)

    def test_equal_sequences_including_empty_are_accepted(self):
        for moves in (self.expected["moves"], ()):
            with self.subTest(moves=moves):
                expected = {**self.expected, "moves": moves}
                assert_golden_equal(
                    self, expected, deepcopy(expected), workload="equal",
                )

    def test_each_move_field_is_compared_even_with_equal_total_clicks(self):
        for field, replacement in enumerate(("fallback_click", 2, 1, None, 2)):
            with self.subTest(field=field):
                move = list(self.expected["moves"][0])
                move[field] = replacement
                actual = {**self.expected, "moves": (tuple(move), ("later",))}
                message = self.mismatch(actual)
                self.assertIn("[comparator_probe]", message)
                self.assertIn("expected move count: 2", message)
                self.assertIn("actual move count: 2", message)
                self.assertIn("first differing step index (0-based): 0", message)
                self.assertIn(f"expected move: {self.expected['moves'][0]!r}", message)
                self.assertIn(f"actual move: {tuple(move)!r}", message)
                self.assertNotIn("later", message)

    def test_either_sequence_can_end_first_including_empty(self):
        for count in (0, 1):
            shorter = {**self.expected, "moves": self.expected["moves"][:count]}
            for expected, actual, ended in (
                (self.expected, shorter, "actual"),
                (shorter, self.expected, "expected"),
            ):
                with self.subTest(count=count, ended=ended):
                    message = self.mismatch(actual, expected)
                    self.assertIn(f"expected move count: {len(expected['moves'])}", message)
                    self.assertIn(f"actual move count: {len(actual['moves'])}", message)
                    self.assertIn(f"first differing step index (0-based): {count}", message)
                    self.assertIn(f"{ended} move: <end of sequence>", message)

    def test_clicks_and_search_metadata_report_field_and_both_values(self):
        actual = deepcopy(self.expected)
        actual["clicks"] = 4
        actual["metadata"]["evaluations"] = 19
        actual["metadata"]["generations"] = 1
        message = self.mismatch(actual)
        self.assertIn("clicks: expected=3, actual=4", message)
        self.assertIn("metadata.evaluations: expected=20, actual=19", message)
        self.assertIn("metadata.generations: expected=2, actual=1", message)
        self.assertNotIn("differing step", message)

    def test_missing_extra_and_nested_metadata_are_reported(self):
        expected = deepcopy(self.expected)
        expected["metadata"]["config"] = {"seed": 0}
        actual = deepcopy(expected)
        actual["metadata"]["config"]["seed"] = 1
        del actual["metadata"]["evaluations"]
        actual["metadata"]["extra"] = True
        message = self.mismatch(actual, expected)
        self.assertIn("metadata.config.seed: expected=0, actual=1", message)
        self.assertIn("metadata.evaluations: expected=20, actual=<missing>", message)
        self.assertIn("metadata.extra: expected=<missing>, actual=True", message)


if __name__ == "__main__":
    unittest.main()
