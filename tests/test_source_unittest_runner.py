"""Regressions for alias identity and non-additive unittest result events."""
import io
import json
import unittest

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
