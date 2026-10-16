"""Pure comparison admission preserves the existing Replay/Engine authorities."""

import subprocess
import sys
import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from benchmark_board import calculate_board_fingerprint
from core_engine import CellState, GameStatus
from mouse_trace import MouseTraceData, MouseTracePoint, MouseTraceSegment
from replay_model import (
    ACTION_CHORD, ACTION_FLAG, ACTION_OPEN,
    SOURCE_AI, SOURCE_ALGORITHM, SOURCE_HUMAN,
    ReplayBoard, ReplayData, ReplayEvent,
)
from replay_player import ReplayPlayer
from same_board_comparison import (
    STAGE2_CANONICAL_FIRST_ACTION, STAGE3_CANONICAL_FIRST_ACTION,
    ComparisonAdmissionError, ComparisonLayout, HumanComparisonContext,
)


def replay_with(actions, *, mines=((1, 1),), width=2, height=2):
    return ReplayData(
        ReplayBoard(width, height, len(mines), mines),
        tuple(ReplayEvent(index / 4, x, y, action)
              for index, (action, x, y) in enumerate(actions)),
    )


WIN_ACTIONS = ((ACTION_OPEN, 0, 0), (ACTION_OPEN, 1, 0), (ACTION_OPEN, 0, 1))
LOSS_ACTIONS = ((ACTION_OPEN, 0, 0), (ACTION_OPEN, 1, 1))


def admit(replay):
    return HumanComparisonContext(replay, declared_full_game_human=True)


