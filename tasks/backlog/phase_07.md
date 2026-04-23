---
# Phase 7：UI 统一化、质量加固与交付

## 目标
全量迁移到 `src/neuropilot/`，删除旧版遗留；Fluent 主题统一、响应式布局；端到端测试通过；CI 就绪；可交付 1.0 版本。

## 前置条件
- Phase 1–6 全部完成，新版覆盖旧版所有场景
- `scripts/migrate_legacy_db.py` 已把历史数据迁入新库
- 已跑过完整闭环：登录 → 选 subject → 连 EEG → 校准 → 训练 → 激活 → 连外设 → 跑范式 → 分析页可见新 trials

## 任务清单
- [ ] 任务 1：`ui/theme.py`：统一颜色变量（主 `#007AFF`、成功 `#4CAF50`、警告 `#FF9800`、错误 `#F44336`、次要文字 `#666`）；`apply_global_qss(app)` 与 qfluentwidgets 协同；删除旧模块内嵌 QSS
- [ ] 任务 2：响应式审核：
  - Task 页 settings_area 改 `QSplitter`
  - Dashboard 卡片 `minimumSize`，1280×720 不溢出
  - `FixedWidth` 全部替换为 `minimumWidth + sizePolicy`
- [ ] 任务 3：`ui/pages/analytics_page.py`（新）：统一从 `data/neuro_pilot.db` 读；过滤器 subject/日期/session；图表学习曲线、混淆矩阵、准确率趋势、带 p 值（启用旧版已导入但未用的 `ttest_ind`）；导出 CSV/JSON/PDF
- [ ] 任务 4：`ui/pages/logs_page.py`（新）：订阅 loguru sink 实时渲染；级别过滤/关键字/导出；"打开目录"用 `QDesktopServices.openUrl(QUrl.fromLocalFile(path))` 取代旧对话框
- [ ] 任务 5：登录/主窗口 UX：
  - 首次启动若无 admin：弹引导对话框设置管理员密码（不再强依赖环境变量）
  - 登录页彻底删除硬编码提示
  - 所有 `event.globalPos()` 迁 `event.globalPosition().toPoint()`
- [ ] 任务 6：清理与下线：
  - 删除根目录旧版 `.py`：`main.py` `eeg_module.py` `task_module.py` `dashboard_module.py` `device_control.py` `debug_module.py` `ml_module.py` `data_module.py` `subject_manager.py` `log_module.py` `log_viewer.py` `login_dialog.py` `CSP_2.py` 与 `core/`、`__pycache__/`
  - 删除 `NeuroPilot_Source_Code.txt`
  - 旧库 `data.db` 改名 `data.db.bak_<timestamp>`；README 补说明
- [ ] 任务 7：CI（GitHub Actions 或等效）：
  - `lint`: ruff + mypy
  - `test`: pytest + coverage，阈值 70%
  - `build`: `pyinstaller` 单文件（可选）
- [ ] 任务 8：端到端测试 `tests/e2e/test_full_flow.py`（pytest-qt + demo transport + fake device）：登录 → 建 subject → 启 session → 采 100 chunk → 训练 → 激活 → 跑 3 trial → 断言 DB 有 1 session + 3 trial + 1 model
- [ ] 任务 9：文档：
  - `README.md` 补截图、安装、常见问题
  - `docs/ARCHITECTURE.md` C4 图（Mermaid）
  - `docs/MIGRATION.md` 从旧版迁移步骤

## 验收标准
- [ ] 仓库根已无旧 `.py`；`tree -L 2` 与 CLAUDE.md 目录结构一致
- [ ] `ruff check . && mypy src && pytest --cov=src --cov-fail-under=70` 全过
- [ ] 1280×720 窗口下 8 页无截断/溢出
- [ ] 登录流程无任何默认账号密码显示
- [ ] CI 绿色徽章
- [ ] `pytest tests/e2e` 通过
- [ ] 打 `git tag v1.0.0`，README 顶部显示版本

## 注意事项
- 删旧代码前在 `tasks/decisions.md` 记录"旧→新"映射表
- `pyinstaller` 打包时 `pyqtgraph` / `pylsl` 需手动补 hidden imports
- headless CI 用 `QT_QPA_PLATFORM=offscreen` 跑 `pytest-qt`
- 删旧库先 `cp` `.bak_YYYYMMDD` 再改名；不要 `rm`
- 若发现新版未覆盖旧版某功能，先在 `progress.md` 记录阻塞，决定"补做 / 显式弃用"
---
