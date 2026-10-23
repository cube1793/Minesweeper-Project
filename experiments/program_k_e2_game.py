"""I4 per-game projection over the existing CONTROL and K-P0 runners.

Only supplied Engines are executed; no board generation, coordinator, persistence
or research qualification is owned here. Public captures are projected directly,
with terminal disclosures segregated. The existing harness codec is used only
for one public certificate at a time, never for an execution archive or audit.
"""

from dataclasses import dataclass, replace
from fractions import Fraction
from functools import wraps

from core_engine import Action, CellState, GameStatus
from experiments import program_k_e2_records as records
from experiments import program_k_runner as runner
from experiments import program_k_evidence as evidence
from experiments import program_k_capability as capability
from experiments import program_k_policy as policy
from experiments.program_k_harness import content_digest
from stage3_physical import action_cost, validate_timing_table
from stage3_planner import Stage3Decision, RevealPlan
from stage3_runner import Stage3ActionTrace, Stage3RunResult


class GameProjectionError(ValueError):
    """Malformed or contradictory evidence; never retry or substitute an input."""


def _need(condition, message):
    if not condition:
        raise GameProjectionError(message)


def _integer(value, minimum=0):
    _need(type(value) is int and value >= minimum, "Expected exact integer in bounds.")


def _record(value, cls):
    _need(type(value) is cls, "Unexpected record type/subclass: " + cls.__name__)
    try:
        cls.__post_init__(value)
    except (ValueError, TypeError, AttributeError) as error:
        raise GameProjectionError(str(error)) from error


