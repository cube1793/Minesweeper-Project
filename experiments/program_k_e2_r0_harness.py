"""Program-K E2 R0 orchestration and non-effectiveness evidence.

Actual launch entry points require explicit mode authorization and committed,
clean source. Importing, planning and decoding evidence never launch workers.
The accepted E2 owners retain all selection, worker, record/store, readiness and
bootstrap semantics. R0 operator evidence describes a closed synthetic experiment
archive; every archive-local supporting file counts toward its fixed allowance.
"""

from dataclasses import dataclass, fields, replace
from enum import Enum
from fractions import Fraction
from hashlib import sha256, shake_256
import base64
import json
import os
from pathlib import Path
import platform
import struct
import sys
import threading
import time
import uuid

from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_records as records
from experiments import program_k_e2_physical as physical
from experiments import program_k_e2_store as store
from experiments import program_k_e2_execution as execution
from experiments import program_k_e2_operational as operational
from experiments import program_k_e2_qualification as qualification
from experiments import program_k_e2_readiness as readiness
from experiments import program_k_e2_r0_evidence as evidence
from experiments import program_k_e2_analysis as analysis
from experiments import program_k_e2_report as report
from experiments import program_k_e2_game as game
from experiments import program_k_e2_audit as audit


class HarnessError(ValueError):
    """Closed operational failure; never an effectiveness verdict."""


def _need(condition, reason):
    if not condition:
        raise HarnessError(reason)


def _integer(value, minimum=0):
    _need(type(value) is int and minimum <= value <= identity.UINT64_MAX, "EXACT_INTEGER_REQUIRED")


def _canonical(node):
    return json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii") + b"\n"


def _exclusive_bytes(path, data):
    _need(type(data) is bytes, "EXACT_BYTES_REQUIRED")
    path = Path(path)
    with path.open("xb") as stream:
        _need(stream.write(data) == len(data), "SHORT_EVIDENCE_WRITE")
        stream.flush()
        os.fsync(stream.fileno())
    _need(path.read_bytes() == data, "EVIDENCE_READBACK_MISMATCH")
    return path


# RECEIPT_PROVENANCE_BEGIN
SELECTION_SOURCE_HEAD = "cdba3513c23df77ba44449af1e551889a6954768"
SETUP_REPAIR_HEAD = "e6593f7a99af2f0dd941eda7ee53a5164c79a2bd"
SELECTION_RECEIPT_BYTES = 7364
SELECTION_RECEIPT_SHA256 = "72ea48582d3eb2c4eff82172b58fe88460a8a3747eee910efe5fc8a2deb6337c"
_REAL_DIGEST = "b712aa0733c5ad458ea01838b35589926184cc0892da6a33844df60b6ae31167"
_SYNTHETIC_DIGEST = "b78485dc50dc051d42645059bb86c39c1d4ca9db6cc3ba3be9d9290413831efb"
_HARNESS_PATH = "experiments/program_k_e2_r0_harness.py"
_SELECTION_SCHEMA = "program-k-e2-r0-synthetic-selection-receipt/v1"
_RECEIPT_KEYS = frozenset("""accepted_i8_ancestor actual_e2_run ahead amendment_byte_length
amendment_sha256 base_protocol_blob base_protocol_byte_length base_protocol_freeze_commit
base_protocol_sha256 behind board_generation classification committed_candidate_blobs
committed_readiness_blob domain_hygiene dominance_margins fact_scope fingerprints_generated
git_branch git_head git_parent git_parents git_subject git_tree holdout_accessed
observational_search_timing open_findings origin_main other_real_n_computed outcomes_read
project_git_mutation protocol_seed purpose real_candidate_identity real_corpus_digest
real_r0_run real_target_count_invocations real_target_counts real_target_n repository_preservation
schema selector_identity solver_execution static_call_path status structural_coverage
synthetic_corpus_digest synthetic_counts synthetic_rule synthetic_search tracked_source_changes
work_plan_validation""".split())


def _json_bytes(data):
    def pairs(items):
        value = {}
        for key, item in items:
            _need(key not in value, "DUPLICATE_JSON_FIELD")
            value[key] = item
        return value
    def illegal(_):
        raise HarnessError("NONINTEGER_JSON_NUMBER")
    _need(type(data) is bytes, "EXACT_BYTES_REQUIRED")
    try:
        value = json.loads(data.decode("ascii"), object_pairs_hook=pairs,
                           parse_float=illegal, parse_constant=illegal)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise HarnessError("INVALID_JSON") from error
    _need(_canonical(value) == data, "NONCANONICAL_JSON")
    return value


def _exact_fields(node, expected, reason):
    _need(type(node) is dict and set(node) == set(expected), reason)
    for key, value in expected.items():
        _need(type(node[key]) is type(value) and node[key] == value, reason)


def _selection_semantics(node):
    _need(type(node) is dict and set(node) == _RECEIPT_KEYS, "SELECTION_FIELDS")
    scalar = {
        "schema": _SELECTION_SCHEMA,
        "purpose": "Program K E2 R0 synthetic-corpus selection",
        "classification": "non-research operational evidence",
        "fact_scope": "OUTCOME-BLIND SELECTOR-MEMBERSHIP FACTS ONLY",
        "status": "SELECTION_CANDIDATE_PENDING_CHATGPT_ADJUDICATION",
        "git_head": SELECTION_SOURCE_HEAD, "origin_main": SELECTION_SOURCE_HEAD,
        "git_branch": "main", "ahead": 0, "behind": 0,
        "amendment_byte_length": qualification._AMENDMENT_BYTE_LENGTH,
        "amendment_sha256": qualification._AMENDMENT_SHA256,
        "base_protocol_sha256": identity.PROTOCOL_SHA256,
        "base_protocol_blob": qualification._BLOB, "base_protocol_byte_length": 57841,
        "base_protocol_freeze_commit": qualification._FREEZE,
        "protocol_seed": identity.PROTOCOL_SHA256,
        "committed_readiness_blob": "5fea5c48b7ce4dfdbdc1de04df95d3e27180042f",
        "real_target_n": identity.CANDIDATE_MAX, "real_corpus_digest": _REAL_DIGEST,
        "synthetic_corpus_digest": _SYNTHETIC_DIGEST, "real_target_count_invocations": 1,
    }
    for key, expected in scalar.items():
        _need(type(node[key]) is type(expected) and node[key] == expected,
              "SELECTION_" + key.upper())
    for key in ("actual_e2_run", "real_r0_run", "board_generation", "fingerprints_generated",
                "outcomes_read", "solver_execution", "holdout_accessed", "project_git_mutation",
                "tracked_source_changes"):
        _need(node[key] is False, "SELECTION_FORBIDDEN_ACTIVITY")
    _need(node["other_real_n_computed"] == [], "SELECTION_OTHER_TARGETS")
    _exact_fields(node["real_target_counts"], {"u_kd": 505, "i_od": 2, "i_ok": 3}, "SELECTION_REAL_COUNTS")
    _exact_fields(node["synthetic_counts"], {"u_kd": 506, "i_od": 4, "i_ok": 4}, "SELECTION_SYNTHETIC_COUNTS")
    _exact_fields(node["dominance_margins"], {"u_kd": 1, "i_od": 2, "i_ok": 1}, "SELECTION_DOMINANCE")
    _exact_fields(node["structural_coverage"], {"o_intersect_d": 4, "o_intersect_k": 4}, "SELECTION_STRUCTURE")
    _exact_fields(node["synthetic_rule"], {
        "domain_low": readiness.SYNTHETIC_INDEX_LOW,
        "domain_high_exclusive": readiness.SYNTHETIC_INDEX_HIGH,
        "corpus_size": identity.CANDIDATE_MAX, "production_search_limit": readiness.SYNTHETIC_SEARCH_LIMIT,
        "selected_ordinal": 5, "selected_start": 2000000050000,
        "selected_end_exclusive": 2000000060000,
        "enumeration": "contiguous non-overlapping blocks, ordinal zero first",
        "selection": "first match", "auxiliary_d_repeat": False, "auxiliary_k_bind": False,
    }, "SELECTION_SYNTHETIC_RULE")
    _need(type(node["committed_candidate_blobs"]) is dict and
          node["committed_candidate_blobs"].get("experiments/program_k_e2_readiness.py")
          == node["committed_readiness_blob"], "SELECTION_READINESS_BINDING")
    _need(node["domain_hygiene"].get("status") == node["work_plan_validation"].get("status") == "PASS",
          "SELECTION_HYGIENE")
    return node


def _decode_selection(data):
    _need(type(data) is bytes and len(data) == SELECTION_RECEIPT_BYTES, "SELECTION_RECEIPT_SIZE")
    _need(sha256(data).hexdigest() == SELECTION_RECEIPT_SHA256, "SELECTION_RECEIPT_SHA256")
    return _selection_semantics(_json_bytes(data))


@dataclass(frozen=True, slots=True)
class AcceptedSelectionReceipt:
    path: str
    canonical_bytes: bytes

    def __post_init__(self):
        _need(type(self.path) is str and Path(self.path).is_absolute(), "ABSOLUTE_RECEIPT_PATH_REQUIRED")
        _decode_selection(self.canonical_bytes)

    @property
    def selection_source_head(self):
        return SELECTION_SOURCE_HEAD

    @property
    def target(self):
        return readiness.SubsetCounts(identity.CANDIDATE_MAX, 505, 2, 3, bytes.fromhex(_REAL_DIGEST))

    @property
    def selection(self):
        return readiness.SyntheticCorpusSelection(bytes.fromhex(identity.PROTOCOL_SHA256), 5,
            readiness.SubsetCounts(identity.CANDIDATE_MAX, 506, 4, 4, bytes.fromhex(_SYNTHETIC_DIGEST)))

    @property
    def workload(self):
        return readiness.SyntheticWorkload(self.selection, self.target)


def load_selection_receipt(path):
    """Authenticate the operator-supplied file; never search or rewrite it."""
    path = Path(path).resolve(strict=True)
    _need(path.is_file(), "SELECTION_RECEIPT_FILE_REQUIRED")
    return AcceptedSelectionReceipt(str(path), path.read_bytes())


def _runtime_identity():
    return records.RuntimeIdentity(platform.python_implementation(), platform.python_version(),
        os.name, platform.platform(), platform.machine(), None)


@dataclass(frozen=True, slots=True)
class RunProvenance:
    selection_source_head: str
    r0_harness_source_head: str
    sources: tuple
    working_files: tuple
    runtime: records.RuntimeIdentity
    executable: str
    dont_write_bytecode: bool

    def __post_init__(self):
        _need(self.selection_source_head == SELECTION_SOURCE_HEAD, "SELECTION_SOURCE_BINDING")
        _need(type(self.r0_harness_source_head) is str and len(self.r0_harness_source_head) == 40
              and all(c in "0123456789abcdef" for c in self.r0_harness_source_head), "HARNESS_HEAD_REQUIRED")
        _need(type(self.sources) is tuple and bool(self.sources), "SOURCE_IDENTITIES_REQUIRED")
        _need(all(type(s) is records.SourceBlobIdentity for s in self.sources), "SOURCE_IDENTITY_TYPE")
        for source in self.sources:
            records.SourceBlobIdentity.__post_init__(source)
        _need(tuple(s.path for s in self.sources) == tuple(sorted(set(s.path for s in self.sources)))
              and _HARNESS_PATH in {s.path for s in self.sources}, "HARNESS_SOURCE_NOT_BOUND")
        _need(type(self.working_files) is tuple and len(self.working_files) == len(self.sources)
              and all(type(v) is tuple and len(v) == 4 and type(v[0]) is str and type(v[1]) is str
                      and type(v[2]) is int and type(v[3]) is bool for v in self.working_files),
              "WORKING_FILE_IDENTITIES_REQUIRED")
        _need(tuple(v[0] for v in self.working_files) == tuple(s.path for s in self.sources),
              "WORKING_SOURCE_PATH_MISMATCH")
        for _, digest, length, normalized in self.working_files:
            _integer(length)
            _need(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "WORKING_SOURCE_HASH")
        _need(type(self.runtime) is records.RuntimeIdentity, "RUNTIME_REQUIRED")
        records.RuntimeIdentity.__post_init__(self.runtime)
        _need(type(self.executable) is str and bool(self.executable) and self.dont_write_bytecode is True,
              "PYTHON_ENVIRONMENT_REQUIRED")


def capture_run_provenance(receipt):
    """Committed live source is independent of the receipt's historical HEAD."""
    _need(type(receipt) is AcceptedSelectionReceipt, "ACCEPTED_RECEIPT_REQUIRED")
    _need(load_selection_receipt(receipt.path) == receipt, "SELECTION_RECEIPT_CHANGED")
    _need(sys.dont_write_bytecode and os.environ.get("PYTHONDONTWRITEBYTECODE") == "1",
          "PYTHONDONTWRITEBYTECODE_REQUIRED")
    head = qualification._git("rev-parse", "HEAD").strip().decode("ascii")
    _need(not qualification._git("status", "--porcelain=v1", "--untracked-files=all").strip(),
          "COMMITTED_CLEAN_SOURCE_REQUIRED")
    for ancestor in (SELECTION_SOURCE_HEAD, SETUP_REPAIR_HEAD):
        qualification._git("merge-base", "--is-ancestor", ancestor, head)
    sources = qualification.capture_sources()
    _need(_HARNESS_PATH in {v.path for v in sources}, "HARNESS_SOURCE_NOT_BOUND")
    blobs = qualification._blobs(tuple(head + ":" + v.path for v in sources))
    working = []
    for source, (blob, data) in zip(sources, blobs):
        _need((blob, sha256(data).hexdigest(), len(data)) ==
              (source.blob_id, source.sha256, source.byte_length), "SOURCE_BLOB_CHANGED")
        raw = (qualification._ROOT / source.path).read_bytes()
        if source.path == qualification._AMENDMENT:
            _need(len(raw) == qualification._AMENDMENT_BYTE_LENGTH
                  and sha256(raw).hexdigest() == qualification._AMENDMENT_SHA256,
                  "FROZEN_WORKING_AMENDMENT_DRIFT")
        elif source.path == qualification._PROTOCOL:
            identity.validate_protocol_bytes(raw)
        # The only allowed raw/blob distinction is proven CRLF normalization.
        _need(raw == data or raw.replace(b"\r\n", b"\n") == data, "WORKING_SOURCE_IDENTITY_DRIFT")
        working.append((source.path, sha256(raw).hexdigest(), len(raw), raw != data))
    _need(qualification._git("rev-parse", "HEAD").strip().decode("ascii") == head
          and not qualification._git("status", "--porcelain=v1", "--untracked-files=all").strip(),
          "SOURCE_CHANGED_DURING_CAPTURE")
    _need(load_selection_receipt(receipt.path) == receipt, "SELECTION_RECEIPT_CHANGED")
    return RunProvenance(SELECTION_SOURCE_HEAD, head, sources, tuple(working),
                         _runtime_identity(), sys.executable, sys.dont_write_bytecode)


def _recheck_provenance(receipt, provenance):
    _need(capture_run_provenance(receipt) == provenance, "SOURCE_CHANGED_DURING_RUN")
    return provenance


def build_selected_work_plan(receipt, run_id):
    """Pure own-corpus validation; no board generation or corpus search."""
    _need(type(receipt) is AcceptedSelectionReceipt, "ACCEPTED_RECEIPT_REQUIRED")
    AcceptedSelectionReceipt.__post_init__(receipt)
    workload = receipt.workload
    boards = tuple(synthetic_board_identity(index) for index in workload.selection.ordered_indices)
    plan = execution.make_work_plan(boards, protocol_seed=workload.selection.protocol_seed,
                                    run_id=run_id, runtime=_runtime_identity())
    execution.revalidate_work_plan(plan)
    return readiness.validate_synthetic_work_plan(plan, workload)
# RECEIPT_PROVENANCE_END


# R0A_BEGIN
_R0A_REFERENCE_COMPONENTS = (
    ("K", operational.R0Component.K_CONTROL),
    ("D", operational.R0Component.DETERMINISM),
    ("O_K_SETUP", operational.R0Component.ORACLE_K_BIND),
    ("O_D_SETUP", operational.R0Component.ORACLE_D_REPEAT),
)
_R0A_OBSERVATION_FIELDS = (
    ("max_worker_memory_bytes", "worker_memory"),
    ("max_decision_wall_ns", "decision_wall"),
    ("max_arm_wall_ns", "arm_wall"),
    ("max_shadow_wall_ns", "shadow_wall"),
    ("max_physical_inputs", "physical_inputs"),
)
_R0A_MAXIMA = (
    "max_worker_memory_bytes", "max_coordinator_memory_bytes", "max_combined_memory_bytes",
    "max_decision_wall_ns", "max_arm_wall_ns", "max_case_wall_ns", "max_shadow_wall_ns",
    "max_physical_inputs",
)
_R0A_COMPLETENESS = ("watchdogs_complete", "resources_complete", "cleanup_complete")


def _r0a_work(plan, envelope, work):
    """Authenticate supplied rehearsal identities without generating any board."""
    _need(type(plan) is readiness.R0APlan, "R0A_PLAN_REQUIRED")
    readiness.R0APlan.__post_init__(plan)
    _need(type(envelope) is operational.OperatingEnvelope, "R0A_ENVELOPE_REQUIRED")
    operational.OperatingEnvelope.__post_init__(envelope)
    _need(type(work) is tuple and len(work) == len(plan.ordered_indices), "R0A_WORK_COVERAGE")
    for position, (item, index) in enumerate(zip(work, plan.ordered_indices)):
        _need(type(item) is operational.R0Work, "R0A_WORK_REQUIRED")
        operational.R0Work.__post_init__(item)
        _need((item.position, item.board.game_index, item.protocol_seed)
              == (position, index, plan.protocol_seed), "R0A_WORK_IDENTITY")
        _need((item.run_id, item.runtime) == (work[0].run_id, work[0].runtime),
              "R0A_WORK_IDENTITY")
    return work


def _r0a_component_containment(component):
    observations = tuple(observation for unit in component.units for observation in unit.observations)
    setup = component.setup_measurements
    maxima = {name: max(getattr(value, field) for value in observations)
              for name, field in _R0A_OBSERVATION_FIELDS}
    maxima.update(
        max_coordinator_memory_bytes=component.coordinator_memory_bytes,
        max_combined_memory_bytes=component.combined_memory_bytes,
        max_case_wall_ns=max(unit.max_case_wall_ns for unit in component.units),
        max_payload_bytes=max(unit.max_payload_bytes for unit in component.units),
        launcher_wall_ns=component.complete_wall_ns,
    )
    complete = {name: all(getattr(value, name) for value in observations)
                and all(getattr(value, name) for value in setup) for name in _R0A_COMPLETENESS}
    # The accepted return boundary has persisted, read back and closed every
    # target archive. Setup additionally carries its independent explicit flag.
    readback = all(value.readback_complete for value in setup)
    return readiness.RouteContainment(component.component.value, **maxima, **complete,
        progress_complete=all(unit.status is records.AuditStatus.PASS for unit in component.units)
                          and all(value.progress_complete for value in setup),
        readback_complete=readback)


def _r0a_setup_containment(component):
    """Aggregate disjoint setup waves; no target/parent peak is a setup fact."""
    setup = component.setup_measurements
    _need(bool(setup), "R0A_SETUP_REQUIRED")
    maxima = {name: max(getattr(value, name) for value in setup)
              for name in _R0A_MAXIMA + ("max_payload_bytes",)}
    complete = {name: all(getattr(value, name) for value in setup)
                for name in _R0A_COMPLETENESS + ("progress_complete", "readback_complete")}
    return readiness.RouteContainment(setup[0].route, **maxima,
        launcher_wall_ns=component.setup_wall_ns, **complete)


def adapt_r0a_concurrency(plan, envelope, work, components, progress_traces):
    """Adapt accepted, complete operational facts without reattributing walls.

    Inputs retain all six original measurements and their actual progress traces.
    Failed raw evidence remains owned by the launcher and cannot become a
    readiness input. No source authentication, generation or execution occurs.
    """
    _r0a_work(plan, envelope, work)
    kinds = tuple(operational.R0Component)
    _need(type(components) is tuple and len(components) == len(kinds), "R0A_COMPONENT_COVERAGE")
    _need(type(progress_traces) is tuple and len(progress_traces) == len(kinds), "R0A_PROGRESS_COVERAGE")
    by_kind = {}
    for kind, component, trace in zip(kinds, components, progress_traces):
        _need(type(component) is operational.R0ComponentMeasurement, "R0A_COMPONENT_REQUIRED")
        operational.R0ComponentMeasurement.__post_init__(component)
        _need(component.component is kind and component.concurrency == envelope.concurrency,
              "R0A_COMPONENT_IDENTITY")
        _need(tuple(unit.work for unit in component.units) == work, "R0A_COMPONENT_WORK_IDENTITY")
        _need(type(trace) is tuple and len(trace) == len(work), "R0A_PROGRESS_INCOMPLETE")
        has_setup = kind in dict(_R0A_REFERENCE_COMPONENTS).values()
        for position, (unit, progress) in enumerate(zip(component.units, trace)):
            _need(type(progress) is tuple and len(progress) == 3, "R0A_PROGRESS_SHAPE")
            observed, done, total = progress
            _integer(done, 1)
            _integer(total, 1)
            _need(type(observed) is operational.R0UnitMeasurement and observed == unit
                  and (done, total) == (position + 1, len(work)), "R0A_PROGRESS_IDENTITY")
            _need(unit.status is records.AuditStatus.PASS and not unit.reasons,
                  "R0A_COMPONENT_INCOMPLETE")
            _need(len(unit.observations) == (2 if has_setup else 1), "R0A_OBSERVATION_COVERAGE")
            _need(all(all(getattr(value, name) for name in _R0A_COMPLETENESS)
                      for value in unit.observations), "R0A_OBSERVATION_INCOMPLETE")
            _need(all(value.coordinator_memory <= component.coordinator_memory_bytes
                      and value.combined_memory <= component.combined_memory_bytes
                      for value in unit.observations), "R0A_COMPONENT_MEMORY_OMITTED")
            _need(kind is not operational.R0Component.ORACLE_K_BIND
                  or bool(unit.observations[-1].prior_binding_intervals), "R0A_BINDING_OBSERVATION_MISSING")
            if not has_setup:
                _need(unit.setup_wall_ns == unit.setup_bytes == unit.reference_bytes == 0,
                      "R0A_UNEXPECTED_SETUP")
        for setup in component.setup_measurements:
            _need(setup.completed_units == len(setup.positions)
                  and all(getattr(setup, name) for name in _R0A_COMPLETENESS
                          + ("progress_complete", "readback_complete")), "R0A_SETUP_INCOMPLETE")
            for receipt, observation, payload in zip(setup.receipts, setup.observations, setup.payload_bytes):
                unit = component.units[receipt.position]
                _need(receipt.reason == "ADMITTED" and observation == unit.observations[0]
                      and receipt.elapsed_ns == unit.setup_wall_ns
                      and payload <= unit.max_payload_bytes, "R0A_SETUP_UNIT_IDENTITY")
        by_kind[kind] = component

    def measured(kind, cls):
        component = by_kind[kind]
        completed = sum(unit.status is records.AuditStatus.PASS for unit in component.units)
        if cls is readiness.WallRouteMeasurement:
            _need(all(unit.durable_bytes == 0 for unit in component.units), "R0A_BIND_HAS_NO_BYTE_FAMILY")
            return cls(component.wall_ns, completed)
        return cls(component.wall_ns, sum(unit.durable_bytes for unit in component.units),
                   max(unit.durable_bytes for unit in component.units), completed)

    references = tuple(readiness.ReferenceMeasurement(route,
        sum(unit.reference_bytes for unit in by_kind[kind].units),
        max(unit.reference_bytes for unit in by_kind[kind].units),
        sum(value.completed_units for value in by_kind[kind].setup_measurements))
        for route, kind in _R0A_REFERENCE_COMPONENTS)
    routes = {kind.value: _r0a_component_containment(component) for kind, component in by_kind.items()}
    for kind in (operational.R0Component.ORACLE_K_BIND, operational.R0Component.ORACLE_D_REPEAT):
        value = _r0a_setup_containment(by_kind[kind])
        routes[value.route] = value
    containment = tuple(routes[name] for name in readiness.CALIBRATION_ROUTES)
    return readiness.R0AConcurrencyMeasurement(
        concurrency=envelope.concurrency, plan=plan,
        primary=measured(operational.R0Component.PRIMARY, readiness.ComponentMeasurement),
        k_control=measured(operational.R0Component.K_CONTROL, readiness.ComponentMeasurement),
        determinism=measured(operational.R0Component.DETERMINISM, readiness.ComponentMeasurement),
        oracle_primary=measured(operational.R0Component.ORACLE_B, readiness.OracleMeasurement),
        oracle_k_bind=measured(operational.R0Component.ORACLE_K_BIND, readiness.WallRouteMeasurement),
        oracle_d_repeat=measured(operational.R0Component.ORACLE_D_REPEAT, readiness.OracleMeasurement),
        references=references, containment=containment,
        wall_accounting=readiness.WallAccounting.CONSERVATIVE_STANDALONE,
        byte_accounting=readiness.ByteAccounting.NON_OVERLAPPING, envelope=envelope,
        **{name: max(getattr(value, name) for value in containment) for name in _R0A_MAXIMA},
        **{name: all(getattr(value, name) for value in containment)
           for name in _R0A_COMPLETENESS + ("progress_complete",)})


