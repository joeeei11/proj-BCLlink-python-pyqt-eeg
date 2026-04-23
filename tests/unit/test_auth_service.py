"""AuthService 单元测试：正确密码、错误密码、锁定、重置。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from neuropilot.app.auth_service import AuthService
from neuropilot.infra.db.repositories.user_repo import UserDTO


def _make_repo(
    password_hash: str | None = None,
    failed_count: int = 0,
    locked_until: str | None = None,
) -> MagicMock:
    repo = MagicMock()
    repo.get_password_hash.return_value = password_hash

    user = UserDTO(
        id=1,
        username="testuser",
        role="researcher",
        failed_count=failed_count,
        locked_until=locked_until,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    repo.get_by_username.return_value = user
    return repo


@pytest.fixture()
def svc_factory():
    def _make(password: str = "secret", failed_count: int = 0, locked_until: str | None = None):
        from passlib.hash import bcrypt
        pw_hash = bcrypt.using(rounds=4).hash(password)
        repo = _make_repo(pw_hash, failed_count, locked_until)
        svc = AuthService(repo, lock_threshold=5, lock_minutes=10, bcrypt_rounds=4)
        return svc, repo
    return _make


def test_correct_password(svc_factory):
    svc, repo = svc_factory("secret")
    result = svc.login("testuser", "secret")
    assert result.success
    assert result.username == "testuser"
    repo.reset_failed.assert_called_once_with("testuser")


def test_wrong_password(svc_factory):
    svc, repo = svc_factory("secret", failed_count=0)
    # 模拟 increment 后 failed_count=1
    from neuropilot.infra.db.repositories.user_repo import UserDTO
    updated = UserDTO(
        id=1, username="testuser", role="researcher", failed_count=1,
        locked_until=None, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    repo.get_by_username.side_effect = [updated, updated]
    result = svc.login("testuser", "wrong")
    assert not result.success
    assert result.remaining_attempts == 4
    repo.increment_failed.assert_called_once()


def test_lockout_triggered(svc_factory):
    svc, repo = svc_factory("secret", failed_count=4)
    from neuropilot.infra.db.repositories.user_repo import UserDTO
    after_inc = UserDTO(
        id=1, username="testuser", role="researcher", failed_count=5,
        locked_until=None, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    repo.get_by_username.side_effect = [after_inc, after_inc]
    result = svc.login("testuser", "wrong")
    assert not result.success
    assert result.locked_until is not None
    repo.lock_until.assert_called_once()


def test_already_locked(svc_factory):
    from datetime import datetime, timedelta, timezone
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    svc, repo = svc_factory("secret", failed_count=5, locked_until=future)
    result = svc.login("testuser", "secret")
    assert not result.success
    assert result.locked_until == future


def test_lock_expired_resets(svc_factory):
    from datetime import datetime, timedelta, timezone
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    svc, repo = svc_factory("secret", failed_count=5, locked_until=past)
    result = svc.login("testuser", "secret")
    assert result.success
    repo.reset_failed.assert_called()
