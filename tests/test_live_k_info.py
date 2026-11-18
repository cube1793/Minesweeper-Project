"""KLC1_INFO_D1 (experiment candidate): display-only certainty for Live K-LC1.

Contracts of the accepted design supplement, section 11 items 1-8. Small test
fixtures only (9x9 and below). The expected certain sets come from an
enumerator written here, never from a product counter.
"""
from dataclasses import fields, replace
import hashlib
import json
from math import comb
import os
import random
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QSignalSpy

import live_k_info
import live_k_policy as k
import live_policy_info
import live_policy_job as jobs
import live_policy_worker as worker
from core_engine import Action, GameStatus, MinesweeperEngine
from live_analysis import OverlayKind, present_k_proposal
from live_k_info import KInfoSupplement
from live_policy import LivePolicyError, POLICY_K, POLICY_K_LC0, POLICY_K_LC1
from live_policy_info import CertaintyEngine, Outcome
from live_policy_transport import PROTOCOL_VERSION, message, write_once
from simple_algorithm import InconsistentObservationError
from stage3_physical import load_timing_table
from tests import test_live_k_lc0_ui as lc0
from tests import test_live_k_ui as base
from tests.live_k_lc1_fixtures import as_policy, singleton_start
from tests.test_live_k_flag_adopt import flag_start
from tests.test_live_k_policy import initial

H, F = -2, -3
TABLE = load_timing_table()
UI_MINES = ((1, 0), (3, 2), (4, 4), (8, 8), (2, 7), (6, 2), (8, 3), (7, 5), (4, 8), (0, 6))
KPROPOSAL_KEYS = {f.name for f in fields(k.KProposal)}


# ---------------------------------------------------------------- fixtures
def engine_for(width, height, mines, opening):
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), frozenset(mines))
    engine.step(opening[0], opening[1], Action.OPEN)
    assert engine.status == GameStatus.PLAYING
    return engine


def adopt(engine, cursor, policy=POLICY_K_LC1):
    return k.make_snapshot(
        run_id=uuid4().hex, game_id=uuid4().hex, board_generation=1, input_seq=0,
        width=engine.width, height=engine.height, num_mines=engine.num_mines,
        observation=engine.get_observation(), cursor=cursor, input_revision=1, start_input_revision=1,
        entry_mode=k.ADOPT_CURRENT, policy_id=policy,
        definition=k.definition_for_entry(k.ADOPT_CURRENT, policy), phase=k.normal_phase(policy))


def ui_board(opening=(0, 3), policy=POLICY_K_LC1):
    engine = engine_for(9, 9, UI_MINES, opening)
    return engine, adopt(engine, opening, policy)


def small_board(width, height, count, seed):
    """A fixed small test layout; not an evaluation board."""
    rng = random.Random(1000 * width + 10 * height + seed)
    cells = [(x, y) for y in range(height) for x in range(width)]
    mines = rng.sample(cells, count)
    return mines, rng.choice([cell for cell in cells if cell not in mines])


def step(owner, engine, proposal):
    permit = owner.validate(k.KValidation(proposal.snapshot, proposal.token, uuid4().hex,
                                          proposal.pending_m_revision))
    engine.step(proposal.x, proposal.y, proposal.move.action)
    status = engine.status
    ack = k.make_ack(permit, status, engine.get_observation() if status == GameStatus.PLAYING else None)
    return owner.acknowledge(ack)


def play(engine, state, supplement=None, limit=120):
    """(proposal, info) for every proposal of one small game."""
    owner = k.KOwner(state, TABLE)
    supplement = KInfoSupplement() if supplement is None else supplement
    rows = []
    for _ in range(limit):
        proposal = owner.propose(state)
        rows.append((proposal, supplement.describe(proposal)))
        state = step(owner, engine, proposal)
        if state is None:
            break
    return rows


def wire(proposal, info):
    payload = k.to_dict(proposal)
    if info is not None:
        payload['info'] = k.info_to_dict(info)
    return payload


def certain_cells(grid, num_mines):
    """Independent truth: HIDDEN cells that are safe / mine in every consistent world.

    Flags are read as mines. Plain backtracking over the frontier with an exact
    binomial count for the cells no clue touches. Shares no code with the product.
    """
    height, width = len(grid), len(grid[0])
    hidden = [(x, y) for y in range(height) for x in range(width) if grid[y][x] == H]
    remaining = num_mines - sum(value == F for row in grid for value in row)
    clues = []
    for y in range(height):
        for x in range(width):
            if 0 <= grid[y][x] <= 8:
                around = [(nx, ny) for ny in range(max(0, y - 1), min(height, y + 2))
                          for nx in range(max(0, x - 1), min(width, x + 2)) if (nx, ny) != (x, y)]
                need = grid[y][x] - sum(grid[ny][nx] == F for nx, ny in around)
                clues.append((need, [cell for cell in around if grid[cell[1]][cell[0]] == H]))
    frontier = sorted({cell for _, cells in clues for cell in cells})
    position = {cell: index for index, cell in enumerate(frontier)}
    clues = [(need, [position[cell] for cell in cells]) for need, cells in clues]
    touching = [[] for _ in frontier]
    for number, (_, cells) in enumerate(clues):
        for index in cells:
            touching[index].append(number)
    interior = len(hidden) - len(frontier)
    value = [None] * len(frontier)
    total, mine_ways, interior_mine_ways = 0, [0] * len(frontier), 0
    if any(need != 0 for need, cells in clues if not cells):
        raise AssertionError('fixture grid is inconsistent')

    def feasible(number):
        need, cells = clues[number]
        mines = sum(value[index] == 1 for index in cells)
        unknown = sum(value[index] is None for index in cells)
        return mines <= need <= mines + unknown

    def walk(index, used):
        nonlocal total, interior_mine_ways
        if used > remaining:
            return
        if index == len(frontier):
            rest = remaining - used
            if not 0 <= rest <= interior:
                return
            ways = comb(interior, rest)
            total += ways
            for at, chosen in enumerate(value):
                if chosen:
                    mine_ways[at] += ways
            if interior and rest:
                interior_mine_ways += comb(interior - 1, rest - 1)
            return
        for choice in (0, 1):
            value[index] = choice
            if all(feasible(number) for number in touching[index]):
                walk(index + 1, used + choice)
        value[index] = None

    walk(0, 0)
    assert total > 0
    inside = [cell for cell in hidden if cell not in position]
    safe = {frontier[at] for at, ways in enumerate(mine_ways) if ways == 0}
    mines = {frontier[at] for at, ways in enumerate(mine_ways) if ways == total}
    if inside and interior_mine_ways == 0:
        safe.update(inside)
    if inside and interior_mine_ways == total:
        mines.update(inside)
    return safe, mines


