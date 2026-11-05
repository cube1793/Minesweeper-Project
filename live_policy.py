"""Detached public values and one frozen V1 decision for Main Live."""

from dataclasses import dataclass, fields, replace
from fractions import Fraction
from time import perf_counter_ns
from uuid import uuid4

from core_engine import Action, CellState, GameStatus
from live_flag_review import (
    FlagReview, report_from_dict, report_to_dict, review_flags, validate_review_current,
)
from simple_algorithm import SimpleMove
from stage3_physical import PROFILE_SHA256, TABLE_SHA256


POLICY_SIMPLE = "S2_SIMPLE"
POLICY_V1 = "STAGE3_V1"
POLICY_K = "K_P0"
POLICY_K_LC0 = "K_LC0"
POLICY_K_LC1 = "K_LC1"
V1_PRESETS = frozenset({(9, 9, 10), (16, 16, 40), (30, 16, 99)})
PUBLIC_GLYPHS = frozenset({-2, -3, *range(9)})
CANONICAL_NEW = "CANONICAL_NEW"
ADOPT_CURRENT = "ADOPT_CURRENT"
FIXED_BOARD = "FIXED_BOARD"
PHASE_FLAG_REVIEW = "FLAG_REVIEW"
PHASE_V1 = "V1"
MAX_BOARD_CELLS = 480
MAX_V1_INPUTS = 480
MAX_INPUTS = MAX_V1_INPUTS + MAX_BOARD_CELLS


class LivePolicyError(ValueError):
    """A public value, sequence, or actual input is not admissible."""


def _require(condition, detail):
    if not condition:
        raise LivePolicyError(detail)


def _integer(value, low=0, high=2 ** 53 - 1):
    return type(value) is int and low <= value <= high


def _identity(value):
    return (type(value) is str and len(value) == 32
            and all(character in "0123456789abcdef" for character in value))


def _coordinate(value, width, height):
    return (type(value) is tuple and len(value) == 2
            and _integer(value[0], 0, width - 1) and _integer(value[1], 0, height - 1))


def _grid(value, width, height):
    return (type(value) is tuple and len(value) == height
            and all(type(row) is tuple and len(row) == width
                    and all(type(glyph) is int and glyph in PUBLIC_GLYPHS for glyph in row)
                    for row in value))


def _detach_grid(value):
    _require(type(value) in (tuple, list), "Observation must be a public grid.")
    rows = []
    for row in value:
        _require(type(row) in (tuple, list), "Observation rows must be lists or tuples.")
        _require(all(type(glyph) in (int, CellState) for glyph in row), "Public glyphs must be integers.")
        rows.append(tuple(int(glyph) for glyph in row))
    return tuple(rows)


def supports_v1_board(width, height, num_mines):
    return (all(type(value) is int for value in (width, height, num_mines))
            and (width, height, num_mines) in V1_PRESETS)


