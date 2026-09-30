"""Synthetic offline fixtures only; these are not human calibration evidence.

Records follow the committed collector format, but no Qt events are generated.
Independent 120-digit calculations and byte encodings check the 80-digit model.
"""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import (
    Context, Decimal, Inexact, ROUND_DOWN, ROUND_HALF_EVEN, getcontext, localcontext,
)
from pathlib import Path
from unittest.mock import patch

import stage3_calibration_analysis as analysis


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "calibration/stage3_calibration_manifest_v1.json"
FROZEN_SHA = "07ce6943abec4f47474f50bfb317fea3dcd9c51afcf87c316adef674f58ce61d"
CONSTANT_TABLE_SHA = "a93610593cc0fc723857790e2ff95a3b0a4d75a91c480f4e92c1d7082bf3b3e0"
SCHEDULE = json.loads(MANIFEST_PATH.read_bytes())


def reference_x(dx, dy):
    # Called inside the independent 120-digit context, never production helpers.
    return (Decimal(dx * dx + dy * dy).sqrt() + 1).ln() / Decimal(2).ln()


def retime(records):
    """Lay synthetic attempts sequentially on an artificial monotonic clock."""
    now = 1_000_000_000
    for record in records:
        duration = record["duration_ns"] if record["duration_ns"] is not None else 50_000
        record["start_press_ns"] = now
        record["end_ns"] = now + duration
        if record["start_release_ns"] is not None:
            record["start_release_ns"] = now + duration // 3
        if record["target_press_ns"] is not None:
            record["target_press_ns"] = now + duration
        samples = record["trajectory"]
        for index, sample in enumerate(samples):
            sample["relative_time_ns"] = duration * index // max(1, len(samples) - 1)
        now += duration + 1_000_000


def synthetic_fixture(*, constant=False):
    records = []
    with localcontext(Context(prec=120, rounding=ROUND_HALF_EVEN)):
        for trial in SCHEDULE["trials"]:
            start = [28 * v + 14.0 for v in trial["start_cell"]]
            target = [28 * v + 14.0 for v in trial["target_cell"]]
            duration = 100_000_000 if constant else int((100_000_000 + 25_000_000 *
                      reference_x(trial["abs_dx"], trial["abs_dy"])).to_integral_value())
            if trial["phase"] == "WARMUP":
                duration = 9_999_999_999  # Deliberately unrelated to fitted costs.
            records.append({**copy.deepcopy(trial), "attempt_index": 1, "valid": True,
                            "invalid_reason": None, "start_press_ns": 0, "start_release_ns": 1,
                            "target_press_ns": 2, "duration_ns": duration, "end_ns": 2,
                            "start_press_px": start, "target_press_px": target,
                            "trajectory": [
                                {"relative_time_ns": 0, "x_px": start[0], "y_px": start[1], "kind": "start"},
                                {"relative_time_ns": duration, "x_px": target[0], "y_px": target[1], "kind": "target"},
                            ]})
    retime(records)
    session = {
        "protocol_version": "STAGE3_CALIBRATION_V1", "manifest_sha256": FROZEN_SHA,
        "manifest_path": str(MANIFEST_PATH), "manifest_seed": 20260930,
        "session_id": "SYNTHETIC_TEST_ONLY", "session_status": "COMPLETED",
        "session_started_at_utc": "2026-09-30T00:00:00+00:00",
        "session_ended_at_utc": "2026-09-30T01:00:00+00:00",
        "os": "synthetic", "python_version": "3.12.14", "python_implementation": "CPython",
        "pyqt_version": "5.15.11", "qt_version": "5.15.2", "qt_platform": "offscreen",
        "clock": "injected", "timing_boundary": "start_press_to_target_press",
        "raw_timing_unit": "ns", "coordinate_unit": "qt_logical_px",
        "grid_width": 30, "grid_height": 16, "cell_size_px": 28,
        "notes": "SYNTHETIC TEST FIXTURE, NOT REAL CALIBRATION",
        "screen_name": None, "screen_resolution_logical_px": [840, 448],
        "qt_logical_dpi": 96.0, "device_pixel_ratio": 1.0,
        "display_refresh_rate_hz": None, "display_refresh_rate_status": "unavailable",
        "display_refresh_rate_unavailable_reason": "virtual_platform",
        "valid_warmup_attempts": 24, "valid_official_attempts": 384, "invalid_attempts": 0,
    }
    return session, records


class SessionAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_session, cls.base_records = synthetic_fixture()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="stage3-synthetic-analysis-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.session_path = self.root / "calibration_session_SYNTHETIC_TEST_ONLY.json"
        self.trials_path = self.root / "calibration_trials_SYNTHETIC_TEST_ONLY.jsonl"
        self.session = copy.deepcopy(self.base_session)
        self.records = copy.deepcopy(self.base_records)

    def save(self):
        self.session_path.write_text(json.dumps(self.session, sort_keys=True) + "\n", encoding="utf-8")
        self.trials_path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in self.records), encoding="utf-8")

    def analyze(self):
        self.save()
        return analysis.analyze_files(self.session_path, self.trials_path)

    def reject_before_fit(self, pattern=None):
        self.save()
        with patch.object(analysis, "fit_offset_medians", side_effect=AssertionError("must validate before fitting")):
            with self.assertRaisesRegex(ValueError, pattern or "."):
                analysis.analyze_files(self.session_path, self.trials_path)

    def insert_invalid(self, index=24, reason="WINDOW_DEACTIVATED", target=False):
        record = copy.deepcopy(self.records[index])
        record.update(valid=False, invalid_reason=reason, duration_ns=100_000 if target else None)
        if not target:
            record.update(target_press_ns=None, target_press_px=None, start_release_ns=None)
            record["trajectory"] = record["trajectory"][:1]
        self.records[index]["attempt_index"] = 2
        self.records.insert(index, record)
        self.session["invalid_attempts"] += 1
        retime(self.records)
        return record

    def test_complete_synthetic_session_accepted(self):
        report, profile = self.analyze()
        self.assertEqual((report["accepted_warmup_count"], report["accepted_official_count"],
                          report["invalid_attempt_count"]), (24, 384, 0))
        self.assertEqual(len(report["offsets"]), 16)
        self.assertTrue(all(row["count"] == 24 for row in report["offsets"]))
        self.assertEqual(profile["fitted_c_us"], "100000")
        self.assertLess(abs(Decimal(profile["fitted_b_us"]) - 25000), Decimal("0.0002"))

    def test_canonical_source_filenames_are_recorded_in_provenance(self):
        report, profile = self.analyze()
        for provenance in (report["provenance"], profile):
            self.assertEqual(provenance["source_session_filename"],
                             "calibration_session_SYNTHETIC_TEST_ONLY.json")
            self.assertEqual(provenance["source_trials_filename"],
                             "calibration_trials_SYNTHETIC_TEST_ONLY.jsonl")

    def test_session_a_with_session_b_trials_rejected_before_fit(self):
        self.session["session_id"] = "SESSION_A"
        self.session_path = self.root / "calibration_session_SESSION_A.json"
        self.trials_path = self.root / "calibration_trials_SESSION_B.jsonl"
        self.reject_before_fit("Trials filename must match session_id exactly")

    def test_session_b_with_session_a_trials_rejected_before_fit(self):
        self.session["session_id"] = "SESSION_B"
        self.session_path = self.root / "calibration_session_SESSION_B.json"
        self.trials_path = self.root / "calibration_trials_SESSION_A.jsonl"
        self.reject_before_fit("Trials filename must match session_id exactly")

    def test_session_filename_must_match_metadata_id_exactly(self):
        self.session["session_id"] = "SESSION_A"
        self.trials_path = self.root / "calibration_trials_SESSION_A.jsonl"
        for name in ("calibration_session_SESSION_B.json", "SESSION_A.json",
                     "calibration_session_SESSION_A.JSON"):
            with self.subTest(filename=name):
                self.session_path = self.root / name
                self.reject_before_fit("Session filename must match session_id exactly")

    def test_canonical_pair_can_move_without_changing_hashes_fit_or_table(self):
        before_report, before_profile = self.analyze()
        source_bytes = [self.session_path.read_bytes(), self.trials_path.read_bytes()]
        destination = self.root / "arbitrary-parent"
        destination.mkdir()
        moved_session = self.session_path.rename(destination / self.session_path.name)
        moved_trials = self.trials_path.rename(destination / self.trials_path.name)
        after_report, after_profile = analysis.analyze_files(moved_session, moved_trials)
        self.assertEqual(source_bytes, [moved_session.read_bytes(), moved_trials.read_bytes()])
        for provenance in (after_report["provenance"], after_profile):
            self.assertEqual(provenance["source_session_sha256"], hashlib.sha256(source_bytes[0]).hexdigest())
            self.assertEqual(provenance["source_trials_sha256"], hashlib.sha256(source_bytes[1]).hexdigest())
        # Full output equality includes all fitted parameters, table entries,
        # table hash, diagnostics, provenance and their serialized bytes.
        self.assertEqual(analysis.canonical_output_bytes(before_report), analysis.canonical_output_bytes(after_report))
        self.assertEqual(analysis.canonical_output_bytes(before_profile), analysis.canonical_output_bytes(after_profile))

    def test_missing_official_and_warmup_coverage_rejected(self):
        for index in (0, 24, 200, 407):
            with self.subTest(index=index):
                self.records = copy.deepcopy(self.base_records)
                del self.records[index]
                self.reject_before_fit("coverage")

    def test_duplicate_accepted_id_rejected(self):
        self.records.insert(25, copy.deepcopy(self.records[24]))
        self.reject_before_fit("Duplicate accepted")

    def test_unknown_trial_rejected(self):
        self.records[24]["trial_id"] = "invented"
        self.reject_before_fit("Unknown trial")

    def test_every_stored_schedule_field_must_match(self):
        for key, wrong in {
            "phase": "WARMUP", "block_index": 2, "offset_id": "O99", "abs_dx": 99,
            "abs_dy": 99, "dx": 99, "dy": 99, "start_cell": [0, -1],
            "target_cell": [0, -1], "start_button": "MIDDLE", "target_button": "MIDDLE",
        }.items():
            with self.subTest(key=key):
                self.records = copy.deepcopy(self.base_records)
                self.records[24][key] = wrong
                self.reject_before_fit("Schedule mismatch")

    def test_schedule_integer_aliases_rejected(self):
        for key, value in (("block_index", True), ("abs_dx", float(self.records[24]["abs_dx"]))):
            with self.subTest(key=key):
                self.records = copy.deepcopy(self.base_records)
                self.records[24][key] = value
                self.reject_before_fit("Schedule mismatch")

    def test_wrong_required_metadata_rejected(self):
        for key, value in {
            "session_status": "IN_PROGRESS", "protocol_version": "V2", "manifest_seed": 42,
            "manifest_sha256": "0" * 64, "grid_width": 31, "grid_height": 17,
            "cell_size_px": 32, "timing_boundary": "release_to_press", "raw_timing_unit": "us",
            "coordinate_unit": "physical_px", "valid_warmup_attempts": 23,
            "valid_official_attempts": 383, "invalid_attempts": 1,
        }.items():
            with self.subTest(key=key):
                self.session = copy.deepcopy(self.base_session)
                self.session[key] = value
                self.reject_before_fit()

    def test_missing_provenance_rejected(self):
        for key in ("session_id", "os", "manifest_path", "clock", "session_ended_at_utc",
                    "display_refresh_rate_hz", "device_pixel_ratio"):
            with self.subTest(key=key):
                self.session = copy.deepcopy(self.base_session)
                del self.session[key]
                self.reject_before_fit()

    def test_metadata_integer_aliases_rejected(self):
        self.session["grid_width"] = 30.0
        self.reject_before_fit("grid_width")

    def test_session_dates_require_ordered_utc(self):
        for value in (None, "invalid", "2026-09-30T01:00:00", "2026-09-29T00:00:00+00:00"):
            with self.subTest(value=value):
                self.session["session_ended_at_utc"] = value
                self.reject_before_fit()

    def test_invalid_durations_rejected(self):
        for duration in (None, 0, -1, True, 1.5, "100000000", 100_000_000.0):
            with self.subTest(duration=duration):
                self.records[24]["duration_ns"] = duration
                self.reject_before_fit("duration")

    def test_inconsistent_timestamps_and_missing_release_rejected(self):
        for key, value in (("target_press_ns", 1), ("end_ns", 1), ("start_release_ns", None),
                           ("start_release_ns", 10**20), ("start_press_ns", -1)):
            with self.subTest(key=key, value=value):
                self.records = copy.deepcopy(self.base_records)
                self.records[24][key] = value
                self.reject_before_fit()

    def test_trajectory_endpoints_are_required(self):
        changes = (
            lambda r: r.update(trajectory=r["trajectory"][1:]),
            lambda r: r.update(trajectory=r["trajectory"][:-1]),
            lambda r: r["trajectory"][0].update(relative_time_ns=1),
            lambda r: r["trajectory"][0].update(x_px=1),
            lambda r: r["trajectory"][-1].update(kind="move"),
            lambda r: r["trajectory"][-1].update(relative_time_ns=1),
            lambda r: r["trajectory"][-1].update(y_px=1),
        )
        for mutate in changes:
            with self.subTest(mutation=mutate):
                self.records = copy.deepcopy(self.base_records)
                mutate(self.records[24])
                self.reject_before_fit()

    def test_malformed_trajectory_and_click_points_rejected(self):
        for sample in (
            {"relative_time_ns": -1, "x_px": 10, "y_px": 10, "kind": "move"},
            {"relative_time_ns": 0.5, "x_px": 10, "y_px": 10, "kind": "move"},
            {"relative_time_ns": 10**20, "x_px": 10, "y_px": 10, "kind": "move"},
            {"relative_time_ns": 1, "x_px": -1, "y_px": 10, "kind": "move"},
            {"relative_time_ns": 1, "x_px": True, "y_px": 10, "kind": "move"},
        ):
            with self.subTest(sample=sample):
                self.records = copy.deepcopy(self.base_records)
                self.records[24]["trajectory"].insert(1, sample)
                self.reject_before_fit()

    def test_valid_actual_target_must_be_in_scheduled_cell(self):
        r = self.records[24]
        r["target_press_px"] = [-1, -1]
        r["trajectory"][-1].update(x_px=-1, y_px=-1)
        self.reject_before_fit("TARGET click")

    def test_attempt_order_and_retry_indices_rejected(self):
        self.records[24], self.records[25] = self.records[25], self.records[24]
        self.reject_before_fit("order")
        self.records = copy.deepcopy(self.base_records)
        self.records[24]["attempt_index"] = 2
        self.reject_before_fit("attempt index")

    def test_invalid_attempts_preserved_and_excluded_from_fit(self):
        base_report, base_profile = self.analyze()
        self.insert_invalid()
        bad = self.insert_invalid(index=30, reason="WRONG_TARGET", target=True)
        bad["duration_ns"] = 10**15
        bad["target_press_px"] = [-100, -100]
        bad["trajectory"][-1].update(x_px=-100, y_px=-100)
        retime(self.records)
        report, profile = self.analyze()
        self.assertEqual(report["invalid_attempt_count"], 2)
        self.assertEqual(report["invalid_reason_counts"], {"WINDOW_DEACTIVATED": 1, "WRONG_TARGET": 1})
        self.assertIsNone(report["invalid_attempts"][0]["duration_ns"])
        self.assertIsNone(report["invalid_attempts"][0]["target_press_ns"])
        self.assertEqual(report["invalid_attempts"][1]["duration_ns"], 10**15)
        self.assertEqual(report["offsets"], base_report["offsets"])
        self.assertEqual(profile["table_sha256"], base_profile["table_sha256"])

    def test_interrupted_attempt_must_keep_null_fields(self):
        r = self.insert_invalid()
        r["duration_ns"] = r["end_ns"] - r["start_press_ns"]
        self.reject_before_fit("null")

    def test_invalid_zero_duration_target_is_preserved(self):
        r = self.insert_invalid(reason="NON_POSITIVE_DURATION", target=True)
        r["duration_ns"] = 0
        retime(self.records)
        report, _ = self.analyze()
        self.assertEqual(report["invalid_attempts"][0]["duration_ns"], 0)

    def test_warmup_excluded_from_all_fitting_input(self):
        report1, profile1 = self.analyze()
        for r in self.records[:24]:
            r["duration_ns"] = 10**17
        retime(self.records)
        report2, profile2 = self.analyze()
        self.assertEqual(profile1["table_sha256"], profile2["table_sha256"])
        self.assertEqual(report1["anchored_fit"], report2["anchored_fit"])
        self.assertEqual(report1["button_transitions"], report2["button_transitions"])

    def test_slow_valid_observation_retained_but_fit_uses_medians(self):
        report1, profile1 = self.analyze()
        slow = next(r for r in self.records if r["phase"] == "OFFICIAL" and r["offset_id"] == "O04")
        slow["duration_ns"] = 10**16
        retime(self.records)
        report2, profile2 = self.analyze()
        offset = next(o for o in report2["offsets"] if o["offset_id"] == "O04")
        self.assertEqual(offset["count"], 24)
        self.assertEqual(offset["max_ns"], 10**16)
        self.assertEqual(profile1["table_sha256"], profile2["table_sha256"])
        self.assertEqual(report1["anchored_fit"], report2["anchored_fit"])

    def test_majority_slow_valid_observations_change_median_and_fit(self):
        selected = [r for r in self.records if r["phase"] == "OFFICIAL" and r["offset_id"] == "O04"]
        for r in selected[:13]:
            r["duration_ns"] = 10**12
        retime(self.records)
        report, profile = self.analyze()
        offset = next(o for o in report["offsets"] if o["offset_id"] == "O04")
        self.assertEqual(offset["median_ns"], "1000000000000")
        self.assertGreater(Decimal(profile["fitted_b_us"]), 25000)

    def test_exact_even_median_and_anchored_c(self):
        selected = [r for r in self.records if r["phase"] == "OFFICIAL" and r["offset_id"] == "O00"]
        for index, record in enumerate(selected):
            record["duration_ns"] = 100_000_000 + index
        retime(self.records)
        report, profile = self.analyze()
        self.assertEqual(report["offsets"][0]["median_ns"], "100000011.5")
        self.assertEqual(profile["fitted_c_us"], "100000.0115")

    def test_negative_anchored_slope_is_rejected(self):
        for r in self.records:
            if r["phase"] == "OFFICIAL" and r["offset_id"] == "O00":
                r["duration_ns"] = 10**12
        retime(self.records)
        with self.assertRaisesRegex(ValueError, "b >= 0"):
            self.analyze()

    def test_free_fit_and_equal_distance_diagnostics_do_not_replace_anchor(self):
        for r in self.records:
            if r["phase"] == "OFFICIAL" and r["offset_id"] == "O09":
                r["duration_ns"] += 100_000_000
        retime(self.records)
        report, profile = self.analyze()
        free = report["free_intercept_diagnostic"]
        self.assertFalse(free["authoritative"])
        self.assertNotEqual(free["c_hat_us"], profile["fitted_c_us"])
        self.assertEqual(profile["fitted_c_us"], "100000")
        self.assertEqual(profile["fitted_b_us"], report["anchored_fit"]["b_us"])
        shape = report["shape_sanity"]["equal_distance_families"]
        self.assertEqual(shape["observed_median_difference_us"], "100000")
        self.assertTrue(shape["equal_prediction"] and shape["equal_table_ticks"])

    def test_transition_and_orientation_diagnostics(self):
        report, _ = self.analyze()
        self.assertEqual([r["count"] for r in report["button_transitions"]], [96] * 4)
        self.assertEqual(len(report["offset_button_transitions"]), 64)
        self.assertTrue(all(r["count"] == 6 for r in report["offset_button_transitions"]))
        orientations = report["orientations"]
        self.assertEqual(len(orientations), 89)
        self.assertEqual(sum(r["count"] for r in orientations), 384)
        self.assertTrue(all("median_residual_us" in r for r in orientations))

    def test_click_and_path_diagnostics_do_not_define_duration(self):
        chosen = next(r for r in self.records if r["phase"] == "OFFICIAL" and r["offset_id"] == "O01")
        chosen["start_press_px"][0] += 3
        chosen["start_press_px"][1] += 4
        chosen["trajectory"][0].update(x_px=chosen["start_press_px"][0], y_px=chosen["start_press_px"][1])
        chosen["target_press_px"][0] -= 0.25
        chosen["trajectory"][-1].update(x_px=chosen["target_press_px"][0])
        # Many extreme in-canvas movements remain diagnostic, with no cutoff.
        chosen["trajectory"][1:1] = [
            {"relative_time_ns": 0, "x_px": 1 if i % 2 else 839,
             "y_px": 1 if i % 2 else 447, "kind": "move"} for i in range(20)]
        retime(self.records)
        report, profile = self.analyze()
        diagnostic = report["geometry_diagnostics"]
        self.assertEqual((diagnostic["path_ratio_count"], diagnostic["zero_distance_excluded_count"]), (360, 24))
        item = next(x for x in diagnostic["trials"] if x["trial_id"] == chosen["trial_id"])
        self.assertEqual(item["start_offset_from_center"]["radius_px"], "5")
        self.assertEqual(item["target_offset_from_center"]["dx_px"], "-0.25")
        self.assertGreater(Decimal(item["path_ratio"]), 100)
        with localcontext(Context(prec=120)):
            points = [(Decimal(str(p["x_px"])), Decimal(str(p["y_px"]))) for p in chosen["trajectory"]]
            length = sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2).sqrt() for a, b in zip(points, points[1:]))
            self.assertLess(abs(Decimal(item["path_ratio"]) - length / 28), Decimal("1e-70"))
        self.assertEqual(profile["fitted_c_us"], "100000")
        self.assertLess(abs(Decimal(profile["fitted_b_us"]) - 25000), Decimal("0.0002"))
        self.assertTrue(all(x["path_ratio"] is None for x in diagnostic["trials"] if x["offset_id"] == "O00"))

    def test_profile_schema_and_exact_provenance(self):
        report, profile = self.analyze()
        self.assertEqual(profile["source_manifest_sha256"], FROZEN_SHA)
        self.assertEqual(profile["source_session_sha256"], hashlib.sha256(self.session_path.read_bytes()).hexdigest())
        self.assertEqual(profile["source_trials_sha256"], hashlib.sha256(self.trials_path.read_bytes()).hexdigest())
        self.assertEqual(profile["source_session_id"], "SYNTHETIC_TEST_ONLY")
        self.assertEqual(profile["source_protocol_version"], "STAGE3_CALIBRATION_V1")
        self.assertEqual((profile["physical_profile_version"], profile["schema_version"]), (1, 1))
        self.assertEqual((profile["grid_width"], profile["grid_height"], profile["cell_size_px"]), (30, 16, 28))
        self.assertEqual((profile["distance_unit"], profile["timing_tick_unit"]), ("cell_width", "1_us"))
        self.assertEqual((profile["canonical_chord_input"], profile["canonical_chord_action"],
                          profile["canonical_chord_target"]), ("LEFT", "LEFT_CLICK", "revealed_clue"))
        self.assertEqual(profile["table_order"], "dx_major_dy_minor")
        self.assertEqual(profile["numeric_contract"]["precision"], 80)
        self.assertIsInstance(profile["fitted_c_us"], str)
        self.assertIsInstance(profile["fitted_b_us"], str)
        self.assertNotIn(b"trajectory", analysis.canonical_output_bytes(profile))
        self.assertEqual(report["session_metadata"], self.session)

    def test_display_refresh_is_provenance_only(self):
        report1, profile1 = self.analyze()
        self.assertIsNone(report1["session_metadata"]["display_refresh_rate_hz"])
        self.session.update(display_refresh_rate_hz=144.0, display_refresh_rate_status="qt_reported_approximate",
                            display_refresh_rate_unavailable_reason=None, device_pixel_ratio=2.0)
        report2, profile2 = self.analyze()
        self.assertEqual(profile1["table_sha256"], profile2["table_sha256"])
        self.assertEqual(report1["anchored_fit"], report2["anchored_fit"])
        self.assertEqual(report2["session_metadata"]["display_refresh_rate_hz"], 144.0)

    def test_constant_synthetic_profile_literal_golden(self):
        self.session, self.records = synthetic_fixture(constant=True)
        _, profile = self.analyze()
        expected = ",".join(["100000"] * 480).encode("ascii")
        self.assertEqual(profile["fitted_b_us"], "0")
        self.assertEqual(profile["table_sha256"], CONSTANT_TABLE_SHA)
        self.assertEqual(hashlib.sha256(expected).hexdigest(), CONSTANT_TABLE_SHA)
        self.assertEqual(profile["timing_table_us"], [[100000] * 16 for _ in range(30)])

    def test_repeated_analysis_identical_and_raw_files_unchanged(self):
        self.save()
        before = [self.session_path.read_bytes(), self.trials_path.read_bytes(), MANIFEST_PATH.read_bytes()]
        first = analysis.analyze_files(self.session_path, self.trials_path)
        second = analysis.analyze_files(self.session_path, self.trials_path)
        self.assertEqual([analysis.canonical_output_bytes(x) for x in first],
                         [analysis.canonical_output_bytes(x) for x in second])
        self.assertEqual(before, [self.session_path.read_bytes(), self.trials_path.read_bytes(), MANIFEST_PATH.read_bytes()])

    def test_source_hash_tracks_exact_bytes_not_parsed_json(self):
        _, profile1 = self.analyze()
        self.session_path.write_bytes(self.session_path.read_bytes() + b"\n")
        _, profile2 = analysis.analyze_files(self.session_path, self.trials_path)
        self.assertNotEqual(profile1["source_session_sha256"], profile2["source_session_sha256"])
        self.assertEqual(profile1["table_sha256"], profile2["table_sha256"])

    def test_modified_or_missing_frozen_manifest_fails_without_generator(self):
        self.save()
        modified = self.root / "manifest.json"
        modified.write_bytes(MANIFEST_PATH.read_bytes() + b"\n")
        with patch("stage3_calibration.generate_manifest_v1", side_effect=AssertionError("must not regenerate")):
            for path, exception in ((modified, ValueError), (self.root / "missing.json", FileNotFoundError)):
                with self.subTest(path=path), self.assertRaises(exception):
                    analysis.analyze_files(self.session_path, self.trials_path, manifest_path=path)
            analysis.analyze_files(self.session_path, self.trials_path)

    def test_bad_json_duplicate_keys_nonfinite_and_blank_lines_rejected(self):
        self.save()
        original = self.trials_path.read_bytes()
        for payload in (b'{"valid":true,"valid":false}\n', b'{"x":NaN}\n', b'{"x":Infinity}\n',
                        original + b"\n", b"{broken}\n"):
            with self.subTest(payload=payload[:50]):
                self.trials_path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    analysis.analyze_files(self.session_path, self.trials_path)
        self.trials_path.write_bytes(original)
        original_session = self.session_path.read_bytes()
        for payload in (original_session.replace(b"96.0", b"1e999"),
                        b'{"session_status":"COMPLETED","session_status":"ABORTED"}'):
            self.session_path.write_bytes(payload)
            with patch.object(analysis, "fit_offset_medians", side_effect=AssertionError("validate first")):
                with self.assertRaises(ValueError):
                    analysis.analyze_files(self.session_path, self.trials_path)

    def test_cli_explicit_paths_and_hash_seed_independence(self):
        self.save()
        results = []
        for seed in ("1", "9182"):
            report_path, profile_path = self.root / f"report-{seed}.json", self.root / f"profile-{seed}.json"
            command = [sys.executable, "-S", str(ROOT / "stage3_calibration_analysis.py"),
                       "--session", str(self.session_path), "--trials", str(self.trials_path),
                       "--report", str(report_path), "--profile", str(profile_path)]
            result = subprocess.run(command, cwd=ROOT, env={**os.environ, "PYTHONHASHSEED": seed},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            results.append((report_path.read_bytes(), profile_path.read_bytes()))
        self.assertEqual(results[0], results[1])
        collision = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(collision.returncode, 0)
        self.assertIn("already exists", collision.stderr)
        self.assertEqual(results[-1], (report_path.read_bytes(), profile_path.read_bytes()))


class NumericContractTests(unittest.TestCase):
    def test_even_median_is_exact_without_context_rounding(self):
        with localcontext(Context(prec=3)):
            self.assertEqual(analysis.median_ns([20, 1, 8, 3]), Decimal("5.5"))
            self.assertEqual(analysis.median_ns([1, 3, 9]), Decimal(3))
            self.assertEqual(analysis.median_ns([10**100, 10**100 + 1]), Decimal(str(10**100) + ".5"))

    def test_decimal_sqrt_ln_algorithm_and_precision(self):
        for dx, expected in ((0, 0), (1, 1), (3, 2), (7, 3)):
            self.assertEqual(analysis.distance_and_log2(dx, 0)[1], Decimal(expected))
        self.assertEqual(analysis.distance_and_log2(8, 6), analysis.distance_and_log2(10, 0))
        with localcontext(Context(prec=120)):
            d, x = analysis.distance_and_log2(29, 15)
            self.assertLess(abs(d - Decimal(1066).sqrt()), Decimal("1e-77"))
            self.assertLess(abs(x - reference_x(29, 15)), Decimal("1e-77"))

    def test_fit_matches_independent_median_formula_and_residuals(self):
        medians = {name: Decimal(100_000_000 + i * i * 10_000_000)
                   for i, (name, _, _) in enumerate(SCHEDULE["offsets"])}
        fit = analysis.fit_offset_medians(medians)
        with localcontext(Context(prec=120)):
            xs = [reference_x(dx, dy) for _, dx, dy in SCHEDULE["offsets"]]
            ys = [medians[name] / 1000 for name, _, _ in SCHEDULE["offsets"]]
            b = sum(x * (y - ys[0]) for x, y in zip(xs[1:], ys[1:])) / sum(x**2 for x in xs[1:])
            self.assertEqual(fit["c_us"], ys[0])
            self.assertLess(abs(fit["b_us"] - b), Decimal("1e-70"))
            residuals = [y - (ys[0] + b * x) for x, y in zip(xs, ys)]
            self.assertLess(abs(fit["residual_mae_us"] - sum(abs(r) for r in residuals) / 16), Decimal("1e-70"))
            self.assertLess(abs(fit["residual_rmse_us"] - (sum(r*r for r in residuals) / 16).sqrt()), Decimal("1e-70"))
            x_mean, y_mean = sum(xs) / 16, sum(ys) / 16
            b_hat = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / sum((x - x_mean)**2 for x in xs)
            self.assertLess(abs(fit["b_hat_us"] - b_hat), Decimal("1e-70"))
            self.assertLess(abs(fit["c_hat_us"] - (y_mean - b_hat * x_mean)), Decimal("1e-70"))

    def test_table_shape_positive_and_t00(self):
        table = analysis.build_timing_table(Decimal("12345.6"), Decimal("23456.7"))
        self.assertEqual(len(table), 30)
        self.assertTrue(all(len(row) == 16 for row in table))
        self.assertEqual(sum(len(row) for row in table), 480)
        self.assertTrue(all(type(v) is int and v > 0 for row in table for v in row))
        self.assertEqual(table[0][0], 12346)

    def test_half_even_rounding_boundaries(self):
        self.assertEqual(analysis.build_timing_table(Decimal("1000.5"), Decimal(0))[0][0], 1000)
        self.assertEqual(analysis.build_timing_table(Decimal("1001.5"), Decimal(0))[0][0], 1002)
        self.assertEqual(analysis.build_timing_table(Decimal(1000), Decimal("0.5"))[1][0], 1000)
        self.assertEqual(analysis.build_timing_table(Decimal(1001), Decimal("0.5"))[1][0], 1002)
        self.assertEqual(analysis.build_timing_table(Decimal(1000), Decimal("0.25"))[3][0], 1000)
        self.assertEqual(analysis.build_timing_table(Decimal(1001), Decimal("0.25"))[3][0], 1002)

    def test_table_matches_120_digit_reference_for_all_entries(self):
        c, b = Decimal("12345.6789"), Decimal("23456.78901")
        table = analysis.build_timing_table(c, b)
        with localcontext(Context(prec=120, rounding=ROUND_HALF_EVEN)):
            expected = [[int((c + b * reference_x(dx, dy)).to_integral_value()) for dy in range(16)] for dx in range(30)]
        self.assertEqual(table, expected)

    def test_monotonicity_by_physical_distance_including_equal_ticks(self):
        for slope in (Decimal("0"), Decimal("0.01"), Decimal("9876.543")):
            table = analysis.build_timing_table(Decimal("1000"), slope)
            cells = sorted((dx*dx + dy*dy, table[dx][dy]) for dx in range(30) for dy in range(16))
            self.assertTrue(all(a[1] <= b[1] for a, b in zip(cells, cells[1:])))
            self.assertEqual(table[8][6], table[10][0])

    def test_table_structural_validation_rejects_invalid_tables(self):
        table = analysis.build_timing_table(1000, 0)
        changes = (
            lambda t: t.pop(), lambda t: t[0].pop(),
            lambda t: t[0].__setitem__(0, 0), lambda t: t[0].__setitem__(0, True),
            lambda t: t[0].__setitem__(0, 1000.0), lambda t: t[0].__setitem__(0, 1001),
            lambda t: t[29].__setitem__(15, 999),
            lambda t: t[8].__setitem__(6, 1001),
        )
        for mutate in changes:
            with self.subTest(mutation=mutate):
                damaged = copy.deepcopy(table)
                mutate(damaged)
                with self.assertRaises(ValueError):
                    analysis.validate_timing_table(damaged, 1000)

    def test_invalid_parameters_and_rounded_zero_rejected(self):
        for c, b in ((0, 1), (-1, 1), (1, -1), (1.0, 1), (1, 1.0),
                     (Decimal("NaN"), 1), (1, Decimal("Infinity")), (Decimal("0.5"), 0)):
            with self.subTest(c=c, b=b), self.assertRaises(ValueError):
                analysis.build_timing_table(c, b)

    def test_canonical_dx_major_byte_encoding_and_hash_independent(self):
        table = [[dx * 100 + dy + 1 for dy in range(16)] for dx in range(30)]
        expected = b",".join(str(dx * 100 + dy + 1).encode("ascii")
                             for dx in range(30) for dy in range(16))
        encoded = analysis.canonical_timing_table_bytes(table)
        self.assertEqual(encoded, expected)
        self.assertTrue(encoded.startswith(b"1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,101,"))
        self.assertFalse(encoded.endswith(b","))
        self.assertNotIn(b" ", encoded)
        self.assertNotIn(b"\n", encoded)
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), hashlib.sha256(expected).hexdigest())

    def test_hostile_ambient_decimal_context_does_not_change_results(self):
        medians = {name: Decimal(100_000_000 + i * 10_000_000)
                   for i, (name, _, _) in enumerate(SCHEDULE["offsets"])}
        baseline_fit = analysis.fit_offset_medians(medians)
        baseline_table = analysis.build_timing_table(baseline_fit["c_us"], baseline_fit["b_us"])
        with localcontext(Context(prec=6, rounding=ROUND_DOWN)) as context:
            context.traps[Inexact] = True
            before = str(context)
            fit = analysis.fit_offset_medians(medians)
            self.assertEqual(fit, baseline_fit)
            self.assertEqual(analysis.build_timing_table(fit["c_us"], fit["b_us"]), baseline_table)
            self.assertEqual(str(getcontext()), before)
            with self.assertRaises(ValueError):
                analysis.build_timing_table(0, 1)
            self.assertEqual(str(getcontext()), before)

    def test_decimal_text_preserves_value_without_context_normalization(self):
        value = Decimal("123456789.123456789000")
        with localcontext(Context(prec=3)):
            self.assertEqual(analysis.decimal_text(value), "123456789.123456789")
            self.assertEqual(analysis.decimal_text(Decimal("-0.00")), "0")


class OutputAndImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="stage3-synthetic-outputs-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.report_path, self.profile_path = self.root / "report.json", self.root / "profile.json"

    def test_exclusive_outputs_and_canonical_json(self):
        report = {"z": Decimal("1.250"), "a": "synthetic"}
        profile = {"synthetic": True}
        analysis.write_outputs(report, profile, self.report_path, self.profile_path)
        self.assertEqual(self.report_path.read_bytes(), b'{"a":"synthetic","z":"1.25"}\n')
        self.assertEqual(self.profile_path.read_bytes(), b'{"synthetic":true}\n')

    def test_collision_on_either_output_never_modifies_existing_or_creates_other(self):
        for existing, other in ((self.report_path, self.profile_path), (self.profile_path, self.report_path)):
            with self.subTest(existing=existing):
                existing.write_bytes(b"preserve me")
                with self.assertRaises(FileExistsError):
                    analysis.write_outputs({}, {}, self.report_path, self.profile_path)
                self.assertEqual(existing.read_bytes(), b"preserve me")
                self.assertFalse(other.exists())
                existing.unlink()

    def test_same_output_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "must differ"):
            analysis.write_outputs({}, {}, self.report_path, self.report_path)
        self.assertFalse(self.report_path.exists())

    def test_second_reservation_failure_cleans_only_new_first_file(self):
        original = Path.open

        def race(path, mode="r", *args, **kwargs):
            if path == self.profile_path and mode == "xb":
                with original(path, "wb") as stream:
                    stream.write(b"other writer")
            return original(path, mode, *args, **kwargs)

        with patch.object(Path, "open", race), self.assertRaises(FileExistsError):
            analysis.write_outputs({}, {}, self.report_path, self.profile_path)
        self.assertFalse(self.report_path.exists())
        self.assertEqual(self.profile_path.read_bytes(), b"other writer")

    def test_missing_output_parent_cleans_new_reservation(self):
        with self.assertRaises(FileNotFoundError):
            analysis.write_outputs({}, {}, self.report_path, self.root / "missing/profile.json")
        self.assertFalse(self.report_path.exists())

    def test_module_import_has_no_collection_or_runtime_dependencies(self):
        script = r'''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(("PyQt", "core_engine", "solver", "simple_", "benchmark", "stage3_calibration_tool", "qt_bootstrap", "main", "sqlite")):
        raise AssertionError("Forbidden dependency: " + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import stage3_calibration_analysis
'''
        result = subprocess.run([sys.executable, "-S", "-c", script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_requires_explicit_input_and_output_paths(self):
        result = subprocess.run([sys.executable, "-S", str(ROOT / "stage3_calibration_analysis.py")],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        for name in ("--session", "--trials", "--report", "--profile"):
            self.assertIn(name, result.stderr)


if __name__ == "__main__":
    unittest.main()
