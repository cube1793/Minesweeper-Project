"""runtime 모델과 정책에 연결된 root 기본 계산 재사용의 계약 시험.

다루는 것: 재사용을 켜는 곳이 evaluate_model 하나라는 것, 식별자, root 회계가 모델 사용량으로 이어지는 것,
세션 오류가 모델·정책의 오류로 올라가고 직접 F로 대체되지 않는 것, 그리고 시간 계약 —
작업량으로는 두 방식 모두 root를 끝내는 공개 상태에서도 시간 한도 아래에서는 종료와 최종 출처가 갈릴 수 있다.
시간 계약은 두 경우로 나눠 본다. TimeContractTests는 기존 root가 시간으로 멈추는 경우,
BothRootsCompleteTimeTests는 두 root가 모두 끝났는데 root에서 쓴 시간 차이가 부모 모델의 남은 시간에
반영되어 후속 F 시간 예약에서 갈리는 경우다.
"""
from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import replace
import inspect
import time
import unittest
from unittest import mock

import stage4_belief as belief
import stage4_candidates as candidates
import stage4_exact_pilot
import stage4_objective_pilot
import stage4_policy
import stage4_posterior
import stage4_runtime_model as m
import stage4_runtime_policy
from stage4_posterior import public_digest
from stage4_runtime_policy import RuntimeLimits, RuntimePolicy, RuntimeRequest
from tests.test_stage4_risk_value import CHORD_STATE, FLAG_STATE, request

CANDIDATE_ID = "RUNTIME_COMMON_POSTERIOR_THEN_PUBLIC_F_V5_ROOT_BASE_REUSE"
PREVIOUS_ID = "RUNTIME_COMMON_POSTERIOR_THEN_PUBLIC_F_V4_RV1_OWN_SURVIVAL"


@contextmanager
def existing_root_path():
    """모델이 root를 기존 경로(reuse_base=False)로 부르게 한다. 비교용이며 다른 것은 바꾸지 않는다."""
    real = m.analyze_candidates

    def old(query, *, cancelled=None, reuse_base=True):
        return real(query, cancelled=cancelled, reuse_base=False)

    with mock.patch.object(m, "analyze_candidates", old):
        yield


def policy_request(state=FLAG_STATE, mode="M", limits=None):
    grid, mines, counted = state
    return RuntimeRequest(grid, mines, counted, mode, True, None, limits=limits or RuntimeLimits())


