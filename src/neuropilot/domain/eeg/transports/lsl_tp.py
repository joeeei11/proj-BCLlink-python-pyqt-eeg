from __future__ import annotations

from typing import Optional

import numpy as np

from neuropilot.domain.eeg.transports.base import (
    DependencyMissingError,
    IDeviceTransport,
    TransportError,
)


class LSLTransport(IDeviceTransport):
    """Lab Streaming Layer (LSL) EEG source.

    Uses ``pylsl.resolve_byprop`` (the current, non-deprecated API).
    srate and n_channels are overridden from the discovered stream info.
    """

    def __init__(
        self,
        stream_name: str = "NeuroPilot",
        srate: float = 250.0,
        n_channels: int = 8,
    ) -> None:
        self._stream_name = stream_name
        self._srate = srate
        self._n_channels = n_channels
        self._inlet: object = None

    @property
    def srate(self) -> float:
        return self._srate

    @property
    def n_channels(self) -> int:
        return self._n_channels

    @property
    def is_open(self) -> bool:
        return self._inlet is not None

    def open(self, timeout: float = 5.0) -> None:
        try:
            import pylsl  # type: ignore[import]
        except ImportError as exc:
            raise DependencyMissingError(
                "pylsl is required for LSL transport. "
                "Install with: pip install pylsl"
            ) from exc

        streams = pylsl.resolve_byprop("name", self._stream_name, timeout=timeout)
        if not streams:
            streams = pylsl.resolve_byprop("type", "EEG", timeout=2.0)
        if not streams:
            raise TransportError(
                f"No LSL stream found (name='{self._stream_name}', type='EEG')"
            )
        info = streams[0]
        # Override srate/n_channels from actual stream
        self._srate = info.nominal_srate() or self._srate
        self._n_channels = info.channel_count() or self._n_channels
        self._inlet = pylsl.StreamInlet(info, max_buflen=360)

    def close(self) -> None:
        if self._inlet is not None:
            try:
                self._inlet.close_stream()  # type: ignore[union-attr]
            except Exception:
                pass
            self._inlet = None

    def read(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        if self._inlet is None:
            return None
        try:
            chunk, _ = self._inlet.pull_chunk(timeout=timeout, max_samples=128)  # type: ignore[union-attr]
        except Exception as exc:
            raise TransportError(f"LSL pull_chunk error: {exc}") from exc
        if not chunk:
            return None
        return np.array(chunk, dtype=np.float32)  # (n_samples, n_channels)
