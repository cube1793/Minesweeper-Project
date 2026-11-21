"""K_D23: the FT-based new K connected to the product's owner, worker protocol and parent job (copy only).

Material: the owner on declared PUBLIC grids, the data records, the worker protocol driven in this process
(``serve`` with its two transport functions replaced) and the real LivePolicyJob with a fake process.
No Engine is built, no board is generated and no hidden layout exists in this module. The fixed states and
their expected values are read from INTEGRATION_TEST_PLAN.json, which was sealed before the source changed.
"""
import ast
from dataclasses import fields, replace
from fractions import Fraction
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from qt_bootstrap import configure_qt_plugin_path
configure_qt_plugin_path()
from PyQt5.QtWidgets import QApplication

import live_analysis
import live_k_basis as b
import live_k_policy as k
import live_policy_job as jobs
import live_policy_worker as worker
import ui_help
from core_engine import Action, GameStatus
from experiments import program_d2_opening_policy as opening_policy
from experiments import program_d3_explanation as X
from experiments import program_d3_link_diagnosis as link_diagnosis
from experiments import program_d3_lookahead_policy as lookahead
from experiments import program_d3_pseudo_diagnosis as pseudo_diagnosis
from experiments import program_d23_policy as combined_policy
from experiments.program_k_capability import KLocalSession
from live_k_d23 import KD23Explainer
from live_k_info import KInfoSupplement
from live_policy import LivePolicyError, POLICY_K, POLICY_K_D23, POLICY_K_LC0, POLICY_K_LC1
from live_policy_transport import message, read_next, write_once
from simple_algorithm import SimpleMove
from stage3_physical import load_timing_table


SOURCE = Path(__file__).resolve().parents[1]
PLAN = json.loads((SOURCE / "tests" / "fixtures" / "live_k_d23_test_plan_v1.json").read_text(encoding="utf-8"))
STATES = PLAN["fixed_states"]
DECISIONS = ("CERTAIN_APPLIED", "FORCED_KEPT", "FORCED_ABOVE_MINIMUM", "TIE_CHANGED", "KEPT")
OLD_POLICIES = (POLICY_K, POLICY_K_LC0, POLICY_K_LC1)
NEW_CATEGORIES = ("FORCED_5050_GUESS", "TIE_LOOKAHEAD_GUESS", "PROVEN_OPENING_OPEN")
BASIS_FIELDS = ("basis_id", "token", "binding_sha256", "diagnosis", "branch", "reason", "original",
                "input_changed", "risk", "pair", "short", "head_proposed", "head_blocked", "head_executed",
                "body", "pseudo", "linked", "loss", "calls", "stage_ns")
H, F = -2, -3
TABLE = load_timing_table()
PLAYING = GameStatus.PLAYING


def grid(rows):
    return tuple(tuple(H if token == "H" else F if token == "F" else int(token) for token in row.split())
                 for row in rows)


# Public observations written by hand from the accepted small layouts; no Engine made them here.
S8_AFTER_FIRST = grid(["0 0 1 H H H H H", "0 0 1 H H H H H"])   # 8x2, one mine in column 3, after OPEN (0, 0)
S8_AFTER_OPENING = grid(["0 0 1 H 1 0 0 0", "0 0 1 H 1 0 0 0"])  # ... and after OPEN (5, 0)
G5_AFTER_GUESS = grid(["0 0 1 1 H H", "0 0 1 H H H"])            # FORCED_ABOVE_MINIMUM after a safe OPEN (3, 0)
FLAGGED = grid(["1 F 1 F", "1 1 1 H"])                           # FLAG4X2: (1, 0) proven, (3, 0) removable


def adopted(rows, mines, cursor, policy=POLICY_K_D23, revision=5):
    observation = rows if type(rows) is tuple else grid(rows)
    return k.KSnapshot(uuid4().hex, 1, 0, len(observation[0]), len(observation), mines, observation,
                       tuple(cursor), revision, game_id="f" * 32, policy_id=policy,
                       definition=k.definition_for_entry(k.ADOPT_CURRENT, policy), entry_mode=k.ADOPT_CURRENT,
                       start_input_revision=revision, phase=k.normal_phase(policy))


def state_of(name, policy=POLICY_K_D23):
    spec = STATES[name]
    return adopted(spec["grid"], spec["mines"], spec["cursor"], policy)


def canonical(width, height, mines, policy=POLICY_K_D23):
    return k.KSnapshot(uuid4().hex, 1, 0, width, height, mines, tuple((H,) * width for _ in range(height)),
                       (0, 0), 0, game_id="f" * 32, policy_id=policy,
                       definition=k.definition_for_entry(k.CANONICAL_NEW, policy), phase=k.normal_phase(policy))


def fixed_board(width, height, mines, policy=POLICY_K_D23):
    return k.KSnapshot(uuid4().hex, 1, 0, width, height, mines, tuple((H,) * width for _ in range(height)),
                       (0, 0), 0, game_id="f" * 32, policy_id=policy,
                       definition=k.definition_for_entry(k.FIXED_BOARD, policy), entry_mode=k.FIXED_BOARD,
                       phase=k.normal_phase(policy))


def flagged_start(policy=POLICY_K_D23, revision=7):
    return k.make_snapshot(
        run_id=uuid4().hex, game_id="f" * 32, board_generation=1, input_seq=0, width=4, height=2, num_mines=1,
        observation=FLAGGED, cursor=(3, 0), input_revision=revision, entry_mode=k.FLAG_ADOPT,
        definition=k.definition_for_entry(k.FLAG_ADOPT, policy), start_input_revision=revision,
        phase=k.PHASE_BOOTSTRAP, policy_id=policy)


def permit(owner, proposal, nonce=None):
    return owner.validate(k.KValidation(proposal.snapshot, proposal.token, nonce or uuid4().hex,
                                        proposal.pending_m_revision))


def decide(name, diagnosis="PSEUDO", policy=POLICY_K_D23):
    """(owner, start, proposal, basis) of one declared public state, analysed once by a new owner."""
    start = state_of(name, policy)
    owner = k.KOwner(start, TABLE)
    proposal = owner.propose(start)
    basis = KD23Explainer(diagnosis).describe(owner, proposal) if policy == POLICY_K_D23 else None
    return owner, start, proposal, basis


def worker_payload(start, diagnosis="PSEUDO"):
    """What the worker publishes for the first proposal of ``start``: (owner, proposal, payload)."""
    owner = k.KOwner(start, TABLE)
    info = KInfoSupplement() if start.policy_id in (POLICY_K_LC1, POLICY_K_D23) else None
    explainer = KD23Explainer(diagnosis) if start.policy_id == POLICY_K_D23 else None
    proposal = owner.propose(start)
    return owner, proposal, worker._k_proposal_payload(proposal, info, owner, explainer)


class ExactCalls:
    """Counts every exact call. K's own call and the three additional seams all leave through
    simple_probability.calculate_probabilities, which each of them looks up at call time."""

    def __enter__(self):
        import simple_probability
        self.count, self._module = 0, simple_probability
        self._original = simple_probability.calculate_probabilities

        def counted(*args, **kwargs):
            self.count += 1
            return self._original(*args, **kwargs)

        simple_probability.calculate_probabilities = counted
        return self

    def __exit__(self, *_error):
        self._module.calculate_probabilities = self._original
        return False


def drive_worker(start, replies, environment):
    """The worker's ``serve`` in this process. The parent side follows the product's order: every PROPOSAL
    is validated, every permit is answered by the next (status, observation) of ``replies`` and a PLAYING
    acknowledgement is followed by NEXT. Returns (exit code, everything the worker published)."""
    outputs, memory = [], {"proposal": None, "ack": None, "inputs": 0}

    def read(_directory, _direction, sequence, run):
        if sequence == 0:
            return message(run, sequence, "START", k.to_dict(start))
        last = outputs[-1]
        if last["kind"] == "PROPOSAL":
            proposal = b.split_payload(last["payload"])[0]
            memory["proposal"] = proposal
            request = k.KValidation(proposal.snapshot, proposal.token, uuid4().hex, proposal.pending_m_revision)
            return message(run, sequence, "VALIDATE", k.to_dict(request))
        if last["kind"] == "ADMITTED":
            status, observation = replies[memory["inputs"]]
            memory["inputs"] += 1
            memory["ack"] = k.make_ack(k.from_dict(last["payload"], k.KPermit), status, observation)
            return message(run, sequence, "ACK", k.to_dict(memory["ack"]))
        if last["kind"] == "ACKED":
            following = k.next_snapshot(memory["proposal"], memory["ack"])
            return message(run, sequence, "NEXT", k.to_dict(following))
        raise AssertionError("the worker was asked again after " + last["kind"])

    with patch.dict(os.environ, environment), patch.object(worker, "read_next", side_effect=read), \
            patch.object(worker, "write_once", side_effect=lambda _d, _c, _s, envelope: outputs.append(envelope)):
        code = worker.serve("unused", start.run_id)
    return code, outputs


