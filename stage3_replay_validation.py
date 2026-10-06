"""REPLAY_VALIDATION_V1_1: offline, fixed-layout Minesweeper.Online video validation.

Usage (outputs should stay under the already ignored results/ directory)::

    python stage3_replay_validation.py --video local.mp4 --metadata local.json \
        --output results/stage3_replay_validation/local.json

Install requirements-replay-validation.txt separately from the game requirements.
This module has no game, solver, replay, benchmark, or calibration imports.

Metadata JSON requires category (STANDARD/NO_FLAG), selected_rank, corpus_role
(TECHNICAL_PILOT/FINAL), displayed_time_seconds (decimal STRING) or
displayed_time_ms (INTEGER), and displayed_final_click_count. Optional fields:
player, recorded_date, replacement_of, replacement_reason, capture_declaration.
Original FINAL target ranks: STANDARD 1..10/21..30; NO_FLAG 1..5/26..30.
A replacement supplies replacement_of as an INTEGER original target rank in
the same category, a nonempty replacement_reason, and a different positive
selected_rank, which may be outside the original set. Rank 15 remains pilot
only. Nearest-unused selection (ties to lower rank) and corpus-wide uniqueness
are checked at the later corpus gate, not by this single-video validator.
No download, selection, recording, fitting, aggregation, or performance pass gate.

Frozen capture assumptions: full-screen 1920x1080, CFR 120/1 fps, 1x replay,
fixed window/zoom, board (582,332), 30x16 cells of 32 px. Korean sidebar click
counter occupies (1672,385)..(1825,402). Both running `n / total` and completed
`left+right` (or `total`) glyph states are read. The final summary is an event
only when its measured total increments the running counter. Initial completed
summaries are pre-playback evidence, never events. Screen refresh, OBS settings,
and absence of transport manipulation cannot be proved from pixels; the capture
operator must supply capture_declaration for FINAL inputs, including session
OBS Stats assertions of zero frames missed due to rendering lag and zero frames
skipped due to encoding lag. Exact CFR PTS cannot prove every source frame was
captured: OBS can duplicate frames while maintaining CFR. PTS is therefore an
independent timing-integrity check, alongside board layout and counter continuity.
V1.1 keeps whole-file PTS diagnostics but permits exactly one narrow exception:
a single long non-CFR interval entering the final decoded frame, only when that
frame is strictly later than the last event's +/-4-frame cursor search guard.
Missing PTS, short/backward final intervals, multiple anomalies, or any anomaly
at/before that guard remain incompatible.

Numeric JSON contract: integer microseconds for table costs and supplied H;
every rational quantity (including frame durations and P/H) is a reduced object
{numerator: integer, denominator: positive integer}. No rounding, binary-float
timing, current timestamps, absolute paths, or nondeterministic run identifiers.
Canonical ASCII JSON: sorted keys, compact separators, one terminal LF.
Frame indices are zero-based; event indices are one-based. Completeness difference
is reconstructed minus displayed. Unresolved/noncontiguous event transitions are
omitted; their known subtotal is diagnostic. Authoritative P and P/H are null
unless reconstruction, layout, metadata and timing integrity are complete/compatible.
The accepted terminal-tail exception applies only to post-analysis tail timing:
it does not relax any event/cursor/counter requirement and never changes event timing.

Cursor: a unique 32 px replay ring at the event frame is primary. Only +/-4
frames are searched on failure, nearest first; fallback requires a same-cell
consecutive-frame witness and no conflicting nearest candidate. Full diagnostics
are retained. No board-effect timestamps, interpolation, or inferred game logic.
Action type remains UNKNOWN/NOT_CLASSIFIED, because V1.1 uses one common table.

Detector constants describe this UI's pixels, never performance thresholds.
Digits are small abstract font masks, not human replay images. Recognition uses
Otsu foreground separation and unique, bounded shape matching;
uncertain reads stay unreadable. Hough ring parameters derive from its 32 px
diameter; edge/vote constants and limitations are exposed below. The +/-1 frame
envelope is capture quantization ONLY, not statistical uncertainty or latency.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys


PROTOCOL_VERSION = "REPLAY_VALIDATION_V1_1"
PROFILE_PATH = Path(__file__).resolve().parent / "calibration/stage3_physical_profile_v1.json"
PROFILE_SHA256 = "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b"
TABLE_SHA256 = "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b"
MODEL_ID = "overlap_floor_log2_distance_v1"
FPS = Fraction(120, 1)
CURSOR_SEARCH_RADIUS = 4
BOARD_X, BOARD_Y, CELL, COLS, ROWS = 582, 332, 32, 30, 16
COUNTER_ROI = (1672, 385, 1825, 402)
ORIGINAL_TARGET_RANKS = {
    "STANDARD": frozenset(range(1, 11)) | frozenset(range(21, 31)),
    "NO_FLAG": frozenset(range(1, 6)) | frozenset(range(26, 31)),
}
CAPTURE_DECLARATION = {
    "display_width": 1920, "display_height": 1080, "display_refresh_hz": 120,
    "obs_output_width": 1920, "obs_output_height": 1080,
    "replay_speed": "1", "window_position_fixed": True, "browser_zoom_fixed": True,
    "site_cell_size_px": 32, "full_screen_no_crop": True,
    "no_pause_seek_speed_change_during_playback": True,
    "obs_stats_frames_missed_due_to_rendering_lag_zero": True,
    "obs_stats_skipped_frames_due_to_encoding_lag_zero": True,
}


class ValidationError(ValueError):
    """Input rejected before authoritative calculation."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def rational(value):
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique_object)


