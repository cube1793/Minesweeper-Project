"""Small public-state/transport checks; no public corpus or complete-game runner."""

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from core_engine import Action, CellState
from live_flag_review import review_flags
import live_policy as policy
import live_policy_transport as transport
import live_policy_worker as worker
from simple_decision import analyze_position
from stage3_physical import action_cost, load_timing_table
from stage3_planner import plan_position
from stage3_runner import _validate_execution


H, F = int(CellState.HIDDEN), int(CellState.FLAGGED)
RUN = "0123456789abcdef0123456789abcdef"


def snapshot(observation=((H, H, H, H),), mines=1, *, seq=0, cursor=(0, 0), generation=7):
    return policy.make_snapshot(run_id=RUN, board_generation=generation, input_seq=seq,
                                width=len(observation[0]), height=len(observation), num_mines=mines,
                                observation=observation, cursor=cursor)


class PublicValueTests(unittest.TestCase):
    def test_snapshot_detaches_public_grid_and_is_frozen(self):
        original = [[CellState.HIDDEN, CellState.HIDDEN]]
        state = snapshot(original)
        original[0][0] = 1
        self.assertEqual(state.observation, ((H, H),))
        self.assertIs(type(state.observation[0][0]), int)
        with self.assertRaises(FrozenInstanceError):
            state.cursor = (1, 0)

    def test_snapshot_rejects_nonpublic_or_wrong_typed_fields(self):
        state = snapshot()
        invalid = {"board_generation": (True, 1.0, -1), "input_seq": (True, 1.0, 481),
                   "width": (True, 31), "height": (True, 17), "num_mines": (True, -1, 4),
                   "status": ("WON", "LOST", 0), "policy_id": ("K_P0", "S2_SIMPLE"),
                   "run_id": ("bad", "A" * 32), "cursor": ((True, 0), (4, 0), [0, 0]),
                   "observation": (((-5, H, H, H),), ((False, H, H, H),), [[H] * 4])}
        for name, values in invalid.items():
            for value in values:
                with self.subTest(field=name, value=value), self.assertRaises(policy.LivePolicyError):
                    replace(state, **{name: value})

    def test_wire_snapshot_rejects_extra_truth_fields_and_float_glyphs(self):
        wire = policy.snapshot_to_dict(snapshot())
        for extra in ("mines", "adjacent", "engine", "ReplayBoard"):
            with self.subTest(extra=extra), self.assertRaises(policy.LivePolicyError):
                policy.snapshot_from_dict({**wire, extra: []})
        wire["observation"][0][0] = -2.0
        with self.assertRaises(policy.LivePolicyError):
            policy.snapshot_from_dict(wire)

    def test_ui_presets_are_exact_and_do_not_claim_custom_support(self):
        for board in ((9, 9, 10), (16, 16, 40), (30, 16, 99)):
            self.assertTrue(policy.supports_v1_board(*board))
        for board in ((9, 9, 11), (4, 1, 1), (16, 30, 99), (True, 9, 10)):
            self.assertFalse(policy.supports_v1_board(*board))

    def test_snapshot_codec_roundtrip_has_only_public_fields(self):
        state = snapshot()
        wire = json.loads(json.dumps(policy.snapshot_to_dict(state)))
        self.assertEqual(policy.snapshot_from_dict(wire), state)
        self.assertEqual(set(wire), {"run_id", "board_generation", "input_seq", "width", "height",
                                    "num_mines", "observation", "cursor", "policy_id", "status",
                                    "entry_mode", "input_revision", "phase", "initial_flag_count", "review_inputs"})


class FrozenDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def plan(self, state):
        return policy.plan_snapshot(state, table=self.table)

    def test_initial_policy_uses_no_planner_and_is_not_guess(self):
        state = snapshot()
        with patch("stage3_planner.plan_position", side_effect=AssertionError("initial must not analyze")), \
             patch("stage3_runner._validate_execution", wraps=_validate_execution) as validate:
            proposal = self.plan(state)
        validate.assert_called_once_with(state.observation, proposal.move, None)
        self.assertEqual((proposal.action, proposal.x, proposal.y), ("OPEN", 0, 0))
        self.assertEqual(proposal.modeled_action_us, 126005)
        self.assertEqual(proposal.compute_ns, 0)
        self.assertFalse(proposal.is_guess)
        self.assertTrue(proposal.initial)

    def test_initial_policy_rejects_progressed_start_or_nonorigin_cursor(self):
        for state in (snapshot(((1, H, H, H),)), snapshot(cursor=(1, 0))):
            with self.subTest(state=state), self.assertRaises(policy.LivePolicyError):
                self.plan(state)

    def test_actual_first_choices_match_frozen_api_on_small_public_states(self):
        cases = [(((0, H, H, 3), (H, H, H, H)), 3, (0, 0)),
                 (((F, 1, H, H), (1, 1, H, H)), 1, (1, 0)),
                 (((1, H, 1, H),), 1, (0, 0)),
                 (((H, 1, H),), 1, (1, 0))]
        for observation, mines, cursor in cases:
            state = snapshot(observation, mines, seq=1, cursor=cursor)
            expected = plan_position(state.observation, mines, cursor, self.table)
            with self.subTest(observation=observation), \
                 patch("stage3_planner.plan_position", wraps=plan_position) as planner, \
                 patch("stage3_runner._validate_execution", wraps=_validate_execution) as validator:
                actual = self.plan(state)
            planner.assert_called_once_with(state.observation, mines, cursor, self.table)
            validator.assert_called_once()
            self.assertEqual(actual.move, expected.move)
            self.assertEqual(actual.modeled_action_us, action_cost(self.table, cursor, (actual.x, actual.y)))

    def test_projection_does_not_recompute_simple_or_probability(self):
        state = snapshot(((0, H, H, 3), (H, H, H, H)), 3, seq=1)
        with patch("stage3_planner.analyze_position", wraps=analyze_position) as analyze, \
             patch("simple_decision.calculate_probabilities", side_effect=AssertionError("local only")):
            proposal = self.plan(state)
        analyze.assert_called_once_with(state.observation, state.num_mines)
        self.assertEqual(proposal.action, "OPEN")
        self.assertEqual((proposal.x, proposal.y), (1, 0))
        self.assertTrue(all(cell.mine_worlds is None for cell in proposal.overlays))

    def test_chord_proposal_uses_revealed_anchor_and_safe_hidden_neighbors(self):
        state = snapshot(((F, 1, H, H), (1, 1, H, H)), 1, seq=2, cursor=(1, 0))
        proposal = self.plan(state)
        self.assertEqual(proposal.action, "CHORD")
        self.assertEqual(state.observation[proposal.y][proposal.x], 1)
        self.assertEqual({(cell.x, cell.y) for cell in proposal.overlays if cell.kind == "safe"}, {(2, 0), (2, 1)})
        self.assertNotIn((proposal.x, proposal.y), {(cell.x, cell.y) for cell in proposal.overlays})

    def test_setup_plan_exposes_only_first_flag_not_suffix(self):
        proposal = self.plan(snapshot(((1, H, 1, H),), 1, seq=1))
        self.assertEqual((proposal.action, proposal.x, proposal.y), ("FLAG", 1, 0))
        wire = policy.proposal_to_dict(proposal)
        self.assertNotIn("actions", wire)
        self.assertNotIn("plan", wire)
        self.assertNotIn("suffix", wire)

    def test_guess_projection_keeps_exact_risk_and_frozen_tie(self):
        proposal = self.plan(snapshot(((H, 1, H),), 1, seq=1, cursor=(1, 0)))
        self.assertTrue(proposal.is_guess)
        self.assertEqual((proposal.x, proposal.y), (0, 0))
        self.assertTrue(all(cell.kind == "guess_candidate" and cell.mine_worlds * 2 == cell.total_worlds
                            for cell in proposal.overlays))

    def test_admission_reuses_decision_and_rejects_same_grid_different_generation(self):
        state = snapshot()
        proposal = self.plan(state)
        with patch("stage3_planner.plan_position", side_effect=AssertionError("must reuse pending")):
            self.assertIs(policy.admit_proposal(proposal, state), proposal)
            for stale in (replace(state, board_generation=8), replace(state, run_id="f" * 32),
                          replace(state, cursor=(1, 0)), replace(state, input_seq=1, input_revision=1)):
                with self.subTest(stale=stale), self.assertRaises(policy.LivePolicyError):
                    policy.admit_proposal(proposal, stale)

    def test_proposal_wire_roundtrip_and_tampered_action_or_profile_rejected(self):
        proposal = self.plan(snapshot())
        wire = json.loads(json.dumps(policy.proposal_to_dict(proposal)))
        self.assertEqual(policy.proposal_from_dict(wire), proposal)
        for key, value in (("action", "FLAG"), ("x", 1), ("profile_sha256", "0" * 64),
                           ("kind", "guess"), ("modeled_action_us", True), ("token", 1)):
            with self.subTest(key=key), self.assertRaises(policy.LivePolicyError):
                policy.proposal_from_dict({**wire, key: value})

    def test_initial_ack_progress_and_next_snapshot(self):
        proposal = self.plan(snapshot())
        ack = policy.make_ack(proposal, "PLAYING", ((1, H, H, H),))
        following = policy.validate_ack(proposal, ack)
        self.assertEqual(following.input_seq, 1)
        self.assertEqual(following.cursor, (0, 0))
        self.assertEqual(following.observation, ((1, H, H, H),))
        self.assertEqual(policy.ack_from_dict(policy.ack_to_dict(ack)), ack)

    def test_ack_rejects_no_progress_regression_or_wrong_flag_effect(self):
        initial = self.plan(snapshot())
        with self.assertRaises(policy.LivePolicyError):
            policy.make_ack(initial, "PLAYING", initial.snapshot.observation)
        flag = self.plan(snapshot(((1, H, 1, H),), 1, seq=1))
        for after in (((0, F, 1, H),), ((1, F, 1, F),), ((1, 1, 1, H),)):
            with self.subTest(after=after), self.assertRaises(policy.LivePolicyError):
                policy.make_ack(flag, "PLAYING", after)
        self.assertEqual(policy.make_ack(flag, "PLAYING", ((1, F, 1, H),)).action, "FLAG")

    def test_chord_ack_requires_all_selected_hidden_neighbors_and_no_new_flags(self):
        chord = self.plan(snapshot(((F, 1, H, H), (1, 1, H, H)), 1, seq=2, cursor=(1, 0)))
        for after in (((F, 1, 0, H), (1, 1, H, H)), ((F, 1, F, H), (1, 1, 0, H))):
            with self.subTest(after=after), self.assertRaises(policy.LivePolicyError):
                policy.make_ack(chord, "PLAYING", after)
        policy.make_ack(chord, "PLAYING", ((F, 1, 0, H), (1, 1, 0, H)))

    def test_terminal_ack_has_status_only_and_keeps_last_action_binding(self):
        proposal = self.plan(snapshot())
        ack = policy.make_ack(proposal, "WON")
        self.assertIsNone(ack.observation)
        self.assertIsNone(policy.validate_ack(proposal, ack))
        with self.assertRaises(policy.LivePolicyError):
            policy.make_ack(proposal, "WON", ((0, 1, F, F),))
        for changed in (replace(ack, token="f" * 32), replace(ack, action="FLAG"), replace(ack, x=1)):
            with self.subTest(changed=changed), self.assertRaises(policy.LivePolicyError):
                policy.validate_ack(proposal, changed)


