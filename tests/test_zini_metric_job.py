"""Transport/lifecycle tests on tiny synthetic snapshots, never official evidence."""

import os
from pathlib import Path
import pickle
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

from core_engine import MinesweeperEngine
import zini_metric_job as jobs


class ZiniMetricJobTests(unittest.TestCase):
    def setUp(self):
        engine = MinesweeperEngine(3, 3, 0)
        engine.reset_with_mines(3, 3, 0, set())
        self.snapshot = engine.get_board_snapshot()
        self.job = jobs.ZiniMetricJob()
        self.addCleanup(self.job.close)

    def launch(self):
        process = Mock()
        process.poll.return_value = None
        with patch.object(jobs.subprocess, 'Popen', return_value=process) as popen:
            self.job.start(self.snapshot, 17)
        self.assertTrue(self.job.active)
        return process, popen

    def write_result(self, **changes):
        result = dict(token=17, clicks=1, moves=(), error=None)
        result.update(changes)
        Path(self.job.result_path).write_bytes(pickle.dumps(result))
        return result

    def assert_clean(self, directory):
        self.assertFalse(Path(directory).exists())
        self.assertFalse(self.job.active)
        self.assertIsNone(self.job.process)
        self.assertIsNone(self.job.payload_path)
        self.assertIsNone(self.job.result_path)

    def test_import_without_qt_and_exact_shared_config(self):
        result = subprocess.run([sys.executable, '-B', '-S', '-c',
            "import sys; import zini_metric_job; assert not any(n.startswith('PyQt') for n in sys.modules)"],
            cwd=Path(jobs.__file__).parent, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        config = jobs.ZINI_COUNTER_CONFIG
        self.assertEqual((config.ranking_policy, config.max_evaluations,
            config.standard_phase_evaluations, config.max_seconds, config.stall_seconds, config.seed),
            ('standard_seeded_chain_v1', 1000, 500, None, None, 0))

    def test_source_and_frozen_commands_and_exact_payload(self):
        for frozen in (False, True):
            with self.subTest(frozen=frozen), patch.object(sys, 'frozen', frozen, create=True):
                process, popen = self.launch()
                payload_path, result_path = self.job.payload_path, self.job.result_path
                popen.assert_called_once_with(
                    [sys.executable, '--zini-metric-worker' if frozen else jobs.ZINI_WORKER_SCRIPT,
                     payload_path, result_path], cwd=os.path.dirname(jobs.ZINI_WORKER_SCRIPT),
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                payload = pickle.loads(Path(payload_path).read_bytes())
                self.assertEqual(payload, dict(token=17, snapshot=self.snapshot, config=jobs.ZINI_COUNTER_CONFIG))
                self.assertFalse(Path(result_path).exists())
                self.assertEqual(Path(payload_path).parent, Path(result_path).parent)
                self.job.close()
                process.terminate.assert_called_once()

    def test_pending_poll_does_not_wait_or_deliver(self):
        process, _ = self.launch()
        for _ in range(3):
            self.assertIsNone(self.job.poll())
        process.wait.assert_not_called()
        process.terminate.assert_not_called()

    def test_success_returned_once_reaps_and_removes_directory(self):
        process, _ = self.launch()
        directory = Path(self.job.payload_path).parent
        result = self.write_result()
        self.assertEqual(self.job.poll(), result)
        self.assertIsNone(self.job.poll())
        process.wait.assert_called_once_with(timeout=0.1)
        process.terminate.assert_not_called()
        self.assert_clean(directory)

    def test_stale_and_invalid_tokens_never_publish_clicks(self):
        for token in (16, None, True, '17'):
            with self.subTest(token=token):
                self.launch()
                self.write_result(token=token, clicks=999)
                result = self.job.poll()
                self.assertEqual(result['token'], 17)
                self.assertIsNone(result['clicks'])
                self.assertIn('token', result['error'])

    def test_corrupt_null_result_exit_and_calculation_failure_are_envelopes(self):
        for failure in ('corrupt', 'null', 'exit', 'calculation'):
            with self.subTest(failure=failure):
                process, _ = self.launch()
                directory = Path(self.job.payload_path).parent
                if failure == 'corrupt':
                    Path(self.job.result_path).write_bytes(b'not pickle')
                elif failure == 'null':
                    Path(self.job.result_path).write_bytes(pickle.dumps(None))
                elif failure == 'exit':
                    process.poll.return_value = process.returncode = 9
                else:
                    self.write_result(clicks=None, moves=None, error='calculation failed')
                result = self.job.poll()
                self.assertEqual(result['token'], 17)
                self.assertIsNone(result['clicks'])
                self.assertTrue(result['error'])
                self.assertIsNone(self.job.poll())
                self.assert_clean(directory)

    def test_launch_failure_cleans_files_and_delivers_once(self):
        with patch.object(jobs.subprocess, 'Popen', side_effect=OSError('launch failed')) as popen:
            self.job.start(self.snapshot, 17)
        directory = Path(popen.call_args.args[0][-2]).parent
        self.assertFalse(directory.exists())
        self.assertEqual(self.job.token, 17)
        result = self.job.poll()
        self.assertIn('launch failed', result['error'])
        self.assertEqual(result['token'], 17)
        self.assertIsNone(self.job.poll())
        self.assert_clean(directory)

    def test_cancel_escalates_to_kill_cleans_atomic_temp_and_is_idempotent(self):
        process, _ = self.launch()
        directory = Path(self.job.payload_path).parent
        (directory / '.minesweeper_zini_result_interrupted.tmp').write_bytes(b'partial')
        process.wait.side_effect = [subprocess.TimeoutExpired('worker', 1), 0]
        self.assertIsNone(self.job.close())
        self.assertIsNone(self.job.close())
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)
        self.assert_clean(directory)

    def test_cleanup_os_failure_keeps_child_owned_for_retry(self):
        process, _ = self.launch()
        directory = Path(self.job.payload_path).parent
        process.terminate.side_effect = OSError('terminate failed')
        process.kill.side_effect = OSError('kill failed')
        self.assertIn('kill failed', self.job.close())
        self.assertIs(self.job.process, process)
        self.assertTrue(directory.exists())
        process.terminate.side_effect = process.kill.side_effect = None
        self.assertIsNone(self.job.close())
        self.assert_clean(directory)

    def test_new_job_cancels_old_and_removes_old_result(self):
        process, _ = self.launch()
        directory = Path(self.job.payload_path).parent
        self.write_result()
        new_process = Mock()
        new_process.poll.return_value = None
        with patch.object(jobs.subprocess, 'Popen', return_value=new_process):
            self.job.start(self.snapshot, 18)
        process.terminate.assert_called_once()
        self.assertFalse(directory.exists())
        self.assertEqual(self.job.token, 18)
        self.assertIsNone(self.job.poll())

    def test_reap_error_is_failure_and_cleanup_is_still_attempted(self):
        process, _ = self.launch()
        directory = Path(self.job.payload_path).parent
        self.write_result()
        process.wait.side_effect = [OSError('wait failed'), 0]
        result = self.job.poll()
        self.assertIn('wait failed', result['error'])
        self.assertIsNone(result['clicks'])
        process.terminate.assert_called_once()
        self.assert_clean(directory)

    def test_replacement_does_not_launch_if_old_child_cannot_be_reaped(self):
        process, _ = self.launch()
        process.terminate.side_effect = process.kill.side_effect = OSError('denied')
        with patch.object(jobs.subprocess, 'Popen') as popen:
            self.job.start(self.snapshot, 18)
        popen.assert_not_called()
        self.assertIs(self.job.process, process)
        result = self.job.poll()
        self.assertEqual(result['token'], 18)
        self.assertIsNone(result['clicks'])
        self.assertIn('denied', result['error'])
        process.terminate.side_effect = process.kill.side_effect = None

    def test_real_tiny_board_worker_job_and_cleanup(self):
        # Real production config on a 3x3 empty board, not an Expert workload.
        self.job.start(self.snapshot, 17)
        process = self.job.process
        self.assertIsNotNone(process)
        directory = Path(self.job.payload_path).parent
        deadline = time.monotonic() + 20
        result = None
        while result is None and time.monotonic() < deadline:
            result = self.job.poll()
            if result is None:
                time.sleep(0.01)
        self.assertIsNotNone(result)
        self.assertIsNone(result['error'], result)
        self.assertEqual(result['clicks'], 1)
        self.assertEqual(result['token'], 17)
        self.assertIsNotNone(process.poll())
        self.assertIsNone(self.job.poll())
        self.assert_clean(directory)


if __name__ == '__main__':
    unittest.main()
