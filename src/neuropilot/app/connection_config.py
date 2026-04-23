from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EEGConnectionConfig:
    """EEG 连接参数统一模型（参考 brainflow BrainFlowInputParams）.

    所有 transport 所需参数集中在此，通过 build_transport() 构造实际传输对象。
    """

    transport: str = "demo"
    channels: int = 8
    srate: float = 250.0
    # serial
    serial_port: str = ""
    serial_baud: int = 115200
    # bluetooth
    bt_address: str = ""
    bt_port: int = 1
    # tcp
    tcp_host: str = "127.0.0.1"
    tcp_port: int = 4000
    # udp
    udp_host: str = "0.0.0.0"
    udp_port: int = 4001
    # lsl
    lsl_stream_name: str = "NeuroPilot"
    # playback
    playback_file: str = ""

    @classmethod
    def from_app_settings(cls, cfg: object) -> "EEGConnectionConfig":
        """从 AppSettings 对象构造配置。"""
        return cls(
            transport=str(getattr(cfg, "eeg_transport", "demo")),
            channels=int(getattr(cfg, "eeg_channels", 8)),
            srate=float(getattr(cfg, "eeg_sample_rate", 250)),
            serial_port=str(getattr(cfg, "eeg_serial_port", "")),
            serial_baud=int(getattr(cfg, "eeg_serial_baud", 115200)),
            bt_address=str(getattr(cfg, "eeg_bluetooth_address", "")),
            bt_port=int(getattr(cfg, "eeg_bluetooth_port", 1)),
            tcp_host=str(getattr(cfg, "eeg_tcp_host", "127.0.0.1")),
            tcp_port=int(getattr(cfg, "eeg_tcp_port", 4000)),
            udp_host=str(getattr(cfg, "eeg_udp_host", "0.0.0.0")),
            udp_port=int(getattr(cfg, "eeg_udp_port", 4001)),
            lsl_stream_name=str(getattr(cfg, "eeg_lsl_stream_name", "NeuroPilot")),
            playback_file=str(getattr(cfg, "eeg_playback_file", "")),
        )

    @classmethod
    def from_key_params(cls, key: str, params: dict, cfg: object | None = None) -> "EEGConnectionConfig":
        """从 EventBus 的松散 dict 参数构造配置（兼容现有 UI 事件）。"""
        default_srate = float(getattr(cfg, "eeg_sample_rate", 250)) if cfg else 250.0
        default_ch = int(getattr(cfg, "eeg_channels", 8)) if cfg else 8
        instance = cls.from_app_settings(cfg) if cfg else cls()
        instance.transport = key
        if key == "demo":
            instance.srate = float(params.get("srate", default_srate))
            instance.channels = int(params.get("n_channels", default_ch))
        elif key == "synthetic":
            instance.srate = float(params.get("srate", default_srate))
            instance.channels = int(params.get("n_channels", default_ch))
        elif key == "playback":
            instance.playback_file = str(params.get("file", instance.playback_file))
            instance.srate = float(params.get("srate", default_srate))
            instance.channels = int(params.get("n_channels", default_ch))
        elif key == "serial":
            instance.serial_port = str(params.get("port", instance.serial_port))
            instance.serial_baud = int(params.get("baud", instance.serial_baud))
        elif key == "bluetooth":
            instance.bt_address = str(params.get("address", instance.bt_address))
            instance.bt_port = int(params.get("port", instance.bt_port))
        elif key == "tcp":
            instance.tcp_host = str(params.get("host", instance.tcp_host))
            instance.tcp_port = int(params.get("port", instance.tcp_port))
        elif key == "udp":
            instance.udp_host = str(params.get("host", instance.udp_host))
            instance.udp_port = int(params.get("port", instance.udp_port))
        elif key == "lsl":
            instance.lsl_stream_name = str(params.get("stream_name", instance.lsl_stream_name))
        return instance

    def build_transport(self):
        """根据 transport 字段构造对应的 IDeviceTransport 实例。"""
        key = self.transport
        if key == "demo":
            from neuropilot.domain.eeg.transports.demo import DemoTransport
            return DemoTransport(srate=self.srate, n_channels=self.channels)
        if key == "synthetic":
            from neuropilot.domain.eeg.transports.synthetic_tp import SyntheticTransport
            return SyntheticTransport(srate=self.srate, n_channels=self.channels)
        if key == "playback":
            from neuropilot.domain.eeg.transports.playback_tp import PlaybackTransport
            return PlaybackTransport(
                csv_path=self.playback_file,
                loop=True,
                srate_override=self.srate if self.srate else None,
            )
        if key == "serial":
            from neuropilot.domain.eeg.transports.serial_tp import SerialTransport
            return SerialTransport(
                port=self.serial_port, baud=self.serial_baud,
                srate=self.srate, n_channels=self.channels,
            )
        if key == "bluetooth":
            from neuropilot.domain.eeg.transports.bluetooth_tp import BluetoothTransport
            return BluetoothTransport(
                address=self.bt_address, port=self.bt_port,
                srate=self.srate, n_channels=self.channels,
            )
        if key == "tcp":
            from neuropilot.domain.eeg.transports.tcp_tp import TCPTransport
            return TCPTransport(
                host=self.tcp_host, port=self.tcp_port,
                srate=self.srate, n_channels=self.channels,
            )
        if key == "udp":
            from neuropilot.domain.eeg.transports.udp_tp import UDPTransport
            return UDPTransport(
                host=self.udp_host, port=self.udp_port,
                srate=self.srate, n_channels=self.channels,
            )
        if key == "lsl":
            from neuropilot.domain.eeg.transports.lsl_tp import LSLTransport
            return LSLTransport(
                stream_name=self.lsl_stream_name,
                srate=self.srate, n_channels=self.channels,
            )
        raise ValueError(f"未知 EEG 传输协议: {key!r}")


