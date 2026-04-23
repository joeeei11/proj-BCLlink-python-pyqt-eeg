from __future__ import annotations

import time
from typing import Optional

import numpy as np

from neuropilot.domain.eeg.transports.base import IDeviceTransport

_CHUNK_MS = 100  # 每次 read() 返回约 100ms 数据


class SyntheticTransport(IDeviceTransport):
    """多频段合成 EEG 信号源（比 DemoTransport 更接近真实 EEG 频谱）.

    参考 brainflow BoardShim.get_board_data() 的 synthetic board 设计：
    提供可重复的、带物理意义频段的合成数据，用于无硬件时的主链路调试。

    信号组成（µV）：
    - Delta  (0.5–4 Hz)  幅度 30
    - Theta  (4–8 Hz)   幅度 20
    - Alpha  (8–13 Hz)  幅度 25（各通道相位偏移，模拟空间差异）
    - Beta   (13–30 Hz) 幅度 10
    - Gamma  (30–45 Hz) 幅度 5
    - 高斯噪声幅度 3 µV
    """

    _BANDS = [
        (2.0, 30.0),   # delta
        (6.0, 20.0),   # theta
        (10.0, 25.0),  # alpha
        (20.0, 10.0),  # beta
        (40.0, 5.0),   # gamma
    ]

    def __init__(
        self,
        srate: float = 250.0,
        n_channels: int = 8,
        noise_uv: float = 3.0,
    ) -> None:
        self._srate = max(srate, 1.0)
        self._n_channels = max(n_channels, 1)
        self._noise_uv = noise_uv
        self._chunk_size = max(1, int(self._srate * _CHUNK_MS / 1000))
        self._is_open = False
        self._sample_idx = 0
        self._t_last: float = 0.0
        self._chunk_dur = self._chunk_size / self._srate

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
            ch_phase_offset = ch * (2 * np.pi / max(self._n_channels, 1))
            signal = np.zeros(self._chunk_size, dtype=np.float64)
            for freq, amp in self._BANDS:
                phase = ch_phase_offset + (ch * 0.3)
                signal += amp * np.sin(2 * np.pi * freq * t + phase)
            signal += self._noise_uv * np.random.randn(self._chunk_size)
            data[:, ch] = signal.astype(np.float32)

        self._sample_idx += self._chunk_size
        return data