def serve(start, engine=None, *, stop_after=None, validations=1):
    """Run the real worker loop in-process against a small engine."""
    outputs = []

    def read(_directory, _direction, seq, run):
        if seq == 0:
            return message(run, seq, 'START', k.to_dict(start))
        last = outputs[-1]
        if last['kind'] == 'BOOTSTRAPPED':
            summary = k.from_dict(last['payload'], k.KBootstrap)
            return message(run, seq, 'NEXT', k.to_dict(k.after_bootstrap(start, summary)))
        proposals = [m for m in outputs if m['kind'] == 'PROPOSAL']
        if last['kind'] == 'PROPOSAL' or (last['kind'] == 'ADMITTED' and sum(
                1 for m in outputs[outputs.index(proposals[-1]):] if m['kind'] == 'ADMITTED') < validations):
            proposal, _, _ = k.split_proposal_payload(proposals[-1]['payload'])
            return message(run, seq, 'VALIDATE', k.to_dict(k.KValidation(
                proposal.snapshot, proposal.token, uuid4().hex, proposal.pending_m_revision)))
        if last['kind'] == 'ADMITTED':
            admitted = k.from_dict(last['payload'], k.KPermit)
            proposal = admitted.proposal
            if engine is None or (stop_after is not None and len(proposals) >= stop_after):
                return message(run, seq, 'ACK', k.to_dict(k.make_ack(admitted, 'LOST')))
            engine.step(proposal.x, proposal.y, proposal.move.action)
            status = engine.status
            after = engine.get_observation() if status == GameStatus.PLAYING else None
            return message(run, seq, 'ACK', k.to_dict(k.make_ack(admitted, status, after)))
        if last['kind'] == 'ACKED':
            ack = k.from_dict(last['payload'], k.KAck)
            return message(run, seq, 'NEXT', k.to_dict(k.next_snapshot(ack.permit.proposal, ack)))
        raise AssertionError(last['kind'])

    with patch.object(worker, 'read_next', side_effect=read), \
            patch.object(worker, 'write_once', side_effect=lambda d, c, s, m: outputs.append(m)):
        code = worker.serve('unused', start.run_id)
    return code, outputs


def has_key(value, name):
    if isinstance(value, dict):
        return name in value or any(has_key(item, name) for item in value.values())
    if isinstance(value, list):
        return any(has_key(item, name) for item in value)
    return False


# ---------------------------------------------------------------- 1. decision / authority separation
class KInfoSeparationTests(unittest.TestCase):
    def test_kproposal_permit_and_ack_never_carry_info(self):
        self.assertNotIn('info', KPROPOSAL_KEYS)
        self.assertEqual(len(KPROPOSAL_KEYS), 14)
        engine, state = ui_board()
        owner = k.KOwner(state, TABLE)
        proposal = owner.propose(state)
        info = KInfoSupplement().describe(proposal)
        self.assertEqual(set(k.to_dict(proposal)), KPROPOSAL_KEYS)
        self.assertFalse(hasattr(proposal, 'info'))
        permit = owner.validate(k.KValidation(proposal.snapshot, proposal.token, uuid4().hex,
                                              proposal.pending_m_revision))
        ack = k.make_ack(permit, 'LOST')
        for value in (permit, ack):
            self.assertFalse(has_key(k.to_dict(value), 'info'))
        with self.assertRaises(ValueError):   # the strict proposal codec still rejects the extra key
            k.from_dict(wire(proposal, info), k.KProposal)

    def test_describe_reads_the_finished_proposal_and_writes_nothing_back(self):
        engine, state = ui_board()
        owner = k.KOwner(state, TABLE)
        proposal = owner.propose(state)
        before = (owner.pending, owner.decision, owner.selection, owner.singleton_selection,
                  owner.session.M, owner.expected, owner.permit, k.to_dict(proposal))
        info = KInfoSupplement().describe(proposal)
        after = (owner.pending, owner.decision, owner.selection, owner.singleton_selection,
                 owner.session.M, owner.expected, owner.permit, k.to_dict(proposal))
        self.assertTrue(info.safe or info.mines)
        for old, new in zip(before[:4], after[:4]):
            self.assertIs(old, new)
        self.assertEqual(before[4:], after[4:])
        self.assertIs(owner.pending, proposal)

    def test_same_public_states_give_the_same_decisions_with_and_without_the_supplement(self):
        engine_a, state = ui_board()
        engine_b = engine_for(9, 9, UI_MINES, (0, 3))
        code, outputs = serve(state, engine_a)
        self.assertEqual(code, 0)
        with_info = [k.split_proposal_payload(m['payload'])[0] for m in outputs if m['kind'] == 'PROPOSAL']
        owner, current, plain = k.KOwner(state, TABLE), state, []
        while current is not None:
            proposal = owner.propose(current)
            plain.append(proposal)
            current = step(owner, engine_b, proposal)
        self.assertEqual(len(with_info), len(plain))
        self.assertGreater(len(plain), 10)
        for a, b in zip(with_info, plain):
            self.assertEqual(replace(a, token='0' * 32, compute_ns=0), replace(b, token='0' * 32, compute_ns=0))
        self.assertEqual(engine_a.status, engine_b.status)
        self.assertEqual(engine_a.get_observation(), engine_b.get_observation())

    def test_an_info_cell_cannot_authorize_open_or_flag(self):
        engine, state = ui_board()
        rows = play(engine, state)
        tried = 0
        for proposal, info in rows:
            for x, y in info.safe:
                tried += 1
                with self.assertRaises(ValueError):
                    replace(proposal, action='OPEN', x=x, y=y, category='DIRECT_SAFE_OPEN')
            for x, y in info.mines:
                tried += 1
                with self.assertRaises(ValueError):
                    replace(proposal, action='FLAG', x=x, y=y, category='SETUP_CHORD')
        self.assertGreater(tried, 5)

    def test_validation_rejects_a_request_for_an_info_cell_without_consuming(self):
        engine, state = ui_board()
        owner = k.KOwner(state, TABLE)
        proposal = owner.propose(state)
        info = KInfoSupplement().describe(proposal)
        x, y = info.safe[0]
        forged = object.__new__(k.KProposal)
        for name in KPROPOSAL_KEYS:
            object.__setattr__(forged, name, getattr(proposal, name))
        object.__setattr__(forged, 'x', x)
        object.__setattr__(forged, 'y', y)
        with self.assertRaises(ValueError):
            forged.__post_init__()
        with self.assertRaises(ValueError):   # ACK for a different target than the admitted one
            permit = owner.validate(k.KValidation(proposal.snapshot, proposal.token, uuid4().hex,
                                                  proposal.pending_m_revision))
            owner.acknowledge(k.KAck(permit, 'LOST', None, proposal.snapshot.input_revision + 1, (x, y)))
        self.assertIs(owner.pending, proposal)


