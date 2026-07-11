# blackbox 实现路线图

本文档基于 `docs/designs/00-产品概述.md` 至 `docs/designs/10-一句话版本的产品定义.md` 生成，并随当前实现持续校准。当前仓库已包含后端、SDK、CLI、WebUI 与端到端测试；本路线图保留阶段目标，同时记录已经落地的实现取舍。

> 说明：用户提到的 `docs/design` 在仓库中实际为 `docs/designs`。

## 1. 目标边界

`blackbox` 的 V1 目标是做成面向量化研究的实验图谱系统，而不是回测引擎、任务调度系统或数据仓库。

V1 必须先跑通：

- Research / Branch / Run 的核心研究图谱模型
- Event / Metric / Artifact / Snapshot 的追加式记录
- SDK 与 CLI 的稳定写入路径
- WebUI 的浏览、详情、比较、lineage 展示
- 本地模式可运行，团队服务模式可平滑扩展到 Postgres + MinIO

V1 暂缓：

- Notebook 在线编辑
- 复杂权限系统
- 拖拽式 dashboard builder
- 完整任务调度与执行引擎
- 对具体回测框架的深度绑定

## 2. 推荐仓库结构

第一步先把仓库整理为可实现结构：

```text
blackbox/
├── apps/
│   └── server/
├── packages/
│   ├── common/
│   ├── sdk/
│   └── cli/
├── webui/
├── docs/
├── scripts/
└── tests/
```

模块职责：

- `packages/common`：共享 schema、枚举、ID 生成、错误码、API 响应模型。
- `apps/server`：FastAPI 服务、SQLAlchemy 模型、内置 schema migration、对象存储适配、后台任务。
- `packages/sdk`：Python SDK，提供 `bb.init()`、`bb.log()`、artifact 上传、离线 spool。
- `packages/cli`：argparse CLI，给 Agent 和脚本使用，默认结构化输出。
- `webui`：React + Vite 前端工程，使用紧凑的研究工作台信息架构。
- `tests`：跨模块测试，尤其覆盖 SDK -> API -> DB -> Artifact 的闭环。

## 3. 技术选型

后端：

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- 内置 schema migration
- SQLite 本地模式，PostgreSQL 团队模式
- 本地文件存储本地模式，MinIO/S3 团队模式
- 后台任务 V1 先用轻量内置 worker 抽象，后续再接 ARQ/RQ/Celery

CLI / SDK：

- argparse
- httpx
- Rich 仅用于人类 table 输出
- pandas / pyarrow 作为可选依赖支持 table、series、parquet

WebUI：

- React + Vite
- ECharts / echarts-for-react
- DAG / Tree lineage 使用 ECharts tree/graph 视图
- 原生表格为主，保持紧凑、可扫描的研究工作台风格

## 4. 里程碑总览

| 阶段 | 目标 | 主要产出 |
|---|---|---|
| M0 | 工程脚手架与契约冻结 | monorepo 结构、共享 schema、API 响应规范、开发环境 |
| M1 | 后端核心元数据闭环 | Project / Research / Branch / Run / Event / Metric / Note API |
| M2 | Artifact 与 Snapshot 闭环 | 上传、注册、预览元数据、代码/数据/环境快照 |
| M3 | SDK 最小可用 | `bb.init/log/artifact/finish` 可真实写入后端 |
| M4 | CLI 最小可用 | Agent 可用的创建、查询、记录、上传、比较命令 |
| M5 | WebUI 最小可读闭环 | Dashboard、Research、Branch、Run 详情 |
| M6 | Compare 与 Lineage 增强 | Run 对比、config diff、branch lineage 图 |
| M7 | Sweep 与量化专用能力 | Sweep 模型、参数热力图、因子/策略 helper |
| M8 | Agent 与离线能力 | offline spool、sync、搜索 DSL、批量命令 |

## 5. M0：工程脚手架与共享契约

目标：所有后续模块都基于同一套类型、错误码和开发命令推进。

任务：

- 创建 `apps/server`、`packages/common`、`packages/sdk`、`packages/cli`、`tests` 目录。
- 配置 Python 包管理与开发命令，建议使用 `pyproject.toml` 管理 workspace。
- 在 `packages/common` 定义共享对象：
  - 枚举：run status、branch status、artifact kind、note kind、event type、point kind。
  - ID 规范：`prj_`、`rsr_`、`br_`、`run_`、`evt_`、`met_`、`art_`、`snp_` 等。
  - 统一响应包：`{"ok": true, "data": ..., "error": null}`。
  - 统一错误码：validation、not found、conflict、auth、storage、network。
