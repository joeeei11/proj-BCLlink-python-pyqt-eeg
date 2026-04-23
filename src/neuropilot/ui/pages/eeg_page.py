from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QFileDialog,
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
from neuropilot.ui.theme import (
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_SURFACE,
    COLOR_TEXT_SECONDARY,
)
from neuropilot.ui.widgets.status_panel import StatusPanel

_TRANSPORT_LABELS = ["Demo", "Synthetic（多频段）", "Playback（回放）", "Serial", "Bluetooth", "TCP", "UDP", "LSL"]
_TRANSPORT_KEYS   = ["demo", "synthetic", "playback", "serial", "bluetooth", "tcp", "udp", "lsl"]

_CARD = (
    f"background: {COLOR_SURFACE}; "
    f"border: 1px solid {COLOR_BORDER}; "
    "border-radius: 8px;"
)


class _StatusDot(QWidget):
    """连接状态小圆圈指示器。"""

    OFF    = "off"
    BUSY   = "busy"
    ONLINE = "online"
    ERROR  = "error"

    _COLORS = {
        OFF:    QColor("#C8C6C4"),
        BUSY:   QColor("#FF8C00"),
        ONLINE: QColor("#107C10"),
        ERROR:  QColor("#D13438"),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = self.OFF
        self.setFixedSize(10, 10)

    def set_state(self, state: str) -> None:
        self._state = state
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self._COLORS.get(self._state, self._COLORS[self.OFF]))
        p.drawEllipse(QRectF(0, 0, 10, 10))


