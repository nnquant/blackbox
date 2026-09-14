# Agent Workflow Guide

This guide is the operational contract for AI agents and batch jobs that write to Blackbox through `bbox`, the Python SDK, and the WebUI-backed API.

## Defaults

- CLI entrypoint: `bbox`
- SDK import: `import blackbox as bb`
- API response envelope: `{"ok": true, "data": ..., "error": null}`
- Default endpoint: `http://127.0.0.1:8000`, or `BLACKBOX_ENDPOINT`
- Token environment: `BLACKBOX_TOKEN` or `BLACKBOX_API_TOKEN`
- Default local data directory: `~/.blackbox`
- Offline spool layout: `~/.blackbox/queue`, `~/.blackbox/artifacts`, `~/.blackbox/manifests`
- Preferred performance publisher: `bbox run publish-performance`. It normalizes safe structural differences, runs strict preflight, uploads, validates stored rows, and optionally finishes the run.
- Low-level upload preflight: pass `--strict-contract` on `bbox run log-series` / `bbox run log-metric`, or set `BLACKBOX_AGENT_STRICT_UPLOAD=1`. Use `--skip-upload-validation` only for an explicit legacy/manual override.
- Upload diagnostics: add `--agent-output` for compact `code`/`field`/`fix` issues. Full CLI/API failures retain diagnostics under `error.details.issues`; SDK failures expose `UploadValidationError.report["issues"]`.

For agent automation, prefer JSON output and narrow payloads:

```powershell
bbox search runs --where 'metrics.strategy.summary.sharpe > 1 and tags contains "baseline"' --select id,name,status,branch_key,summary_json --json
```

Global flags such as `--json`, `--select`, `--endpoint`, `--token`, and `--agent-output` can be placed before or after the subcommand.

## Recommended Online Loop

1. Find a baseline candidate.

```powershell
bbox search runs `
  --where 'metrics.strategy.summary.sharpe > 1 and tags contains "baseline" and has_artifact(report_html)' `
  --select id,name,branch_id,branch_key,summary_json,config_json `
  --json
```

2. Fork a branch from the chosen run.

```powershell
bbox branch create `
  --research csi500-reversal `
  --key agent-fee-model-v2 `
  --title "Agent Fee Model V2" `
  --from-run run_abc `
  --parent-branch-id br_baseline `
  --reason-code agent_hypothesis `
  --reason-summary "Test a more conservative post-cost fee model" `
  --json
```

3. Start a run with a stable idempotency key.

```powershell
bbox run start `
  --project alpha-lab `
  --research csi500-reversal `
  --branch agent-fee-model-v2 `
  --name fee-model-v2-run-001 `
  --source-run-id run_abc `
  --created-by-type agent `
  --created-by-id agent-alpha `
  --config-file .\config.json `
  --tags '["agent","fee-model"]' `
  --idempotency-key agent-task-123-run-start `
  --json
```

4. Write events, metrics, series, and artifacts.

```powershell
bbox run log-event --run-id run_new --event-type stage_started --stage backtest --payload '{"step":"backtest"}' --client-event-id agent-task-123-evt-backtest-start --json

bbox dataset register `
  --run-id run_new `
  --dataset-name csi500_daily `
  --dataset-version 2026-05-20 `
  --fingerprint sha256:abc123 `
  --universe CSI500 `
  --benchmark 000905.XSHG `
  --calendar XSHG `
  --time-range '{"start":"2020-01-01","end":"2026-05-20"}' `
  --metadata '{"vendor":"rqdata","adjustment":"post"}' `
  --json

bbox artifact upload --run-id run_new --name post_cost_report --kind report_html --path .\report.html --idempotency-key agent-task-123-art-report --json

bbox run publish-performance `
  --run-id run_new `
  --curve-file .\equity.csv `
  --mode nav `
  --periods-per-year 252 `
  --summary '{"turnover":0.42}' `
  --summary-unit decimal `
  --idempotency-prefix agent-task-123-performance `
  --expected-start 2023-01-03 `
  --expected-end 2026-05-07 `
  --expected-rows 820 `
  --finish `
  --fail-on-warning `
  --agent-output
```

5. Finish or fail the run.

`publish-performance` derives annual compound return, annual volatility, max drawdown, Sharpe, Sortino, and Calmar from the full primary curve. It stores `periods_per_year` separately so Run Detail can show the annualization period in its own card. `--finish` performs the post-upload validation and finish quality gate. Omit `--finish` when more artifacts still need to be attached, then run `bbox run finish --run-id run_new --fail-on-warning --agent-output` after the remaining writes.

Run Detail shows a Result Summary panel above the tabs. Use it as the first check for primary curve, date range, result domains, key metric coverage, artifact counts, update time, and quality status. Expand Result diagnostics when present; each issue includes a suggested fix command.

Result templates are registry-driven in WebUI. Built-in domains cover `performance`, `factor`, `factor_batch`, `risk`, `cost`, and `diagnostic`. To extend rendering without changing application code, set `window.BLACKBOX_RESULT_TEMPLATES` before app boot or store JSON in localStorage key `blackbox.resultTemplates`; use the same shape as the built-in domain registry, for example `{"event_study":{"blocks":[{"title":"Event Returns","roles":["event_curve"],"chart":true}]}}`.

```powershell
bbox run fail --run-id run_new --error '{"code":"BACKTEST_ERROR","message":"input data missing"}' --json
```

6. Compare against baseline and record the decision.

```powershell
bbox compare runs --run-ids run_abc run_new --metrics strategy.summary.sharpe,strategy.summary.max_drawdown --series equity_curve --json

