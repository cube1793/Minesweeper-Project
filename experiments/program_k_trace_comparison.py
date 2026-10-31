"""D4.1: exact CONTROL / K-P0 pairs from one preserved E1 publication.

No playback state, shared progress, execution, UI, or file access on navigation.
Byte factories authenticate both adapters before publishing the complete tuple.
The pair constructor accepts already-admitted models and checks their pairing;
it is not a substitute for the byte factories' evidence authentication.
"""

from dataclasses import dataclass, fields

from experiments import program_k_control_trace_adapter as control
from experiments import program_k_trace_adapter as k


K_PAIR_INDICES = tuple(i + 2 for i in control.CONTROL_SCHEDULE_INDICES)
DIFFERENCE_LABEL = "Recorded difference for this preserved case"
DIFFERENCE_DIRECTION = "K-P0 minus CONTROL"
LIMITATION = "Single preserved research case; not E2 effectiveness evidence."


class TraceComparisonError(ValueError):
    """A fixed, complete, exact same-board pair could not be admitted."""


def _need(condition, message):
    if not condition:
        raise TraceComparisonError(message)


# Closed model types only; no generic evidence/event abstraction or coercion.
_IMMUTABLE_MODELS = (
    control.ControlTracePresentation, control.ControlTraceProvenance,
    control.ControlCaseIdentity, control.ControlActionView, control.ControlTraceFrame,
    control.RecordedRunIdentity, k.KTracePresentation, k.KTraceProvenance,
    k.KCaseIdentity, k.KActionView, k.KTraceFrame, k.KAcquisitionView,
    k.EvidenceReference, k.HistoricalSourceFile, k.TerminalAnswerReference,
)


def _immutable(value):
    if type(value) in (str, int, bool, type(None)):
        return
    if type(value) in (tuple, frozenset):
        for item in value:
            _immutable(item)
        return
    _need(type(value) in _IMMUTABLE_MODELS, "Pair input must contain only immutable admitted model values.")
    for field in fields(value):
        _immutable(getattr(value, field.name))


@dataclass(frozen=True, slots=True)
class ComparisonPairIdentity:
    run_id: str
    case_id: str
    repetition: int
    control_schedule_index: int
    kp0_schedule_index: int
    width: int
    height: int
    num_mines: int
    first_click: tuple[int, int]
    board_fingerprint: str


@dataclass(frozen=True, slots=True)
class RecordedTraceFacts:
    outcome: str
    total_inputs: int
    open_inputs: int
    flag_inputs: int
    chord_inputs: int
    model_c_total_us: int
    explicit_physical_flags: int
    automatic_win_flags: int
    board_fingerprint: str


@dataclass(frozen=True, slots=True)
class RecordedDifference:
    total_inputs: int
    open_inputs: int
    flag_inputs: int
    chord_inputs: int
    model_c_us: int | None
    model_c_applicability: str
    label: str = DIFFERENCE_LABEL
    direction: str = DIFFERENCE_DIRECTION


def _facts(view):
    actions = tuple(a.action for a in view.actions)
    return RecordedTraceFacts(
        view.terminal_status, len(actions), actions.count("OPEN"), actions.count("FLAG"),
        actions.count("CHORD"), view.total_modeled_us, len(view.frames[-1].explicit_flags),
        len(view.frames[-1].automatic_flags), view.case.board_fingerprint)