class HumanAdmissionTests(unittest.TestCase):
    def test_complete_v1_win_without_trace(self):
        replay = replay_with(WIN_ACTIONS)
        context = admit(replay)
        self.assertIs(context.human_replay, replay)
        self.assertIs(context.layout.board, replay.board)
        self.assertEqual(context.terminal_status, GameStatus.WON)
        self.assertEqual(context.terminal_event_index, 2)
        self.assertEqual(context.terminal_observation, ((1, 1), (1, CellState.FLAGGED)))
        self.assertEqual(context.human_replay.schema_version, 1)
        self.assertIsNone(context.human_replay.mouse_trace)

    def test_complete_loss(self):
        context = admit(replay_with(LOSS_ACTIONS))
        self.assertEqual(context.terminal_status, GameStatus.LOST)
        self.assertEqual(context.terminal_event_index, 1)
        self.assertEqual(context.terminal_observation, (
            (1, CellState.HIDDEN), (CellState.HIDDEN, CellState.EXPLODED),
        ))

    def test_v2_retains_original_attachment_and_stream_without_copying(self):
        trace = MouseTraceData(2, 2, (MouseTraceSegment(20, (
            MouseTracePoint(0, 10.25, 10.5, 0),
            MouseTracePoint(700, 22.75, 10.5),
            MouseTracePoint(800, 30, 10, 1),
            MouseTracePoint(1500, 10, 30, 2),
        )),))
        replay = replace(replay_with(WIN_ACTIONS), schema_version=2, mouse_trace=trace)
        before = deepcopy(replay)
        context = admit(replay)
        self.assertEqual(replay, before)
        self.assertIs(context.human_replay, replay)
        self.assertIs(context.human_replay.mouse_trace, trace)
        self.assertIs(context.human_replay.events, replay.events)
        self.assertIs(context.first_event, replay.events[0])
        self.assertIs(context.first_open_event, replay.events[0])
        self.assertEqual(context.terminal_status, GameStatus.WON)

    def test_noncanonical_human_open_and_mined_solver_origin_are_admissible(self):
        replay = replay_with(
            ((ACTION_OPEN, 1, 0), (ACTION_OPEN, 0, 1), (ACTION_OPEN, 1, 1)),
            mines=((0, 0),),
        )
        context = admit(replay)
        self.assertEqual(context.terminal_status, GameStatus.WON)
        self.assertTrue(context.solver_origin_is_mine)
        self.assertFalse(context.matches_canonical_recorded_start)
        self.assertEqual((context.first_open_event.x, context.first_open_event.y), (1, 0))

    def test_mined_origin_immediate_human_loss_is_not_filtered_or_relocated(self):
        replay = replay_with(((ACTION_OPEN, 0, 0),), mines=((0, 0),))
        with patch("core_engine.random.sample", side_effect=AssertionError("regeneration")):
            context = admit(replay)
        self.assertEqual(context.terminal_status, GameStatus.LOST)
        self.assertEqual(context.terminal_event_index, 0)
        self.assertEqual(context.terminal_observation[0][0], CellState.EXPLODED)
        self.assertTrue(context.solver_origin_is_mine)
        self.assertTrue(context.matches_canonical_recorded_start)
        self.assertIs(context.layout.board, replay.board)

    def test_prelude_and_all_wasted_inputs_remain_in_original_order(self):
        replay = replay_with((
            (ACTION_CHORD, 0, 0),  # Untimed, hidden-cell CHORD.
            (ACTION_FLAG, 1, 0),   # Wrong flag.
            (ACTION_OPEN, 1, 0),   # Blocked OPEN is still the first OPEN.
            (ACTION_FLAG, 1, 0),   # Unflag.
            (ACTION_OPEN, 0, 0),
            (ACTION_OPEN, 0, 0),   # Already revealed.
            (ACTION_FLAG, 0, 0),   # Already revealed.
            (ACTION_CHORD, 0, 0),  # Flag-count mismatch.
            (ACTION_OPEN, 1, 0),
            (ACTION_OPEN, 0, 1),
        ))
        before = deepcopy(replay)
        context = admit(replay)
        self.assertEqual(replay, before)
        self.assertIs(context.human_replay.events, replay.events)
        self.assertEqual(context.terminal_event_index, 9)
        self.assertEqual(context.first_open_event_index, 2)
        self.assertIs(context.first_open_event, replay.events[2])
        self.assertTrue(context.has_prelude_events)
        self.assertFalse(context.matches_canonical_recorded_start)
        self.assertEqual(context.terminal_status, GameStatus.WON)

    def test_real_chord_semantics_reconstruct_win_and_wrong_flag_loss(self):
        for flag, status, expected in (
            ((1, 1), GameStatus.WON, ((1, 1), (1, CellState.FLAGGED))),
            ((1, 0), GameStatus.LOST, ((1, CellState.FALSE_FLAG), (1, CellState.EXPLODED))),
        ):
            with self.subTest(flag=flag):
                context = admit(replay_with((
                    (ACTION_OPEN, 0, 0), (ACTION_FLAG, *flag), (ACTION_CHORD, 0, 0),
                )))
                self.assertEqual(context.terminal_status, status)
                self.assertEqual(context.terminal_observation, expected)
                self.assertEqual(context.terminal_event_index, 2)

    def test_reconstruction_is_deterministic_and_ignores_wall_clock(self):
        replay = replay_with(WIN_ACTIONS)
        with patch("core_engine.time.perf_counter", return_value=10.0):
            first = admit(replay)
        with patch("core_engine.time.perf_counter", return_value=900.0):
            second = admit(replay)
        self.assertEqual(first, second)
        player = ReplayPlayer(replay)
        observation = player.go_to(len(replay.events))
        self.assertEqual(first.terminal_status, player.engine.status)
        self.assertEqual(first.terminal_observation, tuple(map(tuple, observation)))
        self.assertEqual(replay.events[-1].elapsed_time, 0.5)

    def test_each_admission_uses_a_fresh_fixed_hidden_reconstruction(self):
        players = []

        def new_player(replay):
            player = ReplayPlayer(replay)
            players.append(player)
            self.assertEqual(player.current_index, 0)
            self.assertEqual(player.engine.status, GameStatus.PLAYING)
            self.assertEqual(player.get_observation(), [[CellState.HIDDEN] * 2 for _ in range(2)])
            snapshot = player.engine.get_board_snapshot()
            self.assertTrue(snapshot.mines_placed)
            self.assertEqual(snapshot.mines, replay.board.mine_positions)
            return player

        with patch("same_board_comparison.ReplayPlayer", side_effect=new_player), \
             patch("core_engine.random.sample", side_effect=AssertionError("regeneration")):
            first = admit(replay_with(WIN_ACTIONS))
            second = admit(replay_with(WIN_ACTIONS))
        self.assertIsNot(players[0].engine, players[1].engine)
        self.assertEqual(first, second)

    def test_supported_dimension_edges_are_not_expert_board_only(self):
        for width, height in ((1, 1), (30, 1), (1, 16), (30, 16)):
            with self.subTest(dimensions=(width, height)):
                context = admit(replay_with(
                    ((ACTION_OPEN, 0, 0),), width=width, height=height, mines=(),
                ))
                self.assertEqual(context.terminal_status, GameStatus.WON)

    def test_human_source_requires_declaration_without_proving_provenance(self):
        # Human metadata is necessary eligibility, not provenance proof: old
        # Human-labeled recordings may contain Auto input. Declaration is intent,
        # and reconstruction proves structural completion, not historical origin.
        replay = replace(replay_with(WIN_ACTIONS), source_type=SOURCE_HUMAN)
        with self.assertRaises(ComparisonAdmissionError):
            HumanComparisonContext(replay, declared_full_game_human=False)
        context = admit(replay)
        self.assertIs(context.declared_full_game_human, True)
        self.assertIs(context.human_replay, replay)
        self.assertEqual(context.human_replay.source_type, SOURCE_HUMAN)


