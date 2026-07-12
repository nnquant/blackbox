# FastAPI 服务设计

## 1. 模块划分

建议服务端按以下结构组织：

```text
blackbox-server/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── projects.py
│   │   ├── researches.py
│   │   ├── branches.py
│   │   ├── runs.py
│   │   ├── artifacts.py
│   │   ├── compare.py
│   │   ├── search.py
│   │   ├── lineage.py
│   │   ├── notes.py
│   │   └── auth.py
│   ├── schemas/
│   ├── services/
│   ├── repositories/
│   ├── models/
│   ├── workers/
│   ├── websocket/
│   └── settings.py
└── webui_dist/
```

## 2. API 分组

### 2.1 Project / Research / Branch

#### Project
- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`

#### Research
- `POST /api/v1/researches`
- `GET /api/v1/projects/{project_id}/researches`
- `GET /api/v1/researches/{research_id}`
- `PATCH /api/v1/researches/{research_id}`

#### Branch
- `POST /api/v1/branches`
- `GET /api/v1/researches/{research_id}/branches`
- `GET /api/v1/branches/{branch_id}`
- `PATCH /api/v1/branches/{branch_id}`

### 2.2 Run

- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `PATCH /api/v1/runs/{run_id}`
- `POST /api/v1/runs/{run_id}/finish`
- `POST /api/v1/runs/{run_id}/fail`
- `POST /api/v1/runs/{run_id}/clone`

### 2.3 Event / Metric / Series / Note

- `POST /api/v1/runs/{run_id}/events`
- `POST /api/v1/runs/{run_id}/metrics`
- `POST /api/v1/runs/{run_id}/series`
- `POST /api/v1/runs/{run_id}/notes`
- `GET /api/v1/runs/{run_id}/events`
- `GET /api/v1/runs/{run_id}/metrics`
- `GET /api/v1/runs/{run_id}/notes`

### 2.4 Artifact

- `POST /api/v1/runs/{run_id}/artifacts/init-upload`
- `POST /api/v1/runs/{run_id}/artifacts/complete-upload`
- `POST /api/v1/runs/{run_id}/artifacts/register-external`
- `GET /api/v1/runs/{run_id}/artifacts`
- `GET /api/v1/artifacts/{artifact_id}`

### 2.5 Search / Compare / Lineage

- `POST /api/v1/search/runs`
- `POST /api/v1/search/researches`
- `POST /api/v1/compare/runs`
- `GET /api/v1/lineage/researches/{research_id}`
- `GET /api/v1/lineage/branches/{branch_id}`

### 2.6 实时接口

- `WS /ws/runs/{run_id}`
- `WS /ws/projects/{project_id}`
- `WS /ws/researches/{research_id}`

## 3. 关键请求模型

### 3.1 创建 Run

```json
{
  "project_key": "alpha-lab",
  "research_key": "csi500-reversal",
  "branch_key": "baseline-v1",
  "name": "lb20-hold5-fee10bp",
  "title": "lookback=20, hold=5, 加入手续费",
  "source_run_id": "run_01HXXXX",
  "reason": {
    "type": "implementation_change",
    "summary": "从pandas实现切换到numba实现",
    "expected_effect": {
      "runtime_sec": "down",
      "summary_metrics": "unchanged"
    }
  },
  "config": {
    "lookback": 20,
    "hold_days": 5,
    "fee_bps": 10
  },
  "context": {
    "asset_class": "CN_EQ",
    "frequency": "1d",
    "benchmark": "CSI500"
  },
  "tags": ["reversal", "baseline", "fee-model-v1"]
}
```

### 3.2 记录 Metric

```json
{
  "namespace": "strategy.summary",
  "values": {
    "annual_return": 18.0,
    "sharpe": 1.42,
    "max_drawdown": -9.0,
    "periods_per_year": 252,
    "turnover": 3.8
  },
  "point": {
    "kind": "event",
    "name": "post_cost_backtest_done"
  }
}
```

### 3.3 记录 Event

```json
{
  "event_type": "stage_completed",
  "stage": "neutralization_done",
  "payload": {
    "method": "barra_regression",
    "coverage": 0.93
  }
}
```

### 3.4 注册 Artifact

```json
{
  "kind": "report_html",
  "name": "post_cost_report",
  "path": "reports/post_cost.html",
  "metadata": {
    "stage": "post_cost_backtest_done",
    "preview": true
  }
}
```

## 4. API 设计要求

### 4.1 幂等性

所有写接口建议支持：

- `Idempotency-Key` header
- 或 `client_event_id`

因为 SDK/CLI/Agent 常会自动重试。

### 4.2 追加式写入

- `events` 应 append-only
- `metrics` 可以 append-only，再由服务汇总 summary
- `runs.finish` 应有状态机校验

### 4.3 Summary 与 Raw 分离

- `summary_metrics`：用于列表、检索、比较
- `raw_metrics` / `series` / `artifacts`：用于详情与下载

### 4.4 查询要支持结构化过滤

搜索 Run 时建议支持：

- project / research / branch
- tags
- status
- 时间范围
- metric 条件
- config 条件
- context 条件
- author_type
- has_artifact(kind)

这对 Agent 很重要。

## 5. Compare API

Compare 是量化场景的高频能力，应独立出来。

### 输入
- 一组 `run_ids`
- 指定需要比较的 metrics
- 指定需要 overlay 的 series
- 是否展开 config diff

### 输出
- run 基本信息
- metrics 对照表
- config diff
- 关键 artifacts 引用
- 可画图的 series 摘要

## 6. 后台任务

建议异步处理以下任务：

- HTML 报告截图 / 预览生成
- parquet 表 schema 抽取
- DataFrame 前几行预览
- 图像缩略图
- sweep heatmap 数据预计算
- compare cache 构建
- git patch 去重
- artifact hash 计算

## 7. 鉴权建议

V1 可采用：

- UI：cookie session
- SDK / CLI：API token
- 本地模式：可关闭 auth

后续可扩展为：

- workspace 级角色
- project 级权限
- artifact download policy
