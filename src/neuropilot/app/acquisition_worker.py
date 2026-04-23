from __future__ import annotations

import select
import socket
import threading
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

from neuropilot.app.eeg_record_service import EEGRecordService
from neuropilot.app.eeg_session_coordinator import EEGSessionCoordinator
from neuropilot.app.transport_connect import ConnectCancelledError, open_transport_with_cancel
from neuropilot.domain.eeg.acquisition_service import AcquisitionService
from neuropilot.domain.eeg.transports.base import IDeviceTransport, TransportError


class AcquisitionWorker(QThread):
    """Qt 线程桥接层 — 只负责线程包装和信号转发.

    业务职责已下沉至：
    - AcquisitionService (domain): 连接/读取抽象（参考 neurodecode StreamReceiver）
    - EEGRecordService: CSV 落盘（参考 neurodecode StreamRecorder）
    - EEGSessionCoordinator: session DB 生命周期
    """

    sig_connected = pyqtSignal(bool, str)
    sig_samples = pyqtSignal(object)
    sig_error = pyqtSignal(str)
    sig_traffic = pyqtSignal(str, object)

    def __init__(
        self,
        transport: IDeviceTransport,
        session_coordinator: EEGSessionCoordinator,
        record_service: EEGRecordService,
        subject_id: int,
        user_id: int,
        transport_name: str = "demo",
        parent: object = None,
    ) -> None:
        super().__init__(parent)  # type: ignore[call-arg]
        self._transport = transport
        self._acq_service = AcquisitionService(transport)
        self._coordinator = session_coordinator
        self._recorder = record_service
        self._subject_id = subject_id
        self._user_id = user_id
        self._transport_name = transport_name
        self._r_pipe, self._w_pipe = socket.socketpair()
        self._cancel_event = threading.Event()

    @property
    def session_id(self) -> Optional[int]:
        return self._coordinator.session_id

    @property
    def csv_path(self) -> Optional[Path]:
        return self._recorder.csv_path

    def stop(self) -> None:
        self._cancel_event.set()
        self._safe_disconnect()
        try:
            self._w_pipe.send(b"\x00")
        except Exception:
            pass

    def run(self) -> None:
        from loguru import logger

        try:
            # open_transport_with_cancel 负责可取消的连接等待
            open_transport_with_cancel(self._transport, self._cancel_event, total_timeout=5.0)
            if self._cancel_event.is_set():
                raise ConnectCancelledError("连接已取消")
            session_id = self._coordinator.create(
                subject_id=self._subject_id,
                user_id=self._user_id,
                transport=self._transport_name,
                n_channels=self._acq_service.n_channels,
                srate=self._acq_service.srate,
            )
        except ConnectCancelledError as exc:
            self.sig_connected.emit(False, str(exc))
            self._safe_disconnect()
            self._close_pipe()
            return
        except Exception as exc:
            self.sig_connected.emit(False, str(exc))
            self._safe_disconnect()
            self._close_pipe()
            return

        self.sig_connected.emit(True, self._transport_name)
        logger.info(
            "EEG 已连接: {} {}ch @ {}Hz (session={})",
            self._transport_name,
            self._acq_service.n_channels,
            self._acq_service.srate,
            session_id,
        )

        self._recorder.start(
            subject_id=self._subject_id,
            session_id=session_id,
            n_channels=self._acq_service.n_channels,
            srate=self._acq_service.srate,
        )

        flush_interval = max(1, int(self._acq_service.srate))

        try:
            while True:
                ready, _, _ = select.select([self._r_pipe], [], [], 0.05)
                if ready:
                    self._r_pipe.recv(1)
                    break

                try:
                    # 通过 domain 层 AcquisitionService 读取，不直接调 transport
                    data = self._acq_service.read_once(timeout=0.0)
                except TransportError as exc:
                    self.sig_error.emit(str(exc))
                    break

                if data is None or len(data) == 0:
                    continue

                self.sig_samples.emit(data)
                total = self._recorder.write_chunk(data)
                if total % flush_interval == 0:
                    self.sig_traffic.emit("csv_rows", total)

        except Exception as exc:
            self.sig_error.emit(str(exc))
            logger.exception("AcquisitionWorker 错误: {}", exc)
        finally:
            self._recorder.stop()
            self._coordinator.stop()
            self._safe_disconnect()
            self._close_pipe()
            logger.info("EEG 采集停止. 总样本: {}", self._recorder.sample_count)

    def _safe_disconnect(self) -> None:
        try:
            self._acq_service.disconnect()
        except Exception:
            pass

    def _close_pipe(self) -> None:
        for sock in (self._r_pipe, self._w_pipe):
            try:
                sock.close()
            except Exception:
                pass