class WiringTests(unittest.TestCase):
    def test_only_the_runtime_model_turns_reuse_on(self):
        seen = []
        real = m.analyze_candidates

        def spy(query, **kwargs):
            seen.append(kwargs)
            return real(query, **kwargs)

        with mock.patch.object(m, "analyze_candidates", spy):
            result = m.evaluate_model(request(FLAG_STATE))
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(len(seen), 1)
        self.assertIs(seen[0]["reuse_base"], True)
        self.assertTrue(callable(seen[0]["cancelled"]))
        for module in (stage4_policy, stage4_objective_pilot, stage4_exact_pilot, stage4_runtime_policy):
            source = inspect.getsource(module)
            self.assertNotIn("reuse_base", source, module.__name__)
            self.assertNotIn("PublicCountSession", source, module.__name__)

    def test_identifiers(self):
        self.assertEqual(m.MODEL_ID, CANDIDATE_ID)
        query = request(FLAG_STATE)
        self.assertEqual(query.identity, public_digest((CANDIDATE_ID, query)))
        self.assertNotEqual(query.identity, public_digest((PREVIOUS_ID, query)))
        self.assertEqual(m.F_ID, "PUBLIC_F_INDEXED_COVER_UNIT10_V1:prepaid_indexed_immutable_relations_v1:FA1K_U71")
        self.assertEqual(m.K100K_F_ID,
                         "PUBLIC_F_INDEXED_K100K_COVER_UNIT10_V1:prepaid_indexed_immutable_relations_v1:FA1K_U71")
        self.assertEqual(stage4_runtime_policy.POLICY_ID, "UNCONNECTED_RUNTIME_SMR_V1")
        result = m.evaluate_model(query)
        self.assertEqual((result.model_id, result.request_id), (CANDIDATE_ID, query.identity))

    def test_root_accounting_reaches_the_model_usage(self):
        for state in (FLAG_STATE, CHORD_STATE):
            grid, mines, _ = state
            result = m.evaluate_model(request(state))
            used = result.root.diagnostics
            self.assertEqual((result.usage.unit4_calls, result.usage.unit4_work), (used.backend_calls, used.backend_work))
            settled = {s.resource: s for s in result.settlements if s.resource in ("unit4_calls", "unit4_work")}
            self.assertEqual((settled["unit4_calls"].actual, settled["unit4_work"].actual),
                             (used.backend_calls, used.backend_work))
            old = candidates.analyze_candidates(candidates.CandidateRequest(grid, mines))
            self.assertEqual(old.status, "COMPLETE")
            self.assertGreater(old.diagnostics.backend_calls, 1)
            base_work = old.diagnostics.backend_trace[0].work
            self.assertEqual(used.backend_calls, old.diagnostics.backend_calls)
            self.assertEqual(used.backend_work,
                             old.diagnostics.backend_work - (old.diagnostics.backend_calls - 1) * base_work)
            self.assertEqual((result.root.request_id, result.root.base, result.root.events, result.root.candidates),
                             (old.request_id, old.base, old.events, old.candidates))

    def test_rows_scores_and_selection_equal_the_existing_root_path(self):
        # 작은 상태라 시간 한도가 개입하지 않는 조건이다. 시간이 개입하는 경우는 TimeContractTests가 다룬다.
        for state in (FLAG_STATE, CHORD_STATE):
            for mode in ("S", "M", "R"):
                with self.subTest(mode=mode):
                    new = m.evaluate_model(request(state, mode))
                    with existing_root_path():
                        old = m.evaluate_model(request(state, mode))
                    for name in ("status", "reason", "information", "target_status", "selected_candidate_id",
                                 "sequence", "rows", "scores", "shortlist", "request_id", "model_id"):
                        self.assertEqual(getattr(new, name), getattr(old, name), name)
                    self.assertEqual(new.posterior.samples, old.posterior.samples)
                    self.assertEqual(len(new.calls), len(old.calls))
                    self.assertEqual([c.request.identity for c in new.calls], [c.request.identity for c in old.calls])
                    self.assertEqual(replace(new.usage, unit4_work=0), replace(old.usage, unit4_work=0))
                    self.assertLess(new.usage.unit4_work, old.usage.unit4_work)
                    self.assertEqual(new.root.candidates, old.root.candidates)


class Corrupting(belief.PublicCountSession):
    """기본 계산 뒤 보관 값을 바꿔 봉인 불일치를 만든다."""

    def count_events(self, query, *, cancelled=None):
        state = self._state
        self._state = replace(state, base=replace(state.base, total_worlds=state.base.total_worlds + 1))
        return super().count_events(query, cancelled=cancelled)


class Closing(belief.PublicCountSession):
    def count_events(self, query, *, cancelled=None):
        self.close()
        return super().count_events(query, cancelled=cancelled)


class Raising(belief.PublicCountSession):
    def count_events(self, query, *, cancelled=None):
        raise RuntimeError("deliberate session fault")


