"""New exhibition focused fixtures only; no E1 verdict/archive or corpus run."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import pickle
import unittest
from unittest.mock import patch
import weakref

from benchmark_board import calculate_board_fingerprint
from core_engine import Action, GameStatus, MinesweeperEngine
from experiments import random_expert_exhibition_execution as execution
from experiments import random_expert_exhibition_model as model
from experiments.program_k_runner import run_control_capture, run_k_p0
from experiments.random_expert_exhibition_worker import calculate
from stage3_physical import load_timing_table
from stage3_runner import run_stage3


FIXTURES = ((4, 1, frozenset({(1, 0)})),
            (5, 1, frozenset({(1, 0), (2, 0)})),
            (5, 4, frozenset({(1, 2), (3, 2)})))


def engine_for(width=4, height=1, mines=frozenset({(1, 0)})):
    engine = MinesweeperEngine(width, height, len(mines))
    engine.reset_with_mines(width, height, len(mines), mines)
    return engine


def fixture_traces(fixture=FIXTURES[0]):
    w, h, mines = fixture
    return execution._run_layout(w, h, mines, calculate_board_fingerprint(w, h, len(mines), mines),
                                 load_timing_table(), lambda *args: None)


def synthetic_expert_pair(index=11):
    """Explicit GUI/transport-only synthetic data, NEVER native execution evidence.

