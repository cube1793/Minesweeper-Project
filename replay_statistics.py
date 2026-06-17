"""Pure replay counter timeline and statistics helpers."""

from dataclasses import dataclass

from board_analyzer import BoardAnalysis, CellClass, analyze_board
from core_engine import GameStatus
from replay_model import (
    ACTION_CHORD,
    ACTION_FLAG,
    ACTION_OPEN,
    ReplayData,
)
from replay_player import ReplayPlayer


STAT_KEYS = (
    "time",
    "est_time",
    "bbbv",
    "bbbv_per_sec",
    "clicks",
    "left",
    "right",
    "chord",
    "cps",
    "efficiency",
    "ioe",
    "ops",
    "thrp",
    "corr",
    "zini",
    "zne",
    "znt",
)

REPLAY_ACTION_COUNTER_KEYS = {
    ACTION_OPEN: "left",
    ACTION_FLAG: "right",
    ACTION_CHORD: "chord",
}


@dataclass(frozen=True)
class ReplayCounterEntry:
    status: GameStatus
    active_total: int
    wasted_total: int
    active_left: int
    wasted_left: int
    active_right: int
    wasted_right: int
    active_chord: int
    wasted_chord: int
    completed_3bv: int
    completed_ops: int


@dataclass(frozen=True)
class ReplayCounterTimeline:
    is_completed: bool
    total_3bv: int
    total_ops: int
    entries: tuple[ReplayCounterEntry, ...]


