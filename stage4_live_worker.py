"""Persistent Stage4 owner, entered through main.py before any Qt import."""
import sys
from time import monotonic_ns, sleep

from experiments.random_expert_exhibition_process import verify_worker_scope
from stage4_live_contract import (Snapshot, Acknowledgement, POLICY_ID, MAX_SEQUENCE, MAX_INPUTS,
    require, fields, text, digest, exact, envelope, read_next, write_once,
    validate_ack, guard_target, PERMIT_NS)
from stage4_live_delivery import RuntimeDelivery
from stage4_runtime_policy import RuntimePolicy, RuntimeHistory

class Session:
    def __init__(self, state, history, history_sink, *, policy=None, clock_ns=monotonic_ns):
        require(state.status=="PLAYING", "STAGE4_START_TERMINAL")
        require(history.scope in (None,(state.game_id,state.game_id)), "STAGE4_HISTORY_SCOPE")
        self.policy = policy if policy is not None else RuntimePolicy(history=history,history_sink=history_sink)
        self.state=state; self.delivery=None; self.pending=None; self.permit=None
        self.last_result=None; self.validations=0; self.clock_ns=clock_ns
        self.closed=False

    def propose(self,state):
        require(not self.closed and self.pending is None and state==self.state, "STAGE4_NEXT_BEFORE_ACK_OR_STALE")
        if state.entry=="CANONICAL_NEW":
            move=dict(action="OPEN",x=0,y=0); desired=None; position=0
            source,status,reason="BOOTSTRAP","READY","FIRST_CLICK_CANONICAL_UNPLACED"
            request_id=digest([POLICY_ID,"FIRST_CLICK",state.to_dict()]); survival=None
            claim_id=request_id; model_status="NOT_CALLED"
        else:
            if self.delivery is None or self.delivery.finished:
                request=state.runtime_request()
                self.last_result=self.policy.choose(request)
                result=self.last_result
                if not result.sequence:
                    self.delivery=None
                    projection=dict(state_id=state.identity,request_id=request.identity,
                        token=digest([state.identity,result.status,result.reason]),move=None,position=0,
                        source="NONE",status=result.status,
                        reason=(result.reason+(": "+result.error if result.error else ""))[:512],is_guess=False,
                        desired_flag=None,model_status=result.model_status,
                        attempts=self.policy.attempts_used,survival=None)
                    self.closed=True
                    return projection
                self.delivery=RuntimeDelivery(self.policy,request,result)
            value=self.delivery.next(state.observation)
            if value is None:
                # A flood can consume the rest without input; fresh planning is
                # explicit and occurs only from the acknowledged observation.
                self.delivery=None
                return self.propose(state)
            move,desired,position=value
            result=self.last_result
            source,status,reason=self.delivery.source,result.status,result.reason
            request_id,claim_id=self.delivery.request_id,self.delivery.claim_id
            survival=self.delivery.survival; model_status=result.model_status
        self.pending=dict(state_id=state.identity,request_id=request_id,
            token=digest([claim_id,state.identity,position]),move=move,position=position,
            source=source,status=status,reason=reason,is_guess=survival is not None and survival<1,
            desired_flag=desired,model_status=model_status,attempts=self.policy.attempts_used,
            survival=exact(survival))
        self.validations=0
        guard_target(self.pending,state)
        return self.pending

    def validate(self,payload):
        fields(payload,"state token nonce")
        state=Snapshot.from_dict(payload["state"]); nonce=text(payload["nonce"])
        require(not self.closed and self.pending is not None and state==self.state
                and payload["token"]==self.pending["token"] and self.validations<16,"STAGE4_VALIDATE_BINDING")
        guard_target(self.pending,state)
        require(max(state.counted,state.revision,state.event_count)<MAX_INPUTS,"STAGE4_INPUT_LIMIT")
        self.validations+=1
        self.permit=dict(proposal=self.pending,nonce=nonce,deadline_ns=self.clock_ns()+PERMIT_NS)
        return self.permit

    def acknowledge(self,payload):
        ack=Acknowledgement.from_dict(payload)
        require(not self.closed and self.pending is not None and self.permit is not None,"STAGE4_ACK_WITHOUT_PERMIT")
        after=validate_ack(ack,self.state,self.pending,self.permit["nonce"])
        require(self.pending["source"]!="BOOTSTRAP" or after.status!="LOST","STAGE4_SAFE_BOOTSTRAP_LOST")
        if self.delivery is not None:
            self.delivery.acknowledge(after.observation,after.status)
        self.state=after; self.pending=None; self.permit=None
        if after.status!="PLAYING":
            self.closed=True; self.policy.close()
        return ack


def serve(directory,run_id):
    sequence=0; session=None; history_seq=0
    def publish_history(history):
        nonlocal history_seq
        write_once(directory,"history",history_seq,envelope(run_id,history_seq,"HISTORY",history.to_payload()))
        history_seq+=1
    try:
        while sequence<=MAX_SEQUENCE:
            incoming=read_next(directory,"parent",sequence,run_id)
            if incoming is None:
                sleep(.01);continue
            kind,payload=incoming["kind"],incoming["payload"]
            if sequence==0:
                require(kind=="START","STAGE4_START_REQUIRED")
                fields(payload,"state history")
                state=Snapshot.from_dict(payload["state"])
                require(state.run_id==run_id,"STAGE4_START_RUN")
                history=RuntimeHistory.from_payload(payload["history"])
                publish_history(history)
                session=Session(state,history,publish_history)
                reply=session.propose(state); outgoing="PROPOSAL"
            elif kind=="NEXT":
                fields(payload,"state")
                reply=session.propose(Snapshot.from_dict(payload["state"]));outgoing="PROPOSAL"
            elif kind=="VALIDATE":
                require(sequence<MAX_SEQUENCE,"STAGE4_ACK_SEQUENCE_RESERVATION")
                reply=session.validate(payload);outgoing="ADMITTED"
            elif kind=="ACK":
                ack=session.acknowledge(payload)
                outgoing="ACKED" if ack.status=="PLAYING" else "FINISHED"
                reply=ack.to_dict()
            else:
                raise ValueError("STAGE4_UNEXPECTED_COMMAND")
            write_once(directory,"worker",sequence,envelope(run_id,sequence,outgoing,reply))
            sequence+=1
            if outgoing=="FINISHED":
                return 0
    except Exception as exc:
        detail=f"{type(exc).__name__}: {exc}"[:2048]
        print(detail,file=sys.stderr,flush=True)
        try:
            write_once(directory,"worker",sequence,envelope(run_id,sequence,"ERROR",dict(code="STAGE4_WORKER",detail=detail)))
        except Exception as error:
            print(f"PUBLICATION: {error!r}",file=sys.stderr,flush=True)
        return 1
    finally:
        if session is not None:
            session.policy.close()
    return 1


def main(argv):
    if len(argv)!=4:
        print("usage: --stage4-live-worker directory run_id scope_name",file=sys.stderr)
        return 2
    try:
        verify_worker_scope(argv[3])
        return serve(argv[1],argv[2])
    except Exception as exc:
        print(f"STAGE4_WORKER_START: {exc!r}",file=sys.stderr,flush=True)
        return 1
