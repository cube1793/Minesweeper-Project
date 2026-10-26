"""Slice 1A representation tests using bounded, supplied logical evidence only."""

from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import types
import unittest
from unittest.mock import patch
import zlib

from experiments import program_k_e2_physical as p
from experiments import program_k_e2_records as r
from tests import test_program_k_e2_records as fixtures


PROFILE = bytes.fromhex("12" * 32)
U64_MAX = (1 << 64) - 1


def _context(name="boards"):
    return p.context_for(name, PROFILE)


def _deflate(data):
    compressor = zlib.compressobj(6, zlib.DEFLATED, -15, 8, zlib.Z_DEFAULT_STRATEGY)
    return compressor.compress(data) + compressor.flush(zlib.Z_FINISH)


def _row(logical, *, name="boards", key=(0, 0, 0), mode=0,
         payload=None, logical_length=None, payload_length=None):
    """Independent wire builder permits CRC-correct negative reader cases."""
    if payload is None:
        payload = logical
    body = struct.pack(">BII", mode, len(logical) if logical_length is None else logical_length,
                       len(payload) if payload_length is None else payload_length)
    body += b"".join(p.encode_uleb128(component) for component in key) + payload
    context = (b"PKE2RF02-CHECK\0" + PROFILE + bytes((len(name),))
               + name.encode("ascii") + bytes((len(key),)))
    return body + struct.pack(">I", zlib.crc32(context + body, 0) & 0xffffffff)


