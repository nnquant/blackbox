# Agent Workflow Guide

This guide is the operational contract for AI agents and batch jobs that write to Blackbox through `bbox`, the Python SDK, and the WebUI-backed API.

## Contents

- [Defaults](#defaults)
- [Recommended Online Loop](#recommended-online-loop)
- [WebUI-Compatible Data Contract](#webui-compatible-data-contract)
- [Batch Operations](#batch-operations)
- [Offline Loop](#offline-loop)
- [Idempotency Keys](#idempotency-keys)
- [Error Handling](#error-handling)
- [WebUI Verification](#webui-verification)

## Defaults

- CLI entrypoint: `bbox`
- SDK import: `import blackbox as bb`
- API response envelope: `{"ok": true, "data": ..., "error": null}`
- Default endpoint: `http://127.0.0.1:8000`, or `BLACKBOX_ENDPOINT`
- Token environment: `BLACKBOX_TOKEN` or `BLACKBOX_API_TOKEN`
- Default local data directory: `~/.blackbox`
- Offline spool layout: `~/.blackbox/queue`, `~/.blackbox/artifacts`, `~/.blackbox/manifests`
- Preferred CLI performance publisher: `bbox run publish-performance`; use `--agent-output` to avoid repeated prose diagnostics.

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
  --summary '{"annual_return":0.185,"annual_volatility":0.124,"max_drawdown":-0.09,"sharpe":1.34,"sortino":1.88,"calmar":2.06,"turnover":0.42}' `
  --summary-unit decimal `
  --drawdown-file .\drawdown.csv `
  --idempotency-prefix agent-task-123-performance `
  --expected-start 2023-01-03 `
  --expected-end 2026-05-07 `
  --expected-rows 820 `
  --finish `
  --fail-on-warning `
  --agent-output
```

5. Finish or fail the run.

`publish-performance --finish` performs post-upload validation and the finish quality gate. Omit `--finish` when more writes remain, then call `bbox run finish --run-id run_new --fail-on-warning --agent-output` after them.

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

## WebUI-Compatible Data Contract

Agents must follow this contract when the result is expected to render cleanly in WebUI.

### Run Detail key metric cards

The Run Detail metric cards read from `summary_json.strategy.summary` only. Use these exact numeric keys:

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

Rules:

- `annual_return`, `annual_volatility`, and `max_drawdown` are percentage-point values for summary cards. Use `18.5` for `18.50%`, not `0.185`.
- `max_drawdown` should be negative when representing a loss, for example `-9.0`.
- `sharpe`, `sortino`, `calmar`, and `turnover` are plain ratios unless the strategy convention explicitly says otherwise.
- Keep additional metrics under stable namespaces, but do not expect custom names like `annual_ret`, `ann_vol`, `mdd`, or `drawdown` to populate the default cards.

CLI:

```powershell
bbox run log-metric `
  --run-id run_new `
  --namespace strategy.summary `
  --values '{"annual_return":18.5,"annual_volatility":12.4,"max_drawdown":-9.0,"sharpe":1.34,"sortino":1.88,"calmar":2.06,"turnover":0.42}' `
  --client-event-id agent-task-123-met-summary `
  --json
```

SDK:

```python
import blackbox as bb

bb.log(
    {
        "annual_return": 18.5,
        "annual_volatility": 12.4,
        "max_drawdown": -9.0,
        "sharpe": 1.34,
        "sortino": 1.88,
        "calmar": 2.06,
        "turnover": 0.42,
    },
    namespace="strategy.summary",
    client_event_id="agent-task-123-met-summary",
)
```

### Scalar metrics vs data-backed metrics

Best practice:

- Use scalar metrics for values that should be searchable, sortable, and shown in summary/compare tables.
- Use metric-bound artifacts for sequences and tables that users need to inspect in Run Detail. WebUI Metrics renders these as clickable rows and opens a detail modal with `Table` and `Plot` views.
- Do not put large arrays, date-indexed series, or per-factor tables inside `bbox run log-metric --values`. The server intentionally limits metric payload size; store large data as artifact content.
- Use `metadata.metric` to bind an artifact to a metric identity. For series uploaded through `log-series`, set `metric.namespace`, `metric.key`, `metric.kind`, `x`, `y`, and `mode` where applicable.
- Prefer CSV for small to medium WebUI-inspected data. Parquet is fine for large artifacts and downloads, but browser preview/plot support depends on available preview rows unless a content reader is added.

#### Scenario A: ordinary scalar summary

Use this for final values such as Sharpe, drawdown, annual return, IC mean, turnover, and coverage.

```powershell
bbox run log-metric `
  --run-id run_new `
  --namespace factor.summary `
  --values '{"ic_mean":0.034,"ic_ir":0.61,"coverage":0.94,"turnover":0.38}' `
  --point '{"kind":"event","name":"factor_eval_done"}' `
  --client-event-id agent-task-123-factor-summary `
  --json
```

```python
import blackbox as bb

bb.log(
    {"ic_mean": 0.034, "ic_ir": 0.61, "coverage": 0.94, "turnover": 0.38},
    namespace="factor.summary",
    point={"kind": "event", "name": "factor_eval_done"},
    client_event_id="agent-task-123-factor-summary",
)
```

#### Scenario B: one run evaluates many factors

Use scalar metrics for aggregate summary, and use a metric-bound table for the per-factor comparison. Users can open `factor.summary.factor_comparison` from the Metrics tab and sort/inspect the table.

Example `factor_comparison.json`:

```json
[
  {"factor": "alpha_reversal_5d", "ic_mean": 0.034, "ic_ir": 0.61, "coverage": 0.94, "turnover": 0.38},
  {"factor": "alpha_volume_shock", "ic_mean": 0.021, "ic_ir": 0.44, "coverage": 0.90, "turnover": 0.52}
]
```

CLI:

```powershell
bbox run log-series `
  --run-id run_new `
  --name factor_comparison `
  --data-file .\factor_comparison.json `
  --kind table_csv `
  --metric-namespace factor.summary `
  --metric-key factor_comparison `
  --metric-kind table `
  --idempotency-key agent-task-123-factor-comparison `
  --json
```

SDK:

```python
import blackbox as bb

bb.log_metric_table(
    "factor.summary",
    "factor_comparison",
    [
        {"factor": "alpha_reversal_5d", "ic_mean": 0.034, "ic_ir": 0.61, "coverage": 0.94, "turnover": 0.38},
        {"factor": "alpha_volume_shock", "ic_mean": 0.021, "ic_ir": 0.44, "coverage": 0.90, "turnover": 0.52},
    ],
    kind="table_csv",
    idempotency_key="agent-task-123-factor-comparison",
)
```

#### Scenario C: factor IC or rank-IC time series

Use a metric-bound series when each row is indexed by date/time and should be plotted. Users can open `factor.ic.ic_by_date` and switch to `Plot`.

Example `factor_ic.json`:

```json
[
  {"date": "2026-01-02", "ic": 0.031, "rank_ic": 0.044},
  {"date": "2026-01-05", "ic": -0.012, "rank_ic": -0.018},
  {"date": "2026-01-06", "ic": 0.027, "rank_ic": 0.036}
]
```

CLI:

```powershell
bbox run log-series `
  --run-id run_new `
  --name factor_ic_series `
  --data-file .\factor_ic.json `
  --x date `
  --y ic,rank_ic `
  --kind table_csv `
  --namespace factor.ic `
  --metric-namespace factor.ic `
  --metric-key ic_by_date `
  --metric-kind series `
  --idempotency-key agent-task-123-factor-ic `
  --json
```

SDK:

```python
import blackbox as bb

bb.log_metric_series(
    "factor.ic",
    "ic_by_date",
    [
        {"date": "2026-01-02", "ic": 0.031, "rank_ic": 0.044},
        {"date": "2026-01-05", "ic": -0.012, "rank_ic": -0.018},
        {"date": "2026-01-06", "ic": 0.027, "rank_ic": 0.036},
    ],
    x="date",
    y=["ic", "rank_ic"],
    kind="table_csv",
    idempotency_key="agent-task-123-factor-ic",
)
```

#### Scenario D: strategy diagnostics and cost breakdowns

Use scalar metrics for the headline cost/risk values and metric-bound tables for detailed rows.

```python
import blackbox as bb

bb.log({"total_cost_bps": 18.4, "fee_bps": 6.1, "slippage_bps": 12.3}, namespace="cost.summary")

bb.log_metric_table(
    "cost.breakdown",
    "by_symbol",
    [
        {"symbol": "000001.SZ", "turnover": 1200000, "fee_bps": 5.8, "slippage_bps": 11.2},
        {"symbol": "000002.SZ", "turnover": 980000, "fee_bps": 6.0, "slippage_bps": 13.0},
    ],
    kind="table_csv",
)
```

#### Scenario E: parameter diagnostics inside one run

If one run contains a small parameter grid or stage diagnostics that should not become separate runs, bind it as a table metric. If each parameter combination is a serious candidate strategy, prefer separate Runs under a Sweep instead.

```python
import blackbox as bb

bb.log_metric_table(
    "diagnostics.grid",
    "lookback_hold_grid",
    [
        {"lookback": 10, "hold": 1, "sharpe": 1.12, "max_drawdown": -7.4},
        {"lookback": 20, "hold": 3, "sharpe": 1.36, "max_drawdown": -8.1},
    ],
    kind="table_csv",
)
```

Decision rule:

- Separate Run: compare candidates, preserve lineage, use Quick Compare / Compare / Sweep.
- Data-backed Metric: inspect diagnostics within a single run, especially factor-level tables, IC history, cost breakdown, parameter diagnostics, or debug traces.

### Run Results contract

Run is the smallest execution unit. Project, Research, and Branch are aggregation and analysis layers. Inside one Run, every user-facing output should be either a scalar metric or a typed result artifact.

Use `metadata.result` for artifacts that should appear in the WebUI Results tab:

```json
{
  "result": {
    "domain": "factor",
    "name": "alpha_reversal_ic",
    "role": "ic_curve",
    "title": "Cumulative IC",
    "group": "factor.alpha_reversal_5d",
    "order": 10,
    "view": {"default": "plot", "x": "date", "y": "cumulative_ic", "chart": "line"}
  }
}
```

Domains:

- `performance`: strategy performance outputs.
- `factor`: one factor's test outputs.
- `factor_batch`: one run testing many factors.
- `risk`, `cost`, `diagnostic`, `custom`: other run outputs.

Common roles:

- `primary_curve`: net value, cumulative return, or cumulative PnL curve.
- `drawdown`: drawdown series.
- `ic_curve`: IC / Rank IC / cumulative IC series.
- `quantile_returns`: grouped or quantile returns table/series.
- `comparison_table`: multi-factor comparison table.
- `comparison_curve`: multi-factor overlaid return / IC / score curve.
- `table`, `series`, `report`: generic diagnostic outputs.

Preferred SDK helpers:

```python
import blackbox as bb

bb.log_performance_result(
    metrics={"annual_return": 18.5, "max_drawdown": -9.0, "sharpe": 1.34},
    curve=[
        {"date": "2026-01-02", "series_values": 1.000},
        {"date": "2026-01-05", "series_values": 1.012},
    ],
    mode="nav",
    drawdown=[
        {"date": "2026-01-02", "drawdown": 0.0},
        {"date": "2026-01-05", "drawdown": -0.004},
    ],
)

bb.log_factor_result(
    metrics={"ic_mean": 0.034, "ic_ir": 0.61, "coverage": 0.94, "turnover": 0.38},
    factor_name="alpha_reversal_5d",
    ic_series=[
        {"date": "2026-01-02", "ic": 0.031, "rank_ic": 0.044, "cumulative_ic": 0.031},
        {"date": "2026-01-05", "ic": -0.012, "rank_ic": -0.018, "cumulative_ic": 0.019},
    ],
    quantile_returns=[
        {"date": "2026-01-02", "quantile": 1, "series_values": 1.000},
        {"date": "2026-01-02", "quantile": 5, "series_values": 1.006},
    ],
)

bb.log_factor_batch_result(
    comparison_table=[
        {"factor": "alpha_reversal_5d", "ic_mean": 0.034, "ic_ir": 0.61, "long_short_return": 0.082},
        {"factor": "alpha_volume_shock", "ic_mean": 0.021, "ic_ir": 0.44, "long_short_return": 0.051},
    ],
    comparison_series=[
        {"date": "2026-01-02", "alpha_reversal_5d": 1.000, "alpha_volume_shock": 1.000},
        {"date": "2026-01-05", "alpha_reversal_5d": 1.004, "alpha_volume_shock": 0.998},
    ],
    y=["alpha_reversal_5d", "alpha_volume_shock"],
)
```

CLI can attach result metadata directly:

```powershell
bbox run log-series `
  --run-id run_new `
  --name factor_ic_series `
  --data-file .\factor_ic.json `
  --x date `
  --y cumulative_ic `
  --namespace factor.ic `
  --result-domain factor `
  --result-name alpha_reversal_ic `
  --result-role ic_curve `
  --result-title "Cumulative IC" `
  --result-group factor.alpha_reversal_5d `
  --result-order 10 `
  --result-view '{"default":"plot","x":"date","y":"cumulative_ic","chart":"line"}' `
  --json
```

Compatibility:

- Existing `equity_curve`, `returns_series`, `pnl_series`, `absolute_return_series`, and `drawdown_series` still render as performance results.
- Existing `factor_ic_series` renders as a factor IC result.
- Existing `factor_quantile_returns` renders as grouped returns.
- Existing `factor_comparison` / `factor_rank_*` render as factor-batch comparison tables.

### Run Detail net value and drawdown chart

The Run Detail chart reads full series artifact content. `preview_json.rows` is only a display preview and may be shorter than the full dataset. A metrics-only run will show `No Series Data Available`.

Preferred net value file `equity.json`:

```json
[
  {"date": "2026-01-01", "series_values": 1.0000},
  {"date": "2026-01-02", "series_values": 1.0125},
  {"date": "2026-01-05", "series_values": 1.0060},
  {"date": "2026-01-06", "series_values": 1.0310}
]
```

Preferred absolute-change file `pnl.json`:

```json
[
  {"date": "2026-01-01", "series_values": 0.0},
  {"date": "2026-01-02", "series_values": 9.0},
  {"date": "2026-01-05", "series_values": -2.5},
  {"date": "2026-01-06", "series_values": 4.0}
]
```

Preferred drawdown file `drawdown.json`:

```json
[
  {"date": "2026-01-01", "drawdown": 0.0},
  {"date": "2026-01-02", "drawdown": 0.0},
  {"date": "2026-01-05", "drawdown": -0.0064},
  {"date": "2026-01-06", "drawdown": 0.0}
]
```

CLI:

```powershell
bbox run publish-performance `
  --run-id run_new `
  --curve-file .\equity.json `
  --mode nav `
  --summary-file .\summary.json `
  --summary-unit percentage-point `
  --drawdown-file .\drawdown.json `
  --idempotency-prefix agent-task-123-performance `
  --finish `
  --agent-output
```

`publish-performance` accepts JSON, JSONL, CSV, YAML, and Parquet rows. It infers exactly one standard date column and common mode-specific value names such as `nav`, `ret`, `pnl`, and `drawdown`; pass `--x`, `--value`, or `--drawdown-value` when inference is ambiguous. It copies the source value into canonical `series_values`, preserves the original columns, and reports every normalization. Percentage units are never inferred: use `--summary-unit decimal` for values such as `0.18`, or `--summary-unit percentage-point` for values such as `18.0`.

Use the low-level commands only for custom contracts not covered by the publisher:

```powershell
bbox run log-series `
  --run-id run_new `
  --name equity_curve `
  --data-file .\equity.json `
  --x date `
  --y series_values `
  --mode nav `
  --kind table_csv `
  --result-domain performance `
  --result-name primary_performance `
  --result-role primary_curve `
  --idempotency-key agent-task-123-series-equity `
  --strict-contract `
  --json

bbox run log-series `
  --run-id run_new `
  --name pnl_series `
  --data-file .\pnl.json `
  --x date `
  --y series_values `
  --mode pnl `
  --kind table_csv `
  --result-domain performance `
  --result-name primary_performance `
  --result-role primary_curve `
  --idempotency-key agent-task-123-series-pnl `
  --strict-contract `
  --json

bbox run log-series `
  --run-id run_new `
  --name drawdown_series `
  --data-file .\drawdown.json `
  --x date `
  --y drawdown `
  --mode drawdown `
  --kind table_csv `
  --result-domain performance `
  --result-name primary_drawdown `
  --result-role drawdown `
  --idempotency-key agent-task-123-series-drawdown `
  --strict-contract `
  --json
```

SDK:

```python
import blackbox as bb

bb.log_performance_result(
    curve=[
        {"date": "2026-01-01", "series_values": 1.0000},
        {"date": "2026-01-02", "series_values": 1.0125},
        {"date": "2026-01-05", "series_values": 1.0060},
        {"date": "2026-01-06", "series_values": 1.0310},
    ],
    mode="nav",
    idempotency_prefix="agent-task-123",
)

bb.log_pnl_series(
    [
        {"date": "2026-01-01", "series_values": 0.0},
        {"date": "2026-01-02", "series_values": 9.0},
        {"date": "2026-01-05", "series_values": -2.5},
        {"date": "2026-01-06", "series_values": 4.0},
    ],
)

bb.log_drawdown_series(
    [
        {"date": "2026-01-01", "drawdown": 0.0},
        {"date": "2026-01-02", "drawdown": 0.0},
        {"date": "2026-01-05", "drawdown": -0.0064},
        {"date": "2026-01-06", "drawdown": 0.0},
    ]
)
```

Rules:

- New uploads should use `series_values` as the value column and set `mode` explicitly. Supported performance modes are `nav`, `return`, and `pnl`.
- Use `equity_curve` with `mode=nav` for ordinary net value curves. Values should normally start near `1.0`.
- If only periodic returns are available, upload `returns_series` with `mode=return`; `series_values` are decimal returns such as `0.012`. WebUI compounds it into cumulative return.
- For arbitrage, intraday, or other absolute-PnL backtests that do not have a meaningful return base, upload `pnl_series` or `absolute_return_series` with `mode=pnl`. Values are absolute period changes, not percentages; for example, if value moves from `101` to `110`, upload `9.0`, and WebUI cumulatively sums the series.
- Legacy value columns (`nav`, `return`, `ret`, `pnl`, `change`) remain readable, but new agent uploads should use `series_values`.
- Drawdown series values are decimal fractions for net-value/return runs, not percentage points. Use `-0.09` for `-9%`. For `pnl_series` / `absolute_return_series`, drawdown values may be absolute changes such as `-9.0`.
- If `drawdown_series` is not uploaded, WebUI computes drawdown from `nav`, compounded returns, or cumulative absolute changes depending on the primary series type.
- `drawdown` is accepted as a compare/overlay request alias for `drawdown_series`, but uploaded artifacts should still be named `drawdown_series`.
- `returns` is accepted as a compare/overlay request alias for `returns_series`, but uploaded artifacts should still be named `returns_series`.
- `pnl` / `profit` are accepted as compare/overlay request aliases for `pnl_series`; `absolute_return` / `absolute_change` are accepted aliases for `absolute_return_series`.
- Do not upload display-only names such as `annual_ret`, `cum_ret_pct`, or `mdd_pct` unless you also upload the preferred names above.
- Keep dates as ISO strings (`YYYY-MM-DD`) and keep rows sorted ascending.

### Required upload-side validation

For standard performance results, agents should use `publish-performance`. It applies safe normalization, strict contract preflight, stored-result validation, and optional finish without a repair loop. Use `--dry-run` when the source columns or units need inspection; a successful real publication does not require a separate dry-run command.

Low-level upload preflight:

- CLI: pass `--strict-contract --dry-run` on `bbox run log-series` and `bbox run log-metric` before the real upload, or set `BLACKBOX_AGENT_STRICT_UPLOAD=1` for the process.
- SDK: set `BLACKBOX_AGENT_STRICT_UPLOAD=1`, or pass `strict_contract=True` where the helper exposes it.
- `--skip-upload-validation` is a manual override for legacy data inspection only; document why it was used.

Strict upload preflight fails before writing when:

- A performance curve upload does not use `series_values`.
- A performance curve omits `mode` or uses a mode outside `nav`, `return`, `pnl`.
- A performance curve omits typed `metadata.result`.
- A declared `x` or `y` column is missing from uploaded rows.
- `strategy.summary` percentage metrics look like decimals, for example `annual_return=0.18` instead of `18.0`.

Upload diagnostic response contract:

- `--agent-output` removes duplicated message/detail prose and returns compact machine-readable issue fields.
- CLI/API failures use the standard envelope and put machine-readable diagnostics under `error.details.issues`.
- CLI/SDK dry-runs return diagnostics under `data.validation.issues`.
- SDK strict failures raise `blackbox.UploadValidationError`, which is still a `ValueError`; parse `exc.report["issues"]`.
- Each issue has stable `code`, `severity`, `title`, `detail`, and usually `field`, `fix`, and `example`.
- Agents should branch on `code`, apply `fix`, regenerate the payload, and retry with the same idempotency key. Do not retry unchanged requests on `VALIDATION_ERROR`.

Example failed CLI/API issue:

```json
{
  "code": "SERIES_Y_COLUMN_NOT_FOUND",
  "severity": "error",
  "title": "Series y column is missing",
  "field": "y",
  "detail": "Column(s) series_values are not present in uploaded rows.",
  "fix": "Set y to existing numeric column(s), or add series_values to each row.",
  "example": "[{\"date\":\"2026-01-01\",\"series_values\":1.0}]"
}
```

Common fix branches for agents:

- `SUMMARY_UNIT_AMBIGUOUS`: rerun with `--summary-unit decimal` or `--summary-unit percentage-point`; never infer the financial unit from magnitude.
- `SERIES_X_AMBIGUOUS` / `SERIES_VALUE_AMBIGUOUS`: pass `--x` / `--value` explicitly.
- `SERIES_Y_COLUMN_NOT_FOUND`, `SERIES_RESULT_METADATA_MISSING`, and `PERFORMANCE_VALUE_COLUMN_NOT_SERIES_VALUES` are normally avoided by `publish-performance`; handle them manually only on low-level uploads.
- `PERFORMANCE_MODE_INVALID`: choose `mode=nav`, `mode=return`, or `mode=pnl` according to the source series semantics.
- `SERIES_RESULT_METADATA_MISSING`: add `--result-domain performance --result-name primary_performance --result-role primary_curve` for primary curves.
- `SUMMARY_PERCENT_DECIMAL_UNIT`: convert percentage-style summary metrics from decimals to percentage points.
- `DRAWDOWN_UNIT_SUSPICIOUS`: use decimal drawdown for nav/return runs, or `mode=pnl` only for absolute drawdown values.

`publish-performance` automatically checks the stored primary series name, full row count, and first/last x values against the normalized source. Explicit `--expected-start`, `--expected-end`, and `--expected-rows` override those source-derived expectations. For low-level uploads, run `bbox run validate --expected-start ... --expected-end ... --expected-rows ... --primary-series ... --fail-on-warning` before finish.

WebUI Run Detail now shows a Result Summary panel at the top of a run. Check it before reading charts: it shows the primary curve, date range, result domains, key metric coverage, artifact counts, update time, and quality status. If the diagnostics card appears, expand it and follow the suggested fix command.

Result view templates are registry-driven. Built-in domains cover `performance`, `factor`, `factor_batch`, `risk`, `cost`, and `diagnostic`; teams can extend WebUI rendering with `window.BLACKBOX_RESULT_TEMPLATES` or localStorage key `blackbox.resultTemplates` using the same domain/block shape as the built-in registry.

Minimum checks:

- One primary curve series exists with `x == "date"`, `y == "series_values"`, and `mode` in `{"nav", "return", "pnl"}`. Valid names are `equity_curve`, `returns_series`, `pnl_series`, or `absolute_return_series`.
- `drawdown_series` exists when the run provides explicit drawdown, with canonical `y == "series_values"` from `publish-performance` or legacy low-level `y == "drawdown"`. Use decimal drawdowns for return/net-value runs and absolute drawdowns for absolute-change runs.
- Full series rows cover the intended date range. For the current CSI500 example, first date must be `2023-01-03` and last date must be `2026-05-07`.
- The full row count must match the source dataframe length. Do not use `preview_json.rows.length` as the full row count; it may be a preview.
- `strategy.summary` percent metrics are percentage points, not decimals.
- Run name, title, tags, and note summaries must not include temporary-fix wording such as `hotfix`, `temp`, `preview workaround`, or `manual patch`.

Python validation skeleton:

```python
def validate_blackbox_payload(run_detail, expected_start, expected_end, expected_rows):
    artifacts = {item["name"]: item for item in run_detail["artifacts"]}
    primary = (
        artifacts.get("equity_curve")
        or artifacts.get("returns_series")
        or artifacts.get("pnl_series")
        or artifacts.get("absolute_return_series")
    )
    assert primary, "missing chartable performance series"
    series = primary["metadata_json"]["series"]
    assert series["name"] in {"equity_curve", "returns_series", "pnl_series", "absolute_return_series"}
    assert series["x"] == "date"
    assert series["y"] == "series_values"
    assert series["mode"] in {"nav", "return", "pnl"}

    rows = primary["preview_json"].get("rows", [])
    assert len(rows) == expected_rows, f"expected {expected_rows} full rows, got {len(rows)}"
    assert rows[0]["date"] == expected_start
    assert rows[-1]["date"] == expected_end

    summary = run_detail["summary_json"]["strategy.summary"]
    assert abs(summary["annual_return"]) > 1, "annual_return must be percentage points, not decimal"
    assert summary["max_drawdown"] <= 0, "max_drawdown should be negative percentage points"
```

CLI validation outline:

```powershell
bbox run get --run-id run_new --json --select id,name,tags,summary_json,artifacts
```

Inspect the returned `artifacts` for `equity_curve` / `returns_series` / `pnl_series` / `absolute_return_series` / `drawdown_series`, full `preview_json.row_count`, first row date, last row date, and `strategy.summary` units before finishing the run.

### Quick Compare contract

WebUI Quick Compare is available on Project, Research, and Branch pages. Single Run Detail pages use the dedicated net value / drawdown chart instead.

Target resolution:

- Project page compares each child Research target by its representative completed run.
- Research page compares each child Branch target by its representative completed run.
- Branch page compares the branch's Run targets directly.
- A Project / Research / Branch target resolves to the completed run with the highest `strategy.summary.sharpe`; if no completed run exists, it falls back to the latest available run.

Quick Compare only expects two data surfaces:

- Net value / performance overlay: `equity_curve(mode=nav, date, series_values)`; fallback `returns_series(mode=return, date, series_values)`; fallback `pnl_series(mode=pnl, date, series_values)` or `absolute_return_series(mode=pnl, date, series_values)`.
- Key metric table: `strategy.summary.annual_return`, `annual_volatility`, `max_drawdown`, `sharpe`, `sortino`, `calmar`, and `turnover`.

Agents must not rely on custom metric or series names for Quick Compare. These are valid:

```text
strategy.summary.annual_return
strategy.summary.annual_volatility
strategy.summary.max_drawdown
strategy.summary.sharpe
strategy.summary.sortino
strategy.summary.calmar
strategy.summary.turnover
series: equity_curve(mode=nav, date, series_values)
series: returns_series(mode=return, date, series_values)
series: pnl_series(mode=pnl, date, series_values)
series: absolute_return_series(mode=pnl, date, series_values)
series: drawdown_series(mode=drawdown, date, drawdown)
```

These are not valid by themselves for Quick Compare:

```text
annual_ret
ann_vol
mdd
cum_ret_pct
net_value_pct
drawdown
```

`drawdown` and `returns` may be accepted as request aliases in compare calls, but uploaded artifacts should still use `drawdown_series` and `returns_series`.
`pnl`, `profit`, `absolute_return`, and `absolute_change` may be accepted as request aliases in compare calls, but uploaded artifacts should still use `pnl_series` or `absolute_return_series`.

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
bb.log(
    {"annual_return": 12.0, "annual_volatility": 10.5, "max_drawdown": -10.0, "sharpe": 1.21},
    namespace="strategy.summary",
    client_event_id="agent-task-456-summary",
)
bb.log_series(
    "equity_curve",
    [{"date": "2026-01-01", "nav": 1.0}, {"date": "2026-01-02", "nav": 1.012}],
    x="date",
    y="nav",
    namespace="strategy.equity",
    kind="table_csv",
    idempotency_key="agent-task-456-series-equity",
)
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
