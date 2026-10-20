"""Prospective Program-K E1 Slice 1: prerequisites, case seals and schedule.

This is harness-only planning metadata, never solver input: even a layout
fingerprint must remain outside inference. No execution, result publication,
supplement selection or E1 verdict exists here. Import performs no artifact
reads, board generation or runtime capture.
"""

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import platform
import sys

from benchmark_board import (
    EXPERT_GENERAL_V1, BenchmarkBoard, calculate_board_fingerprint, generate_board,
)
from experiments import program_k_harness as _e0
from experiments import program_k_oracles as _oracles


ACCEPTED_E0_RUN_ID = "e0-20261020T091707Z-a64907341e6c"
ACCEPTED_E0_QUALIFICATION_SHA256 = "71ee9b3a9dc0a24de7471be996da5069f5c77ed750485a84b298ee74b7065576"
ACCEPTED_E0_COMPLETE_SHA256 = "a664e8dfdc5e6aa8a6fe02d6fabe84da3df901829c8291558d5d874d646eb522"
ACCEPTED_E0_SOURCE_DIGEST = "a8d2ed2f5547316603b4ba54899a7deed289016df7a5954f1db5b4816e00abd1"
ACCEPTED_P8_EVIDENCE_DIGEST = "9ccffab72d34173181dd84170cf442156f2df888f03d87c1571660ba7774137d"
FROZEN_SPEC_SHA256 = "3e26c5b36d590e90bbd34951ee869cf63ed4f89b6cd3657a059132d065669903"
FROZEN_PROTOCOL_SHA256 = "43504d42d6c921c8291ed6c2a61cf198d2c64aaec2fb1f443caa59fbd59a91af"
MODEL_ID = "overlap_floor_log2_distance_v1"
PROFILE_SHA256 = "52e140e9fc4b760c64ba3c214c503b5ef6ee1e390e7b2162cc647d47a26b292b"
TABLE_SHA256 = "7c284c66f7ddbd5f0c7de96f5f4e6a26b12d31fddb4ebb931674866d1041123b"
E1_SOURCE_PATHS = ("experiments/program_k_e1_harness.py", "benchmark_board.py")
CASE_IDS = ("S-WIN", "S-LIFECYCLE", "S-REPLAN", "S-LOSS",
            "X-0", "X-1", "X-2", "X-3", "X-100000")
EXPERT_INDICES = (0, 1, 2, 3, 100000)
VARIANTS = ("CONTROL", "K-CONTROL", "K-P0")
REPETITIONS = (1, 2)
NO_EFFECTIVENESS_CLAIM = "Not statistically representative; not E2 effectiveness evidence."
PLAN_PURPOSE = "Complete-execution qualification, not effectiveness."
REPETITION_PURPOSE = (
    "Determinism/state-contamination checks only; no statistical-independence meaning."
)
QUALIFICATION_SCOPE = "PROSPECTIVE_SLICE_1_NOT_FINAL_E1_QUALIFICATION"
PRODUCTIVE_CHORD_REQUIREMENT = (
    "Actual productive K-P0 FLAG/CHORD must be observed during E1. If missing, "
    "E1 is INCOMPLETE; A-E5 requires a separately prospectively selected supplement. "
    "The S-LIFECYCLE rationale does not establish K-P0 coverage."
)


class E1PlanningError(ValueError):
    """A missing or mismatched prerequisite/seal fails closed."""


def _need(condition, detail):
    if not condition:
        raise E1PlanningError(detail)


def _sha(value):
    _need(type(value) is str and len(value) == 64
          and all(c in "0123456789abcdef" for c in value),
          "Expected a lowercase SHA-256 digest.")


def _frozen_identities(value):
    values = (value.spec_sha256, value.protocol_sha256, value.model_id,
              value.profile_sha256, value.table_sha256)
    _need(all(type(v) is str for v in values)
          and values == (FROZEN_SPEC_SHA256, FROZEN_PROTOCOL_SHA256, MODEL_ID,
              PROFILE_SHA256, TABLE_SHA256), "Frozen authority/Model-C identity mismatch.")


