"""Production physical-table integrity; no calibration code is an oracle."""

import ast
import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import stage3_physical as physical


class Stage3PhysicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = physical.load_timing_table()

    def test_frozen_whole_profile_hash(self):
        self.assertEqual(
            hashlib.sha256(physical.PROFILE_PATH.read_bytes()).hexdigest(),
            "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b",
        )

    def test_frozen_table_canonical_hash_and_shape(self):
        encoded = ",".join(str(tick) for row in self.table for tick in row).encode("ascii")
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),
                         "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b")
        self.assertEqual(len(self.table), 30)
        self.assertTrue(all(type(row) is tuple and len(row) == 16 for row in self.table))
        self.assertTrue(all(type(tick) is int and tick > 0 for row in self.table for tick in row))

    def test_representative_ticks_from_frozen_spec(self):
        for target, tick in {
            (0, 0): 126005, (1, 0): 126005, (1, 1): 144891,
            (3, 0): 227896, (4, 3): 294552, (8, 6): 394196,
            (10, 0): 394196, (20, 10): 518010, (29, 15): 578005,
        }.items():
            with self.subTest(target=target):
                self.assertEqual(physical.action_cost(self.table, (0, 0), target), tick)
                self.assertEqual(physical.action_cost(self.table, target, (0, 0)), tick)

    def test_exact_displacement_and_input_floor(self):
        self.assertEqual(physical.action_cost(self.table, (20, 14), (16, 11)), 294552)
        self.assertEqual(physical.action_cost(self.table, (20, 14), (20, 14)), 126005)

    def test_any_profile_byte_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "profile.json"
            for raw in (physical.PROFILE_PATH.read_bytes() + b" ", b"{}", b"not json"):
                with self.subTest(raw_length=len(raw)):
                    target.write_bytes(raw)
                    with self.assertRaisesRegex(ValueError, "profile SHA-256"):
                        physical.load_timing_table(target)

    def test_each_required_metadata_field_is_checked_independently(self):
        original = json.loads(physical.PROFILE_PATH.read_bytes())
        changes = {
            "model_id": "other", "timing_tick_unit": "1_ms", "timing_unit": "ms",
            "distance_unit": "pixels", "grid_width": 29, "grid_height": 15,
            "table_dimensions": [16, 30], "table_order": "dy_major_dx_minor",
            "table_encoding": "json", "table_sha256": "0" * 64,
        }
        # Bypass only the outer digest so the inner metadata guard is exercised.
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "profile.json"
            for name, value in changes.items():
                with self.subTest(name=name):
                    payload = {**original, name: value}
                    raw = json.dumps(payload).encode()
                    target.write_bytes(raw)
                    with patch.object(physical, "PROFILE_SHA256", hashlib.sha256(raw).hexdigest()):
                        with self.assertRaisesRegex(ValueError, name):
                            physical.load_timing_table(target)

    def test_mutated_table_fails_independent_hash(self):
        table = [list(row) for row in self.table]
        table[29][15] += 1
        with self.assertRaisesRegex(ValueError, "table SHA-256"):
            physical.validate_timing_table(table)

    def test_shape_and_positive_true_integer_validation(self):
        invalid_tables = [self.table[:-1], [row[:-1] for row in self.table], None]
        for invalid in (0, -1, True, 126005.0, "126005"):
            table = [list(row) for row in self.table]
            table[0][0] = invalid
            invalid_tables.append(table)
        for table in invalid_tables:
            with self.subTest(table_type=type(table)):
                with self.assertRaises(ValueError):
                    physical.validate_timing_table(table)

    def test_validated_table_is_immutable_detached_from_input_lists(self):
        mutable = [list(row) for row in self.table]
        validated = physical.validate_timing_table(mutable)
        mutable[0][0] = 1
        self.assertEqual(validated[0][0], 126005)
        with self.assertRaises(TypeError):
            validated[0][0] = 1

    def test_unsupported_coordinates_fail_closed(self):
        for coordinate in ((30, 0), (0, 16), (-1, 0), (False, 0), (1.0, 0), (0,)):
            with self.subTest(coordinate=coordinate):
                with self.assertRaises(ValueError):
                    physical.action_cost(self.table, (0, 0), coordinate)

    def test_loader_does_not_read_coefficients_or_formula(self):
        class ProvenanceGuard(dict):
            def get(self, key, default=None):
                if key.startswith("fitted_") or key in ("numeric_contract", "model_formula"):
                    raise AssertionError("Calibration provenance used at runtime")
                return super().get(key, default)

            def __getitem__(self, key):
                if key.startswith("fitted_") or key in ("numeric_contract", "model_formula"):
                    raise AssertionError("Calibration provenance used at runtime")
                return super().__getitem__(key)

        guarded = ProvenanceGuard(json.loads(physical.PROFILE_PATH.read_bytes()))
        with patch.object(physical.json, "loads", return_value=guarded):
            self.assertEqual(physical.load_timing_table(), self.table)

    def test_no_calibration_or_regeneration_dependencies(self):
        source = inspect.getsource(physical)
        parsed = ast.parse(source)
        imports = []
        for node in ast.walk(parsed):
            if isinstance(node, ast.Import):
                imports.extend(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        self.assertFalse(any("calibration" in name or "experiment" in name for name in imports))
        self.assertNotIn("math", imports)
        self.assertNotIn("decimal", imports)
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                             and node.func.attr in ("log2", "sqrt", "ln") for node in ast.walk(parsed)))


if __name__ == "__main__":
    unittest.main()
