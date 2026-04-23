from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


class CSP(BaseEstimator, TransformerMixin):
    """Numerically stable two-class Common Spatial Pattern implementation."""

    def __init__(self, n_components: int = 4) -> None:
        self.n_components = n_components

    def fit(self, X: np.ndarray, y: np.ndarray) -> "CSP":
        classes = np.unique(y)
        if len(classes) != 2:
            raise ValueError(f"CSP requires exactly 2 classes, got {len(classes)}")

        eps = 1e-6

        def _cov(trials: np.ndarray) -> np.ndarray:
            cov = np.mean([trial.T @ trial / max(trial.shape[0], 1) for trial in trials], axis=0)
            cov += eps * np.eye(cov.shape[0])
            return cov

        cov0 = _cov(X[y == classes[0]])
        cov1 = _cov(X[y == classes[1]])
        cov_total = cov0 + cov1

        eigvals, eigvecs = np.linalg.eigh(cov_total)
        eigvals = np.maximum(eigvals, eps)
        whitening = eigvecs @ np.diag(eigvals ** -0.5) @ eigvecs.T

        s_matrix = whitening @ cov0 @ whitening.T
        eigenvalues, eigenvectors = np.linalg.eigh(s_matrix)

        order = np.argsort(eigenvalues)[::-1]
        n = max(1, self.n_components // 2)
        selected = np.concatenate([order[:n], order[-n:]])
        self.filters_ = (whitening.T @ eigenvectors)[:, selected]
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if not hasattr(self, "filters_"):
            raise RuntimeError("CSP not fitted. Call fit() first.")

        projected = X @ self.filters_
        variance = np.var(projected, axis=1)
        total = np.maximum(variance.sum(axis=1, keepdims=True), 1e-12)
        normalized = np.maximum(variance / total, 1e-12)
        return np.log(normalized)
