import random
import unittest

from board_analyzer import CellClass
from board_snapshot import BoardSnapshot
from zini_core import (
    _PremiumCandidate,
    _ZiniBoardState,
    _apply_next_g_zini_move,
    _apply_premium_candidate,
    _build_premium_context,
    _calculate_premium,
    _click_covered_candidate,
    _click_fallback_cell,
    _copy_zini_state,
    _extract_static_3bv_units,
    _find_fallback_click_targets,
    _find_premium_candidates,
    _flag_and_chord_uncovered_candidate,
    _select_best_premium_candidate,
    _select_fallback_click_target,
    _zini_state_key,
)
from tests.zini_fixtures import (
    _EXPERT_SEED1003_120_TRACE,
    _advanced_search_snapshot,
    _expert_seed1003_snapshot,
)
from tests.zini_golden_helpers import workload_snapshot
from tests.zini_v1_golden import GOLDEN


def _reference_premium_candidates(state, context):
    """Express the pre-lookup Premium scan without production Premium helpers."""
    snapshot = state.snapshot
    candidates = []
    for y in range(snapshot.height):
        for x in range(snapshot.width):
            coord = (x, y)
            if coord in snapshot.mines or snapshot.adjacent[y][x] == 0:
                continue
            openings = set()
            isolated = set()
            unflagged_mines = 0
            for ny in range(max(0, y - 1), min(snapshot.height, y + 2)):
                for nx in range(max(0, x - 1), min(snapshot.width, x + 2)):
                    neighbor = (nx, ny)
                    if neighbor == coord:
                        continue
                    if neighbor in snapshot.mines:
                        unflagged_mines += neighbor not in state.flagged_mines
                        continue
                    if neighbor in state.revealed:
                        continue
                    cell_class = context.analysis.cell_class[ny][nx]
                    if cell_class == CellClass.OPENING:
                        opening_id = context.analysis.opening_id[ny][nx]
                        if opening_id in context.opening_units_by_id:
                            openings.add(opening_id)
                    elif (
                        cell_class == CellClass.ISOLATED
                        and neighbor in context.isolated_cells
                    ):
                        isolated.add(neighbor)
            premium = len(openings) + len(isolated) - unflagged_mines - 1
            if (
                coord not in state.revealed
                and context.analysis.cell_class[y][x] == CellClass.BORDER
            ):
                premium -= 1
            candidates.append(_PremiumCandidate(coord=coord, premium=premium))
    return tuple(candidates)


class PremiumLookupEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boards = {
            name: workload_snapshot(name)
            for name in ("board_c", "expert1003", "general0", "general42")
        }
        cls.boards.update({
            "small_empty": BoardSnapshot(
                width=1, height=1, num_mines=0, mines_placed=True,
                mines=frozenset(), adjacent=((0,),),
            ),
            "small_corner": BoardSnapshot(
                width=3, height=3, num_mines=1, mines_placed=True,
                mines=frozenset({(0, 0)}),
                adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
            ),
            "small_center": BoardSnapshot(
                width=3, height=3, num_mines=1, mines_placed=True,
                mines=frozenset({(1, 1)}),
                adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
            ),
            "small_mixed": _advanced_search_snapshot(),
        })

    def assert_candidates_match_reference(self, state, context):
        expected = _reference_premium_candidates(state, context)
        actual = _find_premium_candidates(state, context)
        self.assertIs(type(actual), tuple)
        for candidate in actual:
            self.assertIs(type(candidate), _PremiumCandidate)
        # Tuple equality protects coordinates, Premium values, and row-major
        # order, including candidates that are already revealed.
        self.assertEqual(actual, expected)
        self.assertEqual(
            tuple(_calculate_premium(state, item.coord, context) for item in expected),
            tuple(item.premium for item in expected),
        )
        return expected

    def test_lookup_matches_reference_on_all_golden_trajectory_states(self):
        for name, golden in GOLDEN.items():
            snapshot = self.boards[golden["inputs"]["board"]]
            context = _build_premium_context(snapshot)
            state = _ZiniBoardState.create(snapshot)
            for step, expected in enumerate(golden["expected"]["moves"]):
                with self.subTest(workload=name, step=step):
                    self.assert_candidates_match_reference(state, context)
                    action, x, y, premium, clicks_added = expected
                    if action == "fallback_click":
                        move = _click_fallback_cell(state, (x, y), context)
                    else:
                        move = _apply_premium_candidate(
                            state, _PremiumCandidate((x, y), premium), context,
                        )
                    self.assertEqual(
                        (move.action, move.x, move.y, move.premium, move.clicks_added),
                        expected,
                    )
            with self.subTest(workload=name, step="solved"):
                self.assertTrue(state.all_safe_cells_revealed())
                self.assert_candidates_match_reference(state, context)

    def test_lookup_matches_reference_on_small_board_trajectories(self):
        for name, snapshot in self.boards.items():
            if not name.startswith("small_"):
                continue
            context = _build_premium_context(snapshot)
            state = _ZiniBoardState.create(snapshot)
            for step in range(snapshot.width * snapshot.height * 4):
                with self.subTest(board=name, step=step):
                    self.assert_candidates_match_reference(state, context)
                    if state.all_safe_cells_revealed():
                        break
                    self.assertIsNotNone(_apply_next_g_zini_move(state, context))
            else:
                self.fail(f"Small-board trajectory did not finish: {name}")

    def test_lookup_matches_reference_after_seeded_direct_state_mutations(self):
        rng = random.Random(1003)
        for name, snapshot in self.boards.items():
            context = _build_premium_context(snapshot)
            state = _ZiniBoardState.create(snapshot)
            cells = [
                (x, y)
                for y in range(snapshot.height)
                for x in range(snapshot.width)
            ]
            for case in range(24):
                # Replace both sets so coverage can shrink as well as grow.
                # Include arbitrary mine/safe memberships: Premium only reads
                # the relevant neighbor memberships from these public sets.
                state.revealed = {coord for coord in cells if rng.random() < 0.5}
                state.flagged_mines = {
                    coord for coord in cells if rng.random() < 0.5
                }
                with self.subTest(board=name, case=case):
                    self.assert_candidates_match_reference(state, context)

    def test_lookup_counts_only_unrevealed_adjacent_zeros_in_partial_opening(self):
        snapshot = self.boards["small_corner"]
        context = _build_premium_context(snapshot)
        state = _ZiniBoardState.create(snapshot)
        coord = (1, 0)
        for revealed, expected in (
            (set(), -2),
            ({(2, 0)}, -2),
            ({(2, 0), (2, 1)}, -3),
            ({(2, 1)}, -2),
            (set(), -2),
        ):
            state.revealed.clear()
            state.revealed.update(revealed)
            with self.subTest(revealed=revealed):
                self.assert_candidates_match_reference(state, context)
                self.assertEqual(_calculate_premium(state, coord, context), expected)

    def test_four_field_manual_contexts_preserve_reduced_memberships(self):
        snapshot = self.boards["board_c"]
        built = _build_premium_context(snapshot)
        contexts = (
            type(built)(
                built.analysis, built.units,
                built.opening_units_by_id, built.isolated_cells,
            ),
            type(built)(
                analysis=built.analysis, units=built.units,
                opening_units_by_id={}, isolated_cells=built.isolated_cells,
            ),
            type(built)(
                analysis=built.analysis, units=built.units,
                opening_units_by_id=built.opening_units_by_id,
                isolated_cells=frozenset(),
            ),
            type(built)(
                analysis=built.analysis, units=built.units,
                opening_units_by_id={}, isolated_cells=frozenset(),
            ),
        )
        state = _ZiniBoardState.create(snapshot)
        for revealed in (set(), {(0, 0), (2, 3), (3, 3)}, set()):
            state.revealed.clear()
            state.revealed.update(revealed)
            state.flagged_mines.symmetric_difference_update({(1, 0)})
            for index, context in enumerate(contexts):
                with self.subTest(context=index, revealed=revealed):
                    self.assert_candidates_match_reference(state, context)


def _reference_all_safe_cells_revealed(state):
    """Keep the original row-major membership predicate independent of caches."""
    snapshot = state.snapshot
    return all(
        (x, y) in state.revealed
        for y in range(snapshot.height)
        for x in range(snapshot.width)
        if (x, y) not in snapshot.mines
    )


class SolvedCheckEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = BoardSnapshot(
            width=2, height=2, num_mines=1, mines_placed=True,
            mines=frozenset({(1, 1)}), adjacent=((1, 1), (1, 0)),
        )

    def assert_solved_matches_reference(self, state):
        self.assertEqual(
            state.all_safe_cells_revealed(),
            _reference_all_safe_cells_revealed(state),
        )

    def test_matches_reference_for_every_small_board_reveal_subset(self):
        boards = (
            self.snapshot,
            BoardSnapshot(0, 0, 0, True, frozenset(), ()),
            BoardSnapshot(0, 2, 0, True, frozenset(), ((), ())),
            BoardSnapshot(2, 0, 0, True, frozenset(), ()),
            BoardSnapshot(1, 1, 1, True, frozenset({(0, 0)}), ((0,),)),
            BoardSnapshot(2, 2, 0, True, frozenset(), ((0, 0), (0, 0))),
            BoardSnapshot(
                3, 3, 1, True, frozenset({(1, 1)}),
                ((1, 1, 1), (1, 0, 1), (1, 1, 1)),
            ),
        )
        for board_index, snapshot in enumerate(boards):
            state = _ZiniBoardState.create(snapshot)
            cells = [
                (x, y)
                for y in range(snapshot.height)
                for x in range(snapshot.width)
            ]
            # Include mines in the exhaustive domain, even for abnormal states.
            for mask in range(1 << len(cells)):
                state.revealed = {
                    coord for index, coord in enumerate(cells)
                    if mask & (1 << index)
                }
                with self.subTest(board=board_index, revealed_mask=mask):
                    self.assert_solved_matches_reference(state)

    def test_mines_and_extra_cells_do_not_replace_missing_safe_cells(self):
        state = _ZiniBoardState.create(self.snapshot)
        safe_cells = {(0, 0), (1, 0), (0, 1)}
        state.revealed = (safe_cells - {(0, 1)}) | {(1, 1)}
        self.assertEqual(len(state.revealed), len(safe_cells))
        self.assertFalse(state.all_safe_cells_revealed())
        self.assert_solved_matches_reference(state)

        state.revealed.update({(-1, -1), (2, 2)})
        self.assertFalse(state.all_safe_cells_revealed())
        self.assert_solved_matches_reference(state)
        state.revealed.add((0, 1))
        self.assertTrue(state.all_safe_cells_revealed())
        self.assert_solved_matches_reference(state)

    def test_matches_reference_after_replacing_and_clearing_revealed(self):
        state = _ZiniBoardState.create(self.snapshot)
        state.revealed.update({(0, 0), (1, 0), (0, 1)})
        self.assert_solved_matches_reference(state)
        state.revealed.remove((1, 0))
        self.assert_solved_matches_reference(state)
        state.revealed.clear()
        self.assert_solved_matches_reference(state)
        state.revealed = {(0, 0), (1, 0), (0, 1), (1, 1)}
        self.assert_solved_matches_reference(state)
        state.revealed = {(1, 1)}
        self.assert_solved_matches_reference(state)

    def test_matches_reference_on_all_expert_golden_trajectory_states(self):
        snapshot = _expert_seed1003_snapshot()
        context = _build_premium_context(snapshot)
        for name, golden in GOLDEN.items():
            if golden["inputs"]["board"] != "expert1003":
                continue
            state = _ZiniBoardState.create(snapshot)
            for step, expected in enumerate(golden["expected"]["moves"]):
                with self.subTest(workload=name, step=step):
                    self.assert_solved_matches_reference(state)
                    action, x, y, premium, _ = expected
                    if action == "fallback_click":
                        _click_fallback_cell(state, (x, y), context)
                    else:
                        _apply_premium_candidate(
                            state, _PremiumCandidate((x, y), premium), context,
                        )
            with self.subTest(workload=name, step="solved"):
                self.assert_solved_matches_reference(state)
                self.assertTrue(state.all_safe_cells_revealed())

    def test_three_argument_state_and_copy_share_only_immutable_safe_cells(self):
        state = _ZiniBoardState(self.snapshot, {(0, 0)}, {(1, 1)})
        copied = _copy_zini_state(state)
        self.assertEqual(_zini_state_key(copied), _zini_state_key(state))
        self.assertIsInstance(state._safe_cell_set, frozenset)
        self.assertIs(copied._safe_cell_set, state._safe_cell_set)
        self.assertIsNot(copied.revealed, state.revealed)
        self.assertIsNot(copied.flagged_mines, state.flagged_mines)
        self.assert_solved_matches_reference(state)
        self.assert_solved_matches_reference(copied)
        copied.revealed.update({(1, 0), (0, 1)})
        copied.flagged_mines.clear()
        self.assertTrue(copied.all_safe_cells_revealed())
        self.assertFalse(state.all_safe_cells_revealed())
        self.assertEqual(state.revealed, {(0, 0)})
        self.assertEqual(state.flagged_mines, {(1, 1)})