def _typed(value, cls):
    _need(type(value) is cls, "Expected immutable " + cls.__name__ + ".")
    return replace(value)


def _repository_root():
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    platform: str
    node: str
    python_version: str
    executable: str

    def __post_init__(self):
        _need(all(type(v) is str and bool(v.strip()) for v in
                  (self.platform, self.node, self.python_version, self.executable)),
              "Runtime identity requires actual, nonempty platform/node/Python/executable strings.")


def capture_runtime_identity():
    return RuntimeIdentity(platform.platform(), platform.node(), sys.version, sys.executable)


@dataclass(frozen=True, slots=True)
class AcceptedE0Prerequisite:
    """Small historical reference; no E0 record, file, path or live object."""

    run_id: str
    qualification_sha256: str
    source_digest: str
    verdict: str
    readiness: str
    p8_evidence_digest: str
    spec_sha256: str
    protocol_sha256: str
    model_id: str
    profile_sha256: str
    table_sha256: str

    def __post_init__(self):
        values = (self.run_id, self.qualification_sha256, self.source_digest,
                  self.verdict, self.readiness, self.p8_evidence_digest)
        _need(all(type(v) is str for v in values)
              and values == (ACCEPTED_E0_RUN_ID, ACCEPTED_E0_QUALIFICATION_SHA256,
                  ACCEPTED_E0_SOURCE_DIGEST, "E0_PASS", "E0_QUALIFIED",
                  ACCEPTED_P8_EVIDENCE_DIGEST), "Not the accepted E0/P-8 prerequisite.")
        _frozen_identities(self)


def _check_accepted_files(directory):
    # Check BEFORE the existing reader: assessment of a different unit-readiness
    # artifact could replay qualification work. Only the accepted E0 bytes enter.
    for filename, expected in (
        ("qualification.json", ACCEPTED_E0_QUALIFICATION_SHA256),
        ("COMPLETE.json", ACCEPTED_E0_COMPLETE_SHA256),
    ):
        _need(hashlib.sha256((directory / filename).read_bytes()).hexdigest() == expected,
              "Accepted E0 " + filename + " byte identity mismatch.")


def load_accepted_e0_prerequisite(path=None):
    """Bind read-only to accepted evidence using the existing artifact reader."""
    directory = (_repository_root() / "results/program_k_research" / ACCEPTED_E0_RUN_ID
                 if path is None else Path(path))
    try:
        _check_accepted_files(directory)
        record, receipt, assessment = _e0.read_qualification_artifact(directory)
        _need(type(record) is _e0.QualificationRecord
              and type(receipt) is _e0.ArtifactReceipt
              and type(assessment) is _e0.QualificationAssessment,
              "Malformed E0 artifact/receipt/assessment.")
        _need(directory.name == record.run_id == receipt.run_id == ACCEPTED_E0_RUN_ID
              and record.purpose == "E0_QUALIFICATION", "Wrong accepted E0 run or purpose.")
        _need(receipt.content_sha256 == _e0.content_digest(record)
              == ACCEPTED_E0_QUALIFICATION_SHA256
              and receipt.completion_marker == "COMPLETE", "Wrong E0 content identity.")
        source = _typed(record.source_identity, _e0.SourceIdentity)
        _need(receipt.source_digest == _e0.content_digest(source)
              == ACCEPTED_E0_SOURCE_DIGEST, "Wrong E0 base source identity.")
        _frozen_identities(source)
        _need(receipt.protocol_sha256 == source.protocol_sha256, "Wrong receipt protocol.")
        _need(assessment.verdict == receipt.verdict == "E0_PASS"
              and assessment.readiness == "E0_QUALIFIED"
              and assessment.progression_allowed is True, "E0 is not qualified.")
        p8 = record.p8_reference
        _need(type(p8) is _oracles.P8Result, "Missing/malformed accepted P-8.")
        _need(p8.scope == "FROZEN_P8" and p8.authentication_status == "AUTHENTICATED"
              and p8.completion_marker == "COMPLETE" and p8.status == "PASS"
              and type(p8.expected_triple_count) is int
              and type(p8.visited_triple_count) is int
              and p8.expected_triple_count == p8.visited_triple_count == 110361600
              and p8.evidence_sha256 == ACCEPTED_P8_EVIDENCE_DIGEST,
              "Accepted exhaustive P-8 identity mismatch.")
        gate = _e0.check_p8_gate(p8)  # Evidence validation only; never a scan.
        _need(type(gate) is _e0.P8Gate and gate.status == "PASS"
              and gate.classification == "FROZEN_P8_COMPLETE"
              and gate.evidence_digest == ACCEPTED_P8_EVIDENCE_DIGEST,
              "Current P-8 evidence gate does not pass.")
        # Detect changes during the existing reader's separate artifact reads.
        _check_accepted_files(directory)
        return AcceptedE0Prerequisite(
            record.run_id, receipt.content_sha256, receipt.source_digest,
            assessment.verdict, assessment.readiness, p8.evidence_sha256,
            source.spec_sha256, source.protocol_sha256, source.model_id,
            source.profile_sha256, source.table_sha256)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        raise E1PlanningError("Accepted E0 prerequisite refused: " + str(error)) from error


