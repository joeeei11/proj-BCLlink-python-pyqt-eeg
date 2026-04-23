from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QRectF, Qt, QUrl
from PyQt5.QtGui import QColor, QFont, QMovie, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QLabel, QSizePolicy, QStackedLayout, QVBoxLayout, QWidget

try:
    from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
    from PyQt5.QtMultimediaWidgets import QVideoWidget

    _HAS_VIDEO = True
except ImportError:
    QMediaContent = object  # type: ignore[assignment,misc]
    QMediaPlayer = object  # type: ignore[assignment,misc]
    QVideoWidget = QWidget  # type: ignore[assignment,misc]
    _HAS_VIDEO = False


_ASSET_DIR = Path(__file__).parent.parent.parent.parent.parent / "assets"
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv"}

# Phase background colors (Fluent-light palette)
_BG_IDLE = QColor("#F3F2F1")
_BG_FIX = QColor("#EFF6FC")
_BG_LEFT = QColor("#E6F4EA")
_BG_RIGHT = QColor("#FFF4CE")
_BG_REST = QColor("#F3F2F1")
_BG_RESULT = QColor("#F0F0F0")


class _Canvas(QWidget):
    """Self-contained painter canvas that renders the current stimulus state."""

    IDLE = "idle"
    FIX = "fix"
    LEFT = "left"
    RIGHT = "right"
    REST = "rest"
    RESULT = "result"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = self.IDLE
        self._result_label = ""
        self._confidence = 0.0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(200, 180)

    def set_state(self, state: str, *, result_label: str = "", confidence: float = 0.0) -> None:
        self._state = state
        self._result_label = result_label
        self._confidence = confidence
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(self.rect())
        bg = {
            self.IDLE: _BG_IDLE,
            self.FIX: _BG_FIX,
            self.LEFT: _BG_LEFT,
            self.RIGHT: _BG_RIGHT,
            self.REST: _BG_REST,
            self.RESULT: _BG_RESULT,
        }.get(self._state, _BG_IDLE)

        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        p.fillPath(path, bg)

        border_color = {
            self.FIX: QColor("#0078D4"),
            self.LEFT: QColor("#107C10"),
            self.RIGHT: QColor("#FF8C00"),
            self.REST: QColor("#C8C6C4"),
        }.get(self._state, QColor("#E1DFDD"))
        p.setPen(QPen(border_color, 1.5))
        inner = rect.adjusted(0.75, 0.75, -0.75, -0.75)
        inner_path = QPainterPath()
        inner_path.addRoundedRect(inner, 11.5, 11.5)
        p.drawPath(inner_path)

        center_x = rect.center().x()
        center_y = rect.center().y()

        if self._state == self.FIX:
            self._draw_fixation(p, center_x, center_y)
        elif self._state == self.LEFT:
            self._draw_arrow(p, center_x, center_y, direction="left")
        elif self._state == self.RIGHT:
            self._draw_arrow(p, center_x, center_y, direction="right")
        elif self._state == self.REST:
            self._draw_text(p, rect, "休 息", QColor("#605E5C"), size=28)
        elif self._state == self.RESULT:
            self._draw_result(p, rect, center_x, center_y)
        elif self._state == self.IDLE:
            self._draw_text(p, rect, "等待开始", QColor("#A19F9D"), size=20)

    def _draw_fixation(self, p: QPainter, center_x: float, center_y: float) -> None:
        p.setPen(QPen(QColor("#0078D4"), 4, Qt.SolidLine, Qt.RoundCap))
        arm = 32
        p.drawLine(int(center_x - arm), int(center_y), int(center_x + arm), int(center_y))
        p.drawLine(int(center_x), int(center_y - arm), int(center_x), int(center_y + arm))

    def _draw_arrow(self, p: QPainter, center_x: float, center_y: float, direction: str) -> None:
        color = QColor("#107C10") if direction == "left" else QColor("#FF8C00")
        p.setPen(QPen(color, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(color)

        shaft_w = 52
        head_w = 22
        head_h = 16

        from PyQt5.QtCore import QPointF
        from PyQt5.QtGui import QPolygonF

        if direction == "left":
            tip_x = center_x - shaft_w - head_w
            tail_x = center_x + shaft_w
            head_tip_x = center_x - shaft_w
            p.drawLine(int(head_tip_x), int(center_y), int(tail_x), int(center_y))
            p.drawPolygon(
                QPolygonF(
                    [
                        QPointF(tip_x, center_y),
                        QPointF(head_tip_x, center_y - head_h),
                        QPointF(head_tip_x, center_y + head_h),
                    ]
                )
            )
            self._draw_text(
                p,
                QRectF(tip_x, center_y + head_h + 12, tail_x - tip_x, 28),
                "左手",
                color,
                size=16,
            )
            return

        tip_x = center_x + shaft_w + head_w
        tail_x = center_x - shaft_w
        head_tip_x = center_x + shaft_w
        p.drawLine(int(tail_x), int(center_y), int(head_tip_x), int(center_y))
        p.drawPolygon(
            QPolygonF(
                [
                    QPointF(tip_x, center_y),
                    QPointF(head_tip_x, center_y - head_h),
                    QPointF(head_tip_x, center_y + head_h),
                ]
            )
        )
        self._draw_text(
            p,
            QRectF(tail_x, center_y + head_h + 12, tip_x - tail_x, 28),
            "右手",
            color,
            size=16,
        )

    def _draw_result(self, p: QPainter, rect: QRectF, center_x: float, center_y: float) -> None:
        pct = int(self._confidence * 100)
        label = "左手" if self._result_label == "left" else "右手" if self._result_label == "right" else self._result_label
        color = QColor("#107C10") if self._result_label == "left" else QColor("#FF8C00")

        self._draw_text(p, QRectF(rect.left(), rect.top() + 20, rect.width(), 40), "预测结果", QColor("#605E5C"), size=13)
        self._draw_text(p, QRectF(rect.left(), center_y - 24, rect.width(), 48), label, color, size=32, bold=True)
        self._draw_text(p, QRectF(rect.left(), center_y + 32, rect.width(), 32), f"置信度 {pct}%", color, size=14)

        bar_w = min(rect.width() * 0.6, 200)
        bar_h = 6
        bar_x = center_x - bar_w / 2
        bar_y = center_y + 72
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E1DFDD"))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * self._confidence, bar_h), 3, 3)

    @staticmethod
    def _draw_text(
        p: QPainter,
        rect: QRectF,
        text: str,
        color: QColor,
        size: int = 16,
        bold: bool = False,
    ) -> None:
        font = QFont("Microsoft YaHei", size, QFont.Bold if bold else QFont.Normal)
        p.setFont(font)
        p.setPen(color)
        p.drawText(rect, Qt.AlignCenter, text)


class StimulusArea(QWidget):
    """Displays the MI cue with optional GIF / video media overlays."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._custom_media: dict[str, str] = {"left": "", "right": ""}
        self._movie: Optional[QMovie] = None
        self._media_player: Optional[QMediaPlayer] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack_host = QWidget(self)
        self._stack = QStackedLayout(self._stack_host)
        self._stack.setContentsMargins(0, 0, 0, 0)

        self._canvas = _Canvas(self._stack_host)
        self._stack.addWidget(self._canvas)

        self._gif_label = QLabel(self._stack_host)
        self._gif_label.setAlignment(Qt.AlignCenter)
        self._gif_label.setMinimumSize(160, 160)
        self._gif_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._stack.addWidget(self._gif_label)

        self._video_widget: Optional[QVideoWidget]
        if _HAS_VIDEO:
            self._video_widget = QVideoWidget(self._stack_host)
            self._video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._stack.addWidget(self._video_widget)
            self._media_player = QMediaPlayer(self)
            self._media_player.setVideoOutput(self._video_widget)
            self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)
            self._media_player.error.connect(self._on_media_error)
        else:
            self._video_widget = None

        root.addWidget(self._stack_host, stretch=1)
        self.show_fix()

    def set_cue_media(self, *, left_path: str = "", right_path: str = "") -> None:
        self._custom_media["left"] = left_path.strip()
        self._custom_media["right"] = right_path.strip()

    def cue_media_path(self, intent: str) -> str:
        return self._custom_media.get(intent, "")

    def show_fix(self) -> None:
        self._stop_media()
        self._canvas.set_state(_Canvas.FIX)
        self._stack.setCurrentWidget(self._canvas)

    def show_prompt(self, intent: str) -> None:
        self._stop_media()
        state = _Canvas.LEFT if intent == "left" else _Canvas.RIGHT
        self._canvas.set_state(state)
        self._stack.setCurrentWidget(self._canvas)

    def show_cue(self, intent: str) -> None:
        self.show_prompt(intent)
        media_path = self._resolve_media_path(intent)
        if media_path is not None and self._show_media(media_path):
            return

        self._stack.setCurrentWidget(self._canvas)

    def show_rest(self) -> None:
        self._stop_media()
        self._canvas.set_state(_Canvas.REST)
        self._stack.setCurrentWidget(self._canvas)

    def show_result(self, predicted: str, confidence: float) -> None:
        self._stop_media()
        self._canvas.set_state(_Canvas.RESULT, result_label=predicted, confidence=confidence)
        self._stack.setCurrentWidget(self._canvas)

    def _resolve_media_path(self, intent: str) -> Path | None:
        custom = self._custom_media.get(intent, "")
        if custom:
            path = Path(custom)
            if path.exists() and path.is_file():
                return path
            return None

        default_name = "left_hand_grasp.gif" if intent == "left" else "right_hand_grasp.gif"
        default_path = _ASSET_DIR / default_name
        if default_path.exists():
            return default_path
        return None

    def _show_media(self, media_path: Path) -> bool:
        ext = media_path.suffix.lower()
        if ext == ".gif":
            movie = QMovie(str(media_path))
            if not movie.isValid():
                movie.deleteLater()
                return False
            self._movie = movie
            self._gif_label.setMovie(movie)
            movie.start()
            self._stack.setCurrentWidget(self._gif_label)
            return True

        if ext in _VIDEO_EXTENSIONS and _HAS_VIDEO and self._media_player is not None and self._video_widget is not None:
            self._media_player.setMedia(QMediaContent(QUrl.fromLocalFile(str(media_path))))
            self._media_player.play()
            self._stack.setCurrentWidget(self._video_widget)
            return True

        return False

    def _stop_media(self) -> None:
        if self._movie is not None:
            self._movie.stop()
            self._gif_label.clear()
            self._movie.deleteLater()
            self._movie = None

        if self._media_player is not None:
            self._media_player.stop()
            self._media_player.setMedia(QMediaContent())

    def _on_media_status_changed(self, status: int) -> None:
        if self._media_player is None:
            return
        if status == QMediaPlayer.EndOfMedia:
            self._media_player.setPosition(0)
            self._media_player.play()

    def _on_media_error(self, error: int) -> None:
        del error
        self._stop_media()
        self._stack.setCurrentWidget(self._canvas)
