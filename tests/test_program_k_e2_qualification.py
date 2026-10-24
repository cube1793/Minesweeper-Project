"""I7 integration qualification of tiny synthetic durable evidence only.

The accepted I6 literal materialization seam supplies bounded solver fixtures.
The coordinator's workflow is replaced after those fixtures exist; qualification
itself consumes only canonical I2 files and never executes a solver or corpus.
"""

from contextlib import contextmanager, ExitStack
from dataclasses import FrozenInstanceError, is_dataclass, replace
from hashlib import sha256
from itertools import chain, repeat
import json
import os
from pathlib import Path
import platform
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments import program_k_e2_analysis as analysis
from experiments import program_k_e2_audit as audit
from experiments import program_k_e2_evaluator as evaluator
from experiments import program_k_e2_execution as execution
from experiments import program_k_e2_identity as identity
from experiments import program_k_e2_operational as op
from experiments import program_k_e2_qualification as q
from experiments import program_k_e2_records as records
from experiments import program_k_e2_store as store
from experiments import program_k_runner as runner
from tests.test_program_k_e2_execution import _literal_context, _literal_work
from tests.test_program_k_e2_operational import _envelope


def _committed_fixture_sources():
    """Snapshot committed I7 premises for synthetic fixtures, not live admission.

    Later slices may legitimately be under review in the working tree. This
    fixture reads only explicit committed blobs; production capture_sources and
    its separate live-worktree rejection tests retain their original authority.
    """
    head = q._git("rev-parse", "HEAD").strip().decode("ascii")
    paths = tuple(sorted(set(q._PROTECTED + ("benchmark_board.py", q._PROTOCOL,
                                             q._REPAIR_TEST) + q._E2)))
    refs = tuple(head + ":" + path for path in paths)
    refs += tuple(q._E1 + ":" + path for path in q._PROTECTED)
    refs += (q._FREEZE + ":" + q._PROTOCOL,)
    blobs = q._blobs(refs)
    current = dict(zip(paths, blobs[:len(paths)]))
    for index, path in enumerate(q._PROTECTED):
        if current[path] != blobs[len(paths) + index]:
            raise AssertionError("FIXTURE_E1_CORE_IDENTITY_DRIFT")
    protocol_blob = blobs[-1]
    if current[q._PROTOCOL] != protocol_blob or protocol_blob[0] != q._BLOB:
        raise AssertionError("FIXTURE_FROZEN_PROTOCOL_IDENTITY_DRIFT")
    identity.validate_protocol_bytes(protocol_blob[1])
    if q._git("rev-parse", "HEAD").strip().decode("ascii") != head:
        raise AssertionError("FIXTURE_HEAD_CHANGED_DURING_CAPTURE")
    return tuple(records.SourceBlobIdentity(path, current[path][0],
                 sha256(current[path][1]).hexdigest(), len(current[path][1])) for path in paths)


def _entries(root, name):
    values = []
    for line in (Path(root) / (name + ".jsonl")).read_bytes().splitlines():
        key, data = line.split(b"\t", 1)
        values.append((tuple(json.loads(key)), records.decode(data)))
    return values


def _rewrite(fixture, name, entries, *, reseal=True):
    """Deliberate test corruption/resealing, never a production storage path."""
    data = b"".join(json.dumps(key, separators=(",", ":")).encode("ascii")
                    + b"\t" + records.encode(value) + b"\n" for key, value in entries)
    (Path(fixture.root) / (name + ".jsonl")).write_bytes(data)
    if reseal:
        digest = records.StreamDigest(name, sha256(data).hexdigest(), len(data), len(entries))
        if name == "qualification_identity":
            fixture.identity_seal = digest
        else:
            streams = tuple(digest if value.name == name else value for value in fixture.coordinator.streams)
            fixture.coordinator = replace(fixture.coordinator, streams=streams,
                                           archive_bytes=sum(value.byte_length for value in streams))


class QualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime = records.RuntimeIdentity(platform.python_implementation(), platform.python_version(),
                                          os.name, platform.platform(), platform.machine(), None)
        board = _literal_work().board
        cls.plan = execution.make_work_plan((board,), protocol_seed=bytes.fromhex(identity.PROTOCOL_SHA256),
                                            run_id="synthetic-i7-literal", runtime=runtime)
        cls.envelope = _envelope(validation_wall_ms=10_000, readback_wall_ms=10_000,
                                 aggregation_wall_ms=10_000, report_wall_ms=10_000,
                                 publication_wall_ms=10_000)
        cls.sources = _committed_fixture_sources()
        cls.protocol_bytes = q._git("cat-file", "blob", q._BLOB)
        cls.bundles = cls._literal_bundles(cls.plan[0])
        cls.two_plan = execution.make_work_plan(
            (board, _literal_work(42_424_243).board),
            protocol_seed=bytes.fromhex(identity.PROTOCOL_SHA256),
            run_id="synthetic-i7-two-literals", runtime=runtime)
        cls.two_bundles = tuple(cls._literal_bundles(work) for work in cls.two_plan)

    @staticmethod
    def _literal_bundles(work):
        with _literal_context(work):
            primary = execution.execute_primary(work)
            values = [primary]
            if work.determinism_selected:
                values.append(execution.execute_repeat(work, primary))
            if work.k_control_selected:
                values.append(execution.execute_k_control(work, primary))
        if any(value.status is not records.AuditStatus.PASS for value in values):
            raise AssertionError("The tiny synthetic fixture must have complete I6 evidence")
        return tuple(values)

    @contextmanager
    def fixture(self, *, receipt_status=None, final_status=None, final_reasons=(), two_boards=False):
        plan = self.two_plan if two_boards else self.plan
        bundles = self.two_bundles if two_boards else (self.bundles,)

        def workflow(work, *_):
            results = []
            for bundle in bundles[work.position]:
                status = bundle.status if receipt_status is None else receipt_status
                reason = "ADMITTED" if status is records.AuditStatus.PASS else "SYNTHETIC_" + status.value
                unit = str(work.position) + ":" + bundle.kind.value
                sample = records.ResourceSampleRecord(unit, records.ProcessRole.COMBINED,
                    100, 200, 300, "monotonic_ns:1", 1, records.MemoryMethod.PRIVATE_BYTES)
                receipt = op.UnitReceipt(work.position, bundle.kind, status, reason, 1, 0)
                results.append(op._OperationResult(receipt, bundle, (sample,)))
            return tuple(results)

        with tempfile.TemporaryDirectory(prefix="i7-synthetic-") as directory, ExitStack() as stack:
            stack.enter_context(patch.object(q, "capture_sources", return_value=self.sources))
            stack.enter_context(patch.object(op, "_workflow", side_effect=workflow))
            stack.enter_context(patch.object(op.harness, "_coordinator_private_bytes", return_value=200))
            identity_seal = q.write_identity(directory, plan)
            coordinated = op.coordinate(plan, directory, self.envelope)
            if final_status is not None:
                coordinated = replace(coordinated, status=final_status, reason_codes=final_reasons)
            yield SimpleNamespace(root=directory, plan=plan, coordinator=coordinated,
                                  identity_seal=identity_seal, envelope=self.envelope)

    def qualify(self, fixture):
        return q.qualify(fixture.root, fixture.plan, fixture.coordinator,
                         fixture.identity_seal, fixture.envelope)

    def assertNotPass(self, fixture):
        result = self.qualify(fixture)
        self.assertIsNot(result.status, records.AuditStatus.PASS)
        self.assertIsNone(result.analysis_json)
        self.assertIsNone(result.report_html)
        return result

    def test_complete_i1_through_i7_durable_fixture_passes(self):
        with self.fixture() as fixture:
            result = self.qualify(fixture)
            self.assertIs(result.status, records.AuditStatus.PASS, result.reason_codes)
            self.assertEqual(len(result.rows), 1)
            self.assertIs(type(result.rows[0]), analysis.BoardAnalysisRow)
            self.assertEqual(result.rows[0].position, 0)
            self.assertEqual(result.rows[0].pair.board, self.plan[0].board)
            self.assertIs(type(result.streams), tuple)
            self.assertTrue(is_dataclass(result))
            self.assertFalse(hasattr(result, "__dict__"))
            with self.assertRaises(FrozenInstanceError):
                result.status = records.AuditStatus.FAIL
            self.assertFalse((Path(fixture.root) / "COMPLETE.json").exists())

    def test_identity_uses_existing_i1_families_and_exact_seal(self):
        with self.fixture() as fixture:
            observed = store.scan_stream(fixture.root, "qualification_identity")
            self.assertEqual(observed, fixture.identity_seal)
            values = [value for _, value in _entries(fixture.root, "qualification_identity")]
            self.assertEqual(sum(type(value) is records.ProtocolIdentity for value in values), 1)
            self.assertEqual(sum(type(value) is records.CorpusIdentity for value in values), 1)
            self.assertEqual(sum(type(value) is records.RuntimeIdentity for value in values), 1)
            corpus = next(value for value in values if type(value) is records.CorpusIdentity)
            self.assertEqual(corpus.frame_label, "SYNTHETIC_I7")
            self.assertEqual(corpus.ordered_indices, tuple(work.board.game_index for work in fixture.plan))
            self.assertTrue(any(type(value) is records.SourceBlobIdentity for value in values))
            self.assertIs(self.qualify(fixture).status, records.AuditStatus.PASS)

    def test_exactly_one_validation_scan_per_declared_stream(self):
        with self.fixture() as fixture, patch.object(store, "scan_stream", wraps=store.scan_stream) as scanned:
            result = self.qualify(fixture)
        self.assertIs(result.status, records.AuditStatus.PASS, result.reason_codes)
        names = [call.args[1] for call in scanned.call_args_list]
        expected = set(execution.STREAM_NAMES) | {"operations", "resources", "qualification_identity"}
        self.assertEqual(set(names), expected)
        self.assertEqual(len(names), len(expected))

    def test_identical_durable_evidence_has_byte_identical_qualification(self):
        with self.fixture() as fixture:
            first, second = self.qualify(fixture), self.qualify(fixture)
        self.assertIs(first.status, records.AuditStatus.PASS)
        self.assertEqual(q.canonical_result(first), q.canonical_result(second))
        self.assertEqual(first.analysis_json, second.analysis_json)
        self.assertEqual(first.report_html, second.report_html)
        self.assertIs(type(q.canonical_result(first)), bytes)

    def test_i3_exact_rows_bootstrap_and_report_have_no_overall_research_verdict(self):
        with self.fixture() as fixture:
            result = self.qualify(fixture)
        core = json.loads(result.analysis_json)
        self.assertEqual(core["bootstrap"]["replicates"], 10_000)
        self.assertEqual(core["n"], 1)
        self.assertIsNone(core["overall"])
        self.assertEqual(result.rows[0].control_model_us,
                         execution.restore_projection(self.bundles[0], "control").total_model_us)
        self.assertEqual(result.rows[0].kp0_model_us,
                         execution.restore_projection(self.bundles[0], "kp0").total_model_us)
        self.assertIn("<html", result.report_html.lower())
        self.assertIn("nonclaims", core)

    def test_qualification_reuses_parent_revalidation_without_forbidden_execution(self):
        with self.fixture() as fixture, ExitStack() as stack:
            for module, name in ((execution, "execute_primary"), (execution, "execute_repeat"),
                                 (execution, "execute_k_control"), (runner, "run_control_capture"),
                                 (runner, "run_k_p0"), (runner, "run_k_control"),
                                 (audit, "audit_k_p0"), (audit, "_oracle_b"),
                                 (evaluator, "evaluate_k_p0")):
                stack.enter_context(patch.object(module, name, side_effect=AssertionError("Forbidden execution: " + name)))
            stack.enter_context(patch("benchmark_board.generate_board", side_effect=AssertionError("No indexed boards")))
            validated = stack.enter_context(patch.object(execution, "revalidate_bundle",
                                                         wraps=execution.revalidate_bundle))
            result = self.qualify(fixture)
        self.assertIs(result.status, records.AuditStatus.PASS, result.reason_codes)
        self.assertEqual({call.args[2] for call in validated.call_args_list}, set(execution.WorkerKind))

    def test_every_declared_stream_file_is_required_even_if_empty(self):
        with self.fixture() as fixture:
            for name in execution.STREAM_NAMES + ("operations", "resources", "qualification_identity"):
                path = Path(fixture.root) / (name + ".jsonl")
                original = path.read_bytes()
                path.unlink()
                try:
                    with self.subTest(stream=name):
                        self.assertNotPass(fixture)
                finally:
                    path.write_bytes(original)

    def test_unexpected_stream_file_cannot_be_ignored(self):
        with self.fixture() as fixture:
            (Path(fixture.root) / "unexpected.jsonl").write_bytes(b"")
            result = self.assertNotPass(fixture)
            self.assertIn("DURABLE_STREAM_DIRECTORY_COVERAGE_MISMATCH", result.reason_codes)

    def test_validation_timeout_cancels_and_joins_all_scanner_threads(self):
        with self.fixture() as fixture:
            clock = chain((0,), repeat(10 ** 30))
            with patch.object(q.time, "monotonic_ns", side_effect=lambda: next(clock)), \
                 patch.object(analysis, "analyze_effectiveness",
                              side_effect=AssertionError("Incomplete validation cannot reach analysis")):
                result = self.assertNotPass(fixture)
            self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
            self.assertIn("QUALIFICATION_TIMEOUT", result.reason_codes)
            self.assertFalse(any(thread.is_alive() and thread.name.startswith("i7-scan-")
                                 for thread in threading.enumerate()))
            self.assertFalse((Path(fixture.root) / "COMPLETE.json").exists())

    def test_aggregation_cap_cannot_publish_a_completed_report(self):
        with self.fixture() as fixture:
            actual_clock, actual_analyze = q.time.monotonic_ns, analysis.analyze_effectiveness
            offset = [0]

            def analyze(*args, **kwargs):
                value = actual_analyze(*args, **kwargs)
                offset[0] += fixture.envelope.aggregation_wall_ms * 1_000_000 + 1
                return value

            with patch.object(q.time, "monotonic_ns", side_effect=lambda: actual_clock() + offset[0]), \
                 patch.object(analysis, "analyze_effectiveness", side_effect=analyze) as invoked, \
                 patch.object(q.report, "render_report_html",
                              side_effect=AssertionError("Expired aggregation cannot render a report")):
                result = self.assertNotPass(fixture)
            invoked.assert_called_once()
            self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
            self.assertIn("INTEGRATION_POSTPROCESSING_INCOMPLETE", result.reason_codes)
            self.assertFalse((Path(fixture.root) / "COMPLETE.json").exists())

    def test_report_cap_discards_already_rendered_synthetic_output(self):
        with self.fixture() as fixture:
            actual_clock, actual_render = q.time.monotonic_ns, q.report.render_report_html
            offset = [0]

            def render(*args, **kwargs):
                value = actual_render(*args, **kwargs)
                offset[0] += fixture.envelope.report_wall_ms * 1_000_000 + 1
                return value

            with patch.object(q.time, "monotonic_ns", side_effect=lambda: actual_clock() + offset[0]), \
                 patch.object(q.report, "render_report_html", side_effect=render) as invoked:
                result = self.assertNotPass(fixture)
            invoked.assert_called_once()
            self.assertIs(result.status, records.AuditStatus.INCOMPLETE)
            self.assertIn("INTEGRATION_POSTPROCESSING_INCOMPLETE", result.reason_codes)
            self.assertFalse((Path(fixture.root) / "COMPLETE.json").exists())

    def test_missing_duplicate_and_unknown_stream_seals_cannot_pass(self):
        for change in (lambda values: values[:-1], lambda values: values + (values[0],),
                       lambda values: values + (replace(values[0], name="unexpected_stream"),)):
            with self.fixture() as fixture:
                fixture.coordinator = replace(fixture.coordinator, streams=change(fixture.coordinator.streams))
                self.assertNotPass(fixture)

    def test_unverified_changed_bytes_and_digest_drift_cannot_pass(self):
        with self.fixture() as fixture:
            path = Path(fixture.root) / "boards.jsonl"
            path.write_bytes(path.read_bytes() + b" ")
            self.assertNotPass(fixture)
        with self.fixture() as fixture:
            seals = fixture.coordinator.streams
            fixture.coordinator = replace(fixture.coordinator,
                streams=(replace(seals[0], sha256="0" * 64),) + seals[1:])
            self.assertNotPass(fixture)

    def test_validly_resealed_wrong_record_family_is_rejected(self):
        with self.fixture() as fixture:
            values = _entries(fixture.root, "control_physical_inputs")
            values[0] = (values[0][0], fixture.plan[0].board)
            _rewrite(fixture, "control_physical_inputs", values)
            self.assertNotPass(fixture)

    def test_duplicate_descending_gap_and_extra_operation_keys_are_rejected(self):
        for mutation in (lambda values: [values[0]] + values,
                         lambda values: list(reversed(values)),
                         lambda values: [(values[0][0][:-1] + (99,), values[0][1])] + values[1:],
                         lambda values: values + [((99, 0, 0), values[0][1])]):
            with self.fixture() as fixture:
                values = _entries(fixture.root, "kp0_physical_inputs")
                self.assertGreater(len(values), 1)
                _rewrite(fixture, "kp0_physical_inputs", mutation(values))
                self.assertNotPass(fixture)

    def test_wrong_board_arm_and_run_identity_are_rejected(self):
        for name, change in (("boards", lambda value: replace(value, fingerprint="wrong-fingerprint")),
                             ("kp0_arms", lambda value: replace(value, run_id="synthetic-i7-wrong")),
                             ("control_arms", lambda value: replace(value, unit_id="wrong-unit"))):
            with self.fixture() as fixture:
                values = _entries(fixture.root, name)
                values[0] = (values[0][0], change(values[0][1]))
                _rewrite(fixture, name, values)
                self.assertNotPass(fixture)

    def test_identity_protocol_corpus_runtime_and_source_drift_are_rejected(self):
        for cls, change in ((records.ProtocolIdentity, lambda value: replace(value, sha256="0" * 64)),
                            (records.CorpusIdentity, lambda value: replace(value, corpus_sha256="0" * 64)),
                            (records.RuntimeIdentity, lambda value: replace(value, architecture="wrong-architecture")),
                            (records.SourceBlobIdentity, lambda value: replace(value, sha256="0" * 64))):
            with self.fixture() as fixture:
                values = _entries(fixture.root, "qualification_identity")
                index = next(i for i, (_, value) in enumerate(values) if type(value) is cls)
                values[index] = (values[index][0], change(values[index][1]))
                _rewrite(fixture, "qualification_identity", values)
                self.assertNotPass(fixture)

    def test_identity_seal_and_manifest_record_coverage_are_required(self):
        with self.fixture() as fixture:
            fixture.identity_seal = replace(fixture.identity_seal, sha256="0" * 64)
            self.assertNotPass(fixture)
        with self.fixture() as fixture:
            values = _entries(fixture.root, "qualification_identity")
            values = [(key, value) for key, value in values if type(value) is not records.RuntimeIdentity]
            _rewrite(fixture, "qualification_identity", values)
            self.assertNotPass(fixture)

    def test_prospective_subset_change_cannot_pass(self):
        with self.fixture() as fixture:
            fixture.plan = (replace(fixture.plan[0], oracle_b_selected=False),)
            try:
                self.assertNotPass(fixture)
            except ValueError:
                pass  # Malformed caller plan may be rejected before scanning.

    def test_oracle_coverage_and_child_omissions_are_rejected_for_primary_and_repeat(self):
        for name in ("oracle_b_coverage", "repeat_oracle_b_coverage", "oracle_b_audits", "repeat_oracle_b_audits"):
            with self.fixture() as fixture:
                self.assertTrue(_entries(fixture.root, name))
                _rewrite(fixture, name, [])
                with self.subTest(stream=name):
                    self.assertNotPass(fixture)

    def test_oracle_child_phase_mismatch_cannot_pass(self):
        for name in ("oracle_b_audits", "repeat_oracle_b_audits"):
            with self.fixture() as fixture:
                values = _entries(fixture.root, name)
                key, value = values[0]
                values[0] = (key, replace(value, phase="E" if value.phase == "D" else "D"))
                _rewrite(fixture, name, values)
                self.assertNotPass(fixture)

    def test_same_key_oracle_child_cannot_substitute_another_public_premise(self):
        for name in ("oracle_b_audits", "repeat_oracle_b_audits"):
            with self.fixture() as fixture:
                values = _entries(fixture.root, name)
                key, value = values[0]
                first = value.public_observation[0]
                observation = ((8 if first[0] != 8 else 7,) + first[1:],) + value.public_observation[1:]
                digest = q.oracles.oracle_b_input_digest(observation, fixture.plan[0].board.mines,
                                                        frozenset(value.logical_mines))
                values[0] = (key, replace(value, public_observation=observation, input_digest=digest))
                _rewrite(fixture, name, values)
                with self.subTest(stream=name):
                    result = self.assertNotPass(fixture)
                    self.assertIn("ORACLE_PUBLIC_PREMISE_MISMATCH", result.reason_codes)

    def test_certificate_and_evaluator_coverage_cannot_be_dropped(self):
        for name in ("certificate_audits", "repeat_certificate_audits", "evaluators", "repeat_evaluators"):
            with self.fixture() as fixture:
                values = _entries(fixture.root, name)
                self.assertTrue(values)
                _rewrite(fixture, name, values[1:])
                with self.subTest(stream=name):
                    self.assertNotPass(fixture)

    def test_falsified_evaluator_child_cannot_be_upgraded(self):
        with self.fixture() as fixture:
            values = _entries(fixture.root, "evaluators")
            key, value = values[0]
            values[0] = (key, replace(value, status=records.EvaluationStatus.FAIL, reason_code="SYNTHETIC_FALSE"))
            _rewrite(fixture, "evaluators", values)
            self.assertIs(self.assertNotPass(fixture).status, records.AuditStatus.FAIL)

    def test_evaluator_pass_must_cover_the_exact_public_assertion_targets(self):
        for name in ("evaluators", "repeat_evaluators"):
            with self.fixture() as fixture:
                values = _entries(fixture.root, name)
                index = next(i for i, (_, value) in enumerate(values) if value.targets)
                key, value = values[index]
                targets = ((0, 0),) if value.targets != ((0, 0),) else ((3, 0),)
                values[index] = (key, replace(value, targets=targets))
                _rewrite(fixture, name, values)
                with self.subTest(stream=name):
                    result = self.assertNotPass(fixture)
                    self.assertIn("EVALUATOR_ASSERTION_PREMISE_MISMATCH", result.reason_codes)

    def test_determinism_full_stream_and_summary_are_both_required(self):
        for name in ("repeat_kp0_decision_spans", "kp0_determinism", "control_determinism"):
            with self.fixture() as fixture:
                _rewrite(fixture, name, [])
                with self.subTest(stream=name):
                    self.assertNotPass(fixture)

    def test_repeat_first_premises_cannot_drift_from_primary(self):
        with self.fixture() as fixture:
            values = _entries(fixture.root, "control_decision_spans")
            index = next(i for i, (key, _) in enumerate(values) if key[1] == 1)
            key, value = values[index]
            values[index] = (key, replace(value, duration_ns=value.duration_ns + 1))
            _rewrite(fixture, "control_decision_spans", values)
            self.assertNotPass(fixture)

    def test_kcontrol_reference_and_full_actual_evidence_are_required(self):
        with self.fixture() as fixture:
            _rewrite(fixture, "kcontrol_maintenance", [])
            self.assertNotPass(fixture)
        with self.fixture() as fixture:
            values = _entries(fixture.root, "control_maintenance")
            index = next(i for i, (key, _) in enumerate(values) if key[1] == 2)
            key, value = values[index]
            timings = tuple((name, duration + 1 if duration is not None else None) for name, duration in value.timings)
            values[index] = (key, replace(value, timings=timings))
            _rewrite(fixture, "control_maintenance", values)
            self.assertNotPass(fixture)

    def test_pair_record_model_c_drift_is_rejected(self):
        with self.fixture() as fixture:
            values = _entries(fixture.root, "pairs")
            key, value = values[0]
            self.assertIsNotNone(value.ww_delta_us)
            values[0] = (key, replace(value, ww_delta_us=value.ww_delta_us + 1))
            _rewrite(fixture, "pairs", values)
            self.assertNotPass(fixture)

    def test_raw_pair_p3_failure_dominates_missing_evidence(self):
        with self.fixture(final_status=records.AuditStatus.INCOMPLETE,
                          final_reasons=("READBACK_TIMEOUT",)) as fixture:
            values = _entries(fixture.root, "pairs")
            key, value = values[0]
            values[0] = (key, replace(value, p3_status=records.P3Status.FAIL,
                                      diagnosis="SYNTHETIC_P3_FAIL"))
            _rewrite(fixture, "pairs", values)
            self.assertIs(self.assertNotPass(fixture).status, records.AuditStatus.FAIL)

    def test_missing_terminal_lane_cannot_be_inferred_from_outcome(self):
        with self.fixture() as fixture:
            _rewrite(fixture, "kp0_terminal_effects", [])
            self.assertNotPass(fixture)

    def test_missing_or_duplicate_terminal_operation_event_is_rejected(self):
        for duplicate in (False, True):
            with self.fixture() as fixture:
                values = _entries(fixture.root, "operations")
                index = next(i for i, (_, value) in enumerate(values)
                             if value.unit_id.startswith("0:PRIMARY:") and value.event_kind is records.EventKind.END)
                if duplicate:
                    values.insert(index, values[index])
                else:
                    del values[index]
                values = [((i,), replace(value, ordinal=i)) for i, (_, value) in enumerate(values)]
                _rewrite(fixture, "operations", values)
                self.assertNotPass(fixture)

    def test_receipt_count_order_status_and_durable_count_drift_are_rejected(self):
        for change in (lambda value: replace(value, receipts=value.receipts[:-1]),
                       lambda value: replace(value, receipts=value.receipts[::-1]),
                       lambda value: replace(value, durable_units=value.durable_units + 1),
                       lambda value: replace(value, durable_primary_boards=value.durable_primary_boards + 1),
                       lambda value: replace(value, archive_bytes=value.archive_bytes + 1)):
            with self.fixture() as fixture:
                fixture.coordinator = change(fixture.coordinator)
                self.assertNotPass(fixture)

    def test_fabricated_durable_progress_count_is_rejected(self):
        with self.fixture() as fixture:
            values = _entries(fixture.root, "operations")
            index = next(i for i, (_, value) in enumerate(values) if value.unit_id.startswith("durable_primary_count:"))
            key, value = values[index]
            values[index] = (key, replace(value, unit_id="durable_primary_count:999"))
            _rewrite(fixture, "operations", values)
            self.assertNotPass(fixture)

    def test_wrong_resource_owner_and_missing_required_samples_cannot_pass(self):
        with self.fixture() as fixture:
            values = _entries(fixture.root, "resources")
            key, value = values[0]
            values[0] = (key, replace(value, unit_id="999:PRIMARY"))
            _rewrite(fixture, "resources", values)
            self.assertNotPass(fixture)
        with self.fixture() as fixture:
            _rewrite(fixture, "resources", [])
            self.assertNotPass(fixture)

    def test_every_passing_unit_needs_its_own_resource_sample(self):
        with self.fixture() as fixture:
            values = _entries(fixture.root, "resources")
            missing = values[0][1].unit_id
            kept = [value for _, value in values if value.unit_id != missing]
            self.assertTrue(kept)
            _rewrite(fixture, "resources", [((i,), value) for i, value in enumerate(kept)])
            self.assertNotPass(fixture)

    def test_extra_resource_samples_and_wrong_role_or_memory_method_cannot_pass(self):
        for mutation in ("extra", "worker", "coordinator", "rss"):
            with self.fixture() as fixture:
                values = _entries(fixture.root, "resources")
                key, value = values[0]
                if mutation == "extra":
                    values = [values[0]] * 4 + values[1:]
                else:
                    change = {"worker": {"process_role": records.ProcessRole.WORKER},
                              "coordinator": {"process_role": records.ProcessRole.COORDINATOR},
                              "rss": {"method": records.MemoryMethod.RSS}}[mutation]
                    values[0] = (key, replace(value, **change))
                values = [((i,), value) for i, (_, value) in enumerate(values)]
                _rewrite(fixture, "resources", values)
                with self.subTest(mutation=mutation):
                    self.assertNotPass(fixture)

    def test_resource_coordinator_and_combined_caps_cannot_be_upgraded(self):
        for cap in ("coordinator", "combined"):
            with self.fixture() as fixture:
                values = _entries(fixture.root, "resources")
                key, value = values[0]
                coordinator = (fixture.envelope.coordinator_memory_cap_bytes + 1
                               if cap == "coordinator" else value.coordinator_bytes)
                workers = (fixture.envelope.memory_cap_bytes + 1
                           if cap == "combined" else value.worker_bytes)
                values[0] = (key, replace(value, worker_bytes=workers, coordinator_bytes=coordinator,
                                          combined_bytes=workers + coordinator))
                _rewrite(fixture, "resources", values)
                with self.subTest(cap=cap):
                    self.assertIs(self.assertNotPass(fixture).status, records.AuditStatus.INCOMPLETE)

    def test_combined_sample_worker_sum_is_not_an_individual_job_cap(self):
        with self.fixture() as fixture:
            values = _entries(fixture.root, "resources")
            key, value = values[0]
            workers = fixture.envelope.worker_memory_cap_bytes + 1
            self.assertLess(workers + value.coordinator_bytes, fixture.envelope.memory_cap_bytes)
            values[0] = (key, replace(value, worker_bytes=workers,
                                      combined_bytes=workers + value.coordinator_bytes))
            _rewrite(fixture, "resources", values)
            result = self.qualify(fixture)
            self.assertIs(result.status, records.AuditStatus.PASS, result.reason_codes)

    def test_two_literal_boards_reconcile_all_units_and_rows(self):
        with self.fixture(two_boards=True) as fixture:
            result = self.qualify(fixture)
            self.assertIs(result.status, records.AuditStatus.PASS, result.reason_codes)
            self.assertEqual(tuple(value.position for value in result.rows), (0, 1))
            self.assertEqual(fixture.coordinator.durable_primary_boards, 2)

    def test_progress_cannot_be_borrowed_from_a_later_primary(self):
        with self.fixture(two_boards=True) as fixture:
            values = [value for _, value in _entries(fixture.root, "operations")]
            progress = [value for value in values if value.unit_id.startswith("durable_primary_count:")]
            self.assertEqual(tuple(value.unit_id for value in progress),
                             ("durable_primary_count:1", "durable_primary_count:2"))
            values.remove(progress[1])
            values.insert(values.index(progress[0]) + 1, progress[1])
            # Preserve stream order, ordinals, elapsed monotonicity, total count,
            # and both count labels; only the admitted-primary association drifts.
            _rewrite(fixture, "operations",
                     [((i,), replace(value, ordinal=i, elapsed_ns=i)) for i, value in enumerate(values)])
            self.assertNotPass(fixture)

    def test_fabricated_runtime_cannot_authenticate_itself_via_plan_and_files(self):
        with self.fixture() as fixture:
            fabricated = replace(fixture.plan[0].runtime, architecture="invented-runtime")
            fixture.plan = tuple(replace(work, runtime=fabricated) for work in fixture.plan)
            for name in ("runtime", "qualification_identity"):
                values = [(key, fabricated if type(value) is records.RuntimeIdentity else value)
                          for key, value in _entries(fixture.root, name)]
                _rewrite(fixture, name, values)
            result = self.assertNotPass(fixture)
            self.assertIn("RUNTIME_IDENTITY_MISMATCH", result.reason_codes)

    @contextmanager
    def source_capture(self, *, drift=None, statuses=(b"",), heads=None, tracked=False):
        """Mock only Git observations; exercise the production source guard."""
        head = "a" * 40
        heads = (head,) if heads is None else heads
        observations = {"head": 0, "status": 0}

        def git(*args, data=None):
            if args == ("rev-parse", "HEAD"):
                index = observations["head"]
                observations["head"] += 1
                return heads[min(index, len(heads) - 1)].encode("ascii") + b"\n"
            if args == ("status", "--porcelain=v1", "--untracked-files=all"):
                index = observations["status"]
                observations["status"] += 1
                return statuses[min(index, len(statuses) - 1)]
            if args == ("ls-files", "--", q._E2[-1]):
                return q._E2[-1].encode("ascii") + b"\n" if tracked else b""
            raise AssertionError("Unexpected source-guard Git query: " + repr(args))

        def blobs(refs):
            result = []
            for ref in refs:
                commit, path = ref.split(":", 1)
                oid, data = "1" * 40, b"mock committed source\n"
                if path == q._PROTOCOL:
                    oid, data = q._BLOB, self.protocol_bytes
                    if drift == "protocol_oid":
                        oid = "f" * 40
                elif path == q._PROTECTED[0] and commit == head and drift == "protected_oid":
                    oid = "2" * 40
                result.append((oid, data))
            return tuple(result)

        with patch.object(q, "_git", side_effect=git), patch.object(q, "_blobs", side_effect=blobs):
            yield observations

    def test_source_guard_rejects_protected_and_protocol_blob_drift(self):
        for drift, reason in (("protected_oid", "E1_CORE_IDENTITY_DRIFT"),
                              ("protocol_oid", "FROZEN_PROTOCOL_IDENTITY_DRIFT")):
            with self.source_capture(drift=drift), self.subTest(drift=drift):
                with self.assertRaisesRegex(q.QualificationError, reason):
                    q.capture_sources()

    def test_source_guard_rejects_dirty_staged_and_unapproved_untracked_paths(self):
        for status in (b" M core_engine.py\n", b"M  experiments/program_k_e2_qualification.py\n",
                       b"?? unrelated.py\n", b" M experiments/program_k_e2_qualification.py\n",
                       b"?? experiments/program_k_e2_readiness.py\n",
                       b"?? tests/test_program_k_e2_readiness.py\n",
                       b" M tests/test_program_k_e2_qualification.py\n"):
            with self.source_capture(statuses=(status,)), self.subTest(status=status):
                with self.assertRaisesRegex(q.QualificationError, "UNAUTHORIZED_WORKTREE_OR_INDEX_CHANGE"):
                    q.capture_sources()

    def test_committed_fixture_snapshot_does_not_claim_live_review_admission(self):
        status = b"?? experiments/program_k_e2_readiness.py\n"
        with self.source_capture(statuses=(status,), tracked=True) as observations:
            with patch.object(Path, "read_bytes", side_effect=AssertionError("No working-tree bytes")):
                first = _committed_fixture_sources()
                self.assertEqual(first, _committed_fixture_sources())
            self.assertEqual(observations["status"], 0)
            self.assertIs(type(first), tuple)
            self.assertTrue(all(type(value) is records.SourceBlobIdentity for value in first))
            with self.assertRaisesRegex(q.QualificationError, "UNAUTHORIZED_WORKTREE_OR_INDEX_CHANGE"):
                q.capture_sources()

    def test_committed_fixture_snapshot_retains_authority_and_head_checks(self):
        for drift, reason in (("protected_oid", "FIXTURE_E1_CORE_IDENTITY_DRIFT"),
                              ("protocol_oid", "FIXTURE_FROZEN_PROTOCOL_IDENTITY_DRIFT")):
            with self.source_capture(drift=drift), self.subTest(drift=drift):
                with self.assertRaisesRegex(AssertionError, reason):
                    _committed_fixture_sources()
        with self.source_capture(heads=("a" * 40, "b" * 40)):
            with self.assertRaisesRegex(AssertionError, "FIXTURE_HEAD_CHANGED_DURING_CAPTURE"):
                _committed_fixture_sources()

    def test_source_guard_detects_head_and_status_races(self):
        for changes in ({"heads": ("a" * 40, "b" * 40)},
                        {"statuses": (b"", b"?? unrelated.py\n")}):
            with self.source_capture(**changes), self.subTest(changes=changes):
                with self.assertRaisesRegex(q.QualificationError, "SOURCE_CHANGED_DURING_CAPTURE"):
                    q.capture_sources()

    def test_source_guard_detects_candidate_byte_race(self):
        with self.source_capture(), patch.object(Path, "read_bytes", side_effect=(b"before\n", b"after\n")):
            with self.assertRaisesRegex(q.QualificationError, "SOURCE_CHANGED_DURING_CAPTURE"):
                q.capture_sources()

    def test_source_guard_accepts_only_named_candidates_and_committed_qualification(self):
        permitted = b"".join(b"?? " + value.encode("ascii") + b"\n" for value in q._CANDIDATES)
        for options in ({"statuses": (permitted,)}, {"tracked": True}):
            with self.source_capture(**options), self.subTest(options=options):
                values = q.capture_sources()
                self.assertTrue(all(type(value) is records.SourceBlobIdentity for value in values))
                self.assertEqual(sum(value.path == q._E2[-1] for value in values), 1)

    def test_source_guard_binds_only_unstaged_repair_during_candidate_review(self):
        status = (" M " + q._REPAIR_TEST + "\n").encode("ascii")
        with self.source_capture(statuses=(status,)):
            values = q.capture_sources()
        repaired = next(value for value in values if value.path == q._REPAIR_TEST)
        actual = (q._ROOT / q._REPAIR_TEST).read_bytes()
        self.assertEqual(repaired.sha256, sha256(actual).hexdigest())
        self.assertEqual(repaired.byte_length, len(actual))
        staged = ("M  " + q._REPAIR_TEST + "\n").encode("ascii")
        for options in ({"statuses": (status,), "tracked": True}, {"statuses": (staged,)}):
            with self.subTest(options=options), self.source_capture(**options):
                with self.assertRaisesRegex(q.QualificationError, "UNAUTHORIZED_WORKTREE_OR_INDEX_CHANGE"):
                    q.capture_sources()

    def test_source_guard_detects_repair_byte_race(self):
        status = (" M " + q._REPAIR_TEST + "\n").encode("ascii")
        with self.source_capture(statuses=(status,)), patch.object(
                Path, "read_bytes", side_effect=(b"candidate\n", b"before\n", b"candidate\n", b"after\n")):
            with self.assertRaisesRegex(q.QualificationError, "SOURCE_CHANGED_DURING_CAPTURE"):
                q.capture_sources()

    def test_prior_fail_is_never_upgraded_even_with_complete_public_evidence(self):
        with self.fixture(receipt_status=records.AuditStatus.FAIL) as fixture:
            self.assertIs(self.assertNotPass(fixture).status, records.AuditStatus.FAIL)

    def test_prior_incomplete_is_never_upgraded(self):
        with self.fixture(receipt_status=records.AuditStatus.INCOMPLETE) as fixture:
            self.assertIs(self.assertNotPass(fixture).status, records.AuditStatus.INCOMPLETE)

    def test_postseal_readback_failure_remains_incomplete(self):
        for reason in ("READBACK_TIMEOUT", "READBACK_INTEGRITY_FAIL"):
            with self.fixture(final_status=records.AuditStatus.INCOMPLETE, final_reasons=(reason,)) as fixture:
                self.assertIs(self.assertNotPass(fixture).status, records.AuditStatus.INCOMPLETE)

    def test_raw_failure_dominates_prior_readback_incomplete(self):
        with self.fixture(final_status=records.AuditStatus.INCOMPLETE, final_reasons=("READBACK_TIMEOUT",)) as fixture:
            values = _entries(fixture.root, "evaluators")
            key, value = values[0]
            values[0] = (key, replace(value, status=records.EvaluationStatus.FAIL, reason_code="SYNTHETIC_FALSE"))
            _rewrite(fixture, "evaluators", values)
            self.assertIs(self.assertNotPass(fixture).status, records.AuditStatus.FAIL)

    def test_identity_writer_never_overwrites_or_publishes_completion(self):
        with self.fixture() as fixture:
            before = (Path(fixture.root) / "qualification_identity.jsonl").read_bytes()
            with self.assertRaises(ValueError):
                q.write_identity(fixture.root, fixture.plan)
            self.assertEqual((Path(fixture.root) / "qualification_identity.jsonl").read_bytes(), before)
            self.assertFalse((Path(fixture.root) / "COMPLETE.json").exists())


if __name__ == "__main__":
    unittest.main()
