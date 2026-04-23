"""Minimal fake TCP server for testing TCPTransport.

Usage (standalone):
    python tests/tools/tcp_fake_server.py --port 14000 --n-channels 4 --srate 250

Usage (programmatic):
    server = FakeTCPServer(port=0, n_channels=4, srate=250.0)
    server.start()
    port = server.port   # get the OS-assigned port
    ...
    server.stop()
"""
from __future__ import annotations

import socket
import struct
import threading
import time
import argparse
import numpy as np


class FakeTCPServer(threading.Thread):
    """Streams float32 EEG frames to the first connecting client."""

    def __init__(
        self,
        port: int = 0,
        n_channels: int = 4,
        srate: float = 250.0,
        chunk_size: int = 25,
    ) -> None:
        super().__init__(daemon=True)
        self._n_ch = n_channels
        self._srate = srate
        self._chunk = chunk_size
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", port))
        self._srv.listen(1)
        self._port: int = self._srv.getsockname()[1]
        self._stop_evt = threading.Event()

    @property
    def port(self) -> int:
        return self._port

    def stop(self) -> None:
        self._stop_evt.set()
        try:
            self._srv.close()
        except Exception:
            pass

    def run(self) -> None:
        self._srv.settimeout(2.0)
        try:
            conn, _ = self._srv.accept()
        except Exception:
            return

        chunk_dur = self._chunk / self._srate
        idx = 0
        try:
            while not self._stop_evt.is_set():
                t = np.arange(idx, idx + self._chunk) / self._srate
                data = np.zeros((self._chunk, self._n_ch), dtype=np.float32)
                for ch in range(self._n_ch):
                    data[:, ch] = 50.0 * np.sin(2 * np.pi * 10 * t + ch * 0.5)
                payload = data.tobytes()
                try:
                    conn.sendall(payload)
                except Exception:
                    break
                idx += self._chunk
                time.sleep(chunk_dur)
        finally:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=14000)
    parser.add_argument("--n-channels", type=int, default=4)
    parser.add_argument("--srate", type=float, default=250.0)
    args = parser.parse_args()

    srv = FakeTCPServer(port=args.port, n_channels=args.n_channels, srate=args.srate)
    srv.start()
    print(f"Fake TCP server running on port {srv.port}. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.stop()
