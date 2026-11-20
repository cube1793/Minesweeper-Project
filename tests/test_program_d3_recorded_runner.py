"""S3D3-A stage 3 (GUESS_OUTCOME_RECORD_V1): the recording layer on real tiny Engines.

Kinds of evidence, kept apart on purpose:
  * full runs (G1, G2, G4, G5, G6, G7, G8, R11L, F1) start from the canonical
    initial state on fixed tiny synthetic layouts chosen first; every expected
    move, result and classification was fixed by hand beforehand
    (VERIFICATION_PLAN.json). No seed search, no public Expert board.
  * segments after a prefix state (E_TIE_L, E_TIE, E_SINGLE_L, E_FIVE_PAIRS_L)
    receive an explicit list of legal public inputs through the input-cap
    proxy; a fresh KLocalSession analyses the resulting grid; the unchanged
    stage-2 policy and both validators decide and check ONE input. Neither
    Engine state nor M is injected. They are not autonomous runs from the
    first input and not evaluation boards.
  * stand-ins (an Engine double that reports LOST although the game goes on,
    a modified copy of a real run result) exist only for the integrity case.
The hidden layout is used only to build the Engine. Every Engine is wrapped by
the input-cap proxy (tools/s3d2_input_cap.py, loaded by path). Results here
are functional checks and no evidence about win rate. Files written by these
tests go to a new folder under the process's temporary directory and stay there.
"""

from dataclasses import replace
from fractions import Fraction
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import simple_probability
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from experiments import program_d3_forced_pair_policy as stage1
from experiments import program_d3_guess_record as record
from experiments import program_d3_lookahead_policy as policy
from experiments import program_d3_lookahead_runner as d3runner
from experiments import program_d3_recorded_runner as recorded
from experiments import program_k_lc1_policy as lc1
from experiments.program_k_capability import KLocalSession
from experiments.program_k_runner import KExecutionError, validate_k_p0_execution
from simple_algorithm import SimpleMove
from stage3_physical import load_timing_table
from tests.test_program_d3_guess_record import forced_evidence, min_evidence, tie_evidence
from tests.test_program_k_harness import PublicPort


# 입력 상한 도우미는 제품 저장소의 tests/support에 있다(출력 폴더의 tools에서 옮겼다).
TOOLS = Path(__file__).resolve().parent / "support"


def load_tool(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cap_tool = load_tool("s3d2_input_cap")
H, PLAYING, WON, LOST = int(CellState.HIDDEN), GameStatus.PLAYING, GameStatus.WON, GameStatus.LOST
HALF = Fraction(1, 2)
# Full games: (width, height, mines).
BOARDS = {
    "G1": (2, 8, ((0, 3),)), "G2": (2, 8, ((1, 3),)), "G4": (8, 2, ((3, 0),)),
    "G5": (6, 2, ((3, 1), (5, 0))), "G6": (6, 2, ((3, 0), (5, 0))), "G7": (5, 1, ((1, 0), (3, 0))),
    "G8": (5, 1, ((1, 0), (2, 0))), "R11L": (11, 1, ((1, 0), (2, 0))),
    "F1": (3, 3, ((0, 0), (0, 1), (1, 1), (2, 2))),
}
GUESS_ALLOWED = ("G1", "G2", "G4", "G6", "G7", "G8", "R11L", "F1")
GUESS_OFF = ("G1", "G5", "G7")
D3_CALLS = {("G1", True): 4, ("G2", True): 4, ("G4", True): 4, ("G6", True): 8, ("G7", True): 7,
            ("G8", True): 7, ("R11L", True): 0, ("F1", True): 0, ("G1", False): 4, ("G5", False): 8,
            ("G7", False): 7}
# Segments after a prefix state: (board, legal public OPEN inputs). The cursor is the last input.
E_TIE_L = ((3, 3, ((0, 0), (0, 1), (1, 1), (2, 2))), ((1, 0), (2, 0)))
E_TIE = ((3, 3, ((0, 0), (0, 1), (1, 1), (0, 2))), ((1, 0), (2, 0)))
E_SINGLE_L = ((7, 1, ((0, 0), (1, 0), (4, 0))), ((3, 0), (5, 0)))
E_FIVE_PAIRS_L = ((19, 2, ((1, 0), (5, 1), (9, 0), (13, 1), (17, 1))),
                  ((3, 0), (7, 0), (11, 0), (15, 0), (0, 0), (0, 1), (18, 0), (18, 1)))


def O(x, y):
    return SimpleMove(Action.OPEN, x, y)


class SpyEngine(MinesweeperEngine):
    """Engine-side count of inputs that really reached the Engine."""

    def step(self, x, y, action):
        self.steps = getattr(self, "steps", 0) + 1
        return super().step(x, y, action)


def build(board, cap=480):
    width, height, mines = board
    engine = SpyEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), frozenset(mines))
    engine.steps = 0
    return engine, cap_tool.CappedEngine(engine, cap)


