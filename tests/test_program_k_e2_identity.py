"""I1-only synthetic selection tests; never derive a real E2/rehearsal seed stream."""

import ast
import builtins
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import hashlib
import inspect
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_records as records


SEED = bytes(range(32))
LABEL = b"I1_SYNTHETIC"


class FrozenConstantsTests(unittest.TestCase):
    def test_protocol_provenance_literals(self):
        self.assertEqual(identity.PROTOCOL_PATH, "docs/stage3-extended/STAGE3_PROGRAM_K_E2_EFFECTIVENESS_PROTOCOL.md")
        self.assertEqual(identity.PROTOCOL_SHA256, "10b1055a6e1bcab8e03ab504755c9c9d655d5457800318396afb6e31497ba2fa")
        self.assertEqual(identity.PROTOCOL_BLOB_ID, "3351017f0f0116be00917be3ff95312120f43117")
        self.assertEqual(identity.PROTOCOL_BYTE_LENGTH, 57841)
        self.assertEqual(identity.FREEZE_COMMIT, "6d3eb456d72632d24e9cab14bdeea0cffd279092")
        self.assertEqual(identity.E1_CORE_BASELINE, "6106f730320c35e7123a75526f34dbeadeef3c5d")

    def test_labels_and_frames(self):
        literals = {
            "PRIMARY_LABEL": b"PROGRAM_K_E2_PRIMARY_V1", "REHEARSAL_LABEL": b"PROGRAM_K_E2_REHEARSAL_V1",
            "CORPUS_LABEL": b"PROGRAM_K_E2_CORPUS_V1", "KCONTROL_LABEL": b"PROGRAM_K_E2_KCONTROL_V1",
            "ORACLE_B_LABEL": b"PROGRAM_K_E2_ORACLEB_V1", "DETERMINISM_LABEL": b"PROGRAM_K_E2_DETERMINISM_V1",
            "BOOT_LABEL": b"PROGRAM_K_E2_BOOTSTRAP_V1", "ORDER_LABEL": b"PROGRAM_K_E2_ARM_ORDER_V1",
        }
        for name, expected in literals.items():
            self.assertEqual(getattr(identity, name), expected)
        self.assertEqual((identity.PRIMARY_LOW, identity.PRIMARY_HIGH), (1000000000, 1001000000))
        self.assertEqual((identity.REHEARSAL_LOW, identity.REHEARSAL_HIGH), (1001000000, 1001100000))
        self.assertEqual(identity.CANDIDATE_MAX, 10000)
        self.assertEqual(identity.E2_PRIMARY_EXCLUSION_SET, frozenset())
        self.assertEqual(identity.E2_REHEARSAL_EXCLUSION_SET, frozenset())

    def test_statistical_constants_are_exact(self):
        self.assertEqual(identity.N_LADDER, (1000, 2500, 5000, 10000))
        self.assertEqual((identity.KCONTROL_CAP, identity.ORACLE_B_CAP, identity.DETERMINISM_CAP), (256, 128, 256))
        self.assertEqual(identity.PRACTICAL_MARGIN_US_PER_WW, 126005)
        self.assertEqual(identity.BOOTSTRAP_REPLICATES, 10000)
        self.assertIs(type(identity.CONFIDENCE_LEVEL), Fraction)
        self.assertEqual(identity.CONFIDENCE_LEVEL, Fraction(19, 20))
        self.assertEqual(identity.INTERVAL, "percentile")
        self.assertEqual((identity.LOWER_RANK, identity.UPPER_RANK), (250, 9750))

    def test_operational_constants(self):
        self.assertEqual((identity.MAX_DECISION_WALL_MS, identity.MAX_ARM_WALL_MS, identity.SHADOW_TIMEOUT_MS),
                         (30000, 420000, 1000))
        self.assertEqual(identity.R0_A_BOARD_COUNT, 64)
        self.assertEqual(identity.R0_A_CONCURRENCY_CANDIDATES, (1, 2, 4))
        for name, expected in (("EXECUTION_WALL_SAFETY_FACTOR", Fraction(2)),
                               ("POSTPROCESS_WALL_SAFETY_FACTOR", Fraction(2)),
                               ("ARCHIVE_BYTES_SAFETY_FACTOR", Fraction(3, 2)),
                               ("MEMORY_SAFETY_FACTOR", Fraction(3, 2))):
            self.assertIs(type(getattr(identity, name)), Fraction)
            self.assertEqual(getattr(identity, name), expected)
        self.assertEqual(identity.MAX_ACTUAL_E2_LAUNCHER_WALL_SECONDS, 43200)
        self.assertEqual(identity.MAX_COMBINED_MEMORY_BYTES, 4294967296)
        self.assertEqual(identity.MAX_ARCHIVE_BYTES, 17179869184)
        self.assertEqual(identity.FIXED_REPORT_RECEIPT_ALLOWANCE, 268435456)

    def test_exposure_registry_exact_and_immutable(self):
        registry = identity.DOCUMENTED_EXPOSURE_REGISTRY
        self.assertIs(type(registry), tuple)
        self.assertEqual(tuple((r.name, r.category.value, r.domain, tuple(sorted(r.indices))) for r in registry), (
            ("official Stage-2/Stage-3", "INDEXED_RANGE", (0, 100000), ()),
            ("B7 / B7-C", "INDEXED_RANGE", (0, 1000), ()),
            ("E/L", "INDEXED_RANGE", (100000, 110000), ()),
            ("Program-K E1", "EXPLICIT_INDICES", None, (0, 1, 2, 3, 100000)),
            ("Program-K E0", "SYNTHETIC_NON_INDEX", None, ()),
            ("R3", "SYNTHETIC_NON_INDEX", None, ()),
            ("F1", "SYNTHETIC_NON_INDEX", None, ()),
            ("fixed exemplars", "EXPLICIT_INDICES", None, (1, 73024, 73758, 93557)),
            ("ZiNi development", "INDEXED_RANGE", (1010000, 1010050), ()),
            ("ZiNi final holdout", "UNOPENED_HOLDOUT", (2010000, 2010100), ()),
            ("ZiNi tuning/internal validation", "INDEXED_RANGE", (3010000, 3010500), ()),
        ))
        with self.assertRaises(FrozenInstanceError):
            registry[0].name = "changed"
        with self.assertRaises(identity.IdentityError):
            replace(registry[5], domain=(0, 1))
        with self.assertRaises(identity.IdentityError):
            replace(registry[5], indices=frozenset((1,)))
        with self.assertRaises(identity.IdentityError):
            replace(registry[0], domain=(True, 2))


