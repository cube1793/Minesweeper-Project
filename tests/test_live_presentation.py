"""Focused presentation/gesture boundaries; synthetic jobs, no worker starts."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QFont, QFontMetrics, QImage, QKeyEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QLayout

from core_engine import MinesweeperEngine
from live_policy import POLICY_SIMPLE, POLICY_V1, plan_snapshot
from replay_model import ReplayBoard, ReplayData
from replay_player import ReplayPlayer
from tests.test_live_auto import SyntheticLivePolicyJob
from tests.ui_settings import isolate_ui_settings
from ui_manager import LiveStatusLabel, MinesweeperUI


GEOMETRY_OBSERVATIONS = []


class LivePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        isolate_ui_settings(self)
        for target, value in (("ui_manager.LivePolicyJob", SyntheticLivePolicyJob),
                              ("ui_manager.MinesweeperUI._ensure_zini_metric_job", None)):
            seam = patch(target, return_value=None) if value is None else patch(target, value)
            seam.start()
            self.addCleanup(seam.stop)
        self.ui = MinesweeperUI(MinesweeperEngine(9, 9, 10))
        self.ui.simple_auto_interval_spin.setValue(2000)
        self.addCleanup(self.close_ui)
        self.ui.show()
        self.ui.activateWindow()
        self.app.processEvents()

    def close_ui(self):
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def select_v1(self):
        self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(POLICY_V1))

    def geometry(self):
        cell = self.ui._buttons[(0, 0)]
        point = cell.mapTo(self.ui, QPoint(0, 0))
        return {"window": [self.ui.width(), self.ui.height()],
                "cell_origin": [point.x(), point.y()], "cell_size": [cell.width(), cell.height()],
                "policy": list(self.ui.live_policy_status_label.geometry().getRect()),
                "analysis": list(self.ui.analysis_status_label.geometry().getRect()),
                "minimum_width": self.ui.minimumSizeHint().width()}

    def test_idle_controls_do_not_flicker_on_press_hold_release(self):
        for policy in (POLICY_SIMPLE, POLICY_V1):
            for button in (Qt.LeftButton, Qt.RightButton):
                with self.subTest(policy=policy, button=int(button)):
                    self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))
                    self.ui.on_reset()
                    self.app.processEvents()
                    cell = self.ui._buttons[(4, 4)]
                    controls = (self.ui.analyze_button, self.ui.simple_auto_checkbox)
                    self.assertTrue(all(c.isEnabled() for c in controls))
                    QTest.mousePress(cell, button)
                    self.assertTrue(self.ui._mouse_buttons)
                    self.assertTrue(all(c.isEnabled() for c in controls))
                    self.ui._update_policy_controls()
                    self.assertTrue(all(c.isEnabled() for c in controls))
                    QTest.mouseRelease(cell, button)
                    self.assertFalse(self.ui._mouse_buttons)
                    self.assertTrue(all(c.isEnabled() for c in controls))
                    self.assertEqual(len(self.ui._replay_recorder.events), 1)

    def test_explicit_analysis_and_auto_activations_held_start_nothing(self):
        for policy in (POLICY_SIMPLE, POLICY_V1):
            with self.subTest(policy=policy):
                self.ui.live_policy_combo.setCurrentIndex(self.ui.live_policy_combo.findData(policy))
                self.ui.on_reset()
                self.app.processEvents()
                cell = self.ui._buttons[(4, 4)]
                QTest.mousePress(cell, Qt.LeftButton)
                with patch("ui_manager.analyze_position", side_effect=AssertionError("held analysis")):
                    self.ui.analyze_button.click()
                    self.ui.analyze_button.clicked.emit()
                    self.ui.on_analyze_current()
                    self.ui.analysis_checkbox.setChecked(True)
                    self.ui.simple_auto_checkbox.click()
                    # Window Space is the existing Reset shortcut. Exercise the
                    # checkbox's real key activation without invoking Reset.
                    for kind in (QEvent.KeyPress, QEvent.KeyRelease):
                        event = QKeyEvent(kind, Qt.Key_Space, Qt.NoModifier)
                        handler = (self.ui.simple_auto_checkbox.keyPressEvent if kind == QEvent.KeyPress
                                   else self.ui.simple_auto_checkbox.keyReleaseEvent)
                        handler(event)
                    self.ui.simple_auto_checkbox.setChecked(True)
                    self.ui.on_simple_auto_toggled(True)
                    self.ui.allow_guess_checkbox.setChecked(True)
                    self.ui.simple_auto_interval_spin.setValue(0)
                    self.ui._simple_auto_timer.timeout.emit()
                self.assertEqual(self.ui._v1_job.requests, [])
                self.assertEqual(len(self.ui._replay_recorder.events), 0)
                self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
                self.assertFalse(self.ui._simple_auto_pending)
                self.assertFalse(self.ui._simple_auto_timer.isActive())
                QTest.mouseRelease(cell, Qt.LeftButton)
                self.assertEqual(len(self.ui._replay_recorder.events), 1)
                self.ui.simple_auto_interval_spin.setValue(2000)

    def test_simple_right_input_refreshes_during_hold_and_rearms_after_release(self):
        self.ui.simple_auto_checkbox.setChecked(True)
        self.ui.allow_guess_checkbox.setChecked(True)
        old_callback = self.ui._simple_auto_timeout_slot
        cell = self.ui._buttons[(4, 4)]
        with patch.object(self.ui, "_analyze_simple_current", wraps=self.ui._analyze_simple_current) as analyze:
            QTest.mousePress(cell, Qt.RightButton)
            analyze.assert_called_once()
            self.assertEqual(self.ui._analysis_observation,
                             tuple(tuple(row) for row in self.ui.engine.get_observation()))
            self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
            self.assertFalse(self.ui._simple_auto_pending)
            self.assertFalse(self.ui._simple_auto_timer.isActive())
            self.assertEqual(len(self.ui._replay_recorder.events), 1)
            self.ui.on_allow_guess_toggled(True)
            self.ui.simple_auto_interval_spin.setValue(500)
            old_callback()
            self.assertEqual(len(self.ui._replay_recorder.events), 1)
            QTest.mouseRelease(cell, Qt.RightButton)
            analyze.assert_called_once()
        self.assertFalse(self.ui._simple_auto_pending)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertTrue(self.ui._simple_auto_pending)
        fresh_callback = self.ui._simple_auto_timeout_slot
        old_callback()
        self.assertTrue(self.ui._simple_auto_pending)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        fresh_callback()
        self.assertEqual(len(self.ui._replay_recorder.events), 2)

    def test_v1_cleanup_is_persistent_gate_but_hold_is_only_activation_gate(self):
        self.select_v1()
        self.ui.simple_auto_checkbox.setChecked(True)
        job = self.ui._v1_job
        job.deliver(plan_snapshot(job.requests[-1]))
        callback = self.ui._simple_auto_timeout_slot
        cell = self.ui._buttons[(4, 4)]
        QTest.mousePress(cell, Qt.LeftButton)
        self.assertEqual(job.state, "cancelling")
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
        job.complete_cancel()
        self.assertTrue(self.ui.analyze_button.isEnabled())
        self.assertTrue(self.ui.simple_auto_checkbox.isEnabled())
        self.ui.analyze_button.click()
        self.ui.simple_auto_checkbox.setChecked(True)
        callback()
        self.assertEqual(len(job.requests), 1)
        self.assertFalse(self.ui.simple_auto_checkbox.isChecked())
        QTest.mouseRelease(cell, Qt.LeftButton)
        self.assertEqual(len(self.ui._replay_recorder.events), 1)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(len(job.requests), 2)
        self.assertEqual(job.requests[-1].entry_mode, "ADOPT_CURRENT")
        self.assertEqual(job.requests[-1].input_seq, 0)
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())

    def test_pause_reuses_pending_stop_discards_then_readopts(self):
        self.select_v1()
        self.assertEqual(self.ui.live_policy_combo.currentText(), "Stage3 V1")
        self.assertEqual(self.ui.live_policy_combo.currentData(), POLICY_V1)
        self.ui.on_right_click(4, 4)
        self.ui.simple_auto_checkbox.setChecked(True)
        job = self.ui._v1_job
        proposal = plan_snapshot(job.requests[-1])
        job.deliver(proposal)
        self.ui.simple_auto_checkbox.setChecked(False)
        self.assertIs(self.ui._v1_pending, proposal)
        self.assertIn("일시정지", self.ui.live_policy_status_label.text())
        self.assertIn("보관", self.ui.live_policy_status_label.text())
        self.ui.simple_auto_interval_spin.setValue(1000)
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertIs(self.ui._v1_pending, proposal)
        self.assertEqual(len(job.requests), 1)
        self.ui.on_right_click(5, 4)
        self.assertIsNone(self.ui._v1_pending)
        self.assertEqual(job.state, "cancelling")
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
        job.complete_cancel()
        self.assertIn("정리 완료", self.ui.live_policy_status_label.text())
        self.ui.simple_auto_checkbox.setChecked(True)
        self.assertEqual(len(job.requests), 2)
        self.assertNotEqual(job.requests[-1].run_id, proposal.snapshot.run_id)
        self.assertEqual(job.requests[-1].entry_mode, "ADOPT_CURRENT")
        self.ui.simple_auto_checkbox.setChecked(False)
        self.ui.live_policy_combo.setCurrentIndex(0)
        self.assertFalse(self.ui.allow_guess_checkbox.isChecked())

    def test_persistent_disabled_conditions_remain(self):
        self.select_v1()
        self.ui._live_input_uncertain = True
        self.ui._update_policy_controls()
        self.assertFalse(self.ui.analyze_button.isEnabled())
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
        self.ui.on_analyze_current()
        self.assertEqual(self.ui._v1_job.requests, [])
        self.ui._live_input_uncertain = False
        self.ui._v1_job.state = "blocked"
        self.ui._update_policy_controls()
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
        self.ui.on_reset()
        self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
        self.ui._v1_job.state = "idle"
        self.ui._live_closing = True
        self.ui._update_policy_controls()
        self.assertFalse(self.ui.analyze_button.isEnabled())
        self.ui._live_closing = False

    def test_status_geometry_stays_fixed_for_simple_v1_and_replay(self):
        # Offscreen's existing toolbar minimum differs from native Windows.
        # Fix only this fixture's window constraint to measure the requested
        # viewport widths; all labels, layout, cell sizing and guards are real.
        self.ui.layout().setSizeConstraint(QLayout.SetNoConstraint)
        messages = ["분석 대기", "확정 수 FLAG (2, 3)\n두 번째 줄",
                    "V1 준비 · 미검증 깃발 해제 (4, 4) | 실제 지뢰도 미검증이면 해제될 수 있습니다. " * 20,
                    "Stage3 V1 (frozen) | 추측 후보 (0, 0) · 50% | 추측 대기",
                    "V1 자동 진행 중단 - FINISH_EXIT_TIMEOUT: " + "상세 오류 원인 " * 100,
                    "일시정지 · 추천 보관", "추천·계산 종료 · 수동 가능"]
        for mode in ("Simple", "V1", "Replay"):
            if mode == "V1":
                self.select_v1()
            elif mode == "Replay":
                data = ReplayData(ReplayBoard(2, 2, 1, {(1, 1)}), ())
                self.ui._enter_replay_mode(ReplayPlayer(data))
                self.assertFalse(self.ui.simple_auto_checkbox.isEnabled())
            for width, height in ((1086, 766), (820, 620)):
                self.ui.setFixedSize(width, height)
                self.app.processEvents()
                baseline = self.geometry()
                self.assertEqual(baseline["window"], [width, height])
                for text in messages:
                    with self.subTest(mode=mode, requested=(width, height), text=text[:30]):
                        self.ui.live_policy_status_label.setText("현재: Stage3 V1 | " + text)
                        self.ui.analysis_status_label.setText(text)
                        self.app.processEvents()
                        actual = self.geometry()
                        GEOMETRY_OBSERVATIONS.append({"mode": mode, "requested": [width, height],
                                                      "text": text, "baseline": baseline, "actual": actual})
                        self.assertEqual(actual, baseline)
                        self.assertIn(text, self.ui.analysis_status_label.toolTip())
                        self.assertIn(text, self.ui.analysis_status_label.accessibleDescription())
                        shown = self.ui.analysis_status_label.display_text()
                        self.assertLessEqual(len(shown.splitlines()), 2)
                        if "미검증" in text:
                            self.assertIn("미검증 깃발 해제", shown)
                            self.assertIn("실제 지뢰", shown)
                        if "추측 대기" in text:
                            self.assertTrue(shown.startswith("추측 대기"))
                        if "FINISH_EXIT_TIMEOUT" in text:
                            self.assertIn("중단", shown)
                            self.assertIn("FINISH_EXIT_TIMEOUT", shown)
                render_dir = os.environ.get("MINESWEEPER_UI_POLISH_RENDER_DIR")
                if render_dir:
                    self.assertTrue(self.ui.grab().save(str(Path(render_dir) / f"{mode}_{width}.png")))

    def test_status_font_metrics_and_full_diagnostic_survive_elision(self):
        label = self.ui.analysis_status_label
        self.ui.resize(1086, 766)
        self.app.processEvents()
        for points in (9, 15, 21):
            font = QFont(label.font())
            font.setPointSize(points)
            label.setFont(font)
            self.app.processEvents()
            height = label.height()
            baseline = self.geometry()
            for text in ("짧은 안내", "오류 · 공개 상태 모순: " + "원인 " * 100):
                label.setText(text)
                self.app.processEvents()
                self.assertEqual(label.height(), height)
                self.assertEqual(self.geometry(), baseline)
                self.assertIn(text, label.accessibleDescription())
            GEOMETRY_OBSERVATIONS.append({"font_points": points, "metrics_height": label.fontMetrics().height(),
                                          "line_spacing": label.fontMetrics().lineSpacing(), "geometry": baseline})
        self.assertGreater(GEOMETRY_OBSERVATIONS[-1]["geometry"]["analysis"][3],
                           GEOMETRY_OBSERVATIONS[-3]["geometry"]["analysis"][3])
        label.setText("V1 준비 · 미검증 깃발 해제 | 실제 지뢰도 미검증이면 해제될 수 있습니다.")
        self.assertIn("미검증 깃발 해제", label._summary())
        self.assertIn("실제 지뢰일 수 있음", label._summary())
        label.setText("Stage3 V1 (frozen) | " + "설명 " * 80 + " | 추측 대기")
        self.assertTrue(label._summary().startswith("추측 대기"))
        self.assertNotIn("(frozen)", label.display_text())
        self.assertIn("(frozen)", label.toolTip())
        self.assertIsInstance(label, LiveStatusLabel)

    def test_status_line_budget_tracks_device_dpi_in_small_fixture(self):
        # Real Qt font metrics on a controlled paint device, not OS DPI changes.
        class DeviceLabel(LiveStatusLabel):
            def fontMetrics(self):
                return QFontMetrics(self.font(), device)

        device = QImage(1, 1, QImage.Format_ARGB32)
        label = DeviceLabel("미검증 깃발 해제 · 실제 지뢰일 수 있음", 2)
        self.addCleanup(label.deleteLater)
        font = QFont(label.font())
        font.setPointSize(12)
        label.setFont(font)
        heights = []
        for dpi in (96, 144, 192):
            device.setDotsPerMeterX(round(dpi / 0.0254))
            device.setDotsPerMeterY(round(dpi / 0.0254))
            label._sync_height()
            heights.append(label.height())
            label.setText("상세 오류 " * 200)
            self.assertEqual(label.height(), heights[-1])
            GEOMETRY_OBSERVATIONS.append({"fixture_device_dpi": dpi, "height": label.height(),
                                          "metrics_height": label.fontMetrics().height(),
                                          "line_spacing": label.fontMetrics().lineSpacing()})
        self.assertLess(heights[0], heights[1])
        self.assertLess(heights[1], heights[2])
