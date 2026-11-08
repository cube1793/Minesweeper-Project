"""Unit30 controlled lifecycle and Unit31 actual product subprocess tests."""
from dataclasses import replace
from fractions import Fraction
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PyQt5.QtWidgets import QApplication
from core_engine import MinesweeperEngine,Action,GameStatus
from stage4_live_contract import (Settings,Snapshot,Acknowledgement,digest,exact)
from stage4_live_job import Stage4LiveJob,build_worker_command
from stage4_live_worker import Session
from stage4_runtime_policy import RuntimeHistory
from tests.test_stage4_live_contract import snapshot

AUDIT=lambda *args:None


def pump(app,predicate,timeout=45):
    end=time.monotonic()+timeout
    while not predicate() and time.monotonic()<end:
        app.processEvents();time.sleep(.005)
    if not predicate():
        raise AssertionError("Bounded Qt wait expired")


def make_engine():
    engine=MinesweeperEngine(3,2,1)
    engine.reset_with_mines(3,2,1,{(2,1)})
    engine.step(1,0,Action.OPEN);engine.step(2,1,Action.FLAG)
    return engine


def apply_to_engine(job,engine,before,proposal):
    nonce="actual-input-nonce"
    job.validate_pending(before,nonce)
    pump(QApplication.instance(),lambda:job.state in ("admitted","idle","blocked"))
    if job.state!="admitted":raise AssertionError(str(job.last_record))
    accepted=job.mark_applying(proposal["token"],nonce,before)
    move=accepted["move"]
    engine.step(move["x"],move["y"],Action[move["action"]])
    status=engine.status.name
    after=replace(before,observation=tuple(tuple(int(v) for v in r) for r in engine.get_observation()) if status=="PLAYING" else None,
        counted=before.counted+1,revision=before.revision+1,event_count=before.event_count+1,
        ledger=digest([before.ledger,move]),cursor=(move["x"],move["y"]),status=status)
    ack=Acknowledgement(before.run_id,proposal["token"],nonce,before.identity,after)
    job.acknowledge(ack)
    pump(QApplication.instance(),lambda:job.last_ack==ack or job.state in ("idle","blocked"))
    if job.last_ack!=ack:raise AssertionError(str(job.last_record))
    return after,ack


