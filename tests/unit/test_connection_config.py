"""单元测试：connection_config — EEGConnectionConfig / DeviceConnectionConfig"""
from __future__ import annotations

import pytest

from neuropilot.app.connection_config import DeviceConnectionConfig, EEGConnectionConfig


class TestEEGConnectionConfig:
    def test_defaults(self):
        cfg = EEGConnectionConfig()
        assert cfg.transport == "demo"
        assert cfg.channels == 8
        assert cfg.srate == 250.0

    def test_from_key_params_demo(self):
        cfg = EEGConnectionConfig.from_key_params("demo", {"n_channels": 16, "srate": 500.0})
        assert cfg.transport == "demo"
        assert cfg.channels == 16
        assert cfg.srate == 500.0

    def test_from_key_params_synthetic(self):
        cfg = EEGConnectionConfig.from_key_params("synthetic", {"n_channels": 4, "srate": 128.0})
        assert cfg.transport == "synthetic"
        assert cfg.channels == 4
        assert cfg.srate == 128.0

    def test_from_key_params_serial(self):
        cfg = EEGConnectionConfig.from_key_params("serial", {"port": "COM5", "baud": 9600})
        assert cfg.transport == "serial"
        assert cfg.serial_port == "COM5"
        assert cfg.serial_baud == 9600

    def test_from_key_params_tcp(self):
        cfg = EEGConnectionConfig.from_key_params("tcp", {"host": "10.0.0.1", "port": 8080})
        assert cfg.tcp_host == "10.0.0.1"
        assert cfg.tcp_port == 8080

    def test_from_key_params_playback(self):
        cfg = EEGConnectionConfig.from_key_params("playback", {"file": "/tmp/eeg.csv"})
        assert cfg.transport == "playback"
        assert cfg.playback_file == "/tmp/eeg.csv"

    def test_build_transport_demo(self):
        cfg = EEGConnectionConfig(transport="demo", channels=4, srate=100.0)
        t = cfg.build_transport()
        from neuropilot.domain.eeg.transports.demo import DemoTransport
        assert isinstance(t, DemoTransport)
        assert t.n_channels == 4
        assert t.srate == 100.0

    def test_build_transport_synthetic(self):
        cfg = EEGConnectionConfig(transport="synthetic", channels=8, srate=250.0)
        t = cfg.build_transport()
        from neuropilot.domain.eeg.transports.synthetic_tp import SyntheticTransport
        assert isinstance(t, SyntheticTransport)
        assert t.n_channels == 8

    def test_build_transport_playback(self):
        cfg = EEGConnectionConfig(transport="playback", playback_file="")
        t = cfg.build_transport()
        from neuropilot.domain.eeg.transports.playback_tp import PlaybackTransport
        assert isinstance(t, PlaybackTransport)

    def test_build_transport_unknown_raises(self):
        cfg = EEGConnectionConfig(transport="unknown_xyz")
        with pytest.raises(ValueError, match="未知 EEG 传输协议"):
            cfg.build_transport()

    def test_from_app_settings(self):
        class FakeCfg:
            eeg_transport = "synthetic"
            eeg_channels = 16
            eeg_sample_rate = 512
            eeg_playback_file = "/tmp/default-playback.csv"
            eeg_serial_port = "COM3"
            eeg_serial_baud = 115200
            eeg_bluetooth_address = ""
            eeg_bluetooth_port = 1
            eeg_tcp_host = "127.0.0.1"
            eeg_tcp_port = 4000
            eeg_udp_host = "0.0.0.0"
            eeg_udp_port = 4001
            eeg_lsl_stream_name = "Test"

        cfg = EEGConnectionConfig.from_app_settings(FakeCfg())
        assert cfg.transport == "synthetic"
        assert cfg.channels == 16
        assert cfg.srate == 512.0
        assert cfg.playback_file == "/tmp/default-playback.csv"


class TestDeviceConnectionConfig:
    def test_defaults(self):
        cfg = DeviceConnectionConfig()
        assert cfg.transport == "serial"

    def test_from_key_params_serial(self):
        cfg = DeviceConnectionConfig.from_key_params("serial", {"port": "COM6", "baud": 115200})
        assert cfg.serial_port == "COM6"
        assert cfg.serial_baud == 115200

    def test_from_key_params_tcp(self):
        cfg = DeviceConnectionConfig.from_key_params("tcp", {"host": "192.168.0.1", "port": 5001})
        assert cfg.tcp_host == "192.168.0.1"
        assert cfg.tcp_port == 5001

    def test_build_transport_unknown_raises(self):
        cfg = DeviceConnectionConfig(transport="lsl")
        with pytest.raises(ValueError, match="未知外设传输协议"):
            cfg.build_transport()