class ZiniCoreTests(unittest.TestCase):
    def test_copy_zini_state_preserves_key_without_sharing_mutable_sets(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        state.flag_mine((1, 0))

        copied = _copy_zini_state(state)

        self.assertEqual(_zini_state_key(copied), _zini_state_key(state))
        self.assertIsNot(copied.revealed, state.revealed)
        self.assertIsNot(copied.flagged_mines, state.flagged_mines)

    def test_apply_premium_candidate_preserves_covered_then_revealed_routing(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        candidate = _PremiumCandidate(coord=(0, 0), premium=0)

        click = _apply_premium_candidate(state, candidate, context)
        flag_chord = _apply_premium_candidate(state, candidate, context)

        self.assertEqual(click.action, "click")
        self.assertEqual(click.clicks_added, 1)
        self.assertEqual(flag_chord.action, "flag_chord")
        self.assertEqual(flag_chord.clicks_added, 2)
        self.assertEqual(state.revealed, {(0, 0)})
        self.assertEqual(state.flagged_mines, {(1, 0)})

    def test_expert_seed1003_replays_known_120_trace(self):
        snapshot = _expert_seed1003_snapshot()
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        replayed_moves = []

        self.assertEqual(snapshot.width, 30)
        self.assertEqual(snapshot.height, 16)
        self.assertEqual(len(snapshot.mines), 99)
        self.assertEqual(len(_EXPERT_SEED1003_120_TRACE), 87)

        for step, expected in enumerate(_EXPERT_SEED1003_120_TRACE, start=1):
            with self.subTest(step=step, expected=expected):
                action, x, y, premium, clicks_added = expected
                coord = (x, y)
                candidates = _find_premium_candidates(state, context)
                best_premium = max(
                    (candidate.premium for candidate in candidates),
                    default=None,
                )
                before_revealed = set(state.revealed)
                before_flagged = set(state.flagged_mines)

                if action == "fallback_click":
                    self.assertTrue(
                        best_premium is None or best_premium < 0
                    )
                    # This intentionally locks the known trace to the current
                    # unresolved-static-3BV fallback policy as well as replay
                    # move validity.
                    self.assertEqual(
                        _select_fallback_click_target(state, context),
                        coord,
                    )
                    self.assertNotIn(coord, snapshot.mines)
                    self.assertNotIn(coord, state.revealed)
                    self.assertIsNone(premium)
                    self.assertEqual(clicks_added, 1)

                    move = _click_fallback_cell(state, coord, context)
                else:
                    matching_candidates = [
                        candidate
                        for candidate in candidates
                        if candidate.coord == coord
                    ]
                    self.assertEqual(len(matching_candidates), 1)
                    candidate = matching_candidates[0]

                    self.assertEqual(candidate.premium, premium)
                    self.assertNotIn(coord, snapshot.mines)
                    self.assertGreater(snapshot.adjacent[y][x], 0)

                    if action == "click":
                        self.assertNotIn(coord, state.revealed)
                        self.assertEqual(clicks_added, 1)
                        move = _click_covered_candidate(state, candidate)
                    else:
                        self.assertEqual(action, "flag_chord")
                        self.assertIn(coord, state.revealed)
                        flags_before = len(state.flagged_mines)

                        move = _flag_and_chord_uncovered_candidate(
                            state,
                            candidate,
                            context,
                        )

                        new_flags = len(state.flagged_mines) - flags_before
                        self.assertEqual(clicks_added, new_flags + 1)

                self.assertEqual(
                    (
                        move.action,
                        move.x,
                        move.y,
                        move.premium,
                        move.clicks_added,
                    ),
                    expected,
                )
                self.assertTrue(
                    state.revealed != before_revealed
                    or state.flagged_mines != before_flagged
                )
                self.assertTrue(state.flagged_mines <= snapshot.mines)
                replayed_moves.append(move)

        self.assertEqual(len(replayed_moves), 87)
        self.assertEqual(
            sum(move.clicks_added for move in replayed_moves),
            120,
        )
        self.assertEqual(len(state.revealed), 381)
        self.assertTrue(state.all_safe_cells_revealed())
        self.assertEqual(len(state.flagged_mines), 33)
        self.assertTrue(state.flagged_mines <= snapshot.mines)

    def test_static_units_empty_board_has_one_opening(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )

        units = _extract_static_3bv_units(snapshot)

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].kind, "opening")
        self.assertEqual(units[0].representative, (0, 0))
        self.assertEqual(units[0].cells, frozenset({(0, 0)}))

    def test_static_units_center_mine_has_eight_isolated_numbers(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )

        units = _extract_static_3bv_units(snapshot)

        self.assertEqual(len(units), 8)
        self.assertTrue(all(unit.kind == "isolated" for unit in units))
        self.assertEqual(
            [unit.representative for unit in units],
            [
                (0, 0),
                (1, 0),
                (2, 0),
                (0, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            ],
        )

    def test_static_units_corner_mine_has_one_opening_represented_top_left(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )

        units = _extract_static_3bv_units(snapshot)

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].kind, "opening")
        self.assertEqual(units[0].representative, (2, 0))
        self.assertEqual(
            units[0].cells,
            frozenset({(2, 0), (2, 1), (0, 2), (1, 2), (2, 2)}),
        )
        self.assertEqual(units[0].opening_id, 0)

    def test_dynamic_state_reveals_single_cell_opening_and_completes_board(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        unit = _extract_static_3bv_units(snapshot)[0]
        state = _ZiniBoardState.create(snapshot)

        state.reveal_unit(unit)

        self.assertEqual(state.revealed, {(0, 0)})
        self.assertTrue(state.all_safe_cells_revealed())

    def test_dynamic_state_reveals_opening_zero_cells_and_border_ring(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        unit = _extract_static_3bv_units(snapshot)[0]
        state = _ZiniBoardState.create(snapshot)

        state.reveal_unit(unit)

        self.assertEqual(
            state.revealed,
            {
                (1, 0),
                (2, 0),
                (0, 1),
                (1, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            },
        )
        self.assertTrue(state.all_safe_cells_revealed())

    def test_dynamic_state_reveals_isolated_number_only(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        unit = _extract_static_3bv_units(snapshot)[0]
        state = _ZiniBoardState.create(snapshot)

        state.reveal_unit(unit)

        self.assertEqual(unit.kind, "isolated")
        self.assertEqual(unit.representative, (0, 0))
        self.assertEqual(state.revealed, {(0, 0)})
        self.assertFalse(state.all_safe_cells_revealed())

    def test_dynamic_state_flags_mine_coordinate(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)

        state.flag_mine((1, 0))

        self.assertEqual(state.flagged_mines, {(1, 0)})

    def test_dynamic_state_rejects_non_mine_flag(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)

        with self.assertRaises(ValueError):
            state.flag_mine((0, 0))

    def test_premium_counts_adjacent_unflagged_mines_without_counting_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        # Adjacent covered isolated cells: (1, 0), (0, 1). The covered
        # isolated candidate (0, 0) is not adjacent to itself and is not
        # counted. Adjacent unflagged mines: (1, 1).
        self.assertEqual(premium, 0)

    def test_premium_ignores_already_flagged_adjacent_mines(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.flag_mine((1, 1))
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        self.assertEqual(premium, 1)

    def test_premium_deduplicates_multiple_adjacent_zero_cells(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (1, 1), context)

        # Candidate (1, 1) touches several zero cells from the same opening,
        # two covered BORDER numbers, and one unflagged mine. The opening is
        # counted once, BORDER numbers are not independent 3BV, and the covered
        # BORDER candidate receives the non-3BV penalty.
        self.assertEqual(premium, -2)

    def test_premium_excludes_border_only_opening_contact(self):
        snapshot = BoardSnapshot(
            width=4,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 1)}),
            adjacent=((1, 1, 0, 0), (0, 1, 0, 0), (1, 1, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        # Candidate (0, 0) touches only BORDER numbers from the opening at its
        # east side, not any zero cell from that opening. The opening must not
        # be counted as adjacent covered 3BV. The negative value is intentional
        # and must not be clamped to zero.
        self.assertEqual(premium, -2)

    def test_premium_applies_covered_border_penalty_only_while_covered(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        covered_premium = _calculate_premium(state, (1, 1), context)
        state.revealed.add((1, 1))
        uncovered_premium = _calculate_premium(state, (1, 1), context)

        self.assertEqual(covered_premium, -2)
        self.assertEqual(uncovered_premium, -1)

    def test_premium_excludes_already_revealed_adjacent_3bv(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        context = _build_premium_context(snapshot)

        premium = _calculate_premium(state, (0, 0), context)

        # Only (0, 1) remains as adjacent covered 3BV. The adjacent mine is
        # still unflagged, so the Premium is negative and remains unclamped.
        self.assertEqual(premium, -1)

    def test_select_best_candidate_uses_highest_premium_and_top_left_tie_break(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (1, 0))
        self.assertEqual(candidate.premium, 2)

    def test_select_best_candidate_uses_flagged_mines_in_premium(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.flag_mine((1, 1))
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (1, 0))
        self.assertEqual(candidate.premium, 3)

    def test_select_best_candidate_tie_breaks_by_y_then_x(self):
        snapshot = BoardSnapshot(
            width=2,
            height=2,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1), (1, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (0, 0))
        self.assertEqual(candidate.premium, 0)

    def test_find_premium_candidates_excludes_covered_zero_cells(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidates = _find_premium_candidates(state, context)

        self.assertEqual(
            {candidate.coord for candidate in candidates},
            {(1, 0), (0, 1), (1, 1)},
        )

    def test_select_best_candidate_allows_negative_premium(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        candidate = _select_best_premium_candidate(state, context)

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.coord, (0, 0))
        self.assertEqual(candidate.premium, -2)

    def test_select_best_candidate_returns_none_when_no_number_candidates_exist(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        self.assertEqual(_find_premium_candidates(state, context), ())
        self.assertIsNone(_select_best_premium_candidate(state, context))

    def test_select_best_candidate_returns_none_when_board_is_solved(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.update(
            (x, y)
            for y in range(snapshot.height)
            for x in range(snapshot.width)
            if (x, y) not in snapshot.mines
        )
        context = _build_premium_context(snapshot)

        self.assertIsNone(_select_best_premium_candidate(state, context))

    def test_click_covered_candidate_reveals_isolated_number_only(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        candidate = _select_best_premium_candidate(state, context)

        move = _click_covered_candidate(state, candidate)

        self.assertEqual(state.revealed, {candidate.coord})
        self.assertEqual(move.action, "click")
        self.assertEqual((move.x, move.y), candidate.coord)
        self.assertEqual(move.premium, candidate.premium)
        self.assertEqual(move.clicks_added, 1)

    def test_click_covered_candidate_reveals_border_number_only(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        candidate = next(
            candidate
            for candidate in _find_premium_candidates(state, context)
            if candidate.coord == (1, 1)
        )

        move = _click_covered_candidate(state, candidate)

        self.assertEqual(state.revealed, {(1, 1)})
        self.assertTrue(
            {(2, 0), (2, 1), (0, 2), (1, 2), (2, 2)}.isdisjoint(
                state.revealed
            )
        )
        self.assertEqual(move.action, "click")
        self.assertEqual((move.x, move.y), (1, 1))
        self.assertEqual(move.premium, candidate.premium)
        self.assertEqual(move.clicks_added, 1)

    def test_click_covered_candidate_rejects_already_revealed_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        candidate = _select_best_premium_candidate(state, context)
        state.revealed.add(candidate.coord)

        with self.assertRaises(ValueError):
            _click_covered_candidate(state, candidate)

    def test_click_covered_candidate_rejects_mine_coordinate(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        candidate = _PremiumCandidate(coord=(1, 0), premium=0)

        with self.assertRaises(ValueError):
            _click_covered_candidate(state, candidate)

    def test_click_covered_candidate_rejects_zero_cell(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        candidate = _PremiumCandidate(coord=(0, 0), premium=0)

        with self.assertRaises(ValueError):
            _click_covered_candidate(state, candidate)

    def test_flag_chord_flags_adjacent_mine_and_reveals_safe_neighbors(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        context = _build_premium_context(snapshot)
        candidate = _PremiumCandidate(
            coord=(1, 0),
            premium=_calculate_premium(state, (1, 0), context),
        )

        move = _flag_and_chord_uncovered_candidate(state, candidate, context)

        self.assertEqual(state.flagged_mines, {(1, 1)})
        self.assertEqual(
            state.revealed,
            {(1, 0), (0, 0), (2, 0), (0, 1), (2, 1)},
        )
        self.assertEqual(move.action, "flag_chord")
        self.assertEqual((move.x, move.y), (1, 0))
        self.assertEqual(move.premium, 2)
        self.assertEqual(move.clicks_added, 2)

    def test_flag_chord_counts_only_chord_when_adjacent_mine_already_flagged(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        state.flag_mine((1, 1))
        context = _build_premium_context(snapshot)
        candidate = _PremiumCandidate(
            coord=(1, 0),
            premium=_calculate_premium(state, (1, 0), context),
        )

        move = _flag_and_chord_uncovered_candidate(state, candidate, context)

        self.assertEqual(state.flagged_mines, {(1, 1)})
        self.assertEqual(move.premium, 3)
        self.assertEqual(move.clicks_added, 1)

    def test_flag_chord_reveals_opening_through_adjacent_zero_cell(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 1))
        state.flag_mine((0, 0))
        context = _build_premium_context(snapshot)
        candidate = _PremiumCandidate(
            coord=(1, 1),
            premium=_calculate_premium(state, (1, 1), context),
        )

        move = _flag_and_chord_uncovered_candidate(state, candidate, context)

        self.assertEqual(
            state.revealed,
            {
                (1, 0),
                (0, 1),
                (1, 1),
                (2, 0),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            },
        )
        self.assertEqual(move.clicks_added, 1)

    def test_flag_chord_reveals_border_neighbors_without_border_only_opening(self):
        snapshot = BoardSnapshot(
            width=4,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 1)}),
            adjacent=((1, 1, 0, 0), (0, 1, 0, 0), (1, 1, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        state.flag_mine((0, 1))
        context = _build_premium_context(snapshot)
        candidate = _PremiumCandidate(coord=(0, 0), premium=0)

        move = _flag_and_chord_uncovered_candidate(state, candidate, context)

        self.assertEqual(state.revealed, {(0, 0), (1, 0), (1, 1)})
        self.assertTrue(
            {(2, 0), (2, 1), (1, 2), (2, 2), (3, 2)}.isdisjoint(
                state.revealed
            )
        )
        self.assertEqual(move.clicks_added, 1)

    def test_flag_chord_rejects_covered_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        candidate = _PremiumCandidate(coord=(1, 0), premium=2)

        with self.assertRaises(ValueError):
            _flag_and_chord_uncovered_candidate(
                state, candidate, _build_premium_context(snapshot)
            )

    def test_flag_chord_rejects_negative_premium(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        candidate = _PremiumCandidate(coord=(0, 0), premium=-1)

        with self.assertRaises(ValueError):
            _flag_and_chord_uncovered_candidate(
                state, candidate, _build_premium_context(snapshot)
            )

    def test_flag_chord_rejects_mine_candidate(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        candidate = _PremiumCandidate(coord=(1, 0), premium=0)

        with self.assertRaises(ValueError):
            _flag_and_chord_uncovered_candidate(
                state, candidate, _build_premium_context(snapshot)
            )

    def test_flag_chord_rejects_zero_candidate(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        candidate = _PremiumCandidate(coord=(0, 0), premium=0)

        with self.assertRaises(ValueError):
            _flag_and_chord_uncovered_candidate(
                state, candidate, _build_premium_context(snapshot)
            )

    def test_select_fallback_click_target_returns_single_empty_cell(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        self.assertEqual(
            _select_fallback_click_target(state, context),
            (0, 0),
        )

    def test_fallback_click_zero_reveals_opening_and_solves_board(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _click_fallback_cell(state, (0, 0), context)

        self.assertEqual(state.revealed, {(0, 0)})
        self.assertTrue(state.all_safe_cells_revealed())
        self.assertEqual(move.action, "fallback_click")
        self.assertEqual((move.x, move.y), (0, 0))
        self.assertIsNone(move.premium)
        self.assertEqual(move.clicks_added, 1)

    def test_fallback_click_zero_reveals_opening_and_border_ring(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _click_fallback_cell(state, (2, 0), context)

        self.assertEqual(
            state.revealed,
            {
                (1, 0),
                (0, 1),
                (1, 1),
                (2, 0),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            },
        )
        self.assertEqual(move.action, "fallback_click")
        self.assertIsNone(move.premium)
        self.assertEqual(move.clicks_added, 1)

    def test_fallback_click_number_reveals_only_that_number(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _click_fallback_cell(state, (0, 0), context)

        self.assertEqual(state.revealed, {(0, 0)})
        self.assertEqual(move.action, "fallback_click")
        self.assertEqual((move.x, move.y), (0, 0))
        self.assertIsNone(move.premium)
        self.assertEqual(move.clicks_added, 1)

    def test_select_fallback_click_target_uses_top_leftmost_unrevealed_3bv_unit(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(0, 0)}),
            adjacent=((0, 1, 0), (1, 1, 0), (0, 0, 0)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        self.assertEqual(
            _select_fallback_click_target(state, context),
            (2, 0),
        )

    def test_find_fallback_click_targets_uses_deterministic_row_major_order(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        targets = _find_fallback_click_targets(state, context)

        self.assertEqual(
            targets,
            (
                (0, 0),
                (1, 0),
                (2, 0),
                (0, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
            ),
        )
        self.assertEqual(_select_fallback_click_target(state, context), targets[0])

    def test_select_fallback_click_target_returns_none_when_all_safe_revealed(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        context = _build_premium_context(snapshot)

        self.assertIsNone(_select_fallback_click_target(state, context))

    def test_fallback_click_rejects_mine_target(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        with self.assertRaises(ValueError):
            _click_fallback_cell(state, (1, 0), context)

    def test_fallback_click_rejects_already_revealed_target(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        context = _build_premium_context(snapshot)

        with self.assertRaises(ValueError):
            _click_fallback_cell(state, (0, 0), context)

    def test_fallback_click_rejects_zero_without_opening_unit(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)
        broken_context = type(context)(
            analysis=context.analysis,
            units=context.units,
            opening_units_by_id={},
            isolated_cells=context.isolated_cells,
        )

        with self.assertRaises(ValueError):
            _click_fallback_cell(state, (0, 0), broken_context)

    def test_apply_next_move_returns_none_when_solved(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((0, 0))
        context = _build_premium_context(snapshot)

        self.assertIsNone(_apply_next_g_zini_move(state, context))

    def test_apply_next_move_clicks_covered_best_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _apply_next_g_zini_move(state, context)

        self.assertEqual(move.action, "click")
        self.assertEqual((move.x, move.y), (1, 0))
        self.assertEqual(move.premium, 2)
        self.assertEqual(move.clicks_added, 1)
        self.assertEqual(state.revealed, {(1, 0)})

    def test_apply_next_move_flag_chords_revealed_non_negative_candidate(self):
        snapshot = BoardSnapshot(
            width=3,
            height=3,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 1)}),
            adjacent=((1, 1, 1), (1, 0, 1), (1, 1, 1)),
        )
        state = _ZiniBoardState.create(snapshot)
        state.revealed.add((1, 0))
        context = _build_premium_context(snapshot)

        move = _apply_next_g_zini_move(state, context)

        self.assertEqual(move.action, "flag_chord")
        self.assertEqual((move.x, move.y), (1, 0))
        self.assertEqual(move.premium, 2)
        self.assertEqual(move.clicks_added, 2)
        self.assertEqual(state.flagged_mines, {(1, 1)})
        self.assertEqual(
            state.revealed,
            {(1, 0), (0, 0), (2, 0), (0, 1), (2, 1)},
        )

    def test_apply_next_move_uses_fallback_when_best_premium_is_negative(self):
        snapshot = BoardSnapshot(
            width=2,
            height=1,
            num_mines=1,
            mines_placed=True,
            mines=frozenset({(1, 0)}),
            adjacent=((1, 0),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _apply_next_g_zini_move(state, context)

        self.assertEqual(move.action, "fallback_click")
        self.assertEqual((move.x, move.y), (0, 0))
        self.assertIsNone(move.premium)
        self.assertEqual(move.clicks_added, 1)
        self.assertEqual(state.revealed, {(0, 0)})

    def test_apply_next_move_uses_fallback_when_no_premium_candidate_exists(self):
        snapshot = BoardSnapshot(
            width=1,
            height=1,
            num_mines=0,
            mines_placed=True,
            mines=frozenset(),
            adjacent=((0,),),
        )
        state = _ZiniBoardState.create(snapshot)
        context = _build_premium_context(snapshot)

        move = _apply_next_g_zini_move(state, context)

        self.assertEqual(move.action, "fallback_click")
        self.assertEqual((move.x, move.y), (0, 0))
        self.assertIsNone(move.premium)
        self.assertEqual(move.clicks_added, 1)
        self.assertEqual(state.revealed, {(0, 0)})
        self.assertTrue(state.all_safe_cells_revealed())


if __name__ == "__main__":
    unittest.main()
