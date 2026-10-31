"""Standalone D2 entry point: load accepted E1 once, then display D1 models.

Run from the repository root with:
    python -B -m experiments.program_k_trace_demo
No algorithm execution, worker/job, packaging, or production-menu integration.
"""

import argparse
from pathlib import Path
import sys

from experiments.program_k_trace_adapter import (
    ACCEPTED_RUN_ID, KTraceAdapterError, load_accepted_e1_traces,
)
from qt_bootstrap import configure_qt_plugin_path


ROOT = Path(__file__).resolve().parents[1]
DEMO_SCHEDULE_INDICES = (8, 14, 20, 26)
DEFAULT_ARTIFACT_DIRECTORY = ROOT / "results/program_k_research" / ACCEPTED_RUN_ID
DEFAULT_PROFILE = ROOT / "calibration/stage3_physical_profile_v1.json"


def load_demo_presentations(artifact_directory=DEFAULT_ARTIFACT_DIRECTORY, *, profile_path=DEFAULT_PROFILE):
    """The sole admission boundary; fixed selections, no navigation-time reads."""
    return load_accepted_e1_traces(artifact_directory, schedule_indices=DEMO_SCHEDULE_INDICES,
                                  profile_path=profile_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Program K Research Trace Viewer: preserved accepted E1 K-P0 only.")
    parser.add_argument("--artifact-directory", type=Path, default=DEFAULT_ARTIFACT_DIRECTORY,
                        help="Directory containing the exact accepted qualification.json and COMPLETE.json.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE,
                        help="Exact accepted Model C profile (byte-identical portable copy permitted).")
    args = parser.parse_args(argv)
    print("Loading preserved accepted E1 K-P0 evidence…", flush=True)
    try:
        presentations = load_demo_presentations(args.artifact_directory, profile_path=args.profile)
    except KTraceAdapterError as exc:
        print(f"Cannot load accepted E1 evidence: {exc}", file=sys.stderr)
        return 1
    configure_qt_plugin_path()
    from PyQt5.QtWidgets import QApplication
    from experiments.program_k_trace_viewer import KTraceViewerWindow

    app = QApplication.instance() or QApplication([sys.argv[0]])
    window = KTraceViewerWindow(presentations)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
