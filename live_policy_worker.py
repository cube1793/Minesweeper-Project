"""Contained, persistent public-only worker for frozen V1 Live decisions."""

import sys
from time import sleep

from experiments.random_expert_exhibition_process import verify_worker_scope
from live_policy import (
    LivePolicyError, ack_from_dict, ack_to_dict, plan_snapshot, proposal_to_dict,
    PHASE_FLAG_REVIEW, snapshot_from_dict, validate_ack, validate_start_snapshot,
)
from live_policy_info import InfoSupplement
from live_policy_transport import MAX_V1_SEQUENCE, message, read_next, write_once
import live_k_policy as k_live
from stage3_physical import load_timing_table


def _check_sequence(sequence, bound):
    if type(sequence) is not int or not 0 <= sequence <= bound:
        raise LivePolicyError("Entry-mode transport sequence bound exceeded.")


def _k_proposal_payload(proposal, k_info, k_owner=None, k_basis=None):
    """The unchanged 14 KProposal keys; K-LC1 and K_D23 decision proposals add ``info``,
    and K_D23 decision proposals add ``basis`` (the reason of the actual input and its diagnoses).

    The proposal is finished and immutable before the display pass reads it.
    A contradiction or integrity error raised here leaves nothing published.
    """
    payload = k_live.to_dict(proposal)
    if k_info is not None:
        record = k_info.describe(proposal)
        if record is not None:
            payload["info"] = k_live.info_to_dict(record)
    if k_basis is not None:
        # K_D23: validation, diagnosis and explanation of the finished proposal. An error of any stage
        # is raised here, nothing is published, and the run ends with that error.
        basis = k_basis.describe(k_owner, proposal)
        if basis is not None:
            import live_k_basis
            payload["basis"] = live_k_basis.basis_to_dict(basis)
    return payload


def serve(directory, run_id):
    """One pending proposal; ACK then an explicit NEXT authorizes more work."""
    table = load_timing_table()
    sequence = 0
    pending = None
    expected_snapshot = None
    review = None
    info = None  # V1 display-only supplement; this process serves exactly one owner run.
    k_owner = None
    k_info = None  # KLC1_INFO_D1: K-LC1 and K_D23; K-P0/K-LC0 never create or load it.
    k_basis = None  # K_D23 only: one diagnosis configuration for the whole run.
    sequence_bound = MAX_V1_SEQUENCE
    while True:
        try:
            _check_sequence(sequence, sequence_bound)
            incoming = read_next(directory, "parent", sequence, run_id)
            if incoming is None:
                sleep(.01)
                continue
            kind, payload = incoming["kind"], incoming["payload"]
            if sequence == 0:
                if kind != "START":
                    raise LivePolicyError("First command must be START.")
                if k_live.is_k_policy(payload.get("policy_id")):
                    snapshot = k_live.from_dict(payload, k_live.KSnapshot)
                    if snapshot.run_id != run_id:
                        raise LivePolicyError("K START run identity mismatch.")
                    k_owner = k_live.KOwner(snapshot, table)
                    if snapshot.policy_id in (k_live.POLICY_K_LC1, k_live.POLICY_K_D23):
                        from live_k_info import KInfoSupplement
                        k_info = KInfoSupplement()
                    if snapshot.policy_id == k_live.POLICY_K_D23:
                        import os
                        import live_k_basis
                        from live_k_d23 import KD23Explainer
                        k_basis = KD23Explainer(live_k_basis.diagnosis_from_environment(os.environ))
                    sequence_bound = k_live.sequence_limit(snapshot)
                    if snapshot.entry_mode == k_live.FLAG_ADOPT:
                        outgoing = message(run_id, sequence, "BOOTSTRAPPED",
                                           k_live.to_dict(k_owner.bootstrap_proof.summary))
                    else:
                        outgoing = message(run_id, sequence, "PROPOSAL",
                                           _k_proposal_payload(k_owner.propose(snapshot), k_info, k_owner, k_basis))
                    write_once(directory, "worker", sequence, outgoing)
                    sequence += 1
                    continue
                snapshot = snapshot_from_dict(payload)
                if snapshot.run_id != run_id or snapshot.input_seq != 0:
                    raise LivePolicyError("START identity/input sequence mismatch.")
                validate_start_snapshot(snapshot)
                info = InfoSupplement()
                pending = plan_snapshot(snapshot, table=table, info=info)
                review = pending.review
                outgoing = message(run_id, sequence, "PROPOSAL", proposal_to_dict(pending))
            elif k_owner is not None:
                if kind == "VALIDATE":
                    permit = k_owner.validate(k_live.from_dict(payload, k_live.KValidation))
                    outgoing = message(run_id, sequence, "ADMITTED", k_live.to_dict(permit))
                elif kind == "ACK":
                    ack = k_live.from_dict(payload, k_live.KAck)
                    k_owner.acknowledge(ack)
                    outgoing = message(run_id, sequence, "ACKED" if ack.status == "PLAYING" else "FINISHED",
                                       k_live.to_dict(ack))
                    if ack.status != "PLAYING":
                        write_once(directory, "worker", sequence, outgoing)
                        return 0
                elif kind == "NEXT":
                    snapshot = k_live.from_dict(payload, k_live.KSnapshot)
                    outgoing = message(run_id, sequence, "PROPOSAL",
                                       _k_proposal_payload(k_owner.propose(snapshot), k_info, k_owner, k_basis))
                else:
                    raise LivePolicyError("K pending requires VALIDATE/ACK, or explicit NEXT after ACK.")
            elif pending is not None:
                if kind != "ACK":
                    raise LivePolicyError("Pending proposal requires ACK before another analysis.")
                ack = ack_from_dict(payload)
                expected_snapshot = validate_ack(pending, ack)
                pending = None
                if ack.status != "PLAYING":
                    outgoing = message(run_id, sequence, "FINISHED",
                                       {"token": ack.token, "input_seq": ack.input_seq, "status": ack.status})
                    write_once(directory, "worker", sequence, outgoing)
                    return 0
                if expected_snapshot.phase != PHASE_FLAG_REVIEW:
                    review = None
                outgoing = message(run_id, sequence, "ACKED", ack_to_dict(ack))
            else:
                if kind != "NEXT":
                    raise LivePolicyError("An acknowledged input requires explicit NEXT.")
                snapshot = snapshot_from_dict(payload)
                if snapshot != expected_snapshot:
                    raise LivePolicyError("NEXT differs from the actual acknowledged public state.")
                pending = plan_snapshot(snapshot, table=table, review=review, info=info)
                review = pending.review
                expected_snapshot = None
                outgoing = message(run_id, sequence, "PROPOSAL", proposal_to_dict(pending))
            write_once(directory, "worker", sequence, outgoing)
            sequence += 1
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"[:8192]
            print(detail, file=sys.stderr, flush=True)
            try:
                write_once(directory, "worker", sequence,
                           message(run_id, sequence, "ERROR", {"code": "WORKER", "detail": detail}))
            except Exception as publication_error:
                print(f"ERROR_PUBLICATION: {publication_error!r}", file=sys.stderr, flush=True)
            return 1


def main(argv):
    if len(argv) != 4:
        print("usage: live_policy_worker directory run_id scope_name", file=sys.stderr)
        return 2
    try:
        verify_worker_scope(argv[3])
        return serve(argv[1], argv[2])
    except Exception as exc:
        print(f"WORKER_START: {exc!r}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
