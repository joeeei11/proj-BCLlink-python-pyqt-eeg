from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from neuropilot.infra.db.repositories.session_repo import SessionRepo
from neuropilot.infra.db.repositories.trial_repo import TrialRepo


@dataclass
class TrainingDataset:
    X: np.ndarray
    y: np.ndarray
    srate: float


def build_subject_dataset(
    subject_id: int,
    session_repo: SessionRepo,
    trial_repo: TrialRepo,
    data_dir: str | Path,
    *,
    min_samples: int = 32,
) -> TrainingDataset:
    data_root = Path(data_dir) / "raw_eeg"
    sessions = session_repo.list_by_subject(subject_id)
    if not sessions:
        raise ValueError("No sessions found for the selected subject.")

    segments: list[np.ndarray] = []
    labels: list[int] = []
    rates: list[float] = []

    for session in sessions:
        csv_path = _find_session_csv(data_root, subject_id, session.id)
        if csv_path is None:
            continue

        raw = np.genfromtxt(csv_path, delimiter=",", skip_header=1)
        if raw.size == 0:
            continue
        if raw.ndim == 1:
            raw = raw.reshape(1, -1)
        if raw.shape[1] < 2:
            continue

        times = raw[:, 0].astype(float)
        eeg = raw[:, 1:].astype(np.float32)
        if eeg.ndim != 2 or eeg.shape[0] < min_samples:
            continue

        session_start = _parse_iso(session.started_at)
        session_rate = float(session.srate) if session.srate else _infer_srate(times)
        if session_rate <= 0:
            continue

        for trial in trial_repo.list_by_session(session.id):
            if trial.label not in {"left", "right"} or trial.offset_time is None:
                continue
            onset = max(0.0, (_parse_iso(trial.onset_time) - session_start).total_seconds())
            offset = max(onset, (_parse_iso(trial.offset_time) - session_start).total_seconds())
            mask = (times >= onset) & (times <= offset)
            segment = eeg[mask]
            if len(segment) < min_samples:
                continue
            segments.append(segment)
            labels.append(0 if trial.label == "left" else 1)
            rates.append(session_rate)

    if not segments:
        raise ValueError("No trial-aligned EEG segments were found for training.")

    channel_count = segments[0].shape[1]
    filtered = [
        (segment, label, rate)
        for segment, label, rate in zip(segments, labels, rates, strict=True)
        if segment.shape[1] == channel_count
    ]
    if len(filtered) < 2:
        raise ValueError("Not enough compatible trials were found for training.")

    class_counts = np.bincount(np.array([label for _, label, _ in filtered], dtype=np.int64))
    if len(class_counts) < 2 or class_counts.min() < 2:
        raise ValueError("Training requires at least two trials for each class.")

    sample_count = min(segment.shape[0] for segment, _, _ in filtered)
    if sample_count < min_samples:
        raise ValueError("Trial windows are too short to train a model.")

    X = np.stack([segment[:sample_count] for segment, _, _ in filtered], axis=0)
    y = np.array([label for _, label, _ in filtered], dtype=np.int64)
    srate = float(np.mean([rate for _, _, rate in filtered]))

    return TrainingDataset(X=X, y=y, srate=srate)


def _find_session_csv(data_root: Path, subject_id: int, session_id: int) -> Path | None:
    matches = sorted(data_root.glob(f"subj{subject_id}_{session_id}_*.csv"))
    return matches[-1] if matches else None


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _infer_srate(times: np.ndarray) -> float:
    diffs = np.diff(times)
    diffs = diffs[diffs > 0]
    if len(diffs) == 0:
        return 0.0
    return float(round(1.0 / float(np.median(diffs)), 3))
