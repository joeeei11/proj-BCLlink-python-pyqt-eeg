from __future__ import annotations

import numpy as np


class RingBuffer:
    """Fixed-capacity circular buffer for EEG samples.

    Thread-safety: not guaranteed. Callers must synchronise if used across threads.

    Key fix vs. the old implementation:
        ``get_last(n)`` used to return None when the buffer was not full and
        ``self._idx < n``.  It now clamps ``n`` to the number of samples
        actually available and returns whatever is there (may be fewer than n).
    """

    def __init__(self, capacity: int, n_channels: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._cap = capacity
        self._n_ch = n_channels
        self._buf = np.zeros((capacity, n_channels), dtype=np.float32)
        self._idx = 0       # next write position
        self._count = 0     # samples stored (≤ capacity)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def push(self, samples: np.ndarray) -> None:
        """Append samples to the ring buffer.

        Args:
            samples: shape (n, n_channels).  If n > capacity, only the last
                     ``capacity`` samples are retained.
        """
        n = len(samples)
        if n == 0:
            return
        if n >= self._cap:
            self._buf[:] = samples[-self._cap:]
            self._idx = 0
            self._count = self._cap
            return

        end = self._idx + n
        if end <= self._cap:
            self._buf[self._idx:end] = samples
        else:
            first = self._cap - self._idx
            self._buf[self._idx:] = samples[:first]
            self._buf[: n - first] = samples[first:]

        self._idx = end % self._cap
        self._count = min(self._count + n, self._cap)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_last(self, n: int) -> np.ndarray:
        """Return the last *up to* n samples in chronological order.

        If fewer than n samples have been written, returns however many
        are available (never raises, never returns None).

        Returns:
            ndarray of shape (actual_n, n_channels), dtype float32.
        """
        n = min(n, self._count)
        if n == 0:
            return np.zeros((0, self._n_ch), dtype=np.float32)

        start = (self._idx - n) % self._cap
        if start + n <= self._cap:
            return self._buf[start : start + n].copy()

        # Wraps around
        first = self._cap - start
        return np.concatenate([self._buf[start:], self._buf[: n - first]])

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def n_samples(self) -> int:
        """Number of samples currently stored."""
        return self._count

    @property
    def capacity(self) -> int:
        return self._cap

    @property
    def n_channels(self) -> int:
        return self._n_ch

    @property
    def is_full(self) -> bool:
        return self._count == self._cap

    def clear(self) -> None:
        self._idx = 0
        self._count = 0