@dataclass(frozen=True)
class PublicSnapshot:
    run_id: str
    board_generation: int
    input_seq: int
    width: int
    height: int
    num_mines: int
    observation: tuple
    cursor: tuple
    policy_id: str = POLICY_V1
    status: str = "PLAYING"
    entry_mode: str = CANONICAL_NEW
    input_revision: int = 0
    phase: str = PHASE_V1
    initial_flag_count: int = 0
    review_inputs: int = 0
    fixed_game_id: str | None = None

    def __post_init__(self):
        _require(_identity(self.run_id), "Invalid run identity.")
        _require(_integer(self.board_generation), "Invalid board generation.")
        _require(_integer(self.input_seq, 0, MAX_INPUTS), "Invalid input sequence.")
        _require(type(self.entry_mode) is str and self.entry_mode in (CANONICAL_NEW, ADOPT_CURRENT, FIXED_BOARD),
                 "Invalid entry mode.")
        _require((_identity(self.fixed_game_id) and self.input_revision == self.input_seq
                  and self.phase == PHASE_V1 and self.initial_flag_count == self.review_inputs == 0)
                 if self.entry_mode == FIXED_BOARD else self.fixed_game_id is None,
                 "Invalid fixed-board game/revision/phase binding.")
        if self.entry_mode == FIXED_BOARD and self.input_seq == 0:
            _require(self.cursor == (0, 0)
                     and all(v == CellState.HIDDEN for row in self.observation for v in row),
                     "Fixed-board origin must be entirely HIDDEN with origin cursor.")
        _require(_integer(self.input_revision) and self.input_revision >= self.input_seq,
                 "Invalid global input revision.")
        _require(type(self.phase) is str and self.phase in (PHASE_FLAG_REVIEW, PHASE_V1),
                 "Invalid input phase.")
        _require(_integer(self.initial_flag_count, 0, MAX_BOARD_CELLS)
                 and _integer(self.review_inputs, 0, self.initial_flag_count)
                 and 0 <= self.input_seq - self.review_inputs <= MAX_V1_INPUTS
                 and self.input_seq <= MAX_V1_INPUTS + self.initial_flag_count,
                 "Owner phase input bound exceeded.")
        _require(self.phase != PHASE_FLAG_REVIEW
                 or (self.entry_mode == ADOPT_CURRENT and self.initial_flag_count > 0
                     and self.input_seq == self.review_inputs), "Invalid review phase counters.")
        _require(self.entry_mode != CANONICAL_NEW
                 or (self.phase == PHASE_V1 and self.initial_flag_count == self.review_inputs == 0),
                 "Canonical owner cannot acquire a review phase.")
        _require(type(self.policy_id) is str and self.policy_id == POLICY_V1, "Unsupported live policy.")
        _require(type(self.status) is str and self.status == "PLAYING", "Only PLAYING observations enter policy.")
        _require(_integer(self.width, 1, 30) and _integer(self.height, 1, 16), "Board exceeds frozen table.")
        _require(_integer(self.num_mines, 0, self.width * self.height - 1), "Invalid mine count.")
        _require(_grid(self.observation, self.width, self.height), "Invalid detached public observation.")
        _require(_coordinate(self.cursor, self.width, self.height), "Invalid board-cell cursor.")
        _require(self.initial_flag_count <= self.width * self.height, "Flag bound exceeds board cells.")


def make_snapshot(*, run_id, board_generation, input_seq, width, height, num_mines,
                  observation, cursor, policy_id=POLICY_V1, status="PLAYING",
                  entry_mode=CANONICAL_NEW, input_revision=None, phase=PHASE_V1,
                  initial_flag_count=0, review_inputs=0, fixed_game_id=None):
    if type(status) is GameStatus:
        status = status.name
    _require(type(cursor) in (tuple, list), "Cursor must be a coordinate.")
    return PublicSnapshot(run_id, board_generation, input_seq, width, height, num_mines,
                          _detach_grid(observation), tuple(cursor), policy_id, status, entry_mode,
                          input_seq if input_revision is None else input_revision, phase,
                          initial_flag_count, review_inputs, fixed_game_id)


def validate_start_snapshot(snapshot):
    """Validate owner seq0 separately from canonical first-OPEN provenance.

    Placement/fresh UI provenance stays in Main; no hidden state enters here.
    """
    _require(type(snapshot) is PublicSnapshot, "START needs a public snapshot.")
    snapshot.__post_init__()
    _require(snapshot.input_seq == snapshot.review_inputs == 0, "START requires owner input zero.")
    flags = sum(value == CellState.FLAGGED for row in snapshot.observation for value in row)
    if snapshot.entry_mode in (CANONICAL_NEW, FIXED_BOARD):
        _require(snapshot.input_revision == 0 and snapshot.cursor == (0, 0)
                 and all(value == CellState.HIDDEN for row in snapshot.observation for value in row),
                 "Canonical START requires pristine all-HIDDEN origin.")
    else:
        _require(snapshot.initial_flag_count == flags
                 and snapshot.phase == (PHASE_FLAG_REVIEW if flags else PHASE_V1),
                 "ADOPT START must review exactly its current physical flags.")
    return snapshot


