from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import text

from neuropilot.infra.db.repositories._base import RepositoryBase, SessionSource


class SessionDTO(BaseModel):
    id: int
    subject_id: int
    user_id: int
    paradigm: str
    status: str
    transport: Optional[str]
    n_channels: Optional[int]
    srate: Optional[float]
    started_at: str
    stopped_at: Optional[str]
    notes: Optional[str]


class SessionRepo(RepositoryBase):
    def __init__(self, session: SessionSource) -> None:
        super().__init__(session)

    def create(
        self,
        subject_id: int,
        user_id: int,
        transport: Optional[str] = None,
        n_channels: Optional[int] = None,
        srate: Optional[float] = None,
        paradigm: str = "MI",
    ) -> int:
        with self._session(write=True) as session:
            result = session.execute(
                text(
                    "INSERT INTO sessions "
                    "(subject_id, user_id, paradigm, transport, n_channels, srate) "
                    "VALUES (:sid, :uid, :par, :tp, :nch, :sr)"
                ),
                {
                    "sid": subject_id,
                    "uid": user_id,
                    "par": paradigm,
                    "tp": transport,
                    "nch": n_channels,
                    "sr": srate,
                },
            )
            session.flush()
            return result.lastrowid  # type: ignore[return-value]

    def set_stopped(self, session_id: int, status: str = "completed") -> None:
        with self._session(write=True) as session:
            session.execute(
                text(
                    "UPDATE sessions SET stopped_at = :now, status = :status "
                    "WHERE id = :id"
                ),
                {"now": _now_iso(), "status": status, "id": session_id},
            )

    def get(self, session_id: int) -> Optional[SessionDTO]:
        with self._session() as session:
            row = session.execute(
                text(
                    "SELECT id, subject_id, user_id, paradigm, status, transport, "
                    "n_channels, srate, started_at, stopped_at, notes "
                    "FROM sessions WHERE id = :id"
                ),
                {"id": session_id},
            ).fetchone()
        return _row_to_dto(row) if row else None

    def list_all(self) -> list[SessionDTO]:
        with self._session() as session:
            rows = session.execute(
                text(
                    "SELECT id, subject_id, user_id, paradigm, status, transport, "
                    "n_channels, srate, started_at, stopped_at, notes "
                    "FROM sessions ORDER BY started_at DESC"
                ),
            ).fetchall()
        return [_row_to_dto(r) for r in rows]

    def list_by_subject(self, subject_id: int) -> list[SessionDTO]:
        with self._session() as session:
            rows = session.execute(
                text(
                    "SELECT id, subject_id, user_id, paradigm, status, transport, "
                    "n_channels, srate, started_at, stopped_at, notes "
                    "FROM sessions WHERE subject_id = :sid ORDER BY started_at DESC"
                ),
                {"sid": subject_id},
            ).fetchall()
        return [_row_to_dto(r) for r in rows]


def _row_to_dto(row: object) -> SessionDTO:
    return SessionDTO(
        id=row[0],
        subject_id=row[1],
        user_id=row[2],
        paradigm=row[3],
        status=row[4],
        transport=row[5],
        n_channels=row[6],
        srate=row[7],
        started_at=row[8],
        stopped_at=row[9],
        notes=row[10],
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
