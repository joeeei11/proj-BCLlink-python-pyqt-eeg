from __future__ import annotations

from PyQt5.QtWidgets import QApplication

# ── Fluent Light Palette ───────────────────────────────────────────────────
COLOR_PRIMARY        = "#0078D4"   # Fluent Windows Blue
COLOR_PRIMARY_HOVER  = "#106EBE"
COLOR_PRIMARY_LIGHT  = "#EFF6FC"   # 淡蓝背景
COLOR_SUCCESS        = "#107C10"   # 绿
COLOR_SUCCESS_LIGHT  = "#DFF6DD"
COLOR_WARNING        = "#FF8C00"   # 橙
COLOR_WARNING_LIGHT  = "#FFF4CE"
COLOR_ERROR          = "#D13438"   # 红
COLOR_ERROR_LIGHT    = "#FDE7E9"
COLOR_TEXT           = "#201F1E"   # 主文字
COLOR_TEXT_SECONDARY = "#605E5C"   # 次级文字
COLOR_TEXT_DISABLED  = "#A19F9D"   # 禁用文字
COLOR_BG             = "#FAF9F8"   # 页面背景
COLOR_SURFACE        = "#FFFFFF"   # 卡片背景
COLOR_BORDER         = "#E1DFDD"   # 边框
COLOR_BORDER_FOCUS   = "#0078D4"
COLOR_SEPARATOR      = "#EDEBE9"

# 保持向后兼容
COLOR_BG_DARK  = "#1E1E2E"
COLOR_BG_LIGHT = COLOR_BG

_GLOBAL_QSS = """
/* ── 全局字体 ───────────────────────────────────────────────────────────── */
QWidget {
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #201F1E;
}
QPlainTextEdit, QTextEdit {
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
}

/* ── 页面背景 ───────────────────────────────────────────────────────────── */
QMainWindow, QDialog {
    background-color: #FAF9F8;
}

/* ── 卡片容器 ───────────────────────────────────────────────────────────── */
QFrame[cardFrame="true"], QWidget[cardWidget="true"] {
    background: #FFFFFF;
    border: 1px solid #E1DFDD;
    border-radius: 8px;
}

/* ── 标准输入框 ─────────────────────────────────────────────────────────── */
QLineEdit {
    background: #FFFFFF;
    border: 1px solid #C8C6C4;
    border-radius: 4px;
    padding: 5px 10px;
    selection-background-color: #0078D4;
    color: #201F1E;
    min-height: 28px;
}
QLineEdit:hover {
    border-color: #979693;
}
QLineEdit:focus {
    border-color: #0078D4;
    border-width: 1px;
    outline: none;
}
QLineEdit:disabled {
    background: #F3F2F1;
    color: #A19F9D;
    border-color: #E1DFDD;
}

/* ── SpinBox ────────────────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    border: 1px solid #C8C6C4;
    border-radius: 4px;
    padding: 5px 8px;
    color: #201F1E;
    min-height: 28px;
}
QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #979693;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #0078D4;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: transparent;
    border: none;
    width: 18px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: #F3F2F1;
}
QSpinBox::up-arrow {
    width: 8px; height: 8px;
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #605E5C;
}
QSpinBox::down-arrow {
    width: 8px; height: 8px;
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #605E5C;
}

/* ── 标准按钮（非 qfluentwidgets） ─────────────────────────────────────── */
QPushButton {
    background: #FFFFFF;
    border: 1px solid #C8C6C4;
    border-radius: 4px;
    padding: 6px 16px;
    color: #201F1E;
    min-height: 28px;
}
QPushButton:hover {
    background: #F3F2F1;
    border-color: #979693;
}
QPushButton:pressed {
    background: #EDEBE9;
}
QPushButton:disabled {
    background: #F3F2F1;
    color: #A19F9D;
    border-color: #E1DFDD;
}
QPushButton[primaryButton="true"] {
    background: #0078D4;
    border-color: #0078D4;
    color: #FFFFFF;
    font-weight: 600;
}
QPushButton[primaryButton="true"]:hover {
    background: #106EBE;
    border-color: #106EBE;
}
QPushButton[primaryButton="true"]:pressed {
    background: #005A9E;
}

/* ── ProgressBar ────────────────────────────────────────────────────────── */
QProgressBar {
    background: #F3F2F1;
    border: none;
    border-radius: 3px;
    text-align: center;
    color: #201F1E;
    font-size: 11px;
    min-height: 6px;
    max-height: 6px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0078D4, stop:1 #4FC3F7);
    border-radius: 3px;
}

/* ── Splitter ───────────────────────────────────────────────────────────── */
QSplitter::handle {
    background: #EDEBE9;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}
QSplitter::handle:hover {
    background: #0078D4;
}

/* ── TableWidget ────────────────────────────────────────────────────────── */
QTableWidget {
    background: #FFFFFF;
    border: 1px solid #E1DFDD;
    border-radius: 6px;
    gridline-color: #EDEBE9;
    selection-background-color: #EFF6FC;
    selection-color: #201F1E;
    alternate-background-color: #FAF9F8;
}
QTableWidget::item {
    padding: 6px 10px;
    border: none;
}
QTableWidget::item:selected {
    background: #EFF6FC;
    color: #201F1E;
}
QHeaderView::section {
    background: #F3F2F1;
    color: #605E5C;
    font-weight: 600;
    font-size: 12px;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #EDEBE9;
    border-right: 1px solid #EDEBE9;
}
QHeaderView::section:last {
    border-right: none;
}

/* ── ScrollBar ──────────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #C8C6C4;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #979693;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #C8C6C4;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: #979693;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ── Label ──────────────────────────────────────────────────────────────── */
QLabel[statusSuccess="true"] {
    color: #107C10;
    font-weight: 600;
}
QLabel[statusError="true"] {
    color: #D13438;
    font-weight: 600;
}
QLabel[statusWarning="true"] {
    color: #FF8C00;
    font-weight: 600;
}
QLabel[captionLabel="true"] {
    color: #605E5C;
    font-size: 11px;
}

/* ── ToolTip ────────────────────────────────────────────────────────────── */
QToolTip {
    background: #323130;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
}
"""


def apply_global_qss(app: QApplication) -> None:
    existing = app.styleSheet()
    if _GLOBAL_QSS not in existing:
        app.setStyleSheet(existing + _GLOBAL_QSS)


def card_style(radius: int = 8, border_color: str = COLOR_BORDER) -> str:
    return (
        f"background: {COLOR_SURFACE}; "
        f"border: 1px solid {border_color}; "
        f"border-radius: {radius}px;"
    )


def status_style(status: str) -> str:
    """Return QSS color string for status labels: 'ok' | 'error' | 'warn' | 'idle'."""
    _MAP = {
        "ok":    f"color: {COLOR_SUCCESS}; font-weight: 600;",
        "error": f"color: {COLOR_ERROR};   font-weight: 600;",
        "warn":  f"color: {COLOR_WARNING}; font-weight: 600;",
        "idle":  f"color: {COLOR_TEXT_SECONDARY};",
    }
    return _MAP.get(status, _MAP["idle"])
