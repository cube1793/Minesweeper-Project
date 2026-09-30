"""Offline V1 calibration analysis; no collection or solver dependencies.

Usage: python stage3_calibration_analysis.py --session SESSION.json
    --trials TRIALS.jsonl --report REPORT.json --profile PROFILE.json

Inputs are read once and hashed verbatim. Both output paths must be new files
in existing directories. Outputs contain no generation timestamp, so identical
inputs produce identical bytes. Synthetic measurements belong only in tests.

Numeric contract (reference: CPython 3.12 Decimal): precision 80, HALF_EVEN,
explicit exponent bounds and traps below. Distance uses Decimal.sqrt(); x uses
Decimal.ln(1 + distance) / Decimal.ln(2), with exact integer results when
1 + distance is an integer power of two. Every operation, including each sum,
runs in that context in frozen offset order. No binary float enters the fit or
table. Decimal strings preserve the computed values exactly, not an assertion
that irrational logarithms have a finite exact representation.

The authoritative model is max(c, k*x): c is the O00 execution-time floor;
k minimizes the nonzero-median SSE by finite piecewise-quadratic enumeration.
Additive fits remain explicitly non-authoritative report diagnostics only.
The output versions remain 1: this format has no frozen profile or runtime
consumer yet. model_id identifies the revised pre-freeze model semantics.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime
from decimal import (
    Context, Decimal, DecimalException, DivisionByZero, FloatOperation,
    InvalidOperation, Overflow, ROUND_HALF_EVEN, localcontext,
)
from pathlib import Path

from stage3_calibration import (
    BUTTON_TRANSITIONS, CELL_SIZE_PX, GRID_HEIGHT, GRID_WIDTH, OFFICIAL,
    OFFSET_FAMILIES, PROTOCOL_VERSION, WARMUP, CalibrationManifest,
    CalibrationTrial, canonical_manifest_bytes,
)


FROZEN_MANIFEST_PATH = Path(__file__).resolve().parent / "calibration/stage3_calibration_manifest_v1.json"
FROZEN_MANIFEST_SHA256 = "07ce6943abec4f47474f50bfb317fea3dcd9c51afcf87c316adef674f58ce61d"
DECIMAL_PRECISION = 80
MODEL_ID = "overlap_floor_log2_distance_v1"
MODEL_FORMULA = "T_us(dx,dy)=max(c_us,k_us*log2(1+sqrt(dx^2+dy^2)))"
PARAMETER_SEMANTICS = {
    "c_us": "empirical same-cell execution-time floor",
    "k_us": "distance-dependent execution coefficient",
}
PHYSICAL_EXECUTION = {
    "includes": ["pre-presented target execution", "LEFT/RIGHT button selection",
                 "ordinary motor preparation", "cursor movement", "target press"],
    "excludes": ["Minesweeper board reading", "safe/mine inference",
                 "probability reasoning", "strategic deliberation"],
}
NUMERIC_CONTRACT = {
    "reference_python": "CPython 3.12 Decimal",
    "precision": DECIMAL_PRECISION,
    "rounding": "ROUND_HALF_EVEN",
    "Emin": -999999,
    "Emax": 999999,
    "capitals": 1,
    "clamp": 0,
    "traps": ["InvalidOperation", "DivisionByZero", "Overflow", "FloatOperation"],
    "distance": "Decimal(dx*dx + dy*dy).sqrt()",
    "log2": "Exact integer log2 for integer powers of two; otherwise (Decimal(1) + distance).ln() / Decimal(2).ln()",
    "summation_order": "frozen offset order O00..O15; floor coefficient objective uses O01..O15",
    "coefficient_fit": "Enumerate all c/x_i breakpoints, k=0 and feasible region stationary points; minimize (SSE, k)",
    "crossover_distance": "((c/k)*Decimal(2).ln()).exp()-1; null when k=0",
    "parameter_encoding": "fixed-point decimal strings; fractional trailing zeros removed",
}


def numeric_context():
    """A fresh context, independent of the caller's precision, traps and flags."""
    return Context(prec=DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN,
                   Emin=-999999, Emax=999999, capitals=1, clamp=0,
                   traps=[InvalidOperation, DivisionByZero, Overflow, FloatOperation])


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, name, minimum=0):
    _require(type(value) is int and value >= minimum, f"{name}: expected integer >= {minimum}")
    return value


