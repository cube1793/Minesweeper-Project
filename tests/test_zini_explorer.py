"""Transport ownership, lazy trace, information gate, and controller playback.

Frozen V1 paths exercise playback here; test_zini_golden checks fresh search
output. The historical 120-click path remains only a replay-validity witness.
"""

from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

from board_snapshot import BoardSnapshot
from tests.zini_fixtures import _EXPERT_SEED1003_120_TRACE, _expert_seed1003_snapshot
from tests.zini_golden_helpers import workload_snapshot
from tests.zini_v1_golden import GOLDEN
from zini_calculator import ZiniMove, calculate_g_zini
from zini_explorer import ZiniExplorerController
from zini_trace import build_zini_trace


def _small_snapshot():
    return BoardSnapshot(
        3, 3, 1, True, frozenset({(1, 1)}),
        ((1, 1, 1), (1, 0, 1), (1, 1, 1)),
    )


def _payload(token, moves, *, clicks=None):
    return {
        "token": token,
        "clicks": sum(move.clicks_added for move in moves) if clicks is None else clicks,
        "moves": moves,
        "error": None,
    }


class ZiniExplorerTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = _small_snapshot()
        self.result = calculate_g_zini(self.snapshot)
        self.controller = ZiniExplorerController()
        self.controller.begin(7, self.snapshot, eligible=True)
        self.payload = _payload(7, self.result.moves)

    def receive(self):
        self.assertTrue(self.controller.receive(self.payload, expected_token=7))

    def assert_hidden(self):
        controller = self.controller
        for field in (
            "snapshot", "moves", "trace", "current_index", "step_count",
            "current_step", "cumulative_clicks",
        ):
            self.assertIsNone(getattr(controller, field), field)
        self.assertEqual(controller.revealed, frozenset())
        self.assertEqual(controller.flagged_mines, frozenset())
        self.assertIsNone(controller.request_trace())
        self.assertFalse(controller.go_to(0))
        self.assertFalse(controller.next())
        self.assertFalse(controller.previous())

    def test_pending_receipt_and_all_reads_are_lazy_until_explicit_request(self):
        controller = self.controller
        self.assertEqual(controller.state, "pending")
        self.assertFalse(controller.completed)
        self.assertIsNone(controller.request_trace())
        with patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as build:
            self.receive()
            self.assertTrue(controller.completed)
            self.assertTrue(controller.result_received)
            self.assertEqual(controller.state, "ready")
            self.assertEqual(controller.clicks, 5)
            self.assertIs(controller.snapshot, self.snapshot)
            self.assertEqual(controller.moves, self.result.moves)
            self.assertIsNone(controller.trace)
            self.assertIsNone(controller.current_index)
            self.assertIsNone(controller.step_count)
            self.assertIsNone(controller.current_step)
            self.assertIsNone(controller.cumulative_clicks)
            self.assertFalse(controller.next())
            self.assertFalse(controller.previous())
            self.assertFalse(controller.go_to(0))
            build.assert_not_called()
            trace = controller.request_trace()
            self.assertIsNotNone(trace)
            controller.next()
            self.assertIs(controller.request_trace(), trace)
            self.assertIs(controller.trace, trace)
            self.assertEqual(controller.current_index, 1)
            build.assert_called_once()
            self.assertIs(build.call_args.args[0], self.snapshot)
            self.assertEqual(build.call_args.args[1], self.result)

    def test_information_gate_covers_cached_and_pending_answer_data(self):
        controller = self.controller
        controller.set_eligible(False)
        self.assert_hidden()
        self.receive()
        with patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as build:
            self.assertEqual(controller.state, "unavailable")
            self.assert_hidden()
            build.assert_not_called()
            controller.set_eligible(True)
            trace = controller.request_trace()
            controller.go_to(2)
            before = controller.revealed
            controller.set_eligible(False)
            self.assert_hidden()
            controller.set_eligible(True)
            self.assertIs(controller.request_trace(), trace)
            self.assertEqual(controller.current_index, 2)
            self.assertEqual(controller.revealed, before)
            build.assert_called_once()

    def test_invalidation_drops_pending_or_built_session_and_ignores_late_result(self):
        for build_first in (False, True):
            with self.subTest(build_first=build_first):
                self.controller.begin(7, self.snapshot, eligible=True)
                if build_first:
                    self.receive()
                    self.controller.request_trace()
                    self.controller.go_to(2)
                self.controller.invalidate()
                self.assertIsNone(self.controller.token)
                self.assertIsNone(self.controller.clicks)
                self.assertIsNone(self.controller.error)
                self.assertFalse(self.controller.completed)
                self.assertFalse(self.controller.eligible)
                self.assertEqual(self.controller.state, "unavailable")
                self.assert_hidden()
                self.assertFalse(self.controller.receive(self.payload, expected_token=7))
                self.controller.set_eligible(True)
                self.assert_hidden()

    def test_new_token_on_same_board_discards_old_cache_and_stale_success_or_error(self):
        self.receive()
        old_trace = self.controller.request_trace()
        self.controller.begin(8, self.snapshot, eligible=True)
        for payload, expected_token in (
            (self.payload, 7),
            (self.payload, 8),
            ({"token": 7, "clicks": None, "moves": None, "error": "old"}, 8),
            (None, 7),
        ):
            self.assertFalse(self.controller.receive(payload, expected_token=expected_token))
            self.assertEqual(self.controller.state, "pending")
            self.assertIsNone(self.controller.error)
            self.assertIsNone(self.controller.trace)
        self.assertTrue(self.controller.receive(_payload(8, self.result.moves), expected_token=8))
        new_trace = self.controller.request_trace()
        self.assertIsNot(new_trace, old_trace)
        self.assertEqual(self.controller.current_index, 0)

    def test_wrong_expected_token_and_duplicate_receipts_cannot_poison_current_state(self):
        for expected in (True, 7.0, "7", 6, None):
            self.assertFalse(self.controller.receive(self.payload, expected_token=expected))
        self.receive()
        trace = self.controller.request_trace()
        self.controller.go_to(2)
        for payload in (self.payload, None, {"token": 7, "error": "broken"}):
            self.assertFalse(self.controller.receive(payload, expected_token=7))
            self.assertIs(self.controller.trace, trace)
            self.assertEqual(self.controller.current_index, 2)
            self.assertIsNone(self.controller.error)

    def test_worker_failure_is_distinct_from_trace_failure(self):
        payload = {"token": 7, "clicks": None, "moves": None, "error": "RuntimeError('worker')"}
        self.assertTrue(self.controller.receive(payload, expected_token=7))
        self.assertTrue(self.controller.completed)
        self.assertIsNone(self.controller.clicks)
        self.assertEqual(self.controller.worker_error, payload["error"])
        self.assertIsNone(self.controller.trace_error)
        self.assertEqual(self.controller.state, "error")
        with patch("zini_explorer.build_zini_trace") as build:
            self.assertIsNone(self.controller.request_trace())
            build.assert_not_called()

    def test_malformed_envelopes_never_raise_or_accept_a_counter_value(self):
        payloads = [None, (), [], "bad", {}, {"token": 7}]
        for token in (True, False, 7.0, "7", None):
            payloads.append({**self.payload, "token": token})
        for clicks in (True, False, 5.0, "5", None, -1):
            payloads.append({**self.payload, "clicks": clicks})
        for error in (True, 1, [], {}, "worker failure with success fields"):
            payloads.append({**self.payload, "error": error})
        for key in ("token", "clicks", "error"):
            payloads.append({name: value for name, value in self.payload.items() if name != key})
        for payload in payloads:
            with self.subTest(payload=payload):
                self.controller.begin(7, self.snapshot, eligible=True)
                self.assertTrue(self.controller.receive(payload, expected_token=7))
                self.assertTrue(self.controller.completed)
                self.assertIsNone(self.controller.clicks)
                self.assertIsNone(self.controller.worker_error)
                self.assertIsNotNone(self.controller.trace_error)
                self.assertEqual(self.controller.state, "error")

    def test_bad_moves_preserve_valid_clicks_without_calling_builder(self):
        class DerivedMove(ZiniMove):
            pass

        class DerivedText(str):
            pass

        class DerivedInt(int):
            pass

        first = self.result.moves[0]
        bad_moves = [
            None, [], list(self.result.moves), (tuple(vars(first).values()),),
            (None,), (DerivedMove(**vars(first)),),
        ]
        for changes in (
            {"action": "unknown"}, {"action": None}, {"action": ["click"]},
            {"action": DerivedText("click")},
            {"x": True}, {"x": 1.0}, {"x": -1}, {"x": DerivedInt(1)},
            {"y": False}, {"y": 0.0}, {"y": -1},
            {"premium": None}, {"premium": True}, {"premium": 2.0},
            {"premium": DerivedInt(2)},
            {"clicks_added": True}, {"clicks_added": 1.0},
            {"clicks_added": 0}, {"clicks_added": -1},
            {"action": "fallback_click", "premium": 2},
            {"action": "flag_chord", "premium": None},
        ):
            bad_moves.append((replace(first, **changes), *self.result.moves[1:]))
        bad_moves.append(self.result.moves[:-1])  # Well-formed moves, wrong sum.
        with patch("zini_explorer.build_zini_trace") as build:
            for moves in bad_moves:
                with self.subTest(moves=moves):
                    self.controller.begin(7, self.snapshot, eligible=True)
                    self.assertTrue(self.controller.receive(
                        {**self.payload, "moves": moves}, expected_token=7,
                    ))
                    self.assertEqual(self.controller.clicks, self.result.clicks)
                    self.assertIsNone(self.controller.moves)
                    self.assertIsNone(self.controller.worker_error)
                    self.assertIsNotNone(self.controller.trace_error)
                    self.assertIsNone(self.controller.request_trace())
            self.controller.begin(7, self.snapshot, eligible=True)
            self.controller.receive(
                {key: value for key, value in self.payload.items() if key != "moves"},
                expected_token=7,
            )
            self.assertEqual(self.controller.clicks, self.result.clicks)
            self.assertIsNotNone(self.controller.trace_error)
            build.assert_not_called()

    def test_semantics_validation_is_lazy_and_failed_build_is_cached(self):
        moves = (replace(self.result.moves[0], premium=99), *self.result.moves[1:])
        with patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as build:
            self.controller.receive(_payload(7, moves), expected_token=7)
            self.assertEqual(self.controller.state, "ready")
            self.assertIsNone(self.controller.trace_error)
            build.assert_not_called()
            self.assertIsNone(self.controller.request_trace())
            self.assertEqual(self.controller.state, "error")
            self.assertEqual(self.controller.clicks, self.result.clicks)
            self.assertIsNone(self.controller.worker_error)
            self.assertIn("premium", self.controller.trace_error)
            for _ in range(3):
                self.assertIsNone(self.controller.request_trace())
            self.controller.set_eligible(False)
            self.controller.set_eligible(True)
            self.assertIsNone(self.controller.request_trace())
            build.assert_called_once()
            self.controller.begin(8, self.snapshot, eligible=True)
            self.controller.receive(_payload(8, self.result.moves), expected_token=8)
            self.assertIsNotNone(self.controller.request_trace())
            self.assertEqual(build.call_count, 2)

    def test_builder_exception_is_isolated_but_base_exception_is_not_swallowed(self):
        self.receive()
        with patch("zini_explorer.build_zini_trace", side_effect=RuntimeError("trace unavailable")) as build:
            self.assertIsNone(self.controller.request_trace())
            self.assertIsNone(self.controller.request_trace())
            build.assert_called_once()
        self.assertIn("RuntimeError", self.controller.trace_error)
        self.assertEqual(self.controller.clicks, self.result.clicks)
        self.controller.begin(7, self.snapshot, eligible=True)
        self.receive()
        with patch("zini_explorer.build_zini_trace", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.controller.request_trace()

    def test_external_receipt_and_readonly_views_cannot_mutate_owned_state(self):
        self.receive()
        self.payload.clear()
        trace = self.controller.request_trace()
        self.controller.go_to(2)
        old_revealed, old_flags = self.controller.revealed, self.controller.flagged_mines
        self.assertIsInstance(self.controller.moves, tuple)
        for value, field, replacement in (
            (trace, "total_clicks", 999),
            (trace.steps[0], "step_index", 999),
            (self.controller.moves[0], "x", 999),
            (self.controller.snapshot, "width", 999),
        ):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, field, replacement)
        for cells in (old_revealed, old_flags):
            with self.assertRaises(AttributeError):
                cells.add((99, 99))
        for field in (
            "token", "clicks", "moves", "snapshot", "trace", "current_index",
            "revealed", "flagged_mines", "completed", "error", "eligible",
        ):
            with self.assertRaises(AttributeError):
                setattr(self.controller, field, None)
        self.assertFalse(hasattr(self.controller, "player"))
        self.controller.go_to(0)
        self.assertEqual(len(old_revealed), 5)
        self.assertEqual(old_flags, frozenset({(1, 1)}))

    def test_logical_index_physical_clicks_and_navigation_match_player_contract(self):
        self.receive()
        trace = self.controller.request_trace()
        self.assertEqual(self.controller.step_count, 4)
        self.assertFalse(self.controller.previous())
        self.assertTrue(self.controller.next())
        self.assertTrue(self.controller.next())
        self.assertEqual(self.controller.current_index, 2)
        self.assertEqual(self.controller.cumulative_clicks, 3)
        self.assertEqual(self.controller.current_step, trace.steps[1])
        self.assertTrue(self.controller.previous())
        self.assertEqual(self.controller.cumulative_clicks, 1)
        self.controller.go_to(4)
        self.assertEqual(self.controller.cumulative_clicks, 5)
        self.assertFalse(self.controller.next())
        before = self.controller.revealed
        for index in (-1, 5, True, 1.0, None, "2"):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    self.controller.go_to(index)
                self.assertEqual(self.controller.current_index, 4)
                self.assertEqual(self.controller.revealed, before)

    def test_begin_arguments_are_strict_and_invalid_begin_preserves_current_session(self):
        for token, snapshot, eligible in (
            (True, self.snapshot, True), (7.0, self.snapshot, True),
            (7, {}, True), (7, self.snapshot, 1),
            (7, replace(self.snapshot, adjacent=(([],),)), True),
            (7, replace(self.snapshot, width=True), True),
            (7, replace(self.snapshot, mines_placed=1), True),
            (7, replace(self.snapshot, mines={(1.0, 1)}), True),
        ):
            with self.assertRaises(ValueError):
                self.controller.begin(token, snapshot, eligible=eligible)
            self.assertEqual(self.controller.token, 7)
            self.assertIs(self.controller.snapshot, self.snapshot)
        with self.assertRaises(ValueError):
            self.controller.set_eligible(1)

    def test_snapshot_constructor_inputs_cannot_mutate_owned_board(self):
        mines = {(1, 1)}
        grid = [[1, 1, 1], [1, 0, 1], [1, 1, 1]]
        snapshot = BoardSnapshot(3, 3, 1, True, mines, grid)
        self.controller.begin(8, snapshot, eligible=True)
        mines.clear()
        grid[0][0] = 99
        self.assertIs(self.controller.snapshot, snapshot)
        self.assertEqual(self.controller.snapshot, self.snapshot)


