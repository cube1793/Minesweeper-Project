"""D1: read-only presentation of the accepted E1 K-P0 evidence, using stdlib only.

This is a closed reader for ONE historical publication, not an E1 codec, solver,
replay evaluator, Stage3Execution producer, or production algorithm entry point.
The bytes of the publication, completion receipt and Model-C profile are pinned
before parsing. No artifact-selected imports or historical class constructors
are used. Archived PASS records are bound and inspected, never recomputed.

Frame k is after exactly k physical inputs: M(0) is empty and M(k) is the
preceding trace's preinput_M. Terminal answer data never supplies knowledge.
E1 qualification is not Actual E2, effectiveness evidence, or Gate-P approval.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct


ACCEPTED_RUN_ID = "e1-20261022T003214Z-fba3da048d46"
QUALIFICATION_SHA256 = "1f2a6ee1801f8ea498d4f8844df80d5b4f8f481752e874c5bff67f2da41da05a"
QUALIFICATION_SIZE = 30_701_850
COMPLETE_SHA256 = "bb6301b2245d5affec9604568b49557100227436946b0934b94d972d53a7e544"
COMPLETE_SIZE = 1_260
PROFILE_SHA256 = "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b"
PROFILE_SIZE = 6_059
TABLE_SHA256 = "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b"
SPEC_SHA256 = "3e26c5b36d590e90bbd34951ee869cf63ed4f89b6cd3657a059132d065669903"
PROTOCOL_SHA256 = "43504d42d6c921c8291ed6c2a61cf198d2c64aaec2fb1f443caa59fbd59a91af"
MODEL_ID = "overlap_floor_log2_distance_v1"
K_SCHEDULE_INDICES = tuple(range(2, 54, 3))
_CASE_IDS = ("S-WIN", "S-LIFECYCLE", "S-REPLAN", "S-LOSS",
             "X-0", "X-1", "X-2", "X-3", "X-100000")
_QUALIFICATION_SOURCE = "939664757a5c308f599b6cf80eb0ac07081998e1fead5f465f5706ebe7071906"
_OPERATIONAL_SOURCE = "c538ef92a751e5cbb3d6cafd2a5a9cf8c0a154151161c797a77f340f372a78d5"
_PLAN_SOURCE = "8f60ef5ff1590f855562d5d6c58e0b3333f213da267ad742c1bf9e98b6edcb24"
_ENVELOPE = "d422d72721b0fd62f123d6397ae97e833bc616b604073bc3facadcade8a2dd65"
_DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / "calibration/stage3_physical_profile_v1.json"
NO_EFFECTIVENESS_CLAIM = "Not statistically representative; not E2 effectiveness evidence."
RESEARCH_SCOPE = "Program K Research Trace Viewer / Demo; not production or Gate-P qualification."

# Public-observation glyphs are the archived wire values, not an Engine import.
HIDDEN, FLAGGED, EXPLODED, MINE, FALSE_FLAG = -2, -3, -4, -5, -6
Coord = tuple[int, int]
Observation = tuple[tuple[int, ...], ...]


class KTraceAdapterError(ValueError):
    """Unaccepted, incomplete, corrupt, or inconsistent presentation input."""


def _need(condition, message):
    if not condition:
        raise KTraceAdapterError(message)


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    artifact_sha256: str
    node_index: int
    record_type: str


@dataclass(frozen=True, slots=True)
class HistoricalSourceFile:
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class KTraceProvenance:
    run_id: str
    qualification_sha256: str
    qualification_size: int
    complete_sha256: str
    qualification_source_digest: str
    operational_source_digest: str
    plan_source_digest: str
    base_source_digest: str
    execution_source_digest: str
    audit_source_digest: str
    spec_sha256: str
    protocol_sha256: str
    profile_sha256: str
    table_sha256: str
    model_id: str
    source_files: tuple[HistoricalSourceFile, ...]
    historical_runtime: tuple[tuple[str, str], ...]
    scope: str = RESEARCH_SCOPE
    no_effectiveness_claim: str = NO_EFFECTIVENESS_CLAIM


@dataclass(frozen=True, slots=True)
class KCaseIdentity:
    case_id: str
    schedule_index: int
    repetition: int
    variant: str
    width: int
    height: int
    num_mines: int
    first_click: Coord
    board_fingerprint: str
    source_type: str
    benchmark_set_id: str | None
    board_generator_version: str | None
    seed_scheme: str | None
    game_index: int | None
    seed: int | None
    fixture_id: str | None
    provenance: str
    permitted_claims: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KAcquisitionView:
    input_index: int
    target: Coord
    kind: str
    retained_mines: frozenset[Coord]
    certificate: EvidenceReference
    accepted_audit: EvidenceReference


@dataclass(frozen=True, slots=True)
class KActionView:
    input_index: int
    action: str
    target: Coord
    cursor_before: Coord
    modeled_action_us: int
    cumulative_modeled_us: int
    status_after: str
    category: str
    M_before: frozenset[Coord]
    preinput_M: frozenset[Coord]
    safe_cells_opened_delta: int
    explicit_flag_delta: int
    acquisitions: tuple[KAcquisitionView, ...]
    trace: EvidenceReference
    effect: EvidenceReference
    selection: EvidenceReference | None


@dataclass(frozen=True, slots=True)
class KTraceFrame:
    index: int
    observation: Observation
    status: str
    cursor: Coord
    cumulative_modeled_us: int
    logical_mines: frozenset[Coord]
    explicit_flags: frozenset[Coord]
    automatic_flags: frozenset[Coord]

    @property
    def hidden_logical_mines(self) -> frozenset[Coord]:
        return frozenset((x, y) for x, y in self.logical_mines
                         if self.observation[y][x] == HIDDEN)

    @property
    def public_flags(self) -> frozenset[Coord]:
        return _cells(self.observation, FLAGGED)


@dataclass(frozen=True, slots=True)
class TerminalAnswerReference:
    """Answer/reference data only. Never a source for a frame's logical M."""

    mines: frozenset[Coord]
    board_fingerprint: str
    terminal_effect: EvidenceReference