- 建立格式化、lint、类型检查、测试命令。
- 加入本地开发配置样例：
  - SQLite URL
  - 本地 artifact 根目录
  - auth disabled

验收标准：

- `pytest` 可运行，即使只有 smoke tests。
- `apps/server` 能启动空 FastAPI healthcheck。
- `packages/common` 的 schema 可被 server、sdk、cli 共同 import。

## 6. M1：后端核心元数据闭环

目标：先把 Research / Branch / Run 作为不可变研究脉络管理起来，支持事件与指标追加。

任务：

- 建立 SQLAlchemy 模型与内置 schema migration：
  - `workspaces`
  - `projects`
  - `researches`
  - `branches`
  - `runs`
  - `run_events`
  - `run_metrics`
  - `run_notes`
- 实现 repository / service 分层：
  - repository 只处理 DB 查询与写入
  - service 处理状态机、幂等、summary 更新、lineage 关系
- 实现 API：
  - `POST /api/v1/projects`
  - `GET /api/v1/projects`
  - `POST /api/v1/researches`
  - `GET /api/v1/projects/{project_id}/researches`
  - `POST /api/v1/branches`
  - `GET /api/v1/researches/{research_id}/branches`
  - `POST /api/v1/runs`
  - `GET /api/v1/runs/{run_id}`
  - `POST /api/v1/runs/{run_id}/events`
  - `POST /api/v1/runs/{run_id}/metrics`
  - `POST /api/v1/runs/{run_id}/notes`
  - `POST /api/v1/runs/{run_id}/finish`
  - `POST /api/v1/runs/{run_id}/fail`
- 实现 run 状态机：
  - `created -> running -> completed`
  - `created -> running -> failed`
  - `created/running -> cancelled`
  - completed / failed 后禁止修改原始 config，但允许追加 note / tag / review。
- 实现 metric 写入语义：
  - 支持 event axis、iteration axis、time axis、coordinate axis。
  - 小型 scalar 入库。
  - 更新 `runs.summary_json` 用于列表、搜索、比较。
- 实现 idempotency：
  - 支持 `Idempotency-Key`
  - 或每条 event / metric 的 `client_event_id`

验收标准：

- 可以通过 HTTP 创建 project -> research -> branch -> run。
- 可以追加 event、metric、note。
- finish/fail 有状态机校验。
- 同一 idempotency key 重试不会重复写入。

## 7. M2：Artifact 与 Snapshot 闭环

目标：完成“元数据入库，大产物入对象存储”的核心架构。

任务：

- 建立表：
  - `artifacts`
  - `code_snapshots`
  - `data_snapshots`
  - `env_snapshots`
- 实现 storage 抽象：
  - `LocalFileStorage`
  - `S3CompatibleStorage`
- 实现 artifact API：
  - `POST /api/v1/runs/{run_id}/artifacts/init-upload`
  - `POST /api/v1/runs/{run_id}/artifacts/complete-upload`
  - `POST /api/v1/runs/{run_id}/artifacts/register-external`
  - `GET /api/v1/runs/{run_id}/artifacts`
  - `GET /api/v1/artifacts/{artifact_id}`
- 本地模式可以先简化为 server 接收 multipart 上传，再落本地文件。
- 团队模式再扩展为预签名 URL。
- artifact 类型先覆盖：
  - `report_html`
  - `image_png`
  - `table_parquet`
  - `table_csv`
  - `config_yaml`
  - `returns_series_parquet`
  - `trade_log_parquet`
  - `position_log_parquet`
  - `risk_report_json`
  - `notebook_ipynb`
- 实现 sha256、size、mime type 记录。
- 实现 preview 元数据占位：
  - HTML 报告：标题、大小、可预览 URL
  - CSV/Parquet：列名、行数、前 N 行
  - 图片：尺寸、缩略图路径
- Snapshot 先支持 SDK / CLI 显式提交，后续再自动采集。

验收标准：

- 可以上传一个 HTML 报告，并在 Run 详情 API 中看到 artifact 引用。
- 可以注册外部 artifact URI。
- artifact metadata 与 storage object 一致。
- 删除或缺失对象时 API 返回可解析错误。

## 8. M3：SDK 最小可用

目标：研究代码可以用低侵入方式记录一次完整回测。

任务：

- 实现 SDK 配置：
  - endpoint
  - token
  - timeout
  - offline mode
  - artifact root / spool dir
