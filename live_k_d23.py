"""Worker-only: the basis record of a finished K_D23 decision proposal.

The parent never imports this module. The K owner has already made the decision: ONE K-LC1 selection and
the accepted composition S3D23-A (FT) on it. This module then, for that same pending proposal and in this
order,

  VALIDATION   runs the accepted execution validation on the state the proposal was made for, before any
               sentence about it is written (the permit validation repeats it later on the current state);
  PSEUDO       runs the accepted pseudo 50/50 diagnosis and its validation, when the run's configuration
               includes it and the decision is a guess;
  LINKED       runs the accepted linked diagnosis, its validation and its binding, when configured;
  EXPLANATION  turns the validated records into sentences (experiments.program_d3_explanation). The
               explanation computes nothing and judges nothing;
  record       writes the basis record and checks it exactly as the parent will.

Nothing here selects or changes an input, and no result flows back into the owner, its session M, the
safe cells, the candidates or a later decision. A diagnosis is a separate diagnosis, never a reason.
An error of a stage is raised with its stage, the kind of the original error and its message; the worker's
existing error path then ends the run. No stage error is turned into "continue with another policy".
The diagnosis configuration is fixed when this object is made and does not change during the run.
"""

from time import perf_counter_ns

import live_k_basis as b
import live_k_policy as k


class KD23Explainer:
    """Owned by one K_D23 worker run; consulted once per finished decision proposal."""

    def __init__(self, diagnosis):
        if type(diagnosis) is not str or diagnosis not in b.DIAGNOSES:
            raise k.LivePolicyError(f"Unknown K_D23 diagnosis configuration {diagnosis!r}.")
        from experiments import program_d3_explanation
        from experiments.program_d23_link_runner import link_before_input
        from experiments.program_d23_policy import BRANCH_GUESS, CombinedSelection
        from experiments.program_d3_pseudo_runner import diagnose_before_input

        self.diagnosis = diagnosis
        self._explain = program_d3_explanation
        self._pseudo, self._linked = diagnose_before_input, link_before_input
        self._guess_branch, self._combined_type = BRANCH_GUESS, CombinedSelection

    def describe(self, owner, proposal):
        """KProposalBasis for a K_D23 decision proposal of ``owner``, else None."""
        if not b.basis_required(proposal):
            return None
        combined = owner.combined_selection
        if owner.pending is not proposal or type(combined) is not self._combined_type:
            raise b.basis_error("SENDER_INVALID", "The proposal is not the pending decision of this owner.")
        guess = combined.branch == self._guess_branch
        stages, pseudo, linked = [0, 0, 0, 0], None, None

        def stage(index, name, action):
            started = perf_counter_ns()
            try:
                return action()
            except Exception as exc:
                raise k.d23_stage_error(name, exc) from exc
            finally:
                stages[index] = perf_counter_ns() - started

        # Before any explanation exists: the record it will describe is validated on its own state.
        stage(0, "VALIDATION", owner.validate_pending_execution)
        if guess and self.diagnosis in (b.DIAGNOSIS_PSEUDO, b.DIAGNOSIS_PSEUDO_LINKED):
            pseudo = stage(1, "PSEUDO", lambda: self._pseudo(combined.guess))
        if guess and self.diagnosis == b.DIAGNOSIS_PSEUDO_LINKED:
            linked = stage(2, "LINKED", lambda: self._linked(combined, combined.move))

        def explain():
            explain_decision = self._explain.explain_decision
            executed = explain_decision(combined, pseudo=pseudo, linked=linked, state=self._explain.EXECUTED)
            proposed = explain_decision(combined, state=self._explain.PROPOSED).selection[0]
            blocked = (explain_decision(combined, state=self._explain.BLOCKED).selection[0] if guess else None)
            return executed, proposed, blocked, self._explain.loss_lines_for(combined)

        executed, proposed, blocked, loss = stage(3, "EXPLANATION", explain)
        try:
            original = combined.inner.selected.move
            risk = pair = None
            calls = (0, 0, 0)
            if guess:
                record = combined.guess
                counts = dict(record.premises.mine_worlds)
                risk = (counts[record.target], record.premises.total_worlds)
                pair = record.evidence.pair
                if pair is not None:  # reading order, as the record requires
                    pair = tuple(sorted((tuple(cell) for cell in pair), key=lambda cell: (cell[1], cell[0])))
                calls = (record.actual_calls, 0 if pseudo is None else pseudo.actual_calls,
                         0 if linked is None else linked.actual_calls)
                reason = record.selection_reason
            else:
                reason = combined.opening.reason
            fields = dict(
                basis_id=b.BASIS_ID, token=proposal.token, binding_sha256="0" * 64, diagnosis=self.diagnosis,
                branch=b.BRANCH_GUESS if guess else b.BRANCH_CERTAIN, reason=reason,
                original=(original.action.name, original.x, original.y), input_changed=combined.input_changed,
                risk=risk, pair=pair, short=executed.short, head_proposed=proposed, head_blocked=blocked,
                head_executed=executed.selection[0], body=executed.selection[1:], pseudo=executed.pseudo,
                linked=executed.linked, loss=loss, calls=calls, stage_ns=tuple(stages))
            unbound = b.KProposalBasis(**fields)
            fields["binding_sha256"] = b.basis_digest(proposal, unbound)
            return b.validate_basis(proposal, b.KProposalBasis(**fields), self.diagnosis)
        except Exception as exc:
            raise b.basis_error("SENDER_INVALID", f"record {type(exc).__name__}: {exc}") from exc
