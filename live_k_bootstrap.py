"""Public local bootstrap for K flag adoption; never a K policy decision.

The native LocalAnalysis stays with the same session. Its detached summary is
only a binding/display value, not proof authority for an OPEN/CHORD/FLAG move.
"""

from dataclasses import dataclass
from time import perf_counter_ns

from core_engine import GameStatus
from live_policy import _coordinate, _grid, _integer, _require


BOOTSTRAP_SCOPE = "K_NATIVE_LOCAL_ALL_FLAGS_MASKED_V1"


def ordered(cells):
    return tuple(sorted(cells, key=lambda c: (c[1], c[0])))


def mask_flags(observation):
    return tuple(tuple(-2 if v == -3 else v for v in row) for row in observation)


@dataclass(frozen=True)
class KBootstrap:
    width: int
    height: int
    num_mines: int
    original_observation: tuple
    flags: tuple
    mines: tuple
    retained: tuple
    removable: tuple
    proved_safe: tuple
    unverified: tuple
    compute_ns: int
    scope: str = BOOTSTRAP_SCOPE
    local_calls: int = 1

    def __post_init__(self):
        _require(_integer(self.width, 1, 30) and _integer(self.height, 1, 16)
                 and _integer(self.num_mines, 0, self.width * self.height - 1),
                 "Invalid K bootstrap metadata.")
        _require(_grid(self.original_observation, self.width, self.height),
                 "Invalid K bootstrap original observation.")
        for name in ('flags', 'mines', 'retained', 'removable', 'proved_safe', 'unverified'):
            cells = getattr(self, name)
            _require(type(cells) is tuple and len(cells) <= self.width * self.height
                     and all(_coordinate(c, self.width, self.height) for c in cells)
                     and cells == ordered(set(cells)), "Invalid K bootstrap coordinates.")
        flags = {(x, y) for y, row in enumerate(self.original_observation)
                 for x, v in enumerate(row) if v == -3}
        _require(bool(flags) and self.flags == ordered(flags), "Bootstrap must bind all original flags.")
        mines, safe, unknown = set(self.mines), set(self.proved_safe), set(self.unverified)
        _require(len(mines) <= self.num_mines
                 and all(self.original_observation[y][x] in (-2, -3) for x, y in mines),
                 "Invalid K bootstrap M.")
        _require(self.retained == ordered(flags & mines)
                 and self.removable == ordered(flags - mines)
                 and not safe & unknown and safe | unknown == flags - mines,
                 "K bootstrap flag partition mismatch.")
        _require(_integer(self.compute_ns) and type(self.scope) is str and self.scope == BOOTSTRAP_SCOPE
                 and type(self.local_calls) is int and self.local_calls == 1,
                 "Invalid K bootstrap scope/count/timing.")

    def observation_after(self, preparation_seq):
        _require(_integer(preparation_seq, 0, len(self.removable)), "Invalid preparation prefix.")
        removed = set(self.removable[:preparation_seq])
        return tuple(tuple(-2 if (x, y) in removed else value for x, value in enumerate(row))
                     for y, row in enumerate(self.original_observation))


class KFlagPreparation:
    """One original native local result, retained for monotone UNFLAGs only."""

    def __init__(self, session, snapshot):
        _require(not session.M, "K bootstrap requires a fresh empty native session.")
        self.session = session
        self.view = mask_flags(snapshot.observation)
        started = perf_counter_ns()
        self.analysis = session.analyze_local(self.view, status=GameStatus.PLAYING)
        elapsed = perf_counter_ns() - started
        _require(self.analysis.before.M == frozenset() and self.analysis.after.M == session.M,
                 "Bootstrap result differs from its native session.")
        flags = {(x, y) for y, row in enumerate(snapshot.observation)
                 for x, v in enumerate(row) if v == -3}
        removable = flags - session.M
        self.summary = KBootstrap(
            snapshot.width, snapshot.height, snapshot.num_mines, snapshot.observation,
            ordered(flags), ordered(session.M), ordered(flags & session.M), ordered(removable),
            ordered(removable & self.analysis.S_current),
            ordered(removable - self.analysis.S_current), elapsed,
        )

    def validate(self, snapshot):
        """No inference, no previous-state advance, and no synthetic graph."""
        _require(snapshot.bootstrap == self.summary
                 and snapshot.observation == self.summary.observation_after(snapshot.preparation_seq)
                 and self.session.M == self.analysis.after.M
                 and ordered(self.session.M) == self.summary.mines == snapshot.base_m,
                 "Preparation differs from the retained native bootstrap.")

    def validate_target(self, snapshot, target):
        self.validate(snapshot)
        _require(snapshot.preparation_seq < len(self.summary.removable)
                 and target == self.summary.removable[snapshot.preparation_seq]
                 and target not in self.summary.retained
                 and snapshot.observation[target[1]][target[0]] == -3,
                 "Only the next removable physical flag can be toggled.")

