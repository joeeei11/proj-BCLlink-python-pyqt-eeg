# NeuroPilot 脑机接口康复系统

面向脑卒中上肢康复的桌面端 BCI 系统：EEG 采集 → 运动想象范式 → 在线左/右手意图分类 → 外设（机械手/刺激器）反馈。

## 技术栈

Python 3.10+ · PyQt5 · PyQt-Fluent-Widgets · pyqtgraph · SQLAlchemy 2 · loguru · pydantic-settings · scikit-learn

## 快速开始

```bash
# 1. 创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. 安装依赖（推荐 uv）
pip install -e ".[dev]"
# 或
uv pip install -e ".[dev]"

# 3. 初始化数据库并创建 admin（首次运行）
NEUROPILOT_ADMIN_INITIAL_PASSWORD='ChangeMe!' python scripts/seed_admin.py

# 4. 迁移历史数据库（从旧版迁移时执行一次）
python scripts/migrate_legacy_db.py --old data.db --old data/neuro_pilot.db

# 5. 启动
python -m neuropilot
```

## 开发

```bash
# 运行测试
pytest -q

# Lint
ruff check src tests

# 类型检查
mypy src/neuropilot/infra src/neuropilot/domain

# 安装 pre-commit 钩子
pre-commit install
```

## 配置

- `config/default.toml`：默认配置（入 git）
- `config/local.toml`：本地覆盖（.gitignore，不入 git）
- 环境变量 `NEUROPILOT_*` 优先级最高

常用环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `NEUROPILOT_ENV` | `dev` | `dev` / `prod` / `test` |
| `NEUROPILOT_DB_PATH` | `data/neuro_pilot.db` | SQLite 路径 |
| `NEUROPILOT_LOG_LEVEL` | `INFO` | 日志级别 |
| `NEUROPILOT_THEME` | `light` | `light` / `dark` |

## 目录结构

```
src/neuropilot/
├── app/          # 应用层（用例、事件总线）
├── domain/       # 领域层（无 PyQt 依赖）
│   ├── eeg/      # 采集、环形缓冲、传输策略
│   ├── device/   # 外设控制
│   ├── dsp/      # 数字滤波、频谱
│   └── ml/       # CSP、分类管线、模型存储
├── infra/        # 基础设施（DB、配置、日志）
└── ui/           # 展示层（页面、组件）
```

## 许可

Internal / Research Use Only
