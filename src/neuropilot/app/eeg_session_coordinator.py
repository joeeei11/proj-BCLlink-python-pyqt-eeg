from __future__ import annotations

from typing import Optional

from neuropilot.infra.db.repositories.session_repo import SessionRepo


class EEGSessionCoordinator:
    """EEG session 数据库记录的生命周期管理（无 Qt 依赖）.

    参考 neurodecode 协议层/录制层分离原则：
    session 状态变更只在此类中发生，与采集线程和录制器解耦。
    """

    def __init__(self, session_repo: SessionRepo) -> None:
        self._repo = session_repo
        self._session_id: Optional[int] = None

    @property
    def session_id(self) -> Optional[int]:
        return self._session_id

    def create(
        self,
        subject_id: int,
        user_id: int,
        transport: str,
        n_channels: int,
        srate: float,
    ) -> int:
        """创建 session 记录并返回 session_id。"""
        self._session_id = self._repo.create(
            subject_id=subject_id,
            user_id=user_id,
            transport=transport,
            n_channels=n_channels,
            srate=srate,
        )
        return self._session_id

    def stop(self) -> None:
        """将当前 session 标记为已停止。"""
        if self._session_id is not None:
            try:
                self._repo.set_stopped(self._session_id)
            except Exception:
                from loguru import logger
                logger.warning(
                    "EEGSessionCoordinator: 无法标记 session 为已停止 id={}",
                    self._session_id,
                )
            finally:
                self._session_id = None
