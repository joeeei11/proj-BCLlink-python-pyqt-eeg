from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    # Auth
    user_logged_in = pyqtSignal(object)
    user_logged_out = pyqtSignal()

    # Subjects
    subject_selected = pyqtSignal(object)
    subject_changed = pyqtSignal()

    # EEG acquisition
    eeg_connect_requested = pyqtSignal(str, object)
    eeg_disconnect_requested = pyqtSignal()
    eeg_connected = pyqtSignal(bool, str)
    eeg_disconnected = pyqtSignal()
    eeg_session_started = pyqtSignal(int, int, float)   # session_id, n_channels, srate
    eeg_samples = pyqtSignal(object)
    eeg_error = pyqtSignal(str)
    eeg_traffic = pyqtSignal(str, object)

    # Device control
    device_connect_requested = pyqtSignal(str, object)
    device_disconnect_requested = pyqtSignal()
    device_send_raw = pyqtSignal(bytes)
    device_send_command = pyqtSignal(object)
    device_connected = pyqtSignal(bool, str)
    device_disconnected = pyqtSignal()
    device_error = pyqtSignal(str)
    device_traffic = pyqtSignal(str, object)

    # Paradigm
    paradigm_state_changed = pyqtSignal(str, int, int)
    paradigm_trial_opened = pyqtSignal(str, str)
    paradigm_trial_closed = pyqtSignal(str)
    prediction_result = pyqtSignal(str, float)
    paradigm_start_requested = pyqtSignal(object)
    paradigm_abort_requested = pyqtSignal()

    # ML
    ml_start_training = pyqtSignal(object)
    ml_cancel_training = pyqtSignal()
    ml_activate_model = pyqtSignal()
    ml_train_requested = pyqtSignal(int, str)
    ml_train_done = pyqtSignal(object)
    ml_train_failed = pyqtSignal(str)

    _instance: "EventBus | None" = None

    @classmethod
    def instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
