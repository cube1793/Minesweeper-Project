"""Closed, deterministic publication and historical reconstruction of E1 evidence.

Publication is an explicit, separate operation. COMPLETE records completion of
publication, including an incomplete or failed qualification attempt. Historical
readback checks retained identities and evidence without executing research work
or requiring today's source files to have the historical identity.
"""

from dataclasses import dataclass, fields
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path

from core_engine import Action, CellState, GameStatus
from experiments import program_k_e1_evaluator as _e1_evaluator
from experiments import program_k_e1_operational as _operational
from experiments import program_k_e1_qualification as _qualification
from experiments import program_k_e1_suite as _suite
from experiments import program_k_evaluator as _evaluator
from experiments import program_k_harness as _harness
from simple_decision import DecisionKind


class E1PersistenceError(ValueError):
    """Unrecognized, noncanonical, corrupted, or unpublished E1 evidence."""


def _need(condition, detail):
    if not condition:
        raise E1PersistenceError(detail)


def _sha(value):
    _need(type(value) is str and len(value) == 64
          and all(c in "0123456789abcdef" for c in value), "Invalid SHA-256.")


@dataclass(frozen=True, slots=True)
class E1ArtifactReceipt:
    run_id: str
    content_sha256: str
    size_bytes: int
    qualification_source_digest: str
    operational_source_digest: str
    plan_source_digest: str
    envelope_digest: str
    protocol_sha256: str
    verdict: str
    readiness: str
    progression_allowed: bool
    assessment_content_sha256: str
    suite_content_sha256: str | None
    resource_content_sha256: str | None
    completion_marker: str = "COMPLETE"

    def __post_init__(self):
        _qualification.validate_run_id(self.run_id)
        for name in (
                "content_sha256", "qualification_source_digest",
                "operational_source_digest", "plan_source_digest",
                "envelope_digest", "protocol_sha256", "assessment_content_sha256"):
            _sha(getattr(self, name))
        for value in (self.suite_content_sha256, self.resource_content_sha256):
            if value is not None:
                _sha(value)
        _need(type(self.size_bytes) is int and self.size_bytes > 0,
              "Qualification byte size must be a positive exact integer.")
        _need(type(self.verdict) is str and self.verdict in (
            "E1_PASS", "IMPLEMENTATION_IDENTITY_FAIL", "INCOMPLETE"),
              "Unknown E1 implementation verdict.")
        _need(type(self.readiness) is str and self.readiness in (
            "E1_QUALIFIED", "E1_A_E5_REQUIRED", "NOT_QUALIFIED"),
              "Unknown E1 readiness.")
        _need(type(self.progression_allowed) is bool
              and self.progression_allowed == (self.verdict == "E1_PASS")
              and (self.readiness == "E1_QUALIFIED") == self.progression_allowed
              and (self.readiness != "E1_A_E5_REQUIRED" or self.verdict == "INCOMPLETE"),
              "Receipt verdict/readiness/progression disagree.")
        _need(type(self.completion_marker) is str and self.completion_marker == "COMPLETE",
              "Only a completed publication has an artifact receipt.")


# Exact imported families and individually named extensions. Artifact content
# never chooses a module to import or discovers classes by scanning a module.
_ENUM_TYPES = (Action, CellState, GameStatus, DecisionKind)
_RECORD_TYPES = tuple(dict.fromkeys(_suite._RECORD_TYPES + (
    _evaluator.ArchivedAssertion, _evaluator.SealedEvaluatorInput,
    _evaluator.CoordinateComparison, _evaluator.AssertionFinding,
    _evaluator.FalsificationResult, _evaluator.EvaluatorCallDiagnostic,
    _e1_evaluator.E1EvaluatorFinding,
    _operational.E1OperationalSourceFile, _operational.E1OperationalSourceIdentity,
    _operational.E1MonitorEvent, _operational.E1OperationReceipt,
    _operational.E1OperationResult, _operational.E1ResourceSummary,
    _harness.OperatingEnvelope, _harness.MemoryEvidence,
    _qualification.E1QualificationSourceFile,
    _qualification.E1QualificationSourceIdentity,
    _qualification.E1Preflight, _qualification.E1GateResult,
    _qualification.E1QualificationAssessment, _qualification.E1QualificationRecord,
    E1ArtifactReceipt,
)))
_RECORD_BY_TAG = {cls.__module__ + "." + cls.__qualname__: cls for cls in _RECORD_TYPES}
_ENUM_BY_TAG = {cls.__module__ + "." + cls.__qualname__: cls for cls in _ENUM_TYPES}


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":")).encode("ascii")


