"""Unit tests for RingBuffer."""
import numpy as np
import pytest

from neuropilot.domain.eeg.ring_buffer import RingBuffer


def make_data(n: int, n_ch: int = 2, start: float = 0.0) -> np.ndarray:
    return np.tile(np.arange(start, start + n, dtype=np.float32)[:, None], (1, n_ch))


# ------------------------------------------------------------------
# Constructor
# ------------------------------------------------------------------

def test_empty_on_init() -> None:
    rb = RingBuffer(capacity=100, n_channels=2)
    assert rb.n_samples == 0
    assert not rb.is_full


def test_invalid_capacity() -> None:
    with pytest.raises(ValueError):
        RingBuffer(capacity=0, n_channels=2)


# ------------------------------------------------------------------
# get_last on under-filled buffer (the old bug case)
# ------------------------------------------------------------------

def test_get_last_returns_empty_when_no_data() -> None:
    rb = RingBuffer(capacity=100, n_channels=2)
    result = rb.get_last(10)
    assert result.shape == (0, 2)


def test_get_last_clamps_to_available() -> None:
    rb = RingBuffer(capacity=100, n_channels=2)
    rb.push(make_data(5))
    result = rb.get_last(20)
    assert len(result) == 5, "Should return only the 5 available samples, not raise or return None"


def test_get_last_exact_count() -> None:
    rb = RingBuffer(capacity=100, n_channels=2)
    rb.push(make_data(10))
    result = rb.get_last(10)
    assert len(result) == 10


# ------------------------------------------------------------------
# Wrap-around
# ------------------------------------------------------------------

def test_wrap_around_correct_order() -> None:
    rb = RingBuffer(capacity=8, n_channels=1)
    # Fill more than capacity
    rb.push(np.arange(12, dtype=np.float32).reshape(12, 1))
    assert rb.is_full
    result = rb.get_last(8)
    expected = np.arange(4, 12, dtype=np.float32).reshape(8, 1)
    np.testing.assert_array_equal(result, expected)


def test_get_last_partial_after_wrap() -> None:
    rb = RingBuffer(capacity=8, n_channels=1)
    rb.push(np.arange(10, dtype=np.float32).reshape(10, 1))
    result = rb.get_last(3)
    np.testing.assert_array_equal(result.flatten(), [7, 8, 9])


# ------------------------------------------------------------------
# Oversized push (n > capacity)
# ------------------------------------------------------------------

def test_push_larger_than_capacity() -> None:
    rb = RingBuffer(capacity=4, n_channels=1)
    data = np.arange(10, dtype=np.float32).reshape(10, 1)
    rb.push(data)
    assert rb.n_samples == 4
    result = rb.get_last(4)
    np.testing.assert_array_equal(result.flatten(), [6, 7, 8, 9])


# ------------------------------------------------------------------
# Multiple incremental pushes
# ------------------------------------------------------------------

def test_incremental_push() -> None:
    rb = RingBuffer(capacity=10, n_channels=2)
    for i in range(3):
        rb.push(make_data(3, start=float(i * 3)))
    assert rb.n_samples == 9
    last = rb.get_last(3)
    assert last.shape == (3, 2)
    np.testing.assert_array_equal(last[:, 0], [6.0, 7.0, 8.0])


# ------------------------------------------------------------------
# clear()
# ------------------------------------------------------------------

def test_clear() -> None:
    rb = RingBuffer(capacity=10, n_channels=2)
    rb.push(make_data(5))
    rb.clear()
    assert rb.n_samples == 0
    assert rb.get_last(5).shape == (0, 2)
