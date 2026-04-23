from __future__ import annotations

import threading
from typing import Optional

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from neuropilot.app.event_bus import EventBus
from neuropilot.domain.eeg.ring_buffer import RingBuffer


class Predictor(QObject):
    """Online EEG predictor.

    Subscribes to ``EventBus.eeg_samples`` and accumulates data in a
    RingBuffer.  When a trial is active (between ``begin_voting`` /
    ``end_voting``), emits ``prediction_result`` every 500 ms.

    Tie-breaking:
        If both classes have equal vote counts, the winner is chosen by
        ``np.random.default_rng()`` — no fixed seed — to avoid the old
        systematic left-bias bug.
    """

    def __init__(
        self,
        parent: Optional[QObject] = None,
        window_ms: int = 2000,
        step_ms: int = 500,
        srate: float = 250.0,
        n_channels: int = 8,
    ) -> None:
        super().__init__(parent)
        self._window_ms = window_ms
        self._step_ms = step_ms
        self._srate = srate
        self._n_channels = n_channels
        self._window_samples = int(srate * window_ms / 1000)
        self._step_samples = int(srate * step_ms / 1000)
        self._buf = RingBuffer(capacity=self._window_samples * 2, n_channels=n_channels)
        self._pipeline: object = None
        self._classes: list[str] = ["left", "right"]
        self._voting: bool = False
        self._votes: list[int] = []
        self._lock = threading.Lock()
        self._trial_uuid: Optional[str] = None
        self._samples_since_pred = 0

        EventBus.instance().eeg_samples.connect(self._on_samples)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_pipeline(self, pipeline: object, classes: list[str]) -> None:
        with self._lock:
            self._pipeline = pipeline
            self._classes = classes

    def update_sampling(self, srate: float, n_channels: int) -> None:
        with self._lock:
            self._srate = srate
            self._n_channels = n_channels
            self._window_samples = int(srate * self._window_ms / 1000)
            self._step_samples = int(srate * self._step_ms / 1000)
            self._buf = RingBuffer(capacity=self._window_samples * 2, n_channels=n_channels)
            self._samples_since_pred = 0

    def begin_voting(self, trial_uuid: str) -> None:
        with self._lock:
            self._trial_uuid = trial_uuid
            self._votes = []
            self._voting = True
            self._samples_since_pred = 0

    def end_voting(self, trial_uuid: str) -> None:
        with self._lock:
            if self._trial_uuid != trial_uuid:
                return
            self._voting = False
            self._emit_final_vote()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_samples(self, data: np.ndarray) -> None:
        with self._lock:
            if data.shape[1] != self._n_channels:
                # Channel count changed — rebuild buffer
                self._n_channels = data.shape[1]
                self._buf = RingBuffer(
                    capacity=self._window_samples * 2, n_channels=self._n_channels
                )
            self._buf.push(data)
            self._samples_since_pred += len(data)

            if not self._voting or self._pipeline is None:
                return
            if self._samples_since_pred < self._step_samples:
                return

            self._samples_since_pred = 0
            window = self._buf.get_last(self._window_samples)
            if len(window) < self._window_samples:
                return
            self._run_prediction(window)

    def _run_prediction(self, window: np.ndarray) -> None:
        X = window[np.newaxis, :, :]  # (1, n_samples, n_channels)
        try:
            proba = self._pipeline.predict_proba(X)[0]  # type: ignore[union-attr]
        except Exception:
            return
        pred_idx = int(np.argmax(proba))
        self._votes.append(pred_idx)

    def _emit_final_vote(self) -> None:
        if not self._votes:
            return
        counts = np.bincount(self._votes, minlength=len(self._classes))
        max_count = counts.max()
        winners = np.where(counts == max_count)[0]
        if len(winners) > 1:
            # Tie — random selection, no fixed seed
            rng = np.random.default_rng()
            winner_idx = int(rng.choice(winners))
        else:
            winner_idx = int(winners[0])

        label = self._classes[winner_idx] if winner_idx < len(self._classes) else "unknown"
        # Confidence: fraction of votes for the winner
        confidence = float(counts[winner_idx] / len(self._votes))
        EventBus.instance().prediction_result.emit(label, confidence)
