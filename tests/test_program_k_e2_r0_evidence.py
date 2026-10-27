"""Slice 1B identity/metadata contracts on supplied, in-memory facts only."""

import ast
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, dataclass, fields, replace
from enum import Enum
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from experiments import program_k_e2_r0_evidence as e
from experiments import program_k_e2_r0_harness as h
from experiments import program_k_e2_execution as execution
from experiments import program_k_e2_operational as operational
from experiments import program_k_e2_physical as physical
from experiments import program_k_e2_readiness as readiness
from experiments import program_k_e2_records as records


PROFILE = "a3" * 32
V1_SCHEMAS = ("program-k-e2-r0a-observations/v1", "program-k-e2-r0-run/v1",
              "program-k-e2-r0b-experiment/v1")
V2_SCHEMAS = ("program-k-e2-r0a-observations/v2", "program-k-e2-r0-run/v2",
              "program-k-e2-r0b-experiment/v2")
BASIS_FIELDS = {
    "logical_record_codec": "program-k-e2-records/v1",
    "logical_counting": "sum-exact-REC.encode-record-bytes",
    "durable_counting": "sum-complete-attributable-PKE2RF02-frames",
    "record_frame_format": "PKE2RF02",
    "worker_container_format": "PKE2WB02",
    "qualification_policy": "dual-independent-ceil-3-over-2/v1",
    "codec_profile_sha256": PROFILE,
}


def _local_types():
    return (h.RunProvenance, h.FileFact, h.ArchiveAccounting, h.FinalizationFact)


# Frozen explicit vocabulary from the accepted pre-Slice-1B harness. This
# independent test oracle never calls either new implementation or wrapper.
_HISTORICAL_FACT_TYPES = _local_types() + (
    operational.OperatingEnvelope, operational.R0Work, operational.R0UnitMeasurement,
    operational.R0ComponentMeasurement, operational.R0SetupMeasurement,
    operational._R0Observation, operational.UnitReceipt, operational.CoordinatorResult,
    readiness.AmendmentProvenance, readiness.SubsetCounts, readiness.SyntheticCorpusSelection,
    readiness.SyntheticWorkload, readiness.R0APlan, readiness.ComponentMeasurement,
    readiness.OracleMeasurement, readiness.WallRouteMeasurement, readiness.ReferenceMeasurement,
    readiness.RouteContainment, readiness.R0AConcurrencyMeasurement, readiness.ComponentSizes,
    readiness.SupportingStreams, readiness.PhaseMeasurement, readiness.R0BMeasurement,
)
_HISTORICAL_ENUMS = (operational.R0Component, execution.WorkerKind, records.AuditStatus,
                     records.Phase, readiness.WallAccounting, readiness.ByteAccounting)
_HISTORICAL_RECORDS = (records.BoardIdentity, records.RuntimeIdentity,
                       records.SourceBlobIdentity, records.StreamDigest)


def _historical_node(value):
    """Valid-input encoding semantics copied from baseline 223442f, not dispatch."""
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is bytes:
        return {"bytes": value.hex()}
    if type(value) is Fraction:
        return {"fraction": [value.numerator, value.denominator]}
    if type(value) is tuple:
        return [_historical_node(item) for item in value]
    if type(value) is records.StreamDigest:
        records.StreamDigest.__post_init__(value)
        return {"stream": [value.name, value.sha256, value.byte_length, value.record_count]}
    if type(value) in _HISTORICAL_RECORDS:
        return {"record": records.encode(value).decode("ascii")}
    if type(value) in _HISTORICAL_ENUMS:
        return {"enum": type(value).__name__, "value": value.value}
    if type(value) not in _HISTORICAL_FACT_TYPES:
        raise AssertionError("The historical test oracle has a closed vocabulary")
    if hasattr(type(value), "__post_init__"):
        type(value).__post_init__(value)
    return {"fact": type(value).__name__, "fields": {
        item.name: _historical_node(getattr(value, item.name)) for item in fields(value)}}


def _encode(value):
    return e.fact_node_v1(value, local_fact_types=_local_types())


def _decode(node):
    return e.fact_read_v1(node, local_fact_types=_local_types())


