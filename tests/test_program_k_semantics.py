"""Slice-1 synthetic implementation verification, not E0 qualification.

All observations are constructed public states. No Engine, hidden layout,
physical policy, complete-game runner, timing-table scan, or corpus is used.
Coordinates are stored as (x, y); ordered expectations use the (y, x) key.
"""

import runpy
import sys
import types
import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch

from core_engine import CellState, GameStatus
from experiments import program_k_capability as capability
from experiments import program_k_oracles as oracles
from experiments.program_k_capability import KIntegrityError, KLocalSession
from experiments.program_k_oracles import (
    LocalMineCertificate,
    OracleANotEvaluated,
    PublicProofError,
    enumerate_public_worlds,
    verify_local_certificate,
)


H = CellState.HIDDEN.value
F = CellState.FLAGGED.value
PLAYING = GameStatus.PLAYING


def certificate(observation, num_mines, clue, target, retained=()):
    """Only raw public premises; expected residuals are never supplied."""
    return LocalMineCertificate(
        observation=observation,
        num_mines=num_mines,
        clue=clue,
        target=target,
        retained_mines=frozenset(retained),
        status=PLAYING,
    )


class UntouchableObservation:
    """Any observation access before terminal-status rejection is a failure."""

    def __len__(self):
        raise AssertionError("Terminal observation was inspected")

    def __getitem__(self, item):
        raise AssertionError("Terminal observation was inspected")

    def __iter__(self):
        raise AssertionError("Terminal observation was inspected")


