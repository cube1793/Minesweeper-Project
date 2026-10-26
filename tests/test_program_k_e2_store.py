"""I2-only transport tests: synthetic records, temporary roots, injected I/O faults."""

import ast
import builtins
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
import hashlib
import inspect
import io
import json
import os
from pathlib import Path
import random
import stat
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

from experiments import program_k_e2_records as records
from experiments import program_k_e2_store as store
from experiments import program_k_e2_physical as physical


_SHA = "a" * 64


def _event(ordinal=0):
    return records.OperationEventRecord(records.Phase.EXECUTION, "synthetic-unit", records.EventKind.PROGRESS,
                                        ordinal, ordinal, records.OperationStatus.RUNNING)


def _receipt(streams=(), state=records.CompletionState.COMPLETED):
    return records.CompletionReceipt(_SHA, _SHA, _SHA, _SHA, streams, state)


def _line(key, record):
    return json.dumps(key, separators=(",", ":")).encode("ascii") + b"\t" + records.encode(record) + b"\n"


class _WriteProbe:
    """Real temporary file underneath; forbid every read/seek on the write path."""

    def __init__(self, file):
        self.file = file
        self.writes = []
        self.calls = []
        self.mode = "normal"
        self.flush_error = False
        self.close_error = False

    def write(self, data):
        self.calls.append("write")
        self.writes.append(data)
        if self.mode == "short":
            return self.file.write(data[:-1])
        if self.mode == "raise":
            self.file.write(data[:3])
            raise OSError("injected partial-write failure")
        if self.mode == "none":
            return None
        if self.mode == "bool":
            return True
        return self.file.write(data)

    def flush(self):
        self.calls.append("flush")
        if self.flush_error:
            raise OSError("injected flush failure")
        self.file.flush()

    def fileno(self):
        self.calls.append("fileno")
        return self.file.fileno()

    def close(self):
        self.calls.append("close")
        self.file.close()
        if self.close_error:
            raise OSError("injected close failure")

    def read(self, *args):
        raise AssertionError("Writer read prior content")

    readinto = read
    readline = read
    readlines = read
    seek = read
    tell = read


class _ReadProbe:
    def __init__(self, file):
        self.file = file
        self.lines = []
        self.close_error = False

    def readline(self):
        line = self.file.readline()
        self.lines.append(line)
        return line

    def close(self):
        self.file.close()
        if self.close_error:
            raise OSError("injected reader-close failure")

    def forbidden(self, *args):
        raise AssertionError("Scanner must only read sequential lines")

    read = forbidden
    readinto = forbidden
    readlines = forbidden
    seek = forbidden
    tell = forbidden
    write = forbidden


class _HashProbe:
    def __init__(self):
        self.digest = hashlib.sha256()
        self.updates = []

    def update(self, data):
        self.updates.append(data)
        self.digest.update(data)

    def hexdigest(self):
        return self.digest.hexdigest()


class _TemporaryRootCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def writer(self, name="events"):
        writer = store.StreamWriter(self.root, name)
        self.addCleanup(writer.close)
        return writer

    def probe_writer(self, name="events"):
        path = self.root / (name + ".jsonl")
        probe = _WriteProbe(path.open("xb", buffering=0))
        self.addCleanup(probe.file.close)
        with patch.object(store.Path, "open", return_value=probe) as opened:
            writer = self.writer(name)
        opened.assert_called_once_with("xb", buffering=0)
        return writer, probe

    def put(self, name, data):
        path = self.root / (name + ".jsonl")
        with path.open("xb") as file:
            file.write(data)
        return path


class WriterTests(_TemporaryRootCase):
    def test_exact_lines_digest_and_sealed_scan_round_trip(self):
        board = records.BoardIdentity(101, "synthetic", 2, 2, 1, (0, 0), "supplied-generator", "supplied-spec")
        values = (_event(), records.PhysicalInputRecord(0, records.Action.OPEN, (0, 0), (0, 0), 7, 7, records.Status.WON),
                  records.PairComparisonRecord(board, records.Outcome.WIN, records.Outcome.WIN, records.P3Status.PASS,
                                               0, records.G5ExposureSummary(5, 0, 0), "SUPPLIED"))
        writer = self.writer()
        for i, record in enumerate(values):
            writer.append((i,), record)
        expected = b"".join(_line((i,), record) for i, record in enumerate(values))
        digest = writer.seal()
        self.assertIs(type(digest), records.StreamDigest)
        self.assertEqual(writer.path.read_bytes(), expected)
        self.assertEqual(digest, records.StreamDigest("events", hashlib.sha256(expected).hexdigest(), len(expected), 3))
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (3, len(expected), (2,)))
        visited = []
        self.assertEqual(store.scan_stream(self.root, "events", visit=lambda k, r: visited.append((k, r))), digest)
        self.assertEqual(visited, [((i,), r) for i, r in enumerate(values)])

    def test_append_not_durable_until_checkpoint_and_prefix_snapshot_stays_immutable(self):
        writer, probe = self.probe_writer()
        real_fsync = os.fsync
        with patch.object(store.os, "fsync", wraps=real_fsync) as synced:
            writer.append((0,), _event())
            self.assertIsNone(writer.last_durable_checkpoint)
            synced.assert_not_called()
            self.assertEqual(probe.calls, ["write"])
            first = writer.checkpoint()
            self.assertEqual(synced.call_count, 1)
            self.assertEqual(probe.calls, ["write", "flush", "fileno"])
            with self.assertRaises(FrozenInstanceError):
                first.record_count = 99
            writer.append((1,), _event(1))
            self.assertIs(writer.last_durable_checkpoint, first)
            self.assertEqual((first.record_count, first.last_key), (1, (0,)))
            self.assertEqual(synced.call_count, 1)
            final = writer.seal()
            self.assertEqual(synced.call_count, 2)
            self.assertEqual(writer.last_durable_checkpoint.record_count, 2)
            self.assertEqual(writer.last_durable_checkpoint.sha256, final.sha256)
        self.assertTrue(writer.sealed)
        self.assertTrue(probe.file.closed)

    def test_empty_stream_seal_and_checkpoint(self):
        writer = self.writer()
        snapshot = writer.checkpoint()
        self.assertEqual(snapshot, store.DurableCheckpoint("events", hashlib.sha256(b"").hexdigest(), 0, 0, None))
        digest = writer.seal()
        self.assertEqual(digest, store.scan_stream(self.root, "events"))
        self.assertEqual(writer.path.read_bytes(), b"")

    def test_append_checkpoint_and_seal_after_seal_fail(self):
        writer = self.writer()
        writer.seal()
        for call in (lambda: writer.append((0,), _event()), writer.checkpoint, writer.seal):
            with self.assertRaises(store.StoreError):
                call()
        writer.close()
        self.assertTrue(writer.sealed)

    def test_close_is_non_success_and_idempotent(self):
        writer, probe = self.probe_writer()
        writer.append((0,), _event())
        with patch.object(store.os, "fsync", side_effect=AssertionError("close must not fsync")):
            writer.close()
            writer.close()
        self.assertEqual(probe.calls.count("close"), 1)
        self.assertFalse(writer.sealed)
        self.assertIsNone(writer.last_durable_checkpoint)
        for call in (lambda: writer.append((1,), _event()), writer.checkpoint, writer.seal):
            with self.assertRaises(store.StoreError):
                call()

    def test_context_exit_does_not_silently_seal(self):
        with patch.object(store.os, "fsync", side_effect=AssertionError("context exit must not fsync")):
            with store.StreamWriter(self.root, "normal") as normal:
                normal.append((0,), _event())
            marker = RuntimeError("caller failed")
            with self.assertRaises(RuntimeError) as caught:
                with store.StreamWriter(self.root, "exceptional") as exceptional:
                    exceptional.append((0,), _event())
                    raise marker
        self.assertIs(caught.exception, marker)
        self.assertFalse(normal.sealed)
        self.assertFalse(exceptional.sealed)
        self.assertIsNone(exceptional.last_durable_checkpoint)
        self.assertTrue((self.root / "exceptional.jsonl").exists())

    def test_stream_name_validation_before_path_access(self):
        class S(str):
            pass
        invalid = ("", "A", "0event", "_event", "-event", "a.b", "a/b", "a\\b", "a:b", "a b",
                   "a\n", "a\t", "a\0", "한글", "é", "a" * 65, b"events", None, S("events"))
        with patch.object(store.Path, "resolve", side_effect=AssertionError("invalid name touched root")):
            for name in invalid:
                with self.subTest(name=name), self.assertRaises(store.StoreError):
                    store.StreamWriter(self.root, name)

    def test_valid_stream_name_bounds_and_reserved_device_rejection(self):
        for name in ("a", "a0_-z", "a" * 64):
            writer = self.writer(name)
            self.assertEqual(writer.path.name, name + ".jsonl")
            writer.close()
        with patch.object(store.Path, "is_reserved", return_value=True):
            with self.assertRaises(store.StoreError):
                store.StreamWriter(self.root, "reserved")
        self.assertFalse((self.root / "reserved.jsonl").exists())

    def test_root_must_exist_and_be_directory_no_parent_creation(self):
        missing = self.root / "missing" / "child"
        not_directory = self.put("ordinary", b"existing")
        for root in (missing, not_directory, None, 12):
            with self.assertRaises(store.StoreError):
                store.StreamWriter(root, "events")
        self.assertFalse((self.root / "missing").exists())

    def test_existing_target_is_never_overwritten_or_resumed(self):
        path = self.put("events", b"existing-corrupt-evidence")
        with self.assertRaises(store.StoreError):
            self.writer()
        self.assertEqual(path.read_bytes(), b"existing-corrupt-evidence")
        directory = self.root / "directory.jsonl"
        directory.mkdir()
        with self.assertRaises(store.StoreError):
            self.writer("directory")
        self.assertTrue(directory.is_dir())

    def test_second_writer_cannot_open_live_or_closed_stream(self):
        writer = self.writer()
        with self.assertRaises(store.StoreError):
            store.StreamWriter(self.root, "events")
        writer.close()
        with self.assertRaises(store.StoreError):
            store.StreamWriter(self.root, "events")

    def test_uint64_keys_tuple_order_including_variable_arity(self):
        writer = self.writer()
        keys = ((0,), (0, 0), (0, 0, 0), (0, 1), (1,), ((1 << 64) - 1,))
        for key in keys:
            writer.append(key, _event())
        writer.seal()
        found = []
        store.scan_stream(self.root, "events", visit=lambda key, record: found.append(key))
        self.assertEqual(tuple(found), keys)

    def test_invalid_keys_rejected_without_poison_or_accounting_changes(self):
        class T(tuple):
            pass
        class I(int):
            pass
        writer = self.writer()
        for key in ((), [], [0], (True,), (False,), (-1,), (1 << 64,), (0.0,), ("0",), (None,),
                    ((0,),), T((0,)), (I(0),)):
            with self.subTest(key=key), self.assertRaises(store.StoreError):
                writer.append(key, _event())
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (0, 0, None))
        self.assertFalse(writer.poisoned)
        writer.append((0,), _event())
        writer.seal()

    def test_duplicate_and_descending_keys_rejected_without_write(self):
        writer, probe = self.probe_writer()
        writer.append((2, 0), _event())
        for key in ((2, 0), (2,), (1, 99)):
            with self.assertRaises(store.StoreError):
                writer.append(key, _event())
        self.assertEqual(len(probe.writes), 1)
        self.assertEqual(writer.last_key, (2, 0))
        self.assertFalse(writer.poisoned)
        writer.append((3,), _event())
        writer.seal()

    def test_unsupported_spoofed_and_corrupted_records_rejected_before_write(self):
        class Subclass(records.OperationEventRecord):
            pass
        base = _event()
        subclass = Subclass(base.phase, base.unit_id, base.event_kind, base.elapsed_ns, base.ordinal, base.status)
        corrupted = replace(base)
        object.__setattr__(corrupted, "ordinal", True)
        writer, probe = self.probe_writer()
        for record in (object(), {"kind": "operation_event"}, subclass, corrupted, object.__new__(records.OperationEventRecord)):
            with self.assertRaises(store.StoreError):
                writer.append((0,), record)
        self.assertEqual(probe.writes, [])
        self.assertEqual(writer.record_count, 0)
        self.assertFalse(writer.poisoned)
        with self.assertRaises(store.StoreError) as caught:
            writer.append((0,), object())
        self.assertIsInstance(caught.exception.__cause__, records.RecordError)

    def test_properties_do_not_expose_handle_or_allow_state_assignment(self):
        writer = self.writer()
        for name in ("stream_name", "path", "record_count", "byte_length", "last_key", "sealed", "poisoned", "last_durable_checkpoint"):
            with self.assertRaises(AttributeError):
                setattr(writer, name, None)
        self.assertFalse(hasattr(writer, "file"))
        self.assertFalse(hasattr(writer, "__dict__"))

    def test_durable_checkpoint_validates_immutable_fields(self):
        base = store.DurableCheckpoint("events", _SHA, 100, 1, (0,))
        for changes in (dict(stream_name="../x"), dict(sha256="A" * 64), dict(byte_length=True),
                        dict(record_count=-1), dict(last_key=(True,)), dict(last_key=[0]),
                        dict(record_count=0), dict(byte_length=0)):
            with self.assertRaises(store.StoreError):
                replace(base, **changes)


