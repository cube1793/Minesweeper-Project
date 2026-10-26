"""E2 I2 append-only transport for caller-supplied I1 records.

Each stream line is canonical-key JSON + TAB + canonical-record JSON + LF.
Writers are single-owner objects. Append is not a durability claim: only a
successful flush/fsync checkpoint identifies a durable prefix. No capture,
semantic extraction, resume, repair, aggregation or research verdict lives here.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat

from experiments import program_k_e2_records as records
from experiments import program_k_e2_physical as physical


_UINT64_MAX = (1 << 64) - 1
_RECEIPT_NAME = "COMPLETE.json"


class StoreError(ValueError):
    """Invalid storage input, failed I/O, or corrupt/noncanonical evidence."""


def _need(condition, detail):
    if not condition:
        raise StoreError(detail)


def _uint64(value):
    _need(type(value) is int and 0 <= value <= _UINT64_MAX, "Expected exact uint64.")


def _stream_name(value):
    _need(type(value) is str and 1 <= len(value) <= 64, "Invalid stream name type/length.")
    _need("a" <= value[0] <= "z"
          and all("a" <= c <= "z" or "0" <= c <= "9" or c in "_-" for c in value),
          "Stream name must be lowercase ASCII [a-z][a-z0-9_-]*.")
    return value


def _key(value):
    _need(type(value) is tuple and bool(value), "Key must be a nonempty exact tuple.")
    for component in value:
        _uint64(component)
    return value


def _key_bytes(key):
    _key(key)
    return json.dumps(key, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _no_float(value):
    raise StoreError("Floating-point/nonfinite logical key is forbidden.")


def _decode_key(data):
    try:
        value = json.loads(data.decode("ascii", errors="strict"), parse_float=_no_float, parse_constant=_no_float)
        _need(type(value) is list, "Key JSON must be an array.")
        key = _key(tuple(value))
        _need(_key_bytes(key) == data, "Noncanonical key JSON.")
        return key
    except StoreError:
        raise
    except (ValueError, TypeError, RecursionError) as error:
        raise StoreError("Malformed logical key.") from error


def _encode_record(record):
    try:
        return records.encode(record)
    except (ValueError, TypeError, AttributeError, RecursionError, OverflowError) as error:
        raise StoreError("Invalid I1 record.") from error


def _decode_record(data):
    try:
        return records.decode(data)
    except records.RecordError as error:
        raise StoreError("Invalid canonical I1 record bytes.") from error


def _root(root):
    try:
        path = Path(root).resolve(strict=True)
        _need(path.is_dir(), "Store root must already be a directory.")
        return path
    except StoreError:
        raise
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        raise StoreError("Invalid/missing store root.") from error


def _stream_path(root, name):
    _stream_name(name)  # validate before deriving a filename or touching the root
    filename = name + ".jsonl"
    _need(not Path(filename).is_reserved(), "Reserved device filename is not a stream.")
    return _root(root) / filename


def _exclusive(path):
    try:
        # O_EXCL creation rejects existing files, directories and dangling links.
        # Unbuffered binary writes make the reported write length explicit.
        return path.open("xb", buffering=0)
    except (OSError, ValueError) as error:
        raise StoreError("Exclusive creation failed; no overwrite or resume is allowed.") from error


def _write_complete(file, data):
    written = file.write(data)
    _need(type(written) is int and written == len(data), "Short/indeterminate write; no retry.")


def _close_best_effort(file):
    try:
        file.close()
    except Exception:
        pass


@dataclass(frozen=True, slots=True)
class DurableCheckpoint:
    stream_name: str
    sha256: str
    byte_length: int
    record_count: int
    last_key: tuple | None

    def __post_init__(self):
        _stream_name(self.stream_name)
        _need(type(self.sha256) is str and len(self.sha256) == 64
              and all(c in "0123456789abcdef" for c in self.sha256), "Invalid SHA-256.")
        _uint64(self.byte_length)
        _uint64(self.record_count)
        if self.record_count == 0:
            _need(self.byte_length == 0 and self.last_key is None, "Invalid empty checkpoint.")
        else:
            _need(self.byte_length > 0, "Nonempty checkpoint needs bytes.")
            _key(self.last_key)


class StreamWriter:
    """Exclusive, incremental stream writer; close/context exit never implies seal."""

    __slots__ = ("_stream_name", "_path", "_file", "_hash", "_record_count", "_byte_length",
                 "_last_key", "_sealed", "_poisoned", "_closed", "_last_durable_checkpoint")

    def __init__(self, root, stream_name):
        self._path = _stream_path(root, stream_name)
        self._stream_name = stream_name
        self._hash = hashlib.sha256()
        self._record_count = 0
        self._byte_length = 0
        self._last_key = None
        self._sealed = False
        self._poisoned = False
        self._closed = False
        self._last_durable_checkpoint = None
        self._file = _exclusive(self._path)

    @property
    def stream_name(self):
        return self._stream_name

    @property
    def path(self):
        return self._path

    @property
    def record_count(self):
        return self._record_count

    @property
    def byte_length(self):
        return self._byte_length

    @property
    def last_key(self):
        return self._last_key

    @property
    def sealed(self):
        return self._sealed

    @property
    def poisoned(self):
        return self._poisoned

    @property
    def last_durable_checkpoint(self):
        return self._last_durable_checkpoint

    def _writable(self):
        _need(not (self._poisoned or self._sealed or self._closed), "Writer is poisoned, sealed or closed.")

    def _poison(self, error, operation):
        self._poisoned = True
        if isinstance(error, Exception):
            raise StoreError("Stream " + operation + " failed; writer poisoned.") from error
        raise error  # preserve cancellation/SystemExit while forbidding later success

    def append(self, key, record):
        self._writable()
        encoded_key = _key_bytes(key)
        _need(self._last_key is None or key > self._last_key, "Duplicate/descending logical key.")
        line = encoded_key + b"\t" + _encode_record(record) + b"\n"
        next_bytes, next_count = self._byte_length + len(line), self._record_count + 1
        _uint64(next_bytes)
        _uint64(next_count)
        try:
            _write_complete(self._file, line)
            self._hash.update(line)
        except BaseException as error:
            self._poison(error, "append")
        self._byte_length, self._record_count, self._last_key = next_bytes, next_count, key

    def checkpoint(self):
        self._writable()
        try:
            self._file.flush()
            os.fsync(self._file.fileno())
            snapshot = DurableCheckpoint(self._stream_name, self._hash.hexdigest(),
                                         self._byte_length, self._record_count, self._last_key)
        except BaseException as error:
            self._poison(error, "checkpoint")
        self._last_durable_checkpoint = snapshot
        return snapshot

    def seal(self):
        self._writable()
        snapshot = self.checkpoint()
        try:
            self._file.close()
        except BaseException as error:
            self._poison(error, "seal close")
        self._closed = True
        self._sealed = True
        return records.StreamDigest(snapshot.stream_name, snapshot.sha256, snapshot.byte_length, snapshot.record_count)

    def close(self):
        """Best-effort resource release, never a checkpoint or completion claim."""
        if not self._closed:
            try:
                self._file.close()
            except Exception:
                self._poisoned = True
            finally:
                self._closed = True

    def __enter__(self):
        self._writable()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def _framed_context(stream_name, context):
    _stream_name(stream_name)
    _need(type(context) is physical.FrameContext, "Expected exact FrameContext.")
    try:
        physical.FrameContext.__post_init__(context)
        _need(context.stream_name == stream_name, "Stream/context name mismatch.")
        # Own an immutable binding rather than retaining caller-owned context state.
        return physical.context_for(stream_name, context.codec_profile_sha256)
    except physical.PhysicalError as error:
        raise StoreError("Invalid RF02 frame context.") from error


def _framed_limit(value):
    _need(type(value) is int and 0 < value <= physical.MAX_PAYLOAD_BYTES,
          "Expected positive bounded RF02 payload limit.")
    return value


def _framed_path(root, stream_name):
    _stream_name(stream_name)
    filename = stream_name + ".pkf"
    _need(not Path(filename).is_reserved(), "Reserved device filename is not a stream.")
    return _root(root) / filename


class FramedStreamWriter(StreamWriter):
    """Explicit RF02 writer with dirty checkpoints; no operational format switch.

    Append accepts exact logical record objects. The additive append_frame seam
    independently validates supplied RF02 bytes before persisting them exactly.
    State checks, poison, seal and close use the historical writer's mechanics;
    its JSONL constructor, append and checkpoint behavior remain unchanged.
    """

    __slots__ = ("_context", "_max_payload_bytes", "_dirty")

    def __init__(self, root, stream_name, context, *, max_payload_bytes=physical.MAX_PAYLOAD_BYTES):
        self._context = _framed_context(stream_name, context)
        self._max_payload_bytes = _framed_limit(max_payload_bytes)
        self._path = _framed_path(root, stream_name)
        self._stream_name = stream_name
        self._hash = hashlib.sha256()
        self._record_count = 0
        self._byte_length = 0
        self._last_key = None
        self._sealed = False
        self._poisoned = False
        self._closed = False
        self._last_durable_checkpoint = None
        self._dirty = False
        self._file = _exclusive(self._path)

    @property
    def dirty(self):
        return self._dirty

    def append(self, key, record):
        self._writable()
        context = _framed_context(self._stream_name, self._context)
        limit = _framed_limit(self._max_payload_bytes)
        _key(key)
        _need(len(key) == context.expected_key_arity, "RF02 key arity mismatch.")
        _need(self._last_key is None or key > self._last_key, "Duplicate/descending logical key.")
        _need(type(record) in context.allowed_logical_record_types, "Wrong RF02 logical record family.")
        logical = _encode_record(record)
        _need(len(logical) <= limit, "RF02 logical payload cap exceeded.")
        try:
            frame = physical.encode_frame(logical, key, context, max_payload_bytes=limit)
        except physical.PhysicalError as error:
            raise StoreError("Invalid RF02 record/frame.") from error
        _need(type(frame) is bytes and 0 < len(frame) <= limit + 13 + 10 * context.expected_key_arity,
              "RF02 physical frame cap exceeded.")
        next_bytes, next_count = self._byte_length + len(frame), self._record_count + 1
        _uint64(next_bytes)
        _uint64(next_count)
        try:
            _write_complete(self._file, frame)
            self._hash.update(frame)
        except BaseException as error:
            self._poison(error, "append")
        self._byte_length, self._record_count, self._last_key = next_bytes, next_count, key
        self._dirty = True

    def append_frame(self, key, logical_bytes, frame_bytes):
        """Validate this frame anew; neither supplied bytes nor context grant trust."""
        self._writable()
        context = _framed_context(self._stream_name, self._context)
        limit = _framed_limit(self._max_payload_bytes)
        _key(key)
        _need(len(key) == context.expected_key_arity, "RF02 key arity mismatch.")
        _need(self._last_key is None or key > self._last_key, "Duplicate/descending logical key.")
        _need(type(logical_bytes) is bytes and len(logical_bytes) <= limit,
              "Expected immutable bounded RF02 logical bytes.")
        _need(type(frame_bytes) is bytes
              and 0 < len(frame_bytes) <= limit + 13 + 10 * context.expected_key_arity,
              "Expected immutable bounded RF02 frame bytes.")
        try:
            decoded = physical.decode_frame(frame_bytes, context, expected_key=key,
                                            max_payload_bytes=limit)
        except physical.PhysicalError as error:
            raise StoreError("Invalid supplied RF02 frame.") from error
        _need(decoded.logical_bytes == logical_bytes, "RF02 supplied logical bytes mismatch.")
        next_bytes, next_count = self._byte_length + len(frame_bytes), self._record_count + 1
        _uint64(next_bytes)
        _uint64(next_count)
        try:
            _write_complete(self._file, frame_bytes)
            self._hash.update(frame_bytes)
        except BaseException as error:
            self._poison(error, "append frame")
        self._byte_length, self._record_count, self._last_key = next_bytes, next_count, key
        self._dirty = True

    def checkpoint(self):
        self._writable()
        if not self._dirty and self._last_durable_checkpoint is not None:
            return self._last_durable_checkpoint
        snapshot = super().checkpoint()
        self._dirty = False
        return snapshot


@contextmanager
def _reader(path):
    try:
        info = path.lstat()
        _need(stat.S_ISREG(info.st_mode)
              and not (getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
              "Read target must be a regular file, not a symlink/reparse point.")
        file = path.open("rb")
    except (OSError, ValueError) as error:
        raise StoreError("Cannot open evidence file read-only.") from error
    try:
        yield file
    except BaseException:
        _close_best_effort(file)
        raise  # in particular, never wrap a visitor's exception
    else:
        try:
            file.close()
        except (OSError, ValueError) as error:
            raise StoreError("Read-only close failed.") from error


def _readline(file):
    try:
        return file.readline()
    except (OSError, ValueError) as error:
        raise StoreError("Sequential evidence read failed.") from error


def scan_stream(root, stream_name, *, visit=None):
    """Validate once sequentially; retain only the current record and previous key.

    Returns integrity of the observed bytes, not an effectiveness/semantic verdict.
    A visitor exception propagates unchanged and prevents a completed scan result.
    """
    path = _stream_path(root, stream_name)
    _need(visit is None or callable(visit), "Visitor must be callable or None.")
    digest = hashlib.sha256()
    byte_length = record_count = 0
    last_key = None
    with _reader(path) as file:
        while True:
            line = _readline(file)
            if line == b"":
                break
            _need(line.endswith(b"\n") and line.count(b"\t") == 1, "Truncated/malformed stream line.")
            key_bytes, record_bytes = line[:-1].split(b"\t")
            key = _decode_key(key_bytes)
            _need(last_key is None or key > last_key, "Duplicate/descending stream key.")
            record = _decode_record(record_bytes)
            byte_length += len(line)
            record_count += 1
            _uint64(byte_length)
            _uint64(record_count)
            digest.update(line)
            last_key = key
            if visit is not None:
                visit(key, record)
    return records.StreamDigest(stream_name, digest.hexdigest(), byte_length, record_count)


def _read_framed_component(file, size, *, boundary=False):
    data = bytearray()
    while len(data) < size:
        remaining = size - len(data)
        try:
            chunk = file.read(remaining)
        except (OSError, ValueError) as error:
            raise StoreError("Sequential RF02 evidence read failed.") from error
        _need(type(chunk) is bytes and len(chunk) <= remaining, "Indeterminate RF02 read.")
        if not chunk:
            _need(boundary and not data, "Truncated RF02 frame component.")
            return b""
        data.extend(chunk)
    return bytes(data)


def _read_framed_frame(file, context, limit):
    prefix = _read_framed_component(file, 9, boundary=True)
    if not prefix:
        return None
    logical_length = int.from_bytes(prefix[1:5], "big")
    payload_length = int.from_bytes(prefix[5:9], "big")
    _need(logical_length <= limit and payload_length <= limit, "RF02 declared payload cap exceeded.")
    encoded_key = bytearray()
    for _ in range(context.expected_key_arity):
        component = bytearray()
        for _ in range(10):
            byte = _read_framed_component(file, 1)
            component.extend(byte)
            if byte[0] < 128:
                break
        # Use the representation authority for minimality, termination and uint64.
        try:
            physical.decode_uleb128(bytes(component))
        except physical.PhysicalError as error:
            raise StoreError("Malformed RF02 key component.") from error
        encoded_key.extend(component)
    payload_and_crc = _read_framed_component(file, payload_length + 4)
    return prefix + bytes(encoded_key) + payload_and_crc


def scan_framed_stream(root, stream_name, context, *, max_payload_bytes=physical.MAX_PAYLOAD_BYTES,
                       visit=None):
    """Scan only .pkf, bounded to one frame; supplied context selects the format.

    visit(key, record, canonical_logical_bytes, physical_frame_length) observes
    facts at this validation boundary, without a transferable validation token.
    """
    context = _framed_context(stream_name, context)
    limit = _framed_limit(max_payload_bytes)
    _need(visit is None or callable(visit), "Visitor must be callable or None.")
    path = _framed_path(root, stream_name)
    digest = hashlib.sha256()
    byte_length = record_count = 0
    last_key = None
    with _reader(path) as file:
        while True:
            data = _read_framed_frame(file, context, limit)
            if data is None:
                break
            try:
                frame = physical.decode_frame(data, context, max_payload_bytes=limit)
            except physical.PhysicalError as error:
                raise StoreError("Invalid RF02 evidence frame.") from error
            _need(last_key is None or frame.key > last_key, "Duplicate/descending stream key.")
            byte_length += len(data)
            record_count += 1
            _uint64(byte_length)
            _uint64(record_count)
            digest.update(data)
            last_key = frame.key
            if visit is not None:
                visit(frame.key, _decode_record(frame.logical_bytes), frame.logical_bytes, frame.frame_length)
            del data, frame
    return records.StreamDigest(stream_name, digest.hexdigest(), byte_length, record_count)


@dataclass(frozen=True, slots=True)
class FramedStreamRow:
    """One current row observed after full RF02 validation, never a trust token."""

    key: tuple
    record: object
    logical_bytes: bytes
    frame_length: int


def _read_pull_remainder(file, size):
    """Read one frame remainder within the pull reader's 64 KiB I/O bound."""
    data = bytearray()
    while len(data) < size:
        request_size = min(size - len(data), 65536)
        try:
            chunk = file.read(request_size)
        except (OSError, ValueError) as error:
            raise StoreError("Sequential RF02 evidence read failed.") from error
        _need(type(chunk) is bytes and len(chunk) <= request_size, "Indeterminate RF02 read.")
        _need(bool(chunk), "Truncated RF02 frame component.")
        data.extend(chunk)
    return bytes(data)


