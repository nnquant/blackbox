# Blackbox 页面改造与验收

日期：2026-09-14。分支：`codex/page-organization`。

改造前基线：`5984d75`，包含开始改造前工作区已有变更。`main` 未移动。所有实现沿用 React、Tailwind、Lucide、ECharts 和项目现有组件；没有引入 antd、数据库迁移、新权限体系或新研究准入规则。

指南实际文件：`D:\project\blackbox\docs\fe-page-guide-antd.md`。原文 SHA-256 再次核对为 `a4c0087db75c1243600060fc735d8df2d78bc2197e6fe9835d4bb797fc68e1ba`。

## 已确认的业务选择

- 代表 Run：人工基准优先，其次已完成 Run 的最高有效主指标，最后取最新 Run。0 是有效指标；空值、布尔值、非有限数不参与排名。并列时按更新时间、创建时间、ID 确定稳定顺序。
- 当前模型没有独立的人工基准 Run 字段，因此复用**活跃研究地图的基准节点明确绑定的 Run**。绑定 Branch 或 Research 的节点是动态证据，不假称人工选定了某次 Run。多个活跃地图指定不同 Run 时，从当前候选范围中的人工基准取最近 Run；不修改地图指针。
- 通用研究/分支/快捷比较继续使用现有主指标 `strategy.summary.sharpe`；地图使用该图的 `primary_metric`。不把最高值等同于已批准策略。
- 研究线默认“研究脉络”，地图优先；同一浏览器标签页记住已切换的视图。
- 比较继续允许跨样本、跨费用；展示已记录字段的差异和未知项，不新增自动通过或阻断规则。既有服务端结果质量门保持生效。
- 比较页手动选择的基准只影响该页差值和 URL，不修改研究地图的正式基准。

## 各页面落地情况

| 页面 | 实际变化 | 指南依据 |
|---|---|---|
| 总览 | 增加页面标题和全局观察范围；压缩主要统计；最近结果、待复核 Run、研究代表结果先于项目目录与活动热图 | §2.1、§3.1–3.3 |
| 项目 | 研究线表前置，合并重复的活动表；保留目标、7 日 Run/失败数、状态、代表证据；元数据放入项目设置，地图/保存视图/快捷比较保留 | §2.3、§3.6、§4.2 |
| 研究线 | 单层“研究脉络 / 分支与 Run / 评审记录 / 来源与历史”；默认地图；从 Run/分支定位地图时切回地图视图；评审动作编码改为可读名称 | §2.2、§2.5、§4.5 |
| 分支 | 指标演进与配置演进移出折叠上下文，靠近 Run 序列；本分支 Run 表隐藏重复的分支列；代表 Run 显示选择依据 | §2.4、§4.2、§4.8 |
| Run 查询 | 明示最多加载 1000 条、仅在已加载范围筛选；关键词/项目/状态优先，高级条件可展开；默认主要列，完整列可切换；筛选、排序、页码和列设置保存在 URL | §3.3、§3.5、§4.2 |
| Run 详情 | 精简身份重复；状态操作移到对象头附近；运行中/失败默认事件视图；完整 JSON 配置替代前三项摘要；Tab 支持方向键、Home/End 和 ARIA；质量提示与研究结论分开 | §4.4、§4.6、§4.8、§4.11 |
| 对比目录 | 名称优先；新建对比入口前置；筛选无匹配和真正空目录分开；全局目录不继承之前项目的面包屑 | §2.3、§3.5、§4.2 |
| 对比详情 | 基准选择、样本/费用/资产数据口径先于摘要；指标矩阵与配置差异前置；明确百分比、百分点、比值单位；“可决策”改为“已生成对比 · 研究结论待评审”；请求失败不显示“配置一致” | §2.4、§3.1、§4.8 |
| 搜索 | 默认展开 Run 常用条件；高级指标使用字段—运算符—值布局；保留 JSON/Where/保存视图；按 Run 或研究线显示一个结果区；支持条件重置与 URL 恢复 | §3.5、§4.10–4.11 |
| 地图 | 错误/空目录/无匹配分开，有重试；侧栏/内嵌错误不再吞掉；节点、搜索和详情视图可恢复；地图标题可键盘打开；方向键平移、加减缩放、Home 适应窗口；去向筛选明确是淡化；窄屏适应窗口修正；统一 UTC 时间解析 | §2.4、§3.5、§4.5、§4.8 |
| 研究资产 | 14 天巡检口径明确；陈旧运行和陈旧研究线先于占用排行；继续只读，不增加清理或停止执行器操作 | §2.3、§3.2、§4.6 |

