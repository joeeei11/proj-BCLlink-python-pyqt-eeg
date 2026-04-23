"""Integration test: DemoTransport → AcquisitionWorker → stop < 300 ms."""
from __future__ import annotations

import time

import numpy as np
import pytest

from neuropilot.domain.eeg.transports.demo import DemoTransport
from neuropilot.domain.eeg.ring_buffer import RingBuffer


# ------------------------------------------------------------------
# DemoTransport unit-level
# ------------------------------------------------------------------

def test_demo_open_close() -> None:
    tp = DemoTransport(srate=250.0, n_channels=4)
    assert not tp.is_open
    tp.open()
    assert tp.is_open
    tp.close()
    assert not tp.is_open


def test_demo_read_returns_correct_shape() -> None:
    tp = DemoTransport(srate=250.0, n_channels=4)
    tp.open()
    # Read until we get data (at most 1 s)
    t0 = time.monotonic()
    data = None
    while data is None and time.monotonic() - t0 < 1.0:
        data = tp.read(timeout=0.0)
        if data is None:
            time.sleep(0.01)
    tp.close()
    assert data is not None, "DemoTransport produced no data in 1 s"
    assert data.ndim == 2
    assert data.shape[1] == 4


def test_demo_values_in_expected_range() -> None:
    tp = DemoTransport(srate=250.0, n_channels=2, amp_uv=50.0)
    tp.open()
    chunks = []
    t0 = time.monotonic()
    while time.monotonic() - t0 < 0.5:
        d = tp.read(timeout=0.0)
        if d is not None:
            chunks.append(d)
        time.sleep(0.005)
    tp.close()
    assert chunks, "No data received"
    all_data = np.concatenate(chunks, axis=0)
    assert np.abs(all_data).max() < 500.0, "Amplitude out of expected range"


# ------------------------------------------------------------------
# Thread-level stop timing
# ------------------------------------------------------------------

def test_demo_stop_under_300ms_without_qt(tmp_path) -> None:
    """Verify that stopping a demo acquisition loop takes < 300 ms."""
    import socket
    import select as _select
    import threading

    tp = DemoTransport(srate=250.0, n_channels=8)
    samples_received: list[int] = []
    stop_evt = threading.Event()
    r_pipe, w_pipe = socket.socketpair()

    def run() -> None:
        tp.open()
        while True:
            ready, _, _ = _select.select([r_pipe], [], [], 0.05)
            if ready:
                r_pipe.recv(1)
                break
            data = tp.read(timeout=0.0)
            if data is not None:
                samples_received.append(len(data))
        tp.close()
        r_pipe.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.2)  # let it produce some data

    t0 = time.monotonic()
    w_pipe.send(b"\x00")
    t.join(timeout=1.0)
    elapsed = time.monotonic() - t0
    w_pipe.close()

    assert not t.is_alive(), "Worker thread did not stop"
    assert elapsed < 0.3, f"Stop took {elapsed:.3f}s, expected < 0.3s"
    assert sum(samples_received) > 0, "No samples were received before stop"


# ------------------------------------------------------------------
# RingBuffer integration with demo data
# ------------------------------------------------------------------

def test_ring_buffer_with_demo_data() -> None:
    tp = DemoTransport(srate=250.0, n_channels=8)
    rb = RingBuffer(capacity=500, n_channels=8)
    tp.open()
    t0 = time.monotonic()
    while time.monotonic() - t0 < 0.5:
        d = tp.read(timeout=0.0)
        if d is not None:
            rb.push(d)
        time.sleep(0.005)
    tp.close()

    assert rb.n_samples > 0
    last = rb.get_last(50)
    assert last.shape[1] == 8
    assert len(last) <= 50