@dataclass(frozen=True, slots=True)
class E1SourceFile:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        _need(type(self.path) is str and self.path in E1_SOURCE_PATHS,
              "Unregistered or non-normalized E1 runtime source path.")
        _sha(self.sha256)
        _need(type(self.size_bytes) is int and self.size_bytes > 0, "Invalid source byte size.")


@dataclass(frozen=True, slots=True)
class E1SourceIdentity:
    base_source_digest: str
    files: tuple[E1SourceFile, ...]
    spec_sha256: str
    protocol_sha256: str
    model_id: str
    profile_sha256: str
    table_sha256: str

    def __post_init__(self):
        _need(type(self.base_source_digest) is str
              and self.base_source_digest == ACCEPTED_E0_SOURCE_DIGEST,
              "E1 must extend the accepted E0 source identity.")
        _need(type(self.files) is tuple and all(type(f) is E1SourceFile for f in self.files)
              and tuple(f.path for f in self.files) == E1_SOURCE_PATHS,
              "Missing/extra/out-of-order E1 runtime source fields.")
        for source in self.files:
            _typed(source, E1SourceFile)
        _frozen_identities(self)

    @property
    def digest(self):
        _typed(self, E1SourceIdentity)
        data = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
        return hashlib.sha256(data).hexdigest()


def _capture_e1_source_identity(prerequisite, root):
    """Private temporary-root seam; base evidence is never rewritten."""
    prerequisite = _typed(prerequisite, AcceptedE0Prerequisite)
    base = _e0.capture_source_identity()
    _need(_e0.content_digest(base) == prerequisite.source_digest,
          "Current qualified E0 sources differ from the accepted base.")
    files = []
    try:
        for path in E1_SOURCE_PATHS:
            raw = (root / path).read_bytes()
            files.append(E1SourceFile(path, hashlib.sha256(raw).hexdigest(), len(raw)))
    except OSError as error:
        raise E1PlanningError("Missing E1 runtime source: " + str(error)) from error
    return E1SourceIdentity(
        prerequisite.source_digest, tuple(files), prerequisite.spec_sha256,
        prerequisite.protocol_sha256, prerequisite.model_id,
        prerequisite.profile_sha256, prerequisite.table_sha256)


def capture_e1_source_identity(prerequisite):
    """Exact-byte extension; the new test module is not a runtime dependency."""
    return _capture_e1_source_identity(prerequisite, _repository_root())


