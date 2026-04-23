"""Migration 0002: add transport/n_channels/srate to sessions table."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def upgrade(engine: Engine) -> None:
    """Idempotent: adds columns only if they do not already exist."""
    with engine.connect() as conn:
        existing = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(sessions)")).fetchall()
        }
        for col, definition in [
            ("transport", "TEXT"),
            ("n_channels", "INTEGER"),
            ("srate", "REAL"),
        ]:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE sessions ADD COLUMN {col} {definition}"))
        conn.commit()