class AdmissionRejectionTests(unittest.TestCase):
    def test_algorithm_and_ai_sources_cannot_be_overridden_by_human_declaration(self):
        for source in (SOURCE_ALGORITHM, SOURCE_AI):
            with self.subTest(source=source):
                replay = replace(replay_with(WIN_ACTIONS), source_type=source)
                before = deepcopy(replay)
                with patch("same_board_comparison.ReplayPlayer") as player:
                    with self.assertRaisesRegex(ComparisonAdmissionError, "source_type=SOURCE_HUMAN"):
                        HumanComparisonContext(replay, declared_full_game_human=True)
                    player.assert_not_called()
                self.assertEqual(replay, before)
                # Their existing Replay validity and playback remain unchanged.
                ordinary_player = ReplayPlayer(replay)
                ordinary_player.go_to(len(replay.events))
                self.assertEqual(ordinary_player.engine.status, GameStatus.WON)

    def test_empty_and_nonterminal_streams_are_comparison_rejections_only(self):
        for actions in ((), WIN_ACTIONS[:1]):
            with self.subTest(actions=actions):
                replay = replay_with(actions)
                with self.assertRaisesRegex(ComparisonAdmissionError, "incomplete"):
                    admit(replay)
                player = ReplayPlayer(replay)
                player.go_to(len(replay.events))
                self.assertEqual(player.engine.status, GameStatus.PLAYING)

    def test_flag_chord_only_stream_cannot_finish_under_existing_engine(self):
        # At least one safe cell exists; FLAG cannot reveal it and CHORD needs
        # an already opened center. There is no valid terminal no-OPEN fixture.
        replay = replay_with(((ACTION_CHORD, 0, 0), (ACTION_FLAG, 1, 1), (ACTION_CHORD, 1, 1)))
        player = ReplayPlayer(replay)
        player.go_to(len(replay.events))
        self.assertEqual(player.engine.status, GameStatus.PLAYING)
        with self.assertRaisesRegex(ComparisonAdmissionError, "incomplete"):
            admit(replay)

    def test_rejects_first_trailing_event_after_either_terminal_outcome(self):
        for actions, status in ((WIN_ACTIONS, GameStatus.WON), (LOSS_ACTIONS, GameStatus.LOST)):
            with self.subTest(status=status):
                replay = replay_with(actions + ((ACTION_CHORD, 0, 0), (ACTION_FLAG, 1, 1)))
                before = deepcopy(replay)
                # Ordinary Replay still accepts and ignores these terminal tails.
                player = ReplayPlayer(replay)
                player.go_to(len(replay.events))
                self.assertEqual(player.engine.status, status)
                with self.assertRaisesRegex(
                    ComparisonAdmissionError,
                    f"event {len(actions)} follows terminal event {len(actions) - 1} ",
                ):
                    admit(replay)
                self.assertEqual(replay, before)

    def test_dimension_rejection_precedes_reconstruction(self):
        for width, height in ((31, 16), (30, 17), (16, 30)):
            with self.subTest(dimensions=(width, height)):
                replay = replay_with(((ACTION_OPEN, 0, 0),), width=width, height=height, mines=())
                with patch("same_board_comparison.ReplayPlayer") as player:
                    with self.assertRaisesRegex(ComparisonAdmissionError, "dimensions"):
                        admit(replay)
                    player.assert_not_called()

    def test_declaration_is_required_and_accepts_only_explicit_true(self):
        replay = replay_with(WIN_ACTIONS)
        self.assertEqual(replay.source_type, SOURCE_HUMAN)
        with self.assertRaises(TypeError):
            HumanComparisonContext(replay)
        for value in (False, None, 0, 1, "human", "True", []):
            with self.subTest(value=value), self.assertRaisesRegex(
                ComparisonAdmissionError, "declared_full_game_human=True",
            ):
                HumanComparisonContext(replay, declared_full_game_human=value)

    def test_rejects_non_replay_input(self):
        for value in (None, {}, (), replay_with(WIN_ACTIONS).board):
            with self.subTest(value=value), self.assertRaisesRegex(
                ComparisonAdmissionError, "requires ReplayData",
            ):
                admit(value)

    def test_rejects_mutable_duck_typed_board_and_events_not_checked_by_replay(self):
        replay = replay_with(WIN_ACTIONS)
        mutable_board = SimpleNamespace(width=2, height=2, num_mines=1, mine_positions={(1, 1)})
        mutable_event = SimpleNamespace(elapsed_time=0, x=0, y=0, action=ACTION_OPEN)
        for malformed in (
            ReplayData(mutable_board, replay.events),
            ReplayData(replay.board, (mutable_event,)),
        ):
            with self.subTest(replay=malformed), self.assertRaisesRegex(
                ComparisonAdmissionError, "ReplayBoard and ReplayEvent",
            ):
                admit(malformed)

    def test_mismatching_installed_layout_is_rejected_before_actions(self):
        replay = replay_with(WIN_ACTIONS)
        player = ReplayPlayer(replay)
        player.engine.reset_with_mines(2, 2, 1, {(0, 0)})
        with patch("same_board_comparison.ReplayPlayer", return_value=player), \
             patch.object(player, "next") as step:
            with self.assertRaisesRegex(ComparisonAdmissionError, "layout differs"):
                admit(replay)
            step.assert_not_called()


