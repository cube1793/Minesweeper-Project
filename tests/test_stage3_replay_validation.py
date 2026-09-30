"""Offline V1 contract tests. All frames/videos are generated; no human evidence.

Optional image/video tests skip without requirements-replay-validation.txt.
The standard-library measurement/profile tests always run.
"""

import copy
from decimal import localcontext
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import stage3_replay_validation as v


HAS_CV = all(importlib.util.find_spec(name) for name in ("cv2", "numpy"))
HAS_AV = importlib.util.find_spec("av") is not None


def metadata(**updates):
    value = {"category": "STANDARD", "selected_rank": 15, "corpus_role": "TECHNICAL_PILOT",
             "displayed_time_seconds": "0.125", "displayed_final_click_count": 3}
    value.update(updates)
    return value


def final_metadata(**updates):
    value = metadata(corpus_role="FINAL", selected_rank=1,
                     capture_declaration=v.CAPTURE_DECLARATION.copy())
    value.update(updates)
    return value


def reading(count, total=3, mode="RUNNING"):
    return {"mode": mode, "count": count, "total": total,
            "text": f"{count}/{total}" if mode == "RUNNING" else str(count)}


def event(index, frame, x, y, count=None):
    return {"event_index": index, "event_frame": frame, "visible_click_count_after": count or index,
            "target_x": x, "target_y": y, "target_resolution_method": "EVENT_FRAME" if x is not None else "MANUAL_REVIEW",
            "target_frame_used": frame if x is not None else None,
            "action_type": "UNKNOWN", "action_type_confidence": "NOT_CLASSIFIED", "review_flags": []}


def observation(cell=None, status=None):
    return {"cell": list(cell) if cell is not None else None, "candidates": [],
            "status": status or ("UNIQUE" if cell is not None else "NOT_DETECTED")}


class FrozenProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = v.load_frozen_profile()

    def test_accepted_frozen_profile(self):
        self.assertEqual(self.profile["table_sha256"], v.TABLE_SHA256)
        self.assertEqual(v.file_sha256(v.PROFILE_PATH), v.PROFILE_SHA256)

    def test_wrong_whole_profile_hash_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_bytes(v.PROFILE_PATH.read_bytes() + b" ")
            with self.assertRaisesRegex(v.ValidationError, "whole-profile"):
                v.load_frozen_profile(path)

    def test_wrong_declared_table_hash_rejected(self):
        self.profile["table_sha256"] = "0" * 64
        with self.assertRaisesRegex(v.ValidationError, "timing-table"):
            v.verify_profile_structure(self.profile)

    def test_wrong_actual_table_hash_rejected(self):
        self.profile["timing_table_us"] = [[tick + 1 for tick in row] for row in self.profile["timing_table_us"]]
        with self.assertRaisesRegex(v.ValidationError, "timing-table"):
            v.verify_profile_structure(self.profile)

    def test_dimensions_and_model_rejected(self):
        for key, value in (("table_dimensions", [16, 30]), ("grid_width", 29), ("model_id", "wrong"),
                           ("timing_unit", "ms"), ("table_order", "dy_major"), ("schema_version", 2)):
            with self.subTest(key=key), self.assertRaises(v.ValidationError):
                v.verify_profile_structure({**self.profile, key: value})

    def test_invalid_table_shape(self):
        self.profile["timing_table_us"].pop()
        with self.assertRaisesRegex(v.ValidationError, "30x16"):
            v.verify_profile_structure(self.profile)

    def test_invalid_ticks(self):
        for tick in (True, 1.0, 0, -1, "126005"):
            profile = copy.deepcopy(self.profile)
            profile["timing_table_us"][0][0] = tick
            with self.subTest(tick=tick), self.assertRaisesRegex(v.ValidationError, "tick"):
                v.verify_profile_structure(profile)

    def test_equal_distance_invariant(self):
        self.profile["timing_table_us"][0][1] += 1
        with self.assertRaisesRegex(v.ValidationError, "Equal distances"):
            v.verify_profile_structure(self.profile)

    def test_monotonic_invariant(self):
        self.profile["timing_table_us"][0][0] = 999999
        with self.assertRaisesRegex(v.ValidationError, "decreases"):
            v.verify_profile_structure(self.profile)

    def test_canonical_profile_and_duplicate_keys(self):
        self.assertEqual(v.canonical_bytes(self.profile), v.PROFILE_PATH.read_bytes())
        with self.assertRaisesRegex(v.ValidationError, "Duplicate"):
            json.loads('{"a":1,"a":2}', object_pairs_hook=v.unique_object)

    def test_profile_verified_before_video_open(self):
        with patch.object(v, "load_frozen_profile", side_effect=v.ValidationError("Wrong profile")):
            with self.assertRaisesRegex(v.ValidationError, "Wrong profile"):
                v.analyze_video("VIDEO_MUST_NOT_EXIST.mp4", metadata())

    def test_coefficients_are_never_consumed(self):
        self.profile["fitted_c_us"] = "DO NOT PARSE"
        self.profile["fitted_k_us"] = None
        table = v.verify_profile_structure(self.profile)
        transitions = v.calculate_transitions([event(1, 1, 0, 0), event(2, 2, 3, 4)], table)
        self.assertEqual(transitions[0]["predicted_us"], 294552)


