"""Bounded, strict JSON messages published once per direction/sequence."""

import json
import os
from pathlib import Path
import re
from uuid import uuid4

from live_policy import LivePolicyError, MAX_INPUTS, _identity, _integer, _require
from live_k_policy import MAX_K_SEQUENCE, MAX_FLAG_ADOPT_SEQUENCE


PROTOCOL_VERSION = 8
MAX_MESSAGE_BYTES = 2 * 1024 * 1024
# At most 480 preparation toggles plus 480 normal V1 inputs per owner.
# This bound is independent of global game revision and board overlay size.
# K: <=480 actual inputs, <=64 VALIDATE round trips per pending input,
# plus START/NEXT and ACK. The worker enforces the per-input limit as well.
MAX_V1_SEQUENCE = 2 * MAX_INPUTS + 1
# FLAG_ADOPT adds <=480 preparation inputs and one bootstrap transition.
# Endpoints retain the narrower bound of each entry mode.
MAX_SEQUENCE = max(MAX_V1_SEQUENCE, MAX_K_SEQUENCE, MAX_FLAG_ADOPT_SEQUENCE)
KINDS = frozenset({"START", "BOOTSTRAPPED", "NEXT", "VALIDATE", "ADMITTED", "ACK", "PROPOSAL", "ACKED", "FINISHED", "ERROR"})


def validate_message(value, *, run_id=None, seq=None):
    _require(type(value) is dict and set(value) == {"version", "run_id", "seq", "kind", "payload"},
             "Invalid transport envelope fields.")
    _require(type(value["version"]) is int and value["version"] == PROTOCOL_VERSION,
             "Invalid transport version.")
    _require(_identity(value["run_id"]), "Invalid transport run identity.")
    _require(_integer(value["seq"], 0, MAX_SEQUENCE), "Invalid transport sequence.")
    _require(type(value["kind"]) is str and value["kind"] in KINDS, "Invalid message kind.")
    _require(type(value["payload"]) is dict, "Message payload must be an object.")
    if run_id is not None:
        _require(type(run_id) is str and value["run_id"] == run_id, "Wrong transport run identity.")
    if seq is not None:
        _require(type(seq) is int and value["seq"] == seq, "Out-of-order transport sequence.")
    return value


def message(run_id, seq, kind, payload):
    return validate_message({"version": PROTOCOL_VERSION, "run_id": run_id, "seq": seq,
                             "kind": kind, "payload": payload})


def _path(directory, direction, seq):
    _require(type(direction) is str and direction in ("parent", "worker"), "Invalid channel direction.")
    _require(_integer(seq, 0, MAX_SEQUENCE), "Invalid channel sequence.")
    directory = Path(directory)
    _require(directory.is_dir() and not directory.is_symlink(), "Missing or unsafe private channel directory.")
    return directory / f"{direction}-{seq:08d}.json"


def write_once(directory, direction, seq, envelope):
    """Publish a closed file atomically without replacing any existing message."""
    validate_message(envelope, seq=seq)
    path = _path(directory, direction, seq)
    encoded = json.dumps(envelope, ensure_ascii=True, allow_nan=False,
                         sort_keys=True, separators=(",", ":")).encode("ascii")
    _require(0 < len(encoded) <= MAX_MESSAGE_BYTES, "Transport message exceeds length limit.")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.part")
    published = False
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory hard-link publication is atomic and fails if destination
        # exists. Readers never hold a target that a subsequent write replaces.
        os.link(temporary, path)
        published = True
    finally:
        # Keep published staging links until owner cleanup as a conservative
        # lifetime choice. The reviewed NTFS share-mode checks did not find
        # that a reader of the final link blocks deleting the staging link.
        if not published:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
    return path


def _unique_object(items):
    result = {}
    for name, value in items:
        if name in result:
            raise LivePolicyError("Duplicate JSON object key.")
        result[name] = value
    return result


def _invalid_constant(value):
    raise LivePolicyError(f"Non-finite JSON constant: {value}.")


def read_next(directory, direction, seq, run_id):
    path = _path(directory, direction, seq)
    if not path.exists():
        pattern = re.compile(rf"{direction}-([0-9]{{8}})\.json\Z")
        for candidate in path.parent.glob(f"{direction}-*.json"):
            match = pattern.fullmatch(candidate.name)
            _require(match is not None, "Malformed channel filename.")
            _require(int(match.group(1)) <= seq, "Future message arrived before its predecessor.")
        return None
    _require(path.is_file() and not path.is_symlink(), "Unsafe channel message path.")
    with path.open("rb") as stream:
        raw = stream.read(MAX_MESSAGE_BYTES + 1)
    _require(0 < len(raw) <= MAX_MESSAGE_BYTES, "Transport message exceeds length limit.")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise LivePolicyError(f"Invalid transport JSON: {exc}") from exc
    return validate_message(value, run_id=run_id, seq=seq)