def file_sha256(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verify_profile_structure(profile):
    """Local structural check; deliberately never reads/recomputes fitted c or k."""
    require(profile.get("model_id") == MODEL_ID, "Wrong model_id")
    require(profile.get("schema_version") == 1 and profile.get("physical_profile_version") == 1,
            "Wrong profile version")
    require(profile.get("table_dimensions") == [30, 16] and
            profile.get("grid_width") == 30 and profile.get("grid_height") == 16,
            "Wrong profile dimensions")
    require(profile.get("timing_unit") == "us" and profile.get("timing_tick_unit") == "1_us" and
            profile.get("table_order") == "dx_major_dy_minor", "Wrong table units/order")
    table = profile.get("timing_table_us")
    require(isinstance(table, list) and len(table) == 30 and
            all(isinstance(row, list) and len(row) == 16 for row in table), "Table must be 30x16")
    require(all(type(t) is int and t > 0 for row in table for t in row), "Invalid table tick")
    by_distance = {}
    for dx, row in enumerate(table):
        for dy, tick in enumerate(row):
            squared = dx * dx + dy * dy
            require(squared not in by_distance or by_distance[squared] == tick,
                    "Equal distances have unequal table costs")
            by_distance[squared] = tick
    ticks = [by_distance[d] for d in sorted(by_distance)]
    require(all(a <= b for a, b in zip(ticks, ticks[1:])), "Table decreases with distance")
    encoded = ",".join(str(t) for row in table for t in row).encode("ascii")
    require(profile.get("table_sha256") == TABLE_SHA256 and
            hashlib.sha256(encoded).hexdigest() == TABLE_SHA256, "Wrong timing-table SHA-256")
    return table


def load_frozen_profile(path=PROFILE_PATH):
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == PROFILE_SHA256, "Wrong whole-profile SHA-256")
    profile = json.loads(raw, object_pairs_hook=unique_object)
    require(canonical_bytes(profile) == raw, "Profile is not canonical JSON")
    verify_profile_structure(profile)
    return profile


def capture_declaration_compatible(declaration):
    # JSON true must be an actual boolean assertion, not the integer 1.
    return (isinstance(declaration, dict) and declaration.keys() == CAPTURE_DECLARATION.keys() and
            all(type(declaration[key]) is type(expected) and declaration[key] == expected
                for key, expected in CAPTURE_DECLARATION.items()))


def validate_metadata(metadata):
    require(isinstance(metadata, dict), "Metadata must be an object")
    category = metadata.get("category")
    rank = metadata.get("selected_rank")
    role = metadata.get("corpus_role")
    require(category in ("STANDARD", "NO_FLAG"), "Invalid category")
    require(type(rank) is int and rank > 0, "selected_rank must be a positive integer")
    require(role in ("TECHNICAL_PILOT", "FINAL"), "Explicit corpus_role is required")
    if role == "FINAL":
        require(rank != 15, "Rank 15 is reserved for technical pilots")
    replacement_of = metadata.get("replacement_of")
    replacement_reason = metadata.get("replacement_reason")
    if replacement_of is None and replacement_reason is None:
        if role == "FINAL":
            require(rank in ORIGINAL_TARGET_RANKS[category], "Rank is outside the original target set")
    else:
        require(type(replacement_of) is int and replacement_of in ORIGINAL_TARGET_RANKS[category],
                "replacement_of must be an integer original target rank for this category")
        require(isinstance(replacement_reason, str) and replacement_reason.strip(),
                "replacement_reason must be a nonempty string")
        require(rank != replacement_of, "selected_rank must differ from replacement_of")
        # Nearest/unused rank and corpus uniqueness need other replay records.
        # Deferring those checks does not make a valid replacement non-authoritative.
    require(type(metadata.get("displayed_final_click_count")) is int and
            metadata["displayed_final_click_count"] > 0, "Final click count must be a positive integer")
    require(("displayed_time_seconds" in metadata) != ("displayed_time_ms" in metadata),
            "Supply exactly one displayed_time_seconds string or displayed_time_ms integer")
    if "displayed_time_ms" in metadata:
        require(type(metadata["displayed_time_ms"]) is int, "displayed_time_ms must be an integer")
        human_us = metadata["displayed_time_ms"] * 1000
        displayed = {"value": metadata["displayed_time_ms"], "unit": "ms", "source": "SUPPLIED_METADATA"}
    else:
        text = metadata["displayed_time_seconds"]
        require(isinstance(text, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text),
                "displayed_time_seconds must be an exact decimal string")
        # Fraction(Decimal) avoids the ambient Decimal precision/rounding context.
        try:
            microseconds = Fraction(Decimal(text)) * 1_000_000
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError("Invalid displayed time") from exc
        require(microseconds.denominator == 1, "Displayed time must resolve to integer microseconds")
        human_us = microseconds.numerator
        displayed = {"value": text, "unit": "s", "source": "SUPPLIED_METADATA"}
    require(human_us > 0, "Displayed time must be positive")
    for key in ("player", "recorded_date"):
        require(metadata.get(key) is None or isinstance(metadata[key], str), f"{key} must be a string or null")
    notes = []
    declaration = metadata.get("capture_declaration")
    if declaration is not None:
        require(isinstance(declaration, dict), "capture_declaration must be an object")
        if not capture_declaration_compatible(declaration):
            notes.append("CAPTURE_DECLARATION_INCOMPATIBLE")
    elif role == "FINAL":
        notes.append("CAPTURE_DECLARATION_REQUIRED")
    return human_us, displayed, notes


