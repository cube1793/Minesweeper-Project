"""Synthetic temporary telemetry only; official smoke is not a unit fixture."""

import ast
from contextlib import closing
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction
from hashlib import sha256
import inspect
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from board_analyzer import analyze_board
import benchmark_board as boards
from core_engine import Action, CellState, GameStatus, MinesweeperEngine
import exemplar_board_evidence as evidence
from stage3_identity import STAGE3_V1_IDENTITY
from telemetry_collector import TelemetryCollector
from telemetry_model import InferenceCategory
import telemetry_repository as repository
import telemetry_schema as schema
from tests.test_telemetry_repository import run_inputs


PRODUCTION_HASHES = evidence._SOURCE_HASHES
PRODUCTION_REFERENCES = evidence._REFERENCES
PRODUCTION_PREFIX = evidence._PREFIX_GAMES
RISK = Fraction(10**100 + 1, 3 * 10**100)


class ExemplarEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.paths = tuple(self.root / name for name in ('s2 #%.sqlite3', 's3.sqlite3'))
        self.evaluation = evidence.modeled.authenticate_model_c()
        cells = [(x, y) for y in range(16) for x in range(30) if (x, y) not in ((0, 0), (1, 1))]
        self.mines = frozenset(cells[-98:] + [(1, 1)])
        engine = MinesweeperEngine()
        engine.reset_with_mines(30, 16, 99, self.mines)
        self.board = engine.get_board_snapshot()
        self.fingerprint = boards.calculate_board_fingerprint(30, 16, 99, self.mines)
        self.records = {}
        self.game_ids = {}
        self.run_ids = []
        self.run_values = []
        for side, path in enumerate(self.paths):
            config = {'accept_guesses': True, 'initial_open': [0, 0]}
            if side:
                config = {name: getattr(self.evaluation, name) for name in (
                    'physical_model_id', 'physical_profile_version', 'physical_profile_sha256',
                    'timing_table_sha256', 'timing_unit')}
                config.update(initial_open=[0, 0], initial_cursor=[0, 0],
                              algorithm_spec_version=STAGE3_V1_IDENTITY.algorithm_spec_version,
                              algorithm_spec_sha256=STAGE3_V1_IDENTITY.algorithm_spec_sha256)
            values = run_inputs(
                solver_stage=evidence._STAGES[side],
                solver_policy=(schema.SOLVER_POLICY_SIMPLE_MINIMUM_RISK,
                               schema.SOLVER_POLICY_E_FIRST_FIRST_REVEAL_V1)[side],
                telemetry_schema_version=side + 1, solver_config_snapshot=config,
                width=30, height=16, num_mines=99, benchmark_set_id='EXPERT_GENERAL_V1',
                requested_games=6,
            )
            self.run_values.append(values)
            with closing(repository.connect_database(path)) as connection:
                # Distinct actual IDs, neither assumed to be 1.
                for _ in range(side + 1):
                    repository.create_run(connection, **run_inputs())
                run_id = repository.create_run(connection, **values)
                self.run_ids.append(run_id)
                for index in range(6):
                    record, events = self._stream(index, side)
                    self.records[side, index] = record, events
                    self.game_ids[side, index] = repository.persist_completed_game(
                        connection, run_id, record, events)
                repository.update_run_status(connection, run_id, schema.RUN_STATUS_COMPLETED)
        references = []
        for index in (0, 2, 4, 5):
            streams = [self.records[side, index] for side in (0, 1)]
            totals = [evidence.project_timeline(record, events, width=30, height=16,
                                               evaluation=self.evaluation).total_modeled_us
                      for record, events in streams]
            references.append(evidence.ExemplarReference(index, f'Synthetic category {index}',
                self.fingerprint, *(record.total_actions for record, _ in streams),
                *totals, streams[0][0].result))
        self.references = tuple(references)
        for name, value in (('_PREFIX_GAMES', 6), ('_REFERENCES', self.references),
                            ('_SOURCE_HASHES', ()), ('_git_identity', lambda: ('synthetic-source', False))):
            patcher = patch.object(evidence, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self._seal()
        patcher = patch.object(boards, 'generate_board', side_effect=self._generated)
        self.generator = patcher.start()
        self.addCleanup(patcher.stop)

    def _generated(self, spec, index):
        self.assertIs(spec, boards.EXPERT_GENERAL_V1)
        self.assertIn(index, (0, 2, 4, 5))
        return boards.BenchmarkBoard(index, index, self.mines, self.fingerprint)

    def _stream(self, index, side):
        engine = MinesweeperEngine()
        engine.reset_with_mines(30, 16, 99, self.mines)
        steps = [(Action.OPEN, 0, 0, None)]
        if index == 5:
            steps.append((Action.OPEN, 1, 1, InferenceCategory.PROBABILITY_GUESS))
        else:
            steps.append((Action.FLAG, 1, 1, InferenceCategory.LOCAL_DETERMINISTIC))
            if side:
                steps.append((Action.CHORD, 0, 0, InferenceCategory.GLOBAL_CERTAINTY))
            else:
                steps.extend(((Action.OPEN, 1, 0, InferenceCategory.GLOBAL_CERTAINTY),
                              (Action.OPEN, 0, 1, InferenceCategory.GLOBAL_CERTAINTY)))
            steps.append((Action.OPEN, 4, 0, InferenceCategory.GLOBAL_CERTAINTY))
        collector = TelemetryCollector()
        for action, x, y, category in steps:
            before = engine.get_observation()
            engine.step(x, y, action)
            after = engine.get_observation()
            safe = sum(old in (CellState.HIDDEN, CellState.FLAGGED) and 0 <= new <= 8
                       for old_row, new_row in zip(before, after) for old, new in zip(old_row, new_row))
            metadata = {}
            if category is not None:
                guess = category == InferenceCategory.PROBABILITY_GUESS
                metadata = dict(inference_category=category,
                    selection_candidate_count=None if side else 3,
                    target_mine_probability=RISK if guess else Fraction(int(action == Action.FLAG)),
                    minimum_available_mine_probability=Fraction(1, 3) if guess else None,
                    decision_compute_ns=0 if action == Action.FLAG else 7)
            collector.record_action(action_type=action, x=x, y=y, status_after=engine.status,
                                    safe_cells_opened_delta=safe,
                                    explicit_flag_delta=int(action == Action.FLAG), **metadata)
        analysis = analyze_board(self.board)
        record = collector.finalize(game_index=index, seed=index, board_fingerprint=self.fingerprint,
                                    board_3bv=analysis.total_3bv, board_ops=analysis.total_ops)
        return record, collector.events

    def _seal(self):
        evidence._SOURCE_HASHES = tuple((role, sha256(path.read_bytes()).hexdigest())
                                       for (role, _), path in zip(PRODUCTION_HASHES, self.paths))

    def _edit(self, side, sql, parameters=()):
        with closing(repository.connect_database(self.paths[side])) as connection:
            connection.execute('PRAGMA ignore_check_constraints=ON')
            connection.execute(sql, parameters)
        self._seal()

    def _load(self):
        return evidence.load_accepted_exemplar_evidence(*self.paths)

    def _invalid(self, pattern):
        with self.assertRaisesRegex(evidence.ExemplarEvidenceError, pattern):
            self._load()

    def _reader(self, opened, queries=None):
        original = repository.connect_database_readonly
        def read(path, **kwargs):
            self.assertEqual(kwargs, {'immutable': True})
            connection = original(path, **kwargs)
            opened.append(connection)
            if queries is not None:
                connection.set_trace_callback(lambda sql: queries.append((Path(path), sql)))
            return connection
        return read

    def _closed(self, connections):
        for connection in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')

    def test_happy_path_original_models_and_four_eight_composition(self):
        with patch.object(evidence, 'project_timeline', wraps=evidence.project_timeline) as project, \
                patch.object(evidence, 'reconstruct_board', wraps=evidence.reconstruct_board) as reconstruct, \
                patch.object(evidence.modeled, 'authenticate_model_c', wraps=evidence.modeled.authenticate_model_c) as auth:
            result = self._load()
        self.assertEqual(len(result.exemplars), 4)
        self.assertEqual(project.call_count, 8)
        self.assertEqual(reconstruct.call_count, 8)
        self.assertEqual(auth.call_count, 1)
        self.assertEqual([call.args[1] for call in self.generator.call_args_list], [0, 2, 4, 5])
        self.assertEqual([run.summary.run_id for run in result.runs], self.run_ids)
        self.assertTrue(all(run.coverage.official_eligible for run in result.runs))
        self.assertTrue(all(run.coverage.exact_requested_prefix for run in result.runs))
        for game in result.exemplars:
            self.assertIs(game.board_snapshot, game.stage2.board_snapshot)
            self.assertIs(game.board_snapshot, game.stage3.board_snapshot)
            for side, rebuilt in enumerate((game.stage2, game.stage3)):
                record, events = self.records[side, game.reference.game_index]
                self.assertEqual(rebuilt.timeline.record, record)
                self.assertEqual(tuple(item.event for item in rebuilt.timeline.actions), events)
                self.assertIs(rebuilt.timeline.evaluation, result.evaluation)
                self.assertEqual(len(rebuilt.frames), record.total_actions + 1)
        self.assertEqual(result.reconstruction_git_head, 'synthetic-source')
        self.assertFalse(result.reconstruction_git_dirty)
        self.assertTrue(result.python_version)

    def test_source_provenance_exact_bytes_and_immutable_lifecycle(self):
        opened = []
        before = tuple((p.read_bytes(), p.stat().st_mtime_ns) for p in self.paths)
        original = evidence._source_state
        calls = []
        def state(role, path):
            if len(calls) >= 2:
                self._closed(opened)
            calls.append(role)
            return original(role, path)
        with patch.object(repository, 'connect_database_readonly', side_effect=self._reader(opened)), \
                patch.object(repository, 'connect_database', side_effect=AssertionError('writer')), \
                patch.object(evidence, '_source_state', side_effect=state):
            result = self._load()
        self.assertEqual(calls, ['stage2', 'stage3', 'stage2', 'stage3'])
        self.assertEqual(len(opened), 2)
        self._closed(opened)
        for source, path, (data, mtime) in zip(result.sources, self.paths, before):
            self.assertEqual((source.path, source.sha256, source.size_bytes, source.mtime_ns, source.sidecars),
                             (path.resolve(), sha256(data).hexdigest(), len(data), mtime, ()))
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), (data, mtime))
            self.assertFalse(evidence._sidecars(path))

    def test_hash_mismatch_for_either_role_before_any_open(self):
        for side in (0, 1):
            bad = list(evidence._SOURCE_HASHES)
            bad[side] = (bad[side][0], '0' * 64)
            with self.subTest(side=side), patch.object(evidence, '_SOURCE_HASHES', tuple(bad)), \
                    patch.object(repository, 'connect_database_readonly') as opener:
                self._invalid('SHA-256 mismatch')
                opener.assert_not_called()

    def test_swapped_roles_fail(self):
        with patch.object(repository, 'connect_database_readonly') as opener, \
                self.assertRaisesRegex(evidence.ExemplarEvidenceError, 'stage2.*SHA-256'):
            evidence.load_accepted_exemplar_evidence(*reversed(self.paths))
        opener.assert_not_called()

    def test_missing_or_directory_source_never_created_or_opened(self):
        for path in (self.root / 'missing', self.root):
            with self.subTest(path=path), patch.object(repository, 'connect_database_readonly') as opener, \
                    self.assertRaises(evidence.ExemplarEvidenceError):
                evidence.load_accepted_exemplar_evidence(path, self.paths[1])
            opener.assert_not_called()
        self.assertFalse((self.root / 'missing').exists())

    def test_same_physical_path_and_alias_rejected(self):
        for path in (self.paths[0], self.paths[0].parent / '.' / self.paths[0].name):
            with self.subTest(path=path), self.assertRaisesRegex(evidence.ExemplarEvidenceError, 'different physical'):
                evidence.load_accepted_exemplar_evidence(self.paths[0], path)

    def test_hard_link_is_same_physical_source(self):
        alias = self.root / 'alias.sqlite3'
        os.link(self.paths[0], alias)
        with self.assertRaisesRegex(evidence.ExemplarEvidenceError, 'different physical'):
            evidence.load_accepted_exemplar_evidence(self.paths[0], alias)

    def test_source_mutation_while_hashing_rejected(self):
        original = evidence._hash_file
        def changed(path):
            digest = original(path)
            stat = path.stat()
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
            return digest
        with patch.object(evidence, '_hash_file', side_effect=changed), \
                patch.object(repository, 'connect_database_readonly') as opener:
            self._invalid('changed while hashing')
            opener.assert_not_called()

    def test_each_entry_sidecar_rejected_before_open(self):
        for suffix in ('-wal', '-shm', '-journal'):
            path = Path(str(self.paths[0]) + suffix)
            path.write_bytes(b'synthetic sidecar')
            with self.subTest(suffix=suffix), patch.object(repository, 'connect_database_readonly') as opener:
                self._invalid('sidecars')
                opener.assert_not_called()
            path.unlink()

    def test_exit_size_hash_mtime_and_sidecar_drift_rejected(self):
        original = evidence._load_exemplars
        for kind in ('size', 'hash', 'mtime', 'sidecar'):
            path = self.paths[0]
            data, stat = path.read_bytes(), path.stat()
            sidecar = Path(str(path) + '-shm')
            def drift(*args):
                result = original(*args)
                if kind == 'size':
                    with path.open('ab') as stream:
                        stream.write(b'changed')
                elif kind == 'hash':
                    with path.open('r+b') as stream:
                        stream.seek(-1, 2)
                        stream.write(bytes([data[-1] ^ 1]))
                    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                elif kind == 'mtime':
                    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
                else:
                    sidecar.write_bytes(b'synthetic drift')
                return result
            with self.subTest(kind=kind), patch.object(evidence, '_load_exemplars', side_effect=drift), \
                    patch.object(evidence, 'AcceptedExemplarEvidence') as publish:
                self._invalid('Source preservation failed')
                publish.assert_not_called()
            if sidecar.exists():
                sidecar.unlink()
            path.write_bytes(data)
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    def test_failure_closes_both_and_rechecks_both_authenticated_sources(self):
        opened = []
        with patch.object(repository, 'connect_database_readonly', side_effect=self._reader(opened)), \
                patch.object(evidence, '_load_exemplars', side_effect=ValueError('original decode failure')), \
                patch.object(evidence, '_source_state', wraps=evidence._source_state) as state:
            self._invalid('original decode failure')
        self._closed(opened)
        self.assertEqual(state.call_count, 4)

    def test_second_open_failure_closes_first_and_checks_sources(self):
        opened = []
        read = self._reader(opened)
        def fail_second(path, **kwargs):
            if opened:
                raise sqlite3.OperationalError('second open failed')
            return read(path, **kwargs)
        with patch.object(repository, 'connect_database_readonly', side_effect=fail_second), \
                patch.object(evidence, '_source_state', wraps=evidence._source_state) as state:
            self._invalid('second open failed')
        self._closed(opened)
        self.assertEqual(state.call_count, 4)

    def test_partial_entry_authentication_still_rechecks_first_source(self):
        with patch.object(evidence, '_SOURCE_HASHES', (evidence._SOURCE_HASHES[0], ('stage3', '0' * 64))), \
                patch.object(evidence, '_source_state', wraps=evidence._source_state) as state:
            self._invalid('SHA-256 mismatch')
        self.assertEqual([call.args[0] for call in state.call_args_list], ['stage2', 'stage3', 'stage2'])

    def test_original_failure_and_exit_drift_both_reported(self):
        def fail(*args):
            Path(str(self.paths[0]) + '-journal').write_bytes(b'synthetic drift')
            raise ValueError('original failure')
        with patch.object(evidence, '_load_exemplars', side_effect=fail), \
                self.assertRaisesRegex(evidence.ExemplarEvidenceError, 'Source preservation.*original failure') as raised:
            self._load()
        self.assertEqual(str(raised.exception.__cause__), 'original failure')

    def test_model_authentication_failure_rechecks_sources_before_open(self):
        with patch.object(evidence.modeled, 'authenticate_model_c', side_effect=ValueError('model invalid')), \
                patch.object(repository, 'connect_database_readonly') as opener, \
                patch.object(evidence, '_source_state', wraps=evidence._source_state) as state:
            self._invalid('model invalid')
        opener.assert_not_called()
        self.assertEqual(state.call_count, 4)

    def test_no_eligible_run_and_each_wrong_identity_field(self):
        cases = (('solver_stage', 'OTHER'), ('solver_policy', 'OTHER'),
                 ('telemetry_schema_version', 9), ('solver_config_snapshot', '{}'),
                 ('benchmark_set_id', 'OTHER'), ('width', 31), ('height', 17), ('num_mines', 98),
                 ('first_click_policy', 'OTHER'), ('board_generator_version', 'V2'))
        for side in (0, 1):
            original = self.paths[side].read_bytes()
            for name, value in cases:
                with self.subTest(side=side, field=name):
                    self._edit(side, f'UPDATE benchmark_runs SET {name}=? WHERE run_id=?',
                               (value, self.run_ids[side]))
                    self._invalid('found 0')
                self.paths[side].write_bytes(original)
                self._seal()

    def test_dirty_incomplete_and_count_mismatches_fail(self):
        for field, value in (('git_dirty', 1), ('run_status', 'FAILED'),
                             ('requested_games', 7), ('processed_games', 5)):
            data = self.paths[0].read_bytes()
            with self.subTest(field=field):
                self._edit(0, f'UPDATE benchmark_runs SET {field}=? WHERE run_id=?', (value, self.run_ids[0]))
                self._invalid('found 0')
            self.paths[0].write_bytes(data)
            self._seal()

    def test_missing_and_noncontiguous_stored_coverage_fail(self):
        for sql in ('DELETE FROM games WHERE game_index=3',
                    'UPDATE games SET game_index=9 WHERE game_index=3'):
            data = self.paths[0].read_bytes()
            with self.subTest(sql=sql):
                self._edit(0, sql)
                self._invalid('found 0')
            self.paths[0].write_bytes(data)
            self._seal()

    def test_multiple_matching_runs_fail(self):
        with closing(repository.connect_database(self.paths[0])) as connection:
            run_id = repository.create_run(connection, **self.run_values[0])
            for index in range(6):
                repository.persist_completed_game(connection, run_id, *self.records[0, index])
            repository.update_run_status(connection, run_id, schema.RUN_STATUS_COMPLETED)
        self._seal()
        self._invalid('found 2')

    def test_production_entry_has_no_identity_or_game_override(self):
        self.assertEqual(tuple(inspect.signature(evidence.load_accepted_exemplar_evidence).parameters),
                         ('stage2_db_path', 'stage3_db_path'))
        self.assertEqual(PRODUCTION_PREFIX, 100000)
        self.assertEqual([r.game_index for r in PRODUCTION_REFERENCES], [73758, 73024, 93557, 1])
        self.assertEqual(PRODUCTION_HASHES, (
            ('stage2', '8b2adbe2ac1f9ef82a035f4ceb02e0193c944e4cb74b55c9243798386f60e65f'),
            ('stage3', 'b96141a069e3d77c6c4559eee468604785f147539dd290c456f65aaeab7d6f9e')))
        with patch.object(evidence, '_REFERENCES', PRODUCTION_REFERENCES):
            for index in (0, 6, True, '73758'):
                with self.subTest(index=index), self.assertRaises(evidence.ExemplarEvidenceError):
                    evidence._load_selected(None, None, index)

    def test_selected_only_sql_reads_and_no_paired_population_scan(self):
        opened, queries = [], []
        with patch.object(repository, 'connect_database_readonly', side_effect=self._reader(opened, queries)), \
                patch.object(evidence.statistics, 'validate_paired_prefix_sources',
                             side_effect=AssertionError('unnecessary paired scan')):
            self._load()
        details = [(path, sql) for path, sql in queries if 'SELECT * FROM action_events' in sql]
        games = [(path, sql) for path, sql in queries if 'SELECT * FROM games' in sql]
        self.assertEqual(len(details), 8)
        self.assertEqual(len(games), 8)
        for side, path in enumerate(self.paths):
            self.assertEqual({int(re.search(r'game_id = (\d+)', sql)[1]) for p, sql in details if p == path},
                             {self.game_ids[side, i] for i in (0, 2, 4, 5)})
            self.assertTrue(all('ORDER BY action_index' in sql for p, sql in details if p == path))
            self.assertEqual({int(re.search(r'game_index = (\d+)', sql)[1]) for p, sql in games if p == path},
                             {0, 2, 4, 5})
        self.assertTrue(all(sql.lstrip().upper().startswith(('SELECT ', 'PRAGMA ')) for _, sql in queries))
        self._closed(opened)

    def test_exact_decoding_fraction_null_zero_and_explicit_enums(self):
        result = self._load()
        winner, loser = result.exemplars[0], result.exemplars[-1]
        for side, rebuilt in enumerate((winner.stage2, winner.stage3)):
            events = tuple(item.event for item in rebuilt.timeline.actions)
            self.assertIsNone(events[0].inference_category)
            self.assertIsNone(events[0].decision_compute_ns)
            self.assertEqual(events[1].decision_compute_ns, 0)
            self.assertIs(type(events[1].decision_compute_ns), int)
            self.assertIs(events[1].action_type, Action.FLAG)
            self.assertIs(events[1].inference_category, InferenceCategory.LOCAL_DETERMINISTIC)
            self.assertIs(events[-1].status_after, GameStatus.WON)
            self.assertEqual(events[1].selection_candidate_count, None if side else 3)
        self.assertIs(winner.stage3.timeline.actions[2].event.action_type, Action.CHORD)
        for rebuilt in (loser.stage2, loser.stage3):
            guess = rebuilt.timeline.actions[-1].event
            self.assertEqual(guess.target_mine_probability, RISK)
            self.assertIsInstance(guess.target_mine_probability, Fraction)
            self.assertEqual(guess.minimum_available_mine_probability, Fraction(1, 3))
            self.assertEqual(rebuilt.timeline.record.result, 'LOSS')
            self.assertEqual(rebuilt.frames[-1].status, GameStatus.LOST)

    def test_malformed_persistence_enums_probabilities_and_boolean_fail(self):
        cases = (('action_events', 'action_type', 90), ('action_events', 'status_after', 90),
                 ('action_events', 'inference_category', 90),
                 ('action_events', 'target_mine_probability', '0.3'),
                 ('games', 'result', 90), ('games', 'had_probability_guess', 2))
        data = self.paths[0].read_bytes()
        for table, name, value in cases:
            with self.subTest(field=name):
                self._edit(0, f'UPDATE {table} SET {name}=? WHERE game_id=?', (value, self.game_ids[0, 0]))
                self._invalid('Invalid|probability')
            self.paths[0].write_bytes(data)
            self._seal()

    def test_missing_duplicate_selected_rows_rejected(self):
        run = MagicMock()
        run.summary.run_id, run.role = self.run_ids[0], 'stage2'
        for rows in ([], [None, None]):
            connection = MagicMock()
            connection.cursor.return_value.execute.return_value.fetchall.return_value = rows
            with self.subTest(count=len(rows)), self.assertRaisesRegex(ValueError, 'exactly one selected game row'):
                evidence._load_selected(connection, run, 0)
            connection.cursor.return_value.close.assert_called_once()

    def test_missing_shifted_and_postterminal_actions_fail_existing_timeline_validation(self):
        gid = self.game_ids[0, 0]
        data = self.paths[0].read_bytes()
        for sql in (f'DELETE FROM action_events WHERE game_id={gid} AND action_index=1',
                    f'UPDATE action_events SET action_index=7 WHERE game_id={gid} AND action_index=1',
                    f'UPDATE action_events SET status_after=2 WHERE game_id={gid} AND action_index=0'):
            with self.subTest(sql=sql):
                self._edit(0, sql)
                self._invalid('action|terminal|status')
            self.paths[0].write_bytes(data)
            self._seal()

    def test_selected_seed_first_click_and_fingerprint_fail_before_generation(self):
        data = self.paths[1].read_bytes()
        for field, value in (('seed', 99), ('first_click_x', 1), ('board_fingerprint', '0' * 64)):
            with self.subTest(field=field):
                self._edit(1, f'UPDATE games SET {field}=? WHERE game_index=0', (value,))
                self._invalid('selected identity/fingerprint')
                self.generator.assert_not_called()
            self.paths[1].write_bytes(data)
            self._seal()

    def test_paired_board_metrics_fail_before_generation(self):
        self._edit(1, 'UPDATE games SET board_ops=board_ops+1 WHERE game_index=0')
        self._invalid('paired selected identity')
        self.generator.assert_not_called()

    def test_generated_seed_index_fingerprint_and_actual_layout_are_gated(self):
        generated = self._generated(boards.EXPERT_GENERAL_V1, 0)
        different_mines = (self.mines - {(1, 1)}) | {(2, 2)}
        for changed in (replace(generated, game_index=8), replace(generated, seed=8),
                        replace(generated, board_fingerprint='0' * 64),
                        replace(generated, mine_positions=different_mines)):
            with self.subTest(changed=changed.seed), patch.object(boards, 'generate_board', return_value=changed) as generate, \
                    patch.object(evidence, 'reconstruct_board') as reconstruct:
                self._invalid('generated seed/fingerprint')
                generate.assert_called_once()
                reconstruct.assert_not_called()

    def test_generator_configuration_drift_rejected_before_generation(self):
        with patch.object(boards, 'EXPERT_GENERAL_V1', replace(boards.EXPERT_GENERAL_V1, width=31)):
            self._invalid('configuration drift')
        self.generator.assert_not_called()

    def test_wrong_fixed_fingerprint_rejected(self):
        refs = (replace(self.references[0], board_fingerprint='0' * 64), *self.references[1:])
        with patch.object(evidence, '_REFERENCES', refs):
            self._invalid('selected identity/fingerprint')
        self.generator.assert_not_called()

    def test_accepted_action_cost_and_outcome_gates(self):
        for field, value in (('stage2_actions', 999), ('stage3_actions', 999),
                             ('stage2_modeled_us', 1), ('stage3_modeled_us', 1), ('outcome', 'LOSS')):
            refs = (replace(self.references[0], **{field: value}), *self.references[1:])
            with self.subTest(field=field), patch.object(evidence, '_REFERENCES', refs):
                self._invalid('accepted action/cost/outcome totals')

    def test_reconstruction_effect_failure_remains_failure_atomic(self):
        self._edit(0, 'UPDATE action_events SET safe_cells_opened_delta=17 WHERE game_id=? AND action_index=0',
                   (self.game_ids[0, 0],))
        with patch.object(evidence, 'AcceptedExemplarEvidence') as publish:
            self._invalid('safe reveal delta')
        publish.assert_not_called()

    def test_bundle_is_deeply_immutable_and_retains_no_live_resources(self):
        result = self._load()
        for value in (result, result.sources[0], result.runs[0], result.exemplars[0], result.exemplars[0].reference):
            with self.subTest(kind=type(value)), self.assertRaises(FrozenInstanceError):
                setattr(value, fields(value)[0].name, None)
        def check(value):
            self.assertNotIsInstance(value, (list, dict, set, sqlite3.Connection, sqlite3.Row, MinesweeperEngine))
            if is_dataclass(value):
                for field in fields(value):
                    check(getattr(value, field.name))
            elif isinstance(value, (tuple, frozenset)):
                for item in value:
                    check(item)
        check(result)

    def test_no_forbidden_dependencies_or_write_paths(self):
        tree = ast.parse(inspect.getsource(evidence))
        forbidden = {'PyQt5', 'PyQt6', 'PySide6', 'zini', 'simple_runner', 'simple_decision',
                     'stage3_runner', 'stage3_planner', 'benchmark_runner', 'stage3_benchmark_runner',
                     'representative_boards', 'scripts', 'json', 'replay_model', 'stage3_trace_player'}
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                self.assertNotIn(name.split('.')[0], forbidden)
                self.assertFalse(name.startswith('zini'))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, {'connect_database', 'connect_database_for_continuation',
                    'initialize_schema', 'select_exemplars', 'collect_evidence', 'write_text', 'write_bytes'})
        with patch.object(repository, 'connect_database', side_effect=AssertionError('writer')), \
                patch.object(repository, 'connect_database_for_continuation', side_effect=AssertionError('writer')), \
                patch.object(schema, 'initialize_schema', side_effect=AssertionError('schema')):
            self._load()


if __name__ == '__main__':
    unittest.main()
