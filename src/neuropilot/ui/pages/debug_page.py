from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import (
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
)

from neuropilot.app.event_bus import EventBus


def _bytes_to_display(data: bytes, hex_mode: bool) -> str:
    if hex_mode:
        return " ".join(f"{b:02X}" for b in data)

    parts: list[str] = []
    for b in data:
        if b == ord("\n"):
            parts.append("\\n")
        elif b == ord("\r"):
            parts.append("\\r")
        elif b == ord("\t"):
            parts.append("\\t")
        elif 0x20 <= b < 0x7F:
            parts.append(chr(b))
        else:
            parts.append(f"\\x{b:02X}")
    return "".join(parts)


def _parse_hex_input(text: str) -> bytes:
    normalized = text.replace(" ", "").replace("0x", "").replace("0X", "")
    if len(normalized) % 2 != 0:
        normalized = "0" + normalized
    return bytes.fromhex(normalized)


class DebugPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._hex_mode = False
        self._setup_ui()
        self._bind_bus()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        root.addWidget(SubtitleLabel("调试控制台", self))

        ctrl = QHBoxLayout()
        ctrl.addWidget(StrongBodyLabel("显示模式", self))

        self._hex_switch = SwitchButton(self)
        self._hex_switch.setChecked(False)
        self._hex_switch.checkedChanged.connect(self._on_hex_toggled)
        ctrl.addWidget(self._hex_switch)
        ctrl.addWidget(QWidget(self), 1)

        self._log = QPlainTextEdit(self)
        self._log.setReadOnly(True)
        self._log.document().setMaximumBlockCount(1000)
        self._log.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")

        self._btn_clear = PushButton("清空", self)
        self._btn_clear.clicked.connect(self._log.clear)
        ctrl.addWidget(self._btn_clear)
        root.addLayout(ctrl)
        root.addWidget(self._log, stretch=1)

        send_row = QHBoxLayout()
        send_row.addWidget(StrongBodyLabel("发送", self))

        self._input_mode = ComboBox(self)
        self._input_mode.addItem("ASCII")
        self._input_mode.addItem("HEX")
        send_row.addWidget(self._input_mode)

        self._send_edit = LineEdit(self)
        self._send_edit.setPlaceholderText("输入 ASCII 文本或 HEX 字节，如 4C 0A")
        self._send_edit.returnPressed.connect(self._on_send)
        send_row.addWidget(self._send_edit, stretch=1)

        self._btn_send = PrimaryPushButton("发送", self)
        self._btn_send.clicked.connect(self._on_send)
        send_row.addWidget(self._btn_send)
        root.addLayout(send_row)

    def _bind_bus(self) -> None:
        bus = EventBus.instance()
        bus.device_traffic.connect(self._on_device_traffic)
        bus.eeg_traffic.connect(self._on_eeg_traffic)

    def _on_hex_toggled(self, checked: bool) -> None:
        self._hex_mode = checked

    def _on_device_traffic(self, label: str, data: object) -> None:
        text = _bytes_to_display(data, self._hex_mode) if isinstance(data, bytes) else str(data)
        color = "#00BCD4" if label.upper().startswith("TX") else "#F48FB1"
        self._append(f"[Device {label}]", text, color)

    def _on_eeg_traffic(self, label: str, data: object) -> None:
        color = "#64B5F6" if label.upper() == "INFO" else "#81C784"
        self._append(f"[EEG {label}]", str(data), color)

    def _append(self, prefix: str, text: str, color: str) -> None:
        self._log.appendHtml(f'<span style="color:{color}"><b>{prefix}</b> {text}</span>')

    def _on_send(self) -> None:
        raw = self._send_edit.text().strip()
        if not raw:
            return

        try:
            payload = _parse_hex_input(raw) if self._input_mode.currentText() == "HEX" else (raw + "\n").encode("utf-8")
        except ValueError as exc:
            InfoBar.error(
                "格式错误",
                str(exc),
                parent=self,
                duration=3000,
                position=InfoBarPosition.TOP_RIGHT,
            )
            return

        EventBus.instance().device_send_raw.emit(payload)
        self._append("[TX]", _bytes_to_display(payload, self._hex_mode), "#FFEB3B")
        self._send_edit.clear()
