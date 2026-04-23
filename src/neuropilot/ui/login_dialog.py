from __future__ import annotations

from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath
from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
)
from loguru import logger

from neuropilot.app.auth_service import AuthResult, AuthService
from neuropilot.ui.theme import (
    COLOR_BG,
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
)


class _AccentHeader(QWidget):
    """Rounded top header with brand color gradient."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(88)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        r = self.rect()
        path.moveTo(0, r.height())
        path.lineTo(0, 10)
        path.quadTo(0, 0, 10, 0)
        path.lineTo(r.width() - 10, 0)
        path.quadTo(r.width(), 0, r.width(), 10)
        path.lineTo(r.width(), r.height())
        path.closeSubpath()

        from PyQt5.QtGui import QLinearGradient
        grad = QLinearGradient(0, 0, r.width(), 0)
        grad.setColorAt(0.0, QColor("#0078D4"))
        grad.setColorAt(1.0, QColor("#00B4FF"))
        p.fillPath(path, grad)

        p.setPen(QColor("#FFFFFF"))

        font_title = QFont("Microsoft YaHei", 14, QFont.Bold)
        p.setFont(font_title)
        p.drawText(r.adjusted(20, 14, -10, -30), Qt.AlignLeft | Qt.AlignVCenter, "NeuroPilot")

        font_sub = QFont("Microsoft YaHei", 9)
        p.setFont(font_sub)
        p.setPen(QColor(255, 255, 255, 180))
        p.drawText(r.adjusted(20, 46, -10, -8), Qt.AlignLeft | Qt.AlignVCenter, "脑机接口康复系统")


class LoginDialog(QDialog):
    def __init__(self, auth_service: AuthService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svc = auth_service
        self._result: AuthResult | None = None
        self._drag_pos: QPoint | None = None

        self.setWindowTitle("NeuroPilot 登录")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)  # type: ignore[arg-type]
        self.setAttribute(Qt.WA_TranslucentBackground)  # type: ignore[arg-type]
        self.setFixedSize(420, 360)

        self._build_ui()
        self._load_saved_username()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QWidget(self)
        card.setObjectName("loginCard")
        card.setStyleSheet(
            "#loginCard {"
            f"  background: {COLOR_SURFACE};"
            "   border-radius: 12px;"
            f"  border: 1px solid {COLOR_BORDER};"
            "}"
        )
        outer.addWidget(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ── 顶部品牌 Header ───────────────────────────────────────
        header = _AccentHeader(card)
        card_layout.addWidget(header)

        # ── 表单区域 ──────────────────────────────────────────────
        form_container = QWidget(card)
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(32, 24, 32, 24)
        form_layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft)

        lbl_user = BodyLabel("用户名")
        lbl_user.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        self._username_edit = LineEdit(form_container)
        self._username_edit.setPlaceholderText("请输入用户名")
        self._username_edit.setFixedHeight(34)
        form.addRow(lbl_user, self._username_edit)

        lbl_pass = BodyLabel("密码")
        lbl_pass.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        self._password_edit = PasswordLineEdit(form_container)
        self._password_edit.setPlaceholderText("请输入密码")
        self._password_edit.setFixedHeight(34)
        form.addRow(lbl_pass, self._password_edit)

        form_layout.addLayout(form)

        # ── 提示文字 ──────────────────────────────────────────────
        self._hint_label = QLabel("", form_container)
        self._hint_label.setAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
        self._hint_label.setStyleSheet(f"color: {COLOR_ERROR}; font-size: 12px;")
        self._hint_label.setFixedHeight(18)
        form_layout.addWidget(self._hint_label)

        # ── 登录按钮 ──────────────────────────────────────────────
        self._login_btn = PrimaryPushButton("登 录", form_container)
        self._login_btn.setFixedHeight(36)
        form_layout.addWidget(self._login_btn)

        # ── 版权信息 ──────────────────────────────────────────────
        footer_lbl = QLabel("© NeuroPilot BCI Rehabilitation System", form_container)
        footer_lbl.setAlignment(Qt.AlignCenter)
        footer_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px;")
        form_layout.addWidget(footer_lbl)

        card_layout.addWidget(form_container)

        # ── Timers ────────────────────────────────────────────────
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._on_countdown)
        self._countdown_seconds = 0

        self._login_btn.clicked.connect(self._on_login)
        self._password_edit.returnPressed.connect(self._on_login)

    # ------------------------------------------------------------------
    # 拖动
    # ------------------------------------------------------------------
    def _global_point(self, event: QMouseEvent) -> QPoint:
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        return event.globalPos()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:  # type: ignore[attr-defined]
            self._drag_pos = self._global_point(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.LeftButton:  # type: ignore[attr-defined]
            current_pos = self._global_point(event)
            self.move(self.pos() + current_pos - self._drag_pos)
            self._drag_pos = current_pos

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None

    # ------------------------------------------------------------------
    # 逻辑
    # ------------------------------------------------------------------
    def _on_login(self) -> None:
        username = self._username_edit.text().strip()
        password = self._password_edit.text()

        if not username or not password:
            self._hint_label.setText("用户名和密码不能为空")
            return

        self._login_btn.setEnabled(False)
        self._hint_label.setText("")
        try:
            result = self._svc.login(username, password)
        except Exception:
            logger.exception("Unexpected login failure for user '{}'", username)
            self._login_btn.setEnabled(True)
            self._hint_label.setText("登录服务异常，请查看日志")
            InfoBar.error(
                "登录异常",
                "认证服务发生异常，请查看日志后重试",
                parent=self,
                duration=4000,
                position=InfoBarPosition.TOP_RIGHT,
            )
            return

        if result.success:
            self._save_username(username)
            self._result = result
            self.accept()
            return

        if result.locked_until:
            from datetime import datetime, timezone
            try:
                locked_dt = datetime.fromisoformat(result.locked_until.replace("Z", "+00:00"))
                remaining_s = max(0, int((locked_dt - datetime.now(timezone.utc)).total_seconds()))
            except ValueError:
                remaining_s = 0
            self._countdown_seconds = remaining_s
            self._start_countdown()
        else:
            self._login_btn.setEnabled(True)
            hint = result.error or "登录失败"
            if result.remaining_attempts is not None:
                hint += f"（还剩 {result.remaining_attempts} 次机会）"
            self._hint_label.setText(hint)

    def _start_countdown(self) -> None:
        self._update_countdown_label()
        self._countdown_timer.start(1000)

    def _on_countdown(self) -> None:
        self._countdown_seconds -= 1
        if self._countdown_seconds <= 0:
            self._countdown_timer.stop()
            self._login_btn.setEnabled(True)
            self._hint_label.setText("账号已解锁，请重新登录")
            self._hint_label.setStyleSheet(f"color: {COLOR_PRIMARY}; font-size: 12px;")
        else:
            self._update_countdown_label()

    def _update_countdown_label(self) -> None:
        m, s = divmod(self._countdown_seconds, 60)
        self._hint_label.setText(f"账号已锁定，请 {m:02d}:{s:02d} 后重试")
        self._hint_label.setStyleSheet(f"color: {COLOR_ERROR}; font-size: 12px;")

    # ------------------------------------------------------------------
    # QSettings：仅存 username
    # ------------------------------------------------------------------
    def _save_username(self, username: str) -> None:
        try:
            from PyQt5.QtCore import QSettings
            qs = QSettings("NeuroPilot", "Login")
            qs.setValue("username", username)
        except Exception:
            pass

    def _load_saved_username(self) -> None:
        try:
            from PyQt5.QtCore import QSettings
            qs = QSettings("NeuroPilot", "Login")
            saved = qs.value("username", "")
            if saved:
                self._username_edit.setText(saved)
                self._password_edit.setFocus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def auth_result(self) -> AuthResult | None:
        return self._result
