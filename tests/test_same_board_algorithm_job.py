"""F: sequential algorithm queue with real worker processes (limit, cancel, error, order)."""

import os
import time
import unittest
from unittest.mock import patch

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
try:
    from PyQt5.QtCore import QCoreApplication
except ImportError:
    QCoreApplication = None
else:
    import same_board_algorithm_job as job_module
    from same_board_algorithm_job import SameBoardAlgorithmQueue

from replay_model import ReplayBoard
from same_board_algorithms import ALGORITHMS, LIMIT_SECONDS
from tests.test_same_board_algorithms import WIN_BOARD

BAD_BOARD = ReplayBoard(31, 16, 1, {(0, 0)})  # Outside every supported comparison size.


@unittest.skipIf(QCoreApplication is None, "PyQt5 unavailable")
class AlgorithmQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def make_queue(self):
        queue = SameBoardAlgorithmQueue()
        received = []
        queue.run_finished.connect(lambda token, run: received.append((token, run)))
        done = []
        queue.finished.connect(done.append)
        self.addCleanup(queue.shutdown)
        return queue, received, done

    def wait(self, done, seconds=90):
        deadline = time.monotonic() + seconds
        while not done and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
        self.assertTrue(done, "queue did not finish")

    def run_one(self, algorithm, board=WIN_BOARD, *, cancel=False, limit=None, r_target="120"):
        queue, received, done = self.make_queue()
        limits = dict(LIMIT_SECONDS)
        if limit is not None:
            limits[algorithm] = limit
        with patch.object(job_module, "LIMIT_SECONDS", limits):
            token = queue.start(board, (algorithm,), r_target if algorithm == "S4_R" else None)
            if cancel:
                queue.cancel()
            self.wait(done)
        self.assertEqual(done, [token])
        self.assertEqual([item[0] for item in received], [token])
        self.assertEqual(queue.state, "idle")
        return received[0][1]

    def test_each_algorithm_limit_cancel_and_worker_error_with_real_workers(self):
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm, case="limit"):
                run = self.run_one(algorithm, limit=0.2)
                self.assertEqual((run.algorithm, run.outcome), (algorithm, "LIMIT"))
                self.assertIn("Algorithm limit", run.detail)
                self.assertEqual((run.moves, run.actions, run.model_c_total_us), ((), None, None))
            with self.subTest(algorithm=algorithm, case="cancel"):
                run = self.run_one(algorithm, cancel=True)
                self.assertEqual((run.algorithm, run.outcome), (algorithm, "CANCELLED"))
                self.assertEqual(run.moves, ())
            with self.subTest(algorithm=algorithm, case="worker error"):
                run = self.run_one(algorithm, BAD_BOARD)
                self.assertEqual((run.algorithm, run.outcome), (algorithm, "ERROR"))
                self.assertIn("Execution failed", run.detail)
                self.assertEqual(run.moves, ())

    def test_completed_run_is_validated_in_the_parent(self):
        run = self.run_one("K_LC0")
        self.assertEqual(run.outcome, "WON")
        self.assertTrue(run.validated and run.playable)
        self.assertIsNotNone(run.actions)
        self.assertIsNotNone(run.model_c_total_us)
        self.assertGreater(run.elapsed_seconds, 0)

    def test_queue_limits_cancel_and_order(self):
        # Selection order is ignored; registry order is used.
        queue, received, done = self.make_queue()
        token = queue.start(WIN_BOARD, ("S4_S", "K_LC0", "K_P0"))
        deadline = time.monotonic() + 60
        while not received and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
        queue.cancel()
        self.wait(done)
        runs = [run for _, run in received]
        self.assertEqual([run.algorithm for run in runs], ["K_P0", "K_LC0", "S4_S"])
        self.assertEqual(runs[0].outcome, "WON")
        self.assertEqual([run.outcome for run in runs[1:]], ["CANCELLED", "CANCELLED"])
        self.assertTrue(all(item[0] == token for item in received))
        # Overall limit: the sum of selected limits; a spent budget marks the rest LIMIT.
        queue, received, done = self.make_queue()
        clock = [0.0]
        queue._clock = lambda: clock[0]
        limits = dict(LIMIT_SECONDS, K_P0=0.5, K_LC0=0.5)
        with patch.object(job_module, "LIMIT_SECONDS", limits):
            queue.start(WIN_BOARD, ("K_P0", "K_LC0"))
            clock[0] = 1.5  # Past both limits before the first child is reaped.
            self.wait(done)
        self.assertEqual([run.outcome for _, run in received], ["LIMIT", "LIMIT"])
        self.assertIn("Overall limit", received[1][1].detail)

    def test_queue_results_are_keyed_by_algorithm(self):
        queue, received, done = self.make_queue()
        queue.start(WIN_BOARD, ("K_LC1", "K_P0"))
        self.wait(done)
        by_key = {run.algorithm: run for _, run in received}
        self.assertEqual(set(by_key), {"K_P0", "K_LC1"})
        self.assertTrue(all(run.outcome == "WON" for run in by_key.values()))
        with self.assertRaises(ValueError):
            queue.start(WIN_BOARD, ("K_P0", "K_P0"))
        with self.assertRaises(ValueError):
            queue.start(WIN_BOARD, ("V9",))
        with self.assertRaises(ValueError):
            queue.start(WIN_BOARD, ())


if __name__ == "__main__":
    unittest.main()
