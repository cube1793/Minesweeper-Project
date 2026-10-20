"""Program-K E1 Slice 2: fresh materialization and one scheduled invocation.

This harness boundary confers no research execution authorization. The caller
owns that separate decision. Source identities and receipts are provenance only,
never policy inputs. Imports perform no materialization, artifact reads or runs.
"""

from dataclasses import asdict, dataclass, fields, replace
from fractions import Fraction
import hashlib
import json
from math import isfinite
from pathlib import Path

import benchmark_board as _board
from board_snapshot import BoardSnapshot
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from experiments import program_k_capability as _capability
from experiments import program_k_e1_harness as _e1
from experiments import program_k_evidence as _evidence
from experiments import program_k_oracles as _oracles
from experiments import program_k_policy as _policy
from experiments import program_k_runner as _runner
from simple_algorithm import Constraint, InferenceResult, SimpleMove
from simple_decision import DecisionKind, SimpleDecision
from simple_probability import CellProbability, ProbabilityResult
import stage3_physical as _physical
from stage3_planner import RevealPlan, Stage3Decision
from stage3_runner import Stage3ActionTrace, Stage3RunResult


EXECUTION_SOURCE_PATH = "experiments/program_k_e1_execution.py"
_AUTHORITY_FIELDS = (
    "spec_sha256", "protocol_sha256", "model_id", "profile_sha256", "table_sha256",
)


class E1ExecutionError(ValueError):
    """One invocation failed closed; no replacement action or retry."""


def _need(condition, detail):
    if not condition:
        raise E1ExecutionError(detail)


def _checked(value, cls):
    _need(type(value) is cls, "Expected exact " + cls.__name__ + ".")
    try:
        return replace(value)
    except (ValueError, TypeError, AttributeError) as error:
        raise E1ExecutionError("Invalid " + cls.__name__ + ".") from error


def _sha(value):
    _need(type(value) is str and len(value) == 64
          and all(c in "0123456789abcdef" for c in value), "Invalid SHA-256 identity.")


def _timeout(value):
    # Check range before isfinite, including arbitrarily large Python integers.
    _need(type(value) in (int, float) and 0 < value <= 60 and isfinite(value),
          "Shadow timeout must be a true int/float, finite and in (0, 60].")


@dataclass(frozen=True, slots=True)
class E1ExecutionSourceFile:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        _need(type(self.path) is str and self.path == EXECUTION_SOURCE_PATH,
              "Only the execution module extends this runtime identity.")
        _sha(self.sha256)
        _need(type(self.size_bytes) is int and self.size_bytes > 0,
              "Source byte size must be a positive true integer.")


@dataclass(frozen=True, slots=True)
class E1ExecutionSourceIdentity:
    plan_source_digest: str
    execution_file: E1ExecutionSourceFile
    spec_sha256: str
    protocol_sha256: str
    model_id: str
    profile_sha256: str
    table_sha256: str

    def __post_init__(self):
        _sha(self.plan_source_digest)
        _checked(self.execution_file, E1ExecutionSourceFile)
        try:
            _e1._frozen_identities(self)
        except ValueError as error:
            raise E1ExecutionError("Frozen execution authority mismatch.") from error

    @property
    def digest(self):
        _checked(self, E1ExecutionSourceIdentity)
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
        return hashlib.sha256(raw).hexdigest()


def _capture_execution_source_identity(plan, root):
    """Temporary-root seam for execution bytes; plan sources remain live."""
    plan = _checked(plan, _e1.E1Plan)
    try:
        current = _e1.capture_e1_source_identity(plan.prerequisite)
        _need(current == plan.source_identity, "Current Slice-1 source identity drifted.")
        raw = (Path(root) / EXECUTION_SOURCE_PATH).read_bytes()
        return E1ExecutionSourceIdentity(
            plan.source_identity.digest,
            E1ExecutionSourceFile(EXECUTION_SOURCE_PATH, hashlib.sha256(raw).hexdigest(), len(raw)),
            *(getattr(plan.prerequisite, name) for name in _AUTHORITY_FIELDS),
        )
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise E1ExecutionError("Execution source capture refused.") from error