@dataclass(frozen=True, slots=True)
class KTracePresentation:
    provenance: KTraceProvenance
    case: KCaseIdentity
    actions: tuple[KActionView, ...]
    frames: tuple[KTraceFrame, ...]
    answer_reference: TerminalAnswerReference

    def frame(self, index: int) -> KTraceFrame:
        _need(type(index) is int and 0 <= index < len(self.frames), "Invalid frame index.")
        return self.frames[index]

    def completed_route(self, index: int) -> tuple[Coord, ...]:
        self.frame(index)
        return tuple(action.target for action in self.actions[:index])

    @property
    def terminal_status(self) -> str:
        return self.frames[-1].status

    @property
    def total_modeled_us(self) -> int:
        return self.frames[-1].cumulative_modeled_us


class _Graph:
    """Selective wire access; deliberately does not reconstruct E1 objects."""

    def __init__(self, wire):
        _need(type(wire) is list and len(wire) == 3 and wire[0] == "e1-dag-v1",
              "Unknown evidence encoding.")
        self.root, self.nodes = wire[1:]
        _need(type(self.nodes) is list and 0 < len(self.nodes) <= 194_219,
              "Invalid evidence node count.")
        self.node(self.root)

    def node(self, index):
        _need(type(index) is int and 0 <= index < len(self.nodes), "Invalid evidence reference.")
        node = self.nodes[index]
        _need(type(node) is list and node and type(node[0]) is str, "Invalid evidence node.")
        return node

    def _refs(self, index, refs):
        _need(type(refs) is list and all(type(r) is int and 0 <= r < index for r in refs),
              "Evidence references must point backward.")
        return tuple(refs)

    def record(self, index, expected):
        node = self.node(index)
        _need(len(node) == 3 and node[:2] == ["record", expected]
              and type(node[2]) is list, "Unexpected evidence record: " + expected)
        result = {}
        for field in node[2]:
            _need(type(field) is list and len(field) == 2 and type(field[0]) is str
                  and field[0] not in result, "Invalid or duplicate record field.")
            self._refs(index, [field[1]])
            result[field[0]] = field[1]
        return result

    def sequence(self, index, tag="tuple"):
        node = self.node(index)
        _need(len(node) == 2 and node[0] == tag, "Unexpected evidence collection.")
        return self._refs(index, node[1])

    def scalar(self, index):
        node = self.node(index)
        if node == ["none"]:
            return None
        _need(len(node) == 2, "Expected scalar evidence.")
        tag, value = node
        if tag == "int":
            _need(type(value) is str and len(value) <= 100_000, "Invalid integer encoding.")
            try:
                parsed = int(value, 16)
            except ValueError as exc:
                raise KTraceAdapterError("Invalid integer encoding.") from exc
            _need(hex(parsed) == value, "Noncanonical integer encoding.")
            return parsed
        _need((tag == "str" and type(value) is str)
              or (tag == "bool" and type(value) is bool), "Unexpected scalar evidence.")
        return value

    def integer(self, index):
        value = self.scalar(index)
        _need(type(value) is int, "Expected an exact integer.")
        return value

    def enum(self, index, kind, allowed):
        node = self.node(index)
        _need(len(node) == 3 and node[:2] == ["enum", "core_engine." + kind]
              and node[2] in allowed, "Unexpected archived enum.")
        return node[2]

    def coord(self, index, width, height):
        refs = self.sequence(index)
        _need(len(refs) == 2, "Expected a coordinate.")
        x, y = (self.integer(r) for r in refs)
        _need(0 <= x < width and 0 <= y < height, "Coordinate outside the case.")
        return x, y

    def cells(self, index, width, height):
        refs = self.sequence(index, "frozenset")
        result = frozenset(self.coord(r, width, height) for r in refs)
        _need(len(result) == len(refs), "Duplicate cell in set.")
        return result

    def grid(self, index, width, height, status):
        rows = self.sequence(index)
        _need(len(rows) == height, "Observation height mismatch.")
        result = []
        for row in rows:
            refs = self.sequence(row)
            _need(len(refs) == width, "Observation width mismatch.")
            values = tuple(self.integer(r) for r in refs)
            allowed = {HIDDEN, FLAGGED} if status == "PLAYING" else {FLAGGED, EXPLODED, MINE, FALSE_FLAG}
            if status == "LOST":
                allowed.add(HIDDEN)  # Loss reveals mines, not unopened safe cells.
            _need(all(v in allowed or 0 <= v <= 8 for v in values), "Invalid public observation.")
            result.append(values)
        return tuple(result)

    def reference(self, index):
        node = self.node(index)
        _need(node[0] == "record" and len(node) == 3, "Expected record reference.")
        return EvidenceReference(QUALIFICATION_SHA256, index, node[1])

    def plain(self, index, depth=0):
        # Only small source/receipt/runtime records use this projection. No
        # recursive decoding of decisions, certificates, or qualification runs.
        _need(depth <= 16, "Source identity nesting exceeds the accepted shape.")
        node = self.node(index)
        if node[0] == "record":
            return {k: self.plain(v, depth + 1) for k, v in self.record(index, node[1]).items()}
        if node[0] == "tuple":
            return [self.plain(v, depth + 1) for v in self.sequence(index)]
        return self.scalar(index)