class ErrorPropagationTests(unittest.TestCase):
    """세션의 정합성 오류는 오류로 끝난다. 자원 한도 종료나 직접 F로 바뀌지 않는다."""

    def test_session_refusal_is_a_model_error_and_never_replaced_by_f(self):
        for cls, reason in ((Corrupting, "ROOT_SESSION_STATE_CORRUPT"), (Closing, "ROOT_SESSION_CLOSED")):
            with mock.patch.object(candidates, "PublicCountSession", cls):
                result = m.evaluate_model(request(FLAG_STATE))
                policy = RuntimePolicy()
                with mock.patch("stage4_runtime_policy.choose_followup",
                                side_effect=AssertionError("F must not replace a root error")) as followup:
                    proposal = policy.choose(policy_request())
                policy.close()
            self.assertEqual((result.status, result.reason), ("ERROR", reason))
            self.assertEqual(result.root.status, "ERROR")
            self.assertGreaterEqual(result.root.diagnostics.backend_calls, 2)
            self.assertEqual((result.sequence, result.scores, result.selected_candidate_id), ((), (), None))
            self.assertEqual(result.rows, ())
            self.assertTrue(result.usage.accounting_complete)
            self.assertEqual(followup.call_count, 0)
            self.assertEqual((proposal.status, proposal.reason), ("ERROR", "MODEL_BLOCKED:" + reason))
            self.assertEqual((tuple(proposal.sequence), proposal.decision_source), ((), None))
            self.assertEqual(proposal.model_status, "ERROR")
            self.assertIsNone(proposal.proposal_id)
            self.assertTrue(proposal.usage.accounting_complete)

    def test_session_exception_is_an_error_without_f(self):
        with mock.patch.object(candidates, "PublicCountSession", Raising):
            result = m.evaluate_model(request(FLAG_STATE))
            policy = RuntimePolicy()
            with mock.patch("stage4_runtime_policy.choose_followup",
                            side_effect=AssertionError("F must not replace a root error")) as followup:
                proposal = policy.choose(policy_request())
            policy.close()
        self.assertEqual((result.status, result.reason), ("ERROR", "MODEL_ERROR"))
        self.assertEqual(result.error, "ValueError: UNKNOWN_MODEL_BACKEND_SPEND")
        self.assertFalse(result.usage.accounting_complete)
        self.assertEqual((result.root.status, result.root.reason), ("ERROR", "BACKEND_ERROR"))
        self.assertEqual(followup.call_count, 0)
        self.assertEqual((proposal.status, proposal.reason), ("ERROR", "RUNTIME_POLICY_ERROR"))
        self.assertIn("MODEL_BINDING_OR_UNKNOWN_ACCOUNTING", proposal.error)
        self.assertEqual((tuple(proposal.sequence), proposal.decision_source), ((), None))

    def test_resource_limits_of_the_reuse_path_still_use_the_direct_f(self):
        grid, mines, _ = FLAG_STATE
        base_work = candidates.analyze_candidates(candidates.CandidateRequest(grid, mines)).diagnostics.backend_trace[0].work
        for cap, root_status in ((1, "INSUFFICIENT"), (base_work + 1, "PARTIAL")):
            limits = RuntimeLimits(model=replace(m.ModelLimits(), root=candidates.CandidateLimits(
                max_total_backend_work=cap)))
            policy = RuntimePolicy()
            proposal = policy.choose(policy_request(limits=limits))
            policy.close()
            self.assertEqual(proposal.model.root.status, root_status)
            self.assertLessEqual(proposal.model.root.diagnostics.backend_work, cap)
            self.assertEqual((proposal.model_status, proposal.model.reason), ("RESOURCE_LIMIT", "ROOT_WORK_LIMIT"))
            self.assertEqual(proposal.decision_source, "F")
            self.assertEqual(proposal.usage.unit4_work, proposal.model.root.diagnostics.backend_work)


def stepping(step):
    now = [0.0]

    def clock():
        now[0] += step
        return now[0]
    return clock


