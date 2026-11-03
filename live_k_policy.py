"""K-P0 Live public protocol and a worker-only persistent decision owner.

Only primitive projections cross the wire. K inference/selection/validation
imports occur in KOwner, never while importing Main or the default V1 worker.
M revisions count successful analyses, not physical inputs or acquired cells.
The snapshot's base M is the last ACK's M; a pending decision may already own
more M. Discarding that decision means retiring the entire owner.
"""

from dataclasses import dataclass, fields, replace
from time import perf_counter_ns
from uuid import uuid4

from core_engine import Action, CellState, GameStatus
from live_policy import (
    POLICY_K, _coordinate, _detach_grid, _grid, _identity, _integer, _object,
    _require, _neighbors, supports_v1_board,
)
from simple_algorithm import SimpleMove
from stage3_physical import PROFILE_SHA256, TABLE_SHA256


DEFINITION = "K_P0_NATIVE_DEFAULT_FIRST_INPUT_V1"
MAX_K_INPUTS = 480
MAX_VALIDATIONS_PER_INPUT = 64
MAX_K_SEQUENCE = MAX_K_INPUTS * (MAX_VALIDATIONS_PER_INPUT + 2) + 1
supports_board = supports_v1_board


def _mines(value, state):
    return (type(value) is tuple and len(value) <= state.num_mines
            and all(_coordinate(cell, state.width, state.height) for cell in value)
            and tuple(sorted(set(value), key=lambda c: (c[1], c[0]))) == value)


def _ordered(value):
    return tuple(sorted(value, key=lambda c: (c[1], c[0])))


@dataclass(frozen=True)
class KSnapshot:
    run_id: str
    board_generation: int
    input_seq: int
    width: int
    height: int
    num_mines: int
    observation: tuple
    cursor: tuple
    input_revision: int
    base_m_revision: int = 0
    base_m: tuple = ()
    policy_id: str = POLICY_K
    definition: str = DEFINITION
    status: str = "PLAYING"
    profile_sha256: str = PROFILE_SHA256
    table_sha256: str = TABLE_SHA256

    def __post_init__(self):
        _require(_identity(self.run_id) and _integer(self.board_generation), "Invalid K owner identity.")
        _require(_integer(self.width, 1, 30) and _integer(self.height, 1, 16)
                 and _integer(self.num_mines, 0, self.width * self.height - 1), "Invalid K dimensions/mines.")
        _require(_integer(self.input_seq, 0, self.width * self.height)
                 and _integer(self.input_revision) and self.input_revision == self.input_seq,
                 "K canonical owner input/revision bound mismatch.")
        _require(_integer(self.base_m_revision, 0, MAX_K_INPUTS)
                 and self.base_m_revision == max(0, self.input_seq - 1), "Invalid K base M revision.")
        _require(_grid(self.observation, self.width, self.height)
                 and _coordinate(self.cursor, self.width, self.height), "Invalid K public grid/cursor.")
        for value, expected in ((self.policy_id, POLICY_K), (self.definition, DEFINITION),
                                (self.status, "PLAYING"), (self.profile_sha256, PROFILE_SHA256),
                                (self.table_sha256, TABLE_SHA256)):
            _require(type(value) is str and value == expected, "K policy/definition/status/profile mismatch.")
        _require(_mines(self.base_m, self), "Invalid K base M projection.")
        _require(all(self.observation[y][x] in (-2, -3) for x, y in self.base_m), "Base M became revealed.")
        flags = {(x, y) for y, row in enumerate(self.observation) for x, v in enumerate(row) if v == -3}
        _require(flags <= set(self.base_m), "Physical flags must belong to acknowledged K M.")


def make_snapshot(**kwargs):
    kwargs['observation'] = _detach_grid(kwargs['observation'])
    _require(type(kwargs['cursor']) in (tuple, list), "Invalid cursor.")
    kwargs['cursor'] = tuple(kwargs['cursor'])
    return KSnapshot(**kwargs)


