"""I5 answer-segregated adapter over the accepted private falsification primitive.

One completed raw K-P0 result is rebound to its supplied I4 projection before
private truth is consumed. The caller supplies one fixed answer explicitly; this
module never acquires an answer, executes a solver, or retains private findings
in its three detached I1 evaluator records. PASS means no counterexample in that
assertion category, not sound public provenance or an effectiveness verdict.
"""

from dataclasses import dataclass, field
import hashlib
import json
import struct

from core_engine import Action, CellState
from experiments import program_k_e2_game as game
from experiments import program_k_e2_records as records
from experiments import program_k_evaluator as evaluator


class E2EvaluatorError(ValueError):
    """Malformed or mismatched execution/answer evidence; never a research result."""


def _need(condition, reason):
    if not condition:
        raise E2EvaluatorError(reason)


def _ordered(cells):
    return tuple(sorted(cells, key=lambda cell: (cell[1], cell[0])))


def _layout_fingerprint(board, mines):
    """Exact accepted MSLAYOUT1 bytes, without importing a board generator.

    This only binds the explicit private layout to the public fingerprint. It
    mirrors benchmark_board.calculate_board_fingerprint's fixed byte format,
    not its generation API or seed selection. Callers validate every value first.
    """
    payload = (b"MSLAYOUT1\0" + struct.pack(">III", board.width, board.height, board.mines)
               + b"".join(struct.pack(">II", x, y) for x, y in _ordered(mines)))
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class PrivateFixedAnswer:
    """Evaluator-only explicit answer, with private coordinates suppressed in repr.

    This input is never an output record or a public proof premise. Board
    metadata, count and canonical fingerprint bind every supplied coordinate.
    """

    arm: records.ArmIdentity
    mines: frozenset[tuple[int, int]] = field(repr=False)

    def __post_init__(self):
        _need(type(self.arm) is records.ArmIdentity, "ANSWER_ARM_TYPE")
        try:
            records.ArmIdentity.__post_init__(self.arm)
        except (ValueError, TypeError, AttributeError):
            raise E2EvaluatorError("ANSWER_ARM_MALFORMED") from None
        board = self.arm.board
        _need(self.arm.arm is records.Arm.K_P0 and board.width <= 30 and board.height <= 16
              and board.first_click == (0, 0), "ANSWER_KP0_BOARD_BINDING")
        _need(type(self.mines) is frozenset, "ANSWER_REQUIRES_IMMUTABLE_COORDINATES")
        _need(all(type(cell) is tuple and len(cell) == 2
                  and all(type(v) is int for v in cell)
                  and 0 <= cell[0] < board.width and 0 <= cell[1] < board.height
                  for cell in self.mines), "ANSWER_COORDINATE_BOUNDS")
        _need(len(self.mines) == board.mines, "ANSWER_MINE_COUNT")
        _need(_layout_fingerprint(board, self.mines) == board.fingerprint,
              "ANSWER_FINGERPRINT_MISMATCH")


def _projection_digest(projection):
    """Explicit complete I4 record authority; no raw object graph serialization."""
    payload = (
        "PROGRAM_K_E2_EVALUATOR_ARCHIVE_V1", projection.outcome.value,
        projection.total_model_us, projection.comparable_compute_ns,
        projection.effect_evidence_complete, projection.p3_evidence_complete,
        projection.g5_evidence_complete, projection.diagnostics,
        tuple(tuple(records.encode(item).decode("utf-8") for item in stream)
              for stream in (projection.physical_inputs, projection.public_effects,
                             projection.terminal_effects, projection.decision_spans,
                             projection.guess_checkpoints, projection.flag_provenance,
                             projection.acquisitions, projection.decisions)),
    )
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True, allow_nan=False,
                                     separators=(",", ":")).encode("ascii")).hexdigest()


def _assertions(raw):
    """Exact assertion extraction precedent: harness.seal_execution_archive.

    Actual CHORD-opened cells include an exploded cell so a failed certainty
    claim cannot disappear. Terminal mine displays/automatic flags do not become
    assertions, and unexecuted planned suffixes are never inspected here.
    """
    assertions = []
    for trace in raw.traces:
        ordinal = trace.input_index
        assertions.append(evaluator.ArchivedAssertion("LOGICAL_M", ordinal, trace.preinput_M))
        target = (trace.move.x, trace.move.y)
        if trace.category in ("POLICY_INITIAL_OPEN", "EXACT_MINIMUM_RISK_GUESS"):
            assertions.append(evaluator.ArchivedAssertion(trace.category, ordinal, (target,)))
        elif trace.move.action is Action.OPEN:
            assertions.append(evaluator.ArchivedAssertion("CERTAINTY_OPEN", ordinal, (target,)))
        elif trace.move.action is Action.CHORD:
            effect = trace.public_effect
            opened = tuple((x, y) for y, row in enumerate(effect.before_observation)
                           for x, value in enumerate(row) if value == CellState.HIDDEN
                           and (0 <= effect.after_observation.rows[y][x] <= 8
                                or effect.after_observation.rows[y][x] == CellState.EXPLODED))
            assertions.append(evaluator.ArchivedAssertion("CERTAINTY_CHORD_OPENED", ordinal, opened))
    return tuple(assertions)


