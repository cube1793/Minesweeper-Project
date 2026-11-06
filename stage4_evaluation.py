"""Bounded, synchronous evaluation of the public Stage 4 planner.

The evaluator owns fixed layouts. Only ``public_request`` crosses the policy
boundary. Prefixes and policy moves go through engine.step, one input at a
time. A caller can journal events as they occur with ``emit``. Without a
journal, the returned attempt retains those events in memory.
"""

from dataclasses import dataclass, fields, replace
from fractions import Fraction
from hashlib import sha256
from itertools import combinations
import json
from math import comb
from time import monotonic

from board_analyzer import analyze_board
from core_engine import Action, GameStatus, MinesweeperEngine
import stage4_planning as planning


DECIDED = ("WON", "LOST", "GUESS_BLOCKED")
OUTCOMES = DECIDED + ("UNRESOLVED",)
EXACT = "EXACT_WITHIN_DECLARED_FAMILY"
SCORE_FIELDS = tuple(field.name for field in fields(planning.Score))
PUBLIC_FIELDS = frozenset(field.name for field in fields(planning.PlanningRequest))
LEDGER_FIELDS = frozenset(field.name for field in fields(planning.PublicInput))


def digest(value):
    data = json.dumps(planning.exact_json(value), sort_keys=True, separators=(",", ":"))
    return sha256(data.encode("utf-8")).hexdigest()


def read_fraction(value):
    """Decode the planner's lossless rational format, rejecting float input."""
    if type(value) is not dict or set(value) != {"numerator", "denominator"}:
        raise ValueError("Expected an exact rational object")
    if any(type(part) is not str for part in value.values()):
        raise ValueError("Rational components must be decimal strings")
    numerator, denominator = int(value["numerator"]), int(value["denominator"])
    if denominator <= 0:
        raise ValueError("Rational denominator must be positive")
    return Fraction(numerator, denominator)


def public_request(*, observation, num_mines, ledger, mode, allow_guess,
                   target, limits, prior_id=planning.PRIOR_ID):
    """Construct a policy DTO using only explicitly named public inputs."""
    request = planning.PlanningRequest(observation, num_mines, ledger, mode,
                                       allow_guess, target, limits, prior_id)
    if set(planning.exact_json(request)) != PUBLIC_FIELDS:
        raise ValueError("Public request schema changed")
    if any(set(planning.exact_json(item)) != LEDGER_FIELDS for item in request.ledger):
        raise ValueError("Public ledger schema changed")
    return request


@dataclass(frozen=True, slots=True)
class Settings:
    mode: str
    allow_guess: bool
    target: Fraction | None
    limits: planning.Limits = planning.Limits()
    prior_id: str = planning.PRIOR_ID

    def __post_init__(self):
        checked = public_request(observation=((-2,),), num_mines=0, ledger=(),
                                 mode=self.mode, allow_guess=self.allow_guess,
                                 target=self.target, limits=self.limits,
                                 prior_id=self.prior_id)
        object.__setattr__(self, "target", checked.target)


@dataclass(frozen=True, slots=True)
class PublicCase:
    observation: tuple
    num_mines: int
    prefix: tuple = ()
    transcript: tuple | None = None

    def __post_init__(self):
        checked = planning.PlanningRequest(self.observation, self.num_mines)
        prefix = tuple(self.prefix)
        if any(type(move) is not planning.Move for move in prefix):
            raise ValueError("Prefix must contain public Move values")
        if any(not (0 <= move.x < len(checked.observation[0])
                    and 0 <= move.y < len(checked.observation)) for move in prefix):
            raise ValueError("Prefix coordinates must be in bounds")
        object.__setattr__(self, "observation", checked.observation)
        object.__setattr__(self, "prefix", prefix)
        if self.transcript is not None:
            transcript = tuple(planning.PlanningRequest(grid, self.num_mines).observation
                               for grid in self.transcript)
            if len(transcript) != len(prefix):
                raise ValueError("One observation per prefix input is required")
            object.__setattr__(self, "transcript", transcript)

    @property
    def identity(self):
        return digest(self)


@dataclass(frozen=True, slots=True)
class Layout:
    mines: tuple
    bbbv: int


