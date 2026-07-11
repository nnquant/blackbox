# Blackbox Agent Bootstrap

This file is for coding agents that need to install and operate Blackbox without reading the whole repository first.

Canonical raw URL:

```text
https://raw.githubusercontent.com/nnquant/blackbox/main/FOR-AGENTS.md
```

Skill raw URLs:

```text
https://raw.githubusercontent.com/nnquant/blackbox/main/skills/blackbox-agent-workflow/SKILL.md
https://raw.githubusercontent.com/nnquant/blackbox/main/skills/blackbox-agent-workflow/references/agent-workflow.md
```

## Clone

```powershell
git clone https://github.com/nnquant/blackbox.git
cd blackbox
```

## Install Python Package, CLI, And SDK

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev,data,s3,postgres]"
```

Verify:

```powershell
bbox --help
python -c "import blackbox as bb; print(bb.__name__)"
```

## Start The API Server

```powershell
$env:PYTHONPATH = "packages/common;packages/sdk;packages/cli;apps/server"
$env:BLACKBOX_DATA_DIR = "$HOME\.blackbox"
python -m uvicorn blackbox_server.main:app --host 127.0.0.1 --port 8010
```

The API and built WebUI are served from:

```text
http://127.0.0.1:8010
```

Check status:

```powershell
curl http://127.0.0.1:8010/healthz
bbox --endpoint http://127.0.0.1:8010 db status
```

## Start The Full Docker Stack

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Use:

```text
http://127.0.0.1:8000
```

## Install The Codex Skill

From a cloned repository:

```powershell
$skillRoot = Join-Path $env:USERPROFILE ".codex\skills"
New-Item -ItemType Directory -Force $skillRoot | Out-Null
Copy-Item -Recurse -Force .\skills\blackbox-agent-workflow (Join-Path $skillRoot "blackbox-agent-workflow")
```

Direct raw install:

```powershell
$skillRoot = Join-Path $env:USERPROFILE ".codex\skills\blackbox-agent-workflow"
New-Item -ItemType Directory -Force "$skillRoot\references" | Out-Null
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/nnquant/blackbox/main/skills/blackbox-agent-workflow/SKILL.md" -OutFile "$skillRoot\SKILL.md"
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/nnquant/blackbox/main/skills/blackbox-agent-workflow/references/agent-workflow.md" -OutFile "$skillRoot\references\agent-workflow.md"
```

After installation, agents should use the `blackbox-agent-workflow` skill for Blackbox CLI, SDK, offline sync, compare, note, lineage, and WebUI verification work.

## Minimal Online Workflow

Set defaults:

```powershell
$env:BLACKBOX_ENDPOINT = "http://127.0.0.1:8010"
```

Create project, research, branch, and a run:

```powershell
bbox project create --key alpha-lab --title "Alpha Lab" --json
bbox research create --project alpha-lab --key csi500-reversal --title "CSI500 Reversal" --json
bbox branch create --research csi500-reversal --key baseline --title "Baseline" --created-by-type agent --created-by-id codex --json
bbox run start --project alpha-lab --research csi500-reversal --branch baseline --name run-001 --created-by-type agent --created-by-id codex --idempotency-key codex-demo:run:start --json
```

Publish performance data and finish:

```powershell
bbox run publish-performance --run-id <run_id> --curve-file .\equity.csv --mode nav --summary '{"sharpe":1.2,"max_drawdown":-0.08}' --summary-unit decimal --idempotency-prefix codex-demo:performance --finish --agent-output
bbox note add --run-id <run_id> --kind decision --summary "Keep for review" --author-type agent --client-event-id codex-demo:note:decision --json
```

Search and compare:

```powershell
bbox search runs --where 'metrics.strategy.summary.sharpe > 1 and tags contains "baseline"' --select id,name,status,branch_key,summary_json --json
bbox compare runs --run-ids <baseline_run_id> <candidate_run_id> --metrics strategy.summary.sharpe,strategy.summary.max_drawdown --json
```

## Offline Workflow

Use this when the server is not reachable:

```powershell
$env:BLACKBOX_OFFLINE = "1"
$env:BLACKBOX_SPOOL_DIR = "$HOME\.blackbox"
```

Python:

```python
import blackbox as bb

bb.init(
    project="alpha-lab",
    research="csi500-reversal",
    branch="offline-agent",
    name="offline-run-001",
    tags=["agent", "offline"],
    created_by_type="agent",
    created_by_id="codex",
    offline=True,
)
bb.log("strategy.summary", {"sharpe": 1.1, "max_drawdown": 0.1}, client_event_id="offline-demo:metric:summary")
bb.finish()
```

Sync later:

```powershell
bbox sync --spool-dir "$HOME\.blackbox" --endpoint http://127.0.0.1:8010 --json
```

## Agent Rules

- Prefer JSON output and use `--select` to reduce context.
- Prefer `bbox run publish-performance --agent-output` over manually constructing performance `log-metric` and `log-series` contracts.
- Always declare performance `--mode` and summary `--summary-unit`; Blackbox does not guess financial units.
- Preserve idempotency keys and `client_event_id` values across retries.
- Use `created_by_type=agent` and a stable `created_by_id`.
- Retry transient network/storage failures with the same idempotency key.
- Do not retry validation or state errors unchanged.
- Verify important writes in WebUI: dashboard, search, run detail, lineage, compare, and sweep pages.