@dataclass(frozen=True)
class OverlayCell:
    x: int
    y: int
    kind: str
    mine_worlds: int | None = None
    total_worlds: int | None = None

    def __post_init__(self):
        _require(_integer(self.x, 0, 29) and _integer(self.y, 0, 15), "Invalid overlay coordinate.")
        _require(type(self.kind) is str and self.kind in ("safe", "mine", "guess_candidate", "uncertain"),
                 "Invalid overlay kind.")
        numerator, denominator = self.mine_worlds, self.total_worlds
        if numerator is None and denominator is None:
            _require(self.kind in ("safe", "mine"), "Uncertain overlays need existing probability evidence.")
            return
        _require(type(numerator) is int and type(denominator) is int
                 and 0 <= numerator <= denominator and 0 < denominator < 2 ** 512,
                 "Invalid exact probability projection.")
        _require((self.kind == "safe" and numerator == 0)
                 or (self.kind == "mine" and numerator == denominator)
                 or (self.kind in ("guess_candidate", "uncertain") and 0 < numerator < denominator),
                 "Probability and overlay kind disagree.")


@dataclass(frozen=True)
class Proposal:
    snapshot: PublicSnapshot
    token: str
    action: str
    x: int
    y: int
    kind: str
    modeled_action_us: int
    compute_ns: int
    overlays: tuple
    profile_sha256: str = PROFILE_SHA256
    table_sha256: str = TABLE_SHA256
    phase: str = PHASE_V1
    review: FlagReview | None = None
    review_compute_ns: int = 0

    def __post_init__(self):
        _require(type(self.snapshot) is PublicSnapshot, "Proposal needs a public snapshot.")
        self.snapshot.__post_init__()
        if self.snapshot.input_seq == 0:
            validate_start_snapshot(self.snapshot)
        _require(_identity(self.token), "Invalid decision token.")
        _require(type(self.action) is str and self.action in ("OPEN", "FLAG", "CHORD"), "Invalid action.")
        state = self.snapshot
        _require(_coordinate((self.x, self.y), state.width, state.height), "Invalid action target.")
        _require(type(self.kind) is str and self.kind in ("initial", "certain", "guess", "flag_review"),
                 "Invalid decision kind.")
        _require(_integer(self.modeled_action_us, 1) and _integer(self.compute_ns), "Invalid timing value.")
        _require(type(self.phase) is str and self.phase in (PHASE_FLAG_REVIEW, PHASE_V1)
                 and _integer(self.review_compute_ns), "Invalid proposal phase/review timing.")
        _require((self.kind == "flag_review") == (self.phase == PHASE_FLAG_REVIEW),
                 "Preparation input must have its own explicit phase and kind.")
        if state.phase == PHASE_FLAG_REVIEW:
            remaining = _validate_review_binding(state, self.review)
            if self.is_flag_review:
                _require(bool(remaining) and (self.x, self.y) == remaining[0]
                         and self.action == "FLAG" and self.compute_ns == 0 and not self.overlays,
                         "Review must toggle only its next row-major removable flag.")
            else:
                _require(not remaining, "V1 planning cannot precede flag cleanup.")
        else:
            _require(not self.is_flag_review and self.review is None and self.review_compute_ns == 0,
                     "V1 phase cannot contain a preparation receipt.")
        _require(type(self.profile_sha256) is str and self.profile_sha256 == PROFILE_SHA256
                 and type(self.table_sha256) is str and self.table_sha256 == TABLE_SHA256,
                 "Frozen timing identity mismatch.")
        _require(type(self.overlays) is tuple and len(self.overlays) <= state.width * state.height,
                 "Invalid overlay collection.")
        seen = set()
        for cell in self.overlays:
            _require(type(cell) is OverlayCell, "Invalid overlay record.")
            cell.__post_init__()
            target = (cell.x, cell.y)
            _require(_coordinate(target, state.width, state.height)
                     and state.observation[cell.y][cell.x] == CellState.HIDDEN
                     and target not in seen, "Overlay must identify a unique current HIDDEN cell.")
            seen.add(target)
        if self.is_flag_review:
            _require(state.review_inputs < state.initial_flag_count
                     and state.observation[self.y][self.x] == CellState.FLAGGED,
                     "Preparation needs a current physical flag within its finite bound.")
        elif self.kind == "initial":
            _require(state.entry_mode == CANONICAL_NEW and state.input_seq == 0
                     and state.input_revision == 0 and state.cursor == (0, 0)
                     and self.action == "OPEN" and (self.x, self.y) == (0, 0)
                     and not self.overlays and self.compute_ns == 0
                     and all(glyph == CellState.HIDDEN for row in state.observation for glyph in row),
                     "Initial policy requires canonical all-HIDDEN origin.")
        else:
            _require(state.entry_mode in (ADOPT_CURRENT, FIXED_BOARD) or state.input_seq > 0,
                     "A planned decision cannot replace canonical initial policy.")
            _require(state.input_seq - state.review_inputs < MAX_V1_INPUTS,
                     "V1 input bound exhausted.")
            _validate_projection_move(self)

    @property
    def move(self):
        return SimpleMove(Action[self.action], self.x, self.y)

    @property
    def is_guess(self):
        return self.kind == "guess"

    @property
    def initial(self):
        return self.kind == "initial"

    @property
    def is_flag_review(self):
        return self.phase == PHASE_FLAG_REVIEW


