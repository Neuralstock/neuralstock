"""Optional Cloudflare R2 synchronization for verified static releases.

The module deliberately imports boto3 only in :func:`r2_client`, so using the
local registry and release tooling does not require the optional R2 dependency.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from neuralstock.canonical import read_json, sha256_file
from neuralstock.release import (
    canonical_contract_artifacts,
    complete_artifact_descriptors,
    verify_release,
)
from neuralstock.storage import object_key, snapshot_key, version_manifest_key

IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
ALIAS_CACHE_CONTROL = "public, max-age=60, must-revalidate"
SHA256_METADATA_KEY = "neuralstock-sha256"
ALIAS_KEYS = ("registry.json", "snapshots/latest.json")


class R2SyncError(RuntimeError):
    """Base error raised by the R2 synchronization adapter."""


class R2ImmutableConflict(R2SyncError):
    """Raised when an immutable R2 key exists with different content."""


@dataclass(frozen=True)
class R2UploadItem:
    source_path: Path
    release_key: str
    key: str
    sha256: str
    size_bytes: int
    content_type: str
    immutable: bool
    verify_existing_bytes: bool = False

    @property
    def cache_control(self) -> str:
        return IMMUTABLE_CACHE_CONTROL if self.immutable else ALIAS_CACHE_CONTROL


@dataclass(frozen=True)
class R2UploadPlan:
    release_root: Path
    revision: str
    prefix: str
    items: tuple[R2UploadItem, ...]


@dataclass(frozen=True)
class R2SyncResult:
    uploaded: tuple[str, ...]
    already_present: tuple[str, ...]
    aliases_updated: tuple[str, ...]


def _safe_prefix(prefix: str) -> str:
    if not isinstance(prefix, str):
        raise TypeError("R2 prefix must be a string")
    if prefix:
        raise ValueError(
            "R2 prefixes are not supported by the v0.2 root-relative URI contract; "
            "use a dedicated bucket or custom domain"
        )
    return ""


def _remote_key(prefix: str, release_key: str) -> str:
    return f"{prefix}/{release_key}" if prefix else release_key


def _release_path(root: Path, key: str) -> Path:
    if key.startswith("/") or "\\" in key:
        raise ValueError(f"unsafe release key: {key!r}")
    relative = Path(key)
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"unsafe release key: {key!r}")
    candidate = root.joinpath(*relative.parts).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"release key escapes release root: {key!r}")
    if not candidate.is_file():
        raise FileNotFoundError(f"release file does not exist: {candidate}")
    return candidate


def _upload_item(
    *,
    root: Path,
    release_key: str,
    prefix: str,
    content_type: str,
    immutable: bool,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
    verify_existing_bytes: bool = False,
) -> R2UploadItem:
    path = _release_path(root, release_key)
    size_bytes = path.stat().st_size
    digest = sha256_file(path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(
            f"release digest mismatch for {release_key}: expected {expected_sha256}, got {digest}"
        )
    if expected_size is not None and size_bytes != expected_size:
        raise ValueError(
            f"release size mismatch for {release_key}: expected {expected_size}, got {size_bytes}"
        )
    return R2UploadItem(
        source_path=path,
        release_key=release_key,
        key=_remote_key(prefix, release_key),
        sha256=digest,
        size_bytes=size_bytes,
        content_type=content_type,
        immutable=immutable,
        verify_existing_bytes=verify_existing_bytes,
    )


def _add_object(
    objects: dict[str, R2UploadItem],
    *,
    root: Path,
    prefix: str,
    digest: str,
    size_bytes: int,
    content_type: str,
) -> None:
    key = object_key(digest)
    item = _upload_item(
        root=root,
        release_key=key,
        prefix=prefix,
        content_type=content_type,
        immutable=True,
        expected_sha256=digest,
        expected_size=size_bytes,
    )
    existing = objects.get(key)
    if existing is not None:
        if existing.sha256 != item.sha256 or existing.size_bytes != item.size_bytes:
            raise ValueError(f"conflicting descriptors for content-addressed object: {key}")
        if existing.content_type != item.content_type:
            raise ValueError(
                f"conflicting media types for content-addressed object {key}: "
                f"{existing.content_type!r} and {item.content_type!r}"
            )
        return
    objects[key] = item


def build_upload_plan(
    release_root: str | Path,
    *,
    prefix: str = "",
) -> R2UploadPlan:
    """Build a deterministic R2 upload plan from the verified current release graph."""

    root = Path(release_root).resolve()
    normalized_prefix = _safe_prefix(prefix)
    verification = verify_release(root)
    latest_path = _release_path(root, "snapshots/latest.json")
    registry_path = _release_path(root, "registry.json")
    registry = read_json(latest_path)
    if registry["revision"] != verification.revision:
        raise ValueError("verified release revision changed while building the R2 upload plan")

    immutable_snapshot_key = snapshot_key(verification.revision)
    immutable_snapshot_path = _release_path(root, immutable_snapshot_key)
    latest_bytes = latest_path.read_bytes()
    if registry_path.read_bytes() != latest_bytes:
        raise ValueError("registry.json does not match snapshots/latest.json")
    if immutable_snapshot_path.read_bytes() != latest_bytes:
        raise ValueError("immutable revision snapshot does not match snapshots/latest.json")

    contracts = tuple(
        _upload_item(
            root=root,
            release_key=artifact.release_key,
            prefix=normalized_prefix,
            content_type=artifact.content_type,
            immutable=True,
            expected_sha256=sha256_file(artifact.source_path),
            expected_size=artifact.source_path.stat().st_size,
            verify_existing_bytes=True,
        )
        for artifact in canonical_contract_artifacts()
    )

    objects: dict[str, R2UploadItem] = {}
    manifests: dict[str, R2UploadItem] = {}
    for entry in sorted(
        registry["entries"],
        key=lambda value: (value["asset"]["id"], value["asset"]["version"]),
    ):
        asset_id = entry["asset"]["id"]
        version = entry["asset"]["version"]
        manifest_descriptor = entry["manifest"]
        manifest_key = version_manifest_key(asset_id, version)
        expected_uri = f"/{manifest_key}"
        if manifest_descriptor["uri"] != expected_uri:
            raise ValueError(f"manifest URI for {asset_id}@{version} must be {expected_uri!r}")
        manifest_item = _upload_item(
            root=root,
            release_key=manifest_key,
            prefix=normalized_prefix,
            content_type="application/json",
            immutable=True,
            expected_sha256=manifest_descriptor["sha256"],
            expected_size=manifest_descriptor["bytes"],
        )
        manifests[manifest_key] = manifest_item
        _add_object(
            objects,
            root=root,
            prefix=normalized_prefix,
            digest=manifest_item.sha256,
            size_bytes=manifest_item.size_bytes,
            content_type="application/json",
        )

        manifest = read_json(manifest_item.source_path)
        for descriptor in complete_artifact_descriptors(root, manifest):
            _add_object(
                objects,
                root=root,
                prefix=normalized_prefix,
                digest=descriptor["sha256"],
                size_bytes=descriptor["bytes"],
                content_type=descriptor["media_type"],
            )

    snapshot_digest = sha256_file(immutable_snapshot_path)
    _add_object(
        objects,
        root=root,
        prefix=normalized_prefix,
        digest=snapshot_digest,
        size_bytes=immutable_snapshot_path.stat().st_size,
        content_type="application/json",
    )
    immutable_snapshot = _upload_item(
        root=root,
        release_key=immutable_snapshot_key,
        prefix=normalized_prefix,
        content_type="application/json",
        immutable=True,
        expected_sha256=snapshot_digest,
    )
    aliases = tuple(
        _upload_item(
            root=root,
            release_key=key,
            prefix=normalized_prefix,
            content_type="application/json",
            immutable=False,
            expected_sha256=snapshot_digest,
        )
        for key in ALIAS_KEYS
    )
    items = (
        *contracts,
        *(objects[key] for key in sorted(objects)),
        *(manifests[key] for key in sorted(manifests)),
        immutable_snapshot,
        *aliases,
    )
    return R2UploadPlan(
        release_root=root,
        revision=verification.revision,
        prefix=normalized_prefix,
        items=tuple(items),
    )


def _is_precondition_failed(error: Exception) -> bool:
    response = getattr(error, "response", None)
    if not isinstance(response, Mapping):
        return False
    metadata = response.get("ResponseMetadata")
    status = metadata.get("HTTPStatusCode") if isinstance(metadata, Mapping) else None
    error_detail = response.get("Error")
    code = error_detail.get("Code") if isinstance(error_detail, Mapping) else None
    return status == 412 or code in {"PreconditionFailed", "412", "10031"}


def _is_bucket_policy_lock(error: Exception) -> bool:
    response = getattr(error, "response", None)
    if not isinstance(response, Mapping):
        return False
    metadata = response.get("ResponseMetadata")
    status = metadata.get("HTTPStatusCode") if isinstance(metadata, Mapping) else None
    error_detail = response.get("Error")
    code = error_detail.get("Code") if isinstance(error_detail, Mapping) else None
    if str(code) not in {"10069", "ObjectLockedByBucketPolicy"}:
        return False
    # Cloudflare's S3 compatibility layer has returned this exact lock code
    # with more than one client-error status.  The fallback remains fail closed:
    # it accepts only a 4xx lock response (or an SDK response without a status),
    # then HEADs and downloads the existing object to verify its exact bytes.
    return status is None or (
        isinstance(status, int) and not isinstance(status, bool) and 400 <= status < 500
    )


def _verify_local_item(item: R2UploadItem) -> None:
    actual_size = item.source_path.stat().st_size
    actual_digest = sha256_file(item.source_path)
    if actual_size != item.size_bytes or actual_digest != item.sha256:
        raise R2SyncError(f"release file changed after planning: {item.source_path}")


def _normalized_cache_control(value: str) -> str:
    return ",".join(directive.strip() for directive in value.split(","))


def _remote_body_digest(body: Any) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    if hasattr(body, "read"):
        while chunk := body.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    else:
        payload = bytes(body)
        size = len(payload)
        digest.update(payload)
    return size, digest.hexdigest()


def _verify_existing_immutable(
    *,
    client: Any,
    bucket: str,
    item: R2UploadItem,
    collision: Exception,
    force_download: bool,
) -> None:
    head = client.head_object(Bucket=bucket, Key=item.key)
    metadata_value = head.get("Metadata")
    metadata = (
        {str(key).lower(): str(value) for key, value in metadata_value.items()}
        if isinstance(metadata_value, Mapping)
        else {}
    )
    remote_digest = metadata.get(SHA256_METADATA_KEY, "").lower()
    remote_size = head.get("ContentLength")
    if remote_size != item.size_bytes or (remote_digest and remote_digest != item.sha256):
        raise R2ImmutableConflict(
            f"immutable R2 key {item.key!r} already contains different content"
        ) from collision

    verify_bytes = item.verify_existing_bytes or force_download
    if not verify_bytes:
        if remote_digest != item.sha256:
            raise R2ImmutableConflict(
                f"immutable R2 key {item.key!r} lacks matching integrity metadata"
            ) from collision
        return

    remote_content_type = head.get("ContentType")
    if (
        not isinstance(remote_content_type, str)
        or remote_content_type.split(";", 1)[0].strip().lower() != item.content_type.lower()
    ):
        raise R2ImmutableConflict(
            f"immutable R2 key {item.key!r} has unexpected content type"
        ) from collision
    remote_cache_control = head.get("CacheControl")
    if not isinstance(remote_cache_control, str) or _normalized_cache_control(
        remote_cache_control
    ) != _normalized_cache_control(item.cache_control):
        raise R2ImmutableConflict(
            f"immutable R2 key {item.key!r} has unexpected cache policy"
        ) from collision

    response = client.get_object(Bucket=bucket, Key=item.key)
    body = response.get("Body")
    if body is None:
        raise R2SyncError(
            f"R2 did not return bytes for existing immutable key {item.key!r}"
        ) from collision
    try:
        downloaded_size, downloaded_digest = _remote_body_digest(body)
    finally:
        close = getattr(body, "close", None)
        if callable(close):
            close()
    if downloaded_size != item.size_bytes or downloaded_digest != item.sha256:
        raise R2ImmutableConflict(
            f"immutable R2 key {item.key!r} already contains different content"
        ) from collision


def _put_immutable(*, client: Any, bucket: str, item: R2UploadItem) -> bool:
    try:
        with item.source_path.open("rb") as body:
            client.put_object(
                Bucket=bucket,
                Key=item.key,
                Body=body,
                IfNoneMatch="*",
                Metadata={SHA256_METADATA_KEY: item.sha256},
                ContentType=item.content_type,
                CacheControl=item.cache_control,
            )
    except Exception as error:
        precondition_failed = _is_precondition_failed(error)
        bucket_policy_lock = _is_bucket_policy_lock(error)
        if not precondition_failed and not bucket_policy_lock:
            raise
        _verify_existing_immutable(
            client=client,
            bucket=bucket,
            item=item,
            collision=error,
            force_download=bucket_policy_lock,
        )
        return True
    return False


def execute_upload_plan(
    plan: R2UploadPlan,
    *,
    bucket: str,
    client: Any,
    immutable_only: bool = False,
) -> R2SyncResult:
    """Execute immutable writes first, optionally stopping before mutable aliases."""

    if not bucket:
        raise ValueError("R2 bucket must not be empty")
    uploaded: list[str] = []
    already_present: list[str] = []
    aliases_updated: list[str] = []
    alias_phase = False
    for item in plan.items:
        if item.immutable:
            if alias_phase:
                raise ValueError("immutable R2 uploads must precede aliases")
        else:
            alias_phase = True
            if item.release_key not in ALIAS_KEYS:
                raise ValueError(f"unsupported mutable R2 key: {item.release_key!r}")
            if immutable_only:
                continue
        _verify_local_item(item)
        if item.immutable:
            if _put_immutable(client=client, bucket=bucket, item=item):
                already_present.append(item.key)
            else:
                uploaded.append(item.key)
            continue
        with item.source_path.open("rb") as body:
            client.put_object(
                Bucket=bucket,
                Key=item.key,
                Body=body,
                Metadata={SHA256_METADATA_KEY: item.sha256},
                ContentType=item.content_type,
                CacheControl=item.cache_control,
            )
        aliases_updated.append(item.key)
    return R2SyncResult(
        uploaded=tuple(uploaded),
        already_present=tuple(already_present),
        aliases_updated=tuple(aliases_updated),
    )


def sync_release(
    release_root: str | Path,
    *,
    bucket: str,
    client: Any,
    prefix: str = "",
    immutable_only: bool = False,
) -> R2SyncResult:
    """Build and execute an R2 upload plan for a verified static release."""

    return execute_upload_plan(
        build_upload_plan(release_root, prefix=prefix),
        bucket=bucket,
        client=client,
        immutable_only=immutable_only,
    )


def r2_client(
    *,
    endpoint_url: str,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
) -> Any:
    """Create a boto3-compatible R2 client without importing boto3 at module load."""

    if not access_key_id or not secret_access_key:
        raise ValueError(
            "R2 sync requires both NEURALSTOCK_R2_ACCESS_KEY_ID and "
            "NEURALSTOCK_R2_SECRET_ACCESS_KEY; ambient AWS credentials are disabled"
        )
    parsed_endpoint = urlsplit(endpoint_url)
    hostname = (parsed_endpoint.hostname or "").lower()
    if (
        parsed_endpoint.scheme != "https"
        or parsed_endpoint.username is not None
        or parsed_endpoint.password is not None
        or parsed_endpoint.query
        or parsed_endpoint.fragment
        or parsed_endpoint.path not in {"", "/"}
        or not hostname.endswith(".r2.cloudflarestorage.com")
    ):
        raise ValueError("R2 endpoint must be an HTTPS Cloudflare R2 S3 endpoint")
    try:
        import boto3
    except ImportError as error:
        message = "R2 support requires the optional 'neuralstock[r2]' dependency"
        raise RuntimeError(message) from error

    arguments: dict[str, Any] = {
        "service_name": "s3",
        "endpoint_url": endpoint_url,
        "region_name": "auto",
    }
    arguments["aws_access_key_id"] = access_key_id
    arguments["aws_secret_access_key"] = secret_access_key
    return boto3.client(**arguments)