Native projection correctness is tested separately with real small engines.
"""
    rows = tuple((model.HIDDEN,) * 30 for _ in range(16))
    flags = frozenset((i % 30, i // 30) for i in range(381, 480))
    final = tuple(tuple(model.FLAGGED if (x, y) in flags else 0 for x in range(30)) for y in range(16))
    empty = frozenset()
    first = model.ExhibitionFrame(0, rows, "PLAYING", (0, 0), 0, empty, empty, empty)
    last = model.ExhibitionFrame(1, final, "WON", (0, 0), 126005, empty, empty, flags)
    action = model.ExhibitionAction(0, "OPEN", (0, 0), (0, 0), 126005, "WON", empty, empty, 381)
    source = model.ExhibitionSource("synthetic-test", True, "fixture only", "test", (), (), ())
    return model.ExhibitionPair(model.ExhibitionBoard(index, index, "a" * 64),
                                model.ExhibitionTrace("V1", (action,), (first, last)),
                                model.ExhibitionTrace("K-P0", (action,), (first, last)), source)


class ExhibitionExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_timing_table()

    def test_index_edges_and_all_invalid_values_before_generation(self):
        for index in (0, 99999):
            self.assertEqual(model.validate_index(index), index)
        for index in (-1, 100000, 2010000, 2010099, True, False, 1.0, "11", None):
            with self.subTest(index=index), patch.object(execution, "generate_board") as generate:
                with self.assertRaises(ValueError):
                    execution.run_expert_pair(index)
                generate.assert_not_called()

    def test_draw_has_one_random_call_and_only_skips_current(self):
        for current in (0, 11, 99999):
            for raw in (0, 10, 11, 99998):
                with patch.object(model, "randbelow", return_value=raw) as draw:
                    selected = model.draw_index(current)
                    self.assertEqual(selected, raw + (raw >= current))
                    self.assertNotEqual(selected, current)
                    draw.assert_called_once_with(99999)
        with patch.object(model, "randbelow", return_value=99999) as draw:
            self.assertEqual(model.draw_index(), 99999)
            draw.assert_called_once_with(100000)

    def test_generator_once_at_allowed_edges_without_running_solvers(self):
        for index in (0, 99999):
            source = synthetic_expert_pair().source
            sentinel = RuntimeError("stop at installation seam")
            with patch.object(execution, "capture_source", return_value=source), \
                    patch.object(execution, "generate_board", wraps=execution.generate_board) as generate, \
                    patch.object(execution, "_run_layout", side_effect=sentinel) as run:
                with self.assertRaisesRegex(RuntimeError, "installation seam"):
                    execution.run_expert_pair(index)
                generate.assert_called_once_with(execution.EXPERT_GENERAL_V1, index)
                self.assertEqual(run.call_args.args[:2], (30, 16))
                self.assertEqual(len(run.call_args.args[2]), 99)

    def test_actual_calls_fresh_engines_same_layout_table_and_release(self):
        native_ref, engines, seen_tables = [], [], []
        def control(engine, *, table):
            engines.append(engine)
            seen_tables.append(table)
            result = run_control_capture(engine, table=table)
            native_ref.append(weakref.ref(result))
            return result
        def kp0(engine, *, table, capture_effects):
            self.assertIsNone(native_ref[0]())  # full V1 evidence released before K
            self.assertTrue(capture_effects)
            self.assertIsNot(engine, engines[0])
            self.assertEqual(engine.get_board_snapshot().mines, engines[0].get_board_snapshot().mines)
            self.assertTrue(all(v == -2 for row in engine.get_observation() for v in row))
            self.assertIs(table, seen_tables[0])
            engines.append(engine)
            return run_k_p0(engine, table=table, capture_effects=True)
        with patch.object(execution, "run_control_capture", side_effect=control) as left, \
                patch.object(execution, "run_k_p0", side_effect=kp0) as right:
            v1, k = fixture_traces()
        left.assert_called_once()
        right.assert_called_once()
        for trace in (v1, k):
            self.assertEqual((trace.actions[0].action, trace.actions[0].target,
                              trace.actions[0].cursor_before), ("OPEN", (0, 0), (0, 0)))

    def test_tiny_native_action_cost_effect_M_and_outcomes(self):
        seen_actions, outcomes = set(), set()
        for fixture in FIXTURES:
            for variant in ("V1", "K-P0"):
                with self.subTest(fixture=fixture[:2], variant=variant):
                    engine = engine_for(*fixture)
                    native = (run_control_capture(engine, table=self.table) if variant == "V1" else
                              run_k_p0(engine, table=self.table, capture_effects=True))
                    trace = execution.project_native(native, variant, self.table)
                    effects = native.effects if variant == "V1" else tuple(t.public_effect for t in native.traces)
                    self.assertEqual(trace.outcome, native.status.name)
                    self.assertEqual(trace.total_modeled_us, native.total_modeled_us)
                    self.assertEqual(len(trace.frames), len(native.traces) + 1)
                    self.assertFalse(trace.frames[0].logical_mines)
                    self.assertEqual(trace.frames[-1].observation, tuple(tuple(row) for row in engine.get_observation()))
                    outcomes.add(trace.outcome)
                    for i, (a, n, e) in enumerate(zip(trace.actions, native.traces, effects)):
                        seen_actions.add(a.action)
                        self.assertEqual((a.action, a.target, a.cursor_before, a.modeled_action_us),
                                         (n.move.action.name, (n.move.x, n.move.y), n.cursor_before, n.modeled_action_us))
                        self.assertEqual(trace.frames[i].observation, e.before_observation)
                        self.assertEqual(trace.frames[i + 1].observation, e.after_observation.rows)
                        self.assertEqual(trace.frames[i + 1].logical_mines,
                                         n.preinput_M if variant == "K-P0" else frozenset())
                        if variant == "K-P0":
                            self.assertEqual(a.M_before, trace.frames[i].logical_mines)
                    self.assertEqual(sum(a.modeled_action_us for a in trace.actions), trace.total_modeled_us)
        self.assertEqual(outcomes, {"WON", "LOST"})
        self.assertEqual(seen_actions, {"OPEN", "FLAG", "CHORD"})

    def test_capture_is_unchanged_frozen_run_stage3(self):
        captured = run_control_capture(engine_for(), table=self.table)
        direct = run_stage3(engine_for(), table=self.table)
        self.assertEqual(captured.status, direct.status)
        self.assertEqual(captured.moves, direct.moves)
        self.assertEqual(captured.total_modeled_us, direct.total_modeled_us)
        self.assertEqual(tuple(replace(t, decision_compute_ns=None) for t in captured.traces),
                         tuple(replace(t, decision_compute_ns=None) for t in direct.traces))

    def test_auto_flags_are_not_inputs_or_invented_M(self):
        v1, k = fixture_traces()
        self.assertEqual(v1.counts, (2, 1, 1))
        self.assertEqual(k.counts, (3, 0, 0))
        self.assertEqual(k.frames[-1].automatic_flags, {(1, 0)})
        self.assertFalse(k.frames[-2].automatic_flags)
        # A one-input win occurs before K has ever analyzed anything (not a zero-opening claim).
        engine = engine_for(2, 1, frozenset({(1, 0)}))
        trace = execution.project_native(run_k_p0(engine, table=self.table, capture_effects=True), "K-P0", self.table)
        self.assertEqual(len(trace.actions), 1)
        self.assertEqual(trace.frames[-1].automatic_flags, {(1, 0)})
        self.assertFalse(trace.frames[-1].logical_mines)

    def test_one_tiny_fresh_engine_repeat_is_semantically_identical(self):
        first, second = fixture_traces(), fixture_traces()
        self.assertEqual(first, second)  # projection deliberately excludes compute ns
        self.assertIsNot(first[0], second[0])

    def test_loss_still_runs_other_side_and_errors_are_not_loss(self):
        phases = []
        w, h, mines = FIXTURES[1]
        pair = execution._run_layout(w, h, mines, calculate_board_fingerprint(w, h, len(mines), mines),
                                     self.table, lambda phase, summary: phases.append(phase))
        self.assertEqual(tuple(t.outcome for t in pair), ("LOST", "LOST"))
        self.assertEqual(phases, ["V1_RUNNING", "K_P0_RUNNING", "PROJECTED"])
        with patch.object(execution, "run_expert_pair", side_effect=RuntimeError("runner fault")):
            envelope = calculate({"token": 1, "index": 11})
        self.assertIsNone(envelope["pair"])
        self.assertIn("runner fault", envelope["error"])

    def test_projection_rejects_cost_M_capture_and_terminal_corruption(self):
        native = run_k_p0(engine_for(), table=self.table, capture_effects=True)
        changes = (
            replace(native, traces=(replace(native.traces[0], modeled_action_us=1),) + native.traces[1:]),
            replace(native, traces=native.traces[:1] + (replace(native.traces[1], M_before=frozenset({(1, 0)})),) + native.traces[2:]),
            replace(native, traces=(replace(native.traces[0], public_effect_status="NOT_EVALUATED"),) + native.traces[1:]),
            replace(native, final_M=frozenset()),
            replace(native, status=GameStatus.PLAYING),
        )
        for changed in changes:
            with self.subTest(changed=changed.status), self.assertRaises(ValueError):
                execution.project_native(changed, "K-P0", self.table)

    def test_presentation_is_frozen_compact_and_pickle_preserves_it(self):
        trace = fixture_traces()[1]
        with self.assertRaises(FrozenInstanceError):
            trace.variant = "other"
        self.assertEqual(pickle.loads(pickle.dumps(trace)), trace)
        self.assertFalse(hasattr(trace, "selection"))
        self.assertFalse(hasattr(trace, "answer_reference"))
        with self.assertRaises(ValueError):
            replace(trace, frames=trace.frames[1:])
        with self.assertRaises(ValueError):
            replace(trace, frames=(replace(trace.frames[0], logical_mines=frozenset({(1, 0)})),) + trace.frames[1:])

    def test_time_to_win_comparison_requires_both_won(self):
        pair = synthetic_expert_pair()
        self.assertEqual(pair.time_to_win_difference_us, 0)
        # This property depends on actual outcomes, not total cost sign.
        for left, right in (("WON", "LOST"), ("LOST", "WON"), ("LOST", "LOST")):
            from types import SimpleNamespace
            view = SimpleNamespace(v1=SimpleNamespace(outcome=left), k=SimpleNamespace(outcome=right))
            self.assertIsNone(model.ExhibitionPair.time_to_win_difference_us.fget(view))

    def test_new_modules_do_not_import_D5_archive_or_research_harness(self):
        import ast
        for path in (execution.ROOT / "experiments").glob("random_expert_exhibition*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            self.assertFalse(any("trace_adapter" in name or "trace_comparison" in name
                                 or "harness" in name or "e1_" in name or "e2_" in name for name in imports), path)


if __name__ == "__main__":
    unittest.main()