class TimeContractTests(unittest.TestCase):
    """같은 공개 입력, 같은 작업량 조건이어도 남은 시간이 다르면 종료와 행동이 달라질 수 있다.

    root의 시계(stage4_candidates.perf_counter)만 제어한다. 조회마다 일정량 진행하는 시계에서
    기존 경로는 기본 계산을 묶음마다 반복해 시계를 더 많이 읽는다. 시간 한도를 두 경로의 소요 사이에 두면
    기존 경로는 시간으로 멈추고 재사용 경로는 끝난다. 실보드 시간 측정이 아니다.
    """

    @classmethod
    def setUpClass(cls):
        grid, mines, _ = FLAG_STATE
        cls.query = candidates.CandidateRequest(grid, mines)
        counts = {}
        for flag in (False, True):
            reads = [0]

            def clock():
                reads[0] += 1
                return 0.0

            # 모델은 root에 취소 콜백을 넘긴다. 콜백이 있으면 root는 검사마다 시계를 두 번 읽으므로
            # 조회 수를 같은 조건(콜백 있음)으로 센다.
            with mock.patch.object(candidates, "perf_counter", clock):
                result = candidates.analyze_candidates(cls.query, cancelled=lambda: False, reuse_base=flag)
            counts[flag] = (reads[0], result)
        cls.old_reads, cls.old_root = counts[False]
        cls.new_reads, cls.new_root = counts[True]
        cls.step = 5.0 / cls.old_reads
        cls.limit = cls.step * (cls.old_reads + cls.new_reads) / 2

    def test_both_paths_finish_the_root_without_time_pressure(self):
        self.assertEqual((self.old_root.status, self.new_root.status), ("COMPLETE", "COMPLETE"))
        self.assertEqual(self.old_root.candidates, self.new_root.candidates)
        self.assertGreaterEqual(self.old_reads - self.new_reads, 2)  # 재사용 경로가 시계를 덜 읽는다
        self.assertLess(self.limit, 10.0)

    def test_root_under_a_time_limit_between_the_two_paths(self):
        limited = replace(self.query, limits=candidates.CandidateLimits(max_seconds=self.limit))
        with mock.patch.object(candidates, "perf_counter", stepping(self.step)):
            old = candidates.analyze_candidates(limited, cancelled=lambda: False, reuse_base=False)
        with mock.patch.object(candidates, "perf_counter", stepping(self.step)):
            new = candidates.analyze_candidates(limited, cancelled=lambda: False, reuse_base=True)
        self.assertEqual((old.status, old.reason), ("PARTIAL", "TIME_LIMIT"))
        self.assertEqual(new.status, "COMPLETE")
        self.assertEqual(new.candidates, self.new_root.candidates)
        self.assertLess(new.diagnostics.elapsed_seconds, old.diagnostics.elapsed_seconds)

    def test_model_and_policy_outcomes_diverge_only_through_time(self):
        limits = replace(m.ModelLimits(), root=candidates.CandidateLimits(max_seconds=self.limit))
        # 시계를 제어하지 않으면 두 경로가 같은 선택을 한다.
        free_new = m.evaluate_model(request(FLAG_STATE, limits=limits))
        with existing_root_path():
            free_old = m.evaluate_model(request(FLAG_STATE, limits=limits))
        self.assertEqual((free_new.status, free_old.status), ("COMPLETE", "COMPLETE"))
        self.assertEqual((free_new.selected_candidate_id, free_new.scores), (free_old.selected_candidate_id, free_old.scores))
        # 같은 요청, 같은 시간 한도, 제어 시계: 종료가 갈린다.
        with mock.patch.object(candidates, "perf_counter", stepping(self.step)):
            timed_new = m.evaluate_model(request(FLAG_STATE, limits=limits))
        with existing_root_path(), mock.patch.object(candidates, "perf_counter", stepping(self.step)):
            timed_old = m.evaluate_model(request(FLAG_STATE, limits=limits))
        self.assertEqual(timed_new.status, "COMPLETE")
        self.assertEqual((timed_new.selected_candidate_id, timed_new.scores),
                         (free_new.selected_candidate_id, free_new.scores))
        self.assertEqual((timed_old.status, timed_old.reason), ("RESOURCE_LIMIT", "ROOT_TIME_LIMIT"))
        self.assertEqual((timed_old.sequence, timed_old.scores), ((), ()))
        # 정책의 최종 출처도 갈린다: 재사용 경로는 MODEL, 기존 경로는 직접 F.
        runtime = RuntimeLimits(model=limits)
        policy = RuntimePolicy()
        with mock.patch.object(candidates, "perf_counter", stepping(self.step)):
            new = policy.choose(policy_request(limits=runtime))
        policy.close()
        policy = RuntimePolicy()
        with existing_root_path(), mock.patch.object(candidates, "perf_counter", stepping(self.step)):
            old = policy.choose(policy_request(limits=runtime))
        policy.close()
        self.assertEqual((new.model_status, new.decision_source), ("COMPLETE", "MODEL"))
        self.assertEqual((old.model_status, old.decision_source, old.model.reason),
                         ("RESOURCE_LIMIT", "F", "ROOT_TIME_LIMIT"))
        self.assertTrue(new.sequence and old.sequence)


