"""Experimental S3D3-A / GUESS_STRUCTURE_V1, stage 3: GUESS_OUTCOME_RECORD_V1.

An in-memory record of one run (or of one segment after a prefix state): every
actual input, the evidence that was fixed BEFORE each guess input, a blocked
proposal if any, the base game result, and an auxiliary loss classification.
The record can be written to an experiment JSON file (format version 1, see
RECORD_FORMAT_KO.md) and read back.

This module imports the standard library only. It makes NO inference and NO
probability call, runs no Engine and never reads a hidden layout: everything
is taken from evidence that already exists. The base result (WON / LOST /
PLAYING) is never replaced by the classification or by a save state. A loss is
classified from the LAST actual input and the evidence attached to that very
input; a blocked proposal or an earlier guess is never used for it.

Limits, stated on purpose: the per-number world counts and the pair geometry
are trusted as recorded (no independent recomputation); a successful save or
load proves neither the original calculation nor the origin of a file; a
loaded record is data, never a permission to send an input. LINKED and
PSEUDO_5050 are not implemented. Not a product Replay format.
Experimental copy only.
"""

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import os


FORMAT = "S3D3_GUESS_OUTCOME_RECORD"
VERSION = 1
POLICY_ID = "S3D3-A"
POLICY_DEFINITION = "GUESS_STRUCTURE_V1"
SELECTION_SCOPE = "FORCED_PAIR_AND_TIE_LOOKAHEAD_V1"
RECORD_STAGE = "GUESS_OUTCOME_RECORD_V1"
POLICY = {"id": POLICY_ID, "definition": POLICY_DEFINITION, "selection_scope": SELECTION_SCOPE,
          "record_stage": RECORD_STAGE}
EVIDENCE_TIMING = {"evidence_created": "BEFORE_EACH_INPUT", "file_written": "AFTER_RUN_END"}
FULL_RUN, SEGMENT, DECLARED = (
    "FULL_RUN_FROM_FIRST_INPUT", "SEGMENT_AFTER_PREFIX_STATE", "DECLARED_TEST_MATERIAL")
SCOPES = (FULL_RUN, SEGMENT, DECLARED)
PLAYING, WON, LOST = "PLAYING", "WON", "LOST"
STATUSES = (PLAYING, WON, LOST)
TERMINAL, GUESS_BLOCKED, SEGMENT_END = "TERMINAL", "GUESS_BLOCKED", "SEGMENT_END"
STOP_REASONS = (TERMINAL, GUESS_BLOCKED, SEGMENT_END)
ACTIONS = ("OPEN", "FLAG", "CHORD")
INITIAL_OPEN, CERTAIN, GUESS, EVIDENCE_NOT_RECORDED = (
    "INITIAL_OPEN", "CERTAIN", "GUESS", "EVIDENCE_NOT_RECORDED")
DECISIONS = (INITIAL_OPEN, CERTAIN, GUESS, EVIDENCE_NOT_RECORDED)
FORCED_5050, TIE_LOOKAHEAD, MIN_RISK, UNCLASSIFIED = (
    "FORCED_5050", "TIE_LOOKAHEAD", "MIN_RISK", "UNCLASSIFIED")
EVIDENCE_KINDS = (FORCED_5050, TIE_LOOKAHEAD, MIN_RISK)
REASON_OF_KIND = {FORCED_5050: "FORCED_5050_FIRST", TIE_LOOKAHEAD: "TIE_LOOKAHEAD",
                  MIN_RISK: "K_LC1_GUESS_KEPT"}
RISK_KIND_OF_KIND = {FORCED_5050: "PROVEN_BY_PAIR_SYMMETRY", TIE_LOOKAHEAD: "COMPUTED_EXACT_MINIMUM",
                     MIN_RISK: "COMPUTED_EXACT_MINIMUM"}
CHANGED_CATEGORY = {FORCED_5050: "FORCED_5050_GUESS", TIE_LOOKAHEAD: "TIE_LOOKAHEAD_GUESS"}
KEPT_CATEGORY = "EXACT_MINIMUM_RISK_GUESS"
COMPUTED, SINGLE, LIMIT = "COMPUTED", "NOT_REQUIRED_SINGLE", "NOT_COMPUTED_CANDIDATE_LIMIT"
LOOKAHEAD_STATUSES = (COMPUTED, SINGLE, LIMIT)
PAIR_CELLS, TIES = "FORCED_PAIR_CELLS", "MIN_RISK_TIES"
RANK_NONE, RANK_S, RANK_COST = "NOT_APPLICABLE", "S_COST_READING", "COST_READING"
OUTSIDE_NOT_COMPUTED = "NOT_COMPUTED"
IMPOSSIBLE, GAME_ENDS, SAFE_CELL_EXISTS, MIN_RISK_GUESS = (
    "IMPOSSIBLE", "GAME_ENDS", "SAFE_CELL_EXISTS", "MIN_RISK_GUESS")
Q_KINDS = (IMPOSSIBLE, GAME_ENDS, SAFE_CELL_EXISTS, MIN_RISK_GUESS)
VERDICT_FORCED, VERDICT_APPARENT = "FORCED_5050", "APPARENT_5050"
CELL_STATES = ("PROVEN_MINE", "REVEALED_NUMBER", "UNRESOLVED_HIDDEN")
INDEPENDENCE_VALUES = ("NOT_APPLICABLE", "INDEPENDENT_PROVEN", "OVERLAPPING_NOT_CLAIMED")
CELL_LIMIT, CALL_LIMIT = 8, 72
HIDDEN, FLAGGED = -2, -3
APPLIES, NOT_APPLICABLE_WON, NOT_APPLICABLE_NOT_FINISHED, INTEGRITY_PROBLEM = (
    "APPLIES", "NOT_APPLICABLE_WON", "NOT_APPLICABLE_NOT_FINISHED", "INTEGRITY_PROBLEM")
BASIS_EVIDENCE, BASIS_INITIAL, BASIS_NOT_RECORDED, BASIS_CERTAIN = (
    "PRE_INPUT_EVIDENCE", "INITIAL_OPEN_WITHOUT_EVIDENCE", "EVIDENCE_NOT_RECORDED", "LOST_ON_CERTAIN_INPUT")
NOT_SAVED, SAVED, SAVE_FAILED, LOADED_FROM_FILE = "NOT_SAVED", "SAVED", "SAVE_FAILED", "LOADED_FROM_FILE"


class GuessRecordError(ValueError):
    """A record (in memory or in a file) that is damaged, incomplete or inconsistent.

    Never converted into UNCLASSIFIED and never repaired by recomputation.
    """

    def __init__(self, code: str, detail: str):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class NumberOutcome:
    """One number k of one candidate; ``worlds`` is Z(g,k) and 0 means impossible."""

    number: int
    worlds: int
    q_kind: str
    q: Fraction | None
    minimum_mine_worlds: int | None
    safe_cells: int
    flood: bool


@dataclass(frozen=True)
class CandidateValue:
    """Recorded look-ahead of one candidate: number outcomes, Z_f, S_v and S_c."""

    cell: tuple
    mine_worlds: int
    total_worlds: int
    mine_neighbors: int
    unresolved_neighbors: int
    calls: int
    outcomes: tuple
    flood_worlds: int
    s_v: Fraction
    s_c: Fraction


