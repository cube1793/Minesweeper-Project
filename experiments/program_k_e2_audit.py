"""I5 public qualification adapters over supplied, already-executed K evidence.

No execution, corpus selection, private answer, persistence or research verdict
belongs here. The caller binds raw provenance explicitly because KRunResult has
no board identity. Certificate verification retains the accepted primitive's
internal arithmetic checks; only the optional board maintenance pass is selected
by oracle_b_enabled.
"""

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json

from core_engine import CellState, GameStatus
from experiments import program_k_e2_records as records
from experiments import program_k_e2_game as game
from experiments import program_k_capability as capability
from experiments import program_k_harness as harness
from experiments import program_k_oracles as oracles


class E2AuditError(ValueError):
    """Malformed/badly bound evidence; never a scientific verdict."""


AuditStatus = records.AuditStatus
CertificateAuditRecord = records.CertificateAuditRecord
OracleBAuditRecord = records.OracleBAuditRecord


def _need(condition, detail):
    if not condition:
        raise E2AuditError(detail)


def _closed(value):
    if type(value) in (str, int, bool, type(None)):
        return
    _need(type(value) is tuple, "Audit semantic values must be detached closed tuples/scalars.")
    for child in value:
        _closed(child)


def _canonical(value):
    _closed(value)
    return json.dumps(value, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":")).encode("ascii")


def _digest(value):
    return sha256(_canonical(value)).hexdigest()


def _cells(value):
    return tuple(sorted(value, key=lambda cell: (cell[1], cell[0])))


def _items(**values):
    return tuple(values.items())


def _texts(value):
    _need(type(value) is tuple and all(type(s) is str and s for s in value),
          "Expected immutable nonempty reason strings.")


@dataclass(frozen=True, slots=True)
class KBoardPublicAudit:
    arm: records.ArmIdentity
    certificate_audits: tuple
    oracle_b_selected: bool
    oracle_b_audits: tuple
    status: AuditStatus
    incomplete_reasons: tuple
    failure_reasons: tuple

    def __post_init__(self):
        _need(type(self.arm) is records.ArmIdentity and self.arm.arm is records.Arm.K_P0,
              "Public audit requires a K-P0 arm.")
        records.ArmIdentity.__post_init__(self.arm)
        _need(type(self.oracle_b_selected) is bool, "Oracle selection must be explicit bool.")
        for items, cls in ((self.certificate_audits, CertificateAuditRecord),
                           (self.oracle_b_audits, OracleBAuditRecord)):
            _need(type(items) is tuple and all(type(item) is cls for item in items), "Invalid audit collection.")
            for item in items:
                cls.__post_init__(item)
        _need(self.oracle_b_selected or not self.oracle_b_audits, "Unselected board has maintenance audits.")
        _texts(self.incomplete_reasons)
        _texts(self.failure_reasons)
        children = self.certificate_audits + self.oracle_b_audits
        _need(bool(self.failure_reasons) == any(item.status is AuditStatus.FAIL for item in children),
              "Board failure reasons must retain every failed child status.")
        _need(not any(item.status is AuditStatus.INCOMPLETE for item in children) or self.incomplete_reasons,
              "Incomplete child audits cannot silently disappear.")
        expected = (AuditStatus.FAIL if self.failure_reasons else
                    AuditStatus.INCOMPLETE if self.incomplete_reasons else AuditStatus.PASS)
        _need(self.status is expected, "Board public audit status/reasons disagree.")


