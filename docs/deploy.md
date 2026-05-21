# Deployment

Blackbox can run as a single FastAPI service that serves both the API and the built WebUI.

## Local Source Run

```powershell
$env:PYTHONPATH = "packages/common;packages/sdk;packages/cli;apps/server"
$env:BLACKBOX_DATA_DIR = "$HOME\.blackbox"
python -m uvicorn blackbox_server.main:app --host 127.0.0.1 --port 8010
```

Then open `http://127.0.0.1:8010`.

## Docker Compose

Copy `.env.example` to `.env` and adjust secrets when enabling auth.

```powershell
docker compose up --build
```

Services:

- `blackbox`: FastAPI API + WebUI on `http://127.0.0.1:8000`
- `postgres`: metadata database
- `minio`: S3-compatible artifact storage on `http://127.0.0.1:9000`
- MinIO console: `http://127.0.0.1:9001`

The compose stack uses:

```text
BLACKBOX_DATABASE_URL=postgresql+psycopg://blackbox:blackbox@postgres:5432/blackbox
BLACKBOX_ARTIFACT_STORAGE=s3
BLACKBOX_S3_ENDPOINT_URL=http://minio:9000
```

On startup the server runs the built-in schema migration and creates missing tables/columns.

## Health And Migration Checks

```powershell
curl http://127.0.0.1:8000/healthz
bbox --endpoint http://127.0.0.1:8000 db status
bbox --endpoint http://127.0.0.1:8000 project list
```

`bbox db status` and `bbox db migrate` operate on the local process environment. Inside Docker, run:

```powershell
docker compose exec blackbox bbox db status
```

## Auth

Set:

```powershell
BLACKBOX_AUTH_ENABLED=1
BLACKBOX_API_TOKEN=<strong-token>
```

CLI and SDK clients should pass the token through `--token`, `BLACKBOX_TOKEN`, or `BLACKBOX_API_TOKEN`.
The WebUI no longer exposes a token editor in the navigation bar. Configure browser-served deployments with `VITE_BLACKBOX_TOKEN` at build time when a static token is appropriate, or keep auth disabled for trusted local-only deployments.

The WebUI Dashboard includes a `System Status` panel backed by `/healthz`, `/api/v1/auth/status`, `/api/v1/system/db-status`, and `/api/v1/system/runtime-status`, so operators can verify API health, auth configuration, schema migration status, artifact storage mode, and worker backend without editing credentials in the UI.
