"""Read-only report for the one accepted official Stage-2/Stage-3 evidence family.

No execution, replay, board reconstruction or all-game action evaluation occurs.
Source authentication/pairing precedes selection; only unique selected games'
actions are loaded. Connections close and sources are rechecked before publishing.
"""

import argparse
from collections import Counter
from contextlib import ExitStack, closing
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

# Support direct invocation from scripts/ without installing the project.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import benchmark_modeled_time as modeled
import benchmark_statistics as statistics
from core_engine import Action, GameStatus
import representative_boards as representatives
from telemetry_model import ActionEvent, GameRecord, InferenceCategory
import telemetry_repository as repository
import telemetry_schema as schema
import timeline_analytics as timeline


EXPECTED_HASHES = {
    "stage2": "8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f",
    "stage3": "b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e",
    "comparison": "f31226a660eda02a804ee41c66f233513fd950cac6f6123f36bf62578fbf5979",
    "result": "09f228ee9a8ec96a934dbb94656a7cd6f03c7987640df267f5fd6818dd007cc0",
}
PREFIX_GAMES = 100000
EXPECTED_OUTCOMES = {"ww": 37702, "wl": 0, "lw": 0, "ll": 62298}
SOURCE_ROLES = {
    "stage2": "Stage-2 preserved accepted analysis copy",
    "stage3": "Stage-3 preserved accepted analysis copy",
    "comparison": "Accepted G4 comparison",
    "result": "Accepted G4 gate result",
}
MODEL_FIELDS = (
    "physical_model_id", "physical_profile_version", "physical_profile_sha256",
    "timing_table_sha256", "timing_unit", "initial_cursor",
)
CATEGORY_TEXT = {
    representatives.ExemplarCategory.MAX_STAGE3_WW_ADVANTAGE: (
        "Maximum Stage-3 WW advantage", "Minimum negative delta_us; tie: lowest game_index."),
    representatives.ExemplarCategory.MEDIAN_DELTA_WW: (
        "Median-delta WW exemplar", "Sort ALL WW by (delta_us, game_index); lower median index (N - 1) // 2."),
    representatives.ExemplarCategory.CLOSEST_TO_ZERO_STAGE3_WW_ADVANTAGE: (
        "Closest-to-zero Stage-3 WW advantage", "Greatest negative delta_us; tie: lowest game_index. No near-tie tolerance is defined."),
    representatives.ExemplarCategory.STAGE2_WW_ADVANTAGE: (
        "Stage-2 WW advantage", "Largest positive delta_us; tie: lowest game_index."),
    representatives.ExemplarCategory.EXACT_WW_TIE: (
        "Exact WW tie", "delta_us == 0; lowest game_index."),
    representatives.ExemplarCategory.WL: ("WL", "Lowest game_index in WL."),
    representatives.ExemplarCategory.LW: ("LW", "Lowest game_index in LW."),
    representatives.ExemplarCategory.LL: ("LL", "Lowest game_index in LL."),
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _hash_file(path):
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SourceState:
    role: str
    path: Path
    size_bytes: int
    mtime_ns: int
    sha256: str
    sidecars: tuple[str, ...]


def _source_state(role, path):
    path = Path(path).resolve(strict=True)
    before = path.stat()
    digest = _hash_file(path)
    after = path.stat()
    _require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
             f"Source changed while hashing: {role}.")
    sidecars = tuple(
        suffix for suffix in ("-wal", "-shm", "-journal")
        if role in ("stage2", "stage3") and Path(str(path) + suffix).exists()
    )
    return SourceState(role, path, after.st_size, after.st_mtime_ns, digest, sidecars)


def _authenticate_sources(paths):
    _require(set(paths) == set(EXPECTED_HASHES), "Exactly four source roles are required.")
    sources = tuple(_source_state(role, paths[role]) for role in EXPECTED_HASHES)
    for source in sources:
        _require(source.sha256 == EXPECTED_HASHES[source.role], f"SHA-256 mismatch: {source.role}.")
        _require(not source.sidecars, f"Preserved DB has unexpected sidecars: {source.role}.")
    return sources