def _public_records(arm, finding):
    """Remove every private truth bit and private answer digest from the result."""
    output = []
    for category in records.AssertionCategory:
        items = tuple(item for item in finding.findings if item.assertion.assertion_type == category.value)
        targets = _ordered(frozenset(cell for item in items for cell in item.assertion.coordinates))
        if any(item.classification == "G1_FALSIFICATION" for item in items):
            status = records.EvaluationStatus.FAIL
            reason = "ASSERTION_FALSIFIED"
            detail = "The private comparison falsified an archived assertion."
        elif any(item.comparisons for item in items):
            status = records.EvaluationStatus.PASS
            reason = "NO_COUNTEREXAMPLE"
            detail = "No counterexample was found; this is not a public proof."
        else:
            status = records.EvaluationStatus.NOT_EVALUATED
            reason = "NO_ASSERTED_COORDINATES"
            detail = "This category has no applicable asserted coordinates."
        # Canonical roundtrip also detaches nested arm/board identities from all
        # input objects. Coordinates are the already-public assertions only.
        output.append(records.decode(records.encode(records.EvaluatorRecord(
            arm, category, targets, status, reason, detail))))
    return tuple(output)


def evaluate_k_p0(raw, projection, private_answer, *, raw_arm, table):
    """Evaluate this already-executed board once, returning all three categories.

    Missing/incomplete execution cannot produce PASS: the future coordinator owns
    its unit-level INCOMPLETE disposition. A falsified assertion returns FAIL;
    malformed binding raises E2EvaluatorError. No retained output contains private
    mine layout, comparison truth bits, evaluator diagnostics or answer digests.
    KRunResult has no intrinsic board identity: raw_arm is the caller's explicit
    execution provenance and must equal the projection identity. The comparison
    cannot independently authenticate a producer's provenance declaration.
    """
    try:
        _need(type(projection) is game.GameProjection, "PROJECTION_TYPE")
        game.GameProjection.__post_init__(projection)
        _need(projection.arm.arm is records.Arm.K_P0, "KP0_ARM_REQUIRED")
        _need(type(raw_arm) is records.ArmIdentity, "RAW_ARM_REQUIRED")
        records.ArmIdentity.__post_init__(raw_arm)
        _need(raw_arm == projection.arm, "RAW_ARM_IDENTITY_MISMATCH")
        rebound = game.project_k_p0(raw, projection.arm, table=table)
        _need(rebound == projection, "RAW_PROJECTION_MISMATCH")
        _need(projection.effect_evidence_complete
              and projection.outcome in (records.Outcome.WIN, records.Outcome.LOSS),
              "COMPLETE_EXECUTION_REQUIRED")
        _need(type(private_answer) is PrivateFixedAnswer, "EXPLICIT_PRIVATE_ANSWER_REQUIRED")
        PrivateFixedAnswer.__post_init__(private_answer)
        _need(private_answer.arm == projection.arm, "ANSWER_EXECUTION_IDENTITY_MISMATCH")
        board = projection.arm.board
        sealed = evaluator.SealedEvaluatorInput(
            projection.arm.unit_id, projection.arm.run_id, board.width, board.height,
            _assertions(raw), _projection_digest(projection))
        answer = evaluator.HiddenAnswer(
            sealed.case_id, sealed.run_id, board.width, board.height,
            private_answer.mines, sealed.archive_digest, board.mines)
        finding = evaluator.evaluate_falsification(sealed, answer)
        evaluator.verify_bound_finding(finding, sealed, answer)
        return _public_records(projection.arm, finding)
    except E2EvaluatorError:
        raise
    except (ValueError, TypeError, AttributeError, IndexError, KeyError, OverflowError):
        # Never interpolate private answer or primitive findings into errors.
        raise E2EvaluatorError("MALFORMED_EVALUATOR_EVIDENCE") from None