def adopted(observation, mines=1, *, revision=601, cursor=(0, 0)):
    flags = sum(value == F for row in observation for value in row)
    return policy.make_snapshot(
        run_id=RUN, board_generation=7, input_seq=0, width=len(observation[0]),
        height=len(observation), num_mines=mines, observation=observation, cursor=cursor,
        entry_mode=policy.ADOPT_CURRENT, input_revision=revision,
        phase=policy.PHASE_FLAG_REVIEW if flags else policy.PHASE_V1, initial_flag_count=flags,
    )


class AdoptionAndReviewProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def plan(self, state, review=None):
        return policy.plan_snapshot(state, table=self.table, review=review)

    def test_adopt_seq_zero_uses_frozen_once_and_never_canonical_exception(self):
        state = adopted(((H, 1, H),), cursor=(1, 0))
        expected = plan_position(state.observation, 1, state.cursor, self.table)
        with patch("stage3_planner.plan_position", wraps=plan_position) as planner:
            actual = self.plan(state)
        planner.assert_called_once_with(state.observation, 1, state.cursor, self.table)
        self.assertEqual(actual.move, expected.move)
        self.assertEqual(actual.snapshot.input_seq, 0)
        self.assertEqual(actual.snapshot.input_revision, 601)
        self.assertTrue(actual.is_guess)
        self.assertFalse(actual.initial)

    def test_adopt_all_hidden_after_manual_flag_unflag_remains_a_guess(self):
        state = adopted(((H, H),), revision=2, cursor=(1, 0))
        with patch("stage3_planner.plan_position", wraps=plan_position) as planner:
            proposal = self.plan(state)
        self.assertEqual(planner.call_count, 1)
        self.assertTrue(proposal.is_guess)
        self.assertFalse(proposal.initial)

    def test_start_rejects_skipped_review_wrong_flag_bound_or_canonical_revision(self):
        state = adopted(((F, 1, H),))
        for altered in (replace(state, phase=policy.PHASE_V1), replace(state, initial_flag_count=2),
                        replace(snapshot(), input_revision=2),
                        replace(snapshot(), input_seq=1, input_revision=1)):
            with self.subTest(altered=altered), self.assertRaises(policy.LivePolicyError):
                policy.validate_start_snapshot(altered)

    def test_new_wire_fields_are_required_strict_and_revision_not_board_bound(self):
        state = adopted(((H, 1, H),), revision=10001)
        self.assertEqual(policy.snapshot_from_dict(policy.snapshot_to_dict(state)), state)
        wire = policy.snapshot_to_dict(state)
        for name in ("entry_mode", "input_revision", "phase", "initial_flag_count", "review_inputs"):
            missing = dict(wire)
            del missing[name]
            with self.subTest(missing=name), self.assertRaises(policy.LivePolicyError):
                policy.snapshot_from_dict(missing)
        for key, value in (("entry_mode", "ADOPT"), ("phase", 1), ("input_revision", True),
                           ("initial_flag_count", True), ("review_inputs", 1)):
            with self.subTest(key=key), self.assertRaises(policy.LivePolicyError):
                policy.snapshot_from_dict({**wire, key: value})

    def test_unverified_fifty_fifty_flag_is_preparation_then_guess_with_zero_opens(self):
        state = adopted(((F, 1, H),), cursor=(2, 0))
        with patch("stage3_planner.plan_position", side_effect=AssertionError("review cannot plan")):
            proposal = self.plan(state)
        self.assertEqual((proposal.action, proposal.x, proposal.y, proposal.kind), ("FLAG", 0, 0, "flag_review"))
        self.assertTrue(proposal.is_flag_review)
        self.assertEqual(proposal.review.unverified, ((0, 0),))
        self.assertEqual(proposal.compute_ns, 0)
        self.assertEqual(proposal.overlays, ())
        self.assertEqual(proposal.modeled_action_us, action_cost(self.table, (2, 0), (0, 0)))
        ack = policy.make_ack(proposal, "PLAYING", ((H, 1, H),))
        following = policy.validate_ack(proposal, ack)
        self.assertEqual((following.input_seq, following.input_revision, following.review_inputs,
                          following.phase, following.cursor), (1, 602, 1, policy.PHASE_V1, (0, 0)))
        decision = self.plan(following)
        self.assertTrue(decision.is_guess)
        self.assertFalse(decision.is_flag_review)
        # Pure selection/ACK validation never calls an engine or performs OPEN.
        self.assertEqual(state.observation, ((F, 1, H),))

    def test_proved_mine_is_retained_and_first_plan_uses_physical_current_view(self):
        state = adopted(((F, 1, H, H),), cursor=(1, 0))
        # This flag is not proved from H,1,H,H, so it must be reviewed as unknown.
        proposal = self.plan(state)
        self.assertEqual(proposal.review.unverified, ((0, 0),))
        proved = adopted(((F, 1, 0, H),), cursor=(1, 0))
        with patch("stage3_planner.plan_position", wraps=plan_position) as planner:
            selected = self.plan(proved)
        self.assertFalse(selected.is_flag_review)
        self.assertEqual(selected.review.proved_mine, ((0, 0),))
        self.assertEqual(selected.snapshot.phase, policy.PHASE_FLAG_REVIEW)
        self.assertEqual(selected.phase, policy.PHASE_V1)
        planner.assert_called_once_with(proved.observation, 1, proved.cursor, self.table)
        self.assertNotEqual((selected.action, selected.x, selected.y), ("FLAG", 0, 0))

    def test_preparation_order_is_row_major_and_reuses_exact_public_view_once(self):
        state = adopted(((F, 1, F),))
        first = self.plan(state)
        self.assertEqual((first.x, first.y), (0, 0))
        following = policy.validate_ack(first, policy.make_ack(first, "PLAYING", ((H, 1, F),)))
        self.assertEqual(following.phase, policy.PHASE_FLAG_REVIEW)
        with patch.object(policy, "review_flags", side_effect=AssertionError("reuse only")), \
             patch("stage3_planner.plan_position", side_effect=AssertionError("no V1 until cleanup")):
            second = self.plan(following, first.review)
        self.assertEqual((second.x, second.y), (2, 0))
        self.assertEqual(second.review_compute_ns, 0)
        self.assertEqual(second.review, first.review)
        following = policy.validate_ack(second, policy.make_ack(second, "PLAYING", ((H, 1, H),)))
        self.assertEqual((following.review_inputs, following.input_seq, following.phase), (2, 2, policy.PHASE_V1))

    def test_review_ack_rejects_wrong_toggle_extra_change_no_progress_and_terminal(self):
        proposal = self.plan(adopted(((F, 1, F),)))
        for after in (((F, 1, F),), ((F, 1, H),), ((H, 1, H),), ((0, 1, F),), ((H, 0, F),)):
            with self.subTest(after=after), self.assertRaises(policy.LivePolicyError):
                policy.make_ack(proposal, "PLAYING", after)
        for status in ("WON", "LOST"):
            with self.subTest(status=status), self.assertRaises(policy.LivePolicyError):
                policy.make_ack(proposal, status)

    def test_review_ack_binds_entry_phase_revision_token_and_cursor(self):
        proposal = self.plan(adopted(((F, 1, H),)))
        ack = policy.make_ack(proposal, "PLAYING", ((H, 1, H),))
        self.assertEqual(policy.ack_from_dict(policy.ack_to_dict(ack)), ack)
        for changed in (replace(ack, input_revision=601), replace(ack, entry_mode=policy.CANONICAL_NEW),
                        replace(ack, phase=policy.PHASE_V1), replace(ack, token="f" * 32), replace(ack, x=2)):
            with self.subTest(changed=changed), self.assertRaises(policy.LivePolicyError):
                policy.validate_ack(proposal, changed)

    def test_review_wire_rejects_phase_classification_target_and_omission_tampering(self):
        proposal = self.plan(adopted(((F, 1, F),)))
        wire = json.loads(json.dumps(policy.proposal_to_dict(proposal)))
        self.assertEqual(policy.proposal_from_dict(wire), proposal)
        for key, value in (("phase", policy.PHASE_V1), ("kind", "certain"), ("action", "OPEN"),
                           ("x", 2), ("review", None), ("review_compute_ns", True)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                policy.proposal_from_dict({**wire, key: value})
        missing = dict(wire)
        del missing["phase"]
        with self.assertRaises(policy.LivePolicyError):
            policy.proposal_from_dict(missing)
        forged = json.loads(json.dumps(wire))
        forged["review"]["proved_mine"] = [[0, 0]]
        forged["review"]["unverified"] = [[2, 0]]
        with self.assertRaises(ValueError):
            policy.proposal_from_dict(forged)

    def test_review_cannot_be_recomputed_or_reused_after_unacknowledged_changes(self):
        first = self.plan(adopted(((F, 1, F),)))
        following = policy.validate_ack(first, policy.make_ack(first, "PLAYING", ((H, 1, F),)))
        with self.assertRaises(policy.LivePolicyError):
            self.plan(following)
        for altered in (replace(following, observation=((F, 1, H),)),
                        replace(following, observation=((H, 0, F),))):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                self.plan(altered, first.review)
        second = self.plan(following, first.review)
        completed = policy.validate_ack(second, policy.make_ack(second, "PLAYING", ((H, 1, H),)))
        with self.assertRaises(policy.LivePolicyError):
            self.plan(completed, first.review)

    def test_new_plan_token_cannot_acknowledge_another_preparation(self):
        state = adopted(((F, 1, H),))
        first, second = self.plan(state), self.plan(state)
        self.assertNotEqual(first.token, second.token)
        with self.assertRaises(policy.LivePolicyError):
            policy.validate_ack(first, policy.make_ack(second, "PLAYING", ((H, 1, H),)))

    def test_review_failure_propagates_without_unverified_fallback(self):
        state = adopted(((F, 1, H),))
        with patch.object(policy, "review_flags", side_effect=RuntimeError("classification failed")), \
             patch("stage3_planner.plan_position", side_effect=AssertionError("no fallback")):
            with self.assertRaisesRegex(RuntimeError, "classification failed"):
                self.plan(state)

    def test_finite_review_and_v1_bounds_do_not_limit_global_revision_or_overlay_cells(self):
        original = tuple(tuple(F for _ in range(30)) for _ in range(16))
        report = review_flags(original, 99)
        current = tuple(tuple(F if (x, y) == (29, 15) else H for x in range(30)) for y in range(16))
        state = policy.make_snapshot(
            run_id=RUN, board_generation=7, input_seq=479, width=30, height=16, num_mines=99,
            observation=current, cursor=(28, 15), entry_mode=policy.ADOPT_CURRENT,
            input_revision=5001, phase=policy.PHASE_FLAG_REVIEW, initial_flag_count=480, review_inputs=479,
        )
        last = self.plan(state, report)
        after = tuple(tuple(H for _ in range(30)) for _ in range(16))
        following = policy.validate_ack(last, policy.make_ack(last, "PLAYING", after))
        self.assertEqual((following.input_seq, following.review_inputs, following.input_revision), (480, 480, 5002))
        exhausted = replace(following, input_seq=960, input_revision=5482)
        with patch("stage3_planner.plan_position", side_effect=AssertionError("bound before plan")):
            with self.assertRaises(policy.LivePolicyError):
                self.plan(exhausted)
        with self.assertRaises(policy.LivePolicyError):
            replace(exhausted, input_seq=961)
        self.assertEqual((policy.MAX_BOARD_CELLS, policy.MAX_V1_INPUTS, policy.MAX_INPUTS,
                          transport.MAX_V1_SEQUENCE), (480, 480, 960, 1921))
        self.assertEqual(transport.MAX_SEQUENCE, 63362)  # New FLAG_ADOPT envelope; V1 remains 1921.


class WriteOnceTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="minesweeper_live_protocol_test_")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_real_write_once_roundtrip_and_held_prior_reader(self):
        first = transport.message(RUN, 0, "START", policy.snapshot_to_dict(snapshot()))
        path = transport.write_once(self.directory, "parent", 0, first)
        with path.open("rb") as held:
            second = transport.message(RUN, 1, "ACK", {})
            transport.write_once(self.directory, "parent", 1, second)
            self.assertEqual(transport.read_next(self.directory, "parent", 1, RUN), second)
            self.assertTrue(held.read())
        self.assertEqual(transport.read_next(self.directory, "parent", 0, RUN), first)
        original = path.read_bytes()
        published_parts = set(self.directory.glob("*.part"))
        self.assertEqual(len(published_parts), 2)
        with self.assertRaises(FileExistsError):
            transport.write_once(self.directory, "parent", 0, first)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(set(self.directory.glob("*.part")), published_parts)

    def test_real_publication_keeps_staging_link_while_new_final_reader_is_open(self):
        real_link = transport.os.link
        held = []

        def link_then_open(source, destination):
            real_link(source, destination)
            stream = Path(destination).open("rb")
            held.append(stream)
            self.addCleanup(stream.close)

        first = transport.message(RUN, 0, "START", policy.snapshot_to_dict(snapshot()))
        second = transport.message(RUN, 1, "ACK", {})
        with patch.object(transport.os, "link", side_effect=link_then_open):
            first_path = transport.write_once(self.directory, "parent", 0, first)
            self.assertFalse(held[0].closed)
            self.assertEqual(json.loads(held[0].read()), first)
            self.assertEqual(transport.read_next(self.directory, "parent", 0, RUN), first)
            transport.write_once(self.directory, "parent", 1, second)
            self.assertEqual(transport.read_next(self.directory, "parent", 1, RUN), second)
        self.assertEqual(len(held), 2)
        self.assertTrue(all(not stream.closed for stream in held))
        self.assertEqual(len(list(self.directory.glob("*.part"))), 2)
        self.assertEqual(json.loads(first_path.read_bytes()), first)

    def test_missing_expected_and_future_sequence_are_distinct(self):
        self.assertIsNone(transport.read_next(self.directory, "worker", 0, RUN))
        transport.write_once(self.directory, "worker", 1, transport.message(RUN, 1, "ACKED", {}))
        with self.assertRaises(policy.LivePolicyError):
            transport.read_next(self.directory, "worker", 0, RUN)

    def test_duplicate_json_key_trailing_data_and_nonfinite_rejected(self):
        path = self.directory / "worker-00000000.json"
        valid = json.dumps(transport.message(RUN, 0, "PROPOSAL", {}))
        bad = [valid[:-1] + ', "seq":0}', valid + '{}', valid.replace('"payload": {}', '"payload":{"bad":NaN}')]
        for raw in bad:
            path.write_text(raw, encoding="utf-8")
            with self.subTest(raw=raw), self.assertRaises(policy.LivePolicyError):
                transport.read_next(self.directory, "worker", 0, RUN)

    def test_strict_version_sequence_identity_and_envelope_keys(self):
        valid = transport.message(RUN, 0, "PROPOSAL", {})
        for key, value in (("version", True), ("version", 1.0), ("seq", False), ("seq", 0.0),
                           ("version", 1),
                           ("kind", "COMPLETED"), ("payload", []), ("run_id", "bad")):
            with self.subTest(key=key, value=value), self.assertRaises(policy.LivePolicyError):
                transport.validate_message({**valid, key: value})
        for changed in ({**valid, "unknown": 1}, {**valid, "seq": 1}, {**valid, "run_id": "f" * 32}):
            with self.subTest(changed=changed), self.assertRaises(policy.LivePolicyError):
                transport.validate_message(changed, seq=0, run_id=RUN)

    def test_length_cap_checked_on_read_and_write(self):
        with patch.object(transport, "MAX_MESSAGE_BYTES", 100):
            with self.assertRaises(policy.LivePolicyError):
                transport.write_once(self.directory, "worker", 0, transport.message(RUN, 0, "ERROR", {"detail": "x" * 101}))
            (self.directory / "worker-00000000.json").write_bytes(b" " * 101)
            with self.assertRaises(policy.LivePolicyError):
                transport.read_next(self.directory, "worker", 0, RUN)


