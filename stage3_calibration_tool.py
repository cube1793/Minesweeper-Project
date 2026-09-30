"""Standalone collection UI: python stage3_calibration_tool.py [--output-dir DIR].

Reads the frozen V1 manifest; never generates a schedule or fits measurements.
Default output is the repository's already-ignored results/stage3_calibration/.
Each launch creates a new session, with no resume or overwrite of older data.

Raw coordinates are Qt logical pixels. Valid attempts always contain explicit
start/target trajectory endpoints. An interruption without a target press has
null target/duration fields: no target event or position is invented. end_ns
records the interruption time separately. Refresh rate is provenance only.
"""

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
import uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from qt_bootstrap import configure_qt_plugin_path

# Respect an explicitly supplied plugin path (including the offscreen test
# environment). Normal script startup shares the game's Windows bootstrap.
if __name__ == "__main__" and not os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
    configure_qt_plugin_path()

from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, QEvent, QRect, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QLabel, QLayout, QPushButton, QVBoxLayout, QWidget

from stage3_calibration import (
    CELL_SIZE_PX, GRID_HEIGHT, GRID_WIDTH, OFFICIAL, WARMUP,
    CalibrationManifest, CalibrationTrial, canonical_manifest_bytes,
)


ROOT = Path(__file__).resolve().parent
FROZEN_MANIFEST_PATH = ROOT / "calibration" / "stage3_calibration_manifest_v1.json"
FROZEN_MANIFEST_SHA256 = "07ce6943abec4f47474f50bfb317fea3dcd9c51afcf87c316adef674f58ce61d"
DEFAULT_OUTPUT_DIR = ROOT / "results" / "stage3_calibration"
BUTTONS = {"LEFT": Qt.LeftButton, "RIGHT": Qt.RightButton}


class TrialState(str, Enum):
    READY = "READY"
    ACTIVE = "ACTIVE"
    BLOCK_COMPLETE = "BLOCK_COMPLETE"
    FINISHED = "FINISHED"


def load_frozen_manifest(path=FROZEN_MANIFEST_PATH):
    """Fail loudly for missing, modified, malformed or noncanonical input."""
    payload = Path(path).read_bytes()
    if hashlib.sha256(payload).hexdigest() != FROZEN_MANIFEST_SHA256:
        raise ValueError("Frozen calibration manifest SHA-256 mismatch.")
    data = json.loads(payload)
    data["trials"] = [CalibrationTrial(**trial) for trial in data["trials"]]
    manifest = CalibrationManifest(**data)
    if canonical_manifest_bytes(manifest) != payload:
        raise ValueError("Frozen calibration manifest is not canonical.")
    return manifest


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def display_metadata(screen, qt_platform):
    """Capture the session-start display. Missing refresh data stays null.

    QScreen.refreshRate() is an approximate Qt report, not a measured physical
    rate. Virtual offscreen/minimal screens cannot supply display provenance.
    No refresh-rate value is consulted by collection or validity logic.
    """
    result = {
        "screen_name": None,
        "screen_resolution_logical_px": None,
        "qt_logical_dpi": None,
        "device_pixel_ratio": None,
        "display_refresh_rate_hz": None,
        "display_refresh_rate_status": "unavailable",
        "display_refresh_rate_unavailable_reason": "no_screen",
    }
    if screen is None:
        return result
    size = screen.size()
    result.update(
        screen_name=screen.name(),
        screen_resolution_logical_px=[size.width(), size.height()],
        qt_logical_dpi=screen.logicalDotsPerInch(),
        device_pixel_ratio=screen.devicePixelRatio(),
    )
    if qt_platform in ("offscreen", "minimal", "minimalegl"):
        result["display_refresh_rate_unavailable_reason"] = "virtual_platform"
        return result
    try:
        rate = screen.refreshRate()
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
            result["display_refresh_rate_unavailable_reason"] = "invalid_qt_report"
        else:
            result.update(display_refresh_rate_hz=rate,
                          display_refresh_rate_status="qt_reported_approximate",
                          display_refresh_rate_unavailable_reason=None)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        result["display_refresh_rate_unavailable_reason"] = "qt_query_failed"
    return result