def raw_engine(board):
    width, height, mines = board
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), frozenset(mines))
    return engine


def public(guard):
    return tuple(tuple(int(v) for v in row) for row in guard.get_observation())


def new_folder():
    return tempfile.mkdtemp(prefix="s3d3run_")  # left in place; nothing is deleted


class Calls:
    """Counts D3's hypothetical calls at the stage-2 policy's single seam."""

    def __init__(self):
        self.count, self.original = 0, policy._kernel

    def __call__(self, observation, num_mines):
        self.count += 1
        return self.original(observation, num_mines)


def counting():
    return patch.object(policy, "_kernel", Calls())


def kernel_total():
    return patch("simple_probability.calculate_probabilities",
                 wraps=simple_probability.calculate_probabilities)


class LyingEngine:
    """Stand-in: reports LOST after its second input although the real game goes on."""

    def __init__(self, guard):
        self._guard, self.steps = guard, 0

    width = property(lambda self: self._guard.width)
    height = property(lambda self: self._guard.height)
    num_mines = property(lambda self: self._guard.num_mines)

    @property
    def status(self):
        return LOST if self.steps >= 2 else self._guard.status

    def get_observation(self):
        return self._guard.get_observation()

    def step(self, x, y, action):
        self.steps += 1
        return self._guard.step(x, y, action)


class RunCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def run_recorded(self, name, allow_guess=True, save_path=None):
        engine, guard = build(BOARDS[name])
        return engine, guard, recorded.run_recorded(guard, allow_guess=allow_guess, table=self.table,
                                                    save_path=save_path)

    def run_plain(self, name, allow_guess=True):
        engine, guard = build(BOARDS[name])
        return engine, guard, d3runner.run_s3d3_stage2(guard, allow_guess=allow_guess, table=self.table,
                                                       capture_effects=False)

    def loss(self, item):
        return (item.loss.applicability, item.loss.kind, item.loss.basis, item.loss.input_index)

    def segment(self, state):
        """Prefix inputs, a fresh session's decision, the unchanged stage-2 selection and both
        validations, ONE input through the cap channel, then the record of that segment."""
        board, prefix = state
        engine, guard = build(board)
        for x, y in prefix:
            guard.step(x, y, Action.OPEN)
            self.assertIs(guard.status, PLAYING)
        observation, cursor = public(guard), prefix[-1]
        session = KLocalSession(guard.width, guard.height, guard.num_mines)  # fresh; M is not injected
        decision = session.analyze_decision(observation, status=PLAYING)
        inner = lc1.select_singleton_policy(decision, cursor, self.table)
        choice = policy.apply_lookahead(inner, self.table)
        common = dict(status=PLAYING, num_mines=len(board[2]), cursor=cursor, current_mines=session.M,
                      decision=decision)
        validate_k_p0_execution(observation, inner.selected.move, selection=inner.selected, **common)
        d3runner.validate_lookahead_execution(observation, choice.move, choice=choice, table=self.table,
                                              **common)
        before = recorded.evidence_of(choice)  # fixed before the input
        guard.step(choice.move.x, choice.move.y, choice.move.action)
        status = guard.status
        outcome = recorded.record_of_segment(
            guard.width, guard.height, guard.num_mines, tuple(O(x, y) for x, y in prefix),
            (recorded.SegmentInput(choice.move, status, choice),))
        return dict(engine=engine, guard=guard, session=session, observation=observation, decision=decision,
                    inner=inner, choice=choice, common=common, before=before, status=status, record=outcome)


