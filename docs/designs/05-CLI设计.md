# CLI 设计

## 1. CLI 目标

CLI 不是给人“手打命令看表格”用的，而是主要给 AI Agent 与自动化脚本用的。  
因此它的设计原则应是：

- 默认非交互
- 默认结构化输出
- 命令尽量原子化
- 资源路径稳定
- 易于组合到 shell / agent toolchain

## 2. 命令分组

建议采用：

```text
bbox project ...
bbox research ...
bbox branch ...
bbox run ...
bbox artifact ...
bbox search ...
bbox compare ...
bbox note ...
bbox sync ...
```

## 3. 典型命令

### 3.1 Project / Research / Branch

```bash
bbox project create --key alpha-lab --title "Alpha Lab" --json
bbox research create --project alpha-lab --key csi500-reversal --title "中证500反转研究" --json
bbox branch create --research csi500-reversal --key baseline-v1 --title "Baseline V1" --json
```

### 3.2 从已有 Run 开新分支

```bash
bbox branch create \
  --research csi500-reversal \
  --from-run run_01HABC \
  --key barra-neutralization \
  --title "切换到Barra中性化" \
  --reason-type hypothesis_change \
  --reason-summary "验证Barra暴露回归是否提升IC稳定性" \
  --json
```

### 3.3 创建和完成 Run

```bash
bbox run start \
  --project alpha-lab \
  --research csi500-reversal \
  --branch baseline-v1 \
  --name lb20_hold5_fee10bp \
  --config-file config.yaml \
  --json

bbox run finish --run-id run_01HXYZ --status completed --json
```

### 3.4 记录指标与事件

```bash
bbox run log-metric \
  --run-id run_01HXYZ \
  --namespace strategy.summary \
  --values '{"sharpe":1.42,"max_drawdown":0.09}' \
  --point '{"kind":"event","name":"post_cost_backtest_done"}' \
  --json

bbox run log-event \
  --run-id run_01HXYZ \
  --event-type stage_completed \
  --stage neutralization_done \
  --payload '{"method":"barra_regression","coverage":0.93}' \
  --json
```

### 3.5 上传产物

```bash
bbox artifact upload \
  --run-id run_01HXYZ \
  --kind report_html \
  --name post_cost_report \
  --path reports/post_cost.html \
  --json
```

### 3.6 搜索与比较

```bash
bbox search runs \
  --project alpha-lab \
  --where 'metrics.strategy.summary.sharpe > 1.2 and tags contains "baseline"' \
  --json

bbox compare runs \
  --run-ids run_01A run_01B run_01C \
  --metrics strategy.summary.sharpe,strategy.summary.max_drawdown,factor.summary.ic_mean \
  --with-config-diff \
  --json
```

## 4. 输出格式

建议所有 CLI 命令支持：

- `--json`
- `--output json|table|yaml`
- `--quiet`

Agent 模式下，建议默认使用统一响应包：

```json
{
  "ok": true,
  "data": {...},
  "error": null
}
```

错误时：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "RUN_NOT_FOUND",
    "message": "run run_01HXYZ not found",
    "hint": "check project/research/branch scope"
  }
}
```

## 5. Exit Code 约定

建议：

- `0`: success
- `2`: validation error
- `3`: not found
- `4`: conflict / state error
- `5`: auth error
- `10`: server/network error

这对 Agent 很有用。

## 6. CLI 对 AI Agent 的特殊要求

### 6.1 不要强依赖自然语言输出
输出要尽量结构化，不让 Agent 去“读人类说明文”。

### 6.2 支持字段选择

```bash
bbox search runs ... --select id,name,status,summary.strategy.summary.sharpe --json
```

### 6.3 支持幂等写入

```bash
bbox run start ... --idempotency-key task_123_attempt_1
```

### 6.4 支持 clone / fork
这是量化实验里的高频操作。

### 6.5 支持 sync
离线机器和批处理系统会用到。

## 7. 建议的 Agent 工作流

一个 Agent 的完整回路通常会是：

1. `bbox search runs` 找当前最优 baseline
2. `bbox branch create --from-run`
3. `bbox run start`
4. 启动本地代码执行
5. 过程中不断 `bbox run log-event` / `bbox run log-metric`
6. 完成后 `bbox artifact upload`
7. `bbox run finish`
8. `bbox compare runs`
9. `bbox note add` 写下结论

这也是 CLI 应该优先优化的路径。
