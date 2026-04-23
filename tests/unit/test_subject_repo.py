"""SubjectRepo 集成测试（内存 SQLite）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from neuropilot.infra.db.engine import _apply_schema
from neuropilot.infra.db.repositories.subject_repo import SubjectCreateDTO, SubjectRepo, SubjectUpdateDTO


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    _apply_schema(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_create_and_list(session):
    repo = SubjectRepo(session)
    dto = SubjectCreateDTO(name="Alice", gender="F", age=30, diagnosis="stroke")
    created = repo.create(dto)
    assert created.id > 0
    subjects = repo.list()
    assert len(subjects) == 1
    assert subjects[0].name == "Alice"


def test_get(session):
    repo = SubjectRepo(session)
    dto = SubjectCreateDTO(name="Bob")
    created = repo.create(dto)
    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.name == "Bob"


def test_update(session):
    repo = SubjectRepo(session)
    created = repo.create(SubjectCreateDTO(name="Carol"))
    updated = repo.update(created.id, SubjectUpdateDTO(age=25, diagnosis="TBI"))
    assert updated is not None
    assert updated.age == 25
    assert updated.diagnosis == "TBI"
    assert updated.name == "Carol"


def test_delete(session):
    repo = SubjectRepo(session)
    created = repo.create(SubjectCreateDTO(name="Dave"))
    assert repo.delete(created.id)
    assert repo.get(created.id) is None


def test_search(session):
    repo = SubjectRepo(session)
    repo.create(SubjectCreateDTO(name="Alice"))
    repo.create(SubjectCreateDTO(name="Bob"))
    results = repo.list(keyword="Ali")
    assert len(results) == 1
    assert results[0].name == "Alice"