@dataclass(frozen=True, slots=True)
class _CaseDefinition:
    """Answer-bearing inputs stay private to sealing, outside the plan graph."""

    case_id: str
    width: int
    height: int
    num_mines: int
    mine_positions: tuple[tuple[int, int], ...] | None
    game_index: int | None
    board_fingerprint: str
    purpose: str
    provenance: str
    prior_exposure: tuple[str, ...]
    overlap: tuple[str, ...]
    permitted_claims: tuple[str, ...]

    @property
    def source_type(self):
        return "PRE_EXISTING_REGRESSION_FIXTURE" if self.game_index is None else "EXPERT_REGRESSION_TUPLE"


_SYNTHETIC_CLAIMS = ("Execution boundary / mechanism qualification only.",)
_EXPERT_CLAIMS = ("Experimental regression only.",)
_EXPERT_PROVENANCE = (
    "Complete existing Expert regression tuple: "
    "tests/test_stage3_planner.py::test_fixed_expert_complete_public_trajectories_match"
)
_CASE_DEFINITIONS = (
    _CaseDefinition("S-WIN", 3, 1, 1, ((2, 0),), None,
        "7420118e517924990ff86e47fca7c246e84cb17b7941c1525888a5d5962bf55f",
        "Immediate WIN / automatic-flag boundary.",
        "Pre-existing regression fixture: tests/test_stage3_runner.py::test_terminal_first_open_win_and_auto_flags_have_no_cost",
        ("Pre-existing synthetic regression fixture.",), (), _SYNTHETIC_CLAIMS),
    _CaseDefinition("S-LIFECYCLE", 4, 1, 1, ((1, 0),), None,
        "202dfd5c0a4e7534eba7ea3885b9755a5485e57b73118f1d052b5ec3bf346d53",
        "Existing local/global, FLAG/CHORD and fresh-replan fixture.",
        "Pre-existing regression fixture: tests/test_stage3_runner.py::test_flag_triggers_full_replan_then_chord_executes",
        ("Pre-existing synthetic regression fixture.",), (), _SYNTHETIC_CLAIMS),
    _CaseDefinition("S-REPLAN", 6, 4, 5, ((4, 0), (2, 1), (4, 1), (1, 2), (4, 2)), None,
        "6bd8c08c1b59fce179c64708033d6885dc6144d8d61f181570b9ed3c926d07ba",
        "Discarded-suffix regression.",
        "Pre-existing regression fixture: tests/test_stage3_runner.py::test_setup_suffix_is_discarded_when_fresh_plan_changes",
        ("Pre-existing synthetic regression fixture.",), (), _SYNTHETIC_CLAIMS),
    _CaseDefinition("S-LOSS", 5, 1, 2, ((1, 0), (2, 0)), None,
        "ad299cd7234c269c935af06357607f89cb56bfcb13a82fa813cba9f42340775c",
        "Exact-guess terminal LOSS.",
        "Pre-existing regression fixture: tests/test_stage3_runner.py::test_terminal_guess_exact_coordinate_and_cost_included",
        ("Pre-existing synthetic regression fixture.",), (), _SYNTHETIC_CLAIMS),
    _CaseDefinition("X-0", 30, 16, 99, None, 0,
        "fbd8b8069ef4f449bbc844329579b6538d2b175c1cf99eb22c49c0585322e053",
        "Complete existing Expert regression tuple.", _EXPERT_PROVENANCE,
        ("Existing Expert regression tuple; official-range identity.",),
        ("Official [0,100000) identity; experimental regression only, no official rerun.",), _EXPERT_CLAIMS),
    _CaseDefinition("X-1", 30, 16, 99, None, 1,
        "007b8d203106dd32d1b5b6c46052bbeeeb9fde2be89c81023b01519fba1bee9e",
        "Complete existing Expert regression tuple.", _EXPERT_PROVENANCE,
        ("Existing Expert regression tuple; official-range identity.",),
        ("Official [0,100000) identity; experimental regression only, no official rerun.",
         "Fixed interpretation exemplar overlap; not effectiveness evidence."), _EXPERT_CLAIMS),
    _CaseDefinition("X-2", 30, 16, 99, None, 2,
        "58b8e6399a435371a430a75bd0a51035614242662b53015c61eb61292ccdd28a",
        "Complete existing Expert regression tuple.", _EXPERT_PROVENANCE,
        ("Existing Expert regression tuple; official-range identity.",),
        ("Official [0,100000) identity; experimental regression only, no official rerun.",), _EXPERT_CLAIMS),
    _CaseDefinition("X-3", 30, 16, 99, None, 3,
        "d191ef5fe000deb925b6c966cf83e8722e2d58c5f105717ab053b290d116b03c",
        "Complete existing Expert regression tuple.", _EXPERT_PROVENANCE,
        ("Existing Expert regression tuple; official-range identity.",),
        ("Official [0,100000) identity; experimental regression only, no official rerun.",), _EXPERT_CLAIMS),
    _CaseDefinition("X-100000", 30, 16, 99, None, 100000,
        "148b48aeda9730e8604bf68b7db8723de896bc8f4c5b741b33191d38edca065c",
        "Scale/integration regression.", _EXPERT_PROVENANCE,
        ("Existing Expert regression tuple; historical E/L pilot exposure.",),
        ("Historical E/L pilot overlap; no E/L range rerun.",),
        ("Scale/integration regression only.",)),
)


