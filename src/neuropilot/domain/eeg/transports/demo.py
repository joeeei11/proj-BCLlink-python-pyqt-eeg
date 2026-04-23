from __future__ import annotations

import time
from typing import Optional

import numpy as np

from neuropilot.domain.eeg.transports.base import IDeviceTransport

_CHUNK_MS = 100  # ms per read() chunk


class DemoTransport(IDeviceTransport):
    """Synthetic EEG source — 10 Hz sine per channel + Gaussian noise.

    read() is non-blocking and returns None until the next chunk's wall-clock
    time has elapsed, so the caller's select() loop controls CPU usage.
    """

    def __init__(
        self,
        srate: float = 250.0,
        n_channels: int = 8,
        freq_hz: float = 10.0,
        amp_uv: float = 50.0,
    ) -> None:
        self._srate = srate
        self._n_channels = n_channels
        self._freq = freq_hz
        self._amp = amp_uv
        self._chunk_size = max(1, int(srate * _CHUNK_MS / 1000))
        self._is_open = False
        self._sample_idx = 0
        self._t_last: float = 0.0
        self._chunk_dur: float = self._chunk_size / srate

    @property
    def srate(self) -> float:
        return self._srate

    @property
    def n_channels(self) -> int:
        return self._n_channels

    @property
    def is_open(self) -> bool:
        return self._is_open

    def open(self, timeout: float = 5.0) -> None:
        self._is_open = True
        self._sample_idx = 0
        self._t_last = time.monotonic()

    def close(self) -> None:
        self._is_open = False

    def read(self, timeout: float = 0.0) -> Optional[np.ndarray]:
        if not self._is_open:
            return None
        now = time.monotonic()
        if now - self._t_last < self._chunk_dur:
            return None
        self._t_last = now

        t = np.arange(self._sample_idx, self._sample_idx + self._chunk_size) / self._srate
        data = np.zeros((self._chunk_size, self._n_channels), dtype=np.float32)
        for ch in range(self._n_channels):
            phase = ch * (np.pi / self._n_channels)
            data[:, ch] = (
                self._amp * np.sin(2 * np.pi * self._freq * t + phase)
                + 5.0 * np.random.randn(self._chunk_size)
            )
        self._sample_idx += self._chunk_size
        return data
