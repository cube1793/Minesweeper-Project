"""Full source unittest gate with a fresh coordinator for the supervisor class."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
APPROVED_PYTHON = Path(r"C:\venvs\minesweeper\Scripts\python.exe")
ISOLATED_CLASS = "test_program_k_harness.ProgramKSlice7SupervisorTests"
COUNTS = ("run", "pass", "failure", "error", "skip", "expected_failure",
          "unexpected_success")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


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


def partition(tests):
    full_ids = test_ids(tests)
    isolated = [test for test in tests if test.id().rsplit(".", 1)[0] == ISOLATED_CLASS]
    main = [test for test in tests if test.id().rsplit(".", 1)[0] != ISOLATED_CLASS]
    main_ids, isolated_ids = test_ids(main), test_ids(isolated)
    require(isolated_ids, "Supervisor class missing from full discovery")
    require(not set(main_ids) & set(isolated_ids), "Partitions overlap")
    require(set(main_ids) | set(isolated_ids) == set(full_ids), "Partition omits tests")
    require(len(main_ids) + len(isolated_ids) == len(full_ids), "Partition count mismatch")
    return main, main_ids, isolated_ids


class AccountedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started_ids = []
        self.stopped_ids = []
        self.passed_ids = []

    def startTest(self, test):
        self.started_ids.append(test.id())
        super().startTest(test)

    def stopTest(self, test):
        self.stopped_ids.append(test.id())
        super().stopTest(test)

    def addSuccess(self, test):
        self.passed_ids.append(test.id())
        super().addSuccess(test)


def run_suite(suite, selected_ids):
    result = unittest.TextTestRunner(verbosity=2, resultclass=AccountedResult).run(suite)
    return {
        "selected_ids": selected_ids,
        "started_ids": result.started_ids,
        "stopped_ids": result.stopped_ids,
        "passed_ids": result.passed_ids,
        "counts": {
            "run": result.testsRun, "pass": len(result.passed_ids),
            "failure": len(result.failures), "error": len(result.errors),
            "skip": len(result.skipped), "expected_failure": len(result.expectedFailures),
            "unexpected_success": len(result.unexpectedSuccesses),
        },
    }


def validate_receipt(receipt, selected_ids):
    require(set(receipt) == {"selected_ids", "started_ids", "stopped_ids", "passed_ids", "counts"},
            "Unexpected result receipt schema")
    require(receipt["selected_ids"] == selected_ids, "Selected IDs differ from request")
    require(receipt["started_ids"] == selected_ids, "Executed IDs differ from discovery order")
    require(receipt["stopped_ids"] == selected_ids, "Not every selected test completed once")
    passed = receipt["passed_ids"]
    require(isinstance(passed, list) and len(passed) == len(set(passed))
            and set(passed) <= set(selected_ids), "Invalid PASS accounting")
    counts = receipt["counts"]
    require(set(counts) == set(COUNTS), "Unexpected count fields")
    require(all(type(value) is int and value >= 0 for value in counts.values()),
            "Invalid result counts")
    require(counts["run"] == len(selected_ids) and counts["pass"] == len(passed),
            "Executed count mismatch")
    require(sum(counts[key] for key in COUNTS if key != "run") == counts["run"],
            "Result totals do not reconcile")


def successful(counts):
    return not (counts["failure"] or counts["error"] or counts["unexpected_success"])


def isolated_child(request_path, result_path):
    ids = json.loads(Path(request_path).read_text(encoding="utf-8"))
    require(isinstance(ids, list) and ids and all(isinstance(item, str) for item in ids),
            "Invalid isolated ID request")
    require(len(ids) == len(set(ids)), "Duplicate isolated request")
    require(all(item.rsplit(".", 1)[0] == ISOLATED_CLASS for item in ids),
            "Requested test outside isolated class")
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(ids)
    require(not loader.errors, "Isolated test loading failed: " + repr(loader.errors))
    require(test_ids(list(flatten(suite))) == ids, "Loaded isolated IDs differ from request")
    receipt = run_suite(suite, ids)
    with Path(result_path).open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True)
        stream.write("\n")
    validate_receipt(receipt, ids)
    return 0 if successful(receipt["counts"]) else 1


def full_source():
    summary = {"full_discovered": 0, "main_selected": 0, "isolated_selected": 0,
               "combined_run": 0, "pass": 0, "failure": 0, "error": 0, "skip": 0,
               "expected_failure": 0, "unexpected_success": 0,
               "isolated_subprocess_exit_code": None,
               "partition_integrity": "FAIL", "result_accounting": "FAIL"}
    try:
        loader = unittest.TestLoader()
        discovered = loader.discover(str(ROOT / "tests"))
        require(not loader.errors, "Full discovery failed: " + repr(loader.errors))
        tests = list(flatten(discovered))
        summary["full_discovered"] = len(tests)
        main, main_ids, isolated_ids = partition(tests)
        summary.update(main_selected=len(main_ids), isolated_selected=len(isolated_ids),
                       partition_integrity="PASS")
        print("ISOLATED_TEST_IDS " + json.dumps(isolated_ids), flush=True)
        main_suite = unittest.TestSuite(main)
        # Let unittest release executed cases; do not retain the discovery tree.
        del tests, discovered, main
        main_receipt = run_suite(main_suite, main_ids)
        for key in COUNTS:
            summary["combined_run" if key == "run" else key] += main_receipt["counts"][key]
        # Always attempt both partitions, even if MAIN reports failures/errors.
        with tempfile.TemporaryDirectory(prefix="source-unittest-isolated-") as temporary:
            request = Path(temporary) / "request.json"
            result = Path(temporary) / "result.json"
            request.write_text(json.dumps(isolated_ids), encoding="utf-8")
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            child = subprocess.run(
                [str(APPROVED_PYTHON), "-B", str(Path(__file__).resolve()),
                 "--isolated-child", str(request), str(result)],
                cwd=ROOT, env=environment, check=False,
            )
            summary["isolated_subprocess_exit_code"] = child.returncode
            require(result.is_file(), "Isolated process did not provide exact result accounting")
            isolated_receipt = json.loads(result.read_text(encoding="utf-8"))
        validate_receipt(main_receipt, main_ids)
        validate_receipt(isolated_receipt, isolated_ids)
        for key in COUNTS:
            summary["combined_run" if key == "run" else key] += isolated_receipt["counts"][key]
        require(child.returncode == (0 if successful(isolated_receipt["counts"]) else 1),
                "Isolated subprocess exit/result mismatch")
        require(summary["combined_run"] == summary["full_discovered"], "Combined run mismatch")
        summary["result_accounting"] = "PASS"
        return 0 if successful(summary) else 1
    except Exception as exc:
        summary["gate_error"] = f"{type(exc).__name__}: {exc}"
        print(summary["gate_error"], file=sys.stderr, flush=True)
        return 2
    finally:
        print("SOURCE_UNITTEST_SUMMARY " + json.dumps(summary, sort_keys=True), flush=True)


def main():
    require(Path(sys.executable).resolve() == APPROVED_PYTHON.resolve(),
            "Run with the approved development Python")
    require(sys.dont_write_bytecode and os.environ.get("PYTHONDONTWRITEBYTECODE") == "1",
            "Use -B and PYTHONDONTWRITEBYTECODE=1")
    os.chdir(ROOT)
    sys.path[:0] = [str(ROOT / "tests"), str(ROOT)]
    if len(sys.argv) == 4 and sys.argv[1] == "--isolated-child":
        return isolated_child(sys.argv[2], sys.argv[3])
    require(len(sys.argv) == 1, "No public arguments are supported")
    return full_source()


if __name__ == "__main__":
    sys.exit(main())
