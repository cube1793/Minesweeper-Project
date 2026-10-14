"""The expert source retains identity and delegates execution to frozen V1."""

import unittest
from dataclasses import FrozenInstanceError, fields
from unittest.mock import patch

from benchmark_board import EXPERT_GENERAL_V1, calculate_board_fingerprint, generate_board
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from simple_algorithm import SimpleMove
from stage3_execution import Stage3Execution, run_expert_stage3_execution
from stage3_planner import plan_position
from stage3_runner import Stage3RunResult, run_stage3
from tests.test_benchmark_board import GOLDEN_FINGERPRINTS


class Stage3ExecutionTests(unittest.TestCase):
    def test_real_expert_preserves_generated_installed_and_result_identity(self):
        spec = EXPERT_GENERAL_V1
        generated, installed, returned = [], [], []

        def generate(source, index):
            board = generate_board(source, index)
            generated.append(board)
            return board

        def public_plan(observation, num_mines, cursor, table):
            # This signature rejects board/snapshot/fingerprint arguments.
            self.assertIsInstance(observation, list)
            self.assertTrue(all(isinstance(row, list) for row in observation))
            self.assertTrue(all(type(cell) is int for row in observation for cell in row))
            self.assertEqual((len(observation[0]), len(observation)), (30, 16))
            self.assertEqual(num_mines, 99)
            self.assertEqual(len(cursor), 2)
            return plan_position(observation, num_mines, cursor, table)

        def execute(engine):
            self.assertIsInstance(engine, MinesweeperEngine)
            self.assertEqual(engine.status, GameStatus.PLAYING)
            self.assertEqual(engine.get_observation(), [[CellState.HIDDEN] * 30 for _ in range(16)])
            snapshot = engine.get_board_snapshot()
            installed.append(snapshot)
            self.assertTrue(snapshot.mines_placed)
            self.assertEqual((snapshot.width, snapshot.height, snapshot.num_mines), (30, 16, 99))
            self.assertEqual(snapshot.mines, generated[0].mine_positions)
            result = run_stage3(engine)
            self.assertEqual(engine.get_board_snapshot().mines, snapshot.mines)
            self.assertEqual(result.status, engine.status)
            returned.append(result)
            return result

        with patch("stage3_execution.generate_board", side_effect=generate) as generator, \
             patch("stage3_execution.run_stage3", side_effect=execute) as runner, \
             patch("stage3_runner.plan_position", side_effect=public_plan) as planner:
            execution = run_expert_stage3_execution(0)

        generator.assert_called_once_with(spec, 0)
        runner.assert_called_once()
        self.assertIs(execution.spec, spec)
        self.assertIs(execution.board, generated[0])
        self.assertIs(execution.result, returned[0])
        self.assertEqual((execution.board.game_index, execution.board.seed), (0, 0))
        self.assertEqual(execution.board.board_fingerprint, GOLDEN_FINGERPRINTS[0])
        self.assertEqual(calculate_board_fingerprint(30, 16, 99, installed[0].mines), GOLDEN_FINGERPRINTS[0])
        self.assertNotIn((0, 0), execution.board.mine_positions)
        self.assertIn(execution.result.status, (GameStatus.WON, GameStatus.LOST))
        self.assertEqual(execution.result.traces[0].move, SimpleMove(Action.OPEN, 0, 0))
        self.assertIsNone(execution.result.traces[0].decision)
        self.assertEqual(planner.call_count, len(execution.result.traces) - 1)

    def test_context_is_frozen_and_has_only_the_three_retained_objects(self):
        board = generate_board(EXPERT_GENERAL_V1, 42)
        result = Stage3RunResult(GameStatus.PLAYING, ())
        execution = Stage3Execution(EXPERT_GENERAL_V1, board, result)
        self.assertEqual(tuple(field.name for field in fields(execution)), ("spec", "board", "result"))
        with patch("stage3_execution.generate_board", side_effect=AssertionError("regeneration")):
            self.assertIs(execution.spec, EXPERT_GENERAL_V1)
            self.assertIs(execution.board, board)
            self.assertIs(execution.result, result)
        for field in fields(execution):
            with self.subTest(field=field.name), self.assertRaises(FrozenInstanceError):
                setattr(execution, field.name, None)

    def test_invalid_indices_use_the_existing_generator_contract_before_engine_creation(self):
        for index in (-1, True, False, 1.0, "1", None):
            with self.subTest(index=index):
                with self.assertRaises(ValueError) as expected:
                    generate_board(EXPERT_GENERAL_V1, index)
                with patch("stage3_execution.MinesweeperEngine") as engine, \
                     patch("stage3_execution.run_stage3") as runner:
                    with self.assertRaises(ValueError) as actual:
                        run_expert_stage3_execution(index)
                self.assertEqual(str(actual.exception), str(expected.exception))
                engine.assert_not_called()
                runner.assert_not_called()

    def test_loss_is_returned_complete_without_filtering_or_retry(self):
        engine = MinesweeperEngine(2, 1, 1)
        engine.reset_with_mines(2, 1, 1, {(0, 0)})
        loss = run_stage3(engine)
        self.assertEqual(loss.status, GameStatus.LOST)
        with patch("stage3_execution.generate_board", wraps=generate_board) as generator, \
             patch("stage3_execution.run_stage3", return_value=loss) as runner:
            execution = run_expert_stage3_execution(42)
        generator.assert_called_once_with(EXPERT_GENERAL_V1, 42)
        runner.assert_called_once()
        self.assertIs(execution.result, loss)
        self.assertIs(execution.result.traces, loss.traces)
        self.assertEqual(execution.board.board_fingerprint, GOLDEN_FINGERPRINTS[42])

    def test_each_execution_uses_a_fresh_hidden_engine(self):
        result = Stage3RunResult(GameStatus.LOST, ())
        engines = []

        def execute(engine):
            engines.append(engine)
            self.assertEqual(engine.status, GameStatus.PLAYING)
            self.assertTrue(all(cell == CellState.HIDDEN for row in engine.get_observation() for cell in row))
            engine.step(0, 0, Action.OPEN)
            return result

        with patch("stage3_execution.run_stage3", side_effect=execute):
            first = run_expert_stage3_execution(42)
            second = run_expert_stage3_execution(42)
        self.assertIsNot(engines[0], engines[1])
        self.assertEqual(first.board, second.board)

    def test_large_game_index_is_not_narrowed(self):
        index = 1 << 40
        with patch("stage3_execution.run_stage3", return_value=Stage3RunResult(GameStatus.LOST, ())):
            execution = run_expert_stage3_execution(index)
        self.assertEqual((execution.board.game_index, execution.board.seed), (index, index))
        self.assertEqual(execution.board, generate_board(EXPERT_GENERAL_V1, index))

    def test_runner_failure_propagates_without_retry(self):
        with patch("stage3_execution.generate_board", wraps=generate_board) as generator, \
             patch("stage3_execution.run_stage3", side_effect=RuntimeError("runner failed")) as runner:
            with self.assertRaisesRegex(RuntimeError, "runner failed"):
                run_expert_stage3_execution(42)
        generator.assert_called_once_with(EXPERT_GENERAL_V1, 42)
        runner.assert_called_once()


if __name__ == "__main__":
    unittest.main()
