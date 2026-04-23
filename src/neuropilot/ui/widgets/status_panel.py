from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QGridLayout, QLabel, QWidget

from neuropilot.app.event_bus import EventBus
from neuropilot.ui.theme import (
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_SUCCESS,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
)

_CARD_STYLE = (
    f"background: {COLOR_SURFACE}; "
    f"border: 1px solid {COLOR_BORDER}; "
    "border-radius: 8px;"
)

_VALUE_STYLE = f"color: {COLOR_TEXT}; font-size: 13px; font-weight: 600; border: none;"
_MUTED_VALUE_STYLE = (
    f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px; font-weight: 600; border: none;"
)


class StatusPanel(QWidget):
    """轻量 EEG 状态面板。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._session_id: Optional[int] = None
        self._sample_count = 0
        self._setup_ui()
        self._reset_runtime_state()
        self._bind_bus()

    def _setup_ui(self) -> None:
        self.setObjectName("statusPanel")
        self.setStyleSheet(f"#statusPanel {{ {_CARD_STYLE} }}")

        grid = QGridLayout(self)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)

        def _kv(label: str, row: int, col: int) -> QLabel:
            key_label = QLabel(label)
            key_label.setStyleSheet(
                f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; border: none;"
            )
            grid.addWidget(key_label, row * 2, col)

            value_label = QLabel("-")
            value_label.setStyleSheet(_VALUE_STYLE)
            grid.addWidget(value_label, row * 2 + 1, col)
            return value_label

        self._lbl_status = _kv("采集状态", 0, 0)
        self._lbl_transport = _kv("传输协议", 0, 1)
        self._lbl_channels = _kv("通道数", 0, 2)
        self._lbl_srate = _kv("采样率", 0, 3)
        self._lbl_session = _kv("Session ID", 1, 0)
        self._lbl_recording = _kv("录制状态", 1, 1)
        self._lbl_samples = _kv("样本数", 1, 2)
        self._lbl_source = _kv("数据源", 1, 3)

        grid.setColumnStretch(4, 1)

    def _bind_bus(self) -> None:
        bus = EventBus.instance()
        bus.eeg_connected.connect(self._on_eeg_connected)
        bus.eeg_disconnected.connect(self._on_eeg_disconnected)
        bus.eeg_error.connect(self._on_eeg_error)
        bus.eeg_traffic.connect(self._on_eeg_traffic)
        bus.eeg_session_started.connect(self._on_session_started)

    def _reset_runtime_state(self) -> None:
        self._sample_count = 0
        self._lbl_transport.setText("-")
        self._lbl_source.setText("-")
        self._lbl_channels.setText("-")
        self._lbl_srate.setText("-")
        self._lbl_samples.setText("0")
        self.update_session(None)
        self.update_recording(False)
        self._set_status("未连接", COLOR_TEXT_SECONDARY)

    def _set_status(self, text: str, color: str) -> None:
        self._lbl_status.setText(text)
        self._lbl_status.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: 600; border: none;"
        )

    def _set_stream_info(self, n_channels: Optional[int], srate: Optional[float]) -> None:
        self._lbl_channels.setText("-" if n_channels is None else f"{n_channels} ch")
        self._lbl_srate.setText("-" if srate is None else f"{srate:.0f} Hz")

    def update_session(self, session_id: Optional[int]) -> None:
        self._session_id = session_id
        self._lbl_session.setText("-" if session_id is None else str(session_id))

    def update_recording(self, active: bool) -> None:
        if active:
            self._lbl_recording.setText("录制中")
            self._lbl_recording.setStyleSheet(
                f"color: {COLOR_SUCCESS}; font-size: 13px; font-weight: 600; border: none;"
            )
            return

        self._lbl_recording.setText("未录制")
        self._lbl_recording.setStyleSheet(_MUTED_VALUE_STYLE)

    def _on_session_started(self, session_id: int, n_channels: int, srate: float) -> None:
        self.update_session(session_id)
        self._sample_count = 0
        self._lbl_samples.setText("0")
        self._set_stream_info(n_channels, srate)

    def _on_eeg_connected(self, success: bool, transport: str) -> None:
        if not success:
            self._set_status("连接失败", COLOR_ERROR)
            return

        self._set_status("已连接", COLOR_SUCCESS)
        self._lbl_transport.setText(transport.upper())
        self._lbl_source.setText(self._classify_source(transport))
        self.update_recording(True)

    def _on_eeg_disconnected(self) -> None:
        self._reset_runtime_state()

    def _on_eeg_error(self, message: str) -> None:
        del message
        self._set_status("连接错误", COLOR_ERROR)

    def _on_eeg_traffic(self, kind: str, value: object) -> None:
        if kind != "csv_rows":
            return
        self._sample_count = int(value)
        self._lbl_samples.setText(f"{self._sample_count:,}")

    @staticmethod
    def _classify_source(transport: str) -> str:
        mapping = {
            "demo": "仿真 (Demo)",
            "synthetic": "仿真 (Synthetic)",
            "playback": "回放 (Playback)",
            "lsl": "流式 (LSL)",
            "serial": "硬件 (Serial)",
            "bluetooth": "硬件 (Bluetooth)",
            "tcp": "硬件 (TCP)",
            "udp": "硬件 (UDP)",
        }
        return mapping.get(transport.lower(), transport)
