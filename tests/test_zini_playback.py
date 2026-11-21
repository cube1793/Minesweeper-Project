"""Click-unit playback derived from builder-validated ZiNi traces (E-C1..E-C5).

Expected states are recomputed here from trace steps and from the unchanged
ZiniTracePlayer, never from zini_playback itself.
"""

from dataclasses import replace
import unittest

from board_snapshot import BoardSnapshot
from tests.zini_fixtures import _EXPERT_SEED1003_120_TRACE, _expert_seed1003_snapshot
from tests.zini_golden_helpers import workload_snapshot
from tests.zini_v1_golden import GOLDEN
from zini_calculator import ZiniMove, ZiniResult
from zini_playback import (
    ZiniPlaybackPlayer, ZiniPlaybackUnit, ZiniPlaybackUnitKind, derive_playback_units,
)
from zini_trace import ZiniTrace, ZiniTracePlayer, ZiniTraceStep, ZiniTraceSelection, build_zini_trace

CLICK, FALLBACK, FLAG, CHORD = (
    ZiniPlaybackUnitKind.CLICK, ZiniPlaybackUnitKind.FALLBACK_CLICK,
    ZiniPlaybackUnitKind.FLAG, ZiniPlaybackUnitKind.CHORD,
)

CENTER_SNAPSHOT = BoardSnapshot(
    3, 3, 1, True, frozenset({(1, 1)}), ((1, 1, 1), (1, 0, 1), (1, 1, 1)),
)
CENTER_RESULT = ZiniResult(5, (
    ZiniMove("click", 1, 0, 2, 1),
    ZiniMove("flag_chord", 1, 0, 2, 2),
    ZiniMove("flag_chord", 0, 1, 1, 1),
    ZiniMove("flag_chord", 2, 1, 0, 1),
))
# Row 0: mine, 2, mine; row 1: 1, 2, 1. One flag_chord places two flags.
MULTI_SNAPSHOT = BoardSnapshot(
    3, 2, 2, True, frozenset({(0, 0), (2, 0)}), ((0, 2, 0), (1, 2, 1)),
)
MULTI_RESULT = ZiniResult(4, (
    ZiniMove("click", 1, 0, 0, 1),
    ZiniMove("flag_chord", 1, 0, 0, 3),
))
FALLBACK_SNAPSHOT = BoardSnapshot(3, 1, 1, True, frozenset({(1, 0)}), ((1, 0, 1),))
FALLBACK_RESULT = ZiniResult(2, (
    ZiniMove("fallback_click", 2, 0, None, 1),
    ZiniMove("fallback_click", 0, 0, None, 1),
))
EMPTY_SNAPSHOT = BoardSnapshot(1, 1, 1, True, frozenset({(0, 0)}), ((0,),))


def fixture_traces():
    traces = {
        "center": build_zini_trace(CENTER_SNAPSHOT, CENTER_RESULT),
        "multi": build_zini_trace(MULTI_SNAPSHOT, MULTI_RESULT),
        "fallback": build_zini_trace(FALLBACK_SNAPSHOT, FALLBACK_RESULT),
        "empty": build_zini_trace(EMPTY_SNAPSHOT, ZiniResult(0)),
    }
    return traces


def golden_traces():
    traces = {}
    for name, golden in GOLDEN.items():
        moves = tuple(ZiniMove(*entry) for entry in golden["expected"]["moves"])
        traces[name] = build_zini_trace(
            workload_snapshot(golden["inputs"]["board"]),
            ZiniResult(golden["expected"]["clicks"], moves),
        )
    moves = tuple(ZiniMove(*entry) for entry in _EXPERT_SEED1003_120_TRACE)
    traces["witness120"] = build_zini_trace(
        _expert_seed1003_snapshot(), ZiniResult(sum(m.clicks_added for m in moves), moves),
    )
    return traces


def expected_state(trace, position):
    """Independent (revealed, flags, unit-highlights) for a click position."""
    revealed, flags, used = set(), set(), 0
    for step in trace.steps:
        cost = step.move.clicks_added
        if used + cost <= position:
            revealed.update(step.newly_revealed)
            flags.update(step.newly_flagged)
            used += cost
            continue
        flags.update(step.newly_flagged[:position - used])
        break
    return frozenset(revealed), frozenset(flags)


