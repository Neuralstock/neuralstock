#!/usr/bin/env python3
"""Verify a staged immutable release and manage its three R2 bucket locks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

BUCKET = "neuralstock-public"
MUTABLE_ALIASES = ("registry.json", "snapshots/latest.json")
ENV_CREDENTIALS = (
    "CLOUDFLARE_API_TOKEN",
    "CF_API_TOKEN",
    "CLOUDFLARE_API_KEY",
    "CLOUDFLARE_API_USER_SERVICE_KEY",
    "WRANGLER_CF_AUTHORIZATION_TOKEN",
)
HISTORICAL_RULES = (
    ("immutable-manifests", "assets/"),
    ("immutable-objects", "objects/sha256/"),
    ("schema-v0.1", "v0.1/"),
    ("profile-v0.1", "profiles/v0.1/"),
    (
        "room-zero-snapshot",
        "snapshots/a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523/",
    ),
)
SCHEMA_NAMES = (
    "asset.intent.schema.json",
    "asset.schema.json",
    "build-receipt.schema.json",
    "common.schema.json",
    "discovery.schema.json",
    "inspection.schema.json",
    "profile.schema.json",
    "provenance.schema.json",
    "registry.schema.json",
)
CONTRACT_KEYS = frozenset(
    [
        *(f"v0.2/{name}" for name in SCHEMA_NAMES),
        "v0.2/LICENSE",
        "profiles/v0.2/web-v1.json",
        "profiles/v0.2/LICENSE",
    ]
)
REVISION_PATTERN = re.compile(r"^[0-9a-f]{64}$")
LOCK_FIELD_PATTERN = re.compile(r"^(name|enabled|prefix|condition):\s*(.*)$")


class GateError(RuntimeError):
    """A fail-closed retention-gate error."""


@dataclass(frozen=True)
class LockRule:
    name: str
    enabled: bool
    prefix: str
    condition: str


@dataclass(frozen=True)
class PlanItem:
    key: str
    sha256: str
    bytes: int
    content_type: str
    immutable: bool
    source_path: Path


def _run(
    arguments: list[str],
    *,
    cwd: Path,
    capture_stdout: bool = False,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        env={**os.environ, "NO_COLOR": "1"},
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    if completed.stdout and not capture_stdout:
        print(completed.stdout, file=sys.stderr, end="")
    if completed.returncode:
        raise GateError(f"command failed ({completed.returncode}): {' '.join(arguments)}")
    return completed


def _require_manual_oauth() -> None:
    if os.environ.get("CI", "").lower() == "true":
        raise GateError("snapshot lock management is a manual gate and must not run in CI")
    for name in ENV_CREDENTIALS:
        if os.environ.get(name):
            raise GateError(f"unset {name}; authenticate this manual gate with wrangler login")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _require_toolchain(project_root: Path) -> str:
    for command in ("pnpm", "uv"):
        if shutil.which(command) is None:
            raise GateError(f"required command is unavailable: {command}")
    package = json.loads((project_root / "package.json").read_text(encoding="utf-8"))
    expected = package["devDependencies"]["wrangler"]
    actual = _run(
        ["pnpm", "wrangler", "--version"], cwd=project_root, capture_stdout=True
    ).stdout.strip()
    if actual != expected:
        raise GateError(f"wrangler version mismatch: expected {expected}, got {actual}")
    return actual


def _parse_lock_rules(output: str) -> list[LockRule]:
    raw_rules: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in output.replace("\r", "").splitlines():
        match = LOCK_FIELD_PATTERN.match(line)
        if match is None:
            continue
        field, value = match.groups()
        if field == "name":
            if current is not None:
                raw_rules.append(current)
            current = {}
        if current is not None:
            current[field] = value.rstrip()
    if current is not None:
        raw_rules.append(current)
    if not raw_rules:
        raise GateError("wrangler returned no parseable R2 lock rules")

    rules: list[LockRule] = []
    for raw in raw_rules:
        if set(raw) != {"name", "enabled", "prefix", "condition"}:
            raise GateError(f"wrangler returned an incomplete lock rule: {raw.get('name', '?')}")
        if raw["enabled"] not in {"Yes", "No"}:
            raise GateError(f"wrangler returned an invalid enabled value: {raw['enabled']}")
        rules.append(
            LockRule(
                name=raw["name"],
                enabled=raw["enabled"] == "Yes",
                prefix=raw["prefix"],
                condition=raw["condition"],
            )
        )
    return rules


def _list_rules(project_root: Path) -> tuple[list[LockRule], str]:
    completed = _run(
        ["pnpm", "wrangler", "r2", "bucket", "lock", "list", BUCKET],
        cwd=project_root,
        capture_stdout=True,
    )
    print(completed.stdout, file=sys.stderr, end="")
    return _parse_lock_rules(completed.stdout), completed.stdout


def _validate_rules(rules: list[LockRule]) -> None:
    for expected_name, expected_prefix in HISTORICAL_RULES:
        named = [rule for rule in rules if rule.name == expected_name]
        exact = [
            rule
            for rule in named
            if rule.enabled and rule.prefix == expected_prefix and rule.condition == "indefinitely"
        ]
        if len(named) != 1 or len(exact) != 1:
            raise GateError(
                f"required historical lock {expected_name} does not have its exact enabled "
                f"indefinite prefix {expected_prefix}"
            )

    for rule in rules:
        if not rule.enabled or rule.condition != "indefinitely":
            continue
        if rule.prefix in {"", "(all prefixes)"} or any(
            alias.startswith(rule.prefix) for alias in MUTABLE_ALIASES
        ):
            raise GateError(
                f"enabled indefinite lock {rule.name!r} on {rule.prefix!r} would cover a "
                "mutable alias"
            )


def _target_rule(
    rules: list[LockRule], *, expected_name: str, expected_prefix: str
) -> LockRule | None:
    by_prefix = [rule for rule in rules if rule.prefix == expected_prefix]
    exact = [rule for rule in by_prefix if rule.enabled and rule.condition == "indefinitely"]
    named = [rule for rule in rules if rule.name == expected_name]
    if len(exact) > 1 or len(by_prefix) > 1:
        raise GateError(f"multiple rules use target prefix {expected_prefix}")
    if exact:
        if exact[0].name != expected_name:
            raise GateError(
                f"target prefix {expected_prefix} uses rule name {exact[0].name!r}, "
                f"expected {expected_name!r}"
            )
        return exact[0]
    if by_prefix:
        raise GateError(f"target prefix {expected_prefix} has a disabled or non-indefinite rule")
    if named:
        raise GateError(f"target rule name {expected_name} is attached to another prefix")
    return None


def _safe_source_path(release_root: Path, key: str) -> Path:
    if "\\" in key:
        raise GateError(f"R2 plan contains an unsafe key: {key!r}")
    relative = PurePosixPath(key)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise GateError(f"R2 plan contains an unsafe key: {key!r}")
    candidate = release_root.joinpath(*relative.parts)
    resolved = candidate.resolve()
    if candidate != resolved or (resolved != release_root and release_root not in resolved.parents):
        raise GateError(f"R2 plan key resolves outside the release root: {key!r}")
    if not resolved.is_file():
        raise GateError(f"R2 plan source is missing: {key}")
    return resolved


def _load_plan(
    project_root: Path, release_root: Path, revision: str
) -> tuple[list[PlanItem], bytes]:
    completed = _run(
        [
            "uv",
            "run",
            "--frozen",
            "neuralstock",
            "r2",
            "plan",
            "--root",
            str(release_root),
        ],
        cwd=project_root,
        capture_stdout=True,
    )
    raw = completed.stdout.encode()
    try:
        plan = json.loads(
            completed.stdout,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {value}")
            ),
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise GateError(f"R2 plan is not strict JSON: {error}") from error
    if plan.get("revision") != revision:
        raise GateError("R2 plan revision does not match the requested registry revision")
    raw_items = plan.get("items")
    if not isinstance(raw_items, list):
        raise GateError("R2 plan has no items array")

    items: list[PlanItem] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise GateError("R2 plan contains a non-object item")
        key = raw_item.get("key")
        digest = raw_item.get("sha256")
        size = raw_item.get("bytes")
        content_type = raw_item.get("content_type")
        immutable = raw_item.get("immutable")
        if not isinstance(key, str) or key in seen:
            raise GateError(f"R2 plan contains an invalid or duplicate key: {key!r}")
        seen.add(key)
        if not isinstance(digest, str) or REVISION_PATTERN.fullmatch(digest) is None:
            raise GateError(f"R2 plan contains an invalid SHA-256: {key}")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise GateError(f"R2 plan contains an invalid byte count: {key}")
        if not isinstance(content_type, str) or not content_type:
            raise GateError(f"R2 plan contains an invalid content type: {key}")
        if not isinstance(immutable, bool):
            raise GateError(f"R2 plan contains an invalid immutable flag: {key}")
        source_path = _safe_source_path(release_root, key)
        body = source_path.read_bytes()
        if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
            raise GateError(f"R2 plan descriptor differs from release file: {key}")
        items.append(
            PlanItem(
                key=key,
                sha256=digest,
                bytes=size,
                content_type=content_type,
                immutable=immutable,
                source_path=source_path,
            )
        )

    aliases = [item for item in items if not item.immutable]
    if [item.key for item in aliases] != list(MUTABLE_ALIASES):
        raise GateError(
            "R2 plan must end with only registry.json and snapshots/latest.json aliases"
        )
    if [item.key for item in items[-2:]] != list(MUTABLE_ALIASES):
        raise GateError("R2 plan aliases are not last")
    immutable_items = [item for item in items if item.immutable]
    if {item.key for item in immutable_items if item.key in CONTRACT_KEYS} != CONTRACT_KEYS:
        raise GateError("R2 plan is missing one or more exact v0.2 contract objects")
    unexpected_contracts = {
        item.key
        for item in immutable_items
        if item.key.startswith(("v0.2/", "profiles/v0.2/")) and item.key not in CONTRACT_KEYS
    }
    if unexpected_contracts:
        raise GateError(
            f"R2 plan contains unexpected v0.2 contract objects: {unexpected_contracts}"
        )
    snapshot_key = f"snapshots/{revision}/registry.json"
    snapshots = [item for item in immutable_items if item.key == snapshot_key]
    if len(snapshots) != 1:
        raise GateError("R2 plan is missing its exact immutable revision snapshot")
    snapshot = snapshots[0]
    if any(alias.sha256 != snapshot.sha256 or alias.bytes != snapshot.bytes for alias in aliases):
        raise GateError("mutable aliases do not match the exact revision snapshot descriptor")
    _verify_snapshot_semantics(snapshot.source_path, revision)
    return immutable_items, raw


def _verify_snapshot_semantics(snapshot_path: Path, revision: str) -> None:
    registry = json.loads(
        snapshot_path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON number: {value}")
        ),
    )
    if registry.get("revision") != revision:
        raise GateError("revision snapshot declares a different registry revision")
    payload = {
        "generated_at": registry["generated_at"],
        "profiles": registry["profiles"],
        "entries": registry["entries"],
        "aliases": registry["aliases"],
        "withdrawals": registry["withdrawals"],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if hashlib.sha256(canonical).hexdigest() != revision:
        raise GateError("revision snapshot semantic revision does not match the requested revision")


def _verify_direct_r2(
    project_root: Path,
    items: list[PlanItem],
    destination: Path,
    revision: str,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        output = destination / f"{index:04d}.object"
        _run(
            [
                "pnpm",
                "wrangler",
                "r2",
                "object",
                "get",
                f"{BUCKET}/{item.key}",
                "--file",
                str(output),
                "--remote",
            ],
            cwd=project_root,
        )
        body = output.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        if len(body) != item.bytes or digest != item.sha256:
            raise GateError(f"direct R2 object differs from its release descriptor: {item.key}")
        if body != item.source_path.read_bytes():
            raise GateError(f"direct R2 object differs from the release file: {item.key}")
        if item.key == f"snapshots/{revision}/registry.json":
            _verify_snapshot_semantics(output, revision)
        evidence.append(
            {
                "key": item.key,
                "sha256": digest,
                "bytes": len(body),
                "content_type": item.content_type,
            }
        )
    return evidence


def _add_rule(project_root: Path, name: str, prefix: str) -> None:
    _run(
        [
            "pnpm",
            "wrangler",
            "r2",
            "bucket",
            "lock",
            "add",
            BUCKET,
            name,
            prefix,
            "--retention-indefinite",
            "--force",
        ],
        cwd=project_root,
    )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("verify a staged NeuralStock immutable release and manage its exact R2 locks")
    )
    parser.add_argument("revision", help="64-character semantic registry revision")
    parser.add_argument("--release-root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="create missing exact lock rules")
    return parser.parse_args()


def run() -> dict[str, Any]:
    arguments = _arguments()
    revision = arguments.revision
    if REVISION_PATTERN.fullmatch(revision) is None:
        raise GateError("revision must be a 64-character lowercase hexadecimal SHA-256")
    release_root = arguments.release_root.resolve()
    if not release_root.is_dir():
        raise GateError(f"release root does not exist: {release_root}")

    _require_manual_oauth()
    project_root = _project_root()
    wrangler_version = _require_toolchain(project_root)
    immutable_items, raw_plan = _load_plan(project_root, release_root, revision)
    _run(
        ["sh", str(project_root / "tools" / "verify-contract-origin.sh"), str(release_root)],
        cwd=project_root,
    )

    target_specs = (
        ("schema", "schema-v0.2", "v0.2/"),
        ("profile", "profile-v0.2", "profiles/v0.2/"),
        ("snapshot", f"snapshot-{revision[:16]}", f"snapshots/{revision}/"),
    )
    rules_before, _raw_before = _list_rules(project_root)
    _validate_rules(rules_before)
    targets_before = {
        label: _target_rule(rules_before, expected_name=name, expected_prefix=prefix)
        for label, name, prefix in target_specs
    }
    missing = [label for label, rule in targets_before.items() if rule is None]
    if missing and not arguments.apply:
        raise GateError(
            "release locks are missing for "
            + ", ".join(missing)
            + "; after immutable staging verifies, rerun with --apply"
        )

    created: list[str] = []
    with tempfile.TemporaryDirectory(prefix="neuralstock-r2-lock-") as temporary:
        temporary_root = Path(temporary)
        (temporary_root / "before").mkdir()
        before_evidence = _verify_direct_r2(
            project_root,
            immutable_items,
            temporary_root / "before",
            revision,
        )

        for label, name, prefix in target_specs:
            if targets_before[label] is None:
                _add_rule(project_root, name, prefix)
                created.append(name)

        rules_after, raw_after = _list_rules(project_root)
        _validate_rules(rules_after)
        targets_after = {
            label: _target_rule(rules_after, expected_name=name, expected_prefix=prefix)
            for label, name, prefix in target_specs
        }
        absent = [label for label, rule in targets_after.items() if rule is None]
        if absent:
            raise GateError(f"exact release locks are absent from readback: {', '.join(absent)}")

        target_items = [
            item
            for item in immutable_items
            if item.key in CONTRACT_KEYS or item.key == f"snapshots/{revision}/registry.json"
        ]
        if created:
            (temporary_root / "after").mkdir()
            after_target_evidence = _verify_direct_r2(
                project_root,
                target_items,
                temporary_root / "after",
                revision,
            )
            before_targets = [
                item
                for item in before_evidence
                if item["key"] in CONTRACT_KEYS
                or item["key"] == f"snapshots/{revision}/registry.json"
            ]
            if before_targets != after_target_evidence:
                raise GateError("target R2 object evidence changed across lock creation")
        else:
            after_target_evidence = [
                item
                for item in before_evidence
                if item["key"] in CONTRACT_KEYS
                or item["key"] == f"snapshots/{revision}/registry.json"
            ]

    serialized_targets = {
        label: asdict(rule) for label, rule in targets_after.items() if rule is not None
    }
    return {
        "document_type": "neuralstock-r2-release-lock-readback",
        "bucket": BUCKET,
        "registry_revision": revision,
        "mode": "created" if created else "already-present",
        "created_rules": created,
        "verified_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "wrangler_version": wrangler_version,
        "release_plan_sha256": hashlib.sha256(raw_plan).hexdigest(),
        "verification": {
            "candidate_plan_and_files": True,
            "public_v0_2_contract_bytes": True,
            "direct_r2_immutable_items": len(before_evidence),
            "post_lock_target_items": len(after_target_evidence),
            "pre_post_target_comparison_performed": bool(created),
            "target_bytes_unchanged_across_creation": True if created else None,
        },
        "rules": serialized_targets,
        "raw_lock_readback_sha256": hashlib.sha256(raw_after.encode()).hexdigest(),
        "direct_r2_immutable_evidence": before_evidence,
        "direct_r2_post_lock_target_evidence": after_target_evidence,
        "all_rules": [asdict(rule) for rule in rules_after],
    }


def main() -> int:
    try:
        evidence = run()
    except (GateError, KeyError, OSError, TypeError, ValueError) as error:
        print(f"retention gate failed: {error}", file=sys.stderr)
        return 65
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
