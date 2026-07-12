# SDK 设计

## 1. SDK 目标

SDK 的目标是让研究代码以尽量低的侵入性接入 `blackbox`。

理想使用体验是：

```python
import blackbox as bb

with bb.init(
    project="alpha-lab",
    research="csi500-reversal",
    branch="baseline-v1",
    name="lb20_hold5_fee10bp",
    config={"lookback": 20, "hold_days": 5, "fee_bps": 10},
    tags=["reversal", "baseline"]
) as run:
    bb.log({"rows": 3200000}, namespace="pipeline.stage", point={"kind": "event", "name": "data_loaded"})
    bb.log_factor_summary({"ic_mean": 0.034, "ic_ir": 0.61, "coverage": 0.94})
    bb.log_performance_result(curve=equity_df, mode="nav", x="date", y="nav", periods_per_year=252)
    bb.log_artifact("post_cost_report", "reports/post_cost.html", kind="report_html")
```

## 2. SDK 主接口

建议最小 API 面如下。

### 2.1 生命周期

- `bb.init(...)`
- `bb.finish(status="completed")`
- `bb.fail(error=...)`
- `bb.current_run()`

### 2.2 记录类接口

- `bb.log(values, namespace=None, point=None, tags=None)`
- `bb.log_event(event_type, stage=None, payload=None)`
- `bb.log_note(kind, summary, content=None, structured=None)`
- `bb.log_params(params)`
- `bb.set_tags(tags)`
- `bb.set_summary(values)`

### 2.3 序列与表格

- `bb.log_series(name, data, x=None, y=None, namespace=None)`
- `bb.log_table(name, df, kind="table_parquet")`

### 2.4 产物

- `bb.log_artifact(name, path, kind=None, metadata=None)`
- `bb.log_bytes(name, content, kind=None, filename=None)`
- `bb.register_external_artifact(name, uri, kind=None, metadata=None)`

### 2.5 快照

- `bb.capture_git()`
- `bb.capture_env()`
- `bb.capture_requirements()`
- `bb.register_dataset(...)`

## 3. 量化专用 helper

为了降低使用门槛，建议内置量化领域 helper。

### 因子研究

- `bb.log_factor_summary(...)`
- `bb.log_factor_ic_series(df)`
- `bb.log_quantile_returns(df)`
- `bb.log_factor_turnover(df)`
- `bb.log_factor_coverage(df)`

### 策略回测

- `bb.log_backtest_summary(...)`
- `bb.log_returns_series(df)`
- `bb.log_drawdown_series(df)`
- `bb.log_positions(df)`
- `bb.log_trades(df)`
- `bb.log_cost_breakdown(...)`
- `bb.log_risk_exposure(df)`

### Sweep

- `bb.log_sweep_coord({"lookback": 20, "hold_days": 5})`
- `bb.attach_sweep(sweep_id, coord=...)`

这样上层策略代码只需要处理领域数据，不必重复拼装 namespace 和 artifact 类型。

## 4. `bb.log` 的建议语义

`bb.log` 主要用于小型结构化指标。

### 适合 `bb.log` 的内容

- scalar metrics
- 短小的 stage stats
- pipeline event payload
- 资源使用情况
- 关键阶段 summary

### 不适合 `bb.log` 的内容

- 大 DataFrame
- 全量持仓矩阵
- 分钟级大序列
- 完整交易流水

这些应走 `bb.log_table` / `bb.log_artifact`。

## 5. 上下文自动采集

SDK 在 `bb.init()` 时建议自动采集：

- `git_commit`
- `git_dirty`
- `hostname`
- `python_version`
- `platform`
- `pid`
- `cwd`
- `entry_file`
- `start_time`

如果用户显式关闭，才不采集。

## 6. 离线模式

量化回测很常在内网、远端机器、批处理环境中跑。  
SDK 应提供离线模式：

- 本地写到 spool 目录
- 后续用 CLI `bbox sync` 同步
- 保留本地失败重试记录

建议目录：

```text
.blackbox/
├── queue/
├── artifacts/
└── manifests/
```

## 7. 缓冲与重试

SDK 不应每条日志都立刻发 HTTP。

建议机制：

- 内存缓冲
- 批量 flush
- 异常自动重试
- 进程退出时强制 flush
- 每条记录带 `client_event_id`

这样即使网络短暂波动，也不会导致 run 记录不一致。

## 8. 异常处理

当用户在 `with bb.init()` 中抛异常时：

- 自动写 `run_failed` event
- 记录异常栈摘要
- 标记 run 状态为 `failed`
- 尽可能保留已经上传的 artifact

## 9. SDK 设计取舍

### 9.1 不把 SDK 做得太“重”
SDK 只做记录，不接管回测流程。

### 9.2 尽量兼容 pandas / numpy
量化研究里绝大部分数据都以 pandas DataFrame 为主。

### 9.3 不强依赖某个回测框架
无论你用的是自研引擎、vectorbt、zipline 风格框架，SDK 都应可接。
