"""Pure, lazy ownership of one worker job's ZiNi result and Explorer playback.

The caller owns job orchestration and the authoritative information gate. A
finished job's cleanup must not invalidate this controller; board/mode changes
must. Receive performs transport checks only. Premium and path semantics are
checked once, on explicit request_trace(), using the existing trace backend.
No search, engine access, I/O, timers, or UI operations happen here.
"""

from board_snapshot import BoardSnapshot, Coordinate
from zini_calculator import ZiniMove, ZiniResult
from zini_trace import ZiniTrace, ZiniTracePlayer, ZiniTraceStep, build_zini_trace


def _validate_snapshot_shape(snapshot: BoardSnapshot) -> None:
    """Keep the supplied snapshot immutable without reconstructing board facts."""
    if type(snapshot) is not BoardSnapshot:
        raise ValueError("ZiNi job snapshot must be a BoardSnapshot.")
    if (
        any(type(value) is not int for value in (
            snapshot.width, snapshot.height, snapshot.num_mines,
        ))
        or type(snapshot.mines_placed) is not bool
        or type(snapshot.mines) is not frozenset
        or type(snapshot.adjacent) is not tuple
        or any(
            type(coord) is not tuple or len(coord) != 2
            or any(type(value) is not int for value in coord)
            for coord in snapshot.mines
        )
        or any(
            type(row) is not tuple or any(type(value) is not int for value in row)
            for row in snapshot.adjacent
        )
    ):
        raise ValueError("ZiNi snapshot fields must have immutable primitive shapes.")


def _validate_moves(moves: object, clicks: int) -> tuple[ZiniMove, ...]:
    """Check transport shape, leaving Premium/legality/completion to the builder."""
    if type(moves) is not tuple:
        raise ValueError("ZiNi moves must be a tuple.")
    for index, move in enumerate(moves):
        if type(move) is not ZiniMove:
            raise ValueError(f"ZiNi move {index} must be exactly ZiniMove.")
        if type(move.action) is not str or move.action not in (
            "click", "flag_chord", "fallback_click",
        ):
            raise ValueError(f"ZiNi move {index} has an invalid action.")
        for field in ("x", "y", "clicks_added"):
            if type(getattr(move, field)) is not int:
                raise ValueError(f"ZiNi move {index} {field} must be an integer.")
        if move.x < 0 or move.y < 0 or move.clicks_added <= 0:
            raise ValueError(f"ZiNi move {index} has invalid coordinates/clicks.")
        if move.action == "fallback_click":
            if move.premium is not None:
                raise ValueError(f"ZiNi move {index} fallback premium must be None.")
        elif type(move.premium) is not int:
            raise ValueError(f"ZiNi move {index} premium must be an integer.")
    if clicks != sum(move.clicks_added for move in moves):
        raise ValueError("ZiNi clicks do not match the recorded move total.")
    return moves