def capture_execution_source_identity(plan):
    """Bind exact current plan and execution bytes without generating a board."""
    return _capture_execution_source_identity(plan, Path(__file__).resolve().parents[1])


@dataclass(frozen=True, slots=True)
class CaseMaterializationReceipt:
    """Detached construction provenance; never supplied to a runner."""

    case_id: str
    source_type: str
    width: int
    height: int
    num_mines: int
    first_click: tuple[int, int]
    game_index: int | None
    seed: int | None
    board_fingerprint: str
    runtime: _e1.RuntimeIdentity
    materialization_method: str
    fresh_engine: bool = True

    def __post_init__(self):
        try:
            definition = _e1._definition(self.case_id)
        except ValueError as error:
            raise E1ExecutionError("Unregistered materialization receipt.") from error
        for name in ("source_type", "width", "height", "num_mines", "game_index",
                     "board_fingerprint"):
            actual, expected = getattr(self, name), getattr(definition, name)
            _need(type(actual) is type(expected) and actual == expected,
                  "Receipt changed fixed case " + name + ".")
        _need(type(self.seed) is type(definition.game_index)
              and self.seed == definition.game_index, "Receipt seed mismatch.")
        _need(type(self.first_click) is tuple and self.first_click == (0, 0)
              and all(type(v) is int for v in self.first_click),
              "Receipt first click is not canonical.")
        _checked(self.runtime, _e1.RuntimeIdentity)
        method = ("FIXED_SYNTHETIC_RESET" if definition.game_index is None
                  else "EXPERT_GENERAL_V1_RESET")
        _need(type(self.materialization_method) is str and self.materialization_method == method
              and self.fresh_engine is True, "Receipt needs fresh fixed-case materialization.")


def _require_fresh_engine(engine, case):
    _need(type(engine) is MinesweeperEngine, "Materialization requires a new exact Engine.")
    _need(engine.status is GameStatus.PLAYING, "Fresh Engine must be PLAYING.")
    metadata = (engine.width, engine.height, engine.num_mines)
    _need(all(type(v) is int for v in metadata)
          and metadata == (case.width, case.height, case.num_mines),
          "Engine dimensions/count differ from the seal.")
    rows = engine.get_observation()
    _need(len(rows) == case.height and all(len(row) == case.width for row in rows)
          and all(value == CellState.HIDDEN for row in rows for value in row),
          "Fresh Engine must be entirely HIDDEN.")
    # Construction-side checks only; these values never enter policy evidence.
    counters = engine.get_counter_snapshot()
    _need(all(type(counters[name]) is int and counters[name] == 0 for name in
              ("active_clicks", "wasted_clicks", "completed_3bv", "completed_ops"))
          and engine._timer_started is False
          and engine._start_time is None and engine._end_time is None
          and engine._cells_to_reveal == case.width * case.height - case.num_mines,
          "Engine retains previous input state.")


