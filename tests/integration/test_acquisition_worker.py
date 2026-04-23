"""集成测试：AcquisitionWorker + EEGRecordService + EEGSessionCoordinator.

用 DemoTransport 模拟真实采集，MockSessionRepo 避免实际 DB 操作。
验证：连接信号、样本信号、CSV 落盘、session 生命周期、停止时序。
"""
from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import numpy as np
import pytest

from neuropilot.app.acquisition_worker import AcquisitionWorker
from neuropilot.app.eeg_record_service import EEGRecordService
from neuropilot.app.eeg_session_coordinator import EEGSessionCoordinator
from neuropilot.domain.eeg.transports.demo import DemoTransport
from neuropilot.domain.eeg.transports.synthetic_tp import SyntheticTransport


# ── 辅助工具 ─────────────────────────────────────────────────────────

def _make_mock_session_repo(session_id: int = 42):
    repo = MagicMock()
    repo.create.return_value = session_id
    return repo


def _run_worker_for(
    worker: AcquisitionWorker,
    seconds: float = 0.4,
) -> dict:
    """启动 worker，采集指定时长后停止，收集结果。"""
    results: dict = {
        "connected_ok": None,
        "connected_transport": None,
        "samples": [],
        "errors": [],
        "traffic": [],
    }

    worker.sig_connected.connect(
        lambda ok, msg: results.update(connected_ok=ok, connected_transport=msg)
    )
    worker.sig_samples.connect(lambda data: results["samples"].append(data.copy()))
    worker.sig_error.connect(lambda msg: results["errors"].append(msg))
    worker.sig_traffic.connect(lambda k, v: results["traffic"].append((k, v)))

    worker.start()
    # 等连接建立（最多 2s）
    deadline = time.monotonic() + 2.0
    while results["connected_ok"] is None and time.monotonic() < deadline:
        time.sleep(0.02)
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.processEvents()

    if results["connected_ok"]:
        time.sleep(seconds)
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.processEvents()

    worker.stop()
    worker.wait(3000)
    return results


# ── 测试：Demo 传输 ───────────────────────────────────────────────

