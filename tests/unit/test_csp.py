"""Unit tests for CSP."""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.utils.estimator_checks import parametrize_with_checks

from neuropilot.domain.ml.csp import CSP


def _make_data(
    n_trials: int = 20,
    n_samples: int = 250,
    n_channels: int = 8,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X0 = rng.standard_normal((n_trials // 2, n_samples, n_channels)).astype(np.float32)
    X1 = rng.standard_normal((n_trials // 2, n_samples, n_channels)).astype(np.float32)
    # Make class 1 have higher power on first channel
    X1[:, :, 0] *= 5.0
    X = np.concatenate([X0, X1], axis=0)
    y = np.array([0] * (n_trials // 2) + [1] * (n_trials // 2))
    return X, y


# ------------------------------------------------------------------
# Basic fit/transform
# ------------------------------------------------------------------

def test_fit_transform_shape() -> None:
    X, y = _make_data(20, 250, 8)
    csp = CSP(n_components=4)
    features = csp.fit_transform(X, y)
    assert features.shape == (20, 4)


def test_n_components_must_be_even() -> None:
    X, y = _make_data(10, 100, 4)
    csp = CSP(n_components=2)
    features = csp.fit_transform(X, y)
    assert features.shape == (10, 2)


def test_no_nan_inf_in_features() -> None:
    X, y = _make_data(20, 250, 8)
    features = CSP(4).fit_transform(X, y)
    assert np.all(np.isfinite(features)), "Features contain NaN or Inf"


# ------------------------------------------------------------------
# Numerical stability
# ------------------------------------------------------------------

def test_zero_variance_trial_does_not_crash() -> None:
    """A trial with all-zero samples must not cause log(0) = -inf."""
    X, y = _make_data(20, 250, 8)
    X[0] = 0.0  # zero-variance trial
    features = CSP(4).fit_transform(X, y)
    assert np.all(np.isfinite(features))


def test_two_classes_required() -> None:
    X, y = _make_data(10, 100, 4)
    y[:] = 0  # single class
    with pytest.raises(ValueError):
        CSP(2).fit(X, y)


# ------------------------------------------------------------------
# Transform before fit raises
# ------------------------------------------------------------------

def test_transform_without_fit_raises() -> None:
    X, _ = _make_data(10, 100, 4)
    with pytest.raises(RuntimeError):
        CSP(2).transform(X)
