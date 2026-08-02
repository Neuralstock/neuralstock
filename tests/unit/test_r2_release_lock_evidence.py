from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REVISION = "c" * 64
HISTORICAL_RULES = {
    "immutable-manifests": "assets/",
    "immutable-objects": "objects/sha256/",
    "schema-v0.1": "v0.1/",
    "profile-v0.1": "profiles/v0.1/",
    "room-zero-snapshot": (
        "snapshots/a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523/"
    ),
}
CONTRACT_KEYS = (
    *(
        f"v0.2/{name}"
        for name in (
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
    ),
    "v0.2/LICENSE",
    "profiles/v0.2/web-v1.json",
    "profiles/v0.2/LICENSE",
)


def _descriptor(key: str) -> dict[str, Any]:
    body = f"body:{key}".encode()
    return {
        "bytes": len(body),
        "content_type": "application/json",
        "key": key,
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def _rule(name: str, prefix: str) -> dict[str, Any]:
    return {"condition": "indefinitely", "enabled": True, "name": name, "prefix": prefix}


def _fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot_key = f"snapshots/{REVISION}/registry.json"
    immutable = [
        *(_descriptor(key) for key in CONTRACT_KEYS),
        _descriptor("objects/sha256/aa/" + "a" * 64),
        _descriptor(snapshot_key),
    ]
    plan = {
        "items": [
            *({**item, "immutable": True} for item in immutable),
            {**_descriptor("registry.json"), "immutable": False},
            {**_descriptor("snapshots/latest.json"), "immutable": False},
        ],
        "revision": REVISION,
    }
    plan_raw = (json.dumps(plan, sort_keys=True) + "\n").encode()
    snapshot_rule = f"snapshot-{REVISION[:16]}"
    target_rules = {
        "schema": _rule("schema-v0.2", "v0.2/"),
        "profile": _rule("profile-v0.2", "profiles/v0.2/"),
        "snapshot": _rule(snapshot_rule, f"snapshots/{REVISION}/"),
    }
    all_rules = [
        *(_rule(name, prefix) for name, prefix in HISTORICAL_RULES.items()),
        *target_rules.values(),
    ]
    targets = [
        item for item in immutable if item["key"] in CONTRACT_KEYS or item["key"] == snapshot_key
    ]
    evidence = {
        "document_type": "neuralstock-r2-release-lock-readback",
        "bucket": "neuralstock-public",
        "registry_revision": REVISION,
        "mode": "already-present",
        "created_rules": [],
        "release_plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
        "verification": {
            "candidate_plan_and_files": True,
            "public_v0_2_contract_bytes": True,
            "direct_r2_immutable_items": len(immutable),
        },
        "rules": target_rules,
        "direct_r2_immutable_evidence": immutable,
        "direct_r2_post_lock_target_evidence": targets,
        "all_rules": all_rules,
    }
    return plan, evidence


def _run(
    tmp_path: Path, plan: dict[str, Any], evidence: dict[str, Any]
) -> subprocess.CompletedProcess[str]:
    plan_path = tmp_path / "plan.json"
    evidence_path = tmp_path / "evidence.json"
    plan_path.write_text(json.dumps(plan, sort_keys=True) + "\n")
    evidence_path.write_text(json.dumps(evidence))
    return subprocess.run(
        [
            "python3",
            str(ROOT / "tools/verify-r2-release-lock-evidence.py"),
            str(evidence_path),
            str(plan_path),
            REVISION,
            "neuralstock-public",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_verifier_accepts_candidate_bound_independent_readback(tmp_path: Path) -> None:
    plan, evidence = _fixture()

    completed = _run(tmp_path, plan, evidence)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["rules_verified"] == 8


def test_verifier_rejects_evidence_bound_to_another_plan(tmp_path: Path) -> None:
    plan, evidence = _fixture()
    evidence["release_plan_sha256"] = "0" * 64

    completed = _run(tmp_path, plan, evidence)

    assert completed.returncode == 65
    assert "not bound to the reproduced R2 plan" in completed.stderr


def test_verifier_rejects_a_missing_historical_lock(tmp_path: Path) -> None:
    plan, evidence = _fixture()
    evidence["all_rules"] = evidence["all_rules"][1:]

    completed = _run(tmp_path, plan, evidence)

    assert completed.returncode == 65
    assert "immutable-manifests" in completed.stderr


def test_verifier_rejects_a_duplicate_required_rule_name(tmp_path: Path) -> None:
    plan, evidence = _fixture()
    evidence["all_rules"].append(_rule("schema-v0.2", "other/"))

    completed = _run(tmp_path, plan, evidence)

    assert completed.returncode == 65
    assert "duplicate required rule name" in completed.stderr


def test_verifier_rejects_a_rule_covering_mutable_aliases(tmp_path: Path) -> None:
    plan, evidence = _fixture()
    changed = copy.deepcopy(evidence)
    changed["all_rules"].append(_rule("unsafe", "snapshots/"))

    completed = _run(tmp_path, plan, changed)

    assert completed.returncode == 65
    assert "covering a mutable alias" in completed.stderr


def test_verifier_rejects_a_negative_object_size(tmp_path: Path) -> None:
    plan, evidence = _fixture()
    evidence["direct_r2_immutable_evidence"][0]["bytes"] = -1

    completed = _run(tmp_path, plan, evidence)

    assert completed.returncode == 65
    assert "invalid bytes" in completed.stderr


def test_workflow_retrieves_real_evidence_and_rejects_zero_placeholder() -> None:
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text()

    assert 'gh release download "v$RELEASE_VERSION"' in workflow
    assert "tools/verify-r2-release-lock-evidence.py" in workflow
    assert "0000000000000000000000000000000000000000000000000000000000000000" in workflow
