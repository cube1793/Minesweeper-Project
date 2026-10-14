"""Independent frozen identity pins and unchanged benchmark snapshot contract."""

from dataclasses import FrozenInstanceError, asdict, fields
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch

from benchmark_board import EXPERT_GENERAL_V1
import benchmark_modeled_time as modeled
import stage3_benchmark_runner as benchmark
from stage3_identity import STAGE3_V1_IDENTITY
import stage3_physical as physical
import telemetry_schema as schema


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ALGORITHM = {
    "algorithm_spec_version": 1,
    "algorithm_spec_sha256": "6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33",
    "solver_stage": "STAGE_3",
    "solver_policy": "E_FIRST_FIRST_REVEAL_V1",
}
EXPECTED_PHYSICAL = {
    "physical_model_id": "overlap_floor_log2_distance_v1",
    "physical_profile_version": 1,
    "physical_profile_sha256": "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b",
    "timing_table_sha256": "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b",
    "timing_unit": "us",
}
# Literal canonical V1 snapshot, independently pinned rather than assembled from
# production identities. Existing comparison/continuation tests cover rejection.
EXPECTED_CONFIG_JSON = (
    '{"algorithm_spec_sha256":"6e4ff95b74d274f4938e22f0a04be33879bdfab6156280e48a25429d0c811c33",'
    '"algorithm_spec_version":1,"initial_cursor":[0,0],"initial_open":[0,0],'
    '"physical_model_id":"overlap_floor_log2_distance_v1","physical_profile_sha256":'
    '"52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b",'
    '"physical_profile_version":1,"timing_table_sha256":'
    '"7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b","timing_unit":"us"}'
)