@dataclass(frozen=True)
class PairBasis:
    """Recorded judgement of one pair (a before b in reading order)."""

    a: tuple
    b: tuple
    verdict: str
    failed: tuple
    bases: tuple
    distinguishing: tuple
    mine_worlds: tuple
    total_worlds: int


@dataclass(frozen=True)
class PublicState:
    """Public state one guess decision was made from: grid, current M, cursor, exact counts."""

    observation: tuple
    num_mines: int
    mines: tuple
    cursor: tuple
    total_worlds: int
    mine_worlds: tuple


@dataclass(frozen=True)
class GuessEvidence:
    """Evidence fixed BEFORE one guess input.

    ``risk`` belongs to the actual target, ``original_risk`` to the K-LC1
    target. ``kind`` is the guess type; ``lookahead_status`` says whether a
    look-ahead was computed and, if not, why. The two are separate fields.
    """

    kind: str
    selection_reason: str
    target: tuple
    risk: Fraction
    risk_kind: str
    original_target: tuple
    original_risk: Fraction
    is_minimum_risk: bool
    target_changed: bool
    pair: tuple | None
    category: str
    k_lc1_move: tuple
    lookahead_status: str
    lookahead_set: str
    rank_basis: str
    lookahead_cells: tuple
    outside_set_lookahead: str
    planned_calls: int
    actual_calls: int
    target_s_c: Fraction | None
    original_s_v: Fraction | None
    values: tuple
    ranking: tuple
    pair_proofs: tuple
    independence: str
    public_state: PublicState


@dataclass(frozen=True)
class RecordedInput:
    """One input that actually reached the Engine, with the evidence of that very input."""

    index: int
    action: str
    x: int
    y: int
    status_after: str
    decision: str
    evidence: GuessEvidence | None


@dataclass(frozen=True)
class BlockedProposal:
    """A validated guess proposal that was NOT sent (guess OFF). Not an input."""

    input_index: int
    cursor: tuple
    action: str
    x: int
    y: int
    evidence: GuessEvidence


@dataclass(frozen=True)
class LossClassification:
    """Auxiliary classification of a loss; the base result stays in ``final_status``."""

    applicability: str
    kind: str | None
    basis: str | None
    input_index: int | None


@dataclass(frozen=True)
class GuessOutcomeRecord:
    """The whole record. ``final_status`` is the base game result."""

    record_scope: str
    width: int
    height: int
    num_mines: int
    allow_guess: bool
    prefix_inputs: tuple
    inputs: tuple
    blocked: BlockedProposal | None
    final_status: str
    stop_reason: str
    loss: LossClassification

    @property
    def format(self) -> str:
        return FORMAT

    @property
    def version(self) -> int:
        return VERSION


@dataclass(frozen=True)
class SaveOutcome:
    """Result of one save attempt; never a game result."""

    state: str
    path: str | None
    bytes: int | None
    sha256: str | None
    code: str | None
    detail: str | None
    partial_path: str | None


def _need(condition, code, detail):
    if not condition:
        raise GuessRecordError(code, detail)


def _is_int(value) -> bool:
    return type(value) is int


def _is_cell(value) -> bool:
    return type(value) is tuple and len(value) == 2 and _is_int(value[0]) and _is_int(value[1])


def _is_move(value) -> bool:
    return (type(value) is tuple and len(value) == 3 and type(value[0]) is str
            and _is_int(value[1]) and _is_int(value[2]))


def _reading(cell):
    return cell[1], cell[0]


def classify(inputs, final_status) -> LossClassification:
    """Auxiliary loss classification from the LAST actual input and its own evidence.

    Nothing but the recorded decision kind and the evidence attached to that
    input is used: no earlier guess, no blocked proposal, no board.
    """
    if final_status == WON:
        return LossClassification(NOT_APPLICABLE_WON, None, None, None)
    if final_status == PLAYING:
        return LossClassification(NOT_APPLICABLE_NOT_FINISHED, None, None, None)
    _need(final_status == LOST and type(inputs) is tuple and bool(inputs)
          and type(inputs[-1]) is RecordedInput, "RECORD_INPUTS",
          "A loss needs a known base result and a last actual input.")
    last = inputs[-1]
    if last.decision == GUESS:
        _need(type(last.evidence) is GuessEvidence and last.evidence.kind in EVIDENCE_KINDS,
              "RECORD_EVIDENCE", "A guess input without usable pre-input evidence is a damaged record.")
        return LossClassification(APPLIES, last.evidence.kind, BASIS_EVIDENCE, last.index)
    if last.decision == INITIAL_OPEN:
        return LossClassification(APPLIES, UNCLASSIFIED, BASIS_INITIAL, last.index)
    if last.decision == EVIDENCE_NOT_RECORDED:
        return LossClassification(APPLIES, UNCLASSIFIED, BASIS_NOT_RECORDED, last.index)
    _need(last.decision == CERTAIN, "RECORD_INPUTS", "Unknown decision kind of the last input.")
    # A loss on a non-guess input is not a guess loss: reported as an integrity problem.
    return LossClassification(INTEGRITY_PROBLEM, None, BASIS_CERTAIN, last.index)


def _check_value(value, counts, total):
    def need(condition, detail):
        _need(condition, "RECORD_EVIDENCE", detail)

    need(type(value) is CandidateValue and _is_cell(value.cell) and value.cell in counts,
         "A candidate value must belong to an unresolved cell.")
    m, u = value.mine_neighbors, value.unresolved_neighbors
    need(_is_int(value.mine_worlds) and _is_int(value.total_worlds)
         and value.mine_worlds == counts[value.cell] and value.total_worlds == total,
         f"World counts of {value.cell} disagree with the public state.")
    need(_is_int(m) and _is_int(u) and m >= 0 and u >= 0 and m + u <= 8 and _is_int(value.calls)
         and value.calls == u + 1 and type(value.outcomes) is tuple and len(value.outcomes) == u + 1,
         f"Number outcomes of {value.cell} are missing, duplicated or out of range.")
    for offset, outcome in enumerate(value.outcomes):
        need(type(outcome) is NumberOutcome and _is_int(outcome.number) and outcome.number == m + offset
             and _is_int(outcome.worlds) and outcome.worlds >= 0 and _is_int(outcome.safe_cells)
             and outcome.safe_cells >= 0 and type(outcome.flood) is bool
             and outcome.flood is (outcome.number == 0 and u > 0),
             f"Malformed number outcome of {value.cell}.")
        minimum = outcome.minimum_mine_worlds
        if outcome.worlds == 0:
            need(outcome.q_kind == IMPOSSIBLE and outcome.q is None and minimum is None
                 and outcome.safe_cells == 0, "An impossible number has no Q and no ground.")
            continue
        need(minimum is None or (_is_int(minimum) and 0 <= minimum <= outcome.worlds),
             "Ground of Q out of range.")
        if minimum is None or minimum == outcome.worlds:
            kind, q = GAME_ENDS, Fraction(1)
            need(outcome.safe_cells == 0 and not outcome.flood, "A finished game has no safe cell left.")
        elif minimum == 0:
            kind, q = SAFE_CELL_EXISTS, Fraction(1)
            need(outcome.safe_cells > 0, "A safe-cell outcome needs a safe cell.")
        else:
            kind, q = MIN_RISK_GUESS, 1 - Fraction(minimum, outcome.worlds)
            need(outcome.safe_cells == 0 and not outcome.flood, "A guess outcome has no safe cell.")
        need(outcome.q_kind == kind and type(outcome.q) is Fraction and outcome.q == q,
             f"Q of number {outcome.number} of {value.cell} disagrees with its grounds.")
    need(sum(o.worlds for o in value.outcomes) == total - value.mine_worlds,
         f"Number outcomes of {value.cell} do not add up to its safe worlds.")
    flood_worlds = sum(o.worlds for o in value.outcomes if o.flood)
    s_v = sum((Fraction(o.worlds, total) * o.q for o in value.outcomes if o.worlds), Fraction(0))
    s_c = s_v - Fraction(flood_worlds, total)
    need(_is_int(value.flood_worlds) and value.flood_worlds == flood_worlds
         and type(value.s_v) is Fraction and value.s_v == s_v
         and type(value.s_c) is Fraction and value.s_c == s_c
         and 0 <= s_c <= s_v <= 1 - Fraction(value.mine_worlds, total),
         f"Z_f, S_v or S_c of {value.cell} disagrees with its number outcomes.")