class MetadataAndTimingTests(unittest.TestCase):
    def test_expected_video_metadata(self):
        self.assertEqual(v.validate_video_metadata(1920, 1080, Fraction(120)), [])

    def test_incompatible_video_metadata(self):
        for width, height, fps in ((1920, 1080, Fraction(60)), (1920, 1080, Fraction(120000, 1001)),
                                   (960, 540, Fraction(120)), (1920, 1080, None)):
            with self.subTest(fps=fps):
                self.assertTrue(v.validate_video_metadata(width, height, fps))

    def test_displayed_decimal_conversion_exact(self):
        with localcontext() as ctx:
            ctx.prec = 2
            self.assertEqual(v.validate_metadata(metadata(displayed_time_seconds="36.101"))[0], 36101000)

    def test_displayed_integer_ms(self):
        data = metadata()
        del data["displayed_time_seconds"]
        data["displayed_time_ms"] = 42023
        self.assertEqual(v.validate_metadata(data)[0], 42023000)

    def test_float_ambiguous_or_nonpositive_time_rejected(self):
        for value in (36.101, "nan", "0", "-1", "1.0000001"):
            with self.subTest(value=value), self.assertRaises(v.ValidationError):
                v.validate_metadata(metadata(displayed_time_seconds=value))
        with self.assertRaises(v.ValidationError):
            v.validate_metadata(metadata(displayed_time_ms=1))

    def test_final_rank_policy_and_pilot_exclusion(self):
        for category in ("STANDARD", "NO_FLAG"):
            with self.subTest(category=category), self.assertRaises(v.ValidationError):
                v.validate_metadata(metadata(category=category, corpus_role="FINAL"))
            with self.subTest(category=category, replacement=True), self.assertRaises(v.ValidationError):
                v.validate_metadata(final_metadata(category=category, selected_rank=15, replacement_of=1,
                                                   replacement_reason="Unavailable"))
            self.assertEqual(v.validate_metadata(metadata(category=category))[2], [])

    def test_valid_standard_replacement_outside_original_set(self):
        self.assertEqual(v.validate_metadata(final_metadata(selected_rank=11, replacement_of=10,
                                                            replacement_reason="Original replay unavailable"))[2], [])

    def test_valid_no_flag_replacement_outside_original_set(self):
        self.assertEqual(v.validate_metadata(final_metadata(category="NO_FLAG", selected_rank=6,
                                                            replacement_of=5, replacement_reason="Corrupt video"))[2], [])

    def test_replacement_rank_context_checks_are_deferred(self):
        # Both in-set and distant out-of-set replacements are structurally valid;
        # this validator cannot know which nearer ranks are already used/unusable.
        for rank in (9, 31, 100):
            with self.subTest(rank=rank):
                self.assertEqual(v.validate_metadata(final_metadata(selected_rank=rank, replacement_of=10,
                                                                    replacement_reason="Unreconstructable"))[2], [])

    def test_replacement_of_wrong_type_rejected(self):
        for target in ("10", 10.0, True, False, [], {}):
            with self.subTest(target=target), self.assertRaisesRegex(v.ValidationError, "replacement_of"):
                v.validate_metadata(final_metadata(selected_rank=11, replacement_of=target,
                                                   replacement_reason="Unavailable"))

    def test_replacement_of_must_be_original_target_in_same_category(self):
        for category, target in (("STANDARD", 11), ("STANDARD", 0), ("NO_FLAG", 10), ("NO_FLAG", 25)):
            with self.subTest(category=category, target=target), self.assertRaisesRegex(v.ValidationError, "replacement_of"):
                v.validate_metadata(final_metadata(category=category, selected_rank=31,
                                                   replacement_of=target, replacement_reason="Unavailable"))

    def test_replacement_cannot_use_same_selected_rank(self):
        with self.assertRaisesRegex(v.ValidationError, "must differ"):
            v.validate_metadata(final_metadata(selected_rank=10, replacement_of=10, replacement_reason="Unavailable"))

    def test_one_sided_replacement_metadata_rejected(self):
        for fields in ({"replacement_of": 10}, {"replacement_reason": "Unavailable"},
                       {"replacement_of": 10, "replacement_reason": None},
                       {"replacement_of": None, "replacement_reason": "Unavailable"}):
            with self.subTest(fields=fields), self.assertRaises(v.ValidationError):
                v.validate_metadata(final_metadata(**fields))

    def test_replacement_reason_must_be_nonempty_string(self):
        for reason in ("", " \t\n", 1, True, [], {}):
            with self.subTest(reason=reason), self.assertRaisesRegex(v.ValidationError, "replacement_reason"):
                v.validate_metadata(final_metadata(selected_rank=11, replacement_of=10, replacement_reason=reason))

    def test_replacement_selected_rank_must_be_positive_integer(self):
        for rank in (0, -1, True, "11", 11.0):
            with self.subTest(rank=rank), self.assertRaisesRegex(v.ValidationError, "selected_rank"):
                v.validate_metadata(final_metadata(selected_rank=rank, replacement_of=10, replacement_reason="Unavailable"))

    def test_nonreplacement_rank_must_be_original_target(self):
        for category, rank in (("STANDARD", 11), ("NO_FLAG", 6)):
            for fields in ({}, {"replacement_of": None, "replacement_reason": None}):
                with self.subTest(category=category, fields=fields), self.assertRaisesRegex(v.ValidationError, "original target set"):
                    v.validate_metadata(final_metadata(category=category, selected_rank=rank, **fields))

    def test_nonreplacement_accepts_absent_or_null_replacement_fields(self):
        for fields in ({}, {"replacement_of": None}, {"replacement_reason": None},
                       {"replacement_of": None, "replacement_reason": None}):
            with self.subTest(fields=fields):
                self.assertEqual(v.validate_metadata(final_metadata(**fields))[2], [])

    def test_final_capture_declaration_required(self):
        self.assertIn("CAPTURE_DECLARATION_REQUIRED", v.validate_metadata(metadata(corpus_role="FINAL", selected_rank=1))[2])
        self.assertEqual(v.validate_metadata(metadata(corpus_role="FINAL", selected_rank=30,
                                                     capture_declaration=v.CAPTURE_DECLARATION))[2], [])

    def test_final_requires_both_obs_stats_assertions(self):
        for key in ("obs_stats_frames_missed_due_to_rendering_lag_zero",
                    "obs_stats_skipped_frames_due_to_encoding_lag_zero"):
            self.assertIs(v.CAPTURE_DECLARATION[key], True)
            missing = v.CAPTURE_DECLARATION.copy()
            del missing[key]
            variants = [missing] + [{**v.CAPTURE_DECLARATION, key: value}
                                    for value in (False, None, 1, 1.0, "true")]
            for declaration in variants:
                with self.subTest(key=key, value=declaration.get(key)):
                    self.assertEqual(v.validate_metadata(final_metadata(capture_declaration=declaration))[2],
                                     ["CAPTURE_DECLARATION_INCOMPATIBLE"])

    def test_incompatible_declaration_and_replacement(self):
        self.assertTrue(v.validate_metadata(metadata(capture_declaration={}))[2])
        with self.assertRaises(v.ValidationError):
            v.validate_metadata(metadata(replacement_of="rank1"))

    def test_exact_rational_120fps_math(self):
        point, low, high = v.frame_interval(1)
        self.assertEqual((point, low, high), (Fraction(25000, 3), 0, Fraction(50000, 3)))
        self.assertEqual(v.frame_interval(4330)[0], Fraction(108250000, 3))

    def test_zero_delta_low_is_zero(self):
        self.assertEqual(v.frame_interval(0), (0, 0, Fraction(25000, 3)))

    def test_model_below_inclusive_boundary(self):
        self.assertEqual(v.comparison_class(100, Fraction(100), Fraction(102)), "MODEL_BELOW")

    def test_frame_ambiguous_inclusive_high(self):
        for tick in (101, 102):
            self.assertEqual(v.comparison_class(tick, Fraction(100), Fraction(102)), "FRAME_AMBIGUOUS")

    def test_model_above(self):
        self.assertEqual(v.comparison_class(103, Fraction(100), Fraction(102)), "MODEL_ABOVE")

    def test_frozen_cost_in_all_three_frame_classes(self):
        table = v.load_frozen_profile()["timing_table_us"]
        for delta, expected in ((17, "MODEL_BELOW"), (15, "FRAME_AMBIGUOUS"), (13, "MODEL_ABOVE")):
            with self.subTest(delta=delta):
                actual = v.calculate_transitions([event(1, 0, 0, 0), event(2, delta, 0, 0)], table)
                self.assertEqual(actual[0]["comparison_class"], expected)

    def test_first_action_excluded_and_same_cell(self):
        table = v.load_frozen_profile()["timing_table_us"]
        self.assertEqual(v.calculate_transitions([event(1, 3, 29, 15)], table), [])
        transitions = v.calculate_transitions([event(1, 3, 29, 15), event(2, 5, 29, 15)], table)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0]["predicted_us"], 126005)

    def test_abs_offsets_and_table_orientation(self):
        table = [[1000 * dx + dy for dy in range(16)] for dx in range(30)]
        transitions = v.calculate_transitions([event(1, 1, 29, 15), event(2, 3, 0, 0)], table)
        self.assertEqual((transitions[0]["dx"], transitions[0]["dy"], transitions[0]["predicted_us"]), (29, 15, 29015))

    def test_unresolved_target_does_not_bridge(self):
        transitions = v.calculate_transitions([event(1, 1, 0, 0), event(2, 2, None, None), event(3, 3, 1, 1)],
                                              v.load_frozen_profile()["timing_table_us"])
        self.assertEqual(transitions, [])

    def test_skipped_count_does_not_form_authoritative_transition(self):
        transitions = v.calculate_transitions([event(1, 1, 0, 0), event(2, 2, 1, 1, count=3)],
                                              v.load_frozen_profile()["timing_table_us"])
        self.assertEqual(transitions, [])

    def test_deterministic_rational_json(self):
        value = {"b": v.rational(Fraction(6, 8)), "a": 2}
        self.assertEqual(v.canonical_bytes(value), b'{"a":2,"b":{"denominator":4,"numerator":3}}\n')


