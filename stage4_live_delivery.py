"""Worker-owned claims and public proof guards for one atomic input at a time.

Adapted from the reviewed RuntimePending/PublicPending prefix rules. No
engine, layout, seed, Qt or output-harness dependency belongs here.
"""
from fractions import Fraction
from time import perf_counter

from stage4_live_contract import HIDDEN, FLAG, require, move_dict
from stage4_posterior import neighbor_indices
from stage4_public_kernel import verify_facts
from stage4_efficiency_plan import plan_identity
from stage4_exact_pilot import ExactResult, UNIT10_SUMMED, q_pilot_id


def consistent(root, current, safe, mines, total):
    width, height = len(root[0]), len(root)
    require(len(current) == height and all(len(r) == width for r in current), "ROOT_GRID_SHAPE")
    flat, original = sum(current, ()), sum(root, ())
    require(all(v >= 0 or v in (HIDDEN, FLAG) for v in flat), "UNEXPECTED_PUBLIC_VALUE")
    require(all(flat[c] == v for c,v in enumerate(original) if v >= 0), "ROOT_NUMBER_CHANGED")
    require(not any(flat[c] >= 0 for c in mines), "ROOT_MINE_REVEALED")
    closed = {c for c,v in enumerate(flat) if v < 0}
    require(len(mines) <= total <= len(closed-safe), "ROOT_GLOBAL_CONTRADICTION")
    for c in range(len(flat)):
        if flat[c] >= 0:
            adjacent = set(neighbor_indices(width,height)[c])
            require(len(adjacent & mines) <= flat[c] <= len((adjacent & closed)-safe), "ROOT_FACT_CONTRADICTION")


def group(kind, pivot, targets, mines, moves):
    return dict(kind=kind, pivot=pivot, targets=frozenset(targets),
                required_mines=frozenset(mines), moves=tuple(moves))


