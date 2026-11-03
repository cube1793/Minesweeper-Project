"""Bounded, public-only review of physical flags before a Live V1 adoption.

Every physical FLAG is removed from the *detached review view*, including the
flag being checked.  Existing direct zero/all rules plus the public total-mine
zero/all rule are the complete proof scope.  There is no propagation, exact
enumeration, probability rounding, layout access, or physical input here.
UNVERIFIED means no proof in this scope; it does not mean safe or incorrect.
In particular, stronger inference may prove a flag which this review removes.
"""

from dataclasses import dataclass, fields
from hashlib import sha256
import json

from core_engine import CellState
from simple_algorithm import (
    Constraint, InconsistentObservationError, build_constraints,
    infer_deterministic,
)


HIDDEN = int(CellState.HIDDEN)
FLAGGED = int(CellState.FLAGGED)
PROVED_MINE = "PROVED_MINE"
PROVED_SAFE = "PROVED_SAFE"
UNVERIFIED = "UNVERIFIED"
REVIEW_SCOPE = "LOCAL_DIRECT_WITH_TOTAL_V1"
MAX_CELLS = 480


class FlagReviewError(ValueError):
    """A review value, identity, partition, or reuse is inadmissible."""


def _require(condition, message):
    if not condition:
        raise FlagReviewError(message)


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _row_major(cells):
    return tuple(sorted(cells, key=lambda cell: (cell[1], cell[0])))


def _detach(observation, num_mines):
    _require(type(observation) in (tuple, list) and 1 <= len(observation) <= 16,
             "Review needs 1..16 public rows.")
    _require(type(observation[0]) in (tuple, list) and 1 <= len(observation[0]) <= 30,
             "Review needs 1..30 public columns.")
    width, height = len(observation[0]), len(observation)
    _require(_integer(num_mines, 0, width * height - 1), "Invalid public total mine count.")
    detached = []
    for row in observation:
        _require(type(row) in (tuple, list) and len(row) == width, "Review rows must be rectangular.")
        _require(all(type(value) in (int, CellState)
                     and (value in (HIDDEN, FLAGGED) or 0 <= value <= 8) for value in row),
                 "Review accepts only public PLAYING glyphs.")
        detached.append(tuple(int(value) for value in row))
    return tuple(detached)


