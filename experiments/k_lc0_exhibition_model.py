"""Immutable actual K-P0 / K-LC0 records, independent of ExhibitionTrace.

Validation is structural/public-effect arithmetic, not an inference certificate.
No planner, generation, source-file IO or solver is called when replaying JSON.
"""

from dataclasses import dataclass
from datetime import datetime
from math import fsum, hypot, isfinite
import re

from benchmark_board import calculate_board_fingerprint
from experiments.random_expert_exhibition_model import (
    ExhibitionAction, ExhibitionBoard, ExhibitionFrame, HIDDEN, FLAGGED,
    EXPLODED, MINE, _cells, _coord, _need,
)
from stage3_physical import PROFILE_SHA256, TABLE_SHA256, action_cost, validate_timing_table

POLICIES = ("K-P0", "K-LC0")
DEFINITIONS = ("actual run_k_p0", "DISTANCE_BAND_V1")
SCHEMA = "K_LC0_RANDOM_EXPERT_COMPARE"
VERSION = 1
LIMITS = ("Actual inputs/public frames/M and g/selected plans permit local route inspection. "
          "Other native candidates, survivors, scores, proofs and exact world counts are not saved. "
          "No later calculation is an original native record. SHA-256 detects accidental changes; "
          "it is neither an external signature nor independent execution authentication.")


def distance(actions):
    return fsum(hypot(a.target[0] - a.cursor_before[0], a.target[1] - a.cursor_before[1]) for a in actions)


def valid_time(value):
    _need(type(value) is str and len(value) <= 40, "Invalid timestamp.")
    parsed = datetime.fromisoformat(value)
    _need(parsed.tzinfo is not None, "Timestamp requires timezone.")
    return parsed


def valid_run_id(value):
    _need(type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value) is not None, "Invalid run ID.")


def valid_hash(value, length=64):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


@dataclass(frozen=True, slots=True)
class PlanNote:
    actions: tuple[tuple[str, int, int], ...]
    L: int
    R: int
    D: float
    category: str

    def validate(self, cursor, width, height, table=None):
        _need(type(self.actions) is tuple and 1 <= len(self.actions) <= 9, "Invalid plan actions.")
        for i, move in enumerate(self.actions):
            _need(type(move) is tuple and len(move) == 3 and _coord(move[1:], width, height)
                  and move[0] in (("OPEN", "CHORD") if i == len(self.actions)-1 else ("FLAG",)),
                  "Invalid plan suffix/action.")
        _need(type(self.L) is int and self.L > 0 and type(self.R) is int and 1 <= self.R <= 480
              and type(self.D) is float and isfinite(self.D) and self.D >= 0
              and type(self.category) is str and 0 < len(self.category) < 100, "Invalid plan metrics.")
        points = (cursor,) + tuple(m[1:] for m in self.actions)
        _need(self.D == fsum(hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(points, points[1:])),
              "Recorded plan distance differs from recorded route.")
        if table is not None:
            _need(self.L == sum(action_cost(table, a, b) for a, b in zip(points, points[1:])),
                  "Recorded plan L differs from table.")


