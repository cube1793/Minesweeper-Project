"""Read-only benchmark statistics and explicit paired-prefix validation.

Persisted game summaries supply game aggregates; action events supply decision
timings and selected guess risks. Rational TEXT is grouped only by identity in
SQL and decoded before numeric ordering. No solver or board logic is rerun.

The caller owns the connection. Reads do not change its configuration or open a
transaction, and do not provide a snapshot across queries while a writer runs.
Statistics retain their run's corpus/first-click condition. Pairing validates
board identity, not environment compatibility for direct compute-time claims.
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from fractions import Fraction

from telemetry_repository import decode_probability, fetch_game_indices
import telemetry_schema as schema


class BenchmarkStatisticsError(ValueError):
    """A requested run, comparison range, or persisted identity is invalid."""


@dataclass(frozen=True)
class RunCoverage:
    run_id: int
    run_status: str
    requested_games: int
    processed_games: int
    stored_game_count: int
    git_dirty: bool
    exact_processed_prefix: bool
    exact_requested_prefix: bool
    official_eligible: bool


@dataclass(frozen=True)
class RunStatistics:
    coverage: RunCoverage
    wins: int
    losses: int
    win_rate: Fraction | None
    games_with_probability_guess: int
    guess_game_rate: Fraction | None
    mean_guess_count: Fraction | None
    guess_count_distribution: tuple[tuple[int, int], ...]
    probability_guess_distribution: tuple[tuple[Fraction, int], ...]
    local_deterministic_count: int
    global_certainty_count: int
    probability_guess_count: int
    total_actions: int
    open_count: int
    flag_count: int
    chord_count: int
    compute_time_total_ns: int
    decision_compute_count: int
    mean_decision_compute_ns: Fraction | None
    max_decision_compute_ns: int | None
    decision_compute_percentiles_ns: tuple[tuple[int, int], ...]
    board_3bv_distribution: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class PairedGameIdentity:
    game_index: int
    seed: int
    board_fingerprint: str
    first_click_x: int
    first_click_y: int


@dataclass(frozen=True)
class PairedComparison:
    left_run_id: int
    right_run_id: int
    benchmark_set_id: str
    prefix_games: int
    identities: tuple[PairedGameIdentity, ...]
    require_official: bool


_PAIR_COMPATIBILITY_FIELDS = (
    "benchmark_set_id", "width", "height", "num_mines", "first_click_policy",
    "board_generator_version", "telemetry_schema_version",
)


def _fetch_run(connection: sqlite3.Connection, run_id: int) -> sqlite3.Row:
    if type(run_id) is not int:
        raise BenchmarkStatisticsError("run_id must be an int, excluding bool.")
    # Use a cursor-local factory, preserving both ordinary and repository
    # connections' caller-selected row factories.
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        run = cursor.execute(
            """
            SELECT run_id, run_status, requested_games, processed_games, git_dirty,
                   benchmark_set_id, width, height, num_mines, first_click_policy,
                   board_generator_version, telemetry_schema_version
            FROM benchmark_runs WHERE run_id = ?
            """, (run_id,),
        ).fetchone()
    if run is None:
        raise BenchmarkStatisticsError(f"Unknown run_id: {run_id!r}.")
    return run


def _coverage(connection: sqlite3.Connection, run: sqlite3.Row) -> RunCoverage:
    indices = fetch_game_indices(connection, run["run_id"])
    stored = len(indices)
    contiguous = all(index == expected for expected, index in enumerate(indices))
    exact_processed = stored == run["processed_games"] and contiguous
    exact_requested = stored == run["requested_games"] and contiguous
    dirty = bool(run["git_dirty"])
    return RunCoverage(
        run_id=run["run_id"], run_status=run["run_status"],
        requested_games=run["requested_games"], processed_games=run["processed_games"],
        stored_game_count=stored, git_dirty=dirty,
        exact_processed_prefix=exact_processed, exact_requested_prefix=exact_requested,
        official_eligible=(
            run["run_status"] == schema.RUN_STATUS_COMPLETED and not dirty and exact_requested
        ),
    )


def get_run_coverage(connection: sqlite3.Connection, run_id: int) -> RunCoverage:
    """Compare stored indices with metadata; never repair either one.

    Official eligibility is exactly COMPLETED + clean provenance + exact
    requested prefix. Empty coverage is an exact processed prefix when the
    processed count is zero, but cannot be an official completed baseline.
    """
    return _coverage(connection, _fetch_run(connection, run_id))


def calculate_run_statistics(connection: sqlite3.Connection, run_id: int) -> RunStatistics:
    """Aggregate stored WIN/LOSS games, including diagnostic partial runs.

    All game rates use WIN + LOSS; mean guess count includes zero-guess games.
    Decision time uses every non-null event timing, including zero nanoseconds.
    Percentile pairs are (percent, nanoseconds), using nearest rank without
    interpolation. The game-summary compute total is reported independently.
    """
    coverage = get_run_coverage(connection, run_id)
    game_parameters = (run_id, schema.GAME_RESULT_WIN, schema.GAME_RESULT_LOSS)
    (
        wins, losses, guessed_games, local_count, global_count, guess_count,
        total_actions, open_count, flag_count, chord_count, compute_total,
    ) = connection.execute(
        """
        SELECT COUNT(CASE WHEN result = ? THEN 1 END),
               COUNT(CASE WHEN result = ? THEN 1 END),
               COALESCE(SUM(had_probability_guess), 0),
               COALESCE(SUM(local_deterministic_count), 0),
               COALESCE(SUM(global_certainty_count), 0),
               COALESCE(SUM(probability_guess_count), 0),
               COALESCE(SUM(total_actions), 0),
               COALESCE(SUM(open_count), 0),
               COALESCE(SUM(flag_count), 0),
               COALESCE(SUM(chord_count), 0),
               COALESCE(SUM(compute_time_total_ns), 0)
        FROM games WHERE run_id = ? AND result IN (?, ?)
        """, (schema.GAME_RESULT_WIN, schema.GAME_RESULT_LOSS, *game_parameters),
    ).fetchone()
    game_count = wins + losses
    guess_distribution = tuple(tuple(row) for row in connection.execute(
        """
        SELECT probability_guess_count, COUNT(*) FROM games
        WHERE run_id = ? AND result IN (?, ?)
        GROUP BY probability_guess_count ORDER BY probability_guess_count
        """, game_parameters,
    ).fetchall())
    board_distribution = tuple(tuple(row) for row in connection.execute(
        """
        SELECT board_3bv, COUNT(*) FROM games
        WHERE run_id = ? AND result IN (?, ?)
        GROUP BY board_3bv ORDER BY board_3bv
        """, game_parameters,
    ).fetchall())

    decision_count, decision_total, decision_max = connection.execute(
        """
        SELECT COUNT(e.decision_compute_ns), SUM(e.decision_compute_ns),
               MAX(e.decision_compute_ns)
        FROM games g JOIN action_events e ON e.game_id = g.game_id
        WHERE g.run_id = ? AND g.result IN (?, ?) AND e.decision_compute_ns IS NOT NULL
        """, game_parameters,
    ).fetchone()
    percentiles = []
    if decision_count:
        for percent, numerator, denominator in ((50, 1, 2), (90, 9, 10), (95, 19, 20), (99, 99, 100)):
            rank = (numerator * decision_count + denominator - 1) // denominator
            # Only one ordered observation crosses into Python per percentile.
            timing = connection.execute(
                """
                SELECT e.decision_compute_ns
                FROM games g JOIN action_events e ON e.game_id = g.game_id
                WHERE g.run_id = ? AND g.result IN (?, ?) AND e.decision_compute_ns IS NOT NULL
                ORDER BY e.decision_compute_ns LIMIT 1 OFFSET ?
                """, (*game_parameters, rank - 1),
            ).fetchone()[0]
            percentiles.append((percent, timing))

    probability_distribution = []
    probability_rows = connection.execute(
        """
        SELECT e.target_mine_probability, COUNT(*)
        FROM games g JOIN action_events e ON e.game_id = g.game_id
        WHERE g.run_id = ? AND g.result IN (?, ?) AND e.inference_category = ?
        GROUP BY e.target_mine_probability
        """, (*game_parameters, schema.INFERENCE_PROBABILITY_GUESS),
    ).fetchall()
    for text, count in probability_rows:
        try:
            probability = decode_probability(text)
        except (TypeError, ValueError) as error:
            raise BenchmarkStatisticsError(
                f"Run {run_id} has an invalid probability-guess target: {text!r}."
            ) from error
        if probability is None:
            raise BenchmarkStatisticsError(f"Run {run_id} has a NULL probability-guess target.")
        probability_distribution.append((probability, count))

    return RunStatistics(
        coverage=coverage, wins=wins, losses=losses,
        win_rate=Fraction(wins, game_count) if game_count else None,
        games_with_probability_guess=guessed_games,
        guess_game_rate=Fraction(guessed_games, game_count) if game_count else None,
        mean_guess_count=Fraction(guess_count, game_count) if game_count else None,
        guess_count_distribution=guess_distribution,
        probability_guess_distribution=tuple(sorted(probability_distribution)),
        local_deterministic_count=local_count, global_certainty_count=global_count,
        probability_guess_count=guess_count, total_actions=total_actions,
        open_count=open_count, flag_count=flag_count, chord_count=chord_count,
        compute_time_total_ns=compute_total, decision_compute_count=decision_count,
        mean_decision_compute_ns=Fraction(decision_total, decision_count) if decision_count else None,
        max_decision_compute_ns=decision_max,
        decision_compute_percentiles_ns=tuple(percentiles),
        board_3bv_distribution=board_distribution,
    )


def _read_prefix(
    connection: sqlite3.Connection, run_id: int, prefix_games: int,
) -> tuple[PairedGameIdentity, ...]:
    rows = connection.execute(
        """
        SELECT game_index, seed, board_fingerprint, first_click_x, first_click_y
        FROM games WHERE run_id = ? AND game_index >= 0 AND game_index < ?
        ORDER BY game_index
        """, (run_id, prefix_games),
    ).fetchall()
    if len(rows) != prefix_games or any(row[0] != index for index, row in enumerate(rows)):
        raise BenchmarkStatisticsError(
            f"Run {run_id} is missing exact coverage of prefix [0, {prefix_games})."
        )
    return tuple(PairedGameIdentity(*row) for row in rows)


def validate_paired_prefix(
    connection: sqlite3.Connection, left_run_id: int, right_run_id: int,
    prefix_games: int, *, require_official: bool = False,
) -> PairedComparison:
    """Validate every identity in explicit [0, prefix_games), or raise.

    V1 requires equal telemetry semantic versions. Solver identity, commit and
    environment may differ. Official mode requires each run's entire requested
    prefix to be eligible, even when the comparison selects a smaller prefix.
    Diagnostic mode stays diagnostic even if both runs happen to be eligible.
    """
    if type(prefix_games) is not int or prefix_games <= 0:
        raise BenchmarkStatisticsError("prefix_games must be a positive int, excluding bool.")
    if not isinstance(require_official, bool):
        raise BenchmarkStatisticsError("require_official must be a bool.")
    left = _fetch_run(connection, left_run_id)
    right = _fetch_run(connection, right_run_id)
    for field in _PAIR_COMPATIBILITY_FIELDS:
        if left[field] != right[field]:
            raise BenchmarkStatisticsError(f"Run compatibility mismatch: {field}.")
    for run in (left, right):
        if prefix_games > run["requested_games"]:
            raise BenchmarkStatisticsError(
                f"prefix_games exceeds requested_games for run {run['run_id']}."
            )
        if require_official and not _coverage(connection, run).official_eligible:
            raise BenchmarkStatisticsError(f"Run {run['run_id']} is not official-eligible.")

    # Read each side independently so absent rows cannot disappear in a join.
    left_identities = _read_prefix(connection, left_run_id, prefix_games)
    right_identities = _read_prefix(connection, right_run_id, prefix_games)
    for left_game, right_game in zip(left_identities, right_identities, strict=True):
        for field in ("seed", "board_fingerprint", "first_click_x", "first_click_y"):
            if getattr(left_game, field) != getattr(right_game, field):
                raise BenchmarkStatisticsError(
                    f"Game identity mismatch at game_index {left_game.game_index}: {field}."
                )
    return PairedComparison(
        left_run_id=left_run_id, right_run_id=right_run_id,
        benchmark_set_id=left["benchmark_set_id"], prefix_games=prefix_games,
        identities=left_identities, require_official=require_official,
    )
