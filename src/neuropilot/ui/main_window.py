from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QThreadPool, QTimer
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import FluentWindow, InfoBar, InfoBarPosition, NavigationItemPosition

from neuropilot.app.auth_service import AuthResult, AuthService
from neuropilot.app.connection_config import EEGConnectionConfig
from neuropilot.app.eeg_record_service import EEGRecordService
from neuropilot.app.eeg_session_coordinator import EEGSessionCoordinator
from neuropilot.app.event_bus import EventBus
from neuropilot.app.ml_jobs import TrainJob
from neuropilot.app.predictor import Predictor
from neuropilot.app.protocols.motor_imagery_protocol import MotorImageryProtocol
from neuropilot.app.session_manager import SessionManager
from neuropilot.app.training_dataset import build_subject_dataset
from neuropilot.app.trial_recorder import TrialRecorder
from neuropilot.domain.ml.model_store import ModelStore, ModelRecord
from neuropilot.infra.db.repositories.session_repo import SessionRepo
from neuropilot.infra.db.repositories.subject_repo import SubjectRepo
from neuropilot.infra.db.repositories.trial_repo import TrialRepo
from neuropilot.ui.pages.subjects_page import SubjectsPage


class MainWindow(FluentWindow):
    """主窗口 — 装配器角色.

    职责：
    - 创建并注入各服务（session_manager、trial_recorder、predictor、protocol）
    - 组装导航页面
    - 监听 EventBus 并转发到对应服务，不直接处理业务逻辑
    """

    def __init__(
        self,
        auth_service: AuthService,
        subject_repo: SubjectRepo,
        session_repo: SessionRepo,
        trial_repo: TrialRepo,
        cfg: object,
        session_factory: object,
    ) -> None:
        super().__init__()
        self._auth_svc = auth_service
        self._subject_repo = subject_repo
        self._session_repo = session_repo
        self._trial_repo = trial_repo
        self._cfg = cfg
        self._session_factory = session_factory
        self._current_user: Optional[AuthResult] = None
        self._selected_subject_id = 0
        self._worker: object = None
        self._disconnecting_worker: object = None
        self._ml_job: Optional[TrainJob] = None
        self._current_model_record: Optional[ModelRecord] = None
        self._disconnect_timer = QTimer(self)
        self._disconnect_timer.setSingleShot(True)
        self._disconnect_timer.setInterval(2000)
        self._disconnect_timer.timeout.connect(self._on_disconnect_timeout)

        # ── 服务层初始化 ──────────────────────────────────────────
        self._session_manager = SessionManager(parent=self)
        self._trial_recorder = TrialRecorder(self._trial_repo)
        self._predictor = Predictor(
            parent=self,
            srate=float(getattr(cfg, "eeg_sample_rate", 250)),
            n_channels=int(getattr(cfg, "eeg_channels", 8)),
        )
        self._model_store = ModelStore(
            session=self._session_factory,
            models_dir=Path(cfg.data_dir) / "models",
        )
        # 运动想象协议层（参考 EEG-ExPy BaseExperiment）
        self._mi_protocol = MotorImageryProtocol(
            trial_recorder=self._trial_recorder,
            predictor=self._predictor,
            parent=self,
        )

        self.setWindowTitle("NeuroPilot")
        self.resize(1280, 800)
        self._build_nav()
        self._bind_bus()

    def _build_nav(self) -> None:
        from neuropilot.ui.pages.analytics_page import AnalyticsPage
        from neuropilot.ui.pages.dashboard_page import DashboardPage
        from neuropilot.ui.pages.debug_page import DebugPage
        from neuropilot.ui.pages.device_page import DevicePage
        from neuropilot.ui.pages.eeg_page import EEGPage
        from neuropilot.ui.pages.logs_page import LogsPage
        from neuropilot.ui.pages.ml_page import MLPage
        from neuropilot.ui.pages.settings_page import SettingsPage
        from neuropilot.ui.pages.task_page import TaskPage

        self._dashboard_page = DashboardPage(cfg=self._cfg)
        self._dashboard_page.setObjectName("dashboardPage")
        self.addSubInterface(self._dashboard_page, FIF.HOME, "总览", NavigationItemPosition.TOP)

        self._eeg_page = EEGPage(cfg=self._cfg)
        self._eeg_page.setObjectName("eegPage")
        self.addSubInterface(self._eeg_page, FIF.HEART, "脑电采集", NavigationItemPosition.SCROLL)

        self._subjects_page = SubjectsPage(self._subject_repo)
        self._subjects_page.setObjectName("subjectsPage")
        self.addSubInterface(self._subjects_page, FIF.PEOPLE, "受试者", NavigationItemPosition.SCROLL)

        self._device_page = DevicePage(cfg=self._cfg)
        self._device_page.setObjectName("devicePage")
        self.addSubInterface(self._device_page, FIF.IOT, "外设控制", NavigationItemPosition.SCROLL)

        self._debug_page = DebugPage()
        self._debug_page.setObjectName("debugPage")
        self.addSubInterface(self._debug_page, FIF.DEVELOPER_TOOLS, "调试", NavigationItemPosition.SCROLL)

        self._task_page = TaskPage(
            trial_repo=self._trial_repo,
            session_id_getter=self._get_current_session_id,
            parent=self,
        )
        self._task_page.apply_runtime_config(self._cfg)
        self._task_page.setObjectName("taskPage")
        self.addSubInterface(self._task_page, FIF.PLAY, "运动范式", NavigationItemPosition.SCROLL)

        self._ml_page = MLPage()
        self._ml_page.setObjectName("mlPage")
        self.addSubInterface(self._ml_page, FIF.EDUCATION, "模型训练", NavigationItemPosition.SCROLL)

        self._analytics_page = AnalyticsPage(
            session_repo=self._session_repo,
            trial_repo=self._trial_repo,
            subject_repo=self._subject_repo,
        )
        self._analytics_page.setObjectName("analyticsPage")
        self.addSubInterface(self._analytics_page, FIF.PIE_SINGLE, "数据分析", NavigationItemPosition.SCROLL)

        log_file = getattr(self._cfg, "log_file", "")
        log_dir = str(Path(log_file).parent) if log_file else None
        self._logs_page = LogsPage(log_dir=log_dir)
        self._logs_page.setObjectName("logsPage")
        self.addSubInterface(self._logs_page, FIF.SCROLL, "日志", NavigationItemPosition.BOTTOM)

        self._settings_page = SettingsPage(self._cfg)
        self._settings_page.settings_saved.connect(self._on_settings_saved)
        self._settings_page.setObjectName("settingsPage")
        self.addSubInterface(self._settings_page, FIF.SETTING, "设置", NavigationItemPosition.BOTTOM)

    def _bind_bus(self) -> None:
        bus = EventBus.instance()
        bus.eeg_connect_requested.connect(self._on_eeg_connect_requested)
        bus.eeg_disconnect_requested.connect(self._on_eeg_disconnect_requested)
        bus.subject_selected.connect(self._on_subject_selected)
        bus.paradigm_start_requested.connect(self._on_paradigm_start)
        bus.paradigm_abort_requested.connect(self._on_paradigm_abort)
        bus.ml_start_training.connect(self._on_ml_start_training)
        bus.ml_cancel_training.connect(self._on_ml_cancel_training)
        bus.ml_activate_model.connect(self._on_ml_activate_model)

    # ------------------------------------------------------------------
    # 用户登录
    # ------------------------------------------------------------------

    def bind_user(self, result: AuthResult) -> None:
        self._current_user = result
        EventBus.instance().user_logged_in.emit(result)
        self.setWindowTitle(f"NeuroPilot - {result.username} ({result.role})")

    # ------------------------------------------------------------------
    # EEG 连接 — 使用 EEGConnectionConfig 统一构造 transport
    # ------------------------------------------------------------------

    def _on_eeg_connect_requested(self, transport_key: str, params: dict) -> None:
        from loguru import logger

        logger.info("EEG 连接请求. transport={} params={}", transport_key, params)
        if self._worker is not None:
            return
        if self._current_user is None:
            self._show_warning("请先登录", "连接 EEG 前请先登录。")
            EventBus.instance().eeg_connected.emit(False, "请先登录")
            return
        if self._selected_subject_id <= 0:
            self._show_warning("请选择受试者", "启动 EEG 前请先选择受试者。")
            EventBus.instance().eeg_connected.emit(False, "请先选择受试者")
            return

        try:
            eeg_cfg = EEGConnectionConfig.from_key_params(transport_key, params, self._cfg)
            transport = eeg_cfg.build_transport()
        except Exception as exc:
            EventBus.instance().eeg_connected.emit(False, str(exc))
            return

        from neuropilot.app.acquisition_worker import AcquisitionWorker

        coordinator = EEGSessionCoordinator(self._session_repo)
        recorder = EEGRecordService(self._cfg.data_dir)

        worker = AcquisitionWorker(
            transport=transport,
            session_coordinator=coordinator,
            record_service=recorder,
            subject_id=self._selected_subject_id,
            user_id=self._current_user.user_id or 0,
            transport_name=transport_key,
            parent=self,
        )
        worker.sig_connected.connect(
            lambda ok, message, current=worker, key=transport_key: self._on_worker_connected(
                current, key, ok, message
            )
        )
        worker.sig_samples.connect(EventBus.instance().eeg_samples.emit)
        worker.sig_error.connect(EventBus.instance().eeg_error.emit)
        worker.sig_traffic.connect(EventBus.instance().eeg_traffic.emit)
        worker.finished.connect(lambda current=worker: self._on_worker_finished(current))
        self._worker = worker
        worker.start()

    def _on_worker_connected(self, worker: object, transport_key: str, ok: bool, message: str) -> None:
        if ok:
            session_id = getattr(worker, "session_id", None)
            if session_id:
                self._mi_protocol.set_session_id(int(session_id))
                try:
                    t = getattr(worker, "_transport", None)
                    n_ch = t.n_channels if t else 0
                    srate = t.srate if t else 0.0
                    EventBus.instance().eeg_session_started.emit(int(session_id), n_ch, srate)
                except Exception:
                    pass
            EventBus.instance().eeg_connected.emit(True, transport_key)
        else:
            EventBus.instance().eeg_connected.emit(False, message)

    def _on_eeg_disconnect_requested(self) -> None:
        worker = self._worker
        if worker is None:
            EventBus.instance().eeg_disconnected.emit()
            return
        if worker is self._disconnecting_worker:
            return

        self._disconnecting_worker = worker
        self._disconnect_timer.start()
        worker.stop()  # type: ignore[union-attr]

    def _on_worker_finished(self, worker: object) -> None:
        if worker is self._disconnecting_worker:
            self._disconnect_timer.stop()
            self._disconnecting_worker = None
        if worker is not self._worker:
            return

        self._mi_protocol.set_session_id(None)
        self._worker = None
        EventBus.instance().eeg_disconnected.emit()

    def _on_disconnect_timeout(self) -> None:
        worker = self._disconnecting_worker
        if worker is None:
            return

        from loguru import logger

        logger.warning("EEG disconnect timed out; forcing worker shutdown")
        try:
            if worker.isRunning():  # type: ignore[union-attr]
                worker.terminate()  # type: ignore[union-attr]
                worker.wait(300)  # type: ignore[union-attr]
        except Exception:
            logger.exception("Failed to force-stop EEG worker after disconnect timeout")

        self._disconnecting_worker = None
        if worker is self._worker:
            self._mi_protocol.set_session_id(None)
            self._worker = None
            EventBus.instance().eeg_disconnected.emit()

        self._show_warning("断开超时", "EEG 连接关闭过慢，已强制释放，可重新连接。")

    def _get_current_session_id(self) -> Optional[int]:
        return self._mi_protocol.session_id

    # ------------------------------------------------------------------
    # 范式控制 — 委托给 MotorImageryProtocol
    # ------------------------------------------------------------------

    def _on_paradigm_start(self, config: dict) -> None:
        if self._mi_protocol.session_id is None:
            self._show_warning("无 EEG 会话", "请先连接 EEG 再开始任务。")
            return
        self._mi_protocol.configure(config)
        self._mi_protocol.start()

    def _on_paradigm_abort(self) -> None:
        self._mi_protocol.abort()

    # ------------------------------------------------------------------
    # 受试者选择
    # ------------------------------------------------------------------

    def _on_subject_selected(self, subject: object) -> None:
        subject_id = getattr(subject, "id", 0)
        self._selected_subject_id = int(subject_id) if subject_id else 0
        self._sync_subject_model()

    # ------------------------------------------------------------------
    # ML 训练
    # ------------------------------------------------------------------

    def _on_ml_start_training(self, config: dict) -> None:
        if self._selected_subject_id <= 0:
            EventBus.instance().ml_train_failed.emit("请先选择受试者再训练。")
            return
        try:
            dataset = build_subject_dataset(
                self._selected_subject_id,
                self._session_repo,
                self._trial_repo,
                self._cfg.data_dir,
            )
        except Exception as exc:
            EventBus.instance().ml_train_failed.emit(str(exc))
            return

        job = TrainJob(
            dataset.X,
            dataset.y,
            model_store=self._model_store,
            subject_id=self._selected_subject_id,
            algo=str(config.get("algo", "svm")),
            n_components=int(config.get("n_components", 4)),
            srate=dataset.srate,
        )
        job.signals.sig_progress.connect(EventBus.instance().ml_train_requested.emit)
        job.signals.sig_done.connect(self._on_ml_train_done)
        job.signals.sig_failed.connect(self._on_ml_train_failed)
        self._ml_job = job
        QThreadPool.globalInstance().start(job)

    def _on_ml_cancel_training(self) -> None:
        if self._ml_job is not None:
            self._ml_job.cancel()

    def _on_ml_train_done(self, record: object) -> None:
        self._ml_job = None
        self._current_model_record = record if isinstance(record, ModelRecord) else record
        self._ml_page.set_model_record(record, active=False)
        EventBus.instance().ml_train_done.emit(record)

    def _on_ml_train_failed(self, message: str) -> None:
        self._ml_job = None
        EventBus.instance().ml_train_failed.emit(message)

    def _on_ml_activate_model(self) -> None:
        record = self._current_model_record
        if record is None:
            self._show_warning("无可用模型", "请先训练或选择模型后再激活。")
            return
        try:
            pipeline = self._model_store.load(record.id)
            self._model_store.activate(record.id)
            self._predictor.set_pipeline(pipeline, ["left", "right"])
            self._ml_page.set_model_record(record, active=True)
        except Exception as exc:
            self._show_warning("激活失败", str(exc))

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------

    def _on_settings_saved(self, cfg: object) -> None:
        self._apply_runtime_config(cfg)

    def _apply_runtime_config(self, cfg: object) -> None:
        self._cfg = cfg
        self._auth_svc.update_policy(
            lock_threshold=int(getattr(cfg, "lock_threshold", 5)),
            lock_minutes=int(getattr(cfg, "lock_minutes", 10)),
        )
        self._eeg_page.apply_runtime_config(cfg)
        self._device_page.apply_runtime_config(cfg)
        self._task_page.apply_runtime_config(cfg)
        self._dashboard_page.apply_runtime_config(cfg)
        self._predictor.update_sampling(
            srate=float(getattr(cfg, "eeg_sample_rate", 250)),
            n_channels=int(getattr(cfg, "eeg_channels", 8)),
        )

    # ------------------------------------------------------------------
    # 模型同步
    # ------------------------------------------------------------------

    def _sync_subject_model(self) -> None:
        if self._selected_subject_id <= 0:
            self._current_model_record = None
            self._ml_page.set_model_record(None)
            return
        records = self._model_store.list_by_subject(self._selected_subject_id)
        if not records:
            self._current_model_record = None
            self._ml_page.set_model_record(None)
            return
        active_record = next((r for r in records if r.is_active), records[0])
        self._current_model_record = active_record
        self._ml_page.set_model_record(active_record, active=active_record.is_active)
        if active_record.is_active:
            try:
                pipeline = self._model_store.load(active_record.id)
                self._predictor.set_pipeline(pipeline, ["left", "right"])
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _show_warning(self, title: str, content: str) -> None:
        InfoBar.warning(
            title, content, parent=self,
            duration=4000, position=InfoBarPosition.TOP_RIGHT,
        )


def show_login_and_run(
    auth_service: AuthService,
    subject_repo: SubjectRepo,
    session_repo: SessionRepo,
    trial_repo: TrialRepo,
    cfg: object,
    session_factory: object,
) -> None:
    from neuropilot.ui.login_dialog import LoginDialog

    app = QApplication.instance()
    if app is not None:
        app.setQuitOnLastWindowClosed(False)

    dialog = LoginDialog(auth_service)
    if dialog.exec_() != dialog.Accepted:
        current_app = QApplication.instance()
        if current_app is not None:
            current_app.quit()
        return

    result = dialog.auth_result()
    if result is None or not result.success:
        current_app = QApplication.instance()
        if current_app is not None:
            current_app.quit()
        return

    window = MainWindow(
        auth_service,
        subject_repo,
        session_repo=session_repo,
        trial_repo=trial_repo,
        cfg=cfg,
        session_factory=session_factory,
    )
    window.bind_user(result)
    app = QApplication.instance()
    if app is not None:
        setattr(app, "_neuropilot_main_window", window)
        app.setQuitOnLastWindowClosed(True)
    window.show()
    window.raise_()
    window.activateWindow()