@dataclass(frozen=True, slots=True)
class ChoiceNote:
    phase: str
    phase_d: str
    phase_e: str
    category: str
    reason: str
    override: bool
    g_move: tuple[str, int, int]
    selected_move: tuple[str, int, int]
    g: PlanNote | None
    selected: PlanNote | None

    def validate(self, action, policy, width, height, table=None):
        _need(type(self.override) is bool and self.phase in ("INITIAL", "LOCAL_SAFE", "EXACT_SAFE", "EXACT_GUESS")
              and self.phase_d in ("NOT_REACHED", "REACHED")
              and self.phase_e in ("NOT_REACHED", "REACHED_CHANGED", "REACHED_NO_CHANGE"), "Invalid phase.")
        for move in (self.g_move, self.selected_move):
            _need(type(move) is tuple and len(move) == 3 and move[0] in ("OPEN", "FLAG", "CHORD")
                  and _coord(move[1:], width, height), "Invalid choice move.")
        _need(self.selected_move == (action.action, *action.target), "Choice/actual first input mismatch.")
        _need(type(self.category) is str and 0 < len(self.category) < 100, "Invalid category.")
        if action.index == 0:
            _need(self.phase == "INITIAL" and self.reason == "INITIAL_OPEN" and not self.override
                  and self.g is self.selected is None and self.g_move == self.selected_move
                  and self.category == "POLICY_INITIAL_OPEN"
                  and self.phase_d == self.phase_e == "NOT_REACHED", "Invalid initial choice.")
            return
        _need(self.phase != "INITIAL", "Repeated initial choice.")
        _need((self.phase == "LOCAL_SAFE" and self.phase_d == self.phase_e == "NOT_REACHED")
              or (self.phase in ("EXACT_SAFE", "EXACT_GUESS") and self.phase_d == "REACHED"
                  and self.phase_e in ("REACHED_CHANGED", "REACHED_NO_CHANGE")), "Phase reachability mismatch.")
        if self.phase == "EXACT_GUESS":
            _need(self.g is self.selected is None and not self.override and self.g_move == self.selected_move
                  and action.action == "OPEN" and self.reason == "EXACT_GUESS_UNCHANGED"
                  and self.category == "EXACT_MINIMUM_RISK_GUESS", "Changed guess record.")
        else:
            _need(type(self.g) is PlanNote and type(self.selected) is PlanNote, "Missing certainty plans.")
            for plan in (self.g, self.selected):
                plan.validate(action.cursor_before, width, height, table)
            _need(self.g.actions[0] == self.g_move and self.selected.actions[0] == self.selected_move
                  and self.category == self.selected.category
                  and self.override == (self.g != self.selected), "Plan/choice mismatch.")
            if policy == "K-P0":
                _need(not self.override and self.g == self.selected and self.reason == "NATIVE_G_RETAINED",
                      "K-P0 must retain actual g.")
            else:
                _need(20*self.selected.L*self.g.R <= 21*self.g.L*self.selected.R,
                      "Selected plan outside fixed band.")
                _need(self.reason == ("DISTANCE_BAND_OVERRIDE" if self.override else "NATIVE_G_RETAINED"),
                      "Override reason mismatch.")