def _guard(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except GameProjectionError:
            raise
        except (ValueError, TypeError, AttributeError, IndexError, KeyError,
                StopIteration, ZeroDivisionError, runner.Stage3RunnerError) as error:
            raise GameProjectionError(str(error) or type(error).__name__) from error
    return checked


def _cells(cells):
    return tuple(sorted(cells, key=lambda cell: (cell[1], cell[0])))


def _inside(cell, board):
    _need(type(cell) is tuple and len(cell) == 2
          and all(type(v) is int for v in cell)
          and 0 <= cell[0] < board.width and 0 <= cell[1] < board.height,
          "Coordinate outside supplied board identity.")


def _status(value):
    _need(type(value) is GameStatus, "Expected exact public Engine status.")
    return records.Status[value.name]


def _outcome(value):
    _status(value)
    return {GameStatus.WON: records.Outcome.WIN, GameStatus.LOST: records.Outcome.LOSS,
            GameStatus.PLAYING: records.Outcome.INCOMPLETE}[value]


def _arm(arm, expected):
    _record(arm, records.ArmIdentity)
    _need(arm.arm is expected and arm.board.first_click == (0, 0)
          and arm.board.width <= 30 and arm.board.height <= 16,
          "I4 requires the named canonical arm and origin first click.")


def _closed(value):
    if type(value) in (str, int, bool, Fraction, type(None), records.Outcome):
        return
    _need(type(value) is tuple, "Divergence detail cannot retain mutable/live evidence.")
    for child in value:
        _closed(child)


@dataclass(frozen=True, slots=True)
class P3Divergence:
    guess_ordinal: int | None
    field: str
    control_value: object
    kp0_value: object

    def __post_init__(self):
        if self.guess_ordinal is not None:
            _integer(self.guess_ordinal, 1)
        _need(type(self.field) is str and bool(self.field), "Missing divergence field.")
        _closed(self.control_value)
        _closed(self.kp0_value)
        _need(self.control_value != self.kp0_value, "Divergence must record different values.")


@dataclass(frozen=True, slots=True)
class P3Comparison:
    status: records.P3Status
    reason: str
    divergence: P3Divergence | None

    def __post_init__(self):
        _need(type(self.status) is records.P3Status and type(self.reason) is str and bool(self.reason),
              "Missing typed P-3 comparison.")
        if self.divergence is not None:
            _record(self.divergence, P3Divergence)
        _need((self.status is records.P3Status.FAIL) == (self.divergence is not None),
              "P-3 FAIL requires its exact first divergence.")


_P3_FIELDS = (
    ("guess_ordinal", "guess_ordinal"), ("public_clues", "public_clues"),
    ("physical_p", "effective_p_union_m"), ("unresolved", "unresolved"),
    ("mine_budget", "mine_budget"), ("unreduced_z", "unreduced_z"),
    ("mine_counts", "mine_counts"), ("probabilities", "probabilities"),
    ("minimum_risk", "minimum_risk"), ("minimum_ties", "minimum_ties"),
    ("chosen_target", "chosen_target"), ("eventual_outcome", "eventual_outcome"),
)


def _compare_checkpoint_fields(left, right):
    """Field comparator after ownership validation; no physical-action pairing."""
    for control_field, kp0_field in _P3_FIELDS:
        expected, actual = getattr(left, control_field), getattr(right, kp0_field)
        if expected != actual:
            return P3Divergence(left.guess_ordinal, control_field, expected, actual)
    return None


@_guard
def compare_p3(control_checkpoints, kp0_checkpoints, *, control_complete=True, kp0_complete=True):
    for complete in (control_complete, kp0_complete):
        _need(type(complete) is bool, "P-3 completeness must be exact bool.")
    boards = []
    for checkpoints, expected_arm in ((control_checkpoints, records.Arm.CONTROL),
                                      (kp0_checkpoints, records.Arm.K_P0)):
        _need(type(checkpoints) is tuple, "Checkpoints must be an owned tuple.")
        board = None
        for ordinal, checkpoint in enumerate(checkpoints, 1):
            _record(checkpoint, records.GuessCheckpointRecord)
            _need(checkpoint.arm.arm is expected_arm and checkpoint.guess_ordinal == ordinal,
                  "Wrong arm or noncontiguous uncertain-guess ordinal.")
            _need(board is None or checkpoint.arm.board == board, "Checkpoint board identity drift.")
            board = checkpoint.arm.board
        boards.append(board)
    _need(None in boards or boards[0] == boards[1], "P-3 requires the same supplied board identity.")
    if not control_complete or not kp0_complete:
        return P3Comparison(records.P3Status.INCOMPLETE, "MISSING_P3_EVIDENCE", None)
    if len(control_checkpoints) != len(kp0_checkpoints):
        divergence = P3Divergence(min(len(control_checkpoints), len(kp0_checkpoints)) + 1,
                                  "checkpoint_count", len(control_checkpoints), len(kp0_checkpoints))
        return P3Comparison(records.P3Status.FAIL, "CHECKPOINT_COUNT_MISMATCH", divergence)
    for left, right in zip(control_checkpoints, kp0_checkpoints):
        divergence = _compare_checkpoint_fields(left, right)
        if divergence is not None:
            return P3Comparison(records.P3Status.FAIL, "CHECKPOINT_FIELD_MISMATCH", divergence)
    return P3Comparison(records.P3Status.PASS, "P3_MATCH", None)


@dataclass(frozen=True, slots=True)
class GameProjection:
    arm: records.ArmIdentity
    outcome: records.Outcome
    physical_inputs: tuple
    public_effects: tuple
    terminal_effects: tuple
    decision_spans: tuple
    guess_checkpoints: tuple
    flag_provenance: tuple
    acquisitions: tuple
    decisions: tuple[records.ActionDecisionRecord, ...]
    total_model_us: int
    comparable_compute_ns: int | None
    effect_evidence_complete: bool
    p3_evidence_complete: bool
    g5_evidence_complete: bool
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self):
        _record(self.arm, records.ArmIdentity)
        _need(self.arm.arm in (records.Arm.CONTROL, records.Arm.K_P0), "K-CONTROL is not I4.")
        _arm(self.arm, self.arm.arm)
        _need(type(self.outcome) is records.Outcome, "Expected exact outcome.")
        for items, cls in ((self.physical_inputs, records.PhysicalInputRecord),
                           (self.public_effects, records.PublicEffectRecord),
                           (self.terminal_effects, records.TerminalEffectRecord),
                           (self.decision_spans, records.DecisionSpanRecord),
                           (self.guess_checkpoints, records.GuessCheckpointRecord),
                           (self.flag_provenance, records.ControlFlagProvenanceRecord),
                           (self.acquisitions, records.AcquisitionRecord),
                           (self.decisions, records.ActionDecisionRecord)):
            _need(type(items) is tuple, "Published evidence must be an exact tuple.")
            for item in items:
                _record(item, cls)
        for value in (self.effect_evidence_complete, self.p3_evidence_complete, self.g5_evidence_complete):
            _need(type(value) is bool, "Completeness must be exact bool.")
        _integer(self.total_model_us)
        if self.comparable_compute_ns is not None:
            _integer(self.comparable_compute_ns)
        board, cursor, total = self.arm.board, (0, 0), 0
        _need(bool(self.physical_inputs), "Projection requires physical input evidence.")
        for ordinal, item in enumerate(self.physical_inputs):
            _inside(item.target, board)
            _inside(item.cursor_before, board)
            _need(item.action_ordinal == ordinal and item.cursor_before == cursor and item.input_us > 0,
                  "Physical ordinals/cursor/cost are inconsistent.")
            if ordinal == 0:
                _need(item.action is records.Action.OPEN and item.target == board.first_click,
                      "Initial OPEN differs from supplied first click.")
            else:
                _need(self.physical_inputs[ordinal - 1].after_status is records.Status.PLAYING,
                      "Postterminal physical input.")
            total += item.input_us
            _need(item.cumulative_us == total, "Cumulative Model C mismatch.")
            cursor = item.target
        _need(total == self.total_model_us, "Final Model C total mismatch.")
        final = self.physical_inputs[-1].after_status
        if self.outcome in (records.Outcome.WIN, records.Outcome.LOSS):
            _need(final is (records.Status.WON if self.outcome is records.Outcome.WIN else records.Status.LOST),
                  "Outcome and physical terminal status differ.")
        else:
            _need(self.outcome is records.Outcome.INCOMPLETE and final is records.Status.PLAYING,
                  "Incomplete outcome requires a nonterminal physical prefix.")
        _need(not self.p3_evidence_complete or self.effect_evidence_complete,
              "P-3 cannot be complete with missing public effects.")
        public_ordinals = tuple(item.action_ordinal for item in self.public_effects)
        _need(public_ordinals == tuple(sorted(set(public_ordinals))), "Duplicate/out-of-order public effects.")
        for item in self.public_effects:
            _need(item.action_ordinal < len(self.physical_inputs)
                  and item.after_status is self.physical_inputs[item.action_ordinal].after_status,
                  "Public/physical status binding differs.")
            for change in item.changes:
                _inside(change.cell, board)
        if self.effect_evidence_complete:
            _need(public_ordinals == tuple(range(len(self.physical_inputs))), "Missing public input coverage.")
        terminal_ordinals = tuple(item.action_ordinal for item in self.terminal_effects)
        _need(terminal_ordinals == tuple(sorted(set(terminal_ordinals))), "Duplicate terminal effects.")
        for item in self.terminal_effects:
            _need(item.action_ordinal == len(self.physical_inputs) - 1 and item.terminal_status is final,
                  "Terminal effects must bind the final physical input.")
            for change in item.changes:
                _inside(change.cell, board)
        if self.effect_evidence_complete and final is not records.Status.PLAYING:
            _need(terminal_ordinals == (len(self.physical_inputs) - 1,), "Missing terminal lane.")
        scope = (records.DecisionScope.CONTROL_PLAN_POSITION if self.arm.arm is records.Arm.CONTROL
                 else records.DecisionScope.K_ANALYZE_DECISION_THROUGH_SELECT_POLICY)
        _need(tuple(span.action_ordinal for span in self.decision_spans) == tuple(range(1, len(self.physical_inputs)))
              and all(span.scope is scope for span in self.decision_spans), "Comparable span coverage/scope differs.")
        expected_compute = (None if any(span.duration_ns is None for span in self.decision_spans)
                            else sum(span.duration_ns for span in self.decision_spans))
        _need(self.comparable_compute_ns == expected_compute, "Comparable compute sum mismatch.")
        for ordinal, checkpoint in enumerate(self.guess_checkpoints, 1):
            _need(checkpoint.arm == self.arm and checkpoint.guess_ordinal == ordinal
                  and checkpoint.eventual_outcome is self.outcome, "Checkpoint arm/ordinal/outcome binding differs.")
        if self.arm.arm is records.Arm.K_P0:
            _need(not self.flag_provenance, "CONTROL FLAG provenance cannot belong to K-P0.")
        else:
            _need(not self.acquisitions, "K acquisitions cannot belong to CONTROL.")
        flag_ordinals = tuple(item.flag_ordinal for item in self.flag_provenance)
        _need(flag_ordinals == tuple(sorted(set(flag_ordinals))), "Duplicate FLAG provenance.")
        for item in self.flag_provenance:
            _need(item.flag_ordinal < len(self.physical_inputs), "Unknown FLAG input.")
            physical = self.physical_inputs[item.flag_ordinal]
            _need(physical.action is records.Action.FLAG and physical.target == item.cell, "FLAG provenance binding differs.")
            if item.terminal_target is not None:
                _inside(item.terminal_target, board)
            if item.witness is not None:
                witness = item.witness
                _need(witness.action_ordinal < len(self.physical_inputs), "Witness input is absent.")
                chord = self.physical_inputs[witness.action_ordinal]
                _need(chord.action is records.Action.CHORD and chord.target == witness.clue,
                      "Witness is not bound to its actual CHORD.")
                for cell in witness.physical_flag_neighbors + witness.directly_opened_safe_cells:
                    _inside(cell, board)
        if self.g5_evidence_complete and self.arm.arm is records.Arm.CONTROL:
            _need(flag_ordinals == tuple(p.action_ordinal for p in self.physical_inputs if p.action is records.Action.FLAG),
                  "Missing CONTROL FLAG classification.")
        for item in self.acquisitions:
            _need(0 < item.action_ordinal < len(self.physical_inputs)
                  and item.decision_ordinal == item.action_ordinal - 1, "Acquisition boundary differs.")
            _inside(item.cell, board)
            _need(item.certificate_ref == "sha256:" + item.certificate_sha256, "Acquisition reference/digest differ.")
        _need(type(self.diagnostics) is tuple and all(type(s) is str and bool(s) for s in self.diagnostics),
              "Diagnostic reasons must be an immutable string tuple.")
        _validate_decision_bindings(self.arm, self.physical_inputs, self.decisions, self.acquisitions)
        if self.effect_evidence_complete:
            _replay_public_projection(self)


@dataclass(frozen=True, slots=True)
class PairedGameProjection:
    control: GameProjection
    kp0: GameProjection
    pair: records.PairComparisonRecord
    p3: P3Comparison

    def __post_init__(self):
        _record(self.control, GameProjection)
        _record(self.kp0, GameProjection)
        _record(self.pair, records.PairComparisonRecord)
        _record(self.p3, P3Comparison)
        _need(self.control.arm.arm is records.Arm.CONTROL and self.kp0.arm.arm is records.Arm.K_P0
              and self.control.arm.board == self.kp0.arm.board == self.pair.board
              and self.control.arm.run_id == self.kp0.arm.run_id, "Pair identities do not correspond.")
        _need(self.pair.control_outcome is self.control.outcome and self.pair.kp0_outcome is self.kp0.outcome,
              "Pair outcomes differ from projections.")
        expected_delta = (self.kp0.total_model_us - self.control.total_model_us
                          if self.control.outcome is self.kp0.outcome is records.Outcome.WIN else None)
        _need(self.pair.ww_delta_us == expected_delta, "Pair WW delta sign/value mismatch.")
        expected_p3 = compare_p3(self.control.guess_checkpoints, self.kp0.guess_checkpoints,
                                 control_complete=self.control.p3_evidence_complete,
                                 kp0_complete=self.kp0.p3_evidence_complete)
        _need(self.p3 == expected_p3 and self.pair.p3_status is self.p3.status
              and self.pair.g5 == summarize_g5(self.control.flag_provenance), "Pair P-3/G5 claim mismatch.")