def validate_video_metadata(width, height, fps):
    return [] if (width, height, fps) == (1920, 1080, FPS) else ["INCOMPATIBLE_DIMENSIONS_OR_FPS"]


def classify_pts_issues(issues, decoded_frame_count, last_event_frame):
    """Split blocking PTS issues from the one permitted terminal-tail exception.

    Each issue is ``(frame_index, kind, delta)`` where kind is MISSING_PTS or
    NON_CFR_INTERVAL and delta is an exact Fraction for interval issues. The
    exception is intentionally narrower than a general post-game CFR relaxation.
    """
    if not issues:
        return [], None
    issue = issues[0]
    frame_index, kind, delta = issue
    terminal_tail = (
        len(issues) == 1
        and kind == "NON_CFR_INTERVAL"
        and delta is not None
        and delta > 1 / FPS
        and decoded_frame_count > 0
        and frame_index == decoded_frame_count - 1
        and last_event_frame is not None
        and frame_index > last_event_frame + CURSOR_SEARCH_RADIUS
    )
    return ([], issue) if terminal_tail else (list(issues), None)


def pts_issue_json(issue):
    frame_index, kind, delta = issue
    return {"frame": frame_index, "kind": kind,
            "delta_seconds": rational(delta) if delta is not None else None}


def pixel_to_cell(x, y):
    if not (BOARD_X <= x < BOARD_X + COLS * CELL and BOARD_Y <= y < BOARD_Y + ROWS * CELL):
        return None
    return int((x - BOARD_X) // CELL), int((y - BOARD_Y) // CELL)


def frame_interval(frame_delta, fps=FPS):
    require(type(frame_delta) is int and frame_delta >= 0, "Invalid frame delta")
    require(isinstance(fps, Fraction) and fps > 0, "FPS must be a positive rational")
    tick = 1_000_000 / fps
    return frame_delta * tick, max(0, frame_delta - 1) * tick, (frame_delta + 1) * tick


def comparison_class(predicted, low, high):
    if predicted <= low:
        return "MODEL_BELOW"
    return "FRAME_AMBIGUOUS" if predicted <= high else "MODEL_ABOVE"


def calculate_transitions(events, table, fps=FPS):
    transitions = []
    for previous, event in zip(events, events[1:]):
        if (previous["target_x"] is None or event["target_x"] is None or
                event["visible_click_count_after"] != previous["visible_click_count_after"] + 1):
            continue
        dx, dy = abs(event["target_x"] - previous["target_x"]), abs(event["target_y"] - previous["target_y"])
        predicted = table[dx][dy]
        delta = event["event_frame"] - previous["event_frame"]
        point, low, high = frame_interval(delta, fps)
        transitions.append({
            "from_event_index": previous["event_index"], "to_event_index": event["event_index"],
            "dx": dx, "dy": dy, "predicted_us": predicted, "frame_delta": delta,
            "observed_point_us": rational(point), "observed_low_us": rational(low),
            "observed_high_us": rational(high), "comparison_class": comparison_class(predicted, low, high),
        })
    return transitions


# Abstract 12-row numeral/operator masks for the fixed sidebar UI, without
# screenshot backgrounds, player identifiers, board information or replay data.
# All masks are normalized before matching, including subpixel width variants.
GLYPHS = {
    "0": ("..#####..", ".###.###.", "###...###", "##.....##", "##.....##", "##.....##",
          "##.....##", "##.....##", "##.....##", "###...###", ".###.###.", "..#####.."),
    "1": ("..###", ".####", "##.##", "...##", "...##", "...##", "...##", "...##", "...##", "...##", "...##", "...##"),
    "2": ("..#####..", ".###.###.", "......##.", "......##.", "......##.", ".....###.",
          ".....##..", "....##...", "...##....", "..##.....", ".##......", "#########"),
    "3": (".######.", "###..###", "......##", "......##", "....###.", "..#####.",
          ".....###", "......##", "......##", "......##", "##..####", "#######."),
    "4": ("......##..", ".....###..", "....####..", "...#####..", "...##.##..", "..##..##..",
          ".##...##..", ".##...##..", "##########", "......##..", "......##..", "......##.."),
    "5": (".#######", ".##.....", ".##.....", ".##.....", ".##.....", ".######.",
          ".#...###", "......##", "......##", "......##", "##...###", "#######."),
    "6": ("...####..", "..###....", ".###.....", ".##......", "##.......", "########.",
          "###..####", "##....###", "##....###", "##....##.", ".###.###.", "..#####.."),
    "7": ("#########", "......###", "......##.", "......##.", ".....##..", ".....##..",
          "....##...", "....##...", "...##....", "...##....", "..##.....", "..##....."),
    "8": ("..#####..", ".##..###.", "##....##.", "##....##.", ".##..###.", "..####...",
          ".######..", "##....##.", "##....###", "##....###", "###..###.", ".######.."),
    "9": ("..#####..", ".###.###.", ".##....##", "###....##", ".##....##", ".###..###",
          "..#######", ".......##", "......###", "......##.", "....####.", ".#####..."),
    "/": ("....##", "....##", "...##.", "...##.", "...##.", "..##..", "..##..", "..##..", ".##...", ".##...", "##....", "##...."),
    "+": ("...##...", "...##...", "...##...", "...##...", "########", "...##...", "...##...", "...##...", "...##..."),
}


class FixedUI:
    """OpenCV/numpy are loaded only when the offline detector is instantiated."""

    def __init__(self):
        import cv2
        import numpy as np
        self.cv2, self.np = cv2, np
        self.templates = {key: self.normalize(np.array([[v == "#" for v in row] for row in rows],
                                                       dtype=np.uint8) * 255)
                          for key, rows in GLYPHS.items()}
        self.template_distances = {k: cv2.distanceTransform((~a).astype("uint8"), cv2.DIST_L2,
                                                          cv2.DIST_MASK_PRECISE)
                                   for k, a in self.templates.items()}

    def normalize(self, mask):
        return self.cv2.resize(mask, (12, 16), interpolation=self.cv2.INTER_AREA) > 127

    def glyph(self, mask, x_offset, y_offset):
        cv2, np = self.cv2, self.np
        ys, xs = np.nonzero(mask)
        if not len(xs):
            return None
        x, y = int(xs.min()), int(ys.min())
        w, h = int(xs.max()) - x + 1, int(ys.max()) - y + 1
        if not (4 <= w <= 11 and 9 <= h <= 13):
            return None
        sample = self.normalize(mask[y:y+h, x:x+w])
        sample_distance = cv2.distanceTransform((~sample).astype("uint8"), cv2.DIST_L2,
                                                cv2.DIST_MASK_PRECISE)
        distances = sorted((max(float(sample_distance[template].max()),
                                float(self.template_distances[k][sample].max())), k)
                           for k, template in self.templates.items())
        distance, char = distances[0]
        # A one-pixel source raster edge can move ~2 pixels on the 12x16
        # normalized grid. BOTH directed maximum distances must be <=2;
        # a second matching template makes the glyph unreadable.
        if distance > 2 or distances[1][0] <= 2:
            return None
        return {"x": x + x_offset, "y": y + y_offset, "width": w, "height": h, "candidate": char,
                "distance_milli": round(distance * 1000), "second_distance_milli": round(distances[1][0] * 1000),
                "acceptance_radius_milli": 2000}

    def glyph_run(self, mask, x_offset):
        """Exhaustive shape-only segmentation of touching proportional glyphs.

        Connected components alone join e.g. 34 where the 4's crossbar touches
        the 3. Enumerate all cuts of at most the UI's 11 px glyph width; consume
        every foreground column, and accept only one distinct decoded string.
        No expected count, previous reading, or corpus number participates.
        """
        from functools import lru_cache

        @lru_cache(None)
        def visit(start):
            if start == mask.shape[1]:
                return [("", [])]
            solutions = []
            for end in range(start + 4, min(start + 11, mask.shape[1]) + 1):
                glyph = self.glyph(mask[:, start:end], x_offset + start, 0)
                if glyph is None:
                    continue
                for suffix, details in visit(end):
                    solutions.append((glyph["candidate"] + suffix, [glyph] + details))
            return solutions

        solutions = visit(0)
        if len({text for text, _ in solutions}) != 1:
            return None
        return min(solutions, key=lambda s: (sum(g["distance_milli"] for g in s[1]),
                                            tuple(g["width"] for g in s[1])))

    def counter(self, frame):
        cv2, np = self.cv2, self.np
        x0, y0, x1, y1 = COUNTER_ROI
        crop = frame[y0:y1, x0:x1]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        ink_rows = np.flatnonzero(mask.any(axis=1))
        if not len(ink_rows):
            return {"mode": "UNREADABLE", "text": None, "glyphs": [], "reason": "EMPTY_COUNTER"}
        # Numerals have a 12 px cap height. The summary's dotted underline begins
        # immediately below it and can connect otherwise separate characters.
        mask[int(ink_rows[0]) + 12:] = 0
        chars, diagnostics = [], []
        ink_columns = np.flatnonzero(mask.any(axis=0))
        groups = np.split(ink_columns, np.flatnonzero(np.diff(ink_columns) != 1) + 1)
        for group in groups:
            x, end = int(group[0]), int(group[-1]) + 1
            decoded = self.glyph_run(mask[:, x:end], x)
            if decoded is None:
                return {"mode": "UNREADABLE", "text": None, "glyphs": diagnostics,
                        "reason": "AMBIGUOUS_GLYPH_OR_SEGMENTATION", "unreadable_run_x": [x, end]}
            chars.append(decoded[0])
            diagnostics.extend(decoded[1])
        text = "".join(chars)
        running = re.fullmatch(r"(0|[1-9][0-9]*)/(0|[1-9][0-9]*)", text)
        if running:
            current, total = map(int, running.groups())
            if current <= total and total > 0:
                return {"mode": "RUNNING", "count": current, "total": total,
                        "text": text, "glyphs": diagnostics}
        if re.fullmatch(r"[0-9]+(?:\+[0-9]+)?", text):
            return {"mode": "SUMMARY", "count": sum(map(int, text.split("+"))),
                    "text": text, "glyphs": diagnostics}
        return {"mode": "UNREADABLE", "text": text, "glyphs": diagnostics, "reason": "UNKNOWN_COUNTER_SYNTAX"}

    def layout(self, frame):
        """Validate outer bevels and all interior grid lines at fixed coordinates.

        The V1 grayscale palette is dark bevel 128, face 197, white bevel 255.
        Midpoints between palette levels define pixel classes. Grid lines have
        either dark or white bevel pixels; sample them in the top-left margins
        of each cell, away from numbers, flags and cursor centers. Medians across
        each complete row/column permit localized cursor occlusion. Every line
        and all four outer bevels must agree; no percentage-of-board pass rule.
        """
        if frame.shape[:2] != (1080, 1920):
            return False
        gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
        np = self.np
        dark_limit, white_limit = (128 + 197) / 2, (197 + 255) / 2
        outer = (np.median(gray[328:332, 590:1534]) < dark_limit and
                 np.median(gray[340:836, 578:582]) < dark_limit and
                 np.median(gray[846:850, 590:1534]) > white_limit and
                 np.median(gray[340:836, 1544:1548]) > white_limit)
        if not outer:
            return False
        # Covered cells have white left/top bevels; revealed cells have dark
        # grid lines. At a mixed covered/revealed boundary there may be NO dark
        # pixel. Both palette edge states are valid at the same lattice position.
        for col in range(COLS):
            x = BOARD_X + CELL * col
            values = gray[BOARD_Y + 8:BOARD_Y + ROWS * CELL - 8, x:x+3]
            bevel = (values < dark_limit) | (values > white_limit)
            face = np.median(gray[BOARD_Y + 8:BOARD_Y + ROWS * CELL - 8, x+6:x+9])
            if not np.median(bevel.any(axis=1)) or not dark_limit < face < white_limit:
                return False
        for row in range(ROWS):
            y = BOARD_Y + CELL * row
            values = gray[y:y+3, BOARD_X + 8:BOARD_X + COLS * CELL - 8]
            bevel = (values < dark_limit) | (values > white_limit)
            face = np.median(gray[y+6:y+9, BOARD_X + 8:BOARD_X + COLS * CELL - 8])
            if not np.median(bevel.any(axis=0)) or not dark_limit < face < white_limit:
                return False
        return True

    def cursor(self, frame):
        cv2 = self.cv2
        # Include one cell around the board so clipped/outside rings are rejected
        # by pixel_to_cell, instead of silently being mapped to an edge cell.
        x0, y0 = BOARD_X - CELL, BOARD_Y - CELL
        gray = cv2.cvtColor(frame[y0:BOARD_Y + (ROWS + 1) * CELL,
                                 x0:BOARD_X + (COLS + 1) * CELL], cv2.COLOR_BGR2GRAY)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1, minDist=CELL,
                                   param1=100, param2=20, minRadius=13, maxRadius=17)
        # param1: gradient edge threshold, separating the ~69-level ring/bevel
        # contrasts; param2: minimum 20 circle votes (~one fifth of circumference).
        # Radius bounds include the inner/outer edges of the nominal 16 px ring.
        candidates = []
        if circles is not None:
            for x, y, radius in circles[0]:
                px, py = float(x) + x0, float(y) + y0
                cell = pixel_to_cell(px, py)
                candidates.append({"center_x_half_px": round(px * 2), "center_y_half_px": round(py * 2),
                                   "radius_milli_px": round(float(radius) * 1000),
                                   "cell": list(cell) if cell is not None else None})
        candidates.sort(key=lambda c: (c["center_x_half_px"], c["center_y_half_px"]))
        cells = {tuple(c["cell"]) for c in candidates if c["cell"] is not None}
        # Multiple ring candidates are ambiguous even if they map to one cell.
        cell = next(iter(cells)) if len(candidates) == 1 and len(cells) == 1 else None
        return {"cell": list(cell) if cell is not None else None, "candidates": candidates,
                "status": "UNIQUE" if cell else ("NOT_DETECTED" if not candidates else "AMBIGUOUS_OR_OUTSIDE")}


