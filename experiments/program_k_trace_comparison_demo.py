"""D4.2 standalone launcher: python -B -m experiments.program_k_trace_comparison_demo.

Read the accepted E1 pair set once. No algorithm, job, or production entry point.
"""

import argparse
from pathlib import Path
import sys

from experiments.program_k_trace_comparison import load_accepted_e1_pairs, TraceComparisonError
from experiments.program_k_trace_adapter import ACCEPTED_RUN_ID
from qt_bootstrap import configure_qt_plugin_path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIRECTORY = ROOT / "results/program_k_research" / ACCEPTED_RUN_ID
DEFAULT_PROFILE = ROOT / "calibration/stage3_physical_profile_v1.json"


def load_demo_pairs(artifact_directory=DEFAULT_ARTIFACT_DIRECTORY, *, profile_path=DEFAULT_PROFILE):
    return load_accepted_e1_pairs(artifact_directory, profile_path=profile_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Program K Research Comparison: preserved CONTROL ↔ K-P0 E1 pairs.")
    parser.add_argument("--artifact-directory", type=Path, default=DEFAULT_ARTIFACT_DIRECTORY,
                        help="Directory containing the exact accepted qualification.json and COMPLETE.json.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE,
                        help="Exact accepted Model C profile (byte-identical copy permitted).")
    args = parser.parse_args(argv)
    print("Loading preserved accepted E1 CONTROL / K-P0 pairs…", flush=True)
    try:
        pairs = load_demo_pairs(args.artifact_directory, profile_path=args.profile)
    except TraceComparisonError as exc:
        print(f"Cannot load accepted E1 pairs: {exc}", file=sys.stderr)
        return 1
    configure_qt_plugin_path()
    from PyQt5.QtWidgets import QApplication
    from experiments.program_k_trace_comparison_ui import ProgramKComparisonWindow

    app = QApplication.instance() or QApplication([sys.argv[0]])
    window = ProgramKComparisonWindow(pairs)
    window.showMaximized()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