def _validate_review_binding(state, report):
    """Check public proof/identity and the exact row-major removal prefix.

    This performs bounded public DTO validation only; the worker owns inference.
    """
    _require(type(report) is FlagReview, "FLAG_REVIEW needs its classification receipt.")
    try:
        validate_review_current(report, state.observation, state.num_mines)
    except ValueError as exc:
        raise LivePolicyError(f"Invalid flag review receipt: {exc}") from exc
    _require(len(report.flags) == state.initial_flag_count
             and state.review_inputs <= len(report.removable), "Review flag/input count mismatch.")
    expected = set(report.flags) - set(report.removable[:state.review_inputs])
    actual = {(x, y) for y, row in enumerate(state.observation) for x, value in enumerate(row)
              if value == CellState.FLAGGED}
    _require(actual == expected, "Review flags differ from the exact acknowledged removal prefix.")
    return report.removable[state.review_inputs:]


def _neighbors(x, y, width, height):
    return {(nx, ny) for ny in range(max(0, y - 1), min(height, y + 2))
            for nx in range(max(0, x - 1), min(width, x + 2)) if (nx, ny) != (x, y)}


def _validate_projection_move(proposal):
    state = proposal.snapshot
    cells = {(cell.x, cell.y): cell for cell in proposal.overlays}
    target = (proposal.x, proposal.y)
    glyph = state.observation[proposal.y][proposal.x]
    if proposal.is_guess:
        selected = cells.get(target)
        _require(proposal.action == "OPEN" and glyph == CellState.HIDDEN
                 and selected is not None and selected.kind == "guess_candidate",
                 "Guess must retain its projected exact target.")
    elif proposal.action in ("OPEN", "FLAG"):
        selected = cells.get(target)
        required = "safe" if proposal.action == "OPEN" else "mine"
        _require(glyph == CellState.HIDDEN and selected is not None and selected.kind == required,
                 "Certain input must have current projected certainty.")
    else:
        adjacent = _neighbors(proposal.x, proposal.y, state.width, state.height)
        hidden = {cell for cell in adjacent if state.observation[cell[1]][cell[0]] == CellState.HIDDEN}
        flags = {cell for cell in adjacent if state.observation[cell[1]][cell[0]] == CellState.FLAGGED}
        _require(1 <= glyph <= 8 and len(flags) == glyph and bool(hidden)
                 and all(cell in cells and cells[cell].kind == "safe" for cell in hidden),
                 "CHORD needs an actual satisfied clue and current-safe HIDDEN neighbors.")


