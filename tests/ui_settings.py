"""Per-test QSettings storage: never open the user's native settings."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def isolate_ui_settings(test_case):
    # Lazy import preserves the existing optional-PyQt test guards.
    from PyQt5.QtCore import QSettings

    directory = TemporaryDirectory()
    test_case.addCleanup(directory.cleanup)
    path = str(Path(directory.name) / "settings.ini")

    def create_settings(organization, application):
        test_case.assertEqual((organization, application),
                              ("MinesweeperProject", "Minesweeper"))
        settings = QSettings(path, QSettings.IniFormat)
        settings.setFallbacksEnabled(False)
        return settings

    factory = patch("ui_manager.QSettings", side_effect=create_settings)
    factory.start()
    test_case.addCleanup(factory.stop)
    return create_settings("MinesweeperProject", "Minesweeper")