class WriterFailureTests(_TemporaryRootCase):
    def assert_poisoned(self, writer, probe, checkpoint):
        self.assertTrue(writer.poisoned)
        self.assertFalse(writer.sealed)
        self.assertIs(writer.last_durable_checkpoint, checkpoint)
        calls = tuple(probe.calls)
        for call in (lambda: writer.append((99,), _event()), writer.checkpoint, writer.seal):
            with self.assertRaises(store.StoreError):
                call()
        self.assertEqual(tuple(probe.calls), calls)

    def test_short_write_retains_partial_file_and_last_durable_prefix(self):
        writer, probe = self.probe_writer()
        writer.append((0,), _event())
        prefix = writer.checkpoint()
        probe.mode = "short"
        with self.assertRaises(store.StoreError):
            writer.append((1,), _event(1))
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (1, prefix.byte_length, (0,)))
        self.assert_poisoned(writer, probe, prefix)
        writer.close()
        self.assertEqual(writer.path.read_bytes(), _line((0,), _event()) + _line((1,), _event(1))[:-1])
        with self.assertRaises(store.StoreError):
            store.scan_stream(self.root, "events")

    def test_partial_write_exception_poisoned_no_retry(self):
        writer, probe = self.probe_writer()
        probe.mode = "raise"
        with self.assertRaises(store.StoreError):
            writer.append((0,), _event())
        self.assert_poisoned(writer, probe, None)
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (0, 0, None))
        writer.close()
        self.assertEqual(writer.path.read_bytes(), _line((0,), _event())[:3])
        self.assertEqual(probe.calls.count("write"), 1)

    def test_none_and_bool_write_reports_are_failures(self):
        for mode in ("none", "bool"):
            writer, probe = self.probe_writer(mode)
            probe.mode = mode
            with self.assertRaises(store.StoreError):
                writer.append((0,), _event())
            self.assert_poisoned(writer, probe, None)
            self.assertEqual(writer.record_count, 0)

    def test_flush_failure_does_not_advance_durable_prefix_or_call_fsync(self):
        writer, probe = self.probe_writer()
        writer.append((0,), _event())
        prefix = writer.checkpoint()
        writer.append((1,), _event(1))
        probe.flush_error = True
        with patch.object(store.os, "fsync") as synced:
            with self.assertRaises(store.StoreError):
                writer.checkpoint()
            synced.assert_not_called()
        self.assert_poisoned(writer, probe, prefix)

    def test_fsync_failure_does_not_advance_durable_prefix(self):
        writer, probe = self.probe_writer()
        writer.append((0,), _event())
        prefix = writer.checkpoint()
        writer.append((1,), _event(1))
        with patch.object(store.os, "fsync", side_effect=OSError("injected fsync failure")) as synced:
            with self.assertRaises(store.StoreError):
                writer.checkpoint()
            self.assert_poisoned(writer, probe, prefix)
            self.assertEqual(synced.call_count, 1)

    def test_seal_checkpoint_failure_cannot_claim_completion(self):
        writer, probe = self.probe_writer()
        writer.append((0,), _event())
        with patch.object(store.os, "fsync", side_effect=OSError("fsync failed")):
            with self.assertRaises(store.StoreError):
                writer.seal()
        self.assert_poisoned(writer, probe, None)
        self.assertFalse(probe.file.closed)
        writer.close()
        self.assertTrue(probe.file.closed)

    def test_seal_close_failure_cannot_claim_completion(self):
        writer, probe = self.probe_writer()
        writer.append((0,), _event())
        probe.close_error = True
        with self.assertRaises(store.StoreError):
            writer.seal()
        self.assert_poisoned(writer, probe, writer.last_durable_checkpoint)
        self.assertEqual(writer.last_durable_checkpoint.record_count, 1)
        writer.close()  # best-effort close is allowed and suppresses the close error

    def test_cancellation_during_write_poisoned_and_propagated(self):
        writer, probe = self.probe_writer()
        marker = KeyboardInterrupt()
        with patch.object(probe, "write", side_effect=marker):
            with self.assertRaises(KeyboardInterrupt) as caught:
                writer.append((0,), _event())
        self.assertIs(caught.exception, marker)
        self.assert_poisoned(writer, probe, None)


class ScanTests(_TemporaryRootCase):
    def test_missing_file_and_bad_root_fail_closed(self):
        with self.assertRaises(store.StoreError):
            store.scan_stream(self.root, "missing")
        with self.assertRaises(store.StoreError):
            store.scan_stream(self.root / "missing", "events")

    def test_framing_corruption_and_truncation_rejected(self):
        line = _line((0,), _event())
        cases = (b"\n", b"no-tab\n", b"\t\n", b"[0]\t\t" + records.encode(_event()) + b"\n",
                 line[:-1], line + b"garbage", line + b"\n", line[:-1] + b"\r\n", line + b"garbage\n")
        for i, data in enumerate(cases):
            with self.subTest(case=i):
                self.put("bad_" + str(i), data)
                with self.assertRaises(store.StoreError):
                    store.scan_stream(self.root, "bad_" + str(i))

    def test_key_malformed_noncanonical_wrong_type_and_range_rejected(self):
        keys = (b"[", b"{}", b"null", b"[]", b"[true]", b"[false]", b"[-1]", b"[18446744073709551616]",
                b"[0.0]", b"[1e0]", b"[NaN]", b"[Infinity]", b'["0"]', b"[null]", b"[[0]]",
                b" [0]", b"[0] ", b"[0, 1]", b"[-0]", b"[00]", b"\xef\xbb\xbf[0]", b"[\xff]")
        for i, key in enumerate(keys):
            with self.subTest(key=key):
                name = "key_" + str(i)
                self.put(name, key + b"\t" + records.encode(_event()) + b"\n")
                with self.assertRaises(store.StoreError):
                    store.scan_stream(self.root, name)

    def test_duplicate_and_descending_keys_rejected(self):
        for i, keys in enumerate((((1,), (1,)), ((1,), (0,)), ((1, 0), (1,)))):
            name = "order_" + str(i)
            self.put(name, b"".join(_line(key, _event()) for key in keys))
            visited = []
            with self.assertRaises(store.StoreError):
                store.scan_stream(self.root, name, visit=lambda key, record: visited.append(key))
            self.assertEqual(visited, [keys[0]])

    def test_record_malformed_noncanonical_wrong_schema_rejected(self):
        raw = records.encode(_event())
        records_bad = (b"{", b"{}", b"null", raw + b" ", b" " + raw,
                       raw.replace(b'"version":1', b'"version":1,"version":1'),
                       raw.replace(b'"ordinal":0', b'"ordinal":0.0'),
                       raw.replace(b'"operation_event"', b'"unknown"'),
                       raw.replace(b'"version":1', b'"version":2'))
        for i, bad in enumerate(records_bad):
            name = "record_" + str(i)
            self.put(name, b"[0]\t" + bad + b"\n")
            with self.assertRaises(store.StoreError):
                store.scan_stream(self.root, name)

    def test_visitor_exception_propagates_unchanged_and_stops_reading(self):
        path = self.put("events", _line((0,), _event()) + _line((1,), _event(1)))
        probe = _ReadProbe(path.open("rb"))
        self.addCleanup(probe.file.close)
        probe.close_error = True
        marker = OSError("visitor failure must not become StoreError")
        def visitor(key, record):
            raise marker
        with patch.object(store.Path, "open", return_value=probe):
            with self.assertRaises(OSError) as caught:
                store.scan_stream(self.root, "events", visit=visitor)
        self.assertIs(caught.exception, marker)
        self.assertEqual(len(probe.lines), 1)
        self.assertTrue(probe.file.closed)

    def test_read_io_failure_is_store_error(self):
        path = self.put("events", _line((0,), _event()))
        probe = _ReadProbe(path.open("rb"))
        self.addCleanup(probe.file.close)
        with patch.object(store.Path, "open", return_value=probe), patch.object(probe, "readline", side_effect=OSError("read failed")):
            with self.assertRaises(store.StoreError):
                store.scan_stream(self.root, "events")
        self.assertTrue(probe.file.closed)

    def test_existing_symlink_or_reparse_read_target_is_rejected_without_open(self):
        path = self.put("events", b"")
        for mode, attributes in ((stat.S_IFLNK, 0), (stat.S_IFREG, stat.FILE_ATTRIBUTE_REPARSE_POINT)):
            info = types.SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
            with patch.object(store.Path, "lstat", return_value=info), patch.object(store.Path, "open") as opened:
                with self.assertRaises(store.StoreError):
                    store.scan_stream(self.root, path.stem)
                opened.assert_not_called()

    def test_invalid_visitor_rejected(self):
        self.put("events", b"")
        with self.assertRaises(store.StoreError):
            store.scan_stream(self.root, "events", visit=1)


class ReceiptTests(_TemporaryRootCase):
    def test_exact_bytes_readback_and_all_completion_states_preserved(self):
        for state in records.CompletionState:
            with tempfile.TemporaryDirectory() as directory:
                receipt = _receipt(state=state)
                path = store.write_completion_receipt(directory, receipt)
                self.assertEqual(path, Path(directory).resolve() / "COMPLETE.json")
                self.assertEqual(path.read_bytes(), records.encode(receipt) + b"\n")
                self.assertEqual(store.read_completion_receipt(directory), receipt)
                self.assertIs(store.read_completion_receipt(directory).state, state)

    def test_exclusive_receipt_does_not_overwrite_existing_bytes(self):
        path = self.root / "COMPLETE.json"
        with path.open("xb") as file:
            file.write(b"partial-existing-receipt")
        with self.assertRaises(store.StoreError):
            store.write_completion_receipt(self.root, _receipt())
        self.assertEqual(path.read_bytes(), b"partial-existing-receipt")

    def test_receipt_exact_type_required_before_creation(self):
        class Subclass(records.CompletionReceipt):
            pass
        subclass = Subclass(_SHA, _SHA, _SHA, _SHA, (), records.CompletionState.COMPLETED)
        for value in (_event(), {}, None, subclass):
            with self.assertRaises(store.StoreError):
                store.write_completion_receipt(self.root, value)
        self.assertFalse((self.root / "COMPLETE.json").exists())

    def test_receipt_missing_or_non_directory_root_never_created(self):
        missing = self.root / "missing"
        for call in (lambda: store.write_completion_receipt(missing, _receipt()),
                     lambda: store.read_completion_receipt(missing),
                     lambda: store.read_completion_receipt(self.root)):
            with self.assertRaises(store.StoreError):
                call()
        self.assertFalse(missing.exists())

    def test_receipt_truncation_extra_bytes_wrong_kind_and_noncanonical_rejected(self):
        raw = records.encode(_receipt())
        bad_files = (raw, raw + b"\n\n", raw + b"\ntrailing", raw + b"\n" + raw + b"\n",
                     raw + b" \n", raw + b"\r\n", b"\n", b"{}\n", b"{\n", b" \n",
                     records.encode(_event()) + b"\n", raw.replace(b'"version":1', b'"version":2') + b"\n")
        for data in bad_files:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "COMPLETE.json"
                with path.open("xb") as file:
                    file.write(data)
                with self.assertRaises(store.StoreError):
                    store.read_completion_receipt(directory)
                self.assertEqual(path.read_bytes(), data)

    def test_receipt_write_failure_fsync_failure_and_flush_failure_keep_file(self):
        for mode in ("short", "raise", "flush", "fsync"):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "COMPLETE.json"
                probe = _WriteProbe(path.open("xb", buffering=0))
                probe.mode = mode
                probe.flush_error = mode == "flush"
                try:
                    with patch.object(store.Path, "open", return_value=probe), patch.object(store.os, "fsync") as synced:
                        if mode == "fsync":
                            synced.side_effect = OSError("fsync failed")
                        with self.assertRaises(store.StoreError):
                            store.write_completion_receipt(directory, _receipt())
                        self.assertEqual(synced.call_count, 1 if mode == "fsync" else 0)
                    self.assertTrue(path.exists())
                    self.assertTrue(probe.file.closed)
                    retained = path.read_bytes()
                    self.assertTrue(retained)
                    with self.assertRaises(store.StoreError):
                        store.write_completion_receipt(directory, _receipt())
                    self.assertEqual(path.read_bytes(), retained)
                    self.assertEqual(probe.calls.count("write"), 1)
                finally:
                    probe.file.close()

    def test_receipt_write_has_flush_fsync_close_order_and_no_stream_rescan(self):
        path = self.root / "COMPLETE.json"
        probe = _WriteProbe(path.open("xb", buffering=0))
        self.addCleanup(probe.file.close)
        receipt = _receipt((records.StreamDigest("absent_stream", _SHA, 120, 1),))
        with patch.object(store.Path, "open", return_value=probe) as opened, \
                patch.object(store, "scan_stream", side_effect=AssertionError("receipt rescanned streams")), \
                patch.object(store.os, "fsync", side_effect=lambda fd: probe.calls.append("fsync")) as synced:
            self.assertEqual(store.write_completion_receipt(self.root, receipt), path)
            opened.assert_called_once_with("xb", buffering=0)
            self.assertEqual(synced.call_count, 1)
        self.assertEqual(probe.calls, ["write", "flush", "fileno", "fsync", "close"])
        self.assertEqual(probe.writes, [records.encode(receipt) + b"\n"])
        self.assertEqual(store.read_completion_receipt(self.root), receipt)


