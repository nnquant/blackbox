from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlencode, urlparse
from urllib.request import url2pathname

from blackbox_common.errors import ApiError, ErrorCode
from blackbox_common.ids import new_id

from .settings import Settings


class StoredObject(NamedTuple):
    storage_uri: str
    path: Path | None
    filename: str
    mime_type: str | None
    size_bytes: int
    sha256: str


class UploadTarget(NamedTuple):
    artifact_id: str
    method: str
    upload_path: str | None
    upload_url: str | None
    storage_uri: str | None
    headers: dict[str, str]
    metadata: dict[str, str]


class ArtifactContentTarget(NamedTuple):
    path: Path | None
    redirect_url: str | None


class LocalFileStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, *, run_id: str, artifact_id: str | None, filename: str, content: bytes) -> StoredObject:
        artifact_id = artifact_id or new_id("artifact")
        safe_filename = Path(filename).name or "artifact.bin"
        target_dir = self.root / "run" / run_id / "artifacts" / artifact_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / safe_filename
        target.write_bytes(content)
        sha256 = hashlib.sha256(content).hexdigest()
        mime_type = mimetypes.guess_type(safe_filename)[0]
        return StoredObject(
            storage_uri=target.as_uri(),
            path=target,
            filename=safe_filename,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=sha256,
        )

    def init_upload(self, *, run_id: str, artifact_id: str, name: str, kind: str, filename: str, metadata: dict[str, str]) -> UploadTarget:
        del metadata
        query = urlencode({"artifact_id": artifact_id, "name": name, "kind": kind, "filename": filename})
        return UploadTarget(
            artifact_id=artifact_id,
            method="POST",
            upload_path=f"/api/v1/runs/{run_id}/artifacts/upload?{query}",
            upload_url=None,
            storage_uri=None,
            headers={},
            metadata={},
        )

    def content_target(self, storage_uri: str) -> ArtifactContentTarget:
        path = local_path_from_file_uri(storage_uri)
        root = self.root.resolve()
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ApiError(ErrorCode.validation_error, "file artifact is outside the configured artifact root") from exc
        if not resolved.is_file():
            raise ApiError(ErrorCode.not_found, "artifact content file not found")
        return ArtifactContentTarget(path=resolved, redirect_url=None)


class S3ObjectStorage:
    def __init__(self, settings: Settings):
        if not settings.s3_bucket:
            raise ApiError(ErrorCode.storage_error, "BLACKBOX_S3_BUCKET is required when BLACKBOX_ARTIFACT_STORAGE=s3")
        try:
            import boto3
        except ImportError as exc:
            raise ApiError(
                ErrorCode.storage_error,
                "boto3 is required for BLACKBOX_ARTIFACT_STORAGE=s3",
                "install blackbox[s3] or add boto3 to the environment",
            ) from exc

        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix.strip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def ensure_ready(self) -> None:
        return None

    def put_bytes(self, *, run_id: str, artifact_id: str | None, filename: str, content: bytes) -> StoredObject:
        artifact_id = artifact_id or new_id("artifact")
        safe_filename = Path(filename).name or "artifact.bin"
        key = self.object_key(run_id, artifact_id, safe_filename)
        mime_type = mimetypes.guess_type(safe_filename)[0]
        extra: dict[str, str] = {}
        if mime_type:
            extra["ContentType"] = mime_type
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, **extra)
        return StoredObject(
            storage_uri=f"s3://{self.bucket}/{key}",
            path=None,
            filename=safe_filename,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def init_upload(self, *, run_id: str, artifact_id: str, name: str, kind: str, filename: str, metadata: dict[str, str]) -> UploadTarget:
        del name, kind
        safe_filename = Path(filename).name or "artifact.bin"
        key = self.object_key(run_id, artifact_id, safe_filename)
        mime_type = mimetypes.guess_type(safe_filename)[0]
        params: dict[str, str] = {"Bucket": self.bucket, "Key": key}
        headers: dict[str, str] = {}
        if mime_type:
            params["ContentType"] = mime_type
            headers["Content-Type"] = mime_type
        upload_url = self.client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=3600,
            HttpMethod="PUT",
        )
        return UploadTarget(
            artifact_id=artifact_id,
            method="PUT",
            upload_path=None,
            upload_url=upload_url,
            storage_uri=f"s3://{self.bucket}/{key}",
            headers=headers,
            metadata={key: str(value) for key, value in metadata.items()},
        )

    def content_target(self, storage_uri: str, mime_type: str | None = None) -> ArtifactContentTarget:
        bucket, key = parse_s3_uri(storage_uri)
        params: dict[str, str] = {"Bucket": bucket, "Key": key}
        if mime_type:
            params["ResponseContentType"] = mime_type
        download_url = self.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=3600,
            HttpMethod="GET",
        )
        return ArtifactContentTarget(path=None, redirect_url=download_url)

    def object_key(self, run_id: str, artifact_id: str, filename: str) -> str:
        parts = [part for part in [self.prefix, "run", run_id, "artifacts", artifact_id, filename] if part]
        return "/".join(parts)


def get_storage(settings: Settings) -> LocalFileStorage | S3ObjectStorage:
    if settings.artifact_storage == "local":
        return LocalFileStorage(settings.artifact_root)
    if settings.artifact_storage in {"s3", "minio"}:
        return S3ObjectStorage(settings)
    raise ApiError(
        ErrorCode.storage_error,
        f"unsupported artifact storage backend: {settings.artifact_storage}",
        "use BLACKBOX_ARTIFACT_STORAGE=local or s3",
    )


def get_artifact_content_target(settings: Settings, storage_uri: str, mime_type: str | None = None) -> ArtifactContentTarget:
    parsed = urlparse(storage_uri)
    if parsed.scheme == "file":
        return LocalFileStorage(settings.artifact_root).content_target(storage_uri)
    if parsed.scheme == "s3":
        return S3ObjectStorage(settings).content_target(storage_uri, mime_type)
    if parsed.scheme in {"http", "https"}:
        return ArtifactContentTarget(path=None, redirect_url=storage_uri)
    raise ApiError(ErrorCode.validation_error, f"unsupported artifact storage URI: {storage_uri}")


def local_path_from_file_uri(storage_uri: str) -> Path:
    parsed = urlparse(storage_uri)
    if parsed.scheme != "file":
        raise ApiError(ErrorCode.validation_error, f"expected file artifact URI, got: {storage_uri}")
    if parsed.netloc and parsed.netloc not in {"", "localhost"}:
        raise ApiError(ErrorCode.validation_error, f"unsupported file artifact host: {parsed.netloc}")
    return Path(url2pathname(parsed.path))


def parse_s3_uri(storage_uri: str) -> tuple[str, str]:
    parsed = urlparse(storage_uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
        raise ApiError(ErrorCode.validation_error, f"invalid s3 artifact URI: {storage_uri}")
    return parsed.netloc, parsed.path.lstrip("/")
