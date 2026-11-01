"""Source entry: python -B -m experiments.k_lc0_exhibition (no automatic run)."""

import argparse
import os
import sys
from pathlib import Path

from experiments.k_lc0_exhibition_store import DEFAULT_RUNS
from experiments.random_expert_exhibition_model import validate_index


def main(argv=None):
    parser = argparse.ArgumentParser(description="actual K-P0 / active K-LC0 새 Expert 비교")
    parser.add_argument("--index",type=int,default=314,help="입력란 초기값만 설정; 실행 버튼을 눌러야 계산")
    parser.add_argument("--open",type=Path,help="이번 형식의 저장 JSON 재생 (계산 없음)")
    parser.add_argument("--runs-root",type=Path,default=DEFAULT_RUNS)
    parser.add_argument("--small",action="store_true",help="900×760 작은 창")
    args = parser.parse_args(argv)
    try: validate_index(args.index)
    except ValueError as exc: parser.error(str(exc))
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    from qt_bootstrap import configure_qt_plugin_path
    configure_qt_plugin_path()
    from PyQt5.QtWidgets import QApplication
    from experiments.k_lc0_exhibition_ui import CompareWindow
    app = QApplication.instance() or QApplication([sys.argv[0]])
    window = CompareWindow(runs_root=args.runs_root)
    window.index_edit.setText(str(args.index))
    if args.open: window.open_record(args.open)
    if args.small:
        window.resize(900,760)
        window.show()
    else: window.showMaximized()
    return app.exec_()


if __name__ == "__main__": raise SystemExit(main())
