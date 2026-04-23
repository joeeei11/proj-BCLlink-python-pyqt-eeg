# 技术决策记录

## [2026-04-21] 初始技术选型

### 基础技术栈
- **语言**：Python 3.10+（`match-case`、TypeAlias 需要）
- **GUI 框架**：PyQt5 5.15.x + PyQt-Fluent-Widgets ≥ 1.5（延续旧版选型，Fluent 视觉语言统一）
- **实时绘图**：pyqtgraph ≥ 0.13 为主，matplotlib ≥ 3.7 用于离线分析与导出
- **科学计算**：numpy ≥ 1.24 / scipy ≥ 1.10 / scikit-learn ≥ 1.3 / pandas ≥ 2.0
- **设备传输**：pyserial ≥ 3.5（必需）、pylsl ≥ 1.16 / pybluez2（可选依赖）
- **数据库**：SQLite + SQLAlchemy 2.0 Core，WAL 模式，单一库文件 `data/neuro_pilot.db`
- **配置**：pydantic-settings ≥ 2.0，分层读取 `config/default.toml` + `config/local.toml` + 环境变量
- **安全**：passlib[bcrypt] ≥ 1.7（登录密码哈希）、joblib + sha256（模型持久化校验）
- **日志**：loguru ≥ 0.7，替代零散 `logging.getLogger`，stdout + 轮转文件 + LogPanel sink
- **开发工具**：pytest 7.x + pytest-qt 4.x + ruff + mypy + pre-commit

### 选型理由
1. **保留 PyQt5 而非升级 PyQt6**：旧代码全量使用 PyQt5.QtCore/QtWidgets，升级成本高；qfluentwidgets 对 PyQt5 支持更成熟。
2. **SQLAlchemy Core 而非 ORM**：业务表不多（5 张），Core 更轻、性能更可控、迁移脚本更直观。
3. **loguru 取代 logging**：配置集中、自动 rotation、零样板代码。
4. **pydantic-settings**：强类型配置解析，解决旧版 `QSettings` bool/int 类型丢失问题。
5. **joblib + sha256 取代 pickle**：规避 pickle 反序列化代码执行风险；哈希校验保障模型完整性。

---

## [2026-04-21] D-001 分层架构：ui / app / domain / infra
- **背景**：旧版 UI 直接持有 DB 连接与 socket，单模块 400–900 行难维护与测试。
- **方案**：四层分离，`domain` 与 `infra` 严格不依赖 PyQt；UI 仅发射意图、渲染状态。
- **原因**：隔离 Qt 便于单测；后续可无痛加 FastAPI 远程层。
- **后果**：多一层 DTO 转换成本，可接受。

## [2026-04-21] D-002 单一 SQLite 库
- **背景**：旧版存在 `data.db`（subject_manager）、`data/neuro_pilot.db`（data_module）、`DataManager` 单例三处数据写入，同类数据分裂。
- **方案**：统一 `data/neuro_pilot.db`；一次性迁移脚本 `scripts/migrate_legacy_db.py` 合并旧库后 `.bak` 备份。
- **原因**：消除数据孤岛。
- **后果**：迁移脚本需幂等、可 dry-run。

## [2026-04-21] D-003 传输策略化（IDeviceTransport）
- **背景**：EEG 与外设两套独立连接栈，模式集合不一致（Serial/Bluetooth/WiFi vs Serial/Bluetooth/TCP/UDP/LSL）。
- **方案**：统一 `IDeviceTransport` 抽象 + 策略注册表；EEG 与 Device 共享。
- **原因**：减少维护面；新增传输模式只写一个类。
- **后果**：NeuSenW 等特殊协议作为子类特化。

## [2026-04-21] D-004 模型持久化：joblib + sha256
- **背景**：pickle 反序列化存在代码执行风险。
- **方案**：`joblib.dump` 写文件，`models` 表存 sha256 与元信息；加载前校验哈希。
- **原因**：安全 + 完整性校验。
- **后果**：模型文件被修改需重新入库。

## [2026-04-21] D-005 登录 bcrypt + 失败锁定
- **背景**：旧版 `admin/123456` 硬编码且在 UI 明文显示。
- **方案**：首次启动引导创建 admin；bcrypt 存储；5 次失败锁 10 min。
- **原因**：基础安全合规。
- **后果**：首次部署需运行 `scripts/seed_admin.py` 或走引导对话框。

## [2026-04-21] D-006 范式状态机取代定时器堆
- **背景**：旧版 `task_module.py` 用 4 个 `QTimer.singleShot` 串联四阶段，中止后仍可能触发残留 timer。
- **方案**：`ParadigmEngine` FSM（`IDLE → FIX → CUE → IMAG → REST → ITI → loop/DONE`），单定时器驱动。
- **原因**：可中止、可回放、可单测。
- **后果**：UI 不再排 timer，须订阅 engine 的状态变更信号。

