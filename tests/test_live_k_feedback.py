"""K UI feedback: exact projection and strict public values; no processes."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from math import comb
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import live_k_policy as k
import live_policy_transport as transport
from experiments.program_k_capability import KLocalSession
from live_analysis import OverlayKind, format_mine_probability, present_k_proposal
from live_policy import LivePolicyError
from simple_probability import CellProbability
from stage3_physical import load_timing_table
import tests.test_live_k_policy as fixtures


def guess_owner():
    return fixtures.after_initial(((1, -2, -2, -2, -2),), mines=3)


class KProbabilityFeedbackTests(unittest.TestCase):
    def test_original_phase_e_projection_one_analysis_selection_and_retained_graph(self):
        owner, snapshot = guess_owner()
        original = KLocalSession.analyze_decision
        with patch.object(KLocalSession, 'analyze_decision', autospec=True, side_effect=original) as analyze:
            owner._select = Mock(wraps=owner._select)
            p = owner.propose(snapshot)
            graph, decision = owner.selection, owner.decision
            exact = decision.phase_e
            self.assertIs(graph.evidence, decision)
            self.assertEqual(p.probabilities.cells,
                             tuple((*cell, count) for cell, count in exact.mine_worlds))
            self.assertEqual(p.probabilities.total_worlds, exact.total_worlds)
            self.assertEqual(set(p.probabilities.minimum_risk_cells), exact.minimum_risk_cells)
            self.assertEqual((p.x, p.y), decision.guess_target)
            for _ in range(5):
                self.assertIs(fixtures.permit(owner, p).proposal, p)
                present_k_proposal(p)
                k.from_dict(json.loads(json.dumps(k.to_dict(p))), k.KProposal)
            self.assertIs(owner.selection, graph)
            self.assertIs(owner.decision, decision)
            self.assertEqual(analyze.call_count, 1)
            self.assertEqual(owner._select.call_count, 1)
            self.assertEqual(owner._select.call_args.kwargs, {})
            self.assertEqual(owner.session.M, frozenset({(1, 0)}))
            self.assertEqual(p.snapshot.base_m, ())

    def test_presentation_has_exact_unresolved_candidates_and_separate_logical_m(self):
        owner, snapshot = guess_owner()
        p = owner.propose(snapshot)
        result = present_k_proposal(p)
        self.assertIn('지뢰 확률 66.7%', result.status_text)
        self.assertEqual(result.move, owner.selection.move)
        self.assertEqual(set(result.overlays), {(1, 0), (2, 0), (3, 0), (4, 0)})
        self.assertEqual(result.overlays[(1, 0)].kind, OverlayKind.MINE)
        self.assertIsNone(result.overlays[(1, 0)].probability)
        uncertain = [o for cell, o in result.overlays.items() if cell not in p.preinput_m]
        self.assertEqual([c for c, o in result.overlays.items() if o.recommended], [(2, 0)])
        self.assertTrue(all(o.kind == OverlayKind.GUESS_CANDIDATE for o in uncertain))
        self.assertTrue(all((o.probability.mine_worlds, o.probability.total_worlds) == (2, 3)
                            for o in uncertain))

    def test_initial_and_certain_do_not_fabricate_probabilities(self):
        initial = fixtures.initial()
        owner = k.KOwner(initial, load_timing_table())
        p = owner.propose(initial)
        self.assertIsNone(p.probabilities)
        self.assertNotIn('확률', present_k_proposal(p).status_text)
        owner, snapshot = fixtures.after_initial()
        p = owner.propose(snapshot)
        self.assertEqual(p.action, 'FLAG')
        self.assertIsNone(p.probabilities)
        self.assertTrue(all(c.probability is None for c in present_k_proposal(p).overlays.values()))

    def test_huge_integers_round_trip_and_format_without_false_certainty(self):
        denominator = 10 ** 100
        exact = k.ExactGuessProbabilities(denominator, ((1, 0, 1), (2, 0, denominator - 1)), ((1, 0),), 1)
        state = replace(fixtures.initial(3, 1, 1), input_seq=1, input_revision=1,
                        observation=((1, -2, -2),))
        p = k.KProposal(state, 'b' * 32, 'OPEN', 1, 0, 'guess', 'EXACT_MINIMUM_RISK_GUESS',
                        'EXACT_GUESS', 1, 1, 1, (), exact)
        restored = k.from_dict(json.loads(json.dumps(k.to_dict(p))), k.KProposal)
        self.assertEqual(restored, p)
        result = present_k_proposal(restored)
        self.assertIn('지뢰 확률 <0.1%', result.status_text)
        self.assertEqual(result.overlays[(1, 0)].kind, OverlayKind.GUESS_CANDIDATE)
        self.assertEqual(result.overlays[(2, 0)].kind, OverlayKind.UNCERTAIN)
        self.assertEqual(format_mine_probability(result.overlays[(2, 0)].probability), '>99.9%')
        for numerator, full, compact in ((0, '0%', '0%'), (1, '<0.1%', '<1%'),
                                         (denominator - 1, '>99.9%', '>99%'),
                                         (denominator, '100%', '100%')):
            with self.subTest(numerator=numerator):
                cell = CellProbability((1, 0), numerator, denominator)
                self.assertEqual(format_mine_probability(cell), full)
                self.assertEqual(format_mine_probability(cell, compact=True), compact)

    def test_strict_probability_fields_coordinates_coverage_and_payload_cap(self):
        owner, snapshot = guess_owner()
        original = k.to_dict(owner.propose(snapshot))
        mutations = []
        for field in ('total_worlds', 'selected_mine_worlds'):
            for bad in (True, False, 1.0, -1, 0, 1 << 481, '3', None):
                mutations.append((field, lambda d, f=field, v=bad: d['probabilities'].__setitem__(f, v)))
        for column, values in ((0, (True, 2.0, -1, 5, 30)), (1, (False, 0.0, -1, 1, 16)),
                               (2, (True, 2.0, -1, 0, 3, 1 << 481))):
            for bad in values:
                mutations.append((f'cell{column}', lambda d, c=column, v=bad: d['probabilities']['cells'][0].__setitem__(c, v)))
        mutations += [
            ('missing_cell', lambda d: d['probabilities']['cells'].pop()),
            ('duplicate_cell', lambda d: d['probabilities']['cells'].append(d['probabilities']['cells'][0])),
            ('oversized', lambda d: d['probabilities'].__setitem__('cells', [[2, 0, 2]] * 481)),
            ('zero_cells', lambda d: d['probabilities'].__setitem__('cells', [])),
            ('revealed', lambda d: d['probabilities']['cells'][0].__setitem__(0, 0)),
            ('owned_m', lambda d: d['probabilities']['cells'][0].__setitem__(0, 1)),
            ('wrong_count', lambda d: d['probabilities']['cells'][0].__setitem__(2, 1)),
            ('selected_mismatch', lambda d: d['probabilities'].__setitem__('selected_mine_worlds', 1)),
            ('minimum_missing', lambda d: d['probabilities']['minimum_risk_cells'].pop()),
            ('minimum_duplicate', lambda d: d['probabilities']['minimum_risk_cells'].append([2, 0])),
            ('minimum_bool', lambda d: d['probabilities']['minimum_risk_cells'][0].__setitem__(1, False)),
            ('unknown', lambda d: d['probabilities'].__setitem__('proof', {})),
            ('missing_field', lambda d: d['probabilities'].pop('selected_mine_worlds')),
            ('missing_probabilities', lambda d: d.pop('probabilities')),
            ('null', lambda d: d.__setitem__('probabilities', None)),
        ]
        for label, mutate in mutations:
            with self.subTest(case=label, index=mutations.index((label, mutate))):
                value = deepcopy(original)
                mutate(value)
                with self.assertRaises(LivePolicyError):
                    k.from_dict(value, k.KProposal)

    def test_immutable_and_non_guess_cannot_carry_probability(self):
        owner, state = guess_owner()
        p = owner.propose(state)
        with self.assertRaises(FrozenInstanceError):
            p.probabilities.total_worlds = 9
        raw = k.to_dict(p)
        raw['probabilities']['cells'][0][2] = 1
        self.assertEqual(p.probabilities.cells[0][2], 2)
        initial = fixtures.initial()
        owner2 = k.KOwner(initial, load_timing_table())
        with self.assertRaises(LivePolicyError):
            replace(owner2.propose(initial), probabilities=p.probabilities)

    def test_valid_alternate_numbers_cannot_replace_retained_permit_or_ack(self):
        owner, state = guess_owner()
        p = owner.propose(state)
        permit = fixtures.permit(owner, p)
        old = p.probabilities
        # Mathematically the same fractions, but different raw evidence bytes.
        alternate = replace(old, total_worlds=old.total_worlds * 2,
                            cells=tuple((x, y, n * 2) for x, y, n in old.cells),
                            selected_mine_worlds=old.selected_mine_worlds * 2)
        changed = replace(permit, proposal=replace(p, probabilities=alternate))
        with self.assertRaisesRegex(LivePolicyError, 'differs'):
            owner.acknowledge(k.make_ack(changed, 'LOST'))
        self.assertIs(owner.pending, p)
        owner.acknowledge(k.make_ack(permit, 'LOST'))
        self.assertIsNone(owner.pending)
        self.assertIsNone(owner.decision)

    def test_v5_rejects_old_v4_v3_without_changing_sequence_bounds(self):
        valid = transport.message('a' * 32, 0, 'START', {})
        self.assertEqual(valid['version'], 5)
        for old_version in (3, 4):
            with self.subTest(version=old_version), self.assertRaises(LivePolicyError):
                transport.validate_message({**valid, 'version': old_version})
        self.assertEqual(transport.MAX_V1_SEQUENCE, 1921)
        self.assertEqual(transport.MAX_SEQUENCE, 31681)
        self.assertEqual(k.MAX_VALIDATIONS_PER_INPUT, 64)

    def test_maximum_board_exact_payload_fits_wire_without_losing_integer_bytes(self):
        # Structural stress fixture only, not a solved Expert/native board.
        cells = tuple((x, y) for y in range(16) for x in range(30) if (x, y) != (0, 0))
        denominator, numerator = comb(479, 99), comb(478, 98)
        exact = k.ExactGuessProbabilities(denominator, tuple((*c, numerator) for c in cells), cells, numerator)
        state = replace(fixtures.initial(30, 16, 99), input_seq=1, input_revision=1,
                        observation=((1,) + (-2,) * 29,) + ((-2,) * 30,) * 15)
        proposal = k.KProposal(state, 'c' * 32, 'OPEN', 1, 0, 'guess', 'EXACT_MINIMUM_RISK_GUESS',
                               'EXACT_GUESS', 1, 1, 1, (), exact)
        permit = k.KPermit(proposal, 'd' * 32)
        ack = k.make_ack(permit, 'LOST')
        envelope = transport.message(state.run_id, 6, 'ACK', k.to_dict(ack))
        with TemporaryDirectory() as name:
            path = transport.write_once(Path(name), 'parent', 6, envelope)
            self.assertLess(path.stat().st_size, transport.MAX_MESSAGE_BYTES)
            decoded = transport.read_next(Path(name), 'parent', 6, state.run_id)
            self.assertEqual(k.from_dict(decoded['payload'], k.KAck), ack)
