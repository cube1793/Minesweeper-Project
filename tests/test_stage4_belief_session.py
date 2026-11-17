"""계수 세션(stage4_belief.PublicCountSession)의 계약 시험.

독립 정답은 tests.stage4_belief_oracle.count_small에서 온다(제품 계수기를 가져오지 않는 전수 열거).
count_public과의 비교는 같은 코드 계열의 재현이며 독립 정답 대조와 구분해서 읽는다.
"""
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import unittest
from unittest.mock import patch

import stage4_belief as belief
from tests.stage4_belief_oracle import OracleBudget, count_small
from tests.test_stage4_belief import small_corpus, small_events

H, F = -2, -3
PAIR = [[H, 1, H]]
EVENTS = (belief.EventQuery(), belief.EventQuery([(0, 0)]), belief.EventQuery([(2, 0)]))
RICH = ([[H, 1, H, 1, H, H, H]], 2)  # 제약 구성요소와 제약 없는 칸이 함께 있는 공개 상태


def base_request(grid=PAIR, mines=1, **limits):
    return belief.BeliefRequest(grid, mines, (), belief.BeliefLimits(**limits))


def event_request(events=EVENTS, grid=PAIR, mines=1, **limits):
    return belief.BeliefRequest(grid, mines, events, belief.BeliefLimits(**limits))


def chunks(items, size):
    return [tuple(items[i:i + size]) for i in range(0, len(items), size)]


def prepared(grid=PAIR, mines=1):
    session = belief.PublicCountSession()
    reply = session.count_base(base_request(grid, mines))
    assert reply.status == "COMPLETE", reply
    return session


def no_numbers(test, reply):
    test.assertIsNone(reply.base.total_worlds)
    test.assertIsNone(reply.base.marginals)
    for row in reply.events:
        test.assertIsNone(row.event_worlds)
        test.assertIsNone(row.probability)


class OracleTests(unittest.TestCase):
    """독립 정답 대조: 기본값과 여러 묶음으로 나눠 센 사건 값."""

    def test_corpus_against_independent_enumeration(self):
        budget = OracleBudget()
        checked = 0
        for index, (grid, mines) in enumerate(small_corpus()):
            with self.subTest(index=index):
                request = belief.BeliefRequest(grid, mines, small_events(grid))
                primitive = [(e.safe_cells, e.mine_cells) for e in request.events]
                expected = count_small(grid, mines, primitive, budget)
                session = belief.PublicCountSession()
                base = session.count_base(belief.BeliefRequest(grid, mines))
                self.assertEqual(base.base.total_worlds, expected["D"])
                if expected["D"] == 0:
                    self.assertEqual(base.status, "INCONSISTENT_INPUT")
                    self.assertFalse(session.prepared)
                    continue
                self.assertEqual(base.status, "COMPLETE")
                self.assertTrue(session.prepared)
                self.assertEqual({c.coordinate: c.mine_worlds for c in base.base.marginals}, expected["M"])
                worlds = {}
                for part in chunks(request.events, 3):
                    reply = session.count_events(belief.BeliefRequest(grid, mines, part))
                    self.assertEqual(reply.status, "COMPLETE")
                    self.assertIs(reply.base, base.base)
                    for row in reply.events:
                        self.assertEqual(row.status, "EXACT")
                        self.assertEqual(row.probability, Fraction(row.event_worlds, expected["D"]))
                        worlds[row.event] = row.event_worlds
                self.assertEqual([worlds[e] for e in request.events], expected["W"])
                session.close()
                checked += 1
        self.assertEqual(budget.states, 32)
        self.assertGreater(checked, 20)