- 实现生命周期：
  - `bb.init(...)`
  - `bb.current_run()`
  - `bb.finish(status="completed")`
  - `bb.fail(error=...)`
  - context manager 异常自动 fail
- 实现记录接口：
  - `bb.log(values, namespace=None, point=None, tags=None)`
  - `bb.log_event(event_type, stage=None, payload=None)`
  - `bb.log_note(kind, summary, content=None, structured=None)`
  - `bb.set_summary(values)`
- 实现产物接口：
  - `bb.log_artifact(name, path, kind=None, metadata=None)`
  - `bb.log_bytes(name, content, kind=None, filename=None)`
  - `bb.register_external_artifact(name, uri, kind=None, metadata=None)`
  - `bb.log_table` 与 `bb.log_series` 按 artifact kind 写入 CSV 或真实 Parquet；Parquet 依赖通过 `blackbox[data]` 提供。
- 实现自动采集：
  - git commit
  - git dirty
  - hostname
  - python version
  - platform
  - pid
  - cwd
  - entry file
  - start time
- 实现基础批量 flush 与重试。

验收标准：

- 一段示例回测脚本可以创建 run、写 metrics、上传 artifact、finish。
- 脚本异常时 run 标记为 failed，且写入异常 note/event。
- SDK 每条写入带 `client_event_id`，重试不重复。

## 9. M4：CLI 最小可用

目标：Agent 可以不依赖自然语言输出完成实验编排。

任务：

- 建立 argparse 命令：
  - `bbox project create/list/get`
  - `bbox research create/list/get`
  - `bbox branch create/list/get`
  - `bbox run start/get/finish/fail/log-metric/log-event`
  - `bbox artifact upload/list/get`
  - `bbox note add/list`
  - `bbox search runs`
  - `bbox compare runs`
- 默认输出统一响应包。
- 支持：
  - `--json`
  - `--output json|table|yaml`
  - `--quiet`
  - `--select`
  - `--idempotency-key`
- 定义 exit code：
  - `0` success
  - `2` validation error
  - `3` not found
  - `4` conflict / state error
  - `5` auth error
  - `10` server / network error
- 实现 `bbox branch create --from-run`。
- 实现 `bbox run start --config-file`；配置文件支持 JSON 与 YAML，`run update --config-file`、`run clone --config-overrides-file` 保持同样解析语义。

验收标准：

- Agent 工作流可跑通：
  1. `bbox search runs`
  2. `bbox branch create --from-run`
  3. `bbox run start`
  4. `bbox run log-event`
  5. `bbox run log-metric`
  6. `bbox artifact upload`
  7. `bbox run finish`
  8. `bbox compare runs`
- 错误输出稳定可解析。

## 10. M5：WebUI 最小可读闭环

目标：人类研究员可以浏览项目、研究脉络、分支、运行详情。

任务：

- 建立前端工程。
- 接入当前 WebUI 设计语言：
  - 浅色、低饱和金融研究界面
  - 紧凑表格、指标卡、状态展示
  - 默认只读展示，显式编辑入口
- 实现页面：
  - Dashboard
  - Project 页面
  - Research 页面
  - Branch 页面
  - Run 详情页
- 先聚焦 5 类基础展示：
  - 表格
  - 时间线
  - 曲线叠加
  - DAG / Tree lineage
  - 配置 diff
- Run 详情页 Tab：
  - Metrics
  - Events
  - Artifacts
  - Config
  - Code / Data / Env
  - Notes
- server 支持托管 webui build 产物。

验收标准：

- 用户可以从 Dashboard 进入 Research，再进入 Branch 和 Run。
- Run 页面能看到 metrics、events、artifacts、snapshots、notes。
- 页面在没有数据、加载中、错误状态下都有明确展示。

## 11. M6：Compare 与 Lineage 增强

目标：支持量化研究高频问题：“谁更好，为什么更好，从哪里演化来”。

任务：

- 实现 Compare API：
  - `POST /api/v1/compare/runs`
  - 输入 run ids、metrics、series、是否 config diff
  - 输出指标矩阵、config diff、artifact 引用、series preview
- 实现 Lineage API：
  - `GET /api/v1/lineage/researches/{research_id}`
  - `GET /api/v1/lineage/branches/{branch_id}`
- 实现 config diff：
  - 对 JSON config 做结构化 diff
  - 只展示变化项
  - 支持与 source run 对比
