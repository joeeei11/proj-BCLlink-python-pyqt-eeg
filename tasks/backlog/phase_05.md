---
# Phase 5：范式引擎与试次记录

## 目标
用显式有限状态机替换旧版 4 个 `QTimer.singleShot` 串联；`TrialRecorder` 按 trial_uuid 聚合事件，数据落 `trials` 表无串扰；范式预设可保存。

## 前置条件
- Phase 3/4 已完成：EEG 采集、外设发送稳定
- `sessions` 表写入正常

## 任务清单
- [ ] 任务 1：`app/paradigm_engine.py`：
  - 状态：`IDLE → FIX → CUE → IMAG → REST → ITI → (loop | DONE)`
  - 单个 `QTimer` 驱动，`abort()` 立即回 IDLE，过期 timer 不再影响状态机
  - 信号：`sig_state_changed(state, trial_index, total)`、`sig_trial_opened(uuid, intent)`、`sig_trial_closed(uuid)`
- [ ] 任务 2：`app/trial_recorder.py`：
  - `open(uuid, intent, timing) → TrialDraft`
  - `record_prediction(uuid, pred, conf)` / `record_device_send(uuid, ok, msg)`
  - `close(uuid)` 写入 `trials` 表
  - 超 5 s 未 close 的 draft 自动 flush，`predicted_label='unknown'`
  - 全部操作加 `threading.Lock`
- [ ] 任务 3：`ui/widgets/stage_bar.py`（新）：取代旧 `FluentStageBar`；`highlight(idx)` 每次显式重置所有 badge 到 `INFORMATION`，只高亮当前
- [ ] 任务 4：`ui/widgets/stimulus_area.py`：迁移旧 `StimulusArea`；默认 `show_fix()`（不再是"休息"）；GIF 丢失回退为文字提示
- [ ] 任务 5：`ui/pages/task_page.py`（新）：
  - 左侧参数面板用 `ParadigmConfig` Pydantic 双向绑定
  - 参数预设：保存/加载/删除，存 `config/local.toml`（原子写）
  - CSV 导出从 `trials` 表按 session_id 查询，不再维护 UI 侧 `_records`
- [ ] 任务 6：范式联动：
  - 进入 `CUE`：`device.send(TRIGGER_START)` + 通知 EEG `begin_trial(uuid, intent)`
  - 进入 `REST`：EEG `end_trial(uuid)` 返回预测/置信 → `TrialRecorder.record_prediction`
  - `DeviceService.sig_send_result` → `TrialRecorder.record_device_send`
- [ ] 任务 7：Dashboard 订阅 `paradigm_engine.sig_state_changed` 同步 badge 与进度条
- [ ] 任务 8：测试：
  - `tests/unit/test_paradigm_engine.py`：状态跳转、abort 不触发过期事件、循环次数
  - `tests/unit/test_trial_recorder.py`：交错事件匹配、孤儿 flush
  - `tests/integration/test_task_flow.py`：demo + mock device 跑 3 循环，`trials` 表有 3 行

## 验收标准
- [ ] 循环 10 次无试次丢失/重复；中止按钮按下 100 ms 内 timer 全停
- [ ] `trials` 表每行 `predicted_label / device_send_ok / session_id / trial_index` 对齐
- [ ] 阶段徽章颜色不再累积
- [ ] 范式预设保存后重启仍可加载
- [ ] 导出 CSV 行数 == `trials` 表对应 session 行数
- [ ] `pytest -q tests/unit tests/integration` 全绿

## 注意事项
- `QTimer.singleShot` 可用，但必须由 `ParadigmEngine` 独占；UI 不再排 timer
- `TrialRecorder` 的孤儿 flush 在 session stop 时 cancel
- 预设保存用"写临时文件 + `os.replace`"原子写
- 状态机信号发射放 `QTimer.singleShot(0, ...)` 下一 tick，避免 UI 槽内回改状态机
- `abort()` 应发一次 IDLE 状态变更，不多不少
---