class PrefixGuard:
    """Public proof and incremental macro cursor; never queues GUI input tails."""
    def __init__(self, root, num_mines, safe, mines, groups, *, survival, joint_flags=None):
        self.root, self.total = root, num_mines
        self.safe, self.mines = frozenset(safe), frozenset(mines)
        self.groups = tuple(groups)
        self.survival, self.joint_flags = survival, joint_flags
        self.group_index = self.move_index = self.position = 0
        self.skips = []
        self.pending = None
        self.expected = root
        self.finished = False

    def _chord_mines(self, g):
        width,height=len(self.root[0]),len(self.root)
        flat=sum(self.root,()); p=g["pivot"]
        require(type(p) is int and 0<=p<len(flat) and flat[p]>0, "SHARED_FLAG_PIVOT")
        closed={c for c in neighbor_indices(width,height)[p] if flat[c]<0}
        mines=closed & self.mines
        moves=g["moves"]
        require(moves and moves[-1]==dict(action="CHORD",x=p%width,y=p//width)
                and all(m["action"]=="FLAG" for m in moves[:-1]), "SHARED_FLAG_GROUP")
        require(g["targets"] and g["targets"]<=closed & self.safe and closed<=self.safe|self.mines
                and len(mines)==flat[p] and g["required_mines"]==mines, "SHARED_FLAG_CHORD_PROOF")
        require(all(m["y"]*width+m["x"] in closed & (self.safe|self.mines) for m in moves[:-1]), "SHARED_FLAG_PREPARATION_PROOF")
        return mines

    def _retained(self, flat):
        g=self.groups[self.group_index]
        if g["kind"]!="CHORD":
            return set()
        current=self._chord_mines(g)
        needed=set()
        for later in self.groups[self.group_index+1:]:
            if later["kind"]=="CHORD":
                mines=self._chord_mines(later)
                if any(flat[t]<0 for t in later["targets"]):
                    needed |= current & mines
        return needed

    def _advance(self):
        self.position+=1
        self.move_index+=1
        if self.move_index==len(self.groups[self.group_index]["moves"]):
            self.group_index+=1; self.move_index=0
        self.finished=self.group_index==len(self.groups)

    def next(self, observation):
        require(self.pending is None and observation==self.expected, "PREFIX_NOT_ACKNOWLEDGED_OR_STALE")
        consistent(self.root,observation,self.safe,self.mines,self.total)
        width,height=len(self.root[0]),len(self.root)
        flat=sum(observation,())
        while not self.finished:
            g=self.groups[self.group_index]; m=g["moves"][self.move_index]
            c=m["y"]*width+m["x"]
            require(0<=m["x"]<width and 0<=m["y"]<height, "PREFIX_COORDINATE")
            desired=None; skip=None
            empty=all(flat[t]>=0 for t in g["targets"])
            retained=self._retained(flat) if empty and self.joint_flags is None else set()
            if empty and not (m["action"]=="FLAG" and c in retained):
                skip="SKIP_ALREADY_OPEN"
            elif self.joint_flags is not None:
                if m["action"]=="FLAG":
                    desired=c in self.joint_flags
                    require(flat[c] in (HIDDEN,FLAG) and (flat[c]==FLAG)!=desired, "CANDIDATE_PREPARATION")
                elif m["action"]=="OPEN":
                    require(flat[c]==HIDDEN and g["targets"]=={c}, "CANDIDATE_OPEN_TARGET")
                else:
                    adjacent=set(neighbor_indices(width,height)[c])
                    require(m["action"]=="CHORD" and flat[c]>0
                            and {n for n in adjacent if flat[n]==HIDDEN}==g["targets"]
                            and {n for n in adjacent if flat[n]==FLAG}==self.joint_flags
                            and len(self.joint_flags)==flat[c], "EXACT_JOINT_CHORD_EVENT_CHANGED")
            elif m["action"]=="FLAG":
                desired=c in self.mines
                if flat[c]>=0:
                    require(not desired,"MINE_PREPARATION_REVEALED"); skip="SKIP_ALREADY_OPEN"
                elif (flat[c]==FLAG)==desired:
                    skip="SKIP_FLAG_ALREADY_PREPARED"
                else:
                    require(flat[c] in (HIDDEN,FLAG) and (c in self.mines if desired else c in self.safe or self.survival<1),"FLAG_PROOF")
            elif m["action"]=="OPEN":
                if flat[c]>=0:
                    skip="SKIP_ALREADY_OPEN"
                else:
                    require(flat[c]==HIDDEN and (c in self.safe or self.survival<1),"OPEN_PROOF")
            else:
                adjacent=set(neighbor_indices(width,height)[c])
                require(m["action"]=="CHORD" and flat[c]>0,"CHORD_PIVOT")
                targets={n for n in adjacent if flat[n]==HIDDEN}
                if not targets:
                    skip="SKIP_ALREADY_OPEN"
                else:
                    require(sum(flat[n]==FLAG for n in adjacent)==flat[c] and targets<=self.safe,"CHORD_PROOF")
            if skip:
                self.skips.append(dict(position=self.position,reason=skip,move=m))
                self._advance()
                continue
            self.pending=m
            return m,desired,self.position
        return None

    def acknowledge(self, observation, status):
        require(self.pending is not None,"PREFIX_ACK_WITHOUT_INPUT")
        self.pending=None
        self._advance()
        if status=="PLAYING":
            consistent(self.root,observation,self.safe,self.mines,self.total)
            self.expected=observation
        else:
            require(status in ("WON","LOST") and (self.survival<1 or status!="LOST"),"SAFE_GROUP_LOST")
            self.finished=True


class RuntimeDelivery:
    def __init__(self, policy, request, result):
        require(result.request_id==request.identity and result.settings_fingerprint==request.settings_fingerprint,
                "RUNTIME_BINDING")
        sequence=policy.claim(result,request)
        require(sequence and sequence==result.sequence,"CONSUMED_OR_STALE_RUNTIME_PROPOSAL")
        self.claim_id=result.proposal_id
        self.request_id=request.identity
        self.result=result  # Worker retains authority and full proof, never IPC.
        root=request.observation; width=len(root[0]); height=len(root)
        moves=tuple(move_dict(m) for m in sequence)
        require(len(moves)<=480,"STAGE4_MACRO_BOUND")
        joint=None
        if result.decision_source=="MODEL":
            model=result.model
            require(model is not None and model.status=="COMPLETE" and model.usage.accounting_complete,"MODEL_NOT_COMPLETE")
            candidates=[c for c in model.root.candidates if c.candidate_id==model.selected_candidate_id]
            require(len(candidates)==1,"MODEL_CANDIDATE_ID")
            candidate=candidates[0]
            require(candidate.sequence==sequence==model.sequence and candidate.status==candidate.survival.status=="EXACT", "MODEL_SELECTION_BINDING")
            eligible=candidate.eligibility.guess_off if not request.allow_guess else getattr(candidate.eligibility,request.mode+"_guess_on")
            survival=candidate.survival_probability
            require(eligible is True and survival is not None and 0<survival<=1
                    and survival==Fraction(candidate.survival.worlds,model.root.base.total_worlds),"MODEL_EXACT_ELIGIBILITY")
            safe={y*width+x for row in model.root.base.marginals for x,y in (row.coordinate,) if row.mine_worlds==0}
            mines={y*width+x for row in model.root.base.marginals for x,y in (row.coordinate,) if row.mine_worlds==model.root.base.total_worlds}
            targets={y*width+x for x,y in candidate.targets}
            joint=frozenset(y*width+x for x,y in candidate.final_flags)
            pivot=candidate.pivot[1]*width+candidate.pivot[0]
            groups=(group(candidate.kind,pivot,targets,joint,moves),)
            self.source="MODEL"
        else:
            f=result.followup
            require(result.decision_source=="F" and f is not None and f.status=="READY"
                    and f.request.observation==root and f.request.counted_inputs==request.counted_inputs
                    and f.sequence==sequence,"F_DELIVERY_BINDING")
            self.source=f.source
            if f.source=="PUBLIC_KERNEL":
                def checkpoint(_units):
                    require(perf_counter()<result.expires_at,"PROPOSAL_DEADLINE")
                verify_facts(f.kernel_request,f.facts,checkpoint=checkpoint)
                p=f.plan
                require(p.status=="READY" and p.group is not None and p.request_id==f.kernel_request.identity
                        and p.proof_id==f.facts.proof_id and p.plan_id==plan_identity(p.request_id,p.proof_id,
                            p.limits,p.status,p.reason,p.provenance,p.group,p.candidates,p.components),"PLAN_FACT_BINDING")
                safe,mines=set(f.facts.proven_safe),set(f.facts.proven_mines)
                g=p.group
                require(g.sequence==sequence,"PLAN_SEQUENCE")
                groups=(group(g.kind,g.pivot,g.targets,g.required_mines,moves),)
                survival=Fraction(1)
            else:
                q,qr=f.q_result,f.q_request
                require(f.source=="EXACT_Q" and type(q) is ExactResult and qr is not None
                        and qr.observation==root and qr.counted_inputs==request.counted_inputs
                        and qr.allow_guess==request.allow_guess and q.request_id==qr.identity
                        and q.pilot_id==q_pilot_id(UNIT10_SUMMED) and q.base_backend==UNIT10_SUMMED
                        and q.status=="READY" and q.sequence==sequence and q.work_accounting_complete
                        and not q.error and not q.cache_hit and q.exact_work==0,"Q_PROVENANCE")
                require(q.mine_probability is not None and 0<=q.mine_probability<1,"Q_PROBABILITY")
                safe,mines=set(q.proven_safe),set(q.proven_mines)
                survival=1-q.mine_probability
                flat=list(sum(root,()))
                require(all(m["action"]=="FLAG" for m in moves[:-1]),"Q_MACRO_SHAPE")
                for m in moves[:-1]:
                    c=m["y"]*width+m["x"]
                    require(flat[c] in (HIDDEN,FLAG),"Q_PREPARATION_STATE")
                    if survival==1:
                        require(c in (safe if flat[c]==FLAG else mines),"Q_PREPARATION_PROOF")
                    flat[c]=HIDDEN if flat[c]==FLAG else FLAG
                last=moves[-1]; pivot=last["y"]*width+last["x"]
                if last["action"]=="OPEN":
                    require(flat[pivot]==HIDDEN,"Q_OPEN_STATE"); targets={pivot}
                else:
                    adjacent=set(neighbor_indices(width,height)[pivot])
                    require(last["action"]=="CHORD" and flat[pivot]>0
                            and sum(flat[c]==FLAG for c in adjacent)==flat[pivot],"Q_CHORD_FLAGS")
                    targets={c for c in adjacent if flat[c]==HIDDEN}
                require(targets and (survival<1 or targets<=safe),"Q_DIRECT_PROOF")
                groups=(group(last["action"],pivot,targets,mines & set(neighbor_indices(width,height)[pivot]),moves),)
        require(request.allow_guess or survival==1,"GUESS_OFF_DELIVERY")
        self.guard=PrefixGuard(root,request.num_mines,safe,mines,groups,survival=survival,joint_flags=joint)
        self.survival=survival

    def next(self, observation):
        return self.guard.next(observation)

    def acknowledge(self, observation, status):
        self.guard.acknowledge(observation,status)

    @property
    def finished(self):
        return self.guard.finished