- WebUI Compare 页面：
  - 指标矩阵
  - 最佳值高亮
  - 相对 baseline 变化
  - 曲线叠加
  - Artifact 对照
  - Pareto 散点
- WebUI Research lineage 图：
  - branch 继承关系
  - source run
  - reason code
  - branch status
  - best metric 摘要

验收标准：

- 选择多个 run 后可生成稳定 compare 结果。
- lineage 图能展示从 baseline 到分叉的研究脉络。
- Compare API 不需要加载大 artifact 原始文件即可返回摘要。

## 12. M7：Sweep 与量化专用能力

目标：把参数遍历从“很多孤立 run”提升为结构化实验集合。

任务：

- 建立表：
  - `sweeps`
  - `sweep_runs`
  - `compare_sets`
- 实现 API：
  - 创建 sweep
  - attach run to sweep
  - sweep ranking
  - sweep heatmap summary
  - compare set 保存与读取
- SDK helper：
  - `bb.log_factor_summary(...)`
  - `bb.log_factor_ic_series(df)`
  - `bb.log_quantile_returns(df)`
  - `bb.log_factor_turnover(df)`
  - `bb.log_backtest_summary(...)`
  - `bb.log_returns_series(df)`
  - `bb.log_drawdown_series(df)`
  - `bb.log_positions(df)`
  - `bb.log_trades(df)`
  - `bb.log_cost_breakdown(...)`
  - `bb.log_risk_exposure(df)`
  - `bb.attach_sweep(sweep_id, coord=...)`
- WebUI Sweep 页面：
  - 参数热力图
  - 参数结果表
  - Pareto frontier
  - 跳转对应 run

验收标准：

- 同一 sweep 下的 run 可以按参数坐标检索。
- WebUI 能展示二维参数热力图。
- SDK helper 生成的 namespace 和 artifact kind 与设计文档一致。

## 13. M8：Agent 与离线能力

目标：让 AI Agent 和批处理环境可稳定使用 blackbox。

任务：

- SDK offline mode：
  - `~/.blackbox/queue`
  - `~/.blackbox/artifacts`
  - `~/.blackbox/manifests`
  - 本地 manifest 记录 run、event、metric、artifact 的依赖关系
- CLI `bbox sync`：
  - 扫描本地 spool
  - 批量创建/补写 run
  - 上传 artifacts
  - 失败可重试
  - 输出同步报告
- 搜索 DSL：
  - project / research / branch
  - tags
  - status
  - 时间范围
  - metric 条件
  - config 条件
  - context 条件
  - author_type
  - `has_artifact(kind)`
- 批量命令：
  - 批量 compare
  - 批量 add note
  - 批量 mark branch status
- Agent 友好的结构化写入：
  - `bbox dataset register` 登记 data snapshot，避免 Agent 手写通用 snapshot JSON
- Agent 专用文档：
  - 推荐命令序列
  - 错误码处理
  - 幂等 key 生成建议
  - 已落地为本机 Codex skill：`blackbox-agent-workflow`

验收标准：

- 离线生成的 run 可以通过 `bbox sync` 恢复到服务端，包含 artifact。
- Agent 可以用 JSON 输出完成 baseline 搜索、分支创建、run 写入、结果比较、结论记录。
- 搜索结果支持 `--select` 降低上下文负担。

## 14. 测试策略

单元测试：

- schema 校验
- ID 生成
- run 状态机
- metric point 解析
- config diff
- lineage 构建
- storage path 生成

集成测试：

- SDK -> API -> DB
- CLI -> API
- artifact 上传 -> 注册 -> 查询
- finish/fail 状态迁移
- idempotency 重试
- search / compare 查询

端到端测试：

- 新建 research -> 新建 branch -> 启动 run -> 写 event/metric -> 上传 report -> finish -> compare。
- 从一个优秀 run 创建新 branch -> 新 run -> compare -> note decision。
- offline spool -> sync -> WebUI 可查看。

WebUI 测试：

- Dashboard 空状态和有数据状态。
- Research lineage 图。
- Run 详情 Tabs。
- Compare 指标矩阵和 config diff。

## 15. 第一轮实现建议

建议第一轮只做 M0 到 M3 的窄闭环，不要同时铺开完整 WebUI 和 Sweep。

第一轮具体顺序：