class FramedStreamPullReader:
    """Demand-driven RF02 input with only an unauthenticated pending prefix.

    Opening and peeking do not decode or inflate a record. The caller consumes
    each returned current row before choosing another stream to pull. Only an
    observed EOF followed by successful close publishes a detached digest;
    outer semantic/user failures must invalidate every opened reader.
    """

    __slots__ = ("_stream_name", "_context", "_max_payload_bytes", "_file", "_hash",
                 "_byte_length", "_record_count", "_last_key", "_pending_prefix",
                 "_pending_key", "_eof", "_closed", "_poisoned", "_completed_digest")

    def __init__(self, root, stream_name, context, *, max_payload_bytes=physical.MAX_PAYLOAD_BYTES):
        self._context = _framed_context(stream_name, context)
        self._max_payload_bytes = _framed_limit(max_payload_bytes)
        path = _framed_path(root, stream_name)
        self._stream_name = stream_name
        self._hash = hashlib.sha256()
        self._byte_length = self._record_count = 0
        self._last_key = self._pending_key = None
        self._pending_prefix = b""
        self._eof = self._closed = self._poisoned = False
        self._completed_digest = None
        try:
            info = path.lstat()
            _need(stat.S_ISREG(info.st_mode)
                  and not (getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
                  "Read target must be a regular file, not a symlink/reparse point.")
            # No hidden buffered read-ahead beyond the reserved pending prefix.
            self._file = path.open("rb", buffering=0)
        except (OSError, ValueError) as error:
            raise StoreError("Cannot open RF02 evidence file read-only.") from error

    @property
    def completed_digest(self):
        return self._completed_digest

    def _readable(self):
        _need(not (self._closed or self._poisoned), "RF02 reader is closed or invalidated.")

    def peek_key(self):
        """Return an unauthenticated scheduling hint, not evidence of this row."""
        self._readable()
        if self._eof:
            return None
        if self._pending_key is not None:
            return self._pending_key
        try:
            prefix = _read_framed_component(self._file, 9, boundary=True)
            if not prefix:
                self._eof = True
                return None
            logical_length = int.from_bytes(prefix[1:5], "big")
            payload_length = int.from_bytes(prefix[5:9], "big")
            _need(logical_length <= self._max_payload_bytes and payload_length <= self._max_payload_bytes,
                  "RF02 declared payload cap exceeded.")
            encoded_key, values = bytearray(), []
            for _ in range(self._context.expected_key_arity):
                component = bytearray()
                for _ in range(10):
                    byte = _read_framed_component(self._file, 1)
                    component.extend(byte)
                    if byte[0] < 128:
                        break
                try:
                    value, _ = physical.decode_uleb128(bytes(component))
                except physical.PhysicalError as error:
                    raise StoreError("Malformed RF02 pending key component.") from error
                encoded_key.extend(component)
                values.append(value)
            self._pending_prefix = prefix + bytes(encoded_key)
            _need(len(self._pending_prefix) <= 39, "RF02 pending prefix reservation exceeded.")
            self._pending_key = tuple(values)
            return self._pending_key
        except BaseException:
            self.invalidate()
            raise

    def pull(self):
        """Validate and return exactly one row; never prefetch the next prefix."""
        self._readable()
        try:
            key = self.peek_key()
            if key is None:
                return None
            payload_length = int.from_bytes(self._pending_prefix[5:9], "big")
            data = self._pending_prefix + _read_pull_remainder(self._file, payload_length + 4)
            try:
                frame = physical.decode_frame(data, self._context, expected_key=key,
                                              max_payload_bytes=self._max_payload_bytes)
            except physical.PhysicalError as error:
                raise StoreError("Invalid RF02 evidence frame.") from error
            record = _decode_record(frame.logical_bytes)
            _need(self._last_key is None or frame.key > self._last_key, "Duplicate/descending stream key.")
            next_bytes, next_count = self._byte_length + len(data), self._record_count + 1
            _uint64(next_bytes)
            _uint64(next_count)
            row = FramedStreamRow(frame.key, record, frame.logical_bytes, frame.frame_length)
            self._hash.update(data)
            self._byte_length, self._record_count, self._last_key = next_bytes, next_count, frame.key
            self._pending_prefix, self._pending_key = b"", None
            del data, frame
            return row
        except BaseException:
            self.invalidate()
            raise

    def close(self):
        """Close once; only a completely validated EOF can yield a digest."""
        if self._closed:
            return self._completed_digest
        self._closed = True
        self._pending_prefix, self._pending_key = b"", None
        try:
            self._file.close()
            if self._eof and not self._poisoned:
                self._completed_digest = records.StreamDigest(self._stream_name, self._hash.hexdigest(),
                                                              self._byte_length, self._record_count)
        except BaseException as error:
            self._poisoned = True
            self._completed_digest = None
            if isinstance(error, Exception):
                raise StoreError("RF02 read-only close/completion failed.") from error
            raise
        return self._completed_digest

    def invalidate(self):
        """Discard success, including after EOF/close, and preserve outer errors."""
        self._poisoned = True
        self._completed_digest = None
        self._pending_prefix, self._pending_key = b"", None
        if not self._closed:
            self._closed = True
            try:
                self._file.close()
            except BaseException:
                pass

    def __enter__(self):
        self._readable()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.close()
        else:
            self.invalidate()
        return False


def write_completion_receipt(root, receipt):
    """Persist exactly the supplied receipt; successful return follows flush/fsync.

    Failure leaves the created file untouched, possibly partial. Its mere presence
    is not proof that this call completed successfully; no retry/repair is made.
    No stream is opened or rescanned here, and no completion state is inferred.
    """
    _need(type(receipt) is records.CompletionReceipt, "Expected exact CompletionReceipt.")
    data = _encode_record(receipt) + b"\n"
    path = _root(root) / _RECEIPT_NAME
    file = _exclusive(path)
    try:
        _write_complete(file, data)
        file.flush()
        os.fsync(file.fileno())
        file.close()
    except BaseException as error:
        _close_best_effort(file)
        if isinstance(error, Exception):
            raise StoreError("Completion receipt publication failed; file retained.") from error
        raise
    return path


def read_completion_receipt(root):
    path = _root(root) / _RECEIPT_NAME
    with _reader(path) as file:
        line = _readline(file)
        _need(line.endswith(b"\n") and _readline(file) == b"", "Receipt needs one final LF and no trailing bytes.")
        receipt = _decode_record(line[:-1])
        _need(type(receipt) is records.CompletionReceipt, "Wrong completion receipt kind.")
    return receipt
