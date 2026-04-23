from __future__ import annotations

import uuid
from enum import Enum, auto
from typing import Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from neuropilot.app.event_bus import EventBus


class ParadigmState(str, Enum):
    IDLE = "IDLE"
    FIX = "FIX"       # 注视十字
    CUE = "CUE"       # 线索呈现（左/右）
    IMAG = "IMAG"     # 运动想象
    REST = "REST"     # 休息 / 结果反馈
    ITI = "ITI"       # 试次间隔
    DONE = "DONE"     # 全部循环结束


_INTENTS = ("left", "right")


class ParadigmEngine(QObject):
    """Explicit FSM for the motor-imagery paradigm.

    One QTimer drives all state transitions.  Calling ``abort()`` cancels
    any pending transition and immediately returns to IDLE — the expired
    timer callback is guarded by a generation counter so it becomes a no-op.

    Signals
    -------
    sig_state_changed(state: str, trial_index: int, total: int)
    sig_trial_opened(uuid: str, intent: str)
    sig_trial_closed(uuid: str)
    """

    sig_state_changed = pyqtSignal(str, int, int)
    sig_trial_opened = pyqtSignal(str, str)
    sig_trial_closed = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state = ParadigmState.IDLE
        self._trial_index = 0
        self._total_trials = 0
        self._current_uuid: Optional[str] = None
        self._current_intent: Optional[str] = None
        self._generation = 0          # increment on abort to invalidate pending callbacks
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        # Paradigm timing (ms)
        self._t_fix = 500
        self._t_cue = 1000
        self._t_imag = 4000
        self._t_rest = 2000
        self._t_iti = 1000

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> ParadigmState:
        return self._state

    def configure(
        self,
        total_trials: int = 20,
        t_fix_ms: int = 500,
        t_cue_ms: int = 1000,
        t_imag_ms: int = 4000,
        t_rest_ms: int = 2000,
        t_iti_ms: int = 1000,
    ) -> None:
        if self._state != ParadigmState.IDLE:
            raise RuntimeError("Cannot configure while running.")
        self._total_trials = total_trials
        self._t_fix = t_fix_ms
        self._t_cue = t_cue_ms
        self._t_imag = t_imag_ms
        self._t_rest = t_rest_ms
        self._t_iti = t_iti_ms

    def start(self) -> None:
        if self._state != ParadigmState.IDLE:
            return
        self._trial_index = 0
        self._advance(ParadigmState.FIX)

    def abort(self) -> None:
        self._generation += 1
        self._timer.stop()
        if self._current_uuid is not None:
            self.sig_trial_closed.emit(self._current_uuid)
            EventBus.instance().paradigm_trial_closed.emit(self._current_uuid)
            self._current_uuid = None
        self._to_idle()

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _advance(self, next_state: ParadigmState, delay_ms: int = 0) -> None:
        gen = self._generation

        def _go() -> None:
            if self._generation != gen:
                return
            self._enter(next_state)

        if delay_ms > 0:
            QTimer.singleShot(delay_ms, _go)
        else:
            _go()

    def _enter(self, state: ParadigmState) -> None:
        self._state = state
        self.sig_state_changed.emit(state.value, self._trial_index, self._total_trials)
        EventBus.instance().paradigm_state_changed.emit(
            state.value, self._trial_index, self._total_trials
        )

        if state == ParadigmState.FIX:
            self._advance(ParadigmState.CUE, self._t_fix)

        elif state == ParadigmState.CUE:
            self._current_intent = _INTENTS[self._trial_index % 2]
            self._current_uuid = str(uuid.uuid4())
            self.sig_trial_opened.emit(self._current_uuid, self._current_intent)
            EventBus.instance().paradigm_trial_opened.emit(
                self._current_uuid, self._current_intent
            )
            self._advance(ParadigmState.IMAG, self._t_cue)

        elif state == ParadigmState.IMAG:
            self._advance(ParadigmState.REST, self._t_imag)

        elif state == ParadigmState.REST:
            if self._current_uuid is not None:
                self.sig_trial_closed.emit(self._current_uuid)
                EventBus.instance().paradigm_trial_closed.emit(self._current_uuid)
                self._current_uuid = None
            self._advance(ParadigmState.ITI, self._t_rest)

        elif state == ParadigmState.ITI:
            self._trial_index += 1
            if self._trial_index >= self._total_trials:
                self._advance(ParadigmState.DONE, self._t_iti)
            else:
                self._advance(ParadigmState.FIX, self._t_iti)

        elif state == ParadigmState.DONE:
            self._to_idle()

    def _to_idle(self) -> None:
        self._state = ParadigmState.IDLE
        self.sig_state_changed.emit(ParadigmState.IDLE.value, self._trial_index, self._total_trials)
        EventBus.instance().paradigm_state_changed.emit(
            ParadigmState.IDLE.value, self._trial_index, self._total_trials
        )