def _verify_stability(sources):
    for source in sources:
        _require(_source_state(source.role, source.path) == source,
                 f"Source stability/sidecar check failed: {source.role}.")


def _discover_run(connection, stage, evaluation):
    matches = []
    for run in statistics.list_benchmark_runs(connection):
        if run.solver_stage != stage:
            continue
        try:
            modeled.validate_run_identity(connection, run.run_id, solver_stage=stage, evaluation=evaluation)
        except modeled.ModeledTimeValidationError:
            continue
        coverage = statistics.get_run_coverage(connection, run.run_id)
        if (coverage.official_eligible and coverage.exact_requested_prefix
                and coverage.requested_games == coverage.processed_games
                == coverage.stored_game_count == PREFIX_GAMES):
            matches.append((run, coverage))
    _require(len(matches) == 1, f"Expected exactly one accepted {stage} run; found {len(matches)}.")
    return matches[0]


_RESULTS = {schema.GAME_RESULT_WIN: "WIN", schema.GAME_RESULT_LOSS: "LOSS"}
_ACTIONS = {schema.ACTION_OPEN: Action.OPEN, schema.ACTION_FLAG: Action.FLAG, schema.ACTION_CHORD: Action.CHORD}
_STATUSES = {
    schema.STATUS_AFTER_PLAYING: GameStatus.PLAYING,
    schema.STATUS_AFTER_WON: GameStatus.WON, schema.STATUS_AFTER_LOST: GameStatus.LOST,
}
_INFERENCES = {
    schema.INFERENCE_LOCAL_DETERMINISTIC: InferenceCategory.LOCAL_DETERMINISTIC,
    schema.INFERENCE_GLOBAL_CERTAINTY: InferenceCategory.GLOBAL_CERTAINTY,
    schema.INFERENCE_PROBABILITY_GUESS: InferenceCategory.PROBABILITY_GUESS,
}


def _decode_enum(value, mapping):
    _require(type(value) is int and value in mapping, "Invalid persisted enum value.")
    return mapping[value]


def _load_summaries(connection, run_id):
    # Each database is read independently. No join can hide missing identities.
    rows = connection.execute(
        "SELECT game_index, seed, board_fingerprint, first_click_x, first_click_y, result "
        "FROM games WHERE run_id = ? ORDER BY game_index", (run_id,),
    ).fetchall()
    _require(len(rows) == PREFIX_GAMES, "Summary prefix count mismatch.")
    summaries = {}
    for index, row in enumerate(rows):
        _require(type(row["game_index"]) is int and row["game_index"] == index,
                 "Summary indices must be the exact requested prefix.")
        values = dict(row)
        values["result"] = _decode_enum(values["result"], _RESULTS)
        summaries[index] = values
    return summaries


def _identity(values):
    return tuple(values[name] for name in ("game_index", "seed", "board_fingerprint", "first_click_x", "first_click_y"))


def _paired_outcomes(left, right):
    _require(left.keys() == right.keys(), "Independent summary prefixes differ.")
    outcomes = Counter({key: 0 for key in EXPECTED_OUTCOMES})
    ww = set()
    for index in left:
        _require(_identity(left[index]) == _identity(right[index]), "Paired summary identity mismatch.")
        _require((left[index]["first_click_x"], left[index]["first_click_y"]) == (0, 0),
                 "Noncanonical summary first click.")
        pair = left[index]["result"][0].lower() + right[index]["result"][0].lower()
        outcomes[pair] += 1
        if pair == "ww":
            ww.add(index)
    _require(dict(outcomes) == EXPECTED_OUTCOMES, "Accepted outcome reconciliation failed.")
    return dict(outcomes), ww


def _model_identity(evaluation):
    return {name: list(evaluation.initial_cursor) if name == "initial_cursor" else getattr(evaluation, name)
            for name in MODEL_FIELDS}