class EquivalenceTests(unittest.TestCase):
    """같은 코드 계열의 재현: count_public과 같은 값, 작업량은 사건 계산량만."""

    def test_base_call_equals_count_public_plus_the_session_stages(self):
        for index, (grid, mines) in enumerate(small_corpus()):
            with self.subTest(index=index):
                request = belief.BeliefRequest(grid, mines)
                reference = belief.count_public(request)
                session = belief.PublicCountSession()
                reply = session.count_base(request)
                self.assertEqual((reply.request_id, reply.status, reply.reason), (reference.request_id,
                                 reference.status, reference.reason))
                self.assertEqual(reply.base, reference.base)
                self.assertEqual(reply.diagnostics.work, reference.diagnostics.work)
                names = [s.stage for s in reference.diagnostics.stages]
                got = reply.diagnostics.stages
                self.assertEqual([s.stage for s in got[:len(names)]], names)
                self.assertEqual([(s.work_start, s.work_end) for s in got[:len(names)]],
                                 [(s.work_start, s.work_end) for s in reference.diagnostics.stages])
                if reference.status == "COMPLETE":
                    # 새 단계 둘(준비, 봉인)의 시작·끝 검사 네 번이 더해진다. 작업량은 늘지 않는다.
                    self.assertEqual([s.stage for s in got[len(names):]], ["session.prepare", "session.seal"])
                    self.assertTrue(all(s.work_start == s.work_end for s in got[len(names):]))
                    self.assertEqual(reply.diagnostics.checkpoints, reference.diagnostics.checkpoints + 4)
                    self.assertTrue(session.prepared)
                else:
                    self.assertEqual(len(got), len(names))
                    self.assertEqual(reply.diagnostics.checkpoints, reference.diagnostics.checkpoints)
                    self.assertFalse(session.prepared)

    def test_event_batches_equal_count_public_and_charge_only_event_work(self):
        for index, (grid, mines) in enumerate(small_corpus()):
            request = belief.BeliefRequest(grid, mines, small_events(grid))
            full = belief.count_public(request)
            if full.status != "COMPLETE":
                continue
            with self.subTest(index=index):
                base_work = belief.count_public(belief.BeliefRequest(grid, mines)).diagnostics.work
                reference = {row.event: row for row in full.events}
                session = belief.PublicCountSession()
                base = session.count_base(belief.BeliefRequest(grid, mines))
                spent = 0
                for part in chunks(request.events, 4):
                    query = belief.BeliefRequest(grid, mines, part)
                    reply = session.count_events(query)
                    self.assertEqual(reply.request_id, query.identity)
                    self.assertNotEqual(reply.request_id, base.request_id)
                    self.assertEqual(reply.status, "COMPLETE")
                    self.assertEqual(reply.base, full.base)
                    self.assertEqual([s.stage for s in reply.diagnostics.stages[:2]],
                                     ["session.bind", "session.verify"])
                    self.assertTrue(all(s.stage.startswith("event.") for s in reply.diagnostics.stages[2:]))
                    self.assertEqual(reply.diagnostics.work,
                                     sum(s.work_end - s.work_start for s in reply.diagnostics.stages))
                    for row in reply.events:
                        self.assertEqual(row, reference[row.event])
                    spent += reply.diagnostics.work
                self.assertEqual(spent, full.diagnostics.work - base_work)

    def test_exact_event_work_limit_boundary(self):
        grid, mines = RICH
        events = tuple(small_events(grid))[:6]
        session = prepared(grid, mines)
        needed = session.count_events(belief.BeliefRequest(grid, mines, events)).diagnostics.work
        self.assertGreater(needed, 1)
        exact = session.count_events(belief.BeliefRequest(grid, mines, events, belief.BeliefLimits(max_work=needed)))
        self.assertEqual((exact.status, exact.diagnostics.work), ("COMPLETE", needed))
        short = session.count_events(belief.BeliefRequest(grid, mines, events,
                                                          belief.BeliefLimits(max_work=needed - 1)))
        self.assertEqual((short.status, short.reason, short.diagnostics.work), ("PARTIAL", "WORK_LIMIT", needed - 1))
        self.assertEqual(short.base, exact.base)
        done = [row for row in short.events if row.status == "EXACT"]
        self.assertTrue(done)
        reference = {row.event: row for row in exact.events}
        for row in done:
            self.assertEqual(row, reference[row.event])
        self.assertTrue(all(row.event_worlds is None for row in short.events if row.status != "EXACT"))


