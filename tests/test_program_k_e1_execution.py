"""Bounded Slice-2 checks; every scheduled-entry runner is mocked.

Fixed boards may be materialized, but no E1 Engine receives a physical input.
Terminal result fixtures below are manually constructed structural test data,
not a frozen case action sequence and not research evidence.
"""

import ast
from contextlib import ExitStack, contextmanager
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from enum import Enum
from fractions import Fraction
import hashlib
import inspect
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import call, patch

import benchmark_board as board
import core_engine
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
from experiments import program_k_e1_execution as execution
from experiments import program_k_e1_harness as e1
from experiments import program_k_evidence as evidence
from experiments import program_k_harness as e0
from experiments import program_k_runner as runner
from simple_algorithm import SimpleMove
import stage3_physical as physical
from stage3_runner import Stage3ActionTrace, Stage3RunResult


ROOT = Path(__file__).resolve().parents[1]
RUNNER_NAMES = ("run_control_capture", "run_k_control", "run_k_p0")
FINGERPRINTS = (
    "7420118e517924990ff86e47fca7c246e84cb17b7941c1525888a5d5962bf55f",
    "202dfd5c0a4e7534eba7ea3885b9755a5485e57b73118f1d052b5ec3bf346d53",
    "6bd8c08c1b59fce179c64708033d6885dc6144d8d61f181570b9ed3c926d07ba",
    "ad299cd7234c269c935af06357607f89cb56bfcb13a82fa813cba9f42340775c",
    "fbd8b8069ef4f449bbc844329579b6538d2b175c1cf99eb22c49c0585322e053",
    "007b8d203106dd32d1b5b6c46052bbeeeb9fde2be89c81023b01519fba1bee9e",
    "58b8e6399a435371a430a75bd0a51035614242662b53015c61eb61292ccdd28a",
    "d191ef5fe000deb925b6c966cf83e8722e2d58c5f105717ab053b290d116b03c",
    "148b48aeda9730e8604bf68b7db8723de896bc8f4c5b741b33191d38edca065c",
)
_PLAN = None


def _plan():
    """A current prospective plan, without reading or rerunning E0 artifacts."""
    global _PLAN
    if _PLAN is None:
        prerequisite = e1.AcceptedE0Prerequisite(
            e1.ACCEPTED_E0_RUN_ID, e1.ACCEPTED_E0_QUALIFICATION_SHA256,
            e1.ACCEPTED_E0_SOURCE_DIGEST, "E0_PASS", "E0_QUALIFIED",
            e1.ACCEPTED_P8_EVIDENCE_DIGEST, e1.FROZEN_SPEC_SHA256,
            e1.FROZEN_PROTOCOL_SHA256, e1.MODEL_ID, e1.PROFILE_SHA256,
            e1.TABLE_SHA256,
        )
        runtime = e1.capture_runtime_identity()
        _PLAN = e1.E1Plan(
            prerequisite, e1.capture_e1_source_identity(prerequisite), runtime,
            e1._seal_fixed_cases(runtime), e1.build_schedule(),
        )
    return _PLAN


def _corrupt(value, **changes):
    """Inject a malformed detached value without changing the valid original."""
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, changes.get(field.name, getattr(value, field.name)))
    return result


def _independent_fingerprint(snapshot):
    values = (snapshot.width, snapshot.height, snapshot.num_mines) + tuple(
        value for cell in sorted(snapshot.mines, key=lambda c: (c[1], c[0]))
        for value in cell
    )
    return hashlib.sha256(
        b"MSLAYOUT1\0" + b"".join(value.to_bytes(4, "big") for value in values)
    ).hexdigest()


def _fake_result(variant, *, status=GameStatus.WON, shadow=None):
    """Construct one synthetic public terminal record without calling a runner."""
    move = SimpleMove(Action.OPEN, 0, 0)
    before = ((int(CellState.HIDDEN),) * 3,)
    after = ((0, 1, int(CellState.FLAGGED)),)
    cost = physical.load_timing_table()[0][0]
    effect = evidence.make_public_effect(
        before, move, after, input_index=0, status_after=status,
        cursor_before=(0, 0), modeled_action_us=cost,
    )
    timings = evidence.DecisionTimings()
    if variant == "CONTROL":
        trace = Stage3ActionTrace(move, None, None, (0, 0), cost, status, 2, 0)
        return runner.ControlCaptureResult(
            Stage3RunResult(status, (trace,)), (effect,), (timings,))
    if variant == "K-CONTROL":
        shadow = runner.ShadowCheckpoint() if shadow is None else shadow
        trace = runner.KControlActionTrace(
            0, before, None, move, (0, 0), cost, status, shadow,
            frozenset(), frozenset(), timings, effect, "CAPTURED",
        )
        return runner.KControlRunResult(status, (trace,), shadow)
    trace = runner.KActionTrace(
        0, move, "POLICY_INITIAL_OPEN", None, (0, 0), cost, status,
        frozenset(), frozenset(), timings, effect, "CAPTURED",
    )
    return runner.KRunResult(status, (trace,), frozenset())