class ZiniExplorerGoldenAndIsolationTests(unittest.TestCase):
    def check_playback(self, snapshot, moves):
        controller = ZiniExplorerController()
        controller.begin(1, snapshot, eligible=True)
        controller.receive(_payload(1, moves), expected_token=1)
        trace = controller.request_trace()
        self.assertIsNotNone(trace, controller.error)
        self.assertEqual(tuple(step.move for step in trace.steps), moves)
        with ExitStack() as stack:
            for target in (
                "zini_explorer.build_zini_trace", "zini_trace._build_premium_context",
                "zini_trace._find_premium_candidates", "zini_trace._apply_premium_candidate",
                "zini_trace._click_fallback_cell",
            ):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            for index in (0, len(moves) // 2, len(moves), 0, len(moves)):
                controller.go_to(index)
                self.assertEqual(controller.current_index, index)
                self.assertEqual(controller.cumulative_clicks,
                                 sum(move.clicks_added for move in moves[:index]))
                self.assertEqual(controller.revealed, frozenset(
                    cell for step in trace.steps[:index] for cell in step.newly_revealed
                ))
                self.assertEqual(controller.flagged_mines, frozenset(
                    cell for step in trace.steps[:index] for cell in step.newly_flagged
                ))
                self.assertEqual(controller.current_step,
                                 trace.steps[index - 1] if index else None)
                self.assertIs(controller.request_trace(), trace)
        safe = frozenset(
            (x, y) for y in range(snapshot.height) for x in range(snapshot.width)
            if (x, y) not in snapshot.mines
        )
        self.assertEqual(controller.revealed, safe)
        self.assertLessEqual(controller.flagged_mines, snapshot.mines)
        return controller

    def test_all_ten_frozen_v1_paths_preserve_652_moves_at_first_middle_and_end(self):
        self.assertEqual(len(GOLDEN), 10)
        self.assertEqual(sum(len(g["expected"]["moves"]) for g in GOLDEN.values()), 652)
        for name, golden in GOLDEN.items():
            with self.subTest(workload=name):
                snapshot = workload_snapshot(golden["inputs"]["board"])
                moves = tuple(ZiniMove(*entry) for entry in golden["expected"]["moves"])
                controller = self.check_playback(snapshot, moves)
                self.assertEqual(controller.clicks, golden["expected"]["clicks"])

    def test_historical_120_witness_is_replay_valid_without_fresh_search(self):
        snapshot = _expert_seed1003_snapshot()
        moves = tuple(ZiniMove(*entry) for entry in _EXPERT_SEED1003_120_TRACE)
        controller = self.check_playback(snapshot, moves)
        self.assertEqual((controller.clicks, controller.step_count), (120, 87))
        self.assertNotEqual(
            _EXPERT_SEED1003_120_TRACE,
            GOLDEN["advanced/expert1003/standard_seeded_chain_v1"]["expected"]["moves"],
        )

    def test_controller_never_calls_search_or_rng_and_trace_off_has_no_premium_work(self):
        snapshot = _expert_seed1003_snapshot()
        moves = tuple(ZiniMove(*entry) for entry in _EXPERT_SEED1003_120_TRACE)
        random_state = random.getstate()
        controller = ZiniExplorerController()
        with ExitStack() as stack:
            for target in (
                "random.Random.seed", "random.Random.random", "random.Random.getrandbits",
                "random.random", "random.choice", "random.sample", "random.randrange",
                "zini_calculator.calculate_g_zini",
                "zini_calculator.calculate_g_zini_min_ties_bounded",
                "zini_calculator.calculate_g_zini_neighborhood_beam_bounded",
                "zini_min_ties._MinTieSearch.find_best_moves",
                "zini_advanced._NeighborhoodBeamSearch.run",
            ):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            with patch("zini_trace._build_premium_context") as premium:
                controller.begin(1, snapshot, eligible=False)
                controller.receive(_payload(1, moves), expected_token=1)
                self.assertIsNone(controller.request_trace())
                controller.set_eligible(True)
                self.assertEqual(controller.state, "ready")
                self.assertEqual(controller.clicks, 120)
                premium.assert_not_called()
            self.assertIsNotNone(controller.request_trace(), controller.error)
            controller.go_to(40)
            controller.next()
            controller.previous()
        self.assertEqual(random.getstate(), random_state)

    def test_fresh_process_import_has_no_qt_ui_engine_replay_worker_dependency(self):
        code = """
import sys
import zini_explorer
for forbidden in ('PyQt5', 'ui_manager', 'core_engine', 'replay_player',
                  'replay_statistics', 'replay_loader', 'replay_recorder',
                  'zini_metric_worker', 'main'):
    assert not any(name == forbidden or name.startswith(forbidden + '.')
                   for name in sys.modules), forbidden
assert zini_explorer.ZiniExplorerController().state == 'unavailable'
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