def _complete(view, run, variant):
    action_type = control.ControlActionView if variant == "CONTROL" else k.KActionView
    frame_type = control.ControlTraceFrame if variant == "CONTROL" else k.KTraceFrame
    _need(type(view.actions) is tuple and type(view.frames) is tuple
          and all(type(a) is action_type for a in view.actions)
          and all(type(f) is frame_type for f in view.frames)
          and type(view.answer_reference) is k.TerminalAnswerReference,
          "Pair requires exact physical action/frame/reference models.")
    _need(type(run) is control.RecordedRunIdentity and run.variant == variant
          and type(run.schedule_index) is int and run.schedule_index == view.case.schedule_index
          and run.operation_id == f"SCHEDULED_RUN:{run.schedule_index:02d}"
          and type(run.payload_size) is int and run.payload_size > 0
          and type(run.payload_sha256) is str and len(run.payload_sha256) == 64
          and all(c in "0123456789abcdef" for c in run.payload_sha256), "Scheduled run identity mismatch.")
    expected_types = (
        (run.operation, "experiments.program_k_e1_operational.E1OperationResult"),
        (run.archive, "experiments.program_k_e1_execution.E1ScheduledRunArchive"),
        (run.result, "experiments.program_k_runner." + ("ControlCaptureResult" if variant == "CONTROL" else "KRunResult")),
        (run.audit, "experiments.program_k_e1_audit.E1RunAudit"),
        (run.registration, "experiments.program_k_e1_harness.SealedCaseRegistration"),
        (run.materialization, "experiments.program_k_e1_execution.CaseMaterializationReceipt"),
    )
    for ref, record_type in expected_types:
        _need(type(ref) is k.EvidenceReference and ref.record_type == record_type,
              "Scheduled evidence reference type mismatch.")
    for ref in tuple(r for r, _ in expected_types) + run.traces + run.effects:
        _need(ref.artifact_sha256 == k.QUALIFICATION_SHA256 and type(ref.node_index) is int
              and 0 <= ref.node_index < 194_219, "Foreign or invalid scheduled evidence reference.")
    count = len(view.actions)
    _need(0 < count <= view.case.width * view.case.height and len(view.frames) == count + 1
          and view.frames[-1].status in ("WON", "LOST"), "Pair requires two complete physical traces.")
    _need(run.traces == tuple(a.trace for a in view.actions)
          and run.effects == tuple(a.effect for a in view.actions), "Scheduled result/action binding mismatch.")
    initial = view.frames[0]
    _need(initial.index == 0 and initial.status == "PLAYING" and initial.cumulative_modeled_us == 0
          and initial.cursor == view.case.first_click and not initial.explicit_flags
          and not initial.automatic_flags
          and initial.observation == tuple((k.HIDDEN,) * view.case.width for _ in range(view.case.height)),
          "Invalid initial physical frame.")
    cumulative = 0
    for i, action in enumerate(view.actions):
        prior, frame = view.frames[i:i + 2]
        _need(type(action.modeled_action_us) is int and action.modeled_action_us > 0,
              "Invalid exact Model-C action cost.")
        cumulative += action.modeled_action_us
        _need(type(action.input_index) is int and action.input_index == i
              and action.action in ("OPEN", "FLAG", "CHORD")
              and action.cursor_before == prior.cursor and prior.status == "PLAYING"
              and frame.index == i + 1 and frame.cursor == action.target
              and action.status_after == frame.status
              and action.cumulative_modeled_us == frame.cumulative_modeled_us == cumulative,
              "Incomplete or inconsistent physical action/frame sequence.")
    _need(view.actions[0].action == "OPEN" and view.actions[0].target == view.case.first_click
          and view.answer_reference.terminal_effect == view.actions[-1].effect,
          "First input/terminal reference binding mismatch.")


