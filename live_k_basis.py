"""Selection basis of a K_D23 decision proposal: the display record beside the proposal.

Parent-safe: this module imports no solver and no experiment module. The worker writes the record
(live_k_d23.py); the parent checks its exact format, its presence rule and its binding to the very proposal
it arrived with, and assembles the lines it shows. Nothing here selects, validates or authorises an input,
and nothing is solved again: whether a pair is proven is the worker's execution validation.

The record travels beside the unchanged 14 KProposal keys under ``basis``, exactly as ``info`` does. It is
required for a K_D23 decision proposal (not initial, not preparation) and forbidden on every other proposal.
``binding_sha256`` binds the content to the run, the input number, the policy, the token, the public grid
and the actual input. It is a content binding: no mathematical proof and no authentication of the sender.

The diagnosis configuration of a worker run is read once from the environment. It is the temporary switch
of this copy, not a user setting and not the final product configuration.
"""

from dataclasses import dataclass, fields
import hashlib
import json

import live_k_policy as k
from live_policy import LivePolicyError, POLICY_K_D23, _coordinate, _identity, _integer, _require


BASIS_ID = "K_D23_BASIS_V1"
BASIS_FORMAT = 1
DIAGNOSIS_ENV = "MINESWEEPER_K_D23_DIAGNOSIS"
DIAGNOSIS_NONE, DIAGNOSIS_PSEUDO, DIAGNOSIS_PSEUDO_LINKED = "NONE", "PSEUDO", "PSEUDO_LINKED"
DIAGNOSES = (DIAGNOSIS_NONE, DIAGNOSIS_PSEUDO, DIAGNOSIS_PSEUDO_LINKED)
DEFAULT_DIAGNOSIS = DIAGNOSIS_PSEUDO  # the temporary default of this copy
BRANCH_CERTAIN, BRANCH_GUESS = "CERTAIN_D2", "GUESS_D3"
OPENING, NO_PROVEN, NO_ELIGIBLE = "PROVEN_OPENING_OVERRIDE", "NO_PROVEN_OPENING", "NO_ELIGIBLE_OPENING"
FORCED, TIE, KEPT = "FORCED_5050_FIRST", "TIE_LOOKAHEAD", "K_LC1_GUESS_KEPT"
CERTAIN_REASONS, GUESS_REASONS = (OPENING, NO_PROVEN, NO_ELIGIBLE), (FORCED, TIE, KEPT)
PROPOSED, BLOCKED, EXECUTED = "PROPOSED", "BLOCKED", "EXECUTED"
ERROR_CODES = ("SENDER_INVALID", "MISSING", "UNEXPECTED", "RECEIVED_INVALID")
CALL_LIMITS = (72, 8, 54)  # look-ahead, pseudo, linked: the accepted limits, only checked here
MAX_LINE, MAX_LINES = 1200, 160  # bounds of the record only; the longest stored real-board line was 391
LAST_K_DECISION, LAST_K_INITIAL, LAST_UNKNOWN = "K_DECISION", "K_INITIAL", "UNKNOWN"
SELECTION_TITLE = "선택 이유"
PSEUDO_TITLE = "별도 진단 · pseudo 50/50"
LINKED_TITLE = "별도 진단 · linked 풀림"
NOT_COMPUTED = "이 구성에서는 계산하지 않았다. 계산하지 않은 것이며 진단 결과가 아니다."
# The end lines the parent writes itself, when the last actual input has no basis. Equal, by test, to the
# sentences of experiments.program_d3_explanation, which the parent must not import.
LOSS_INITIAL = "패배 보조 설명: 첫 입력에서 패배했다. 첫 입력에는 입력 전 근거가 없어 유형을 확인할 수 없다."
LOSS_NOT_RECORDED = "패배 보조 설명: 마지막 입력의 입력 전 근거가 없어 패배 유형을 확인할 수 없다."
LOSS_BASE = "기본 결과 LOST는 그대로다."
HELP_LINES = (
    "K의 추측 선택: 확정 입력이 없으면 지뢰 확률이 가장 낮은 칸을 고른다. 아래 두 경우에만 그 선택을 바꾼다.",
    "불가피한 50/50 먼저 처리: 두 칸 중 정확히 하나가 지뢰이고 한쪽에만 닿는 주변 칸이 없거나 모두 확정 지뢰인 쌍이 증명되면 "
    "그 쌍을 먼저 연다. 이때 여는 칸의 지뢰 확률(50%)이 현재 최소 위험보다 높을 수 있으며, 화면에는 실제로 여는 칸의 확률을 "
    "표시한다.",
    "겉보기에 반반인 칸이 모두 불가피한 것은 아니다. 조건이 증명된 쌍만 불가피한 50/50으로 다룬다.",
    "동률 전방 비교: 최소 위험이 같은 칸이 2개에서 8개일 때 각 칸을 연 뒤 다음 입력 하나까지 본 값(S_c, S_v)을 비교한다. "
    "이 값은 제한된 전방 계산값이며 판 전체 승률이 아니다.",
    "지뢰 확률은 지금 공개된 정보에서 그 칸을 한 번 열 때의 위험이다. 두 확률의 차이는 %p로 적는다.",
    "pseudo 50/50 진단: 서로 거울 관계인 두 칸을 찾는 별도 진단이며 선택에 쓰지 않는다. 고립형은 한쪽에만 닿는 주변 칸이 없거나 "
    "모두 확정 지뢰인 쌍, 조건형은 그런 칸에 미확정 칸이 있지만 한 칸이 지뢰인 모든 경우에 그 칸도 지뢰인 쌍이다. 증명되면 판 "
    "전체에서 이기지 못할 확률의 하한을 보여 준다. 하한은 승률이나 최적 선택의 증명이 아니다. 지원 범위에서 조건 불충족, 한도 "
    "미검사, 범위 밖은 서로 다른 결과이며 어느 것도 pseudo 50/50이 없다는 증명이 아니다.",
    "linked 풀림 진단: 한 칸을 열고 살아남았을 때 그 칸이 속하지 않은 쌍 묶음이 풀리는지를 그 한 입력의 범위에서 계산하는 별도 "
    "진단이며 선택에 쓰지 않는다. 칸을 공유하거나 기하적으로 이어진 것과 실제로 풀리는 것은 다르다. 풀리지 않았다는 결과는 "
    "독립의 증명이 아니고, 미검사와 범위 밖은 연결이 없다는 뜻이 아니다. 숫자 0이 나오는 결과는 주변이 함께 열리므로 판단을 "
    "보류할 수 있다.",
    "패배 보조 설명: 마지막 실제 입력에 입력 전 근거가 있을 때만 그 근거로 설명한다. 패배 뒤 공개된 지뢰로 다시 판정하지 않고 "
    "기본 결과(LOST)를 바꾸지 않는다. 추측 허용이 꺼져 입력하지 않은 제안은 입력도 패배 원인도 아니다.",
)