class SessionWriter:
    """One new session and an append-only stream of completed attempts.

    flush() is called after every line, before the UI advances. This is not a
    power-loss durability guarantee. I/O failure stops collection, without
    retrying a potentially partial append or claiming successful completion.
    """

    def __init__(self, output_dir, manifest, manifest_path, display, notes="", clock_source="time.perf_counter_ns"):
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid.uuid4().hex[:8]
        self.session_path = directory / f"calibration_session_{session_id}.json"
        self.trials_path = directory / f"calibration_trials_{session_id}.jsonl"
        self.accepted_ids = set()
        self.valid_counts = Counter()
        self.invalid_count = 0
        self.closed = False
        self.metadata = {
            "protocol_version": manifest.protocol_version,
            "manifest_sha256": hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest(),
            "manifest_path": str(Path(manifest_path).resolve()),
            "manifest_seed": manifest.seed,
            "session_id": session_id,
            "session_started_at_utc": utc_now(),
            "session_ended_at_utc": None,
            "session_status": "IN_PROGRESS",
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "pyqt_version": PYQT_VERSION_STR,
            "qt_version": QT_VERSION_STR,
            "qt_platform": QApplication.platformName(),
            "clock": clock_source,
            "timing_boundary": "start_press_to_target_press",
            "raw_timing_unit": "ns",
            "coordinate_unit": "qt_logical_px",
            "grid_width": manifest.grid_width,
            "grid_height": manifest.grid_height,
            "cell_size_px": manifest.cell_size_px,
            "notes": notes,
            **display,
        }
        # Exclusive creation prevents accidental reuse or overwrite.
        self._stream = self.trials_path.open("x", encoding="utf-8", newline="\n")
        try:
            with self.session_path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(self.metadata, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.write("\n")
        except Exception:
            self._stream.close()
            raise

    def append_attempt(self, record):
        if self.closed:
            raise ValueError("Session is already closed.")
        if record["valid"] and record["trial_id"] in self.accepted_ids:
            raise ValueError("Duplicate accepted trial ID.")
        line = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self._stream.write(line + "\n")
        self._stream.flush()
        if record["valid"]:
            self.accepted_ids.add(record["trial_id"])
            self.valid_counts[record["phase"]] += 1
        else:
            self.invalid_count += 1

    def close(self, status):
        if self.closed:
            return
        self._stream.close()
        self.metadata.update(
            session_status=status, session_ended_at_utc=utc_now(),
            valid_warmup_attempts=self.valid_counts[WARMUP],
            valid_official_attempts=self.valid_counts[OFFICIAL],
            invalid_attempts=self.invalid_count,
        )
        # Replace only this session's metadata; attempts remain append-only.
        temporary = self.session_path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(self.metadata, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        temporary.replace(self.session_path)
        self.closed = True


class CalibrationCanvas(QWidget):
    """One fixed logical-pixel grid, including overlapping START/TARGET cues."""

    def __init__(self, window):
        super().__init__(window)
        self.collection = window
        self.setFixedSize(GRID_WIDTH * CELL_SIZE_PX, GRID_HEIGHT * CELL_SIZE_PX)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setContextMenuPolicy(Qt.NoContextMenu)

    def cell_at(self, position):
        x, y = position
        if not (0 <= x < self.width() and 0 <= y < self.height()):
            return None
        return int(x // CELL_SIZE_PX), int(y // CELL_SIZE_PX)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f5f7fa"))
        trial = self.collection.current_trial
        if trial is not None:
            sx, sy = trial.start_cell
            tx, ty = trial.target_cell
            start = QRect(sx * CELL_SIZE_PX, sy * CELL_SIZE_PX, CELL_SIZE_PX, CELL_SIZE_PX)
            target = QRect(tx * CELL_SIZE_PX, ty * CELL_SIZE_PX, CELL_SIZE_PX, CELL_SIZE_PX)
            painter.fillRect(start, QColor("#90caf9"))
            if start != target:
                painter.fillRect(target, QColor("#ffcc80"))
        painter.setPen(QPen(QColor("#c4cbd4"), 1))
        for x in range(GRID_WIDTH + 1):
            painter.drawLine(x * CELL_SIZE_PX, 0, x * CELL_SIZE_PX, self.height() - 1)
        for y in range(GRID_HEIGHT + 1):
            painter.drawLine(0, y * CELL_SIZE_PX, self.width() - 1, y * CELL_SIZE_PX)
        if trial is not None:
            painter.setPen(QPen(QColor("#1565c0"), 2))
            painter.drawRect(start.adjusted(2, 2, -2, -2))
            painter.setPen(QPen(QColor("#d66300"), 2))
            painter.drawRect(target.adjusted(4, 4, -4, -4))
            painter.setPen(QColor("#172333"))
            if start == target:
                painter.drawText(start, Qt.AlignCenter, "S/T")
            else:
                painter.drawText(start, Qt.AlignCenter, "S")
                painter.drawText(target, Qt.AlignCenter, "T")
        painter.end()

    def mousePressEvent(self, event):
        self.collection.mouse_press(event)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        # Qt replaces the second press with this event, particularly at O00.
        self.mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.collection.mouse_release(event)
        event.accept()

    def mouseMoveEvent(self, event):
        self.collection.mouse_move(event)
        event.accept()

    def leaveEvent(self, event):
        self.collection.interrupt("POINTER_LEFT_CANVAS")
        super().leaveEvent(event)

    def enterEvent(self, event):
        self.collection.rearm_after_external_release()
        super().enterEvent(event)


class CalibrationWindow(QWidget):
    """Fixed schedule, four states, and a single in-memory active attempt."""

    def __init__(self, *, output_dir=DEFAULT_OUTPUT_DIR, manifest_path=FROZEN_MANIFEST_PATH,
                 clock_ns=None, notes=""):
        # Validate before creating output files or an interactive widget.
        manifest = load_frozen_manifest(manifest_path)
        super().__init__()
        self.manifest = manifest
        self.clock_ns = time.perf_counter_ns if clock_ns is None else clock_ns
        self.state = TrialState.READY
        self.trial_index = 0
        self.attempt_indices = Counter()
        self._attempt = None
        self._start_released = False
        self._buttons_down = 0
        self._awaiting_release = False
        self.storage_error = None
        self.setWindowTitle("Stage 3 · 마우스 입력 보정")
        self.progress_label = QLabel()
        self.transition_label = QLabel()
        self.status_label = QLabel()
        self.canvas = CalibrationCanvas(self)
        self.continue_button = QPushButton("다음 블록 시작")
        self.continue_button.clicked.connect(self.continue_block)
        instructions = QLabel("파랑 S: START → 버튼 해제 → 주황 T: TARGET  |  Esc: 현재 시도 중단")
        self.output_label = QLabel(f"저장 위치: {Path(output_dir).resolve()}")
        for label in (instructions, self.progress_label, self.transition_label, self.status_label, self.output_label):
            label.setWordWrap(True)
            label.setMaximumWidth(self.canvas.width())
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetFixedSize)
        for widget in (instructions, self.progress_label, self.transition_label, self.canvas,
                       self.status_label, self.continue_button, self.output_label):
            layout.addWidget(widget)
        self.writer = SessionWriter(output_dir, manifest, manifest_path,
                                    display_metadata(self.screen(), QApplication.platformName()), notes,
                                    "time.perf_counter_ns" if clock_ns is None else "injected")
        self._refresh()

    @property
    def current_trial(self):
        if self.trial_index < len(self.manifest.trials):
            return self.manifest.trials[self.trial_index]
        return None

    def _refresh(self, message=None):
        trial = self.current_trial
        accepted = len(self.writer.accepted_ids)
        self.progress_label.setText(f"{self.state.value}  |  완료 {accepted}/{len(self.manifest.trials)}"
                                    f"  |  정식 {self.writer.valid_counts[OFFICIAL]}/384")
        if trial is not None:
            group = [t for t in self.manifest.trials
                     if (t.phase, t.block_index) == (trial.phase, trial.block_index)]
            phase = "연습 WARMUP" if trial.phase == WARMUP else f"정식 블록 {trial.block_index}/3"
            self.transition_label.setText(
                f"{phase} · {group.index(trial) + 1}/{len(group)} · {trial.trial_id}  |  "
                f"{trial.start_button} → {trial.target_button}  |  "
                f"START {trial.start_cell} → TARGET {trial.target_cell}")
        else:
            self.transition_label.setText("모든 trial 수집 완료")
        defaults = {
            TrialState.READY: "모든 버튼을 놓은 뒤 START를 지정된 버튼으로 누르세요.",
            TrialState.ACTIVE: "START 버튼을 놓은 뒤 TARGET을 지정된 버튼으로 누르세요.",
            TrialState.BLOCK_COMPLETE: "구간 완료. 쉬었다가 다음 블록을 시작하세요.",
            TrialState.FINISHED: "수집 완료. 결과가 저장되었습니다.",
        }
        self.status_label.setText(message or defaults[self.state])
        self.continue_button.setEnabled(self.state == TrialState.BLOCK_COMPLETE and not self.storage_error)
        # Present the next pair before accepting its START, never on START.
        self.canvas.repaint()

    @staticmethod
    def _position(event):
        return [event.localPos().x(), event.localPos().y()]

    @staticmethod
    def _overlap(buttons):
        return bool(buttons & (buttons - 1))

    def _sample(self, now, position, kind):
        self._attempt["trajectory"].append({
            "relative_time_ns": now - self._attempt["start_press_ns"],
            "x_px": position[0], "y_px": position[1], "kind": kind,
        })

    def mouse_press(self, event):
        if self.state not in (TrialState.READY, TrialState.ACTIVE):
            return
        # Capture the boundary before validation, painting, or persistence.
        # Reading the clock does not start an attempt: wrong READY input drops
        # this timestamp without storing any timed sample.
        now = self.clock_ns()
        position = self._position(event)
        self._buttons_down = int(event.buttons())
        trial = self.current_trial
        if self.state == TrialState.READY:
            if (self._awaiting_release or self.canvas.cell_at(position) != trial.start_cell
                    or event.button() != BUTTONS[trial.start_button]
                    or self._buttons_down != int(event.button())):
                return
            self.attempt_indices[trial.trial_id] += 1
            self._attempt = {
                **asdict(trial), "attempt_index": self.attempt_indices[trial.trial_id],
                "start_press_ns": now, "start_release_ns": None,
                "target_press_ns": None, "duration_ns": None,
                "start_press_px": position, "target_press_px": None,
                "trajectory": [], "valid": False, "invalid_reason": None,
            }
            self._sample(now, position, "start")
            self._start_released = False
            self.state = TrialState.ACTIVE
            return
        reason = None
        if self.canvas.cell_at(position) is None:
            reason = "POINTER_LEFT_CANVAS"
        elif self._overlap(self._buttons_down):
            reason = "BUTTON_OVERLAP"
        elif not self._start_released:
            reason = "START_NOT_RELEASED"
        elif event.button() != BUTTONS[trial.target_button]:
            reason = "WRONG_TARGET_BUTTON"
        elif self._buttons_down != int(event.button()):
            reason = "PROTOCOL_STATE"
        elif self.canvas.cell_at(position) != trial.target_cell:
            reason = "WRONG_TARGET"
        self._finish_attempt(now, reason, target_position=position)

    def mouse_release(self, event):
        now = self.clock_ns() if self.state == TrialState.ACTIVE else None
        self._buttons_down = int(event.buttons())
        if self.state != TrialState.ACTIVE:
            if not self._buttons_down:
                self._awaiting_release = False
            return
        if self.canvas.cell_at(self._position(event)) is None:
            self._finish_attempt(now, "POINTER_LEFT_CANVAS")
        elif self._overlap(self._buttons_down):
            self._finish_attempt(now, "BUTTON_OVERLAP")
        elif (self._start_released or event.button() != BUTTONS[self.current_trial.start_button]
              or self._buttons_down):
            self._finish_attempt(now, "PROTOCOL_STATE")
        else:
            self._start_released = True
            self._attempt["start_release_ns"] = now

    def mouse_move(self, event):
        if self.state != TrialState.ACTIVE:
            return
        now = self.clock_ns()
        position = self._position(event)
        self._buttons_down = int(event.buttons())
        self._sample(now, position, "move")
        expected_buttons = 0 if self._start_released else int(BUTTONS[self.current_trial.start_button])
        if self.canvas.cell_at(position) is None:
            self._finish_attempt(now, "POINTER_LEFT_CANVAS")
        elif self._overlap(self._buttons_down):
            self._finish_attempt(now, "BUTTON_OVERLAP")
        elif self._buttons_down != expected_buttons:
            self._finish_attempt(now, "PROTOCOL_STATE")

    def interrupt(self, reason):
        if self.state == TrialState.ACTIVE:
            self._finish_attempt(self.clock_ns(), reason)

    def _finish_attempt(self, now, reason, target_position=None):
        record = self._attempt
        if target_position is not None:
            record["target_press_ns"] = now
            record["target_press_px"] = target_position
            record["duration_ns"] = now - record["start_press_ns"]
            self._sample(now, target_position, "target")
            if reason is None and record["duration_ns"] <= 0:
                reason = "NON_POSITIVE_DURATION"
        if reason is None and record["trial_id"] in self.writer.accepted_ids:
            reason = "PROTOCOL_STATE"
        record.update(end_ns=now, valid=reason is None, invalid_reason=reason)
        try:
            self.writer.append_attempt(record)
        except (OSError, ValueError) as exc:
            self._storage_failure(exc)
            return
        self._attempt = None
        self._awaiting_release = bool(self._buttons_down)
        if reason is not None:
            self.state = TrialState.READY
            self._refresh(f"무효: {reason} · 같은 trial을 다시 시도하세요.")
            return
        previous = self.current_trial
        self.trial_index += 1
        if self.current_trial is None:
            expected = {t.trial_id for t in self.manifest.trials}
            self.state = TrialState.FINISHED
            if self.writer.accepted_ids != expected:
                self._storage_failure(ValueError("Incomplete accepted trial set."))
                return
            try:
                self.writer.close("COMPLETED")
            except (OSError, ValueError) as exc:
                self._storage_failure(exc)
                return
        elif (previous.phase, previous.block_index) != (self.current_trial.phase, self.current_trial.block_index):
            self.state = TrialState.BLOCK_COMPLETE
        else:
            self.state = TrialState.READY
        self._refresh()

    def _storage_failure(self, exc):
        self.storage_error = str(exc)
        self.state = TrialState.FINISHED
        self._refresh(f"저장 오류 · 수집 중지: {exc}")
        print(f"Calibration collection stopped: {exc}", file=sys.stderr)

    def rearm_after_external_release(self):
        if self.state == TrialState.READY and self._awaiting_release:
            self._buttons_down = int(QApplication.mouseButtons())
            self._awaiting_release = bool(self._buttons_down)

    def continue_block(self):
        if self.state == TrialState.BLOCK_COMPLETE and not QApplication.mouseButtons():
            self._awaiting_release = False
            self.state = TrialState.READY
            self._refresh()
            self.canvas.setFocus()

    def event(self, event):
        if hasattr(self, "state"):
            if event.type() == QEvent.WindowDeactivate:
                self.interrupt("WINDOW_DEACTIVATED")
            elif event.type() == QEvent.WindowActivate:
                self.rearm_after_external_release()
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.interrupt("MANUAL_INTERRUPT")
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.interrupt("WINDOW_CLOSED")
        try:
            self.writer.close("FAILED" if self.storage_error else "ABORTED")
        except (OSError, ValueError) as exc:
            self._storage_failure(exc)
        event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--notes", default="", help="Optional mouse device / pointer setting notes")
    args = parser.parse_args(argv)
    app = QApplication([sys.argv[0]])
    try:
        window = CalibrationWindow(output_dir=args.output_dir, notes=args.notes)
    except (OSError, ValueError) as exc:
        print(f"Cannot start calibration: {exc}", file=sys.stderr)
        return 1
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
