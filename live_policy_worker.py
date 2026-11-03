"""Contained, persistent public-only worker for frozen V1 Live decisions."""

import sys
from time import sleep

from experiments.random_expert_exhibition_process import verify_worker_scope
from live_policy import (
    LivePolicyError, ack_from_dict, ack_to_dict, plan_snapshot, proposal_to_dict,
    PHASE_FLAG_REVIEW, snapshot_from_dict, validate_ack, validate_start_snapshot,
)
from live_policy_transport import message, read_next, write_once
import live_k_policy as k_live
from stage3_physical import load_timing_table


def serve(directory, run_id):
    """One pending proposal; ACK then an explicit NEXT authorizes more work."""
    table = load_timing_table()
    sequence = 0
    pending = None
    expected_snapshot = None
    review = None
    k_owner = None
    while True:
        try:
            incoming = read_next(directory, "parent", sequence, run_id)
            if incoming is None:
                sleep(.01)
                continue
            kind, payload = incoming["kind"], incoming["payload"]
            if sequence == 0:
                if kind != "START":
                    raise LivePolicyError("First command must be START.")
                if payload.get("policy_id") == k_live.POLICY_K:
                    snapshot = k_live.from_dict(payload, k_live.KSnapshot)
                    if snapshot.run_id != run_id:
                        raise LivePolicyError("K START run identity mismatch.")
                    k_owner = k_live.KOwner(snapshot, table)
                    outgoing = message(run_id, sequence, "PROPOSAL", k_live.to_dict(k_owner.propose(snapshot)))
                    write_once(directory, "worker", sequence, outgoing)
                    sequence += 1
                    continue
                snapshot = snapshot_from_dict(payload)
                if snapshot.run_id != run_id or snapshot.input_seq != 0:
                    raise LivePolicyError("START identity/input sequence mismatch.")
                validate_start_snapshot(snapshot)
                pending = plan_snapshot(snapshot, table=table)
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
                    outgoing = message(run_id, sequence, "PROPOSAL", k_live.to_dict(k_owner.propose(snapshot)))
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
                pending = plan_snapshot(snapshot, table=table, review=review)
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