def basis_error(code, detail):
    """An integrity error of the basis record. It ends the owner run through the existing error path."""
    _require(code in ERROR_CODES, "Unknown K basis error code.")
    return LivePolicyError(f"K_D23_BASIS:{code} {detail}"[:4096])


def diagnosis_from_environment(environment):
    """The diagnosis configuration of one worker run. Absent means the default; an unknown value is refused."""
    value = environment.get(DIAGNOSIS_ENV)
    if value is None or value == "":
        return DEFAULT_DIAGNOSIS
    _require(type(value) is str and value in DIAGNOSES, f"Unknown {DIAGNOSIS_ENV} value.")
    return value


def basis_required(proposal):
    """True exactly for a K_D23 decision proposal: not initial, not preparation."""
    _require(type(proposal) is k.KProposal, "K basis rule requires a KProposal.")
    return (proposal.snapshot.policy_id == POLICY_K_D23
            and not proposal.is_preparation and not proposal.initial)


@dataclass(frozen=True)
class KProposalBasis:
    """Why the actual input of one K_D23 decision proposal was chosen, as text and a few exact values.

    ``original`` is the K-LC1 proposal; the actual input is the proposal's own action and target. ``risk``
    is the exact count of the ACTUAL target. ``pseudo`` and ``linked`` are separate diagnoses and never a
    reason. ``loss`` is what to show IF this input ends the game as LOST; it is made before the input."""

    basis_id: str
    token: str
    binding_sha256: str
    diagnosis: str
    branch: str
    reason: str
    original: tuple
    input_changed: bool
    risk: tuple | None
    pair: tuple | None
    short: str
    head_proposed: str
    head_blocked: str | None
    head_executed: str
    body: tuple
    pseudo: tuple
    linked: tuple
    loss: tuple
    calls: tuple
    stage_ns: tuple

    def __post_init__(self):
        _require(type(self.basis_id) is str and self.basis_id == BASIS_ID and _identity(self.token),
                 "Invalid K basis identity.")
        _require(type(self.binding_sha256) is str and len(self.binding_sha256) == 64
                 and all(character in "0123456789abcdef" for character in self.binding_sha256),
                 "Invalid K basis binding digest.")
        _require(type(self.diagnosis) is str and self.diagnosis in DIAGNOSES, "Invalid K basis diagnosis.")
        _require(type(self.branch) is str and self.branch in (BRANCH_CERTAIN, BRANCH_GUESS)
                 and type(self.reason) is str
                 and self.reason in (GUESS_REASONS if self.branch == BRANCH_GUESS else CERTAIN_REASONS),
                 "Invalid K basis branch/reason.")
        _require(type(self.original) is tuple and len(self.original) == 3 and type(self.original[0]) is str
                 and self.original[0] in ("OPEN", "FLAG", "CHORD") and _coordinate(self.original[1:], 30, 16)
                 and type(self.input_changed) is bool, "Invalid K basis original input.")
        guess = self.branch == BRANCH_GUESS
        if guess:
            _require(type(self.risk) is tuple and len(self.risk) == 2 and _integer(self.risk[1], 2, 1 << 480)
                     and _integer(self.risk[0], 1, self.risk[1] - 1), "Invalid K basis risk.")
        else:
            _require(self.risk is None, "Only a guess basis carries a risk.")
        if self.reason == FORCED:
            _require(type(self.pair) is tuple and len(self.pair) == 2
                     and all(_coordinate(cell, 30, 16) for cell in self.pair)
                     and (self.pair[0][1], self.pair[0][0]) < (self.pair[1][1], self.pair[1][0]),
                     "Invalid K basis pair.")
        else:
            _require(self.pair is None, "Only a forced pair basis carries a pair.")
        for text in (self.short, self.head_proposed, self.head_executed):
            _require(_line(text), "Invalid K basis line.")
        _require(" | " not in self.short and len(self.short) <= 160, "Invalid K basis short line.")
        _require(_line(self.head_blocked) if guess else self.head_blocked is None,
                 "Only a guess basis has a blocked wording.")
        for lines in (self.body, self.pseudo, self.linked, self.loss):
            _require(type(lines) is tuple and len(lines) <= MAX_LINES and all(_line(text) for text in lines),
                     "Invalid K basis lines.")
        _require(1 <= len(self.body) and 1 <= len(self.loss) <= 6, "A K basis needs its reason and its loss lines.")
        pseudo = guess and self.diagnosis in (DIAGNOSIS_PSEUDO, DIAGNOSIS_PSEUDO_LINKED)
        linked = guess and self.diagnosis == DIAGNOSIS_PSEUDO_LINKED
        _require(bool(self.pseudo) == pseudo and bool(self.linked) == linked,
                 "Diagnosis lines contradict the diagnosis configuration.")
        _require(type(self.calls) is tuple and len(self.calls) == 3
                 and all(_integer(count, 0, limit) for count, limit in zip(self.calls, CALL_LIMITS))
                 and (guess or self.calls == (0, 0, 0)) and (pseudo or self.calls[1] == 0)
                 and (linked or self.calls[2] == 0), "Invalid K basis call counts.")
        _require(type(self.stage_ns) is tuple and len(self.stage_ns) == 4
                 and all(_integer(value) for value in self.stage_ns), "Invalid K basis stage timings.")


