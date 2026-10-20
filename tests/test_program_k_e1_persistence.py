"""Slice-6 codec/publication tests using manual evidence and temporary roots only."""

import ast
from contextlib import ExitStack
from dataclasses import dataclass, fields, replace
from fractions import Fraction
import hashlib
import inspect
import json
import math
import multiprocessing
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import benchmark_board
import board_snapshot
import core_engine
from experiments import program_k_e1_audit as audit
from experiments import program_k_e1_execution as execution
from experiments import program_k_e1_evaluator as e1_evaluator
from experiments import program_k_e1_harness as e1
from experiments import program_k_e1_operational as operational
from experiments import program_k_e1_persistence as persistence
from experiments import program_k_e1_qualification as qualification
from experiments import program_k_e1_suite as suite
from experiments import program_k_evaluator as evaluator
from experiments import program_k_harness as harness
from tests.test_program_k_e1_qualification import _record


def _wire(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":")).encode("ascii")


def _corrupt(value, **changes):
    candidate = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(candidate, field.name, changes.get(field.name, getattr(value, field.name)))
    return candidate


class CodecTests(unittest.TestCase):
    def test_exact_primitives_and_large_integer(self):
        values = (None, False, True, 0, 1, -1, 2 ** 20000, -(2 ** 20000),
                  "", "E1 qualification", "\u03b1\ud55c\uad6d\uc5b4")
        rebuilt = persistence.reconstruct(persistence.canonical_bytes(values))
        self.assertEqual(rebuilt, values)
        for original, decoded in zip(values, rebuilt):
            self.assertIs(type(decoded), type(original))

    def test_bool_int_encodings_are_distinct(self):
        self.assertNotEqual(persistence.canonical_bytes(True), persistence.canonical_bytes(1))
        self.assertNotEqual(persistence.canonical_bytes(False), persistence.canonical_bytes(0))
        for malformed in (["bool", 1], ["int", True], ["str", 1]):
            with self.subTest(malformed=malformed), self.assertRaises(persistence.E1PersistenceError):
                persistence.reconstruct(_wire(malformed))

    def test_float_hex_preserves_exact_bits_including_negative_zero(self):
        values = (0.0, -0.0, 0.1, math.nextafter(1.0, 2.0),
                  float.fromhex("0x0.0000000000001p-1022"),
                  float.fromhex("0x1.fffffffffffffp+1023"))
        rebuilt = persistence.reconstruct(persistence.canonical_bytes(values))
        self.assertEqual(tuple(v.hex() for v in rebuilt), tuple(v.hex() for v in values))
        self.assertIn(b"-0x0.0p+0", persistence.canonical_bytes(values))

    def test_fraction_exactness(self):
        values = (Fraction(0), Fraction(-7, 13), Fraction(2 ** 20000, 3 ** 7000))
        self.assertEqual(persistence.reconstruct(persistence.canonical_bytes(values)), values)

    def test_every_allowed_enum_and_member_roundtrips(self):
        for cls in persistence._ENUM_TYPES:
            for member in cls:
                with self.subTest(enum=cls.__name__, member=member.name):
                    self.assertIs(persistence.reconstruct(persistence.canonical_bytes(member)), member)

    def test_tuple_preserves_order_and_empty_collections(self):
        value = ((), frozenset(), (3, 2, 1), ((1, 2), (2, 1)))
        self.assertEqual(persistence.reconstruct(persistence.canonical_bytes(value)), value)

    def test_frozenset_is_deterministic_and_coordinates_sort_y_x(self):
        members = ((2, 0), (0, 2), (1, 1), (0, 0))
        first, second = frozenset(members), frozenset(reversed(members))
        raw = persistence.canonical_bytes(first)
        self.assertEqual(raw, persistence.canonical_bytes(second))
        node = json.loads(raw)
        ordered = tuple(persistence.reconstruct(_wire(child)) for child in node[1])
        self.assertEqual(ordered, tuple(sorted(members, key=lambda c: (c[1], c[0]))))
        mixed = frozenset(("one", (2, 3), Fraction(1, 3), None))
        self.assertEqual(persistence.reconstruct(persistence.canonical_bytes(mixed)), mixed)

    def test_unknown_tag_and_type_are_rejected_without_import(self):
        for value in (["unknown"], ["record", "subprocess.Popen", []],
                      ["enum", "unknown.Action", "OPEN"],
                      ["enum", "core_engine.Action", "UNREGISTERED"]):
            with self.subTest(value=value), self.assertRaises(persistence.E1PersistenceError):
                persistence.reconstruct(_wire(value))

    def test_arbitrary_frozen_dataclass_and_subclasses_are_rejected(self):
        @dataclass(frozen=True)
        class Unknown:
            value: int

        class IntegerSubclass(int):
            pass

        class EventSubclass(operational.E1MonitorEvent):
            pass

        for value in (Unknown(1), IntegerSubclass(2), EventSubclass(0, "STARTED", 0, 0)):
            with self.subTest(value=type(value).__name__), self.assertRaises(persistence.E1PersistenceError):
                persistence.canonical_bytes(value)

    def test_mutable_payloads_are_rejected(self):
        for value in ([], {}, set(), bytearray(b"x"), {"tuple": []}):
            with self.subTest(value=type(value).__name__), self.assertRaises(persistence.E1PersistenceError):
                persistence.canonical_bytes(value)
        for raw in (b"[]", b"{}", b'{"a":1,"a":2}', b'["tuple",{}]', b'["tuple",[{}]]'):
            with self.subTest(raw=raw), self.assertRaises(persistence.E1PersistenceError):
                persistence.reconstruct(raw)

    def test_extra_missing_duplicate_and_reordered_fields_rejected(self):
        event = operational.E1MonitorEvent(0, "STARTED", 1, 0)
        original = json.loads(persistence.canonical_bytes(event))
        variants = []
        extra = json.loads(_wire(original))
        extra[2].append(["unexpected", ["none"]])
        variants.append(extra)
        missing = json.loads(_wire(original))
        missing[2].pop()
        variants.append(missing)
        duplicate = json.loads(_wire(original))
        duplicate[2].append(duplicate[2][0])
        variants.append(duplicate)
        reordered = json.loads(_wire(original))
        reordered[2].reverse()
        variants.append(reordered)
        for node in variants:
            with self.subTest(node=node), self.assertRaises(persistence.E1PersistenceError):
                persistence.reconstruct(_wire(node))

    def test_nonfinite_float_and_json_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaises(persistence.E1PersistenceError):
                persistence.canonical_bytes(value)
        for raw in (b"NaN", b"Infinity", b"-Infinity", b'["float","nan"]',
                    b'["float","inf"]', b'["float","-inf"]'):
            with self.subTest(raw=raw), self.assertRaises(persistence.E1PersistenceError):
                persistence.reconstruct(raw)

    def test_hidden_answer_and_live_owners_rejected(self):
        answer = evaluator.HiddenAnswer("codec-test", "manual", 2, 1, frozenset({(1, 0)}))
        values = (answer, object.__new__(core_engine.MinesweeperEngine),
                  object.__new__(board_snapshot.BoardSnapshot),
                  lambda: None, threading.Thread(), multiprocessing.Process())
        for value in values:
            with self.subTest(value=type(value).__name__), self.assertRaises(persistence.E1PersistenceError):
                persistence.canonical_bytes(value)
        self.assertNotIn(evaluator.HiddenAnswer, persistence._RECORD_TYPES)
        self.assertNotIn(e1._CaseDefinition, persistence._RECORD_TYPES)

    def test_unexpected_record_attachment_rejected(self):
        value = harness.MemoryEvidence(1, 2, 1, 10, 100)
        object.__setattr__(value, "unexpected", "payload")
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.canonical_bytes(value)

    def test_noncanonical_encodings_and_duplicate_members_rejected(self):
        for raw in (b'["int","01"]', b'["int","-0x0"]', b'["fraction","0x2","0x4"]',
                    b'["float","0.1"]', b'["none"]\n',
                    b'["frozenset",[["int","0x1"],["int","0x1"]]]',
                    b'["frozenset",[["int","0x2"],["int","0x1"]]]',
                    b'["none",false]', b'["str","\xc3\xa9"]'):
            with self.subTest(raw=raw), self.assertRaises(persistence.E1PersistenceError):
                persistence.reconstruct(raw)

    def test_digest_and_bytes_type_are_checked(self):
        raw = persistence.canonical_bytes(("test", 17))
        self.assertEqual(persistence.reconstruct(
            raw, expected_digest=hashlib.sha256(raw).hexdigest()), ("test", 17))
        for bad in ("0" * 64, "bad", True):
            with self.subTest(bad=bad), self.assertRaises(persistence.E1PersistenceError):
                persistence.reconstruct(raw, expected_digest=bad)
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.reconstruct(raw.decode("ascii"))

    def test_codec_source_has_no_dynamic_execution_or_pickle_loader(self):
        tree = ast.parse(inspect.getsource(persistence))
        prohibited = {"eval", "exec", "__import__", "compile"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, prohibited)
            if isinstance(node, ast.Import):
                self.assertFalse(any(name.name in ("pickle", "importlib") for name in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, ("pickle", "importlib"))
        self.assertEqual(len(persistence._RECORD_BY_TAG), len(persistence._RECORD_TYPES))
        self.assertTrue(all(cls.__dataclass_params__.frozen for cls in persistence._RECORD_TYPES))


class CompleteRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = _record()

    def test_complete_manual_record_roundtrip_is_exact(self):
        record = self.record
        raw = persistence.canonical_bytes(record)
        decoded = persistence.reconstruct(raw)
        self.assertIs(type(decoded), qualification.E1QualificationRecord)
        self.assertEqual(decoded, record)
        self.assertEqual(persistence.canonical_bytes(decoded), raw)
        self.assertEqual(persistence.canonical_bytes(record), raw)
        self.assertEqual(len(decoded.scheduled_results), 54)
        self.assertEqual(len(decoded.evaluator_results), 18)
        for left, right in zip(record.scheduled_results, decoded.scheduled_results):
            self.assertEqual(persistence.canonical_bytes(left.archive), persistence.canonical_bytes(right.archive))
            self.assertEqual(persistence.canonical_bytes(left.audit), persistence.canonical_bytes(right.audit))
            self.assertEqual(left.receipt, right.receipt)
        for left, right in zip(record.evaluator_results, decoded.evaluator_results):
            self.assertEqual(persistence.canonical_bytes(left.evaluation),
                             persistence.canonical_bytes(right.evaluation))
            self.assertEqual(left.receipt, right.receipt)
        self.assertEqual(decoded.source_identity, record.source_identity)
        self.assertEqual(decoded.operating_envelope, record.operating_envelope)
        self.assertEqual(qualification.assess_e1(decoded), qualification.assess_e1(record))

    def test_compare_false_timing_fields_remain_in_codec(self):
        trace = self.record.scheduled_results[2].archive.result.traces[0]
        self.assertFalse(next(f for f in fields(trace) if f.name == "timings").compare)
        changed = replace(trace, timings=replace(
            trace.timings, evidence_ns=(trace.timings.evidence_ns or 0) + 123))
        self.assertEqual(trace, changed)
        self.assertNotEqual(persistence.canonical_bytes(trace), persistence.canonical_bytes(changed))
        rebuilt = persistence.reconstruct(persistence.canonical_bytes(changed))
        self.assertEqual(rebuilt.timings, changed.timings)

    def test_standalone_historical_receipt_and_result_need_no_live_runtime(self):
        result = self.record.scheduled_results[0]
        with patch.object(e1, "capture_runtime_identity", side_effect=AssertionError("live runtime")), \
                patch.object(operational, "capture_operational_source_identity",
                             side_effect=AssertionError("live source")):
            for value in (result.receipt, result):
                rebuilt = persistence.reconstruct(persistence.canonical_bytes(value))
                self.assertIs(type(rebuilt), type(value))
                self.assertEqual(persistence.canonical_bytes(rebuilt), persistence.canonical_bytes(value))

    def test_temp_root_complete_publication_and_reconstruction(self):
        record = self.record
        assessment = qualification.assess_e1(record)
        original_suite = qualification.reconstruct_e1_suite(record)
        original_resources = qualification.reconstruct_e1_resources(record)
        with tempfile.TemporaryDirectory() as root:
            receipt = persistence.persist_e1_qualification(record, repository_root=root)
            directory = Path(root) / "results" / "program_k_research" / record.run_id
            read_record, read_receipt, read_assessment = persistence.read_e1_qualification_artifact(directory)
            self.assertEqual((read_record, read_receipt, read_assessment),
                             (record, receipt, assessment))
            self.assertEqual(persistence.canonical_bytes(
                qualification.reconstruct_e1_suite(read_record)), persistence.canonical_bytes(original_suite))
            self.assertEqual(persistence.canonical_bytes(
                qualification.reconstruct_e1_resources(read_record)), persistence.canonical_bytes(original_resources))
            self.assertEqual(receipt.suite_content_sha256, persistence.content_digest(original_suite))
            self.assertEqual(receipt.resource_content_sha256, persistence.content_digest(original_resources))
            self.assertEqual({p.name for p in directory.iterdir()}, {"qualification.json", "COMPLETE.json"})

    def test_historical_readback_never_executes_or_reads_current_sources(self):
        record = self.record
        with tempfile.TemporaryDirectory() as root:
            receipt = persistence.persist_e1_qualification(record, repository_root=root)
            directory = Path(root) / "results" / "program_k_research" / record.run_id
            with ExitStack() as stack:
                calls = [stack.enter_context(patch.object(module, name, side_effect=AssertionError(name)))
                         for module, name in (
                    (qualification, "execute_e1"),
                    (qualification, "capture_qualification_source_identity"),
                    (operational, "supervise_scheduled_run"),
                    (operational, "supervise_posthoc_evaluator"),
                    (operational, "capture_operational_source_identity"),
                    (execution, "execute_scheduled_entry"),
                    (execution, "capture_execution_source_identity"),
                    (audit, "audit_scheduled_run"),
                    (audit, "capture_audit_source_identity"),
                    (suite, "capture_suite_source_identity"),
                    (e1, "capture_e1_source_identity"),
                    (e1, "capture_runtime_identity"),
                    (e1, "generate_board"),
                    (benchmark_board, "generate_board"),
                    (e1_evaluator, "evaluate_scheduled_kp0"),
                    (e1_evaluator, "_fixed_answer"),
                    (evaluator, "evaluate_falsification"),
                    (evaluator, "derive_terminal_answer"),
                    (core_engine.MinesweeperEngine, "__init__"),
                    (core_engine.MinesweeperEngine, "step"),
                )]
                restored, marker, assessment = persistence.read_e1_qualification_artifact(directory)
            self.assertEqual(restored, record)
            self.assertEqual(marker, receipt)
            self.assertEqual(assessment.verdict, "E1_PASS")
            for call in calls:
                call.assert_not_called()


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = _record(scheduled_results=(), evaluator_results=(),
                             interruptions=("Manual partial qualification fixture.",))

    def _publish(self, record=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        record = self.record if record is None else record
        receipt = persistence.persist_e1_qualification(record, repository_root=temporary.name)
        directory = Path(temporary.name) / "results" / "program_k_research" / record.run_id
        return Path(temporary.name), directory, receipt

    def _rewrite_receipt(self, directory, receipt, **changes):
        changed = _corrupt(receipt, **changes)
        (directory / "COMPLETE.json").write_bytes(persistence.canonical_bytes(changed))

    def test_partial_attempt_publishes_complete_marker_with_incomplete_verdict(self):
        _, directory, receipt = self._publish()
        self.assertEqual(receipt.completion_marker, "COMPLETE")
        self.assertEqual(receipt.verdict, "INCOMPLETE")
        self.assertFalse(receipt.progression_allowed)
        record, restored, assessment = persistence.read_e1_qualification_artifact(directory)
        self.assertEqual(record, self.record)
        self.assertEqual(restored, receipt)
        self.assertEqual(assessment.verdict, "INCOMPLETE")
        self.assertIsNone(receipt.suite_content_sha256)
        self.assertIsNone(receipt.resource_content_sha256)

    def test_implementation_failure_attempt_can_publish_complete(self):
        record = replace(self.record, diagnosed_implementation_defects=("Manual diagnosed source defect.",))
        _, directory, receipt = self._publish(record)
        self.assertEqual(receipt.verdict, "IMPLEMENTATION_IDENTITY_FAIL")
        self.assertEqual(receipt.completion_marker, "COMPLETE")
        self.assertEqual(persistence.read_e1_qualification_artifact(directory)[0], record)

    def test_qualification_is_completed_before_marker_exclusive_create(self):
        order = []
        original = persistence._write_exclusive

        def observed(path, data):
            order.append(path.name)
            if path.name == "COMPLETE.json":
                self.assertTrue((path.parent / "qualification.json").is_file())
                self.assertFalse(path.exists())
            original(path, data)

        with patch.object(persistence, "_write_exclusive", side_effect=observed):
            self._publish()
        self.assertEqual(order, ["qualification.json", "COMPLETE.json"])

    def test_destination_preexistence_is_rejected_without_overwrite(self):
        root, directory, _ = self._publish()
        before = {p.name: p.read_bytes() for p in directory.iterdir()}
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.persist_e1_qualification(self.record, repository_root=root)
        self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})

    def test_existing_empty_destination_is_also_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "results" / "program_k_research" / self.record.run_id
            directory.mkdir(parents=True)
            with self.assertRaises(persistence.E1PersistenceError):
                persistence.persist_e1_qualification(self.record, repository_root=root)
            self.assertEqual(list(directory.iterdir()), [])

    def test_archive_cap_checked_before_any_write(self):
        record = replace(self.record, operating_envelope=replace(
            self.record.operating_envelope, archive_cap_bytes=1))
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(persistence.E1PersistenceError):
                persistence.persist_e1_qualification(record, repository_root=root)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_path_traversal_and_unsafe_run_ids_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            for run_id in ("../e1-escape", "e1-../x", "e1-..\\x", "e1-a/b", "e1-a:b",
                           "e1-a.", "e1-a ", "E1-wrong", "e1-", "e1-" + "a" * 77):
                with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                    persistence.persist_e1_qualification(_corrupt(self.record, run_id=run_id),
                                                         repository_root=root)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_publication_rejects_live_source_drift(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(qualification, "capture_qualification_source_identity", return_value=None):
                with self.assertRaises(persistence.E1PersistenceError):
                    persistence.persist_e1_qualification(self.record, repository_root=root)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_interrupted_write_keeps_unaccepted_partial_directory(self):
        original = persistence._write_exclusive

        def interrupted(path, data):
            if path.name == "COMPLETE.json":
                raise OSError("Simulated publication interruption.")
            original(path, data)

        with tempfile.TemporaryDirectory() as root:
            with patch.object(persistence, "_write_exclusive", side_effect=interrupted):
                with self.assertRaises(OSError):
                    persistence.persist_e1_qualification(self.record, repository_root=root)
            directory = Path(root) / "results" / "program_k_research" / self.record.run_id
            before = (directory / "qualification.json").read_bytes()
            with self.assertRaises(persistence.E1PersistenceError):
                persistence.read_e1_qualification_artifact(directory)
            with self.assertRaises(persistence.E1PersistenceError):
                persistence.persist_e1_qualification(self.record, repository_root=root)
            self.assertEqual({p.name for p in directory.iterdir()}, {"qualification.json"})
            self.assertEqual((directory / "qualification.json").read_bytes(), before)

    def test_wrong_directory_name_rejected(self):
        _, directory, _ = self._publish()
        other = directory.with_name("e1-other")
        directory.rename(other)
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(other)

    def test_qualification_byte_flip_rejected(self):
        _, directory, _ = self._publish()
        path = directory / "qualification.json"
        raw = bytearray(path.read_bytes())
        raw[len(raw) // 2] ^= 1
        path.write_bytes(raw)
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)

    def test_complete_byte_flip_rejected(self):
        _, directory, _ = self._publish()
        path = directory / "COMPLETE.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)

    def test_wrong_size_rejected(self):
        _, directory, receipt = self._publish()
        self._rewrite_receipt(directory, receipt, size_bytes=receipt.size_bytes + 1)
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)

    def test_wrong_content_digest_rejected(self):
        _, directory, receipt = self._publish()
        self._rewrite_receipt(directory, receipt, content_sha256="0" * 64)
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)

    def test_wrong_qualification_source_digest_rejected(self):
        self._assert_receipt_digest_rejected("qualification_source_digest")

    def test_wrong_operational_source_digest_rejected(self):
        self._assert_receipt_digest_rejected("operational_source_digest")

    def test_wrong_plan_source_digest_rejected(self):
        self._assert_receipt_digest_rejected("plan_source_digest")

    def test_wrong_envelope_digest_rejected(self):
        self._assert_receipt_digest_rejected("envelope_digest")

    def test_wrong_protocol_digest_rejected(self):
        self._assert_receipt_digest_rejected("protocol_sha256")

    def test_wrong_assessment_digest_rejected(self):
        self._assert_receipt_digest_rejected("assessment_content_sha256")

    def test_wrong_suite_reconstruction_digest_rejected(self):
        self._assert_receipt_digest_rejected("suite_content_sha256")

    def test_wrong_resource_reconstruction_digest_rejected(self):
        self._assert_receipt_digest_rejected("resource_content_sha256")

    def _assert_receipt_digest_rejected(self, field):
        _, directory, receipt = self._publish()
        self._rewrite_receipt(directory, receipt, **{field: "0" * 64})
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)

    def test_wrong_verdict_rejected(self):
        _, directory, receipt = self._publish()
        self._rewrite_receipt(directory, receipt, verdict="E1_PASS",
                              readiness="E1_QUALIFIED", progression_allowed=True)
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)

    def test_wrong_readiness_rejected(self):
        _, directory, receipt = self._publish()
        self._rewrite_receipt(directory, receipt, readiness="E1_A_E5_REQUIRED")
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)

    def test_wrong_progression_rejected(self):
        _, directory, receipt = self._publish()
        self._rewrite_receipt(directory, receipt, progression_allowed=True)
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)

    def test_wrong_exact_top_level_types_rejected(self):
        _, directory, receipt = self._publish()
        marker = directory / "COMPLETE.json"
        marker.write_bytes(persistence.canonical_bytes(("COMPLETE",)))
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)
        wrong = persistence.canonical_bytes(("qualification",))
        (directory / "qualification.json").write_bytes(wrong)
        self._rewrite_receipt(directory, receipt, size_bytes=len(wrong),
                              content_sha256=hashlib.sha256(wrong).hexdigest())
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)

    def test_extra_artifact_file_is_not_silently_accepted(self):
        _, directory, _ = self._publish()
        (directory / "unexpected.json").write_bytes(b"[]")
        with self.assertRaises(persistence.E1PersistenceError):
            persistence.read_e1_qualification_artifact(directory)


if __name__ == "__main__":
    unittest.main()
