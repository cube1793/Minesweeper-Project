"""Bounded public wire for Stage4 Live; deliberately distinct from V1/K."""
from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from uuid import uuid4

POLICY_ID = "STAGE4_LIVE_SMR_V1"
SCHEMA = "stage4_live_wire_v1"
POLICIES = {"STAGE4_S": "S", "STAGE4_M": "M", "STAGE4_R": "R"}
MAX_BYTES = 128 * 1024
MAX_SEQUENCE = 8191
MAX_INPUTS = 4096
HIDDEN, FLAG = -2, -3
KINDS = {"START", "NEXT", "VALIDATE", "ACK", "PROPOSAL", "ADMITTED", "ACKED", "FINISHED", "ERROR", "HISTORY"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def fields(value, names):
    require(type(value) is dict and set(value) == set(names.split()), "STAGE4_FIELDS")
    return value


def integer(value, low=0, high=MAX_INPUTS):
    require(type(value) is int and low <= value <= high, "STAGE4_INTEGER")
    return value


def text(value, limit=128):
    require(type(value) is str and 0 < len(value) <= limit, "STAGE4_TEXT")
    return value


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def hash_id(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "STAGE4_DIGEST")
    return value


def exact(value):
    if value is None:
        return None
    require(type(value) is Fraction, "STAGE4_FRACTION")
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def fraction(value):
    if value is None:
        return None
    fields(value, "numerator denominator")
    for part in value.values():
        require(type(part) is str and len(part) <= 200 and re.fullmatch(r"-?(0|[1-9][0-9]*)", part), "STAGE4_EXACT_INTEGER")
    n, d = int(value["numerator"]), int(value["denominator"])
    require(d > 0, "STAGE4_DENOMINATOR")
    result = Fraction(n, d)
    require(result.numerator == n and result.denominator == d, "STAGE4_UNREDUCED")
    return result


def target_percent(value):
    require(type(value) is str and 0 < len(value.strip()) <= 48, "R 목표 IOE 백분율을 입력하세요.")
    value = value.strip()
    require(re.fullmatch(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value) is not None,
            "R 목표는 양의 십진 백분율이어야 합니다.")
    result = Fraction(value) / 100
    require(result > 0, "R 목표는 0보다 커야 합니다.")
    return result


@dataclass(frozen=True)
class Settings:
    mode: str = "S"
    profile: str = "indexed"
    allow_guess: bool = False
    target: Fraction | None = None

    def __post_init__(self):
        require(self.mode in ("S", "M", "R") and self.profile in ("indexed", "indexed_k100k"), "STAGE4_SETTINGS")
        require(type(self.allow_guess) is bool, "STAGE4_GUESS")
        require((self.mode == "R" and type(self.target) is Fraction and self.target > 0)
                or (self.mode != "R" and self.target is None), "STAGE4_TARGET_REQUIRED_OR_FORBIDDEN")

    def to_dict(self):
        return dict(mode=self.mode, profile=self.profile, allow_guess=self.allow_guess, target=exact(self.target))

    @classmethod
    def from_dict(cls, value):
        fields(value, "mode profile allow_guess target")
        return cls(value["mode"], value["profile"], value["allow_guess"], fraction(value["target"]))

    @property
    def identity(self):
        return digest(self.to_dict())


@dataclass(frozen=True)
class Snapshot:
    game_id: str
    owner_id: str
    run_id: str
    generation: int
    settings: Settings
    observation: tuple | None
    width: int
    height: int
    num_mines: int
    counted: int
    revision: int
    event_count: int
    ledger: str
    cursor: tuple
    entry: str = "CURRENT"
    status: str = "PLAYING"

    def __post_init__(self):
        for value in (self.game_id, self.owner_id, self.run_id):
            text(value)
        integer(self.generation, high=2**31-1)
        require(type(self.settings) is Settings, "STAGE4_TYPED_SETTINGS")
        integer(self.width, 1, 480); integer(self.height, 1, 480)
        require(self.width * self.height <= 480, "STAGE4_MAX_480_CELLS")
        integer(self.num_mines, 0, self.width*self.height-1)
        integer(self.counted); integer(self.revision); integer(self.event_count)
        require(self.counted <= self.revision and self.event_count <= self.revision, "STAGE4_PUBLIC_COUNT")
        hash_id(self.ledger)
        require(type(self.cursor) is tuple and len(self.cursor) == 2, "STAGE4_CURSOR")
        integer(self.cursor[0], 0, self.width-1); integer(self.cursor[1], 0, self.height-1)
        require(self.entry in ("CURRENT", "CANONICAL_NEW", "FIXED_BOARD"), "STAGE4_ENTRY")
        require(self.status in ("PLAYING", "WON", "LOST"), "STAGE4_STATUS")
        if self.status != "PLAYING":
            require(self.observation is None, "STAGE4_TERMINAL_MUST_NOT_LEAK_LAYOUT")
            return
        require(type(self.observation) is tuple and len(self.observation) == self.height, "STAGE4_GRID")
        for row in self.observation:
            require(type(row) is tuple and len(row) == self.width, "STAGE4_GRID")
            for v in row:
                require(type(v) is int and (v in (HIDDEN, FLAG) or 0 <= v <= 8), "STAGE4_CELL")
        if self.entry == "CANONICAL_NEW":
            require(self.counted == self.revision == self.event_count == 0
                    and all(v == HIDDEN for row in self.observation for v in row), "STAGE4_BOOTSTRAP_PROVENANCE")

    def to_dict(self):
        value = asdict(self)
        value["settings"] = self.settings.to_dict()
        value["cursor"] = list(self.cursor)
        value["observation"] = None if self.observation is None else [list(r) for r in self.observation]
        return value

    @classmethod
    def from_dict(cls, value):
        fields(value, "game_id owner_id run_id generation settings observation width height num_mines counted revision event_count ledger cursor entry status")
        args = dict(value)
        args["settings"] = Settings.from_dict(args["settings"])
        require(type(args["cursor"]) is list, "STAGE4_CURSOR")
        args["cursor"] = tuple(args["cursor"])
        grid = args["observation"]
        if grid is not None:
            require(type(grid) is list and 0 < len(grid) <= 480 and all(type(r) is list and len(r) <= 480 for r in grid), "STAGE4_GRID")
            args["observation"] = tuple(tuple(r) for r in grid)
        return cls(**args)

    @property
    def identity(self):
        return digest(self.to_dict())

    @property
    def stop_key(self):
        # Owner/generation deliberately excluded: toggling Auto cannot escape a stop.
        return digest([self.game_id, self.settings.to_dict(), self.observation, self.num_mines,
                       self.counted, self.revision, self.event_count, self.ledger, self.entry])

    def runtime_request(self):
        from stage4_runtime_model import ModelLimits
        from stage4_runtime_policy import RuntimeLimits, RuntimeRequest
        require(self.status == "PLAYING" and self.entry != "CANONICAL_NEW", "STAGE4_RUNTIME_ENTRY")
        model = (ModelLimits(samples=4, shortlist=2, rows=8, kernel_kind="indexed_k100k")
                 if self.settings.profile == "indexed_k100k" else ModelLimits())
        return RuntimeRequest(self.observation, self.num_mines, self.counted, self.settings.mode,
            self.settings.allow_guess, self.settings.target, episode_key=self.game_id,
            instance_id=self.game_id, settings_id=self.settings.identity,
            generation=self.generation, limits=RuntimeLimits(model=model))


def move_dict(move):
    return dict(action=move.action, x=move.x, y=move.y)


def validate_move(move, state):
    fields(move, "action x y")
    require(move["action"] in ("OPEN", "FLAG", "CHORD"), "STAGE4_ACTION")
    integer(move["x"], 0, state.width-1); integer(move["y"], 0, state.height-1)
    return move


def validate_projection(value, state):
    fields(value, "state_id request_id token move position source status reason is_guess desired_flag model_status attempts survival")
    require(value["state_id"] == state.identity, "STAGE4_STALE_PROJECTION")
    hash_id(value["request_id"]); hash_id(value["token"])
    integer(value["position"], 0, 480)
    for k in ("source", "status", "reason", "model_status"):
        text(value[k], 512)
    integer(value["attempts"], 0, 8)
    require(type(value["is_guess"]) is bool and value["desired_flag"] in (None, True, False), "STAGE4_PROJECTION_FLAGS")
    require(value["desired_flag"] is None or type(value["desired_flag"]) is bool, "STAGE4_DESIRED_FLAG")
    probability = fraction(value["survival"])
    require(probability is None or 0 < probability <= 1, "STAGE4_SURVIVAL")
    if value["move"] is not None:
        validate_move(value["move"], state)
        require(value["source"] in ("BOOTSTRAP", "MODEL", "PUBLIC_KERNEL", "EXACT_Q"), "STAGE4_SOURCE")
        require(not value["is_guess"] or state.settings.allow_guess, "STAGE4_GUESS_OFF")
        require((value["move"]["action"] == "FLAG") == (value["desired_flag"] is not None), "STAGE4_FLAG_INTENT")
    else:
        require(value["desired_flag"] is None and not value["is_guess"], "STAGE4_NO_MOVE_FLAGS")
    return value


def guard_target(proposal, state):
    validate_projection(proposal, state)
    require(state.status == "PLAYING" and proposal["move"] is not None, "STAGE4_NO_INPUT")
    m = proposal["move"]; x, y = m["x"], m["y"]; v = state.observation[y][x]
    if m["action"] == "FLAG":
        require(v in (HIDDEN, FLAG) and (v == FLAG) != proposal["desired_flag"], "STAGE4_FLAG_CHANGED")
    elif m["action"] == "OPEN":
        require(v == HIDDEN, "STAGE4_OPEN_CHANGED")
    else:
        adjacent = [state.observation[ny][nx] for ny in range(max(0,y-1),min(state.height,y+2))
                    for nx in range(max(0,x-1),min(state.width,x+2)) if (nx,ny)!=(x,y)]
        require(v > 0 and adjacent.count(FLAG) == v and HIDDEN in adjacent, "STAGE4_CHORD_CHANGED")


@dataclass(frozen=True)
class Acknowledgement:
    run_id: str
    token: str
    nonce: str
    before_id: str
    after: Snapshot

    @property
    def status(self):
        return self.after.status

    def to_dict(self):
        return dict(run_id=self.run_id, token=self.token, nonce=self.nonce, before_id=self.before_id, after=self.after.to_dict())

    @classmethod
    def from_dict(cls, value):
        fields(value, "run_id token nonce before_id after")
        return cls(text(value["run_id"]), hash_id(value["token"]), text(value["nonce"]),
                   hash_id(value["before_id"]), Snapshot.from_dict(value["after"]))


def validate_ack(ack, before, proposal, nonce):
    require(type(ack) is Acknowledgement and ack.run_id == before.run_id and ack.token == proposal["token"]
            and ack.nonce == nonce and ack.before_id == before.identity, "STAGE4_ACK_BINDING")
    after = ack.after
    for key in ("game_id", "owner_id", "run_id", "generation", "settings", "width", "height", "num_mines"):
        require(getattr(before,key) == getattr(after,key), "STAGE4_ACK_IDENTITY")
    require(after.counted == before.counted+1 and after.revision == before.revision+1
            and after.event_count == before.event_count+1 and after.ledger != before.ledger,
            "STAGE4_ACK_COUNTED_EVENT")
    m=proposal["move"]
    require(m["action"] != "FLAG" or after.status == "PLAYING", "STAGE4_FLAG_TERMINAL")
    require(after.cursor == (m["x"],m["y"]) and after.entry != "CANONICAL_NEW", "STAGE4_ACK_CURSOR")
    if after.status == "PLAYING":
        for y in range(before.height):
            for x in range(before.width):
                a,b=before.observation[y][x],after.observation[y][x]
                if m["action"] == "FLAG":
                    expected = (HIDDEN if a==FLAG else FLAG) if (x,y)==after.cursor else a
                    require(b==expected, "STAGE4_ACK_FLAG")
                else:
                    require((a>=0 and a==b) or (a==FLAG and b==FLAG) or (a==HIDDEN and (b==HIDDEN or b>=0)), "STAGE4_ACK_REVEAL")
        if m["action"] == "OPEN":
            require(after.observation[m["y"]][m["x"]]>=0, "STAGE4_ACK_OPEN")
    return after


def envelope(run_id, seq, kind, payload):
    return validate_message(dict(schema=SCHEMA, policy_id=POLICY_ID, run_id=run_id, seq=seq, kind=kind, payload=payload))


def validate_message(value, run_id=None, seq=None):
    fields(value, "schema policy_id run_id seq kind payload")
    require(value["schema"]==SCHEMA and value["policy_id"]==POLICY_ID, "STAGE4_SCHEMA")
    text(value["run_id"]); integer(value["seq"],0,MAX_SEQUENCE)
    require(type(value["kind"]) is str and value["kind"] in KINDS and type(value["payload"]) is dict, "STAGE4_MESSAGE")
    require(run_id is None or value["run_id"]==run_id, "STAGE4_WRONG_RUN")
    require(seq is None or value["seq"]==seq, "STAGE4_WRONG_SEQUENCE")
    return value


def _unique(items):
    result={}
    for key,value in items:
        require(key not in result, "STAGE4_DUPLICATE_KEY")
        result[key]=value
    return result


def _constant(value):
    raise ValueError("STAGE4_NONFINITE:"+value)


def channel_path(directory, direction, seq):
    require(direction in ("parent", "worker", "history"), "STAGE4_DIRECTION")
    integer(seq,0,MAX_SEQUENCE)
    p=Path(directory)
    require(p.is_dir() and not p.is_symlink(), "STAGE4_CHANNEL")
    return p / f"s4-{direction}-{seq:08d}.json"


def write_once(directory, direction, seq, value):
    validate_message(value,seq=seq)
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("ascii")
    require(0<len(raw)<=MAX_BYTES, "STAGE4_MESSAGE_SIZE")
    dest=channel_path(directory,direction,seq)
    temporary=dest.with_name(f".{dest.name}.{uuid4().hex}.part")
    published=False
    try:
        with temporary.open("xb") as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,dest)
        published=True
    finally:
        if not published:
            temporary.unlink(missing_ok=True)


def read_next(directory,direction,seq,run_id):
    path=channel_path(directory,direction,seq)
    if not path.exists():
        pattern=re.compile(rf"s4-{direction}-([0-9]{{8}})\.json\Z")
        for p in path.parent.glob(f"s4-{direction}-*.json"):
            match=pattern.fullmatch(p.name)
            require(match is not None and int(match[1])<=seq, "STAGE4_FUTURE_MESSAGE")
        return None
    require(path.is_file() and not path.is_symlink(), "STAGE4_MESSAGE_PATH")
    with path.open("rb") as stream:
        raw=stream.read(MAX_BYTES+1)
    require(0<len(raw)<=MAX_BYTES, "STAGE4_MESSAGE_SIZE")
    return validate_message(json.loads(raw.decode("utf-8"),object_pairs_hook=_unique,parse_constant=_constant),run_id,seq)
