"""Migration 0003: repair columns lost to early schema/comment corruption."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def upgrade(engine: Engine) -> None:
    with engine.connect() as conn:
        users_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()
        }
        if users_cols and "created_at" not in users_cols:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN created_at TEXT "
                    "NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"
                )
            )

        trials_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(trials)")).fetchall()
        }
        if trials_cols and "created_at" not in trials_cols:
            conn.execute(
                text(
                    "ALTER TABLE trials ADD COLUMN created_at TEXT "
                    "NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"
                )
            )

        conn.commit()
