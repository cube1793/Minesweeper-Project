"""Display-only certainty supplement for Live V1 (candidate S3X_INFO_A1).

Public information only: an observation grid (numbers 0..8, HIDDEN, FLAGGED)
and the public total mine count.  No engine, layout, seed or evaluator result
is accepted anywhere in this module.

The frozen V1 planner is not called, replaced or parameterised from here.  Its
decision is made first, by the caller, exactly as before.  This module only
answers a second question for the same public state: which other HIDDEN cells
are already proven safe or mine?  The answer is shown to the player and grants
no input.

Flags are read as mines, as in the frozen solver.  That reading is sound for
the V1 phase of a Live run: the preparation phase removes every flag the public
clues do not prove, and V1 itself flags only proven mines.

  * bounded      -- at most live_policy.INFO_NODE_BUDGET search nodes per public state.  A
    component the bound cannot finish contributes nothing; the pass is then
    PARTIAL and never combined with the global mine count.
  * incremental  -- the per-component count is a pure function of that
    component's constraints and is memoised.  Cells proven for an earlier state
    of the same owner run are substituted first; they stay proven only while the
    public state grows (cells open, flags land on proven mines).
  * no promotion -- a cell is reported only when a finished count leaves it no
    other value.  Nothing is derived from a probability.
"""

from dataclasses import dataclass
from time import perf_counter_ns

from core_engine import CellState
from live_policy import INFO_NODE_BUDGET
from simple_algorithm import Constraint, InconsistentObservationError, build_constraints
from simple_probability import _ComponentCounts, _combinations, _convolve, _split_components
from stage3_planner import certainty_pool


MEMO_ENTRIES = 512
COMPLETE = "COMPLETE"
PARTIAL = "PARTIAL"


class BudgetExceeded(Exception):
    """The bounded search used up its nodes; this component has no result."""


def enumerate_component_bounded(component, node_limit):
    """simple_probability._enumerate_component with a node counter.

    Same variable order, value order, pruning test and leaf accumulation.  The
    only addition is counting tried values: trying one more than ``node_limit``
    raises BudgetExceeded.  Returns (counts, nodes).
    """
    memberships = {cell: [] for cell in component.cells}
    for index, constraint in enumerate(component.constraints):
        for cell in constraint.hidden_cells:
            memberships[cell].append(index)
    ordered_cells = sorted(
        component.cells, key=lambda cell: (-len(memberships[cell]), cell[1], cell[0]),
    )
    incident = [memberships[cell] for cell in ordered_cells]
    targets = [constraint.remaining_mines for constraint in component.constraints]
    unassigned = [len(constraint.hidden_cells) for constraint in component.constraints]
    assigned = [0] * len(component.constraints)
    count = len(ordered_cells)
    values = [0] * count
    next_values = [0] * count
    ways = {}
    mine_ways = {cell: {} for cell in component.cells}

    depth = 0
    mine_count = 0
    nodes = 0
    while depth >= 0:
        if next_values[depth] == 2:
            next_values[depth] = 0
            depth -= 1
            if depth >= 0:
                value = values[depth]
                for index in incident[depth]:
                    assigned[index] -= value
                    unassigned[index] += 1
                mine_count -= value
            continue

        if nodes >= node_limit:
            raise BudgetExceeded(nodes)
        value = next_values[depth]
        next_values[depth] += 1
        nodes += 1
        feasible = True
        for index in incident[depth]:
            taken = assigned[index] + value
            left = unassigned[index] - 1
            assigned[index] = taken
            unassigned[index] = left
            if taken > targets[index] or taken + left < targets[index]:
                feasible = False
        if not feasible:
            for index in incident[depth]:
                assigned[index] -= value
                unassigned[index] += 1
            continue

        values[depth] = value
        mine_count += value
        if depth + 1 == count:
            ways[mine_count] = ways.get(mine_count, 0) + 1
            for cell, is_mine in zip(ordered_cells, values):
                if is_mine:
                    histogram = mine_ways[cell]
                    histogram[mine_count] = histogram.get(mine_count, 0) + 1
            for index in incident[depth]:
                assigned[index] -= value
                unassigned[index] += 1
            mine_count -= value
        else:
            depth += 1

    if not ways:
        raise InconsistentObservationError(
            f"Constraint component containing {component.cells[0]} "
            "has no valid assignment."
        )
    return _ComponentCounts(
        ways=dict(sorted(ways.items())),
        mine_ways={cell: dict(sorted(counts.items())) for cell, counts in mine_ways.items()},
    ), nodes


@dataclass(frozen=True)
class Outcome:
    """Every HIDDEN cell proven for one public state, carried proofs included.

    COMPLETE: every component was counted and combined with the public mine
    count.  PARTIAL: the node bound stopped at least one component; ``safe`` and
    ``mines`` then hold only what finished counts prove on their own.
    """

    status: str
    safe: frozenset
    mines: frozenset
    nodes: int
    skipped: int
    components: int
    enumerated: int
    reused: int
    elapsed_ns: int