# ---------------------------------------------------------------- 2. small independent truth
class KInfoSmallTruthTests(unittest.TestCase):
    BOARDS = ((6, 6, 6, 1), (6, 6, 6, 3), (6, 6, 6, 4), (6, 6, 6, 6), (7, 5, 6, 1), (6, 5, 5, 1), (6, 5, 5, 11))

    def games(self):
        for width, height, count, seed in self.BOARDS:
            mines, opening = small_board(width, height, count, seed)
            engine = engine_for(width, height, mines, opening)
            yield (width, height, count, seed), set(mines), engine, adopt(engine, opening)

    def test_complete_equals_the_enumerated_certain_set_on_the_same_hidden_cells(self):
        complete = extra = exact = 0
        for name, layout, engine, state in self.games():
            for proposal, info in play(engine, state):
                grid = proposal.snapshot.observation
                safe, mines = certain_cells(grid, proposal.snapshot.num_mines)
                own_mines = {c for c in proposal.preinput_m if grid[c[1]][c[0]] == H}
                with self.subTest(board=name, seq=proposal.snapshot.input_seq, route=info.route):
                    self.assertFalse(layout & safe)
                    self.assertTrue(mines <= layout)
                    if info.status == 'COMPLETE':
                        complete += 1
                        extra += bool(info.safe or info.mines)
                        self.assertEqual(set(proposal.safe_cells) | set(info.safe), safe)
                        self.assertEqual(own_mines | set(info.mines), mines)
                    else:
                        exact += 1
                        self.assertEqual((info.status, info.safe, info.mines), ('NOT_RUN', (), ()))
                        # The exact route already owns every certain cell: nothing to add.
                        self.assertEqual(set(proposal.safe_cells), safe)
                        self.assertEqual(own_mines, mines)
        self.assertGreater(complete, 30)
        self.assertGreater(extra, 15)
        self.assertGreater(exact, 5)

    def test_partial_is_a_subset_and_never_claims_an_unproven_cell(self):
        partial = cells = 0
        with patch.object(k, 'K_INFO_NODE_BUDGET', 3):
            for name, layout, engine, state in self.games():
                for proposal, info in play(engine, state):
                    grid = proposal.snapshot.observation
                    safe, mines = certain_cells(grid, proposal.snapshot.num_mines)
                    with self.subTest(board=name, seq=proposal.snapshot.input_seq):
                        self.assertTrue(set(info.safe) <= safe)
                        self.assertTrue(set(info.mines) <= mines)
                        self.assertFalse(set(info.safe) & layout)
                        self.assertTrue(set(info.mines) <= layout)
                        if info.status == 'PARTIAL':
                            partial += 1
                            cells += len(info.safe) + len(info.mines)
                            self.assertGreater(info.skipped, 0)
                            self.assertLessEqual(info.nodes, 3)
        self.assertGreater(partial, 10)
        self.assertGreater(cells, 10)

    def test_facts_and_no_facts_passes_prove_the_same_cells_when_both_finish(self):
        compared = 0
        for name, layout, engine, state in self.games():
            for proposal, info in play(engine, state):
                if info.status != 'COMPLETE':
                    continue
                s = proposal.snapshot
                plain = CertaintyEngine().analyze(s.observation, s.num_mines, node_budget=k.K_INFO_NODE_BUDGET)
                if plain.status != 'COMPLETE':
                    continue
                compared += 1
                own_mines = {c for c in proposal.preinput_m if s.observation[c[1]][c[0]] == H}
                self.assertEqual(set(plain.safe), set(proposal.safe_cells) | set(info.safe))
                self.assertEqual(set(plain.mines), own_mines | set(info.mines))
        self.assertGreater(compared, 20)


# ---------------------------------------------------------------- 3. case table through the real worker loop
class KInfoCaseTableTests(unittest.TestCase):
    def proposals(self, outputs):
        return [m['payload'] for m in outputs if m['kind'] == 'PROPOSAL']

    def test_other_k_policies_never_create_the_supplement_or_send_info(self):
        for policy in (POLICY_K, POLICY_K_LC0):
            engine, state = ui_board(policy=policy)
            with self.subTest(policy=policy), \
                    patch.object(live_k_info, 'KInfoSupplement', side_effect=AssertionError('supplement')):
                code, outputs = serve(state, engine, stop_after=4)
                self.assertEqual(code, 0)
                payloads = self.proposals(outputs)
                self.assertEqual(len(payloads), 4)
                for payload in payloads:
                    self.assertEqual(set(payload), KPROPOSAL_KEYS)
                    self.assertEqual(payload, k.to_dict(k.from_dict(payload, k.KProposal)))

    def test_lc1_initial_and_preparation_proposals_have_no_info(self):
        code, outputs = serve(as_policy(initial()))
        self.assertEqual(code, 0)
        first = self.proposals(outputs)[0]
        self.assertEqual((first['kind'], set(first)), ('initial', KPROPOSAL_KEYS))
        code, outputs = serve(as_policy(flag_start()))
        payloads = self.proposals(outputs)
        self.assertEqual(outputs[0]['kind'], 'BOOTSTRAPPED')
        self.assertEqual(payloads[0]['kind'], 'prepare')
        self.assertEqual(set(payloads[0]), KPROPOSAL_KEYS)

    def test_lc1_decisions_always_carry_info_local_runs_once_and_exact_never_searches(self):
        engine, state = ui_board(opening=(0, 8))
        analyze = CertaintyEngine.analyze
        routes = []

        def counted(self, observation, num_mines, **kwargs):
            routes.append('analyze')
            return analyze(self, observation, num_mines, **kwargs)

        with patch.object(CertaintyEngine, 'analyze', autospec=True, side_effect=counted), \
                patch.object(KInfoSupplement, 'describe', autospec=True,
                             side_effect=KInfoSupplement.describe) as describe:
            code, outputs = serve(state, engine, validations=3)
        self.assertEqual(code, 0)
        payloads = self.proposals(outputs)
        self.assertEqual(describe.call_count, len(payloads))          # never on VALIDATE or ACK
        self.assertEqual(sum(m['kind'] == 'ADMITTED' for m in outputs), 3 * len(payloads))
        local = [p for p in payloads if p['continuation'] == 'LOCAL_SAFE']
        exact = [p for p in payloads if p['continuation'] != 'LOCAL_SAFE']
        self.assertGreater(len(local), 5)
        self.assertGreaterEqual(len(exact), 3)
        self.assertEqual(len(routes), len(local))                      # one bounded pass per LOCAL_SAFE
        for payload in payloads:
            self.assertEqual(set(payload), KPROPOSAL_KEYS | {'info'})
            proposal, has_info, raw = k.split_proposal_payload(payload)
            info = k.receive_info(proposal, has_info, raw)
            if payload['continuation'] == 'LOCAL_SAFE':
                self.assertEqual((info.route, info.status), ('local', 'COMPLETE'))
            else:
                self.assertEqual((info.route, info.status, info.safe, info.mines, info.nodes),
                                 ('exact', 'NOT_RUN', (), (), 0))
        for message_ in outputs:
            if message_['kind'] != 'PROPOSAL':
                self.assertFalse(has_key(message_['payload'], 'info'))

    def test_missing_required_info_and_unexpected_info_are_errors_not_omissions(self):
        engine, state = ui_board()
        owner = k.KOwner(state, TABLE)
        proposal = owner.propose(state)
        info = KInfoSupplement().describe(proposal)
        with self.assertRaisesRegex(LivePolicyError, 'KLC1_INFO_D1:MISSING'):
            k.receive_info(proposal, False, None)
        for other in (POLICY_K, POLICY_K_LC0):
            engine, state = ui_board(policy=other)
            plain = k.KOwner(state, TABLE).propose(state)
            self.assertFalse(k.info_required(plain))
            self.assertIsNone(k.receive_info(plain, False, None))
            with self.assertRaisesRegex(LivePolicyError, 'KLC1_INFO_D1:UNEXPECTED'):
                k.receive_info(plain, True, k.info_to_dict(info))
        first = k.KOwner(as_policy(initial()), TABLE)
        opening = first.propose(first.expected)
        self.assertTrue(opening.initial)
        self.assertIsNone(k.receive_info(opening, False, None))
        with self.assertRaisesRegex(LivePolicyError, 'KLC1_INFO_D1:UNEXPECTED'):
            k.receive_info(opening, True, k.info_to_dict(info))
        with self.assertRaisesRegex(LivePolicyError, 'KLC1_INFO_D1:RECEIVED_INVALID'):
            k.receive_info(proposal, True, None)   # "info": null is not an omission