def _check_evidence(evidence, width, height, num_mines):
    """Internal consistency of one pre-input evidence. Arithmetic and cross-references only."""
    def need(condition, detail):
        _need(condition, "RECORD_EVIDENCE", detail)

    def inside(cell):
        return _is_cell(cell) and 0 <= cell[0] < width and 0 <= cell[1] < height

    need(type(evidence) is GuessEvidence and type(evidence.public_state) is PublicState,
         "Expected the pre-input evidence of one guess.")
    state = evidence.public_state
    grid = state.observation
    need(type(grid) is tuple and len(grid) == height and all(
        type(row) is tuple and len(row) == width
        and all(_is_int(v) and (v in (HIDDEN, FLAGGED) or 0 <= v <= 8) for v in row) for row in grid),
         "The recorded observation is not a public grid of this board.")
    need(_is_int(state.num_mines) and state.num_mines == num_mines, "Mine total differs from the board.")
    need(type(state.mines) is tuple and all(inside(cell) for cell in state.mines)
         and list(state.mines) == sorted(set(state.mines), key=_reading),
         "Current M must be unique cells in reading order.")
    hidden = {(x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v == HIDDEN}
    flags = {(x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v == FLAGGED}
    mines = set(state.mines)
    need(mines <= hidden | flags and flags <= mines, "Current M disagrees with the recorded grid.")
    unresolved = hidden - mines
    total = state.total_worlds
    need(inside(state.cursor) and _is_int(total) and total > 0 and type(state.mine_worlds) is tuple
         and all(type(item) is tuple and len(item) == 2 and inside(item[0]) and _is_int(item[1])
                 for item in state.mine_worlds),
         "Malformed cursor or exact counts.")
    need(bool(unresolved) and [cell for cell, _ in state.mine_worlds] == sorted(unresolved, key=_reading),
         "Exact counts must cover exactly the unresolved cells, in reading order.")
    counts = dict(state.mine_worlds)
    need(all(0 < count < total for count in counts.values()),
         "A guess decision has only strictly uncertain cells.")
    minimum = min(counts.values())
    ties = tuple(cell for cell, _ in state.mine_worlds if counts[cell] == minimum)
    g0 = ties[0]
    kind = evidence.kind
    need(kind in EVIDENCE_KINDS and evidence.selection_reason == REASON_OF_KIND[kind]
         and evidence.risk_kind == RISK_KIND_OF_KIND[kind],
         "Guess type, selection reason and risk kind contradict each other.")
    need(_is_cell(evidence.target) and evidence.target in unresolved
         and _is_cell(evidence.original_target) and evidence.original_target == g0,
         "Target or original target is not an unresolved cell of this state.")
    need(type(evidence.risk) is Fraction and evidence.risk == Fraction(counts[evidence.target], total)
         and type(evidence.original_risk) is Fraction
         and evidence.original_risk == Fraction(counts[g0], total),
         "A recorded risk is not the ratio of the recorded world counts.")
    need(type(evidence.is_minimum_risk) is bool and type(evidence.target_changed) is bool
         and evidence.is_minimum_risk is (counts[evidence.target] == minimum)
         and evidence.target_changed is (evidence.target != g0)
         and _is_move(evidence.k_lc1_move) and evidence.k_lc1_move == ("OPEN", g0[0], g0[1])
         and evidence.category == (CHANGED_CATEGORY.get(kind) if evidence.target_changed else KEPT_CATEGORY),
         "Flags, K-LC1 move or category contradict the targets.")
    # Look-ahead: set, status, calls and values.
    cells = evidence.lookahead_cells
    need(type(cells) is tuple and bool(cells) and all(_is_cell(cell) and cell in unresolved for cell in cells)
         and list(cells) == sorted(set(cells), key=_reading)
         and evidence.lookahead_set in (PAIR_CELLS, TIES)
         and evidence.rank_basis in (RANK_NONE, RANK_S, RANK_COST)
         and evidence.outside_set_lookahead == OUTSIDE_NOT_COMPUTED,
         "Malformed candidate set.")
    status = SINGLE if len(cells) == 1 else LIMIT if len(cells) > CELL_LIMIT else COMPUTED
    need(evidence.lookahead_status == status and type(evidence.values) is tuple
         and _is_int(evidence.planned_calls) and _is_int(evidence.actual_calls),
         "Calculation status contradicts the number of candidates.")
    if status == COMPUTED:
        need(len(evidence.values) == len(cells)
             and all(type(value) is CandidateValue for value in evidence.values)
             and tuple(value.cell for value in evidence.values) == cells,
             "Missing, duplicate or partial candidate values.")
        for value in evidence.values:
            _check_value(value, counts, total)
        planned = sum(value.calls for value in evidence.values)
        need(evidence.planned_calls == planned == evidence.actual_calls and planned <= CALL_LIMIT,
             "Planned and actual hypothetical calls disagree with the values.")
    else:
        need(evidence.values == () and evidence.planned_calls == 0 == evidence.actual_calls,
             "Nothing may be recorded as computed when nothing was computed.")
    by_cell = {value.cell: value for value in evidence.values}
    for name, got, cell, field in (("target S_c", evidence.target_s_c, evidence.target, "s_c"),
                                   ("original S_v", evidence.original_s_v, g0, "s_v")):
        want = getattr(by_cell[cell], field) if cell in by_cell else None
        need((got is None and want is None) or (type(got) is Fraction and got == want),
             f"The recorded {name} is not the value of that cell (a missing value is never zero).")
    # Pair judgements (structure and counts; the geometry is trusted as recorded).
    need(type(evidence.pair_proofs) is tuple, "Malformed pair judgements.")
    forced_pairs = []
    for proof in evidence.pair_proofs:
        need(type(proof) is PairBasis and _is_cell(proof.a) and _is_cell(proof.b)
             and proof.a in unresolved and proof.b in unresolved
             and _reading(proof.a) < _reading(proof.b) and proof.verdict in (VERDICT_FORCED, VERDICT_APPARENT)
             and type(proof.failed) is tuple and type(proof.bases) is tuple and bool(proof.bases)
             and type(proof.distinguishing) is tuple, "Malformed pair judgement.")
        need(all(type(basis) is tuple and len(basis) == 2 and (
            (basis[0] == "CLUE" and inside(basis[1]) and 0 <= grid[basis[1][1]][basis[1][0]] <= 8)
            or (basis[0] == "LAST_MINE" and basis[1] is None)) for basis in proof.bases)
             and all(type(item) is tuple and len(item) == 2 and inside(item[0]) and item[1] in CELL_STATES
                     for item in proof.distinguishing),
             "Malformed ground or distinguishing cell of a pair.")
        need(type(proof.mine_worlds) is tuple and len(proof.mine_worlds) == 2
             and all(_is_int(count) for count in proof.mine_worlds) and _is_int(proof.total_worlds)
             and proof.mine_worlds == (counts[proof.a], counts[proof.b]) and proof.total_worlds == total,
             "World counts of a pair disagree with the public state.")
        isolated = all(state_name == "PROVEN_MINE" for _, state_name in proof.distinguishing)
        if proof.verdict == VERDICT_FORCED:
            need(isolated and proof.failed == () and 2 * counts[proof.a] == total == 2 * counts[proof.b],
                 "A forced pair needs proven-mine distinguishing cells and exact halves.")
            forced_pairs.append((proof.a, proof.b))
        else:
            need(not isolated and proof.failed == ("F3",), "An apparent pair must fail F3.")
    need(len(set((p.a, p.b) for p in evidence.pair_proofs)) == len(evidence.pair_proofs),
         "Duplicate pair judgement.")
    forced_cells = [cell for pair in forced_pairs for cell in pair]
    independence = ("NOT_APPLICABLE" if len(forced_pairs) < 2 else
                    "INDEPENDENT_PROVEN" if len(set(forced_cells)) == len(forced_cells)
                    else "OVERLAPPING_NOT_CLAIMED")
    need(evidence.independence == independence, "Recorded independence contradicts the forced pairs.")
    # Type-specific contract.
    if kind == FORCED_5050:
        need(bool(forced_pairs) and evidence.lookahead_set == PAIR_CELLS
             and cells == tuple(sorted(set(forced_cells), key=_reading))
             and type(evidence.pair) is tuple and len(evidence.pair) == 2
             and all(_is_cell(cell) for cell in evidence.pair)
             and evidence.pair in forced_pairs and evidence.target in evidence.pair
             and evidence.risk == Fraction(1, 2)
             and evidence.rank_basis == (RANK_S if by_cell else RANK_COST),
             "A FORCED_5050 guess needs its proven pair, the pair cells as candidates and risk 1/2.")
        rows = evidence.ranking
        need(type(rows) is tuple and len(rows) == len(cells) and all(
            type(row) is tuple and len(row) == 3 and inside(row[0])
            and (row[1] is None or type(row[1]) is Fraction) and _is_int(row[2]) and row[2] > 0
            for row in rows) and sorted((row[0] for row in rows), key=_reading) == list(cells),
             "Malformed rank of the pair cells.")
        need(all((row[1] is None and not by_cell) or (bool(by_cell) and row[1] == by_cell[row[0]].s_c)
                 for row in rows), "A rank row does not carry the S_c of its cell.")
        key = ((lambda row: (-row[1], row[2], row[0][1], row[0][0])) if by_cell
               else (lambda row: (row[2], row[0][1], row[0][0])))
        need(list(rows) == sorted(rows, key=key) and rows[0][0] == evidence.target,
             "The rank order or its first cell contradicts the target.")
        return
    need(not forced_pairs and evidence.lookahead_set == TIES and cells == ties and evidence.pair is None
         and evidence.ranking == () and evidence.rank_basis == RANK_NONE,
         "A tie guess has the minimum-risk ties as candidates, and no pair and no rank.")
    if kind == TIE_LOOKAHEAD:
        need(status == COMPUTED and evidence.target != g0, "A TIE_LOOKAHEAD guess needs computed values.")
        better = [value for value in evidence.values if value.s_c > by_cell[g0].s_v]
        need(bool(better), "No candidate has S_c above S_v of the original target.")
        best = max(value.s_c for value in better)
        need(evidence.target == min((value.cell for value in better if value.s_c == best), key=_reading),
             "The target is not the cell the tie rule selects from the recorded values.")
        return
    need(evidence.target == g0 and not (by_cell and any(
        value.s_c > by_cell[g0].s_v for value in evidence.values)),
         "A MIN_RISK guess keeps the original target and has no strictly better candidate.")


def _check_link(evidence, previous, opened, flagged):
    """The evidence must be of the state right before ITS input, not of an earlier decision."""
    grid = evidence.public_state.observation
    _need(all(0 <= grid[y][x] <= 8 for x, y in opened) and all(grid[y][x] == FLAGGED for x, y in flagged)
          and (previous is None or evidence.public_state.cursor == previous),
          "RECORD_LINK", "The evidence was made from another state than the one right before this input.")


def validate_record(record) -> None:
    """Internal consistency of a whole record. No probability call, no Engine, no recomputation
    of world counts or pair geometry."""
    _need(type(record) is GuessOutcomeRecord, "RECORD_FIELD", "Expected a guess outcome record.")
    width, height, num_mines = record.width, record.height, record.num_mines
    _need(all(_is_int(v) for v in (width, height, num_mines)) and 1 <= width <= 30 and 1 <= height <= 16
          and 0 <= num_mines < width * height and record.record_scope in SCOPES
          and type(record.allow_guess) is bool, "RECORD_FIELD", "Invalid public board conditions or scope.")

    def inside(x, y):
        return _is_int(x) and _is_int(y) and 0 <= x < width and 0 <= y < height

    prefix, inputs, scope = record.prefix_inputs, record.inputs, record.record_scope
    _need(type(prefix) is tuple and all(type(item) is tuple and len(item) == 3 and item[0] in ACTIONS
                                        and inside(item[1], item[2]) for item in prefix)
          and (scope != FULL_RUN or not prefix) and (scope != SEGMENT or bool(prefix)),
          "RECORD_INPUTS", "Prefix inputs contradict the record scope.")
    _need(type(inputs) is tuple and bool(inputs), "RECORD_INPUTS", "A record needs at least one actual input.")
    opened = {(x, y) for action, x, y in prefix if action == "OPEN"}
    flagged = {(x, y) for action, x, y in prefix if action == "FLAG"}
    previous = (prefix[-1][1], prefix[-1][2]) if prefix else None
    for position, item in enumerate(inputs):
        _need(type(item) is RecordedInput and _is_int(item.index) and item.index == len(prefix) + position
              and item.action in ACTIONS and inside(item.x, item.y) and item.status_after in STATUSES
              and item.decision in DECISIONS
              and (position == len(inputs) - 1 or item.status_after == PLAYING),
              "RECORD_INPUTS", "Input indices, actions or statuses are duplicated or inconsistent.")
        if item.decision == GUESS:
            _need(item.evidence is not None, "RECORD_EVIDENCE",
                  "A guess input without its pre-input evidence is a damaged record.")
            _check_evidence(item.evidence, width, height, num_mines)
            _need(item.action == "OPEN" and (item.x, item.y) == item.evidence.target, "RECORD_LINK",
                  "The evidence of a guess input must describe that very input.")
            _check_link(item.evidence, previous, opened, flagged)
            _need(record.allow_guess, "RECORD_INPUTS", "A guess cannot have been sent with guess OFF.")
        else:
            _need(item.evidence is None, "RECORD_LINK", "Evidence is attached to an input that is no guess.")
            _need(item.decision != INITIAL_OPEN
                  or (item.index == 0 and item.action == "OPEN" and (item.x, item.y) == (0, 0)),
                  "RECORD_INPUTS", "Only the canonical first OPEN (0,0) is an initial input.")
            _need(item.decision != EVIDENCE_NOT_RECORDED or scope == DECLARED, "RECORD_INPUTS",
                  "Evidence may be declared as not recorded only in declared test material.")
        _need(scope != FULL_RUN or (item.decision == INITIAL_OPEN) == (item.index == 0), "RECORD_INPUTS",
              "A full run starts with the initial input and has no other one.")
        _need(scope != SEGMENT or item.decision in (CERTAIN, GUESS), "RECORD_INPUTS",
              "A segment holds decided inputs only.")
        if item.action == "OPEN":
            opened.add((item.x, item.y))
        elif item.action == "FLAG":
            flagged.add((item.x, item.y))
        previous = (item.x, item.y)
    final, stop, blocked = record.final_status, record.stop_reason, record.blocked
    _need(final in STATUSES and final == inputs[-1].status_after and stop in STOP_REASONS, "RECORD_INPUTS",
          "The base result must be the status after the last actual input.")
    if final in (WON, LOST):
        _need(stop == TERMINAL and blocked is None, "RECORD_INPUTS", "A finished game stops as TERMINAL.")
    elif stop == GUESS_BLOCKED:
        _need(blocked is not None and not record.allow_guess, "RECORD_INPUTS",
              "GUESS_BLOCKED needs guess OFF and the blocked proposal.")
    else:
        _need(stop == SEGMENT_END and blocked is None and scope != FULL_RUN, "RECORD_INPUTS",
              "Only a segment may end while the game is still PLAYING.")
    if blocked is not None:
        _need(type(blocked) is BlockedProposal and _is_int(blocked.input_index)
              and blocked.input_index == inputs[-1].index + 1 and blocked.action == "OPEN"
              and _is_int(blocked.x) and _is_int(blocked.y) and _is_cell(blocked.cursor),
              "RECORD_INPUTS", "Malformed blocked proposal.")
        _check_evidence(blocked.evidence, width, height, num_mines)
        _need((blocked.x, blocked.y) == blocked.evidence.target
              and blocked.cursor == blocked.evidence.public_state.cursor, "RECORD_LINK",
              "The blocked proposal must be described by its own evidence.")
        _check_link(blocked.evidence, previous, opened, flagged)
    _need(type(record.loss) is LossClassification
          and (record.loss.input_index is None or _is_int(record.loss.input_index))
          and record.loss == classify(inputs, final),
          "RECORD_CLASSIFICATION", "The stored classification differs from the one its inputs give.")


def make_record(*, record_scope, width, height, num_mines, allow_guess, prefix_inputs, inputs, blocked,
                final_status, stop_reason) -> GuessOutcomeRecord:
    """Build, classify and validate one record."""
    _need(type(inputs) is tuple and all(type(item) is RecordedInput for item in inputs), "RECORD_INPUTS",
          "Inputs must be a tuple of recorded inputs.")
    record = GuessOutcomeRecord(record_scope, width, height, num_mines, allow_guess, prefix_inputs, inputs,
                                blocked, final_status, stop_reason, classify(inputs, final_status))
    validate_record(record)
    return record


# ---- exact numbers and the fixed byte form -------------------------------------------------

def _fraction_doc(value):
    return None if value is None else {"n": str(value.numerator), "d": str(value.denominator)}


def _cell_doc(cell):
    return None if cell is None else [cell[0], cell[1]]


def _evidence_doc(e):
    return {
        "kind": e.kind, "selection_reason": e.selection_reason, "target": _cell_doc(e.target),
        "risk": _fraction_doc(e.risk), "risk_kind": e.risk_kind,
        "original_target": _cell_doc(e.original_target), "original_risk": _fraction_doc(e.original_risk),
        "is_minimum_risk": e.is_minimum_risk, "target_changed": e.target_changed,
        "pair": None if e.pair is None else [_cell_doc(cell) for cell in e.pair],
        "category": e.category, "k_lc1_move": list(e.k_lc1_move),
        "lookahead": {
            "status": e.lookahead_status, "set": e.lookahead_set, "rank_basis": e.rank_basis,
            "cells": [_cell_doc(cell) for cell in e.lookahead_cells], "outside_set": e.outside_set_lookahead,
            "planned_calls": e.planned_calls, "actual_calls": e.actual_calls,
            "target_s_c": _fraction_doc(e.target_s_c), "original_s_v": _fraction_doc(e.original_s_v),
            "values": [{
                "cell": _cell_doc(v.cell), "mine_worlds": str(v.mine_worlds),
                "total_worlds": str(v.total_worlds), "mine_neighbors": v.mine_neighbors,
                "unresolved_neighbors": v.unresolved_neighbors, "calls": v.calls,
                "outcomes": [{
                    "number": o.number, "worlds": str(o.worlds), "q_kind": o.q_kind,
                    "q": _fraction_doc(o.q),
                    "minimum_mine_worlds": None if o.minimum_mine_worlds is None else str(o.minimum_mine_worlds),
                    "safe_cells": o.safe_cells, "flood": o.flood} for o in v.outcomes],
                "flood_worlds": str(v.flood_worlds), "s_v": _fraction_doc(v.s_v),
                "s_c": _fraction_doc(v.s_c)} for v in e.values]},
        "ranking": [{"cell": _cell_doc(cell), "s_c": _fraction_doc(s_c), "cost_us": cost}
                    for cell, s_c, cost in e.ranking],
        "pair_proofs": [{
            "a": _cell_doc(p.a), "b": _cell_doc(p.b), "verdict": p.verdict, "failed": list(p.failed),
            "bases": [[kind, _cell_doc(cell)] for kind, cell in p.bases],
            "distinguishing": [[_cell_doc(cell), state] for cell, state in p.distinguishing],
            "mine_worlds": [str(count) for count in p.mine_worlds], "total_worlds": str(p.total_worlds)}
            for p in e.pair_proofs],
        "independence": e.independence,
        "public_state": {
            "observation": [list(row) for row in e.public_state.observation],
            "num_mines": e.public_state.num_mines,
            "mines": [_cell_doc(cell) for cell in e.public_state.mines],
            "cursor": _cell_doc(e.public_state.cursor), "total_worlds": str(e.public_state.total_worlds),
            "mine_worlds": [[_cell_doc(cell), str(count)] for cell, count in e.public_state.mine_worlds]}}


def _document(record):
    blocked = record.blocked
    return {
        "format": FORMAT, "version": VERSION, "policy": dict(POLICY), "record_scope": record.record_scope,
        "evidence_timing": dict(EVIDENCE_TIMING),
        "board": {"width": record.width, "height": record.height, "num_mines": record.num_mines},
        "allow_guess": record.allow_guess,
        "prefix_inputs": [list(item) for item in record.prefix_inputs],
        "inputs": [{"index": item.index, "action": item.action, "x": item.x, "y": item.y,
                    "status_after": item.status_after, "decision": item.decision,
                    "evidence": None if item.evidence is None else _evidence_doc(item.evidence)}
                   for item in record.inputs],
        "blocked_proposal": None if blocked is None else {
            "input_index": blocked.input_index, "cursor": _cell_doc(blocked.cursor),
            "action": blocked.action, "x": blocked.x, "y": blocked.y,
            "evidence": _evidence_doc(blocked.evidence)},
        "final_status": record.final_status, "stop_reason": record.stop_reason,
        "loss_classification": {"applicability": record.loss.applicability, "kind": record.loss.kind,
                                "basis": record.loss.basis, "input_index": record.loss.input_index}}


def encode_record(record) -> bytes:
    """The one byte form of a valid record (UTF-8, LF, fixed key order)."""
    validate_record(record)
    return (json.dumps(_document(record), ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def _obj(value, keys, where):
    _need(type(value) is dict, "RECORD_FIELD", f"{where} must be an object.")
    _need(list(value) == list(keys), "RECORD_FIELD",
          f"{where} must have exactly the fields {list(keys)} in this order, got {list(value)}.")
    return value


def _list(value, where):
    _need(type(value) is list, "RECORD_FIELD", f"{where} must be a list.")
    return value


def _text(value, where, allowed=None):
    _need(type(value) is str and (allowed is None or value in allowed), "RECORD_FIELD",
          f"{where} has an unknown or malformed value.")
    return value


def _small(value, where):
    _need(type(value) is int, "RECORD_NUMBER", f"{where} must be a JSON integer.")
    return value


def _flag(value, where):
    _need(type(value) is bool, "RECORD_FIELD", f"{where} must be a boolean.")
    return value


def _big(value, where):
    _need(type(value) is str and value.isascii() and value.isdigit() and (value == "0" or value[0] != "0"),
          "RECORD_NUMBER", f"{where} must be a canonical decimal integer string.")
    return int(value)


def _fraction(value, where, nullable=False):
    if value is None and nullable:
        return None
    _need(type(value) is dict and list(value) == ["n", "d"], "RECORD_NUMBER",
          f"{where} must be a fraction object with n and d.")
    numerator, denominator = _big(value["n"], where), _big(value["d"], where)
    _need(denominator >= 1, "RECORD_NUMBER", f"{where} has denominator 0.")
    result = Fraction(numerator, denominator)
    _need(result.numerator == numerator and result.denominator == denominator, "RECORD_NUMBER",
          f"{where} is not in lowest terms.")
    _need(0 <= result <= 1, "RECORD_NUMBER", f"{where} is outside 0..1.")
    return result


def _cell(value, where, nullable=False):
    if value is None and nullable:
        return None
    _need(type(value) is list and len(value) == 2 and all(type(v) is int for v in value), "RECORD_FIELD",
          f"{where} must be a cell [x, y].")
    return value[0], value[1]


EVIDENCE_KEYS = ("kind", "selection_reason", "target", "risk", "risk_kind", "original_target",
                 "original_risk", "is_minimum_risk", "target_changed", "pair", "category", "k_lc1_move",
                 "lookahead", "ranking", "pair_proofs", "independence", "public_state")
LOOKAHEAD_KEYS = ("status", "set", "rank_basis", "cells", "outside_set", "planned_calls", "actual_calls",
                  "target_s_c", "original_s_v", "values")
VALUE_KEYS = ("cell", "mine_worlds", "total_worlds", "mine_neighbors", "unresolved_neighbors", "calls",
              "outcomes", "flood_worlds", "s_v", "s_c")
OUTCOME_KEYS = ("number", "worlds", "q_kind", "q", "minimum_mine_worlds", "safe_cells", "flood")
PROOF_KEYS = ("a", "b", "verdict", "failed", "bases", "distinguishing", "mine_worlds", "total_worlds")
STATE_KEYS = ("observation", "num_mines", "mines", "cursor", "total_worlds", "mine_worlds")
TOP_KEYS = ("format", "version", "policy", "record_scope", "evidence_timing", "board", "allow_guess",
            "prefix_inputs", "inputs", "blocked_proposal", "final_status", "stop_reason",
            "loss_classification")
INPUT_KEYS = ("index", "action", "x", "y", "status_after", "decision", "evidence")
BLOCKED_KEYS = ("input_index", "cursor", "action", "x", "y", "evidence")
LOSS_KEYS = ("applicability", "kind", "basis", "input_index")


def _move(value, where):
    _need(type(value) is list and len(value) == 3 and type(value[0]) is str
          and type(value[1]) is int and type(value[2]) is int, "RECORD_FIELD",
          f"{where} must be [action, x, y].")
    return value[0], value[1], value[2]


def _evidence(doc, where):
    doc = _obj(doc, EVIDENCE_KEYS, where)
    look = _obj(doc["lookahead"], LOOKAHEAD_KEYS, where + ".lookahead")
    values = []
    for position, row in enumerate(_list(look["values"], where + ".values")):
        at = f"{where}.values[{position}]"
        row = _obj(row, VALUE_KEYS, at)
        outcomes = []
        for index, item in enumerate(_list(row["outcomes"], at + ".outcomes")):
            item = _obj(item, OUTCOME_KEYS, f"{at}.outcomes[{index}]")
            minimum = item["minimum_mine_worlds"]
            outcomes.append(NumberOutcome(
                _small(item["number"], at), _big(item["worlds"], at), _text(item["q_kind"], at, Q_KINDS),
                _fraction(item["q"], at, nullable=True), None if minimum is None else _big(minimum, at),
                _small(item["safe_cells"], at), _flag(item["flood"], at)))
        values.append(CandidateValue(
            _cell(row["cell"], at), _big(row["mine_worlds"], at), _big(row["total_worlds"], at),
            _small(row["mine_neighbors"], at), _small(row["unresolved_neighbors"], at),
            _small(row["calls"], at), tuple(outcomes), _big(row["flood_worlds"], at),
            _fraction(row["s_v"], at), _fraction(row["s_c"], at)))
    ranking = []
    for position, row in enumerate(_list(doc["ranking"], where + ".ranking")):
        at = f"{where}.ranking[{position}]"
        row = _obj(row, ("cell", "s_c", "cost_us"), at)
        ranking.append((_cell(row["cell"], at), _fraction(row["s_c"], at, nullable=True),
                        _small(row["cost_us"], at)))
    proofs = []
    for position, row in enumerate(_list(doc["pair_proofs"], where + ".pair_proofs")):
        at = f"{where}.pair_proofs[{position}]"
        row = _obj(row, PROOF_KEYS, at)
        bases = []
        for basis in _list(row["bases"], at + ".bases"):
            _need(type(basis) is list and len(basis) == 2, "RECORD_FIELD", f"{at}.bases is malformed.")
            bases.append((_text(basis[0], at), _cell(basis[1], at, nullable=True)))
        distinguishing = []
        for item in _list(row["distinguishing"], at + ".distinguishing"):
            _need(type(item) is list and len(item) == 2, "RECORD_FIELD", f"{at}.distinguishing is malformed.")
            distinguishing.append((_cell(item[0], at), _text(item[1], at, CELL_STATES)))
        worlds = _list(row["mine_worlds"], at + ".mine_worlds")
        _need(len(worlds) == 2, "RECORD_FIELD", f"{at}.mine_worlds needs two counts.")
        proofs.append(PairBasis(
            _cell(row["a"], at), _cell(row["b"], at), _text(row["verdict"], at),
            tuple(_text(name, at) for name in _list(row["failed"], at + ".failed")), tuple(bases),
            tuple(distinguishing), (_big(worlds[0], at), _big(worlds[1], at)), _big(row["total_worlds"], at)))
    state = _obj(doc["public_state"], STATE_KEYS, where + ".public_state")
    grid = []
    for row in _list(state["observation"], where + ".observation"):
        grid.append(tuple(_small(v, where + ".observation") for v in _list(row, where + ".observation")))
    counts = []
    for item in _list(state["mine_worlds"], where + ".mine_worlds"):
        _need(type(item) is list and len(item) == 2, "RECORD_FIELD", f"{where}.mine_worlds is malformed.")
        counts.append((_cell(item[0], where), _big(item[1], where + ".mine_worlds")))
    pair = doc["pair"]
    if pair is not None:
        _need(type(pair) is list and len(pair) == 2, "RECORD_FIELD", f"{where}.pair needs two cells.")
        pair = (_cell(pair[0], where), _cell(pair[1], where))
    return GuessEvidence(
        kind=_text(doc["kind"], where), selection_reason=_text(doc["selection_reason"], where),
        target=_cell(doc["target"], where), risk=_fraction(doc["risk"], where + ".risk"),
        risk_kind=_text(doc["risk_kind"], where), original_target=_cell(doc["original_target"], where),
        original_risk=_fraction(doc["original_risk"], where + ".original_risk"),
        is_minimum_risk=_flag(doc["is_minimum_risk"], where), target_changed=_flag(doc["target_changed"], where),
        pair=pair, category=_text(doc["category"], where), k_lc1_move=_move(doc["k_lc1_move"], where),
        lookahead_status=_text(look["status"], where), lookahead_set=_text(look["set"], where),
        rank_basis=_text(look["rank_basis"], where),
        lookahead_cells=tuple(_cell(cell, where) for cell in _list(look["cells"], where + ".cells")),
        outside_set_lookahead=_text(look["outside_set"], where),
        planned_calls=_small(look["planned_calls"], where), actual_calls=_small(look["actual_calls"], where),
        target_s_c=_fraction(look["target_s_c"], where + ".target_s_c", nullable=True),
        original_s_v=_fraction(look["original_s_v"], where + ".original_s_v", nullable=True),
        values=tuple(values), ranking=tuple(ranking), pair_proofs=tuple(proofs),
        independence=_text(doc["independence"], where),
        public_state=PublicState(
            tuple(grid), _small(state["num_mines"], where),
            tuple(_cell(cell, where) for cell in _list(state["mines"], where + ".mines")),
            _cell(state["cursor"], where), _big(state["total_worlds"], where + ".total_worlds"),
            tuple(counts)))


def _unique_pairs(pairs):
    keys = [key for key, _ in pairs]
    _need(len(set(keys)) == len(keys), "RECORD_JSON", "An object repeats a key.")
    return dict(pairs)


def _reject_float(text):
    raise GuessRecordError("RECORD_NUMBER", f"A real number ({text}) is not allowed in a record.")


def decode_record(data) -> GuessOutcomeRecord:
    """Read a record from its bytes and validate it. Only what the bytes say is used:
    nothing is recomputed to fill a gap, and no Engine or probability code is involved."""
    _need(type(data) is bytes, "RECORD_JSON", "A record is read from bytes.")
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs,
                              parse_float=_reject_float, parse_constant=_reject_float)
    except GuessRecordError:
        raise
    except (ValueError, RecursionError) as error:  # not UTF-8, truncated or otherwise not JSON
        raise GuessRecordError("RECORD_JSON", f"Not a complete JSON document: {error}") from error
    _need(type(document) is dict, "RECORD_FIELD", "A record is one JSON object.")
    _need(document.get("format") == FORMAT and type(document.get("version")) is int
          and document.get("version") == VERSION, "RECORD_VERSION",
          f"Unknown record format or version: {document.get('format')!r} {document.get('version')!r}.")
    document = _obj(document, TOP_KEYS, "record")
    _need(document["policy"] == POLICY and type(document["policy"]) is dict
          and list(document["policy"]) == list(POLICY), "RECORD_FIELD", "Unknown policy identification.")
    _need(document["evidence_timing"] == EVIDENCE_TIMING and type(document["evidence_timing"]) is dict
          and list(document["evidence_timing"]) == list(EVIDENCE_TIMING), "RECORD_FIELD",
          "Unknown evidence timing.")
    board = _obj(document["board"], ("width", "height", "num_mines"), "board")
    inputs = []
    for position, item in enumerate(_list(document["inputs"], "inputs")):
        at = f"inputs[{position}]"
        item = _obj(item, INPUT_KEYS, at)
        inputs.append(RecordedInput(
            _small(item["index"], at), _text(item["action"], at), _small(item["x"], at),
            _small(item["y"], at), _text(item["status_after"], at), _text(item["decision"], at),
            None if item["evidence"] is None else _evidence(item["evidence"], at + ".evidence")))
    blocked = document["blocked_proposal"]
    if blocked is not None:
        blocked = _obj(blocked, BLOCKED_KEYS, "blocked_proposal")
        blocked = BlockedProposal(
            _small(blocked["input_index"], "blocked_proposal"), _cell(blocked["cursor"], "blocked_proposal"),
            _text(blocked["action"], "blocked_proposal"), _small(blocked["x"], "blocked_proposal"),
            _small(blocked["y"], "blocked_proposal"),
            _evidence(blocked["evidence"], "blocked_proposal.evidence"))
    loss = _obj(document["loss_classification"], LOSS_KEYS, "loss_classification")
    _need(all(loss[key] is None or type(loss[key]) is str for key in ("kind", "basis"))
          and (loss["input_index"] is None or type(loss["input_index"]) is int), "RECORD_FIELD",
          "Malformed loss classification.")
    record = GuessOutcomeRecord(
        _text(document["record_scope"], "record_scope"), _small(board["width"], "board"),
        _small(board["height"], "board"), _small(board["num_mines"], "board"),
        _flag(document["allow_guess"], "allow_guess"),
        tuple(_move(item, "prefix_inputs") for item in _list(document["prefix_inputs"], "prefix_inputs")),
        tuple(inputs), blocked, _text(document["final_status"], "final_status"),
        _text(document["stop_reason"], "stop_reason"),
        LossClassification(_text(loss["applicability"], "loss_classification"), loss["kind"], loss["basis"],
                           loss["input_index"]))
    validate_record(record)
    _need(encode_record(record) == data, "RECORD_JSON", "The file is not in the fixed byte form of version 1.")
    return record


def save_record(record, path) -> SaveOutcome:
    """Write one record to a NEW file. Never overwrites, never deletes, never raises for an I/O failure.

    The final name appears only with complete content: the bytes go to ``<path>.partial``
    first and that file is then renamed. After a failure the partial file is left where it is.
    An invalid record raises GuessRecordError before anything is written.
    """
    data = encode_record(record)
    path = os.fspath(path)
    partial = path + ".partial"
    if os.path.lexists(path):
        return SaveOutcome(SAVE_FAILED, path, None, None, "PATH_EXISTS",
                           "The path already exists; nothing was written.", None)
    if os.path.lexists(partial):
        return SaveOutcome(SAVE_FAILED, path, None, None, "PARTIAL_PATH_EXISTS",
                           "An earlier partial file exists; nothing was written.", partial)
    try:
        with open(partial, "xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        return SaveOutcome(SAVE_FAILED, path, None, None, "WRITE_FAILED", repr(error),
                           partial if os.path.lexists(partial) else None)
    try:
        if os.path.lexists(path):
            raise FileExistsError(path)
        os.rename(partial, path)
    except OSError as error:
        return SaveOutcome(SAVE_FAILED, path, None, None, "RENAME_FAILED", repr(error), partial)
    try:
        with open(path, "rb") as stream:
            written = stream.read()
    except OSError as error:
        return SaveOutcome(SAVE_FAILED, path, None, None, "VERIFY_FAILED", repr(error), None)
    if written != data:
        return SaveOutcome(SAVE_FAILED, path, None, None, "VERIFY_FAILED",
                           "The file content differs from the bytes written.", None)
    return SaveOutcome(SAVED, path, len(data), hashlib.sha256(data).hexdigest(), None, None, None)


def load_record(path) -> GuessOutcomeRecord:
    """Read a record file. The result is data only; it authorises no input."""
    with open(os.fspath(path), "rb") as stream:
        return decode_record(stream.read())


# ---- description and tally -------------------------------------------------------------

def _lookahead_line(evidence) -> str:
    if evidence.lookahead_status == COMPUTED:
        return f"전방 계산: 계산함 (가정 계산 {evidence.actual_calls}회)."
    if evidence.lookahead_status == SINGLE:
        return "전방 계산: 후보가 한 칸이라 계산하지 않음."
    return "전방 계산: 후보 수 한도로 계산하지 않음."


def _storage_line(storage) -> str:
    if storage is None or storage == NOT_SAVED or (type(storage) is SaveOutcome and storage.state == NOT_SAVED):
        return "저장 상태: 저장되지 않음 (메모리 기록)."
    if storage == LOADED_FROM_FILE:
        return "저장 상태: 실험 기록 파일에서 읽음."
    _need(type(storage) is SaveOutcome and storage.state in (SAVED, SAVE_FAILED), "RECORD_FIELD",
          "Unknown storage state.")
    if storage.state == SAVED:
        return "저장 상태: 실험 기록 파일로 저장됨."
    return f"저장 상태: 저장 실패 ({storage.code}). 게임 결과와 무관하다."


def describe(record, storage=None) -> tuple:
    """Short Korean description: base result, auxiliary classification, storage state.

    Display strings such as "1/2" are made here only. S_c and S_v are named as values of the
    K-LC1 line's next input, never as this policy's survival probability or a win rate.
    """
    validate_record(record)
    final, loss = record.final_status, record.loss
    lines = ["기본 결과: PLAYING (판이 끝나지 않았다)" if final == PLAYING else f"기본 결과: {final}"]
    if loss.applicability == NOT_APPLICABLE_WON:
        lines.append("패배 보조 분류: 해당 없음 (WON).")
    elif loss.applicability == NOT_APPLICABLE_NOT_FINISHED:
        lines.append("패배 보조 분류: 해당 없음 (판이 끝나지 않았다).")
        if record.blocked is not None:
            lines.append(f"차단된 제안 1건: OPEN ({record.blocked.x},{record.blocked.y}), "
                         f"{record.blocked.evidence.kind}. 실제 입력이 아니며 입력 수와 패배 수에 세지 않는다.")
    elif loss.applicability == INTEGRITY_PROBLEM:
        last = record.inputs[-1]
        lines.append(f"무결성 문제: 추측이 아닌 입력 {last.action} ({last.x},{last.y})에서 LOST가 기록됐다. "
                     "추측 패배로 분류하지 않는다. 기본 결과 LOST는 그대로다.")
    elif loss.kind == UNCLASSIFIED:
        reason = ("첫 입력에는 입력 전 근거가 없다." if loss.basis == BASIS_INITIAL
                  else "입력 전 근거가 기록되지 않았다.")
        lines.append(f"패배 보조 분류: 유형 미확인 (UNCLASSIFIED). {reason}")
    else:
        last = record.inputs[-1]
        evidence = last.evidence
        head = {FORCED_5050: "불가피한 50/50 쌍의 추측",
                TIE_LOOKAHEAD: "최소 위험 동률 집합에서 전방 비교로 고른 추측",
                MIN_RISK: "기존 최소 위험 선택을 유지한 추측"}[loss.kind]
        lines.append(f"패배 보조 분류: {head} ({loss.kind}). 입력 OPEN ({last.x},{last.y}), "
                     f"입력 전 위험 {evidence.risk}.")
        original = f"원 대상 ({evidence.original_target[0]},{evidence.original_target[1]})의 위험 {evidence.original_risk}."
        if loss.kind == FORCED_5050:
            lines.append(original + " 쌍의 어느 칸을 열어도 위험이 1/2이라는 뜻이며, "
                                    "판 전체의 패배가 정해져 있었다는 뜻이 아니다.")
        elif loss.kind == TIE_LOOKAHEAD:
            lines.append(original + f" 대상의 S_c {evidence.target_s_c}, 원 대상의 S_v {evidence.original_s_v}.")
            lines.append("S_c와 S_v는 K-LC1 기준 수순의 다음 입력에 관한 값이다. "
                         "이 정책의 실제 생존확률이나 판 전체 승률이 아니다.")
        lines.append(_lookahead_line(evidence))
    lines.append(_storage_line(storage))
    return tuple(lines)


def tally(records) -> dict:
    """Base results counted from ``final_status`` alone; classifications counted apart.

    A blocked proposal is neither an input nor a loss.
    """
    out = {WON: 0, LOST: 0, PLAYING: 0, "executed_inputs": 0, "blocked_proposals": 0,
           "loss_kinds": {FORCED_5050: 0, TIE_LOOKAHEAD: 0, MIN_RISK: 0, UNCLASSIFIED: 0},
           "integrity_problems": 0}
    for record in records:
        validate_record(record)
        out[record.final_status] += 1
        out["executed_inputs"] += len(record.inputs)
        out["blocked_proposals"] += record.blocked is not None
        if record.loss.applicability == APPLIES:
            out["loss_kinds"][record.loss.kind] += 1
        elif record.loss.applicability == INTEGRITY_PROBLEM:
            out["integrity_problems"] += 1
    return out