def _materialize_case(case):
    """Private evaluator/harness seam: only Engine and layout-free receipt leave."""
    case = _checked(case, _e1.SealedCaseRegistration)
    try:
        definition = _e1._definition(case.case_id)
        runtime = _e1.capture_runtime_identity()
        _need(runtime == case.runtime, "Materialization runtime differs from the seal.")
        if case.game_index is None:
            mines = definition.mine_positions
            method = "FIXED_SYNTHETIC_RESET"
        else:
            spec = _board.EXPERT_GENERAL_V1
            _need(type(spec) is _board.BenchmarkSetSpec
                  and all(type(v) is int for v in
                          (spec.width, spec.height, spec.num_mines,
                           spec.first_click_x, spec.first_click_y))
                  and all(type(v) is str for v in
                          (spec.benchmark_set_id, spec.board_generator_version, spec.seed_scheme))
                  and (spec.benchmark_set_id, spec.width, spec.height, spec.num_mines,
                       spec.first_click_x, spec.first_click_y,
                       spec.board_generator_version, spec.seed_scheme)
                  == (case.benchmark_set_id, case.width, case.height, case.num_mines,
                      *case.first_click, case.board_generator_version, case.seed_scheme),
                  "Frozen Expert generator identity differs from the seal.")
            generated = _board.generate_board(spec, case.game_index)
            _need(type(generated) is _board.BenchmarkBoard
                  and type(generated.game_index) is int and type(generated.seed) is int
                  and generated.game_index == generated.seed == case.game_index == case.seed,
                  "Generated Expert index/seed mismatch.")
            mines = generated.mine_positions
            method = "EXPERT_GENERAL_V1_RESET"
        fingerprint = _board.calculate_board_fingerprint(
            case.width, case.height, case.num_mines, mines)
        _need(case.first_click not in mines, "Canonical first click must be safe.")
        _need(fingerprint == case.board_fingerprint, "Materialized fingerprint differs from seal.")
        if case.game_index is not None:
            _need(type(generated.board_fingerprint) is str
                  and generated.board_fingerprint == fingerprint,
                  "Generated fingerprint does not reconstruct.")
        engine = MinesweeperEngine(case.width, case.height, case.num_mines)
        engine.reset_with_mines(case.width, case.height, case.num_mines, mines)
        snapshot = engine.get_board_snapshot()
        _need(type(snapshot) is BoardSnapshot and snapshot.mines_placed is True
              and all(type(v) is int for v in
                      (snapshot.width, snapshot.height, snapshot.num_mines))
              and (snapshot.width, snapshot.height, snapshot.num_mines)
              == (case.width, case.height, case.num_mines)
              and _board.calculate_board_fingerprint(
                  snapshot.width, snapshot.height, snapshot.num_mines, snapshot.mines)
              == case.board_fingerprint, "Finalized Engine snapshot differs from seal.")
        _require_fresh_engine(engine, case)
        receipt = CaseMaterializationReceipt(
            case.case_id, case.source_type, case.width, case.height, case.num_mines,
            case.first_click, case.game_index, case.seed, fingerprint, runtime, method,
        )
        return engine, receipt
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        raise E1ExecutionError("Fixed-case materialization refused.") from error


# Closed public-result vocabulary. Logical M and public terminal effects are
# retained runner evidence; construction layouts and evaluator answers are not.
_RESULT_RECORD_TYPES = (
    _runner.ControlCaptureResult, _runner.KControlRunResult, _runner.KRunResult,
    _runner.KControlActionTrace, _runner.KActionTrace,
    _runner.ShadowCheckpoint, _runner.ShadowFailure,
    Stage3RunResult, Stage3ActionTrace, Stage3Decision, RevealPlan,
    SimpleMove, SimpleDecision, Constraint, InferenceResult, CellProbability, ProbabilityResult,
    _capability.Accounting, _capability.ClueAccounting, _capability.LocalAnalysis,
    _capability.ExactAnalysis, _capability.DecisionAnalysis,
    _policy.PolicySelection, _policy.KCandidate,
    _oracles.LocalMineCertificate, _oracles.ExactGlobalMineCertificate,
) + _evidence._EVIDENCE_TYPES


def _require_detached_result(value, active=None, checked=None):
    """Reject live/mutable/custom payloads, extra attachments and cycles."""
    if type(value) in (str, int, bool, type(None), Fraction, Action, CellState,
                       GameStatus, DecisionKind):
        return
    active = set() if active is None else active
    checked = set() if checked is None else checked
    key = id(value)
    _need(key not in active, "Cyclic result evidence.")
    if key in checked:
        return
    active.add(key)
    if type(value) in (tuple, frozenset):
        children = value
    else:
        _need(type(value) in _RESULT_RECORD_TYPES, "Unsupported live/hidden/mutable result value.")
        names = tuple(field.name for field in fields(value))
        _need(not hasattr(value, "__dict__") or set(vars(value)) == set(names),
              "Unexpected attachment on result evidence.")
        children = tuple(getattr(value, name) for name in names)
    for child in children:
        _require_detached_result(child, active, checked)
    active.remove(key)
    checked.add(key)


