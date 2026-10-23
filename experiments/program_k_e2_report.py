"""Pure I3 renderers for an already computed immutable E2 analysis result.

The JSON field map is explicit and versioned. HTML displays that same map; it
does not classify gates, rebuild records, rerun analysis, or write a report.
"""

from fractions import Fraction
from html import escape
import json

from experiments import program_k_e2_analysis as analysis


SCHEMA = "program_k_e2_analysis"
SCHEMA_VERSION = 1
NONCLAIMS = (
    "Model C is not CPU/human wall time.",
    "Compute is not added into the primary Model C score.",
    "No production/Gate-P claim is made by this analysis.",
)


class ReportError(ValueError):
    """The supplied value is not an exact supported analysis result."""


def _fraction(value):
    if value is None:
        return None
    if type(value) is not Fraction:
        raise ReportError("Expected an exact Fraction or None.")
    return {"numerator": value.numerator, "denominator": value.denominator}


def _median(value):
    if type(value) is int or value is None:
        return value
    return _fraction(value)


def _distribution(value):
    return {
        "count": value.count,
        "minimum": value.minimum,
        "maximum": value.maximum,
        "mean": _fraction(value.mean),
        "median": _median(value.median),
        "p90": value.p90,
        "p95": value.p95,
        "p99": value.p99,
    }


def _diagnostics(value):
    return {
        "distribution": _distribution(value.distribution),
        "faster": value.faster,
        "slower": value.slower,
        "ties": value.ties,
        "maximum_slowdown": value.maximum_slowdown,
        "worst": [{"position": item.position, "game_index": item.game_index,
                   "fingerprint": item.fingerprint, "delta_us": item.delta_us,
                   "diagnosis": item.diagnosis} for item in value.worst],
    }


def _bootstrap_metric(value):
    return {
        "interval": None if value.interval is None else {
            "lower": _fraction(value.interval[0]), "upper": _fraction(value.interval[1])},
        "defined_count": value.defined_count,
        "undefined_count": value.undefined_count,
        "zero_eligible_count": value.zero_eligible_count,
        "missing_data_count": value.missing_data_count,
    }


def _model(result):
    if type(result) is not analysis.AnalysisResult:
        raise ReportError("Expected the exact immutable AnalysisResult class.")
    try:
        # Structural validation only: no classifier, bootstrap or row analysis.
        analysis.AnalysisResult.__post_init__(result)
    except (ValueError, TypeError, AttributeError) as error:
        raise ReportError("Malformed analysis result.") from error
    outcomes, primary = result.outcomes, result.primary
    g5, g8, g9, boot = result.g5, result.g8, result.g9, result.bootstrap
    overall = result.overall
    return {
        "schema": SCHEMA,
        "version": SCHEMA_VERSION,
        "n": result.n,
        "concurrency": result.concurrency,
        "outcomes": {"WW": outcomes.ww, "WL": outcomes.wl, "LW": outcomes.lw,
                     "LL": outcomes.ll, "ERROR": outcomes.error, "INCOMPLETE": outcomes.incomplete},
        "primary": {"n_w": primary.n_w, "s_c": primary.s_c, "s_k": primary.s_k,
                    "total_delta": primary.total_delta, "ratio": _fraction(primary.ratio),
                    "reduction": _fraction(primary.reduction),
                    "mean_saving_us": _fraction(primary.mean_saving_us)},
        "ww_diagnostics": _diagnostics(result.ww_diagnostics),
        "bootstrap": {"replicates": boot.replicates, "accepted_draws": boot.accepted_draws,
                      "rejected_draws": boot.rejected_draws, "seed_hex": boot.seed_hex,
                      "g5": _bootstrap_metric(boot.g5), "g8": _bootstrap_metric(boot.g8),
                      "g9": _bootstrap_metric(boot.g9)},
        "g5": {"exposure_count": g5.exposure_count,
               "exposure_fraction": _fraction(g5.exposure_fraction),
               "diagnostic_setup_chord_flags": g5.diagnostic_setup_chord_flags,
               "qualifying_fallback_flags": g5.qualifying_fallback_flags,
               "qualifying_flag_to_open_setup_flags": g5.qualifying_flag_to_open_setup_flags,
               "exposed_ww_count": g5.exposed_ww_count,
               "mean_saving_us": _fraction(g5.mean_saving_us),
               "diagnostics": _diagnostics(g5.diagnostics), "evidence_complete": g5.evidence_complete,
               "status": g5.status.value, "cause": g5.cause.value,
               "bootstrap": _bootstrap_metric(g5.bootstrap)},
        "g8": {"status": g8.status.value, "cause": g8.cause.value, "margin_us": g8.margin_us,
               "bootstrap": _bootstrap_metric(g8.bootstrap)},
        "g9": {"status": g9.status.value, "cause": g9.cause.value, "concurrency": g9.concurrency,
               "pathology": g9.pathology.value,
               "observed_mean_net_headroom_ns": _fraction(g9.observed_mean_net_headroom_ns),
               "missing_compute_rows": g9.missing_compute_rows,
               "control_compute": _distribution(g9.control_compute),
               "kp0_compute": _distribution(g9.kp0_compute),
               "added_compute": _distribution(g9.added_compute),
               "bootstrap": _bootstrap_metric(g9.bootstrap)},
        "overall": None if overall is None else {
            "gates": {gate: status.value for gate, status in overall.gates},
            "implementation_identity_fail": overall.implementation_identity_fail,
            "verdict": overall.verdict.value, "e3_trigger": overall.e3_trigger},
        "nonclaims": list(NONCLAIMS),
        "context": list(result.context),
    }