@dataclass(frozen=True, slots=True)
class PreparedCase:
    public: PublicCase
    status: str
    layouts: tuple
    ledger: tuple
    replay_records: tuple


def _new_engine(case, mines):
    height, width = len(case.observation), len(case.observation[0])
    engine = MinesweeperEngine(width, height, case.num_mines)
    engine.reset_with_mines(width, height, case.num_mines, mines)
    return engine


def _apply(engine, ledger, move):
    playing = engine.status == GameStatus.PLAYING
    before = tuple(tuple(row) for row in engine.get_observation())
    engine.step(move.x, move.y, getattr(Action, move.action))
    after = tuple(tuple(row) for row in engine.get_observation())
    ledger = planning.record_input(ledger, move.action, move.x, move.y, after,
                                   engine.num_mines, playing=playing)
    counters = engine.get_counter_snapshot()
    if sum(item.counted for item in ledger) != counters["active_clicks"] + counters["wasted_clicks"]:
        raise RuntimeError("PUBLIC_LEDGER_ENGINE_COUNT_MISMATCH")
    return ledger, {"move": move, "before": before, "after": after,
                    "playing_before": playing, "status_after": engine.status.name,
                    "receipt": ledger[-1], "private_counters": counters}


def _replay(case, mines):
    engine = _new_engine(case, mines)
    ledger, transitions = (), []
    for move in case.prefix:
        if engine.status != GameStatus.PLAYING:
            break
        ledger, event = _apply(engine, ledger, move)
        transitions.append(event)
    transcript = tuple(event["after"] for event in transitions)
    observation = tuple(tuple(row) for row in engine.get_observation())
    valid = (engine.status == GameStatus.PLAYING and len(transcript) == len(case.prefix)
             and observation == case.observation)
    return engine, ledger, tuple(transitions), transcript, valid


def prepare_case(case, *, max_cells=64, max_closed=8, max_layouts=256):
    """Enumerate current public posterior, then replay every candidate prefix.

    A layout satisfying the final transcript must also satisfy the current
    clues. Therefore replaying the complete current posterior is sufficient
    to test equality of these two sets. No posterior mass is discarded.
    """
    if type(case) is not PublicCase:
        raise ValueError("PublicCase required")
    grid = case.observation
    height, width = len(grid), len(grid[0])
    closed = tuple((x, y) for y, row in enumerate(grid)
                   for x, value in enumerate(row) if value < 0)
    if (width * height > max_cells or len(closed) > max_closed
            or case.num_mines > len(closed)
            or comb(len(closed), case.num_mines) > max_layouts):
        return PreparedCase(case, "UNSUPPORTED_SIZE", (), (), ())
    layouts, records, common_ledger = [], [], ()
    expected = case.transcript
    accepted = 0
    for mines in combinations(closed, case.num_mines):
        mine_set = set(mines)
        consistent = all(value < 0 or value == sum(
            (nx, ny) in mine_set
            for ny in range(max(0, y - 1), min(height, y + 2))
            for nx in range(max(0, x - 1), min(width, x + 2))
            if (nx, ny) != (x, y))
            for y, row in enumerate(grid) for x, value in enumerate(row))
        if not consistent:
            continue
        engine, ledger, transitions, transcript, valid = _replay(case, mines)
        bbbv = analyze_board(engine.get_board_snapshot()).total_3bv
        layouts.append(Layout(mines, bbbv))
        if expected is None and valid:
            expected = transcript
        matches = valid and transcript == expected
        if matches:
            accepted += 1
            common_ledger = ledger
        records.append({"layout": mines, "bbbv": bbbv, "transitions": transitions,
                        "final_status": engine.status.name, "matches": matches})
    if not layouts:
        status = "INCONSISTENT_INPUT"
    elif accepted == 0:
        status = "PREFIX_NOT_REPLAYABLE"
    elif accepted != len(layouts):
        status = "POSTERIOR_MISMATCH"
    else:
        status = "VALID"
    bound_case = replace(case, transcript=expected) if expected is not None else case
    return PreparedCase(bound_case, status, tuple(layouts), common_ledger, tuple(records))