class ManualClock:
    """읽어도 흐르지 않는 단조 시계. advance()로만 진행한다."""

    def __init__(self, start=1000.0):
        self.start = self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        if seconds < 0:
            raise ValueError("a monotonic clock cannot go back")
        self.now += seconds

    @property
    def elapsed(self):
        return self.now - self.start


# 정책·모델·root·계수기·표본 추출기가 읽는 시계 이름. 같은 시계 하나를 건다.
CLOCK_NAMES = ((stage4_runtime_policy, "perf_counter"), (m, "perf_counter"), (candidates, "perf_counter"),
               (belief, "monotonic"), (stage4_posterior, "perf_counter"))
TIME_DOUBLES = CLOCK_NAMES + ((belief, "_base"), (m, "choose_followup"), (m._Clock, "remaining"))
ORIGINALS = tuple(getattr(owner, name) for owner, name in TIME_DOUBLES)


@contextmanager
def staged_time(base_seconds, followup_seconds):
    """단계별로만 진행하는 시간. 계산과 판정은 모두 실제 코드가 한다.

    - 기본 계산(stage4_belief._base)을 실제로 한 번 실행할 때마다 base_seconds가 흐른다.
    - 모델 안의 F 미스(실제 choose_followup 실행)마다 followup_seconds가 흐른다.
    - 모델 예산이 계산한 남은 시간은 값을 바꾸지 않고 기록만 한다.
    문맥을 나오면 모든 대역이 복구된다. 들어올 때마다 새 시계로 시작한다.
    """
    clock = ManualClock()
    seen = {"base_runs": 0, "followup_runs": 0, "remaining": []}
    real_base, real_followup, real_remaining = belief._base, m.choose_followup, m._Clock.remaining

    def timed_base(*args, **kwargs):
        value = real_base(*args, **kwargs)
        seen["base_runs"] += 1
        clock.advance(base_seconds)
        return value

    def timed_followup(*args, **kwargs):
        value = real_followup(*args, **kwargs)
        seen["followup_runs"] += 1
        clock.advance(followup_seconds)
        return value

    def watched_remaining(self):
        value = real_remaining(self)
        if isinstance(self, m._Budget):  # 모델 예산만. F 자신의 시계는 기록하지 않는다.
            seen["remaining"].append(value)
        return value

    with ExitStack() as stack:
        for owner, name in CLOCK_NAMES:
            stack.enter_context(mock.patch.object(owner, name, clock))
        stack.enter_context(mock.patch.object(belief, "_base", timed_base))
        stack.enter_context(mock.patch.object(m, "choose_followup", timed_followup))
        stack.enter_context(mock.patch.object(m._Clock, "remaining", watched_remaining))
        yield clock, seen