def _aligned_effects(raw, size):
    _need(type(raw) is tuple, "Effects must be an exact tuple.")
    aligned = [None] * size
    previous = -1
    for effect in raw:
        if effect is None:
            continue
        _need(type(effect) is evidence.PublicEffectRecord, "Malformed public effect record.")
        # Existing validation reconstructs the closed capture type without inference.
        effect = replace(effect)
        _need(previous < effect.input_index < size and aligned[effect.input_index] is None,
              "Duplicate/out-of-order/out-of-range public effect ordinal.")
        aligned[effect.input_index] = effect
        previous = effect.input_index
    if all(effect is not None for effect in aligned):
        check = evidence.validate_public_effect_stream(tuple(aligned), complete=True)
        _need(check.status != "FAIL", "Public effect stream: " + check.detail)
    return tuple(aligned)


def _public_state(value):
    if value == CellState.HIDDEN:
        return "HIDDEN"
    if value == CellState.FLAGGED:
        return "FLAGGED"
    _need(type(value) is int and 0 <= value <= 8, "Answer-bearing glyph cannot enter public effects.")
    return "CLUE_" + str(value)


def _project_effect(effect):
    public, terminal = [], []
    terminal_status = effect.status_after is not GameStatus.PLAYING
    terminal_glyphs = {CellState.MINE: records.TerminalPresentation.MINE,
                       CellState.EXPLODED: records.TerminalPresentation.EXPLODED_MINE,
                       CellState.FALSE_FLAG: records.TerminalPresentation.WRONG_FLAG}
    for y, (before_row, after_row) in enumerate(zip(effect.before_observation, effect.after_observation.rows)):
        for x, (before, after) in enumerate(zip(before_row, after_row)):
            cell = (x, y)
            if terminal_status and (after in terminal_glyphs or after == CellState.FLAGGED):
                presentation = terminal_glyphs.get(after, records.TerminalPresentation.CORRECT_FLAG)
                terminal.append(records.TerminalCellChange(cell, presentation))
                # A last physical FLAG is still a public action; auto-flags are not.
                if before == CellState.HIDDEN and after == CellState.FLAGGED and effect.move.action is Action.FLAG and cell == (effect.move.x, effect.move.y):
                    public.append(records.PublicCellChange(cell, "HIDDEN", "FLAGGED"))
            elif before != after:
                public.append(records.PublicCellChange(cell, _public_state(before), _public_state(after)))
    public_record = records.PublicEffectRecord(effect.input_index, tuple(public),
                                                records.Status.PLAYING, _status(effect.status_after))
    terminal_record = (records.TerminalEffectRecord(effect.input_index, tuple(terminal), _status(effect.status_after))
                       if terminal_status else None)
    return public_record, terminal_record


def _neighbors(cell, rows):
    x, y = cell
    return {(nx, ny) for ny in range(max(0, y - 1), min(len(rows), y + 2))
            for nx in range(max(0, x - 1), min(len(rows[0]), x + 2)) if (nx, ny) != cell}


def _replay_public_projection(projection):
    """Check owned public rows and G5 witnesses without any terminal disclosure."""
    board = projection.arm.board
    state = [["HIDDEN"] * board.width for _ in range(board.height)]
    active, expected = {}, {}
    provenance = {item.flag_ordinal: item for item in projection.flag_provenance}
    for physical, effect in zip(projection.physical_inputs, projection.public_effects):
        for change in effect.changes:
            x, y = change.cell
            _need(state[y][x] == change.before, "Published public changes do not replay.")
            if change.before == "FLAGGED" or change.after == "FLAGGED":
                _need(physical.action is records.Action.FLAG and physical.target == change.cell,
                      "Public flag transition lacks its physical FLAG.")
        if physical.action is records.Action.CHORD:
            x, y = physical.target
            _need(state[y][x] in tuple("CLUE_" + str(n) for n in range(1, 9)),
                  "Published CHORD lacks a positive clue.")
            adjacent = _neighbors(physical.target, state)
            flags = _cells(cell for cell in adjacent if state[cell[1]][cell[0]] == "FLAGGED")
            opened = _cells(change.cell for change in effect.changes
                            if change.cell in adjacent and change.before == "HIDDEN"
                            and change.after.startswith("CLUE_"))
            if opened:
                _need(len(flags) == int(state[y][x][5:]), "Productive CHORD has an unsatisfied clue.")
                witness = records.ProductiveChordWitness(physical.action_ordinal, physical.target, flags, opened)
                for cell in flags:
                    if cell in active:
                        expected.setdefault(active[cell], witness)
        if physical.action is records.Action.FLAG:
            _need(len(effect.changes) == 1 and effect.changes[0].cell == physical.target
                  and (effect.changes[0].before, effect.changes[0].after)
                  in (("HIDDEN", "FLAGGED"), ("FLAGGED", "HIDDEN")),
                  "Published FLAG must toggle exactly its physical target.")
            if effect.changes[0].after == "FLAGGED" and physical.action_ordinal in provenance:
                active[physical.target] = physical.action_ordinal
            else:
                active.pop(physical.target, None)
        for change in effect.changes:
            state[change.cell[1]][change.cell[0]] = change.after
    for ordinal, item in provenance.items():
        _need(item.witness == expected.get(ordinal), "Published FLAG witness differs from public replay.")


@_guard
def project_control_flags(traces, effects):
    """Bind each classified physical FLAG occurrence to its first public witness.

    Arm-local selected-plan references name the exact archived action boundary.
    An unflag removes the old occurrence; a later reflag is a distinct input.
    """
    _need(type(traces) is tuple and type(effects) is tuple and len(traces) == len(effects),
          "CONTROL provenance requires aligned immutable traces/effects.")
    provenance, active = [], {}
    complete = True
    for ordinal, (trace, effect) in enumerate(zip(traces, effects)):
        _need(type(trace) is Stage3ActionTrace and type(trace.move.action) is Action,
              "Malformed CONTROL trace in FLAG provenance.")
        target = (trace.move.x, trace.move.y)
        slot = None
        if trace.move.action is Action.FLAG:
            decision = trace.decision
            _need(type(decision) is Stage3Decision and decision.move == trace.move,
                  "CONTROL FLAG has no classified current decision.")
            plan = decision.plan
            if plan is None:
                category = records.FlagCategory.CONTROL_FALLBACK_FLAG
                plan_ref = terminal_action = terminal_target = None
            else:
                _need(type(plan) is RevealPlan and type(plan.actions) is tuple and bool(plan.actions)
                      and plan.actions[0] == trace.move, "FLAG selected-plan binding differs.")
                terminal = plan.actions[-1]
                _need(type(terminal.action) is Action and terminal.action in (Action.OPEN, Action.CHORD),
                      "Unknown reachable CONTROL FLAG category.")
                category = (records.FlagCategory.CONTROL_SETUP_CHORD_FLAG if terminal.action is Action.CHORD
                            else records.FlagCategory.CONTROL_FLAG_TO_OPEN_SETUP)
                plan_ref = "control/action/" + str(ordinal) + "/selected-plan"
                terminal_action = records.Action[terminal.action.name]
                terminal_target = (terminal.x, terminal.y)
            slot = len(provenance)
            provenance.append(records.ControlFlagProvenanceRecord(
                ordinal, target, category, plan_ref, terminal_action, terminal_target, None))
        if effect is None:
            complete = False
            # Unknown intervening effects cannot establish that a FLAG remained.
            active.clear()
            continue
        _need(type(effect) is evidence.PublicEffectRecord, "Malformed CONTROL effect.")
        effect = replace(effect)
        _need(effect.input_index == ordinal and effect.move.action is trace.move.action
              and (effect.move.x, effect.move.y) == target and effect.status_after is trace.status_after,
              "CONTROL FLAG/effect binding differs.")
        before, after = effect.before_observation, effect.after_observation.rows
        for cell in tuple(active):
            if before[cell[1]][cell[0]] != CellState.FLAGGED:
                del active[cell]
        if trace.move.action is Action.CHORD:
            adjacent = _neighbors(target, before)
            _need(1 <= before[target[1]][target[0]] <= 8, "CHORD target is not a positive public clue.")
            flags = _cells(cell for cell in adjacent if before[cell[1]][cell[0]] == CellState.FLAGGED)
            opened = _cells(cell for cell in adjacent
                            if before[cell[1]][cell[0]] == CellState.HIDDEN and 0 <= after[cell[1]][cell[0]] <= 8)
            if opened:
                _need(len(flags) == before[target[1]][target[0]],
                      "Productive CHORD has an unsatisfied public clue.")
                witness = records.ProductiveChordWitness(ordinal, target, flags, opened)
                for cell in flags:
                    if cell in active:
                        index = active[cell]
                        if provenance[index].witness is None:
                            provenance[index] = replace(provenance[index], witness=witness)
        for cell in tuple(active):
            if after[cell[1]][cell[0]] != CellState.FLAGGED:
                del active[cell]
        if slot is not None:
            old, new = before[target[1]][target[0]], after[target[1]][target[0]]
            _need((old, new) in ((CellState.HIDDEN, CellState.FLAGGED),
                                 (CellState.FLAGGED, CellState.HIDDEN)), "FLAG did not toggle its public target.")
            if new == CellState.FLAGGED:
                active[target] = slot
            else:
                active.pop(target, None)
    return tuple(provenance), complete


