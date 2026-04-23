from __future__ import annotations

import select
import socket
import struct
from typing import Optional

import numpy as np

from neuropilot.domain.eeg.transports.base import IDeviceTransport, TransportError

_HANDSHAKE_MAGIC = b"NEURO\x00"
_HEADER_FMT = ">HH"   # n_channels (uint16), srate*10 (uint16) as fixed-point


class TCPTransport(IDeviceTransport):
    """TCP binary transport.

    Wire format after handshake:
      - 4-byte little-endian float32 per sample, n_channels floats per frame.
    The server sends frames continuously; we read frames using select() so
    the socket never blocks indefinitely.

    Fixes the old bug where setblocking() was toggled back and forth —
    we use select() exclusively and leave the socket non-blocking.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4000,
        srate: float = 250.0,
        n_channels: int = 8,
    ) -> None:
        self._host = host
        self._port = port
        self._srate = srate
        self._n_channels = n_channels
        self._sock: Optional[socket.socket] = None
        self._buf = b""
        self._frame_bytes = n_channels * 4  # float32 per channel

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
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        self._sock = sock
        try:
            sock.connect((self._host, self._port))
        except Exception as exc:
            self._sock = None
            sock.close()
            raise TransportError(f"TCP connect to {self._host}:{self._port} failed: {exc}") from exc
        sock.setblocking(False)
        self._buf = b""

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def read(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        if self._sock is None:
            return None
        ready, _, _ = select.select([self._sock], [], [], timeout)
        if not ready:
            return None
        try:
            data = self._sock.recv(4096)
        except BlockingIOError:
            return None
        except Exception as exc:
            raise TransportError(f"TCP recv error: {exc}") from exc
        if not data:
            raise TransportError("TCP connection closed by remote")
        self._buf += data

        frames_available = len(self._buf) // self._frame_bytes
        if frames_available == 0:
            return None

        n_bytes = frames_available * self._frame_bytes
        raw = self._buf[:n_bytes]
        self._buf = self._buf[n_bytes:]
        arr = np.frombuffer(raw, dtype=np.float32).reshape(frames_available, self._n_channels)
        return arr.copy()

    def write(self, payload: bytes) -> None:
        if self._sock is None:
            raise TransportError("TCP socket not open")
        try:
            self._sock.sendall(payload)
        except Exception as exc:
            raise TransportError(f"TCP write error: {exc}") from exc
