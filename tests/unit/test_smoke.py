"""基础冒烟测试：验证包可导入且配置/日志系统正常初始化。"""
from __future__ import annotations

import os
from pathlib import Path


def test_import_neuropilot() -> None:
    import neuropilot  # noqa: F401


def test_load_settings() -> None:
    os.environ.setdefault("NEUROPILOT_ENV", "test")
    from neuropilot.infra.config import load_settings

    cfg = load_settings(
        default_toml="config/default.toml",
        local_toml="config/local.toml",
    )
    assert cfg.env in {"dev", "prod", "test"}
    assert cfg.eeg_channels > 0
    assert isinstance(cfg.eeg_playback_file, str)
    assert cfg.lock_threshold > 0


def test_setup_logger(tmp_path: Path) -> None:
    import neuropilot.infra.logger as logger_mod

    log_file = str(tmp_path / "test.log")

    from neuropilot.infra.config import AppSettings

    cfg = AppSettings(log_file=log_file, log_level="DEBUG", env="test")
    logger_mod._initialized = False
    logger_mod.setup_logger(cfg)
    assert (tmp_path / "test.log").exists()
