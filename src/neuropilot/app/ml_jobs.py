from __future__ import annotations

import numpy as np
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal
from sklearn.model_selection import cross_val_score

from neuropilot.domain.ml.model_store import ModelStore
from neuropilot.domain.ml.pipelines import AlgoName, build_pipeline


class _JobSignals(QObject):
    sig_progress = pyqtSignal(int, str)
    sig_done = pyqtSignal(object)
    sig_failed = pyqtSignal(str)


class TrainJob(QRunnable):
    """Async ML training job running in QThreadPool."""

    def __init__(
        self,
        X: np.ndarray,
        y: np.ndarray,
        model_store: ModelStore,
        subject_id: int,
        algo: AlgoName = "svm",
        n_components: int = 4,
        srate: float = 250.0,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._X = X
        self._y = y
        self._store = model_store
        self._subject_id = subject_id
        self._algo = algo
        self._n_components = n_components
        self._srate = srate
        self.signals = _JobSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            self.signals.sig_progress.emit(5, "Building pipeline...")
            pipeline = build_pipeline(
                algo=self._algo,
                n_components=self._n_components,
                srate=self._srate,
            )

            if self._cancelled:
                return

            class_counts = np.bincount(self._y)
            non_zero_counts = class_counts[class_counts > 0]
            if len(non_zero_counts) < 2 or non_zero_counts.min() < 2:
                raise ValueError("Training requires at least two samples for each class.")

            self.signals.sig_progress.emit(20, "Running cross-validation...")
            cv = min(5, int(non_zero_counts.min()))
            scores = cross_val_score(
                pipeline, self._X, self._y, cv=cv, scoring="accuracy", n_jobs=1
            )
            accuracy = float(scores.mean())

            if self._cancelled:
                return

            self.signals.sig_progress.emit(80, "Fitting full dataset...")
            pipeline.fit(self._X, self._y)

            if self._cancelled:
                return

            self.signals.sig_progress.emit(95, "Saving model...")
            record = self._store.save(
                pipeline=pipeline,
                subject_id=self._subject_id,
                algo=self._algo,
                accuracy=accuracy,
            )

            self.signals.sig_progress.emit(100, "Training complete")
            self.signals.sig_done.emit(record)
        except Exception as exc:
            self.signals.sig_failed.emit(str(exc))
