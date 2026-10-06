"""Read-only final Replay Validation V1.1 corpus analysis.

Reads the 30 canonical JSON outputs from:
  results/stage3_replay_validation/final/validation_v1_1_final_audit

It does not open videos, modify metadata, refit the physical model, or apply
a pass/fail threshold. All authoritative arithmetic is exact Fraction math;
decimal percentages printed to the console are presentation only.

Run from the repository root:
  python results/stage3_replay_validation/analyze_final_validation.py
"""

from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
import json
from pathlib import Path
from statistics import median
import sys


ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = ROOT / "results" / "stage3_replay_validation" / "final" / "validation_v1_1_final_audit"

EXPECTED = (
    [f"STD_R{i:03d}" for i in range(1, 11)]
    + [f"STD_R{i:03d}" for i in range(21, 31)]
    + [f"NF_R{i:03d}" for i in range(1, 6)]
    + [f"NF_R{i:03d}" for i in range(26, 31)]
)

PROFILE_SHA256 = "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b"
TABLE_SHA256 = "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b"
MODEL_ID = "overlap_floor_log2_distance_v1"

CLASSES = ("MODEL_BELOW", "FRAME_AMBIGUOUS", "MODEL_ABOVE")


def frac(obj) -> Fraction:
    if not isinstance(obj, dict) or set(obj) != {"numerator", "denominator"}:
        raise ValueError(f"Invalid rational object: {obj!r}")
    return Fraction(obj["numerator"], obj["denominator"])


def pct(value: Fraction) -> str:
    return f"{float(value) * 100:.3f}%"


def seconds(us: int) -> str:
    return f"{us / 1_000_000:.6f}"


def load_records():
    if not AUDIT_DIR.is_dir():
        raise SystemExit(f"Audit directory not found: {AUDIT_DIR}")

    records = []
    for stem in EXPECTED:
        path = AUDIT_DIR / f"{stem}.validation.json"
        if not path.is_file():
            raise SystemExit(f"Missing audit JSON: {path}")
        data = json.loads(path.read_text(encoding="ascii"))
        records.append((stem, data))
    return records


def validate_corpus(records):
    if len(records) != 30:
        raise ValueError(f"Expected 30 records, got {len(records)}")

    selected_by_category = defaultdict(list)
    replacements = []

    for stem, d in records:
        if d["replay_status"] != "RECONSTRUCTED":
            raise ValueError(f"{stem}: status={d['replay_status']}")
        if d["reconstructed_event_count"] != d["displayed_final_click_count"]:
            raise ValueError(f"{stem}: event count mismatch")
        if d["unresolved_target_count"] != 0:
            raise ValueError(f"{stem}: unresolved targets")
        if d["modeled_physical_time_us"] is None:
            raise ValueError(f"{stem}: null authoritative P")
        if d["capture_declaration_status"] != "SUPPLIED_COMPATIBLE":
            raise ValueError(f"{stem}: incompatible capture declaration")
        if d["physical_profile"]["whole_profile_sha256"] != PROFILE_SHA256:
            raise ValueError(f"{stem}: wrong physical profile SHA")
        if d["physical_profile"]["timing_table_sha256"] != TABLE_SHA256:
            raise ValueError(f"{stem}: wrong timing table SHA")
        if d["physical_profile"]["model_id"] != MODEL_ID:
            raise ValueError(f"{stem}: wrong model id")
        if d["transition_count"] != len(d["transitions"]):
            raise ValueError(f"{stem}: transition count mismatch")
        if d["transition_count"] != d["reconstructed_event_count"] - 1:
            raise ValueError(f"{stem}: incomplete transitions")
        if d["review_flags"]:
            raise ValueError(f"{stem}: unexpected review flags {d['review_flags']}")

        selected_by_category[d["category"]].append(d["selected_rank"])
        if d.get("replacement_of") is not None:
            replacements.append((stem, d["selected_rank"], d["replacement_of"]))

    for category, ranks in selected_by_category.items():
        if len(ranks) != len(set(ranks)):
            raise ValueError(f"{category}: duplicate selected ranks {ranks}")
        if 15 in ranks:
            raise ValueError(f"{category}: pilot-only rank 15 present in FINAL corpus")

    return replacements


def summarize(label, items):
    games = len(items)
    p_sum = sum(d["modeled_physical_time_us"] for _, d in items)
    h_sum = sum(d["displayed_human_time_us"] for _, d in items)
    game_ratios = [Fraction(d["modeled_physical_time_us"], d["displayed_human_time_us"]) for _, d in items]
    transition_count = sum(d["transition_count"] for _, d in items)
    counts = Counter()
    games_with_above = 0

    for _, d in items:
        counts.update(d["comparison_counts"])
        if d["comparison_counts"]["MODEL_ABOVE"]:
            games_with_above += 1

    print(f"\n=== {label} ===")
    print(f"games                    : {games}")
    print(f"transitions              : {transition_count}")
    print(f"sum P / sum H            : {pct(Fraction(p_sum, h_sum))}  ({seconds(p_sum)}s / {seconds(h_sum)}s)")
    print(f"mean per-game P/H        : {pct(sum(game_ratios, Fraction(0)) / games)}")
    print(f"median per-game P/H      : {pct(median(game_ratios))}")
    print(f"min / max per-game P/H   : {pct(min(game_ratios))} / {pct(max(game_ratios))}")
    print(f"games with P < H         : {sum(d['modeled_physical_time_us'] < d['displayed_human_time_us'] for _, d in items)}/{games}")
    print(f"games with MODEL_ABOVE   : {games_with_above}/{games}")

    for klass in CLASSES:
        c = counts[klass]
        rate = Fraction(c, transition_count) if transition_count else Fraction(0)
        print(f"{klass:25}: {c:5d} / {transition_count:5d}  {pct(rate)}")


