"""Boundaries and protections of the M/R own-survival scores (stage4_risk_value).

Expected values come from brute-force enumeration and from arithmetic written
in this file, not from stage4_risk_value.
"""
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from types import SimpleNamespace
from unittest import mock
import unittest

import stage4_risk_value as rv
import stage4_runtime_model as m
from stage4_live_delivery import RuntimeDelivery
from stage4_objective_pilot import _complete_scores
from stage4_policy import model_order, _shortlist
from stage4_posterior import PosteriorRequest, public_digest, sample_posterior
from stage4_runtime_policy import RuntimeLimits, RuntimePolicy, RuntimeRequest
from tests import stage4_pilot_oracle as oracle

H, FL = -2, -3
# Public states (observation, mines, counted inputs) met on small development boards of the
# risk-value study. They are observations only; no board layout or seed belongs to them.
CHORD_STATE = (((0, 1, H, H, H), (0, 1, H, 2, H), (1, 2, 1, H, H), (H, H, H, H, 1), (H, H, H, H, H)), 4, 4)
FLAG_STATE = (((1, H, 2, 1, H, H), (1, 2, FL, H, H, H), (0, 1, 2, H, H, H), (1, 1, 2, H, H, H),
               (H, H, H, H, H, H), (H, H, H, H, H, H)), 5, 7)
# 2,100 worlds; the first two shortlisted candidates are proven safe, the next two are not.
SAFE_PAIR_STATE = (((0, 1, H, H, H, H), (0, 1, 1, H, H, H), (1, 1, H, H, H, H), (H, H, H, H, H, H),
                    (H, 4, H, H, H, H), (H, H, H, H, H, H)), 7, 3)
# 14 worlds; one shortlisted two-flag chord survives in 2 of them (1/7).
RARE_SURVIVOR_STATE = (((0, 1, 1, 1, 1, 1, 1), (1, 2, H, 1, 1, FL, 1), (H, H, 2, 1, 1, 1, 1), (H, H, 1, 0, 1, 2, 2),
                        (H, 2, 2, 1, 1, FL, H), (H, H, H, 2, 2, 3, H), (H, H, H, H, H, H, H)), 10, 14)
NARROW = dict(samples=4, shortlist=2, rows=8)
MODEL_ID = "RUNTIME_COMMON_POSTERIOR_THEN_PUBLIC_F_V4_RV1_OWN_SURVIVAL"


def brute(observation, num_mines):
    """Every layout consistent with the open numbers and the mine count (flags are unknowns)."""
    height, width = len(observation), len(observation[0])
    unknown = [(x, y) for y in range(height) for x in range(width) if observation[y][x] < 0]
    clues = [((x, y), observation[y][x]) for y in range(height) for x in range(width) if observation[y][x] >= 0]
    around = {cell: [n for n in oracle.neighbors(width, height, cell) if observation[n[1]][n[0]] < 0]
              for cell, _ in clues}
    layouts = []
    for chosen in combinations(unknown, num_mines):
        mines = set(chosen)
        if all(sum(n in mines for n in around[cell]) == clue for cell, clue in clues):
            layouts.append(frozenset(chosen))
    return layouts


def request(state, mode="M", seed=0, allow_guess=True, limits=None, target=None):
    grid, mines, counted = state
    if mode == "R" and target is None:
        target = Fraction(13, 10)
    return m.ModelRequest(grid, mines, counted, mode, allow_guess, target, seed,
                          limits=limits or m.ModelLimits())


def alive(candidate, layout):
    return not (set(candidate.targets) & set(layout))


def plain(rows, target=None):
    count = len(rows)
    hit = None if target is None else Fraction(sum(r.outcome == "WON" and r.value_x >= target for r in rows), count)
    return (sum((r.value_x for r in rows), Fraction(0)) / count,
            Fraction(sum(r.outcome == "WON" for r in rows), count), hit)


def own_survival(candidate, rows, samples, exact_p, target=None):
    """p_c times the mean over the samples in which the candidate's targets are all safe."""
    kept = [r for r, s in zip(rows, samples) if alive(candidate, s.mines)]
    if not kept:
        return Fraction(0), Fraction(0), (None if target is None else Fraction(0))
    hit = None if target is None else exact_p * Fraction(
        sum(r.outcome == "WON" and r.value_x >= target for r in kept), len(kept))
    return (exact_p * sum((r.value_x for r in kept), Fraction(0)) / len(kept),
            exact_p * Fraction(sum(r.outcome == "WON" for r in kept), len(kept)), hit)


def fake_candidate(name, worlds, total, targets=((0, 0),), length=1):
    return SimpleNamespace(candidate_id=name, targets=tuple(targets), sequence=tuple(range(length)),
                           survival=SimpleNamespace(worlds=worlds), survival_probability=Fraction(worlds, total))


def fake_rows(candidate, samples, values, target=None):
    rows = []
    for i, (sample, value) in enumerate(zip(samples, values)):
        dead = not alive(candidate, sample.mines)
        if dead:
            rows.append(m.RuntimeRow(candidate.candidate_id, i, sample.rank, "LOST", "TERMINAL", Fraction(0),
                                     False if target is not None else None, None, len(candidate.sequence), (), ()))
            continue
        value = Fraction(value)
        won = value > 0
        rows.append(m.RuntimeRow(candidate.candidate_id, i, sample.rank, "WON" if won else "LOST", "TERMINAL",
                                 value, (won and value >= target) if target is not None else None,
                                 10 if won else None, len(candidate.sequence) + 3, (), (0,)))
    return rows


def bank(*mine_cells):
    """Fake bank: one layout per argument; () is a layout without a mine on any target used here."""
    return [SimpleNamespace(rank=i, mines=tuple(cells)) for i, cells in enumerate(mine_cells)]


def replace_ns(namespace, **changes):
    values = dict(vars(namespace))
    values.update(changes)
    return SimpleNamespace(**values)


