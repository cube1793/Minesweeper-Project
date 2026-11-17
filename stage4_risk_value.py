"""Exact immediate-survival scoring of M/R model candidates (own survival).

Used by stage4_runtime_model for mode M or R with guessing allowed, a sampled
(not enumerated) bank and at least one shortlisted candidate whose exact joint
immediate survival is below 1. Every other request keeps the plain scores.

score(c) = p_c * (mean over the bank samples in which c's own first action
survives). p_c is the exact probability that every cell the candidate reveals
is safe: a joint event for a chord, never a product of per-cell values. A
sample in which c dies at once is not added again as a zero, because that
probability is already the exact factor p_c. A survivor that loses later stays
in the mean as a zero. The win rate and the target hit rate use the same rule.
Without a sampled survivor the three scores are 0.

The bank, the rows, the order of candidates and every limit are untouched.
Only public quantities enter: candidate targets, exact world counts and the
sampled layouts the model evaluator already owns.
"""
from fractions import Fraction

from stage4_policy import ModelScore


def applies(mode, allow_guess, total_worlds, samples):
    """S, guess-off and enumerated banks keep the plain scores."""
    return (mode in ("M", "R") and allow_guess is True
            and type(total_worlds) is int and total_worlds > samples)


def risky_candidates(chosen, total_worlds):
    """Shortlisted candidates whose exact joint immediate survival is in (0, 1)."""
    return tuple(c for c in chosen if 0 < c.survival.worlds < total_worlds)


def survives(candidate, mines):
    """The candidate's own reveal targets are all safe in this layout (joint event)."""
    return not any(cell in mines for cell in candidate.targets)


def own_survival_scores(chosen, samples, rows, target, followup_id, total_worlds):
    """Model scores from exact own survival and the mean over own survivors.

    A row of a sample in which the candidate's targets hold a mine must be the
    immediate loss the exact event predicts, and no other row may be one.
    """
    count = len(samples)
    if not count or len(rows) != len(chosen) * count:
        raise ValueError("OWN_SURVIVAL_SCORE_BINDING")
    layouts = [set(sample.mines) for sample in samples]
    scores = []
    for index, candidate in enumerate(chosen):
        group = rows[index * count:(index + 1) * count]
        survival = Fraction(candidate.survival.worlds, total_worlds)
        if survival != candidate.survival_probability or not 0 < survival <= 1:
            raise ValueError("OWN_SURVIVAL_SCORE_SURVIVAL")
        survivors = 0
        x_sum = Fraction(0)
        wins = hits = 0
        for row, mines in zip(group, layouts):
            alive = survives(candidate, mines)
            immediate = (row.outcome == "LOST" and not row.f_call_indices
                         and row.added_inputs <= len(candidate.sequence))
            if row.candidate_id != candidate.candidate_id or alive is immediate:
                raise ValueError("IMMEDIATE_SURVIVAL_ROW_MISMATCH")
            if not alive:
                continue
            survivors += 1
            x_sum += row.value_x
            wins += row.outcome == "WON"
            hits += row.hit is True
        if survival == 1 and survivors != count:
            raise ValueError("SAFE_CANDIDATE_DIED_IN_BANK")
        if survivors:
            mean = survival * x_sum / survivors
            win = survival * Fraction(wins, survivors)
            hit = survival * Fraction(hits, survivors)
        else:  # no sampled survivor: no conditional information
            mean = win = hit = Fraction(0)
        scores.append(ModelScore(candidate.candidate_id, mean, win, hit if target is not None else None,
                                 count, count, followup_id))
    return tuple(scores)
