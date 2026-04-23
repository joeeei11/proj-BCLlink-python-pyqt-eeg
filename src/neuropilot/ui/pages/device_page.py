from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QStackedWidget,
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

_TRANSPORT_LABELS = ["Serial", "Bluetooth", "TCP", "UDP"]
_TRANSPORT_KEYS = ["serial", "bluetooth", "tcp", "udp"]


class DevicePage(QWidget):
    def __init__(self, cfg: object | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self._connected = False
        self._connecting = False
        self._setup_ui()
        self._apply_config_defaults()
        self._bind_bus()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(SubtitleLabel("外设控制", self))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self._mode_box = ComboBox(self)
        for label in _TRANSPORT_LABELS:
            self._mode_box.addItem(label)
        form.addRow(StrongBodyLabel("传输协议", self), self._mode_box)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._make_serial_panel())
        self._stack.addWidget(self._make_bluetooth_panel())
        self._stack.addWidget(self._make_tcp_panel())
        self._stack.addWidget(self._make_udp_panel())
        form.addRow("", self._stack)
        root.addLayout(form)

        self._status_lbl = QLabel("未连接", self)
        root.addWidget(self._status_lbl)

        btn_row = QHBoxLayout()
        self._btn_connect = PrimaryPushButton("连接", self)
        self._btn_disconnect = PushButton("断开", self)
        self._btn_disconnect.setEnabled(False)
        btn_row.addWidget(self._btn_connect)
        btn_row.addWidget(self._btn_disconnect)
        btn_row.addStretch()
        root.addLayout(btn_row)
        root.addStretch()

        self._mode_box.currentIndexChanged.connect(self._stack.setCurrentIndex)
        self._btn_connect.clicked.connect(self._on_connect)
        self._btn_disconnect.clicked.connect(self._on_disconnect)

    def _make_serial_panel(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)

        self._serial_port = QLineEdit(widget)
        self._serial_baud = QSpinBox(widget)
        self._serial_baud.setRange(300, 4_000_000)

        form.addRow("串口", self._serial_port)
        form.addRow("波特率", self._serial_baud)
        return widget

    def _make_bluetooth_panel(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)

        self._bt_addr = QLineEdit(widget)
        self._bt_port_spin = QSpinBox(widget)
        self._bt_port_spin.setRange(1, 30)

        form.addRow("蓝牙地址", self._bt_addr)
        form.addRow("RFCOMM 端口", self._bt_port_spin)
        return widget

    def _make_tcp_panel(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)

        self._tcp_host = QLineEdit(widget)
        self._tcp_port = QSpinBox(widget)
        self._tcp_port.setRange(1, 65535)

        form.addRow("主机", self._tcp_host)
        form.addRow("端口", self._tcp_port)
        return widget

    def _make_udp_panel(self) -> QWidget:
        widget = QWidget(self)
        form = QFormLayout(widget)

        self._udp_host = QLineEdit(widget)
        self._udp_port = QSpinBox(widget)
        self._udp_port.setRange(1, 65535)

        form.addRow("主机", self._udp_host)
        form.addRow("端口", self._udp_port)
        return widget

    def _apply_config_defaults(self) -> None:
        self._serial_port.setText(self._cfg_str("device_serial_port", "COM4"))
        self._serial_baud.setValue(self._cfg_int("device_serial_baud", 9600))

        self._bt_addr.setText(self._cfg_str("device_bluetooth_address", ""))
        self._bt_port_spin.setValue(self._cfg_int("device_bluetooth_port", 1))

        self._tcp_host.setText(self._cfg_str("device_tcp_host", "192.168.1.100"))
        self._tcp_port.setValue(self._cfg_int("device_tcp_port", 5000))

        self._udp_host.setText(self._cfg_str("device_udp_host", "192.168.1.100"))
        self._udp_port.setValue(self._cfg_int("device_udp_port", 5001))

        selected_transport = self._cfg_str("device_transport", "serial").lower()
        index = _TRANSPORT_KEYS.index(selected_transport) if selected_transport in _TRANSPORT_KEYS else 0
        self._mode_box.setCurrentIndex(index)
        self._stack.setCurrentIndex(index)

    def apply_runtime_config(self, cfg: object) -> None:
        self._cfg = cfg
        self._apply_config_defaults()

    def _cfg_str(self, name: str, default: str) -> str:
        value = getattr(self._cfg, name, default) if self._cfg is not None else default
        return str(value)

    def _cfg_int(self, name: str, default: int) -> int:
        value = getattr(self._cfg, name, default) if self._cfg is not None else default
        return int(value)

    def _bind_bus(self) -> None:
        bus = EventBus.instance()
        bus.device_connected.connect(self._on_device_connected)
        bus.device_disconnected.connect(self._on_device_disconnected)
        bus.device_error.connect(self._on_device_error)

    def _on_connect(self) -> None:
        transport_key = _TRANSPORT_KEYS[self._mode_box.currentIndex()]
        params = self._collect_params(transport_key)
        EventBus.instance().device_connect_requested.emit(transport_key, params)
        self._connecting = True
        self._btn_connect.setEnabled(False)
        self._btn_disconnect.setEnabled(True)
        self._status_lbl.setText("连接中...")

    def _on_disconnect(self) -> None:
        EventBus.instance().device_disconnect_requested.emit()
        self._btn_disconnect.setEnabled(False)
        self._status_lbl.setText("正在取消连接..." if self._connecting and not self._connected else "断开中...")

    def _collect_params(self, key: str) -> dict:
        if key == "serial":
            return {
                "port": self._serial_port.text().strip(),
                "baud": self._serial_baud.value(),
            }
        if key == "bluetooth":
            return {
                "address": self._bt_addr.text().strip(),
                "port": self._bt_port_spin.value(),
            }
        if key == "tcp":
            return {
                "host": self._tcp_host.text().strip(),
                "port": self._tcp_port.value(),
            }
        if key == "udp":
            return {
                "host": self._udp_host.text().strip(),
                "port": self._udp_port.value(),
            }
        return {}

    def _on_device_connected(self, success: bool, transport: str) -> None:
        self._connected = success
        self._connecting = False
        if success:
            self._status_lbl.setText(f"已连接 [{transport}]")
            self._btn_connect.setEnabled(False)
            self._btn_disconnect.setEnabled(True)
            InfoBar.success(
                "外设已连接",
                f"协议: {transport}",
                parent=self,
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
            )
            return

        self._status_lbl.setText(f"连接失败: {transport}")
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)
        InfoBar.error(
            "外设连接失败",
            transport,
            parent=self,
            duration=4000,
            position=InfoBarPosition.TOP_RIGHT,
        )

    def _on_device_disconnected(self) -> None:
        self._connected = False
        self._connecting = False
        self._status_lbl.setText("未连接")
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)

    def _on_device_error(self, message: str) -> None:
        InfoBar.error(
            "外设错误",
            message,
            parent=self,
            duration=5000,
            position=InfoBarPosition.TOP_RIGHT,
        )
        self._on_device_disconnected()