# ---------------------------------------------------------------- 4. binding
class KInfoBindingTests(unittest.TestCase):
    def setUp(self):
        self.engine, state = ui_board()
        self.owner = k.KOwner(state, TABLE)
        self.supplement = KInfoSupplement()
        first = self.owner.propose(state)
        self.first = (first, self.supplement.describe(first))
        state = step(self.owner, self.engine, first)
        self.proposal = self.owner.propose(state)
        self.info = self.supplement.describe(self.proposal)

    def rejected(self, proposal, info=None, needle=None):
        info = self.info if info is None else info
        with self.assertRaises(LivePolicyError) as caught:
            k.validate_info(proposal, info)
        if needle:
            self.assertIn(needle, str(caught.exception))
        with self.assertRaisesRegex(LivePolicyError, 'KLC1_INFO_D1:RECEIVED_INVALID'):
            k.receive_info(proposal, True, k.info_to_dict(info))

    def test_fixture_is_a_local_safe_flag_with_several_safe_cells_and_extra_info(self):
        p = self.proposal
        self.assertEqual((p.continuation, p.action), ('LOCAL_SAFE', 'FLAG'))
        self.assertGreater(len(p.safe_cells), 2)
        self.assertTrue(self.info.safe and self.info.mines)
        self.assertIs(k.validate_info(p, self.info), self.info)

    def test_digest_equals_an_independently_built_canonical_json(self):
        p, s = self.proposal, self.proposal.snapshot
        safe, mines, digest = k.info_basis(p)
        self.assertEqual(safe, p.safe_cells)
        self.assertEqual(mines, tuple(c for c in p.preinput_m if s.observation[c[1]][c[0]] == H))
        expected = {
            'basis_format': 1, 'candidate_id': 'KLC1_INFO_D1', 'run_id': s.run_id,
            'board_generation': s.board_generation, 'input_seq': s.input_seq,
            'input_revision': s.input_revision, 'policy_id': 'K_LC1', 'continuation': 'LOCAL_SAFE',
            'token': p.token, 'width': 9, 'height': 9, 'num_mines': 10,
            'observation': [[int(v) for v in row] for row in s.observation],
            'facts_safe': sorted(([x, y] for x, y in p.safe_cells), key=lambda c: (c[1], c[0])),
            'facts_mines': sorted(([x, y] for x, y in p.preinput_m if s.observation[y][x] == H),
                                  key=lambda c: (c[1], c[0])),
            'node_budget': 20000,
        }
        self.assertEqual(len(expected), 16)
        text = json.dumps(expected, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(',', ':'))
        self.assertEqual(digest, hashlib.sha256(text.encode('ascii')).hexdigest())
        self.assertEqual(self.info.basis_sha256, digest)
        self.assertEqual(k.info_basis(k.from_dict(k.to_dict(p), k.KProposal))[2], digest)   # parent side

    def test_same_token_and_grid_with_changed_safe_cells_is_rejected_by_the_basis(self):
        p = self.proposal
        shown = set(self.info.safe) | set(self.info.mines)
        drop = next(c for c in p.safe_cells if c not in shown)
        changed = replace(p, safe_cells=tuple(c for c in p.safe_cells if c != drop))
        self.assertEqual((changed.token, changed.snapshot), (p.token, p.snapshot))
        self.rejected(changed, needle='basis differs')

    def test_same_token_and_grid_with_changed_preinput_m_is_rejected_by_the_basis(self):
        p, s = self.proposal, self.proposal.snapshot
        taken = set(p.safe_cells) | set(p.preinput_m) | set(self.info.safe) | set(self.info.mines)
        spare = next((x, y) for y in range(s.height) for x in range(s.width)
                     if s.observation[y][x] == H and (x, y) not in taken)
        added = replace(p, preinput_m=k._ordered(set(p.preinput_m) | {spare}))
        self.assertEqual((added.token, added.snapshot), (p.token, p.snapshot))
        self.rejected(added, needle='basis differs')
        # Removing a mine fact: on the first proposal base M is still empty, so a
        # shorter preinput_m is itself a valid KProposal with the same token and grid.
        first, first_info = self.first
        self.assertEqual((first.snapshot.base_m, first.action), ((), 'OPEN'))
        self.assertGreater(len(first.preinput_m), 1)
        removed = replace(first, preinput_m=first.preinput_m[1:])
        self.assertEqual((removed.token, removed.snapshot), (first.token, first.snapshot))
        self.assertIs(k.validate_info(first, first_info), first_info)
        self.rejected(removed, info=first_info, needle='basis differs')

    def test_info_moved_to_another_proposal_run_generation_or_token_is_rejected(self):
        p, s = self.proposal, self.proposal.snapshot
        self.rejected(self.first[0], needle='token')                       # another proposal of this run
        self.rejected(p, info=self.first[1], needle='token')
        self.rejected(replace(p, snapshot=replace(s, run_id=uuid4().hex)), needle='basis differs')
        self.rejected(replace(p, snapshot=replace(s, board_generation=s.board_generation + 1)),
                      needle='basis differs')
        self.rejected(replace(p, token=uuid4().hex), needle='token')
        later = replace(p, pending_m_revision=p.pending_m_revision + 1, snapshot=replace(
            s, input_seq=s.input_seq + 1, input_revision=s.input_revision + 1,
            base_m_revision=s.base_m_revision + 1))
        self.rejected(later, needle='basis differs')

    def test_cells_must_be_hidden_separate_from_the_input_basis_and_within_the_mine_count(self):
        p, s = self.proposal, self.proposal.snapshot
        opened = next((x, y) for y in range(s.height) for x in range(s.width) if s.observation[y][x] >= 0)
        cases = {
            'opened cell': replace(self.info, safe=k._ordered(set(self.info.safe) | {opened})),
            'own safe cell': replace(self.info, safe=k._ordered(set(self.info.safe) | {p.safe_cells[0]})),
            'own M cell': replace(self.info, mines=k._ordered(set(self.info.mines) | {p.preinput_m[0]})),
            'other route': replace(self.info, route='exact', status='NOT_RUN', nodes=0, safe=(), mines=()),
        }
        for name, info in cases.items():
            with self.subTest(name):
                self.rejected(p, info=info)
        hidden = [(x, y) for y in range(s.height) for x in range(s.width)
                  if s.observation[y][x] == H and (x, y) not in p.preinput_m and (x, y) not in p.safe_cells]
        many = replace(self.info, safe=(), mines=k._ordered(hidden[:s.num_mines - len(p.preinput_m) + 1]))
        self.rejected(p, info=many, needle='mine count')

    def test_wire_normalization_rejects_order_duplicates_bool_float_null_and_unknown_keys(self):
        good = k.info_to_dict(self.info)
        self.assertEqual(k.info_from_dict(good), self.info)
        self.assertEqual(len(good), 12)
        a, b = good['safe'][0], good['safe'][1]
        bad = {
            'unordered': dict(good, safe=[b, a] + good['safe'][2:]),
            'duplicate': dict(good, safe=[a, a] + good['safe'][1:]),
            'bool coordinate': dict(good, safe=[[True, a[1]]] + good['safe'][1:]),
            'float coordinate': dict(good, safe=[[float(a[0]), a[1]]] + good['safe'][1:]),
            'tuple-like triple': dict(good, safe=[a + [0]] + good['safe'][1:]),
            'null cells': dict(good, mines=None),
            'bool nodes': dict(good, nodes=True),
            'float budget': dict(good, node_budget=20000.0),
            'other budget': dict(good, node_budget=19999),
            'uppercase digest': dict(good, basis_sha256=good['basis_sha256'].upper()),
            'unknown key': dict(good, extra=1),
            'missing key': {name: value for name, value in good.items() if name != 'skipped'},
            'old state key': dict({n: v for n, v in good.items() if n != 'basis_sha256'}, state_sha256='0' * 64),
            'removed status': dict(good, status='INCONSISTENT'),
            'error on success': dict(good, error='RuntimeError'),
            'partial without skipped': dict(good, status='PARTIAL'),
            'not a dict': [good],
        }
        for name, value in bad.items():
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    k.info_from_dict(value)
                with self.assertRaisesRegex(LivePolicyError, 'KLC1_INFO_D1:RECEIVED_INVALID'):
                    k.receive_info(self.proposal, True, value)

    def test_engine_is_kept_only_across_consecutive_inputs_of_one_run(self):
        engine = self.supplement._engine
        state = step(self.owner, self.engine, self.proposal)
        third = self.owner.propose(state)
        self.supplement.describe(third)
        self.assertIs(self.supplement._engine, engine)                    # consecutive input: carried
        state = step(self.owner, self.engine, third)
        self.owner.propose(state)                                         # one proposal never described
        state = step(self.owner, self.engine, self.owner.pending)
        fifth = self.owner.propose(state)
        self.supplement.describe(fifth)
        self.assertIsNot(self.supplement._engine, engine)                 # gap: a new engine
        other_engine, other_state = ui_board()
        other = k.KOwner(other_state, TABLE).propose(other_state)
        gap = self.supplement._engine
        self.supplement.describe(other)
        self.assertIsNot(self.supplement._engine, gap)                    # other run: a new engine


