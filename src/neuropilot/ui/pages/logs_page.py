from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    ComboBox,
    LineEdit,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
)


class _LogSink:
    """Loguru-compatible sink that forwards to a QPlainTextEdit."""

    def __init__(self, widget: QPlainTextEdit) -> None:
        self._widget = widget

    def write(self, message: str) -> None:
        # loguru message objects have a str representation
        try:
            text = str(message).rstrip("\n")
            self._widget.appendPlainText(text)
        except RuntimeError:
            pass  # widget already destroyed


class LogsPage(QWidget):
    """Live log viewer with level filter and keyword search.

    Adds a loguru sink on construction so all subsequent log messages
    appear in real time.  Uses QDesktopServices to open the log directory.
    """

    _LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]

    def __init__(
        self,
        log_dir: Optional[str | Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._log_dir = Path(log_dir) if log_dir else None
        self._sink_id: Optional[int] = None
        self._setup_ui()
        self._install_sink()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(8)
        root.addWidget(SubtitleLabel("运行日志"))

        # Controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(StrongBodyLabel("级别"))
        self._level_box = ComboBox()
        for lvl in self._LEVELS:
            self._level_box.addItem(lvl)
        self._level_box.setCurrentIndex(1)  # INFO default
        self._level_box.currentIndexChanged.connect(self._apply_filter)
        ctrl.addWidget(self._level_box)

        ctrl.addWidget(StrongBodyLabel("关键词"))
        self._search_edit = LineEdit()
        self._search_edit.setPlaceholderText("过滤关键词…")
        self._search_edit.textChanged.connect(self._apply_filter)
        ctrl.addWidget(self._search_edit, stretch=1)

        self._btn_clear = PushButton("清空")
        self._btn_clear.clicked.connect(self._log_view.clear if hasattr(self, "_log_view") else lambda: None)
        ctrl.addWidget(self._btn_clear)

        self._btn_export = PushButton("导出")
        self._btn_export.clicked.connect(self._export)
        ctrl.addWidget(self._btn_export)

        if self._log_dir:
            self._btn_open_dir = PushButton("打开目录")
            self._btn_open_dir.clicked.connect(self._open_log_dir)
            ctrl.addWidget(self._btn_open_dir)

        root.addLayout(ctrl)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.document().setMaximumBlockCount(2000)
        self._log_view.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        root.addWidget(self._log_view, stretch=1)

        # Fix button clear connection after widget is created
        self._btn_clear.clicked.disconnect()
        self._btn_clear.clicked.connect(self._log_view.clear)

    def _install_sink(self) -> None:
        try:
            from loguru import logger
            sink = _LogSink(self._log_view)
            self._sink_id = logger.add(
                sink.write,
                format="{time:HH:mm:ss} | {level:<7} | {message}",
                level="DEBUG",
                colorize=False,
            )
        except Exception:
            pass

    def _apply_filter(self) -> None:
        # Simple approach: hide lines not matching current filter
        # (full refilter on change — acceptable for ≤2000 lines)
        level = self._level_box.currentText()
        keyword = self._search_edit.text().lower()
        text = self._log_view.toPlainText()
        lines = text.splitlines()

        _LEVEL_ORDER = {lvl: i for i, lvl in enumerate(self._LEVELS)}
        min_ord = _LEVEL_ORDER.get(level, 0)

        visible: list[str] = []
        for line in lines:
            line_lvl = next(
                (lvl for lvl in self._LEVELS if lvl in line), "DEBUG"
            )
            if _LEVEL_ORDER.get(line_lvl, 0) < min_ord:
                continue
            if keyword and keyword not in line.lower():
                continue
            visible.append(line)

        self._log_view.setPlainText("\n".join(visible))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "neuropilot.log", "文本文件 (*.log *.txt)"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self._log_view.toPlainText())

    def _open_log_dir(self) -> None:
        if self._log_dir and self._log_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._log_dir)))

    def closeEvent(self, event: object) -> None:
        if self._sink_id is not None:
            try:
                from loguru import logger
                logger.remove(self._sink_id)
            except Exception:
                pass
        super().closeEvent(event)  # type: ignore[misc]
