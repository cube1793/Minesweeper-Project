"""Dedicated child executes actual K-P0 then active K-LC0 exactly once each."""

import ast
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

from benchmark_board import EXPERT_GENERAL_V1, calculate_board_fingerprint, generate_board
from core_engine import CellState, GameStatus
from experiments.program_k_evidence import validate_public_effect_stream
from experiments.program_k_runner import KRunResult, run_k_p0
from experiments.program_k_lc0_runner import DistanceRunResult, run_k_lc0
from experiments.program_k_lc0_policy import route_distance
from experiments.random_expert_exhibition_execution import _fresh_engine, _verify_terminal
from experiments.random_expert_exhibition_model import ExhibitionAction, ExhibitionBoard, ExhibitionFrame, _need
from experiments.k_lc0_exhibition_model import ComparePair, CompareTrace, CompareSource, ChoiceNote, PlanNote, DEFINITIONS
from experiments.k_lc0_exhibition_store import now, validate_request
from stage3_physical import action_cost, load_timing_table

ROOT = Path(__file__).resolve().parents[1]


def source_hashes():
    """Conservative local import closure, including function-local imports.

    Includes the source app/renderer/worker even when capture runs GUI-free.
    External libraries are identified by Python version/path, not vendored here.
    """
    todo = list((ROOT/"experiments").glob("k_lc0_exhibition*.py"))
    seen = {ROOT/"calibration/stage3_physical_profile_v1.json"}
    while todo:
        path = todo.pop()
        if path in seen: continue
        seen.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): modules.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                modules.append(node.module)
                modules.extend(node.module+"."+n.name for n in node.names)
        for module in modules:
            base = ROOT.joinpath(*module.split("."))
            candidates = [base.with_suffix(".py"), base/"__init__.py"]
            candidates.extend(ROOT.joinpath(*module.split(".")[:i])/"__init__.py"
                              for i in range(1,len(module.split("."))))
            todo.extend(p for p in candidates if p.is_file() and p not in seen)
    return tuple((p.relative_to(ROOT).as_posix(),sha256(p.read_bytes()).hexdigest()) for p in sorted(seen))


def capture_source():
    def git(*args):
        return subprocess.run(["git","--no-optional-locks",*args],cwd=ROOT,capture_output=True,text=True,
                              encoding="utf-8",check=True,timeout=5,
                              creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)).stdout.strip()
    status = git("status","--porcelain=v1","--untracked-files=normal")
    return CompareSource(git("rev-parse","HEAD"),bool(status),status,sys.version,sys.executable,source_hashes())


def _plan(selection):
    plan = selection.plan
    if plan is None: return None
    return PlanNote(tuple((m.action.name,m.x,m.y) for m in plan.actions),plan.latency_us,plan.reveals,
                    route_distance(plan,selection.cursor),selection.category)


def _choice(trace, choice=None):
    move = (trace.move.action.name,trace.move.x,trace.move.y)
    if trace.selection is None:
        return ChoiceNote("INITIAL","NOT_REACHED","NOT_REACHED",trace.category,"INITIAL_OPEN",False,move,move,None,None)
    selected = trace.selection
    native = choice.native if choice is not None else selected
    reason = choice.reason if choice is not None else ("EXACT_GUESS_UNCHANGED" if selected.continuation == "EXACT_GUESS" else "NATIVE_G_RETAINED")
    return ChoiceNote(selected.continuation,selected.evidence.phase_d_status,selected.evidence.phase_e_status,
                      selected.category,reason,choice.overridden if choice is not None else False,
                      (native.move.action.name,native.move.x,native.move.y),move,_plan(native),_plan(selected))


