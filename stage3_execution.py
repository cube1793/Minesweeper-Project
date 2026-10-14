"""Fixed benchmark context beside an unchanged, complete Stage-3 result.

Board truth is retained for setup and reconstruction only. The frozen runner
owns the canonical first OPEN and every subsequent action.
"""

from dataclasses import dataclass

from benchmark_board import (
    EXPERT_GENERAL_V1, BenchmarkBoard, BenchmarkSetSpec, generate_board,
)
from core_engine import MinesweeperEngine
from stage3_runner import Stage3RunResult, run_stage3


@dataclass(frozen=True)
class Stage3Execution:
    """Retain the source identity and result, without a live engine or copies."""

    spec: BenchmarkSetSpec
    board: BenchmarkBoard
    result: Stage3RunResult


def run_expert_stage3_execution(game_index: int) -> Stage3Execution:
    """Run exactly one EXPERT_GENERAL_V1 index, without filtering or retries.

    generate_board owns index validation and layout/fingerprint correspondence;
    reset_with_mines installs that layout without moving or opening any cells.
    Only the engine is passed to the frozen Stage-3 execution boundary.
    """
    spec = EXPERT_GENERAL_V1
    board = generate_board(spec, game_index)
    engine = MinesweeperEngine(spec.width, spec.height, spec.num_mines)
    engine.reset_with_mines(spec.width, spec.height, spec.num_mines, board.mine_positions)
    result = run_stage3(engine)
    return Stage3Execution(spec, board, result)
