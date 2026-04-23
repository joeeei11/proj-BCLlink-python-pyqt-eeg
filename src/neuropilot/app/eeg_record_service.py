from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np


class EEGRecordService:
    """EEG 原始数据 CSV 落盘服务（无 Qt 依赖）.

    职责：打开/写入/关闭 CSV 文件，管理行缓冲。
    参考 neurodecode StreamRecorder 的职责分离原则：
    录制器只关心"把样本写到文件"，不关心采集线程和 session 状态。
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._data_dir = Path(data_dir)
        self._csv_path: Optional[Path] = None
        self._handle = None
        self._writer = None
        self._n_channels: int = 0
        self._srate: float = 1.0
        self._sample_idx: int = 0
        self._flush_every: int = 1
        self._row_buffer: list[list[str]] = []

    @property
    def csv_path(self) -> Optional[Path]:
        return self._csv_path

    @property
    def sample_count(self) -> int:
        return self._sample_idx

    @property
    def is_recording(self) -> bool:
        return self._handle is not None

    def start(
        self,
        subject_id: int,
        session_id: int,
        n_channels: int,
        srate: float,
    ) -> Path:
        """开始录制，创建并打开 CSV 文件，写入表头。"""
        self._n_channels = n_channels
        self._srate = max(srate, 1.0)
        self._sample_idx = 0
        self._flush_every = max(1, int(self._srate))
        self._row_buffer = []

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_path = (
            self._data_dir
            / "raw_eeg"
            / f"subj{subject_id}_{session_id}_{timestamp}.csv"
        )
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_path = csv_path

        self._handle = open(csv_path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._handle)
        self._writer.writerow(["time"] + [f"CH{i + 1}" for i in range(n_channels)])
        return csv_path

    def write_chunk(self, data: np.ndarray) -> int:
        """写入一块样本数据，返回累计已写样本数。

        每满 flush_every 行自动 flush（约每秒一次）。
        """
        if self._writer is None or data is None or len(data) == 0:
            return self._sample_idx

        count = len(data)
        time_vector = np.arange(self._sample_idx, self._sample_idx + count) / self._srate
        n_ch = min(self._n_channels, data.shape[1] if data.ndim == 2 else 1)
        for i in range(count):
            if data.ndim == 2:
                row = [f"{time_vector[i]:.6f}"] + [f"{data[i, ch]:.4f}" for ch in range(n_ch)]
            else:
                row = [f"{time_vector[i]:.6f}", f"{data[i]:.4f}"]
            self._row_buffer.append(row)
        self._sample_idx += count

        if len(self._row_buffer) >= self._flush_every:
            self._writer.writerows(self._row_buffer)
            self._handle.flush()
            self._row_buffer.clear()

        return self._sample_idx

    def stop(self) -> None:
        """刷新剩余缓冲并关闭文件。"""
        if self._writer is not None and self._row_buffer:
            self._writer.writerows(self._row_buffer)
            self._row_buffer.clear()
        if self._handle is not None:
            try:
                self._handle.flush()
                self._handle.close()
            except Exception:
                pass
            self._handle = None
            self._writer = None
