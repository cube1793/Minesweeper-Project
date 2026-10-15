"""
replay_json.py
JSON serialization helpers for one-game replay data.

This module deliberately only handles JSON-compatible conversion and file I/O.
Replay validation remains centralized in replay_model dataclasses.
"""

import json
from pathlib import Path

from mouse_trace import MouseTraceData, MouseTracePoint, MouseTraceSegment
from replay_model import ReplayBoard, ReplayData, ReplayEvent


def replay_data_to_dict(replay_data: ReplayData) -> dict:
    """Convert ReplayData to a JSON-serializable dictionary."""
    data = {
        "schema_version": replay_data.schema_version,
        "source_type": replay_data.source_type,
        "board": {
            "width": replay_data.board.width,
            "height": replay_data.board.height,
            "num_mines": replay_data.board.num_mines,
            "mine_positions": [
                [x, y] for x, y in sorted(replay_data.board.mine_positions)
            ],
        },
        "events": [
            {
                "elapsed_time": event.elapsed_time,
                "x": event.x,
                "y": event.y,
                "action": event.action,
            }
            for event in replay_data.events
        ],
    }
    if replay_data.mouse_trace is not None:
        trace = replay_data.mouse_trace
        data["mouse_trace"] = {
            "width": trace.width,
            "height": trace.height,
            "segments": [
                {
                    "cell_size": segment.cell_size,
                    "points": [
                        {"elapsed_us": point.elapsed_us, "x": point.x, "y": point.y,
                         "replay_event_index": point.replay_event_index}
                        for point in segment.points
                    ],
                }
                for segment in trace.segments
            ],
        }
    return data


def replay_data_from_dict(data: dict) -> ReplayData:
    """Create ReplayData from a dictionary loaded from JSON."""
    if not isinstance(data, dict):
        raise ValueError("Replay JSON root must be an object.")

    try:
        board_data = data["board"]
        event_data = data["events"]
    except KeyError as exc:
        raise ValueError("Replay JSON is missing a required field.") from exc

    if not isinstance(board_data, dict):
        raise ValueError("Replay JSON board must be an object.")
    if not isinstance(event_data, list):
        raise ValueError("Replay JSON events must be a list.")

    board = _board_from_dict(board_data)
    events = tuple(_event_from_dict(event) for event in event_data)
    schema_version = data.get("schema_version", 1)
    if schema_version == 1 and "mouse_trace" in data:
        raise ValueError("Replay schema v1 cannot contain mouse_trace.")
    trace = _mouse_trace_from_dict(data["mouse_trace"]) if "mouse_trace" in data else None

    return ReplayData(
        board=board,
        events=events,
        source_type=data.get("source_type", "human"),
        schema_version=schema_version,
        mouse_trace=trace,
    )


def _mouse_trace_from_dict(data) -> MouseTraceData:
    """Check JSON containers; pure trace models own value/order validation."""
    if not isinstance(data, dict):
        raise ValueError("Replay JSON mouse_trace must be an object.")
    try:
        if not isinstance(data["segments"], list):
            raise ValueError("Mouse Trace segments must be a list.")
        segments = []
        for segment in data["segments"]:
            if not isinstance(segment, dict) or not isinstance(segment.get("points"), list):
                raise ValueError("Mouse Trace segment must be an object with a points list.")
            points = []
            for point in segment["points"]:
                if not isinstance(point, dict):
                    raise ValueError("Mouse Trace point must be an object.")
                points.append(MouseTracePoint(point["elapsed_us"], point["x"], point["y"],
                                              point["replay_event_index"]))
            segments.append(MouseTraceSegment(segment["cell_size"], tuple(points)))
        return MouseTraceData(data["width"], data["height"], tuple(segments))
    except KeyError as exc:
        raise ValueError("Replay JSON mouse_trace is missing a required field.") from exc


def save_replay_json(replay_data: ReplayData, path) -> None:
    """Save ReplayData as a deterministic UTF-8 JSON file."""
    target = Path(path)
    with target.open("w", encoding="utf-8") as file:
        json.dump(
            replay_data_to_dict(replay_data),
            file,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        file.write("\n")


def load_replay_json(path) -> ReplayData:
    """Load ReplayData from a UTF-8 JSON file."""
    source = Path(path)
    with source.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return replay_data_from_dict(data)


def _board_from_dict(data: dict) -> ReplayBoard:
    try:
        mine_positions = data["mine_positions"]
        board = ReplayBoard(
            width=data["width"],
            height=data["height"],
            num_mines=data["num_mines"],
            mine_positions=_coordinates_from_json(mine_positions),
        )
    except KeyError as exc:
        raise ValueError("Replay JSON board is missing a required field.") from exc
    return board


def _event_from_dict(data: dict) -> ReplayEvent:
    if not isinstance(data, dict):
        raise ValueError("Replay JSON event must be an object.")

    try:
        event = ReplayEvent(
            elapsed_time=data["elapsed_time"],
            x=data["x"],
            y=data["y"],
            action=data["action"],
        )
    except KeyError as exc:
        raise ValueError("Replay JSON event is missing a required field.") from exc
    return event


def _coordinates_from_json(value) -> tuple[tuple[object, object], ...]:
    if not isinstance(value, list):
        raise ValueError("Replay JSON coordinates must be a list.")

    coordinates = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("Replay JSON coordinate must be a two-item list.")
        coordinates.append((item[0], item[1]))
    return tuple(coordinates)
