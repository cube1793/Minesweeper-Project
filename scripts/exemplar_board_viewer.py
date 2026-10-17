"""Standalone fixed-exemplar viewer; explicit evidence paths, one initial load."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from exemplar_board_evidence import ExemplarEvidenceError, load_accepted_exemplar_evidence
from qt_bootstrap import configure_qt_plugin_path

configure_qt_plugin_path()
from PyQt5.QtWidgets import QApplication
from exemplar_board_viewer_ui import ExemplarBoardViewerWindow


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect the four accepted fixed Timeline exemplars.')
    parser.add_argument('--stage2-db', required=True, type=Path)
    parser.add_argument('--stage3-db', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        evidence = load_accepted_exemplar_evidence(args.stage2_db, args.stage3_db)
    except ExemplarEvidenceError as exc:
        print(f'Cannot load accepted exemplar evidence: {exc}', file=sys.stderr)
        return 1
    app = QApplication.instance() or QApplication([sys.argv[0]])
    window = ExemplarBoardViewerWindow(evidence)
    window.show()
    return app.exec_()


if __name__ == '__main__':
    raise SystemExit(main())
