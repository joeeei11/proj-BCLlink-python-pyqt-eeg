from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt5")

from neuropilot.ui.widgets.stimulus_area import StimulusArea, _Canvas


@pytest.mark.qt
def test_show_cue_falls_back_to_arrow_state_when_video_errors(qtbot, tmp_path: Path):
    area = StimulusArea()
    qtbot.addWidget(area)

    custom_video = tmp_path / "left.mp4"
    custom_video.write_bytes(b"fake-mp4")
    area.set_cue_media(left_path=str(custom_video))

    area.show_fix()
    area.show_cue("left")

    assert area._canvas._state == _Canvas.LEFT

    area._on_media_error(1)

    assert area._stack.currentWidget() is area._canvas
    assert area._canvas._state == _Canvas.LEFT
