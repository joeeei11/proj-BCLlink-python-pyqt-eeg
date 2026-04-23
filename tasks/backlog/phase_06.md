---
# Phase 6：ML 管线、模型持久化、在线预测

## 目标
CSP + 分类器管线数值稳定；训练异步不阻塞 UI；模型可按受试者保存/加载/激活；在线预测接入范式循环。

## 前置条件
- Phase 5 已完成：范式可跑、trials 入库
- 已有某 subject 的训练数据（至少 10 left + 10 right trial）

## 任务清单
- [ ] 任务 1：`domain/ml/csp.py`：
  - 迁移旧 `core/models.py:CSP`
  - 白化前 `cov += eps*I`（eps=1e-6）
  - `np.log(np.maximum(var/sum, 1e-12))` 防 -inf
  - 保留 `vectorized` 后端；删除 `loop` 后端
  - 添加 `fit_transform` 并通过 sklearn 兼容性测试
- [ ] 任务 2：`domain/ml/pipelines.py`：标准 `Pipeline([("bandpass", ...), ("csp", CSP(4)), ("scaler", StandardScaler()), ("clf", SVC(probability=True))])`；支持 `algo ∈ {svm, lr, rf, knn}`
- [ ] 任务 3：`domain/ml/model_store.py`：
  - `save(pipeline, subject_id, metadata) → ModelRecord`：`joblib.dump` + sha256 + 写 `models` 表
  - `load(model_id) → Pipeline`：读库 → 校验 sha256 → `joblib.load`
  - 拒绝未入库或哈希不匹配的文件
- [ ] 任务 4：`app/ml_jobs.py`：`QThreadPool` + `QRunnable`；`train_async(session_ids, algo) → JobHandle`；信号 `sig_progress(int,str) / sig_done(ModelRecord) / sig_failed(str)`
- [ ] 任务 5：`ui/pages/ml_page.py`（新）：
  - 选 subject + sessions 数据源（DB 中所有符合条件的 trial）
  - 算法选择 + 参数网格输入（复用旧 parser）
  - "开始训练"触发 `train_async`；进度条 + 取消按钮
  - 右侧展示混淆矩阵、ROC、学习曲线
  - "保存为当前模型"按钮
- [ ] 任务 6：在线预测：
  - `app/predictor.py`：订阅 `AcquisitionWorker.sig_samples`，累积窗口；每 500 ms 预测；发射 `sig_prediction(label, conf)`
  - `ParadigmEngine.begin_trial/end_trial` 改为调 `predictor.begin_voting/end_voting`
  - 投票平票**随机选一边**（修复旧版系统性偏左 bug），用 `np.random.default_rng(None)`
- [ ] 任务 7：`ui/pages/eeg_page.py`：校准卡片保留，但训练入口跳转 ML 页或共用 `train_async`；加载模型下拉按 subject 展示全部模型
- [ ] 任务 8：测试：
  - `tests/unit/test_csp.py`：零方差 trial、不同 n_components、两类校验
  - `tests/unit/test_model_store.py`：保存-加载-篡改拒绝
  - `tests/integration/test_train_job.py`：demo session → 训练 → 预测

## 验收标准
- [ ] 10 left + 10 right demo 数据训练，UI 不卡（主线程 FPS > 25）
- [ ] 训练完成后 `models` 表新记录 `sha256` 非空 + `accuracy` 有值
- [ ] 激活模型后在线预测灯亮；Task 范式实时回填 `predicted_label`
- [ ] 手动改 `data/models/xxx.pkl` 一字节 → 加载被拒并提示
- [ ] `pytest -q` 全绿；`mypy src/neuropilot/domain/ml` 无错

## 注意事项
- `QThreadPool.globalInstance().start(runnable)` 后 `runnable.setAutoDelete(True)` 避免引用悬挂
- joblib `n_jobs=1`（多进程与 PyQt 主线程冲突）
- CSP 前带通 8–30 Hz：pipeline 最前 `FunctionTransformer` 包 `dsp.filters.bandpass`
- 平票随机 `np.random.default_rng()` 不固定 seed
- 激活模型时 `Predictor.pipeline` 原子替换（配合锁）
---
