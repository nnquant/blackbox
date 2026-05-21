# Artifact Storage

Blackbox defaults to local artifact storage under `~/.blackbox/artifacts`.

## Local

```powershell
$env:BLACKBOX_ARTIFACT_STORAGE = "local"
$env:BLACKBOX_ARTIFACT_ROOT = "D:\blackbox-artifacts"
```

Stored artifact URIs are `file:///...`.

## S3 / MinIO

Install the optional S3 dependency:

```powershell
pip install -e ".[s3]"
```

Configure a S3-compatible endpoint:

```powershell
$env:BLACKBOX_ARTIFACT_STORAGE = "s3"
$env:BLACKBOX_S3_BUCKET = "blackbox"
$env:BLACKBOX_S3_ENDPOINT_URL = "http://127.0.0.1:9000"
$env:BLACKBOX_S3_ACCESS_KEY_ID = "minioadmin"
$env:BLACKBOX_S3_SECRET_ACCESS_KEY = "minioadmin"
$env:BLACKBOX_S3_PREFIX = "blackbox"
```

Direct server uploads (`/artifacts/upload`) write objects with `put_object`.
`/artifacts/init-upload` returns a presigned `PUT` URL when S3 storage is active; callers should upload to that URL and then call `/artifacts/complete-upload` with the returned `storage_uri`.
