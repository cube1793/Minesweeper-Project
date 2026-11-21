"""F: additional fixed-layout algorithms — adapters, metrics, information boundary.

Metrics are recomputed here with an independent replay loop and the existing
Model C evaluator; nothing is read back from same_board_algorithms' own counts.
"""

from collections import Counter
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import pickle
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from benchmark_modeled_time import authenticate_model_c, evaluate_ordered_actions
from core_engine import Action, GameStatus, MinesweeperEngine
from replay_model import ReplayBoard
import same_board_algorithm_worker as worker
from same_board_algorithms import (
    ALGORITHMS, K_ALGORITHMS, LIMIT_SECONDS, STAGE4_ALGORITHMS, AlgorithmMove, AlgorithmRun,
    execute_algorithm, not_run, settings_for, support_reason, validate_run,
)
from same_board_runner import ComparisonExecutionError

ROOT = Path(__file__).resolve().parents[1]
MINES = ((8, 0), (7, 1), (8, 2), (1, 8), (2, 7), (5, 5), (6, 6), (8, 8), (3, 4), (4, 8))
WIN_BOARD = ReplayBoard(9, 9, 10, set(MINES))
LOSS_BOARD = ReplayBoard(9, 9, 10, {(0, 0), *MINES[1:]})  # Mined origin.
R_TARGET = "120"  # Test input only, not a recommended target.


def target(algorithm):
    return R_TARGET if algorithm == "S4_R" else None


def first(run):
    move = run.moves[0]
    return move.action, move.x, move.y


def independent_metrics(board, moves):
    engine = MinesweeperEngine(board.width, board.height, board.num_mines)
    engine.reset_with_mines(board.width, board.height, board.num_mines, board.mine_positions)
    statuses = []
    for move in moves:
        engine.step(move.x, move.y, Action[move.action])
        statuses.append(engine.status)
    total = evaluate_ordered_actions(
        ((i, Action[m.action], m.x, m.y, s) for i, (m, s) in enumerate(zip(moves, statuses))),
        total_actions=len(moves), terminal_status=engine.status,
        width=board.width, height=board.height, evaluation=authenticate_model_c(),
    )
    counts = Counter(m.action for m in moves)
    return engine.status, statuses, (len(moves), counts["OPEN"], counts["FLAG"], counts["CHORD"]), total


class AlgorithmRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {}
        for name, board in (("win", WIN_BOARD), ("loss", LOSS_BOARD)):
            for algorithm in ALGORITHMS:
                raw = execute_algorithm(algorithm, board, r_target=target(algorithm))
                cls.runs[name, algorithm] = (raw, validate_run(board, raw))

    def test_each_algorithm_wins_and_loses_on_small_fixed_boards(self):
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                self.assertEqual(self.runs["win", algorithm][1].outcome, "WON")
                self.assertEqual(self.runs["loss", algorithm][1].outcome, "LOST")
                self.assertTrue(self.runs["win", algorithm][1].playable)

    def test_metrics_are_independently_recomputed_by_engine_replay_and_model_c(self):
        for (name, algorithm), (raw, run) in self.runs.items():
            board = WIN_BOARD if name == "win" else LOSS_BOARD
            with self.subTest(board=name, algorithm=algorithm):
                self.assertIsNone(raw.actions)
                self.assertIsNone(raw.model_c_total_us)
                status, statuses, counts, total = independent_metrics(board, run.moves)
                self.assertEqual(status.name, run.outcome)
                self.assertEqual([s.name for s in statuses], [m.status_after for m in run.moves])
                actions = run.actions
                self.assertEqual((actions.semantic_action_count, actions.open_count,
                                  actions.flag_input_count, actions.chord_count), counts)
                self.assertEqual(run.model_c_total_us, total)

    def test_existing_pair_matches_the_existing_runner_on_the_same_board(self):
        from same_board_runner import run_fixed_layout_solvers
        existing = run_fixed_layout_solvers(WIN_BOARD)
        for key, metrics in (("S2", existing.stage2_metrics), ("S3", existing.stage3_metrics)):
            run = self.runs["win", key][1]
            self.assertEqual(run.actions, metrics.actions)
            self.assertEqual(run.model_c_total_us, metrics.model_c_total_us)
            self.assertEqual(run.outcome, metrics.outcome.name)

    def test_validation_rejects_tampered_runs(self):
        run = self.runs["win", "K_D23"][0]
        moved = list(run.moves)
        moved[1] = replace(moved[1], status_after="WON" if moved[1].status_after == "PLAYING" else "PLAYING")
        cases = {
            "status": replace(run, moves=tuple(moved)),
            "outcome": replace(run, outcome="LOST"),
            "truncated": replace(run, moves=run.moves[:-1]),
            "after_terminal": replace(run, moves=run.moves + (run.moves[-1],)),
            "stopped_terminal": replace(run, outcome="STOPPED"),
        }
        for name, tampered in cases.items():
            with self.subTest(name=name), self.assertRaises(ComparisonExecutionError):
                validate_run(WIN_BOARD, tampered)
        with self.assertRaises(ComparisonExecutionError):
            validate_run(WIN_BOARD, replace(not_run("K_P0", "LIMIT"), model_c_total_us=5))
        with self.assertRaises(ValueError):
            AlgorithmRun("K_P0", "LIMIT", run.moves)
        with self.assertRaises(ValueError):
            AlgorithmMove("UNFLAG", 0, 0, "PLAYING")

    def test_first_input_comes_from_policy_and_mined_first_input_loses(self):
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                win, loss = self.runs["win", algorithm][1], self.runs["loss", algorithm][1]
                # The public start is the same all-HIDDEN board, so the first input is the same.
                self.assertEqual(first(win), first(loss))
                self.assertEqual(len(loss.moves), 1)
                self.assertEqual(loss.moves[0].status_after, "LOST")
        for algorithm in ("S2", "S3"):
            self.assertEqual(first(self.runs["win", algorithm][1]), ("OPEN", 0, 0))

    def test_settings_are_recorded_per_algorithm(self):
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                run = self.runs["win", algorithm][1]
                settings = dict(run.settings)
                self.assertEqual(run.settings, settings_for(algorithm, target(algorithm)))
                if algorithm in K_ALGORITHMS:
                    self.assertEqual(settings["entry"], "FIXED_BOARD")
                    self.assertIn("FIXED_BOARD", settings["definition"])
                if algorithm in STAGE4_ALGORITHMS:
                    self.assertEqual((settings["entry"], settings["model attempts"]), ("FIXED_BOARD", "max 8"))
                    self.assertIn("allowed", settings["guesses"])
                    self.assertTrue(run.time_dependent)
                else:
                    self.assertFalse(run.time_dependent)
        self.assertEqual(dict(self.runs["win", "K_D23"][1].settings)["diagnosis"][:4], "NONE")
        self.assertEqual(dict(self.runs["win", "S4_R"][1].settings)["R target"], "120%")
        self.assertEqual(LIMIT_SECONDS, {"S2": 120.0, "S3": 120.0, "K_P0": 30.0, "K_LC0": 30.0, "K_LC1": 30.0,
                                         "K_D23": 30.0, "S4_S": 120.0, "S4_M": 120.0, "S4_R": 120.0})


