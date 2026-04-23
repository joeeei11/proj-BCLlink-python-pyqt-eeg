from __future__ import annotations

import pytest

pytest.importorskip("PyQt5")

from neuropilot.ui.widgets.status_panel import StatusPanel


@pytest.mark.qt
def test_disconnect_resets_runtime_state(qtbot):
    panel = StatusPanel()
    qtbot.addWidget(panel)

    panel._on_eeg_connected(True, "playback")
    panel._on_session_started(42, 8, 250.0)
    panel._on_eeg_traffic("csv_rows", 128)

    panel._on_eeg_disconnected()

    assert panel._lbl_status.text() == "未连接"
    assert panel._lbl_transport.text() == "-"
    assert panel._lbl_source.text() == "-"
    assert panel._lbl_session.text() == "-"
    assert panel._lbl_channels.text() == "-"
    assert panel._lbl_srate.text() == "-"
    assert panel._lbl_samples.text() == "0"
    assert panel._lbl_recording.text() == "未录制"