def _json(node):
    return json.dumps(node, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _facts():
    """Small literal identity/fact values, with no selector, runner or capture."""
    board = records.BoardIdentity(42_424_242, "invented-fingerprint", 2, 1, 0,
                                  (0, 0), "supplied-generator", "supplied-spec")
    runtime = records.RuntimeIdentity("SuppliedPython", "0.0", "supplied-os",
                                      "supplied-platform", "supplied-arch", None)
    source = records.SourceBlobIdentity("experiments/program_k_e2_r0_harness.py",
                                        "b" * 40, "c" * 64, 3)
    stream = records.StreamDigest("operations", "d" * 64, 17, 1)
    provenance = h.RunProvenance(h.SELECTION_SOURCE_HEAD, "e" * 40, (source,),
        ((source.path, "f" * 64, 3, False),), runtime, "supplied-python", True)
    file = h.FileFact("attributable", 2, "a" * 64)
    support = h.FileFact("support", 1, "b" * 64)
    accounting = h.ArchiveAccounting((file, support), 2, 1, 3)
    finalization = h.FinalizationFact((("writes", 4, 4), ("manifest_inventory", 2, 2),
        ("accounting_inventory", 3, 3), ("source_recheck", 1, 1), ("cleanup", 1, 1)),
        10, 2, 10, True)
    envelope = operational.OperatingEnvelope(1, 1, 2, 3, 4, 5, 1, 10,
        64, 64, 128, 2048, 1, 1024, 128, 1, 1, 1, 1, 1)
    work = operational.R0Work(0, board, b"\x12" * 32, "R0-SUPPLIED", runtime)
    receipt = operational.UnitReceipt(0, execution.WorkerKind.PRIMARY,
        records.AuditStatus.FAIL, "SYNTHETIC_FAILURE", 3, 1)
    observation = operational._R0Observation(1, 2, 3, 1, 2, 0, 1,
                                             (0, 0, 0, ()), True, False, True)
    unit = operational.R0UnitMeasurement(work, operational.R0Component.PRIMARY,
        records.AuditStatus.FAIL, ("SYNTHETIC_FAILURE",), 3, 2, 0, 0, 3,
        (observation,), 0, 1, 10)
    component = operational.R0ComponentMeasurement(operational.R0Component.PRIMARY,
        1, (unit,), 3, 2, 4, 3)
    setup = operational.R0SetupMeasurement("K", 1, 3, (receipt,), (None,),
                                            (0,), 2, 3, 1, False)
    coordinator = operational.CoordinatorResult((receipt,), (stream,), 0, 0, 17,
                                                records.AuditStatus.FAIL, ("SYNTHETIC_FAILURE",))
    containment = readiness.RouteContainment("P", 1, 2, 3, 1, 2, 3, 0, 1, 10, 4,
                                             True, False, True, False, False)
    supporting = readiness.SupportingStreams(tuple(records.StreamDigest(name, "d" * 64, 1, 1)
        for name in ("operations", "resources", "qualification_identity")),
        True, True, True, True, True, True)
    return (
        board, runtime, source, stream,
        provenance, file, accounting, finalization,
        envelope, work, receipt, observation, unit, component, setup, coordinator,
        readiness.AmendmentProvenance(), readiness.SubsetCounts(1, 1, 1, 1, b"\x22" * 32),
        readiness.ComponentMeasurement(3, 2, 1, 1), readiness.OracleMeasurement(1, 0, 0, 0),
        readiness.WallRouteMeasurement(1, 0), readiness.ReferenceMeasurement("K", 2, 1, 1),
        containment, readiness.ComponentSizes(1, 2, 0, 0, 3, 4), supporting,
        readiness.PhaseMeasurement(records.Phase.VALIDATION, 1, 0, 1, 0, False, False),
    )


class SizeBasisTests(unittest.TestCase):
    def test_exact_fields_values_and_canonical_bytes(self):
        basis = e.SizeBasisV2(PROFILE)
        self.assertEqual({item.name for item in fields(basis)}, set(BASIS_FIELDS))
        self.assertEqual({item.name: getattr(basis, item.name) for item in fields(basis)}, BASIS_FIELDS)
        self.assertEqual(e.encode_size_basis(basis), _json(BASIS_FIELDS))
        self.assertEqual(e.decode_size_basis(_json(BASIS_FIELDS)), basis)
        self.assertTrue(e.encode_size_basis(basis).isascii())

    def test_immutable_deterministic_and_explicit_profile_identity(self):
        first = e.SizeBasisV2(PROFILE)
        second = e.SizeBasisV2(PROFILE)
        self.assertEqual(first, second)
        self.assertEqual(e.encode_size_basis(first), e.encode_size_basis(second))
        self.assertFalse(hasattr(first, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            first.codec_profile_sha256 = "b" * 64
        other = e.SizeBasisV2("b" * 64)
        self.assertNotEqual(e.encode_size_basis(first), e.encode_size_basis(other))

    def test_each_fixed_identity_rejects_alternatives_in_constructor_and_decoder(self):
        changes = {"logical_record_codec": "program-k-e2-records/v2",
            "logical_counting": "sum-jsonl-bytes", "durable_counting": "sum-logical-bytes",
            "record_frame_format": "PKE2RF01", "worker_container_format": "PKE2WB01",
            "qualification_policy": "single-floor/v1"}
        for field, value in changes.items():
            with self.subTest(field=field):
                with self.assertRaises(e.EvidenceError):
                    e.SizeBasisV2(PROFILE, **{field: value})
                node = dict(BASIS_FIELDS, **{field: value})
                with self.assertRaises(e.EvidenceError):
                    e.decode_size_basis(_json(node))

    def test_profile_rejects_malformed_noncanonical_or_coerced_identity(self):
        class Text(str):
            pass
        for profile in (None, True, False, 0, 1.0, "", "a" * 63, "a" * 65,
                        "A3" * 32, "g" * 64, PROFILE + "\n", bytes.fromhex(PROFILE),
                        bytearray.fromhex(PROFILE), Text(PROFILE)):
            with self.subTest(profile=profile), self.assertRaises(e.EvidenceError):
                e.SizeBasisV2(profile)

    def test_exact_field_sets_no_missing_extra_or_mutable_input(self):
        for field in BASIS_FIELDS:
            node = dict(BASIS_FIELDS)
            del node[field]
            with self.subTest(missing=field), self.assertRaises(e.EvidenceError):
                e.decode_size_basis(_json(node))
        for node in (dict(BASIS_FIELDS, extra="value"), {}, [], None):
            with self.assertRaises(e.EvidenceError):
                e.decode_size_basis(_json(node))
        for data in (bytearray(_json(BASIS_FIELDS)), memoryview(_json(BASIS_FIELDS)),
                     _json(BASIS_FIELDS).decode("ascii")):
            with self.assertRaises(e.EvidenceError):
                e.decode_size_basis(data)

    def test_duplicate_noncanonical_float_nan_and_bool_wire_rejected(self):
        raw = _json(BASIS_FIELDS)
        malformed = [raw + b"\n", json.dumps(BASIS_FIELDS).encode("ascii"),
                     b'{"codec_profile_sha256":"' + PROFILE.encode("ascii") + b'",' + raw[1:]]
        for value in (b"true", b"1", b"1.0", b"NaN", b"Infinity", b"-Infinity"):
            malformed.append(raw.replace(b'"' + PROFILE.encode("ascii") + b'"', value))
        for data in malformed:
            with self.subTest(data=data[:60]), self.assertRaises(e.EvidenceError):
                e.decode_size_basis(data)
        for field in BASIS_FIELDS:
            with self.subTest(field=field), self.assertRaises(e.EvidenceError):
                e.decode_size_basis(_json(dict(BASIS_FIELDS, **{field: True})))

    def test_encoder_revalidates_corrupted_basis_and_rejects_subclasses(self):
        basis = e.SizeBasisV2(PROFILE)
        object.__setattr__(basis, "worker_container_format", "PKE2WB01")
        with self.assertRaises(e.EvidenceError):
            e.encode_size_basis(basis)
        class Subclass(e.SizeBasisV2):
            pass
        with self.assertRaises(e.EvidenceError):
            e.encode_size_basis(Subclass(PROFILE))


class SchemaIsolationTests(unittest.TestCase):
    def test_exact_schema_constants_and_version_classification(self):
        self.assertEqual((e.R0A_OBSERVATIONS_V1, e.R0_RUN_V1, e.R0B_EXPERIMENT_V1), V1_SCHEMAS)
        self.assertEqual((e.R0A_OBSERVATIONS_V2, e.R0_RUN_V2, e.R0B_EXPERIMENT_V2), V2_SCHEMAS)
        for schema in V1_SCHEMAS:
            self.assertEqual(e.schema_version(schema), 1)
            self.assertIs(type(e.schema_version(schema)), int)
        for schema in V2_SCHEMAS:
            self.assertEqual(e.schema_version(schema), 2)

    def test_unknown_missing_and_content_sniffing_do_not_dispatch(self):
        class Text(str):
            pass
        for schema in (None, "", "program-k-e2-r0a-observations/v3", "other/v1",
                       "PKE2RF02", "PKE2WB02", "evidence.json", V1_SCHEMAS[0].encode("ascii"),
                       {"schema": V1_SCHEMAS[0]}, Text(V1_SCHEMAS[0]), True, 1, 1.0):
            with self.subTest(schema=schema), self.assertRaises(e.EvidenceError):
                e.schema_version(schema)
            with self.assertRaises(e.EvidenceError):
                e.validate_metadata_identity(schema)
        with self.assertRaises(TypeError):
            e.schema_version()

    def test_v1_remains_profile_free_and_rejects_v2_basis(self):
        for schema in V1_SCHEMAS:
            self.assertEqual(e.validate_metadata_identity(schema), 1)
            with self.assertRaises(e.EvidenceError):
                e.validate_metadata_identity(schema, size_basis=e.SizeBasisV2(PROFILE))
            for expected in (PROFILE, "b" * 64, True):
                with self.assertRaises(e.EvidenceError):
                    e.validate_metadata_identity(schema, expected_profile_sha256=expected)
        # Historical V1 fact read is independent of all profile capture/qualification.
        with patch.object(physical, "capture_profile", side_effect=AssertionError("No capture")), \
                patch.object(physical, "require_qualified_profile", side_effect=AssertionError("No qualification")):
            self.assertEqual(e.fact_read_v1({"bytes": "00ff"}), b"\x00\xff")

    def test_v2_requires_exact_basis_and_explicit_profile_match(self):
        basis = e.SizeBasisV2(PROFILE)
        for schema in V2_SCHEMAS:
            self.assertEqual(e.validate_metadata_identity(schema, size_basis=basis), 2)
            self.assertEqual(e.validate_metadata_identity(schema, size_basis=basis,
                                                         expected_profile_sha256=PROFILE), 2)
            for missing in (None, BASIS_FIELDS, _json(BASIS_FIELDS), "PKE2RF02", True):
                with self.assertRaises(e.EvidenceError):
                    e.validate_metadata_identity(schema, size_basis=missing)
            for expected in ("b" * 64, "A3" * 32, b"x" * 32, True, 1.0):
                with self.assertRaises(e.EvidenceError):
                    e.validate_metadata_identity(schema, size_basis=basis, expected_profile_sha256=expected)

    def test_v2_identity_never_becomes_a_v1_fact_or_qualification_receipt(self):
        basis = e.SizeBasisV2(PROFILE)
        with self.assertRaises(e.EvidenceError):
            _encode(basis)
        with self.assertRaises(e.EvidenceError):
            _decode({"fact": "SizeBasisV2", "fields": BASIS_FIELDS})
        self.assertFalse(hasattr(basis, "qualified"))
        with self.assertRaises(TypeError):
            e.validate_metadata_identity(V2_SCHEMAS[0], size_basis=basis, qualified=True)


class HistoricalV1CodecTests(unittest.TestCase):
    def assertExactValue(self, actual, expected):
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)
        if type(expected) is tuple:
            for a, b in zip(actual, expected):
                self.assertExactValue(a, b)
        elif type(expected) in _HISTORICAL_FACT_TYPES:
            for item in fields(expected):
                self.assertExactValue(getattr(actual, item.name), getattr(expected, item.name))

    def checkHistorical(self, value):
        node = _historical_node(value)
        self.assertEqual(_encode(value), node)
        self.assertEqual(h._fact_node(value), node)
        self.assertExactValue(_decode(node), value)
        self.assertExactValue(h._fact_read(node), value)
        self.assertEqual(_encode(_decode(node)), node)
        self.assertEqual(_json(_encode(value)), _json(node))

    def test_literal_scalar_byte_fraction_tuple_and_stream_nodes(self):
        cases = ((None, None), (False, False), (True, True), (0, 0), (-1, -1),
                 (1 << 300, 1 << 300), (-(1 << 300), -(1 << 300)),
                 ("quote\"slash\\한글", "quote\"slash\\한글"),
                 (b"", {"bytes": ""}), (b"\x00\xff", {"bytes": "00ff"}),
                 (Fraction(-7, 3), {"fraction": [-7, 3]}),
                 (Fraction(0), {"fraction": [0, 1]}),
                 ((None, (True, 5)), [None, [True, 5]]),
                 (records.StreamDigest("operations", "d" * 64, 17, 1),
                  {"stream": ["operations", "d" * 64, 17, 1]}))
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(_encode(value), expected)
                self.checkHistorical(value)

    def test_all_local_and_representative_operational_readiness_fact_nodes_match_baseline(self):
        values = _facts()
        self.assertTrue(set(_local_types()) <= {type(value) for value in values})
        self.assertTrue(set(_HISTORICAL_FACT_TYPES[4:12]) <= {type(value) for value in values})
        for value in values:
            with self.subTest(kind=type(value).__name__):
                self.checkHistorical(value)
        self.assertEqual(_encode(h.FileFact("attributable", 2, "a" * 64)),
                         {"fact": "FileFact", "fields": {
                             "path": "attributable", "byte_length": 2, "sha256": "a" * 64}})

    def test_all_closed_enum_families_and_every_member_roundtrip(self):
        self.assertEqual(len(_HISTORICAL_ENUMS), 6)
        for enum in _HISTORICAL_ENUMS:
            for value in enum:
                with self.subTest(enum=enum.__name__, value=value.value):
                    self.assertEqual(_encode(value), {"enum": enum.__name__, "value": value.value})
                    self.checkHistorical(value)

    def test_nested_tuple_reconstruction_and_valid_failure_evidence_preserved(self):
        facts = _facts()
        receipt = next(value for value in facts if type(value) is operational.UnitReceipt)
        self.assertIs(receipt.status, records.AuditStatus.FAIL)
        incomplete = replace(receipt, status=records.AuditStatus.INCOMPLETE,
                             reason="SYNTHETIC_INCOMPLETE", exit_code=None)
        final = next(value for value in facts if type(value) is h.FinalizationFact)
        unfinished = replace(final, complete=False, progress_events=0)
        self.checkHistorical((facts, (incomplete, unfinished, Fraction(7, 3), b"\0")))

    def test_exact_preexisting_closed_type_registry(self):
        self.assertEqual(len(_HISTORICAL_FACT_TYPES), 27)
        self.assertEqual(set(e._FACT_TYPES) | {cls.__name__ for cls in _local_types()},
                         {cls.__name__ for cls in _HISTORICAL_FACT_TYPES})
        self.assertEqual(set(e._FACT_ENUMS), {cls.__name__ for cls in _HISTORICAL_ENUMS})
        self.assertEqual(set(e._FACT_RECORDS), set(_HISTORICAL_RECORDS))

    def test_local_mapping_is_explicit_closed_and_not_mutable_registration(self):
        file = h.FileFact("fixture", 1, "a" * 64)
        with self.assertRaises(e.EvidenceError):
            e.fact_node_v1(file)
        with self.assertRaises(e.EvidenceError):
            e.fact_read_v1(_historical_node(file))
        @dataclass(frozen=True, slots=True)
        class Arbitrary:
            value: int
        for mapping in (list(_local_types()), dict(zip((c.__name__ for c in _local_types()), _local_types())),
                        _local_types()[:-1], _local_types()[::-1], _local_types() + (Arbitrary,),
                        (Arbitrary,) + _local_types()[1:]):
            with self.subTest(mapping=mapping), self.assertRaises(e.EvidenceError):
                e.fact_node_v1(file, local_fact_types=mapping)
        # Passing local classes to one call does not globally register them.
        self.assertEqual(e.fact_read_v1(e.fact_node_v1(7)), 7)
        with self.assertRaises(e.EvidenceError):
            e.fact_node_v1(file)

    def test_extra_missing_and_wrong_fact_fields_fail_closed(self):
        for value in _facts():
            if type(value) not in _HISTORICAL_FACT_TYPES:
                continue
            node = _historical_node(value)
            for key in node["fields"]:
                malformed = {"fact": node["fact"], "fields": dict(node["fields"])}
                del malformed["fields"][key]
                with self.subTest(fact=node["fact"], missing=key), self.assertRaises(ValueError):
                    _decode(malformed)
            malformed = {"fact": node["fact"], "fields": dict(node["fields"], arbitrary=0)}
            with self.assertRaises(ValueError):
                _decode(malformed)
            for malformed in (dict(node, arbitrary=0), {"fact": node["fact"]}, {"fields": node["fields"]},
                              dict(node, fact="wrong_" + node["fact"]), dict(node, fields=[])):
                with self.assertRaises(ValueError):
                    _decode(malformed)

    def test_all_tag_shapes_reject_extra_or_missing_keys(self):
        for node in ({"bytes": "00"}, {"fraction": [1, 2]},
                     {"stream": ["operations", "a" * 64, 1, 1]},
                     {"record": records.encode(_facts()[0]).decode("ascii")},
                     {"enum": "AuditStatus", "value": "PASS"}):
            with self.assertRaises(ValueError):
                _decode(dict(node, extra=0))
            for key in node:
                malformed = dict(node)
                del malformed[key]
                with self.assertRaises(ValueError):
                    _decode(malformed)

    def test_noncanonical_fraction_and_hex_rejected(self):
        for fraction in ([2, 4], [0, 2], [1, -2], [1, 0], [True, 1], [1, False],
                         [1.0, 2], [1, 2.0], [1], [1, 2, 3], ["1", 2], None):
            with self.subTest(fraction=fraction), self.assertRaises((ValueError, TypeError)):
                _decode({"fraction": fraction})
        for hex_text in ("AB", "00 FF", "0", "gg", " 00", "00\n", True, 1, b"00"):
            with self.subTest(hex_text=hex_text), self.assertRaises(ValueError):
                _decode({"bytes": hex_text})

    def test_floats_nonfinite_and_scalar_coercion_never_enter_v1(self):
        class Integer(int):
            pass
        class Text(str):
            pass
        for value in (0.0, 1.5, float("nan"), float("inf"), -float("inf"),
                      Integer(1), Text("x"), bytearray(b"x"), [1, 2], {"x": 1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _encode(value)
        for value in (0.0, float("nan"), float("inf"), -float("inf"), Integer(1), Text("x")):
            with self.assertRaises(ValueError):
                _decode(value)
            with self.assertRaises(ValueError):
                _decode([value])

    def test_unsupported_embedded_records_and_noncanonical_record_bytes_rejected(self):
        event = records.OperationEventRecord(records.Phase.VALIDATION, "supplied",
            records.EventKind.START, 0, 0, records.OperationStatus.RUNNING)
        with self.assertRaises(ValueError):
            _encode(event)
        with self.assertRaises(ValueError):
            _decode({"record": records.encode(event).decode("ascii")})
        board = _facts()[0]
        for text in (records.encode(board).decode("ascii") + "\n", "{}", "not-json"):
            with self.assertRaises(ValueError):
                _decode({"record": text})

    def test_arbitrary_dataclass_enum_and_class_name_injection_rejected(self):
        @dataclass(frozen=True)
        class Unknown:
            value: int
        class UnknownEnum(Enum):
            PASS = "PASS"
        class FakeFile(h.FileFact):
            pass
        for value in (Unknown(1), UnknownEnum.PASS, FakeFile("x", 1, "a" * 64), Path("x"),
                      h.ActualRunAuthorization.R0_A):
            with self.assertRaises(ValueError):
                _encode(value)
        for name in ("__import__", "builtins.eval", "os.system", "pathlib.Path", "SizeBasisV2"):
            with self.assertRaises(ValueError):
                _decode({"fact": name, "fields": {"value": "never-run"}})
            with self.assertRaises(ValueError):
                _decode({"enum": name, "value": "PASS"})
        for enum in _HISTORICAL_ENUMS:
            with self.assertRaises(ValueError):
                _decode({"enum": enum.__name__, "value": "UNDECLARED_VALUE"})

    def test_constructor_validation_is_preserved_for_known_fact_types(self):
        for value, field, invalid in ((h.FileFact("x", 1, "a" * 64), "byte_length", True),
                (readiness.ComponentSizes(1, 2, 0, 0, 3, 4), "primary", 0),
                (operational.UnitReceipt(0, execution.WorkerKind.PRIMARY, records.AuditStatus.FAIL,
                    "SYNTHETIC_FAILURE", 1, 1), "reason", "untrusted arbitrary detail")):
            node = _historical_node(value)
            node["fields"][field] = invalid
            with self.assertRaises(ValueError):
                _decode(node)
            object.__setattr__(value, field, invalid)
            with self.assertRaises(ValueError):
                _encode(value)


class V2MaterializationEvidenceTests(unittest.TestCase):
    """Pure metadata fixtures: no constructor, persistence or runtime capture."""

    @classmethod
    def setUpClass(cls):
        from tests.test_program_k_e2_physical import _qualified_node
        cls.profile = physical.decode_profile(_json(_qualified_node()))
        cls.runtime = records.RuntimeIdentity("FixturePython", "0", "fixture-os", "fixture-platform",
                                              "fixture-arch", None)
        cls.plan = (execution.BoardWork(0, h.synthetic_board_identity(2_000_000_090_000),
            b"\x12" * 32, "slice1n-evidence-fixture", False, False, False, cls.runtime),)
        trial = e.V2ConstructorTrialEvidence(1, 0, 100, 200, 0, 0, True, None)
        cls.fact = e.V2ConstructorEvidence(0, "primary", "text", 100, 200, 0, 1,
            100, 200, 0, 0, 0, 0, True, 4196, False, (trial,))
        cls.value = e.V2MaterializationEvidence(
            schema=e.R0B_EXPERIMENT_V2, size_basis=e.SizeBasisV2(cls.profile.sha256.hex()),
            codec_profile_bytes=cls.profile.canonical_bytes, codec_profile_sha256=cls.profile.sha256.hex(),
            source_plan_identity=e.plan_identity_v2(cls.plan),
            materialization_plan_identity=e.plan_identity_v2(cls.plan),
            mapping_policy=e.V2_MATERIALIZATION_MAPPING_POLICY, protocol_seed=cls.plan[0].protocol_seed,
            run_id=cls.plan[0].run_id, runtime=cls.runtime, work_count=1,
            family_counts=tuple(zip(readiness.V2_FAMILIES, (1, 0, 0, 0, 0, 0))),
            targets=readiness.DualComponentSizes(readiness.ComponentSizes(100, 1, 0, 0, 1, 1),
                                                 readiness.ComponentSizes(200, 1, 0, 0, 1, 1)),
            streams=tuple(records.StreamDigest(name, "a" * 64, 0, 0)
                          for name in execution.STREAM_NAMES + ("operations", "resources")),
            constructor_facts=(cls.fact,),
            family_totals=tuple(e.V2FamilyTotalEvidence(name, 100 if name == "primary" else 0,
                200 if name == "primary" else 0, 0) for name in readiness.V2_FAMILIES),
            physical_minimum_total=100, fixed_allowance_reservation=268435456, b_proc=1000,
            committed_procedural_excess=0, remaining_procedural_budget=1000, durable_operation_count=1,
            durable_primary_count=1, attributable_experiment_bytes=100, current_sealed_pkf_bytes=100,
            runtime_monitor_peak_coordinator_private_bytes=300,
            progress_complete=True, cleanup_complete=True, synthetic_non_evidence=True)
        cls.raw = e.encode_materialization_v2(cls.value)

    def node(self):
        return json.loads(self.raw)

    def decode_node(self, node):
        return e.decode_materialization_v2(_json(node) + b"\n")

    def test_canonical_ascii_final_lf_exact_roundtrip_and_profile_bytes(self):
        self.assertTrue(self.raw.isascii())
        self.assertTrue(self.raw.endswith(b"\n") and not self.raw.endswith(b"\n\n"))
        self.assertEqual(self.raw, _json(self.node()) + b"\n")
        value = e.decode_materialization_v2(self.raw, expected_profile_sha256=self.profile.sha256.hex())
        self.assertEqual(value, self.value)
        self.assertEqual(e.encode_materialization_v2(value), self.raw)
        self.assertEqual(value.codec_profile_bytes, self.profile.canonical_bytes)
        self.assertEqual(physical.decode_profile(value.codec_profile_bytes).sha256.hex(), value.codec_profile_sha256)
        self.assertNotIn("readback_complete", self.node())
        self.assertNotIn("durable_sample_max_coordinator_private_bytes", self.node())
        self.assertEqual(self.node()["runtime_monitor_peak_coordinator_private_bytes"], 300)

    def test_v2_metadata_types_are_frozen_closed_and_excluded_from_v1(self):
        for value in (self.value, self.fact, self.fact.trials[0], self.value.family_totals[0]):
            self.assertFalse(hasattr(value, "__dict__"))
            self.assertNotIn(type(value), e._FACT_TYPES.values())
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)
            with self.assertRaises(e.EvidenceError):
                e.fact_node_v1(value)
            with self.assertRaises(e.EvidenceError):
                e.fact_read_v1({"fact": type(value).__name__, "fields": {}})
        class Derived(e.V2MaterializationEvidence):
            pass
        values = {field.name: getattr(self.value, field.name) for field in fields(self.value)}
        with self.assertRaises(e.EvidenceError):
            e.encode_materialization_v2(Derived(**values))

    def test_every_closed_nested_shape_rejects_unknown_and_missing_fields(self):
        paths = ((), ("size_basis",), ("targets",), ("targets", "physical"),
                 ("streams", 0), ("constructor_facts", 0), ("constructor_facts", 0, "trials", 0),
                 ("family_totals", 0))
        for path in paths:
            node = self.node()
            shape = node
            for key in path:
                shape = shape[key]
            for field in tuple(shape):
                candidate = self.node()
                changed = candidate
                for key in path:
                    changed = changed[key]
                del changed[field]
                with self.subTest(path=path, missing=field), self.assertRaises(e.EvidenceError):
                    self.decode_node(candidate)
            shape["unexpected"] = None
            with self.subTest(path=path, extra=True), self.assertRaises(e.EvidenceError):
                self.decode_node(node)

    def test_duplicate_fields_noncanonical_spacing_lf_and_non_ascii_wire_fail(self):
        duplicate = b'{"schema":"' + e.R0B_EXPERIMENT_V2.encode("ascii") + b'",' + self.raw[1:]
        nested = self.raw.replace(b'"ordinal":1', b'"ordinal":1,"ordinal":1', 1)
        for raw in (self.raw[:-1], self.raw + b"\n", self.raw + b" ", b" " + self.raw,
                    self.raw.replace(b'"work_count":1', b'"work_count": 1'), duplicate, nested,
                    self.raw.replace(b'"run_id":', b'"r\xffn_id":')):
            with self.subTest(raw=raw[:40]), self.assertRaises(e.EvidenceError):
                e.decode_materialization_v2(raw)
        for value in (bytearray(self.raw), memoryview(self.raw), self.raw.decode("ascii"), None):
            with self.assertRaises(e.EvidenceError):
                e.decode_materialization_v2(value)

    def test_float_nan_bool_as_int_and_scalar_coercion_fail_at_every_depth(self):
        paths = (("work_count",), ("family_counts", 0, 1), ("targets", "physical", "primary"),
                 ("streams", 0, "byte_length"), ("constructor_facts", 0, "position"),
                 ("constructor_facts", 0, "trials", 0, "knob"), ("family_totals", 0, "physical_bytes"),
                 ("runtime_monitor_peak_coordinator_private_bytes",))
        for path in paths:
            for bad in (True, False, 1.0, "1", None):
                node = self.node()
                parent = node
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = bad
                with self.subTest(path=path, bad=bad), self.assertRaises(e.EvidenceError):
                    self.decode_node(node)
        for token in (b"NaN", b"Infinity", b"-Infinity", b"1e0"):
            with self.assertRaises(e.EvidenceError):
                e.decode_materialization_v2(self.raw.replace(b'"work_count":1', b'"work_count":' + token))
        for field in ("progress_complete", "cleanup_complete", "synthetic_non_evidence"):
            for bad in (1, "true", False):
                node = self.node()
                node[field] = bad
                with self.subTest(field=field, bad=bad), self.assertRaises(e.EvidenceError):
                    self.decode_node(node)

    def test_explicit_schema_basis_profile_bytes_and_expected_profile_are_all_bound(self):
        for schema in (e.R0B_EXPERIMENT_V1, e.R0_RUN_V2, e.R0A_OBSERVATIONS_V2, "unknown", True):
            node = self.node()
            node["schema"] = schema
            with self.assertRaises(e.EvidenceError):
                self.decode_node(node)
        for field, invalid in (("size_basis", None), ("codec_profile_bytes", "7b7d"),
                               ("codec_profile_sha256", "b" * 64), ("mapping_policy", "unapproved")):
            node = self.node()
            node[field] = invalid
            with self.assertRaises(e.EvidenceError):
                self.decode_node(node)
        node = self.node()
        node["size_basis"]["codec_profile_sha256"] = "c" * 64
        with self.assertRaises(e.EvidenceError):
            self.decode_node(node)
        profile_node = json.loads(self.profile.canonical_bytes)
        profile_node["status"] = "UNQUALIFIED_SLICE_1A"
        raw = _json(profile_node)
        import hashlib
        node = self.node()
        node["codec_profile_bytes"] = raw.hex()
        node["codec_profile_sha256"] = node["size_basis"]["codec_profile_sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(e.EvidenceError):
            self.decode_node(node)
        for expected in ("0" * 64, self.profile.sha256, True, "A" * 64):
            with self.assertRaises(e.EvidenceError):
                e.decode_materialization_v2(self.raw, expected_profile_sha256=expected)

    def test_canonical_hex_runtime_and_digest_fields_have_no_permissive_coercion(self):
        for field in ("protocol_seed", "codec_profile_bytes"):
            for mutation in (lambda value: value.upper(), lambda value: value + " ", lambda value: "g0",
                             lambda value: "0", lambda value: True):
                node = self.node()
                # The seed fixture is numeric hex, so introduce a noncanonical
                # letter explicitly for its uppercase case.
                node[field] = mutation(node[field] if field != "protocol_seed" else "ab" * 32)
                with self.subTest(field=field), self.assertRaises(e.EvidenceError):
                    self.decode_node(node)
        for field in ("source_plan_identity", "materialization_plan_identity", "codec_profile_sha256"):
            for value in ("A" * 64, "a" * 63, "g" * 64, True):
                node = self.node()
                node[field] = value
                with self.assertRaises(e.EvidenceError):
                    self.decode_node(node)
        for runtime in ({}, records.encode(self.plan[0].board).decode("ascii"),
                        records.encode(self.runtime).decode("ascii") + "\n", True):
            node = self.node()
            node["runtime"] = runtime
            with self.assertRaises(e.EvidenceError):
                self.decode_node(node)

    def test_stream_family_order_shape_and_constructor_position_are_closed(self):
        for field in ("streams", "family_counts", "family_totals"):
            for mutation in (lambda value: value[::-1], lambda value: value[:-1],
                             lambda value: value + value[:1], lambda value: {}):
                node = self.node()
                node[field] = mutation(node[field])
                with self.subTest(field=field), self.assertRaises(e.EvidenceError):
                    self.decode_node(node)
        node = self.node()
        node["constructor_facts"][0]["position"] = 1
        with self.assertRaises(e.EvidenceError):
            self.decode_node(node)
        node = self.node()
        node["family_counts"][0][1] = 2
        with self.assertRaises(e.EvidenceError):
            self.decode_node(node)

    def test_closed_rejected_trial_provenance_is_distinct_from_family_policy(self):
        rejected = e.V2ConstructorTrialEvidence(2, 1, 100, 200, 0, 0, False, "SYNTHETIC_TEXT_WNEW_CAP")
        fact = replace(self.fact, trials=self.fact.trials + (rejected,))
        value = replace(self.value, constructor_facts=(fact,))
        decoded = e.decode_materialization_v2(e.encode_materialization_v2(value))
        self.assertEqual(decoded.constructor_facts[0].trials[1], rejected)
        self.assertTrue(readiness.evaluate_family_size("primary", 100, 200, 100, 200).eligible)
        self.assertNotIn(rejected.rejection_reason, e.V2_FAMILY_POLICY_REASONS)
        for reason in ("private arbitrary error", "SYNTHETIC_SIZING_SEARCH_EXHAUSTED",
                       "SYNTHETIC_LOGICAL_DOMAIN_EMPTY", "SYNTHETIC_TEXT_WNEW_CAP ", True, None):
            with self.subTest(reason=reason), self.assertRaises(e.EvidenceError):
                replace(rejected, rejection_reason=reason)
        with self.assertRaises(e.EvidenceError):
            replace(self.fact, trials=(replace(rejected, ordinal=1, rejection_reason="REFERENCE_SUNIT_CAP"),))

    def test_trial_domains_ordinals_availability_and_exact_boolean_are_closed(self):
        trial = self.fact.trials[0]
        for changes in ({"ordinal": 0}, {"ordinal": 9}, {"ordinal": True}, {"knob": -1},
                        {"knob": physical.MAX_PAYLOAD_BYTES + 1}, {"eligible": 1},
                        {"rejection_reason": "SYNTHETIC_TEXT_WNEW_CAP"},
                        {"actual_physical_bytes": None}, {"physical_margin": None}):
            with self.subTest(changes=changes), self.assertRaises(e.EvidenceError):
                replace(trial, **changes)
        for trials in (list(self.fact.trials), (), (replace(trial, ordinal=2),),
                       (trial, replace(trial, ordinal=2)), self.fact.trials * 9):
            with self.assertRaises(e.EvidenceError):
                replace(self.fact, trials=trials)
        reference_trial = replace(trial, knob=2_581_111)
        with self.assertRaises(e.EvidenceError):
            replace(self.fact, family="reference", constructor_kind="reference", trials=(reference_trial,))
        partial = e.V2ConstructorTrialEvidence(1, 0, None, 200, None, 0, False,
                                              "REFERENCE_CANONICAL_RECORD_FAILURE")
        self.assertIsNone(partial.actual_physical_bytes)

    def test_zero_oracle_evidence_retains_ordinal_zero_without_fake_trial(self):
        zero = replace(self.fact, family="oracle_primary", physical_target=0, logical_target=0,
            actual_physical_bytes=0, actual_logical_bytes=0, selected_knob=0, selected_trial_ordinal=0,
            text_window_applies=False, text_window_upper_bound=None, zero_oracle=True, trials=())
        value = replace(self.value, constructor_facts=(self.fact, zero),
            family_counts=tuple(zip(readiness.V2_FAMILIES, (1, 0, 1, 0, 0, 0))))
        self.assertEqual(e.decode_materialization_v2(e.encode_materialization_v2(value)), value)
        for changes in ({"selected_knob": 1}, {"selected_trial_ordinal": 1},
                        {"actual_physical_bytes": 1}, {"trials": self.fact.trials}, {"family": "primary"}):
            with self.assertRaises(e.EvidenceError):
                replace(zero, **changes)

    def test_encoder_revalidates_frozen_objects_after_external_corruption(self):
        for field, invalid in (("work_count", True), ("constructor_facts", []), ("family_totals", []),
                               ("runtime_monitor_peak_coordinator_private_bytes", 0), ("codec_profile_bytes", b"{}")):
            value = replace(self.value)
            object.__setattr__(value, field, invalid)
            with self.subTest(field=field), self.assertRaises(ValueError):
                e.encode_materialization_v2(value)
        fact = replace(self.fact)
        object.__setattr__(fact, "trials", (object(),))
        value = replace(self.value)
        object.__setattr__(value, "constructor_facts", (fact,))
        with self.assertRaises(e.EvidenceError):
            e.encode_materialization_v2(value)

    def test_plan_digest_independently_matches_closed_bytes_and_binds_every_work_field(self):
        import hashlib
        work = self.plan[0]
        node = {"position": work.position, "board": records.encode(work.board).decode("ascii"),
            "protocol_seed": work.protocol_seed.hex(), "run_id": work.run_id,
            "runtime": records.encode(work.runtime).decode("ascii"),
            "oracle_b_selected": work.oracle_b_selected, "determinism_selected": work.determinism_selected,
            "k_control_selected": work.k_control_selected}
        expected = hashlib.sha256(b"PROGRAM_K_V2_MATERIALIZATION_PLAN_IDENTITY_V1\0" + _json(node) + b"\n").hexdigest()
        self.assertEqual(e.plan_identity_v2(self.plan), expected)
        for changes in ({"board": h.reference_board_identity(work.board.game_index)},
                        {"protocol_seed": b"\x13" * 32}, {"run_id": work.run_id + "x"},
                        {"runtime": replace(work.runtime, host="other")}, {"oracle_b_selected": True},
                        {"determinism_selected": True}, {"k_control_selected": True}):
            with self.subTest(changes=changes):
                self.assertNotEqual(e.plan_identity_v2((replace(work, **changes),)), expected)
        for plan in ([], list(self.plan), (), (replace(work, position=1),),
                     (replace(work, runtime=None),), (object(),)):
            with self.assertRaises(e.EvidenceError):
                e.plan_identity_v2(plan)

    def test_v2_codec_and_plan_identity_are_pure_and_v1_remains_independent(self):
        forbidden = AssertionError("Evidence codec must not perform execution or I/O")
        with ExitStack() as stack:
            for owner, name in ((Path, "open"), (Path, "read_bytes"), (Path, "write_bytes"),
                    (physical, "capture_profile"), (physical, "capture_qualified_profile"),
                    (h, "_capture_qualified_codec_profile"), (h, "construct_reference_v2"),
                    (h, "construct_text_family_v2"), (h, "_materialize_v2_plan")):
                stack.enter_context(patch.object(owner, name, side_effect=forbidden))
            self.assertEqual(e.decode_materialization_v2(e.encode_materialization_v2(self.value)), self.value)
            self.assertEqual(e.plan_identity_v2(self.plan), self.value.source_plan_identity)
        with patch.object(e, "decode_materialization_v2", side_effect=forbidden), \
                patch.object(e, "encode_materialization_v2", side_effect=forbidden), \
                patch.object(e, "plan_identity_v2", side_effect=forbidden), \
                patch.object(physical, "require_qualified_profile", side_effect=forbidden):
            self.assertEqual(_decode(_encode(_facts()[0])), _facts()[0])
            self.assertEqual(e.encode_size_basis(e.SizeBasisV2(PROFILE)), _json(BASIS_FIELDS))


class V2ArchiveManifestEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from experiments import program_k_e2_identity as identity
        cls.streams = tuple(records.StreamDigest(name, format(index + 1, "064x"), index + 1, 1)
                            for index, name in enumerate(execution.STREAM_NAMES + (
                                "operations", "resources", "qualification_identity", "postprocessing_operations")))
        stream_files = {}
        for seal in cls.streams:
            prefix = "postprocessing/" if seal.name == "postprocessing_operations" else "streams/"
            path = prefix + seal.name + ".pkf"
            stream_files[path] = e.V2ArchiveFileEvidence(path, seal.byte_length, seal.sha256)
        cls.inventory = tuple(stream_files.get(path) or e.V2ArchiveFileEvidence(path, 3, "f" * 64)
                              for path in e.V2_ARCHIVE_PRE_MANIFEST_PATHS)
        by_path = {fact.path: fact for fact in cls.inventory}
        targets = readiness.DualComponentSizes(*(readiness.ComponentSizes(1, 1, 0, 0, 1, 1) for _ in range(2)))
        cls.value = e.V2ArchiveManifestEvidence(
            schema=e.R0B_EXPERIMENT_V2, kind="archive_manifest", classification="SYNTHETIC_NON_EFFECTIVENESS",
            synthetic_non_evidence=True, selection_receipt_sha256="1" * 64, corpus_sha256="2" * 64,
            source_sha256="3" * 64, protocol_sha256=identity.PROTOCOL_SHA256,
            materialization_file=by_path["streams/materialization-v2.json"], codec_profile_sha256=PROFILE,
            size_basis=e.SizeBasisV2(PROFILE), source_plan_identity="4" * 64, materialization_plan_identity="5" * 64,
            family_counts=tuple(zip(readiness.V2_FAMILIES, (1, 0, 0, 0, 0, 0))), targets=targets,
            family_totals=tuple(e.V2FamilyTotalEvidence(family, 1 if family == "primary" else 0,
                1 if family == "primary" else 0, 0) for family in readiness.V2_FAMILIES),
            e_final=0, b_proc=1000, remaining_procedural_budget=1000, physical_minimum_total=1,
            materialization_readback_complete=True, readback_streams=cls.streams[:-2], durable_operation_count=1,
            durable_primary_count=1, durable_sample_max_coordinator_private_bytes=200,
            runtime_monitor_peak_coordinator_private_bytes=300, runtime_peak_is_independent=False,
            constructor_rejections_are_runtime_provenance=True, qualification_identity_stream=cls.streams[-2],
            postprocessing_operations_stream=cls.streams[-1], analysis_file=by_path["postprocessing/analysis.json"],
            report_file=by_path["postprocessing/report.html"], streams=cls.streams,
            inventory_before_manifest_receipt=cls.inventory,
            attributable_bytes=sum(seal.byte_length for seal in cls.streams[:53]),
            projected_fixed_bytes=0, projected_archive_bytes=0,
            fixed_allowance_cap=identity.FIXED_REPORT_RECEIPT_ALLOWANCE, archive_cap=identity.MAX_ARCHIVE_BYTES,
            scope=e.V2_ARCHIVE_SCOPE)
        cls.raw = e.encode_archive_manifest_v2(cls.value)

    def node(self):
        return json.loads(self.raw)

    def decode_node(self, node):
        return e.decode_archive_manifest_v2(_json(node) + b"\n")

    def test_canonical_ascii_final_lf_roundtrip_and_explicit_archive_identity(self):
        self.assertEqual(self.raw, _json(self.node()) + b"\n")
        self.assertTrue(self.raw.isascii())
        self.assertFalse(self.raw.endswith(b"\n\n"))
        self.assertEqual(e.decode_archive_manifest_v2(self.raw, expected_profile_sha256=PROFILE), self.value)
        self.assertEqual(e.encode_archive_manifest_v2(e.decode_archive_manifest_v2(self.raw)), self.raw)
        self.assertEqual(self.node()["schema"], "program-k-e2-r0b-experiment/v2")
        self.assertEqual(self.node()["kind"], "archive_manifest")
        self.assertEqual(self.node()["classification"], "SYNTHETIC_NON_EFFECTIVENESS")
        self.assertNotIn("manifest_sha256", self.node())
        self.assertNotIn("completion", self.node())
        self.assertFalse(self.value.runtime_peak_is_independent)
        self.assertTrue(self.value.constructor_rejections_are_runtime_provenance)

    def test_exact_layout_paths_and_pre_manifest_inventory_exclude_future_files(self):
        self.assertEqual(len(e.V2_ARCHIVE_ATTRIBUTABLE_PATHS), 53)
        self.assertEqual(e.V2_ARCHIVE_ATTRIBUTABLE_PATHS,
                         tuple("streams/" + name + ".pkf" for name in execution.STREAM_NAMES))
        self.assertEqual(len(e.V2_ARCHIVE_PRE_MANIFEST_PATHS), 62)
        self.assertEqual(len(e.V2_ARCHIVE_FINAL_PATHS), 64)
        self.assertEqual(e.V2_ARCHIVE_FINAL_PATHS, tuple(sorted(set(e.V2_ARCHIVE_FINAL_PATHS))))
        self.assertEqual(set(e.V2_ARCHIVE_FINAL_PATHS) - set(e.V2_ARCHIVE_PRE_MANIFEST_PATHS),
                         {"manifest.json", "COMPLETE.json"})
        self.assertEqual(tuple(f.path for f in self.value.inventory_before_manifest_receipt),
                         e.V2_ARCHIVE_PRE_MANIFEST_PATHS)
        for path in ("/streams/boards.pkf", "../streams/boards.pkf", "streams/../status.json",
                     "streams\\boards.pkf", "streams//boards.pkf", "./status.json", "STATUS.json",
                     "streams/boards.jsonl", "unexpected", "", True):
            with self.subTest(path=path), self.assertRaises(e.EvidenceError):
                e.V2ArchiveFileEvidence(path, 0, "a" * 64)

    def test_archive_types_frozen_exact_and_excluded_from_v1_registry(self):
        for value in (self.value, self.value.materialization_file):
            self.assertFalse(hasattr(value, "__dict__"))
            self.assertNotIn(type(value), e._FACT_TYPES.values())
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)
            with self.assertRaises(e.EvidenceError):
                e.fact_node_v1(value)
            with self.assertRaises(e.EvidenceError):
                e.fact_read_v1({"fact": type(value).__name__, "fields": {}})
        class Derived(e.V2ArchiveManifestEvidence):
            pass
        values = {field.name: getattr(self.value, field.name) for field in fields(self.value)}
        with self.assertRaises(e.EvidenceError):
            e.encode_archive_manifest_v2(Derived(**values))
        class DerivedFile(e.V2ArchiveFileEvidence):
            pass
        with self.assertRaises(e.EvidenceError):
            replace(self.value, analysis_file=DerivedFile("postprocessing/analysis.json", 3, "f" * 64))

    def test_every_closed_nested_object_rejects_unknown_and_missing_fields(self):
        paths = ((), ("materialization_file",), ("size_basis",), ("targets",), ("targets", "physical"),
                 ("targets", "logical"), ("family_totals", 0), ("readback_streams", 0),
                 ("qualification_identity_stream",), ("postprocessing_operations_stream",),
                 ("analysis_file",), ("report_file",), ("streams", 0), ("inventory_before_manifest_receipt", 0))
        for path in paths:
            shape = self.node()
            for key in path:
                shape = shape[key]
            for field in tuple(shape) + ("unexpected",):
                node = self.node()
                target = node
                for key in path:
                    target = target[key]
                if field == "unexpected":
                    target[field] = None
                else:
                    del target[field]
                with self.subTest(path=path, field=field), self.assertRaises(e.EvidenceError):
                    self.decode_node(node)

    def test_duplicate_noncanonical_non_ascii_and_wrong_wire_types_fail(self):
        duplicate = b'{"kind":"archive_manifest",' + self.raw[1:]
        nested = self.raw.replace(b'"byte_length":1,', b'"byte_length":1,"byte_length":1,', 1)
        for raw in (self.raw[:-1], self.raw + b"\n", b" " + self.raw, self.raw + b" ",
                    self.raw.replace(b'"e_final":0', b'"e_final": 0'), duplicate, nested,
                    self.raw.replace(b'"kind":', b'"k\xffnd":')):
            with self.subTest(raw=raw[:40]), self.assertRaises(e.EvidenceError):
                e.decode_archive_manifest_v2(raw)
        for raw in (bytearray(self.raw), memoryview(self.raw), self.raw.decode("ascii"), None, b""):
            with self.assertRaises(e.EvidenceError):
                e.decode_archive_manifest_v2(raw)

    def test_exact_integer_fields_no_float_nan_bool_or_coercion(self):
        paths = tuple((field,) for field in ("e_final", "b_proc", "remaining_procedural_budget",
            "physical_minimum_total", "durable_operation_count", "durable_primary_count",
            "durable_sample_max_coordinator_private_bytes", "runtime_monitor_peak_coordinator_private_bytes",
            "attributable_bytes", "projected_fixed_bytes", "projected_archive_bytes",
            "fixed_allowance_cap", "archive_cap")) + (("family_counts", 0, 1),
            ("targets", "physical", "primary"), ("family_totals", 0, "physical_bytes"),
            ("streams", 0, "byte_length"), ("readback_streams", 0, "record_count"),
            ("materialization_file", "byte_length"), ("inventory_before_manifest_receipt", 0, "byte_length"))
        for path in paths:
            for bad in (True, False, 1.0, "1", None, -1):
                node = self.node()
                target = node
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = bad
                with self.subTest(path=path, bad=bad), self.assertRaises(e.EvidenceError):
                    self.decode_node(node)
        for token in (b"NaN", b"Infinity", b"-Infinity", b"1e0"):
            with self.assertRaises(e.EvidenceError):
                e.decode_archive_manifest_v2(self.raw.replace(b'"e_final":0', b'"e_final":' + token))

    def test_identity_digests_profile_provenance_flags_and_caps_are_exact(self):
        for field in ("selection_receipt_sha256", "corpus_sha256", "source_sha256", "protocol_sha256",
                      "codec_profile_sha256", "source_plan_identity", "materialization_plan_identity"):
            for bad in ("A" * 64, "a" * 63, "g" * 64, True, None):
                node = self.node()
                node[field] = bad
                with self.subTest(field=field, bad=bad), self.assertRaises(e.EvidenceError):
                    self.decode_node(node)
        for field, bad in (("schema", e.R0B_EXPERIMENT_V1), ("kind", "materialization"),
                ("classification", "EFFECTIVENESS"), ("scope", "support-only"),
                ("protocol_sha256", "a" * 64), ("fixed_allowance_cap", self.value.fixed_allowance_cap + 1),
                ("archive_cap", self.value.archive_cap - 1)):
            with self.subTest(field=field), self.assertRaises(e.EvidenceError):
                replace(self.value, **{field: bad})
        for field, expected in (("synthetic_non_evidence", True), ("materialization_readback_complete", True),
                ("runtime_peak_is_independent", False), ("constructor_rejections_are_runtime_provenance", True)):
            for bad in (not expected, int(expected), str(expected)):
                with self.subTest(field=field, bad=bad), self.assertRaises(e.EvidenceError):
                    replace(self.value, **{field: bad})
        with self.assertRaises(e.EvidenceError):
            replace(self.value, size_basis=e.SizeBasisV2("b" * 64))
        for expected in ("0" * 64, bytes.fromhex(PROFILE), True, "A" * 64):
            with self.assertRaises(e.EvidenceError):
                e.decode_archive_manifest_v2(self.raw, expected_profile_sha256=expected)

    def test_registry_order_missing_extra_duplicates_and_closed_family_order_fail(self):
        for field in ("streams", "readback_streams", "family_counts", "family_totals",
                      "inventory_before_manifest_receipt"):
            for mutate in (lambda value: value[::-1], lambda value: value[:-1],
                           lambda value: value + value[:1], lambda value: {}, lambda value: None):
                node = self.node()
                node[field] = mutate(node[field])
                with self.subTest(field=field), self.assertRaises(e.EvidenceError):
                    self.decode_node(node)
        node = self.node()
        node["streams"][0]["name"] = "extra"
        with self.assertRaises(e.EvidenceError):
            self.decode_node(node)
        with self.assertRaises(e.EvidenceError):
            replace(self.value, streams=tuple(sorted(self.streams, key=lambda seal: seal.name)))

    def test_manifest_registry_order_and_receipt_sorted_order_bind_same_57_seals(self):
        from experiments import program_k_e2_identity as identity
        receipt_fields = dict(manifest_sha256="6" * 64, corpus_sha256=self.value.corpus_sha256,
            source_sha256=self.value.source_sha256, protocol_sha256=identity.PROTOCOL_SHA256,
            state=records.CompletionState.COMPLETED)
        self.assertEqual(tuple(s.name for s in self.streams), e.V2_ARCHIVE_STREAM_NAMES)
        with self.assertRaises(ValueError):
            records.CompletionReceipt(streams=self.streams, **receipt_fields)
        sorted_streams = tuple(sorted(self.streams, key=lambda seal: seal.name))
        receipt = records.CompletionReceipt(streams=sorted_streams, **receipt_fields)
        self.assertEqual(records.decode(records.encode(receipt)), receipt)
        self.assertEqual(len(receipt.streams), 57)
        self.assertEqual({s.name: s for s in receipt.streams}, {s.name: s for s in self.value.streams})
        self.assertEqual(len({s.name for s in self.value.streams}), 57)
        with self.assertRaises(ValueError):
            records.CompletionReceipt(streams=sorted_streams + sorted_streams[-1:], **receipt_fields)

    def test_repeated_stream_file_and_inventory_bindings_cannot_disagree(self):
        paths = (("readback_streams", 0, "sha256"), ("qualification_identity_stream", "sha256"),
                 ("postprocessing_operations_stream", "byte_length"), ("materialization_file", "sha256"),
                 ("analysis_file", "byte_length"), ("report_file", "sha256"), ("streams", 0, "sha256"),
                 ("inventory_before_manifest_receipt", 1, "sha256"))
        # Inventory entry 1 is analysis.json in the fixed sorted layout.
        self.assertEqual(self.inventory[1].path, "postprocessing/analysis.json")
        for path in paths:
            node = self.node()
            target = node
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = "a" * 64 if path[-1] == "sha256" else target[path[-1]] + 1
            with self.subTest(path=path), self.assertRaises(e.EvidenceError):
                self.decode_node(node)
        node = self.node()
        node["inventory_before_manifest_receipt"].append({"path": "manifest.json", "byte_length": 0, "sha256": "0" * 64})
        with self.assertRaises(e.EvidenceError):
            self.decode_node(node)

    def test_provisional_projection_is_shape_only_and_does_not_create_budget_credit(self):
        # The close owner calculates the encoded-length fixed point and caps.
        # Pure codec validation must allow a provisional zero and over-cap facts.
        for fixed, archive in ((0, 0), (self.value.fixed_allowance_cap, self.value.archive_cap),
                               (self.value.fixed_allowance_cap + 1, self.value.archive_cap + 1)):
            value = replace(self.value, projected_fixed_bytes=fixed, projected_archive_bytes=archive)
            decoded = e.decode_archive_manifest_v2(e.encode_archive_manifest_v2(value))
            self.assertEqual((decoded.projected_fixed_bytes, decoded.projected_archive_bytes), (fixed, archive))
            self.assertEqual((decoded.b_proc, decoded.e_final, decoded.remaining_procedural_budget), (1000, 0, 1000))

    def test_encoder_revalidates_exact_frozen_nested_objects(self):
        for field, bad in (("e_final", True), ("streams", []), ("inventory_before_manifest_receipt", []),
                           ("scope", "wrong"), ("runtime_peak_is_independent", True)):
            value = replace(self.value)
            object.__setattr__(value, field, bad)
            with self.subTest(field=field), self.assertRaises(ValueError):
                e.encode_archive_manifest_v2(value)
        file_fact = replace(self.value.materialization_file)
        object.__setattr__(file_fact, "byte_length", True)
        value = replace(self.value)
        object.__setattr__(value, "materialization_file", file_fact)
        with self.assertRaises(ValueError):
            e.encode_archive_manifest_v2(value)

    def test_archive_codec_is_pure_and_historical_and_materialization_codecs_remain_independent(self):
        forbidden = AssertionError("Archive codec must not perform I/O, capture, readback or execution")
        with ExitStack() as stack:
            for owner, name in ((Path, "open"), (Path, "read_bytes"), (Path, "write_bytes"),
                    (physical, "capture_profile"), (physical, "capture_qualified_profile"),
                    (h, "_capture_qualified_codec_profile"), (h, "construct_reference_v2"),
                    (h, "construct_text_family_v2"), (h, "_materialize_v2_plan"), (h, "_readback_v2_plan"),
                    (e, "encode_materialization_v2"), (e, "decode_materialization_v2")):
                stack.enter_context(patch.object(owner, name, side_effect=forbidden))
            self.assertEqual(e.decode_archive_manifest_v2(e.encode_archive_manifest_v2(self.value)), self.value)
        with patch.object(e, "encode_archive_manifest_v2", side_effect=forbidden), \
                patch.object(e, "decode_archive_manifest_v2", side_effect=forbidden):
            self.assertEqual(_decode(_encode(_facts()[0])), _facts()[0])
            # Reuse a literal fixture constructor; no profile capture or workload.
            V2MaterializationEvidenceTests.setUpClass()
            materialization = V2MaterializationEvidenceTests.value
            self.assertEqual(e.decode_materialization_v2(e.encode_materialization_v2(materialization)), materialization)


class ImportPurityTests(unittest.TestCase):
    def test_no_harness_import_dynamic_registry_or_side_effect_calls(self):
        source = Path(e.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse(any(alias.name.endswith("program_k_e2_r0_harness") for alias in node.names))
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse((node.module or "").endswith("program_k_e2_r0_harness"))
                self.assertFalse(any(alias.name == "program_k_e2_r0_harness" for alias in node.names))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, ("eval", "exec", "__import__", "open"))

    def test_import_execution_is_read_write_process_workload_and_capture_free(self):
        import benchmark_board
        from experiments import program_k_runner as runner
        source = Path(e.__file__).read_text(encoding="utf-8")
        code = compile(source, e.__file__, "exec")
        probe = types.ModuleType("_slice1b_evidence_import_probe")
        probe.__file__ = e.__file__
        before = dict(os.environ)
        forbidden = AssertionError("Import must not perform I/O or work")
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {probe.__name__: probe}))
            for owner, name in ((Path, "open"), (Path, "read_bytes"), (Path, "read_text"),
                (Path, "write_bytes"), (Path, "write_text"), (subprocess, "Popen"), (subprocess, "run"),
                (benchmark_board, "generate_board"), (runner, "run_control_capture"),
                (runner, "run_k_p0"), (physical, "capture_profile"),
                (h, "capture_run_provenance"), (h, "launch_r0a"), (h, "launch_r0b"),
                (readiness, "_memberships"), (os, "putenv")):
                stack.enter_context(patch.object(owner, name, side_effect=forbidden))
            stack.enter_context(patch("builtins.open", side_effect=forbidden))
            exec(code, probe.__dict__)
        self.assertEqual(dict(os.environ), before)
        self.assertEqual(probe.schema_version(V2_SCHEMAS[0]), 2)


def _r0a_supplied_fixture_v2():
    """Complete supplied claims only: no board generation, wire, disk or capture."""
    from experiments import program_k_e2_identity as identity
    from tests.test_program_k_e2_physical import _qualified_node
    profile = physical.decode_profile(_json(_qualified_node()))
    runtime = records.RuntimeIdentity("FixturePython", "0", "fixture-os", "fixture-platform",
                                      "fixture-arch", None)
    seed = bytes.fromhex(identity.PROTOCOL_SHA256)
    indices = readiness.build_r0a_plan(seed).ordered_indices
    boards = tuple(records.BoardIdentity(index, "supplied-fingerprint-" + str(position), 30, 16, 99,
        (0, 0), "supplied-generator", "supplied-spec") for position, index in enumerate(indices))
    names = execution.STREAM_NAMES + ("operations", "resources")
    seals = tuple(records.StreamDigest(name, "a" * 64, 500, 1) for name in names)
    interval = e.R0AIntervalV2
    components = ("P", "K", "O", "D", "O_K_BIND", "O_D_REPEAT")
    families = dict(P="primary", K="k_control", O="oracle_primary", D="determinism",
                    O_K_BIND=None, O_D_REPEAT="oracle_repeat")
    kinds = dict(P=execution.WorkerKind.PRIMARY, K=execution.WorkerKind.K_CONTROL,
                 O=execution.WorkerKind.PRIMARY, D=execution.WorkerKind.DETERMINISM,
                 O_K_BIND=execution.WorkerKind.K_CONTROL,
                 O_D_REPEAT=execution.WorkerKind.DETERMINISM)
    setup_routes = dict(K="K", D="D", O_K_BIND="O_K_SETUP", O_D_REPEAT="O_D_SETUP")
    monitor = e.R0AMonitorEvidenceV2(25, 40, 3)
    payload = e.R0APayloadAxesV2(1000, 1200, 2000, 1500)
    concurrencies = []
    for concurrency in (1, 2, 4):
        measured = []
        for component_index, component in enumerate(components):
            units, waves, wall_intervals = [], [], []
            end = 100 + (64 // concurrency) * 100
            complete = interval(0, end + 30)
            for offset in range(0, 64, concurrency):
                positions = tuple(range(offset, offset + concurrency))
                base = 100 + (offset // concurrency) * 100
                setup_interval, target_interval = interval(base, base + 10), interval(base + 20, base + 80)
                if component in setup_routes:
                    waves.append(e.R0ASetupWaveV2(setup_routes[component], positions, setup_interval,
                                                target_interval, monitor, True))
                if component == "O_K_BIND":
                    wall_intervals.append(e.R0AWallIntervalV2("PRIOR_ENCODE", positions,
                                                              interval(base + 20, base + 25)))
                if component == "O_D_REPEAT":
                    wall_intervals.append(e.R0AWallIntervalV2("TARGET_PHASE", positions, target_interval))
                for position in positions:
                    binding = (interval(base + 30, base + 40),) if component == "O_K_BIND" else ()
                    observation = e.R0ATelemetryV2(10, 20, 30, 1, 2, 0, 1,
                        e.R0AOracleTelemetryV2(0, 0, 0, ()), True, True, True, binding)
                    family = families[component]
                    owned = e.R0AByteCountV2(0, 0, 0) if family is None else e.R0AByteCountV2(
                        200 + concurrency if position == 0 else 100 + concurrency,
                        220 + concurrency if position == 1 else 120 + concurrency, 1)
                    target = e.R0ACaseEvidenceV2(operational.UnitReceipt(position, kinds[component],
                        records.AuditStatus.PASS, "ADMITTED", 50, 0), observation, payload,
                        e.R0AArchiveEvidenceV2("c%d/%s/%d/target" % (concurrency, component, position), seals),
                        family, owned, True)
                    setup = None
                    if component in setup_routes:
                        setup_observation = replace(observation, prior_binding_intervals=())
                        setup_owned = e.R0AByteCountV2(300 + component_index * 10 + concurrency,
                                                      400 - component_index * 10 + concurrency, 1)
                        setup = e.R0ACaseEvidenceV2(operational.UnitReceipt(position,
                            execution.WorkerKind.PRIMARY, records.AuditStatus.PASS, "ADMITTED", 5, 0),
                            setup_observation, payload,
                            e.R0AArchiveEvidenceV2("c%d/%s/%d/setup" % (concurrency, component, position), seals),
                            "reference", setup_owned, True)
                    units.append(e.R0AUnitEvidenceV2(position, target, setup))
                    if component == "O_K_BIND":
                        wall_intervals.extend((e.R0AWallIntervalV2("PRIOR_BIND", (position,), binding[0]),
                            e.R0AWallIntervalV2("PARENT_ADMISSION", (position,),
                                interval(base + 50 + position - offset, base + 51 + position - offset))))
            if component in ("P", "K", "O", "D"):
                wall_intervals = [e.R0AWallIntervalV2("COMPLETE_ROUTE", tuple(range(64)), complete)]
            else:
                wall_intervals.extend((e.R0AWallIntervalV2("ORCHESTRATION", (), interval(10, 20)),
                    e.R0AWallIntervalV2("CLEANUP", (), interval(end + 10, end + 20))))
            wall_intervals.sort(key=lambda item: (item.interval.started_ns, item.interval.finished_ns,
                                                  item.phase, item.positions))
            measured.append(e.R0AComponentEvidenceV2(component, complete, tuple(wall_intervals), monitor,
                tuple(units), tuple(waves), tuple(e.R0AProgressV2(p, p + 1, 64) for p in range(64))))
        measured = tuple(measured)
        envelope = operational.OperatingEnvelope(concurrency, 100, 200, 300, 400, 500, 100,
            1000, 100000, 100000, 200000, 100000000, 1, 1000000, 65536, 100, 100, 100, 100, 100)
        concurrencies.append(e.R0AConcurrencyEvidenceV2(concurrency, "R0-SUPPLIED-C%d" % concurrency,
            envelope, measured, e.summarize_r0a_components_v2(measured), e.derive_r0a_containment_v2(measured)))
    return e.R0AObservationsV2(e.R0A_OBSERVATIONS_V2, h.SELECTION_RECEIPT_SHA256, "b" * 40,
        "c" * 64, records.ProtocolIdentity(identity.PROTOCOL_PATH, identity.PROTOCOL_SHA256,
            identity.PROTOCOL_BLOB_ID, identity.FREEZE_COMMIT), readiness.AmendmentProvenance(), runtime,
        e.R0APlanEvidenceV2(seed, boards), profile.canonical_bytes, profile.sha256.hex(),
        e.SizeBasisV2(profile.sha256.hex()), tuple(concurrencies))


def _r0a_change_component_v2(value, concurrency_index, component_index, component):
    concurrency = value.concurrencies[concurrency_index]
    components = list(concurrency.components)
    components[component_index] = component
    components = tuple(components)
    changed = replace(concurrency, components=components,
        family_summaries=e.summarize_r0a_components_v2(components),
        containment=e.derive_r0a_containment_v2(components))
    values = list(value.concurrencies)
    values[concurrency_index] = changed
    return replace(value, concurrencies=tuple(values))


class R0AProvenanceDigestV2Tests(unittest.TestCase):
    def setUp(self):
        self.sources = (records.SourceBlobIdentity("experiments/a.py", "a" * 40, "b" * 64, 10),
                        records.SourceBlobIdentity("experiments/z.py", "c" * 40, "d" * 64, 20))
        self.runtime = records.RuntimeIdentity("SuppliedPython", "1", "fixture", "fixture", "fixture", None)
        self.args = ("1" * 40, "2" * 40, self.sources,
            ((self.sources[0].path, "3" * 64, 12, True),
             (self.sources[1].path, "4" * 64, 20, False)), self.runtime, "C:\\supplied\\python.exe", True)

    def expected_node(self):
        a = self.args
        return dict(selection_source_head=a[0], r0_harness_source_head=a[1],
            sources=[records.encode(s).decode("ascii") for s in a[2]],
            working_files=[list(v) for v in a[3]], runtime=records.encode(a[4]).decode("ascii"),
            executable=a[5], dont_write_bytecode=a[6])

    def test_exact_seven_field_preimage_with_domain_lf_and_no_final_lf(self):
        from hashlib import sha256
        raw = b"program-k-e2-r0-provenance/v2\n" + _json(self.expected_node())
        actual = e.provenance_digest_v2(*self.args)
        self.assertFalse(raw.endswith(b"\n"))
        self.assertEqual(actual, sha256(raw).hexdigest())
        self.assertNotEqual(actual, sha256(raw + b"\n").hexdigest())
        self.assertEqual(actual, e.provenance_digest_v2(*self.args))
        self.assertEqual(set(self.expected_node()), {"selection_source_head", "r0_harness_source_head",
            "sources", "working_files", "runtime", "executable", "dont_write_bytecode"})
        self.assertIsInstance(self.expected_node()["runtime"], str)
        self.assertTrue(all(isinstance(v, str) for v in self.expected_node()["sources"]))

    def test_each_mutable_field_changes_binding_and_unsupported_bool_is_rejected(self):
        original = e.provenance_digest_v2(*self.args)
        changes = {0: "5" * 40, 1: "6" * 40,
            2: (replace(self.sources[0], blob_id="7" * 40), self.sources[1]),
            3: ((self.sources[0].path, "8" * 64, 12, True), self.args[3][1]),
            4: replace(self.runtime, python_version="2"), 5: "C:\\SUPPLIED\\python.exe"}
        for index, value in changes.items():
            args = list(self.args)
            args[index] = value
            with self.subTest(index=index):
                self.assertNotEqual(e.provenance_digest_v2(*args), original)
        for value in (False, 0, 1, "true", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                e.provenance_digest_v2(*self.args[:-1], value)

    def test_sources_are_exact_sorted_unique_and_working_files_exactly_correspond(self):
        mutations = ((2, self.sources[::-1]), (2, self.sources + self.sources[:1]),
            (2, list(self.sources)), (2, ()), (3, self.args[3][::-1]), (3, self.args[3][:-1]),
            (3, list(self.args[3])), (3, (list(self.args[3][0]), self.args[3][1])))
        for index, value in mutations:
            args = list(self.args)
            args[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                e.provenance_digest_v2(*args)
        for index, bad in ((0, "wrong/path"), (1, "A" * 64), (1, "g" * 64),
                           (2, True), (2, -1), (2, 1 << 64), (3, 1), (3, "false")):
            first = list(self.args[3][0])
            first[index] = bad
            args = list(self.args)
            args[3] = (tuple(first), self.args[3][1])
            with self.subTest(index=index, bad=bad), self.assertRaises(ValueError):
                e.provenance_digest_v2(*args)

    def test_head_runtime_executable_and_record_types_are_not_coerced(self):
        for index, bad in ((0, "A" * 40), (0, "a" * 39), (1, True), (4, records.encode(self.runtime)),
                           (5, ""), (5, Path("python.exe")), (5, True)):
            args = list(self.args)
            args[index] = bad
            with self.subTest(index=index, bad=bad), self.assertRaises(ValueError):
                e.provenance_digest_v2(*args)
        class Source(records.SourceBlobIdentity):
            pass
        with self.assertRaises(ValueError):
            e.provenance_digest_v2(self.args[0], self.args[1],
                (Source("experiments/a.py", "a" * 40, "b" * 64, 10),),
                (self.args[3][0],), *self.args[4:])

    def test_digest_is_supplied_only_with_capture_and_file_access_poisoned(self):
        from experiments import program_k_e2_qualification as qualification
        forbidden = AssertionError("Pure digest must not authenticate or touch files")
        with ExitStack() as stack:
            for owner, name in ((Path, "open"), (Path, "read_bytes"), (Path, "resolve"),
                (Path, "exists"), (subprocess, "run"), (qualification, "capture_sources_v2"),
                (h, "capture_run_provenance_v2"), (e, "fact_node_v1"), (e, "fact_read_v1")):
                stack.enter_context(patch.object(owner, name, side_effect=forbidden))
            stack.enter_context(patch("builtins.open", side_effect=forbidden))
            self.assertEqual(len(e.provenance_digest_v2(*self.args)), 64)


class R0AObservationsV2Tests(unittest.TestCase):
    """Supplied metadata acceptance is deliberately not durable authentication."""

    @classmethod
    def setUpClass(cls):
        cls.value = _r0a_supplied_fixture_v2()
        cls.raw = e.encode_r0a_observations_v2(cls.value)

    def test_canonical_complete_shape_exact_roundtrip_and_supplied_expected_bindings(self):
        node = json.loads(self.raw)
        self.assertEqual(self.raw, _json(node) + b"\n")
        self.assertTrue(self.raw.isascii())
        self.assertEqual(tuple(f.name for f in fields(self.value)), (
            "schema", "selection_receipt_sha256", "source_head", "provenance_sha256", "protocol",
            "amendment", "runtime", "plan", "codec_profile_bytes", "codec_profile_sha256", "size_basis",
            "concurrencies"))
        decoded = e.decode_r0a_observations_v2(self.raw,
            expected_profile_sha256=self.value.codec_profile_sha256,
            expected_provenance_sha256=self.value.provenance_sha256,
            expected_source_head=self.value.source_head)
        self.assertEqual(decoded, self.value)
        self.assertEqual(e.encode_r0a_observations_v2(decoded), self.raw)
        self.assertEqual(node["schema"], "program-k-e2-r0a-observations/v2")
        self.assertEqual(node["runtime"], records.encode(self.value.runtime).decode("ascii"))
        self.assertEqual(len(node["plan"]["boards"]), 64)
        self.assertNotIn("admission", node)
        self.assertNotIn("effectiveness", node)

    def test_exact_declaration_orders_are_frozen(self):
        orders = {
            e.R0APlanEvidenceV2: "protocol_seed boards",
            e.R0AConcurrencyEvidenceV2: "concurrency run_id envelope components family_summaries containment",
            e.R0AComponentEvidenceV2: "component complete_interval wall_intervals monitor units setup_waves progress",
            e.R0AIntervalV2: "started_ns finished_ns",
            e.R0AWallIntervalV2: "phase positions interval",
            e.R0AMonitorEvidenceV2: "coordinator_private_peak_bytes combined_peak_bytes memory_sample_count",
            e.R0AUnitEvidenceV2: "position target setup",
            e.R0ACaseEvidenceV2: "receipt observation payload archive family owned_bytes readback_complete",
            e.R0APayloadAxesV2: "logical_sum_bytes legacy_bundle_bytes wb02_wire_bytes physical_frame_bytes",
            e.R0AArchiveEvidenceV2: "relative_directory streams",
            e.R0AByteCountV2: "physical_bytes logical_bytes record_count",
            e.R0ASetupWaveV2: "route positions setup_interval target_interval monitor readback_complete",
            e.R0AProgressV2: "position done total",
            e.R0ATelemetryV2: "worker_memory coordinator_memory combined_memory decision_wall arm_wall shadow_wall "
                "physical_inputs oracle resources_complete cleanup_complete watchdogs_complete prior_binding_intervals",
            e.R0AOracleTelemetryV2: "probes calls wall_ns intervals",
            e.R0ARouteContainmentV2: "route max_worker_memory_bytes max_coordinator_memory_bytes max_combined_memory_bytes "
                "max_decision_wall_ns max_arm_wall_ns max_case_wall_ns max_shadow_wall_ns max_physical_inputs "
                "max_logical_sum_bytes max_legacy_bundle_bytes max_wb02_wire_bytes max_physical_frame_bytes "
                "launcher_wall_ns watchdogs_complete resources_complete cleanup_complete progress_complete "
                "readback_complete watchdog_breaches resource_breaches",
        }
        for cls, order in orders.items():
            with self.subTest(cls=cls.__name__):
                self.assertEqual(tuple(f.name for f in fields(cls)), tuple(order.split()))

    def test_root_and_nested_unknown_missing_and_duplicate_fields_fail(self):
        # One representative at each new closed nested shape; no archive is opened.
        node = json.loads(self.raw)
        paths = ((), ("plan",), ("concurrencies", 0), ("concurrencies", 0, "components", 0),
            ("concurrencies", 0, "components", 0, "monitor"),
            ("concurrencies", 0, "components", 0, "units", 0, "target", "payload"),
            ("concurrencies", 0, "family_summaries", 0), ("concurrencies", 0, "containment", 0))
        for path in paths:
            target = node
            for part in path:
                target = target[part]
            original = dict(target)
            key = next(iter(target))
            del target[key]
            with self.subTest(path=path, missing=key), self.assertRaises(ValueError):
                e.decode_r0a_observations_v2(_json(node) + b"\n")
            target.update(original)
            target["unexpected"] = 0
            with self.subTest(path=path, extra=True), self.assertRaises(ValueError):
                e.decode_r0a_observations_v2(_json(node) + b"\n")
            del target["unexpected"]
        duplicate = self.raw.replace(b'"finished_ns":', b'"finished_ns":0,"finished_ns":', 1)
        with self.assertRaises(ValueError):
            e.decode_r0a_observations_v2(duplicate)

    def test_noncanonical_wire_numbers_input_types_and_bounds_fail(self):
        for raw in (self.raw[:-1], self.raw + b"\n", self.raw[:-1] + b"\r\n", b" " + self.raw,
                    self.raw + b" ", self.raw + b"{}"):
            with self.subTest(suffix=raw[-5:]), self.assertRaises(ValueError):
                e.decode_r0a_observations_v2(raw)
        for token in (b"1.0", b"1e0", b"NaN", b"Infinity", b"-Infinity", b"true", b"-1",
                      str(1 << 64).encode("ascii")):
            raw = self.raw.replace(b'"memory_sample_count":3', b'"memory_sample_count":' + token, 1)
            with self.subTest(token=token), self.assertRaises(ValueError):
                e.decode_r0a_observations_v2(raw)
        for value in (b"", None, bytearray(b"{}\n"), memoryview(b"{}\n"), "{}\n"):
            with self.assertRaises(ValueError):
                e.decode_r0a_observations_v2(value)
        with self.assertRaises(ValueError):
            e.decode_r0a_observations_v2(b"x" * (67_108_864 + 1))

    def test_closed_c_component_summary_containment_and_run_identity_orders(self):
        value, concurrency = self.value, self.value.concurrencies[0]
        self.assertEqual(tuple(v.concurrency for v in value.concurrencies), (1, 2, 4))
        self.assertEqual(tuple(v.component for v in concurrency.components), ("P", "K", "O", "D", "O_K_BIND", "O_D_REPEAT"))
        for field in ("components", "family_summaries", "containment"):
            source = getattr(concurrency, field)
            for bad in (source[::-1], source[:-1], source + source[:1], list(source)):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    replace(concurrency, **{field: bad})
        with self.assertRaises(ValueError):
            replace(value, concurrencies=value.concurrencies[::-1])
        with self.assertRaises(ValueError):
            replace(value, concurrencies=(concurrency, replace(value.concurrencies[1], run_id=concurrency.run_id),
                                         value.concurrencies[2]))

    def test_unit_progress_wave_and_stream_orders_are_not_silently_normalized(self):
        component = self.value.concurrencies[1].components[1]
        for field in ("units", "progress", "setup_waves"):
            source = getattr(component, field)
            for bad in (source[::-1], source[:-1], source + source[:1], list(source)):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    replace(component, **{field: bad})
        archive = component.units[0].target.archive
        self.assertEqual(len(archive.streams), 55)
        for bad in (archive.streams[::-1], archive.streams[:-1], archive.streams + archive.streams[:1]):
            with self.assertRaises(ValueError):
                replace(archive, streams=bad)
        with self.assertRaises(ValueError):
            replace(component.progress[0], done=2)

    def test_plan_seed_board_identity_and_profile_bindings_are_closed(self):
        from experiments import program_k_e2_identity as identity
        plan = self.value.plan
        for bad in (plan.boards[::-1], plan.boards[:-1], plan.boards + plan.boards[:1]):
            with self.assertRaises(ValueError):
                replace(plan, boards=bad)
        with self.assertRaises(ValueError):
            replace(plan, protocol_seed=b"\0" * 32)
        for field, bad in (("schema", e.R0A_OBSERVATIONS_V1),
            ("protocol", replace(self.value.protocol, sha256="0" * 64)),
            ("size_basis", e.SizeBasisV2("0" * 64)), ("codec_profile_sha256", "0" * 64)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(self.value, **{field: bad})
        profile_node = json.loads(self.value.codec_profile_bytes)
        profile_node["status"] = "UNQUALIFIED"
        from hashlib import sha256
        raw = _json(profile_node)
        digest = sha256(raw).hexdigest()
        with self.assertRaises(ValueError):
            replace(self.value, codec_profile_bytes=raw, codec_profile_sha256=digest, size_basis=e.SizeBasisV2(digest))
        self.assertEqual(plan.protocol_seed.hex(), identity.PROTOCOL_SHA256)

    def test_expected_binding_mismatch_does_not_trigger_live_authentication(self):
        for kwargs in (dict(expected_profile_sha256="0" * 64),
                       dict(expected_provenance_sha256="0" * 64), dict(expected_source_head="0" * 40)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                e.decode_r0a_observations_v2(self.raw, **kwargs)

    def test_complete_claim_flags_receipts_breaches_and_missing_setup_fail(self):
        c = self.value.concurrencies[0]
        case = c.components[1].units[0].target
        for status in (records.AuditStatus.FAIL, records.AuditStatus.INCOMPLETE):
            with self.assertRaises(ValueError):
                replace(case, receipt=replace(case.receipt, status=status))
        for field in ("resources_complete", "cleanup_complete", "watchdogs_complete"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(case.observation, **{field: False})
        with self.assertRaises(ValueError):
            replace(case, readback_complete=False)
        for field in ("watchdog_breaches", "resource_breaches"):
            with self.assertRaises(ValueError):
                replace(c.containment[0], **{field: 1})
        units = (replace(c.components[1].units[0], setup=None),) + c.components[1].units[1:]
        with self.assertRaises(ValueError):
            replace(c.components[1], units=units)
        with self.assertRaises(ValueError):
            replace(c.components[1].setup_waves[0], readback_complete=False)

    def test_safe_path_claims_numeric_bools_and_exact_record_types(self):
        case = self.value.concurrencies[0].components[0].units[0].target
        for path in ("/absolute", "C:/absolute", "../escape", "a/../b", "a/./b", "a//b", "a\\b", "", True):
            with self.subTest(path=path), self.assertRaises(ValueError):
                replace(case.archive, relative_directory=path)
        for field in ("physical_bytes", "logical_bytes", "record_count"):
            for bad in (True, -1, 1 << 64, 1.0, "1"):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    replace(case.owned_bytes, **{field: bad})
        with self.assertRaises(ValueError):
            replace(case, receipt=records.encode(self.value.runtime))
        with self.assertRaises(ValueError):
            replace(case.payload, wb02_wire_bytes=48 + case.payload.physical_frame_bytes)

    def test_raw_summaries_reconcile_independent_totals_and_distinct_witnesses(self):
        c = self.value.concurrencies[0]
        summary = c.family_summaries[0]
        owned = tuple(v.target.owned_bytes for v in c.components[0].units)
        self.assertEqual(summary.physical_total_bytes, sum(v.physical_bytes for v in owned))
        self.assertEqual(summary.logical_total_bytes, sum(v.logical_bytes for v in owned))
        self.assertEqual(summary.record_count, 64)
        self.assertEqual(summary.physical_max_unit_bytes, owned[0].physical_bytes)
        self.assertEqual(summary.logical_max_unit_bytes, owned[1].logical_bytes)
        for field in ("physical_total_bytes", "logical_total_bytes", "physical_max_unit_bytes",
                      "logical_max_unit_bytes", "record_count"):
            wrong = replace(summary, **{field: getattr(summary, field) + 1})
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(c, family_summaries=(wrong,) + c.family_summaries[1:])

    def test_physical_only_and_logical_only_changes_have_no_cross_credit(self):
        original = readiness.derive_r0a_dual_maxima_v2(tuple((c.concurrency, c.family_summaries)
                                                          for c in self.value.concurrencies))
        component = self.value.concurrencies[2].components[0]
        for field, axis, other in (("physical_bytes", "physical", "logical"),
                                   ("logical_bytes", "logical", "physical")):
            case = component.units[2].target
            changed_case = replace(case, owned_bytes=replace(case.owned_bytes, **{field: 700}))
            units = list(component.units)
            units[2] = replace(units[2], target=changed_case)
            value = _r0a_change_component_v2(self.value, 2, 0, replace(component, units=tuple(units)))
            maxima = readiness.derive_r0a_dual_maxima_v2(tuple((c.concurrency, c.family_summaries)
                                                            for c in value.concurrencies))
            self.assertEqual(getattr(maxima, axis).primary, 700)
            self.assertEqual(getattr(maxima, other), getattr(original, other))

    def test_zero_oracle_is_complete_and_k_bind_can_have_nonempty_archive(self):
        value = self.value
        for ci in range(3):
            for component_index in (2, 5):
                component = value.concurrencies[ci].components[component_index]
                units = tuple(replace(unit, target=replace(unit.target,
                    owned_bytes=e.R0AByteCountV2(0, 0, 0))) for unit in component.units)
                value = _r0a_change_component_v2(value, ci, component_index, replace(component, units=units))
        maxima = readiness.derive_r0a_dual_maxima_v2(tuple((c.concurrency, c.family_summaries)
                                                         for c in value.concurrencies))
        self.assertEqual((maxima.physical.oracle_primary, maxima.logical.oracle_repeat), (0, 0))
        for c in value.concurrencies:
            self.assertTrue(all(c.family_summaries[i].completed_units == 64 for i in (2, 3)))
            case = c.components[4].units[0].target
            self.assertIsNone(case.family)
            self.assertEqual(case.owned_bytes, e.R0AByteCountV2(0, 0, 0))
            self.assertGreater(sum(s.byte_length for s in case.archive.streams), 0)

    def test_containment_reconciliation_keeps_runtime_monitor_peak_independent(self):
        c = self.value.concurrencies[0]
        containment = c.containment[0]
        self.assertEqual(containment.max_coordinator_memory_bytes, 25)
        self.assertEqual(containment.max_combined_memory_bytes, 40)
        self.assertEqual(c.components[0].units[0].target.observation.coordinator_memory, 20)
        self.assertEqual((containment.max_logical_sum_bytes, containment.max_legacy_bundle_bytes,
            containment.max_wb02_wire_bytes, containment.max_physical_frame_bytes), (1000, 1200, 2000, 1500))
        for field in ("max_coordinator_memory_bytes", "max_combined_memory_bytes", "launcher_wall_ns",
                      "max_logical_sum_bytes", "max_wb02_wire_bytes"):
            changed = replace(containment, **{field: getattr(containment, field) + 1})
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(c, containment=(changed,) + c.containment[1:])

    def test_setup_only_variable_memory_does_not_borrow_target_or_global_peaks(self):
        concurrency = self.value.concurrencies[1]
        for component_index, setup_route in ((4, "O_K_SETUP"), (5, "O_D_SETUP")):
            component = concurrency.components[component_index]
            first = component.units[0]
            target = replace(first.target, observation=replace(first.target.observation,
                coordinator_memory=700, combined_memory=800))
            setup = replace(first.setup, observation=replace(first.setup.observation,
                coordinator_memory=250, combined_memory=350))
            units = (replace(first, target=target, setup=setup),) + component.units[1:]
            waves = (replace(component.setup_waves[0], monitor=e.R0AMonitorEvidenceV2(300, 400, 4)),) + component.setup_waves[1:]
            changed = replace(component, units=units, setup_waves=waves,
                              monitor=e.R0AMonitorEvidenceV2(900, 1100, 5))
            components = list(concurrency.components)
            components[component_index] = changed
            summaries = {item.route: item for item in e.derive_r0a_containment_v2(tuple(components))}
            with self.subTest(component=component.component):
                self.assertEqual((summaries[component.component].max_coordinator_memory_bytes,
                    summaries[component.component].max_combined_memory_bytes), (900, 1100))
                self.assertEqual((summaries[setup_route].max_coordinator_memory_bytes,
                    summaries[setup_route].max_combined_memory_bytes), (300, 400))
                self.assertEqual(summaries[setup_route].max_case_wall_ns, 5)
                self.assertEqual(summaries[component.component].max_case_wall_ns, 50)
                self.assertEqual(summaries[setup_route].launcher_wall_ns, 32 * 10)

    def test_k_d_copied_target_bytes_remain_in_target_family_not_reference(self):
        baseline = readiness.derive_r0a_dual_maxima_v2(tuple((c.concurrency, c.family_summaries)
                                                          for c in self.value.concurrencies))
        concurrency = self.value.concurrencies[2]
        for index, target_family in ((1, "k_control"), (3, "determinism")):
            component = concurrency.components[index]
            first = component.units[0]
            target = replace(first.target, owned_bytes=replace(first.target.owned_bytes, physical_bytes=700))
            changed = replace(component, units=(replace(first, target=target),) + component.units[1:])
            components = list(concurrency.components)
            components[index] = changed
            summaries = e.summarize_r0a_components_v2(tuple(components))
            maxima = readiness.derive_r0a_dual_maxima_v2(tuple(
                (c.concurrency, summaries if c.concurrency == 4 else c.family_summaries)
                for c in self.value.concurrencies))
            with self.subTest(family=target_family):
                self.assertEqual(getattr(maxima.physical, target_family), 700)
                self.assertEqual(maxima.physical.reference, baseline.physical.reference)
                self.assertEqual(maxima.logical, baseline.logical)
            with self.assertRaises(ValueError):
                replace(component, units=(replace(first, target=replace(first.target, family="reference")),)
                                         + component.units[1:])

    def test_every_nested_reader_has_closed_fields_without_opening_full_archive(self):
        component = self.value.concurrencies[1].components[4]
        telemetry = replace(component.units[0].target.observation,
            oracle=e.R0AOracleTelemetryV2(1, 1, 3, (e.R0AIntervalV2(130, 133),)))
        cases = (
            (e._r0a_read_interval, e._r0a_interval_node(component.complete_interval), ((),)),
            (e._r0a_read_monitor, e._r0a_monitor_node(component.monitor), ((),)),
            (e._r0a_read_telemetry, e._r0a_telemetry_node(telemetry),
             ((), ("oracle",), ("oracle", "intervals", 0), ("prior_binding_intervals", 0))),
            (e._r0a_read_case, e._r0a_case_node(component.units[0].target),
             ((), ("receipt",), ("payload",), ("archive",), ("archive", "streams", 0), ("owned_bytes",))),
            (e._r0a_read_wave, e._r0a_wave_node(component.setup_waves[0]),
             ((), ("setup_interval",), ("target_interval",), ("monitor",))),
            (e._r0a_read_component, e._r0a_component_node(component),
             (("wall_intervals", 0), ("units", 0), ("progress", 0))),
            (e._r0a_read_concurrency, e._r0a_concurrency_node(self.value.concurrencies[1]),
             (("envelope",), ("family_summaries", 0), ("containment", 0))),
        )
        for reader, node, paths in cases:
            for path in paths:
                target = node
                for part in path:
                    target = target[part]
                original = dict(target)
                for field in original:
                    del target[field]
                    with self.subTest(reader=reader.__name__, path=path, missing=field), self.assertRaises(ValueError):
                        reader(node)
                    target[field] = original[field]
                target["unexpected"] = None
                with self.subTest(reader=reader.__name__, path=path, extra=True), self.assertRaises(ValueError):
                    reader(node)
                del target["unexpected"]

    def test_oracle_and_binding_telemetry_require_exact_counts_intervals_and_clocks(self):
        interval = e.R0AIntervalV2(10, 15)
        valid = e.R0AOracleTelemetryV2(1, 1, 5, (interval,))
        for fields_changed in (dict(probes=2), dict(calls=2), dict(wall_ns=6), dict(probes=True),
                               dict(intervals=()), dict(intervals=[interval])):
            with self.subTest(fields=fields_changed), self.assertRaises(ValueError):
                replace(valid, **fields_changed)
        with self.assertRaises(ValueError):
            e.R0AOracleTelemetryV2(2, 1, 10, (interval, e.R0AIntervalV2(14, 19)))
        with self.assertRaises(ValueError):
            e.R0AIntervalV2(15, 10)
        with self.assertRaises(ValueError):
            e.R0AIntervalV2(True, 10)
        observation = self.value.concurrencies[0].components[0].units[0].target.observation
        for changes in (dict(combined_memory=9), dict(decision_wall=3), dict(resources_complete=1),
                        dict(prior_binding_intervals=(e.R0AIntervalV2(10, 20), e.R0AIntervalV2(19, 21)))):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(observation, **changes)

    def test_frozen_exact_types_and_encoder_revalidate_corrupted_nested_claims(self):
        component = self.value.concurrencies[0].components[0]
        case = component.units[0].target
        for value in (self.value, self.value.plan, self.value.concurrencies[0], component,
                      component.monitor, case, case.owned_bytes, case.archive, case.payload,
                      case.observation, case.observation.oracle, component.progress[0]):
            self.assertFalse(hasattr(value, "__dict__"))
            self.assertNotIn(type(value), e._FACT_TYPES.values())
            with self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)
        forged = replace(case.owned_bytes)
        object.__setattr__(forged, "physical_bytes", True)
        forged_case = replace(case)
        object.__setattr__(forged_case, "owned_bytes", forged)
        forged_unit = replace(component.units[0])
        object.__setattr__(forged_unit, "target", forged_case)
        forged_component = replace(component)
        object.__setattr__(forged_component, "units", (forged_unit,) + component.units[1:])
        forged_concurrency = replace(self.value.concurrencies[0])
        object.__setattr__(forged_concurrency, "components", (forged_component,) + forged_concurrency.components[1:])
        forged_root = replace(self.value)
        object.__setattr__(forged_root, "concurrencies", (forged_concurrency,) + self.value.concurrencies[1:])
        with self.assertRaises(ValueError):
            e.encode_r0a_observations_v2(forged_root)

    def test_embedded_record_strings_are_exact_and_not_alternate_json_or_types(self):
        runtime = records.encode(self.value.runtime).decode("ascii")
        self.assertEqual(e._r0a_read_rec(runtime, records.RuntimeIdentity), self.value.runtime)
        alternatives = (json.dumps(json.loads(runtime)), runtime + "\n", runtime.encode("ascii"),
                        records.encode(self.value.plan.boards[0]).decode("ascii"))
        for raw in alternatives:
            with self.subTest(raw=repr(raw)[:60]), self.assertRaises(ValueError):
                e._r0a_read_rec(raw, records.RuntimeIdentity)

    def test_v1_registry_literal_and_helpers_remain_independent(self):
        baseline = e.fact_node_v1((b"\x00\xff", Fraction(3, 2), records.StreamDigest("operations", "d" * 64, 0, 0)))
        forbidden = AssertionError("V1 must not dispatch to R0A V2")
        with patch.object(e, "encode_r0a_observations_v2", side_effect=forbidden), \
                patch.object(e, "decode_r0a_observations_v2", side_effect=forbidden), \
                patch.object(e, "provenance_digest_v2", side_effect=forbidden):
            self.assertEqual(e.fact_node_v1(e.fact_read_v1(baseline)), baseline)
        for value in (self.value, self.value.plan, self.value.concurrencies[0],
                      self.value.concurrencies[0].components[0]):
            self.assertNotIn(type(value), e._FACT_TYPES.values())
            with self.assertRaises(ValueError):
                e.fact_node_v1(value)
        with self.assertRaises(ValueError):
            e.decode_r0a_observations_v2(_json({"fact": "R0AObservationsV2", "fields": {}}) + b"\n")

    def test_pure_codec_reconciliation_and_maxima_never_touch_real_archives(self):
        from experiments import program_k_e2_qualification as qualification
        from experiments import program_k_e2_store as store
        forbidden = AssertionError("Pure claims are not durable authentication")
        with ExitStack() as stack:
            for owner, name in ((Path, "open"), (Path, "read_bytes"), (Path, "write_bytes"),
                (Path, "exists"), (Path, "resolve"), (Path, "iterdir"), (Path, "is_symlink"),
                (subprocess, "run"), (physical, "capture_qualified_profile"),
                (qualification, "capture_sources_v2"), (h, "capture_run_provenance_v2"),
                (h, "launch_r0a"), (h, "launch_r0b"), (h, "_begin_run"),
                (operational, "measure_r0_component"), (operational, "_persist_r0"),
                (store, "scan_framed_stream"), (store, "FramedStreamPullReader")):
                stack.enter_context(patch.object(owner, name, side_effect=forbidden))
            stack.enter_context(patch("builtins.open", side_effect=forbidden))
            value = e.decode_r0a_observations_v2(e.encode_r0a_observations_v2(self.value))
            maxima = readiness.derive_r0a_dual_maxima_v2(tuple((c.concurrency, c.family_summaries)
                                                             for c in value.concurrencies))
            self.assertEqual(readiness.derive_dual_targets(maxima).physical.primary,
                             (3 * maxima.physical.primary + 1) // 2)


class R0AWallReconstructionV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = _r0a_supplied_fixture_v2()

    def component(self, name, concurrency_index=1):
        return next(v for v in self.value.concurrencies[concurrency_index].components if v.component == name)

    def test_p_k_d_o_use_only_complete_boundary_including_orchestration_once(self):
        for name in ("P", "K", "D", "O"):
            component = self.component(name)
            self.assertEqual(e.r0a_component_wall_v2(component),
                             component.complete_interval.finished_ns - component.complete_interval.started_ns)
            self.assertEqual(tuple(v.phase for v in component.wall_intervals), ("COMPLETE_ROUTE",))
            with self.assertRaises(ValueError):
                replace(component, wall_intervals=component.wall_intervals +
                    (e.R0AWallIntervalV2("ORCHESTRATION", (), e.R0AIntervalV2(10, 20)),))

    def test_k_bind_global_union_counts_concurrent_binding_once(self):
        component = self.component("O_K_BIND")
        # c=2: 32 waves * (encode5 + shared bind10 + two admission1) + overhead20.
        self.assertEqual(e.r0a_component_wall_v2(component), 32 * 17 + 20)
        naive = sum(v.interval.finished_ns - v.interval.started_ns for v in component.wall_intervals)
        self.assertGreater(naive, e.r0a_component_wall_v2(component))
        self.assertGreater(component.complete_interval.finished_ns, e.r0a_component_wall_v2(component))

    def test_k_bind_missing_duplicate_or_wrong_phase_coverage_fails(self):
        component = self.component("O_K_BIND")
        for phase in ("ORCHESTRATION", "PRIOR_ENCODE", "PRIOR_BIND", "PARENT_ADMISSION", "CLEANUP"):
            index = next(i for i, item in enumerate(component.wall_intervals) if item.phase == phase)
            items = component.wall_intervals
            for bad in (items[:index] + items[index + 1:], items[:index] + (items[index],) + items[index:]):
                with self.subTest(phase=phase), self.assertRaises(ValueError):
                    replace(component, wall_intervals=bad)
        encoding = next(v for v in component.wall_intervals if v.phase == "PRIOR_ENCODE")
        changed = replace(encoding, positions=(0,))
        with self.assertRaises(ValueError):
            replace(component, wall_intervals=tuple(changed if v is encoding else v for v in component.wall_intervals))

    def test_k_bind_exact_prior_binding_multiset_and_parent_positions(self):
        component = self.component("O_K_BIND")
        for phase in ("PRIOR_BIND", "PARENT_ADMISSION"):
            item = next(v for v in component.wall_intervals if v.phase == phase)
            changed = replace(item, positions=(63,))
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                replace(component, wall_intervals=tuple(changed if v is item else v for v in component.wall_intervals))
        item = next(v for v in component.wall_intervals if v.phase == "PRIOR_BIND")
        changed = replace(item, interval=replace(item.interval, finished_ns=item.interval.finished_ns + 1))
        with self.assertRaises(ValueError):
            replace(component, wall_intervals=tuple(changed if v is item else v for v in component.wall_intervals))

    def test_d_repeat_includes_orchestration_target_waves_cleanup_without_setup(self):
        component = self.component("O_D_REPEAT")
        self.assertEqual(e.r0a_component_wall_v2(component), 10 + 32 * 60 + 10)
        self.assertEqual(tuple(v.phase for v in component.wall_intervals).count("TARGET_PHASE"), 32)
        setup_wall = sum(v.setup_interval.finished_ns - v.setup_interval.started_ns for v in component.setup_waves)
        containment = self.value.concurrencies[1].containment[-1]
        self.assertEqual(containment.launcher_wall_ns, setup_wall)
        span = component.setup_waves[-1].setup_interval.finished_ns - component.setup_waves[0].setup_interval.started_ns
        self.assertNotEqual(containment.launcher_wall_ns, span)
        self.assertNotEqual(containment.launcher_wall_ns, component.complete_interval.finished_ns -
                            e.r0a_component_wall_v2(component))

    def test_d_repeat_phase_mismatch_overlap_and_chronology_fail(self):
        component = self.component("O_D_REPEAT")
        target = next(v for v in component.wall_intervals if v.phase == "TARGET_PHASE")
        changed = replace(target, interval=replace(target.interval, finished_ns=target.interval.finished_ns - 1))
        with self.assertRaises(ValueError):
            replace(component, wall_intervals=tuple(changed if v is target else v for v in component.wall_intervals))
        orchestration = component.wall_intervals[0]
        overlapping = replace(orchestration, interval=e.R0AIntervalV2(10, target.interval.started_ns + 1))
        with self.assertRaises(ValueError):
            replace(component, wall_intervals=(overlapping,) + component.wall_intervals[1:])
        wave = component.setup_waves[0]
        with self.assertRaises(ValueError):
            replace(wave, setup_interval=e.R0AIntervalV2(wave.target_interval.started_ns,
                                                       wave.target_interval.started_ns + 1))

    def test_zero_duration_required_phase_remains_present_and_canonical_order_is_enforced(self):
        component = self.component("O_D_REPEAT")
        phase = component.wall_intervals[0]
        zero = replace(phase, interval=e.R0AIntervalV2(10, 10))
        changed = replace(component, wall_intervals=(zero,) + component.wall_intervals[1:])
        self.assertEqual(e.r0a_component_wall_v2(changed), e.r0a_component_wall_v2(component) - 10)
        with self.assertRaises(ValueError):
            replace(component, wall_intervals=component.wall_intervals[1:])
        with self.assertRaises(ValueError):
            replace(component, wall_intervals=component.wall_intervals[::-1])
        for bad in ("ROUTE_OVERHEAD", "orchestration", "SETUP"):
            with self.assertRaises(ValueError):
                replace(phase, phase=bad)


if __name__ == "__main__":
    unittest.main()