def admit_proposal(proposal, current_snapshot):
    _require(type(proposal) is Proposal and type(current_snapshot) is PublicSnapshot, "Invalid admission values.")
    proposal.__post_init__()
    current_snapshot.__post_init__()
    _require(proposal.snapshot == current_snapshot, "Stale proposal/public state.")
    return proposal


def plan_snapshot(snapshot, *, table=None, review=None):
    """Review in the worker, or plan frozen V1 once and retain only its first input.

    A cached review is usable only along its exact acknowledged toggle prefix.
    V1 input uses the physical current observation after preparation completes.
    """
    from simple_decision import DecisionKind
    from stage3_physical import action_cost, load_timing_table
    from stage3_planner import plan_position
    from stage3_runner import _validate_execution

    _require(type(snapshot) is PublicSnapshot, "Expected a detached public snapshot.")
    snapshot.__post_init__()
    if snapshot.input_seq == 0:
        validate_start_snapshot(snapshot)
    table = load_timing_table() if table is None else table
    review_compute_ns = 0
    if snapshot.phase == PHASE_FLAG_REVIEW:
        if review is None:
            _require(snapshot.review_inputs == 0, "An interrupted review cannot be recomputed mid-owner.")
            started = perf_counter_ns()
            review = review_flags(snapshot.observation, snapshot.num_mines)
            review_compute_ns = perf_counter_ns() - started
        remaining = _validate_review_binding(snapshot, review)
        if remaining:
            x, y = remaining[0]
            return Proposal(snapshot, uuid4().hex, "FLAG", x, y, "flag_review",
                            action_cost(table, snapshot.cursor, (x, y)), 0, (),
                            phase=PHASE_FLAG_REVIEW, review=review,
                            review_compute_ns=review_compute_ns)
    else:
        _require(review is None, "Completed review evidence cannot enter ordinary V1 planning.")
    _require(snapshot.input_seq - snapshot.review_inputs < MAX_V1_INPUTS,
             "V1 input bound exhausted.")
    decision = None
    overlays = []
    if snapshot.entry_mode == CANONICAL_NEW and snapshot.input_seq == 0:
        _require(snapshot.cursor == (0, 0)
                 and all(value == CellState.HIDDEN for row in snapshot.observation for value in row),
                 "Initial policy requires all-HIDDEN and origin cursor.")
        move, kind, compute_ns = SimpleMove(Action.OPEN, 0, 0), "initial", 0
    else:
        started = perf_counter_ns()
        decision = plan_position(snapshot.observation, snapshot.num_mines, snapshot.cursor, table)
        compute_ns = perf_counter_ns() - started
        move = decision.move
        evidence = decision.evidence
        kind = "guess" if evidence.kind is DecisionKind.PROBABILITY_GUESS else "certain"
        if evidence.probability_result is None:
            for coordinates, label in ((evidence.deterministic_result.safe_cells, "safe"),
                                       (evidence.deterministic_result.mine_cells, "mine")):
                overlays.extend(OverlayCell(x, y, label) for x, y in sorted(coordinates, key=lambda c: (c[1], c[0])))
        else:
            probabilities = evidence.probability_result.probabilities
            minimum = min((Fraction(cell.mine_worlds, cell.total_worlds) for cell in probabilities
                           if 0 < cell.mine_worlds < cell.total_worlds), default=None) if kind == "guess" else None
            for cell in probabilities:
                x, y = cell.coordinate
                if snapshot.observation[y][x] != CellState.HIDDEN:
                    continue
                label = ("safe" if cell.mine_worlds == 0 else "mine" if cell.mine_worlds == cell.total_worlds
                         else "guess_candidate" if minimum is not None and cell.probability == minimum else "uncertain")
                overlays.append(OverlayCell(x, y, label, cell.mine_worlds, cell.total_worlds))
    _validate_execution(snapshot.observation, move, decision)
    return Proposal(snapshot, uuid4().hex, move.action.name, move.x, move.y, kind,
                    action_cost(table, snapshot.cursor, (move.x, move.y)), compute_ns, tuple(overlays),
                    phase=PHASE_V1, review=review, review_compute_ns=review_compute_ns)


