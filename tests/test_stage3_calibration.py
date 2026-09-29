"""Independent protocol counts, geometry, determinism and rejection checks.

The official manifest and literal SHA-256 golden are deliberately deferred
until Milestone B review. These tests do not write any calibration artifacts.
"""

import builtins
import hashlib
import json
import os
import random
import runpy
import subprocess
import sys
import unittest
from collections import Counter
from dataclasses import FrozenInstanceError, fields, replace
from unittest.mock import patch

import stage3_calibration as calibration
from stage3_calibration import (
    CalibrationManifest, CalibrationTrial, calculate_manifest_sha256,
    canonical_manifest_bytes, enumerate_feasible_orientations,
    feasible_start_cells, generate_manifest_v1, validate_manifest,
)


# Protocol facts transcribed independently of production constants/helpers.
EXPECTED_OFFSETS = (
    ("O00", 0, 0), ("O01", 1, 0), ("O02", 1, 1), ("O03", 2, 0),
    ("O04", 2, 1), ("O05", 3, 1), ("O06", 4, 3), ("O07", 6, 0),
    ("O08", 6, 4), ("O09", 8, 6), ("O10", 10, 0), ("O11", 12, 5),
    ("O12", 15, 8), ("O13", 20, 10), ("O14", 24, 12), ("O15", 29, 15),
)
EXPECTED_TRANSITIONS = (("LEFT", "LEFT"), ("LEFT", "RIGHT"),
                        ("RIGHT", "LEFT"), ("RIGHT", "RIGHT"))
SEEDS = (0, 1, 42, 20260930, (1 << 80) + 123)


def legal_deltas(abs_dx, abs_dy):
    # Exhaust the entire board displacement domain instead of using the
    # production sign/swap enumeration or its feasibility predicate.
    return tuple((dx, dy) for dx in range(-29, 30) for dy in range(-15, 16)
                 if sorted((abs(dx), abs(dy))) == sorted((abs_dx, abs_dy)))


def with_delta(trial, delta):
    dx, dy = delta
    start = (max(0, -dx), max(0, -dy))
    return replace(trial, dx=dx, dy=dy, start_cell=start,
                   target_cell=(start[0] + dx, start[1] + dy))


class GeometryTests(unittest.TestCase):
    def test_fixed_protocol_constants(self):
        self.assertEqual((calibration.GRID_WIDTH, calibration.GRID_HEIGHT,
                          calibration.CELL_SIZE_PX), (30, 16, 28))
        self.assertEqual(calibration.PROTOCOL_VERSION, "STAGE3_CALIBRATION_V1")
        self.assertEqual(calibration.OFFSET_FAMILIES, EXPECTED_OFFSETS)
        self.assertEqual(calibration.BUTTON_TRANSITIONS, EXPECTED_TRANSITIONS)
        self.assertEqual((calibration.BLOCK_COUNT, calibration.TRIALS_PER_BLOCK,
                          calibration.OFFICIAL_TRIAL_COUNT, calibration.WARMUP_TRIAL_COUNT,
                          calibration.REPETITIONS_PER_TRANSITION,
                          calibration.REPETITIONS_PER_BLOCK), (3, 128, 384, 24, 6, 2))

    def test_every_family_orientation_matches_exhaustive_geometry(self):
        for offset_id, dx, dy in EXPECTED_OFFSETS:
            with self.subTest(offset_id=offset_id):
                self.assertEqual(enumerate_feasible_orientations(dx, dy), legal_deltas(dx, dy))

    def test_zero_axes_diagonals_and_long_swaps(self):
        for absolute, expected in (
            ((0, 0), ((0, 0),)),
            ((1, 0), ((-1, 0), (0, -1), (0, 1), (1, 0))),
            ((1, 1), ((-1, -1), (-1, 1), (1, -1), (1, 1))),
            ((29, 15), ((-29, -15), (-29, 15), (29, -15), (29, 15))),
            ((30, 16), ()),
        ):
            with self.subTest(absolute=absolute):
                self.assertEqual(enumerate_feasible_orientations(*absolute), expected)

    def test_all_feasible_starts_match_exhaustive_board_search(self):
        for offset_id, ax, ay in EXPECTED_OFFSETS:
            for dx, dy in legal_deltas(ax, ay):
                with self.subTest(offset_id=offset_id, delta=(dx, dy)):
                    expected = tuple((x, y) for y in range(16) for x in range(30)
                                     if 0 <= x + dx < 30 and 0 <= y + dy < 16)
                    actual = feasible_start_cells(dx, dy)
                    self.assertEqual(actual, expected)
                    self.assertEqual(len(actual), (30 - abs(dx)) * (16 - abs(dy)))

    def test_start_edges_and_impossible_deltas(self):
        self.assertEqual(feasible_start_cells(29, 15), ((0, 0),))
        self.assertEqual(feasible_start_cells(-29, -15), ((29, 15),))
        for delta in ((30, 0), (-30, 0), (0, 16), (0, -16), (100, -100)):
            self.assertEqual(feasible_start_cells(*delta), ())

    def test_geometry_rejects_nonintegers_and_negative_absolute_components(self):
        for invalid in (True, False, 1.0, "1", None, [], (1,)):
            for operation in (enumerate_feasible_orientations, feasible_start_cells):
                for args in ((invalid, 0), (0, invalid)):
                    with self.subTest(operation=operation.__name__, args=args):
                        with self.assertRaises(ValueError):
                            operation(*args)
        for args in ((-1, 0), (0, -1)):
            with self.assertRaises(ValueError):
                enumerate_feasible_orientations(*args)


class ManifestTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = generate_manifest_v1(42)

    def replace_trial(self, index, trial):
        trials = list(self.manifest.trials)
        trials[index] = trial
        return replace(self.manifest, trials=trials)


class GenerationTests(ManifestTestCase):
    def test_exact_schedule_counts_for_multiple_seeds(self):
        for seed in SEEDS:
            with self.subTest(seed=seed):
                manifest = generate_manifest_v1(seed)
                self.assertEqual(manifest.seed, seed)
                self.assertIsNone(validate_manifest(manifest))
                self.assertEqual(len(manifest.trials), 408)
                warmup, official = manifest.trials[:24], manifest.trials[24:]
                self.assertEqual({trial.phase for trial in warmup}, {"WARMUP"})
                self.assertEqual({trial.block_index for trial in warmup}, {None})
                self.assertEqual({trial.offset_id for trial in warmup}, {row[0] for row in EXPECTED_OFFSETS})
                self.assertEqual(Counter((t.start_button, t.target_button) for t in warmup),
                                 Counter({transition: 6 for transition in EXPECTED_TRANSITIONS}))
                self.assertEqual({trial.phase for trial in official}, {"OFFICIAL"})
                self.assertEqual([t.block_index for t in official], [1] * 128 + [2] * 128 + [3] * 128)
                self.assertEqual(len({trial.trial_id for trial in manifest.trials}), 408)
                self.assertEqual(Counter((t.offset_id, t.start_button, t.target_button) for t in official),
                                 Counter({(o, a, b): 6 for o, _, _ in EXPECTED_OFFSETS
                                          for a, b in EXPECTED_TRANSITIONS}))
                self.assertEqual(Counter((t.block_index, t.offset_id, t.start_button, t.target_button)
                                         for t in official),
                                 Counter({(block, o, a, b): 2 for block in (1, 2, 3)
                                          for o, _, _ in EXPECTED_OFFSETS for a, b in EXPECTED_TRANSITIONS}))

    def test_generated_coordinates_and_family_deltas(self):
        for seed in SEEDS:
            for trial in generate_manifest_v1(seed).trials:
                with self.subTest(seed=seed, trial=trial.trial_id):
                    self.assertIn((trial.offset_id, trial.abs_dx, trial.abs_dy), EXPECTED_OFFSETS)
                    for x, y in (trial.start_cell, trial.target_cell):
                        self.assertTrue(0 <= x < 30 and 0 <= y < 16)
                    self.assertEqual((trial.dx, trial.dy),
                                     tuple(t - s for s, t in zip(trial.start_cell, trial.target_cell)))
                    self.assertEqual(sorted((abs(trial.dx), abs(trial.dy))),
                                     sorted((trial.abs_dx, trial.abs_dy)))

    def test_direction_balance_overall_and_per_transition_including_zero_counts(self):
        for seed in SEEDS:
            official = generate_manifest_v1(seed).trials[24:]
            for offset_id, ax, ay in EXPECTED_OFFSETS:
                orientations = legal_deltas(ax, ay)
                family_trials = [t for t in official if t.offset_id == offset_id]
                overall = Counter((t.dx, t.dy) for t in family_trials)
                with self.subTest(seed=seed, offset_id=offset_id):
                    self.assertEqual(set(overall), set(orientations))
                    self.assertEqual(sorted(overall.values()), [24 // len(orientations)] * len(orientations))
                    for transition in EXPECTED_TRANSITIONS:
                        counts = Counter((t.dx, t.dy) for t in family_trials
                                         if (t.start_button, t.target_button) == transition)
                        uses = [counts[delta] for delta in orientations]
                        self.assertEqual(sum(uses), 6)
                        self.assertLessEqual(max(uses) - min(uses), 1)

    def test_avoids_duplicate_pairs_except_unavoidable_corner_family(self):
        for seed in SEEDS:
            official = generate_manifest_v1(seed).trials[24:]
            for offset_id, _, _ in EXPECTED_OFFSETS:
                pairs = Counter((t.start_cell, t.target_cell) for t in official if t.offset_id == offset_id)
                with self.subTest(seed=seed, offset_id=offset_id):
                    if offset_id == "O15":
                        self.assertEqual(sorted(pairs.values()), [6] * 4)
                    else:
                        self.assertEqual(len(pairs), 24)

    def test_zero_offset_placements_are_dispersed_across_all_quadrants(self):
        for seed in SEEDS:
            trials = [t for t in generate_manifest_v1(seed).trials if t.offset_id == "O00"]
            uses = Counter((t.start_cell[0] // 15, t.start_cell[1] // 8) for t in trials)
            self.assertEqual(set(uses), {(0, 0), (0, 1), (1, 0), (1, 1)})
            self.assertLessEqual(max(uses.values()) - min(uses.values()), 1)

    def test_same_seed_is_byte_identical_and_different_seeds_change_schedule(self):
        originals = {seed: canonical_manifest_bytes(generate_manifest_v1(seed)) for seed in SEEDS}
        for seed in reversed(SEEDS):
            self.assertEqual(canonical_manifest_bytes(generate_manifest_v1(seed)), originals[seed])
        schedules = {generate_manifest_v1(seed).trials for seed in SEEDS}
        self.assertEqual(len(schedules), len(SEEDS))

    def test_generation_does_not_read_or_mutate_global_rng(self):
        state = random.getstate()
        try:
            with patch("random.seed", side_effect=AssertionError("global seed")), \
                 patch("random.shuffle", side_effect=AssertionError("global shuffle")), \
                 patch("random.choice", side_effect=AssertionError("global choice")):
                self.assertEqual(generate_manifest_v1(42), self.manifest)
                self.assertEqual(random.getstate(), state)
                random.random()
                self.assertEqual(generate_manifest_v1(42), self.manifest)
        finally:
            random.setstate(state)

    def test_seed_is_required_and_rejects_invalid_values(self):
        with self.assertRaises(TypeError):
            generate_manifest_v1()
        for seed in (-1, True, False, 42.0, "42", None):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                generate_manifest_v1(seed)


class ModelValidationTests(ManifestTestCase):
    def test_models_and_nested_collections_are_immutable_copies(self):
        trial = self.manifest.trials[0]
        start, target = list(trial.start_cell), list(trial.target_cell)
        copied_trial = replace(trial, start_cell=start, target_cell=target)
        trials = list(self.manifest.trials)
        offsets = [list(row) for row in EXPECTED_OFFSETS]
        transitions = [list(row) for row in EXPECTED_TRANSITIONS]
        copied = replace(self.manifest, trials=trials, offsets=offsets, button_transitions=transitions)
        start[0] = target[0] = -1
        trials.clear()
        offsets[0][1] = 999
        transitions[0][0] = "MIDDLE"
        self.assertEqual(copied_trial, trial)
        self.assertEqual(copied, self.manifest)
        for model in (copied, copied_trial):
            hash(model)
            for field in fields(model):
                with self.subTest(model=type(model), field=field.name):
                    with self.assertRaises(FrozenInstanceError):
                        setattr(model, field.name, None)
        with self.assertRaises(TypeError):
            copied.offsets[0][1] = 99
        with self.assertRaises(TypeError):
            copied_trial.start_cell[0] = 99

    def test_trial_rejects_malformed_identity_phase_blocks_and_buttons(self):
        trial = self.manifest.trials[24]
        for name, values in (
            ("trial_id", ("", " ", None, 1, [])),
            ("phase", ("warmup", "UNKNOWN", None, [])),
            ("block_index", (None, True, False, 1.0, "1", 0, -1, 4)),
            ("offset_id", ("O16", "", None, [])),
            ("start_button", ("left", "MIDDLE", None, [])),
            ("target_button", ("CHORD", "", None, [])),
        ):
            for value in values:
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    replace(trial, **{name: value})
        with self.assertRaisesRegex(ValueError, "WARMUP block_index"):
            replace(self.manifest.trials[0], block_index=0)

    def test_trial_rejects_malformed_cells_and_deltas(self):
        trial = self.manifest.trials[24]
        for name in ("start_cell", "target_cell"):
            for value in (None, "12", (), (1,), (1, 2, 3), (True, 0), (0, False),
                          (1.0, 0), (0, "1"), (-1, 0), (0, -1), (30, 0), (0, 16)):
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    replace(trial, **{name: value})
        for name in ("abs_dx", "abs_dy", "dx", "dy"):
            for value in (True, False, 0.0, "1", None):
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    replace(trial, **{name: value})

    def test_trial_rejects_family_mismatch_illegal_orientation_and_actual_delta_mismatch(self):
        zero = next(t for t in self.manifest.trials if t.offset_id == "O00")
        with self.assertRaisesRegex(ValueError, "offset family"):
            replace(zero, abs_dx=1)
        with self.assertRaisesRegex(ValueError, "feasible orientation"):
            replace(zero, dx=1)
        with self.assertRaisesRegex(ValueError, "Actual target - start"):
            replace(zero, start_cell=(0, 0), target_cell=(1, 0))
        corner = next(t for t in self.manifest.trials if t.offset_id == "O15")
        with self.assertRaisesRegex(ValueError, "feasible orientation"):
            replace(corner, dx=15, dy=29)

    def test_manifest_rejects_invalid_header_and_seed(self):
        for name, values in (
            ("protocol_version", ("V2", 1, None, [])),
            ("grid_width", (29, 31, 30.0, True, "30", None)),
            ("grid_height", (15, 17, 16.0, False, "16", None)),
            ("cell_size_px", (27, 29, 28.0, True, "28", None)),
            ("seed", (-1, 42.0, True, False, "42", None)),
        ):
            for value in values:
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    replace(self.manifest, **{name: value})

    def test_manifest_rejects_altered_catalogs_including_numeric_type_aliases(self):
        for offsets in (EXPECTED_OFFSETS[:-1], EXPECTED_OFFSETS + (EXPECTED_OFFSETS[0],),
                        EXPECTED_OFFSETS[::-1], (("O00", False, 0),) + EXPECTED_OFFSETS[1:],
                        (("O00", 0, 0.0),) + EXPECTED_OFFSETS[1:],
                        (("O00", 0),) + EXPECTED_OFFSETS[1:]):
            with self.subTest(offsets=offsets), self.assertRaises(ValueError):
                replace(self.manifest, offsets=offsets)
        for transitions in (EXPECTED_TRANSITIONS[:-1], EXPECTED_TRANSITIONS[::-1],
                            EXPECTED_TRANSITIONS + (("MIDDLE", "LEFT"),)):
            with self.subTest(transitions=transitions), self.assertRaises(ValueError):
                replace(self.manifest, button_transitions=transitions)

    def test_manifest_rejects_malformed_collections_and_trial_objects(self):
        for name in ("trials", "offsets", "button_transitions"):
            for value in (None, {}, "bad", 1):
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    replace(self.manifest, **{name: value})
        for name in ("offsets", "button_transitions"):
            with self.assertRaises(ValueError):
                replace(self.manifest, **{name: [None]})
        with self.assertRaisesRegex(ValueError, "CalibrationTrial"):
            self.replace_trial(0, {})
        for value in (None, {}, [], "manifest"):
            with self.assertRaisesRegex(ValueError, "CalibrationManifest"):
                validate_manifest(value)

    def test_manifest_rejects_missing_extra_or_duplicate_trials(self):
        for trials in (self.manifest.trials[:-1], self.manifest.trials + (self.manifest.trials[0],)):
            with self.assertRaisesRegex(ValueError, "24 warm-up and 384"):
                replace(self.manifest, trials=trials)
        for index, duplicate_id in ((25, self.manifest.trials[24].trial_id),
                                    (24, self.manifest.trials[0].trial_id)):
            with self.assertRaisesRegex(ValueError, "Duplicate trial_id"):
                self.replace_trial(index, replace(self.manifest.trials[index], trial_id=duplicate_id))

    def test_manifest_rejects_warmup_mixing_and_wrong_block_order(self):
        trials = list(self.manifest.trials)
        trials[0], trials[24] = trials[24], trials[0]
        with self.assertRaisesRegex(ValueError, "first 24"):
            replace(self.manifest, trials=trials)
        with self.assertRaisesRegex(ValueError, "Warm-up must be separated"):
            self.replace_trial(24, replace(self.manifest.trials[24], phase="WARMUP", block_index=None))
        with self.assertRaisesRegex(ValueError, "Official blocks"):
            self.replace_trial(24, replace(self.manifest.trials[24], block_index=2))

    def test_manifest_rejects_wrong_family_and_transition_multiplicities(self):
        trial = self.manifest.trials[24]
        with self.assertRaisesRegex(ValueError, "offset/transition/block"):
            self.replace_trial(24, replace(trial, start_button="RIGHT" if trial.start_button == "LEFT" else "LEFT"))
        donor = next(t for t in self.manifest.trials[24:152] if t.offset_id != trial.offset_id)
        with self.assertRaisesRegex(ValueError, "offset/transition/block"):
            self.replace_trial(24, replace(donor, trial_id=trial.trial_id))

    def test_manifest_rejects_wrong_block_repetitions_even_with_correct_global_totals(self):
        trials = list(self.manifest.trials)
        first = trials[24]
        other_index = next(i for i in range(152, 280) if trials[i].offset_id != first.offset_id)
        second = trials[other_index]
        trials[24] = replace(second, trial_id=first.trial_id, block_index=1)
        trials[other_index] = replace(first, trial_id=second.trial_id, block_index=2)
        self.assertEqual(Counter((t.offset_id, t.start_button, t.target_button) for t in trials[24:]),
                         Counter((t.offset_id, t.start_button, t.target_button) for t in self.manifest.trials[24:]))
        with self.assertRaisesRegex(ValueError, "offset/transition/block"):
            replace(self.manifest, trials=trials)

    def test_manifest_rejects_unbalanced_or_missing_orientations(self):
        index = next(i for i, t in enumerate(self.manifest.trials)
                     if t.phase == "OFFICIAL" and t.offset_id == "O04")
        trial = self.manifest.trials[index]
        with self.assertRaisesRegex(ValueError, "orientation counts"):
            self.replace_trial(index, with_delta(trial, (-trial.dx, -trial.dy)))
        trials = tuple(with_delta(t, (2, 1)) if t.phase == "OFFICIAL" and t.offset_id == "O04" else t
                       for t in self.manifest.trials)
        with self.assertRaisesRegex(ValueError, "orientation counts"):
            replace(self.manifest, trials=trials)

    def test_manifest_rejects_transition_bias_despite_perfect_overall_orientation_balance(self):
        trials = list(self.manifest.trials)
        orientations = legal_deltas(2, 1)
        transition_uses = Counter()
        for index, trial in enumerate(trials):
            if trial.phase != "OFFICIAL" or trial.offset_id != "O04":
                continue
            transition = (trial.start_button, trial.target_button)
            rank = EXPECTED_TRANSITIONS.index(transition)
            # Give each transition its own two directions, three uses each.
            delta = orientations[2 * rank + transition_uses[transition] % 2]
            transition_uses[transition] += 1
            trials[index] = with_delta(trial, delta)

        official = [t for t in trials if t.phase == "OFFICIAL" and t.offset_id == "O04"]
        self.assertEqual(Counter((t.dx, t.dy) for t in official),
                         Counter({delta: 3 for delta in orientations}))
        self.assertEqual(Counter((t.block_index, t.start_button, t.target_button) for t in official),
                         Counter({(block, a, b): 2 for block in (1, 2, 3)
                                  for a, b in EXPECTED_TRANSITIONS}))
        for transition in EXPECTED_TRANSITIONS:
            counts = Counter((t.dx, t.dy) for t in official
                             if (t.start_button, t.target_button) == transition)
            self.assertEqual(sorted(counts[delta] for delta in orientations), [0] * 6 + [3, 3])

        # Manifest construction invokes validate_manifest().
        with self.assertRaisesRegex(ValueError, "transition orientation counts.*O04"):
            replace(self.manifest, trials=trials)


class SerializationTests(ManifestTestCase):
    def test_canonical_bytes_match_independent_schema_and_hash(self):
        expected = {
            "protocol_version": "STAGE3_CALIBRATION_V1", "seed": 42,
            "grid_width": 30, "grid_height": 16, "cell_size_px": 28,
            "offsets": [list(row) for row in EXPECTED_OFFSETS],
            "button_transitions": [list(row) for row in EXPECTED_TRANSITIONS],
            "trials": [{
                "trial_id": t.trial_id, "phase": t.phase, "block_index": t.block_index,
                "offset_id": t.offset_id, "abs_dx": t.abs_dx, "abs_dy": t.abs_dy,
                "dx": t.dx, "dy": t.dy, "start_cell": list(t.start_cell),
                "target_cell": list(t.target_cell), "start_button": t.start_button,
                "target_button": t.target_button,
            } for t in self.manifest.trials],
        }
        payload = canonical_manifest_bytes(self.manifest)
        self.assertEqual(json.loads(payload), expected)
        self.assertEqual(payload, json.dumps(expected, sort_keys=True, separators=(",", ":"),
                                            ensure_ascii=True, allow_nan=False).encode("ascii"))
        self.assertTrue(payload.startswith(b'{"button_transitions":'))
        self.assertFalse(payload.endswith(b"\n"))
        self.assertNotIn(b" ", payload)
        self.assertEqual(calculate_manifest_sha256(self.manifest), hashlib.sha256(payload).hexdigest())

    def test_json_roundtrip_preserves_canonical_bytes_and_immutable_models(self):
        data = json.loads(canonical_manifest_bytes(self.manifest))
        data["trials"] = [CalibrationTrial(**trial) for trial in data["trials"]]
        restored = CalibrationManifest(**data)
        self.assertEqual(restored, self.manifest)
        self.assertEqual(canonical_manifest_bytes(restored), canonical_manifest_bytes(self.manifest))

    def test_hash_covers_seed_trial_order_identity_and_placement(self):
        trials = list(self.manifest.trials)
        trials[24], trials[25] = trials[25], trials[24]
        reordered = replace(self.manifest, trials=trials)
        renamed = self.replace_trial(0, replace(self.manifest.trials[0], trial_id="warmup-renamed"))
        zero_index = next(i for i, t in enumerate(self.manifest.trials) if t.offset_id == "O00")
        zero = self.manifest.trials[zero_index]
        moved_cell = ((zero.start_cell[0] + 1) % 30, zero.start_cell[1])
        moved = self.replace_trial(zero_index, replace(zero, start_cell=moved_cell, target_cell=moved_cell))
        variants = (self.manifest, replace(self.manifest, seed=43), reordered, renamed, moved)
        self.assertEqual(len({calculate_manifest_sha256(m) for m in variants}), len(variants))

    def test_deterministic_across_process_hash_seeds(self):
        expected = calculate_manifest_sha256(self.manifest)
        script = ("from stage3_calibration import generate_manifest_v1, calculate_manifest_sha256; "
                  "print(calculate_manifest_sha256(generate_manifest_v1(42)))")
        for hash_seed in ("1", "98765"):
            environment = dict(os.environ, PYTHONHASHSEED=hash_seed)
            result = subprocess.run([sys.executable, "-c", script], env=environment,
                                    cwd=os.path.dirname(calibration.__file__),
                                    check=True, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.stdout.strip(), expected)

    def test_core_executes_without_qt_engine_solver_or_telemetry(self):
        real_import = builtins.__import__

        def isolated_import(name, *args, **kwargs):
            if name.startswith(("PyQt", "core_engine", "simple_", "benchmark_", "telemetry_", "ui_manager")):
                raise AssertionError(f"Forbidden dependency: {name}")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=isolated_import):
            isolated = runpy.run_path(calibration.__file__)
            manifest = isolated["generate_manifest_v1"](42)
            payload = isolated["canonical_manifest_bytes"](manifest)
        self.assertEqual(payload, canonical_manifest_bytes(self.manifest))


if __name__ == "__main__":
    unittest.main()
