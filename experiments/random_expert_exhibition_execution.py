"""One NEW Expert pair, executed only in the dedicated non-GUI child.

Canonical runners own inference and input selection. Layout is used solely to
install/verify two fresh engines. No research harness or accepted archive IO.
"""

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

from benchmark_board import EXPERT_GENERAL_V1, calculate_board_fingerprint, generate_board
from core_engine import CellState, GameStatus, MinesweeperEngine
from experiments.program_k_evidence import validate_public_effect_stream
from experiments.program_k_runner import ControlCaptureResult, KRunResult, run_control_capture, run_k_p0
from experiments.random_expert_exhibition_model import (
    ExhibitionAction, ExhibitionBoard, ExhibitionFrame, ExhibitionPair, ExhibitionSource,
    ExhibitionTrace, validate_index,
)
from stage3_identity import STAGE3_V1_IDENTITY
from stage3_physical import MODEL_C_V1_IDENTITY, action_cost, load_timing_table


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = (
    "benchmark_board.py", "core_engine.py", "board_analyzer.py", "board_snapshot.py",
    "simple_algorithm.py", "simple_decision.py", "simple_probability.py",
    "stage3_runner.py", "stage3_planner.py", "stage3_physical.py", "stage3_identity.py",
    "stage3_modeled_playback.py", "visualization_reference_overlays.py", "qt_bootstrap.py",
    "telemetry_schema.py", "experiments/program_k_runner.py",
    "experiments/program_k_capability.py", "experiments/program_k_policy.py",
    "experiments/program_k_oracles.py", "experiments/program_k_evidence.py",
    "calibration/stage3_physical_profile_v1.json",
)


def source_hashes():
    paths = set(SOURCE_PATHS) | {p.relative_to(ROOT).as_posix()
                               for p in (ROOT / "experiments").glob("random_expert_exhibition*.py")}
    return tuple((path, sha256((ROOT / path).read_bytes()).hexdigest()) for path in sorted(paths))


def capture_source():
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            check=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()

    status = git("status", "--porcelain=v1", "--untracked-files=normal")
    algorithm = {"V1": "frozen Stage-3 V1 / run_control_capture -> unchanged run_stage3",
                 "K-P0": "actual Program K K-P0 / run_k_p0(capture_effects=True)",
                 **{k: str(v) for k, v in asdict(STAGE3_V1_IDENTITY).items()}}
    return ExhibitionSource(git("rev-parse", "HEAD"), bool(status), status, sys.version,
                            source_hashes(), tuple(algorithm.items()),
                            tuple((k, str(v)) for k, v in asdict(MODEL_C_V1_IDENTITY).items()))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def project_native(native, variant, table):
    """Verify actual public effects and project, without inference or replay.

The full native object stays child-local. In particular K selection/proof
objects and archival observations never masquerade as presentation types.
"""
    if variant == "V1":
        _require(type(native) is ControlCaptureResult, "Expected actual CONTROL capture.")
        effects = native.effects
    elif variant == "K-P0":
        _require(type(native) is KRunResult, "Expected actual K-P0 result.")
        _require(all(t.public_effect_status == "CAPTURED" for t in native.traces),
                 "K-P0 must capture every actual public effect.")
        effects = tuple(t.public_effect for t in native.traces)
    else:
        raise ValueError("Unsupported native variant.")
    audit = validate_public_effect_stream(effects, complete=True)
    _require(audit.status == "PASS", f"Public effect stream invalid: {audit}")
    _require(len(native.traces) == len(effects) and native.status in (GameStatus.WON, GameStatus.LOST),
             "Incomplete native result.")
    rows = tuple(tuple(int(v) for v in row) for row in effects[0].before_observation)
    frames = [ExhibitionFrame(0, rows, "PLAYING", (0, 0), 0, frozenset(), frozenset(), frozenset())]
    actions, total, explicit = [], 0, frozenset()
    for i, (trace, effect) in enumerate(zip(native.traces, effects)):
        target = (trace.move.x, trace.move.y)
        _require((trace.move.action, *target) == (effect.move.action, effect.move.x, effect.move.y)
                 and trace.status_after is effect.status_after
                 and trace.cursor_before == effect.cursor_before
                 and trace.modeled_action_us == effect.modeled_action_us
                 == action_cost(table, trace.cursor_before, target), "Native/effect/Model C binding mismatch.")
        _require(effect.capture_method == "STATUS_GATED_ACTUAL_EXECUTION", "Actual effects required.")
        if variant == "K-P0":
            _require(trace.input_index == i and trace.M_before == frames[-1].logical_mines,
                     "K M_before differs from the preceding committed frame.")
            before_m, after_m = frozenset(trace.M_before), frozenset(trace.preinput_M)
        else:
            _require(trace.safe_cells_opened_delta == effect.safe_cells_opened_delta
                     and trace.explicit_flag_delta == effect.explicit_flag_delta, "V1 effect delta differs.")
            before_m = after_m = frozenset()
        action = trace.move.action.name
        if action == "FLAG":
            explicit = explicit | {target}
        rows = tuple(tuple(int(v) for v in row) for row in effect.after_observation.rows)
        flags = frozenset((x, y) for y, row in enumerate(rows)
                          for x, v in enumerate(row) if v == CellState.FLAGGED)
        automatic = flags - explicit if trace.status_after is GameStatus.WON else frozenset()
        total += trace.modeled_action_us
        actions.append(ExhibitionAction(i, action, target, tuple(trace.cursor_before), trace.modeled_action_us,
                                        trace.status_after.name, before_m, after_m, effect.safe_cells_opened_delta))
        frames.append(ExhibitionFrame(i + 1, rows, trace.status_after.name, target, total,
                                      after_m, explicit, automatic))
    _require(total == native.total_modeled_us and frames[-1].status == native.status.name,
             "Native total/terminal outcome differs (first and last inputs included).")
    if variant == "K-P0":
        _require(frames[-1].logical_mines == native.final_M, "Final M must come from the last legitimate trace.")
    return ExhibitionTrace(variant, tuple(actions), tuple(frames))


