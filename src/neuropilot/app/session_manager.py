from __future__ import annotations

from typing import Optional

import threading

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from neuropilot.app.connection_config import DeviceConnectionConfig
from neuropilot.app.event_bus import EventBus
from neuropilot.app.transport_connect import ConnectCancelledError, open_transport_with_cancel
from neuropilot.domain.device.commands import DeviceCommand
from neuropilot.domain.device.device_service import DeviceService
from neuropilot.domain.eeg.transports.base import IDeviceTransport


class DeviceConnectWorker(QThread):
    sig_connected = pyqtSignal(object)
    sig_failed = pyqtSignal(str)
    sig_cancelled = pyqtSignal()

    def __init__(
        self,
        transport: IDeviceTransport,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._transport = transport
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()
        try:
            self._transport.close()
        except Exception:
            pass

    def run(self) -> None:
        try:
            open_transport_with_cancel(self._transport, self._cancel_event, total_timeout=5.0)
            service = DeviceService(self._transport)
            service.connect(timeout=0.0)
            if self._cancel_event.is_set():
                service.disconnect()
                self.sig_cancelled.emit()
                return
            self.sig_connected.emit(service)
        except ConnectCancelledError:
            self.sig_cancelled.emit()
        except Exception as exc:
            try:
                self._transport.close()
            except Exception:
                pass
            self.sig_failed.emit(str(exc))


class SessionManager(QObject):
    """协调外设（假肢手/刺激器）连接和命令发送.

    使用 DeviceConnectionConfig 统一构造传输对象（参考 brainflow 输入参数模型）。
    """

    device_auto_send_disabled = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._device_svc: Optional[DeviceService] = None
        self._connect_worker: Optional[DeviceConnectWorker] = None
        self._bind_bus()

    def _bind_bus(self) -> None:
        bus = EventBus.instance()
        bus.device_connect_requested.connect(self._on_connect_requested)
        bus.device_disconnect_requested.connect(self._on_disconnect_requested)
        bus.device_send_raw.connect(self._on_send_raw)
        bus.device_send_command.connect(self._on_send_command)

    def _on_connect_requested(self, transport_key: str, params: dict) -> None:
        from loguru import logger

        bus = EventBus.instance()
        if self._connect_worker is not None:
            return
        try:
            logger.info("外设连接请求. transport={} params={}", transport_key, params)
            dev_cfg = DeviceConnectionConfig.from_key_params(transport_key, params)
            transport = dev_cfg.build_transport()
            worker = DeviceConnectWorker(transport, parent=self)
            worker.sig_connected.connect(
                lambda svc, current=worker, key=transport_key: self._on_connect_succeeded(current, key, svc)
            )
            worker.sig_failed.connect(
                lambda message, current=worker: self._on_connect_failed(current, message)
            )
            worker.sig_cancelled.connect(
                lambda current=worker: self._on_connect_cancelled(current)
            )
            self._connect_worker = worker
            worker.start()
        except Exception as exc:
            bus.device_connected.emit(False, str(exc))

    def _on_disconnect_requested(self) -> None:
        if self._connect_worker is not None:
            worker = self._connect_worker
            self._connect_worker = None
            worker.cancel()
            EventBus.instance().device_disconnected.emit()
            return
        self._disconnect_device()

    def _on_send_raw(self, payload: bytes) -> None:
        if self._device_svc is None:
            return
        ok, reason = self._device_svc.send(payload)
        bus = EventBus.instance()
        bus.device_traffic.emit("TX", payload)
        if not ok and reason not in ("throttled", "未连接"):
            bus.device_error.emit(reason)

    def _on_send_command(self, command: DeviceCommand) -> None:
        if self._device_svc is None:
            return
        ok, reason = self._device_svc.send(command)
        if ok:
            EventBus.instance().device_traffic.emit("TX", command.to_bytes())
        elif reason not in ("throttled",):
            if not self._device_svc.is_connected:
                self._handle_unexpected_disconnect("设备连接丢失")

    def _disconnect_device(self) -> None:
        if self._connect_worker is not None:
            worker = self._connect_worker
            self._connect_worker = None
            worker.cancel()
            EventBus.instance().device_disconnected.emit()
            return
        if self._device_svc is not None:
            try:
                self._device_svc.disconnect()
            except Exception:
                pass
            self._device_svc = None
        EventBus.instance().device_disconnected.emit()

    def _handle_unexpected_disconnect(self, reason: str) -> None:
        self._disconnect_device()
        self.device_auto_send_disabled.emit(reason)
        from qfluentwidgets import InfoBar, InfoBarPosition
        from PyQt5.QtWidgets import QApplication
        parent_widget = QApplication.activeWindow()
        if parent_widget is not None:
            InfoBar.warning(
                "外设断开", reason, parent=parent_widget,
                duration=5000, position=InfoBarPosition.TOP_RIGHT,
            )

    @property
    def device_service(self) -> Optional[DeviceService]:
        return self._device_svc

    def _on_connect_succeeded(
        self,
        worker: DeviceConnectWorker,
        transport_key: str,
        service: object,
    ) -> None:
        if worker is not self._connect_worker:
            if isinstance(service, DeviceService):
                service.disconnect()
            return
        self._connect_worker = None
        self._device_svc = service if isinstance(service, DeviceService) else None
        EventBus.instance().device_connected.emit(True, transport_key)

    def _on_connect_failed(self, worker: DeviceConnectWorker, message: str) -> None:
        if worker is not self._connect_worker:
            return
        self._connect_worker = None
        EventBus.instance().device_connected.emit(False, message)

    def _on_connect_cancelled(self, worker: DeviceConnectWorker) -> None:
        if worker is not self._connect_worker:
            return
        self._connect_worker = None
        EventBus.instance().device_disconnected.emit()