class CertaintyEngine:
    """State of one owner run: a pure-function memo and carried proofs."""

    def __init__(self):
        self._counts = {}       # solved component -> counts (pure function of the key)
        self._too_large = {}    # exact search problem -> largest node limit it exceeded
        self._previous = None
        self._num_mines = None
        self._safe = frozenset()
        self._mines = frozenset()

    @property
    def known_safe(self):
        return self._safe

    @property
    def known_mines(self):
        return self._mines

    def _sync(self, grid, num_mines):
        """Keep carried proofs only across a monotone public extension."""
        previous = self._previous
        reset = False
        if previous is None:
            reset = bool(self._safe or self._mines)
        elif (num_mines != self._num_mines or len(previous) != len(grid)
                or len(previous[0]) != len(grid[0])):
            reset = True
        else:
            hidden, flagged = int(CellState.HIDDEN), int(CellState.FLAGGED)
            for y, (before_row, after_row) in enumerate(zip(previous, grid)):
                if before_row == after_row:
                    continue
                for x, (before, after) in enumerate(zip(before_row, after_row)):
                    if before == after:
                        continue
                    if before != hidden:
                        reset = True          # an opened / flagged cell changed
                    elif after == flagged:
                        reset = reset or (x, y) not in self._mines
                    elif (x, y) in self._mines:
                        reset = True          # a proven mine was opened as a number
                if reset:
                    break
        if reset:
            self._safe = frozenset()
            self._mines = frozenset()
        self._previous = grid
        self._num_mines = num_mines
        return reset

    def _adopt(self, grid, num_mines, safe, mines):
        hidden = frozenset((x, y) for y, row in enumerate(grid) for x, value in enumerate(row)
                           if value == CellState.HIDDEN)
        self._sync(grid, num_mines)
        self._safe = (self._safe | frozenset(safe)) & hidden
        self._mines = (self._mines | frozenset(mines)) & hidden
        if self._safe & self._mines:
            raise InconsistentObservationError("A cell is proven both safe and mine.")
        return hidden

    def note_facts(self, observation, num_mines, safe, mines):
        """Adopt proofs the frozen planner made for exactly this public state."""
        self._adopt(tuple(tuple(int(value) for value in row) for row in observation),
                    num_mines, safe, mines)

    def analyze(self, observation, num_mines, *, node_budget, constraints=None, facts=None):
        """Prove what the node bound allows for one public state.

        ``constraints`` may be build_constraints(observation) for this very
        observation.  ``facts`` is a pair (safe, mines) already proven for this
        state.  Any exception leaves this object unusable: the owner discards it.
        """
        started = perf_counter_ns()
        if isinstance(num_mines, bool) or not isinstance(num_mines, int):
            raise ValueError("num_mines must be an integer.")
        if type(node_budget) is not int or node_budget <= 0:
            raise ValueError("node_budget must be a positive integer.")
        if constraints is None:
            constraints = build_constraints(observation)
        grid = tuple(tuple(int(value) for value in row) for row in observation)
        hidden_cells = tuple((x, y) for y, row in enumerate(grid) for x, value in enumerate(row)
                             if value == CellState.HIDDEN)
        flag_count = sum(value == CellState.FLAGGED for row in grid for value in row)
        remaining_mines = num_mines - flag_count
        if not 0 <= remaining_mines <= len(hidden_cells):
            raise InconsistentObservationError(
                f"num_mines={num_mines}, flag_count={flag_count}: remaining_mines="
                f"{remaining_mines} must be between 0 and {len(hidden_cells)} hidden cells."
            )
        self._adopt(grid, num_mines, *(facts or ((), ())))
        status, safe, mines, statistics = self._solve(
            constraints, hidden_cells, remaining_mines, node_budget)
        self._safe, self._mines = safe, mines
        return Outcome(status, safe, mines, *statistics, perf_counter_ns() - started)

    def _solve(self, constraints, hidden_cells, remaining_mines, node_budget):
        known_safe, known_mines = self._safe, self._mines
        known = known_safe | known_mines
        if known:
            # A contradiction with a proven cell surfaces here, in Constraint.
            reduced = tuple(
                constraint if constraint.hidden_cells.isdisjoint(known) else Constraint(
                    source=constraint.source,
                    remaining_mines=constraint.remaining_mines
                    - len(constraint.hidden_cells & known_mines),
                    hidden_cells=constraint.hidden_cells - known,
                )
                for constraint in constraints
            )
            free_cells = tuple(cell for cell in hidden_cells if cell not in known)
            free_mines = remaining_mines - len(known_mines)
            if not 0 <= free_mines <= len(free_cells):
                raise InconsistentObservationError("Proven cells exceed the public mine count.")
        else:
            reduced, free_cells, free_mines = constraints, hidden_cells, remaining_mines

        components = _split_components(reduced)
        counts = []
        enumerated = reused = skipped = nodes = 0
        left = node_budget
        for component in components:
            # A repeated identical constraint does not change the solution set.
            solved = (component.cells, frozenset(
                (constraint.remaining_mines, constraint.hidden_cells)
                for constraint in component.constraints))
            found = self._counts.get(solved)
            if found is not None:
                counts.append(found)
                reused += 1
                continue
            # The search itself (and so its node count) also depends on order and repeats.
            problem = (component.cells, tuple(
                (constraint.remaining_mines, constraint.hidden_cells)
                for constraint in component.constraints))
            if left <= self._too_large.get(problem, 0):
                counts.append(None)   # known not to finish within what is left
                skipped += 1
                continue
            try:
                found, used = enumerate_component_bounded(component, left)
            except BudgetExceeded:
                self._remember(self._too_large, problem, left)
                nodes += left
                left = 0
                counts.append(None)
                skipped += 1
                continue
            nodes += used
            left -= used
            self._remember(self._counts, solved, found)
            counts.append(found)
            enumerated += 1

        safe, mines = set(known_safe), set(known_mines)
        for component, found in zip(components, counts):
            if found is not None:   # fixed in every assignment of a fully counted component
                safe.update(cell for cell in component.cells if not found.mine_ways[cell])
                mines.update(cell for cell in component.cells
                             if found.mine_ways[cell] == found.ways)
        statistics = (nodes, skipped, len(components), enumerated, reused)

        if skipped:
            # No global combination. Only the bound the finished counts already imply.
            finished = [found for found in counts if found is not None]
            open_cells = len(free_cells) - sum(
                len(component.cells) for component, found in zip(components, counts)
                if found is not None)
            if (sum(min(found.ways) for found in finished) > free_mines
                    or free_mines - sum(max(found.ways) for found in finished) > open_cells):
                raise InconsistentObservationError(
                    "Counted components contradict the public mine count.")
            return PARTIAL, frozenset(safe), frozenset(mines), statistics

        frontier = {cell for component in components for cell in component.cells}
        floating = [cell for cell in free_cells if cell not in frontier]
        floating_count = len(floating)
        prefix = [{0: 1}]
        for found in counts:
            prefix.append(_convolve(prefix[-1], found.ways))
        suffix = [{} for _ in range(len(counts) + 1)]
        suffix[-1] = {0: 1}
        for index in range(len(counts) - 1, -1, -1):
            suffix[index] = _convolve(counts[index].ways, suffix[index + 1])
        all_ways = prefix[-1]
        total_worlds = sum(
            ways * _combinations(floating_count, free_mines - used)
            for used, ways in all_ways.items()
        )
        if total_worlds == 0:
            raise InconsistentObservationError(
                "No complete board satisfies the observation and total num_mines."
            )
        for index, found in enumerate(counts):
            other_ways = _convolve(prefix[index], suffix[index + 1])
            completion_weights = {
                used: sum(
                    ways * _combinations(floating_count, free_mines - used - other)
                    for other, ways in other_ways.items()
                )
                for used in found.ways
            }
            for cell, histogram in found.mine_ways.items():
                worlds = sum(ways * completion_weights[used] for used, ways in histogram.items())
                if worlds == 0:
                    safe.add(cell)
                elif worlds == total_worlds:
                    mines.add(cell)
        if floating_count:
            worlds = sum(
                ways * _combinations(floating_count - 1, free_mines - used - 1)
                for used, ways in all_ways.items()
            )
            if worlds == 0:
                safe.update(floating)
            elif worlds == total_worlds:
                mines.update(floating)
        return COMPLETE, frozenset(safe), frozenset(mines), statistics

    @staticmethod
    def _remember(memo, key, value):
        if len(memo) >= MEMO_ENTRIES:
            memo.pop(next(iter(memo)))
        memo[key] = value


