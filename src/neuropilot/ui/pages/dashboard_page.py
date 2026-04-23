from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import SubtitleLabel

from neuropilot.app.event_bus import EventBus
from neuropilot.ui.theme import COLOR_BORDER, COLOR_TEXT_SECONDARY
from neuropilot.ui.widgets.status_panel import StatusPanel

try:
    import pyqtgraph as pg
    _HAS_PG = True
except ImportError:
    _HAS_PG = False

_Y_MIN = -500.0
_Y_MAX = 500.0
_WINDOW_SECS = 4.0
_DEFAULT_SRATE = 250.0
_DEFAULT_CH = 8
_COLORS = [
    "#4A9EFF", "#22D3A5", "#F59E0B", "#EF4444",
    "#A78BFA", "#34D399", "#FB923C", "#60A5FA",
]


class DashboardPage(QWidget):
    """实时 EEG 波形总览页.

    布局：StatusPanel（状态监控）+ pyqtgraph 波形区。
    状态数据全部来自 EventBus，不依赖 main_window 直接调用。
    """

    def __init__(self, cfg: object | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self._srate = float(getattr(cfg, "eeg_sample_rate", _DEFAULT_SRATE)) if cfg else _DEFAULT_SRATE
        self._n_ch = int(getattr(cfg, "eeg_channels", _DEFAULT_CH)) if cfg else _DEFAULT_CH
        self._buf: Optional[np.ndarray] = None
        self._curves: list = []
        self._setup_ui()
        bus = EventBus.instance()
        bus.eeg_samples.connect(self._on_samples)
        bus.eeg_disconnected.connect(self._on_disconnected)
        bus.eeg_session_started.connect(self._on_session_started)

    def apply_runtime_config(self, cfg: object) -> None:
        """更新配置默认值（仅影响未连接时的默认通道数/采样率）。"""
        self._cfg = cfg
        self._srate = float(getattr(cfg, "eeg_sample_rate", self._srate))
        target_ch = int(getattr(cfg, "eeg_channels", self._n_ch))
        if target_ch != self._n_ch:
            self._n_ch = target_ch
            self._buf = None
            if _HAS_PG:
                self._build_curves(self._n_ch)

    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # ── 标题 ──────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_row.addWidget(SubtitleLabel("实时 EEG 监视器"))
        title_row.addStretch()
        root.addLayout(title_row)

        # ── 状态监控面板（替代原来的分散状态卡片）───────────────
        self._status_panel = StatusPanel(self)
        root.addWidget(self._status_panel)

        # ── EEG 波形区域 ─────────────────────────────────────────
        if not _HAS_PG:
            root.addWidget(QLabel("pyqtgraph 未安装，无法显示波形"))
            return

        pg.setConfigOptions(antialias=True, useOpenGL=False)
        self._plot_widget = pg.GraphicsLayoutWidget()
        self._plot_widget.setBackground("#FFFFFF")
        self._plot_widget.setStyleSheet(
            f"border: 1px solid {COLOR_BORDER}; border-radius: 8px;"
        )
        root.addWidget(self._plot_widget, stretch=1)

        self._plot = self._plot_widget.addPlot()
        self._plot.setLabel("left", "µV", color=COLOR_TEXT_SECONDARY, size="11pt")
        self._plot.setLabel("bottom", "时间 / s", color=COLOR_TEXT_SECONDARY, size="11pt")
        self._plot.setYRange(_Y_MIN, _Y_MAX, padding=0)
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.getAxis("left").setStyle(tickTextOffset=6)
        self._plot.getAxis("left").setPen(pg.mkPen(COLOR_BORDER))
        self._plot.getAxis("bottom").setPen(pg.mkPen(COLOR_BORDER))
        self._plot.getAxis("left").setTextPen(pg.mkPen(COLOR_TEXT_SECONDARY))
        self._plot.getAxis("bottom").setTextPen(pg.mkPen(COLOR_TEXT_SECONDARY))

        self._build_curves(self._n_ch)

    def _build_curves(self, n_ch: int) -> None:
        if not _HAS_PG:
            return
        self._plot.clear()
        self._curves = []
        offset_step = (_Y_MAX - _Y_MIN) / max(n_ch, 1)
        for i in range(n_ch):
            color = _COLORS[i % len(_COLORS)]
            offset = (n_ch - 1 - i) * offset_step + _Y_MIN + offset_step * 0.5
            curve = self._plot.plot(pen=pg.mkPen(color, width=1.2))
            curve._ch_offset = offset  # type: ignore[attr-defined]
            self._curves.append(curve)

    # ------------------------------------------------------------------
    def _on_session_started(self, session_id: int, n_channels: int, srate: float) -> None:
        """EEG session 建立后同步通道数和采样率到波形区。"""
        if srate > 0:
            self._srate = srate
        if n_channels > 0 and n_channels != self._n_ch:
            self._n_ch = n_channels
            self._buf = None
            if _HAS_PG:
                self._build_curves(n_channels)

    def _on_disconnected(self) -> None:
        self._buf = None
        if _HAS_PG and self._curves:
            for c in self._curves:
                c.setData([], [])

    def _on_samples(self, data: np.ndarray) -> None:
        if not _HAS_PG or data is None or len(data) == 0:
            return

        n_ch = data.shape[1] if data.ndim == 2 else 1
        if n_ch != self._n_ch or self._buf is None:
            self._n_ch = n_ch
            self._buf = np.zeros((0, n_ch), dtype=np.float32)
            self._build_curves(n_ch)

        if data.ndim == 1:
            data = data[:, np.newaxis]

        self._buf = np.concatenate([self._buf, data], axis=0)  # type: ignore[arg-type]
        window = int(self._srate * _WINDOW_SECS)
        if len(self._buf) > window:
            self._buf = self._buf[-window:]

        t = np.arange(len(self._buf)) / self._srate - _WINDOW_SECS
        for i, curve in enumerate(self._curves):
            if i >= self._buf.shape[1]:
                break
            ch_data = np.clip(self._buf[:, i], _Y_MIN, _Y_MAX)
            curve.setData(t, ch_data)
