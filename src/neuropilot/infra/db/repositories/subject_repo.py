from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import text

from neuropilot.infra.db.repositories._base import RepositoryBase, SessionSource


class SubjectDTO(BaseModel):
    id: int
    name: str
    gender: Optional[str]
    age: Optional[int]
    diagnosis: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: str


class SubjectCreateDTO(BaseModel):
    name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None


class SubjectUpdateDTO(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None


class SubjectRepo(RepositoryBase):
    def __init__(self, session: SessionSource) -> None:
        super().__init__(session)

    def list(self, keyword: str = "") -> list[SubjectDTO]:
        with self._session() as session:
            if keyword:
                rows = session.execute(
                    text(
                        "SELECT id, name, gender, age, diagnosis, notes, created_at, updated_at "
                        "FROM subjects WHERE name LIKE :kw ORDER BY name"
                    ),
                    {"kw": f"%{keyword}%"},
                ).fetchall()
            else:
                rows = session.execute(
                    text(
                        "SELECT id, name, gender, age, diagnosis, notes, created_at, updated_at "
                        "FROM subjects ORDER BY name"
                    ),
                ).fetchall()
        return [_row_to_dto(r) for r in rows]

    def get(self, subject_id: int) -> Optional[SubjectDTO]:
        with self._session() as session:
            row = session.execute(
                text(
                    "SELECT id, name, gender, age, diagnosis, notes, created_at, updated_at "
                    "FROM subjects WHERE id = :id"
                ),
                {"id": subject_id},
            ).fetchone()
        return _row_to_dto(row) if row else None

    def create(self, dto: SubjectCreateDTO) -> SubjectDTO:
        now = _now_iso()
        with self._session(write=True) as session:
            result = session.execute(
                text(
                    "INSERT INTO subjects (name, gender, age, diagnosis, notes, created_at, updated_at) "
                    "VALUES (:name, :gender, :age, :diagnosis, :notes, :now, :now)"
                ),
                {
                    "name": dto.name,
                    "gender": dto.gender,
                    "age": dto.age,
                    "diagnosis": dto.diagnosis,
                    "notes": dto.notes,
                    "now": now,
                },
            )
            session.flush()
            subject_id = result.lastrowid
        return self.get(subject_id)  # type: ignore[arg-type,return-value]

    def update(self, subject_id: int, dto: SubjectUpdateDTO) -> Optional[SubjectDTO]:
        updates: dict[str, object] = {}
        for field in ("name", "gender", "age", "diagnosis", "notes"):
            value = getattr(dto, field, None)
            if value is not None:
                updates[field] = value
        if not updates:
            return self.get(subject_id)

        updates["updated_at"] = _now_iso()
        updates["id"] = subject_id
        set_clause = ", ".join(f"{key} = :{key}" for key in updates if key != "id")

        with self._session(write=True) as session:
            session.execute(
                text(f"UPDATE subjects SET {set_clause} WHERE id = :id"),
                updates,
            )
        return self.get(subject_id)

    def delete(self, subject_id: int) -> bool:
        with self._session(write=True) as session:
            result = session.execute(
                text("DELETE FROM subjects WHERE id = :id"),
                {"id": subject_id},
            )
            return result.rowcount > 0  # type: ignore[return-value]


def _row_to_dto(row: object) -> SubjectDTO:
    return SubjectDTO(
        id=row[0],
        name=row[1],
        gender=row[2],
        age=row[3],
        diagnosis=row[4],
        notes=row[5],
        created_at=row[6],
        updated_at=row[7],
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