class EventDetector:
    """Count increments are the sole event boundary; never repairs the sequence."""

    def __init__(self):
        self.events = []
        self.flags = []
        self.active = False
        self.ended = False
        self.previous = 0
        self.total = None
        self.unreadable_frames = []
        self.last_read_frame = None
        self.final_summary_count = None

    def feed(self, frame_index, reading):
        mode = reading["mode"]
        if mode == "UNREADABLE":
            self.unreadable_frames.append(frame_index)
            return
        if mode == "SUMMARY":
            self.final_summary_count = reading["count"]
            if not self.active or self.ended:
                self.last_read_frame = frame_index
                return
            self.ended = True
            count = reading["count"]
        else:
            count = reading["count"]
            if self.ended:
                self.flags.append("PLAYBACK_RESTART_OR_SEEK")
            if self.total is not None and self.total != reading["total"]:
                self.flags.append("COUNTER_TOTAL_CHANGED")
            self.total = reading["total"]
            self.active = True
        if count > self.previous:
            flags = []
            if count != self.previous + 1:
                flags.append("SKIPPED_VISIBLE_COUNT")
            if self.last_read_frame != frame_index - 1:
                flags.append("EVENT_BOUNDARY_UNVERIFIED")
            self.events.append({"event_index": len(self.events) + 1, "event_frame": frame_index,
                                "visible_click_count_after": count, "target_x": None, "target_y": None,
                                "target_resolution_method": "MANUAL_REVIEW", "target_frame_used": None,
                                "action_type": "UNKNOWN", "action_type_confidence": "NOT_CLASSIFIED",
                                "counter_text": reading["text"], "counter_glyphs": reading.get("glyphs", []),
                                "review_flags": flags})
            self.flags.extend(flags)
        elif count < self.previous:
            self.flags.append("COUNTER_DECREASE_OR_SEEK")
        self.previous = count
        self.last_read_frame = frame_index