class TestAcquisitionWorkerDemo:
    def test_connect_emits_connected_true(self, tmp_path, qtbot):
        repo = _make_mock_session_repo(session_id=1)
        coordinator = EEGSessionCoordinator(repo)
        recorder = EEGRecordService(tmp_path)
        transport = DemoTransport(srate=100.0, n_channels=4)

        worker = AcquisitionWorker(
            transport=transport,
            session_coordinator=coordinator,
            record_service=recorder,
            subject_id=1,
            user_id=1,
            transport_name="demo",
        )
        results = _run_worker_for(worker, seconds=0.3)

        assert results["connected_ok"] is True
        assert results["connected_transport"] == "demo"
        assert not results["errors"]

    def test_samples_received(self, tmp_path, qtbot):
        repo = _make_mock_session_repo(session_id=2)
        coordinator = EEGSessionCoordinator(repo)
        recorder = EEGRecordService(tmp_path)
        transport = DemoTransport(srate=100.0, n_channels=4)

        worker = AcquisitionWorker(
            transport=transport,
            session_coordinator=coordinator,
            record_service=recorder,
            subject_id=1, user_id=1, transport_name="demo",
        )
        results = _run_worker_for(worker, seconds=0.5)

        total_samples = sum(len(chunk) for chunk in results["samples"])
        assert total_samples > 0, "应收到 EEG 样本"
        # 各 chunk 形状正确
        for chunk in results["samples"]:
            assert chunk.ndim == 2
            assert chunk.shape[1] == 4

    def test_csv_written_after_stop(self, tmp_path, qtbot):
        repo = _make_mock_session_repo(session_id=3)
        coordinator = EEGSessionCoordinator(repo)
        recorder = EEGRecordService(tmp_path)
        transport = DemoTransport(srate=100.0, n_channels=4)

        worker = AcquisitionWorker(
            transport=transport,
            session_coordinator=coordinator,
            record_service=recorder,
            subject_id=1, user_id=1, transport_name="demo",
        )
        _run_worker_for(worker, seconds=0.4)

        csv_path = recorder.csv_path
        assert csv_path is not None
        assert csv_path.exists()

        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        # header + 至少一行数据
        assert len(rows) >= 2
        assert rows[0] == ["time", "CH1", "CH2", "CH3", "CH4"]

    def test_session_create_called(self, tmp_path, qtbot):
        repo = _make_mock_session_repo(session_id=10)
        coordinator = EEGSessionCoordinator(repo)
        recorder = EEGRecordService(tmp_path)
        transport = DemoTransport(srate=100.0, n_channels=4)

        worker = AcquisitionWorker(
            transport=transport,
            session_coordinator=coordinator,
            record_service=recorder,
            subject_id=7, user_id=3, transport_name="demo",
        )
        _run_worker_for(worker, seconds=0.3)

        repo.create.assert_called_once()
        call_kwargs = repo.create.call_args[1]
        assert call_kwargs["subject_id"] == 7
        assert call_kwargs["user_id"] == 3
        assert call_kwargs["transport"] == "demo"
        assert call_kwargs["n_channels"] == 4

    def test_session_stopped_after_worker_stop(self, tmp_path, qtbot):
        repo = _make_mock_session_repo(session_id=5)
        coordinator = EEGSessionCoordinator(repo)
        recorder = EEGRecordService(tmp_path)
        transport = DemoTransport(srate=100.0, n_channels=4)

        worker = AcquisitionWorker(
            transport=transport,
            session_coordinator=coordinator,
            record_service=recorder,
            subject_id=1, user_id=1, transport_name="demo",
        )
        _run_worker_for(worker, seconds=0.3)

        repo.set_stopped.assert_called_once_with(5)

    def test_stop_completes_within_500ms(self, tmp_path, qtbot):
        repo = _make_mock_session_repo(session_id=6)
        coordinator = EEGSessionCoordinator(repo)
        recorder = EEGRecordService(tmp_path)
        transport = DemoTransport(srate=100.0, n_channels=4)

        worker = AcquisitionWorker(
            transport=transport,
            session_coordinator=coordinator,
            record_service=recorder,
            subject_id=1, user_id=1, transport_name="demo",
        )
        worker.start()
        # 等连接建立
        deadline = time.monotonic() + 2.0
        while worker.session_id is None and time.monotonic() < deadline:
            time.sleep(0.05)

        t0 = time.monotonic()
        worker.stop()
        worker.wait(2000)
        elapsed = time.monotonic() - t0

        assert not worker.isRunning(), "Worker 线程应已停止"
        assert elapsed < 0.5, f"停止耗时 {elapsed:.3f}s，期望 < 0.5s"


# ── 测试：Synthetic 传输 ──────────────────────────────────────────

class TestAcquisitionWorkerSynthetic:
    def test_synthetic_produces_multi_channel_data(self, tmp_path, qtbot):
        repo = _make_mock_session_repo(session_id=20)
        coordinator = EEGSessionCoordinator(repo)
        recorder = EEGRecordService(tmp_path)
        transport = SyntheticTransport(srate=100.0, n_channels=8)

        worker = AcquisitionWorker(
            transport=transport,
            session_coordinator=coordinator,
            record_service=recorder,
            subject_id=1, user_id=1, transport_name="synthetic",
        )
        results = _run_worker_for(worker, seconds=0.4)

        assert results["connected_ok"] is True
        total = sum(len(c) for c in results["samples"])
        assert total > 0

        # 验证 synthetic 数据包含多频段（标准差应 > 纯零信号）
        if results["samples"]:
            all_data = np.concatenate(results["samples"], axis=0)
            assert all_data.std() > 0.1, "Synthetic 信号标准差过小"

    def test_synthetic_csv_has_8_channels(self, tmp_path, qtbot):
        repo = _make_mock_session_repo(session_id=21)
        coordinator = EEGSessionCoordinator(repo)
        recorder = EEGRecordService(tmp_path)
        transport = SyntheticTransport(srate=100.0, n_channels=8)

        worker = AcquisitionWorker(
            transport=transport,
            session_coordinator=coordinator,
            record_service=recorder,
            subject_id=1, user_id=1, transport_name="synthetic",
        )
        _run_worker_for(worker, seconds=0.4)

        csv_path = recorder.csv_path
        assert csv_path is not None
        with open(csv_path, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        expected = ["time"] + [f"CH{i+1}" for i in range(8)]
        assert header == expected
