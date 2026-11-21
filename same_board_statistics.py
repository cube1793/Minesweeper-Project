"""Main-play statistics for Same-board Comparison results (pure, no Qt).

The existing ``ReplayStatisticsAnalyzer`` computes every value; nothing here
defines a metric or a format. Human statistics use the compared Replay and its
own Replay time. A validated algorithm stream is moved, unchanged, into a
fixed-layout algorithm ``ReplayData`` (event time 0) and analysed by the same
code. Values that need real elapsed time are "—" for algorithms (they have no
real time; Model C time is not substituted). ZiNi, ZNE and ZNT are "—" for
every column because the board ZiNi comes from the main window's separate ZiNi
job, which this window does not run. Unfinished runs keep the analyzer's own
masking ("-").
"""

from replay_model import SOURCE_ALGORITHM, ReplayData, ReplayEvent
from replay_statistics import STAT_KEYS, ReplayStatisticsAnalyzer


# Display order and names follow the main window's statistics panel.
STAT_LABELS = (
    ("time", "시간"), ("est_time", "예상 시간"), ("bbbv", "3BV"), ("bbbv_per_sec", "3BV/s"),
    ("clicks", "클릭"), ("left", "왼쪽 클릭"), ("right", "오른쪽 클릭"), ("chord", "화음"),
    ("cps", "CPS"), ("efficiency", "Efficiency"), ("ioe", "IOE"), ("ops", "Ops"),
    ("thrp", "Thrp"), ("corr", "Corr"), ("zini", "ZiNi"), ("zne", "ZNE"), ("znt", "ZNT"),
)
# The items ReplayStatisticsAnalyzer.statistics_at derives from replay_time.
TIME_KEYS = ("time", "est_time", "bbbv_per_sec", "cps")
# The items that need the board ZiNi value (statistics_at's board_zini input).
ZINI_KEYS = ("zini", "zne", "znt")
NOT_AVAILABLE = "—"
NOTE = ("—: 이 창에서 값을 만들지 않음. 알고리즘의 시간·예상 시간·3BV/s·CPS는 실제 경과 시간이 "
        "없어서 비워 둡니다(Model C 시간으로 대신 계산하지 않음). ZiNi·ZNE·ZNT는 메인 창의 별도 "
        "ZiNi 계산 결과가 필요한데 이 창은 그 계산을 실행하지 않습니다.\n"
        "-: 기존 통계 규칙 그대로 값이 없음(끝나지 않은 판, 0으로 나눔).\n"
        "값은 메인 창 Replay 통계와 같은 코드로 판 전체(마지막 위치)를 계산합니다. "
        "Human의 시간은 Replay 시간입니다.")

if tuple(key for key, _label in STAT_LABELS) != STAT_KEYS:
    raise RuntimeError("Same-board statistics labels must match the main statistics keys.")


def algorithm_replay(board, moves) -> ReplayData:
    """The validated moves as an algorithm Replay on the same fixed layout."""
    return ReplayData(board, tuple(ReplayEvent(0.0, move.x, move.y, move.action) for move in moves),
                      source_type=SOURCE_ALGORITHM)


def final_statistics(replay: ReplayData, replay_time: float) -> dict[str, str]:
    """The existing Replay statistics at the last position, without a board ZiNi."""
    timeline = ReplayStatisticsAnalyzer.analyze(replay)
    return ReplayStatisticsAnalyzer.statistics_at(timeline, len(replay.events), replay_time, None)


def human_statistics(replay: ReplayData) -> dict[str, str]:
    replay_time = replay.events[-1].elapsed_time if replay.events else 0.0
    stats = final_statistics(replay, replay_time)
    stats.update({key: NOT_AVAILABLE for key in ZINI_KEYS})
    return stats


def algorithm_statistics(board, run) -> dict[str, str]:
    """Only a validated played run has moves; other outcomes have none."""
    stats = final_statistics(algorithm_replay(board, run.moves if run.playable else ()), 0.0)
    stats.update({key: NOT_AVAILABLE for key in TIME_KEYS + ZINI_KEYS})
    return stats
