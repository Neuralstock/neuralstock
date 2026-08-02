from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_REVISION = "a3e851194d092bf1a06452a62ae98ba8687462ea0cbca668a9b9cc2385768523"
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
CONTRACT_KEYS = (
    *(f"v0.2/{name}" for name in SCHEMA_NAMES),
    "v0.2/LICENSE",
    "profiles/v0.2/web-v1.json",
    "profiles/v0.2/LICENSE",
)
NEW_PAYLOAD = {
    "generated_at": "2026-08-01T00:00:00Z",
    "profiles": ["web-v1"],
    "entries": [],
    "aliases": [],
    "withdrawals": [],
}
NEW_REVISION = hashlib.sha256(
    json.dumps(
        NEW_PAYLOAD,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
).hexdigest()
NEW_SNAPSHOT = json.dumps({"revision": NEW_REVISION, **NEW_PAYLOAD}, indent=2) + "\n"

BASELINE_RULES = [
    {
        "name": "immutable-manifests",
        "enabled": "Yes",
        "prefix": "assets/",
        "condition": "indefinitely",
    },
    {
        "name": "immutable-objects",
        "enabled": "Yes",
        "prefix": "objects/sha256/",
        "condition": "indefinitely",
    },
    {
        "name": "profile-v0.1",
        "enabled": "Yes",
        "prefix": "profiles/v0.1/",
        "condition": "indefinitely",
    },
    {
        "name": "room-zero-snapshot",
        "enabled": "Yes",
        "prefix": f"snapshots/{HISTORICAL_REVISION}/",
        "condition": "indefinitely",
    },
    {
        "name": "schema-v0.1",
        "enabled": "Yes",
        "prefix": "v0.1/",
        "condition": "indefinitely",
    },
]

TARGET_RULES = [
    {
        "name": "schema-v0.2",
        "enabled": "Yes",
        "prefix": "v0.2/",
        "condition": "indefinitely",
    },
    {
        "name": "profile-v0.2",
        "enabled": "Yes",
        "prefix": "profiles/v0.2/",
        "condition": "indefinitely",
    },
    {
        "name": f"snapshot-{NEW_REVISION[:16]}",
        "enabled": "Yes",
        "prefix": f"snapshots/{NEW_REVISION}/",
        "condition": "indefinitely",
    },
]

FAKE_PNPM = r"""#!/usr/bin/env python3
import json
import os
import sys

arguments = sys.argv[1:]
if arguments == ["wrangler", "--version"]:
    print("4.118.0")
    raise SystemExit(0)

state_path = os.environ["FAKE_LOCK_STATE"]
with open(state_path, encoding="utf-8") as handle:
    state = json.load(handle)

if arguments == ["wrangler", "r2", "bucket", "lock", "list", "neuralstock-public"]:
    for rule in state["rules"]:
        print(f"name:       {rule['name']}")
        print(f"enabled:    {rule['enabled']}")
        print(f"prefix:     {rule['prefix']}")
        print(f"condition:  {rule['condition']}")
        print()
    raise SystemExit(0)

if (
    len(arguments) == 8
    and arguments[:4] == ["wrangler", "r2", "object", "get"]
    and arguments[5] == "--file"
    and arguments[7] == "--remote"
):
    bucket_and_key = arguments[4]
    bucket_prefix = "neuralstock-public/"
    if not bucket_and_key.startswith(bucket_prefix):
        raise SystemExit(f"unexpected bucket: {bucket_and_key}")
    key = bucket_and_key[len(bucket_prefix):]
    body = state["objects"].get(key)
    if body is None:
        raise SystemExit(f"missing fake object: {key}")
    with open(arguments[6], "w", encoding="utf-8") as handle:
        handle.write(body)
    state["events"].append(f"get:{key}")
    with open(state_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    print(f"Downloaded {key}")
    raise SystemExit(0)

expected_prefix = ["wrangler", "r2", "bucket", "lock", "add", "neuralstock-public"]
if arguments[:6] == expected_prefix and arguments[-2:] == ["--retention-indefinite", "--force"]:
    state["rules"].append(
        {
            "name": arguments[6],
            "enabled": "Yes",
            "prefix": arguments[7],
            "condition": "indefinitely",
        }
    )
    state["events"].append(f"add:{arguments[6]}")
    with open(state_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    print(f"Added lock rule {arguments[6]}")
    raise SystemExit(0)

raise SystemExit(f"unexpected pnpm invocation: {arguments!r}")
"""

FAKE_UV = r"""#!/usr/bin/env python3
import os
import sys

expected = ["run", "--frozen", "neuralstock", "r2", "plan", "--root"]
if sys.argv[1:7] != expected or len(sys.argv) != 8:
    raise SystemExit(f"unexpected uv invocation: {sys.argv[1:]!r}")
with open(os.environ["FAKE_PLAN_PATH"], encoding="utf-8") as handle:
    print(handle.read(), end="")
"""


def _item(key: str, body: str, content_type: str, *, immutable: bool) -> dict[str, Any]:
    encoded = body.encode()
    return {
        "bytes": len(encoded),
        "content_type": content_type,
        "immutable": immutable,
        "key": key,
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


@pytest.fixture
def gate_project(tmp_path: Path) -> tuple[Path, dict[str, str], Path, Path]:
    tools = tmp_path / "tools"
    tools.mkdir()
    gate = tools / "manage-r2-release-lock.sh"
    shutil.copy2(ROOT / "tools/manage-r2-release-lock.sh", gate)
    shutil.copy2(ROOT / "tools/manage-r2-release-lock.py", tools)
    marker = tmp_path / "contract-origin-verified"
    (tools / "verify-contract-origin.sh").write_text(
        '#!/bin/sh\nset -eu\nprintf "%s" "$1" >"$LOCK_VERIFY_MARKER"\n'
    )
    (tmp_path / "package.json").write_text(json.dumps({"devDependencies": {"wrangler": "4.118.0"}}))

    release_root = tmp_path / "release"
    bodies = {key: f"fixture for {key}\n" for key in CONTRACT_KEYS}
    object_body = "content-addressed immutable object\n"
    object_digest = hashlib.sha256(object_body.encode()).hexdigest()
    object_key = f"objects/sha256/{object_digest[:2]}/{object_digest}"
    bodies[object_key] = object_body
    manifest_key = "assets/fixture/1.0.0/asset.json"
    bodies[manifest_key] = '{"id":"fixture"}\n'
    snapshot_key = f"snapshots/{NEW_REVISION}/registry.json"
    bodies[snapshot_key] = NEW_SNAPSHOT
    bodies["registry.json"] = NEW_SNAPSHOT
    bodies["snapshots/latest.json"] = NEW_SNAPSHOT
    for key, body in bodies.items():
        path = release_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    items = [
        *[
            _item(
                key,
                bodies[key],
                "text/plain" if key.endswith("LICENSE") else "application/json",
                immutable=True,
            )
            for key in CONTRACT_KEYS
        ],
        _item(object_key, object_body, "application/octet-stream", immutable=True),
        _item(manifest_key, bodies[manifest_key], "application/json", immutable=True),
        _item(snapshot_key, NEW_SNAPSHOT, "application/json", immutable=True),
        _item("registry.json", NEW_SNAPSHOT, "application/json", immutable=False),
        _item("snapshots/latest.json", NEW_SNAPSHOT, "application/json", immutable=False),
    ]
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"items": items, "revision": NEW_REVISION}))

    binary_root = tmp_path / "bin"
    binary_root.mkdir()
    for name, source in (("pnpm", FAKE_PNPM), ("uv", FAKE_UV)):
        binary = binary_root / name
        binary.write_text(textwrap.dedent(source))
        binary.chmod(0o755)
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "events": [],
                "objects": {key: body for key, body in bodies.items() if key not in MUTABLE_KEYS},
                "rules": BASELINE_RULES,
            }
        )
    )
    environment = {
        **os.environ,
        "PATH": f"{binary_root}{os.pathsep}{os.environ['PATH']}",
        "FAKE_LOCK_STATE": str(state_path),
        "FAKE_PLAN_PATH": str(plan_path),
        "LOCK_VERIFY_MARKER": str(marker),
    }
    for name in (
        "CI",
        "CLOUDFLARE_API_TOKEN",
        "CF_API_TOKEN",
        "CLOUDFLARE_API_KEY",
        "CLOUDFLARE_API_USER_SERVICE_KEY",
        "WRANGLER_CF_AUTHORIZATION_TOKEN",
    ):
        environment.pop(name, None)
    return gate, environment, marker, release_root


