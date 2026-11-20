"""S3D3-A stage 3 (GUESS_OUTCOME_RECORD_V1): record model, classification, exact numbers, files.

Everything here is DECLARED TEST MATERIAL or synthetic: the evidence objects are
written by hand (values fixed beforehand in VERIFICATION_PLAN.json) and no
Engine, session, policy or probability code is imported or run. What a real
decision produces is compared with these hand-written objects in
tests/test_program_d3_recorded_runner.py. Damaged, truncated and inconsistent
records are synthetic and exist only to check that they are refused.

Files written by these tests go to a new folder under the process's temporary
directory and are left there; nothing is deleted.
"""

import ast
from dataclasses import replace
from fractions import Fraction as F
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from experiments import program_d3_guess_record as R


H = R.HIDDEN
IMP, END, SAFE, MIN = R.IMPOSSIBLE, R.GAME_ENDS, R.SAFE_CELL_EXISTS, R.MIN_RISK_GUESS
MINE, NUMBER, OPENABLE = "PROVEN_MINE", "REVEALED_NUMBER", "UNRESOLVED_HIDDEN"
BIG = 2 ** 200


def grid(*rows):
    return tuple(tuple(H if v == "H" else int(v) for v in row.split()) for row in rows)


def value(cell, z_g, z, m, u, rows, z_f, s_v, s_c):
    outcomes = tuple(R.NumberOutcome(k, worlds, kind, None if q is None else F(q), minimum, safe, flood)
                     for k, worlds, kind, q, minimum, safe, flood in rows)
    return R.CandidateValue(cell, z_g, z, m, u, len(rows), outcomes, z_f, F(s_v), F(s_c))


def tie_evidence():
    """D_TIE: the E_TIE public state (3x3, `H 3 1 / H H H / H H H`, 4 mines), target (2,2)."""
    return R.GuessEvidence(
        kind="TIE_LOOKAHEAD", selection_reason="TIE_LOOKAHEAD", target=(2, 2), risk=F(1, 3),
        risk_kind="COMPUTED_EXACT_MINIMUM", original_target=(0, 2), original_risk=F(1, 3),
        is_minimum_risk=True, target_changed=True, pair=None, category="TIE_LOOKAHEAD_GUESS",
        k_lc1_move=("OPEN", 0, 2), lookahead_status="COMPUTED", lookahead_set="MIN_RISK_TIES",
        rank_basis="NOT_APPLICABLE", lookahead_cells=((0, 2), (1, 2), (2, 2)),
        outside_set_lookahead="NOT_COMPUTED", planned_calls=12, actual_calls=12, target_s_c=F(2, 3),
        original_s_v=F(1, 2),
        values=(
            value((0, 2), 2, 6, 1, 2, [(1, 1, SAFE, 1, 0, 2, False), (2, 2, MIN, "1/2", 1, 0, False),
                                       (3, 1, SAFE, 1, 0, 2, False)], 0, "1/2", "1/2"),
            value((1, 2), 2, 6, 1, 4, [(1, 0, IMP, None, None, 0, False), (2, 0, IMP, None, None, 0, False),
                                       (3, 4, MIN, "1/2", 2, 0, False), (4, 0, IMP, None, None, 0, False),
                                       (5, 0, IMP, None, None, 0, False)], 0, "1/3", "1/3"),
            value((2, 2), 2, 6, 0, 3, [(0, 0, IMP, None, None, 0, True), (1, 2, SAFE, 1, 0, 1, False),
                                       (2, 2, SAFE, 1, 0, 1, False), (3, 0, IMP, None, None, 0, False)],
                  0, "2/3", "2/3")),
        ranking=(),
        pair_proofs=(R.PairBasis((1, 1), (2, 1), "APPARENT_5050", ("F3",),
                                 (("CLUE", (1, 0)), ("CLUE", (2, 0))),
                                 (((0, 0), MINE), ((0, 1), MINE), ((0, 2), OPENABLE)), (3, 3), 6),),
        independence="NOT_APPLICABLE",
        public_state=R.PublicState(grid("H 3 1", "H H H", "H H H"), 4, ((0, 0), (0, 1)), (2, 0), 6,
                                   (((1, 1), 3), ((2, 1), 3), ((0, 2), 2), ((1, 2), 2), ((2, 2), 2))))


LAST_PAIR_ROWS = [(0, 0, IMP, None, None, 0, True), (1, 1, END, 1, 1, 0, False)]


def forced_evidence():
    """D_FORCED: the last decision of G1 / G2 (2x8), pair (0,3),(1,3), target (1,3) from cursor (1,5)."""
    return R.GuessEvidence(
        kind="FORCED_5050", selection_reason="FORCED_5050_FIRST", target=(1, 3), risk=F(1, 2),
        risk_kind="PROVEN_BY_PAIR_SYMMETRY", original_target=(0, 3), original_risk=F(1, 2),
        is_minimum_risk=True, target_changed=True, pair=((0, 3), (1, 3)), category="FORCED_5050_GUESS",
        k_lc1_move=("OPEN", 0, 3), lookahead_status="COMPUTED", lookahead_set="FORCED_PAIR_CELLS",
        rank_basis="S_COST_READING", lookahead_cells=((0, 3), (1, 3)), outside_set_lookahead="NOT_COMPUTED",
        planned_calls=4, actual_calls=4, target_s_c=F(1, 2), original_s_v=F(1, 2),
        values=(value((0, 3), 1, 2, 0, 1, LAST_PAIR_ROWS, 0, "1/2", "1/2"),
                value((1, 3), 1, 2, 0, 1, LAST_PAIR_ROWS, 0, "1/2", "1/2")),
        ranking=(((1, 3), F(1, 2), 180604), ((0, 3), F(1, 2), 193056)),
        pair_proofs=(R.PairBasis((0, 3), (1, 3), "FORCED_5050", (),
                                 (("CLUE", (0, 2)), ("CLUE", (1, 2)), ("CLUE", (0, 4)), ("CLUE", (1, 4)),
                                  ("LAST_MINE", None)), (), (1, 1), 2),),
        independence="NOT_APPLICABLE",
        public_state=R.PublicState(grid("0 0", "0 0", "1 1", "H H", "1 1", "0 0", "0 0", "0 0"), 1, (),
                                   (1, 5), 2, (((0, 3), 1), ((1, 3), 1))))


def min_evidence():
    """D_MIN: the first guess decision of G7 / G8 (5x1, `1 H H H H`, 2 mines), target (2,0) kept."""
    return R.GuessEvidence(
        kind="MIN_RISK", selection_reason="K_LC1_GUESS_KEPT", target=(2, 0), risk=F(1, 3),
        risk_kind="COMPUTED_EXACT_MINIMUM", original_target=(2, 0), original_risk=F(1, 3),
        is_minimum_risk=True, target_changed=False, pair=None, category="EXACT_MINIMUM_RISK_GUESS",
        k_lc1_move=("OPEN", 2, 0), lookahead_status="COMPUTED", lookahead_set="MIN_RISK_TIES",
        rank_basis="NOT_APPLICABLE", lookahead_cells=((2, 0), (3, 0), (4, 0)),
        outside_set_lookahead="NOT_COMPUTED", planned_calls=7, actual_calls=7, target_s_c=F(2, 3),
        original_s_v=F(2, 3),
        values=(
            value((2, 0), 1, 3, 1, 1, [(1, 1, SAFE, 1, 0, 1, False), (2, 1, SAFE, 1, 0, 1, False)],
                  0, "2/3", "2/3"),
            value((3, 0), 1, 3, 0, 2, [(0, 0, IMP, None, None, 0, True), (1, 2, MIN, "1/2", 1, 0, False),
                                       (2, 0, IMP, None, None, 0, False)], 0, "1/3", "1/3"),
            value((4, 0), 1, 3, 0, 1, [(0, 1, SAFE, 1, 0, 1, True), (1, 1, SAFE, 1, 0, 1, False)],
                  1, "2/3", "1/3")),
        ranking=(), pair_proofs=(), independence="NOT_APPLICABLE",
        public_state=R.PublicState(grid("1 H H H H"), 2, ((1, 0),), (0, 0), 3,
                                   (((2, 0), 1), ((3, 0), 1), ((4, 0), 1))))


def limit_evidence():
    """11x1, `1 H x10`, 2 mines: nine minimum-risk ties, so nothing is computed."""
    cells = tuple((x, 0) for x in range(2, 11))
    return R.GuessEvidence(
        kind="MIN_RISK", selection_reason="K_LC1_GUESS_KEPT", target=(2, 0), risk=F(1, 9),
        risk_kind="COMPUTED_EXACT_MINIMUM", original_target=(2, 0), original_risk=F(1, 9),
        is_minimum_risk=True, target_changed=False, pair=None, category="EXACT_MINIMUM_RISK_GUESS",
        k_lc1_move=("OPEN", 2, 0), lookahead_status="NOT_COMPUTED_CANDIDATE_LIMIT",
        lookahead_set="MIN_RISK_TIES", rank_basis="NOT_APPLICABLE", lookahead_cells=cells,
        outside_set_lookahead="NOT_COMPUTED", planned_calls=0, actual_calls=0, target_s_c=None,
        original_s_v=None, values=(), ranking=(), pair_proofs=(), independence="NOT_APPLICABLE",
        public_state=R.PublicState(grid("1 H H H H H H H H H H"), 2, ((1, 0),), (0, 0), 9,
                                   tuple((cell, 1) for cell in cells)))