class BindingTests(unittest.TestCase):
    def refused(self, reply, request, reason):
        self.assertEqual((reply.status, reply.reason), ("ERROR", reason))
        self.assertEqual(reply.request_id, request.identity)
        self.assertEqual((reply.base.status, reply.base.reason), ("ERROR", reason))
        self.assertEqual(reply.diagnostics.work, 0)
        self.assertEqual(len(reply.events), len(request.events))
        no_numbers(self, reply)

    def test_other_public_state_is_refused_without_numbers(self):
        session = prepared()
        others = [event_request(grid=[[F, 1, H]]),          # 깃발 표현만 다른 관측
                  event_request(mines=2),                    # 다른 지뢰 수
                  event_request(grid=[[H, 1, H], [H, H, H]]),  # 다른 관측
                  event_request(events=(belief.EventQuery(),), grid=[[H, 0, H]], mines=0)]
        for request in others:
            self.refused(session.count_events(request), request, "SESSION_BINDING_MISMATCH")
        # 깃발만 다른 관측은 계수 값이 같아도 재사용하지 않는다(count_public의 결과는 같다).
        self.assertEqual(belief.count_public(event_request()).events,
                         belief.count_public(event_request(grid=[[F, 1, H]])).events)
        # 거부 뒤에도 원래 공개 상태의 요청은 정상이다.
        good = session.count_events(event_request())
        self.assertEqual(good.status, "COMPLETE")
        self.assertEqual(good.events, belief.count_public(event_request()).events)
        # 다른 prior는 count_public처럼 결속 검사보다 먼저 지원 범위에서 걸린다.
        other_prior = replace(event_request(), prior_id="other")
        reply = session.count_events(other_prior)
        self.assertEqual((reply.status, reply.reason), ("UNSUPPORTED", "PRIOR_UNSUPPORTED"))
        no_numbers(self, reply)

    def test_unprepared_closed_and_repeated_base(self):
        session = belief.PublicCountSession()
        self.assertFalse(session.prepared)
        self.refused(session.count_events(event_request()), event_request(), "SESSION_BASE_NOT_PREPARED")
        with_events = event_request()
        self.refused(session.count_base(with_events), with_events, "SESSION_BASE_REQUEST_HAS_EVENTS")
        self.assertFalse(session.prepared)
        first = session.count_base(base_request())
        self.assertEqual(first.status, "COMPLETE")
        again = base_request()
        self.refused(session.count_base(again), again, "SESSION_BASE_ALREADY_PREPARED")
        self.assertEqual(session.count_events(event_request()).status, "COMPLETE")  # 기존 상태는 그대로다
        session.close()
        self.assertFalse(session.prepared)
        self.assertIsNone(session._state)
        self.refused(session.count_events(event_request()), event_request(), "SESSION_CLOSED")
        self.refused(session.count_base(base_request()), base_request(), "SESSION_CLOSED")

    def test_argument_types_and_limits(self):
        session = belief.PublicCountSession()
        for method in (session.count_base, session.count_events):
            with self.assertRaises(TypeError):
                method({"observation": PAIR, "num_mines": 1})
            with self.assertRaises(TypeError):
                method(base_request(), cancelled=True)
        small = session.count_base(base_request(max_cells=2))
        self.assertEqual((small.status, small.reason), ("UNSUPPORTED", "CELL_LIMIT"))
        self.assertFalse(session.prepared)
        session = prepared()
        for request, reason in ((event_request(max_events=1), "EVENT_LIMIT"), (event_request(max_cells=2), "CELL_LIMIT")):
            reply = session.count_events(request)
            self.assertEqual((reply.status, reply.reason), ("UNSUPPORTED", reason))
            no_numbers(self, reply)

    def test_request_identity_follows_events_and_limits_not_the_base_call(self):
        session = prepared()
        a = session.count_events(event_request())
        b = session.count_events(event_request(max_work=100))
        c = session.count_events(event_request(events=EVENTS[:2]))
        self.assertEqual(len({a.request_id, b.request_id, c.request_id}), 3)
        self.assertEqual(a.request_id, event_request().identity)
        self.assertEqual(b.request_id, event_request(max_work=100).identity)
        self.assertEqual(a.events, b.events)