def _line(text):
    return (type(text) is str and 0 < len(text) <= MAX_LINE and "\n" not in text and "\r" not in text)


def _plain(basis):
    """Every field but the digest, as JSON values."""
    data = {field.name: getattr(basis, field.name) for field in fields(basis) if field.name != "binding_sha256"}
    for name in ("original", "risk", "calls", "stage_ns", "body", "pseudo", "linked", "loss"):
        data[name] = None if data[name] is None else list(data[name])
    data["pair"] = None if data["pair"] is None else [list(cell) for cell in data["pair"]]
    return data


def basis_digest(proposal, basis):
    """The binding of one basis record to one finished proposal. Content binding only."""
    _require(type(proposal) is k.KProposal and type(basis) is KProposalBasis, "K basis binding values.")
    s = proposal.snapshot
    bound = {
        "basis_format": BASIS_FORMAT, "run_id": s.run_id, "game_id": s.game_id,
        "board_generation": s.board_generation, "input_seq": s.input_seq, "input_revision": s.input_revision,
        "policy_id": s.policy_id, "definition": s.definition, "token": proposal.token,
        "action": proposal.action, "x": proposal.x, "y": proposal.y, "kind": proposal.kind,
        "category": proposal.category, "continuation": proposal.continuation,
        "observation": [list(row) for row in s.observation], "basis": _plain(basis),
    }
    encoded = json.dumps(bound, ensure_ascii=True, allow_nan=False, sort_keys=True,
                         separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def validate_basis(proposal, basis, diagnosis):
    """Bind a basis record to the one proposal it was written for. Format, presence and binding only."""
    _require(type(proposal) is k.KProposal and type(basis) is KProposalBasis, "Invalid K basis values.")
    _require(basis_required(proposal), "This K proposal must not carry a basis.")
    basis.__post_init__()
    s = proposal.snapshot
    target, actual = (proposal.x, proposal.y), (proposal.action, proposal.x, proposal.y)
    _require(basis.token == proposal.token, "K basis token differs from its proposal.")
    _require(type(diagnosis) is str and diagnosis in DIAGNOSES and basis.diagnosis == diagnosis,
             "K basis diagnosis differs from the configuration of this run.")
    _require((basis.branch == BRANCH_GUESS) == proposal.is_guess, "K basis branch differs from the proposal kind.")
    _require(_coordinate(basis.original[1:], s.width, s.height)
             and basis.input_changed == (actual != basis.original),
             "K basis original input contradicts the actual input.")
    if proposal.is_guess:
        exact = proposal.probabilities
        counts = {(x, y): count for x, y, count in exact.cells}
        category = {FORCED: "FORCED_5050_GUESS" if basis.input_changed else "EXACT_MINIMUM_RISK_GUESS",
                    TIE: "TIE_LOOKAHEAD_GUESS", KEPT: "EXACT_MINIMUM_RISK_GUESS"}[basis.reason]
        _require(proposal.category == category
                 and basis.original == ("OPEN", *exact.minimum_risk_cells[0])
                 and basis.input_changed == (basis.reason == TIE or (basis.reason == FORCED and target != basis.original[1:]))
                 and (basis.reason != KEPT or not basis.input_changed),
                 "K basis reason contradicts the proposal category or the original target.")
        # The shown risk is the exact value of the ACTUAL target, never the original target's minimum.
        _require(basis.risk == (counts.get(target), exact.total_worlds),
                 "K basis risk is not the exact value of the actual target.")
        if basis.reason == FORCED:
            _require(target in basis.pair and all(2 * counts.get(cell, 0) == exact.total_worlds for cell in basis.pair),
                     "K basis pair is not a pair of two half-risk cells holding the target.")
        else:
            _require(basis.risk[0] == exact.selected_mine_worlds, "A tie or kept target must have the minimum risk.")
    else:
        opening = basis.reason == OPENING
        _require((proposal.category == "PROVEN_OPENING_OPEN") == opening and basis.input_changed == opening
                 and (not opening or proposal.action == "OPEN"),
                 "K basis reason contradicts the certain proposal.")
    _require(basis.binding_sha256 == basis_digest(proposal, basis),
             "K basis binding differs from the proposal it arrived with.")
    return basis


def basis_to_dict(basis):
    _require(type(basis) is KProposalBasis, "Unknown K basis DTO.")
    basis.__post_init__()
    return {**_plain(basis), "binding_sha256": basis.binding_sha256}


def basis_from_dict(value):
    """Strict wire form: exactly the fields of the record, lists for every sequence."""
    names = [field.name for field in fields(KProposalBasis)]
    _require(type(value) is dict and set(value) == set(names), "Invalid K basis wire fields.")
    data = dict(value)

    def sequence(name, inner=None):
        item = data[name]
        _require(type(item) is list and len(item) <= MAX_LINES, "Invalid K basis wire array.")
        if inner is not None:
            _require(all(type(part) is list and len(part) == inner for part in item), "Invalid K basis wire array.")
            return tuple(tuple(part) for part in item)
        return tuple(item)

    for name in ("original", "calls", "stage_ns", "body", "pseudo", "linked", "loss"):
        data[name] = sequence(name)
    if data["risk"] is not None:
        data["risk"] = sequence("risk")
    if data["pair"] is not None:
        data["pair"] = sequence("pair", 2)
    return KProposalBasis(**data)


def split_payload(payload):
    """(KProposal, has_info, raw_info, has_basis, raw_basis): the 14 proposal keys stay strict."""
    _require(type(payload) is dict, "K PROPOSAL payload must be an object.")
    proposal = k.from_dict({name: value for name, value in payload.items() if name not in ("info", "basis")},
                           k.KProposal)
    return proposal, "info" in payload, payload.get("info"), "basis" in payload, payload.get("basis")


def receive_basis(proposal, has_basis, raw_basis, diagnosis):
    """Parent-side presence rule and strict check. Returns KProposalBasis or None.

    A required basis that is absent, or a basis where none may exist, is an integrity error and never a
    silent omission."""
    required = basis_required(proposal)
    if required and not has_basis:
        raise basis_error("MISSING", "K_D23 decision proposal arrived without its basis.")
    if has_basis and not required:
        raise basis_error("UNEXPECTED", "A basis arrived on a proposal that must not carry one.")
    if not has_basis:
        return None
    try:
        return validate_basis(proposal, basis_from_dict(raw_basis), diagnosis)
    except Exception as exc:
        raise basis_error("RECEIVED_INVALID", f"{type(exc).__name__}: {exc}") from exc


# ---- lines the parent shows ---------------------------------------------------------------------------

def detail_lines(basis, state):
    """The folded detail of one basis: the selection first, each diagnosis under its own title.

    ``state`` is PROPOSED for a pending proposal, BLOCKED for a guess held back by guess OFF and EXECUTED
    only after the input really reached the Engine. A diagnosis that the configuration does not compute
    is written as not computed, never as a result."""
    _require(type(basis) is KProposalBasis and state in (PROPOSED, BLOCKED, EXECUTED), "Invalid K detail request.")
    _require(state != BLOCKED or basis.head_blocked is not None, "A certain input is never a blocked proposal.")
    head = {PROPOSED: basis.head_proposed, BLOCKED: basis.head_blocked, EXECUTED: basis.head_executed}[state]
    lines = [SELECTION_TITLE, head, *basis.body]
    if basis.branch == BRANCH_GUESS:
        lines += [PSEUDO_TITLE, *(basis.pseudo or (NOT_COMPUTED,))]
        lines += [LINKED_TITLE, *(basis.linked or (NOT_COMPUTED,))]
    return tuple(lines)


def end_lines(status, last_input, basis):
    """The basic note under the unchanged base result. ``last_input`` says what the last ACTUAL input was:
    a K_D23 decision input (with the basis bound to it), the K_D23 initial input, or anything else."""
    _require(type(status) is str and status in ("PLAYING", "WON", "LOST")
             and last_input in (LAST_K_DECISION, LAST_K_INITIAL, LAST_UNKNOWN), "Invalid K end request.")
    if status != "LOST":
        return ()
    if last_input == LAST_K_DECISION and type(basis) is KProposalBasis:
        return basis.loss
    if last_input == LAST_K_INITIAL:
        return (LOSS_INITIAL, LOSS_BASE)
    return (LOSS_NOT_RECORDED, LOSS_BASE)
