"""Immutable, content-addressed local storage compatible with the R2 key plan."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from neuralstock.canonical import sha256_file


def require_sha256(digest: str) -> str:
    normalized = digest.lower()
    invalid_character = any(character not in "0123456789abcdef" for character in normalized)
    if len(normalized) != 64 or invalid_character:
        raise ValueError(f"invalid SHA-256 digest: {digest!r}")
    return normalized


def object_key(digest: str) -> str:
    normalized = require_sha256(digest)
    return f"objects/sha256/{normalized[:2]}/{normalized}"


def version_manifest_key(asset_id: str, version: str) -> str:
    _safe_segment(asset_id, "asset ID")
    _safe_segment(version, "version")
    return f"assets/{asset_id}/{version}/manifest.json"


def snapshot_key(revision: str) -> str:
    _safe_segment(revision, "revision")
    return f"snapshots/{revision}/registry.json"


def _safe_segment(value: str, label: str) -> None:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"unsafe {label}: {value!r}")


@dataclass(frozen=True)
class PublishedObject:
    digest: str
    key: str
    path: Path
    size_bytes: int
    already_present: bool


def _copy_immutable(source: Path, destination: Path) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(source) != sha256_file(destination):
            raise FileExistsError(
                f"immutable destination already has different bytes: {destination}"
            )
        return True

    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if sha256_file(source) != sha256_file(destination):
                raise FileExistsError(
                    f"immutable destination raced with different bytes: {destination}"
                ) from None
        return False
    finally:
        temporary.unlink(missing_ok=True)


def publish_object(source: str | Path, root: str | Path) -> PublishedObject:
    source_path = Path(source)
    digest = sha256_file(source_path)
    key = object_key(digest)
    destination = Path(root) / key
    already_present = _copy_immutable(source_path, destination)
    return PublishedObject(
        digest=digest,
        key=key,
        path=destination,
        size_bytes=source_path.stat().st_size,
        already_present=already_present,
    )


def publish_named_immutable(source: str | Path, root: str | Path, key: str) -> Path:
    if key.startswith("/") or ".." in Path(key).parts:
        raise ValueError(f"unsafe storage key: {key!r}")
    source_path = Path(source)
    destination = Path(root) / key
    _copy_immutable(source_path, destination)
    return destination


def replace_alias(source: str | Path, root: str | Path, key: str) -> Path:
    """Atomically replace an explicitly mutable alias such as snapshots/latest.json."""

    if key.startswith("/") or ".." in Path(key).parts:
        raise ValueError(f"unsafe storage key: {key!r}")
    source_path = Path(source)
    destination = Path(root) / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source_path, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
