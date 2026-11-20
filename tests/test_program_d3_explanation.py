"""Display text of FT decisions, of the two separate diagnoses and of the basic loss note.

The expected sentences are NOT written here: they are read from TEST_PLAN.json of this output folder, which
was fixed and sealed before the explanation module and this test module were written.

Kinds of material, kept apart on purpose (none of it is a new board or a game run; no Engine is built):
  * declared premises of the accepted tests (PD.*, RK03 as declared in test_program_d23s_policy): the accepted
    ``decide``, ``diagnose_pseudo``, ``diagnose_premises`` and ``diagnose_links`` are called in the fixture
    step only, never by the explanation module;
  * the hand cases of cases/LINKED_CASES.json through the accepted helper of the linked tests;
  * real K decisions on tiny DECLARED public observations (a fresh KLocalSession analyses the grid; no
    Engine, no M injection): GUESS_8X2 and X02 of the accepted tests;
  * declared arithmetic records of the accepted S3D2-A tests (a certain input that keeps the K-LC1 input);
  * hand-written evidence and records of the accepted record tests;
  * two stored record files of accepted real runs (boards 97 and 8191), read with the accepted reader and
    checked against their size and hash every time;
  * SYNTHETIC objects, named as such: a stored record cut after its third guess with the last input set to
    LOST, a diagnosis whose target is left undecided, a loss on a certain input. They are no observation of
    an accepted run and exist only to reach a wording branch.
Results are functional checks of wording, not evidence about win rate or about Live response time.
"""

import ast
from contextlib import ExitStack
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import core_engine
import simple_probability
from core_engine import GameStatus
from experiments import program_d23_policy as P
from experiments import program_d2_opening_policy as d2
from experiments import program_d3_explanation as X
from experiments import program_d3_forced_pair_policy as stage1
from experiments import program_d3_guess_record as R
from experiments import program_d3_link_diagnosis as L
from experiments import program_d3_lookahead_policy as d3
from experiments import program_d3_pseudo_diagnosis as pseudo
from experiments import program_k_lc1_policy as lc1
from experiments.program_k_capability import KLocalSession
from live_analysis import format_mine_probability
from simple_probability import CellProbability
from stage3_physical import load_timing_table
from tests import test_program_d2_opening as D2T
from tests import test_program_d23_policy as CT
from tests import test_program_d3_guess_record as GR
from tests import test_program_d3_link_diagnosis as LT
from tests import test_program_d3_pseudo_diagnosis as PD


# 제품 저장소 안의 고정 자료 폴더다. 출력 폴더에 있던 자료를 옮겼고 출처와 SHA-256은 그 폴더의 PROVENANCE.json에 있다.
ROOT = Path(__file__).resolve().parent / "fixtures" / "program_d3_explanation"
PLAN = json.loads((ROOT / "TEST_PLAN.json").read_text(encoding="utf-8"))
E, T, RULES = PLAN["expected"], PLAN["templates"], PLAN["wording_rules"]
BINDING = json.loads((ROOT / "FIXTURE_BINDING.json").read_text(encoding="utf-8"))
# Supplement 1 (display of long numbers): expectations written before the module was changed.
S1 = json.loads((ROOT / "SUPPLEMENT_1.json").read_text(encoding="utf-8"))["expected"]
PLAYING = GameStatus.PLAYING
# The first guess decision of G7 / G8, declared exactly as in the accepted test_program_d23s_policy.
RK03 = PD.declared(("1 M H H H",), 2, 1, 3, (2, 0))
ENGINES_PLANNED = 0
FIX = {}


def stored_bytes(row):
    """One stored record file, refused unless it is the file named in the binding."""
    data = (ROOT / row["path"]).read_bytes()
    if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise AssertionError(f"The stored record is not the bound file: {row['path']}")
    return data


def scaled(diagnosis, factor=10 ** 20):
    """SYNTHETIC: the world counts of every linked result times ``factor``, as long as on a real board."""
    return replace(diagnosis, results=tuple(replace(
        row, survival_worlds=row.survival_worlds * factor, resolved_worlds=row.resolved_worlds * factor,
        unresolved_worlds=row.unresolved_worlds * factor,
        flood_undetermined_worlds=row.flood_undetermined_worlds * factor) for row in diagnosis.results))


