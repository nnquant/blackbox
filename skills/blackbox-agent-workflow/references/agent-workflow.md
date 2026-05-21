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

For agent automation, prefer JSON output and narrow payloads:

```powershell
bbox search runs --where 'metrics.strategy.summary.sharpe > 1 and tags contains "baseline"' --select id,name,status,branch_key,summary_json --json
```

Global flags such as `--json`, `--select`, `--endpoint`, and `--token` can be placed before or after the subcommand.

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

bbox run log-metric --run-id run_new --namespace strategy.summary --values '{"sharpe":1.34,"max_drawdown":0.08,"turnover":0.42}' --client-event-id agent-task-123-met-summary --json

bbox run log-series --run-id run_new --name equity_curve --data-file .\equity.json --x date --y nav --kind table_csv --idempotency-key agent-task-123-series-equity --json

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
```

5. Finish or fail the run.

```powershell
bbox run finish --run-id run_new --json
```

```powershell
bbox run fail --run-id run_new --error '{"code":"BACKTEST_ERROR","message":"input data missing"}' --json
```

6. Compare against baseline and record the decision.

```powershell
bbox compare runs --run-ids run_abc run_new --metrics strategy.summary.sharpe,strategy.summary.max_drawdown --series equity_curve --json

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

The WebUI will show the resulting run, artifacts, compare output, lineage, notes, and creator/source fields after refresh or websocket update.

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
