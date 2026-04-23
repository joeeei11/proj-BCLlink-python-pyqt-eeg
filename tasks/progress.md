# 开发进度

## 状态：Phase 1–7 代码全部完成（待环境配置与端到端测试验收）

## 已完成

### Phase 1 骨架搭建与基础设施（2026-04-21）
- [x] `pyproject.toml`（依赖声明 + ruff/mypy，src 布局）
- [x] 目录骨架 + 全部 `__init__.py`
- [x] `infra/config.py`（pydantic-settings，env var 优先于 TOML）
- [x] `infra/logger.py`（loguru，stdout + 轮转文件）
- [x] `config/default.toml`（EEG/Device/Paradigm 默认参数）
- [x] `main.py` + `__main__.py`（入口）
- [x] `.gitignore` / `.pre-commit-config.yaml`
- [x] `tests/unit/test_smoke.py`
- [x] `README.md`

### Phase 2 鉴权、受试者、数据库统一（2026-04-21）
- [x] 任务 1：`infra/db/schema.sql`（users/subjects/sessions/trials/models 五表，WAL 索引）
- [x] 任务 2：`infra/db/engine.py`（SQLAlchemy Core，WAL PRAGMA，首次建表）
- [x] 任务 3：`infra/db/repositories/user_repo.py` + `subject_repo.py`（Pydantic DTO，CRUD）
- [x] 任务 4：`app/auth_service.py`（bcrypt 校验，失败计数，锁定/解锁）
- [x] 任务 4b：`app/event_bus.py`（QObject 信号总线）
- [x] 任务 5：`scripts/seed_admin.py`（首次建 admin 账号）
- [x] 任务 6：`scripts/migrate_legacy_db.py`（合并旧库，dry-run，幂等，备份）
- [x] 任务 7：`ui/login_dialog.py`（FramelessWindowHint，拖动，倒计时，QSettings 仅存 username）
- [x] 任务 8：`ui/pages/subjects_page.py`（qfluentwidgets TableView，搜索，删除二次确认）
- [x] 任务 9：`ui/main_window.py`（登录流程接入，bind_user，EventBus 广播）
- [x] 任务 10：测试（test_auth_service / test_subject_repo / test_login_dialog / test_subjects_page）

### 待用户手动验收（配好环境后）
- [ ] `pip install -e ".[dev]"` 成功
- [ ] `python -m neuropilot` → 弹登录框 → 输正确密码 → 进主窗口
- [ ] 输错误密码 5 次 → 按钮置灰 + 倒计时
- [ ] 受试者页增删改查正常，删除有二次确认
- [ ] `pytest -q` 全绿（unit 测试不依赖 PyQt5）
- [ ] `ruff check src tests` / `mypy src/neuropilot/infra src/neuropilot/app` 无错

---

### Phase 3 EEG 采集与传输层统一（2026-04-21，代码已完成）
- [x] 任务 1：`domain/eeg/transports/base.py`（IDeviceTransport 抽象接口）
- [x] 任务 2：六种传输实现（demo/serial/bluetooth/tcp/udp/lsl），缺依赖时抛 DependencyMissingError
- [x] 任务 3：`domain/eeg/ring_buffer.py`（修复 get_last 未满时返回 None 的 bug）
- [x] 任务 4：`app/acquisition_worker.py`（QThread + socketpair 自唤醒，session_repo，CSV 按秒 flush）
- [x] 任务 5：`ui/pages/eeg_page.py`（6 种模式 ComboBox，纯 EventBus 通信）
- [x] 任务 6：`ui/pages/dashboard_page.py`（EventBus 订阅 samples，pyqtgraph 实时波形，±500 µV 限幅）
- [x] 任务 7：`tests/unit/test_ring_buffer.py` + `tests/integration/test_acquisition_demo.py` + `tests/integration/test_tcp_transport.py` + `tests/tools/tcp_fake_server.py`
- [x] `infra/db/repositories/session_repo.py`（SessionRepo CRUD）
- [x] `infra/db/migrations/m0002_sessions_eeg_fields.py`（幂等 ALTER 添加 transport/n_channels/srate）
- [x] `main.py` 更新（接入 session_repo，调用 m0002 迁移）

### 待环境配置后手动验收
- [ ] `pytest -q tests/unit tests/integration` 全绿
- [ ] EEG 页演示模式连接 → Dashboard 出现 10 Hz 正弦波，FPS > 25
- [ ] TCP 连接 fake_server → 收包/写 CSV/断开 ≤ 300 ms
- [ ] ruff check src tests / mypy src/neuropilot/domain 无错

