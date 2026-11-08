"""Unit30 public contract; controlled limits are not performance evidence."""
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import stage4_live_contract as c
import stage4_runtime_policy as p
from stage4_runtime_model import RuntimeUsage


def snapshot(**changes):
    value=c.Snapshot("game","owner","run",0,c.Settings("S","indexed",True),
        ((-2,1,-2),(-2,-2,-3)),3,2,1,2,2,2,c.digest(["open","flag"]),(2,1))
    return replace(value,**changes)


def limited(request,**_kwargs):
    return SimpleNamespace(request_id=request.identity,model_id=p.MODEL_ID,status="RESOURCE_LIMIT",
        reason="CONTROLLED_TIME_LIMIT",usage=RuntimeUsage())


class ContractTests(unittest.TestCase):
    def test_settings_fraction_profiles_and_public_roundtrip(self):
        self.assertEqual(c.target_percent("120"),Fraction(6,5))
        self.assertEqual(c.target_percent("0.125"),Fraction(1,800))
        for bad in ("","0","-2","nan","1/2","1e3","%120"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):c.target_percent(bad)
        for mode in ("S","M","R"):
            for profile in ("indexed","indexed_k100k"):
                settings=c.Settings(mode,profile,False,Fraction(6,5) if mode=="R" else None)
                s=snapshot(settings=settings)
                self.assertEqual(c.Snapshot.from_dict(json.loads(json.dumps(s.to_dict()))),s)
                r=s.runtime_request()
                self.assertFalse(r.allow_guess)
                self.assertEqual(r.target,settings.target)
                self.assertEqual((r.limits.model.samples,r.limits.model.shortlist,r.limits.model.rows),
                    (8,4,32) if profile=="indexed" else (4,2,8))
        for target in ({"numerator":"2","denominator":"2"},{"numerator":True,"denominator":"2"},
                       {"numerator":"1","denominator":"0"}):
            with self.assertRaises(ValueError):c.fraction(target)

    def test_forbidden_fields_invalid_cells_integers_and_large_dtos(self):
        s=snapshot()
        for key in ("seed","mines","engine","active_clicks","wasted_clicks","full_3BV","unknown"):
            with self.assertRaises(ValueError):c.Snapshot.from_dict(dict(s.to_dict(),**{key:1}))
        for changes in (dict(counted=True),dict(generation=-1),dict(width=481),dict(observation=((9,1,-2),(-2,-2,-3))),
                        dict(status="LOST"),dict(entry="CANONICAL_NEW")):
            with self.subTest(changes=changes),self.assertRaises(ValueError):replace(s,**changes)
        with self.assertRaises(ValueError):c.Settings("S",target=Fraction(1))
        with self.assertRaises(ValueError):c.Settings("R")

    def test_wire_duplicate_stale_future_size_and_legacy_rejected(self):
        with TemporaryDirectory() as d:
            msg=c.envelope("run",0,"NEXT",dict(state=snapshot().to_dict()))
            c.write_once(d,"parent",0,msg)
            self.assertEqual(c.read_next(d,"parent",0,"run"),msg)
            with self.assertRaises(FileExistsError):c.write_once(d,"parent",0,msg)
            with self.assertRaises(ValueError):c.read_next(d,"parent",0,"other")
            c.channel_path(d,"worker",0).write_text('{"schema":"stage4_live_wire_v1","schema":"duplicate"}')
            with self.assertRaises(ValueError):c.read_next(d,"worker",0,"run")
            with self.assertRaises(ValueError):c.envelope("run",c.MAX_SEQUENCE+1,"NEXT",{})
            with self.assertRaises(ValueError):c.write_once(d,"worker",1,c.envelope("run",1,"NEXT",dict(big="x"*c.MAX_BYTES)))
            c.write_once(d,"history",1,c.envelope("run",1,"HISTORY",{}))
            with self.assertRaises(ValueError):c.read_next(d,"history",0,"run")
        with self.assertRaises(ValueError):c.validate_message(dict(version=10,run_id="run",seq=0,kind="START",payload={}))

    def test_consumption_lifecycle_reserves_before_work_and_never_restores_claim(self):
        published=[]
        first=p.RuntimePolicy(history_sink=published.append)
        q=p.RuntimeRequest(((0,-2),),0,1,episode_key="episode",instance_id="instance")
        def model(request,**kwargs):
            self.assertEqual(published[-1].attempts,1)
            self.assertEqual(published[-1].last_attempt_count,1)
            return limited(request)
        with patch.object(p,"evaluate_model",side_effect=model):
            result=first.choose(q)
        self.assertTrue(result.sequence)
        history=first.consumption_history()
        self.assertEqual(p.RuntimeHistory.from_payload(history.to_payload()),history)
        first.cancel()
        second=p.RuntimePolicy(history=history)
        self.assertEqual(second.claim(result,q),())
        with patch.object(p,"evaluate_model",side_effect=limited) as model:
            resumed=second.choose(replace(q,generation=1,counted_inputs=2))
            self.assertFalse(resumed.model_attempted)
            later=second.choose(replace(q,generation=1,counted_inputs=17))
            self.assertTrue(later.model_attempted)
            self.assertEqual(model.call_count,1)
        duplicate=second.choose(replace(q,generation=1,counted_inputs=17))
        self.assertEqual((duplicate.status,duplicate.reason,duplicate.sequence),
            ("RESOURCE_LIMIT","REQUEST_ALREADY_DECIDED_NO_NEW_QUOTA",()))
        first.close();second.close()
        with self.assertRaises(ValueError):p.RuntimeHistory.from_payload(dict(history.to_payload(),pending="forged"))

    def test_ack_target_and_generation_are_bound(self):
        before=snapshot()
        move=dict(action="FLAG",x=2,y=1)
        proposal=dict(state_id=before.identity,request_id="a"*64,token="b"*64,move=move,position=0,
            source="MODEL",status="MODEL_SELECTED",reason="CONTROLLED",is_guess=False,desired_flag=False,
            model_status="COMPLETE",attempts=1,survival=c.exact(Fraction(1)))
        c.guard_target(proposal,before)
        after=replace(before,observation=((-2,1,-2),(-2,-2,-2)),counted=3,revision=3,event_count=3,ledger=c.digest([3]))
        ack=c.Acknowledgement(before.run_id,proposal["token"],"nonce",before.identity,after)
        self.assertEqual(c.validate_ack(ack,before,proposal,"nonce"),after)
        for changed in (replace(before,generation=1),replace(before,settings=c.Settings("M","indexed",True))):
            with self.assertRaises(ValueError):c.guard_target(proposal,changed)
        with self.assertRaises(ValueError):c.validate_ack(ack,before,proposal,"old-nonce")
        with self.assertRaises(ValueError):c.validate_ack(replace(ack,after=replace(after,counted=2)),before,proposal,"nonce")