def per_game_table(records):
    print("\n=== PER GAME ===")
    print("slot       rank repl events   P(s)       H(s)       P/H      below ambig above")
    for stem, d in records:
        ratio = Fraction(d["modeled_physical_time_us"], d["displayed_human_time_us"])
        cc = d["comparison_counts"]
        repl = "-" if d.get("replacement_of") is None else str(d["replacement_of"])
        print(
            f"{stem:10} {d['selected_rank']:>4} {repl:>4} "
            f"{d['reconstructed_event_count']:>6} "
            f"{d['modeled_physical_time_us']/1_000_000:>10.6f} "
            f"{d['displayed_human_time_us']/1_000_000:>10.6f} "
            f"{float(ratio):>8.4f} "
            f"{cc['MODEL_BELOW']:>6} {cc['FRAME_AMBIGUOUS']:>5} {cc['MODEL_ABOVE']:>5}"
        )


def transition_diagnostics(records):
    groups = defaultdict(lambda: {
        "n": 0, "classes": Counter(), "excess_total": Fraction(0), "excess_max": Fraction(0)
    })
    above_rows = []

    for stem, d in records:
        for t in d["transitions"]:
            key = (t["dx"], t["dy"], t["predicted_us"])
            g = groups[key]
            g["n"] += 1
            g["classes"][t["comparison_class"]] += 1
            if t["comparison_class"] == "MODEL_ABOVE":
                high = frac(t["observed_high_us"])
                excess = Fraction(t["predicted_us"]) - high
                g["excess_total"] += excess
                g["excess_max"] = max(g["excess_max"], excess)
                above_rows.append((
                    excess, stem, t["from_event_index"], t["to_event_index"],
                    t["dx"], t["dy"], t["predicted_us"], t["frame_delta"], high
                ))

    above_rows.sort(reverse=True)

    print("\n=== MODEL_ABOVE DISTANCE GROUPS ===")
    rows = []
    for (dx, dy, predicted), g in groups.items():
        above = g["classes"]["MODEL_ABOVE"]
        if above:
            rows.append((
                Fraction(above, g["n"]), above, g["n"], g["excess_max"],
                dx, dy, predicted, g["classes"]["FRAME_AMBIGUOUS"], g["classes"]["MODEL_BELOW"]
            ))
    rows.sort(reverse=True)

    if not rows:
        print("none")
    else:
        print(" dx  dy predicted_us    n above  rate     ambig below  max_excess_us")
        for rate, above, n, max_excess, dx, dy, predicted, ambig, below in rows:
            print(
                f"{dx:3d} {dy:3d} {predicted:12d} {n:4d} {above:5d} "
                f"{float(rate):7.3f} {ambig:7d} {below:5d} {float(max_excess):14.3f}"
            )

    print("\n=== LARGEST MODEL_ABOVE EXCESSES ===")
    if not above_rows:
        print("none")
    else:
        print("slot       from->to   dx dy predicted_us frame_delta excess_over_high_us")
        for excess, stem, a, b, dx, dy, predicted, frame_delta, high in above_rows[:20]:
            print(
                f"{stem:10} {a:4d}->{b:<4d} {dx:2d} {dy:2d} "
                f"{predicted:12d} {frame_delta:11d} {float(excess):19.3f}"
            )


def main():
    records = load_records()
    replacements = validate_corpus(records)

    print("FINAL REPLAY VALIDATION V1.1 ANALYSIS")
    print(f"audit directory          : {AUDIT_DIR}")
    print(f"records                  : {len(records)}")
    print(f"replacements             : {len(replacements)}")
    for stem, selected, original in replacements:
        print(f"  {stem}: original {original} -> selected {selected}")
    print(f"physical profile SHA-256 : {PROFILE_SHA256}")
    print(f"timing table SHA-256     : {TABLE_SHA256}")
    print(f"model id                 : {MODEL_ID}")

    per_game_table(records)

    standard = [(s, d) for s, d in records if d["category"] == "STANDARD"]
    no_flag = [(s, d) for s, d in records if d["category"] == "NO_FLAG"]

    summarize("STANDARD", standard)
    summarize("NO_FLAG", no_flag)
    summarize("OVERALL", records)

    transition_diagnostics(records)


if __name__ == "__main__":
    try:
        main()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Analysis rejected: {exc}", file=sys.stderr)
        raise SystemExit(2)
