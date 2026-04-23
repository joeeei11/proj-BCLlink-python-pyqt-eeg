from __future__ import annotations

from functools import partial
from typing import Literal

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.svm import SVC

from neuropilot.domain.dsp.filters import bandpass_filter
from neuropilot.domain.ml.csp import CSP

AlgoName = Literal["svm", "lr", "rf", "knn"]


def _apply_bandpass(
    X: np.ndarray,
    *,
    srate: float,
    low: float = 8.0,
    high: float = 30.0,
) -> np.ndarray:
    return np.array(
        [bandpass_filter(trial, srate=srate, low=low, high=high) for trial in X],
        dtype=np.float32,
    )


def _make_bandpass(srate: float, low: float = 8.0, high: float = 30.0) -> FunctionTransformer:
    transform = partial(_apply_bandpass, srate=srate, low=low, high=high)
    return FunctionTransformer(transform, validate=False)


def build_pipeline(
    algo: AlgoName = "svm",
    n_components: int = 4,
    srate: float = 250.0,
) -> Pipeline:
    clf: object
    if algo == "svm":
        clf = SVC(kernel="rbf", probability=True, C=1.0, gamma="scale")
    elif algo == "lr":
        clf = LogisticRegression(max_iter=1000, solver="lbfgs")
    elif algo == "rf":
        clf = RandomForestClassifier(n_estimators=100, n_jobs=1)
    elif algo == "knn":
        clf = KNeighborsClassifier(n_neighbors=5)
    else:
        raise ValueError(f"Unknown algorithm: {algo!r}")

    return Pipeline(
        [
            ("bandpass", _make_bandpass(srate)),
            ("csp", CSP(n_components=n_components)),
            ("scaler", StandardScaler()),
            ("clf", clf),
        ]
    )
