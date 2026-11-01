"""RF transport regressions using a synthetic pair, never an Expert solver."""

from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch

from experiments import random_expert_exhibition_execution as execution
from experiments import random_expert_exhibition_process as processes
from experiments import random_expert_exhibition_worker as worker
from tests.test_random_expert_exhibition_execution import synthetic_expert_pair


class ExhibitionWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pair = synthetic_expert_pair()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="exhibition_worker_test_")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.request = self.directory / "request.pkl"
        self.result = self.directory / "result.pkl"
        self.progress = self.directory / "progress.json"
        self.request.write_bytes(pickle.dumps({"token": 1, "index": 11}))
        self.args = [str(p) for p in (self.request, self.result, self.progress)] + ["unit-test-scope"]

    def fixture_runner(self, index, *, progress):
        self.assertEqual(index, 11)
        progress("V1_RUNNING", None)
        progress("K_P0_RUNNING", self.pair.v1.summary())
        progress("PROJECTED", self.pair.k.summary())
        return self.pair

    def test_permission_error_at_every_progress_phase_preserves_pair_and_internal_state(self):
        publications = []

        def denied(path, value, *, json_text=False):
            self.assertEqual(path, self.progress)
            self.assertTrue(json_text)
            publications.append(json.loads(json.dumps(value)))
            raise PermissionError("injected progress sharing violation")

        with patch.object(worker, "write_atomic", side_effect=denied), \
                patch.object(execution, "run_expert_pair", side_effect=self.fixture_runner) as runner:
            value = worker.calculate({"token": 1, "index": 11}, self.progress)
        runner.assert_called_once()
        self.assertEqual(value, {"token": 1, "index": 11, "pair": self.pair, "error": None})
        self.assertEqual([p["phase"] for p in publications],
                         ["PREPARING", "V1_RUNNING", "K_P0_RUNNING", "PROJECTED"])
        self.assertEqual([len(p["completed"]) for p in publications], [0, 0, 1, 2])
        self.assertEqual(publications[-1]["completed"], [self.pair.v1.summary(), self.pair.k.summary()])
        worker.write_atomic(self.result, value)
        self.assertEqual(pickle.loads(self.result.read_bytes()), value)

    def test_progress_oserror_does_not_replace_later_native_cause_or_phase(self):
        def fails(index, *, progress):
            progress("K_P0_RUNNING", self.pair.v1.summary())
            raise RuntimeError("native fixture failure")

        with patch.object(worker, "write_atomic", side_effect=OSError("advisory unavailable")), \
                patch.object(execution, "run_expert_pair", side_effect=fails):
            value = worker.calculate({"token": 1, "index": 11}, self.progress)
        self.assertIsNone(value["pair"])
        self.assertTrue(value["error"].startswith("K_P0_RUNNING:"))
        self.assertIn("native fixture failure", value["error"])
        self.assertNotIn("advisory unavailable", value["error"])

    def test_non_io_progress_error_is_not_silently_ignored(self):
        with patch.object(worker, "write_atomic", side_effect=ValueError("bad serialization")), \
                patch.object(execution, "run_expert_pair") as runner:
            value = worker.calculate({"token": 1, "index": 11}, self.progress)
        runner.assert_not_called()
        self.assertIsNone(value["pair"])
        self.assertIn("bad serialization", value["error"])

    @unittest.skipUnless(os.name == "nt", "Windows file sharing contract")
    def test_real_windows_progress_sharing_violation_preserves_final_pair_and_removes_temps(self):
        worker.write_atomic(self.progress, {"previous": "advisory"}, json_text=True)
        original = self.progress.read_bytes()
        with self.progress.open("rb"):
            with self.assertRaises(PermissionError) as caught:
                worker.write_atomic(self.progress, {"replacement": True}, json_text=True)
            self.assertIn(caught.exception.winerror, (5, 32))
            with patch.object(execution, "run_expert_pair", side_effect=self.fixture_runner):
                value = worker.calculate({"token": 1, "index": 11}, self.progress)
            self.assertEqual(value["pair"], self.pair)
            self.assertIsNone(value["error"])
            worker.write_atomic(self.result, value)
        self.assertEqual(self.progress.read_bytes(), original)
        self.assertEqual(pickle.loads(self.result.read_bytes())["pair"], self.pair)
        self.assertEqual(list(self.directory.glob(".publish_*")), [])

    def test_final_atomic_publication_failure_is_nonzero_and_diagnostic(self):
        replace = os.replace

        def deny_result(source, target):
            if Path(target) == self.result:
                raise PermissionError("final result publication denied")
            return replace(source, target)

        stderr = io.StringIO()
        with patch.object(processes, "verify_worker_scope"), \
                patch.object(execution, "run_expert_pair", side_effect=self.fixture_runner), \
                patch.object(worker.os, "replace", side_effect=deny_result), redirect_stderr(stderr):
            code = worker.main(self.args)
        self.assertEqual(code, 1)
        self.assertIn("PermissionError: final result publication denied", stderr.getvalue())
        self.assertFalse(self.result.exists())
        self.assertEqual(list(self.directory.glob(".publish_*")), [])

    def test_scope_failure_is_reported_before_request_read_or_solver_execution(self):
        stderr = io.StringIO()
        with patch.object(processes, "verify_worker_scope", side_effect=FileNotFoundError("absent scope")), \
                patch("builtins.open", side_effect=AssertionError("must not read request before scope")), \
                patch.object(worker, "calculate") as calculate, redirect_stderr(stderr):
            code = worker.main(self.args)
        calculate.assert_not_called()
        self.assertEqual(code, 0)  # diagnostic envelope was published, not a successful pair
        value = pickle.loads(self.result.read_bytes())
        self.assertIsNone(value["token"])
        self.assertIsNone(value["pair"])
        self.assertIn("REQUEST_TRANSPORT", value["error"])
        self.assertIn("FileNotFoundError: absent scope", stderr.getvalue())
        self.assertIn(value["error"], stderr.getvalue())

    def test_request_read_failure_also_retains_tokenless_stderr_cause(self):
        self.request.unlink()
        stderr = io.StringIO()
        with patch.object(processes, "verify_worker_scope"), \
                patch.object(worker, "calculate") as calculate, redirect_stderr(stderr):
            code = worker.main(self.args)
        calculate.assert_not_called()
        self.assertEqual(code, 0)
        value = pickle.loads(self.result.read_bytes())
        self.assertIsNone(value["token"])
        self.assertIsNone(value["pair"])
        self.assertIn("REQUEST_TRANSPORT", stderr.getvalue())
        self.assertIn("FileNotFoundError", stderr.getvalue())
        self.assertIn(value["error"], stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