class Stage3IdentityTests(unittest.TestCase):
    def assert_exact_values_and_types(self, actual, expected):
        self.assertEqual(set(actual), set(expected))
        self.assertEqual(actual, expected)
        for name, value in expected.items():
            with self.subTest(field=name):
                self.assertIs(type(actual[name]), type(value))
                if type(value) is list:
                    self.assertEqual([type(item) for item in actual[name]],
                                     [type(item) for item in value])

    def test_algorithm_identity_has_only_the_exact_frozen_algorithm_fields(self):
        self.assert_exact_values_and_types(asdict(STAGE3_V1_IDENTITY), EXPECTED_ALGORITHM)
        self.assertEqual(schema.SOLVER_STAGE_STAGE_3, "STAGE_3")
        self.assertEqual(schema.SOLVER_POLICY_E_FIRST_FIRST_REVEAL_V1,
                         "E_FIRST_FIRST_REVEAL_V1")

    def test_algorithm_digest_identifies_canonical_lf_specification(self):
        raw = (ROOT / "STAGE3_ALGORITHM_SPEC_v1.md").read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         EXPECTED_ALGORITHM["algorithm_spec_sha256"])

    def test_physical_identity_has_only_the_exact_frozen_physical_fields(self):
        self.assert_exact_values_and_types(asdict(physical.MODEL_C_V1_IDENTITY),
                                          EXPECTED_PHYSICAL)

    def test_physical_display_alias_is_separate_from_authenticated_identity(self):
        self.assertEqual(physical.MODEL_C_DISPLAY_NAME, "Model C")
        with patch.object(physical, "MODEL_C_DISPLAY_NAME", "Display-only test alias"):
            evaluation = modeled.authenticate_model_c()
            self.assert_exact_values_and_types(asdict(physical.MODEL_C_V1_IDENTITY),
                                              EXPECTED_PHYSICAL)
            for config in (benchmark._benchmark_identity(EXPERT_GENERAL_V1)["solver_config_snapshot"],
                           modeled._stage3_config(evaluation)):
                self.assertEqual(json.dumps(config, sort_keys=True, separators=(",", ":")),
                                 EXPECTED_CONFIG_JSON)

    def test_public_identity_values_are_immutable(self):
        for identity in (STAGE3_V1_IDENTITY, physical.MODEL_C_V1_IDENTITY):
            for field in fields(identity):
                with self.subTest(identity=type(identity).__name__, field=field.name):
                    with self.assertRaises(FrozenInstanceError):
                        setattr(identity, field.name, None)

    def test_physical_identity_agrees_with_authenticated_profile_and_table(self):
        evaluation = modeled.authenticate_model_c()
        identity = physical.MODEL_C_V1_IDENTITY
        raw = physical.PROFILE_PATH.read_bytes()
        profile = json.loads(raw)
        self.assertEqual(identity.physical_model_id, profile["model_id"])
        self.assertIs(type(profile["physical_profile_version"]), int)
        self.assertEqual(identity.physical_profile_version, profile["physical_profile_version"])
        self.assertEqual(identity.timing_unit, profile["timing_unit"])
        self.assertEqual(identity.physical_profile_sha256, hashlib.sha256(raw).hexdigest())
        encoded = ",".join(str(value) for row in evaluation.table for value in row).encode("ascii")
        self.assertEqual(identity.timing_table_sha256, hashlib.sha256(encoded).hexdigest())
        self.assertEqual(identity.timing_table_sha256, profile["table_sha256"])
        self.assertEqual(evaluation.table, tuple(tuple(row) for row in profile["timing_table_us"]))
        self.assert_exact_values_and_types(
            {name: getattr(evaluation, name) for name in EXPECTED_PHYSICAL},
            EXPECTED_PHYSICAL,
        )

    def test_existing_benchmark_constant_names_preserve_the_frozen_values(self):
        self.assertEqual(benchmark.ALGORITHM_SPEC_VERSION, 1)
        self.assertEqual(benchmark.ALGORITHM_SPEC_SHA256, EXPECTED_ALGORITHM["algorithm_spec_sha256"])
        self.assertEqual(benchmark.PHYSICAL_MODEL_ID, EXPECTED_PHYSICAL["physical_model_id"])
        self.assertEqual(benchmark.PHYSICAL_PROFILE_VERSION, 1)
        self.assertEqual(benchmark.TIMING_UNIT, "us")
        self.assertEqual(physical.PROFILE_SHA256, EXPECTED_PHYSICAL["physical_profile_sha256"])
        self.assertEqual(physical.TABLE_SHA256, EXPECTED_PHYSICAL["timing_table_sha256"])

    def test_producer_and_evaluator_preserve_exact_nine_field_canonical_snapshot(self):
        run_identity = benchmark._benchmark_identity(EXPERT_GENERAL_V1)
        evaluation = modeled.authenticate_model_c()
        producer = run_identity["solver_config_snapshot"]
        evaluator = modeled._stage3_config(evaluation)
        expected = json.loads(EXPECTED_CONFIG_JSON)
        self.assertEqual(len(expected), 9)
        for config in (producer, evaluator):
            self.assert_exact_values_and_types(config, expected)
            self.assertEqual(json.dumps(config, sort_keys=True, separators=(",", ":")),
                             EXPECTED_CONFIG_JSON)
        self.assertEqual(producer, evaluator)
        self.assert_exact_values_and_types(
            {name: run_identity[name] for name in
             ("solver_stage", "solver_policy", "telemetry_schema_version")},
            {"solver_stage": "STAGE_3", "solver_policy": "E_FIRST_FIRST_REVEAL_V1",
             "telemetry_schema_version": 2},
        )

    def test_fresh_algorithm_identity_import_has_no_runtime_side_effects(self):
        code = textwrap.dedent("""
            import importlib.abc
            import sys

            forbidden = {
                "PyQt5", "PyQt6", "PySide2", "PySide6", "core_engine",
                "simple_algorithm", "stage3_runner", "stage3_planner",
                "stage3_physical", "stage3_execution", "stage3_benchmark_runner",
                "benchmark_modeled_time", "ui_manager", "subprocess",
            }

            class Guard(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.split(".")[0] in forbidden:
                        raise AssertionError("Runtime dependency: " + fullname)

            def audit(event, args):
                if event in ("subprocess.Popen", "os.system", "sqlite3.connect"):
                    raise AssertionError("Runtime side effect: " + event)
                if event.startswith("winreg."):
                    raise AssertionError("Settings access: " + event)
                if event == "open" and isinstance(args[0], (str, bytes)):
                    path = str(args[0]).lower()
                    if ".json" in path or "calibration" in path:
                        raise AssertionError("Profile I/O: " + path)

            sys.meta_path.insert(0, Guard())
            sys.addaudithook(audit)
            import stage3_identity
            assert stage3_identity.STAGE3_V1_IDENTITY.solver_stage == "STAGE_3"
            assert forbidden.isdisjoint(sys.modules)
        """)
        result = subprocess.run(
            [sys.executable, "-B", "-c", code], cwd=ROOT,
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