@_guard
def summarize_g5(provenance):
    _need(type(provenance) is tuple, "G5 provenance must be an owned tuple.")
    setup = fallback = flag_to_open = 0
    for item in provenance:
        _record(item, records.ControlFlagProvenanceRecord)
        if item.category is records.FlagCategory.CONTROL_SETUP_CHORD_FLAG:
            setup += 1
        elif item.witness is not None:
            if item.category is records.FlagCategory.CONTROL_FALLBACK_FLAG:
                fallback += 1
            else:
                flag_to_open += 1
    return records.G5ExposureSummary(setup, fallback, flag_to_open)


@_guard
def certificate_reference(certificate):
    """Existing single-certificate codec only; no proof admission or truth call."""
    _need(type(certificate) in (capability.LocalMineCertificate, capability.ExactGlobalMineCertificate),
          "Missing or unsupported exact public certificate reference.")
    checked = replace(certificate)  # public schema validation, never certificate verification
    _need(checked == certificate, "Certificate is not in its exact canonical public form.")
    digest = content_digest(checked)
    _need(type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
          "Existing certificate codec did not supply an exact digest.")
    return "sha256:" + digest, digest


@_guard
def project_acquisitions(traces):
    _need(type(traces) is tuple, "K acquisition traces must be an exact tuple.")
    projected, previous_m, previous_index = [], None, -1
    for trace in traces:
        _need(type(trace) is runner.KActionTrace and type(trace.input_index) is int
              and trace.input_index > previous_index, "Malformed/out-of-order acquisition boundary.")
        previous_index = trace.input_index
        _need(type(trace.M_before) is frozenset and type(trace.preinput_M) is frozenset
              and trace.M_before <= trace.preinput_M, "K acquisition M snapshots regress.")
        _need(previous_m is None or trace.M_before == previous_m, "K retained M continuity differs.")
        previous_m = trace.preinput_M
        added = trace.preinput_M - trace.M_before
        if trace.input_index == 0:
            _need(not added and not trace.M_before and trace.selection is None, "Initial OPEN cannot acquire M.")
            continue
        if trace.selection is None:
            _need(not added, "Missing certificate references for acquired logical mines.")
            continue
        _need(type(trace.selection) is policy.PolicySelection
              and type(trace.selection.evidence) is capability.DecisionAnalysis,
              "Missing K decision/certificate evidence.")
        decision = trace.selection.evidence
        _need(type(decision.local) is capability.LocalAnalysis
              and decision.local.before.M == trace.M_before and decision.after.M == trace.preinput_M,
              "Certificate acquisition decision boundary differs.")
        seen = set()
        for certificates, cls, source, retained in (
                (decision.local.certificates, capability.LocalMineCertificate,
                 records.AcquisitionSource.LOCAL, trace.M_before),
                (decision.exact_certificates, capability.ExactGlobalMineCertificate,
                 records.AcquisitionSource.EXACT_GLOBAL, decision.local.after.M)):
            _need(type(certificates) is tuple, "Missing immutable acquisition certificates.")
            for certificate in certificates:
                _need(type(certificate) is cls, "Certificate source/type mismatch.")
                reference, digest = certificate_reference(certificate)
                _need(certificate.target in added and certificate.target not in seen
                      and certificate.observation == decision.observation
                      and certificate.num_mines == decision.num_mines
                      and certificate.retained_mines == retained,
                      "Certificate reference is not bound to this acquisition.")
                seen.add(certificate.target)
                projected.append(records.AcquisitionRecord(trace.input_index, trace.input_index - 1,
                                                            certificate.target, source, reference, digest))
        _need(seen == added, "Acquisition without its stable exact certificate reference.")
    return tuple(projected)


def _decision_plan(plan):
    if plan is None:
        return (), None, None
    _need(type(plan) is RevealPlan and type(plan.actions) is tuple and bool(plan.actions),
          "Malformed selected reveal plan.")
    _integer(plan.latency_us, 1)
    _integer(plan.reveals, 1)
    actions = []
    for move in plan.actions:
        _need(type(move) is runner.SimpleMove and type(move.action) is Action,
              "Malformed selected plan action.")
        actions.append((records.Action[move.action.name], (move.x, move.y)))
    return tuple(actions), plan.latency_us, plan.reveals


@_guard
def project_control_decisions(traces, arm):
    """Retain the actual V1 semantic kind and selected plan for every input."""
    _arm(arm, records.Arm.CONTROL)
    _need(type(traces) is tuple and bool(traces), "Missing CONTROL decisions.")
    result = []
    for ordinal, trace in enumerate(traces):
        _need(type(trace) is Stage3ActionTrace and type(trace.move) is runner.SimpleMove
              and type(trace.move.action) is Action, "Malformed CONTROL decision input.")
        if ordinal == 0:
            _need(trace.decision is None, "Initial CONTROL input cannot have a selected decision.")
            category, semantic, plan = "CONTROL_INITIAL_OPEN", "INITIAL", None
        else:
            _need(type(trace.decision) is Stage3Decision and trace.decision.move == trace.move,
                  "Every post-initial CONTROL input requires its matching decision.")
            checked = evidence.project_v1_decision(trace.decision)
            category = semantic = checked.evidence.kind.value
            plan = trace.decision.plan
        actions, model_us, reveals = _decision_plan(plan)
        result.append(records.ActionDecisionRecord(
            arm, ordinal, category, semantic, records.Action[trace.move.action.name],
            (trace.move.x, trace.move.y), actions, model_us, reveals, (), (), (), ()))
    return tuple(result)