def _measure_r0a(plan, work_by_concurrency, envelopes, root, *, measure=operational.measure_r0_component):
    """Private orchestration seam; the public launcher owns authorization.

    Return readiness inputs together with every raw measurement and progress
    trace, so evidence publication can retain and independently adapt them.
    """
    _need(type(work_by_concurrency) is tuple and type(envelopes) is tuple
          and len(work_by_concurrency) == len(envelopes) == 3, "R0A_CONCURRENCY_COVERAGE")
    for concurrency, work, envelope in zip(identity.R0_A_CONCURRENCY_CANDIDATES,
                                           work_by_concurrency, envelopes):
        _r0a_work(plan, envelope, work)
        _need(envelope.concurrency == concurrency, "R0A_CONCURRENCY_ORDER")
        _need(tuple((value.board, value.protocol_seed, value.runtime) for value in work)
              == tuple((value.board, value.protocol_seed, value.runtime)
                       for value in work_by_concurrency[0]), "R0A_CROSS_CONCURRENCY_IDENTITY")
    _need(len({work[0].run_id for work in work_by_concurrency}) == 3, "R0A_DISTINCT_RUN_IDS_REQUIRED")
    _need(callable(measure), "R0A_MEASUREMENT_CALLABLE")
    root = Path(root)
    root.mkdir()
    values, raw, traces = [], [], []
    for work, envelope in zip(work_by_concurrency, envelopes):
        directory = root / ("c" + str(envelope.concurrency))
        directory.mkdir()
        components, progress_traces = [], []
        for kind in operational.R0Component:
            progress = []
            def observe(unit, done, total):
                progress.append((unit, done, total))
            components.append(measure(work, kind, directory / kind.value, envelope, progress=observe))
            progress_traces.append(tuple(progress))
        components, progress_traces = tuple(components), tuple(progress_traces)
        values.append(adapt_r0a_concurrency(plan, envelope, work, components, progress_traces))
        raw.append(components)
        traces.append(progress_traces)
    return readiness.validate_r0a_measurements(tuple(values)), tuple(raw), tuple(traces)
# R0A_END


# SYNTHETIC_BEGIN
_SYNTHETIC_FAMILIES = tuple(field.name for field in fields(readiness.ComponentSizes))
_SYNTHETIC_LABEL = "SYNTHETIC_NON_EVIDENCE"


def synthetic_board_identity(index):
    """Public schema identity only: no indexed board or answer layout exists."""
    _integer(index)
    return records.BoardIdentity(index, "UNMATERIALIZED_SYNTHETIC_R0B:" + str(index),
        2, 1, 0, (0, 0), "SYNTHETIC_NON_BOARD", "R0B_SCHEMA_FIXTURE")


def reference_board_identity(index):
    """Explicit engine-counterfactual public scaffold; never a benchmark board."""
    _integer(index)
    return records.BoardIdentity(index, "UNMATERIALIZED_SYNTHETIC_REFERENCE_R0B:" + str(index),
        30, 16, 0, (0, 0), "SYNTHETIC_REFERENCE_NON_BOARD", "R0B_REFERENCE_30X16_SCHEMA_FIXTURE")


def _known_synthetic_board(board):
    return type(board) is records.BoardIdentity and board in (
        synthetic_board_identity(board.game_index), reference_board_identity(board.game_index))


def _synthetic_projection(work, kind, *, repeat=False, exact=False):
    from stage3_physical import action_cost, load_timing_table
    arm = execution._arm(work, kind, repeat=repeat)
    table, origin, target = load_timing_table(), (0, 0), (1, 0)
    first, second = action_cost(table, origin, origin), action_cost(table, origin, target)
    physical = (
        records.PhysicalInputRecord(0, records.Action.OPEN, origin, origin,
                                    first, first, records.Status.PLAYING),
        records.PhysicalInputRecord(1, records.Action.OPEN, target, origin,
                                    second, first + second, records.Status.WON))
    public = tuple(records.PublicEffectRecord(i,
        (records.PublicCellChange(cell, "HIDDEN", "CLUE_0"),), records.Status.PLAYING, status)
        for i, cell, status in ((0, origin, records.Status.PLAYING), (1, target, records.Status.WON)))
    initial = records.ActionDecisionRecord(arm, 0,
        "CONTROL_INITIAL_OPEN" if kind is records.Arm.CONTROL else "POLICY_INITIAL_OPEN",
        "INITIAL", records.Action.OPEN, origin, (), None, None, (), (), (), ())
    if kind is records.Arm.CONTROL:
        selected = records.ActionDecisionRecord(arm, 1, "local_deterministic", "local_deterministic",
            records.Action.OPEN, target, (), None, None, (), (), (), ())
        scope = records.DecisionScope.CONTROL_PLAN_POSITION
    else:
        selected = records.ActionDecisionRecord(arm, 1, "DIRECT_SAFE_OPEN",
            "EXACT_SAFE" if exact else "LOCAL_SAFE", records.Action.OPEN, target,
            ((records.Action.OPEN, target),), second, 1, (), (target,), (), ())
        scope = records.DecisionScope.K_ANALYZE_DECISION_THROUGH_SELECT_POLICY
    return game.GameProjection(arm, records.Outcome.WIN, physical, public,
        (records.TerminalEffectRecord(1, (), records.Status.WON),),
        (records.DecisionSpanRecord(1, scope, 1),), (), (), (), (initial, selected),
        first + second, 1, True, True, True, ())


def _synthetic_reference(projection, constraint_copies=1):
    v1 = records.KControlV1Decision(records.Action.OPEN, (1, 0), "LOCAL_DETERMINISTIC",
        records.Action.OPEN, (1, 0), (((0, 0), 0, ((1, 0),)),) * constraint_copies,
        ((1, 0),), (), None, (), (), (), (), None, None)
    return tuple(records.KControlMaintenanceRecord(projection.arm, physical,
        ((-2, -2),) if i == 0 else ((0, -2),), projection.public_effects[i],
        None if i == 0 else projection.terminal_effects[0], None if i == 0 else v1, None,
        tuple((name, None if i == 0 and name == "v1_plan_position_ns" else 1)
              for name in execution._TIMINGS), (), (), None, None, None, "REFERENCE")
        for i, physical in enumerate(projection.physical_inputs))


def _synthetic_k_actual(work, reference):
    arm = execution._arm(work, records.Arm.K_CONTROL)
    accounting = records.KControlAccounting((), ((1, 0),), (), (), ((1, 0),), 0,
        (((0, 0), 0, (), ((1, 0),), 0),))
    decision = records.KControlShadowDecision(((0, -2),), 0, accounting, accounting,
        (), ((1, 0),), ((1, 0),), (), ((1, 0),), (), None, None, "NOT_REACHED",
        accounting, (), "LOCAL_SAFE", ((1, 0),), None)
    initial = records.KControlShadowState(True, (), None, None, None, False, True)
    current = records.KControlShadowState(True, (), decision, None, 1, True, True)
    final = records.KControlShadowState(True, (), None, None, 1, False, True)
    soundness = (("classification", "NO_DISCREPANCY"), ("boundary", 1),
        ("implicated_boundary", None), ("safe_cells", ((1, 0),)), ("detail", _SYNTHETIC_LABEL))
    return (replace(reference[0], arm=arm, shadow=initial, classification="NOT_REACHED"),
            replace(reference[1], arm=arm, shadow=current, soundness=soundness,
                    final_shadow=final, classification="PASS"))


def _synthetic_oracle_rows(padding=0):
    # These detached premises exercise codec/joins; no exact kernel is invoked.
    from experiments import program_k_oracles
    observation, target = ((0, -2),), ((1, 0),)
    snapshot = records.OracleBExactSnapshot(target, target, (), 1, (((1, 0), 0),),
        target, (), Fraction(0), target, _SYNTHETIC_LABEL + "x" * padding,
        _SYNTHETIC_LABEL, observation)
    digest = records.oracle_b_snapshot_digest(snapshot)
    input_digest = program_k_oracles.oracle_b_input_digest(observation, 0, frozenset())
    return tuple(records.OracleBAuditRecord(1, phase, (), observation, (), input_digest,
        digest, digest, records.AuditStatus.PASS, (), snapshot, snapshot) for phase in ("D", "E"))


def _synthetic_children(projection, selected, oracle_bytes, prefix=""):
    oracle = _synthetic_oracle_rows() if selected and oracle_bytes else ()
    values = {prefix + "certificate_audits": (),
        prefix + "oracle_b_audits": tuple(records.encode(v) for v in oracle),
        prefix + "oracle_b_coverage": (records.encode(records.OracleBCoverageRecord(
            projection.arm, selected, tuple((v.action_ordinal, v.phase) for v in oracle))),),
        prefix + "evaluators": tuple(records.encode(records.EvaluatorRecord(projection.arm, category,
            ((1, 0),) if category is records.AssertionCategory.CERTAINTY_OPEN else (),
            records.EvaluationStatus.PASS if category is records.AssertionCategory.CERTAINTY_OPEN
            else records.EvaluationStatus.NOT_EVALUATED, _SYNTHETIC_LABEL, _SYNTHETIC_LABEL))
            for category in records.AssertionCategory)}
    return values


def _synthetic_operation(bundle, elapsed_ns=0, samples=()):
    receipt = operational.UnitReceipt(bundle.work_position, bundle.kind, bundle.status,
                                     "SYNTHETIC_MATERIALIZED", elapsed_ns, 0)
    return operational._OperationResult(receipt, bundle, samples)


def synthetic_bundle_family_bytes(bundle):
    """Exact durable attribution with accepted position/rank/key/TAB/LF framing."""
    execution.WorkerBundle.__post_init__(bundle)
    operation = _synthetic_operation(bundle)
    if bundle.kind is execution.WorkerKind.PRIMARY:
        result = [("primary", operational._r0_attributable_bytes(operation, operational.R0Component.PRIMARY))]
        if "control_maintenance" in dict(bundle.streams):
            result.append(("reference", operational._bundle_stream_bytes(operation, {"control_maintenance"})))
        coverage = records.decode(dict(bundle.streams)["oracle_b_coverage"][0])
        if coverage.selected:
            result.append(("oracle_primary", operational._r0_attributable_bytes(operation,
                operational.R0Component.ORACLE_B)))
    elif bundle.kind is execution.WorkerKind.DETERMINISM:
        result = [("determinism", operational._r0_attributable_bytes(operation,
            operational.R0Component.DETERMINISM))]
        coverage = records.decode(dict(bundle.streams)["repeat_oracle_b_coverage"][0])
        if coverage.selected:
            result.append(("oracle_repeat", operational._r0_attributable_bytes(operation,
                operational.R0Component.ORACLE_D_REPEAT)))
    else:
        result = [("k_control", operational._r0_attributable_bytes(operation,
            operational.R0Component.K_CONTROL))]
    _need(sum(size for _, size in result) == operational._bundle_stream_bytes(operation),
          "SYNTHETIC_BYTE_PARTITION")
    return tuple(result)


def _synthetic_finish_bundle(work, kind, streams, headers, max_payload_bytes):
    bundle = execution._bundle(work, kind, streams, headers, records.AuditStatus.PASS, ())
    execution.revalidate_bundle(bundle, work, kind, max_payload_bytes=max_payload_bytes)
    _need(sum(size for _, size in synthetic_bundle_family_bytes(bundle)) <= max_payload_bytes,
          "SYNTHETIC_DURABLE_PAYLOAD_CAP")
    return bundle