def resolve_target(event, observations):
    frame = event["event_frame"]
    available = {f: o for f, o in observations.items() if abs(f - frame) <= CURSOR_SEARCH_RADIUS}
    event["cursor_diagnostics"] = [{"frame": f, **available[f]} for f in sorted(available)]
    exact = available.get(frame, {})
    if exact.get("cell") is not None:
        chosen = frame
        method = "EVENT_FRAME"
    else:
        event["fallback_reason"] = exact.get("status", "FRAME_UNAVAILABLE")
        # A visibly conflicting exact frame cannot be repaired with nearby motion.
        if exact.get("status") == "AMBIGUOUS_OR_OUTSIDE":
            event["review_flags"].append("AMBIGUOUS_EVENT_FRAME_CURSOR")
            return
        candidates = [(abs(f - frame), f, o["cell"]) for f, o in available.items() if o.get("cell") is not None]
        if not candidates:
            event["review_flags"].append("NO_CURSOR_WITHIN_FOUR_FRAMES")
            return
        nearest_distance = min(c[0] for c in candidates)
        nearest = [c for c in candidates if c[0] == nearest_distance]
        if len({tuple(c[2]) for c in nearest}) != 1:
            event["review_flags"].append("CONFLICTING_NEAREST_CURSOR_CELLS")
            return
        _, chosen, cell = min(nearest)
        if not any(available.get(f, {}).get("cell") == cell for f in (chosen - 1, chosen + 1)):
            event["review_flags"].append("FALLBACK_CELL_NOT_STABLE")
            return
        method = "NEAREST_STABLE_WITHIN_4"
    event["target_x"], event["target_y"] = available[chosen]["cell"]
    event["target_frame_used"] = chosen
    event["target_resolution_method"] = method


