"""Additional fixed-layout runs for the Same-board Comparison (pure, no Qt).

Each algorithm's unchanged product decision logic runs once on the admitted
fixed layout: Stage-2 Simple and Stage-3 V1 through their runners, the K family
through ``live_k_policy.KOwner`` and Stage4 S/M/R through
``stage4_live_worker.Session``, both with their existing FIXED_BOARD entry.
Decisions receive public snapshots only. The layout is confined to engine setup
(``same_board_runner._fixed_engine``) and to the parent's validation/metrics.

A worker returns only moves, settings and a short detail. ``validate_run``
replays the moves on a fresh fixed engine, recounts the actions and recomputes
the original Model C total; any disagreement is an error, never a result.
Model C time is through termination and is not a speed ranking.
"""

from collections import Counter
from dataclasses import dataclass, field, replace
import uuid

from core_engine import Action, GameStatus
from replay_model import ReplayBoard
from same_board_runner import (
    ActionCounts, ComparisonExecutionError, _fixed_engine, _validated_layout,
)


ALGORITHMS = ("S2", "S3", "K_P0", "K_LC0", "K_LC1", "K_D23", "S4_S", "S4_M", "S4_R")
LEGACY_PAIR = ("S2", "S3")
K_ALGORITHMS = ("K_P0", "K_LC0", "K_LC1", "K_D23")
STAGE4_ALGORITHMS = ("S4_S", "S4_M", "S4_R")
LABELS = {
    "S2": "Stage 2 Simple", "S3": "Stage 3 V1", "K_P0": "K-P0", "K_LC0": "K-LC0",
    "K_LC1": "K-LC1", "K_D23": "K (K_D23)", "S4_S": "Stage4 S", "S4_M": "Stage4 M",
    "S4_R": "Stage4 R",
}
# Per-algorithm limits fixed from the 2026-11-21 pilot (max K 3.266 s, max
# Stage4 109.641 s on two 30x16/99 boards); never relaxed during a run.
LIMIT_SECONDS = {
    "S2": 120.0, "S3": 120.0, "K_P0": 30.0, "K_LC0": 30.0, "K_LC1": 30.0, "K_D23": 30.0,
    "S4_S": 120.0, "S4_M": 120.0, "S4_R": 120.0,
}
TIME_DEPENDENT = frozenset(STAGE4_ALGORITHMS)
TIME_DEPENDENCE_NOTE = ("시간 기반 한도(계획 1회 35초, 모델·커널 마감) 때문에 "
                        "같은 보드에서도 실행마다 결과가 달라질 수 있습니다.")
OUTCOMES = ("WON", "LOST", "STOPPED", "LIMIT", "CANCELLED", "ERROR")
PLAYABLE_OUTCOMES = ("WON", "LOST", "STOPPED")
MOVE_ACTIONS = ("OPEN", "FLAG", "CHORD")
MOVE_STATUSES = ("PLAYING", "WON", "LOST")


def support_reason(algorithm: str, board: ReplayBoard) -> str | None:
    """None when the algorithm can run on this board; otherwise the reason."""
    if algorithm not in ALGORITHMS:
        return "알 수 없는 알고리즘입니다."
    if algorithm in LEGACY_PAIR:
        return None
    from live_policy import supports_v1_board
    if not supports_v1_board(board.width, board.height, board.num_mines):
        return ("K와 Stage4는 기본 난이도 보드(9×9/10, 16×16/40, 30×16/99)에서만 실행할 수 있습니다"
                "(실시간 자동 진행과 같은 지원 범위).")
    return None