def _record(graph, index, module, name):
    return graph.record(index, "experiments.program_k_" + module + "." + name)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def _pinned_json(data, size, digest, label):
    _need(type(data) is bytes and len(data) == size, label + " byte size mismatch.")
    _need(hashlib.sha256(data).hexdigest() == digest, label + " SHA-256 mismatch.")
    try:
        return json.loads(data)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise KTraceAdapterError(label + " is not valid JSON.") from exc


def _timing_table(profile):
    _need(profile["model_id"] == MODEL_ID and profile["table_sha256"] == TABLE_SHA256
          and profile["table_dimensions"] == [30, 16]
          and profile["table_order"] == "dx_major_dy_minor"
          and profile["timing_unit"] == "us" and profile["timing_tick_unit"] == "1_us",
          "Model-C profile contract mismatch.")
    table = profile["timing_table_us"]
    _need(type(table) is list and len(table) == 30
          and all(type(row) is list and len(row) == 16
                  and all(type(v) is int and v > 0 for v in row) for row in table),
          "Invalid Model-C timing table.")
    encoded = ",".join(str(v) for row in table for v in row).encode("ascii")
    _need(hashlib.sha256(encoded).hexdigest() == TABLE_SHA256, "Model-C table digest mismatch.")
    return tuple(tuple(row) for row in table)


def _sources(graph, root, marker):
    source = graph.plain(root["source_identity"])
    operational = source["operational_source_identity"]
    plan = operational["plan_source_identity"]
    execution = operational["execution_source_identity"]
    audit = operational["audit_source_identity"]
    suite = operational["suite_source_identity"]
    execution_digest, audit_digest = _digest(execution), _digest(audit)
    _need(_digest(source) == marker["qualification_source_digest"] == _QUALIFICATION_SOURCE
          and _digest(operational) == marker["operational_source_digest"] == _OPERATIONAL_SOURCE
          and _digest(plan) == marker["plan_source_digest"] == _PLAN_SOURCE
          and execution["plan_source_digest"] == _PLAN_SOURCE
          and audit["execution_source_digest"] == execution_digest
          and suite["audit_source_digest"] == audit_digest, "Historical source chain mismatch.")
    authority = dict(spec_sha256=SPEC_SHA256, protocol_sha256=PROTOCOL_SHA256,
                     model_id=MODEL_ID, profile_sha256=PROFILE_SHA256, table_sha256=TABLE_SHA256)
    for identity in (source, operational, plan, execution, audit, suite):
        _need(all(identity[k] == v for k, v in authority.items()), "Frozen authority mismatch.")
    plan_record = _record(graph, root["plan"], "e1_harness", "E1Plan")
    _need(graph.plain(plan_record["source_identity"]) == plan, "Plan source binding mismatch.")
    runtime = graph.plain(plan_record["runtime"])
    _need(all(type(k) is str and type(v) is str for k, v in runtime.items()), "Invalid runtime identity.")
    files = (plan["files"] + [execution["execution_file"], audit["audit_file"], suite["suite_file"]]
             + operational["files"] + source["files"])
    provenance = KTraceProvenance(
        ACCEPTED_RUN_ID, QUALIFICATION_SHA256, QUALIFICATION_SIZE, COMPLETE_SHA256,
        _QUALIFICATION_SOURCE, _OPERATIONAL_SOURCE, _PLAN_SOURCE, plan["base_source_digest"], execution_digest,
        audit_digest, SPEC_SHA256, PROTOCOL_SHA256, PROFILE_SHA256, TABLE_SHA256, MODEL_ID,
        tuple(HistoricalSourceFile(**item) for item in files), tuple(sorted(runtime.items())))
    return provenance, plan_record, execution, audit


