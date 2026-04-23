from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

SessionSource = Session | Callable[[], Session]


class RepositoryBase:
    def __init__(self, session_source: SessionSource) -> None:
        self._session_source = session_source

    @contextmanager
    def _session(self, *, write: bool = False) -> Iterator[Session]:
        if isinstance(self._session_source, Session):
            yield self._session_source
            if write:
                self._session_source.flush()
            return

        session = self._session_source()
        try:
            yield session
            if write:
                session.commit()
        except Exception:
            if write:
                session.rollback()
            raise
        finally:
            session.close()
