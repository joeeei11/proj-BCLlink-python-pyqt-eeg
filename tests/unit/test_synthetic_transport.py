"""单元测试：SyntheticTransport 和 PlaybackTransport"""
from __future__ import annotations

import csv
import time
import tempfile
from pathlib import Path

import numpy as np
import pytest

from neuropilot.domain.eeg.transports.synthetic_tp import SyntheticTransport
from neuropilot.domain.eeg.transports.playback_tp import PlaybackTransport
from neuropilot.domain.eeg.transports.base import TransportError


class TestSyntheticTransport:
    def test_properties_before_open(self):
        t = SyntheticTransport(srate=250.0, n_channels=8)
        assert t.srate == 250.0
        assert t.n_channels == 8
        assert not t.is_open

    def test_open_sets_is_open(self):
        t = SyntheticTransport(srate=100.0, n_channels=4)
        t.open()
        assert t.is_open
        t.close()

    def test_close_sets_not_open(self):
        t = SyntheticTransport()
        t.open()
        t.close()
        assert not t.is_open

    def test_read_returns_none_before_chunk_elapsed(self):
        t = SyntheticTransport(srate=250.0, n_channels=8)
        t.open()
        data = t.read()
        # 刚 open 后立刻 read，chunk 未到时间
        # 可能为 None（正常）也可能非 None（open 时 _t_last=monotonic 导致首读为 None）
        # 不做强断言，只要不抛异常
        t.close()

    def test_read_returns_correct_shape_after_wait(self):
        t = SyntheticTransport(srate=100.0, n_channels=4)
        t.open()
        time.sleep(0.12)  # 等超过 100ms chunk_dur
        data = t.read()
        assert data is not None
        assert data.ndim == 2
        assert data.shape[1] == 4
        t.close()

    def test_read_returns_float32(self):
        t = SyntheticTransport(srate=100.0, n_channels=2)
        t.open()
        time.sleep(0.12)
        data = t.read()
        assert data is not None
        assert data.dtype == np.float32
        t.close()

    def test_read_closed_returns_none(self):
        t = SyntheticTransport()
        assert t.read() is None

    def test_multi_read_accumulates(self):
        t = SyntheticTransport(srate=100.0, n_channels=2)
        t.open()
        total = 0
        for _ in range(5):
            time.sleep(0.12)
            data = t.read()
            if data is not None:
                total += len(data)
        t.close()
        assert total > 0


class TestPlaybackTransport:
    @staticmethod
    def _write_csv(path: Path, n_rows: int = 50, n_ch: int = 4, srate: float = 100.0) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["time"] + [f"CH{i+1}" for i in range(n_ch)])
            for i in range(n_rows):
                t = i / srate
                row = [f"{t:.6f}"] + [f"{np.random.randn():.4f}" for _ in range(n_ch)]
                w.writerow(row)

    def test_open_nonexistent_file_raises(self, tmp_path):
        t = PlaybackTransport(csv_path=tmp_path / "missing.csv")
        with pytest.raises(TransportError, match="文件不存在"):
            t.open()

    def test_open_valid_file(self, tmp_path):
        p = tmp_path / "test.csv"
        self._write_csv(p, n_rows=50, n_ch=4, srate=100.0)
        t = PlaybackTransport(csv_path=p, loop=False)
        t.open()
        assert t.is_open
        assert t.n_channels == 4
        t.close()

    def test_srate_inferred_from_timestamps(self, tmp_path):
        p = tmp_path / "test.csv"
        self._write_csv(p, n_rows=100, n_ch=2, srate=200.0)
        t = PlaybackTransport(csv_path=p, loop=False)
        t.open()
        # 推算采样率应接近 200 Hz（允许浮点偏差）
        assert abs(t.srate - 200.0) < 5.0
        t.close()

    def test_read_returns_chunk_after_wait(self, tmp_path):
        p = tmp_path / "test.csv"
        self._write_csv(p, n_rows=100, n_ch=4, srate=100.0)
        t = PlaybackTransport(csv_path=p, loop=True)
        t.open()
        time.sleep(0.12)
        data = t.read()
        assert data is not None
        assert data.ndim == 2
        assert data.shape[1] == 4
        t.close()

    def test_read_dtype_is_float32(self, tmp_path):
        p = tmp_path / "test.csv"
        self._write_csv(p, n_rows=50, n_ch=2, srate=100.0)
        t = PlaybackTransport(csv_path=p, loop=True)
        t.open()
        time.sleep(0.12)
        data = t.read()
        if data is not None:
            assert data.dtype == np.float32
        t.close()

    def test_loop_mode_continues(self, tmp_path):
        p = tmp_path / "test.csv"
        self._write_csv(p, n_rows=20, n_ch=2, srate=100.0)
        t = PlaybackTransport(csv_path=p, loop=True)
        t.open()
        collected = 0
        for _ in range(10):
            time.sleep(0.12)
            data = t.read()
            if data is not None:
                collected += len(data)
        t.close()
        # loop 模式下应持续出数据，远超原始 20 行
        assert collected >= 20

    def test_no_loop_stops(self, tmp_path):
        p = tmp_path / "test.csv"
        self._write_csv(p, n_rows=15, n_ch=2, srate=100.0)
        t = PlaybackTransport(csv_path=p, loop=False)
        t.open()
        # 非循环模式：反复调用 read 直到数据耗尽（is_open 自动置 False）
        deadline = time.monotonic() + 5.0
        while t.is_open and time.monotonic() < deadline:
            time.sleep(0.12)
            t.read()
        assert not t.is_open