class EventAndCursorTests(unittest.TestCase):
    def test_increment_and_no_increment(self):
        d = v.EventDetector()
        for i, c in enumerate((0, 1, 1, 2, 2, 3)):
            d.feed(i, reading(c))
        self.assertEqual([e["event_frame"] for e in d.events], [1, 3, 5])
        self.assertEqual([e["event_index"] for e in d.events], [1, 2, 3])
        self.assertEqual(d.flags, [])

    def test_skipped_count_preserved_no_synthesis(self):
        d = v.EventDetector()
        for i, c in enumerate((0, 1, 3)):
            d.feed(i, reading(c))
        self.assertEqual([e["visible_click_count_after"] for e in d.events], [1, 3])
        self.assertIn("SKIPPED_VISIBLE_COUNT", d.flags)

    def test_initial_summary_ignored_final_summary_increment_preserved(self):
        d = v.EventDetector()
        for i, r in enumerate((reading(3, mode="SUMMARY"), reading(1), reading(2), reading(3, mode="SUMMARY"), reading(3, mode="SUMMARY"))):
            d.feed(i, r)
        self.assertEqual([e["event_frame"] for e in d.events], [1, 2, 3])
        self.assertEqual(d.flags, [])

    def test_end_visual_changes_without_increment_are_not_events(self):
        d = v.EventDetector()
        for i, r in enumerate((reading(0), reading(1), reading(2), reading(3), reading(3, mode="SUMMARY"))):
            d.feed(i, r)
        self.assertEqual(len(d.events), 3)

    def test_unreadable_boundary_requires_review(self):
        d = v.EventDetector()
        d.feed(0, reading(0))
        d.feed(1, {"mode": "UNREADABLE"})
        d.feed(2, reading(1))
        self.assertIn("EVENT_BOUNDARY_UNVERIFIED", d.events[0]["review_flags"])

    def test_count_decrease_requires_review(self):
        d = v.EventDetector()
        for i, c in enumerate((0, 1, 2, 1)):
            d.feed(i, reading(c))
        self.assertIn("COUNTER_DECREASE_OR_SEEK", d.flags)

    def test_all_board_corners_and_half_open_edges(self):
        for px, py, cell in ((582, 332, (0, 0)), (1541, 332, (29, 0)),
                             (582, 843, (0, 15)), (1541, 843, (29, 15)), (614, 364, (1, 1))):
            with self.subTest(cell=cell):
                self.assertEqual(v.pixel_to_cell(px, py), cell)
        for x, y in ((581, 332), (582, 331), (1542, 500), (800, 844)):
            self.assertIsNone(v.pixel_to_cell(x, y))

    def test_exact_frame_cursor_primary(self):
        e = event(1, 10, None, None)
        v.resolve_target(e, {10: observation((2, 3)), 9: observation((1, 1))})
        self.assertEqual((e["target_x"], e["target_y"], e["target_frame_used"]), (2, 3, 10))
        self.assertEqual(e["target_resolution_method"], "EVENT_FRAME")

    def test_fallback_at_both_four_frame_boundaries(self):
        for sign in (-1, 1):
            e = event(1, 10, None, None)
            # Nearest detectable frame 3, with a stable witness at the limit 4.
            v.resolve_target(e, {10: observation(), 10 + 3*sign: observation((2, 3)), 10 + 4*sign: observation((2, 3))})
            self.assertEqual(e["target_frame_used"], 10 + 3*sign)
            self.assertEqual(e["target_resolution_method"], "NEAREST_STABLE_WITHIN_4")

    def test_beyond_four_frames_never_extrapolated(self):
        e = event(1, 10, None, None)
        v.resolve_target(e, {15: observation((1, 1)), 16: observation((1, 1))})
        self.assertIsNone(e["target_x"])

    def test_ambiguous_equidistant_fallback_unresolved(self):
        e = event(1, 10, None, None)
        v.resolve_target(e, {8: observation((1, 1)), 9: observation((1, 1)),
                             11: observation((2, 2)), 12: observation((2, 2))})
        self.assertIsNone(e["target_x"])
        self.assertIn("CONFLICTING_NEAREST_CURSOR_CELLS", e["review_flags"])

    def test_unstable_single_cursor_unresolved(self):
        e = event(1, 10, None, None)
        v.resolve_target(e, {9: observation((1, 1))})
        self.assertIsNone(e["target_x"])

    def test_ambiguous_exact_frame_cannot_be_overridden(self):
        e = event(1, 10, None, None)
        v.resolve_target(e, {10: observation(status="AMBIGUOUS_OR_OUTSIDE"), 9: observation((1, 1)), 8: observation((1, 1))})
        self.assertIsNone(e["target_x"])

    def test_completeness_and_authoritative_total(self):
        table = v.load_frozen_profile()["timing_table_us"]
        events = [event(1, 1, 0, 0), event(2, 17, 0, 1)]
        result = v.summarize(events, 2, 200000, table, [])
        self.assertEqual(result["replay_status"], "RECONSTRUCTED")
        self.assertEqual(result["modeled_physical_time_us"], 126005)
        self.assertEqual(result["completeness_difference"], 0)
        result = v.summarize(events, 3, 200000, table, [])
        self.assertEqual(result["replay_status"], "REVIEW_REQUIRED")
        self.assertEqual(result["completeness_difference"], -1)
        self.assertIsNone(result["modeled_physical_time_us"])
        self.assertIsNone(result["physical_to_human_ratio"])

    def test_unresolved_authoritative_total_is_null(self):
        result = v.summarize([event(1, 0, None, None), event(2, 1, 1, 1)], 2, 100000,
                             v.load_frozen_profile()["timing_table_us"], [])
        self.assertEqual(result["unresolved_target_count"], 1)
        self.assertEqual(result["transition_count"], 0)
        self.assertIsNone(result["modeled_physical_time_us"])