def _ordered_set_members(value):
    # Frozen protocol coordinates remain (x,y), ordered by (y,x). General
    # immutable membership uses the exact tagged representation as its key.
    if all(type(cell) is tuple and len(cell) == 2
           and all(type(n) is int for n in cell) for cell in value):
        return tuple(sorted(value, key=lambda cell: (cell[1], cell[0])))
    return None


def _encoded(value):
    active, memo = set(), {}

    def visit(item):
        cls = type(item)
        if cls in _ENUM_TYPES:
            return ("enum", cls.__module__ + "." + cls.__qualname__, item.name)
        if cls is type(None):
            return ("none",)
        if cls is bool:
            return ("bool", item)
        if cls is int:
            # Hex avoids the interpreter's decimal digit limit without changing
            # global settings or ever converting authoritative integers to float.
            return ("int", hex(item))
        if cls is str:
            return ("str", item)
        if cls is Fraction:
            return ("fraction", hex(item.numerator), hex(item.denominator))
        if cls is float:
            _need(math.isfinite(item), "Nonfinite floating-point evidence.")
            return ("float", item.hex())
        key = id(item)
        _need(key not in active, "Cyclic evidence graph.")
        if key in memo:
            return memo[key]
        active.add(key)
        if cls is tuple:
            result = ("tuple", tuple(visit(child) for child in item))
        elif cls is frozenset:
            ordered = _ordered_set_members(item)
            children = tuple(visit(child) for child in (item if ordered is None else ordered))
            if ordered is None:
                children = tuple(sorted(children, key=_json_bytes))
            result = ("frozenset", children)
        else:
            _need(cls in _RECORD_TYPES and cls.__dataclass_params__.frozen,
                  "Unsupported mutable, live, hidden, or unregistered evidence type.")
            names = tuple(field.name for field in fields(cls))
            _need(not hasattr(item, "__dict__") or set(vars(item)) == set(names),
                  "Unexpected attachment to a frozen evidence record.")
            result = ("record", cls.__module__ + "." + cls.__qualname__,
                      tuple((name, visit(getattr(item, name))) for name in names))
        active.remove(key)
        memo[key] = result
        return result

    return visit(value)


def canonical_bytes(value):
    """Encode exact immutable types and every field, including compare=False."""
    try:
        return _json_bytes(_encoded(value))
    except (TypeError, AttributeError, OverflowError, RecursionError) as error:
        raise E1PersistenceError("Evidence cannot enter the closed E1 codec.") from error