AUDIT=lambda *args:None


class TransportRecoveryTests(unittest.TestCase):
    def test_ordered_publication_between_absence_and_glob(self):
        # Control the production filesystem-call boundary, not read_next's answer.
        for direction,kind in (("history","HISTORY"),("parent","START"),("worker","PROPOSAL")):
            with self.subTest(direction=direction), TemporaryDirectory() as directory:
                original_glob=Path.glob;published=[]
                first=c.envelope("race",0,kind,p.RuntimeHistory().to_payload() if direction=="history" else {})
                second=c.envelope("race",1,kind,p.RuntimeHistory(("game","game"),0,None,("a"*64,)).to_payload() if direction=="history" else {})
                def interleave(path,pattern):
                    if pattern==f"s4-{direction}-*.json" and not published:
                        self.assertFalse(c.channel_path(directory,direction,0).exists())
                        c.write_once(directory,direction,0,first);published.append(0)
                        c.write_once(directory,direction,1,second);published.append(1)
                    return original_glob(path,pattern)
                try:
                    with patch.object(Path,"glob",interleave):value=c.read_next(directory,direction,0,"race")
                except Exception as exc:
                    AUDIT("ordered_publication",dict(direction=direction,published=published,error=repr(exc),
                        expected_exists=c.channel_path(directory,direction,0).exists()))
                    raise
                self.assertEqual(value,first);self.assertEqual(published,[0,1])
                self.assertEqual(c.read_next(directory,direction,1,"race"),second)
                self.assertIsNone(c.read_next(directory,direction,2,"race"))
                AUDIT("ordered_publication",dict(direction=direction,published=published,read_sequences=[0,1],old_only_poll=None))

    def test_gaps_identity_corruption_names_and_immutable_publication(self):
        cases=("gap","run","sequence","json","duplicate_key","filename","directory","symlink","oversize","schema")
        for case in cases:
            with self.subTest(case=case), TemporaryDirectory() as directory:
                path=c.channel_path(directory,"history",0)
                value=c.envelope("run",0,"HISTORY",p.RuntimeHistory().to_payload())
                if case=="gap":c.write_once(directory,"history",1,c.envelope("run",1,"HISTORY",{}))
                elif case=="run":c.write_once(directory,"history",0,c.envelope("other",0,"HISTORY",{}))
                elif case=="sequence":path.write_text(json.dumps(dict(value,seq=1)))
                elif case=="json":path.write_text('{')
                elif case=="duplicate_key":path.write_text(json.dumps(value)[:-1]+',"seq":0}')
                elif case=="filename":(Path(directory)/"s4-history-invalid.json").write_text('{}')
                elif case=="directory":path.mkdir()
                elif case=="oversize":path.write_bytes(b' '* (c.MAX_BYTES+1))
                elif case=="schema":path.write_text(json.dumps(dict(value,schema="legacy")))
                else:c.write_once(directory,"history",0,value)
                if case=="symlink":
                    original=Path.is_symlink
                    with patch.object(Path,"is_symlink",lambda current:current==path or original(current)):
                        with self.assertRaisesRegex(ValueError,"MESSAGE_PATH"):c.read_next(directory,"history",0,"run")
                else:
                    with self.assertRaises((ValueError,OSError)):c.read_next(directory,"history",0,"run")
        with TemporaryDirectory() as directory:
            value=c.envelope("run",0,"HISTORY",{})
            c.write_once(directory,"history",0,value)
            original=c.channel_path(directory,"history",0).read_bytes()
            with self.assertRaises(FileExistsError):c.write_once(directory,"history",0,value)
            self.assertEqual(c.channel_path(directory,"history",0).read_bytes(),original)
            self.assertIsNone(c.read_next(directory,"history",1,"run"))
            with self.assertRaisesRegex(ValueError,"DIRECTION"):c.read_next(directory,"invalid",0,"run")