class PreparationTests(unittest.TestCase):
    """준비·봉인 단계와 결속·대조 단계의 시간 종료·취소·오류. 상태 확정은 마지막 검사 뒤다."""

    def setUp(self):
        self.reference = belief.count_public(base_request())
        self.checks = self.reference.diagnostics.checkpoints
        self.work = self.reference.diagnostics.work
        self.assertGreater(self.work, 0)

    def stopped_base(self, reply, session, status, reason, stage):
        self.assertEqual((reply.status, reply.reason), (status, reason))
        no_numbers(self, reply)
        self.assertEqual(reply.diagnostics.work, self.work)  # 이미 쓴 기본 계산량은 0으로 빠지지 않는다
        self.assertEqual(reply.diagnostics.last_checkpoint, stage)
        self.assertFalse(session.prepared)
        self.assertIsNone(session._state)
        later = session.count_events(event_request())
        self.assertEqual((later.status, later.reason), ("ERROR", "SESSION_BASE_NOT_PREPARED"))

    def test_cancel_inside_prepare_and_seal_leaves_no_state(self):
        for offset, stage in ((1, "session.prepare"), (2, "session.prepare"), (3, "session.seal"), (4, "session.seal")):
            calls = [0]

            def cancelled():
                calls[0] += 1
                return calls[0] == self.checks + offset

            session = belief.PublicCountSession()
            reply = session.count_base(base_request(), cancelled=cancelled)
            self.stopped_base(reply, session, "CANCELLED", "CANCELLED", stage)
        # 마지막 검사(offset 4)는 봉인 계산이 끝난 뒤다. 그래도 상태를 확정하지 않는다.
        session = belief.PublicCountSession()
        done = session.count_base(base_request(), cancelled=lambda: False)
        self.assertEqual(done.status, "COMPLETE")
        self.assertEqual(done.diagnostics.checkpoints, self.checks + 4)
        self.assertTrue(session.prepared)

    def test_time_limit_inside_prepare_and_seal(self):
        for offset, stage in ((1, "session.prepare"), (3, "session.seal"), (4, "session.seal")):
            reads = [0]

            def clock():
                reads[0] += 1  # 예산 생성 때 1회, 그 뒤 검사마다 1회
                return 3.0 if reads[0] >= 1 + self.checks + offset else 0.0

            session = belief.PublicCountSession()
            with patch.object(belief, "monotonic", side_effect=clock):
                reply = session.count_base(base_request())
            self.stopped_base(reply, session, "INSUFFICIENT", "TIME_LIMIT", stage)

    def test_callback_and_internal_errors_inside_prepare_and_seal(self):
        calls = [0]

        def failing():
            calls[0] += 1
            if calls[0] == self.checks + 1:
                raise RuntimeError("injected callback failure")
            return False

        session = belief.PublicCountSession()
        reply = session.count_base(base_request(), cancelled=failing)
        self.stopped_base(reply, session, "ERROR", "CANCEL_CALLBACK_ERROR", "session.prepare")
        self.assertIn("injected callback failure", reply.diagnostics.error)
        for name, stage in (("MappingProxyType", "session.prepare"), ("_session_seal", "session.seal")):
            session = belief.PublicCountSession()
            with patch.object(belief, name, side_effect=RuntimeError("injected " + name)):
                reply = session.count_base(base_request())
            self.stopped_base(reply, session, "ERROR", "INTERNAL_ERROR", stage)
            self.assertIn("injected " + name, reply.diagnostics.error)

    def test_bind_and_verify_stages_obey_cancel_time_and_errors(self):
        reference = belief.count_public(event_request())
        session = prepared()
        for offset, stage in ((1, "session.bind"), (2, "session.bind"), (3, "session.verify"), (4, "session.verify")):
            calls = [0]

            def cancelled():
                calls[0] += 1
                return calls[0] == offset

            reply = session.count_events(event_request(), cancelled=cancelled)
            self.assertEqual((reply.status, reply.reason), ("CANCELLED", "CANCELLED"))
            self.assertEqual(reply.request_id, event_request().identity)
            no_numbers(self, reply)  # 대조를 끝내지 못한 기본값은 내보내지 않는다
            self.assertEqual((reply.diagnostics.work, reply.diagnostics.last_checkpoint), (0, stage))
            reads = [0]

            def clock():
                reads[0] += 1
                return 3.0 if reads[0] >= 1 + offset else 0.0

            with patch.object(belief, "monotonic", side_effect=clock):
                reply = session.count_events(event_request())
            self.assertEqual((reply.status, reply.reason), ("INSUFFICIENT", "TIME_LIMIT"))
            no_numbers(self, reply)
        calls = [0]

        def failing():
            calls[0] += 1
            raise RuntimeError("injected bind callback failure")

        reply = session.count_events(event_request(), cancelled=failing)
        self.assertEqual((reply.status, reply.reason), ("ERROR", "CANCEL_CALLBACK_ERROR"))
        no_numbers(self, reply)
        with patch.object(belief, "_session_seal", side_effect=RuntimeError("injected verify failure")):
            reply = session.count_events(event_request())
        self.assertEqual((reply.status, reply.reason), ("ERROR", "INTERNAL_ERROR"))
        self.assertIn("injected verify failure", reply.diagnostics.error)
        no_numbers(self, reply)
        zero = session.count_events(event_request(max_seconds=0))
        self.assertEqual((zero.status, zero.reason), ("INSUFFICIENT", "TIME_LIMIT"))
        no_numbers(self, zero)
        # 중단된 호출은 보관 상태를 바꾸지 않는다. 다음 정상 호출은 기준과 같다.
        self.assertTrue(session.prepared)
        good = session.count_events(event_request())
        self.assertEqual((good.status, good.events, good.base), ("COMPLETE", reference.events, reference.base))

    def test_event_phase_partials_keep_completed_rows(self):
        reference = belief.count_public(event_request())
        session = prepared()
        limited = session.count_events(event_request(max_work=1))
        self.assertEqual(limited.status, "PARTIAL")
        self.assertEqual(limited.base, reference.base)
        self.assertEqual([row.status for row in limited.events], ["EXACT", "INSUFFICIENT", "NOT_EVALUATED"])
        self.assertEqual(limited.events[0], reference.events[0])
        self.assertIsNone(limited.events[1].probability)
        self.assertIsNone(limited.events[2].event_worlds)
        self.assertEqual(limited.diagnostics.work, 1)
        zero = session.count_events(event_request(max_work=0))
        self.assertEqual([row.status for row in zero.events], ["EXACT", "INSUFFICIENT", "NOT_EVALUATED"])
        self.assertEqual(zero.diagnostics.work, 0)
        for mode in ("time", "cancel", "error"):
            calls = [0]

            def trigger():
                calls[0] += 1
                return calls[0] >= 4 + 8  # 결속·대조 4회와 첫 사건 4회 뒤, 둘째 사건의 열거 안

            def failing():
                if trigger():
                    raise RuntimeError("injected event callback failure")
                return False

            if mode == "time":
                with patch.object(belief, "monotonic", side_effect=lambda: 3.0 if trigger() else 0.0):
                    reply = session.count_events(event_request())
            else:
                reply = session.count_events(event_request(), cancelled=trigger if mode == "cancel" else failing)
            self.assertEqual(reply.status, "PARTIAL")
            self.assertEqual(reply.base, reference.base)
            self.assertEqual(reply.events[0], reference.events[0])
            self.assertEqual(reply.events[1].status,
                             {"time": "INSUFFICIENT", "cancel": "CANCELLED", "error": "ERROR"}[mode])
            self.assertIsNone(reply.events[1].probability)
            self.assertEqual(reply.events[2].status, "NOT_EVALUATED")
        with patch.object(belief, "_convolve", side_effect=RuntimeError("injected DP error")):
            reply = session.count_events(event_request())
        self.assertEqual((reply.status, reply.reason), ("PARTIAL", "INTERNAL_ERROR"))
        self.assertEqual(reply.events[0], reference.events[0])
        self.assertEqual(reply.events[1].status, "ERROR")
        self.assertIn("injected DP error", reply.diagnostics.error)


