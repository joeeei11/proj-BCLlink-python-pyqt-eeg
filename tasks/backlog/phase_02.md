---
# Phase 2：鉴权、受试者、数据库统一

## 目标
统一 SQLite 数据库；完成安全登录（bcrypt + 失败锁定）；受试者管理页可增删改查并强制成为后续实验的必选上下文。

## 前置条件
- Phase 1 已完成：`python -m neuropilot` 能启动空窗口
- `infra/config.py`、`infra/logger.py` 已可用

## 任务清单
- [ ] 任务 1：创建 `src/neuropilot/infra/db/schema.sql`，落地 `users/subjects/sessions/trials/models` 五表，开启 WAL
- [ ] 任务 2：创建 `src/neuropilot/infra/db/engine.py`：SQLAlchemy Core engine + sessionmaker，首次启动时执行 schema.sql
- [ ] 任务 3：实现 `infra/db/repositories/user_repo.py`、`subject_repo.py`（list/get/create/update/delete，DTO 用 Pydantic）
- [ ] 任务 4：实现 `app/auth_service.py`：`login(username, pwd)` → bcrypt 校验；`failed_count ≥ NEUROPILOT_LOCK_THRESHOLD` 写 `locked_until = now + N min`；通过后重置 failed_count
- [ ] 任务 5：编写 `scripts/seed_admin.py`：若 users 表空，读 `NEUROPILOT_ADMIN_INITIAL_PASSWORD`，写入 admin 账号
- [ ] 任务 6：编写 `scripts/migrate_legacy_db.py`：扫描 `data.db` 与 `data/neuro_pilot.db`，合并 `subjects/trials` 到新库；旧库改名 `*.bak_<timestamp>`；支持 `--dry-run`
- [ ] 任务 7：实现 `ui/login_dialog.py`（新）：调用 `AuthService`；删除默认账号明文；"记住密码"只持久化 username 到 `QSettings`；失败时显示剩余尝试次数 / 锁定时长；`mousePressEvent` 使用 `event.globalPosition().toPoint()`
- [ ] 任务 8：实现 `ui/pages/subjects_page.py`（新）：qfluentwidgets 的 `TableView` + Pydantic 校验表单；删除按二次确认；列表支持关键字搜索
- [ ] 任务 9：在 `ui/main_window.py` 中接入登录流程：登录成功后 `SessionManager.bind_user(user)` 并通过 `app/event_bus.py` 广播 `user_logged_in`
- [ ] 任务 10：测试：
  - `tests/unit/test_auth_service.py`（正确密码、错误密码、锁定、重置）
  - `tests/unit/test_subject_repo.py`（CRUD + 级联）
  - `tests/ui/test_login_dialog.py`（失败 5 次按钮置灰）
  - `tests/ui/test_subjects_page.py`（删除弹确认框）

## 验收标准
- [ ] 运行 `python scripts/seed_admin.py` 后，`data/neuro_pilot.db` 存在且 users 表有 admin 行
- [ ] 启动应用 → 输入错误密码 5 次 → 按钮置灰 + 倒计时提示
- [ ] 输入正确密码 → 进入主窗口，`event_bus` 发出 `user_logged_in` 事件
- [ ] 受试者页：新增/编辑/删除顺畅；删除有二次确认
- [ ] 未选 subject 时调用 `SessionManager.start` 抛 `SubjectRequiredError`
- [ ] `pytest -q` 全绿；`mypy src/neuropilot/app src/neuropilot/infra` 无错
- [ ] 运行 `scripts/migrate_legacy_db.py --dry-run` 输出预期合并条目数

## 注意事项
- `QSettings` 只存 username；**绝不**存明文或可逆加密密码
- bcrypt 轮数取 12；测试配置可降至 10 加速
- SQLAlchemy engine 传 `connect_args={"check_same_thread": False}` + 配合锁或每请求 session
- 迁移脚本必须幂等：以 `subject.name + onset_time` 作去重键
- 登录失败计数写库必须事务化，避免并发漏计
- `ui/login_dialog.py` 严禁直接访问 DB；全部经 `AuthService`
---
