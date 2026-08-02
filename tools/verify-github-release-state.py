#!/usr/bin/env python3
"""Verify the exact local and GitHub state of a NeuralStock release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class ReleaseStateError(RuntimeError):
    """The release is not in the exact state required for publication."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ReleaseStateError(f"{path} is not strict UTF-8 JSON: {error}") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise ReleaseStateError(f"cannot hash {path}: {error}") from error
    return digest.hexdigest()


def verify(
    release_path: Path,
    assets_dir: Path,
    version: str,
    revision: str,
    source_commit: str,
    evidence_sha256: str,
    expected_state: str,
) -> dict[str, Any]:
    if SEMVER_PATTERN.fullmatch(version) is None:
        raise ReleaseStateError("version is not a plain semantic version")
    if SHA256_PATTERN.fullmatch(revision) is None:
        raise ReleaseStateError("revision is not a lowercase SHA-256")
    if COMMIT_PATTERN.fullmatch(source_commit) is None:
        raise ReleaseStateError("source commit is not 40 lowercase hexadecimal characters")
    if SHA256_PATTERN.fullmatch(evidence_sha256) is None:
        raise ReleaseStateError("evidence digest is not a lowercase SHA-256")
    if expected_state not in {"draft", "immutable"}:
        raise ReleaseStateError("expected state must be draft or immutable")
    if not assets_dir.is_dir() or assets_dir.is_symlink():
        raise ReleaseStateError("release asset directory is absent or unsafe")

    archive_name = f"neuralstock-release-{version}.tar.gz"
    evidence_name = f"neuralstock-r2-release-lock-{revision}.json"
    expected_names = {
        "SHA256SUMS",
        archive_name,
        "r2-plan.json",
        "release-metadata.json",
        "worker-image-metadata.json",
        evidence_name,
    }
    local_paths = list(assets_dir.iterdir())
    if any(not path.is_file() or path.is_symlink() for path in local_paths):
        raise ReleaseStateError("release asset directory contains a non-regular file")
    local_names = {path.name for path in local_paths}
    if local_names != expected_names or len(local_paths) != len(expected_names):
        raise ReleaseStateError(
            f"local release assets differ from the exact expected set: {sorted(local_names)}"
        )

    release = _load_json(release_path)
    if not isinstance(release, dict):
        raise ReleaseStateError("GitHub release response is not an object")
    if release.get("tag_name") != f"v{version}":
        raise ReleaseStateError("GitHub release tag does not match the requested version")
    if release.get("name") != f"NeuralStock {version}":
        raise ReleaseStateError("GitHub release title does not match the requested version")
    if release.get("prerelease") is not False:
        raise ReleaseStateError("GitHub release must not be a prerelease")
    if expected_state == "draft":
        if release.get("draft") is not True or release.get("immutable") is not False:
            raise ReleaseStateError("GitHub release is not the expected mutable draft")
        if release.get("published_at") is not None:
            raise ReleaseStateError("draft GitHub release already has a publication timestamp")
    elif (
        release.get("draft") is not False
        or release.get("immutable") is not True
        or not isinstance(release.get("published_at"), str)
        or not release["published_at"]
    ):
        raise ReleaseStateError("GitHub release is not published and immutable")

    assets = release.get("assets")
    if not isinstance(assets, list) or not all(isinstance(asset, dict) for asset in assets):
        raise ReleaseStateError("GitHub release assets are not an array of objects")
    remote_names = [asset.get("name") for asset in assets]
    if not all(isinstance(name, str) for name in remote_names):
        raise ReleaseStateError("a GitHub release asset name is invalid")
    if set(remote_names) != expected_names or len(remote_names) != len(expected_names):
        raise ReleaseStateError(
            f"GitHub release assets differ from the exact expected set: {sorted(remote_names)!r}"
        )
    remote_ids = [asset.get("id") for asset in assets]
    if not all(
        isinstance(asset_id, int) and not isinstance(asset_id, bool) and asset_id > 0
        for asset_id in remote_ids
    ) or len(set(remote_ids)) != len(expected_names):
        raise ReleaseStateError("GitHub release asset IDs are invalid or duplicated")
    local_by_name = {path.name: path for path in local_paths}
    for asset in assets:
        name = asset["name"]
        path = local_by_name[name]
        if asset.get("state") != "uploaded":
            raise ReleaseStateError(f"GitHub release asset is not uploaded: {name}")
        if asset.get("size") != path.stat().st_size:
            raise ReleaseStateError(f"GitHub release asset size differs locally: {name}")
        expected_digest = f"sha256:{_sha256(path)}"
        if asset.get("digest") != expected_digest:
            raise ReleaseStateError(f"GitHub release asset digest differs locally: {name}")

    metadata = _load_json(assets_dir / "release-metadata.json")
    if not isinstance(metadata, dict):
        raise ReleaseStateError("release metadata is not an object")
    expected_metadata = {
        "release_version": version,
        "package_version": version,
        "release_tag": f"v{version}",
        "source_commit": source_commit,
        "registry_revision": revision,
        "release_archive": archive_name,
    }
    for field, expected in expected_metadata.items():
        if metadata.get(field) != expected:
            raise ReleaseStateError(f"release metadata has unexpected {field}")
    if _sha256(assets_dir / evidence_name) != evidence_sha256:
        raise ReleaseStateError("R2 lock evidence SHA-256 does not match the approved digest")

    release_id = release.get("id")
    if not isinstance(release_id, int) or isinstance(release_id, bool) or release_id <= 0:
        raise ReleaseStateError("GitHub release ID is invalid")
    return {
        "assets": len(expected_names),
        "evidence_sha256": evidence_sha256,
        "registry_revision": revision,
        "release_id": release_id,
        "state": expected_state,
        "tag": f"v{version}",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_json", type=Path)
    parser.add_argument("assets_dir", type=Path)
    parser.add_argument("version")
    parser.add_argument("revision")
    parser.add_argument("source_commit")
    parser.add_argument("evidence_sha256")
    parser.add_argument("--state", choices=("draft", "immutable"), required=True)
    arguments = parser.parse_args()
    try:
        result = verify(
            arguments.release_json,
            arguments.assets_dir,
            arguments.version,
            arguments.revision,
            arguments.source_commit,
            arguments.evidence_sha256,
            arguments.state,
        )
    except (ReleaseStateError, KeyError, OSError, TypeError, ValueError) as error:
        print(f"GitHub release state rejected: {error}", file=sys.stderr)
        return 65
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