def best(candidates, scores, mode="M"):
    by_id = {s.candidate_id: s for s in scores}
    order = {c.candidate_id: model_order(by_id[c.candidate_id], c.survival_probability, i, mode)
             for i, c in enumerate(candidates)}
    return max(order, key=order.get)


def chosen_of(result):
    by_id = {c.candidate_id: c for c in result.root.candidates}
    return [by_id[s.candidate_id] for s in result.scores]


class FormulaTests(unittest.TestCase):
    """Synthetic rows: what the score means, without running a model."""

    def setUp(self):
        self.safe = fake_candidate("safe", 100, 100, targets=((9, 9),))
        self.risky = fake_candidate("risky", 75, 100, targets=((0, 0),))

    def score(self, candidates, samples, values, target=None):
        rows = [r for c in candidates for r in fake_rows(c, samples, values[c.candidate_id], target)]
        plain_scores = _complete_scores(candidates, samples, rows, target, m.F_ID)
        scores = rv.own_survival_scores(candidates, samples, rows, target, m.F_ID, 100)
        return rows, plain_scores, scores

    def test_exact_survival_times_survivor_mean_is_not_a_double_count(self):
        samples = bank((), (), ((0, 0),), (), (), ((0, 0),), (), ())  # 2 of 8 samples hold a mine on the target
        values = {"safe": [1] * 8, "risky": [1, 1, 0, Fraction(6, 5), 1, 0, Fraction(4, 5), 1]}
        _, plain_scores, scores = self.score([self.safe, self.risky], samples, values)
        survivors = [1, 1, Fraction(6, 5), 1, Fraction(4, 5), 1]
        self.assertEqual(scores[1].rollout_mean_x, Fraction(3, 4) * sum(survivors) / 6)
        self.assertEqual(scores[1].rollout_win_rate, Fraction(3, 4))
        # the unconditional mean already holds the two zeros; multiplying it by p would count the risk twice
        self.assertEqual(plain_scores[1].rollout_mean_x, sum(survivors) / 8)
        self.assertNotEqual(scores[1].rollout_mean_x, Fraction(3, 4) * plain_scores[1].rollout_mean_x)
        # the safe candidate keeps the plain mean
        self.assertEqual((scores[0].rollout_mean_x, scores[0].rollout_win_rate),
                         (plain_scores[0].rollout_mean_x, plain_scores[0].rollout_win_rate))
        self.assertEqual((scores[0].sample_count, scores[0].terminal_count, scores[0].pilot_id), (8, 8, m.F_ID))
        self.assertEqual((scores[1].sample_count, scores[1].terminal_count, scores[1].pilot_id), (8, 8, m.F_ID))

    def test_later_losses_stay_in_the_survivor_mean_as_zeros(self):
        # 6 survivors: 3 win with 1, 3 lose after surviving. A mean over the wins only would be 1.
        samples = bank((), (), ((0, 0),), (), (), ((0, 0),), (), ())
        values = {"safe": [1] * 8, "risky": [1, 0, 0, 1, 0, 0, 0, 1]}
        rows, plain_scores, scores = self.score([self.safe, self.risky], samples, values)
        risky_rows = rows[8:]
        later = [r for r, s in zip(risky_rows, samples) if not s.mines and r.outcome == "LOST"]
        at_once = [r for r, s in zip(risky_rows, samples) if s.mines]
        self.assertEqual((len(later), len(at_once)), (3, 2))
        self.assertTrue(all(r.f_call_indices for r in later) and not any(r.f_call_indices for r in at_once))
        self.assertEqual(scores[1].rollout_mean_x, Fraction(3, 4) * Fraction(3, 6))
        self.assertEqual(scores[1].rollout_win_rate, Fraction(3, 4) * Fraction(3, 6))
        self.assertNotEqual(scores[1].rollout_mean_x, Fraction(3, 4) * 1)   # wins-only mean
        self.assertEqual(plain_scores[1].rollout_mean_x, Fraction(3, 8))

    def test_failure_event_missed_by_the_bank_is_still_charged(self):
        samples = bank(*[()] * 8)  # no sampled layout has the mine although the exact risk is 1/4
        values = {"safe": [1] * 8, "risky": [Fraction(101, 100)] * 8}
        _, plain_scores, scores = self.score([self.safe, self.risky], samples, values)
        self.assertEqual(best([self.safe, self.risky], plain_scores), "risky")  # plain scores: looks risk free
        self.assertEqual(scores[1].rollout_mean_x, Fraction(3, 4) * Fraction(101, 100))
        self.assertEqual(scores[1].rollout_win_rate, Fraction(3, 4))
        self.assertEqual(best([self.safe, self.risky], scores), "safe")

    def test_large_gain_still_justifies_the_risk(self):
        samples = bank((), (), ((0, 0),), (), (), ((0, 0),), (), ())
        values = {"safe": [Fraction(1, 2)] * 8, "risky": [Fraction(6, 5)] * 8}
        _, _, scores = self.score([self.safe, self.risky], samples, values)
        self.assertEqual(scores[1].rollout_mean_x, Fraction(3, 4) * Fraction(6, 5))
        self.assertEqual(best([self.safe, self.risky], scores), "risky")  # a safe move does not exclude it

    def test_no_survivor_all_zero_and_no_target_hit(self):
        dead = bank(*[((0, 0),)] * 8)
        values = {"safe": [0] * 8, "risky": [1] * 8}
        target = Fraction(13, 10)
        _, plain_scores, scores = self.score([self.safe, self.risky], dead, values, target=target)
        self.assertEqual((scores[1].rollout_mean_x, scores[1].rollout_win_rate, scores[1].rollout_hit_rate),
                         (0, 0, 0))
        self.assertTrue(all(s.rollout_mean_x == 0 and s.rollout_hit_rate == 0 for s in scores))
        # everything is zero: the order falls through to the exact survival, as with plain scores
        self.assertEqual(best([self.safe, self.risky], scores, "M"), "safe")
        self.assertEqual(best([self.safe, self.risky], scores, "R"), "safe")
        self.assertEqual([s.rollout_hit_rate for s in plain_scores], [0, 0])
        without = self.score([self.safe, self.risky], dead, values)[2]
        self.assertEqual([s.rollout_hit_rate for s in without], [None, None])

    def test_no_survivor_of_one_candidate_leaves_the_others_scored(self):
        dead = bank(*[((0, 0),)] * 8)
        values = {"safe": [Fraction(1, 2)] * 8, "risky": [2] * 8}
        _, _, scores = self.score([self.safe, self.risky], dead, values)
        self.assertEqual((scores[0].rollout_mean_x, scores[1].rollout_mean_x), (Fraction(1, 2), 0))
        self.assertEqual(best([self.safe, self.risky], scores), "safe")

    def test_target_hits_use_the_same_rule(self):
        samples = bank((), (), ((0, 0),), (), (), ((0, 0),), (), ())
        values = {"safe": [1] * 8, "risky": [Fraction(7, 5), 1, 0, Fraction(3, 2), 1, 0, 0, 1]}
        _, plain_scores, scores = self.score([self.safe, self.risky], samples, values, target=Fraction(13, 10))
        self.assertEqual(plain_scores[1].rollout_hit_rate, Fraction(2, 8))
        self.assertEqual(scores[1].rollout_hit_rate, Fraction(3, 4) * Fraction(2, 6))
        self.assertEqual(scores[1].rollout_win_rate, Fraction(3, 4) * Fraction(5, 6))  # one survivor loses later
        self.assertEqual(best([self.safe, self.risky], scores, "R"), "risky")
        self.assertEqual(best([self.safe, self.risky], scores, "M"), "safe")

    def test_a_hit_score_is_positive_exactly_when_the_plain_one_is(self):
        # hits happen only in surviving rows, so reweighting never creates a hit that the bank lacks
        samples = bank((), (), ((0, 0),), (), (), ((0, 0),), (), ())
        target = Fraction(13, 10)
        for risky_values in ([1, 1, 0, 1, 1, 0, 1, 1], [Fraction(7, 5), 1, 0, 1, 1, 0, 1, 1], [0] * 8):
            values = {"safe": [1] * 8, "risky": risky_values}
            _, plain_scores, scores = self.score([self.safe, self.risky], samples, values, target=target)
            for a, b in zip(plain_scores, scores):
                self.assertEqual(a.rollout_hit_rate > 0, b.rollout_hit_rate > 0)
                self.assertEqual(a.rollout_mean_x > 0, b.rollout_mean_x > 0)

    def test_repeated_layouts_count_as_drawn(self):
        same = SimpleNamespace(rank=5, mines=())
        hit = SimpleNamespace(rank=7, mines=((0, 0),))
        samples = [same, same, same, hit, hit, same, same, same]
        values = {"safe": [1] * 8, "risky": [1, 1, 1, 0, 0, 2, 2, 2]}
        _, _, scores = self.score([self.safe, self.risky], samples, values)
        self.assertEqual(scores[1].rollout_mean_x, Fraction(3, 4) * Fraction(9, 6))

    def test_exhaustive_bank_gives_the_plain_scores(self):
        # all 8 worlds of a tiny posterior: the exact survival equals the survivor share of the bank
        samples = bank((), (), ((0, 0),), (), (), ((0, 0),), (), ())
        risky = fake_candidate("risky", 6, 8)
        safe = fake_candidate("safe", 8, 8, targets=((9, 9),))
        values = {"safe": [1, 0, 1, 1, 0, 1, 1, 1], "risky": [1, 2, 0, 0, 3, 0, 1, 1]}
        rows = [r for c in (safe, risky) for r in fake_rows(c, samples, values[c.candidate_id], Fraction(2))]
        plain_scores = _complete_scores((safe, risky), samples, rows, Fraction(2), m.F_ID)
        scores = rv.own_survival_scores((safe, risky), samples, rows, Fraction(2), m.F_ID, 8)
        self.assertEqual(scores, plain_scores)

    def test_rows_that_contradict_the_exact_event_are_rejected(self):
        samples = bank((), ((0, 0),))
        good = fake_rows(self.risky, samples, [1, 1])
        lying = [good[0], replace(good[0], sample_index=1, rank=1)]  # claims to survive the sampled mine
        with self.assertRaisesRegex(ValueError, "IMMEDIATE_SURVIVAL_ROW_MISMATCH"):
            rv.own_survival_scores((self.risky,), samples, lying, None, m.F_ID, 100)
        early = [replace(good[1], sample_index=0, rank=0), good[1]]  # an immediate loss where the target is safe
        with self.assertRaisesRegex(ValueError, "IMMEDIATE_SURVIVAL_ROW_MISMATCH"):
            rv.own_survival_scores((self.risky,), samples, early, None, m.F_ID, 100)
        other = [replace(good[0], candidate_id="someone-else"), good[1]]  # a row of another candidate
        with self.assertRaisesRegex(ValueError, "IMMEDIATE_SURVIVAL_ROW_MISMATCH"):
            rv.own_survival_scores((self.risky,), samples, other, None, m.F_ID, 100)
        wrong_p = replace_ns(self.risky, survival_probability=Fraction(1, 2))
        with self.assertRaisesRegex(ValueError, "OWN_SURVIVAL_SCORE_SURVIVAL"):
            rv.own_survival_scores((wrong_p,), samples, good, None, m.F_ID, 100)
        never = fake_candidate("never", 0, 100)
        with self.assertRaisesRegex(ValueError, "OWN_SURVIVAL_SCORE_SURVIVAL"):
            rv.own_survival_scores((never,), samples, fake_rows(never, samples, [1, 1]), None, m.F_ID, 100)
        with self.assertRaisesRegex(ValueError, "OWN_SURVIVAL_SCORE_BINDING"):
            rv.own_survival_scores((self.risky,), samples, good[:1], None, m.F_ID, 100)
        with self.assertRaisesRegex(ValueError, "OWN_SURVIVAL_SCORE_BINDING"):
            rv.own_survival_scores((self.risky,), [], [], None, m.F_ID, 100)
        # a candidate whose exact survival is 1 cannot have a sampled layout with a mine on its target
        claimed_safe = fake_candidate("claimed", 100, 100)
        with self.assertRaisesRegex(ValueError, "SAFE_CANDIDATE_DIED_IN_BANK"):
            rv.own_survival_scores((claimed_safe,), samples, fake_rows(claimed_safe, samples, [1, 1]), None, m.F_ID, 100)

    def test_applies_only_to_guessing_m_and_r_with_a_sampled_bank(self):
        self.assertTrue(rv.applies("M", True, 9, 8))
        self.assertTrue(rv.applies("R", True, 9, 8))
        self.assertTrue(rv.applies("M", True, 5, 4))
        for case in (("S", True, 9, 8), ("M", False, 9, 8), ("R", False, 9, 8), ("M", True, 8, 8),
                     ("M", True, 3, 8), ("M", 1, 9, 8), ("M", True, None, 8)):
            self.assertFalse(rv.applies(*case), case)
        self.assertEqual(rv.risky_candidates((self.safe, self.risky, fake_candidate("dead", 0, 100)), 100),
                         (self.risky,))
        self.assertEqual(rv.risky_candidates((self.safe,), 100), ())


