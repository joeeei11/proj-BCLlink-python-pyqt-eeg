from __future__ import annotations

import pytest

pytest.importorskip("PyQt5")

from neuropilot.ui.pages.task_page import TaskPage


@pytest.mark.qt
def test_task_page_uses_arrow_for_cue_and_media_for_imagery(qtbot):
    page = TaskPage()
    qtbot.addWidget(page)

    calls: list[tuple[str, object | None]] = []

    original_show_fix = page._stimulus.show_fix
    original_show_prompt = page._stimulus.show_prompt
    original_show_cue = page._stimulus.show_cue
    original_show_rest = page._stimulus.show_rest

    page._stimulus.show_fix = lambda: calls.append(("fix", None))  # type: ignore[method-assign]
    page._stimulus.show_prompt = lambda intent: calls.append(("prompt", intent))  # type: ignore[method-assign]
    page._stimulus.show_cue = lambda intent: calls.append(("cue", intent))  # type: ignore[method-assign]
    page._stimulus.show_rest = lambda: calls.append(("rest", None))  # type: ignore[method-assign]

    try:
        page._on_state_changed("FIX", 1, 4)
        page._on_trial_opened("trial-1", "left")
        page._on_state_changed("CUE", 1, 4)
        page._on_state_changed("IMAG", 1, 4)
        page._on_state_changed("REST", 1, 4)
        page._on_trial_closed("trial-1")
        page._on_state_changed("DONE", 4, 4)
    finally:
        page._stimulus.show_fix = original_show_fix  # type: ignore[method-assign]
        page._stimulus.show_prompt = original_show_prompt  # type: ignore[method-assign]
        page._stimulus.show_cue = original_show_cue  # type: ignore[method-assign]
        page._stimulus.show_rest = original_show_rest  # type: ignore[method-assign]

    assert calls == [
        ("fix", None),
        ("prompt", "left"),
        ("prompt", "left"),
        ("cue", "left"),
        ("rest", None),
    ]
    assert page._current_intent is None
