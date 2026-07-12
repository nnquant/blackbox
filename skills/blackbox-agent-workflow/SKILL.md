---
name: blackbox-agent-workflow
description: Operate the Blackbox quant research system through bbox CLI, Python SDK, offline spool sync, and WebUI verification. Use when Codex needs to run or guide AI-agent research workflows for Blackbox, including baseline search, branch creation from a run, run logging, artifacts, compare, notes, sweep attachment, offline sync from ~/.blackbox, idempotent retry handling, or checking that backend/SDK/CLI results are visible in the WebUI.
---

# Blackbox Agent Workflow

Use this skill to execute or explain reliable Blackbox agent workflows. Prefer current repository state over memory, and verify command names against `packages/cli/blackbox_cli/main.py` when changing implementation.

## Core Rules

- Use `bbox` as the CLI entrypoint.
- Use `import blackbox as bb` for SDK examples.
- Expect API/CLI envelopes shaped as `{"ok": true, "data": ..., "error": null}`.
- Use JSON output for automation; add `--select` to reduce context.
- Use `~/.blackbox` as the default local data/spool directory unless the user specifies another path.
- Pass `created_by_type` and `created_by_id` when an agent identity is available; WebUI displays these in Creator fields.
- Preserve idempotency keys and `client_event_id` values across retries for the same logical write.
- For WebUI-compatible performance display, log key cards under `strategy.summary` with numeric keys `annual_return`, `periods_per_year`, `annual_volatility`, `max_drawdown`, `sharpe`, `sortino`, and `calmar`. Percent-style summary metrics use percentage points (`18.5` means `18.50%`; `-9.0` means `-9.00%`). Run Detail shows `periods_per_year` in a separate annualization-period card rather than adding it to the annual-return label.
- For metrics, use scalar `log-metric` / `bb.log` for searchable summary values, and use metric-bound table/series artifacts for large or inspectable data. Prefer SDK helpers `bb.log_metric_series(...)` and `bb.log_metric_table(...)`, or CLI `bbox run log-series --metric-key ...`; WebUI Metrics shows these as clickable rows with Table and Plot views.
- For Run-level outputs that should appear in WebUI Results, add typed `metadata.result` to artifacts. Use domains `performance`, `factor`, `factor_batch`, `risk`, `cost`, `diagnostic`, or `custom`; use roles such as `primary_curve`, `drawdown`, `ic_curve`, `quantile_returns`, `comparison_table`, and `comparison_curve`. Prefer SDK helpers `bb.log_performance_result(...)`, `bb.log_factor_result(...)`, `bb.log_factor_batch_result(...)`, `bb.log_result_series(...)`, and `bb.log_result_table(...)`. `bb.log_performance_result(...)` computes the same canonical summary as the CLI when a curve is supplied.
- For Run Detail curves, upload a `mode` and use `series_values` as the preferred value column. Supported performance modes are `nav`, `return`, and `pnl`: `mode=nav` means `series_values` is a net-value level, `mode=return` means decimal period returns such as `0.012`, and `mode=pnl` means absolute period changes such as `9.0` for a move from `101` to `110`. Legacy value columns (`nav`, `return`, `ret`, `pnl`, `change`) remain readable, but new uploads should use `series_values`. Upload optional `drawdown_series` with `mode=drawdown`; for return/net-value runs values are decimal drawdowns such as `-0.09`, while `mode=pnl` runs may use absolute drawdown values such as `-9.0`.
- For CLI performance results, prefer `bbox run publish-performance`. It safely infers standard date/value columns, copies the chosen value into `series_values`, computes the canonical performance summary from the full curve, records the calculation contract, uploads with stable derived idempotency keys, and validates the stored run. Pass `--finish` to finish only after validation succeeds.
- Always declare `--mode` and `--periods-per-year` on `publish-performance`. When reported percentage metrics are also supplied, declare `--summary-unit`; unit semantics are never guessed. Use `--dry-run` to inspect normalization without writing and `--agent-output` for compact diagnostics.
- For low-level/custom uploads, enable local preflight checks in strict mode: pass CLI `--strict-contract` on `bbox run log-series` / `bbox run log-metric`, pass SDK `strict_contract=True` where exposed, or set `BLACKBOX_AGENT_STRICT_UPLOAD=1`. Use `--skip-upload-validation` only as an explicit manual override.
- Upload diagnostics are part of the agent contract. On CLI/API failure, parse `error.details.issues`; on CLI/SDK dry-run, parse `data.validation.issues`; on SDK `UploadValidationError`, parse `exc.report["issues"]`. Each issue includes stable `code`, `severity`, `title`, `detail`, and usually `field`, `fix`, and `example`. Do not retry the same payload on `VALIDATION_ERROR`; apply `fix` first.
- Treat `preview_json.rows` as a display preview only. WebUI and compare should read full series content, but agents must still verify after upload that series names, row counts, first/last dates, and summary metric units match the run spec. Run `bbox run validate --run-id <run_id> --expected-start <date> --expected-end <date> --expected-rows <n> --primary-series <name> --fail-on-warning` after uploading results, or call `bb.validate_run(run_id, expected_start=..., expected_end=..., expected_rows=..., primary_series_name=...)` from Python and fail the workflow on `severity != "ok"`; use CLI `--no-fail` only when collecting diagnostics without gating.
- `bbox run finish` and SDK `bb.finish()` run the result quality gate by default and block red/error diagnostics. Use CLI `--fail-on-warning` or SDK `fail_on_warning=True` for strict release workflows. Use `--skip-quality-gate` / `skip_quality_gate=True` only as an explicit manual override, and document why the run is allowed to finish.
- `bbox compare runs` also applies the result quality gate to selected runs by default. Use `--skip-quality-gate` only for legacy/manual diagnostics where invalid runs must be inspected side by side.
- Quick Compare is exposed on Project / Research / Branch pages. It resolves Project and Research scopes to representative runs, and Branch scopes to comparable runs. Single Run Detail pages use the dedicated net value chart, not Quick Compare.
- After writing data, verify in WebUI when a local browser target is available.

