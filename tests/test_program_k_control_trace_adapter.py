"""D4.1 CONTROL tests: retained bytes only; missing evidence is never generated."""

import ast
from collections import Counter
from dataclasses import FrozenInstanceError, fields, is_dataclass
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from experiments import program_k_control_trace_adapter as c
from experiments import program_k_trace_adapter as k


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "results/program_k_research" / k.ACCEPTED_RUN_ID
PROFILE = ROOT / "calibration/stage3_physical_profile_v1.json"
HAS_EVIDENCE = all((ARTIFACT / name).is_file() for name in ("qualification.json", "COMPLETE.json"))


class PortableControlTests(unittest.TestCase):
    def test_only_four_unique_repetition_one_control_indices(self):
        self.assertEqual(c._indices((24, 6, 18, 12)), (24, 6, 18, 12))
        for value in ((), [], (True,), (6.0,), (0,), (7,), (8,), (9,), (10,), (11,), (25,), (26,),
                      (6, 6), (6, 12, 18, 24, 30), "6"):
            with self.subTest(value=value), self.assertRaises(c.ControlTraceAdapterError):
                c.project_accepted_control_traces(b"", b"", b"", schedule_indices=value)

    def test_imports_are_stdlib_and_d1_only(self):
        tree = ast.parse(Path(c.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                if node.module == "experiments":
                    self.assertEqual([a.name for a in node.names], ["program_k_trace_adapter"])
                else:
                    self.assertIn(node.module.split(".")[0], sys.stdlib_module_names)
            elif isinstance(node, ast.Import):
                self.assertTrue(all(a.name.split(".")[0] in sys.stdlib_module_names for a in node.names))

    def test_control_types_have_no_k_knowledge_or_category_fields(self):
        forbidden = {"logical_mines", "hidden_logical_mines", "M_before", "preinput_M", "category",
                     "acquisitions", "certificate", "selection", "shadow"}
        for cls in (c.ControlTracePresentation, c.ControlTraceFrame, c.ControlActionView):
            self.assertTrue(forbidden.isdisjoint(f.name for f in fields(cls)))

    def test_public_pin_fails_before_traversal(self):
        with patch.object(k, "_sources", side_effect=AssertionError("untrusted traversal")):
            with self.assertRaises(c.ControlTraceAdapterError):
                c.project_accepted_control_traces(b"corrupt", b"truncated", b"profile")

    def test_exact_profile_pin_and_table_family(self):
        profile = PROFILE.read_bytes()
        self.assertEqual(hashlib.sha256(profile).hexdigest(), k.PROFILE_SHA256)
        table = k._timing_table(k._pinned_json(profile, k.PROFILE_SIZE, k.PROFILE_SHA256, "profile"))
        self.assertEqual((len(table), len(table[0]), table[0][0], table[2][0]), (30, 16, 126005, 180604))

    def test_incomplete_and_extra_files_fail_before_projection(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(c, "project_accepted_control_traces") as project:
            path = Path(tmp)
            for name in (None, "qualification.json", "COMPLETE.json", "extra.json"):
                if name:
                    (path / name).write_bytes(b"")
                with self.assertRaises(c.ControlTraceAdapterError):
                    c.load_accepted_control_traces(path)
            project.assert_not_called()

    def test_link_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for method in ("is_symlink", "is_junction"):
                with patch.object(Path, method, return_value=True), self.assertRaises(c.ControlTraceAdapterError):
                    c.load_accepted_control_traces(tmp)

    def test_automatic_win_flags_are_not_extra_inputs(self):
        explicit, automatic, safe, flag = c._physical_effect(
            ((1, -2, -2, -2),), ((1, -3, 1, 0),), "OPEN", (3, 0), "WON", frozenset())
        self.assertEqual((explicit, automatic, safe, flag), (frozenset(), frozenset({(1, 0)}), 2, 0))

    def test_loss_false_flag_is_not_a_mine_or_an_unflag_input(self):
        before = ((1, -3, -2, -2, -2),)
        after = ((1, -6, -4, -5, -2),)
        explicit, automatic, safe, flag = c._physical_effect(before, after, "OPEN", (2, 0), "LOST", frozenset({(1, 0)}))
        self.assertEqual((explicit, automatic, safe, flag), (frozenset({(1, 0)}), frozenset(), 0, 0))
        self.assertEqual(k._cells(after, c.FLAGGED, c.EXPLODED, c.MINE), frozenset({(2, 0), (3, 0)}))
        self.assertEqual(after, ((1, -6, -4, -5, -2),))

    def test_public_effect_rejects_unrecorded_flags_and_changed_clues(self):
        for before, after, action, target in (
                (((1, -2, -2),), ((1, -3, 1),), "OPEN", (2, 0)),
                (((1, -2, -2),), ((2, -3, -2),), "FLAG", (1, 0)),
                (((1, -2, -2),), ((1, -3, 1),), "FLAG", (1, 0))):
            with self.subTest(after=after), self.assertRaises(c.ControlTraceAdapterError):
                c._physical_effect(before, after, action, target, "PLAYING", frozenset())

    def test_closed_d1_source_bytes_unchanged(self):
        expected = {
            "experiments/program_k_trace_adapter.py": "43eea1a8f68ab8e333999d2b4f3ba7c4cd1e7b60a19e970a0dcb91a990cd61a4",
            "tests/test_program_k_trace_adapter.py": "e03511fd512f92f56f20f831ac36bc6d2a084ee1f55d3f80cdf1edc9a7b6a81c",
        }
        for name, digest in expected.items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest)


@unittest.skipUnless(HAS_EVIDENCE, "Accepted E1 archive absent; never regenerate evidence.")
class AcceptedControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ((ARTIFACT / "qualification.json").read_bytes(),
                    (ARTIFACT / "COMPLETE.json").read_bytes(), PROFILE.read_bytes())
        cls.views = c.project_accepted_control_traces(*cls.data)
        cls.graph, cls.operations, cls.plan, cls.execution, cls.audit_source, cls.provenance, cls.table = c._admit_publication(*cls.data)

    @classmethod
    def record(cls, ref):
        return dict(cls.graph.nodes[ref][2])

    @classmethod
    def refs(cls, index=6):
        operation = cls.record(cls.operations[index])
        archive = cls.record(operation["archive"])
        result = cls.record(archive["result"])
        native = cls.record(result["control"])
        audit = cls.record(operation["audit"])
        return operation, archive, result, native, audit

    def reject(self, changes, index=6):
        # Behind-pin mutation tests exercise semantic admission without weakening
        # the public byte authentication API. No mutated bytes reach disk.
        nodes = self.graph.nodes[:]
        for ref, value in changes.items():
            nodes[ref] = value
        graph = k._Graph(["e1-dag-v1", self.graph.root, nodes])
        with self.assertRaises((c.ControlTraceAdapterError, k.KTraceAdapterError)):
            c._project_run(graph, self.operations[index], index, self.plan, self.execution,
                           self.audit_source, self.provenance, self.table)

    def field(self, ref, name, replacement):
        node = self.graph.nodes[ref]
        self.assertIn(name, dict(node[2]))
        return [node[0], node[1], [[key, replacement if key == name else value] for key, value in node[2]]]

    def test_all_four_control_results_match_archived_acceptance_facts(self):
        expected = ((6, "S-LIFECYCLE", "WON", 4, 2, 1, 1, 504020),
                    (12, "S-REPLAN", "WON", 15, 5, 5, 5, 2469364),
                    (18, "S-LOSS", "LOST", 3, 2, 1, 0, 378015),
                    (24, "X-0", "WON", 227, 42, 99, 86, 39987084))
        for view, row in zip(self.views, expected, strict=True):
            counts = Counter(a.action for a in view.actions)
            self.assertEqual((view.case.schedule_index, view.case.case_id, view.terminal_status, len(view.actions),
                              counts["OPEN"], counts["FLAG"], counts["CHORD"], view.total_modeled_us), row)
            self.assertEqual((view.case.variant, view.case.repetition, view.provenance.variant), ("CONTROL", 1, "CONTROL"))

    def test_all_public_frames_actions_cursors_and_costs_are_exact(self):
        for view in self.views:
            initial = view.frame(0)
            self.assertEqual(initial.observation, tuple((-2,) * view.case.width for _ in range(view.case.height)))
            self.assertEqual((initial.status, initial.cursor, initial.cumulative_modeled_us), ("PLAYING", (0, 0), 0))
            total = 0
            for i, action in enumerate(view.actions):
                before, after = view.frame(i), view.frame(i + 1)
                raw = self.record(action.effect.node_index)
                rows = self.record(raw["after_observation"])["rows"]
                self.assertEqual(before.observation, self.graph.grid(raw["before_observation"], view.case.width, view.case.height, "PLAYING"))
                self.assertEqual(after.observation, self.graph.grid(rows, view.case.width, view.case.height, after.status))
                self.assertEqual((action.input_index, action.cursor_before, after.cursor), (i, before.cursor, action.target))
                self.assertEqual(k._move(self.graph, raw["move"], view.case.width, view.case.height, effect=True), (action.action, action.target))
                self.assertEqual(action.modeled_action_us, self.graph.integer(raw["modeled_action_us"]))
                total += action.modeled_action_us
                self.assertEqual((action.cumulative_modeled_us, after.cumulative_modeled_us), (total, total))
                self.assertEqual(view.completed_route(i + 1), tuple(a.target for a in view.actions[:i + 1]))
            for bad in (-1, True, len(view.frames)):
                with self.assertRaises(c.ControlTraceAdapterError):
                    view.frame(bad)

    def test_explicit_flags_come_only_from_executed_flag_actions(self):
        for view in self.views:
            explicit = frozenset()
            for i, action in enumerate(view.actions, 1):
                if action.action == "FLAG":
                    explicit |= {action.target}
                self.assertEqual(view.frame(i).explicit_flags, explicit)
                self.assertEqual(view.frame(i).automatic_flags, view.frame(i).public_flags - explicit
                                 if view.frame(i).status == "WON" else frozenset())
        self.assertEqual(self.views[0].frame(2).observation, ((1, -3, -2, -2),))

    def test_loss_feedback_and_terminal_layout_authority(self):
        loss = self.views[2]
        self.assertEqual(loss.frames[-1].observation, ((1, -3, -4, -2, -2),))
        for view in self.views:
            mines = k._cells(view.frames[-1].observation, c.FLAGGED, c.EXPLODED, c.MINE)
            self.assertEqual(mines, view.answer_reference.mines)
            self.assertEqual(k._fingerprint(view.case.width, view.case.height, view.case.num_mines, mines), view.case.board_fingerprint)
            self.assertEqual(view.answer_reference.terminal_effect, view.actions[-1].effect)

    def test_empty_replay_audits_are_correct_control_authority(self):
        for view in self.views:
            audit = self.refs(view.case.schedule_index)[4]
            self.assertEqual(self.graph.sequence(audit["replay_audits"]), ())
            self.assertEqual(len(self.graph.sequence(audit["v1_audits"])), len(view.actions))
        operation, _, _, _, audit = self.refs()
        self.reject({operation["audit"]: self.field(operation["audit"], "replay_audits", audit["v1_audits"])})

    def test_missing_failed_or_shadow_v1_audit_rejected(self):
        audit = self.refs()[4]
        self.reject({audit["v1_audits"]: ["tuple", []]})
        ref = self.graph.sequence(audit["v1_audits"])[0]
        v1 = self.record(ref)
        self.reject({v1["status"]: ["str", "FAIL"]})
        self.reject({ref: self.field(ref, "external_flag", v1["input_index"])})

    def test_failed_public_effect_and_cost_audits_rejected(self):
        audit = self.refs()[4]
        public = self.record(audit["public_effect_audit"])
        cost = self.record(self.graph.sequence(audit["cost_audits"])[0])
        self.reject({public["status"]: ["str", "FAIL"]})
        self.reject({cost["status"]: ["str", "FAIL"]})
        self.reject({cost["expected_us"]: ["int", "0x1"]})
        self.reject({public["boundary"]: ["int", "0x1"]})

    def test_contiguous_v1_effect_and_cost_indices_required(self):
        _, _, result, _, audit = self.refs()
        for field in (self.record(self.graph.sequence(result["effects"])[2])["input_index"],
                      self.record(self.graph.sequence(audit["v1_audits"])[2])["input_index"],
                      self.record(self.graph.sequence(audit["cost_audits"])[2])["input_index"]):
            self.reject({field: ["int", "0x63"]})

    def test_incomplete_and_reordered_streams_rejected(self):
        _, _, result, native, audit = self.refs()
        for ref in (result["effects"], native["traces"], result["timings"], audit["cost_audits"], audit["v1_audits"]):
            refs = self.graph.sequence(ref)
            self.reject({ref: ["tuple", list(refs[:-1])]})
        self.reject({native["traces"]: ["tuple", list(reversed(self.graph.sequence(native["traces"])))]})

    def test_cursor_move_and_before_observation_binding(self):
        _, _, result, native, _ = self.refs()
        trace_ref = self.graph.sequence(native["traces"])[2]
        trace = self.record(trace_ref)
        effect_ref = self.graph.sequence(result["effects"])[2]
        effect = self.record(effect_ref)
        other = self.record(self.graph.sequence(result["effects"])[0])
        self.reject({trace_ref: self.field(trace_ref, "cursor_before", other["cursor_before"])})
        self.reject({effect_ref: self.field(effect_ref, "move", other["move"])})
        self.reject({effect_ref: self.field(effect_ref, "before_observation", other["before_observation"])})
        self.reject({effect_ref: self.field(effect_ref, "cursor_after", effect["cursor_before"])})

    def test_status_and_model_cost_counter_tamper_rejected(self):
        _, _, result, native, audit = self.refs()
        trace = self.record(self.graph.sequence(native["traces"])[-1])
        effect = self.record(self.graph.sequence(result["effects"])[-1])
        self.reject({trace["status_after"]: ["enum", "core_engine.GameStatus", "PLAYING"]})
        for ref in (trace["modeled_action_us"], effect["modeled_action_us"], audit["recorded_total_us"]):
            self.reject({ref: ["int", "0x1"]})
        self.reject({effect["safe_cells_opened_delta"]: ["int", "0x63"]})

    def test_schedule_variant_repetition_and_case_binding(self):
        operation, archive, _, _, _ = self.refs()
        schedule = self.record(archive["schedule_entry"])
        for field, encoded in (("variant", ["str", "K-CONTROL"]), ("variant", ["str", "K-P0"]),
                               ("repetition", ["int", "0x2"]), ("schedule_index", ["int", "0x8"])):
            self.reject({schedule[field]: encoded})
        other_case = self.refs(12)[1]["case"]
        self.reject({operation["archive"]: self.field(operation["archive"], "case", other_case)})

    def test_materialization_and_source_bindings_required(self):
        operation, archive, _, _, _ = self.refs()
        material = self.record(archive["receipt"])
        self.reject({material["fresh_engine"]: ["bool", False]})
        self.reject({material["materialization_method"]: ["str", "UNBOUND"]})
        self.reject({archive["plan_source_digest"]: ["str", "0" * 64]})
        receipt = self.record(operation["receipt"])
        self.reject({receipt["operational_source_digest"]: ["str", "0" * 64]})

    def test_complete_receipt_and_result_type_required(self):
        operation, archive, _, _, audit = self.refs()
        receipt = self.record(operation["receipt"])
        for ref in (archive["completion_status"], receipt["status"]):
            self.reject({ref: ["str", "INCOMPLETE"]})
        self.reject({audit["audit_status"]: ["str", "FAIL"]})
        raw = self.graph.nodes[archive["result"]]
        self.reject({archive["result"]: [raw[0], "experiments.program_k_runner.KRunResult", raw[2]]})
        self.reject({receipt["physical_inputs"]: ["int", "0x3"]})

    def test_p3_is_archived_control_binding_not_recomputed(self):
        audit = self.refs()[4]
        p3 = self.record(audit["p3_audit"])
        for ref, value in ((audit["p3_status"], "INCOMPLETE"), (p3["variant"], "K-CONTROL"),
                           (p3["archive_digest"], "0" * 64)):
            self.reject({ref: ["str", value]})
        self.assertEqual(self.views[0].p3_archive_sha256, c._P3_DIGESTS[0])

    def test_registration_fingerprint_tamper_rejected(self):
        case = self.record(self.refs()[1]["case"])
        self.reject({case["board_fingerprint"]: ["str", "0" * 64]})

    def test_byte_corruption_or_truncation_rejected_for_each_input(self):
        for i in range(3):
            for replacement in (self.data[i][:-1], bytes([self.data[i][0] ^ 1]) + self.data[i][1:]):
                damaged = list(self.data)
                damaged[i] = replacement
                with self.subTest(input=i), self.assertRaises(c.ControlTraceAdapterError):
                    c.project_accepted_control_traces(*damaged)

    def test_output_is_deeply_immutable(self):
        def visit(value):
            if is_dataclass(value):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, fields(value)[0].name, None)
                for field in fields(value):
                    visit(getattr(value, field.name))
            elif type(value) in (tuple, frozenset):
                for item in value:
                    visit(item)
            else:
                self.assertIn(type(value), (str, int, bool, type(None)))
        for view in self.views:
            visit(view)

    def test_later_control_failure_publishes_no_partial_collection(self):
        original = c._project_run
        def project(*args):
            if args[2] == 24:
                raise c.ControlTraceAdapterError("last record rejected")
            return original(*args)
        with patch.object(c, "_project_run", side_effect=project), self.assertRaisesRegex(c.ControlTraceAdapterError, "last record"):
            c.project_accepted_control_traces(*self.data)

    def test_loader_import_write_and_execution_boundary_in_fresh_process(self):
        script = textwrap.dedent('''
            import importlib.abc
            import os
            from pathlib import Path
            import sys
            root = Path.cwd()
            local = {p.stem for p in root.glob('*.py')}
            allowed = {'experiments.program_k_trace_adapter', 'experiments.program_k_control_trace_adapter',
                       'experiments.program_k_trace_comparison'}
            class Guard(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if (fullname.split('.')[0] in local or
                        (fullname.startswith('experiments.') and fullname not in allowed)):
                        raise AssertionError('Execution dependency: ' + fullname)
            sys.meta_path.insert(0, Guard())
            def audit(event, args):
                if event == 'open':
                    mode, flags = args[1:3]
                    assert not (isinstance(mode, str) and any(c in mode for c in 'wax+'))
                    assert not (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
                assert not event.startswith(('subprocess.', 'socket.'))
                assert event not in ('os.system', 'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir')
            sys.addaudithook(audit)
            from experiments.program_k_control_trace_adapter import load_accepted_control_traces
            from experiments.program_k_trace_comparison import load_accepted_e1_pairs
            directory = root / 'results/program_k_research/e1-20261022T003214Z-fba3da048d46'
            controls = load_accepted_control_traces(directory)
            pairs = load_accepted_e1_pairs(directory)
            assert len(controls) == len(pairs) == 4
            assert not any(name in sys.modules for name in local)
            print('CONTROL/pair import/write/execution boundary PASS')
        ''')
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("boundary PASS", result.stdout)

    def test_accepted_source_bytes_unchanged(self):
        for path, digest in ((ARTIFACT / "qualification.json", k.QUALIFICATION_SHA256),
                             (ARTIFACT / "COMPLETE.json", k.COMPLETE_SHA256), (PROFILE, k.PROFILE_SHA256)):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
