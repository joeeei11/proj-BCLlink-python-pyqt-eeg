"""单元测试：EEGRecordService — CSV 落盘"""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import numpy as np
import pytest

from neuropilot.app.eeg_record_service import EEGRecordService


def _make_chunk(n_samples: int = 25, n_ch: int = 8) -> np.ndarray:
    return np.random.randn(n_samples, n_ch).astype(np.float32)


class TestEEGRecordService:
    def test_start_creates_csv(self, tmp_path):
        svc = EEGRecordService(tmp_path)
        path = svc.start(subject_id=1, session_id=42, n_channels=8, srate=250.0)
        assert path.exists()
        assert path.suffix == ".csv"
        assert "subj1_42" in path.name

    def test_write_chunk_increments_count(self, tmp_path):
        svc = EEGRecordService(tmp_path)
        svc.start(subject_id=1, session_id=1, n_channels=8, srate=250.0)
        total = svc.write_chunk(_make_chunk(25))
        assert total == 25
        total = svc.write_chunk(_make_chunk(25))
        assert total == 50

    def test_stop_writes_remaining_buffer(self, tmp_path):
        svc = EEGRecordService(tmp_path)
        path = svc.start(subject_id=1, session_id=1, n_channels=4, srate=100.0)
        # 写 10 行（< flush_every=100），这些在缓冲区里
        svc.write_chunk(np.zeros((10, 4), dtype=np.float32))
        assert svc.is_recording
        svc.stop()
        assert not svc.is_recording
        # 文件应包含 header + 10 数据行
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert len(rows) == 11  # 1 header + 10 data

    def test_csv_header(self, tmp_path):
        svc = EEGRecordService(tmp_path)
        path = svc.start(subject_id=2, session_id=5, n_channels=4, srate=100.0)
        svc.stop()
        with open(path, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        assert header == ["time", "CH1", "CH2", "CH3", "CH4"]

    def test_write_without_start_is_noop(self, tmp_path):
        svc = EEGRecordService(tmp_path)
        total = svc.write_chunk(_make_chunk(10))
        assert total == 0

    def test_stop_without_start_is_safe(self, tmp_path):
        svc = EEGRecordService(tmp_path)
        svc.stop()  # should not raise

    def test_csv_path_none_before_start(self, tmp_path):
        svc = EEGRecordService(tmp_path)
        assert svc.csv_path is None
        assert svc.sample_count == 0

    def test_auto_flush_every_srate_samples(self, tmp_path):
        svc = EEGRecordService(tmp_path)
        path = svc.start(subject_id=1, session_id=1, n_channels=2, srate=10.0)
        # flush_every = 10; 写 10 行应触发 flush
        chunk = np.ones((10, 2), dtype=np.float32)
        svc.write_chunk(chunk)
        # buffer should be empty after flush
        assert len(svc._row_buffer) == 0
        svc.stop()
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert len(rows) == 11  # header + 10
