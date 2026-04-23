from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt5")

from neuropilot.app.event_bus import EventBus
from neuropilot.ui.pages.task_page import TaskPage
from neuropilot.ui.widgets.stimulus_area import StimulusArea


@pytest.mark.qt
def test_task_start_pushes_selected_media_to_stimulus(qtbot):
    page = TaskPage()
    qtbot.addWidget(page)

    page._left_media_edit.setText(r"D:\demo\left.gif")
    page._right_media_edit.setText(r"D:\demo\right.mp4")

    captured_media: list[tuple[str, str]] = []
    captured_config: list[dict] = []
    bus = EventBus.instance()
    slot = lambda config: captured_config.append(config)
    bus.paradigm_start_requested.connect(slot)

    original = page._stimulus.set_cue_media
    page._stimulus.set_cue_media = lambda *, left_path="", right_path="": captured_media.append((left_path, right_path))  # type: ignore[method-assign]

    try:
        page._on_start()
    finally:
        page._stimulus.set_cue_media = original  # type: ignore[method-assign]
        bus.paradigm_start_requested.disconnect(slot)

    assert captured_media == [(r"D:\demo\left.gif", r"D:\demo\right.mp4")]
    assert len(captured_config) == 1


@pytest.mark.qt
def test_stimulus_area_prefers_custom_media_path(qtbot, tmp_path: Path):
    area = StimulusArea()
    qtbot.addWidget(area)

    left_media = tmp_path / "left.gif"
    left_media.write_bytes(b"GIF89a")
    right_media = tmp_path / "right.mp4"
    right_media.write_bytes(b"fake-mp4")

    area.set_cue_media(left_path=str(left_media), right_path=str(right_media))

    assert area.cue_media_path("left") == str(left_media)
    assert area.cue_media_path("right") == str(right_media)
    assert area._resolve_media_path("left") == left_media
    assert area._resolve_media_path("right") == right_media