class JointEventTests(unittest.TestCase):
    """Chords and flags: the joint survival event and the counted inputs, against brute force."""

    @classmethod
    def setUpClass(cls):
        cls.grid, cls.mines, cls.counted = CHORD_STATE
        cls.layouts = brute(cls.grid, cls.mines)
        cls.result = m.evaluate_model(request(CHORD_STATE))
        cls.total = cls.result.root.base.total_worlds
        cls.chosen = chosen_of(cls.result)

    def test_brute_force_agrees_with_the_exact_root(self):
        self.assertEqual(self.result.status, "COMPLETE", self.result.error)
        self.assertEqual(len(self.layouts), self.total)
        self.assertEqual(self.total, 10)
        kinds = Counter(c.kind for c in self.chosen)
        self.assertEqual((kinds["OPEN"], kinds["CHORD"]), (3, 1))
        for c in self.chosen:
            self.assertEqual(c.survival.worlds, sum(alive(c, layout) for layout in self.layouts))

    def test_chord_risk_is_the_joint_event_of_every_revealed_cell(self):
        chord = next(c for c in self.chosen if c.kind == "CHORD")
        self.assertEqual([a.action for a in chord.sequence], ["FLAG", "CHORD"])
        self.assertEqual((len(chord.targets), chord.immediate_input_cost), (4, 2))
        joint = Fraction(sum(alive(chord, layout) for layout in self.layouts), self.total)
        self.assertEqual(chord.survival_probability, joint)
        self.assertEqual(joint, Fraction(9, 10))
        self.assertTrue(rv.survives(chord, set()))
        for cell in chord.targets:
            self.assertFalse(rv.survives(chord, {cell}))
        self.assertTrue(rv.survives(chord, {(a.x, a.y) for a in chord.sequence if a.action == "FLAG"}))

    def test_correlated_chord_targets_use_the_joint_count_not_a_product(self):
        # A 1 with three closed neighbours: flag one, chord the other two. The chord survives
        # exactly when the flagged cell is the mine, so the two targets are not independent.
        grid, mines, counted = ((1, H, H, H), (H, H, H, H), (H, H, H, H)), 2, 1
        layouts = brute(grid, mines)
        self.assertEqual(len(layouts), 24)
        root = m.analyze_candidates(m.CandidateRequest(grid, mines))
        chord = next(c for c in root.candidates
                     if c.kind == "CHORD" and c.pivot == (0, 0) and c.final_flags == ((1, 0),))
        self.assertEqual(([a.action for a in chord.sequence], set(chord.targets)), (["FLAG", "CHORD"], {(0, 1), (1, 1)}))
        joint = Fraction(sum(alive(chord, layout) for layout in layouts), len(layouts))
        product = Fraction(1)
        for cell in chord.targets:
            product *= Fraction(sum(cell not in layout for layout in layouts), len(layouts))
        self.assertEqual((joint, product), (Fraction(1, 3), Fraction(4, 9)))
        self.assertEqual(chord.survival_probability, joint)
        query = m.ModelRequest(grid, mines, counted, "M", True)
        samples = sample_posterior(PosteriorRequest(grid, mines, counted, 5, 8)).samples
        cache, rows = m._FollowupCache(64), []
        for index, sample in enumerate(samples):
            row, stopped = m._row(query, chord, sample, index, m._Budget(query, None), cache, [])
            self.assertIsNone(stopped)
            rows.append(row)
            if alive(chord, sample.mines):
                self.assertEqual(row.actions[:2], chord.sequence)
                self.assertFalse(row.outcome == "LOST" and not row.f_call_indices)
            else:  # the flag and the failed chord are both counted inputs
                self.assertEqual((row.outcome, row.added_inputs, row.actions), ("LOST", 2, chord.sequence))
        dead = sum(not alive(chord, s.mines) for s in samples)
        self.assertTrue(0 < dead < 8)
        score = rv.own_survival_scores((chord,), samples, rows, None, m.F_ID, 24)[0]
        self.assertEqual((score.rollout_mean_x, score.rollout_win_rate, score.rollout_hit_rate),
                         own_survival(chord, rows, samples, joint))
        self.assertEqual(score.rollout_mean_x,
                         Fraction(1, 3) * sum((r.value_x for r in rows), Fraction(0)) / (8 - dead))

    def test_two_flag_chord_counts_every_input_and_fails_on_its_joint_event(self):
        # A 2 with five closed neighbours and exactly two mines among them: flag two, chord three.
        grid, mines, counted = ((H, 2, H), (H, H, H)), 2, 1
        layouts = brute(grid, mines)
        self.assertEqual(len(layouts), 10)
        root = m.analyze_candidates(m.CandidateRequest(grid, mines))
        chord = next(c for c in root.candidates if c.kind == "CHORD" and c.final_flags == ((0, 0), (2, 0)))
        self.assertEqual([a.action for a in chord.sequence], ["FLAG", "FLAG", "CHORD"])
        self.assertEqual((chord.immediate_input_cost, set(chord.targets)), (3, {(0, 1), (1, 1), (2, 1)}))
        joint = Fraction(sum(alive(chord, layout) for layout in layouts), len(layouts))
        product = Fraction(1)
        for cell in chord.targets:
            product *= Fraction(sum(cell not in layout for layout in layouts), len(layouts))
        self.assertEqual((joint, product), (Fraction(1, 10), Fraction(27, 125)))
        self.assertEqual(chord.survival_probability, joint)
        self.assertEqual(root.base.total_worlds, 10)
        query = m.ModelRequest(grid, mines, counted, "M", True)
        samples = sample_posterior(PosteriorRequest(grid, mines, counted, 0, 8), ranks=tuple(range(10))).samples
        cache, rows = m._FollowupCache(64), []
        for index, sample in enumerate(samples):
            row, stopped = m._row(query, chord, sample, index, m._Budget(query, None), cache, [])
            self.assertIsNone(stopped)
            replay = oracle.replay(grid, mines, sample.mines, [(a.action, a.x, a.y) for a in row.actions], counted)
            self.assertEqual((replay["outcome"], replay["X"], replay["added_inputs"]),
                             (row.outcome, row.value_x, row.added_inputs))
            self.assertEqual((row.added_inputs, row.actions, row.f_call_indices), (3, chord.sequence, ()))
            if alive(chord, sample.mines):   # the right two flags: the chord opens everything that is left
                self.assertEqual((row.outcome, row.value_x), ("WON", Fraction(row.virtual_b, counted + 3)))
            else:                            # any wrong flag: both flags and the chord were still spent
                self.assertEqual((row.outcome, row.value_x), ("LOST", 0))
            rows.append(row)
        self.assertEqual(sum(r.outcome == "WON" for r in rows), 1)
        score = rv.own_survival_scores((chord,), samples, rows, None, m.F_ID, 10)[0]
        won = next(r for r in rows if r.outcome == "WON")
        self.assertEqual(score.rollout_mean_x, Fraction(1, 10) * won.value_x)   # = the exhaustive mean
        self.assertEqual(score.rollout_mean_x, sum((r.value_x for r in rows), Fraction(0)) / 10)
        # a bank that happens to hold the winning layout three times in eight still charges 9/10
        skewed = [samples[rows.index(won)]] * 3 + [s for s in samples if s is not samples[rows.index(won)]][:5]
        skewed_rows = [replace(rows[samples.index(s)], sample_index=i) for i, s in enumerate(skewed)]
        skewed_score = rv.own_survival_scores((chord,), skewed, skewed_rows, None, m.F_ID, 10)[0]
        self.assertEqual(skewed_score.rollout_mean_x, Fraction(1, 10) * won.value_x)
        self.assertEqual(plain(skewed_rows)[0], Fraction(3, 8) * won.value_x)


