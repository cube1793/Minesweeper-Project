"""Qt-independent presentation timing for an already accepted comparison.

The three native streams remain separate authorities. Projections retain only
immutable targets/times, never an Engine, decision, timing table or execution.
One controller belongs to one run; callers update only the selected controller.

A state's completed_index is the *due presentation prefix*, not proof that a
board has been applied. The UI must apply it through SameBoardPlayback (which
remains the committed-board/index authority), then render once after catch-up.
If application fails, align to the player's actual committed index and stop.
This module neither applies actions nor introduces a synchronized run clock.
"""

from bisect import bisect_right
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from math import isfinite
from time import monotonic_ns
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from replay_model import ReplayEvent
    from same_board_runner import SameBoardExecution
    from stage3_runner import Stage3ActionTrace


Coordinate = tuple[int, int]
INDEX_INTERVAL_MIN_MS = 20
INDEX_INTERVAL_MAX_MS = 5000
INDEX_INTERVAL_DEFAULT_MS = 200


class TimingAuthority(Enum):
    REPLAY_TIME = "Replay Time"
    MODEL_C_TIME = "Model C Time"


class PlaybackMode(Enum):
    INDEX = "Index"
    REPLAY_TIME = "Replay Time"
    MODEL_C_TIME = "Model C Time"


def _coordinate(value) -> Coordinate:
    if (not isinstance(value, (tuple, list)) or len(value) != 2
            or any(type(part) is not int or part < 0 for part in value)):
        raise ValueError("A target/cursor must contain two nonnegative integers.")
    return tuple(value)


def _microseconds(value) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Model C cost must be nonnegative integer microseconds.")
    return value


@dataclass(frozen=True)
class RunTiming:
    """Nonempty completed-run projection, with native time units explicit.

    Human completion times are exact Fractions of stored Replay seconds;
    solver completion times are integer Model C microseconds. Neither is a
    shared/comparable Human-versus-solver elapsed-time axis.
    """

    authority: TimingAuthority
    targets: tuple[Coordinate, ...]
    completion_times: tuple[Fraction | int, ...]
    initial_cursor: Coordinate

    def __post_init__(self):
        if type(self.authority) is not TimingAuthority:
            raise ValueError("A declared Replay Time or Model C Time authority is required.")
        targets = tuple(_coordinate(target) for target in self.targets)
        times = tuple(self.completion_times)
        initial = _coordinate(self.initial_cursor)
        if not targets or len(targets) != len(times):
            raise ValueError("A completed comparison run needs nonempty aligned targets/times.")
        previous = 0
        for value in times:
            if self.authority is TimingAuthority.MODEL_C_TIME:
                _microseconds(value)
            elif type(value) is not Fraction:
                raise ValueError("Replay boundaries must be exact rational seconds.")
            if value < previous:
                raise ValueError("Completion boundaries must be nonnegative and nondecreasing.")
            previous = value
        if self.authority is TimingAuthority.REPLAY_TIME and initial != targets[0]:
            raise ValueError("Human synthetic initial cursor must be the first action target.")
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "completion_times", times)
        object.__setattr__(self, "initial_cursor", initial)

    @property
    def action_count(self) -> int:
        return len(self.targets)

    @property
    def time_unit(self) -> str:
        return "seconds" if self.authority is TimingAuthority.REPLAY_TIME else "microseconds"

    @property
    def initial_cursor_policy(self) -> str:
        return ("first action target (synthetic, no recorded prior origin)"
                if self.authority is TimingAuthority.REPLAY_TIME
                else "retained Model C initial cursor")

    @property
    def total_time(self) -> Fraction | int:
        return self.completion_times[-1]


def project_human_timing(events: Iterable["ReplayEvent"]) -> RunTiming:
    """Read only ordered event targets/timestamps, never Mouse Trace coordinates.

    Fraction(float) represents the stored binary float exactly. In particular,
    this does not pass through str/decimal formatting or round to microseconds.
    Empty streams cannot be completed games under Same-board admission.
    """
    targets, times = [], []
    for event in events:
        value = event.elapsed_time
        if (type(value) not in (int, float) or value < 0
                or (type(value) is float and not isfinite(value))):
            raise ValueError("Replay elapsed time must be finite nonnegative seconds.")
        targets.append((event.x, event.y))
        times.append(Fraction(value))
    if not targets:
        raise ValueError("A completed Human comparison run cannot be empty.")
    return RunTiming(TimingAuthority.REPLAY_TIME, tuple(targets), tuple(times), targets[0])