@_guard
def project_k_decisions(traces, arm):
    """Detach only the uniquely selected K plan, candidate cells and M snapshots."""
    _arm(arm, records.Arm.K_P0)
    _need(type(traces) is tuple and bool(traces), "Missing K decisions.")
    result, previous_m = [], frozenset()
    for ordinal, trace in enumerate(traces):
        _need(type(trace) is runner.KActionTrace and type(trace.input_index) is int
              and trace.input_index == ordinal and type(trace.move) is runner.SimpleMove
              and type(trace.move.action) is Action, "Malformed K decision input.")
        _need(type(trace.M_before) is frozenset and type(trace.preinput_M) is frozenset
              and trace.M_before == previous_m and trace.M_before <= trace.preinput_M,
              "K decision M snapshots regress or lose continuity.")
        previous_m = trace.preinput_M
        setup = reveal = ()
        if ordinal == 0:
            _need(trace.selection is None and trace.category == "POLICY_INITIAL_OPEN"
                  and not trace.M_before and not trace.preinput_M, "Malformed initial K decision.")
            semantic, plan = "INITIAL", None
        else:
            selection = trace.selection
            _need(type(selection) is policy.PolicySelection
                  and type(selection.evidence) is capability.DecisionAnalysis
                  and selection.move == trace.move and selection.category == trace.category
                  and selection.cursor == trace.cursor_before and selection.failure_code is None,
                  "Every selected K input requires its matching selection.")
            decision = selection.evidence
            _need(type(decision.local) is capability.LocalAnalysis
                  and type(decision.local.before) is capability.Accounting
                  and type(decision.after) is capability.Accounting
                  and decision.local.before.M == trace.M_before and decision.after.M == trace.preinput_M,
                  "K selected decision/acquisition M snapshots differ.")
            semantic, plan = decision.continuation, selection.plan
            _need(type(selection.candidates) is tuple and type(selection.survivors) is tuple
                  and all(type(candidate) is policy.KCandidate
                          for candidate in selection.candidates + selection.survivors),
                  "Missing selected candidate evidence.")
            if plan is not None:
                matches = tuple(candidate for candidate in selection.survivors
                                if candidate.plan == plan and candidate.category == selection.category)
                _need(len(matches) == 1 and matches[0] in selection.candidates,
                      "Selected K plan needs exactly one matching survivor.")
                selected = matches[0]
                _need(type(selected.setup_cells) is frozenset and type(selected.reveal_cells) is frozenset,
                      "Selected candidate cells are not immutable sets.")
                setup, reveal = _cells(selected.setup_cells), _cells(selected.reveal_cells)
            else:
                _need(selection.candidates == selection.survivors == (),
                      "Planless K guess cannot retain selected candidates.")
        actions, model_us, reveals = _decision_plan(plan)
        projected = records.ActionDecisionRecord(
            arm, ordinal, trace.category, semantic, records.Action[trace.move.action.name],
            (trace.move.x, trace.move.y), actions, model_us, reveals, setup, reveal,
            _cells(trace.M_before), _cells(trace.preinput_M))
        _validate_selected_category(projected)
        result.append(projected)
    return tuple(result)


def _validate_selected_category(decision):
    """Validate retained category/plan bindings, not inference or proof truth."""
    if decision.action_ordinal == 0:
        return  # The closed I1 initial record owns these invariants.
    if decision.arm.arm is records.Arm.CONTROL:
        _need(decision.category == decision.semantic_kind
              and decision.semantic_kind in tuple(kind.value for kind in evidence.DecisionKind),
              "CONTROL category must retain the frozen V1 semantic kind.")
        _need(not decision.setup_cells and not decision.reveal_cells,
              "V1 does not own K candidate cell projections.")
        return
    if decision.category == "EXACT_MINIMUM_RISK_GUESS":
        _need(decision.semantic_kind == "EXACT_GUESS" and decision.action is records.Action.OPEN
              and not decision.plan_actions, "K guess category/continuation/plan differs.")
        return
    _need(decision.semantic_kind in ("LOCAL_SAFE", "EXACT_SAFE") and bool(decision.plan_actions),
          "K certainty selection requires a current selected reveal plan.")
    _need(decision.plan_safe_reveals == len(decision.reveal_cells) > 0
          and not set(decision.reveal_cells) & set(decision.logical_mines_after),
          "K selected reveal count/cells differ.")
    if decision.category == "DIRECT_SAFE_OPEN":
        _need(decision.action is records.Action.OPEN and len(decision.plan_actions) == 1
              and not decision.setup_cells and decision.reveal_cells == (decision.target,),
              "DIRECT_SAFE_OPEN selected plan differs.")
    elif decision.category == "DIRECT_CHORD":
        _need(decision.action is records.Action.CHORD and len(decision.plan_actions) == 1
              and not decision.setup_cells, "DIRECT_CHORD selected plan differs.")
    elif decision.category == "SETUP_CHORD":
        prefix, terminal = decision.plan_actions[:-1], decision.plan_actions[-1]
        _need(decision.action is records.Action.FLAG and bool(prefix)
              and terminal[0] is records.Action.CHORD
              and all(action is records.Action.FLAG for action, _ in prefix)
              and len(prefix) == len(decision.setup_cells)
              and _cells(cell for _, cell in prefix) == decision.setup_cells
              and set(decision.setup_cells) <= set(decision.logical_mines_after),
              "SETUP_CHORD selected plan/setup cells differ.")
    else:
        raise GameProjectionError("Unknown K selected category.")


def _validate_decision_bindings(arm, physical_inputs, decisions, acquisitions):
    """Validate the durable action/decision/acquisition join; return recovered M."""
    _record(arm, records.ArmIdentity)
    _arm(arm, arm.arm)
    _need(arm.arm in (records.Arm.CONTROL, records.Arm.K_P0), "Unsupported durable arm.")
    for stream, cls in ((physical_inputs, records.PhysicalInputRecord),
                        (decisions, records.ActionDecisionRecord), (acquisitions, records.AcquisitionRecord)):
        _need(type(stream) is tuple, "Durable streams must be exact tuples.")
        for item in stream:
            _record(item, cls)
    _need(bool(physical_inputs) and len(decisions) == len(physical_inputs),
          "Exactly one durable decision is required per physical input.")
    by_ordinal, acquired, last_ordinal = {}, set(), -1
    for item in acquisitions:
        _need(0 < item.action_ordinal < len(decisions) and item.action_ordinal >= last_ordinal
              and item.decision_ordinal == item.action_ordinal - 1 and item.cell not in acquired,
              "Acquisition chronology or unique cell ownership differs.")
        _inside(item.cell, arm.board)
        _need(item.certificate_ref == "sha256:" + item.certificate_sha256,
              "Acquisition reference/digest differ.")
        by_ordinal.setdefault(item.action_ordinal, set()).add(item.cell)
        acquired.add(item.cell)
        last_ordinal = item.action_ordinal
    if arm.arm is records.Arm.CONTROL:
        _need(not acquisitions, "CONTROL cannot acquire logical M.")
    previous_m, cursor, total = (), arm.board.first_click, 0
    for ordinal, (physical, decision) in enumerate(zip(physical_inputs, decisions)):
        _need(physical.action_ordinal == decision.action_ordinal == ordinal and decision.arm == arm
              and (physical.action, physical.target) == (decision.action, decision.target),
              "Durable decision ordinal/arm/action does not bind its physical input.")
        _inside(physical.target, arm.board)
        _inside(physical.cursor_before, arm.board)
        _need(physical.cursor_before == cursor and physical.input_us > 0, "Durable physical cursor/cost differs.")
        if ordinal:
            _need(physical_inputs[ordinal - 1].after_status is records.Status.PLAYING,
                  "Durable stream contains postterminal input.")
        total += physical.input_us
        _need(physical.cumulative_us == total, "Durable cumulative cost differs.")
        cursor = physical.target
        _validate_selected_category(decision)
        _need(decision.logical_mines_before == previous_m,
              "Consecutive durable M snapshots do not join.")
        added = set(decision.logical_mines_after) - set(decision.logical_mines_before)
        _need(added == by_ordinal.get(ordinal, set()), "Acquisitions do not match this decision's M transition.")
        previous_m = decision.logical_mines_after
        _need(len(previous_m) <= arm.board.mines, "Durable M exceeds public mine total.")
    _need(set(previous_m) == acquired, "Final durable M differs from unique acquisition cells.")
    return previous_m


