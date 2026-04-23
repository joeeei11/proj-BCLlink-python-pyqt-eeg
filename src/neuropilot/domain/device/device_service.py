from __future__ import annotations

import time
from typing import Optional, Tuple

from neuropilot.domain.device.commands import DeviceCommand
from neuropilot.domain.eeg.transports.base import IDeviceTransport, TransportError


class DeviceService:
    """Controls an external device (prosthetic hand / stimulator).

    Reuses IDeviceTransport for the actual I/O (Serial / Bluetooth / TCP / UDP).
    Thread-safety: intended to be called from a single Qt thread; callers must
    ensure that send() and connect/disconnect are not called concurrently.

    Throttle:
        send() enforces a minimum interval of ``min_interval_ms`` milliseconds
        using ``time.monotonic()`` — never wall-clock.  A second send attempt
        within the window returns ``(False, "throttled")`` and is silently dropped.
    """

    def __init__(
        self,
        transport: IDeviceTransport,
        min_interval_ms: int = 150,
    ) -> None:
        self._transport = transport
        self._min_interval_ms = min_interval_ms
        self._last_send_time: float = 0.0
        self._connected: bool = False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected and self._transport.is_open

    def connect(self, timeout: float = 5.0) -> None:
        if not self._transport.is_open:
            self._transport.open(timeout=timeout)
        self._connected = True

    def disconnect(self) -> None:
        try:
            self._transport.close()
        finally:
            self._connected = False

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send(
        self,
        command: DeviceCommand | bytes,
        *,
        min_interval_ms: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Send a command to the device.

        Args:
            command: A ``DeviceCommand`` enum member or raw ``bytes``.
            min_interval_ms: Override the instance-level throttle for this call.

        Returns:
            ``(True, "")`` on success.
            ``(False, reason)`` when throttled, not connected, or on transport error.
        """
        if not self.is_connected:
            return False, "未连接"

        interval = min_interval_ms if min_interval_ms is not None else self._min_interval_ms
        now = time.monotonic()
        if (now - self._last_send_time) * 1000 < interval:
            return False, "throttled"

        payload: bytes
        if isinstance(command, DeviceCommand):
            payload = command.to_bytes()
        else:
            payload = command

        try:
            # IDeviceTransport.read() is used for incoming data;
            # outgoing data goes through a write-like call.  Since
            # IDeviceTransport does not define write(), we call the
            # underlying socket/serial send via the transport object.
            self._transport.write(payload)  # type: ignore[attr-defined]
        except AttributeError:
            # Fallback: some transports expose send() instead of write()
            try:
                self._transport.send(payload)  # type: ignore[attr-defined]
            except Exception as exc:
                return False, str(exc)
        except TransportError as exc:
            return False, str(exc)
        except Exception as exc:
            return False, str(exc)

        self._last_send_time = now
        return True, ""

    def set_transport(self, transport: IDeviceTransport) -> None:
        if self.is_connected:
            raise RuntimeError("Cannot swap transport while connected.")
        self._transport = transport
