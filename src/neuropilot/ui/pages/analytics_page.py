from __future__ import annotations

import csv
from typing import Optional

from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    ComboBox,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
)

from neuropilot.app.event_bus import EventBus


class AnalyticsPage(QWidget):
    """Show session and trial-level training analytics."""

    def __init__(
        self,
        session_repo: object = None,
        trial_repo: object = None,
        subject_repo: object = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._session_repo = session_repo
        self._trial_repo = trial_repo
        self._subject_repo = subject_repo
        self._subject_ids: list[int | None] = []
        self._setup_ui()
        self._bind_bus()
        self._reload_subjects()

    def set_repos(
        self,
        *,
        session_repo: object | None = None,
        trial_repo: object | None = None,
        subject_repo: object | None = None,
    ) -> None:
        if session_repo is not None:
            self._session_repo = session_repo
        if trial_repo is not None:
            self._trial_repo = trial_repo
        if subject_repo is not None:
            self._subject_repo = subject_repo
        self._reload_subjects()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(SubtitleLabel("数据分析"))

        controls = QHBoxLayout()
        controls.addWidget(StrongBodyLabel("受试者"))
        self._subject_box = ComboBox()
        self._subject_box.currentIndexChanged.connect(self._refresh)
        controls.addWidget(self._subject_box)

        self._btn_refresh = PrimaryPushButton("刷新")
        self._btn_refresh.clicked.connect(self._refresh)
        controls.addWidget(self._btn_refresh)

        self._btn_export = PushButton("导出 CSV")
        self._btn_export.clicked.connect(self._export)
        controls.addWidget(self._btn_export)
        controls.addStretch()
        root.addLayout(controls)

        self._summary_lbl = QLabel("点击「刷新」加载分析数据。")
        root.addWidget(self._summary_lbl)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["会话 ID", "受试者", "协议", "采样率", "试次数", "准确率"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self._table, stretch=1)

    def _bind_bus(self) -> None:
        bus = EventBus.instance()
        bus.subject_changed.connect(self._reload_subjects)

    def _reload_subjects(self) -> None:
        self._subject_box.blockSignals(True)
        self._subject_box.clear()
        self._subject_ids = [None]
        self._subject_box.addItem("全部受试者")

        if self._subject_repo is not None:
            try:
                subjects = self._subject_repo.list()  # type: ignore[union-attr]
            except Exception:
                subjects = []
            for subject in subjects:
                self._subject_box.addItem(subject.name)
                self._subject_ids.append(subject.id)

        self._subject_box.blockSignals(False)

    def _selected_subject_id(self) -> int | None:
        if not self._subject_ids:
            return None
        index = self._subject_box.currentIndex()
        if index < 0 or index >= len(self._subject_ids):
            return None
        return self._subject_ids[index]

    def _refresh(self) -> None:
        if self._session_repo is None or self._trial_repo is None:
            InfoBar.warning(
                "服务不可用",
                "分析服务尚未配置。",
                parent=self,
                duration=3000,
                position=InfoBarPosition.TOP_RIGHT,
            )
            return

        subject_id = self._selected_subject_id()
        if subject_id is None:
            sessions = self._session_repo.list_all()  # type: ignore[union-attr]
        else:
            sessions = self._session_repo.list_by_subject(subject_id)  # type: ignore[union-attr]

        self._table.setRowCount(0)
        total_trials = 0
        total_correct = 0

        for session in sessions:
            trials = self._trial_repo.list_by_session(session.id)  # type: ignore[union-attr]
            trial_count = len(trials)
            correct_count = sum(
                1
                for trial in trials
                if trial.predicted is not None and trial.label == trial.predicted
            )
            accuracy = correct_count / trial_count if trial_count else None

            total_trials += trial_count
            total_correct += correct_count

            row = self._table.rowCount()
            self._table.insertRow(row)
            values = [
                str(session.id),
                str(session.subject_id),
                str(session.transport or "-"),
                str(session.srate or "-"),
                str(trial_count),
                "-" if accuracy is None else f"{accuracy:.1%}",
            ]
            for column, value in enumerate(values):
                self._table.setItem(row, column, QTableWidgetItem(value))

        overall_accuracy = total_correct / total_trials if total_trials else 0.0
        self._summary_lbl.setText(
            f"会话数: {len(sessions)}  试次数: {total_trials}  准确率: {overall_accuracy:.1%}"
        )

    def _export(self) -> None:
        if self._table.rowCount() == 0:
            InfoBar.warning(
                "暂无数据",
                "导出前请先刷新数据。",
                parent=self,
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出分析 CSV",
            "analytics.csv",
            "CSV (*.csv)",
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            headers = [
                self._table.horizontalHeaderItem(column).text()
                for column in range(self._table.columnCount())
            ]
            writer.writerow(headers)
            for row in range(self._table.rowCount()):
                writer.writerow(
                    [
                        self._table.item(row, column).text()
                        if self._table.item(row, column) is not None
                        else ""
                        for column in range(self._table.columnCount())
                    ]
                )

        InfoBar.success(
            "已导出",
            path,
            parent=self,
            duration=3000,
            position=InfoBarPosition.TOP_RIGHT,
        )