def _g4_deltas(comparison, result, sources, runs, evaluation, outcomes, ww):
    """Validate sealed G4 provenance and exact WW facts, without ranking them."""
    by_role = {source.role: source for source in sources}
    _require(comparison["scope"] == "official_100000_prefix_comparison"
             and comparison["prefix_games"] == PREFIX_GAMES and comparison["require_official"] is True,
             "G4 comparison scope mismatch.")
    _require(comparison["evaluation"] == _model_identity(evaluation), "G4 Model C identity mismatch.")
    for side, run, kind, label in zip(
        ("left", "right"), runs, ("post_hoc_frozen_model_c", "declared_frozen_model_c"),
        ("stage2-analysis-copy", "stage3-analysis-copy"),
    ):
        _require(comparison[side] == dict(
            run_id=run.run_id, solver_stage=run.solver_stage,
            telemetry_schema_version=run.telemetry_schema_version, evaluation_kind=kind, label=label,
        ), f"G4 {side} source identity mismatch.")
    _require(comparison["outcomes"] == outcomes, "G4 outcome totals mismatch.")
    for stage, wins in (("stage2", outcomes["ww"] + outcomes["wl"]),
                        ("stage3", outcomes["ww"] + outcomes["lw"])):
        _require(comparison[stage + "_wins"] == wins
                 and comparison[stage + "_losses"] == PREFIX_GAMES - wins
                 and Fraction(comparison[stage + "_win_rate"]) == Fraction(wins, PREFIX_GAMES),
                 "G4 per-stage outcomes mismatch.")
    primary = comparison["primary"]
    entries = primary["paired_deltas_us"]
    _require(isinstance(entries, list) and len(entries) == len(ww), "G4 WW count mismatch.")
    deltas = {}
    for entry in entries:
        _require(isinstance(entry, list) and len(entry) == 2
                 and all(type(value) is int for value in entry), "G4 delta entries require exact integers.")
        index, delta = entry
        _require(index not in deltas, "Duplicate G4 WW index.")
        deltas[index] = delta
    _require(deltas.keys() == ww, "G4 WW index set mismatch.")
    _require(type(primary["total_delta_us"]) is int
             and sum(deltas.values()) == primary["total_delta_us"]
             == primary["stage3_total_us"] - primary["stage2_total_us"], "G4 total delta mismatch.")
    _require(primary["game_count"] == len(ww)
             and primary["stage3_faster"] == sum(value < 0 for value in deltas.values())
             and primary["stage2_faster"] == sum(value > 0 for value in deltas.values())
             and primary["ties"] == sum(value == 0 for value in deltas.values()), "G4 delta counts mismatch.")
    _require(result["gate"] == "G4" and result["status"] == "PASS", "G4 acceptance mismatch.")
    _require(result["official_comparison"] == {
        "path": "comparison-001.json", "sha256": by_role["comparison"].sha256,
    }, "G4 comparison provenance mismatch.")
    _require(result["comparison_api"] == dict(
        name="benchmark_comparison.compare_stage2_stage3_sources",
        left_run_id=runs[0].run_id, right_run_id=runs[1].run_id,
        left_source_label="stage2-analysis-copy", right_source_label="stage3-analysis-copy",
        prefix_games=PREFIX_GAMES, require_official=True,
    ), "G4 API provenance mismatch.")
    _require(result["paired_delta_count"] == len(ww), "G4 result WW count mismatch.")
    for phase in ("preservation_entry", "preservation_exit"):
        for role in ("stage2", "stage3"):
            source = by_role[role]
            name = role + "-analysis.sqlite3"
            preserved = result[phase][role + "_copy"]
            _require(preserved[name] == dict(present=True, sha256=source.sha256, size_bytes=source.size_bytes),
                     "G4 preserved source provenance mismatch.")
            _require(all(preserved[name + suffix] == {"present": False}
                         for suffix in ("-wal", "-shm", "-journal")), "G4 preserved sidecar mismatch.")
    summary = {key: comparison[key] for key in (
        "diagnostic_stage2_total_us", "diagnostic_stage3_total_us", "outcomes",
        "stage2_losses", "stage2_win_rate", "stage2_wins", "stage3_losses", "stage3_win_rate", "stage3_wins",
    )}
    summary["primary"] = {key: value for key, value in primary.items() if key != "paired_deltas_us"}
    _require(result["summary"] == summary, "G4 result/comparison summary mismatch.")
    return deltas