@dataclass(frozen=True, slots=True)
class ProgramKComparisonPair:
    """Two independent complete traces; no common playhead is defined."""

    control: control.ControlTracePresentation
    kp0: k.KTracePresentation
    kp0_run: control.RecordedRunIdentity

    def __post_init__(self):
        c, p = self.control, self.kp0
        _need(type(c) is control.ControlTracePresentation and type(p) is k.KTracePresentation,
              "Pair requires separate CONTROL and D1 K-P0 presentation types.")
        for value in (c, p, self.kp0_run):
            _immutable(value)
        ci, ki = c.case, p.case
        _need(type(ci) is control.ControlCaseIdentity and type(ki) is k.KCaseIdentity
              and type(ci.schedule_index) is int and ci.schedule_index in control.CONTROL_SCHEDULE_INDICES
              and type(ki.schedule_index) is int and ki.schedule_index == ci.schedule_index + 2
              and type(ci.repetition) is int and type(ki.repetition) is int
              and ci.repetition == ki.repetition == 1
              and ci.variant == "CONTROL" and ki.variant == "K-P0", "Fixed pair schedule/variant/repetition mismatch.")
        expected = control.FIXED_CASES[control.CONTROL_SCHEDULE_INDICES.index(ci.schedule_index)]
        _need((ci.case_id, ci.width, ci.height, ci.num_mines, ci.board_fingerprint) == expected[1:]
              and ci.first_click == (0, 0), "Fixed pair case identity mismatch.")
        for field in fields(ki):
            if field.name not in ("schedule_index", "variant"):
                _need(getattr(ci, field.name) == getattr(ki, field.name), "Pair case/source mismatch: " + field.name)
        _need(type(c.provenance) is control.ControlTraceProvenance
              and type(p.provenance) is k.KTraceProvenance and c.provenance.variant == "CONTROL",
              "Pair provenance type/variant mismatch.")
        for field in fields(p.provenance):
            _need(getattr(c.provenance, field.name) == getattr(p.provenance, field.name),
                  "Pair historical source/publication mismatch: " + field.name)
        for name, value in (("run_id", k.ACCEPTED_RUN_ID), ("qualification_sha256", k.QUALIFICATION_SHA256),
                            ("qualification_size", k.QUALIFICATION_SIZE), ("complete_sha256", k.COMPLETE_SHA256),
                            ("profile_sha256", k.PROFILE_SHA256), ("table_sha256", k.TABLE_SHA256),
                            ("model_id", k.MODEL_ID), ("scope", k.RESEARCH_SCOPE),
                            ("no_effectiveness_claim", k.NO_EFFECTIVENESS_CLAIM)):
            _need(getattr(p.provenance, name) == value, "Pair publication/profile/scope mismatch: " + name)
        _complete(c, c.run, "CONTROL")
        _complete(p, self.kp0_run, "K-P0")
        for name in ("operation_id", "payload_sha256", "operation", "archive", "result", "audit"):
            _need(getattr(c.run, name) != getattr(self.kp0_run, name), "Pair must own distinct scheduled executions.")
        _need(c.run.registration == self.kp0_run.registration
              and c.run.materialization == self.kp0_run.materialization,
              "Pair registration/materialization binding mismatch.")
        mines = c.answer_reference.mines
        _need(mines == p.answer_reference.mines and len(mines) == ci.num_mines
              and all(type(x) is int and type(y) is int and 0 <= x < ci.width and 0 <= y < ci.height for x, y in mines)
              and c.answer_reference.board_fingerprint == p.answer_reference.board_fingerprint == ci.board_fingerprint
              and k._fingerprint(ci.width, ci.height, ci.num_mines, mines) == ci.board_fingerprint,
              "Pair terminal layout/fingerprint mismatch.")

    @property
    def identity(self):
        c = self.control.case
        return ComparisonPairIdentity(self.control.provenance.run_id, c.case_id, 1, c.schedule_index,
                                      self.kp0.case.schedule_index, c.width, c.height, c.num_mines,
                                      c.first_click, c.board_fingerprint)

    @property
    def control_facts(self):
        return _facts(self.control)

    @property
    def kp0_facts(self):
        return _facts(self.kp0)

    @property
    def difference(self):
        c, p = self.control_facts, self.kp0_facts
        ww = c.outcome == p.outcome == "WON"
        return RecordedDifference(p.total_inputs - c.total_inputs, p.open_inputs - c.open_inputs,
                                  p.flag_inputs - c.flag_inputs, p.chord_inputs - c.chord_inputs,
                                  p.model_c_total_us - c.model_c_total_us if ww else None,
                                  "WW recorded Model-C difference" if ww else
                                  "N/A: not applicable for speed-to-win interpretation")


def project_accepted_e1_pairs(qualification_bytes: bytes, complete_bytes: bytes, profile_bytes: bytes):
    """Publish all four repetition-1 pairs, or raise without publishing any pair."""
    try:
        graph, operations, plan, execution, audit, provenance, table = control._admit_publication(
            qualification_bytes, complete_bytes, profile_bytes)
        controls = tuple(control._project_run(graph, operations[i], i, plan, execution, audit, provenance, table)
                         for i in control.CONTROL_SCHEDULE_INDICES)
        # D1 retains sole authority for K admission, including K knowledge/proofs.
        kp0s = k.project_accepted_e1_traces(qualification_bytes, complete_bytes, profile_bytes,
                                          schedule_indices=K_PAIR_INDICES)
        runs = tuple(control._run_binding(graph, operations[i], i, "K-P0", plan, execution, audit, provenance)[3]
                     for i in K_PAIR_INDICES)
        return tuple(ProgramKComparisonPair(c, p, run) for c, p, run in zip(controls, kp0s, runs, strict=True))
    except (control.ControlTraceAdapterError, k.KTraceAdapterError, KeyError, TypeError, IndexError,
            RecursionError) as exc:
        raise TraceComparisonError("Accepted comparison refused: " + str(exc)) from exc


def load_accepted_e1_pairs(artifact_directory, *, profile_path=k._DEFAULT_PROFILE):
    """Read each of the three pinned files once; return immutable in-memory pairs."""
    try:
        return project_accepted_e1_pairs(*control._read_publication(artifact_directory, profile_path))
    except control.ControlTraceAdapterError as exc:
        raise TraceComparisonError("Cannot read accepted comparison: " + str(exc)) from exc