主题开关沿用基线中已统一的同一组件，深浅色均为 32×32px。研究地图继续使用随容器宽度伸缩的布局。

## 检查结果

- `npm run build`：通过，Vite 6.4.2，2415 个模块。项目没有既有 lint/typecheck 脚本，不宣称这些检查通过。
- `python -m pytest tests --basetemp=work/page-review/full-tests -o cache_dir=work/page-review/pytest-cache -q --tb=short`：**128 passed，10.32 秒**。包括既有 API、鉴权、地图、SDK/CLI、质量校验，以及新增 8 项代表 Run 测试。
- `node --test webui/src/representative.test.mjs`：**2 passed**。覆盖人工/最高/最新优先级、零值和负值，以及费用比较的 0、false、null、未提供区分。
- `git diff --check`：通过。
- Windows 项目 `.venv` 的基础 Python 路径不可访问，使用已可运行的 `D:\miniconda3\python.exe`；测试缓存、数据库、产物及临时文件均在仓库 `work/page-review/`。该目录不提交到 Git。

## 页面交互验证

浏览器用 `http://127.0.0.1:8021` 隔离实例；数据库 `D:\project\blackbox\work\page-review\ui-data\blackbox.db`，产物目录位于同级 `artifacts/`。没有向现有研究后端写状态、重启现有服务或发布部署。

截图对照使用同一隔离实例、相同初始 8 个 Run，1 项目、4 研究线、1 分支、1 地图、1 对比集。改造前页面来自 `5984d75` 对应的已构建静态资源，临时在 4174 端口访问，同样读取隔离后端。故对照主要证明页面表达变化，代表 Run 后端规则由专项 API 测试证明。

用于曲线和指标展示的合成序列为 **2025-01-01 至 2025-01-28，共 28 行**；采用项目既有 `compute_performance_summary` 计算与曲线一致的指标，不作为量化研究结果。样本窗字段故意与另一个候选不同，用于口径提示验收；界面不据此推导业务等价性。

| 场景 | 页面实际操作与结果 |
|---|---|
| 代表 Run | 较低 Sharpe 的人工基准优先于较高候选；Dashboard、项目、研究搜索、分支快捷比较及地图绑定由 API 回归统一验证 |
| 字段比较 | 查看费用 `10 / 0 / 10`、训练/验证样本、起始日差异；配置 `false / true` 保持原值；手动切到零值 Run 基准后差值更新，基准为 0 时不产生无穷百分比 |
| 比较恢复 | 切换基准写入 URL；刷新后保留基准与指标矩阵 |
| Run 查询恢复 | 选已完成、打开完整列、进入 Run、从导航返回、刷新，条件与完整列保持 |
| 分页 | 截图对照后另新增 51 条分页专用 Run，总数 59；按关键词查到 51 条，50+1 分页；第二页刷新仍为第二页；跨页勾选显示“已选择 2 个 Run” |
| 完成 | “状态验收 · 完成”调用既有 finish，回读 `completed`，终态按钮禁用 |
| 失败 | “状态验收 · 失败”写入测试原因，回读 `failed`，终态按钮禁用 |
| 取消 | “状态验收 · 取消”写入测试原因，回读 `cancelled`，终态按钮禁用；提示明确不保证远程进程停止 |
| 分支编辑 | 基准分支由 active 改 paused，保存“隔离页面验收”原因后成功回读 |
| 地图 | 搜索“跨样本”定位节点；刷新深链接后节点和查询保留；Home 适应窗口；不存在的地图显示错误与重试，没有“空地图”误报 |
| 键盘 Tab | Run 配置 Tab 按右方向键移到上下文，选中状态和键盘焦点同步 |
| 产物 | 打开 returns_series 产物预览，看到日期和收益字段；原文件、下载入口保留；原 API 测试覆盖产物读取 |
| 搜索 | 常用状态条件可直接执行；已完成结果正确显示；高级字段和原始 JSON 能力保留 |

没有在真实后端执行任何生命周期操作。模拟网络中断、所有文件格式的浏览器下载、屏幕阅读器实机和全部异常组合未逐一穷举；已有接口测试不能替代这些人工验收。

## 响应式与主题

地图测量结果（单位 px，详见截图目录 `layout-checks.json`）：

