# WebUI 设计

这里不展开前端技术栈，只描述页面应该展示什么，以及以什么形式展示。

## 1. 首页 / Dashboard

### 目标
让研究员一进来就知道：

- 最近在做什么
- 哪些 run 在跑
- 哪些失败了
- 最近有哪些新分支
- 哪些实验结果最好

### 展示形式

#### 顶部摘要卡片
显示：

- 活跃 Project 数
- 今日新增 Run 数
- 运行中 Run 数
- 最近 24h 失败数
- 最近新增 Branch 数

#### 最近活动流
用时间线展示：

- 新建 branch
- run finished / failed
- 上传报告
- Agent 写入 decision note

#### 最近优胜结果
用表格展示最近一段时间的 top runs：

- run 名称
- research / branch
- sharpe
- max drawdown
- ic_mean
- 最后更新时间

## 2. Project 页面

### 目标
展示一个项目下有哪些 Research、最近进展如何。

### 展示形式

#### Research 列表
表格字段：

- Research 名称
- 状态
- 最近更新
- branch 数
- run 数
- 当前 champion run
- 最近 summary 指标

#### 研究热力区
按 Research 展示最近活跃度，比如过去 7 天 run 数、失败率、分支数。

#### 保存视图
展示“最近看的 compare 视图”和“常用筛选条件”。

## 3. Research 页面

这是量化研究最重要的页面之一。

### 目标
把一个研究对象下的完整脉络展示出来。

### 展示形式

#### 顶部信息区
显示：

- Research 标题
- 研究目标
- 当前 hypothesis
- 标签
- champion branch / champion run
- 负责人 / 最近修改人

#### Branch Lineage 图
核心区域用 **树状图 / DAG 图** 展示：

- 各个 Branch 的继承关系
- 每个 Branch 的来源 run
- 分支原因标签
- 每个 Branch 当前状态

节点上显示最少信息：

- branch 名称
- 最近 run 数
- best metric 摘要
- 最后更新时间

#### 研究时间线
用时间线展示关键决策：

- 何时从 baseline 分出新支
- 何时更改手续费模型
- 何时引入新的 neutralization 方法
- 何时判定某分支被废弃

#### Champion 区域
单独展示当前最好的一条分支和其最佳 run，作为“当前结论”。

## 4. Branch 页面

### 目标
看清这一条思路分支内部是怎么演进的。

### 展示形式

#### Branch 信息卡
显示：

- branch 标题
- hypothesis
- 分支原因
- 来源 run
- 状态
- 标签

#### Run 序列列表
按时间倒序或 sequence 排序的表格：

- run 名称
- 状态
- 关键指标
- config diff 摘要
- 是否有报告
- 创建者（human / agent）

#### 关键曲线叠加
可选择 branch 内多个 run 叠加查看：

- 净值曲线 overlay
- 回撤曲线 overlay
- IC 曲线 overlay
- turnover 曲线 overlay

#### 配置演化视图
用 diff 形式展示每个 run 相比上一个 run 改了什么：

- lookback 改了
- fee model 改了
- neutralization 方法改了
- universe 改了

这个页面对于复盘非常重要。

## 5. Run 详情页

### 目标
让用户完整理解“一次运行到底发生了什么”。

### 页面结构建议

#### 顶部摘要区
展示：

- run 名称
- 状态
- project / research / branch
- source run
- 开始/结束时间
- 运行耗时
- tags

#### 关键指标卡片
展示最重要的 summary metrics，例如：

- annual return
- sharpe
- sortino
- max drawdown
- turnover
- ic_mean
- ic_ir
- coverage
- runtime

#### 主图区域
根据 run 类型显示最有代表性的图：

- 策略 run：净值 + 回撤
- 因子 run：IC 曲线 + 分层收益
- sweep run：参数热力图或该点结果摘要

#### Tab 区域

##### Metrics
表格形式展示所有 scalar metrics，可按 namespace 分组。

##### Events
时间线形式展示运行过程关键阶段。

##### Artifacts
卡片 + 列表形式展示：

- 报告
- 图像
- 表格
- notebook
- trades / positions

支持预览与下载。

##### Config
JSON diff 形式，支持与 source run 对比。

##### Code / Data / Env
分别展示：

- git commit / dirty / patch
- dataset version / universe / fee model
- Python / 依赖 / 容器 / hostname

##### Notes
Markdown 形式展示人和 Agent 的观察/决策。

## 6. Compare 页面

### 目标
比较多个 run，回答“谁更好，为什么更好”。

### 展示形式

#### 指标矩阵
表格列为 run，行为 metric，支持：

- 排序
- 高亮最佳
- 显示差值
- 显示相对基线提升百分比

#### Config Diff 面板
只展示有变化的配置项。

#### 曲线叠加图
支持：

- 净值
- 回撤
- IC
- turnover
- exposure

#### Artifact 对照
比如对比两个回测报告、两个 risk report、两个因子分层图。

#### Pareto 视图
当比较收益与回撤、IC 与 turnover 这类冲突指标时，可显示二维散点。

## 7. Sweep 页面

量化研究里参数遍历非常常见，建议单独有 Sweep 视图。

### 展示形式

#### 参数热力图
对于二维参数（如 lookback x hold_days），显示 heatmap，颜色为目标 metric。

#### 参数结果表
表格列出：

- 参数组合
- 指标
- 排名
- 对应 run

#### Pareto Frontier
显示多目标最优前沿，例如：

- sharpe 高
- max drawdown 低
- turnover 低

## 8. 搜索页

### 目标
让研究员和 Agent 快速找到历史实验。

### 展示形式

#### 筛选器
按：

- Project
- Research
- Branch
- 时间范围
- tags
- status
- metric 条件
- config 条件
- artifact 类型

#### 结果表
显示：

- run 名称
- branch
- key metrics
- 关键 config 摘要
- 报告存在与否
- 创建者

#### 保存视图
允许保存常用搜索条件，比如：

- “近 30 天所有 post-cost sharpe > 1 的 run”
- “所有 Barra 中性化分支”
- “所有 fee_bps=10 的回测”

## 9. WebUI 设计建议总结

WebUI 不需要一开始就做复杂交互，但必须优先支持这 5 类展示：

- **表格**
- **时间线**
- **曲线叠加**
- **DAG / Tree lineage**
- **配置 diff**

对你的场景来说，这五个比任何炫酷组件都更有价值。