class EEGPage(QWidget):
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
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)
        root.addWidget(SubtitleLabel("脑电采集"))

        # ── 状态监控面板 ──────────────────────────────────────────
        self._status_panel = StatusPanel(self)
        root.addWidget(self._status_panel)

        # ── 协议选择卡片 ─────────────────────────────────────────
        proto_card = QWidget()
        proto_card.setObjectName("protoCard")
        proto_card.setStyleSheet(f"#protoCard {{ {_CARD} }}")
        proto_inner = QVBoxLayout(proto_card)
        proto_inner.setContentsMargins(16, 12, 16, 16)
        proto_inner.setSpacing(12)

        proto_hdr = QHBoxLayout()
        lbl_hdr = StrongBodyLabel("传输协议 / 数据源")
        lbl_hdr.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 600;")
        proto_hdr.addWidget(lbl_hdr)
        proto_hdr.addStretch()
        proto_inner.addLayout(proto_hdr)

        self._mode_box = ComboBox(proto_card)
        for label in _TRANSPORT_LABELS:
            self._mode_box.addItem(label)
        proto_inner.addWidget(self._mode_box)

        self._stack = QStackedWidget(proto_card)
        self._stack.addWidget(self._make_demo_panel())        # 0 demo
        self._stack.addWidget(self._make_synthetic_panel())   # 1 synthetic
        self._stack.addWidget(self._make_playback_panel())    # 2 playback
        self._stack.addWidget(self._make_serial_panel())      # 3 serial
        self._stack.addWidget(self._make_bluetooth_panel())   # 4 bluetooth
        self._stack.addWidget(self._make_tcp_panel())         # 5 tcp
        self._stack.addWidget(self._make_udp_panel())         # 6 udp
        self._stack.addWidget(self._make_lsl_panel())         # 7 lsl
        proto_inner.addWidget(self._stack)

        root.addWidget(proto_card)

        # ── 连接状态卡片 ─────────────────────────────────────────
        conn_card = QWidget()
        conn_card.setObjectName("connCard")
        conn_card.setStyleSheet(f"#connCard {{ {_CARD} }}")
        conn_inner = QHBoxLayout(conn_card)
        conn_inner.setContentsMargins(16, 12, 16, 12)
        conn_inner.setSpacing(10)

        self._dot = _StatusDot(conn_card)
        conn_inner.addWidget(self._dot)

        self._status_lbl = QLabel("未连接", conn_card)
        self._status_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px;")
        conn_inner.addWidget(self._status_lbl)
        conn_inner.addStretch()

        self._btn_connect = PrimaryPushButton("连接", conn_card)
        self._btn_disconnect = PushButton("断开", conn_card)
        self._btn_disconnect.setEnabled(False)
        conn_inner.addWidget(self._btn_connect)
        conn_inner.addWidget(self._btn_disconnect)

        root.addWidget(conn_card)
        root.addStretch()

        self._mode_box.currentIndexChanged.connect(self._stack.setCurrentIndex)
        self._btn_connect.clicked.connect(self._on_connect)
        self._btn_disconnect.clicked.connect(self._on_disconnect)

    # ------------------------------------------------------------------
    # 各协议参数面板
    # ------------------------------------------------------------------

    def _make_demo_panel(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        self._demo_channels = QSpinBox(w)
        self._demo_channels.setRange(1, 64)
        self._demo_srate = QSpinBox(w)
        self._demo_srate.setRange(1, 4096)
        form.addRow(self._lbl("通道数"), self._demo_channels)
        form.addRow(self._lbl("采样率 (Hz)"), self._demo_srate)
        return w

    def _make_synthetic_panel(self) -> QWidget:
        """多频段 EEG 仿真源（alpha/beta/theta/delta/gamma）。"""
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        self._syn_channels = QSpinBox(w)
        self._syn_channels.setRange(1, 64)
        self._syn_srate = QSpinBox(w)
        self._syn_srate.setRange(1, 4096)
        hint = QLabel("● 多频段合成信号，更接近真实 EEG 频谱，适合调试分类器链路")
        hint.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow(self._lbl("通道数"), self._syn_channels)
        form.addRow(self._lbl("采样率 (Hz)"), self._syn_srate)
        form.addRow(hint)
        return w

    def _make_playback_panel(self) -> QWidget:
        """CSV 回放源——回放已录制的 EEG 文件。"""
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)

        file_row = QHBoxLayout()
        self._playback_file = QLineEdit(w)
        self._playback_file.setPlaceholderText("选择 EEG CSV 文件…")
        self._playback_file.setReadOnly(True)
        btn_browse = PushButton("浏览", w)
        btn_browse.setFixedWidth(60)
        btn_browse.clicked.connect(self._browse_playback_file)
        file_row.addWidget(self._playback_file)
        file_row.addWidget(btn_browse)

        hint = QLabel("● 重放已录制的 EEG CSV，无需真实设备即可测试完整主链路")
        hint.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow(self._lbl("回放文件"), file_row)
        form.addRow(hint)
        return w

    def _make_serial_panel(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        self._serial_port = QLineEdit(w)
        self._serial_baud = QSpinBox(w)
        self._serial_baud.setRange(300, 4_000_000)
        form.addRow(self._lbl("串口"), self._serial_port)
        form.addRow(self._lbl("波特率"), self._serial_baud)
        return w

    def _make_bluetooth_panel(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        self._bt_addr = QLineEdit(w)
        self._bt_port_spin = QSpinBox(w)
        self._bt_port_spin.setRange(1, 30)
        form.addRow(self._lbl("蓝牙地址"), self._bt_addr)
        form.addRow(self._lbl("RFCOMM 端口"), self._bt_port_spin)
        return w

    def _make_tcp_panel(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        self._tcp_host = QLineEdit(w)
        self._tcp_port = QSpinBox(w)
        self._tcp_port.setRange(1, 65535)
        form.addRow(self._lbl("主机"), self._tcp_host)
        form.addRow(self._lbl("端口"), self._tcp_port)
        return w

    def _make_udp_panel(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        self._udp_host = QLineEdit(w)
        self._udp_port = QSpinBox(w)
        self._udp_port.setRange(1, 65535)
        form.addRow(self._lbl("绑定地址"), self._udp_host)
        form.addRow(self._lbl("端口"), self._udp_port)
        return w

    def _make_lsl_panel(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        self._lsl_name = QLineEdit(w)
        form.addRow(self._lbl("流名称"), self._lsl_name)
        return w

    @staticmethod
    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    def _browse_playback_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 EEG 回放文件", "", "CSV 文件 (*.csv)"
        )
        if path:
            self._playback_file.setText(path)

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------

    def _apply_config_defaults(self) -> None:
        self._demo_channels.setValue(self._cfg_int("eeg_channels", 8))
        self._demo_srate.setValue(self._cfg_int("eeg_sample_rate", 250))
        self._syn_channels.setValue(self._cfg_int("eeg_channels", 8))
        self._syn_srate.setValue(self._cfg_int("eeg_sample_rate", 250))
        self._playback_file.setText(self._cfg_str("eeg_playback_file", ""))
        self._serial_port.setText(self._cfg_str("eeg_serial_port", "COM3"))
        self._serial_baud.setValue(self._cfg_int("eeg_serial_baud", 115200))
        self._bt_addr.setText(self._cfg_str("eeg_bluetooth_address", ""))
        self._bt_port_spin.setValue(self._cfg_int("eeg_bluetooth_port", 1))
        self._tcp_host.setText(self._cfg_str("eeg_tcp_host", "127.0.0.1"))
        self._tcp_port.setValue(self._cfg_int("eeg_tcp_port", 4000))
        self._udp_host.setText(self._cfg_str("eeg_udp_host", "0.0.0.0"))
        self._udp_port.setValue(self._cfg_int("eeg_udp_port", 4001))
        self._lsl_name.setText(self._cfg_str("eeg_lsl_stream_name", "NeuroPilot"))

        selected = self._cfg_str("eeg_transport", "demo").lower()
        index = _TRANSPORT_KEYS.index(selected) if selected in _TRANSPORT_KEYS else 0
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

    # ------------------------------------------------------------------
    # EventBus
    # ------------------------------------------------------------------

    def _bind_bus(self) -> None:
        bus = EventBus.instance()
        bus.eeg_connected.connect(self._on_eeg_connected)
        bus.eeg_disconnected.connect(self._on_eeg_disconnected)
        bus.eeg_error.connect(self._on_eeg_error)

    def _on_connect(self) -> None:
        transport_key = _TRANSPORT_KEYS[self._mode_box.currentIndex()]
        # playback 协议：未选文件时提前拦截
        if transport_key == "playback" and not self._playback_file.text().strip():
            InfoBar.warning(
                "未选择回放文件",
                "请先点击【浏览】选择一个 EEG CSV 录制文件。",
                parent=self, duration=3000, position=InfoBarPosition.TOP_RIGHT,
            )
            return
        params = self._collect_params(transport_key)
        EventBus.instance().eeg_connect_requested.emit(transport_key, params)
        self._connecting = True
        self._btn_connect.setEnabled(False)
        self._btn_disconnect.setEnabled(True)
        self._status_lbl.setText("连接中…")
        self._status_lbl.setStyleSheet(f"color: {COLOR_PRIMARY}; font-size: 13px;")
        self._dot.set_state(_StatusDot.BUSY)

    def _on_disconnect(self) -> None:
        EventBus.instance().eeg_disconnect_requested.emit()
        self._btn_disconnect.setEnabled(False)
        self._status_lbl.setText("断开中…")
        self._dot.set_state(_StatusDot.BUSY)

    def _collect_params(self, key: str) -> dict:
        if key == "demo":
            return {"n_channels": self._demo_channels.value(), "srate": float(self._demo_srate.value())}
        if key == "synthetic":
            return {"n_channels": self._syn_channels.value(), "srate": float(self._syn_srate.value())}
        if key == "playback":
            return {"file": self._playback_file.text().strip()}
        if key == "serial":
            return {"port": self._serial_port.text().strip(), "baud": self._serial_baud.value()}
        if key == "bluetooth":
            return {"address": self._bt_addr.text().strip(), "port": self._bt_port_spin.value()}
        if key == "tcp":
            return {"host": self._tcp_host.text().strip(), "port": self._tcp_port.value()}
        if key == "udp":
            return {"host": self._udp_host.text().strip(), "port": self._udp_port.value()}
        if key == "lsl":
            return {"stream_name": self._lsl_name.text().strip()}
        return {}

    def _on_eeg_connected(self, success: bool, transport: str) -> None:
        self._connected = success
        self._connecting = False
        if success:
            self._status_lbl.setText(f"已连接  [{transport.upper()}]")
            self._status_lbl.setStyleSheet(f"color: {COLOR_SUCCESS}; font-size: 13px; font-weight: 600;")
            self._dot.set_state(_StatusDot.ONLINE)
            self._btn_connect.setEnabled(False)
            self._btn_disconnect.setEnabled(True)
            InfoBar.success(
                "EEG 已连接", f"协议: {transport}",
                parent=self, duration=2000, position=InfoBarPosition.TOP_RIGHT,
            )
            return

        self._status_lbl.setText(f"连接失败: {transport}")
        self._status_lbl.setStyleSheet(f"color: {COLOR_ERROR}; font-size: 13px;")
        self._dot.set_state(_StatusDot.ERROR)
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)
        InfoBar.error(
            "EEG 连接失败", transport,
            parent=self, duration=4000, position=InfoBarPosition.TOP_RIGHT,
        )

    def _on_eeg_disconnected(self) -> None:
        self._connected = False
        self._connecting = False
        self._status_lbl.setText("未连接")
        self._status_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px;")
        self._dot.set_state(_StatusDot.OFF)
        self._btn_connect.setEnabled(True)
        self._btn_disconnect.setEnabled(False)

    def _on_eeg_error(self, message: str) -> None:
        InfoBar.error(
            "EEG 错误", message,
            parent=self, duration=5000, position=InfoBarPosition.TOP_RIGHT,
        )
        self._on_eeg_disconnected()

    # ------------------------------------------------------------------
    # 给 StatusPanel 提供更新接口
    # ------------------------------------------------------------------

    @property
    def status_panel(self) -> StatusPanel:
        return self._status_panel