## Workflow

1. Search for baseline runs with `bbox search runs`.
2. Fork or update a branch with `bbox branch create --from-run`.
3. Start the new run with `bbox run start --idempotency-key`.
4. Log events, metrics, series, structured dataset snapshots, artifacts, and notes. Prefer `bbox dataset register` over hand-written data snapshot JSON.
   - Always include WebUI-compatible `strategy.summary` metrics and one chartable performance series for completed backtests: `equity_curve`, `returns_series`, `pnl_series`, or `absolute_return_series`.
   - For multi-row metric outputs such as factor IC history, per-factor rankings, cost breakdowns, or parameter diagnostics, bind table/series artifacts to a metric and add `metadata.result` instead of forcing the data into scalar metrics.
   - For single-factor tests, prefer `bb.log_factor_result(...)` with cumulative IC and grouped returns. For one run that tests many factors, prefer `bb.log_factor_batch_result(...)` with a comparison table and optional comparison curve.
   - Add `drawdown_series` when the backtest engine already has precise drawdown values.
   - For CLI backtests, use `bbox run publish-performance ... --finish --agent-output`; it performs normalization, upload preflight, stored-result validation, and optional finish in one command.
   - For custom low-level CLI/SDK writes, keep strict preflight and immediately verify uploaded series with `bbox run validate --run-id <run_id> --fail-on-warning` before finishing.
5. Finish, fail, or cancel the run. Finish only after validation passes; `bbox run finish --fail-on-warning` is preferred for agent-published results.
6. Compare candidate runs with `bbox compare runs` or `bbox batch compare`.
   - For WebUI Quick Compare, expect Project to compare child Research targets, Research to compare child Branch targets, and Branch to compare Run targets.
7. Review the research loop with `bbox research review --research-id <research_id>` to see state, ranked candidates, saved compare sets, decision notes, and archive suggestions before changing branch status.
8. Write a decision note with `--author-type agent`.
9. Verify Dashboard, Search, Compare, Sweep, Branch, and Run Detail in WebUI.

For exact command examples, offline sync, retry policy, and WebUI verification checklist, read `references/agent-workflow.md`.

## Error Handling

On CLI failure, parse stderr as the standard envelope. Retry only when the error is likely transient (`NETWORK_ERROR`, transient `STORAGE_ERROR`, transport failures), and reuse the original idempotency key or `client_event_id`.

Do not retry unchanged requests on `VALIDATION_ERROR` or `STATE_ERROR`. Refresh IDs on `NOT_FOUND`. For batch commands, retry only failed items.

## Implementation Notes

- When adding new Blackbox capabilities, update this skill only with stable operational rules. Keep long command examples in `references/agent-workflow.md`.
- If a workflow changes in code, update the reference and run the skill validator.