@_guard
def validate_durable_decisions(physical_inputs, public_effects, decisions, acquisitions):
    """Rebind only decoded durable records; no runner objects or truth admission.

    Complete public effects are required by this replay helper. Ordinary I4
    projections still retain explicitly incomplete effect/P-3 evidence.
    """
    _need(type(decisions) is tuple and bool(decisions), "Missing durable decisions.")
    _record(decisions[0], records.ActionDecisionRecord)
    arm = decisions[0].arm
    final_m = _validate_decision_bindings(arm, physical_inputs, decisions, acquisitions)
    _need(type(public_effects) is tuple and len(public_effects) == len(physical_inputs),
          "Complete public effects required for durable replay.")
    state = [["HIDDEN"] * arm.board.width for _ in range(arm.board.height)]
    for ordinal, (physical, decision, effect) in enumerate(zip(physical_inputs, decisions, public_effects)):
        _record(effect, records.PublicEffectRecord)
        _need(effect.action_ordinal == ordinal and effect.after_status is physical.after_status,
              "Durable public effect/action status differs.")
        if arm.arm is records.Arm.K_P0:
            fixed = set(decision.logical_mines_after)
            flags = {(x, y) for y, row in enumerate(state) for x, value in enumerate(row) if value == "FLAGGED"}
            _need(flags <= fixed and all(state[y][x] in ("HIDDEN", "FLAGGED") for x, y in fixed),
                  "Durable K M conflicts with public cells.")
            if decision.plan_actions:
                terminal_action, terminal_cell = decision.plan_actions[-1]
                if terminal_action is records.Action.CHORD:
                    x, y = terminal_cell
                    _need(state[y][x] in tuple("CLUE_" + str(n) for n in range(1, 9)),
                          "Selected CHORD lacks its current positive clue.")
                    adjacent = _neighbors(terminal_cell, state)
                    hidden = {cell for cell in adjacent if state[cell[1]][cell[0]] == "HIDDEN"}
                    setup = set(decision.setup_cells)
                    _need(setup <= hidden and len(flags & adjacent) + len(setup) == int(state[y][x][5:])
                          and set(decision.reveal_cells) == hidden - setup,
                          "Selected CHORD setup/reveal facts differ from public state.")
                else:
                    _need(terminal_action is records.Action.OPEN and state[terminal_cell[1]][terminal_cell[0]] == "HIDDEN",
                          "Selected OPEN target is not publicly HIDDEN.")
        x, y = physical.target
        if physical.action is records.Action.OPEN:
            _need(state[y][x] == "HIDDEN", "Executed OPEN target is not HIDDEN.")
            if arm.arm is records.Arm.K_P0:
                _need(physical.target not in fixed, "Executed K OPEN targets retained M.")
        elif physical.action is records.Action.FLAG and arm.arm is records.Arm.K_P0:
            _need(state[y][x] == "HIDDEN" and physical.target in fixed,
                  "Executed K setup FLAG must materialize a HIDDEN retained mine.")
        elif physical.action is records.Action.CHORD:
            _need(state[y][x] in tuple("CLUE_" + str(n) for n in range(1, 9)),
                  "Executed CHORD target is not a positive clue.")
        for change in effect.changes:
            _inside(change.cell, arm.board)
            cx, cy = change.cell
            _need(state[cy][cx] == change.before, "Durable public effects do not replay.")
            if change.before == "FLAGGED" or change.after == "FLAGGED":
                _need(physical.action is records.Action.FLAG and physical.target == change.cell,
                      "Durable public flag transition lacks its physical input.")
            state[cy][cx] = change.after
        if physical.action is records.Action.FLAG:
            _need(len(effect.changes) == 1 and effect.changes[0].cell == physical.target
                  and (effect.changes[0].before, effect.changes[0].after)
                  in (("HIDDEN", "FLAGGED"), ("FLAGGED", "HIDDEN")), "Durable FLAG must toggle its target.")
    return final_m


@dataclass(frozen=True, slots=True)
class KSetupFacts:
    """Sequence diagnostics only; no causal or saved-FLAG interpretation."""
    executed_setup_flags: int
    selected_setup_ordinals: tuple
    realized_setup_ordinals: tuple
    abandoned_setup_ordinals: tuple
    terminated_setup_ordinals: tuple
    incomplete_setup_ordinals: tuple

    def __post_init__(self):
        _integer(self.executed_setup_flags)
        groups = (self.selected_setup_ordinals, self.realized_setup_ordinals, self.abandoned_setup_ordinals,
                  self.terminated_setup_ordinals, self.incomplete_setup_ordinals)
        for group in groups:
            _need(type(group) is tuple, "Setup diagnostics must be immutable tuples.")
            for ordinal in group:
                _integer(ordinal, 1)
            _need(group == tuple(sorted(set(group))), "Setup diagnostic ordinals repeat or are unordered.")
        classified = self.realized_setup_ordinals + self.abandoned_setup_ordinals + self.terminated_setup_ordinals + self.incomplete_setup_ordinals
        _need(len(classified) == len(set(classified)) and tuple(sorted(classified)) == self.selected_setup_ordinals
              and self.executed_setup_flags == len(self.selected_setup_ordinals), "Setup diagnostic partition differs.")


@_guard
def derive_k_setup_facts_from_records(physical_inputs, decisions, acquisitions):
    """Compare each committed setup's full plan with the contiguous actual suffix."""
    _need(type(decisions) is tuple and bool(decisions), "Missing durable K decisions.")
    _record(decisions[0], records.ActionDecisionRecord)
    arm = decisions[0].arm
    _need(arm.arm is records.Arm.K_P0, "K setup facts require K-P0 records.")
    _validate_decision_bindings(arm, physical_inputs, decisions, acquisitions)
    selected, realized, abandoned, terminated, incomplete = [], [], [], [], []
    for decision in decisions:
        if decision.category != "SETUP_CHORD":
            continue
        start, plan = decision.action_ordinal, decision.plan_actions
        selected.append(start)
        for offset, expected in enumerate(plan):
            index = start + offset
            if index == len(physical_inputs):
                (incomplete if physical_inputs[-1].after_status is records.Status.PLAYING else terminated).append(start)
                break
            actual = physical_inputs[index]
            if (actual.action, actual.target) != expected:
                abandoned.append(start)
                break
        else:
            realized.append(start)
    return KSetupFacts(len(selected), tuple(selected), tuple(realized), tuple(abandoned), tuple(terminated), tuple(incomplete))


@_guard
def derive_k_setup_facts(projection):
    _record(projection, GameProjection)
    return derive_k_setup_facts_from_records(projection.physical_inputs, projection.decisions, projection.acquisitions)


def _partition(observation):
    clues = tuple(((x, y), value) for y, row in enumerate(observation) for x, value in enumerate(row)
                  if 0 <= value <= 8)
    flags = frozenset((x, y) for y, row in enumerate(observation) for x, value in enumerate(row)
                      if value == CellState.FLAGGED)
    hidden = frozenset((x, y) for y, row in enumerate(observation) for x, value in enumerate(row)
                       if value == CellState.HIDDEN)
    return clues, flags, hidden


