from __future__ import annotations

from typing import Optional

import numpy as np

from neuropilot.domain.eeg.transports.base import (
    DependencyMissingError,
    IDeviceTransport,
    TransportError,
)

_RFCOMM = 3  # bluetooth.RFCOMM constant value


class BluetoothTransport(IDeviceTransport):
    """Bluetooth RFCOMM transport via pybluez2.

    Data format: same ASCII-CSV as SerialTransport.
    If pybluez2 is not installed, open() raises DependencyMissingError.
    """

    def __init__(
        self,
        address: str = "",
        port: int = 1,
        srate: float = 250.0,
        n_channels: int = 8,
    ) -> None:
        self._address = address
        self._port = port
        self._srate = srate
        self._n_channels = n_channels
        self._sock: object = None
        self._buf = b""

    @property
    def srate(self) -> float:
        return self._srate

    @property
    def n_channels(self) -> int:
        return self._n_channels

    @property
    def is_open(self) -> bool:
        return self._sock is not None

    def open(self, timeout: float = 5.0) -> None:
        try:
            import bluetooth  # type: ignore[import]
        except ImportError as exc:
            raise DependencyMissingError(
                "pybluez2 is required for Bluetooth transport. "
                "Install with: pip install pybluez2"
            ) from exc
        sock: object = None
        try:
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.settimeout(timeout)
            self._sock = sock
            sock.connect((self._address, self._port))
            sock.settimeout(None)
            self._buf = b""
        except Exception as exc:
            self._sock = None
            try:
                if sock is not None:
                    sock.close()
            except Exception:
                pass
            raise TransportError(f"Bluetooth connect failed: {exc}") from exc

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()  # type: ignore[union-attr]
            except Exception:
                pass
            self._sock = None

    def read(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        if not self.is_open or self._sock is None:
            return None
        import select as _select

        ready, _, _ = _select.select([self._sock], [], [], timeout)
        if not ready:
            return None
        try:
            chunk = self._sock.recv(256)  # type: ignore[union-attr]
        except Exception as exc:
            raise TransportError(f"Bluetooth recv error: {exc}") from exc
        if not chunk:
            return None
        self._buf += chunk
        if b"\n" not in self._buf:
            return None
        line, self._buf = self._buf.split(b"\n", 1)
        try:
            values = [float(v) for v in line.decode("ascii", errors="ignore").strip().split(",")]
        except ValueError:
            return None
        if len(values) < self._n_channels:
            return None
        return np.array(values[: self._n_channels], dtype=np.float32).reshape(1, self._n_channels)

    def write(self, payload: bytes) -> None:
        if not self.is_open or self._sock is None:
            from neuropilot.domain.eeg.transports.base import TransportError
            raise TransportError("Bluetooth socket not open")
        try:
            self._sock.send(payload)  # type: ignore[union-attr]
        except Exception as exc:
            from neuropilot.domain.eeg.transports.base import TransportError
            raise TransportError(f"Bluetooth write error: {exc}") from exc