# ---------------------------------------------------------------- 5. failures and errors
class KInfoFailureTests(unittest.TestCase):
    def first_error(self, outputs):
        self.assertEqual([m['kind'] for m in outputs][-1], 'ERROR')
        return outputs[-1]['payload']

    def test_partial_and_supplement_only_failure_still_deliver_the_original_proposal(self):
        engine, state = ui_board()
        with patch.object(k, 'K_INFO_NODE_BUDGET', 3):
            code, outputs = serve(state, engine, stop_after=3)
        self.assertEqual(code, 0)
        statuses = [m['payload']['info']['status'] for m in outputs if m['kind'] == 'PROPOSAL']
        self.assertIn('PARTIAL', statuses)

        engine, state = ui_board()
        owner, supplement = k.KOwner(state, TABLE), KInfoSupplement()
        proposal = owner.propose(state)
        with patch.object(CertaintyEngine, 'analyze', side_effect=RuntimeError('fixture')):
            failed = supplement.describe(proposal)
        self.assertEqual((failed.status, failed.error, failed.safe, failed.mines, failed.nodes),
                         ('FAILED', 'RuntimeError', (), (), 0))
        self.assertIsNone(supplement._engine)                             # the failed engine is gone
        self.assertIs(k.validate_info(proposal, failed), failed)
        self.assertEqual(k.receive_info(proposal, True, k.info_to_dict(failed)), failed)
        following = owner.propose(step(owner, engine, proposal))
        recovered = supplement.describe(following)
        self.assertEqual(recovered.status, 'COMPLETE')
        self.assertIsNotNone(supplement._engine)
        view = present_k_proposal(proposal, failed)
        self.assertEqual(view.overlays, present_k_proposal(proposal).overlays)

        engine, state = ui_board()
        with patch.object(CertaintyEngine, 'analyze', side_effect=KeyError('fixture')):
            code, outputs = serve(state, engine, stop_after=2)
        self.assertEqual(code, 0)
        infos = [m['payload']['info'] for m in outputs if m['kind'] == 'PROPOSAL']
        self.assertEqual([(i['status'], i['error']) for i in infos], [('FAILED', 'KeyError')] * 2)

    def test_contradiction_publishes_no_proposal_and_ends_the_worker_with_error(self):
        for where in ('analyze', 'note_facts'):
            engine, state = ui_board(opening=(0, 8) if where == 'note_facts' else (0, 3))
            with self.subTest(where=where), patch.object(
                    CertaintyEngine, where, side_effect=InconsistentObservationError('fixture contradiction')):
                code, outputs = serve(state, engine)
                self.assertEqual(code, 1)
                self.assertEqual([m['kind'] for m in outputs], ['ERROR'])   # the original proposal never left
                error = self.first_error(outputs)
                self.assertEqual(error['code'], 'WORKER')
                self.assertIn('KLC1_INFO_D1:CONTRADICTION', error['detail'])
                self.assertEqual(k.info_error_code(error['detail']), 'CONTRADICTION')

    def test_real_contradiction_from_wrong_facts_is_not_downgraded_to_failed(self):
        engine, state = ui_board()
        owner = k.KOwner(state, TABLE)
        proposal = owner.propose(state)
        supplement = KInfoSupplement()
        real = k.info_basis

        def poisoned(value):
            # Facts that cannot all be true: every other HIDDEN cell declared a mine.
            safe, _, digest = real(value)
            s = value.snapshot
            hidden = {(x, y) for y in range(s.height) for x in range(s.width) if s.observation[y][x] == H}
            return safe, k._ordered(hidden - set(safe)), digest

        with patch.object(k, 'info_basis', side_effect=poisoned):
            with self.assertRaisesRegex(LivePolicyError, 'KLC1_INFO_D1:CONTRADICTION'):
                supplement.describe(proposal)   # the unpatched engine itself reports it
        self.assertIsNone(supplement._engine)

    def test_sender_side_integrity_errors_end_the_worker_instead_of_dropping_info(self):
        cases = {
            'record': patch.object(k, 'validate_info', side_effect=LivePolicyError('fixture record')),
            'basis': patch.object(k, 'info_basis', side_effect=LivePolicyError('fixture basis')),
        }
        for name, patcher in cases.items():
            engine, state = ui_board()
            with self.subTest(name), patcher:
                code, outputs = serve(state, engine)
                self.assertEqual((code, [m['kind'] for m in outputs]), (1, ['ERROR']))
                self.assertEqual(k.info_error_code(self.first_error(outputs)['detail']), 'SENDER_INVALID')

    def test_memory_error_and_unpublishable_error_follow_the_existing_worker_path(self):
        engine, state = ui_board()
        with patch.object(CertaintyEngine, 'analyze', side_effect=MemoryError('fixture')):
            code, outputs = serve(state, engine)
        self.assertEqual((code, [m['kind'] for m in outputs]), (1, ['ERROR']))
        self.assertTrue(self.first_error(outputs)['detail'].startswith('MemoryError'))
        self.assertIsNone(k.info_error_code(self.first_error(outputs)['detail']))

        engine, state = ui_board()
        with patch.object(CertaintyEngine, 'analyze', side_effect=InconsistentObservationError('fixture')), \
                patch.object(worker, 'read_next', return_value=message(state.run_id, 0, 'START', k.to_dict(state))), \
                patch.object(worker, 'write_once', side_effect=OSError('channel gone')):
            self.assertEqual(worker.serve('unused', state.run_id), 1)

        engine, state = ui_board()
        with patch.object(CertaintyEngine, 'analyze', side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):                     # never turned into FAILED
                serve(state, engine)

    @staticmethod
    def unusable_returns():
        """Values an engine call hands back normally, but that cannot become an info record."""
        good = Outcome('COMPLETE', frozenset(), frozenset(), 0, 0, 0, 0, 0, 0)
        return {
            'none': None,
            'safe is None': replace(good, safe=None),
            'mines is None': replace(good, mines=None),
            'cells that cannot be ordered': replace(good, safe=frozenset({'x'})),
            'another type with the same attributes': Mock(
                status='COMPLETE', safe=frozenset(), mines=frozenset(), nodes=0, skipped=0),
            'unknown status': replace(good, status='WEIRD'),
            'bool node count': replace(good, nodes=True),
        }

    def test_errors_after_the_engine_returned_are_integrity_errors_not_failed(self):
        # Design 8.2: FAILED is only an ordinary exception raised INSIDE analyze/note_facts.
        # Anything wrong with the returned value or its post-processing is outside that call.
        for name, value in self.unusable_returns().items():
            engine, state = ui_board()
            owner, supplement = k.KOwner(state, TABLE), KInfoSupplement()
            proposal = owner.propose(state)
            with self.subTest(name, level='describe'), patch.object(CertaintyEngine, 'analyze', return_value=value):
                with self.assertRaisesRegex(LivePolicyError, 'KLC1_INFO_D1:SENDER_INVALID'):
                    supplement.describe(proposal)
                self.assertIsNone(supplement._engine)                      # the engine is discarded
                self.assertIs(owner.pending, proposal)
            engine, state = ui_board()
            with self.subTest(name, level='worker'), patch.object(CertaintyEngine, 'analyze', return_value=value):
                code, outputs = serve(state, engine)
                self.assertEqual((code, [m['kind'] for m in outputs]), (1, ['ERROR']))   # no PROPOSAL published
                self.assertEqual(k.info_error_code(outputs[-1]['payload']['detail']), 'SENDER_INVALID')

    def test_the_same_exception_types_raised_inside_the_engine_call_stay_failed(self):
        for error in (AttributeError('inside'), TypeError('inside'), IndexError('inside'), ValueError('inside')):
            engine, state = ui_board()
            owner, supplement = k.KOwner(state, TABLE), KInfoSupplement()
            proposal = owner.propose(state)
            with self.subTest(type(error).__name__), patch.object(CertaintyEngine, 'analyze', side_effect=error):
                failed = supplement.describe(proposal)
                self.assertEqual((failed.route, failed.status, failed.error, failed.safe, failed.mines),
                                 ('local', 'FAILED', type(error).__name__, (), ()))
                self.assertIsNone(supplement._engine)
                engine, state = ui_board()
                code, outputs = serve(state, engine, stop_after=1)
                self.assertEqual((code, [m['kind'] for m in outputs][0]), (0, 'PROPOSAL'))   # original proposal delivered
                self.assertEqual(outputs[0]['payload']['info']['status'], 'FAILED')
        engine, state = ui_board(opening=(0, 8))                           # exact route: note_facts only
        owner, supplement = k.KOwner(state, TABLE), KInfoSupplement()
        proposal = owner.propose(state)
        with patch.object(CertaintyEngine, 'note_facts', side_effect=TypeError('inside')):
            failed = supplement.describe(proposal)
        self.assertEqual((failed.route, failed.status, failed.error), ('exact', 'FAILED', 'TypeError'))

    def test_normal_engine_results_are_unchanged_by_the_narrower_failure_scope(self):
        engine, state = ui_board(opening=(0, 8))
        statuses = [(p.continuation, info.status, info.error) for p, info in play(engine, state)]
        self.assertEqual({s for s in statuses if s[0] == 'LOCAL_SAFE'}, {('LOCAL_SAFE', 'COMPLETE', '')})
        self.assertEqual({s[1:] for s in statuses if s[0] != 'LOCAL_SAFE'}, {('NOT_RUN', '')})
        engine, state = ui_board()
        with patch.object(k, 'K_INFO_NODE_BUDGET', 3):
            partial = [info.status for _, info in play(engine, state)]
        self.assertIn('PARTIAL', partial)
        self.assertLessEqual(set(partial), {'COMPLETE', 'PARTIAL', 'NOT_RUN'})

    def test_info_for_another_proposal_cannot_be_displayed(self):
        engine, state = ui_board()
        rows = play(engine, state, limit=2)
        with self.assertRaises(ValueError):
            present_k_proposal(rows[1][0], rows[0][1])


