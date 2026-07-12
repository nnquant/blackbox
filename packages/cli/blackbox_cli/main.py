from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import httpx

from blackbox_common.performance import compute_performance_summary, performance_metadata
from blackbox_common.validation import (
    format_upload_report_for_agent,
    upload_report_failed,
    validate_metric_upload,
    validate_run_detail,
    validate_series_upload,
)

from .sync import sync_spool


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_global_args(sys.argv[1:] if argv is None else argv))
    try:
        data = dispatch(args)
        write_success(args, data)
        return command_exit_code(args, data)
    except CliError as exc:
        error = compact_agent_error(exc.payload) if getattr(args, "agent_output", False) else exc.payload
        print(json.dumps({"ok": False, "data": None, "error": error}, ensure_ascii=False), file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(json.dumps({"ok": False, "data": None, "error": {"code": "CLI_ERROR", "message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
        return 10


class CliError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 2, hint: str | None = None, details: Any = None):
        super().__init__(message)
        self.exit_code = exit_code
        self.payload = {"code": code, "message": message, "hint": hint, "details": details}


GLOBAL_FLAG_OPTIONS = {"--json", "--quiet", "--compact", "--agent-output"}
GLOBAL_VALUE_OPTIONS = {"--endpoint", "--token", "--output", "--select"}


def normalize_global_args(argv: list[str]) -> list[str]:
    """Allow documented global flags after subcommands.

    argparse only accepts root parser options before the subcommand. The CLI
    docs and common agent usage put flags such as --json/--select at the end,
    so normalize those root flags before parsing while leaving subcommand
    options untouched.
    """
    globals_: list[str] = []
    rest: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in GLOBAL_FLAG_OPTIONS:
            globals_.append(token)
            index += 1
            continue
        if token in GLOBAL_VALUE_OPTIONS:
            globals_.append(token)
            if index + 1 < len(argv):
                globals_.append(argv[index + 1])
                index += 2
            else:
                index += 1
            continue
        option, has_equals, _ = token.partition("=")
        if has_equals and option in GLOBAL_VALUE_OPTIONS:
            globals_.append(token)
            index += 1
            continue
        rest.append(token)
        index += 1
    return globals_ + rest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bbox")
    parser.add_argument("--endpoint", default=os.getenv("BLACKBOX_ENDPOINT", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("BLACKBOX_TOKEN") or os.getenv("BLACKBOX_API_TOKEN"))
    parser.add_argument("--json", action="store_true", help="Emit JSON output. This is the default and kept for script compatibility.")
    parser.add_argument("--output", choices=["json", "yaml", "table"], default="json")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--select", help="Comma-separated fields to keep from data, for example id,name,status.")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--agent-output", action="store_true", help="Emit compact, non-duplicated diagnostics for AI agents.")
    sub = parser.add_subparsers(dest="group", required=True)

    workspace = sub.add_parser("workspace")
    workspace_sub = workspace.add_subparsers(dest="action", required=True)
    workspace_create = workspace_sub.add_parser("create")
    workspace_create.add_argument("--id")
    workspace_create.add_argument("--key", required=True)
    workspace_create.add_argument("--title", required=True)
    workspace_create.add_argument("--description")
    workspace_create.add_argument("--roles", default="{}")
    workspace_update = workspace_sub.add_parser("update")
    workspace_update.add_argument("--workspace-id", required=True)
    workspace_update.add_argument("--title")
    workspace_update.add_argument("--description")
    workspace_update.add_argument("--roles")
    workspace_get = workspace_sub.add_parser("get")
    workspace_get.add_argument("--workspace-id", required=True)
    workspace_sub.add_parser("list")

    project = sub.add_parser("project")
    project_sub = project.add_subparsers(dest="action", required=True)
    project_create = project_sub.add_parser("create")
    project_create.add_argument("--workspace-id", default="local")
    project_create.add_argument("--key", required=True)
    project_create.add_argument("--title", required=True)
    project_create.add_argument("--description")
    project_create.add_argument("--tags", default="[]")
    project_create.add_argument("--retention-policy", default="{}")
    project_update = project_sub.add_parser("update")
    project_update.add_argument("--project-id", required=True)
    project_update.add_argument("--title")
    project_update.add_argument("--description")
    project_update.add_argument("--tags")
    project_update.add_argument("--retention-policy")
    project_get = project_sub.add_parser("get")
    project_get.add_argument("--project-id", required=True)
    project_sub.add_parser("list")

    research = sub.add_parser("research")
    research_sub = research.add_subparsers(dest="action", required=True)
    research_create = research_sub.add_parser("create")
    research_create.add_argument("--project", required=True)
    research_create.add_argument("--key", required=True)
    research_create.add_argument("--title", required=True)
    research_create.add_argument("--goal")
    research_create.add_argument("--hypothesis")
    research_list = research_sub.add_parser("list")
    research_list.add_argument("--project-id", required=True)
    research_get = research_sub.add_parser("get")
    research_get.add_argument("--research-id", required=True)
    research_update = research_sub.add_parser("update")
    research_update.add_argument("--research-id", required=True)
    research_update.add_argument("--title")
    research_update.add_argument("--goal")
    research_update.add_argument("--hypothesis")
    research_update.add_argument("--status")
    research_update.add_argument("--tags")
    research_review = research_sub.add_parser("review")
    research_review.add_argument("--research-id", required=True)
    research_review.add_argument("--metric", default="strategy.summary.sharpe")
    research_review.add_argument("--direction", choices=["max", "min"], default="max")
    research_review.add_argument("--stale-days", type=int, default=14)
    research_review.add_argument("--limit", type=int, default=10)

    branch = sub.add_parser("branch")
    branch_sub = branch.add_subparsers(dest="action", required=True)
    branch_create = branch_sub.add_parser("create")
    branch_create.add_argument("--research-id")
    branch_create.add_argument("--research")
    branch_create.add_argument("--key", required=True)
    branch_create.add_argument("--title", required=True)
    branch_create.add_argument("--from-run", dest="source_run_id")
    branch_create.add_argument("--parent-branch-id")
    branch_create.add_argument("--reason-code", "--reason-type", dest="reason_code")
    branch_create.add_argument("--reason-summary")
    branch_create.add_argument("--created-by-type")
    branch_create.add_argument("--created-by-id")
    branch_list = branch_sub.add_parser("list")
    branch_list.add_argument("--research-id", required=True)
    branch_get = branch_sub.add_parser("get")
    branch_get.add_argument("--branch-id", required=True)
    branch_update = branch_sub.add_parser("update")
    branch_update.add_argument("--branch-id", required=True)
    branch_update.add_argument("--title")
    branch_update.add_argument("--parent-branch-id")
    branch_update.add_argument("--source-run-id")
    branch_update.add_argument("--reason-code")
    branch_update.add_argument("--reason-summary")
    branch_update.add_argument("--hypothesis")
    branch_update.add_argument("--expected-change")
    branch_update.add_argument("--status")

    run = sub.add_parser("run")
    run_sub = run.add_subparsers(dest="action", required=True)
    run_start = run_sub.add_parser("start")
    run_start.add_argument("--project", required=True)
    run_start.add_argument("--research", required=True)
    run_start.add_argument("--branch", required=True)
    run_start.add_argument("--name", required=True)
    run_start.add_argument("--title")
    run_start.add_argument("--config", default="{}")
    run_start.add_argument("--config-file")
    run_start.add_argument("--context", default="{}")
    run_start.add_argument("--tags", default="[]")
    run_start.add_argument("--source-run-id")
    run_start.add_argument("--created-by-type")
    run_start.add_argument("--created-by-id")
    run_start.add_argument("--idempotency-key")
    run_get = run_sub.add_parser("get")
    run_get.add_argument("--run-id", required=True)
    run_validate = run_sub.add_parser("validate")
    run_validate.add_argument("--run-id", required=True)
    run_validate.add_argument("--expected-start", help="Expected first x/date value for the primary performance curve.")
    run_validate.add_argument("--expected-end", help="Expected last x/date value for the primary performance curve.")
    run_validate.add_argument("--expected-rows", type=int, help="Expected full row count for the primary performance curve.")
    run_validate.add_argument("--primary-series", help="Expected primary performance series name, e.g. equity_curve or pnl_series.")
    run_validate.add_argument("--fail-on-warning", action="store_true", help="Return a non-zero exit code when validation warnings are present.")
    run_validate.add_argument("--no-fail", action="store_true", help="Always return exit code 0 after printing diagnostics.")
    run_update = run_sub.add_parser("update")
    run_update.add_argument("--run-id", required=True)
    run_update.add_argument("--name")
    run_update.add_argument("--title")
    run_update.add_argument("--source-run-id")
    run_update.add_argument("--config")
    run_update.add_argument("--config-file")
    run_update.add_argument("--context")
    run_update.add_argument("--tags")
    run_clone = run_sub.add_parser("clone")
    run_clone.add_argument("--run-id", required=True)
    run_clone.add_argument("--name")
    run_clone.add_argument("--title")
    run_clone.add_argument("--branch-id")
    run_clone.add_argument("--config-overrides", default="{}")
    run_clone.add_argument("--config-overrides-file")
    run_clone.add_argument("--context-overrides", default="{}")
    run_clone.add_argument("--tags")
    run_clone.add_argument("--created-by-type")
    run_clone.add_argument("--created-by-id")
    run_clone.add_argument("--idempotency-key")
    run_event = run_sub.add_parser("log-event")
    run_event.add_argument("--run-id", required=True)
    run_event.add_argument("--event-type", required=True)
    run_event.add_argument("--stage")
    run_event.add_argument("--payload", default="{}")
    run_event.add_argument("--client-event-id")
    run_metric = run_sub.add_parser("log-metric")
    run_metric.add_argument("--run-id", required=True)
    run_metric.add_argument("--namespace", required=True)
    run_metric.add_argument("--values", required=True)
    run_metric.add_argument("--point", default='{"kind":"summary"}')
    run_metric.add_argument("--client-event-id")
    run_metric.add_argument("--strict-contract", action="store_true", help="Fail upload preflight on contract warnings. Also enabled by BLACKBOX_AGENT_STRICT_UPLOAD=1.")
    run_metric.add_argument("--skip-upload-validation", action="store_true", help="Bypass local upload preflight checks.")
    run_metric.add_argument("--dry-run", action="store_true", help="Validate the upload payload locally without writing it.")
    run_series = run_sub.add_parser("log-series")
    run_series.add_argument("--run-id", required=True)
    run_series.add_argument("--name", required=True)
    run_series.add_argument("--data", default="[]")
    run_series.add_argument("--data-file")
    run_series.add_argument("--x")
    run_series.add_argument("--y")
    run_series.add_argument("--mode")
    run_series.add_argument("--namespace")
    run_series.add_argument("--metric-key")
    run_series.add_argument("--metric-namespace")
    run_series.add_argument("--metric-kind", choices=["series", "table"], default="series")
    run_series.add_argument("--result")
    run_series.add_argument("--result-domain")
    run_series.add_argument("--result-name")
    run_series.add_argument("--result-role")
    run_series.add_argument("--result-title")
    run_series.add_argument("--result-group")
    run_series.add_argument("--result-order", type=int)
    run_series.add_argument("--result-view")
    run_series.add_argument("--kind", default="table_csv")
    run_series.add_argument("--filename")
    run_series.add_argument("--metadata", default="{}")
    run_series.add_argument("--idempotency-key")
    run_series.add_argument("--strict-contract", action="store_true", help="Fail upload preflight on contract warnings. Also enabled by BLACKBOX_AGENT_STRICT_UPLOAD=1.")
    run_series.add_argument("--skip-upload-validation", action="store_true", help="Bypass local upload preflight checks.")
    run_series.add_argument("--dry-run", action="store_true", help="Validate the upload payload locally without writing it.")
    run_publish_performance = run_sub.add_parser("publish-performance")
    run_publish_performance.add_argument("--run-id", required=True)
    run_publish_performance.add_argument("--curve-file", required=True, help="Performance rows in JSON, JSONL, CSV, YAML, or Parquet format.")
    run_publish_performance.add_argument("--mode", required=True, choices=["nav", "return", "pnl"])
    run_publish_performance.add_argument("--periods-per-year", type=float, default=252.0, help="Explicit annualization periods. Defaults to 252.")
    run_publish_performance.add_argument("--risk-free-rate", type=float, default=0.0, help="Annual risk-free rate as a decimal, for example 0.02.")
    run_publish_performance.add_argument("--mar", type=float, default=0.0, help="Annual minimum acceptable return as a decimal for Sortino.")
    run_publish_performance.add_argument("--capital-base", type=float, help="Capital base required to derive percentage metrics from mode=pnl.")
    run_publish_performance.add_argument("--x", help="Date/time column. Inferred when exactly one standard date column exists.")
    run_publish_performance.add_argument("--value", help="Value column. Inferred from mode aliases or a single numeric column.")
    run_publish_performance.add_argument("--summary", default="{}", help="strategy.summary values as JSON.")
    run_publish_performance.add_argument("--summary-file", help="strategy.summary values in JSON or YAML format.")
    run_publish_performance.add_argument("--summary-unit", choices=["percentage-point", "decimal"], help="Unit for percentage-style summary metrics; required when such metrics are present.")
    run_publish_performance.add_argument("--drawdown-file", help="Optional drawdown rows in JSON, JSONL, CSV, YAML, or Parquet format.")
    run_publish_performance.add_argument("--drawdown-value", help="Drawdown value column; inferred when omitted.")
    run_publish_performance.add_argument("--idempotency-prefix", required=True, help="Stable prefix reused when retrying the same logical publication.")
    run_publish_performance.add_argument("--expected-start")
    run_publish_performance.add_argument("--expected-end")
    run_publish_performance.add_argument("--expected-rows", type=int)
    run_publish_performance.add_argument("--finish", action="store_true", help="Finish the run after post-upload validation passes.")
    run_publish_performance.add_argument("--fail-on-warning", action="store_true", help="Block publication or finish on quality warnings.")
    run_publish_performance.add_argument("--dry-run", action="store_true", help="Normalize and validate locally without writing.")
    run_finish = run_sub.add_parser("finish")
    run_finish.add_argument("--run-id", required=True)
    run_finish.add_argument("--status", default="completed", choices=["completed"])
    run_finish.add_argument("--fail-on-warning", action="store_true", help="Fail the finish quality gate when validation warnings are present.")
    run_finish.add_argument("--skip-quality-gate", action="store_true", help="Finish without running the result quality gate.")
    run_fail = run_sub.add_parser("fail")
    run_fail.add_argument("--run-id", required=True)
    run_fail.add_argument("--error", default="{}")
    run_cancel = run_sub.add_parser("cancel")
    run_cancel.add_argument("--run-id", required=True)
    run_cancel.add_argument("--reason", default="{}")

    artifact = sub.add_parser("artifact")
    artifact_sub = artifact.add_subparsers(dest="action", required=True)
    artifact_upload = artifact_sub.add_parser("upload")
    artifact_upload.add_argument("--run-id", required=True)
    artifact_upload.add_argument("--name", required=True)
    artifact_upload.add_argument("--kind", default="other")
    artifact_upload.add_argument("--path", required=True)
    artifact_upload.add_argument("--metadata", default="{}")
    artifact_upload.add_argument("--idempotency-key")
    artifact_init = artifact_sub.add_parser("init-upload")
    artifact_init.add_argument("--run-id", required=True)
    artifact_init.add_argument("--name", required=True)
    artifact_init.add_argument("--kind", default="other")
    artifact_init.add_argument("--filename", default="artifact.bin")
    artifact_init.add_argument("--metadata", default="{}")
    artifact_complete = artifact_sub.add_parser("complete-upload")
    artifact_complete.add_argument("--run-id", required=True)
    artifact_complete.add_argument("--name", required=True)
    artifact_complete.add_argument("--uri", required=True)
    artifact_complete.add_argument("--artifact-id")
    artifact_complete.add_argument("--kind", default="other")
    artifact_complete.add_argument("--filename")
    artifact_complete.add_argument("--mime-type")
    artifact_complete.add_argument("--size-bytes", type=int, default=0)
    artifact_complete.add_argument("--sha256", default="")
    artifact_complete.add_argument("--preview", default="{}")
    artifact_complete.add_argument("--metadata", default="{}")
    artifact_complete.add_argument("--idempotency-key")
    artifact_list = artifact_sub.add_parser("list")
    artifact_list.add_argument("--run-id", required=True)
    artifact_get = artifact_sub.add_parser("get")
    artifact_get.add_argument("--artifact-id", required=True)
    artifact_download = artifact_sub.add_parser("download")
    artifact_download.add_argument("--artifact-id", required=True)
    artifact_download.add_argument("--output-path", required=True)
    artifact_external = artifact_sub.add_parser("register-external")
    artifact_external.add_argument("--run-id", required=True)
    artifact_external.add_argument("--name", required=True)
    artifact_external.add_argument("--uri", required=True)
    artifact_external.add_argument("--kind", default="other")
    artifact_external.add_argument("--filename")
    artifact_external.add_argument("--mime-type")
    artifact_external.add_argument("--size-bytes", type=int)
    artifact_external.add_argument("--sha256")
    artifact_external.add_argument("--preview", default="{}")
    artifact_external.add_argument("--metadata", default="{}")
    artifact_external.add_argument("--idempotency-key")

    note = sub.add_parser("note")
    note_sub = note.add_subparsers(dest="action", required=True)
    note_add = note_sub.add_parser("add")
    note_add.add_argument("--run-id", required=True)
    note_add.add_argument("--kind", default="observation")
    note_add.add_argument("--summary", required=True)
    note_add.add_argument("--content")
    note_add.add_argument("--structured", default="{}")
    note_add.add_argument("--structured-file")
    note_add.add_argument("--author-type", default="human")
    note_add.add_argument("--client-event-id")
    note_list = note_sub.add_parser("list")
    note_list.add_argument("--run-id", required=True)

    search = sub.add_parser("search")
    search_sub = search.add_subparsers(dest="action", required=True)
    search_runs = search_sub.add_parser("runs")
    search_runs.add_argument("--project")
    search_runs.add_argument("--research")
    search_runs.add_argument("--branch")
    search_runs.add_argument("--status")
    search_runs.add_argument("--branch-id")
    search_runs.add_argument("--name")
    search_runs.add_argument("--author-type")
    search_runs.add_argument("--created-after")
    search_runs.add_argument("--created-before")
    search_runs.add_argument("--updated-after")
    search_runs.add_argument("--updated-before")
    search_runs.add_argument("--started-after")
    search_runs.add_argument("--started-before")
    search_runs.add_argument("--ended-after")
    search_runs.add_argument("--ended-before")
    search_runs.add_argument("--tag", action="append", default=[])
    search_runs.add_argument("--metric", action="append", default=[])
    search_runs.add_argument("--config", action="append", default=[])
    search_runs.add_argument("--context", action="append", default=[])
    search_runs.add_argument("--has-artifact")
    search_runs.add_argument("--where", help='Search expression, for example: metrics.strategy.summary.sharpe > 1.2 and tags contains "baseline"')
    search_runs.add_argument("--limit", type=int, default=50)
    search_runs.add_argument("--select", default=argparse.SUPPRESS)
    search_researches = search_sub.add_parser("researches")
    search_researches.add_argument("--project")
    search_researches.add_argument("--project-id")
    search_researches.add_argument("--status")
    search_researches.add_argument("--key")
    search_researches.add_argument("--text")
    search_researches.add_argument("--tag", action="append", default=[])
    search_researches.add_argument("--limit", type=int, default=50)
    search_researches.add_argument("--select", default=argparse.SUPPRESS)
    search_view = sub.add_parser("search-view")
    search_view_sub = search_view.add_subparsers(dest="action", required=True)
    search_view_create = search_view_sub.add_parser("create")
    search_view_create.add_argument("--project-id", required=True)
    search_view_create.add_argument("--name", required=True)
    search_view_create.add_argument("--description")
    search_view_create.add_argument("--filters", required=True)
    search_view_list = search_view_sub.add_parser("list")
    search_view_list.add_argument("--project-id", required=True)
    search_view_get = search_view_sub.add_parser("get")
    search_view_get.add_argument("--view-id", required=True)
    search_view_run = search_view_sub.add_parser("run")
    search_view_run.add_argument("--view-id", required=True)
    search_view_run.add_argument("--overrides", default="{}")
    search_view_update = search_view_sub.add_parser("update")
    search_view_update.add_argument("--view-id", required=True)
    search_view_update.add_argument("--name")
    search_view_update.add_argument("--description")
    search_view_update.add_argument("--filters")

    compare = sub.add_parser("compare")
    compare_sub = compare.add_subparsers(dest="action", required=True)
    compare_runs = compare_sub.add_parser("runs")
    compare_runs.add_argument("--run-ids", nargs="+", required=True)
    compare_runs.add_argument("--metrics", default="")
    compare_runs.add_argument("--series", default="")
    compare_runs.add_argument("--with-config-diff", action="store_true", default=True)
    compare_runs.add_argument("--no-config-diff", action="store_false", dest="with_config_diff")
    compare_runs.add_argument("--fail-on-warning", action="store_true", help="Fail compare when any selected run has quality warnings.")
    compare_runs.add_argument("--skip-quality-gate", action="store_true", help="Compare runs without applying the result quality gate.")

    lineage = sub.add_parser("lineage")
    lineage_sub = lineage.add_subparsers(dest="action", required=True)
    lineage_research = lineage_sub.add_parser("research")
    lineage_research.add_argument("--research-id", required=True)
    lineage_branch = lineage_sub.add_parser("branch")
    lineage_branch.add_argument("--branch-id", required=True)

    sweep = sub.add_parser("sweep")
    sweep_sub = sweep.add_subparsers(dest="action", required=True)
    sweep_create = sweep_sub.add_parser("create")
    sweep_create.add_argument("--branch-id", required=True)
    sweep_create.add_argument("--name", required=True)
    sweep_create.add_argument("--search-space", default="{}")
    sweep_create.add_argument("--objective", default="{}")
    sweep_create.add_argument("--status", default="active")
    sweep_list = sweep_sub.add_parser("list")
    sweep_list.add_argument("--branch-id", required=True)
    sweep_get = sweep_sub.add_parser("get")
    sweep_get.add_argument("--sweep-id", required=True)
    sweep_summary = sweep_sub.add_parser("summary")
    sweep_summary.add_argument("--sweep-id", required=True)
    sweep_attach = sweep_sub.add_parser("attach-run")
    sweep_attach.add_argument("--sweep-id", required=True)
    sweep_attach.add_argument("--run-id", required=True)
    sweep_attach.add_argument("--coord", default="{}")
    sweep_attach.add_argument("--rank", type=int)

    compare_set = sub.add_parser("compare-set")
    compare_set_sub = compare_set.add_subparsers(dest="action", required=True)
    compare_set_create = compare_set_sub.add_parser("create")
    compare_set_create.add_argument("--project-id", required=True)
    compare_set_create.add_argument("--research-id")
    compare_set_create.add_argument("--name", required=True)
    compare_set_create.add_argument("--run-ids", nargs="+", required=True)
    compare_set_create.add_argument("--layout", default="{}")
    compare_set_list = compare_set_sub.add_parser("list")
    compare_set_list.add_argument("--project-id")
    compare_set_list.add_argument("--research-id")
    compare_set_get = compare_set_sub.add_parser("get")
    compare_set_get.add_argument("--compare-set-id", required=True)
    compare_set_update = compare_set_sub.add_parser("update")
    compare_set_update.add_argument("--compare-set-id", required=True)
    compare_set_update.add_argument("--name")
    compare_set_update.add_argument("--research-id")
    compare_set_update.add_argument("--run-ids", nargs="+")
    compare_set_update.add_argument("--layout")
    compare_set_run = compare_set_sub.add_parser("run")
    compare_set_run.add_argument("--compare-set-id", required=True)
    compare_set_run.add_argument("--metrics")
    compare_set_run.add_argument("--series")
    compare_set_run.add_argument("--with-config-diff", action="store_true", default=True)
    compare_set_run.add_argument("--no-config-diff", action="store_false", dest="with_config_diff")

    batch = sub.add_parser("batch")
    batch_sub = batch.add_subparsers(dest="action", required=True)
    batch_note = batch_sub.add_parser("add-note")
    batch_note.add_argument("--run-ids", nargs="+")
    batch_note.add_argument("--run-ids-file")
    batch_note.add_argument("--kind", default="observation")
    batch_note.add_argument("--summary", required=True)
    batch_note.add_argument("--content")
    batch_note.add_argument("--structured", default="{}")
    batch_note.add_argument("--structured-file")
    batch_note.add_argument("--author-type", default="agent")
    batch_branch = batch_sub.add_parser("mark-branch-status")
    batch_branch.add_argument("--branch-ids")
    batch_branch.add_argument("--branch-ids-file")
    batch_branch.add_argument("--status", required=True)
    batch_compare = batch_sub.add_parser("compare")
    batch_compare.add_argument("--run-ids", nargs="+")
    batch_compare.add_argument("--run-ids-file")
    batch_compare.add_argument("--groups")
    batch_compare.add_argument("--groups-file")
    batch_compare.add_argument("--metrics", default="")
    batch_compare.add_argument("--series", default="")
    batch_compare.add_argument("--with-config-diff", action="store_true", default=True)
    batch_compare.add_argument("--no-config-diff", action="store_false", dest="with_config_diff")

    snapshot = sub.add_parser("snapshot")
    snapshot_sub = snapshot.add_subparsers(dest="action", required=True)
    snapshot_add = snapshot_sub.add_parser("add")
    snapshot_add.add_argument("--run-id", required=True)
    snapshot_add.add_argument("--kind", required=True, choices=["code", "data", "env"])
    snapshot_add.add_argument("--payload", default="{}")
    snapshot_add.add_argument("--payload-file")
    snapshot_list = snapshot_sub.add_parser("list")
    snapshot_list.add_argument("--run-id", required=True)

    dataset = sub.add_parser("dataset")
    dataset_sub = dataset.add_subparsers(dest="action", required=True)
    dataset_register = dataset_sub.add_parser("register")
    dataset_register.add_argument("--run-id", required=True)
    dataset_register.add_argument("--name", "--dataset-name", dest="dataset_name")
    dataset_register.add_argument("--version", "--dataset-version", dest="dataset_version")
    dataset_register.add_argument("--fingerprint")
    dataset_register.add_argument("--universe")
    dataset_register.add_argument("--benchmark")
    dataset_register.add_argument("--calendar")
    dataset_register.add_argument("--fee-model")
    dataset_register.add_argument("--slippage-model")
    dataset_register.add_argument("--time-range", default="{}")
    dataset_register.add_argument("--time-range-file")
    dataset_register.add_argument("--metadata", default="{}")
    dataset_register.add_argument("--metadata-file")

    db = sub.add_parser("db")
    db_sub = db.add_subparsers(dest="action", required=True)
    db_sub.add_parser("status")
    db_sub.add_parser("migrate")

    sync = sub.add_parser("sync")
    sync.add_argument("--spool-dir", default=os.getenv("BLACKBOX_SPOOL_DIR") or os.getenv("BLACKBOX_DATA_DIR") or "~/.blackbox")
    sync.add_argument("--include-synced", action="store_true")

    return parser


def dispatch(args: argparse.Namespace) -> Any:
    if args.group == "workspace" and args.action == "create":
        return request(args, "POST", "/api/v1/workspaces", json={"id": args.id, "key": args.key, "title": args.title, "description": args.description, "roles": parse_json(args.roles)})
    if args.group == "workspace" and args.action == "update":
        return request(args, "PATCH", f"/api/v1/workspaces/{args.workspace_id}", json=compact_payload({"title": args.title, "description": args.description, "roles": parse_json(args.roles) if args.roles is not None else None}))
    if args.group == "workspace" and args.action == "get":
        return request(args, "GET", f"/api/v1/workspaces/{args.workspace_id}")
    if args.group == "workspace" and args.action == "list":
        return request(args, "GET", "/api/v1/workspaces")
    if args.group == "project" and args.action == "create":
        return request(
            args,
            "POST",
            "/api/v1/projects",
            json={
                "workspace_id": args.workspace_id,
                "key": args.key,
                "title": args.title,
                "description": args.description,
                "tags": parse_json(args.tags),
                "retention_policy": parse_json(args.retention_policy),
            },
        )
    if args.group == "project" and args.action == "update":
        return request(
            args,
            "PATCH",
            f"/api/v1/projects/{args.project_id}",
            json=compact_payload({
                "title": args.title,
                "description": args.description,
                "tags": parse_json(args.tags) if args.tags is not None else None,
                "retention_policy": parse_json(args.retention_policy) if args.retention_policy is not None else None,
            }),
        )
    if args.group == "project" and args.action == "get":
        return request(args, "GET", f"/api/v1/projects/{args.project_id}")
    if args.group == "project" and args.action == "list":
        return request(args, "GET", "/api/v1/projects")
    if args.group == "research" and args.action == "create":
        return request(args, "POST", "/api/v1/researches", json={"project_key": args.project, "key": args.key, "title": args.title, "goal": args.goal, "hypothesis": args.hypothesis})
    if args.group == "research" and args.action == "list":
        return request(args, "GET", f"/api/v1/projects/{args.project_id}/researches")
    if args.group == "research" and args.action == "get":
        return request(args, "GET", f"/api/v1/researches/{args.research_id}")
    if args.group == "research" and args.action == "update":
        return request(args, "PATCH", f"/api/v1/researches/{args.research_id}", json=compact_payload({"title": args.title, "goal": args.goal, "hypothesis": args.hypothesis, "status": args.status, "tags": parse_json(args.tags) if args.tags is not None else None}))
    if args.group == "research" and args.action == "review":
        return request(args, "GET", f"/api/v1/researches/{args.research_id}/review-board", params={"metric": args.metric, "direction": args.direction, "stale_days": args.stale_days, "limit": args.limit})
    if args.group == "branch" and args.action == "create":
        payload = {"research_id": args.research_id, "research_key": args.research, "key": args.key, "title": args.title, "source_run_id": args.source_run_id, "parent_branch_id": args.parent_branch_id, "reason_code": args.reason_code, "reason_summary": args.reason_summary}
        payload.update(compact_payload({"created_by_type": args.created_by_type, "created_by_id": args.created_by_id}))
        return request(args, "POST", "/api/v1/branches", json=payload)
    if args.group == "branch" and args.action == "list":
        return request(args, "GET", f"/api/v1/researches/{args.research_id}/branches")
    if args.group == "branch" and args.action == "get":
        return request(args, "GET", f"/api/v1/branches/{args.branch_id}")
    if args.group == "branch" and args.action == "update":
        return request(args, "PATCH", f"/api/v1/branches/{args.branch_id}", json=compact_payload({"title": args.title, "parent_branch_id": args.parent_branch_id, "source_run_id": args.source_run_id, "reason_code": args.reason_code, "reason_summary": args.reason_summary, "hypothesis": args.hypothesis, "expected_change": parse_json(args.expected_change) if args.expected_change is not None else None, "status": args.status}))
    if args.group == "run" and args.action == "start":
        config = parse_structured_file(args.config_file, "config file") if args.config_file else parse_json(args.config)
        headers = {"Idempotency-Key": args.idempotency_key} if args.idempotency_key else {}
        return request(
            args,
            "POST",
            "/api/v1/runs",
            headers=headers,
            json={
                "project_key": args.project,
                "research_key": args.research,
                "branch_key": args.branch,
                "name": args.name,
                "title": args.title,
                "source_run_id": args.source_run_id,
                "config": config,
                "context": parse_json(args.context),
                "tags": parse_json(args.tags),
                **compact_payload({"created_by_type": args.created_by_type, "created_by_id": args.created_by_id}),
            },
        )
    if args.group == "run" and args.action == "get":
        return request(args, "GET", f"/api/v1/runs/{args.run_id}")
    if args.group == "run" and args.action == "validate":
        detail = request(args, "GET", f"/api/v1/runs/{args.run_id}")
        report = validate_run_detail(
            detail,
            expected_start=args.expected_start,
            expected_end=args.expected_end,
            expected_rows=args.expected_rows,
            primary_series_name=args.primary_series,
        )
        return {"run_id": args.run_id, **report}
    if args.group == "run" and args.action == "update":
        config = parse_structured_file(args.config_file, "config file") if args.config_file else (parse_json(args.config) if args.config is not None else None)
        return request(args, "PATCH", f"/api/v1/runs/{args.run_id}", json=compact_payload({"name": args.name, "title": args.title, "source_run_id": args.source_run_id, "config": config, "context": parse_json(args.context) if args.context is not None else None, "tags": parse_json(args.tags) if args.tags is not None else None}))
    if args.group == "run" and args.action == "clone":
        config_overrides = parse_structured_file(args.config_overrides_file, "config overrides file") if args.config_overrides_file else parse_json(args.config_overrides)
        headers = {"Idempotency-Key": args.idempotency_key} if args.idempotency_key else {}
        return request(
            args,
            "POST",
            f"/api/v1/runs/{args.run_id}/clone",
            headers=headers,
            json={
                "branch_id": args.branch_id,
                "name": args.name,
                "title": args.title,
                "config_overrides": config_overrides,
                "context_overrides": parse_json(args.context_overrides),
                "tags": parse_json(args.tags) if args.tags else None,
                **compact_payload({"created_by_type": args.created_by_type, "created_by_id": args.created_by_id}),
            },
        )
    if args.group == "run" and args.action == "log-event":
        return request(args, "POST", f"/api/v1/runs/{args.run_id}/events", json=compact_payload({"event_type": args.event_type, "stage": args.stage, "payload": parse_json(args.payload), "client_event_id": args.client_event_id}))
    if args.group == "run" and args.action == "log-metric":
        values = parse_json(args.values)
        report = validate_metric_upload(args.namespace, values, strict=upload_validation_strict(args))
        if not args.skip_upload_validation:
            enforce_upload_preflight(report, fail_on_warning=upload_validation_strict(args))
        if args.dry_run:
            return {"dry_run": True, "kind": "metric", "namespace": args.namespace, "validation": report}
        return request(args, "POST", f"/api/v1/runs/{args.run_id}/metrics", json=compact_payload({"namespace": args.namespace, "values": values, "point": parse_json(args.point), "client_event_id": args.client_event_id}))
    if args.group == "run" and args.action == "log-series":
        data = parse_json(Path(args.data_file).read_text(encoding="utf-8")) if args.data_file else parse_json(args.data)
        headers = {"Idempotency-Key": args.idempotency_key} if args.idempotency_key else {}
        series_payload = {
            "name": args.name,
            "data": data,
            "x": args.x,
            "y": parse_csv_arg(args.y),
            "mode": args.mode,
            "namespace": args.namespace,
            "kind": args.kind,
            "filename": args.filename,
            "metadata": parse_json(args.metadata),
        }
        if args.metric_key:
            series_payload["metric"] = compact_payload({"namespace": args.metric_namespace or args.namespace, "key": args.metric_key, "kind": args.metric_kind, "x": args.x, "y": parse_csv_arg(args.y), "mode": args.mode})
        result_payload = build_result_payload(args)
        if result_payload:
            series_payload["result"] = result_payload
        report = validate_series_upload(series_payload, strict=upload_validation_strict(args))
        if not args.skip_upload_validation:
            enforce_upload_preflight(report, fail_on_warning=upload_validation_strict(args))
        if args.dry_run:
            return {"dry_run": True, "kind": "series", "name": args.name, "validation": report, "rows": len(data) if isinstance(data, list) else None}
        return request(
            args,
            "POST",
            f"/api/v1/runs/{args.run_id}/series",
            headers=headers,
            json=series_payload,
        )
    if args.group == "run" and args.action == "publish-performance":
        return publish_performance(args)
    if args.group == "run" and args.action == "finish":
        params = compact_payload({"fail_on_warning": args.fail_on_warning or None, "skip_quality_gate": args.skip_quality_gate or None})
        return request(
            args,
            "POST",
            f"/api/v1/runs/{args.run_id}/finish",
            **({"params": params} if params else {}),
        )
    if args.group == "run" and args.action == "fail":
        return request(args, "POST", f"/api/v1/runs/{args.run_id}/fail", json=parse_json(args.error))
    if args.group == "run" and args.action == "cancel":
        return request(args, "POST", f"/api/v1/runs/{args.run_id}/cancel", json=parse_json(args.reason))
    if args.group == "artifact" and args.action == "upload":
        path = Path(args.path)
        headers = {"Idempotency-Key": args.idempotency_key} if args.idempotency_key else {}
        return request(
            args,
            "POST",
            f"/api/v1/runs/{args.run_id}/artifacts/upload",
            headers=headers,
            params={"name": args.name, "kind": args.kind, "filename": path.name, "metadata": json.dumps(parse_json(args.metadata), ensure_ascii=False)},
            content=path.read_bytes(),
        )
    if args.group == "artifact" and args.action == "init-upload":
        return request(
            args,
            "POST",
            f"/api/v1/runs/{args.run_id}/artifacts/init-upload",
            json={
                "name": args.name,
                "kind": args.kind,
                "filename": args.filename,
                "metadata": parse_json(args.metadata),
            },
        )
    if args.group == "artifact" and args.action == "complete-upload":
        headers = {"Idempotency-Key": args.idempotency_key} if args.idempotency_key else {}
        return request(
            args,
            "POST",
            f"/api/v1/runs/{args.run_id}/artifacts/complete-upload",
            headers=headers,
            json=compact_payload(
                {
                    "artifact_id": args.artifact_id,
                    "name": args.name,
                    "kind": args.kind,
                    "uri": args.uri,
                    "filename": args.filename,
                    "mime_type": args.mime_type,
                    "size_bytes": args.size_bytes,
                    "sha256": args.sha256,
                    "preview": parse_json(args.preview),
                    "metadata": parse_json(args.metadata),
                }
            ),
        )
    if args.group == "artifact" and args.action == "list":
        return request(args, "GET", f"/api/v1/runs/{args.run_id}/artifacts")
    if args.group == "artifact" and args.action == "get":
        return request(args, "GET", f"/api/v1/artifacts/{args.artifact_id}")
    if args.group == "artifact" and args.action == "download":
        return download_artifact(args)
    if args.group == "artifact" and args.action == "register-external":
        headers = {"Idempotency-Key": args.idempotency_key} if args.idempotency_key else {}
        return request(
            args,
            "POST",
            f"/api/v1/runs/{args.run_id}/artifacts/register-external",
            headers=headers,
            json=compact_payload(
                {
                    "name": args.name,
                    "uri": args.uri,
                    "kind": args.kind,
                    "filename": args.filename,
                    "mime_type": args.mime_type,
                    "size_bytes": args.size_bytes,
                    "sha256": args.sha256,
                    "preview": parse_json(args.preview),
                    "metadata": parse_json(args.metadata),
                }
            ),
        )
    if args.group == "note" and args.action == "add":
        return request(args, "POST", f"/api/v1/runs/{args.run_id}/notes", json=note_payload(args))
    if args.group == "note" and args.action == "list":
        return request(args, "GET", f"/api/v1/runs/{args.run_id}/notes")
    if args.group == "search" and args.action == "runs":
        where_filters = parse_search_where(args.where)
        return request(
            args,
            "POST",
            "/api/v1/search/runs",
            json={
                "project_key": args.project or where_filters.get("project_key"),
                "research_key": args.research or where_filters.get("research_key"),
                "branch_key": args.branch or where_filters.get("branch_key"),
                "status": args.status or where_filters.get("status"),
                "branch_id": args.branch_id or where_filters.get("branch_id"),
                "name": args.name or where_filters.get("name"),
                "author_type": args.author_type or where_filters.get("author_type"),
                "created_after": args.created_after,
                "created_before": args.created_before,
                "updated_after": args.updated_after,
                "updated_before": args.updated_before,
                "started_after": args.started_after,
                "started_before": args.started_before,
                "ended_after": args.ended_after,
                "ended_before": args.ended_before,
                "tags": args.tag + where_filters.get("tags", []),
                "metrics": [parse_metric_filter(item) for item in args.metric] + where_filters.get("metrics", []),
                "config": {**parse_key_value_filters(args.config), **where_filters.get("config", {})},
                "context": {**parse_key_value_filters(args.context), **where_filters.get("context", {})},
                "has_artifact": args.has_artifact or where_filters.get("has_artifact"),
                "limit": args.limit,
            },
        )
    if args.group == "search" and args.action == "researches":
        return request(
            args,
            "POST",
            "/api/v1/search/researches",
            json={
                "project_key": args.project,
                "project_id": args.project_id,
                "status": args.status,
                "key": args.key,
                "text": args.text,
                "tags": args.tag,
                "limit": args.limit,
            },
        )
    if args.group == "search-view" and args.action == "create":
        return request(args, "POST", "/api/v1/search-views", json={"project_id": args.project_id, "name": args.name, "description": args.description, "filters": parse_json(args.filters)})
    if args.group == "search-view" and args.action == "list":
        return request(args, "GET", f"/api/v1/projects/{args.project_id}/search-views")
    if args.group == "search-view" and args.action == "get":
        return request(args, "GET", f"/api/v1/search-views/{args.view_id}")
    if args.group == "search-view" and args.action == "run":
        return request(args, "POST", f"/api/v1/search-views/{args.view_id}/run", json=parse_json(args.overrides))
    if args.group == "search-view" and args.action == "update":
        return request(args, "PATCH", f"/api/v1/search-views/{args.view_id}", json=compact_payload({"name": args.name, "description": args.description, "filters": parse_json(args.filters) if args.filters is not None else None}))
    if args.group == "compare" and args.action == "runs":
        return request(
            args,
            "POST",
            "/api/v1/compare/runs",
            json={
                "run_ids": parse_id_values(args.run_ids),
                "metrics": split_csv(args.metrics),
                "series": split_csv(args.series),
                "with_config_diff": args.with_config_diff,
                **compact_payload({"fail_on_warning": args.fail_on_warning or None, "skip_quality_gate": args.skip_quality_gate or None}),
            },
        )
    if args.group == "lineage" and args.action == "research":
        return request(args, "GET", f"/api/v1/lineage/researches/{args.research_id}")
    if args.group == "lineage" and args.action == "branch":
        return request(args, "GET", f"/api/v1/lineage/branches/{args.branch_id}")
    if args.group == "sweep" and args.action == "create":
        return request(
            args,
            "POST",
            "/api/v1/sweeps",
            json={
                "branch_id": args.branch_id,
                "name": args.name,
                "search_space": parse_json(args.search_space),
                "objective": parse_json(args.objective),
                "status": args.status,
            },
        )
    if args.group == "sweep" and args.action == "list":
        return request(args, "GET", f"/api/v1/branches/{args.branch_id}/sweeps")
    if args.group == "sweep" and args.action == "get":
        return request(args, "GET", f"/api/v1/sweeps/{args.sweep_id}")
    if args.group == "sweep" and args.action == "summary":
        return request(args, "GET", f"/api/v1/sweeps/{args.sweep_id}/summary")
    if args.group == "sweep" and args.action == "attach-run":
        return request(
            args,
            "POST",
            f"/api/v1/sweeps/{args.sweep_id}/runs",
            json={"run_id": args.run_id, "coord": parse_json(args.coord), "rank": args.rank},
        )
    if args.group == "compare-set" and args.action == "create":
        return request(
            args,
            "POST",
            "/api/v1/compare-sets",
            json=compact_payload(
                {
                    "project_id": args.project_id,
                    "research_id": args.research_id,
                    "name": args.name,
                    "run_ids": parse_id_values(args.run_ids),
                    "layout": parse_json(args.layout),
                }
            ),
        )
    if args.group == "compare-set" and args.action == "list":
        if args.research_id:
            return request(args, "GET", f"/api/v1/researches/{args.research_id}/compare-sets")
        if not args.project_id:
            raise CliError("VALIDATION_ERROR", "compare-set list requires --project-id or --research-id")
        return request(args, "GET", f"/api/v1/projects/{args.project_id}/compare-sets")
    if args.group == "compare-set" and args.action == "get":
        return request(args, "GET", f"/api/v1/compare-sets/{args.compare_set_id}")
    if args.group == "compare-set" and args.action == "update":
        return request(
            args,
            "PATCH",
            f"/api/v1/compare-sets/{args.compare_set_id}",
            json=compact_payload(
                {
                    "name": args.name,
                    "research_id": args.research_id,
                    "run_ids": parse_id_values(args.run_ids) if args.run_ids is not None else None,
                    "layout": parse_json(args.layout) if args.layout is not None else None,
                }
            ),
        )
    if args.group == "compare-set" and args.action == "run":
        compare_set = request(args, "GET", f"/api/v1/compare-sets/{args.compare_set_id}")
        layout = compare_set.get("layout_json") or {}
        return request(
            args,
            "POST",
            "/api/v1/compare/runs",
            json={
                "run_ids": compare_set.get("run_ids_json") or [],
                "metrics": split_csv(args.metrics) if args.metrics is not None else list_or_csv(layout.get("metrics", [])),
                "series": split_csv(args.series) if args.series is not None else list_or_csv(layout.get("series", [])),
                "with_config_diff": args.with_config_diff,
            },
        )
    if args.group == "batch" and args.action == "add-note":
        run_ids = parse_id_list(args.run_ids, args.run_ids_file, "run_ids")
        items = [
            batch_request(
                args,
                {"run_id": run_id},
                "POST",
                f"/api/v1/runs/{run_id}/notes",
                json=note_payload(args),
            )
            for run_id in run_ids
        ]
        return batch_summary("add-note", items)
    if args.group == "batch" and args.action == "mark-branch-status":
        branch_ids = parse_id_list(args.branch_ids, args.branch_ids_file, "branch_ids")
        items = [
            batch_request(
                args,
                {"branch_id": branch_id},
                "PATCH",
                f"/api/v1/branches/{branch_id}",
                json={"status": args.status},
            )
            for branch_id in branch_ids
        ]
        return batch_summary("mark-branch-status", items)
    if args.group == "batch" and args.action == "compare":
        groups = parse_compare_groups(args)
        items = [
            batch_request(
                args,
                {"name": group.get("name"), "run_ids": group["run_ids"]},
                "POST",
                "/api/v1/compare/runs",
                json={
                    "run_ids": group["run_ids"],
                    "metrics": group.get("metrics", split_csv(args.metrics)),
                    "series": group.get("series", split_csv(args.series)),
                    "with_config_diff": group.get("with_config_diff", args.with_config_diff),
                },
            )
            for group in groups
        ]
        return batch_summary("compare", items)
    if args.group == "snapshot" and args.action == "add":
        payload = parse_json(Path(args.payload_file).read_text(encoding="utf-8")) if args.payload_file else parse_json(args.payload)
        if not isinstance(payload, dict):
            raise CliError("VALIDATION_ERROR", "snapshot payload must be a JSON object")
        return request(args, "POST", f"/api/v1/runs/{args.run_id}/snapshots/{args.kind}", json=payload)
    if args.group == "snapshot" and args.action == "list":
        return request(args, "GET", f"/api/v1/runs/{args.run_id}/snapshots")
    if args.group == "dataset" and args.action == "register":
        return request(args, "POST", f"/api/v1/runs/{args.run_id}/snapshots/data", json=dataset_payload(args))
    if args.group == "db" and args.action == "status":
        return database_status()
    if args.group == "db" and args.action == "migrate":
        return database_migrate()
    if args.group == "sync":
        return sync_spool(args.endpoint, args.spool_dir, include_synced=args.include_synced, token=args.token)
    raise CliError("VALIDATION_ERROR", "unsupported command")


PERCENT_SUMMARY_KEYS = {
    "annual_return",
    "annualized_return",
    "annual_volatility",
    "annualized_volatility",
    "max_drawdown",
}
CANONICAL_PERFORMANCE_KEYS = {
    "annual_return",
    "annualized_return",
    "annual_volatility",
    "annualized_volatility",
    "max_drawdown",
    "sharpe",
    "sortino",
    "calmar",
    "periods_per_year",
    "total_pnl",
    "annualized_pnl",
}


def publish_performance(args: argparse.Namespace) -> dict[str, Any]:
    curve_rows = parse_rows_file(args.curve_file, "curve file")
    curve_rows, x_key, value_key, normalizations = normalize_performance_rows(
        curve_rows,
        mode=args.mode,
        x=args.x,
        value=args.value,
        label="performance curve",
    )
    try:
        computed_summary = compute_performance_summary(
            curve_rows,
            mode=args.mode,
            periods_per_year=args.periods_per_year,
            risk_free_rate=args.risk_free_rate,
            mar=args.mar,
            capital_base=args.capital_base,
        )
    except ValueError as exc:
        raise CliError(
            "VALIDATION_ERROR",
            str(exc),
            exit_code=4,
            details={"issues": [{"code": "PERFORMANCE_CALCULATION_INVALID", "field": "curve-file", "fix": "Correct the curve values or annualization arguments, then retry."}]},
        ) from exc
    curve_name, namespace = performance_contract(args.mode)
    curve_payload = {
        "name": curve_name,
        "data": curve_rows,
        "x": x_key,
        "y": "series_values",
        "mode": args.mode,
        "namespace": namespace,
        "kind": "table_csv",
        "filename": f"{curve_name}.csv",
        "metadata": {
            "performance": performance_metadata(
                mode=args.mode,
                periods_per_year=args.periods_per_year,
                risk_free_rate=args.risk_free_rate,
                mar=args.mar,
                capital_base=args.capital_base,
            )
        },
        "result": {
            "domain": "performance",
            "name": "primary_performance",
            "role": "primary_curve",
            "title": "Performance Curve",
            "group": "performance.primary",
            "order": 10,
            "view": {"default": "performance_chart", "x": x_key, "y": "series_values", "mode": args.mode, "chart": "line_drawdown"},
        },
    }
    curve_report = validate_series_upload(curve_payload, strict=True)
    enforce_upload_preflight(curve_report, fail_on_warning=args.fail_on_warning)

    reported_summary = parse_structured_object_file(args.summary_file, "summary file") if args.summary_file else parse_json_object_arg(args.summary, "summary")
    reported_summary, summary_normalizations = normalize_summary_metrics(reported_summary, args.summary_unit)
    normalizations.extend(summary_normalizations)
    if reported_summary:
        curve_payload["metadata"]["reported_summary"] = reported_summary
    for key in sorted(CANONICAL_PERFORMANCE_KEYS.intersection(reported_summary)):
        if key in computed_summary and finite_number(reported_summary[key]) != finite_number(computed_summary[key]):
            normalizations.append({
                "code": "REPLACE_REPORTED_PERFORMANCE_METRIC",
                "field": key,
                "reported": reported_summary[key],
                "computed": computed_summary[key],
            })
    summary = {key: value for key, value in reported_summary.items() if key not in CANONICAL_PERFORMANCE_KEYS}
    summary.update(computed_summary)
    normalizations.append({"code": "COMPUTE_PERFORMANCE_SUMMARY", "fields": sorted(computed_summary)})
    summary_report = validate_metric_upload("strategy.summary", summary, strict=True, percent_unit="percentage_point") if summary else empty_validation_report()
    if summary:
        enforce_upload_preflight(summary_report, fail_on_warning=args.fail_on_warning)

    drawdown_payload: dict[str, Any] | None = None
    drawdown_report = empty_validation_report()
    if args.drawdown_file:
        drawdown_rows = parse_rows_file(args.drawdown_file, "drawdown file")
        drawdown_rows, drawdown_x, _, drawdown_normalizations = normalize_performance_rows(
            drawdown_rows,
            mode="drawdown",
            x=args.x or x_key,
            value=args.drawdown_value,
            label="drawdown series",
        )
        normalizations.extend(drawdown_normalizations)
        drawdown_payload = {
            "name": "drawdown_series",
            "data": drawdown_rows,
            "x": drawdown_x,
            "y": "series_values",
            "mode": "drawdown",
            "namespace": "strategy.drawdown",
            "kind": "table_csv",
            "filename": "drawdown_series.csv",
            "metadata": {},
            "result": {
                "domain": "performance",
                "name": "primary_drawdown",
                "role": "drawdown",
                "title": "Drawdown",
                "group": "performance.primary",
                "order": 20,
                "view": {"default": "drawdown", "x": drawdown_x, "y": "series_values", "mode": "drawdown", "chart": "area"},
            },
        }
        drawdown_report = validate_series_upload(drawdown_payload, strict=True)
        enforce_upload_preflight(drawdown_report, fail_on_warning=args.fail_on_warning)

    preflight = {
        "curve": compact_validation_report(curve_report),
        "summary": compact_validation_report(summary_report),
        "drawdown": compact_validation_report(drawdown_report),
    }
    if args.dry_run:
        return {
            "action": "publish-performance",
            "dry_run": True,
            "run_id": args.run_id,
            "mode": args.mode,
            "primary_series": curve_name,
            "rows": len(curve_rows),
            "summary_metrics": len(summary),
            "computed_summary": computed_summary,
            "normalizations": normalizations,
            "preflight": preflight,
            "finished": False,
        }

    uploaded: list[dict[str, Any]] = []
    if summary:
        metric_result = request(
            args,
            "POST",
            f"/api/v1/runs/{args.run_id}/metrics",
            json={
                "namespace": "strategy.summary",
                "values": summary,
                "point": {"kind": "summary", "coord": {"percent_unit": "percentage_point"}},
                "client_event_id": f"{args.idempotency_prefix}-summary",
            },
        )
        uploaded.append({"kind": "metric", "namespace": "strategy.summary", "count": len(metric_result) if isinstance(metric_result, list) else len(summary)})

    curve_result = request(
        args,
        "POST",
        f"/api/v1/runs/{args.run_id}/series",
        headers={"Idempotency-Key": f"{args.idempotency_prefix}-curve"},
        json=curve_payload,
    )
    uploaded.append({"kind": "series", "name": curve_name, "artifact_id": curve_result.get("id") if isinstance(curve_result, dict) else None, "rows": len(curve_rows)})

    if drawdown_payload is not None:
        drawdown_result = request(
            args,
            "POST",
            f"/api/v1/runs/{args.run_id}/series",
            headers={"Idempotency-Key": f"{args.idempotency_prefix}-drawdown"},
            json=drawdown_payload,
        )
        uploaded.append({"kind": "series", "name": "drawdown_series", "artifact_id": drawdown_result.get("id") if isinstance(drawdown_result, dict) else None, "rows": len(drawdown_payload["data"])})

    detail = request(args, "GET", f"/api/v1/runs/{args.run_id}")
    quality_report = validate_run_detail(
        detail,
        expected_start=args.expected_start or str(curve_rows[0][x_key]),
        expected_end=args.expected_end or str(curve_rows[-1][x_key]),
        expected_rows=args.expected_rows if args.expected_rows is not None else len(curve_rows),
        primary_series_name=curve_name,
    )
    if upload_report_failed(quality_report, fail_on_warning=args.fail_on_warning):
        raise CliError(
            "VALIDATION_ERROR",
            "published performance result failed the post-upload quality gate",
            exit_code=4,
            hint=quality_report.get("hint"),
            details=quality_report,
        )

    finished = False
    if args.finish:
        params = {"fail_on_warning": True} if args.fail_on_warning else {}
        request(args, "POST", f"/api/v1/runs/{args.run_id}/finish", **({"params": params} if params else {}))
        finished = True

    return {
        "action": "publish-performance",
        "run_id": args.run_id,
        "mode": args.mode,
        "primary_series": curve_name,
        "rows": len(curve_rows),
        "summary_metrics": len(summary),
        "computed_summary": computed_summary,
        "normalizations": normalizations,
        "uploaded": uploaded,
        "validation": compact_validation_report(quality_report),
        "finished": finished,
    }


def parse_rows_file(path_value: str, label: str) -> list[dict[str, Any]]:
    path = Path(path_value)
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return [{key: parse_csv_scalar(value) for key, value in row.items()} for row in csv.DictReader(handle)]
        if suffix in {".jsonl", ".ndjson"}:
            rows = [parse_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            return rows
        if suffix in {".parquet", ".pq"}:
            try:
                import pandas as pd
            except ImportError as exc:
                raise CliError("VALIDATION_ERROR", f"pandas is required to read {label}: {path}", hint="install blackbox[data] or convert the file to CSV/JSON") from exc
            return pd.read_parquet(path).to_dict(orient="records")
        parsed = parse_structured_file(path_value, label)
    except OSError as exc:
        raise CliError("VALIDATION_ERROR", f"cannot read {label}: {path}") from exc
    if isinstance(parsed, dict) and isinstance(parsed.get("rows"), list):
        parsed = parsed["rows"]
    if not isinstance(parsed, list):
        raise CliError("VALIDATION_ERROR", f"{label} must contain a list of row objects")
    return parsed


def parse_csv_scalar(value: str | None) -> Any:
    if value is None or value == "":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def normalize_performance_rows(
    rows: list[dict[str, Any]],
    *,
    mode: str,
    x: str | None,
    value: str | None,
    label: str,
) -> tuple[list[dict[str, Any]], str, str, list[dict[str, Any]]]:
    if not rows or any(not isinstance(row, dict) for row in rows):
        report = validate_series_upload({"name": label, "data": rows, "x": x, "y": value, "mode": mode}, strict=True)
        enforce_upload_preflight(report)
    columns = list(dict.fromkeys(key for row in rows for key in row))
    actions: list[dict[str, Any]] = []
    x_key = infer_x_column(columns, x)
    if x is None:
        actions.append({"code": "INFER_X_COLUMN", "value": x_key})
    value_key = infer_value_column(rows, columns, x_key, mode, value)
    if value is None:
        actions.append({"code": "INFER_VALUE_COLUMN", "value": value_key})

    normalized: list[dict[str, Any]] = []
    invalid_rows: list[int] = []
    for index, row in enumerate(rows):
        number = finite_number(row.get(value_key))
        if number is None:
            invalid_rows.append(index + 1)
            continue
        normalized.append({**row, "series_values": number})
    if invalid_rows:
        raise CliError(
            "VALIDATION_ERROR",
            f"{label} column {value_key} contains missing or non-finite values",
            exit_code=4,
            details={"issues": [{"code": "SERIES_Y_NOT_NUMERIC", "field": value_key, "rows": invalid_rows[:20], "fix": "Provide a finite numeric value in every published row."}]},
        )
    if value_key != "series_values":
        actions.append({"code": "COPY_VALUE_COLUMN", "from": value_key, "to": "series_values"})
    return normalized, x_key, value_key, actions


def infer_x_column(columns: list[str], requested: str | None) -> str:
    if requested:
        if requested not in columns:
            raise CliError("VALIDATION_ERROR", f"x column {requested} is not present", exit_code=4, details={"issues": [{"code": "SERIES_X_COLUMN_NOT_FOUND", "field": "x", "candidates": columns}]})
        return requested
    aliases = {"date", "datetime", "trade_date", "end_date", "time", "timestamp"}
    candidates = [column for column in columns if str(column).lower() in aliases]
    if len(candidates) == 1:
        return candidates[0]
    raise CliError(
        "VALIDATION_ERROR",
        "cannot infer a unique x column",
        exit_code=4,
        hint="pass --x with the date/time column",
        details={"issues": [{"code": "SERIES_X_AMBIGUOUS", "field": "x", "candidates": candidates or columns}]},
    )


def infer_value_column(rows: list[dict[str, Any]], columns: list[str], x_key: str, mode: str, requested: str | None) -> str:
    if requested:
        if requested not in columns:
            raise CliError("VALIDATION_ERROR", f"value column {requested} is not present", exit_code=4, details={"issues": [{"code": "SERIES_Y_COLUMN_NOT_FOUND", "field": "value", "candidates": columns}]})
        return requested
    if "series_values" in columns:
        return "series_values"
    aliases = {
        "nav": ["nav", "net_value", "equity", "净值"],
        "return": ["return", "returns", "ret", "period_return", "收益率"],
        "pnl": ["pnl", "profit", "change", "盈亏"],
        "drawdown": ["drawdown", "dd", "回撤"],
    }.get(mode, [])
    alias_candidates = [column for column in columns if str(column).lower() in {alias.lower() for alias in aliases}]
    if len(alias_candidates) == 1:
        return alias_candidates[0]
    numeric_candidates = [column for column in columns if column != x_key and any(finite_number(row.get(column)) is not None for row in rows)]
    if len(numeric_candidates) == 1:
        return numeric_candidates[0]
    raise CliError(
        "VALIDATION_ERROR",
        "cannot infer a unique performance value column",
        exit_code=4,
        hint="pass --value or --drawdown-value explicitly",
        details={"issues": [{"code": "SERIES_VALUE_AMBIGUOUS", "field": "value", "candidates": alias_candidates or numeric_candidates or columns}]},
    )


def finite_number(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_summary_metrics(values: dict[str, Any], unit: str | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    percent_keys = [key for key in values if key in PERCENT_SUMMARY_KEYS]
    if percent_keys and unit is None:
        raise CliError(
            "VALIDATION_ERROR",
            "summary percentage unit is ambiguous",
            exit_code=4,
            hint="pass --summary-unit decimal or --summary-unit percentage-point",
            details={"issues": [{"code": "SUMMARY_UNIT_AMBIGUOUS", "field": "summary-unit", "keys": percent_keys, "choices": ["decimal", "percentage-point"]}]},
        )
    normalized = dict(values)
    actions: list[dict[str, Any]] = []
    for key in percent_keys:
        number = finite_number(values[key])
        if number is None:
            raise CliError("VALIDATION_ERROR", f"summary metric {key} must be numeric", exit_code=4, details={"issues": [{"code": "SUMMARY_METRIC_NOT_NUMERIC", "field": f"strategy.summary.{key}"}]})
        normalized[key] = number * 100.0 if unit == "decimal" else number
    if percent_keys and unit == "decimal":
        actions.append({"code": "CONVERT_SUMMARY_PERCENT_UNIT", "from": "decimal", "to": "percentage-point", "fields": percent_keys})
    return normalized, actions


def performance_contract(mode: str) -> tuple[str, str]:
    return {
        "nav": ("equity_curve", "strategy.equity"),
        "return": ("returns_series", "strategy.returns"),
        "pnl": ("pnl_series", "strategy.pnl"),
    }[mode]


def empty_validation_report() -> dict[str, Any]:
    return {"schema_version": 1, "severity": "ok", "error_count": 0, "warning_count": 0, "issues": []}


def compact_validation_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "severity": report.get("severity", "ok"),
        "error_count": int(report.get("error_count") or 0),
        "warning_count": int(report.get("warning_count") or 0),
        "issues": [compact_issue(issue) for issue in report.get("issues") or []],
    }


def compact_agent_error(payload: dict[str, Any]) -> dict[str, Any]:
    details = payload.get("details")
    issues = details.get("issues") if isinstance(details, dict) else None
    compact = {"code": payload.get("code"), "message": short_error_message(payload), "hint": payload.get("hint")}
    if isinstance(issues, list):
        compact["issues"] = [compact_issue(issue) for issue in issues if isinstance(issue, dict)]
    return compact_payload(compact)


def short_error_message(payload: dict[str, Any]) -> str:
    message = str(payload.get("message") or "request failed")
    return message.split(":", 1)[0] if message.startswith("upload preflight validation failed:") else message


def compact_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return compact_payload({key: issue.get(key) for key in ["code", "severity", "field", "fix", "rows", "keys", "choices", "candidates"]})


def database_status() -> Any:
    try:
        from blackbox_server.db import engine
        from blackbox_server.migrations import schema_status
    except Exception as exc:
        raise CliError("CLI_ERROR", f"database tooling is unavailable: {exc}", exit_code=10) from exc
    return schema_status(engine)


def database_migrate() -> Any:
    try:
        from blackbox_server.db import engine
        from blackbox_server.migrations import migrate_database
    except Exception as exc:
        raise CliError("CLI_ERROR", f"database tooling is unavailable: {exc}", exit_code=10) from exc
    return migrate_database(engine)


def request(args: argparse.Namespace, method: str, path: str, **kwargs: Any) -> Any:
    headers = kwargs.pop("headers", {})
    if args.token:
        headers = {**headers, "Authorization": f"Bearer {args.token}"}
    with httpx.Client(timeout=30.0) as client:
        response = client.request(method, f"{args.endpoint.rstrip('/')}{path}", headers=headers, **kwargs)
    try:
        payload = response.json()
    except Exception as exc:
        raise CliError("SERVER_ERROR", response.text, 10) from exc
    if not payload.get("ok"):
        error = payload.get("error") or {}
        code = error.get("code", "SERVER_ERROR")
        exit_code = {"VALIDATION_ERROR": 2, "NOT_FOUND": 3, "CONFLICT": 4, "STATE_ERROR": 4, "AUTH_ERROR": 5}.get(code, 10)
        raise CliError(code, error.get("message", "request failed"), exit_code, error.get("hint"), error.get("details"))
    return payload["data"]


def download_artifact(args: argparse.Namespace) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    url = f"{args.endpoint.rstrip('/')}/api/v1/artifacts/{args.artifact_id}/content"
    output_path = Path(args.output_path).expanduser().resolve()
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
    if response.status_code >= 400:
        try:
            payload = response.json()
            error = payload.get("error") or {}
            code = error.get("code", "SERVER_ERROR")
            message = error.get("message", response.text)
            hint = error.get("hint")
        except Exception:
            code = "SERVER_ERROR"
            message = response.text
            hint = None
        exit_code = {"VALIDATION_ERROR": 2, "NOT_FOUND": 3, "CONFLICT": 4, "STATE_ERROR": 4, "AUTH_ERROR": 5}.get(code, 10)
        raise CliError(code, message, exit_code, hint)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return {
        "artifact_id": args.artifact_id,
        "output_path": str(output_path),
        "size_bytes": len(response.content),
        "content_type": response.headers.get("content-type"),
        "source_url": str(response.url),
    }


def write_success(args: argparse.Namespace, data: Any) -> None:
    selected = apply_select(data, getattr(args, "select", None))
    if args.quiet:
        if selected is not None and not isinstance(selected, (dict, list)):
            print(selected)
        return
    if args.output == "table":
        print(format_table(selected))
        return
    payload = {"ok": True, "data": selected, "error": None}
    if args.output == "yaml":
        print(format_yaml(payload))
        return
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact or args.agent_output else 2))


def command_exit_code(args: argparse.Namespace, data: Any) -> int:
    if getattr(args, "group", None) == "run" and getattr(args, "action", None) == "validate" and isinstance(data, dict):
        if getattr(args, "no_fail", False):
            return 0
        if int(data.get("error_count") or 0) > 0:
            return 4
        if getattr(args, "fail_on_warning", False) and int(data.get("warning_count") or 0) > 0:
            return 4
    return 0


def upload_validation_strict(args: argparse.Namespace) -> bool:
    if getattr(args, "strict_contract", False):
        return True
    return os.getenv("BLACKBOX_AGENT_STRICT_UPLOAD", "0").lower() in {"1", "true", "yes"}


def enforce_upload_preflight(report: dict[str, Any], *, fail_on_warning: bool = False) -> None:
    if upload_report_failed(report, fail_on_warning=fail_on_warning):
        raise CliError(
            "VALIDATION_ERROR",
            format_upload_report_for_agent(report),
            exit_code=4,
            hint=report.get("hint") or "Fix the upload contract or pass --skip-upload-validation for an explicit manual override.",
            details=report,
        )


def apply_select(data: Any, select: str | None) -> Any:
    fields = split_csv(select or "")
    if not fields:
        return data
    if isinstance(data, list):
        return [select_fields(item, fields) for item in data]
    return select_fields(data, fields)


def select_fields(item: Any, fields: list[str]) -> Any:
    if not isinstance(item, dict):
        return item
    result: dict[str, Any] = {}
    for field in fields:
        value = get_path(item, field)
        if value is not None:
            result[field] = value
    return result


def get_path(item: dict[str, Any], path: str) -> Any:
    return get_path_parts(item, path.split("."))


def get_path_parts(current: Any, parts: list[str]) -> Any:
    if not parts:
        return current
    if not isinstance(current, dict):
        return None
    for end in range(len(parts), 0, -1):
        key = ".".join(parts[:end])
        if key in current:
            return get_path_parts(current[key], parts[end:])
    return None


def format_table(data: Any) -> str:
    rows = data if isinstance(data, list) else [data]
    if not rows or not all(isinstance(row, dict) for row in rows):
        return json.dumps(data, ensure_ascii=False)
    columns = list(dict.fromkeys(key for row in rows for key in row))
    string_rows = [{key: format_cell(row.get(key)) for key in columns} for row in rows]
    widths = {key: max(len(key), *(len(row[key]) for row in string_rows)) for key in columns}
    header = "  ".join(key.ljust(widths[key]) for key in columns)
    separator = "  ".join("-" * widths[key] for key in columns)
    body = ["  ".join(row[key].ljust(widths[key]) for key in columns) for row in string_rows]
    return "\n".join([header, separator, *body])


def format_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if value is None:
        return ""
    return str(value)


def format_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(format_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {format_yaml_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(format_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {format_yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{prefix}{format_yaml_scalar(value)}"


def format_yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise CliError("VALIDATION_ERROR", f"invalid JSON: {value}") from exc


def parse_structured_file(path_value: str, label: str) -> Any:
    path = Path(path_value)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError("VALIDATION_ERROR", f"cannot read {label}: {path}") from exc
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return parse_yaml(raw, label, str(path))
    return parse_json(raw)


def parse_yaml(value: str, label: str, source: str) -> Any:
    try:
        import yaml
    except ImportError as exc:
        raise CliError("VALIDATION_ERROR", f"cannot parse YAML {label}: PyYAML is not installed") from exc
    try:
        parsed = yaml.safe_load(value)
    except yaml.YAMLError as exc:
        raise CliError("VALIDATION_ERROR", f"invalid YAML in {label}: {source}") from exc
    return {} if parsed is None else parsed


def parse_json_object_arg(value: str, label: str) -> dict[str, Any]:
    parsed = parse_json(value)
    if not isinstance(parsed, dict):
        raise CliError("VALIDATION_ERROR", f"{label} must be a JSON object")
    return parsed


def build_result_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = parse_json_object_arg(args.result, "result") if getattr(args, "result", None) else {}
    view = parse_json_object_arg(args.result_view, "result view") if getattr(args, "result_view", None) else None
    payload.update(
        compact_payload(
            {
                "domain": getattr(args, "result_domain", None),
                "name": getattr(args, "result_name", None),
                "role": getattr(args, "result_role", None),
                "title": getattr(args, "result_title", None),
                "group": getattr(args, "result_group", None),
                "order": getattr(args, "result_order", None),
                "view": view,
            }
        )
    )
    return payload


def parse_structured_object_file(path_value: str, label: str) -> dict[str, Any]:
    parsed = parse_structured_file(path_value, label)
    if not isinstance(parsed, dict):
        raise CliError("VALIDATION_ERROR", f"{label} must be an object")
    return parsed


def dataset_payload(args: argparse.Namespace) -> dict[str, Any]:
    time_range = parse_structured_object_file(args.time_range_file, "time range file") if args.time_range_file else parse_json_object_arg(args.time_range, "time range")
    metadata = parse_structured_object_file(args.metadata_file, "metadata file") if args.metadata_file else parse_json_object_arg(args.metadata, "metadata")
    return compact_payload(
        {
            "dataset_name": args.dataset_name,
            "dataset_version": args.dataset_version,
            "fingerprint": args.fingerprint,
            "universe": args.universe,
            "benchmark": args.benchmark,
            "calendar": args.calendar,
            "fee_model": args.fee_model,
            "slippage_model": args.slippage_model,
            "time_range": time_range,
            "metadata": metadata,
        }
    )


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_csv_arg(value: str | None) -> str | list[str] | None:
    if not value:
        return None
    items = split_csv(value)
    if not items:
        return None
    return items[0] if len(items) == 1 else items


def list_or_csv(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return split_csv(str(value))


def parse_id_list(value: Any, file_path: str | None, field_name: str) -> list[str]:
    raw = Path(file_path).read_text(encoding="utf-8") if file_path else value
    if not raw:
        raise CliError("VALIDATION_ERROR", f"{field_name} is required", hint=f"use --{field_name.replace('_', '-')} or --{field_name.replace('_', '-')}-file")
    ids = parse_id_values(raw)
    if not ids:
        raise CliError("VALIDATION_ERROR", f"{field_name} is empty")
    return ids


def parse_id_values(value: Any) -> list[str]:
    if isinstance(value, list):
        ids: list[str] = []
        for item in value:
            ids.extend(parse_id_values(item))
        return ids
    parsed = parse_scalar(str(value).strip())
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return split_csv(str(parsed))


def parse_compare_groups(args: argparse.Namespace) -> list[dict[str, Any]]:
    raw = Path(args.groups_file).read_text(encoding="utf-8") if args.groups_file else args.groups
    if raw:
        parsed = parse_json(raw)
        if not isinstance(parsed, list):
            raise CliError("VALIDATION_ERROR", "compare groups must be a JSON list")
        groups: list[dict[str, Any]] = []
        for index, group in enumerate(parsed):
            if not isinstance(group, dict):
                raise CliError("VALIDATION_ERROR", f"compare group at index {index} must be an object")
            run_ids = list_or_csv(group.get("run_ids"))
            if not run_ids:
                raise CliError("VALIDATION_ERROR", f"compare group at index {index} has no run_ids")
            groups.append(
                {
                    "name": group.get("name") or f"group_{index + 1}",
                    "run_ids": run_ids,
                    "metrics": list_or_csv(group.get("metrics")) or split_csv(args.metrics),
                    "series": list_or_csv(group.get("series")) or split_csv(args.series),
                    "with_config_diff": bool(group.get("with_config_diff", args.with_config_diff)),
                }
            )
        return groups
    return [{"name": "default", "run_ids": parse_id_list(args.run_ids, args.run_ids_file, "run_ids")}]


def note_payload(args: argparse.Namespace) -> dict[str, Any]:
    structured = parse_json(Path(args.structured_file).read_text(encoding="utf-8")) if getattr(args, "structured_file", None) else parse_json(args.structured)
    if not isinstance(structured, dict):
        raise CliError("VALIDATION_ERROR", "note structured payload must be a JSON object")
    payload = {
        "kind": args.kind,
        "summary": args.summary,
        "content": args.content,
        "structured": structured,
        "author_type": args.author_type,
    }
    if getattr(args, "client_event_id", None):
        payload["client_event_id"] = args.client_event_id
    return payload


def batch_request(args: argparse.Namespace, target: dict[str, Any], method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "target": target, "data": request(args, method, path, **kwargs), "error": None}
    except CliError as exc:
        return {"ok": False, "target": target, "data": None, "error": exc.payload}


def batch_summary(action: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    success_count = sum(1 for item in items if item["ok"])
    return {
        "action": action,
        "success_count": success_count,
        "failure_count": len(items) - success_count,
        "items": items,
    }


def parse_metric_filter(value: str) -> dict[str, Any]:
    for op in (">=", "<=", "!=", "==", ">", "<", "="):
        if op in value:
            metric, raw_expected = value.split(op, 1)
            return {"metric": metric.strip(), "op": op, "value": parse_scalar(raw_expected.strip())}
    raise CliError("VALIDATION_ERROR", f"invalid metric filter: {value}", hint="use metric>=value")


def parse_search_where(where: str | None) -> dict[str, Any]:
    if not where:
        return {}
    filters: dict[str, Any] = {"tags": [], "metrics": [], "config": {}, "context": {}}
    for clause in split_where_clauses(where):
        apply_search_where_clause(filters, clause)
    return filters


def split_where_clauses(where: str) -> list[str]:
    clauses = [part.strip() for part in re.split(r"\s+and\s+", where, flags=re.IGNORECASE) if part.strip()]
    if not clauses:
        raise CliError("VALIDATION_ERROR", "where expression is empty")
    return clauses


def apply_search_where_clause(filters: dict[str, Any], clause: str) -> None:
    artifact_match = re.fullmatch(r"has_artifact\(([^)]+)\)", clause.strip(), flags=re.IGNORECASE)
    if artifact_match:
        filters["has_artifact"] = parse_scalar(artifact_match.group(1).strip().strip("\"'"))
        return

    contains = parse_contains_clause(clause)
    if contains:
        field, value = contains
        if field not in {"tag", "tags"}:
            raise CliError("VALIDATION_ERROR", f"unsupported contains field in where clause: {field}", hint='use tags contains "baseline"')
        filters["tags"].append(str(value))
        return

    field, op, value = parse_binary_where_clause(clause)
    if field.startswith("metrics."):
        filters["metrics"].append({"metric": field.removeprefix("metrics."), "op": op, "value": value})
        return
    if field.startswith("config."):
        if op not in {"=", "=="}:
            raise CliError("VALIDATION_ERROR", f"unsupported config operator in where clause: {op}", hint="use config.key == value")
        filters["config"][field.removeprefix("config.")] = value
        return
    if field.startswith("context."):
        if op not in {"=", "=="}:
            raise CliError("VALIDATION_ERROR", f"unsupported context operator in where clause: {op}", hint="use context.key == value")
        filters["context"][field.removeprefix("context.")] = value
        return
    simple_fields = {
        "project": "project_key",
        "project_key": "project_key",
        "research": "research_key",
        "research_key": "research_key",
        "branch": "branch_key",
        "branch_key": "branch_key",
        "branch_id": "branch_id",
        "status": "status",
        "name": "name",
        "author_type": "author_type",
    }
    if field in simple_fields and op in {"=", "=="}:
        filters[simple_fields[field]] = value
        return
    raise CliError("VALIDATION_ERROR", f"unsupported where clause: {clause}")


def parse_contains_clause(clause: str) -> tuple[str, Any] | None:
    try:
        parts = shlex.split(clause)
    except ValueError as exc:
        raise CliError("VALIDATION_ERROR", f"invalid where clause: {clause}") from exc
    if len(parts) >= 3 and parts[1].lower() == "contains":
        return parts[0], parse_scalar(" ".join(parts[2:]))
    return None


def parse_binary_where_clause(clause: str) -> tuple[str, str, Any]:
    for op in (">=", "<=", "!=", "==", ">", "<", "="):
        pattern = rf"^\s*(?P<field>[A-Za-z_][\w.]*?)\s*{re.escape(op)}\s*(?P<value>.+?)\s*$"
        match = re.match(pattern, clause)
        if match:
            raw_value = match.group("value").strip()
            return match.group("field").strip(), op, parse_scalar(raw_value.strip("\"'"))
    raise CliError("VALIDATION_ERROR", f"invalid where clause: {clause}", hint='use metrics.strategy.summary.sharpe > 1.2 or tags contains "baseline"')


def parse_key_value_filters(values: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise CliError("VALIDATION_ERROR", f"invalid key/value filter: {value}", hint="use key=value")
        key, raw_expected = value.split("=", 1)
        result[key.strip()] = parse_scalar(raw_expected.strip())
    return result


def compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def parse_scalar(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


if __name__ == "__main__":
    raise SystemExit(main())
