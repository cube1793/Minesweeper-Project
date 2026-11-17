"""analyze_candidates(reuse_base=True)의 계약 시험.

독립 정답은 tests.stage4_candidates_oracle.analyze_grid에서 온다(제품 모듈을 쓰지 않는 전수 계산).
기존 경로(reuse_base=False)와의 비교는 같은 코드 계열의 재현이며 독립 정답 대조와 구분해서 읽는다.
기존 tests.test_stage4_candidates는 바꾸지 않았고 기본 경로를 그대로 시험한다.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import fields, replace
import unittest
from unittest.mock import patch

import stage4_candidates as candidates
from stage4_belief import BaseResult, BeliefRequest, PublicCountSession as RealSession, count_public as real_count_public
from tests.stage4_candidates_oracle import FIXTURES, analyze_grid
from tests.test_stage4_candidates import profile

CENTER = FIXTURES[0][1]


def request(**limits):
    return candidates.CandidateRequest(CENTER, 1, candidates.CandidateLimits(**limits))


def reuse(query, **kwargs):
    return candidates.analyze_candidates(query, reuse_base=True, **kwargs)


def legacy(query, **kwargs):
    return candidates.analyze_candidates(query, **kwargs)


class SessionProxy:
    """실제 세션을 감싸 응답만 바꾸는 대역. 요청과 닫힘 횟수를 기록한다."""
    created = []

    def __init__(self):
        self.real = RealSession()
        self.requests = []
        self.closed = 0
        type(self).created.append(self)

    def alter(self, query, reply):
        return reply

    def count_base(self, query, *, cancelled=None):
        self.requests.append(query)
        return self.alter(query, self.real.count_base(query, cancelled=cancelled))

    def count_events(self, query, *, cancelled=None):
        self.requests.append(query)
        return self.alter(query, self.real.count_events(query, cancelled=cancelled))

    def close(self):
        self.closed += 1
        self.real.close()


def proxy(alter=None, **methods):
    namespace = dict(methods, created=[])
    if alter is not None:
        namespace["alter"] = lambda self, query, reply: alter(query, reply)
    return type("Proxy", (SessionProxy,), namespace)


@contextmanager
def sessions(cls):
    with patch.object(candidates, "PublicCountSession", cls):
        yield cls


def closed_once(test, cls):
    test.assertEqual(len(cls.created), 1)
    test.assertEqual(cls.created[0].closed, 1)
    test.assertFalse(cls.created[0].real.prepared)


class OracleTests(unittest.TestCase):
    """독립 정답 대조."""

    def test_oracle_24_public_observations_with_reuse(self):
        self.assertEqual(len(FIXTURES), 24)
        for name, grid, mines in FIXTURES:
            with self.subTest(name=name):
                oracle = analyze_grid(grid, mines)
                result = reuse(candidates.CandidateRequest(grid, mines))
                self.assertEqual(result.base.total_worlds, oracle["D"])
                if not oracle["D"]:
                    self.assertEqual(result.status, "INCONSISTENT_INPUT")
                    self.assertEqual(result.candidates, ())
                    continue
                self.assertEqual(result.status, "COMPLETE")
                self.assertTrue(result.catalogue_complete and result.evidence_complete)
                self.assertEqual({row.coordinate: row.mine_worlds for row in result.base.marginals}, oracle["M"])
                self.assertEqual(result.has_proven_safe_cell, oracle["has_proven_safe_cell"])
                self.assertEqual(tuple(map(profile, result.candidates)), oracle["candidates"])
                self.assertEqual(result.diagnostics.generated, oracle["generated"])
                self.assertEqual(result.diagnostics.excluded_empty_targets, oracle["empty_excluded"])
                self.assertEqual(result.diagnostics.excluded_edited_single_target, oracle["single_excluded"])
                for row in result.candidates:
                    self.assertTrue(all(z.event.worlds <= row.survival.worlds for z in row.zero_targets))
                    self.assertEqual(row.survival.safe_cells, row.targets)


class TwoPathTests(unittest.TestCase):
    """같은 코드 계열의 재현: 두 경로의 정확값은 같고 작업량만 반복분만큼 다르다."""

    COUNTS = ("generated", "excluded_empty_targets", "excluded_edited_single_target", "backend_calls",
              "distinct_queried_events", "queued_events", "event_references", "duplicate_event_references",
              "base_proofs", "exact_candidates", "exact_survivals", "exact_zero_targets", "work_accounting_complete",
              "last_checkpoint", "error")

    def test_exact_values_agree_and_work_differs_by_the_repeated_base(self):
        multi = 0
        for name, grid, mines in FIXTURES:
            with self.subTest(name=name):
                query = candidates.CandidateRequest(grid, mines)
                old, new = legacy(query), reuse(query)
                self.assertEqual((new.request_id, new.observation_id), (old.request_id, old.observation_id))
                self.assertEqual(new.request_id, query.identity)
                self.assertEqual((new.status, new.reason, new.stop_stage), (old.status, old.reason, old.stop_stage))
                self.assertEqual((new.family_id, new.schema_version, new.counter_version),
                                 (old.family_id, old.schema_version, old.counter_version))
                self.assertEqual(new.base, old.base)
                self.assertEqual(new.events, old.events)
                self.assertEqual(new.candidates, old.candidates)
                self.assertEqual((new.has_proven_safe_cell, new.catalogue_complete, new.event_collection_complete,
                                  new.evidence_complete),
                                 (old.has_proven_safe_cell, old.catalogue_complete, old.event_collection_complete,
                                  old.evidence_complete))
                for field in self.COUNTS:
                    self.assertEqual(getattr(new.diagnostics, field), getattr(old.diagnostics, field), field)
                old_trace, new_trace = old.diagnostics.backend_trace, new.diagnostics.backend_trace
                self.assertEqual(len(new_trace), len(old_trace))
                if not old_trace:
                    continue
                base_work = old_trace[0].work
                self.assertEqual(new_trace[0], old_trace[0])  # 기본 호출은 같은 요청, 같은 작업량이다
                for before, after in zip(old_trace[1:], new_trace[1:]):
                    self.assertEqual((after.stage, after.event_count, after.status, after.reason),
                                     (before.stage, before.event_count, before.status, before.reason))
                    self.assertEqual(after.work, before.work - base_work)
                self.assertEqual(new.diagnostics.backend_work,
                                 old.diagnostics.backend_work - (len(old_trace) - 1) * base_work)
                self.assertEqual(new.diagnostics.backend_work, sum(row.work for row in new_trace))
                multi += len(old_trace) > 1
        self.assertGreater(multi, 0)  # 사건 묶음 호출이 있는 고정 자료가 들어 있다

    def test_default_is_the_existing_path_and_reuse_never_calls_count_public(self):
        class Forbidden:
            def __init__(self):
                raise AssertionError("the default path must not create a session")

        with patch.object(candidates, "PublicCountSession", Forbidden):
            implicit = candidates.analyze_candidates(request())
            explicit = candidates.analyze_candidates(request(), reuse_base=False)
        self.assertEqual((implicit.status, explicit.status), ("COMPLETE", "COMPLETE"))
        self.assertEqual(implicit.candidates, explicit.candidates)
        self.assertEqual(implicit.diagnostics.backend_work, explicit.diagnostics.backend_work)
        with patch.object(candidates, "count_public", side_effect=AssertionError("reuse must not call count_public")):
            new = reuse(request())
        self.assertEqual(new.status, "COMPLETE")
        self.assertEqual(new.candidates, implicit.candidates)

    def test_reuse_base_must_be_a_real_bool(self):
        for value in (1, 0, None, "True"):
            with self.assertRaises(TypeError):
                candidates.analyze_candidates(request(), reuse_base=value)
        with self.assertRaises(TypeError):
            candidates.analyze_candidates(request(), True)  # 키워드 전용

    def test_dto_shapes_and_identifiers_are_unchanged(self):
        self.assertEqual([f.name for f in fields(candidates.CandidateLimits)],
                         ["max_cells", "max_generated", "max_candidates", "max_distinct_events",
                          "max_backend_calls", "max_total_backend_work", "max_seconds"])
        self.assertEqual([f.name for f in fields(candidates.CandidateRequest)],
                         ["observation", "num_mines", "limits", "prior_id"])
        self.assertEqual([f.name for f in fields(candidates.BackendCall)],
                         ["request_id", "stage", "event_count", "work_limit", "seconds_limit", "status", "reason", "work"])
        self.assertEqual(len(fields(candidates.CandidateResult)), 16)
        self.assertEqual(len(fields(candidates.CandidateDiagnostics)), 19)
        self.assertEqual((candidates.FAMILY_ID, candidates.SCHEMA_VERSION, candidates.COUNTER_VERSION),
                         ("progress_preparations_evidence_v1", "candidate_evidence_v1", "bounded_public_counts_v1"))
        result = reuse(request())
        self.assertNotIn("session", " ".join(result.to_dict()))
        self.assertEqual(set(result.to_dict()), {f.name for f in fields(candidates.CandidateResult)})


class LimitTests(unittest.TestCase):
    def test_zero_limits_base(self):
        for field, expected in (("max_cells", "UNSUPPORTED"), ("max_backend_calls", "INSUFFICIENT"),
                                ("max_total_backend_work", "INSUFFICIENT"), ("max_seconds", "INSUFFICIENT")):
            result = reuse(request(**{field: 0}))
            self.assertEqual(result.status, expected)
            self.assertEqual(result.diagnostics.backend_calls, 0)
            self.assertIsNone(result.base.total_worlds)
            self.assertFalse(result.catalogue_complete)

    def test_zero_catalogue_and_event_limits(self):
        for field in ("max_generated", "max_candidates", "max_distinct_events"):
            result = reuse(request(**{field: 0}))
            self.assertEqual(result.status, "PARTIAL")
            self.assertEqual(result.base.total_worlds, 8)
            self.assertFalse(result.evidence_complete)
            self.assertEqual(result.diagnostics.backend_calls, 1)
        complete = reuse(candidates.CandidateRequest(((-2, -2),), 0, candidates.CandidateLimits(max_distinct_events=0)))
        self.assertEqual(complete.status, "COMPLETE")
        limited = reuse(request(max_distinct_events=1))
        self.assertEqual(limited.status, "PARTIAL")
        self.assertFalse(limited.event_collection_complete)
        self.assertEqual(limited.diagnostics.queued_events, 1)
        self.assertIsNone(limited.candidates[8].survival.worlds)

    def test_total_work_and_call_caps(self):
        full = reuse(request())
        self.assertEqual(full.status, "COMPLETE")
        self.assertGreater(full.diagnostics.backend_calls, 1)
        for limits in (candidates.CandidateLimits(max_backend_calls=1),
                       candidates.CandidateLimits(max_total_backend_work=1),
                       candidates.CandidateLimits(max_total_backend_work=full.diagnostics.backend_work - 1),
                       candidates.CandidateLimits(max_backend_calls=full.diagnostics.backend_calls - 1)):
            result = reuse(candidates.CandidateRequest(CENTER, 1, limits))
            self.assertIn(result.status, ("PARTIAL", "INSUFFICIENT"))
            self.assertLessEqual(result.diagnostics.backend_calls, limits.max_backend_calls)
            self.assertLessEqual(result.diagnostics.backend_work, limits.max_total_backend_work)
            self.assertTrue(result.diagnostics.work_accounting_complete)
            spent = 0
            for row in result.diagnostics.backend_trace:
                self.assertLessEqual(row.work_limit, limits.max_total_backend_work - spent)
                self.assertLessEqual(row.work_limit, 200000)
                self.assertLessEqual(row.seconds_limit, 2)
                self.assertLessEqual(row.event_count, 16)
                self.assertLessEqual(row.work, row.work_limit)
                spent += row.work
            self.assertEqual(spent, result.diagnostics.backend_work)

    def test_more_events_complete_under_the_same_work_cap(self):
        full_old, full_new = legacy(request()), reuse(request())
        self.assertEqual((full_old.status, full_new.status), ("COMPLETE", "COMPLETE"))
        needed = full_new.diagnostics.backend_work
        self.assertLess(needed, full_old.diagnostics.backend_work)
        capped_new = reuse(request(max_total_backend_work=needed))
        capped_old = legacy(request(max_total_backend_work=needed))
        # 재사용 방식은 같은 한도에서 끝나고, 기존 방식은 작업량으로 멈춘다.
        self.assertEqual((capped_new.status, capped_new.diagnostics.backend_work), ("COMPLETE", needed))
        self.assertEqual(capped_old.status, "PARTIAL")
        self.assertIn(capped_old.reason, ("WORK_LIMIT", "BACKEND_WORK_LIMIT"))
        self.assertLessEqual(capped_old.diagnostics.backend_work, needed)
        # (가) 기존 방식이 끝낸 사건은 값이 같다.
        new_events = {row.safe_cells: row for row in capped_new.events}
        finished = [row for row in capped_old.events if row.worlds is not None]
        for row in finished:
            self.assertEqual(new_events[row.safe_cells], row)
        self.assertLess(len(finished), len(capped_new.events))
        # (나) 더 끝낸 사건은 한도 없이 끝낸 기준과 같다(독립 정답 대조는 OracleTests).
        self.assertEqual(capped_new.events, full_old.events)
        self.assertEqual(capped_new.candidates, full_old.candidates)
        short = reuse(request(max_total_backend_work=needed - 1))
        self.assertEqual(short.status, "PARTIAL")
        self.assertIn(short.reason, ("WORK_LIMIT", "BACKEND_WORK_LIMIT"))
        self.assertLessEqual(short.diagnostics.backend_work, needed - 1)
        self.assertEqual(short.diagnostics.backend_work, sum(row.work for row in short.diagnostics.backend_trace))


class ProtectionTests(unittest.TestCase):
    """대역 세션으로 보는 응답 검증. 기존 경로의 backend 시험과 같은 결함을 넣는다."""

    def test_reordering_and_event_deduplication(self):
        cls = proxy(lambda query, reply: replace(reply, events=tuple(reversed(reply.events))) if query.events else reply)
        with sessions(cls):
            result = reuse(request())
        self.assertEqual(result.status, "COMPLETE")
        seen = [event for query in cls.created[0].requests for event in query.events]
        self.assertEqual(len(set(seen)), len(seen))
        self.assertEqual(result.candidates[8].survival.worlds, 1)
        self.assertEqual([z.event.worlds for z in result.candidates[8].zero_targets], [0, 1, 0, 1, 1, 1, 1])
        closed_once(self, cls)

    def test_request_binding_mismatch(self):
        cls = proxy(lambda query, reply: replace(reply, request_id="0" * 64) if query.events else reply)
        with sessions(cls):
            result = reuse(request())
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.base.total_worlds, 8)
        self.assertEqual(result.diagnostics.backend_calls, 2)
        self.assertTrue(all(row.survival.worlds == 7 for row in result.candidates[:8]))
        closed_once(self, cls)

    def test_base_mismatch(self):
        def wrong(query, reply):
            if not query.events:
                return reply
            base = replace(reply.base, total_worlds=16,
                           marginals=tuple(replace(m, mine_worlds=m.mine_worlds * 2) for m in reply.base.marginals))
            return replace(reply, base=base)
        cls = proxy(wrong)
        with sessions(cls):
            result = reuse(request())
        self.assertEqual(result.status, "ERROR")
        self.assertEqual(result.base.total_worlds, 8)
        self.assertEqual(result.diagnostics.backend_calls, 2)
        closed_once(self, cls)

    def test_duplicate_missing_and_invalid_events(self):
        for defect in ("duplicate", "missing", "numeric"):
            def wrong(query, reply):
                if not query.events:
                    return reply
                rows = reply.events
                if defect == "duplicate":
                    rows = rows + (rows[0],)
                elif defect == "missing":
                    rows = rows[1:]
                else:
                    rows = (replace(rows[0], event_worlds=reply.base.total_worlds + 1),) + rows[1:]
                return replace(reply, events=rows)
            cls = proxy(wrong)
            with sessions(cls):
                result = reuse(request())
            self.assertEqual(result.status, "ERROR", defect)
            self.assertEqual(result.diagnostics.backend_calls, 2)
            self.assertEqual(result.base.total_worlds, 8)
            closed_once(self, cls)

    def test_malformed_response_and_exception(self):
        def raises(self, query, *, cancelled=None):
            raise RuntimeError("deliberate session fault")
        for cls in (proxy(count_base=lambda self, query, *, cancelled=None: None), proxy(count_base=raises)):
            with sessions(cls):
                result = reuse(request())
            self.assertEqual(result.status, "ERROR")
            self.assertEqual(result.diagnostics.backend_calls, 1)
            self.assertFalse(result.diagnostics.work_accounting_complete)
            closed_once(self, cls)
        later = proxy(count_events=raises)
        with sessions(later):
            result = reuse(request())
        self.assertEqual((result.status, result.reason), ("ERROR", "BACKEND_ERROR"))
        self.assertEqual(result.base.total_worlds, 8)
        self.assertFalse(result.diagnostics.work_accounting_complete)
        closed_once(self, later)

    def test_partial_event_batch(self):
        def partial(query, reply):
            if not query.events:
                return reply
            rows = (reply.events[0],) + tuple(replace(r, status="NOT_EVALUATED", reason="TEST_STOP",
                                                      event_worlds=None, probability=None) for r in reply.events[1:])
            return replace(reply, status="PARTIAL", reason="TEST_STOP", events=rows)
        cls = proxy(partial)
        with sessions(cls):
            result = reuse(request())
        self.assertEqual(result.status, "PARTIAL")
        self.assertTrue(result.catalogue_complete)
        self.assertTrue(result.event_collection_complete)
        self.assertEqual(result.candidates[0].survival.worlds, 7)
        self.assertTrue(any(e.reason == "TEST_STOP" and e.worlds is None for e in result.events))
        self.assertTrue(any(e.status == "EXACT" and not e.reason.startswith("BASE_") for e in result.events))
        closed_once(self, cls)

    def test_session_refusal_is_an_error_not_a_resource_stop(self):
        def closed_first(self, query, *, cancelled=None):
            self.real.close()
            return SessionProxy.count_events(self, query, cancelled=cancelled)

        def corrupted(self, query, *, cancelled=None):
            state = self.real._state
            self.real._state = replace(state, base=replace(state.base, total_worlds=state.base.total_worlds + 1))
            return SessionProxy.count_events(self, query, cancelled=cancelled)

        def other_state(self, query, *, cancelled=None):
            flagged = ((-3,) + tuple(query.observation[0][1:]),) + tuple(query.observation[1:])
            moved = BeliefRequest(flagged, query.num_mines, query.events, query.limits, query.prior_id)
            return SessionProxy.count_events(self, moved, cancelled=cancelled)

        for method, reason in ((closed_first, "SESSION_CLOSED"), (corrupted, "SESSION_STATE_CORRUPT")):
            cls = proxy(count_events=method)
            with sessions(cls):
                result = reuse(request())
            self.assertEqual((result.status, result.reason), ("ERROR", reason))
            self.assertEqual(result.base.total_worlds, 8)
            self.assertEqual(result.diagnostics.backend_calls, 2)
            self.assertTrue(result.diagnostics.work_accounting_complete)  # 작업량 0은 알려진 값이다
            self.assertEqual((result.diagnostics.backend_trace[1].status, result.diagnostics.backend_trace[1].work),
                             ("ERROR", 0))
            self.assertFalse(result.evidence_complete)
            self.assertTrue(all(row.survival.worlds == 7 for row in result.candidates[:8]))
            closed_once(self, cls)
        # 다른 공개 상태로 바뀐 요청의 응답은 세션이 거부하고, 그 응답의 식별값은 root의 요청과도 다르다.
        cls = proxy(count_events=other_state)
        with sessions(cls):
            result = reuse(request())
        self.assertEqual((result.status, result.reason), ("ERROR", "BACKEND_ERROR"))
        self.assertIn("binding mismatch", result.diagnostics.error)
        closed_once(self, cls)

    def test_interrupted_session_stage_is_a_partial_stop(self):
        def cancelled_inside(self, query, *, cancelled=None):
            return SessionProxy.count_events(self, query, cancelled=lambda: True)
        cls = proxy(count_events=cancelled_inside)
        with sessions(cls):
            result = reuse(request())
        self.assertEqual((result.status, result.reason), ("PARTIAL", "CANCELLED"))
        self.assertEqual(result.base.total_worlds, 8)
        self.assertEqual(result.diagnostics.backend_calls, 2)
        self.assertTrue(result.diagnostics.work_accounting_complete)
        closed_once(self, cls)


class StopTests(unittest.TestCase):
    def test_controlled_clock_stop_stages(self):
        original = candidates._Budget.check
        for target in ("request", "base", "base.after", "catalogue", "events.collect",
                       "batch.0", "batch.0.after", "publish.before", "publish.after"):
            clock = [0.0]

            def check(budget, stage=None):
                if stage == target:
                    clock[0] = 20.0
                return original(budget, stage)
            cls = proxy()
            with sessions(cls), patch.object(candidates, "perf_counter", lambda: clock[0]), \
                    patch.object(candidates._Budget, "check", check):
                result = reuse(request())
            self.assertEqual(result.reason, "TIME_LIMIT", target)
            self.assertEqual(result.status, "INSUFFICIENT" if target in ("request", "base") else "PARTIAL", target)
            closed_once(self, cls)

    def test_cancellation_at_boundaries(self):
        original = candidates._Budget.check
        for target in ("request", "base.after", "catalogue", "events.collect", "batch.0.after", "publish.after"):
            current = [None]

            def check(budget, stage=None):
                if stage is not None:
                    current[0] = stage
                return original(budget, stage)
            cls = proxy()
            with sessions(cls), patch.object(candidates._Budget, "check", check):
                result = reuse(request(), cancelled=lambda: current[0] == target)
            self.assertEqual(result.status, "CANCELLED" if target == "request" else "PARTIAL", target)
            self.assertEqual(result.reason, "CANCELLED")
            closed_once(self, cls)

    def test_callback_failure_inside_backend(self):
        callbacks = [0]

        def bad_callback():
            callbacks[0] += 1
            return None if callbacks[0] == 20 else False
        result = reuse(request(), cancelled=bad_callback)
        self.assertEqual((result.status, result.reason), ("ERROR", "CANCEL_CALLBACK_ERROR"))
        self.assertEqual(result.diagnostics.backend_calls, 1)
        self.assertGreater(result.diagnostics.backend_work, 0)

    def test_stop_inside_session_stages_keeps_the_spent_base_work(self):
        reference = real_count_public(BeliefRequest(CENTER, 1))
        checks, base_work = reference.diagnostics.checkpoints, reference.diagnostics.work
        self.assertGreater(base_work, 0)
        # root는 기본 호출 전에 검사를 세 번 한다. 그 뒤 계수기의 검사 하나마다 콜백이 한 번 불린다.
        for offset in (1, 2, 3, 4):
            calls = [0]

            def cancelled():
                calls[0] += 1
                return calls[0] == 3 + checks + offset
            cls = proxy()
            with sessions(cls):
                result = reuse(request(), cancelled=cancelled)
            self.assertEqual((result.status, result.reason), ("CANCELLED", "CANCELLED"), offset)
            self.assertIsNone(result.base.total_worlds)
            self.assertEqual(result.diagnostics.backend_calls, 1)
            self.assertEqual(result.diagnostics.backend_work, base_work)  # 0으로 빠지지 않는다
            self.assertEqual((result.diagnostics.backend_trace[0].status, result.diagnostics.backend_trace[0].work),
                             ("CANCELLED", base_work))
            self.assertTrue(result.diagnostics.work_accounting_complete)
            self.assertEqual(len(cls.created[0].requests), 1)
            closed_once(self, cls)
        # 한 칸 앞(offset 0)은 기존과 같은 기본 계산의 마지막 공개 검사다.
        calls = [0]

        def at_publish():
            calls[0] += 1
            return calls[0] == 3 + checks
        result = reuse(request(), cancelled=at_publish)
        self.assertEqual((result.status, result.diagnostics.backend_work), ("CANCELLED", base_work))


class LifecycleTests(unittest.TestCase):
    def test_one_session_per_call_closed_and_not_shared(self):
        cls = proxy()
        with sessions(cls):
            query = request()
            payload = deepcopy(query.to_payload())
            replies = [reuse(query) for _ in range(2)]
        self.assertEqual(query.to_payload(), payload)
        self.assertEqual(len(cls.created), 2)
        self.assertIsNot(cls.created[0].real, cls.created[1].real)
        self.assertTrue(all(session.closed == 1 and not session.real.prepared for session in cls.created))
        self.assertEqual(replies[0].candidates, replies[1].candidates)
        self.assertGreater(replies[0].diagnostics.backend_calls, 1)
        self.assertEqual(replies[0].diagnostics.backend_calls, replies[1].diagnostics.backend_calls)
        self.assertEqual(replies[0].diagnostics.backend_work, replies[1].diagnostics.backend_work)
        # 두 번째 호출도 기본 계산을 자기 세션에서 한 번 한다(앞 호출의 값을 물려받지 않는다).
        self.assertEqual(replies[1].diagnostics.backend_trace[0].work,
                         real_count_public(BeliefRequest(CENTER, 1)).diagnostics.work)
        self.assertEqual([len(q.events) for q in cls.created[0].requests][0], 0)
        self.assertTrue(all(q.events for q in cls.created[0].requests[1:]))

    def test_later_base_failure_shape_is_still_handled(self):
        # 기존 경로의 "뒤 묶음의 기본 계산 실패" 응답 모양을 세션이 돌려줘도 root는 부분 결과로 멈춘다.
        cls = proxy(lambda query, reply: replace(reply, status="INSUFFICIENT", reason="WORK_LIMIT",
                                                 base=BaseResult("INSUFFICIENT", "WORK_LIMIT")) if query.events else reply)
        with sessions(cls):
            result = reuse(request())
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.base.total_worlds, 8)
        self.assertEqual(result.diagnostics.backend_calls, 2)
        closed_once(self, cls)


if __name__ == "__main__":
    unittest.main()
