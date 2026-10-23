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


if __name__ == "__main__":
    unittest.main()
