from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from sqlalchemy import text

from neuropilot.infra.db.repositories._base import RepositoryBase, SessionSource


class TrialDTO(BaseModel):
    id: int
    session_id: int
    trial_uuid: str
    label: str
    onset_time: str
    offset_time: Optional[str]
    predicted: Optional[str]
    confidence: Optional[float]
    eeg_file: Optional[str]
    created_at: str


class TrialRepo(RepositoryBase):
    def __init__(self, session: SessionSource) -> None:
        super().__init__(session)

    def create(
        self,
        session_id: int,
        trial_uuid: str,
        label: str,
        onset_time: str,
        offset_time: Optional[str] = None,
        predicted: Optional[str] = None,
        confidence: Optional[float] = None,
        eeg_file: Optional[str] = None,
    ) -> int:
        with self._session(write=True) as session:
            result = session.execute(
                text(
                    "INSERT INTO trials "
                    "(session_id, trial_uuid, label, onset_time, offset_time, "
                    "predicted, confidence, eeg_file) "
                    "VALUES (:sid, :uuid, :lbl, :on, :off, :pred, :conf, :ef)"
                ),
                {
                    "sid": session_id,
                    "uuid": trial_uuid,
                    "lbl": label,
                    "on": onset_time,
                    "off": offset_time,
                    "pred": predicted,
                    "conf": confidence,
                    "ef": eeg_file,
                },
            )
            session.flush()
            return result.lastrowid  # type: ignore[return-value]

    def list_by_session(self, session_id: int) -> list[TrialDTO]:
        with self._session() as session:
            rows = session.execute(
                text(
                    "SELECT id, session_id, trial_uuid, label, onset_time, offset_time, "
                    "predicted, confidence, eeg_file, created_at "
                    "FROM trials WHERE session_id = :sid ORDER BY onset_time"
                ),
                {"sid": session_id},
            ).fetchall()
        return [_row_to_dto(r) for r in rows]

    def get(self, trial_uuid: str) -> Optional[TrialDTO]:
        with self._session() as session:
            row = session.execute(
                text(
                    "SELECT id, session_id, trial_uuid, label, onset_time, offset_time, "
                    "predicted, confidence, eeg_file, created_at "
                    "FROM trials WHERE trial_uuid = :uuid"
                ),
                {"uuid": trial_uuid},
            ).fetchone()
        return _row_to_dto(row) if row else None

    def update_prediction(self, trial_uuid: str, predicted: str, confidence: float) -> None:
        with self._session(write=True) as session:
            session.execute(
                text(
                    "UPDATE trials SET predicted = :pred, confidence = :conf "
                    "WHERE trial_uuid = :uuid"
                ),
                {"pred": predicted, "conf": confidence, "uuid": trial_uuid},
            )


def _row_to_dto(row: object) -> TrialDTO:
    return TrialDTO(
        id=row[0],
        session_id=row[1],
        trial_uuid=row[2],
        label=row[3],
        onset_time=row[4],
        offset_time=row[5],
        predicted=row[6],
        confidence=row[7],
        eeg_file=row[8],
        created_at=row[9],
    )