def single_evidence():
    """7x1, `H H H 1 H 1 H`, 3 mines: one minimum-risk cell, so no look-ahead is needed."""
    return R.GuessEvidence(
        kind="MIN_RISK", selection_reason="K_LC1_GUESS_KEPT", target=(4, 0), risk=F(1, 3),
        risk_kind="COMPUTED_EXACT_MINIMUM", original_target=(4, 0), original_risk=F(1, 3),
        is_minimum_risk=True, target_changed=False, pair=None, category="EXACT_MINIMUM_RISK_GUESS",
        k_lc1_move=("OPEN", 4, 0), lookahead_status="NOT_REQUIRED_SINGLE", lookahead_set="MIN_RISK_TIES",
        rank_basis="NOT_APPLICABLE", lookahead_cells=((4, 0),), outside_set_lookahead="NOT_COMPUTED",
        planned_calls=0, actual_calls=0, target_s_c=None, original_s_v=None, values=(), ranking=(),
        pair_proofs=(
            R.PairBasis((2, 0), (4, 0), "APPARENT_5050", ("F3",), (("CLUE", (3, 0)),),
                        (((1, 0), OPENABLE), ((5, 0), NUMBER)), (2, 1), 3),
            R.PairBasis((4, 0), (6, 0), "APPARENT_5050", ("F3",), (("CLUE", (5, 0)),),
                        (((3, 0), NUMBER),), (1, 2), 3)),
        independence="NOT_APPLICABLE",
        public_state=R.PublicState(grid("H H H 1 H 1 H"), 3, (), (5, 0), 3,
                                   (((0, 0), 2), ((1, 0), 2), ((2, 0), 2), ((4, 0), 1), ((6, 0), 2))))


def kept_forced_evidence():
    """The last decision of G3 / G4 (8x2): the forced-pair target equals the K-LC1 target."""
    return R.GuessEvidence(
        kind="FORCED_5050", selection_reason="FORCED_5050_FIRST", target=(3, 0), risk=F(1, 2),
        risk_kind="PROVEN_BY_PAIR_SYMMETRY", original_target=(3, 0), original_risk=F(1, 2),
        is_minimum_risk=True, target_changed=False, pair=((3, 0), (3, 1)),
        category="EXACT_MINIMUM_RISK_GUESS", k_lc1_move=("OPEN", 3, 0), lookahead_status="COMPUTED",
        lookahead_set="FORCED_PAIR_CELLS", rank_basis="S_COST_READING", lookahead_cells=((3, 0), (3, 1)),
        outside_set_lookahead="NOT_COMPUTED", planned_calls=4, actual_calls=4, target_s_c=F(1, 2),
        original_s_v=F(1, 2),
        values=(value((3, 0), 1, 2, 0, 1, LAST_PAIR_ROWS, 0, "1/2", "1/2"),
                value((3, 1), 1, 2, 0, 1, LAST_PAIR_ROWS, 0, "1/2", "1/2")),
        ranking=(((3, 0), F(1, 2), 180604), ((3, 1), F(1, 2), 193056)),
        pair_proofs=(R.PairBasis((3, 0), (3, 1), "FORCED_5050", (),
                                 (("CLUE", (2, 0)), ("CLUE", (4, 0)), ("CLUE", (2, 1)), ("CLUE", (4, 1)),
                                  ("LAST_MINE", None)), (), (1, 1), 2),),
        independence="NOT_APPLICABLE",
        public_state=R.PublicState(grid("0 0 1 H 1 0 0 0", "0 0 1 H 1 0 0 0"), 1, (), (5, 0), 2,
                                   (((3, 0), 1), ((3, 1), 1))))


PAIR_OF_FOUR_ROWS = [(0, 0, IMP, None, None, 0, True), (1, 2, SAFE, 1, 0, 2, False),
                     (2, 2, SAFE, 1, 0, 2, False), (3, 0, IMP, None, None, 0, False)]


def split_risk_evidence():
    """The first guess decision of G5 / G6 (6x2): pair risk 1/2 although the K-LC1 target has 1/4."""
    return R.GuessEvidence(
        kind="FORCED_5050", selection_reason="FORCED_5050_FIRST", target=(3, 0), risk=F(1, 2),
        risk_kind="PROVEN_BY_PAIR_SYMMETRY", original_target=(4, 0), original_risk=F(1, 4),
        is_minimum_risk=False, target_changed=True, pair=((3, 0), (3, 1)), category="FORCED_5050_GUESS",
        k_lc1_move=("OPEN", 4, 0), lookahead_status="COMPUTED", lookahead_set="FORCED_PAIR_CELLS",
        rank_basis="S_COST_READING", lookahead_cells=((3, 0), (3, 1)), outside_set_lookahead="NOT_COMPUTED",
        planned_calls=8, actual_calls=8, target_s_c=F(1, 2), original_s_v=None,
        values=(value((3, 0), 4, 8, 0, 3, PAIR_OF_FOUR_ROWS, 0, "1/2", "1/2"),
                value((3, 1), 4, 8, 0, 3, PAIR_OF_FOUR_ROWS, 0, "1/2", "1/2")),
        ranking=(((3, 0), F(1, 2), 227896), ((3, 1), F(1, 2), 234434)),
        pair_proofs=(R.PairBasis((3, 0), (3, 1), "FORCED_5050", (), (("CLUE", (2, 0)), ("CLUE", (2, 1))), (),
                                 (4, 4), 8),),
        independence="NOT_APPLICABLE",
        public_state=R.PublicState(grid("0 0 1 H H H", "0 0 1 H H H"), 2, (), (0, 0), 8,
                                   (((3, 0), 4), ((4, 0), 2), ((5, 0), 2), ((3, 1), 4), ((4, 1), 2),
                                    ((5, 1), 2))))


FIVE_PAIR_COLUMNS = (1, 5, 9, 13, 17)
FIVE_PAIR_PREFIX = (("OPEN", 3, 0), ("OPEN", 7, 0), ("OPEN", 11, 0), ("OPEN", 15, 0), ("OPEN", 0, 0),
                    ("OPEN", 0, 1), ("OPEN", 18, 0), ("OPEN", 18, 1))


def five_pairs_evidence():
    """19x2 with five vertical forced pairs: ten pair cells exceed the limit, nothing is computed.
    The costs are declared numbers (distance from the cursor), not the Model C table."""
    row = " ".join("H" if x % 4 == 1 else "0" if x % 4 == 3 else "1" for x in range(19))
    cells = tuple((x, y) for y in (0, 1) for x in FIVE_PAIR_COLUMNS)
    rows = sorted(((cell, None, 1000 * abs(cell[0] - 18) + 100 * abs(cell[1] - 1) + 1) for cell in cells),
                  key=lambda item: (item[2], item[0][1], item[0][0]))
    proofs = tuple(R.PairBasis((x, 0), (x, 1), "FORCED_5050", (),
                               (("CLUE", (x - 1, 0)), ("CLUE", (x + 1, 0)), ("CLUE", (x - 1, 1)),
                                ("CLUE", (x + 1, 1))), (), (16, 16), 32) for x in FIVE_PAIR_COLUMNS)
    return R.GuessEvidence(
        kind="FORCED_5050", selection_reason="FORCED_5050_FIRST", target=(17, 1), risk=F(1, 2),
        risk_kind="PROVEN_BY_PAIR_SYMMETRY", original_target=(1, 0), original_risk=F(1, 2),
        is_minimum_risk=True, target_changed=True, pair=((17, 0), (17, 1)), category="FORCED_5050_GUESS",
        k_lc1_move=("OPEN", 1, 0), lookahead_status="NOT_COMPUTED_CANDIDATE_LIMIT",
        lookahead_set="FORCED_PAIR_CELLS", rank_basis="COST_READING", lookahead_cells=cells,
        outside_set_lookahead="NOT_COMPUTED", planned_calls=0, actual_calls=0, target_s_c=None,
        original_s_v=None, values=(), ranking=tuple(rows), pair_proofs=proofs,
        independence="INDEPENDENT_PROVEN",
        public_state=R.PublicState(grid(row, row), 5, (), (18, 1), 32, tuple((cell, 16) for cell in cells)))


def inp(index, x, y, status="PLAYING", decision=R.CERTAIN, evidence=None, action="OPEN"):
    return R.RecordedInput(index, action, x, y, status, decision, evidence)


def full(width, height, mines, inputs, allow_guess=True, blocked=None, stop=None):
    final = inputs[-1].status_after
    return R.make_record(
        record_scope=R.FULL_RUN, width=width, height=height, num_mines=mines, allow_guess=allow_guess,
        prefix_inputs=(), inputs=tuple(inputs), blocked=blocked, final_status=final,
        stop_reason=stop or (R.TERMINAL if final != "PLAYING" else R.GUESS_BLOCKED))


def segment(width, height, mines, prefix, inputs):
    final = inputs[-1].status_after
    return R.make_record(
        record_scope=R.SEGMENT, width=width, height=height, num_mines=mines, allow_guess=True,
        prefix_inputs=tuple(prefix), inputs=tuple(inputs), blocked=None, final_status=final,
        stop_reason=R.TERMINAL if final != "PLAYING" else R.SEGMENT_END)


G1_HEAD = (inp(0, 0, 0, decision=R.INITIAL_OPEN), inp(1, 0, 4), inp(2, 1, 4), inp(3, 1, 5))
TIE_PREFIX = (("OPEN", 1, 0), ("OPEN", 2, 0))


def record_forced(status="LOST"):       # G2 (LOST) or G1 (WON), declared
    return full(2, 8, 1, G1_HEAD + (inp(4, 1, 3, status, R.GUESS, forced_evidence()),))


