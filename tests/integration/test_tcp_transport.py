"""Integration test: TCPTransport against FakeTCPServer."""
from __future__ import annotations

import time

import numpy as np
import pytest

from neuropilot.domain.eeg.transports.tcp_tp import TCPTransport
from tests.tools.tcp_fake_server import FakeTCPServer


def test_tcp_connect_receive_disconnect() -> None:
    n_ch = 4
    srate = 250.0

    srv = FakeTCPServer(port=0, n_channels=n_ch, srate=srate)
    srv.start()
    port = srv.port

    tp = TCPTransport(host="127.0.0.1", port=port, srate=srate, n_channels=n_ch)
    try:
        tp.open(timeout=2.0)
        assert tp.is_open

        chunks = []
        t0 = time.monotonic()
        while time.monotonic() - t0 < 0.5:
            d = tp.read(timeout=0.1)
            if d is not None:
                chunks.append(d)

        assert chunks, "No data received from fake server"
        all_data = np.concatenate(chunks, axis=0)
        assert all_data.shape[1] == n_ch
        assert np.abs(all_data).max() < 1000.0

    finally:
        tp.close()
        srv.stop()
        assert not tp.is_open


def test_tcp_stop_under_300ms() -> None:
    import socket
    import select as _select
    import threading

    n_ch = 4
    srv = FakeTCPServer(port=0, n_channels=n_ch, srate=250.0)
    srv.start()
    port = srv.port

    tp = TCPTransport(host="127.0.0.1", port=port, srate=250.0, n_channels=n_ch)
    r_pipe, w_pipe = socket.socketpair()
    done = threading.Event()
    samples: list[int] = []

    def run() -> None:
        tp.open(timeout=2.0)
        while True:
            ready, _, _ = _select.select([r_pipe], [], [], 0.05)
            if ready:
                r_pipe.recv(1)
                break
            d = tp.read(timeout=0.0)
            if d is not None:
                samples.append(len(d))
        tp.close()
        r_pipe.close()
        done.set()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.3)

    t0 = time.monotonic()
    w_pipe.send(b"\x00")
    done.wait(timeout=1.0)
    elapsed = time.monotonic() - t0
    w_pipe.close()
    srv.stop()

    assert done.is_set(), "Worker thread did not stop"
    assert elapsed < 0.3, f"Stop took {elapsed:.3f}s"
    assert sum(samples) > 0