def code(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except X.ExplanationError as error:
        return error.code
    raise AssertionError("No ExplanationError was raised.")


def setUpModule():
    """Every fixture is built once, here, with the accepted functions. The tests only read them."""
    never = AssertionError("an Engine was built")
    FIX["engine_guard"] = patch.object(core_engine.MinesweeperEngine, "__init__", side_effect=never)
    FIX["engine_guard"].start()
    if not LT.FIX:
        LT.setUpModule()
    table = FIX["table"] = load_timing_table()
    for name, premises in (("A", PD.RK02_DECLARED), ("C", PD.RK04_DECLARED), ("D", RK03)):
        FIX[name] = d3.decide(premises, table)
        FIX[name + "_pseudo"] = pseudo.diagnose_pseudo(FIX[name])
        FIX[name + "_linked"] = L.diagnose_links(FIX[name])
    session = KLocalSession(8, 2, 1)
    decision = session.analyze_decision(CT.GUESS_8X2, status=PLAYING)
    FIX["B"] = P.apply_combined(lc1.select_singleton_policy(decision, (5, 0), table), table)
    FIX["B_pseudo"] = pseudo.diagnose_pseudo(FIX["B"].guess)
    FIX["B_linked"] = L.diagnose_links(FIX["B"].guess)
    session = KLocalSession(7, 1, 1)
    decision = session.analyze_decision(D2T.X02, status=PLAYING)
    FIX["X02"] = P.apply_combined(lc1.select_singleton_policy(decision, (0, 0), table), table)
    native, _ = D2T.s1(140, 500, 510)
    FIX["kept"] = P.apply_combined(lc1.apply_singleton_band(native), table)
    o4, o5 = D2T.direct((4, 0), 140), D2T.direct((5, 0), 150)
    native = D2T.record((o4, o5), (o4,), unresolved=((6, 0),), mines=((3, 0),))
    FIX["no_proven"] = P.apply_combined(lc1.apply_singleton_band(native), table)
    for name in ("PC01", "PC02", "PC04", "PC10A", "PC10B", "PC13"):
        selection = d3.decide(PD.ALL_CASES[name], table)
        FIX[name] = (selection, pseudo.diagnose_pseudo(selection))
    FIX["PC05_p"] = pseudo.diagnose_premises(PD.PC05, actual_target=(1, 0), selection_reason="K_LC1_GUESS_KEPT",
                                             kind="MIN_RISK")
    ten = FIX["PC10B"][1]
    row = replace(ten.cells[0], status=pseudo.CELL_UNDECIDED, not_examined_pairs=1)
    FIX["undecided"] = replace(ten, cells=(row,) + ten.cells[1:], target_status=pseudo.CELL_UNDECIDED)  # SYNTHETIC
    for name in ("LC01", "LA01", "LC07", "LC03", "LC04", "LC08"):
        FIX[name] = LT.diagnose(name)
    rows = {row["path"].rsplit("/", 1)[-1]: row for row in BINDING["record_files"]}
    FIX["rows"] = rows
    FIX["r97"] = R.decode_record(stored_bytes(rows["97.json"]))
    FIX["r8191"] = R.decode_record(stored_bytes(rows["8191.json"]))
    head = FIX["r97"].inputs[:6]
    FIX["cut"] = R.make_record(  # SYNTHETIC: the stored record cut after its third guess, last input LOST
        record_scope=R.FULL_RUN, width=30, height=16, num_mines=99, allow_guess=True, prefix_inputs=(),
        inputs=head[:5] + (replace(head[5], status_after="LOST"),), blocked=None, final_status="LOST",
        stop_reason=R.TERMINAL)
    FIX["on_certain"] = replace(  # SYNTHETIC: a loss on an input that was no guess
        GR.record_first_click(),
        inputs=(GR.inp(0, 0, 0, decision=R.INITIAL_OPEN), GR.inp(1, 2, 2, "LOST", R.CERTAIN)),
        loss=R.LossClassification(R.INTEGRITY_PROBLEM, None, R.BASIS_CERTAIN, 1))
    FIX["records"] = {
        "record_min": GR.record_min(), "record_tie": GR.record_tie(), "record_forced": GR.record_forced(),
        "record_split_risk": GR.record_split_risk(), "record_forced_WON": GR.record_forced("WON"),
        "record_tie_PLAYING": GR.record_tie("PLAYING"), "record_first_click": GR.record_first_click(),
        "record_not_recorded": GR.record_not_recorded(), "record_guess_off": GR.record_guess_off(),
        "record_limit": GR.record_limit(), "record_single": GR.record_single(),
        "record_kept_forced": GR.record_kept_forced(), "record_five_pairs": GR.record_five_pairs()}


def tearDownModule():
    FIX["engine_guard"].stop()


def decisions():
    """Every decision explanation of the fixtures: (name, DecisionExplanation)."""
    out = [(name, X.explain_decision(FIX[name], pseudo=FIX[name + "_pseudo"], linked=FIX[name + "_linked"]))
           for name in ("A", "B", "C", "D")]
    out += [(name, X.explain_decision(FIX[name])) for name in ("A", "B", "C", "D", "X02", "kept", "no_proven")]
    out += [(name, X.explain_decision(selection, pseudo=diagnosis))
            for name, (selection, diagnosis) in ((n, FIX[n]) for n in ("PC01", "PC02", "PC04", "PC10A", "PC10B", "PC13"))]
    for name, make in (("tie", GR.tie_evidence), ("forced", GR.forced_evidence), ("min", GR.min_evidence),
                       ("limit", GR.limit_evidence), ("single", GR.single_evidence),
                       ("kept_forced", GR.kept_forced_evidence), ("split", GR.split_risk_evidence),
                       ("five", GR.five_pairs_evidence)):
        out.append((name, X.explain_evidence(make())))
        out.append((name + "_blocked", X.explain_evidence(make(), executed=False)))
    return out


def diagnosis_texts():
    out = [X.explain_pseudo(FIX[name][1]) for name in ("PC01", "PC02", "PC04", "PC10A", "PC10B", "PC13")]
    out += [X.explain_pseudo(FIX["PC05_p"]), X.explain_pseudo(FIX["undecided"])]
    out += [X.explain_linked(FIX[name]) for name in ("LC01", "LA01", "LC07", "LC03", "LC04", "LC08")]
    out += [X.explain_linked(FIX[name + "_linked"]) for name in ("A", "B", "C", "D")]
    return out


def losses():
    out = [(name, X.explain_loss(record)) for name, record in FIX["records"].items()]
    return out + [(name, X.explain_loss(FIX[name])) for name in ("r97", "r8191", "cut", "on_certain")]


class ExplanationTests(unittest.TestCase):
    maxDiff = None

    def exact(self, explanation, block):
        self.assertEqual((explanation.short, list(explanation.selection)), (block["short"], block["selection"]))

    # ---- the reason of the actual selection -------------------------------------------------------------

    def test_x01_forced_pair_above_minimum_risk_shows_the_actual_risk(self):
        selection = FIX["A"]
        self.assertEqual((selection.selection_reason, selection.target, selection.original_target,
                          selection.evidence.risk, selection.evidence.original_risk),
                         ("FORCED_5050_FIRST", (3, 0), (4, 0), Fraction(1, 2), Fraction(1, 4)))
        e = X.explain_decision(selection)
        self.exact(e, E["A_forced_above_minimum"])
        # The lower risk of the original target appears as the original proposal's and as the minimum only.
        self.assertIn("50.0%", e.selection[0])
        self.assertNotIn("25.0%", e.selection[0])
        self.assertEqual([i for i, line in enumerate(e.selection) if "25.0%" in line], [1, 3])
        self.assertEqual((e.pseudo, e.linked), ((), ()))

    def test_x02_forced_pair_at_minimum_risk_on_a_real_k_decision(self):
        choice = FIX["B"]
        self.assertEqual((type(choice), choice.branch, choice.guess.selection_reason, choice.guess.target_changed),
                         (P.CombinedSelection, P.BRANCH_GUESS, "FORCED_5050_FIRST", False))
        e = X.explain_decision(choice)
        self.exact(e, E["B_forced_at_minimum_real_k"])
        self.assertNotIn("높", e.short)
        self.assertEqual(X.explain_decision(choice.guess), e)  # the stage-2 record of the same decision

    def test_x03_tie_lookahead_names_bounded_values_not_a_win_rate(self):
        e = X.explain_decision(FIX["C"])
        self.exact(e, E["C_tie"])
        self.assertEqual(e.selection[-1], T["guess"]["S_NOTE"])
        self.assertTrue(all("아니" in line for line in e.selection if "승률" in line))
        # Supplement 1: a value whose reduced terms are long is written as a percentage only (SYNTHETIC value).
        block = S1["tie_with_a_large_s_c"]
        large = X.explain_evidence(replace(GR.tie_evidence(), target_s_c=Fraction(*block["target_s_c"])))
        self.assertEqual(large.selection[2], block["reason_line"])

    def test_x04_kept_minimum_risk_with_and_without_a_lookahead(self):
        self.exact(X.explain_decision(FIX["D"]), E["D_kept"])
        limit = X.explain_evidence(GR.limit_evidence())
        self.assertEqual((limit.short, limit.selection[-1], len(limit.selection), T["guess"]["S_NOTE"] in limit.selection),
                         (E["limit_evidence"]["short"], E["limit_evidence"]["lookahead_line"], 4, False))
        single = X.explain_evidence(GR.single_evidence())
        self.assertEqual((single.selection[-1], len(single.selection), T["guess"]["S_NOTE"] in single.selection),
                         (E["single_evidence"]["lookahead_line"], 4, False))
        five = X.explain_evidence(GR.five_pairs_evidence())
        self.assertEqual((five.short, five.selection[1], five.selection[-1], T["guess"]["S_NOTE"] in five.selection),
                         (E["five_pairs_evidence"]["short"], E["five_pairs_evidence"]["original_line"],
                          E["five_pairs_evidence"]["lookahead_line"], False))
        # Three different states of the look-ahead give three different lines.
        lines = {X.explain_decision(FIX["D"]).selection[3], limit.selection[-1], single.selection[-1]}
        self.assertEqual(len(lines), 3)

    def test_x05_opening_applied_and_kept_are_certain_inputs(self):
        choice = FIX["X02"]
        self.assertEqual((choice.branch, choice.opening.reason), (P.BRANCH_CERTAIN, "PROVEN_OPENING_OVERRIDE"))
        count = choice.opening.applied.region.guaranteed_count
        self.assertGreaterEqual(count, 2)
        e = X.explain_decision(choice)
        self.assertEqual(e.short, T["short"]["OPENING"].format(n=count))
        self.assertEqual(list(e.selection), [E["certain"]["X02_applied"]["actual"], E["certain"]["X02_applied"]["original"],
                                             T["certain"]["REASON_OPENING"].format(n=count)])
        kept = FIX["kept"]
        self.assertEqual((kept.opening.applied, kept.opening.reason), (None, "NO_ELIGIBLE_OPENING"))
        e = X.explain_decision(kept)
        self.exact(e, E["certain"]["s1_no_eligible"])
        none = FIX["no_proven"]
        self.assertEqual((none.opening.applied, none.opening.reason), (None, "NO_PROVEN_OPENING"))
        e = X.explain_decision(none)
        self.assertEqual((e.short, e.selection[2]), (T["short"]["CERTAIN_KEPT"], E["certain"]["a01_no_proven"]["reason"]))
        for name in ("X02", "kept", "no_proven"):
            e = X.explain_decision(FIX[name])
            self.assertEqual((e.pseudo, e.linked), ((), ()))
            self.assertFalse([line for line in e.detail if "지뢰 확률" in line or "추측에서" in line])

    def test_x06_memory_selection_and_stored_evidence_give_the_same_text(self):
        for name, make in (("A", GR.split_risk_evidence), ("C", GR.tie_evidence), ("D", GR.min_evidence)):
            with self.subTest(case=name):
                memory, stored = X.explain_decision(FIX[name]), X.explain_evidence(make())
                self.assertEqual((memory.short, memory.selection), (stored.short, stored.selection))
                self.assertEqual(X.facts_of_selection(FIX[name]), X.facts_of_evidence(make()))
        memory, stored = X.explain_decision(FIX["B"]), X.explain_evidence(GR.kept_forced_evidence())
        self.assertEqual((memory.short, memory.selection), (stored.short, stored.selection))

    def test_x07_a_blocked_proposal_is_worded_as_a_proposal_not_an_input(self):
        sent, blocked = X.explain_evidence(GR.forced_evidence()), X.explain_evidence(GR.forced_evidence(), executed=False)
        self.assertEqual((blocked.selection[0], blocked.selection[1]),
                         (E["blocked_forced_evidence"]["first"], E["blocked_forced_evidence"]["second"]))
        self.assertFalse([line for line in blocked.selection if line.startswith("실제 입력 대상")])
        self.assertTrue(sent.selection[0].startswith("실제 입력 대상"))
        self.assertEqual((blocked.short, blocked.selection[1:]), (sent.short, sent.selection[1:]))
        memory = X.explain_decision(FIX["A"], executed=False)
        self.assertTrue(memory.selection[0].startswith("제안 대상") and "실제 입력이 아니다" in memory.selection[0])

    # ---- the pseudo 50/50 diagnosis ---------------------------------------------------------------------

    def test_x08_pseudo_proven_isolated_and_conditional_with_a_lower_bound(self):
        selection, diagnosis = FIX["PC01"]
        self.assertEqual(list(X.explain_pseudo(diagnosis)), E["pseudo"]["PC01"])
        selection, diagnosis = FIX["PC04"]
        lines = X.explain_pseudo(diagnosis)
        self.assertEqual((lines[1], lines[3], len(lines)),
                         (E["pseudo"]["PC04"]["result"], E["pseudo"]["PC04"]["search"], E["pseudo"]["PC04"]["lines"]))
        selection, diagnosis = FIX["PC02"]
        lines = X.explain_pseudo(diagnosis)
        other = next(cell for cell in ((0, 0), (1, 0)) if cell != selection.target)
        self.assertEqual((lines[1], lines[2], lines[-1]),
                         (T["pseudo"]["PROVEN"].format(partners=f"({other[0]}, {other[1]}) 고립형"),
                          E["pseudo"]["PC02"]["bound"], E["pseudo"]["PC02"]["forced"]))
        for name in ("PC01", "PC04", "PC02"):
            lines = X.explain_pseudo(FIX[name][1])
            bound = [line for line in lines if "하한" in line]
            self.assertEqual(len(bound), 1)
            self.assertIn("승률이나 최적 선택의 증명이 아니다", bound[0])
            self.assertIn("뜻이 다르다", bound[0])
        # Supplement 1: a bound with long terms is written as a percentage only (SYNTHETIC bound).
        block = S1["pseudo_bound_with_large_terms"]
        large = X.explain_pseudo(replace(FIX["PC01"][1], target_bound=tuple(block["target_bound"])))
        self.assertEqual(large[2], block["bound_line"])

    def test_x09_pseudo_refuted_no_pair_partial_and_out_of_range_are_kept_apart(self):
        self.assertEqual(list(X.explain_pseudo(FIX["PC10A"][1])), E["pseudo"]["PC10A"])
        self.assertEqual(list(X.explain_pseudo(FIX["PC10B"][1])), E["pseudo"]["PC10B"])
        selection, diagnosis = FIX["PC13"]
        lines, block = X.explain_pseudo(diagnosis), E["pseudo"]["PC13"]
        self.assertEqual(list(lines[1:]), [block["result"], block["search"], block["far"], block["forced"]])
        self.assertEqual(lines[0], T["pseudo"]["HEAD"].format(cell=f"({selection.target[0]}, {selection.target[1]})"))
        undecided = X.explain_pseudo(FIX["undecided"])
        self.assertEqual(undecided[1], E["pseudo"]["synthetic_undecided"]["result"])
        results = {X.explain_pseudo(FIX["PC01"][1])[1], X.explain_pseudo(FIX["PC10A"][1])[1], lines[1], undecided[1]}
        self.assertEqual(len(results), 4)
        for text in (X.explain_pseudo(FIX["PC10A"][1]), X.explain_pseudo(FIX["PC10B"][1]), lines, undecided):
            self.assertFalse([line for line in text if "하한" in line and "하한은 없다" not in line])
            self.assertFalse([line for line in text if "pseudo가 아니" in line or "거울 쌍이 아니" in line])

    def test_x10_a_proven_pair_of_other_cells_is_not_a_proof_for_the_target(self):
        diagnosis = FIX["PC05_p"]
        self.assertEqual((diagnosis.actual_target, diagnosis.target_status, diagnosis.target_bound),
                         ((1, 0), "REFUTED_IN_SUPPORTED_RANGE", None))
        lines = X.explain_pseudo(diagnosis)
        self.assertEqual((lines[1], lines[-1]), (E["pseudo"]["PC05_target_p"]["result"], E["pseudo"]["PC05_target_p"]["other"]))
        self.assertFalse([line for line in lines if line.startswith("결과: 증명된")])
        self.assertFalse([line for line in lines if "하한:" in line])

    # ---- the linked diagnosis ---------------------------------------------------------------------------

    def test_x11_linked_labels_follow_the_accepted_classification(self):
        lines, block = X.explain_linked(FIX["LC01"]), E["linked"]["LC01"]
        self.assertEqual(list(lines[:5]), [block["head"], block["structure"], block["plan"], block["target"], block["row"]])
        self.assertEqual((lines[5], lines[-1]), (block["other_head"], block["close"]))
        # Supplement 1: world counts too long to read are written as shares; small counts stay as they are.
        self.assertEqual(X.explain_linked(scaled(FIX["LC01"]))[4], S1["linked_scaled_LC01_row"])
        self.assertEqual(X.explain_linked(scaled(FIX["LC01"], 1))[4], block["row"])
        labels = {"LC01": "LINKED_ALL", "LA01": "LINKED_SOME", "LC07": "UNDETERMINED", "LC03": "NOT_OBSERVED",
                  "LC04": "NOT_APPLICABLE"}
        for name, label in labels.items():
            with self.subTest(case=name):
                diagnosis = FIX[name]
                self.assertEqual(diagnosis.target_label, label)
                self.assertEqual(X.explain_linked(diagnosis)[3], T["linked"]["TARGET"][label])
        for name in ("LA01", "LC07", "LC03", "LC04"):
            self.assertEqual(X.explain_linked(FIX[name])[3], E["linked"][name]["target"])
        self.assertEqual(len(set(T["linked"]["TARGET"].values())), 5)
        lines = X.explain_linked(FIX["LC04"])
        self.assertEqual((lines[1], lines[2]), (E["linked"]["LC04"]["structure"], E["linked"]["LC04"]["plan"]))

    def test_x12_linked_not_examined_out_of_scope_and_no_pair_are_not_no_link(self):
        lines = X.explain_linked(FIX["LC08"])
        self.assertEqual(lines[2], E["linked"]["LC08"]["plan"])
        self.assertIn(E["linked"]["LC08"]["limit"], lines)
        self.assertIn(E["linked"]["LC07"]["out_of_scope"], X.explain_linked(FIX["LC07"]))
        self.assertIn(E["linked"]["LC04"]["out_of_scope"], X.explain_linked(FIX["LC04"]))
        diagnosis, block = FIX["D_linked"], E["linked"]["RK03_no_listed_pair"]
        self.assertEqual((diagnosis.plan.status, diagnosis.actual_calls), ("NO_LISTED_PAIR", 0))
        lines = X.explain_linked(diagnosis)
        self.assertEqual(list(lines[1:4]), [block["structure"], block["plan"], block["target"]])
        for name in ("LC08", "LC07", "LC04", "D_linked"):
            for line in X.explain_linked(FIX[name]):
                if "연결 없음" in line:
                    self.assertIn("아니", line)
                self.assertNotIn("독립이다", line)

    def test_x13_results_of_other_anchor_cells_are_not_the_targets_results(self):
        selection, diagnosis, block = FIX["C"], FIX["C_linked"], E["linked"]["RK04_bound_to_its_selection"]
        self.assertEqual((diagnosis.actual_target, diagnosis.original_target, diagnosis.actual_calls),
                         ((2, 2), (0, 2), 7))
        lines = X.explain_decision(selection, linked=diagnosis).linked
        self.assertEqual((lines[2], lines[3]), (block["plan"], block["target"]))
        head = lines.index(T["linked"]["OTHER_HEAD"])
        own = lines[4:head]
        other = [line for line in lines[head + 1:] if line.startswith("기준 칸 ")]
        self.assertTrue(own and all(line.startswith("묶음 ") for line in own))
        self.assertFalse([line for line in own if "풀린다" in line])
        self.assertTrue(other[0].startswith(block["other_row_starts_with"]))
        # No result of another anchor cell stands above the heading that says whose result it is.
        self.assertFalse([line for line in lines[:head] if line.startswith("기준 칸 ")])
        self.assertEqual(lines[-1], T["linked"]["CLOSE"])
        self.assertIn(S1["linked_scaled_RK04_other_row"], X.explain_linked(scaled(diagnosis)))
        self.assertIn("실제 대상의 결과가 아니다", lines[head])

    def test_x14_diagnoses_are_bound_to_their_decision_and_never_change_the_reason(self):
        for name in ("A", "B", "C", "D"):
            with self.subTest(case=name):
                plain = X.explain_decision(FIX[name])
                full = X.explain_decision(FIX[name], pseudo=FIX[name + "_pseudo"], linked=FIX[name + "_linked"])
                self.assertEqual((plain.short, plain.selection), (full.short, full.selection))
                self.assertEqual((plain.pseudo, plain.linked), ((), ()))
                self.assertEqual(full.detail, full.selection + full.pseudo + full.linked)
                self.assertIn("선택에 쓰지 않음", full.pseudo[0])
                self.assertIn("선택에 쓰지 않음", full.linked[0])
                for word in RULES["selection_lines_never_contain"]:
                    self.assertFalse([line for line in full.selection if word in line])
                self.assertFalse([line for line in full.pseudo + full.linked if line.startswith("선택 이유")])
        # A diagnosis of another decision is refused, whatever it says.
        self.assertEqual(code(X.explain_decision, FIX["A"], pseudo=FIX["C_pseudo"]), "EXPLANATION_BINDING")
        self.assertEqual(code(X.explain_decision, FIX["A"], linked=FIX["C_linked"]), "EXPLANATION_BINDING")
        self.assertEqual(code(X.explain_decision, FIX["B"], pseudo=FIX["PC02"][1]), "EXPLANATION_BINDING")
        moved = replace(FIX["A_pseudo"], actual_target=(4, 0))
        self.assertEqual(code(X.explain_decision, FIX["A"], pseudo=moved), "EXPLANATION_BINDING")

    # ---- the basic note of a loss -----------------------------------------------------------------------

    def test_x15_loss_note_only_for_a_lost_last_input_with_pre_input_evidence(self):
        for name in ("record_min", "record_tie", "record_forced", "record_split_risk"):
            with self.subTest(record=name):
                record, block = FIX["records"][name], E["loss"][name]
                note = X.explain_loss(record)
                self.assertEqual((note.status, note.shown, note.basis, note.input_index, list(note.lines)),
                                 ("LOST", True, "PRE_INPUT_EVIDENCE", block["input_index"], block["lines"]))
                self.assertEqual(note.input_index, record.inputs[-1].index)
        for name in ("record_forced_WON", "record_tie_PLAYING"):
            note = X.explain_loss(FIX["records"][name])
            self.assertEqual((note.status, note.shown, note.basis, note.input_index, note.lines),
                             (E["loss"][name]["status"], False, None, None, ()))
        # The lower risk of the original target is named as the minimum of that time, not as the input's risk.
        lines = X.explain_loss(FIX["records"]["record_split_risk"]).lines
        self.assertIn("50.0%", lines[0])
        self.assertNotIn("25.0%", lines[0])

    def test_x16_loss_without_evidence_is_reported_as_unknown(self):
        for name, record in (("record_first_click", FIX["records"]["record_first_click"]),
                             ("record_not_recorded", FIX["records"]["record_not_recorded"]),
                             ("synthetic_lost_on_certain", FIX["on_certain"])):
            with self.subTest(record=name):
                note, block = X.explain_loss(record), E["loss"][name]
                self.assertEqual((note.status, note.shown, note.basis, list(note.lines)),
                                 ("LOST", True, block["basis"], block["lines"]))
                self.assertFalse([line for line in note.lines if "지뢰 확률" in line or "최소 위험" in line])

    def test_x17_a_blocked_proposal_is_neither_an_input_nor_a_loss_cause(self):
        record, block = FIX["records"]["record_guess_off"], E["loss"]["record_guess_off"]
        self.assertEqual((record.final_status, record.blocked is not None, len(record.inputs)), ("PLAYING", True, 4))
        note = X.explain_loss(record)
        self.assertEqual((note.status, note.shown, note.basis, note.input_index, list(note.lines)),
                         ("PLAYING", False, None, None, block["lines"]))
        self.assertFalse([line for line in note.lines if line.startswith("패배 보조 설명")])
        # The same proposal, explained as a decision, is a proposal and not an input.
        proposal = X.explain_evidence(record.blocked.evidence, executed=False)
        self.assertTrue(proposal.selection[0].startswith("제안 대상"))

    def test_x18_several_guesses_the_note_follows_the_last_actual_input(self):
        for name, key in (("r97", "stored_97"), ("r8191", "stored_8191")):
            record, block = FIX[name], E["loss"][key]
            guesses = [item.index for item in record.inputs if item.decision == R.GUESS]
            note = X.explain_loss(record)
            self.assertEqual((record.final_status, guesses, note.shown, note.lines),
                             (block["status"], block["guess_inputs"], False, ()))
        # Supplement 1: a risk whose reduced terms are long is written as a percentage only.
        firsts = {str(item.index): X.explain_evidence(item.evidence).selection[0]
                  for item in FIX["r97"].inputs if item.decision == R.GUESS}
        self.assertEqual(firsts, S1["stored_97_first_lines"])
        one = next(item for item in FIX["r8191"].inputs if item.decision == R.GUESS)
        self.assertEqual(X.explain_evidence(one.evidence).short, E["loss"]["stored_8191"]["guess_short"])
        record, block = FIX["cut"], E["loss"]["synthetic_97_cut_after_input_5"]
        self.assertEqual((record.final_status, [i.index for i in record.inputs if i.decision == R.GUESS]),
                         ("LOST", [3, 4, 5]))
        note = X.explain_loss(record)
        self.assertEqual((note.shown, note.basis, note.input_index, note.lines[0]),
                         (True, block["basis"], block["input_index"], block["first_line"]))
        text = " ".join(note.lines)
        self.assertFalse([word for word in block["must_not_contain"] if word in text])
        earlier = [X.explain_evidence(item.evidence).short for item in record.inputs[3:5]]
        self.assertEqual(earlier, block["earlier_guess_shorts"])
        # The stored record itself is unchanged by the cut and by the explanations.
        self.assertEqual(R.encode_record(FIX["r97"]), stored_bytes(FIX["rows"]["97.json"]))

    # ---- what the module does not do --------------------------------------------------------------------

    def test_x19_explanations_make_no_calculation_decision_judgement_or_engine_input(self):
        blocked = (
            (simple_probability, "calculate_probabilities"), (d3, "_kernel"), (pseudo, "_kernel"), (L, "_kernel"),
            (KLocalSession, "analyze_decision"), (KLocalSession, "analyze_local"), (KLocalSession, "validate"),
            (lc1, "select_singleton_policy"), (lc1, "apply_singleton_band"), (lc1, "validate_singleton_selection"),
            (d3, "apply_lookahead"), (d3, "decide"), (d3, "_decide"), (d3, "validate_lookahead_selection"),
            (d3, "premises_of"), (d2, "apply_proven_opening"), (d2, "validate_opening_selection"),
            (P, "apply_combined"), (P, "select_combined_policy"), (P, "validate_combined_selection"),
            (P, "check_combined_shape"), (stage1, "pair_proofs_for_state"), (stage1, "find_pairs"),
            (pseudo, "plan_pseudo"), (pseudo, "diagnose_premises"), (pseudo, "diagnose_pseudo"),
            (pseudo, "validate_pseudo_diagnosis"), (L, "plan_links"), (L, "diagnose_links"),
            (L, "diagnose_premises_links"), (L, "validate_link_diagnosis"), (L, "examine_cell"),
            (R, "validate_record"), (R, "classify"), (R, "make_record"), (R, "decode_record"), (R, "describe"),
            (core_engine.MinesweeperEngine, "step"))
        with ExitStack() as stack:
            spies = [stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
                     for owner, name in blocked]
            made = (len(decisions()), len(diagnosis_texts()), len(losses()), len(X.help_lines()))
            self.assertEqual([spy.call_count for spy in spies], [0] * len(blocked))
        self.assertEqual(made[3], 8)
        self.assertTrue(all(count > 0 for count in made))
        # The source: only these imports, and no function of an accepted module is called.
        tree = ast.parse(Path(X.__file__).read_text(encoding="utf-8"))
        imported, aliases = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.update(f"{node.module}.{alias.name}" for alias in node.names)
                aliases.update(alias.asname for alias in node.names if alias.asname)
        self.assertEqual(imported, {
            "dataclasses.dataclass", "fractions.Fraction", "experiments.program_d2_opening_policy",
            "experiments.program_d3_guess_record", "experiments.program_d3_link_diagnosis",
            "experiments.program_d3_lookahead_policy", "experiments.program_d3_pseudo_diagnosis",
            "experiments.program_d23_policy.BRANCH_CERTAIN", "experiments.program_d23_policy.BRANCH_GUESS",
            "experiments.program_d23_policy.CombinedSelection"})
        self.assertEqual(aliases, {"opening_policy", "guess_record", "link_diagnosis", "lookahead", "mirror"})
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        through_modules = [ast.unparse(node.func) for node in calls if isinstance(node.func, ast.Attribute)
                           and isinstance(node.func.value, ast.Name) and node.func.value.id in aliases]
        self.assertEqual(through_modules, [])
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertFalse(names & {"open", "eval", "exec", "print", "__import__", "CombinedSelection.__init__"})
        self.assertEqual(ENGINES_PLANNED, 0)

    def test_x20_inputs_are_unchanged_and_the_output_is_deterministic(self):
        table = FIX["table"]
        material = [FIX[name] for name in ("A", "B", "C", "D", "X02", "kept", "no_proven", "PC05_p", "undecided",
                                           "LC01", "LC08", "r8191", "cut", "on_certain")]
        material += [FIX[name + suffix] for name in ("A", "B", "C", "D") for suffix in ("_pseudo", "_linked")]
        material += list(FIX["records"].values())
        before = [repr(item) for item in material]
        encoded = {name: R.encode_record(record) for name, record in FIX["records"].items()}
        files = {name: hashlib.sha256(stored_bytes(row)).hexdigest() for name, row in FIX["rows"].items()}
        first = (decisions(), diagnosis_texts(), losses(), X.help_lines())
        second = (decisions(), diagnosis_texts(), losses(), X.help_lines())
        self.assertEqual(first, second)
        self.assertEqual([repr(item) for item in material], before)
        self.assertEqual({name: R.encode_record(record) for name, record in FIX["records"].items()}, encoded)
        self.assertEqual({name: hashlib.sha256(stored_bytes(row)).hexdigest() for name, row in FIX["rows"].items()},
                         files)
        # Equal material built a second time gives the same text, and the selection is what it was.
        again = d3.decide(PD.RK02_DECLARED, table)
        self.assertEqual(again, FIX["A"])
        self.assertEqual(X.explain_decision(again), X.explain_decision(FIX["A"]))
        self.assertEqual((again.target, again.selection_reason, again.move, again.category),
                         (FIX["A"].target, FIX["A"].selection_reason, FIX["A"].move, FIX["A"].category))
        for item in first[0]:
            self.assertIs(type(item[1]), X.DecisionExplanation)
            self.assertTrue(all(type(line) is str for line in item[1].detail) and type(item[1].short) is str)

    def test_x21_wording_rules_hold_for_every_generated_text(self):
        explained = decisions()
        shorts = [e.short for _, e in explained]
        selections = [line for _, e in explained for line in e.selection]
        lines = selections + [line for _, e in explained for line in e.pseudo + e.linked]
        lines += [line for text in diagnosis_texts() for line in text]
        lines += [line for _, note in losses() for line in note.lines]
        lines += list(X.help_lines())
        everything = shorts + lines
        self.assertGreater(len(everything), 200)
        for line in everything:
            if "승률" in line:
                self.assertIn(RULES["every_line_with_승률_also_has"], line)
            if "연결 없음" in line:
                self.assertIn(RULES["every_line_with_연결_없음_also_has"], line)
            for word in RULES["never_appears"]:
                self.assertNotIn(word, line)
            if "%p" in line:
                self.assertTrue("높" in line or "차이" in line, line)
            self.assertNotIn("\n", line)
        for word in RULES["selection_lines_never_contain"]:
            self.assertFalse([line for line in selections + shorts if word in line])
        for _, e in explained:
            for block in (e.pseudo, e.linked):
                if block:
                    self.assertIn(RULES["first_line_of_each_diagnosis_contains"], block[0])
            # The short line is one line and is not the detail.
            self.assertLessEqual(len(e.short), 80)
            self.assertGreaterEqual(len(e.selection), 3)
            self.assertNotIn(e.short, e.selection)
        for text in diagnosis_texts():
            self.assertIn(RULES["first_line_of_each_diagnosis_contains"], text[0])
        # Supplement 1: no generated line holds a number too long to read, also for real-board sized counts.
        extra = [line for item in FIX["r97"].inputs + FIX["r8191"].inputs if item.decision == R.GUESS
                 for line in X.explain_evidence(item.evidence).detail]
        extra += [line for name in ("LC01", "LC08", "A_linked", "C_linked")
                  for line in X.explain_linked(scaled(FIX[name]))]
        self.assertGreater(len(extra), 30)
        for line in everything + extra:
            self.assertIsNone(re.search(r"[0-9]{10,}", line), line)
        # S_c and S_v never appear without the note that they are bounded look-ahead values.
        for _, e in explained:
            if any("S_c" in line or "S_v" in line for line in e.selection):
                self.assertIn(T["guess"]["S_NOTE"], e.selection)

    def test_x22_help_text_is_static_and_states_the_limits(self):
        lines = X.help_lines()
        self.assertEqual((type(lines), list(lines)), (tuple, T["help"]))
        self.assertIs(X.help_lines(), lines)
        self.assertEqual(len(lines), 8)
        text = " ".join(lines)
        for phrase in ("판 전체 승률이 아니다", "하한은 승률이나 최적 선택의 증명이 아니다", "선택에 쓰지 않는다",
                       "독립의 증명이 아니고", "연결이 없다는 뜻이 아니다", "입력도 패배 원인도 아니다", "%p"):
            self.assertIn(phrase, text)

    def test_x23_percent_and_point_formatting_never_rounds_to_certainty(self):
        for (numerator, denominator), text in PLAN["format_samples"]["percent_text"]:
            with self.subTest(value=(numerator, denominator)):
                self.assertEqual(X.percent_text(Fraction(numerator, denominator)), text)
                # The product's display rule gives the same text for the same world counts.
                self.assertEqual(format_mine_probability(CellProbability((0, 0), numerator, denominator)), text)
        for higher, lower, text in PLAN["format_samples"]["points_text"]:
            self.assertEqual(X.points_text(Fraction(*higher), Fraction(*lower)), text)
        for wrong in (0.5, 1, True, "1/2", Fraction(3, 2), Fraction(-1, 2)):
            self.assertEqual(code(X.percent_text, wrong), "EXPLANATION_TYPE")
        self.assertEqual(code(X.points_text, Fraction(1, 4), Fraction(1, 2)), "EXPLANATION_TYPE")

    def test_x24_wrong_types_and_inconsistent_material_are_refused(self):
        a, minimum = FIX["A"], FIX["records"]["record_min"]
        types = (
            (X.explain_decision, ({},), {}), (X.explain_decision, (a,), {"executed": 1}),
            (X.explain_decision, (a,), {"pseudo": FIX["A_linked"]}), (X.explain_decision, (a,), {"linked": FIX["A_pseudo"]}),
            (X.explain_evidence, (a.evidence,), {}), (X.explain_pseudo, (FIX["A_linked"],), {}),
            (X.explain_linked, (FIX["A_pseudo"],), {}), (X.explain_loss, ("LOST",), {}),
            (X.explain_loss, (minimum.loss,), {}))
        for function, args, kwargs in types:
            self.assertEqual(code(function, *args, **kwargs), "EXPLANATION_TYPE")
        binding = (
            (X.explain_decision, (FIX["X02"],), {"pseudo": FIX["A_pseudo"]}),
            (X.explain_loss, (replace(minimum, loss=replace(minimum.loss, input_index=0)),), {}),
            (X.explain_loss, (replace(minimum, loss=replace(minimum.loss, kind=R.FORCED_5050)),), {}))
        for function, args, kwargs in binding:
            self.assertEqual(code(function, *args, **kwargs), "EXPLANATION_BINDING")
        proven = FIX["PC01"][1]
        material = (
            (X.explain_decision, (FIX["X02"],), {"executed": False}),
            (X.explain_evidence, (replace(GR.min_evidence(), selection_reason="OTHER"),), {}),
            (X.explain_evidence, (replace(GR.split_risk_evidence(), is_minimum_risk=True),), {}),
            (X.explain_evidence, (replace(GR.tie_evidence(), target_s_c=None),), {}),
            (X.explain_pseudo, (replace(proven, target_status="REFUTED_IN_SUPPORTED_RANGE"),), {}),
            (X.explain_pseudo, (replace(proven, target_bound=None),), {}),
            (X.explain_pseudo, (replace(proven, search_status="DONE"),), {}),
            (X.explain_linked, (replace(FIX["LC01"], target_label="LINKED"),), {}),
            (X.explain_loss, (replace(FIX["records"]["record_forced_WON"], loss=minimum.loss),), {}))
        for function, args, kwargs in material:
            self.assertEqual(code(function, *args, **kwargs), "EXPLANATION_MATERIAL")
        # A refusal is an error; it is never turned into a milder sentence.
        self.assertTrue(issubclass(X.ExplanationError, ValueError))


if __name__ == "__main__":
    unittest.main()
