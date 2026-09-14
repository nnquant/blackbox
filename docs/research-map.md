# Research Map (研究地图)

A research map is a **manually maintained tree** of research nodes. Every node carries a short narrative (hypothesis, change, reading, verdict, caveats, next step), a lifecycle **stage**, a review **decision**, and at most one **binding** to a Blackbox entity (run, branch, compare set, or research). The WebUI renders the tree with a structured detail panel: verdict first, then a metric comparison against the parent and the baseline, then changes, reading, caveats, evidence, and revisions.

**Principle: structure and narrative are written by hand; evidence is read automatically.** Agents decide which nodes exist, where they hang, what was tested, and what was concluded. Metrics, quality-gate status, artifacts, and decision notes come from the bound entity and are never stored in the map. Blackbox never creates nodes, changes a stage or a decision, or moves the baseline on its own.

## Scope

- A map belongs to a project and may optionally be attached to one research line. A project can hold several maps, and a map may bind entities from different research lines.
- The research page embeds every map that is attached to that research or binds one of its runs, branches, or compare sets.
- Map keys are unique within the project. Address a map by id (`rmap_...`) or `<project-key>/<map-key>`.
- Node keys are unique within a map: short stable slugs (`hold`, `h20`, `tail-delta`) chosen by the agent. Renaming a key creates a new node.

## Two axes: stage and decision

| Stage (ordered) | Meaning | Blackbox counterpart |
| --- | --- | --- |
| `idea` | Written down, no binding, not registered | — |
| `hypothesis` | Registered: the one thing to test is written, usually a branch exists | Branch |
| `experiment` | A backtest is running or finished | Run (`mode=backtest`) |
| `validation` | Out-of-sample / robustness / cost review, optional | Run + review board |
| `tracking` | Forward signals recorded, no trading | Run (`mode=paper`) |
| `simulation` | Simulated trading with execution | Run (`mode=sim`) |
| `live` | Real money | Run (`mode=live`) |
| `retired` | Was simulated or live, now switched off | — |

| Decision (written at review) | Meaning |
| --- | --- |
| *(empty)* | Undecided |
| `pending` | Results seen, no conclusion yet |
| `kept` | Not on the mainline, kept as a lead |
| `accepted` | Holds; the gate into validation / tracking / simulation / live |
| `rejected` | Refuted or stopped |
| `superseded` | Replaced by a child node; read the child instead |

Rules:

- Stages only move forward. Moving back requires a `reason`, which is recorded in the revisions.
- Colour on the map follows the decision family (in progress / accepted / kept / ended); the card text shows the stage.
- The **baseline** is a map-level pointer (`baseline`) to one node. The **mainline** is derived: the path from the root to the baseline. Neither is a node field.
- `bbox map lint` warns when an accepted node has no binding, when its run fails the quality gate, or when tracking / simulation / live nodes are not accepted.
- Runs carry a `mode` (`backtest`, `paper`, `sim`, `live`) so tracking, simulation, and live evidence can be bound exactly like backtests.

## Node fields and how to write them

| Field | Who | Limit (lint warns) | How to write |
| --- | --- | --- | --- |
| `title` | agent | ≤ 14 chars | Noun phrase: what was done, not the conclusion |
| `hypothesis` | agent | one sentence, ≤ 50 chars | The single thing this node tests |
| `change[]` | agent | ≤ 3 | Relative to the parent: `{what, from, to}` objects (plain strings allowed) |
| `reading[]` | agent | ≤ 3, each ≤ 40 chars | Facts with numbers; no judgement |
| `verdict` | agent | one sentence, ≤ 60 chars | Starts with the decision verb + reason; matches `decision` |
| `caveats[]` | agent | ≤ 3 | Unverified items, sample issues, cost sensitivity |
| `next` | agent | one sentence | Optional; most useful for idea / hypothesis / kept |
| `stage`, `decision` | agent | enums above | |
| `binding` | agent | one entity | `{kind: run|branch|compare_set|research, id}`; a branch binds its best run by `primary_metric` |
| `refs[]` | agent | — | Extra links: `run`, `branch`, `compare_set`, `artifact`, `sweep`, `research`, `project`, `url`, `file` |
| `date_label` | agent | ≤ 12 chars | Short text on the card, e.g. `09-07 user pick` |
| metrics / quality / artifacts / notes / comparison / mainline / flags / revisions | system | — | Read from the bound entity or derived; never written by agents |

