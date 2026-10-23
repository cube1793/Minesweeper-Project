"""E2 I1 immutable evidence vocabulary and closed, version-1 canonical JSON.

Only supplied values are represented: no capture, execution, storage or verdict
calculation. Coordinates are (x, y). Set-like cell tuples must already be unique
and in reading order (y, x); constructors never silently discard duplicates.
Ordinals are zero-based except the one-based uncertain-guess ordinal. Stream-wide
relationships remain the later validator's responsibility.
"""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from hashlib import sha256
import json


SCHEMA_VERSION = 1
UINT64_MAX = (1 << 64) - 1


class RecordError(ValueError):
    """Malformed, inexact, unsupported or noncanonical evidence."""


def _need(ok, message):
    if not ok:
        raise RecordError(message)


def _int(value, low=0, high=UINT64_MAX):
    _need(type(value) is int and low <= value and (high is None or value <= high),
          "Expected an exact integer in bounds.")


def _text(value, *, empty=False):
    _need(type(value) is str and (empty or bool(value)), "Expected exact text.")
    _need(all(ord(c) >= 32 and not 0xD800 <= ord(c) <= 0xDFFF for c in value),
          "Control characters/surrogates are not identity text.")


def _hex(value, size=64):
    _text(value)
    _need(len(value) == size and all(c in "0123456789abcdef" for c in value),
          "Expected lowercase hex identity.")


def _path(value):
    _text(value)
    _need("\\" not in value and ":" not in value
          and all(part not in ("", ".", "..") for part in value.split("/")),
          "Expected normalized repository-relative path.")


def _enum(value, cls):
    _need(type(value) is cls, "Expected exact schema enum.")


def _cell(value, board=None):
    _need(type(value) is tuple and len(value) == 2, "Expected (x, y) tuple.")
    for n in value:
        _int(n)
    if board is not None:
        _need(value[0] < board.width and value[1] < board.height, "Cell outside board.")


def _tuple(value):
    _need(type(value) is tuple, "Expected owned immutable tuple.")


def _cells(value, board=None):
    _tuple(value)
    for cell in value:
        _cell(cell, board)
    _need(len(set(value)) == len(value), "Duplicate cell.")
    _need(value == tuple(sorted(value, key=lambda c: (c[1], c[0]))), "Cells out of reading order.")


def _fraction(value, *, probability=False):
    _need(type(value) is Fraction, "Expected exact Fraction.")
    if probability:
        _need(0 <= value <= 1, "Probability outside [0, 1].")


def _record(value, cls):
    _need(type(value) is cls, "Unexpected record type/subclass.")
    cls.__post_init__(value)


class Arm(Enum):
    CONTROL = "CONTROL"
    K_P0 = "K_P0"
    K_CONTROL = "K_CONTROL"


class Action(Enum):
    OPEN = "OPEN"
    FLAG = "FLAG"  # physical toggle; UNFLAG is an explicit public-state change
    CHORD = "CHORD"


class Status(Enum):
    PLAYING = "PLAYING"
    WON = "WON"
    LOST = "LOST"


