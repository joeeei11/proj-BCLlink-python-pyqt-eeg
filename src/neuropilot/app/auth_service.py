from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger
from pydantic import BaseModel

from neuropilot.infra.db.repositories.user_repo import UserRepo


class AuthResult(BaseModel):
    success: bool
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None
    error: Optional[str] = None
    remaining_attempts: Optional[int] = None
    locked_until: Optional[str] = None


class AuthService:
    def __init__(
        self,
        user_repo: UserRepo,
        lock_threshold: int = 5,
        lock_minutes: int = 10,
        bcrypt_rounds: int = 12,
    ) -> None:
        self._repo = user_repo
        self._threshold = lock_threshold
        self._lock_minutes = lock_minutes
        self._rounds = bcrypt_rounds

    def hash_password(self, password: str) -> str:
        from passlib.hash import bcrypt
        return bcrypt.using(rounds=self._rounds).hash(password)

    def update_policy(self, *, lock_threshold: int, lock_minutes: int) -> None:
        self._threshold = lock_threshold
        self._lock_minutes = lock_minutes

    def login(self, username: str, password: str) -> AuthResult:
        from passlib.hash import bcrypt as bcrypt_hasher
        from passlib.exc import PasswordSizeError

        user = self._repo.get_by_username(username)
        if user is None:
            logger.warning("Login failed: unknown user '{}'", username)
            return AuthResult(success=False, error="用户名或密码错误")

        if user.locked_until:
            locked_dt = datetime.fromisoformat(user.locked_until.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if now < locked_dt:
                remaining_s = int((locked_dt - now).total_seconds())
                remaining_m = remaining_s // 60 + 1
                logger.warning("Login blocked: user '{}' is locked for {}m", username, remaining_m)
                return AuthResult(
                    success=False,
                    error=f"账号已锁定，请 {remaining_m} 分钟后重试",
                    locked_until=user.locked_until,
                )
            else:
                self._repo.reset_failed(username)

        pw_hash = self._repo.get_password_hash(username)
        try:
            password_valid = pw_hash is not None and bcrypt_hasher.verify(password, pw_hash)
        except PasswordSizeError:
            logger.warning("Login rejected for '{}': password exceeds maximum allowed size", username)
            return AuthResult(success=False, error="密码过长，请重新输入")

        if not password_valid:
            self._repo.increment_failed(username)
            user = self._repo.get_by_username(username)
            count = user.failed_count if user else self._threshold
            if count >= self._threshold:
                until = (datetime.now(timezone.utc) + timedelta(minutes=self._lock_minutes))
                until_str = until.strftime("%Y-%m-%dT%H:%M:%SZ")
                self._repo.lock_until(username, until_str)
                logger.warning("Account '{}' locked until {}", username, until_str)
                return AuthResult(
                    success=False,
                    error=f"密码错误次数过多，账号已锁定 {self._lock_minutes} 分钟",
                    locked_until=until_str,
                )
            remaining = self._threshold - count
            logger.warning("Login failed for '{}', {} attempts remaining", username, remaining)
            return AuthResult(
                success=False,
                error="用户名或密码错误",
                remaining_attempts=remaining,
            )

        self._repo.reset_failed(username)
        user = self._repo.get_by_username(username)
        assert user is not None
        logger.info("User '{}' logged in successfully", username)
        return AuthResult(
            success=True,
            user_id=user.id,
            username=user.username,
            role=user.role,
        )

    def logout(self, username: str) -> None:
        logger.info("User '{}' logged out", username)
