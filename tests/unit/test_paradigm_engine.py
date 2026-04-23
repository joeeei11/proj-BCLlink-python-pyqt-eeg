"""Unit tests for ParadigmEngine FSM."""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QApplication
import sys

_app = QApplication.instance() or QApplication(sys.argv)

from neuropilot.app.paradigm_engine import ParadigmEngine, ParadigmState


def _collect_states(engine: ParadigmEngine, max_ms: int = 5000) -> list[str]:
    """Run the Qt event loop until IDLE is reached or timeout."""
    from PyQt5.QtCore import QEventLoop, QTimer
    states: list[str] = []

    def on_state(s: str, _i: int, _t: int) -> None:
        states.append(s)

    engine.sig_state_changed.connect(on_state)

    loop = QEventLoop()
    engine.sig_state_changed.connect(
        lambda s, i, t: loop.quit() if s == "IDLE" else None
    )

    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(loop.quit)
    guard.start(max_ms)

    loop.exec_()
    guard.stop()
    return states


def test_initial_state_is_idle() -> None:
    eng = ParadigmEngine()
    assert eng.state == ParadigmState.IDLE


def test_start_transitions_through_states() -> None:
    eng = ParadigmEngine()
    eng.configure(total_trials=2, t_fix_ms=10, t_cue_ms=10,
                  t_imag_ms=10, t_rest_ms=10, t_iti_ms=10)
    eng.start()
    states = _collect_states(eng, max_ms=3000)
    assert "FIX" in states
    assert "CUE" in states
    assert "IMAG" in states
    assert "REST" in states
    assert states[-1] == "IDLE"  # ends back at IDLE after DONE


def test_abort_returns_to_idle_immediately() -> None:
    from PyQt5.QtCore import QEventLoop, QTimer
    eng = ParadigmEngine()
    eng.configure(total_trials=10, t_fix_ms=500, t_cue_ms=500,
                  t_imag_ms=2000, t_rest_ms=500, t_iti_ms=500)
    eng.start()

    # Let one state pass then abort
    loop = QEventLoop()
    QTimer.singleShot(50, loop.quit)
    loop.exec_()

    states_after: list[str] = []
    eng.sig_state_changed.connect(lambda s, _i, _t: states_after.append(s))
    eng.abort()

    # After abort, no more transitions should arrive
    QTimer.singleShot(100, loop.quit)
    loop.exec_()

    assert "IDLE" in states_after
    # Only IDLE should appear, not more paradigm states
    non_idle = [s for s in states_after if s != "IDLE"]
    assert non_idle == [], f"Unexpected states after abort: {non_idle}"


def test_trial_count_matches_config() -> None:
    eng = ParadigmEngine()
    n = 4
    eng.configure(total_trials=n, t_fix_ms=5, t_cue_ms=5,
                  t_imag_ms=5, t_rest_ms=5, t_iti_ms=5)
    opened: list[str] = []
    closed: list[str] = []
    eng.sig_trial_opened.connect(lambda u, _i: opened.append(u))
    eng.sig_trial_closed.connect(closed.append)

    eng.start()
    _collect_states(eng, max_ms=3000)

    assert len(opened) == n
    assert len(closed) == n
    assert set(opened) == set(closed)
