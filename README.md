# Blackbox

Blackbox is an experiment graph system for quantitative research. It provides a FastAPI server, a React WebUI, a `bbox` CLI, a Python SDK, artifact storage, lineage, compare views, sweeps, and an agent-oriented workflow for writing research results in a reproducible format.

## Components

- Server: `apps/server/blackbox_server`
- CLI: `packages/cli`, entrypoint `bbox`
- SDK: `packages/sdk`, import name `blackbox`
- Shared schemas: `packages/common`
- WebUI: `webui`
- Codex skill: `skills/blackbox-agent-workflow`
- Agent guide: `FOR-AGENTS.md`

## Requirements

- Python 3.11 or newer
- Node.js 22 or newer, for building the WebUI from source
- Docker and Docker Compose, optional but recommended for the full stack

## Install CLI And SDK

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev,data,s3,postgres]"
```

Verify the CLI:

```powershell
bbox --help
python -c "import blackbox as bb; print(bb.__name__)"
```

The editable install exposes both:

- CLI command: `bbox`
- SDK module: `blackbox`

## Start The Server

### Local Source Run

```powershell
$env:PYTHONPATH = "packages/common;packages/sdk;packages/cli;apps/server"
$env:BLACKBOX_DATA_DIR = "$HOME\.blackbox"
python -m uvicorn blackbox_server.main:app --host 127.0.0.1 --port 8010
```

Open `http://127.0.0.1:8010`.

Health checks:

```powershell
curl http://127.0.0.1:8010/healthz
bbox --endpoint http://127.0.0.1:8010 db status
```

### WebUI Development Server

Run the API separately, then start Vite:

```powershell
cd webui
npm ci
npm run dev
```

Open the Vite URL, usually `http://127.0.0.1:5173`.

### Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open:

- Blackbox: `http://127.0.0.1:8000`
- MinIO API: `http://127.0.0.1:9000`
- MinIO console: `http://127.0.0.1:9001`

Inside Docker:

```powershell
docker compose exec blackbox bbox db status
docker compose exec blackbox bbox project list
```

## CLI Quick Start

```powershell
bbox --endpoint http://127.0.0.1:8010 project create --key alpha-lab --title "Alpha Lab"
bbox --endpoint http://127.0.0.1:8010 research create --project alpha-lab --key csi500-reversal --title "CSI500 Reversal"
bbox --endpoint http://127.0.0.1:8010 branch create --research csi500-reversal --key baseline --title "Baseline"
bbox --endpoint http://127.0.0.1:8010 run start --project alpha-lab --research csi500-reversal --branch baseline --name run-001 --json
```

Use `BLACKBOX_ENDPOINT`, `BLACKBOX_TOKEN`, or `BLACKBOX_API_TOKEN` to avoid repeating endpoint and token flags.

## SDK Quick Start

```python
import blackbox as bb

run = bb.init(
    project="alpha-lab",
    research="csi500-reversal",
    branch="baseline",
    name="run-001",
    endpoint="http://127.0.0.1:8010",
    tags=["baseline"],
)
bb.log("strategy.summary", {"sharpe": 1.2, "max_drawdown": 0.08})
bb.finish()
```

For offline agent runs:

```powershell
$env:BLACKBOX_OFFLINE = "1"
$env:BLACKBOX_SPOOL_DIR = "$HOME\.blackbox"
```

Sync later:

```powershell
bbox sync --spool-dir "$HOME\.blackbox" --endpoint http://127.0.0.1:8010 --json
```

## Install The Codex Skill

This repository includes a Codex skill for agents that operate Blackbox through `bbox`, the SDK, offline spool sync, and WebUI verification.

Local install from a cloned repository:

```powershell
$skillRoot = Join-Path $env:USERPROFILE ".codex\skills"
New-Item -ItemType Directory -Force $skillRoot | Out-Null
Copy-Item -Recurse -Force .\skills\blackbox-agent-workflow (Join-Path $skillRoot "blackbox-agent-workflow")
```

Install directly from GitHub raw content:

```powershell
$skillRoot = Join-Path $env:USERPROFILE ".codex\skills\blackbox-agent-workflow"
New-Item -ItemType Directory -Force "$skillRoot\references" | Out-Null
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/nnquant/blackbox/main/skills/blackbox-agent-workflow/SKILL.md" -OutFile "$skillRoot\SKILL.md"
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/nnquant/blackbox/main/skills/blackbox-agent-workflow/references/agent-workflow.md" -OutFile "$skillRoot\references\agent-workflow.md"
```

Agent bootstrap document:

- GitHub: `https://github.com/nnquant/blackbox/blob/main/FOR-AGENTS.md`
- Raw: `https://raw.githubusercontent.com/nnquant/blackbox/main/FOR-AGENTS.md`

## Agent Documentation

Agents should read `FOR-AGENTS.md` first. It contains the exact clone, install, server start, CLI/SDK verification, skill install, and workflow commands.

The longer operational reference is in `docs/agent-workflow.md`, with the skill copy at `skills/blackbox-agent-workflow/references/agent-workflow.md`.

## Development Checks

```powershell
pytest
cd webui
npm ci
npm run build
```

## More Docs

- Deployment: `docs/deploy.md`
- Artifact storage: `docs/storage.md`
- Agent workflow: `docs/agent-workflow.md`
- Product and design notes: `docs/designs`