bbox research review --research-id res_csi500_reversal --metric strategy.summary.sharpe --stale-days 14 --json

bbox note add `
  --run-id run_new `
  --kind decision `
  --summary "Promote fee model v2 for review" `
  --content "Higher Sharpe with lower drawdown than baseline." `
  --structured '{"baseline":"run_abc","candidate":"run_new","promote":true}' `
  --author-type agent `
  --client-event-id agent-task-123-note-decision `
  --json
```

`bbox research review` returns the current research state, ranked candidate set, saved compare sets, decision notes, and conservative archive suggestions. It does not mutate branch status; use `bbox batch mark-branch-status --status archived` only after reviewing the suggested archive queue.

The WebUI will show the resulting run, artifacts, compare output, lineage, notes, and creator/source fields after refresh or websocket update.

## Research Map Maintenance

A research map is the agent's hand-maintained tree of research nodes. Each node has a lifecycle **stage** (`idea → hypothesis → experiment → validation → tracking → simulation → live → retired`), a review **decision** (`pending | kept | accepted | rejected | superseded`, empty while undecided), a short narrative (hypothesis, change, reading, verdict, caveats, next), and at most one **binding** to a run, branch, compare set, or research. Metrics, quality-gate status, artifacts, and decision notes are read from the bound entity; Blackbox never creates nodes, changes stages or decisions, or moves the baseline by itself.

Register the node when you start the experiment, decide when the results are in, advance accepted nodes through the lifecycle:

```powershell
bbox map init --project alpha-lab --research csi500-reversal --key csi500-map --title "CSI500 reversal map" --created-by-id agent-alpha

bbox map node set --map alpha-lab/csi500-map --key fee-v2 --parent baseline --title "Fee model v2" --stage experiment `
  --hypothesis "A conservative post-cost fee model keeps the right tail?" `
  --change "fee per side|5bp|10bp" --run run_new --created-by-id agent-alpha --agent-output

bbox map node decide --map alpha-lab/csi500-map --key fee-v2 --decision kept `
  --reading "sharpe 1.30 vs baseline 1.21" --reading "max_drawdown -8.1% vs -9.4%" `
  --verdict "Keep: better Sharpe and drawdown; compare against baseline before promotion." `
  --caveat "single fee assumption, not swept" --note --created-by-id agent-alpha

bbox map node advance --map alpha-lab/csi500-map --key fee-v2 --stage validation --date 2026-09-14
bbox map baseline --map alpha-lab/csi500-map --key fee-v2 --reason "promoted after robustness review" --created-by-id agent-alpha
bbox map node update --map alpha-lab/csi500-map --key fee-v1 --decision superseded --verdict "Superseded by fee-v2."
bbox map node delete --map alpha-lab/csi500-map --key abandoned --cascade
```

Review and document-style maintenance:

```powershell
bbox map status --map alpha-lab/csi500-map      # results without a decision, stale experiments, accepted but not advanced, broken bindings, runs without a node
bbox map lint --map alpha-lab/csi500-map        # field limits (title ≤ 14, hypothesis ≤ 50, ≤ 3 changes / readings / caveats, verdict ≤ 60) and consistency
bbox map export --map alpha-lab/csi500-map --output-file .\research-map.yaml
bbox map import --file .\research-map.yaml --created-by-id agent-alpha --agent-output   # merge by key; add --replace to prune
```

Rules:

- `decide --note` writes the verdict as a `kind=decision` note on the bound run, so the review board and the map never disagree. Use it instead of a separate `bbox note add` for map decisions.
- Stages only advance; moving back needs `--reason` and is recorded in `bbox map revisions`.
- Accepted nodes should bind a run that passes the quality gate; tracking / simulation / live nodes should be accepted. `map lint` reports both.
- Use `run start --mode paper|sim|live` for forward-tracking, simulated, and live runs so they can be bound to the matching stages.
- Keep node keys stable, pass `--created-by-id`, and put long text in run notes or report artifacts, not in the map.
- Prefer `--fields-file` or the document for long Chinese text on Windows; shell arguments can be mangled by the console code page.

Document format, SDK helpers (`bb.set_research_map_node`, `bb.decide_research_map_node`, `bb.advance_research_map_node`, `bb.set_research_map_baseline`), and the REST API are described in `docs/research-map.md`.