def project_native(native, policy, table):
    """Only actual return/trace; never regenerate candidates or native choices."""
    if policy == "K-P0":
        _need(type(native) is KRunResult,"Actual K-P0 result required.")
        traces, choices = native.traces, (None,)*len(native.traces)
    else:
        _need(policy == "K-LC0" and type(native) is DistanceRunResult and native.policy_id == "K-LC0"
              and native.policy_definition == "DISTANCE_BAND_V1", "Active K-LC0 result required.")
        traces = tuple(t.action for t in native.traces)
        choices = tuple(t.choice for t in native.traces)
        _need(all(c is None if i == 0 else c is not None and not c.control for i,c in enumerate(choices)), "Wrong LC0 control/choice.")
    _need(traces and all(t.public_effect_status == "CAPTURED" for t in traces), "Missing actual effects.")
    effects = tuple(t.public_effect for t in traces)
    _need(validate_public_effect_stream(effects,complete=True).status == "PASS", "Invalid public effect stream.")
    rows = tuple(tuple(int(v) for v in row) for row in effects[0].before_observation)
    empty = frozenset()
    frames = [ExhibitionFrame(0,rows,"PLAYING",(0,0),0,empty,empty,empty)]
    actions, notes, explicit, total = [], [], empty, 0
    for i,(trace,effect,choice) in enumerate(zip(traces,effects,choices)):
        target = (trace.move.x,trace.move.y)
        _need(trace.input_index == i
              and (trace.move.action,*target) == (effect.move.action,effect.move.x,effect.move.y)
              and trace.status_after is effect.status_after
              and trace.cursor_before == effect.cursor_before and trace.M_before == frames[-1].logical_mines
              and trace.modeled_action_us == effect.modeled_action_us == action_cost(table,trace.cursor_before,target)
              and effect.capture_method == "STATUS_GATED_ACTUAL_EXECUTION", "Native/effect binding mismatch.")
        if trace.move.action.name == "FLAG": explicit = explicit | {target}
        rows = tuple(tuple(int(v) for v in row) for row in effect.after_observation.rows)
        flags = frozenset((x,y) for y,row in enumerate(rows) for x,v in enumerate(row) if v == CellState.FLAGGED)
        automatic = flags-explicit if trace.status_after is GameStatus.WON else empty
        total += trace.modeled_action_us
        actions.append(ExhibitionAction(i,trace.move.action.name,target,trace.cursor_before,trace.modeled_action_us,
                       trace.status_after.name,trace.M_before,trace.preinput_M,effect.safe_cells_opened_delta))
        notes.append(_choice(trace,choice))
        frames.append(ExhibitionFrame(i+1,rows,trace.status_after.name,target,total,trace.preinput_M,explicit,automatic))
    _need(total == native.total_modeled_us and frames[-1].status == native.status.name
          and frames[-1].logical_mines == native.final_M, "Native terminal/total/M mismatch.")
    return CompareTrace(policy,DEFINITIONS[("K-P0","K-LC0").index(policy)],tuple(actions),tuple(frames),tuple(notes))


def run_layout(width,height,mines,fingerprint,table,progress=lambda phase,summary: None):
    """Tiny-fixture seam; the public app entry below always requires Expert."""
    left = _fresh_engine(width,height,mines,fingerprint)
    right = _fresh_engine(width,height,mines,fingerprint)
    _need(left is not right,"Fresh engines required.")
    progress("K_P0_RUNNING",None)
    native = run_k_p0(left,table=table,capture_effects=True)
    kp0 = project_native(native,"K-P0",table)
    _verify_terminal(left,kp0,mines)
    del native,left
    _need(right.status is GameStatus.PLAYING and all(v == CellState.HIDDEN for row in right.get_observation() for v in row),
          "K-LC0 engine changed before its run.")
    progress("K_LC0_RUNNING",kp0.summary())
    native = run_k_lc0(right,table=table,control=False,capture_effects=True)
    lc0 = project_native(native,"K-LC0",table)
    _verify_terminal(right,lc0,mines)
    del native,right
    progress("PROJECTED",lc0.summary())
    return kp0,lc0


def run_pair(request, *, progress=lambda phase,summary: None):
    validate_request(request)
    started = now()
    source = capture_source()
    board = generate_board(EXPERT_GENERAL_V1,request["index"])
    fingerprint = calculate_board_fingerprint(30,16,99,board.mine_positions)
    _need(board.game_index == board.seed == request["index"] and fingerprint == board.board_fingerprint,"Generator identity mismatch.")
    table = load_timing_table()
    left,right = run_layout(30,16,board.mine_positions,fingerprint,table,progress)
    _need(source.files == source_hashes(),"Source changed during pair execution.")
    return ComparePair(request["run_id"],request["requested_at"],started,now(),request["request_kind"],
                       ExhibitionBoard(board.game_index,board.seed,fingerprint),left,right,source,table)
