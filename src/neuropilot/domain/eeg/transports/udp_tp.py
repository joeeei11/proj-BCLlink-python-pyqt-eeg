from __future__ import annotations

import select
import socket
from typing import Optional

import numpy as np

from neuropilot.domain.eeg.transports.base import IDeviceTransport, TransportError

_MAGIC = b"EEG\x00"  # optional 4-byte header prefix


class UDPTransport(IDeviceTransport):
    """UDP datagram transport.

    Each datagram may optionally start with ``_MAGIC``.
    Payload is float32 samples: n_channels × n_frames floats.
    Datagrams whose payload length is not aligned to ``n_channels * 4`` bytes
    are dropped with a log warning.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 4001,
        srate: float = 250.0,
        n_channels: int = 8,
        check_magic: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._srate = srate
        self._n_channels = n_channels
        self._check_magic = check_magic
        self._frame_bytes = n_channels * 4
        self._sock: Optional[socket.socket] = None

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
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self._host, self._port))
        except Exception as exc:
            sock.close()
            raise TransportError(f"UDP bind {self._host}:{self._port} failed: {exc}") from exc
        sock.setblocking(False)
        self._sock = sock

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
            datagram, _ = self._sock.recvfrom(65535)
        except BlockingIOError:
            return None
        except Exception as exc:
            raise TransportError(f"UDP recv error: {exc}") from exc

        payload = datagram
        if self._check_magic:
            if not datagram.startswith(_MAGIC):
                from loguru import logger
                logger.warning("UDP: dropped datagram — missing magic header")
                return None
            payload = datagram[len(_MAGIC):]

        if len(payload) == 0 or len(payload) % self._frame_bytes != 0:
            from loguru import logger
            logger.warning(
                "UDP: dropped datagram — payload {} bytes not aligned to {} bytes/frame",
                len(payload), self._frame_bytes,
            )
            return None

        n_frames = len(payload) // self._frame_bytes
        arr = np.frombuffer(payload, dtype=np.float32).reshape(n_frames, self._n_channels)
        return arr.copy()

    def write(self, payload: bytes, *, dest: tuple[str, int] | None = None) -> None:
        """Send a datagram.  ``dest`` overrides the bound address for unicast."""
        if self._sock is None:
            raise TransportError("UDP socket not open")
        target = dest or (self._host, self._port)
        try:
            self._sock.sendto(payload, target)
        except Exception as exc:
            raise TransportError(f"UDP write error: {exc}") from exc