def record_tie(status="LOST"):          # E_TIE_L (LOST) or E_TIE (PLAYING), declared
    return segment(3, 3, 4, TIE_PREFIX, (inp(2, 2, 2, status, R.GUESS, tie_evidence()),))


def record_min():                       # G8, declared
    return full(5, 1, 2, (inp(0, 0, 0, decision=R.INITIAL_OPEN), inp(1, 2, 0, "LOST", R.GUESS, min_evidence())))


def record_limit():                     # R11L, declared
    return full(11, 1, 2, (inp(0, 0, 0, decision=R.INITIAL_OPEN),
                           inp(1, 2, 0, "LOST", R.GUESS, limit_evidence())))


def record_single():                    # E_SINGLE_L, declared
    return segment(7, 1, 3, (("OPEN", 3, 0), ("OPEN", 5, 0)),
                   (inp(2, 4, 0, "LOST", R.GUESS, single_evidence()),))


def record_kept_forced():               # G4, declared
    return full(8, 2, 1, (inp(0, 0, 0, decision=R.INITIAL_OPEN), inp(1, 4, 0), inp(2, 5, 0),
                          inp(3, 3, 0, "LOST", R.GUESS, kept_forced_evidence())))


def record_split_risk():                # G6, declared
    return full(6, 2, 2, (inp(0, 0, 0, decision=R.INITIAL_OPEN),
                          inp(1, 3, 0, "LOST", R.GUESS, split_risk_evidence())))


def record_five_pairs():                # E_FIVE_PAIRS_L, declared
    return segment(19, 2, 5, FIVE_PAIR_PREFIX, (inp(8, 17, 1, "LOST", R.GUESS, five_pairs_evidence()),))


def record_first_click():               # F1, declared
    return full(3, 3, 4, (inp(0, 0, 0, "LOST", R.INITIAL_OPEN),))


def record_guess_off():                 # G1 with guess OFF, declared
    blocked = R.BlockedProposal(4, (1, 5), "OPEN", 1, 3, forced_evidence())
    return full(2, 8, 1, G1_HEAD, allow_guess=False, blocked=blocked)


def record_not_recorded():
    """Declared material: the last input says that no pre-input evidence was recorded."""
    return R.make_record(
        record_scope=R.DECLARED, width=3, height=3, num_mines=4, allow_guess=True, prefix_inputs=(),
        inputs=(inp(0, 0, 0, decision=R.INITIAL_OPEN), inp(1, 2, 2, "LOST", R.EVIDENCE_NOT_RECORDED)),
        blocked=None, final_status="LOST", stop_reason=R.TERMINAL)


def scale_evidence(e, k):
    """Every world count times k; the fractions stay what they are."""
    state = e.public_state
    return replace(
        e,
        values=tuple(replace(
            v, mine_worlds=v.mine_worlds * k, total_worlds=v.total_worlds * k, flood_worlds=v.flood_worlds * k,
            outcomes=tuple(replace(o, worlds=o.worlds * k, minimum_mine_worlds=(
                None if o.minimum_mine_worlds is None else o.minimum_mine_worlds * k)) for o in v.outcomes))
            for v in e.values),
        pair_proofs=tuple(replace(p, mine_worlds=(p.mine_worlds[0] * k, p.mine_worlds[1] * k),
                                  total_worlds=p.total_worlds * k) for p in e.pair_proofs),
        public_state=replace(state, total_worlds=state.total_worlds * k,
                             mine_worlds=tuple((cell, count * k) for cell, count in state.mine_worlds)))


def doc_of(record):
    return json.loads(R.encode_record(record).decode("utf-8"))


