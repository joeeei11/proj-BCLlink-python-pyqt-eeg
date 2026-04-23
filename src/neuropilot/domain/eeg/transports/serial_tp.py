from __future__ import annotations

from typing import Optional

import numpy as np

from neuropilot.domain.eeg.transports.base import (
    DependencyMissingError,
    IDeviceTransport,
    TransportError,
)


class SerialTransport(IDeviceTransport):
    """ASCII-CSV serial transport.

    Each line: comma-separated float values, one sample per line.
    Example: ``CH1,CH2,...,CHn``
    """

    def __init__(
        self,
        port: str = "COM3",
        baud: int = 115200,
        srate: float = 250.0,
        n_channels: int = 8,
    ) -> None:
        self._port = port
        self._baud = baud
        self._srate = srate
        self._n_channels = n_channels
        self._ser: object = None

    @property
    def srate(self) -> float:
        return self._srate

    @property
    def n_channels(self) -> int:
        return self._n_channels

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open  # type: ignore[union-attr]

    def open(self, timeout: float = 5.0) -> None:
        try:
            import serial  # type: ignore[import]
        except ImportError as exc:
            raise DependencyMissingError("pyserial is required for serial transport") from exc
        try:
            self._ser = serial.Serial(
                port=self._port,
                baudrate=self._baud,
                timeout=timeout,
            )
        except Exception as exc:
            raise TransportError(f"Serial open failed: {exc}") from exc

    def close(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()  # type: ignore[union-attr]
            except Exception:
                pass
            self._ser = None

    def read(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        if not self.is_open or self._ser is None:
            return None
        self._ser.timeout = timeout  # type: ignore[union-attr]
        try:
            line: bytes = self._ser.readline()  # type: ignore[union-attr]
        except Exception as exc:
            raise TransportError(f"Serial read error: {exc}") from exc
        if not line:
            return None
        try:
            values = [float(v) for v in line.decode("ascii", errors="ignore").strip().split(",")]
        except ValueError:
            return None
        if len(values) < self._n_channels:
            return None
        return np.array(values[: self._n_channels], dtype=np.float32).reshape(1, self._n_channels)

    def write(self, payload: bytes) -> None:
        if not self.is_open or self._ser is None:
            from neuropilot.domain.eeg.transports.base import TransportError
            raise TransportError("Serial port not open")
        try:
            self._ser.write(payload)  # type: ignore[union-attr]
        except Exception as exc:
            from neuropilot.domain.eeg.transports.base import TransportError
            raise TransportError(f"Serial write error: {exc}") from exc