def synthetic_frame(counter_text="0/3", cell=None, second_cell=None, vertical_shift=0, glyph_gap=3):
    """Artificial palette/grid/glyphs only; generated without any video evidence."""
    import cv2
    import numpy as np
    image = np.full((1080, 1920, 3), 30, np.uint8)
    image[327:851, 577:1549] = 128
    image[845:851, 582:1549] = 255
    image[332:851, 1543:1549] = 255
    for y in range(16):
        for x in range(30):
            px, py = 582 + 32*x, 332 + 32*y
            image[py:py+32, px:px+32] = 128
            image[py+3:py+30, px+3:px+30] = 197
    x = 1673
    for char in counter_text:
        glyph = v.GLYPHS[char]
        for row, pixels in enumerate(glyph):
            for col, pixel in enumerate(pixels):
                if pixel == "#":
                    image[387 + vertical_shift + row, x + col] = 190
        x += len(glyph[0]) + glyph_gap
    for target in (cell, second_cell):
        if target is not None:
            cx, cy = 598 + 32*target[0], 348 + 32*target[1]
            cv2.circle(image, (cx, cy), 15, (224, 224, 224), -1, cv2.LINE_AA)
            cv2.circle(image, (cx, cy), 15, (115, 115, 115), 1, cv2.LINE_AA)
    return image