def settings_for(algorithm: str, r_target: str | None = None) -> tuple[tuple[str, str], ...]:
    """The recorded run configuration (F-C2); r_target is a percent text for S4_R.

    Display text (F-S4, Korean); internal IDs stay with a Korean description.
    Execution and validation never read these strings.
    """
    if algorithm == "S2":
        return (("추측", "허용"), ("첫 입력", "OPEN (0, 0) 선언"))
    if algorithm == "S3":
        return (("첫 입력", "OPEN (0, 0) 선언"), ("비용 모델", "원 Model C"))
    if algorithm in K_ALGORITHMS:
        import live_k_policy as k
        definition = k.definition_for_entry(k.FIXED_BOARD, _k_policy(algorithm))
        pairs = (("진입", "FIXED_BOARD (고정 배치 보드에서 시작)"),
                 ("정의", f"{definition} (고정 배치용 정의 ID)"),
                 ("첫 입력", "전부 HIDDEN인 공개 보드에서 정책이 선택"),
                 ("추측", "정책 고유의 정확 추측"))
        if algorithm == "K_D23":
            pairs += (("진단", "NONE (표시용 정보 보충·설명·진단을 만들지 않음)"),)
        return pairs
    if algorithm in STAGE4_ALGORITHMS:
        pairs = (("진입", "FIXED_BOARD (고정 배치 보드에서 시작)"), ("모드", algorithm[-1]),
                 ("프로필", "indexed (표본 8 / 후보 4)"), ("모델 시도", "최대 8회"),
                 ("계획 시간 한도", "35 s"), ("추측", "허용 (전부 HIDDEN인 보드에서 시작하려면 필요)"),
                 ("첫 입력", "전부 HIDDEN인 공개 보드에서 정책이 선택"))
        if algorithm == "S4_R":
            pairs += (("R 목표", f"{r_target}%"),)
        return pairs
    raise ValueError("Unknown algorithm.")


@dataclass(frozen=True)
class AlgorithmMove:
    action: str
    x: int
    y: int
    status_after: str

    def __post_init__(self):
        if (type(self.action) is not str or self.action not in MOVE_ACTIONS
                or any(type(value) is not int or value < 0 for value in (self.x, self.y))
                or type(self.status_after) is not str or self.status_after not in MOVE_STATUSES):
            raise ValueError("Invalid algorithm move.")


@dataclass(frozen=True)
class AlgorithmRun:
    """One executed algorithm. Metrics are filled only by validate_run."""

    algorithm: str
    outcome: str
    moves: tuple = ()
    settings: tuple = ()
    detail: str = ""
    actions: ActionCounts | None = None
    model_c_total_us: int | None = None
    elapsed_seconds: float | None = None
    validated: bool = field(default=False)

    def __post_init__(self):
        object.__setattr__(self, "moves", tuple(self.moves))
        object.__setattr__(self, "settings", tuple(tuple(pair) for pair in self.settings))
        if self.algorithm not in ALGORITHMS or self.outcome not in OUTCOMES:
            raise ValueError("Invalid algorithm run identity or outcome.")
        if any(type(move) is not AlgorithmMove for move in self.moves):
            raise ValueError("Algorithm moves must be AlgorithmMove values.")
        if any(len(pair) != 2 or any(type(part) is not str for part in pair) for pair in self.settings):
            raise ValueError("Settings must be (str, str) pairs.")
        if type(self.detail) is not str:
            raise ValueError("Detail must be text.")
        if self.outcome not in PLAYABLE_OUTCOMES and self.moves:
            raise ValueError("Only a played run carries moves.")

    @property
    def label(self) -> str:
        return LABELS[self.algorithm]

    @property
    def time_dependent(self) -> bool:
        return self.algorithm in TIME_DEPENDENT

    @property
    def playable(self) -> bool:
        return self.validated and self.outcome in PLAYABLE_OUTCOMES


def not_run(algorithm: str, outcome: str, detail: str = "", *, settings=(),
            elapsed_seconds: float | None = None) -> AlgorithmRun:
    """A LIMIT/CANCELLED/ERROR record; it never carries moves or metrics."""
    if outcome not in ("LIMIT", "CANCELLED", "ERROR"):
        raise ValueError("Only LIMIT, CANCELLED or ERROR can be recorded without a played run.")
    return AlgorithmRun(algorithm, outcome, (), settings, detail, elapsed_seconds=elapsed_seconds)