1. 搭建 Python workspace、server、common、sdk、cli 的最小包结构。
2. 实现 SQLite 本地模式和核心表迁移。
3. 实现 project / research / branch / run / event / metric / note API。
4. 实现本地文件 artifact 上传与注册。
5. 实现 SDK context manager 跑通一次回测记录。
6. 实现 CLI 的 `run start/log-metric/log-event/artifact upload/finish`。
7. 写一个 `examples/basic_backtest_record.py` 作为端到端验收脚本。

第一轮完成后，系统就能回答：

- 这次 run 属于哪个 research 和 branch？
- 它从哪里演化来？
- 它用了什么 config？
- 它在每个阶段记录了什么？
- 它的关键指标是什么？
- 它有哪些报告和产物？

这比先做完整 UI 更关键，因为 UI、compare、lineage 都依赖这条写入链路稳定。

## 16. 主要风险与控制

风险一：模型过早复杂化。

- 控制：M1 只实现核心表和核心 API，Sweep、CompareSet、复杂权限延后。

风险二：大文件误入数据库。

- 控制：SDK 明确区分 `log`、`log_series`、`log_table`、`log_artifact`；服务端限制 metric payload 大小。

风险三：Agent 写入重复或乱序。

- 控制：所有写接口支持 idempotency；event 使用 `sequence_no`；服务端对状态迁移做校验。

风险四：WebUI 先行导致后端契约反复变化。

- 控制：先冻结 API schema 和 summary shape，再实现页面。

风险五：本地模式和团队模式分叉。

- 控制：DB 和 storage 都走适配层；业务 service 不直接依赖 SQLite、本地文件、Postgres 或 S3。

## 17. 当前可立即执行的任务清单

- [x] 创建 monorepo 目录结构。
- [x] 建立 `packages/common` 的枚举、schema、错误码。
- [x] 建立 `apps/server` 的 FastAPI healthcheck。
- [x] 建立 SQLite 配置和内置 schema migration。
- [x] 实现 Project / Research / Branch / Run 表。
- [x] 实现 Run Event / Metric / Note 表。
- [x] 实现核心 REST API。
- [x] 实现本地 artifact storage。
- [x] 实现 SDK `bb.init()` 与 `bb.log()`。
- [x] 实现 CLI `bbox run start/log-metric/log-event/finish`。
- [x] 增加端到端示例和测试。

## 18. 当前实现状态同步

本节记录当前代码库相对 M5-M8 的状态，避免路线图停留在早期闭环阶段。

### 已完成

- [x] WebUI 接入 Dashboard / Project / Research / Branch / Run Detail / Sweep / Search / Compare 页面。
- [x] Dashboard 支持自动刷新和 WebSocket 变更触发刷新。
- [x] 顶部创建入口已收敛为导航条右侧 `New` 下拉菜单。
- [x] 导航条 API token 输入已移除，改为全局 run 搜索入口；搜索框前置图标已移除。
- [x] 右上刷新按钮已移除，刷新由自动轮询和 WebSocket 负责。
- [x] Project / Research / Branch / Run 的主要元数据展示默认只读，通过卡片右上角编辑图标进入编辑。
- [x] 只读展示信息尽量统一为单行只读字段，JSON 和长文本按摘要单行展示。
- [x] Run Detail 的 Record 写入区已收敛为紧凑操作按钮，默认不再平铺所有写入表单。
- [x] Sweep / Search View 等列表里的 objective、search space、coord、filters 已从原始 JSON 改为紧凑摘要文本。
- [x] Sweep 页面和 Branch Sweep Management 的创建/绑定表单已收敛为按需操作按钮。
- [x] Compare 页面 Batch Compare 的 Groups JSON 表单已收敛为按需展开。
- [x] Compare 页面 Batch Note 表单已收敛为按需展开。
- [x] Compare Artifact Comparison 表格的 preview 列已改为单行摘要，完整预览保留在选中详情区。
- [x] Run Detail 的 Config 与主要元数据区已统一为单行只读摘要展示，完整编辑仍通过元数据编辑入口进入。
- [x] Run Detail 的 Events / Code-Data-Env / Notes 和 Artifact 详情中的结构化只读信息已统一为单行摘要字段，避免默认暴露大块 JSON。
- [x] Search 页面 Search Controls 已从四个常驻表单收敛为按需操作按钮，默认只展示当前 filters 摘要。
- [x] Compare 页面 Compare Controls 已从常驻 Metrics / Compare Set 表单收敛为按需操作按钮，默认只展示当前比较配置摘要。
- [x] Sweep 页面和 Branch Sweep Management 的默认操作区已统一为单行只读状态字段，避免说明性占位文案和表单默认展开。
- [x] Run Detail 的 Record 默认态已统一为单行 `Current Action` 状态字段，写入表单仅在点击具体动作后展开。
- [x] Project / Research / Branch / Sweep / Search / Compare 的 Hero 区已移除泛化功能说明文案，只保留真实业务描述或上下文摘要。
- [x] Research 页面 Branch 批量状态更新已从常驻表单收敛为按需 `Batch Status` 操作按钮，默认只展示选中数量和目标状态摘要。
- [x] Compare 页面已接入指标矩阵、最佳值高亮、baseline 差值、配置 diff、series preview、artifact 对照和 Pareto 视图。
- [x] Sweep 页面已接入 sweep 列表、run attach、ranking、heatmap、结果表和 Pareto frontier。
- [x] Search 页面已接入结构化筛选、where 表达式、research 搜索、保存视图和保存视图执行。
- [x] 后端 / SDK / CLI 已覆盖 compare set、search view、lineage、sweep、dataset snapshot、offline spool 和 `bbox sync`。
- [x] 本地源码入口 `packages/cli/bbox.py` 已补齐仓库内包路径，并增加回归测试保护 `python packages/cli/bbox.py --help`。

