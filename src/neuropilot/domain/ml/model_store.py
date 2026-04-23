from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib
from pydantic import BaseModel
from sklearn.pipeline import Pipeline

from neuropilot.infra.db.repositories._base import SessionSource
from neuropilot.infra.db.repositories.model_repo import ModelRepo


class ModelRecord(BaseModel):
    id: int
    subject_id: Optional[int]
    name: str
    algorithm: str
    file_path: str
    sha256: str
    accuracy: Optional[float]
    is_active: bool


class ModelStore:
    """Persist and load scikit-learn pipelines with sha256 integrity checks."""

    def __init__(self, session: SessionSource, models_dir: str | Path) -> None:
        self._repo = ModelRepo(session)
        self._dir = Path(models_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        pipeline: Pipeline,
        subject_id: int,
        algo: str,
        accuracy: Optional[float] = None,
        name: Optional[str] = None,
    ) -> ModelRecord:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        model_name = name or f"{algo}_{ts}"
        rel_path = f"subj{subject_id}_{model_name}.pkl"
        abs_path = self._dir / rel_path

        joblib.dump(pipeline, abs_path)
        sha = _sha256(abs_path)

        record_id = self._repo.create(
            subject_id=subject_id,
            name=model_name,
            algorithm=algo,
            file_path=str(rel_path),
            sha256=sha,
            accuracy=accuracy,
        )
        return ModelRecord(
            id=record_id,
            subject_id=subject_id,
            name=model_name,
            algorithm=algo,
            file_path=str(rel_path),
            sha256=sha,
            accuracy=accuracy,
            is_active=False,
        )

    def load(self, model_id: int) -> Pipeline:
        record = self._repo.get(model_id)
        if record is None:
            raise FileNotFoundError(f"Model id={model_id} not found in database.")

        abs_path = self._dir / record.file_path
        if not abs_path.exists():
            raise FileNotFoundError(f"Model file missing: {abs_path}")

        sha = _sha256(abs_path)
        if sha != record.sha256:
            raise ValueError(
                f"Model file integrity check failed for id={model_id}. "
                "File may have been tampered with."
            )

        pipeline: Pipeline = joblib.load(abs_path)
        return pipeline

    def list_by_subject(self, subject_id: int) -> list[ModelRecord]:
        return [
            ModelRecord(
                id=r.id,
                subject_id=r.subject_id,
                name=r.name,
                algorithm=r.algorithm,
                file_path=r.file_path,
                sha256=r.sha256,
                accuracy=r.accuracy,
                is_active=bool(r.is_active),
            )
            for r in self._repo.list_by_subject(subject_id)
        ]

    def activate(self, model_id: int) -> None:
        self._repo.set_active(model_id)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