def project_stage2_timing(
    targets: Iterable[Coordinate], *, table: Sequence[Sequence[int]],
    initial_cursor: Coordinate, final_total_us: int,
) -> RunTiming:
    """Project the retained authenticated table once; do not authenticate it again.

    Caller admission owns the table identity and stream validity. Only used
    cells are read here; the table is not retained for subsequent ticks.
    """
    cursor = initial = _coordinate(initial_cursor)
    targets = tuple(_coordinate(target) for target in targets)
    total, times = 0, []
    for target in targets:
        dx, dy = abs(target[0] - cursor[0]), abs(target[1] - cursor[1])
        try:
            cost = table[dx][dy]
        except (IndexError, KeyError, TypeError) as exc:
            raise ValueError("Target displacement is outside the retained Model C table.") from exc
        total += _microseconds(cost)
        times.append(total)
        cursor = target
    if total != _microseconds(final_total_us):
        raise ValueError("Stage-2 projected total differs from the retained Model C total.")
    return RunTiming(TimingAuthority.MODEL_C_TIME, targets, tuple(times), initial)


def project_stage3_timing(
    traces: Iterable["Stage3ActionTrace"], *, initial_cursor: Coordinate, final_total_us: int,
) -> RunTiming:
    """Use native recorded action costs, with no displacement/table recomputation."""
    targets, times, total = [], [], 0
    for trace in traces:
        targets.append((trace.move.x, trace.move.y))
        total += _microseconds(trace.modeled_action_us)
        times.append(total)
    if total != _microseconds(final_total_us):
        raise ValueError("Stage-3 recorded sum differs from the retained Model C total.")
    return RunTiming(TimingAuthority.MODEL_C_TIME, tuple(targets), tuple(times), initial_cursor)


@dataclass(frozen=True)
class SameBoardTimings:
    """Three projections, with no selection state or shared playhead."""

    human: RunTiming
    stage2: RunTiming
    stage3: RunTiming


def project_same_board_timings(execution: "SameBoardExecution") -> SameBoardTimings:
    """Compose projections from an already admitted, completed SameBoardExecution.

    This is not an alternative admission/authentication boundary. Native result
    and metrics totals are cross-checked, not replaced or recalculated as results.
    """
    evaluation = execution.model_c_evaluation
    human = project_human_timing(execution.context.human_replay.events)
    stage2 = project_stage2_timing(
        ((move.x, move.y) for move in execution.stage2_result.moves),
        table=evaluation.table, initial_cursor=evaluation.initial_cursor,
        final_total_us=execution.stage2_metrics.model_c_total_us,
    )
    stage3 = project_stage3_timing(
        execution.stage3_result.traces, initial_cursor=evaluation.initial_cursor,
        final_total_us=execution.stage3_metrics.model_c_total_us,
    )
    if stage3.total_time != _microseconds(execution.stage3_result.total_modeled_us):
        raise ValueError("Stage-3 native result total differs from its retained metrics.")
    return SameBoardTimings(human, stage2, stage3)


@dataclass(frozen=True)
class PresentationState:
    """Sampled state; querying never reads the clock or advances a board.

    pending_action_index is zero-based; completed_index is a count in 0..N.
    playhead is in actions for Index, seconds for Replay Time, microseconds for
    Model C Time. Fractional presentation time never changes recorded boundaries.
    At terminal, pending is None, both targets are the final target, and u is 0.
    UI rendering may apply smoothstep to progress; timing does not apply easing.
    """

    completed_index: int
    pending_action_index: int | None
    segment_start: Coordinate
    segment_end: Coordinate
    progress: Fraction
    playhead: Fraction
    playhead_unit: str
    mode: PlaybackMode
    running: bool

    @property
    def stationary(self) -> bool:
        return self.segment_start == self.segment_end

    @property
    def terminal(self) -> bool:
        return self.pending_action_index is None