class Outcome(Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    ERROR = "ERROR"
    INCOMPLETE = "INCOMPLETE"


class DecisionScope(Enum):
    CONTROL_PLAN_POSITION = "CONTROL_PLAN_POSITION"
    K_ANALYZE_DECISION_THROUGH_SELECT_POLICY = "K_ANALYZE_DECISION_THROUGH_SELECT_POLICY"
    K_EXECUTION_VALIDATION = "K_EXECUTION_VALIDATION"
    EVALUATOR = "EVALUATOR"
    SERIALIZATION = "SERIALIZATION"
    PERSISTENCE = "PERSISTENCE"
    REPORT = "REPORT"


class FlagCategory(Enum):
    CONTROL_SETUP_CHORD_FLAG = "CONTROL_SETUP_CHORD_FLAG"
    CONTROL_FALLBACK_FLAG = "CONTROL_FALLBACK_FLAG"
    CONTROL_FLAG_TO_OPEN_SETUP = "CONTROL_FLAG_TO_OPEN_SETUP"


class AcquisitionSource(Enum):
    LOCAL = "LOCAL"
    EXACT_GLOBAL = "EXACT_GLOBAL"


class AssertionCategory(Enum):
    LOGICAL_M = "LOGICAL_M"
    CERTAINTY_OPEN = "CERTAINTY_OPEN"
    CERTAINTY_CHORD_OPENED = "CERTAINTY_CHORD_OPENED"


class EvaluationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"


class P3Status(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"


class AuditStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"


class Phase(Enum):
    PREFLIGHT = "PREFLIGHT"
    CORPUS_AUTHENTICATION = "CORPUS_AUTHENTICATION"
    EXECUTION = "EXECUTION"
    AGGREGATION = "AGGREGATION"
    VALIDATION = "VALIDATION"
    PUBLICATION = "PUBLICATION"
    READBACK = "READBACK"
    REPORT = "REPORT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"


class EventKind(Enum):
    START = "START"
    PROGRESS = "PROGRESS"
    END = "END"
    ERROR = "ERROR"


class OperationStatus(Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"


class ProcessRole(Enum):
    WORKER = "WORKER"
    COORDINATOR = "COORDINATOR"
    COMBINED = "COMBINED"


class MemoryMethod(Enum):
    RSS = "RSS"
    PRIVATE_BYTES = "PRIVATE_BYTES"
    WORKING_SET = "WORKING_SET"


class CompletionState(Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"


class TerminalPresentation(Enum):
    MINE = "MINE"
    EXPLODED_MINE = "EXPLODED_MINE"
    WRONG_FLAG = "WRONG_FLAG"
    CORRECT_FLAG = "CORRECT_FLAG"


@dataclass(frozen=True, slots=True)
class ProtocolIdentity:
    path: str
    sha256: str
    blob_id: str
    freeze_commit: str

    def __post_init__(self):
        _path(self.path)
        _hex(self.sha256)
        _hex(self.blob_id, 40)
        _hex(self.freeze_commit, 40)


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    python_implementation: str
    python_version: str
    os: str
    platform: str
    architecture: str
    host: str | None

    def __post_init__(self):
        for v in (self.python_implementation, self.python_version, self.os, self.platform, self.architecture):
            _text(v)
        if self.host is not None:
            _text(self.host)


@dataclass(frozen=True, slots=True)
class SourceBlobIdentity:
    path: str
    blob_id: str
    sha256: str
    byte_length: int

    def __post_init__(self):
        _path(self.path)
        _hex(self.blob_id, 40)
        _hex(self.sha256)
        _int(self.byte_length)


@dataclass(frozen=True, slots=True)
class CorpusIdentity:
    frame_label: str
    low: int
    high: int
    n: int
    ordered_indices: tuple
    corpus_sha256: str
    exclusions: tuple

    def __post_init__(self):
        _text(self.frame_label)
        _need(all(33 <= ord(c) <= 126 for c in self.frame_label), "Frame label must be ASCII.")
        _int(self.low)
        _int(self.high, 1, 1 << 64)
        _need(self.low < self.high, "Empty frame.")
        _int(self.n, 1)
        _tuple(self.ordered_indices)
        _tuple(self.exclusions)
        for v in self.ordered_indices + self.exclusions:
            _int(v, self.low, self.high - 1)
        _need(len(self.ordered_indices) == self.n and len(set(self.ordered_indices)) == self.n,
              "Invalid ordered N/duplicate index.")
        _need(self.exclusions == tuple(sorted(set(self.exclusions))), "Noncanonical exclusions.")
        _need(not set(self.ordered_indices).intersection(self.exclusions), "Excluded corpus member.")
        _hex(self.corpus_sha256)


@dataclass(frozen=True, slots=True)
class BoardIdentity:
    game_index: int
    fingerprint: str
    width: int
    height: int
    mines: int
    first_click: tuple
    generator_identity: str
    spec_identity: str

    def __post_init__(self):
        _int(self.game_index)
        _text(self.fingerprint)
        _int(self.width, 1)
        _int(self.height, 1)
        _int(self.mines, 0, min(UINT64_MAX, self.width * self.height - 1))
        _cell(self.first_click, self)
        _text(self.generator_identity)
        _text(self.spec_identity)


@dataclass(frozen=True, slots=True)
class ArmIdentity:
    arm: Arm
    board: BoardIdentity
    run_id: str
    unit_id: str

    def __post_init__(self):
        _enum(self.arm, Arm)
        _record(self.board, BoardIdentity)
        _text(self.run_id)
        _text(self.unit_id)


@dataclass(frozen=True, slots=True)
class PhysicalInputRecord:
    action_ordinal: int
    action: Action
    target: tuple
    cursor_before: tuple
    input_us: int
    cumulative_us: int
    after_status: Status

    def __post_init__(self):
        _int(self.action_ordinal)
        _enum(self.action, Action)
        _cell(self.target)
        _cell(self.cursor_before)
        _int(self.input_us)
        _int(self.cumulative_us, self.input_us)
        _enum(self.after_status, Status)
        if self.action_ordinal == 0:
            _need(self.cumulative_us == self.input_us, "Initial cumulative cost must equal input cost.")


_PUBLIC_STATES = ("HIDDEN", "FLAGGED", "CLUE_0", "CLUE_1", "CLUE_2", "CLUE_3",
                  "CLUE_4", "CLUE_5", "CLUE_6", "CLUE_7", "CLUE_8")


@dataclass(frozen=True, slots=True)
class PublicCellChange:
    cell: tuple
    before: str
    after: str

    def __post_init__(self):
        _cell(self.cell)
        _need(type(self.before) is str and type(self.after) is str
              and self.before in _PUBLIC_STATES and self.after in _PUBLIC_STATES,
              "Only public hidden/flag/clue states are allowed.")
        _need((self.before == "HIDDEN" and self.after != "HIDDEN")
              or (self.before == "FLAGGED" and self.after == "HIDDEN"),
              "Invalid public reveal/flag/unflag transition.")


@dataclass(frozen=True, slots=True)
class PublicEffectRecord:
    action_ordinal: int
    changes: tuple
    before_status: Status
    after_status: Status

    def __post_init__(self):
        _int(self.action_ordinal)
        _tuple(self.changes)
        for change in self.changes:
            _record(change, PublicCellChange)
        _cells(tuple(change.cell for change in self.changes))
        _enum(self.before_status, Status)
        _enum(self.after_status, Status)
        _need(self.before_status is Status.PLAYING, "Public input must begin while PLAYING.")


@dataclass(frozen=True, slots=True)
class TerminalCellChange:
    cell: tuple
    presentation: TerminalPresentation

    def __post_init__(self):
        _cell(self.cell)
        _enum(self.presentation, TerminalPresentation)


@dataclass(frozen=True, slots=True)
class TerminalEffectRecord:
    action_ordinal: int
    changes: tuple
    terminal_status: Status

    def __post_init__(self):
        _int(self.action_ordinal)
        _tuple(self.changes)
        for change in self.changes:
            _record(change, TerminalCellChange)
        _cells(tuple(change.cell for change in self.changes))
        _enum(self.terminal_status, Status)
        _need(self.terminal_status in (Status.WON, Status.LOST), "Expected terminal status.")


@dataclass(frozen=True, slots=True)
class DecisionSpanRecord:
    action_ordinal: int
    scope: DecisionScope
    duration_ns: int | None

    def __post_init__(self):
        _int(self.action_ordinal)
        _enum(self.scope, DecisionScope)
        if self.duration_ns is not None:
            _int(self.duration_ns)


@dataclass(frozen=True, slots=True)
class ActionDecisionRecord:
    """Durable selected decision only; no candidate graph or proof admission.

    Plan actions preserve execution order. Set-like cell tuples are already in
    reading order. Logical-M snapshots retain K-P0 mechanism facts separately
    from physical flags and do not assert certificate validity.
    """

    arm: ArmIdentity
    action_ordinal: int
    category: str
    semantic_kind: str
    action: Action
    target: tuple
    plan_actions: tuple
    plan_model_us: int | None
    plan_safe_reveals: int | None
    setup_cells: tuple
    reveal_cells: tuple
    logical_mines_before: tuple
    logical_mines_after: tuple

    def __post_init__(self):
        _record(self.arm, ArmIdentity)
        _need(self.arm.arm in (Arm.CONTROL, Arm.K_P0), "Action decisions currently cover CONTROL/K-P0 only.")
        _int(self.action_ordinal)
        _text(self.category)
        _text(self.semantic_kind)
        _enum(self.action, Action)
        board = self.arm.board
        _cell(self.target, board)
        _tuple(self.plan_actions)
        for entry in self.plan_actions:
            _need(type(entry) is tuple and len(entry) == 2, "Expected a closed (Action, cell) plan entry.")
            _enum(entry[0], Action)
            _cell(entry[1], board)
        for cells in (self.setup_cells, self.reveal_cells, self.logical_mines_before, self.logical_mines_after):
            _cells(cells, board)
        _need(set(self.logical_mines_before) <= set(self.logical_mines_after), "Logical M cannot regress.")
        if self.arm.arm is Arm.CONTROL:
            _need(not self.logical_mines_before and not self.logical_mines_after,
                  "CONTROL decisions cannot retain logical M.")
        if self.action_ordinal == 0:
            expected_category = "CONTROL_INITIAL_OPEN" if self.arm.arm is Arm.CONTROL else "POLICY_INITIAL_OPEN"
            _need(self.category == expected_category and self.semantic_kind == "INITIAL"
                  and self.action is Action.OPEN and self.target == board.first_click,
                  "Initial decision must retain its arm's initial OPEN identity.")
            _need(not self.plan_actions and self.plan_model_us is None and self.plan_safe_reveals is None
                  and not self.setup_cells and not self.reveal_cells
                  and not self.logical_mines_before and not self.logical_mines_after,
                  "Initial input cannot carry a plan, inference or logical M.")
        else:
            _need(self.semantic_kind != "INITIAL", "Only action zero has INITIAL semantics.")
        if not self.plan_actions:
            _need(self.plan_model_us is None and self.plan_safe_reveals is None
                  and not self.setup_cells and not self.reveal_cells,
                  "No selected plan permits no plan metrics or candidate cell claims.")
        else:
            _need(self.plan_actions[0] == (self.action, self.target),
                  "Selected plan must begin with the executed input.")
            _int(self.plan_model_us, 1)
            _int(self.plan_safe_reveals)


@dataclass(frozen=True, slots=True)
class GuessCheckpointRecord:
    arm: ArmIdentity
    guess_ordinal: int
    public_clues: tuple
    physical_p: tuple
    effective_p_union_m: tuple
    unresolved: tuple
    mine_budget: int
    unreduced_z: int
    mine_counts: tuple
    probabilities: tuple
    minimum_risk: Fraction
    minimum_ties: tuple
    chosen_target: tuple
    eventual_outcome: Outcome

    def __post_init__(self):
        _record(self.arm, ArmIdentity)
        board = self.arm.board
        _int(self.guess_ordinal, 1)
        _tuple(self.public_clues)
        for entry in self.public_clues:
            _need(type(entry) is tuple and len(entry) == 2, "Invalid public clue entry.")
            _cell(entry[0], board)
            _int(entry[1], 0, 8)
        clue_cells = tuple(e[0] for e in self.public_clues)
        for cells in (clue_cells, self.physical_p, self.effective_p_union_m,
                      self.unresolved, self.minimum_ties):
            _cells(cells, board)
        known, unresolved, clues = set(self.effective_p_union_m), set(self.unresolved), set(clue_cells)
        _need(set(self.physical_p) <= known, "Physical P is not a subset of effective P union M.")
        if self.arm.arm is not Arm.K_P0:
            _need(self.effective_p_union_m == self.physical_p,
                  "Only K-P0 may augment physical P with logical known mines.")
        _need(not (known & unresolved or clues & known or clues & unresolved), "Overlapping premises.")
        _need(len(known) + len(unresolved) + len(clues) == board.width * board.height,
              "Public/effective/unresolved premises must cover the board.")
        _int(self.mine_budget, 1, len(unresolved) - 1)
        _need(self.mine_budget == board.mines - len(known), "Inconsistent remaining mine budget.")
        _int(self.unreduced_z, 1, None)
        _tuple(self.mine_counts)
        _tuple(self.probabilities)
        for entries in (self.mine_counts, self.probabilities):
            _need(all(type(e) is tuple and len(e) == 2 for e in entries), "Invalid cell map entry.")
            _cells(tuple(e[0] for e in entries), board)
            _need(tuple(e[0] for e in entries) == self.unresolved, "Incomplete unresolved cell map.")
        for (_, count), (_, probability) in zip(self.mine_counts, self.probabilities):
            _int(count, 1, self.unreduced_z - 1)
            _fraction(probability, probability=True)
            _need(probability == Fraction(count, self.unreduced_z), "Probability differs from raw m/Z.")
        _need(sum(e[1] for e in self.mine_counts) == self.mine_budget * self.unreduced_z,
              "Unreduced counts do not conserve mine budget.")
        _fraction(self.minimum_risk, probability=True)
        _need(self.minimum_risk == min(e[1] for e in self.probabilities), "Incorrect minimum risk.")
        _need(self.minimum_ties == tuple(c for c, p in self.probabilities if p == self.minimum_risk),
              "Incomplete minimum-risk tie set.")
        _cell(self.chosen_target, board)
        _need(self.chosen_target == self.minimum_ties[0],
              "Target must be the first minimum-risk tie in (y, x) order.")
        _enum(self.eventual_outcome, Outcome)


@dataclass(frozen=True, slots=True)
class ProductiveChordWitness:
    action_ordinal: int
    clue: tuple
    physical_flag_neighbors: tuple
    directly_opened_safe_cells: tuple

    def __post_init__(self):
        _int(self.action_ordinal)
        _cell(self.clue)
        _cells(self.physical_flag_neighbors)
        _cells(self.directly_opened_safe_cells)
        _need(bool(self.directly_opened_safe_cells), "Productive CHORD requires safe reveals.")
        for c in self.physical_flag_neighbors + self.directly_opened_safe_cells:
            _need(c != self.clue and max(abs(c[0] - self.clue[0]), abs(c[1] - self.clue[1])) == 1,
                  "Witness cell is not adjacent to clue.")
        _need(not set(self.physical_flag_neighbors).intersection(self.directly_opened_safe_cells),
              "Flagged neighbor cannot be a direct safe reveal.")


@dataclass(frozen=True, slots=True)
class ControlFlagProvenanceRecord:
    flag_ordinal: int
    cell: tuple
    category: FlagCategory
    selected_plan_ref: str | None
    terminal_reveal: Action | None
    terminal_target: tuple | None
    witness: ProductiveChordWitness | None

    def __post_init__(self):
        _int(self.flag_ordinal)
        _cell(self.cell)
        _enum(self.category, FlagCategory)
        if self.category is FlagCategory.CONTROL_FALLBACK_FLAG:
            _need(self.selected_plan_ref is None and self.terminal_reveal is None and self.terminal_target is None,
                  "Fallback has no selected plan/terminal reveal.")
        else:
            _text(self.selected_plan_ref)
            _enum(self.terminal_reveal, Action)
            expected = Action.CHORD if self.category is FlagCategory.CONTROL_SETUP_CHORD_FLAG else Action.OPEN
            _need(self.terminal_reveal is expected, "Provenance/terminal action mismatch.")
            _cell(self.terminal_target)
        if self.witness is not None:
            _record(self.witness, ProductiveChordWitness)
            _need(self.witness.action_ordinal > self.flag_ordinal
                  and self.cell in self.witness.physical_flag_neighbors, "Invalid later CHORD witness binding.")


@dataclass(frozen=True, slots=True)
class AcquisitionRecord:
    action_ordinal: int
    decision_ordinal: int
    cell: tuple
    source: AcquisitionSource
    certificate_ref: str
    certificate_sha256: str

    def __post_init__(self):
        _int(self.action_ordinal)
        _int(self.decision_ordinal)
        _cell(self.cell)
        _enum(self.source, AcquisitionSource)
        _text(self.certificate_ref)
        _hex(self.certificate_sha256)


_CERTIFICATE_COMMON = ("source", "observation", "num_mines", "target", "retained_mines", "status")
_LOCAL_FACTS = ("target", "clue", "clue_value", "physical_flags", "logical_mines",
                "unresolved", "residual", "antecedents")
_EXACT_FACTS = ("target", "total_worlds", "mine_worlds", "antecedents", "oracle_a_status",
                "oracle_a_variable_count", "oracle_a_envelope", "oracle_a_reason", "arithmetic_evidence")


def _signed_exact(value):
    _need(type(value) is int, "Expected an exact signed integer.")


def _observation(value):
    _tuple(value)
    _need(bool(value), "Expected nonempty public observation.")
    width = None
    for row in value:
        _tuple(row)
        _need(bool(row) and (width is None or len(row) == width), "Expected rectangular public observation.")
        width = len(row)
        for cell in row:
            _need(type(cell) is int and (cell in (-2, -3) or 0 <= cell <= 8),
                  "Only exact public hidden/flag/clue glyphs are allowed.")


def _named(value, names):
    _tuple(value)
    _need(all(type(item) is tuple and len(item) == 2 and type(item[0]) is str for item in value)
          and tuple(item[0] for item in value) == names, "Unknown/missing/out-of-order named evidence fields.")
    return dict(value)


def _count_map(value):
    _tuple(value)
    _need(all(type(item) is tuple and len(item) == 2 for item in value), "Expected immutable cell/count pairs.")
    _cells(tuple(item[0] for item in value))
    for _, count in value:
        _signed_exact(count)


def _digests(value):
    _tuple(value)
    for digest in value:
        _hex(digest)


def _certificate_premises(value):
    _tuple(value)
    _need(bool(value) and type(value[0]) is tuple and len(value[0]) == 2
          and value[0][0] == "source" and type(value[0][1]) is str
          and value[0][1] in ("LOCAL", "EXACT_GLOBAL"), "Missing exact certificate source.")
    source = value[0][1]
    names = _CERTIFICATE_COMMON + (("clue",) if source == "LOCAL" else
                                   ("total_worlds", "mine_worlds", "exact_reached"))
    facts = _named(value, names)
    _observation(facts["observation"])
    _int(facts["num_mines"])
    _cell(facts["target"])
    _cells(facts["retained_mines"])
    _need(type(facts["status"]) is str and facts["status"] in ("PLAYING", "WON", "LOST"),
          "Unknown exact certificate game status.")
    if source == "LOCAL":
        _cell(facts["clue"])
    else:
        _signed_exact(facts["total_worlds"])
        _count_map(facts["mine_worlds"])
        _need(type(facts["exact_reached"]) is bool, "Expected exact reachability bool.")
    return facts


def _certificate_facts(value, premises, verifier_status):
    _tuple(value)
    if not value:
        _need(verifier_status != "PASS", "Passing verifier must retain full public facts.")
        return
    local = premises["source"] == "LOCAL"
    facts = _named(value, _LOCAL_FACTS if local else _EXACT_FACTS)
    _cell(facts["target"])
    _need(facts["target"] == premises["target"], "Verifier target differs from certificate.")
    _cells(facts["antecedents"])
    if local:
        _cell(facts["clue"])
        _need(facts["clue"] == premises["clue"], "Verifier clue differs from certificate.")
        _int(facts["clue_value"], 0, 8)
        x, y = facts["clue"]
        observation = premises["observation"]
        _need(y < len(observation) and x < len(observation[0])
              and facts["clue_value"] == observation[y][x],
              "Verifier clue value differs from the public certificate observation.")
        for name in ("physical_flags", "logical_mines", "unresolved"):
            _cells(facts[name])
        _signed_exact(facts["residual"])
    else:
        _signed_exact(facts["total_worlds"])
        _signed_exact(facts["mine_worlds"])
        _need(facts["total_worlds"] == facts["mine_worlds"] == premises["total_worlds"],
              "Verifier exact counts differ from certificate world count.")
        _text(facts["oracle_a_status"])
        _int(facts["oracle_a_variable_count"])
        _int(facts["oracle_a_envelope"])
        if facts["oracle_a_reason"] is not None:
            _text(facts["oracle_a_reason"], empty=True)
        _text(facts["arithmetic_evidence"])


def certificate_premises_digest(premises):
    """Bind exactly the two accepted certificate shapes to their legacy SHA.

    These fixed tags reproduce the existing certificate codec identity without
    importing its graph registry or admitting arbitrary objects into I1.
    """
    p = _certificate_premises(premises)
    fields = {
        "observation": {"tuple": [{"tuple": list(row)} for row in p["observation"]]},
        "num_mines": p["num_mines"], "target": {"tuple": list(p["target"])},
        "retained_mines": {"coordinate_set": [{"tuple": list(cell)} for cell in p["retained_mines"]]},
        "status": {"enum": "GameStatus", "name": p["status"]},
    }
    if p["source"] == "LOCAL":
        name = "LocalMineCertificate"
        fields["clue"] = {"tuple": list(p["clue"])}
    else:
        name = "ExactGlobalMineCertificate"
        fields["total_worlds"] = p["total_worlds"]
        fields["mine_worlds"] = {"tuple": [
            {"tuple": [{"tuple": list(cell)}, count]} for cell, count in p["mine_worlds"]]}
        fields["exact_reached"] = p["exact_reached"]
    wire = {"record": "experiments.program_k_oracles." + name, "fields": fields}
    try:
        encoded = json.dumps(wire, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, OverflowError) as error:
        raise RecordError("Certificate premises exceed the accepted legacy identity codec.") from error
    return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class CertificateAuditRecord:
    """Detached public premises and verifier facts, never a live proof object."""

    action_ordinal: int
    acquisition: AcquisitionRecord
    certificate_premises: tuple
    prior_certificate_sha256s: tuple
    status: AuditStatus
    verifier_status: str
    detail: str
    owned_m_before: tuple
    owned_m_after: tuple
    verifier_facts: tuple

    def __post_init__(self):
        _int(self.action_ordinal, 1)
        _record(self.acquisition, AcquisitionRecord)
        _enum(self.status, AuditStatus)
        _need(type(self.verifier_status) is str and self.verifier_status in ("PASS", "FAIL", "INCOMPLETE"),
              "Unknown public verifier status.")
        _text(self.detail)
        premises = _certificate_premises(self.certificate_premises)
        _certificate_facts(self.verifier_facts, premises, self.verifier_status)
        _digests(self.prior_certificate_sha256s)
        _cells(self.owned_m_before)
        _cells(self.owned_m_after)
        _need(self.action_ordinal == self.acquisition.action_ordinal
              and premises["target"] == self.acquisition.cell
              and premises["source"] == self.acquisition.source.value
              and self.acquisition.certificate_ref == "sha256:" + self.acquisition.certificate_sha256
              and self.acquisition.certificate_sha256 == certificate_premises_digest(self.certificate_premises),
              "Acquisition boundary/source/target/certificate identity differs.")
        # The retained SHA is the accepted certificate codec identity, not an I1
        # record hash. Full named premises remain the evidence for later auditing.
        _need(self.owned_m_before == premises["retained_mines"]
              and self.owned_m_after == tuple(sorted(set(self.owned_m_before) | {premises["target"]},
                                                    key=lambda cell: (cell[1], cell[0]))),
              "Owned M does not bind the certificate retained set and target.")
        _need((self.verifier_status == "FAIL") == (self.status is AuditStatus.FAIL),
              "A failed public verifier cannot be downgraded.")
        _need(self.status is not AuditStatus.PASS or self.verifier_status == "PASS",
              "PASS requires the public verifier to PASS.")


@dataclass(frozen=True, slots=True)
class OracleBExactSnapshot:
    """Nested exact semantic premise; deliberately not a top-level wire kind.

    Exact but erroneous count values can be retained as failed audit evidence.
    No constructor repairs classifications, kernels or materialized observations.
    """

    unresolved_cells: tuple
    frontier_cells: tuple
    unconstrained_cells: tuple
    total_worlds: int
    mine_worlds: tuple
    G0: tuple
    G1: tuple
    minimum_risk: Fraction | None
    minimum_risk_cells: tuple
    shared_kernel_evidence: str
    kernel: str
    materialized_observation: tuple

    def __post_init__(self):
        for value in (self.unresolved_cells, self.frontier_cells, self.unconstrained_cells,
                      self.G0, self.G1, self.minimum_risk_cells):
            _cells(value)
        _signed_exact(self.total_worlds)
        _count_map(self.mine_worlds)
        if self.minimum_risk is not None:
            _fraction(self.minimum_risk)
        _text(self.shared_kernel_evidence)
        _text(self.kernel)
        _observation(self.materialized_observation)


@dataclass(frozen=True, slots=True)
class OracleBAuditRecord:
    action_ordinal: int
    phase: str
    logical_mines: tuple
    public_observation: tuple
    prior_certificate_sha256s: tuple
    input_digest: str
    expected_digest: str
    actual_digest: str | None
    status: AuditStatus
    differences: tuple
    expected: OracleBExactSnapshot
    actual: OracleBExactSnapshot | None

    def __post_init__(self):
        _int(self.action_ordinal, 1)
        _need(type(self.phase) is str and self.phase in ("D", "E"), "Oracle-B phase must be D or E.")
        _cells(self.logical_mines)
        _observation(self.public_observation)
        _digests(self.prior_certificate_sha256s)
        _hex(self.input_digest)
        _hex(self.expected_digest)
        _enum(self.status, AuditStatus)
        _tuple(self.differences)
        for reason in self.differences:
            _text(reason)
        _record(self.expected, OracleBExactSnapshot)
        _need(self.expected_digest == oracle_b_snapshot_digest(self.expected), "Expected semantic digest differs.")
        _need((self.actual is None) == (self.actual_digest is None), "Actual snapshot/digest presence differs.")
        if self.actual is not None:
            _record(self.actual, OracleBExactSnapshot)
            _hex(self.actual_digest)
            _need(self.actual_digest == oracle_b_snapshot_digest(self.actual), "Actual semantic digest differs.")
        exact_pass = (self.actual is not None and self.expected == self.actual and not self.differences
                      and self.expected.total_worlds > 0 and self.actual.total_worlds > 0)
        _need((self.status is AuditStatus.PASS) == exact_pass,
              "Oracle PASS requires exact equal full premises, positive worlds and no differences.")
        _need(self.status is AuditStatus.PASS or bool(self.differences),
              "Nonpassing Oracle evidence needs explicit differences/prerequisite reasons.")


@dataclass(frozen=True, slots=True)
class DeterminismAuditRecord:
    """Summary only; selected repeats also require both full I1 semantic streams."""

    selected: bool
    first_digest: str | None
    repeat_digest: str | None
    status: AuditStatus | None
    first_difference_path: str | None

    def __post_init__(self):
        _need(type(self.selected) is bool, "Expected exact determinism selection bool.")
        if not self.selected:
            _need(self.first_digest is self.repeat_digest is self.status is self.first_difference_path is None,
                  "Unselected determinism cannot claim any result.")
            return
        _hex(self.first_digest)
        _enum(self.status, AuditStatus)
        if self.repeat_digest is None:
            _need(self.status is AuditStatus.INCOMPLETE and self.first_difference_path is None,
                  "Missing repeat requires INCOMPLETE and no difference.")
            return
        _hex(self.repeat_digest)
        _need(self.status in (AuditStatus.PASS, AuditStatus.FAIL), "Completed comparison needs PASS or FAIL.")
        if self.status is AuditStatus.PASS:
            _need(self.first_digest == self.repeat_digest and self.first_difference_path is None,
                  "PASS summary needs equal digests and no difference.")
        else:
            _text(self.first_difference_path)


@dataclass(frozen=True, slots=True)
class EvaluatorRecord:
    arm: ArmIdentity
    assertion: AssertionCategory
    targets: tuple
    status: EvaluationStatus
    reason_code: str
    detail: str

    def __post_init__(self):
        _record(self.arm, ArmIdentity)
        _enum(self.assertion, AssertionCategory)
        _cells(self.targets, self.arm.board)
        _enum(self.status, EvaluationStatus)
        _text(self.reason_code)
        _text(self.detail, empty=True)


@dataclass(frozen=True, slots=True)
class G5ExposureSummary:
    """Supplied CONTROL counts; setup-CHORD accounting never qualifies exposure.

    The two qualifying counts refer to flags with the frozen later productive-
    CHORD witness. Their evidence validation belongs to the later validator.
    """

    diagnostic_setup_chord_flags: int
    qualifying_fallback_flags: int
    qualifying_flag_to_open_setup_flags: int

    def __post_init__(self):
        for v in (self.diagnostic_setup_chord_flags, self.qualifying_fallback_flags,
                  self.qualifying_flag_to_open_setup_flags):
            _int(v)

    @property
    def is_exposed(self):
        return self.qualifying_fallback_flags + self.qualifying_flag_to_open_setup_flags > 0


@dataclass(frozen=True, slots=True)
class PairComparisonRecord:
    board: BoardIdentity
    control_outcome: Outcome
    kp0_outcome: Outcome
    p3_status: P3Status
    ww_delta_us: int | None
    g5: G5ExposureSummary
    diagnosis: str

    def __post_init__(self):
        _record(self.board, BoardIdentity)
        _enum(self.control_outcome, Outcome)
        _enum(self.kp0_outcome, Outcome)
        _enum(self.p3_status, P3Status)
        both_win = self.control_outcome is Outcome.WIN and self.kp0_outcome is Outcome.WIN
        _need((self.ww_delta_us is not None) == both_win,
              "WW delta must be present exactly when both outcomes are WIN.")
        if self.ww_delta_us is not None:
            _int(self.ww_delta_us, -UINT64_MAX, UINT64_MAX)
        _record(self.g5, G5ExposureSummary)
        _text(self.diagnosis)


@dataclass(frozen=True, slots=True)
class OperationEventRecord:
    phase: Phase
    unit_id: str
    event_kind: EventKind
    elapsed_ns: int
    ordinal: int
    status: OperationStatus

    def __post_init__(self):
        _enum(self.phase, Phase)
        _text(self.unit_id)
        _enum(self.event_kind, EventKind)
        _int(self.elapsed_ns)
        _int(self.ordinal)
        _enum(self.status, OperationStatus)


@dataclass(frozen=True, slots=True)
class ResourceSampleRecord:
    unit_id: str
    process_role: ProcessRole
    worker_bytes: int
    coordinator_bytes: int
    combined_bytes: int
    timestamp: str
    elapsed_ns: int
    method: MemoryMethod

    def __post_init__(self):
        _text(self.unit_id)
        _enum(self.process_role, ProcessRole)
        for v in (self.worker_bytes, self.coordinator_bytes, self.combined_bytes, self.elapsed_ns):
            _int(v)
        _need(self.combined_bytes == self.worker_bytes + self.coordinator_bytes, "Memory total mismatch.")
        _text(self.timestamp)
        _enum(self.method, MemoryMethod)


@dataclass(frozen=True, slots=True)
class StreamDigest:
    name: str
    sha256: str
    byte_length: int
    record_count: int

    def __post_init__(self):
        _text(self.name)
        _hex(self.sha256)
        _int(self.byte_length)
        _int(self.record_count)


@dataclass(frozen=True, slots=True)
class CompletionReceipt:
    manifest_sha256: str
    corpus_sha256: str
    source_sha256: str
    protocol_sha256: str
    streams: tuple
    state: CompletionState

    def __post_init__(self):
        for v in (self.manifest_sha256, self.corpus_sha256, self.source_sha256, self.protocol_sha256):
            _hex(v)
        _tuple(self.streams)
        for stream in self.streams:
            _record(stream, StreamDigest)
        names = tuple(s.name for s in self.streams)
        _need(names == tuple(sorted(set(names))), "Stream names must be sorted/unique.")
        _enum(self.state, CompletionState)


# Explicit encoding branches: helper types are field-specific, never top-level
# graph nodes. No module catalog, arbitrary dataclass traversal or dynamic import.
def _wire(r):
    cls = type(r)
    _need(cls in (ProtocolIdentity, RuntimeIdentity, SourceBlobIdentity, CorpusIdentity,
                  BoardIdentity, ArmIdentity, PhysicalInputRecord, PublicEffectRecord,
                  TerminalEffectRecord, DecisionSpanRecord, ActionDecisionRecord, GuessCheckpointRecord,
                  ControlFlagProvenanceRecord, AcquisitionRecord, EvaluatorRecord,
                  PairComparisonRecord, OperationEventRecord, ResourceSampleRecord, CompletionReceipt,
                  CertificateAuditRecord, OracleBAuditRecord, DeterminismAuditRecord),
          "Unsupported record type/subclass.")
    cls.__post_init__(r)  # also rejects records corrupted through object.__setattr__
    if cls is ProtocolIdentity:
        kind, f = "protocol_identity", dict(path=r.path, sha256=r.sha256, blob_id=r.blob_id, freeze_commit=r.freeze_commit)
    elif cls is RuntimeIdentity:
        kind, f = "runtime_identity", dict(python_implementation=r.python_implementation, python_version=r.python_version,
                                          os=r.os, platform=r.platform, architecture=r.architecture, host=r.host)
    elif cls is SourceBlobIdentity:
        kind, f = "source_blob_identity", dict(path=r.path, blob_id=r.blob_id, sha256=r.sha256, byte_length=r.byte_length)
    elif cls is CorpusIdentity:
        kind, f = "corpus_identity", dict(frame_label=r.frame_label, low=r.low, high=r.high, n=r.n,
                                         ordered_indices=r.ordered_indices, corpus_sha256=r.corpus_sha256, exclusions=r.exclusions)
    elif cls is BoardIdentity:
        kind, f = "board_identity", dict(game_index=r.game_index, fingerprint=r.fingerprint, width=r.width, height=r.height,
                                        mines=r.mines, first_click=r.first_click, generator_identity=r.generator_identity,
                                        spec_identity=r.spec_identity)
    elif cls is ArmIdentity:
        kind, f = "arm_identity", dict(arm=r.arm.value, board=_wire(r.board), run_id=r.run_id, unit_id=r.unit_id)
    elif cls is PhysicalInputRecord:
        kind, f = "physical_input", dict(action_ordinal=r.action_ordinal, action=r.action.value, target=r.target,
                                        cursor_before=r.cursor_before, input_us=r.input_us, cumulative_us=r.cumulative_us,
                                        after_status=r.after_status.value)
    elif cls is PublicEffectRecord:
        kind, f = "public_effect", dict(action_ordinal=r.action_ordinal,
                                       changes=[dict(cell=c.cell, before=c.before, after=c.after) for c in r.changes],
                                       before_status=r.before_status.value, after_status=r.after_status.value)
    elif cls is TerminalEffectRecord:
        kind, f = "terminal_effect", dict(action_ordinal=r.action_ordinal,
                                         changes=[dict(cell=c.cell, presentation=c.presentation.value) for c in r.changes],
                                         terminal_status=r.terminal_status.value)
    elif cls is DecisionSpanRecord:
        kind, f = "decision_span", dict(action_ordinal=r.action_ordinal, scope=r.scope.value, duration_ns=r.duration_ns)
    elif cls is ActionDecisionRecord:
        kind, f = "action_decision", dict(arm=_wire(r.arm), action_ordinal=r.action_ordinal,
                                          category=r.category, semantic_kind=r.semantic_kind,
                                          action=r.action.value, target=r.target,
                                          plan_actions=[(action.value, cell) for action, cell in r.plan_actions],
                                          plan_model_us=r.plan_model_us, plan_safe_reveals=r.plan_safe_reveals,
                                          setup_cells=r.setup_cells, reveal_cells=r.reveal_cells,
                                          logical_mines_before=r.logical_mines_before,
                                          logical_mines_after=r.logical_mines_after)
    elif cls is GuessCheckpointRecord:
        kind, f = "guess_checkpoint", dict(arm=_wire(r.arm), guess_ordinal=r.guess_ordinal, public_clues=r.public_clues,
                                           physical_p=r.physical_p, effective_p_union_m=r.effective_p_union_m,
                                           unresolved=r.unresolved, mine_budget=r.mine_budget, unreduced_z=_big(r.unreduced_z),
                                           mine_counts=[(c, _big(m)) for c, m in r.mine_counts],
                                           probabilities=[(c, _wf(p)) for c, p in r.probabilities],
                                           minimum_risk=_wf(r.minimum_risk), minimum_ties=r.minimum_ties,
                                           chosen_target=r.chosen_target, eventual_outcome=r.eventual_outcome.value)
    elif cls is ControlFlagProvenanceRecord:
        w = r.witness
        kind, f = "control_flag_provenance", dict(flag_ordinal=r.flag_ordinal, cell=r.cell, category=r.category.value,
                                                 selected_plan_ref=r.selected_plan_ref,
                                                 terminal_reveal=None if r.terminal_reveal is None else r.terminal_reveal.value,
                                                 terminal_target=r.terminal_target,
                                                 witness=None if w is None else dict(action_ordinal=w.action_ordinal, clue=w.clue,
                                                 physical_flag_neighbors=w.physical_flag_neighbors,
                                                 directly_opened_safe_cells=w.directly_opened_safe_cells))
    elif cls is AcquisitionRecord:
        kind, f = "acquisition", dict(action_ordinal=r.action_ordinal, decision_ordinal=r.decision_ordinal, cell=r.cell,
                                     source=r.source.value, certificate_ref=r.certificate_ref, certificate_sha256=r.certificate_sha256)
    elif cls is CertificateAuditRecord:
        kind, f = "certificate_audit", dict(
            action_ordinal=r.action_ordinal, acquisition=_wire(r.acquisition),
            certificate_premises=_w_certificate_premises(r.certificate_premises),
            prior_certificate_sha256s=r.prior_certificate_sha256s, status=r.status.value,
            verifier_status=r.verifier_status, detail=r.detail, owned_m_before=r.owned_m_before,
            owned_m_after=r.owned_m_after,
            verifier_facts=_w_certificate_facts(r.verifier_facts, r.acquisition.source))
    elif cls is OracleBAuditRecord:
        kind, f = "oracle_b_audit", dict(
            action_ordinal=r.action_ordinal, phase=r.phase, logical_mines=r.logical_mines,
            public_observation=r.public_observation, prior_certificate_sha256s=r.prior_certificate_sha256s,
            input_digest=r.input_digest, expected_digest=r.expected_digest, actual_digest=r.actual_digest,
            status=r.status.value, differences=r.differences, expected=_w_oracle_snapshot(r.expected),
            actual=None if r.actual is None else _w_oracle_snapshot(r.actual))
    elif cls is DeterminismAuditRecord:
        kind, f = "determinism_audit", dict(
            selected=r.selected, first_digest=r.first_digest, repeat_digest=r.repeat_digest,
            status=None if r.status is None else r.status.value, first_difference_path=r.first_difference_path)
    elif cls is EvaluatorRecord:
        kind, f = "evaluator", dict(arm=_wire(r.arm), assertion=r.assertion.value, targets=r.targets, status=r.status.value,
                                   reason_code=r.reason_code, detail=r.detail)
    elif cls is PairComparisonRecord:
        kind, f = "pair_comparison", dict(board=_wire(r.board), control_outcome=r.control_outcome.value,
                                         kp0_outcome=r.kp0_outcome.value, p3_status=r.p3_status.value, ww_delta_us=r.ww_delta_us,
                                         g5=dict(diagnostic_setup_chord_flags=r.g5.diagnostic_setup_chord_flags,
                                                 qualifying_fallback_flags=r.g5.qualifying_fallback_flags,
                                                 qualifying_flag_to_open_setup_flags=r.g5.qualifying_flag_to_open_setup_flags), diagnosis=r.diagnosis)
    elif cls is OperationEventRecord:
        kind, f = "operation_event", dict(phase=r.phase.value, unit_id=r.unit_id, event_kind=r.event_kind.value,
                                         elapsed_ns=r.elapsed_ns, ordinal=r.ordinal, status=r.status.value)
    elif cls is ResourceSampleRecord:
        kind, f = "resource_sample", dict(unit_id=r.unit_id, process_role=r.process_role.value, worker_bytes=r.worker_bytes,
                                         coordinator_bytes=r.coordinator_bytes, combined_bytes=r.combined_bytes,
                                         timestamp=r.timestamp, elapsed_ns=r.elapsed_ns, method=r.method.value)
    else:
        kind, f = "completion_receipt", dict(manifest_sha256=r.manifest_sha256, corpus_sha256=r.corpus_sha256,
                                            source_sha256=r.source_sha256, protocol_sha256=r.protocol_sha256,
                                            streams=[dict(name=s.name, sha256=s.sha256, byte_length=s.byte_length,
                                                          record_count=s.record_count) for s in r.streams], state=r.state.value)
    return dict(kind=kind, version=SCHEMA_VERSION, fields=f)


def _big(value):
    # Hex avoids Python's process-global decimal digit limit for exact world counts.
    # This tag is used only for the explicit unbounded count/Fraction fields.
    return {"integer_hex": hex(value)}


def _wf(value):
    return {"fraction": [_big(value.numerator), _big(value.denominator)]}


def _w_certificate_premises(value):
    p = dict(value)  # Called only after the closed named-field schema is validated.
    common = (("source", p["source"]), ("observation", p["observation"]),
              ("num_mines", p["num_mines"]), ("target", p["target"]),
              ("retained_mines", p["retained_mines"]), ("status", p["status"]))
    if p["source"] == "LOCAL":
        return common + (("clue", p["clue"]),)
    return common + (("total_worlds", _big(p["total_worlds"])),
                     ("mine_worlds", tuple((cell, _big(count)) for cell, count in p["mine_worlds"])),
                     ("exact_reached", p["exact_reached"]))


def _w_certificate_facts(value, source):
    if not value or source is AcquisitionSource.LOCAL:
        return value
    f = dict(value)
    return (("target", f["target"]), ("total_worlds", _big(f["total_worlds"])),
            ("mine_worlds", _big(f["mine_worlds"])), ("antecedents", f["antecedents"]),
            ("oracle_a_status", f["oracle_a_status"]), ("oracle_a_variable_count", f["oracle_a_variable_count"]),
            ("oracle_a_envelope", f["oracle_a_envelope"]), ("oracle_a_reason", f["oracle_a_reason"]),
            ("arithmetic_evidence", f["arithmetic_evidence"]))


def _w_oracle_snapshot(value):
    _record(value, OracleBExactSnapshot)
    return dict(unresolved_cells=value.unresolved_cells, frontier_cells=value.frontier_cells,
                unconstrained_cells=value.unconstrained_cells, total_worlds=_big(value.total_worlds),
                mine_worlds=tuple((cell, _big(count)) for cell, count in value.mine_worlds),
                G0=value.G0, G1=value.G1,
                minimum_risk=None if value.minimum_risk is None else _wf(value.minimum_risk),
                minimum_risk_cells=value.minimum_risk_cells,
                shared_kernel_evidence=value.shared_kernel_evidence, kernel=value.kernel,
                materialized_observation=value.materialized_observation)


def oracle_b_snapshot_digest(snapshot):
    """Corroborating canonical hash; exact snapshot equality remains mandatory."""
    return sha256(json.dumps(_w_oracle_snapshot(snapshot), sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def encode(record):
    """Canonical UTF-8 JSON (ASCII escaped), compact, lexically sorted object keys."""
    return json.dumps(_wire(record), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _keys(value, names):
    _need(type(value) is dict and set(value) == set(names.split()), "Unknown/missing fields.")
    return value


def _list(value):
    _need(type(value) is list, "Expected JSON array.")
    return value


def _dc(value):
    _need(type(value) is list and len(value) == 2, "Expected coordinate array.")
    cell = tuple(value)
    _cell(cell)
    return cell


def _dcs(value):
    cells = tuple(_dc(c) for c in _list(value))
    _cells(cells)
    return cells


def _de(value, cls):
    _need(type(value) is str, "Enum value must be exact text.")
    try:
        return cls(value)
    except ValueError as error:
        raise RecordError("Unknown enum value.") from error


def _db(value):
    _keys(value, "integer_hex")
    s = value["integer_hex"]
    _need(type(s) is str and s.startswith(("0x", "-0x")), "Expected tagged exact integer.")
    try:
        result = int(s, 16)
    except ValueError as error:
        raise RecordError("Invalid integer hex.") from error
    _need(hex(result) == s, "Noncanonical integer hex.")
    return result


def _df(value):
    _keys(value, "fraction")
    pair = _list(value["fraction"])
    _need(len(pair) == 2, "Fraction requires numerator/denominator.")
    numerator, denominator = _db(pair[0]), _db(pair[1])
    _need(denominator > 0, "Nonpositive denominator.")
    result = Fraction(numerator, denominator)
    _need((result.numerator, result.denominator) == (numerator, denominator), "Unreduced Fraction encoding.")
    return result


def _map(value, convert):
    result = []
    for item in _list(value):
        _need(type(item) is list and len(item) == 2, "Invalid cell map entry.")
        result.append((_dc(item[0]), convert(item[1])))
    return tuple(result)


def _nested(value, cls):
    r = _from_wire(value)
    _record(r, cls)
    return r


def _d_observation(value):
    result = tuple(tuple(_list(row)) for row in _list(value))
    _observation(result)
    return result


def _d_named(value, names):
    pairs = _list(value)
    _need(all(type(item) is list and len(item) == 2 and type(item[0]) is str for item in pairs)
          and tuple(item[0] for item in pairs) == names, "Unknown/missing/out-of-order named wire fields.")
    return dict(pairs)


def _d_certificate_premises(value):
    pairs = _list(value)
    _need(bool(pairs) and type(pairs[0]) is list and len(pairs[0]) == 2
          and pairs[0][0] == "source" and type(pairs[0][1]) is str
          and pairs[0][1] in ("LOCAL", "EXACT_GLOBAL"), "Missing certificate wire source.")
    local = pairs[0][1] == "LOCAL"
    p = _d_named(value, _CERTIFICATE_COMMON + (("clue",) if local else
                  ("total_worlds", "mine_worlds", "exact_reached")))
    common = (("source", p["source"]), ("observation", _d_observation(p["observation"])),
              ("num_mines", p["num_mines"]), ("target", _dc(p["target"])),
              ("retained_mines", _dcs(p["retained_mines"])), ("status", p["status"]))
    if local:
        return common + (("clue", _dc(p["clue"])),)
    return common + (("total_worlds", _db(p["total_worlds"])),
                     ("mine_worlds", _map(p["mine_worlds"], _db)), ("exact_reached", p["exact_reached"]))


def _d_certificate_facts(value, source):
    if not _list(value):
        return ()
    local = source is AcquisitionSource.LOCAL
    f = _d_named(value, _LOCAL_FACTS if local else _EXACT_FACTS)
    if local:
        return (("target", _dc(f["target"])), ("clue", _dc(f["clue"])), ("clue_value", f["clue_value"]),
                ("physical_flags", _dcs(f["physical_flags"])), ("logical_mines", _dcs(f["logical_mines"])),
                ("unresolved", _dcs(f["unresolved"])), ("residual", f["residual"]),
                ("antecedents", _dcs(f["antecedents"])))
    return (("target", _dc(f["target"])), ("total_worlds", _db(f["total_worlds"])),
            ("mine_worlds", _db(f["mine_worlds"])), ("antecedents", _dcs(f["antecedents"])),
            ("oracle_a_status", f["oracle_a_status"]), ("oracle_a_variable_count", f["oracle_a_variable_count"]),
            ("oracle_a_envelope", f["oracle_a_envelope"]), ("oracle_a_reason", f["oracle_a_reason"]),
            ("arithmetic_evidence", f["arithmetic_evidence"]))


def _d_oracle_snapshot(value):
    f = _keys(value, "unresolved_cells frontier_cells unconstrained_cells total_worlds mine_worlds G0 G1 minimum_risk minimum_risk_cells shared_kernel_evidence kernel materialized_observation")
    return OracleBExactSnapshot(
        _dcs(f["unresolved_cells"]), _dcs(f["frontier_cells"]), _dcs(f["unconstrained_cells"]),
        _db(f["total_worlds"]), _map(f["mine_worlds"], _db), _dcs(f["G0"]), _dcs(f["G1"]),
        None if f["minimum_risk"] is None else _df(f["minimum_risk"]), _dcs(f["minimum_risk_cells"]),
        f["shared_kernel_evidence"], f["kernel"], _d_observation(f["materialized_observation"]))


def _from_wire(value):
    _keys(value, "kind version fields")
    _need(type(value["version"]) is int and value["version"] == SCHEMA_VERSION, "Unknown schema version.")
    k, f = value["kind"], value["fields"]
    _need(type(k) is str, "Invalid record kind.")
    if k == "protocol_identity":
        _keys(f, "path sha256 blob_id freeze_commit")
        return ProtocolIdentity(f["path"], f["sha256"], f["blob_id"], f["freeze_commit"])
    if k == "runtime_identity":
        _keys(f, "python_implementation python_version os platform architecture host")
        return RuntimeIdentity(f["python_implementation"], f["python_version"], f["os"], f["platform"], f["architecture"], f["host"])
    if k == "source_blob_identity":
        _keys(f, "path blob_id sha256 byte_length")
        return SourceBlobIdentity(f["path"], f["blob_id"], f["sha256"], f["byte_length"])
    if k == "corpus_identity":
        _keys(f, "frame_label low high n ordered_indices corpus_sha256 exclusions")
        return CorpusIdentity(f["frame_label"], f["low"], f["high"], f["n"], tuple(_list(f["ordered_indices"])),
                              f["corpus_sha256"], tuple(_list(f["exclusions"])))
    if k == "board_identity":
        _keys(f, "game_index fingerprint width height mines first_click generator_identity spec_identity")
        return BoardIdentity(f["game_index"], f["fingerprint"], f["width"], f["height"], f["mines"], _dc(f["first_click"]),
                             f["generator_identity"], f["spec_identity"])
    if k == "arm_identity":
        _keys(f, "arm board run_id unit_id")
        return ArmIdentity(_de(f["arm"], Arm), _nested(f["board"], BoardIdentity), f["run_id"], f["unit_id"])
    if k == "physical_input":
        _keys(f, "action_ordinal action target cursor_before input_us cumulative_us after_status")
        return PhysicalInputRecord(f["action_ordinal"], _de(f["action"], Action), _dc(f["target"]), _dc(f["cursor_before"]),
                                   f["input_us"], f["cumulative_us"], _de(f["after_status"], Status))
    if k == "public_effect":
        _keys(f, "action_ordinal changes before_status after_status")
        changes = []
        for c in _list(f["changes"]):
            _keys(c, "cell before after")
            changes.append(PublicCellChange(_dc(c["cell"]), c["before"], c["after"]))
        return PublicEffectRecord(f["action_ordinal"], tuple(changes), _de(f["before_status"], Status), _de(f["after_status"], Status))
    if k == "terminal_effect":
        _keys(f, "action_ordinal changes terminal_status")
        changes = []
        for c in _list(f["changes"]):
            _keys(c, "cell presentation")
            changes.append(TerminalCellChange(_dc(c["cell"]), _de(c["presentation"], TerminalPresentation)))
        return TerminalEffectRecord(f["action_ordinal"], tuple(changes), _de(f["terminal_status"], Status))
    if k == "decision_span":
        _keys(f, "action_ordinal scope duration_ns")
        return DecisionSpanRecord(f["action_ordinal"], _de(f["scope"], DecisionScope), f["duration_ns"])
    if k == "action_decision":
        _keys(f, "arm action_ordinal category semantic_kind action target plan_actions plan_model_us plan_safe_reveals setup_cells reveal_cells logical_mines_before logical_mines_after")
        actions = []
        for entry in _list(f["plan_actions"]):
            _need(type(entry) is list and len(entry) == 2, "Expected a closed plan action pair.")
            actions.append((_de(entry[0], Action), _dc(entry[1])))
        return ActionDecisionRecord(_nested(f["arm"], ArmIdentity), f["action_ordinal"], f["category"],
                                    f["semantic_kind"], _de(f["action"], Action), _dc(f["target"]), tuple(actions),
                                    f["plan_model_us"], f["plan_safe_reveals"], _dcs(f["setup_cells"]),
                                    _dcs(f["reveal_cells"]), _dcs(f["logical_mines_before"]),
                                    _dcs(f["logical_mines_after"]))
    if k == "guess_checkpoint":
        _keys(f, "arm guess_ordinal public_clues physical_p effective_p_union_m unresolved mine_budget unreduced_z mine_counts probabilities minimum_risk minimum_ties chosen_target eventual_outcome")
        return GuessCheckpointRecord(_nested(f["arm"], ArmIdentity), f["guess_ordinal"], _map(f["public_clues"], lambda x: x),
                                     _dcs(f["physical_p"]), _dcs(f["effective_p_union_m"]), _dcs(f["unresolved"]),
                                     f["mine_budget"], _db(f["unreduced_z"]), _map(f["mine_counts"], _db),
                                     _map(f["probabilities"], _df), _df(f["minimum_risk"]), _dcs(f["minimum_ties"]),
                                     _dc(f["chosen_target"]), _de(f["eventual_outcome"], Outcome))
    if k == "control_flag_provenance":
        _keys(f, "flag_ordinal cell category selected_plan_ref terminal_reveal terminal_target witness")
        w = f["witness"]
        if w is not None:
            _keys(w, "action_ordinal clue physical_flag_neighbors directly_opened_safe_cells")
            w = ProductiveChordWitness(w["action_ordinal"], _dc(w["clue"]), _dcs(w["physical_flag_neighbors"]),
                                       _dcs(w["directly_opened_safe_cells"]))
        return ControlFlagProvenanceRecord(f["flag_ordinal"], _dc(f["cell"]), _de(f["category"], FlagCategory),
                                           f["selected_plan_ref"], None if f["terminal_reveal"] is None else _de(f["terminal_reveal"], Action),
                                           None if f["terminal_target"] is None else _dc(f["terminal_target"]), w)
    if k == "acquisition":
        _keys(f, "action_ordinal decision_ordinal cell source certificate_ref certificate_sha256")
        return AcquisitionRecord(f["action_ordinal"], f["decision_ordinal"], _dc(f["cell"]), _de(f["source"], AcquisitionSource),
                                 f["certificate_ref"], f["certificate_sha256"])
    if k == "certificate_audit":
        _keys(f, "action_ordinal acquisition certificate_premises prior_certificate_sha256s status verifier_status detail owned_m_before owned_m_after verifier_facts")
        acquisition = _nested(f["acquisition"], AcquisitionRecord)
        return CertificateAuditRecord(
            f["action_ordinal"], acquisition, _d_certificate_premises(f["certificate_premises"]),
            tuple(_list(f["prior_certificate_sha256s"])), _de(f["status"], AuditStatus), f["verifier_status"],
            f["detail"], _dcs(f["owned_m_before"]), _dcs(f["owned_m_after"]),
            _d_certificate_facts(f["verifier_facts"], acquisition.source))
    if k == "oracle_b_audit":
        _keys(f, "action_ordinal phase logical_mines public_observation prior_certificate_sha256s input_digest expected_digest actual_digest status differences expected actual")
        return OracleBAuditRecord(
            f["action_ordinal"], f["phase"], _dcs(f["logical_mines"]), _d_observation(f["public_observation"]),
            tuple(_list(f["prior_certificate_sha256s"])), f["input_digest"], f["expected_digest"], f["actual_digest"],
            _de(f["status"], AuditStatus), tuple(_list(f["differences"])), _d_oracle_snapshot(f["expected"]),
            None if f["actual"] is None else _d_oracle_snapshot(f["actual"]))
    if k == "determinism_audit":
        _keys(f, "selected first_digest repeat_digest status first_difference_path")
        return DeterminismAuditRecord(f["selected"], f["first_digest"], f["repeat_digest"],
                                      None if f["status"] is None else _de(f["status"], AuditStatus),
                                      f["first_difference_path"])
    if k == "evaluator":
        _keys(f, "arm assertion targets status reason_code detail")
        return EvaluatorRecord(_nested(f["arm"], ArmIdentity), _de(f["assertion"], AssertionCategory), _dcs(f["targets"]),
                               _de(f["status"], EvaluationStatus), f["reason_code"], f["detail"])
    if k == "pair_comparison":
        _keys(f, "board control_outcome kp0_outcome p3_status ww_delta_us g5 diagnosis")
        g = _keys(f["g5"], "diagnostic_setup_chord_flags qualifying_fallback_flags qualifying_flag_to_open_setup_flags")
        return PairComparisonRecord(_nested(f["board"], BoardIdentity), _de(f["control_outcome"], Outcome), _de(f["kp0_outcome"], Outcome),
                                    _de(f["p3_status"], P3Status), f["ww_delta_us"],
                                    G5ExposureSummary(g["diagnostic_setup_chord_flags"], g["qualifying_fallback_flags"],
                                                      g["qualifying_flag_to_open_setup_flags"]), f["diagnosis"])
    if k == "operation_event":
        _keys(f, "phase unit_id event_kind elapsed_ns ordinal status")
        return OperationEventRecord(_de(f["phase"], Phase), f["unit_id"], _de(f["event_kind"], EventKind), f["elapsed_ns"],
                                    f["ordinal"], _de(f["status"], OperationStatus))
    if k == "resource_sample":
        _keys(f, "unit_id process_role worker_bytes coordinator_bytes combined_bytes timestamp elapsed_ns method")
        return ResourceSampleRecord(f["unit_id"], _de(f["process_role"], ProcessRole), f["worker_bytes"], f["coordinator_bytes"],
                                    f["combined_bytes"], f["timestamp"], f["elapsed_ns"], _de(f["method"], MemoryMethod))
    if k == "completion_receipt":
        _keys(f, "manifest_sha256 corpus_sha256 source_sha256 protocol_sha256 streams state")
        streams = []
        for s in _list(f["streams"]):
            _keys(s, "name sha256 byte_length record_count")
            streams.append(StreamDigest(s["name"], s["sha256"], s["byte_length"], s["record_count"]))
        return CompletionReceipt(f["manifest_sha256"], f["corpus_sha256"], f["source_sha256"], f["protocol_sha256"],
                                 tuple(streams), _de(f["state"], CompletionState))
    raise RecordError("Unknown record kind.")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, "Duplicate JSON key.")
        result[key] = value
    return result


def _no_float(value):
    raise RecordError("Floating-point/nonfinite JSON is forbidden.")


def decode(data):
    """Decode only these fixed schemas, then require byte-for-byte canonicality."""
    _need(type(data) is bytes, "Decoder requires exact bytes.")
    try:
        value = json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=_unique,
                           parse_float=_no_float, parse_constant=_no_float)
        result = _from_wire(value)
        _need(encode(result) == data, "Noncanonical JSON bytes.")
        return result
    except RecordError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError) as error:
        raise RecordError("Malformed record encoding.") from error