@dataclass(frozen=True)
class Ack:
    run_id: str
    board_generation: int
    policy_id: str
    input_seq: int
    token: str
    action: str
    x: int
    y: int
    status: str
    observation: tuple | None
    entry_mode: str = CANONICAL_NEW
    input_revision: int = 1
    phase: str = PHASE_V1

    def __post_init__(self):
        _require(_identity(self.run_id) and _identity(self.token), "Invalid ACK identity.")
        _require(_integer(self.board_generation) and _integer(self.input_seq, 0, MAX_INPUTS), "Invalid ACK sequence.")
        _require(type(self.entry_mode) is str and self.entry_mode in (CANONICAL_NEW, ADOPT_CURRENT, FIXED_BOARD)
                 and _integer(self.input_revision, 1)
                 and type(self.phase) is str and self.phase in (PHASE_FLAG_REVIEW, PHASE_V1),
                 "Invalid ACK entry/revision/phase.")
        _require(type(self.policy_id) is str and self.policy_id == POLICY_V1, "Wrong ACK policy.")
        _require(type(self.action) is str and self.action in ("OPEN", "FLAG", "CHORD"), "Invalid ACK action.")
        _require(_integer(self.x, 0, 29) and _integer(self.y, 0, 15), "Invalid ACK target.")
        _require(type(self.status) is str and self.status in ("PLAYING", "WON", "LOST"), "Invalid ACK status.")
        if self.status == "PLAYING":
            _require(type(self.observation) is tuple and 1 <= len(self.observation) <= 16
                     and type(self.observation[0]) is tuple and 1 <= len(self.observation[0]) <= 30
                     and _grid(self.observation, len(self.observation[0]), len(self.observation)),
                     "PLAYING ACK needs a detached public grid.")
        else:
            _require(self.observation is None, "Terminal ACK must not carry terminal observation/truth.")


def make_ack(proposal, status, observation=None):
    _require(type(proposal) is Proposal, "ACK requires the consumed proposal.")
    if type(status) is GameStatus:
        status = status.name
    ack = Ack(proposal.snapshot.run_id, proposal.snapshot.board_generation, proposal.snapshot.policy_id,
              proposal.snapshot.input_seq, proposal.token, proposal.action, proposal.x, proposal.y,
              status, None if observation is None else _detach_grid(observation),
              proposal.snapshot.entry_mode, proposal.snapshot.input_revision + 1, proposal.phase)
    validate_ack(proposal, ack)
    return ack


def validate_ack(proposal, ack):
    _require(type(proposal) is Proposal and type(ack) is Ack, "Invalid pending/ACK values.")
    proposal.__post_init__()
    ack.__post_init__()
    state = proposal.snapshot
    _require((ack.run_id, ack.board_generation, ack.policy_id, ack.input_seq, ack.token, ack.action, ack.x, ack.y)
             == (state.run_id, state.board_generation, state.policy_id, state.input_seq,
                 proposal.token, proposal.action, proposal.x, proposal.y), "ACK does not match pending action/token.")
    _require((ack.entry_mode, ack.input_revision, ack.phase)
             == (state.entry_mode, state.input_revision + 1, proposal.phase),
             "ACK does not match pending entry/revision/phase.")
    _require(not proposal.is_flag_review or ack.status == "PLAYING",
             "A preparation UNFLAG cannot produce a terminal ACK.")
    if ack.status != "PLAYING":
        return None
    after = ack.observation
    _require(_grid(after, state.width, state.height), "ACK board dimensions changed.")
    hidden = {(x, y) for y, row in enumerate(state.observation) for x, glyph in enumerate(row)
              if glyph == CellState.HIDDEN}
    remaining = {(x, y) for y, row in enumerate(after) for x, glyph in enumerate(row) if glyph == CellState.HIDDEN}
    changed = {(x, y) for y, row in enumerate(state.observation) for x, glyph in enumerate(row) if after[y][x] != glyph}
    target = (proposal.x, proposal.y)
    if proposal.is_flag_review:
        _require(changed == {target} and state.observation[proposal.y][proposal.x] == CellState.FLAGGED
                 and after[proposal.y][proposal.x] == CellState.HIDDEN and len(remaining) == len(hidden) + 1,
                 "Preparation ACK must only toggle its selected FLAG to HIDDEN.")
        review_inputs = state.review_inputs + 1
        phase = PHASE_FLAG_REVIEW if review_inputs < len(proposal.review.removable) else PHASE_V1
        following = replace(state, input_seq=state.input_seq + 1, input_revision=ack.input_revision,
                            observation=after, cursor=target, review_inputs=review_inputs, phase=phase)
        if phase == PHASE_FLAG_REVIEW:
            _validate_review_binding(following, proposal.review)
        return following
    # The frozen V1 phase keeps its original strict HIDDEN-decrease contract.
    _require(len(remaining) < len(hidden) and changed <= hidden, "ACK made no progress or regressed public cells.")
    if proposal.action == "FLAG":
        _require(changed == {target} and after[proposal.y][proposal.x] == CellState.FLAGGED,
                 "FLAG ACK must change only the selected HIDDEN target.")
    else:
        required = {target} if proposal.action == "OPEN" else _neighbors(*target, state.width, state.height) & hidden
        _require(required <= changed and all(0 <= after[y][x] <= 8 for x, y in changed),
                 "Reveal ACK must open selected targets without creating flags.")
    return replace(state, input_seq=state.input_seq + 1, input_revision=ack.input_revision,
                   observation=after, cursor=target, phase=PHASE_V1)