class PerformanceAndBoundaryTests(_TemporaryRootCase):
    def test_append_hashes_only_new_line_without_read_decode_or_rescan(self):
        digest = _HashProbe()
        with patch.object(store.hashlib, "sha256", return_value=digest):
            writer, probe = self.probe_writer()
        expected = [_line((0,), _event()), _line((1,), _event(1))]
        with patch.object(store.records, "decode", side_effect=AssertionError("append decoded prior data")), \
                patch.object(store.os, "fsync") as synced:
            writer.append((0,), _event())
            writer.append((1,), _event(1))
            self.assertEqual(digest.updates, expected)
            self.assertEqual(probe.writes, expected)
            synced.assert_not_called()
            writer.checkpoint()
            writer.seal()
            self.assertEqual(synced.call_count, 2)
            self.assertEqual(digest.updates, expected)
            self.assertEqual(probe.writes, expected)

    def test_many_tiny_appends_retain_only_last_key_no_collection(self):
        writer = self.writer()
        record = _event()
        for i in range(512):
            writer.append((i,), record)
        self.assertEqual(writer.record_count, 512)
        self.assertEqual(writer.last_key, (511,))
        for slot in store.StreamWriter.__slots__:
            value = getattr(writer, slot)
            if slot != "_last_key":
                self.assertNotIsInstance(value, (list, tuple, set, frozenset, dict))
        self.assertFalse(hasattr(writer, "__dict__"))
        digest = writer.seal()
        self.assertEqual(store.scan_stream(self.root, "events"), digest)

    def test_scanner_one_sequential_pass_one_decode_visit_and_hash_per_line(self):
        lines = [_line((i,), _event(i)) for i in range(7)]
        path = self.put("events", b"".join(lines))
        probe = _ReadProbe(path.open("rb"))
        self.addCleanup(probe.file.close)
        digest = _HashProbe()
        visited = []
        real_decode = records.decode
        with patch.object(store.Path, "open", return_value=probe) as opened, \
                patch.object(store.hashlib, "sha256", return_value=digest), \
                patch.object(store.records, "decode", wraps=real_decode) as decoded:
            result = store.scan_stream(self.root, "events", visit=lambda key, record: visited.append((key, record)))
        opened.assert_called_once_with("rb")
        self.assertEqual(probe.lines, lines + [b""])
        self.assertEqual(digest.updates, lines)
        self.assertEqual(decoded.call_count, len(lines))
        self.assertEqual(visited, [((i,), _event(i)) for i in range(7)])
        self.assertEqual(result.sha256, hashlib.sha256(b"".join(lines)).hexdigest())
        self.assertEqual(result.byte_length, sum(map(len, lines)))
        self.assertTrue(probe.file.closed)

    def test_ast_import_boundary_and_no_dynamic_loader(self):
        tree = ast.parse(inspect.getsource(store))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(a.name.split(".")[0] in sys.stdlib_module_names for a in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                if node.module == "experiments":
                    if tuple(a.name for a in node.names) == ("program_k_e2_physical",):
                        self.assertEqual(node.names[0].asname, "physical")
                        continue
                    self.assertEqual(tuple(a.name for a in node.names), ("program_k_e2_records",))
                else:
                    self.assertIn(node.module.split(".")[0], sys.stdlib_module_names)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"eval", "exec", "__import__", "compile"})
        for name in ("append", "checkpoint", "seal"):
            method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
            calls = {n.func.attr for n in ast.walk(method) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
            self.assertFalse(calls.intersection({"read", "readline", "readlines", "seek", "decode", "scan_stream"}))

    def test_import_has_no_io_process_clock_random_or_environment_capture(self):
        name = "_e2_i2_import_probe"
        source = compile(inspect.getsource(store), store.__file__, "exec")
        probe = types.ModuleType(name)
        real_import = builtins.__import__
        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "experiments" and tuple(fromlist) == ("program_k_e2_physical",):
                self.assertEqual(level, 0)
                return real_import(name, globals, locals, fromlist, level)
            if name == "experiments":
                self.assertEqual(tuple(fromlist), ("program_k_e2_records",))
            else:
                self.assertIn(name.split(".")[0], sys.stdlib_module_names)
            return real_import(name, globals, locals, fromlist, level)
        blocked = ((builtins, "open"), (io, "open"), (os, "open"), (os, "stat"), (os, "lstat"),
                   (os, "listdir"), (os, "scandir"), (os, "mkdir"), (os, "makedirs"), (os, "getcwd"),
                   (os, "getenv"), (os, "urandom"), (os, "system"), (subprocess, "Popen"), (subprocess, "run"),
                   (Path, "open"), (Path, "resolve"), (Path, "mkdir"), (Path, "read_bytes"), (Path, "write_bytes"),
                   (time, "time"), (time, "monotonic"), (time, "perf_counter"), (random, "random"), (random, "getrandbits"))
        with patch.dict(sys.modules, {name: probe}), ExitStack() as stack:
            for owner, attribute in blocked:
                stack.enter_context(patch.object(owner, attribute, side_effect=AssertionError("import side effect")))
            stack.enter_context(patch.object(builtins, "__import__", side_effect=guarded_import))
            exec(source, probe.__dict__)


_RF02_PROFILE = bytes.fromhex("5a" * 32)  # Supplied synthetic identity; no profile capture.


def _frame_context(name="operations"):
    return physical.context_for(name, _RF02_PROFILE)


def _board(seed=101):
    return records.BoardIdentity(seed, "synthetic", 2, 2, 1, (0, 0), "supplied-generator", "supplied-spec")


def _frame(key, record, context=None):
    return physical.encode_frame(records.encode(record), key, context or _frame_context())


class _FramedReadProbe:
    """Only bounded forward reads; optional fragmentation of actual file reads."""

    def __init__(self, file, limits=None, fragment=None):
        self.file = file
        self.limits = limits
        self.fragment = fragment
        self.position = 0
        self.reads = []
        self.close_error = False

    def read(self, size=-1):
        if type(size) is not int or size <= 0:
            raise AssertionError("RF02 scan attempted an unbounded read")
        if self.limits is not None and size > self.limits.get(self.position, 9):
            raise AssertionError("Read exceeded the remaining declared frame component")
        self.reads.append((self.position, size))
        data = self.file.read(min(size, self.fragment) if self.fragment else size)
        self.position += len(data)
        return data

    def close(self):
        self.file.close()
        if self.close_error:
            raise OSError("injected framed reader close failure")

    def forbidden(self, *args, **kwargs):
        raise AssertionError("RF02 scan must use bounded forward reads only")

    seek = forbidden
    tell = forbidden
    readinto = forbidden
    readline = forbidden
    readlines = forbidden
    write = forbidden
    fileno = forbidden  # Whole-file mmap cannot acquire this reader's descriptor.


class _FramedRootCase(_TemporaryRootCase):
    def framed_writer(self, name="operations", *, root=None, context=None, **kwargs):
        writer = store.FramedStreamWriter(root or self.root, name, context or _frame_context(name), **kwargs)
        self.addCleanup(writer.close)
        return writer

    def framed_probe_writer(self, name="operations", *, root=None, **kwargs):
        directory = root or self.root
        probe = _WriteProbe((directory / (name + ".pkf")).open("xb", buffering=0))
        self.addCleanup(probe.file.close)
        with patch.object(store.Path, "open", return_value=probe) as opened:
            writer = self.framed_writer(name, root=directory, **kwargs)
        opened.assert_called_once_with("xb", buffering=0)
        return writer, probe

    def put_framed(self, data, name="operations", *, root=None):
        path = (root or self.root) / (name + ".pkf")
        path.write_bytes(data)
        return path

    def assert_framed_poisoned(self, writer, probe, snapshot):
        self.assertTrue(writer.poisoned)
        self.assertFalse(writer.sealed)
        self.assertIs(writer.last_durable_checkpoint, snapshot)
        calls = tuple(probe.calls)
        for call in (lambda: writer.append((99,), _event()), writer.checkpoint, writer.seal):
            with self.assertRaises(store.StoreError):
                call()
        self.assertEqual(tuple(probe.calls), calls)


class FramedWriterTests(_FramedRootCase):
    def test_empty_file_has_explicit_pkf_path_no_prologue_or_completion_marker(self):
        writer = self.framed_writer()
        self.assertEqual(writer.path, self.root / "operations.pkf")
        self.assertEqual(writer.path.read_bytes(), b"")
        digest = writer.seal()
        self.assertEqual(digest, records.StreamDigest("operations", hashlib.sha256(b"").hexdigest(), 0, 0))
        self.assertEqual(tuple(path.name for path in self.root.iterdir()), ("operations.pkf",))
        self.assertEqual(store.scan_framed_stream(self.root, "operations", _frame_context()), digest)

    def test_experiment_and_support_exact_frames_hash_counts_and_numeric_keys(self):
        cases = (("boards", ((0, 0, 127), (0, 0, 128), (1, 0, 0)), (_board(), _board(102), _board(103))),
                 ("operations", ((127,), (128,), (255,), (256,), ((1 << 64) - 1,)), tuple(_event(i) for i in range(5))))
        for name, keys, values in cases:
            with self.subTest(stream=name):
                context = _frame_context(name)
                expected = b"".join(_frame(key, value, context) for key, value in zip(keys, values))
                writer = self.framed_writer(name, context=context)
                for key, value in zip(keys, values):
                    writer.append(key, value)
                digest = writer.seal()
                self.assertEqual(writer.path.read_bytes(), expected)
                self.assertEqual(digest, records.StreamDigest(name, hashlib.sha256(expected).hexdigest(), len(expected), len(keys)))
                self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (len(keys), len(expected), keys[-1]))
                fresh = _frame_context(name)
                self.assertIsNot(fresh, context)
                visited = []
                self.assertEqual(store.scan_framed_stream(self.root, name, fresh, visit=lambda *facts: visited.append(facts)), digest)
                self.assertEqual(visited, [(key, value, records.encode(value), len(_frame(key, value, fresh)))
                                           for key, value in zip(keys, values)])

    def test_append_constructs_one_frame_and_writes_and_hashes_the_exact_object(self):
        context = _frame_context()
        expected = _frame((0,), _event(), context)
        digest = _HashProbe()
        with patch.object(store.hashlib, "sha256", return_value=digest):
            writer, probe = self.framed_probe_writer(context=context)
        with patch.object(physical, "encode_frame", return_value=expected) as encoded, \
                patch.object(store.Path, "read_bytes", side_effect=AssertionError("append reread file")), \
                patch.object(store.os, "fsync") as synced:
            writer.append((0,), _event())
            encoded.assert_called_once()
            self.assertEqual(encoded.call_args.args, (records.encode(_event()), (0,), context))
            self.assertEqual(encoded.call_args.kwargs, {"max_payload_bytes": physical.MAX_PAYLOAD_BYTES})
            self.assertIs(probe.writes[0], expected)
            self.assertEqual(len(probe.writes), 1)
            self.assertIs(digest.updates[0], expected)
            self.assertEqual(len(digest.updates), 1)
            synced.assert_not_called()
        self.assertEqual(writer.checkpoint().sha256, hashlib.sha256(expected).hexdigest())

    def test_first_empty_checkpoint_syncs_clean_checkpoint_and_seal_reuse_snapshot(self):
        writer, probe = self.framed_probe_writer()
        with patch.object(store.os, "fsync") as synced:
            first = writer.checkpoint()
            self.assertEqual(first, store.DurableCheckpoint("operations", hashlib.sha256(b"").hexdigest(), 0, 0, None))
            self.assertEqual(probe.calls, ["flush", "fileno"])
            self.assertEqual(synced.call_count, 1)
            self.assertIs(writer.checkpoint(), first)
            self.assertIs(writer.last_durable_checkpoint, first)
            digest = writer.seal()
            self.assertEqual(synced.call_count, 1)
            self.assertEqual(probe.calls, ["flush", "fileno", "close"])
            self.assertEqual(digest.sha256, first.sha256)

    def test_append_marks_dirty_and_new_checkpoint_does_not_mutate_old_snapshot(self):
        writer, probe = self.framed_probe_writer()
        with patch.object(store.os, "fsync") as synced:
            first = writer.checkpoint()
            writer.append((0,), _event())
            self.assertIs(writer.last_durable_checkpoint, first)
            self.assertEqual((first.record_count, first.byte_length, first.last_key), (0, 0, None))
            self.assertEqual(synced.call_count, 1)
            second = writer.checkpoint()
            self.assertIsNot(second, first)
            self.assertEqual(second.record_count, 1)
            self.assertIs(writer.checkpoint(), second)
            self.assertEqual(synced.call_count, 2)
            with self.assertRaises(FrozenInstanceError):
                second.record_count = 9
            writer.append((1,), _event(1))
            self.assertIs(writer.last_durable_checkpoint, second)
            self.assertEqual(second.record_count, 1)
            final = writer.seal()
            self.assertEqual(synced.call_count, 3)
            self.assertEqual(probe.calls.count("flush"), 3)
            self.assertEqual(final.record_count, 2)
            self.assertEqual(writer.last_durable_checkpoint.sha256, final.sha256)

    def test_never_checkpointed_dirty_seal_syncs_once(self):
        writer, probe = self.framed_probe_writer()
        writer.append((0,), _event())
        with patch.object(store.os, "fsync") as synced:
            writer.seal()
        self.assertEqual(synced.call_count, 1)
        self.assertEqual(probe.calls, ["write", "flush", "fileno", "close"])

    def test_invalid_context_and_bounds_rejected_before_filesystem_access(self):
        class ContextSubclass(physical.FrameContext):
            pass
        good = _frame_context()
        subclass = ContextSubclass(good.codec_profile_sha256, good.stream_name,
                                   expected_key_arity=good.expected_key_arity,
                                   allowed_logical_record_types=good.allowed_logical_record_types)
        corrupted = replace(good)
        object.__setattr__(corrupted, "expected_key_arity", 3)
        with patch.object(store.Path, "resolve", side_effect=AssertionError("invalid input accessed root")), \
                patch.object(store.Path, "open", side_effect=AssertionError("invalid input opened file")):
            for context in (None, object(), subclass, corrupted, _frame_context("postprocessing_operations")):
                with self.subTest(context=context), self.assertRaises(store.StoreError):
                    store.FramedStreamWriter(self.root, "operations", context)
            for bound in (True, False, 0, -1, 1.0, physical.MAX_PAYLOAD_BYTES + 1):
                with self.subTest(bound=bound), self.assertRaises(store.StoreError):
                    store.FramedStreamWriter(self.root, "operations", good, max_payload_bytes=bound)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_keys_do_not_write_or_poison_and_later_append_succeeds(self):
        class IntegerSubclass(int):
            pass
        class TupleSubclass(tuple):
            pass
        writer, probe = self.framed_probe_writer()
        snapshot = writer.checkpoint()
        for key in ((), [], [0], (0, 0), (0, 0, 0), (True,), (False,), (IntegerSubclass(0),),
                    TupleSubclass((0,)), (-1,), (1 << 64,), (0.0,), ("0",), (None,)):
            with self.subTest(key=key), self.assertRaises(store.StoreError):
                writer.append(key, _event())
        self.assertEqual(probe.writes, [])
        self.assertFalse(writer.poisoned)
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (0, 0, None))
        self.assertIs(writer.last_durable_checkpoint, snapshot)
        writer.append((0,), _event())
        self.assertEqual(writer.seal().record_count, 1)

    def test_duplicate_descending_wrong_family_and_corrupt_records_preserve_state(self):
        writer, probe = self.framed_probe_writer()
        writer.append((128,), _event())
        snapshot = writer.checkpoint()
        for key in ((128,), (127,)):
            with self.assertRaises(store.StoreError):
                writer.append(key, _event())
        corrupted = replace(_event())
        object.__setattr__(corrupted, "ordinal", True)
        for record in (_board(), corrupted, object.__new__(records.OperationEventRecord),
                       records.encode(_event()), object(), {"kind": "operation_event"}):
            with self.subTest(record_type=type(record)), self.assertRaises(store.StoreError):
                writer.append((129,), record)
        self.assertEqual(len(probe.writes), 1)
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (1, snapshot.byte_length, (128,)))
        self.assertIs(writer.last_durable_checkpoint, snapshot)
        self.assertFalse(writer.poisoned)
        writer.append((129,), _event(1))
        self.assertEqual(writer.seal().record_count, 2)

    def test_logical_cap_rejection_keeps_writer_usable(self):
        small = _event()
        cap = len(records.encode(small))
        large = replace(small, unit_id="bounded-synthetic-" * 64)
        writer, probe = self.framed_probe_writer(max_payload_bytes=cap)
        with self.assertRaises(store.StoreError):
            writer.append((0,), large)
        self.assertEqual(probe.writes, [])
        self.assertFalse(writer.poisoned)
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (0, 0, None))
        writer.append((0,), small)
        self.assertEqual(writer.seal().record_count, 1)

    def test_physical_frame_cap_rejected_before_io_without_poison(self):
        cap = len(records.encode(_event()))
        writer, probe = self.framed_probe_writer(max_payload_bytes=cap)
        oversized = b"x" * (cap + 13 + 10 + 1)
        with patch.object(physical, "encode_frame", return_value=oversized) as encoded:
            with self.assertRaises(store.StoreError):
                writer.append((0,), _event())
        encoded.assert_called_once()
        self.assertEqual(probe.writes, [])
        self.assertFalse(writer.poisoned)
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (0, 0, None))
        writer.append((0,), _event())
        self.assertEqual(writer.seal().record_count, 1)

    def test_existing_pkf_never_overwritten_or_resumed(self):
        path = self.put_framed(b"retained-existing-evidence")
        with self.assertRaises(store.StoreError):
            self.framed_writer()
        self.assertEqual(path.read_bytes(), b"retained-existing-evidence")

    def test_close_is_idempotent_without_sync_or_completion(self):
        writer, probe = self.framed_probe_writer()
        writer.append((0,), _event())
        with patch.object(store.os, "fsync", side_effect=AssertionError("close checkpointed")):
            writer.close()
            writer.close()
        self.assertEqual(probe.calls, ["write", "close"])
        self.assertFalse(writer.sealed)
        self.assertIsNone(writer.last_durable_checkpoint)
        for call in (lambda: writer.append((1,), _event()), writer.checkpoint, writer.seal):
            with self.assertRaises(store.StoreError):
                call()
        self.assertEqual([path.name for path in self.root.iterdir()], ["operations.pkf"])

    def test_context_exit_does_not_seal_and_caller_exception_is_unchanged(self):
        marker = RuntimeError("caller interrupted")
        with patch.object(store.os, "fsync", side_effect=AssertionError("context exit checkpointed")):
            with store.FramedStreamWriter(self.root, "operations", _frame_context()) as normal:
                normal.append((0,), _event())
            with self.assertRaises(RuntimeError) as caught:
                with store.FramedStreamWriter(self.root, "postprocessing_operations", _frame_context("postprocessing_operations")) as exceptional:
                    exceptional.append((0,), _event())
                    raise marker
        self.assertIs(caught.exception, marker)
        self.assertFalse(normal.sealed)
        self.assertFalse(exceptional.sealed)
        self.assertIsNone(normal.last_durable_checkpoint)
        self.assertIsNone(exceptional.last_durable_checkpoint)

    def test_sealed_writer_rejects_further_operations(self):
        writer = self.framed_writer()
        writer.seal()
        for call in (lambda: writer.append((0,), _event()), writer.checkpoint, writer.seal):
            with self.assertRaises(store.StoreError):
                call()
        self.assertTrue(writer.sealed)