class ReplayStatisticsAnalyzer:
    @classmethod
    def analyze(cls, replay_data: ReplayData) -> ReplayCounterTimeline:
        """Build replay counter timeline using public replay/engine interfaces."""
        player = ReplayPlayer(replay_data)
        analysis = analyze_board(player.engine.get_board_snapshot())
        active = {"total": 0, "left": 0, "right": 0, "chord": 0}
        wasted = {"total": 0, "left": 0, "right": 0, "chord": 0}
        entries: list[ReplayCounterEntry] = []

        def append_current_entry() -> None:
            counter_snapshot = player.engine.get_counter_snapshot()
            active["total"] = counter_snapshot["active_clicks"]
            wasted["total"] = counter_snapshot["wasted_clicks"]
            entries.append(
                ReplayCounterEntry(
                    status=counter_snapshot["status"],
                    active_total=active["total"],
                    wasted_total=wasted["total"],
                    active_left=active["left"],
                    wasted_left=wasted["left"],
                    active_right=active["right"],
                    wasted_right=wasted["right"],
                    active_chord=active["chord"],
                    wasted_chord=wasted["chord"],
                    completed_3bv=counter_snapshot["completed_3bv"],
                    completed_ops=cls._completed_ops_from_public_observation(
                        player.engine.get_observation(),
                        analysis,
                    ),
                )
            )

        append_current_entry()
        for event in replay_data.events:
            before = player.engine.get_counter_snapshot()
            player.next()
            after = player.engine.get_counter_snapshot()
            category = REPLAY_ACTION_COUNTER_KEYS.get(event.action)
            if category is not None:
                active_delta = after["active_clicks"] - before["active_clicks"]
                wasted_delta = after["wasted_clicks"] - before["wasted_clicks"]
                if active_delta > 0:
                    active[category] += active_delta
                if wasted_delta > 0:
                    wasted[category] += wasted_delta
            append_current_entry()

        final_status = entries[-1].status if entries else GameStatus.PLAYING
        return ReplayCounterTimeline(
            is_completed=final_status in (GameStatus.WON, GameStatus.LOST),
            total_3bv=analysis.total_3bv,
            total_ops=analysis.total_ops,
            entries=tuple(entries),
        )

    @staticmethod
    def statistics_at(
        timeline: ReplayCounterTimeline,
        index: int,
        replay_time: float,
        board_zini: int | None,
    ) -> dict[str, str]:
        """Return formatted replay Counters values at one timeline position."""
        if not timeline.is_completed:
            return ReplayStatisticsAnalyzer.masked_statistics()

        entry = ReplayStatisticsAnalyzer._entry_at(timeline, index)
        if entry is None:
            return ReplayStatisticsAnalyzer.masked_statistics()

        active_clicks = entry.active_total
        wasted_clicks = entry.wasted_total
        total_clicks = active_clicks + wasted_clicks
        completed_3bv = entry.completed_3bv
        completed_ops = entry.completed_ops

        bbbv_per_sec = (
            completed_3bv / replay_time if replay_time > 0.0 else None
        )
        est_time = (
            timeline.total_3bv / bbbv_per_sec
            if bbbv_per_sec and bbbv_per_sec > 0.0
            else None
        )

        stats = {
            "time": f"{replay_time:.3f}",
            "est_time": f"{est_time:.3f}" if est_time is not None else "-",
            "bbbv": f"{completed_3bv}/{timeline.total_3bv}",
            "bbbv_per_sec": (
                f"{bbbv_per_sec:.4f}" if bbbv_per_sec is not None else "-"
            ),
            "clicks": ReplayStatisticsAnalyzer._format_replay_click_counter(
                entry.active_total,
                entry.wasted_total,
            ),
            "left": ReplayStatisticsAnalyzer._format_replay_click_counter(
                entry.active_left,
                entry.wasted_left,
            ),
            "right": ReplayStatisticsAnalyzer._format_replay_click_counter(
                entry.active_right,
                entry.wasted_right,
            ),
            "chord": ReplayStatisticsAnalyzer._format_replay_click_counter(
                entry.active_chord,
                entry.wasted_chord,
            ),
            "cps": ReplayStatisticsAnalyzer._format_replay_rate(
                total_clicks,
                replay_time,
            ),
            "efficiency": ReplayStatisticsAnalyzer._format_counter_percent(
                completed_3bv,
                total_clicks,
            ),
            "ioe": ReplayStatisticsAnalyzer._format_counter_decimal(
                completed_3bv,
                total_clicks,
            ),
            "ops": f"{completed_ops}/{timeline.total_ops}",
            "thrp": ReplayStatisticsAnalyzer._format_counter_decimal(
                completed_3bv,
                active_clicks,
            ),
            "corr": ReplayStatisticsAnalyzer._format_counter_decimal(
                active_clicks,
                total_clicks,
            ),
            "zini": str(board_zini) if board_zini is not None else "-",
            "zne": "-",
            "znt": "-",
        }

        if board_zini is not None:
            stats["zne"] = ReplayStatisticsAnalyzer._format_counter_decimal(
                board_zini,
                total_clicks,
            )
            stats["znt"] = ReplayStatisticsAnalyzer._format_counter_decimal(
                board_zini,
                active_clicks,
            )

        return stats

    @staticmethod
    def masked_statistics() -> dict[str, str]:
        return {key: "-" for key in STAT_KEYS}

    @staticmethod
    def _entry_at(
        timeline: ReplayCounterTimeline,
        index: int,
    ) -> ReplayCounterEntry | None:
        if not timeline.entries:
            return None
        bounded_index = max(0, min(index, len(timeline.entries) - 1))
        return timeline.entries[bounded_index]

    @staticmethod
    def _completed_ops_from_public_observation(
        observation,
        analysis: BoardAnalysis,
    ) -> int:
        opened_groups = set()
        for y, row in enumerate(observation):
            for x, value in enumerate(row):
                if analysis.cell_class[y][x] != CellClass.OPENING:
                    continue
                if value != 0:
                    continue
                group_id = analysis.opening_id[y][x]
                if group_id >= 0:
                    opened_groups.add(group_id)
        return len(opened_groups)

    @staticmethod
    def _format_counter_decimal(numerator: int, denominator: int) -> str:
        if denominator == 0:
            return "-"
        return f"{numerator / denominator:.4f}"

    @staticmethod
    def _format_counter_percent(numerator: int, denominator: int) -> str:
        if denominator == 0:
            return "-"
        return f"{numerator / denominator * 100:.0f}%"

    @staticmethod
    def _format_replay_rate(numerator: int, elapsed: float) -> str:
        if elapsed <= 0.0:
            return "-"
        return f"{numerator / elapsed:.4f}"

    @staticmethod
    def _format_replay_click_counter(active: int, wasted: int) -> str:
        if wasted == 0:
            return str(active)
        return f"{active} + {wasted}"
