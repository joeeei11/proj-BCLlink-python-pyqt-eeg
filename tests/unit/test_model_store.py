"""Unit tests for ModelStore — save, load, tamper rejection."""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.pipeline import Pipeline

from neuropilot.domain.ml.model_store import ModelStore
from neuropilot.domain.ml.pipelines import build_pipeline


@pytest.fixture()
def store_and_pipeline(tmp_path, monkeypatch):
    """Return a ModelStore backed by an in-memory SQLite DB."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from neuropilot.infra.db.engine import _apply_schema

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()
    _apply_schema(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    store = ModelStore(session=session, models_dir=tmp_path / "models")
    pipeline = build_pipeline(algo="svm", n_components=2, srate=250.0)

    # Fit with minimal dummy data
    rng = np.random.default_rng(42)
    X = rng.standard_normal((20, 250, 4)).astype(np.float32)
    y = np.array([0] * 10 + [1] * 10)
    pipeline.fit(X, y)

    return store, pipeline, session


def test_save_and_load(store_and_pipeline) -> None:
    store, pipeline, _ = store_and_pipeline
    record = store.save(pipeline, subject_id=1, algo="svm", accuracy=0.85)
    assert record.id > 0
    assert record.sha256 != ""

    loaded = store.load(record.id)
    assert isinstance(loaded, Pipeline)


def test_load_after_tamper_raises(store_and_pipeline, tmp_path) -> None:
    store, pipeline, _ = store_and_pipeline
    record = store.save(pipeline, subject_id=1, algo="svm")

    # Tamper with the file
    model_path = tmp_path / "models" / record.file_path
    with open(model_path, "ab") as f:
        f.write(b"\xff\xff")

    with pytest.raises(ValueError, match="integrity check failed"):
        store.load(record.id)


def test_load_missing_file_raises(store_and_pipeline, tmp_path) -> None:
    store, pipeline, _ = store_and_pipeline
    record = store.save(pipeline, subject_id=1, algo="svm")

    model_path = tmp_path / "models" / record.file_path
    model_path.unlink()

    with pytest.raises(FileNotFoundError):
        store.load(record.id)


def test_load_unknown_id_raises(store_and_pipeline) -> None:
    store, _, _ = store_and_pipeline
    with pytest.raises(FileNotFoundError):
        store.load(99999)
