"""Korean display text for ONE already validated decision of the experimental composition S3D23-A (FT),
for its two separate diagnoses and for the basic note of a loss. Text only.

What comes in was decided, judged and validated elsewhere: a combined selection record (or the guess record
of declared premises), a pseudo 50/50 diagnosis, a linked diagnosis, a stored guess evidence, a guess outcome
record. This module reads those records and writes sentences. It

  * selects nothing, judges no pair, computes no probability and makes no K decision;
  * calls no validator, no kernel and no Engine, and imports the accepted modules for their types and
    constants only (no function of them is called here);
  * keeps the reason of the actual selection apart from the diagnoses: a diagnosis is never given as the
    reason of an input, a proven pair of other cells is never given as a proof for the actual target;
  * names the risk of the ACTUAL target as the risk of the input and the risk of the K-LC1 target as that of
    the original proposal only;
  * writes S_c and S_v as values of a bounded look-ahead, a pseudo bound as a lower bound, and a linked
    result as the share of one input; none of them as a win rate;
  * writes "not examined", "out of range" and "undetermined" as what they are, never as "no link", "not
    resolved" or "no pseudo 50/50";
  * explains a loss only from the pre-input evidence of the last actual input of a LOST record, with the
    classification the record already carries. A blocked proposal is neither an input nor a cause.

``GuessFacts`` is display material in memory. It is no storage format and no transport protocol. The checks
here are cheap structural ones (exact types, the diagnosis belongs to this decision); they replace no
accepted validator. Experimental copy only.
"""

from dataclasses import dataclass
from fractions import Fraction

from experiments import program_d2_opening_policy as opening_policy
from experiments import program_d3_guess_record as guess_record
from experiments import program_d3_link_diagnosis as link_diagnosis
from experiments import program_d3_lookahead_policy as lookahead
from experiments import program_d3_pseudo_diagnosis as mirror
from experiments.program_d23_policy import BRANCH_CERTAIN, BRANCH_GUESS, CombinedSelection


EXPLANATION_SCOPE = "D3_LIVE_EXPLANATION_V1"
DISPLAY_LIMIT = 9999  # a fraction or a world count with a larger term is written as a percentage only
# The state the first line is worded for: a pending proposal, a guess proposal held back by guess OFF, an
# input that really reached the Engine.
PROPOSED, BLOCKED, EXECUTED = "PROPOSED", "BLOCKED", "EXECUTED"
STATES = (PROPOSED, BLOCKED, EXECUTED)
TYPE, BINDING, MATERIAL = "EXPLANATION_TYPE", "EXPLANATION_BINDING", "EXPLANATION_MATERIAL"
KIND_OF_REASON = {lookahead.FORCED_FIRST: "FORCED_5050", lookahead.TIE_LOOKAHEAD: "TIE_LOOKAHEAD",
                  lookahead.KEPT: "MIN_RISK"}
S_NOTE = "S_c와 S_v는 한 입력 뒤까지만 본 제한된 전방 계산값이다. 판 전체 승률이 아니다."
OPENING_REASONS = {
    "NO_PROVEN_OPENING": "선택 이유: 0이 증명된 칸이 없어 원 제안을 유지했다.",
    "NO_ELIGIBLE_OPENING": "선택 이유: 0이 증명된 칸은 있지만 바꿀 조건을 만족하지 않아 원 제안을 유지했다."}
SEARCH_TEXT = {mirror.SEARCH_NONE: "후보 쌍이 없다.", mirror.SEARCH_COMPLETE: "지원 범위의 후보를 모두 판정했다.",
               mirror.SEARCH_PARTIAL: "한도 때문에 일부만 판정했다."}
FORCED_TEXT = {mirror.FORCED_SAME: "이 진단도 같은 쌍을 증명했다.",
               mirror.FORCED_OUT_OF_RANGE: "거리 {far} 이상이라 이 진단의 범위 밖이다. 검사하지 않았다.",
               mirror.FORCED_NOT_EXAMINED: "범위 안이지만 호출 한도 때문에 검사하지 않았다."}
PLAN_TEXT = {
    link_diagnosis.NO_OTHER_BUNDLE: "검사: 실제 대상이 속하지 않은 묶음이 없어 계산한 것이 없다. 연결 없음의 판정이 아니다.",
    link_diagnosis.NO_LISTED_PAIR: "검사: 나열된 쌍이 없어 계산한 것이 없다. 연결 없음의 판정이 아니다."}
