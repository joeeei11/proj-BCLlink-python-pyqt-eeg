from __future__ import annotations

import pytest

pytest.importorskip("PyQt5")

from neuropilot.ui.widgets.stimulus_area import StimulusArea, _Canvas


@pytest.mark.qt
def test_prompt_phase_always_uses_arrow_canvas(qtbot):
    area = StimulusArea()
    qtbot.addWidget(area)

    area.show_prompt("right")

    assert area._stack.currentWidget() is area._canvas
    assert area._canvas._state == _Canvas.RIGHT


@pytest.mark.qt
def test_invalid_custom_media_does_not_fall_back_to_builtin_gif(qtbot):
    area = StimulusArea()
    qtbot.addWidget(area)

    area.set_cue_media(right_path=r"D:\nonexistent\custom_right.mp4")

    assert area._resolve_media_path("right") is None