def content_digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _decode(node):
    _need(type(node) is list and bool(node) and type(node[0]) is str,
          "A canonical tagged node is required.")
    tag = node[0]
    if tag == "none":
        _need(len(node) == 1, "Extra null payload.")
        return None
    if tag in ("bool", "str"):
        expected = bool if tag == "bool" else str
        _need(len(node) == 2 and type(node[1]) is expected, "Wrong primitive payload type.")
        return node[1]
    if tag == "int":
        _need(len(node) == 2 and type(node[1]) is str, "Malformed exact integer.")
        return int(node[1], 16)
    if tag == "float":
        _need(len(node) == 2 and type(node[1]) is str, "Malformed hexadecimal float.")
        result = float.fromhex(node[1])
        _need(math.isfinite(result), "Nonfinite floating-point evidence.")
        return result
    if tag == "fraction":
        _need(len(node) == 3 and all(type(v) is str for v in node[1:]),
              "Malformed exact fraction.")
        numerator, denominator = (int(v, 16) for v in node[1:])
        _need(denominator > 0, "Fraction denominator must be positive.")
        return Fraction(numerator, denominator)
    if tag == "enum":
        _need(len(node) == 3 and all(type(v) is str for v in node[1:])
              and node[1] in _ENUM_BY_TAG, "Unknown enum tag.")
        cls = _ENUM_BY_TAG[node[1]]
        _need(node[2] in cls.__members__, "Unknown enum member.")
        return cls.__members__[node[2]]
    if tag in ("tuple", "frozenset"):
        _need(len(node) == 2 and type(node[1]) is list, "Malformed immutable collection.")
        children = tuple(_decode(child) for child in node[1])
        if tag == "tuple":
            return children
        result = frozenset(children)
        _need(len(result) == len(children), "Duplicate frozenset membership.")
        return result
    _need(tag == "record" and len(node) == 3 and type(node[1]) is str
          and node[1] in _RECORD_BY_TAG and type(node[2]) is list,
          "Unknown record schema or node tag.")
    cls, pairs = _RECORD_BY_TAG[node[1]], node[2]
    _need(all(type(pair) is list and len(pair) == 2 and type(pair[0]) is str
              for pair in pairs), "Malformed ordered record fields.")
    names = tuple(pair[0] for pair in pairs)
    _need(names == tuple(field.name for field in fields(cls)),
          "Missing, extra, duplicate, or reordered record fields.")
    values = {name: _decode(child) for name, child in pairs}
    if cls in (_operational.E1OperationReceipt, _operational.E1OperationResult):
        # These accepted Slice-5 constructors also check today's machine.
        # Their unchanged checks run in qualification's isolated historical
        # binding instead; no module globals are patched.
        candidate = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(candidate, name, value)
        return _qualification._historical_checked(candidate, cls)
    return cls(**values)


def reconstruct(data, *, expected_digest=None):
    """Strict canonical decoding through the explicit vocabulary only."""
    _need(type(data) is bytes, "Canonical evidence must be exact bytes.")
    if expected_digest is not None:
        _sha(expected_digest)
        _need(hashlib.sha256(data).hexdigest() == expected_digest, "Content digest mismatch.")

    def reject_object(_):
        raise E1PersistenceError("JSON mappings are outside the E1 codec.")

    def reject_constant(_):
        raise E1PersistenceError("Nonfinite JSON number.")

    try:
        text = data.decode("ascii")
        decoded = _decode(json.loads(text, object_pairs_hook=reject_object,
                                    parse_constant=reject_constant))
        _need(canonical_bytes(decoded) == data, "Noncanonical or lossy E1 encoding.")
        return decoded
    except (ValueError, TypeError, AttributeError, KeyError, IndexError,
            OverflowError, RecursionError) as error:
        if isinstance(error, E1PersistenceError):
            raise
        raise E1PersistenceError("Corrupt E1 evidence encoding.") from error


def _reconstruction_digests(record):
    try:
        suite = _qualification.reconstruct_e1_suite(record)
    except _qualification.E1ReconstructionError:
        return None, None
    try:
        resources = _qualification.reconstruct_e1_resources(record)
    except _qualification.E1ReconstructionError:
        return content_digest(suite), None
    return content_digest(suite), content_digest(resources)


def _receipt(record, data, assessment):
    suite_digest, resource_digest = _reconstruction_digests(record)
    source = record.source_identity
    return E1ArtifactReceipt(
        record.run_id, hashlib.sha256(data).hexdigest(), len(data),
        source.digest, source.operational_source_identity.digest,
        record.plan.source_identity.digest,
        _harness.content_digest(record.operating_envelope), source.protocol_sha256,
        assessment.verdict, assessment.readiness, assessment.progression_allowed,
        content_digest(assessment), suite_digest, resource_digest)