class PrimitiveTests(unittest.TestCase):
    def test_uint64_endpoints(self):
        for v, b in ((0, b"\0" * 8), ((1 << 64) - 1, b"\xff" * 8), (258, b"\0" * 6 + b"\x01\x02")):
            self.assertEqual(identity.uint64_be(v), b)
            self.assertEqual(identity.uint64_be_decode(b), v)

    def test_strict_integer_types_and_bounds(self):
        class IntSubclass(int):
            pass
        for value in (-1, 1 << 64, True, False, 1.0, "1", IntSubclass(1), None):
            with self.subTest(value=value), self.assertRaises(identity.IdentityError):
                identity.uint64_be(value)

    def test_decode_requires_exact_eight_bytes(self):
        class BytesSubclass(bytes):
            pass
        for value in (b"", b"\0" * 7, b"\0" * 9, bytearray(8), "12345678", BytesSubclass(b"12345678")):
            with self.subTest(value=value), self.assertRaises(identity.IdentityError):
                identity.uint64_be_decode(value)

    def test_hash_exact_bytes(self):
        self.assertEqual(identity.sha256_bytes(b"abc").hex(),
                         "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        for v in ("abc", bytearray(b"abc"), None):
            with self.assertRaises(identity.IdentityError):
                identity.sha256_bytes(v)

    def test_labels(self):
        self.assertEqual(identity.ascii_label(LABEL), LABEL)
        for v in (b"", b"bad\0label", b"white space", b"\xff", b"\n", "ASCII", bytearray(b"ASCII")):
            with self.assertRaises(identity.IdentityError):
                identity.ascii_label(v)

    def test_synthetic_protocol_validation(self):
        b = b"synthetic protocol fixture\n"
        digest = hashlib.sha256(b).hexdigest()
        result = identity.validate_protocol_bytes(b, expected_sha256=digest)
        self.assertEqual((result.sha256, result.seed, result.byte_length), (digest, bytes.fromhex(digest), len(b)))
        with self.assertRaises(FrozenInstanceError):
            result.byte_length = 0
        with self.assertRaises(identity.IdentityError):
            identity.validate_protocol_bytes(b)  # real default must reject synthetic content
        for expected in (digest.upper(), "bad", b"0" * 64, "0" * 64):
            with self.assertRaises(identity.IdentityError):
                identity.validate_protocol_bytes(b, expected_sha256=expected)
        with self.assertRaises(identity.IdentityError):
            identity.validate_protocol_bytes(bytearray(b), expected_sha256=digest)


class SelectionTests(unittest.TestCase):
    def test_independent_synthetic_fixture(self):
        # Independently calculated with .NET SHA256 and uint64 big-endian bytes.
        expected = (109, 101, 104, 103, 111, 100, 108)
        self.assertEqual(identity.select_indices(LABEL, SEED, 100, 113, 7, frozenset((105,))), expected)
        self.assertEqual(identity.select_indices(LABEL, SEED, 100, 113, 7, frozenset((105,))), expected)

    def test_rejection_boundary_duplicate_exclusion_and_counter_message(self):
        limit = ((1 << 64) // 13) * 13
        # Reject limit, accept limit-1, reject duplicate, reject excluded 100,
        # then accept 101. Exercise the exact biased tail rather than RNG luck.
        draws = (limit, limit - 1, limit - 1, 0, 1)
        outputs = [struct.pack(">Q", x) + bytes(24) for x in draws]
        with patch.object(identity, "sha256_bytes", side_effect=outputs) as digest:
            actual = identity.select_indices(LABEL, SEED, 100, 113, 2, frozenset((100,)))
        self.assertEqual(actual, (112, 101))
        self.assertEqual([c.args[0] for c in digest.call_args_list],
                         [LABEL + b"\0" + SEED + struct.pack(">Q", c) for c in range(5)])

    def test_empty_request_and_full_tiny_domain(self):
        with patch.object(identity, "sha256_bytes", side_effect=AssertionError("no draw required")):
            self.assertEqual(identity.select_indices(LABEL, SEED, 100, 113, 0), ())
        self.assertEqual(set(identity.select_indices(LABEL, SEED, 100, 113, 13)), set(range(100, 113)))

    def test_impossible_and_malformed_selectors(self):
        base = dict(label=LABEL, seed=SEED, low=100, high=113, count=3, exclusions=frozenset(), start_counter=0)
        cases = (dict(low=113), dict(high=99), dict(low=-1), dict(high=(1 << 64) + 1),
                 dict(high=True), dict(count=14), dict(count=True), dict(count=-1), dict(count=1.0),
                 dict(seed=b"short"), dict(seed=bytearray(SEED)), dict(label=b"bad\0label"),
                 dict(exclusions={100}), dict(exclusions=frozenset((True,))), dict(start_counter=-1),
                 dict(start_counter=1 << 64), dict(start_counter=True),
                 dict(count=13, exclusions=frozenset((100,))))
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(identity.IdentityError):
                identity.select_indices(**(base | changes))

    def test_counter_never_wraps(self):
        with patch.object(identity, "sha256_bytes", return_value=b"\xff" * 32) as mocked:
            with self.assertRaises(identity.IdentityError):
                identity.select_indices(LABEL, SEED, 100, 113, 1, start_counter=(1 << 64) - 1)
        self.assertEqual(mocked.call_count, 1)

    def test_full_uint64_domain_and_exclusion_order(self):
        with patch.object(identity, "sha256_bytes", return_value=b"\xff" * 32):
            self.assertEqual(identity.select_indices(LABEL, SEED, 0, 1 << 64, 1), ((1 << 64) - 1,))
        a = identity.select_indices(LABEL, SEED, 100, 113, 5, frozenset((100, 102, 105)))
        b = identity.select_indices(LABEL, SEED, 100, 113, 5, frozenset((105, 102, 100)))
        self.assertEqual(a, b)

    def test_corpus_bytes_independent_and_order_sensitive(self):
        indices = (103, 100, 112)
        expected = b"PROGRAM_K_E2_CORPUS_V1\0" + SEED + struct.pack(">QQQQ", 3, *indices)
        self.assertEqual(identity.corpus_bytes(SEED, 3, indices), expected)
        self.assertEqual(identity.corpus_digest(SEED, 3, indices), hashlib.sha256(expected).digest())
        self.assertNotEqual(identity.corpus_digest(SEED, 3, indices), identity.corpus_digest(SEED, 3, indices[::-1]))

    def test_corpus_strictness(self):
        for n, indices in ((2, (100, 100)), (3, (100, 101)), (2, [100, 101]), (True, (100,)),
                           (1, (True,)), (1, (-1,)), (1, (1 << 64,)), (1, (100.0,))):
            with self.assertRaises(identity.IdentityError):
                identity.corpus_digest(SEED, n, indices)

    def test_subset_independent_reference(self):
        fake_digest = b"s" * 32
        seed = hashlib.sha256(LABEL + b"\0" + SEED + b"\0" + fake_digest).digest()
        expected = []
        counter = 0
        while len(expected) < 9:
            x = struct.unpack(">Q", hashlib.sha256(LABEL + b"\0" + seed + struct.pack(">Q", counter)).digest()[:8])[0]
            counter += 1
            if x < ((1 << 64) // 13) * 13 and x % 13 not in expected:
                expected.append(x % 13)
        actual = identity.select_subset_positions(LABEL, SEED, fake_digest, 13, 9)
        self.assertEqual(actual, tuple(expected))
        self.assertEqual(len(set(actual)), 9)
        for n, count in ((0, 0), (13, 14), (True, 1), (13, True)):
            with self.assertRaises(identity.IdentityError):
                identity.select_subset_positions(LABEL, SEED, fake_digest, n, count)

    def test_arm_order_matches_independent_bytes(self):
        seen = set()
        for index in range(100, 113):
            bit = hashlib.sha256(b"PROGRAM_K_E2_ARM_ORDER_V1\0" + SEED + struct.pack(">Q", index)).digest()[0] & 1
            expected = (identity.ArmOrder.CONTROL_THEN_KP0, identity.ArmOrder.KP0_THEN_CONTROL)[bit]
            self.assertIs(identity.arm_order(SEED, index), expected)
            seen.add(expected)
        self.assertEqual(len(seen), 2)
        with self.assertRaises(identity.IdentityError):
            identity.arm_order(SEED, True)


class ImportBoundaryTests(unittest.TestCase):
    def test_source_imports_only_stdlib_and_no_dynamic_loader(self):
        for module in (identity, records):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(a.name.split(".")[0] in sys.stdlib_module_names for a in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertEqual(node.level, 0)
                    self.assertIn(node.module.split(".")[0], sys.stdlib_module_names)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"eval", "exec", "__import__", "open", "compile"})
            self.assertNotIn("__dict__", inspect.getsource(module))

    def test_module_execution_with_io_process_and_host_capture_blocked(self):
        # Read/compile only the two module sources before the monitoring boundary.
        # Executing fresh module code avoids import-cache false positives and avoids
        # confusing the import loader's own source read with module-originated I/O.
        for module in (identity, records):
            name = "_i1_import_probe_" + module.__name__.rsplit(".", 1)[-1]
            code = compile(inspect.getsource(module), module.__file__, "exec")
            probe = types.ModuleType(name)
            real_import = builtins.__import__
            def guarded_import(name, *args, **kwargs):
                if name.split(".")[0] not in sys.stdlib_module_names:
                    raise AssertionError("Non-stdlib import: " + name)
                return real_import(name, *args, **kwargs)
            targets = ((builtins, "open"), (io, "open"), (os, "open"), (os, "stat"),
                       (os, "listdir"), (os, "scandir"), (os, "getcwd"), (os, "getenv"),
                       (os, "system"), (subprocess, "Popen"), (subprocess, "run"),
                       (Path, "read_bytes"), (Path, "write_bytes"), (Path, "read_text"), (Path, "write_text"))
            with patch.dict(sys.modules, {name: probe}), ExitStack() as stack:
                for owner, attribute in targets:
                    stack.enter_context(patch.object(owner, attribute, side_effect=AssertionError("Import side effect")))
                stack.enter_context(patch.object(builtins, "__import__", side_effect=guarded_import))
                exec(code, probe.__dict__)


if __name__ == "__main__":
    unittest.main()
