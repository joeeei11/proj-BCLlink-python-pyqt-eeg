---
# Phase 1：骨架搭建与基础设施

## 目标
仓库完成现代化工具链、分层目录骨架、配置与日志系统就绪，能够以 `python -m neuropilot` 启动一个带占位主窗口的空壳应用。

## 前置条件
- Python 3.10+ 已安装
- 旧版代码仍保留在仓库根目录（CSP_2.py、*.py、core/、data/ 等），本阶段不删除
- 已读 CLAUDE.md、tasks/progress.md、tasks/decisions.md

## 任务清单
- [ ] 任务 1：在仓库根创建 `pyproject.toml`，声明依赖（PyQt5、pyqtgraph、numpy、scipy、scikit-learn、pandas、pyserial、pylsl、pybluez2、SQLAlchemy、pydantic-settings、passlib[bcrypt]、loguru、joblib、pytest、pytest-qt、ruff、mypy、pre-commit），配置 `ruff`/`mypy` 规则；`src` 布局
- [ ] 任务 2：创建目录骨架 `src/neuropilot/{app,domain,infra,ui}/` 及 `tests/{unit,integration,ui}/`，每个目录 `__init__.py`
- [ ] 任务 3：实现 `src/neuropilot/infra/config.py`：基于 `pydantic-settings` 读 `config/default.toml` + `config/local.toml` + 环境变量（CLAUDE.md 中的变量全部落地）
- [ ] 任务 4：实现 `src/neuropilot/infra/logger.py`：loguru 初始化函数 `setup_logger(cfg)`，同时输出到 stdout + `data/logs/neuropilot.log`（rotation=10 MB, retention=14 天）
- [ ] 任务 5：创建 `config/default.toml` 并把旧 `QSettings` 中的 EEG/Device 默认参数平移过来（作为应用层默认值）
- [ ] 任务 6：创建 `src/neuropilot/main.py` + `src/neuropilot/__main__.py`：构造 `QApplication`，载入配置，初始化 logger，弹一个只显示 "NeuroPilot 重构版 骨架就绪" 的 `FluentWindow`
- [ ] 任务 7：配置 `.gitignore`（`.venv/`、`data/`、`__pycache__/`、`*.pyc`、`.env`、`config/local.toml`、`.ruff_cache/`、`.mypy_cache/`、`.pytest_cache/`）
- [ ] 任务 8：配置 `.pre-commit-config.yaml`（ruff 自动修复、mypy、trailing-whitespace）
- [ ] 任务 9：创建空测试 `tests/unit/test_smoke.py`：`def test_import_package(): import neuropilot`
- [ ] 任务 10：写 `README.md`，覆盖 CLAUDE.md 中的"启动方式"章节

## 验收标准
- [ ] 运行 `uv pip install -e ".[dev]"` 成功（或 `pip install`）
- [ ] 运行 `python -m neuropilot` 弹出空主窗口，无异常
- [ ] 运行 `ruff check src tests` 无错误
- [ ] 运行 `mypy src/neuropilot/infra` 无错误
- [ ] 运行 `pytest -q` 至少 1 个测试通过
- [ ] 日志文件 `data/logs/neuropilot.log` 被创建且包含 `logger started` 行
- [ ] `git status` 不应出现 `data/`、`config/local.toml`、`__pycache__/`

## 注意事项
- 旧版模块（`main.py`、`eeg_module.py` 等）仍保留在根目录，不要在本阶段移动或修改
- `pyqtgraph` 与 `PyQt5` 必须同时安装；某些系统下需显式装 `PyQt5>=5.15.9` 以修复高 DPI 问题
- pybluez2 在 Windows 上编译困难，把它放 `[optional-dependencies] bluetooth = ["pybluez2"]`，不进默认依赖
- macOS 下 loguru 写文件要先 `os.makedirs` 父目录，写在 `setup_logger` 内部
- `FluentWindow` 初始化时若不 `show()` 就 `exec_()` 会一闪而过，务必 `show()` 后进事件循环
- 本阶段**不要**动业务逻辑；只搭架子
---