class ModelTests(unittest.TestCase):
    """The real model on small public states."""

    @classmethod
    def setUpClass(cls):
        cls.layouts = {name: brute(state[0], state[1]) for name, state in
                       (("chord", CHORD_STATE), ("flag", FLAG_STATE))}
        cls.runs = {}
        for name, state in (("chord", CHORD_STATE), ("flag", FLAG_STATE)):
            for mode in ("M", "R"):
                for seed in range(6):
                    cls.runs[name, mode, seed] = m.evaluate_model(
                        request(state, mode, seed, target=Fraction(11, 10) if mode == "R" else None))

    def test_identity(self):
        self.assertEqual(m.MODEL_ID, MODEL_ID)
        for name in ("EXPERIMENT_VARIANT", "EXPERIMENT_ID", "LAST_EXPERIMENT_TRACE"):
            self.assertFalse(hasattr(m, name), name)
        for (name, mode, seed), result in self.runs.items():
            state = CHORD_STATE if name == "chord" else FLAG_STATE
            query = request(state, mode, seed, target=Fraction(11, 10) if mode == "R" else None)
            self.assertEqual(result.status, "COMPLETE", (name, mode, seed, result.reason, result.error))
            self.assertEqual(result.model_id, MODEL_ID)
            self.assertEqual(result.request_id, query.identity)
            self.assertEqual(query.identity, public_digest((MODEL_ID, query)))
            self.assertNotEqual(query.identity, public_digest(
                ("RUNTIME_COMMON_POSTERIOR_THEN_PUBLIC_F_V3_OBSERVATION_REUSE", query)))
            self.assertEqual(result.reason, "COMPLETE_COMMON_BANK_THEN_F")
            self.assertTrue(result.usage.accounting_complete)

    def test_scores_are_exact_survival_times_survivor_mean(self):
        risky_seen = 0
        for (name, mode, seed), result in self.runs.items():
            layouts = self.layouts[name]
            target = Fraction(11, 10) if mode == "R" else None
            samples = result.posterior.samples
            for sample in samples:
                self.assertIn(frozenset(sample.mines), set(layouts))
            for candidate, score in zip(chosen_of(result), result.scores):
                rows = [r for r in result.rows if r.candidate_id == candidate.candidate_id]
                exact_p = Fraction(sum(alive(candidate, layout) for layout in layouts), len(layouts))
                self.assertEqual(exact_p, candidate.survival_probability)
                risky_seen += exact_p < 1
                self.assertEqual((score.rollout_mean_x, score.rollout_win_rate, score.rollout_hit_rate),
                                 own_survival(candidate, rows, samples, exact_p, target), (name, mode, seed))
                self.assertEqual((score.sample_count, score.terminal_count, score.pilot_id),
                                 (len(samples), len(samples), result.followup_id))
                if exact_p == 1:
                    self.assertEqual((score.rollout_mean_x, score.rollout_win_rate, score.rollout_hit_rate),
                                     plain(rows, target))
        self.assertGreater(risky_seen, 0)

    def test_bank_is_the_ordinary_common_bank(self):
        for (name, mode, seed), result in self.runs.items():
            state = CHORD_STATE if name == "chord" else FLAG_STATE
            ordinary = sample_posterior(PosteriorRequest(state[0], state[1], state[2], seed, 8))
            self.assertEqual(result.posterior.sampling_kind, "WITH_REPLACEMENT")
            self.assertEqual(result.posterior.samples, ordinary.samples)
            self.assertEqual(result.usage.sampler_work, ordinary.diagnostics.work)
            used = result.root.diagnostics   # no exact count beyond the root analysis
            self.assertEqual((result.usage.unit4_calls, result.usage.unit4_work), (used.backend_calls, used.backend_work))

    def test_selection_is_the_unchanged_order_on_these_scores(self):
        for (name, mode, seed), result in self.runs.items():
            state = CHORD_STATE if name == "chord" else FLAG_STATE
            eligible, chosen, _ = _shortlist(result.root, request(state, mode, seed))
            index = {c.candidate_id: i for i, c in enumerate(eligible)}
            by_id = {s.candidate_id: s for s in result.scores}
            expected = max(chosen, key=lambda c: model_order(by_id[c.candidate_id], c.survival_probability,
                                                             index[c.candidate_id], mode))
            self.assertEqual(result.selected_candidate_id, expected.candidate_id)
            self.assertEqual(result.sequence, expected.sequence)

    def test_flag_inputs_are_counted_and_a_chord_fails_exactly_on_its_joint_event(self):
        seen_alive = 0
        for (name, mode, seed), result in self.runs.items():
            state = CHORD_STATE if name == "chord" else FLAG_STATE
            for candidate in chosen_of(result):
                if candidate.kind != "CHORD":
                    continue
                for row in (r for r in result.rows if r.candidate_id == candidate.candidate_id):
                    sample = result.posterior.samples[row.sample_index]
                    replay = oracle.replay(state[0], state[1], sample.mines,
                                           [(a.action, a.x, a.y) for a in row.actions], state[2])
                    self.assertEqual((replay["outcome"], replay["X"], replay["added_inputs"]),
                                     (row.outcome, row.value_x, row.added_inputs))
                    self.assertEqual(row.actions[:len(candidate.sequence)], candidate.sequence)
                    if alive(candidate, sample.mines):
                        seen_alive += 1
                        self.assertFalse(row.outcome == "LOST" and not row.f_call_indices)
                        if row.outcome == "WON":  # every flag and the chord are in the denominator
                            self.assertEqual(row.value_x, Fraction(row.virtual_b, state[2] + row.added_inputs))
                            self.assertGreaterEqual(row.added_inputs, len(candidate.sequence))
                    else:
                        self.assertEqual((row.outcome, row.value_x, row.added_inputs, row.f_call_indices),
                                         ("LOST", 0, len(candidate.sequence), ()))
        self.assertGreater(seen_alive, 0)

    def test_bank_that_missed_a_failure_event_still_charges_the_exact_risk(self):
        missed = 0
        for seed in range(40):
            result = m.evaluate_model(request(FLAG_STATE, "M", seed))
            samples = result.posterior.samples
            for candidate, score in zip(chosen_of(result), result.scores):
                if candidate.survival_probability == 1 or any(not alive(candidate, s.mines) for s in samples):
                    continue
                missed += 1  # the bank of this seed holds no layout in which this candidate dies
                rows = [r for r in result.rows if r.candidate_id == candidate.candidate_id]
                self.assertEqual(score.rollout_mean_x, candidate.survival_probability * plain(rows)[0])
                if plain(rows)[0] > 0:
                    self.assertLess(score.rollout_mean_x, plain(rows)[0])
            if missed >= 6:
                break
        self.assertGreaterEqual(missed, 6)

    def test_candidate_without_a_sampled_survivor_scores_zero_in_the_model(self):
        layouts = brute(RARE_SURVIVOR_STATE[0], RARE_SURVIVOR_STATE[1])
        self.assertEqual(len(layouts), 14)
        found = 0
        for seed in range(12):
            for mode in ("M", "R"):
                result = m.evaluate_model(request(RARE_SURVIVOR_STATE, mode, seed))
                self.assertEqual(result.status, "COMPLETE", (seed, mode, result.reason, result.error))
                self.assertEqual(result.root.base.total_worlds, 14)
                samples = result.posterior.samples
                for candidate, score in zip(chosen_of(result), result.scores):
                    exact_p = Fraction(sum(alive(candidate, layout) for layout in layouts), 14)
                    self.assertEqual(exact_p, candidate.survival_probability)
                    if any(alive(candidate, s.mines) for s in samples):
                        continue
                    found += 1
                    self.assertEqual(exact_p, Fraction(1, 7))
                    self.assertEqual([a.action for a in candidate.sequence], ["FLAG", "FLAG", "CHORD"])
                    self.assertEqual((score.rollout_mean_x, score.rollout_win_rate), (0, 0))
                    if mode == "R":
                        self.assertEqual(score.rollout_hit_rate, 0)
                    rows = [r for r in result.rows if r.candidate_id == candidate.candidate_id]
                    self.assertTrue(all((r.outcome, r.added_inputs, r.f_call_indices) == ("LOST", 3, ()) for r in rows))
                    self.assertNotEqual(result.selected_candidate_id, candidate.candidate_id)
                    self.assertEqual(result.information, "COMPLETE_NONZERO")
        self.assertGreater(found, 0)  # exact chance of no survivor in 8 draws is (6/7)^8, about 0.29 per seed

    def test_unreachable_target_falls_back_to_the_mean_order(self):
        for state in (CHORD_STATE, FLAG_STATE):
            mean = m.evaluate_model(request(state, "M", 2))
            high = m.evaluate_model(request(state, "R", 2, target=Fraction(100)))
            self.assertEqual(high.target_status, "NO_HIT_EVIDENCE_MEAN_X_TIEBREAK")
            self.assertTrue(all(s.rollout_hit_rate == 0 for s in high.scores))
            self.assertEqual(high.selected_candidate_id, mean.selected_candidate_id)
            self.assertEqual([(s.rollout_mean_x, s.rollout_win_rate) for s in high.scores],
                             [(s.rollout_mean_x, s.rollout_win_rate) for s in mean.scores])
            low = m.evaluate_model(request(state, "R", 2, target=Fraction(1, 100)))
            self.assertEqual(low.target_status, "POSITIVE_MODEL_HIT")
            self.assertEqual([s.rollout_hit_rate for s in low.scores], [s.rollout_win_rate for s in low.scores])

    def test_guard_paths_keep_the_plain_scores(self):
        witness = (((H, 1, H), (H, H, FL)), 1, 2)  # 3 worlds: enumerated bank
        no_safe = (((1, H, H, H), (H, H, H, H), (H, H, H, H)), 2, 1)  # 24 worlds, no proven-safe cell
        cases = [request(CHORD_STATE, "S"), request(CHORD_STATE, "M", allow_guess=False),
                 request(CHORD_STATE, "R", allow_guess=False), request(FLAG_STATE, "S", 3),
                 request(witness, "M"), request(witness, "R"), request(no_safe, "S")]
        risky_scored_in_s = 0
        with mock.patch.object(m, "own_survival_scores", side_effect=AssertionError("must not be called")):
            for query in cases:
                result = m.evaluate_model(query)
                self.assertEqual(result.status, "COMPLETE", (query.mode, result.reason, result.error))
                if query.mode == "S" and query.observation == no_safe[0]:
                    # S guesses the least risky cell here: a sampled bank with risky candidates, plain scores
                    self.assertEqual(result.posterior.sampling_kind, "WITH_REPLACEMENT")
                    risky_scored_in_s += sum(c.survival_probability < 1 for c in chosen_of(result))
                self.assertIn(result.posterior.sampling_kind, ("WITH_REPLACEMENT", "SMALL_POSTERIOR_ENUMERATED"))
                if result.posterior.sampling_kind == "WITH_REPLACEMENT":
                    ordinary = sample_posterior(PosteriorRequest(query.observation, query.num_mines,
                                                                 query.counted_inputs, query.planning_seed, 8))
                    self.assertEqual(result.posterior.samples, ordinary.samples)
                for score in result.scores:
                    rows = [r for r in result.rows if r.candidate_id == score.candidate_id]
                    self.assertEqual((score.rollout_mean_x, score.rollout_win_rate, score.rollout_hit_rate),
                                     plain(rows, query.target))
                if not query.allow_guess:
                    by_id = {c.candidate_id: c for c in result.root.candidates}
                    self.assertTrue(all(by_id[s.candidate_id].survival_probability == 1 for s in result.scores))
        self.assertGreater(risky_scored_in_s, 0)
        self.assertEqual(m.evaluate_model(request(witness, "M")).posterior.sampling_kind, "SMALL_POSTERIOR_ENUMERATED")

    def test_guessing_on_a_sampled_bank_with_only_safe_candidates_keeps_the_plain_scores(self):
        narrow = m.ModelLimits(**NARROW)
        for mode in ("M", "R"):
            with mock.patch.object(m, "own_survival_scores", side_effect=AssertionError("must not be called")):
                result = m.evaluate_model(request(SAFE_PAIR_STATE, mode, 1, limits=narrow))
            self.assertEqual(result.status, "COMPLETE", (mode, result.reason, result.error))
            self.assertEqual(result.posterior.sampling_kind, "WITH_REPLACEMENT")
            self.assertEqual(result.root.base.total_worlds, 2100)
            self.assertTrue(rv.applies(mode, True, result.root.base.total_worlds, narrow.samples))
            chosen = chosen_of(result)
            self.assertEqual(len(chosen), 2)
            self.assertTrue(all(c.survival_probability == 1 for c in chosen))
            self.assertEqual(rv.risky_candidates(chosen, result.root.base.total_worlds), ())
            target = Fraction(13, 10) if mode == "R" else None
            for score in result.scores:
                rows = [r for r in result.rows if r.candidate_id == score.candidate_id]
                self.assertEqual((score.rollout_mean_x, score.rollout_win_rate, score.rollout_hit_rate),
                                 plain(rows, target))
        # the same public state with the wider shortlist holds risky candidates and takes the new scores
        wide = m.evaluate_model(request(SAFE_PAIR_STATE, "M", 1))
        self.assertEqual(wide.status, "COMPLETE", (wide.reason, wide.error))
        self.assertEqual(len(rv.risky_candidates(chosen_of(wide), wide.root.base.total_worlds)), 2)
        for candidate, score in zip(chosen_of(wide), wide.scores):
            rows = [r for r in wide.rows if r.candidate_id == candidate.candidate_id]
            self.assertEqual((score.rollout_mean_x, score.rollout_win_rate, score.rollout_hit_rate),
                             own_survival(candidate, rows, wide.posterior.samples, candidate.survival_probability))

    def test_cancel_and_limits_stay_atomic(self):
        base = m.ModelLimits()
        for limits, reason in ((replace(base, sampler_work=0), "SAMPLER_WORK_LIMIT"), (replace(base, rows=0), "MATRIX_LIMIT"),
                               (replace(base, f_lookups=0), "F_LOOKUPS_LIMIT"), (replace(base, max_seconds=0), "TIME_LIMIT"),
                               (replace(base, virtual_inputs=0), "VIRTUAL_INPUTS_LIMIT")):
            result = m.evaluate_model(request(CHORD_STATE, limits=limits))
            self.assertEqual((result.status, result.reason), ("RESOURCE_LIMIT", reason), result.error)
            self.assertEqual((result.sequence, result.scores, result.selected_candidate_id), ((), (), None))
            self.assertEqual(result.information, "INCOMPLETE_NO_INFORMATION")
            self.assertTrue(result.usage.accounting_complete)
        self.assertEqual(m.evaluate_model(request(CHORD_STATE), cancelled=lambda: True).status, "CANCELLED")
        self.assertEqual(m.evaluate_model(request(CHORD_STATE), cancelled=lambda: 1).status, "ERROR")
        calls = []

        def late():
            calls.append(1)
            return len(calls) > 40

        result = m.evaluate_model(request(CHORD_STATE), cancelled=late)
        self.assertEqual((result.status, result.sequence, result.scores), ("CANCELLED", (), ()))

    def test_model_selection_keeps_the_delivery_binding(self):
        grid, mines, counted = FLAG_STATE
        for mode, allow_guess in (("M", True), ("R", True), ("M", False), ("S", True)):
            policy = RuntimePolicy()
            query = RuntimeRequest(grid, mines, counted, mode, allow_guess, Fraction(13, 10) if mode == "R" else None,
                                   limits=RuntimeLimits())
            proposal = policy.choose(query)
            self.assertIsNone(proposal.error)
            self.assertEqual(proposal.decision_source, "MODEL", (mode, allow_guess, proposal.status, proposal.reason))
            self.assertEqual(proposal.model.model_id, MODEL_ID)
            delivery = RuntimeDelivery(policy, query, proposal)
            selected = next(c for c in proposal.model.root.candidates
                            if c.candidate_id == proposal.model.selected_candidate_id)
            self.assertEqual(delivery.survival, selected.survival_probability)
            self.assertEqual(delivery.source, "MODEL")
            if not allow_guess or mode == "S":
                self.assertEqual(delivery.survival, 1)
            self.assertEqual(policy.claim(proposal, query), ())  # consumed once
            policy.close()