class RecordedRunTests(RunCase):
    def test_x01_a_loss_stays_lost_and_is_never_retried(self):
        with patch.object(recorded, "run_s3d3_stage2", wraps=recorded.run_s3d3_stage2) as runner:
            engine, guard, r = self.run_recorded("G2")
        self.assertEqual(runner.call_count, 1)
        self.assertEqual((r.run.status, r.run.stop_reason, r.record.final_status, r.record.stop_reason,
                          engine.status, engine.steps, guard.engine_inputs_reached, len(r.record.inputs)),
                         (LOST, "TERMINAL", "LOST", "TERMINAL", LOST, 5, 5, 5))
        self.assertEqual(r.run.moves, (O(0, 0), O(0, 4), O(1, 4), O(1, 5), O(1, 3)))
        self.assertEqual([(i.index, i.action, i.x, i.y, i.status_after, i.decision) for i in r.record.inputs],
                         [(0, "OPEN", 0, 0, "PLAYING", "INITIAL_OPEN"), (1, "OPEN", 0, 4, "PLAYING", "CERTAIN"),
                          (2, "OPEN", 1, 4, "PLAYING", "CERTAIN"), (3, "OPEN", 1, 5, "PLAYING", "CERTAIN"),
                          (4, "OPEN", 1, 3, "LOST", "GUESS")])
        self.assertEqual(self.loss(r.record), ("APPLIES", "FORCED_5050", "PRE_INPUT_EVIDENCE", 4))
        self.assertEqual((r.save.state, r.record.record_scope, r.record.allow_guess, r.record.prefix_inputs,
                          (r.record.width, r.record.height, r.record.num_mines)),
                         ("NOT_SAVED", record.FULL_RUN, True, (), (2, 8, 1)))
        # The first input can lose too: there is no evidence before it, so the type is unconfirmed.
        engine, guard, first = self.run_recorded("F1")
        self.assertEqual((first.run.status, first.run.moves, engine.steps, first.record.final_status,
                          self.loss(first.record)),
                         (LOST, (O(0, 0),), 1, "LOST",
                          ("APPLIES", "UNCLASSIFIED", "INITIAL_OPEN_WITHOUT_EVIDENCE", 0)))

    def test_x02_the_classification_is_the_pre_input_evidence_of_the_last_actual_input(self):
        expected = {"G2": ("FORCED_5050", (1, 3), HALF, (0, 3), HALF, "COMPUTED", 4),
                    "G4": ("FORCED_5050", (3, 0), HALF, (3, 0), HALF, "COMPUTED", 3),
                    "G6": ("FORCED_5050", (3, 0), HALF, (4, 0), Fraction(1, 4), "COMPUTED", 1),
                    "G8": ("MIN_RISK", (2, 0), Fraction(1, 3), (2, 0), Fraction(1, 3), "COMPUTED", 1),
                    "R11L": ("MIN_RISK", (2, 0), Fraction(1, 9), (2, 0), Fraction(1, 9),
                             "NOT_COMPUTED_CANDIDATE_LIMIT", 1)}
        for name, (kind, target, risk, original, original_risk, status, index) in expected.items():
            with self.subTest(board=name):
                engine, guard, r = self.run_recorded(name)
                last_trace, last = r.run.traces[-1], r.record.inputs[-1]
                self.assertEqual((r.run.status, r.record.final_status), (LOST, "LOST"))
                self.assertIs(last_trace.evidence, last_trace.choice.evidence)
                self.assertEqual(last.evidence, recorded.evidence_of(last_trace.choice))
                self.assertEqual((last.evidence.kind, last_trace.evidence.kind, last.evidence.target,
                                  (last.x, last.y), last.evidence.risk, last.evidence.original_target,
                                  last.evidence.original_risk, last.evidence.lookahead_status),
                                 (kind, kind, target, target, risk, original, original_risk, status))
                self.assertEqual(self.loss(r.record), ("APPLIES", kind, "PRE_INPUT_EVIDENCE", index))
                self.assertEqual(last.evidence.selection_reason, last_trace.choice.selection_reason)
        # The real decisions give exactly the hand-written evidence of the plan.
        self.assertEqual(self.run_recorded("G2")[2].record.inputs[-1].evidence, forced_evidence())
        self.assertEqual(self.run_recorded("G8")[2].record.inputs[-1].evidence, min_evidence())
        g4 = self.run_recorded("G4")[2].record.inputs[-1].evidence
        self.assertEqual((g4.target_changed, g4.category, g4.ranking, g4.pair, g4.rank_basis),
                         (False, "EXACT_MINIMUM_RISK_GUESS",
                          (((3, 0), HALF, 180604), ((3, 1), HALF, 193056)), ((3, 0), (3, 1)), "S_COST_READING"))
        g6 = self.run_recorded("G6")[2].record.inputs[-1].evidence
        self.assertEqual((g6.is_minimum_risk, g6.target_s_c, g6.original_s_v, g6.planned_calls),
                         (False, HALF, None, 8))
        # An earlier guess is never the evidence of a later input: G7 guesses at input 1 and
        # wins with a certain input. A modified copy of that result that ends LOST (synthetic)
        # is an integrity problem, not a MIN_RISK loss.
        engine, guard, r = self.run_recorded("G7")
        self.assertEqual(([i.decision for i in r.record.inputs], r.record.inputs[1].evidence.kind,
                          self.loss(r.record)),
                         (["INITIAL_OPEN", "GUESS", "CERTAIN"], "MIN_RISK", ("NOT_APPLICABLE_WON", None, None, None)))
        last = r.run.traces[-1]
        forged = replace(r.run, status=LOST, traces=r.run.traces[:-1] + (
            replace(last, action=replace(last.action, status_after=LOST)),))
        self.assertEqual(self.loss(recorded.record_of_run(forged, 5, 1, 2, True)),
                         ("INTEGRITY_PROBLEM", None, "LOST_ON_CERTAIN_INPUT", 2))

    def test_x02_segments_after_a_prefix_state_are_classified_from_their_own_evidence(self):
        single = self.segment(E_SINGLE_L)
        self.assertEqual(single["observation"], ((H, H, H, 1, H, 1, H),))
        evidence = single["record"].inputs[-1].evidence
        self.assertEqual((single["status"], single["record"].record_scope, single["record"].final_status,
                          self.loss(single["record"]), evidence, single["engine"].steps),
                         (LOST, record.SEGMENT, "LOST", ("APPLIES", "MIN_RISK", "PRE_INPUT_EVIDENCE", 2),
                          single["before"], 3))
        self.assertEqual((evidence.target, evidence.risk, evidence.lookahead_status, evidence.lookahead_cells,
                          evidence.values, evidence.target_s_c, evidence.original_s_v, evidence.actual_calls,
                          [p.verdict for p in evidence.pair_proofs], evidence.public_state.mines,
                          evidence.public_state.total_worlds, dict(evidence.public_state.mine_worlds)),
                         ((4, 0), Fraction(1, 3), "NOT_REQUIRED_SINGLE", ((4, 0),), (), None, None, 0,
                          ["APPARENT_5050", "APPARENT_5050"], (), 3,
                          {(0, 0): 2, (1, 0): 2, (2, 0): 2, (4, 0): 1, (6, 0): 2}))
        five = self.segment(E_FIVE_PAIRS_L)
        evidence = five["record"].inputs[-1].evidence
        self.assertEqual((five["status"], five["record"].final_status, self.loss(five["record"]),
                          five["engine"].steps, len(five["record"].prefix_inputs)),
                         (LOST, "LOST", ("APPLIES", "FORCED_5050", "PRE_INPUT_EVIDENCE", 8), 9, 8))
        self.assertEqual((evidence.kind, evidence.selection_reason, evidence.target, evidence.risk,
                          evidence.original_target, evidence.original_risk, evidence.target_changed,
                          evidence.category, evidence.pair, evidence.lookahead_status, evidence.lookahead_set,
                          len(evidence.lookahead_cells), evidence.rank_basis, evidence.ranking[:2],
                          len(evidence.ranking), evidence.values, evidence.planned_calls, evidence.target_s_c,
                          evidence.original_s_v, evidence.independence, evidence.public_state.total_worlds),
                         ("FORCED_5050", "FORCED_5050_FIRST", (17, 1), HALF, (1, 0), HALF, True,
                          "FORCED_5050_GUESS", ((17, 0), (17, 1)), "NOT_COMPUTED_CANDIDATE_LIMIT",
                          "FORCED_PAIR_CELLS", 10, "COST_READING",
                          (((17, 1), None, 126005), ((17, 0), None, 144891)), 10, (), 0, None, None,
                          "INDEPENDENT_PROVEN", 32))
        for item in (single, five):  # the record survives the file form
            self.assertEqual(record.decode_record(record.encode_record(item["record"])), item["record"])

    def test_x04_the_terminal_observation_and_the_layout_are_never_read(self):
        # PublicPort raises if a terminal observation is read through the public channel.
        port = PublicPort(raw_engine(BOARDS["G2"]))
        with patch.object(recorded, "run_s3d3_stage2", wraps=recorded.run_s3d3_stage2) as runner:
            r = recorded.run_recorded(port, allow_guess=True, table=self.table)
        self.assertEqual(runner.call_args.kwargs, {"allow_guess": True, "table": self.table,
                                                   "capture_effects": False})
        self.assertEqual((r.run.status, r.record.final_status, self.loss(r.record)[1], port.inputs),
                         (LOST, "LOST", "FORCED_5050", [O(0, 0), O(0, 4), O(1, 4), O(1, 5), O(1, 3)]))
        step = max(i for i, event in enumerate(port.events) if event[0] == "step")
        self.assertEqual(port.events[step + 1:], [("status", LOST)])  # recording read nothing afterwards
        self.assertTrue(all(t.action.public_effect is None for t in r.run.traces))
        # Recording from the finished result touches neither the Engine nor a layout.
        events = len(port.events)
        again = recorded.record_of_run(r.run, 2, 8, 1, True)
        record.describe(again)
        record.encode_record(again)
        self.assertEqual((again, len(port.events)), (r.record, events))
        text = record.encode_record(again).decode("utf-8")
        self.assertNotIn("layout", text)
        self.assertEqual(record.decode_record(text.encode("utf-8")).inputs[-1].evidence.public_state.mines, ())

    def test_x06_the_saved_evidence_reads_back_with_the_same_values(self):
        folder = new_folder()
        for name, allow in (("G6", True), ("G8", True), ("R11L", True), ("F1", True), ("G1", True), ("G5", False)):
            with self.subTest(board=name, allow_guess=allow):
                path = os.path.join(folder, f"{name}_{'on' if allow else 'off'}.json")
                engine, guard, r = self.run_recorded(name, allow_guess=allow, save_path=path)
                self.assertEqual((r.save.state, r.save.path, r.save.code, os.path.getsize(path)),
                                 ("SAVED", path, None, r.save.bytes))
                loaded = record.load_record(path)
                self.assertEqual((loaded, record.describe(loaded, record.LOADED_FROM_FILE)[:-1]),
                                 (r.record, record.describe(r.record, r.save)[:-1]))
                self.assertEqual((record.describe(r.record, r.save)[-1],
                                  record.describe(loaded, record.LOADED_FROM_FILE)[-1]),
                                 ("저장 상태: 실험 기록 파일로 저장됨.", "저장 상태: 실험 기록 파일에서 읽음."))
        g6 = record.load_record(os.path.join(folder, "G6_on.json"))
        evidence = g6.inputs[-1].evidence
        self.assertEqual((evidence.risk, evidence.original_risk, evidence.target_s_c, evidence.original_s_v,
                          [(v.cell, v.s_v, v.s_c, v.flood_worlds, v.calls) for v in evidence.values]),
                         (HALF, Fraction(1, 4), HALF, None,
                          [((3, 0), HALF, HALF, 0, 4), ((3, 1), HALF, HALF, 0, 4)]))
        off = record.load_record(os.path.join(folder, "G5_off.json"))
        self.assertEqual((off.final_status, off.stop_reason, len(off.inputs), off.blocked.input_index,
                          (off.blocked.x, off.blocked.y), off.blocked.evidence.kind, self.loss(off)),
                         ("PLAYING", "GUESS_BLOCKED", 1, 1, (3, 0), "FORCED_5050",
                          ("NOT_APPLICABLE_NOT_FINISHED", None, None, None)))
        # A failed save leaves the run result and the record as they are and re-runs nothing.
        path = os.path.join(folder, "G6_on.json")
        with patch.object(recorded, "run_s3d3_stage2", wraps=recorded.run_s3d3_stage2) as runner:
            engine, guard, r = self.run_recorded("G6", save_path=path)
        self.assertEqual((runner.call_count, r.save.state, r.save.code, r.run.status, r.record.final_status,
                          r.record, engine.steps),
                         (1, "SAVE_FAILED", "PATH_EXISTS", LOST, "LOST", g6, 2))
        self.assertEqual(record.describe(r.record, r.save)[0], "기본 결과: LOST")

    def test_t14_a_loss_on_a_certain_input_is_an_integrity_problem_not_a_guess_loss(self):
        engine, guard = build(BOARDS["G1"])
        liar = LyingEngine(guard)
        r = recorded.run_recorded(liar, allow_guess=True, table=self.table)
        self.assertEqual((r.run.status, r.run.moves, engine.steps, engine.status),
                         (LOST, (O(0, 0), O(0, 4)), 2, PLAYING))  # the real game was still going on
        self.assertEqual(([i.decision for i in r.record.inputs], r.record.final_status, self.loss(r.record)),
                         (["INITIAL_OPEN", "CERTAIN"], "LOST",
                          ("INTEGRITY_PROBLEM", None, "LOST_ON_CERTAIN_INPUT", 1)))
        self.assertEqual(record.describe(r.record)[:2], (
            "기본 결과: LOST",
            "무결성 문제: 추측이 아닌 입력 OPEN (0,4)에서 LOST가 기록됐다. 추측 패배로 분류하지 않는다. 기본 결과 LOST는 그대로다."))
        counts = record.tally([r.record])
        self.assertEqual((counts["LOST"], counts["integrity_problems"], sum(counts["loss_kinds"].values())),
                         (1, 1, 0))
        self.assertEqual(record.decode_record(record.encode_record(r.record)), r.record)

    def test_s10_recording_saving_and_loading_add_no_probability_call_and_no_engine_use(self):
        folder = new_folder()
        engine, guard, r = self.run_recorded("G8")
        tie = self.segment(E_TIE_L)
        path = os.path.join(folder, "G8.json")
        with patch.object(policy, "_kernel", side_effect=AssertionError("hypothetical call")), \
                patch("simple_probability.calculate_probabilities", side_effect=AssertionError("kernel")), \
                patch.object(KLocalSession, "analyze_decision", side_effect=AssertionError("inference")), \
                patch.object(MinesweeperEngine, "step", side_effect=AssertionError("engine input")), \
                patch.object(MinesweeperEngine, "get_observation", side_effect=AssertionError("observation")), \
                patch.object(policy, "select_singleton_policy", side_effect=AssertionError("selection")):
            again = recorded.record_of_run(r.run, 5, 1, 2, True)
            segment = recorded.record_of_segment(3, 3, 4, (O(1, 0), O(2, 0)), (
                recorded.SegmentInput(tie["choice"].move, tie["status"], tie["choice"]),))
            self.assertEqual((again, segment), (r.record, tie["record"]))
            record.validate_record(again)
            self.assertEqual(record.classify(again.inputs, again.final_status), again.loss)
            outcome = record.save_record(again, path)
            loaded = record.load_record(path)
            record.describe(loaded, record.LOADED_FROM_FILE)
            record.tally([again, segment, loaded])
        self.assertEqual((outcome.state, loaded), ("SAVED", r.record))

    def test_s11_a_loaded_record_authorises_no_input(self):
        folder = new_folder()
        tie = self.segment(E_TIE)  # the surviving layout: the game is still PLAYING
        path = os.path.join(folder, "tie.json")
        self.assertEqual(record.save_record(tie["record"], path).state, "SAVED")
        loaded = record.load_record(path)
        observation = public(tie["guard"])
        session = KLocalSession(3, 3, 4)
        decision = session.analyze_decision(observation, status=PLAYING)
        for choice in (loaded, loaded.inputs[-1], loaded.inputs[-1].evidence):
            with self.assertRaises(KExecutionError) as caught:
                d3runner.validate_lookahead_execution(
                    observation, O(1, 2), status=PLAYING, num_mines=4, cursor=(2, 2), current_mines=session.M,
                    decision=decision, choice=choice, table=self.table)
            self.assertEqual(caught.exception.code, "LOOKAHEAD_EXECUTION")
        self.assertEqual(tie["engine"].steps, 3)  # nothing was sent because of the record

    def test_a01_the_base_result_tally_is_the_same_with_and_without_the_classification(self):
        runs = [(name, True) for name in GUESS_ALLOWED] + [(name, False) for name in GUESS_OFF]
        records = [self.run_recorded(name, allow)[2].record for name, allow in runs]
        plain = [self.run_plain(name, allow)[2] for name, allow in runs]
        counts = record.tally(records)
        self.assertEqual({status: counts[status] for status in ("WON", "LOST", "PLAYING")},
                         {status.name: sum(1 for r in plain if r.status is status) for status in (WON, LOST, PLAYING)})
        self.assertEqual(counts, {
            "WON": 2, "LOST": 6, "PLAYING": 3, "executed_inputs": 30, "blocked_proposals": 3,
            "loss_kinds": {"FORCED_5050": 3, "TIE_LOOKAHEAD": 0, "MIN_RISK": 2, "UNCLASSIFIED": 1},
            "integrity_problems": 0})
        self.assertEqual(counts["executed_inputs"], sum(len(r.moves) for r in plain))
        segments = [self.segment(state)["record"] for state in (E_TIE_L, E_TIE, E_SINGLE_L, E_FIVE_PAIRS_L)]
        self.assertEqual(record.tally(records + segments), {
            "WON": 2, "LOST": 9, "PLAYING": 4, "executed_inputs": 34, "blocked_proposals": 3,
            "loss_kinds": {"FORCED_5050": 4, "TIE_LOOKAHEAD": 1, "MIN_RISK": 3, "UNCLASSIFIED": 1},
            "integrity_problems": 0})

    def test_b01_recording_changes_neither_inputs_results_nor_probability_calls(self):
        runs = [(name, True) for name in GUESS_ALLOWED] + [(name, False) for name in GUESS_OFF]
        for name, allow in runs:
            with self.subTest(board=name, allow_guess=allow):
                with kernel_total() as kernel, counting() as calls:
                    engine_a, guard_a, plain = self.run_plain(name, allow)
                    plain_calls, plain_kernel = calls.count, kernel.call_count
                with kernel_total() as kernel, counting() as calls:
                    engine_b, guard_b, r = self.run_recorded(name, allow)
                    recorded_calls, recorded_kernel = calls.count, kernel.call_count
                self.assertEqual((r.run.moves, r.run.status, r.run.stop_reason, engine_b.steps, engine_b.status),
                                 (plain.moves, plain.status, plain.stop_reason, engine_a.steps, engine_a.status))
                self.assertEqual((recorded_calls, recorded_kernel, r.run.added_hypothetical_calls),
                                 (plain_calls, plain_kernel, plain.added_hypothetical_calls))
                self.assertEqual(plain_calls, D3_CALLS[(name, allow)])
                self.assertEqual([None if t.choice is None else replace(t.choice, inner=None) for t in r.run.traces],
                                 [None if t.choice is None else replace(t.choice, inner=None) for t in plain.traces])
                self.assertEqual((r.run.blocked is None, plain.blocked is None), (allow, allow))
                if not allow:
                    self.assertEqual((r.run.blocked.choice.move, r.run.blocked.input_index, r.record.blocked.x,
                                      r.record.blocked.y),
                                     (plain.blocked.choice.move, plain.blocked.input_index,
                                      plain.blocked.choice.move.x, plain.blocked.choice.move.y))
                self.assertEqual([(i.action, i.x, i.y) for i in r.record.inputs],
                                 [(m.action.name, m.x, m.y) for m in plain.moves])
                self.assertEqual(r.record.final_status, plain.status.name)