def _definition(case_id):
    _need(type(case_id) is str and case_id in CASE_IDS, "Unregistered E1 case.")
    return next(case for case in _CASE_DEFINITIONS if case.case_id == case_id)


@dataclass(frozen=True, slots=True)
class SealedCaseRegistration:
    """Harness metadata only: no layout, and no solver-facing fingerprint."""

    case_id: str
    source_type: str
    width: int
    height: int
    num_mines: int
    first_click: tuple[int, int]
    benchmark_set_id: str | None
    board_generator_version: str | None
    seed_scheme: str | None
    game_index: int | None
    seed: int | None
    fixture_id: str | None
    board_fingerprint: str
    provenance: str
    prior_exposure: tuple[str, ...]
    overlap: tuple[str, ...]
    purpose: str
    permitted_claims: tuple[str, ...]
    runtime: RuntimeIdentity
    statistically_representative: bool = False
    e2_effectiveness_evidence: bool = False
    no_effectiveness_claim: str = NO_EFFECTIVENESS_CLAIM

    def __post_init__(self):
        definition = _definition(self.case_id)
        _typed(self.runtime, RuntimeIdentity)
        _need(all(type(v) is int for v in (self.width, self.height, self.num_mines))
              and (self.width, self.height, self.num_mines)
              == (definition.width, definition.height, definition.num_mines),
              "Fixed case dimensions/count changed.")
        _need(type(self.first_click) is tuple and self.first_click == (0, 0)
              and all(type(v) is int for v in self.first_click), "Noncanonical first click.")
        for name in ("source_type", "board_fingerprint", "provenance", "prior_exposure",
                     "overlap", "purpose", "permitted_claims"):
            _need(getattr(self, name) == getattr(definition, name)
                  and type(getattr(self, name)) is type(getattr(definition, name)),
                  "Fixed case " + name + " changed.")
        _need(all(type(v) is str for values in
                  (self.prior_exposure, self.overlap, self.permitted_claims) for v in values),
              "Provenance/claim tuples must contain immutable text.")
        if definition.game_index is None:
            _need(all(v is None for v in
                      (self.benchmark_set_id, self.board_generator_version,
                       self.seed_scheme, self.game_index, self.seed))
                  and type(self.fixture_id) is str and self.fixture_id == self.case_id,
                  "Synthetic fixture identity changed.")
        else:
            _need(type(self.game_index) is int and type(self.seed) is int
                  and self.game_index == self.seed == definition.game_index
                  and all(type(v) is str for v in
                          (self.benchmark_set_id, self.board_generator_version, self.seed_scheme))
                  and (self.benchmark_set_id, self.board_generator_version, self.seed_scheme)
                  == ("EXPERT_GENERAL_V1", "V1", "game_index")
                  and self.fixture_id is None, "Frozen Expert generator identity changed.")
        _need(self.statistically_representative is False
              and self.e2_effectiveness_evidence is False
              and type(self.no_effectiveness_claim) is str
              and self.no_effectiveness_claim == NO_EFFECTIVENESS_CLAIM,
              "A fixed E1 case cannot claim statistical/effectiveness evidence.")