def _fresh_engine(width, height, mines, fingerprint):
    engine = MinesweeperEngine(width, height, len(mines))
    observation = engine.reset_with_mines(width, height, len(mines), mines)
    snapshot = engine.get_board_snapshot()  # installation verification only; never passed to policy
    _require(snapshot.mines_placed and snapshot.mines == mines
             and calculate_board_fingerprint(width, height, len(mines), snapshot.mines) == fingerprint,
             "Installed layout differs from the generated board.")
    _require(engine.status is GameStatus.PLAYING
             and all(v == CellState.HIDDEN for row in observation for v in row), "Engine is not fresh/all-HIDDEN.")
    return engine


def _verify_terminal(engine, trace, mines):
    _require(engine.status.name == trace.outcome
             and tuple(tuple(row) for row in engine.get_observation()) == trace.frames[-1].observation,
             "Projected terminal differs from actual engine.")
    disclosed = frozenset((x, y) for y, row in enumerate(trace.frames[-1].observation)
                          for x, v in enumerate(row) if v in (CellState.FLAGGED, CellState.MINE, CellState.EXPLODED))
    _require(disclosed == mines, "Terminal public disclosure differs from installed layout.")


def _run_layout(width, height, mines, fingerprint, table, progress):
    """Internal fixed-layout seam for tiny focused fixtures; no UI/import route."""
    left = _fresh_engine(width, height, mines, fingerprint)
    right = _fresh_engine(width, height, mines, fingerprint)
    _require(left is not right, "Fresh engines must be distinct.")
    progress("V1_RUNNING", None)
    native = run_control_capture(left, table=table)
    v1 = project_native(native, "V1", table)
    _verify_terminal(left, v1, mines)
    del native, left  # release the full V1 graph before actual K-P0 starts
    _require(right.status is GameStatus.PLAYING
             and all(v == CellState.HIDDEN for row in right.get_observation() for v in row),
             "K engine was changed by V1 execution.")
    progress("K_P0_RUNNING", v1.summary())
    native = run_k_p0(right, table=table, capture_effects=True)
    k = project_native(native, "K-P0", table)
    _verify_terminal(right, k, mines)
    del native, right
    progress("PROJECTED", k.summary())
    return v1, k


def run_expert_pair(index, *, progress=lambda phase, summary: None):
    validate_index(index)  # before ANY generation, profile read or runner call
    source = capture_source()
    board = generate_board(EXPERT_GENERAL_V1, index)  # exactly once; never outcome-filtered
    _require(board.game_index == board.seed == index, "Generated identity mismatch.")
    fingerprint = calculate_board_fingerprint(30, 16, 99, board.mine_positions)
    _require(fingerprint == board.board_fingerprint, "Generated fingerprint mismatch.")
    identity = ExhibitionBoard(index, board.seed, fingerprint)
    table = load_timing_table()  # authenticated bytes and table, identical for both runners
    v1, k = _run_layout(30, 16, board.mine_positions, fingerprint, table, progress)
    _require(source.files == source_hashes(), "Relevant source changed during execution; result not installed.")
    return ExhibitionPair(identity, v1, k, source)