def _control_checkpoints(traces, effects, arm, outcome):
    checkpoints, missing = [], []
    for index, (trace, effect) in enumerate(zip(traces, effects)):
        if index == 0:
            _need(trace.decision is None, "Initial CONTROL input cannot carry a decision.")
            continue
        if trace.decision is None or effect is None:
            missing.append("MISSING_CONTROL_P3_BOUNDARY:" + str(index))
            continue
        decision = evidence.project_v1_decision(trace.decision)
        _need(decision.move == effect.move, "CONTROL selected input/effect differ.")
        supplied = decision.evidence
        counts = supplied.probability_result
        if supplied.kind in (evidence.DecisionKind.GLOBAL_CERTAINTY, evidence.DecisionKind.PROBABILITY_GUESS) and counts is None:
            missing.append("MISSING_CONTROL_EXACT_EVIDENCE:" + str(index))
            continue
        # Reuse only the frozen public execution predicate, never inference or
        # certificate admission. A relabeled uncertain OPEN must not disappear.
        runner._validate_execution(effect.before_observation, trace.move, trace.decision)
        if supplied.kind is not evidence.DecisionKind.PROBABILITY_GUESS:
            if counts is not None and trace.move.action is Action.OPEN:
                chosen = next((p for p in counts.probabilities if p.coordinate == (trace.move.x, trace.move.y)), None)
                _need(chosen is not None and chosen.mine_worlds in (0, counts.total_worlds),
                      "Uncertain CONTROL OPEN was mislabeled as certainty.")
            continue
        _need(decision.plan is None and decision.move == supplied.move and trace.move.action is Action.OPEN
              and not supplied.deterministic_result.safe_cells and not supplied.deterministic_result.mine_cells,
              "CONTROL guess lacks certainty exhaustion/selected target binding.")
        clues, flags, hidden = _partition(effect.before_observation)
        numbers = tuple((item.coordinate, item.mine_worlds) for item in counts.probabilities)
        probabilities = tuple((cell, Fraction(count, counts.total_worlds)) for cell, count in numbers)
        risk = min(probability for _, probability in probabilities)
        checkpoints.append(records.GuessCheckpointRecord(
            arm, len(checkpoints) + 1, clues, _cells(flags), _cells(flags), _cells(hidden),
            arm.board.mines - len(flags), counts.total_worlds, numbers, probabilities, risk,
            tuple(cell for cell, probability in probabilities if probability == risk),
            (trace.move.x, trace.move.y), outcome))
    return tuple(checkpoints), tuple(missing)


def _kp0_checkpoints(traces, effects, arm, outcome):
    checkpoints, missing = [], []
    for index, (trace, effect) in enumerate(zip(traces, effects)):
        if index == 0:
            _need(trace.selection is None and trace.category == "POLICY_INITIAL_OPEN"
                  and not trace.M_before and not trace.preinput_M, "Initial K input cannot carry inference.")
            continue
        if trace.selection is None or effect is None:
            missing.append("MISSING_K_P3_BOUNDARY:" + str(index))
            continue
        selection = trace.selection
        _need(type(selection) is policy.PolicySelection and type(selection.evidence) is capability.DecisionAnalysis
              and selection.category == trace.category and selection.move == trace.move,
              "Missing/mislabeled K-P0 selection.")
        decision = selection.evidence
        clues, flags, hidden = _partition(effect.before_observation)
        _need(decision.observation == effect.before_observation and decision.num_mines == arm.board.mines
              and type(decision.after) is capability.Accounting and decision.after.M == trace.preinput_M
              and decision.after.P == flags, "K decision/public checkpoint binding differs.")
        _need((trace.category == "EXACT_MINIMUM_RISK_GUESS") == (decision.continuation == "EXACT_GUESS"),
              "K uncertain continuation was relabeled.")
        _need(decision.continuation in ("LOCAL_SAFE", "EXACT_SAFE", "EXACT_GUESS"),
              "Unknown K continuation.")
        if decision.continuation != "LOCAL_SAFE" and (decision.phase_e is None or decision.phase_d is None):
            missing.append("MISSING_K_EXACT_EVIDENCE:" + str(index))
            continue
        runner.validate_k_p0_execution(
            effect.before_observation, trace.move, status=GameStatus.PLAYING, num_mines=arm.board.mines,
            cursor=trace.cursor_before, current_mines=trace.preinput_M, decision=decision, selection=selection)
        if trace.category != "EXACT_MINIMUM_RISK_GUESS":
            continue
        exact = decision.phase_e
        _need(type(exact) is capability.ExactAnalysis and type(decision.local) is capability.LocalAnalysis
              and decision.phase_e_status in ("REACHED_CHANGED", "REACHED_NO_CHANGE")
              and trace.move.action is Action.OPEN and selection.plan is None
              and not decision.selection_safe_cells and not decision.local.S_current
              and not exact.G0 and not exact.G1, "K guess lacks certainty-exhausted Phase E.")
        fixed, unresolved = flags | trace.preinput_M, hidden - trace.preinput_M
        budget = arm.board.mines - len(fixed)
        _need(decision.after.J == fixed and decision.after.U == unresolved and decision.after.b == budget
              and exact.unresolved_cells == tuple(cell for cell, _ in exact.mine_worlds)
              and decision.guess_target == (trace.move.x, trace.move.y), "K normalized guess premises differ.")
        probabilities = tuple((cell, Fraction(count, exact.total_worlds)) for cell, count in exact.mine_worlds)
        checkpoints.append(records.GuessCheckpointRecord(
            arm, len(checkpoints) + 1, clues, _cells(flags), _cells(fixed), _cells(unresolved), budget,
            exact.total_worlds, exact.mine_worlds, probabilities, exact.minimum_risk,
            _cells(exact.minimum_risk_cells), (trace.move.x, trace.move.y), outcome))
    return tuple(checkpoints), tuple(missing)