class BoundaryAndShapeTests(unittest.TestCase):
    def test_decisions_receive_public_snapshots_only(self):
        """Layout reads are allowed only outside the decision calls."""
        import live_k_policy
        import stage4_live_worker
        state = {"inside": 0, "snapshots": []}
        original_snapshot = MinesweeperEngine.get_board_snapshot

        def guarded_snapshot(engine):
            if state["inside"]:
                raise AssertionError("mine layout read inside a decision call")
            return original_snapshot(engine)

        def wrap(name, cls):
            original = getattr(cls, name)

            def call(self, *args, **kwargs):
                state["snapshots"].extend(args[:1])
                state["inside"] += 1
                try:
                    return original(self, *args, **kwargs)
                finally:
                    state["inside"] -= 1
            return call

        with ExitStack() as stack:
            stack.enter_context(patch.object(MinesweeperEngine, "get_board_snapshot", guarded_snapshot))
            for name in ("propose", "validate", "acknowledge"):
                stack.enter_context(patch.object(live_k_policy.KOwner, name, wrap(name, live_k_policy.KOwner)))
                stack.enter_context(patch.object(stage4_live_worker.Session, name,
                                                 wrap(name, stage4_live_worker.Session)))
            for algorithm in K_ALGORITHMS + STAGE4_ALGORITHMS:
                with self.subTest(algorithm=algorithm):
                    state["snapshots"].clear()
                    run = execute_algorithm(algorithm, WIN_BOARD, r_target=target(algorithm))
                    self.assertEqual(run.outcome, "WON")
                    self.assertTrue(state["snapshots"])
                    for value in state["snapshots"]:
                        grid = getattr(value, "observation", None)
                        if grid is None and isinstance(value, dict):
                            grid = (value.get("state") or value.get("after") or {}).get("observation")
                        flat = [] if grid is None else [glyph for row in grid for glyph in row]
                        self.assertTrue(set(flat) <= {-3, -2, *range(9)})
                        for field in ("mines", "mine_positions", "board"):
                            self.assertFalse(hasattr(value, field), field)

    def test_support_reason_matches_live_presets(self):
        custom = ReplayBoard(8, 8, 10, {(x, 7) for x in range(8)} | {(0, 0), (1, 0)})
        for algorithm in ALGORITHMS:
            reason = support_reason(algorithm, custom)
            self.assertEqual(reason is None, algorithm in ("S2", "S3"))
            self.assertIsNone(support_reason(algorithm, WIN_BOARD))
        with self.assertRaises(ValueError):
            execute_algorithm("K_P0", custom)
        with self.assertRaises(ValueError):
            execute_algorithm("S4_R", WIN_BOARD, r_target="0")
        with self.assertRaises(ValueError):
            execute_algorithm("K_P0", WIN_BOARD, r_target="120")

    def test_new_worker_payload_and_result_shape(self):
        result = worker.calculate_algorithm_run(
            {"token": 3, "board": WIN_BOARD, "algorithm": "K_LC1", "r_target": None})
        self.assertEqual(set(result), {"token", "run", "error"})
        self.assertEqual((result["token"], result["error"], result["run"].outcome), (3, None, "WON"))
        for payload in (None, {"token": 3}, {"token": True, "board": WIN_BOARD, "algorithm": "K_P0", "r_target": None},
                        {"token": 3, "board": {}, "algorithm": "K_P0", "r_target": None},
                        {"token": 3, "board": WIN_BOARD, "algorithm": "V9", "r_target": None},
                        {"token": 3, "board": WIN_BOARD, "algorithm": "S4_R", "r_target": 120}):
            with self.subTest(payload=payload):
                bad = worker.calculate_algorithm_run(payload)
                self.assertIsNone(bad["run"])
                self.assertTrue(bad["error"].startswith("Transport failed"))
        failed = worker.calculate_algorithm_run(
            {"token": 4, "board": WIN_BOARD, "algorithm": "S4_R", "r_target": "-5"})
        self.assertTrue(failed["error"].startswith("Execution failed"))
        self.assertEqual(worker.WORKER_FLAG, "--same-board-algorithm-worker")

    def test_worker_cli_round_trip_in_a_real_process(self):
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            payload, result = Path(directory) / "payload.pkl", Path(directory) / "result.pkl"
            payload.write_bytes(pickle.dumps({"token": 1, "board": WIN_BOARD, "algorithm": "K_P0",
                                              "r_target": None}))
            completed = subprocess.run([sys.executable, "-B", worker.WORKER_SCRIPT, str(payload), str(result)],
                                       cwd=ROOT, capture_output=True, text=True, timeout=120)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            envelope = pickle.loads(result.read_bytes())
        self.assertEqual(validate_run(WIN_BOARD, envelope["run"]).outcome, "WON")

    def test_selection_logic_files_are_unchanged(self):
        """F adds adapters only; selection/policy files keep their E-commit content."""
        expected = {
            "live_k_policy.py": "67c4835f63aa6777b2482b72433895bd77f6e7c60b0a1f8acd5578b5f2231fef",
            "live_k_d23.py": "21cfcc6e6f9faa833dec0e8851d16ff4ea2407a8423af730ff45af86929be414",
            "stage4_runtime_policy.py": "16ec84cbd721f40fda2aa06036ab1dfdc4340bee3b0ad50363b64c1effce9397",
            "stage4_policy.py": "0bfdb3aa908492da50e000ad56828f64dfd74d1d3322759c98a97ebfc3a218a5",
            "stage3_planner.py": "dd73edfbb14cd6fdbdf2752a290c4417198a14723ea40761a81a32b113f64010",
        }
        for name, digest in expected.items():
            data = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
            crlf = data.replace(b"\n", b"\r\n")
            self.assertIn(digest, {hashlib.sha256(data).hexdigest(), hashlib.sha256(crlf).hexdigest()}, name)


if __name__ == "__main__":
    unittest.main()