class InfoSupplement:
    """Owned by one worker run; consulted once per planned V1 decision.

    Inference state follows the owner's own input sequence and nothing else: a
    snapshot of another run, board or generation, or one that is not the next
    recorded input, starts from nothing.  ``discard`` drops everything.
    """

    def __init__(self):
        self._engine = None
        self._owner = None
        self._step = None

    def discard(self):
        self._engine = self._owner = self._step = None

    def supplement(self, snapshot, evidence):
        """Outcome of the bounded pass on a local-route state, else None.

        ``evidence`` is the frozen decision's evidence for ``snapshot``.  On the
        exact route the frozen step already proved every certain cell; they are
        only noted, so the next local-route pass starts from them.
        """
        owner = (snapshot.run_id, snapshot.board_generation, snapshot.entry_mode,
                 snapshot.fixed_game_id, snapshot.width, snapshot.height, snapshot.num_mines)
        step = (snapshot.input_seq, snapshot.input_revision)
        if (self._engine is None or owner != self._owner
                or step != (self._step[0] + 1, self._step[1] + 1)):
            self._engine = CertaintyEngine()
        self._owner, self._step = owner, step
        try:
            safe, mines = certainty_pool(evidence)
            if evidence.probability_result is not None:
                self._engine.note_facts(snapshot.observation, snapshot.num_mines, safe, mines)
                return None
            return self._engine.analyze(
                snapshot.observation, snapshot.num_mines, node_budget=INFO_NODE_BUDGET,
                constraints=evidence.constraints, facts=(safe, mines))
        except BaseException:
            self.discard()   # a pass that did not finish leaves nothing to build on
            raise