def _object(value, cls):
    _require(type(value) is dict and set(value) == {field.name for field in fields(cls)},
             f"Invalid {cls.__name__} fields.")
    return dict(value)


def snapshot_to_dict(value):
    _require(type(value) is PublicSnapshot, "Expected PublicSnapshot.")
    value.__post_init__()
    result = {field.name: getattr(value, field.name) for field in fields(PublicSnapshot)}
    result["observation"] = [list(row) for row in value.observation]
    result["cursor"] = list(value.cursor)
    return result


def snapshot_from_dict(value):
    data = _object(value, PublicSnapshot)
    _require(type(data["observation"]) is list and all(type(row) is list for row in data["observation"])
             and type(data["cursor"]) is list, "Wire grid/cursor must be JSON arrays.")
    data["observation"] = tuple(tuple(row) for row in data["observation"])
    data["cursor"] = tuple(data["cursor"])
    return PublicSnapshot(**data)


def proposal_to_dict(value):
    _require(type(value) is Proposal, "Expected Proposal.")
    value.__post_init__()
    result = {field.name: getattr(value, field.name) for field in fields(Proposal)}
    result["snapshot"] = snapshot_to_dict(value.snapshot)
    result["overlays"] = [{field.name: getattr(cell, field.name) for field in fields(OverlayCell)} for cell in value.overlays]
    result["review"] = None if value.review is None else report_to_dict(value.review)
    return result


def proposal_from_dict(value):
    data = _object(value, Proposal)
    data["snapshot"] = snapshot_from_dict(data["snapshot"])
    _require(type(data["overlays"]) is list and len(data["overlays"]) <= MAX_BOARD_CELLS, "Invalid wire overlays.")
    data["overlays"] = tuple(OverlayCell(**_object(cell, OverlayCell)) for cell in data["overlays"])
    data["review"] = None if data["review"] is None else report_from_dict(data["review"])
    return Proposal(**data)


def ack_to_dict(value):
    _require(type(value) is Ack, "Expected Ack.")
    value.__post_init__()
    result = {field.name: getattr(value, field.name) for field in fields(Ack)}
    result["observation"] = None if value.observation is None else [list(row) for row in value.observation]
    return result


def ack_from_dict(value):
    data = _object(value, Ack)
    if data["observation"] is not None:
        _require(type(data["observation"]) is list and all(type(row) is list for row in data["observation"]),
                 "Wire ACK grid must be JSON arrays.")
        data["observation"] = tuple(tuple(row) for row in data["observation"])
    return Ack(**data)
