"""
main.py
지뢰찾기 프로그램 진입점.

[중요] Windows 환경에서 PyQt5 플랫폼 플러그인(qwindows.dll)을
찾지 못하는 고질적 에러를 방지하기 위한 방어 코드를
Qt import 이전에 가장 먼저 실행한다.
"""

import os
import sys


def _configure_qt_plugin_path():
    """
    Windows에서 'could not find or load the Qt platform plugin "windows"'
    에러를 예방하기 위해 QT_QPA_PLATFORM_PLUGIN_PATH 를 설정한다.
    """
    if sys.platform != "win32":
        return
    try:
        import PyQt5
        pyqt_dir = os.path.dirname(PyQt5.__file__)
        candidates = [
            os.path.join(pyqt_dir, "Qt5", "plugins"),
            os.path.join(pyqt_dir, "Qt", "plugins"),
        ]
        for base in candidates:
            platform_dir = os.path.join(base, "platforms")
            if os.path.isdir(platform_dir):
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platform_dir
                break
    except Exception as e:
        print(f"[경고] Qt 플러그인 경로 설정 실패: {e}", file=sys.stderr)


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
