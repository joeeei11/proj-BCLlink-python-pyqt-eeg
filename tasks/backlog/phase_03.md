---
# Phase 3：EEG 采集与传输层统一

## 目标
完成 `IDeviceTransport` 抽象 + 六种策略实现（Demo/Serial/Bluetooth/TCP/UDP/LSL）；`AcquisitionService` 以独立线程稳定采集，可即时中断不泄漏；原始数据按 Session 落盘到 `data/raw_eeg/`。

## 前置条件
- Phase 2 已完成：用户登录后可选 subject
- 数据库 `sessions` 表可写

## 任务清单
- [ ] 任务 1：`domain/eeg/transports/base.py`：抽象类 `IDeviceTransport`（`open() / close() / read() -> np.ndarray | None / is_open`），属性 `srate`、`n_channels`
- [ ] 任务 2：实现 6 个策略：
  - `demo.py`：按 srate 节拍生成可控正弦波 + 噪声（替代旧 50 Hz 错拍 bug）
  - `serial_tp.py`：ASCII CSV 逐行解析，含 readline 超时
  - `bluetooth_tp.py`：pybluez2 RFCOMM；缺依赖时 `open()` 抛 `DependencyMissingError`
  - `tcp_tp.py`：握手 + `select` 可唤醒；修复旧版 setblocking 翻转 bug
  - `udp_tp.py`：可选 magic header 校验；不对齐丢包并记日志
  - `lsl_tp.py`：`resolve_byprop('type','EEG',timeout=5)`；从流覆盖 srate/n_channels
- [ ] 任务 3：`domain/eeg/ring_buffer.py`：从旧实现迁移并修复 `get_last(n)` 在未满且 `idx<n` 时返回 None 的问题，改返回可用长度
- [ ] 任务 4：`app/acquisition_worker.py`（Qt 适配层）：
  - 独立 `QThread` 包装 `AcquisitionService`
  - `socket.socketpair()` 自唤醒管道实现 `stop()` 即时返回
  - 启动时 `session_repo.create()`；停止时写 `ended_at`
  - 原始 CSV 落 `data/raw_eeg/{subject}_{session_id}_{ts}.csv`（`encoding='utf-8'`；按 1s 批 flush）
  - 信号：`sig_connected(bool,str) / sig_samples(np.ndarray) / sig_error(str) / sig_traffic(str, Any)`
- [ ] 任务 5：`ui/pages/eeg_page.py`（新）：
  - UI 不含业务逻辑；订阅/发射 event_bus
  - 模式 ComboBox 统一 6 项
  - 断开按钮调用 `stop()`，<300 ms 返回
- [ ] 任务 6：Dashboard 接入实时波形：通过 event_bus 订阅 samples；pyqtgraph 渲染；垂直缩放范围限制为 1–500 uV
- [ ] 任务 7：测试：
  - `tests/integration/test_acquisition_demo.py`：demo transport → 100 ms 后 stop → 断言 stop < 300 ms 且 ≥ 1 次 samples 事件
  - `tests/unit/test_ring_buffer.py`：首次写入未满、跨界回绕、超长 chunk
  - `tests/integration/test_tcp_transport.py`：用 `tests/tools/tcp_fake_server.py` 造对端

## 验收标准
- [ ] 启动 → 登录 → 选 subject → EEG 页选"演示模式" → 连接 → Dashboard 出现 10 Hz 正弦波，FPS 稳定 > 25
- [ ] 连接 TCP（用 fake_server）收包/写文件/断开均正常；断开按钮 300 ms 内恢复
- [ ] 原始 CSV 生成于 `data/raw_eeg/`，首行 `time,CH1..CHn`，n 与 transport 一致
- [ ] `sessions` 表有对应行，`started_at/ended_at/n_channels/srate` 正确
- [ ] 任一 transport 缺依赖时 UI 明确提示，不崩溃
- [ ] `pytest -q tests/unit tests/integration` 全绿
- [ ] `ruff` / `mypy src/neuropilot/domain` 无错

## 注意事项
- `domain/` 内**禁止** `import PyQt5`；Qt 适配放 `app/acquisition_worker.py`
- `sock.setblocking()` 反复切换是旧版 bug 来源；一律用 `select()` + 非阻塞
- `pylsl.resolve_byprop` 替代已废弃的 `resolve_stream`
- UDP 首包做长度对齐校验（`len % (4*n_ch) == 0`），不对齐直接丢
- 写 CSV 不要每样本 flush；按 1 秒或 N 行批量 flush
- 线程退出时必须 `close_stream()` + `sock.close()` + 关闭 CSV
---
