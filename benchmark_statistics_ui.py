"""Read-only auxiliary benchmark viewer. Aggregation belongs to the backend."""

import sqlite3
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QTabWidget,
    QVBoxLayout, QWidget,
)
import pyqtgraph as pg

import benchmark_statistics as statistics
import benchmark_statistics_presentation as presentation
from telemetry_repository import connect_database_readonly


_SECTIONS = (
    ("identity", ("run_id", "created_at", "benchmark_set_id", "solver_stage", "solver_policy",
                  "board_size", "num_mines", "first_click_policy", "board_generator_version",
                  "telemetry_schema_version")),
    ("coverage", ("run_status", "requested_games", "processed_games", "stored_game_count",
                  "exact_processed_prefix", "exact_requested_prefix", "git_dirty", "official_eligible")),
    ("results", ("wins", "losses", "win_rate", "games_with_probability_guess",
                 "guess_game_rate", "mean_guess_count")),
    ("actions", ("local_deterministic_count", "global_certainty_count", "probability_guess_count",
                 "total_actions", "open_count", "flag_count", "chord_count")),
    ("timing", ("compute_time_total_ns", "decision_compute_count", "mean_decision_compute_ns",
                "max_decision_compute_ns", "p50", "p90", "p95", "p99")),
)
_READ_ERRORS = (sqlite3.Error, OSError, ValueError, OverflowError)


class _ProbabilityPercentAxis(pg.AxisItem):
    """Keep PyQtGraph's zoom-sensitive tick precision and append percent units."""

    def tickStrings(self, values, scale, spacing):
        return [f"{label}%" for label in super().tickStrings(values, scale, spacing)]


