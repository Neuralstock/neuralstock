"""Build deterministic static registry snapshots from published asset manifests."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from neuralstock.canonical import read_json, sha256_json, write_json_atomic
from neuralstock.schema import require_valid_document
from neuralstock.storage import object_key, version_manifest_key

SEMVER = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


def generated_timestamp() -> str:
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch is not None:
        moment = datetime.fromtimestamp(int(source_date_epoch), tz=UTC)
    else:
        moment = datetime.now(tz=UTC)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def semantic_version_key(
    version: str,
) -> tuple[int, int, int, int, tuple[tuple[int, int | str], ...]]:
    match = SEMVER.fullmatch(version)
    if match is None:
        raise ValueError(f"invalid semantic version: {version!r}")
    prerelease = match.group("prerelease")
    identifiers: list[tuple[int, int | str]] = []
    for identifier in (prerelease or "").split(".") if prerelease is not None else ():
        if identifier.isdigit():
            if len(identifier) > 1 and identifier.startswith("0"):
                raise ValueError(f"invalid numeric prerelease identifier: {version!r}")
            identifiers.append((0, int(identifier)))
        else:
            identifiers.append((1, identifier))
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        1 if prerelease is None else 0,
        tuple(identifiers),
    )


def revision_payload(registry: dict[str, Any]) -> dict[str, Any]:
    """Return the exact snapshot fields protected by ``revision``."""

    return {
        "generated_at": registry["generated_at"],
        "profiles": registry["profiles"],
        "entries": registry["entries"],
        "aliases": registry["aliases"],
        "withdrawals": registry["withdrawals"],
    }


def _relative_uri(path: Path, base: Path) -> str:
    relative = Path(os.path.relpath(path.resolve(), base.resolve())).as_posix()
    if relative.startswith("../"):
        raise ValueError(f"manifest must be inside the registry output tree: {path}")
    return f"./{relative}" if not relative.startswith(".") else relative


def manifest_artifact(
    path: Path,
    registry_directory: Path,
    *,
    public_uri: str | None = None,
) -> dict[str, Any]:
    from neuralstock.canonical import sha256_file

    return {
        "role": "manifest",
        "file_name": "asset.json",
        "media_type": "application/json",
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "uri": public_uri or _relative_uri(path, registry_directory),
    }


def registry_entry(
    manifest: dict[str, Any],
    manifest_path: Path,
    registry_directory: Path,
) -> dict[str, Any]:
    require_valid_document("asset", manifest)
    return {
        "asset": {"id": manifest["id"], "version": manifest["version"]},
        "name": manifest["name"],
        "description": manifest["description"],
        "license": manifest["license"],
        "target_profile": manifest["target_profile"],
        "coordinate_system": manifest["coordinate_system"],
        "semantics": manifest["semantics"],
        "bounds_m": manifest["bounds_m"],
        "triangle_count": manifest["geometry"]["triangle_count"],
        "manifest": manifest_artifact(
            manifest_path,
            registry_directory,
            public_uri=f"/{version_manifest_key(manifest['id'], manifest['version'])}",
        ),
    }


def build_registry(
    manifest_paths: Iterable[str | Path],
    *,
    output: str | Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    output_path = Path(output)
    entries = [
        registry_entry(read_json(path), Path(path), output_path.parent)
        for path in sorted(
            (Path(value) for value in manifest_paths), key=lambda item: item.as_posix()
        )
    ]
    entries.sort(
        key=lambda item: (item["asset"]["id"], semantic_version_key(item["asset"]["version"]))
    )

    seen: set[tuple[str, str]] = set()
    for entry in entries:
        identity = (entry["asset"]["id"], entry["asset"]["version"])
        if identity in seen:
            raise ValueError(f"duplicate asset version: {identity[0]}@{identity[1]}")
        seen.add(identity)

    latest: dict[str, str] = {}
    for entry in entries:
        identity = entry["asset"]
        current = latest.get(identity["id"])
        if current is None or semantic_version_key(identity["version"]) > semantic_version_key(
            current
        ):
            latest[identity["id"]] = identity["version"]

    aliases = [
        {"id": asset_id, "alias": "latest", "version": version}
        for asset_id, version in sorted(latest.items())
    ]
    snapshot_time = generated_at or generated_timestamp()
    payload = {
        "generated_at": snapshot_time,
        "profiles": ["web-v1"],
        "entries": entries,
        "aliases": aliases,
        "withdrawals": [],
    }
    registry = {
        "$schema": "https://schemas.neuralstock.ai/v0.2/registry.schema.json",
        "schema_version": "0.2",
        "document_type": "registry",
        "generated": True,
        "revision": sha256_json(payload),
        **payload,
    }
    require_valid_document("registry", registry)
    write_json_atomic(output_path, registry)
    return registry


def publication_objects(registry: dict[str, Any]) -> list[str]:
    """Return immutable content-addressed keys referenced by a registry snapshot."""

    keys: set[str] = set()
    for entry in registry["entries"]:
        keys.add(object_key(entry["manifest"]["sha256"]))
    return sorted(keys)
