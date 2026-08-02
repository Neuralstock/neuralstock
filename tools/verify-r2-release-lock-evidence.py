#!/usr/bin/env python3
"""Fail closed unless release-lock evidence exactly binds a staged R2 plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

HISTORICAL_RULES = {
    "immutable-manifests": "assets/",
    "immutable-objects": "objects/sha256/",
    "schema-v0.1": "v0.1/",
    "profile-v0.1": "profiles/v0.1/",
    "room-zero-snapshot": (
        "snapshots/a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523/"
    ),
}
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
MUTABLE_ALIASES = ("registry.json", "snapshots/latest.json")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(RuntimeError):
    """The supplied evidence cannot authorize production publication."""


def _strict_json(path: Path) -> tuple[Any, bytes]:
    raw = path.read_bytes()
    try:
        return (
            json.loads(
                raw,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"non-finite JSON number: {value}")
                ),
            ),
            raw,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise EvidenceError(f"{path} is not strict UTF-8 JSON: {error}") from error


def _descriptor(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise EvidenceError("an object descriptor is not a JSON object")
    descriptor = {
        "bytes": item.get("bytes"),
        "content_type": item.get("content_type"),
        "key": item.get("key"),
        "sha256": item.get("sha256"),
    }
    if not isinstance(descriptor["key"], str):
        raise EvidenceError("an object descriptor has no key")
    if (
        not isinstance(descriptor["bytes"], int)
        or isinstance(descriptor["bytes"], bool)
        or descriptor["bytes"] < 0
    ):
        raise EvidenceError(f"object descriptor has invalid bytes: {descriptor['key']}")
    if not isinstance(descriptor["content_type"], str) or not descriptor["content_type"]:
        raise EvidenceError(f"object descriptor has invalid content type: {descriptor['key']}")
    if (
        not isinstance(descriptor["sha256"], str)
        or SHA256_PATTERN.fullmatch(descriptor["sha256"]) is None
    ):
        raise EvidenceError(f"object descriptor has invalid SHA-256: {descriptor['key']}")
    return descriptor


def _exact_rule(name: str, prefix: str) -> dict[str, Any]:
    return {
        "condition": "indefinitely",
        "enabled": True,
        "name": name,
        "prefix": prefix,
    }


def verify(evidence_path: Path, plan_path: Path, revision: str, bucket: str) -> dict[str, Any]:
    if SHA256_PATTERN.fullmatch(revision) is None:
        raise EvidenceError("expected revision is not a lowercase SHA-256")
    evidence, _evidence_raw = _strict_json(evidence_path)
    plan, plan_raw = _strict_json(plan_path)
    if not isinstance(evidence, dict) or not isinstance(plan, dict):
        raise EvidenceError("evidence and plan must be JSON objects")
    if plan.get("revision") != revision:
        raise EvidenceError("R2 plan revision does not match the deployment revision")
    plan_items = plan.get("items")
    if not isinstance(plan_items, list):
        raise EvidenceError("R2 plan has no items array")
    immutable = []
    for item in plan_items:
        if not isinstance(item, dict):
            raise EvidenceError("R2 plan contains a non-object item")
        if item.get("immutable") is True:
            immutable.append(_descriptor(item))
    if not immutable:
        raise EvidenceError("R2 plan has no immutable items")

    plan_sha256 = hashlib.sha256(plan_raw).hexdigest()
    expected_snapshot_key = f"snapshots/{revision}/registry.json"
    expected_targets = [
        item
        for item in immutable
        if item["key"] in CONTRACT_KEYS or item["key"] == expected_snapshot_key
    ]
    if {item["key"] for item in expected_targets if item["key"] in CONTRACT_KEYS} != CONTRACT_KEYS:
        raise EvidenceError("R2 plan does not contain the exact twelve v0.2 contract files")
    if sum(item["key"] == expected_snapshot_key for item in expected_targets) != 1:
        raise EvidenceError("R2 plan does not contain the exact revision snapshot")
    unexpected_targets = [
        item["key"]
        for item in immutable
        if item["key"].startswith(("v0.2/", "profiles/v0.2/", f"snapshots/{revision}/"))
        and item["key"] not in CONTRACT_KEYS
        and item["key"] != expected_snapshot_key
    ]
    if unexpected_targets:
        raise EvidenceError(
            f"R2 plan contains unexpected target-prefix objects: {unexpected_targets}"
        )

    snapshot_rule = f"snapshot-{revision[:16]}"
    target_rules = {
        "schema": _exact_rule("schema-v0.2", "v0.2/"),
        "profile": _exact_rule("profile-v0.2", "profiles/v0.2/"),
        "snapshot": _exact_rule(snapshot_rule, f"snapshots/{revision}/"),
    }
    if evidence.get("document_type") != "neuralstock-r2-release-lock-readback":
        raise EvidenceError("unexpected evidence document type")
    if evidence.get("bucket") != bucket:
        raise EvidenceError("evidence bucket does not match the deployment bucket")
    if evidence.get("registry_revision") != revision:
        raise EvidenceError("evidence revision does not match the deployment revision")
    if evidence.get("mode") != "already-present" or evidence.get("created_rules") != []:
        raise EvidenceError("Phase B requires an independent check-only readback")
    if evidence.get("release_plan_sha256") != plan_sha256:
        raise EvidenceError("evidence is not bound to the reproduced R2 plan")
    if evidence.get("rules") != target_rules:
        raise EvidenceError("evidence does not contain the three exact target rules")

    verification = evidence.get("verification")
    if not isinstance(verification, dict):
        raise EvidenceError("evidence has no verification summary")
    if verification.get("candidate_plan_and_files") is not True:
        raise EvidenceError("evidence did not verify candidate files")
    if verification.get("public_v0_2_contract_bytes") is not True:
        raise EvidenceError("evidence did not verify public v0.2 contract bytes")
    if verification.get("direct_r2_immutable_items") != len(immutable):
        raise EvidenceError("evidence direct-R2 item count differs from the plan")

    direct = evidence.get("direct_r2_immutable_evidence")
    if not isinstance(direct, list) or [_descriptor(item) for item in direct] != immutable:
        raise EvidenceError("direct-R2 evidence does not exactly match every immutable plan item")
    post_lock = evidence.get("direct_r2_post_lock_target_evidence")
    if (
        not isinstance(post_lock, list)
        or [_descriptor(item) for item in post_lock] != expected_targets
    ):
        raise EvidenceError("post-lock evidence does not exactly match all target objects")

    all_rules = evidence.get("all_rules")
    if not isinstance(all_rules, list) or not all(isinstance(rule, dict) for rule in all_rules):
        raise EvidenceError("evidence has no complete lock-rule readback")
    required_rules = {
        **HISTORICAL_RULES,
        "schema-v0.2": "v0.2/",
        "profile-v0.2": "profiles/v0.2/",
        snapshot_rule: f"snapshots/{revision}/",
    }
    for name, prefix in required_rules.items():
        matches = [rule for rule in all_rules if rule == _exact_rule(name, prefix)]
        if len(matches) != 1:
            raise EvidenceError(f"evidence lacks one exact required lock rule: {name}")
        if sum(rule.get("name") == name for rule in all_rules) != 1:
            raise EvidenceError(f"evidence contains a duplicate required rule name: {name}")
        if sum(rule.get("prefix") == prefix for rule in all_rules) != 1:
            raise EvidenceError(f"evidence contains a duplicate required rule prefix: {prefix}")
    for rule in all_rules:
        if rule.get("enabled") is not True or rule.get("condition") != "indefinitely":
            continue
        prefix = rule.get("prefix")
        if not isinstance(prefix, str):
            raise EvidenceError("an enabled indefinite rule has no string prefix")
        if prefix in {"", "(all prefixes)"} or any(
            alias.startswith(prefix) for alias in MUTABLE_ALIASES
        ):
            raise EvidenceError("evidence contains an indefinite rule covering a mutable alias")

    return {
        "bucket": bucket,
        "immutable_items": len(immutable),
        "plan_sha256": plan_sha256,
        "registry_revision": revision,
        "rules_verified": len(required_rules),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("revision")
    parser.add_argument("bucket")
    arguments = parser.parse_args()
    try:
        result = verify(arguments.evidence, arguments.plan, arguments.revision, arguments.bucket)
    except (EvidenceError, KeyError, OSError, TypeError, ValueError) as error:
        print(f"release-lock evidence rejected: {error}", file=sys.stderr)
        return 65
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