def _destination(repository_root, run_id):
    _qualification.validate_run_id(run_id)
    root = Path(__file__).resolve().parents[1] if repository_root is None else Path(repository_root)
    root = root.resolve()
    parent = root / "results" / "program_k_research"
    # Reject link/junction redirection before creating any directory.
    for path in (root / "results", parent):
        _need(not path.is_symlink()
              and not (hasattr(path, "is_junction") and path.is_junction()),
              "Artifact parent cannot be a link or junction.")
        _need(path.resolve().is_relative_to(root), "Artifact path escapes the repository root.")
    directory = parent / run_id
    _need(directory.parent == parent and directory.resolve().is_relative_to(parent.resolve()),
          "Artifact path escapes its publication parent.")
    _need(not directory.exists() and not directory.is_symlink(),
          "Artifact destination already exists; publication never overwrites.")
    return directory


def _write_exclusive(path, data):
    with path.open("xb") as handle:
        written = handle.write(data)
        _need(written == len(data), "Incomplete artifact write.")
        handle.flush()
        os.fsync(handle.fileno())


def persist_e1_qualification(record, *, repository_root=None):
    """Publish once; leave a partial directory visible on any interruption."""
    _need(type(record) is _qualification.E1QualificationRecord,
          "An exact E1 qualification record is required.")
    directory = _destination(repository_root, record.run_id)
    assessment = _qualification.assess_e1(record)
    data = canonical_bytes(record)
    receipt = _receipt(record, data, assessment)
    marker = canonical_bytes(receipt)
    _need(len(data) + len(marker) <= record.operating_envelope.archive_cap_bytes,
          "Durable qualification and completion receipt exceed the declared archive cap.")
    _need(_qualification.capture_qualification_source_identity(record.plan) == record.source_identity,
          "Current final qualification source differs; publication refused.")
    directory.parent.mkdir(parents=True, exist_ok=True)
    # Recheck after parent creation, including a competing publication.
    _need(_destination(repository_root, record.run_id) == directory,
          "Artifact destination changed during publication admission.")
    directory.mkdir()
    _write_exclusive(directory / "qualification.json", data)
    _write_exclusive(directory / "COMPLETE.json", marker)
    return receipt


def read_e1_qualification_artifact(directory):
    """Reconstruct historical evidence, bindings, and exact assessment read-only."""
    directory = Path(directory)
    try:
        _qualification.validate_run_id(directory.name)
        _need(directory.is_dir() and not directory.is_symlink()
              and not (hasattr(directory, "is_junction") and directory.is_junction()),
              "An unredirected completed artifact directory is required.")
        _need({path.name for path in directory.iterdir()}
              == {"qualification.json", "COMPLETE.json"},
              "Artifact must contain exactly qualification.json and COMPLETE.json.")
        qualification_path, marker_path = directory / "qualification.json", directory / "COMPLETE.json"
        _need(all(path.is_file() and not path.is_symlink()
                  for path in (qualification_path, marker_path)),
              "Artifact files must be ordinary files.")
        marker = marker_path.read_bytes()
        receipt = reconstruct(marker)
        _need(type(receipt) is E1ArtifactReceipt, "COMPLETE is not an exact E1 artifact receipt.")
        _need(qualification_path.stat().st_size == receipt.size_bytes,
              "Qualification file byte count differs.")
        data = qualification_path.read_bytes()
        _need(len(data) == receipt.size_bytes, "Qualification file changed while reading.")
        record = reconstruct(data, expected_digest=receipt.content_sha256)
        _need(type(record) is _qualification.E1QualificationRecord,
              "Qualification is not an exact E1 qualification record.")
        _need(directory.name == record.run_id == receipt.run_id, "Artifact run identity differs.")
        _need(len(data) + len(marker) <= record.operating_envelope.archive_cap_bytes,
              "Published evidence exceeds the declared archive cap.")
        assessment = _qualification.assess_e1(record)
        expected = _receipt(record, data, assessment)
        _need(canonical_bytes(receipt) == canonical_bytes(expected),
              "Artifact source, evidence reconstruction, or assessment receipt differs.")
        _need(marker_path.read_bytes() == marker and qualification_path.read_bytes() == data,
              "Artifact changed during readback.")
        return record, receipt, assessment
    except (OSError, ValueError, TypeError, AttributeError, KeyError, IndexError) as error:
        if isinstance(error, E1PersistenceError):
            raise
        raise E1PersistenceError("Incomplete or invalid E1 qualification artifact.") from error