def _view_identity(view, num_mines):
    # The original FLAG set is separately bound in FlagReview.flags.  Views
    # differing only by eligible physical removals intentionally share identity.
    raw = json.dumps([len(view[0]), len(view), num_mines, view],
                     ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return sha256(raw).hexdigest()


def _constraints(view, num_mines):
    hidden = frozenset((x, y) for y, row in enumerate(view)
                       for x, value in enumerate(row) if value == HIDDEN)
    # This is a public total-mine constraint, not a physical FLAG assumption.
    return (*build_constraints(view), Constraint((-1, -1), num_mines, hidden)), hidden


def _check_fact_budget(safe, mines, hidden, num_mines):
    if safe & mines:
        raise InconsistentObservationError("Review has conflicting direct safe/mine proofs.")
    if len(mines) > num_mines or num_mines > len(hidden - safe):
        raise InconsistentObservationError("Direct review facts contradict the public total mine count.")


def _check_direct_witnesses(view, num_mines, flags, proved_mine, proved_safe, unverified):
    """Check bounded proof witnesses in a DTO; never run inference/search.

    Each zero/all witness is a public clue (at most eight neighbors) or the
    public total.  This cheap check also rejects a relabelled wire partition.
    Only review_flags calls infer_deterministic, in the public-only worker.
    """
    constraints, hidden = _constraints(view, num_mines)
    safe, mines = set(), set()
    for constraint in constraints:
        if constraint.remaining_mines == 0:
            safe.update(constraint.hidden_cells)
        elif constraint.remaining_mines == len(constraint.hidden_cells):
            mines.update(constraint.hidden_cells)
    _check_fact_budget(safe, mines, hidden, num_mines)
    flag_set = set(flags)
    _require(set(proved_mine) == flag_set & mines
             and set(proved_safe) == flag_set & safe
             and set(unverified) == flag_set - mines - safe,
             "Review partition does not match its direct public proof witnesses.")


@dataclass(frozen=True)
class FlagReview:
    width: int
    height: int
    num_mines: int
    view: tuple
    view_identity: str
    flags: tuple
    proved_mine: tuple
    proved_safe: tuple
    unverified: tuple
    scope: str = REVIEW_SCOPE

    def __post_init__(self):
        _require(_integer(self.width, 1, 30) and _integer(self.height, 1, 16),
                 "Invalid review dimensions.")
        _require(_integer(self.num_mines, 0, self.width * self.height - 1),
                 "Invalid review total mine count.")
        _require(type(self.view) is tuple and len(self.view) == self.height
                 and all(type(row) is tuple and len(row) == self.width
                         and all(type(value) is int and (value == HIDDEN or 0 <= value <= 8)
                                 for value in row) for row in self.view),
                 "Review view must be detached, rectangular, and FLAG-free.")
        _require(type(self.view_identity) is str
                 and self.view_identity == _view_identity(self.view, self.num_mines),
                 "Review public view identity mismatch.")
        _require(type(self.scope) is str and self.scope == REVIEW_SCOPE, "Unsupported flag proof scope.")
        for name in ("flags", "proved_mine", "proved_safe", "unverified"):
            cells = getattr(self, name)
            _require(type(cells) is tuple and len(cells) <= MAX_CELLS,
                     f"Invalid review {name} collection.")
            _require(all(type(cell) is tuple and len(cell) == 2
                         and _integer(cell[0], 0, self.width - 1)
                         and _integer(cell[1], 0, self.height - 1)
                         and self.view[cell[1]][cell[0]] == HIDDEN for cell in cells),
                     f"Review {name} needs current closed coordinates.")
            _require(len(set(cells)) == len(cells) and _row_major(cells) == cells,
                     f"Review {name} must be unique and in row-major order.")
        mine, safe, unknown = set(self.proved_mine), set(self.proved_safe), set(self.unverified)
        _require(not (mine & safe or mine & unknown or safe & unknown)
                 and mine | safe | unknown == set(self.flags),
                 "Review must partition the complete original physical FLAG set.")
        _check_direct_witnesses(self.view, self.num_mines, self.flags,
                                self.proved_mine, self.proved_safe, self.unverified)

    @property
    def removable(self):
        """Deterministic preparation order: increasing row, then column."""
        return _row_major((*self.proved_safe, *self.unverified))

    def classification(self, target):
        _require(type(target) is tuple and len(target) == 2
                 and _integer(target[0], 0, self.width - 1)
                 and _integer(target[1], 0, self.height - 1) and target in self.flags,
                 "Classification requires an original reviewed FLAG coordinate.")
        if target in self.proved_mine:
            return PROVED_MINE
        if target in self.proved_safe:
            return PROVED_SAFE
        return UNVERIFIED


def review_flags(observation, num_mines):
    """Review once without touching a board, recorder, counter, or UI.

    Failure and contradiction propagate.  No failure is converted to an
    all-UNVERIFIED result.  Runtime compute time is bounded by the owning job.
    """
    current = _detach(observation, num_mines)
    flags = tuple((x, y) for y, row in enumerate(current)
                  for x, value in enumerate(row) if value == FLAGGED)
    view = tuple(tuple(HIDDEN if value == FLAGGED else value for value in row) for row in current)
    constraints, hidden = _constraints(view, num_mines)
    facts = infer_deterministic(constraints)
    _check_fact_budget(facts.safe_cells, facts.mine_cells, hidden, num_mines)
    flag_set = set(flags)
    return FlagReview(len(view[0]), len(view), num_mines, view, _view_identity(view, num_mines),
                      flags, _row_major(flag_set & facts.mine_cells),
                      _row_major(flag_set & facts.safe_cells),
                      _row_major(flag_set - facts.mine_cells - facts.safe_cells))


def validate_review_current(report, observation, num_mines):
    """Allow reuse only while the public view is unchanged by eligible removals.

    Owner/generation/revision/token and the exact removal-prefix checks belong
    to the Live protocol.  This function does not authorize a physical input.
    """
    _require(type(report) is FlagReview, "Expected a detached flag review.")
    report.__post_init__()
    current = _detach(observation, num_mines)
    view = tuple(tuple(HIDDEN if value == FLAGGED else value for value in row) for row in current)
    _require(num_mines == report.num_mines and view == report.view
             and _view_identity(view, num_mines) == report.view_identity,
             "Flag review no longer matches the current public view.")
    flags = {(x, y) for y, row in enumerate(current)
             for x, value in enumerate(row) if value == FLAGGED}
    _require(flags <= set(report.flags) and set(report.proved_mine) <= flags,
             "Flag review cannot add flags or remove a proved-mine flag.")
    return report


def report_to_dict(report):
    _require(type(report) is FlagReview, "Expected FlagReview.")
    report.__post_init__()
    result = {field.name: getattr(report, field.name) for field in fields(FlagReview)}
    result["view"] = [list(row) for row in report.view]
    for name in ("flags", "proved_mine", "proved_safe", "unverified"):
        result[name] = [list(cell) for cell in getattr(report, name)]
    return result


def report_from_dict(value):
    _require(type(value) is dict and set(value) == {field.name for field in fields(FlagReview)},
             "Invalid FlagReview wire fields.")
    data = dict(value)
    _require(type(data["view"]) is list and all(type(row) is list for row in data["view"]),
             "Wire review view must be JSON arrays.")
    data["view"] = tuple(tuple(row) for row in data["view"])
    for name in ("flags", "proved_mine", "proved_safe", "unverified"):
        _require(type(data[name]) is list and len(data[name]) <= MAX_CELLS
                 and all(type(cell) is list for cell in data[name]),
                 f"Wire review {name} must be bounded JSON arrays.")
        data[name] = tuple(tuple(cell) for cell in data[name])
    return FlagReview(**data)