| 浏览器宽度 | 地图容器 | 树画布 | 详情区域 | 结构 |
|---:|---:|---:|---:|---|
| 390 | 349 | 349 | 349 | 上下；调用适应窗口后 5 个节点均在画布横向范围内 |
| 768 | 463 | 463 | 463 | 上下 |
| 1024 | 726 | 426 | 300 | 左右 |
| 1440 | 1142 | 822 | 320 | 左右，另验证深色 |
| 1920 | 1622 | 1202 | 420 | 左右 |
| 3440 | 3142 | 2722 | 420 | 左右，解除宽度上限后继续扩展 |

这些宽度下均未出现文档整体横向溢出。Run 查询在 1024px 下：查询栏 711px、默认表格 820px，表内横向滚动；相比检查阶段默认 1810px 的宽表明显缩短。390px 高级查询栏 349px，条件纵向排列。完整列仍需表内滚动，以保留逐字段比较能力。

## 截图索引

完整目录：`D:\project\blackbox\docs\page-implementation-2026-09-14\`，共 **39 张 PNG**，主要页面配有 DOM 快照。11 组主要布局对照均在 1440×1000 视口采集；后续状态、分页和窄屏截图另标，不与初始 8 Run 混作同一数值快照。

| 页面 | 改造前 | 改造后 |
|---|---|---|
| 总览 | [before](page-implementation-2026-09-14/dashboard-before.png) | [after](page-implementation-2026-09-14/dashboard-after.png) |
| 项目 | [before](page-implementation-2026-09-14/project-before.png) | [after](page-implementation-2026-09-14/project-after.png) |
| 研究线 | [before](page-implementation-2026-09-14/research-before.png) | [after](page-implementation-2026-09-14/research-after.png) |
| 分支 | [before](page-implementation-2026-09-14/branch-before.png) | [after](page-implementation-2026-09-14/branch-after.png) |
| Run 查询 | [before](page-implementation-2026-09-14/runs-before.png) | [after](page-implementation-2026-09-14/runs-after.png) |
| Run 配置 | [before](page-implementation-2026-09-14/run-config-before.png) | [after](page-implementation-2026-09-14/run-config-after.png) |
| 对比目录 | [before](page-implementation-2026-09-14/compare-list-before.png) | [after](page-implementation-2026-09-14/compare-list-after.png) |
| 比较详情 | [before](page-implementation-2026-09-14/compare-before.png) | [after](page-implementation-2026-09-14/compare-after.png) |
| 搜索 | [before](page-implementation-2026-09-14/search-before.png) | [after](page-implementation-2026-09-14/search-after.png) |
| 地图 | [before](page-implementation-2026-09-14/map-before.png) | [after](page-implementation-2026-09-14/map-after.png) |
| 资产管理 | [before](page-implementation-2026-09-14/management-before.png) | [after](page-implementation-2026-09-14/management-after.png) |

补充：[窄屏适应窗口最终验证](page-implementation-2026-09-14/map-fit-390-final.png)、[超宽屏最终验证](page-implementation-2026-09-14/map-3440-final.png)、[深色地图](page-implementation-2026-09-14/map-1440-dark.png)、[跨页选择](page-implementation-2026-09-14/pagination-selection.png)。主要布局截图后的少量字段提示/时间修正，以最终源码和补充验证为准。

## 保留边界与人工判断

1. 真正全库 Run 查询的服务端分页/排序不在本轮实施；目前明确限制为已加载最多 1000 条。没有扩大扫描范围。
2. 未统一的自定义样本、费用、资产、数据版本字段只能提示“未提供/未校验”。已识别字段一致也不等于样本、费用口径具有业务等价性，仍需研究人员判读。
3. 多张活跃地图存在不同人工基准时，目前按当前候选范围内最近 Run 处理；若需要单一全局基准或跨主指标“最高”方向配置，需要新增明确业务契约。
4. 地图详情已用支持地图接口的隔离实例验证；先前现有 8013 后端不支持地图接口的问题不因前端改造自动解决。切到实际使用环境时需匹配该分支后端版本。
5. Run 终态是记录状态；未验证与远程策略执行器中止的联动。地图仍只读，Sweep 入口继续关闭。
6. 地图折叠、平移和缩放保持当前视图交互；可分享链接保存节点、搜索与详情视图，不声称保存每次平移坐标。大树在窄屏仍需要缩放或平移，不把节点挤成无法阅读的小字。

## 回退方式

在工作区无未保存变更时，从基线新开回退分支即可恢复改造前文件，同时保留当前改造分支：

```powershell
git switch -c codex/page-organization-rollback 5984d75
```

不要使用 `reset --hard` 删除后续工作。若已经切换实际服务版本，回退源码后还需重新构建前端并按原项目方式启动匹配的后端。本轮没有执行部署。
