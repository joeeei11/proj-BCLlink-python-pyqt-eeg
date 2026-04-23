from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class DependencyMissingError(RuntimeError):
    """Raised when an optional transport dependency is not installed."""


class TransportError(RuntimeError):
    """Raised for transport-level I/O errors."""


class IDeviceTransport(ABC):
    """Abstract EEG transport strategy.

    Implementations must be **non-Qt** (no PyQt5 imports).
    All I/O operations accept an explicit `timeout` parameter.
    """

    @property
    @abstractmethod
    def srate(self) -> float:
        """Nominal sampling rate in Hz."""

    @property
    @abstractmethod
    def n_channels(self) -> int:
        """Number of EEG channels."""

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """True when the connection is established."""

    @abstractmethod
    def open(self, timeout: float = 5.0) -> None:
        """Establish connection.

        Raises:
            DependencyMissingError: if required package is not installed.
            TransportError: on connection failure.
        """

    @abstractmethod
    def close(self) -> None:
        """Tear down connection. Must be idempotent."""

    @abstractmethod
    def read(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """Try to read a chunk of samples.

        Returns:
            ndarray of shape (n_samples, n_channels) in µV, or None if no data
            is ready within the timeout window.
        """

    def write(self, payload: bytes) -> None:
        """Send raw bytes to the device (bidirectional transports only).

        Default implementation raises NotImplementedError.  Override in
        Serial / Bluetooth / TCP / UDP transports for device-control use.

        Raises:
            NotImplementedError: for read-only transports (Demo, LSL).
            TransportError: on I/O failure.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support write()")
