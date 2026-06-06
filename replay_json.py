"""
replay_json.py
JSON serialization helpers for one-game replay data.

This module deliberately only handles JSON-compatible conversion and file I/O.
Replay validation remains centralized in replay_model dataclasses.
"""

import json
from pathlib import Path

from replay_model import ReplayBoard, ReplayData, ReplayEvent


def replay_data_to_dict(replay_data: ReplayData) -> dict:
    """Convert ReplayData to a JSON-serializable dictionary."""
    return {
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

    return ReplayData(
        board=board,
        events=events,
        source_type=data.get("source_type", "human"),
        schema_version=data.get("schema_version", 1),
    )


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


def _coordinates_from_json(value) -> frozenset[tuple[int, int]]:
    if not isinstance(value, list):
        raise ValueError("Replay JSON coordinates must be a list.")

    coordinates = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("Replay JSON coordinate must be a two-item list.")
        coordinates.append((item[0], item[1]))
    return frozenset(coordinates)
