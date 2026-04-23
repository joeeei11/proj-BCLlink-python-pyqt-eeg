#!/usr/bin/env python
"""首次启动时创建 admin 账号。

用法：
    NEUROPILOT_ADMIN_INITIAL_PASSWORD='ChangeMe!' python scripts/seed_admin.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from neuropilot.infra.config import load_settings
from neuropilot.infra.db.engine import init_engine, get_session
from neuropilot.infra.db.repositories.user_repo import UserRepo
from neuropilot.app.auth_service import AuthService


def main() -> None:
    cfg = load_settings()
    init_engine(cfg.db_path)

    password = cfg.admin_initial_password
    if not password:
        print("错误：请设置环境变量 NEUROPILOT_ADMIN_INITIAL_PASSWORD", file=sys.stderr)
        sys.exit(1)

    for session in get_session():
        repo = UserRepo(session)
        if repo.exists():
            print("users 表已有数据，跳过 seed。")
            return
        svc = AuthService(repo, bcrypt_rounds=12)
        pw_hash = svc.hash_password(password)
        uid = repo.create("admin", pw_hash, role="admin")
        print(f"admin 账号已创建，id={uid}")


if __name__ == "__main__":
    main()