def _cells(observation, *glyphs):
    return frozenset((x, y) for y, row in enumerate(observation)
                     for x, value in enumerate(row) if value in glyphs)


def _move(graph, index, width, height, effect=False):
    expected = ("experiments.program_k_evidence.MoveProjection" if effect
                else "simple_algorithm.SimpleMove")
    move = graph.record(index, expected)
    action = graph.enum(move["action"], "Action", ("OPEN", "FLAG", "CHORD"))
    x, y = graph.integer(move["x"]), graph.integer(move["y"])
    _need(0 <= x < width and 0 <= y < height, "Action target outside the case.")
    return action, (x, y)


def _fingerprint(width, height, num_mines, mines):
    # Frozen MSLAYOUT1 wire contract; no board generation or Engine creation.
    wire = b"MSLAYOUT1\0" + struct.pack(">III", width, height, num_mines)
    wire += b"".join(struct.pack(">II", x, y) for x, y in sorted(mines, key=lambda c: (c[1], c[0])))
    return hashlib.sha256(wire).hexdigest()


def _case(graph, archive, audit, operation, plan, index):
    schedule_ref = archive["schedule_entry"]
    schedule = _record(graph, schedule_ref, "e1_harness", "ScheduleEntry")
    schedules = graph.sequence(plan["schedule"])
    cases = graph.sequence(plan["cases"])
    _need(len(schedules) == 54 and len(cases) == 9
          and schedules[index] == schedule_ref and archive["case"] == cases[index // 6]
          and audit["schedule_entry"] == schedule_ref and audit["case"] == archive["case"],
          "Schedule/case evidence binding mismatch.")
    raw = _record(graph, archive["case"], "e1_harness", "SealedCaseRegistration")
    width, height, count = (graph.integer(raw[k]) for k in ("width", "height", "num_mines"))
    _need(0 < width <= 30 and 0 < height <= 16 and 0 < count < width * height, "Invalid case dimensions.")
    case_id, repetition = _CASE_IDS[index // 6], (index % 6) // 3 + 1
    for record in (schedule, operation):
        _need(graph.integer(record["schedule_index"]) == index
              and graph.scalar(record["case_id"]) == case_id
              and graph.integer(record["repetition"]) == repetition
              and graph.scalar(record["variant"]) == "K-P0", "Selected schedule identity mismatch.")
    _need(graph.scalar(schedule["fresh_state_required"]) is True
          and graph.scalar(raw["case_id"]) == case_id
          and graph.scalar(audit["variant"]) == "K-P0"
          and graph.integer(audit["repetition"]) == repetition
          and graph.scalar(raw["statistically_representative"]) is False
          and graph.scalar(raw["e2_effectiveness_evidence"]) is False
          and graph.scalar(raw["no_effectiveness_claim"]) == NO_EFFECTIVENESS_CLAIM,
          "Case scope or repetition mismatch.")
    receipt = _record(graph, archive["receipt"], "e1_execution", "CaseMaterializationReceipt")
    for name in ("case_id", "source_type", "width", "height", "num_mines", "first_click",
                 "game_index", "seed", "board_fingerprint", "runtime"):
        _need(receipt[name] == raw[name], "Materialization receipt/case mismatch: " + name)
    _need(graph.scalar(receipt["fresh_engine"]) is True, "Case was not materialized fresh.")
    return KCaseIdentity(
        case_id, index, repetition, "K-P0", width, height, count,
        graph.coord(raw["first_click"], width, height), graph.scalar(raw["board_fingerprint"]),
        *(graph.scalar(raw[k]) for k in ("source_type", "benchmark_set_id", "board_generator_version",
                                        "seed_scheme", "game_index", "seed", "fixture_id", "provenance")),
        tuple(graph.scalar(r) for r in graph.sequence(raw["permitted_claims"])))


def _acquisitions(graph, selection_ref, audit_refs, index, case, before, cursor,
                  move, category, old_M, new_M):
    w, h = case.width, case.height
    selection = _record(graph, selection_ref, "policy", "PolicySelection")
    _need(graph.coord(selection["cursor"], w, h) == cursor
          and _move(graph, selection["move"], w, h) == move
          and graph.scalar(selection["category"]) == category
          and graph.scalar(selection["failure_code"]) is None, "Selection/action binding mismatch.")
    decision = _record(graph, selection["evidence"], "capability", "DecisionAnalysis")
    local = _record(graph, decision["local"], "capability", "LocalAnalysis")
    local_before = _record(graph, local["before"], "capability", "Accounting")
    local_after = _record(graph, local["after"], "capability", "Accounting")
    after = _record(graph, decision["after"], "capability", "Accounting")
    local_M = graph.cells(local_after["M"], w, h)
    _need(graph.grid(decision["observation"], w, h, "PLAYING") == before
          and graph.integer(decision["num_mines"]) == case.num_mines
          and graph.cells(local_before["M"], w, h) == old_M
          and graph.cells(after["M"], w, h) == new_M
          and old_M <= local_M <= new_M, "M_before -> preinput_M chronology mismatch.")
    certificates = (("LOCAL", graph.sequence(local["certificates"]), old_M),
                    ("EXACT_GLOBAL", graph.sequence(decision["exact_certificates"]), local_M))
    acquired = []
    phase_targets = {}
    for kind, refs, retained in certificates:
        targets = set()
        for certificate_ref in refs:
            cert = _record(graph, certificate_ref, "oracles",
                           "LocalMineCertificate" if kind == "LOCAL" else "ExactGlobalMineCertificate")
            target = graph.coord(cert["target"], w, h)
            _need(target not in targets and target not in retained and before[target[1]][target[0]] == HIDDEN
                  and graph.grid(cert["observation"], w, h, "PLAYING") == before
                  and graph.integer(cert["num_mines"]) == case.num_mines
                  and graph.enum(cert["status"], "GameStatus", ("PLAYING",)) == "PLAYING"
                  and graph.cells(cert["retained_mines"], w, h) == retained,
                  "Acquisition certificate/boundary mismatch.")
            key = index, certificate_ref
            _need(key in audit_refs, "Missing accepted acquisition audit.")
            audit_ref = audit_refs.pop(key)
            check = _record(graph, audit_ref, "harness", "AcquisitionAudit")
            checked = _record(graph, check["certificate_check"], "oracles",
                              "LocalCertificateCheck" if kind == "LOCAL" else "ExactGlobalCertificateCheck")
            _need(graph.coord(checked["target"], w, h) == target
                  and not graph.sequence(check["external_flags"]), "Acquisition audit proof binding mismatch.")
            owned_before = graph.cells(check["owned_M_before"], w, h)
            owned_after = graph.cells(check["owned_M_after"], w, h)
            # AcquisitionAudit describes ONE certificate, not sequential batch
            # accumulation (program_k_harness.AcquisitionAudit). The phase M
            # snapshots above/below are the simultaneous batch authority.
            _need(owned_before == retained
                  and owned_after == owned_before | {target}, "Acquisition audit M chronology mismatch.")
            acquired.append(KAcquisitionView(index, target, kind, retained,
                                             graph.reference(certificate_ref), graph.reference(audit_ref)))
            targets.add(target)
        phase_targets[kind] = frozenset(targets)
    _need(local_M == old_M | phase_targets["LOCAL"]
          and graph.cells(local["acquired_mines"], w, h) == phase_targets["LOCAL"]
          and new_M == local_M | phase_targets["EXACT_GLOBAL"], "Unauthenticated logical mine addition.")
    return tuple(acquired)


def _project_run(graph, operation_ref, index, plan, execution_source, audit_source, provenance, table):
    operation = _record(graph, operation_ref, "e1_operational", "E1OperationResult")
    archive = _record(graph, operation["archive"], "e1_execution", "E1ScheduledRunArchive")
    audit = _record(graph, operation["audit"], "e1_audit", "E1RunAudit")
    receipt = _record(graph, operation["receipt"], "e1_operational", "E1OperationReceipt")
    _need(graph.scalar(archive["completion_status"]) == "COMPLETE"
          and graph.scalar(receipt["status"]) == "COMPLETE"
          and graph.scalar(receipt["operation_kind"]) == "SCHEDULED_RUN"
          and graph.scalar(receipt["operation_id"]) == f"SCHEDULED_RUN:{index:02d}"
          and graph.integer(receipt["exit_code"]) == 0
          and graph.scalar(receipt["reason"]) is None
          and graph.scalar(receipt["operational_source_digest"]) == _OPERATIONAL_SOURCE
          and graph.scalar(receipt["envelope_digest"]) == _ENVELOPE, "Incomplete scheduled execution.")
    _need(graph.plain(archive["execution_source_identity"]) == execution_source
          and graph.plain(audit["source_identity"]) == audit_source
          and graph.scalar(archive["plan_source_digest"]) == _PLAN_SOURCE
          and graph.scalar(audit["execution_source_digest"]) == provenance.execution_source_digest,
          "Run historical source binding mismatch.")
    _need(graph.scalar(audit["audit_status"]) == "PASS"
          and not graph.sequence(audit["discrepancies"])
          and not graph.sequence(audit["incomplete_reasons"]), "Run audit is incomplete or failed.")
    case = _case(graph, archive, audit, receipt, plan, index)
    w, h = case.width, case.height
    result = _record(graph, archive["result"], "runner", "KRunResult")
    traces = graph.sequence(result["traces"])
    costs, replays = (graph.sequence(audit[k]) for k in ("cost_audits", "replay_audits"))
    _need(0 < len(traces) <= w * h and len(costs) == len(replays) == len(traces)
          and graph.integer(receipt["physical_inputs"]) == len(traces), "Incomplete action/audit stream.")
    public_audit = _record(graph, audit["public_effect_audit"], "evidence", "EvidenceComparison")
    _need(graph.scalar(public_audit["status"]) == "PASS"
          and not graph.sequence(public_audit["mismatches"]), "Public effect audit did not pass.")
    audit_refs = {}
    for ref in graph.sequence(audit["acquisition_audits"]):
        acquired = _record(graph, ref, "harness", "AcquisitionAudit")
        key = graph.integer(acquired["boundary"]), acquired["certificate"]
        _need(key not in audit_refs and 0 < key[0] < len(traces)
              and graph.scalar(acquired["status"]) == "PASS", "Invalid acquisition audit.")
        audit_refs[key] = ref
    hidden = tuple((HIDDEN,) * w for _ in range(h))
    frames = [KTraceFrame(0, hidden, "PLAYING", case.first_click, 0, frozenset(), frozenset(), frozenset())]
    actions = []
    for i, trace_ref in enumerate(traces):
        trace = _record(graph, trace_ref, "runner", "KActionTrace")
        effect = _record(graph, trace["public_effect"], "evidence", "PublicEffectRecord")
        cost = _record(graph, costs[i], "e1_audit", "ModelCCostAudit")
        replay = _record(graph, replays[i], "e1_audit", "KReplayAudit")
        prior = frames[-1]
        status = graph.enum(trace["status_after"], "GameStatus", ("PLAYING", "WON", "LOST"))
        _need(prior.status == "PLAYING" and (status != "PLAYING") == (i == len(traces) - 1),
              "Terminal status is missing or occurs before the last input.")
        _need(all(graph.integer(r["input_index"]) == i for r in (trace, effect, cost, replay)),
              "Action/effect/audit order mismatch.")
        _need(graph.scalar(trace["public_effect_status"]) == "CAPTURED"
              and graph.scalar(effect["capture_method"]) == "STATUS_GATED_ACTUAL_EXECUTION"
              and graph.scalar(effect["archival_only"]) is True
              and graph.enum(effect["status_before"], "GameStatus", ("PLAYING",)) == "PLAYING"
              and graph.enum(effect["status_after"], "GameStatus", ("PLAYING", "WON", "LOST")) == status,
              "Public effect capture/status mismatch.")
        before = graph.grid(effect["before_observation"], w, h, "PLAYING")
        archived_after = _record(graph, effect["after_observation"], "evidence", "ArchivalObservation")
        _need(graph.scalar(archived_after["archival_only"]) is True
              and graph.enum(archived_after["status"], "GameStatus", ("PLAYING", "WON", "LOST")) == status,
              "Archival observation/status mismatch.")
        after = graph.grid(archived_after["rows"], w, h, status)
        move = _move(graph, trace["move"], w, h)
        action, target = move
        cursor = graph.coord(trace["cursor_before"], w, h)
        _need(before == prior.observation and cursor == prior.cursor
              and graph.coord(effect["cursor_before"], w, h) == cursor
              and graph.coord(effect["cursor_after"], w, h) == target
              and _move(graph, effect["move"], w, h, effect=True) == move,
              "Observation, target, or cursor continuity mismatch.")
        modeled = table[abs(target[0] - cursor[0])][abs(target[1] - cursor[1])]
        _need(graph.integer(trace["modeled_action_us"]) == graph.integer(effect["modeled_action_us"]) == modeled
              and all(graph.integer(cost[k]) == modeled for k in ("expected_us", "trace_us", "effect_us"))
              and graph.scalar(cost["status"]) == "PASS", "Exact Model-C cost mismatch.")
        old_M, new_M = (graph.cells(trace[k], w, h) for k in ("M_before", "preinput_M"))
        _need(old_M == prior.logical_mines and old_M <= new_M
              and new_M <= _cells(before, HIDDEN, FLAGGED)
              and prior.explicit_flags <= old_M, "Logical/physical state separation mismatch.")
        category = graph.scalar(trace["category"])
        if i == 0:
            _need(move == ("OPEN", case.first_click) and category == "POLICY_INITIAL_OPEN"
                  and not old_M and not new_M and graph.scalar(trace["selection"]) is None,
                  "Initial OPEN contract mismatch.")
            acquisitions, selection_ref = (), None
        else:
            _need({"DIRECT_SAFE_OPEN": "OPEN", "EXACT_MINIMUM_RISK_GUESS": "OPEN",
                   "SETUP_CHORD": "FLAG", "DIRECT_CHORD": "CHORD"}.get(category) == action,
                  "Action/category mismatch.")
            acquisitions = _acquisitions(graph, trace["selection"], audit_refs, i, case,
                                         before, cursor, move, category, old_M, new_M)
            selection_ref = graph.reference(trace["selection"])
        for field in ("decision_status", "policy_status"):
            _need(graph.scalar(replay[field]) == ("PASS" if i else "NOT_APPLICABLE"),
                  "Archived replay audit did not pass.")
        for part in ("decision", "selection"):
            archived = graph.scalar(replay["archived_" + part + "_digest"])
            replayed = graph.scalar(replay["replayed_" + part + "_digest"])
            _need(archived == replayed and (type(archived) is str if i else archived is None),
                  "Archived replay audit digest mismatch.")
        x, y = target
        explicit = prior.explicit_flags
        if action == "FLAG":
            _need(before[y][x] == HIDDEN and target in new_M and status == "PLAYING"
                  and after[y][x] == FLAGGED, "Physical FLAG is not a known-mine materialization.")
            explicit = explicit | {target}
        elif action == "OPEN":
            _need(before[y][x] == HIDDEN and target not in new_M, "Invalid archived OPEN target.")
        else:
            adjacent_flags = sum(before[ny][nx] == FLAGGED
                                 for ny in range(max(0, y - 1), min(h, y + 2))
                                 for nx in range(max(0, x - 1), min(w, x + 2)) if (nx, ny) != target)
            _need(0 < before[y][x] <= 8 and adjacent_flags == before[y][x], "Invalid CHORD target.")
        safe_delta = sum(old in (HIDDEN, FLAGGED) and 0 <= new <= 8
                         for row0, row1 in zip(before, after) for old, new in zip(row0, row1))
        _need(graph.integer(effect["safe_cells_opened_delta"]) == safe_delta
              and graph.integer(effect["explicit_flag_delta"]) == int(action == "FLAG"),
              "Public effect work counters mismatch.")
        _need(all(old == HIDDEN or old == new
                  for row0, row1 in zip(before, after) for old, new in zip(row0, row1)),
              "Previously public cells changed unexpectedly.")
        public_flags = _cells(after, FLAGGED)
        automatic = public_flags - explicit if status == "WON" else frozenset()
        _need(explicit <= new_M and public_flags == explicit | automatic,
              "Public flags disagree with executed FLAG actions.")
        if action == "FLAG":
            _need(sum(a != b for r0, r1 in zip(before, after) for a, b in zip(r0, r1)) == 1,
                  "FLAG effect changed other cells.")
        if status == "PLAYING":
            _need(len(_cells(after, HIDDEN)) < len(_cells(before, HIDDEN)), "No physical input progress.")
        total = prior.cumulative_modeled_us + modeled
        frames.append(KTraceFrame(i + 1, after, status, target, total, new_M, explicit, automatic))
        actions.append(KActionView(i, action, target, cursor, modeled, total, status, category,
                                   old_M, new_M, safe_delta, int(action == "FLAG"), acquisitions,
                                   graph.reference(trace_ref), graph.reference(trace["public_effect"]), selection_ref))
    final = frames[-1]
    _need(not audit_refs and graph.cells(result["final_M"], w, h) == final.logical_mines
          and graph.enum(result["status"], "GameStatus", ("WON", "LOST")) == final.status
          and graph.integer(audit["expected_total_us"]) == graph.integer(audit["recorded_total_us"])
          == final.cumulative_modeled_us, "Final state/cost/acquisition mismatch.")
    mines = _cells(final.observation, FLAGGED, EXPLODED, MINE)
    _need(len(mines) == case.num_mines
          and _fingerprint(w, h, case.num_mines, mines) == case.board_fingerprint,
          "Terminal layout fingerprint mismatch.")
    _need((final.status == "WON" and not _cells(final.observation, EXPLODED, MINE, FALSE_FLAG))
          or (final.status == "LOST" and bool(_cells(final.observation, EXPLODED))),
          "Terminal observation/result mismatch.")
    return KTracePresentation(provenance, case, tuple(actions), tuple(frames),
                              TerminalAnswerReference(mines, case.board_fingerprint, actions[-1].effect))


def _indices(schedule_indices):
    _need(type(schedule_indices) is tuple and 0 < len(schedule_indices) <= 18
          and all(type(i) is int and i in K_SCHEDULE_INDICES for i in schedule_indices)
          and len(set(schedule_indices)) == len(schedule_indices),
          "Select unique K-P0 schedule indices from the accepted E1 publication.")
    return schedule_indices


def project_accepted_e1_traces(qualification_bytes: bytes, complete_bytes: bytes,
                              profile_bytes: bytes, *, schedule_indices: tuple[int, ...]
                              ) -> tuple[KTracePresentation, ...]:
    """Project selected completed K runs; reject any different artifact or profile.

    No caller-supplied trust roots or permissive loading mode. The returned
    tuple is all-or-nothing. Nothing is published before all selections pass.
    Historical source digests describe the accepted evidence, not today's code.
    """
    indices = _indices(schedule_indices)
    # Check all three identities before any graph traversal or projection.
    marker_graph = _Graph(_pinned_json(complete_bytes, COMPLETE_SIZE, COMPLETE_SHA256, "COMPLETE"))
    graph = _Graph(_pinned_json(qualification_bytes, QUALIFICATION_SIZE, QUALIFICATION_SHA256, "Qualification"))
    profile = _pinned_json(profile_bytes, PROFILE_SIZE, PROFILE_SHA256, "Model-C profile")
    try:
        marker = marker_graph.plain(marker_graph.root)
        _record(marker_graph, marker_graph.root, "e1_persistence", "E1ArtifactReceipt")
        _need(marker["run_id"] == ACCEPTED_RUN_ID and marker["content_sha256"] == QUALIFICATION_SHA256
              and marker["size_bytes"] == QUALIFICATION_SIZE and marker["completion_marker"] == "COMPLETE"
              and marker["verdict"] == "E1_PASS" and marker["readiness"] == "E1_QUALIFIED"
              and marker["envelope_digest"] == _ENVELOPE and marker["protocol_sha256"] == PROTOCOL_SHA256,
              "Accepted publication receipt mismatch.")
        root = _record(graph, graph.root, "e1_qualification", "E1QualificationRecord")
        _need(graph.scalar(root["run_id"]) == ACCEPTED_RUN_ID
              and graph.scalar(root["purpose"]) == "E1_QUALIFICATION", "Qualification identity mismatch.")
        provenance, plan, execution_source, audit_source = _sources(graph, root, marker)
        table = _timing_table(profile)
        operations = graph.sequence(root["scheduled_results"])
        _need(len(operations) == 54, "Incomplete accepted schedule.")
        return tuple(_project_run(graph, operations[i], i, plan, execution_source, audit_source,
                                  provenance, table) for i in indices)
    except (KeyError, TypeError, IndexError, RecursionError) as exc:
        raise KTraceAdapterError("Incomplete or malformed selected evidence.") from exc


def _read_bounded(path, size):
    _need(not path.is_symlink() and not path.is_junction() and path.is_file(),
          "Evidence must be a regular file: " + str(path))
    with path.open("rb") as stream:
        data = stream.read(size + 1)
    _need(len(data) == size, "Evidence byte size mismatch: " + str(path))
    return data


def load_accepted_e1_traces(artifact_directory: str | Path, *, schedule_indices: tuple[int, ...],
                           profile_path: str | Path = _DEFAULT_PROFILE) -> tuple[KTracePresentation, ...]:
    """Read an intact accepted archive (including a portable byte-identical copy).

    Only qualification.json, COMPLETE.json and the pinned profile are read.
    No board generation, Engine gameplay, solver, evaluator, or file writes.
    """
    _indices(schedule_indices)
    directory = Path(artifact_directory)
    try:
        _need(directory.is_dir() and not directory.is_symlink() and not directory.is_junction(),
              "Expected a regular completed artifact directory.")
        _need({p.name for p in directory.iterdir()} == {"qualification.json", "COMPLETE.json"},
              "Incomplete or unexpected files in the accepted archive.")
        return project_accepted_e1_traces(
            _read_bounded(directory / "qualification.json", QUALIFICATION_SIZE),
            _read_bounded(directory / "COMPLETE.json", COMPLETE_SIZE),
            _read_bounded(Path(profile_path), PROFILE_SIZE), schedule_indices=schedule_indices)
    except OSError as exc:
        raise KTraceAdapterError("Unable to read completed E1 evidence: " + str(exc)) from exc
