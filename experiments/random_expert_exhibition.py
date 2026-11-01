"""Standalone source entry: python -B -m experiments.random_expert_exhibition."""

import argparse
import os
import sys

from experiments.random_expert_exhibition_model import validate_index


def main(argv=None):
    parser = argparse.ArgumentParser(description="새 Expert 전시 실행 · frozen V1 / actual K-P0")
    parser.add_argument("--index", type=int, help="창을 연 뒤 0..99999의 지정 index를 한 번 실행")
    args = parser.parse_args(argv)
    if args.index is not None:
        try:
            validate_index(args.index)
        except ValueError as exc:
            parser.error(str(exc))
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    from qt_bootstrap import configure_qt_plugin_path

    configure_qt_plugin_path()
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication
    from experiments.random_expert_exhibition_ui import ExhibitionWindow

    app = QApplication.instance() or QApplication([sys.argv[0]])
    window = ExhibitionWindow()
    window.showMaximized()
    if args.index is not None:
        QTimer.singleShot(0, lambda: window.run_index(args.index))
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