def request_for(case, settings, *, observation=None, ledger=None):
    return public_request(observation=case.public.observation if observation is None else observation,
                          num_mines=case.public.num_mines,
                          ledger=case.ledger if ledger is None else ledger,
                          mode=settings.mode, allow_guess=settings.allow_guess,
                          target=settings.target, limits=settings.limits,
                          prior_id=settings.prior_id)


@dataclass(frozen=True, slots=True)
class Trial:
    trial_id: str
    case_id: str
    request_id: str
    layout: Layout
    weight: Fraction
    prefix_c: int
    settings: Settings


def plan_trials(case, settings):
    if case.status != "VALID":
        raise ValueError("Only a fully replayable posterior may be evaluated")
    request = request_for(case, settings)
    return tuple(Trial(digest((case.public.identity, request.identity, index)),
                       case.public.identity, request.identity, layout,
                       Fraction(1, len(case.layouts)), request.total_c, settings)
                 for index, layout in enumerate(case.layouts))


@dataclass(slots=True)
class Budget:
    max_calls: int
    max_attempts: int = 320
    max_inputs: int = 16
    deadline: float | None = None
    calls: int = 0
    attempts: int = 0

    def __post_init__(self):
        for name in ("max_calls", "max_attempts", "max_inputs", "calls", "attempts"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError("Budget counts must be nonnegative integers")
        if self.max_inputs > 16 or self.calls > self.max_calls or self.attempts > self.max_attempts:
            raise ValueError("Budget exceeds its bounds")

    def stop_reason(self):
        if self.deadline is not None and monotonic() >= self.deadline:
            return "BATCH_DEADLINE"
        if self.calls >= self.max_calls:
            return "CALL_BUDGET"
        return None


def call_public(request, budget, emit):
    """Call the original planner. The callback journals only public values."""
    reason = budget.stop_reason()
    if reason:
        return None, reason
    budget.calls += 1
    emit({"event": "call_begin", "call_number": budget.calls,
          "request": planning.exact_json(request), "request_id": request.identity})
    try:
        result = planning.plan_next(request)
    except Exception as exc:
        emit({"event": "call_error", "call_number": budget.calls,
              "error_type": type(exc).__name__, "error": str(exc)})
        return None, "PLANNER_EXCEPTION"
    emit({"event": "call_result", "call_number": budget.calls,
          "result": result, "result_hash": digest(result)})
    return result, None


def _score(result):
    values = {name: read_fraction(result["score"][name]) for name in SCORE_FIELDS}
    if any(value < 0 for value in values.values()):
        raise ValueError("Negative score component")
    if sum(values[name] for name in ("win_probability", "lost_probability", "blocked_probability")) != 1:
        raise ValueError("Score mass differs from one")
    if values["target_probability"] > values["win_probability"]:
        raise ValueError("Target mass exceeds winning mass")
    return values


def _validate_result(request, result):
    if type(result) is not dict or result.get("identity") != request.identity:
        raise ValueError("Response must bind the current public request")
    if result.get("observation_id") != request.observation_id:
        raise ValueError("Response observation identity differs")
    if result.get("status") not in ("OK", "DEFER", "TERMINAL"):
        if any(result.get(name) is not None for name in ("action", "score", "terminal_outcome")):
            raise ValueError("Incomplete response contains executable or scored output")
        return None
    if result.get("exactness") != EXACT:
        raise ValueError("Completed response lacks exactness")
    _score(result)
    if result["status"] == "DEFER":
        if (request.allow_guess or result.get("reason") != "GUESS_DISABLED"
                or result.get("terminal_outcome") != "GUESS_BLOCKED"
                or result.get("action") is not None):
            raise ValueError("Invalid blocked response")
        return None
    if result["status"] != "OK" or result.get("terminal_outcome") is not None:
        raise ValueError("Planner terminal conflicts with a playing engine")
    action = result.get("action")
    if type(action) is not dict or set(action) != {"action", "x", "y"}:
        raise ValueError("Exactly one Move is required")
    if any(type(action[name]) is not str for name in ("x", "y")):
        raise ValueError("Planner coordinates must be decimal strings")
    move = planning.Move(action["action"], int(action["x"]), int(action["y"]))
    if not (0 <= move.x < len(request.observation[0]) and 0 <= move.y < len(request.observation)):
        raise ValueError("Planner move out of bounds")
    return move


@dataclass(frozen=True, slots=True)
class Attempt:
    trial: Trial
    execution_state: str
    outcome: str | None
    reason: str
    total_c: int
    additional_inputs: int = 0
    calls: tuple = ()
    all_exact: bool = False
    events: tuple = ()

    @property
    def x(self):
        if self.outcome == "WON":
            return Fraction(self.trial.layout.bbbv, self.total_c)
        if self.outcome in ("LOST", "GUESS_BLOCKED"):
            return Fraction(0)
        return None


def run_attempt(case, trial, budget, *, emit=None):
    """Run one planned layout with a durable pre/post event at each boundary.

    The public planner is deliberately not injectable here. Unit tests may
    patch its module attribute. Every later action requires a fresh call.
    """
    if case.status != "VALID" or trial not in plan_trials(case, trial.settings):
        raise ValueError("Trial does not belong to the complete registered case")
    events = []
    journal = events.append if emit is None else emit
    reason = budget.stop_reason()
    if reason or budget.attempts >= budget.max_attempts:
        answer = Attempt(trial, "NOT_STARTED", None, reason or "ATTEMPT_BUDGET", trial.prefix_c)
        journal({"event": "attempt_not_started", "attempt": answer})
        return replace(answer, events=tuple(events))
    budget.attempts += 1
    journal({"event": "attempt_begin", "trial": trial})
    engine, ledger, prefix_events, transcript, valid = _replay(case.public, trial.layout.mines)
    journal({"event": "prefix_replay", "transitions": prefix_events})
    if not valid or transcript != case.public.transcript or ledger != case.ledger:
        raise RuntimeError("REGISTERED_PREFIX_CHANGED")
    calls, inputs, all_exact = [], 0, True
    outcome, reason = "UNRESOLVED", "INPUT_BUDGET"
    while inputs < budget.max_inputs:
        request = request_for(case, trial.settings, observation=engine.get_observation(), ledger=ledger)
        result, failure = call_public(request, budget, journal)
        if failure:
            reason, all_exact = failure, False
            break
        calls.append({"request_id": request.identity, "result_hash": digest(result),
                      **{name: result.get(name) for name in
                         ("status", "reason", "action", "score", "exactness", "resources")}})
        try:
            move = _validate_result(request, result)
        except (ValueError, TypeError, KeyError) as exc:
            reason, all_exact = "POLICY_PROTOCOL_ERROR", False
            journal({"event": "protocol_error", "error": str(exc)})
            break
        if result["status"] == "DEFER":
            outcome, reason = "GUESS_BLOCKED", "GUESS_DISABLED"
            break
        if result["status"] != "OK":
            reason, all_exact = result.get("reason") or result["status"], False
            break
        stop = budget.deadline is not None and monotonic() >= budget.deadline
        if stop:
            reason, all_exact = "BATCH_DEADLINE_BEFORE_INPUT", False
            break
        journal({"event": "input_begin", "call_number": budget.calls,
                 "request_id": request.identity, "result_hash": digest(result), "move": move})
        ledger, transition = _apply(engine, ledger, move)
        inputs += 1
        journal({"event": "input_end", "call_number": budget.calls, **transition})
        if engine.status != GameStatus.PLAYING:
            outcome, reason = engine.status.name, "ENGINE_TERMINAL"
            break
    total_c = sum(item.counted for item in ledger)
    answer = Attempt(trial, "COMPLETED" if outcome in DECIDED else "INTERRUPTED",
                     outcome, reason, total_c, inputs, tuple(calls),
                     all_exact and bool(calls) and outcome in DECIDED)
    journal({"event": "attempt_end", "attempt": answer})
    return replace(answer, events=tuple(events))


def aggregate(trials, attempts):
    """Reject omitted/duplicate records and retain the full registered mass."""
    trials, attempts = tuple(trials), tuple(attempts)
    ids = [trial.trial_id for trial in trials]
    actual_ids = [attempt.trial.trial_id for attempt in attempts]
    if not ids or len(set(ids)) != len(ids) or len(set(actual_ids)) != len(actual_ids):
        raise ValueError("Empty or duplicate trial IDs")
    if set(ids) != set(actual_ids):
        raise ValueError("Missing or unregistered attempt records")
    if len({(trial.case_id, trial.request_id) for trial in trials}) != 1:
        raise ValueError("Aggregate requires one public case and configuration")
    if len({trial.layout.mines for trial in trials}) != len(trials):
        raise ValueError("Duplicate layout mass")
    if any(type(trial.weight) is not Fraction or trial.weight <= 0 for trial in trials):
        raise ValueError("Positive exact weights required")
    if sum((trial.weight for trial in trials), Fraction(0)) != 1:
        raise ValueError("Registered weights must sum to one")
    if any(trial.weight != Fraction(1, len(trials)) for trial in trials):
        raise ValueError("The public prior requires equal weight for every layout")
    expected = {trial.trial_id: trial for trial in trials}
    for attempt in attempts:
        if attempt.trial != expected[attempt.trial.trial_id]:
            raise ValueError("Attempt binding differs from its registration")
        if (type(attempt.total_c) is not int or type(attempt.additional_inputs) is not int
                or attempt.additional_inputs < 0 or attempt.additional_inputs > 16
                or attempt.total_c != attempt.trial.prefix_c + attempt.additional_inputs):
            raise ValueError("Invalid public input accounting")
        if attempt.execution_state == "NOT_STARTED":
            if attempt.outcome is not None or attempt.additional_inputs or attempt.calls or attempt.all_exact:
                raise ValueError("Unstarted attempt contains execution")
        elif attempt.outcome not in OUTCOMES:
            raise ValueError("Invalid attempt outcome")
        elif attempt.execution_state != ("COMPLETED" if attempt.outcome in DECIDED else "INTERRUPTED"):
            raise ValueError("Outcome and execution state disagree")
        if attempt.outcome == "WON" and attempt.total_c <= 0:
            raise ValueError("Won attempt requires a positive denominator")
    counts = {name: sum(attempt.outcome == name for attempt in attempts) for name in OUTCOMES}
    counts.update(planned=len(trials), started=sum(a.execution_state != "NOT_STARTED" for a in attempts),
                  completed=sum(a.outcome in DECIDED for a in attempts),
                  interrupted=counts["UNRESOLVED"],
                  not_started=sum(a.execution_state == "NOT_STARTED" for a in attempts))
    known = {name: Fraction(0) for name in SCORE_FIELDS}
    unknown, extra_upper = Fraction(0), Fraction(0)
    for attempt in attempts:
        weight = attempt.trial.weight
        if attempt.x is None:
            unknown += weight
            extra_upper += weight * Fraction(attempt.trial.layout.bbbv, max(1, attempt.total_c))
            continue
        known["expected_x"] += weight * attempt.x
        for outcome, name in (("WON", "win_probability"), ("LOST", "lost_probability"),
                              ("GUESS_BLOCKED", "blocked_probability")):
            known[name] += weight * (attempt.outcome == outcome)
        target = attempt.trial.settings.target
        known["target_probability"] += weight * (attempt.outcome == "WON" and target is not None and attempt.x >= target)
    intervals = {name: {"lower": value, "upper": value + (extra_upper if name == "expected_x" else unknown)}
                 for name, value in known.items()}
    initial_scores = [_score({"score": a.calls[0]["score"]})
                      for a in attempts if a.calls and a.calls[0].get("score") is not None]
    initial = initial_scores[0] if initial_scores else None
    eligible = not unknown and all(a.all_exact for a in attempts) and len(initial_scores) == len(trials)
    comparison = "INSUFFICIENT"
    primary = "target_probability" if trials[0].settings.mode == "R" else "expected_x"
    if eligible:
        if any(score != initial for score in initial_scores):
            comparison = "CONTRADICTION"
        else:
            delta = known[primary] - initial[primary]
            comparison = "MATCH" if delta == 0 else "STRICTLY_HIGHER" if delta > 0 else "CONTRADICTION"
    return {"counts": counts, "coverage": 1 - unknown, "unknown_mass": unknown,
            "complete_mean": known if unknown == 0 else None, "intervals": intervals,
            "observed_wins_only": known["expected_x"] / known["win_probability"] if known["win_probability"] else None,
            "initial_score": initial, "primary": primary, "comparison": comparison,
            "component_deltas": {name: known[name] - initial[name] for name in SCORE_FIELDS} if eligible else None}
