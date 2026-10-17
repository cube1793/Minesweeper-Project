"""Bounded synthetic evidence only; no official artifacts or solver execution."""

import ast
from collections import Counter
from contextlib import closing
from dataclasses import asdict, replace
from fractions import Fraction
from html.parser import HTMLParser
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core_engine import Action, GameStatus
from scripts import stage3_timeline_report as report
from stage3_identity import STAGE3_V1_IDENTITY
from telemetry_model import InferenceCategory
import telemetry_repository as repository
import telemetry_schema as schema
from tests.test_telemetry_repository import completed_game, run_inputs


class DocumentInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.external = []
        self.svg_count = 0
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        self.svg_count += tag == "svg"
        self.scripts += tag == "script"
        for key, value in attrs:
            if key in ("src", "href", "srcset") and value and not value.startswith("#"):
                self.external.append(value)


class ReportTests(unittest.TestCase):
    """Nine tiny games per DB, including every outcome and WW delta sign."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.paths = {role: self.root / name for role, name in (
            ("stage2", "stage2-analysis.sqlite3"), ("stage3", "stage3-analysis.sqlite3"),
            ("comparison", "comparison-001.json"), ("result", "g4-result.json"),
        )}
        self.evaluation = report.modeled.authenticate_model_c()
        self.records = {}
        self.run_ids = []
        self.game_ids = {}
        self.outcomes = {"ww": 5, "wl": 1, "lw": 1, "ll": 2}
        totals = [[], []]
        for side, role in enumerate(("stage2", "stage3")):
            with closing(repository.connect_database(self.paths[role])) as connection:
                # An unrelated earlier run proves that accepted run_id is discovered.
                repository.create_run(connection, **run_inputs())
                config = {"accept_guesses": True, "initial_open": [0, 0]}
                if side:
                    config = {**report._model_identity(self.evaluation), "initial_open": [0, 0],
                              "algorithm_spec_version": STAGE3_V1_IDENTITY.algorithm_spec_version,
                              "algorithm_spec_sha256": STAGE3_V1_IDENTITY.algorithm_spec_sha256}
                run_id = repository.create_run(connection, **run_inputs(
                    telemetry_schema_version=2 if side else 1,
                    solver_stage="STAGE_3" if side else "STAGE_2",
                    solver_policy=schema.SOLVER_POLICY_E_FIRST_FIRST_REVEAL_V1 if side else schema.SOLVER_POLICY_SIMPLE_MINIMUM_RISK,
                    solver_config_snapshot=config, benchmark_set_id="EXPERT_GENERAL_V1",
                    width=30, height=16, num_mines=99, requested_games=9,
                ))
                self.run_ids.append(run_id)
                for index in range(9):
                    won = index < 5 or index == (6 if side else 5)
                    record, events = completed_game(index, GameStatus.WON if won else GameStatus.LOST)
                    record = replace(record, seed=100 + index, board_fingerprint=f"{index + 1:064x}")
                    x = ((4, 4, 4, 20, 4)[index] if side else (20, 15, 10, 4, 4)[index]) if index < 5 else 4
                    events = events[:-1] + (replace(events[-1], x=x),)
                    if side:
                        events = tuple(replace(event, selection_candidate_count=None) for event in events)
                    self.records[role, index] = record, events
                    self.game_ids[role, index] = repository.persist_completed_game(connection, run_id, record, events)
                    totals[side].append(report.timeline.project_timeline(
                        record, events, width=30, height=16, evaluation=self.evaluation,
                    ).total_modeled_us)
                repository.update_run_status(connection, run_id, schema.RUN_STATUS_COMPLETED)
        deltas = [[index, totals[1][index] - totals[0][index]] for index in reversed(range(5))]
        primary = dict(
            game_count=5, paired_deltas_us=deltas,
            stage2_total_us=sum(totals[0][:5]), stage3_total_us=sum(totals[1][:5]),
            total_delta_us=sum(delta for _, delta in deltas), stage3_faster=3, stage2_faster=1, ties=1,
            ratio=str(Fraction(sum(totals[1][:5]), sum(totals[0][:5]))),
            reduction=str(1 - Fraction(sum(totals[1][:5]), sum(totals[0][:5]))),
        )
        self.comparison = dict(
            scope="official_100000_prefix_comparison", prefix_games=9, require_official=True,
            evaluation=report._model_identity(self.evaluation), outcomes=self.outcomes,
            primary=primary, primary_delta_convention="Stage3 minus Stage2, integer microseconds",
            diagnostic_stage2_total_us=sum(totals[0]), diagnostic_stage3_total_us=sum(totals[1]),
            stage2_wins=6, stage2_losses=3, stage3_wins=6, stage3_losses=3,
            stage2_win_rate="2/3", stage3_win_rate="2/3",
            left=dict(run_id=self.run_ids[0], solver_stage="STAGE_2", telemetry_schema_version=1,
                      evaluation_kind="post_hoc_frozen_model_c", label="stage2-analysis-copy"),
            right=dict(run_id=self.run_ids[1], solver_stage="STAGE_3", telemetry_schema_version=2,
                       evaluation_kind="declared_frozen_model_c", label="stage3-analysis-copy"),
        )
        self.result = dict(gate="G4", status="PASS", paired_delta_count=5,
                           comparison_api=dict(name="benchmark_comparison.compare_stage2_stage3_sources",
                                               left_run_id=self.run_ids[0], right_run_id=self.run_ids[1],
                                               left_source_label="stage2-analysis-copy", right_source_label="stage3-analysis-copy",
                                               prefix_games=9, require_official=True))
        self._refresh_artifacts()
        self.addCleanup(patch.stopall)
        patch.object(report, "PREFIX_GAMES", 9).start()
        patch.object(report, "EXPECTED_OUTCOMES", self.outcomes).start()
        patch.object(report, "EXPECTED_HASHES", self.hashes).start()

    def _refresh_artifacts(self):
        """Seal synthetic fixtures; never called by production report code."""
        self.paths["comparison"].write_text(json.dumps(self.comparison), encoding="utf-8")
        self.result["official_comparison"] = dict(path="comparison-001.json", sha256=report._hash_file(self.paths["comparison"]))
        preservation = {}
        for role in ("stage2", "stage3"):
            path = self.paths[role]
            preservation[role + "_copy"] = {path.name: dict(present=True, sha256=report._hash_file(path), size_bytes=path.stat().st_size)}
            preservation[role + "_copy"].update({path.name + suffix: {"present": False} for suffix in ("-wal", "-shm", "-journal")})
        self.result["preservation_entry"] = preservation
        self.result["preservation_exit"] = preservation
        self.result["summary"] = {key: self.comparison[key] for key in (
            "diagnostic_stage2_total_us", "diagnostic_stage3_total_us", "outcomes", "stage2_losses",
            "stage2_win_rate", "stage2_wins", "stage3_losses", "stage3_win_rate", "stage3_wins",
        )}
        self.result["summary"]["primary"] = {key: value for key, value in self.comparison["primary"].items() if key != "paired_deltas_us"}
        self.paths["result"].write_text(json.dumps(self.result), encoding="utf-8")
        hashes = {role: report._hash_file(path) for role, path in self.paths.items()}
        if hasattr(self, "hashes"):
            self.hashes.update(hashes)
        else:
            self.hashes = hashes

    def _edit_db(self, role, statement, parameters=()):
        with closing(repository.connect_database(self.paths[role])) as connection:
            connection.execute(statement, parameters)
        self._refresh_artifacts()

    def _collect(self):
        return report.collect_evidence(self.paths)

    def _assert_invalid(self, message=None):
        with patch.object(report.representatives, "select_exemplars") as selector:
            with self.assertRaisesRegex(ValueError, message or ".*"):
                self._collect()
            selector.assert_not_called()

    def test_each_hash_mismatch_fails_before_sqlite_or_selection(self):
        for role in self.paths:
            with self.subTest(role=role), patch.dict(report.EXPECTED_HASHES, {role: "0" * 64}), \
                    patch.object(repository, "connect_database_readonly") as opener:
                self._assert_invalid("SHA-256 mismatch")
                opener.assert_not_called()

    def test_missing_input_fails_before_selection(self):
        paths = {**self.paths, "stage3": self.root / "missing.sqlite3"}
        with patch.object(report.representatives, "select_exemplars") as selector, self.assertRaises(FileNotFoundError):
            report.collect_evidence(paths)
        selector.assert_not_called()
        self.assertFalse(paths["stage3"].exists())

    def test_sidecar_before_open_rejected(self):
        Path(str(self.paths["stage2"]) + "-wal").write_bytes(b"synthetic unexpected sidecar")
        with patch.object(repository, "connect_database_readonly") as opener:
            self._assert_invalid("sidecars")
        opener.assert_not_called()

    def test_immutable_open_and_discovered_run_identity(self):
        with patch.object(repository, "connect_database_readonly", wraps=repository.connect_database_readonly) as opener:
            data = self._collect()
        self.assertEqual(opener.call_count, 2)
        self.assertTrue(all(call.kwargs == {"immutable": True} for call in opener.call_args_list))
        self.assertEqual([run.run_id for run in data.runs], self.run_ids)
        self.assertNotEqual(self.run_ids[0], 1)
        self.assertTrue(all(item.official_eligible and item.exact_requested_prefix for item in data.coverage))

    def test_zero_matching_runs_rejected(self):
        self._edit_db("stage2", "UPDATE benchmark_runs SET git_dirty=1")
        self._assert_invalid("found 0")

    def test_multiple_matching_runs_rejected(self):
        with closing(repository.connect_database(self.paths["stage2"])) as connection:
            original = dict(repository.fetch_run(connection, self.run_ids[0]))
            values = {name: original[name] for name in run_inputs()}
            values["git_dirty"] = False
            values["solver_config_snapshot"] = json.loads(values["solver_config_snapshot"])
            values["environment_snapshot"] = json.loads(values["environment_snapshot"])
            duplicate = repository.create_run(connection, **values)
            for index in range(9):
                repository.persist_completed_game(connection, duplicate, *self.records["stage2", index])
            repository.update_run_status(connection, duplicate, schema.RUN_STATUS_COMPLETED)
        self._refresh_artifacts()
        self._assert_invalid("found 2")

    def test_independent_summary_missing_and_shifted_prefix_fail(self):
        for role in ("stage2", "stage3"):
            with self.subTest(role=role), closing(repository.connect_database(self.paths[role])) as connection:
                connection.execute("UPDATE games SET game_index=20 WHERE run_id=? AND game_index=8", (self.run_ids[0],))
                with self.assertRaisesRegex(ValueError, "exact requested prefix"):
                    report._load_summaries(connection, self.run_ids[0])
                connection.execute("DELETE FROM games WHERE run_id=? AND game_index=20", (self.run_ids[0],))
                with self.assertRaisesRegex(ValueError, "count mismatch"):
                    report._load_summaries(connection, self.run_ids[0])

    def test_cross_source_identity_mismatch_fails(self):
        self._edit_db("stage3", "UPDATE games SET seed=seed+1 WHERE game_index=8")
        self._assert_invalid()

    def test_g4_ww_set_mismatch_fails(self):
        self.comparison["primary"]["paired_deltas_us"][0][0] = 8
        self._refresh_artifacts()
        self._assert_invalid("WW index set mismatch")

    def test_g4_duplicate_index_fails(self):
        self.comparison["primary"]["paired_deltas_us"][0][0] = self.comparison["primary"]["paired_deltas_us"][1][0]
        self._refresh_artifacts()
        self._assert_invalid("Duplicate G4")

    def test_g4_noninteger_delta_fails_including_bool(self):
        for value in (1.5, True, "123", None):
            with self.subTest(value=value):
                self.comparison["primary"]["paired_deltas_us"][0][1] = value
                self._refresh_artifacts()
                self._assert_invalid("exact integers")

    def test_g4_stored_sum_mismatch_fails(self):
        self.comparison["primary"]["total_delta_us"] += 1
        self._refresh_artifacts()
        self._assert_invalid("total delta mismatch")

    def test_g4_result_provenance_mismatch_fails(self):
        self.result["comparison_api"]["left_run_id"] = 900
        self._refresh_artifacts()
        self._assert_invalid("API provenance mismatch")

    def test_g4_model_identity_mismatch_fails(self):
        self.comparison["evaluation"]["timing_table_sha256"] = "0" * 64
        self._refresh_artifacts()
        self._assert_invalid("Model C identity mismatch")

    def test_selector_input_and_output_preserved_all_categories(self):
        calls = []
        accepted = report.representatives.select_exemplars
        def select(facts):
            selected = accepted(facts)
            calls.append((facts, selected))
            return selected
        with patch.object(report.representatives, "select_exemplars", side_effect=select):
            data = self._collect()
        self.assertEqual(len(calls), 1)
        facts, selection = calls[0]
        self.assertIs(data.selection, selection)
        self.assertEqual(len(facts), 9)
        self.assertTrue(all(fact.delta_us is None for fact in facts[5:]))
        self.assertTrue(all(type(fact.delta_us) is int for fact in facts[:5]))
        self.assertEqual(len(data.selection), 8)
        self.assertTrue(all(item.game is not None for item in data.selection))
        self.assertEqual(data.outcomes, self.outcomes)
        self.assertEqual(data.delta_counts, (3, 1, 1))

    def test_duplicate_memberships_and_selected_only_detail_reads(self):
        queries = []
        real_open = repository.connect_database_readonly
        def open_traced(path, **kwargs):
            connection = real_open(path, **kwargs)
            connection.set_trace_callback(lambda sql: queries.append((Path(path).name, sql)))
            return connection
        with patch.object(repository, "connect_database_readonly", side_effect=open_traced), \
                patch.object(report, "_load_game", wraps=report._load_game) as loader:
            data = self._collect()
        indices = {item.game.game_index for item in data.selection if item.game}
        self.assertLess(len(indices), 8)
        self.assertLess(len(indices), 9)
        self.assertEqual(len(data.games), len(indices))
        self.assertEqual(loader.call_count, 2 * len(indices))
        self.assertEqual(Counter(call.args[2] for call in loader.call_args_list), Counter({index: 2 for index in indices}))
        action_reads = [(name, sql) for name, sql in queries if "FROM action_events" in sql]
        self.assertEqual(len(action_reads), 2 * len(indices))
        for role in ("stage2", "stage3"):
            expected = {f"SELECT * FROM action_events WHERE game_id = {self.game_ids[role, index]} ORDER BY action_index" for index in indices}
            self.assertEqual({sql for name, sql in action_reads if name == self.paths[role].name}, expected)

    def test_empty_categories_retained_in_renderer(self):
        data = self._collect()
        selected = report.representatives.select_exemplars([
            report.representatives.PairedGameFact(0, "WIN", "WIN", -10),
        ])
        html = report.render_report(replace(data, selection=selected, games=()), {})
        self.assertEqual(html.count("<td>EMPTY</td>"), 5)
        for title, rule in report.CATEGORY_TEXT.values():
            self.assertIn(title, html)

    def test_full_record_and_events_decode_exactly(self):
        data = self._collect()
        for pair in data.games:
            for role, analytics in zip(("stage2", "stage3"), pair):
                record, events = self.records[role, analytics.record.game_index]
                self.assertEqual(analytics.record, record)
                self.assertEqual(tuple(item.event for item in analytics.actions), events)
                self.assertEqual([item.event.action_index for item in analytics.actions], [0, 1, 2, 3])
                self.assertEqual([item.event.action_type for item in analytics.actions], [Action.OPEN, Action.FLAG, Action.CHORD, Action.OPEN])
                self.assertIsNone(analytics.actions[0].event.decision_compute_ns)
                self.assertEqual(analytics.actions[2].event.decision_compute_ns, 0)
                guess = analytics.actions[-1].event
                self.assertIsInstance(guess.target_mine_probability, Fraction)
                self.assertEqual(guess.target_mine_probability, Fraction(10**100 + 1, 3 * 10**100))
                self.assertEqual(guess.minimum_available_mine_probability, Fraction(1, 3))
                self.assertEqual(guess.selection_candidate_count, None if role == "stage3" else 4)
                self.assertEqual(analytics.actions[1].event.inference_category, InferenceCategory.LOCAL_DETERMINISTIC)
                self.assertEqual(analytics.actions[2].event.inference_category, InferenceCategory.GLOBAL_CERTAINTY)

    def test_unknown_persisted_enum_fails_closed(self):
        for value in (True, 99, "1", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                report._decode_enum(value, report._ACTIONS)

    def test_selected_timeline_delta_matches_g4_exactly(self):
        data = self._collect()
        deltas = dict(self.comparison["primary"]["paired_deltas_us"])
        for left, right in data.games:
            for analytics in (left, right):
                reconstructed = report.modeled.reconstruct_game(
                    analytics.record, tuple(item.event for item in analytics.actions),
                    width=30, height=16, evaluation=self.evaluation,
                )
                self.assertEqual(analytics.total_modeled_us, reconstructed.total_modeled_us)
            if left.record.game_index in deltas:
                self.assertEqual(right.total_modeled_us - left.total_modeled_us, deltas[left.record.game_index])

    def test_selected_ww_delta_disagreement_fails(self):
        # Preserve G4 internal sum but make a selected game's physical stream differ.
        self._edit_db("stage3", "UPDATE action_events SET x=5 WHERE game_id=? AND action_index=3", (self.game_ids["stage3", 0],))
        with self.assertRaisesRegex(ValueError, "timeline/G4 delta mismatch"):
            self._collect()

    def test_selected_missing_action_and_summary_disagreement_fail(self):
        with closing(repository.connect_database(self.paths["stage2"])) as connection:
            run = report.statistics.list_benchmark_runs(connection)[0]
            summary = report._load_summaries(connection, run.run_id)[0]
            connection.execute("UPDATE games SET compute_time_total_ns=19 WHERE game_index=0")
            with self.assertRaisesRegex(ValueError, "compute_time_total_ns"):
                report._load_game(connection, run, 0, summary, self.evaluation)
            connection.execute("DELETE FROM action_events WHERE game_id=? AND action_index=2", (self.game_ids["stage2", 0],))
            with self.assertRaisesRegex(ValueError, "row count"):
                report._load_game(connection, run, 0, summary, self.evaluation)

    def test_report_provenance_labels_and_independent_curves(self):
        data = self._collect()
        html = report.render_report(data, {"git_head": "synthetic-head", "git_dirty": True, "report_script_sha256": "synthetic-script"})
        for text in (
            "deterministically selected category exemplars", "NOT a statistically representative sample",
            "Equal action counts do NOT imply equal board state or progress", "not a shared execution clock",
            "(0,0) curve origin is not an action/event", "persisted action_index i maps to i+1",
            "Stage-2 and Stage-3 compute timing scopes/environments differ", "unavailable (None)",
            "FLAG exposure is not recoverable savings", "adjacency is not causal payoff",
            "Non-WW: both modeled totals are descriptive costs through termination", "No paired speed-to-win benefit",
            "synthetic-head", "synthetic-script", "first_click_policy", "telemetry_schema_version",
            "physical_profile_sha256", "timing_table_sha256", "Exact recorded-action table",
        ):
            self.assertIn(text, html)
        for source in data.sources:
            self.assertIn(source.sha256, html)
            self.assertIn(str(source.path), html)
        inspector = DocumentInspector()
        inspector.feed(html)
        self.assertEqual(inspector.svg_count, 4 * len(data.games))
        self.assertEqual(inspector.scripts, 0)
        self.assertEqual(inspector.external, [])
        self.assertNotIn("url(", html)
        self.assertIn("100000000000000000000000000000", html)

    def test_report_explains_posthoc_and_missing_native_evidence(self):
        html = report.render_report(self._collect(), {})
        for text in (
            "Both solver timelines in this report use post-hoc Model C evaluation of persisted executed action targets",
            "Stage-2 historical telemetry did not natively declare Model C",
            "Stage-3 collection declared frozen Model C and historically checked its native total",
            "reduced persisted Stage-3 events used here contain neither native per-action modeled_action_us nor cursor_before fields",
            "displayed Stage-3 timeline is therefore also reconstructed post-hoc from persisted actions under the authenticated frozen Model C",
            "does not display retained native Stage-3 action costs",
            "Stage-2 decision_compute_ns covers decision analysis",
            "Stage-3 decision_compute_ns covers analysis plus planning",
            "compute timing scopes/environments differ in the historical runs",
            "no cross-stage compute-speed winner is inferred",
            "On a recorded Stage-2 probability-guess event, selection_candidate_count is the exact-minimum-risk tie multiplicity / final selector pool size",
            "Official Stage-3 candidate count is unavailable, including on guesses",
            "missing Stage-3 candidate counts are never reconstructed",
            "Persisted inputs do not retain native cursor_before, native per-action modeled_action_us, Replay timestamps, full probability coordinate maps or chosen plans",
            "none is fabricated as native evidence",
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)
        self.assertNotIn("Stage-2 Model C evaluation is post-hoc; Stage-3 declares the same frozen model", html)

    def test_html_escaping_all_dynamic_text(self):
        data = self._collect()
        attack = '<script src="bad">&evil</script>'
        html = report.render_report(data, {attack: attack})
        self.assertNotIn(attack, html)
        self.assertIn("&lt;script src=&quot;bad&quot;&gt;&amp;evil&lt;/script&gt;", html)
        self.assertNotIn("<script", html)
        self.assertIn("&lt;bad&gt;", report._svg(((0, 0), (1, 12)), "<bad>", "<us>"))

    def test_svg_ticks_origin_and_no_fabricated_action(self):
        data = self._collect()
        analytics = data.games[0][0]
        svg = report._svg(analytics.cumulative_modeled_curve, "cost", "us")
        self.assertIn('points="100,240 ', svg)
        self.assertIn(f'>{analytics.total_modeled_us}</text>', svg)
        self.assertIn('>4</text>', svg)
        self.assertEqual(len(analytics.actions), 4)
        self.assertEqual(analytics.actions[0].completed_action_count, 1)
        self.assertEqual(len(analytics.cumulative_modeled_curve), 5)
        self.assertEqual(svg, report._svg(analytics.cumulative_modeled_curve, "cost", "us"))

    def test_top_five_exact_tie_order_and_null_filter(self):
        analytics = self._collect().games[0][0]
        template = analytics.actions[1]
        actions = tuple(replace(template, event=replace(template.event, action_index=index, decision_compute_ns=0), modeled_action_us=7,
                                dx=2, dy=3) for index in (8, 3, 1, 9, 7, 0, 4))
        for metric in (lambda item: item.modeled_action_us, lambda item: item.squared_displacement,
                       lambda item: item.event.decision_compute_ns):
            self.assertEqual([item.completed_action_count for item in report._top_five(actions, metric)], [1, 2, 4, 5, 8])
        ranked = report._top_five((analytics.actions[0], *actions), lambda item: item.event.decision_compute_ns)
        self.assertTrue(all(item.event.decision_compute_ns == 0 for item in ranked))

    def test_diagnostics_certainty_flags_chords_and_guesses(self):
        analytics = self._collect().games[0][0]
        html = report._run_html(analytics, "Stage 2")
        flag_cost = analytics.actions[1].modeled_action_us
        self.assertIn(f"<td>1</td><td>{flag_cost}</td><td>1</td><td>3</td>", html)
        self.assertIn("All recorded probability-guess events (1)", html)
        self.assertIn("<td>1/3</td><td>4</td>", html)

    def test_fresh_output_collision_refused_without_overwrite(self):
        directory = self.root / "reports" / "unique"
        path = report._publish("first", directory)
        with self.assertRaises(FileExistsError):
            report._publish("second", directory)
        self.assertEqual(path.read_text(encoding="utf-8"), "first")

    def test_sources_unchanged_and_connections_closed_before_publish(self):
        before = report._authenticate_sources(self.paths)
        opened = []
        opener = repository.connect_database_readonly
        publisher = report._publish
        output_dir = self.root / "report-run"
        def open_recorded(*args, **kwargs):
            connection = opener(*args, **kwargs)
            opened.append(connection)
            return connection
        def publish_checked(html, directory):
            for connection in opened:
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute("SELECT 1")
            self.assertEqual(report._authenticate_sources(self.paths), before)
            return publisher(html, directory)
        with patch.object(repository, "connect_database_readonly", side_effect=open_recorded), \
                patch.object(report, "_publish", side_effect=publish_checked), \
                patch.object(report, "_generation_provenance", return_value={"synthetic": True}):
            data, path = report.generate_report(self.paths, output_dir)
        self.assertGreater(path.stat().st_size, 0)
        self.assertEqual(report._authenticate_sources(self.paths), before)
        self.assertEqual(set(output_dir.iterdir()), {path})

    def test_stability_failure_blocks_publication(self):
        output = self.root / "must-not-exist"
        with patch.object(report, "_verify_stability", side_effect=ValueError("changed")), \
                patch.object(report, "_publish") as publish, self.assertRaisesRegex(ValueError, "changed"):
            report.generate_report(self.paths, output)
        publish.assert_not_called()
        self.assertFalse(output.exists())

    def test_stability_detects_modified_source_and_new_sidecar(self):
        before = report._authenticate_sources(self.paths)
        self.paths["comparison"].write_bytes(self.paths["comparison"].read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "stability"):
            report._verify_stability(before)
        sidecar = Path(str(self.paths["stage2"]) + "-shm")
        sidecar.write_bytes(b"synthetic")
        with self.assertRaisesRegex(ValueError, "stability"):
            report._verify_stability(before)

    def test_validation_failure_never_creates_report_directory(self):
        self.hashes["result"] = "0" * 64
        directory = self.root / "absent-report"
        with self.assertRaises(ValueError):
            report.generate_report(self.paths, directory)
        self.assertFalse(directory.exists())

    def test_script_has_only_readonly_domain_dependencies(self):
        source = Path(report.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
        forbidden = {"benchmark_comparison", "benchmark_board", "benchmark_runner", "stage3_benchmark_runner",
                     "simple_runner", "simple_decision", "stage3_runner", "stage3_planner", "stage3_execution", "sqlite3"}
        self.assertFalse(imports & forbidden)
        engine_import = next(node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module == "core_engine")
        self.assertEqual({alias.name for alias in engine_import.names}, {"Action", "GameStatus"})
        calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(calls & {"connect_database", "connect_database_for_continuation", "initialize_schema", "step", "run_stage3"})
        with patch.object(repository, "connect_database", side_effect=AssertionError("writer")), \
                patch.object(schema, "initialize_schema", side_effect=AssertionError("schema write")):
            self._collect()


if __name__ == "__main__":
    unittest.main()