# ---------------------------------------------------------------- 5/6/7/8. parent job
class KInfoJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.engine, self.state = ui_board()
        self.owner = k.KOwner(self.state, TABLE)
        self.supplement = KInfoSupplement()
        self.start(self.state)

    def start(self, state):
        self.now = 0.0
        self.job = jobs.LivePolicyJob(clock=lambda: self.now)
        self.addCleanup(self.job.shutdown)
        self.ready = QSignalSpy(self.job.proposal_ready)
        self.process = Mock()
        self.process.poll.return_value = None
        self.process.wait.return_value = 0
        with patch.object(jobs.subprocess, 'Popen', return_value=self.process), \
                patch.object(jobs, 'create_scope', return_value=None):
            self.job.start(state)
        self.job.timer.stop()

    def publish(self, kind, payload):
        write_once(self.job._directory, 'worker', self.job._sequence,
                   message(self.job.active_run_id, self.job._sequence, kind, payload))
        self.job.poll()

    def make(self, state=None):
        proposal = self.owner.propose(self.state if state is None else state)
        return proposal, self.supplement.describe(proposal)

    def reap(self, code=0):
        self.process.poll.return_value = code
        self.job.poll()
        return self.job.last_record

    def assert_failed(self, code):
        self.assertEqual(self.job.state, 'cancelling')
        self.assertTrue(self.job._failure.startswith('REPLY_TRANSPORT:'))
        self.assertIsNone(self.job.pending)
        self.assertIsNone(self.job.pending_info)
        self.assertEqual((len(self.ready), self.job._applied_count), (0, 0))
        record = self.reap(1)
        self.assertEqual((record['status'], record['k_info_error']), ('FAILED', code))
        self.assertTrue(record['cleanup_complete'])
        self.assertEqual(sum(record['k_info_counts'].values()), record['proposal_count'])
        return record

    def test_valid_info_is_kept_beside_pending_and_counted_once(self):
        proposal, info = self.make()
        self.publish('PROPOSAL', wire(proposal, info))
        self.assertEqual((self.job.state, self.job.pending, self.job.pending_info), ('pending', proposal, info))
        self.assertEqual(len(self.ready), 1)
        self.assertEqual(self.job._k_info_counts,
                         {'COMPLETE': 1, 'PARTIAL': 0, 'NOT_RUN': 0, 'FAILED': 0, 'NOT_APPLICABLE': 0})
        for _ in range(3):                                                 # repeated VALIDATE / pause
            nonce = uuid4().hex
            self.job.validate_pending(proposal.snapshot, nonce)
            permit = self.owner.validate(self.job._sent_validation)
            self.job.invalidate_admission()
            self.publish('ADMITTED', k.to_dict(permit))
            self.assertEqual((self.job.state, self.job.pending_info), ('pending', info))
        self.assertEqual(sum(self.job._k_info_counts.values()), 1)
        self.assertEqual(self.job._proposal_count, 1)

    def test_ack_clears_pending_info_and_the_next_proposal_brings_its_own(self):
        proposal, info = self.make()
        self.publish('PROPOSAL', wire(proposal, info))
        self.job.validate_pending(proposal.snapshot, uuid4().hex)
        permit = self.owner.validate(self.job._sent_validation)
        self.publish('ADMITTED', k.to_dict(permit))
        self.job.mark_applying(proposal.token, permit.nonce)
        self.assertEqual(self.job.pending_info, info)                      # still pending until ACKED
        self.engine.step(proposal.x, proposal.y, proposal.move.action)
        self.job.acknowledge('PLAYING', self.engine.get_observation())
        ack = self.job._sent_ack
        following = self.owner.acknowledge(ack)
        self.publish('ACKED', k.to_dict(ack))
        self.assertEqual((self.job.state, self.job.pending, self.job.pending_info), ('ready', None, None))
        self.job.request(following)
        second, second_info = self.make(following)
        self.publish('PROPOSAL', wire(second, second_info))
        self.assertEqual(self.job.pending_info, second_info)
        self.assertNotEqual(second_info.token, info.token)
        self.assertEqual(sum(self.job._k_info_counts.values()), 2)

    def test_pause_while_computing_still_receives_keeps_and_counts_the_proposal_once(self):
        self.job.invalidate_admission()                                    # Auto OFF during computing
        self.assertEqual((self.job.state, self.job._deadline), ('computing', 30.0))
        proposal, info = self.make()
        self.now = 12.0
        self.publish('PROPOSAL', wire(proposal, info))
        self.assertEqual((self.job.state, self.job.pending_info), ('pending', info))
        self.assertEqual(self.job._applied_count, 0)
        self.now = 10000.0
        self.job.poll()                                                    # an idle pending has no cap
        self.assertEqual((self.job.state, self.job.pending_info), ('pending', info))
        self.assertEqual(sum(self.job._k_info_counts.values()), 1)

    def test_receiver_side_integrity_errors_reject_the_whole_reply(self):
        proposal, info = self.make()
        tampered = {
            'RECEIVED_INVALID': wire(proposal, replace(info, basis_sha256='0' * 64)),
            'MISSING': k.to_dict(proposal),
        }
        for code, payload in tampered.items():
            with self.subTest(code):
                self.publish('PROPOSAL', payload)
                self.assert_failed(code)
                self.start(self.state)

    def test_info_on_a_proposal_that_must_not_carry_it_is_rejected(self):
        proposal, info = self.make()
        engine, state = ui_board(policy=POLICY_K_LC0)
        self.start(state)
        plain = k.KOwner(state, TABLE).propose(state)
        self.publish('PROPOSAL', dict(k.to_dict(plain), info=k.info_to_dict(info)))
        self.assertTrue(self.job._failure.startswith('REPLY_TRANSPORT:'))
        self.assertIn('KLC1_INFO_D1:UNEXPECTED', self.job._failure)
        self.assertIsNone(self.job.pending)
        record = self.reap(1)
        self.assertEqual(record['status'], 'FAILED')
        self.assertNotIn('k_info_counts', record)                          # other K policies: record unchanged
        self.start(state)
        self.publish('PROPOSAL', k.to_dict(plain))                         # and without info it is accepted
        self.assertEqual((self.job.state, self.job.pending, self.job.pending_info), ('pending', plain, None))

    def test_sender_and_receiver_detection_end_the_run_the_same_way(self):
        with patch.object(CertaintyEngine, 'analyze', side_effect=InconsistentObservationError('fixture')):
            code, outputs = serve(self.state, self.engine)
        self.assertEqual((code, [m['kind'] for m in outputs]), (1, ['ERROR']))
        self.publish('ERROR', outputs[-1]['payload'])
        sender = self.assert_failed('CONTRADICTION')
        self.start(self.state)
        with patch.object(k, 'validate_info', side_effect=LivePolicyError('fixture')):
            code, outputs = serve(self.state, self.engine)
        self.publish('ERROR', outputs[-1]['payload'])
        self.assert_failed('SENDER_INVALID')
        self.start(self.state)
        proposal, info = self.make()
        self.publish('PROPOSAL', wire(proposal, replace(info, token=uuid4().hex)))
        receiver = self.assert_failed('RECEIVED_INVALID')
        for record in (sender, receiver):
            self.assertEqual((record['proposal_count'], record['consumed_token_count'], record['ack_count']),
                             (0, 0, 0))

    def test_version_mix_old_parent_rejects_info_and_new_parent_rejects_its_absence(self):
        self.assertEqual(PROTOCOL_VERSION, 10)
        proposal, info = self.make()
        payload = wire(proposal, info)
        with self.assertRaises(ValueError):                                # old parent: strict 14-key codec
            k.from_dict(payload, k.KProposal)
        self.publish('PROPOSAL', k.to_dict(proposal))                      # old worker: no info
        self.assert_failed('MISSING')
        self.start(self.state)
        self.publish('PROPOSAL', payload)                                  # new + new
        self.assertEqual(self.job.pending_info, info)

    def test_reply_just_inside_the_thirty_second_cap_is_accepted(self):
        proposal, info = self.make()
        self.now = 29.999
        self.publish('PROPOSAL', wire(proposal, info))
        self.assertEqual((self.job.state, self.job.pending_info, self.job._deadline), ('pending', info, None))

    def test_cap_covers_decision_plus_supplement_and_a_late_proposal_is_never_delivered(self):
        proposal, info = self.make()
        self.now = 30.0
        self.job.poll()
        self.assertEqual((self.job._intent, self.job._intent_reason, self.job.state),
                         ('TIMEOUT', 'computing', 'cancelling'))
        write_once(self.job._directory, 'worker', self.job._sequence,
                   message(self.job.active_run_id, self.job._sequence, 'PROPOSAL', wire(proposal, info)))
        self.job.poll()
        self.assertEqual((len(self.ready), self.job.pending, self.job.pending_info), (0, None, None))
        self.process.terminate.assert_called_once()
        self.process.kill.assert_not_called()
        self.now = 30.4
        self.job.poll()
        self.process.kill.assert_not_called()                             # the cap is not the reap time
        self.now = 30.5
        self.job.poll()
        self.process.kill.assert_called_once()
        self.now = 31.6
        self.job.poll()
        self.assertEqual(self.job.state, 'blocked')
        record = self.reap(1)
        self.assertEqual((record['status'], record['intent_reason'], record['k_info_error']),
                         ('TIMEOUT', 'computing', None))
        self.assertEqual((record['proposal_count'], sum(record['k_info_counts'].values())), (0, 0))

    def test_cancel_reaps_and_the_record_keeps_the_counts_made_so_far(self):
        proposal, info = self.make()
        self.publish('PROPOSAL', wire(proposal, info))
        directory = self.job._directory
        self.job.cancel('manual')
        self.assertEqual((self.job.pending, self.job.pending_info), (None, None))
        record = self.reap(0)
        self.assertEqual((record['status'], record['intent_reason'], record['cleanup_complete']),
                         ('CANCELLED', 'manual', True))
        self.assertEqual(record['k_info_counts'],
                         {'COMPLETE': 1, 'PARTIAL': 0, 'NOT_RUN': 0, 'FAILED': 0, 'NOT_APPLICABLE': 0})
        self.assertIsNone(record['k_info_error'])
        self.assertFalse(directory.exists())
        self.assertEqual(self.job.state, 'idle')

    def test_unusable_engine_return_reaches_the_parent_as_sender_invalid_and_nothing_is_applied(self):
        with patch.object(CertaintyEngine, 'analyze', return_value=None):
            code, outputs = serve(self.state, self.engine)
        self.assertEqual((code, [m['kind'] for m in outputs]), (1, ['ERROR']))
        self.publish('ERROR', outputs[-1]['payload'])
        self.assert_failed('SENDER_INVALID')

    def test_initial_proposal_is_counted_as_not_applicable(self):
        state = as_policy(initial())
        self.start(state)
        opening = k.KOwner(state, TABLE).propose(state)
        self.publish('PROPOSAL', k.to_dict(opening))
        self.assertEqual((self.job.pending, self.job.pending_info), (opening, None))
        self.assertEqual(self.job._k_info_counts['NOT_APPLICABLE'], 1)