def _seal_fixed_cases(runtime):
    runtime = _typed(runtime, RuntimeIdentity)
    _need(all(type(v) is int for v in
              (EXPERT_GENERAL_V1.width, EXPERT_GENERAL_V1.height, EXPERT_GENERAL_V1.num_mines,
               EXPERT_GENERAL_V1.first_click_x, EXPERT_GENERAL_V1.first_click_y))
          and (EXPERT_GENERAL_V1.benchmark_set_id, EXPERT_GENERAL_V1.width,
           EXPERT_GENERAL_V1.height, EXPERT_GENERAL_V1.num_mines,
           EXPERT_GENERAL_V1.first_click_x, EXPERT_GENERAL_V1.first_click_y,
           EXPERT_GENERAL_V1.board_generator_version, EXPERT_GENERAL_V1.seed_scheme)
          == ("EXPERT_GENERAL_V1", 30, 16, 99, 0, 0, "V1", "game_index"),
          "Frozen Expert generator specification changed.")
    registrations = []
    for definition in _CASE_DEFINITIONS:
        index = definition.game_index
        if index is None:
            mines = definition.mine_positions
        else:
            # Exactly one generator call per fixed Expert identity per seal.
            generated = generate_board(EXPERT_GENERAL_V1, index)
            _need(type(generated) is BenchmarkBoard
                  and type(generated.game_index) is int and type(generated.seed) is int
                  and generated.game_index == generated.seed == index,
                  "Generated Expert index/seed mismatch.")
            mines = generated.mine_positions
        # Recompute from raw coordinates, independent of the returned fingerprint.
        # This public pure helper also checks count, uniqueness and dimensions.
        fingerprint = calculate_board_fingerprint(
            definition.width, definition.height, definition.num_mines, mines)
        _need((0, 0) not in mines, "Canonical first click is mined.")
        _need(fingerprint == definition.board_fingerprint, "Fixed layout fingerprint changed.")
        if index is not None:
            _need(generated.board_fingerprint == fingerprint, "Generated fingerprint does not reconstruct.")
        registrations.append(SealedCaseRegistration(
            definition.case_id, definition.source_type, definition.width, definition.height,
            definition.num_mines, (0, 0), None if index is None else "EXPERT_GENERAL_V1",
            None if index is None else "V1", None if index is None else "game_index",
            index, index, definition.case_id if index is None else None, fingerprint,
            definition.provenance, definition.prior_exposure, definition.overlap,
            definition.purpose, definition.permitted_claims, runtime))
    return tuple(registrations)


def seal_fixed_cases():
    """Capture this runtime and seal only the nine prospectively fixed cases."""
    return _seal_fixed_cases(capture_runtime_identity())


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    schedule_index: int
    case_id: str
    repetition: int
    variant: str
    fresh_state_required: bool = True

    def __post_init__(self):
        _need(type(self.schedule_index) is int and 0 <= self.schedule_index < 54,
              "Invalid schedule index.")
        _definition(self.case_id)
        _need(type(self.repetition) is int and self.repetition in REPETITIONS
              and type(self.variant) is str and self.variant in VARIANTS
              and self.fresh_state_required is True, "Invalid repetition/variant/fresh-state requirement.")