def validate_start_snapshot(state):
    _require(type(state) is KSnapshot, "K START requires KSnapshot.")
    state.__post_init__()
    _require(state.input_seq == state.input_revision == state.base_m_revision == 0
             and not state.base_m and state.cursor == (0, 0)
             and all(v == -2 for row in state.observation for v in row),
             "K START requires canonical fresh origin and empty M; ADOPT is unsupported.")
    return state


@dataclass(frozen=True)
class ExactGuessProbabilities:
    """Display-only exact marginals, bound to a proposal by its enclosing DTO.

    At most 480 binary cells give fewer than 2**480 worlds. All arithmetic
    stays integral; the selected numerator is checked against the same table.
    This is a projection, never a replacement for the worker's proof graph.
    """

    total_worlds: int
    cells: tuple  # (x, y, mine_worlds), in public reading order
    minimum_risk_cells: tuple
    selected_mine_worlds: int

    def __post_init__(self):
        _require(_integer(self.total_worlds, 1, 1 << MAX_K_INPUTS), "Invalid exact denominator.")
        _require(type(self.cells) is tuple and 0 < len(self.cells) <= MAX_K_INPUTS,
                 "Invalid exact cell count.")
        _require(all(type(c) is tuple and len(c) == 3 and _coordinate(c[:2], 30, 16)
                     and _integer(c[2], 1, self.total_worlds - 1) for c in self.cells),
                 "Invalid strictly uncertain exact marginal.")
        coordinates = tuple(c[:2] for c in self.cells)
        _require(coordinates == _ordered(set(coordinates)), "Duplicate/unordered exact coordinates.")
        minimum = min(c[2] for c in self.cells)
        _require(type(self.minimum_risk_cells) is tuple
                 and all(_coordinate(c, 30, 16) for c in self.minimum_risk_cells)
                 and self.minimum_risk_cells == tuple(c[:2] for c in self.cells if c[2] == minimum),
                 "Exact minimum candidate mismatch.")
        _require(_integer(self.selected_mine_worlds, 1, self.total_worlds - 1)
                 and self.selected_mine_worlds == minimum, "Selected exact probability mismatch.")


def project_exact_guess(decision, selection):
    """Read the original selected EXACT_GUESS once; perform no new inference."""
    _require(decision.continuation == 'EXACT_GUESS' and decision.phase_e is not None
             and selection.evidence is decision
             and (selection.move.x, selection.move.y) == decision.guess_target,
             "Exact display projection differs from original K selection.")
    exact = decision.phase_e
    counts = dict(exact.mine_worlds)
    return ExactGuessProbabilities(
        exact.total_worlds, tuple((x, y, count) for (x, y), count in exact.mine_worlds),
        _ordered(exact.minimum_risk_cells), counts[decision.guess_target],
    )