class SealTests(unittest.TestCase):
    """봉인은 계산 결과와 응답 내용에 영향을 주는 보관 값을 모두 덮는다."""

    def corrupt(self, session, request):
        reply = session.count_events(request)
        self.assertEqual((reply.status, reply.reason), ("ERROR", "SESSION_STATE_CORRUPT"))
        self.assertEqual(reply.diagnostics.work, 0)
        no_numbers(self, reply)

    def test_every_retained_value_is_sealed(self):
        grid, mines = RICH
        events = tuple(small_events(grid))[:5]
        request = belief.BeliefRequest(grid, mines, events)
        reference = belief.count_public(request)
        session = prepared(grid, mines)
        state = session._state
        self.assertGreater(len(state.components), 0)
        self.assertGreater(len(state.floating), 0)
        first_ways = dict(state.counts[0][0])
        key = next(iter(first_ways))
        changed_ways = belief.MappingProxyType({**first_ways, key: first_ways[key] + 1})
        marginals = state.base.marginals
        changes = {
            "base_total": replace(state, base=replace(state.base, total_worlds=state.base.total_worlds + 1)),
            "base_marginal": replace(state, base=replace(state.base, marginals=(
                replace(marginals[0], mine_worlds=marginals[0].mine_worlds + 1),) + marginals[1:])),
            "components": replace(state, components=state.components[:-1] + (replace(
                state.components[-1], cells=state.components[-1].cells[:-1]),)),
            "constraint": replace(state, components=(replace(state.components[0], constraints=tuple(
                (cells, value + 1) for cells, value in state.components[0].constraints)),) + state.components[1:]),
            "floating": replace(state, floating=state.floating[:-1]),
            "ways": replace(state, counts=((changed_ways, None),) + state.counts[1:]),
        }
        for name, tampered in changes.items():
            with self.subTest(name=name):
                self.assertEqual(tampered.seal, state.seal)
                session._state = tampered
                self.corrupt(session, request)
        # 공개 상태 자체를 바꾼 경우: 요청이 원래 상태면 결속에서, 바뀐 상태와 같으면 봉인에서 걸린다.
        flagged = tuple(tuple(F if (x, y) == (0, 0) else v for x, v in enumerate(row))
                        for y, row in enumerate(state.observation))
        session._state = replace(state, observation=flagged)
        reply = session.count_events(request)
        self.assertEqual((reply.status, reply.reason), ("ERROR", "SESSION_BINDING_MISMATCH"))
        self.corrupt(session, belief.BeliefRequest(flagged, mines, events))
        session._state = replace(state, num_mines=mines + 1)
        self.corrupt(session, belief.BeliefRequest(grid, mines + 1, events))
        # 원래 상태로 돌아오면 기준과 같은 값이 나온다.
        session._state = state
        good = session.count_events(request)
        self.assertEqual((good.status, good.events, good.base), ("COMPLETE", reference.events, reference.base))

    def test_retained_values_are_read_only(self):
        session = prepared(*RICH)
        state = session._state
        ways = state.counts[0][0]
        with self.assertRaises(TypeError):
            ways[next(iter(ways))] = 0
        with self.assertRaises(FrozenInstanceError):
            state.floating = ()
        with self.assertRaises(FrozenInstanceError):
            state.base.total_worlds = 0
        self.assertIsInstance(state.counts, tuple)
        self.assertIsInstance(state.components, tuple)
        self.assertIsInstance(state.floating, tuple)
        self.assertTrue(all(pair[1] is None for pair in state.counts))  # mine_ways는 보관하지 않는다
        self.assertEqual(set(type(state).__dataclass_fields__),
                         {"observation", "num_mines", "prior_id", "base", "components", "floating", "counts",
                          "component_sizes", "base_request_id", "seal"})

    def test_seal_is_deterministic_and_state_specific(self):
        one, two = prepared(*RICH), prepared(*RICH)
        self.assertEqual(one._state.seal, two._state.seal)
        self.assertEqual(len(one._state.seal), 64)
        self.assertNotEqual(one._state.seal, prepared()._state.seal)
        self.assertNotEqual(one._state.seal, prepared([[F, 1, H, 1, H, H, H]], 2)._state.seal)