class OpeningQualificationTests(unittest.TestCase):
    def test_event_zero_canonical_open_has_no_prelude(self):
        replay = replay_with(WIN_ACTIONS)
        context = admit(replay)
        self.assertIs(context.first_event, replay.events[0])
        self.assertIs(context.first_open_event, replay.events[0])
        self.assertEqual(context.first_open_event_index, 0)
        self.assertFalse(context.has_prelude_events)
        self.assertFalse(context.solver_origin_is_mine)
        self.assertTrue(context.matches_canonical_recorded_start)
        self.assertEqual(STAGE2_CANONICAL_FIRST_ACTION, (ACTION_OPEN, 0, 0))
        self.assertEqual(STAGE3_CANONICAL_FIRST_ACTION, (ACTION_OPEN, 0, 0))

    def test_open_at_origin_after_prelude_is_not_a_matching_recorded_start(self):
        for prelude in (
            ((ACTION_CHORD, 0, 0),),
            ((ACTION_FLAG, 1, 0), (ACTION_FLAG, 1, 0)),
        ):
            with self.subTest(prelude=prelude):
                replay = replay_with(prelude + WIN_ACTIONS)
                context = admit(replay)
                self.assertIs(context.first_event, replay.events[0])
                self.assertIs(context.first_open_event, replay.events[len(prelude)])
                self.assertEqual(context.first_open_event_index, len(prelude))
                self.assertTrue(context.has_prelude_events)
                self.assertFalse(context.matches_canonical_recorded_start)

    def test_first_open_elsewhere_with_safe_origin_is_not_a_match(self):
        context = admit(replay_with((WIN_ACTIONS[1], WIN_ACTIONS[0], WIN_ACTIONS[2])))
        self.assertEqual(context.first_open_event_index, 0)
        self.assertFalse(context.has_prelude_events)
        self.assertFalse(context.solver_origin_is_mine)
        self.assertFalse(context.matches_canonical_recorded_start)