@dataclass(frozen=True, slots=True)
class CompareTrace:
    policy_id: str
    policy_definition: str
    actions: tuple[ExhibitionAction, ...]
    frames: tuple[ExhibitionFrame, ...]
    choices: tuple[ChoiceNote, ...]

    def __post_init__(self):
        _need(self.policy_id in POLICIES and self.policy_definition == DEFINITIONS[POLICIES.index(self.policy_id)],
              "Actual K-P0/K-LC0 identity required.")
        _need(type(self.actions) is tuple and 0 < len(self.actions) <= 480
              and type(self.frames) is tuple and len(self.frames) == len(self.actions)+1
              and type(self.choices) is tuple and len(self.choices) == len(self.actions), "N+1 frames required.")
        _need(all(type(a) is ExhibitionAction for a in self.actions)
              and all(type(f) is ExhibitionFrame for f in self.frames)
              and all(type(c) is ChoiceNote for c in self.choices), "Invalid immutable record types.")
        first = self.frames[0]
        _need(type(first.observation) is tuple and bool(first.observation)
              and type(first.observation[0]) is tuple, "Invalid public rows.")
        w, h = self.width, self.height
        _need(1 <= w <= 30 and 1 <= h <= 16, "Invalid dimensions.")
        for i, f in enumerate(self.frames):
            _need(type(f.index) is int and f.index == i and type(f.observation) is tuple
                  and len(f.observation) == h and all(type(row) is tuple and len(row) == w
                  and all(type(v) is int and v in range(-6, 9) and v != -1 for v in row)
                  for row in f.observation), "Invalid frame shape/glyph.")
            _need(_coord(f.cursor, w, h) and type(f.cumulative_modeled_us) is int
                  and f.cumulative_modeled_us >= 0, "Invalid frame cursor/cost.")
            _need(all(type(s) is frozenset and all(_coord(c, w, h) for c in s)
                      for s in (f.logical_mines, f.explicit_flags, f.automatic_flags)), "Invalid frame sets.")
            _need(f.status in ("PLAYING", "WON", "LOST")
                  and (f.status == "PLAYING") == (i < len(self.actions)), "Incomplete/premature terminal.")
            if f.status != "LOST":
                _need(all(v >= 0 or v in (HIDDEN, FLAGGED) for row in f.observation for v in row),
                      "Premature terminal disclosure.")
            _need(not f.explicit_flags & f.automatic_flags
                  and _cells(f.observation, FLAGGED) == f.explicit_flags | f.automatic_flags
                  and (not f.automatic_flags or f.status == "WON"), "Flag provenance mismatch.")
        _need(all(v == HIDDEN for row in first.observation for v in row)
              and first.cursor == (0, 0) and first.cumulative_modeled_us == 0
              and not (first.logical_mines | first.explicit_flags | first.automatic_flags), "Not a fresh start.")
        for i, (a, choice) in enumerate(zip(self.actions, self.choices)):
            before, after = self.frames[i:i+2]
            _need(type(a.index) is int and a.index == i and a.action in ("OPEN", "FLAG", "CHORD")
                  and _coord(a.target, w, h) and _coord(a.cursor_before, w, h)
                  and a.cursor_before == before.cursor and after.cursor == a.target
                  and type(a.modeled_action_us) is int and a.modeled_action_us > 0
                  and a.status_after == after.status
                  and after.cumulative_modeled_us == before.cumulative_modeled_us+a.modeled_action_us,
                  "Action/frame/cost/status binding mismatch.")
            _need(type(a.M_before) is frozenset and type(a.preinput_M) is frozenset
                  and all(_coord(c, w, h) for c in a.preinput_M)
                  and a.M_before == before.logical_mines and a.M_before <= a.preinput_M
                  and after.logical_mines == a.preinput_M
                  and all(before.observation[y][x] in (HIDDEN, FLAGGED) for x, y in a.preinput_M),
                  "M completion boundary mismatch.")
            if i == 0:
                _need(not a.preinput_M and a.action == "OPEN" and a.target == (0, 0), "Invalid first OPEN.")
            x, y = a.target
            value = before.observation[y][x]
            if a.action in ("OPEN", "FLAG"):
                _need(value == HIDDEN, "Input target is not hidden.")
                _need((a.target in a.preinput_M) == (a.action == "FLAG"), "Input/M contradiction.")
                if a.action == "OPEN":
                    _need(0 <= after.observation[y][x] <= 8
                          or (after.status == "LOST" and after.observation[y][x] == EXPLODED),
                          "OPEN target has no actual reveal/explosion.")
            else:
                neighbors = ((xx, yy) for yy in range(max(0,y-1),min(h,y+2))
                             for xx in range(max(0,x-1),min(w,x+2)) if (xx,yy) != (x,y))
                _need(1 <= value <= 8 and sum(before.observation[yy][xx] == FLAGGED for xx,yy in neighbors) == value,
                      "CHORD physical flag mismatch.")
            _need(after.explicit_flags == before.explicit_flags | ({a.target} if a.action == "FLAG" else set()),
                  "Only FLAG inputs create explicit flags.")
            safe_delta = 0
            for yy, (oldrow, newrow) in enumerate(zip(before.observation, after.observation)):
                for xx, (old, new) in enumerate(zip(oldrow, newrow)):
                    _need(old < 0 or old == new, "Revealed clue changed.")
                    safe_delta += old in (HIDDEN, FLAGGED) and 0 <= new <= 8
                    if a.action == "FLAG" and (xx, yy) != a.target:
                        _need(old == new, "FLAG changed another cell.")
            _need(type(a.safe_cells_opened_delta) is int and a.safe_cells_opened_delta == safe_delta,
                  "Reveal delta mismatch.")
            _need(a.action == "FLAG" or safe_delta > 0 or after.status == "LOST", "No public progress.")
            choice.validate(a, self.policy_id, w, h)

    @property
    def width(self): return len(self.frames[0].observation[0])
    @property
    def height(self): return len(self.frames[0].observation)
    @property
    def outcome(self): return self.frames[-1].status
    @property
    def total_modeled_us(self): return self.frames[-1].cumulative_modeled_us
    @property
    def counts(self): return tuple(sum(a.action == name for a in self.actions) for name in ("OPEN", "FLAG", "CHORD"))
    def frame(self, index):
        _need(type(index) is int and 0 <= index <= len(self.actions), "Invalid frame index.")
        return self.frames[index]
    def summary(self):
        return dict(policy_id=self.policy_id, outcome=self.outcome, inputs=len(self.actions),
                    open=self.counts[0], flag=self.counts[1], chord=self.counts[2],
                    model_c_us_to_terminal=self.total_modeled_us, total_distance_cells=distance(self.actions),
                    long_moves_ge_8=sum(hypot(a.target[0]-a.cursor_before[0],a.target[1]-a.cursor_before[1]) >= 8
                                        for a in self.actions))


