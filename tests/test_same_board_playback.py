"""Independent runner/Engine observations and isolation checks for Slice 3."""

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from mouse_trace import MouseTraceData, MouseTracePoint, MouseTraceSegment
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from replay_player import ReplayPlayer
from same_board_comparison import HumanComparisonContext
from same_board_playback import ComparisonRun, SameBoardPlayback, SameBoardStage3Player
from same_board_runner import run_same_board_comparison
from simple_algorithm import SimpleMove
from simple_runner import run_simple
from stage3_runner import Stage3RunResult, run_stage3
from tests.test_same_board_runner import human_context


RUNS = tuple(ComparisonRun)


def captured_comparison():
    """One small genuine comparison; capture observations during original runs."""
    board = ReplayBoard(6, 4, 5, {(1, 2), (2, 1), (4, 0), (4, 1), (4, 2)})
    human = MinesweeperEngine(board.width, board.height, board.num_mines)
    human.reset_with_mines(board.width, board.height, board.num_mines, board.mine_positions)
    prefixes = {ComparisonRun.HUMAN: [(human.get_observation(), human.status)]}
    events = []

    def record(action, x, y):
        human.step(x, y, action)
        events.append(ReplayEvent(0.5 + len(events) * 0.75, x, y, action.name))
        prefixes[ComparisonRun.HUMAN].append((human.get_observation(), human.status))

    for action, x, y in ((Action.CHORD, 0, 0), (Action.FLAG, 4, 0), (Action.FLAG, 4, 0),
                         (Action.OPEN, 0, 0), (Action.OPEN, 0, 0)):
        record(action, x, y)
    for y in range(board.height):
        for x in range(board.width):
            if (human.status == GameStatus.PLAYING and (x, y) not in board.mine_positions
                    and human.get_observation()[y][x] == CellState.HIDDEN):
                record(Action.OPEN, x, y)
    trace = MouseTraceData(6, 4, (MouseTraceSegment(20, (
        MouseTracePoint(0, 10.25, 10.5, 0),
        MouseTracePoint(987654, 110.25, 70.5, len(events) - 1),
    )),))
    replay = ReplayData(board, tuple(events), schema_version=2, mouse_trace=trace)
    context = HumanComparisonContext(replay, declared_full_game_human=True)

    def stage2(engine, *, observer, **kwargs):
        prefixes[ComparisonRun.STAGE2] = [(engine.get_observation(), engine.status)]

        def observe(action_trace):
            prefixes[ComparisonRun.STAGE2].append((engine.get_observation(), engine.status))
            observer(action_trace)

        return run_simple(engine, observer=observe, **kwargs)

    def stage3(engine, **kwargs):
        prefixes[ComparisonRun.STAGE3] = [(engine.get_observation(), engine.status)]
        return run_stage3(engine, observer=lambda _: prefixes[ComparisonRun.STAGE3].append(
            (engine.get_observation(), engine.status)), **kwargs)

    with patch("same_board_runner.run_simple", side_effect=stage2), \
         patch("same_board_runner.run_stage3", side_effect=stage3):
        execution = run_same_board_comparison(context)
    return execution, prefixes


class ComparisonPlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.execution, cls.prefixes = captured_comparison()
        cls.loss = run_same_board_comparison(human_context(mined_origin=True, with_trace=True))

    def setUp(self):
        self.playback = SameBoardPlayback(self.execution)

    def indices(self):
        return tuple(self.playback.index_for(run) for run in RUNS)

    def test_default_human_and_all_three_exact_hidden_initial_states(self):
        player = self.playback
        self.assertIs(player.selected_run, ComparisonRun.HUMAN)
        self.assertIs(player.execution, self.execution)
        self.assertIs(type(player._human), ReplayPlayer)
        self.assertIs(type(player._stage2), ReplayPlayer)
        self.assertIs(type(player._stage3), SameBoardStage3Player)
        engines = (player._human.engine, player._stage2.engine, player._stage3._engine)
        self.assertEqual(len({id(engine) for engine in engines}), 3)
        for run, engine in zip(RUNS, engines):
            player.select(run)
            self.assertEqual(player.current_index, 0)
            self.assertEqual(player.status, GameStatus.PLAYING)
            self.assertEqual(player.get_observation(), [[CellState.HIDDEN] * 6 for _ in range(4)])
            snapshot = engine.get_board_snapshot()
            self.assertTrue(snapshot.mines_placed)
            self.assertEqual((snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines),
                             (6, 4, 5, self.execution.context.layout.board.mine_positions))

    def test_every_prefix_and_arbitrary_seek_order_matches_original_observations(self):
        for run in RUNS:
            self.playback.select(run)
            count = self.playback.action_count()
            order = [count, 0, 1, count // 2, count - 1, 2, count, 0]
            order += list(range(count + 1)) + list(range(count, -1, -1))
            for index in order:
                with self.subTest(run=run, index=index):
                    observed = self.playback.go_to(index)
                    self.assertEqual((observed, self.playback.status), self.prefixes[run][index])
                    self.assertEqual(self.playback.current_index, index)

    def test_incremental_next_previous_and_end_boundaries_for_each_run(self):
        for run in RUNS:
            self.playback.select(run)
            self.assertFalse(self.playback.previous())
            count = self.playback.action_count()
            for index in range(1, count + 1):
                self.assertTrue(self.playback.next())
                self.assertEqual((self.playback.get_observation(), self.playback.status), self.prefixes[run][index])
            self.assertFalse(self.playback.next())
            for index in range(count - 1, -1, -1):
                self.assertTrue(self.playback.previous())
                self.assertEqual(self.playback.current_index, index)
                self.assertEqual((self.playback.get_observation(), self.playback.status), self.prefixes[run][index])
            self.assertFalse(self.playback.previous())

    def test_each_run_remembers_its_index_without_common_mapping(self):
        for run, index in zip(RUNS, (3, 5, 2)):
            self.playback.select(run)
            self.assertEqual(self.playback.current_index, 0)
            self.playback.go_to(index)
        for run, index in zip(RUNS, (3, 5, 2)):
            self.playback.select(run)
            self.assertEqual(self.playback.current_index, index)
            self.assertEqual(self.playback.get_observation(), self.prefixes[run][index][0])
            self.assertEqual(self.indices(), (3, 5, 2))

    def test_selected_navigation_does_not_touch_unselected_players(self):
        for run in RUNS:
            self.playback.select(run)
            others = [self.playback._player(other) for other in RUNS if other is not run]
            with ExitStack() as stack:
                for other in others:
                    for method in ("go_to", "next", "previous"):
                        stack.enter_context(patch.object(other, method, side_effect=AssertionError("unselected navigation")))
                before = self.indices()
                self.playback.go_to(3)
                self.assertTrue(self.playback.next())
                self.assertTrue(self.playback.previous())
                for other, old_index in zip(RUNS, before):
                    if other is not run:
                        self.assertEqual(self.playback.index_for(other), old_index)

    def test_selection_and_read_queries_do_not_reconstruct_any_run(self):
        self.playback.go_to(3)
        before = self.indices()
        with patch.object(MinesweeperEngine, "step", side_effect=AssertionError("step")), \
             patch.object(MinesweeperEngine, "reset_with_mines", side_effect=AssertionError("reset")):
            for run in (*RUNS, *reversed(RUNS)):
                self.playback.select(run)
                self.playback.index_for(run)
                self.playback.action_count(run)
                self.playback.final_outcome(run)
                self.playback.get_observation()
                self.assertEqual(self.indices(), before)

    def test_unequal_ranges_reject_instead_of_clamping_or_mapping(self):
        self.assertEqual(tuple(self.playback.action_count(run) for run in RUNS), (20, 21, 15))
        for run in RUNS:
            self.playback.select(run)
            count = self.playback.action_count()
            self.playback.go_to(count)
            with self.assertRaises(ValueError):
                self.playback.go_to(count + 1)
            self.assertEqual(self.playback.current_index, count)
        self.playback.select(ComparisonRun.STAGE2)
        self.playback.go_to(21)
        for run in (ComparisonRun.HUMAN, ComparisonRun.STAGE3):
            self.playback.select(run)
            before = self.indices()
            with self.assertRaises(ValueError):
                self.playback.go_to(21)
            self.assertEqual(self.indices(), before)

    def test_equal_indices_are_not_equal_progress(self):
        observations = []
        for run in RUNS:
            self.playback.select(run)
            observations.append(self.playback.go_to(1))
        self.assertNotEqual(observations[0], observations[1])  # Human's CHORD was wasted.
        self.assertEqual(self.indices(), (1, 1, 1))

    def test_invalid_indices_reject_bool_noninteger_and_bounds_for_all_runs(self):
        for run in RUNS:
            self.playback.select(run)
            self.playback.go_to(2)
            for invalid in (True, False, -1, self.playback.action_count() + 1, 0.0, 1.5, "1", None, [], {}):
                with self.subTest(run=run, invalid=invalid):
                    before = self.indices(), self.playback.get_observation()
                    with self.assertRaises(ValueError):
                        self.playback.go_to(invalid)
                    self.assertEqual((self.indices(), self.playback.get_observation()), before)

    def test_invalid_run_rejects_without_changing_selection_or_indices(self):
        for invalid in ("human", "stage2", 0, True, None, object()):
            before = self.playback.selected_run, self.indices()
            for query in (self.playback.select, self.playback.index_for):
                with self.assertRaises(ValueError):
                    query(invalid)
            if invalid is not None:  # None explicitly means selected for these queries.
                for query in (self.playback.action_count, self.playback.final_outcome):
                    with self.assertRaises(ValueError):
                        query(invalid)
            self.assertEqual((self.playback.selected_run, self.indices()), before)

    def test_current_status_and_final_outcome_are_separate(self):
        for run in RUNS:
            self.playback.select(run)
            for index in (0, 1, self.playback.action_count() // 2):
                self.playback.go_to(index)
                self.assertEqual(self.playback.status, GameStatus.PLAYING)
                self.assertEqual(self.playback.final_outcome(), GameStatus.WON)
            self.playback.go_to(self.playback.action_count())
            self.assertEqual(self.playback.status, self.playback.final_outcome(run))

    def test_mined_origin_solver_losses_and_independent_human_win(self):
        player = SameBoardPlayback(self.loss)
        player.go_to(player.action_count())
        self.assertEqual(player.status, GameStatus.WON)
        for run in (ComparisonRun.STAGE2, ComparisonRun.STAGE3):
            player.select(run)
            self.assertEqual((player.current_index, player.status), (0, GameStatus.PLAYING))
            self.assertEqual(player.final_outcome(), GameStatus.LOST)
            self.assertEqual(player.action_count(), 1)
            self.assertTrue(player.next())
            self.assertEqual(player.status, GameStatus.LOST)
            self.assertEqual(player.get_observation()[0][0], CellState.EXPLODED)
            self.assertFalse(player.next())
            self.assertTrue(player.previous())
            self.assertEqual(player.status, GameStatus.PLAYING)
            self.assertEqual(player.final_outcome(), GameStatus.LOST)
        player.select(ComparisonRun.HUMAN)
        self.assertEqual((player.current_index, player.status, player.final_outcome()), (3, GameStatus.WON, GameStatus.WON))

    def test_human_loss_retains_its_own_recorded_outcome(self):
        board = self.execution.context.layout.board
        context = HumanComparisonContext(ReplayData(board, (ReplayEvent(12, 4, 0, "OPEN"),)),
                                         declared_full_game_human=True)
        execution = run_same_board_comparison(context)
        player = SameBoardPlayback(execution)
        self.assertEqual(player.status, GameStatus.PLAYING)
        self.assertEqual(player.final_outcome(), GameStatus.LOST)
        player.next()
        self.assertEqual(player.status, GameStatus.LOST)
        self.assertEqual(player.final_outcome(ComparisonRun.STAGE3), GameStatus.WON)

    def test_original_replay_authorities_prelude_wasted_inputs_and_timestamps(self):
        player = self.playback
        self.assertIs(player._human.replay_data, self.execution.context.human_replay)
        self.assertIs(player._stage2.replay_data, self.execution.stage2_result.replay_data)
        for index in (1, 2, 3, 4, 5):
            player.go_to(index)
            event = self.execution.context.human_replay.events[index - 1]
            self.assertIs(player._human.current_event, event)
            self.assertEqual(player._human.current_time, event.elapsed_time)
        self.assertEqual(self.prefixes[ComparisonRun.HUMAN][0], self.prefixes[ComparisonRun.HUMAN][1])
        self.assertEqual(self.prefixes[ComparisonRun.HUMAN][4], self.prefixes[ComparisonRun.HUMAN][5])
        self.assertIs(player._stage3.board, self.execution.context.layout.board)
        self.assertIs(player._stage3.result, self.execution.stage3_result)

    def test_navigation_preserves_source_deep_equality_and_every_authority_identity(self):
        before = deepcopy(self.execution)
        retained = (
            self.execution.context, self.execution.context.human_replay,
            self.execution.context.human_replay.mouse_trace,
            self.execution.stage2_result, self.execution.stage2_result.replay_data,
            self.execution.stage2_traces, self.execution.stage3_result,
            self.execution.stage3_result.traces, self.execution.human_metrics,
            self.execution.stage2_metrics, self.execution.stage3_metrics,
        )
        for run in RUNS:
            self.playback.select(run)
            for index in (self.playback.action_count(), 0, 2, 1, 0):
                self.playback.go_to(index)
                self.playback.next()
                self.playback.previous()
        self.assertEqual(self.execution, before)
        current = self.playback.execution
        after = (current.context, current.context.human_replay, current.context.human_replay.mouse_trace,
                 current.stage2_result, current.stage2_result.replay_data, current.stage2_traces,
                 current.stage3_result, current.stage3_result.traces, current.human_metrics,
                 current.stage2_metrics, current.stage3_metrics)
        for original, final in zip(retained, after):
            self.assertIs(final, original)

    def test_returned_observations_and_separate_coordinators_are_isolated(self):
        second = SameBoardPlayback(self.execution)
        for run in RUNS:
            self.playback.select(run)
            observation = self.playback.go_to(2)
            observation[0][0] = 999
            self.assertEqual(self.playback.get_observation(), self.prefixes[run][2][0])
            second.select(run)
            self.assertEqual(second.current_index, 0)

    def test_no_solver_worker_model_evaluation_or_board_generation_during_playback(self):
        forbidden = (
            "same_board_runner.run_same_board_comparison", "same_board_runner.run_fixed_layout_solvers",
            "same_board_runner.compose_same_board_execution", "same_board_runner.run_simple",
            "same_board_runner.run_stage3", "simple_runner.run_simple", "stage3_runner.run_stage3",
            "simple_runner.analyze_position", "simple_decision.analyze_position",
            "stage3_runner.plan_position", "stage3_planner.plan_position",
            "same_board_execution_worker.calculate_same_board_execution",
            "same_board_runner.authenticate_model_c", "same_board_runner.evaluate_ordered_actions",
            "benchmark_modeled_time.authenticate_model_c", "benchmark_modeled_time.evaluate_ordered_actions",
            "stage3_physical.action_cost", "stage3_physical.load_timing_table",
            "benchmark_board.generate_board", "core_engine.random.sample",
        )
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch(name, side_effect=AssertionError(name))) for name in forbidden]
            player = SameBoardPlayback(self.execution)
            for run in RUNS:
                player.select(run)
                player.go_to(player.action_count())
                player.go_to(0)
                player.next()
                player.previous()
            for mocked in mocks:
                mocked.assert_not_called()

    def test_decision_graph_is_not_read_during_construction_or_navigation(self):
        from simple_decision import SimpleDecision
        from stage3_planner import RevealPlan, Stage3Decision

        def forbidden(instance, name):
            raise AssertionError(f"Playback read decision evidence: {type(instance).__name__}.{name}")

        with ExitStack() as stack:
            for model in (SimpleDecision, Stage3Decision, RevealPlan):
                stack.enter_context(patch.object(model, "__getattribute__", forbidden))
            player = SameBoardPlayback(self.execution)
            for run in RUNS:
                player.select(run)
                player.go_to(player.action_count())
                player.previous()
                player.next()

    def test_only_completed_bundle_and_exact_matching_layouts_are_accepted(self):
        different = ReplayBoard(6, 4, 5, {(1, 2), (2, 1), (5, 0), (4, 1), (4, 2)})
        bad_human = deepcopy(self.execution)
        object.__setattr__(bad_human.context.human_replay, "board", different)
        bad_fingerprint = deepcopy(self.execution)
        object.__setattr__(bad_fingerprint.context.layout, "board_fingerprint", "invented")
        bad_stage2 = replace(self.execution.stage2_result,
                             replay_data=replace(self.execution.stage2_result.replay_data, board=different))
        cases = (None, {}, self.execution.context, bad_human, bad_fingerprint,
                 replace(self.execution, stage2_result=bad_stage2),
                 replace(self.execution, stage2_result=replace(self.execution.stage2_result, status=GameStatus.PLAYING)),
                 replace(self.execution, stage2_result=replace(self.execution.stage2_result, started_from_hidden=False)),
                 replace(self.execution, stage3_result=replace(self.execution.stage3_result, status=GameStatus.PLAYING)))
        for source in cases:
            with self.subTest(source_type=type(source)), self.assertRaises(ValueError):
                SameBoardPlayback(source)

    def test_no_generic_time_or_benchmark_identity_fields(self):
        for player in (self.playback, self.playback._stage3):
            for name in ("time", "current_time", "speed", "progress", "seed", "game_index", "spec",
                         "benchmark_set_id", "cumulative_modeled_us", "registry"):
                self.assertFalse(hasattr(player, name), name)

    def test_module_import_and_exercise_without_qt_or_benchmark_wrapper(self):
        script = """
import sys
for name in ('PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'stage3_execution',
             'stage3_trace_player', 'same_board_execution_worker', 'same_board_execution_job'):
    sys.modules[name] = None
from replay_model import ReplayBoard, ReplayData, ReplayEvent
from same_board_comparison import HumanComparisonContext
from same_board_runner import run_same_board_comparison
from same_board_playback import SameBoardPlayback, ComparisonRun
context = HumanComparisonContext(ReplayData(ReplayBoard(1, 1, 0, ()),
    (ReplayEvent(0, 0, 0, 'OPEN'),)), declared_full_game_human=True)
execution = run_same_board_comparison(context)  # Fixture creation, not playback.
player = SameBoardPlayback(execution)
for run in ComparisonRun:
    player.select(run)
    assert player.current_index == 0 and player.status.name == 'PLAYING'
    assert player.next() and player.status.name == 'WON'
    assert player.previous() and player.current_index == 0
    player.go_to(1)
"""
        completed = subprocess.run([sys.executable, "-B", "-S", "-c", script],
                                   cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


class FixedLayoutStage3PlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.execution, cls.prefixes = captured_comparison()
        cls.board = cls.execution.context.layout.board
        cls.result = cls.execution.stage3_result

    def state(self, player):
        return player.current_index, player.status, player.get_observation(), deepcopy(player._engine.__dict__)

    def test_only_recorded_move_executes_and_obsolete_plan_suffix_is_ignored(self):
        setup = self.result.traces[4]
        self.assertEqual(len(setup.decision.plan.actions), 3)
        self.assertNotEqual(setup.decision.plan.actions[1], self.result.traces[5].move)
        player = SameBoardStage3Player(self.board, self.result)
        applied = []
        real_step = MinesweeperEngine.step

        def step(engine, x, y, action):
            applied.append(SimpleMove(action, x, y))
            return real_step(engine, x, y, action)

        with patch.object(MinesweeperEngine, "step", new=step):
            for trace in self.result.traces:
                before = len(applied)
                self.assertTrue(player.next())
                self.assertEqual(applied[before:], [trace.move])
        self.assertEqual(tuple(applied), self.result.moves)
        self.assertEqual(player.get_observation(), self.prefixes[ComparisonRun.STAGE3][-1][0])

    def test_standalone_index_validation_and_same_index_noop(self):
        player = SameBoardStage3Player(self.board, self.result)
        player.go_to(3)
        before = self.state(player)
        for invalid in (True, False, -1, player.action_count + 1, 0.0, 1.5, "3", None):
            with self.assertRaises(ValueError):
                player.go_to(invalid)
            self.assertEqual(self.state(player), before)
        with patch.object(MinesweeperEngine, "step", side_effect=AssertionError("same index")), \
             patch.object(MinesweeperEngine, "reset_with_mines", side_effect=AssertionError("same index")):
            self.assertEqual(player.go_to(3), before[2])

    def test_rejects_wrong_source_types_empty_stream_and_nonterminal_result(self):
        for board, result in ((None, self.result), (self.board, None),
                              (self.board, Stage3RunResult(GameStatus.WON, ())),
                              (self.board, replace(self.result, status=GameStatus.PLAYING)),
                              (self.board, replace(self.result, status=True))):
            with self.assertRaises(ValueError):
                SameBoardStage3Player(board, result)

    def test_malformed_pending_trace_or_move_fails_before_step(self):
        from types import SimpleNamespace
        trace = self.result.traces[2]
        cases = [None, SimpleNamespace(**vars(trace)), replace(trace, move=None),
                 replace(trace, status_after=False)]
        for move in (SimpleMove(True, 1, 0), SimpleMove(999, 1, 0),
                     SimpleMove(Action.OPEN, False, 0), SimpleMove(Action.OPEN, 1.0, 0),
                     SimpleMove(Action.OPEN, -1, 0), SimpleMove(Action.OPEN, 6, 0),
                     SimpleMove(Action.OPEN, 1, 4)):
            cases.append(replace(trace, move=move))
        for invalid in cases:
            result = replace(self.result, traces=(*self.result.traces[:2], invalid, *self.result.traces[3:]))
            player = SameBoardStage3Player(self.board, result)
            player.go_to(2)
            before = self.state(player)
            with patch.object(MinesweeperEngine, "step", side_effect=AssertionError("malformed step")):
                with self.assertRaises(ValueError):
                    player.next()
            self.assertEqual(self.state(player), before)

    def test_status_mismatch_failed_seek_and_next_are_atomic(self):
        traces = (*self.result.traces[:2], replace(self.result.traces[2], status_after=GameStatus.LOST),
                  *self.result.traces[3:])
        player = SameBoardStage3Player(self.board, replace(self.result, traces=traces))
        player.go_to(1)
        before = self.state(player)
        with self.assertRaisesRegex(ValueError, "status_after"):
            player.go_to(4)
        self.assertEqual(self.state(player), before)
        player.go_to(2)
        before = self.state(player)
        with self.assertRaisesRegex(ValueError, "status_after"):
            player.next()
        self.assertEqual(self.state(player), before)

    def test_final_result_mismatch_does_not_publish_terminal_state(self):
        player = SameBoardStage3Player(self.board, replace(self.result, status=GameStatus.LOST))
        player.go_to(player.action_count - 1)
        before = self.state(player)
        for navigate in (player.next, lambda: player.go_to(player.action_count)):
            with self.assertRaisesRegex(ValueError, "result.status"):
                navigate()
            self.assertEqual(self.state(player), before)

    def test_trailing_action_after_win_or_loss_is_rejected_without_executing_it(self):
        for source in (self.execution, run_same_board_comparison(human_context(mined_origin=True))):
            result = source.stage3_result
            player = SameBoardStage3Player(source.context.layout.board,
                                          replace(result, traces=(*result.traces, result.traces[-1])))
            player.go_to(len(result.traces))
            before = self.state(player)
            with patch.object(MinesweeperEngine, "step", side_effect=AssertionError("post-terminal step")):
                with self.assertRaisesRegex(ValueError, "follows a terminal"):
                    player.next()
            self.assertEqual(self.state(player), before)
            player.go_to(0)
            before = self.state(player)
            with self.assertRaisesRegex(ValueError, "follows a terminal"):
                player.go_to(player.action_count)
            self.assertEqual(self.state(player), before)

    def test_step_exception_after_mutation_is_atomic_for_next_seek_and_previous(self):
        player = SameBoardStage3Player(self.board, self.result)
        player.go_to(3)
        before = self.state(player)
        real_step = MinesweeperEngine.step

        def fail_after_step(engine, x, y, action):
            real_step(engine, x, y, action)
            raise RuntimeError("injected after candidate mutation")

        with patch.object(MinesweeperEngine, "step", new=fail_after_step):
            for navigate in (player.next, lambda: player.go_to(5), player.previous):
                with self.assertRaisesRegex(RuntimeError, "candidate mutation"):
                    navigate()
                self.assertEqual(self.state(player), before)
        self.assertTrue(player.next())
        self.assertEqual(player.get_observation(), self.prefixes[ComparisonRun.STAGE3][4][0])


if __name__ == "__main__":
    unittest.main()
