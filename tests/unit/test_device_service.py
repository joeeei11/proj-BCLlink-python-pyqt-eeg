"""Unit tests for DeviceService — throttle and send logic."""
from __future__ import annotations

import time
from typing import Optional

import numpy as np
import pytest

from neuropilot.domain.device.commands import DeviceCommand
from neuropilot.domain.device.device_service import DeviceService
from neuropilot.domain.eeg.transports.base import IDeviceTransport


class _MockTransport(IDeviceTransport):
    """Minimal in-memory transport for testing."""

    def __init__(self) -> None:
        self._open = False
        self.sent: list[bytes] = []

    @property
    def srate(self) -> float:
        return 0.0

    @property
    def n_channels(self) -> int:
        return 0

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self, timeout: float = 5.0) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def read(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        return None

    def write(self, payload: bytes) -> None:
        self.sent.append(payload)


# ------------------------------------------------------------------
# Connection
# ------------------------------------------------------------------

def test_not_connected_initially() -> None:
    tp = _MockTransport()
    svc = DeviceService(tp)
    assert not svc.is_connected


def test_connect_disconnect() -> None:
    tp = _MockTransport()
    svc = DeviceService(tp)
    svc.connect()
    assert svc.is_connected
    svc.disconnect()
    assert not svc.is_connected


def test_send_when_not_connected_returns_false() -> None:
    tp = _MockTransport()
    svc = DeviceService(tp)
    ok, reason = svc.send(DeviceCommand.LEFT)
    assert not ok
    assert "未连接" in reason


# ------------------------------------------------------------------
# Throttle
# ------------------------------------------------------------------

def test_second_send_within_interval_is_throttled() -> None:
    tp = _MockTransport()
    svc = DeviceService(tp, min_interval_ms=150)
    svc.connect()

    ok1, _ = svc.send(DeviceCommand.LEFT)
    assert ok1
    assert tp.sent[-1] == b"L\n"

    ok2, reason2 = svc.send(DeviceCommand.RIGHT)
    assert not ok2
    assert reason2 == "throttled"
    assert len(tp.sent) == 1   # second send was dropped


def test_send_after_interval_succeeds() -> None:
    tp = _MockTransport()
    svc = DeviceService(tp, min_interval_ms=50)
    svc.connect()

    svc.send(DeviceCommand.LEFT)
    time.sleep(0.06)  # wait past throttle window
    ok, _ = svc.send(DeviceCommand.RIGHT)
    assert ok
    assert tp.sent[-1] == b"R\n"


# ------------------------------------------------------------------
# Raw bytes
# ------------------------------------------------------------------

def test_send_raw_bytes() -> None:
    tp = _MockTransport()
    svc = DeviceService(tp)
    svc.connect()
    ok, _ = svc.send(b"CUSTOM\n")
    assert ok
    assert tp.sent[-1] == b"CUSTOM\n"


# ------------------------------------------------------------------
# Transport swap
# ------------------------------------------------------------------

def test_swap_transport_while_connected_raises() -> None:
    tp = _MockTransport()
    svc = DeviceService(tp)
    svc.connect()
    with pytest.raises(RuntimeError):
        svc.set_transport(_MockTransport())