@dataclass(frozen=True, slots=True)
class CompareSource:
    head: str
    dirty: bool
    git_status: str
    python_version: str
    python_executable: str
    files: tuple[tuple[str, str], ...]
    profile_sha256: str = PROFILE_SHA256
    table_sha256: str = TABLE_SHA256

    def validate(self):
        _need(valid_hash(self.head, 40) and type(self.dirty) is bool and type(self.git_status) is str
              and self.dirty == bool(self.git_status) and type(self.python_version) is str
              and bool(self.python_version) and type(self.python_executable) is str
              and bool(self.python_executable), "Invalid source identity.")
        _need(type(self.files) is tuple and 1 <= len(self.files) <= 500, "Source hashes required.")
        names = set()
        for item in self.files:
            _need(type(item) is tuple and len(item) == 2 and type(item[0]) is str
                  and re.fullmatch(r"[A-Za-z0-9_./-]+", item[0]) is not None
                  and not item[0].startswith("/") and ".." not in item[0].split("/")
                  and item[0] not in names and valid_hash(item[1]), "Invalid source hash entry.")
            names.add(item[0])
        _need({"experiments/program_k_runner.py", "experiments/program_k_lc0_runner.py",
               "experiments/program_k_lc0_policy.py", "experiments/k_lc0_exhibition_execution.py",
               "calibration/stage3_physical_profile_v1.json"} <= names, "Missing actual dependencies.")
        _need(self.profile_sha256 == PROFILE_SHA256 and self.table_sha256 == TABLE_SHA256
              and dict(self.files)["calibration/stage3_physical_profile_v1.json"] == PROFILE_SHA256,
              "Model C identity mismatch.")


@dataclass(frozen=True, slots=True)
class ComparePair:
    run_id: str
    requested_at: str
    started_at: str
    completed_at: str
    request_kind: str
    board: ExhibitionBoard
    left: CompareTrace
    right: CompareTrace
    source: CompareSource
    timing_table: tuple[tuple[int, ...], ...]
    record_limits: str = LIMITS

    def __post_init__(self):
        valid_run_id(self.run_id)
        _need(valid_time(self.requested_at) <= valid_time(self.started_at) <= valid_time(self.completed_at),
              "Timestamp order mismatch.")
        _need(self.request_kind in ("index", "draw") and self.record_limits == LIMITS, "Invalid request/record scope.")
        _need(type(self.board) is ExhibitionBoard and type(self.source) is CompareSource, "Missing identity.")
        self.board.__post_init__()
        self.source.validate()
        _need(type(self.timing_table) is tuple and all(type(r) is tuple for r in self.timing_table), "Immutable table required.")
        table = validate_timing_table(self.timing_table)
        for trace, policy in zip((self.left, self.right), POLICIES):
            _need(type(trace) is CompareTrace and trace.policy_id == policy, "Wrong left/right policy.")
            trace.__post_init__()
            _need((trace.width, trace.height) == (30,16), "Expert dimensions required.")
            for action, choice in zip(trace.actions, trace.choices):
                _need(action.modeled_action_us == action_cost(table, action.cursor_before, action.target),
                      "Charged Model C differs from saved authenticated table.")
                choice.validate(action, policy, 30, 16, table)
            final = trace.frames[-1]
            mines = frozenset((x,y) for y,row in enumerate(final.observation) for x,v in enumerate(row)
                              if v in (FLAGGED, MINE, EXPLODED))
            _need(len(mines) == 99 and calculate_board_fingerprint(30,16,99,mines) == self.board.fingerprint,
                  "Terminal/board fingerprint mismatch.")
            _need((0,0) not in mines, "Public corpus canonical first cell must be safe.")
            _need(all(sum(v >= 0 for row in f.observation for v in row) < 381 for f in trace.frames[:-1]),
                  "PLAYING frame already has all safe cells open.")
            _need(final.logical_mines <= mines and final.explicit_flags <= mines, "Terminal M/flags contradiction.")
            if trace.outcome == "WON":
                _need(sum(v >= 0 for row in final.observation for v in row) == 381, "Incomplete WON.")
            else:
                _need(bool(_cells(final.observation, EXPLODED)), "LOST without explosion.")
            # Terminal comparison only: no hidden layout is sent to any policy.
            for y,row in enumerate(final.observation):
                for x,v in enumerate(row):
                    if v >= 0:
                        _need(v == sum((xx,yy) in mines for yy in range(max(0,y-1),min(16,y+2))
                                       for xx in range(max(0,x-1),min(30,x+2)) if (xx,yy)!=(x,y)),
                              "Terminal clue/layout mismatch.")

    @property
    def time_to_win_difference_us(self):
        return self.right.total_modeled_us-self.left.total_modeled_us if self.left.outcome == self.right.outcome == "WON" else None
