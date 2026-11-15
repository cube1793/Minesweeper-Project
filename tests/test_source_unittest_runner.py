"""Regressions for alias identity, result events and parent-side accounting."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import run_source_unittest_isolated as runner


class SourceRunnerTests(unittest.TestCase):
    def run_fixture(self, cls):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        ids = runner.test_ids(list(runner.flatten(suite)))
        journal = io.StringIO()
        result = runner.AccountedResult(unittest.runner._WritelnDecorator(io.StringIO()),
                                        True, 2, journal=journal)
        suite.run(result)
        receipt = runner.make_receipt(ids, [json.loads(row) for row in journal.getvalue().splitlines()])
        runner.validate_receipt(receipt, ids)
        return receipt

    def test_imported_alias_requires_same_class_method_and_state(self):
        first = SourceRunnerTests('test_imported_alias_requires_same_class_method_and_state')
        second = SourceRunnerTests(first._testMethodName)
        kept, audit = runner.normalize_discovered([first, second])
        self.assertEqual(kept, [first])
        self.assertEqual(len(audit), 1)
        self.assertTrue(all(audit[0]['checks'].values()))
        second.custom_state = 'different fixture'
        with self.assertRaisesRegex(RuntimeError, 'Nonidentical duplicate'):
            runner.normalize_discovered([first, second])

    def test_id_collision_between_distinct_classes_is_rejected(self):
        class First(unittest.TestCase):
            def test_one(self):
                pass
        class Second(First):
            pass
        Second.__qualname__ = First.__qualname__
        with self.assertRaisesRegex(RuntimeError, 'Nonidentical duplicate'):
            runner.normalize_discovered([First('test_one'), Second('test_one')])

    def test_custom_id_or_run_cannot_be_collapsed(self):
        class Custom(unittest.TestCase):
            def id(self):
                return 'shared-id'
            def test_one(self):
                pass
        with self.assertRaisesRegex(RuntimeError, 'Nonidentical duplicate'):
            runner.normalize_discovered([Custom('test_one'), Custom('test_one')])

    def test_multiple_subtest_failures_count_one_failed_test(self):
        class Fixture(unittest.TestCase):
            def test_many(self):
                for index in range(3):
                    with self.subTest(index=index):
                        self.fail('deliberate')
        receipt = self.run_fixture(Fixture)
        self.assertEqual(receipt['counts']['failure'], 1)
        self.assertEqual(receipt['counts']['failure_events'], 3)
        self.assertEqual(receipt['counts']['run'], 1)
        self.assertFalse(runner.successful(receipt['counts']))

    def test_setup_class_error_records_fixture_and_unstarted_ids(self):
        class Fixture(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError('deliberate setup error')
            def test_one(self):
                pass
            def test_two(self):
                pass
        receipt = self.run_fixture(Fixture)
        self.assertEqual(receipt['counts']['run'], 0)
        self.assertEqual(receipt['counts']['not_started'], 2)
        self.assertEqual(receipt['counts']['error_events'], 1)
        self.assertEqual(receipt['counts']['fixture_errors'], 1)
        self.assertFalse(runner.successful(receipt['counts']))

    def test_failure_and_teardown_error_preserve_both_events(self):
        class Fixture(unittest.TestCase):
            def test_one(self):
                self.fail('body')
            def tearDown(self):
                raise RuntimeError('teardown')
        counts = self.run_fixture(Fixture)['counts']
        self.assertEqual((counts['error'], counts['failure']), (1, 0))
        self.assertEqual((counts['error_events'], counts['failure_events']), (1, 1))

    def test_skip_and_expected_failure_are_not_passes(self):
        class Fixture(unittest.TestCase):
            @unittest.skip('explicit opt-in')
            def test_skip(self):
                pass
            @unittest.expectedFailure
            def test_expected(self):
                self.fail('expected')
            def test_pass(self):
                pass
        counts = self.run_fixture(Fixture)['counts']
        self.assertEqual((counts['pass'], counts['skip'], counts['expected_failure']), (1, 1, 1))
        self.assertEqual(sum(counts[key] for key in runner.STATUSES), 3)
        self.assertTrue(runner.successful(counts))

    def test_interrupted_journal_does_not_invent_a_completion(self):
        receipt = runner.make_receipt(['one', 'two'], [dict(kind='start', id='one')])
        runner.validate_receipt(receipt, ['one', 'two'])
        self.assertEqual(receipt['outcomes'], {'one': 'unfinished', 'two': 'not_started'})
        self.assertFalse(runner.successful(receipt['counts']))
        receipt['counts']['pass'] = 2
        with self.assertRaisesRegex(RuntimeError, 'accounting mismatch'):
            runner.validate_receipt(receipt, ['one', 'two'])

    def test_duplicate_execution_is_rejected(self):
        receipt = runner.make_receipt(['one'], [dict(kind='start', id='one')] * 2)
        with self.assertRaisesRegex(RuntimeError, 'Repeated test'):
            runner.validate_receipt(receipt, ['one'])

    def test_teardown_class_error_is_not_hidden_by_passed_methods(self):
        class Fixture(unittest.TestCase):
            def test_one(self):
                pass
            @classmethod
            def tearDownClass(cls):
                raise RuntimeError('class cleanup')
        counts = self.run_fixture(Fixture)['counts']
        self.assertEqual((counts['pass'], counts['error'], counts['fixture_errors']), (1, 0, 1))
        self.assertFalse(runner.successful(counts))

    def test_unknown_result_is_rejected_instead_of_claimed_as_fixture(self):
        receipt = runner.make_receipt(['one'], [dict(kind='pass', id='other', parent_id=None, detail=None)])
        with self.assertRaisesRegex(RuntimeError, 'Unknown fixture result'):
            runner.validate_receipt(receipt, ['one'])


def journal_row(kind, identity, parent_id=None, detail=None):
    return dict(kind=kind, id=identity, parent_id=parent_id, detail=detail)


def ran(identity, kind='pass', detail=None):
    return [journal_row('start', identity), journal_row(kind, identity, detail=detail),
            journal_row('stop', identity)]


def as_journal(rows):
    return ''.join(json.dumps(row) + '\n' for row in rows).encode('ascii')


class ParentAccountingTests(unittest.TestCase):
    """full_source with a stand-in launch. No child process is started."""

    ONE, TWO, THREE = IDS = ['fake.module.Case.test_one', 'fake.module.Case.test_two',
                             'fake.module.Case.test_three']

    def run_parent(self, journal=None, claimed=None, exit_code=0, launch_errors=(), extra_files=None):
        """Feed one partition to the parent and return its verdict and files.

        journal: rows, raw bytes, or None for no events.jsonl.
        claimed: rows the child's receipt is built from, or None for no receipt.
        """
        def launch(arguments, directory, timeout):
            if arguments[0] == '--discover-child':
                runner.write_json(arguments[1], dict(
                    raw_discovered=len(self.IDS), unique_discovered=len(self.IDS), selected_ids=self.IDS,
                    duplicates=[], partitions={'fake.module': self.IDS}))
                return dict(exit_code=0, errors=[])
            self.assertEqual(json.loads(Path(arguments[1]).read_text(encoding='utf-8')), self.IDS)
            if journal is not None:
                (directory / 'events.jsonl').write_bytes(
                    journal if isinstance(journal, bytes) else as_journal(journal))
            if claimed is not None:
                receipt = runner.make_receipt(self.IDS, claimed)
                runner.validate_receipt(receipt, self.IDS)
                runner.write_json(directory / 'receipt.json', receipt)
            for name, data in (extra_files or {}).items():
                (directory / name).write_bytes(data)
            return dict(exit_code=exit_code, errors=list(launch_errors))

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(runner, 'launch', launch), \
                contextlib.redirect_stdout(io.StringIO()) as printed:
            output = Path(temporary) / 'run'
            code = runner.full_source(output)
            files = {path.name: path.read_bytes() for path in (output / '001_fake.module').iterdir()}
            summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
        return code, summary, files, printed.getvalue()

    def all_passed(self):
        return [row for identity in self.IDS for row in ran(identity)]

    def assert_rejected(self, code, summary, message):
        self.assertEqual(code, 1)
        self.assertFalse(summary['successful'])
        self.assertEqual(summary['result_accounting'], 'INCOMPLETE')
        self.assertEqual(summary['journal_reconciled'], 0)
        self.assertGreater(summary['infrastructure_errors'], 0)
        self.assertTrue(any(message in row['error'] for row in summary['accounting_errors']),
                        summary['accounting_errors'])
        self.assertTrue(all(row['partition'] == 'fake.module' for row in summary['accounting_errors']))

    def test_matching_journal_receipt_and_exit_code_succeed(self):
        rows = (ran(self.ONE) + ran(self.TWO, 'skip', 'explicit opt-in') +
                ran(self.THREE, 'expected_failure', 'expected'))
        code, summary, files, printed = self.run_parent(journal=rows, claimed=rows)
        self.assertEqual(code, 0)
        self.assertTrue(summary['successful'])
        counts = summary['counts']
        self.assertEqual((counts['pass'], counts['skip'], counts['expected_failure']), (1, 1, 1))
        self.assertEqual((counts['selected'], counts['run'], counts['completed']), (3, 3, 3))
        self.assertEqual((summary['result_accounting'], summary['accounting_errors']), ('PASS', []))
        self.assertEqual((summary['journal_reconciled'], summary['infrastructure_errors']), (1, 0))
        self.assertEqual(sorted(files), ['events.jsonl', 'receipt.json', 'request.json'])
        self.assertIn('journal=MATCH', printed)

    def test_valid_receipt_that_contradicts_the_journal_fails(self):
        failed_two = ran(self.ONE) + ran(self.TWO, 'failure', 'deliberate') + ran(self.THREE)
        failed_one = ran(self.ONE, 'failure', 'deliberate') + ran(self.TWO) + ran(self.THREE)
        subtests = (ran(self.ONE)[:1] + [journal_row('failure', self.ONE + ' (index=0)', self.ONE, 'a'),
                                         journal_row('failure', self.ONE + ' (index=1)', self.ONE, 'b')] +
                    ran(self.ONE)[2:] + ran(self.TWO) + ran(self.THREE))
        fixture = self.all_passed() + [journal_row('error', 'tearDownClass (fake.module.Case)', detail='cleanup')]
        cases = dict(
            receipt_hides_failure=(failed_two, self.all_passed(), 0, ('outcomes', 'counts'), 'failure'),
            same_totals_different_test=(failed_two, failed_one, 1, ('outcomes',), 'failure'),
            receipt_drops_subtest_event=(subtests, subtests[:2] + subtests[3:], 1, ('events',), 'failure'),
            receipt_drops_fixture_error=(fixture, self.all_passed(), 0, ('fixture_events',), 'fixture_errors'),
            receipt_invents_failure=(self.all_passed(), failed_two, 1, ('outcomes',), None))
        for name, (journal, claimed, exit_code, differing, journal_status) in cases.items():
            with self.subTest(name):
                code, summary, files, printed = self.run_parent(journal=journal, claimed=claimed,
                                                                exit_code=exit_code)
                self.assert_rejected(code, summary, 'Journal/receipt mismatch')
                error = summary['accounting_errors'][0]['error']
                for field in differing:
                    self.assertIn(field, error)
                # The journal view is reported, and only as a recovery beside the originals.
                recovered = runner.make_receipt(self.IDS, journal)
                self.assertEqual(json.loads(files['recovered_receipt.json']), recovered)
                self.assertEqual(summary['counts'], recovered['counts'])
                if journal_status:
                    self.assertEqual(summary['counts'][journal_status], 1)
                else:
                    self.assertTrue(runner.successful(summary['counts']))
                self.assertEqual(files['events.jsonl'], as_journal(journal))
                self.assertEqual(json.loads(files['receipt.json']), runner.make_receipt(self.IDS, claimed))
                self.assertIn('journal=RECOVERED', printed)

    def test_success_receipt_without_a_usable_journal_fails(self):
        complete = as_journal(self.all_passed())
        cases = dict(
            missing=(None, 'Missing child journal', dict(not_started=3)),
            truncated_last_line=(complete[:-9], 'Incomplete journal line 9', dict(unfinished=1)),
            invalid_json_line=(complete.replace(b'{"kind": "pass"', b'{"kind": pass', 1),
                               'Incomplete journal line 2', dict(unfinished=1)),
            not_a_record=(b'[]\n' + complete, 'Incomplete journal line 1', dict()),
            unknown_kind=(complete + as_journal([journal_row('vanished', self.ONE)]),
                          'Incomplete journal line 10', dict()),
            not_utf8=(b'\xff\xfe' + complete, 'Unreadable child journal', dict(not_started=3)))
        for name, (journal, message, journal_counts) in cases.items():
            with self.subTest(name):
                code, summary, files, _ = self.run_parent(journal=journal, claimed=self.all_passed())
                self.assert_rejected(code, summary, message)
                for status, count in journal_counts.items():
                    self.assertEqual(summary['counts'][status], count)
                self.assertEqual(json.loads(files['receipt.json'])['counts']['pass'], 3)
                self.assertEqual(files.get('events.jsonl'), journal)
                self.assertEqual(json.loads(files['recovered_receipt.json'])['counts'], summary['counts'])

    def test_partial_journal_without_receipt_keeps_unfinished_and_unstarted(self):
        journal = ran(self.ONE) + ran(self.TWO)[:1]
        code, summary, files, _ = self.run_parent(
            journal=journal, exit_code=None, launch_errors=['TimeoutExpired: deliberate stand-in'])
        self.assert_rejected(code, summary, 'Missing child receipt')
        counts = summary['counts']
        self.assertEqual((counts['pass'], counts['unfinished'], counts['not_started']), (1, 1, 1))
        self.assertEqual((counts['selected'], counts['run'], counts['completed']), (3, 2, 1))
        self.assertNotIn('receipt.json', files)
        self.assertEqual(json.loads(files['recovered_receipt.json'])['outcomes'],
                         {self.ONE: 'pass', self.TWO: 'unfinished', self.THREE: 'not_started'})
        self.assertEqual(summary['processes'][0]['errors'],
                         ['TimeoutExpired: deliberate stand-in', 'Missing child receipt'])

    def test_exit_code_that_contradicts_the_receipt_fails(self):
        failed = ran(self.ONE) + ran(self.TWO, 'error', 'deliberate') + ran(self.THREE)
        for name, rows, exit_code in (('clean_receipt_exit_1', self.all_passed(), 1),
                                      ('clean_receipt_exit_2', self.all_passed(), 2),
                                      ('failed_receipt_exit_0', failed, 0),
                                      ('clean_receipt_no_exit', self.all_passed(), None)):
            with self.subTest(name):
                code, summary, _, _ = self.run_parent(journal=rows, claimed=rows, exit_code=exit_code)
                self.assert_rejected(code, summary, 'Exit/receipt mismatch')
                self.assertEqual(summary['counts'], runner.make_receipt(self.IDS, rows)['counts'])

    def test_launch_error_fails_even_when_results_look_clean(self):
        rows = self.all_passed()
        code, summary, files, _ = self.run_parent(
            journal=rows, claimed=rows,
            launch_errors=['Cleanup RuntimeError: Owned processes remain after cleanup'])
        self.assertEqual(code, 1)
        self.assertFalse(summary['successful'])
        self.assertEqual(summary['counts']['pass'], 3)
        self.assertTrue(runner.successful(summary['counts']))
        self.assertEqual((summary['result_accounting'], summary['journal_reconciled']), ('PASS', 1))
        self.assertEqual(summary['infrastructure_errors'], 1)
        self.assertNotIn('recovered_receipt.json', files)
        # A timeout leaves no exit code, so it is also an accounting failure.
        code, summary, _, _ = self.run_parent(
            journal=rows, claimed=rows, exit_code=None,
            launch_errors=['TimeoutExpired: deliberate stand-in'])
        self.assert_rejected(code, summary, 'Exit/receipt mismatch')
        self.assertEqual((summary['counts']['pass'], summary['infrastructure_errors']), (3, 2))

    def test_unwritable_recovery_keeps_the_summary_and_the_existing_file(self):
        journal = ran(self.ONE) + ran(self.TWO, 'failure', 'deliberate') + ran(self.THREE)
        code, summary, files, _ = self.run_parent(journal=journal, claimed=self.all_passed(),
                                                  extra_files={'recovered_receipt.json': b'occupied'})
        self.assert_rejected(code, summary, 'Journal/receipt mismatch')
        self.assertTrue(any('Recovered receipt not written' in row['error']
                            for row in summary['accounting_errors']))
        self.assertEqual((summary['counts']['pass'], summary['counts']['failure']), (2, 1))
        self.assertEqual(files['recovered_receipt.json'], b'occupied')