class BothRootsCompleteTimeTests(unittest.TestCase):
    """두 방식의 root가 모두 COMPLETE인데도 root에서 쓴 시간 차이가 후속 처리를 가르는 경우.

    같은 공개 입력·모드·프로파일·표본 조건이고 한도는 모두 기본값이다. 두 군의 차이는 root 호출의 reuse_base뿐이다.
    시간은 staged_time이 단계별로만 진행한다. 기존 경로는 기본 계산을 root 호출마다 실제로 다시 실행하므로
    root가 쓴 시간이 N*T, 재사용 경로는 T다. 그 차이가 부모 모델의 남은 시간에 그대로 남고,
    뒤의 F 미스들이 같은 양(f)을 쓴 끝에 기존 경로만 F 시간 예약(남은 시간 >= F의 시간 한도)을 채우지 못한다.

    "그런 시간 차이가 주어졌을 때 기존 계약대로 처리되는가"를 본다. 재사용이 실제로 더 빠르다는 것이나
    실제 게임에서 이 차이가 얼마나 자주 생기는지를 보이는 시험이 아니다.
    """

    @classmethod
    def setUpClass(cls):
        limits = m.ModelLimits()
        cls.model_seconds = limits.max_seconds                                           # 모델 시간 한도(기본 30초)
        cls.reserve = m.fixed_followup_limits(limits.kernel_kind).max_seconds            # F 시간 예약(기본 5초)
        cls.free = m.evaluate_model(request(FLAG_STATE))                                 # 시계를 건드리지 않은 실행
        cls.calls = cls.free.root.diagnostics.backend_calls                              # N: root 호출 수
        cls.misses = cls.free.usage.f_misses                                             # K: 모델의 F 미스 수
        cls.base_seconds = min(1.0, 8.0 / cls.calls)                                     # T: 기본 계산 1회
        cls.gap = (cls.calls - 1) * cls.base_seconds                                     # D: root 시간 차이
        # 재사용 경로가 마지막 F 미스의 예약 검사에 도착하는 시각을 경계(모델 한도 - 예약)보다 D/2 앞에 둔다.
        cls.followup_seconds = ((cls.model_seconds - cls.reserve - cls.gap / 2 - cls.base_seconds)
                                / max(cls.misses - 1, 1))                               # f: F 미스 1회
        cls.model, cls.policy = {}, {}
        for name, root_path in (("existing", existing_root_path), ("reuse", nullcontext)):
            with root_path(), staged_time(cls.base_seconds, cls.followup_seconds) as (clock, seen):
                result = m.evaluate_model(request(FLAG_STATE))
                cls.model[name] = (result, seen, clock.elapsed)
            with root_path(), staged_time(cls.base_seconds, cls.followup_seconds) as (clock, seen):
                policy = RuntimePolicy()
                try:
                    proposal = policy.choose(policy_request())
                finally:
                    policy.close()
                cls.policy[name] = (proposal, seen, clock.elapsed)

    def test_both_roots_complete_with_equal_exact_evidence(self):
        self.assertGreaterEqual(self.calls, 2)
        reference = self.free.root
        for name, base_runs in (("existing", self.calls), ("reuse", 1)):
            for result, seen in ((self.model[name][0], self.model[name][1]),
                                 (self.policy[name][0].model, self.policy[name][1])):
                with self.subTest(arm=name):
                    root = result.root
                    self.assertEqual((root.status, root.reason), ("COMPLETE", reference.reason))
                    self.assertTrue(root.catalogue_complete and root.evidence_complete)
                    self.assertEqual((root.request_id, root.base, root.events, root.candidates),
                                     (reference.request_id, reference.base, reference.events, reference.candidates))
                    self.assertEqual(root.diagnostics.backend_calls, self.calls)
                    self.assertEqual(seen["base_runs"], base_runs)  # 기본 계산을 실제로 실행한 횟수
                    self.assertFalse(result.reason.startswith("ROOT_"))

    def test_root_time_reaches_the_parent_model(self):
        spent = {"existing": self.calls * self.base_seconds, "reuse": self.base_seconds}
        self.assertLess(self.base_seconds, 2.0)       # 계수기 호출 한 번의 시간 한도 안
        self.assertLess(spent["existing"], 10.0)      # root 시간 한도 안
        self.assertGreater(self.gap, 0)
        for name in ("existing", "reuse"):
            result, seen, _ = self.model[name]
            self.assertAlmostEqual(result.root.diagnostics.elapsed_seconds, spent[name], places=6)
            self.assertAlmostEqual(seen["remaining"][0], self.model_seconds, places=6)                # root 시작 전
            self.assertAlmostEqual(seen["remaining"][1], self.model_seconds - spent[name], places=6)  # root 직후
        self.assertAlmostEqual(self.model["reuse"][1]["remaining"][1] - self.model["existing"][1]["remaining"][1],
                               self.gap, places=6)

    def test_followup_time_reservation_splits_the_model(self):
        self.assertGreaterEqual(self.misses, 2)
        self.assertGreater(self.followup_seconds, 0)
        self.assertLess(self.followup_seconds, self.reserve)  # F 자신의 시간 한도 안
        new, new_seen, new_elapsed = self.model["reuse"]
        old, old_seen, old_elapsed = self.model["existing"]
        # 재사용 경로: 모든 F 미스가 시간 예약을 통과하고 모델이 끝난다.
        self.assertEqual((new.status, new.reason), ("COMPLETE", "COMPLETE_COMMON_BANK_THEN_F"))
        self.assertEqual((new.selected_candidate_id, new.sequence, new.scores, new.rows),
                         (self.free.selected_candidate_id, self.free.sequence, self.free.scores, self.free.rows))
        new_checks = new_seen["remaining"][2:]
        self.assertEqual((new_seen["followup_runs"], len(new_checks), new.usage.f_misses),
                         (self.misses, self.misses, self.misses))
        self.assertGreaterEqual(min(new_checks), self.reserve)
        self.assertAlmostEqual(new_checks[-1], self.reserve + self.gap / 2, places=6)
        self.assertLess(new_elapsed, self.model_seconds)
        # 기존 경로: root는 끝났지만 어느 F 미스의 예약 검사에서 남은 시간이 모자라 모델이 멈춘다.
        self.assertEqual((old.status, old.reason), ("RESOURCE_LIMIT", "F_TIME_RESERVATION"))
        self.assertEqual(old.root.status, "COMPLETE")
        self.assertEqual((old.sequence, old.scores, old.selected_candidate_id), ((), (), None))
        self.assertTrue(old.usage.accounting_complete)
        old_checks = old_seen["remaining"][2:]
        self.assertLess(old_checks[-1], self.reserve)
        self.assertGreater(old_checks[-1], 0)  # 모델 자신의 기한(TIME_LIMIT)은 아직 남아 있었다
        self.assertTrue(all(value >= self.reserve for value in old_checks[:-1]))
        self.assertEqual((old_seen["followup_runs"], old.usage.f_misses), (len(old_checks) - 1, len(old_checks) - 1))
        self.assertLess(old_seen["followup_runs"], self.misses)
        self.assertLess(old_elapsed, self.model_seconds)
        # 같은 순번의 예약 검사에서 재사용 경로에는 root 시간 차이만큼 더 남아 있었다.
        index = len(old_checks) - 1
        self.assertAlmostEqual(new_checks[index] - old_checks[index], self.gap, places=6)
        self.assertGreaterEqual(new_checks[index], self.reserve)

    def test_policy_final_handling_follows_the_model(self):
        new, _, _ = self.policy["reuse"]
        old, _, old_elapsed = self.policy["existing"]
        for name, proposal in (("reuse", new), ("existing", old)):
            model = self.model[name][0]
            self.assertEqual((proposal.model.request_id, proposal.model.status, proposal.model.reason),
                             (model.request_id, model.status, model.reason))
            self.assertIsNone(proposal.error)
            self.assertTrue(proposal.usage.accounting_complete)
            self.assertIsNotNone(proposal.proposal_id)
        expected = "NO_INFORMATION" if self.free.information == "COMPLETE_ALL_ZERO" else "MODEL_SELECTED"
        self.assertEqual((new.status, new.decision_source, new.model_status), (expected, "MODEL", "COMPLETE"))
        self.assertEqual(tuple(new.sequence), tuple(self.free.sequence))
        self.assertIsNone(new.followup)
        # 기존 경로: 모델의 자원 한도 종료이므로 정책은 직접 F로 처리한다.
        self.assertEqual((old.status, old.decision_source, old.model_status),
                         ("HEURISTIC_FALLBACK", "F", "RESOURCE_LIMIT"))
        self.assertEqual((old.model.reason, old.model.root.status), ("F_TIME_RESERVATION", "COMPLETE"))
        self.assertTrue(old.reason.startswith("MODEL_RESOURCE_LIMIT:"))
        self.assertEqual(old.followup.status, "READY")
        self.assertEqual(tuple(old.sequence), tuple(old.followup.sequence))
        self.assertTrue(old.sequence)
        self.assertLessEqual(old_elapsed, RuntimeLimits().max_seconds - self.reserve)  # 정책 기한 안에서 직접 F 실행

    def test_time_doubles_are_restored(self):
        self.assertEqual(tuple(getattr(owner, name) for owner, name in TIME_DOUBLES), ORIGINALS)
        self.assertIs(m.perf_counter, time.perf_counter)
        self.assertIs(belief.monotonic, time.monotonic)
        again = m.evaluate_model(request(FLAG_STATE))
        self.assertEqual((again.status, again.selected_candidate_id, again.scores, again.usage.f_misses,
                          again.root.diagnostics.backend_calls),
                         (self.free.status, self.free.selected_candidate_id, self.free.scores, self.misses, self.calls))

    @classmethod
    def evidence(cls):
        """관측값 요약(기록용). 판정에는 쓰지 않는다."""
        def arm(name):
            model, seen, elapsed = cls.model[name]
            proposal, policy_seen, policy_elapsed = cls.policy[name]
            checks, policy_checks = seen["remaining"][2:], policy_seen["remaining"][2:]
            return {
                "base_runs": seen["base_runs"], "followup_runs": seen["followup_runs"],
                "root": {"status": model.root.status, "reason": model.root.reason,
                         "backend_calls": model.root.diagnostics.backend_calls,
                         "backend_work": model.root.diagnostics.backend_work,
                         "elapsed_seconds": model.root.diagnostics.elapsed_seconds,
                         "total_worlds": model.root.base.total_worlds, "candidates": len(model.root.candidates),
                         "equals_free_run": (model.root.base, model.root.events, model.root.candidates)
                         == (cls.free.root.base, cls.free.root.events, cls.free.root.candidates)},
                "remaining_before_root": seen["remaining"][0], "remaining_after_root": seen["remaining"][1],
                "reservation_checks": len(checks), "reservation_first": checks[0], "reservation_min": min(checks),
                "reservation_last": checks[-1],
                "model": {"status": model.status, "reason": model.reason, "selected": model.selected_candidate_id,
                          "sequence": repr(model.sequence), "information": model.information,
                          "f_lookups": model.usage.f_lookups, "f_misses": model.usage.f_misses,
                          "f_hits": model.usage.f_hits, "rows": len(model.rows),
                          "rows_with_value": sum(row.value_x is not None for row in model.rows),
                          "accounting_complete": model.usage.accounting_complete,
                          "elapsed_seconds": model.elapsed_seconds, "clock_elapsed": elapsed},
                "policy": {"status": proposal.status, "reason": proposal.reason,
                           "decision_source": proposal.decision_source, "model_status": proposal.model_status,
                           "model_reason": proposal.model.reason, "model_root_status": proposal.model.root.status,
                           "sequence": repr(tuple(proposal.sequence)),
                           "followup_status": None if proposal.followup is None else proposal.followup.status,
                           "proposal_id_present": proposal.proposal_id is not None, "error": proposal.error,
                           "base_runs": policy_seen["base_runs"], "followup_runs": policy_seen["followup_runs"],
                           "reservation_last": policy_checks[-1], "clock_elapsed": policy_elapsed},
            }
        return {"state": "FLAG_STATE", "mode": "M", "limits": "ModelLimits()/RuntimeLimits() 기본값",
                "model_seconds": cls.model_seconds, "reserve_seconds": cls.reserve,
                "root_calls_N": cls.calls, "f_misses_K": cls.misses, "base_seconds_T": cls.base_seconds,
                "root_gap_D": cls.gap, "followup_seconds_f": cls.followup_seconds,
                "free_run": {"status": cls.free.status, "reason": cls.free.reason,
                             "selected": cls.free.selected_candidate_id, "information": cls.free.information},
                "existing": arm("existing"), "reuse": arm("reuse")}


if __name__ == "__main__":
    unittest.main()