class PlaybackUnitTests(unittest.TestCase):
    def test_units_for_click_fallback_and_flag_chord_with_zero_one_and_many_flags(self):
        traces = fixture_traces()
        expected = {
            "center": [
                (1, 0, CLICK, (1, 0), 0, 0),
                (2, 1, FLAG, (1, 1), 1, 1),
                (3, 1, CHORD, (1, 0), 0, 1),
                (4, 2, CHORD, (0, 1), 0, 0),   # flag_chord with no new flag
                (5, 3, CHORD, (2, 1), 0, 0),
            ],
            "multi": [
                (1, 0, CLICK, (1, 0), 0, 0),
                (2, 1, FLAG, (0, 0), 1, 2),
                (3, 1, FLAG, (2, 0), 2, 2),
                (4, 1, CHORD, (1, 0), 0, 2),
            ],
            "fallback": [
                (1, 0, FALLBACK, (2, 0), 0, 0),
                (2, 1, FALLBACK, (0, 0), 0, 0),
            ],
        }
        for name, rows in expected.items():
            with self.subTest(name=name):
                units = derive_playback_units(traces[name])
                self.assertEqual(units, tuple(ZiniPlaybackUnit(*row) for row in rows))
        # The zero-flag chord at (0, 1) opens nothing new but is still a unit.
        center = traces["center"]
        self.assertEqual(center.steps[2].newly_flagged, ())
        self.assertTrue(all(isinstance(unit.kind, ZiniPlaybackUnitKind)
                            for unit in derive_playback_units(center)))

    def test_empty_trace_has_no_units(self):
        trace = fixture_traces()["empty"]
        self.assertEqual(derive_playback_units(trace), ())
        player = ZiniPlaybackPlayer(trace)
        self.assertEqual((player.playback_count, player.playback_position, player.step_count), (0, 0, 0))
        self.assertIsNone(player.playback_unit)
        self.assertFalse(player.next_playback())
        self.assertFalse(player.previous_playback())
        self.assertFalse(player.next())
        self.assertFalse(player.previous())

    def test_golden_and_witness_units_match_move_kinds_and_flag_counts(self):
        traces = golden_traces()
        self.assertEqual(len(traces), 11)
        total_moves = 0
        for name, trace in traces.items():
            with self.subTest(name=name):
                units = derive_playback_units(trace)
                total_moves += len(trace.steps)
                by_step = {}
                for unit in units:
                    by_step.setdefault(unit.step_index, []).append(unit)
                self.assertEqual(sorted(by_step), list(range(len(trace.steps))))
                for step in trace.steps:
                    step_units = by_step[step.step_index]
                    kinds = [unit.kind for unit in step_units]
                    if step.move.action == "click":
                        self.assertEqual(kinds, [CLICK])
                    elif step.move.action == "fallback_click":
                        self.assertEqual(kinds, [FALLBACK])
                    else:
                        n = len(step.newly_flagged)
                        self.assertEqual(kinds, [FLAG] * n + [CHORD])
                        self.assertEqual([u.target for u in step_units[:n]], list(step.newly_flagged))
                        self.assertEqual([u.flag_number for u in step_units[:n]], list(range(1, n + 1)))
                        self.assertTrue(all(u.flag_count == n for u in step_units))
                    self.assertEqual(step_units[-1].target, (step.move.x, step.move.y))
                    self.assertEqual(len(step_units), step.move.clicks_added)
                self.assertEqual([u.position for u in units], list(range(1, len(units) + 1)))
        self.assertEqual(total_moves, 652 + 87)

    def test_inconsistent_trace_is_rejected(self):
        trace = fixture_traces()["center"]
        step = trace.steps[1]
        bad_cost = replace(trace, steps=(trace.steps[0], replace(step, move=replace(step.move, clicks_added=3)),
                                         *trace.steps[2:]), total_clicks=6)
        bad_click = replace(trace, steps=(replace(trace.steps[0], move=replace(trace.steps[0].move, clicks_added=2)),
                                          *trace.steps[1:]), total_clicks=6)
        flagged_click = replace(trace, steps=(replace(trace.steps[0], newly_flagged=((1, 1),)),
                                              *trace.steps[1:]))
        bad_total = replace(trace, total_clicks=4)
        unknown = replace(trace, steps=(replace(trace.steps[0], move=replace(trace.steps[0].move, action="open")),
                                        *trace.steps[1:]))
        for name, value in (("flag_chord cost", bad_cost), ("click cost", bad_click),
                            ("click with flag", flagged_click), ("total", bad_total),
                            ("action", unknown)):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    derive_playback_units(value)
                with self.assertRaises(ValueError):
                    ZiniPlaybackPlayer(value)

    def test_flags_follow_trace_newly_flagged_row_major_order(self):
        found = []
        for name, trace in golden_traces().items():
            for step in trace.steps:
                flags = step.newly_flagged
                self.assertEqual(list(flags), sorted(flags, key=lambda c: (c[1], c[0])))
                if len(flags) > 1 and list(flags) != sorted(flags):
                    found.append((name, step))
        # At least one move whose (y, x) order differs from plain (x, y) order.
        self.assertTrue(found)
        name, step = found[0]
        trace = golden_traces()[name]
        targets = [unit.target for unit in derive_playback_units(trace)
                   if unit.step_index == step.step_index and unit.kind == FLAG]
        self.assertEqual(targets, list(step.newly_flagged))
        self.assertNotEqual(targets, sorted(targets))
        multi = [unit.target for unit in derive_playback_units(fixture_traces()["multi"])
                 if unit.kind == FLAG]
        self.assertEqual(multi, [(0, 0), (2, 0)])

    def test_intermediate_flag_and_chord_states_and_highlights(self):
        traces = {**fixture_traces(), **golden_traces()}
        for name, trace in traces.items():
            with self.subTest(name=name):
                player = ZiniPlaybackPlayer(trace)
                units = player.units
                for position in range(player.playback_count + 1):
                    player.seek_playback(position)
                    revealed, flags = expected_state(trace, position)
                    self.assertEqual(player.playback_revealed, revealed)
                    self.assertEqual(player.playback_flagged_mines, flags)
                    unit = units[position - 1] if position else None
                    self.assertEqual(player.playback_unit, unit)
                    if unit is None:
                        self.assertIsNone(player.playback_step)
                        self.assertEqual(player.playback_newly_revealed, frozenset())
                        self.assertEqual(player.playback_newly_flagged, frozenset())
                        continue
                    step = trace.steps[unit.step_index]
                    self.assertIs(player.playback_step, step)
                    if unit.kind == FLAG:
                        # Before-state plus the first k flags; reveals unchanged.
                        before_revealed, before_flags = expected_state(trace, position - unit.flag_number)
                        self.assertEqual(player.playback_revealed, before_revealed)
                        self.assertEqual(player.playback_flagged_mines,
                                         before_flags | frozenset(step.newly_flagged[:unit.flag_number]))
                        self.assertEqual(player.playback_newly_flagged, frozenset({unit.target}))
                        self.assertEqual(player.playback_newly_revealed, frozenset())
                    else:
                        self.assertEqual(player.playback_newly_revealed, frozenset(step.newly_revealed))
                        self.assertEqual(player.playback_newly_flagged, frozenset())

    def test_logical_boundaries_match_trace_player_on_all_paths(self):
        traces = {**fixture_traces(), **golden_traces()}
        for name, trace in traces.items():
            with self.subTest(name=name):
                player = ZiniPlaybackPlayer(trace)
                reference = ZiniTracePlayer(trace)
                boundary = 0
                for index in range(len(trace.steps) + 1):
                    if index:
                        boundary += trace.steps[index - 1].move.clicks_added
                    reference.go_to(index)
                    player.seek_playback(boundary)
                    self.assertEqual(player.playback_revealed, reference.revealed)
                    self.assertEqual(player.playback_flagged_mines, reference.flagged_mines)
                    self.assertEqual(player.current_index, index)
                    self.assertEqual(player.revealed, reference.revealed)
                    self.assertEqual(player.flagged_mines, reference.flagged_mines)
                    self.assertEqual(player.current_step, reference.current_step)
                self.assertEqual(boundary, trace.total_clicks)

    def test_unit_count_equals_total_clicks_and_position_is_cumulative_clicks(self):
        traces = {**fixture_traces(), **golden_traces()}
        for name, trace in traces.items():
            with self.subTest(name=name):
                player = ZiniPlaybackPlayer(trace)
                self.assertEqual(player.playback_count, trace.total_clicks)
                for position in range(trace.total_clicks + 1):
                    player.seek_playback(position)
                    done = player.current_index
                    clicks = (sum(step.move.clicks_added for step in trace.steps[:done])
                              + len(player.playback_flagged_mines - player.flagged_mines))
                    self.assertEqual(player.playback_position, position)
                    self.assertEqual(clicks, position)

    def test_playback_never_reads_snapshot_or_answer_data(self):
        class Forbidden:
            def __getattr__(self, name):
                raise AssertionError(f"snapshot.{name} read by playback")

        for name, trace in {**fixture_traces(), **golden_traces()}.items():
            with self.subTest(name=name):
                blind = replace(trace, snapshot=Forbidden())
                player = ZiniPlaybackPlayer(blind)
                for position in range(player.playback_count + 1):
                    player.seek_playback(position)
                    (player.playback_revealed, player.playback_flagged_mines,
                     player.playback_newly_revealed, player.playback_newly_flagged,
                     player.playback_unit, player.playback_step, player.current_step)
                player.go_to(0)
                while player.next():
                    pass
                while player.previous():
                    pass


class HandBuiltTraceTests(unittest.TestCase):
    """Synthetic (not builder-produced) trace for an otherwise unreachable case."""

    def test_flag_chord_first_move_is_derivable_from_trace_fields_alone(self):
        step = ZiniTraceStep(0, ZiniMove("flag_chord", 1, 0, 0, 3), ((1, 0),),
                             ((0, 0), (2, 0)), 0, 1, ZiniTraceSelection.GREEDY)
        trace = ZiniTrace(MULTI_SNAPSHOT, 3, (step,))
        player = ZiniPlaybackPlayer(trace)
        self.assertEqual([unit.kind for unit in player.units], [FLAG, FLAG, CHORD])


if __name__ == "__main__":
    unittest.main()
