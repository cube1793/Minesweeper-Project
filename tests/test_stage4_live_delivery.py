"""Actual legal engine prefixes with explicitly controlled candidate selection."""
from fractions import Fraction
from types import SimpleNamespace
from time import perf_counter
import unittest

from core_engine import MinesweeperEngine,Action,GameStatus
from stage4_candidates import CandidateRequest,analyze_candidates
from stage4_public_kernel import KernelRequest,infer_public
from stage4_runtime_policy import RuntimeRequest
from stage4_runtime_model import RuntimeUsage
from stage4_live_delivery import RuntimeDelivery,PrefixGuard,group


def observation(engine):
    return tuple(tuple(int(v) for v in row) for row in engine.get_observation())


class OneClaim:
    def __init__(self):self.calls=0
    def claim(self,result,request):
        self.calls+=1
        return result.sequence if self.calls==1 else ()


class DeliveryTests(unittest.TestCase):
    def test_controlled_exact_model_chord_claim_once_and_actual_engine(self):
        engine=MinesweeperEngine(4,2,1);engine.reset_with_mines(4,2,1,{(3,1)})
        for x,y,a in ((3,0,Action.OPEN),(2,0,Action.OPEN),(2,1,Action.OPEN),(3,1,Action.FLAG)):
            engine.step(x,y,a)
        root=observation(engine)
        evidence=analyze_candidates(CandidateRequest(root,1))
        chosen=next(c for c in evidence.candidates if c.kind=="CHORD" and c.survival_probability==1)
        request=RuntimeRequest(root,1,4,"M",True)
        model=SimpleNamespace(status="COMPLETE",usage=RuntimeUsage(),root=evidence,
            selected_candidate_id=chosen.candidate_id,sequence=chosen.sequence)
        result=SimpleNamespace(request_id=request.identity,settings_fingerprint=request.settings_fingerprint,
            proposal_id="controlled-exact-chord",sequence=chosen.sequence,decision_source="MODEL",model=model,
            expires_at=perf_counter()+30)
        policy=OneClaim();delivery=RuntimeDelivery(policy,request,result)
        self.assertEqual(policy.calls,1)
        with self.assertRaises(ValueError):RuntimeDelivery(policy,request,result)
        actual=[]
        while not delivery.finished:
            item=delivery.next(observation(engine))
            if item is None:break
            move,desired,pos=item
            engine.step(move["x"],move["y"],Action[move["action"]]);actual.append(move)
            delivery.acknowledge(observation(engine) if engine.status==GameStatus.PLAYING else None,engine.status.name)
        self.assertTrue(any(m["action"]=="CHORD" for m in actual))
        self.assertNotEqual(engine.status,GameStatus.LOST)

    def test_controlled_shared_flag_survives_empty_group_after_real_flood(self):
        engine=MinesweeperEngine(5,3,2);engine.reset_with_mines(5,3,2,{(2,2),(4,0)})
        for x,y in ((1,1),(1,2),(2,1),(3,1),(4,1)):engine.step(x,y,Action.OPEN)
        root=observation(engine);facts=infer_public(KernelRequest(root,2))
        self.assertEqual(facts.status,"COMPLETE")
        safe,mines=set(facts.proven_safe),set(facts.proven_mines)
        self.assertIn(12,mines);self.assertIn(13,safe)
        move=lambda a,x,y:dict(action=a,x=x,y=y)
        groups=(group("OPEN",0,{0},set(),(move("OPEN",0,0),)),
            group("CHORD",6,{0,1,2,5,10},{12},(move("FLAG",2,2),move("CHORD",1,1))),
            group("CHORD",7,{13},{12},(move("CHORD",2,1),)))
        guard=PrefixGuard(root,2,safe,mines,groups,survival=Fraction(1))
        actual=[]
        while not guard.finished:
            value=guard.next(observation(engine))
            if value is None:break
            m,desired,pos=value
            actual.append((m,desired,pos));engine.step(m["x"],m["y"],Action[m["action"]])
            guard.acknowledge(observation(engine),engine.status.name)
        self.assertEqual([m[0]["action"] for m in actual],["OPEN","FLAG","CHORD"])
        self.assertTrue(any(x["position"]==2 and x["reason"]=="SKIP_ALREADY_OPEN" for x in guard.skips))
        self.assertGreaterEqual(engine.get_observation()[2][3],0)
        self.assertEqual(engine.get_observation()[2][2],-3)

    def test_prefix_rejects_changed_public_number_and_double_delivery(self):
        root=((1,-2),)
        guard=PrefixGuard(root,1,set(),{1},(group("OPEN",1,{1},set(),(dict(action="OPEN",x=1,y=0),)),),survival=Fraction(1,2))
        with self.assertRaises(ValueError):guard.next(((0,-2),))
        guard.next(root)
        with self.assertRaises(ValueError):guard.next(root)
