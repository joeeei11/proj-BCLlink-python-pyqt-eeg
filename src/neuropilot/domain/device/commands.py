from __future__ import annotations

from enum import Enum


class DeviceCommand(Enum):
    """Standard device command set.

    ``to_bytes()`` returns the wire payload.  UI code must not hard-code
    byte literals like b'L\\n' — use this enum exclusively.
    """

    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TRIGGER_START = "TRIGGER_START"
    TRIGGER_END = "TRIGGER_END"
    RESET = "RESET"

    def to_bytes(self) -> bytes:
        _MAP = {
            DeviceCommand.LEFT: b"L\n",
            DeviceCommand.RIGHT: b"R\n",
            DeviceCommand.TRIGGER_START: b"TS\n",
            DeviceCommand.TRIGGER_END: b"TE\n",
            DeviceCommand.RESET: b"RST\n",
        }
        return _MAP[self]

    @staticmethod
    def custom(payload: bytes) -> bytes:
        """Pass-through for arbitrary payloads from the debug page."""
        return payload