class TieLossConnectionTests(RunCase):
    """A real KLocalSession decision whose TIE_LOOKAHEAD input loses, through to the record file."""

    def test_k01_a_real_tie_lookahead_loss_is_classified_saved_and_read_back(self):
        folder = new_folder()
        with kernel_total() as kernel, counting() as calls:
            tie = self.segment(E_TIE_L)
            added, total = calls.count, kernel.call_count
        self.assertEqual(tie["observation"], ((H, 3, 1), (H, H, H), (H, H, H)))
        decision, inner, choice, common = tie["decision"], tie["inner"], tie["choice"], tie["common"]
        self.assertEqual((decision.continuation, decision.guess_target, tie["session"].M, added),
                         ("EXACT_GUESS", (0, 2), frozenset({(0, 0), (0, 1)}), 12))
        self.assertEqual((inner.selected.move, choice.selection_reason, choice.original_target, choice.target,
                          choice.move, choice.category),
                         (O(0, 2), "TIE_LOOKAHEAD", (0, 2), (2, 2), O(2, 2), "TIE_LOOKAHEAD_GUESS"))
        with self.assertRaises(KExecutionError) as caught:  # the old validator does not authorise it
            validate_k_p0_execution(tie["observation"], choice.move, selection=inner.selected, **common)
        self.assertEqual(caught.exception.code, "SELECTED_INPUT")
        # The evidence fixed before the input is exactly the hand-written one of the plan.
        self.assertEqual(tie["before"], tie_evidence())
        self.assertEqual((tie["status"], tie["engine"].status, tie["engine"].steps,
                          tie["guard"].engine_inputs_reached), (LOST, LOST, 3, 3))
        outcome = tie["record"]
        self.assertEqual((outcome.record_scope, outcome.prefix_inputs, outcome.final_status, outcome.stop_reason,
                          self.loss(outcome), outcome.inputs[-1].evidence),
                         (record.SEGMENT, (("OPEN", 1, 0), ("OPEN", 2, 0)), "LOST", "TERMINAL",
                          ("APPLIES", "TIE_LOOKAHEAD", "PRE_INPUT_EVIDENCE", 2), tie["before"]))
        self.assertEqual([(i.index, i.action, i.x, i.y, i.status_after, i.decision) for i in outcome.inputs],
                         [(2, "OPEN", 2, 2, "LOST", "GUESS")])
        path = os.path.join(folder, "E_TIE_L.json")
        with kernel_total() as kernel, counting() as calls:
            saved = record.save_record(outcome, path)
            loaded = record.load_record(path)
            lines = record.describe(loaded, record.LOADED_FROM_FILE)
            self.assertEqual((calls.count, kernel.call_count), (0, 0))
        self.assertEqual((saved.state, loaded, total > added), ("SAVED", outcome, True))
        self.assertEqual(lines, (
            "기본 결과: LOST",
            "패배 보조 분류: 최소 위험 동률 집합에서 전방 비교로 고른 추측 (TIE_LOOKAHEAD). 입력 OPEN (2,2), 입력 전 위험 1/3.",
            "원 대상 (0,2)의 위험 1/3. 대상의 S_c 2/3, 원 대상의 S_v 1/2.",
            "S_c와 S_v는 K-LC1 기준 수순의 다음 입력에 관한 값이다. 이 정책의 실제 생존확률이나 판 전체 승률이 아니다.",
            "전방 계산: 계산함 (가정 계산 12회).",
            "저장 상태: 실험 기록 파일에서 읽음."))
        evidence = loaded.inputs[-1].evidence
        self.assertEqual((evidence.target, evidence.risk, evidence.original_target, evidence.original_risk,
                          evidence.target_s_c, evidence.original_s_v,
                          [(v.cell, v.s_v, v.s_c, v.calls) for v in evidence.values]),
                         ((2, 2), Fraction(1, 3), (0, 2), Fraction(1, 3), Fraction(2, 3), HALF,
                          [((0, 2), HALF, HALF, 3), ((1, 2), Fraction(1, 3), Fraction(1, 3), 5),
                           ((2, 2), Fraction(2, 3), Fraction(2, 3), 4)]))

    def test_k02_the_same_pre_input_evidence_on_the_layout_that_survives(self):
        lost, alive = self.segment(E_TIE_L), self.segment(E_TIE)
        self.assertEqual((alive["observation"], alive["before"]), (lost["observation"], lost["before"]))
        self.assertEqual(alive["before"], tie_evidence())
        self.assertEqual((alive["status"], public(alive["guard"])[2][2], alive["engine"].steps),
                         (PLAYING, 1, 3))
        outcome = alive["record"]
        self.assertEqual((outcome.final_status, outcome.stop_reason, self.loss(outcome)),
                         ("PLAYING", "SEGMENT_END", ("NOT_APPLICABLE_NOT_FINISHED", None, None, None)))
        # Only the status after the input and what follows from it differ.
        self.assertEqual(replace(outcome, inputs=lost["record"].inputs, final_status="LOST",
                                 stop_reason="TERMINAL", loss=lost["record"].loss), lost["record"])
        self.assertEqual(record.describe(outcome)[:2],
                         ("기본 결과: PLAYING (판이 끝나지 않았다)", "패배 보조 분류: 해당 없음 (판이 끝나지 않았다)."))