Long text (background, methodology, full reports) belongs in a run note (`kind=review`) or a report artifact; keep only a ref on the node.

## Agent workflow

```powershell
# 1. Create the map once (idempotent)
bbox map init --project quadrant-lab --research quadrant-options --key quadrant-options-tree --title "象限期权研究树" --created-by-id agent-alpha

# 2. Register a node while starting the experiment (binds the run)
bbox map node set --map quadrant-lab/quadrant-options-tree --key roll --parent hold --title "ROLL95 换回 50Δ" --stage experiment `
  --hypothesis "Delta ≥0.95 时换回 50Δ 重置凸性，能否提高净收益？" --change "高 Delta 处理|持有到全平|Delta ≥ 0.95 卖出，换回同到期 50Δ Call" `
  --run run_roll --created-by-id agent-alpha --agent-output

# 3. Results arrive through the normal run flow; the card shows the metric automatically and the node is flagged "ready"

# 4. Decide: decision + reading + verdict, and the same sentence as a decision note on the run
bbox map node decide --map quadrant-lab/quadrant-options-tree --key roll --decision rejected `
  --reading "配对 73 组 −35.6bp，区间跨零" --verdict "否决：重置凸性没有可分辨的增益，回撤更深。" --note --created-by-id agent-alpha

# 5. Advance an accepted node through the lifecycle
bbox map node advance --map quadrant-lab/quadrant-options-tree --key hold --stage validation --date 09-14

# 6. Move the baseline (reason required for the record)
bbox map baseline --map quadrant-lab/quadrant-options-tree --key hold --reason "用户选为后续 S2 研究的比较基准" --created-by-id human:jiang --created-by-type human