def _bind_raw(raw, projection, *, raw_arm, table):
    """Reproject supplied evidence, never execute; raw provenance is caller-owned."""
    try:
        _need(type(projection) is game.GameProjection and type(raw_arm) is records.ArmIdentity,
              "Expected I4 projection and explicit raw arm provenance.")
        game.GameProjection.__post_init__(projection)
        records.ArmIdentity.__post_init__(raw_arm)
        _need(raw_arm == projection.arm and raw_arm.arm is records.Arm.K_P0,
              "Raw/projection arm or board identity differs.")
        actual = game.project_k_p0(raw, raw_arm, table=table)
        _need(actual == projection, "Raw execution and supplied I4 projection differ.")
    except (ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
        raise E2AuditError(str(error)) from error


def _certificate_semantics(certificate):
    common = _items(observation=certificate.observation, num_mines=certificate.num_mines,
                    target=certificate.target, retained_mines=_cells(certificate.retained_mines),
                    status=certificate.status.name)
    if type(certificate) is oracles.LocalMineCertificate:
        return (("source", "LOCAL"),) + common + _items(clue=certificate.clue)
    _need(type(certificate) is oracles.ExactGlobalMineCertificate, "Unknown certificate class.")
    return (("source", "EXACT_GLOBAL"),) + common + _items(
        total_worlds=certificate.total_worlds, mine_worlds=certificate.mine_worlds,
        exact_reached=certificate.exact_reached)


def _verifier_facts(check, certificate, status):
    if check is None:
        _need(status != "PASS", "Passing verifier omitted its public check.")
        return ()
    _need(check.target == certificate.target, "Verifier check target differs.")
    if type(certificate) is oracles.LocalMineCertificate:
        _need(type(check) is oracles.LocalCertificateCheck, "Wrong local verifier check type.")
        _need(check.clue == certificate.clue
              and type(check.clue_value) is int
              and check.clue_value == certificate.observation[certificate.clue[1]][certificate.clue[0]]
              and type(check.residual) is int
              and all(type(cells) is frozenset for cells in
                      (check.physical_flags, check.logical_mines, check.unresolved))
              and type(check.antecedents) is tuple,
              "Local verifier facts differ from the certificate or immutable schema.")
        result = _items(target=check.target, clue=check.clue, clue_value=check.clue_value,
                        physical_flags=_cells(check.physical_flags), logical_mines=_cells(check.logical_mines),
                        unresolved=_cells(check.unresolved), residual=check.residual, antecedents=check.antecedents)
    else:
        _need(type(check) is oracles.ExactGlobalCertificateCheck, "Wrong exact verifier check type.")
        _need(type(check.total_worlds) is int and type(check.mine_worlds) is int
              and check.total_worlds == check.mine_worlds == certificate.total_worlds
              and type(check.antecedents) is tuple
              and type(check.oracle_a_variable_count) is int and type(check.oracle_a_envelope) is int
              and type(check.oracle_a_status) is str and type(check.arithmetic_evidence) is str
              and (check.oracle_a_reason is None or type(check.oracle_a_reason) is str),
              "Exact verifier facts differ from the certificate or immutable schema.")
        result = _items(target=check.target, total_worlds=check.total_worlds, mine_worlds=check.mine_worlds,
                        antecedents=check.antecedents, oracle_a_status=check.oracle_a_status,
                        oracle_a_variable_count=check.oracle_a_variable_count,
                        oracle_a_envelope=check.oracle_a_envelope, oracle_a_reason=check.oracle_a_reason,
                        arithmetic_evidence=check.arithmetic_evidence)
    _closed(result)
    return result


def _audit_certificate(certificate, acquisition, proofs, *, history_valid):
    reference, digest = game.certificate_reference(certificate)
    expected_source = (records.AcquisitionSource.LOCAL if type(certificate) is oracles.LocalMineCertificate
                       else records.AcquisitionSource.EXACT_GLOBAL)
    _need(acquisition.cell == certificate.target and acquisition.source is expected_source
          and (acquisition.certificate_ref, acquisition.certificate_sha256) == (reference, digest),
          "I4 certificate reference/source/target differs.")
    audit = harness.audit_acquisition(certificate, boundary=acquisition.action_ordinal,
                                      prior_certificates=proofs, external_flags=())
    _need(type(audit) is harness.AcquisitionAudit, "Public verifier returned the wrong class.")
    _need(audit.certificate == certificate and type(audit.boundary) is int
          and audit.boundary == acquisition.action_ordinal and type(audit.prior_certificates) is tuple
          and audit.prior_certificates == proofs and audit.external_flags == ()
          and type(audit.owned_M_before) is frozenset and type(audit.owned_M_after) is frozenset
          and audit.owned_M_before == certificate.retained_mines
          and audit.owned_M_after == certificate.retained_mines | {certificate.target},
          "Public verifier certificate/history/boundary/owned M binding differs.")
    _need(type(audit.status) is str and audit.status in ("PASS", "FAIL", "INCOMPLETE")
          and type(audit.detail) is str and bool(audit.detail), "Invalid public verifier status/detail.")
    status = AuditStatus[audit.status]
    detail = audit.detail
    if status is AuditStatus.PASS and not history_valid:
        status = AuditStatus.INCOMPLETE
        detail += " Prior public proof authority is broken; this check grants no authority."
    return CertificateAuditRecord(
        acquisition.action_ordinal, acquisition, _certificate_semantics(certificate),
        tuple(game.certificate_reference(proof)[1] for proof in proofs), status, audit.status, detail,
        _cells(audit.owned_M_before), _cells(audit.owned_M_after),
        _verifier_facts(audit.certificate_check, certificate, audit.status))


_EXACT_FIELDS = ("unresolved_cells", "frontier_cells", "unconstrained_cells", "total_worlds",
                 "mine_worlds", "G0", "G1", "minimum_risk", "minimum_risk_cells",
                 "shared_kernel_evidence", "kernel")


def _exact_snapshot(value, materialized_observation):
    _need(type(value) in (capability.ExactAnalysis, oracles.OracleBResult), "Missing exact semantic record.")
    _need(all(type(cells) is frozenset for cells in (value.G0, value.G1, value.minimum_risk_cells)),
          "Exact classification sets must be immutable frozensets.")
    risk = value.minimum_risk
    _need(risk is None or type(risk) is Fraction, "Exact risk must be Fraction/None.")
    return records.OracleBExactSnapshot(
        unresolved_cells=value.unresolved_cells, frontier_cells=value.frontier_cells,
        unconstrained_cells=value.unconstrained_cells, total_worlds=value.total_worlds,
        mine_worlds=value.mine_worlds, G0=_cells(value.G0), G1=_cells(value.G1),
        minimum_risk=risk, minimum_risk_cells=_cells(value.minimum_risk_cells),
        shared_kernel_evidence=value.shared_kernel_evidence, kernel=value.kernel,
        materialized_observation=materialized_observation)


def _oracle_b(index, phase, observation, num_mines, logical, proofs, expected, *, ready):
    materialized = tuple(tuple(int(CellState.FLAGGED)
                               if v == CellState.HIDDEN and (x, y) in logical else v
                               for x, v in enumerate(row)) for y, row in enumerate(observation))
    expected_snapshot = _exact_snapshot(expected, materialized)
    input_digest = oracles.oracle_b_input_digest(observation, num_mines, logical)
    actual_snapshot = None
    if not ready:
        status, differences = AuditStatus.INCOMPLETE, ("UNQUALIFIED_PUBLIC_PREREQUISITES",)
    else:
        try:
            actual = oracles.materialized_exact_reference(
                observation, num_mines, status=GameStatus.PLAYING, logical_mines=logical, proofs=proofs)
            _need(type(actual) is oracles.OracleBResult, "Oracle B returned the wrong class.")
            actual_snapshot = _exact_snapshot(actual, actual.materialized_observation)
            differences = tuple(name for name in _EXACT_FIELDS
                                if getattr(expected_snapshot, name) != getattr(actual_snapshot, name))
            if (actual.shared_kernel_evidence != oracles.SHARED_KERNEL_EVIDENCE
                    or actual.kernel != oracles.FROZEN_EXACT_KERNEL
                    or expected.shared_kernel_evidence != oracles.SHARED_KERNEL_EVIDENCE
                    or expected.kernel != oracles.FROZEN_EXACT_KERNEL):
                differences += ("FROZEN_KERNEL_DISCLOSURE",)
            if type(actual.total_worlds) is not int or actual.total_worlds <= 0:
                differences += ("POSITIVE_EXACT_INTEGER_WORLD_COUNT",)
            if _canonical(actual.materialized_observation) != _canonical(materialized):
                differences += ("materialized_observation",)
            status = AuditStatus.FAIL if differences else AuditStatus.PASS
        except (ValueError, TypeError, AttributeError, IndexError, KeyError, StopIteration, ZeroDivisionError) as error:
            status, differences = AuditStatus.FAIL, ("ORACLE_B_PUBLIC_CHECK: " + str(error),)
            # A malformed actual value cannot escape even if some fields were extracted.
            actual_snapshot = None
    return OracleBAuditRecord(
        index, phase, _cells(logical), observation,
        tuple(game.certificate_reference(proof)[1] for proof in proofs), input_digest,
        records.oracle_b_snapshot_digest(expected_snapshot),
        None if actual_snapshot is None else records.oracle_b_snapshot_digest(actual_snapshot),
        status, differences, expected_snapshot, actual_snapshot)


def audit_k_p0(raw, projection, *, raw_arm, table, oracle_b_enabled):
    """Audit one supplied board. No subset choice, solver replay or truth read.

    Certificate owned-M snapshots are batch premises, not the running union of
    earlier targets. Only PASS certificates enter the qualified proof history.
    A broken history prevents subsequent Oracle-B qualification, while retaining
    every reached phase and every acquisition's public verifier result.
    """
    _need(type(oracle_b_enabled) is bool, "Oracle selection must be an exact bool.")
    _bind_raw(raw, projection, raw_arm=raw_arm, table=table)
    certificates, oracle_checks, proofs = [], [], ()
    failures, incomplete = [], []
    history_valid = True
    acquisitions = iter(projection.acquisitions)
    if not projection.effect_evidence_complete:
        incomplete.append("INCOMPLETE_PUBLIC_EXECUTION_EVIDENCE")
    if not projection.p3_evidence_complete:
        incomplete.append("INCOMPLETE_DECISION_EVIDENCE")
    try:
        for trace in raw.traces[1:]:
            index = trace.input_index
            if trace.selection is None:
                incomplete.append("MISSING_DECISION:" + str(index))
                history_valid = False
                continue
            decision = trace.selection.evidence
            observation = decision.observation
            effect = trace.public_effect
            public_ready = effect is not None
            if public_ready:
                _need(observation == effect.before_observation, "Decision/public observation differs.")
            d_check = None
            for phase, batch, retained in (("D", decision.local.certificates, decision.local.before.M),
                                           ("E", decision.exact_certificates, decision.local.after.M)):
                for certificate in batch:
                    acquisition = next(acquisitions, None)
                    _need(acquisition is not None and acquisition.action_ordinal == index,
                          "Acquisition coverage/boundary differs.")
                    _need(certificate.observation == observation and certificate.num_mines == raw_arm.board.mines
                          and certificate.status is GameStatus.PLAYING and certificate.retained_mines == retained,
                          "Certificate public/batch premise binding differs.")
                    if phase == "E":
                        _need(decision.phase_d is not None and certificate.exact_reached is True
                              and certificate.total_worlds == decision.phase_d.total_worlds
                              and certificate.mine_worlds == decision.phase_d.mine_worlds,
                              "Exact certificate and archived Phase D differ.")
                    item = _audit_certificate(certificate, acquisition, proofs, history_valid=history_valid)
                    certificates.append(item)
                    if item.status is AuditStatus.PASS:
                        proofs += (certificate,)
                    else:
                        history_valid = False
                expected = decision.phase_d if phase == "D" else decision.phase_e
                if oracle_b_enabled and expected is not None:
                    ready = public_ready and history_valid
                    if phase == "E":
                        ready = ready and d_check is not None and d_check.status is AuditStatus.PASS
                    logical = decision.local.after.M if phase == "D" else decision.after.M
                    check = _oracle_b(index, phase, observation, raw_arm.board.mines, logical,
                                      proofs, expected, ready=ready)
                    oracle_checks.append(check)
                    if phase == "D":
                        d_check = check
        _need(next(acquisitions, None) is None, "Unconsumed I4 acquisition evidence.")
        for item in certificates:
            reason = "CERTIFICATE:" + str(item.action_ordinal) + ":" + item.acquisition.certificate_sha256
            if item.status is AuditStatus.FAIL:
                failures.append(reason)
            elif item.status is AuditStatus.INCOMPLETE:
                incomplete.append(reason)
        for item in oracle_checks:
            reason = "ORACLE_B:" + str(item.action_ordinal) + ":" + item.phase
            if item.status is AuditStatus.FAIL:
                failures.append(reason)
            elif item.status is AuditStatus.INCOMPLETE:
                incomplete.append(reason)
        status = AuditStatus.FAIL if failures else AuditStatus.INCOMPLETE if incomplete else AuditStatus.PASS
        return KBoardPublicAudit(raw_arm, tuple(certificates), oracle_b_enabled, tuple(oracle_checks),
                                 status, tuple(incomplete), tuple(failures))
    except E2AuditError:
        raise
    except (ValueError, TypeError, AttributeError, IndexError, KeyError, StopIteration) as error:
        raise E2AuditError(str(error)) from error


@dataclass(frozen=True, slots=True)
class DeterminismAudit:
    """Exact semantic comparison; complete detached premises survive a mismatch."""

    selected: bool
    first_digest: str | None
    repeat_digest: str | None
    status: AuditStatus | None
    first_difference_path: str | None
    left_value: object
    right_value: object
    first_semantics: tuple | None
    repeat_semantics: tuple | None

    def __post_init__(self):
        _need(type(self.selected) is bool, "Determinism selection must be an exact bool.")
        for value in (self.left_value, self.right_value, self.first_semantics, self.repeat_semantics):
            _closed(value)
        for value in (self.first_digest, self.repeat_digest):
            _need(value is None or (type(value) is str and len(value) == 64
                  and all(char in "0123456789abcdef" for char in value)),
                  "Determinism requires exact SHA-256 identities.")
        if not self.selected:
            _need(all(value is None for value in (
                self.first_digest, self.repeat_digest, self.status, self.first_difference_path,
                self.left_value, self.right_value, self.first_semantics, self.repeat_semantics)),
                "Unselected determinism cannot claim an evaluated result.")
            return
        _need(type(self.first_semantics) is tuple and self.first_digest is not None
              and type(self.status) is AuditStatus, "Selected determinism needs its first semantic record.")
        if self.status is AuditStatus.INCOMPLETE:
            _need(self.repeat_semantics is None and self.repeat_digest is None
                  and self.first_difference_path is self.left_value is self.right_value is None,
                  "Missing repeat evidence must remain explicit.")
            return
        _need(type(self.repeat_semantics) is tuple and self.repeat_digest is not None,
              "Completed determinism needs both full semantic records.")
        equal = (self.first_semantics == self.repeat_semantics
                 and self.first_digest == self.repeat_digest)
        _need((self.status is AuditStatus.PASS) == equal,
              "Determinism PASS requires exact equality as well as equal digests.")
        if equal:
            _need(self.first_difference_path is self.left_value is self.right_value is None,
                  "Matching deterministic evidence cannot carry a difference.")
        else:
            _need(type(self.first_difference_path) is str and bool(self.first_difference_path)
                  and self.left_value != self.right_value,
                  "Determinism FAIL needs its exact first difference.")


def determinism_record(audit):
    """Project a validated rich comparison to the canonical durable summary.

    I6 must persist BOTH first and repeat full I1 semantic component streams:
    physical inputs, public effects, terminal effects, action decisions, P-3
    checkpoints and acquisitions, together with the relevant board/arm identity.
    This summary is never the sole premise; its digests cannot replace those
    streams. Persistence/orchestration stays with I6. Exact semantic equality
    remains mandatory in the rich comparator before a PASS summary is possible.
    """
    _need(type(audit) is DeterminismAudit, "Expected an exact rich determinism audit.")
    DeterminismAudit.__post_init__(audit)
    return records.DeterminismAuditRecord(
        audit.selected, audit.first_digest, audit.repeat_digest, audit.status,
        audit.first_difference_path)


def _det_record(value, cls):
    _need(type(value) is cls, "Determinism requires exact " + cls.__name__ + " records.")
    cls.__post_init__(value)
    return value


def _det_records(values, cls):
    _need(type(values) is tuple, "Determinism streams must be immutable tuples.")
    return tuple(_det_record(value, cls) for value in values)


def _det_board(board):
    _det_record(board, records.BoardIdentity)
    return _items(game_index=board.game_index, fingerprint=board.fingerprint,
                  width=board.width, height=board.height, mines=board.mines,
                  first_click=board.first_click, generator_identity=board.generator_identity,
                  spec_identity=board.spec_identity)


def _det_arm(arm):
    _det_record(arm, records.ArmIdentity)
    _need(arm.arm is records.Arm.K_P0, "I5 determinism compares K-P0 projections only.")
    # Run/unit transport identity intentionally differs between independent runs.
    return _items(arm=arm.arm.value, board=_det_board(arm.board))


def _det_fraction(value):
    _need(type(value) is Fraction, "Exact checkpoint probabilities require Fraction values.")
    return ("fraction", value.numerator, value.denominator)


def _det_decision(item):
    return _items(arm=_det_arm(item.arm), action_ordinal=item.action_ordinal,
                  category=item.category, semantic_kind=item.semantic_kind,
                  action=item.action.value, target=item.target,
                  plan_actions=tuple((action.value, cell) for action, cell in item.plan_actions),
                  plan_model_us=item.plan_model_us, plan_safe_reveals=item.plan_safe_reveals,
                  setup_cells=item.setup_cells, reveal_cells=item.reveal_cells,
                  logical_mines_before=item.logical_mines_before,
                  logical_mines_after=item.logical_mines_after)


def _det_checkpoint(item):
    return _items(arm=_det_arm(item.arm), guess_ordinal=item.guess_ordinal,
                  public_clues=item.public_clues, physical_p=item.physical_p,
                  effective_p_union_m=item.effective_p_union_m, unresolved=item.unresolved,
                  mine_budget=item.mine_budget, unreduced_z=item.unreduced_z,
                  mine_counts=item.mine_counts,
                  probabilities=tuple((cell, _det_fraction(value)) for cell, value in item.probabilities),
                  minimum_risk=_det_fraction(item.minimum_risk), minimum_ties=item.minimum_ties,
                  chosen_target=item.chosen_target, eventual_outcome=item.eventual_outcome.value)


def _deterministic_semantics(projection):
    """An explicit whitelist, not dataclass traversal or raw-object equality.

    The comparator checks record schemas and the accepted durable setup join.
    Raw-execution/projection binding remains the public audit's separate job;
    comparing repeated records does not rerun that audit or a solver.
    """
    _need(type(projection) is game.GameProjection, "Expected an exact detached I4 GameProjection.")
    arm = _det_arm(projection.arm)
    _need(type(projection.outcome) is records.Outcome, "Missing exact deterministic outcome.")
    physical = _det_records(projection.physical_inputs, records.PhysicalInputRecord)
    public = _det_records(projection.public_effects, records.PublicEffectRecord)
    terminal = _det_records(projection.terminal_effects, records.TerminalEffectRecord)
    spans = _det_records(projection.decision_spans, records.DecisionSpanRecord)
    decisions = _det_records(projection.decisions, records.ActionDecisionRecord)
    checkpoints = _det_records(projection.guess_checkpoints, records.GuessCheckpointRecord)
    acquisitions = _det_records(projection.acquisitions, records.AcquisitionRecord)
    _need(type(projection.flag_provenance) is tuple and not projection.flag_provenance,
          "K-P0 determinism cannot retain CONTROL flag provenance.")
    _need(all(item.arm == projection.arm for item in decisions + checkpoints),
          "Deterministic child evidence has a different arm identity.")
    _need(type(projection.total_model_us) is int and projection.total_model_us >= 0,
          "Model C total must be an exact nonnegative integer.")
    _need(all(type(value) is bool for value in (
        projection.effect_evidence_complete, projection.p3_evidence_complete,
        projection.g5_evidence_complete)), "Deterministic evidence completeness must be explicit.")
    _need(type(projection.diagnostics) is tuple
          and all(type(value) is str and bool(value) for value in projection.diagnostics),
          "Deterministic diagnostic facts must be detached strings.")
    setup = game.derive_k_setup_facts_from_records(physical, decisions, acquisitions)
    _det_record(setup, game.KSetupFacts)
    semantic = _items(
        arm=arm, outcome=projection.outcome.value,
        physical_inputs=tuple(_items(
            action_ordinal=item.action_ordinal, action=item.action.value, target=item.target,
            cursor_before=item.cursor_before, input_us=item.input_us,
            cumulative_us=item.cumulative_us, after_status=item.after_status.value) for item in physical),
        public_effects=tuple(_items(
            action_ordinal=item.action_ordinal,
            changes=tuple(_items(cell=change.cell, before=change.before, after=change.after)
                          for change in item.changes),
            before_status=item.before_status.value, after_status=item.after_status.value) for item in public),
        terminal_effects=tuple(_items(
            action_ordinal=item.action_ordinal,
            changes=tuple(_items(cell=change.cell, presentation=change.presentation.value)
                          for change in item.changes), terminal_status=item.terminal_status.value)
            for item in terminal),
        # Scope/coverage remain semantic; all duration values are excluded.
        decision_spans=tuple(_items(action_ordinal=item.action_ordinal, scope=item.scope.value)
                             for item in spans),
        decisions=tuple(_det_decision(item) for item in decisions),
        guess_checkpoints=tuple(_det_checkpoint(item) for item in checkpoints),
        acquisitions=tuple(_items(
            action_ordinal=item.action_ordinal, decision_ordinal=item.decision_ordinal,
            cell=item.cell, source=item.source.value, certificate_ref=item.certificate_ref,
            certificate_sha256=item.certificate_sha256) for item in acquisitions),
        total_model_us=projection.total_model_us,
        effect_evidence_complete=projection.effect_evidence_complete,
        p3_evidence_complete=projection.p3_evidence_complete,
        g5_evidence_complete=projection.g5_evidence_complete,
        diagnostics=tuple(value for value in projection.diagnostics
                          if not value.startswith("MISSING_COMPARABLE_COMPUTE:")),
        setup_facts=_items(
            executed_setup_flags=setup.executed_setup_flags,
            selected_setup_ordinals=setup.selected_setup_ordinals,
            realized_setup_ordinals=setup.realized_setup_ordinals,
            abandoned_setup_ordinals=setup.abandoned_setup_ordinals,
            terminated_setup_ordinals=setup.terminated_setup_ordinals,
            incomplete_setup_ordinals=setup.incomplete_setup_ordinals))
    _closed(semantic)
    return semantic


def _semantic_digest(value):
    """Hash corroboration only; semantic equality is always checked separately."""
    return _digest(value)


def _named_semantic_tuple(value):
    return (type(value) is tuple and bool(value)
            and all(type(item) is tuple and len(item) == 2 and type(item[0]) is str for item in value)
            and len({item[0] for item in value}) == len(value))


def _first_semantic_difference(left, right, path=""):
    if type(left) is type(right) and left == right:
        return None
    if type(left) is tuple and type(right) is tuple:
        if _named_semantic_tuple(left) and _named_semantic_tuple(right):
            if tuple(item[0] for item in left) == tuple(item[0] for item in right):
                for (name, first), (_, repeat) in zip(left, right):
                    difference = _first_semantic_difference(first, repeat, path + ("." if path else "") + name)
                    if difference is not None:
                        return difference
        else:
            for index, (first, repeat) in enumerate(zip(left, right)):
                difference = _first_semantic_difference(first, repeat, path + "[" + str(index) + "]")
                if difference is not None:
                    return difference
        if len(left) != len(right):
            return (path + ".length", len(left), len(right))
    return (path or "semantics", left, right)


def compare_determinism(first, repeat=None, *, selected):
    """Compare supplied independent K-P0 projections; never execute a repeat."""
    _need(type(selected) is bool, "Determinism selection must be an exact bool.")
    if not selected:
        return DeterminismAudit(False, None, None, None, None, None, None, None, None)
    try:
        left = _deterministic_semantics(first)
        first_digest = _semantic_digest(left)
        if repeat is None:
            return DeterminismAudit(True, first_digest, None, AuditStatus.INCOMPLETE,
                                    None, None, None, left, None)
        right = _deterministic_semantics(repeat)
        repeat_digest = _semantic_digest(right)
        difference = _first_semantic_difference(left, right)
        if difference is None and first_digest == repeat_digest:
            return DeterminismAudit(True, first_digest, repeat_digest, AuditStatus.PASS,
                                    None, None, None, left, right)
        if difference is None:
            difference = ("semantic_digest", first_digest, repeat_digest)
        return DeterminismAudit(True, first_digest, repeat_digest, AuditStatus.FAIL,
                                *difference, left, right)
    except E2AuditError:
        raise
    except (ValueError, TypeError, AttributeError, IndexError, KeyError) as error:
        raise E2AuditError("Malformed deterministic projection: " + str(error)) from error