def _load_game(connection, run, index, summary, evaluation):
    """The only detailed-action query: one explicitly selected game_id at a time."""
    row = connection.execute("SELECT * FROM games WHERE run_id = ? AND game_index = ?", (run.run_id, index)).fetchone()
    _require(row is not None, "Selected game is missing.")
    values = {field.name: row[field.name] for field in fields(GameRecord)}
    values["result"] = _decode_enum(values["result"], _RESULTS)
    _require(type(values["had_probability_guess"]) is int and values["had_probability_guess"] in (0, 1),
             "Invalid persisted guess boolean.")
    values["had_probability_guess"] = bool(values["had_probability_guess"])
    _require(all(values[name] == value for name, value in summary.items()), "Selected summary identity changed.")
    record = GameRecord(**values)
    events = []
    for event in connection.execute(
        "SELECT * FROM action_events WHERE game_id = ? ORDER BY action_index", (row["game_id"],),
    ):
        values = {field.name: event[field.name] for field in fields(ActionEvent)}
        values["action_type"] = _decode_enum(values["action_type"], _ACTIONS)
        values["status_after"] = _decode_enum(values["status_after"], _STATUSES)
        if values["inference_category"] is not None:
            values["inference_category"] = _decode_enum(values["inference_category"], _INFERENCES)
        for name in ("target_mine_probability", "minimum_available_mine_probability"):
            values[name] = repository.decode_probability(values[name])
        events.append(ActionEvent(**values))
    return timeline.project_timeline(record, tuple(events), width=run.width, height=run.height, evaluation=evaluation)


@dataclass(frozen=True)
class ReportData:
    sources: tuple[SourceState, ...]
    runs: tuple[statistics.BenchmarkRunSummary, ...]
    coverage: tuple[statistics.RunCoverage, ...]
    evaluation: modeled.ModelCEvaluation
    selection: tuple[representatives.CategoryExemplar, ...]
    games: tuple[tuple[timeline.TimelineAnalytics, timeline.TimelineAnalytics], ...]
    # Population counts only; the full prefix/action streams are not report models.
    outcomes: dict[str, int]
    delta_counts: tuple[int, int, int]


def collect_evidence(paths):
    """Authenticate all four sources before SQLite/selection; recheck after close."""
    sources = _authenticate_sources(paths)
    try:
        evaluation = modeled.authenticate_model_c()
        with ExitStack() as stack:
            connections = tuple(stack.enter_context(closing(repository.connect_database_readonly(
                source.path, immutable=True,
            ))) for source in sources if source.role in ("stage2", "stage3"))
            discovered = tuple(_discover_run(connection, stage, evaluation) for connection, stage in zip(
                connections, (schema.SOLVER_STAGE_STAGE_2, schema.SOLVER_STAGE_STAGE_3),
            ))
            runs, coverage = tuple(zip(*discovered))
            paired = statistics.validate_paired_prefix_sources(
                connections[0], runs[0].run_id, connections[1], runs[1].run_id,
                PREFIX_GAMES, require_official=True,
            )
            _require(len(paired.identities) == PREFIX_GAMES, "Paired identity count mismatch.")
            summaries = tuple(_load_summaries(connection, run.run_id) for connection, run in zip(connections, runs))
            outcomes, ww = _paired_outcomes(*summaries)
            documents = {source.role: json.loads(source.path.read_text(encoding="utf-8"))
                         for source in sources if source.role in ("comparison", "result")}
            deltas = _g4_deltas(documents["comparison"], documents["result"], sources, runs, evaluation, outcomes, ww)
            facts = tuple(representatives.PairedGameFact(
                index, summaries[0][index]["result"], summaries[1][index]["result"], deltas.get(index),
            ) for index in range(PREFIX_GAMES))
            selection = representatives.select_exemplars(facts)
            selected_indices = sorted({item.game.game_index for item in selection if item.game is not None})
            games = []
            for index in selected_indices:
                pair = tuple(_load_game(connection, run, index, summary[index], evaluation)
                             for connection, run, summary in zip(connections, runs, summaries))
                _require(_identity(asdict(pair[0].record)) == _identity(asdict(pair[1].record)),
                         "Selected board identity mismatch.")
                if index in deltas:
                    _require(pair[1].total_modeled_us - pair[0].total_modeled_us == deltas[index],
                             "Selected WW timeline/G4 delta mismatch.")
                games.append(pair)
            data = ReportData(sources, runs, coverage, evaluation, selection, tuple(games), outcomes, (
                sum(value < 0 for value in deltas.values()), sum(value == 0 for value in deltas.values()),
                sum(value > 0 for value in deltas.values()),
            ))
    finally:
        # This also runs after validation failures, after ExitStack closes both DBs.
        _verify_stability(sources)
    return data


