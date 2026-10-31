"""D1 tests: bytes and completed records only; never generate missing evidence.

The accepted archive is deliberately ignored by Git. Evidence-dependent tests
explicitly skip when it is absent; portable boundary tests still run. To verify
D1 completely, retain the accepted qualification.json and COMPLETE.json at the
path below. No test imports a runner, solver, Engine, or E1 evaluator.
"""

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from experiments import program_k_trace_adapter as adapter


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "results/program_k_research" / adapter.ACCEPTED_RUN_ID
PROFILE = ROOT / "calibration/stage3_physical_profile_v1.json"
HAS_EVIDENCE = (ARTIFACT / "qualification.json").is_file() and (ARTIFACT / "COMPLETE.json").is_file()


class PortableBoundaryTests(unittest.TestCase):
    def test_module_has_only_stdlib_imports(self):
        tree = ast.parse(Path(adapter.__file__).read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                imports.add(node.module.split(".")[0])
        self.assertLessEqual(imports, sys.stdlib_module_names)

    def test_only_explicit_unique_k_indices_are_accepted(self):
        for value in ((), [], (True,), (0,), (1,), (54,), (8, 8), "8", (8.0,)):
            with self.subTest(value=value), self.assertRaises(adapter.KTraceAdapterError):
                adapter.project_accepted_e1_traces(b"", b"", b"", schedule_indices=value)
        self.assertEqual(adapter._indices((26, 8)), (26, 8))

    def test_pin_rejects_changed_size_or_digest_before_json_parse(self):
        with patch.object(adapter.json, "loads", side_effect=AssertionError("must not parse")):
            for data, size, digest in ((b"x", 2, "0" * 64), (b"x", 1, "0" * 64),
                                       (bytearray(b"x"), 1, hashlib.sha256(b"x").hexdigest())):
                with self.subTest(data=data), self.assertRaises(adapter.KTraceAdapterError):
                    adapter._pinned_json(data, size, digest, "test")

    def test_graph_rejects_forward_cycle_duplicate_field_and_bool_reference(self):
        wires = (
            ["e1-dag-v1", 0, [["tuple", [0]]]],
            ["e1-dag-v1", 0, [["tuple", [True]]]],
            ["e1-dag-v1", 1, [["none"], ["record", "T", [["x", 0], ["x", 0]]]]],
        )
        for wire in wires:
            with self.subTest(wire=wire), self.assertRaises(adapter.KTraceAdapterError):
                graph = adapter._Graph(wire)
                if graph.node(graph.root)[0] == "record":
                    graph.record(graph.root, "T")
                else:
                    graph.sequence(graph.root)

    def test_exact_integer_and_coordinate_contract(self):
        for encoded in ("1", "0X1", "+0x1", "0x01", "invalid", True):
            with self.subTest(encoded=encoded), self.assertRaises(adapter.KTraceAdapterError):
                adapter._Graph(["e1-dag-v1", 0, [["int", encoded]]]).integer(0)
        graph = adapter._Graph(["e1-dag-v1", 2, [["int", "0x0"], ["int", "0x2"], ["tuple", [0, 1]]]])
        self.assertEqual(graph.coord(2, 4, 3), (0, 2))
        with self.assertRaises(adapter.KTraceAdapterError):
            graph.coord(2, 4, 2)

    def test_incomplete_or_extra_archive_files_are_rejected_without_loading(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, "project_accepted_e1_traces") as project:
            root = Path(directory)
            for filename in (None, "qualification.json", "COMPLETE.json", "unexpected.txt"):
                if filename:
                    (root / filename).write_bytes(b"")
                with self.assertRaises(adapter.KTraceAdapterError):
                    adapter.load_accepted_e1_traces(root, schedule_indices=(8,))
            project.assert_not_called()

    def test_reader_is_bounded_and_rejects_link_surfaces(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence"
            path.write_bytes(b"12345")
            with self.assertRaises(adapter.KTraceAdapterError):
                adapter._read_bounded(path, 4)
            self.assertEqual(adapter._read_bounded(path, 5), b"12345")
            for method in ("is_symlink", "is_junction"):
                with patch.object(Path, method, return_value=True), self.assertRaises(adapter.KTraceAdapterError):
                    adapter._read_bounded(path, 5)

    def test_profile_identity_and_exact_integer_table(self):
        data = PROFILE.read_bytes()
        profile = adapter._pinned_json(data, adapter.PROFILE_SIZE, adapter.PROFILE_SHA256, "profile")
        table = adapter._timing_table(profile)
        self.assertEqual((len(table), len(table[0]), table[0][0]), (30, 16, 126005))
        for value in (True, 126005.0, 126006):
            damaged = dict(profile, timing_table_us=[row[:] for row in profile["timing_table_us"]])
            damaged["timing_table_us"][0][0] = value
            with self.subTest(value=value), self.assertRaises(adapter.KTraceAdapterError):
                adapter._timing_table(damaged)


@unittest.skipUnless(HAS_EVIDENCE, "Accepted E1 archive absent; no evidence regeneration is permitted.")
class AcceptedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qualification = (ARTIFACT / "qualification.json").read_bytes()
        cls.complete = (ARTIFACT / "COMPLETE.json").read_bytes()
        cls.profile = PROFILE.read_bytes()
        cls.views = adapter.project_accepted_e1_traces(
            cls.qualification, cls.complete, cls.profile, schedule_indices=adapter.K_SCHEDULE_INDICES)
        cls.by_index = {view.case.schedule_index: view for view in cls.views}
        cls.wire = json.loads(cls.qualification)
        cls.graph = adapter._Graph(cls.wire)
        cls.root = cls.record(cls.graph.root)
        marker_graph = adapter._Graph(json.loads(cls.complete))
        cls.marker = marker_graph.plain(marker_graph.root)
        cls.provenance, cls.plan, cls.execution, cls.audit_source = adapter._sources(cls.graph, cls.root, cls.marker)
        cls.table = adapter._timing_table(json.loads(cls.profile))
        cls.operations = cls.graph.sequence(cls.root["scheduled_results"])

    @classmethod
    def record(cls, index):
        return dict(cls.wire[2][index][2])

    @classmethod
    def refs(cls, schedule_index):
        operation = cls.record(cls.operations[schedule_index])
        archive = cls.record(operation["archive"])
        result = cls.record(archive["result"])
        return operation, archive, result, cls.record(operation["audit"])

    @classmethod
    def trace_ref(cls, schedule_index, input_index):
        return cls.graph.sequence(cls.refs(schedule_index)[2]["traces"])[input_index]

    def assert_rejected_mutation(self, schedule_index, changes, message=None):
        # Private semantic checks deliberately bypass the public byte pins, so
        # tests can also catch projection mistakes behind the integrity gate.
        nodes = self.wire[2][:]
        for ref, replacement in changes.items():
            nodes[ref] = replacement
        graph = adapter._Graph(["e1-dag-v1", self.wire[1], nodes])
        with self.assertRaises(adapter.KTraceAdapterError) as caught:
            adapter._project_run(graph, self.operations[schedule_index], schedule_index, self.plan,
                                 self.execution, self.audit_source, self.provenance, self.table)
        if message:
            self.assertIn(message, str(caught.exception))

    def changed_field(self, record_ref, name, value_ref):
        node = self.wire[2][record_ref]
        self.assertIn(name, dict(node[2]))
        return [node[0], node[1], [[k, value_ref if k == name else v] for k, v in node[2]]]

    def test_all_18_completed_runs_have_expected_identity_outcome_and_cost(self):
        expected = (
            ("S-WIN", "WON", 1, 126005), ("S-LIFECYCLE", "WON", 3, 432614),
            ("S-REPLAN", "WON", 14, 2382644), ("S-LOSS", "LOST", 2, 306609),
            ("X-0", "WON", 180, 31586418), ("X-1", "LOST", 3, 534505),
            ("X-2", "LOST", 155, 29350527), ("X-3", "LOST", 93, 17863935),
            ("X-100000", "LOST", 141, 24701388),
        )
        self.assertEqual(len(self.views), 18)
        for view in self.views:
            with self.subTest(index=view.case.schedule_index):
                self.assertEqual((view.case.case_id, view.terminal_status, len(view.actions), view.total_modeled_us),
                                 expected[view.case.schedule_index // 6])
                self.assertEqual(view.case.variant, "K-P0")
                self.assertEqual(view.case.repetition, (view.case.schedule_index % 6) // 3 + 1)
                self.assertEqual(len(view.frames), len(view.actions) + 1)

    def test_every_frame_is_the_archived_physical_boundary_without_lookahead(self):
        for view in self.views:
            self.assertFalse(view.frame(0).logical_mines)
            self.assertFalse(view.completed_route(0))
            total = 0
            for action in view.actions:
                i = action.input_index
                before, after = view.frame(i), view.frame(i + 1)
                self.assertEqual(before.logical_mines, action.M_before)
                self.assertEqual(after.logical_mines, action.preinput_M)
                self.assertEqual(action.cursor_before, before.cursor)
                self.assertEqual(after.cursor, action.target)
                expected = self.table[abs(after.cursor[0] - before.cursor[0])][abs(after.cursor[1] - before.cursor[1])]
                self.assertEqual(action.modeled_action_us, expected)
                total += expected
                self.assertEqual(after.cumulative_modeled_us, total)
                self.assertEqual(view.completed_route(i + 1)[-1], action.target)
                self.assertEqual(after.logical_mines - before.logical_mines,
                                 frozenset(a.target for a in action.acquisitions))
                effect = self.record(action.effect.node_index)
                archived_after = self.record(effect["after_observation"])
                self.assertEqual(after.observation, self.graph.grid(
                    archived_after["rows"], view.case.width, view.case.height, action.status_after))

    def test_lifecycle_has_hidden_known_mine_without_executed_flag(self):
        view = self.by_index[8]
        self.assertEqual([a.action for a in view.actions], ["OPEN"] * 3)
        self.assertFalse(view.frame(1).logical_mines)  # Not the NEXT decision's M.
        self.assertEqual(view.frame(2).hidden_logical_mines, frozenset({(1, 0)}))
        self.assertFalse(view.frame(2).public_flags)
        self.assertFalse(view.frame(3).explicit_flags)
        self.assertEqual(view.frame(3).automatic_flags, frozenset({(1, 0)}))
        self.assertEqual(view.frame(3).logical_mines, view.frame(2).logical_mines)

    def test_win_auto_flags_and_loss_answers_do_not_create_solver_knowledge(self):
        won = self.by_index[2]
        self.assertFalse(won.frames[-1].logical_mines)
        self.assertFalse(won.frames[-1].explicit_flags)
        self.assertEqual(len(won.frames[-1].automatic_flags), 1)
        lost = self.by_index[20]
        self.assertEqual(lost.terminal_status, "LOST")
        self.assertEqual(len(lost.answer_reference.mines), 2)
        self.assertEqual(len(lost.frames[-1].logical_mines), 1)
        self.assertFalse(lost.frames[-1].automatic_flags)
        self.assertTrue(lost.answer_reference.mines - lost.frames[-1].logical_mines)
        self.assertIn(adapter.EXPLODED, lost.frames[-1].observation[0])
        self.assertIn(adapter.HIDDEN, lost.frames[-1].observation[0])

    def test_replan_preserves_real_open_flag_chord_route(self):
        view = self.by_index[14]
        self.assertEqual({kind: sum(a.action == kind for a in view.actions) for kind in ("OPEN", "FLAG", "CHORD")},
                         {"OPEN": 8, "FLAG": 2, "CHORD": 4})
        for action in view.actions:
            if action.action == "FLAG":
                frame = view.frame(action.input_index + 1)
                self.assertIn(action.target, frame.logical_mines)
                self.assertIn(action.target, frame.explicit_flags)
                self.assertNotIn(action.target, frame.hidden_logical_mines)
        self.assertEqual(view.completed_route(14), tuple(a.target for a in view.actions))
        self.assertEqual(len(view.completed_route(14)), 14)  # No unexecuted plan suffix.

    def test_acquisition_refs_bind_accepted_proofs_and_simultaneous_batches(self):
        kinds = set()
        for view in self.views:
            for action in view.actions:
                for acquisition in action.acquisitions:
                    kinds.add(acquisition.kind)
                    self.assertEqual(acquisition.certificate.artifact_sha256, adapter.QUALIFICATION_SHA256)
                    audit = self.record(acquisition.accepted_audit.node_index)
                    self.assertEqual(audit["certificate"], acquisition.certificate.node_index)
                    self.assertEqual(self.graph.scalar(audit["status"]), "PASS")
                    self.assertEqual(self.graph.integer(audit["boundary"]), action.input_index)
        self.assertEqual(kinds, {"LOCAL", "EXACT_GLOBAL"})
        simultaneous = self.by_index[14].actions[4].acquisitions
        self.assertEqual(len(simultaneous), 5)
        self.assertTrue(all(not a.retained_mines for a in simultaneous))

    def test_presentation_is_deeply_immutable_and_source_bound(self):
        seen = set()
        def inspect(value):
            if id(value) in seen:
                return
            seen.add(id(value))
            self.assertNotIsInstance(value, (list, dict, set, bytearray))
            if is_dataclass(value):
                self.assertTrue(type(value).__dataclass_params__.frozen)
                for field in fields(value):
                    inspect(getattr(value, field.name))
            elif isinstance(value, (tuple, frozenset)):
                for member in value:
                    inspect(member)
        for view in self.views:
            inspect(view)
        view = self.by_index[26]
        self.assertEqual(view.provenance.qualification_sha256, adapter.QUALIFICATION_SHA256)
        self.assertEqual(view.provenance.base_source_digest,
                         "a8d2ed2f5547316603b4ba54899a7deed289016df7a5954f1db5b4816e00abd1")
        self.assertEqual(len(view.provenance.source_files), 9)
        self.assertIn("not production", view.provenance.scope)
        self.assertEqual(view.provenance.no_effectiveness_claim, adapter.NO_EFFECTIVENESS_CLAIM)
        with self.assertRaises(FrozenInstanceError):
            view.frames[0].status = "WON"
        with self.assertRaises(TypeError):
            view.frames[0].observation[0][0] = 0
        for index in (-1, True, 181, 1.0):
            with self.subTest(index=index), self.assertRaises(adapter.KTraceAdapterError):
                view.frame(index)

    def test_public_loader_rejects_each_changed_or_truncated_input(self):
        original = (self.qualification, self.complete, self.profile)
        for slot, data in enumerate(original):
            for corrupt in (data[:-1], bytes([data[0] ^ 1]) + data[1:]):
                args = list(original)
                args[slot] = corrupt
                with self.subTest(slot=slot, length=len(corrupt)), self.assertRaises(adapter.KTraceAdapterError):
                    adapter.project_accepted_e1_traces(*args, schedule_indices=(8,))

    def test_source_identity_tamper_is_rejected(self):
        with patch.object(adapter, "_digest", return_value="0" * 64), self.assertRaisesRegex(
                adapter.KTraceAdapterError, "source chain"):
            adapter._sources(self.graph, self.root, self.marker)

    def test_action_order_missing_effect_and_cursor_corruption_fail_closed(self):
        ref = self.trace_ref(8, 1)
        fields1 = self.record(ref)
        fields0 = self.record(self.trace_ref(8, 0))
        cases = (
            ("input_index", fields0["input_index"], "order"),
            ("public_effect", fields0["public_effect"], "order"),
            ("public_effect", fields0["selection"], "Unexpected evidence record"),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                self.assert_rejected_mutation(8, {ref: self.changed_field(ref, field, value)}, message)
        last_ref = self.trace_ref(8, 2)
        self.assert_rejected_mutation(8, {last_ref: self.changed_field(last_ref, "cursor_before", fields0["cursor_before"])},
                                      "continuity")

    def test_model_c_cost_and_cumulative_total_corruption_fail_closed(self):
        ref = self.trace_ref(8, 1)
        zero = self.record(self.trace_ref(8, 0))["input_index"]
        self.assert_rejected_mutation(8, {ref: self.changed_field(ref, "modeled_action_us", zero)}, "Model-C")
        operation = self.refs(8)[0]
        audit_ref = operation["audit"]
        self.assert_rejected_mutation(8, {audit_ref: self.changed_field(audit_ref, "recorded_total_us", zero)}, "Final state")

    def test_m_chronology_and_certificate_binding_corruption_fail_closed(self):
        first = self.record(self.trace_ref(8, 0))
        ref = self.trace_ref(8, 1)
        self.assert_rejected_mutation(8, {ref: self.changed_field(ref, "preinput_M", first["preinput_M"])}, "chronology")
        last_ref = self.trace_ref(8, 2)
        self.assert_rejected_mutation(8, {last_ref: self.changed_field(last_ref, "M_before", first["M_before"])}, "separation")
        certificate = self.by_index[8].actions[1].acquisitions[0].certificate.node_index
        cert = self.record(certificate)
        self.assert_rejected_mutation(8, {certificate: self.changed_field(certificate, "retained_mines",
                                                                         self.record(ref)["preinput_M"])})
        audit_ref = self.by_index[8].actions[1].acquisitions[0].accepted_audit.node_index
        audit = self.record(audit_ref)
        self.assert_rejected_mutation(8, {audit_ref: self.changed_field(audit_ref, "owned_M_after", cert["retained_mines"])},
                                      "audit M chronology")
        self.assert_rejected_mutation(8, {audit_ref: self.changed_field(audit_ref, "boundary", first["input_index"])},
                                      "acquisition audit")

    def test_no_final_m_repair_from_terminal_truth(self):
        _, archive, _, _ = self.refs(8)
        result_ref = archive["result"]
        empty = self.record(self.trace_ref(8, 0))["preinput_M"]
        self.assert_rejected_mutation(8, {result_ref: self.changed_field(result_ref, "final_M", empty)}, "Final state")

    def test_incomplete_action_stream_and_nonterminal_result_fail_closed(self):
        _, archive, result, _ = self.refs(8)
        traces_ref = result["traces"]
        truncated = ["tuple", list(self.graph.sequence(traces_ref)[:-1])]
        self.assert_rejected_mutation(8, {traces_ref: truncated}, "Incomplete action")
        status_ref = self.record(self.trace_ref(8, 2))["status_after"]
        self.assert_rejected_mutation(8, {status_ref: ["enum", "core_engine.GameStatus", "PLAYING"]}, "Terminal status")

    def test_schedule_case_and_layout_fingerprint_tamper_fail_closed(self):
        operation, archive, _, _ = self.refs(8)
        schedule_ref = archive["schedule_entry"]
        schedule = self.record(schedule_ref)
        zero = self.record(self.trace_ref(8, 0))["input_index"]
        self.assert_rejected_mutation(8, {schedule_ref: self.changed_field(schedule_ref, "schedule_index", zero)}, "identity")
        case = self.record(archive["case"])
        fingerprint_ref = case["board_fingerprint"]
        self.assert_rejected_mutation(8, {fingerprint_ref: ["str", "0" * 64]}, "fingerprint")
        other_archive = self.refs(14)[1]
        self.assert_rejected_mutation(8, {operation["archive"]: self.changed_field(
            operation["archive"], "case", other_archive["case"])})

    def test_failed_audit_and_missing_acquisition_audit_fail_closed(self):
        _, _, _, audit = self.refs(8)
        self.assert_rejected_mutation(8, {audit["audit_status"]: ["str", "FAIL"]}, "audit")
        self.assert_rejected_mutation(8, {audit["acquisition_audits"]: ["tuple", []]}, "Missing accepted")

    def test_multiple_selection_is_atomic_when_a_later_projection_fails(self):
        original = adapter._project_run
        def project(*args):
            if args[2] == 14:
                raise adapter.KTraceAdapterError("second selected record failed")
            return original(*args)
        with patch.object(adapter, "_project_run", side_effect=project), self.assertRaisesRegex(
                adapter.KTraceAdapterError, "second selected"):
            adapter.project_accepted_e1_traces(self.qualification, self.complete, self.profile, schedule_indices=(8, 14))

    def test_loader_cannot_import_gameplay_research_modules_or_write_files(self):
        # Fresh process avoids hiding forbidden imports in sys.modules. The
        # audit hook also blocks subprocess/network/file writes during loading.
        script = textwrap.dedent('''
            import importlib.abc
            import os
            from pathlib import Path
            import sys
            root = Path.cwd()
            local_modules = {p.stem for p in root.glob('*.py')}
            class NoExecutionImports(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if (fullname.split('.')[0] in local_modules or
                        (fullname.startswith('experiments.') and fullname != 'experiments.program_k_trace_adapter')):
                        raise AssertionError('Forbidden execution dependency: ' + fullname)
            sys.meta_path.insert(0, NoExecutionImports())
            def guard(event, args):
                if event == 'open':
                    mode, flags = args[1:3]
                    assert not (isinstance(mode, str) and any(c in mode for c in 'wax+'))
                    assert not (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
                assert not event.startswith(('subprocess.', 'socket.'))
                assert event not in ('os.system', 'os.remove', 'os.rename', 'os.mkdir')
            sys.addaudithook(guard)
            from experiments.program_k_trace_adapter import load_accepted_e1_traces, ACCEPTED_RUN_ID
            views = load_accepted_e1_traces(root / 'results/program_k_research' / ACCEPTED_RUN_ID,
                                          schedule_indices=(8, 14, 20, 26))
            assert [v.case.case_id for v in views] == ['S-LIFECYCLE', 'S-REPLAN', 'S-LOSS', 'X-0']
            assert not any(name in sys.modules for name in local_modules)
            print('D1 import/write/execution boundary PASS')
        ''')
        completed = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT,
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("boundary PASS", completed.stdout)

    def test_accepted_input_files_are_unchanged(self):
        for path, digest in ((ARTIFACT / "qualification.json", adapter.QUALIFICATION_SHA256),
                             (ARTIFACT / "COMPLETE.json", adapter.COMPLETE_SHA256),
                             (PROFILE, adapter.PROFILE_SHA256)):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
