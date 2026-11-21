"""Controller playback API vs. unchanged logical API (E-C1, E-C6, E-C10).

One click-unit position is the only cursor. Logical calls keep their names and
meaning and are checked against the unchanged ZiniTracePlayer.
"""

import unittest
from unittest.mock import patch

from tests.test_zini_playback import (
    CENTER_RESULT, CENTER_SNAPSHOT, MULTI_RESULT, MULTI_SNAPSHOT,
)
from zini_calculator import ZiniMove
from zini_explorer import ZiniExplorerController
from zini_playback import ZiniPlaybackPlayer
from zini_trace import (
    ZiniTrace, ZiniTracePlayer, ZiniTraceSelection, ZiniTraceStep, build_zini_trace,
)


def payload(token, result):
    return {"token": token, "clicks": result.clicks, "moves": result.moves, "error": None}


def ready(snapshot=CENTER_SNAPSHOT, result=CENTER_RESULT, token=7):
    controller = ZiniExplorerController()
    controller.begin(token, snapshot, eligible=True)
    controller.receive(payload(token, result), expected_token=token)
    if controller.request_trace() is None:
        raise AssertionError(controller.error)
    return controller


def boundaries(trace):
    values = [0]
    for step in trace.steps:
        values.append(values[-1] + step.move.clicks_added)
    return values


