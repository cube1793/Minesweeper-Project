"""Bounded tests for the prospective E1 registry, never E1 execution.

Artifact tests use synthetic, genuine-shaped records at the existing reader
boundary. No accepted artifact is edited and no E0 or P-8 scan is invoked.
"""

import ast
from collections import Counter
from contextlib import ExitStack, contextmanager
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
import hashlib
from pathlib import Path
import platform
import random
import sys
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import PropertyMock, call, patch

import benchmark_board
from experiments import program_k_e1_harness as e1
from experiments import program_k_harness as h
from experiments import program_k_oracles as oracles
from stage3_physical import MODEL_C_V1_IDENTITY, load_timing_table


CASE_IDS = (
    "S-WIN", "S-LIFECYCLE", "S-REPLAN", "S-LOSS",
    "X-0", "X-1", "X-2", "X-3", "X-100000",
)
EXPERT_INDICES = (0, 1, 2, 3, 100000)
VARIANTS = ("CONTROL", "K-CONTROL", "K-P0")
E0_RUN_ID = "e0-20261020T091707Z-a64907341e6c"
E0_SHA = "71ee9b3a9dc0a24de7471be996da5069f5c77ed750485a84b298ee74b7065576"
E0_SOURCE = "a8d2ed2f5547316603b4ba54899a7deed289016df7a5954f1db5b4816e00abd1"
P8_SHA = "9ccffab72d34173181dd84170cf442156f2df888f03d87c1571660ba7774137d"
FINGERPRINTS = (
    "7420118e517924990ff86e47fca7c246e84cb17b7941c1525888a5d5962bf55f",
    "202dfd5c0a4e7534eba7ea3885b9755a5485e57b73118f1d052b5ec3bf346d53",
    "6bd8c08c1b59fce179c64708033d6885dc6144d8d61f181570b9ed3c926d07ba",
    "ad299cd7234c269c935af06357607f89cb56bfcb13a82fa813cba9f42340775c",
    "fbd8b8069ef4f449bbc844329579b6538d2b175c1cf99eb22c49c0585322e053",
    "007b8d203106dd32d1b5b6c46052bbeeeb9fde2be89c81023b01519fba1bee9e",
    "58b8e6399a435371a430a75bd0a51035614242662b53015c61eb61292ccdd28a",
    "d191ef5fe000deb925b6c966cf83e8722e2d58c5f105717ab053b290d116b03c",
    "148b48aeda9730e8604bf68b7db8723de896bc8f4c5b741b33191d38edca065c",
)
SYNTHETICS = (
    (3, 1, ((2, 0),)),
    (4, 1, ((1, 0),)),
    (6, 4, ((1, 2), (2, 1), (4, 0), (4, 1), (4, 2))),
    (5, 1, ((1, 0), (2, 0))),
)
RUNTIME = e1.RuntimeIdentity("test-platform", "test-node", "test-python", "test-python.exe")


def independent_fingerprint(width, height, mines):
    """Reconstruct the documented byte format without the production helper."""
    values = (width, height, len(mines)) + tuple(
        value for cell in sorted(mines, key=lambda c: c[1] * width + c[0])
        for value in cell
    )
    return hashlib.sha256(
        b"MSLAYOUT1\0" + b"".join(value.to_bytes(4, "big") for value in values)
    ).hexdigest()


def corrupt_copy(value, **changes):
    """Inject transport corruption after validation without touching the input."""
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, changes.get(field.name, getattr(value, field.name)))
    return result


def prerequisite():
    identity = MODEL_C_V1_IDENTITY
    return e1.AcceptedE0Prerequisite(
        E0_RUN_ID, E0_SHA, E0_SOURCE, "E0_PASS", "E0_QUALIFIED", P8_SHA,
        h.FROZEN_SPEC_SHA256, h.FROZEN_PROTOCOL_SHA256,
        identity.physical_model_id, identity.physical_profile_sha256,
        identity.timing_table_sha256,
    )


def source_identity():
    base = prerequisite()
    return e1.E1SourceIdentity(
        base.source_digest,
        tuple(e1.E1SourceFile(path, hashlib.sha256(path.encode()).hexdigest(), len(path))
              for path in ("experiments/program_k_e1_harness.py", "benchmark_board.py")),
        base.spec_sha256, base.protocol_sha256, base.model_id,
        base.profile_sha256, base.table_sha256,
    )


def prospective_plan():
    return e1.E1Plan(
        prerequisite(), source_identity(), RUNTIME, e1._seal_fixed_cases(RUNTIME),
        e1.build_schedule(),
    )


class FixedCaseRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = e1._seal_fixed_cases(RUNTIME)

    def test_exact_nine_ids_and_order(self):
        self.assertEqual(e1.CASE_IDS, CASE_IDS)
        self.assertEqual(tuple(case.case_id for case in self.cases), CASE_IDS)
        self.assertEqual(len(self.cases), 9)

    def test_four_literal_synthetic_dimensions_counts_and_fingerprints(self):
        for case, (width, height, mines), expected in zip(
                self.cases[:4], SYNTHETICS, FINGERPRINTS[:4]):
            with self.subTest(case=case.case_id):
                self.assertEqual((case.width, case.height, case.num_mines),
                                 (width, height, len(mines)))
                self.assertEqual(case.board_fingerprint, expected)
                self.assertEqual(independent_fingerprint(width, height, mines), expected)
                self.assertEqual(case.first_click, (0, 0))
                self.assertIsNone(case.game_index)
                self.assertIsNone(case.seed)
                self.assertTrue(case.fixture_id)

    def test_expert_indices_and_complete_frozen_generator_metadata(self):
        self.assertEqual(e1.EXPERT_INDICES, EXPERT_INDICES)
        for case, index, expected in zip(self.cases[4:], EXPERT_INDICES, FINGERPRINTS[4:]):
            with self.subTest(case=case.case_id):
                self.assertEqual(
                    (case.width, case.height, case.num_mines, case.first_click,
                     case.benchmark_set_id, case.board_generator_version,
                     case.seed_scheme, case.game_index, case.seed),
                    (30, 16, 99, (0, 0), "EXPERT_GENERAL_V1", "V1",
                     "game_index", index, index),
                )
                self.assertEqual(case.board_fingerprint, expected)

    def test_one_generation_per_expert_and_independent_layout_reconstruction(self):
        generated = []

        def capture(spec, index):
            board = benchmark_board.generate_board(spec, index)
            generated.append(board)
            return board

        with patch.object(e1, "generate_board", side_effect=capture) as generator:
            cases = e1._seal_fixed_cases(RUNTIME)
        self.assertEqual(generator.call_args_list,
                         [call(benchmark_board.EXPERT_GENERAL_V1, i) for i in EXPERT_INDICES])
        for case, board in zip(cases[4:], generated):
            self.assertEqual(board.game_index, case.game_index)
            self.assertEqual(board.seed, case.game_index)
            self.assertEqual(len(board.mine_positions), 99)
            self.assertNotIn((0, 0), board.mine_positions)
            self.assertEqual(case.board_fingerprint,
                             independent_fingerprint(30, 16, board.mine_positions))
            self.assertEqual(case.board_fingerprint, board.board_fingerprint)

    def test_sealed_public_cases_expose_no_layout(self):
        for case in self.cases:
            self.assertFalse(hasattr(case, "__dict__"))
            names = {field.name for field in fields(case)}
            self.assertFalse(names & {"mine_positions", "mines", "layout", "definition", "engine"})
            self.assertFalse(any(isinstance(getattr(case, f.name), (set, frozenset, dict, list))
                                 for f in fields(case)))
            self.assertEqual(case.runtime, RUNTIME)

    def test_provenance_exposure_overlap_and_claim_limits_are_explicit(self):
        for case in self.cases:
            with self.subTest(case=case.case_id):
                for name in ("source_type", "provenance", "prior_exposure",
                             "purpose", "permitted_claims", "no_effectiveness_claim"):
                    self.assertTrue(getattr(case, name), name)
                self.assertIs(type(case.overlap), tuple)
                self.assertIs(case.statistically_representative, False)
                self.assertIs(case.e2_effectiveness_evidence, False)
        for case in self.cases[:4]:
            self.assertIn("regression", case.source_type.lower())
            self.assertIn("mechanism", str(case.permitted_claims).lower())
        self.assertIn("exemplar", str(self.cases[5].overlap).lower())
        self.assertIn("pilot", str(self.cases[-1].overlap).lower())
        self.assertIn("integration", str(self.cases[-1].permitted_claims).lower())

    def test_case_registration_rejects_identity_or_claim_changes(self):
        changes = (
            {"width": 4}, {"num_mines": True}, {"first_click": [0, 0]},
            {"board_fingerprint": "0" * 64}, {"case_id": "S-OTHER"},
            {"statistically_representative": True}, {"e2_effectiveness_evidence": True},
            {"no_effectiveness_claim": "Effectiveness accepted"},
            {"runtime": object()}, {"permitted_claims": ("speed acceptance",)},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(self.cases[0], **change)

    def test_equal_but_mutable_optional_values_cannot_enter_sealed_graph(self):
        class EqualToNone:
            def __eq__(self, other):
                return other is None

        class StringSubclass(str):
            pass

        for name in ("benchmark_set_id", "board_generator_version",
                     "seed_scheme", "game_index", "seed"):
            with self.subTest(field=name), self.assertRaises((ValueError, TypeError)):
                replace(self.cases[0], **{name: EqualToNone()})
        for name in ("case_id", "source_type", "provenance", "purpose"):
            with self.subTest(field=name), self.assertRaises((ValueError, TypeError)):
                replace(self.cases[0], **{name: StringSubclass(getattr(self.cases[0], name))})

    def test_expert_generation_rejects_wrong_identity_hash_layout_or_first_click(self):
        original = benchmark_board.generate_board(benchmark_board.EXPERT_GENERAL_V1, 0)
        unsafe = frozenset((original.mine_positions - {next(iter(original.mine_positions))}) | {(0, 0)})
        changed = frozenset(
            (original.mine_positions - {next(iter(original.mine_positions))})
            | {next((x, y) for y in range(16) for x in range(30)
                    if (x, y) != (0, 0) and (x, y) not in original.mine_positions)}
        )
        faults = (
            corrupt_copy(original, game_index=1), corrupt_copy(original, game_index=False),
            corrupt_copy(original, seed=1), corrupt_copy(original, seed=False),
            corrupt_copy(original, board_fingerprint="0" * 64),
            corrupt_copy(original, mine_positions=unsafe,
                         board_fingerprint=independent_fingerprint(30, 16, unsafe)),
            corrupt_copy(original, mine_positions=changed,
                         board_fingerprint=independent_fingerprint(30, 16, changed)),
            corrupt_copy(original, mine_positions=frozenset()),
            corrupt_copy(original, mine_positions=frozenset({(30, 0)})),
            None,
        )
        for faulty in faults:
            with self.subTest(fault=faulty), patch.object(
                    e1, "generate_board", return_value=faulty) as generator:
                with self.assertRaises((ValueError, TypeError)):
                    e1._seal_fixed_cases(RUNTIME)
                generator.assert_called_once_with(benchmark_board.EXPERT_GENERAL_V1, 0)

    def test_no_global_randomization_or_rng_contamination(self):
        before = random.getstate()
        with ExitStack() as stack:
            for name in ("shuffle", "sample", "seed", "random", "randrange"):
                stack.enter_context(patch.object(random, name, side_effect=AssertionError(name)))
            self.assertEqual(e1._seal_fixed_cases(RUNTIME), self.cases)
            self.assertEqual(e1.build_schedule(), e1.build_schedule())
        self.assertEqual(random.getstate(), before)


class RuntimeIdentityTests(unittest.TestCase):
    def test_capture_uses_actual_runtime(self):
        actual = e1.capture_runtime_identity()
        self.assertEqual((actual.platform, actual.node, actual.python_version, actual.executable),
                         (platform.platform(), platform.node(), sys.version, sys.executable))

    def test_public_sealer_captures_runtime_instead_of_accepting_test_identity(self):
        with patch.object(e1, "capture_runtime_identity", return_value=RUNTIME) as capture:
            cases = e1.seal_fixed_cases()
        capture.assert_called_once_with()
        self.assertTrue(all(case.runtime == RUNTIME for case in cases))
        with self.assertRaises(TypeError):
            e1.seal_fixed_cases(RUNTIME)

    def test_runtime_rejects_missing_blank_mutable_or_nontext_identity(self):
        for field in fields(RUNTIME):
            for invalid in ("", " \n", None, [], 1, True):
                with self.subTest(field=field.name, invalid=invalid):
                    with self.assertRaises((ValueError, TypeError)):
                        replace(RUNTIME, **{field.name: invalid})


class ScheduleTests(unittest.TestCase):
    def test_exact_54_entry_prospective_order_and_unique_keys(self):
        schedule = e1.build_schedule()
        expected = tuple(
            (index, case_id, repetition, variant, True)
            for index, (case_id, repetition, variant) in enumerate(
                (case_id, repetition, variant)
                for case_id in CASE_IDS for repetition in (1, 2) for variant in VARIANTS)
        )
        self.assertEqual(e1.VARIANTS, VARIANTS)
        self.assertEqual(e1.REPETITIONS, (1, 2))
        self.assertIs(type(schedule), tuple)
        self.assertEqual(tuple((s.schedule_index, s.case_id, s.repetition, s.variant,
                                s.fresh_state_required) for s in schedule), expected)
        self.assertEqual(len({(s.case_id, s.repetition, s.variant) for s in schedule}), 54)
        e1.validate_schedule(schedule)

    def test_every_case_six_times_and_every_case_variant_twice(self):
        schedule = e1.build_schedule()
        self.assertEqual(Counter(s.case_id for s in schedule), Counter(dict.fromkeys(CASE_IDS, 6)))
        self.assertEqual(Counter((s.case_id, s.variant) for s in schedule),
                         Counter({(case_id, variant): 2
                                  for case_id in CASE_IDS for variant in VARIANTS}))

    def test_schedule_rejects_missing_duplicate_reordered_or_mutable_entries(self):
        schedule = e1.build_schedule()
        invalid_schedules = (
            schedule[:-1], schedule + (schedule[0],),
            (schedule[1], schedule[0]) + schedule[2:],
            schedule[:-1] + (schedule[0],), list(schedule),
            (corrupt_copy(schedule[0], fresh_state_required=False),) + schedule[1:],
            (corrupt_copy(schedule[0], schedule_index=False),) + schedule[1:],
        )
        for invalid in invalid_schedules:
            with self.subTest(schedule=invalid), self.assertRaises((ValueError, TypeError)):
                e1.validate_schedule(invalid)

    def test_entries_reject_invalid_identity_boolean_integer_or_freshness(self):
        first = e1.build_schedule()[0]
        for change in (
                {"schedule_index": -1}, {"schedule_index": False},
                {"case_id": "X-4"}, {"variant": "RANDOM"}, {"repetition": True},
                {"repetition": 0}, {"repetition": 3}, {"fresh_state_required": False},
                {"fresh_state_required": 1}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(first, **change)


class SourceIdentityTests(unittest.TestCase):
    def test_exact_runtime_paths_and_historical_e0_identity_are_preserved(self):
        before = h.SOURCE_PATHS
        identity = e1.capture_e1_source_identity(prerequisite())
        self.assertEqual(e1.E1_SOURCE_PATHS,
                         ("experiments/program_k_e1_harness.py", "benchmark_board.py"))
        self.assertEqual(tuple(f.path for f in identity.files), e1.E1_SOURCE_PATHS)
        self.assertEqual(h.SOURCE_PATHS, before)
        self.assertNotIn("tests/test_program_k_e1_harness.py", tuple(f.path for f in identity.files))
        self.assertEqual(identity.base_source_digest, E0_SOURCE)
        root = Path(__file__).resolve().parents[1]
        for file in identity.files:
            data = (root / file.path).read_bytes()
            self.assertEqual((file.sha256, file.size_bytes), (hashlib.sha256(data).hexdigest(), len(data)))
        self.assertEqual(identity, e1.capture_e1_source_identity(prerequisite()))
        self.assertEqual(identity.digest, e1.capture_e1_source_identity(prerequisite()).digest)

    def test_exact_bytes_mutation_changes_extension_digest_in_temporary_root(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in e1.E1_SOURCE_PATHS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"first\r\n")
            first = e1._capture_e1_source_identity(prerequisite(), root)
            second_path = root / "benchmark_board.py"
            second_path.write_bytes(b"first\n")
            second = e1._capture_e1_source_identity(prerequisite(), root)
            self.assertNotEqual(first.digest, second.digest)
            self.assertNotEqual(first.files[1].sha256, second.files[1].sha256)
            self.assertNotEqual(first.files[1].size_bytes, second.files[1].size_bytes)
            self.assertEqual(first.files[0], second.files[0])
            self.assertEqual(first.base_source_digest, second.base_source_digest)
            second_path.unlink()
            with self.assertRaises((ValueError, OSError)):
                e1._capture_e1_source_identity(prerequisite(), root)

    def test_source_identity_rejects_missing_extra_reordered_or_mutable_fields(self):
        identity = source_identity()
        for change in (
                {"files": identity.files[:1]}, {"files": identity.files + identity.files[:1]},
                {"files": tuple(reversed(identity.files))}, {"files": list(identity.files)},
                {"base_source_digest": "0" * 64}, {"spec_sha256": "0" * 64},
                {"protocol_sha256": "0" * 64}, {"model_id": "other"},
                {"profile_sha256": "0" * 64}, {"table_sha256": "0" * 64}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(identity, **change)
        with self.assertRaises(TypeError):
            e1.E1SourceIdentity(identity.base_source_digest, identity.files)
        values = {field.name: getattr(identity, field.name) for field in fields(identity)}
        with self.assertRaises(TypeError):
            e1.E1SourceIdentity(**values, extra_identity="unregistered")

    def test_source_file_paths_hashes_and_sizes_reject_noncanonical_values(self):
        file = source_identity().files[0]
        for change in (
                {"path": "experiments\\program_k_e1_harness.py"},
                {"path": "../program_k_e1_harness.py"},
                {"path": "tests/test_program_k_e1_harness.py"},
                {"sha256": "A" * 64}, {"sha256": "0"},
                {"size_bytes": True}, {"size_bytes": 0}, {"size_bytes": -1}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(file, **change)

    def test_live_base_mutation_cannot_silently_extend_a_different_e0_identity(self):
        base = h.capture_source_identity()
        files = base.files[:2] + (replace(base.files[2], sha256="0" * 64),) + base.files[3:]
        changed = replace(base, files=files)
        with patch.object(h, "capture_source_identity", return_value=changed), \
                self.assertRaises(e1.E1PlanningError):
            e1.capture_e1_source_identity(prerequisite())


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = prospective_plan()

    def test_plan_is_prospective_and_cannot_authorize_or_claim_qualification(self):
        self.assertEqual(self.plan.stage, "E1")
        self.assertIs(self.plan.actual_execution_authorized, False)
        self.assertEqual(self.plan.supplement_status, "NOT_EVALUATED")
        self.assertIn("complete", self.plan.purpose.lower())
        self.assertIn("effectiveness", self.plan.purpose.lower())
        self.assertFalse(hasattr(self.plan, "verdict"))
        for change in (
                {"stage": "E2"}, {"actual_execution_authorized": True},
                {"actual_execution_authorized": 0}, {"purpose": "E1_PASS"},
                {"qualification_scope": "E1_PASS"}, {"supplement_status": "SELECTED"},
                {"supplement_status": "NOT_REQUIRED"}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(self.plan, **change)

    def test_productive_chord_requires_actual_future_observation(self):
        requirement = self.plan.productive_chord_requirement
        self.assertIn("K-P0", requirement)
        self.assertIn("FLAG", requirement)
        self.assertIn("CHORD", requirement)
        self.assertIn("INCOMPLETE", requirement)
        self.assertIn("A-E5", requirement)
        self.assertEqual(self.plan.supplement_status, "NOT_EVALUATED")
        self.assertIn("determinism", self.plan.repetition_purpose.lower())
        self.assertIn("contamination", self.plan.repetition_purpose.lower())
        for name in ("productive_chord_requirement", "repetition_purpose"):
            with self.assertRaises((ValueError, TypeError)):
                replace(self.plan, **{name: "already satisfied"})

    def test_plan_rejects_wrong_case_counts_order_runtime_or_schedule(self):
        cases = self.plan.cases
        bad_case = corrupt_copy(cases[0], board_fingerprint="0" * 64)
        for change in (
                {"cases": cases[:-1]}, {"cases": cases + cases[:1]},
                {"cases": (cases[1], cases[0]) + cases[2:]},
                {"cases": list(cases)}, {"cases": (bad_case,) + cases[1:]},
                {"runtime": replace(RUNTIME, node="another-node")},
                {"schedule": self.plan.schedule[:-1]},
                {"prerequisite": corrupt_copy(self.plan.prerequisite, run_id="other")},
                {"source_identity": corrupt_copy(self.plan.source_identity,
                                                 base_source_digest="0" * 64)}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(self.plan, **change)

    def test_graph_is_deeply_immutable_and_contains_only_detached_values(self):
        def check(value):
            if type(value) in (str, int, bool, type(None)):
                return
            if type(value) is tuple:
                for item in value:
                    check(item)
                return
            self.assertTrue(is_dataclass(value), type(value))
            self.assertTrue(type(value).__dataclass_params__.frozen)
            self.assertFalse(hasattr(value, "__dict__"))
            for field in fields(value):
                check(getattr(value, field.name))
            field = fields(value)[0]
            with self.assertRaises((FrozenInstanceError, AttributeError, TypeError)):
                setattr(value, field.name, getattr(value, field.name))

        check(self.plan)

    def test_public_builder_assembles_prerequisite_source_runtime_cases_schedule(self):
        with patch.object(e1, "load_accepted_e0_prerequisite",
                          return_value=self.plan.prerequisite) as loader, patch.object(
                e1, "capture_e1_source_identity", return_value=self.plan.source_identity) as capture, \
                patch.object(e1, "capture_runtime_identity", return_value=RUNTIME):
            plan = e1.build_e1_plan()
        self.assertEqual(plan, self.plan)
        self.assertEqual(loader.call_count, 1)
        self.assertEqual(capture.call_args_list,
                         [call(self.plan.prerequisite), call(self.plan.prerequisite)])

    def test_public_builder_refuses_source_change_during_sealing(self):
        source = self.plan.source_identity
        changed = replace(source, files=(replace(source.files[0], sha256="0" * 64), source.files[1]))
        with patch.object(e1, "load_accepted_e0_prerequisite", return_value=self.plan.prerequisite), \
                patch.object(e1, "capture_e1_source_identity", side_effect=(source, changed)), \
                patch.object(e1, "capture_runtime_identity", return_value=RUNTIME), \
                self.assertRaises(e1.E1PlanningError):
            e1.build_e1_plan()


def synthetic_accepted_triplet():
    """Reader-boundary fixtures, not an actual qualification or scan result."""
    identity = MODEL_C_V1_IDENTITY
    source = h.SourceIdentity(
        tuple(h.SourceFileIdentity(
            path, h.FROZEN_SPEC_SHA256 if path == h.SPEC_PATH
            else h.FROZEN_PROTOCOL_SHA256 if path == h.PROTOCOL_PATH
            else hashlib.sha256(path.encode()).hexdigest(), 1) for path in h.SOURCE_PATHS),
        h.FROZEN_PROTOCOL_SHA256, h.FROZEN_SPEC_SHA256, identity.physical_model_id,
        identity.physical_profile_sha256, identity.timing_table_sha256,
    )
    table = load_timing_table()
    witness = oracles.P8Witness(
        0, (0, 0), (0, 0), (1, 0), ((0, 0), (1, 0), (1, 0)),
        (table[0][0], table[1][0], table[1][0]), table[0][0],
    )
    p8 = oracles.P8Result(
        "FROZEN_P8", table, tuple((x, y) for y in range(16) for x in range(30)),
        110361600, 110361600, True, None, "AUTHENTICATED",
        identity.physical_profile_sha256, identity.timing_table_sha256,
        identity.physical_model_id, identity.physical_profile_version,
        "us", "dx_major_dy_minor", oracles.P8_CHECKER_IDENTITY,
        oracles.P8_CHECKER_VERSION, "f" * 64, "f" * 64, table[0][0],
        witness, 0, 0, (), 1,
    )
    envelope = h.OperatingEnvelope(
        "test-runtime", "test-machine", "test-python",
        1000, 10000, 100000, 1000, 1000, 1000000, 1000000, 10,
        "test-monitor", "Mock reader boundary only; no execution.",
    )
    record = h.QualificationRecord(
        E0_RUN_ID, "E0_QUALIFICATION", "synthetic reader-boundary fixture",
        source, envelope, h.MANIFEST_ID, h.PINNED_MANIFEST_SHA256, h.MANIFEST,
        (), (), h.ExecutionVerification((), (), (), (), (), (), ()), (),
        p8, (), (),
    )
    receipt = h.ArtifactReceipt(
        E0_RUN_ID, E0_SHA, 1, E0_SOURCE, "c" * 64, h.FROZEN_PROTOCOL_SHA256, "E0_PASS",
    )
    gate = h.P8Gate("PASS", "FROZEN_P8_COMPLETE", P8_SHA, "Synthetic reader-boundary gate.")
    assessment = h.QualificationAssessment("E0_PASS", "E0_QUALIFIED", (), gate)
    return record, receipt, assessment


@contextmanager
def accepted_reader_boundary(triplet, *, p8_gate=None, record_digest=E0_SHA,
                             source_digest=E0_SOURCE, p8_digest=P8_SHA):
    """Bypass artifact authentication only inside explicit unit-test mocks."""
    original_digest = h.content_digest

    def mocked_digest(value):
        if type(value) is h.QualificationRecord:
            return record_digest
        if type(value) is h.SourceIdentity:
            return source_digest
        return original_digest(value)

    gate = p8_gate if p8_gate is not None else h.P8Gate(
        "PASS", "FROZEN_P8_COMPLETE", P8_SHA, "Synthetic reader-boundary gate.",
    )
    with patch.object(e1, "_check_accepted_files") as checks, patch.object(
            h, "read_qualification_artifact", return_value=triplet) as reader, patch.object(
            h, "content_digest", side_effect=mocked_digest), patch.object(
            h, "check_p8_gate", return_value=gate) as p8_check, patch.object(
            oracles.P8Result, "evidence_sha256", new_callable=PropertyMock,
            return_value=p8_digest):
        yield checks, reader, p8_check


class AcceptedPrerequisiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.triplet = synthetic_accepted_triplet()

    def load(self):
        # The explicit path has the accepted basename but is never read while
        # the synthetic reader-boundary mocks are active.
        return e1.load_accepted_e0_prerequisite(Path("synthetic-reader-boundary") / E0_RUN_ID)

    def test_genuine_shaped_reader_pass_returns_only_small_immutable_reference(self):
        with accepted_reader_boundary(self.triplet) as (checks, reader, gate):
            result = self.load()
        self.assertEqual(result, prerequisite())
        self.assertEqual(checks.call_count, 2)
        reader.assert_called_once_with(Path("synthetic-reader-boundary") / E0_RUN_ID)
        gate.assert_called_once_with(self.triplet[0].p8_reference)
        self.assertTrue(all(type(getattr(result, field.name)) is str for field in fields(result)))
        self.assertFalse(any(hasattr(result, name) for name in ("record", "path", "engine", "p8_reference")))

    def test_wrong_run_id_purpose_or_receipt_run_is_rejected(self):
        record, receipt, assessment = self.triplet
        for triplet in (
                (replace(record, run_id="wrong"), receipt, assessment),
                (replace(record, purpose="IMPLEMENTATION_UNIT_READINESS"), receipt, assessment),
                (record, replace(receipt, run_id="wrong"), assessment)):
            with self.subTest(record=triplet[0].run_id, receipt=triplet[1].run_id), \
                    accepted_reader_boundary(triplet), self.assertRaises(e1.E1PlanningError):
                self.load()

    def test_wrong_qualification_content_or_receipt_digest_is_rejected(self):
        record, receipt, assessment = self.triplet
        with accepted_reader_boundary(self.triplet, record_digest="0" * 64), \
                self.assertRaises(e1.E1PlanningError):
            self.load()
        with accepted_reader_boundary((record, replace(receipt, content_sha256="0" * 64), assessment)), \
                self.assertRaises(e1.E1PlanningError):
            self.load()
        with accepted_reader_boundary(
                (record, corrupt_copy(receipt, completion_marker="INCOMPLETE"), assessment)), \
                self.assertRaises(e1.E1PlanningError):
            self.load()

    def test_wrong_verdict_readiness_receipt_or_progression_is_rejected(self):
        record, receipt, assessment = self.triplet
        for candidate in (
                replace(assessment, verdict="INCOMPLETE"),
                replace(assessment, readiness="READY_EXCEPT_EXECUTION")):
            with self.subTest(assessment=candidate), accepted_reader_boundary(
                    (record, receipt, candidate)), self.assertRaises(e1.E1PlanningError):
                self.load()
        with accepted_reader_boundary((record, replace(receipt, verdict="INCOMPLETE"), assessment)), \
                self.assertRaises(e1.E1PlanningError):
            self.load()
        for progression in (False, 1, None):
            with self.subTest(progression=progression), accepted_reader_boundary(self.triplet), \
                    patch.object(h.QualificationAssessment, "progression_allowed",
                                 new_callable=PropertyMock, return_value=progression), \
                    self.assertRaises(e1.E1PlanningError):
                self.load()

    def test_missing_malformed_or_nonaccepted_p8_is_rejected(self):
        record, receipt, assessment = self.triplet
        p8 = record.p8_reference
        faults = (
            None, object(), corrupt_copy(p8, scope="PRIVATE_BOUNDED_CHECK"),
            corrupt_copy(p8, authentication_status="NOT_EVALUATED"),
            corrupt_copy(p8, complete=False),
            corrupt_copy(p8, visited_triple_count=110361599),
            corrupt_copy(p8, expected_triple_count=True),
            corrupt_copy(p8, visited_triple_count=True),
            corrupt_copy(p8, zero_gap_count=1),
        )
        for faulty in faults:
            changed = corrupt_copy(record, p8_reference=faulty)
            with self.subTest(p8=faulty), accepted_reader_boundary(
                    (changed, receipt, assessment)), self.assertRaises(e1.E1PlanningError):
                self.load()
        with accepted_reader_boundary(self.triplet, p8_digest="0" * 64), \
                self.assertRaises(e1.E1PlanningError):
            self.load()

    def test_current_p8_gate_must_pass_exact_classification_and_digest(self):
        for gate in (
                h.P8Gate("INCOMPLETE", "INTERRUPTED_P8", P8_SHA, "unit negative"),
                h.P8Gate("FAIL", "IMPLEMENTATION_IDENTITY_FAIL", P8_SHA, "unit negative"),
                h.P8Gate("PASS", "PRIVATE_CHECK_NOT_RESEARCH_EVIDENCE", P8_SHA, "unit negative"),
                h.P8Gate("PASS", "FROZEN_P8_COMPLETE", "0" * 64, "unit negative"),
                object()):
            with self.subTest(gate=gate), accepted_reader_boundary(
                    self.triplet, p8_gate=gate), self.assertRaises(e1.E1PlanningError):
                self.load()

    def test_source_protocol_spec_and_model_identity_mismatches_are_rejected(self):
        record, receipt, assessment = self.triplet
        for name in ("protocol_sha256", "spec_sha256", "profile_sha256", "table_sha256", "model_id"):
            changed = corrupt_copy(record.source_identity, **{name: "0" * 64})
            with self.subTest(field=name), accepted_reader_boundary(
                    (corrupt_copy(record, source_identity=changed), receipt, assessment)), \
                    self.assertRaises(e1.E1PlanningError):
                self.load()
        with accepted_reader_boundary(self.triplet, source_digest="0" * 64), \
                self.assertRaises(e1.E1PlanningError):
            self.load()
        for changed in (replace(receipt, source_digest="0" * 64),
                        replace(receipt, protocol_sha256="0" * 64)):
            with accepted_reader_boundary((record, changed, assessment)), \
                    self.assertRaises(e1.E1PlanningError):
                self.load()

    def test_missing_or_corrupt_bytes_fail_before_any_reader_or_assessment(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / E0_RUN_ID
            root.mkdir()
            with patch.object(h, "read_qualification_artifact") as reader:
                with self.assertRaises(e1.E1PlanningError):
                    e1.load_accepted_e0_prerequisite(root)
                (root / "qualification.json").write_bytes(b'{"purpose":"IMPLEMENTATION_UNIT_READINESS"}')
                (root / "COMPLETE.json").write_bytes(b"corrupt")
                with self.assertRaises(e1.E1PlanningError):
                    e1.load_accepted_e0_prerequisite(root)
                reader.assert_not_called()

    def test_completion_byte_digest_is_checked_before_reader(self):
        # A sentinel digest stands in only for the qualification bytes so this
        # negative test independently reaches COMPLETE authentication.
        with TemporaryDirectory() as directory:
            root = Path(directory) / E0_RUN_ID
            root.mkdir()
            (root / "qualification.json").write_bytes(b"qualification sentinel")
            (root / "COMPLETE.json").write_bytes(b"corrupt completion")
            original_hash = hashlib.sha256

            def hash_bytes(data=b""):
                if data == b"qualification sentinel":
                    return types.SimpleNamespace(hexdigest=lambda: E0_SHA)
                return original_hash(data)

            with patch.object(e1.hashlib, "sha256", side_effect=hash_bytes), \
                    patch.object(h, "read_qualification_artifact") as reader, \
                    self.assertRaises(e1.E1PlanningError):
                e1.load_accepted_e0_prerequisite(root)
            reader.assert_not_called()

    def test_reader_failure_and_artifact_change_during_read_fail_closed(self):
        with accepted_reader_boundary(self.triplet) as (checks, reader, _):
            reader.side_effect = h.QualificationError("corrupt canonical record")
            with self.assertRaises(e1.E1PlanningError):
                self.load()
        with accepted_reader_boundary(self.triplet) as (checks, _, _):
            checks.side_effect = (None, e1.E1PlanningError("changed during read"))
            with self.assertRaises(e1.E1PlanningError):
                self.load()

    def test_malformed_record_receipt_assessment_are_not_accepted(self):
        for index in range(3):
            triplet = list(self.triplet)
            triplet[index] = object()
            with self.subTest(index=index), accepted_reader_boundary(tuple(triplet)), \
                    self.assertRaises(e1.E1PlanningError):
                self.load()


class ImportAndWriteBoundaryTests(unittest.TestCase):
    def test_import_does_not_read_artifacts_generate_boards_or_execute(self):
        module_path = Path(e1.__file__)
        code = compile(module_path.read_bytes(), str(module_path), "exec")
        name = "experiments._e1_import_boundary_probe"
        module = types.ModuleType(name)
        module.__file__ = str(module_path)
        module.__package__ = "experiments"
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {name: module}))
            for owner, attribute in (
                    (Path, "read_bytes"), (Path, "read_text"), (Path, "open"),
                    (benchmark_board, "generate_board"),
                    (h, "read_qualification_artifact"), (h, "execute_e0"),
                    (h._runner, "run_k_p0"), (h._runner, "run_k_control"),
                    (h._runner, "run_control_capture"),
                    (oracles, "check_frozen_p8"), (oracles, "_check_p8_table"),
                    (platform, "platform"), (platform, "node")):
                stack.enter_context(patch.object(
                    owner, attribute, side_effect=AssertionError("forbidden during import: " + attribute)))
            import core_engine
            stack.enter_context(patch.object(
                core_engine.MinesweeperEngine, "__init__",
                side_effect=AssertionError("Engine construction during import")))
            exec(code, module.__dict__)
        self.assertEqual(module.CASE_IDS, CASE_IDS)

    def test_module_has_no_solver_dispatch_or_repository_writer(self):
        source = Path(e1.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = {
            "run_k_p0", "run_k_control", "run_control_capture", "execute_e0",
            "check_frozen_p8", "_check_p8_table", "persist_qualification",
            "MinesweeperEngine", "KLocalSession", "plan_position",
            "write_bytes", "write_text", "mkdir", "makedirs", "unlink", "rename",
            "replace_file", "dump", "Popen", "subprocess", "os.system",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                self.assertNotIn(node.id, forbidden)
            elif isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, forbidden)
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse({alias.name for alias in node.names} & forbidden)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotEqual(node.func.id, "open")
        self.assertNotIn("E1_PASS", source)
        self.assertNotIn("E1_FAIL", source)
        self.assertFalse(any(name for name in vars(e1)
                             if "supplement" in name.lower() and callable(getattr(e1, name))))


if __name__ == "__main__":
    unittest.main()
