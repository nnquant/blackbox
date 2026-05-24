# Run 结果产物契约

## 目标

Run 是 Blackbox 的最小运行单位。Project / Research / Branch 只负责聚合、筛选和对比。一个 Run 内部可能同时产生策略绩效、单因子测试、批量因子测试、风控、成本和诊断产物，因此 Run Detail 不能再只依赖 artifact 名称猜测展示方式。

本契约把 Run 输出拆成三层：

- `run_metrics`：标量指标，用于搜索、排序、Compare 表格和关键指标卡片。
- `artifacts`：序列、表格、报告、图片等原始数据文件。
- `metadata_json.result`：artifact 的展示语义，声明它属于哪个结果域、结果组和角色。

这样存储仍保持通用，WebUI 则可以稳定地按结果域渲染。

## Artifact Result Metadata

所有需要进入 Run Detail Results 的 artifact 都应携带：

```json
{
  "result": {
    "domain": "performance",
    "name": "primary_performance",
    "role": "primary_curve",
    "title": "Performance Curve",
    "group": "performance.primary",
    "order": 10,
    "view": {
      "default": "performance_chart",
      "x": "date",
      "y": "series_values",
      "mode": "nav",
      "chart": "line_drawdown"
    }
  }
}
```

字段含义：

- `domain`：结果域。内置值为 `performance`、`factor`、`factor_batch`、`risk`、`cost`、`diagnostic`、`custom`。
- `name`：结果项稳定名称，不要求等同 artifact 文件名。
- `role`：该 artifact 在结果组中的角色。
- `title`：WebUI 显示名称。
- `group`：同一组结果的稳定 key，例如 `performance.primary`、`factor.alpha_reversal`。
- `order`：组内排序。
- `view`：展示建议。数据仍以 artifact 内容为准。

## 内置角色

`performance`：

- `primary_curve`：主净值 / 累计收益 / 累计 PnL 曲线。
- `drawdown`：回撤序列。
- `summary_table`：绩效摘要表。

`factor`：

- `ic_curve`：单因子 IC / Rank IC / 累计 IC 序列。
- `quantile_returns`：分组收益、分层收益或分位数组合表现。
- `coverage`：覆盖率序列或表格。
- `turnover`：换手率序列或表格。

`factor_batch`：

- `comparison_table`：多因子的关键指标对比表。
- `comparison_curve`：多因子的收益、累计 IC 或其他序列重叠对比图。

`diagnostic` / `risk` / `cost`：

- `table`：普通明细表。
- `series`：可画图序列。
- `report`：HTML / Markdown / JSON 报告。

## Performance 示例

标量指标继续写入 `strategy.summary`，百分比用百分点：

```json
{
  "annual_return": 18.5,
  "annual_volatility": 12.4,
  "max_drawdown": -9.0,
  "sharpe": 1.34,
  "sortino": 1.88,
  "calmar": 2.06
}
```

主曲线使用 `series_values` 和显式 `mode`：

```powershell
bbox run log-series `
  --run-id run_new `
  --name equity_curve `
  --data-file .\equity.json `
  --x date `
  --y series_values `
  --mode nav `
  --namespace strategy.equity `
  --result-domain performance `
  --result-name primary_performance `
  --result-role primary_curve `
  --result-title "Performance Curve" `
  --result-group performance.primary `
  --result-order 10 `
  --result-view '{"default":"performance_chart","x":"date","y":"series_values","mode":"nav","chart":"line_drawdown"}' `
  --json
```

`mode` 语义：

- `nav`：`series_values` 是净值水平。
- `return`：`series_values` 是单期小数收益率，例如 `0.012`。
- `pnl`：`series_values` 是绝对变化，例如 101 到 110 记 `9.0`。
- `drawdown`：用于 `drawdown_series`。

## 单因子测试示例

单因子 Run 应至少包含：

- `factor.summary` 标量指标，如 `ic_mean`、`ic_ir`、`coverage`、`turnover`。
- `factor_ic_series`，角色为 `factor.ic_curve`，建议列包含 `date`、`ic`、`rank_ic`、`cumulative_ic`。
- `factor_quantile_returns`，角色为 `factor.quantile_returns`，用于分组收益。

SDK：

```python
import blackbox as bb

bb.log_factor_result(
    metrics={"ic_mean": 0.034, "ic_ir": 0.61, "coverage": 0.94, "turnover": 0.38},
    factor_name="alpha_reversal_5d",
    ic_series=[
        {"date": "2026-01-02", "ic": 0.031, "rank_ic": 0.044, "cumulative_ic": 0.031},
        {"date": "2026-01-05", "ic": -0.012, "rank_ic": -0.018, "cumulative_ic": 0.019}
    ],
    quantile_returns=[
        {"date": "2026-01-02", "quantile": 1, "series_values": 1.000},
        {"date": "2026-01-02", "quantile": 5, "series_values": 1.006}
    ],
)
```

## 批量因子测试示例

如果一个 Run 是批量测试多个因子，应使用 `factor_batch` 结果域：

```python
import blackbox as bb

bb.log_factor_batch_result(
    comparison_table=[
        {"factor": "alpha_reversal_5d", "ic_mean": 0.034, "ic_ir": 0.61, "long_short_return": 0.082},
        {"factor": "alpha_volume_shock", "ic_mean": 0.021, "ic_ir": 0.44, "long_short_return": 0.051}
    ],
    comparison_series=[
        {"date": "2026-01-02", "alpha_reversal_5d": 1.000, "alpha_volume_shock": 1.000},
        {"date": "2026-01-05", "alpha_reversal_5d": 1.004, "alpha_volume_shock": 0.998}
    ],
    y=["alpha_reversal_5d", "alpha_volume_shock"],
)
```

## 兼容策略

WebUI 优先读取 `metadata_json.result`。旧数据没有该字段时，按以下兼容规则映射：

- `equity_curve`、`returns_series`、`pnl_series`、`absolute_return_series` -> `performance.primary_curve`
- `drawdown_series` -> `performance.drawdown`
- `factor_ic_series` -> `factor.ic_curve`
- `factor_quantile_returns` -> `factor.quantile_returns`
- `factor_comparison`、`factor_rank_*` -> `factor_batch.comparison_table`

Raw Artifacts tab 保留完整 artifact 列表；Results tab 只负责规范化展示。