def summarize(events, displayed_count, human_us, table, flags):
    difference = len(events) - displayed_count
    unresolved = sum(e["target_x"] is None for e in events)
    if difference:
        flags.append("EVENT_COUNT_MISMATCH")
    if unresolved:
        flags.append("UNRESOLVED_TARGETS")
    if not events:
        flags.append("NO_EVENTS")
    transitions = calculate_transitions(events, table)
    subtotal = sum(t["predicted_us"] for t in transitions)
    classes = Counter(t["comparison_class"] for t in transitions)
    flags.extend(flag for event in events for flag in event["review_flags"])
    if len(transitions) != max(0, len(events) - 1):
        flags.append("INCOMPLETE_TRANSITIONS")
    status = ("INCOMPATIBLE_INPUT" if any(f.startswith("INCOMPATIBLE_") for f in flags)
              else "REVIEW_REQUIRED" if flags else "RECONSTRUCTED")
    span = frame_interval(events[-1]["event_frame"] - events[0]["event_frame"])[0] if events else None
    return {
        "replay_status": status, "review_flags": sorted(set(flags)),
        "displayed_final_click_count": displayed_count, "reconstructed_event_count": len(events),
        "completeness_difference": difference, "unresolved_target_count": unresolved,
        "fallback_cursor_resolution_count": sum(e["target_resolution_method"] == "NEAREST_STABLE_WITHIN_4" for e in events),
        "first_event_frame": events[0]["event_frame"] if events else None,
        "last_event_frame": events[-1]["event_frame"] if events else None,
        "video_span_us": rational(span) if span is not None else None,
        "displayed_minus_video_span_us": rational(human_us - span) if span is not None else None,
        "transition_count": len(transitions), "modeled_physical_time_us": subtotal if status == "RECONSTRUCTED" else None,
        "resolved_transition_subtotal_us": subtotal, "displayed_human_time_us": human_us,
        "physical_to_human_ratio": rational(Fraction(subtotal, human_us)) if status == "RECONSTRUCTED" else None,
        "comparison_counts": {key: classes[key] for key in ("MODEL_BELOW", "FRAME_AMBIGUOUS", "MODEL_ABOVE")},
        "events": events, "transitions": transitions,
    }