# 7. Review
bbox map status --map quadrant-lab/quadrant-options-tree   # ready / stale / not advanced / broken bindings / runs without a node
bbox map lint --map quadrant-lab/quadrant-options-tree     # field limits and consistency
bbox map revisions --map quadrant-lab/quadrant-options-tree --key hold
```

Document style maintenance writes the same data:

```powershell
bbox map export --map quadrant-lab/quadrant-options-tree --output-file research-map.yaml
bbox map import --file research-map.yaml --created-by-id agent-alpha --agent-output          # merge (upsert by key)
bbox map import --file research-map.yaml --replace --created-by-id agent-alpha                # also delete nodes missing from the document
```

Document format (JSON or YAML; nested `children` or flat entries with `parent_key`):

```yaml
project: quadrant-lab
research: quadrant-options
key: quadrant-options-tree
title: 象限期权研究树
baseline: hold
primary_metric: strategy.summary.sharpe
settings: {collapsed: [exec, drift], file_base_url: https://github.com/org/repo/blob/main}
nodes:
  - key: root
    title: 老海龟 CTA
    stage: live
    decision: accepted
    binding: {kind: research, id: rsr_...}
    children:
      - key: hold
        title: HOLD（当前基准）
        stage: experiment
        decision: accepted
        hypothesis: 进入高估高波不退出……右尾能否完整保留？
        change:
          - {what: 退出规则, from: 满 10 日后离开即退, to: 只在估值翻转到低估或高估高波变老时全平}
        reading: [逐年 2022→2026：+9.3 / +24.6 / +85.3 / +167.4 / +29.3%]
        verdict: 采纳为比较基准：不因波动膨胀退出，右尾完整保留。
        caveats: [2024/25 贡献集中, C2 成本情景敏感]
        binding: {kind: run, id: run_...}
```

Tips:

- Pass Chinese text through `--fields-file` or the document on Windows; shell arguments can be mangled by the console code page.
- `--change` accepts `what|from|to`, `what|to`, or free text.
- Always pass `--created-by-id`; it appears on the node, in revisions, and on the decision note.

## SDK

```python
import blackbox as bb

bb.import_research_map(document, created_by_id="agent-alpha")
bb.set_research_map_node("quadrant-lab/quadrant-options-tree", "roll", title="ROLL95 换回 50Δ", parent_key="hold", stage="experiment",
                         hypothesis="...", change=[{"what": "高 Delta 处理", "from": "持有到全平", "to": "Delta ≥ 0.95 卖出"}],
                         binding={"kind": "run", "id": "run_roll"}, created_by_id="agent-alpha")
bb.decide_research_map_node("quadrant-lab/quadrant-options-tree", "roll", "rejected", verdict="否决：……", reading=["配对 73 组 −35.6bp"], note=True, created_by_id="agent-alpha")
bb.advance_research_map_node("quadrant-lab/quadrant-options-tree", "hold", "validation")
bb.set_research_map_baseline("quadrant-lab/quadrant-options-tree", "hold", reason="用户选定", created_by_id="human:jiang", created_by_type="human")
bb.research_map_status("quadrant-lab/quadrant-options-tree")
detail = bb.get_research_map("quadrant-lab/quadrant-options-tree")   # nodes with binding evidence, flags, mainline, tree
```

## REST API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/research-maps` | Create (idempotent on project + key) |
| `GET` | `/api/v1/research-maps?project=&research=&key=&status=` | List with counts, baseline summary, recent nodes |
| `GET` | `/api/v1/projects/{id}/research-maps`, `/api/v1/researches/{id}/research-maps` | Maps for a scope (research: attached or bound) |
| `GET` | `/api/v1/research-maps/{id}` | Map + `nodes` (with `binding` evidence, `family`, `flags`, `is_mainline`) + `tree` |
| `PATCH` | `/api/v1/research-maps/{id}` | Title, subtitle, description, status, primary_metric, settings, research |
| `POST` | `/api/v1/research-maps/{id}/baseline` | `{node_key, reason}`; recorded as a revision |
| `GET` | `/api/v1/research-maps/{id}/status` · `/lint` · `/revisions?node_key=` · `/export` | Health check, lint, change log, document |
| `POST` | `/api/v1/research-maps/import` | Document import (creates the map when missing; `mode: merge|replace`) |
| `POST` | `/api/v1/research-maps/{id}/nodes` · `/nodes/import` | Create node (idempotent on key) · import a node list |
| `GET`/`PUT`/`PATCH`/`DELETE` | `/api/v1/research-maps/{id}/nodes/{key}` | Read · upsert · update · delete (`?cascade=true`) |
| `POST` | `/api/v1/research-maps/{id}/nodes/{key}/decide` | `{decision, reading, verdict, caveats, next, note}` |
| `POST` | `/api/v1/research-maps/{id}/nodes/{key}/advance` | `{stage, reason, date_label}` |

Errors use the standard envelope: `NOT_FOUND` for unknown maps, nodes, parents, or binding targets; `VALIDATION_ERROR` for cycles, backwards stages without a reason, duplicate keys in a document, or a baseline that matches no node; `STATE_ERROR` when deleting a node that still has descendants. Every write publishes `research_map.created` / `research_map.updated` over the websocket.

## WebUI

- **Research page**: the map is embedded at the top (fullscreen available). The branch table and the recent-runs table show a **Map node** column with a *Locate* action; selecting a node in the map is independent of those tables.
- **Research Map** in the sidebar lists every map. The map page shows the baseline strip (metrics from the bound run), the decision / stage legend with filters, recent updates, the tree, and the structured node detail.
- The WebUI is read-only for maps. Edits go through the CLI, SDK, or API.

## Example

`examples/research-maps/quadrant-options-tree.json` is a 39-node map in this format. Load it into a local server:

```powershell
bbox project create --key quadrant-lab --title "象限期权实验室"
bbox research create --project quadrant-lab --key quadrant-options --title "估值-波动率象限 × 期权表达"
bbox map import --file examples/research-maps/quadrant-options-tree.json --created-by-id codex --agent-output
```