@dataclass(frozen=True)
class KProposal:
    snapshot: KSnapshot
    token: str
    action: str
    x: int
    y: int
    kind: str
    category: str
    continuation: str
    modeled_action_us: int
    compute_ns: int
    pending_m_revision: int
    preinput_m: tuple
    probabilities: ExactGuessProbabilities | None = None

    def __post_init__(self):
        _require(type(self.snapshot) is KSnapshot, "Expected K snapshot.")
        s = self.snapshot
        s.__post_init__()
        _require(s.input_seq < s.width * s.height and _identity(self.token), "K input bound/token.")
        _require(type(self.action) is str and self.action in ("OPEN", "FLAG", "CHORD")
                 and _coordinate((self.x, self.y), s.width, s.height), "Invalid K first input.")
        _require(type(self.kind) is str and self.kind in ("initial", "certain", "guess"), "Invalid K kind.")
        _require(type(self.category) is str and type(self.continuation) is str, "Invalid K projection labels.")
        _require(_integer(self.modeled_action_us, 1) and _integer(self.compute_ns), "Invalid K timings.")
        _require(_integer(self.pending_m_revision, 0, MAX_K_INPUTS)
                 and self.pending_m_revision == s.base_m_revision + (0 if self.initial else 1),
                 "K pending M revision mismatch.")
        _require(_mines(self.preinput_m, s) and set(s.base_m) <= set(self.preinput_m)
                 and all(s.observation[y][x] in (-2, -3) for x, y in self.preinput_m),
                 "Invalid pending M acquisition.")
        if self.is_guess:
            _require(type(self.probabilities) is ExactGuessProbabilities, "Missing exact guess probabilities.")
            exact = self.probabilities
            exact.__post_init__()
            unresolved = tuple((x, y) for y, row in enumerate(s.observation) for x, glyph in enumerate(row)
                               if glyph == -2 and (x, y) not in self.preinput_m)
            _require(tuple(c[:2] for c in exact.cells) == unresolved,
                     "Exact probabilities must cover current unresolved cells only.")
            counts = {(x, y): n for x, y, n in exact.cells}
            _require((self.x, self.y) in exact.minimum_risk_cells
                     and counts.get((self.x, self.y)) == exact.selected_mine_worlds,
                     "Selected target/probability mismatch.")
            _require(sum(counts.values()) == (s.num_mines - len(self.preinput_m)) * exact.total_worlds,
                     "Exact marginal mine budget mismatch.")
        else:
            _require(self.probabilities is None, "Only EXACT_GUESS carries display probabilities.")
        if self.initial:
            validate_start_snapshot(s)
            _require((self.action, self.x, self.y, self.category, self.continuation)
                     == ("OPEN", 0, 0, "POLICY_INITIAL_OPEN", "INITIAL")
                     and not self.preinput_m and self.compute_ns == 0, "Invalid K initial policy.")
            return
        _require(s.input_seq > 0 and self.continuation in ("LOCAL_SAFE", "EXACT_SAFE", "EXACT_GUESS"),
                 "Invalid K continuation.")
        _require(self.is_guess == (self.continuation == "EXACT_GUESS"), "K guess continuation mismatch.")
        glyph = s.observation[self.y][self.x]
        if self.action == "FLAG":
            _require(not self.is_guess and self.category == "SETUP_CHORD" and glyph == -2
                     and (self.x, self.y) in self.preinput_m, "K FLAG requires owned M and SETUP_CHORD.")
        elif self.action == "OPEN":
            _require(glyph == -2 and (self.x, self.y) not in self.preinput_m
                     and self.category == ("EXACT_MINIMUM_RISK_GUESS" if self.is_guess else "DIRECT_SAFE_OPEN"),
                     "Invalid projected K OPEN.")
        else:
            adjacent = _neighbors(self.x, self.y, s.width, s.height)
            _require(not self.is_guess and self.category == "DIRECT_CHORD" and 1 <= glyph <= 8
                     and sum(s.observation[y][x] == -3 for x, y in adjacent) == glyph
                     and any(s.observation[y][x] == -2 for x, y in adjacent), "Invalid physical K CHORD.")

    @property
    def move(self):
        return SimpleMove(Action[self.action], self.x, self.y)

    @property
    def initial(self):
        return self.kind == "initial"

    @property
    def is_guess(self):
        return self.kind == "guess"


def admit_proposal(proposal, current):
    _require(type(proposal) is KProposal and type(current) is KSnapshot, "Invalid K public admission.")
    proposal.__post_init__()
    current.__post_init__()
    _require(proposal.snapshot == current, "Stale K public state/binding.")
    return proposal


@dataclass(frozen=True)
class KValidation:
    snapshot: KSnapshot
    token: str
    nonce: str
    pending_m_revision: int

    def __post_init__(self):
        _require(type(self.snapshot) is KSnapshot, "Invalid VALIDATE snapshot.")
        self.snapshot.__post_init__()
        _require(_identity(self.token) and _identity(self.nonce)
                 and _integer(self.pending_m_revision, 0, MAX_K_INPUTS), "Invalid VALIDATE binding.")


@dataclass(frozen=True)
class KPermit:
    proposal: KProposal
    nonce: str

    def __post_init__(self):
        _require(type(self.proposal) is KProposal and _identity(self.nonce), "Invalid K permit.")
        self.proposal.__post_init__()


