from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from neuropilot.app.auth_service import AuthService
from neuropilot.infra.config import load_settings
from neuropilot.infra.db.engine import get_engine, get_session_factory, init_engine
from neuropilot.infra.db.migrations.m0002_sessions_eeg_fields import upgrade as migrate_0002
from neuropilot.infra.db.migrations.m0003_audit_columns import upgrade as migrate_0003
from neuropilot.infra.db.repositories.session_repo import SessionRepo
from neuropilot.infra.db.repositories.subject_repo import SubjectRepo
from neuropilot.infra.db.repositories.trial_repo import TrialRepo
from neuropilot.infra.db.repositories.user_repo import UserRepo
from neuropilot.infra.logger import setup_logger


def run() -> None:
    cfg = load_settings()
    setup_logger(cfg)

    from loguru import logger

    logger.info("NeuroPilot starting. env={}", cfg.env)

    app = QApplication(sys.argv)
    app.setApplicationName("NeuroPilot")
    app.setApplicationVersion("1.0.0")

    from neuropilot.ui.theme import apply_global_qss

    apply_global_qss(app)

    init_engine(cfg.db_path)
    migrate_0002(get_engine())
    migrate_0003(get_engine())

    session_factory = get_session_factory()
    user_repo = UserRepo(session_factory)
    subject_repo = SubjectRepo(session_factory)
    session_repo = SessionRepo(session_factory)
    trial_repo = TrialRepo(session_factory)
    auth_svc = AuthService(
        user_repo,
        lock_threshold=cfg.lock_threshold,
        lock_minutes=cfg.lock_minutes,
    )

    from neuropilot.ui.main_window import show_login_and_run

    show_login_and_run(
        auth_svc,
        subject_repo,
        session_repo=session_repo,
        trial_repo=trial_repo,
        cfg=cfg,
        session_factory=session_factory,
    )

    sys.exit(app.exec_())