def analyze_video(video_path, metadata, profile_path=PROFILE_PATH):
    # Profile verification MUST precede opening/decoding any video.
    profile = load_frozen_profile(profile_path)
    human_us, displayed, flags = validate_metadata(metadata)
    source_sha256 = file_sha256(video_path)
    import av
    ui = FixedUI()
    detector = EventDetector()
    layout_bad, pts_issues = [], []
    pts_first = pts_last = None
    decoded = 0
    with av.open(str(video_path)) as container:
        require(len(container.streams.video) == 1, "Exactly one video stream is required")
        stream = container.streams.video[0]
        fps = Fraction(stream.average_rate) if stream.average_rate else None
        width, height = stream.width, stream.height
        flags.extend(validate_video_metadata(width, height, fps))
        video = {"width": width, "height": height, "fps": rational(fps) if fps else None,
                 "declared_frame_count": stream.frames, "frame_count": 0,
                 "stream_duration_us": rational(stream.duration * stream.time_base * 1_000_000)
                 if stream.duration is not None else None,
                 "time_base": rational(stream.time_base), "cfr_compatibility_status": "NOT_CHECKED"}
        if not flags or all(not f.startswith("INCOMPATIBLE_") for f in flags):
            for index, frame in enumerate(container.decode(video=0)):
                decoded += 1
                pts = frame.pts * frame.time_base if frame.pts is not None else None
                if pts is None:
                    pts_issues.append((index, "MISSING_PTS", None))
                elif pts_last is not None:
                    delta = pts - pts_last
                    if delta != 1 / FPS:
                        pts_issues.append((index, "NON_CFR_INTERVAL", delta))
                if index == 0:
                    pts_first = pts
                pts_last = pts
                image = frame.to_ndarray(format="bgr24")
                if (frame.width, frame.height) != (width, height) or not ui.layout(image):
                    layout_bad.append(index)
                detector.feed(index, ui.counter(image))
            if not decoded:
                flags.append("INCOMPATIBLE_EMPTY_VIDEO")
            last_event_frame = detector.events[-1]["event_frame"] if detector.events else None
            blocking_pts, terminal_tail_pts = classify_pts_issues(pts_issues, decoded, last_event_frame)
            if blocking_pts:
                flags.append("INCOMPATIBLE_NON_CFR_OR_MISSING_PTS")
            if stream.frames and decoded != stream.frames:
                flags.append("DECODED_FRAME_COUNT_MISMATCH")
            if layout_bad:
                flags.append("LAYOUT_REVIEW_REQUIRED")
            if not decoded or blocking_pts:
                video["cfr_compatibility_status"] = "INCOMPATIBLE"
            elif terminal_tail_pts is not None:
                video["cfr_compatibility_status"] = "COMPATIBLE_WITH_TERMINAL_TAIL_EXCEPTION"
            else:
                video["cfr_compatibility_status"] = "COMPATIBLE"
        else:
            blocking_pts, terminal_tail_pts = [], None
    video.update({"frame_count": decoded,
                  "bad_pts_frames": [issue[0] for issue in pts_issues],
                  "blocking_bad_pts_frames": [issue[0] for issue in blocking_pts],
                  "pts_issues": [pts_issue_json(issue) for issue in pts_issues],
                  "terminal_tail_pts_exception": pts_issue_json(terminal_tail_pts)
                  if terminal_tail_pts is not None else None,
                  "first_pts_seconds": rational(pts_first) if pts_first is not None else None,
                  "last_pts_seconds": rational(pts_last) if pts_last is not None else None,
                  "video_duration_us": rational((pts_last - pts_first + 1 / FPS) * 1_000_000)
                  if pts_first is not None and pts_last is not None and not blocking_pts else None})
    needed = {f for e in detector.events for f in range(max(0, e["event_frame"] - CURSOR_SEARCH_RADIUS),
                                      min(decoded, e["event_frame"] + CURSOR_SEARCH_RADIUS + 1))}
    observations = {}
    if needed:
        with av.open(str(video_path)) as container:
            for index, frame in enumerate(container.decode(video=0)):
                if index in needed:
                    observations[index] = ui.cursor(frame.to_ndarray(format="bgr24"))
        for event in detector.events:
            resolve_target(event, observations)
    flags.extend(detector.flags)
    if detector.total != metadata["displayed_final_click_count"]:
        flags.append("VISIBLE_TOTAL_METADATA_MISMATCH")
    if not detector.ended or detector.final_summary_count != metadata["displayed_final_click_count"]:
        flags.append("FINAL_SUMMARY_NOT_VALIDATED")
    # Even if an unreadable frame does not border a later increment, it could
    # hide a counter reset/increment. Preserve diagnostics and require review.
    if detector.active and detector.unreadable_frames:
        flags.append("UNREADABLE_COUNTER_FRAMES")
    if file_sha256(video_path) != source_sha256:
        flags.append("SOURCE_VIDEO_CHANGED_DURING_ANALYSIS")
    result = summarize(detector.events, metadata["displayed_final_click_count"], human_us,
                       profile["timing_table_us"], flags)
    result.update({
        "protocol_version": PROTOCOL_VERSION,
        "category": metadata["category"], "selected_rank": metadata["selected_rank"],
        "corpus_role": metadata["corpus_role"], "player": metadata.get("player"),
        "recorded_date": metadata.get("recorded_date"), "displayed_time": displayed,
        "replacement_of": metadata.get("replacement_of"), "replacement_reason": metadata.get("replacement_reason"),
        "source_video_filename": Path(video_path).name, "source_video_sha256": source_sha256,
        "video": video, "capture_declaration": metadata.get("capture_declaration"),
        "capture_declaration_status": ("SUPPLIED_COMPATIBLE" if capture_declaration_compatible(metadata.get("capture_declaration"))
                                       else "NOT_SUPPLIED" if metadata.get("capture_declaration") is None
                                       else "SUPPLIED_INCOMPATIBLE"),
        "geometry": {"board_top_left": [BOARD_X, BOARD_Y], "cell_size_px": CELL,
                     "board_dimensions": [COLS, ROWS], "board_extent_px": [COLS * CELL, ROWS * CELL],
                     "counter_roi_xyxy": list(COUNTER_ROI), "layout_bad_frames": layout_bad},
        "counter_diagnostics": {"unreadable_frames": detector.unreadable_frames,
                                "visible_running_total": detector.total, "final_summary_count": detector.final_summary_count},
        "physical_profile": {"filename": Path(profile_path).name, "whole_profile_sha256": PROFILE_SHA256,
                             "timing_table_sha256": TABLE_SHA256, "model_id": MODEL_ID},
        "software_versions": {"opencv": ui.cv2.__version__, "numpy": ui.np.__version__, "pyav": av.__version__},
        "numeric_contract": "integer us for H/P; reduced numerator/denominator for rational quantities; no rounding",
        "event_boundary": "FIRST_VISIBLE_CLICK_COUNT_INCREMENT",
        "uncertainty_contract": "plus/minus one frame capture quantization only; no latency or statistical claim",
    })
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=PROFILE_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), "Output exists; choose a new filename to preserve evidence")
        result = analyze_video(args.video, read_json(args.metadata), args.profile)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as output:
            output.write(canonical_bytes(result))
    except (ValidationError, OSError, ValueError, ImportError) as exc:
        print(f"Replay validation rejected: {exc}", file=sys.stderr)
        return 2
    print(f"{result['replay_status']}: {result['reconstructed_event_count']}/"
          f"{result['displayed_final_click_count']} events; P_us={result['modeled_physical_time_us']}; {args.output}")
    return 0 if result["replay_status"] == "RECONSTRUCTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
