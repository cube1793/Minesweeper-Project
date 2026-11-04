"""Declared public reveal-state seam, not a natural first-click flood.

Matches the small premise in test_program_k_lc1. Mines are installed only in
the test Engine; the owner receives the resulting public observation. Later
inputs use the unchanged Engine. No native graph, M, selection or route stub.
"""
from dataclasses import replace
from uuid import uuid4

from core_engine import MinesweeperEngine
import live_k_policy as k

SINGLETON_MINES = frozenset({(2, 2), (0, 11)})
SINGLETON_SAFE = frozenset({(2, 1), (0, 10), (1, 10), (2, 10)})
LC1_FIRST = ('OPEN', 2, 1)
BASELINE_FIRST = ('FLAG', 0, 11)


def singleton_engine():
    engine = MinesweeperEngine(6, 14, 2)
    install_singleton(engine)
    return engine


def install_singleton(engine):
    engine.reset_with_mines(6, 14, 2, SINGLETON_MINES)
    hidden = SINGLETON_MINES | SINGLETON_SAFE
    engine._revealed = [[(x, y) not in hidden for x in range(6)] for y in range(14)]


def as_policy(state, policy=k.POLICY_K_LC1):
    return replace(state, policy_id=policy, definition=k.definition_for_entry(state.entry_mode, policy),
                   phase=state.phase if state.phase in (k.PHASE_BOOTSTRAP, k.PHASE_PREPARATION)
                   else k.normal_phase(policy))


def singleton_start(policy=k.POLICY_K_LC1, *, cursor=(0, 0), revision=1):
    engine = singleton_engine()
    return k.make_snapshot(run_id=uuid4().hex, game_id=uuid4().hex, board_generation=1,
        input_seq=0, width=6, height=14, num_mines=2, observation=engine.get_observation(),
        cursor=cursor, input_revision=revision, start_input_revision=revision,
        entry_mode=k.ADOPT_CURRENT, policy_id=policy,
        definition=k.definition_for_entry(k.ADOPT_CURRENT, policy), phase=k.normal_phase(policy))
