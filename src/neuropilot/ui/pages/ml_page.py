from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    ComboBox,
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
    COLOR_PRIMARY_LIGHT,
    COLOR_SUCCESS,
    COLOR_SUCCESS_LIGHT,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
    COLOR_WARNING_LIGHT,
)

_ALGOS       = ["svm", "lr", "rf", "knn"]
_ALGO_LABELS = ["SVM (RBF 核)", "逻辑回归 (LR)", "随机森林 (RF)", "K 近邻 (KNN)"]
_ALGO_DESC   = [
    "适合小样本，泛化能力强，支持非线性分类。",
    "训练快速，可解释性好，适合线性可分场景。",
    "抗噪声，不易过拟合，适合特征较多的场景。",
    "无参数训练，计算简单，适合类别分布均匀。",
]

_CARD = (
    f"background: {COLOR_SURFACE}; "
    f"border: 1px solid {COLOR_BORDER}; "
    "border-radius: 8px;"
)


class MLPage(QWidget):
    """Model training and activation page."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._bind_bus()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)
        root.addWidget(SubtitleLabel("模型训练"))

        # ── 算法配置卡片 ─────────────────────────────────────────
        algo_card = QWidget()
        algo_card.setObjectName("algoCard")
        algo_card.setStyleSheet(f"#algoCard {{ {_CARD} }}")
        algo_inner = QVBoxLayout(algo_card)
        algo_inner.setContentsMargins(16, 12, 16, 16)
        algo_inner.setSpacing(10)

        hdr = StrongBodyLabel("算法与参数")
        hdr.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 600;")
        algo_inner.addWidget(hdr)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._algo_box = ComboBox(algo_card)
        for label in _ALGO_LABELS:
            self._algo_box.addItem(label)
        form.addRow(self._lbl("分类算法"), self._algo_box)

        self._n_comp_spin = QSpinBox(algo_card)
        self._n_comp_spin.setRange(2, 32)
        self._n_comp_spin.setValue(4)
        self._n_comp_spin.setSingleStep(2)
        form.addRow(self._lbl("CSP 分量数"), self._n_comp_spin)
        algo_inner.addLayout(form)

        self._algo_desc = QLabel(_ALGO_DESC[0], algo_card)
        self._algo_desc.setWordWrap(True)
        self._algo_desc.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"background: {COLOR_PRIMARY_LIGHT}; border-radius: 4px; padding: 6px 8px;"
        )
        algo_inner.addWidget(self._algo_desc)
        root.addWidget(algo_card)

        self._algo_box.currentIndexChanged.connect(self._on_algo_changed)

        # ── 训练进度卡片 ─────────────────────────────────────────
        train_card = QWidget()
        train_card.setObjectName("trainCard")
        train_card.setStyleSheet(f"#trainCard {{ {_CARD} }}")
        train_inner = QVBoxLayout(train_card)
        train_inner.setContentsMargins(16, 12, 16, 16)
        train_inner.setSpacing(8)

        status_row = QHBoxLayout()
        self._status_lbl = QLabel("空闲")
        self._status_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px;")
        status_row.addWidget(self._status_lbl)
        status_row.addStretch()
        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setStyleSheet(f"color: {COLOR_PRIMARY}; font-size: 12px; font-weight: 600;")
        status_row.addWidget(self._pct_lbl)
        train_inner.addLayout(status_row)

        self._progress_bar = QProgressBar(train_card)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        train_inner.addWidget(self._progress_bar)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_train = PrimaryPushButton("▶  开始训练", train_card)
        self._btn_cancel = PushButton("■  取消", train_card)
        self._btn_cancel.setEnabled(False)
        btn_row.addWidget(self._btn_train)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addStretch()
        train_inner.addLayout(btn_row)

        root.addWidget(train_card)

        # ── 模型状态卡片 ─────────────────────────────────────────
        model_card = QWidget()
        model_card.setObjectName("modelCard")
        model_card.setStyleSheet(f"#modelCard {{ {_CARD} }}")
        model_inner = QVBoxLayout(model_card)
        model_inner.setContentsMargins(16, 12, 16, 16)
        model_inner.setSpacing(10)

        hdr2 = StrongBodyLabel("当前可用模型")
        hdr2.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 600;")
        model_inner.addWidget(hdr2)

        self._model_status = QLabel("所选受试者暂无可用模型。")
        self._model_status.setWordWrap(True)
        self._model_status.setStyleSheet(
            f"color: {COLOR_TEXT}; font-size: 12px; "
            f"background: #F3F2F1; border-radius: 4px; padding: 8px 10px;"
        )
        model_inner.addWidget(self._model_status)

        self._btn_activate = PrimaryPushButton("⚡  激活模型", model_card)
        self._btn_activate.setEnabled(False)
        model_inner.addWidget(self._btn_activate)

        root.addWidget(model_card)
        root.addStretch()

        self._btn_train.clicked.connect(self._on_train)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_activate.clicked.connect(self._on_activate)

    @staticmethod
    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        return lbl

    # ------------------------------------------------------------------
    def _bind_bus(self) -> None:
        bus = EventBus.instance()
        bus.ml_train_requested.connect(self._on_train_progress)  # type: ignore[attr-defined]
        bus.ml_train_done.connect(self._on_train_done)           # type: ignore[attr-defined]
        bus.ml_train_failed.connect(self._on_train_failed)       # type: ignore[attr-defined]

    def _on_algo_changed(self, index: int) -> None:
        if 0 <= index < len(_ALGO_DESC):
            self._algo_desc.setText(_ALGO_DESC[index])

    def set_model_record(self, record: object | None, *, active: bool | None = None) -> None:
        if record is None:
            self._model_status.setText("所选受试者暂无可用模型。")
            self._model_status.setStyleSheet(
                f"color: {COLOR_TEXT}; font-size: 12px; "
                "background: #F3F2F1; border-radius: 4px; padding: 8px 10px;"
            )
            self._btn_activate.setEnabled(False)
            return

        accuracy = getattr(record, "accuracy", None)
        acc_text = "N/A" if accuracy is None else f"{accuracy:.1%}"
        algorithm = getattr(record, "algorithm", "")
        name = getattr(record, "name", "")
        is_active = bool(getattr(record, "is_active", False) if active is None else active)

        if is_active:
            suffix = "  ✔ 已激活"
            bg = COLOR_SUCCESS_LIGHT
            fg = COLOR_SUCCESS
        else:
            suffix = ""
            bg = COLOR_PRIMARY_LIGHT
            fg = COLOR_PRIMARY

        self._model_status.setText(f"{name}\n算法: {algorithm}  |  准确率: {acc_text}{suffix}")
        self._model_status.setStyleSheet(
            f"color: {fg}; font-size: 12px; font-weight: 600; "
            f"background: {bg}; border-radius: 4px; padding: 8px 10px;"
        )
        self._btn_activate.setEnabled(not is_active)

    def _on_train(self) -> None:
        algo = _ALGOS[self._algo_box.currentIndex()]
        config = {"algo": algo, "n_components": self._n_comp_spin.value()}
        EventBus.instance().ml_start_training.emit(config)  # type: ignore[attr-defined]
        self._btn_train.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._progress_bar.setValue(0)
        self._pct_lbl.setText("0%")
        self._status_lbl.setText("训练中…")
        self._status_lbl.setStyleSheet(f"color: {COLOR_PRIMARY}; font-size: 13px;")

    def _on_cancel(self) -> None:
        EventBus.instance().ml_cancel_training.emit()  # type: ignore[attr-defined]
        self._btn_cancel.setEnabled(False)
        self._status_lbl.setText("正在取消…")
        self._status_lbl.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 13px;")

    def _on_activate(self) -> None:
        EventBus.instance().ml_activate_model.emit()  # type: ignore[attr-defined]

    def _on_train_progress(self, percent: int, message: str) -> None:
        self._progress_bar.setValue(percent)
        self._pct_lbl.setText(f"{percent}%")
        self._status_lbl.setText(message)

    def _on_train_done(self, record: object) -> None:
        self._progress_bar.setValue(100)
        self._pct_lbl.setText("100%")
        self._status_lbl.setText("训练完成")
        self._status_lbl.setStyleSheet(f"color: {COLOR_SUCCESS}; font-size: 13px; font-weight: 600;")
        self._btn_train.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self.set_model_record(record, active=False)
        InfoBar.success(
            "训练完成", self._model_status.text().split("\n")[0],
            parent=self, duration=3000, position=InfoBarPosition.TOP_RIGHT,
        )

    def _on_train_failed(self, message: str) -> None:
        self._btn_train.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self._status_lbl.setText(f"失败: {message}")
        self._status_lbl.setStyleSheet(f"color: {COLOR_ERROR}; font-size: 13px;")
        InfoBar.error(
            "训练失败", message,
            parent=self, duration=5000, position=InfoBarPosition.TOP_RIGHT,
        )