class ULEB128Tests(unittest.TestCase):
    def test_exact_boundary_vectors_and_offset(self):
        vectors = ((0, b"\x00"), (1, b"\x01"), (127, b"\x7f"),
                   (128, b"\x80\x01"), (16383, b"\xff\x7f"),
                   (16384, b"\x80\x80\x01"), (U64_MAX, b"\xff" * 9 + b"\x01"))
        for value, expected in vectors:
            with self.subTest(value=value):
                self.assertEqual(p.encode_uleb128(value), expected)
                self.assertEqual(p.decode_uleb128(expected), (value, len(expected)))
                self.assertEqual(p.decode_uleb128(b"x" + expected + b"z", 1),
                                 (value, len(expected) + 1))

    def test_every_width_and_adjacent_integer_roundtrip(self):
        values = {0, U64_MAX}
        for bit in range(7, 64, 7):
            values.update(((1 << bit) - 1, 1 << bit, (1 << bit) + 1))
        for value in sorted(values):
            encoded = p.encode_uleb128(value)
            self.assertEqual(len(encoded), max(1, (value.bit_length() + 6) // 7))
            self.assertEqual(p.decode_uleb128(encoded), (value, len(encoded)))

    def test_reject_nonminimal_encodings_at_all_boundaries(self):
        for value in (0, 1, 127, 128, 16383, 16384, (1 << 63) - 1):
            encoded = p.encode_uleb128(value)
            bad = encoded[:-1] + bytes((encoded[-1] | 128,)) + b"\x00"
            with self.subTest(value=value), self.assertRaises(p.PhysicalError):
                p.decode_uleb128(bad)

    def test_truncation_overlong_overflow_and_tenth_byte(self):
        malformed = [b"", b"\x80", b"\xff", b"\x80\x80", b"\xff\xff"]
        malformed += [b"\x80" * 10, b"\x80" * 10 + b"\x00",
                      b"\xff" * 9 + b"\x02", b"\x80" * 9 + b"\x7f",
                      b"\xff" * 9 + b"\x81", b"\x80" * 9 + b"\x00"]
        for data in malformed:
            with self.subTest(data=data), self.assertRaises(p.PhysicalError):
                p.decode_uleb128(data)
        maximum = p.encode_uleb128(U64_MAX)
        for end in range(1, len(maximum)):
            with self.assertRaises(p.PhysicalError):
                p.decode_uleb128(maximum[:end])

    def test_exact_integer_domain_excludes_bool_and_subclass(self):
        class Integer(int):
            pass
        for value in (True, False, -1, 1 << 64, 1.0, "1", None, Integer(1)):
            with self.subTest(value=value), self.assertRaises(p.PhysicalError):
                p.encode_uleb128(value)
        for offset in (True, -1, 2, 0.0):
            with self.subTest(offset=offset), self.assertRaises(p.PhysicalError):
                p.decode_uleb128(b"\x00", offset)


class PayloadCodecTests(unittest.TestCase):
    def test_small_and_incompressible_payloads_remain_raw(self):
        for logical in (b"x", b"ab", bytes(range(256))):
            mode, payload = p.encode_payload(logical)
            self.assertEqual((mode, payload), (p.RAW, logical))
            self.assertEqual(p.decode_payload(mode, payload, len(logical)), logical)

    def test_strictly_smaller_rule_includes_equal_compressed_size(self):
        # Raw DEFLATE of five repeated ASCII bytes is exactly five bytes.
        logical = b"a" * 5
        self.assertEqual(len(_deflate(logical)), len(logical))
        self.assertEqual(p.encode_payload(logical), (p.RAW, logical))

    def test_compressible_and_chunk_boundary_roundtrips(self):
        for size in (65535, 65536, 65537, 3 * 65536 + 17):
            logical = (b"canonical evidence\\\"" * ((size // 20) + 1))[:size]
            self.assertEqual(len(logical), size)
            mode, payload = p.encode_payload(logical)
            self.assertEqual(mode, p.DEFLATE)
            self.assertLess(len(payload), size)
            self.assertEqual(payload, _deflate(logical))
            self.assertEqual(p.decode_payload(mode, payload, size), logical)
            self.assertEqual(p.encode_payload(logical), (mode, payload))

    def test_compressor_parameters_fresh_instances_chunks_and_one_finish(self):
        original = zlib.compressobj
        created, calls, chunks, finishes = [], [], [], []

        class Observed:
            def __init__(self, *args, **kwargs):
                calls.append((args, kwargs))
                self.inner = original(*args, **kwargs)
                created.append(self)

            def compress(self, data):
                chunks.append(len(data))
                return self.inner.compress(data)

            def flush(self, mode):
                finishes.append(mode)
                return self.inner.flush(mode)

        with patch.object(p.zlib, "compressobj", side_effect=Observed):
            for _ in range(2):
                p.encode_payload(b"a" * 65537)
        self.assertEqual(len(created), 2)
        self.assertTrue(all(0 < size <= 65536 for size in chunks))
        self.assertEqual(sum(chunks), 2 * 65537)
        self.assertEqual(finishes, [zlib.Z_FINISH, zlib.Z_FINISH])
        for args, kwargs in calls:
            supplied = dict(zip(("level", "method", "wbits", "memLevel", "strategy"), args))
            supplied.update(kwargs)
            self.assertEqual(supplied, dict(level=6, method=zlib.DEFLATED, wbits=-15,
                                           memLevel=8, strategy=zlib.Z_DEFAULT_STRATEGY))

    def test_all_inflation_calls_are_bounded_and_have_at_most_one_sentinel(self):
        original = zlib.decompressobj
        logical = b"a" * 70000
        calls = []

        class Observed:
            def __init__(self, *args, **kwargs):
                self.inner = original(*args, **kwargs)

            def decompress(self, data, max_length=0):
                calls.append(max_length)
                if not 0 < max_length <= len(logical) + 1:
                    raise AssertionError("Unbounded inflation")
                return self.inner.decompress(data, max_length)

            def __getattr__(self, name):
                if name == "flush":
                    raise AssertionError("Unbounded decoder flush")
                return getattr(self.inner, name)

        with patch.object(p.zlib, "decompressobj", side_effect=Observed):
            self.assertEqual(p.decode_payload(p.DEFLATE, _deflate(logical), len(logical)), logical)
        self.assertTrue(calls)

    def test_missing_end_trailing_data_and_concatenated_members(self):
        logical = b"b" * 2000
        compressed = _deflate(logical)
        for payload in (compressed[:-1], compressed + b"junk", compressed + compressed,
                        zlib.compress(logical), b"\xff\xff\xff"):
            with self.subTest(payload=payload[:12]), self.assertRaises(p.PhysicalError):
                p.decode_payload(p.DEFLATE, payload, len(logical))

    def test_output_underflow_overflow_and_bomb(self):
        compressed = _deflate(b"a" * 1000)
        for declared in (999, 1001, 100, 10):
            with self.subTest(declared=declared), self.assertRaises(p.PhysicalError):
                p.decode_payload(p.DEFLATE, compressed, declared)
        with self.assertRaises(p.PhysicalError):
            p.decode_payload(p.DEFLATE, _deflate(b"a" * 100000), 1000)

    def test_stalled_stream_is_rejected_without_retry(self):
        stalled = types.SimpleNamespace(eof=False, unused_data=b"", unconsumed_tail=b"x")
        with patch.object(p.zlib, "decompressobj", return_value=stalled):
            from unittest.mock import Mock
            stalled.decompress = Mock(return_value=b"")
            with self.assertRaises(p.PhysicalError):
                p.decode_payload(p.DEFLATE, b"x", 100)
            stalled.decompress.assert_called_once()

    def test_modes_raw_length_compression_relation_and_raw_only(self):
        for mode, payload, size in ((2, b"x", 1), (True, b"x", 1), (0, b"x", 2),
                                    (1, b"abc", 3), (1, b"abc", 2)):
            with self.subTest(mode=mode, size=size), self.assertRaises(p.PhysicalError):
                p.decode_payload(mode, payload, size)
        logical = b"a" * 1000
        self.assertEqual(p.encode_payload(logical, raw_only=True), (p.RAW, logical))
        with self.assertRaises(p.PhysicalError):
            p.decode_payload(p.DEFLATE, _deflate(logical), len(logical), raw_only=True)

    def test_bounds_precede_codec_allocation(self):
        with patch.object(p.zlib, "decompressobj", side_effect=AssertionError("Must reject first")):
            for size in (True, -1, 1 << 32, p.MAX_PAYLOAD_BYTES + 1):
                with self.subTest(size=size), self.assertRaises(p.PhysicalError):
                    p.decode_payload(p.DEFLATE, b"a", size)
            with self.assertRaises(p.PhysicalError):
                p.decode_payload(p.DEFLATE, b"a" * 20, 100, max_payload_bytes=10)
        with patch.object(p.zlib, "compressobj", side_effect=AssertionError("Must reject first")):
            with self.assertRaises(p.PhysicalError):
                p.encode_payload(b"a" * 11, max_payload_bytes=10)
        for bound in (True, 0, p.MAX_PAYLOAD_BYTES + 1):
            with self.assertRaises(p.PhysicalError):
                p.encode_payload(b"x", max_payload_bytes=bound)


class FrameTests(unittest.TestCase):
    def setUp(self):
        self.logical = r.encode(fixtures._fixtures()[4])
        self.context = _context()

    def test_experiment_and_support_arithmetic_at_minimum_and_maximum_keys(self):
        for name, logical, arity in (("boards", self.logical, 3),
                ("operations", r.encode(fixtures._fixtures()[15]), 1)):
            for key in ((0,) * arity, (U64_MAX,) * arity, (128,) * arity):
                with self.subTest(name=name, key=key):
                    frame = p.encode_frame(logical, key, _context(name))
                    payload_length = int.from_bytes(frame[5:9], "big")
                    self.assertEqual(len(frame), payload_length + 13 +
                                     sum(len(p.encode_uleb128(v)) for v in key))
                    decoded = p.decode_frame(frame, _context(name), expected_key=key)
                    self.assertEqual(decoded.key, key)
                    self.assertEqual(decoded.logical_bytes, logical)
                    self.assertEqual(decoded.frame_length, len(frame))
                    with self.assertRaises(FrozenInstanceError):
                        decoded.key = (1,)

    def test_no_prologue_empty_stream_and_known_boundary_recovery(self):
        frames = tuple(p.encode_frame(self.logical, (3, 0, n), self.context) for n in range(2))
        stream = b"".join(frames)
        self.assertEqual(b"".join(()), b"")
        self.assertIn(stream[0], (p.RAW, p.DEFLATE))
        self.assertFalse(stream.startswith(b"PKE2RF02"))
        first, offset = p.decode_frame_from(stream, 0, self.context, expected_key=(3, 0, 0))
        second, end = p.decode_frame_from(stream, offset, self.context, expected_key=(3, 0, 1))
        self.assertEqual((first.logical_bytes, second.logical_bytes), (self.logical, self.logical))
        self.assertEqual(end, len(stream))
        # Recovery needs an already-known boundary; damaged prefix is not scanned.
        corrupted = b"!" * len(frames[0]) + frames[1]
        recovered, end = p.decode_frame_from(corrupted, offset, self.context)
        self.assertEqual(recovered.key, (3, 0, 1))
        with self.assertRaises(p.PhysicalError):
            p.decode_frame_from(corrupted, 0, self.context)
        with self.assertRaises(p.PhysicalError):
            p.decode_frame(b"", self.context)

    def test_crc_formula_and_context_binding(self):
        frame = p.encode_frame(self.logical, (1, 2, 3), self.context)
        prefix = b"PKE2RF02-CHECK\0" + PROFILE + b"\x06boards\x03"
        expected = zlib.crc32(prefix + frame[:-4], 0) & 0xffffffff
        self.assertEqual(int.from_bytes(frame[-4:], "big"), expected)
        self.assertEqual(p.contextual_crc32(self.context, frame[:-4]), expected)
        for context in (_context("runtime"), p.context_for("boards", b"z" * 32)):
            with self.assertRaises(p.PhysicalError):
                p.decode_frame(frame, context)
        with self.assertRaises(p.PhysicalError):
            p.decode_frame(frame, self.context, expected_key=(1, 2, 4))

    def test_corrupt_crc_is_rejected_before_inflation_or_canonical_decode(self):
        frame = p.encode_frame(self.logical, (0, 0, 0), self.context)
        bad = frame[:-1] + bytes((frame[-1] ^ 1,))
        with patch.object(p.zlib, "decompressobj", side_effect=AssertionError("CRC first")), \
                patch.object(r, "decode", side_effect=AssertionError("CRC first")):
            with self.assertRaises(p.PhysicalError):
                p.decode_frame(bad, self.context)

    def test_every_byte_corruption_fails_closed(self):
        frame = p.encode_frame(self.logical, (0, 0, 0), self.context)
        for index in range(len(frame)):
            bad = frame[:index] + bytes((frame[index] ^ 1,)) + frame[index + 1:]
            with self.subTest(index=index), self.assertRaises(p.PhysicalError):
                p.decode_frame(bad, self.context)

    def test_all_prefix_key_payload_crc_truncations_and_trailing_bytes(self):
        frame = p.encode_frame(self.logical, (U64_MAX,) * 3, self.context)
        for end in range(len(frame)):
            with self.subTest(end=end), self.assertRaises(p.PhysicalError):
                p.decode_frame(frame[:end], self.context)
        for trailing in (b"\x00", frame):
            with self.assertRaises(p.PhysicalError):
                p.decode_frame(frame + trailing, self.context)

    def test_prefix_lengths_and_key_malformed_before_body_allocation(self):
        for row in (struct.pack(">BII", 0, 1 << 31, 1 << 31) + b"\0" * 7,
                    struct.pack(">BII", 1, 10, 10) + b"\0" * 17,
                    struct.pack(">BII", 0, 1, 1) + b"\x80" * 10,
                    struct.pack(">BII", 0, 1, 1) + b"\x80\0\0\0x\0\0\0\0"):
            with self.subTest(row=row), self.assertRaises(p.PhysicalError):
                p.decode_frame(row, self.context)

    def test_crc_correct_raw_and_deflate_malformations(self):
        compressed = _deflate(self.logical)
        rows = (
            _row(self.logical, mode=9),
            _row(self.logical, logical_length=len(self.logical) + 1),
            _row(self.logical, mode=1, payload=compressed[:-1]),
            _row(self.logical, mode=1, payload=compressed + b"trailing"),
            _row(self.logical, mode=1, payload=compressed * 2),
            _row(self.logical, mode=1, payload=compressed, logical_length=len(self.logical) - 1),
            _row(self.logical, mode=1, payload=compressed, logical_length=len(self.logical) + 1),
            _row(self.logical, mode=1, payload=self.logical),
        )
        for row in rows:
            with self.subTest(row=row[:9]), self.assertRaises(p.PhysicalError):
                p.decode_frame(row, self.context)

    def test_coverage_writer_raw_reader_rejects_crc_correct_deflate(self):
        logical = r.encode(fixtures._oracle_coverage_fixture())
        for name in ("oracle_b_coverage", "repeat_oracle_b_coverage"):
            frame = p.encode_frame(logical, (0, 0, 0), _context(name))
            self.assertEqual(frame[0], p.RAW)
            self.assertEqual(frame[12:-4], logical)
            self.assertEqual(p.decode_frame(frame, _context(name)).logical_bytes, logical)
            bad = _row(logical, name=name, mode=1, payload=_deflate(logical))
            with self.assertRaises(p.PhysicalError):
                p.decode_frame(bad, _context(name))

    def test_context_is_closed_exact_and_not_caller_mutable(self):
        for name in ("", "arbitrary", "b" * 65, "böards", True):
            with self.subTest(name=name), self.assertRaises(p.PhysicalError):
                p.context_for(name, PROFILE)
        for digest in (b"x" * 31, b"x" * 33, "12" * 32, bytearray(PROFILE)):
            with self.assertRaises(p.PhysicalError):
                p.context_for("boards", digest)
        for changes in (dict(expected_key_arity=1), dict(expected_key_arity=True),
                        dict(stream_registry_revision=2), dict(frame_format="PKE2RF01"),
                        dict(allowed_logical_record_types=(r.RuntimeIdentity,))):
            with self.assertRaises(p.PhysicalError):
                replace(self.context, **changes)
        for key in ((1,), (1, 2), (1, 2, 3, 4), (True, 0, 0), [0, 0, 0]):
            with self.assertRaises(p.PhysicalError):
                p.encode_frame(self.logical, key, self.context)

    def test_registry_matches_existing_execution_and_support_ownership(self):
        from experiments import program_k_e2_execution as execution
        specs = {item.name: item for item in p.STREAM_REGISTRY}
        support = {"operations": (r.OperationEventRecord,), "resources": (r.ResourceSampleRecord,),
                   "qualification_identity": (r.ProtocolIdentity, r.CorpusIdentity,
                                               r.RuntimeIdentity, r.SourceBlobIdentity),
                   "postprocessing_operations": (r.OperationEventRecord,)}
        self.assertEqual(set(specs), set(execution.STREAM_NAMES) | set(support))
        for name in execution.STREAM_NAMES:
            self.assertEqual(specs[name].key_arity, 3)
            self.assertEqual(specs[name].record_types, (execution._family(name),))
        for name, classes in support.items():
            self.assertEqual(specs[name].key_arity, 1)
            self.assertEqual(set(specs[name].record_types), set(classes))
        self.assertEqual({name for name, spec in specs.items() if spec.raw_only},
                         {"oracle_b_coverage", "repeat_oracle_b_coverage"})

    def test_canonical_type_validation_never_normalizes_logical_bytes(self):
        for logical in (self.logical + b"\n", self.logical.replace(b'"fields":', b'"fields": '),
                        r.encode(fixtures._fixtures()[1]), b"{}"):
            with self.subTest(logical=logical[:40]):
                with self.assertRaises(p.PhysicalError):
                    p.encode_frame(logical, (0, 0, 0), self.context)
                with self.assertRaises(p.PhysicalError):
                    p.decode_frame(_row(logical), self.context)


class LogicalCompatibilityTests(unittest.TestCase):
    def test_historical_canonical_hashes_and_representative_types_are_unchanged(self):
        from experiments import program_k_e2_execution as execution
        values = fixtures._fixtures() + (fixtures._decision_fixture(), fixtures._certificate_audit_fixture(),
            fixtures._oracle_audit_fixture(), fixtures._determinism_summary_fixtures()[0],
            fixtures._kc_fixture(), fixtures._kc_fixture(reference=True), fixtures._oracle_coverage_fixture())
        for value in values:
            logical = r.encode(value)
            known_hash = fixtures._OLD_RECORD_SHA256.get(type(value).__name__)
            if known_hash is not None:
                self.assertEqual(hashlib.sha256(logical).hexdigest(), known_hash)
            candidates = [spec for spec in p.STREAM_REGISTRY if type(value) in spec.record_types]
            # CompletionReceipt is an outer closure, not a stream record.
            if type(value) is r.CompletionReceipt:
                self.assertFalse(candidates)
                continue
            self.assertTrue(candidates, type(value).__name__)
            spec = candidates[0]
            key = (0,) * spec.key_arity
            result = p.decode_frame(p.encode_frame(logical, key, _context(spec.name)), _context(spec.name))
            self.assertEqual(result.logical_bytes, logical)
            self.assertEqual(r.decode(result.logical_bytes), value)
            self.assertEqual(r.encode(r.decode(result.logical_bytes)), logical)

    def test_certificate_and_oracle_semantic_digests_full_premises_and_failure_survive(self):
        certificate = fixtures._certificate_audit_fixture("EXACT_GLOBAL")
        oracle = fixtures._oracle_audit_fixture()
        failed_snapshot = replace(oracle.actual, total_worlds=-7, minimum_risk=Fraction(-1, 3))
        failed = replace(oracle, actual=failed_snapshot,
                         actual_digest=r.oracle_b_snapshot_digest(failed_snapshot),
                         status=r.AuditStatus.FAIL, differences=("EXACT_COUNTS_DIFFER",))
        for name, value in (("certificate_audits", certificate), ("oracle_b_audits", oracle),
                            ("repeat_oracle_b_audits", failed)):
            logical = r.encode(value)
            restored = r.decode(p.decode_frame(p.encode_frame(logical, (7, 2, 1), _context(name)),
                                               _context(name)).logical_bytes)
            self.assertEqual(restored, value)
            if isinstance(restored, r.CertificateAuditRecord):
                self.assertEqual(r.certificate_premises_digest(restored.certificate_premises),
                                 certificate.acquisition.certificate_sha256)
            else:
                self.assertEqual(r.oracle_b_snapshot_digest(restored.expected), value.expected_digest)
                self.assertEqual(r.oracle_b_snapshot_digest(restored.actual), value.actual_digest)


class ImportPurityTests(unittest.TestCase):
    def test_module_execution_has_no_io_process_generation_or_qualification(self):
        import benchmark_board
        source = Path(p.__file__).read_text(encoding="utf-8")
        code = compile(source, p.__file__, "exec")
        probe = types.ModuleType("_slice1a_physical_import_probe")
        probe.__file__ = p.__file__
        forbidden = AssertionError("Import-time I/O or workload is forbidden")
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {probe.__name__: probe}))
            for owner, name in ((Path, "open"), (Path, "read_bytes"), (Path, "read_text"),
                                (Path, "write_bytes"), (Path, "write_text"), (subprocess, "Popen"),
                                (subprocess, "run"), (benchmark_board, "generate_board"),
                                (zlib, "compressobj")):
                stack.enter_context(patch.object(owner, name, side_effect=forbidden))
            stack.enter_context(patch("builtins.open", side_effect=forbidden))
            exec(code, probe.__dict__)
        self.assertEqual(probe.FRAME_FORMAT, "PKE2RF02")


def _profile_facts():
    writers = tuple(dict(role=role, path=role + ".py", byte_length=1, sha256="a" * 64)
                    for role in ("logical_records", "physical", "worker_bundle"))
    runtime = {key: "synthetic" for key in ("python_implementation", "python_version",
               "python_abi", "platform", "zlib_build_version", "zlib_runtime_version")}
    runtime.update(artifacts=[dict(role="interpreter", path="test-python", byte_length=1,
                                  sha256="b" * 64)],
                   unresolved=["native_dependency_closure", "operational_qualification"])
    return writers, runtime


def _json_bytes(node):
    return json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.writers, self.runtime = _profile_facts()
        self.profile = p.profile_from_facts(writer_sources=self.writers, runtime=self.runtime)

    def test_deterministic_closed_canonical_profile_and_digest(self):
        original = self.profile.canonical_bytes
        self.assertTrue(original.isascii())
        self.assertEqual(_json_bytes(json.loads(original)), original)
        self.assertEqual(self.profile.sha256, hashlib.sha256(original).digest())
        self.assertEqual(p.decode_profile(original), self.profile)
        reordered_runtime = dict(reversed(tuple(self.runtime.items())))
        self.assertEqual(p.profile_from_facts(writer_sources=self.writers, runtime=reordered_runtime),
                         self.profile)
        node = json.loads(original)
        self.assertEqual(set(node), {"schema_version", "status", "contract", "writer_sources",
                                     "runtime", "constructor_policies"})
        self.assertEqual(node["contract"]["frame_format"], "PKE2RF02")
        self.assertEqual(node["contract"]["bundle_format"], "PKE2WB02")
        self.assertEqual(node["contract"]["compression"]["chunk_bytes"], 65536)
        self.assertEqual(node["contract"]["limits"]["experiment_frame_bytes"], 67108864 + 43)
        self.assertEqual(node["contract"]["limits"]["support_frame_bytes"], 67108864 + 23)

    def test_profile_copies_facts_into_immutable_bytes(self):
        before = self.profile.canonical_bytes
        self.writers[0]["sha256"] = "c" * 64
        self.runtime["artifacts"].clear()
        self.assertEqual(self.profile.canonical_bytes, before)
        with self.assertRaises(FrozenInstanceError):
            self.profile.canonical_bytes = b"{}"

    def test_every_runtime_and_source_identity_is_digest_bound(self):
        for key in ("python_implementation", "python_version", "python_abi", "platform",
                    "zlib_build_version", "zlib_runtime_version"):
            writers, runtime = _profile_facts()
            runtime[key] += "-different"
            changed = p.profile_from_facts(writer_sources=writers, runtime=runtime)
            self.assertNotEqual(changed.sha256, self.profile.sha256)
        for index in range(3):
            writers, runtime = _profile_facts()
            writers[index]["sha256"] = "c" * 64
            self.assertNotEqual(p.profile_from_facts(writer_sources=writers, runtime=runtime).sha256,
                                self.profile.sha256)
        writers, runtime = _profile_facts()
        runtime["artifacts"][0]["sha256"] = "c" * 64
        self.assertNotEqual(p.profile_from_facts(writer_sources=writers, runtime=runtime).sha256,
                            self.profile.sha256)
        policy = (dict(name="synthetic-test-policy", sha256="d" * 64),)
        self.assertNotEqual(p.profile_from_facts(writer_sources=self.writers, runtime=self.runtime,
                                                constructor_policies=policy).sha256, self.profile.sha256)

    def test_unknown_missing_and_changed_contract_facts_rejected(self):
        for key in json.loads(self.profile.canonical_bytes):
            node = json.loads(self.profile.canonical_bytes)
            del node[key]
            with self.subTest(missing=key), self.assertRaises(p.PhysicalError):
                p.decode_profile(_json_bytes(node))
        for mutation in (
                lambda node: node.update(extra=1),
                lambda node: node["runtime"].update(extra=1),
                lambda node: node["contract"].update(frame_format="PKE2RF01"),
                lambda node: node["contract"]["compression"].update(level=9),
                lambda node: node["contract"]["streams"][0].update(key_arity=1),
                lambda node: node["writer_sources"].pop(),
                lambda node: node["runtime"].update(artifacts=[]),
                lambda node: node.update(schema_version=True),
                lambda node: node["writer_sources"][0].update(byte_length=True),
                lambda node: node["contract"].update(stream_registry_revision=True)):
            node = json.loads(self.profile.canonical_bytes)
            mutation(node)
            with self.assertRaises(p.PhysicalError):
                p.decode_profile(_json_bytes(node))

    def test_noncanonical_duplicate_float_nan_and_nonascii_rejected(self):
        raw = self.profile.canonical_bytes
        bad_inputs = [raw + b"\n", b'{"schema_version":1,' + raw[1:],
                      raw.replace(b'"schema_version":1', b'"schema_version":1.0'),
                      raw.replace(b'"schema_version":1', b'"schema_version":NaN'),
                      raw.replace(b'"schema_version":1', b'"schema_version":Infinity'),
                      raw.replace(b"synthetic", b"\xff", 1)]
        for bad in bad_inputs:
            with self.assertRaises(p.PhysicalError):
                p.decode_profile(bad)
        for value in (1.5, float("nan"), True, 0, -1):
            writers, runtime = _profile_facts()
            writers[0]["byte_length"] = value
            with self.assertRaises(p.PhysicalError):
                p.profile_from_facts(writer_sources=writers, runtime=runtime)

    def test_no_claim_or_flag_can_grant_operational_qualification(self):
        self.assertFalse(self.profile.qualified)
        with self.assertRaises(p.PhysicalError):
            p.require_qualified_profile(self.profile)
        node = json.loads(self.profile.canonical_bytes)
        node["status"] = "QUALIFIED"
        with self.assertRaises(p.PhysicalError):
            p.decode_profile(_json_bytes(node))
        # Even supplied facts claiming no unresolved dependencies are not a qualification receipt.
        self.runtime["unresolved"] = []
        profile = p.profile_from_facts(writer_sources=self.writers, runtime=self.runtime)
        self.assertFalse(profile.qualified)
        with self.assertRaises(p.PhysicalError):
            p.require_qualified_profile(profile)
        with self.assertRaises(TypeError):
            p.profile_from_facts(writer_sources=self.writers, runtime=self.runtime, qualified=True)

    def test_capture_is_explicit_read_only_and_preserves_unresolved_dependencies(self):
        opened = []

        def read_artifact(path, mode):
            self.assertEqual(mode, "rb")
            opened.append(str(path))
            return io.BytesIO(b"synthetic artifact bytes")

        with patch.object(Path, "open", autospec=True, side_effect=read_artifact), \
                patch.object(subprocess, "Popen", side_effect=AssertionError("No process")), \
                patch.object(subprocess, "run", side_effect=AssertionError("No process")):
            profile = p.capture_profile()
        self.assertGreaterEqual(len(opened), 4)
        node = json.loads(profile.canonical_bytes)
        self.assertEqual({source["role"] for source in node["writer_sources"]},
                         {"logical_records", "physical", "worker_bundle"})
        for item in node["writer_sources"] + node["runtime"]["artifacts"]:
            self.assertEqual(item["sha256"], hashlib.sha256(b"synthetic artifact bytes").hexdigest())
        self.assertIn("native_dependency_closure", node["runtime"]["unresolved"])
        self.assertIn("constructor_policy_identities", node["runtime"]["unresolved"])
        self.assertFalse(profile.qualified)

    def test_capture_missing_artifact_fails_closed(self):
        with patch.object(Path, "open", side_effect=OSError("synthetic missing artifact")):
            with self.assertRaises(p.PhysicalError):
                p.capture_profile()


if __name__ == "__main__":
    unittest.main()
