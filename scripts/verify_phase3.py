"""Quick smoke-test for Phase 3 core logic (no pytest/Qt dependency)."""
import sys
import os
import time
import socket
import select as _select
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np

# ---------- RingBuffer ----------
from neuropilot.domain.eeg.ring_buffer import RingBuffer

def test_ring_buffer():
    # empty
    rb = RingBuffer(100, 2)
    assert rb.n_samples == 0

    # get_last returns empty (old bug was None)
    r = rb.get_last(20)
    assert r.shape == (0, 2), f"Expected (0,2), got {r.shape}"

    # under-filled clamp
    rb.push(np.ones((5, 2), dtype=np.float32))
    r = rb.get_last(20)
    assert len(r) == 5, f"Expected 5, got {len(r)}"

    # wrap-around
    rb2 = RingBuffer(8, 1)
    rb2.push(np.arange(12, dtype=np.float32).reshape(12, 1))
    assert rb2.is_full
    result = rb2.get_last(8)
    expected = np.arange(4, 12, dtype=np.float32).reshape(8, 1)
    assert np.array_equal(result, expected), f"Wrap mismatch: {result.flatten()} != {expected.flatten()}"

    # oversized push
    rb3 = RingBuffer(4, 1)
    rb3.push(np.arange(10, dtype=np.float32).reshape(10, 1))
    assert rb3.n_samples == 4
    assert np.array_equal(rb3.get_last(4).flatten(), [6, 7, 8, 9])

    # clear
    rb3.clear()
    assert rb3.n_samples == 0

    print("[PASS] RingBuffer all checks")

# ---------- DemoTransport ----------
from neuropilot.domain.eeg.transports.demo import DemoTransport

def test_demo_transport():
    tp = DemoTransport(srate=250.0, n_channels=4)
    assert not tp.is_open
    tp.open()
    assert tp.is_open

    chunks = []
    t0 = time.monotonic()
    while time.monotonic() - t0 < 0.5:
        d = tp.read(timeout=0.0)
        if d is not None:
            chunks.append(d)
        time.sleep(0.005)
    tp.close()
    assert not tp.is_open
    assert chunks, "DemoTransport produced no data"
    all_data = np.concatenate(chunks, axis=0)
    assert all_data.shape[1] == 4
    assert np.abs(all_data).max() < 500.0
    print(f"[PASS] DemoTransport: {all_data.shape[0]} samples received")

# ---------- socketpair stop ----------
def test_stop_latency():
    tp = DemoTransport(srate=250.0, n_channels=8)
    r_pipe, w_pipe = socket.socketpair()
    samples: list = []
    done = threading.Event()

    def run():
        tp.open()
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
    time.sleep(0.2)

    t0 = time.monotonic()
    w_pipe.send(b"\x00")
    done.wait(timeout=1.0)
    elapsed = time.monotonic() - t0
    w_pipe.close()

    assert done.is_set(), "Thread did not stop!"
    assert elapsed < 0.3, f"Stop took {elapsed:.3f}s"
    assert sum(samples) > 0, "No samples received"
    print(f"[PASS] Stop latency: {elapsed*1000:.0f}ms, {sum(samples)} samples")

# ---------- Run all ----------
if __name__ == "__main__":
    test_ring_buffer()
    test_demo_transport()
    test_stop_latency()
    print("\n=== All Phase 3 smoke tests PASSED ===")
