"""Versioned JSON only for user files; private worker pickle lives elsewhere."""

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

from experiments.k_lc0_exhibition_model import (
    ComparePair, CompareSource, CompareTrace, PlanNote, ChoiceNote,
    SCHEMA, VERSION, POLICIES, valid_run_id, valid_time,
)
from experiments.random_expert_exhibition_model import ExhibitionAction, ExhibitionFrame, ExhibitionBoard, validate_index, _need

DEFAULT_RUNS = Path(r"C:\Projects\GraduationProject\K_LC0_RANDOM_EXPERT_COMPARE_RUNS")
MAX_JSON_BYTES = 16 * 1024 * 1024


def now(): return datetime.now(timezone.utc).isoformat()


def plain(value):
    if is_dataclass(value): return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if type(value) is dict: return {k: plain(v) for k,v in value.items()}
    if type(value) is frozenset: return [plain(v) for v in sorted(value, key=lambda p: (p[1],p[0]))]
    if type(value) in (tuple, list): return [plain(v) for v in value]
    return value


def canonical(value):
    return json.dumps(plain(value), ensure_ascii=False, sort_keys=True, separators=(",",":"), allow_nan=False).encode("utf-8")


def publish_json(path, value):
    """Publish an owned new file, atomically and without replacing any file."""
    path = Path(path)
    temporary = path.parent / (".new_" + uuid4().hex + ".json")
    try:
        with temporary.open("xb") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # exclusive destination; atomic complete-file publication
    finally:
        temporary.unlink(missing_ok=True)  # exact owned file, never recursive


def make_request(root, index, kind="index"):
    validate_index(index)
    _need(kind in ("index", "draw"), "Invalid request kind.")
    value = dict(schema=SCHEMA, version=VERSION, run_id=uuid4().hex, index=index,
                 requested_at=now(), request_kind=kind, policies=list(POLICIES))
    directory = Path(root).resolve() / value["run_id"]
    directory.mkdir(parents=True, exist_ok=False)
    publish_json(directory / "request.json", value)  # before child/algorithm starts
    return value, directory


def validate_request(value):
    _need(type(value) is dict and set(value) == {"schema","version","run_id","index","requested_at","request_kind","policies"},
          "Invalid request envelope.")
    _need(value["schema"] == SCHEMA and type(value["version"]) is int and value["version"] == VERSION
          and value["policies"] == list(POLICIES) and value["request_kind"] in ("index","draw"), "Wrong request identity.")
    validate_index(value["index"])
    valid_run_id(value["run_id"])
    valid_time(value["requested_at"])


def document(pair):
    _need(type(pair) is ComparePair, "Expected completed ComparePair.")
    pair.__post_init__()
    payload = dict(schema=SCHEMA, version=VERSION, complete=True, pair=plain(pair))
    return {**payload, "sha256": sha256(canonical(payload)).hexdigest()}


def save_pair(directory, pair):
    directory = Path(directory).resolve()
    _need(directory.name == pair.run_id, "Save directory/run ID mismatch.")
    request = read_json(directory / "request.json")
    validate_request(request)
    bind_request(pair, request)
    path = directory / "pair.json"
    publish_json(path, document(pair))
    _need(load_pair(path) == pair, "Saved JSON round-trip mismatch.")
    return path


def bind_request(pair, request):
    _need(pair.run_id == request["run_id"] and pair.board.index == request["index"]
          and pair.requested_at == request["requested_at"] and pair.request_kind == request["request_kind"]
          and (pair.left.policy_id, pair.right.policy_id) == tuple(request["policies"]), "Pair/request identity mismatch.")


def _object(items):
    value = {}
    for key, item in items:
        _need(key not in value, "Duplicate JSON key.")
        value[key] = item
    return value


def read_json(path):
    path = Path(path)
    _need(path.suffix.lower() == ".json", "JSON files only; pickle import is forbidden.")
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    _need(len(raw) <= MAX_JSON_BYTES, "JSON exceeds size limit.")
    def reject_constant(value): raise ValueError("Non-finite JSON number: " + value)
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=reject_constant)


def _fields(value, cls):
    _need(type(value) is dict and set(value) == {f.name for f in fields(cls)}, "Invalid " + cls.__name__ + " fields.")
    return dict(value)


def _tuple(value, limit=481):
    _need(type(value) is list and len(value) <= limit, "Invalid JSON list.")
    return tuple(value)


def _coords(value):
    rows = tuple(_tuple(v, 2) for v in _tuple(value, 480))
    _need(all(len(v) == 2 and all(type(n) is int for n in v) for v in rows)
          and len(set(rows)) == len(rows), "Invalid/duplicate coordinate set.")
    return frozenset(rows)


def _plan(value):
    if value is None: return None
    d = _fields(value, PlanNote)
    d["actions"] = tuple(_tuple(v,3) for v in _tuple(d["actions"],9))
    return PlanNote(**d)


def _trace(value):
    d = _fields(value, CompareTrace)
    actions, frames, choices = [], [], []
    for item in _tuple(d["actions"],480):
        a = _fields(item, ExhibitionAction)
        for key in ("target","cursor_before"): a[key] = _tuple(a[key],2)
        for key in ("M_before","preinput_M"): a[key] = _coords(a[key])
        actions.append(ExhibitionAction(**a))
    for item in _tuple(d["frames"]):
        f = _fields(item, ExhibitionFrame)
        f["observation"] = tuple(_tuple(row,30) for row in _tuple(f["observation"],16))
        f["cursor"] = _tuple(f["cursor"],2)
        for key in ("logical_mines","explicit_flags","automatic_flags"): f[key] = _coords(f[key])
        frames.append(ExhibitionFrame(**f))
    for item in _tuple(d["choices"],480):
        c = _fields(item, ChoiceNote)
        for key in ("g_move","selected_move"): c[key] = _tuple(c[key],3)
        for key in ("g","selected"): c[key] = _plan(c[key])
        choices.append(ChoiceNote(**c))
    return CompareTrace(d["policy_id"],d["policy_definition"],tuple(actions),tuple(frames),tuple(choices))


def parse_document(value):
    _need(type(value) is dict and set(value) == {"schema","version","complete","pair","sha256"}, "Invalid document envelope.")
    _need(value["schema"] == SCHEMA and type(value["version"]) is int and value["version"] == VERSION
          and value["complete"] is True, "Unsupported/incomplete JSON.")
    payload = {k:v for k,v in value.items() if k != "sha256"}
    _need(type(value["sha256"]) is str and sha256(canonical(payload)).hexdigest() == value["sha256"], "JSON checksum mismatch.")
    d = _fields(value["pair"],ComparePair)
    d["board"] = ExhibitionBoard(**_fields(d["board"],ExhibitionBoard))
    s = _fields(d["source"],CompareSource)
    s["files"] = tuple(_tuple(v,2) for v in _tuple(s["files"],500))
    d["source"] = CompareSource(**s)
    d["timing_table"] = tuple(_tuple(row,16) for row in _tuple(d["timing_table"],30))
    d["left"],d["right"] = _trace(d["left"]),_trace(d["right"])
    return ComparePair(**d)


def load_pair(path):
    try:
        return parse_document(read_json(path))
    except (TypeError, KeyError, IndexError, OverflowError, RecursionError) as exc:
        raise ValueError("Malformed comparison JSON: " + str(exc)) from exc
