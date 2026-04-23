from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from neuropilot.infra.db.repositories.trial_repo import TrialRepo


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class TrialDraft:
    uuid: str
    intent: str
    session_id: int
    onset_at: str
    predicted: Optional[str] = None
    confidence: Optional[float] = None
    device_send_ok: Optional[bool] = None
    device_msg: Optional[str] = None
    _closed: bool = field(default=False, repr=False)


class TrialRecorder:
    """Thread-safe accumulator for trial events before DB commit.

    Usage
    -----
    recorder.open(uuid, intent, session_id)
    recorder.record_prediction(uuid, "left", 0.87)
    recorder.record_device_send(uuid, ok=True, msg="")
    recorder.close(uuid)   # writes to DB

    Orphan flush:
        Any draft open for > 5 s is auto-flushed with predicted='unknown'
        when ``flush_orphans()`` is called (e.g., on session stop).
    """

    _ORPHAN_SECS = 5.0

    def __init__(self, trial_repo: TrialRepo) -> None:
        self._repo = trial_repo
        self._drafts: dict[str, TrialDraft] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self, trial_uuid: str, intent: str, session_id: int) -> TrialDraft:
        with self._lock:
            draft = TrialDraft(
                uuid=trial_uuid,
                intent=intent,
                session_id=session_id,
                onset_at=_now_iso(),
            )
            self._drafts[trial_uuid] = draft
            return draft

    def record_prediction(
        self, trial_uuid: str, predicted: str, confidence: float
    ) -> None:
        with self._lock:
            draft = self._drafts.get(trial_uuid)
            if draft is not None:
                draft.predicted = predicted
                draft.confidence = confidence

    def record_device_send(
        self, trial_uuid: str, ok: bool, msg: str = ""
    ) -> None:
        with self._lock:
            draft = self._drafts.get(trial_uuid)
            if draft is not None:
                draft.device_send_ok = ok
                draft.device_msg = msg

    def close(self, trial_uuid: str) -> None:
        with self._lock:
            draft = self._drafts.pop(trial_uuid, None)
        if draft is not None:
            self._write(draft)

    def flush_orphans(self) -> None:
        """Called on session stop to persist any open drafts."""
        with self._lock:
            orphans = list(self._drafts.values())
            self._drafts.clear()
        for draft in orphans:
            if draft.predicted is None:
                draft.predicted = "unknown"
            self._write(draft)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write(self, draft: TrialDraft) -> None:
        try:
            self._repo.create(
                session_id=draft.session_id,
                trial_uuid=draft.uuid,
                label=draft.intent,
                onset_time=draft.onset_at,
                offset_time=_now_iso(),
                predicted=draft.predicted,
                confidence=draft.confidence,
            )
        except Exception:
            from loguru import logger
            logger.exception("TrialRecorder: failed to write trial {}", draft.uuid)
