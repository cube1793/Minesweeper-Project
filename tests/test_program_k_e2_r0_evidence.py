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


if __name__ == "__main__":
    unittest.main()
