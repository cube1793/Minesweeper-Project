"""I3 render-only qualification; all analysis inputs and identities are synthetic."""

import ast
import builtins
from contextlib import ExitStack
from dataclasses import replace
from fractions import Fraction
from html.parser import HTMLParser
import inspect
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

from experiments import program_k_e2_analysis as analysis
from experiments import program_k_e2_records as records
from experiments import program_k_e2_report as report


_SEED = b"\x91" * 32
_DIGEST = b"\x52" * 32
_UNTRUSTED = '<script>alert("supplied")</script> & <img src="remote">'


def _row(position, index, control=300000, kp0=100000, *, outcome=records.Outcome.WIN,
         exposure=(0, 0, 0), compute=(10, 11), diagnosis="SYNTHETIC"):
    board = records.BoardIdentity(index, "synthetic-fingerprint-" + str(index),
                                  2, 2, 1, (0, 0), "supplied-generator", "supplied-spec")
    pair = records.PairComparisonRecord(board, outcome, outcome, records.P3Status.PASS,
                                        kp0 - control if outcome is records.Outcome.WIN else None,
                                        records.G5ExposureSummary(*exposure), diagnosis)
    return analysis.BoardAnalysisRow(position, pair, control, kp0, *compute)


def _analyze(rows, **kwargs):
    return analysis.analyze_effectiveness(rows, protocol_seed=_SEED, corpus_digest=_DIGEST,
                                          concurrency=3, **kwargs)


