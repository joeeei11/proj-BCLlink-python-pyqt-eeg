from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt


def bandpass_filter(
    data: np.ndarray,
    srate: float,
    low: float = 8.0,
    high: float = 30.0,
    order: int = 4,
) -> np.ndarray:
    """Zero-phase Butterworth bandpass filter.

    Parameters
    ----------
    data : ndarray of shape (n_samples, n_channels)
    srate : sampling rate in Hz
    low, high : passband edges in Hz
    order : filter order (applied to each half via sosfiltfilt → effective 2*order)

    Returns
    -------
    filtered : same shape as data
    """
    nyq = srate / 2.0
    sos = butter(order, [low / nyq, high / nyq], btype="band", output="sos")
    return sosfiltfilt(sos, data, axis=0).astype(np.float32)


def notch_filter(
    data: np.ndarray,
    srate: float,
    freq: float = 50.0,
    q: float = 30.0,
) -> np.ndarray:
    """Zero-phase notch filter (e.g., 50 Hz power-line removal)."""
    from scipy.signal import iirnotch
    b, a = iirnotch(freq / (srate / 2.0), q)
    from scipy.signal import sosfilt, tf2sos
    sos = tf2sos(b, a)
    return sosfiltfilt(sos, data, axis=0).astype(np.float32)