class ConsistencyErrorTests(unittest.TestCase):
    """A violated score check ends as an error. It is never replaced by plain scores or by F."""

    def query(self, mode="M"):
        grid, mines, counted = FLAG_STATE
        return RuntimeRequest(grid, mines, counted, mode, True, Fraction(13, 10) if mode == "R" else None,
                              limits=RuntimeLimits())

    def test_score_check_failure_is_a_model_error_without_selection(self):
        for message in ("IMMEDIATE_SURVIVAL_ROW_MISMATCH", "OWN_SURVIVAL_SCORE_SURVIVAL", "SAFE_CANDIDATE_DIED_IN_BANK",
                        "OWN_SURVIVAL_SCORE_BINDING"):
            with mock.patch.object(m, "own_survival_scores", side_effect=ValueError(message)) as scorer:
                result = m.evaluate_model(request(FLAG_STATE))
            self.assertEqual(scorer.call_count, 1)
            self.assertEqual((result.status, result.reason), ("ERROR", "MODEL_ERROR"))
            self.assertEqual(result.error, "ValueError: " + message)
            self.assertEqual((result.sequence, result.scores, result.selected_candidate_id), ((), (), None))
            self.assertEqual(result.information, "INCOMPLETE_NO_INFORMATION")
            self.assertTrue(result.usage.accounting_complete)

    def test_real_row_contradiction_is_rejected_inside_the_model(self):
        # one row of a risky candidate is turned into a later loss in a layout where its target is a mine
        real_row = m._row
        state = {"changed": 0}

        def lying_row(query, candidate, sample, index, budget, cache, calls):
            row, stopped = real_row(query, candidate, sample, index, budget, cache, calls)
            if (stopped is None and not state["changed"] and row.outcome == "LOST" and not row.f_call_indices
                    and set(candidate.targets) & set(sample.mines)):
                state["changed"] += 1
                row = replace(row, added_inputs=len(candidate.sequence) + 1)
            return row, stopped

        seed = next(s for s in range(40) if any(
            c.survival_probability < 1 and any(set(c.targets) & set(x.mines) for x in r.posterior.samples)
            for r in (m.evaluate_model(request(FLAG_STATE, "M", s)),) for c in chosen_of(r)))
        with mock.patch.object(m, "_row", side_effect=lying_row):
            result = m.evaluate_model(request(FLAG_STATE, "M", seed))
        self.assertEqual(state["changed"], 1)
        self.assertEqual((result.status, result.reason, result.error),
                         ("ERROR", "MODEL_ERROR", "ValueError: IMMEDIATE_SURVIVAL_ROW_MISMATCH"))
        self.assertEqual((result.sequence, result.scores, result.selected_candidate_id), ((), (), None))

    def test_policy_reports_the_error_and_does_not_fall_back_to_f(self):
        for mode in ("M", "R"):
            # the existing contract: an error inside the plain score validation blocks the policy
            for name in ("own_survival_scores", "_complete_scores"):
                policy = RuntimePolicy()
                with mock.patch.object(m, name, side_effect=ValueError("INJECTED_SCORE_CHECK")), \
                        mock.patch("stage4_runtime_policy.choose_followup",
                                   side_effect=AssertionError("F must not replace a model error")) as followup:
                    proposal = policy.choose(self.query(mode))
                self.assertEqual(followup.call_count, 0)
                self.assertEqual((proposal.status, proposal.reason), ("ERROR", "MODEL_BLOCKED:MODEL_ERROR"), (mode, name))
                self.assertEqual((tuple(proposal.sequence), proposal.decision_source), ((), None))
                self.assertEqual(proposal.model_status, "ERROR")
                self.assertEqual(proposal.model.error, "ValueError: INJECTED_SCORE_CHECK")
                self.assertEqual(proposal.model.scores, ())
                self.assertTrue(proposal.usage.accounting_complete)
                policy.close()
        # an ordinary resource limit still uses the direct F, as before
        policy = RuntimePolicy()
        tight = RuntimeLimits(model=replace(m.ModelLimits(), rows=0))
        grid, mines, counted = FLAG_STATE
        proposal = policy.choose(RuntimeRequest(grid, mines, counted, "M", True, None, limits=tight))
        self.assertEqual((proposal.model_status, proposal.decision_source), ("RESOURCE_LIMIT", "F"))
        policy.close()


if __name__ == "__main__":
    unittest.main()