TARGET_TEXT = {
    link_diagnosis.LINKED_ALL: "실제 대상: 이 칸을 열고 살아남으면, 이 칸이 속하지 않은 어떤 묶음이 모든 생존 결과에서 풀린다. "
                               "모든 다른 묶음이 풀린다는 뜻은 아니다.",
    link_diagnosis.LINKED_SOME: "실제 대상: 이 칸을 열고 살아남으면, 이 칸이 속하지 않은 어떤 묶음이 일부 생존 결과에서 풀린다.",
    link_diagnosis.UNDETERMINED: "실제 대상: 풀린 결과가 없고, 숫자 0이 나오는 결과는 주변이 함께 열리기 때문에 이 계산으로 "
                                 "판단하지 않았다(판단 보류).",
    link_diagnosis.NOT_OBSERVED: "실제 대상: 검사한 결과에서는 다른 묶음이 풀리지 않았다. 독립이라는 증명은 아니다.",
    link_diagnosis.NOT_APPLICABLE: "실제 대상: 기준 칸으로 계산하지 않았다."}
LABEL_TEXT = {
    link_diagnosis.RESOLVED_ALL: "모든 생존 결과에서 풀린다",
    link_diagnosis.RESOLVED_SOME: "일부 생존 결과에서만 풀린다",
    link_diagnosis.RESOLVED_SOME_FLOOD_OPEN: "일부 생존 결과에서 풀리고, 숫자 0의 결과는 판단 보류다",
    link_diagnosis.NOT_RESOLVED_EXAMINED: "검사한 모든 생존 결과에서 풀리지 않는다",
    link_diagnosis.UNDETERMINED_FLOOD: "풀린 결과가 없고, 숫자 0의 결과는 판단 보류다"}
ROLE_TEXT = {link_diagnosis.ROLE_ORIGINAL: "원 대상", link_diagnosis.ROLE_CROSS: "다른 묶음으로의 연결 칸"}
OUT_TEXT = {link_diagnosis.OUT_IN_BUNDLE: "같은 묶음 안의 연결뿐", link_diagnosis.OUT_NON_PAIR: "쌍에 속하지 않은 구분 칸"}
OTHER_HEAD = "다른 기준 칸의 결과(그 칸을 열었을 때의 진단이며 실제 대상의 결과가 아니다):"
LINKED_CLOSE = "이 진단은 이 한 입력 뒤의 범위다. 여러 입력 뒤의 보장이나 판 전체 승률이 아니다."
LOSS_HEAD = {
    guess_record.MIN_RISK: "패배 보조 설명: 당시 계산된 최소 위험 칸을 선택한 추측에서 패배했다.",
    guess_record.TIE_LOOKAHEAD: "패배 보조 설명: 당시 최소 위험이 같은 칸들 가운데 제한된 전방 계산으로 고른 추측에서 패배했다.",
    guess_record.FORCED_5050: "패배 보조 설명: 증명된 불가피한 50/50 쌍을 먼저 처리한 추측에서 패배했다."}
LOSS_FORCED_NOTE = "쌍의 어느 칸을 열어도 위험이 1/2이었다는 뜻이며, 판 전체의 패배가 정해져 있었다는 뜻이 아니다."
LOSS_CLOSE = "입력 전에 확인한 범위의 설명이다. 패배 뒤 공개된 지뢰로 다시 판정한 것이 아니며, 기본 결과 LOST는 그대로다."
LOSS_INITIAL = "패배 보조 설명: 첫 입력에서 패배했다. 첫 입력에는 입력 전 근거가 없어 유형을 확인할 수 없다."
LOSS_NOT_RECORDED = "패배 보조 설명: 마지막 입력의 입력 전 근거가 없어 패배 유형을 확인할 수 없다."
LOSS_INTEGRITY = "패배 보조 설명: 추측이 아닌 입력에서 LOST가 기록됐다. 추측 패배로 설명하지 않으며 확인이 필요한 기록이다."
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