MUTABLE_KEYS = {"registry.json", "snapshots/latest.json"}


def _run_gate(
    gate: Path,
    environment: dict[str, str],
    release_root: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "sh",
            str(gate),
            NEW_REVISION,
            "--release-root",
            str(release_root),
            *arguments,
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _state(environment: dict[str, str]) -> dict[str, Any]:
    return json.loads(Path(environment["FAKE_LOCK_STATE"]).read_text())


def _write_state(environment: dict[str, str], state: dict[str, Any]) -> None:
    Path(environment["FAKE_LOCK_STATE"]).write_text(json.dumps(state))


def test_apply_verifies_staged_graph_adds_three_exact_locks_and_emits_evidence(
    gate_project: tuple[Path, dict[str, str], Path, Path],
) -> None:
    gate, environment, marker, release_root = gate_project

    completed = _run_gate(gate, environment, release_root, "--apply")

    assert completed.returncode == 0, completed.stderr
    evidence = json.loads(completed.stdout)
    assert evidence["mode"] == "created"
    assert evidence["created_rules"] == [rule["name"] for rule in TARGET_RULES]
    assert evidence["rules"] == {
        "schema": {
            "name": "schema-v0.2",
            "enabled": True,
            "prefix": "v0.2/",
            "condition": "indefinitely",
        },
        "profile": {
            "name": "profile-v0.2",
            "enabled": True,
            "prefix": "profiles/v0.2/",
            "condition": "indefinitely",
        },
        "snapshot": {
            "name": f"snapshot-{NEW_REVISION[:16]}",
            "enabled": True,
            "prefix": f"snapshots/{NEW_REVISION}/",
            "condition": "indefinitely",
        },
    }
    assert evidence["verification"]["direct_r2_immutable_items"] == len(CONTRACT_KEYS) + 3
    assert evidence["verification"]["post_lock_target_items"] == len(CONTRACT_KEYS) + 1
    assert evidence["verification"]["target_bytes_unchanged_across_creation"] is True
    assert marker.read_text() == str(release_root)
    state = _state(environment)
    assert {rule["prefix"] for rule in TARGET_RULES} <= {rule["prefix"] for rule in state["rules"]}
    first_add = next(
        index for index, event in enumerate(state["events"]) if event.startswith("add:")
    )
    assert all(event.startswith("get:") for event in state["events"][:first_add])


def test_check_accepts_existing_exact_rules_without_mutation(
    gate_project: tuple[Path, dict[str, str], Path, Path],
) -> None:
    gate, environment, marker, release_root = gate_project
    state = _state(environment)
    state["rules"].extend(TARGET_RULES)
    _write_state(environment, state)

    completed = _run_gate(gate, environment, release_root)

    assert completed.returncode == 0, completed.stderr
    evidence = json.loads(completed.stdout)
    assert evidence["mode"] == "already-present"
    assert evidence["created_rules"] == []
    assert evidence["verification"]["pre_post_target_comparison_performed"] is False
    assert evidence["verification"]["target_bytes_unchanged_across_creation"] is None
    assert not any(event.startswith("add:") for event in _state(environment)["events"])
    assert marker.exists()


def test_check_rejects_a_noncanonical_target_rule_name(
    gate_project: tuple[Path, dict[str, str], Path, Path],
) -> None:
    gate, environment, _marker, release_root = gate_project
    state = _state(environment)
    state["rules"].extend(TARGET_RULES)
    state["rules"][-1]["name"] = "dashboard-snapshot"
    _write_state(environment, state)

    completed = _run_gate(gate, environment, release_root)

    assert completed.returncode == 65
    assert "uses rule name 'dashboard-snapshot'" in completed.stderr


def test_check_fails_closed_when_release_locks_are_missing(
    gate_project: tuple[Path, dict[str, str], Path, Path],
) -> None:
    gate, environment, _marker, release_root = gate_project

    completed = _run_gate(gate, environment, release_root)

    assert completed.returncode == 65
    assert "release locks are missing for schema, profile, snapshot" in completed.stderr
    assert len(_state(environment)["rules"]) == len(BASELINE_RULES)


def test_apply_is_idempotent_after_a_partial_manual_attempt(
    gate_project: tuple[Path, dict[str, str], Path, Path],
) -> None:
    gate, environment, _marker, release_root = gate_project
    state = _state(environment)
    state["rules"].append(TARGET_RULES[0])
    _write_state(environment, state)

    completed = _run_gate(gate, environment, release_root, "--apply")

    assert completed.returncode == 0, completed.stderr
    evidence = json.loads(completed.stdout)
    assert evidence["created_rules"] == ["profile-v0.2", f"snapshot-{NEW_REVISION[:16]}"]
    assert sum(rule["prefix"] == "v0.2/" for rule in _state(environment)["rules"]) == 1


def test_gate_rejects_an_indefinite_rule_covering_mutable_latest_alias(
    gate_project: tuple[Path, dict[str, str], Path, Path],
) -> None:
    gate, environment, _marker, release_root = gate_project
    state = _state(environment)
    state["rules"].append(
        {
            "name": "unsafe-all-snapshots",
            "enabled": "Yes",
            "prefix": "snapshots/",
            "condition": "indefinitely",
        }
    )
    _write_state(environment, state)

    completed = _run_gate(gate, environment, release_root, "--apply")

    assert completed.returncode == 65
    assert "would cover a mutable alias" in completed.stderr
    assert not any(event.startswith("add:") for event in _state(environment)["events"])


def test_gate_fails_before_locking_when_direct_r2_bytes_differ(
    gate_project: tuple[Path, dict[str, str], Path, Path],
) -> None:
    gate, environment, _marker, release_root = gate_project
    state = _state(environment)
    state["objects"]["v0.2/asset.schema.json"] = "tampered\n"
    _write_state(environment, state)

    completed = _run_gate(gate, environment, release_root, "--apply")

    assert completed.returncode == 65
    assert "direct R2 object differs" in completed.stderr
    assert not any(event.startswith("add:") for event in _state(environment)["events"])


def test_gate_rejects_a_changed_historical_lock(
    gate_project: tuple[Path, dict[str, str], Path, Path],
) -> None:
    gate, environment, _marker, release_root = gate_project
    state = _state(environment)
    state["rules"][0]["prefix"] = "changed/"
    _write_state(environment, state)

    completed = _run_gate(gate, environment, release_root, "--apply")

    assert completed.returncode == 65
    assert "required historical lock immutable-manifests" in completed.stderr
    assert not any(event.startswith("add:") for event in _state(environment)["events"])


@pytest.mark.parametrize(
    "credential_name",
    [
        "CLOUDFLARE_API_TOKEN",
        "CF_API_TOKEN",
        "CLOUDFLARE_API_KEY",
        "CLOUDFLARE_API_USER_SERVICE_KEY",
        "WRANGLER_CF_AUTHORIZATION_TOKEN",
    ],
)
def test_gate_rejects_environment_credentials(
    gate_project: tuple[Path, dict[str, str], Path, Path], credential_name: str
) -> None:
    gate, environment, _marker, release_root = gate_project
    environment[credential_name] = "must-not-be-used"

    completed = _run_gate(gate, environment, release_root, "--apply")

    assert completed.returncode == 65
    assert f"unset {credential_name}" in completed.stderr