def _validate_result(variant, result, case):
    """Pure structure only; no oracle, semantic adjudication or answer access."""
    result_type, trace_type = {
        "CONTROL": (_runner.ControlCaptureResult, Stage3ActionTrace),
        "K-CONTROL": (_runner.KControlRunResult, _runner.KControlActionTrace),
        "K-P0": (_runner.KRunResult, _runner.KActionTrace),
    }[variant]
    _need(type(result) is result_type, "Variant/result class mismatch.")
    _require_detached_result(result)
    _need(type(result.status) is GameStatus
          and result.status in (GameStatus.WON, GameStatus.LOST), "Run is not terminal.")
    _need(type(result.traces) is tuple and bool(result.traces)
          and all(type(trace) is trace_type for trace in result.traces),
          "Complete immutable traces required.")
    if variant == "K-CONTROL":
        _need(type(result.shadow) is _runner.ShadowCheckpoint,
              "Missing final shadow checkpoint.")
    elif variant == "K-P0":
        _need(type(result.final_M) is frozenset, "Final logical M must be immutable.")
    if variant == "CONTROL":
        _checked(result, _runner.ControlCaptureResult)
        _need(result.capture_status == "COMPLETE", "CONTROL capture is incomplete.")
        effects = result.effects
    else:
        _need(all(type(trace.public_effect_status) is str
                  and trace.public_effect_status == "CAPTURED" for trace in result.traces),
              "Every input needs a captured public effect.")
        effects = tuple(trace.public_effect for trace in result.traces)
    _need(type(effects) is tuple and len(effects) == len(result.traces)
          and all(type(effect) is _evidence.PublicEffectRecord for effect in effects),
          "Missing paired public effects.")
    for index, (trace, effect) in enumerate(zip(result.traces, effects)):
        _checked(effect, _evidence.PublicEffectRecord)
        _need(type(trace.move) is SimpleMove and type(trace.move.action) is Action
              and all(type(v) is int for v in (trace.move.x, trace.move.y))
              and type(trace.modeled_action_us) is int
              and type(trace.status_after) is GameStatus
              and type(trace.cursor_before) is tuple
              and all(type(v) is int for v in trace.cursor_before)
              and effect.input_index == index
              and (effect.move.action, effect.move.x, effect.move.y)
              == (trace.move.action, trace.move.x, trace.move.y)
              and effect.status_after is trace.status_after
              and effect.cursor_before == trace.cursor_before
              and effect.modeled_action_us == trace.modeled_action_us,
              "Trace/effect bindings differ.")
        _need(len(effect.before_observation) == case.height
              and all(len(row) == case.width for row in effect.before_observation),
              "Public effects belong to different case dimensions.")
        if variant != "CONTROL":
            _need(type(trace.input_index) is int and trace.input_index == index,
                  "Trace input sequence differs.")
            _need(type(trace.M_before) is frozenset and type(trace.preinput_M) is frozenset
                  and type(trace.timings) is _evidence.DecisionTimings,
                  "Trace logical state/timing structure is malformed.")
        if variant == "K-CONTROL":
            _need(type(trace.shadow) is _runner.ShadowCheckpoint,
                  "Missing captured shadow checkpoint.")
        if index == 0:
            _need(trace.move == SimpleMove(Action.OPEN, *case.first_click)
                  and trace.cursor_before == case.first_click
                  and all(v == CellState.HIDDEN for row in effect.before_observation for v in row),
                  "Missing canonical initial public input.")
        else:
            previous = effects[index - 1]
            _need(previous.status_after is GameStatus.PLAYING
                  and effect.before_observation == previous.after_observation.rows
                  and effect.cursor_before == previous.cursor_after,
                  "Public effect sequence is incomplete or contains postterminal input.")
    _need(effects[-1].status_after is result.status, "Final public effect/status mismatch.")


