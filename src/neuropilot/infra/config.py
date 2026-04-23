from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]


def _load_toml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("rb") as f:
        return tomllib.load(f)


def _flatten_toml(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in data.items():
        key = f"{prefix}{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten_toml(v, f"{key}_"))
        else:
            result[key] = v
    return result



class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NEUROPILOT_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    env: str = "dev"
    theme: str = "light"
    db_path: str = "data/neuropilot_app.db"
    data_dir: str = "data"
    log_level: str = "INFO"
    log_file: str = "data/logs/neuropilot.log"
    log_rotation: str = "10 MB"
    log_retention: str = "14 days"
    admin_initial_password: str = ""

    lock_threshold: int = 5
    lock_minutes: int = 10

    eeg_channels: int = 8
    eeg_sample_rate: int = 250
    eeg_transport: str = "demo"
    eeg_serial_port: str = "COM3"
    eeg_serial_baud: int = 115200
    eeg_bluetooth_address: str = ""
    eeg_bluetooth_port: int = 1
    eeg_tcp_host: str = "192.168.1.100"
    eeg_tcp_port: int = 4000
    eeg_udp_host: str = "0.0.0.0"
    eeg_udp_port: int = 4001
    eeg_lsl_stream_name: str = "NeuroPilot"
    eeg_playback_file: str = ""

    device_transport: str = "serial"
    device_serial_port: str = "COM4"
    device_serial_baud: int = 9600
    device_bluetooth_address: str = ""
    device_bluetooth_port: int = 1
    device_tcp_host: str = "192.168.1.100"
    device_tcp_port: int = 5000
    device_udp_host: str = "192.168.1.100"
    device_udp_port: int = 5001

    paradigm_fix_duration_ms: int = 1000
    paradigm_cue_duration_ms: int = 500
    paradigm_imagery_duration_ms: int = 4000
    paradigm_rest_duration_ms: int = 2000
    paradigm_iti_duration_ms: int = 1000
    paradigm_trials_per_run: int = 20

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"dev", "prod", "test"}
        if v not in allowed:
            raise ValueError(f"env must be one of {allowed}")
        return v

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        allowed = {"light", "dark"}
        if v not in allowed:
            raise ValueError(f"theme must be one of {allowed}")
        return v

def load_settings(
    default_toml: str | Path = "config/default.toml",
    local_toml: str | Path = "config/local.toml",
) -> AppSettings:
    defaults = _flatten_toml(_load_toml(default_toml))
    overrides = _flatten_toml(_load_toml(local_toml))
    merged = {**defaults, **overrides}

    env_override_path = os.environ.get("NEUROPILOT_CONFIG")
    if env_override_path:
        merged.update(_flatten_toml(_load_toml(env_override_path)))

    # 环境变量优先级高于 TOML：只在未被 env var 覆盖时使用 TOML 值
    prefix = "NEUROPILOT_"
    env_keys = {k[len(prefix):].lower() for k in os.environ if k.upper().startswith(prefix)}
    final: dict[str, Any] = {k: v for k, v in merged.items() if k not in env_keys}

    return AppSettings(**final)


_EDITABLE_SCALARS = (
    "lock_threshold",
    "lock_minutes",
)

_EDITABLE_SECTIONS: dict[str, tuple[str, ...]] = {
    "eeg": (
        "channels",
        "sample_rate",
        "transport",
        "serial_port",
        "serial_baud",
        "bluetooth_address",
        "bluetooth_port",
        "tcp_host",
        "tcp_port",
        "udp_host",
        "udp_port",
        "lsl_stream_name",
        "playback_file",
    ),
    "device": (
        "transport",
        "serial_port",
        "serial_baud",
        "bluetooth_address",
        "bluetooth_port",
        "tcp_host",
        "tcp_port",
        "udp_host",
        "udp_port",
    ),
    "paradigm": (
        "fix_duration_ms",
        "cue_duration_ms",
        "imagery_duration_ms",
        "rest_duration_ms",
        "iti_duration_ms",
        "trials_per_run",
    ),
}


def editable_settings_payload(settings: AppSettings) -> dict[str, Any]:
    payload: dict[str, Any] = {
        key: getattr(settings, key)
        for key in _EDITABLE_SCALARS
    }
    for section, keys in _EDITABLE_SECTIONS.items():
        payload[section] = {
            key: getattr(settings, f"{section}_{key}")
            for key in keys
        }
    return payload


def save_local_settings(
    settings: AppSettings,
    local_toml: str | Path = "config/local.toml",
) -> Path:
    path = Path(local_toml)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_toml(editable_settings_payload(settings)), encoding="utf-8")
    return path


def _dump_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []

    for key, value in data.items():
        if isinstance(value, dict):
            continue
        lines.append(f"{key} = {_format_toml_value(value)}")

    if lines:
        lines.append("")

    for section, values in data.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"[{section}]")
        for key, value in values.items():
            lines.append(f"{key} = {_format_toml_value(value)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