class ExactFrameAppendTests(_FramedRootCase):
    def state(self, writer):
        return (writer.record_count, writer.byte_length, writer.last_key, writer.dirty,
                writer.last_durable_checkpoint, writer._hash.hexdigest(), writer.path.read_bytes())

    def test_received_wb02_frames_persist_exactly_without_recompression(self):
        from experiments import program_k_e2_execution as execution

        writer = self.framed_writer("boards")
        rows = []
        for position in (0, 1):
            board = records.encode(_board(101 + position))
            bundle = execution.WorkerBundle(position, execution.WorkerKind.PRIMARY, board,
                execution.identity.ArmOrder.CONTROL_THEN_KP0, (("boards", (board,)),), (),
                records.AuditStatus.PASS, ())
            wire = execution.encode_bundle_v2(bundle, _RF02_PROFILE)
            view = execution.decode_bundle_view_v2(wire, _RF02_PROFILE)
            self.assertEqual(view.bundle, bundle)
            rows.extend(view.rows)
        with patch.object(physical, "encode_frame", side_effect=AssertionError("recompressed received frame")):
            for row in rows:
                writer.append_frame(row.key, row.logical_bytes, row.frame_bytes)
            digest = writer.seal()
        expected = b"".join(row.frame_bytes for row in rows)
        self.assertEqual(writer.path.read_bytes(), expected)
        self.assertEqual(digest, records.StreamDigest("boards", hashlib.sha256(expected).hexdigest(),
                                                     len(expected), len(rows)))
        self.assertEqual(store.scan_framed_stream(self.root, "boards", _frame_context("boards")), digest)
        self.assertEqual([path.name for path in self.root.iterdir()], ["boards.pkf"])

    def test_decoder_runs_independently_and_exact_supplied_object_is_written_and_hashed(self):
        logical = records.encode(_event())
        frame = _frame((0,), _event())
        digest = _HashProbe()
        with patch.object(store.hashlib, "sha256", return_value=digest):
            writer, probe = self.framed_probe_writer()
        with patch.object(physical, "decode_frame", wraps=physical.decode_frame) as decoded, \
                patch.object(physical, "encode_frame", side_effect=AssertionError("reframed received bytes")), \
                patch.object(store.os, "fsync") as synced:
            writer.append_frame((0,), logical, frame)
            decoded.assert_called_once_with(frame, _frame_context(), expected_key=(0,),
                                            max_payload_bytes=physical.MAX_PAYLOAD_BYTES)
            self.assertIs(decoded.call_args.args[0], frame)
            self.assertEqual(len(probe.writes), 1)
            self.assertEqual(len(digest.updates), 1)
            self.assertIs(probe.writes[0], frame)
            self.assertIs(digest.updates[0], frame)
            self.assertEqual(probe.calls, ["write"])
            synced.assert_not_called()
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key, writer.dirty),
                         (1, len(frame), (0,), True))
        self.assertEqual(writer.checkpoint().sha256, hashlib.sha256(frame).hexdigest())

    def test_wrong_profile_stream_key_logical_and_crc_reject_without_state_change(self):
        writer, probe = self.framed_probe_writer()
        writer.append_frame((0,), records.encode(_event()), _frame((0,), _event()))
        writer.checkpoint()
        logical = records.encode(_event(1))
        frame = _frame((1,), _event(1))
        corrupt = frame[:-1] + bytes((frame[-1] ^ 1,))
        cases = (
            (logical, _frame((1,), _event(1), physical.context_for("operations", b"z" * 32))),
            (logical, _frame((1,), _event(1), _frame_context("postprocessing_operations"))),
            (logical, _frame((2,), _event(1))),
            (records.encode(_event(2)), frame),
            (logical, corrupt), (logical, frame[:-1]), (logical, frame + b"\0"),
        )
        before, writes = self.state(writer), tuple(probe.writes)
        for supplied, candidate in cases:
            with self.subTest(frame=candidate), self.assertRaises(store.StoreError):
                writer.append_frame((1,), supplied, candidate)
            self.assertEqual(self.state(writer), before)
            self.assertEqual(tuple(probe.writes), writes)
            self.assertFalse(writer.poisoned)
        writer.append_frame((1,), logical, frame)
        self.assertEqual(writer.seal().record_count, 2)

    def test_crc_correct_noncanonical_wrong_family_and_mode_length_frames_reject(self):
        writer, probe = self.framed_probe_writer()
        context = _frame_context()
        logical = records.encode(_event())
        rows = []
        for data in (records.encode(_board()), logical + b" ", b"{}"):
            rows.append((data, b"\0" + len(data).to_bytes(4, "big") * 2 + b"\0" + data))
        rows.extend((logical, bytes((mode,)) + len(logical).to_bytes(4, "big")
                     + payload_length.to_bytes(4, "big") + b"\0" + logical)
                    for mode, payload_length in ((2, len(logical)), (0, len(logical) - 1),
                                                (1, len(logical))))
        before = self.state(writer)
        for supplied, row in rows:
            frame = row + physical.contextual_crc32(context, row).to_bytes(4, "big")
            with self.subTest(row=row), self.assertRaises(store.StoreError):
                writer.append_frame((0,), supplied, frame)
            self.assertEqual(self.state(writer), before)
            self.assertFalse(writer.poisoned)
        self.assertEqual(probe.writes, [])
        writer.append_frame((0,), logical, _frame((0,), _event()))
        self.assertEqual(writer.seal().record_count, 1)

    def test_mutable_bytes_subclasses_and_nonexact_keys_reject_before_decode(self):
        class BytesSubclass(bytes):
            pass
        class TupleSubclass(tuple):
            pass
        class IntegerSubclass(int):
            pass
        logical, frame = records.encode(_event()), _frame((0,), _event())
        writer, probe = self.framed_probe_writer()
        before = self.state(writer)
        with patch.object(physical, "decode_frame", side_effect=AssertionError("nonexact input decoded")):
            for candidate in (bytearray(logical), memoryview(logical), BytesSubclass(logical), None, _event()):
                with self.subTest(logical_type=type(candidate)), self.assertRaises(store.StoreError):
                    writer.append_frame((0,), candidate, frame)
            for candidate in (bytearray(frame), memoryview(frame), BytesSubclass(frame), None, b""):
                with self.subTest(frame_type=type(candidate)), self.assertRaises(store.StoreError):
                    writer.append_frame((0,), logical, candidate)
            for key in ((), [], [0], (0, 0), TupleSubclass((0,)), (IntegerSubclass(0),),
                        (True,), (-1,), (1 << 64,), (0.0,)):
                with self.subTest(key=key), self.assertRaises(store.StoreError):
                    writer.append_frame(key, logical, frame)
        self.assertEqual(self.state(writer), before)
        self.assertEqual(probe.writes, [])
        self.assertFalse(writer.poisoned)

    def test_context_and_limit_are_revalidated_at_every_exact_append(self):
        writer, probe = self.framed_probe_writer()
        logical, frame = records.encode(_event()), _frame((0,), _event())
        context, limit = writer._context, writer._max_payload_bytes
        bad_context = replace(context)
        object.__setattr__(bad_context, "expected_key_arity", 3)
        before = self.state(writer)
        for candidate in (None, bad_context, _frame_context("postprocessing_operations")):
            writer._context = candidate
            with self.assertRaises(store.StoreError):
                writer.append_frame((0,), logical, frame)
            self.assertEqual(self.state(writer), before)
            self.assertFalse(writer.poisoned)
        writer._context = context
        for candidate in (True, 0, -1, physical.MAX_PAYLOAD_BYTES + 1):
            writer._max_payload_bytes = candidate
            with self.assertRaises(store.StoreError):
                writer.append_frame((0,), logical, frame)
            self.assertEqual(self.state(writer), before)
            self.assertFalse(writer.poisoned)
        writer._max_payload_bytes = limit
        self.assertEqual(probe.writes, [])
        writer.append_frame((0,), logical, frame)
        self.assertEqual(writer.seal().record_count, 1)

    def test_payload_bounds_are_enforced_without_write_or_poison(self):
        small = _event()
        logical = records.encode(small)
        limit = len(logical)
        large = replace(small, unit_id="bounded-synthetic-" * 64)
        writer, probe = self.framed_probe_writer(max_payload_bytes=limit)
        for supplied, frame in ((records.encode(large), _frame((0,), large)),
                                (logical, _frame((0,), large)),
                                (logical, b"x" * (limit + 24))):
            with self.assertRaises(store.StoreError):
                writer.append_frame((0,), supplied, frame)
        self.assertEqual(probe.writes, [])
        self.assertFalse(writer.poisoned)
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key, writer.dirty),
                         (0, 0, None, False))
        writer.append_frame((0,), logical, _frame((0,), small))
        self.assertEqual(writer.seal().record_count, 1)

    def test_duplicate_descending_keys_preserve_dirty_state_and_hash(self):
        writer, probe = self.framed_probe_writer()
        writer.append_frame((128,), records.encode(_event()), _frame((128,), _event()))
        before = self.state(writer)
        for key in ((128,), (127,)):
            frame = _frame(key, _event(1))
            with patch.object(physical, "decode_frame", side_effect=AssertionError("bad order decoded")):
                with self.assertRaises(store.StoreError):
                    writer.append_frame(key, records.encode(_event(1)), frame)
            self.assertEqual(self.state(writer), before)
            self.assertFalse(writer.poisoned)
        self.assertEqual(len(probe.writes), 1)
        writer.append_frame((129,), records.encode(_event(1)), _frame((129,), _event(1)))
        self.assertEqual(writer.seal().record_count, 2)

    def test_mixed_append_checkpoint_and_seal_keep_exact_dirty_prefix_semantics(self):
        writer, probe = self.framed_probe_writer()
        first_frame = _frame((0,), _event())
        with patch.object(store.os, "fsync") as synced:
            empty = writer.checkpoint()
            writer.append_frame((0,), records.encode(_event()), first_frame)
            self.assertTrue(writer.dirty)
            self.assertIs(writer.last_durable_checkpoint, empty)
            first = writer.checkpoint()
            self.assertFalse(writer.dirty)
            self.assertIs(writer.checkpoint(), first)
            self.assertEqual(synced.call_count, 2)
            with patch.object(store.FramedStreamWriter, "append_frame", side_effect=AssertionError("ordinary append delegated")):
                writer.append((1,), _event(1))
            self.assertTrue(writer.dirty)
            self.assertIs(writer.last_durable_checkpoint, first)
            final = writer.seal()
            self.assertEqual(synced.call_count, 3)
        expected = first_frame + _frame((1,), _event(1))
        self.assertEqual(writer.path.read_bytes(), expected)
        self.assertEqual(final.sha256, hashlib.sha256(expected).hexdigest())
        self.assertEqual((empty.record_count, first.record_count, final.record_count), (0, 1, 2))
        self.assertEqual(probe.calls.count("write"), 2)

    def test_short_partial_and_indeterminate_writes_poison_without_retry(self):
        prefix = _frame((0,), _event())
        attempted = _frame((1,), _event(1))
        for mode, retained in (("short", attempted[:-1]), ("raise", attempted[:3]),
                               ("none", b""), ("bool", b"")):
            with self.subTest(mode=mode):
                directory = self.root / mode
                directory.mkdir()
                digest = _HashProbe()
                with patch.object(store.hashlib, "sha256", return_value=digest):
                    writer, probe = self.framed_probe_writer(root=directory)
                writer.append_frame((0,), records.encode(_event()), prefix)
                snapshot = writer.checkpoint()
                probe.mode = mode
                with self.assertRaises(store.StoreError):
                    writer.append_frame((1,), records.encode(_event(1)), attempted)
                self.assert_framed_poisoned(writer, probe, snapshot)
                with self.assertRaises(store.StoreError):
                    writer.append_frame((1,), records.encode(_event(1)), attempted)
                self.assertEqual((writer.record_count, writer.byte_length, writer.last_key, writer.dirty),
                                 (1, len(prefix), (0,), False))
                self.assertEqual(digest.updates, [prefix])
                self.assertEqual(probe.calls.count("write"), 2)
                writer.close()
                self.assertEqual(writer.path.read_bytes(), prefix + retained)

    def test_hash_failure_after_full_frame_write_poisoned_and_retains_bytes(self):
        digest = _HashProbe()
        with patch.object(store.hashlib, "sha256", return_value=digest):
            writer, probe = self.framed_probe_writer()
        logical, frame = records.encode(_event()), _frame((0,), _event())
        with patch.object(digest, "update", side_effect=RuntimeError("injected hash failure")):
            with self.assertRaises(store.StoreError):
                writer.append_frame((0,), logical, frame)
        self.assert_framed_poisoned(writer, probe, None)
        self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (0, 0, None))
        writer.close()
        self.assertEqual(writer.path.read_bytes(), frame)

    def test_checkpoint_failures_after_exact_append_retain_last_durable_prefix(self):
        for failure in ("flush", "fsync"):
            directory = self.root / failure
            directory.mkdir()
            writer, probe = self.framed_probe_writer(root=directory)
            writer.append_frame((0,), records.encode(_event()), _frame((0,), _event()))
            first = writer.checkpoint()
            writer.append_frame((1,), records.encode(_event(1)), _frame((1,), _event(1)))
            probe.flush_error = failure == "flush"
            with patch.object(store.os, "fsync", side_effect=OSError("fsync failed")) as synced:
                with self.assertRaises(store.StoreError):
                    writer.checkpoint()
                self.assertEqual(synced.call_count, 0 if failure == "flush" else 1)
            self.assert_framed_poisoned(writer, probe, first)
            self.assertTrue(writer.dirty)
            self.assertEqual((first.record_count, writer.record_count), (1, 2))

    def test_sealed_closed_and_cancelled_writers_cannot_append_exact_frames(self):
        logical, frame = records.encode(_event()), _frame((0,), _event())
        for state in ("sealed", "closed", "cancelled"):
            directory = self.root / state
            directory.mkdir()
            writer, probe = self.framed_probe_writer(root=directory)
            if state == "sealed":
                writer.seal()
            elif state == "closed":
                writer.close()
            else:
                marker = KeyboardInterrupt()
                with patch.object(probe, "write", side_effect=marker):
                    with self.assertRaises(KeyboardInterrupt) as caught:
                        writer.append_frame((0,), logical, frame)
                self.assertIs(caught.exception, marker)
                self.assert_framed_poisoned(writer, probe, None)
            calls = tuple(probe.calls)
            with patch.object(physical, "decode_frame", side_effect=AssertionError("unwritable frame decoded")):
                with self.assertRaises(store.StoreError):
                    writer.append_frame((0,), logical, frame)
            self.assertEqual(tuple(probe.calls), calls)