def _with_overall(result, changes=None, identity_fail=False):
    gates = {"G" + str(i): analysis.GateStatus.PASS for i in range(1, 11)}
    gates.update(G5=result.g5.status, G8=result.g8.status, G9=result.g9.status)
    gates.update({} if changes is None else changes)
    verdict = analysis.classify_overall(gates, implementation_identity_fail=identity_fail)
    e3 = analysis.e3_trigger(gates, implementation_identity_fail=identity_fail, g8_cause=result.g8.cause)
    overall = analysis.OverallAssessment(tuple(("G" + str(i), gates["G" + str(i)]) for i in range(1, 11)),
                                          identity_fail, verdict, e3)
    return replace(result, overall=overall)


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mixed = _analyze((
            _row(0, 102, exposure=(7, 2, 0)),
            _row(1, 101, kp0=100001, exposure=(11, 0, 3)),
            _row(2, 103, kp0=100004, exposure=(13, 0, 0), diagnosis=_UNTRUSTED),
        ), context=(_UNTRUSTED, "Supplied synthetic context: 한글"))
        cls.mixed_overall = _with_overall(cls.mixed)
        cls.empty = _analyze((_row(0, 104, 9, 8, outcome=records.Outcome.LOSS,
                                   exposure=(2, 0, 0), compute=(None, None)),))
        cls.margin = _with_overall(_analyze((_row(0, 105, 126006, 1, compute=(0, 0)),)))
        cls.missing_compute = _analyze((_row(0, 106, 10, 9, compute=(None, 0)),))
        cls.passing = _with_overall(_analyze((_row(0, 107, 300000, 1, exposure=(0, 1, 0)),)))

    def test_canonical_json_is_deterministic_compact_sorted_and_versioned(self):
        first = report.render_analysis_json(self.mixed_overall)
        self.assertIs(type(first), bytes)
        self.assertEqual(first, report.render_analysis_json(self.mixed_overall))
        model = json.loads(first)
        self.assertEqual((model["schema"], model["version"]), ("program_k_e2_analysis", 1))
        self.assertEqual(first, json.dumps(model, sort_keys=True, separators=(",", ":"),
                                           ensure_ascii=True, allow_nan=False).encode("utf-8"))
        self.assertFalse(first.endswith(b"\n"))
        self.assertEqual(model["n"], 3)
        self.assertEqual(model["concurrency"], 3)
        self.assertEqual(model["outcomes"], {"WW": 3, "WL": 0, "LW": 0, "LL": 0, "ERROR": 0, "INCOMPLETE": 0})

    def test_fractions_are_lossless_numerator_denominator_objects(self):
        model = json.loads(report.render_analysis_json(self.mixed))
        expected_ratio = Fraction(300005, 900000)
        self.assertEqual(model["primary"]["ratio"],
                         {"numerator": expected_ratio.numerator, "denominator": expected_ratio.denominator})
        self.assertEqual(model["primary"]["mean_saving_us"], {"numerator": 599995, "denominator": 3})
        self.assertEqual(model["g5"]["exposure_fraction"], {"numerator": 2, "denominator": 3})
        for key in ("ratio", "reduction", "mean_saving_us"):
            value = model["primary"][key]
            self.assertEqual(Fraction(value["numerator"], value["denominator"]), getattr(self.mixed.primary, key))

    def test_no_float_or_nonfinite_authority_anywhere_in_json(self):
        def forbidden(token):
            raise AssertionError("Floating-point/nonfinite JSON token: " + token)
        for result in (self.mixed, self.empty, self.margin, self.missing_compute):
            raw = report.render_analysis_json(result)
            model = json.loads(raw, parse_float=forbidden, parse_constant=forbidden)
            def visit(value):
                self.assertIn(type(value), (dict, list, str, int, bool, type(None)))
                if type(value) is dict:
                    for item in value.values():
                        visit(item)
                elif type(value) is list:
                    for item in value:
                        visit(item)
            visit(model)

    def test_null_and_empty_results_are_explicit(self):
        model = json.loads(report.render_analysis_json(self.empty))
        for key in ("ratio", "reduction", "mean_saving_us"):
            self.assertIsNone(model["primary"][key])
        self.assertIsNone(model["g8"]["bootstrap"]["interval"])
        self.assertIsNone(model["overall"])
        self.assertEqual(model["context"], [])
        self.assertEqual(model["ww_diagnostics"]["worst"], [])
        self.assertIsNone(model["ww_diagnostics"]["maximum_slowdown"])
        html = report.render_report_html(self.empty)
        self.assertIn("None (undefined / unavailable)", html)
        self.assertIn("Empty (0 observations)", html)
        self.assertIn("None (not supplied)", html)

    def test_html_is_deterministic_static_and_standalone(self):
        html = report.render_report_html(self.mixed_overall)
        self.assertIs(type(html), str)
        self.assertEqual(html, report.render_report_html(self.mixed_overall))
        self.assertEqual(html.encode("utf-8"), report.render_report_html(self.mixed_overall).encode("utf-8"))
        self.assertTrue(html.startswith("<!doctype html>"))
        parser = _Tags()
        parser.feed(html)
        self.assertFalse(set(parser.tags).intersection({"script", "link", "img", "iframe", "object", "embed"}))
        self.assertFalse({key for key, value in parser.attributes}.intersection({"src", "href", "srcset"}))
        self.assertNotIn("<script", html.lower())

    def test_html_escapes_supplied_diagnosis_context_and_fingerprint(self):
        html = report.render_report_html(self.mixed)
        escaped = '&lt;script&gt;alert(&quot;supplied&quot;)&lt;/script&gt; &amp; &lt;img src=&quot;remote&quot;&gt;'
        self.assertEqual(html.count(escaped), 2)  # one worst-board diagnosis and one supplied context
        self.assertNotIn(_UNTRUSTED, html)
        worst = self.mixed.ww_diagnostics.worst
        changed = replace(self.mixed.ww_diagnostics, worst=(replace(worst[0], fingerprint='<b id="x">'),) + worst[1:])
        modified = replace(self.mixed, ww_diagnostics=changed)
        self.assertIn("&lt;b id=&quot;x&quot;&gt;", report.render_report_html(modified))
        self.assertEqual(json.loads(report.render_analysis_json(self.mixed))["context"][0], _UNTRUSTED)

    def test_html_displays_exact_fractions_without_decimal_conversion(self):
        html = report.render_report_html(self.mixed)
        self.assertIn("599995/3", html)
        self.assertIn("2/3", html)
        self.assertIn("60001/180000", html)
        self.assertNotIn("0.666666", html)

    def test_g5_qualifying_categories_are_separate_from_diagnostic_setup_chord(self):
        model = json.loads(report.render_analysis_json(self.mixed))
        self.assertEqual(model["g5"]["diagnostic_setup_chord_flags"], 31)
        self.assertEqual(model["g5"]["qualifying_fallback_flags"], 2)
        self.assertEqual(model["g5"]["qualifying_flag_to_open_setup_flags"], 3)
        html = report.render_report_html(self.mixed)
        for label in ("Qualifying CONTROL_FALLBACK_FLAG", "Qualifying CONTROL_FLAG_TO_OPEN_SETUP",
                      "Separate diagnostic setup-CHORD count (does not qualify exposure)",
                      "Diagnostic CONTROL_SETUP_CHORD_FLAG"):
            self.assertIn(label, html)
        self.assertIn("N/A (NOT_APPLICABLE)", report.render_report_html(self.empty))

    def test_margin_concurrency_compute_units_and_nonclaims_visible(self):
        html = report.render_report_html(self.margin)
        self.assertIn("126,005 µs", html)
        self.assertIn("Frozen supplied concurrency</td><td>3", html)
        self.assertIn("WW per-board comparable compute totals", html)
        for statement in report.NONCLAIMS:
            self.assertIn(statement, html)
        model = json.loads(report.render_analysis_json(self.margin))
        self.assertEqual(model["g8"]["margin_us"], 126005)
        self.assertEqual(model["g9"]["concurrency"], 3)
        self.assertEqual(model["nonclaims"], list(report.NONCLAIMS))

    def test_worst_identities_preserve_analysis_order_in_both_renderings(self):
        model = json.loads(report.render_analysis_json(self.mixed))
        self.assertEqual(tuple((row["game_index"], row["position"]) for row in model["ww_diagnostics"]["worst"]),
                         ((103, 2), (101, 1), (102, 0)))
        html = report.render_report_html(self.mixed)
        self.assertLess(html.index("synthetic-fingerprint-103"), html.index("synthetic-fingerprint-101"))
        self.assertLess(html.index("synthetic-fingerprint-101"), html.index("synthetic-fingerprint-102"))
        self.assertIn("Diagnostic worst 20", html)

    def test_every_gate_status_and_overall_verdict_are_textual(self):
        variants = (
            (self.mixed_overall, "RESEARCH_DEFER"),
            (_with_overall(self.mixed, {"G1": analysis.GateStatus.FAIL}), "RESEARCH_FAIL"),
            (_with_overall(self.mixed, {"G1": analysis.GateStatus.INCOMPLETE}), "INCOMPLETE"),
            (_with_overall(self.mixed, identity_fail=True), "IMPLEMENTATION_IDENTITY_FAIL"),
            (self.passing, "RESEARCH_PASS"),
        )
        for result, verdict in variants:
            model = json.loads(report.render_analysis_json(result))
            self.assertEqual(model["overall"]["verdict"], verdict)
            html = report.render_report_html(result)
            self.assertIn("Overall verdict</td><td>" + verdict, html)
            for name, status in result.overall.gates:
                self.assertIn("<td>" + name + "</td><td>" + status.value, html)
        self.assertIn("INCOMPLETE", report.render_report_html(self.missing_compute))
        self.assertEqual(json.loads(report.render_analysis_json(self.margin))["overall"]["e3_trigger"], True)
        self.assertIn("Prospective E3 trigger</td><td>true", report.render_report_html(self.margin))
        self.assertIn("authorizes no execution", report.render_report_html(self.margin))

    def test_json_discloses_shared_bootstrap_undefined_and_compute_information(self):
        model = json.loads(report.render_analysis_json(self.empty))
        self.assertEqual(model["bootstrap"]["replicates"], 10000)
        self.assertEqual(model["bootstrap"]["accepted_draws"], 10000)
        for gate in ("g5", "g8", "g9"):
            self.assertEqual(model[gate]["bootstrap"], model["bootstrap"][gate])
            self.assertEqual(model[gate]["bootstrap"]["undefined_count"], 10000)
        for key in ("control_compute", "kp0_compute", "added_compute"):
            self.assertEqual(model["g9"][key]["count"], 0)
            self.assertIsNone(model["g9"][key]["mean"])

    def test_renderers_reject_wrong_class_subclass_and_mutated_inexact_value(self):
        class Subclass(analysis.AnalysisResult):
            pass
        subclass = object.__new__(Subclass)
        for value in (None, {}, self.mixed.primary, subclass):
            for renderer in (report.render_analysis_json, report.render_report_html):
                with self.assertRaises(report.ReportError):
                    renderer(value)
        for invalid in (True, 3.0, float("nan"), float("inf")):
            corrupted = replace(self.mixed)
            object.__setattr__(corrupted, "n", invalid)
            with self.assertRaises(report.ReportError):
                report.render_analysis_json(corrupted)

    def test_rendering_never_reanalyzes_or_accesses_filesystem(self):
        # Fixture analysis has finished. Scalar gate invariant checks are allowed
        # through AnalysisResult validation; row analysis/resampling remain blocked.
        blocked = ((builtins, "open"), (io, "open"), (os, "open"), (os, "stat"), (os, "listdir"),
                   (os, "scandir"), (Path, "open"), (Path, "read_bytes"), (Path, "write_bytes"),
                   (Path, "read_text"), (Path, "write_text"), (subprocess, "Popen"), (subprocess, "run"))
        with ExitStack() as stack:
            for owner, name in blocked:
                stack.enter_context(patch.object(owner, name, side_effect=AssertionError("renderer I/O")))
            for name in ("analyze_effectiveness", "bootstrap_seed", "_shared_bootstrap",
                         "uniform_position", "splitmix64_step", "classify_overall", "e3_trigger"):
                stack.enter_context(patch.object(analysis, name, side_effect=AssertionError("renderer recomputation")))
            self.assertTrue(report.render_analysis_json(self.mixed_overall))
            self.assertTrue(report.render_report_html(self.mixed_overall))

    def test_both_renderers_reject_corrupted_embedded_gate_claims(self):
        cases = ((self.passing, "g5", {"status": analysis.GateStatus.FAIL}),
                 (self.passing, "g5", {"cause": analysis.G5Cause.MISSING_REQUIRED_DATA}),
                 (self.passing, "g5", {"evidence_complete": False}),
                 (self.margin, "g5", {"evidence_complete": False}),
                 (self.margin, "g8", {"status": analysis.GateStatus.PASS}),
                 (self.passing, "g8", {"cause": analysis.G8Cause.MARGIN_OVERLAP}),
                 (self.missing_compute, "g9", {"status": analysis.GateStatus.PASS,
                                               "cause": analysis.G9Cause.NONE}),
                 (self.passing, "g9", {"cause": analysis.G9Cause.INHERENT_PATHOLOGY}))
        for original, name, changes in cases:
            # Copy the gate before bypassing frozen ownership, preserving fixtures.
            # No overall record: rejection must come from embedded gate invariants.
            corrupted = replace(original, overall=None)
            gate = replace(getattr(corrupted, name))
            object.__setattr__(corrupted, name, gate)
            for field, value in changes.items():
                object.__setattr__(gate, field, value)
            for renderer in (report.render_analysis_json, report.render_report_html):
                with self.subTest(gate=name, changes=changes, renderer=renderer.__name__):
                    with self.assertRaises(report.ReportError):
                        renderer(corrupted)

    def test_both_renderers_reject_corrupted_g9_quantitative_summary(self):
        for original in (self.passing, self.empty, self.missing_compute):
            for renderer in (report.render_analysis_json, report.render_report_html):
                with self.subTest(n_w=original.primary.n_w,
                                  missing=original.g9.missing_compute_rows, renderer=renderer.__name__):
                    expected = renderer(original)
                    corrupted = replace(original, overall=None)
                    g9 = replace(corrupted.g9)
                    object.__setattr__(g9, "observed_mean_net_headroom_ns", Fraction(123, 7))
                    object.__setattr__(corrupted, "g9", g9)
                    with self.assertRaises(report.ReportError):
                        renderer(corrupted)
                    self.assertEqual(renderer(original), expected)

    def test_ast_boundary_has_no_store_execution_dynamic_encoding_or_analysis_calls(self):
        source = inspect.getsource(report)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(name.name.split(".")[0] in sys.stdlib_module_names for name in node.names))
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                if node.module == "experiments":
                    self.assertEqual(tuple(name.name for name in node.names), ("program_k_e2_analysis",))
                else:
                    self.assertIn(node.module.split(".")[0], sys.stdlib_module_names)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"open", "eval", "exec", "__import__", "asdict", "getattr"})
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, {"analyze_effectiveness", "classify_overall", "e3_trigger",
                                                     "bootstrap_seed", "splitmix64", "read", "write"})
        self.assertNotIn("__dict__", source)

    def test_import_executes_with_io_and_analysis_calls_blocked(self):
        name = "_e2_i3_report_import_probe"
        source = compile(inspect.getsource(report), report.__file__, "exec")
        probe = types.ModuleType(name)
        with patch.dict(sys.modules, {name: probe}), ExitStack() as stack:
            for owner, attribute in ((builtins, "open"), (io, "open"), (os, "open"), (os, "getcwd"),
                                     (Path, "read_bytes"), (Path, "write_bytes"), (subprocess, "Popen"),
                                     (analysis, "analyze_effectiveness"), (analysis, "bootstrap_seed")):
                stack.enter_context(patch.object(owner, attribute, side_effect=AssertionError("import side effect")))
            exec(source, probe.__dict__)
        self.assertEqual(probe.NONCLAIMS, report.NONCLAIMS)


if __name__ == "__main__":
    unittest.main()