class LiveKD23Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.now = 0.0

    # ---- helpers: the real parent job with a fake process -------------------------------------------------
    def start_job(self, start, diagnosis="PSEUDO"):
        job = jobs.LivePolicyJob(clock=lambda: self.now)
        self.addCleanup(job.shutdown)
        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        with patch.dict(os.environ, {b.DIAGNOSIS_ENV: diagnosis}), \
                patch.object(jobs.subprocess, "Popen", return_value=process), \
                patch.object(jobs, "create_scope", return_value=None):
            job.start(start)
        job.timer.stop()
        return job, process

    @staticmethod
    def publish(job, kind, payload):
        write_once(job._directory, "worker", job._sequence,
                   message(job.active_run_id, job._sequence, kind, payload))
        job.poll()

    def admit(self, job, owner, proposal):
        nonce = uuid4().hex
        job.validate_pending(proposal.snapshot, nonce)
        request = read_next(job._directory, "parent", job._sequence, job.active_run_id)
        self.assertEqual(request["kind"], "VALIDATE")
        granted = owner.validate(k.from_dict(request["payload"], k.KValidation))
        self.publish(job, "ADMITTED", k.to_dict(granted))
        self.assertEqual(job.state, "admitted")
        return nonce

    def finish(self, job, process, code):
        process.poll.return_value = code
        job.poll()
        return job.last_record

    def assert_nothing_kept(self, job):
        self.assertIsNone(job.pending)
        self.assertIsNone(job.pending_info)
        self.assertIsNone(job.pending_basis)
        self.assertIsNone(job._pending_info)
        self.assertIsNone(job._pending_basis)

    def assert_refused(self, call, text):
        with self.assertRaises(LivePolicyError) as caught:
            call()
        self.assertIn(text, str(caught.exception))

    # ---- tests ------------------------------------------------------------------------------------------
    def test_d01_identifier_label_phase_and_definitions_are_new_and_distinct(self):
        self.assertEqual(POLICY_K_D23, "K_D23")
        self.assertTrue(k.is_k_policy(POLICY_K_D23))
        self.assertEqual((k.policy_label(POLICY_K_D23), k.normal_phase(POLICY_K_D23)), ("K", "K_D23"))
        new = {mode: k.definition_for_entry(mode, POLICY_K_D23)
               for mode in (k.CANONICAL_NEW, k.ADOPT_CURRENT, k.FLAG_ADOPT, k.FIXED_BOARD)}
        self.assertEqual(new, {
            k.CANONICAL_NEW: "K_D23_OPENING_GUESS_STRUCTURE_FIRST_INPUT_V1",
            k.ADOPT_CURRENT: "K_D23_PUBLIC_ADOPT_OPENING_GUESS_STRUCTURE_FIRST_INPUT_V1",
            k.FLAG_ADOPT: "K_D23_PUBLIC_FLAG_ADOPT_LOCAL_BOOTSTRAP_V1",
            k.FIXED_BOARD: "K_D23_PUBLIC_FIXED_BOARD_OPENING_GUESS_STRUCTURE_V1"})
        self.assertEqual(len(set(new.values())), 4)
        # The three existing policies keep their names, phases and definitions.
        old = {
            POLICY_K: ("K-P0", "K_P0", "K_P0_NATIVE_DEFAULT_FIRST_INPUT_V1",
                       "K_P0_PUBLIC_ADOPT_NATIVE_DEFAULT_FIRST_INPUT_V1",
                       "K_P0_PUBLIC_FLAG_ADOPT_LOCAL_BOOTSTRAP_V1", "K_P0_PUBLIC_FIXED_BOARD_NATIVE_V1"),
            POLICY_K_LC0: ("K-LC0", "K_LC0", "K_LC0_DISTANCE_BAND_FIRST_INPUT_V1",
                           "K_LC0_PUBLIC_ADOPT_DISTANCE_BAND_FIRST_INPUT_V1",
                           "K_LC0_PUBLIC_FLAG_ADOPT_LOCAL_BOOTSTRAP_V1",
                           "K_LC0_PUBLIC_FIXED_BOARD_DISTANCE_BAND_V1"),
            POLICY_K_LC1: ("K-LC1", "K_LC1", "K_LC1_SINGLETON_BAND_FIRST_INPUT_V1",
                           "K_LC1_PUBLIC_ADOPT_SINGLETON_BAND_FIRST_INPUT_V1",
                           "K_LC1_PUBLIC_FLAG_ADOPT_LOCAL_BOOTSTRAP_V1",
                           "K_LC1_PUBLIC_FIXED_BOARD_SINGLETON_BAND_V1")}
        self.assertEqual((POLICY_K, POLICY_K_LC0, POLICY_K_LC1), ("K_P0", "K_LC0", "K_LC1"))
        for policy, (label, phase, *definitions) in old.items():
            with self.subTest(policy=policy):
                self.assertEqual((k.policy_label(policy), k.normal_phase(policy)), (label, phase))
                self.assertEqual([k.definition_for_entry(mode, policy) for mode in
                                  (k.CANONICAL_NEW, k.ADOPT_CURRENT, k.FLAG_ADOPT, k.FIXED_BOARD)], definitions)
                self.assertFalse(set(definitions) & set(new.values()))
        # A snapshot of one policy with a definition of another is no valid snapshot.
        mixed = state_of("KEPT")
        with self.assertRaises(LivePolicyError):
            replace(mixed, definition=k.LC1_ADOPT_DEFINITION)
        with self.assertRaises(LivePolicyError):
            replace(mixed, phase=k.PHASE_LC1)

    def test_d02_same_public_state_gives_the_accepted_ft_choice(self):
        for name in DECISIONS + ("CERTAIN_OTHER",):
            with self.subTest(state=name):
                owner, start, proposal, basis = decide(name)
                # The accepted composition, called apart on a fresh session of the same public state.
                session = KLocalSession(start.width, start.height, start.num_mines)
                accepted = combined_policy.select_combined_policy(
                    session.analyze_decision(start.observation, status=PLAYING), start.cursor, TABLE)
                guess = accepted.branch == combined_policy.BRANCH_GUESS
                self.assertEqual((proposal.action, proposal.x, proposal.y, proposal.category),
                                 (accepted.move.action.name, accepted.move.x, accepted.move.y, accepted.category))
                self.assertEqual((basis.branch, basis.input_changed), (accepted.branch, accepted.input_changed))
                self.assertEqual(basis.reason, accepted.guess.selection_reason if guess else accepted.opening.reason)
                kept = accepted.inner.selected.move
                self.assertEqual(basis.original, (kept.action.name, kept.x, kept.y))
                expected = STATES[name]["expected"]
                self.assertEqual(basis.branch, expected["branch"])
                if name == "CERTAIN_OTHER":
                    continue
                self.assertEqual([proposal.action, proposal.x, proposal.y], expected["input"])
                self.assertEqual(proposal.category, expected["category"])
                self.assertEqual(basis.reason, expected["reason"])
                self.assertEqual(list(basis.original), expected["original"])
                self.assertEqual(basis.input_changed, expected["input_changed"])
                if "risk" in expected:
                    self.assertEqual(list(basis.risk), expected["risk"])
                    self.assertEqual(basis.calls[0], expected["lookahead_calls"])
                if "pair" in expected:
                    self.assertEqual([list(cell) for cell in basis.pair], expected["pair"])
                if "minimum_mine_worlds" in expected:
                    self.assertEqual(proposal.probabilities.selected_mine_worlds, expected["minimum_mine_worlds"])
                if "short" in expected:
                    self.assertEqual(basis.short, expected["short"])

    def test_d03_one_original_selection_and_no_recomputation_in_validation_or_basis(self):
        original = KLocalSession.analyze_decision
        with ExactCalls() as exact, \
                patch.object(KLocalSession, "analyze_decision", autospec=True, side_effect=original) as analyze:
            start = state_of("FORCED_ABOVE_MINIMUM")
            owner = k.KOwner(start, TABLE)
            owner._select = Mock(wraps=owner._select)
            owner._singleton_adapter = Mock(wraps=owner._singleton_adapter)
            owner._combined_adapter = Mock(wraps=owner._combined_adapter)
            proposal = owner.propose(start)
            decided, combined, selection = exact.count, owner.combined_selection, owner.selection
            # Validation at proposal time and the explanation: no exact call at all.
            none = KD23Explainer("NONE").describe(owner, proposal)
            self.assertEqual(exact.count, decided)
            # Each diagnosis adds exactly its own counted calls and nothing else.
            pseudo = KD23Explainer("PSEUDO").describe(owner, proposal)
            self.assertEqual(exact.count - decided, pseudo.calls[1])
            after_pseudo = exact.count
            linked = KD23Explainer("PSEUDO_LINKED").describe(owner, proposal)
            self.assertEqual(exact.count - after_pseudo, linked.calls[1] + linked.calls[2])
            settled = exact.count
            for _ in range(3):  # the permit validation, repeated
                permit(owner, proposal)
            self.assertEqual(exact.count, settled)
            self.assertEqual(analyze.call_count, 1)
        self.assertEqual((owner._select.call_count, owner._singleton_adapter.call_count,
                          owner._combined_adapter.call_count), (1, 1, 1))
        self.assertIs(owner._combined_adapter.call_args.args[0], owner.singleton_selection)
        self.assertIs(owner.combined_selection, combined)
        self.assertIs(owner.selection, selection)
        self.assertIs(combined.inner, owner.singleton_selection)
        self.assertIs(owner.selection, owner.singleton_selection.selected)
        self.assertEqual(none.calls, (8, 0, 0))
        self.assertEqual((pseudo.calls[0], pseudo.calls[2]), (8, 0))
        self.assertEqual((linked.calls[0], linked.calls[1]), (8, pseudo.calls[1]))
        self.assertGreater(linked.calls[2], 0)
        self.assertEqual(combined.guess.actual_calls, 8)

    def test_d04_proposal_rules_of_the_new_policy_and_unchanged_rules_of_the_three_old_ones(self):
        _, _, forced, _ = decide("FORCED_ABOVE_MINIMUM")
        _, _, applied, _ = decide("CERTAIN_APPLIED")
        _, _, tie, _ = decide("TIE_CHANGED")
        for proposal in (forced, applied, tie):  # the three new kinds of input are valid wire records
            self.assertEqual(k.from_dict(json.loads(json.dumps(k.to_dict(proposal))), k.KProposal), proposal)
        self.assertEqual((forced.category, applied.category, tie.category),
                         ("FORCED_5050_GUESS", "PROVEN_OPENING_OPEN", "TIE_LOOKAHEAD_GUESS"))
        refused = (
            ("forced target under the tie category", lambda: replace(forced, category="TIE_LOOKAHEAD_GUESS")),
            ("forced target under the kept category", lambda: replace(forced, category="EXACT_MINIMUM_RISK_GUESS")),
            ("a cell that is not half risk as a forced target", lambda: replace(forced, x=4, y=1)),
            ("a certain category on a guess", lambda: replace(forced, category="DIRECT_SAFE_OPEN")),
            ("an opening category on a guess", lambda: replace(forced, category="PROVEN_OPENING_OPEN")),
            ("a tie change that keeps the original target", lambda: replace(tie, x=0, y=2)),
            ("a tie target outside the minimum cells", lambda: replace(tie, x=1, y=1)),
            ("a guess category on a certain input", lambda: replace(applied, category="FORCED_5050_GUESS")),
            ("an unknown category", lambda: replace(applied, category="OPENING")),
            ("an opening on a known mine", lambda: replace(applied, x=3)),
        )
        for label, make in refused:
            with self.subTest(new_policy=label), self.assertRaises(LivePolicyError):
                make()
        # The same contents under an old policy identifier: every new kind of input is refused there.
        for policy in OLD_POLICIES:
            _, _, guess, _ = decide("FORCED_ABOVE_MINIMUM", policy=policy)
            _, _, certain, _ = decide("CERTAIN_APPLIED", policy=policy)
            self.assertEqual(guess.category, "EXACT_MINIMUM_RISK_GUESS")
            self.assertIn((guess.x, guess.y), guess.probabilities.minimum_risk_cells)
            old_refused = (
                ("a half-risk cell above the minimum", lambda: replace(guess, x=3, y=0)),
                ("the forced category", lambda: replace(guess, category="FORCED_5050_GUESS")),
                ("the tie category", lambda: replace(guess, category="TIE_LOOKAHEAD_GUESS")),
                ("the opening category", lambda: replace(certain, category="PROVEN_OPENING_OPEN")),
            )
            for label, make in old_refused:
                with self.subTest(old_policy=policy, case=label), self.assertRaises(LivePolicyError):
                    make()

    def test_d05_original_projection_keeps_its_meaning_and_the_shown_risk_is_the_targets(self):
        owner, _, proposal, basis = decide("FORCED_ABOVE_MINIMUM")
        exact = proposal.probabilities
        counts = {(x, y): count for x, y, count in exact.cells}
        # The table is the ORIGINAL projection: the K-LC1 target and its minimum risk.
        self.assertEqual(exact, k.project_exact_guess(owner.decision, owner.selection))
        self.assertEqual((exact.total_worlds, exact.selected_mine_worlds), (8, 2))
        self.assertEqual(exact.minimum_risk_cells[0], (4, 0))
        self.assertEqual((owner.selection.move.x, owner.selection.move.y), (4, 0))
        self.assertEqual(counts[(4, 0)], exact.selected_mine_worlds)
        # The actual target is another cell; its own exact count is what the basis and the text show.
        self.assertEqual((proposal.x, proposal.y), (3, 0))
        self.assertEqual(basis.risk, (counts[(3, 0)], exact.total_worlds))
        self.assertEqual(basis.risk, (4, 8))
        self.assertNotEqual(basis.risk[0], exact.selected_mine_worlds)
        shown = live_analysis.present_k_proposal(proposal, None, basis)
        self.assertEqual(shown.status_text, "K | 추측: OPEN (3, 0) | " + basis.short)
        self.assertIn("이 칸의 지뢰 확률 50.0%", shown.status_text)
        self.assertEqual(shown.move, proposal.move)
        target = shown.overlays[(3, 0)]
        self.assertTrue(target.recommended)
        self.assertEqual((target.probability.mine_worlds, target.probability.total_worlds), (4, 8))
        self.assertFalse(shown.overlays[(4, 0)].recommended)
        with self.assertRaises(ValueError):  # a basis of another proposal is never shown with this one
            live_analysis.present_k_proposal(proposal, None, replace(basis, token="c" * 32))
        # K-LC1 on the same public state still shows its own target with the minimum risk.
        _, _, old, _ = decide("FORCED_ABOVE_MINIMUM", policy=POLICY_K_LC1)
        self.assertEqual(old.probabilities, exact)
        self.assertTrue(live_analysis.present_k_proposal(old).status_text.startswith(
            "K-LC1 | 추측: OPEN (4, 0) | 지뢰 확률 "))

    def test_d06_basis_fields_types_presence_and_binding(self):
        self.assertEqual(tuple(field.name for field in fields(b.KProposalBasis)), BASIS_FIELDS)
        for name in DECISIONS:
            with self.subTest(state=name):
                owner, _, proposal, basis = decide(name)
                guess = proposal.is_guess
                self.assertIs(type(basis), b.KProposalBasis)
                self.assertEqual((basis.basis_id, basis.token, basis.diagnosis),
                                 ("K_D23_BASIS_V1", proposal.token, "PSEUDO"))
                for text in (basis.short, basis.head_proposed, basis.head_executed):
                    self.assertIs(type(text), str)
                self.assertEqual((type(basis.original), [type(part) for part in basis.original]),
                                 (tuple, [str, int, int]))
                self.assertIs(type(basis.input_changed), bool)
                for lines in (basis.body, basis.pseudo, basis.linked, basis.loss):
                    self.assertIs(type(lines), tuple)
                    self.assertTrue(all(type(text) is str and text and "\n" not in text for text in lines))
                self.assertEqual([type(value) for value in basis.calls], [int, int, int])
                self.assertEqual([type(value) for value in basis.stage_ns], [int, int, int, int])
                # Presence rules.
                self.assertEqual(basis.branch, b.BRANCH_GUESS if guess else b.BRANCH_CERTAIN)
                self.assertTrue(basis.body and basis.loss)
                if guess:
                    self.assertEqual([type(value) for value in basis.risk], [int, int])
                    self.assertIs(type(basis.head_blocked), str)
                    self.assertTrue(basis.pseudo)
                    self.assertEqual(basis.linked, ())
                    self.assertEqual(basis.calls[2], 0)
                else:
                    self.assertEqual((basis.risk, basis.pair, basis.head_blocked), (None, None, None))
                    self.assertEqual((basis.pseudo, basis.linked, basis.calls), ((), (), (0, 0, 0)))
                self.assertEqual(basis.pair is not None, basis.reason == b.FORCED)
                # Binding: content, proposal and configuration.
                self.assertEqual(basis.binding_sha256, b.basis_digest(proposal, basis))
                self.assertIs(b.validate_basis(proposal, basis, "PSEUDO"), basis)
                wire = json.loads(json.dumps(b.basis_to_dict(basis)))
                self.assertEqual(set(wire), set(BASIS_FIELDS))
                self.assertEqual(b.basis_from_dict(wire), basis)
                payload = worker._k_proposal_payload(proposal, KInfoSupplement(), owner, KD23Explainer("PSEUDO"))
                self.assertEqual(set(payload), set(k.to_dict(proposal)) | {"info", "basis"})
                received, has_info, raw_info, has_basis, raw_basis = b.split_payload(json.loads(json.dumps(payload)))
                self.assertEqual((received, has_info, has_basis), (proposal, True, True))
                again = b.receive_basis(received, has_basis, raw_basis, "PSEUDO")
                # The record is written again for the same pending proposal: everything but its timings
                # is the same content, and each record carries its own binding.
                self.assertEqual(replace(again, stage_ns=basis.stage_ns, binding_sha256=basis.binding_sha256), basis)
                self.assertIs(type(k.receive_info(received, has_info, raw_info)), k.KProposalInfo)
                self.assertTrue(b.basis_required(proposal))
        _, _, old, _ = decide("KEPT", policy=POLICY_K_LC1)
        self.assertFalse(b.basis_required(old))

    def test_d07_a_basis_of_another_proposal_or_with_wrong_content_is_refused(self):
        _, _, proposal, basis = decide("FORCED_ABOVE_MINIMUM")
        _, _, other, other_basis = decide("FORCED_ABOVE_MINIMUM")   # same public state, another run and token
        raw = b.basis_to_dict(basis)
        self.assertEqual(b.receive_basis(proposal, True, json.loads(json.dumps(raw)), "PSEUDO"), basis)
        self.assert_refused(lambda: b.receive_basis(proposal, False, None, "PSEUDO"), "K_D23_BASIS:MISSING")
        start = canonical(8, 2, 1)
        first = k.KOwner(start, TABLE).propose(start)
        self.assert_refused(lambda: b.receive_basis(first, True, raw, "PSEUDO"), "K_D23_BASIS:UNEXPECTED")
        self.assertIsNone(b.receive_basis(first, False, None, "PSEUDO"))
        _, _, old, _ = decide("FORCED_ABOVE_MINIMUM", policy=POLICY_K_LC1)
        self.assert_refused(lambda: b.receive_basis(old, True, raw, "PSEUDO"), "K_D23_BASIS:UNEXPECTED")

        def changed(**values):
            return {**json.loads(json.dumps(raw)), **values}

        missing_field = changed()
        del missing_field["loss"]
        wrong = {
            "the basis of another proposal": b.basis_to_dict(other_basis),
            "another token": changed(token=other.token),
            "a risk that is not the target's": changed(risk=[2, 8]),
            "the minimum written as the original": changed(original=["OPEN", 3, 0]),
            "an original outside the board": changed(original=["OPEN", 29, 0]),
            "a pair without the target": changed(pair=[[4, 0], [4, 1]]),
            "a pair in the wrong order": changed(pair=[[3, 1], [3, 0]]),
            "another reason": changed(reason="TIE_LOOKAHEAD"),
            "another branch": changed(branch="CERTAIN_D2"),
            "an unknown reason": changed(reason="BEST_GUESS"),
            "another sentence under the same binding": changed(short="최소 위험 칸 유지 · 이 칸의 지뢰 확률 50.0%"),
            "another loss line under the same binding": changed(loss=["다른 문장"]),
            "a short line with a separator": changed(short="가 | 나"),
            "a line break inside a line": changed(body=["첫 줄\n둘째 줄"]),
            "an empty body": changed(body=[]),
            "text in place of the risk": changed(risk="4/8"),
            "a boolean call count": changed(calls=[True, 0, 0]),
            "a call count above its limit": changed(calls=[73, 0, 0]),
            "a fractional timing": changed(stage_ns=[1.5, 0, 0, 0]),
            "text in place of the lines": changed(body="선택 이유"),
            "a number in place of a flag": changed(input_changed=1),
            "linked lines without the linked configuration": changed(linked=["줄"]),
            "an extra field": changed(extra=1),
            "a missing field": missing_field,
            "not an object": [raw],
        }
        for label, value in wrong.items():
            with self.subTest(case=label):
                self.assert_refused(lambda: b.receive_basis(proposal, True, value, "PSEUDO"),
                                    "K_D23_BASIS:RECEIVED_INVALID")
        # The same record under another diagnosis configuration of the run.
        for configuration in ("NONE", "PSEUDO_LINKED", "FULL"):
            with self.subTest(configuration=configuration):
                self.assert_refused(lambda: b.receive_basis(proposal, True, json.loads(json.dumps(raw)), configuration),
                                    "K_D23_BASIS:RECEIVED_INVALID")
        # The error keeps the kind and the message of what was wrong; it is not one fixed sentence.
        with self.assertRaises(LivePolicyError) as caught:
            b.receive_basis(proposal, True, changed(risk=[2, 8]), "PSEUDO")
        self.assertIn("LivePolicyError: K basis risk is not the exact value of the actual target.", str(caught.exception))

    def test_d08_diagnosis_configuration_is_fixed_for_a_run_and_named_in_every_basis(self):
        self.assertEqual(b.DIAGNOSIS_ENV, "MINESWEEPER_K_D23_DIAGNOSIS")
        self.assertEqual(b.DIAGNOSES, ("NONE", "PSEUDO", "PSEUDO_LINKED"))
        # The product default (2026-11-21): absent or empty means NONE. An explicit value stays that value.
        self.assertEqual(b.diagnosis_from_environment({}), "NONE")
        self.assertEqual(b.diagnosis_from_environment({b.DIAGNOSIS_ENV: ""}), "NONE")
        for value in b.DIAGNOSES:
            self.assertEqual(b.diagnosis_from_environment({b.DIAGNOSIS_ENV: value}), value)
        # The default reaches the real parent job: without the variable the run is NONE and its basis says NONE.
        unset_start = state_of("FORCED_ABOVE_MINIMUM")
        unset_process = Mock()
        unset_process.poll.return_value = None
        unset_process.wait.return_value = 0
        with patch.dict(os.environ), patch.object(jobs.subprocess, "Popen", return_value=unset_process), \
                patch.object(jobs, "create_scope", return_value=None):
            os.environ.pop(b.DIAGNOSIS_ENV, None)
            unset_job = jobs.LivePolicyJob(clock=lambda: self.now)
            self.addCleanup(unset_job.shutdown)
            unset_job.start(unset_start)
            unset_job.timer.stop()
        self.assertEqual(unset_job._k_diagnosis, "NONE")
        _, _, unset_payload = worker_payload(unset_start, b.diagnosis_from_environment({}))
        self.publish(unset_job, "PROPOSAL", json.loads(json.dumps(unset_payload)))
        self.assertEqual((unset_job.state, unset_job.pending_basis.diagnosis, unset_job.pending_basis.pseudo),
                         ("pending", "NONE", ()))
        for value in ("pseudo", "LINKED", "0"):
            with self.subTest(value=value), self.assertRaises(LivePolicyError):
                b.diagnosis_from_environment({b.DIAGNOSIS_ENV: value})
        for value in ("LINKED", None, 1):
            with self.subTest(explainer=value), self.assertRaises(LivePolicyError):
                KD23Explainer(value)
        start = state_of("FORCED_ABOVE_MINIMUM")
        owner = k.KOwner(start, TABLE)
        proposal = owner.propose(start)
        shown = {}
        for configuration in b.DIAGNOSES:
            with self.subTest(configuration=configuration):
                explainer = KD23Explainer(configuration)
                basis = explainer.describe(owner, proposal)
                self.assertEqual((basis.diagnosis, explainer.diagnosis), (configuration, configuration))
                self.assertEqual(bool(basis.pseudo), configuration != "NONE")
                self.assertEqual(bool(basis.linked), configuration == "PSEUDO_LINKED")
                self.assertTrue(configuration != "NONE" or basis.calls[1] == 0)
                self.assertEqual(basis.calls[2] > 0, configuration == "PSEUDO_LINKED")
                lines = b.detail_lines(basis, b.EXECUTED)
                at_pseudo, at_linked = lines.index(b.PSEUDO_TITLE), lines.index(b.LINKED_TITLE)
                self.assertLess(lines.index(b.SELECTION_TITLE), at_pseudo)
                self.assertLess(at_pseudo, at_linked)
                # What the configuration does not compute is written as not computed, never as a result.
                self.assertEqual(lines[at_pseudo + 1] == b.NOT_COMPUTED, configuration == "NONE")
                self.assertEqual(lines[at_linked + 1] == b.NOT_COMPUTED, configuration != "PSEUDO_LINKED")
                self.assertEqual(lines[at_pseudo + 1:at_linked], basis.pseudo or (b.NOT_COMPUTED,))
                self.assertEqual(lines[at_linked + 1:], basis.linked or (b.NOT_COMPUTED,))
                shown[configuration] = basis
        # The selection and its reason do not depend on the diagnosis configuration.
        for name in ("branch", "reason", "original", "input_changed", "risk", "pair", "short", "head_proposed",
                     "head_blocked", "head_executed", "body", "loss"):
            self.assertEqual(len({repr(getattr(basis, name)) for basis in shown.values()}), 1, name)
        self.assertEqual(shown["PSEUDO"].pseudo, shown["PSEUDO_LINKED"].pseudo)
        # A certain decision has no diagnosis under any configuration.
        certain_start = state_of("CERTAIN_APPLIED")
        certain_owner = k.KOwner(certain_start, TABLE)
        certain = KD23Explainer("PSEUDO_LINKED").describe(certain_owner, certain_owner.propose(certain_start))
        self.assertEqual((certain.diagnosis, certain.pseudo, certain.linked, certain.calls),
                         ("PSEUDO_LINKED", (), (), (0, 0, 0)))
        self.assertNotIn(b.PSEUDO_TITLE, b.detail_lines(certain, b.EXECUTED))

    def test_d09_first_input_and_flag_preparation_are_not_policy_decisions(self):
        explainer = KD23Explainer("PSEUDO_LINKED")
        start = canonical(8, 2, 1)
        with ExactCalls() as exact, \
                patch.object(KLocalSession, "analyze_decision", side_effect=AssertionError("first input")):
            owner = k.KOwner(start, TABLE)
            first = owner.propose(start)
            self.assertIsNone(explainer.describe(owner, first))
            permit(owner, first)
            self.assertEqual(exact.count, 0)
        self.assertTrue(first.initial)
        self.assertEqual((first.action, first.x, first.y, first.category, first.continuation),
                         ("OPEN", 0, 0, "POLICY_INITIAL_OPEN", "INITIAL"))
        self.assertIsNone(owner.combined_selection)
        self.assertFalse(b.basis_required(first))
        self.assertFalse(k.info_required(first))
        self.assertEqual(set(worker._k_proposal_payload(first, KInfoSupplement(), owner, explainer)),
                         set(k.to_dict(first)))
        # A flag adoption: the bootstrap and every preparation input have no combined selection either.
        flagged = flagged_start()
        with ExactCalls() as exact, \
                patch.object(KLocalSession, "analyze_decision", side_effect=AssertionError("preparation")):
            owner = k.KOwner(flagged, TABLE)
            summary = owner.bootstrap_proof.summary
            self.assertEqual((summary.retained, summary.removable), (((1, 0),), ((3, 0),)))
            preparing = owner.expected
            self.assertEqual(preparing.phase, k.PHASE_PREPARATION)
            prepare = owner.propose(preparing)
            self.assertIsNone(explainer.describe(owner, prepare))
            granted = permit(owner, prepare)
            self.assertEqual(exact.count, 0)
        self.assertTrue(prepare.is_preparation)
        self.assertEqual((prepare.action, prepare.x, prepare.y, prepare.kind, prepare.category),
                         ("FLAG", 3, 0, "prepare", "K_PREPARATION_UNFLAG"))
        self.assertIsNone(owner.combined_selection)
        self.assertFalse(b.basis_required(prepare))
        self.assertFalse(k.info_required(prepare))
        self.assertEqual(set(worker._k_proposal_payload(prepare, KInfoSupplement(), owner, explainer)),
                         set(k.to_dict(prepare)))
        # After the preparation the first decision is a policy decision with its basis.
        following = owner.acknowledge(k.make_ack(granted, "PLAYING", summary.observation_after(1)))
        self.assertEqual((following.phase, following.input_seq, following.preparation_seq), (k.PHASE_D23, 0, 1))
        decision = owner.propose(following)
        basis = explainer.describe(owner, decision)
        self.assertFalse(decision.is_preparation or decision.initial)
        self.assertTrue(b.basis_required(decision))
        self.assertIsNotNone(owner.combined_selection)
        self.assertEqual((basis.branch, basis.token), (b.BRANCH_CERTAIN, decision.token))

    def test_d10_entry_modes_new_fixed_adopt_and_flag_adopt_reach_a_policy_decision(self):
        explainer = KD23Explainer("PSEUDO")
        # New game: the canonical first input, its acknowledgement, then the first decision.
        start = canonical(8, 2, 1)
        owner = k.KOwner(start, TABLE)
        first = owner.propose(start)
        following = owner.acknowledge(k.make_ack(permit(owner, first), "PLAYING", S8_AFTER_FIRST))
        decision = owner.propose(following)
        basis = explainer.describe(owner, decision)
        self.assertEqual((start.entry_mode, start.definition), (k.CANONICAL_NEW, k.D23_DEFINITION))
        self.assertEqual((decision.action, decision.x, decision.y, decision.category),
                         ("OPEN", 5, 0, "PROVEN_OPENING_OPEN"))
        self.assertEqual((basis.branch, basis.reason), (b.BRANCH_CERTAIN, b.OPENING))
        permit(owner, decision)
        # Fixed board: no canonical first input; the very first proposal is a policy decision.
        start = fixed_board(6, 2, 2)
        owner = k.KOwner(start, TABLE)
        decision = owner.propose(start)
        basis = explainer.describe(owner, decision)
        self.assertEqual((start.entry_mode, start.definition), (k.FIXED_BOARD, k.D23_FIXED_DEFINITION))
        self.assertFalse(decision.initial)
        self.assertTrue(decision.is_guess)
        self.assertEqual((decision.action, decision.x, decision.y, decision.category),
                         ("OPEN", 0, 0, "EXACT_MINIMUM_RISK_GUESS"))
        self.assertEqual((basis.branch, basis.reason, basis.calls[0]), (b.BRANCH_GUESS, b.KEPT, 0))
        self.assertEqual(Fraction(*basis.risk), Fraction(1, 6))
        permit(owner, decision)
        # Current state: a new owner adopts one public grid; the first proposal is a policy decision.
        owner, start, decision, basis = decide("FORCED_KEPT")
        self.assertEqual((start.entry_mode, start.definition), (k.ADOPT_CURRENT, k.D23_ADOPT_DEFINITION))
        self.assertFalse(decision.initial)
        self.assertEqual((decision.x, decision.y, basis.reason), (3, 0, b.FORCED))
        self.assertEqual(owner.session.M, frozenset(decision.preinput_m))
        permit(owner, decision)
        # Flags: bootstrap, one preparation input, then a policy decision.
        start = flagged_start()
        owner = k.KOwner(start, TABLE)
        prepare = owner.propose(owner.expected)
        following = owner.acknowledge(k.make_ack(permit(owner, prepare), "PLAYING",
                                                 owner.bootstrap_proof.summary.observation_after(1)))
        decision = owner.propose(following)
        basis = explainer.describe(owner, decision)
        self.assertEqual((start.entry_mode, start.definition), (k.FLAG_ADOPT, k.D23_FLAG_ADOPT_DEFINITION))
        self.assertEqual((decision.snapshot.phase, basis.branch), (k.PHASE_D23, b.BRANCH_CERTAIN))
        self.assertEqual(decision.preinput_m, ((1, 0),))
        permit(owner, decision)

    def test_d11_input_permit_revalidates_the_current_state_without_recomputation(self):
        original = KLocalSession.analyze_decision
        with ExactCalls() as exact, \
                patch.object(KLocalSession, "analyze_decision", autospec=True, side_effect=original) as analyze:
            owner, _, proposal, _ = decide("FORCED_ABOVE_MINIMUM", "NONE")
            other_owner, _, _, _ = decide("FORCED_ABOVE_MINIMUM", "NONE")
            settled, analysed = exact.count, analyze.call_count
            owner._validate_combined = Mock(wraps=owner._validate_combined)
            granted = permit(owner, proposal)
            self.assertEqual(owner._validate_combined.call_count, 1)
            call = owner._validate_combined.call_args
            self.assertEqual(call.args, (proposal.snapshot.observation, proposal.move))
            self.assertIs(call.kwargs["choice"], owner.combined_selection)
            self.assertIs(call.kwargs["decision"], owner.decision)
            self.assertEqual(call.kwargs["current_mines"], owner.session.M)
            self.assertEqual((call.kwargs["num_mines"], call.kwargs["cursor"]), (2, (0, 0)))
            self.assertIs(granted.proposal, proposal)
            # A state that is no longer the proposal's state: refused before any validation.
            stale = replace(proposal.snapshot, cursor=(1, 0))
            with self.assertRaises(LivePolicyError):
                owner.validate(k.KValidation(stale, proposal.token, uuid4().hex, proposal.pending_m_revision))
            with self.assertRaises(LivePolicyError):
                owner.validate(k.KValidation(proposal.snapshot, "c" * 32, uuid4().hex, proposal.pending_m_revision))
            with self.assertRaises(LivePolicyError):
                permit(owner, proposal, granted.nonce)  # a used nonce
            self.assertEqual(owner._validate_combined.call_count, 1)
            # A combined record that is not the original object of this decision.
            kept = owner.combined_selection
            for label, swapped in (("an equal copy", replace(kept)), ("another owner's", other_owner.combined_selection)):
                with self.subTest(record=label):
                    owner.combined_selection = swapped
                    with self.assertRaises(LivePolicyError):
                        permit(owner, proposal)
            owner.combined_selection = kept
            self.assertEqual(owner._validate_combined.call_count, 1)
            # The accepted validator itself refuses another input for this record.
            with self.assertRaises(Exception):
                owner._validate_combined(proposal.snapshot.observation, SimpleMove(Action.OPEN, 4, 0),
                                         status=PLAYING, num_mines=2, cursor=(0, 0),
                                         current_mines=owner.session.M, decision=owner.decision,
                                         choice=kept, table=owner.table)
            again = permit(owner, proposal)
            self.assertIs(owner.permit, again)
            self.assertNotEqual(again.nonce, granted.nonce)
            self.assertEqual((exact.count, analyze.call_count), (settled, analysed))

    def test_d12_proposed_blocked_and_executed_wording_differ_and_guess_off_adds_no_input(self):
        owner, _, proposal, basis = decide("FORCED_ABOVE_MINIMUM")
        self.assertTrue(basis.head_proposed.startswith("제안 대상: OPEN (3, 0). 이 칸의 지뢰 확률 50.0%"))
        self.assertTrue(basis.head_blocked.startswith("제안 대상: OPEN (3, 0). 이 칸의 지뢰 확률 50.0%"))
        self.assertTrue(basis.head_executed.startswith("실제 입력 대상: OPEN (3, 0). 이 입력의 지뢰 확률 50.0%"))
        self.assertTrue(basis.head_blocked.endswith("추측 허용이 꺼져 있어 입력하지 않았다. 실제 입력이 아니다."))
        for text in (basis.head_proposed, basis.head_blocked):
            self.assertNotIn("실제 입력 대상", text)
        self.assertNotIn("입력하지 않았다", basis.head_proposed)
        self.assertNotIn("입력하지 않았다", basis.head_executed)
        self.assertEqual(len({basis.head_proposed, basis.head_blocked, basis.head_executed}), 3)
        for state, head in ((b.PROPOSED, basis.head_proposed), (b.BLOCKED, basis.head_blocked),
                            (b.EXECUTED, basis.head_executed)):
            lines = b.detail_lines(basis, state)
            self.assertEqual(lines[:2], (b.SELECTION_TITLE, head))
            self.assertEqual(lines[2:2 + len(basis.body)], basis.body)
        with self.assertRaises(LivePolicyError):
            b.detail_lines(basis, "SENT")
        # A proposal that is only shown or held back changed nothing in the owner and is no loss cause.
        self.assertIs(owner.pending, proposal)
        self.assertIsNone(owner.permit)
        self.assertEqual(len(owner._nonces), 0)
        self.assertEqual(b.end_lines("PLAYING", b.LAST_K_DECISION, basis), ())
        # A certain input is a proposal or an actual input; it is never a blocked proposal.
        _, _, _, certain = decide("CERTAIN_APPLIED")
        self.assertEqual(certain.head_proposed, "제안 입력: OPEN (5, 0). 추측이 아닌 확정 입력이다.")
        self.assertEqual(certain.head_executed, "실제 입력: OPEN (5, 0). 추측이 아닌 확정 입력이다.")
        self.assertIsNone(certain.head_blocked)
        with self.assertRaises(LivePolicyError):
            b.detail_lines(certain, b.BLOCKED)
        self.assertEqual(b.detail_lines(certain, b.PROPOSED), (b.SELECTION_TITLE, certain.head_proposed, *certain.body))

    def test_d13_worker_protocol_start_validate_ack_next_and_terminal(self):
        start = canonical(8, 2, 1)
        original = KLocalSession.analyze_decision
        with patch.object(KLocalSession, "analyze_decision", autospec=True, side_effect=original) as analyze:
            code, outputs = drive_worker(
                start, [("PLAYING", S8_AFTER_FIRST), ("PLAYING", S8_AFTER_OPENING), ("WON", None)],
                {b.DIAGNOSIS_ENV: "PSEUDO_LINKED"})
        self.assertEqual(code, 0)
        self.assertEqual([envelope["kind"] for envelope in outputs],
                         ["PROPOSAL", "ADMITTED", "ACKED", "PROPOSAL", "ADMITTED", "ACKED", "PROPOSAL", "ADMITTED",
                          "FINISHED"])
        self.assertEqual([envelope["seq"] for envelope in outputs], list(range(9)))
        self.assertEqual(analyze.call_count, 2)  # two decisions; none for the first input, none after the end
        first, opening, guess = (outputs[index]["payload"] for index in (0, 3, 6))
        keys = set(k.to_dict(k.from_dict(first, k.KProposal)))
        self.assertEqual(len(keys), 14)
        self.assertEqual(set(first), keys)
        self.assertEqual(set(opening), keys | {"info", "basis"})
        self.assertEqual(set(guess), keys | {"info", "basis"})
        self.assertEqual([(payload["action"], payload["x"], payload["y"], payload["category"])
                          for payload in (first, opening, guess)],
                         [("OPEN", 0, 0, "POLICY_INITIAL_OPEN"), ("OPEN", 5, 0, "PROVEN_OPENING_OPEN"),
                          ("OPEN", 3, 0, "EXACT_MINIMUM_RISK_GUESS")])
        for payload, reason in ((opening, b.OPENING), (guess, b.FORCED)):
            proposal, has_info, raw_info, has_basis, raw_basis = b.split_payload(payload)
            basis = b.receive_basis(proposal, has_basis, raw_basis, "PSEUDO_LINKED")
            self.assertEqual((basis.reason, basis.diagnosis), (reason, "PSEUDO_LINKED"))
            self.assertIs(type(k.receive_info(proposal, has_info, raw_info)), k.KProposalInfo)
            self.assert_refused(lambda: b.receive_basis(proposal, has_basis, raw_basis, "PSEUDO"),
                                "K_D23_BASIS:RECEIVED_INVALID")
        self.assertTrue(basis.pseudo and basis.linked)
        self.assertEqual(basis.risk, (1, 2))
        # Each permit names its own proposal; the terminal receipt is the terminal acknowledgement.
        for at in (1, 4, 7):
            self.assertEqual(outputs[at]["payload"]["proposal"]["token"], outputs[at - 1]["payload"]["token"])
        self.assertEqual((outputs[8]["payload"]["status"], outputs[8]["payload"]["observation"]), ("WON", None))
        # K-LC1 through the same worker is as before: info on its decisions, never a basis.
        code, old = drive_worker(canonical(8, 2, 1, POLICY_K_LC1), [("PLAYING", S8_AFTER_FIRST), ("WON", None)],
                                 {b.DIAGNOSIS_ENV: "PSEUDO_LINKED"})
        self.assertEqual(code, 0)
        self.assertEqual([envelope["kind"] for envelope in old],
                         ["PROPOSAL", "ADMITTED", "ACKED", "PROPOSAL", "ADMITTED", "FINISHED"])
        self.assertEqual(set(old[0]["payload"]), keys)
        self.assertEqual(set(old[3]["payload"]), keys | {"info"})

    def test_d14_errors_in_selection_diagnosis_or_explanation_end_the_run_with_their_cause(self):
        cases = (
            ("SELECTION", "experiments.program_d23_policy.apply_combined", "PSEUDO",
             RuntimeError("selection fixture"), "K_D23:SELECTION RuntimeError: selection fixture"),
            ("VALIDATION", "experiments.program_d23_runner.validate_combined_execution", "PSEUDO",
             RuntimeError("validation fixture"), "K_D23:VALIDATION RuntimeError: validation fixture"),
            ("PSEUDO", "experiments.program_d3_pseudo_runner.diagnose_before_input", "PSEUDO",
             ValueError("pseudo fixture"), "K_D23:PSEUDO ValueError: pseudo fixture"),
            ("LINKED", "experiments.program_d23_link_runner.link_before_input", "PSEUDO_LINKED",
             KeyError("linked fixture"), "K_D23:LINKED KeyError: 'linked fixture'"),
            ("EXPLANATION", "experiments.program_d3_explanation.explain_decision", "PSEUDO",
             X.ExplanationError(X.MATERIAL, "explanation fixture"),
             "K_D23:EXPLANATION ExplanationError: EXPLANATION_MATERIAL: explanation fixture"),
        )
        original = KLocalSession.analyze_decision
        details = {}
        for stage, target, configuration, error, expected in cases:
            with self.subTest(stage=stage):
                start = state_of("FORCED_ABOVE_MINIMUM")
                with patch(target, side_effect=error), \
                        patch.object(KLocalSession, "analyze_decision", autospec=True, side_effect=original) as analyze:
                    code, outputs = drive_worker(start, [], {b.DIAGNOSIS_ENV: configuration})
                # Nothing is published but the error: no proposal, so no permit and no input can follow.
                self.assertEqual(code, 1)
                self.assertEqual([envelope["kind"] for envelope in outputs], ["ERROR"])
                payload = outputs[0]["payload"]
                self.assertEqual(payload["code"], "WORKER")
                self.assertEqual(payload["detail"], "LivePolicyError: " + expected)
                self.assertEqual(analyze.call_count, 1)  # no second analysis and no other policy
                details[stage] = payload["detail"]
        self.assertEqual(len(set(details.values())), len(cases))
        # A diagnosis that is not configured is not called, so its failure cannot end the run.
        with patch("experiments.program_d23_link_runner.link_before_input", side_effect=KeyError("unused")), \
                patch("experiments.program_d3_pseudo_runner.diagnose_before_input", side_effect=KeyError("unused")):
            code, outputs = drive_worker(state_of("FORCED_ABOVE_MINIMUM"), [("LOST", None)], {b.DIAGNOSIS_ENV: "NONE"})
        self.assertEqual((code, [envelope["kind"] for envelope in outputs]), (0, ["PROPOSAL", "ADMITTED", "FINISHED"]))
        # The parent ends the owner run with that cause and keeps nothing to apply.
        start = state_of("FORCED_ABOVE_MINIMUM")
        job, process = self.start_job(start)
        self.publish(job, "ERROR", {"code": "WORKER", "detail": details["LINKED"]})
        self.assertEqual(job.state, "cancelling")
        self.assert_nothing_kept(job)
        record = self.finish(job, process, 1)
        self.assertEqual((record["status"], record["cleanup_complete"], record["consumed_token_count"]),
                         ("FAILED", True, 0))
        self.assertIn("K_D23:LINKED KeyError: 'linked fixture'", record["error"])
        self.assertEqual((record["proposal_count"], record["validation_count"], record["k_basis_count"]), (0, 0, 0))

    def test_d15_job_keeps_info_and_basis_with_the_pending_proposal_and_drops_them_together(self):
        # 1) Kept through pause, permit and consumption; dropped at the terminal receipt.
        start = state_of("FORCED_ABOVE_MINIMUM")
        job, process = self.start_job(start)
        self.assertEqual(job._k_diagnosis, "PSEUDO")
        owner, proposal, payload = worker_payload(start)
        self.publish(job, "PROPOSAL", json.loads(json.dumps(payload)))
        self.assertEqual((job.state, job.pending), ("pending", proposal))
        basis, info = job.pending_basis, job.pending_info
        self.assertEqual(basis, b.basis_from_dict(json.loads(json.dumps(payload["basis"]))))
        self.assertIs(type(info), k.KProposalInfo)
        self.assertEqual((basis.token, info.token), (proposal.token, proposal.token))
        job.invalidate_admission()  # a pause
        self.assertIs(job.pending_basis, basis)
        self.assertIs(job.pending_info, info)
        nonce = self.admit(job, owner, proposal)
        self.assertIs(job.pending_basis, basis)
        job.mark_applying(proposal.token, nonce)
        self.assertIs(job.pending_basis, basis)   # read by the parent right after the consumption
        self.assertIs(job.pending_info, info)
        job.acknowledge("LOST")
        ack = job._sent_ack
        owner.acknowledge(ack)
        self.publish(job, "FINISHED", k.to_dict(ack))
        self.assert_nothing_kept(job)
        record = self.finish(job, process, 0)
        self.assertEqual((record["status"], record["k_diagnosis"], record["k_basis_count"]), ("SUCCEEDED", "PSEUDO", 1))
        self.assertEqual(sum(record["k_info_counts"].values()), 1)
        # 2) Dropped together with the pending proposal by a PLAYING acknowledgement; the next proposal
        #    brings its own records.
        start = state_of("FORCED_ABOVE_MINIMUM")
        job, process = self.start_job(start)
        owner, proposal, payload = worker_payload(start)
        self.publish(job, "PROPOSAL", payload)
        nonce = self.admit(job, owner, proposal)
        job.mark_applying(proposal.token, nonce)
        job.acknowledge("PLAYING", G5_AFTER_GUESS)
        ack = job._sent_ack
        following = owner.acknowledge(ack)
        self.publish(job, "ACKED", k.to_dict(ack))
        self.assertEqual(job.state, "ready")
        self.assert_nothing_kept(job)
        job.request(following)
        second = owner.propose(following)
        self.publish(job, "PROPOSAL", worker._k_proposal_payload(second, KInfoSupplement(), owner,
                                                                 KD23Explainer("PSEUDO")))
        self.assertEqual((job.pending, job.pending_basis.token, job.pending_info.token),
                         (second, second.token, second.token))
        self.assertNotEqual(second.token, proposal.token)
        # 3) Dropped together by a cancellation.
        job.cancel("manual")
        self.assert_nothing_kept(job)
        record = self.finish(job, process, 0)
        self.assertEqual((record["status"], record["k_basis_count"]), ("CANCELLED", 2))
        # 4) Integrity: a missing basis, a basis of another proposal, another configuration of the run.
        _, _, other_payload = worker_payload(state_of("FORCED_ABOVE_MINIMUM"))
        cases = (
            ("missing", "PSEUDO", lambda value: value.pop("basis"), "K_D23_BASIS:MISSING"),
            ("of another proposal", "PSEUDO", lambda value: value.update(basis=other_payload["basis"]),
             "K_D23_BASIS:RECEIVED_INVALID"),
            ("another configuration", "NONE", lambda value: None, "K_D23_BASIS:RECEIVED_INVALID"),
            ("missing info", "PSEUDO", lambda value: value.pop("info"), "KLC1_INFO"),
        )
        for label, configuration, change, expected in cases:
            with self.subTest(case=label):
                start = state_of("FORCED_ABOVE_MINIMUM")
                job, process = self.start_job(start, configuration)
                _, proposal, payload = worker_payload(start)
                payload = json.loads(json.dumps(payload))
                change(payload)
                self.publish(job, "PROPOSAL", payload)
                self.assertEqual(job.state, "cancelling")
                self.assertIn(expected, job._failure)
                self.assert_nothing_kept(job)
                record = self.finish(job, process, 1)
                self.assertEqual((record["status"], record["consumed_token_count"], record["k_basis_count"]),
                                 ("FAILED", 0, 0))
                self.assertTrue(record["cleanup_complete"])

    def test_d16_the_three_old_policies_keep_their_payload_rules_and_choices(self):
        for policy in OLD_POLICIES:
            for name in ("FORCED_ABOVE_MINIMUM", "CERTAIN_APPLIED", "TIE_CHANGED"):
                with self.subTest(policy=policy, state=name):
                    owner, _, proposal, _ = decide(name, policy=policy)
                    self.assertIsNone(owner.combined_selection)
                    self.assertIsNone(owner._combined_adapter)
                    self.assertIsNone(owner._validate_combined)
                    info = KInfoSupplement() if policy == POLICY_K_LC1 else None
                    payload = worker._k_proposal_payload(proposal, info)  # the call of the existing tests
                    keys = set(k.to_dict(proposal))
                    self.assertEqual(len(keys), 14)
                    self.assertEqual(set(payload), keys | ({"info"} if policy == POLICY_K_LC1 else set()))
                    self.assertFalse(b.basis_required(proposal))
                    self.assertEqual(k.info_required(proposal), policy == POLICY_K_LC1)
                    self.assertNotIn(proposal.category, NEW_CATEGORIES)
                    self.assertEqual((proposal.action, proposal.x, proposal.y),
                                     (owner.selection.move.action.name, owner.selection.move.x, owner.selection.move.y))
                    permit(owner, proposal)
        # K-LC1 still proposes what the new K records as the original proposal.
        for name in DECISIONS:
            with self.subTest(original=name):
                _, _, proposal, _ = decide(name, policy=POLICY_K_LC1)
                self.assertEqual([proposal.action, proposal.x, proposal.y], STATES[name]["expected"]["original"])
        # The parent job reads the diagnosis configuration for a K_D23 run only.
        process = Mock()
        process.poll.return_value = None
        with patch.dict(os.environ, {b.DIAGNOSIS_ENV: "NOT_A_CONFIGURATION"}), \
                patch.object(jobs.subprocess, "Popen", return_value=process) as launch, \
                patch.object(jobs, "create_scope", return_value=None):
            old_job = jobs.LivePolicyJob(clock=lambda: self.now)
            self.addCleanup(old_job.shutdown)
            old_job.start(state_of("KEPT", POLICY_K_LC1))
            old_job.timer.stop()
            self.assertEqual(launch.call_count, 1)
            new_job = jobs.LivePolicyJob(clock=lambda: self.now)
            self.addCleanup(new_job.shutdown)
            with self.assertRaises(LivePolicyError):
                new_job.start(state_of("KEPT"))
            self.assertEqual(launch.call_count, 1)  # nothing was started for the refused run
        self.assertIsNone(old_job._k_diagnosis)
        self.assertEqual((new_job.state, new_job.active_run_id), ("idle", None))
        # An old run refuses a payload that carries a basis: its 14 keys stay strict.
        start = state_of("FORCED_ABOVE_MINIMUM", POLICY_K_LC1)
        job, process = self.start_job(start)
        _, proposal, payload = worker_payload(start)
        _, _, new_payload = worker_payload(state_of("FORCED_ABOVE_MINIMUM"))
        self.publish(job, "PROPOSAL", {**payload, "basis": new_payload["basis"]})
        self.assertEqual(job.state, "cancelling")
        self.assertTrue(job._failure.startswith("REPLY_TRANSPORT:"))
        self.assert_nothing_kept(job)
        self.finish(job, process, 1)
        self.assertNotIn("k_diagnosis", job.last_record)

    def test_d17_end_lines_use_the_pre_input_basis_of_the_last_actual_input(self):
        owner, _, _, forced = decide("FORCED_KEPT")
        self.assertEqual(forced.loss, X.loss_lines_for(owner.combined_selection))
        self.assertEqual(forced.loss[0], PLAN["connection_runs"]["cases"]["new_lost"]["expected"]["end_first_line"])
        self.assertEqual(forced.loss[1:], (X.LOSS_FORCED_NOTE, X.LOSS_CLOSE))
        self.assertEqual(b.end_lines("LOST", b.LAST_K_DECISION, forced), forced.loss)
        # The base result is not changed and a game that is won or not finished has no note.
        self.assertEqual(b.end_lines("WON", b.LAST_K_DECISION, forced), ())
        self.assertEqual(b.end_lines("PLAYING", b.LAST_K_DECISION, forced), ())
        self.assertIn("기본 결과 LOST는 그대로다", forced.loss[-1])
        # Without a pre-input basis only what can be confirmed is written.
        self.assertEqual(b.end_lines("LOST", b.LAST_K_INITIAL, None), (b.LOSS_INITIAL, b.LOSS_BASE))
        self.assertEqual(b.end_lines("LOST", b.LAST_UNKNOWN, None), (b.LOSS_NOT_RECORDED, b.LOSS_BASE))
        self.assertEqual(b.end_lines("LOST", b.LAST_UNKNOWN, forced), (b.LOSS_NOT_RECORDED, b.LOSS_BASE))
        self.assertEqual(b.end_lines("LOST", b.LAST_K_DECISION, None), (b.LOSS_NOT_RECORDED, b.LOSS_BASE))
        for status, last in (("DRAW", b.LAST_UNKNOWN), ("LOST", "MANUAL"), (None, b.LAST_UNKNOWN)):
            with self.subTest(status=status, last=last), self.assertRaises(LivePolicyError):
                b.end_lines(status, last, None)
        _, _, _, above = decide("FORCED_ABOVE_MINIMUM")
        self.assertEqual((above.loss[1], above.loss[-1], len(above.loss)), (X.LOSS_FORCED_NOTE, X.LOSS_CLOSE, 4))
        self.assertIn("(4, 0)", above.loss[2])
        self.assertTrue(above.loss[0].endswith("입력 OPEN (3, 0), 입력 전 지뢰 확률 50.0% (1/2)."))
        for name, reason in (("KEPT", lookahead.KEPT), ("TIE_CHANGED", lookahead.TIE_LOOKAHEAD)):
            _, _, proposal, basis = decide(name)
            head = X.LOSS_HEAD[X.KIND_OF_REASON[reason]]
            self.assertTrue(basis.loss[0].startswith(head + f" 입력 OPEN ({proposal.x}, {proposal.y}), "))
            self.assertEqual(basis.loss[-1], X.LOSS_CLOSE)
        # A certain input is not explained as a guess loss.
        _, _, _, certain = decide("CERTAIN_APPLIED")
        self.assertEqual(certain.loss, (X.LOSS_INTEGRITY, X.LOSS_BASE))

    def test_d18_explanation_extension_keeps_the_old_behaviour_and_long_numbers(self):
        owner, _, _, _ = decide("FORCED_ABOVE_MINIMUM", "NONE")
        choice = owner.combined_selection
        executed, blocked = X.explain_decision(choice), X.explain_decision(choice, executed=False)
        # Without ``state`` the older flag decides exactly as before.
        self.assertEqual(executed, X.explain_decision(choice, executed=True))
        self.assertEqual(executed, X.explain_decision(choice, state=X.EXECUTED))
        self.assertEqual(executed, X.explain_decision(choice, executed=False, state=X.EXECUTED))
        self.assertEqual(blocked, X.explain_decision(choice, state=X.BLOCKED))
        self.assertEqual(executed, X.explain_decision(choice.guess))
        proposed = X.explain_decision(choice, state=X.PROPOSED)
        self.assertEqual(len({executed.selection[0], blocked.selection[0], proposed.selection[0]}), 3)
        self.assertEqual((proposed.short, proposed.selection[1:]), (executed.short, executed.selection[1:]))
        self.assertEqual((blocked.short, blocked.selection[1:]), (executed.short, executed.selection[1:]))
        for wrong in ("SENT", 1):
            with self.subTest(state=wrong), self.assertRaises(X.ExplanationError):
                X.explain_decision(choice, state=wrong)
        with self.assertRaises(X.ExplanationError):
            X.explain_decision(choice, executed=1)
        certain_owner, _, _, _ = decide("CERTAIN_APPLIED", "NONE")
        certain = certain_owner.combined_selection
        self.assertEqual(X.explain_decision(certain), X.explain_decision(certain, state=X.EXECUTED))
        self.assertTrue(X.explain_decision(certain, state=X.PROPOSED).selection[0].startswith("제안 입력: OPEN (5, 0)."))
        for arguments in ({"executed": False}, {"state": X.BLOCKED}):
            with self.subTest(certain=arguments), self.assertRaises(X.ExplanationError) as caught:
                X.explain_decision(certain, **arguments)
            self.assertEqual(caught.exception.code, X.MATERIAL)
        self.assertEqual(X.loss_lines_for(choice), X.loss_lines_for(choice.guess))
        self.assertEqual(X.loss_lines_for(certain), (X.LOSS_INTEGRITY, X.LOSS_BASE))
        # Long numbers: a fraction whose terms are too long to read is written as a percentage only.
        self.assertEqual(X.DISPLAY_LIMIT, 9999)
        big = Fraction(3 * 10 ** 40 + 1, 10 ** 41 + 3)
        facts = X.GuessFacts(
            reason=lookahead.KEPT, kind=X.KIND_OF_REASON[lookahead.KEPT], target=(2, 0), risk=big,
            original_target=(2, 0), original_risk=big, is_minimum_risk=True, target_changed=False, pair=None,
            lookahead_status=lookahead.STATUS_SINGLE, lookahead_cells=1, lookahead_calls=0, target_s_c=None,
            original_s_v=None)
        for state in X.STATES:
            lines = X._guess_lines(facts, state) + X._guess_loss_lines(facts) + (X._short(facts),)
            self.assertIn("30.0%", lines[0])
            for line in lines:
                self.assertNotIn(str(big.denominator), line)
                self.assertNotIn(str(big.numerator), line)
                self.assertLess(len(line), 200)
        self.assertEqual(X._risk(Fraction(1, 2)), "50.0% (1/2)")

    def test_d19_fixed_strings_and_help_agree_with_the_explanation_module(self):
        self.assertEqual(b.HELP_LINES, X.HELP_LINES)
        self.assertEqual(b.HELP_LINES, X.help_lines())
        self.assertEqual((b.LOSS_INITIAL, b.LOSS_NOT_RECORDED, b.LOSS_BASE),
                         (X.LOSS_INITIAL, X.LOSS_NOT_RECORDED, X.LOSS_BASE))
        self.assertEqual((b.PROPOSED, b.BLOCKED, b.EXECUTED), (X.PROPOSED, X.BLOCKED, X.EXECUTED))
        self.assertEqual((b.FORCED, b.TIE, b.KEPT), (lookahead.FORCED_FIRST, lookahead.TIE_LOOKAHEAD, lookahead.KEPT))
        self.assertEqual((b.BRANCH_CERTAIN, b.BRANCH_GUESS),
                         (combined_policy.BRANCH_CERTAIN, combined_policy.BRANCH_GUESS))
        self.assertEqual(set(b.CERTAIN_REASONS), set(X.OPENING_REASONS) | {b.OPENING})
        self.assertEqual(b.CALL_LIMITS, (lookahead.CALL_LIMIT, pseudo_diagnosis.PSEUDO_CALL_LIMIT,
                                         link_diagnosis.LINK_CALL_LIMIT))
        self.assertEqual(b.CALL_LIMITS, (72, 8, 54))
        self.assertEqual(set(k.D23_GUESS_CATEGORIES),
                         {lookahead.KEPT_GUESS_CATEGORY, lookahead.FORCED_CATEGORY, lookahead.TIE_CATEGORY})
        self.assertEqual(k.D23_OPEN_CATEGORIES, ("DIRECT_SAFE_OPEN", opening_policy.APPLIED_CATEGORY))
        self.assertEqual(k.D23_STAGES, ("SELECTION", "VALIDATION", "PSEUDO", "LINKED", "EXPLANATION"))
        # The help page of the copy shows those very lines and keeps the existing pages.
        self.assertIs(ui_help.K_HELP_LINES, b.HELP_LINES)
        for line in b.HELP_LINES:
            self.assertIn(line, ui_help.K_HELP_HTML)
        titles = [title for title, _ in ui_help.HELP_PAGES]
        self.assertEqual(titles[-1], "K 설명")
        self.assertEqual(len(titles), len(set(titles)))
        self.assertIs(dict(ui_help.HELP_PAGES)["K 설명"], ui_help.K_HELP_HTML)
        joined = "".join(page for _, page in ui_help.HELP_PAGES[:-1])
        self.assertIn("<b>K-P0 / K-LC0 / K-LC1:</b>", joined)
        self.assertIn("<b>K:</b>", joined)

    def test_d20_the_parent_side_module_imports_no_solver_or_experiment_module(self):
        def imports(name, top_level_only=False):
            tree = ast.parse((SOURCE / name).read_text(encoding="utf-8"))
            nodes = tree.body if top_level_only else ast.walk(tree)
            found = set()
            for node in nodes:
                if isinstance(node, ast.Import):
                    found.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    found.add(node.module)
            return found

        # The record module the parent loads: the standard library and the two parent-side modules only.
        self.assertEqual(imports("live_k_basis.py"), {"dataclasses", "hashlib", "json", "live_k_policy", "live_policy"})
        worker_only = {"live_k_d23", "live_k_info"}
        for name in ("live_policy_job.py", "live_analysis.py", "ui_help.py", "ui_manager.py", "live_k_basis.py"):
            with self.subTest(parent_module=name):
                found = imports(name)
                self.assertFalse(found & worker_only)
                self.assertFalse({module for module in found if module.startswith("experiments.program_")})
        # The policy module stays loadable by the parent: its solver imports are inside the worker's owner.
        self.assertFalse({module for module in imports("live_k_policy.py", top_level_only=True)
                          if module.startswith("experiments") or module in worker_only})
        # The worker-side writer is the only new module that loads the experiment modules.
        self.assertTrue({"experiments.program_d23_policy", "experiments.program_d3_pseudo_runner",
                         "experiments.program_d23_link_runner"} <= imports("live_k_d23.py"))


if __name__ == "__main__":
    unittest.main()