class ZiniExplorerController:
    """Single owner of result data; expose immutable answers only when eligible.

    ``ready`` means valid transport is available, not that a trace was built.
    Receipt/build errors are terminal for this job: begin() is the explicit retry
    boundary, and the caller must assign each new job a fresh token. Duplicate
    receipts cannot replace a completed result or reset playback. Gate changes
    hide/reveal a cache without rebuilding it; invalidate() removes the entire
    session, including gate and errors.

    ``clicks`` stays available for the caller's existing Counters policy even if
    trace transport/build fails. ``worker_error`` records failure envelopes from
    the calculator or the caller's process/IPC handling. Malformed receipts and
    post-hoc failures use ``trace_error`` instead.
    """

    def __init__(self):
        self.invalidate()

    def invalidate(self) -> None:
        self._token: int | None = None
        self._snapshot: BoardSnapshot | None = None
        self._clicks: int | None = None
        self._moves: tuple[ZiniMove, ...] | None = None
        self._trace: ZiniTrace | None = None
        self._player: ZiniTracePlayer | None = None
        self._completed = False
        self._eligible = False
        self._worker_error: str | None = None
        self._trace_error: str | None = None

    def begin(self, token: int, snapshot: BoardSnapshot, *, eligible: bool) -> None:
        """Bind the exact immutable snapshot included in this job's payload."""
        if type(token) is not int:
            raise ValueError("ZiNi job token must be an integer.")
        _validate_snapshot_shape(snapshot)
        if type(eligible) is not bool:
            raise ValueError("ZiNi eligibility must be a boolean.")
        self.invalidate()
        self._token = token
        self._snapshot = snapshot
        self._eligible = eligible

    def set_eligible(self, eligible: bool) -> None:
        if type(eligible) is not bool:
            raise ValueError("ZiNi eligibility must be a boolean.")
        self._eligible = eligible

    def receive(self, payload: object, *, expected_token: int) -> bool:
        """Consume a current receipt without propagating malformed-data errors.

        expected_token identifies the caller's actual job/result file. Both it
        and a well-formed payload token must match this session. Stale receipts
        are ignored before inspecting the rest of their data. Invalid tokens
        (including bool) are malformed current receipts, never integer matches.
        """
        if (
            type(expected_token) is not int or expected_token != self._token
            or self._token is None or self._completed
        ):
            return False
        try:
            if type(payload) is not dict:
                raise ValueError("ZiNi worker result must be a dict.")
            token = payload.get("token")
            if type(token) is not int:
                raise ValueError("ZiNi worker token must be an integer.")
            if token != self._token:
                return False
            if "clicks" not in payload or "error" not in payload:
                raise ValueError("ZiNi worker result is missing clicks/error.")
            clicks, error = payload["clicks"], payload["error"]
            if error is not None:
                if (
                    type(error) is not str or clicks is not None
                    or "moves" not in payload or payload["moves"] is not None
                ):
                    raise ValueError("ZiNi worker failure has an invalid shape.")
                self._worker_error = error
            else:
                if type(clicks) is not int or clicks < 0:
                    raise ValueError("ZiNi clicks must be a non-negative integer.")
                # Isolate move/trace failure from the valid Counters value.
                self._clicks = clicks
                self._moves = _validate_moves(payload.get("moves"), clicks)
        except Exception as exc:
            self._trace_error = repr(exc)
        self._completed = True
        return True

    def request_trace(self) -> ZiniTrace | None:
        """Build once on explicit eligible request; cache failures until begin()."""
        if self.state != "ready":
            return None
        if self._trace is None:
            try:
                trace = build_zini_trace(
                    self._snapshot, ZiniResult(self._clicks, self._moves),
                )
                player = ZiniTracePlayer(trace)
            except Exception as exc:
                self._trace_error = repr(exc)
                return None
            self._trace, self._player = trace, player
        return self._trace

    @property
    def token(self) -> int | None:
        return self._token

    @property
    def completed(self) -> bool:
        return self._completed

    @property
    def result_received(self) -> bool:
        return self._completed

    @property
    def eligible(self) -> bool:
        return self._eligible

    @property
    def clicks(self) -> int | None:
        return self._clicks

    @property
    def worker_error(self) -> str | None:
        return self._worker_error

    @property
    def trace_error(self) -> str | None:
        return self._trace_error

    @property
    def error(self) -> str | None:
        return self._worker_error if self._worker_error is not None else self._trace_error

    @property
    def state(self) -> str:
        if not self._eligible or self._token is None:
            return "unavailable"
        if self.error is not None:
            return "error"
        return "ready" if self._completed else "pending"

    @property
    def snapshot(self) -> BoardSnapshot | None:
        return self._snapshot if self._eligible else None

    @property
    def moves(self) -> tuple[ZiniMove, ...] | None:
        return self._moves if self._eligible else None

    @property
    def trace(self) -> ZiniTrace | None:
        """Return an existing cache without causing a build."""
        return self._trace if self._eligible else None

    @property
    def current_index(self) -> int | None:
        return self._player.current_index if self._can_play() else None

    @property
    def step_count(self) -> int | None:
        return self._player.step_count if self._can_play() else None

    @property
    def current_step(self) -> ZiniTraceStep | None:
        return self._player.current_step if self._can_play() else None

    @property
    def revealed(self) -> frozenset[Coordinate]:
        return self._player.revealed if self._can_play() else frozenset()

    @property
    def flagged_mines(self) -> frozenset[Coordinate]:
        return self._player.flagged_mines if self._can_play() else frozenset()

    @property
    def cumulative_clicks(self) -> int | None:
        if not self._can_play():
            return None
        return sum(move.clicks_added for move in self._moves[:self._player.current_index])

    def _can_play(self) -> bool:
        return self._eligible and self._player is not None

    def go_to(self, index: int) -> bool:
        """Delegate validated seeks; unavailable navigation never starts a build."""
        if not self._can_play():
            return False
        self._player.go_to(index)
        return True

    def next(self) -> bool:
        return self._player.next() if self._can_play() else False

    def previous(self) -> bool:
        return self._player.previous() if self._can_play() else False