class ControllerPlaybackTests(unittest.TestCase):
    def assert_logical_view(self, controller, index):
        reference = ZiniTracePlayer(controller.trace)
        reference.go_to(index)
        self.assertEqual(controller.current_index, index)
        self.assertEqual(controller.step_count, reference.step_count)
        self.assertEqual(controller.current_step, reference.current_step)
        self.assertEqual(controller.revealed, reference.revealed)
        self.assertEqual(controller.flagged_mines, reference.flagged_mines)
        self.assertEqual(controller.cumulative_clicks,
                         sum(move.clicks_added for move in controller.moves[:index]))

    def test_playback_and_logical_api_share_one_position(self):
        controller = ready(MULTI_SNAPSHOT, MULTI_RESULT)
        player = controller._player
        self.assertIsInstance(player, ZiniPlaybackPlayer)
        # The only mutable navigation state is the integer position.
        self.assertEqual(set(vars(player)), {"_trace", "_units", "_boundaries", "_position"})
        bounds = boundaries(controller.trace)
        self.assertEqual(bounds, [0, 1, 4])
        operations = (
            ("next_playback", ()), ("next_playback", ()), ("next", ()), ("previous_playback", ()),
            ("previous", ()), ("seek_playback", (2,)), ("go_to", (2,)), ("previous", ()),
            ("seek_playback", (3,)), ("next", ()), ("previous_playback", ()), ("go_to", (0,)),
        )
        for name, args in operations:
            with self.subTest(operation=name, args=args):
                getattr(controller, name)(*args)
                position = controller.playback_position
                self.assertEqual(player._position, position)
                floor = max(i for i, value in enumerate(bounds) if value <= position)
                self.assertEqual(controller.current_index, floor)
                self.assert_logical_view(controller, floor)

    def test_mid_move_logical_calls(self):
        # CENTER boundaries P = [0, 1, 3, 4, 5]; position 2 is mid-move 1.
        controller = ready()
        self.assertEqual(boundaries(controller.trace), [0, 1, 3, 4, 5])
        controller.seek_playback(2)
        for _ in range(2):  # Queries never move the position.
            self.assertEqual(controller.playback_position, 2)
            self.assert_logical_view(controller, 1)
            self.assertEqual(controller.current_step, controller.trace.steps[0])
            self.assertEqual(controller.cumulative_clicks, 1)
            self.assertEqual(controller.flagged_mines, frozenset())
            self.assertEqual(controller.playback_flagged_mines, frozenset({(1, 1)}))
        self.assertTrue(controller.next())
        self.assertEqual((controller.playback_position, controller.current_index), (3, 2))
        controller.seek_playback(2)
        self.assertTrue(controller.previous())
        self.assertEqual((controller.playback_position, controller.current_index), (0, 0))
        controller.seek_playback(2)
        self.assertTrue(controller.go_to(3))
        self.assertEqual((controller.playback_position, controller.current_index), (4, 3))
        controller.seek_playback(2)
        for index in (-1, 5, True, 1.0, None, "2"):
            with self.assertRaises(ValueError):
                controller.go_to(index)
            self.assertEqual(controller.playback_position, 2)
        # MULTI: positions 2 and 3 are inside the two-flag move.
        multi = ready(MULTI_SNAPSHOT, MULTI_RESULT)
        for position in (2, 3):
            multi.seek_playback(position)
            self.assert_logical_view(multi, 1)
            self.assertTrue(multi.next())
            self.assertEqual(multi.playback_position, 4)
            multi.seek_playback(position)
            self.assertTrue(multi.previous())
            self.assertEqual(multi.playback_position, 0)
        multi.seek_playback(4)
        self.assertFalse(multi.next())
        self.assertEqual(multi.playback_position, 4)

    def test_previous_inside_first_multi_unit_move_is_false(self):
        # Builder-validated traces always start with a one-unit move; this
        # hand-built trace checks the defined behavior anyway.
        move = ZiniMove("flag_chord", 1, 0, 0, 3)
        step = ZiniTraceStep(0, move, ((1, 0), (0, 1), (1, 1), (2, 1)),
                             ((0, 0), (2, 0)), 0, 1, ZiniTraceSelection.GREEDY)
        hand = ZiniTrace(MULTI_SNAPSHOT, 3, (step,))
        controller = ZiniExplorerController()
        controller.begin(9, MULTI_SNAPSHOT, eligible=True)
        controller.receive({"token": 9, "clicks": 3, "moves": (move,), "error": None}, expected_token=9)
        with patch("zini_explorer.build_zini_trace", return_value=hand):
            self.assertIs(controller.request_trace(), hand)
        controller.seek_playback(1)
        self.assertEqual(controller.current_index, 0)
        self.assertFalse(controller.previous())
        self.assertEqual(controller.playback_position, 1)
        self.assertTrue(controller.next())
        self.assertEqual(controller.playback_position, 3)

    def test_playback_api_hidden_when_unavailable_and_validates_input(self):
        fields = ("playback_position", "playback_count", "playback_unit", "playback_step")
        sets = ("playback_revealed", "playback_flagged_mines",
                "playback_newly_revealed", "playback_newly_flagged")
        controller = ZiniExplorerController()
        controller.begin(7, CENTER_SNAPSHOT, eligible=True)
        with patch("zini_explorer.build_zini_trace") as build:
            for stage in ("pending", "ready-unbuilt"):
                if stage == "ready-unbuilt":
                    controller.receive(payload(7, CENTER_RESULT), expected_token=7)
                for name in fields:
                    self.assertIsNone(getattr(controller, name), (stage, name))
                for name in sets:
                    self.assertEqual(getattr(controller, name), frozenset(), (stage, name))
                self.assertFalse(controller.seek_playback(0))
                self.assertFalse(controller.next_playback())
                self.assertFalse(controller.previous_playback())
            build.assert_not_called()
        controller.request_trace()
        controller.seek_playback(3)
        controller.set_eligible(False)
        for name in fields:
            self.assertIsNone(getattr(controller, name))
        for name in sets:
            self.assertEqual(getattr(controller, name), frozenset())
        self.assertFalse(controller.seek_playback(1))
        controller.set_eligible(True)
        self.assertEqual(controller.playback_position, 3)
        for value in (-1, 6, True, 1.0, None, "2"):
            with self.assertRaises(ValueError):
                controller.seek_playback(value)
            self.assertEqual(controller.playback_position, 3)
        self.assertTrue(controller.seek_playback(5))
        self.assertFalse(controller.next_playback())
        self.assertEqual(controller.playback_position, 5)
        controller.seek_playback(0)
        self.assertFalse(controller.previous_playback())
        for name in fields + sets:
            with self.assertRaises(AttributeError):
                setattr(controller, name, None)

    def test_begin_and_invalidate_drop_playback_position(self):
        controller = ready()
        controller.seek_playback(3)
        controller.invalidate()
        self.assertIsNone(controller.playback_position)
        self.assertIsNone(controller.playback_unit)
        controller = ready()
        controller.seek_playback(3)
        controller.begin(8, CENTER_SNAPSHOT, eligible=True)
        self.assertIsNone(controller.playback_position)
        controller.receive(payload(8, CENTER_RESULT), expected_token=8)
        self.assertIsNone(controller.playback_position)
        controller.request_trace()
        self.assertEqual(controller.playback_position, 0)

    def test_derivation_failure_is_a_cached_trace_error(self):
        controller = ZiniExplorerController()
        controller.begin(7, CENTER_SNAPSHOT, eligible=True)
        controller.receive(payload(7, CENTER_RESULT), expected_token=7)
        with patch("zini_explorer.ZiniPlaybackPlayer", side_effect=ValueError("units")) as player, \
                patch("zini_explorer.build_zini_trace", wraps=build_zini_trace) as build:
            self.assertIsNone(controller.request_trace())
            self.assertIsNone(controller.request_trace())
        build.assert_called_once()
        player.assert_called_once()
        self.assertEqual(controller.state, "error")
        self.assertIn("units", controller.trace_error)
        self.assertEqual(controller.clicks, 5)
        self.assertIsNone(controller.trace)
        self.assertIsNone(controller.playback_position)


if __name__ == "__main__":
    unittest.main()