class LifecycleTests(unittest.TestCase):
    def test_sessions_are_independent_and_leave_no_module_state(self):
        grid, mines = RICH
        events = tuple(small_events(grid))[:6]
        before = belief.count_public(belief.BeliefRequest(grid, mines, events))
        containers = {name: len(value) for name, value in vars(belief).items()
                      if isinstance(value, (dict, list, set)) and not name.startswith("__")}
        records = []
        for _ in range(2):
            first, second = prepared(grid, mines), prepared()
            a = first.count_events(belief.BeliefRequest(grid, mines, events))
            b = second.count_events(event_request())
            c = first.count_events(belief.BeliefRequest(grid, mines, events))
            records.append((a.events, a.diagnostics.work, b.events, b.diagnostics.work, c.events, c.diagnostics.work))
            self.assertEqual((a.events, a.diagnostics.work), (c.events, c.diagnostics.work))
            first.close()
            self.assertEqual(second.count_events(event_request()).events, b.events)  # 다른 세션은 영향받지 않는다
            second.close()
        self.assertEqual(records[0], records[1])
        self.assertEqual(records[0][0], before.events)
        after = belief.count_public(belief.BeliefRequest(grid, mines, events))
        self.assertEqual((after.base, after.events, after.diagnostics.work),
                         (before.base, before.events, before.diagnostics.work))
        self.assertEqual(containers, {name: len(value) for name, value in vars(belief).items()
                                      if isinstance(value, (dict, list, set)) and not name.startswith("__")})

    def test_existing_entry_points_are_untouched_names(self):
        for name in ("count_public", "_base", "_event_count", "_Budget", "_prepare", "_enumerate", "_convolve",
                     "_weighted", "BaseResult", "BeliefRequest", "BeliefLimits", "EventQuery"):
            self.assertTrue(hasattr(belief, name), name)
        self.assertEqual(belief.COUNTER_VERSION, "bounded_public_counts_v1")
        self.assertEqual(belief.NORMALIZATION_POLICY, "physical_flags_as_hidden_v1")


if __name__ == "__main__":
    unittest.main()
