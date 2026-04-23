"""Unit tests for DeviceCommand enum."""
from neuropilot.domain.device.commands import DeviceCommand


def test_left_bytes() -> None:
    assert DeviceCommand.LEFT.to_bytes() == b"L\n"


def test_right_bytes() -> None:
    assert DeviceCommand.RIGHT.to_bytes() == b"R\n"


def test_trigger_start_bytes() -> None:
    assert DeviceCommand.TRIGGER_START.to_bytes() == b"TS\n"


def test_trigger_end_bytes() -> None:
    assert DeviceCommand.TRIGGER_END.to_bytes() == b"TE\n"


def test_reset_bytes() -> None:
    assert DeviceCommand.RESET.to_bytes() == b"RST\n"


def test_custom_passthrough() -> None:
    payload = b"HELLO\r\n"
    assert DeviceCommand.custom(payload) == payload


def test_all_commands_have_bytes() -> None:
    for cmd in DeviceCommand:
        result = cmd.to_bytes()
        assert isinstance(result, bytes)
        assert len(result) > 0
