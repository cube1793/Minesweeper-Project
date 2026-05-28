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


# Qt 관련 import 이전에 반드시 호출
_configure_qt_plugin_path()

from PyQt5.QtWidgets import QApplication  # noqa: E402

from core_engine import MinesweeperEngine  # noqa: E402
from ui_manager import MinesweeperUI       # noqa: E402


# 기본 게임 설정 (상급 난이도)
DEFAULT_WIDTH = 30
DEFAULT_HEIGHT = 16
DEFAULT_MINES = 99


def main():
    app = QApplication(sys.argv)

    engine = MinesweeperEngine(
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT,
        num_mines=DEFAULT_MINES,
    )

    window = MinesweeperUI(engine)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()