def validate_schedule(schedule):
    _need(type(schedule) is tuple and len(schedule) == 54, "Exactly 54 immutable entries required.")
    expected = tuple((case, repetition, variant) for case in CASE_IDS
                     for repetition in REPETITIONS for variant in VARIANTS)
    for index, (entry, key) in enumerate(zip(schedule, expected)):
        _typed(entry, ScheduleEntry)
        _need(entry.schedule_index == index
              and (entry.case_id, entry.repetition, entry.variant) == key,
              "Schedule must retain exact case/repetition/variant order.")
    # The exact Cartesian order above implies uniqueness, six per case and two
    # per case/variant; no randomization or outcome-dependent filtering exists.
    return schedule


def build_schedule():
    keys = ((case, repetition, variant) for case in CASE_IDS
            for repetition in REPETITIONS for variant in VARIANTS)
    return validate_schedule(tuple(ScheduleEntry(index, *key) for index, key in enumerate(keys)))


@dataclass(frozen=True, slots=True)
class E1Plan:
    prerequisite: AcceptedE0Prerequisite
    source_identity: E1SourceIdentity
    runtime: RuntimeIdentity
    cases: tuple[SealedCaseRegistration, ...]
    schedule: tuple[ScheduleEntry, ...]
    stage: str = "E1"
    purpose: str = PLAN_PURPOSE
    actual_execution_authorized: bool = False
    supplement_status: str = "NOT_EVALUATED"
    repetition_purpose: str = REPETITION_PURPOSE
    productive_chord_requirement: str = PRODUCTIVE_CHORD_REQUIREMENT
    qualification_scope: str = QUALIFICATION_SCOPE

    def __post_init__(self):
        prerequisite = _typed(self.prerequisite, AcceptedE0Prerequisite)
        source = _typed(self.source_identity, E1SourceIdentity)
        _typed(self.runtime, RuntimeIdentity)
        _need(source.base_source_digest == prerequisite.source_digest
              and all(getattr(source, name) == getattr(prerequisite, name) for name in
                      ("spec_sha256", "protocol_sha256", "model_id", "profile_sha256", "table_sha256")),
              "E1 source/prerequisite binding differs.")
        _need(type(self.cases) is tuple and len(self.cases) == 9
              and all(type(c) is SealedCaseRegistration for c in self.cases)
              and tuple(c.case_id for c in self.cases) == CASE_IDS, "Nine fixed seals in order required.")
        for case in self.cases:
            _typed(case, SealedCaseRegistration)
            _need(case.runtime == self.runtime, "Case/runtime seal mismatch.")
        validate_schedule(self.schedule)
        _need(all(type(v) is str for v in
                  (self.stage, self.purpose, self.supplement_status, self.repetition_purpose,
                   self.productive_chord_requirement, self.qualification_scope))
              and self.stage == "E1" and self.purpose == PLAN_PURPOSE
              and self.actual_execution_authorized is False
              and self.supplement_status == "NOT_EVALUATED"
              and self.repetition_purpose == REPETITION_PURPOSE
              and self.productive_chord_requirement == PRODUCTIVE_CHORD_REQUIREMENT
              and self.qualification_scope == QUALIFICATION_SCOPE,
              "Slice 1 is a prospective plan, not execution authorization or qualification.")


def build_e1_plan(path=None):
    """Read accepted prerequisites and seal a plan; no cases are executed."""
    prerequisite = load_accepted_e0_prerequisite(path)
    source = capture_e1_source_identity(prerequisite)
    runtime = capture_runtime_identity()
    cases = _seal_fixed_cases(runtime)
    _need(capture_e1_source_identity(prerequisite) == source,
          "Source changed during prospective sealing.")
    return E1Plan(prerequisite, source, runtime, cases, build_schedule())