@dataclass(frozen=True)
class KAck:
    permit: KPermit
    status: str
    observation: tuple | None
    input_revision: int
    cursor: tuple

    def __post_init__(self):
        _require(type(self.permit) is KPermit, "K ACK requires exact permit.")
        self.permit.__post_init__()
        p = self.permit.proposal
        s = p.snapshot
        _require(type(self.status) is str and self.status in ("PLAYING", "WON", "LOST"), "Invalid K ACK status.")
        _require(_integer(self.input_revision) and self.input_revision == s.input_revision + 1
                 and _coordinate(self.cursor, s.width, s.height) and self.cursor == (p.x, p.y),
                 "Invalid K ACK revision/cursor.")
        if self.status != "PLAYING":
            _require(self.observation is None, "Terminal K ACK carries no observation.")
        else:
            _require(_grid(self.observation, s.width, s.height), "Invalid K ACK public grid.")

    @property
    def run_id(self):
        return self.permit.proposal.snapshot.run_id

    @property
    def token(self):
        return self.permit.proposal.token

    @property
    def input_seq(self):
        return self.permit.proposal.snapshot.input_seq


def make_ack(permit, status, observation=None):
    _require(type(permit) is KPermit, "Expected consumed K permit.")
    if type(status) is GameStatus:
        status = status.name
    # Status first, so a terminal payload is never even iterated.
    _require(status == "PLAYING" or observation is None, "Terminal ACK must be observation=None.")
    p = permit.proposal
    return KAck(permit, status, None if observation is None else _detach_grid(observation),
                p.snapshot.input_revision + 1, (p.x, p.y))


def next_snapshot(proposal, ack):
    """Structural parent check; full effect validation is worker-owned below."""
    _require(type(proposal) is KProposal and type(ack) is KAck, "Invalid K ACK values.")
    proposal.__post_init__()
    ack.__post_init__()
    _require(ack.permit.proposal == proposal, "ACK differs from pending K action/token/bindings.")
    if ack.status != "PLAYING":
        return None
    return replace(proposal.snapshot, input_seq=proposal.snapshot.input_seq + 1,
                   input_revision=ack.input_revision, cursor=ack.cursor, observation=ack.observation,
                   base_m_revision=proposal.pending_m_revision, base_m=proposal.preinput_m)


# Explicit codecs: no reflection-driven class selection or proof graph transport.
def to_dict(value):
    _require(type(value) in (KSnapshot, KProposal, KValidation, KPermit, KAck, ExactGuessProbabilities), "Unknown K DTO.")
    value.__post_init__()
    result = {f.name: getattr(value, f.name) for f in fields(value)}
    for name in ("snapshot", "proposal", "permit", "probabilities"):
        if name in result and result[name] is not None:
            result[name] = to_dict(result[name])
    for name in ("observation", "base_m", "preinput_m", "cells", "minimum_risk_cells"):
        if name in result and result[name] is not None:
            result[name] = [list(row) for row in result[name]]
    if "cursor" in result:
        result['cursor'] = list(result['cursor'])
    return result


def from_dict(value, cls):
    _require(cls in (KSnapshot, KProposal, KValidation, KPermit, KAck, ExactGuessProbabilities), "Unknown K DTO type.")
    data = _object(value, cls)
    for name, child in (("snapshot", KSnapshot), ("proposal", KProposal), ("permit", KPermit),
                        ("probabilities", ExactGuessProbabilities)):
        if name in data and (name != 'probabilities' or data[name] is not None):
            data[name] = from_dict(data[name], child)
    for name in ("observation", "base_m", "preinput_m", "cells", "minimum_risk_cells"):
        if name in data and data[name] is not None:
            _require(type(data[name]) is list and len(data[name]) <= MAX_K_INPUTS
                     and all(type(row) is list and len(row) <= 30 for row in data[name]),
                     "Invalid K wire array.")
            data[name] = tuple(tuple(row) for row in data[name])
    if 'cursor' in data:
        _require(type(data['cursor']) is list, "K wire cursor must be an array.")
        data['cursor'] = tuple(data['cursor'])
    return cls(**data)


