"""Replay labels/marks from stored inputs and existing public Simple evidence."""
from dataclasses import replace

from core_engine import CellState, GameStatus


def recorded_input(events, index, observation, status=GameStatus.PLAYING):
    if not 0 <= index < len(events):
        return "녹화된 다음 입력: 없음", None
    event = events[index]
    valid = (0 <= event.y < len(observation)
             and 0 <= event.x < len(observation[event.y]))
    action = event.action
    if (status == GameStatus.PLAYING and valid and action == "FLAG"
            and observation[event.y][event.x] == CellState.FLAGGED):
        action = "UNFLAG"
    return (f"녹화된 다음 입력: {action} ({event.x}, {event.y})",
            (event.x, event.y) if valid else None)


def reference_text(presentation, status, error=None):
    if error:
        detail = error
    elif status != GameStatus.PLAYING:
        detail = "게임 종료 (현재 화면)"
    elif presentation is None:
        detail = "분석 대기"
    else:
        detail = (presentation.status_text.replace("추천", "참고 후보")
                  .replace(" | ", " · ").replace(", 확정", " · 확정"))
    return "Simple 참고 분석: " + detail


def reference_overlays(presentation):
    if presentation is None:
        return {}
    # The reference candidate has a text label; only the recorded input is outlined.
    return {c: replace(o, recommended=False) for c, o in presentation.overlays.items()
            if o.kind is not None or o.probability is not None}