class SameBoardTimedPlayback:
    """One run's presentation clock, independent of every other run and board.

    Keep one instance per run; pause the old instance when selecting another.
    update() returns the final due prefix so a caller can apply one ordered
    player seek and render once, rather than rendering every missed frame.
    align() synchronizes to an externally committed index without executing it.
    """

    def __init__(self, timing: RunTiming, *, clock: Callable[[], int] = monotonic_ns):
        if type(timing) is not RunTiming:
            raise ValueError("Playback requires an immutable RunTiming projection.")
        self._timing = timing
        self._clock = clock
        self._mode = PlaybackMode.INDEX
        self._interval_ms = INDEX_INTERVAL_DEFAULT_MS
        self._speed = Fraction(1)
        self._index = 0
        self._playhead = Fraction(0)
        self._running = False
        self._last_ns: int | None = None

    @property
    def timing(self) -> RunTiming:
        return self._timing

    @property
    def interval_ms(self) -> int:
        return self._interval_ms

    @property
    def speed(self) -> Fraction:
        return self._speed

    @property
    def state(self) -> PresentationState:
        timing, index = self.timing, self._index
        terminal = index == timing.action_count
        start = timing.targets[index - 1] if index else timing.initial_cursor
        end = start if terminal else timing.targets[index]
        progress = Fraction(0)
        if not terminal:
            if self._mode is PlaybackMode.INDEX:
                progress = self._playhead - index
            else:
                prior = timing.completion_times[index - 1] if index else 0
                duration = timing.completion_times[index] - prior
                # A manually aligned equal-time boundary is consumed at play(),
                # not by this read-only query. It has no positive motion interval.
                if duration:
                    progress = (self._playhead - prior) / duration
        return PresentationState(
            index, None if terminal else index, start, end, progress,
            self._playhead, "actions" if self._mode is PlaybackMode.INDEX else timing.time_unit,
            self._mode, self._running,
        )

    def align(self, completed_index: int) -> PresentationState:
        """Manual seek/board-error recovery: stop and discard unsampled/partial time."""
        if type(completed_index) is not int or not 0 <= completed_index <= self.timing.action_count:
            raise ValueError("Completed index must be an integer in 0..action_count.")
        self._running = False
        self._last_ns = None
        self._index = completed_index
        boundary = (completed_index if self._mode is PlaybackMode.INDEX else
                    self.timing.completion_times[completed_index - 1] if completed_index else 0)
        self._playhead = Fraction(boundary)
        return self.state

    def stop(self) -> PresentationState:
        """Stop at the last sampled completed prefix; discard partial/unsampled time."""
        return self.align(self._index)

    def set_mode(self, mode: PlaybackMode) -> PresentationState:
        """Stop/alignment on mode change; never translate a Human/solver clock."""
        if type(mode) is not PlaybackMode or mode not in (
                PlaybackMode.INDEX, PlaybackMode(self.timing.authority.value)):
            raise ValueError("Timed mode must match this run's original timing authority.")
        if mode is not self._mode:
            self._mode = mode
            self.align(self._index)
        return self.state

    def play(self) -> PresentationState:
        """Start/resume, including all zero/equal-time actions already due."""
        if not self._running and self._index < self.timing.action_count:
            self._last_ns = self._read_clock()
            self._running = True
            self._advance_to(self._playhead)
        return self.state

    def pause(self) -> PresentationState:
        """Sample through the pause request, then preserve the exact partial state."""
        self.update()
        self._running = False
        return self.state

    def update(self) -> PresentationState:
        if self._running:
            now = self._read_clock()
            elapsed_ns = now - self._last_ns
            self._last_ns = now
            if self._mode is PlaybackMode.INDEX:
                advance = Fraction(elapsed_ns, self.interval_ms * 1_000_000)
            else:
                divisor = 1_000_000_000 if self.timing.authority is TimingAuthority.REPLAY_TIME else 1000
                advance = Fraction(elapsed_ns, divisor) * self.speed
            self._advance_to(self._playhead + advance)
        return self.state

    def set_speed(self, speed: int | float | Fraction) -> PresentationState:
        if (type(speed) not in (int, float, Fraction)
                or (type(speed) is float and not isfinite(speed))):
            raise ValueError("Time speed must be an exact quarter-step from 0.25x through 8x.")
        speed = Fraction(speed)
        if not Fraction(1, 4) <= speed <= 8 or (speed * 4).denominator != 1:
            raise ValueError("Time speed must be an exact quarter-step from 0.25x through 8x.")
        if self._mode is not PlaybackMode.INDEX:
            self.update()  # Elapsed time belongs to the old rate.
        self._speed = speed
        return self.state

    def set_interval(self, interval_ms: int) -> PresentationState:
        if type(interval_ms) is not int or not INDEX_INTERVAL_MIN_MS <= interval_ms <= INDEX_INTERVAL_MAX_MS:
            raise ValueError("Index interval must be an integer in 20..5000 ms.")
        if self._mode is PlaybackMode.INDEX:
            self.update()  # Preserve normalized segment progress at the old interval.
        self._interval_ms = interval_ms
        return self.state

    def _read_clock(self) -> int:
        try:
            now = self._clock()
            if type(now) is not int or now < 0:
                raise ValueError("Clock must return nonnegative integer nanoseconds.")
            if self._last_ns is not None and now < self._last_ns:
                raise ValueError("Monotonic clock moved backwards.")
            return now
        except Exception:
            self._running = False
            raise

    def _advance_to(self, position: Fraction) -> None:
        maximum = (self.timing.action_count if self._mode is PlaybackMode.INDEX
                   else self.timing.total_time)
        self._playhead = min(position, Fraction(maximum))
        self._index = (int(self._playhead) if self._mode is PlaybackMode.INDEX else
                       bisect_right(self.timing.completion_times, self._playhead))
        if self._index == self.timing.action_count:
            self._running = False