@contextmanager
def _blocked_runners(variant=None, result=None, error=None):
    """Patch every runner owner: a test cannot accidentally execute another one."""
    with ExitStack() as stack:
        mocks = {
            name: stack.enter_context(patch.object(
                runner, name, side_effect=AssertionError("Real E1 runner is prohibited.")))
            for name in RUNNER_NAMES
        }
        if variant is not None:
            selected = mocks[RUNNER_NAMES[e1.VARIANTS.index(variant)]]
            selected.side_effect = error
            selected.return_value = result
        yield mocks


def _archive(variant="CONTROL"):
    plan = _plan()
    source = execution.capture_execution_source_identity(plan)
    _, receipt = execution._materialize_case(plan.cases[0])
    index = e1.VARIANTS.index(variant)
    return execution.E1ScheduledRunArchive(
        source, plan.source_identity.digest, plan.schedule[index], plan.cases[0],
        receipt, _fake_result(variant), 1.0,
        "APPLIED" if variant == "K-CONTROL" else "NOT_APPLICABLE",
    )


class SourceIdentityTests(unittest.TestCase):
    def test_exact_execution_bytes_and_current_slice_one_digest(self):
        plan = _plan()
        identity = execution.capture_execution_source_identity(plan)
        raw = (ROOT / execution.EXECUTION_SOURCE_PATH).read_bytes()
        self.assertEqual(identity.plan_source_digest, plan.source_identity.digest)
        self.assertEqual(identity.execution_file.path, "experiments/program_k_e1_execution.py")
        self.assertEqual(identity.execution_file.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(identity.execution_file.size_bytes, len(raw))
        for name in ("spec_sha256", "protocol_sha256", "model_id", "profile_sha256", "table_sha256"):
            self.assertEqual(getattr(identity, name), getattr(plan.prerequisite, name))

    def test_deterministic_immutable_identity_and_no_test_source(self):
        first = execution.capture_execution_source_identity(_plan())
        second = execution.capture_execution_source_identity(_plan())
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(len(first.digest), 64)
        self.assertNotIn("tests/", repr(first))
        self.assertFalse(hasattr(first, "files"))
        with self.assertRaises(FrozenInstanceError):
            first.plan_source_digest = "0" * 64

    def test_capture_checks_current_slice_one_and_does_no_materialization(self):
        plan = _plan()
        with patch.object(e1, "capture_e1_source_identity", wraps=e1.capture_e1_source_identity) as capture, \
                patch.object(execution, "_materialize_case", side_effect=AssertionError), \
                patch.object(board, "generate_board", side_effect=AssertionError), \
                patch.object(execution, "MinesweeperEngine", side_effect=AssertionError), \
                _blocked_runners():
            execution.capture_execution_source_identity(plan)
        capture.assert_called_once_with(plan.prerequisite)

    def test_slice_one_source_drift_is_refused(self):
        plan = _plan()
        changed = replace(plan.source_identity, files=(
            replace(plan.source_identity.files[0], sha256="0" * 64),
            plan.source_identity.files[1],
        ))
        with patch.object(e1, "capture_e1_source_identity", return_value=changed):
            with self.assertRaises(execution.E1ExecutionError):
                execution.capture_execution_source_identity(plan)

    def test_execution_byte_mutation_changes_identity_at_temporary_root(self):
        plan = _plan()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / execution.EXECUTION_SOURCE_PATH
            source.parent.mkdir()
            source.write_bytes((ROOT / execution.EXECUTION_SOURCE_PATH).read_bytes())
            before = execution._capture_execution_source_identity(plan, root)
            source.write_bytes(source.read_bytes() + b"\n# temporary mutation\n")
            after = execution._capture_execution_source_identity(plan, root)
        self.assertEqual(before.plan_source_digest, after.plan_source_digest)
        self.assertNotEqual(before.execution_file.sha256, after.execution_file.sha256)
        self.assertNotEqual(before.digest, after.digest)
        self.assertGreater(after.execution_file.size_bytes, before.execution_file.size_bytes)

    def test_missing_execution_file_and_bad_plan_are_refused(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(execution.E1ExecutionError):
                execution._capture_execution_source_identity(_plan(), Path(directory))
        for value in (None, object(), _corrupt(_plan(), actual_execution_authorized=True),
                      _corrupt(_plan(), supplement_status="SELECTED")):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(execution.E1ExecutionError):
                    execution.capture_execution_source_identity(value)


class MaterializationTests(unittest.TestCase):
    def assert_fresh(self, engine, receipt, case):
        self.assertIs(type(engine), MinesweeperEngine)
        self.assertIs(engine.status, GameStatus.PLAYING)
        self.assertTrue(all(v == CellState.HIDDEN for row in engine.get_observation() for v in row))
        snapshot = engine.get_board_snapshot()
        self.assertTrue(snapshot.mines_placed)
        self.assertEqual((snapshot.width, snapshot.height, snapshot.num_mines),
                         (case.width, case.height, case.num_mines))
        self.assertEqual(len(snapshot.mines), case.num_mines)
        self.assertNotIn((0, 0), snapshot.mines)
        self.assertEqual(_independent_fingerprint(snapshot), case.board_fingerprint)
        self.assertIs(receipt.fresh_engine, True)
        for name in ("case_id", "source_type", "width", "height", "num_mines",
                     "first_click", "game_index", "seed", "board_fingerprint", "runtime"):
            self.assertEqual(getattr(receipt, name), getattr(case, name))
        self.assertEqual(engine.get_counter_snapshot()["active_clicks"], 0)
        self.assertEqual(engine.get_counter_snapshot()["wasted_clicks"], 0)

    def test_all_synthetic_cases_exact_and_distinct_fresh_engines(self):
        for case, expected in zip(_plan().cases[:4], FINGERPRINTS[:4]):
            with self.subTest(case=case.case_id), \
                    patch.object(board, "generate_board", side_effect=AssertionError):
                first, first_receipt = execution._materialize_case(case)
                second, second_receipt = execution._materialize_case(case)
                self.assertIsNot(first, second)
                self.assertEqual(first_receipt, second_receipt)
                self.assertEqual(first_receipt.materialization_method, "FIXED_SYNTHETIC_RESET")
                self.assertEqual(case.board_fingerprint, expected)
                self.assert_fresh(first, first_receipt, case)
                self.assert_fresh(second, second_receipt, case)

    def test_expert_exactly_one_generation_each_and_exact_fingerprints(self):
        retained_engines = []
        for case, expected in zip(_plan().cases[4:], FINGERPRINTS[4:]):
            with self.subTest(case=case.case_id), \
                    patch.object(board, "generate_board", wraps=board.generate_board) as generate:
                engine, receipt = execution._materialize_case(case)
            generate.assert_called_once_with(board.EXPERT_GENERAL_V1, case.game_index)
            self.assertEqual(receipt.materialization_method, "EXPERT_GENERAL_V1_RESET")
            self.assertEqual(receipt.board_fingerprint, expected)
            self.assert_fresh(engine, receipt, case)
            retained_engines.append(engine)
        self.assertEqual(len({id(engine) for engine in retained_engines}), 5)

    def test_repeated_expert_materialization_is_fresh_without_cache(self):
        case = _plan().cases[4]
        with patch.object(board, "generate_board", wraps=board.generate_board) as generate:
            first, first_receipt = execution._materialize_case(case)
            second, second_receipt = execution._materialize_case(case)
        self.assertIsNot(first, second)
        self.assertEqual(first_receipt, second_receipt)
        self.assertEqual(generate.call_args_list, [
            call(board.EXPERT_GENERAL_V1, case.game_index),
            call(board.EXPERT_GENERAL_V1, case.game_index),
        ])

    def test_wrong_generated_index_seed_layout_and_fingerprint_fail_without_retry(self):
        case = _plan().cases[4]
        original = board.generate_board(board.EXPERT_GENERAL_V1, case.game_index)
        removed = next(iter(original.mine_positions))
        replacement = next((x, y) for y in range(case.height) for x in range(case.width)
                           if (x, y) != (0, 0) and (x, y) not in original.mine_positions)
        changed_layout = original.mine_positions - {removed} | {replacement}
        mined_origin = original.mine_positions - {removed} | {(0, 0)}
        bad_boards = (
            replace(original, game_index=1),
            replace(original, seed=1),
            replace(original, board_fingerprint="0" * 64),
            replace(original, mine_positions=changed_layout),
            replace(original, mine_positions=changed_layout, board_fingerprint=board.calculate_board_fingerprint(
                case.width, case.height, case.num_mines, changed_layout)),
            replace(original, mine_positions=mined_origin, board_fingerprint=board.calculate_board_fingerprint(
                case.width, case.height, case.num_mines, mined_origin)),
            _corrupt(original, game_index=True),
        )
        for generated in bad_boards:
            with self.subTest(generated=generated.board_fingerprint), \
                    patch.object(board, "generate_board", return_value=generated) as generate, \
                    patch.object(execution, "MinesweeperEngine", side_effect=AssertionError) as construct:
                with self.assertRaises(execution.E1ExecutionError):
                    execution._materialize_case(case)
            generate.assert_called_once_with(board.EXPERT_GENERAL_V1, case.game_index)
            construct.assert_not_called()

    def test_generator_exception_has_no_retry_or_engine_construction(self):
        with patch.object(board, "generate_board", side_effect=ValueError("generation failed")) as generate, \
                patch.object(execution, "MinesweeperEngine", side_effect=AssertionError) as construct:
            with self.assertRaises(execution.E1ExecutionError):
                execution._materialize_case(_plan().cases[4])
        self.assertEqual(generate.call_count, 1)
        construct.assert_not_called()

    def test_frozen_expert_spec_change_is_refused_before_generation(self):
        changed = replace(board.EXPERT_GENERAL_V1, benchmark_set_id="OTHER")
        with patch.object(board, "EXPERT_GENERAL_V1", changed), \
                patch.object(board, "generate_board", side_effect=AssertionError) as generate:
            with self.assertRaises(execution.E1ExecutionError):
                execution._materialize_case(_plan().cases[4])
        generate.assert_not_called()

    def test_corrupt_case_and_runtime_are_refused(self):
        case = _plan().cases[0]
        for bad in (None, _corrupt(case, width=4), _corrupt(case, board_fingerprint="0" * 64),
                    _corrupt(case, first_click=(1, 0)), _corrupt(case, case_id="ARBITRARY")):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(execution.E1ExecutionError):
                    execution._materialize_case(bad)
        other_runtime = replace(case.runtime, node="not-the-current-node")
        with self.assertRaises(execution.E1ExecutionError):
            execution._materialize_case(replace(case, runtime=other_runtime))

    def test_finalized_snapshot_identity_is_checked(self):
        case = _plan().cases[0]
        actual = MinesweeperEngine.get_board_snapshot

        def wrong_snapshot(engine):
            snapshot = actual(engine)
            return replace(snapshot, mines=frozenset({(1, 0)})) if snapshot.mines_placed else snapshot

        with patch.object(MinesweeperEngine, "get_board_snapshot", wrong_snapshot):
            with self.assertRaises(execution.E1ExecutionError):
                execution._materialize_case(case)

    def test_receipt_and_seal_are_immutable_and_layout_free(self):
        for case in _plan().cases:
            _, receipt = execution._materialize_case(case)
            for value in (case, receipt):
                self.assertFalse(hasattr(value, "__dict__"))
                self.assertFalse({f.name for f in fields(value)} & {
                    "mines", "mine_positions", "layout", "engine", "snapshot", "definition", "answer",
                })
                self.assertFalse(any(type(getattr(value, f.name)) in (list, dict, set, frozenset)
                                     for f in fields(value)))
            with self.assertRaises(FrozenInstanceError):
                receipt.fresh_engine = False


class DispatchTests(unittest.TestCase):
    def test_exact_three_way_dispatch_and_authenticated_table_object(self):
        plan = _plan()
        for index, variant in enumerate(e1.VARIANTS):
            result = _fake_result(variant)
            table = physical.load_timing_table()
            with self.subTest(variant=variant), _blocked_runners(variant, result) as mocks, \
                    patch.object(physical, "load_timing_table", return_value=table) as load, \
                    patch.object(execution, "_materialize_case", wraps=execution._materialize_case) as materialize:
                archive = execution.execute_scheduled_entry(plan, index, shadow_timeout_s=0.25)
            load.assert_called_once_with()
            materialize.assert_called_once_with(plan.cases[0])
            selected = mocks[RUNNER_NAMES[index]]
            engine = selected.call_args.args[0]
            expected = {"table": table}
            if variant == "K-CONTROL":
                expected.update(shadow_timeout_s=0.25, capture_effects=True)
            elif variant == "K-P0":
                expected["capture_effects"] = True
            selected.assert_called_once_with(engine, **expected)
            self.assertIs(selected.call_args.kwargs["table"], table)
            self.assertEqual(len(selected.call_args.args), 1)
            for name, mock in mocks.items():
                if name != RUNNER_NAMES[index]:
                    mock.assert_not_called()
            self.assertIs(archive.result, result)
            self.assertEqual(archive.schedule_entry, plan.schedule[index])
            self.assertEqual(archive.case, plan.cases[0])
            self.assertEqual(archive.shadow_timeout_s, 0.25)
            self.assertEqual(archive.shadow_timeout_usage,
                             "APPLIED" if variant == "K-CONTROL" else "NOT_APPLICABLE")
            self.assertEqual(archive.completion_status, "COMPLETE")
            self.assertIs(plan.actual_execution_authorized, False)
            self.assertEqual(plan.supplement_status, "NOT_EVALUATED")

    def test_schedule_owns_repetition_case_and_variant(self):
        plan = _plan()
        with _blocked_runners("K-P0", _fake_result("K-P0")):
            archive = execution.execute_scheduled_entry(plan, 5)
        self.assertEqual((archive.schedule_entry.case_id, archive.schedule_entry.repetition,
                          archive.schedule_entry.variant), ("S-WIN", 2, "K-P0"))
        self.assertEqual(set(inspect.signature(execution.execute_scheduled_entry).parameters),
                         {"plan", "schedule_index", "shadow_timeout_s"})
        with self.assertRaises(TypeError):
            execution.execute_scheduled_entry(plan, 0, case=plan.cases[1])
        with self.assertRaises(TypeError):
            execution.execute_scheduled_entry(plan, 0, variant="K-P0")

    def test_schedule_index_rejects_bool_nonint_and_out_of_range_before_materialization(self):
        with _blocked_runners(), patch.object(execution, "_materialize_case", side_effect=AssertionError) as materialize:
            for index in (True, False, -1, 54, 100, 0.0, "0", None):
                with self.subTest(index=index), self.assertRaises(execution.E1ExecutionError):
                    execution.execute_scheduled_entry(_plan(), index)
        materialize.assert_not_called()

    def test_tampered_plan_and_schedule_are_refused(self):
        plan = _plan()
        bad_entry = replace(plan.schedule[0], variant="K-P0")
        bad_plans = (
            None, _corrupt(plan, actual_execution_authorized=True),
            _corrupt(plan, supplement_status="SELECTED"),
            _corrupt(plan, schedule=(bad_entry,) + plan.schedule[1:]),
        )
        with _blocked_runners(), patch.object(execution, "_materialize_case", side_effect=AssertionError):
            for bad in bad_plans:
                with self.subTest(bad=type(bad).__name__), self.assertRaises(execution.E1ExecutionError):
                    execution.execute_scheduled_entry(bad, 0)

    def test_runner_exception_is_once_without_alternate_or_fallback(self):
        for index, variant in enumerate(e1.VARIANTS):
            failure = RuntimeError("injected runner failure")
            with self.subTest(variant=variant), _blocked_runners(variant, error=failure) as mocks, \
                    patch.object(execution, "_materialize_case", wraps=execution._materialize_case) as materialize:
                with self.assertRaises(execution.E1ExecutionError) as caught:
                    execution.execute_scheduled_entry(_plan(), index)
            self.assertIs(caught.exception.__cause__, failure)
            self.assertEqual(materialize.call_count, 1)
            self.assertEqual([m.call_count for m in mocks.values()],
                             [int(i == index) for i in range(3)])

    def test_source_capture_is_before_materialization_and_after_runner(self):
        events = []
        source = execution.capture_execution_source_identity(_plan())
        real_materialize = execution._materialize_case

        def capture(plan):
            events.append("source")
            return source

        def materialize(case):
            events.append("materialize")
            return real_materialize(case)

        result = _fake_result("CONTROL")
        with _blocked_runners("CONTROL", result) as mocks, \
                patch.object(execution, "capture_execution_source_identity", side_effect=capture), \
                patch.object(execution, "_materialize_case", side_effect=materialize):
            def dispatched(*args, **kwargs):
                events.append("runner")
                return result
            mocks["run_control_capture"].side_effect = dispatched
            execution.execute_scheduled_entry(_plan(), 0)
        self.assertEqual(events, ["source", "materialize", "runner", "source"])

    def test_source_change_after_runner_fails_closed(self):
        source = execution.capture_execution_source_identity(_plan())
        changed = replace(source, execution_file=replace(source.execution_file, sha256="0" * 64))
        with _blocked_runners("CONTROL", _fake_result("CONTROL")) as mocks, \
                patch.object(execution, "capture_execution_source_identity", side_effect=(source, changed)):
            with self.assertRaises(execution.E1ExecutionError):
                execution.execute_scheduled_entry(_plan(), 0)
        self.assertEqual(mocks["run_control_capture"].call_count, 1)

    def test_entirely_hidden_playing_engine_required_before_dispatch(self):
        engine, receipt = execution._materialize_case(_plan().cases[0])
        with patch.object(engine, "get_observation", return_value=((0, CellState.HIDDEN, CellState.HIDDEN),)), \
                patch.object(execution, "_materialize_case", return_value=(engine, receipt)), \
                _blocked_runners() as mocks:
            with self.assertRaises(execution.E1ExecutionError):
                execution.execute_scheduled_entry(_plan(), 0)
        self.assertTrue(all(mock.call_count == 0 for mock in mocks.values()))
        engine.status = GameStatus.WON
        with patch.object(execution, "_materialize_case", return_value=(engine, receipt)), _blocked_runners():
            with self.assertRaises(execution.E1ExecutionError):
                execution.execute_scheduled_entry(_plan(), 0)

    def test_prior_input_counter_is_refused_even_with_hidden_observation(self):
        engine, receipt = execution._materialize_case(_plan().cases[0])
        counters = dict(engine.get_counter_snapshot(), active_clicks=1)
        with patch.object(engine, "get_counter_snapshot", return_value=counters), \
                patch.object(execution, "_materialize_case", return_value=(engine, receipt)), _blocked_runners():
            with self.assertRaises(execution.E1ExecutionError):
                execution.execute_scheduled_entry(_plan(), 0)

    def test_materialization_and_table_failures_never_dispatch(self):
        with patch.object(execution, "_materialize_case", side_effect=execution.E1ExecutionError("bad seal")), \
                _blocked_runners() as mocks:
            with self.assertRaises(execution.E1ExecutionError):
                execution.execute_scheduled_entry(_plan(), 0)
        self.assertTrue(all(mock.call_count == 0 for mock in mocks.values()))
        with patch.object(physical, "load_timing_table", side_effect=ValueError("unauthenticated")), \
                _blocked_runners() as mocks:
            with self.assertRaises(execution.E1ExecutionError):
                execution.execute_scheduled_entry(_plan(), 0)
        self.assertTrue(all(mock.call_count == 0 for mock in mocks.values()))

    def test_shadow_failure_is_preserved_without_adjudication(self):
        failure = runner.ShadowFailure("SHADOW_TIMEOUT", 0, None, "synthetic timeout")
        shadow = runner.ShadowCheckpoint(False, frozenset(), None, failure, None, False, True)
        result = _fake_result("K-CONTROL", shadow=shadow)
        with _blocked_runners("K-CONTROL", result):
            archive = execution.execute_scheduled_entry(_plan(), 1)
        self.assertIs(archive.result.shadow.failure, failure)
        self.assertIs(archive.result.shadow.enabled, False)
        self.assertEqual(archive.completion_status, "COMPLETE")

    def test_timeout_invalid_values_rejected_for_every_variant(self):
        with _blocked_runners(), patch.object(execution, "_materialize_case", side_effect=AssertionError):
            for index in range(3):
                for timeout in (True, False, 0, -1, float("nan"), float("inf"),
                                -float("inf"), 60.0001, "1", None):
                    with self.subTest(index=index, timeout=timeout), self.assertRaises(execution.E1ExecutionError):
                        execution.execute_scheduled_entry(_plan(), index, shadow_timeout_s=timeout)

    def test_timeout_exact_numeric_value_retained_and_unused_dispatch_unaffected(self):
        for index, variant in enumerate(e1.VARIANTS):
            for timeout in (1, 60, 0.125):
                with self.subTest(variant=variant, timeout=timeout), \
                        _blocked_runners(variant, _fake_result(variant)) as mocks:
                    archive = execution.execute_scheduled_entry(_plan(), index, shadow_timeout_s=timeout)
                self.assertIs(type(archive.shadow_timeout_s), type(timeout))
                self.assertEqual(archive.shadow_timeout_s, timeout)
                kwargs = mocks[RUNNER_NAMES[index]].call_args.kwargs
                self.assertEqual("shadow_timeout_s" in kwargs, variant == "K-CONTROL")


class ArchiveValidationTests(unittest.TestCase):
    def test_all_variant_archives_are_complete_and_frozen(self):
        for variant in e1.VARIANTS:
            archive = _archive(variant)
            self.assertEqual(archive.completion_status, "COMPLETE")
            with self.assertRaises(FrozenInstanceError):
                archive.completion_status = "OTHER"

    def test_lost_terminal_fake_archives_are_structurally_complete(self):
        for variant in e1.VARIANTS:
            with self.subTest(variant=variant):
                archive = replace(_archive(variant), result=_fake_result(variant, status=GameStatus.LOST))
                self.assertIs(archive.result.status, GameStatus.LOST)
                self.assertEqual(archive.completion_status, "COMPLETE")

    def test_non_e1_tiny_runner_results_validate_nested_public_evidence(self):
        """Real runners are confined to this non-E1 2x2 helper-only seam."""
        geometry = types.SimpleNamespace(width=2, height=2, first_click=(0, 0))
        table = physical.load_timing_table()
        for variant in e1.VARIANTS:
            with self.subTest(variant=variant):
                engine = MinesweeperEngine(2, 2, 1)
                engine.reset_with_mines(2, 2, 1, {(1, 1)})
                if variant == "CONTROL":
                    result = runner.run_control_capture(engine, table=table)
                elif variant == "K-CONTROL":
                    result = runner.run_k_control(
                        engine, table=table, shadow_timeout_s=60, capture_effects=True)
                else:
                    result = runner.run_k_p0(engine, table=table, capture_effects=True)
                self.assertIn(result.status, (GameStatus.WON, GameStatus.LOST))
                self.assertGreater(len(result.traces), 1)
                self.assertIsNone(execution._validate_result(variant, result, geometry))

    def test_wrong_exact_result_class_rejected(self):
        archive = _archive()
        for result in (_fake_result("K-P0"), _fake_result("K-CONTROL"), object(), None):
            with self.subTest(result=type(result).__name__), self.assertRaises(execution.E1ExecutionError):
                replace(archive, result=result)
        class ResultSubclass(runner.ControlCaptureResult):
            pass
        subclass = ResultSubclass(archive.result.control, archive.result.effects, archive.result.timings)
        with self.assertRaises(execution.E1ExecutionError):
            replace(archive, result=subclass)

    def test_empty_traces_rejected_for_all_variants(self):
        results = (
            runner.ControlCaptureResult(Stage3RunResult(GameStatus.WON, ()), (), ()),
            runner.KControlRunResult(GameStatus.WON, (), runner.ShadowCheckpoint()),
            runner.KRunResult(GameStatus.WON, (), frozenset()),
        )
        for variant, result in zip(e1.VARIANTS, results):
            with self.subTest(variant=variant), self.assertRaises(execution.E1ExecutionError):
                replace(_archive(variant), result=result)

    def test_missing_effects_rejected_for_every_variant(self):
        for variant in e1.VARIANTS:
            archive = _archive(variant)
            if variant == "CONTROL":
                result = _corrupt(archive.result, effects=(None,))
            else:
                trace = replace(archive.result.traces[0], public_effect=None, public_effect_status="NOT_EVALUATED")
                result = replace(archive.result, traces=(trace,))
            with self.subTest(variant=variant), self.assertRaises(execution.E1ExecutionError):
                replace(archive, result=result)

    def test_nonterminal_and_disagreeing_terminal_result_rejected(self):
        for variant in e1.VARIANTS:
            archive = _archive(variant)
            for status in (GameStatus.PLAYING, GameStatus.LOST):
                result = (_corrupt(archive.result, control=replace(archive.result.control, status=status))
                          if variant == "CONTROL" else replace(archive.result, status=status))
                with self.subTest(variant=variant, status=status), self.assertRaises(execution.E1ExecutionError):
                    replace(archive, result=result)

    def test_schedule_case_repetition_and_variant_substitution_rejected(self):
        archive = _archive()
        wrong_entries = (
            replace(archive.schedule_entry, case_id="S-LOSS"),
            replace(archive.schedule_entry, repetition=2),
            replace(archive.schedule_entry, variant="K-P0"),
        )
        for entry in wrong_entries:
            with self.subTest(entry=entry), self.assertRaises(execution.E1ExecutionError):
                replace(archive, schedule_entry=entry)
        with self.assertRaises(execution.E1ExecutionError):
            replace(archive, case=_plan().cases[1])

    def test_source_binding_receipt_binding_and_completion_are_required(self):
        archive = _archive()
        changes = (
            {"plan_source_digest": "0" * 64},
            {"execution_source_identity": replace(archive.execution_source_identity, plan_source_digest="0" * 64)},
            {"receipt": _corrupt(archive.receipt, fresh_engine=False)},
            {"receipt": _corrupt(archive.receipt, board_fingerprint="0" * 64)},
            {"receipt": _corrupt(archive.receipt, case_id="S-LOSS")},
            {"completion_status": "PASS"},
            {"shadow_timeout_usage": "APPLIED"},
            {"shadow_timeout_s": True},
        )
        for change in changes:
            with self.subTest(field=tuple(change)), self.assertRaises(execution.E1ExecutionError):
                replace(archive, **change)

    def test_effect_trace_bindings_and_terminal_sequence_are_checked(self):
        archive = _archive("K-P0")
        trace = archive.result.traces[0]
        bad_traces = (
            replace(trace, input_index=1),
            replace(trace, move=SimpleMove(Action.OPEN, 1, 0)),
            replace(trace, cursor_before=(1, 0)),
            replace(trace, modeled_action_us=trace.modeled_action_us + 1),
            replace(trace, public_effect_status="NOT_EVALUATED"),
            replace(trace, status_after=GameStatus.LOST),
        )
        for bad in bad_traces:
            with self.subTest(trace=bad), self.assertRaises(execution.E1ExecutionError):
                replace(archive, result=replace(archive.result, traces=(bad,)))
        with self.assertRaises(execution.E1ExecutionError):
            replace(archive, result=replace(archive.result, traces=(trace, trace)))

    def test_constructor_validation_is_pure(self):
        archive = _archive()
        with patch.object(e1, "capture_e1_source_identity", side_effect=AssertionError), \
                patch.object(e1, "capture_runtime_identity", side_effect=AssertionError), \
                patch.object(board, "generate_board", side_effect=AssertionError), \
                patch.object(physical, "load_timing_table", side_effect=AssertionError), \
                patch.object(Path, "read_bytes", side_effect=AssertionError), _blocked_runners():
            self.assertEqual(replace(archive), archive)

    def test_mutable_unknown_or_live_payloads_cannot_enter_result_graph(self):
        archive = _archive("K-P0")
        trace = archive.result.traces[0]
        engine = MinesweeperEngine(3, 1, 1)
        bad_payloads = ([], {}, set(), engine, engine.get_board_snapshot(), lambda: None,
                        types.SimpleNamespace(hidden="payload"))
        for payload in bad_payloads:
            bad_trace = _corrupt(trace, selection=payload)
            with self.subTest(payload=type(payload).__name__), self.assertRaises(execution.E1ExecutionError):
                replace(archive, result=replace(archive.result, traces=(bad_trace,)))

    def test_extra_attachments_and_cycles_cannot_enter_result_graph(self):
        archive = _archive("K-P0")
        attached = replace(archive.result.traces[0])
        object.__setattr__(attached, "hidden_payload", {"secret": "not evidence"})
        with self.assertRaises(execution.E1ExecutionError):
            replace(archive, result=replace(archive.result, traces=(attached,)))
        cyclic = replace(archive.result.traces[0])
        object.__setattr__(cyclic, "selection", cyclic)
        with self.assertRaises(execution.E1ExecutionError):
            replace(archive, result=replace(archive.result, traces=(cyclic,)))

    def test_k_logical_timing_and_shadow_record_shapes_are_exact(self):
        for variant in ("K-CONTROL", "K-P0"):
            archive = _archive(variant)
            trace = archive.result.traces[0]
            for change in ({"M_before": ()}, {"preinput_M": ()}, {"timings": None},
                           {"input_index": False}, {"modeled_action_us": True}):
                bad = _corrupt(trace, **change)
                with self.subTest(variant=variant, change=change), self.assertRaises(execution.E1ExecutionError):
                    replace(archive, result=replace(archive.result, traces=(bad,)))
        archive = _archive("K-CONTROL")
        with self.assertRaises(execution.E1ExecutionError):
            replace(archive, result=replace(archive.result, shadow=None))
        with self.assertRaises(execution.E1ExecutionError):
            replace(archive, result=replace(
                archive.result, traces=(replace(archive.result.traces[0], shadow=None),)))
        archive = _archive("K-P0")
        with self.assertRaises(execution.E1ExecutionError):
            replace(archive, result=_corrupt(archive.result, final_M=()))

    def test_archive_graph_contains_only_detached_immutable_evidence(self):
        def inspect_graph(value):
            self.assertNotIsInstance(value, (MinesweeperEngine, core_engine.BoardSnapshot, list, dict, set))
            self.assertFalse(callable(value))
            if is_dataclass(value):
                self.assertTrue(type(value).__dataclass_params__.frozen)
                for field in fields(value):
                    inspect_graph(getattr(value, field.name))
            elif type(value) in (tuple, frozenset):
                for item in value:
                    inspect_graph(item)
            else:
                self.assertTrue(value is None or type(value) in (str, int, float, bool, Fraction)
                                or isinstance(value, Enum), type(value))
        for variant in e1.VARIANTS:
            inspect_graph(_archive(variant))


class ContainmentTests(unittest.TestCase):
    def test_import_has_no_artifact_generation_engine_table_runner_or_write_side_effects(self):
        source = Path(execution.__file__).read_text(encoding="utf-8")
        namespace = types.ModuleType("_slice_two_import_side_effect_check")
        namespace.__file__ = execution.__file__
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {namespace.__name__: namespace}))
            for owner, name in (
                (e1, "load_accepted_e0_prerequisite"), (e0, "read_qualification_artifact"),
                (e1, "capture_runtime_identity"), (board, "generate_board"),
                (core_engine, "MinesweeperEngine"), (physical, "load_timing_table"),
                (Path, "read_bytes"), (Path, "read_text"), (Path, "write_bytes"),
                (Path, "write_text"), (Path, "mkdir"), (Path, "open"),
            ):
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError("Import side effect")))
            stack.enter_context(patch("builtins.open", side_effect=AssertionError("Import file access")))
            stack.enter_context(_blocked_runners())
            exec(compile(source, execution.__file__, "exec"), namespace.__dict__)
        self.assertTrue(hasattr(namespace, "execute_scheduled_entry"))

    def test_source_has_no_persistence_orchestration_verdict_or_other_stage_execution(self):
        tree = ast.parse(Path(execution.__file__).read_text(encoding="utf-8"))
        forbidden_calls = {
            "write", "write_bytes", "write_text", "mkdir", "makedirs", "dump",
            "persist", "execute_e0", "run_e0", "scan_p8", "verify_p8",
            "select_supplement", "run_e2", "run_e3",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                    node.func.id if isinstance(node.func, ast.Name) else "")
                self.assertNotIn(name, forbidden_calls)
            if isinstance(node, ast.Constant) and type(node.value) is str:
                self.assertNotIn(node.value, ("E1_PASS", "RESEARCH_PASS"))
            if isinstance(node, (ast.For, ast.While, ast.comprehension)):
                calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
                self.assertFalse(any(isinstance(n.func, ast.Name)
                                     and n.func.id == "execute_scheduled_entry" for n in calls))

    def test_public_api_and_evidence_dataclasses_do_not_expose_private_layout(self):
        tree = ast.parse(Path(execution.__file__).read_text(encoding="utf-8"))
        forbidden = {"mines", "mine_positions", "layout", "snapshot", "definition", "answer", "engine"}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                self.assertNotIn(node.name, ("materialize_case", "get_case_definition", "get_mines"))
                for returned in (child for child in ast.walk(node) if isinstance(child, ast.Return)):
                    if isinstance(returned.value, ast.Name):
                        self.assertNotIn(returned.value.id, forbidden)
                    if isinstance(returned.value, ast.Attribute):
                        self.assertNotIn(returned.value.attr, forbidden)
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                cls = getattr(execution, node.name)
                if is_dataclass(cls):
                    self.assertFalse({f.name for f in fields(cls)} & forbidden)
        self.assertFalse({f.name for f in fields(e1.E1Plan)} & forbidden)
        self.assertFalse({f.name for f in fields(e1.SealedCaseRegistration)} & forbidden)

    def test_existing_table_loader_is_used_without_coefficient_regeneration(self):
        tree = ast.parse(Path(execution.__file__).read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertTrue(any(isinstance(node.func, ast.Attribute)
                            and node.func.attr == "load_timing_table" for node in calls))
        self.assertFalse(any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow)
                             for node in ast.walk(tree)))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertFalse(names & {"log2", "log", "fit", "polyfit", "calibrate", "coefficients"})


if __name__ == "__main__":
    unittest.main()