class FramedFailureTests(_FramedRootCase):
    def test_write_failures_retain_evidence_without_retry_or_hash_count_advancement(self):
        prefix = _frame((0,), _event())
        attempted = _frame((1,), _event(1))
        for mode, retained in (("short", attempted[:-1]), ("raise", attempted[:3]),
                               ("none", b""), ("bool", b""), ("ordinary", b"")):
            with self.subTest(mode=mode):
                directory = self.root / mode
                directory.mkdir()
                digest = _HashProbe()
                with patch.object(store.hashlib, "sha256", return_value=digest):
                    writer, probe = self.framed_probe_writer(root=directory)
                writer.append((0,), _event())
                snapshot = writer.checkpoint()
                probe.mode = mode
                if mode == "ordinary":
                    def failure(data):
                        probe.calls.append("write")
                        raise OSError("injected ordinary write failure")
                    operation = patch.object(probe, "write", side_effect=failure)
                else:
                    operation = ExitStack()
                with operation, self.assertRaises(store.StoreError):
                    writer.append((1,), _event(1))
                self.assert_framed_poisoned(writer, probe, snapshot)
                self.assertEqual((writer.record_count, writer.byte_length, writer.last_key), (1, len(prefix), (0,)))
                self.assertEqual(digest.updates, [prefix])
                self.assertEqual(digest.hexdigest(), hashlib.sha256(prefix).hexdigest())
                self.assertEqual(probe.calls.count("write"), 2)
                writer.close()
                self.assertEqual(writer.path.read_bytes(), prefix + retained)

    def test_flush_and_fsync_failures_keep_last_durable_snapshot(self):
        for kind in ("flush", "fsync"):
            with self.subTest(kind=kind):
                directory = self.root / kind
                directory.mkdir()
                writer, probe = self.framed_probe_writer(root=directory)
                writer.append((0,), _event())
                snapshot = writer.checkpoint()
                writer.append((1,), _event(1))
                probe.flush_error = kind == "flush"
                with patch.object(store.os, "fsync", side_effect=OSError("injected fsync failure")) as synced:
                    with self.assertRaises(store.StoreError):
                        writer.checkpoint()
                    self.assertEqual(synced.call_count, 0 if kind == "flush" else 1)
                self.assert_framed_poisoned(writer, probe, snapshot)
                self.assertEqual(snapshot.record_count, 1)
                self.assertEqual(writer.record_count, 2)

    def test_seal_checkpoint_failure_has_no_successful_snapshot(self):
        writer, probe = self.framed_probe_writer()
        writer.append((0,), _event())
        with patch.object(store.os, "fsync", side_effect=OSError("seal sync failed")):
            with self.assertRaises(store.StoreError):
                writer.seal()
        self.assert_framed_poisoned(writer, probe, None)
        self.assertFalse(probe.file.closed)

    def test_clean_seal_close_failure_poisoned_without_extra_sync(self):
        writer, probe = self.framed_probe_writer()
        writer.append((0,), _event())
        snapshot = writer.checkpoint()
        probe.close_error = True
        with patch.object(store.os, "fsync", side_effect=AssertionError("clean seal redundantly synced")):
            with self.assertRaises(store.StoreError):
                writer.seal()
        self.assert_framed_poisoned(writer, probe, snapshot)
        self.assertTrue(probe.file.closed)

    def test_baseexception_during_io_is_preserved_and_poisoned(self):
        for operation, marker in (("write", KeyboardInterrupt()), ("flush", SystemExit("cancel checkpoint")),
                                  ("close", KeyboardInterrupt())):
            with self.subTest(operation=operation):
                directory = self.root / operation
                directory.mkdir()
                writer, probe = self.framed_probe_writer(root=directory)
                snapshot = None
                if operation != "write":
                    writer.append((0,), _event())
                if operation == "close":
                    snapshot = writer.checkpoint()
                with patch.object(probe, operation, side_effect=marker):
                    with self.assertRaises(type(marker)) as caught:
                        if operation == "write":
                            writer.append((0,), _event())
                        elif operation == "flush":
                            writer.checkpoint()
                        else:
                            writer.seal()
                self.assertIs(caught.exception, marker)
                self.assert_framed_poisoned(writer, probe, snapshot)


