---
# Phase 4：外设控制与设备调试统一

## 目标
外设（机械手/刺激器）复用 Phase 3 的 `IDeviceTransport`；`DeviceService` 发送安全、可观测；调试控制台双通道（Device/EEG）实时流量监控与指令下发可用。

## 前置条件
- Phase 3 已完成：`IDeviceTransport` + 6 策略稳定
- EEG 采集能产生实时数据（Dashboard 能看到波形）

## 任务清单
- [ ] 任务 1：`domain/device/device_service.py`：
  - 复用 `IDeviceTransport`（Serial/Bluetooth/TCP/UDP 四种子集）
  - `send(payload: bytes, *, min_interval_ms=150)`：`time.monotonic()` 节流，替代旧版 `QTimer.singleShot + setattr` 的脆弱写法
  - `is_connected` 缓存 + 事件 `sig_connection_changed`
- [ ] 任务 2：`ui/pages/device_page.py`（新）：模式选择与 EEG 页共用枚举；未连接时所有"发送"按钮自动置灰
- [ ] 任务 3：`domain/device/commands.py`：定义 `DeviceCommand` 枚举（LEFT/RIGHT/TRIGGER_START/TRIGGER_END/CUSTOM）+ 统一 byte 映射；UI 不再拼 `b'L\n'`
- [ ] 任务 4：`ui/pages/debug_page.py`（新）：
  - 订阅 `AcquisitionWorker.sig_traffic` 与 `DeviceService.sig_traffic`
  - `QPlainTextEdit.document().setMaximumBlockCount(1000)` 限制行数
  - HEX/ASCII 切换不再使用 Py2 `string_escape`；实现 `\n/\r/\t/\xHH` 正确转义
  - 发送按钮 → `DeviceService.send`
- [ ] 任务 5：`app/session_manager.py`：外设断开事件触发时自动关 `auto_send` 并弹 `InfoBar.warning`
- [ ] 任务 6：Task 页的"自动发送"开关改为订阅 `DeviceService.is_connected` 响应式更新；断开时禁用（消除静默失败）
- [ ] 任务 7：测试：
  - `tests/unit/test_device_service.py`：节流（150 ms 内第二次发送拒绝）
  - `tests/unit/test_device_command.py`：枚举映射
  - `tests/ui/test_debug_page.py`：HEX 发送 `4C 0A` 经 mock transport 收到 `b'L\n'`

## 验收标准
- [ ] 外设页 Serial 模式能连上（USB 虚拟串口或 `socat`）并收发；未连接时"发送"按钮置灰
- [ ] Debug 页长跑 10 min 内存 < 150 MB
- [ ] Task 页在外设断开时自动关 auto_send 并显示警示
- [ ] `pytest -q` 全绿
- [ ] EEG 与 Device 的 `transports/` 无重复代码（`radon cc` / `jscpd` 复审）

## 注意事项
- 节流只用 `time.monotonic()`，不要用 wall clock
- `setMaximumBlockCount` 是关键 API，不要自行数行清理
- 发送前 `is_connected=False` 直接返回 `(False, "未连接")`，不让 transport 抛异常
- `DeviceCommand.CUSTOM(bytes)` 用于 Debug 页的任意 payload
- EEG 与 Device 的日志颜色保持区分：Device TX=青 / RX=粉；EEG INFO=蓝 / RX=绿
---