@unittest.skipUnless(HAS_CV, "optional replay-validation dependencies unavailable")
class FixedImageTests(unittest.TestCase):
    def setUp(self):
        self.ui = v.FixedUI()

    def test_every_numeral_and_summary_operators(self):
        for digit in range(10):
            with self.subTest(digit=digit):
                result = self.ui.counter(synthetic_frame(f"{digit}/19"))
                self.assertEqual((result["mode"], result.get("count")), ("RUNNING", digit))
        result = self.ui.counter(synthetic_frame("12+3"))
        self.assertEqual((result["mode"], result["count"]), ("SUMMARY", 15))

    def test_one_pixel_vertical_glyph_shift(self):
        self.assertEqual(self.ui.counter(synthetic_frame("172", vertical_shift=1))["count"], 172)

    def test_touching_glyphs_are_segmented_by_shape(self):
        for text in ("34/139", "40/172", "44/139", "134/172"):
            with self.subTest(text=text):
                result = self.ui.counter(synthetic_frame(text, glyph_gap=0))
                self.assertEqual(result.get("text"), text)

    def test_four_pixel_wide_one(self):
        import cv2
        image = synthetic_frame("1/3")
        digit = image[387:399, 1673:1678].copy()
        image[387:399, 1673:1678] = 30
        image[387:399, 1673:1677] = cv2.resize(digit, (4, 12), interpolation=cv2.INTER_NEAREST)
        self.assertEqual(self.ui.counter(image).get("count"), 1)

    def test_empty_counter_unreadable(self):
        self.assertEqual(self.ui.counter(synthetic_frame(""))["mode"], "UNREADABLE")

    def test_corrupt_glyph_unreadable(self):
        image = synthetic_frame("1/3")
        image[387:399, 1673:1684] = 190
        self.assertEqual(self.ui.counter(image)["mode"], "UNREADABLE")

    def test_exact_layout_accepted(self):
        self.assertTrue(self.ui.layout(synthetic_frame()))

    def test_mixed_opened_covered_white_boundary(self):
        image = synthetic_frame()
        image[340:836, 838:841] = 255
        self.assertTrue(self.ui.layout(image))

    def test_shifted_layout_rejected(self):
        import numpy as np
        self.assertFalse(self.ui.layout(np.roll(synthetic_frame(), 8, axis=1)))

    def test_missing_board_rejected(self):
        image = synthetic_frame()
        image[327:851, 577:1549] = 0
        self.assertFalse(self.ui.layout(image))

    def test_circle_at_all_corners(self):
        for cell in ((0, 0), (29, 0), (0, 15), (29, 15)):
            with self.subTest(cell=cell):
                self.assertEqual(self.ui.cursor(synthetic_frame(cell=cell))["cell"], list(cell))

    def test_two_cursor_rings_ambiguous(self):
        self.assertIsNone(self.ui.cursor(synthetic_frame(cell=(3, 3), second_cell=(8, 8)))["cell"])

    def test_outside_cursor_not_clamped(self):
        self.assertIsNone(self.ui.cursor(synthetic_frame(cell=(-1, 5)))["cell"])

    def test_counter_events_without_board_effect(self):
        detector = v.EventDetector()
        for index, text in enumerate(("0/3", "1/3", "1/3", "2/3", "3")):
            detector.feed(index, self.ui.counter(synthetic_frame(text)))
        self.assertEqual([e["event_frame"] for e in detector.events], [1, 3, 4])