def build_synthetic_bundle(work, kind, sizes, primary=None, *, max_payload_bytes):
    """Build one bounded schema-valid non-board unit without a worker or solver.

    Synthetic detail text and redundant identical public constraints provide
    byte load within existing I1 fields. Every copied reference remains exact.
    """
    execution.BoardWork.__post_init__(work)
    _need(work.board == synthetic_board_identity(work.board.game_index), "SYNTHETIC_NON_BOARD_IDENTITY_REQUIRED")
    _need(type(kind) is execution.WorkerKind and kind in operational._kinds(work), "SYNTHETIC_KIND_NOT_SCHEDULED")
    _need(type(sizes) is readiness.ComponentSizes, "SYNTHETIC_SIZING_REQUIRED")
    readiness.ComponentSizes.__post_init__(sizes)
    _integer(max_payload_bytes, 1)
    present = (("primary",) + (("reference",) if work.k_control_selected or work.determinism_selected else ())
               + (("oracle_primary",) if work.oracle_b_selected else ()) if kind is execution.WorkerKind.PRIMARY
               else ("determinism",) + (("oracle_repeat",) if work.oracle_b_selected else ())
               if kind is execution.WorkerKind.DETERMINISM else ("k_control",))
    _need(sum(getattr(sizes, name) for name in present) <= max_payload_bytes, "SYNTHETIC_MINIMUM_PAYLOAD_CAP")
    streams, headers = {}, []
    if kind is execution.WorkerKind.PRIMARY:
        _need(primary is None, "SYNTHETIC_PRIMARY_HAS_PRIOR")
        projections = tuple(_synthetic_projection(work, arm,
            exact=bool(sizes.oracle_primary or sizes.oracle_repeat)) for arm in (records.Arm.CONTROL, records.Arm.K_P0))
        for projection, role in zip(projections, ("control", "kp0")):
            header, values = execution._projection_streams(projection, role)
            headers.append(header)
            streams.update(values)
        streams.update(_synthetic_children(projections[1], work.oracle_b_selected, sizes.oracle_primary))
        streams["pairs"] = (records.encode(game.pair_projections(*projections).pair),)
        if work.k_control_selected or work.determinism_selected:
            reference = _synthetic_reference(projections[0])
            streams["control_maintenance"] = tuple(records.encode(v) for v in reference)
            # A redundant identical constraint does not alter its logical premise.
            def reference_size(values):
                return sum(operational._EvidenceSink._size((work.position, 0, i), records.encode(v))
                           for i, v in enumerate(values))
            current = reference_size(reference)
            if current < sizes.reference:
                step = reference_size(_synthetic_reference(projections[0], 2)) - current
                copies = 1 + (sizes.reference - current + step - 1) // step
                streams["control_maintenance"] = tuple(records.encode(v)
                    for v in _synthetic_reference(projections[0], copies))
    else:
        _need(type(primary) is execution.WorkerBundle, "SYNTHETIC_PRIOR_REQUIRED")
        execution.revalidate_bundle(primary, work, execution.WorkerKind.PRIMARY, max_payload_bytes=max_payload_bytes)
        first_streams = dict(primary.streams)
        reference = tuple(records.decode(v) for v in first_streams["control_maintenance"])
        if kind is execution.WorkerKind.K_CONTROL:
            actual = _synthetic_k_actual(work, reference)
            status, reasons = execution.compare_k_control(reference, actual)
            _need(status is records.AuditStatus.PASS and not reasons, "SYNTHETIC_K_CONTROL_MISMATCH")
            streams = {"control_maintenance": first_streams["control_maintenance"],
                "kcontrol_arms": (records.encode(execution._arm(work, records.Arm.K_CONTROL)),),
                "kcontrol_maintenance": tuple(records.encode(v) for v in actual)}
        else:
            first = tuple(execution.restore_projection(primary, role) for role in ("control", "kp0"))
            streams = {name: values for name, values in primary.streams
                       if name.startswith("control_") or name.startswith("kp0_")}
            headers.extend(primary.projection_headers)
            repeated = tuple(_synthetic_projection(work, arm, repeat=True,
                exact=bool(sizes.oracle_primary or sizes.oracle_repeat)) for arm in (records.Arm.CONTROL, records.Arm.K_P0))
            for projection, role in zip(repeated, ("repeat_control", "repeat_kp0")):
                header, values = execution._projection_streams(projection, role)
                headers.append(header)
                streams.update(values)
            repeated_reference = tuple(replace(v, arm=repeated[0].arm) for v in reference)
            streams["repeat_control_maintenance"] = tuple(records.encode(v) for v in repeated_reference)
            streams.update(_synthetic_children(repeated[1], work.oracle_b_selected, sizes.oracle_repeat, "repeat_"))
            streams["control_determinism"] = (records.encode(execution._control_determinism(first[0], repeated[0],
                first_streams["control_maintenance"], streams["repeat_control_maintenance"])),)
            streams["kp0_determinism"] = (records.encode(audit.determinism_record(
                audit.compare_determinism(first[1], repeated[1], selected=True))),)
    # Attribution is measured through the same accepted durable-row helpers used
    # for R0-A. Only the relevant family's own existing field is enlarged.
    bundle = _synthetic_finish_bundle(work, kind, streams, headers, max_payload_bytes)
    for family, measured in synthetic_bundle_family_bytes(bundle):
        deficit = getattr(sizes, family) - measured
        if deficit <= 0 or family == "reference":
            continue
        if family in ("primary", "determinism"):
            name = "evaluators" if family == "primary" else "repeat_evaluators"
            values = list(streams[name])
            item = records.decode(values[0])
            values[0] = records.encode(replace(item, detail=item.detail + "x" * deficit))
            streams[name] = tuple(values)
        elif family == "k_control":
            values = list(streams["kcontrol_maintenance"])
            item = records.decode(values[-1])
            soundness = tuple((name, value + "x" * deficit if name == "detail" else value)
                              for name, value in item.soundness)
            values[-1] = records.encode(replace(item, soundness=soundness))
            streams["kcontrol_maintenance"] = tuple(values)
        else:
            name = "oracle_b_audits" if family == "oracle_primary" else "repeat_oracle_b_audits"
            # Two phases, each with equal expected/actual snapshot text.
            streams[name] = tuple(records.encode(v) for v in _synthetic_oracle_rows((deficit + 3) // 4))
        bundle = _synthetic_finish_bundle(work, kind, streams, headers, max_payload_bytes)
    _need(all(size >= getattr(sizes, name) for name, size in synthetic_bundle_family_bytes(bundle)),
          "SYNTHETIC_PAYLOAD_UNDERSIZED")
    if primary is not None:
        # Bind copied first-run premises using the accepted lower validator.
        class PayloadCap:
            pass
        cap = PayloadCap()
        cap.max_payload_bytes = max_payload_bytes
        operational._bind_prior_bundle(bundle, execution.encode_bundle(primary), work, kind, cap)
    return bundle


# Separate in-memory V2 foundation. The historical builder/materializer below
# retains its V1 durable attribution and never invokes this constructor.
_TEXT_FAMILIES = (
    ("primary", execution.WorkerKind.PRIMARY, "evaluators", 0, 1),
    ("k_control", execution.WorkerKind.K_CONTROL, "kcontrol_maintenance", -1, 1),
    ("oracle_primary", execution.WorkerKind.PRIMARY, "oracle_b_audits", None, 4),
    ("oracle_repeat", execution.WorkerKind.DETERMINISM, "repeat_oracle_b_audits", None, 4),
    ("determinism", execution.WorkerKind.DETERMINISM, "repeat_evaluators", 0, 1),
)


def _text_spec(family):
    _need(type(family) is str, "SYNTHETIC_TEXT_FAMILY_REQUIRED")
    for family_id, spec in enumerate(_TEXT_FAMILIES):
        if spec[0] == family:
            return family_id, spec
    raise HarnessError("SYNTHETIC_TEXT_FAMILY_REQUIRED")


def _text_check(check):
    _need(check is None or callable(check), "SYNTHETIC_TEXT_CHECK_REQUIRED")
    if check is not None:
        check()


def _text_entropy(family, position, h, *, _check=None):
    family_id, spec = _text_spec(family)
    _need(type(position) is int and 0 <= position < 10_000, "SYNTHETIC_TEXT_POSITION_DOMAIN")
    _need(type(h) is int and 0 <= h <= physical.MAX_PAYLOAD_BYTES, "SYNTHETIC_TEXT_H_DOMAIN")
    rank = execution._wb02_rank(spec[1])
    chunks = []
    for block_index, offset in enumerate(range(0, h, 49_152)):
        _text_check(_check)
        domain = (b"PROGRAM_K_R0B_TEXT_FILL_V1\0" + bytes((family_id, rank))
                  + position.to_bytes(4, "big") + block_index.to_bytes(8, "big"))
        raw = shake_256(domain).digest(49_152)[:min(49_152, h - offset)]
        chunks.append(base64.b64encode(raw).decode("ascii"))
        _text_check(_check)
    _text_check(_check)
    result = "".join(chunks)
    _text_check(_check)
    return result


def _text_filler(family, position, ell, h, *, _check=None):
    _need(type(ell) is int and 0 <= ell <= physical.MAX_PAYLOAD_BYTES, "SYNTHETIC_TEXT_ELL_DOMAIN")
    pieces = ["SYNTHETIC_NON_EVIDENCE|L:"]
    for offset in range(0, ell, 65_536):
        _text_check(_check)
        pieces.append("x" * min(65_536, ell - offset))
        _text_check(_check)
    pieces.extend(("|H:", _text_entropy(family, position, h, _check=_check)))
    _text_check(_check)
    result = "".join(pieces)
    _text_check(_check)
    return result


def _text_lengths(logical_target, l0, m, h):
    for value in (logical_target, l0, h):
        _integer(value)
    _need(type(m) is int and m in (1, 4), "SYNTHETIC_TEXT_MULTIPLICITY")
    q = (max(0, logical_target - l0) + m - 1) // m
    b = 4 * ((h + 2) // 3)
    return q, b, max(0, q - b)


@dataclass(frozen=True, slots=True)
class TextTrial:
    """V2 constructor observations only; None means a preceding trial step failed."""

    ordinal: int
    h: int
    ell: int
    actual_physical_bytes: int | None
    actual_logical_bytes: int | None
    physical_margin: int | None
    logical_margin: int | None
    lsum: int | None
    llegacy: int | None
    sunit: int | None
    wnew: int | None
    eligible: bool
    rejection_reason: str | None


@dataclass(frozen=True, slots=True)
class TextConstructionResult:
    """Evaluated-set minimum, not profile qualification or materialization authority."""

    family: str
    selected_bundle: execution.WorkerBundle | None
    selected_wire: bytes | None
    selected_trial: TextTrial | None
    trials: tuple
    rejection_reason: str | None
    zero_oracle: bool = False


def _next_text_h(trials, h_hi, physical_target):
    tried = {trial.h for trial in trials}
    if not tried:
        return 0
    if h_hi not in tried:
        return h_hi
    ordered = sorted((trial for trial in trials if trial.actual_physical_bytes is not None),
                     key=lambda trial: trial.h)
    pairs = [(abs(a.actual_physical_bytes - physical_target)
              + abs(b.actual_physical_bytes - physical_target), a.h, b.h, a, b)
             for i, a in enumerate(ordered) for b in ordered[i + 1:]
             if a.actual_physical_bytes != b.actual_physical_bytes]
    if pairs:
        _, _, _, a, b = min(pairs, key=lambda pair: pair[:3])
        u = a.h + ((physical_target - a.actual_physical_bytes) * (b.h - a.h)
                   // (b.actual_physical_bytes - a.actual_physical_bytes))
        if 0 <= u <= h_hi and u not in tried:
            return u
    endpoints = [-1] + sorted(tried) + [h_hi + 1]
    gaps = [(b - a - 1, a + 1, b - 1) for a, b in zip(endpoints, endpoints[1:]) if b - a > 1]
    if not gaps:
        return None
    _, low, high = min(gaps, key=lambda gap: (-gap[0], gap[1]))
    return (low + high) // 2


def _search_text_trials(h_hi, physical_target, evaluate, *, _check=None):
    _need(type(h_hi) is int and 0 <= h_hi <= physical.MAX_PAYLOAD_BYTES, "SYNTHETIC_TEXT_H_DOMAIN")
    _integer(physical_target, 1)
    _need(callable(evaluate), "SYNTHETIC_TEXT_EVALUATOR_REQUIRED")
    trials = []
    for ordinal in range(1, 9):
        h = _next_text_h(trials, h_hi, physical_target)
        if h is None:
            break
        _text_check(_check)
        trial = evaluate(h, ordinal)
        _text_check(_check)
        _need(type(trial) is TextTrial and trial.h == h and trial.ordinal == ordinal,
              "SYNTHETIC_TEXT_TRIAL_BINDING")
        trials.append(trial)
    eligible = [trial for trial in trials if trial.eligible]
    selected = min(eligible, key=lambda trial: (trial.actual_physical_bytes,
                   trial.actual_logical_bytes, trial.h)) if eligible else None
    return tuple(trials), selected


def _text_terminal_reason(trials):
    if any(trial.eligible for trial in trials):
        return None
    # Preserve window failure for the otherwise floor/cap/semantic-valid subset;
    # floor/cap failures in other trials remain individually recorded.
    if any(trial.rejection_reason == "SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT" for trial in trials):
        return "SYNTHETIC_TEXT_PHYSICAL_OVERSHOOT"
    return "SYNTHETIC_SIZING_SEARCH_EXHAUSTED"


def _mutate_text_bundle(bundle, family, text):
    _, (_, _, name, index, _) = _text_spec(family)
    streams = dict(bundle.streams)
    values = list(streams[name])
    indices = range(len(values)) if index is None else (index % len(values),)
    for i in indices:
        item = records.decode(values[i])
        if family in ("primary", "determinism"):
            mutated = replace(item, detail=text)
        elif family == "k_control":
            _need(sum(key == "detail" for key, _ in item.soundness) == 1,
                  "SYNTHETIC_TEXT_DETAIL_REQUIRED")
            mutated = replace(item, soundness=tuple((key, text if key == "detail" else value)
                                                   for key, value in item.soundness))
        else:
            _need(item.status is records.AuditStatus.PASS and item.expected == item.actual,
                  "SYNTHETIC_TEXT_ORACLE_PASS_REQUIRED")
            snapshot = replace(item.expected, shared_kernel_evidence=text)
            digest = records.oracle_b_snapshot_digest(snapshot)
            mutated = replace(item, expected=snapshot, actual=snapshot,
                              expected_digest=digest, actual_digest=digest)
        data = records.encode(mutated)
        _need(records.decode(data) == mutated, "SYNTHETIC_TEXT_CANONICAL_ROUNDTRIP")
        values[i] = data
    return replace(bundle, streams=tuple((stream, tuple(values) if stream == name else rows)
                                        for stream, rows in bundle.streams))


def _text_owned(family, name):
    if family == "primary":
        return name not in ("control_maintenance", "oracle_b_audits")
    if family == "determinism":
        return name != "repeat_oracle_b_audits"
    if family == "k_control":
        return True
    return name == ("oracle_b_audits" if family == "oracle_primary" else "repeat_oracle_b_audits")


def construct_text_family_v2(work, bundle, family, codec_profile_sha256, *, physical_target,
                             logical_target, max_payload_bytes, envelope,
                             prior_primary_wire=None, _check=None):
    """Bounded text-only search with invocation-local exact baseline-frame reuse.

    The caller's existing envelope is required solely by the fresh WB02 validator;
    it supplies no new time allowance. No files, profile admission or live path
    are touched. Callback/resource errors propagate, including after success.
    """
    _, (_, kind, stream_name, changed_index, multiplicity) = _text_spec(family)
    _need(type(work) is execution.BoardWork and type(bundle) is execution.WorkerBundle,
          "SYNTHETIC_TEXT_EXACT_INPUTS_REQUIRED")
    execution.BoardWork.__post_init__(work)
    execution.WorkerBundle.__post_init__(bundle)
    _need(0 <= work.position < 10_000, "SYNTHETIC_TEXT_POSITION_DOMAIN")
    _need(_known_synthetic_board(work.board), "SYNTHETIC_NON_BOARD_IDENTITY_REQUIRED")
    _need(bundle.kind is kind and kind in operational._kinds(work), "SYNTHETIC_TEXT_WORKER_FAMILY_MISMATCH")
    _need(type(codec_profile_sha256) is bytes and len(codec_profile_sha256) == 32,
          "WB02_PROFILE_IDENTITY_REQUIRED")
    _need(type(max_payload_bytes) is int and 0 < max_payload_bytes <= physical.MAX_PAYLOAD_BYTES,
          "SYNTHETIC_TEXT_PAYLOAD_CAP")
    operational._envelope(envelope)
    _need(envelope.max_payload_bytes == max_payload_bytes, "SYNTHETIC_TEXT_ENVELOPE_CAP_BINDING")
    readiness.evaluate_family_size(family, physical_target, logical_target, 0, 0)
    if kind is execution.WorkerKind.PRIMARY:
        _need(prior_primary_wire is None, "PRIMARY_PRIOR_BINDING")
    else:
        _need(type(prior_primary_wire) is bytes, "WB02_IMMUTABLE_PRIMARY_PRIOR_REQUIRED")
    _text_check(_check)
    # Fresh context performs semantic/prior admission of this invocation's
    # baseline; rows never become a caller-supplied authority token.
    baseline_wire = execution.encode_bundle_v2(bundle, codec_profile_sha256,
                                               max_payload_bytes=max_payload_bytes)
    baseline = operational._fresh_wb02_context(baseline_wire, work, kind, codec_profile_sha256,
                                              envelope, prior_primary_wire=prior_primary_wire)
    values = dict(bundle.streams).get(stream_name, ())
    if multiplicity == 4:
        _need(work.oracle_b_selected, "SYNTHETIC_TEXT_ORACLE_SELECTION_REQUIRED")
        if physical_target == logical_target == 0:
            _need(not values, "ZERO_ORACLE_REQUIRES_EXACT_ZERO")
            trial = TextTrial(0, 0, 0, 0, 0, 0, 0, baseline.logical_bytes,
                baseline.legacy_bundle_bytes, baseline.physical_frame_bytes,
                baseline.wb02_wire_bytes, True, None)
            _text_check(_check)
            return TextConstructionResult(family, bundle, baseline_wire, trial, (), None, True)
        _need(len(values) == 2 and tuple(records.decode(v).phase for v in values) == ("D", "E"),
              "SYNTHETIC_TEXT_TWO_ORACLE_PHASES_REQUIRED")
    _need(bool(values), "SYNTHETIC_TEXT_SURFACE_REQUIRED")
    fixed = _mutate_text_bundle(bundle, family, "SYNTHETIC_NON_EVIDENCE|L:|H:")
    l0 = sum(len(data) for name, rows in fixed.streams if _text_owned(family, name) for data in rows)
    q, _, _ = _text_lengths(logical_target, l0, multiplicity, 0)
    lsum0 = sum(len(data) for _, rows in fixed.streams for data in rows)
    legacy0 = execution.legacy_bundle_size(fixed)
    changed = dict(fixed.streams)[stream_name]
    indices = tuple(range(len(changed))) if changed_index is None else (changed_index % len(changed),)
    per_row = 2 if multiplicity == 4 else 1
    t_max = min((max_payload_bytes - lsum0) // multiplicity,
                (max_payload_bytes - legacy0) // multiplicity,
                *((max_payload_bytes - len(changed[i])) // per_row for i in indices))
    if t_max < q:
        _text_check(_check)
        return TextConstructionResult(family, None, None, None, (), "SYNTHETIC_LOGICAL_DOMAIN_EMPTY")
    h_hi = 3 * (t_max // 4)
    prior_legacy = None
    if prior_primary_wire is not None:
        prior_legacy = execution.encode_bundle(execution.decode_bundle_v2(
            prior_primary_wire, codec_profile_sha256, max_payload_bytes=max_payload_bytes))
    best = None

    def evaluate(h, ordinal):
        nonlocal best
        _, _, ell = _text_lengths(logical_target, l0, multiplicity, h)
        # Checks occur outside the ordinary trial-rejection catches, including
        # callbacks that raise the same ValueError subclasses as validators.
        text = _text_filler(family, work.position, ell, h, _check=_check)
        p = logical = lsum = legacy = sunit = wnew = None
        reason = None
        candidate = wire = None
        try:
            candidate = _mutate_text_bundle(fixed, family, text)
            logical = sum(len(data) for name, rows in candidate.streams
                          if _text_owned(family, name) for data in rows)
            lsum = sum(len(data) for _, rows in candidate.streams for data in rows)
            legacy = execution.legacy_bundle_size(candidate)
            if any(len(data) > max_payload_bytes for _, rows in candidate.streams for data in rows):
                reason = "SYNTHETIC_TEXT_LOGICAL_RECORD_CAP"
            elif lsum > max_payload_bytes:
                reason = "SYNTHETIC_TEXT_LSUM_CAP"
            elif legacy > max_payload_bytes:
                reason = "SYNTHETIC_TEXT_LLEGACY_CAP"
            if reason is None:
                execution.revalidate_bundle(candidate, work, kind, max_payload_bytes=max_payload_bytes)
                operational._bind_prior_bundle(candidate, prior_legacy, work, kind, envelope)
        except records.RecordError:
            reason = "SYNTHETIC_TEXT_CANONICAL_RECORD_FAILURE"
        except (execution.E2ExecutionError, operational.OperationalError, HarnessError):
            reason = "SYNTHETIC_TEXT_SEMANTIC_OR_PRIOR_FAILURE"
        if reason is None:
            try:
                rows = []
                logical_rows = (data for _, group in candidate.streams for data in group)
                for row, data in zip(baseline.rows, logical_rows):
                    if data == row.logical_bytes:
                        rows.append(row)
                    else:
                        _need(row.stream_name == stream_name and row.key[2] in indices,
                              "SYNTHETIC_TEXT_MUTATION_SCOPE")
                        frame = physical.encode_frame(data, row.key,
                            physical.context_for(row.stream_name, codec_profile_sha256),
                            max_payload_bytes=max_payload_bytes)
                        rows.append(execution.WB02Row(row.stream_name, row.key, data, frame, len(frame)))
                p = sum(row.frame_length for row in rows if _text_owned(family, row.stream_name))
                sunit = sum(row.frame_length for row in rows)
                groups = []
                cursor = 0
                for name, values in candidate.streams:
                    group_rows = rows[cursor:cursor + len(values)]
                    groups.append((name, len(values), sum(map(len, values)),
                                   sum(row.frame_length for row in group_rows)))
                    cursor += len(values)
                # The shared representation composer owns all metadata fields
                # and its exact fixed point, even when the wire cannot fit.
                _, _, wnew = execution._wb02_layout(candidate, codec_profile_sha256,
                                                    lsum, legacy, groups, sunit)
                if sunit > max_payload_bytes:
                    reason = "SYNTHETIC_TEXT_SUNIT_CAP"
                elif wnew > max_payload_bytes:
                    reason = "SYNTHETIC_TEXT_WNEW_CAP"
                else:
                    wire = execution._compose_bundle_v2_from_rows(candidate, codec_profile_sha256,
                        tuple(rows), max_payload_bytes=max_payload_bytes)
                    _need(len(wire) == wnew, "SYNTHETIC_TEXT_WIRE_SIZE_BINDING")
            except physical.PhysicalError:
                reason = "SYNTHETIC_TEXT_FRAME_FAILURE"
            except execution.E2ExecutionError:
                reason = "SYNTHETIC_TEXT_WIRE_FAILURE"
        if reason is None:
            policy = readiness.evaluate_family_size(family, physical_target, logical_target, p, logical)
            reason = policy.rejection_reason
        trial = TextTrial(ordinal, h, ell, p, logical,
            None if p is None else p - physical_target,
            None if logical is None else logical - logical_target,
            lsum, legacy, sunit, wnew, reason is None, reason)
        if trial.eligible and (best is None or (p, logical, h) < (
                best[0].actual_physical_bytes, best[0].actual_logical_bytes, best[0].h)):
            best = trial, candidate, wire
        return trial

    trials, selected = _search_text_trials(h_hi, physical_target, evaluate, _check=_check)
    if selected is None:
        return TextConstructionResult(family, None, None, None, trials, _text_terminal_reason(trials))
    trial, candidate, wire = best
    _need(trial == selected, "SYNTHETIC_TEXT_SELECTION_BINDING")
    _text_check(_check)
    final = operational._fresh_wb02_context(wire, work, kind, codec_profile_sha256, envelope,
                                           prior_primary_wire=prior_primary_wire)
    final_p = sum(row.frame_length for row in final.rows if _text_owned(family, row.stream_name))
    final_l = sum(len(row.logical_bytes) for row in final.rows if _text_owned(family, row.stream_name))
    _need(final.bundle == candidate and (final_p, final_l, final.logical_bytes, final.legacy_bundle_bytes,
          final.physical_frame_bytes, final.wb02_wire_bytes) ==
          (trial.actual_physical_bytes, trial.actual_logical_bytes, trial.lsum, trial.llegacy,
           trial.sunit, trial.wnew), "SYNTHETIC_TEXT_SELECTED_FACT_BINDING")
    _text_check(_check)
    return TextConstructionResult(family, candidate, wire, trial, trials, None)


_REFERENCE_Q_MAX = 2_581_110
_REFERENCE_TEXT = "SYNTHETIC_NON_EVIDENCE|L:|H:"


def _reference_catalog():
    target = (1, 0)
    return tuple(((x, y), 0, (target,) if max(abs(x - 1), y) == 1 else ())
                 for y in range(16) for x in range(30) if (x, y) != target)


def _reference_observation(initial=False):
    _need(type(initial) is bool, "REFERENCE_EXACT_INITIAL_FLAG")
    return tuple(tuple(-2 if initial or (x, y) == (1, 0) else 0 for x in range(30)) for y in range(16))


@dataclass(frozen=True, slots=True)
class ReferencePrefix:
    """Invocation-local packed indices and exact canonical added-length prefixes."""

    indices: bytes
    lengths: bytes

    def __post_init__(self):
        _need(type(self.indices) is bytes and type(self.lengths) is bytes
              and len(self.indices) % 2 == 0 and self.q <= _REFERENCE_Q_MAX
              and len(self.lengths) == 4 * (self.q + 1)
              and self.lengths[:4] == bytes(4), "REFERENCE_PACKED_PREFIX_SHAPE")

    @property
    def q(self):
        return len(self.indices) // 2

    def index(self, i):
        _need(type(i) is int and 0 <= i < self.q, "REFERENCE_PREFIX_INDEX")
        return struct.unpack_from(">H", self.indices, 2 * i)[0]

    def added_length(self, q):
        _need(type(q) is int and 0 <= q <= self.q, "REFERENCE_PREFIX_LENGTH_INDEX")
        return struct.unpack_from(">I", self.lengths, 4 * q)[0]


def _reference_prefix(q, *, _check=None):
    _need(type(q) is int and 0 <= q <= _REFERENCE_Q_MAX, "REFERENCE_Q_ABSOLUTE_BOUND")
    # The comma is part of every append to the already nonempty full catalog.
    deltas = tuple(1 + len(execution._json(entry)) for entry in _reference_catalog())
    indices, lengths = bytearray(2 * q), bytearray(4 * (q + 1))
    total = 0
    for start in range(0, q, 16):
        if start % 4_096 == 0:
            _text_check(_check)
        digest = sha256(b"PROGRAM_K_R0B_REFERENCE_REDUNDANCY_V1\0"
                        + (start // 16).to_bytes(8, "big")).digest()
        for offset, word in enumerate(struct.unpack(">16H", digest)):
            i = start + offset
            if i == q:
                break
            index = word % 479
            total += deltas[index]
            struct.pack_into(">H", indices, 2 * i, index)
            struct.pack_into(">I", lengths, 4 * (i + 1), total)
    _text_check(_check)
    result = ReferencePrefix(bytes(indices), bytes(lengths))
    _text_check(_check)
    return result


def _reference_constraints(prefix, q, *, _check=None):
    _need(type(prefix) is ReferencePrefix and type(q) is int and 0 <= q <= prefix.q,
          "REFERENCE_PREFIX_REQUIRED")
    catalog = _reference_catalog()
    # A q-sized collection is formed only for an actual candidate, never bounds.
    entries = list(catalog)
    for start in range(0, q, 4_096):
        _text_check(_check)
        entries.extend(catalog[prefix.index(i)] for i in range(start, min(start + 4_096, q)))
    _text_check(_check)
    result = tuple(entries)
    _text_check(_check)
    return result


def _reference_work(work):
    _need(type(work) is execution.BoardWork, "REFERENCE_EXACT_WORK_REQUIRED")
    execution.BoardWork.__post_init__(work)
    _need(0 <= work.position < 10_000 and work.board == reference_board_identity(work.board.game_index),
          "REFERENCE_NON_BOARD_IDENTITY_REQUIRED")
    _need(work.k_control_selected or work.determinism_selected, "REFERENCE_DEPENDENT_REQUIRED")


def _reference_projection(work, kind, *, repeat=False):
    from stage3_physical import action_cost, load_timing_table
    arm = execution._arm(work, kind, repeat=repeat)
    table, origin, target = load_timing_table(), (0, 0), (1, 0)
    first, second = action_cost(table, origin, origin), action_cost(table, origin, target)
    physical_rows = (
        records.PhysicalInputRecord(0, records.Action.OPEN, origin, origin, first, first, records.Status.PLAYING),
        records.PhysicalInputRecord(1, records.Action.OPEN, target, origin, second, first + second, records.Status.WON))
    public = (
        records.PublicEffectRecord(0, tuple(records.PublicCellChange(source, "HIDDEN", "CLUE_0")
            for source, _, _ in _reference_catalog()), records.Status.PLAYING, records.Status.PLAYING),
        records.PublicEffectRecord(1, (records.PublicCellChange(target, "HIDDEN", "CLUE_0"),),
                                   records.Status.PLAYING, records.Status.WON))
    initial = records.ActionDecisionRecord(arm, 0,
        "CONTROL_INITIAL_OPEN" if kind is records.Arm.CONTROL else "POLICY_INITIAL_OPEN",
        "INITIAL", records.Action.OPEN, origin, (), None, None, (), (), (), ())
    if kind is records.Arm.CONTROL:
        selected = records.ActionDecisionRecord(arm, 1, "local_deterministic", "local_deterministic",
            records.Action.OPEN, target, (), None, None, (), (), (), ())
        scope = records.DecisionScope.CONTROL_PLAN_POSITION
    else:
        selected = records.ActionDecisionRecord(arm, 1, "DIRECT_SAFE_OPEN",
            "EXACT_SAFE" if work.oracle_b_selected else "LOCAL_SAFE", records.Action.OPEN, target,
            ((records.Action.OPEN, target),), second, 1, (), (target,), (), ())
        scope = records.DecisionScope.K_ANALYZE_DECISION_THROUGH_SELECT_POLICY
    return game.GameProjection(arm, records.Outcome.WIN, physical_rows, public,
        (records.TerminalEffectRecord(1, (), records.Status.WON),),
        (records.DecisionSpanRecord(1, scope, 1),), (), (), (), (initial, selected),
        first + second, 1, True, True, True, ())


def _reference_maintenance(projection, constraints):
    decision = records.KControlV1Decision(records.Action.OPEN, (1, 0), "LOCAL_DETERMINISTIC",
        records.Action.OPEN, (1, 0), constraints, ((1, 0),), (), None, (), (), (), (), None, None)
    return tuple(records.KControlMaintenanceRecord(projection.arm, physical_row,
        _reference_observation(initial=i == 0), projection.public_effects[i],
        None if i == 0 else projection.terminal_effects[0], None if i == 0 else decision, None,
        tuple((name, None if i == 0 and name == "v1_plan_position_ns" else 1) for name in execution._TIMINGS),
        (), (), None, None, None, "REFERENCE") for i, physical_row in enumerate(projection.physical_inputs))


def _reference_k_actual(work, reference):
    target = ((1, 0),)
    catalog = tuple((source, 0, (), hidden, 0) for source, _, hidden in _reference_catalog())
    before, local_after, after = (records.KControlAccounting((), target, (), (), target, 0, catalog)
                                  for _ in range(3))
    decision = records.KControlShadowDecision(_reference_observation(), 0, before, local_after,
        (), target, target, (), target, (), None, None, "NOT_REACHED", after, (), "LOCAL_SAFE", target, None)
    initial = records.KControlShadowState(True, (), None, None, None, False, True)
    current = records.KControlShadowState(True, (), decision, None, 1, True, True)
    final = records.KControlShadowState(True, (), None, None, 1, False, True)
    arm = execution._arm(work, records.Arm.K_CONTROL)
    soundness = (("classification", "NO_DISCREPANCY"), ("boundary", 1),
        ("implicated_boundary", None), ("safe_cells", target), ("detail", _REFERENCE_TEXT))
    return (replace(reference[0], arm=arm, shadow=initial, classification="NOT_REACHED"),
            replace(reference[1], arm=arm, shadow=current, soundness=soundness,
                    final_shadow=final, classification="PASS"))


def _reference_children(projection, selected, prefix=""):
    from experiments import program_k_oracles
    target, observation = ((1, 0),), _reference_observation()
    oracle = ()
    if selected:
        snapshot = records.OracleBExactSnapshot(target, target, (), 1, (((1, 0), 0),), target,
            (), Fraction(0), target, _REFERENCE_TEXT, _SYNTHETIC_LABEL, observation)
        digest = records.oracle_b_snapshot_digest(snapshot)
        input_digest = program_k_oracles.oracle_b_input_digest(observation, 0, frozenset())
        oracle = tuple(records.OracleBAuditRecord(1, phase, (), observation, (), input_digest,
            digest, digest, records.AuditStatus.PASS, (), snapshot, snapshot) for phase in ("D", "E"))
    return {prefix + "certificate_audits": (),
        prefix + "oracle_b_audits": tuple(records.encode(value) for value in oracle),
        prefix + "oracle_b_coverage": (records.encode(records.OracleBCoverageRecord(
            projection.arm, selected, tuple((value.action_ordinal, value.phase) for value in oracle))),),
        prefix + "evaluators": tuple(records.encode(records.EvaluatorRecord(projection.arm, category,
            target if category is records.AssertionCategory.CERTAINTY_OPEN else (),
            records.EvaluationStatus.PASS if category is records.AssertionCategory.CERTAINTY_OPEN
            else records.EvaluationStatus.NOT_EVALUATED, _SYNTHETIC_LABEL, _REFERENCE_TEXT))
            for category in records.AssertionCategory)}


def _reference_bundles(work, prefix, q, *, _check=None):
    _reference_work(work)
    constraints = _reference_constraints(prefix, q, _check=_check)
    projections = tuple(_reference_projection(work, arm) for arm in (records.Arm.CONTROL, records.Arm.K_P0))
    reference = _reference_maintenance(projections[0], constraints)
    streams, headers = {}, []
    for projection, role in zip(projections, ("control", "kp0")):
        header, values = execution._projection_streams(projection, role)
        headers.append(header)
        streams.update(values)
    streams.update(_reference_children(projections[1], work.oracle_b_selected))
    streams["pairs"] = (records.encode(game.pair_projections(*projections).pair),)
    streams["control_maintenance"] = tuple(records.encode(value) for value in reference)
    primary = execution._bundle(work, execution.WorkerKind.PRIMARY, streams, headers, records.AuditStatus.PASS, ())
    bundles = [primary]
    for kind in operational._kinds(work)[1:]:
        _text_check(_check)
        if kind is execution.WorkerKind.K_CONTROL:
            actual = _reference_k_actual(work, reference)
            streams = {"control_maintenance": dict(primary.streams)["control_maintenance"],
                "kcontrol_arms": (records.encode(execution._arm(work, records.Arm.K_CONTROL)),),
                "kcontrol_maintenance": tuple(records.encode(value) for value in actual)}
            headers = []
        else:
            streams = {name: values for name, values in primary.streams
                       if name.startswith("control_") or name.startswith("kp0_")}
            headers = list(primary.projection_headers)
            repeated = tuple(_reference_projection(work, arm, repeat=True)
                             for arm in (records.Arm.CONTROL, records.Arm.K_P0))
            for projection, role in zip(repeated, ("repeat_control", "repeat_kp0")):
                header, values = execution._projection_streams(projection, role)
                headers.append(header)
                streams.update(values)
            streams["repeat_control_maintenance"] = tuple(records.encode(replace(value, arm=repeated[0].arm))
                                                          for value in reference)
            streams.update(_reference_children(repeated[1], work.oracle_b_selected, "repeat_"))
            streams["control_determinism"] = (records.encode(execution._control_determinism(
                projections[0], repeated[0], streams["control_maintenance"], streams["repeat_control_maintenance"])),)
            streams["kp0_determinism"] = (records.encode(audit.determinism_record(
                audit.compare_determinism(projections[1], repeated[1], selected=True))),)
        bundles.append(execution._bundle(work, kind, streams, headers, records.AuditStatus.PASS, ()))
        _text_check(_check)
    return tuple(bundles)


def _reference_candidate_bundles(work, baseline_bundles, prefix, q, *, _check=None):
    constraints = _reference_constraints(prefix, q, _check=_check)
    primary_streams = dict(baseline_bundles[0].streams)
    reference = records.decode(primary_streams["control_maintenance"][1])
    decision = replace(reference.v1_decision, constraints=constraints)
    changed_reference = records.encode(replace(reference, v1_decision=decision))
    copies = (primary_streams["control_maintenance"][0], changed_reference)
    result = []
    for baseline in baseline_bundles:
        _text_check(_check)
        streams = dict(baseline.streams)
        streams["control_maintenance"] = copies
        if baseline.kind is execution.WorkerKind.K_CONTROL:
            rows = streams["kcontrol_maintenance"]
            streams["kcontrol_maintenance"] = (rows[0], records.encode(replace(records.decode(rows[1]),
                                                                            v1_decision=decision)))
        elif baseline.kind is execution.WorkerKind.DETERMINISM:
            rows = streams["repeat_control_maintenance"]
            streams["repeat_control_maintenance"] = (rows[0], records.encode(replace(records.decode(rows[1]),
                                                                                   v1_decision=decision)))
            streams["control_determinism"] = (records.encode(execution._control_determinism(
                execution.restore_projection(baseline, "control"), execution.restore_projection(baseline, "repeat_control"),
                copies, streams["repeat_control_maintenance"])),)
        result.append(replace(baseline, streams=tuple((name, streams[name]) for name, _ in baseline.streams)))
        _text_check(_check)
    return tuple(result)


def _reference_text_families(bundle):
    names = dict(bundle.streams)
    if bundle.kind is execution.WorkerKind.PRIMARY:
        return ("primary",) + (("oracle_primary",) if names["oracle_b_audits"] else ())
    if bundle.kind is execution.WorkerKind.DETERMINISM:
        return ("determinism",) + (("oracle_repeat",) if names["repeat_oracle_b_audits"] else ())
    return ("k_control",)


def _reference_size_bases(bundles):
    bases = []
    for bundle in bundles:
        rows = tuple((len(data), int(index == 1 and name in (
            "control_maintenance", "repeat_control_maintenance", "kcontrol_maintenance")))
            for name, values in bundle.streams for index, data in enumerate(values))
        families = tuple((family, sum(len(data) for name, values in bundle.streams
                         if _text_owned(family, name) for data in values),
                         2 if family in ("k_control", "determinism") else 0)
                         for family in _reference_text_families(bundle))
        bases.append((bundle.kind, sum(length for length, _ in rows), execution.legacy_bundle_size(bundle),
                      rows, families))
    return tuple(bases)


def _reference_bases_fit(bases, targets, added, limit):
    for _, logical, legacy, rows, families in bases:
        copies = sum(coefficient for _, coefficient in rows)
        reserve = sum(max(0, getattr(targets.logical, family) - (size + coefficient * added))
                      for family, size, coefficient in families)
        if (logical + copies * added + reserve > limit or legacy + copies * added + reserve > limit
                or any(size + coefficient * added > limit for size, coefficient in rows)):
            return False
    return True


def _reference_expanded_fits(bundles, targets, added_bytes, max_payload_bytes):
    return _reference_bases_fit(_reference_size_bases(bundles), targets, added_bytes, max_payload_bytes)


def _reference_q_bounds(bundles, targets, prefix, max_payload_bytes):
    reference_l0 = sum(len(data) for data in dict(bundles[0].streams)["control_maintenance"])
    needed = max(0, targets.logical.reference - reference_l0)
    low, high = 0, prefix.q + 1
    while low < high:
        mid = (low + high) // 2
        if mid <= prefix.q and prefix.added_length(mid) >= needed:
            high = mid
        else:
            low = mid + 1
    q_lo = low
    bases = _reference_size_bases(bundles)
    if not _reference_bases_fit(bases, targets, 0, max_payload_bytes):
        return q_lo, None
    low, high = 0, prefix.q
    while low < high:
        mid = (low + high + 1) // 2
        if _reference_bases_fit(bases, targets, prefix.added_length(mid), max_payload_bytes):
            low = mid
        else:
            high = mid - 1
    return q_lo, low


@dataclass(frozen=True, slots=True)
class ReferenceUnitMetrics:
    kind: execution.WorkerKind
    lsum: int | None
    llegacy: int | None
    sunit: int | None
    wnew: int | None
    logical_reserve: int | None
    physical_reserve: int | None

    @property
    def physical_closure(self):
        return None if self.sunit is None or self.physical_reserve is None else self.sunit + self.physical_reserve


@dataclass(frozen=True, slots=True)
class ReferenceTrial:
    ordinal: int
    q: int
    actual_physical_bytes: int | None
    actual_logical_bytes: int | None
    physical_margin: int | None
    logical_margin: int | None
    units: tuple
    eligible: bool
    rejection_reason: str | None


@dataclass(frozen=True, slots=True)
class ReferenceConstructionResult:
    """In-memory evaluated-set result; never evidence or profile qualification."""

    q_lo: int | None
    q_hi: int | None
    trials: tuple
    selected_trial: ReferenceTrial | None
    selected_bundles: tuple
    selected_wires: tuple
    rejection_reason: str | None
    cause: str | None


def _next_reference_q(trials, q_lo, q_hi, physical_target):
    # Translate coordinates only; the accepted 1F endpoint/secant/gap schedule
    # is unchanged, including the physical target and all tie-breaking rules.
    shifted = tuple(TextTrial(trial.ordinal, trial.q - q_lo, 0, trial.actual_physical_bytes,
        trial.actual_logical_bytes, trial.physical_margin, trial.logical_margin,
        None, None, None, None, trial.eligible, trial.rejection_reason) for trial in trials)
    proposed = _next_text_h(shifted, q_hi - q_lo, physical_target)
    return None if proposed is None else proposed + q_lo


def _search_reference_trials(q_lo, q_hi, physical_target, evaluate, *, _check=None):
    _need(type(q_lo) is int and type(q_hi) is int and 0 <= q_lo <= q_hi <= _REFERENCE_Q_MAX,
          "REFERENCE_Q_SEARCH_DOMAIN")
    _integer(physical_target, 1)
    _need(callable(evaluate), "REFERENCE_EVALUATOR_REQUIRED")
    trials = []
    for ordinal in range(1, 9):
        q = _next_reference_q(trials, q_lo, q_hi, physical_target)
        if q is None:
            break
        _text_check(_check)
        trial = evaluate(q, ordinal)
        _text_check(_check)
        _need(type(trial) is ReferenceTrial and trial.q == q and trial.ordinal == ordinal,
              "REFERENCE_TRIAL_BINDING")
        trials.append(trial)
    eligible = [trial for trial in trials if trial.eligible]
    selected = min(eligible, key=lambda trial: (trial.actual_physical_bytes,
                   trial.actual_logical_bytes, trial.q)) if eligible else None
    return tuple(trials), selected


def _reference_failure(q_lo, q_hi, trials, cause):
    return ReferenceConstructionResult(q_lo, q_hi, trials, None, (), (),
                                       "REFERENCE_SYNTHETIC_SIZING_UNREPRESENTABLE", cause)


def _reference_static_cause(error):
    # Retain known public diagnoses, never arbitrary validator exception text.
    known = frozenset(("WORKER_PAYLOAD_CAP", "WORKER_LEGACY_CAP", "WORKER_WIRE_CAP",
        "WB02_METADATA_CAP", "LOGICAL_PAYLOAD_CAP", "WB02_WORK_KIND_BINDING",
        "WB02_BOUNDARY_VALIDATION_FAILED", "KCONTROL_REFERENCE_BINDING",
        "REPEAT_FIRST_PREMISE_BINDING", "REPEAT_FIRST_HEADER_BINDING",
        "CONTROL_O4_REFERENCE_BINDING", "CONTROL_O4_DECISION_BINDING",
        "CONTROL_DETERMINISM_SUMMARY_MISMATCH", "KCONTROL_CLASSIFICATION_MISMATCH",
        "NONCANONICAL_OR_WRONG_RECORD_FAMILY", "WRONG_LOGICAL_RECORD_TYPE",
        "NONCANONICAL_LOGICAL_BYTES", "PREPARED_PAYLOAD_LOGICAL_MISMATCH",
        "CONTEXTUAL_CRC_MISMATCH", "UNEXPECTED_LOGICAL_KEY", "MODE_LENGTH_MISMATCH",
        "REFERENCE_MUTATION_SCOPE", "REFERENCE_WIRE_SIZE_BINDING",
        "REFERENCE_SELECTED_FACT_BINDING", "REFERENCE_SELECTED_SIZE_BINDING"))
    reason = str(error)
    if reason in known:
        return reason
    if isinstance(error, records.RecordError):
        return "REFERENCE_CANONICAL_RECORD_FAILURE"
    return "REFERENCE_CANDIDATE_BINDING_OR_CAP_FAILURE"


def _reference_unit_metrics(bundle, rows, targets, profile):
    logical = sum(len(data) for _, values in bundle.streams for data in values)
    legacy = execution.legacy_bundle_size(bundle)
    frames = sum(row.frame_length for row in rows)
    logical_reserve = physical_reserve = 0
    for family in _reference_text_families(bundle):
        owned = tuple(row for row in rows if _text_owned(family, row.stream_name))
        logical_reserve += max(0, getattr(targets.logical, family) - sum(len(row.logical_bytes) for row in owned))
        physical_reserve += max(0, getattr(targets.physical, family) - sum(row.frame_length for row in owned))
    groups, cursor = [], 0
    for name, values in bundle.streams:
        group = rows[cursor:cursor + len(values)]
        groups.append((name, len(values), sum(map(len, values)), sum(row.frame_length for row in group)))
        cursor += len(values)
    _, _, wire = execution._wb02_layout(bundle, profile, logical, legacy, groups, frames)
    return ReferenceUnitMetrics(bundle.kind, logical, legacy, frames, wire, logical_reserve, physical_reserve)


def construct_reference_v2(work, targets, codec_profile_sha256, *, max_payload_bytes, envelope, _check=None):
    """Truthful coupled reference search, without persistence or text searches.

    Every prefix is bounded by the two-copy absolute ceiling. The caller's
    envelope exists solely for the unchanged fresh operational boundary.
    """
    _reference_work(work)
    _need(type(targets) is readiness.DualComponentSizes, "REFERENCE_DUAL_TARGETS_REQUIRED")
    readiness.DualComponentSizes.__post_init__(targets)
    _need(type(codec_profile_sha256) is bytes and len(codec_profile_sha256) == 32,
          "WB02_PROFILE_IDENTITY_REQUIRED")
    _need(type(max_payload_bytes) is int and 0 < max_payload_bytes <= physical.MAX_PAYLOAD_BYTES,
          "REFERENCE_PAYLOAD_CAP")
    operational._envelope(envelope)
    _need(envelope.max_payload_bytes == max_payload_bytes, "REFERENCE_ENVELOPE_CAP_BINDING")
    if work.oracle_b_selected:
        _need(targets.physical.oracle_primary > 0 and (not work.determinism_selected
              or targets.physical.oracle_repeat > 0), "REFERENCE_REACHED_ORACLE_TARGET_REQUIRED")
    _text_check(_check)
    prefix = _reference_prefix(min(_REFERENCE_Q_MAX, max_payload_bytes // 26), _check=_check)
    baselines = _reference_bundles(work, prefix, 0, _check=_check)
    q_lo, q_hi = _reference_q_bounds(baselines, targets, prefix, max_payload_bytes)
    if q_hi is None:
        return _reference_failure(q_lo, q_hi, (), "LOGICAL_MINIMUM_COMPOSITE_CAP")
    if q_lo > q_hi:
        return _reference_failure(q_lo, q_hi, (), "SYNTHETIC_LOGICAL_DOMAIN_EMPTY")
    baseline_contexts = []
    primary_wire = None
    for bundle in baselines:
        _text_check(_check)
        try:
            wire = execution.encode_bundle_v2(bundle, codec_profile_sha256, max_payload_bytes=max_payload_bytes)
        except (records.RecordError, execution.E2ExecutionError, physical.PhysicalError) as error:
            return _reference_failure(q_lo, q_hi, (), _reference_static_cause(error))
        _text_check(_check)
        try:
            context = operational._fresh_wb02_context(wire, work, bundle.kind, codec_profile_sha256, envelope,
                                                     prior_primary_wire=primary_wire)
        except (execution.E2ExecutionError, operational.OperationalError, physical.PhysicalError) as error:
            return _reference_failure(q_lo, q_hi, (), _reference_static_cause(error))
        baseline_contexts.append(context)
        if bundle.kind is execution.WorkerKind.PRIMARY:
            primary_wire = wire
        _text_check(_check)
    best = None

    def evaluate(q, ordinal):
        nonlocal best
        # Materialization callbacks are deliberately outside rejection catches.
        candidates = _reference_candidate_bundles(work, baselines, prefix, q, _check=_check)
        reference_l = sum(len(data) for data in dict(candidates[0].streams)["control_maintenance"])
        reference_p = None
        metrics, wires, prepared = [], [], {}
        reason = None
        primary_legacy = execution.encode_bundle(candidates[0])
        for bundle, baseline in zip(candidates, baseline_contexts):
            _text_check(_check)
            unit = ReferenceUnitMetrics(bundle.kind, None, None, None, None, None, None)
            wire = None
            try:
                execution.revalidate_bundle(bundle, work, bundle.kind, max_payload_bytes=max_payload_bytes)
                operational._bind_prior_bundle(bundle,
                    None if bundle.kind is execution.WorkerKind.PRIMARY else primary_legacy,
                    work, bundle.kind, envelope)
                rows = []
                for row, data in zip(baseline.rows, (data for _, values in bundle.streams for data in values)):
                    if data == row.logical_bytes:
                        rows.append(row)
                        continue
                    _need((row.stream_name in ("control_maintenance", "kcontrol_maintenance",
                          "repeat_control_maintenance") and row.key[2] == 1)
                          or (row.stream_name == "control_determinism" and row.key[2] == 0),
                          "REFERENCE_MUTATION_SCOPE")
                    context = physical.context_for(row.stream_name, codec_profile_sha256)
                    raw_only = physical._context(context).raw_only
                    cache_key = (raw_only, data)
                    if cache_key not in prepared:
                        prepared[cache_key] = physical.encode_payload(data, raw_only=raw_only,
                                                                     max_payload_bytes=max_payload_bytes)
                    mode, payload = prepared[cache_key]
                    frame = physical._frame_from_payload(data, row.key, context, mode, payload,
                                                          max_payload_bytes=max_payload_bytes)
                    rows.append(execution.WB02Row(row.stream_name, row.key, data, frame, len(frame)))
                rows = tuple(rows)
                unit = _reference_unit_metrics(bundle, rows, targets, codec_profile_sha256)
                if bundle.kind is execution.WorkerKind.PRIMARY:
                    reference_p = sum(row.frame_length for row in rows if row.stream_name == "control_maintenance")
                if max(unit.lsum + unit.logical_reserve, unit.llegacy + unit.logical_reserve) > max_payload_bytes:
                    reason = reason or "LOGICAL_MINIMUM_COMPOSITE_CAP"
                elif unit.sunit > max_payload_bytes:
                    reason = reason or "REFERENCE_SUNIT_CAP"
                elif unit.wnew > max_payload_bytes:
                    reason = reason or "REFERENCE_WNEW_CAP"
                elif unit.physical_closure > max_payload_bytes:
                    reason = reason or "REFERENCE_PHYSICAL_MINIMUM_COMPOSITE_CAP"
                else:
                    wire = execution._compose_bundle_v2_from_rows(bundle, codec_profile_sha256, rows,
                                                                  max_payload_bytes=max_payload_bytes)
                    _need(len(wire) == unit.wnew, "REFERENCE_WIRE_SIZE_BINDING")
            except (records.RecordError, execution.E2ExecutionError, operational.OperationalError,
                    physical.PhysicalError, HarnessError) as error:
                reason = reason or _reference_static_cause(error)
            metrics.append(unit)
            wires.append(wire)
            _text_check(_check)
        if reason is None:
            policy = readiness.evaluate_family_size("reference", targets.physical.reference,
                targets.logical.reference, reference_p, reference_l)
            reason = policy.rejection_reason
        trial = ReferenceTrial(ordinal, q, reference_p, reference_l,
            None if reference_p is None else reference_p - targets.physical.reference,
            reference_l - targets.logical.reference, tuple(metrics), reason is None, reason)
        if trial.eligible and (best is None or (reference_p, reference_l, q) < (
                best[0].actual_physical_bytes, best[0].actual_logical_bytes, best[0].q)):
            best = trial, candidates, tuple(wires)
        return trial

    trials, selected = _search_reference_trials(q_lo, q_hi, targets.physical.reference, evaluate, _check=_check)
    if selected is None:
        causes = {trial.rejection_reason for trial in trials}
        cause = next(iter(causes)) if len(causes) == 1 else "SYNTHETIC_SIZING_SEARCH_EXHAUSTED"
        return _reference_failure(q_lo, q_hi, trials, cause)
    trial, bundles, wires = best
    _need(trial == selected, "REFERENCE_SELECTION_BINDING")
    for bundle, wire, expected in zip(bundles, wires, trial.units):
        _text_check(_check)
        try:
            context = operational._fresh_wb02_context(wire, work, bundle.kind, codec_profile_sha256, envelope,
                prior_primary_wire=None if bundle.kind is execution.WorkerKind.PRIMARY else wires[0])
            _need(context.bundle == bundle and _reference_unit_metrics(bundle, context.rows, targets,
                  codec_profile_sha256) == expected, "REFERENCE_SELECTED_FACT_BINDING")
            if bundle.kind is execution.WorkerKind.PRIMARY:
                reference_rows = tuple(row for row in context.rows if row.stream_name == "control_maintenance")
                _need((sum(row.frame_length for row in reference_rows),
                       sum(len(row.logical_bytes) for row in reference_rows)) ==
                      (trial.actual_physical_bytes, trial.actual_logical_bytes), "REFERENCE_SELECTED_SIZE_BINDING")
        except (records.RecordError, execution.E2ExecutionError, operational.OperationalError,
                physical.PhysicalError, HarnessError) as error:
            return _reference_failure(q_lo, q_hi, trials, _reference_static_cause(error))
        _text_check(_check)
    return ReferenceConstructionResult(q_lo, q_hi, trials, trial, bundles, wires, None, None)


def _constructor_policy_source_bundles():
    """Capture only the two closed constructor policies, without orchestration."""
    import inspect
    from types import FunctionType

    def exact_source_value(value):
        if value is None or type(value) in (str, int):
            return
        if type(value) is list:
            for item in value:
                exact_source_value(item)
        elif type(value) is dict and all(type(key) is str for key in value):
            for item in value.values():
                exact_source_value(item)
        else:
            raise HarnessError("CONSTRUCTOR_POLICY_SOURCE_VALUE")

    policies = (
        ("program-k-r0b-reference-constructor/v1", {
            "_REFERENCE_Q_MAX": _REFERENCE_Q_MAX,
            "_REFERENCE_TEXT": _REFERENCE_TEXT,
            "board_dimensions": [30, 16], "mines": 0,
            "origin": [0, 0], "target": [1, 0], "catalog_entries": 479,
            "redundancy_domain": "PROGRAM_K_R0B_REFERENCE_REDUNDANCY_V1\0",
            "minimum_additional_entry_bound": 13, "packed_prefix_bytes": "6q+4",
            "candidate_limit": 8,
            "selection_order": ["actual_physical_bytes", "actual_logical_bytes", "q"],
            "physical_upper_window": None,
            "readiness_policy": "dual-independent-ceil-3-over-2/v1",
        }, (
            "reference_board_identity", "ReferencePrefix", "_reference_catalog",
            "_reference_observation", "_reference_prefix", "_reference_constraints",
            "_reference_work", "_reference_projection", "_reference_maintenance",
            "_reference_k_actual", "_reference_children", "_reference_bundles",
            "_reference_candidate_bundles", "_reference_text_families", "_reference_size_bases",
            "_reference_bases_fit", "_reference_expanded_fits", "_reference_q_bounds",
            "ReferenceUnitMetrics", "ReferenceTrial", "ReferenceConstructionResult",
            "_next_reference_q", "_search_reference_trials", "_reference_failure",
            "_reference_static_cause", "_reference_unit_metrics", "construct_reference_v2",
        )),
        ("program-k-r0b-text-constructor/v1", {
            "_TEXT_FAMILIES": [[family, kind.value, stream, index, multiplicity]
                               for family, kind, stream, index, multiplicity in _TEXT_FAMILIES],
            "text_format": '"SYNTHETIC_NON_EVIDENCE|L:" + "x"*ell + "|H:" + Base64(B(h))',
            "entropy_domain": "PROGRAM_K_R0B_TEXT_FILL_V1\0",
            "entropy_raw_block_bytes": 49152, "base64_full_block_chars": 65536,
            "candidate_limit": 8, "physical_window": 4096, "secant_target": "T_P",
            "selection_order": ["actual_physical_bytes", "actual_logical_bytes", "h"],
            "readiness_policy": "dual-independent-ceil-3-over-2/v1",
        }, (
            "TextTrial", "TextConstructionResult", "_text_spec", "_text_check",
            "_text_entropy", "_text_filler", "_text_lengths", "_next_text_h",
            "_search_text_trials", "_text_terminal_reason", "_mutate_text_bundle",
            "_text_owned", "construct_text_family_v2",
        )),
    )
    result = []
    for policy_name, constants, names in policies:
        sources = []
        for name in names:
            value = globals().get(name)
            expected_type = type if name[0].isupper() else FunctionType
            _need(type(value) is expected_type and value.__name__ == name
                  and value.__qualname__ == name and value.__module__ == __name__,
                  "CONSTRUCTOR_POLICY_SOURCE_OBJECT_REQUIRED")
            try:
                source = inspect.getsource(value)
            except (OSError, TypeError):
                raise HarnessError("CONSTRUCTOR_POLICY_SOURCE_UNAVAILABLE") from None
            _need(type(source) is str and bool(source.strip()), "CONSTRUCTOR_POLICY_SOURCE_UNAVAILABLE")
            sources.append({"name": name, "source": source.replace("\r\n", "\n").replace("\r", "\n")})
        node = {"schema": "program-k-r0b-constructor-policy-source/v1", "name": policy_name,
                "constants": constants, "sources": sources}
        exact_source_value(node)
        result.append(json.dumps(node, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=True, allow_nan=False).encode("ascii"))
    return tuple(result)


def _constructor_policy_identities():
    """Bind exact normalized constructor sources; no file metadata enters identity."""
    return tuple({"name": json.loads(data)["name"], "sha256": sha256(data).hexdigest()}
                 for data in _constructor_policy_source_bundles())


def _capture_qualified_codec_profile():
    """Read-only in-memory profile owner for a later separately authorized run."""
    profile = physical.capture_qualified_profile(constructor_policies=_constructor_policy_identities())
    physical.require_qualified_profile(profile)
    return profile


@dataclass(frozen=True, slots=True)
class _V2PreparedUnit:
    """Local sizing facts, never a validation token accepted by persistence."""

    work: execution.BoardWork
    results: tuple
    family_evaluations: tuple
    physical_family_bytes: tuple
    logical_family_bytes: tuple
    physical_excess: int

    def __reduce_ex__(self, protocol):
        raise TypeError("V2 materialization facts are invocation-local, not serializable.")


@dataclass(frozen=True, slots=True)
class _V2FamilyTotal:
    family: str
    physical_bytes: int
    logical_bytes: int
    physical_excess: int

    def __post_init__(self):
        _need(type(self.family) is str and self.family in readiness.V2_FAMILIES,
              "EXACT_V2_FAMILY_REQUIRED")
        for value in (self.physical_bytes, self.logical_bytes, self.physical_excess):
            _integer(value)


@dataclass(frozen=True, slots=True)
class _V2MaterializedUnit:
    prepared: _V2PreparedUnit
    ledger: readiness.ProceduralLedger
    receipts: tuple
    family_totals: tuple


def _v2_materialization_boundary(work, profile, envelope):
    _need(type(work) is execution.BoardWork, "V2_EXACT_BOARD_WORK_REQUIRED")
    execution.BoardWork.__post_init__(work)
    _need(_known_synthetic_board(work.board), "SYNTHETIC_NON_BOARD_IDENTITY_REQUIRED")
    physical.require_qualified_profile(profile)
    operational._envelope(envelope)
    return profile.sha256


def _synthetic_v2_operation_result(work, kind, wire, profile, envelope, *,
                                   prior_primary_wire=None, samples=()):
    """Observe constructor bytes; this is not a worker execution receipt.

    Resources are optional explicit synthetic observations. No execution or
    resource sampling is inferred, and no fresh context escapes this call.
    """
    profile_sha256 = _v2_materialization_boundary(work, profile, envelope)
    _need(type(kind) is execution.WorkerKind and kind in operational._kinds(work),
          "SYNTHETIC_KIND_NOT_SCHEDULED")
    _need(type(samples) is tuple and len(samples) <= 3, "V2_SYNTHETIC_RESOURCE_SAMPLES")
    context = operational._fresh_wb02_context(wire, work, kind, profile_sha256, envelope,
                                             prior_primary_wire=prior_primary_wire)
    _need(type(context) is operational._WB02Context and context.work == work
          and context.kind is kind and context.codec_profile_sha256 == profile_sha256
          and context.wire is wire and context.envelope is envelope,
          "V2_MATERIALIZATION_CONTEXT_BINDING")
    _need(context.bundle.status is records.AuditStatus.PASS, "V2_MATERIALIZATION_PASS_REQUIRED")
    receipt = operational.UnitReceipt(work.position, kind, records.AuditStatus.PASS,
                                      "SYNTHETIC_MATERIALIZATION", 0, None)
    return operational._V2OperationResult(receipt, wire, profile_sha256, samples, None,
        context.logical_bytes, context.physical_frame_bytes, context.legacy_bundle_bytes,
        context.wb02_wire_bytes)


def _prepare_v2_materialization_unit(work, results, targets, profile, envelope, owned_families):
    """Derive the complete owned partition afresh from exact WB02/RF02 bytes."""
    profile_sha256 = _v2_materialization_boundary(work, profile, envelope)
    _need(type(targets) is readiness.DualComponentSizes, "V2_DUAL_TARGETS_REQUIRED")
    readiness.DualComponentSizes.__post_init__(targets)
    _need(type(results) is tuple, "V2_WORKFLOW_ADMISSION_TYPES")
    for result in results:
        _need(type(result) is operational._V2OperationResult, "V2_EXACT_OPERATION_RESULT_REQUIRED")
        operational._V2OperationResult.__post_init__(result)
        _need(result.receipt.position == work.position, "V2_RESULT_WORK_BINDING")
        _need(result.codec_profile_sha256 == profile_sha256, "V2_RESULT_PROFILE_BINDING")
        _need(result.receipt.status is records.AuditStatus.PASS and result.wire is not None,
              "V2_MATERIALIZATION_PASS_REQUIRED")
    _need(tuple(result.receipt.kind for result in results) == operational._kinds(work),
          "V2_WORKFLOW_RESULT_ORDER")
    _need(type(owned_families) is tuple and bool(owned_families)
          and all(type(family) is str and family in readiness.V2_FAMILIES for family in owned_families),
          "V2_FAMILY_OWNERSHIP_REQUIRED")
    _need(len(set(owned_families)) == len(owned_families), "DUPLICATE_UNIT_FAMILY")

    physical_bytes, logical_bytes = {}, {}
    complete_physical = complete_logical = 0
    for result in results:
        kind = result.receipt.kind
        context = operational._fresh_wb02_context(result.wire, work, kind, profile_sha256, envelope,
            prior_primary_wire=None if kind is execution.WorkerKind.PRIMARY else results[0].wire)
        _need(type(context) is operational._WB02Context and context.work == work
              and context.kind is kind and context.codec_profile_sha256 == profile_sha256
              and context.wire is result.wire and context.envelope is envelope,
              "V2_MATERIALIZATION_CONTEXT_BINDING")
        _need(context.bundle.status is records.AuditStatus.PASS
              and context.bundle.work_position == result.receipt.position and context.bundle.kind is kind,
              "V2_MATERIALIZATION_RECEIPT_BINDING")
        _need((result.logical_bytes, result.physical_frame_bytes, result.legacy_bundle_bytes,
               result.wb02_wire_bytes) == (context.logical_bytes, context.physical_frame_bytes,
               context.legacy_bundle_bytes, context.wb02_wire_bytes), "V2_MATERIALIZATION_SIZE_BINDING")
        for family in _reference_text_families(context.bundle):
            rows = tuple(row for row in context.rows if _text_owned(family, row.stream_name))
            _need(bool(rows) and family not in physical_bytes, "V2_FAMILY_OWNERSHIP_BINDING")
            physical_bytes[family] = sum(row.frame_length for row in rows)
            logical_bytes[family] = sum(len(row.logical_bytes) for row in rows)
        if kind is execution.WorkerKind.PRIMARY:
            # The PRIMARY control_maintenance representation is the sole
            # Reference owner. Copied premises in D/K remain in those text
            # families' accepted _text_owned partition, never another Reference.
            reference_rows = tuple(row for row in context.rows if row.stream_name == "control_maintenance")
            if reference_rows:
                physical_bytes["reference"] = sum(row.frame_length for row in reference_rows)
                logical_bytes["reference"] = sum(len(row.logical_bytes) for row in reference_rows)
        complete_physical += context.physical_frame_bytes
        complete_logical += context.logical_bytes
    present = tuple(family for family in readiness.V2_FAMILIES if family in physical_bytes)
    _need(owned_families == present, "V2_FAMILY_OWNERSHIP_BINDING")
    _need(sum(physical_bytes.values()) == complete_physical
          and sum(logical_bytes.values()) == complete_logical, "V2_FAMILY_BYTE_PARTITION")
    evaluations = tuple(readiness.evaluate_family_size(family,
        getattr(targets.physical, family), getattr(targets.logical, family),
        physical_bytes[family], logical_bytes[family]) for family in present)
    for evaluation in evaluations:
        _need(evaluation.eligible, evaluation.rejection_reason)
    excess = readiness.unit_physical_excess(evaluations)
    return _V2PreparedUnit(work, results, evaluations,
        tuple((family, physical_bytes[family]) for family in present),
        tuple((family, logical_bytes[family]) for family in present), excess)


def _new_v2_materialization_ledger(targets, unit_counts):
    """Bind a future full owner's ledger to the accepted physical capacity."""
    _need(type(targets) is readiness.DualComponentSizes, "V2_DUAL_TARGETS_REQUIRED")
    readiness.DualComponentSizes.__post_init__(targets)
    return readiness.ProceduralLedger(readiness.procedural_excess_capacity(targets.physical, unit_counts))


def _v2_family_totals(values):
    _need(type(values) is tuple, "V2_FAMILY_TOTALS_REQUIRED")
    for value in values:
        _need(type(value) is _V2FamilyTotal, "V2_FAMILY_TOTAL_REQUIRED")
        _V2FamilyTotal.__post_init__(value)
    names = tuple(value.family for value in values)
    _need(len(set(names)) == len(names)
          and names == tuple(family for family in readiness.V2_FAMILIES if family in names),
          "V2_FAMILY_TOTALS_COVERAGE")
    return values


def _materialize_v2_unit(work, results, targets, profile, envelope, owned_families,
                         ledger, sink, *, family_totals=()):
    """One serial unit: fresh facts, reserve, exact durable admission, commit.

    Failed invocations return neither reserved state nor updated totals. Partial
    bytes belong to the aborted outer run; there is no refund or retry path.
    """
    prepared = _prepare_v2_materialization_unit(work, results, targets, profile, envelope, owned_families)
    _need(type(ledger) is readiness.ProceduralLedger, "EXACT_PROCEDURALLEDGER_REQUIRED")
    readiness.ProceduralLedger.__post_init__(ledger)
    previous_totals = {value.family: value for value in _v2_family_totals(family_totals)}
    for evaluation in prepared.family_evaluations:
        old = previous_totals.get(evaluation.family, _V2FamilyTotal(evaluation.family, 0, 0, 0))
        previous_totals[evaluation.family] = _V2FamilyTotal(evaluation.family,
            old.physical_bytes + evaluation.actual_physical_bytes,
            old.logical_bytes + evaluation.actual_logical_bytes,
            old.physical_excess + evaluation.physical_excess)
    updated_totals = tuple(previous_totals[family] for family in readiness.V2_FAMILIES
                           if family in previous_totals)
    _need(type(sink) is operational._V2EvidenceSink, "V2_WORKFLOW_ADMISSION_TYPES")
    _need(sink.profile_sha256 == profile.sha256 and sink.envelope == envelope,
          "V2_MATERIALIZATION_SINK_BINDING")
    reserved = readiness.reserve_procedural_unit(ledger, prepared.family_evaluations)
    sink._writable()
    for result in results:
        sink._result(work, result)
    before_units, before_primary = sink.durable_units, sink.durable_primary_boards
    receipts = []
    # Equivalent accepted 1K admission, with abort on the first refused unit.
    # In particular an ARCHIVE_CAP receipt must not permit downstream writes.
    for result in results:
        receipt = sink.admit(work, result, prior_primary_wire=(None
            if result.receipt.kind is execution.WorkerKind.PRIMARY else results[0].wire))
        _need(type(receipt) is operational.UnitReceipt, "V2_MATERIALIZATION_RECEIPT_BINDING")
        operational.UnitReceipt.__post_init__(receipt)
        _need(receipt.position == result.receipt.position and receipt.kind is result.receipt.kind,
              "V2_MATERIALIZATION_RECEIPT_BINDING")
        _need(receipt.status is records.AuditStatus.PASS, receipt.reason)
        _need(receipt is result.receipt, "V2_MATERIALIZATION_RECEIPT_BINDING")
        receipts.append(receipt)
    sink._writable()
    _need(sink.durable_units == before_units + len(results)
          and sink.durable_primary_boards == before_primary + 1, "V2_MATERIALIZATION_DURABILITY_BINDING")
    committed = readiness.commit_procedural_unit(reserved)
    return _V2MaterializedUnit(prepared, committed, tuple(receipts), updated_totals)


def _reconcile_v2_materialization_totals(targets, unit_counts, family_totals, ledger):
    """Pure physical reconciliation only; this is not final archive readback."""
    _need(type(targets) is readiness.DualComponentSizes, "V2_DUAL_TARGETS_REQUIRED")
    readiness.DualComponentSizes.__post_init__(targets)
    totals = _v2_family_totals(family_totals)
    _need(tuple(value.family for value in totals) == readiness.V2_FAMILIES, "V2_FAMILY_TOTALS_COVERAGE")
    physical_totals = readiness.ComponentSizes(*(value.physical_bytes for value in totals))
    return readiness.reconcile_procedural_excess(targets.physical, unit_counts, physical_totals, ledger)


@dataclass(frozen=True, slots=True)
class _V2ConstructorTrial:
    ordinal: int
    knob: int
    actual_physical_bytes: int | None
    actual_logical_bytes: int | None
    physical_margin: int | None
    logical_margin: int | None
    eligible: bool
    rejection_reason: str | None


@dataclass(frozen=True, slots=True)
class _V2ConstructorObservation:
    """Compact constructor diagnostics, with no transferable byte authority."""

    position: int
    family: str
    constructor_kind: str
    physical_target: int
    logical_target: int
    selected_knob: int
    selected_trial_ordinal: int
    actual_physical_bytes: int
    actual_logical_bytes: int
    physical_margin: int
    logical_margin: int
    physical_excess: int
    logical_excess: int
    text_window_applies: bool
    text_window_upper_bound: int | None
    zero_oracle: bool
    trials: tuple

    def __reduce_ex__(self, protocol):
        raise TypeError("V2 constructor observations are local facts, not trust objects.")


@dataclass(frozen=True, slots=True)
class _V2ConstructedWork:
    """Only the current work's final wires; never retained in a full result."""

    wires: tuple
    constructor_facts: tuple
    owned_families: tuple


@dataclass(frozen=True, slots=True)
class _V2SyntheticMaterialization:
    source_plan: tuple
    materialization_plan: tuple
    codec_profile_sha256: bytes
    coordinator: operational.CoordinatorResult
    ledger: readiness.ProceduralLedger
    family_totals: tuple
    family_counts: tuple
    constructor_facts: tuple
    physical_minimum_total: int
    fixed_allowance_reservation: int
    b_proc: int
    remaining_procedural_budget: int
    max_coordinator_private_bytes: int
    progress_complete: bool
    cleanup_complete: bool
    synthetic_non_evidence: bool = True

    def __reduce_ex__(self, protocol):
        raise TypeError("V2 materialization is not a historical evidence fact.")


def _v2_conceptual_families(work):
    _need(type(work) is execution.BoardWork, "V2_EXACT_BOARD_WORK_REQUIRED")
    execution.BoardWork.__post_init__(work)
    present = {"primary"}
    if work.k_control_selected:
        present.add("k_control")
    if work.determinism_selected:
        present.add("determinism")
    if work.oracle_b_selected:
        present.add("oracle_primary")
        if work.determinism_selected:
            present.add("oracle_repeat")
    if work.k_control_selected or work.determinism_selected:
        present.add("reference")
    return tuple(family for family in readiness.V2_FAMILIES if family in present)


def _v2_materialization_counts(plan):
    counts = dict.fromkeys(readiness.V2_FAMILIES, 0)
    for work in plan:
        for family in _v2_conceptual_families(work):
            counts[family] += 1
    return tuple(counts[family] for family in readiness.V2_FAMILIES)


def _v2_materialization_plan(source_plan):
    """Preserve the supplied selection; transform only Reference producers.

    The full owner separately authenticates accepted selector membership. This
    local mapping also supports small exact non-board plans for bounded tests.
    """
    _need(type(source_plan) is tuple and 0 < len(source_plan) <= identity.CANDIDATE_MAX,
          "V2_SYNTHETIC_SOURCE_PLAN_REQUIRED")
    for work in source_plan:
        _need(type(work) is execution.BoardWork, "V2_EXACT_BOARD_WORK_REQUIRED")
        execution.BoardWork.__post_init__(work)
        _need(work.board == synthetic_board_identity(work.board.game_index),
              "V2_SYNTHETIC_SOURCE_IDENTITY_REQUIRED")
    first = source_plan[0]
    _need(tuple(work.position for work in source_plan) == tuple(range(len(source_plan)))
          and len({work.board.game_index for work in source_plan}) == len(source_plan)
          and all((work.protocol_seed, work.run_id, work.runtime) ==
                  (first.protocol_seed, first.run_id, first.runtime) for work in source_plan),
          "V2_SYNTHETIC_SOURCE_PLAN_BINDING")
    return tuple(replace(work, board=reference_board_identity(work.board.game_index))
                 if work.k_control_selected or work.determinism_selected else work for work in source_plan)


def _build_primary_v2_baseline(work, targets, profile, envelope):
    """Minimal PRIMARY schemas, with V2 framing and no historical size filler."""
    profile_sha256 = _v2_materialization_boundary(work, profile, envelope)
    _need(work.board == synthetic_board_identity(work.board.game_index)
          and not work.k_control_selected and not work.determinism_selected,
          "V2_PRIMARY_ONLY_BASE_REQUIRED")
    _need(type(targets) is readiness.DualComponentSizes, "V2_DUAL_TARGETS_REQUIRED")
    readiness.DualComponentSizes.__post_init__(targets)
    projections = tuple(_synthetic_projection(work, arm, exact=bool(targets.physical.oracle_primary))
                        for arm in (records.Arm.CONTROL, records.Arm.K_P0))
    streams, headers = {}, []
    for projection, role in zip(projections, ("control", "kp0")):
        header, values = execution._projection_streams(projection, role)
        headers.append(header)
        streams.update(values)
    streams.update(_synthetic_children(projections[1], work.oracle_b_selected,
                                       targets.physical.oracle_primary))
    streams["pairs"] = (records.encode(game.pair_projections(*projections).pair),)
    bundle = execution._bundle(work, execution.WorkerKind.PRIMARY, streams, headers,
                               records.AuditStatus.PASS, ())
    execution.revalidate_bundle(bundle, work, execution.WorkerKind.PRIMARY,
                                max_payload_bytes=envelope.max_payload_bytes)
    return bundle, execution.encode_bundle_v2(bundle, profile_sha256,
                                               max_payload_bytes=envelope.max_payload_bytes)


def _v2_constructor_observation(work, family, targets, result):
    reference = family == "reference"
    expected_type = ReferenceConstructionResult if reference else TextConstructionResult
    trial_type = ReferenceTrial if reference else TextTrial
    _need(type(result) is expected_type, "V2_CONSTRUCTOR_RESULT_REQUIRED")
    if not reference:
        _need(result.family == family, "V2_CONSTRUCTOR_FAMILY_BINDING")
    _need(result.rejection_reason is None,
          (result.cause or result.rejection_reason) if reference else result.rejection_reason)
    selected = result.selected_trial
    _need(type(selected) is trial_type and selected.eligible and type(result.trials) is tuple
          and len(result.trials) <= 8 and all(type(trial) is trial_type for trial in result.trials),
          "V2_CONSTRUCTOR_SELECTION_REQUIRED")
    zero_oracle = False if reference else result.zero_oracle
    _need(type(zero_oracle) is bool and (not zero_oracle or family in ("oracle_primary", "oracle_repeat")),
          "V2_ZERO_ORACLE_CONSTRUCTOR_BINDING")
    _need(tuple(trial.ordinal for trial in result.trials) == tuple(range(1, len(result.trials) + 1))
          and ((zero_oracle and not result.trials and selected.ordinal == 0)
               or (not zero_oracle and selected in result.trials)), "V2_CONSTRUCTOR_TRIAL_BINDING")
    policy = readiness.evaluate_family_size(family, getattr(targets.physical, family),
        getattr(targets.logical, family), selected.actual_physical_bytes, selected.actual_logical_bytes)
    _need(policy.eligible and (selected.physical_margin, selected.logical_margin) ==
          (policy.physical_margin, policy.logical_margin), "V2_CONSTRUCTOR_SELECTED_SIZE_BINDING")
    knob = "q" if reference else "h"
    trials = tuple(_V2ConstructorTrial(trial.ordinal, getattr(trial, knob),
        trial.actual_physical_bytes, trial.actual_logical_bytes, trial.physical_margin,
        trial.logical_margin, trial.eligible, trial.rejection_reason) for trial in result.trials)
    return _V2ConstructorObservation(work.position, family, "reference" if reference else "text",
        policy.physical_target, policy.logical_target, getattr(selected, knob), selected.ordinal,
        policy.actual_physical_bytes, policy.actual_logical_bytes, policy.physical_margin,
        policy.logical_margin, policy.physical_excess, policy.logical_excess, policy.text_window_applies,
        policy.text_window_upper_bound, zero_oracle, trials)


def _construct_v2_materialization_work(work, targets, profile, envelope, *, check=None):
    """Reference first, then P/O/D/O-repeat/K, preserving final PRIMARY bytes."""
    profile_sha256 = _v2_materialization_boundary(work, profile, envelope)
    _need(type(targets) is readiness.DualComponentSizes, "V2_DUAL_TARGETS_REQUIRED")
    readiness.DualComponentSizes.__post_init__(targets)
    _text_check(check)
    facts = []
    kinds = operational._kinds(work)
    if work.k_control_selected or work.determinism_selected:
        _need(work.board == reference_board_identity(work.board.game_index), "REFERENCE_NON_BOARD_IDENTITY_REQUIRED")
        result = construct_reference_v2(work, targets, profile_sha256,
            max_payload_bytes=envelope.max_payload_bytes, envelope=envelope, _check=check)
        facts.append(_v2_constructor_observation(work, "reference", targets, result))
        _need(type(result.selected_bundles) is tuple and type(result.selected_wires) is tuple
              and tuple(bundle.kind for bundle in result.selected_bundles) == kinds
              and len(result.selected_wires) == len(kinds), "V2_REFERENCE_WORKFLOW_BINDING")
        bundles = dict(zip(kinds, result.selected_bundles))
        wires = dict(zip(kinds, result.selected_wires))
    else:
        bundle, wire = _build_primary_v2_baseline(work, targets, profile, envelope)
        bundles, wires = {execution.WorkerKind.PRIMARY: bundle}, {execution.WorkerKind.PRIMARY: wire}
    order = ("primary",) + (("oracle_primary",) if work.oracle_b_selected else ())
    order += (("determinism",) + (("oracle_repeat",) if work.oracle_b_selected else ())
              if work.determinism_selected else ())
    order += ("k_control",) if work.k_control_selected else ()
    for family in order:
        _text_check(check)
        _, (_, kind, _, _, _) = _text_spec(family)
        result = construct_text_family_v2(work, bundles[kind], family, profile_sha256,
            physical_target=getattr(targets.physical, family), logical_target=getattr(targets.logical, family),
            max_payload_bytes=envelope.max_payload_bytes, envelope=envelope,
            prior_primary_wire=None if kind is execution.WorkerKind.PRIMARY else wires[execution.WorkerKind.PRIMARY],
            _check=check)
        facts.append(_v2_constructor_observation(work, family, targets, result))
        _need(type(result.selected_bundle) is execution.WorkerBundle
              and result.selected_bundle.kind is kind and type(result.selected_wire) is bytes,
              "V2_TEXT_WORKFLOW_BINDING")
        bundles[kind], wires[kind] = result.selected_bundle, result.selected_wire
        _text_check(check)
    present = set()
    final_wires = tuple(wires[kind] for kind in kinds)
    for kind, wire in zip(kinds, final_wires):
        _text_check(check)
        context = operational._fresh_wb02_context(wire, work, kind, profile_sha256, envelope,
            prior_primary_wire=None if kind is execution.WorkerKind.PRIMARY else final_wires[0])
        _need(context.bundle == bundles[kind], "V2_CONSTRUCTOR_FINAL_WIRE_BINDING")
        present.update(_reference_text_families(context.bundle))
        if kind is execution.WorkerKind.PRIMARY and any(row.stream_name == "control_maintenance" for row in context.rows):
            present.add("reference")
        _text_check(check)
    _need(len(facts) == len(_v2_conceptual_families(work))
          and {fact.family for fact in facts} == set(_v2_conceptual_families(work)),
          "V2_CONSTRUCTOR_FAMILY_COVERAGE")
    return _V2ConstructedWork(final_wires, tuple(facts),
                              tuple(family for family in readiness.V2_FAMILIES if family in present))


class _V2MaterializationMonitor:
    """Serial constructor-only containment; no worker or background sampler."""

    def __init__(self, envelope, cancel=None):
        self.envelope = operational._envelope(envelope)
        _need(cancel is None or callable(getattr(cancel, "is_set", None)), "CANCELLATION_TOKEN")
        self.cancel = cancel
        self.started_ns = time.monotonic_ns()
        self.max_coordinator_private_bytes = 0

    def check(self):
        _need(self.cancel is None or not self.cancel.is_set(), "CANCELLED")
        now = time.monotonic_ns()
        _need(now - self.started_ns < self.envelope.max_launcher_wall_ms * 1_000_000,
              "SYNTHETIC_MATERIALIZATION_TIMEOUT")
        current = operational.harness._coordinator_private_bytes()
        _integer(current, 1)
        self.max_coordinator_private_bytes = max(self.max_coordinator_private_bytes, current)
        _need(current <= self.envelope.coordinator_memory_cap_bytes, "SYNTHETIC_COORDINATOR_MEMORY_CAP")
        _need(current <= self.envelope.memory_cap_bytes, "SYNTHETIC_COMBINED_MEMORY_CAP")
        return now, current

    def sample(self, work, kind):
        now, current = self.check()
        return records.ResourceSampleRecord(operational._unit_id(work.position, kind),
            records.ProcessRole.COMBINED, 0, current, current, "monotonic_ns:" + str(now),
            now - self.started_ns, records.MemoryMethod.PRIVATE_BYTES)


def _v2_empty_materialization_root(streams_root):
    root = Path(streams_root)
    _need(root.is_dir() and not any(root.iterdir()), "V2_EMPTY_STREAM_ROOT_REQUIRED")
    return root


def _materialize_synthetic_v2(plan, workload, targets, profile, envelope, streams_root, *,
                               cancel=None, progress=None):
    """Full accepted-plan entry point; execution requires separate run approval."""
    _need(type(workload) is readiness.SyntheticWorkload, "V2_SYNTHETIC_WORKLOAD_REQUIRED")
    readiness.SyntheticWorkload.__post_init__(workload)
    readiness.validate_synthetic_work_plan(plan, workload)
    materialization_plan = _v2_materialization_plan(plan)
    _need(type(targets) is readiness.DualComponentSizes, "V2_DUAL_TARGETS_REQUIRED")
    readiness.DualComponentSizes.__post_init__(targets)
    physical.require_qualified_profile(profile)
    operational._envelope(envelope)
    counts = _v2_materialization_counts(materialization_plan)
    _need(counts == workload.unit_counts, "V2_MATERIALIZATION_FAMILY_COUNTS")
    readiness.validate_dual_payload_fit(workload, targets, envelope.max_payload_bytes)
    minimum = readiness.minimum_archive_preflight(targets.physical, workload.unit_counts, 0)
    ledger = _new_v2_materialization_ledger(targets, workload.unit_counts)
    root = _v2_empty_materialization_root(streams_root)
    return _materialize_v2_plan(plan, materialization_plan, targets, profile, envelope, root,
        workload.unit_counts, ledger, minimum, cancel=cancel, progress=progress)


def _materialize_v2_plan(source_plan, materialization_plan, targets, profile, envelope, streams_root,
                         unit_counts, ledger, physical_minimum_total, *, cancel=None, progress=None):
    """Serial lower owner shared by the full path and small bounded fixtures.

    The production caller owns accepted-workload preflight. This layer always
    checks mapping/counts and delegates final reconciliation to the accepted
    policy; it has no test bypass, retry, recovery or independent readback path.
    """
    _need(type(materialization_plan) is tuple
          and materialization_plan == _v2_materialization_plan(source_plan), "V2_MATERIALIZATION_PLAN_BINDING")
    _need(type(unit_counts) is tuple and len(unit_counts) == len(readiness.V2_FAMILIES)
          and all(type(count) is int and count >= 0 for count in unit_counts)
          and _v2_materialization_counts(materialization_plan) == unit_counts,
          "V2_MATERIALIZATION_FAMILY_COUNTS")
    _need(type(targets) is readiness.DualComponentSizes, "V2_DUAL_TARGETS_REQUIRED")
    readiness.DualComponentSizes.__post_init__(targets)
    physical.require_qualified_profile(profile)
    operational._envelope(envelope)
    _need(type(ledger) is readiness.ProceduralLedger, "EXACT_PROCEDURALLEDGER_REQUIRED")
    readiness.ProceduralLedger.__post_init__(ledger)
    _need(not ledger.reservation_pending and ledger.committed_excess == 0, "V2_FRESH_PROCEDURAL_LEDGER_REQUIRED")
    _integer(physical_minimum_total)
    _need(progress is None or callable(progress), "SYNTHETIC_PROGRESS_CALLBACK")
    root = _v2_empty_materialization_root(streams_root)
    monitor = _V2MaterializationMonitor(envelope, cancel)
    monitor.check()
    totals = tuple(_V2FamilyTotal(family, 0, 0, 0) for family in readiness.V2_FAMILIES)
    counts = dict.fromkeys(readiness.V2_FAMILIES, 0)
    receipts, facts = [], []
    sink = operational._V2EvidenceSink(root, envelope, profile)
    try:
        sink.event("coordinator", records.EventKind.START, records.OperationStatus.RUNNING, checkpoint=True)
        monitor.check()
        if progress is not None:
            progress(0, len(materialization_plan))
        for work in materialization_plan:
            monitor.check()
            constructed = _construct_v2_materialization_work(work, targets, profile, envelope, check=monitor.check)
            _need(type(constructed) is _V2ConstructedWork, "V2_CONSTRUCTED_WORK_REQUIRED")
            operations = tuple(_synthetic_v2_operation_result(work, kind, wire, profile, envelope,
                prior_primary_wire=None if kind is execution.WorkerKind.PRIMARY else constructed.wires[0],
                samples=(monitor.sample(work, kind),))
                for kind, wire in zip(operational._kinds(work), constructed.wires))
            monitor.check()
            committed = _materialize_v2_unit(work, operations, targets, profile, envelope,
                constructed.owned_families, ledger, sink, family_totals=totals)
            ledger, totals = committed.ledger, committed.family_totals
            receipts.extend(committed.receipts)
            for family in _v2_conceptual_families(work):
                counts[family] += 1
            facts.extend(constructed.constructor_facts)
            # No prepared unit, context, bundle or wire survives into the next
            # constructor invocation; only compact facts and receipts accumulate.
            del committed, operations, constructed
            monitor.check()
            if progress is not None:
                progress(work.position + 1, len(materialization_plan))
        monitor.check()
        _need(tuple(counts[family] for family in readiness.V2_FAMILIES) == unit_counts
              and len(facts) == sum(unit_counts), "V2_MATERIALIZATION_FAMILY_COUNTS")
        _need(tuple(value.family for value in totals) == readiness.V2_FAMILIES
              and sum(value.physical_excess for value in totals) == ledger.committed_excess,
              "V2_MATERIALIZATION_EXCESS_TOTALS")
        excess = _reconcile_v2_materialization_totals(targets, unit_counts, totals, ledger)
        _need(excess == ledger.committed_excess and not ledger.reservation_pending
              and ledger.committed_excess <= ledger.capacity, "PROCEDURAL_EXCESS_RECONCILIATION")
        _need(tuple((receipt.position, receipt.kind) for receipt in receipts) ==
              tuple((work.position, kind) for work in materialization_plan for kind in operational._kinds(work))
              and all(receipt.status is records.AuditStatus.PASS for receipt in receipts)
              and sink.durable_units == len(receipts)
              and sink.durable_primary_boards == len(materialization_plan), "V2_MATERIALIZATION_DURABILITY_BINDING")
        _need(sum(value.physical_bytes for value in totals) ==
              sum(sink.writers[name].byte_length for name in execution.STREAM_NAMES), "V2_MATERIALIZATION_BYTE_PARTITION")
        monitor.check()
        sink.event("coordinator:ADMISSION_END", records.EventKind.END,
                   records.OperationStatus.COMPLETED, checkpoint=True)
        monitor.check()
        seals = sink.seal()
        monitor.check()
        sink.close()
        coordinator = operational.CoordinatorResult(tuple(receipts), seals, sink.durable_units,
            sink.durable_primary_boards, sum(value.byte_length for value in seals), records.AuditStatus.PASS, ())
        return _V2SyntheticMaterialization(source_plan, materialization_plan, profile.sha256, coordinator,
            ledger, totals, tuple((family, counts[family]) for family in readiness.V2_FAMILIES), tuple(facts),
            physical_minimum_total, identity.FIXED_REPORT_RECEIPT_ALLOWANCE, ledger.capacity,
            ledger.capacity - ledger.committed_excess, monitor.max_coordinator_private_bytes, True, True)
    except BaseException:
        if not sink.poisoned and not sink.sealed and not sink.closed:
            try:
                sink.event("coordinator:SYNTHETIC_V2_MATERIALIZATION_INCOMPLETE", records.EventKind.ERROR,
                           records.OperationStatus.INCOMPLETE, checkpoint=True)
            except BaseException:
                pass
        if not sink.closed:
            try:
                sink.close()
            except BaseException:
                pass
        raise


@dataclass(frozen=True, slots=True)
class SyntheticMaterialization:
    coordinator: operational.CoordinatorResult
    identity_seal: records.StreamDigest
    family_min_bytes: readiness.ComponentSizes
    family_totals: tuple
    family_counts: tuple
    max_unit_payload_bytes: int
    max_coordinator_memory_bytes: int
    readback_complete: bool
    cleanup_complete: bool
    synthetic_non_evidence: bool = True


def materialize_synthetic(plan, sizes, envelope, streams_root, identity_seal, *, progress=None):
    """Serial non-board materialization over an already validated synthetic plan.

    The only preexisting file is its authenticated I7 identity stream. Failure
    leaves partial evidence and closes every writer; it never returns success.
    """
    qualification._plan(plan)
    operational._envelope(envelope)
    _need(type(sizes) is readiness.ComponentSizes, "SYNTHETIC_SIZING_REQUIRED")
    readiness.ComponentSizes.__post_init__(sizes)
    _need(progress is None or callable(progress), "SYNTHETIC_PROGRESS_CALLBACK")
    root = Path(streams_root)
    _need(type(identity_seal) is records.StreamDigest
          and identity_seal.name == qualification.IDENTITY_STREAM, "SYNTHETIC_IDENTITY_SEAL_REQUIRED")
    records.StreamDigest.__post_init__(identity_seal)
    _need(root.is_dir() and {p.name for p in root.iterdir()} == {qualification.IDENTITY_STREAM + ".jsonl"},
          "SYNTHETIC_FRESH_STREAM_ROOT_REQUIRED")
    _need(store.scan_stream(root, qualification.IDENTITY_STREAM) == identity_seal, "SYNTHETIC_IDENTITY_READBACK")
    total = sum(len(operational._kinds(work)) for work in plan)
    totals = dict.fromkeys(_SYNTHETIC_FAMILIES, 0)
    counts = dict.fromkeys(_SYNTHETIC_FAMILIES, 0)
    minima, receipts, max_payload, max_memory = {}, [], 0, 0
    sink = operational._EvidenceSink(root, envelope, total)
    ledger = operational._MemoryLedger(envelope)
    started = time.monotonic_ns()
    try:
        sink.event("coordinator", records.EventKind.START, records.OperationStatus.RUNNING)
        if progress is not None:
            progress(0, total)
        for work in plan:
            primary = None
            for kind in operational._kinds(work):
                unit = operational._unit_id(work.position, kind)
                sink.event(unit, records.EventKind.START, records.OperationStatus.RUNNING)
                unit_started = time.monotonic_ns()
                bundle = build_synthetic_bundle(work, kind, sizes, primary,
                                                max_payload_bytes=envelope.max_payload_bytes)
                if kind is execution.WorkerKind.PRIMARY:
                    primary = bundle
                now = time.monotonic_ns()
                sample, breached = ledger.sample("synthetic-coordinator", 0, unit, now - started)
                _integer(sample.coordinator_bytes, 1)
                _need(not breached, "SYNTHETIC_COORDINATOR_MEMORY_CAP")
                max_memory = max(max_memory, sample.coordinator_bytes)
                operation = _synthetic_operation(bundle, now - unit_started, (sample,))
                receipt = sink.admit(operation)
                _need(receipt == operation.receipt and receipt.status is records.AuditStatus.PASS,
                      "SYNTHETIC_PERSISTENCE_INCOMPLETE")
                receipts.append(receipt)
                family_bytes = synthetic_bundle_family_bytes(bundle)
                for name, size in family_bytes:
                    totals[name] += size
                    counts[name] += 1
                    minima[name] = min(minima.get(name, size), size)
                max_payload = max(max_payload, sum(size for _, size in family_bytes),
                                  len(execution.encode_bundle(bundle)))
                _need(time.monotonic_ns() - started < envelope.max_launcher_wall_ms * 1_000_000,
                      "SYNTHETIC_MATERIALIZATION_TIMEOUT")
                if progress is not None:
                    progress(len(receipts), total)
        sink.event("coordinator:ADMISSION_END", records.EventKind.END, records.OperationStatus.COMPLETED)
        seals = sink.seal()
        result = operational.CoordinatorResult(tuple(receipts), seals, sink.durable_units,
            sink.durable_boards, sum(v.byte_length for v in seals), records.AuditStatus.PASS)
        operational.readback_streams(root, seals, envelope)
        _need(store.scan_stream(root, qualification.IDENTITY_STREAM) == identity_seal,
              "SYNTHETIC_IDENTITY_READBACK")
        _need(sum(totals.values()) == sum(v.byte_length for v in seals if v.name in execution.STREAM_NAMES),
              "SYNTHETIC_ARCHIVE_PARTITION")
        # Production contains every family; bounded fixture plans may omit some.
        actual_minima = readiness.ComponentSizes(*(minima.get(name, getattr(sizes, name))
                                                   for name in _SYNTHETIC_FAMILIES))
        return SyntheticMaterialization(result, identity_seal, actual_minima,
            tuple((name, totals[name]) for name in _SYNTHETIC_FAMILIES),
            tuple((name, counts[name]) for name in _SYNTHETIC_FAMILIES),
            max_payload, max_memory, True, True)
    except BaseException:
        # An open, writable partial stream receives an explicit failure marker.
        # A poisoned/sealed writer is never repaired or reopened to add it.
        try:
            if not sink.sealed:
                sink.event("coordinator:SYNTHETIC_MATERIALIZATION_INCOMPLETE", records.EventKind.ERROR,
                           records.OperationStatus.INCOMPLETE)
                sink.checkpoint()
        except Exception:
            pass
        raise
    finally:
        ledger.remove("synthetic-coordinator")
        sink.close()
# SYNTHETIC_END


# POSTPROCESS_BEGIN
@dataclass(frozen=True, slots=True)
class PostprocessProgress:
    phase: records.Phase
    stage: str
    processed: int
    total: int
    elapsed_ns: int
    output_bytes: int


@dataclass(frozen=True, slots=True)
class PostprocessArtifact:
    name: str
    sha256: str
    byte_length: int


@dataclass(frozen=True, slots=True)
class PostprocessingResult:
    phases: tuple
    analysis_result: analysis.AnalysisResult
    streams: tuple
    artifacts: tuple
    progress_stream: records.StreamDigest
    complete_wall_ns: int
    bootstrap_replicates: int
    bootstrap_n: int
    bootstrap_progress_count: int
    shared_bootstrap_complete: bool
    compact_scalar_bootstrap: bool
    streaming_reconstruction: bool
    readback_complete: bool
    progress_bounded: bool
    qualification_complete: bool
    cleanup_complete: bool


class _PostprocessClock:
    """Direct phase intervals; progress observes work and never supplies results."""

    def __init__(self, envelope, clock, progress, writer):
        self.envelope, self.clock, self.progress, self.writer = envelope, clock, progress, writer
        self.started = self.last = self.now()
        self.phase, self.phase_started, self.ordinal = None, self.started, 0
        self.processed = self.total = self.output_bytes = 0
        self.stage, self.measurements = "", {}
        self.recorded_stage, self.recorded_processed, self.recorded_ns = None, 0, self.started

    def now(self):
        value = self.clock()
        _integer(value)
        _need(not hasattr(self, "last") or value >= self.last, "POSTPROCESS_CLOCK_REGRESSION")
        self.last = value
        return value

    def check(self):
        now = self.now()
        _need(now - self.started < self.envelope.max_launcher_wall_ms * 1_000_000,
              "POSTPROCESS_LAUNCHER_TIMEOUT")
        if self.phase is not None:
            cap = getattr(self.envelope, self.phase.value.lower() + "_wall_ms")
            _need(now - self.phase_started < cap * 1_000_000, "POSTPROCESS_PHASE_TIMEOUT")
        return now

    def emit(self, stage, processed, total, output_bytes=0, *, event=records.EventKind.PROGRESS):
        for value in (processed, total, output_bytes):
            _integer(value)
        _need(total > 0 and processed <= total, "POSTPROCESS_PROGRESS_RANGE")
        if stage == self.stage:
            _need(total == self.total and processed >= self.processed
                  and output_bytes >= self.output_bytes, "POSTPROCESS_PROGRESS_REGRESSION")
        now = self.check()
        self.stage, self.processed, self.total, self.output_bytes = stage, processed, total, output_bytes
        fact = PostprocessProgress(self.phase, stage, processed, total,
                                  now - self.phase_started, output_bytes)
        # Every completed unit is observed and checked. Durable snapshots are
        # bounded in work/time so telemetry does not mirror the entire archive.
        stage_key = (self.phase, stage)
        snapshot_step = 65_536 if stage == "bytes" else 128
        if (event is not records.EventKind.PROGRESS or stage_key != self.recorded_stage
                or processed == total or processed - self.recorded_processed >= snapshot_step
                or now - self.recorded_ns >= 1_000_000_000):
            self.writer.append((self.ordinal,), records.OperationEventRecord(self.phase,
                stage + ":" + str(processed) + "/" + str(total) + ":bytes=" + str(output_bytes),
                event, now - self.started, self.ordinal,
                records.OperationStatus.COMPLETED if event is records.EventKind.END
                else records.OperationStatus.RUNNING))
            self.ordinal += 1
            self.recorded_stage, self.recorded_processed, self.recorded_ns = stage_key, processed, now
        if self.progress is not None:
            self.progress(fact)
        self.check()

    def begin(self, phase, stage, total):
        _need(self.phase is None and phase not in self.measurements, "POSTPROCESS_PHASE_OVERLAP")
        self.phase, self.phase_started, self.stage = phase, self.check(), ""
        self.emit(stage, 0, total, event=records.EventKind.START)

    def finish(self):
        _need(self.processed == self.total, "POSTPROCESS_PROGRESS_INCOMPLETE")
        self.emit(self.stage, self.processed, self.total, self.output_bytes, event=records.EventKind.END)
        wall = self.check() - self.phase_started
        self.measurements[self.phase] = readiness.PhaseMeasurement(self.phase, wall,
            self.processed, self.total, self.output_bytes, True, True)
        self.phase = None


class _PostprocessLane:
    """Delegate scanner/merge ownership and count only consumed canonical rows."""

    def __init__(self, lane, consumed):
        self.lane, self.consumed = lane, consumed

    def peek(self):
        return self.lane.peek()

    def pop(self):
        value = self.lane.pop()
        if value is not None:
            self.consumed()
        return value


def _postprocess_validate(root, plan, result, identity_seal, envelope, expected_identity,
                          source_recheck, meter):
    """One accepted I2 scan per stream; all I7 semantic helpers stay authoritative."""
    from stage3_physical import load_timing_table
    failed, incomplete, cancel = threading.Event(), threading.Event(), threading.Event()
    raw_lanes, lanes, rows = [], {}, []
    if result.status is records.AuditStatus.FAIL:
        failed.set()
    elif result.status is records.AuditStatus.INCOMPLETE:
        incomplete.set()
    for receipt in result.receipts:
        if receipt.status is records.AuditStatus.FAIL:
            failed.set()
        elif receipt.status is records.AuditStatus.INCOMPLETE:
            incomplete.set()
    if result.reason_codes:
        incomplete.set()
    seals = result.streams + (identity_seal,)
    names = qualification._STREAMS + (qualification.IDENTITY_STREAM,)
    _need({p.name for p in root.iterdir()} == {name + ".jsonl" for name in names},
          "DURABLE_STREAM_DIRECTORY_COVERAGE_MISMATCH")
    _need(len(seals) == len(names) and tuple(v.name for v in seals) == names,
          "STREAM_SEAL_IDENTITY_MISMATCH")
    for seal in seals:
        _need(type(seal) is records.StreamDigest, "EXACT_STREAM_SEAL_REQUIRED")
        records.StreamDigest.__post_init__(seal)
    total, consumed_count = sum(value.record_count for value in seals), 0
    meter.begin(records.Phase.VALIDATION, "records", total)

    def consumed():
        nonlocal consumed_count
        consumed_count += 1
        meter.emit("records", consumed_count, total)

    try:
        # The accepted lane owns its real monotonic deadline; the injectable
        # outer clock independently checks every consumed record and phase.
        deadline = time.monotonic_ns() + envelope.validation_wall_ms * 1_000_000
        for seal in seals:
            raw = qualification._Lane(root, seal, cancel, deadline, failed, incomplete)
            raw_lanes.append(raw)
            lanes[seal.name] = _PostprocessLane(raw, consumed)
        for ordinal, expected in enumerate(expected_identity):
            _need(lanes[qualification.IDENTITY_STREAM].pop() == ((ordinal,), expected),
                  "DURABLE_IDENTITY_MISMATCH")
        _need(lanes[qualification.IDENTITY_STREAM].peek() is None, "EXTRA_IDENTITY_RECORD")
        table, receipt_index, admitted = load_timing_table(), 0, set()
        for work in plan:
            primary = None
            for kind in operational._kinds(work):
                rank, values, payload_size = operational._kind_rank(kind), {}, 0
                for name in execution.STREAM_NAMES:
                    data, lane = [], lanes[name]
                    while lane.peek() is not None:
                        key, value = lane.peek()
                        _need(len(key) == 3 and key[:2] >= (work.position, rank), "UNIT_KEY_ORDER_MISMATCH")
                        if key[:2] != (work.position, rank):
                            break
                        _need(key == (work.position, rank, len(data))
                              and type(value) is execution._family(name), "UNIT_KEY_OR_RECORD_FAMILY_MISMATCH")
                        encoded = records.encode(value)
                        payload_size += len(encoded)
                        _need(payload_size <= envelope.max_payload_bytes, "QUALIFICATION_UNIT_PAYLOAD_CAP")
                        data.append(encoded)
                        lane.pop()
                    values[name] = tuple(data)
                receipt = result.receipts[receipt_index]
                receipt_index += 1
                if kind is execution.WorkerKind.PRIMARY and values["boards"]:
                    admitted.add(work.position)
                if receipt.status is not records.AuditStatus.PASS:
                    continue
                bundle = qualification._reconstruct(work, kind, values, table, envelope)
                if kind is execution.WorkerKind.PRIMARY:
                    primary = bundle
                    control, kp0 = (execution.restore_projection(bundle, role) for role in ("control", "kp0"))
                    rows.append(analysis.BoardAnalysisRow(work.position, game.pair_projections(control, kp0).pair,
                        control.total_model_us, kp0.total_model_us,
                        control.comparable_compute_ns, kp0.comparable_compute_ns))
                else:
                    _need(primary is not None, "MISSING_PRIMARY_PREMISE")
                    operational._bind_prior_bundle(bundle, execution.encode_bundle(primary), work, kind, envelope)
                meter.check()
        for name in execution.STREAM_NAMES:
            _need(lanes[name].peek() is None, "UNSCHEDULED_OR_EXTRA_UNIT")
        _need(len(admitted) == result.durable_primary_boards, "ADMITTED_PRIMARY_COUNT_MISMATCH")
        qualification._events(lanes["operations"], result, admitted)
        ordinal = 0
        sample_counts = dict.fromkeys((operational._unit_id(v.position, v.kind) for v in result.receipts), 0)
        while lanes["resources"].peek() is not None:
            key, value = lanes["resources"].pop()
            _need(type(value) is records.ResourceSampleRecord and key == (ordinal,)
                  and value.unit_id in sample_counts and value.method is records.MemoryMethod.PRIVATE_BYTES
                  and value.process_role is records.ProcessRole.COMBINED, "RESOURCE_IDENTITY_MISMATCH")
            sample_counts[value.unit_id] += 1
            _need(sample_counts[value.unit_id] <= 3, "EXTRA_RESOURCE_SAMPLE")
            if (value.combined_bytes > envelope.memory_cap_bytes
                    or value.coordinator_bytes > envelope.coordinator_memory_cap_bytes):
                incomplete.set()
            ordinal += 1
        _need(all(sample_counts[operational._unit_id(v.position, v.kind)] > 0
                  for v in result.receipts if v.status is records.AuditStatus.PASS), "MISSING_RESOURCE_EVIDENCE")
        _need(source_recheck() == expected_identity, "SOURCE_CHANGED_DURING_QUALIFICATION")
        meter.check()
    except BaseException as error:
        if failed.is_set():
            raise HarnessError("POSTPROCESS_PRIOR_OR_DURABLE_FAILURE") from error
        raise
    finally:
        cancel.set()
        for lane in raw_lanes:
            lane.thread.join()
    _need(not failed.is_set(), "POSTPROCESS_PRIOR_OR_DURABLE_FAILURE")
    _need(not incomplete.is_set() and len(rows) == len(plan), "POSTPROCESS_REQUIRED_EVIDENCE_INCOMPLETE")
    meter.finish()
    return tuple(rows), seals


def _postprocess_publish(path, data, meter):
    """Publish renderer-owned bytes without another codec or implicit readback."""
    _need(type(data) is bytes and bool(data), "POSTPROCESS_ARTIFACT_BYTES_REQUIRED")
    with store._exclusive(path) as stream:
        for offset in range(0, len(data), 65_536):
            piece = data[offset:offset + 65_536]
            store._write_complete(stream, piece)
            done = offset + len(piece)
            meter.emit("bytes", done, len(data), done)
        stream.flush()
        os.fsync(stream.fileno())
    meter.check()
    return PostprocessArtifact(path.name, sha256(data).hexdigest(), len(data))


def _postprocess_artifact_readback(path, artifact, visit):
    digest, size = sha256(), 0
    with store._reader(path) as stream:
        while True:
            data = stream.read(65_536)
            if not data:
                break
            digest.update(data)
            size += len(data)
            visit(len(data))
    _need(size == artifact.byte_length and digest.hexdigest() == artifact.sha256,
          "POSTPROCESS_ARTIFACT_READBACK_MISMATCH")


def _postprocess_r0b(plan, coordinator_result, identity_seal, root, envelope, output_root, *,
                     expected_identity=None, source_recheck=None, clock=time.perf_counter_ns,
                     progress=None, _analyze=None):
    """Private postprocessing seam; authenticated launchers own authorization.

    Validation precedes aggregation exactly as in accepted I7. Returned phase
    facts use readiness's canonical order, not a fabricated chronological order.
    _analyze is a bounded fixture injection; production launchers never expose it.
    The enclosing launcher owns independent whole-process memory containment.
    """
    qualification._plan(plan)
    readiness._constants()
    operational._envelope(envelope)
    qualification._receipt_plan(plan, coordinator_result)
    _need(callable(clock) and (progress is None or callable(progress)), "POSTPROCESS_OBSERVER_REQUIRED")
    _need(_analyze is None or callable(_analyze), "POSTPROCESS_ANALYZER_REQUIRED")
    _need(source_recheck is None or callable(source_recheck), "POSTPROCESS_SOURCE_RECHECK_REQUIRED")
    if expected_identity is None:
        expected_identity = qualification._identity_records(plan)
    else:
        _need(source_recheck is not None, "POSTPROCESS_SOURCE_RECHECK_REQUIRED")
    _need(type(expected_identity) is tuple and len(expected_identity) >= 3
          and tuple(type(v) for v in expected_identity[:3])
          == (records.ProtocolIdentity, records.CorpusIdentity, records.RuntimeIdentity)
          and all(type(v) is records.SourceBlobIdentity for v in expected_identity[3:]),
          "POSTPROCESS_EXPECTED_IDENTITY_REQUIRED")
    for value in expected_identity:
        records.encode(value)
    indices = tuple(v.board.game_index for v in plan)
    expected_prefix = (
        records.ProtocolIdentity(qualification._PROTOCOL, identity.PROTOCOL_SHA256,
                                 qualification._BLOB, qualification._FREEZE),
        records.CorpusIdentity("SYNTHETIC_I7", min(indices), max(indices) + 1, len(indices), indices,
            identity.corpus_digest(plan[0].protocol_seed, len(plan), indices).hex(), ()), plan[0].runtime)
    _need(expected_identity[:3] == expected_prefix, "POSTPROCESS_PLAN_IDENTITY_MISMATCH")
    recheck = (lambda: qualification._identity_records(plan)) if source_recheck is None else source_recheck
    _need(recheck() == expected_identity, "SOURCE_CHANGED_BEFORE_POSTPROCESSING")
    root, output_root = Path(root).resolve(strict=True), Path(output_root).resolve()
    _need(root.is_dir() and output_root != root and root not in output_root.parents,
          "POSTPROCESS_SEPARATE_OUTPUT_ROOT_REQUIRED")
    output_root.mkdir()
    writer = store.StreamWriter(output_root, "postprocessing_operations")
    meter = None
    try:
        meter = _PostprocessClock(envelope, clock, progress, writer)
        rows, seals = _postprocess_validate(root, plan, coordinator_result, identity_seal,
            envelope, expected_identity, recheck, meter)
        replicates, seen = identity.BOOTSTRAP_REPLICATES, -1
        readiness._constants()
        meter.begin(records.Phase.AGGREGATION, "replicates", replicates)

        def observe(done, total):
            nonlocal seen
            _need(type(done) is int and type(total) is int and total == replicates
                  and done == seen + 1 and 0 <= done <= total, "POSTPROCESS_BOOTSTRAP_PROGRESS_MISMATCH")
            seen = done
            meter.emit("replicates", done, total)

        digest = identity.corpus_digest(plan[0].protocol_seed, len(plan), tuple(v.board.game_index for v in plan))
        analyze = analysis.analyze_effectiveness if _analyze is None else _analyze
        result = analyze(rows, protocol_seed=plan[0].protocol_seed, corpus_digest=digest,
            concurrency=envelope.concurrency, gate_statuses=None,
            context=("SYNTHETIC_R0B_OPERATIONAL_ONLY_NOT_EFFECTIVENESS_EVIDENCE",), bootstrap_progress=observe)
        _need(type(result) is analysis.AnalysisResult, "POSTPROCESS_ANALYSIS_RESULT_REQUIRED")
        analysis.AnalysisResult.__post_init__(result)
        _need(seen == replicates and result.n == len(plan) and result.overall is None
              and result.concurrency == envelope.concurrency
              and result.bootstrap.replicates == replicates
              and result.bootstrap.accepted_draws == len(plan) * replicates
              and result.bootstrap.seed_hex == analysis.bootstrap_seed(plan[0].protocol_seed, digest).hex(),
              "POSTPROCESS_FULL_SHARED_BOOTSTRAP_REQUIRED")
        meter.finish()

        meter.begin(records.Phase.PUBLICATION, "analysis", 1)
        analysis_bytes = report.render_analysis_json(result)
        meter.emit("bytes", 0, len(analysis_bytes))
        analysis_artifact = _postprocess_publish(output_root / "analysis.json", analysis_bytes, meter)
        meter.finish()

        total = sum(v.byte_length for v in seals) + analysis_artifact.byte_length
        meter.begin(records.Phase.READBACK, "bytes", total)
        read = 0
        def read_visit(count=1):
            nonlocal read
            read += count
            meter.emit("bytes", read, total)
        for seal in seals:
            observed = store.scan_stream(root, seal.name, visit=lambda key, value:
                read_visit(len(store._key_bytes(key)) + len(records.encode(value)) + 2))
            _need(observed == seal, "POSTPROCESS_STREAM_READBACK_MISMATCH")
            meter.check()
        _postprocess_artifact_readback(output_root / analysis_artifact.name, analysis_artifact, read_visit)
        meter.finish()

        meter.begin(records.Phase.REPORT, "analysis", 1)
        html = report.render_report_html(result).encode("utf-8")
        meter.emit("bytes", 0, len(html))
        html_artifact = _postprocess_publish(output_root / "report.html", html, meter)
        _postprocess_artifact_readback(output_root / html_artifact.name, html_artifact,
                                      lambda _: meter.check())
        _need(recheck() == expected_identity, "SOURCE_CHANGED_DURING_POSTPROCESSING")
        meter.finish()
        event_seal = writer.seal()
        # Final telemetry is finite, separately included in the complete wall,
        # and scanned once without appending to its already sealed stream.
        telemetry_count = 0
        def telemetry_visit(*_):
            nonlocal telemetry_count
            telemetry_count += 1
            now = meter.check()
            if progress is not None:
                progress(PostprocessProgress(records.Phase.READBACK, "telemetry_records", telemetry_count,
                    event_seal.record_count, now - meter.started, 0))
            meter.check()
        observed = store.scan_stream(output_root, event_seal.name, visit=telemetry_visit)
        _need(observed == event_seal, "POSTPROCESS_PROGRESS_READBACK_MISMATCH")
        complete_wall = meter.check() - meter.started
        phases = tuple(meter.measurements[phase] for phase in readiness.POSTPROCESS_PHASES)
        _need(complete_wall >= sum(v.wall_ns for v in phases), "POSTPROCESS_WALL_ACCOUNTING")
        return PostprocessingResult(phases, result, seals, (analysis_artifact, html_artifact), event_seal,
            complete_wall, replicates, len(plan), seen + 1, True, True, True, True, True, True, True)
    except BaseException:
        # Root's fail-closed launcher owns the failure receipt. An unfinished
        # stream is retained; neither a partial artifact nor a file name is PASS.
        raise
    finally:
        writer.close()
# POSTPROCESS_END


# EVIDENCE_LAUNCH_BEGIN
class ActualRunAuthorization(Enum):
    R0_A = "AUTHORIZE_ACTUAL_PROGRAM_K_E2_R0_A"
    R0_B = "AUTHORIZE_ACTUAL_PROGRAM_K_E2_R0_B"


@dataclass(frozen=True, slots=True)
class FileFact:
    path: str
    byte_length: int
    sha256: str

    def __post_init__(self):
        _need(type(self.path) is str and self.path and "\\" not in self.path
              and not Path(self.path).is_absolute() and ".." not in Path(self.path).parts,
              "RELATIVE_ARCHIVE_PATH_REQUIRED")
        _integer(self.byte_length)
        _need(type(self.sha256) is str and len(self.sha256) == 64
              and all(c in "0123456789abcdef" for c in self.sha256), "ARTIFACT_HASH_REQUIRED")


@dataclass(frozen=True, slots=True)
class ArchiveAccounting:
    files: tuple
    attributable_bytes: int
    fixed_allowance_bytes: int
    archive_bytes: int

    def __post_init__(self):
        _need(type(self.files) is tuple and all(type(v) is FileFact for v in self.files), "ARCHIVE_FILES_REQUIRED")
        for value in self.files:
            FileFact.__post_init__(value)
        _need(tuple(v.path for v in self.files) == tuple(sorted(set(v.path for v in self.files))),
              "ARCHIVE_PATH_ORDER")
        for value in (self.attributable_bytes, self.fixed_allowance_bytes, self.archive_bytes):
            _integer(value)
        _need(self.attributable_bytes + self.fixed_allowance_bytes == self.archive_bytes
              == sum(v.byte_length for v in self.files), "ARCHIVE_EXACT_PARTITION")


_FINALIZATION_STAGES = ("writes", "manifest_inventory", "accounting_inventory", "source_recheck", "cleanup")


@dataclass(frozen=True, slots=True)
class FinalizationFact:
    """External operator observation of closing an already measured archive."""
    stages: tuple
    wall_ns: int
    max_progress_gap_ns: int
    progress_events: int
    complete: bool

    def __post_init__(self):
        _need(type(self.stages) is tuple and len(self.stages) == len(_FINALIZATION_STAGES),
              "FINALIZATION_STAGE_COVERAGE")
        for expected, value in zip(_FINALIZATION_STAGES, self.stages):
            _need(type(value) is tuple and len(value) == 3 and value[0] == expected,
                  "FINALIZATION_STAGE_COVERAGE")
            _integer(value[1])
            _integer(value[2], 1)
            _need(value[1] <= value[2], "FINALIZATION_PROGRESS_RANGE")
        _need(self.stages[0][2] == 4 and self.stages[-2][2] == self.stages[-1][2] == 1,
              "FINALIZATION_WORK_COVERAGE")
        _integer(self.wall_ns, 1)
        _integer(self.max_progress_gap_ns)
        _integer(self.progress_events)
        _need(self.max_progress_gap_ns <= self.wall_ns and type(self.complete) is bool,
              "FINALIZATION_WALL_ACCOUNTING")
        if self.complete:
            _need(all(done == total for _, done, total in self.stages)
                  and self.progress_events >= 2 * len(self.stages), "FINALIZATION_PROGRESS_INCOMPLETE")


class _FinalizationObserver:
    """Fixed archive-closing counters, without writing into the measured tree."""

    def __init__(self, check, *, clock=time.perf_counter_ns):
        self.check, self.clock = check, clock
        self.started = self.last = clock()
        _integer(self.started)
        self.max_gap, self.events, self.stages = 0, 0, {}

    def observe(self, stage, done, total):
        _need(stage in _FINALIZATION_STAGES, "FINALIZATION_STAGE_REQUIRED")
        _integer(done)
        _integer(total, 1)
        _need(done <= total, "FINALIZATION_PROGRESS_RANGE")
        prior = self.stages.get(stage)
        _need((prior is None and done == 0) or (prior is not None
              and total == prior[1] and done >= prior[0]), "FINALIZATION_PROGRESS_REGRESSION")
        self.check()
        now = self.clock()
        _integer(now)
        _need(now >= self.last, "FINALIZATION_CLOCK_REGRESSION")
        self.max_gap = max(self.max_gap, now - self.last)
        self.last, self.stages[stage], self.events = now, (done, total), self.events + 1

    def finish(self):
        self.check()
        now = self.clock()
        _integer(now)
        _need(now >= self.last and set(self.stages) == set(_FINALIZATION_STAGES),
              "FINALIZATION_PROGRESS_INCOMPLETE")
        return FinalizationFact(tuple((stage, *self.stages[stage]) for stage in _FINALIZATION_STAGES),
            now - self.started, max(self.max_gap, now - self.last), self.events, True)


# Constructor/error ownership remains here. The pure codec accepts exactly these
# four local types through a closed compatibility parameter, without importing us.
_LOCAL_FACT_TYPES = (RunProvenance, FileFact, ArchiveAccounting, FinalizationFact)


def _fact_node(value):
    try:
        return evidence.fact_node_v1(value, local_fact_types=_LOCAL_FACT_TYPES)
    except evidence.EvidenceError as error:
        raise HarnessError(str(error)) from None


def _fact_read(node):
    try:
        return evidence.fact_read_v1(node, local_fact_types=_LOCAL_FACT_TYPES)
    except evidence.EvidenceError as error:
        raise HarnessError(str(error)) from None


def _inventory(root, *, exclude=(), check=lambda: None, progress=None):
    root = Path(root).resolve(strict=True)
    _need(progress is None or callable(progress), "INVENTORY_PROGRESS_CALLBACK")
    pending, result = [], []
    for path in sorted(root.rglob("*")):
        _need(not path.is_symlink() and not path.is_junction(), "ARCHIVE_LINK_FORBIDDEN")
        if path.is_dir():
            continue
        _need(path.is_file() and root in path.resolve(strict=True).parents, "ARCHIVE_FILE_REQUIRED")
        relative = path.relative_to(root).as_posix()
        if relative in exclude:
            continue
        pending.append((path, relative, path.stat().st_size))
        check()
    total, processed = sum(size for _, _, size in pending), 0
    if progress is not None:
        progress(0, total)
    for path, relative, expected_size in pending:
        digest, length = sha256(), 0
        with path.open("rb") as stream:
            while True:
                data = stream.read(65536)
                if not data:
                    break
                digest.update(data)
                length += len(data)
                processed += len(data)
                _need(length <= expected_size and processed <= total, "ARCHIVE_CHANGED_DURING_INVENTORY")
                check()
                if progress is not None:
                    progress(processed, total)
        _need(length == expected_size, "ARCHIVE_CHANGED_DURING_INVENTORY")
        result.append(FileFact(relative, length, digest.hexdigest()))
        check()
    _need(processed == total, "ARCHIVE_CHANGED_DURING_INVENTORY")
    if progress is not None:
        progress(processed, total)
    return tuple(sorted(result, key=lambda value: value.path))


def account_experiment_archive(root, materialization, *, check=lambda: None, progress=None):
    """Every archive-local byte belongs once to a family or the fixed allowance."""
    _need(type(materialization) is SyntheticMaterialization, "SYNTHETIC_MATERIALIZATION_REQUIRED")
    files = _inventory(root, check=check, progress=progress)
    attributable_names = {"streams/" + name + ".jsonl" for name in execution.STREAM_NAMES}
    by_path = {v.path: v for v in files}
    required = {"coordinator.json", "status.json", "manifest.json", "COMPLETE.json",
                "postprocessing/analysis.json", "postprocessing/report.html",
                "postprocessing/postprocessing_operations.jsonl", "streams/operations.jsonl",
                "streams/resources.jsonl", "streams/qualification_identity.jsonl"}
    _need(required <= set(by_path), "R0B_SUPPORTING_FILE_OMISSION")
    all_seals = materialization.coordinator.streams + (materialization.identity_seal,)
    for seal in all_seals:
        _need("streams/" + seal.name + ".jsonl" in by_path, "R0B_SUPPORTING_STREAM_OMISSION")
        fact = by_path["streams/" + seal.name + ".jsonl"]
        _need((fact.byte_length, fact.sha256) == (seal.byte_length, seal.sha256), "R0B_SEALED_STREAM_DRIFT")
    closed = store.read_completion_receipt(root)
    _need(closed.state is records.CompletionState.COMPLETED
          and closed.manifest_sha256 == by_path["manifest.json"].sha256,
          "R0B_ARCHIVE_NOT_CLOSED")
    manifest = _json_bytes((Path(root) / "manifest.json").read_bytes())
    _need(manifest.get("schema") == "program-k-e2-r0b-experiment/v1"
          and manifest.get("classification") == "SYNTHETIC_NON_EFFECTIVENESS"
          and _fact_read(manifest["inventory_before_manifest_receipt"])
              == tuple(v for v in files if v.path not in ("manifest.json", "COMPLETE.json")),
          "R0B_CLOSED_ARCHIVE_DRIFT")
    _need(_fact_read(manifest["family_totals"]) == materialization.family_totals
          and _fact_read(manifest["family_counts"]) == materialization.family_counts
          and _fact_read(manifest["family_min_bytes"]) == materialization.family_min_bytes,
          "R0B_FAMILY_MANIFEST_BINDING")
    _need(_fact_read(_json_bytes((Path(root) / "coordinator.json").read_bytes())) == materialization.coordinator,
          "R0B_COORDINATOR_MANIFEST_BINDING")
    provenance = _fact_read(manifest["provenance"])
    workload = _fact_read(manifest["workload"])
    declared_streams = _fact_read(manifest["streams"])
    _need(closed.protocol_sha256 == identity.PROTOCOL_SHA256
          and closed.source_sha256 == _source_digest(provenance)
          and closed.corpus_sha256 == workload.selection.counts.corpus_digest.hex()
          and closed.streams == declared_streams, "R0B_COMPLETION_BINDING")
    _need(tuple(v for v in declared_streams if v.name != "postprocessing_operations")
          == tuple(sorted(all_seals, key=lambda v: v.name)), "R0B_COMPLETION_STREAM_COVERAGE")
    progress_seals = tuple(v for v in declared_streams if v.name == "postprocessing_operations")
    _need(len(progress_seals) == 1 and (progress_seals[0].byte_length, progress_seals[0].sha256)
          == (by_path["postprocessing/postprocessing_operations.jsonl"].byte_length,
              by_path["postprocessing/postprocessing_operations.jsonl"].sha256), "R0B_PROGRESS_SEAL_BINDING")
    _need(attributable_names <= set(by_path), "ATTRIBUTABLE_STREAM_OMISSION")
    attributable = sum(by_path[name].byte_length for name in attributable_names)
    _need(attributable == sum(size for _, size in materialization.family_totals), "ATTRIBUTABLE_BYTE_MISMATCH")
    fixed = sum(v.byte_length for v in files if v.path not in attributable_names)
    _need(fixed <= identity.FIXED_REPORT_RECEIPT_ALLOWANCE, "R0B_FIXED_ALLOWANCE_CAP")
    total = attributable + fixed
    _need(total <= identity.MAX_ARCHIVE_BYTES, "R0B_ARCHIVE_CAP")
    return ArchiveAccounting(files, attributable, fixed, total)


def _r0a_evidence_node(measurements, components, traces):
    values = readiness.validate_r0a_measurements(measurements)
    _need(type(components) is tuple and type(traces) is tuple and len(components) == len(traces) == 3,
          "R0A_EVIDENCE_COVERAGE")
    for measured, raw, progress in zip(values, components, traces):
        work = tuple(unit.work for unit in raw[0].units)
        _need(adapt_r0a_concurrency(measured.plan, measured.envelope, work, raw, progress) == measured,
              "R0A_EVIDENCE_ADAPTER_MISMATCH")
    return {"schema": "program-k-e2-r0a-observations/v1", "readiness": _fact_node(values),
            "operational": _fact_node(components), "progress": _fact_node(traces)}


def write_r0a_evidence(path, measurements, components, traces):
    node = _r0a_evidence_node(measurements, components, traces)
    _exclusive_bytes(path, _canonical(node))
    _need(read_r0a_evidence(path) == (measurements, components, traces), "R0A_EVIDENCE_READBACK")
    return Path(path)


def read_r0a_evidence(path):
    node = _json_bytes(Path(path).read_bytes())
    _need(type(node) is dict and set(node) == {"schema", "readiness", "operational", "progress"}
          and node["schema"] == "program-k-e2-r0a-observations/v1", "R0A_EVIDENCE_SCHEMA")
    values = tuple(_fact_read(node[name]) for name in ("readiness", "operational", "progress"))
    _need(_r0a_evidence_node(*values) == node, "R0A_EVIDENCE_NOT_REPRODUCIBLE")
    return values


def adapt_r0b(measurements, workload, materialization, postprocess, accounting, *,
               complete_wall_ns, max_combined_memory_bytes, containment_complete, finalization):
    """Carry observed facts into the existing readiness owner; no projection here."""
    readiness.validate_r0a_measurements(measurements)
    _need(type(materialization) is SyntheticMaterialization and type(postprocess) is PostprocessingResult
          and type(accounting) is ArchiveAccounting, "R0B_OBSERVATIONS_REQUIRED")
    _need(type(finalization) is FinalizationFact, "R0B_FINALIZATION_OBSERVATION_REQUIRED")
    FinalizationFact.__post_init__(finalization)
    _need(finalization.complete, "R0B_FINALIZATION_INCOMPLETE")
    _need(complete_wall_ns >= postprocess.complete_wall_ns + finalization.wall_ns,
          "R0B_COMPLETE_WALL_ACCOUNTING")
    _need(postprocess.bootstrap_progress_count == identity.BOOTSTRAP_REPLICATES + 1
          and postprocess.bootstrap_n == workload.selection.counts.n, "R0B_BOOTSTRAP_PROGRESS_COVERAGE")
    ArchiveAccounting.__post_init__(accounting)
    _need(finalization.stages[2][1] == accounting.archive_bytes
          and finalization.stages[1][1] < accounting.archive_bytes, "R0B_FINALIZATION_BYTE_BINDING")
    _need(tuple(n for _, n in materialization.family_counts) == workload.unit_counts
          and tuple(name for name, _ in materialization.family_counts) == _SYNTHETIC_FAMILIES,
          "R0B_REALIZED_FAMILY_COUNTS")
    _need(materialization.coordinator.status is records.AuditStatus.PASS
          and materialization.readback_complete and materialization.cleanup_complete
          and postprocess.qualification_complete and postprocess.cleanup_complete,
          "R0B_REQUIRED_COMPLETION")
    expected_seals = materialization.coordinator.streams + (materialization.identity_seal,)
    _need(type(postprocess.streams) is tuple
          and len({v.name for v in postprocess.streams}) == len(postprocess.streams)
          and tuple(sorted(postprocess.streams, key=lambda v: v.name))
              == tuple(sorted(expected_seals, key=lambda v: v.name)), "R0B_SUPPORTING_SEAL_BINDING")
    coordinator = materialization.coordinator
    expected_units = workload.unit_counts[0] + workload.unit_counts[1] + workload.unit_counts[4]
    _need(type(coordinator.receipts) is tuple and len(coordinator.receipts) == coordinator.durable_units == expected_units
          and coordinator.durable_primary_boards == workload.unit_counts[0]
          and all(type(v) is operational.UnitReceipt and v.status is records.AuditStatus.PASS
                  for v in coordinator.receipts) and not coordinator.reason_codes,
          "R0B_RECEIPT_STATUS_COVERAGE")
    _need(accounting.attributable_bytes == sum(size for _, size in materialization.family_totals),
          "R0B_ATTRIBUTABLE_ACCOUNTING")
    seals = {v.name: v for v in postprocess.streams}
    supporting = readiness.SupportingStreams(tuple(seals[name] for name in
        ("operations", "resources", qualification.IDENTITY_STREAM)), True, True, True,
        postprocess.qualification_complete, True, materialization.cleanup_complete and postprocess.cleanup_complete)
    value = readiness.R0BMeasurement(measurements[0].plan.protocol_seed, identity.CANDIDATE_MAX,
        complete_wall_ns, postprocess.phases, postprocess.bootstrap_replicates, postprocess.bootstrap_n,
        postprocess.shared_bootstrap_complete, postprocess.compact_scalar_bootstrap,
        postprocess.streaming_reconstruction, materialization.readback_complete and postprocess.readback_complete,
        postprocess.progress_bounded and finalization.complete,
        materialization.synthetic_non_evidence, materialization.family_min_bytes,
        accounting.archive_bytes, workload, supporting, accounting.fixed_allowance_bytes,
        materialization.max_unit_payload_bytes, max_combined_memory_bytes, containment_complete)
    return readiness.validate_r0b_measurement(value, measurements)


def _source_digest(provenance):
    return sha256(_canonical(_fact_node(provenance.sources))).hexdigest()


def _close_experiment_archive(root, materialization, postprocess, receipt, provenance, workload, *,
                              check=lambda: None, progress=None):
    """Close the measured archive before its external operator receipt exists.

    The internal manifest excludes only its own bytes and COMPLETE.json from
    its hash inventory. Both are subsequently included in fixed-allowance bytes.
    """
    root = Path(root)
    _need(materialization.readback_complete and materialization.cleanup_complete
          and postprocess.qualification_complete and postprocess.readback_complete and postprocess.cleanup_complete,
          "R0B_ARCHIVE_COMPLETION_REQUIRED")
    _need(progress is None or callable(progress), "FINALIZATION_PROGRESS_CALLBACK")
    def observe(stage, done, total):
        check()
        if progress is not None:
            progress(stage, done, total)
    observe("writes", 0, 4)
    _exclusive_bytes(root / "coordinator.json", _canonical(_fact_node(materialization.coordinator)))
    observe("writes", 1, 4)
    _exclusive_bytes(root / "status.json", _canonical({"state": "COMPLETED_SYNTHETIC_NON_EVIDENCE",
        "receipts_complete": True, "work_plan_revalidated": True, "resources_complete": True,
        "cleanup_complete": True, "readback_complete": True}))
    observe("writes", 2, 4)
    files = _inventory(root, check=check,
        progress=lambda done, total: observe("manifest_inventory", done, total))
    streams = tuple(sorted(postprocess.streams + (postprocess.progress_stream,), key=lambda v: v.name))
    node = {"schema": "program-k-e2-r0b-experiment/v1", "classification": "SYNTHETIC_NON_EFFECTIVENESS",
        "selection_receipt_sha256": sha256(receipt.canonical_bytes).hexdigest(),
        "provenance": _fact_node(provenance), "workload": _fact_node(workload),
        "family_totals": _fact_node(materialization.family_totals),
        "family_counts": _fact_node(materialization.family_counts),
        "family_min_bytes": _fact_node(materialization.family_min_bytes),
        "phases": _fact_node(postprocess.phases), "streams": _fact_node(streams),
        "inventory_before_manifest_receipt": _fact_node(files),
        "scope": "Every file under this experiment directory, including manifest and completion receipt, counts."}
    data = _canonical(node)
    _exclusive_bytes(root / "manifest.json", data)
    observe("writes", 3, 4)
    completion = records.CompletionReceipt(sha256(data).hexdigest(), workload.selection.counts.corpus_digest.hex(),
        _source_digest(provenance), identity.PROTOCOL_SHA256, streams, records.CompletionState.COMPLETED)
    store.write_completion_receipt(root, completion)
    _need(store.read_completion_receipt(root) == completion, "R0B_COMPLETION_READBACK")
    observe("writes", 4, 4)
    return account_experiment_archive(root, materialization, check=check,
        progress=lambda done, total: observe("accounting_inventory", done, total))


def _authorize(authorization, expected):
    _need(type(authorization) is ActualRunAuthorization and authorization is expected,
          "EXPLICIT_ACTUAL_R0_AUTHORIZATION_REQUIRED")


def _fresh_ignored_root(path):
    root = Path(path).resolve()
    results = (qualification._ROOT / "results").resolve(strict=True)
    _need(results in root.parents and not root.exists(), "FRESH_IGNORED_R0_ROOT_REQUIRED")
    for parent in root.parents:
        if parent == results:
            break
        _need(not parent.is_symlink() and not parent.is_junction(), "RUN_ROOT_LINK_FORBIDDEN")
    relative = root.relative_to(qualification._ROOT).as_posix() + "/.r0-guard"
    _need(qualification._git("check-ignore", "--", relative).strip(), "IGNORED_RUN_ROOT_REQUIRED")
    return root


def _begin_run(root, mode, receipt, provenance):
    root.mkdir(parents=True, exist_ok=False)
    try:
        _exclusive_bytes(root / "INCOMPLETE.json", _canonical({"state": "INCOMPLETE_AT_CREATION",
            "mode": mode, "source_head": provenance.r0_harness_source_head,
            "selection_sha256": sha256(receipt.canonical_bytes).hexdigest()}))
    except BaseException:
        _fail_run(root)
        raise


def _fail_run(root):
    # Retain the initial marker even if a disk failure prevents this final marker.
    # A FAILED marker always overrides any partially published completion receipt.
    try:
        _exclusive_bytes(Path(root) / "FAILED.json", _canonical({"state": "FAILED_OR_INCOMPLETE"}))
    except Exception:
        pass


def _finish_run(root, mode, receipt, provenance, details, corpus_digest, *, final_check=lambda: None):
    _need(mode in ("R0_A", "R0_B"), "R0_MODE_REQUIRED")
    files = _inventory(root)
    node = {"schema": "program-k-e2-r0-run/v1", "mode": mode,
        "classification": "OPERATIONAL_NON_EFFECTIVENESS_R0_EVIDENCE",
        "status": "COMPLETE_FOR_INDEPENDENT_REVIEW_NOT_ENVELOPE_ADMISSION",
        "provenance": _fact_node(provenance),
        "selection": {"path": receipt.path, "sha256": SELECTION_RECEIPT_SHA256,
                      "byte_length": SELECTION_RECEIPT_BYTES, "selection_source_head": SELECTION_SOURCE_HEAD},
        "amendment": {"sha256": qualification._AMENDMENT_SHA256,
                      "byte_length": qualification._AMENDMENT_BYTE_LENGTH},
        "protocol": {"sha256": identity.PROTOCOL_SHA256, "blob": qualification._BLOB},
        "details": details, "files": _fact_node(files),
        "forbidden_actions": {"actual_e2": False, "final_envelope_selected": False,
            "holdout": False, "target_recount": False, "synthetic_search": False, "project_git_mutation": False}}
    data = _canonical(node)
    _exclusive_bytes(Path(root) / "manifest.json", data)
    completion = records.CompletionReceipt(sha256(data).hexdigest(), corpus_digest,
        _source_digest(provenance), identity.PROTOCOL_SHA256, (), records.CompletionState.COMPLETED)
    result = _validate_run_manifest(Path(root), receipt, completion)
    final_check()
    store.write_completion_receipt(root, completion)
    _need(store.read_completion_receipt(root) == completion, "RUN_COMPLETION_READBACK")
    return result


def validate_existing_run(root, receipt):
    """Read-only integrity and readiness-fact verification; never select an envelope."""
    root = Path(root).resolve(strict=True)
    _need(type(receipt) is AcceptedSelectionReceipt and load_selection_receipt(receipt.path) == receipt,
          "SELECTION_RECEIPT_CHANGED")
    _need(not (root / "FAILED.json").exists(), "RUN_FAILED_OR_INCOMPLETE")
    completion = store.read_completion_receipt(root)
    return _validate_run_manifest(root, receipt, completion)


def _validate_run_manifest(root, receipt, completion):
    _need(not (root / "FAILED.json").exists(), "RUN_FAILED_OR_INCOMPLETE")
    data = (root / "manifest.json").read_bytes()
    node = _json_bytes(data)
    _need(set(node) == {"schema", "mode", "classification", "status", "provenance", "selection",
                        "amendment", "protocol", "details", "files", "forbidden_actions"}
          and node["schema"] == "program-k-e2-r0-run/v1", "RUN_MANIFEST_SCHEMA")
    _need(node["classification"] == "OPERATIONAL_NON_EFFECTIVENESS_R0_EVIDENCE"
          and node["status"] == "COMPLETE_FOR_INDEPENDENT_REVIEW_NOT_ENVELOPE_ADMISSION",
          "RUN_MANIFEST_CLASSIFICATION")
    _exact_fields(node["forbidden_actions"], {"actual_e2": False, "final_envelope_selected": False,
        "holdout": False, "target_recount": False, "synthetic_search": False, "project_git_mutation": False},
        "RUN_MANIFEST_CLASSIFICATION")
    provenance = _fact_read(node["provenance"])
    _exact_fields(_json_bytes((root / "INCOMPLETE.json").read_bytes()),
        {"state": "INCOMPLETE_AT_CREATION", "mode": node["mode"],
         "source_head": provenance.r0_harness_source_head, "selection_sha256": SELECTION_RECEIPT_SHA256},
        "RUN_INITIAL_MARKER_BINDING")
    _need(type(provenance) is RunProvenance and completion.state is records.CompletionState.COMPLETED
          and completion.manifest_sha256 == sha256(data).hexdigest()
          and completion.source_sha256 == _source_digest(provenance)
          and completion.protocol_sha256 == identity.PROTOCOL_SHA256 and completion.streams == (),
          "RUN_COMPLETION_BINDING")
    _need(node["selection"] == {"path": receipt.path, "sha256": SELECTION_RECEIPT_SHA256,
        "byte_length": SELECTION_RECEIPT_BYTES, "selection_source_head": SELECTION_SOURCE_HEAD}
        and node["amendment"] == {"sha256": qualification._AMENDMENT_SHA256,
            "byte_length": qualification._AMENDMENT_BYTE_LENGTH}
        and node["protocol"] == {"sha256": identity.PROTOCOL_SHA256, "blob": qualification._BLOB},
        "RUN_AUTHORITY_BINDING")
    _need(_inventory(root, exclude=("manifest.json", "COMPLETE.json")) == _fact_read(node["files"]),
          "RUN_ARCHIVE_DRIFT")
    details = node["details"]
    if node["mode"] == "R0_A":
        _need(set(details) == {"observations"} and details["observations"] == "r0a-observations.json",
              "R0A_MANIFEST_DETAILS")
        values, _, _ = read_r0a_evidence(root / details["observations"])
        _need(values[0].plan.protocol_seed == bytes.fromhex(identity.PROTOCOL_SHA256), "R0A_FROZEN_PROTOCOL_SEED")
        expected_digest = identity.corpus_digest(values[0].plan.protocol_seed, len(values[0].plan.ordered_indices),
                                                 values[0].plan.ordered_indices).hex()
    else:
        _need(node["mode"] == "R0_B"
              and set(details) == {"r0a", "r0a_source_manifest", "r0b", "accounting", "finalization"},
              "R0B_MANIFEST_DETAILS")
        values, value = _fact_read(details["r0a"]), _fact_read(details["r0b"])
        readiness.validate_r0b_measurement(value, values)
        _need(value.workload == receipt.workload, "R0B_SELECTION_BINDING")
        finalization = _fact_read(details["finalization"])
        _need(type(finalization) is FinalizationFact and finalization.complete
              and value.progress_bounded
              and value.complete_wall_ns >= sum(v.wall_ns for v in value.phases) + finalization.wall_ns,
              "R0B_FINALIZATION_BINDING")
        accounting = _fact_read(details["accounting"])
        _need(type(accounting) is ArchiveAccounting and _inventory(root / "experiment") == accounting.files
              and value.archive_bytes == accounting.archive_bytes
              and value.realized_fixed_allowance_bytes == accounting.fixed_allowance_bytes
              and finalization.stages[2][1] == accounting.archive_bytes
              and finalization.stages[1][1] < accounting.archive_bytes,
              "R0B_ARCHIVE_ACCOUNTING_DRIFT")
        expected_digest = value.workload.selection.counts.corpus_digest.hex()
    _need(completion.corpus_sha256 == expected_digest, "RUN_CORPUS_BINDING")
    return node


def _materialize_r0a_work(plan, envelope, run_id):
    # Called only after the public launcher's explicit authorization/source gate.
    from benchmark_board import EXPERT_GENERAL_V1, generate_board
    work = []
    for position, index in enumerate(plan.ordered_indices):
        generated = generate_board(EXPERT_GENERAL_V1, index)
        board = records.BoardIdentity(index, generated.board_fingerprint, 30, 16, 99, (0, 0),
                                      "V1", "EXPERT_GENERAL_V1")
        work.append(operational.R0Work(position, board, plan.protocol_seed, run_id, _runtime_identity()))
    return _r0a_work(plan, envelope, tuple(work))


def launch_r0a(receipt_path, root, envelopes, *, authorization=None):
    """Actual R0-A. A later operator must separately authorize this exact mode."""
    _authorize(authorization, ActualRunAuthorization.R0_A)
    receipt = load_selection_receipt(receipt_path)
    provenance = capture_run_provenance(receipt)
    _need(type(envelopes) is tuple and tuple(v.concurrency for v in envelopes) == (1, 2, 4),
          "R0A_CONCURRENCY_COVERAGE")
    for envelope in envelopes:
        operational._envelope(envelope)
    plan = readiness.build_r0a_plan(bytes.fromhex(identity.PROTOCOL_SHA256))
    root = _fresh_ignored_root(root)
    _begin_run(root, "R0_A", receipt, provenance)
    try:
        work = tuple(_materialize_r0a_work(plan, envelope, "R0-" + uuid.uuid4().hex + "-c" + str(envelope.concurrency))
                     for envelope in envelopes)
        measured, raw, traces = _measure_r0a(plan, work, envelopes, root / "r0a")
        write_r0a_evidence(root / "r0a-observations.json", measured, raw, traces)
        _recheck_provenance(receipt, provenance)
        result = _finish_run(root, "R0_A", receipt, provenance, {"observations": "r0a-observations.json"},
            identity.corpus_digest(plan.protocol_seed, len(plan.ordered_indices), plan.ordered_indices).hex(),
            final_check=lambda: _recheck_provenance(receipt, provenance))
        return result
    except BaseException:
        _fail_run(root)
        raise


def launch_r0b(receipt_path, root, r0a_root, envelope, *, authorization=None):
    """Actual R0-B; uses the selected corpus and one frozen shared bootstrap."""
    _authorize(authorization, ActualRunAuthorization.R0_B)
    receipt = load_selection_receipt(receipt_path)
    provenance = capture_run_provenance(receipt)
    prior = validate_existing_run(r0a_root, receipt)
    _need(prior["mode"] == "R0_A" and _fact_read(prior["provenance"]) == provenance,
          "R0A_CURRENT_SOURCE_REQUIRED")
    measured, _, _ = read_r0a_evidence(Path(r0a_root) / "r0a-observations.json")
    operational._envelope(envelope)
    _need(envelope in tuple(v.envelope for v in measured), "R0B_MEASURED_ENVELOPE_REQUIRED")
    sizing = readiness.derive_r0b_sizing_plan(measured)
    workload = receipt.workload
    readiness.validate_payload_fit(workload, sizing.unit_bytes, min(v.envelope.max_payload_bytes for v in measured))
    root = _fresh_ignored_root(root)
    _begin_run(root, "R0_B", receipt, provenance)
    try:
        experiment = root / "experiment"
        experiment.mkdir()
        streams = experiment / "streams"
        streams.mkdir()
        cancel = threading.Event()
        monitor = operational._R0MemoryMonitor(operational._MemoryLedger(envelope), cancel, envelope)
        monitor_live = True
        with monitor:
            plan = build_selected_work_plan(receipt, "synthetic-i7-r0b-" + uuid.uuid4().hex)
            identity_seal = qualification.write_identity(streams, plan)
            materialized = materialize_synthetic(plan, sizing.unit_bytes, envelope, streams, identity_seal,
                                                 progress=lambda *_: monitor.check())
            _need(tuple(n for _, n in materialized.family_counts) == workload.unit_counts,
                  "R0B_REALIZED_FAMILY_COUNTS")
            post_started = time.perf_counter_ns()
            def check():
                if monitor_live:
                    monitor.check()
                else:
                    _need(monitor.reason is None, "R0B_CONTAINMENT_INCOMPLETE")
                _need(time.perf_counter_ns() - post_started < envelope.max_launcher_wall_ms * 1_000_000,
                      "R0B_COMPLETE_POSTPROCESS_TIMEOUT")
            postprocess = _postprocess_r0b(plan, materialized.coordinator, identity_seal, streams, envelope,
                                           experiment / "postprocessing", progress=lambda *_: check())
            finalizing = _FinalizationObserver(check)
            accounting = _close_experiment_archive(experiment, materialized, postprocess, receipt,
                provenance, workload, check=check, progress=finalizing.observe)
            finalizing.observe("source_recheck", 0, 1)
            _recheck_provenance(receipt, provenance)
            finalizing.observe("source_recheck", 1, 1)
            finalizing.observe("cleanup", 0, 1)
        monitor_live = False
        finalizing.observe("cleanup", 1, 1)
        finalization = finalizing.finish()
        wall = time.perf_counter_ns() - post_started
        value = adapt_r0b(measured, workload, materialized, postprocess, accounting,
            complete_wall_ns=wall, max_combined_memory_bytes=max(monitor.combined,
                materialized.max_coordinator_memory_bytes), containment_complete=monitor.reason is None,
            finalization=finalization)
        details = {"r0a": _fact_node(measured), "r0b": _fact_node(value), "accounting": _fact_node(accounting),
            "finalization": _fact_node(finalization),
            "r0a_source_manifest": sha256((Path(r0a_root) / "manifest.json").read_bytes()).hexdigest()}
        _recheck_provenance(receipt, provenance)
        result = _finish_run(root, "R0_B", receipt, provenance, details, workload.selection.counts.corpus_digest.hex(),
                             final_check=lambda: _recheck_provenance(receipt, provenance))
        return result
    except BaseException:
        _fail_run(root)
        raise
# EVIDENCE_LAUNCH_END
