from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath
from PyQt5.QtWidgets import QHBoxLayout, QSizePolicy, QWidget


_STAGES = ["FIX", "CUE", "IMAG", "REST", "ITI"]
_LABELS = ["注视期", "提示期", "想象期", "休息期", "间隔"]

_COLOR_ACTIVE   = QColor("#0078D4")
_COLOR_DONE     = QColor("#107C10")
_COLOR_INACTIVE = QColor("#EDEBE9")
_COLOR_TEXT_ON  = QColor("#FFFFFF")
_COLOR_TEXT_OFF = QColor("#A19F9D")


class _Pill(QWidget):
    """Single stage pill indicator."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label  = label
        self._active = False
        self.setFixedHeight(28)
        self.setMinimumWidth(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 14, 14)

        if self._active:
            p.fillPath(path, _COLOR_ACTIVE)
            p.setPen(_COLOR_TEXT_ON)
        else:
            p.fillPath(path, _COLOR_INACTIVE)
            p.setPen(_COLOR_TEXT_OFF)

        font = QFont("Microsoft YaHei", 10, QFont.Bold if self._active else QFont.Normal)
        p.setFont(font)
        p.drawText(QRectF(self.rect()), Qt.AlignCenter, self._label)


class _Connector(QWidget):
    """Thin horizontal line connector between pills."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(16)
        self.setFixedHeight(28)
        self._lit = False

    def set_lit(self, lit: bool) -> None:
        self._lit = lit
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = _COLOR_ACTIVE if self._lit else _COLOR_INACTIVE
        cy = self.height() // 2
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRect(2, cy - 1, self.width() - 4, 2)


class StageBar(QWidget):
    """Pill-style paradigm stage progress bar."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pills: list[_Pill] = []
        self._connectors: list[_Connector] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        for i, label in enumerate(_LABELS):
            pill = _Pill(label, self)
            self._pills.append(pill)
            layout.addWidget(pill)
            if i < len(_LABELS) - 1:
                conn = _Connector(self)
                self._connectors.append(conn)
                layout.addWidget(conn)

        layout.addStretch()

    def highlight(self, state: str) -> None:
        state_upper = state.upper()
        try:
            active_idx = _STAGES.index(state_upper)
        except ValueError:
            active_idx = -1

        for i, pill in enumerate(self._pills):
            pill.set_active(i == active_idx)
        for i, conn in enumerate(self._connectors):
            conn.set_lit(i < active_idx)

    def reset(self) -> None:
        for pill in self._pills:
            pill.set_active(False)
        for conn in self._connectors:
            conn.set_lit(False)