class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_admission_reserves_ack_sequence_and_count_capacity(self):
        from stage4_live_contract import MAX_SEQUENCE,MAX_INPUTS
        state=snapshot()
        proposal=dict(state_id=state.identity,request_id="a"*64,token="b"*64,
            move=dict(action="FLAG",x=2,y=1),position=0,source="MODEL",status="MODEL_SELECTED",
            reason="CONTROLLED",is_guess=False,desired_flag=False,model_status="COMPLETE",attempts=1,survival=exact(Fraction(1)))
        job=Stage4LiveJob();job._start_snapshot=job._expected_snapshot=state
        job._pending=proposal;job.state="pending";job._sequence=MAX_SEQUENCE
        with self.assertRaisesRegex(ValueError,"ACK_SEQUENCE"):job.validate_pending(state,"nonce")
        capped=replace(state,counted=MAX_INPUTS,revision=MAX_INPUTS,event_count=MAX_INPUTS)
        job._sequence=1;job._expected_snapshot=capped;job._pending=dict(proposal,state_id=capped.identity)
        with self.assertRaisesRegex(ValueError,"INPUT_LIMIT"):job.validate_pending(capped,"nonce")
        self.assertEqual(job._applied_count,0);job.shutdown()

    def test_main_worker_dispatch_and_frozen_command_without_qt(self):
        import main
        for flag,module in (("--stage4-live-worker","stage4_live_worker"),("--zini-metric-worker","zini_metric_worker"),
                            ("--stage3-execution-worker","stage3_execution_worker"),("--same-board-execution-worker","same_board_execution_worker"),
                            ("--live-policy-worker","live_policy_worker")):
            calls=[]
            with patch.dict(sys.modules,{module:SimpleNamespace(main=lambda args:calls.append(args) or 71)}), \
                 patch.object(sys,"argv",["main.py",flag,"directory","run","scope"]), \
                 patch.object(main,"_configure_qt_plugin_path",side_effect=AssertionError("Qt before dispatch")):
                self.assertEqual(main.main(),71)
            self.assertEqual(calls,[[flag,"directory","run","scope"]])
        with patch.object(sys,"frozen",True,create=True):
            self.assertEqual(build_worker_command("directory","run","scope")[1:],
                             ["--stage4-live-worker","directory","run","scope"])
        with patch.object(sys,"frozen",False,create=True):
            command=build_worker_command("directory","run","scope")
            self.assertEqual(command[1],"-B");self.assertTrue(command[2].endswith("main.py"))

    def test_controlled_bootstrap_order_nonce_and_stale_ack(self):
        state=snapshot(observation=((-2,-2,-2),(-2,-2,-2)),counted=0,revision=0,event_count=0,
                       ledger=digest([]),cursor=(0,0),entry="CANONICAL_NEW")
        fake=SimpleNamespace(attempts_used=0,close=lambda:None)
        session=Session(state,RuntimeHistory(),lambda h:None,policy=fake,clock_ns=lambda:100)
        proposal=session.propose(state)
        self.assertEqual(proposal["source"],"BOOTSTRAP")
        with self.assertRaises(ValueError):session.propose(state)
        request=dict(state=state.to_dict(),token=proposal["token"],nonce="fresh")
        permit=session.validate(request)
        self.assertEqual(permit["deadline_ns"],5_000_000_100)
        after=replace(state,observation=((1,-2,-2),(-2,-2,-2)),counted=1,revision=1,event_count=1,
                      ledger=digest([1]),entry="CURRENT")
        ack=Acknowledgement(state.run_id,proposal["token"],"old",state.identity,after)
        with self.assertRaises(ValueError):session.acknowledge(ack.to_dict())
        ack=replace(ack,nonce="fresh");self.assertEqual(session.acknowledge(ack.to_dict()),ack)
        with self.assertRaises(ValueError):session.acknowledge(ack.to_dict())

    def test_controlled_job_expiry_timeout_cancel_and_cleanup(self):
        state=snapshot()
        proposal=dict(state_id=state.identity,request_id="a"*64,token="b"*64,
            move=dict(action="FLAG",x=2,y=1),position=0,source="MODEL",status="MODEL_SELECTED",
            reason="CONTROLLED",is_guess=False,desired_flag=False,model_status="COMPLETE",attempts=1,survival=exact(Fraction(1)))
        job=Stage4LiveJob(clock=lambda:100.0)
        job._start_snapshot=job._expected_snapshot=state;job._pending=proposal;job.state="admitted"
        job._active_run_id=state.run_id;job._accepted_nonce="nonce"
        job._permit=dict(proposal=proposal,nonce="nonce",deadline_ns=99_000_000_000)
        with self.assertRaisesRegex(ValueError,"EXPIRED"):job.mark_applying(proposal["token"],"nonce",state)
        self.assertEqual(job._applied_count,0)
        class Process:
            def __init__(self):self.stopped=False
            def terminate(self):self.stopped=True
            def kill(self):self.stopped=True
            def poll(self):return 1 if self.stopped else None
            def wait(self,timeout):return 1
        job._process=Process();job._owner_record=dict(run_id=state.run_id,policy_id="STAGE4_LIVE_SMR_V1")
        job.state="computing";job._deadline=99;job.poll()
        self.assertEqual(job.last_record["status"],"TIMEOUT")
        self.assertTrue(job.last_record["cleanup_complete"])
        self.assertEqual(job.last_record["consumed_token_count"],0)
        job.shutdown()
        cancelled=Stage4LiveJob(clock=lambda:100.0)
        cancelled._active_run_id="cancelled";cancelled._process=Process()
        cancelled.cancel("CONTROLLED_CANCEL");cancelled.poll()
        self.assertEqual(cancelled.last_record["status"],"CANCELLED")
        self.assertTrue(cancelled.last_record["cleanup_complete"]);cancelled.shutdown()

    def test_actual_smr_product_subprocess_selection_input_ack(self):
        for mode in ("S","M","R"):
            with self.subTest(mode=mode):
                engine=make_engine();settings=Settings(mode,"indexed",True,Fraction(6,5) if mode=="R" else None)
                state=snapshot(game_id="actual-"+mode,run_id="actual-"+mode,settings=settings)
                job=Stage4LiveJob()
                try:
                    job.start(state)
                    pump(self.app,lambda:job.state in ("pending","idle","blocked"))
                    self.assertEqual(job.state,"pending",job.last_record)
                    p=job.pending;self.assertIsNotNone(p["move"],p)
                    self.assertEqual(p["attempts"],1)
                    after,ack=apply_to_engine(job,engine,state,p)
                    self.assertEqual(job._applied_count,1);self.assertEqual(job._ack_count,1)
                    if mode=="M" and after.status=="PLAYING":
                        job.request(after);pump(self.app,lambda:job.state in ("pending","idle","blocked"))
                        self.assertEqual(job.state,"pending",job.last_record)
                        if job.pending["move"] is not None:apply_to_engine(job,engine,after,job.pending)
                    if job.active_run_id is not None:job.cancel("registered bounded input complete")
                    pump(self.app,lambda:job.state in ("idle","blocked"))
                    self.assertEqual(job.state,"idle",job.last_record)
                    self.assertTrue(job.last_record["cleanup_complete"])
                    AUDIT("actual_smr_"+mode,job.last_record)
                finally:job.shutdown()

    def test_actual_pause_restart_preserves_model_quota(self):
        state=snapshot(game_id="restart-game",run_id="restart-one")
        first=Stage4LiveJob();second=Stage4LiveJob()
        try:
            first.start(state);pump(self.app,lambda:first.state in ("pending","idle","blocked"))
            self.assertEqual(first.state,"pending",first.last_record)
            self.assertEqual(first.history.attempts,1)
            first.cancel("pause before input");pump(self.app,lambda:first.state in ("idle","blocked"))
            self.assertEqual(first.state,"idle",first.last_record)
            history=first.history
            next_state=replace(state,owner_id="next-owner",run_id="restart-two",generation=1)
            second.start(next_state,history);pump(self.app,lambda:second.state in ("pending","idle","blocked"))
            self.assertEqual(second.state,"pending",second.last_record)
            self.assertEqual(second.pending["model_status"],"SKIPPED")
            self.assertEqual(second.history.attempts,1)
            second.cancel("registered restart complete");pump(self.app,lambda:second.state in ("idle","blocked"))
            AUDIT("actual_restart",dict(first=first.last_record,second=second.last_record))
            self.assertTrue(second.last_record["cleanup_complete"])
        finally:first.shutdown();second.shutdown()


class HistoryRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def make_job(self,directory,state):
        from pathlib import Path
        job=Stage4LiveJob();job._directory=Path(directory)
        job._start_snapshot=job._expected_snapshot=state;job._active_run_id=state.run_id
        job._awaiting="PROPOSAL";job.state="computing";job._sequence=0
        return job

    def release(self,job):
        job._directory=None;job._active_run_id=None;job._sent_ack=None;job._scope=None;job.state="idle"
        job.shutdown();job.deleteLater()

    def proposal(self,state):
        return dict(state_id=state.identity,request_id=state.runtime_request().identity,token="b"*64,
            move=dict(action="OPEN",x=0,y=0),position=0,source="EXACT_Q",status="HEURISTIC_FALLBACK",
            reason="CONTROLLED_HISTORY_SCHEDULE",is_guess=True,desired_flag=None,model_status="COMPLETE",
            attempts=1,survival=exact(Fraction(4,5)))

    def test_history_publication_between_first_drain_and_proposal(self):
        from tempfile import TemporaryDirectory
        import stage4_live_job as module
        from stage4_live_contract import envelope,write_once
        with TemporaryDirectory() as directory:
            state=snapshot();job=self.make_job(directory,state);received=[]
            job.proposal_ready.connect(received.append);proposal=self.proposal(state)
            write_once(directory,"history",0,envelope(state.run_id,0,"HISTORY",RuntimeHistory().to_payload()))
            original_read=module.read_next;published=[]
            def interleave(path,direction,seq,run):
                if direction=="worker" and not published:
                    self.assertEqual((job.history_sequence,job.history.attempts),(1,0))
                    histories=(RuntimeHistory((state.game_id,state.game_id),0,None,(proposal["request_id"],)),
                               RuntimeHistory((state.game_id,state.game_id),1,state.counted,(proposal["request_id"],)))
                    for index,history in enumerate(histories,1):
                        write_once(directory,"history",index,envelope(run,index,"HISTORY",history.to_payload()));published.append(index)
                    write_once(directory,"worker",0,envelope(run,0,"PROPOSAL",proposal))
                return original_read(path,direction,seq,run)
            try:
                try:
                    with patch.object(module,"read_next",interleave):job._read_reply()
                except Exception as exc:
                    AUDIT("history_proposal_interleave",dict(published=published,attempts=job.history.attempts,error=repr(exc)))
                    raise
                self.assertEqual((job.history_sequence,job.history.attempts),(3,1))
                self.assertEqual(received,[proposal]);self.assertEqual(job._proposal_count,1)
                nonce="history-race-input";job.validate_pending(state,nonce)
                permit=dict(proposal=proposal,nonce=nonce,deadline_ns=int((job._clock()+5)*1_000_000_000))
                write_once(directory,"worker",1,envelope(state.run_id,1,"ADMITTED",permit));job._read_reply()
                job.mark_applying(proposal["token"],nonce,state)
                engine=make_engine();engine.step(0,0,Action.OPEN)
                after=replace(state,observation=tuple(tuple(int(v) for v in row) for row in engine.get_observation()),
                    counted=3,revision=3,event_count=3,ledger=digest(["history-race-actual-open"]),cursor=(0,0))
                ack=Acknowledgement(state.run_id,proposal["token"],nonce,state.identity,after)
                job.acknowledge(ack);write_once(directory,"worker",2,envelope(state.run_id,2,"ACKED",ack.to_dict()))
                job._read_reply();job._read_reply()
                with self.assertRaises(ValueError):job.mark_applying(proposal["token"],nonce,state)
                self.assertEqual((job._proposal_count,job._applied_count,job._ack_count),(1,1,1))
                AUDIT("history_proposal_interleave",dict(published=published,attempts=job.history.attempts,
                    history_sequence=job.history_sequence,proposals=1,consumed_inputs=1,acknowledged=1))
            finally:self.release(job)

    def test_history_rollback_scope_and_unsettled_remain_errors(self):
        from tempfile import TemporaryDirectory
        from stage4_live_contract import envelope,write_once
        state=snapshot();request_id=state.runtime_request().identity
        initial=RuntimeHistory((state.game_id,state.game_id),1,state.counted,(request_id,))
        histories=(RuntimeHistory((state.game_id,state.game_id),0,None,(request_id,)),
            RuntimeHistory(("other","other"),1,state.counted,(request_id,)),
            RuntimeHistory((state.game_id,state.game_id),1,state.counted,()),
            RuntimeHistory((state.game_id,state.game_id),1,state.counted-1,(request_id,)))
        for history in histories:
            with self.subTest(history=history),TemporaryDirectory() as directory:
                job=self.make_job(directory,state);job.history=initial
                try:
                    write_once(directory,"history",0,envelope(state.run_id,0,"HISTORY",history.to_payload()))
                    with self.assertRaisesRegex(ValueError,"HISTORY.*ROLLBACK"):job._read_reply()
                    self.assertEqual(job.history,initial);self.assertEqual(job._applied_count,0)
                finally:self.release(job)
        with TemporaryDirectory() as directory:
            job=self.make_job(directory,state)
            try:
                write_once(directory,"worker",0,envelope(state.run_id,0,"PROPOSAL",self.proposal(state)))
                with self.assertRaisesRegex(ValueError,"HISTORY_NOT_SETTLED"):job._read_reply()
                self.assertEqual(job._applied_count,0)
            finally:self.release(job)
        with TemporaryDirectory() as directory:
            job=self.make_job(directory,state);job.history=RuntimeHistory((state.game_id,state.game_id))
            try:
                write_once(directory,"history",0,envelope(state.run_id,0,"HISTORY",RuntimeHistory().to_payload()))
                with self.assertRaisesRegex(ValueError,"HISTORY_ROLLBACK"):job._read_reply()
            finally:self.release(job)