## [2026-04-21] D-007 Trial 记录按 uuid 解耦
- **背景**：旧版 `_pending_trial` 单槽缓存，跨 trial 事件到达错序会互相覆盖。
- **方案**：`TrialRecorder` 维护 `dict[uuid, TrialDraft]`；子事件按 uuid 匹配；孤儿事件 5 s flush。
- **原因**：消除事件串扰。
- **后果**：Trial 生命周期必须显式 `open/close`。

## [2026-04-21] D-008 日志：loguru + LogPanel Sink
- **背景**：旧版 `logging.getLogger` 散落多处，LogPanel 无落盘。
- **方案**：`infra/logger.py` 集中初始化 loguru；stdout + rotation（10MB / 14d）+ 自定义 sink 写入 LogPanel。
- **原因**：配置集中、自动轮转、性能优。
- **后果**：需把旧 `logging` 调用迁到 `from loguru import logger`。

---

## [2026-04-21] D-009 config.toml 扁平化键名策略（Phase 1 实现发现）
- **背景**：pydantic-settings `__init__` kwargs 优先级高于 env var，若将 TOML 值直接传入构造函数则 env var 无法覆盖。
- **方案**：`load_settings` 手动过滤：已在环境变量中出现的键不传入 `AppSettings(**kwargs)`，让 pydantic-settings 自行从 env 读取；`config/default.toml` 的顶层字段（`env`、`theme`、`lock_threshold`、`lock_minutes`）不放在 `[section]` 下，展平后直接与字段名对齐。
- **原因**：保证 `NEUROPILOT_ENV=test` 等 CI 变量能正确覆盖文件配置。
- **后果**：TOML 结构与字段名需严格对应；新增字段时要同步更新 `config/default.toml`。

## [2026-04-21] D-010 SQLAlchemy session 生命周期：覆盖整个 Qt 运行时（Phase 2 实现决策）
- **背景**：`get_session()` 是生成器上下文管理器，需在 `QApplication.exec_()` 退出前保持 session 存活；但 SQLAlchemy session 非线程安全，不适合跨线程共享。
- **方案**：`main.py` 在 `for session in get_session(): ... break` 中启动 Qt 事件循环，session 在主线程内贯穿整个运行时；后台线程（训练、采集）使用 `engine.connect()` 独立连接，不复用该 session。
- **原因**：简单可行；主线程 UI 操作均串行，不存在并发写冲突。
- **后果**：Phase 7 重构时可改为按请求 session（每次 UI 操作开/关），届时需评估事务粒度。

## [2026-04-21] D-012 旧代码映射表（Phase 7 清理前备档）

| 旧文件 | 替换为 | 备注 |
|---|---|---|
| `main.py`（根目录）| `src/neuropilot/main.py` | 入口重写 |
| `eeg_module.py` | `domain/eeg/` + `app/acquisition_worker.py` | 全量迁移 |
| `task_module.py` | `app/paradigm_engine.py` + `ui/pages/task_page.py` | FSM 重写 |
| `dashboard_module.py` | `ui/pages/dashboard_page.py` | pyqtgraph 重写 |
| `device_control.py` | `domain/device/device_service.py` + `ui/pages/device_page.py` | 节流+枚举 |
| `debug_module.py` | `ui/pages/debug_page.py` | HEX 转义修复 |
| `ml_module.py` | `domain/ml/` + `app/ml_jobs.py` + `ui/pages/ml_page.py` | 异步+sha256 |
| `data_module.py` | `infra/db/repositories/` | SQLAlchemy Core |
| `subject_manager.py` | `infra/db/repositories/subject_repo.py` + `ui/pages/subjects_page.py` | 单库 |
| `log_module.py` + `log_viewer.py` | `ui/pages/logs_page.py` | loguru sink |
| `login_dialog.py`（根目录）| `ui/login_dialog.py` | FramelessWindow |
| `CSP_2.py` | `domain/ml/csp.py` | 数值稳定修复 |
| `core/` | 已拆分入对应 domain/ 模块 | 删除 |

---

## [2026-04-21] D-011 登录对话框拖动：`event.globalPosition().toPoint()`（Phase 2 实现决策）
- **背景**：旧版使用 `event.globalPos()`，PyQt5 5.15+ 已废弃该方法；`FramelessWindowHint` 窗口需自行实现拖动。
- **方案**：`mousePressEvent` 中使用 `event.globalPosition().toPoint()` 记录起始点；`mouseMoveEvent` 中计算偏移量更新窗口位置。
- **原因**：消除废弃 API 警告；兼容 PyQt5 5.15.x 最新补丁版本。
- **后果**：如未来升级 PyQt6，`globalPosition()` 返回 `QPointF`，`.toPoint()` 仍可用，无需修改。