# ---------------------------------------------------------------- 6. UI lifetime: pause / display off / discard
class InfoFakeJob(lc0.FamilyFakeJob):
    """The K UI fake job plus the real job's display-info seam (same rule functions)."""

    def start(self, snapshot):
        self.supplement = (KInfoSupplement() if type(snapshot) is k.KSnapshot
                           and snapshot.policy_id == POLICY_K_LC1 else None)
        self._info = None
        self.described = 0
        return super().start(snapshot)

    def deliver(self, proposal):
        self._info = None
        if type(proposal) is k.KProposal:
            record = self.supplement.describe(proposal) if self.supplement is not None else None
            self.described += record is not None
            received, has_info, raw = k.split_proposal_payload(wire(proposal, record))
            self._info = k.receive_info(received, has_info, raw)
        super().deliver(proposal)

    @property
    def pending_info(self):
        return self._info if self.pending is not None else None


class KInfoUITests(unittest.TestCase):
    close_ui = base.LiveKUITests.close_ui
    tick = base.LiveKUITests.tick
    select = lc0.LiveLC0UITests.select

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(base, 'KUIFakeJob', InfoFakeJob):
            base.LiveKUITests.setUp(self)
        self.select(POLICY_K_LC1)
        self.ui.on_reset()
        self.ui.simple_auto_interval_spin.setValue(2000)

    def adopt(self):
        self.ui.on_left_click(0, 3)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.job.compute()
        self.assertIsNotNone(self.job.pending_info)
        return self.job.pending, self.job.pending_info

    def shown(self):
        return {cell: button.analysis_overlay.kind for cell, button in self.ui._buttons.items()
                if button.analysis_overlay is not None and button.analysis_overlay.kind is not None}

    def test_info_cells_are_colors_only_beside_the_original_overlays(self):
        proposal, info = self.adopt()
        self.assertEqual((proposal.continuation, info.status), ('LOCAL_SAFE', 'COMPLETE'))
        self.assertTrue(info.safe)
        plain = present_k_proposal(proposal).overlays
        result = self.ui._analysis_result.overlays
        for cell in info.safe + info.mines:
            self.assertNotIn(cell, plain)
            overlay = result[cell]
            self.assertIs(overlay.kind, OverlayKind.SAFE if cell in info.safe else OverlayKind.MINE)
            self.assertEqual((overlay.recommended, overlay.probability), (False, None))
        for cell, overlay in plain.items():
            self.assertEqual(result[cell], overlay)                        # decision overlays untouched
        self.assertEqual(set(result), set(plain) | set(info.safe) | set(info.mines))
        self.assertEqual(self.ui._analysis_result.move, proposal.move)
        shown = self.shown()
        for cell in info.safe:
            self.assertIs(shown[cell], OverlayKind.SAFE)

    def test_pause_keeps_owner_pending_info_and_display_and_resume_does_not_recompute(self):
        proposal, info = self.adopt()
        shown, requests = self.shown(), len(self.job.requests)
        self.ui.simple_auto_checkbox.setChecked(False)                     # pause
        self.assertTrue(self.ui._v1_owned)
        self.assertIs(self.ui._v1_pending, proposal)
        self.assertEqual(self.job.pending_info, info)
        self.assertIsNotNone(self.ui._certainty_frame)
        self.assertEqual(self.shown(), shown)
        self.assertIn('일시정지', self.ui._v1_status)
        self.ui.simple_auto_checkbox.setChecked(True)                      # resume
        self.assertEqual((len(self.job.requests), self.job.described), (requests, 1))
        self.assertIs(self.ui._v1_pending, proposal)
        self.assertEqual(self.shown(), shown)
        self.assertEqual(self.ui._live_action_count, 1)                    # only the manual opening so far

    def test_display_off_clears_the_colors_and_on_redraws_them_without_recomputing(self):
        proposal, info = self.adopt()
        shown = self.shown()
        self.ui.analysis_checkbox.setChecked(False)
        self.assertEqual(self.shown(), {})
        self.assertIsNone(self.ui._certainty_frame)
        self.assertTrue(self.ui._v1_owned)
        self.assertIs(self.ui._v1_pending, proposal)
        self.assertEqual(self.job.pending_info, info)
        self.ui.analysis_checkbox.setChecked(True)
        self.assertEqual(self.shown(), shown)
        self.assertEqual(self.job.described, 1)

    def test_manual_input_policy_change_and_new_game_discard_info_and_display(self):
        for name in ('manual', 'policy', 'new game'):
            with self.subTest(name):
                proposal, info = self.adopt()
                self.assertTrue(self.shown())
                if name == 'manual':
                    self.ui.on_right_click(8, 0)
                elif name == 'policy':
                    self.select(POLICY_K)
                else:
                    self.ui.on_reset()
                self.assertFalse(self.ui._v1_owned)
                self.assertIsNone(self.ui._v1_pending)
                self.assertIsNone(self.job.pending_info)
                self.assertIsNone(self.ui._certainty_frame)
                self.assertEqual(self.shown(), {})
                self.job.complete_cancel()
                self.select(POLICY_K_LC1)
                self.ui.on_reset()

    def test_ack_ends_the_pending_info_while_still_hidden_colors_stay_on_screen(self):
        proposal, info = self.adopt()
        self.tick()
        self.job.deliver_admission()
        record = self.ui.live_action_records[-1]
        self.assertEqual((record['token'], record['info_status']), (proposal.token, 'COMPLETE'))
        self.job.deliver_ack()
        self.assertIsNone(self.job.pending_info)                           # pending info ended with the ACK
        observation = self.ui.engine.get_observation()
        still_hidden = [cell for cell in info.safe if observation[cell[1]][cell[0]] == H]
        self.assertTrue(still_hidden)
        shown = self.shown()
        for cell in still_hidden:
            self.assertIs(shown[cell], OverlayKind.SAFE)                   # the frame keeps what was shown
        self.job.compute()
        self.assertEqual(self.job.described, 2)
        self.assertNotEqual(self.job.pending_info.token, info.token)

    def test_integrity_failure_ends_the_run_clears_the_display_and_never_restarts(self):
        proposal, info = self.adopt()
        self.assertTrue(self.shown())
        requests = len(self.job.requests)
        record = {'run_id': self.job.active_run_id, 'status': 'FAILED', 'policy_id': POLICY_K_LC1,
                  'error': "REPLY_TRANSPORT: ValueError('WORKER: LivePolicyError: KLC1_INFO_D1:CONTRADICTION fixture')",
                  'cleanup_complete': True, 'reaped': True, 'tree_active_count': 0}
        self.job.active_run_id, self.job.pending, self.job.state = None, None, 'idle'
        self.job.records.append(record)
        self.job.last_record = record
        self.job.finished.emit(record)
        self.assertFalse(self.ui._v1_owned)
        self.assertTrue(self.ui._v1_manual_only)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        self.assertIsNone(self.ui._v1_pending)
        self.assertIsNone(self.ui._certainty_frame)
        self.assertEqual(self.shown(), {})
        self.assertIn('KLC1_INFO_D1:CONTRADICTION', self.ui.live_failure_records[-1]['cause'])
        self.assertEqual(self.ui._live_action_count, 1)                    # the pending proposal was not applied
        self.ui.simple_auto_checkbox.setChecked(True)                      # no automatic or manual restart
        self.assertEqual(len(self.job.requests), requests)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())


if __name__ == '__main__':
    unittest.main()