class WorkerSequenceTests(unittest.TestCase):
    def test_review_worker_reuses_one_classification_then_plans_actual_cleaned_view(self):
        state = adopted(((F, 1, F),))
        sent = []
        expected = None

        def read(_directory, direction, seq, run_id):
            nonlocal expected
            self.assertEqual((direction, run_id), ("parent", RUN))
            if seq == 0:
                return transport.message(RUN, seq, "START", policy.snapshot_to_dict(state))
            if seq % 2:
                proposal = policy.proposal_from_dict(sent[-1]["payload"])
                if seq == 1:
                    ack = policy.make_ack(proposal, "PLAYING", ((H, 1, F),))
                elif seq == 3:
                    ack = policy.make_ack(proposal, "PLAYING", ((H, 1, H),))
                else:
                    ack = policy.make_ack(proposal, "LOST")
                expected = policy.validate_ack(proposal, ack)
                return transport.message(RUN, seq, "ACK", policy.ack_to_dict(ack))
            return transport.message(RUN, seq, "NEXT", policy.snapshot_to_dict(expected))

        with patch.object(worker, "read_next", side_effect=read), \
             patch.object(worker, "write_once", side_effect=lambda _d, _side, _seq, item: sent.append(item)), \
             patch.object(policy, "review_flags", wraps=review_flags) as review, \
             patch("stage3_planner.plan_position", wraps=plan_position) as planner:
            self.assertEqual(worker.serve("synthetic", RUN), 0)
        self.assertEqual(review.call_count, 1)
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(planner.call_args.args[:3], (((H, 1, H),), 1, (2, 0)))
        proposals = [policy.proposal_from_dict(item["payload"]) for item in sent if item["kind"] == "PROPOSAL"]
        self.assertEqual([(item.kind, item.action) for item in proposals],
                         [("flag_review", "FLAG"), ("flag_review", "FLAG"), ("guess", "OPEN")])
        self.assertEqual([item.snapshot.input_revision for item in proposals], [601, 602, 603])
        self.assertEqual(sent[-1]["kind"], "FINISHED")

    def test_review_worker_failure_is_error_with_no_action_publication(self):
        sent = []
        request = transport.message(RUN, 0, "START", policy.snapshot_to_dict(adopted(((F, 1, H),))))
        with patch.object(worker, "read_next", return_value=request), \
             patch.object(worker, "write_once", side_effect=lambda _d, _side, _seq, item: sent.append(item)), \
             patch.object(policy, "review_flags", side_effect=RuntimeError("review failed")), \
             patch("stage3_planner.plan_position", side_effect=AssertionError("no fallback")):
            self.assertEqual(worker.serve("synthetic", RUN), 1)
        self.assertEqual([item["kind"] for item in sent], ["ERROR"])
        self.assertIn("review failed", sent[0]["payload"]["detail"])

    def test_main_worker_dispatch_keeps_entry_marker_and_skips_qt_setup(self):
        import main as entry

        arguments = ["main.py", "--live-policy-worker", "private_channel", RUN, "owned_scope"]
        with patch.object(sys, "argv", arguments), \
             patch.object(worker, "main", return_value=37) as dispatch, \
             patch.object(entry, "_configure_qt_plugin_path", side_effect=AssertionError("Qt setup in worker")) as qt_setup:
            self.assertEqual(entry.main(), 37)
        dispatch.assert_called_once_with(arguments[1:])
        qt_setup.assert_not_called()

    def test_single_pending_ack_then_explicit_next_and_terminal_barrier(self):
        state = snapshot()
        sent = []
        last_ack = None

        def read(_directory, direction, seq, run_id):
            nonlocal last_ack
            self.assertEqual((direction, run_id), ("parent", RUN))
            if seq == 0:
                return transport.message(RUN, seq, "START", policy.snapshot_to_dict(state))
            if seq % 2:
                proposal = policy.proposal_from_dict(sent[-1]["payload"])
                if seq == 1:
                    last_ack = policy.make_ack(proposal, "PLAYING", ((1, H, H, H),))
                elif seq == 3:
                    last_ack = policy.make_ack(proposal, "PLAYING", ((1, F, H, H),))
                else:
                    last_ack = policy.make_ack(proposal, "WON")
                return transport.message(RUN, seq, "ACK", policy.ack_to_dict(last_ack))
            previous = policy.proposal_from_dict(sent[-2]["payload"])
            next_state = policy.validate_ack(previous, last_ack)
            return transport.message(RUN, seq, "NEXT", policy.snapshot_to_dict(next_state))

        with patch.object(worker, "read_next", side_effect=read), \
             patch.object(worker, "write_once", side_effect=lambda _d, _direction, _seq, envelope: sent.append(envelope)), \
             patch("stage3_planner.plan_position", wraps=plan_position) as planner:
            self.assertEqual(worker.serve("synthetic", RUN), 0)
        self.assertEqual([item["kind"] for item in sent], ["PROPOSAL", "ACKED", "PROPOSAL", "ACKED", "PROPOSAL", "FINISHED"])
        self.assertEqual(planner.call_count, 2)
        self.assertEqual([item["payload"]["action"] for item in sent if item["kind"] == "PROPOSAL"], ["OPEN", "FLAG", "OPEN"])
        self.assertNotIn("observation", sent[-1]["payload"])

    def test_next_before_ack_is_error_and_no_second_analysis(self):
        sent = []
        requests = [transport.message(RUN, 0, "START", policy.snapshot_to_dict(snapshot())),
                    transport.message(RUN, 1, "NEXT", policy.snapshot_to_dict(snapshot(seq=1)))]
        with patch.object(worker, "read_next", side_effect=requests), \
             patch.object(worker, "write_once", side_effect=lambda _d, _direction, _seq, envelope: sent.append(envelope)), \
             patch.object(worker, "plan_snapshot", wraps=policy.plan_snapshot) as planner:
            self.assertEqual(worker.serve("synthetic", RUN), 1)
        self.assertEqual(planner.call_count, 1)
        self.assertEqual(sent[-1]["kind"], "ERROR")

    def test_next_must_equal_acknowledged_generation_cursor_and_public_state(self):
        sent = []

        def read(_directory, _direction, seq, _run_id):
            if seq == 0:
                return transport.message(RUN, seq, "START", policy.snapshot_to_dict(snapshot()))
            if seq == 1:
                proposal = policy.proposal_from_dict(sent[-1]["payload"])
                ack = policy.make_ack(proposal, "PLAYING", ((1, H, H, H),))
                return transport.message(RUN, seq, "ACK", policy.ack_to_dict(ack))
            altered = snapshot(((1, H, H, H),), seq=1, generation=8)
            return transport.message(RUN, seq, "NEXT", policy.snapshot_to_dict(altered))

        with patch.object(worker, "read_next", side_effect=read), \
             patch.object(worker, "write_once", side_effect=lambda _d, _direction, _seq, envelope: sent.append(envelope)):
            self.assertEqual(worker.serve("synthetic", RUN), 1)
        self.assertEqual(sent[-1]["kind"], "ERROR")


if __name__ == "__main__":
    unittest.main()