@dataclass
class DeviceConnectionConfig:
    """外设（假肢手/刺激器）连接参数统一模型。"""

    transport: str = "serial"
    serial_port: str = ""
    serial_baud: int = 9600
    bt_address: str = ""
    bt_port: int = 1
    tcp_host: str = "192.168.1.100"
    tcp_port: int = 5000
    udp_host: str = "192.168.1.100"
    udp_port: int = 5001

    @classmethod
    def from_app_settings(cls, cfg: object) -> "DeviceConnectionConfig":
        return cls(
            transport=str(getattr(cfg, "device_transport", "serial")),
            serial_port=str(getattr(cfg, "device_serial_port", "")),
            serial_baud=int(getattr(cfg, "device_serial_baud", 9600)),
            bt_address=str(getattr(cfg, "device_bluetooth_address", "")),
            bt_port=int(getattr(cfg, "device_bluetooth_port", 1)),
            tcp_host=str(getattr(cfg, "device_tcp_host", "192.168.1.100")),
            tcp_port=int(getattr(cfg, "device_tcp_port", 5000)),
            udp_host=str(getattr(cfg, "device_udp_host", "192.168.1.100")),
            udp_port=int(getattr(cfg, "device_udp_port", 5001)),
        )

    @classmethod
    def from_key_params(cls, key: str, params: dict, cfg: object | None = None) -> "DeviceConnectionConfig":
        instance = cls.from_app_settings(cfg) if cfg else cls()
        instance.transport = key
        if key == "serial":
            instance.serial_port = str(params.get("port", instance.serial_port))
            instance.serial_baud = int(params.get("baud", instance.serial_baud))
        elif key == "bluetooth":
            instance.bt_address = str(params.get("address", instance.bt_address))
            instance.bt_port = int(params.get("port", instance.bt_port))
        elif key == "tcp":
            instance.tcp_host = str(params.get("host", instance.tcp_host))
            instance.tcp_port = int(params.get("port", instance.tcp_port))
        elif key == "udp":
            instance.udp_host = str(params.get("host", instance.udp_host))
            instance.udp_port = int(params.get("port", instance.udp_port))
        return instance

    def build_transport(self):
        """构造外设 IDeviceTransport 实例。"""
        key = self.transport
        if key == "serial":
            from neuropilot.domain.eeg.transports.serial_tp import SerialTransport
            return SerialTransport(
                port=self.serial_port, baud=self.serial_baud, srate=0.0, n_channels=0,
            )
        if key == "bluetooth":
            from neuropilot.domain.eeg.transports.bluetooth_tp import BluetoothTransport
            return BluetoothTransport(
                address=self.bt_address, port=self.bt_port, srate=0.0, n_channels=0,
            )
        if key == "tcp":
            from neuropilot.domain.eeg.transports.tcp_tp import TCPTransport
            return TCPTransport(
                host=self.tcp_host, port=self.tcp_port, srate=0.0, n_channels=0,
            )
        if key == "udp":
            from neuropilot.domain.eeg.transports.udp_tp import UDPTransport
            return UDPTransport(
                host=self.udp_host, port=self.udp_port, srate=0.0, n_channels=0,
            )
        raise ValueError(f"未知外设传输协议: {key!r}")