### 后端 / SDK / CLI 到 WebUI 覆盖矩阵

| 能力域 | 后端 / SDK / CLI 能力 | WebUI 当前入口 | 状态 |
| --- | --- | --- | --- |
| Workspace / Project / Research / Branch | `workspace` / `project` / `research` / `branch` create/get/list/update | Dashboard、Project、Research、Branch 页面与顶部 `New` 菜单 | 已对接 |
| Run lifecycle | `run start/get/update/clone/finish/fail/cancel`、SDK `start_run` | Run Detail 元数据、Record -> Lifecycle / Clone | 已对接 |
| Events / Metrics / Series / Notes | `run log-event/log-metric/log-series/publish-performance`、`note add/list`、SDK `log_*`；`publish-performance` 面向 Agent 自动归一化并校验绩效结果 | Run Detail Record 动作、Events / Metrics / Notes / Primary Series / Series Preview | 已对接 |
| Artifacts | `artifact upload/init-upload/complete-upload/register-external/list/get/download`、SDK artifact helpers | Run Detail Record -> Upload / Staged Upload / External Artifact，Artifacts 详情与下载 | 已对接 |
| Snapshots / Dataset / Env | `snapshot add/list`、`dataset register`、SDK 自动 code/env snapshot | Run Detail Record -> Code / Dataset / Environment / Snapshot JSON，Code / Data / Env 页面 | 已对接 |
| Sweep | `sweep create/list/get/summary/attach-run`、SDK `create_sweep` / `attach_sweep` / `log_sweep_coord` / `get_sweep*` | Sweep 页面与 Branch Sweep Management | 已对接 |
| Search / Search View | `search runs/researches`、`search-view create/list/get/run/update`、SDK search helpers | Search 页面、Project Search Views、顶部 run 搜索入口 | 已对接 |
| Compare / Compare Set / Batch | `compare runs`、`compare-set create/list/get/update/run`、`batch compare/add-note/mark-branch-status` | Compare 页面、Project Compare Sets、Batch Compare、Batch Note、Research Branch status 批量更新 | 已对接 |
| Lineage | `lineage research/branch`、SDK lineage helpers | Research lineage、Branch lineage/context | 已对接 |
| System / Realtime | `/healthz`、auth/db/runtime status、WebSocket | Dashboard System Status、自动刷新 | 已对接 |
| Offline spool / `bbox sync` | SDK offline spool、CLI `bbox sync` | 同步后的 run/artifact/sweep 可在 WebUI 查看；执行 sync 的管理页面暂缓 | 结果可见，执行入口暂缓 |
| DB migrate | CLI `db status/migrate` | System Status 展示 DB 状态；迁移执行入口暂缓 | 状态可见，执行入口暂缓 |

### 当前目标内剩余

- [ ] 继续做窄范围 WebUI 细节巡检：只处理新发现的默认可见冗余装饰、裸 JSON、多行只读块和高度不协调字段。
- [ ] 根据每次 UI 收尾结果持续同步本节状态；当前不扩大到部署、后端重构或前端自动化测试。

### 当前目标外暂缓

- [ ] 前端自动化测试。
- [ ] 后端服务层拆分和更深的工程重构。
- [ ] 团队部署的完整环境验证。
- [ ] 专门的 offline sync 管理页面。