def render_analysis_json(result):
    """Return canonical UTF-8 JSON bytes; exact rational values stay lossless."""
    return json.dumps(_model(result), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _text(value):
    """Display only the fixed map's primitive or numerator/denominator fields."""
    if value is None:
        return "None (undefined / unavailable)"
    if type(value) is dict:
        return str(value["numerator"]) + "/" + str(value["denominator"])
    if type(value) is bool:
        return "true" if value else "false"
    if value == "NOT_APPLICABLE":
        return "N/A (NOT_APPLICABLE)"
    return str(value)


def _table(headers, rows):
    head = "".join("<th scope=\"col\">" + escape(label, quote=True) + "</th>" for label in headers)
    body = "".join("<tr>" + "".join("<td>" + escape(_text(value), quote=True) + "</td>"
                                  for value in row) + "</tr>" for row in rows)
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + body + "</tbody></table>"


def _values(rows):
    return _table(("Quantity", "Exact value"), rows)


def _distribution_html(value, title):
    return "<h3>" + escape(title, quote=True) + "</h3>" + _values((
        ("Count", value["count"]), ("Minimum", value["minimum"]), ("Maximum", value["maximum"]),
        ("Mean", value["mean"]), ("Median", value["median"]), ("P90", value["p90"]),
        ("P95", value["p95"]), ("P99", value["p99"])))


def _diagnostics_html(value, title):
    parts = ["<h2>" + escape(title, quote=True) + "</h2>",
             "<p>Diagnostic signed delta = K-P0 minus CONTROL Model C, in µs. "
             "Negative means faster; positive means slower. These diagnostics do not set gates.</p>",
             _values((("Faster", value["faster"]), ("Slower", value["slower"]),
                      ("Exact ties", value["ties"]), ("Maximum positive slowdown (µs)", value["maximum_slowdown"]))),
             _distribution_html(value["distribution"], "Signed delta distribution (µs)"),
             "<h3>Diagnostic worst 20: largest delta first</h3>"]
    if value["worst"]:
        parts.append(_table(("Corpus position", "Game index", "Fingerprint", "Delta (µs)", "Diagnosis"),
                            ((item["position"], item["game_index"], item["fingerprint"],
                              item["delta_us"], item["diagnosis"]) for item in value["worst"])))
    else:
        parts.append("<p>Empty (0 observations); worst board identities: None.</p>")
    return "".join(parts)


def _bootstrap_html(metric):
    interval = metric["interval"]
    return _values((("95% interval lower", None if interval is None else interval["lower"]),
                    ("95% interval upper", None if interval is None else interval["upper"]),
                    ("Defined replicates", metric["defined_count"]),
                    ("Undefined replicates", metric["undefined_count"]),
                    ("Zero eligible replicates", metric["zero_eligible_count"]),
                    ("Missing-data replicates", metric["missing_data_count"])))


def render_report_html(result):
    """Return a deterministic standalone static HTML string, without any I/O."""
    model = _model(result)
    primary, g5, g8, g9, boot = (model[key] for key in ("primary", "g5", "g8", "g9", "bootstrap"))
    parts = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
             "<title>Program K E2 aggregate analysis</title>",
             "<style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.5}"
             "table{border-collapse:collapse;margin:1rem 0;max-width:100%}"
             "th,td{border:1px solid #777;padding:.4rem;text-align:left;overflow-wrap:anywhere}"
             "h2{margin-top:2rem}</style></head><body><h1>Program K E2 aggregate analysis</h1>",
             "<p>Schema: " + SCHEMA + "; version: " + str(SCHEMA_VERSION) + ".</p>"]
    parts.extend("<p>" + escape(text, quote=True) + "</p>" for text in model["nonclaims"])
    parts.append(_values((("N", model["n"]), ("Frozen supplied concurrency", model["concurrency"]))))
    parts.extend(("<h2>Outcome accounting</h2>",
                  _values(tuple((key, model["outcomes"][key]) for key in ("WW", "WL", "LW", "LL", "ERROR", "INCOMPLETE"))),
                  "<h2>Primary exact Model C</h2>",
                  _values((("Common-win count", primary["n_w"]), ("CONTROL total (µs)", primary["s_c"]),
                           ("K-P0 total (µs)", primary["s_k"]), ("Total delta (µs)", primary["total_delta"]),
                           ("Primary ratio of totals", primary["ratio"]), ("Primary reduction", primary["reduction"]),
                           ("Mean WW saving (µs)", primary["mean_saving_us"]))),
                  _diagnostics_html(model["ww_diagnostics"], "All WW diagnostics"),
                  "<h2>Shared bootstrap</h2>",
                  _values((("Replicates", boot["replicates"]), ("Accepted draws", boot["accepted_draws"]),
                           ("Rejected draws", boot["rejected_draws"]), ("Bootstrap seed SHA-256", boot["seed_hex"]))),
                  "<h2>G5 productive-FLAG regression gate</h2>",
                  _values((("Status", g5["status"]), ("Cause", g5["cause"]),
                           ("Required evidence complete", g5["evidence_complete"]),
                           ("Exposed boards", g5["exposure_count"]), ("Exposure fraction", g5["exposure_fraction"]),
                           ("Exposed WW count", g5["exposed_ww_count"]),
                           ("Qualifying CONTROL_FALLBACK_FLAG", g5["qualifying_fallback_flags"]),
                           ("Qualifying CONTROL_FLAG_TO_OPEN_SETUP", g5["qualifying_flag_to_open_setup_flags"]),
                           ("Mean exposed-WW saving (µs)", g5["mean_saving_us"]))),
                  "<h3>Separate diagnostic setup-CHORD count (does not qualify exposure)</h3>",
                  _values((("Diagnostic CONTROL_SETUP_CHORD_FLAG", g5["diagnostic_setup_chord_flags"]),)),
                  _bootstrap_html(g5["bootstrap"]),
                  _diagnostics_html(g5["diagnostics"], "G5-exposed WW diagnostics"),
                  "<h2>G8 effectiveness gate</h2>",
                  _values((("Status", g8["status"]), ("Cause", g8["cause"]),
                           ("Practical margin (µs per WW board)", format(g8["margin_us"], ",") + " µs"))),
                  _bootstrap_html(g8["bootstrap"]),
                  "<h2>G9 compute/resource gate</h2>",
                  "<p>Compute distributions describe supplied WW per-board comparable compute totals. "
                  "Individual decision-span distributions cannot be reconstructed from these compact rows.</p>",
                  _values((("Status", g9["status"]), ("Cause", g9["cause"]),
                           ("Frozen supplied concurrency", g9["concurrency"]),
                           ("Pathology disposition", g9["pathology"]),
                           ("Mean net headroom (ns)", g9["observed_mean_net_headroom_ns"]),
                           ("WW rows missing comparable compute", g9["missing_compute_rows"]))),
                  _bootstrap_html(g9["bootstrap"]),
                  _distribution_html(g9["control_compute"], "CONTROL comparable compute totals (ns per WW board)"),
                  _distribution_html(g9["kp0_compute"], "K-P0 comparable compute totals (ns per WW board)"),
                  _distribution_html(g9["added_compute"], "Added comparable compute totals (ns per WW board)"),
                  "<h2>Supplied overall qualification</h2>"))
    overall = model["overall"]
    if overall is None:
        parts.append("<p>Gate set, overall verdict, and E3 trigger: None (not supplied).</p>")
    else:
        parts.extend((_values(tuple(("G" + str(i), overall["gates"]["G" + str(i)]) for i in range(1, 11))),
                      _values((("Implementation identity fail", overall["implementation_identity_fail"]),
                               ("Overall verdict", overall["verdict"]), ("Prospective E3 trigger", overall["e3_trigger"]))),
                      "<p>The E3 trigger is descriptive and authorizes no execution.</p>"))
    parts.append("<h2>Supplied context</h2>")
    if model["context"]:
        parts.extend("<p>" + escape(text, quote=True) + "</p>" for text in model["context"])
    else:
        parts.append("<p>None (no supplied context).</p>")
    parts.append("</body></html>")
    return "".join(parts)