@dataclass(frozen=True, slots=True)
class E1ScheduledRunArchive:
    execution_source_identity: E1ExecutionSourceIdentity
    plan_source_digest: str
    schedule_entry: _e1.ScheduleEntry
    case: _e1.SealedCaseRegistration
    receipt: CaseMaterializationReceipt
    result: _runner.ControlCaptureResult | _runner.KControlRunResult | _runner.KRunResult
    shadow_timeout_s: int | float
    shadow_timeout_usage: str
    completion_status: str = "COMPLETE"

    def __post_init__(self):
        source = _checked(self.execution_source_identity, E1ExecutionSourceIdentity)
        _sha(self.plan_source_digest)
        _need(source.plan_source_digest == self.plan_source_digest, "Plan source binding mismatch.")
        entry = _checked(self.schedule_entry, _e1.ScheduleEntry)
        case = _checked(self.case, _e1.SealedCaseRegistration)
        receipt = _checked(self.receipt, CaseMaterializationReceipt)
        _need(entry == _e1.build_schedule()[entry.schedule_index]
              and entry.case_id == case.case_id, "Schedule/case/repetition/variant substitution.")
        for name in ("case_id", "source_type", "width", "height", "num_mines", "first_click",
                     "game_index", "seed", "board_fingerprint", "runtime"):
            _need(getattr(receipt, name) == getattr(case, name), "Receipt/case binding mismatch.")
        _timeout(self.shadow_timeout_s)
        usage = "APPLIED" if entry.variant == "K-CONTROL" else "NOT_APPLICABLE"
        _need(type(self.shadow_timeout_usage) is str and self.shadow_timeout_usage == usage,
              "Incorrect timeout applicability.")
        _need(type(self.completion_status) is str and self.completion_status == "COMPLETE",
              "Only structurally complete results may be archived.")
        try:
            _validate_result(entry.variant, self.result, case)
        except (ValueError, TypeError, AttributeError, KeyError) as error:
            raise E1ExecutionError("Malformed scheduled result structure.") from error


def execute_scheduled_entry(plan, schedule_index, *, shadow_timeout_s=1.0):
    """Execute exactly one plan-owned entry; authorization is external to this API.

    The supplied timeout is retained exactly for every variant. Its usage is
    explicitly NOT_APPLICABLE for CONTROL/K-P0. It is operational containment,
    not a final case/job resource envelope or a substitute-action selector.
    """
    plan = _checked(plan, _e1.E1Plan)
    _need(type(schedule_index) is int and 0 <= schedule_index < len(plan.schedule),
          "Schedule index must be a true integer in 0..53.")
    _timeout(shadow_timeout_s)
    entry = plan.schedule[schedule_index]
    case = next(case for case in plan.cases if case.case_id == entry.case_id)
    source = capture_execution_source_identity(plan)
    engine, receipt = _materialize_case(case)
    try:
        table = _physical.load_timing_table()
        _require_fresh_engine(engine, case)
        if entry.variant == "CONTROL":
            result = _runner.run_control_capture(engine, table=table)
        elif entry.variant == "K-CONTROL":
            result = _runner.run_k_control(
                engine, table=table, shadow_timeout_s=shadow_timeout_s, capture_effects=True)
        else:
            result = _runner.run_k_p0(engine, table=table, capture_effects=True)
    except Exception as error:
        raise E1ExecutionError("Scheduled invocation failed without retry.") from error
    _need(capture_execution_source_identity(plan) == source,
          "Source changed during scheduled invocation.")
    return E1ScheduledRunArchive(
        source, plan.source_identity.digest, entry, case, receipt, result,
        shadow_timeout_s, "APPLIED" if entry.variant == "K-CONTROL" else "NOT_APPLICABLE",
    )
