"""EXPERIMENTAL / RESEARCH policy evidence, never an official benchmark run.

Run from repository root: python -m experiments.stage3_e_l_policy_pilot --phase smoke100
Production code must not import this module. No telemetry/benchmark schema writes.
"""

import argparse
from collections import Counter
from contextlib import ExitStack
from fractions import Fraction
import hashlib
from pathlib import Path
import platform
import sys

from benchmark_board import EXPERT_GENERAL_V1, generate_board
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from simple_decision import DecisionKind
from simple_runner import run_simple
from experiments.stage3_policy_planner import (
    POLICIES, PROFILE_PATH, PROFILE_SHA256, ROOT, TABLE_SHA256, PilotInvalid,
    canonical_bytes, certainty_pool, cost, load_table, plan_position, reading,
    require, target,
)


VERSION = "EXPERIMENTAL_STAGE3_E_L_PILOT_V1"
START, STOP = 100000, 110000
PHASES = {"smoke100": 100, "invariants1000": 1000, "evidence10000": 10000}
OUTPUT_ROOT = ROOT / "results/stage3_e_l_policy_pilot"
QUALIFIED_STAGE2_COMMIT = "30b50575b7f8a807cb9f8573f8068f5294b75219"
# Qualified Stage-2 files verified unchanged at implementation time. Normalize
# checkout CRLF to LF only; never allow semantic drift under a reference label.
FROZEN_SOURCES = {
    "core_engine.py": "1a6ad25ef80ca30c3bb0ecbe80fd5ca7e09b60e1ae086e5c65de3703dea52e08",
    "benchmark_board.py": "a02d0626e2d9086b498335cefbfb8d58813b456637d2e8d5b9fccc211460543f",
    "simple_algorithm.py": "12aa2190945c504353ee8f0177557e7eaae03e7d16422e8c5b3ee4fff1c81001",
    "simple_probability.py": "de3b42c4cfc50de4cb8f6a1fbe90016f3ec590f4193d86f4677d7e8ed50ab9be",
    "simple_decision.py": "3d740ee0520cfabb8d4126dcb5d3554a1ec3adeb3d9194ace5150f87a7d37047",
    "simple_runner.py": "fd30beaa9328ec63e804c9bec267feb9641c3475b23cf9f5e3300b6d85b4d561",
}


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_hash(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def verify_sources():
    for name, expected in FROZEN_SOURCES.items():
        require(source_hash(ROOT / name) == expected, f"frozen Stage-2 source mismatch: {name}")


def rational(numerator, denominator=1):
    value = Fraction(numerator, denominator)
    return {"numerator": value.numerator, "denominator": value.denominator}


def move_json(move):
    return {"action": move.action.name, "x": move.x, "y": move.y}


def plan_json(plan):
    return {"actions": [move_json(m) for m in plan.actions], "L_us": plan.latency_us,
            "R": plan.reveals, "E_us": rational(plan.latency_us, plan.reveals),
            "setup_length": len(plan.actions) - 1}


def observation_json(observation):
    return [[int(value) for value in row] for row in observation]


def observation_hash(observation):
    return hashlib.sha256(canonical_bytes(observation)).hexdigest()


def guess_checkpoint(observation, evidence, guess_index):
    require(evidence.kind == DecisionKind.PROBABILITY_GUESS, "not a Stage-2 guess")
    probabilities = evidence.probability_result
    require(probabilities is not None, "guess missing exact probability")
    cells = probabilities.probabilities
    require(bool(cells) and all(0 < c.mine_worlds < c.total_worlds for c in cells),
            "guess despite certainty")
    # All denominators are equal by the frozen ProbabilityResult contract.
    safest = min(cells, key=lambda c: (c.mine_worlds, *reading(c.coordinate)))
    require(evidence.move.action == Action.OPEN and target(evidence.move) == safest.coordinate,
            "guess violates exact Stage-2 minimum risk / (y,x) tie")
    public = observation_json(observation)
    return {"kind": "guess", "guess_index": guess_index, "observation": public,
            "observation_sha256": observation_hash(public),
            "minimum_mine_probability": rational(safest.mine_worlds, safest.total_worlds),
            "selected_coordinate": list(safest.coordinate)}


def engine_for(board):
    """Evaluator-only layout handling; planner never receives board/engine."""
    spec = EXPERT_GENERAL_V1
    engine = MinesweeperEngine(spec.width, spec.height, spec.num_mines)
    engine.reset_with_mines(spec.width, spec.height, spec.num_mines, board.mine_positions)
    return engine


def validate_first_action(observation, decision):
    move = decision.move
    safe, mines = certainty_pool(decision.evidence)
    if decision.reason == "guess":
        return  # Exact guess validator runs at the checkpoint before execution.
    if move.action == Action.FLAG:
        require(target(move) in mines and observation[move.y][move.x] == CellState.HIDDEN,
                "FLAG lacks current execution evidence")
    elif move.action == Action.OPEN:
        require(target(move) in safe and observation[move.y][move.x] == CellState.HIDDEN,
                "OPEN uses virtual-only evidence")
    else:
        clue = next(c for c in decision.evidence.constraints if c.source == target(move))
        require(observation[move.y][move.x] > 0 and clue.remaining_mines == 0 and
                bool(clue.hidden_cells) and clue.hidden_cells <= safe,
                "CHORD lacks current execution evidence")


def policy_game(engine, policy, table, emit):
    """Suspend before every guess, so pairing can reject it BEFORE physical input.

    Each resume commits one previously validated guess, then independently replans
    after every physical action until the next checkpoint. No plan is queued.
    """
    from simple_algorithm import SimpleMove

    cursor = (0, 0)
    observation = engine.get_observation()
    total = guesses = action_index = 0
    counts = Counter()
    while engine.status == GameStatus.PLAYING:
        detail = None
        if action_index == 0:
            move = SimpleMove(Action.OPEN, 0, 0)
            reason = "canonical_first_open"
        else:
            detail = plan_position(observation, engine.num_mines, cursor, table, policy)
            move, reason = detail.move, detail.reason
            validate_first_action(observation, detail)
            if reason == "guess":
                yield guess_checkpoint(observation, detail.evidence, guesses)
                guesses += 1
        record = {"action_index": action_index, "move": move_json(move), "reason": reason,
                  "cursor_before": list(cursor), "observation_sha256": observation_hash(observation),
                  "cost_us": cost(table, cursor, target(move))}
        if detail is not None:
            record.update({"inference_kind": detail.evidence.kind.value,
                           "candidate_count": len(detail.candidates),
                           "survivor_count": len(detail.survivors),
                           "dominated_count": len(detail.candidates) - len(detail.survivors),
                           "selection": detail.selection_diagnostics})
            if detail.choices:
                record["plans"] = {name: plan_json(p) for name, p in detail.choices.items()}
                e, l = (detail.choices[name] for name in POLICIES)
                record["policy_plan_divergence"] = e.actions != l.actions
                record["policy_first_action_divergence"] = e.actions[0] != l.actions[0]
                record["e_longer_latency_delta_us"] = max(0, e.latency_us - l.latency_us)
                record["e_to_l_latency_ratio"] = rational(e.latency_us, l.latency_us)
        hidden_before = sum(v == CellState.HIDDEN for row in observation for v in row)
        engine.step(move.x, move.y, move.action)
        # Explicitly obtain fresh public observation, including after every FLAG.
        observation = engine.get_observation()
        cursor = target(move)
        total += record["cost_us"]
        counts[move.action.name] += 1
        action_index += 1
        record.update({"status_after": engine.status.name, "cumulative_time_us": total})
        emit(record)
        require(engine.status != GameStatus.LOST or reason == "guess", "certainty action LOST")
        hidden_after = sum(v == CellState.HIDDEN for row in observation for v in row)
        require(engine.status != GameStatus.PLAYING or hidden_after < hidden_before,
                "physical action made no public progress")
    yield {"kind": "terminal", "final_result": engine.status.name, "guess_count": guesses,
           "total_time_us": total, "action_counts": dict(counts), "action_count": action_index}


def stage2_reference(board):
    """Execute the actual frozen run_simple, with observational instrumentation only."""
    engine = engine_for(board)
    before = engine.get_observation()
    checkpoints = []

    def observe(trace):
        nonlocal before
        if trace.decision is not None and trace.decision.kind == DecisionKind.PROBABILITY_GUESS:
            checkpoints.append(guess_checkpoint(before, trace.decision, len(checkpoints)))
        before = engine.get_observation()

    result = run_simple(engine, accept_guesses=True, initial_open=(0, 0), observer=observe)
    checkpoints.append({"kind": "terminal", "final_result": result.status.name,
                        "guess_count": len(checkpoints)})
    return checkpoints


def gate_value(checkpoint):
    if checkpoint["kind"] == "terminal":
        return {key: checkpoint[key] for key in ("kind", "final_result", "guess_count")}
    return checkpoint


def check_equal(left, right, label):
    if gate_value(left) != gate_value(right):
        error = PilotInvalid(f"hard gate mismatch: {label}")
        error.evidence = {"comparison": label, "left": left, "right": right}
        raise error


def compare_game(board, table, emit_action, emit_checkpoint, reference=None):
    streams = {name: policy_game(engine_for(board), name, table,
                                lambda record, name=name: emit_action(name, record))
               for name in POLICIES}
    checkpoint_index = 0
    try:
        while True:
            checkpoints = {name: next(streams[name]) for name in POLICIES}
            for name, checkpoint in checkpoints.items():
                emit_checkpoint(name, checkpoint)
            e, l = (checkpoints[name] for name in POLICIES)
            check_equal(e, l, "E-FIRST vs L-FIRST")
            if reference is not None:
                require(checkpoint_index < len(reference), "Stage-2 reference ended early")
                check_equal(e, reference[checkpoint_index], "E-FIRST vs frozen Stage-2")
                check_equal(l, reference[checkpoint_index], "L-FIRST vs frozen Stage-2")
            checkpoint_index += 1
            if e["kind"] == "terminal":
                require(reference is None or checkpoint_index == len(reference),
                        "Stage-2 reference has additional checkpoints")
                return {"game_index": board.game_index, "seed": board.seed,
                        "board_fingerprint": board.board_fingerprint, "policies": checkpoints,
                        "delta_E_minus_L_us": e["total_time_us"] - l["total_time_us"],
                        "guess_checkpoints_compared": checkpoint_index - 1,
                        "stage2_cross_checked": reference is not None, "gate": "PASS"}
    finally:
        for stream in streams.values():
            stream.close()


def distribution(histogram):
    count = sum(histogram.values())
    if not count:
        return {"count": 0, "P50": None, "P95": None, "P99": None, "max": None,
                "histogram": []}
    ordered = sorted(histogram.items())

    def percentile(percent):
        rank = (count * percent + 99) // 100  # nearest rank, integer only
        cumulative = 0
        for value, frequency in ordered:
            cumulative += frequency
            if cumulative >= rank:
                return value

    return {"count": count, "P50": percentile(50), "P95": percentile(95),
            "P99": percentile(99), "max": ordered[-1][0],
            "histogram": [[value, frequency] for value, frequency in ordered]}


class Diagnostics:
    def __init__(self):
        self.counts = Counter()
        self.actions = Counter()
        self.latency = Counter()
        self.reveals = Counter()
        self.setup = Counter()
        self.longer_delta = Counter()
        self.longer_ratio = Counter()
        self.actual_time = 0

    def add(self, policy, record):
        self.actions[record["move"]["action"]] += 1
        self.actual_time += record["cost_us"]
        for key in ("candidate_count", "survivor_count", "dominated_count"):
            self.counts[key] += record.get(key, 0)
        self.counts[record["reason"]] += 1
        if "plans" not in record:
            if record.get("selection", {}).get("flag_fallback_ties", 0) > 1:
                self.counts["flag_fallback_tie_count"] += 1
            return
        plan = record["plans"][policy]
        self.latency[plan["L_us"]] += 1
        self.reveals[plan["R"]] += 1
        self.setup[plan["setup_length"]] += 1
        selection = record["selection"][policy]
        self.counts["exact_e_tie_count"] += selection["exact_e_tie"]
        self.counts["final_deterministic_fallback_count"] += selection["final_fallback"]
        self.counts["policy_decision_divergence_count"] += record["policy_plan_divergence"]
        self.counts["policy_first_action_divergence_count"] += record["policy_first_action_divergence"]
        if record["e_longer_latency_delta_us"]:
            self.longer_delta[record["e_longer_latency_delta_us"]] += 1
            ratio = record["e_to_l_latency_ratio"]
            self.longer_ratio[Fraction(ratio["numerator"], ratio["denominator"])] += 1

    def export(self):
        ratios = distribution(self.longer_ratio)
        for name in ("P50", "P95", "P99", "max"):
            if ratios[name] is not None:
                ratios[name] = rational(ratios[name])
        ratios["histogram"] = [[rational(r), n] for r, n in ratios["histogram"]]
        return {"counts": dict(self.counts), "action_counts": dict(self.actions),
                "actual_action_stream_time_us": self.actual_time,
                "chosen_plan_L_us": distribution(self.latency),
                "R_distribution": distribution(self.reveals),
                "setup_length_distribution": distribution(self.setup),
                "e_longer_latency_delta_us": distribution(self.longer_delta),
                "e_longer_latency_ratio": ratios}


def manifest(phase):
    names = list(FROZEN_SOURCES) + [
        "board_analyzer.py", "board_snapshot.py", "replay_model.py", "replay_recorder.py",
        "experiments/__init__.py", "experiments/stage3_policy_planner.py",
        "experiments/stage3_e_l_policy_pilot.py", "experiments/STAGE3_E_L_POLICY_PILOT.md",
        "tests/test_stage3_e_l_policy_pilot.py", "STAGE3_ALGORITHM_SPEC_DRAFT_v1.1.md",
        "STAGE3_HANDOFF.md", "STAGE3_EXTENSION_BACKLOG.md",
    ]
    return {"version": VERSION, "phase": phase, "official_benchmark": False,
            "corpus_role": "DEVELOPMENT_ONLY", "generator": "EXPERT_GENERAL_V1",
            "dimensions": [30, 16], "mines": 99, "first_click": [0, 0], "initial_cursor": [0, 0],
            "range": [START, START + PHASES[phase]], "seed_scheme": "game_index",
            "whole_development_corpus": [START, STOP], "e_tolerance": 0,
            "profile_sha256": PROFILE_SHA256, "table_sha256": TABLE_SHA256,
            "stage2_qualified_commit": QUALIFIED_STAGE2_COMMIT,
            "stage2_cross_check_games": min(1000, PHASES[phase]) if PHASES[phase] >= 1000 else 0,
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(), "source_hash_encoding": "UTF-8 bytes; CRLF to LF",
            "source_sha256": {name: source_hash(ROOT / name) for name in names}}


def run_pilot(phase, output, profile_path=PROFILE_PATH):
    require(phase in PHASES, "unknown pilot phase")
    output = Path(output).resolve()
    require(output.is_relative_to(OUTPUT_ROOT.resolve()) and output != OUTPUT_ROOT.resolve(),
            "output must be a new child of results/stage3_e_l_policy_pilot")
    output.mkdir(parents=True, exist_ok=False)  # Never overwrite or resume mixed evidence.
    completed = checkpoints = cross_checked = 0
    paired = Counter({"E_win": 0, "L_win": 0, "tie": 0})
    results = Counter()
    totals = {name: 0 for name in POLICIES}
    diagnostics = {name: Diagnostics() for name in POLICIES}
    summary = {"version": VERSION, "status": "INVALID", "primary_policy_result": None}
    try:
        # All startup gates precede board generation or planner decisions.
        table = load_table(profile_path)
        verify_sources()
        require(platform.python_implementation() == "CPython" and
                platform.python_version() == "3.12.14", "requires frozen generator runtime CPython 3.12.14")
        (output / "manifest.json").write_bytes(canonical_bytes(manifest(phase)))
        with ExitStack() as stack:
            streams = {name: stack.enter_context((output / (name + ".jsonl")).open("wb"))
                       for name in ("actions", "checkpoints", "games", "stage2_reference")}
            for game_index in range(START, START + PHASES[phase]):
                board = generate_board(EXPERT_GENERAL_V1, game_index)

                def emit_action(policy, record):
                    diagnostics[policy].add(policy, record)
                    streams["actions"].write(canonical_bytes(
                        {"game_index": game_index, "policy": policy, **record}))

                def emit_checkpoint(policy, record):
                    streams["checkpoints"].write(canonical_bytes(
                        {"game_index": game_index, "policy": policy, **record}))

                reference = None
                if PHASES[phase] >= 1000 and game_index < START + 1000:
                    reference = stage2_reference(board)
                    for checkpoint in reference:
                        streams["stage2_reference"].write(canonical_bytes(
                            {"game_index": game_index, **checkpoint}))
                pair = compare_game(board, table, emit_action, emit_checkpoint, reference)
                streams["games"].write(canonical_bytes(pair))
                for policy in POLICIES:
                    totals[policy] += pair["policies"][policy]["total_time_us"]
                delta = pair["delta_E_minus_L_us"]
                paired["E_win" if delta < 0 else "L_win" if delta > 0 else "tie"] += 1
                results[pair["policies"]["E-FIRST"]["final_result"]] += 1
                completed += 1
                checkpoints += pair["guess_checkpoints_compared"]
                cross_checked += pair["stage2_cross_checked"]
                if completed % 10 == 0:
                    print(f"{phase}: {completed}/{PHASES[phase]} games; hard gate PASS", flush=True)
        require(all(totals[p] == diagnostics[p].actual_time for p in POLICIES),
                "whole-game time does not reconcile with actual action stream")
        summary.update({"status": "VALID", "paired_game_time_wins": dict(paired),
                        "game_results": dict(results), "total_modeled_time_us": totals,
                        "delta_E_minus_L_us": totals["E-FIRST"] - totals["L-FIRST"],
                        "diagnostics": {p: diagnostics[p].export() for p in POLICIES}})
        if PHASES[phase] == 10000:
            summary["primary_policy_result"] = {
                "objective": "SUM actual whole-game table cost over all 10000 games",
                "winner": "E-FIRST" if totals["E-FIRST"] < totals["L-FIRST"] else
                          "L-FIRST" if totals["L-FIRST"] < totals["E-FIRST"] else "TIE",
                "sums_us": totals}
        else:
            summary["policy_gate"] = "OPEN: smoke/invariants are not full-corpus policy evidence"
    except Exception as error:
        summary.update({"status": "INVALID", "primary_policy_result": None,
                        "error_type": type(error).__name__, "error": str(error)})
        if hasattr(error, "evidence"):
            (output / "failure.json").write_bytes(canonical_bytes(error.evidence))
    summary.update({"phase": phase, "requested_games": PHASES[phase], "completed_games": completed,
                    "guess_invariants": {"status": "PASS" if summary["status"] == "VALID" else "INVALID",
                                         "paired_guess_checkpoints": checkpoints,
                                         "stage2_cross_checked_games": cross_checked},
                    "artifact_sha256": {p.name: file_hash(p) for p in sorted(output.iterdir())
                                        if p.is_file() and p.name != "summary.json"}})
    (output / "summary.json").write_bytes(canonical_bytes(summary))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=PHASES, default="smoke100")
    parser.add_argument("--output", type=Path, help="new directory under results/stage3_e_l_policy_pilot")
    args = parser.parse_args(argv)
    try:
        result = run_pilot(args.phase, args.output or OUTPUT_ROOT / args.phase)
    except (PilotInvalid, FileExistsError) as error:
        parser.exit(2, str(error) + "\n")
    print(canonical_bytes({key: result[key] for key in
                           ("status", "completed_games", "primary_policy_result")}).decode(), end="")
    return 0 if result["status"] == "VALID" else 2


if __name__ == "__main__":
    sys.exit(main())
