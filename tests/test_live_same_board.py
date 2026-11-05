"""Fixed-board public entry contracts; small deterministic fixtures, no IPC."""
from dataclasses import replace
import json
import random
import unittest

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
import live_k_policy as k
from live_policy import (FIXED_BOARD, CANONICAL_NEW, ADOPT_CURRENT, LivePolicyError,
                         make_snapshot, plan_snapshot, make_ack, validate_ack,
                         validate_start_snapshot, snapshot_from_dict, snapshot_to_dict)
from live_policy_transport import PROTOCOL_VERSION, message, validate_message
from live_same_board import FixedLayout
from stage3_physical import load_timing_table


def fixed_snapshot(policy=None, width=5, height=1, mines=1):
    values = dict(run_id='a'*32, board_generation=7, input_seq=0, width=width,
                  height=height, num_mines=mines, observation=[[-2]*width for _ in range(height)],
                  cursor=(0, 0), entry_mode=FIXED_BOARD, input_revision=0)
    if policy is None:
        return make_snapshot(**values, fixed_game_id='b'*32)
    return k.make_snapshot(**values, game_id='b'*32, policy_id=policy,
                           definition=k.definition_for_entry(FIXED_BOARD, policy),
                           phase=k.normal_phase(policy))


class SameBoardContracts(unittest.TestCase):
    def test_layout_detaches_and_repeats_without_rng(self):
        engine = MinesweeperEngine(5, 1, 1)
        for terminal in (GameStatus.LOST, GameStatus.WON):
            engine.reset_with_mines(5, 1, 1, {(2, 0)})
            if terminal == GameStatus.LOST:
                engine.step(2, 0, Action.OPEN)
            else:
                engine.step(0, 0, Action.OPEN)
                engine.step(4, 0, Action.OPEN)
            layout = FixedLayout.from_finished_engine(engine)
            self.assertEqual(engine.status, terminal)
            state = random.getstate()
            for _ in range(2):
                layout.reset_engine(engine)
                self.assertEqual(engine.get_observation(), [[CellState.HIDDEN]*5])
                self.assertEqual(engine.get_elapsed_time(), 0)
                self.assertEqual(engine.get_counter_snapshot()['active_clicks'], 0)
                self.assertEqual(layout.mines, frozenset({(2, 0)}))
            self.assertEqual(random.getstate(), state)

    def test_layout_requires_terminal_valid_placement(self):
        engine = MinesweeperEngine(5, 1, 1)
        with self.assertRaises(ValueError):
            FixedLayout.from_finished_engine(engine)
        for args in ((5, 1, 1, set()), (5, 1, 1, {(5, 0)}), (5, 1, 1, {(True, 0)})):
            with self.subTest(args=args), self.assertRaises(ValueError):
                FixedLayout(*args)

    def test_fixed_v1_uses_public_guess_and_preserves_ack_identity(self):
        snapshot = fixed_snapshot()
        validate_start_snapshot(snapshot)
        proposal = plan_snapshot(snapshot)
        self.assertTrue(proposal.is_guess)
        self.assertEqual(proposal.kind, 'guess')
        self.assertGreater(proposal.compute_ns, 0)
        self.assertEqual(len(proposal.overlays), 5)
        self.assertTrue(all((c.mine_worlds, c.total_worlds) == (1, 5) for c in proposal.overlays))
        engine = MinesweeperEngine(5, 1, 1)
        engine.reset_with_mines(5, 1, 1, {(2, 0)})
        engine.step(proposal.x, proposal.y, Action.OPEN)
        following = validate_ack(proposal, make_ack(proposal, engine.status, engine.get_observation()))
        self.assertEqual(following.fixed_game_id, snapshot.fixed_game_id)
        self.assertEqual(following.input_revision, 1)
        self.assertEqual(following.entry_mode, FIXED_BOARD)

    def test_fixed_k_families_analyze_validate_ack_and_reject_old_identity(self):
        table = load_timing_table()
        for policy in (k.POLICY_K, k.POLICY_K_LC0, k.POLICY_K_LC1):
            with self.subTest(policy=policy):
                snapshot = fixed_snapshot(policy)
                owner = k.KOwner(snapshot, table)
                proposal = owner.propose(snapshot)
                self.assertFalse(proposal.initial)
                self.assertTrue(proposal.is_guess)
                self.assertEqual(proposal.pending_m_revision, 1)
                self.assertEqual(proposal.preinput_m, ())
                permit = owner.validate(k.KValidation(snapshot, proposal.token, 'c'*32, 1))
                other = replace(snapshot, game_id='d'*32)
                with self.assertRaises(LivePolicyError):
                    k.admit_proposal(proposal, other)
                engine = MinesweeperEngine(5, 1, 1)
                engine.reset_with_mines(5, 1, 1, {(2, 0)})
                engine.step(proposal.x, proposal.y, Action.OPEN)
                ack = k.make_ack(permit, engine.status, engine.get_observation())
                following = owner.acknowledge(ack)
                self.assertEqual(following.base_m_revision, 1)
                self.assertEqual(following.input_seq, 1)
                self.assertEqual(following.game_id, snapshot.game_id)

    def test_fixed_start_rejects_nonempty_history_cursor_m_and_bad_definition(self):
        v = fixed_snapshot()
        for changes in ({'fixed_game_id': None}, {'input_revision': 1}, {'cursor': (1, 0)},
                        {'observation': ((0, -2, -2, -2, -2),)}, {'entry_mode': CANONICAL_NEW}):
            with self.subTest(changes=changes), self.assertRaises(LivePolicyError):
                validate_start_snapshot(replace(v, **changes))
        s = fixed_snapshot(k.POLICY_K)
        for changes in ({'start_input_revision': 1, 'input_revision': 1}, {'cursor': (1, 0)},
                        {'base_m': ((0, 0),)}, {'base_m_revision': 1}, {'definition': k.DEFINITION}):
            with self.subTest(changes=changes), self.assertRaises(LivePolicyError):
                k.validate_start_snapshot(replace(s, **changes))

    def test_fixed_initial_cannot_be_forged_as_free_canonical_input(self):
        proposal = plan_snapshot(fixed_snapshot())
        with self.assertRaises(LivePolicyError):
            replace(proposal, kind='initial', compute_ns=0, overlays=())
        with self.assertRaises(LivePolicyError):
            replace(fixed_snapshot(k.POLICY_K), entry_mode=ADOPT_CURRENT,
                    definition=k.ADOPT_DEFINITION)

    def test_wire_v10_roundtrip_rejects_old_unknown_and_missing_fields(self):
        self.assertEqual(PROTOCOL_VERSION, 10)
        snapshot = fixed_snapshot()
        payload = snapshot_to_dict(snapshot)
        self.assertEqual(snapshot_from_dict(payload), snapshot)
        self.assertFalse({'mines', 'mine_positions', 'layout'} & set(payload))
        wire = message(snapshot.run_id, 0, 'START', payload)
        self.assertEqual(validate_message(json.loads(json.dumps(wire))), wire)
        for version in (9, 8, 11, True, '10', 10.0):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate_message(dict(wire, version=version))
        del payload['fixed_game_id']
        with self.assertRaises(LivePolicyError):
            snapshot_from_dict(payload)


if __name__ == '__main__':
    unittest.main()