### Phase 4 外设控制与设备调试统一（2026-04-21，代码已完成）
- [x] `domain/device/commands.py`（DeviceCommand 枚举，5 种命令 + custom pass-through）
- [x] `domain/device/device_service.py`（DeviceService，150ms 节流，write() 复用 IDeviceTransport）
- [x] `domain/eeg/transports/` 四个 transport 补 write() 方法（serial/tcp/bluetooth/udp）
- [x] `app/session_manager.py`（统筹外设连接，外设断开自动禁用 auto_send）
- [x] `ui/pages/device_page.py`（4 种模式，未连接时按钮置灰）
- [x] `ui/pages/debug_page.py`（HEX/ASCII 双模式，setMaximumBlockCount(1000)，正确转义）
- [x] EventBus 补充 device_* 信号
- [x] `tests/unit/test_device_command.py`（全枚举映射）
- [x] `tests/unit/test_device_service.py`（节流150ms、未连接拒绝、transport swap）

### Phase 5 范式引擎与试次记录（2026-04-21，代码已完成）
- [x] `app/paradigm_engine.py`（FSM IDLE→FIX→CUE→IMAG→REST→ITI→DONE，abort() 代次计数）
- [x] `app/trial_recorder.py`（dict[uuid] 解耦，threading.Lock，孤儿 flush）
- [x] `infra/db/repositories/trial_repo.py`（TrialRepo CRUD）
- [x] `ui/widgets/stage_bar.py`（每次 highlight 先全部 reset，消除颜色累积 bug）
- [x] `ui/widgets/stimulus_area.py`（GIF 丢失回退文字，默认 show_fix）
- [x] `ui/pages/task_page.py`（QSplitter 双栏，CSV 导出从 DB，外设断开自动中止）
- [x] EventBus 补充 paradigm_* 信号
- [x] `tests/unit/test_paradigm_engine.py`（状态跳转、abort 不泄漏、试次计数）
- [x] `tests/unit/test_trial_recorder.py`（交错事件、孤儿 flush、close 未知 uuid 不报错）

### Phase 6 ML 管线、模型持久化、在线预测（2026-04-21，代码已完成）
- [x] `domain/dsp/filters.py`（bandpass_filter + notch_filter，scipy sosfiltfilt）
- [x] `domain/ml/csp.py`（CSP，cov+=eps*I，log(max(var/sum,1e-12))，sklearn 兼容）
- [x] `domain/ml/pipelines.py`（build_pipeline，4 种算法，bandpass→CSP→Scaler→clf）
- [x] `domain/ml/model_store.py`（joblib.dump + sha256，篡改拒绝）
- [x] `infra/db/repositories/model_repo.py`（ModelRepo，set_active 单激活）
- [x] `app/ml_jobs.py`（QRunnable，5-fold CV，cancel 支持，n_jobs=1）
- [x] `app/predictor.py`（RingBuffer 积累，500ms 投票，平票 random 修复偏左 bug）
- [x] `ui/pages/ml_page.py`（训练进度条，取消按钮，激活模型）
- [x] EventBus 补充 ml_* 信号
- [x] `tests/unit/test_csp.py`（零方差稳定、无 NaN/Inf、单类报错）
- [x] `tests/unit/test_model_store.py`（保存加载、篡改拒绝、缺文件拒绝）

### Phase 7 UI 统一化、质量加固与交付（2026-04-21，代码已完成）
- [x] `ui/theme.py`（颜色变量 + apply_global_qss）
- [x] `ui/pages/analytics_page.py`（session 汇总表，准确率，CSV 导出）
- [x] `ui/pages/logs_page.py`（loguru sink，级别过滤，关键词，导出，openUrl 打开目录）
- [x] `main.py` 接入主题、新页面、SessionManager、ParadigmEngine
- [x] `main_window.py` 补全 8 页（Dashboard/EEG/Subjects/Device/Debug/Task/ML/Analytics/Logs）
- [x] `tasks/decisions.md` 补 D-012 旧→新映射表
- [x] `infra/db/repositories/session_repo.py` 补 list_all()

---

## 当前：全部代码已完成

---

## 后续待完成（需配置环境后执行）
- 旧版 `.py` 文件清理（CLAUDE.md 任务 6 要求在 pytest 全绿后执行）
- `pytest tests/` 全量验收
- `ruff check src tests` + `mypy src/neuropilot/domain` 无错
- 端到端闭环测试（登录→选受试者→Demo EEG→校准→训练→激活→范式→分析）

## 阻塞 / 风险
- qfluentwidgets 某些 InfoLevel 枚举（ATTENTION/NORMAL）版本间不兼容
- Windows/macOS 下 FramelessWindowHint + WA_TranslucentBackground 行为差异（已在 login_dialog 注意）
- `main.py` 中 session 生命周期与 Qt 事件循环的交叉需关注（Phase 7 整体优化）

## 技术说明
- `config/default.toml` 顶层 key 直接对应 `AppSettings` 字段名；嵌套 section 展平为 `{section}_{key}`。
- `load_settings` 手动处理 env var 优先级：已设置的 env var 字段不被 TOML 覆盖。
- `main.py` 在 `get_session()` 上下文中装配 repos 和 service，session 生命周期覆盖整个 Qt 运行时。
