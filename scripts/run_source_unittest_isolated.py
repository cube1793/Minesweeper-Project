"""Source regression: verified discovery, fresh processes, exact receipts.

The coordinator never imports tests. Irreversible hooks and Qt/global state
belong to a module child, not to subsequent tests or process launches.
"""
import argparse
from collections import Counter
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PYTHON = Path(r"C:\venvs\minesweeper\Scripts\python.exe")
ISOLATED_CLASS = "tests.test_program_k_harness.ProgramKSlice7SupervisorTests"
STATUSES = ("pass", "failure", "error", "skip", "expected_failure",
            "unexpected_success", "not_started", "unfinished")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2)
        stream.write("\n")


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def test_ids(tests):
    ids = [test.id() for test in tests]
    require(all(isinstance(item, str) and item for item in ids), "Invalid test ID")
    require(len(ids) == len(set(ids)), "Duplicate test IDs")
    require(not any(isinstance(test, unittest.loader._FailedTest) for test in tests),
            "Unittest loading produced an error placeholder")
    return ids


def normalize_discovered(tests):
    """Collapse imported aliases only after checking the actual test objects."""
    kept, seen, duplicates = [], {}, []
    for ordinal, test in enumerate(tests):
        identity = test.id()
        if identity not in seen:
            seen[identity] = (ordinal, test)
            kept.append(test)
            continue
        first_ordinal, first = seen[identity]
        cls = type(test)
        checks = dict(same_class=cls is type(first),
                      same_method=getattr(cls, test._testMethodName) is
                                  getattr(type(first), first._testMethodName),
                      same_state=vars(first) == vars(test),
                      standard_id=cls.id is unittest.TestCase.id,
                      standard_run=cls.run is unittest.TestCase.run)
        require(all(checks.values()), "Nonidentical duplicate test ID: " + identity)
        source = Path(inspect.getfile(cls)).resolve()
        duplicates.append(dict(id=identity, kept_ordinal=first_ordinal, removed_ordinal=ordinal,
                               checks=checks, source=str(source),
                               source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    test_ids(kept)
    return kept, duplicates


def partition(tests):
    groups = {}
    for test in tests:
        identity = test.id()
        key = ISOLATED_CLASS if identity.rsplit(".", 1)[0] == ISOLATED_CLASS else type(test).__module__
        groups.setdefault(key, []).append(identity)
    ids = [identity for values in groups.values() for identity in values]
    require(Counter(ids) == Counter(test_ids(tests)), "Partitions omit or repeat tests")
    return groups


def discover(output):
    loader = unittest.TestLoader()
    # One canonical package name, rather than both test_x and tests.test_x.
    suite = loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    require(not loader.errors, "Full discovery failed: " + repr(loader.errors))
    raw = list(flatten(suite))
    tests, duplicates = normalize_discovered(raw)
    write_json(output, dict(raw_discovered=len(raw), unique_discovered=len(tests),
               selected_ids=test_ids(tests), duplicates=duplicates, partitions=partition(tests)))


class AccountedResult(unittest.TextTestResult):
    def __init__(self, *args, journal, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal = journal

    def record(self, kind, test, parent_id=None, detail=None):
        row = dict(kind=kind, id=test.id(), parent_id=parent_id, detail=detail)
        self.journal.write(json.dumps(row, ensure_ascii=True) + "\n")
        self.journal.flush()

    def startTest(self, test):
        self.record("start", test)
        super().startTest(test)

    def stopTest(self, test):
        self.record("stop", test)
        super().stopTest(test)

    def addSuccess(self, test):
        self.record("pass", test)
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.record("failure", test, detail=self._exc_info_to_string(err, test))
        super().addFailure(test, err)

    def addError(self, test, err):
        self.record("error", test, detail=self._exc_info_to_string(err, test))
        super().addError(test, err)

    def addSkip(self, test, reason):
        parent = getattr(test, "test_case", None)
        self.record("skip", test, parent_id=parent.id() if parent else None, detail=reason)
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.record("expected_failure", test, detail=self._exc_info_to_string(err, test))
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.record("unexpected_success", test)
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            kind = "failure" if issubclass(err[0], test.failureException) else "error"
            self.record(kind, subtest, parent_id=test.id(), detail=self._exc_info_to_string(err, test))
        super().addSubTest(test, subtest, err)


def make_receipt(ids, records):
    started = [row["id"] for row in records if row["kind"] == "start"]
    stopped = [row["id"] for row in records if row["kind"] == "stop"]
    events = [row for row in records if row["kind"] not in ("start", "stop")]
    by_id = {identity: [] for identity in ids}
    fixtures = []
    for event in events:
        identity = event["parent_id"] or event["id"]
        if identity in by_id:
            by_id[identity].append(event["kind"])
        else:
            fixtures.append(event)
    outcomes = {}
    for identity, kinds in by_id.items():
        if identity not in started:
            status = "not_started"
        elif identity not in stopped:
            status = "unfinished"
        else:
            status = next((kind for kind in ("error", "failure", "unexpected_success",
                                            "expected_failure", "skip", "pass") if kind in kinds), "unfinished")
        outcomes[identity] = status
    counts = {status: list(outcomes.values()).count(status) for status in STATUSES}
    counts.update(selected=len(ids), run=len(started), completed=len(stopped),
                  failure_events=sum(row["kind"] == "failure" for row in events),
                  error_events=sum(row["kind"] == "error" for row in events),
                  skip_events=sum(row["kind"] == "skip" for row in events),
                  fixture_errors=sum(row["kind"] == "error" for row in fixtures))
    return dict(selected_ids=ids, started_ids=started, stopped_ids=stopped,
                outcomes=outcomes, events=events, fixture_events=fixtures, counts=counts)


def validate_receipt(receipt, selected_ids):
    require(receipt["selected_ids"] == selected_ids, "Selected IDs differ from request")
    require(len(selected_ids) == len(set(selected_ids)), "Duplicate selected IDs")
    for field in ("started_ids", "stopped_ids"):
        values = receipt[field]
        require(len(values) == len(set(values)), "Repeated test in " + field)
        require(values == [identity for identity in selected_ids if identity in values],
                "Unknown/out-of-order test in " + field)
    require(set(receipt["stopped_ids"]) <= set(receipt["started_ids"]), "Stop without start")
    for event in receipt["events"]:
        require(event["kind"] in STATUSES[:6], "Unknown result event")
        if event["parent_id"] is not None:
            require(event["parent_id"] in selected_ids, "Unknown subtest parent")
        elif event["id"] not in selected_ids:
            require(event["kind"] in ("error", "skip") and
                    event["id"].startswith(("setUpClass (", "tearDownClass (", "setUpModule (", "tearDownModule (")),
                    "Unknown fixture result")
    records = ([dict(kind="start", id=identity) for identity in receipt["started_ids"]] +
               [dict(kind="stop", id=identity) for identity in receipt["stopped_ids"]] + receipt["events"])
    require(make_receipt(selected_ids, records) == receipt, "Receipt accounting mismatch")


def successful(counts):
    return not any(counts[key] for key in ("failure", "error", "unexpected_success",
                                          "not_started", "unfinished", "fixture_errors"))


def read_journal(path):
    """Return (records, problems) from a child's events.jsonl without trusting it."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return [], ["Missing child journal"]
    except (OSError, ValueError) as exc:
        return [], [f"Unreadable child journal: {type(exc).__name__}: {exc}"]
    records, problems = [], []
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
            require(isinstance(row, dict) and row.get("kind") in ("start", "stop") + STATUSES[:6] and
                    isinstance(row.get("id"), str) and "parent_id" in row and
                    isinstance(row["parent_id"], (str, type(None))), "Not a journal record")
            records.append(row)
        except Exception:
            # A killed child can leave a cut line. Keep the rows around it.
            problems.append(f"Incomplete journal line {number}")
    return records, problems


def reconcile(directory, ids, exit_code):
    """Return (receipt, problems) for one finished child.

    The child's receipt counts only if the journal it flushed while running
    rebuilds to the same receipt and the exit code agrees. Otherwise the journal
    view is returned with the reasons, and the partition must not pass.
    """
    records, problems = read_journal(Path(directory) / "events.jsonl")
    journal_usable = not problems
    try:
        from_journal = make_receipt(ids, records)
    except Exception as exc:
        journal_usable = False
        problems.append(f"Journal accounting failed: {type(exc).__name__}: {exc}")
        from_journal = make_receipt(ids, [])
    receipt = None
    try:
        receipt_path = Path(directory) / "receipt.json"
        require(receipt_path.is_file(), "Missing child receipt")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        validate_receipt(receipt, ids)
    except Exception as exc:
        receipt = None
        problems.append(str(exc) if type(exc) is RuntimeError else f"{type(exc).__name__}: {exc}")
    if receipt is not None:
        if exit_code != (0 if successful(receipt["counts"]) else 1):
            problems.append("Exit/receipt mismatch")
        differing = [key for key in from_journal if receipt[key] != from_journal[key]]
        if journal_usable and differing:
            problems.append("Journal/receipt mismatch: " + ", ".join(differing))
    return (from_journal if problems else receipt), problems


def child(request_path, directory):
    ids = json.loads(Path(request_path).read_text(encoding="utf-8"))
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(ids)
    require(not loader.errors, "Child loading failed: " + repr(loader.errors))
    require(test_ids(list(flatten(suite))) == ids, "Child IDs differ from request")
    journal_path = Path(directory) / "events.jsonl"
    with journal_path.open("x", encoding="utf-8") as journal:
        def factory(*args, **kwargs):
            return AccountedResult(*args, journal=journal, **kwargs)
        unittest.TextTestRunner(verbosity=2, resultclass=factory).run(suite)
    records = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()]
    receipt = make_receipt(ids, records)
    validate_receipt(receipt, ids)
    write_json(Path(directory) / "receipt.json", receipt)
    return 0 if successful(receipt["counts"]) else 1


def launch(arguments, directory, timeout):
    from experiments.random_expert_exhibition_process import CREATE_SUSPENDED, create_scope
    scope, process = None, None
    info = dict(exit_code=None, errors=[], seconds=None, timeout_seconds=timeout,
                active_after=None, active_after_cleanup=None)
    started = time.monotonic()
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                       QT_QPA_PLATFORM="offscreen")
    # Never enable opt-in campaigns or relocate global TEMP into an evidence path.
    if os.name == "nt":
        environment.setdefault("QT_QPA_FONTDIR", str(Path(os.environ["WINDIR"]) / "Fonts"))
    try:
        scope = create_scope()
        with (directory / "stdout.txt").open("x", encoding="utf-8") as out, \
                (directory / "stderr.txt").open("x", encoding="utf-8") as err:
            process = subprocess.Popen([str(APPROVED_PYTHON), "-B", str(Path(__file__).resolve()), *arguments],
                                       cwd=ROOT, env=environment, stdout=out, stderr=err,
                                       creationflags=(CREATE_SUSPENDED | subprocess.CREATE_NO_WINDOW) if scope else 0)
            info["pid"] = process.pid
            if scope:
                scope.assign_and_resume(process)
            info["exit_code"] = process.wait(timeout=timeout)
        if scope:
            deadline = time.monotonic() + 3
            while scope.active_count and time.monotonic() < deadline:
                time.sleep(0.05)
            info["active_after"] = scope.active_count
            require(info["active_after"] == 0, "Child left owned processes running")
    except Exception as exc:
        info["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        if scope:
            try:
                if scope.active_count:
                    scope.terminate()
                deadline = time.monotonic() + 3
                while scope.active_count and time.monotonic() < deadline:
                    time.sleep(0.05)
                info["active_after_cleanup"] = scope.active_count
                require(info["active_after_cleanup"] == 0, "Owned processes remain after cleanup")
            except Exception as exc:
                info["errors"].append(f"Cleanup {type(exc).__name__}: {exc}")
            finally:
                scope.close()
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        info["seconds"] = round(time.monotonic() - started, 3)
    write_json(directory / "process.json", info)
    return info


def full_source(output, modules=(), collect_only=False, timeout=3600):
    output.mkdir(parents=True, exist_ok=False)
    print("SOURCE_UNITTEST_OUTPUT " + str(output), flush=True)
    discovery_dir = output / "discovery"
    discovery_dir.mkdir()
    discovery_path = discovery_dir / "receipt.json"
    info = launch(["--discover-child", str(discovery_path)], discovery_dir, timeout)
    if info["exit_code"] != 0 or info["errors"] or not discovery_path.is_file():
        write_json(output / "summary.json", dict(successful=False, discovery="FAILED",
                   partition_integrity="NOT_VERIFIED", result_accounting="NOT_STARTED", process=info))
        return 2
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    groups = discovery["partitions"]
    if modules:
        unknown = set(modules) - set(groups) - {key.rsplit(".", 1)[0] for key in groups}
        require(not unknown, "Unknown modules: " + repr(sorted(unknown)))
        groups = {key: value for key, value in groups.items()
                  if key in modules or key.rsplit(".", 1)[0] in modules}
    selected_ids = [identity for values in groups.values() for identity in values]
    require(len(selected_ids) == len(set(selected_ids)), "Partition IDs overlap")
    if not modules:
        require(set(selected_ids) == set(discovery["selected_ids"]), "Partition coverage mismatch")
    write_json(output / "selection.json", dict(scope="subset" if modules else "full_source",
               modules=list(modules), selected_ids=selected_ids, partitions=groups))
    if collect_only:
        print(f"SOURCE_UNITTEST_COLLECTED raw={discovery['raw_discovered']} unique={discovery['unique_discovered']} "
              f"selected={len(selected_ids)} partitions={len(groups)}", flush=True)
        return 0
    combined, launches, accounting_errors, reconciled = [], [], [], 0
    for index, (name, ids) in enumerate(groups.items(), 1):
        directory = output / f"{index:03d}_{name}"
        directory.mkdir()
        request = directory / "request.json"
        write_json(request, ids)
        info = launch(["--test-child", str(request), str(directory)], directory, timeout)
        # The journal is read on every path, not only after a receipt failure.
        receipt, problems = reconcile(directory, ids, info["exit_code"])
        if problems:
            try:
                # Kept beside the child's own files, which are never rewritten.
                write_json(directory / "recovered_receipt.json", receipt)
            except Exception as exc:
                problems.append(f"Recovered receipt not written: {type(exc).__name__}: {exc}")
        info["errors"].extend(problems)
        accounting_errors.extend(dict(partition=name, error=problem) for problem in problems)
        reconciled += not problems
        combined.append(receipt)
        launches.append(dict(partition=name, directory=str(directory), **info))
        print(f"SOURCE_UNITTEST_PARTITION {index}/{len(groups)} {name} " +
              json.dumps(receipt["counts"], sort_keys=True) + f" infrastructure_errors={len(info['errors'])}" +
              f" journal={'RECOVERED' if problems else 'MATCH'}", flush=True)
    counts = {key: sum(row["counts"][key] for row in combined) for key in combined[0]["counts"]} if combined else {}
    summary = dict(scope="subset" if modules else "full_source", raw_discovered=discovery["raw_discovered"],
                   unique_discovered=discovery["unique_discovered"], removed_aliases=len(discovery["duplicates"]),
                   partitions=len(groups), counts=counts, processes=launches,
                   infrastructure_errors=sum(len(row["errors"]) for row in launches),
                   partition_integrity="PASS", result_accounting="PASS" if not accounting_errors else "INCOMPLETE",
                   journal_reconciled=reconciled, accounting_errors=accounting_errors)
    summary["successful"] = bool(counts) and successful(counts) and not summary["infrastructure_errors"]
    write_json(output / "summary.json", summary)
    print("SOURCE_UNITTEST_SUMMARY " + json.dumps({k: v for k, v in summary.items() if k != "processes"}, sort_keys=True), flush=True)
    return 0 if summary["successful"] else 1


def main():
    require(Path(sys.executable).resolve() == APPROVED_PYTHON.resolve(), "Run with the approved development Python")
    require(sys.dont_write_bytecode and os.environ.get("PYTHONDONTWRITEBYTECODE") == "1",
            "Use -B and PYTHONDONTWRITEBYTECODE=1")
    os.chdir(ROOT)
    # Some non-test support fixtures use bare imports from the tests directory.
    # Discovery itself still imports every test under its canonical package.
    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    if len(sys.argv) == 3 and sys.argv[1] == "--discover-child":
        discover(sys.argv[2])
        return 0
    if len(sys.argv) == 4 and sys.argv[1] == "--test-child":
        return child(sys.argv[2], sys.argv[3])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "results" / ("source-unittest-" + time.strftime("%Y%m%d-%H%M%S")))
    parser.add_argument("--module", action="append", default=[], help="Optional canonical module/class subset")
    parser.add_argument("--collect-only", action="store_true")
    # Large evidence-validation fixtures can exceed 30 minutes as a module.
    # This outer watchdog does not replace the tests' own wall/memory budgets.
    parser.add_argument("--timeout", type=int, default=3600,
                        help="Seconds per child, including discovery (default: %(default)s)")
    args = parser.parse_args()
    require(args.timeout > 0, "Timeout must be positive")
    return full_source(args.output_dir.resolve(), args.module, args.collect_only, args.timeout)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