def make_video(path, *, fps=120, pts_gap=False, layout_shift=False):
    import av
    import numpy as np
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = 1920, 1080, "yuv444p"
        stream.codec_context.time_base = Fraction(1, fps * 2)
        stream.options = {"crf": "0", "preset": "ultrafast"}
        for index in range(20):
            text = "3" if index < 2 or index >= 17 else "1/3" if index < 9 else "2/3"
            cell = (0, 0) if 2 <= index < 7 else (2, 2) if 7 <= index < 14 else (4, 2) if 14 <= index < 17 else None
            image = synthetic_frame(text, cell=cell)
            if layout_shift:
                image = np.roll(image, 8, axis=1)
            frame = av.VideoFrame.from_ndarray(image, format="bgr24")
            # One late frame, then recovery: average FPS remains 120, but the
            # two affected frame intervals are 3/240 and 1/240 seconds.
            frame.pts = index * 2 + (1 if pts_gap and index == 10 else 0)
            frame.time_base = Fraction(1, fps * 2)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


@unittest.skipUnless(HAS_CV and HAS_AV, "optional replay-validation dependencies unavailable")
class SyntheticVideoTests(unittest.TestCase):
    def test_full_pipeline_and_identical_bytes_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.mp4"
            make_video(path)
            first = v.analyze_video(path, metadata())
            second = v.analyze_video(path, metadata())
        self.assertEqual(first["replay_status"], "RECONSTRUCTED", first["review_flags"])
        self.assertIsNone(first["capture_declaration"])
        self.assertEqual(first["capture_declaration_status"], "NOT_SUPPLIED")
        self.assertEqual(first["reconstructed_event_count"], 3)
        self.assertEqual(first["first_event_frame"], 2)
        self.assertEqual(first["last_event_frame"], 17)
        self.assertEqual(first["fallback_cursor_resolution_count"], 1)
        self.assertEqual(first["unresolved_target_count"], 0)
        self.assertEqual(first["modeled_physical_time_us"], 220689 + 180604)
        self.assertEqual(first["displayed_human_time_us"], 125000)
        self.assertEqual(first["video_span_us"], {"numerator": 125000, "denominator": 1})
        self.assertEqual(v.canonical_bytes(first), v.canonical_bytes(second))

    def test_valid_final_replacements_remain_authoritative(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.mp4"
            make_video(path)
            for category, rank, target in (("STANDARD", 11, 10), ("NO_FLAG", 6, 5)):
                with self.subTest(category=category):
                    result = v.analyze_video(path, final_metadata(category=category, selected_rank=rank,
                                                                  replacement_of=target, replacement_reason="Unavailable"))
                    self.assertEqual(result["replay_status"], "RECONSTRUCTED", result["review_flags"])
                    self.assertEqual(result["modeled_physical_time_us"], 401293)
                    self.assertEqual(result["replacement_of"], target)
                    self.assertIs(type(result["replacement_of"]), int)
                    self.assertEqual(result["selected_rank"], rank)
                    self.assertEqual(result["capture_declaration_status"], "SUPPLIED_COMPATIBLE")

    def test_final_capture_omissions_or_mismatch_keep_cfr_but_null_authoritative_result(self):
        render_key = "obs_stats_frames_missed_due_to_rendering_lag_zero"
        encode_key = "obs_stats_skipped_frames_due_to_encoding_lag_zero"
        legacy = {key: value for key, value in v.CAPTURE_DECLARATION.items()
                  if key not in (render_key, encode_key)}
        declarations = [None, legacy, {**v.CAPTURE_DECLARATION, render_key: False},
                        {**v.CAPTURE_DECLARATION, encode_key: False},
                        {**v.CAPTURE_DECLARATION, render_key: 1}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.mp4"
            make_video(path)
            for declaration in declarations:
                with self.subTest(declaration=declaration):
                    result = v.analyze_video(path, final_metadata(capture_declaration=declaration))
                    self.assertEqual(result["replay_status"], "REVIEW_REQUIRED")
                    self.assertEqual(result["video"]["cfr_compatibility_status"], "COMPATIBLE")
                    self.assertEqual(result["capture_declaration_status"],
                                     "NOT_SUPPLIED" if declaration is None else "SUPPLIED_INCOMPATIBLE")
                    self.assertIn("CAPTURE_DECLARATION_REQUIRED" if declaration is None else
                                  "CAPTURE_DECLARATION_INCOMPATIBLE", result["review_flags"])
                    self.assertIsNone(result["modeled_physical_time_us"])
                    self.assertIsNone(result["physical_to_human_ratio"])

    def test_variable_pts_rejected_even_with_120fps_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vfr.mp4"
            make_video(path, pts_gap=True)
            result = v.analyze_video(path, final_metadata())
        self.assertEqual(result["replay_status"], "INCOMPATIBLE_INPUT")
        self.assertEqual(result["capture_declaration_status"], "SUPPLIED_COMPATIBLE")
        self.assertEqual(result["video"]["fps"], {"numerator": 120, "denominator": 1})
        self.assertEqual(result["video"]["bad_pts_frames"], [10, 11])
        self.assertIn("INCOMPATIBLE_NON_CFR_OR_MISSING_PTS", result["review_flags"])
        self.assertIsNone(result["modeled_physical_time_us"])

    def test_wrong_fps_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "60fps.mp4"
            make_video(path, fps=60)
            result = v.analyze_video(path, metadata())
        self.assertEqual(result["replay_status"], "INCOMPATIBLE_INPUT")

    def test_wrong_layout_review_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shifted.mp4"
            make_video(path, layout_shift=True)
            result = v.analyze_video(path, metadata())
        self.assertEqual(result["replay_status"], "REVIEW_REQUIRED")
        self.assertIn("LAYOUT_REVIEW_REQUIRED", result["review_flags"])
        self.assertIsNone(result["modeled_physical_time_us"])

    def test_changed_evidence_requires_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.mp4"
            make_video(path)
            with patch.object(v, "file_sha256", side_effect=["a" * 64, "b" * 64]):
                result = v.analyze_video(path, metadata())
        self.assertIn("SOURCE_VIDEO_CHANGED_DURING_ANALYSIS", result["review_flags"])
        self.assertEqual(result["replay_status"], "REVIEW_REQUIRED")
        self.assertIsNone(result["modeled_physical_time_us"])

    def test_cli_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.json"
            output.write_bytes(b"existing evidence")
            code = v.main(["--video", "missing.mp4", "--metadata", "missing.json", "--output", str(output)])
            self.assertEqual(code, 2)
            self.assertEqual(output.read_bytes(), b"existing evidence")


if __name__ == "__main__":
    unittest.main()
