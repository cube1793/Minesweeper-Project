"""D4.1: four preserved repetition-1 CONTROL traces, never a V1 execution API.

Only D1's stdlib wire/pin/source helpers are reused. Its K-only admission and
models are unchanged. CONTROL has physical facts and archived V1 audits, not M.
All returned records are detached immutable values; no historical class is loaded.
"""

from dataclasses import dataclass, fields
from pathlib import Path

from experiments import program_k_trace_adapter as _d1


CONTROL_SCHEDULE_INDICES = (6, 12, 18, 24)
# Registration facts, not substitutes for archive/source/materialization checks.
FIXED_CASES = (
    (6, "S-LIFECYCLE", 4, 1, 1, "202dfd5c0a4e7534eba7ea3885b9755a5485e57b73118f1d052b5ec3bf346d53"),
    (12, "S-REPLAN", 6, 4, 5, "6bd8c08c1b59fce179c64708033d6885dc6144d8d61f181570b9ed3c926d07ba"),
    (18, "S-LOSS", 5, 1, 2, "ad299cd7234c269c935af06357607f89cb56bfcb13a82fa813cba9f42340775c"),
    (24, "X-0", 30, 16, 99, "fbd8b8069ef4f449bbc844329579b6538d2b175c1cf99eb22c49c0585322e053"),
)
# Legacy P3 content commitments retained in this byte-pinned publication.
# They are checked, not recomputed by importing the historical audit/evaluator.
_P3_DIGESTS = (
    "f5db94ef25db4db23ea4bc26a113183aa72d8b611925e9b7fa1d32064ed93460",
    "681f1be60d04d2e6a9f1214b76f05b62c0ae7daa13735f53b28abbc24acc4b27",
    "9a7f1f28b64ef416ed9065e84b34a8659cfca9fc3436e3c06fcd0ebf9381819d",
    "ea57f85a2ca32a76e6547260941c47f14beb83fa2974da41919be74e182a2444",
)
HIDDEN, FLAGGED, EXPLODED, MINE, FALSE_FLAG = -2, -3, -4, -5, -6
Coord = tuple[int, int]
Observation = tuple[tuple[int, ...], ...]


class ControlTraceAdapterError(ValueError):
    """The fixed CONTROL publication or selected physical evidence was refused."""


def _need(condition, message):
    if not condition:
        raise ControlTraceAdapterError(message)


def _sha(value):
    _need(type(value) is str and len(value) == 64
          and all(c in "0123456789abcdef" for c in value), "Invalid evidence digest.")
    return value


@dataclass(frozen=True, slots=True)
class ControlTraceProvenance:
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
    source_files: tuple[_d1.HistoricalSourceFile, ...]
    historical_runtime: tuple[tuple[str, str], ...]
    scope: str = _d1.RESEARCH_SCOPE
    no_effectiveness_claim: str = _d1.NO_EFFECTIVENESS_CLAIM
    variant: str = "CONTROL"