class VocabularyTests(RunCase):
    def test_v01_the_record_vocabulary_agrees_with_the_unchanged_policy(self):
        self.assertEqual((record.SELECTION_SCOPE, record.POLICY_ID, record.POLICY_DEFINITION,
                          record.CELL_LIMIT, record.CALL_LIMIT),
                         (policy.IMPLEMENTATION_SCOPE, policy.CANDIDATE_ID, policy.CANDIDATE_DEFINITION,
                          policy.CELL_LIMIT, policy.CALL_LIMIT))
        self.assertEqual(record.REASON_OF_KIND, {"FORCED_5050": policy.FORCED_FIRST,
                                                 "TIE_LOOKAHEAD": policy.TIE_LOOKAHEAD, "MIN_RISK": policy.KEPT})
        self.assertEqual(record.CHANGED_CATEGORY, {"FORCED_5050": policy.FORCED_CATEGORY,
                                                   "TIE_LOOKAHEAD": policy.TIE_CATEGORY})
        self.assertEqual((record.KEPT_CATEGORY, record.LOOKAHEAD_STATUSES, (record.PAIR_CELLS, record.TIES),
                          (record.RANK_NONE, record.RANK_S, record.RANK_COST), record.Q_KINDS,
                          record.OUTSIDE_NOT_COMPUTED),
                         (policy.KEPT_GUESS_CATEGORY,
                          (policy.STATUS_COMPUTED, policy.STATUS_SINGLE, policy.STATUS_LIMIT),
                          (policy.SET_PAIR_CELLS, policy.SET_TIES),
                          (policy.RANK_NONE, policy.RANK_S, policy.RANK_COST),
                          (policy.IMPOSSIBLE, policy.GAME_ENDS, policy.SAFE_CELL_EXISTS, policy.MIN_RISK_GUESS),
                          policy.OUTSIDE_NOT_COMPUTED))
        self.assertEqual(((record.VERDICT_FORCED, record.VERDICT_APPARENT), record.CELL_STATES,
                          (record.HIDDEN, record.FLAGGED), record.STOP_REASONS[:2], record.STATUSES),
                         ((stage1.FORCED, stage1.APPARENT),
                          (stage1.PROVEN_MINE, stage1.REVEALED_NUMBER, stage1.UNRESOLVED_HIDDEN),
                          (int(CellState.HIDDEN), int(CellState.FLAGGED)), d3runner.STOP_REASONS,
                          (PLAYING.name, WON.name, LOST.name)))
        self.assertEqual(recorded.SegmentInput(O(0, 0), PLAYING, None).status_after, PLAYING)
        self.assertEqual(sorted(a.name for a in Action if a.name in record.ACTIONS), ["CHORD", "FLAG", "OPEN"])


if __name__ == "__main__":
    unittest.main()
