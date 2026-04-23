from __future__ import annotations

import csv
from typing import Callable, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
)

from neuropilot.app.event_bus import EventBus
from neuropilot.ui.theme import (
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_SURFACE,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
)
from neuropilot.ui.widgets.stage_bar import StageBar
from neuropilot.ui.widgets.stimulus_area import StimulusArea

_CARD_STYLE = (
    f"background: {COLOR_SURFACE}; "
    f"border: 1px solid {COLOR_BORDER}; "
    "border-radius: 8px;"
)

_STATE_STYLES = {
    "IDLE": f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px; font-weight: 600;",
    "FIX":  f"color: {COLOR_PRIMARY};       font-size: 13px; font-weight: 600;",
    "CUE":  f"color: {COLOR_WARNING};       font-size: 13px; font-weight: 600;",
    "IMAG": f"color: {COLOR_SUCCESS};       font-size: 13px; font-weight: 600;",
    "REST": f"color: {COLOR_TEXT_SECONDARY};font-size: 13px; font-weight: 600;",
    "DONE": f"color: {COLOR_SUCCESS};       font-size: 13px; font-weight: 600;",
}


class TaskPage(QWidget):
    """Motor imagery task control page."""

    def __init__(
        self,
        trial_repo: object = None,
        session_id_getter: Callable[[], int | None] | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._trial_repo = trial_repo
        self._session_id_getter = session_id_getter
        self._current_session_id: Optional[int] = None
        self._current_intent: Optional[str] = None
        self._total_trials = 0
        self._setup_ui()
        self._bind_bus()

    def set_trial_repo(self, trial_repo: object) -> None:
        self._trial_repo = trial_repo

    def set_session_id_getter(self, getter: Callable[[], int | None] | None) -> None:
        self._session_id_getter = getter

    def apply_runtime_config(self, cfg: object) -> None:
        self._total_spin.setValue(int(getattr(cfg, "paradigm_trials_per_run", self._total_spin.value())))
        self._t_fix.setValue(int(getattr(cfg, "paradigm_fix_duration_ms", self._t_fix.value())))
        self._t_cue.setValue(int(getattr(cfg, "paradigm_cue_duration_ms", self._t_cue.value())))
        self._t_imag.setValue(int(getattr(cfg, "paradigm_imagery_duration_ms", self._t_imag.value())))
        self._t_rest.setValue(int(getattr(cfg, "paradigm_rest_duration_ms", self._t_rest.value())))
        self._t_iti.setValue(int(getattr(cfg, "paradigm_iti_duration_ms", self._t_iti.value())))

    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)
        root.addWidget(SubtitleLabel("运动想象任务"))

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)

        # ═══════════════════════════════════════════════════════════
        # 左侧：参数 + 进度 + 按钮
        # ═══════════════════════════════════════════════════════════
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # ── 时序参数卡片 ──────────────────────────────────────────
        param_card = QWidget()
        param_card.setObjectName("paramCard")
        param_card.setStyleSheet(f"#paramCard {{ {_CARD_STYLE} }}")
        param_inner = QVBoxLayout(param_card)
        param_inner.setContentsMargins(16, 12, 16, 16)
        param_inner.setSpacing(10)

        hdr = StrongBodyLabel("任务时序参数")
        hdr.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 600;")
        param_inner.addWidget(hdr)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignLeft)

        self._total_spin = self._make_spin(2, 200, 20)
        form.addRow(self._row_label("试次数"), self._total_spin)

        self._t_fix = self._make_spin(100, 5000, 500, " ms")
        form.addRow(self._row_label("注视期"), self._t_fix)

        self._t_cue = self._make_spin(100, 5000, 1000, " ms")
        form.addRow(self._row_label("提示期"), self._t_cue)

        self._t_imag = self._make_spin(500, 10000, 4000, " ms")
        form.addRow(self._row_label("想象期"), self._t_imag)

        self._t_rest = self._make_spin(500, 10000, 2000, " ms")
        form.addRow(self._row_label("休息期"), self._t_rest)

        self._t_iti = self._make_spin(100, 5000, 1000, " ms")
        form.addRow(self._row_label("试次间隔"), self._t_iti)

        param_inner.addLayout(form)

        media_form = QFormLayout()
        media_form.setSpacing(8)
        media_form.setLabelAlignment(Qt.AlignRight)
        media_form.setFormAlignment(Qt.AlignLeft)

        self._left_media_edit = QLineEdit(self)
        self._left_media_edit.setPlaceholderText("GIF 或 MP4")
        media_form.addRow(self._row_label("左手素材"), self._build_media_picker_row(self._left_media_edit))

        self._right_media_edit = QLineEdit(self)
        self._right_media_edit.setPlaceholderText("GIF 或 MP4")
        media_form.addRow(self._row_label("右手素材"), self._build_media_picker_row(self._right_media_edit))

        param_inner.addLayout(media_form)
        left_layout.addWidget(param_card)

        # ── 进度卡片 ──────────────────────────────────────────────
        prog_card = QWidget()
        prog_card.setObjectName("progCard")
        prog_card.setStyleSheet(f"#progCard {{ {_CARD_STYLE} }}")
        prog_inner = QVBoxLayout(prog_card)
        prog_inner.setContentsMargins(16, 12, 16, 12)
        prog_inner.setSpacing(6)

        status_row = QHBoxLayout()
        self._status_lbl = QLabel("空闲")
        self._status_lbl.setStyleSheet(_STATE_STYLES["IDLE"])
        status_row.addWidget(self._status_lbl)
        status_row.addStretch()
        self._progress_lbl = QLabel("0 / 0")
        self._progress_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        status_row.addWidget(self._progress_lbl)
        prog_inner.addLayout(status_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        prog_inner.addWidget(self._progress_bar)
        left_layout.addWidget(prog_card)

        # ── 操作按钮 ──────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_start = PrimaryPushButton("▶  开始")
        self._btn_abort = PushButton("■  终止")
        self._btn_abort.setEnabled(False)
        self._btn_export = PushButton("↓  导出 CSV")
        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_abort)
        btn_row.addWidget(self._btn_export)
        left_layout.addLayout(btn_row)
        left_layout.addStretch()

        splitter.addWidget(left)

        # ═══════════════════════════════════════════════════════════
        # 右侧：阶段条 + 刺激区
        # ═══════════════════════════════════════════════════════════
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # StageBar 外框
        stage_wrap = QWidget()
        stage_wrap.setObjectName("stageWrap")
        stage_wrap.setStyleSheet(f"#stageWrap {{ {_CARD_STYLE} }}")
        stage_wl = QVBoxLayout(stage_wrap)
        stage_wl.setContentsMargins(12, 8, 12, 8)
        self._stage_bar = StageBar()
        stage_wl.addWidget(self._stage_bar)
        right_layout.addWidget(stage_wrap)

        self._stimulus = StimulusArea()
        right_layout.addWidget(self._stimulus, stretch=1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, stretch=1)

        self._btn_start.clicked.connect(self._on_start)
        self._btn_abort.clicked.connect(self._on_abort)
        self._btn_export.clicked.connect(self._on_export)

    # ------------------------------------------------------------------
    @staticmethod
    def _make_spin(lo: int, hi: int, val: int, suffix: str = "") -> QSpinBox:
        sb = QSpinBox()
        sb.setRange(lo, hi)
        sb.setValue(val)
        if suffix:
            sb.setSuffix(suffix)
        return sb

    @staticmethod
    def _row_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    def _build_media_picker_row(self, line_edit: QLineEdit) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(line_edit, stretch=1)

        browse_btn = PushButton("选择", row)
        browse_btn.clicked.connect(lambda: self._browse_media(line_edit))
        layout.addWidget(browse_btn)

        clear_btn = PushButton("清空", row)
        clear_btn.clicked.connect(line_edit.clear)
        layout.addWidget(clear_btn)
        return row

    def _browse_media(self, line_edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择想象素材",
            line_edit.text().strip(),
            "媒体文件 (*.gif *.mp4 *.mov *.avi *.mkv);;GIF 文件 (*.gif);;视频文件 (*.mp4 *.mov *.avi *.mkv);;所有文件 (*.*)",
        )
        if path:
            line_edit.setText(path)

    # ------------------------------------------------------------------
    def _bind_bus(self) -> None:
        bus = EventBus.instance()
        bus.paradigm_state_changed.connect(self._on_state_changed)
        bus.paradigm_trial_opened.connect(self._on_trial_opened)
        bus.paradigm_trial_closed.connect(self._on_trial_closed)
        bus.prediction_result.connect(self._on_prediction)
        bus.device_disconnected.connect(self._on_device_disconnected)

    def _resolve_session_id(self) -> Optional[int]:
        if self._session_id_getter is None:
            return self._current_session_id
        session_id = self._session_id_getter()
        if session_id is not None and session_id > 0:
            self._current_session_id = session_id
        return self._current_session_id

    def _on_start(self) -> None:
        self._resolve_session_id()
        self._total_trials = self._total_spin.value()
        self._stimulus.set_cue_media(
            left_path=self._left_media_edit.text(),
            right_path=self._right_media_edit.text(),
        )
        config = {
            "total_trials": self._total_trials,
            "t_fix_ms":  self._t_fix.value(),
            "t_cue_ms":  self._t_cue.value(),
            "t_imag_ms": self._t_imag.value(),
            "t_rest_ms": self._t_rest.value(),
            "t_iti_ms":  self._t_iti.value(),
        }
        EventBus.instance().paradigm_start_requested.emit(config)  # type: ignore[attr-defined]

    def _on_abort(self) -> None:
        EventBus.instance().paradigm_abort_requested.emit()  # type: ignore[attr-defined]

    def _on_export(self) -> None:
        session_id = self._resolve_session_id()
        if self._trial_repo is None or session_id is None:
            InfoBar.warning(
                "无会话", "导出前请先连接 EEG 并执行任务。",
                parent=self, duration=3000, position=InfoBarPosition.TOP_RIGHT,
            )
            return

        trials = self._trial_repo.list_by_session(session_id)  # type: ignore[union-attr]
        if not trials:
            InfoBar.warning(
                "暂无数据", "当前会话未找到试次记录。",
                parent=self, duration=3000, position=InfoBarPosition.TOP_RIGHT,
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出试次 CSV", f"session_{session_id}.csv", "CSV (*.csv)",
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["trial_uuid", "label", "onset_time", "offset_time", "predicted", "confidence"])
            for trial in trials:
                writer.writerow([
                    trial.trial_uuid, trial.label, trial.onset_time,
                    trial.offset_time, trial.predicted, trial.confidence,
                ])

        InfoBar.success(
            "已导出", path,
            parent=self, duration=3000, position=InfoBarPosition.TOP_RIGHT,
        )

    def _on_state_changed(self, state: str, trial_index: int, total: int) -> None:
        self._stage_bar.highlight(state)
        self._progress_lbl.setText(f"{trial_index} / {total}")
        pct = int(trial_index / max(total, 1) * 100)
        self._progress_bar.setValue(pct)

        state_label_map = {
            "IDLE": "空闲", "FIX": "注视期", "CUE": "提示期",
            "IMAG": "想象期", "REST": "休息期", "DONE": "已完成",
        }
        self._status_lbl.setText(state_label_map.get(state, state))
        self._status_lbl.setStyleSheet(_STATE_STYLES.get(state, _STATE_STYLES["IDLE"]))

        if state == "IDLE":
            self._btn_start.setEnabled(True)
            self._btn_abort.setEnabled(False)
            self._current_intent = None
            self._stimulus.show_fix()
            self._stage_bar.reset()
            self._progress_bar.setValue(0)
        elif state in ("FIX", "CUE", "IMAG", "REST"):
            self._btn_start.setEnabled(False)
            self._btn_abort.setEnabled(True)
            if state == "FIX":
                self._stimulus.show_fix()
            elif state == "CUE" and self._current_intent in {"left", "right"}:
                self._stimulus.show_prompt(self._current_intent)
            elif state == "IMAG" and self._current_intent in {"left", "right"}:
                self._stimulus.show_cue(self._current_intent)
            elif state == "REST":
                self._stimulus.show_rest()
        elif state == "DONE":
            self._btn_start.setEnabled(True)
            self._btn_abort.setEnabled(False)
            self._current_intent = None
            self._progress_bar.setValue(100)
            InfoBar.success(
                "任务完成", f"共完成 {total} 个试次。",
                parent=self, duration=3000, position=InfoBarPosition.TOP_RIGHT,
            )

    def _on_trial_opened(self, trial_uuid: str, intent: str) -> None:
        self._resolve_session_id()
        self._current_intent = intent
        self._stimulus.show_prompt(intent)

    def _on_trial_closed(self, trial_uuid: str) -> None:
        self._current_intent = None

    def _on_prediction(self, label: str, confidence: float) -> None:
        self._stimulus.show_result(label, confidence)

    def _on_device_disconnected(self) -> None:
        if self._btn_abort.isEnabled():
            InfoBar.warning(
                "设备已断开", "当前任务已自动终止。",
                parent=self, duration=5000, position=InfoBarPosition.TOP_RIGHT,
            )
            self._btn_abort.click()