## Batch Operations

Use batch commands when an agent needs one machine-readable report for many targets.

```powershell
bbox batch compare --run-ids run_1 run_2 run_3 --metrics strategy.summary.sharpe,strategy.summary.max_drawdown --json
```

```powershell
bbox batch add-note --run-ids run_1,run_2 --kind decision --summary "Keep for review" --structured '{"review":true}' --author-type agent --json
```

```powershell
bbox batch mark-branch-status --branch-ids br_1,br_2 --status accepted --json
```

Batch responses include `success_count`, `failure_count`, and per-item results. Treat any non-zero `failure_count` as a partial failure and retry only failed targets.

## Offline Loop

Use offline mode when the agent runs where the API is unavailable.

```powershell
$env:BLACKBOX_OFFLINE = "1"
$env:BLACKBOX_SPOOL_DIR = "$HOME\.blackbox"
```

Python SDK example:

```python
import blackbox as bb

run = bb.init(
    project="alpha-lab",
    research="csi500-reversal",
    branch="baseline-v1",
    name="offline-agent-run",
    tags=["agent", "offline"],
    created_by_type="agent",
    created_by_id="agent-alpha",
    offline=True,
)
bb.log("strategy.summary", {"sharpe": 1.21, "max_drawdown": 0.1}, client_event_id="agent-task-456-summary")
bb.log_artifact("offline_report", "report.html", kind="report_html", idempotency_key="agent-task-456-report")
bb.finish()
```

Sync later:

```powershell
bbox sync --spool-dir "$HOME\.blackbox" --endpoint http://127.0.0.1:8000 --json
```

`bbox sync` creates missing project/research/branch records, restores the run, events, metrics, snapshots, notes, sweeps, and artifacts, then marks the local manifest as synced. Use `--include-synced` only when deliberately replaying already synced manifests; idempotency keys protect supported write surfaces, but not every operation should be blindly replayed.

## Idempotency Keys

Generate deterministic keys from the agent task id and logical write step, not from the retry attempt number.

Recommended pattern:

```text
<agent-task-id>:<entity>:<logical-step>
```

Examples:

- `task-20260520-001:run:start`
- `task-20260520-001:metric:summary`
- `task-20260520-001:artifact:post-cost-report`
- `task-20260520-001:series:equity-curve`

Use idempotency keys for:

- `bbox run start`
- `bbox run clone`
- `bbox run log-series`
- `bbox artifact upload`
- `bbox artifact complete-upload`
- `bbox artifact register-external`

Use `client_event_id` for append-style records:

- `bbox run log-event`
- `bbox run log-metric`
- `bbox note add`

On retry, reuse the same idempotency key or `client_event_id` for the same logical write. Generate a new key only when the agent intentionally creates a new entity or new observation.

## Error Handling

CLI failures are emitted to stderr with the same envelope shape:

```json
{"ok":false,"data":null,"error":{"code":"VALIDATION_ERROR","message":"...","hint":"..."}}
```

Known error codes:

- `VALIDATION_ERROR`: fix command arguments, JSON payloads, enum values, or search syntax before retrying.
- `NOT_FOUND`: refresh IDs from search/list endpoints; the target may have been deleted or the key may be wrong.
- `CONFLICT`: retry with the same idempotency key if the previous write may have succeeded; otherwise inspect the returned object.
- `STATE_ERROR`: do not retry unchanged. The run or branch is in a terminal or incompatible state.
- `AUTH_ERROR`: refresh token or check server auth configuration.
- `STORAGE_ERROR`: artifact storage failed; retry after checking local file paths or server storage.
- `NETWORK_ERROR`: retry with backoff using the same idempotency key or `client_event_id`.
- `CLI_ERROR`: local CLI/runtime problem; inspect the message and environment.

Agent retry policy:

- Retry `NETWORK_ERROR`, transient `STORAGE_ERROR`, and transport failures with exponential backoff.
- Do not retry `VALIDATION_ERROR` or `STATE_ERROR` without changing the request.
- For uncertain write outcomes, retry with the original idempotency key or `client_event_id`.
- After a partial batch failure, retry only failed items.

## WebUI Verification

After an agent run, verify in WebUI:

- Dashboard: run appears in Top / Recent Runs with `Creator`.
- Research page: branch lineage shows source branch/source run.
- Branch page: curve overlay and metric/config evolution include the new run.
- Run Detail: metrics, events, artifacts, snapshots, notes, and source config diff are visible.
- Search page: filters can find the run by project/research/branch/status/tags/metric/config/context/author/artifact.
- Compare page: selected runs show metric matrix, config diff, series preview, artifact comparison, and Pareto view.
- Sweep page: attached sweep runs show heatmap, result table, Pareto frontier, and links back to run detail.
- Research page: the embedded map opens on the baseline node; the branch and recent-run tables show the Map node column; the node detail shows the verdict, the comparison against the baseline, and the bound run's quality gate.