class KOwner:
    """Used only by the selected K worker; one session and original graph."""

    def __init__(self, snapshot, table):
        from stage3_physical import validate_timing_table
        from experiments.program_k_capability import KLocalSession
        from experiments.program_k_policy import select_policy
        from experiments.program_k_runner import validate_k_p0_execution, _validate_progress

        validate_start_snapshot(snapshot)
        self.session = KLocalSession(snapshot.width, snapshot.height, snapshot.num_mines)
        self._select = select_policy
        self._validate = validate_k_p0_execution
        self._progress = _validate_progress
        self.table = validate_timing_table(table)
        self.expected = snapshot
        self.pending = self.decision = self.selection = self.permit = None
        self.closed = False
        self._nonces = set()

    def propose(self, snapshot):
        from stage3_physical import action_cost

        _require(not self.closed and self.pending is None and snapshot == self.expected,
                 "K analysis requires explicit NEXT after exact ACK.")
        snapshot.__post_init__()
        _require(_ordered(self.session.M) == snapshot.base_m, "K session differs from acknowledged M.")
        self.expected = None  # Even a native failure must never re-analyze this session.
        initial = snapshot.input_seq == 0
        if initial:
            move, category, continuation, kind, elapsed = SimpleMove(Action.OPEN, 0, 0), 'POLICY_INITIAL_OPEN', 'INITIAL', 'initial', 0
        else:
            started = perf_counter_ns()
            self.decision = self.session.analyze_decision(snapshot.observation, status=GameStatus.PLAYING)
            self.selection = self._select(self.decision, snapshot.cursor, self.table)
            elapsed = perf_counter_ns() - started
            move, category = self.selection.move, self.selection.category
            continuation = self.decision.continuation
            kind = 'guess' if continuation == 'EXACT_GUESS' else 'certain'
        self.pending = KProposal(snapshot, uuid4().hex, move.action.name, move.x, move.y, kind,
                                 category, continuation, action_cost(self.table, snapshot.cursor, (move.x, move.y)),
                                 elapsed, snapshot.base_m_revision + (not initial), _ordered(self.session.M),
                                 project_exact_guess(self.decision, self.selection) if kind == 'guess' else None)
        self.expected = None
        self._nonces.clear()
        return self.pending

    def validate(self, request):
        _require(not self.closed and self.pending is not None and type(request) is KValidation,
                 "K VALIDATE requires retained pending.")
        request.__post_init__()
        p = admit_proposal(self.pending, request.snapshot)
        _require(request.token == p.token and request.pending_m_revision == p.pending_m_revision
                 and request.nonce not in self._nonces and len(self._nonces) < MAX_VALIDATIONS_PER_INPUT,
                 "K validation token/revision/nonce/budget mismatch.")
        current_mines = self.session.M  # Read live owned M, never archived evidence.
        self._validate(request.snapshot.observation, p.move, status=GameStatus.PLAYING,
                       num_mines=request.snapshot.num_mines, cursor=request.snapshot.cursor,
                       current_mines=current_mines, decision=self.decision, selection=self.selection,
                       initial=p.initial)
        _require(_ordered(current_mines) == p.preinput_m, "Current K M differs from pending projection.")
        self._nonces.add(request.nonce)
        self.permit = KPermit(p, request.nonce)
        return self.permit

    def acknowledge(self, ack):
        _require(not self.closed and self.pending is not None and self.permit is not None
                 and type(ack) is KAck, "K ACK requires admission.")
        ack.__post_init__()
        _require(ack.permit == self.permit, "K ACK permit/nonce differs from last admission.")
        following = next_snapshot(self.pending, ack)
        if ack.status == 'PLAYING':
            self._progress(self.pending.snapshot.observation, ack.observation, self.pending.move)
        else:
            self.closed = True
        self.expected = following
        self.pending = self.decision = self.selection = self.permit = None
        return following
