from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from sqlalchemy import text

from neuropilot.infra.db.repositories._base import RepositoryBase, SessionSource


class ModelDTO(BaseModel):
    id: int
    subject_id: Optional[int]
    name: str
    algorithm: str
    file_path: str
    sha256: str
    accuracy: Optional[float]
    is_active: int
    trained_at: str
    created_at: str


class ModelRepo(RepositoryBase):
    def __init__(self, session: SessionSource) -> None:
        super().__init__(session)

    def create(
        self,
        subject_id: int,
        name: str,
        algorithm: str,
        file_path: str,
        sha256: str,
        accuracy: Optional[float] = None,
    ) -> int:
        with self._session(write=True) as session:
            result = session.execute(
                text(
                    "INSERT INTO models (subject_id, name, algorithm, file_path, sha256, accuracy) "
                    "VALUES (:sid, :name, :algo, :fp, :sha, :acc)"
                ),
                {
                    "sid": subject_id,
                    "name": name,
                    "algo": algorithm,
                    "fp": file_path,
                    "sha": sha256,
                    "acc": accuracy,
                },
            )
            session.flush()
            return result.lastrowid  # type: ignore[return-value]

    def get(self, model_id: int) -> Optional[ModelDTO]:
        with self._session() as session:
            row = session.execute(
                text(
                    "SELECT id, subject_id, name, algorithm, file_path, sha256, "
                    "accuracy, is_active, trained_at, created_at "
                    "FROM models WHERE id = :id"
                ),
                {"id": model_id},
            ).fetchone()
        return _row_to_dto(row) if row else None

    def list_by_subject(self, subject_id: int) -> list[ModelDTO]:
        with self._session() as session:
            rows = session.execute(
                text(
                    "SELECT id, subject_id, name, algorithm, file_path, sha256, "
                    "accuracy, is_active, trained_at, created_at "
                    "FROM models WHERE subject_id = :sid ORDER BY trained_at DESC"
                ),
                {"sid": subject_id},
            ).fetchall()
        return [_row_to_dto(r) for r in rows]

    def set_active(self, model_id: int) -> None:
        with self._session(write=True) as session:
            session.execute(text("UPDATE models SET is_active = 0"))
            session.execute(
                text("UPDATE models SET is_active = 1 WHERE id = :id"),
                {"id": model_id},
            )


def _row_to_dto(row: object) -> ModelDTO:
    return ModelDTO(
        id=row[0],
        subject_id=row[1],
        name=row[2],
        algorithm=row[3],
        file_path=row[4],
        sha256=row[5],
        accuracy=row[6],
        is_active=row[7],
        trained_at=row[8],
        created_at=row[9],
    )