def _text(value):
    if value is None:
        return "unavailable (None)"
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    return str(value)


def _table(headers, rows):
    return '<div class="table-scroll"><table><thead><tr>' + "".join(
        f"<th>{escape(_text(value))}</th>" for value in headers
    ) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join(f"<td>{escape(_text(value))}</td>" for value in row) + "</tr>" for row in rows
    ) + "</tbody></table></div>"


def _svg(points, title, unit):
    """Integer data; integer pixel scaling is presentation only, never an authority."""
    xmax, ymax = points[-1][0], max(point[1] for point in points)
    xscale, yscale = max(1, xmax), max(1, ymax)
    coordinates = " ".join(f"{100 + x * 760 // xscale},{240 - y * 200 // yscale}" for x, y in points)
    parts = [f'<svg viewBox="0 0 920 310" role="img" aria-label="{escape(title, quote=True)}">',
             f"<title>{escape(title)}</title>",
             f'<text x="100" y="22">{escape(title)} ({escape(unit)})</text>',
             '<path d="M100 40 V240 H860" fill="none" stroke="#555"/>']
    for value in sorted({0, xmax // 2, xmax}):
        x = 100 + value * 760 // xscale
        parts.append(f'<text x="{x}" y="264" text-anchor="middle">{value}</text>')
    for value in sorted({0, ymax // 2, ymax}):
        y = 240 - value * 200 // yscale
        parts.append(f'<text x="90" y="{y + 5}" text-anchor="end">{value}</text>')
    parts += [f'<polyline points="{coordinates}" fill="none" stroke="#176b86" stroke-width="2"/>',
              '<text x="480" y="297" text-anchor="middle">Completed semantic action count</text>', "</svg>"]
    return "".join(parts)


def _top_five(actions, metric):
    eligible = (item for item in actions if metric(item) is not None)
    return tuple(sorted(eligible, key=lambda item: (-metric(item), item.completed_action_count))[:5])


def _run_html(analytics, label):
    record = analytics.record
    actions = analytics.actions
    parts = [f"<h3>{escape(label)} — independent timeline</h3>", _table(
        ("Outcome", "Actions", "OPEN", "FLAG", "CHORD", "Total Model C cost through termination (us)"),
        [(record.result, record.total_actions, record.open_count, record.flag_count, record.chord_count,
          analytics.total_modeled_us)],
    ), _svg(analytics.cumulative_modeled_curve, label + " cumulative Model C cost", "integer us"),
        _svg(analytics.cumulative_safe_reveal_curve, label + " cumulative safe reveals", "safe cells")]
    for title, metric, unit in (
        ("Top 5 Model C action costs", lambda item: item.modeled_action_us, "Model C us"),
        ("Top 5 target transitions", lambda item: item.squared_displacement, "squared cell-center displacement"),
        ("Top 5 non-null compute diagnostics", lambda item: item.event.decision_compute_ns, "decision_compute_ns"),
    ):
        parts += [f"<h4>{escape(title)}</h4>",
                  "<p>Descending value; ties use ascending completed action count.</p>",
                  _table(("Completed actions", "Action", "Target", unit), (
                      (item.completed_action_count, item.event.action_type.name, (item.event.x, item.event.y), metric(item))
                      for item in _top_five(actions, metric))) ]
    flags = tuple(item for item in actions if item.event.action_type == Action.FLAG
                  and item.event.inference_category in (InferenceCategory.LOCAL_DETERMINISTIC, InferenceCategory.GLOBAL_CERTAINTY))
    chords = tuple(item for item in actions if item.event.action_type == Action.CHORD)
    guesses = tuple(item for item in actions if item.event.inference_category == InferenceCategory.PROBABILITY_GUESS)
    parts += ["<h4>Certainty-FLAG exposure / CHORD facts</h4>", _table(
        ("Certainty FLAG count", "Certainty FLAG exact Model C cost (us)", "CHORD inputs", "CHORD recorded safe reveals"),
        [(len(flags), sum(item.modeled_action_us for item in flags), len(chords),
          sum(item.event.safe_cells_opened_delta for item in chords))],
    ), "<p>FLAG exposure is not recoverable savings. FLAG→CHORD adjacency is not causal payoff.</p>",
        f"<h4>All recorded probability-guess events ({len(guesses)})</h4>", _table(
            ("Completed actions", "Target", "Exact target probability", "Exact minimum probability", "Candidate count"),
            ((item.completed_action_count, (item.event.x, item.event.y), item.event.target_mine_probability,
              item.event.minimum_available_mine_probability, item.event.selection_candidate_count) for item in guesses),
        ), "<h4>Exact recorded-action table</h4>", _table(
            ("Completed actions", "Action", "Target", "Status after", "Model C action us", "Cumulative Model C us",
             "dx", "dy", "Squared displacement", "Safe reveal delta", "Cumulative safe reveals", "Explicit flag delta",
             "Inference category", "Exact target probability", "Exact minimum probability", "Candidate count", "decision_compute_ns"),
            ((item.completed_action_count, item.event.action_type.name, (item.event.x, item.event.y), item.event.status_after.name,
              item.modeled_action_us, item.cumulative_modeled_us, item.dx, item.dy, item.squared_displacement,
              item.event.safe_cells_opened_delta, item.cumulative_safe_cells_opened, item.event.explicit_flag_delta,
              item.event.inference_category.name if item.event.inference_category else None,
              item.event.target_mine_probability, item.event.minimum_available_mine_probability,
              item.event.selection_candidate_count, item.event.decision_compute_ns) for item in actions),
        )]
    return "".join(parts)


def render_report(data, generation):
    """Self-contained HTML/SVG. All dynamic text is escaped at its output seam."""
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<title>Stage-3 Timeline Analytics — Official Category Exemplars</title>',
             '<style>body{font:16px system-ui,sans-serif;margin:2rem;color:#182830;line-height:1.5}'
             'h1,h2,h3{color:#14546b}table{border-collapse:collapse;margin:1rem 0;font-size:13px}'
             'td,th{border:1px solid #b7c7ce;padding:6px;text-align:left;overflow-wrap:anywhere}'
             'th{background:#edf4f7}.table-scroll{overflow-x:auto}svg{display:block;max-width:920px;width:100%;margin:1rem 0}'
             'svg text{font:13px system-ui,sans-serif}.notice{border-left:5px solid #176b86;padding:1rem;background:#edf4f7}'
             'section{border-top:2px solid #b7c7ce;margin-top:2rem}</style></head><body>',
             '<h1>Representative-board Demonstrations / Timeline Analytics</h1>',
             '<div class="notice"><p>These are deterministically selected category exemplars; '
             'NOT a statistically representative sample.</p><p>Each solver owns its action sequence. '
             'Equal action counts do NOT imply equal board state or progress. Model C is a shared measurement scale, '
             'not a shared execution clock. There is no common playhead, ordinal mapping, normalized progress or wall-clock synchronization.</p>'
             '<p>Model C cost is joint movement-plus-target-input cost, not measured movement time. '
             'LOSS cost is cost through termination, never time-to-win. Paired speed interpretation is WW-only.</p>'
             '<p>Stage-2 decision_compute_ns covers decision analysis. '
             'Stage-3 decision_compute_ns covers analysis plus planning. '
             'Stage-2 and Stage-3 compute timing scopes/environments differ in the historical runs. '
             'decision_compute_ns is a runtime diagnostic; no cross-stage compute-speed winner is inferred.</p></div>',
             '<h2>Provenance and validation</h2>', _table(
                 ("Source role", "Exact source path", "SHA-256", "Bytes", "mtime_ns", "DB sidecars"),
                 ((SOURCE_ROLES[source.role], source.path, source.sha256, source.size_bytes, source.mtime_ns,
                   "absent" if source.role in ("stage2", "stage3") else "not applicable") for source in data.sources),
             ), _table(("Generation provenance", "Value"), generation.items()),
             '<p>All four accepted SHA-256 identities verified before selection. Sources rehashed after both immutable read-only '
             'connections closed: bytes, sizes, modification timestamps and absent sidecars unchanged. '
             'This is a bounded stability check of preserved completed artifacts, not a cross-file atomic snapshot.</p>',
             '<p>Run discovery, official eligibility, independent exact-prefix summaries, paired board identities, '
             'outcome counts, G4 acceptance/provenance and WW index sets all reconcile. '
             'Only unique selected games have detailed action reads. No solver, Engine, board generator or all-prefix action evaluation was used.</p>']
    for run, coverage in zip(data.runs, data.coverage):
        parts += [f"<h3>{escape(run.solver_stage)} source / discovered run</h3>",
                  _table(("Run identity / coverage", "Value"), {**asdict(run), **asdict(coverage)}.items())]
    parts += ["<h3>Authenticated frozen Model C</h3>", _table(("Identity", "Value"), _model_identity(data.evaluation).items()),
              f"<p>Exact corpus prefix [0,{PREFIX_GAMES}); canonical first click (0,0). "
              "Both solver timelines in this report use post-hoc Model C evaluation of persisted executed action targets. "
              "Stage-2 historical telemetry did not natively declare Model C. "
              "Stage-3 collection declared frozen Model C and historically checked its native total. "
              "The reduced persisted Stage-3 events used here contain neither native per-action modeled_action_us nor cursor_before fields. "
              "The displayed Stage-3 timeline is therefore also reconstructed post-hoc from persisted actions under the authenticated frozen Model C; "
              "it does not display retained native Stage-3 action costs.</p>",
              "<h2>Selection rules and category membership</h2>",
              "<p>delta_us = Stage3_model_c_us - Stage2_model_c_us. First outcome letter = Stage 2; second = Stage 3. "
              "All eight predeclared rules use the accepted select_exemplars() result unchanged. "
              "No visual/manual substitution. Duplicate category memberships are retained; detail loads occur once per unique game per solver.</p>",
              _table(("Outcome population", "Count"), ((key.upper(), value) for key, value in data.outcomes.items())),
              _table(("Negative WW deltas", "Zero WW deltas", "Positive WW deltas"), [data.delta_counts]),
              f"<p>Lower-median zero-based rank: {(data.outcomes['ww'] - 1) // 2 if data.outcomes['ww'] else 'EMPTY'} "
              f"within {data.outcomes['ww']} WW games sorted by (delta_us, game_index). "
              "Population facts describe these artifacts only, not a universal invariant.</p>",
              _table(("Category", "Accepted rule (EMPTY if no eligible game)", "Selected game_index", "WW delta_us"), (
                  (*CATEGORY_TEXT[item.category], item.game.game_index if item.game else "EMPTY",
                   item.game.delta_us if item.game else None) for item in data.selection)),
              "<h2>Selected-game independent timelines</h2>",
              "<p>Horizontal coordinate = completed semantic action count; persisted action_index i maps to i+1. "
              "The (0,0) curve origin is not an action/event. Every recorded input, including the canonical first OPEN, "
              "same-cell inputs and the terminal input, counts. Automatic effects do not add actions. "
              "SVG pixel scaling and straight line segments are presentation only; no inter-action execution is inferred. "
              "Exact integer/Fraction tables remain authoritative; missing metadata is unavailable (None), never zero.</p>"]
    for left, right in data.games:
        index = left.record.game_index
        memberships = tuple(item for item in data.selection if item.game and item.game.game_index == index)
        parts += [f"<section><h2>Game {index}</h2>", _table(("Paired board fact", "Value"), [
            ("Category memberships", "; ".join(CATEGORY_TEXT[item.category][0] for item in memberships)),
            ("Stage-2 outcome", left.record.result), ("Stage-3 outcome", right.record.result),
            ("Seed", left.record.seed), ("Board fingerprint", left.record.board_fingerprint),
            ("First click", (left.record.first_click_x, left.record.first_click_y)),
        ])]
        if left.record.result == right.record.result == "WIN":
            parts += [f"<p>Selected WW timeline delta_us = {right.total_modeled_us - left.total_modeled_us}; "
                      "exactly reconciled with authenticated G4 evidence.</p>"]
        else:
            parts += ["<p>Non-WW: both modeled totals are descriptive costs through termination. "
                      "No paired speed-to-win benefit is assigned.</p>"]
        parts += [_run_html(left, "Stage 2"), _run_html(right, "Stage 3"), "</section>"]
    parts += ["<h2>Unavailable evidence / deferred interpretation</h2>",
              "<p>On a recorded Stage-2 probability-guess event, selection_candidate_count is the exact-minimum-risk tie multiplicity / "
              "final selector pool size. Official Stage-3 candidate count is unavailable, including on guesses; "
              "missing Stage-3 candidate counts are never reconstructed. No candidate geometry or decision metadata is inferred.</p>"
              "<p>Persisted inputs do not retain native cursor_before, native per-action modeled_action_us, Replay timestamps, "
              "full probability coordinate maps or chosen plans; none is fabricated as native evidence.</p>"
              "<p>Human Replay/Mouse Trace are deferred. Causal FLAG→CHORD payoff, avoidable-backtracking classification, "
              "nearest-risk counterfactuals, Known-Mine/No-Flag savings, planner phase attribution and new algorithms require later evidence or experiments.</p>",
              "</body></html>"]
    return "".join(parts)


def _generation_provenance():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "report_script_sha256": _hash_file(Path(__file__).resolve()),
        "rendering": "Python standard library; self-contained HTML + inline SVG; no external assets",
    }


def _publish(html, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    output = directory / "report.html"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(html)
    return output


def generate_report(paths, directory):
    data = collect_evidence(paths)
    # No report file/directory is created until all reads/close/stability checks pass.
    html = render_report(data, _generation_provenance())
    output = _publish(html, directory)
    return data, output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for role in EXPECTED_HASHES:
        parser.add_argument("--" + role, type=Path, required=True, help=SOURCE_ROLES[role] + " (exact accepted artifact)")
    args = parser.parse_args(argv)
    directory = ROOT / "results" / "stage3-timeline-analytics" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:12]
    )
    data, output = generate_report(vars(args), directory)
    print(json.dumps({
        "report": str(output), "size_bytes": output.stat().st_size, "sha256": _hash_file(output),
        "sources": [{**asdict(source), "path": str(source.path)} for source in data.sources],
        "runs": [asdict(run) for run in data.runs], "coverage": [asdict(item) for item in data.coverage],
        "model_c": _model_identity(data.evaluation), "outcomes": data.outcomes, "delta_counts": data.delta_counts,
        "categories": [{"category": item.category.value, "game_index": item.game.game_index if item.game else None,
                        "delta_us": item.game.delta_us if item.game else None} for item in data.selection],
        "unique_selected_games": len(data.games),
        "selected_timelines": [{"game_index": left.record.game_index,
                                "outcomes": [left.record.result, right.record.result],
                                "actions": [len(left.actions), len(right.actions)],
                                "modeled_us": [left.total_modeled_us, right.total_modeled_us]}
                               for left, right in data.games],
        "source_stability": "PASS; hashes/sizes/mtimes unchanged; no sidecars",
    }, indent=2))


if __name__ == "__main__":
    main()
