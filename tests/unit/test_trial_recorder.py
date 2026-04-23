"""Unit tests for TrialRecorder."""
from __future__ import annotations

import uuid
from typing import Optional
from unittest.mock import MagicMock, call

import pytest

from neuropilot.app.trial_recorder import TrialRecorder
from neuropilot.infra.db.repositories.trial_repo import TrialRepo


def _make_recorder() -> tuple[TrialRecorder, MagicMock]:
    mock_repo = MagicMock(spec=TrialRepo)
    mock_repo.create.return_value = 1
    return TrialRecorder(mock_repo), mock_repo


def _uuid() -> str:
    return str(uuid.uuid4())


def test_open_and_close_writes_to_repo() -> None:
    rec, repo = _make_recorder()
    uid = _uuid()
    rec.open(uid, "left", session_id=1)
    rec.record_prediction(uid, "left", 0.9)
    rec.close(uid)

    repo.create.assert_called_once()
    kwargs = repo.create.call_args[1]
    assert kwargs["trial_uuid"] == uid
    assert kwargs["label"] == "left"
    assert kwargs["predicted"] == "left"
    assert kwargs["confidence"] == pytest.approx(0.9)


def test_close_unknown_uuid_is_noop() -> None:
    rec, repo = _make_recorder()
    rec.close("does-not-exist")
    repo.create.assert_not_called()


def test_record_prediction_on_unknown_uuid_is_noop() -> None:
    rec, repo = _make_recorder()
    rec.record_prediction("bad-uuid", "right", 0.5)
    repo.create.assert_not_called()


def test_flush_orphans_writes_with_unknown_prediction() -> None:
    rec, repo = _make_recorder()
    uid = _uuid()
    rec.open(uid, "right", session_id=2)
    rec.flush_orphans()

    repo.create.assert_called_once()
    kwargs = repo.create.call_args[1]
    assert kwargs["predicted"] == "unknown"


def test_interleaved_trials() -> None:
    rec, repo = _make_recorder()
    u1, u2 = _uuid(), _uuid()
    rec.open(u1, "left", session_id=1)
    rec.open(u2, "right", session_id=1)
    rec.record_prediction(u1, "left", 0.8)
    rec.record_prediction(u2, "right", 0.7)
    rec.close(u1)
    rec.close(u2)

    assert repo.create.call_count == 2
    calls_uuids = {c[1]["trial_uuid"] for c in repo.create.call_args_list}
    assert calls_uuids == {u1, u2}
