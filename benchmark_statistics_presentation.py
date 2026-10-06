"""Pure display text and plot coordinates for persisted benchmark statistics.

Fractions and nanoseconds remain backend values. These helpers only format them;
plot coordinates are never fed back into aggregation or used to merge identities.
"""

from dataclasses import dataclass
from fractions import Fraction


DEFAULT_LANGUAGE = "ko"
TEXT = {
    "ko": {
        "title": "벤치마크 통계", "open_database": "데이터베이스 열기",
        "database": "데이터베이스", "language": "언어", "run": "실행",
        "database_filter": "SQLite 데이터베이스 (*.sqlite3 *.sqlite *.db);;모든 파일 (*)",
        "no_database": "기존 텔레메트리 데이터베이스를 열어 주세요.",
        "empty_database": "저장된 벤치마크 실행이 없습니다.",
        "error": "데이터베이스를 읽을 수 없습니다", "query_error": "실행 통계를 읽을 수 없습니다",
        "readonly_note": "읽기 전용 · 실행 선택 시 조회한 통계", "summary": "실행 요약",
        "identity": "실행 정보", "coverage": "수집 범위", "results": "결과",
        "actions": "행동 / 추론 횟수", "timing": "의사결정 계산 시간",
        "official": "공식 기준 사용 가능", "diagnostic": "진단용 실행",
        "yes": "예", "no": "아니요", "run_id": "실행 ID", "created_at": "생성 시각",
        "run_status": "실행 상태", "benchmark_set_id": "벤치마크 세트",
        "solver_stage": "솔버 단계", "solver_policy": "솔버 정책", "board_size": "보드 크기",
        "num_mines": "지뢰 수", "first_click_policy": "첫 클릭 정책",
        "board_generator_version": "보드 생성기 버전", "telemetry_schema_version": "텔레메트리 버전",
        "requested_games": "요청 게임 수", "processed_games": "처리 게임 수",
        "stored_game_count": "저장 게임 수", "exact_processed_prefix": "처리 접두 범위 정확",
        "exact_requested_prefix": "요청 접두 범위 정확", "git_dirty": "Git 미커밋 변경 있음",
        "official_eligible": "공식 기준 사용 가능", "wins": "승리", "losses": "패배",
        "win_rate": "승률", "games_with_probability_guess": "확률 추측 포함 게임",
        "guess_game_rate": "추측 게임 비율", "mean_guess_count": "평균 추측 횟수",
        "local_deterministic_count": "지역 확정 추론", "global_certainty_count": "전역 확정 추론",
        "probability_guess_count": "확률 추측", "total_actions": "전체 행동",
        "open_count": "OPEN", "flag_count": "FLAG", "chord_count": "CHORD",
        "compute_time_total_ns": "총 계산 시간", "decision_compute_count": "측정 의사결정 수",
        "mean_decision_compute_ns": "평균", "max_decision_compute_ns": "최대",
        "p50": "P50", "p90": "P90", "p95": "P95", "p99": "P99",
        "timing_note": "의사결정 계산 시간은 진단용이며 실행 환경에 영향을 받습니다.",
        "guess_graph": "추측 횟수 분포", "risk_graph": "확률 추측 위험 분포", "board_graph": "보드 3BV 분포",
        "guess_x": "게임당 확률 추측 횟수", "game_count": "게임 수",
        "risk_x": "선택된 칸의 지뢰 확률 (%)", "event_count": "이벤트 수",
        "board_x": "보드 3BV", "exact_risk": "정확한 확률",
        "risk_note": "관측 단위: PROBABILITY_GUESS ActionEvent 1개. 점을 가리키거나 선택해 정확한 분수를 확인하세요.",
        "no_points": "표시할 관측값이 없습니다.",
    },
    "en": {
        "title": "Benchmark Statistics", "open_database": "Open Database",
        "database": "Database", "language": "Language", "run": "Run",
        "database_filter": "SQLite databases (*.sqlite3 *.sqlite *.db);;All files (*)",
        "no_database": "Open an existing telemetry database.",
        "empty_database": "No persisted benchmark runs.",
        "error": "Cannot read database", "query_error": "Cannot read run statistics",
        "readonly_note": "Read only · statistics queried when a run is selected", "summary": "Run summary",
        "identity": "Run identity", "coverage": "Coverage", "results": "Results",
        "actions": "Action / inference counts", "timing": "Decision compute time",
        "official": "Official eligible", "diagnostic": "Diagnostic run",
        "yes": "Yes", "no": "No", "run_id": "Run ID", "created_at": "Created at",
        "run_status": "Run status", "benchmark_set_id": "Benchmark set",
        "solver_stage": "Solver stage", "solver_policy": "Solver policy", "board_size": "Board size",
        "num_mines": "Mines", "first_click_policy": "First-click policy",
        "board_generator_version": "Board generator version", "telemetry_schema_version": "Telemetry version",
        "requested_games": "Requested games", "processed_games": "Processed games",
        "stored_game_count": "Stored games", "exact_processed_prefix": "Exact processed prefix",
        "exact_requested_prefix": "Exact requested prefix", "git_dirty": "Git dirty",
        "official_eligible": "Official eligible", "wins": "Wins", "losses": "Losses",
        "win_rate": "Win rate", "games_with_probability_guess": "Games with probability guess",
        "guess_game_rate": "Guess-game rate", "mean_guess_count": "Mean guess count",
        "local_deterministic_count": "Local deterministic", "global_certainty_count": "Global certainty",
        "probability_guess_count": "Probability guess", "total_actions": "Total actions",
        "open_count": "OPEN", "flag_count": "FLAG", "chord_count": "CHORD",
        "compute_time_total_ns": "Total compute time", "decision_compute_count": "Timed decisions",
        "mean_decision_compute_ns": "Mean", "max_decision_compute_ns": "Max",
        "p50": "P50", "p90": "P90", "p95": "P95", "p99": "P99",
        "timing_note": "Decision compute time is diagnostic and environment-sensitive.",
        "guess_graph": "Guess count distribution", "risk_graph": "Probability-guess risk distribution",
        "board_graph": "Board 3BV distribution", "guess_x": "Probability guesses per game",
        "game_count": "Game count", "risk_x": "Selected cell mine probability (%)",
        "event_count": "Event count", "board_x": "Board 3BV", "exact_risk": "Exact probability",
        "risk_note": "Observation unit: one PROBABILITY_GUESS ActionEvent. Hover or select a point to inspect its exact fraction.",
        "no_points": "No observations to display.",
    },
}