def _decimal(value):
    _require(type(value) in (int, Decimal), "Expected a finite Decimal or integer, never a float")
    result = Decimal(value)
    _require(result.is_finite(), "Expected a finite numeric value")
    return result


def decimal_text(value):
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if value == 0 else text


def _json_numbers(value):
    if isinstance(value, Decimal):
        return decimal_text(value)
    if isinstance(value, dict):
        return {key: _json_numbers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_numbers(item) for item in value]
    return value


def canonical_output_bytes(value):
    """Report/profile JSON contract; distinct from the timing-table encoding."""
    return (json.dumps(_json_numbers(value), sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError(f"Non-finite JSON constant: {value}")


def _metadata_float(text):
    # Environment metadata stays numeric JSON, but a huge exponent must not
    # silently become infinity before validation. It never enters the model.
    value = float(text)
    _require(value not in (float("inf"), float("-inf")), "Non-finite session metadata")
    return value


def _read_json(payload, *, decimal_pixels=False):
    return json.loads(payload, object_pairs_hook=_unique_object,
                      parse_constant=_bad_constant,
                      parse_float=Decimal if decimal_pixels else _metadata_float)


def load_frozen_manifest(path=FROZEN_MANIFEST_PATH):
    payload = Path(path).read_bytes()
    _require(hashlib.sha256(payload).hexdigest() == FROZEN_MANIFEST_SHA256,
             "Frozen manifest SHA-256 mismatch")
    data = _read_json(payload)
    data["trials"] = [CalibrationTrial(**trial) for trial in data["trials"]]
    manifest = CalibrationManifest(**data)
    _require(canonical_manifest_bytes(manifest) == payload, "Frozen manifest is not canonical")
    return manifest


def _same_json(actual, expected):
    # In particular, JSON true and 1.0 must not match an integer schedule field.
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_same_json(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _validate_session(session):
    _require(isinstance(session, dict), "Session must be a JSON object")
    expected = {
        "session_status": "COMPLETED", "protocol_version": PROTOCOL_VERSION,
        "manifest_seed": 20260930, "manifest_sha256": FROZEN_MANIFEST_SHA256,
        "grid_width": 30, "grid_height": 16, "cell_size_px": 28,
        "timing_boundary": "start_press_to_target_press",
        "raw_timing_unit": "ns", "coordinate_unit": "qt_logical_px",
        "valid_warmup_attempts": 24, "valid_official_attempts": 384,
    }
    for key, value in expected.items():
        _require(_same_json(session.get(key), value), f"Incompatible session {key}")
    for key in ("session_id", "manifest_path", "os", "python_version", "python_implementation",
                "pyqt_version", "qt_version", "qt_platform", "clock"):
        _require(isinstance(session.get(key), str) and bool(session[key].strip()), f"Missing session {key}")
    _require(isinstance(session.get("notes"), str), "Missing session notes")
    # Display values are provenance only, including explicit absence. They do
    # not gate observations or affect any fitted value or generated table.
    for key in ("screen_name", "screen_resolution_logical_px", "qt_logical_dpi",
                "device_pixel_ratio", "display_refresh_rate_hz", "display_refresh_rate_status",
                "display_refresh_rate_unavailable_reason"):
        _require(key in session, f"Missing session provenance: {key}")
    times = []
    for key in ("session_started_at_utc", "session_ended_at_utc"):
        _require(isinstance(session.get(key), str), f"Missing session {key}")
        try:
            stamp = datetime.fromisoformat(session[key])
        except ValueError as error:
            raise ValueError(f"Invalid session {key}") from error
        _require(stamp.utcoffset() is not None and stamp.utcoffset().total_seconds() == 0,
                 f"{key} must be UTC")
        times.append(stamp)
    _require(times[1] >= times[0], "Session end precedes start")
    _integer(session.get("invalid_attempts"), "invalid_attempts")


def _point(value):
    _require(isinstance(value, list) and len(value) == 2, "Click point must have two coordinates")
    return tuple(_decimal(v) for v in value)


def _inside_cell(point, cell):
    return all(c * CELL_SIZE_PX <= p < (c + 1) * CELL_SIZE_PX for p, c in zip(point, cell))


def _validate_attempt(record, trial):
    planned = asdict(trial)
    for key in ("start_cell", "target_cell"):
        planned[key] = list(planned[key])
    for key, value in planned.items():
        _require(_same_json(record.get(key), value), f"Schedule mismatch: {trial.trial_id}.{key}")
    valid = record["valid"]
    _require(record.get("invalid_reason") is None if valid else
             isinstance(record.get("invalid_reason"), str) and bool(record["invalid_reason"].strip()),
             "Invalid validity/reason combination")
    for key in ("start_release_ns", "target_press_ns", "target_press_px", "duration_ns", "invalid_reason"):
        _require(key in record, f"Missing attempt field: {key}")
    start = _integer(record.get("start_press_ns"), "start_press_ns")
    end = _integer(record.get("end_ns"), "end_ns", start)
    released = record["start_release_ns"]
    if released is not None:
        _integer(released, "start_release_ns", start)
        _require(released <= end, "START release occurs after attempt end")
    start_point = _point(record.get("start_press_px"))
    _require(_inside_cell(start_point, trial.start_cell), "START click outside its cell")
    target = record["target_press_ns"]
    if target is None:
        _require(not valid and record["duration_ns"] is None and record["target_press_px"] is None,
                 "Interrupted attempt must have null target/duration")
    else:
        _integer(target, "target_press_ns", start)
        duration = _integer(record["duration_ns"], "duration_ns", 1 if valid else 0)
        _require(target == end and duration == target - start, "Inconsistent press-to-press duration")
        target_point = _point(record["target_press_px"])
        if valid:
            _require(released is not None, "Valid attempt requires START release")
            _require(_inside_cell(target_point, trial.target_cell), "TARGET click outside its cell")
    trajectory = record.get("trajectory")
    _require(isinstance(trajectory, list) and len(trajectory) >= (2 if target is not None else 1),
             "Missing explicit trajectory endpoints")
    previous = 0
    for index, sample in enumerate(trajectory):
        _require(isinstance(sample, dict), "Trajectory sample must be an object")
        relative = _integer(sample.get("relative_time_ns"), "relative_time_ns", previous)
        _require(relative <= end - start, "Trajectory sample after attempt end")
        point = _point([sample.get("x_px"), sample.get("y_px")])
        kind = "start" if index == 0 else "target" if target is not None and index == len(trajectory) - 1 else "move"
        _require(sample.get("kind") == kind, "Invalid trajectory endpoint/kind")
        if index == 0:
            _require(relative == 0 and point == start_point, "Missing explicit START endpoint")
        elif kind == "target":
            _require(relative == target - start and point == target_point, "Missing explicit TARGET endpoint")
        if valid:
            _require(0 <= point[0] < GRID_WIDTH * CELL_SIZE_PX and
                     0 <= point[1] < GRID_HEIGHT * CELL_SIZE_PX, "Valid trajectory outside canvas")
        previous = relative


def validate_inputs(session, records, manifest):
    """Validate the complete collector stream before any fitting occurs.

    Includes warm-up coverage, retry order, contiguous per-trial attempt indices,
    counters, timestamps and endpoints. Invalid interruptions retain null target
    fields; valid slow observations have no upper duration or geometry cutoff.
    """
    _validate_session(session)
    by_id = {trial.trial_id: trial for trial in manifest.trials}
    accepted = {}
    invalid = []
    for record in records:
        _require(isinstance(record, dict) and type(record.get("valid")) is bool,
                 "Attempt must contain a boolean valid field")
        trial_id = record.get("trial_id")
        _require(isinstance(trial_id, str) and trial_id in by_id, "Unknown trial ID")
        _integer(record.get("attempt_index"), "attempt_index", 1)
        _validate_attempt(record, by_id[trial_id])
        if record["valid"]:
            _require(trial_id not in accepted, f"Duplicate accepted trial ID: {trial_id}")
            accepted[trial_id] = record
        else:
            invalid.append(record)
    _require(accepted.keys() == by_id.keys(), "Accepted coverage must exactly match all 408 frozen trials")
    cursor, attempt_index, previous_end = 0, 1, 0
    for record in records:
        _require(cursor < len(manifest.trials) and record["trial_id"] == manifest.trials[cursor].trial_id,
                 "Attempt order disagrees with frozen schedule/retry order")
        _require(record["attempt_index"] == attempt_index, "Noncontiguous attempt index")
        _require(record["start_press_ns"] >= previous_end, "Overlapping/nonmonotonic attempt timestamps")
        previous_end = record["end_ns"]
        if record["valid"]:
            cursor += 1
            attempt_index = 1
        else:
            attempt_index += 1
    _require(session["invalid_attempts"] == len(invalid), "Invalid-attempt counter mismatch")
    return [accepted[t.trial_id] for t in manifest.trials], invalid


def median_ns(values):
    """Exact integer/half-integer median, even beyond the working precision."""
    ordered = sorted(values)
    _require(bool(ordered), "Median requires observations")
    for value in ordered:
        _integer(value, "duration_ns", 1)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return Decimal(ordered[middle])
    total = ordered[middle - 1] + ordered[middle]
    return Decimal(f"{total // 2}.{5 if total % 2 else 0}")


def distance_and_log2(dx, dy):
    _integer(dx, "abs_dx")
    _integer(dy, "abs_dy")
    with localcontext(numeric_context()):
        distance = Decimal(dx * dx + dy * dy).sqrt()
        # ln(4)/ln(2) can round just below 2. Preserve mathematically exact
        # powers of two so such an artifact cannot tip a HALF_EVEN boundary.
        if distance == distance.to_integral_value():
            one_plus = int(distance) + 1
            if one_plus & (one_plus - 1) == 0:
                return distance, Decimal(one_plus.bit_length() - 1)
        return distance, (Decimal(1) + distance).ln() / Decimal(2).ln()


def _fit_floor_coefficient(c, xs, ys):
    """Global k>=0 optimum for validated positive Decimal observations.

    Breakpoints delimit quadratic regions with a fixed active set k*x_i>c.
    Compare all boundaries and feasible stationary points, including k=0.
    All observations enter each SSE, including those on the floor. Exact SSE
    ties select the smaller k; a flat optimum therefore selects zero. No
    tolerance, iterative convergence or clamping is used.
    """
    with localcontext(numeric_context()):
        bounds = sorted({Decimal(0)} | {c / x for x in xs})
        candidates = list(bounds)
        for index, lower in enumerate(bounds):
            upper = bounds[index + 1] if index + 1 < len(bounds) else None
            probe = (lower + upper) / 2 if upper is not None else 2 * lower
            active = [(x, y) for x, y in zip(xs, ys) if probe * x > c]
            if active:
                stationary = sum(x * y for x, y in active) / sum(x * x for x, _ in active)
                if stationary >= lower and (upper is None or stationary <= upper):
                    candidates.append(stationary)

        def score(k):
            residuals = [y - max(c, k * x) for x, y in zip(xs, ys)]
            return sum(r * r for r in residuals), k

        return min(candidates, key=score)


def fit_offset_medians(medians):
    """Fit Model C to the 15 nonzero medians; O00 fixes c. Input unit: ns.

    Return Decimal microseconds. Free-intercept and old additive anchored fits
    remain diagnostic, including when an additive slope would be negative.
    """
    _require(set(medians) == {offset[0] for offset in OFFSET_FAMILIES}, "Expected all 16 offset medians")
    with localcontext(numeric_context()):
        ys = [_decimal(medians[name]) / 1000 for name, _, _ in OFFSET_FAMILIES]
        _require(all(y > 0 for y in ys), "Offset medians must be positive")
        xs = [distance_and_log2(dx, dy)[1] for _, dx, dy in OFFSET_FAMILIES]
        c = ys[0]
        k = _fit_floor_coefficient(c, xs[1:], ys[1:])
        _require(c > 0 and k >= 0, "Floor fit requires c > 0 and k >= 0")
        residuals = [y - max(c, k * x) for x, y in zip(xs, ys)]
        sse = sum(r * r for r in residuals[1:])
        crossover = c / k if k else None
        # KEEP both existing additive diagnostics; neither supplies table costs.
        b = sum(x * (y - c) for x, y in zip(xs[1:], ys[1:])) / sum(x * x for x in xs[1:])
        x_mean, y_mean = sum(xs) / 16, sum(ys) / 16
        b_hat = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / sum((x - x_mean) ** 2 for x in xs)
        c_hat = y_mean - b_hat * x_mean
        additive_residuals = [y - (c + b * x) for x, y in zip(xs, ys)]
        return {
            "c_us": c, "k_us": k,
            "objective_sse_us2": sse,
            "crossover_x": crossover,
            "crossover_distance_cells": (crossover * Decimal(2).ln()).exp() - 1 if k else None,
            "crossover_status": "finite" if k else "no_finite_crossover_k_zero",
            "active_offset_ids": [name for (name, _, _), x in zip(OFFSET_FAMILIES[1:], xs[1:]) if k * x > c],
            "floor_offset_ids": [name for (name, _, _), x in zip(OFFSET_FAMILIES[1:], xs[1:]) if k * x <= c],
            "c_hat_us": c_hat, "b_hat_us": b_hat,
            "residual_mae_us": sum(abs(r) for r in residuals) / 16,
            "residual_rmse_us": (sse / 16).sqrt(),
            "nonzero_residual_metrics": {"count": 15, "mae_us": sum(abs(r) for r in residuals[1:]) / 15,
                                         "rmse_us": (sse / 15).sqrt()},
            "additive_anchored_diagnostic": {
                "authoritative": False, "c_us": c, "b_us": b, "model_formula": "T_us(d)=c_us+b_us*log2(1+d)",
                "observations": "15 nonzero offset medians for slope; O00 anchors intercept",
                "residual_definition": "observed median minus predicted median, us", "residual_metric_count": 16,
                "residual_mae_us": sum(abs(r) for r in additive_residuals) / 16,
                "residual_rmse_us": (sum(r * r for r in additive_residuals) / 16).sqrt(),
            },
        }


def _validate_table_shape(table):
    _require(isinstance(table, list) and len(table) == 30 and
             all(isinstance(row, list) and len(row) == 16 for row in table), "Timing table must be 30x16")
    for row in table:
        for tick in row:
            _integer(tick, "timing tick", 1)


def validate_timing_table(table, c_us):
    _validate_table_shape(table)
    with localcontext(numeric_context()):
        _require(table[0][0] == int(_decimal(c_us).to_integral_value(rounding=ROUND_HALF_EVEN)),
                 "T[0][0] must equal rounded anchored c")
    by_distance = {}
    for dx, row in enumerate(table):
        for dy, tick in enumerate(row):
            squared = dx * dx + dy * dy
            _require(squared not in by_distance or by_distance[squared] == tick,
                     "Equal distances must have equal timing ticks")
            by_distance[squared] = tick
    ticks = [by_distance[d] for d in sorted(by_distance)]
    _require(all(a <= b for a, b in zip(ticks, ticks[1:])), "Timing table decreases with physical distance")


def build_timing_table(c_us, k_us):
    with localcontext(numeric_context()):
        c, k = _decimal(c_us), _decimal(k_us)
        _require(c > 0 and k >= 0, "Timing table requires c > 0 and k >= 0")
        table = [[int(max(c, k * distance_and_log2(dx, dy)[1]).to_integral_value(rounding=ROUND_HALF_EVEN))
                  for dy in range(16)] for dx in range(30)]
        validate_timing_table(table, c)
        return table


def canonical_timing_table_bytes(table):
    """ASCII positive integers, dx-major/dy-minor, commas, no whitespace/newline."""
    _validate_table_shape(table)
    return ",".join(str(tick) for row in table for tick in row).encode("ascii")


def _duration_summary(records):
    values = [r["duration_ns"] for r in records]
    return {"count": len(values), "min_ns": min(values), "max_ns": max(values),
            "median_ns": median_ns(values), "mean_ns": Decimal(sum(values)) / len(values)}


def _click_offset(point, cell):
    dx, dy = [p - (Decimal(c) + Decimal("0.5")) * CELL_SIZE_PX for p, c in zip(point, cell)]
    return {"dx_px": dx, "dy_px": dy, "radius_px": (dx * dx + dy * dy).sqrt()}


def _trial_geometry(record):
    points = [(s["x_px"], s["y_px"]) for s in record["trajectory"]]
    points = [tuple(_decimal(v) for v in point) for point in points]
    length = sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2).sqrt() for a, b in zip(points, points[1:]))
    ideal = distance_and_log2(record["abs_dx"], record["abs_dy"])[0] * CELL_SIZE_PX
    return {
        "trial_id": record["trial_id"], "offset_id": record["offset_id"],
        "start_offset_from_center": _click_offset(_point(record["start_press_px"]), record["start_cell"]),
        "target_offset_from_center": _click_offset(_point(record["target_press_px"]), record["target_cell"]),
        "sampled_path_length_logical_px": length,
        "ideal_center_distance_logical_px": ideal,
        "path_ratio": length / ideal if ideal else None,
    }


def _build_outputs(session, accepted, invalid, provenance):
    official = [record for record in accepted if record["phase"] == OFFICIAL]
    groups = {name: [r for r in official if r["offset_id"] == name] for name, _, _ in OFFSET_FAMILIES}
    _require(len(official) == 384 and all(len(group) == 24 for group in groups.values()),
             "Fitting requires 384 official attempts and 24 per offset")
    medians = {name: median_ns([r["duration_ns"] for r in group]) for name, group in groups.items()}
    fit = fit_offset_medians(medians)
    c, k = fit["c_us"], fit["k_us"]
    table = build_timing_table(c, k)
    table_sha = hashlib.sha256(canonical_timing_table_bytes(table)).hexdigest()
    profile = {
        "physical_profile_version": 1, "schema_version": 1, **provenance,
        "grid_width": 30, "grid_height": 16, "cell_size_px": 28,
        "distance_unit": "cell_width", "timing_unit": "us", "timing_tick_unit": "1_us",
        "table_dimensions": [30, 16], "table_order": "dx_major_dy_minor",
        "table_encoding": "ASCII decimal integers, comma-separated, no whitespace or trailing comma",
        "canonical_chord_input": "LEFT", "canonical_chord_action": "LEFT_CLICK",
        "canonical_chord_target": "revealed_clue",
        "model_id": MODEL_ID, "model_formula": MODEL_FORMULA,
        "parameter_semantics": PARAMETER_SEMANTICS, "physical_execution": PHYSICAL_EXECUTION,
        "action_cost_scope": "common OPEN/FLAG/CHORD execution model; pooled button transitions",
        "fitted_c_us": c, "fitted_k_us": k, "numeric_contract": NUMERIC_CONTRACT,
        "runtime_cost_source": "timing_table_us; do not regenerate from fitted parameters",
        "timing_table_us": table, "table_sha256": table_sha,
    }
    offsets = []
    predictions = {}
    for name, dx, dy in OFFSET_FAMILIES:
        distance, x = distance_and_log2(dx, dy)
        predictions[name] = max(c, k * x)
        offsets.append({"offset_id": name, "abs_dx": dx, "abs_dy": dy,
                        "distance_cells": distance, "log2_one_plus_distance": x,
                        **_duration_summary(groups[name]), "median_us": medians[name] / 1000,
                        "predicted_median_us": predictions[name],
                        "residual_us": medians[name] / 1000 - predictions[name]})
    transitions = []
    offset_transitions = []
    for start, target in BUTTON_TRANSITIONS:
        subset = [r for r in official if (r["start_button"], r["target_button"]) == (start, target)]
        transitions.append({"start_button": start, "target_button": target, **_duration_summary(subset)})
        for name, _, _ in OFFSET_FAMILIES:
            summary = _duration_summary([r for r in subset if r["offset_id"] == name])
            offset_transitions.append({"offset_id": name, "start_button": start, "target_button": target,
                                       **summary, "median_residual_us": summary["median_ns"] / 1000 - predictions[name]})
    orientations = defaultdict(list)
    for record in official:
        orientations[(record["offset_id"], record["dx"], record["dy"])].append(record)
    orientation_report = []
    for (name, dx, dy), subset in sorted(orientations.items()):
        summary = _duration_summary(subset)
        orientation_report.append({"offset_id": name, "dx": dx, "dy": dy, **summary,
                                   "median_residual_us": summary["median_ns"] / 1000 - predictions[name]})
    geometry = [_trial_geometry(r) for r in official]
    ratios = [item["path_ratio"] for item in geometry if item["path_ratio"] is not None]
    sorted_offsets = sorted(offsets, key=lambda o: o["abs_dx"] ** 2 + o["abs_dy"] ** 2)
    decreases = [{"nearer": a["offset_id"], "farther": z["offset_id"]}
                 for a, z in zip(sorted_offsets, sorted_offsets[1:])
                 if a["distance_cells"] < z["distance_cells"] and a["median_ns"] > z["median_ns"]]
    report = {
        "analysis_report_version": 1, "provenance": provenance, "session_metadata": session,
        "numeric_contract": NUMERIC_CONTRACT,
        "accepted_warmup_count": sum(r["phase"] == WARMUP for r in accepted),
        "accepted_official_count": len(official), "invalid_attempt_count": len(invalid),
        "invalid_reason_counts": dict(sorted(Counter(r["invalid_reason"] for r in invalid).items())),
        "invalid_attempts": [{key: r[key] for key in ("trial_id", "phase", "attempt_index", "invalid_reason",
                                                     "start_press_ns", "start_release_ns", "target_press_ns",
                                                     "duration_ns", "end_ns")} for r in invalid],
        "fitting_input": "24 accepted official durations per offset; pooled transitions/orientations; no outlier rejection",
        "offsets": offsets,
        "authoritative_fit": {
            "model_id": MODEL_ID, "model_formula": MODEL_FORMULA, "c_us": c, "k_us": k,
            "parameter_semantics": PARAMETER_SEMANTICS,
            "observations": "c = O00 median; all 15 nonzero offset medians in the k objective; 24 official trials per median",
            "method": "global piecewise-quadratic enumeration; exact equal-SSE ties select smaller k",
            "objective": "sum_i (M_i-max(c,k*x_i))^2 over O01..O15; x_i=log2(1+d_i)",
            "objective_sse_us2": fit["objective_sse_us2"],
            "active_offset_ids": fit["active_offset_ids"], "floor_offset_ids": fit["floor_offset_ids"],
            "crossover_x": fit["crossover_x"], "crossover_distance_cells": fit["crossover_distance_cells"],
            "crossover_status": fit["crossover_status"],
            "residual_definition": "observed median minus predicted median, us",
            "residual_metric_count": 16, "residual_mae_us": fit["residual_mae_us"],
            "residual_rmse_us": fit["residual_rmse_us"], "nonzero_residual_metrics": fit["nonzero_residual_metrics"],
            "table_sha256": table_sha,
        },
        "additive_anchored_diagnostic": fit["additive_anchored_diagnostic"],
        "free_intercept_diagnostic": {"authoritative": False, "observations": "all 16 offset medians",
                                      "model_formula": "T_us(d)=c_hat_us+b_hat_us*log2(1+d)",
                                      "purpose": "diagnose the additive/intercept assumption; never supplies runtime costs",
                                      "c_hat_us": fit["c_hat_us"], "b_hat_us": fit["b_hat_us"],
                                      "c_hat_minus_c_us": fit["c_hat_us"] - c,
                                      "b_hat_minus_b_us": fit["b_hat_us"] - fit["additive_anchored_diagnostic"]["b_us"],
                                      "b_hat_minus_b_reference": "additive_anchored_diagnostic.b_us",
                                      "b_hat_minus_k_us": fit["b_hat_us"] - k},
        "button_transitions": transitions, "offset_button_transitions": offset_transitions,
        "orientations": orientation_report,
        "shape_sanity": {
            "table_dimensions": [30, 16], "table_entries": 480, "all_positive_integer_ticks": True,
            "nondecreasing_by_physical_distance": True, "t00_us": table[0][0], "table_sha256": table_sha,
            "observed_adjacent_median_decreases": decreases,
            "equal_distance_families": {"offset_ids": ["O09", "O10"], "offsets": [[8, 6], [10, 0]],
                                        "distance_cells": "10", "observed_median_difference_us": (medians["O09"] - medians["O10"]) / 1000,
                                        "predicted_median_us": predictions["O09"],
                                        "equal_prediction": predictions["O09"] == predictions["O10"],
                                        "equal_table_ticks": table[8][6] == table[10][0]},
        },
        "geometry_diagnostics": {
            "population": "accepted OFFICIAL only; no filtering or effect on fitting",
            "coordinate_unit": "qt_logical_px", "ratio_unit": "dimensionless",
            "path_ratio_definition": "sampled ACTIVE polyline length / ideal straight cell-center distance",
            "interpretation": "Sampling can miss motion; actual clicks can differ from cell centers. Ratio may be below 1; it does not define duration or validity.",
            "path_ratio_count": len(ratios), "zero_distance_excluded_count": len(geometry) - len(ratios),
            "path_ratio_min": min(ratios), "path_ratio_max": max(ratios),
            "path_ratio_mean": sum(ratios) / len(ratios), "trials": geometry,
        },
        "review_policy": "Only structural acceptance is enforced. Fit quality and all diagnostics require human review; no quality thresholds.",
    }
    return _json_numbers(report), _json_numbers(profile)


def analyze_files(session_path, trials_path, *, manifest_path=FROZEN_MANIFEST_PATH):
    """Analyze a canonically named session pair, from any parent directories."""
    manifest = load_frozen_manifest(manifest_path)
    session_path, trials_path = Path(session_path), Path(trials_path)
    session_bytes, trials_bytes = session_path.read_bytes(), trials_path.read_bytes()
    session = _read_json(session_bytes)
    records = []
    for line_number, line in enumerate(trials_bytes.splitlines(), 1):
        _require(bool(line.strip()), f"Blank JSONL record at line {line_number}")
        try:
            records.append(_read_json(line, decimal_pixels=True))
        except ValueError as error:
            raise ValueError(f"Invalid JSONL record at line {line_number}: {error}") from error
    accepted, invalid = validate_inputs(session, records, manifest)
    _require(session_path.name == f"calibration_session_{session['session_id']}.json",
             "Session filename must match session_id exactly")
    _require(trials_path.name == f"calibration_trials_{session['session_id']}.jsonl",
             "Trials filename must match session_id exactly")
    provenance = {
        "source_protocol_version": PROTOCOL_VERSION, "source_manifest_sha256": FROZEN_MANIFEST_SHA256,
        "source_session_id": session["session_id"],
        "source_session_filename": session_path.name,
        "source_trials_filename": trials_path.name,
        "source_session_sha256": hashlib.sha256(session_bytes).hexdigest(),
        "source_trials_sha256": hashlib.sha256(trials_bytes).hexdigest(),
    }
    with localcontext(numeric_context()):
        return _build_outputs(session, accepted, invalid, provenance)


def write_outputs(report, profile, report_path, profile_path):
    """Exclusive creation; reserve both paths before writing either payload.

    On an ordinary I/O failure remove only files created by this call. This is
    not a crash-atomic transaction or a resume/checkpoint mechanism.
    """
    paths = [Path(report_path), Path(profile_path)]
    _require(paths[0].resolve() != paths[1].resolve(), "Report and profile paths must differ")
    for path in paths:
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Output already exists: {path}")
    payloads = [canonical_output_bytes(report), canonical_output_bytes(profile)]
    created = []
    try:
        with ExitStack() as stack:
            streams = []
            for path in paths:
                streams.append(stack.enter_context(path.open("xb")))
                created.append(path)
            for stream, payload in zip(streams, payloads):
                stream.write(payload)
                stream.flush()
    except OSError:
        for path in created:
            path.unlink()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--trials", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report, profile = analyze_files(args.session, args.trials)
        write_outputs(report, profile, args.report, args.profile)
    except (OSError, ValueError, DecimalException) as error:
        print(f"Calibration analysis failed: {error}", file=sys.stderr)
        return 1
    print(f"Report: {args.report}\nProfile: {args.profile}\nTiming table SHA-256: {profile['table_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