# --- execution (worker side) -------------------------------------------------

def _k_policy(algorithm):
    import live_k_policy as k
    return {"K_P0": k.POLICY_K, "K_LC0": k.POLICY_K_LC0,
            "K_LC1": k.POLICY_K_LC1, "K_D23": k.POLICY_K_D23}[algorithm]


def _public_observation(engine):
    return tuple(tuple(int(value) for value in row) for row in engine.get_observation())


def _run_k(engine, algorithm):
    import live_k_policy as k
    from stage3_physical import load_timing_table

    policy_id = _k_policy(algorithm)
    snapshot = k.make_snapshot(
        run_id=uuid.uuid4().hex, board_generation=0, input_seq=0,
        width=engine.width, height=engine.height, num_mines=engine.num_mines,
        observation=_public_observation(engine), cursor=(0, 0), input_revision=0,
        game_id=uuid.uuid4().hex, policy_id=policy_id,
        definition=k.definition_for_entry(k.FIXED_BOARD, policy_id),
        entry_mode=k.FIXED_BOARD, phase=k.normal_phase(policy_id),
    )
    k.validate_start_snapshot(snapshot)
    owner = k.KOwner(snapshot, load_timing_table())
    moves = []
    while True:
        proposal = owner.propose(snapshot)
        permit = owner.validate(k.KValidation(snapshot, proposal.token, uuid.uuid4().hex,
                                              proposal.pending_m_revision))
        engine.step(proposal.x, proposal.y, Action[proposal.action])
        moves.append(AlgorithmMove(proposal.action, proposal.x, proposal.y, engine.status.name))
        playing = engine.status == GameStatus.PLAYING
        following = owner.acknowledge(k.make_ack(
            permit, engine.status, _public_observation(engine) if playing else None))
        if not playing:
            return moves, ""
        snapshot = following


def _run_stage4(engine, algorithm, r_target):
    from stage4_live_contract import Acknowledgement, Settings, Snapshot, digest, target_percent
    from stage4_live_worker import Session
    from stage4_runtime_policy import RuntimeHistory

    mode = algorithm[-1]
    target = target_percent(r_target) if mode == "R" else None
    settings = Settings(mode, "indexed", True, target)
    game_id, owner_id, run_id = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
    events = []

    def public_state(cursor):
        counters = engine.get_counter_snapshot()
        status = engine.status.name
        return Snapshot(game_id, owner_id, run_id, 0, settings,
                        _public_observation(engine) if status == "PLAYING" else None,
                        engine.width, engine.height, engine.num_mines,
                        counters["active_clicks"] + counters["wasted_clicks"], len(events), len(events),
                        digest([repr(event) for event in events]), cursor, "FIXED_BOARD", status)

    state = public_state((0, 0))
    session = Session(state, RuntimeHistory(), lambda _history: None)
    moves = []
    try:
        while True:
            projection = session.propose(state)
            if projection["move"] is None:
                return moves, f"{projection['status']}: {projection['reason']}"[:512]
            nonce = uuid.uuid4().hex
            session.validate(dict(state=state.to_dict(), token=projection["token"], nonce=nonce))
            move = projection["move"]
            events.append((move["action"], move["x"], move["y"]))
            engine.step(move["x"], move["y"], Action[move["action"]])
            moves.append(AlgorithmMove(move["action"], move["x"], move["y"], engine.status.name))
            after = public_state((move["x"], move["y"]))
            session.acknowledge(Acknowledgement(run_id, projection["token"], nonce,
                                                state.identity, after).to_dict())
            state = after
            if engine.status != GameStatus.PLAYING:
                return moves, ""
    finally:
        session.policy.close()