class ExplanationError(ValueError):
    """Material that is not what the contract names. Never turned into a milder sentence."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class GuessFacts:
    """What the text of one guess decision needs, copied from its pre-input evidence. Memory only."""

    reason: str
    kind: str
    target: tuple
    risk: Fraction
    original_target: tuple
    original_risk: Fraction
    is_minimum_risk: bool
    target_changed: bool
    pair: tuple | None
    lookahead_status: str
    lookahead_cells: int
    lookahead_calls: int
    target_s_c: Fraction | None
    original_s_v: Fraction | None


@dataclass(frozen=True)
class DecisionExplanation:
    """``short`` is the one status line. ``selection`` is the reason of the actual input; ``pseudo`` and
    ``linked`` are the separate diagnoses (empty when none was given)."""

    short: str
    selection: tuple
    pseudo: tuple
    linked: tuple

    @property
    def detail(self) -> tuple:
        return self.selection + self.pseudo + self.linked


@dataclass(frozen=True)
class LossExplanation:
    """``status`` is the base result, unchanged. ``shown`` says whether ``lines`` is a note of a loss."""

    status: str
    shown: bool
    basis: str | None
    input_index: int | None
    lines: tuple


def _need(condition, code: str, detail: str) -> None:
    if not condition:
        raise ExplanationError(code, detail)


def _is_cell(value) -> bool:
    return type(value) is tuple and len(value) == 2 and type(value[0]) is int and type(value[1]) is int


def _cell(cell) -> str:
    return f"({cell[0]}, {cell[1]})"


def _cells(cells) -> str:
    return ", ".join(_cell(cell) for cell in cells)


def _pair(a, b) -> str:
    return f"{_cell(a)}-{_cell(b)}"


def percent_text(value) -> str:
    """One decimal; a value strictly between 0 and 1 is never written as 0% or 100%."""
    _need(type(value) is Fraction and 0 <= value <= 1, TYPE, "A probability must be a Fraction from 0 to 1.")
    numerator, denominator = value.numerator, value.denominator
    if numerator == 0:
        return "0%"
    if numerator == denominator:
        return "100%"
    if numerator * 1000 < denominator:
        return "<0.1%"
    if numerator * 1000 > 999 * denominator:
        return ">99.9%"
    rounded = (2 * numerator * 1000 + denominator) // (2 * denominator)
    return f"{rounded // 10}.{rounded % 10}%"


def points_text(higher, lower) -> str:
    """The difference of two probabilities, in percentage points."""
    _need(type(higher) is Fraction and type(lower) is Fraction and 0 <= lower <= higher <= 1, TYPE,
          "A difference needs two probabilities, the higher one first.")
    return percent_text(higher - lower) + "p"


def _ratio(value) -> str:
    return f"{value.numerator}/{value.denominator}"


def _value(value) -> str:
    """A look-ahead value or a bound: the reduced fraction too, unless its terms are too long to read."""
    if value.denominator > DISPLAY_LIMIT:
        return percent_text(value)
    return f"{_ratio(value)} ({percent_text(value)})"


def _risk(value) -> str:
    if value.denominator > DISPLAY_LIMIT:
        return percent_text(value)
    return f"{percent_text(value)} ({_ratio(value)})"


# ---- the reason of the actual selection ------------------------------------------------------------------

def _checked(facts: GuessFacts) -> GuessFacts:
    _need(type(facts.reason) is str and facts.reason in KIND_OF_REASON
          and facts.kind == KIND_OF_REASON[facts.reason], MATERIAL, "Unknown selection reason or kind.")
    _need(_is_cell(facts.target) and _is_cell(facts.original_target)
          and type(facts.risk) is Fraction and type(facts.original_risk) is Fraction
          and 0 < facts.original_risk <= facts.risk < 1, MATERIAL, "Targets or risks are not those of a guess.")
    _need(type(facts.target_changed) is bool and type(facts.is_minimum_risk) is bool
          and facts.target_changed == (facts.target != facts.original_target)
          and facts.is_minimum_risk == (facts.risk == facts.original_risk), MATERIAL,
          "The marks of the target disagree with the targets and risks.")
    forced = facts.reason == lookahead.FORCED_FIRST
    if forced:
        _need(type(facts.pair) is tuple and len(facts.pair) == 2 and all(_is_cell(cell) for cell in facts.pair)
              and facts.target in facts.pair, MATERIAL, "A forced pair must hold the actual target.")
    else:
        _need(facts.pair is None and facts.is_minimum_risk, MATERIAL,
              "Only a forced pair has a pair and may exceed the minimum risk.")
    _need(type(facts.lookahead_cells) is int and type(facts.lookahead_calls) is int
          and facts.lookahead_status in (lookahead.STATUS_COMPUTED, lookahead.STATUS_SINGLE, lookahead.STATUS_LIMIT),
          MATERIAL, "Unknown look-ahead status.")
    for value in (facts.target_s_c, facts.original_s_v):
        _need(value is None or type(value) is Fraction, MATERIAL, "A look-ahead value must be a Fraction.")
    if facts.lookahead_status == lookahead.STATUS_COMPUTED:
        _need(facts.target_s_c is not None and (forced or facts.original_s_v is not None), MATERIAL,
              "A computed look-ahead needs its values.")
    else:
        _need(facts.reason != lookahead.TIE_LOOKAHEAD, MATERIAL, "A tie selection needs a computed look-ahead.")
    return facts


def facts_of_selection(selection) -> GuessFacts:
    """Display facts of the guess decision behind one stage-2 selection record."""
    _need(type(selection) is lookahead.LookaheadSelection, TYPE, "Expected a stage-2 selection record.")
    evidence = selection.evidence
    _need(type(evidence) is lookahead.LookaheadEvidence and type(selection.lookahead_cells) is tuple, MATERIAL,
          "The selection record is not that of a guess decision.")
    return _checked(GuessFacts(
        selection.selection_reason, evidence.kind, evidence.target, evidence.risk, evidence.original_target,
        evidence.original_risk, evidence.is_minimum_risk, selection.target_changed, evidence.pair,
        evidence.lookahead_status, len(selection.lookahead_cells), selection.actual_calls, evidence.target_s_c,
        evidence.original_s_v))


def facts_of_evidence(evidence) -> GuessFacts:
    """Display facts of one stored pre-input evidence."""
    _need(type(evidence) is guess_record.GuessEvidence and type(evidence.lookahead_cells) is tuple, TYPE,
          "Expected the stored evidence of a guess input.")
    return _checked(GuessFacts(
        evidence.selection_reason, evidence.kind, evidence.target, evidence.risk, evidence.original_target,
        evidence.original_risk, evidence.is_minimum_risk, evidence.target_changed, evidence.pair,
        evidence.lookahead_status, len(evidence.lookahead_cells), evidence.actual_calls, evidence.target_s_c,
        evidence.original_s_v))


def _short(facts: GuessFacts) -> str:
    risk = percent_text(facts.risk)
    if facts.reason == lookahead.FORCED_FIRST:
        if facts.is_minimum_risk:
            return f"불가피한 50/50 먼저 처리 · 이 칸의 지뢰 확률 {risk}"
        return (f"불가피한 50/50 먼저 처리 · 이 칸의 지뢰 확률 {risk} (현재 최소 {percent_text(facts.original_risk)}보다 "
                f"{points_text(facts.risk, facts.original_risk)} 높음)")
    if facts.reason == lookahead.TIE_LOOKAHEAD:
        return f"최소 위험 동률 중 전방 비교로 선택 · 이 칸의 지뢰 확률 {risk}"
    return f"최소 위험 칸 유지 · 이 칸의 지뢰 확률 {risk}"


def _state(executed, state) -> str:
    """The wording state. ``state``, when given, says it directly; otherwise the older ``executed`` flag."""
    _need(type(executed) is bool, TYPE, "Expected a boolean for an executed input.")
    if state is None:
        return EXECUTED if executed else BLOCKED
    _need(type(state) is str and state in STATES, TYPE, "Unknown wording state.")
    return state


def _guess_lines(facts: GuessFacts, state: str) -> tuple:
    forced, tie = facts.reason == lookahead.FORCED_FIRST, facts.reason == lookahead.TIE_LOOKAHEAD
    if state == EXECUTED:
        lines = [f"실제 입력 대상: OPEN {_cell(facts.target)}. 이 입력의 지뢰 확률 {_risk(facts.risk)}."]
    elif state == PROPOSED:
        # A pending proposal: nothing was sent yet and nothing is said about the guess permission.
        lines = [f"제안 대상: OPEN {_cell(facts.target)}. 이 칸의 지뢰 확률 {_risk(facts.risk)}."]
    else:
        lines = [f"제안 대상: OPEN {_cell(facts.target)}. 이 칸의 지뢰 확률 {_risk(facts.risk)}. "
                 "추측 허용이 꺼져 있어 입력하지 않았다. 실제 입력이 아니다."]
    if not facts.target_changed:
        lines.append("원 제안(K-LC1)과 같은 칸이다.")
    else:
        tail = "위험은 같다." if facts.risk == facts.original_risk else "원 제안의 위험이며 이 칸의 위험이 아니다."
        lines.append(f"원 제안(K-LC1): {_cell(facts.original_target)}, 지뢰 확률 {_risk(facts.original_risk)}. {tail}")
    if forced:
        lines.append(f"선택 이유: 증명된 불가피한 50/50 쌍을 먼저 처리한다. 쌍: {_pair(*facts.pair)}. 두 칸 중 정확히 하나가 "
                     "지뢰이고, 한쪽에만 닿는 주변 칸이 없거나 모두 확정 지뢰라는 조건이 증명된 쌍이다.")
        if not facts.is_minimum_risk:
            lines.append(f"이 칸의 지뢰 확률은 현재 최소 위험 {percent_text(facts.original_risk)}보다 "
                         f"{points_text(facts.risk, facts.original_risk)} 높다.")
    elif tie:
        lines.append(f"선택 이유: 최소 위험이 같은 칸 {facts.lookahead_cells}개를 제한된 전방 계산으로 비교해 골랐다. "
                     f"이 칸의 S_c {_value(facts.target_s_c)}가 원 제안의 S_v {_value(facts.original_s_v)}보다 크다.")
    else:
        lines.append("선택 이유: 계산된 최소 위험 칸(원 제안)을 유지했다.")
    if facts.lookahead_status == lookahead.STATUS_COMPUTED:
        line = (f"전방 계산: 후보 {facts.lookahead_cells}칸, 가정 계산 {facts.lookahead_calls}회"
                f"(한도 {lookahead.CALL_LIMIT}회).")
        if forced:
            line += f" 쌍의 칸은 S_c, 입력 비용, 읽기 순서로 순위를 정했다. 이 칸의 S_c {_value(facts.target_s_c)}."
        elif not tie:
            line += f" 원 제안의 S_v {_value(facts.original_s_v)}보다 큰 S_c를 가진 동률 칸이 없었다."
        lines += [line, S_NOTE]
    elif facts.lookahead_status == lookahead.STATUS_SINGLE:
        lines.append("전방 계산: 후보가 한 칸이라 계산하지 않았다.")
    else:
        line = (f"전방 계산: 후보가 {facts.lookahead_cells}칸으로 한도 {lookahead.CELL_LIMIT}칸을 넘어 계산하지 않았다. "
                "계산하지 않은 것이며 비교 결과가 아니다.")
        if forced:
            line += " 쌍의 칸은 입력 비용과 읽기 순서로 순위를 정했다."
        lines.append(line)
    return tuple(lines)


def _move_text(move) -> str:
    return f"{move.action.name} {_cell((move.x, move.y))}"


def _certain(opening, state=EXECUTED) -> tuple:
    """(short, lines) of a certain decision: an applied proven opening or the kept K-LC1 input."""
    _need(type(opening) is opening_policy.OpeningSelection, TYPE, "Expected the opening record of a certain decision.")
    move, kept = opening.move, opening.inner.selected.move
    _need(state != BLOCKED, MATERIAL, "A certain input is never a blocked proposal.")
    actual = (f"실제 입력: {_move_text(move)}. 추측이 아닌 확정 입력이다." if state == EXECUTED
              else f"제안 입력: {_move_text(move)}. 추측이 아닌 확정 입력이다.")
    if opening.applied is not None:
        _need(opening.reason == "PROVEN_OPENING_OVERRIDE" and move.action.name == "OPEN", MATERIAL,
              "An applied opening must be a direct OPEN with its own reason.")
        count = opening.applied.region.guaranteed_count
        _need(type(count) is int and count >= 1, MATERIAL, "An applied opening needs its guaranteed count.")
        return f"0이 증명된 칸 먼저 열기 · 최소 {count}칸 공개", (
            actual, f"원 제안(K-LC1): {_move_text(kept)}.",
            f"선택 이유: 이 칸은 0을 보인다는 것이 증명됐다. 열면 주변이 함께 열려 최소 {count}칸이 공개된다. "
            "원 제안이 여는 칸을 모두 포함하고 칸당 입력 비용이 더 낮을 때만 이렇게 바꾼다.")
    _need(opening.reason in OPENING_REASONS and move == kept, MATERIAL,
          "A kept certain input must be the K-LC1 input with a known reason.")
    return "확정 입력 · K-LC1 선택 유지", (actual, "원 제안(K-LC1)과 같은 입력이다.", OPENING_REASONS[opening.reason])


# ---- the two separate diagnoses -------------------------------------------------------------------------

def explain_pseudo(diagnosis) -> tuple:
    """Lines of one pseudo 50/50 diagnosis. A diagnosis is never a selection reason."""
    _need(type(diagnosis) is mirror.PseudoDiagnosis, TYPE, "Expected a pseudo diagnosis.")
    _need(diagnosis.scope == mirror.DIAGNOSIS_SCOPE and type(diagnosis.limits) is tuple
          and len(diagnosis.limits) == 3 and _is_cell(diagnosis.actual_target), MATERIAL,
          "Unknown scope or limits of the pseudo diagnosis.")
    distance, _, call_limit = diagnosis.limits
    target = diagnosis.actual_target
    rows = [row for row in diagnosis.cells if row.cell == target]
    _need(len(rows) == 1 and rows[0].status == diagnosis.target_status, MATERIAL,
          "The status of the actual target is not that of its own row.")
    row, status = rows[0], diagnosis.target_status
    _need((status == mirror.CELL_PROVEN) == (diagnosis.target_bound is not None), MATERIAL,
          "Only a proven target carries a bound.")
    lines = [f"pseudo 50/50 진단(별도 진단, 선택에 쓰지 않음): 실제 대상 {_cell(target)}."]
    if status == mirror.CELL_PROVEN:
        partners = []
        for partner in row.partners:
            checks = [check for check in diagnosis.checks if {check.a, check.b} == {target, partner}
                      and check.verdict == mirror.MIRROR_PROVEN]
            _need(len(checks) == 1, MATERIAL, "A proven partner has no proven check of its own.")
            partners.append(f"{_cell(partner)} {'고립형' if checks[0].isolated else '조건형'}")
        _need(bool(partners), MATERIAL, "A proven target needs a partner.")
        lines.append(f"결과: 증명된 거울 쌍의 칸이다. 짝: {', '.join(partners)}.")
        lines.append(f"판 전체에서 이기지 못할 확률의 하한: {_value(Fraction(*diagnosis.target_bound))}. 하한일 뿐이며 "
                     "승률이나 최적 선택의 증명이 아니다. 이 입력 한 번의 지뢰 확률과 수는 같지만 뜻이 다르다.")
    elif status == mirror.CELL_REFUTED:
        lines.append(f"결과: 지원 범위(거리 {distance} 이하의 쌍)에서 실제 대상의 쌍 {row.pairs_in_range}개가 모두 조건을 "
                     "만족하지 않았다. 지원하지 않는 구조에 대한 판정이 아니며 하한은 없다.")
    elif status == mirror.CELL_NO_PAIR:
        lines.append(f"결과: 실제 대상에는 지원 범위(거리 {distance} 이하) 안의 쌍이 없어 검사한 것이 없다. "
                     "조건 불충족이 아니며 하한은 없다.")
    else:
        _need(status == mirror.CELL_UNDECIDED, MATERIAL, "Unknown status of the actual target.")
        lines.append(f"결과: 실제 대상의 후보 쌍 {row.not_examined_pairs}개를 호출 한도 때문에 검사하지 못했다. "
                     "조건 불충족이 아니며 하한은 없다.")
    counts = diagnosis.counts
    _need(diagnosis.search_status in SEARCH_TEXT, MATERIAL, "Unknown search status.")
    lines.append(f"탐색: 범위 안의 쌍 {counts.in_range}개, 후보 {counts.candidate}개, 판정 {counts.decided}개, "
                 f"한도 미검사 {counts.not_examined}개. 조건부 계산 {diagnosis.actual_calls}회(한도 {call_limit}회). "
                 f"{SEARCH_TEXT[diagnosis.search_status]}")
    if counts.not_examined:
        lines.append(f"한도 미검사: 후보 쌍 {counts.not_examined}개는 검사하지 못했다. 조건 불충족이 아니다.")
    if row.floating_cells_out_of_range:
        lines.append(f"범위 밖: 실제 대상에서 거리 {distance + 1} 이상인 떠 있는 칸 {row.floating_cells_out_of_range}개와의 "
                     "관계는 지원하지 않아 검사하지 않았다.")
    others = [check for check in diagnosis.checks
              if check.verdict == mirror.MIRROR_PROVEN and target not in (check.a, check.b)]
    if others:
        shown = ", ".join(_pair(check.a, check.b) for check in others[:4])
        more = f" 외 {len(others) - 4}개" if len(others) > 4 else ""
        lines.append(f"다른 칸의 증명된 쌍 {len(others)}개: {shown}{more}. 실제 대상에 대한 증명이 아니다.")
    for a, b, relation in diagnosis.forced_pairs:
        _need(relation in FORCED_TEXT, MATERIAL, "Unknown relation of a forced pair.")
        lines.append(f"불가피한 50/50 쌍 {_pair(a, b)}: {FORCED_TEXT[relation].format(far=distance + 1)}")
    return tuple(lines)


def _bundle_row(plan, row) -> str:
    _need(row.label in LABEL_TEXT and type(row.bundle) is int and 0 <= row.bundle < len(plan.bundles), MATERIAL,
          "Unknown summary label or bundle of a linked result.")
    head = f"묶음 {_cells(plan.bundles[row.bundle].cells)}: {LABEL_TEXT[row.label]}."
    counts = (row.resolved_worlds, row.unresolved_worlds, row.flood_undetermined_worlds)
    survival = row.survival_worlds
    _need(type(survival) is int and all(type(count) is int and 0 <= count <= survival for count in counts), MATERIAL,
          "The world counts of a linked result are not counts of its surviving worlds.")
    if survival <= DISPLAY_LIMIT:
        return (f"{head} 살아남는 경우 {survival} 가운데 풀림 {counts[0]}, 풀리지 않음 {counts[1]}, "
                f"판단 보류 {counts[2]}.")
    # The recorded counts of a real board are too long to read: the same three counts as shares of the survivors.
    shares = [percent_text(Fraction(count, survival)) for count in counts]
    return f"{head} 살아남는 경우 가운데 풀림 {shares[0]}, 풀리지 않음 {shares[1]}, 판단 보류 {shares[2]}."


def explain_linked(diagnosis) -> tuple:
    """Lines of one linked diagnosis: the share of ONE input, kept apart from sharing and geometry."""
    _need(type(diagnosis) is link_diagnosis.LinkDiagnosis, TYPE, "Expected a linked diagnosis.")
    _need(diagnosis.scope == link_diagnosis.DIAGNOSIS_SCOPE and type(diagnosis.limits) is tuple
          and len(diagnosis.limits) == 2 and _is_cell(diagnosis.actual_target)
          and type(diagnosis.plan) is link_diagnosis.LinkPlan, MATERIAL,
          "Unknown scope, limits or plan of the linked diagnosis.")
    anchor_limit, call_limit = diagnosis.limits
    plan, target = diagnosis.plan, diagnosis.actual_target
    cross = sum(1 for relation in plan.links if not relation.same_bundle)
    lines = [f"linked 풀림 진단(별도 진단, 선택에 쓰지 않음): 실제 대상 {_cell(target)}. 이 칸을 여는 한 입력의 범위다.",
             f"구조: 나열된 쌍 {len(plan.pairs)}개, 공유 묶음 {len(plan.bundles)}개, 칸 공유 {len(plan.shares)}건, "
             f"기하적 연결 {len(plan.links)}건(다른 묶음 사이 {cross}건). 칸 공유와 기하적 연결은 풀림이 아니다."]
    if plan.status == link_diagnosis.PLANNED:
        lines.append(f"검사: 기준 칸 {len(plan.anchors)}개, 정밀 계산 {diagnosis.actual_calls}회(한도 {call_limit}회).")
    else:
        _need(plan.status in PLAN_TEXT and not diagnosis.results, MATERIAL, "Unknown plan status of the linked diagnosis.")
        lines.append(PLAN_TEXT[plan.status])
    _need(diagnosis.target_label in TARGET_TEXT, MATERIAL, "Unknown label of the actual target.")
    lines.append(TARGET_TEXT[diagnosis.target_label])
    lines += [_bundle_row(plan, row) for row in diagnosis.results if row.anchor == target]
    others = [row for row in diagnosis.results if row.anchor != target]
    if others:
        roles = {anchor.cell: anchor.role for anchor in plan.anchors}
        lines.append(OTHER_HEAD)
        for row in others:
            _need(roles.get(row.anchor) in ROLE_TEXT, MATERIAL, "A linked result names no planned anchor of another cell.")
            lines.append(f"기준 칸 {_cell(row.anchor)} [{ROLE_TEXT[roles[row.anchor]]}] · {_bundle_row(plan, row)}")
    if plan.not_examined_limit:
        lines.append(f"한도 미검사: 기준 칸 한도({anchor_limit}개) 때문에 검사하지 않은 연결 칸 "
                     f"{_cells(plan.not_examined_limit)}. 연결 없음이 아니다.")
    _need(all(reason in OUT_TEXT for _, reason in plan.out_of_scope), MATERIAL, "Unknown out-of-scope reason.")
    for reason, text in OUT_TEXT.items():
        cells = tuple(cell for cell, why in plan.out_of_scope if why == reason)
        if cells:
            lines.append(f"범위 밖({text}): {_cells(cells)}. 기준 칸으로 지원하지 않아 검사하지 않았다. "
                         "연결 없음이나 풀리지 않음의 판정이 아니다.")
    lines.append(LINKED_CLOSE)
    return tuple(lines)


def _bound(diagnosis, selection, expected_type, reason) -> None:
    """The diagnosis was made from the premises of THIS selection, for its target and its reason."""
    _need(type(diagnosis) is expected_type, TYPE, "The diagnosis is not of the expected kind.")
    _need(diagnosis.premises is selection.premises and diagnosis.actual_target == selection.target
          and reason == selection.selection_reason, BINDING,
          "The diagnosis does not belong to this decision.")


# ---- one decision ---------------------------------------------------------------------------------------

def explain_decision(choice, *, pseudo=None, linked=None, executed=True, state=None) -> DecisionExplanation:
    """Text of one decision. ``choice`` is the combined record of an FT decision or the stage-2 record of a
    guess decision. A diagnosis is added only as its own, separate lines; it never changes the reason.
    ``state`` (PROPOSED, BLOCKED or EXECUTED) words the first line; without it ``executed`` decides as before."""
    state = _state(executed, state)
    if type(choice) is CombinedSelection:
        if choice.branch == BRANCH_CERTAIN:
            _need(pseudo is None and linked is None, BINDING, "A certain decision has no diagnosis.")
            short, lines = _certain(choice.opening, state)
            return DecisionExplanation(short, lines, (), ())
        _need(choice.branch == BRANCH_GUESS and type(choice.guess) is lookahead.LookaheadSelection
              and choice.move == choice.guess.move, MATERIAL, "The combined record is not that of a guess decision.")
        selection = choice.guess
    else:
        _need(type(choice) is lookahead.LookaheadSelection, TYPE, "Expected a combined or a stage-2 selection record.")
        selection = choice
    facts = facts_of_selection(selection)
    pseudo_lines = linked_lines = ()
    if pseudo is not None:
        _bound(pseudo, selection, mirror.PseudoDiagnosis, getattr(pseudo, "actual_selection_reason", None))
        pseudo_lines = explain_pseudo(pseudo)
    if linked is not None:
        _bound(linked, selection, link_diagnosis.LinkDiagnosis, getattr(linked, "selection_reason", None))
        linked_lines = explain_linked(linked)
    return DecisionExplanation(_short(facts), _guess_lines(facts, state), pseudo_lines, linked_lines)


def explain_evidence(evidence, *, executed=True, state=None) -> DecisionExplanation:
    """Text of one stored pre-input evidence. A stored evidence carries no diagnosis."""
    state = _state(executed, state)
    facts = facts_of_evidence(evidence)
    return DecisionExplanation(_short(facts), _guess_lines(facts, state), (), ())


# ---- the basic note of a loss ---------------------------------------------------------------------------

def explain_loss(record) -> LossExplanation:
    """The note of a loss from the classification the record already carries. Nothing is classified here,
    and nothing revealed after the loss is read."""
    _need(type(record) is guess_record.GuessOutcomeRecord and type(record.loss) is guess_record.LossClassification
          and type(record.inputs) is tuple, TYPE, "Expected a guess outcome record with its classification.")
    status, loss = record.final_status, record.loss
    if status != guess_record.LOST:
        expected = {guess_record.WON: guess_record.NOT_APPLICABLE_WON,
                    guess_record.PLAYING: guess_record.NOT_APPLICABLE_NOT_FINISHED}
        _need(status in expected and loss.applicability == expected[status] and loss.input_index is None, MATERIAL,
              "The classification is not that of this base result.")
        lines = ()
        if status == guess_record.PLAYING and record.blocked is not None:
            blocked = record.blocked
            _need(type(blocked) is guess_record.BlockedProposal, TYPE, "Expected a blocked proposal.")
            lines = (f"판이 끝나지 않았다. 입력하지 않은 제안이 있다: {blocked.action} {_cell((blocked.x, blocked.y))}. "
                     "추측 허용이 꺼져 있어 보내지 않았고, 실제 입력도 패배 원인도 아니다.",)
        return LossExplanation(status, False, None, None, lines)
    _need(bool(record.inputs) and type(record.inputs[-1]) is guess_record.RecordedInput, MATERIAL,
          "A loss needs a last actual input.")
    last = record.inputs[-1]
    _need(last.status_after == guess_record.LOST and loss.input_index == last.index, BINDING,
          "The classification does not name the last actual input of this loss.")
    if loss.applicability == guess_record.INTEGRITY_PROBLEM:
        _need(loss.basis == guess_record.BASIS_CERTAIN and last.decision == guess_record.CERTAIN, MATERIAL,
              "An integrity problem is a loss on a certain input.")
        return LossExplanation(status, True, loss.basis, last.index, (LOSS_INTEGRITY, LOSS_BASE))
    _need(loss.applicability == guess_record.APPLIES, MATERIAL, "Unknown applicability of a loss classification.")
    if loss.kind == guess_record.UNCLASSIFIED:
        known = {guess_record.BASIS_INITIAL: (guess_record.INITIAL_OPEN, LOSS_INITIAL),
                 guess_record.BASIS_NOT_RECORDED: (guess_record.EVIDENCE_NOT_RECORDED, LOSS_NOT_RECORDED)}
        _need(loss.basis in known and last.decision == known[loss.basis][0] and last.evidence is None, MATERIAL,
              "An unclassified loss has no pre-input evidence.")
        return LossExplanation(status, True, loss.basis, last.index, (known[loss.basis][1], LOSS_BASE))
    evidence = last.evidence
    _need(loss.basis == guess_record.BASIS_EVIDENCE and last.decision == guess_record.GUESS
          and type(evidence) is guess_record.GuessEvidence and loss.kind in LOSS_HEAD and evidence.kind == loss.kind
          and last.action == "OPEN" and (last.x, last.y) == evidence.target, BINDING,
          "The classified kind is not that of the evidence of the last actual input.")
    return LossExplanation(status, True, loss.basis, last.index, _guess_loss_lines(facts_of_evidence(evidence)))


def _guess_loss_lines(facts: GuessFacts) -> tuple:
    """The note of a loss on one guess input, from what was known BEFORE that input."""
    lines = [f"{LOSS_HEAD[facts.kind]} 입력 OPEN {_cell(facts.target)}, 입력 전 지뢰 확률 {_risk(facts.risk)}."]
    if facts.kind == guess_record.FORCED_5050:
        lines.append(LOSS_FORCED_NOTE)
        if not facts.is_minimum_risk:
            lines.append(f"당시 최소 위험은 원 제안 {_cell(facts.original_target)}의 {_risk(facts.original_risk)}였다.")
    lines.append(LOSS_CLOSE)
    return tuple(lines)


def loss_lines_for(choice) -> tuple:
    """The lines to show IF this very input ends the game as LOST, made from its pre-input record only.

    Whether they are shown is decided later, by the actual result of that input; nothing revealed after a
    loss is read here. A certain input cannot be explained as a guess loss."""
    if type(choice) is CombinedSelection and choice.branch == BRANCH_CERTAIN:
        _need(type(choice.opening) is opening_policy.OpeningSelection, TYPE,
              "Expected the opening record of a certain decision.")
        return (LOSS_INTEGRITY, LOSS_BASE)
    selection = choice.guess if type(choice) is CombinedSelection else choice
    return _guess_loss_lines(facts_of_selection(selection))


def help_lines() -> tuple:
    """The static help text. It depends on no decision."""
    return HELP_LINES
