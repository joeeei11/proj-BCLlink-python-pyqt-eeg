"""LoginDialog UI 测试：失败 5 次后按钮置灰。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from neuropilot.app.auth_service import AuthResult, AuthService


@pytest.fixture()
def mock_auth_locked():
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    svc = MagicMock(spec=AuthService)
    svc.login.return_value = AuthResult(
        success=False,
        error="密码错误次数过多，账号已锁定 10 分钟",
        locked_until=future,
    )
    return svc, future


@pytest.fixture()
def mock_auth_fail():
    svc = MagicMock(spec=AuthService)
    svc.login.return_value = AuthResult(
        success=False,
        error="用户名或密码错误",
        remaining_attempts=3,
    )
    return svc


@pytest.mark.qt
def test_login_btn_disabled_on_lock(qtbot, mock_auth_locked):
    from neuropilot.ui.login_dialog import LoginDialog

    svc, future = mock_auth_locked
    dlg = LoginDialog(svc)
    qtbot.addWidget(dlg)

    dlg._username_edit.setText("admin")
    dlg._password_edit.setText("wrongpassword")
    qtbot.mouseClick(dlg._login_btn, 1)  # Qt.LeftButton = 1

    assert not dlg._login_btn.isEnabled()
    assert "锁定" in dlg._hint_label.text()


@pytest.mark.qt
def test_hint_shows_remaining_attempts(qtbot, mock_auth_fail):
    from neuropilot.ui.login_dialog import LoginDialog

    dlg = LoginDialog(mock_auth_fail)
    qtbot.addWidget(dlg)

    dlg._username_edit.setText("admin")
    dlg._password_edit.setText("wrong")
    qtbot.mouseClick(dlg._login_btn, 1)

    assert "3" in dlg._hint_label.text()