class BenchmarkStatisticsWindow(QDialog):
    """Own one read-only connection and the currently displayed result.

    No query cache: selection queries the backend synchronously. Language changes
    only relabel the existing result and plot items. Failed opens retain the last
    usable database; failed run queries clear the prior result to avoid mislabeling.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.resize(1040, 780)
        self.language = presentation.DEFAULT_LANGUAGE
        self.connection = None
        self.database_path = None
        self.runs = ()
        self.current_statistics = None
        self.guess_points = ()
        self.risk_points = ()
        self.board_points = ()
        self._error = None
        self._labels = {}
        self.value_labels = {}
        self._groups = {}
        self._build_ui()
        self._translate()

    @property
    def selected_run_id(self):
        return self.run_combo.currentData()

    def _text(self, key):
        return presentation.text(key, self.language)

    def _label(self, key):
        label = QLabel()
        label.setTextFormat(Qt.PlainText)
        self._labels[key] = label
        return label

    def _build_ui(self):
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.open_button = QPushButton()
        self.open_button.clicked.connect(self._choose_database)
        toolbar.addWidget(self.open_button)
        toolbar.addStretch()
        toolbar.addWidget(self._label("language"))
        self.language_combo = QComboBox()
        self.language_combo.addItem("한국어", "ko")
        self.language_combo.addItem("English", "en")
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        toolbar.addWidget(self.language_combo)
        layout.addLayout(toolbar)

        database_row = QHBoxLayout()
        database_row.addWidget(self._label("database"))
        self.path_label = QLabel()
        self.path_label.setTextFormat(Qt.PlainText)
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        database_row.addWidget(self.path_label, 1)
        layout.addLayout(database_row)
        run_row = QHBoxLayout()
        run_row.addWidget(self._label("run"))
        self.run_combo = QComboBox()
        self.run_combo.setEnabled(False)
        self.run_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.run_combo.setMinimumContentsLength(25)
        self.run_combo.currentIndexChanged.connect(self._run_changed)
        run_row.addWidget(self.run_combo, 1)
        layout.addLayout(run_row)

        self.state_label = QLabel()
        self.state_label.setTextFormat(Qt.PlainText)
        layout.addWidget(self.state_label)
        self.error_label = QLabel()
        self.error_label.setTextFormat(Qt.PlainText)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #a12622;")
        layout.addWidget(self.error_label)
        layout.addWidget(self._label("readonly_note"))

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        summary = QWidget()
        grid = QGridLayout(summary)
        positions = ((0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1), (2, 0, 1, 1), (2, 1, 1, 1))
        for (section, fields), position in zip(_SECTIONS, positions):
            group = QGroupBox()
            self._groups[section] = group
            form = QFormLayout(group)
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            for key in fields:
                value = QLabel("—")
                value.setTextFormat(Qt.PlainText)
                value.setWordWrap(True)
                value.setTextInteractionFlags(Qt.TextSelectableByMouse)
                self.value_labels[key] = value
                form.addRow(self._label(key), value)
            if section == "timing":
                note = self._label("timing_note")
                note.setWordWrap(True)
                form.addRow(note)
            grid.addWidget(group, *position)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(summary)
        self.tabs.addTab(scroll, "")

        self.guess_plot = self._plot()
        self.guess_plot.setMouseEnabled(x=False, y=False)
        self.guess_bars = pg.BarGraphItem(x=[], height=[], width=0.8, brush="#3b78ac")
        self.guess_plot.addItem(self.guess_bars)
        self.tabs.addTab(self.guess_plot, "")

        risk_page = QWidget()
        risk_layout = QVBoxLayout(risk_page)
        risk_note = self._label("risk_note")
        risk_note.setWordWrap(True)
        risk_layout.addWidget(risk_note)
        self.risk_plot = self._plot(bottom_axis=_ProbabilityPercentAxis("bottom"))
        self.risk_scatter = pg.ScatterPlotItem(
            size=9, pen=pg.mkPen("#20547e"), brush=pg.mkBrush("#4b8fbc"),
            hoverable=True, hoverSize=12,
            tip=lambda x, y, data: presentation.probability_detail(data, self.language),
        )
        self.risk_scatter.sigClicked.connect(self._risk_clicked)
        self.risk_plot.addItem(self.risk_scatter)
        risk_layout.addWidget(self.risk_plot, 1)
        detail_row = QHBoxLayout()
        detail_row.addWidget(self._label("exact_risk"))
        self.risk_combo = QComboBox()
        self.risk_combo.setEnabled(False)
        self.risk_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.risk_combo.setMinimumContentsLength(20)
        self.risk_combo.currentIndexChanged.connect(self._update_risk_detail)
        detail_row.addWidget(self.risk_combo, 1)
        risk_layout.addLayout(detail_row)
        self.risk_detail_label = QLabel()
        self.risk_detail_label.setTextFormat(Qt.PlainText)
        self.risk_detail_label.setWordWrap(True)
        self.risk_detail_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.risk_detail_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        risk_layout.addWidget(self.risk_detail_label)
        self.tabs.addTab(risk_page, "")

        self.board_plot = self._plot()
        self.board_plot.setMouseEnabled(x=False, y=False)
        self.board_bars = pg.BarGraphItem(x=[], height=[], width=0.8, brush="#558b61")
        self.board_plot.addItem(self.board_bars)
        self.tabs.addTab(self.board_plot, "")

    @staticmethod
    def _plot(*, bottom_axis=None):
        axes = {"bottom": bottom_axis} if bottom_axis is not None else None
        plot = pg.PlotWidget(background="w", enableMenu=False, axisItems=axes)
        plot.hideButtons()
        plot.showGrid(x=True, y=True, alpha=0.15)
        for axis in ("left", "bottom"):
            plot.getAxis(axis).setPen("#444444")
            plot.getAxis(axis).setTextPen("#303030")
            plot.getAxis(axis).enableAutoSIPrefix(False)
        return plot

    def _choose_database(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self._text("open_database"), str(self.database_path or ""),
            self._text("database_filter"),
        )
        if path:
            self.open_database(path)

    def open_database(self, path):
        """Stage a usable replacement before releasing the old UI-owned reader."""
        candidate = None
        try:
            candidate = connect_database_readonly(path)
            runs = statistics.list_benchmark_runs(candidate)
            result = statistics.calculate_run_statistics(candidate, runs[0].run_id) if runs else None
        except _READ_ERRORS as error:
            if candidate is not None:
                candidate.close()
            self._error = ("error", str(error))
            self._render_status()
            return False

        self._close_connection()
        self.connection = candidate
        self.database_path = Path(path).resolve()
        self.runs = runs
        self.run_combo.blockSignals(True)
        try:
            self.run_combo.clear()
            for run in runs:
                self.run_combo.addItem(
                    f"#{run.run_id} · {run.benchmark_set_id} · {run.solver_stage} · {run.run_status}",
                    run.run_id,
                )
        finally:
            self.run_combo.blockSignals(False)
        self.run_combo.setEnabled(bool(runs))
        self._error = None
        self._set_statistics(result)
        return True

    def _run_changed(self, index):
        if self.connection is None or index < 0:
            return
        try:
            result = statistics.calculate_run_statistics(self.connection, self.selected_run_id)
        except _READ_ERRORS as error:
            self._error = ("query_error", str(error))
            self._set_statistics(None)
            return
        self._error = None
        self._set_statistics(result)

    def _set_statistics(self, result):
        self.current_statistics = result
        self.guess_points = presentation.discrete_points(result.guess_count_distribution) if result else ()
        self.risk_points = presentation.probability_points(result.probability_guess_distribution) if result else ()
        self.board_points = presentation.discrete_points(result.board_3bv_distribution) if result else ()
        for plot, bars, points in (
            (self.guess_plot, self.guess_bars, self.guess_points),
            (self.board_plot, self.board_bars, self.board_points),
        ):
            bars.setOpts(x=[point.x for point in points], height=[point.count for point in points])
            plot.autoRange()
        self.risk_scatter.setData(
            x=[point.x for point in self.risk_points], y=[point.count for point in self.risk_points],
            data=self.risk_points,
        )
        self.risk_plot.autoRange()
        self.risk_plot.setXRange(0, 100, padding=0.02)
        self.risk_combo.blockSignals(True)
        try:
            self.risk_combo.clear()
            for point in self.risk_points:
                self.risk_combo.addItem(point.exact_label)
        finally:
            self.risk_combo.blockSignals(False)
        self.risk_combo.setEnabled(bool(self.risk_points))
        self._render_values()
        self._render_status()
        self._update_risk_detail()

    def _render_values(self):
        values = {}
        run = next((run for run in self.runs if run.run_id == self.selected_run_id), None)
        if run:
            values.update(vars(run))
            values["board_size"] = f"{run.width} × {run.height}"
        result = self.current_statistics
        if result:
            values.update(vars(result))
            values.update(vars(result.coverage))
            for key in ("win_rate", "guess_game_rate"):
                values[key] = presentation.format_rate(values[key])
            values["mean_guess_count"] = presentation.format_mean(result.mean_guess_count)
            for key in ("compute_time_total_ns", "mean_decision_compute_ns", "max_decision_compute_ns"):
                values[key] = presentation.format_nanoseconds(values[key])
            for percentile, value in result.decision_compute_percentiles_ns:
                values[f"p{percentile}"] = presentation.format_nanoseconds(value)
        for key, label in self.value_labels.items():
            value = values.get(key)
            label.setText(self._text("yes" if value else "no") if isinstance(value, bool)
                          else "—" if value is None else str(value))

    def _render_status(self):
        self.path_label.setText(str(self.database_path) if self.database_path else "—")
        self.error_label.setText(
            f"{self._text(self._error[0])}: {self._error[1]}" if self._error else ""
        )
        self.error_label.setVisible(self._error is not None)
        result = self.current_statistics
        if result:
            official = result.coverage.official_eligible
            self.state_label.setText(self._text("official" if official else "diagnostic"))
            self.state_label.setStyleSheet(
                "font-weight: bold; padding: 6px; color: "
                + ("#185d2a; background: #e6f3e9;" if official else "#744500; background: #fff0d4;")
            )
        else:
            key = ("no_database" if self.connection is None else
                   "empty_database" if not self.runs else "query_error")
            self.state_label.setText(self._text(key))
            self.state_label.setStyleSheet("")

    def _language_changed(self, index):
        self.language = self.language_combo.itemData(index)
        self._translate()

    def _translate(self):
        self.setWindowTitle(self._text("title"))
        self.open_button.setText(self._text("open_database"))
        for key, label in self._labels.items():
            label.setText(self._text(key))
        for key, group in self._groups.items():
            group.setTitle(self._text(key))
        for index, key in enumerate(("summary", "guess_graph", "risk_graph", "board_graph")):
            self.tabs.setTabText(index, self._text(key))
        for plot, x_key, y_key in (
            (self.guess_plot, "guess_x", "game_count"),
            (self.risk_plot, "risk_x", "event_count"),
            (self.board_plot, "board_x", "game_count"),
        ):
            plot.setLabel("bottom", self._text(x_key))
            plot.setLabel("left", self._text(y_key))
        self._render_values()
        self._render_status()
        self._update_risk_detail()

    def _risk_clicked(self, item, points, event):
        if points:
            self.risk_combo.setCurrentIndex(self.risk_points.index(points[0].data()))

    def _update_risk_detail(self, index=None):
        index = self.risk_combo.currentIndex()
        self.risk_detail_label.setText(
            presentation.probability_detail(self.risk_points[index], self.language)
            if index >= 0 else self._text("no_points")
        )

    def _close_connection(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _clear_database(self):
        self._close_connection()
        self.database_path = None
        self.runs = ()
        self.run_combo.clear()
        self.run_combo.setEnabled(False)
        self._error = None
        self._set_statistics(None)

    def closeEvent(self, event):
        # Qt need not call done() when closing a dialog that was never shown.
        self._clear_database()
        super().closeEvent(event)

    def done(self, result):
        """Also release the reader for Escape and programmatic reject/accept."""
        self._clear_database()
        super().done(result)