class ProgramKLocalSemanticsTests(unittest.TestCase):
    def test_new_game_has_empty_immutable_mine_state(self):
        session = KLocalSession(3, 1, 1)

        self.assertEqual(session.M, frozenset())
        self.assertIsInstance(session.M, frozenset)
        with self.assertRaises(AttributeError):
            session.M = frozenset({(0, 0)})
        with self.assertRaises(AttributeError):
            session.M.add((0, 0))

    def test_a_no_new_mines(self):
        session = KLocalSession(3, 1, 1)

        result = session.analyze_local([[H, 1, H]], status=PLAYING)

        self.assertEqual(result.acquired_mines, frozenset())
        self.assertEqual(result.S_first, frozenset())
        self.assertEqual(result.S_second_all, frozenset())
        self.assertEqual(result.S_new, frozenset())
        self.assertEqual(result.S_current, frozenset())
        self.assertEqual(session.M, frozenset())
        self.assertEqual(result.before.U, {(0, 0), (2, 0)})
        self.assertEqual(result.after, result.before)

    def test_b_historical_witness_unlocks_safe_without_physical_flag(self):
        observation = [[1, H, 1, H]]
        session = KLocalSession(4, 1, 1)

        result = session.analyze_local(observation, status=PLAYING)

        self.assertEqual(result.acquired_mines, {(1, 0)})
        self.assertEqual(result.S_first, frozenset())
        self.assertEqual(result.S_second_all, {(3, 0)})
        self.assertEqual(result.S_new, {(3, 0)})
        self.assertEqual(result.S_current, {(3, 0)})
        self.assertEqual(result.before.M, frozenset())
        self.assertEqual(result.after.M, {(1, 0)})
        self.assertEqual(result.after.H, {(1, 0), (3, 0)})
        self.assertEqual(result.after.P, frozenset())
        self.assertEqual(observation, [[1, H, 1, H]])
        self.assertEqual(session.M, {(1, 0)})
        self.assertEqual({proof.target for proof in result.certificates}, {(1, 0)})
        for proof in result.certificates:
            checked = verify_local_certificate(proof)
            self.assertEqual(checked.target, (1, 0))
            self.assertEqual(checked.residual, 1)

    def test_c_one_clue_acquires_all_mines_simultaneously(self):
        result = KLocalSession(4, 1, 2).analyze_local(
            [[H, 2, H, H]], status=PLAYING
        )

        self.assertEqual(result.acquired_mines, {(0, 0), (2, 0)})
        self.assertEqual(result.after.M, {(0, 0), (2, 0)})
        self.assertEqual(result.after.U, {(3, 0)})
        self.assertEqual(result.after.b, 0)
        self.assertEqual(result.S_current, frozenset())
        self.assertEqual(
            {proof.target for proof in result.certificates}, {(0, 0), (2, 0)}
        )
        for proof in result.certificates:
            self.assertEqual(proof.retained_mines, frozenset())
            self.assertEqual(verify_local_certificate(proof).residual, 2)

    def test_d_complete_first_pass_collects_both_clues_before_normalizing(self):
        observation = [[1, H, 1, H, H, 1, H, 1]]
        result = KLocalSession(8, 1, 2).analyze_local(observation, status=PLAYING)

        self.assertEqual(result.acquired_mines, {(1, 0), (6, 0)})
        self.assertEqual(result.S_first, frozenset())
        self.assertEqual(result.S_second_all, {(3, 0), (4, 0)})
        self.assertEqual(result.S_new, {(3, 0), (4, 0)})
        self.assertEqual(result.S_current, {(3, 0), (4, 0)})
        self.assertEqual(result.after.b, 0)
        for proof in result.certificates:
            self.assertEqual(proof.retained_mines, frozenset())
            verify_local_certificate(proof)

    def test_e_safe_cells_remain_unresolved_and_are_not_substituted(self):
        result = KLocalSession(4, 1, 1).analyze_local(
            [[0, H, 1, H]], status=PLAYING
        )

        self.assertEqual(result.S_first, {(1, 0)})
        self.assertEqual(result.S_second_all, {(1, 0)})
        self.assertEqual(result.S_new, frozenset())
        self.assertEqual(result.S_current, {(1, 0)})
        self.assertEqual(result.acquired_mines, frozenset())
        self.assertEqual(result.after.U, {(1, 0), (3, 0)})
        clue = next(item for item in result.after.constraints if item.source == (2, 0))
        self.assertEqual(clue.Uc, {(1, 0), (3, 0)})
        self.assertEqual(clue.rc, 1)
        self.assertNotIn((3, 0), result.after.M)

    def test_f_materialization_retains_mine_and_counts_overlap_once(self):
        session = KLocalSession(4, 1, 1)
        first = session.analyze_local([[1, H, 1, H]], status=PLAYING)

        result = session.analyze_local([[1, F, 1, H]], status=PLAYING)

        self.assertEqual(session.M, {(1, 0)})
        self.assertEqual(result.after.P, {(1, 0)})
        self.assertEqual(result.after.M, {(1, 0)})
        self.assertEqual(result.after.J, {(1, 0)})
        self.assertEqual(result.after.H, {(3, 0)})
        self.assertEqual(result.after.U, {(3, 0)})
        self.assertEqual(result.after.b, 0)
        self.assertEqual(result.acquired_mines, frozenset())
        self.assertEqual(result.S_current, {(3, 0)})
        for clue in result.after.constraints:
            self.assertEqual(clue.fixed_mines, {(1, 0)})
            self.assertEqual(clue.rc, 0)
        logical = enumerate_public_worlds(
            [[1, H, 1, H]], 1, status=PLAYING,
            logical_mines=first.after.M, proofs=first.certificates,
        )
        overlap = enumerate_public_worlds(
            [[1, F, 1, H]], 1, status=PLAYING,
            logical_mines=session.M, proofs=first.certificates,
        )
        self.assertEqual(logical, overlap)
        self.assertEqual(overlap.mine_worlds, (((3, 0), 0),))

    def test_g_invalid_residual_budget_and_conflicting_facts_fail_closed(self):
        cases = (
            (2, 1, 1, [[2, H]]),  # Clue exceeds its unresolved neighborhood.
            (3, 1, 2, [[0, H, 0]]),  # Public budget exceeds hidden capacity.
            (3, 1, 0, [[1, H, H]]),  # Acquired mine exceeds public total.
            (3, 1, 1, [[0, H, 1]]),  # Same target is both safe and mine.
        )
        for width, height, total, observation in cases:
            with self.subTest(observation=observation, total=total):
                session = KLocalSession(width, height, total)
                with self.assertRaises(KIntegrityError):
                    session.analyze_local(observation, status=PLAYING)
                self.assertEqual(session.M, frozenset())

    def test_h_all_unresolved_mines_while_playing_is_integrity_failure(self):
        session = KLocalSession(2, 1, 1)

        with self.assertRaises(KIntegrityError) as failure:
            session.analyze_local([[1, H]], status=PLAYING)

        self.assertEqual(failure.exception.code, "EMPTY_U_PLAYING")
        self.assertEqual(session.M, frozenset())
        with self.assertRaises(KIntegrityError) as failure:
            KLocalSession(1, 1, 0).analyze_local([[0]], status=PLAYING)
        self.assertEqual(failure.exception.code, "EMPTY_U_PLAYING")

    def test_i_second_pass_mine_detects_incomplete_first_pass_without_commit(self):
        session = KLocalSession(4, 1, 1)
        guard_before = session._previous
        original_pass = capability._direct_pass
        calls = 0

        def incomplete_first_pass(*args, **kwargs):
            nonlocal calls
            calls += 1
            result = original_pass(*args, **kwargs)
            if calls == 1:
                return replace(result, mine_cells=frozenset(), certificates=())
            return result

        with patch.object(capability, "_direct_pass", side_effect=incomplete_first_pass):
            with self.assertRaises(KIntegrityError) as failure:
                session.analyze_local([[1, H, 1, H]], status=PLAYING)

        self.assertEqual(failure.exception.code, "SECOND_PASS_MINE")
        self.assertEqual(calls, 2)
        self.assertEqual(session.M, frozenset())
        self.assertEqual(session._previous, guard_before)

    def test_local_safe_and_mine_pools_can_coexist(self):
        result = KLocalSession(4, 2, 3).analyze_local(
            [[0, H, H, 3], [H, H, H, H]], status=PLAYING
        )

        self.assertEqual(result.acquired_mines, {(2, 0), (2, 1), (3, 1)})
        self.assertEqual(result.S_first, {(1, 0), (0, 1), (1, 1)})
        self.assertEqual(result.S_second_all, result.S_first)
        self.assertEqual(result.S_current, result.S_first)
        self.assertLessEqual(result.S_current, result.after.U)

    def test_subset_relationship_does_not_authorize_stronger_inference(self):
        result = KLocalSession(3, 2, 1).analyze_local(
            [[1, 1, H], [H, H, H]], status=PLAYING
        )

        self.assertEqual(result.acquired_mines, frozenset())
        self.assertEqual(result.S_current, frozenset())

    def test_global_budget_alone_does_not_add_local_mines(self):
        result = KLocalSession(2, 1, 2).analyze_local([[H, H]], status=PLAYING)

        self.assertEqual(result.acquired_mines, frozenset())
        self.assertEqual(result.after.M, frozenset())
        self.assertEqual(result.after.U, {(0, 0), (1, 0)})
        self.assertEqual(result.after.b, 2)

    def test_negative_residual_from_new_clue_does_not_repair_retained_mine(self):
        session = KLocalSession(5, 1, 2)
        session.analyze_local([[1, H, H, H, H]], status=PLAYING)
        guard_before = session._previous

        with self.assertRaises(KIntegrityError) as failure:
            session.analyze_local([[1, H, 0, H, H]], status=PLAYING)

        self.assertEqual(failure.exception.code, "CLUE_RESIDUAL")
        self.assertEqual(session.M, {(1, 0)})
        self.assertEqual(session._previous, guard_before)

    def test_later_public_clue_can_use_prior_mine_with_independent_certificate(self):
        session = KLocalSession(5, 1, 2)
        first = session.analyze_local([[1, H, H, H, H]], status=PLAYING)
        second = session.analyze_local([[1, H, 2, H, H]], status=PLAYING)

        self.assertEqual(first.acquired_mines, {(1, 0)})
        self.assertEqual(second.acquired_mines, {(3, 0)})
        self.assertEqual(session.M, {(1, 0), (3, 0)})
        self.assertLessEqual(first.after.M, second.after.M)
        for proof in second.certificates:
            checked = verify_local_certificate(proof, prior_certificates=first.certificates)
            self.assertEqual(checked.antecedents, ((1, 0),))
            self.assertEqual(checked.unresolved, {(3, 0)})
            self.assertEqual(checked.residual, 1)

    def test_m_constraints_keep_xy_coordinates_in_reading_order(self):
        result = KLocalSession(3, 2, 1).analyze_local(
            [[H, H, 1], [1, H, H]], status=PLAYING
        )

        self.assertEqual(
            tuple(clue.source for clue in result.before.constraints),
            ((2, 0), (0, 1)),
        )
        self.assertEqual(
            result.before.constraints[0].Uc, {(1, 0), (1, 1), (2, 1)}
        )
        self.assertEqual(
            result.before.constraints[1].Uc, {(0, 0), (1, 0), (1, 1)}
        )

    def test_n_identical_inputs_have_deterministic_immutable_results(self):
        observation = [[1, H, 1, H, H, 1, H, 1]]
        saved = deepcopy(observation)
        expected = KLocalSession(8, 1, 2).analyze_local(observation, status=PLAYING)

        for _ in range(5):
            actual = KLocalSession(8, 1, 2).analyze_local(observation, status=PLAYING)
            self.assertEqual(actual, expected)
            self.assertEqual(observation, saved)
        with self.assertRaises(FrozenInstanceError):
            expected.S_current = frozenset()
        with self.assertRaises(FrozenInstanceError):
            expected.after.b = 100
        with self.assertRaises(FrozenInstanceError):
            expected.after.constraints[0].rc = 100
        observation[0][0] = 0
        self.assertEqual(expected.certificates[0].observation[0][0], 1)

    def test_o_validation_checks_without_acquiring_or_repairing(self):
        session = KLocalSession(4, 1, 1)
        initial = session.validate([[1, H, 1, H]], status=PLAYING)
        self.assertEqual(initial.M, frozenset())
        self.assertEqual(session.M, frozenset())
        session.analyze_local([[1, H, 1, H]], status=PLAYING)
        mine_snapshot = session.M

        checked = session.validate([[1, F, 1, H]], status=PLAYING)
        self.assertEqual(checked.M, mine_snapshot)
        self.assertEqual(session.M, mine_snapshot)
        # validate did not advance the committed physical-observation guard.
        session.validate([[1, H, 1, H]], status=PLAYING)
        for invalid in ([[1, 0, 1, H]], [[0, H, 1, H]], [[H, H, 1, H]]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(KIntegrityError):
                    session.validate(invalid, status=PLAYING)
                self.assertEqual(session.M, mine_snapshot)

    def test_committed_flag_cannot_be_unflagged_and_clues_cannot_regress(self):
        session = KLocalSession(4, 1, 1)
        session.analyze_local([[1, H, 1, H]], status=PLAYING)
        session.analyze_local([[1, F, 1, H]], status=PLAYING)

        for invalid in ([[1, H, 1, H]], [[H, F, 1, H]], [[1, F, 0, H]]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(KIntegrityError):
                    session.analyze_local(invalid, status=PLAYING)
                self.assertEqual(session.M, {(1, 0)})

    def test_new_session_does_not_inherit_mines_or_accept_unproved_flags(self):
        old = KLocalSession(4, 1, 1)
        old.analyze_local([[1, H, 1, H]], status=PLAYING)
        fresh = KLocalSession(4, 1, 1)

        self.assertEqual(fresh.M, frozenset())
        with self.assertRaises(KIntegrityError):
            fresh.analyze_local([[1, F, 1, H]], status=PLAYING)
        self.assertEqual(fresh.M, frozenset())

    def test_p_terminal_status_is_rejected_before_any_observation_access(self):
        session = KLocalSession(4, 1, 1)
        session.analyze_local([[1, H, 1, H]], status=PLAYING)

        for status in (GameStatus.WON, GameStatus.LOST, 0, False, "PLAYING", None):
            for method in (session.validate, session.analyze_local):
                with self.subTest(status=status, method=method.__name__):
                    with self.assertRaises(KIntegrityError):
                        method(UntouchableObservation(), status=status)
                    self.assertEqual(session.M, {(1, 0)})

        with self.assertRaises(KIntegrityError) as failure:
            session.analyze_local([[1, H, 1, H]], status=PLAYING)
        self.assertEqual(failure.exception.code, "SESSION_CLOSED")

    def test_terminal_glyphs_invalid_values_and_non_grid_objects_are_rejected(self):
        bad_values = (
            CellState.MINE, CellState.EXPLODED, CellState.FALSE_FLAG,
            -1, 9, True, 0.0, "0", None,
        )
        for value in bad_values:
            with self.subTest(value=value):
                with self.assertRaises(KIntegrityError):
                    KLocalSession(2, 1, 1).analyze_local([[H, value]], status=PLAYING)
        for observation in (None, {}, object(), [], [[]], [[H], [H, H]], [H]):
            with self.subTest(observation=observation):
                with self.assertRaises(KIntegrityError):
                    KLocalSession(2, 1, 1).analyze_local(observation, status=PLAYING)

    def test_dimensions_and_metadata_are_checked(self):
        for dimensions in ((0, 1, 0), (1, 0, 0), (2, 1, -1), (2, 1, 3), (True, 1, 0)):
            with self.subTest(dimensions=dimensions):
                with self.assertRaises(ValueError):
                    KLocalSession(*dimensions)
        with self.assertRaises(KIntegrityError):
            KLocalSession(4, 1, 1).analyze_local([[H, 1, H]], status=PLAYING)

    def test_reflected_and_transposed_structural_witnesses(self):
        # Explicit expectations are geometric semantic facts, not policy winners.
        fixtures = (
            ([[H, 1, H, 1]], 4, 1, {(2, 0)}, {(0, 0)}),
            ([[1], [H], [1], [H]], 1, 4, {(0, 1)}, {(0, 3)}),
        )
        for observation, width, height, mines, safes in fixtures:
            with self.subTest(observation=observation):
                result = KLocalSession(width, height, 1).analyze_local(
                    observation, status=PLAYING
                )
                self.assertEqual(result.acquired_mines, mines)
                self.assertEqual(result.S_first, frozenset())
                self.assertEqual(result.S_second_all, safes)
                exact = enumerate_public_worlds(observation, 1, status=PLAYING)
                self.assertEqual(exact.total_worlds, 1)
                self.assertEqual(dict(exact.mine_worlds), {
                    next(iter(mines)): 1, next(iter(safes)): 0,
                })


class ProgramKIndependentCertificateTests(unittest.TestCase):
    def test_checker_reconstructs_raw_local_premises(self):
        proof = certificate([[1, H, 1, H]], 1, (0, 0), (1, 0))

        checked = verify_local_certificate(proof)

        self.assertEqual(checked.clue, (0, 0))
        self.assertEqual(checked.clue_value, 1)
        self.assertEqual(checked.target, (1, 0))
        self.assertEqual(checked.physical_flags, frozenset())
        self.assertEqual(checked.logical_mines, frozenset())
        self.assertEqual(checked.unresolved, {(1, 0)})
        self.assertEqual(checked.residual, 1)
        self.assertEqual(checked.antecedents, ())

    def test_prior_logical_and_physical_antecedents_count_once(self):
        prior = certificate([[1, H, H, H, H]], 2, (0, 0), (1, 0))
        current = certificate(
            [[1, F, 2, H, H]], 2, (2, 0), (3, 0), {(1, 0)}
        )

        checked = verify_local_certificate(current, prior_certificates=(prior,))

        self.assertEqual(checked.physical_flags, {(1, 0)})
        self.assertEqual(checked.logical_mines, {(1, 0)})
        self.assertEqual(checked.antecedents, ((1, 0),))
        self.assertEqual(checked.unresolved, {(3, 0)})
        self.assertEqual(checked.residual, 1)

    def test_checker_does_not_trust_target_or_clue_classification(self):
        invalid = (
            certificate([[H, 1, H]], 1, (1, 0), (0, 0)),
            certificate([[0, H]], 0, (0, 0), (1, 0)),
            certificate([[1, H, 1, H]], 1, (0, 0), (3, 0)),
            certificate([[H, 1, H]], 1, (0, 0), (2, 0)),
        )
        for proof in invalid:
            with self.subTest(proof=proof):
                with self.assertRaises(PublicProofError):
                    verify_local_certificate(proof)

    def test_circular_missing_and_future_premises_are_rejected(self):
        prior = certificate([[1, H, H, H, H]], 2, (0, 0), (1, 0))
        later = certificate([[1, H, 2, H, H]], 2, (2, 0), (3, 0), {(1, 0)})
        circular = certificate([[1, H, H, H]], 2, (0, 0), (1, 0), {(1, 0)})

        with self.assertRaises(PublicProofError):
            verify_local_certificate(later)
        with self.assertRaises(PublicProofError):
            verify_local_certificate(circular)
        with self.assertRaises(PublicProofError):
            verify_local_certificate(prior, prior_certificates=(later,))
        with self.assertRaises(PublicProofError):
            verify_local_certificate(later, prior_certificates=(later, prior))

    def test_future_clue_cannot_support_earlier_public_state(self):
        future = certificate([[1, H, 2, H, H]], 2, (0, 0), (1, 0))
        past = certificate([[1, H, H, H, H]], 2, (0, 0), (1, 0))

        with self.assertRaises(PublicProofError):
            verify_local_certificate(past, prior_certificates=(future,))

    def test_certificate_rejects_unproved_flag_or_mutated_public_history(self):
        bare_flag = certificate([[1, F, 2, H, H]], 2, (2, 0), (3, 0))
        prior = certificate([[1, H, H, H, H]], 2, (0, 0), (1, 0))
        changed = certificate([[0, H, 2, H, H]], 2, (2, 0), (3, 0), {(1, 0)})

        with self.assertRaises(PublicProofError):
            verify_local_certificate(bare_flag)
        with self.assertRaises(PublicProofError):
            verify_local_certificate(changed, prior_certificates=(prior,))
        with self.assertRaises(PublicProofError):
            verify_local_certificate(object())

    def test_certificates_detach_inputs_and_reject_transposed_or_invalid_coordinates(self):
        observation = [[1, H, H, H]]
        retained = set()
        proof = certificate(observation, 2, (0, 0), (1, 0), retained)
        observation[0][0] = 0
        retained.add((2, 0))

        self.assertEqual(proof.observation, ((1, H, H, H),))
        self.assertEqual(proof.retained_mines, frozenset())
        self.assertEqual(verify_local_certificate(proof).target, (1, 0))
        with self.assertRaises(FrozenInstanceError):
            proof.target = (2, 0)
        for target in ((0, 1), (-1, 0), (True, 0), [1, 0], (1.0, 0)):
            with self.subTest(target=target):
                with self.assertRaises(PublicProofError):
                    certificate([[1, H, H, H]], 2, (0, 0), target)


class ProgramKOracleATests(unittest.TestCase):
    def test_j_public_history_qualifies_logical_physical_and_overlap_exact_basis(self):
        observation = [[1, H, H, H]]
        session = KLocalSession(4, 1, 2)
        analysis = session.analyze_local(observation, status=PLAYING)
        self.assertEqual(analysis.after.U, {(2, 0), (3, 0)})
        self.assertEqual(analysis.after.b, 1)
        expected = (((2, 0), 1), ((3, 0), 1))

        logical = enumerate_public_worlds(
            observation, 2, status=PLAYING,
            logical_mines=analysis.after.M, proofs=analysis.certificates,
        )
        overlap = enumerate_public_worlds(
            [[1, F, H, H]], 2, status=PLAYING,
            logical_mines=analysis.after.M, proofs=analysis.certificates,
        )
        # P-only is an informational reference with this prior proof, not live K.
        physical_reference = enumerate_public_worlds(
            [[1, F, H, H]], 2, status=PLAYING, proofs=analysis.certificates,
        )

        self.assertEqual(logical.total_worlds, 2)
        self.assertEqual(logical.mine_worlds, expected)
        self.assertEqual(logical, overlap)
        self.assertEqual(logical, physical_reference)
        self.assertEqual(session.M, {(1, 0)})

    def test_k_no_flag_tie_exact_counts_and_xy_reading_order(self):
        result = enumerate_public_worlds([[1, H, H], [H, H, H]], 2, status=PLAYING)

        self.assertEqual(result.total_worlds, 6)
        self.assertEqual(result.mine_worlds, (
            ((1, 0), 2), ((2, 0), 3), ((0, 1), 2), ((1, 1), 2), ((2, 1), 3),
        ))
        minimum_set = {cell for cell, numerator in result.mine_worlds if numerator == 2}
        self.assertEqual(minimum_set, {(1, 0), (0, 1), (1, 1)})
        # This checks serialization order; no K guess policy is implemented here.
        ordered_minima = tuple(cell for cell, numerator in result.mine_worlds if numerator == 2)
        self.assertEqual(ordered_minima, ((1, 0), (0, 1), (1, 1)))
        self.assertNotEqual(ordered_minima[0], (0, 1))

    def test_transposed_tie_expected_reading_order_is_freshly_derived(self):
        # Transpose moves old (1,0) to (0,1), but that is NOT the new first tie.
        result = enumerate_public_worlds([[1, H], [H, H], [H, H]], 2, status=PLAYING)

        self.assertEqual(result.total_worlds, 6)
        self.assertEqual(result.mine_worlds, (
            ((1, 0), 2), ((0, 1), 2), ((1, 1), 2), ((0, 2), 3), ((1, 2), 3),
        ))
        self.assertEqual(result.mine_worlds[0], ((1, 0), 2))

    def test_frontier_only_floating_and_zero_world_results(self):
        cases = (
            ([[H, 1, H]], 1, 2, (((0, 0), 1), ((2, 0), 1))),
            ([[H, H]], 1, 2, (((0, 0), 1), ((1, 0), 1))),
            ([[0, H, 1]], 1, 0, (((1, 0), 0),)),
            ([[0, H]], 0, 1, (((1, 0), 0),)),
        )
        for observation, total, worlds, numerators in cases:
            with self.subTest(observation=observation, total=total):
                result = enumerate_public_worlds(observation, total, status=PLAYING)
                self.assertEqual(result.total_worlds, worlds)
                self.assertEqual(result.mine_worlds, numerators)
                self.assertIs(type(result.total_worlds), int)
                for _, numerator in result.mine_worlds:
                    self.assertIs(type(numerator), int)

    def test_l_finite_envelope_limit_is_inclusive_and_not_evaluated_is_explicit(self):
        boundary = enumerate_public_worlds([[H] * 16], 1, status=PLAYING)
        self.assertEqual(boundary.total_worlds, 16)
        self.assertEqual(boundary.mine_worlds, tuple(((x, 0), 1) for x in range(16)))

        with self.assertRaises(OracleANotEvaluated) as failure:
            enumerate_public_worlds([[H] * 17], 1, status=PLAYING)

        self.assertEqual(failure.exception.status, "ORACLE_A_NOT_EVALUATED")
        self.assertEqual(failure.exception.variable_count, 17)
        self.assertEqual(failure.exception.envelope, 16)
        self.assertTrue(failure.exception.reason)

    def test_unproved_fixed_mines_and_bare_flags_are_never_oracle_premises(self):
        with self.assertRaises(PublicProofError):
            enumerate_public_worlds(
                [[1, H, H, H]], 2, status=PLAYING, logical_mines={(1, 0)}
            )
        with self.assertRaises(PublicProofError):
            enumerate_public_worlds([[1, F, H, H]], 2, status=PLAYING)

    def test_oracle_rejects_invalid_input_and_terminal_truth_channels(self):
        for status in (GameStatus.WON, GameStatus.LOST, 0, False, None):
            with self.subTest(status=status):
                with self.assertRaises(PublicProofError):
                    enumerate_public_worlds(UntouchableObservation(), 1, status=status)
        for observation in (
            [[H, CellState.MINE]], [[H, CellState.EXPLODED]],
            [[H, CellState.FALSE_FLAG]], [[H, True]], [[H, 0.0]],
            object(), {"hidden_mines": {(0, 0)}}, [[H], []],
        ):
            with self.subTest(observation=observation):
                with self.assertRaises(PublicProofError):
                    enumerate_public_worlds(observation, 1, status=PLAYING)

    def test_oracle_and_certificate_import_only_public_engine_enums(self):
        public_types = types.ModuleType("core_engine")
        public_types.CellState = CellState
        public_types.GameStatus = GameStatus
        # Unavailable solver modules catch accidental oracle dependency imports.
        unavailable = {
            "core_engine": public_types,
            "simple_algorithm": None,
            "simple_probability": None,
            "experiments.program_k_capability": None,
        }
        with patch.dict(sys.modules, unavailable):
            namespace = runpy.run_path(oracles.__file__)
            result = namespace["enumerate_public_worlds"](
                [[1, H, H], [H, H, H]], 2, status=PLAYING
            )
            proof = namespace["LocalMineCertificate"](
                [[1, H, H, H]], 2, (0, 0), (1, 0), frozenset(), PLAYING
            )
            checked = namespace["verify_local_certificate"](proof)

        self.assertEqual(result.total_worlds, 6)
        self.assertEqual(checked.target, (1, 0))

    def test_capability_runs_without_an_engine_object_or_answer_channel(self):
        public_types = types.ModuleType("core_engine")
        public_types.CellState = CellState
        public_types.GameStatus = GameStatus
        with patch.dict(sys.modules, {"core_engine": public_types}):
            namespace = runpy.run_path(capability.__file__)
            result = namespace["KLocalSession"](4, 1, 1).analyze_local(
                [[1, H, 1, H]], status=PLAYING
            )

        self.assertEqual(result.acquired_mines, {(1, 0)})
        self.assertEqual(result.S_current, {(3, 0)})

    def test_independent_diagnostics_never_drive_capability_inference(self):
        with (
            patch.object(oracles, "verify_local_certificate", side_effect=AssertionError("Verifier called by K")),
            patch.object(oracles, "enumerate_public_worlds", side_effect=AssertionError("Oracle called by K")),
        ):
            result = KLocalSession(4, 1, 1).analyze_local(
                [[1, H, 1, H]], status=PLAYING
            )

        self.assertEqual(result.acquired_mines, {(1, 0)})
        self.assertEqual(result.S_current, {(3, 0)})

    def test_repeated_exact_inputs_are_deterministic_and_results_frozen(self):
        observation = [[1, H, H], [H, H, H]]
        saved = deepcopy(observation)
        expected = enumerate_public_worlds(observation, 2, status=PLAYING)

        for _ in range(5):
            self.assertEqual(
                enumerate_public_worlds(observation, 2, status=PLAYING), expected
            )
            self.assertEqual(observation, saved)
        with self.assertRaises(FrozenInstanceError):
            expected.total_worlds = 0


if __name__ == "__main__":
    unittest.main()
