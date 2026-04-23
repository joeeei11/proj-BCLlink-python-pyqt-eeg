from __future__ import annotations

from typing import Optional

import numpy as np

from neuropilot.domain.eeg.transports.base import IDeviceTransport


class AcquisitionService:
    """Domain-layer wrapper around a transport strategy.

    No Qt dependencies.  The Qt thread wrapper lives in app/acquisition_worker.py.
    """

    def __init__(self, transport: IDeviceTransport) -> None:
        self._transport = transport

    @property
    def transport(self) -> IDeviceTransport:
        return self._transport

    def set_transport(self, transport: IDeviceTransport) -> None:
        if self._transport.is_open:
            raise RuntimeError("Cannot swap transport while connected.")
        self._transport = transport

    def connect(self, timeout: float = 5.0) -> None:
        self._transport.open(timeout=timeout)

    def disconnect(self) -> None:
        self._transport.close()

    @property
    def is_connected(self) -> bool:
        return self._transport.is_open

    @property
    def srate(self) -> float:
        return self._transport.srate

    @property
    def n_channels(self) -> int:
        return self._transport.n_channels

    def read_once(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """Single non-blocking read pass. Returns None if no data yet."""
        return self._transport.read(timeout=timeout)