@dataclass(frozen=True, slots=True)
class ControlCaseIdentity:
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
class RecordedRunIdentity:
    """A scheduled E1 payload reference; never an algorithm/knowledge model."""

    schedule_index: int
    variant: str
    operation_id: str
    payload_sha256: str
    payload_size: int
    operation: _d1.EvidenceReference
    archive: _d1.EvidenceReference
    result: _d1.EvidenceReference
    audit: _d1.EvidenceReference
    registration: _d1.EvidenceReference
    materialization: _d1.EvidenceReference
    traces: tuple[_d1.EvidenceReference, ...]
    effects: tuple[_d1.EvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class ControlActionView:
    input_index: int
    action: str
    target: Coord
    cursor_before: Coord
    modeled_action_us: int
    cumulative_modeled_us: int
    status_after: str
    safe_cells_opened_delta: int
    explicit_flag_delta: int
    trace: _d1.EvidenceReference
    effect: _d1.EvidenceReference
    v1_audit: _d1.EvidenceReference
    cost_audit: _d1.EvidenceReference


@dataclass(frozen=True, slots=True)
class ControlTraceFrame:
    index: int
    observation: Observation
    status: str
    cursor: Coord
    cumulative_modeled_us: int
    explicit_flags: frozenset[Coord]
    automatic_flags: frozenset[Coord]

    @property
    def public_flags(self):
        return _d1._cells(self.observation, FLAGGED)


@dataclass(frozen=True, slots=True)
class ControlTracePresentation:
    provenance: ControlTraceProvenance
    case: ControlCaseIdentity
    run: RecordedRunIdentity
    actions: tuple[ControlActionView, ...]
    frames: tuple[ControlTraceFrame, ...]
    answer_reference: _d1.TerminalAnswerReference
    p3_audit: _d1.EvidenceReference
    p3_archive_sha256: str

    def frame(self, index):
        _need(type(index) is int and 0 <= index < len(self.frames), "Invalid frame index.")
        return self.frames[index]

    def completed_route(self, index):
        self.frame(index)
        return tuple(action.target for action in self.actions[:index])

    @property
    def terminal_status(self):
        return self.frames[-1].status

    @property
    def total_modeled_us(self):
        return self.frames[-1].cumulative_modeled_us


def _admit_publication(qualification_bytes, complete_bytes, profile_bytes):
    """Same pinned publication/source family as D1; no K index admission here."""
    marker_graph = _d1._Graph(_d1._pinned_json(
        complete_bytes, _d1.COMPLETE_SIZE, _d1.COMPLETE_SHA256, "COMPLETE"))
    graph = _d1._Graph(_d1._pinned_json(
        qualification_bytes, _d1.QUALIFICATION_SIZE, _d1.QUALIFICATION_SHA256, "Qualification"))
    profile = _d1._pinned_json(profile_bytes, _d1.PROFILE_SIZE, _d1.PROFILE_SHA256, "Model-C profile")
    _d1._record(marker_graph, marker_graph.root, "e1_persistence", "E1ArtifactReceipt")
    marker = marker_graph.plain(marker_graph.root)
    _need(marker["run_id"] == _d1.ACCEPTED_RUN_ID
          and marker["content_sha256"] == _d1.QUALIFICATION_SHA256
          and marker["size_bytes"] == _d1.QUALIFICATION_SIZE
          and marker["completion_marker"] == "COMPLETE" and marker["verdict"] == "E1_PASS"
          and marker["readiness"] == "E1_QUALIFIED" and marker["progression_allowed"] is True
          and marker["envelope_digest"] == _d1._ENVELOPE
          and marker["protocol_sha256"] == _d1.PROTOCOL_SHA256, "Accepted receipt mismatch.")
    root = _d1._record(graph, graph.root, "e1_qualification", "E1QualificationRecord")
    _need(graph.scalar(root["run_id"]) == _d1.ACCEPTED_RUN_ID
          and graph.scalar(root["purpose"]) == "E1_QUALIFICATION", "Qualification identity mismatch.")
    source, plan, execution, audit = _d1._sources(graph, root, marker)
    provenance = ControlTraceProvenance(**{f.name: getattr(source, f.name) for f in fields(source)})
    operations = graph.sequence(root["scheduled_results"])
    _need(len(operations) == 54, "Incomplete accepted schedule.")
    return graph, operations, plan, execution, audit, provenance, _d1._timing_table(profile)


def _run_binding(graph, operation_ref, index, variant, plan, execution_source, audit_source, provenance):
    """Read the two named variants' scheduled identity, without evaluating either."""
    _need((variant == "CONTROL" and index in CONTROL_SCHEDULE_INDICES)
          or (variant == "K-P0" and index - 2 in CONTROL_SCHEDULE_INDICES), "Unexpected fixed run.")
    operation = _d1._record(graph, operation_ref, "e1_operational", "E1OperationResult")
    archive = _d1._record(graph, operation["archive"], "e1_execution", "E1ScheduledRunArchive")
    audit = _d1._record(graph, operation["audit"], "e1_audit", "E1RunAudit")
    receipt = _d1._record(graph, operation["receipt"], "e1_operational", "E1OperationReceipt")
    _need(graph.scalar(operation["evaluation"]) is None
          and graph.scalar(archive["completion_status"]) == "COMPLETE"
          and graph.scalar(archive["shadow_timeout_usage"]) == "NOT_APPLICABLE"
          and graph.scalar(receipt["status"]) == "COMPLETE"
          and graph.scalar(receipt["operation_kind"]) == "SCHEDULED_RUN"
          and graph.scalar(receipt["operation_id"]) == f"SCHEDULED_RUN:{index:02d}"
          and graph.integer(receipt["exit_code"]) == 0 and graph.scalar(receipt["reason"]) is None
          and graph.scalar(receipt["operational_source_digest"]) == provenance.operational_source_digest
          and graph.scalar(receipt["envelope_digest"]) == _d1._ENVELOPE, "Incomplete scheduled execution.")
    _need(graph.plain(archive["execution_source_identity"]) == execution_source
          and graph.plain(audit["source_identity"]) == audit_source
          and graph.scalar(archive["plan_source_digest"]) == provenance.plan_source_digest
          and graph.scalar(audit["execution_source_digest"]) == provenance.execution_source_digest,
          "Run historical source binding mismatch.")
    schedules, cases = graph.sequence(plan["schedule"]), graph.sequence(plan["cases"])
    _need(len(schedules) == 54 and len(cases) == 9 and schedules[index] == archive["schedule_entry"]
          and cases[index // 6] == archive["case"] and audit["case"] == archive["case"]
          and audit["schedule_entry"] == archive["schedule_entry"], "Schedule/case reference mismatch.")
    schedule = _d1._record(graph, archive["schedule_entry"], "e1_harness", "ScheduleEntry")
    case_id = FIXED_CASES[CONTROL_SCHEDULE_INDICES.index(index if variant == "CONTROL" else index - 2)][1]
    for record in (schedule, receipt):
        _need(graph.integer(record["schedule_index"]) == index
              and graph.scalar(record["case_id"]) == case_id
              and graph.integer(record["repetition"]) == 1
              and graph.scalar(record["variant"]) == variant, "Schedule variant/repetition mismatch.")
    _need(graph.scalar(schedule["fresh_state_required"]) is True
          and graph.scalar(audit["variant"]) == variant and graph.integer(audit["repetition"]) == 1
          and graph.scalar(audit["audit_status"]) == "PASS"
          and not graph.sequence(audit["discrepancies"])
          and not graph.sequence(audit["incomplete_reasons"]), "Run audit is incomplete or failed.")
    case = _d1._record(graph, archive["case"], "e1_harness", "SealedCaseRegistration")
    material = _d1._record(graph, archive["receipt"], "e1_execution", "CaseMaterializationReceipt")
    for name in ("case_id", "source_type", "width", "height", "num_mines", "first_click",
                 "game_index", "seed", "board_fingerprint", "runtime"):
        _need(material[name] == case[name], "Materialization binding mismatch: " + name)
    _need(case["runtime"] == plan["runtime"] and graph.scalar(material["fresh_engine"]) is True,
          "Fresh materialization/runtime mismatch.")
    result = _d1._record(graph, archive["result"], "runner",
                         "ControlCaptureResult" if variant == "CONTROL" else "KRunResult")
    if variant == "CONTROL":
        native = graph.record(result["control"], "stage3_runner.Stage3RunResult")
        traces, effects = graph.sequence(native["traces"]), graph.sequence(result["effects"])
    else:
        traces = graph.sequence(result["traces"])
        effects = tuple(_d1._record(graph, ref, "runner", "KActionTrace")["public_effect"] for ref in traces)
    _need(0 < len(traces) == len(effects) == graph.integer(receipt["physical_inputs"]) <= 480,
          "Incomplete physical stream.")
    _need(graph.integer(receipt["result_size_bytes"]) > 0, "Missing recorded payload size.")
    binding = RecordedRunIdentity(
        index, variant, graph.scalar(receipt["operation_id"]), _sha(graph.scalar(receipt["result_digest"])),
        graph.integer(receipt["result_size_bytes"]), graph.reference(operation_ref),
        *(graph.reference(ref) for ref in (operation["archive"], archive["result"], operation["audit"],
                                         archive["case"], archive["receipt"])),
        tuple(graph.reference(ref) for ref in traces), tuple(graph.reference(ref) for ref in effects))
    return archive, audit, result, binding


def _control_case(graph, archive, index):
    raw = _d1._record(graph, archive["case"], "e1_harness", "SealedCaseRegistration")
    expected = FIXED_CASES[CONTROL_SCHEDULE_INDICES.index(index)]
    case_id, w, h, n, fingerprint = expected[1:]
    _need(tuple(graph.integer(raw[k]) for k in ("width", "height", "num_mines")) == (w, h, n)
          and graph.scalar(raw["case_id"]) == case_id
          and graph.scalar(raw["board_fingerprint"]) == fingerprint
          and graph.coord(raw["first_click"], w, h) == (0, 0), "Fixed CONTROL case mismatch.")
    identity = tuple(graph.scalar(raw[k]) for k in (
        "source_type", "benchmark_set_id", "board_generator_version", "seed_scheme", "game_index", "seed", "fixture_id"))
    expected_identity = (("EXPERT_REGRESSION_TUPLE", "EXPERT_GENERAL_V1", "V1", "game_index", 0, 0, None)
                         if index == 24 else ("PRE_EXISTING_REGRESSION_FIXTURE", None, None, None, None, None, case_id))
    _need(identity == expected_identity and graph.scalar(raw["statistically_representative"]) is False
          and graph.scalar(raw["e2_effectiveness_evidence"]) is False
          and graph.scalar(raw["no_effectiveness_claim"]) == _d1.NO_EFFECTIVENESS_CLAIM,
          "CONTROL fixture identity/scope mismatch.")
    material = _d1._record(graph, archive["receipt"], "e1_execution", "CaseMaterializationReceipt")
    _need(graph.scalar(material["materialization_method"]) == (
        "EXPERT_GENERAL_V1_RESET" if index == 24 else "FIXED_SYNTHETIC_RESET"), "Materialization method mismatch.")
    return ControlCaseIdentity(case_id, index, 1, "CONTROL", w, h, n, (0, 0), fingerprint,
                               *identity, graph.scalar(raw["provenance"]),
                               tuple(graph.scalar(r) for r in graph.sequence(raw["permitted_claims"])))


def _physical_effect(before, after, action, target, status, explicit):
    """Check recorded public changes; no gameplay reconstruction or inference."""
    x, y = target
    if action == "FLAG":
        _need(before[y][x] == HIDDEN and after[y][x] == FLAGGED and status == "PLAYING",
              "Invalid physical FLAG effect.")
        explicit = explicit | {target}
        _need(sum(a != b for r0, r1 in zip(before, after) for a, b in zip(r0, r1)) == 1,
              "FLAG changed other public cells.")
    elif action == "OPEN":
        _need(before[y][x] == HIDDEN and (0 <= after[y][x] <= 8 or after[y][x] == EXPLODED),
              "Invalid OPEN effect.")
    else:
        _need(action == "CHORD" and 0 < before[y][x] <= 8, "Invalid CHORD target.")
    _need(all(a == HIDDEN or a == b or (status == "LOST" and a == FLAGGED and b == FALSE_FLAG)
              for r0, r1 in zip(before, after) for a, b in zip(r0, r1)), "Previously public cells changed.")
    public_flags = _d1._cells(after, FLAGGED)
    automatic = public_flags - explicit if status == "WON" else frozenset()
    _need(public_flags | _d1._cells(after, FALSE_FLAG) == explicit | automatic,
          "Public flags disagree with executed FLAG inputs.")
    if status == "PLAYING":
        _need(len(_d1._cells(after, HIDDEN)) < len(_d1._cells(before, HIDDEN)), "No recorded physical progress.")
    safe_delta = sum(a in (HIDDEN, FLAGGED) and 0 <= b <= 8
                     for r0, r1 in zip(before, after) for a, b in zip(r0, r1))
    return explicit, automatic, safe_delta, int(action == "FLAG")


def _project_run(graph, operation_ref, index, plan, execution_source, audit_source, provenance, table):
    archive, audit, result, binding = _run_binding(
        graph, operation_ref, index, "CONTROL", plan, execution_source, audit_source, provenance)
    case = _control_case(graph, archive, index)
    w, h = case.width, case.height
    native = graph.record(result["control"], "stage3_runner.Stage3RunResult")
    traces, effects, timings = (graph.sequence(native["traces"]), graph.sequence(result["effects"]),
                                graph.sequence(result["timings"]))
    costs, v1_audits = (graph.sequence(audit[k]) for k in ("cost_audits", "v1_audits"))
    count = len(traces)
    _need(count <= w * h and len(timings) == len(costs) == len(v1_audits) == count
          and graph.scalar(result["capture_method"]) == "STATUS_GATED_ACTUAL_EXECUTION",
          "Incomplete CONTROL trace/audit coverage.")
    for name in ("replay_audits", "acquisition_audits", "mechanism_observations", "oracle_a_audits", "oracle_b_audits"):
        _need(not graph.sequence(audit[name]), "CONTROL must not carry K/shadow audits.")
    public = _d1._record(graph, audit["public_effect_audit"], "evidence", "EvidenceComparison")
    _need(graph.scalar(public["status"]) == "PASS" and not graph.sequence(public["mismatches"])
          and graph.integer(public["boundary"]) == count - 1, "Public-effect audit did not pass/bind.")
    p3 = _d1._record(graph, audit["p3_audit"], "harness", "GuessCheckpointAudit")
    p3_digest = graph.scalar(p3["archive_digest"])
    _need(graph.scalar(audit["p3_status"]) == "COMPLETE" and graph.scalar(p3["case_id"]) == case.case_id
          and graph.scalar(p3["variant"]) == "CONTROL" and graph.integer(p3["num_mines"]) == case.num_mines
          and not graph.sequence(p3["incomplete"])
          and p3_digest == _P3_DIGESTS[CONTROL_SCHEDULE_INDICES.index(index)], "CONTROL P3 binding mismatch.")
    terminal_status = graph.enum(native["status"], "GameStatus", ("WON", "LOST"))
    for ordinal, ref in enumerate(graph.sequence(p3["checkpoints"]), 1):
        checkpoint = _d1._record(graph, ref, "harness", "GuessCheckpoint")
        _need(graph.scalar(checkpoint["case_id"]) == case.case_id
              and graph.integer(checkpoint["guess_ordinal"]) == ordinal
              and graph.enum(checkpoint["terminal_outcome"], "GameStatus", ("WON", "LOST")) == terminal_status,
              "CONTROL P3 checkpoint binding mismatch.")
    frames = [ControlTraceFrame(0, tuple((HIDDEN,) * w for _ in range(h)), "PLAYING", case.first_click,
                                0, frozenset(), frozenset())]
    actions = []
    for i, (trace_ref, effect_ref) in enumerate(zip(traces, effects)):
        trace = graph.record(trace_ref, "stage3_runner.Stage3ActionTrace")
        effect = _d1._record(graph, effect_ref, "evidence", "PublicEffectRecord")
        cost = _d1._record(graph, costs[i], "e1_audit", "ModelCCostAudit")
        v1 = _d1._record(graph, v1_audits[i], "e1_audit", "V1ActionAudit")
        timing = _d1._record(graph, timings[i], "evidence", "DecisionTimings")
        prior = frames[-1]
        status = graph.enum(trace["status_after"], "GameStatus", ("PLAYING", "WON", "LOST"))
        _need(prior.status == "PLAYING" and (status != "PLAYING") == (i == count - 1)
              and all(graph.integer(r["input_index"]) == i for r in (effect, cost, v1)),
              "Action/effect/audit order or terminal boundary mismatch.")
        _need(graph.scalar(v1["status"]) == "PASS" and graph.scalar(v1["detail"]) == ""
              and all(graph.scalar(v1[k]) is None for k in ("external_flag", "external_verification", "external_qualification")),
              "CONTROL V1 audit missing/failed or contains shadow provenance.")
        _need(timing["v1_plan_position_ns"] == trace["decision_compute_ns"], "CONTROL timing/trace binding mismatch.")
        _need(graph.scalar(effect["capture_method"]) == "STATUS_GATED_ACTUAL_EXECUTION"
              and graph.scalar(effect["archival_only"]) is True
              and graph.enum(effect["status_before"], "GameStatus", ("PLAYING",)) == "PLAYING"
              and graph.enum(effect["status_after"], "GameStatus", ("PLAYING", "WON", "LOST")) == status,
              "Public effect capture/status mismatch.")
        before = graph.grid(effect["before_observation"], w, h, "PLAYING")
        observed = _d1._record(graph, effect["after_observation"], "evidence", "ArchivalObservation")
        _need(graph.scalar(observed["archival_only"]) is True
              and graph.enum(observed["status"], "GameStatus", ("PLAYING", "WON", "LOST")) == status,
              "Archival observation/status mismatch.")
        after = graph.grid(observed["rows"], w, h, status)
        action, target = _d1._move(graph, trace["move"], w, h)
        cursor = graph.coord(trace["cursor_before"], w, h)
        _need(before == prior.observation and cursor == prior.cursor
              and graph.coord(effect["cursor_before"], w, h) == cursor
              and graph.coord(effect["cursor_after"], w, h) == target
              and _d1._move(graph, effect["move"], w, h, effect=True) == (action, target),
              "Observation/move/cursor continuity mismatch.")
        if i == 0:
            _need((action, target) == ("OPEN", case.first_click) and graph.scalar(trace["decision"]) is None
                  and graph.scalar(trace["decision_compute_ns"]) is None, "Initial CONTROL OPEN mismatch.")
        else:
            decision = graph.record(trace["decision"], "stage3_planner.Stage3Decision")
            _need(_d1._move(graph, decision["move"], w, h) == (action, target), "Archived V1 decision/move mismatch.")
        modeled = graph.integer(trace["modeled_action_us"])
        _need(modeled == graph.integer(effect["modeled_action_us"])
              == table[abs(target[0] - cursor[0])][abs(target[1] - cursor[1])]
              and all(graph.integer(cost[k]) == modeled for k in ("expected_us", "trace_us", "effect_us"))
              and graph.scalar(cost["status"]) == "PASS", "Exact Model-C cost mismatch.")
        explicit, automatic, safe_delta, flag_delta = _physical_effect(
            before, after, action, target, status, prior.explicit_flags)
        _need(all(graph.integer(r["safe_cells_opened_delta"]) == safe_delta
                  and graph.integer(r["explicit_flag_delta"]) == flag_delta for r in (trace, effect)),
              "Public effect work counters mismatch.")
        total = prior.cumulative_modeled_us + modeled
        frames.append(ControlTraceFrame(i + 1, after, status, target, total, explicit, automatic))
        actions.append(ControlActionView(i, action, target, cursor, modeled, total, status, safe_delta, flag_delta,
                                         graph.reference(trace_ref), graph.reference(effect_ref),
                                         graph.reference(v1_audits[i]), graph.reference(costs[i])))
    final = frames[-1]
    _need(final.status == terminal_status and graph.integer(audit["expected_total_us"])
          == graph.integer(audit["recorded_total_us"]) == final.cumulative_modeled_us, "Terminal total/status mismatch.")
    mines = _d1._cells(final.observation, FLAGGED, EXPLODED, MINE)
    _need(len(mines) == case.num_mines and _d1._fingerprint(w, h, case.num_mines, mines) == case.board_fingerprint,
          "Terminal layout fingerprint mismatch.")
    _need((final.status == "WON" and not _d1._cells(final.observation, HIDDEN, EXPLODED, MINE, FALSE_FLAG))
          or (final.status == "LOST" and bool(_d1._cells(final.observation, EXPLODED))), "Terminal glyph mismatch.")
    return ControlTracePresentation(provenance, case, binding, tuple(actions), tuple(frames),
        _d1.TerminalAnswerReference(mines, case.board_fingerprint, actions[-1].effect),
        graph.reference(audit["p3_audit"]), p3_digest)


def _indices(indices):
    _need(type(indices) is tuple and 0 < len(indices) <= 4
          and all(type(i) is int and i in CONTROL_SCHEDULE_INDICES for i in indices)
          and len(set(indices)) == len(indices), "Select unique fixed repetition-1 CONTROL indices.")
    return indices


def project_accepted_control_traces(qualification_bytes: bytes, complete_bytes: bytes, profile_bytes: bytes,
                                    *, schedule_indices=CONTROL_SCHEDULE_INDICES):
    """Authenticate/project atomically. No arbitrary corpus or caller trust pins."""
    indices = _indices(schedule_indices)
    try:
        graph, operations, plan, execution, audit, provenance, table = _admit_publication(
            qualification_bytes, complete_bytes, profile_bytes)
        return tuple(_project_run(graph, operations[i], i, plan, execution, audit, provenance, table) for i in indices)
    except (_d1.KTraceAdapterError, KeyError, TypeError, IndexError, RecursionError) as exc:
        raise ControlTraceAdapterError("CONTROL evidence refused: " + str(exc)) from exc


def _read_publication(artifact_directory, profile_path):
    directory = Path(artifact_directory)
    try:
        _need(directory.is_dir() and not directory.is_symlink() and not directory.is_junction(),
              "Expected a regular accepted artifact directory.")
        _need({p.name for p in directory.iterdir()} == {"qualification.json", "COMPLETE.json"},
              "Incomplete or unexpected accepted archive files.")
        return (_d1._read_bounded(directory / "qualification.json", _d1.QUALIFICATION_SIZE),
                _d1._read_bounded(directory / "COMPLETE.json", _d1.COMPLETE_SIZE),
                _d1._read_bounded(Path(profile_path), _d1.PROFILE_SIZE))
    except (OSError, _d1.KTraceAdapterError) as exc:
        raise ControlTraceAdapterError("Cannot read accepted publication: " + str(exc)) from exc


def load_accepted_control_traces(artifact_directory, *, schedule_indices=CONTROL_SCHEDULE_INDICES,
                                profile_path=_d1._DEFAULT_PROFILE):
    """Read only the accepted publication/profile; navigation needs no files."""
    _indices(schedule_indices)
    return project_accepted_control_traces(*_read_publication(artifact_directory, profile_path),
                                           schedule_indices=schedule_indices)
