from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from neuropilot.infra.config import AppSettings

_initialized = False


def setup_logger(cfg: "AppSettings") -> None:
    global _initialized
    if _initialized:
        return

    logger.remove()

    logger.add(
        sys.stdout,
        level=cfg.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    log_path = Path(cfg.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_path),
        level=cfg.log_level,
        rotation=cfg.log_rotation,
        retention=cfg.log_retention,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{line} - {message}",
    )

    _initialized = True
    logger.info("Logger initialized. level={} file={}", cfg.log_level, cfg.log_file)
