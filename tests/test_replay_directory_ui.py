"""Persistent Replay directory, real JSON IO, and isolated Qt user settings."""

import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from core_engine import MinesweeperEngine
from replay_json import load_replay_json, save_replay_json
from tests.ui_settings import isolate_ui_settings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtCore import QSettings
    from PyQt5.QtWidgets import QApplication, QMessageBox
except ImportError:
    QApplication = None
else:
    from ui_manager import MinesweeperUI

KEY = "replay/default_directory"


@unittest.skipIf(QApplication is None, "PyQt5 unavailable")
class ReplayDirectoryUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings = isolate_ui_settings(self)
        self.root = Path(self.settings.fileName()).parent
        worker = patch.object(MinesweeperUI, "_ensure_zini_metric_job")
        worker.start()
        self.addCleanup(worker.stop)
        for name in ("information", "warning"):
            message = patch("ui_manager.QMessageBox." + name)
            message.start()
            self.addCleanup(message.stop)
        self.windows = []
        self.addCleanup(self.close_windows)
        self.ui = self.new_ui()
        self.ui.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        self.ui.on_left_click(0, 0)

    def new_ui(self):
        ui = MinesweeperUI(MinesweeperEngine(3, 3, 1))
        self.windows.append(ui)
        return ui

    def close_windows(self):
        for ui in self.windows:
            ui._stop_timer()
            ui._stop_replay_autoplay()
            ui.close()
            ui.deleteLater()
        self.app.processEvents()

    def directory(self, name="replays"):
        path = self.root / name
        path.mkdir()
        return str(path)

    def choose(self, directory):
        with patch("ui_manager.QFileDialog.getExistingDirectory", return_value=directory) as dialog:
            self.ui.replay_directory_action.trigger()
        return dialog

    def state(self):
        engine = self.ui.engine
        recorder = self.ui._replay_recorder
        return deepcopy((engine.get_observation(), engine.get_counter_snapshot(),
                         engine.get_board_snapshot(), recorder.board, recorder.events,
                         self.ui._replay_mode, self.ui._replay_data))

    def test_first_save_asks_for_directory_and_persists_selection(self):
        directory = self.directory()
        self.assertFalse(self.settings.contains(KEY))
        with patch("ui_manager.QFileDialog.getExistingDirectory", return_value=directory) as dialog:
            self.ui.on_save_replay()
        dialog.assert_called_once_with(self.ui, "Replay 저장 폴더 선택", "")
        self.assertEqual(self.settings.value(KEY), directory)
        files = list(Path(directory).glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(load_replay_json(files[0]), self.ui._replay_recorder.to_replay_data())

    def test_first_save_cancel_preserves_game_and_replay(self):
        before = self.state()
        with (patch("ui_manager.QFileDialog.getExistingDirectory", return_value="") as dialog,
              patch("ui_manager.save_replay_json") as save):
            self.ui.on_save_replay()
        dialog.assert_called_once()
        save.assert_not_called()
        self.assertFalse(self.settings.contains(KEY))
        self.assertEqual(self.state(), before)

    def test_new_ui_and_separate_settings_process_recover_persisted_directory(self):
        directory = self.directory()
        self.choose(directory)
        self.ui.simple_auto_interval_spin.setValue(500)
        self.ui.close()
        second = self.new_ui()
        self.assertIsNot(second._replay_settings, self.ui._replay_settings)
        self.assertEqual(second._replay_dialog_directory(), directory)
        self.assertEqual(second.simple_auto_interval_spin.value(), 180)
        # A new process proves this is flushed to disk, not only Qt's shared cache.
        probe = subprocess.run([
            sys.executable, "-c",
            "import sys; from PyQt5.QtCore import QSettings; "
            "s = QSettings(sys.argv[1], QSettings.IniFormat); "
            "s.setFallbacksEnabled(False); print(s.value('replay/default_directory', ''))",
            self.settings.fileName(),
        ], capture_output=True, text=True, check=True)
        self.assertEqual(probe.stdout.strip(), directory)
        second.engine.reset_with_mines(3, 3, 1, {(1, 1)})
        second.on_left_click(0, 0)
        with patch("ui_manager.QFileDialog.getExistingDirectory") as dialog:
            second.on_save_replay()
        dialog.assert_not_called()
        self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)

    def test_configured_save_skips_chooser_and_retains_timestamp_collision_policy(self):
        directory = self.directory()
        self.choose(directory)
        existing = Path(directory) / "replay_20261013_123456.json"
        existing.write_text("keep", encoding="utf-8")
        before = self.state()
        with (patch("ui_manager.datetime") as clock,
              patch("ui_manager.QFileDialog.getExistingDirectory") as dialog):
            clock.now.return_value = datetime(2026, 10, 13, 12, 34, 56)
            self.ui.on_save_replay()
            self.ui.on_save_replay()
        dialog.assert_not_called()
        self.assertEqual(existing.read_text(encoding="utf-8"), "keep")
        self.assertEqual({p.name for p in Path(directory).iterdir()}, {
            "replay_20261013_123456.json", "replay_20261013_123456_1.json",
            "replay_20261013_123456_2.json",
        })
        for suffix in (1, 2):
            self.assertEqual(load_replay_json(Path(directory) / f"replay_20261013_123456_{suffix}.json"),
                             self.ui._replay_recorder.to_replay_data())
        self.assertEqual(self.state(), before)

    def test_tools_action_replaces_and_persists_default_immediately(self):
        old = self.directory("old")
        new = self.directory("new")
        self.choose(old)
        self.assertEqual([a.text() for a in self.ui.tools_button.menu().actions()],
                         ["벤치마크 통계", "Replay 저장 폴더..."])
        dialog = self.choose(new)
        dialog.assert_called_once_with(self.ui, "Replay 저장 폴더 선택", old)
        self.assertEqual(self.settings.value(KEY), new)
        with patch("ui_manager.QFileDialog.getExistingDirectory") as dialog:
            self.ui.on_save_replay()
        dialog.assert_not_called()
        self.assertEqual(list(Path(old).iterdir()), [])
        self.assertEqual(len(list(Path(new).glob("*.json"))), 1)

    def test_tools_cancel_preserves_previous_setting_and_game(self):
        directory = self.directory()
        self.choose(directory)
        before = self.state()
        self.choose("")
        self.assertEqual(self.settings.value(KEY), directory)
        self.assertEqual(self.ui._replay_dialog_directory(), directory)
        self.assertEqual(self.state(), before)

    def test_unavailable_default_cancel_keeps_setting_without_creating_old_path(self):
        missing = self.root / "unavailable" / "replays"
        self.settings.setValue(KEY, str(missing))
        before = self.state()
        with (patch("ui_manager.QFileDialog.getExistingDirectory", return_value="") as dialog,
              patch("ui_manager.save_replay_json") as save):
            self.ui.on_save_replay()
        dialog.assert_called_once_with(self.ui, "Replay 저장 폴더 선택", "")
        save.assert_not_called()
        self.assertFalse(missing.parent.exists())
        self.assertEqual(self.settings.value(KEY), str(missing))
        self.assertEqual(self.state(), before)

    def test_unavailable_default_recovery_persists_new_directory(self):
        missing = self.root / "unavailable"
        self.settings.setValue(KEY, str(missing))
        recovered = self.directory()
        with patch("ui_manager.QFileDialog.getExistingDirectory", return_value=recovered) as dialog:
            self.ui.on_save_replay()
        dialog.assert_called_once()
        self.assertFalse(missing.exists())
        self.assertEqual(self.settings.value(KEY), recovered)
        self.assertEqual(len(list(Path(recovered).glob("*.json"))), 1)

    def test_invalid_selected_directory_does_not_replace_default(self):
        directory = self.directory()
        self.choose(directory)
        invalid = self.root / "not-a-directory"
        invalid.write_text("file", encoding="utf-8")
        self.choose(str(invalid))
        self.assertEqual(self.settings.value(KEY), directory)
        self.assertEqual(self.ui._replay_dialog_directory(), directory)

    def test_save_as_starts_in_default_and_other_folder_does_not_replace_it(self):
        directory = self.directory()
        self.choose(directory)
        other = Path(self.directory("other")) / "special"
        with (patch("ui_manager.datetime") as clock,
              patch("ui_manager.QFileDialog.getSaveFileName", return_value=(str(other), "")) as dialog):
            clock.now.return_value = datetime(2026, 10, 13, 12, 34, 56)
            self.ui.on_save_replay_as()
        self.assertEqual(dialog.call_args.args[2], os.path.join(directory, "replay_20261013_123456.json"))
        self.assertEqual(load_replay_json(other.with_suffix(".json")), self.ui._replay_recorder.to_replay_data())
        self.assertEqual(self.settings.value(KEY), directory)
        with patch("ui_manager.QFileDialog.getExistingDirectory") as chooser:
            self.ui.on_save_replay()
        chooser.assert_not_called()
        self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)

    def test_save_as_preserves_extension_and_overwrite_confirmation(self):
        path = Path(self.directory()) / "special.JSON"
        for reply in (QMessageBox.No, QMessageBox.Yes):
            with self.subTest(reply=reply):
                path.write_text("keep", encoding="utf-8")
                with (patch("ui_manager.QFileDialog.getSaveFileName", return_value=(str(path), "")),
                      patch("ui_manager.QMessageBox.question", return_value=reply) as question):
                    self.ui.on_save_replay_as()
                question.assert_called_once()
                self.assertFalse(Path(str(path) + ".json").exists())
                if reply == QMessageBox.No:
                    self.assertEqual(path.read_text(encoding="utf-8"), "keep")
                else:
                    self.assertEqual(load_replay_json(path), self.ui._replay_recorder.to_replay_data())
                self.assertFalse(self.settings.contains(KEY))

    def test_load_starts_in_default_and_other_folder_does_not_replace_it(self):
        directory = self.directory()
        self.choose(directory)
        path = Path(self.directory("other")) / "loaded.json"
        replay = self.ui._replay_recorder.to_replay_data()
        save_replay_json(replay, path)
        with patch("ui_manager.QFileDialog.getOpenFileName", return_value=(str(path), "")) as dialog:
            self.ui.on_load_replay()
        self.assertEqual(dialog.call_args.args[2], directory)
        self.assertTrue(self.ui._replay_mode)
        self.assertEqual(self.ui._replay_data, replay)
        self.assertEqual(self.settings.value(KEY), directory)
        with patch("ui_manager.QFileDialog.getExistingDirectory") as chooser:
            self.ui.on_save_replay()
        chooser.assert_not_called()
        self.assertEqual(load_replay_json(next(Path(directory).glob("*.json"))), replay)

    def test_save_as_and_load_cancel_preserve_default_and_state(self):
        directory = self.directory()
        self.choose(directory)
        before = self.state()
        for method, dialog in ((self.ui.on_save_replay_as, "getSaveFileName"),
                               (self.ui.on_load_replay, "getOpenFileName")):
            with self.subTest(method=method.__name__), patch("ui_manager.QFileDialog." + dialog, return_value=("", "")):
                method()
            self.assertEqual(self.settings.value(KEY), directory)
            self.assertEqual(self.state(), before)

    def test_reset_difficulty_and_replay_transitions_preserve_default(self):
        directory = self.directory()
        self.choose(directory)
        from replay_player import ReplayPlayer
        replay = self.ui._replay_recorder.to_replay_data()
        for transition in (self.ui.on_reset,
                           lambda: self.ui.on_difficulty_changed("초급 (9x9, 10)"),
                           lambda: self.ui._enter_replay_mode(ReplayPlayer(replay)),
                           self.ui.on_exit_replay):
            transition()
            self.assertEqual(self.ui._replay_dialog_directory(), directory)
            self.assertEqual(self.settings.value(KEY), directory)

    def test_ui_settings_use_only_temporary_ini_with_no_native_fallback(self):
        settings = self.ui._replay_settings
        self.assertEqual(settings.format(), QSettings.IniFormat)
        self.assertFalse(settings.fallbacksEnabled())
        self.assertEqual(Path(settings.fileName()), self.root / "settings.ini")
        self.assertFalse(settings.contains(KEY))
        self.choose(self.directory())
        self.assertEqual(settings.allKeys(), [KEY])
        self.assertTrue(Path(settings.fileName()).is_file())


if __name__ == "__main__":
    unittest.main()
