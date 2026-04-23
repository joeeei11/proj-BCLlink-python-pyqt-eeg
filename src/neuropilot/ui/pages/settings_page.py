from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
)

from neuropilot.infra.config import AppSettings, save_local_settings

_EEG_TRANSPORTS = ["demo", "synthetic", "playback", "serial", "bluetooth", "tcp", "udp", "lsl"]
_DEVICE_TRANSPORTS = ["serial", "bluetooth", "tcp", "udp"]


class SettingsPage(QWidget):
    settings_saved = pyqtSignal(object)

    def __init__(self, cfg: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self._setup_ui()
        self.load_from_settings(cfg)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        root.addWidget(SubtitleLabel("系统设置", self))

        hint = BodyLabel(
            "这里保存 EEG、外设与任务的默认参数，内容会写入 config/local.toml。"
            " 保存后，当前会话可能需要重新连接设备或重新打开页面才能完全生效。",
            self,
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll, stretch=1)

        content = QWidget(scroll)
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)
        scroll.setWidget(content)

        self._build_login_section()
        self._build_eeg_section()
        self._build_device_section()
        self._build_paradigm_section()
        self._content_layout.addStretch()

        btn_row = QHBoxLayout()
        self._btn_reload = PushButton("重新加载当前配置", self)
        self._btn_reload.clicked.connect(lambda: self.load_from_settings(self._cfg))
        btn_row.addWidget(self._btn_reload)

        self._btn_save = PrimaryPushButton("保存设置", self)
        self._btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self._btn_save)
        btn_row.addStretch()
        root.addLayout(btn_row)

    def _build_login_section(self) -> None:
        form = self._add_section(
            "登录策略",
            "配置本地账户登录失败后的锁定策略。",
        )

        self._lock_threshold = QSpinBox(self)
        self._lock_threshold.setRange(1, 20)
        form.addRow("最大失败次数", self._lock_threshold)

        self._lock_minutes = QSpinBox(self)
        self._lock_minutes.setRange(1, 120)
        self._lock_minutes.setSuffix(" 分钟")
        form.addRow("锁定时长", self._lock_minutes)

    def _build_eeg_section(self) -> None:
        form = self._add_section(
            "EEG 默认配置",
            "打开 EEG 页面或重新连接时，会优先使用这些默认参数。",
        )

        self._eeg_transport = ComboBox(self)
        for key in _EEG_TRANSPORTS:
            self._eeg_transport.addItem(key.upper())
        form.addRow("默认传输协议", self._eeg_transport)

        self._eeg_channels = QSpinBox(self)
        self._eeg_channels.setRange(1, 64)
        form.addRow("通道数", self._eeg_channels)

        self._eeg_sample_rate = QSpinBox(self)
        self._eeg_sample_rate.setRange(1, 4096)
        self._eeg_sample_rate.setSuffix(" Hz")
        form.addRow("采样率", self._eeg_sample_rate)

        self._eeg_playback_file = LineEdit(self)
        self._eeg_playback_file.setPlaceholderText("选择或输入 EEG 回放 CSV 文件路径")
        browse_btn = PushButton("浏览", self)
        browse_btn.clicked.connect(self._browse_eeg_playback_file)

        playback_row = QWidget(self)
        playback_layout = QHBoxLayout(playback_row)
        playback_layout.setContentsMargins(0, 0, 0, 0)
        playback_layout.setSpacing(8)
        playback_layout.addWidget(self._eeg_playback_file, stretch=1)
        playback_layout.addWidget(browse_btn)
        form.addRow("回放文件", playback_row)

        self._eeg_serial_port = LineEdit(self)
        form.addRow("串口", self._eeg_serial_port)

        self._eeg_serial_baud = QSpinBox(self)
        self._eeg_serial_baud.setRange(300, 4_000_000)
        form.addRow("串口波特率", self._eeg_serial_baud)

        self._eeg_bluetooth_address = LineEdit(self)
        form.addRow("蓝牙地址", self._eeg_bluetooth_address)

        self._eeg_bluetooth_port = QSpinBox(self)
        self._eeg_bluetooth_port.setRange(1, 30)
        form.addRow("RFCOMM 端口", self._eeg_bluetooth_port)

        self._eeg_tcp_host = LineEdit(self)
        form.addRow("TCP 主机", self._eeg_tcp_host)

        self._eeg_tcp_port = QSpinBox(self)
        self._eeg_tcp_port.setRange(1, 65535)
        form.addRow("TCP 端口", self._eeg_tcp_port)

        self._eeg_udp_host = LineEdit(self)
        form.addRow("UDP 绑定地址", self._eeg_udp_host)

        self._eeg_udp_port = QSpinBox(self)
        self._eeg_udp_port.setRange(1, 65535)
        form.addRow("UDP 端口", self._eeg_udp_port)

        self._eeg_lsl_stream_name = LineEdit(self)
        form.addRow("LSL 流名称", self._eeg_lsl_stream_name)

    def _build_device_section(self) -> None:
        form = self._add_section(
            "外设默认配置",
            "用于假肢手、刺激器等外设的默认连接参数。",
        )

        self._device_transport = ComboBox(self)
        for key in _DEVICE_TRANSPORTS:
            self._device_transport.addItem(key.upper())
        form.addRow("默认传输协议", self._device_transport)

        self._device_serial_port = LineEdit(self)
        form.addRow("串口", self._device_serial_port)

        self._device_serial_baud = QSpinBox(self)
        self._device_serial_baud.setRange(300, 4_000_000)
        form.addRow("串口波特率", self._device_serial_baud)

        self._device_bluetooth_address = LineEdit(self)
        form.addRow("蓝牙地址", self._device_bluetooth_address)

        self._device_bluetooth_port = QSpinBox(self)
        self._device_bluetooth_port.setRange(1, 30)
        form.addRow("RFCOMM 端口", self._device_bluetooth_port)

        self._device_tcp_host = LineEdit(self)
        form.addRow("TCP 主机", self._device_tcp_host)

        self._device_tcp_port = QSpinBox(self)
        self._device_tcp_port.setRange(1, 65535)
        form.addRow("TCP 端口", self._device_tcp_port)

        self._device_udp_host = LineEdit(self)
        form.addRow("UDP 主机", self._device_udp_host)

        self._device_udp_port = QSpinBox(self)
        self._device_udp_port.setRange(1, 65535)
        form.addRow("UDP 端口", self._device_udp_port)

    def _build_paradigm_section(self) -> None:
        form = self._add_section(
            "任务时序",
            "设置运动想象任务页面的默认时序参数。",
        )

        self._paradigm_trials_per_run = QSpinBox(self)
        self._paradigm_trials_per_run.setRange(2, 200)
        form.addRow("每轮试次数", self._paradigm_trials_per_run)

        self._paradigm_fix_duration_ms = QSpinBox(self)
        self._paradigm_fix_duration_ms.setRange(100, 5000)
        self._paradigm_fix_duration_ms.setSuffix(" ms")
        form.addRow("注视时长", self._paradigm_fix_duration_ms)

        self._paradigm_cue_duration_ms = QSpinBox(self)
        self._paradigm_cue_duration_ms.setRange(100, 5000)
        self._paradigm_cue_duration_ms.setSuffix(" ms")
        form.addRow("提示时长", self._paradigm_cue_duration_ms)

        self._paradigm_imagery_duration_ms = QSpinBox(self)
        self._paradigm_imagery_duration_ms.setRange(500, 10000)
        self._paradigm_imagery_duration_ms.setSuffix(" ms")
        form.addRow("想象时长", self._paradigm_imagery_duration_ms)

        self._paradigm_rest_duration_ms = QSpinBox(self)
        self._paradigm_rest_duration_ms.setRange(500, 10000)
        self._paradigm_rest_duration_ms.setSuffix(" ms")
        form.addRow("休息时长", self._paradigm_rest_duration_ms)

        self._paradigm_iti_duration_ms = QSpinBox(self)
        self._paradigm_iti_duration_ms.setRange(100, 5000)
        self._paradigm_iti_duration_ms.setSuffix(" ms")
        form.addRow("试次间隔", self._paradigm_iti_duration_ms)

    def _browse_eeg_playback_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 EEG 回放文件",
            self._eeg_playback_file.text().strip(),
            "CSV 文件 (*.csv);;所有文件 (*.*)",
        )
        if path:
            self._eeg_playback_file.setText(path)

    def _add_section(self, title: str, description: str) -> QFormLayout:
        card = QFrame(self)
        card.setObjectName("settingsCard")
        card.setStyleSheet(
            "#settingsCard { background: rgba(255, 255, 255, 0.92); border: 1px solid #dcdfe6; border-radius: 12px; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        card_layout.addWidget(StrongBodyLabel(title, card))
        desc = BodyLabel(description, card)
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(10)
        card_layout.addLayout(form)
        self._content_layout.addWidget(card)
        return form

    def load_from_settings(self, cfg: AppSettings) -> None:
        self._cfg = cfg

        self._lock_threshold.setValue(int(cfg.lock_threshold))
        self._lock_minutes.setValue(int(cfg.lock_minutes))

        self._set_combo_value(self._eeg_transport, _EEG_TRANSPORTS, cfg.eeg_transport)
        self._eeg_channels.setValue(int(cfg.eeg_channels))
        self._eeg_sample_rate.setValue(int(cfg.eeg_sample_rate))
        self._eeg_playback_file.setText(cfg.eeg_playback_file)
        self._eeg_serial_port.setText(cfg.eeg_serial_port)
        self._eeg_serial_baud.setValue(int(cfg.eeg_serial_baud))
        self._eeg_bluetooth_address.setText(cfg.eeg_bluetooth_address)
        self._eeg_bluetooth_port.setValue(int(cfg.eeg_bluetooth_port))
        self._eeg_tcp_host.setText(cfg.eeg_tcp_host)
        self._eeg_tcp_port.setValue(int(cfg.eeg_tcp_port))
        self._eeg_udp_host.setText(cfg.eeg_udp_host)
        self._eeg_udp_port.setValue(int(cfg.eeg_udp_port))
        self._eeg_lsl_stream_name.setText(cfg.eeg_lsl_stream_name)

        self._set_combo_value(self._device_transport, _DEVICE_TRANSPORTS, cfg.device_transport)
        self._device_serial_port.setText(cfg.device_serial_port)
        self._device_serial_baud.setValue(int(cfg.device_serial_baud))
        self._device_bluetooth_address.setText(cfg.device_bluetooth_address)
        self._device_bluetooth_port.setValue(int(cfg.device_bluetooth_port))
        self._device_tcp_host.setText(cfg.device_tcp_host)
        self._device_tcp_port.setValue(int(cfg.device_tcp_port))
        self._device_udp_host.setText(cfg.device_udp_host)
        self._device_udp_port.setValue(int(cfg.device_udp_port))

        self._paradigm_trials_per_run.setValue(int(cfg.paradigm_trials_per_run))
        self._paradigm_fix_duration_ms.setValue(int(cfg.paradigm_fix_duration_ms))
        self._paradigm_cue_duration_ms.setValue(int(cfg.paradigm_cue_duration_ms))
        self._paradigm_imagery_duration_ms.setValue(int(cfg.paradigm_imagery_duration_ms))
        self._paradigm_rest_duration_ms.setValue(int(cfg.paradigm_rest_duration_ms))
        self._paradigm_iti_duration_ms.setValue(int(cfg.paradigm_iti_duration_ms))

    def _set_combo_value(self, combo: ComboBox, values: list[str], current: str) -> None:
        try:
            combo.setCurrentIndex(values.index(current))
        except ValueError:
            combo.setCurrentIndex(0)

    def _on_save(self) -> None:
        merged = self._cfg.model_dump()
        merged.update(self._collect_values())

        try:
            new_cfg = AppSettings(**merged)
            path = save_local_settings(new_cfg)
        except Exception as exc:
            InfoBar.error(
                "保存失败",
                str(exc),
                parent=self,
                duration=5000,
                position=InfoBarPosition.TOP_RIGHT,
            )
            return

        self._cfg = new_cfg
        self.settings_saved.emit(new_cfg)
        self.load_from_settings(new_cfg)

        InfoBar.success(
            "设置已保存",
            str(Path(path)),
            parent=self,
            duration=3500,
            position=InfoBarPosition.TOP_RIGHT,
        )

    def _collect_values(self) -> dict[str, object]:
        return {
            "lock_threshold": self._lock_threshold.value(),
            "lock_minutes": self._lock_minutes.value(),
            "eeg_transport": _EEG_TRANSPORTS[self._eeg_transport.currentIndex()],
            "eeg_channels": self._eeg_channels.value(),
            "eeg_sample_rate": self._eeg_sample_rate.value(),
            "eeg_playback_file": self._eeg_playback_file.text().strip(),
            "eeg_serial_port": self._eeg_serial_port.text().strip(),
            "eeg_serial_baud": self._eeg_serial_baud.value(),
            "eeg_bluetooth_address": self._eeg_bluetooth_address.text().strip(),
            "eeg_bluetooth_port": self._eeg_bluetooth_port.value(),
            "eeg_tcp_host": self._eeg_tcp_host.text().strip(),
            "eeg_tcp_port": self._eeg_tcp_port.value(),
            "eeg_udp_host": self._eeg_udp_host.text().strip(),
            "eeg_udp_port": self._eeg_udp_port.value(),
            "eeg_lsl_stream_name": self._eeg_lsl_stream_name.text().strip(),
            "device_transport": _DEVICE_TRANSPORTS[self._device_transport.currentIndex()],
            "device_serial_port": self._device_serial_port.text().strip(),
            "device_serial_baud": self._device_serial_baud.value(),
            "device_bluetooth_address": self._device_bluetooth_address.text().strip(),
            "device_bluetooth_port": self._device_bluetooth_port.value(),
            "device_tcp_host": self._device_tcp_host.text().strip(),
            "device_tcp_port": self._device_tcp_port.value(),
            "device_udp_host": self._device_udp_host.text().strip(),
            "device_udp_port": self._device_udp_port.value(),
            "paradigm_trials_per_run": self._paradigm_trials_per_run.value(),
            "paradigm_fix_duration_ms": self._paradigm_fix_duration_ms.value(),
            "paradigm_cue_duration_ms": self._paradigm_cue_duration_ms.value(),
            "paradigm_imagery_duration_ms": self._paradigm_imagery_duration_ms.value(),
            "paradigm_rest_duration_ms": self._paradigm_rest_duration_ms.value(),
            "paradigm_iti_duration_ms": self._paradigm_iti_duration_ms.value(),
        }