class LayoutAndSeparationTests(unittest.TestCase):
    def test_identity_uses_existing_canonical_calculator_and_retains_source_board(self):
        board = replay_with(WIN_ACTIONS).board
        layout = ComparisonLayout(board)
        self.assertIs(layout.board, board)
        self.assertEqual(layout.board_fingerprint, calculate_board_fingerprint(
            board.width, board.height, board.num_mines, board.mine_positions,
        ))
        self.assertEqual(layout, ComparisonLayout(ReplayBoard(2, 2, 1, [(1, 1)])))
        # No claimed hash or invented benchmark index/seed/set is accepted.
        self.assertEqual(tuple(f.name for f in fields(layout)), ("board", "board_fingerprint"))
        with self.assertRaises(TypeError):
            ComparisonLayout(board, board_fingerprint="0" * 64)

    def test_changed_coordinates_dimensions_and_count_change_identity(self):
        original = ComparisonLayout(ReplayBoard(2, 2, 1, {(1, 1)}))
        for board in (
            ReplayBoard(2, 2, 1, {(0, 0)}), ReplayBoard(3, 2, 1, {(1, 1)}),
            ReplayBoard(2, 3, 1, {(1, 1)}), ReplayBoard(2, 2, 0, ()),
        ):
            with self.subTest(board=board):
                changed = ComparisonLayout(board)
                self.assertNotEqual(changed, original)
                self.assertNotEqual(changed.board_fingerprint, original.board_fingerprint)

    def test_fingerprint_equality_alone_cannot_establish_same_layout(self):
        with patch("same_board_comparison.calculate_board_fingerprint", return_value="0" * 64):
            first = ComparisonLayout(ReplayBoard(2, 2, 1, {(1, 1)}))
            second = ComparisonLayout(ReplayBoard(2, 2, 1, {(0, 0)}))
        self.assertEqual(first.board_fingerprint, second.board_fingerprint)
        self.assertNotEqual(first, second)

    def test_layout_rejects_non_authoritative_board_type(self):
        with self.assertRaisesRegex(ComparisonAdmissionError, "requires a ReplayBoard"):
            ComparisonLayout(None)

    def test_retained_context_and_nested_state_are_immutable(self):
        context = admit(replay_with(WIN_ACTIONS))
        for model in (context, context.layout, context.human_replay, context.first_event):
            for model_field in fields(model):
                with self.subTest(model=type(model), field=model_field.name):
                    with self.assertRaises(FrozenInstanceError):
                        setattr(model, model_field.name, None)
        with self.assertRaises(TypeError):
            context.terminal_observation[0][0] = 7
        with self.assertRaises(AttributeError):
            context.layout.board.mine_positions.add((0, 0))
        # Replacing the source cannot reuse stale admission/derived results.
        with self.assertRaisesRegex(ComparisonAdmissionError, "incomplete"):
            replace(context, human_replay=replay_with(()))

    def test_fresh_import_and_admission_without_qt_solvers_models_or_persistence(self):
        script = """
import sys
for name in ('PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'simple_runner',
             'stage3_runner', 'stage3_physical', 'sqlite3'):
    sys.modules[name] = None
from same_board_comparison import HumanComparisonContext
from replay_model import ReplayBoard, ReplayData, ReplayEvent
replay = ReplayData(ReplayBoard(1, 1, 0, ()), (ReplayEvent(0, 0, 0, 'OPEN'),))
context = HumanComparisonContext(replay, declared_full_game_human=True)
assert context.terminal_status.name == 'WON'
"""
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
