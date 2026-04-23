from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PyQt5")

from neuropilot.app.event_bus import EventBus
from neuropilot.ui.main_window import MainWindow


class _FakeWorker:
    def __init__(self) -> None:
        self.stop_calls = 0
        self.terminate_calls = 0
        self.wait_calls: list[int] = []

    def stop(self) -> None:
        self.stop_calls += 1

    def isRunning(self) -> bool:  # noqa: N802 - Qt naming style
        return True

    def terminate(self) -> None:
        self.terminate_calls += 1

    def wait(self, timeout: int) -> bool:
        self.wait_calls.append(timeout)
        return True


def _make_window(monkeypatch, qtbot, tmp_path: Path) -> MainWindow:
    monkeypatch.setattr(MainWindow, "_build_nav", lambda self: None)
    cfg = SimpleNamespace(
        eeg_sample_rate=250,
        eeg_channels=8,
        data_dir=str(tmp_path),
        log_file="",
        lock_threshold=5,
        lock_minutes=10,
    )
    window = MainWindow(
        auth_service=MagicMock(),
        subject_repo=MagicMock(),
        session_repo=MagicMock(),
        trial_repo=MagicMock(),
        cfg=cfg,
        session_factory=MagicMock(),
    )
    qtbot.addWidget(window)
    return window


@pytest.mark.qt
def test_disconnect_request_starts_guard_timer(monkeypatch, qtbot, tmp_path):
    window = _make_window(monkeypatch, qtbot, tmp_path)
    worker = _FakeWorker()
    window._worker = worker

    window._on_eeg_disconnect_requested()

    assert worker.stop_calls == 1
    assert window._disconnecting_worker is worker
    assert window._disconnect_timer.isActive()


@pytest.mark.qt
def test_disconnect_timeout_force_releases_worker(monkeypatch, qtbot, tmp_path):
    window = _make_window(monkeypatch, qtbot, tmp_path)
    worker = _FakeWorker()
    window._worker = worker
    window._disconnecting_worker = worker

    emitted: list[str] = []
    bus = EventBus.instance()
    slot = lambda: emitted.append("disconnected")
    bus.eeg_disconnected.connect(slot)

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(window, "_show_warning", lambda title, content: warnings.append((title, content)))

    try:
        window._on_disconnect_timeout()
    finally:
        bus.eeg_disconnected.disconnect(slot)

    assert worker.terminate_calls == 1
    assert worker.wait_calls == [300]
    assert window._worker is None
    assert window._disconnecting_worker is None
    assert emitted == ["disconnected"]
    assert warnings == [("断开超时", "EEG 连接关闭过慢，已强制释放，可重新连接。")]