def dump(document):
    return (json.dumps(document, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def new_folder():
    return tempfile.mkdtemp(prefix="s3d3rec_")  # left in place; nothing is deleted


ALL_RECORDS = (record_forced, lambda: record_forced("WON"), record_tie, lambda: record_tie("PLAYING"),
               record_min, record_limit, record_single, record_kept_forced, record_split_risk,
               record_five_pairs, record_first_click, record_guess_off, record_not_recorded)


class RecordCase(unittest.TestCase):
    def code(self, function, *args):
        with self.assertRaises(R.GuessRecordError) as caught:
            function(*args)
        return caught.exception.code

    def loss(self, record):
        return (record.loss.applicability, record.loss.kind, record.loss.basis, record.loss.input_index)


class ClassificationTests(RecordCase):
    def test_t01_a_forced_pair_guess_is_classified_forced_5050(self):
        record = record_forced()
        self.assertEqual((record.final_status, self.loss(record)),
                         ("LOST", ("APPLIES", "FORCED_5050", "PRE_INPUT_EVIDENCE", 4)))
        evidence = record.inputs[-1].evidence
        self.assertEqual((evidence.risk, evidence.original_target, evidence.original_risk, evidence.pair),
                         (F(1, 2), (0, 3), F(1, 2), ((0, 3), (1, 3))))

    def test_t02_a_tie_look_ahead_guess_is_classified_tie_lookahead(self):
        record = record_tie()
        self.assertEqual((record.record_scope, record.final_status, record.stop_reason, self.loss(record)),
                         (R.SEGMENT, "LOST", "TERMINAL", ("APPLIES", "TIE_LOOKAHEAD", "PRE_INPUT_EVIDENCE", 2)))
        evidence = record.inputs[-1].evidence
        self.assertEqual((evidence.target, evidence.risk, evidence.original_target, evidence.original_risk,
                          evidence.selection_reason, evidence.target_s_c, evidence.original_s_v,
                          evidence.lookahead_status),
                         ((2, 2), F(1, 3), (0, 2), F(1, 3), "TIE_LOOKAHEAD", F(2, 3), F(1, 2), "COMPUTED"))

    def test_t03_a_kept_minimum_risk_guess_with_computed_look_ahead_is_min_risk(self):
        record = record_min()
        self.assertEqual(self.loss(record), ("APPLIES", "MIN_RISK", "PRE_INPUT_EVIDENCE", 1))
        self.assertEqual((record.inputs[-1].evidence.lookahead_status, record.inputs[-1].evidence.actual_calls),
                         ("COMPUTED", 7))

    def test_t04_a_single_candidate_guess_is_min_risk_with_its_own_reason(self):
        record = record_single()
        self.assertEqual(self.loss(record), ("APPLIES", "MIN_RISK", "PRE_INPUT_EVIDENCE", 2))
        evidence = record.inputs[-1].evidence
        self.assertEqual((evidence.lookahead_status, evidence.values, evidence.target_s_c, evidence.original_s_v),
                         ("NOT_REQUIRED_SINGLE", (), None, None))

    def test_t05_a_guess_over_the_candidate_limit_is_min_risk_with_its_own_reason(self):
        record = record_limit()
        self.assertEqual(self.loss(record), ("APPLIES", "MIN_RISK", "PRE_INPUT_EVIDENCE", 1))
        evidence = record.inputs[-1].evidence
        self.assertEqual((evidence.lookahead_status, len(evidence.lookahead_cells), evidence.risk,
                          evidence.planned_calls), ("NOT_COMPUTED_CANDIDATE_LIMIT", 9, F(1, 9), 0))

    def test_t06_a_forced_pair_whose_target_equals_the_original_target_is_still_forced_5050(self):
        record = record_kept_forced()
        evidence = record.inputs[-1].evidence
        self.assertEqual((evidence.target, evidence.original_target, evidence.target_changed, evidence.category),
                         ((3, 0), (3, 0), False, "EXACT_MINIMUM_RISK_GUESS"))
        self.assertEqual(self.loss(record), ("APPLIES", "FORCED_5050", "PRE_INPUT_EVIDENCE", 3))

    def test_t07_a_forced_pair_without_computed_look_ahead_is_still_forced_5050(self):
        record = record_five_pairs()
        evidence = record.inputs[-1].evidence
        self.assertEqual((evidence.lookahead_status, len(evidence.lookahead_cells), evidence.rank_basis,
                          evidence.values, evidence.ranking[0][0], evidence.ranking[0][1], evidence.independence),
                         ("NOT_COMPUTED_CANDIDATE_LIMIT", 10, "COST_READING", (), (17, 1), None,
                          "INDEPENDENT_PROVEN"))
        self.assertEqual(self.loss(record), ("APPLIES", "FORCED_5050", "PRE_INPUT_EVIDENCE", 8))

    def test_t08_actual_risk_and_original_target_risk_are_kept_apart(self):
        record = record_split_risk()
        evidence = record.inputs[-1].evidence
        self.assertEqual((evidence.target, evidence.risk, evidence.original_target, evidence.original_risk,
                          evidence.is_minimum_risk, evidence.target_s_c, evidence.original_s_v),
                         ((3, 0), F(1, 2), (4, 0), F(1, 4), False, F(1, 2), None))
        self.assertEqual(self.loss(record), ("APPLIES", "FORCED_5050", "PRE_INPUT_EVIDENCE", 1))
        # The actual risk cannot be replaced by the original target's risk.
        swapped = replace(evidence, risk=F(1, 4))
        self.assertEqual(self.code(full, 6, 2, 2, (inp(0, 0, 0, decision=R.INITIAL_OPEN),
                                                    inp(1, 3, 0, "LOST", R.GUESS, swapped))), "RECORD_EVIDENCE")

    def test_t09_a_loss_without_pre_input_evidence_is_unclassified(self):
        first = record_first_click()
        self.assertEqual((first.final_status, self.loss(first)),
                         ("LOST", ("APPLIES", "UNCLASSIFIED", "INITIAL_OPEN_WITHOUT_EVIDENCE", 0)))
        declared = record_not_recorded()
        self.assertEqual((declared.record_scope, self.loss(declared)),
                         (R.DECLARED, ("APPLIES", "UNCLASSIFIED", "EVIDENCE_NOT_RECORDED", 1)))

    def test_t10_a_win_and_an_unfinished_game_get_no_loss_classification(self):
        self.assertEqual(self.loss(record_forced("WON")), ("NOT_APPLICABLE_WON", None, None, None))
        survived = record_tie("PLAYING")
        self.assertEqual((survived.final_status, survived.stop_reason, self.loss(survived)),
                         ("PLAYING", "SEGMENT_END", ("NOT_APPLICABLE_NOT_FINISHED", None, None, None)))
        off = record_guess_off()
        self.assertEqual((off.final_status, off.stop_reason, self.loss(off)),
                         ("PLAYING", "GUESS_BLOCKED", ("NOT_APPLICABLE_NOT_FINISHED", None, None, None)))
        # The same pre-input evidence serves the lost and the surviving layout: it was not
        # written with the result in hand.
        self.assertEqual(survived.inputs[-1].evidence, record_tie().inputs[-1].evidence)

    def test_t11_a_blocked_proposal_is_neither_an_input_nor_a_loss(self):
        off = record_guess_off()
        self.assertEqual((len(off.inputs), off.blocked.input_index, (off.blocked.x, off.blocked.y),
                          off.blocked.evidence.kind), (4, 4, (1, 3), "FORCED_5050"))
        self.assertTrue(all(item.evidence is None for item in off.inputs))
        counts = R.tally([off])
        self.assertEqual((counts["LOST"], counts["PLAYING"], counts["executed_inputs"],
                          counts["blocked_proposals"], sum(counts["loss_kinds"].values())), (0, 1, 4, 1, 0))
        blocked = off.blocked
        for name, make in (
                ("with guess allowed", lambda: full(2, 8, 1, G1_HEAD, allow_guess=True, blocked=blocked)),
                ("as an executed input", lambda: full(2, 8, 1, G1_HEAD + (
                    inp(4, 1, 3, "LOST", R.GUESS, forced_evidence()),), allow_guess=False)),
                ("beside a finished game", lambda: R.make_record(
                    record_scope=R.FULL_RUN, width=2, height=8, num_mines=1, allow_guess=False, prefix_inputs=(),
                    inputs=G1_HEAD[:3] + (inp(3, 1, 5, "LOST"),), blocked=blocked, final_status="LOST",
                    stop_reason=R.TERMINAL)),
                ("with another index", lambda: full(2, 8, 1, G1_HEAD, allow_guess=False,
                                                    blocked=replace(blocked, input_index=5))),
                ("without the proposal", lambda: full(2, 8, 1, G1_HEAD, allow_guess=False))):
            with self.subTest(name=name):
                self.assertEqual(self.code(make), "RECORD_INPUTS")

    def test_t12_evidence_linked_to_the_wrong_input_is_rejected(self):
        first = inp(0, 0, 0, decision=R.INITIAL_OPEN)
        cases = {
            "another target": lambda: full(5, 1, 2, (first, inp(1, 3, 0, "LOST", R.GUESS, min_evidence()))),
            "an earlier state": lambda: full(5, 1, 2, (first, inp(1, 4, 0),
                                                       inp(2, 2, 0, "LOST", R.GUESS, min_evidence()))),
            "another cursor": lambda: segment(3, 3, 4, (("OPEN", 2, 0), ("OPEN", 1, 0)),
                                              (inp(2, 2, 2, "LOST", R.GUESS, tie_evidence()),)),
            "evidence on a certain input": lambda: full(2, 8, 1, G1_HEAD[:3] + (
                inp(3, 1, 5, "LOST", R.CERTAIN, forced_evidence()),)),
            "evidence on the initial input": lambda: full(5, 1, 2, (
                inp(0, 0, 0, "LOST", R.INITIAL_OPEN, min_evidence()),)),
            "a flag as the guess": lambda: full(5, 1, 2, (first, inp(1, 2, 0, "LOST", R.GUESS, min_evidence(),
                                                                    action="FLAG"))),
        }
        for name, make in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.code(make), "RECORD_LINK")
        # The honest links are accepted.
        self.assertEqual(self.loss(record_min())[1], "MIN_RISK")

    def test_t13_missing_evidence_and_damaged_evidence_are_different_things(self):
        first = inp(0, 0, 0, decision=R.INITIAL_OPEN)
        self.assertEqual(self.loss(record_not_recorded())[1], "UNCLASSIFIED")  # declared as absent

        def lost(evidence):
            return full(5, 1, 2, (first, inp(1, 2, 0, "LOST", R.GUESS, evidence)))

        good = min_evidence()
        damaged = {
            "a guess without evidence": None,
            "kind against reason": replace(good, kind="TIE_LOOKAHEAD"),
            "reason against kind": replace(good, selection_reason="FORCED_5050_FIRST"),
            "LINKED": replace(good, kind="LINKED"),
            "PSEUDO_5050": replace(good, kind="PSEUDO_5050"),
            "UNCLASSIFIED as a kind": replace(good, kind="UNCLASSIFIED"),
            "status as a kind": replace(good, kind="NOT_COMPUTED_CANDIDATE_LIMIT"),
            "no values although computed": replace(good, values=()),
            "one value missing": replace(good, values=good.values[:2]),
            "an outcome missing": replace(good, values=(replace(
                good.values[0], outcomes=good.values[0].outcomes[:1]),) + good.values[1:]),
            "S_c changed": replace(good, values=(replace(good.values[0], s_c=F(1, 3)),) + good.values[1:]),
            "world count changed": replace(good, values=(replace(good.values[0], outcomes=(
                replace(good.values[0].outcomes[0], worlds=2),) + good.values[0].outcomes[1:]),)
                + good.values[1:]),
            "risk changed": replace(good, risk=F(1, 2)),
            "original target changed": replace(good, original_target=(3, 0)),
            "missing S_c written as zero": replace(limit_evidence(), target_s_c=F(0)),
            "status changed": replace(good, lookahead_status="NOT_REQUIRED_SINGLE"),
            "calls changed": replace(good, actual_calls=6),
            "float risk": replace(good, risk=1 / 3),
            "state of another board": replace(good, public_state=replace(
                good.public_state, observation=grid("1 H H H"))),
        }
        for name, evidence in damaged.items():
            with self.subTest(name=name):
                make = (lambda: full(11, 1, 2, (first, inp(1, 2, 0, "LOST", R.GUESS, evidence)))
                        ) if name == "missing S_c written as zero" else (lambda: lost(evidence))
                self.assertEqual(self.code(make), "RECORD_EVIDENCE")  # an error, never UNCLASSIFIED
        self.assertEqual(self.code(R.validate_record, replace(
            record_forced(), loss=R.LossClassification("APPLIES", "UNCLASSIFIED", "EVIDENCE_NOT_RECORDED", 4))),
            "RECORD_CLASSIFICATION")

    def test_x03_no_pre_input_record_gives_type_unconfirmed(self):
        record = record_not_recorded()
        self.assertEqual(R.describe(record)[1], "패배 보조 분류: 유형 미확인 (UNCLASSIFIED). 입력 전 근거가 기록되지 않았다.")
        self.assertEqual(R.describe(record_first_click())[1],
                         "패배 보조 분류: 유형 미확인 (UNCLASSIFIED). 첫 입력에는 입력 전 근거가 없다.")
        again = R.decode_record(R.encode_record(record))
        self.assertEqual((again, again.inputs[-1].evidence, self.loss(again)[1]), (record, None, "UNCLASSIFIED"))
        # Outside declared material an input cannot simply be marked as "not recorded".
        self.assertEqual(self.code(full, 3, 3, 4, (inp(0, 0, 0, decision=R.INITIAL_OPEN),
                                                    inp(1, 2, 2, "LOST", R.EVIDENCE_NOT_RECORDED))), "RECORD_INPUTS")

    def test_x05_the_win_loss_tally_does_not_depend_on_the_classification(self):
        records = [make() for make in ALL_RECORDS]
        counts = R.tally(records)
        by_status = {status: sum(1 for r in records if r.final_status == status) for status in R.STATUSES}
        self.assertEqual({status: counts[status] for status in R.STATUSES}, by_status)
        self.assertEqual((counts["WON"], counts["LOST"], counts["PLAYING"]), (1, 10, 2))
        self.assertEqual((counts["loss_kinds"], counts["integrity_problems"], counts["blocked_proposals"],
                          counts["executed_inputs"]),
                         ({"FORCED_5050": 4, "TIE_LOOKAHEAD": 1, "MIN_RISK": 3, "UNCLASSIFIED": 2}, 0, 1,
                          sum(len(r.inputs) for r in records)))
        self.assertEqual(sum(counts["loss_kinds"].values()), counts["LOST"])  # every loss is still a loss

    def test_x07_a_memory_only_record_is_shown_as_not_saved(self):
        record = record_forced()
        line = "저장 상태: 저장되지 않음 (메모리 기록)."
        self.assertEqual(R.describe(record)[-1], line)
        self.assertEqual(R.describe(record, R.NOT_SAVED)[-1], line)
        self.assertEqual(R.describe(record, R.SaveOutcome(R.NOT_SAVED, None, None, None, None, None, None))[-1],
                         line)
        self.assertEqual(R.describe(record)[0], "기본 결과: LOST")  # the base result is a line of its own

    def test_x08_min_risk_keeps_the_not_computed_reason_in_a_separate_field(self):
        for make, status, line in ((record_limit, "NOT_COMPUTED_CANDIDATE_LIMIT", "전방 계산: 후보 수 한도로 계산하지 않음."),
                                   (record_single, "NOT_REQUIRED_SINGLE", "전방 계산: 후보가 한 칸이라 계산하지 않음."),
                                   (record_min, "COMPUTED", "전방 계산: 계산함 (가정 계산 7회).")):
            record = make()
            evidence = record.inputs[-1].evidence
            self.assertEqual((record.loss.kind, evidence.kind, evidence.lookahead_status), ("MIN_RISK",) * 2 + (status,))
            self.assertIn(line, R.describe(record))
            document = doc_of(record)["inputs"][-1]["evidence"]
            self.assertEqual((document["kind"], document["lookahead"]["status"]), ("MIN_RISK", status))
        # A forced pair stays FORCED_5050 when its look-ahead was skipped by the limit.
        forced = record_five_pairs()
        self.assertEqual((forced.loss.kind, forced.inputs[-1].evidence.lookahead_status),
                         ("FORCED_5050", "NOT_COMPUTED_CANDIDATE_LIMIT"))
        self.assertNotIn(forced.loss.kind, R.LOOKAHEAD_STATUSES)


class StorageTests(RecordCase):
    def test_s01_a_record_is_saved_and_read_back_unchanged(self):
        folder = new_folder()
        for index, make in enumerate(ALL_RECORDS):
            with self.subTest(index=index):
                record = make()
                data = R.encode_record(record)
                self.assertEqual((R.decode_record(data), R.encode_record(R.decode_record(data))), (record, data))
                self.assertTrue(data.endswith(b"}\n") and b"\r" not in data and not data.startswith(b"\xef\xbb\xbf"))
                path = os.path.join(folder, f"record_{index:02d}.json")
                outcome = R.save_record(record, path)
                self.assertEqual((outcome.state, outcome.path, outcome.bytes, outcome.code, outcome.partial_path),
                                 ("SAVED", path, len(data), None, None))
                with open(path, "rb") as stream:
                    self.assertEqual(stream.read(), data)
                self.assertFalse(os.path.exists(path + ".partial"))
                loaded = R.load_record(path)
                self.assertEqual((loaded, R.describe(loaded)[:-1]), (record, R.describe(record)[:-1]))
        document = doc_of(record_tie())
        self.assertEqual(list(document), list(R.TOP_KEYS))
        self.assertEqual((document["format"], document["version"], document["policy"], document["evidence_timing"],
                          document["board"], document["prefix_inputs"]),
                         ("S3D3_GUESS_OUTCOME_RECORD", 1,
                          {"id": "S3D3-A", "definition": "GUESS_STRUCTURE_V1",
                           "selection_scope": "FORCED_PAIR_AND_TIE_LOOKAHEAD_V1",
                           "record_stage": "GUESS_OUTCOME_RECORD_V1"},
                          {"evidence_created": "BEFORE_EACH_INPUT", "file_written": "AFTER_RUN_END"},
                          {"width": 3, "height": 3, "num_mines": 4}, [["OPEN", 1, 0], ["OPEN", 2, 0]]))
        text = json.dumps(document)
        self.assertNotIn("layout", text)  # no hidden layout field exists in the format
        self.assertNotIn("mine_positions", text)

    def test_s02_without_a_save_nothing_is_written(self):
        folder = new_folder()
        record = record_tie()
        R.encode_record(record)
        R.describe(record)
        self.assertEqual(os.listdir(folder), [])
        self.assertEqual(R.describe(record)[-1], "저장 상태: 저장되지 않음 (메모리 기록).")

    def test_s03_a_failed_save_is_reported_and_changes_neither_record_nor_result(self):
        folder = new_folder()
        record, data = record_forced(), R.encode_record(record_forced())
        path = os.path.join(folder, "write_failure.json")
        with patch.object(R.os, "fsync", side_effect=OSError("declared write failure")):
            outcome = R.save_record(record, path)
        self.assertEqual((outcome.state, outcome.code, outcome.bytes, outcome.sha256, outcome.partial_path),
                         ("SAVE_FAILED", "WRITE_FAILED", None, None, path + ".partial"))
        self.assertFalse(os.path.exists(path))            # the final name never shows up incomplete
        self.assertTrue(os.path.exists(path + ".partial"))  # the partial file is left, not deleted
        self.assertEqual((record, R.encode_record(record), record.final_status, record.loss.kind),
                         (record_forced(), data, "LOST", "FORCED_5050"))
        self.assertEqual((R.describe(record, outcome)[0], R.describe(record, outcome)[-1]),
                         ("기본 결과: LOST", "저장 상태: 저장 실패 (WRITE_FAILED). 게임 결과와 무관하다."))
        path = os.path.join(folder, "rename_failure.json")
        with patch.object(R.os, "rename", side_effect=OSError("declared rename failure")):
            outcome = R.save_record(record, path)
        self.assertEqual((outcome.state, outcome.code, outcome.partial_path, os.path.exists(path)),
                         ("SAVE_FAILED", "RENAME_FAILED", path + ".partial", False))
        with open(path + ".partial", "rb") as stream:
            self.assertEqual(stream.read(), data)
        path = os.path.join(folder, "verify_failure.json")
        real_rename = os.rename

        def rename_then_damage(source, target):
            real_rename(source, target)
            with open(target, "ab") as stream:
                stream.write(b"x")

        with patch.object(R.os, "rename", side_effect=rename_then_damage):
            outcome = R.save_record(record, path)
        self.assertEqual((outcome.state, outcome.code), ("SAVE_FAILED", "VERIFY_FAILED"))
        self.assertEqual(self.code(R.load_record, path), "RECORD_JSON")  # the damaged file is no record
        missing = os.path.join(folder, "no_such_folder", "record.json")
        outcome = R.save_record(record, missing)
        self.assertEqual((outcome.state, outcome.code, outcome.partial_path), ("SAVE_FAILED", "WRITE_FAILED", None))
        # An invalid record is refused before anything is written.
        bad = replace(record, final_status="WON")
        path = os.path.join(folder, "invalid.json")
        self.assertEqual(self.code(R.save_record, bad, path), "RECORD_INPUTS")
        self.assertFalse(os.path.exists(path) or os.path.exists(path + ".partial"))

    def test_s04_an_existing_path_is_never_overwritten(self):
        folder = new_folder()
        path = os.path.join(folder, "taken.json")
        first = R.save_record(record_forced(), path)
        with open(path, "rb") as stream:
            before = stream.read()
        second = R.save_record(record_tie(), path)
        self.assertEqual((first.state, second.state, second.code, second.partial_path),
                         ("SAVED", "SAVE_FAILED", "PATH_EXISTS", None))
        with open(path, "rb") as stream:
            self.assertEqual(stream.read(), before)
        self.assertEqual((sorted(os.listdir(folder)), R.load_record(path)), (["taken.json"], record_forced()))
        self.assertEqual(R.describe(record_tie(), second)[-1], "저장 상태: 저장 실패 (PATH_EXISTS). 게임 결과와 무관하다.")

    def test_s05_a_partial_file_is_neither_reused_nor_read_as_a_record(self):
        folder = new_folder()
        path = os.path.join(folder, "interrupted.json")
        data = R.encode_record(record_tie())
        with open(path + ".partial", "xb") as stream:
            stream.write(data[:len(data) // 2])
        outcome = R.save_record(record_tie(), path)
        self.assertEqual((outcome.state, outcome.code, outcome.partial_path, os.path.exists(path)),
                         ("SAVE_FAILED", "PARTIAL_PATH_EXISTS", path + ".partial", False))
        with open(path + ".partial", "rb") as stream:
            self.assertEqual(stream.read(), data[:len(data) // 2])  # untouched
        self.assertEqual(self.code(R.load_record, path + ".partial"), "RECORD_JSON")

    def test_s06_an_unknown_format_or_version_is_rejected(self):
        for name, change in (("version 2", {"version": 2}), ("version 0", {"version": 0}),
                             ("version as text", {"version": "1"}), ("version as boolean", {"version": True}),
                             ("another format", {"format": "S3D3_OTHER"}), ("a product name", {"format": "REPLAY"})):
            with self.subTest(name=name):
                document = doc_of(record_tie())
                document.update(change)
                self.assertEqual(self.code(R.decode_record, dump(document)), "RECORD_VERSION")
        for key in ("format", "version"):
            document = doc_of(record_tie())
            del document[key]
            self.assertEqual(self.code(R.decode_record, dump(document)), "RECORD_VERSION")

    def test_s07_truncated_damaged_or_incomplete_files_are_rejected(self):
        data = R.encode_record(record_tie())
        self.assertEqual(dump(doc_of(record_tie())), data)  # the helper reproduces the fixed byte form
        broken = {
            "truncated": data[:len(data) // 2], "one byte short": data[:-2], "empty": b"",
            "not utf-8": b"\xff\xfe" + data, "with a BOM": b"\xef\xbb\xbf" + data,
            "trailing bytes": data + b"x", "CRLF": data.replace(b"\n", b"\r\n"),
            "not indented": json.dumps(doc_of(record_tie()), ensure_ascii=False).encode("utf-8"),
            "a repeated key": data.replace(b'"version": 1,', b'"version": 1,\n "version": 1,', 1),
        }
        for name, raw in broken.items():
            with self.subTest(name=name):
                self.assertEqual(self.code(R.decode_record, raw), "RECORD_JSON")
        self.assertEqual(self.code(R.decode_record, b"[]\n"), "RECORD_FIELD")
        self.assertEqual(self.code(R.decode_record, data.decode("utf-8")), "RECORD_JSON")  # bytes only

        def changed(mutate):
            document = doc_of(record_tie())
            mutate(document)
            return dump(document)

        evidence = lambda d: d["inputs"][-1]["evidence"]
        fields = {
            "top field missing": lambda d: d.pop("stop_reason"),
            "top field unknown": lambda d: d.update(note="x"),
            "top fields reordered": lambda d: d.update(format=d.pop("format")),
            "board field missing": lambda d: d["board"].pop("num_mines"),
            "input field missing": lambda d: d["inputs"][-1].pop("decision"),
            "evidence field missing": lambda d: evidence(d).pop("risk"),
            "evidence field unknown": lambda d: evidence(d).update(linked=True),
            "look-ahead field missing": lambda d: evidence(d)["lookahead"].pop("values"),
            "value field missing": lambda d: evidence(d)["lookahead"]["values"][0].pop("s_v"),
            "outcome field missing": lambda d: evidence(d)["lookahead"]["values"][0]["outcomes"][0].pop("q"),
            "state field missing": lambda d: evidence(d)["public_state"].pop("mines"),
            "classification field missing": lambda d: d["loss_classification"].pop("basis"),
            "policy changed": lambda d: d["policy"].update(id="K"),
            "timing changed": lambda d: d["evidence_timing"].update(file_written="BEFORE_EACH_INPUT"),
            "inputs not a list": lambda d: d.update(inputs={}),
            "cell not a pair": lambda d: evidence(d).update(target=[2, 2, 0]),
            "allow_guess not boolean": lambda d: d.update(allow_guess=1),
        }
        for name, mutate in fields.items():
            with self.subTest(name=name):
                self.assertEqual(self.code(R.decode_record, changed(mutate)), "RECORD_FIELD")

    def test_s08_duplicate_or_inconsistent_inputs_are_rejected(self):
        record = record_forced()
        last = record.inputs[-1]
        cases = {
            "duplicate index": replace(record, inputs=record.inputs[:4] + (replace(last, index=3),)),
            "gap in the indices": replace(record, inputs=record.inputs[:4] + (replace(last, index=5),)),
            "status after the end": replace(record, inputs=(replace(record.inputs[0], status_after="WON"),)
                                            + record.inputs[1:]),
            "base result against the last input": replace(record, final_status="WON"),
            "stop reason against the result": replace(record, stop_reason="SEGMENT_END"),
            "a guess sent with guess OFF": replace(record, allow_guess=False),
            "an initial input elsewhere": replace(record, inputs=(replace(record.inputs[0], x=1),)
                                                  + record.inputs[1:]),
            "no initial input": replace(record, inputs=(replace(record.inputs[0], decision=R.CERTAIN),)
                                        + record.inputs[1:]),
            "a second initial input": replace(record, inputs=record.inputs[:1] + (
                replace(record.inputs[1], decision=R.INITIAL_OPEN),) + record.inputs[2:]),
            "prefix on a full run": replace(record, prefix_inputs=(("OPEN", 0, 1),)),
            "no input": replace(record, inputs=()),
            "an input outside the board": replace(record, inputs=record.inputs[:3] + (
                replace(record.inputs[3], y=9),) + record.inputs[4:]),
            "an unknown action": replace(record, inputs=record.inputs[:3] + (
                replace(record.inputs[3], action="CLICK"),) + record.inputs[4:]),
            "an unknown status": replace(record, inputs=record.inputs[:4] + (replace(last, status_after="DRAW"),),
                                         final_status="DRAW"),
            "an unfinished full run with guess allowed": replace(record, inputs=record.inputs[:4],
                                                                 final_status="PLAYING", stop_reason="SEGMENT_END"),
        }
        for name, bad in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.code(R.validate_record, bad), "RECORD_INPUTS")
        self.assertEqual(self.code(R.validate_record, replace(record, width=0)), "RECORD_FIELD")
        self.assertEqual(self.code(R.validate_record, replace(record, record_scope="REPLAY")), "RECORD_FIELD")
        self.assertEqual(self.code(R.validate_record, replace(record_tie(), prefix_inputs=())), "RECORD_INPUTS")
        # The same faults inside a file.
        document = doc_of(record)
        document["inputs"][4]["index"] = 3
        self.assertEqual(self.code(R.decode_record, dump(document)), "RECORD_INPUTS")
        for kind in ("MIN_RISK", "UNCLASSIFIED", None):
            document = doc_of(record)
            document["loss_classification"]["kind"] = kind
            self.assertEqual(self.code(R.decode_record, dump(document)), "RECORD_CLASSIFICATION")
        document = doc_of(record)
        document["final_status"] = "WON"
        self.assertEqual(self.code(R.decode_record, dump(document)), "RECORD_INPUTS")

    def test_s09_big_integers_and_fractions_survive_exactly(self):
        big = segment(3, 3, 4, TIE_PREFIX, (inp(2, 2, 2, "LOST", R.GUESS, scale_evidence(tie_evidence(), BIG)),))
        data = R.encode_record(big)
        again = R.decode_record(data)
        self.assertEqual((again, R.encode_record(again)), (big, data))
        evidence = again.inputs[-1].evidence
        self.assertEqual((evidence.public_state.total_worlds, evidence.values[1].outcomes[2].worlds,
                          evidence.values[1].outcomes[2].minimum_mine_worlds),
                         (6 * BIG, 4 * BIG, 2 * BIG))
        self.assertEqual((evidence.risk, evidence.target_s_c, evidence.original_s_v, evidence.values[0].outcomes[1].q),
                         (F(1, 3), F(2, 3), F(1, 2), F(1, 2)))  # the fractions are those of the small record
        self.assertTrue(all(type(v) is int for v in (evidence.public_state.total_worlds,
                                                     evidence.values[0].mine_worlds, evidence.values[0].flood_worlds)))
        self.assertTrue(all(type(v) is F for v in (evidence.risk, evidence.values[0].s_v, evidence.values[0].s_c)))
        text = data.decode("utf-8")
        self.assertIn('"total_worlds": "9641628265553941653251772554046975615133217962696757011808256"', text)
        self.assertIn('"risk": {\n', text)
        document = json.loads(text)
        state = document["inputs"][-1]["evidence"]["public_state"]
        self.assertEqual((type(state["total_worlds"]), document["inputs"][-1]["evidence"]["risk"]),
                         (str, {"n": "1", "d": "3"}))
        self.assertEqual(R.describe(again)[1:3], R.describe(record_tie())[1:3])  # display from exact values

        def changed(mutate):
            document = doc_of(record_tie())
            mutate(document["inputs"][-1]["evidence"])
            return dump(document)

        bad = {
            "denominator 0": lambda e: e.update(risk={"n": "1", "d": "0"}),
            "not in lowest terms": lambda e: e.update(risk={"n": "2", "d": "6"}),
            "above one": lambda e: e.update(risk={"n": "3", "d": "2"}),
            "sign": lambda e: e["public_state"].update(total_worlds="+6"),
            "leading zero": lambda e: e["public_state"].update(total_worlds="06"),
            "decimal point": lambda e: e["public_state"].update(total_worlds="6.0"),
            "space": lambda e: e["public_state"].update(total_worlds=" 6"),
            "full-width digit": lambda e: e["public_state"].update(total_worlds="６"),
            "empty text": lambda e: e["public_state"].update(total_worlds=""),
            "JSON integer for a world count": lambda e: e["public_state"].update(total_worlds=6),
            "fraction as text": lambda e: e.update(risk="1/3"),
            "fraction without d": lambda e: e.update(risk={"n": "1"}),
            "negative numerator": lambda e: e.update(risk={"n": "-1", "d": "3"}),
            "boolean for a count": lambda e: e["lookahead"].update(planned_calls=True),
            "text for a small integer": lambda e: e["lookahead"].update(planned_calls="12"),
        }
        for name, mutate in bad.items():
            with self.subTest(name=name):
                self.assertEqual(self.code(R.decode_record, changed(mutate)), "RECORD_NUMBER")
        raw = R.encode_record(record_tie())
        for name, old, new in (("real number", b'"width": 3', b'"width": 3.0'),
                               ("exponent", b'"width": 3', b'"width": 3e0'),
                               ("NaN", b'"width": 3', b'"width": NaN'),
                               ("Infinity", b'"width": 3', b'"width": Infinity')):
            with self.subTest(name=name):
                self.assertIn(old, raw)
                self.assertEqual(self.code(R.decode_record, raw.replace(old, new, 1)), "RECORD_NUMBER")
        # A well-formed but wrong exact value is an evidence error, not a number error.
        self.assertEqual(self.code(R.decode_record, changed(lambda e: e.update(risk={"n": "1", "d": "2"}))),
                         "RECORD_EVIDENCE")

    def test_s12_missing_evidence_is_never_filled_in_by_recomputation(self):
        def changed(mutate):
            document = doc_of(record_tie())
            mutate(document["inputs"][-1]["evidence"])
            return dump(document)

        cases = {
            "values removed": (lambda e: e["lookahead"].update(values=[]), "RECORD_EVIDENCE"),
            "one value removed": (lambda e: e["lookahead"]["values"].pop(), "RECORD_EVIDENCE"),
            "S_v removed": (lambda e: e["lookahead"]["values"][0].pop("s_v"), "RECORD_FIELD"),
            "S_v set to null": (lambda e: e["lookahead"]["values"][0].update(s_v=None), "RECORD_NUMBER"),
            "target S_c set to null": (lambda e: e["lookahead"].update(target_s_c=None), "RECORD_EVIDENCE"),
            "risk set to null": (lambda e: e.update(risk=None), "RECORD_NUMBER"),
            "world counts removed": (lambda e: e["public_state"].update(mine_worlds=[]), "RECORD_EVIDENCE"),
            "pair judgement emptied of its counts": (lambda e: e["pair_proofs"][0].update(mine_worlds=[]),
                                                    "RECORD_FIELD"),
        }
        for name, (mutate, code) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.code(R.decode_record, changed(mutate)), code)
        document = doc_of(record_tie())
        document["inputs"][-1]["evidence"] = None  # the whole evidence of a guess input is gone
        self.assertEqual(self.code(R.decode_record, dump(document)), "RECORD_EVIDENCE")
        # What was declared as not recorded stays not recorded after a round trip.
        absent = R.decode_record(R.encode_record(record_not_recorded()))
        self.assertEqual((absent.inputs[-1].decision, absent.inputs[-1].evidence, absent.loss.kind),
                         ("EVIDENCE_NOT_RECORDED", None, "UNCLASSIFIED"))


class DescriptionTests(RecordCase):
    def test_d01_descriptions_are_short_and_say_only_what_was_recorded(self):
        saved = R.SaveOutcome(R.SAVED, "x.json", 1, "0" * 64, None, None, None)
        self.assertEqual(R.describe(record_forced()), (
            "기본 결과: LOST",
            "패배 보조 분류: 불가피한 50/50 쌍의 추측 (FORCED_5050). 입력 OPEN (1,3), 입력 전 위험 1/2.",
            "원 대상 (0,3)의 위험 1/2. 쌍의 어느 칸을 열어도 위험이 1/2이라는 뜻이며, 판 전체의 패배가 정해져 있었다는 뜻이 아니다.",
            "전방 계산: 계산함 (가정 계산 4회).",
            "저장 상태: 저장되지 않음 (메모리 기록)."))
        self.assertEqual(R.describe(record_tie(), R.LOADED_FROM_FILE), (
            "기본 결과: LOST",
            "패배 보조 분류: 최소 위험 동률 집합에서 전방 비교로 고른 추측 (TIE_LOOKAHEAD). 입력 OPEN (2,2), 입력 전 위험 1/3.",
            "원 대상 (0,2)의 위험 1/3. 대상의 S_c 2/3, 원 대상의 S_v 1/2.",
            "S_c와 S_v는 K-LC1 기준 수순의 다음 입력에 관한 값이다. 이 정책의 실제 생존확률이나 판 전체 승률이 아니다.",
            "전방 계산: 계산함 (가정 계산 12회).",
            "저장 상태: 실험 기록 파일에서 읽음."))
        self.assertEqual(R.describe(record_min(), saved), (
            "기본 결과: LOST",
            "패배 보조 분류: 기존 최소 위험 선택을 유지한 추측 (MIN_RISK). 입력 OPEN (2,0), 입력 전 위험 1/3.",
            "전방 계산: 계산함 (가정 계산 7회).",
            "저장 상태: 실험 기록 파일로 저장됨."))
        self.assertEqual(R.describe(record_forced("WON"))[:2], ("기본 결과: WON", "패배 보조 분류: 해당 없음 (WON)."))
        self.assertEqual(R.describe(record_tie("PLAYING"))[:2],
                         ("기본 결과: PLAYING (판이 끝나지 않았다)", "패배 보조 분류: 해당 없음 (판이 끝나지 않았다)."))
        self.assertEqual(R.describe(record_guess_off())[1:3], (
            "패배 보조 분류: 해당 없음 (판이 끝나지 않았다).",
            "차단된 제안 1건: OPEN (1,3), FORCED_5050. 실제 입력이 아니며 입력 수와 패배 수에 세지 않는다."))
        for make in (record_forced, record_kept_forced, record_split_risk, record_five_pairs):
            text = " ".join(R.describe(make()))
            self.assertIn("불가피한 50/50", text)
            for phrase in ("반드시 패배", "패배할 판"):
                self.assertNotIn(phrase, text)
            self.assertNotIn("S_c", text)  # a forced-pair description shows no look-ahead score
        self.assertIn("원 대상 (4,0)의 위험 1/4.", R.describe(record_split_risk())[2])
        self.assertEqual(R.describe(record_five_pairs())[3], "전방 계산: 후보 수 한도로 계산하지 않음.")
        for record in (record_forced(), record_tie(), record_min(), record_first_click()):
            lines = R.describe(record)
            self.assertTrue(lines[0].startswith("기본 결과: ") and lines[-1].startswith("저장 상태: "))
            self.assertTrue(all(len(line) < 120 for line in lines))
        with self.assertRaises(R.GuessRecordError):
            R.describe(record_forced(), "SOMEWHERE")
        with self.assertRaises(R.GuessRecordError):
            R.describe(replace(record_forced(), final_status="WON"))  # an invalid record is not described


class ModuleTests(RecordCase):
    def test_p01_the_record_module_imports_the_standard_library_only(self):
        with open(R.__file__, encoding="utf-8") as stream:
            tree = ast.parse(stream.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported, {"dataclasses", "fractions", "hashlib", "json", "os"})
        names = {name for name in vars(R) if not name.startswith("_")}
        self.assertFalse({name for name in names if "engine" in name.lower() or "kernel" in name.lower()})
        self.assertEqual((R.FORMAT, R.VERSION, R.RECORD_STAGE, R.SELECTION_SCOPE, R.CELL_LIMIT, R.CALL_LIMIT),
                         ("S3D3_GUESS_OUTCOME_RECORD", 1, "GUESS_OUTCOME_RECORD_V1",
                          "FORCED_PAIR_AND_TIE_LOOKAHEAD_V1", 8, 72))
        self.assertNotIn("LINKED", R.EVIDENCE_KINDS + (R.UNCLASSIFIED,))
        self.assertNotIn("PSEUDO_5050", R.EVIDENCE_KINDS + (R.UNCLASSIFIED,))


# ---- exact types of the numbers and cells that go into the file (local fix of stage 3) ----

def record_guess_off_split():
    """Declared material: G5 with guess OFF; the blocked proposal is (3,0) from cursor (0,0)."""
    blocked = R.BlockedProposal(1, (0, 0), "OPEN", 3, 0, split_risk_evidence())
    return full(6, 2, 2, (inp(0, 0, 0, decision=R.INITIAL_OPEN),), allow_guess=False, blocked=blocked)


def with_evidence(record, **changes):
    """The record with fields of the evidence of its LAST input replaced. Nothing is validated here."""
    last = record.inputs[-1]
    return replace(record, inputs=record.inputs[:-1] + (replace(last, evidence=replace(last.evidence, **changes)),))


def with_proof(record, position, **changes):
    proofs = record.inputs[-1].evidence.pair_proofs
    return with_evidence(record, pair_proofs=proofs[:position] + (replace(proofs[position], **changes),)
                         + proofs[position + 1:])


def with_blocked(record, **changes):
    return replace(record, blocked=replace(record.blocked, **changes))


def with_loss_index(record, index):
    return replace(record, loss=replace(record.loss, input_index=index))


class ExactTypeTests(RecordCase):
    """A float or a bool that EQUALS the right integer is refused before anything is saved.

    Every case changes ONE value of one valid declared record. ``refused`` checks
    validate_record, encode_record and save_record separately; the save goes to a
    path in a new empty folder, so a refusal can never be a path conflict, and the
    folder must stay empty afterwards (no final file and no partial file).
    """

    def refused(self, bad, code):
        folder = new_folder()
        path = os.path.join(folder, "refused.json")
        self.assertEqual(os.listdir(folder), [])
        self.assertEqual((self.code(R.validate_record, bad), self.code(R.encode_record, bad),
                          self.code(R.save_record, bad, path)), (code, code, code))
        self.assertEqual(os.listdir(folder), [])

    def refused_each(self, cases, code, count):
        self.assertEqual(len(cases), count)
        for name, (good, bad) in cases.items():
            with self.subTest(name=name):
                R.validate_record(good)
                self.assertEqual(bad, good)  # equal in Python: only the exact type of one value differs
                self.refused(bad, code)

    def is_cell(self, value):
        return type(value) is tuple and [type(v) for v in value] == [int, int]

    def forms(self, record):
        """Which optional forms a record shows; the nine fields must hold exact integers."""
        found = {"loss index None" if record.loss.input_index is None else "loss index int",
                 "blocked None" if record.blocked is None else "blocked present"}
        self.assertIn(type(record.loss.input_index), (int, type(None)))
        evidences = [item.evidence for item in record.inputs if item.evidence is not None]
        if record.blocked is not None:
            blocked = record.blocked
            self.assertTrue(type(blocked.x) is int and type(blocked.y) is int and self.is_cell(blocked.cursor))
            evidences.append(blocked.evidence)
        for evidence in evidences:
            self.assertTrue(self.is_cell(evidence.original_target) and type(evidence.k_lc1_move) is tuple
                            and [type(v) for v in evidence.k_lc1_move] == [str, int, int])
            found.add("pair None" if evidence.pair is None else "pair present")
            if evidence.pair is not None:
                self.assertTrue(type(evidence.pair) is tuple and len(evidence.pair) == 2
                                and all(self.is_cell(cell) for cell in evidence.pair))
            found.add("target S_c None" if evidence.target_s_c is None else "target S_c present")
            for proof in evidence.pair_proofs:
                self.assertTrue(type(proof.mine_worlds) is tuple
                                and [type(v) for v in proof.mine_worlds] == [int, int]
                                and type(proof.total_worlds) is int)
        return found

    def test_n01_the_original_target_needs_exact_integers(self):
        tie, split = record_tie(), record_split_risk()
        self.refused_each({
            "float x": (tie, with_evidence(tie, original_target=(0.0, 2))),
            "boolean x": (tie, with_evidence(tie, original_target=(False, 2))),
            "float y": (tie, with_evidence(tie, original_target=(0, 2.0))),
            "float x of another record": (split, with_evidence(split, original_target=(4.0, 0))),
            "boolean y of another record": (split, with_evidence(split, original_target=(4, False))),
        }, "RECORD_EVIDENCE", 5)

    def test_n02_the_k_lc1_move_needs_exact_integers(self):
        tie, split = record_tie(), record_split_risk()
        self.refused_each({
            "float x": (tie, with_evidence(tie, k_lc1_move=("OPEN", 0.0, 2))),
            "boolean x": (tie, with_evidence(tie, k_lc1_move=("OPEN", False, 2))),
            "float y": (tie, with_evidence(tie, k_lc1_move=("OPEN", 0, 2.0))),
            "boolean y of another record": (split, with_evidence(split, k_lc1_move=("OPEN", 4, False))),
        }, "RECORD_EVIDENCE", 4)

    def test_n03_the_pair_needs_cells_of_exact_integers(self):
        forced = record_forced()
        self.refused_each({
            "float x of the first cell": (forced, with_evidence(forced, pair=((0.0, 3), (1, 3)))),
            "boolean x of the first cell": (forced, with_evidence(forced, pair=((False, 3), (1, 3)))),
            "boolean x of the second cell": (forced, with_evidence(forced, pair=((0, 3), (True, 3)))),
            "float y of the second cell": (forced, with_evidence(forced, pair=((0, 3), (1, 3.0)))),
            "float x of the second cell": (forced, with_evidence(forced, pair=((0, 3), (1.0, 3)))),
        }, "RECORD_EVIDENCE", 5)

    def test_n04_the_world_counts_of_a_pair_need_exact_integers(self):
        tie, forced, five = record_tie(), record_forced(), record_five_pairs()
        self.refused_each({
            "float first count": (tie, with_proof(tie, 0, mine_worlds=(3.0, 3))),
            "float second count": (tie, with_proof(tie, 0, mine_worlds=(3, 3.0))),
            "float total": (tie, with_proof(tie, 0, total_worlds=6.0)),
            "boolean first count": (forced, with_proof(forced, 0, mine_worlds=(True, 1))),
            "boolean second count": (forced, with_proof(forced, 0, mine_worlds=(1, True))),
            "float count of a forced pair": (forced, with_proof(forced, 0, mine_worlds=(1.0, 1))),
            "float total of a forced pair": (forced, with_proof(forced, 0, total_worlds=2.0)),
            "float count of the last of five pairs": (five, with_proof(five, 4, mine_worlds=(16.0, 16))),
            "float total of the last of five pairs": (five, with_proof(five, 4, total_worlds=32.0)),
        }, "RECORD_EVIDENCE", 9)

    def test_n05_a_blocked_proposal_needs_exact_integers(self):
        off, split = record_guess_off(), record_guess_off_split()
        self.refused_each({
            "float x": (off, with_blocked(off, x=1.0)),
            "boolean x": (off, with_blocked(off, x=True)),
            "float y": (off, with_blocked(off, y=3.0)),
            "float x of the cursor": (off, with_blocked(off, cursor=(1.0, 5))),
            "boolean x of the cursor": (off, with_blocked(off, cursor=(True, 5))),
            "float y of the cursor": (off, with_blocked(off, cursor=(1, 5.0))),
            "float x of another record": (split, with_blocked(split, x=3.0)),
            "boolean y of another record": (split, with_blocked(split, y=False)),
            "float y of another record": (split, with_blocked(split, y=0.0)),
            "boolean x of the cursor of another record": (split, with_blocked(split, cursor=(False, 0))),
            "float y of the cursor of another record": (split, with_blocked(split, cursor=(0, 0.0))),
        }, "RECORD_INPUTS", 11)

    def test_n06_the_input_index_of_a_classification_needs_an_exact_integer(self):
        forced, tie, low = record_forced(), record_tie(), record_min()
        first, absent = record_first_click(), record_not_recorded()
        self.assertEqual([r.loss.input_index for r in (forced, tie, low, first, absent)], [4, 2, 1, 0, 1])
        self.refused_each({
            "float 4": (forced, with_loss_index(forced, 4.0)),
            "float 2": (tie, with_loss_index(tie, 2.0)),
            "boolean for 1": (low, with_loss_index(low, True)),
            "float 1": (low, with_loss_index(low, 1.0)),
            "boolean for 0 of a first-input loss": (first, with_loss_index(first, False)),
            "float 0 of a first-input loss": (first, with_loss_index(first, 0.0)),
            "boolean for 1 without recorded evidence": (absent, with_loss_index(absent, True)),
        }, "RECORD_CLASSIFICATION", 7)
        # The first-input loss itself stays what it was.
        self.assertEqual(self.loss(first), ("APPLIES", "UNCLASSIFIED", "INITIAL_OPEN_WITHOUT_EVIDENCE", 0))

    def test_n07_exact_values_and_allowed_none_are_still_accepted(self):
        folder = new_folder()
        makers = ALL_RECORDS + (record_guess_off_split,)
        self.assertEqual(len(makers), 14)
        seen = set()
        for index, make in enumerate(makers):
            with self.subTest(index=index):
                record = make()
                R.validate_record(record)
                data = R.encode_record(record)
                path = os.path.join(folder, f"accepted_{index:02d}.json")
                outcome = R.save_record(record, path)
                self.assertEqual((outcome.state, outcome.bytes, outcome.code, outcome.partial_path),
                                 ("SAVED", len(data), None, None))
                with open(path, "rb") as stream:
                    self.assertEqual(stream.read(), data)
                self.assertFalse(os.path.exists(path + ".partial"))
                loaded = R.load_record(path)
                self.assertEqual((loaded, R.encode_record(loaded)), (record, data))
                seen |= self.forms(record) | self.forms(loaded)
        self.assertEqual(seen, {"loss index None", "loss index int", "blocked None", "blocked present",
                                "pair None", "pair present", "target S_c None", "target S_c present"})
        # None stays refused where the format has no None.
        tie, forced, off = record_tie(), record_forced(), record_guess_off()
        missing = {
            "original target": (with_evidence(tie, original_target=None), "RECORD_EVIDENCE"),
            "K-LC1 move": (with_evidence(tie, k_lc1_move=None), "RECORD_EVIDENCE"),
            "pair of a forced-pair guess": (with_evidence(forced, pair=None), "RECORD_EVIDENCE"),
            "world counts of a pair": (with_proof(tie, 0, mine_worlds=None), "RECORD_EVIDENCE"),
            "world total of a pair": (with_proof(tie, 0, total_worlds=None), "RECORD_EVIDENCE"),
            "x of a blocked proposal": (with_blocked(off, x=None), "RECORD_INPUTS"),
            "cursor of a blocked proposal": (with_blocked(off, cursor=None), "RECORD_INPUTS"),
            "input index of a loss": (with_loss_index(forced, None), "RECORD_CLASSIFICATION"),
        }
        self.assertEqual(len(missing), 8)
        for name, (bad, code) in missing.items():
            with self.subTest(name=name):
                self.refused(bad, code)

    def test_n08_a_type_refusal_is_no_path_conflict_and_the_path_rules_are_unchanged(self):
        folder = new_folder()
        good = record_tie()
        bad = with_evidence(good, original_target=(0.0, 2))
        data = R.encode_record(good)
        # A new path: nothing but the type can have refused the record.
        new = os.path.join(folder, "new.json")
        self.assertEqual(self.code(R.save_record, bad, new), "RECORD_EVIDENCE")
        self.assertEqual(os.listdir(folder), [])
        self.assertEqual(R.save_record(good, new).state, "SAVED")  # the same path takes the valid record
        # An existing path: the invalid record is refused as invalid, the valid one as PATH_EXISTS.
        self.assertEqual(self.code(R.save_record, bad, new), "RECORD_EVIDENCE")
        again = R.save_record(good, new)
        self.assertEqual((again.state, again.code, again.partial_path), ("SAVE_FAILED", "PATH_EXISTS", None))
        with open(new, "rb") as stream:
            self.assertEqual(stream.read(), data)
        # An earlier partial file is left alone in both cases.
        held = os.path.join(folder, "held.json")
        with open(held + ".partial", "xb") as stream:
            stream.write(b"earlier")
        self.assertEqual(self.code(R.save_record, bad, held), "RECORD_EVIDENCE")
        outcome = R.save_record(good, held)
        self.assertEqual((outcome.state, outcome.code, outcome.partial_path),
                         ("SAVE_FAILED", "PARTIAL_PATH_EXISTS", held + ".partial"))
        with open(held + ".partial", "rb") as stream:
            self.assertEqual(stream.read(), b"earlier")
        # A write that would fail is never reached by an invalid record.
        failing = os.path.join(folder, "failing.json")
        with patch.object(R.os, "fsync", side_effect=OSError("declared write failure")) as fsync:
            self.assertEqual(self.code(R.save_record, bad, failing), "RECORD_EVIDENCE")
            self.assertEqual(fsync.call_count, 0)
            outcome = R.save_record(good, failing)
        self.assertEqual((outcome.state, outcome.code, outcome.partial_path, fsync.call_count),
                         ("SAVE_FAILED", "WRITE_FAILED", failing + ".partial", 1))
        self.assertEqual(sorted(os.listdir(folder)), ["failing.json.partial", "held.json.partial", "new.json"])


if __name__ == "__main__":
    unittest.main()