def _project_stream(raw, arm, table, effects, control_timings=()):
    """Reconcile captured inputs independently against authenticated Model C."""
    validate_timing_table(table)
    traces = raw.traces
    _need(type(traces) is tuple and bool(traces), "Missing immutable physical input stream.")
    _status(raw.status)
    is_control = arm.arm is records.Arm.CONTROL
    expected_trace = Stage3ActionTrace if is_control else runner.KActionTrace
    scope = (records.DecisionScope.CONTROL_PLAN_POSITION if is_control
             else records.DecisionScope.K_ANALYZE_DECISION_THROUGH_SELECT_POLICY)
    if is_control:
        _need(type(control_timings) is tuple and len(control_timings) <= len(traces),
              "Malformed CONTROL timing stream.")
    physical, public, terminal, spans, diagnostics = [], [], [], [], []
    total, cursor = 0, (0, 0)
    for index, (trace, effect) in enumerate(zip(traces, effects)):
        _need(type(trace) is expected_trace and type(trace.move) is runner.SimpleMove,
              "Unexpected physical trace/move type.")
        _need(type(trace.move.action) is Action, "Unknown physical action.")
        target = (trace.move.x, trace.move.y)
        _inside(target, arm.board)
        _inside(trace.cursor_before, arm.board)
        _need(trace.cursor_before == cursor, "Physical cursor chain differs.")
        _integer(trace.modeled_action_us, 1)
        _need(trace.modeled_action_us == action_cost(table, cursor, target), "Model C input cost differs.")
        if index == 0:
            _need(trace.move.action is Action.OPEN and target == arm.board.first_click,
                  "Canonical initial OPEN is missing.")
        else:
            _need(traces[index - 1].status_after is GameStatus.PLAYING, "Postterminal physical input.")
        total += trace.modeled_action_us
        physical.append(records.PhysicalInputRecord(index, records.Action[trace.move.action.name],
                                                    target, cursor, trace.modeled_action_us,
                                                    total, _status(trace.status_after)))
        if is_control:
            duration = trace.decision_compute_ns
            if duration is not None:
                _integer(duration)
            timing = control_timings[index] if index < len(control_timings) else None
            if timing is not None:
                _record(timing, evidence.DecisionTimings)
                _need(timing.v1_plan_position_ns == duration, "CONTROL planner timing bindings differ.")
        else:
            _integer(trace.input_index)
            _need(trace.input_index == index, "K input ordinals are not contiguous.")
            if trace.timings is None:
                duration = None
            else:
                _record(trace.timings, evidence.DecisionTimings)
                duration = trace.timings.k_analysis_planning_ns
            _need(trace.public_effect_status == ("CAPTURED" if trace.public_effect is not None else "NOT_EVALUATED"),
                  "K public capture status disagrees with its evidence.")
            if trace.public_effect is not None:
                _need(trace.public_effect.input_index == index, "K effect belongs to another input.")
        if index:
            spans.append(records.DecisionSpanRecord(index, scope, duration))
            if duration is None:
                diagnostics.append("MISSING_COMPARABLE_COMPUTE:" + str(index))
        else:
            _need(duration is None, "Initial OPEN has no planner decision span.")
        if effect is None:
            diagnostics.append("MISSING_PUBLIC_EFFECT:" + str(index))
        else:
            _need(effect.input_index == index and effect.move == evidence.MoveProjection(trace.move.action, *target)
                  and effect.cursor_before == cursor and effect.cursor_after == target
                  and effect.modeled_action_us == trace.modeled_action_us
                  and effect.status_after is trace.status_after, "Physical/public capture bindings differ.")
            before = effect.before_observation
            _need(len(before) == arm.board.height and all(len(row) == arm.board.width for row in before),
                  "Captured dimensions differ from supplied identity.")
            if index == 0:
                _need(all(value == CellState.HIDDEN for row in before for value in row),
                      "Initial public observation must be all HIDDEN.")
            elif effects[index - 1] is not None:
                _need(effects[index - 1].after_observation.rows == before,
                      "Adjacent captured public observations do not reconstruct.")
            if is_control:
                _need(trace.safe_cells_opened_delta == effect.safe_cells_opened_delta
                      and trace.explicit_flag_delta == effect.explicit_flag_delta,
                      "CONTROL public effect counters disagree.")
            projected, disclosure = _project_effect(effect)
            public.append(projected)
            if disclosure is not None:
                terminal.append(disclosure)
        cursor = target
    _need(raw.status is traces[-1].status_after and total == raw.total_modeled_us,
          "Final status or cumulative Model C differs from runner result.")
    if raw.status is GameStatus.PLAYING:
        diagnostics.append("MISSING_TERMINAL_INPUT")
    complete = all(effect is not None for effect in effects) and raw.status is not GameStatus.PLAYING
    compute = None if any(span.duration_ns is None for span in spans) else sum(span.duration_ns for span in spans)
    return dict(physical_inputs=tuple(physical), public_effects=tuple(public), terminal_effects=tuple(terminal),
                decision_spans=tuple(spans), total_model_us=total, comparable_compute_ns=compute,
                effect_evidence_complete=complete, diagnostics=tuple(diagnostics))


@_guard
def project_control(capture, arm, *, table):
    """Project supplied CONTROL capture; preserve absent evidence as incomplete."""
    _arm(arm, records.Arm.CONTROL)
    _need(type(capture) is runner.ControlCaptureResult and type(capture.control) is Stage3RunResult
          and capture.capture_method == "STATUS_GATED_ACTUAL_EXECUTION", "Expected existing CONTROL capture.")
    _need(type(capture.traces) is tuple, "Expected immutable CONTROL traces.")
    effects = _aligned_effects(capture.effects, len(capture.traces))
    stream = _project_stream(capture, arm, table, effects, capture.timings)
    decisions = project_control_decisions(capture.traces, arm)
    outcome = _outcome(capture.status)
    checkpoints, missing = _control_checkpoints(capture.traces, effects, arm, outcome)
    flags, g5_complete = project_control_flags(capture.traces, effects)
    stream["diagnostics"] += missing
    return GameProjection(arm=arm, outcome=outcome, guess_checkpoints=checkpoints, flag_provenance=flags,
                          acquisitions=(), decisions=decisions,
                          p3_evidence_complete=stream["effect_evidence_complete"] and not missing,
                          g5_evidence_complete=stream["effect_evidence_complete"] and g5_complete, **stream)


@_guard
def project_k_p0(result, arm, *, table):
    """Project supplied K-P0 capture directly, without whole-archive reconstruction."""
    _arm(arm, records.Arm.K_P0)
    _need(type(result) is runner.KRunResult and type(result.traces) is tuple,
          "Expected existing K-P0 result.")
    _need(all(type(trace) is runner.KActionTrace for trace in result.traces), "Malformed K trace.")
    effects = _aligned_effects(tuple(trace.public_effect for trace in result.traces), len(result.traces))
    stream = _project_stream(result, arm, table, effects)
    _need(type(result.final_M) is frozenset and result.final_M == result.traces[-1].preinput_M,
          "Final retained M differs from captured execution.")
    decisions = project_k_decisions(result.traces, arm)
    _need(frozenset(decisions[-1].logical_mines_after) == result.final_M,
          "Final durable decision M differs from captured final M.")
    outcome = _outcome(result.status)
    checkpoints, missing = _kp0_checkpoints(result.traces, effects, arm, outcome)
    acquisitions = project_acquisitions(result.traces)
    stream["diagnostics"] += missing
    return GameProjection(arm=arm, outcome=outcome, guess_checkpoints=checkpoints, flag_provenance=(),
                          acquisitions=acquisitions, decisions=decisions,
                          p3_evidence_complete=stream["effect_evidence_complete"] and not missing,
                          g5_evidence_complete=True, **stream)


def _execution_arm(engine, board, kind, run_id, unit_id, table):
    _record(board, records.BoardIdentity)
    arm = records.ArmIdentity(kind, board, run_id, unit_id)
    _arm(arm, kind)
    # Only public metadata is read. The supplied identity is never reconstructed
    # from the Engine's answer layout or benchmark generator.
    _need(type(engine.width) is int and type(engine.height) is int and type(engine.num_mines) is int
          and (engine.width, engine.height, engine.num_mines) == (board.width, board.height, board.mines),
          "Supplied board identity/public Engine metadata differ.")
    _need(engine.status is GameStatus.PLAYING, "Execution requires a fresh PLAYING Engine.")
    validate_timing_table(table)
    return arm


@_guard
def run_control(engine, board, *, run_id, unit_id, table):
    """Thin entry point: the frozen CONTROL runner owns all physical execution."""
    arm = _execution_arm(engine, board, records.Arm.CONTROL, run_id, unit_id, table)
    capture = runner.run_control_capture(engine, table=table)
    return project_control(capture, arm, table=table)


@_guard
def run_k_p0(engine, board, *, run_id, unit_id, table):
    """Thin entry point: request public capture from the existing K-P0 runner."""
    arm = _execution_arm(engine, board, records.Arm.K_P0, run_id, unit_id, table)
    result = runner.run_k_p0(engine, table=table, capture_effects=True)
    return project_k_p0(result, arm, table=table)


@_guard
def pair_projections(control, kp0):
    """Supply per-pair facts only; E2 gates and verdicts belong to later slices."""
    _record(control, GameProjection)
    _record(kp0, GameProjection)
    _need(control.arm.arm is records.Arm.CONTROL and kp0.arm.arm is records.Arm.K_P0
          and control.arm.board == kp0.arm.board and control.arm.run_id == kp0.arm.run_id,
          "Pair requires CONTROL/K-P0 for the same supplied board and run.")
    comparison = compare_p3(control.guess_checkpoints, kp0.guess_checkpoints,
                            control_complete=control.p3_evidence_complete,
                            kp0_complete=kp0.p3_evidence_complete)
    delta = kp0.total_model_us - control.total_model_us if control.outcome is kp0.outcome is records.Outcome.WIN else None
    diagnosis = comparison.reason + (";G5_EVIDENCE_INCOMPLETE" if not control.g5_evidence_complete else "")
    pair = records.PairComparisonRecord(control.arm.board, control.outcome, kp0.outcome, comparison.status,
                                        delta, summarize_g5(control.flag_provenance), diagnosis)
    return PairedGameProjection(control, kp0, pair, comparison)
