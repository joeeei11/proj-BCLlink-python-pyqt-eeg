from __future__ import annotations

import time
from threading import Event


class ConnectCancelledError(RuntimeError):
    """Raised when the user cancels an in-flight transport connection."""


def open_transport_with_cancel(
    transport: object,
    cancel_event: Event,
    *,
    total_timeout: float = 5.0,
    slice_timeout: float = 0.5,
) -> None:
    deadline = time.monotonic() + total_timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        if cancel_event.is_set():
            _safe_close(transport)
            raise ConnectCancelledError("Connection cancelled")

        remaining = max(0.0, deadline - time.monotonic())
        timeout = min(slice_timeout, remaining)
        if timeout <= 0:
            break

        try:
            transport.open(timeout=timeout)  # type: ignore[attr-defined]
            if cancel_event.is_set():
                _safe_close(transport)
                raise ConnectCancelledError("Connection cancelled")
            return
        except Exception as exc:
            last_error = exc
            if cancel_event.is_set():
                _safe_close(transport)
                raise ConnectCancelledError("Connection cancelled") from exc
            if not _is_retryable_connect_error(exc):
                raise
            _safe_close(transport)

    if cancel_event.is_set():
        _safe_close(transport)
        raise ConnectCancelledError("Connection cancelled")
    if last_error is not None:
        raise last_error
    raise TimeoutError("Connection attempt timed out")


def _is_retryable_connect_error(exc: Exception) -> bool:
    message = str(exc).lower()
    retry_markers = (
        "timed out",
        "timeout",
        "no lsl stream found",
        "temporarily unavailable",
    )
    return any(marker in message for marker in retry_markers)


def _safe_close(transport: object) -> None:
    close = getattr(transport, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception:
        pass
