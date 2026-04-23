from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Optional

import numpy as np

from neuropilot.domain.eeg.transports.base import IDeviceTransport, TransportError

_CHUNK_MS = 100  # 每次 read() 返回约 100ms 数据


class PlaybackTransport(IDeviceTransport):
    """CSV 回放传输源 — 将录制好的 EEG CSV 文件重新播放.

    参考 neurodecode stream_recorder + replay 的设计思路：
    录制与回放使用相同的数据格式，形成完整的 record/playback 链路。

    CSV 格式（与 EEGRecordService 输出兼容）：
        time, CH1, CH2, ..., CHN

    参数
    ----
    csv_path: EEG 录制 CSV 的路径
    loop: 播放完毕后是否循环
    srate_override: 覆盖 CSV 中的采样率（None 表示从数据推算）
    """

    def __init__(
        self,
        csv_path: str | Path = "",
        loop: bool = True,
        srate_override: Optional[float] = None,
    ) -> None:
        self._csv_path = Path(csv_path) if csv_path else None
        self._loop = loop
        self._srate_override = srate_override
        self._is_open = False
        self._data: Optional[np.ndarray] = None
        self._srate: float = srate_override or 250.0
        self._n_channels: int = 1
        self._cursor: int = 0
        self._chunk_size: int = 1
        self._t_last: float = 0.0
        self._chunk_dur: float = 0.1

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
        if self._csv_path is None or not self._csv_path.exists():
            path_str = str(self._csv_path) if self._csv_path else "<未指定>"
            raise TransportError(f"PlaybackTransport: 文件不存在: {path_str}")

        rows, times = self._load_csv(self._csv_path)
        if len(rows) < 2:
            raise TransportError("PlaybackTransport: CSV 行数过少，无法回放")

        self._data = rows
        self._n_channels = rows.shape[1]

        if self._srate_override:
            self._srate = self._srate_override
        elif len(times) >= 2 and times[-1] > times[0]:
            self._srate = (len(times) - 1) / (times[-1] - times[0])
        else:
            self._srate = 250.0

        self._chunk_size = max(1, int(self._srate * _CHUNK_MS / 1000))
        self._chunk_dur = self._chunk_size / self._srate
        self._cursor = 0
        self._t_last = time.monotonic()
        self._is_open = True

    def close(self) -> None:
        self._is_open = False

    def read(self, timeout: float = 0.0) -> Optional[np.ndarray]:
        if not self._is_open or self._data is None:
            return None
        now = time.monotonic()
        if now - self._t_last < self._chunk_dur:
            return None
        self._t_last = now

        total = len(self._data)
        end = self._cursor + self._chunk_size
        if end >= total:
            chunk = self._data[self._cursor:]
            if self._loop:
                self._cursor = 0
            else:
                self._is_open = False
        else:
            chunk = self._data[self._cursor:end]
            self._cursor = end

        if len(chunk) == 0:
            return None
        return chunk.astype(np.float32)

    @staticmethod
    def _load_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
        """读取 EEGRecordService 格式 CSV，返回 (data[n,ch], times[n])。"""
        rows = []
        times = []
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                return np.zeros((0, 1)), np.zeros(0)
            n_ch = len(header) - 1
            for row in reader:
                if len(row) < n_ch + 1:
                    continue
                try:
                    t = float(row[0])
                    vals = [float(row[i + 1]) for i in range(n_ch)]
                    times.append(t)
                    rows.append(vals)
                except ValueError:
                    continue

        if not rows:
            return np.zeros((0, max(n_ch, 1))), np.zeros(0)
        return np.array(rows, dtype=np.float64), np.array(times, dtype=np.float64)
