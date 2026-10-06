"""Shared Windows Qt plugin-path bootstrap, extracted unchanged from main."""

import os
import sys


def configure_qt_plugin_path():
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