def text(key: str, language: str = DEFAULT_LANGUAGE) -> str:
    if language not in TEXT:
        raise ValueError(f"Unsupported language: {language!r}.")
    return TEXT[language][key]  # Unknown keys explicitly raise KeyError.


def format_fraction(value: Fraction | None) -> str:
    if value is None:
        return "—"
    return f"{value.numerator}/{value.denominator}"


def _decimal(value: Fraction, places: int) -> str:
    """Round for display using integer arithmetic, including huge fractions."""
    scaled = round(value * 10**places)
    sign = "-" if scaled < 0 else ""
    whole, tail = divmod(abs(scaled), 10**places)
    return f"{sign}{whole}.{tail:0{places}d}"


def format_rate(value: Fraction | None) -> str:
    if value is None:
        return "—"
    return f"{format_fraction(value)} ({_decimal(value * 100, 2)}%)"


def format_mean(value: Fraction | None) -> str:
    if value is None:
        return "—"
    return f"{format_fraction(value)} (≈ {_decimal(value, 2)})"


def format_nanoseconds(value: int | Fraction | None) -> str:
    if value is None:
        return "—"
    exact = Fraction(value)
    if exact < 0:
        raise ValueError("Nanoseconds cannot be negative.")
    scale, unit = next(
        (scale, unit) for scale, unit in
        ((10**9, "s"), (10**6, "ms"), (10**3, "µs"), (1, "ns"))
        if exact >= scale or scale == 1
    )
    display = (f"{exact.numerator} ns" if scale == 1 and exact.denominator == 1
               else f"{_decimal(exact / scale, 3)} {unit}")
    if isinstance(value, Fraction):
        return f"{format_fraction(value)} ns (≈ {display})"
    return display


@dataclass(frozen=True)
class DiscretePoint:
    x: int
    count: int


@dataclass(frozen=True)
class ProbabilityPoint:
    probability: Fraction
    x: float
    count: int
    exact_label: str


def discrete_points(distribution: tuple[tuple[int, int], ...]) -> tuple[DiscretePoint, ...]:
    """Preserve backend numeric ordering and every bin, including zero."""
    return tuple(DiscretePoint(value, count) for value, count in distribution)


def probability_points(
    distribution: tuple[tuple[Fraction, int], ...],
) -> tuple[ProbabilityPoint, ...]:
    """Use continuous percent coordinates, preserving exact backend order/identity."""
    return tuple(ProbabilityPoint(risk, float(risk * 100), count, format_fraction(risk))
                 for risk, count in distribution)


def probability_detail(point: ProbabilityPoint, language: str = DEFAULT_LANGUAGE) -> str:
    return (f"{format_rate(point.probability)}\n"
            f"{text('event_count', language)}: {point.count}")
