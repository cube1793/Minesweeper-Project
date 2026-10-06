"""
main.py
지뢰찾기 프로그램 진입점.

[중요] Windows 환경에서 PyQt5 플랫폼 플러그인(qwindows.dll)을
찾지 못하는 고질적 에러를 방지하기 위한 방어 코드를
Qt import 이전에 가장 먼저 실행한다.
"""

import sys

from qt_bootstrap import configure_qt_plugin_path as _configure_qt_plugin_path


# 기본 게임 설정 (상급 난이도)
DEFAULT_WIDTH = 30
DEFAULT_HEIGHT = 16
DEFAULT_MINES = 99


def main():
    # Frozen builds re-enter this executable for the PyQt-independent worker.
    if sys.argv[1:2] == ["--zini-metric-worker"]:
        from zini_metric_worker import main as worker_main

        return worker_main(sys.argv[1:])

    # Qt 설정과 import는 worker 분기 이후에만 실행한다.
    _configure_qt_plugin_path()
    from PyQt5.QtWidgets import QApplication

    from core_engine import MinesweeperEngine
    from ui_manager import MinesweeperUI

    app = QApplication(sys.argv)

    engine = MinesweeperEngine(
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT,
        num_mines=DEFAULT_MINES,
    )

    window = MinesweeperUI(engine)
    window.show()

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
