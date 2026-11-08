"""Policy scheduling and one-use proposal contracts, distinct from game evidence."""
from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace
import json
import unittest
from unittest.mock import patch

import stage4_runtime_policy as p
from stage4_runtime_model import RuntimeUsage, ModelLimits


def request(**kwargs):
    return p.RuntimeRequest(((0, -2),), 0, kwargs.pop("counted_inputs", 1), **kwargs)


def limited(q, **kwargs):
    return SimpleNamespace(request_id=q.identity, model_id=p.MODEL_ID, status="RESOURCE_LIMIT",
                           reason="TEST_RESOURCE_LIMIT", usage=RuntimeUsage())


class RuntimePolicyTests(unittest.TestCase):
    def test_lossless_explicit_dto_roundtrip(self):
        for seed in (2**70+3, "1180591620717411303427"):
            q = request(mode="R", target=Fraction(2**65+3, 17), planning_seed=seed,
                counted_inputs=2**60, generation=2**62, episode_key="episode", settings_id="settings", instance_id="instance")
            payload = json.loads(json.dumps(q.to_payload()))
            self.assertEqual(p.RuntimeRequest.from_payload(payload), q)
            self.assertEqual(p.RuntimeRequest.from_payload(payload).identity, q.identity)
        with self.assertRaises(ValueError):
            p.RuntimeRequest.from_payload(dict(request().to_payload(), unknown=True))

    def test_schedule_first_open_interval_max8_and_retry_no_quota(self):
        policy = p.RuntimePolicy()
        with patch.object(p, "evaluate_model", side_effect=limited) as model:
            self.assertFalse(policy.choose(request(counted_inputs=0)).model_attempted)
            self.assertTrue(policy.choose(request(counted_inputs=1)).model_attempted)
            retry = policy.choose(request(counted_inputs=1))
            self.assertFalse(retry.sequence)
            self.assertEqual(policy.attempts_used, 1)
            self.assertFalse(policy.choose(request(counted_inputs=16)).model_attempted)
            for count in range(17, 114, 16):
                self.assertTrue(policy.choose(request(counted_inputs=count)).model_attempted)
            self.assertEqual(policy.attempts_used, 8)
            self.assertFalse(policy.choose(request(counted_inputs=129)).model_attempted)
            self.assertEqual(model.call_count, 8)

    def test_fallback_and_parent_expiration_are_distinct(self):
        q = request()
        with patch.object(p, "evaluate_model", side_effect=limited):
            r = p.RuntimePolicy().choose(q)
        self.assertEqual((r.status, r.decision_source, r.model_status), ("HEURISTIC_FALLBACK", "F", "RESOURCE_LIMIT"))
        now = [100.0]
        def expire(query, **kwargs):
            now[0] += 36.0
            return limited(query)
        with patch.object(p, "perf_counter", side_effect=lambda:now[0]), patch.object(p, "evaluate_model", side_effect=expire), patch.object(p, "choose_followup") as f:
            r = p.RuntimePolicy().choose(q)
        self.assertEqual((r.status, r.reason, r.sequence), ("RESOURCE_LIMIT", "PARENT_EXPIRED", ()))
        f.assert_not_called()

    def test_model_fault_unknown_cancel_never_fallback(self):
        for status, accounting in (("ERROR", True), ("INCONSISTENT_INPUT", True), ("CANCELLED", True), ("RESOURCE_LIMIT", False)):
            def reply(q, **kwargs):
                return SimpleNamespace(request_id=q.identity, model_id=p.MODEL_ID, status=status, reason="TEST",
                    usage=RuntimeUsage(accounting_complete=accounting))
            with patch.object(p, "evaluate_model", side_effect=reply), patch.object(p, "choose_followup") as f:
                r = p.RuntimePolicy().choose(request())
            self.assertFalse(r.sequence)
            f.assert_not_called()

    def test_claim_once_and_full_identity_binding(self):
        q = request(limits=p.RuntimeLimits(max_model_attempts=0))
        for change in ({"mode":"M"}, {"target":Fraction(6, 5)}, {"settings_id":"changed"},
                       {"instance_id":"different"}, {"generation":1}, {"counted_inputs":2}, {"episode_key":"other"}):
            policy = p.RuntimePolicy()
            r = policy.choose(q)
            self.assertTrue(r.sequence)
            self.assertFalse(policy.claim(r, replace(q, **change)))
            self.assertFalse(policy.claim(r, q))
        policy = p.RuntimePolicy()
        r = policy.choose(q)
        self.assertEqual(policy.claim(r, q), r.sequence)
        self.assertFalse(policy.claim(r, q))
        self.assertFalse(policy.choose(q).sequence)

    def test_busy_close_cancel_and_settings_invalidate_proposals(self):
        q = request(limits=p.RuntimeLimits(max_model_attempts=0))
        policy = p.RuntimePolicy()
        r = policy.choose(q)
        policy._lock.acquire()
        try:
            busy = policy.choose(replace(q, counted_inputs=2))
        finally:
            policy._lock.release()
        self.assertEqual((busy.status, busy.sequence), ("BUSY", ()))
        self.assertFalse(policy.claim(r, q))
        for method in ("cancel", "close", "terminal"):
            policy = p.RuntimePolicy()
            r = policy.choose(q)
            getattr(policy, method)()
            self.assertFalse(policy.claim(r, q))
        policy = p.RuntimePolicy()
        r = policy.choose(q)
        policy.choose(replace(q, mode="M"))
        self.assertFalse(policy.claim(r, q))

    def test_target_required_and_zero_parent(self):
        policy = p.RuntimePolicy()
        r = policy.choose(request(mode="R"))
        self.assertEqual((r.status, r.sequence, r.model_attempts_used), ("TARGET_REQUIRED", (), 0))
        r = p.RuntimePolicy().choose(request(limits=p.RuntimeLimits(max_seconds=0)))
        self.assertEqual((r.status, r.reason, r.sequence), ("RESOURCE_LIMIT", "PARENT_EXPIRED", ()))
        self.assertEqual(p.RuntimePolicy().choose(request(), cancelled=lambda:True).status, "CANCELLED")
        self.assertEqual(p.RuntimePolicy().choose(request(), cancelled=lambda:1).status, "ERROR")


if __name__ == "__main__":
    unittest.main()