def _run_stage2(engine):
    from simple_runner import run_simple
    traces = []
    run_simple(engine, accept_guesses=True, initial_open=(0, 0), observer=traces.append)
    return [AlgorithmMove(t.move.action.name, t.move.x, t.move.y, t.status_after.name)
            for t in traces], ""


def _run_stage3(engine):
    from benchmark_modeled_time import authenticate_model_c
    from stage3_runner import run_stage3
    result = run_stage3(engine, table=authenticate_model_c().table)
    return [AlgorithmMove(t.move.action.name, t.move.x, t.move.y, t.status_after.name)
            for t in result.traces], ""


def execute_algorithm(algorithm: str, board: ReplayBoard, *, r_target: str | None = None) -> AlgorithmRun:
    """Run one algorithm once on a fresh fixed engine; exceptions propagate."""
    if algorithm not in ALGORITHMS:
        raise ValueError("Unknown algorithm.")
    reason = support_reason(algorithm, board)
    if reason is not None:
        raise ValueError(reason)
    if algorithm == "S4_R":
        from stage4_live_contract import target_percent
        target_percent(r_target)  # Validate before any engine/decision work.
    elif r_target is not None:
        raise ValueError("Only Stage4 R takes a target.")
    engine = _fixed_engine(_validated_layout(board))
    if algorithm == "S2":
        moves, detail = _run_stage2(engine)
    elif algorithm == "S3":
        moves, detail = _run_stage3(engine)
    elif algorithm in K_ALGORITHMS:
        moves, detail = _run_k(engine, algorithm)
    else:
        moves, detail = _run_stage4(engine, algorithm, r_target)
    status = engine.status
    outcome = status.name if status in (GameStatus.WON, GameStatus.LOST) else "STOPPED"
    return AlgorithmRun(algorithm, outcome, tuple(moves), settings_for(algorithm, r_target), detail)


# --- validation (parent side) -------------------------------------------------

def validate_run(board: ReplayBoard, run: AlgorithmRun) -> AlgorithmRun:
    """Independently replay and recount a transported run; return it with metrics."""
    from benchmark_modeled_time import authenticate_model_c, evaluate_ordered_actions

    if type(run) is not AlgorithmRun:
        raise ComparisonExecutionError("An AlgorithmRun is required.")
    if run.outcome not in PLAYABLE_OUTCOMES:
        if run.moves or run.actions is not None or run.model_c_total_us is not None:
            raise ComparisonExecutionError("A run that did not play cannot carry moves or metrics.")
        return run
    layout = _validated_layout(board)
    engine = _fixed_engine(layout)
    for index, move in enumerate(run.moves):
        if engine.status != GameStatus.PLAYING:
            raise ComparisonExecutionError(f"Move {index} follows a terminal board.")
        if not (move.x < board.width and move.y < board.height):
            raise ComparisonExecutionError(f"Move {index} is outside the board.")
        engine.step(move.x, move.y, Action[move.action])
        if engine.status.name != move.status_after:
            raise ComparisonExecutionError(f"Move {index} status differs from fixed-board replay.")
    if run.outcome == "STOPPED":
        if engine.status != GameStatus.PLAYING:
            raise ComparisonExecutionError("A stopped run cannot end on a terminal board.")
        model_c = None
    else:
        if engine.status.name != run.outcome or not run.moves:
            raise ComparisonExecutionError("Run outcome differs from fixed-board replay.")
        model_c = evaluate_ordered_actions(
            ((index, Action[m.action], m.x, m.y, GameStatus[m.status_after])
             for index, m in enumerate(run.moves)),
            total_actions=len(run.moves), terminal_status=engine.status,
            width=board.width, height=board.height, evaluation=authenticate_model_c(),
        )
    counts = Counter(move.action for move in run.moves)
    actions = ActionCounts(len(run.moves), counts["OPEN"], counts["FLAG"], counts["CHORD"])
    return replace(run, actions=actions, model_c_total_us=model_c, validated=True)
