from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import text

from neuropilot.infra.db.repositories._base import RepositoryBase, SessionSource


class UserDTO(BaseModel):
    id: int
    username: str
    role: str
    failed_count: int
    locked_until: Optional[str]
    created_at: str
    updated_at: str


class UserRepo(RepositoryBase):
    def __init__(self, session: SessionSource) -> None:
        super().__init__(session)

    def get_by_username(self, username: str) -> Optional[UserDTO]:
        with self._session() as session:
            row = session.execute(
                text(
                    "SELECT id, username, role, failed_count, locked_until, created_at, updated_at "
                    "FROM users WHERE username = :u"
                ),
                {"u": username},
            ).fetchone()
        if row is None:
            return None
        return UserDTO(
            id=row[0],
            username=row[1],
            role=row[2],
            failed_count=row[3],
            locked_until=row[4],
            created_at=row[5],
            updated_at=row[6],
        )

    def get_password_hash(self, username: str) -> Optional[str]:
        with self._session() as session:
            row = session.execute(
                text("SELECT password_hash FROM users WHERE username = :u"),
                {"u": username},
            ).fetchone()
        return row[0] if row else None

    def create(self, username: str, password_hash: str, role: str = "researcher") -> int:
        with self._session(write=True) as session:
            result = session.execute(
                text("INSERT INTO users (username, password_hash, role) VALUES (:u, :h, :r)"),
                {"u": username, "h": password_hash, "r": role},
            )
            session.flush()
            return result.lastrowid  # type: ignore[return-value]

    def increment_failed(self, username: str) -> None:
        now = _now_iso()
        with self._session(write=True) as session:
            session.execute(
                text(
                    "UPDATE users SET failed_count = failed_count + 1, updated_at = :now "
                    "WHERE username = :u"
                ),
                {"now": now, "u": username},
            )

    def lock_until(self, username: str, until: str) -> None:
        now = _now_iso()
        with self._session(write=True) as session:
            session.execute(
                text("UPDATE users SET locked_until = :until, updated_at = :now WHERE username = :u"),
                {"until": until, "now": now, "u": username},
            )

    def reset_failed(self, username: str) -> None:
        now = _now_iso()
        with self._session(write=True) as session:
            session.execute(
                text(
                    "UPDATE users SET failed_count = 0, locked_until = NULL, updated_at = :now "
                    "WHERE username = :u"
                ),
                {"now": now, "u": username},
            )

    def exists(self) -> bool:
        with self._session() as session:
            row = session.execute(text("SELECT COUNT(*) FROM users")).fetchone()
        return bool(row and row[0] > 0)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
