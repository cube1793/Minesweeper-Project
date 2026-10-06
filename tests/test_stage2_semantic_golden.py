"""Absolute accepted Stage-2 semantic-action guard for EXPERT_GENERAL_V1 [0, 2).

The fixture was extracted from a SHA-256-verified physical copy of run 1 of
the accepted 100k database, not generated from the code being tested. Before
copying, the original's full-file SHA-256 and absence of WAL/SHM/journal
sidecars were verified. The copy was read with SQLite mode=ro&immutable=1
and query_only=ON. Source and copy hashes and sidecars were checked again
afterwards. The original was never written. An initial read-only immutable
inspection/extraction preceded the copy; final fixture extraction and
comparison used only the verified physical copy.

N=2 is the smallest exact prefix covering WIN, LOSS, LOCAL, GLOBAL, and GUESS:
game 0 wins with 275/32/10 analyzed actions; game 1 loses with 0/1/2. N=1
cannot cover LOSS. The complete 322-action replay took about 0.42 seconds in
the reference CPython 3.12.14 environment during fixture qualification.
Elapsed timings are deliberately absent from both the fixture and its digest.

The fixture uses canonical UTF-8 JSON: sorted object keys, compact separators,
ASCII escaping, and no trailing newline. Action rows follow action_fields;
probabilities are reduced numerator/denominator strings, never floats.
Changing an expected digest requires new accepted evidence, not regeneration
from current solver output. The external database is not needed by CI.
"""

import hashlib
import json
import unittest
from collections import Counter
from fractions import Fraction
from pathlib import Path

from benchmark_board import EXPERT_GENERAL_V1
from benchmark_runner import _play_game


FIXTURE = Path(__file__).with_name("fixtures") / "stage2_semantic_golden_v1.json"
FIXTURE_SHA256 = "fee9f837b7bd4977e5a910feeeed987bd4c941ce895cdae449e82046cd8a49ff"
ACCEPTED_DATABASE_SHA256 = "8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f"
ACTION_FIELDS = [
    "action_index", "action_type", "x", "y", "status_after",
    "inference_category", "selection_candidate_count", "target_mine_probability",
    "minimum_available_mine_probability", "safe_cells_opened_delta", "explicit_flag_delta",
]


def _canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _probability(value):
    return None if value is None else f"{value.numerator}/{value.denominator}"


def _semantic_game(record, events):
    """Select semantic facts explicitly: compute fields cannot enter the hash."""
    return {
        "game_index": record.game_index,
        "seed": record.seed,
        "board_fingerprint": record.board_fingerprint,
        "first_click": [record.first_click_x, record.first_click_y],
        "result": record.result,
        "actions": [[
            event.action_index, event.action_type.name, event.x, event.y,
            event.status_after.name,
            None if event.inference_category is None else event.inference_category.name,
            event.selection_candidate_count, _probability(event.target_mine_probability),
            _probability(event.minimum_available_mine_probability),
            event.safe_cells_opened_delta, event.explicit_flag_delta,
        ] for event in events],
    }


class Stage2SemanticGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = FIXTURE.read_bytes()
        cls.golden = json.loads(cls.raw)

    def test_fixture_has_frozen_provenance_and_canonical_exact_encoding(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), FIXTURE_SHA256)
        self.assertEqual(self.raw, _canonical_bytes(self.golden))
        self.assertEqual(self.golden["format"], "STAGE2_SEMANTIC_ACTION_GOLDEN_V1")
        self.assertEqual(self.golden["source"]["database_sha256"], ACCEPTED_DATABASE_SHA256)
        self.assertEqual(self.golden["source"]["git_commit"],
                         "30b50575b7f8a807cb9f8573f8068f5294b75219")
        self.assertEqual(self.golden["source"]["run_status"], "COMPLETED")
        self.assertEqual(self.golden["source"]["requested_games"], 100000)
        self.assertEqual(self.golden["source"]["processed_games"], 100000)
        self.assertEqual(self.golden["action_fields"], ACTION_FIELDS)
        self.assertEqual(self.golden["benchmark"], {
            "benchmark_set_id": "EXPERT_GENERAL_V1", "board_generator_version": "V1",
            "first_click_policy": "FIRST_CLICK_FIXED_0_0", "width": 30, "height": 16,
            "num_mines": 99, "solver_stage": "STAGE_2", "solver_policy": "SIMPLE_MINIMUM_RISK",
            "solver_config_snapshot": {"accept_guesses": True, "initial_open": [0, 0]},
        })
        for game in self.golden["games"]:
            self.assertEqual(set(game), {
                "game_index", "seed", "board_fingerprint", "first_click", "result", "actions",
            })
            for action in game["actions"]:
                self.assertEqual(len(action), len(ACTION_FIELDS))
                for encoded in action[7:9]:
                    if encoded is not None:
                        self.assertEqual(encoded, _probability(Fraction(encoded)))

    def test_prefix_is_minimal_for_required_outcome_and_inference_coverage(self):
        self.assertEqual(self.golden["prefix"], [0, 2])
        games = self.golden["games"]
        self.assertEqual([game["game_index"] for game in games], [0, 1])
        self.assertEqual([game["seed"] for game in games], [0, 1])
        self.assertEqual([game["result"] for game in games], ["WIN", "LOSS"])
        self.assertEqual([len(game["actions"]) for game in games], [318, 4])
        expected = [
            {None: 1, "LOCAL_DETERMINISTIC": 275, "GLOBAL_CERTAINTY": 32, "PROBABILITY_GUESS": 10},
            {None: 1, "GLOBAL_CERTAINTY": 1, "PROBABILITY_GUESS": 2},
        ]
        for game, counts in zip(games, expected, strict=True):
            self.assertEqual(Counter(row[5] for row in game["actions"]), counts)
            self.assertEqual([row[0] for row in game["actions"]], list(range(len(game["actions"]))))
            self.assertEqual(game["actions"][0][1:4], ["OPEN", 0, 0])
            self.assertEqual(game["first_click"], [0, 0])
        self.assertNotEqual({game["result"] for game in games[:-1]}, {"WIN", "LOSS"})

    def test_current_stage2_benchmark_path_matches_every_accepted_semantic_action(self):
        # Exercise the existing shared production execution/adapter boundary.
        # No database connection is created by _play_game, and no timing is compared.
        for expected in self.golden["games"]:
            with self.subTest(game_index=expected["game_index"]):
                record, events = _play_game(EXPERT_GENERAL_V1, expected["game_index"])
                actual = _semantic_game(record, events)
                self.assertEqual(actual, expected)
                self.assertEqual(_canonical_bytes(actual), _canonical_bytes(expected))


if __name__ == "__main__":
    unittest.main()
