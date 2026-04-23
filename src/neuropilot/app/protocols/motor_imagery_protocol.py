from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import QObject, pyqtSignal

from neuropilot.app.event_bus import EventBus
from neuropilot.app.paradigm_engine import ParadigmEngine

if TYPE_CHECKING:
    from neuropilot.app.predictor import Predictor
    from neuropilot.app.trial_recorder import TrialRecorder


class MotorImageryProtocol(QObject):
    """运动想象实验协议层（参考 EEG-ExPy BaseExperiment 设计）.

    职责：
    - 封装 ParadigmEngine 的配置和生命周期
    - 协调 TrialRecorder 的打开/关闭
    - 协调 Predictor 的投票开始/结束
    - 从 EventBus 订阅采集信号、向 EventBus 发布结果

    与 EEG-ExPy Experiment.run() 的对应关系：
    - setup()     → configure() + _bind_internal()
    - run()       → start()
    - stop()      → abort()
    - open_trial  → _on_trial_opened()
    - close_trial → _on_trial_closed()
    """

    sig_protocol_started = pyqtSignal()
    sig_protocol_stopped = pyqtSignal()

    def __init__(
        self,
        trial_recorder: "TrialRecorder",
        predictor: "Predictor",
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._recorder = trial_recorder
        self._predictor = predictor
        self._engine = ParadigmEngine(parent=self)
        self._current_session_id: Optional[int] = None
        self._current_trial_uuid: Optional[str] = None
        self._bind_internal()
        self._bind_bus()

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    @property
    def engine(self) -> ParadigmEngine:
        return self._engine

    def set_session_id(self, session_id: Optional[int]) -> None:
        self._current_session_id = session_id

    def configure(self, config: dict) -> None:
        """按 config dict 配置范式参数（来自 TaskPage UI）。"""
        self._engine.configure(
            total_trials=int(config.get("total_trials", 20)),
            t_fix_ms=int(config.get("t_fix_ms", 500)),
            t_cue_ms=int(config.get("t_cue_ms", 1000)),
            t_imag_ms=int(config.get("t_imag_ms", 4000)),
            t_rest_ms=int(config.get("t_rest_ms", 2000)),
            t_iti_ms=int(config.get("t_iti_ms", 1000)),
        )

    def start(self) -> None:
        self._engine.start()
        self.sig_protocol_started.emit()

    def abort(self) -> None:
        self._engine.abort()
        self.sig_protocol_stopped.emit()

    # ------------------------------------------------------------------
    # 内部信号绑定
    # ------------------------------------------------------------------

    def _bind_internal(self) -> None:
        """绑定引擎内部信号 → 协议动作。"""
        self._engine.sig_trial_opened.connect(self._on_trial_opened)
        self._engine.sig_trial_closed.connect(self._on_trial_closed)

    @property
    def session_id(self) -> Optional[int]:
        return self._current_session_id

    def _bind_bus(self) -> None:
        """绑定 EventBus 信号 → 协议响应。"""
        bus = EventBus.instance()
        bus.prediction_result.connect(self._on_prediction_result)
        # Predictor 已在自身 __init__ 中订阅 eeg_samples，无需重复连接

    # ------------------------------------------------------------------
    # 内部处理
    # ------------------------------------------------------------------

    def _on_trial_opened(self, trial_uuid: str, intent: str) -> None:
        if self._current_session_id is None:
            return
        self._current_trial_uuid = trial_uuid
        self._recorder.open(trial_uuid, intent, self._current_session_id)
        self._predictor.begin_voting(trial_uuid)

    def _on_trial_closed(self, trial_uuid: str) -> None:
        self._predictor.end_voting(trial_uuid)
        self._recorder.close(trial_uuid)
        if self._current_trial_uuid == trial_uuid:
            self._current_trial_uuid = None

    def _on_prediction_result(self, label: str, confidence: float) -> None:
        if self._current_trial_uuid is not None:
            self._recorder.record_prediction(self._current_trial_uuid, label, confidence)