class FramedScannerTests(_FramedRootCase):
    def test_independent_physical_file_scan_reports_all_visitor_facts(self):
        context = _frame_context()
        values = ((127, _event()), (128, _event(1)), (256, _event(2)))
        frames = [_frame((key,), record, context) for key, record in values]
        data = b"".join(frames)
        self.put_framed(data)
        visited = []
        fresh = _frame_context()
        self.assertIsNot(fresh, context)
        result = store.scan_framed_stream(self.root, "operations", fresh, visit=lambda *facts: visited.append(facts))
        self.assertEqual(result, records.StreamDigest("operations", hashlib.sha256(data).hexdigest(), len(data), len(values)))
        self.assertEqual(visited, [((key,), record, records.encode(record), len(frame))
                                   for (key, record), frame in zip(values, frames)])

    def test_wrong_profile_or_stream_context_fails_without_visits(self):
        self.put_framed(_frame((0,), _event()))
        visited = []
        wrong_profile = physical.context_for("operations", b"\x6b" * 32)
        for context in (wrong_profile, _frame_context("postprocessing_operations")):
            with self.subTest(context=context), self.assertRaises(store.StoreError):
                store.scan_framed_stream(self.root, "operations", context, visit=lambda *facts: visited.append(facts))
        self.assertEqual(visited, [])

    def test_duplicate_and_descending_numeric_keys_fail_at_second_frame(self):
        for keys in (((128,), (128,)), ((256,), (255,))):
            self.put_framed(b"".join(_frame(key, _event()) for key in keys))
            visited = []
            with self.subTest(keys=keys), self.assertRaises(store.StoreError):
                store.scan_framed_stream(self.root, "operations", _frame_context(), visit=lambda *facts: visited.append(facts[0]))
            self.assertEqual(visited, [keys[0]])

    def test_every_nonempty_truncated_prefix_key_payload_and_crc_fails(self):
        frame = _frame((128,), _event())
        payload_end = len(frame) - 4
        # One complete 9-byte prefix, a two-byte ULEB key, payload, and four CRC bytes.
        classes = {"prefix": range(1, 9), "key": (9, 10),
                   "payload": (11, 12, payload_end - 1), "crc": range(payload_end, len(frame))}
        for part, cuts in classes.items():
            for cut in cuts:
                with self.subTest(component=part, cut=cut):
                    self.put_framed(frame[:cut])
                    with self.assertRaises(store.StoreError):
                        store.scan_framed_stream(self.root, "operations", _frame_context())

    def test_corrupt_middle_frame_stops_without_resynchronizing_or_repair(self):
        frames = [_frame((i,), _event(i)) for i in range(3)]
        bad = bytearray(frames[1])
        bad[-1] ^= 1
        data = frames[0] + bytes(bad) + frames[2]
        path = self.put_framed(data)
        probe = _FramedReadProbe(path.open("rb"))
        self.addCleanup(probe.file.close)
        visited = []
        with patch.object(store.Path, "open", return_value=probe):
            with self.assertRaises(store.StoreError):
                store.scan_framed_stream(self.root, "operations", _frame_context(), visit=lambda *facts: visited.append(facts[0]))
        self.assertEqual(visited, [(0,)])
        self.assertEqual(probe.position, len(frames[0]) + len(frames[1]))
        self.assertEqual(path.read_bytes(), data)

    def test_trailing_garbage_is_not_ignored_or_interpreted_as_another_format(self):
        frame = _frame((0,), _event())
        for suffix in (b"\0", b"\n", b"PKE2RF02", b"garbage\n", _line((1,), _event(1))):
            with self.subTest(suffix=suffix):
                self.put_framed(frame + suffix)
                with self.assertRaises(store.StoreError):
                    store.scan_framed_stream(self.root, "operations", _frame_context())

    def test_visitor_exception_is_unchanged_and_prevents_reading_next_frame(self):
        frames = [_frame((i,), _event(i)) for i in range(2)]
        path = self.put_framed(b"".join(frames))
        probe = _FramedReadProbe(path.open("rb"))
        self.addCleanup(probe.file.close)
        probe.close_error = True
        marker = OSError("exact visitor failure")
        def visitor(*facts):
            raise marker
        with patch.object(store.Path, "open", return_value=probe):
            with self.assertRaises(OSError) as caught:
                store.scan_framed_stream(self.root, "operations", _frame_context(), visit=visitor)
        self.assertIs(caught.exception, marker)
        self.assertEqual(probe.position, len(frames[0]))
        self.assertTrue(probe.file.closed)

    def test_bounded_component_reads_and_incremental_hash_under_short_reads(self):
        keys = ((0,), (128,), ((1 << 64) - 1,))
        frames = [_frame(key, _event(i)) for i, key in enumerate(keys)]
        data = b"".join(frames)
        limits = {}
        offset = 0
        for key, frame in zip(keys, frames):
            for index in range(9):
                limits[offset + index] = 9 - index
            key_width = len(physical.encode_uleb128(key[0]))
            for index in range(key_width):
                limits[offset + 9 + index] = 1
            payload_start = offset + 9 + key_width
            for position in range(payload_start, offset + len(frame)):
                limits[position] = offset + len(frame) - position
            offset += len(frame)
        path = self.put_framed(data)
        probe = _FramedReadProbe(path.open("rb"), limits, fragment=3)
        self.addCleanup(probe.file.close)
        digest = _HashProbe()
        real_decode = physical.decode_frame
        with patch.object(store.Path, "open", return_value=probe), \
                patch.object(store.Path, "read_bytes", side_effect=AssertionError("scanner read all")), \
                patch.object(store.hashlib, "sha256", return_value=digest), \
                patch.object(physical, "decode_frame", wraps=real_decode) as decoded:
            result = store.scan_framed_stream(self.root, "operations", _frame_context())
        self.assertEqual(decoded.call_count, len(frames))
        self.assertEqual([call.args[0] for call in decoded.call_args_list], frames)
        self.assertEqual(digest.updates, frames)
        self.assertEqual(result.sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual(result.byte_length, len(data))
        self.assertEqual(probe.reads[-1], (len(data), 9))
        self.assertTrue(probe.file.closed)

    def test_unchecked_declared_lengths_fail_before_key_payload_reads_or_decode(self):
        cap = 256
        cases = ((0, cap + 1, cap + 1), (1, cap + 1, 1), (0, 0xffffffff, 0xffffffff), (1, 2, 0xffffffff))
        for mode, logical, payload in cases:
            prefix = bytes((mode,)) + logical.to_bytes(4, "big") + payload.to_bytes(4, "big")
            path = self.put_framed(prefix)
            probe = _FramedReadProbe(path.open("rb"), {0: 9})
            self.addCleanup(probe.file.close)
            with self.subTest(logical=logical, payload=payload), \
                    patch.object(store.Path, "open", return_value=probe), \
                    patch.object(physical, "decode_frame", side_effect=AssertionError("unbounded declaration reached decoder")):
                with self.assertRaises(store.StoreError):
                    store.scan_framed_stream(self.root, "operations", _frame_context(), max_payload_bytes=cap)
            self.assertEqual(probe.reads, [(0, 9)])

    def test_uleb_key_limit_and_noncanonical_encodings_fail_closed(self):
        frame = _frame((0,), _event())
        for encoded_key in (b"\x80" * 10, b"\x80\x00", b"\xff" * 9 + b"\x02"):
            row = frame[:9] + encoded_key + frame[10:-4]
            forged = row + physical.contextual_crc32(_frame_context(), row).to_bytes(4, "big")
            path = self.put_framed(forged)
            probe = _FramedReadProbe(path.open("rb"))
            self.addCleanup(probe.file.close)
            with self.subTest(key=encoded_key), patch.object(store.Path, "open", return_value=probe):
                with self.assertRaises(store.StoreError):
                    store.scan_framed_stream(self.root, "operations", _frame_context())
            if encoded_key == b"\x80" * 10:
                self.assertEqual(probe.position, 19)
                self.assertEqual(probe.reads, [(0, 9)] + [(offset, 1) for offset in range(9, 19)])

    def test_crc_valid_wrong_family_and_noncanonical_logical_record_are_rejected(self):
        context = _frame_context()
        for logical in (records.encode(_board()), records.encode(_event()) + b" ", b"{}"):
            row = b"\0" + len(logical).to_bytes(4, "big") * 2 + b"\0" + logical
            frame = row + physical.contextual_crc32(context, row).to_bytes(4, "big")
            self.put_framed(frame)
            with self.subTest(logical=logical), self.assertRaises(store.StoreError):
                store.scan_framed_stream(self.root, "operations", context)

    def test_invalid_context_bound_or_visitor_rejected_before_file_open(self):
        self.put_framed(b"")
        with patch.object(store.Path, "open", side_effect=AssertionError("invalid argument opened evidence")):
            for context in (None, object(), _frame_context("boards")):
                with self.assertRaises(store.StoreError):
                    store.scan_framed_stream(self.root, "operations", context)
            for bound in (True, 0, -1, physical.MAX_PAYLOAD_BYTES + 1):
                with self.assertRaises(store.StoreError):
                    store.scan_framed_stream(self.root, "operations", _frame_context(), max_payload_bytes=bound)
            with self.assertRaises(store.StoreError):
                store.scan_framed_stream(self.root, "operations", _frame_context(), visit=1)

    def test_missing_file_read_error_and_reparse_target_fail_closed(self):
        with self.assertRaises(store.StoreError):
            store.scan_framed_stream(self.root, "operations", _frame_context())
        path = self.put_framed(_frame((0,), _event()))
        probe = _FramedReadProbe(path.open("rb"))
        self.addCleanup(probe.file.close)
        with patch.object(store.Path, "open", return_value=probe), \
                patch.object(probe, "read", side_effect=OSError("injected read failure")):
            with self.assertRaises(store.StoreError):
                store.scan_framed_stream(self.root, "operations", _frame_context())
        self.assertTrue(probe.file.closed)
        info = types.SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        with patch.object(store.Path, "lstat", return_value=info), patch.object(store.Path, "open") as opened:
            with self.assertRaises(store.StoreError):
                store.scan_framed_stream(self.root, "operations", _frame_context())
            opened.assert_not_called()


class FramedV1BoundaryTests(_FramedRootCase):
    def test_v1_and_rf02_same_name_coexist_with_separate_exact_apis(self):
        legacy = self.writer("operations")
        framed = self.framed_writer()
        with patch.object(physical, "encode_frame", side_effect=AssertionError("V1 used RF02 encoder")):
            legacy.append((0,), _event())
            legacy_digest = legacy.seal()
        framed.append((0,), _event())
        framed_digest = framed.seal()
        self.assertEqual(legacy.path.name, "operations.jsonl")
        self.assertEqual(framed.path.name, "operations.pkf")
        self.assertEqual(legacy.path.read_bytes(), _line((0,), _event()))
        self.assertEqual(framed.path.read_bytes(), _frame((0,), _event()))
        with patch.object(store, "scan_framed_stream", side_effect=AssertionError("V1 fell back to RF02")), \
                patch.object(physical, "decode_frame", side_effect=AssertionError("V1 decoded RF02")):
            self.assertEqual(store.scan_stream(self.root, "operations"), legacy_digest)
        with patch.object(store, "scan_stream", side_effect=AssertionError("RF02 fell back to V1")):
            self.assertEqual(store.scan_framed_stream(self.root, "operations", _frame_context()), framed_digest)

    def test_cross_format_bytes_fail_without_fallback_to_other_existing_file(self):
        self.put("operations", _frame((0,), _event()))
        self.put_framed(_line((0,), _event()))
        with patch.object(store, "scan_framed_stream", side_effect=AssertionError("legacy fallback")):
            with self.assertRaises(store.StoreError):
                store.scan_stream(self.root, "operations")
        with patch.object(store, "scan_stream", side_effect=AssertionError("framed fallback")):
            with self.assertRaises(store.StoreError):
                store.scan_framed_stream(self.root, "operations", _frame_context())

    def test_public_framed_api_has_exact_frame_validation_seam_without_trust_bypass(self):
        parameters = tuple(inspect.signature(store.FramedStreamWriter.append).parameters)
        self.assertEqual(parameters, ("self", "key", "record"))
        self.assertEqual(tuple(inspect.signature(store.FramedStreamWriter.append_frame).parameters),
                         ("self", "key", "logical_bytes", "frame_bytes"))
        for name in dir(store.FramedStreamWriter):
            if not name.startswith("_"):
                self.assertNotIn(name, {"append_validated", "append_trusted", "append_raw"})
        tree = ast.parse(inspect.getsource(store))
        forbidden = {"program_k_e2_execution", "program_k_e2_operational", "program_k_e2_readiness", "program_k_e2_r0_harness"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self.assertFalse({alias.name for alias in node.names}.intersection(forbidden))


class _PullReadProbe(_FramedReadProbe):
    def __init__(self, file, **kwargs):
        super().__init__(file, **kwargs)
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        super().close()


class FramedPullReaderTests(_FramedRootCase):
    def reader(self, name="operations", *, context=None, **kwargs):
        reader = store.FramedStreamPullReader(self.root, name, context or _frame_context(name), **kwargs)
        self.addCleanup(reader.invalidate)
        return reader

    def probe_reader(self, name="operations", *, fragment=None, **kwargs):
        probe = _PullReadProbe((self.root / (name + ".pkf")).open("rb", buffering=0), fragment=fragment)
        self.addCleanup(probe.file.close)
        with patch.object(store.Path, "open", return_value=probe) as opened:
            reader = self.reader(name, **kwargs)
        opened.assert_called_once_with("rb", buffering=0)
        return reader, probe

    def raw_coverage_frame(self, payload_bytes):
        # Coverage is an existing raw-only family. A canonical ASCII identity
        # gives an exact serialized size without entropy or compression search.
        arm = records.ArmIdentity(records.Arm.K_P0, _board(), "x", "synthetic-unit")
        record = records.OracleBCoverageRecord(arm, True, ())
        baseline = len(records.encode(record))
        self.assertGreaterEqual(payload_bytes, baseline)
        record = replace(record, arm=replace(arm, run_id="x" * (payload_bytes - baseline + 1)))
        logical = records.encode(record)
        self.assertEqual(len(logical), payload_bytes)
        frame = physical.encode_frame(logical, (0, 0, 0), _frame_context("oracle_b_coverage"))
        self.assertEqual(frame[0], physical.RAW)
        self.assertEqual(int.from_bytes(frame[1:5], "big"), payload_bytes)
        self.assertEqual(int.from_bytes(frame[5:9], "big"), payload_bytes)
        return record, logical, frame

    def test_large_raw_payload_reads_in_bounded_chunks_and_matches_eager_scanner(self):
        record, logical, frame = self.raw_coverage_frame(3 * 65536 + 13)
        self.put_framed(frame, "oracle_b_coverage")
        eager_rows = []
        eager_digest = store.scan_framed_stream(self.root, "oracle_b_coverage",
            _frame_context("oracle_b_coverage"),
            visit=lambda key, value, raw, length: eager_rows.append((key, value, raw, length)))
        expected = ((0, 0, 0), record, logical, len(frame))
        self.assertEqual(eager_rows, [expected])
        for fragment in (None, 16381):
            with self.subTest(fragment=fragment):
                reader, probe = self.probe_reader("oracle_b_coverage", fragment=fragment)
                self.assertEqual(reader.peek_key(), (0, 0, 0))
                prefix_reads = len(probe.reads)
                self.assertEqual(probe.position, 12)
                row = reader.pull()
                self.assertEqual((row.key, row.record, row.logical_bytes, row.frame_length), expected)
                self.assertEqual(probe.position, len(frame))
                remainder_reads = probe.reads[prefix_reads:]
                self.assertGreaterEqual(sum(size == 65536 for _, size in remainder_reads), 3)
                if fragment is None:
                    self.assertEqual([size for _, size in remainder_reads], [65536, 65536, 65536, 17])
                self.assertTrue(all(1 <= size <= 65536 for _, size in probe.reads))
                self.assertIsNone(reader.completed_digest)
                self.assertIsNone(reader.pull())
                self.assertTrue(all(1 <= size <= 65536 for _, size in probe.reads))
                self.assertEqual(reader.close(), eager_digest)
                self.assertEqual(reader.completed_digest, eager_digest)
                self.assertEqual(probe.close_calls, 1)
                self.assertTrue(probe.file.closed)

    def test_payload_and_remainder_chunk_boundaries_before_exact_and_after_65536(self):
        for boundary_kind in ("payload", "payload_plus_crc"):
            for size in (65535, 65536, 65537):
                payload = size if boundary_kind == "payload" else size - 4
                record, logical, frame = self.raw_coverage_frame(payload)
                self.put_framed(frame, "oracle_b_coverage")
                reader, probe = self.probe_reader("oracle_b_coverage")
                with self.subTest(boundary=boundary_kind, size=size):
                    self.assertEqual(reader.peek_key(), (0, 0, 0))
                    prefix_reads = len(probe.reads)
                    row = reader.pull()
                    self.assertEqual((row.key, row.record, row.logical_bytes, row.frame_length),
                                     ((0, 0, 0), record, logical, len(frame)))
                    remainder = payload + 4
                    expected_reads = [65536] * (remainder // 65536)
                    if remainder % 65536:
                        expected_reads.append(remainder % 65536)
                    self.assertEqual([count for _, count in probe.reads[prefix_reads:]], expected_reads)
                    self.assertTrue(all(1 <= count <= 65536 for _, count in probe.reads))
                    self.assertEqual(probe.position, len(frame))
                    self.assertIsNone(reader.pull())
                    expected = records.StreamDigest("oracle_b_coverage",
                        hashlib.sha256(frame).hexdigest(), len(frame), 1)
                    self.assertEqual(reader.close(), expected)

    def test_large_raw_payload_truncated_final_chunk_invalidates_without_decode_or_digest(self):
        _, _, frame = self.raw_coverage_frame(2 * 65536 + 1)
        truncated = frame[:-1]
        path = self.put_framed(truncated, "oracle_b_coverage")
        digest = _HashProbe()
        with patch.object(store.hashlib, "sha256", return_value=digest):
            reader, probe = self.probe_reader("oracle_b_coverage")
        self.assertEqual(reader.peek_key(), (0, 0, 0))
        prefix_reads = len(probe.reads)
        with patch.object(physical, "decode_frame", side_effect=AssertionError("Truncated frame decoded")) as decoded:
            with self.assertRaises(store.StoreError):
                reader.pull()
            decoded.assert_not_called()
        self.assertEqual([count for _, count in probe.reads[prefix_reads:]], [65536, 65536, 5, 1])
        self.assertTrue(all(1 <= count <= 65536 for _, count in probe.reads))
        self.assertEqual(probe.position, len(truncated))
        self.assertEqual(digest.updates, [])
        self.assertTrue(probe.file.closed)
        self.assertEqual(probe.close_calls, 1)
        self.assertIsNone(reader.close())
        self.assertIsNone(reader.completed_digest)
        reads = tuple(probe.reads)
        with self.assertRaises(store.StoreError):
            reader.pull()
        self.assertEqual(tuple(probe.reads), reads)
        self.assertEqual(path.read_bytes(), truncated)

    def test_large_raw_payload_mid_chunk_interrupt_and_io_failure_do_not_retry(self):
        _, _, frame = self.raw_coverage_frame(3 * 65536 + 13)
        for fault in (KeyboardInterrupt, OSError):
            path = self.put_framed(frame, "oracle_b_coverage")
            digest = _HashProbe()
            with patch.object(store.hashlib, "sha256", return_value=digest):
                reader, probe = self.probe_reader("oracle_b_coverage")
            self.assertEqual(reader.peek_key(), (0, 0, 0))
            original_read = probe.read
            attempted = []
            marker = fault("injected second payload-chunk failure")
            def read(size):
                attempted.append((probe.position, size))
                if len(attempted) == 2:
                    probe.reads.append((probe.position, size))
                    raise marker
                return original_read(size)
            expected_error = KeyboardInterrupt if fault is KeyboardInterrupt else store.StoreError
            with self.subTest(fault=fault.__name__), patch.object(probe, "read", side_effect=read), \
                    patch.object(physical, "decode_frame", side_effect=AssertionError("Partial frame decoded")) as decoded:
                with self.assertRaises(expected_error) as caught:
                    reader.pull()
                decoded.assert_not_called()
            if fault is KeyboardInterrupt:
                self.assertIs(caught.exception, marker)
            else:
                self.assertIs(caught.exception.__cause__, marker)
            self.assertEqual(attempted, [(12, 65536), (12 + 65536, 65536)])
            self.assertTrue(all(1 <= count <= 65536 for _, count in probe.reads))
            self.assertEqual(probe.position, 12 + 65536)
            self.assertEqual(digest.updates, [])
            self.assertTrue(probe.file.closed)
            self.assertEqual(probe.close_calls, 1)
            self.assertIsNone(reader.close())
            self.assertIsNone(reader.completed_digest)
            reads = tuple(probe.reads)
            with self.assertRaises(store.StoreError):
                reader.pull()
            self.assertEqual(tuple(probe.reads), reads)
            self.assertEqual(path.read_bytes(), frame)

    def test_exact_current_rows_incremental_digest_and_no_next_prefix_prefetch(self):
        frames = [_frame((index,), _event(index)) for index in (127, 128, 256)]
        data = b"".join(frames)
        self.put_framed(data)
        digest = _HashProbe()
        with patch.object(store.hashlib, "sha256", return_value=digest):
            reader, probe = self.probe_reader(fragment=3)
        self.assertEqual(probe.reads, [])
        offset = 0
        real_decode = physical.decode_frame
        with patch.object(physical, "decode_frame", wraps=real_decode) as decoded:
            for index, frame in zip((127, 128, 256), frames):
                row = reader.pull()
                self.assertIs(type(row), store.FramedStreamRow)
                self.assertEqual((row.key, row.record, row.logical_bytes, row.frame_length),
                                 ((index,), _event(index), records.encode(_event(index)), len(frame)))
                with self.assertRaises(FrozenInstanceError):
                    row.key = (0,)
                self.assertFalse(hasattr(row, "validated"))
                offset += len(frame)
                self.assertEqual(probe.position, offset)
                self.assertEqual(reader._pending_prefix, b"")
                self.assertIsNone(reader.completed_digest)
                del row
            self.assertEqual(decoded.call_count, 3)
            self.assertEqual([call.args[0] for call in decoded.call_args_list], frames)
            self.assertEqual([call.kwargs["expected_key"] for call in decoded.call_args_list],
                             [(127,), (128,), (256,)])
            self.assertIsNone(reader.pull())
            self.assertIsNone(reader.peek_key())
            self.assertEqual(decoded.call_count, 3)
        self.assertIsNone(reader.completed_digest)
        self.assertEqual(digest.updates, frames)
        expected = records.StreamDigest("operations", hashlib.sha256(data).hexdigest(), len(data), 3)
        self.assertEqual(reader.close(), expected)
        self.assertEqual(reader.completed_digest, expected)
        self.assertIs(reader.close(), reader.completed_digest)
        self.assertEqual(probe.close_calls, 1)
        self.assertTrue(probe.file.closed)
        for call in (reader.peek_key, reader.pull):
            with self.assertRaises(store.StoreError):
                call()

    def test_maximum_39_byte_pending_prefix_does_not_decode_or_inflate(self):
        key = ((1 << 64) - 1,) * 3
        frame = _frame(key, _board(), _frame_context("boards"))
        self.put_framed(frame, "boards")
        with patch.object(physical, "decode_frame", side_effect=AssertionError("peek decoded frame")), \
                patch.object(physical, "decode_payload", side_effect=AssertionError("peek inflated")), \
                patch.object(records, "decode", side_effect=AssertionError("peek decoded record")):
            reader, probe = self.probe_reader("boards")
            self.assertEqual(probe.position, 0)
            self.assertEqual(reader.peek_key(), key)
            self.assertEqual(reader.peek_key(), key)
            self.assertEqual(probe.position, 39)
            self.assertEqual(reader._pending_prefix, frame[:39])
            self.assertEqual(probe.reads, [(0, 9)] + [(index, 1) for index in range(9, 39)])
            self.assertIsNone(reader.completed_digest)
            self.assertIsNone(reader.close())

    def test_all_current_materializer_streams_peek_within_57_prefix_reservation_without_inflation(self):
        from experiments import program_k_e2_execution as execution

        specs = tuple(spec for spec in physical.STREAM_REGISTRY
                      if spec.name not in ("qualification_identity", "postprocessing_operations"))
        self.assertEqual(tuple(spec.name for spec in specs), execution.STREAM_NAMES + ("operations", "resources"))
        self.assertLessEqual(len(specs), 57)
        frames = {}
        for spec in specs:
            # A prefix is deliberately not evidence: most payloads below are not
            # records for their stream, yet discovery must not interpret them.
            context = _frame_context(spec.name)
            logical = records.encode(_event())
            prefix = b"\0" + len(logical).to_bytes(4, "big") * 2 + b"\0" * spec.key_arity
            body = prefix + logical
            frames[spec.name] = body + physical.contextual_crc32(context, body).to_bytes(4, "big")
            self.put_framed(frames[spec.name], spec.name)
        readers = []
        real_decode = physical.decode_frame
        with patch.object(physical, "decode_frame", wraps=real_decode) as decoded, \
                patch.object(physical, "decode_payload", wraps=physical.decode_payload) as inflated:
            for spec in specs:
                reader = self.reader(spec.name)
                readers.append(reader)
                self.assertEqual(reader.peek_key(), (0,) * spec.key_arity)
                self.assertLessEqual(len(reader._pending_prefix), 39)
            self.assertLessEqual(sum(len(reader._pending_prefix) for reader in readers), 57 * 39)
            decoded.assert_not_called()
            inflated.assert_not_called()
            chosen = readers[next(index for index, spec in enumerate(specs) if spec.name == "operations")]
            row = chosen.pull()
            self.assertEqual(row.record, _event())
            self.assertEqual(decoded.call_count, 1)
            self.assertEqual(inflated.call_count, 1)
            self.assertEqual(decoded.call_args.args[0], frames["operations"])
            del row
        for reader in readers:
            self.assertIsNone(reader.completed_digest)
            reader.invalidate()

    def test_peek_is_unauthenticated_and_bad_crc_fails_only_at_full_pull(self):
        frame = bytearray(_frame((128,), _event()))
        frame[-1] ^= 1
        data = bytes(frame)
        path = self.put_framed(data)
        reader, probe = self.probe_reader()
        self.assertEqual(reader.peek_key(), (128,))
        self.assertEqual(probe.position, 11)
        with self.assertRaises(store.StoreError):
            reader.pull()
        self.assertEqual(probe.position, len(data))
        self.assertTrue(probe.file.closed)
        self.assertEqual(probe.close_calls, 1)
        self.assertIsNone(reader.close())
        self.assertIsNone(reader.completed_digest)
        self.assertEqual(path.read_bytes(), data)

    def test_strict_numeric_order_is_checked_only_after_complete_frame_validation(self):
        for keys in (((128,), (128,)), ((256,), (255,))):
            frames = [_frame(key, _event(index)) for index, key in enumerate(keys)]
            self.put_framed(b"".join(frames))
            reader, probe = self.probe_reader()
            reader.pull()
            self.assertEqual(reader.peek_key(), keys[1])
            with self.subTest(keys=keys), \
                    patch.object(physical, "decode_frame", wraps=physical.decode_frame) as decoded:
                with self.assertRaisesRegex(store.StoreError, "Duplicate/descending"):
                    reader.pull()
                decoded.assert_called_once()
            self.assertEqual(probe.position, sum(map(len, frames)))
            self.assertIsNone(reader.completed_digest)
            self.assertIsNone(reader.close())

    def test_empty_eof_requires_successful_close_and_early_close_is_not_completion(self):
        self.put_framed(b"")
        reader = self.reader()
        self.assertIsNone(reader.completed_digest)
        self.assertIsNone(reader.peek_key())
        self.assertIsNone(reader.completed_digest)
        self.assertEqual(reader.close(), records.StreamDigest("operations", hashlib.sha256(b"").hexdigest(), 0, 0))
        for consumed in (False, True):
            self.put_framed(_frame((0,), _event()))
            reader = self.reader()
            if consumed:
                reader.pull()
            self.assertIsNone(reader.close())  # Even a complete row is not observed EOF.
            self.assertIsNone(reader.completed_digest)

    def test_successful_context_exit_publishes_digest_and_early_exit_does_not(self):
        frame = _frame((0,), _event())
        self.put_framed(frame)
        with self.reader() as reader:
            self.assertEqual(reader.pull().record, _event())
            self.assertIsNone(reader.pull())
            self.assertIsNone(reader.completed_digest)
        self.assertEqual(reader.completed_digest.byte_length, len(frame))
        with self.reader() as early:
            early.peek_key()
        self.assertIsNone(early.completed_digest)

    def test_outer_user_failure_invalidates_and_preserves_exact_exception(self):
        frames = [_frame((index,), _event(index)) for index in range(2)]
        self.put_framed(b"".join(frames))
        reader, probe = self.probe_reader()
        probe.close_error = True
        marker = OSError("outer semantic/user failure")
        with self.assertRaises(OSError) as caught:
            with reader:
                reader.pull()
                raise marker
        self.assertIs(caught.exception, marker)
        self.assertEqual(probe.position, len(frames[0]))
        self.assertTrue(probe.file.closed)
        self.assertEqual(probe.close_calls, 1)
        self.assertIsNone(reader.completed_digest)

    def test_later_outer_failure_can_invalidate_an_already_closed_reader_digest(self):
        self.put_framed(b"")
        reader = self.reader()
        marker = RuntimeError("another stream failed")
        with self.assertRaises(RuntimeError) as caught:
            with reader:
                self.assertIsNone(reader.peek_key())
                self.assertIsNotNone(reader.close())
                raise marker
        self.assertIs(caught.exception, marker)
        self.assertIsNone(reader.completed_digest)
        self.assertIsNone(reader.close())
        reader.invalidate()
        for call in (reader.peek_key, reader.pull, reader.__enter__):
            with self.assertRaises(store.StoreError):
                call()

    def test_close_failure_cannot_publish_digest_and_never_retries_close(self):
        self.put_framed(b"")
        reader, probe = self.probe_reader()
        self.assertIsNone(reader.pull())
        probe.close_error = True
        with self.assertRaises(store.StoreError):
            reader.close()
        self.assertIsNone(reader.completed_digest)
        self.assertIsNone(reader.close())
        reader.invalidate()
        self.assertEqual(probe.close_calls, 1)

    def test_read_and_decode_cancellation_preserve_exception_and_invalidate(self):
        for stage in ("peek", "pull"):
            self.put_framed(_frame((0,), _event()))
            reader, probe = self.probe_reader()
            marker = KeyboardInterrupt("cancelled " + stage)
            if stage == "pull":
                reader.peek_key()
            owner, attribute = (probe, "read") if stage == "peek" else (physical, "decode_frame")
            with self.subTest(stage=stage), patch.object(owner, attribute, side_effect=marker):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    reader.peek_key() if stage == "peek" else reader.pull()
            self.assertIs(caught.exception, marker)
            self.assertTrue(probe.file.closed)
            self.assertIsNone(reader.completed_digest)
            self.assertIsNone(reader.close())

    def test_truncated_prefix_key_payload_and_crc_and_trailing_bytes_fail_closed(self):
        frame = _frame((128,), _event())
        cuts = tuple(range(1, 12)) + (len(frame) - 5,) + tuple(range(len(frame) - 4, len(frame)))
        for data in tuple(frame[:cut] for cut in cuts) + (frame + b"\0", frame + _line((129,), _event())):
            path = self.put_framed(data)
            reader, probe = self.probe_reader()
            with self.subTest(length=len(data)), self.assertRaises(store.StoreError):
                while reader.pull() is not None:
                    pass
            self.assertTrue(probe.file.closed)
            self.assertIsNone(reader.completed_digest)
            self.assertIsNone(reader.close())
            self.assertEqual(path.read_bytes(), data)

    def test_declared_cap_rejected_before_key_or_payload_read(self):
        for logical, payload in ((257, 1), (1, 257), (0xffffffff, 0xffffffff)):
            self.put_framed(b"\0" + logical.to_bytes(4, "big") + payload.to_bytes(4, "big"))
            reader, probe = self.probe_reader(max_payload_bytes=256)
            with self.subTest(logical=logical, payload=payload), \
                    patch.object(physical, "decode_frame", side_effect=AssertionError("decoded oversized declaration")):
                with self.assertRaises(store.StoreError):
                    reader.peek_key()
            self.assertEqual(probe.reads, [(0, 9)])
            self.assertIsNone(reader.completed_digest)

    def test_noncanonical_overlong_and_overflowing_keys_fail_in_bounded_prefix(self):
        frame = _frame((0,), _event())
        for key in (b"\x80\0", b"\x80" * 10, b"\xff" * 9 + b"\x02"):
            self.put_framed(frame[:9] + key + frame[10:])
            reader, probe = self.probe_reader()
            with self.subTest(key=key), \
                    patch.object(physical, "decode_frame", side_effect=AssertionError("decoded malformed key")):
                with self.assertRaises(store.StoreError):
                    reader.peek_key()
            self.assertLessEqual(probe.position, 19)
            self.assertIsNone(reader.completed_digest)

    def test_wrong_profile_mode_arity_family_and_noncanonical_record_never_return_row(self):
        context = _frame_context()
        cases = [(_frame((0,), _event()), physical.context_for("operations", b"\x6b" * 32))]
        for logical in (records.encode(_board()), records.encode(_event()) + b" ", b"{}"):
            row = b"\0" + len(logical).to_bytes(4, "big") * 2 + b"\0" + logical
            cases.append((row + physical.contextual_crc32(context, row).to_bytes(4, "big"), context))
        for mode in (1, 2):
            logical = records.encode(_event())
            row = bytes((mode,)) + len(logical).to_bytes(4, "big") * 2 + b"\0" + logical
            cases.append((row + physical.contextual_crc32(context, row).to_bytes(4, "big"), context))
        cases.append((_frame((0, 0, 0), _board(), _frame_context("boards")), context))
        for data, supplied in cases:
            self.put_framed(data)
            reader = self.reader(context=supplied)
            self.assertEqual(reader.peek_key(), (0,))
            with self.subTest(data=data, supplied=supplied), self.assertRaises(store.StoreError):
                reader.pull()
            self.assertIsNone(reader.completed_digest)
            self.assertIsNone(reader.close())

    def test_corrupt_middle_row_never_resynchronizes_or_hashes_invalid_frame(self):
        frames = [_frame((index,), _event(index)) for index in range(3)]
        bad = bytearray(frames[1])
        bad[-1] ^= 1
        data = frames[0] + bytes(bad) + frames[2]
        self.put_framed(data)
        digest = _HashProbe()
        with patch.object(store.hashlib, "sha256", return_value=digest):
            reader, probe = self.probe_reader()
        self.assertEqual(reader.pull().key, (0,))
        with self.assertRaises(store.StoreError):
            reader.pull()
        self.assertEqual(probe.position, len(frames[0]) + len(frames[1]))
        self.assertEqual(digest.updates, frames[:1])
        reads = tuple(probe.reads)
        with self.assertRaises(store.StoreError):
            reader.pull()
        self.assertEqual(tuple(probe.reads), reads)
        self.assertIsNone(reader.completed_digest)

    def test_read_fault_indeterminate_read_hash_fault_and_counter_overflow_fail_closed(self):
        for fault in ("read", "indeterminate", "hash", "count"):
            self.put_framed(_frame((0,), _event()))
            reader, probe = self.probe_reader()
            with self.subTest(fault=fault), ExitStack() as stack:
                if fault == "read":
                    stack.enter_context(patch.object(probe, "read", side_effect=OSError("read failed")))
                elif fault == "indeterminate":
                    stack.enter_context(patch.object(probe, "read", return_value=None))
                elif fault == "hash":
                    def fail_hash(data):
                        raise RuntimeError("hash failed")
                    reader._hash = types.SimpleNamespace(update=fail_hash)
                else:
                    reader._record_count = (1 << 64) - 1
                with self.assertRaises((store.StoreError, RuntimeError)):
                    reader.pull()
            self.assertTrue(probe.file.closed)
            self.assertIsNone(reader.completed_digest)
            self.assertIsNone(reader.close())

    def test_invalid_context_limit_missing_file_and_reparse_fail_before_read(self):
        with patch.object(store.Path, "open", side_effect=AssertionError("invalid input opened file")):
            for context in (None, object(), _frame_context("boards")):
                with self.assertRaises(store.StoreError):
                    store.FramedStreamPullReader(self.root, "operations", context)
            for limit in (True, 0, -1, physical.MAX_PAYLOAD_BYTES + 1):
                with self.assertRaises(store.StoreError):
                    self.reader(max_payload_bytes=limit)
        with self.assertRaises(store.StoreError):
            self.reader()
        self.put_framed(b"")
        for info in (types.SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0),
                     types.SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)):
            with patch.object(store.Path, "lstat", return_value=info), patch.object(store.Path, "open") as opened:
                with self.assertRaises(store.StoreError):
                    self.reader()
                opened.assert_not_called()

    def test_reader_owns_context_copy_and_never_uses_legacy_or_scan_api(self):
        context = _frame_context()
        self.put_framed(_frame((0,), _event(), context))
        reader = self.reader(context=context)
        object.__setattr__(context, "codec_profile_sha256", b"\x6b" * 32)
        with patch.object(store, "scan_stream", side_effect=AssertionError("pull fell back to JSONL")), \
                patch.object(store, "scan_framed_stream", side_effect=AssertionError("pull invoked eager scanner")), \
                patch.object(store.Path, "read_bytes", side_effect=AssertionError("pull read all bytes")):
            self.assertEqual(reader.pull().record, _event())
            self.assertIsNone(reader.pull())
            self.assertIsNotNone(reader.close())
        self.put("events", _line((0,), _event()))
        with patch.object(store, "FramedStreamPullReader", side_effect=AssertionError("V1 opened pull reader")), \
                patch.object(physical, "decode_frame", side_effect=AssertionError("V1 decoded RF02")):
            self.assertEqual(store.scan_stream(self.root, "events").record_count, 1)


if __name__ == "__main__":
    unittest.main()
