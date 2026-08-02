from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ZONE_ID = "a" * 32


FAKE_CURL = r"""#!/usr/bin/env python3
import json
import os
import sys
import urllib.parse

arguments = sys.argv[1:]
method = "GET"
output = None
payload_path = None
url = None
index = 0
while index < len(arguments):
    argument = arguments[index]
    if argument == "--request":
        method = arguments[index + 1]
        index += 2
    elif argument in {"--header", "--output", "--write-out", "--retry"}:
        if argument == "--output":
            output = arguments[index + 1]
        index += 2
    elif argument == "--data-binary":
        payload_path = arguments[index + 1].removeprefix("@")
        index += 2
    elif argument in {"--silent", "--show-error", "--retry-all-errors"}:
        index += 1
    elif argument.startswith("http"):
        url = argument
        index += 1
    else:
        raise SystemExit(f"unexpected curl argument: {argument}")

if output is None or url is None:
    raise SystemExit("fake curl did not receive output and URL")
state_path = os.environ["FAKE_CLOUDFLARE_STATE"]
with open(state_path, encoding="utf-8") as handle:
    state = json.load(handle)
path = urllib.parse.urlsplit(url).path
zone_root = f"/client/v4/zones/{'a' * 32}"
phase_path = zone_root + "/rulesets/phases/http_request_dynamic_redirect/entrypoint"
ruleset_path = zone_root + "/rulesets/ruleset-id"
status = 200

if method == "GET" and path == zone_root:
    response = {
        "success": True,
        "result": {"name": "neuralstock.ai", "status": "active"},
    }
elif method == "GET" and path == phase_path:
    if state["phase_exists"]:
        response = {
            "success": True,
            "result": {"id": "ruleset-id", "rules": state["rules"]},
        }
    else:
        status = 404
        response = {"success": False, "errors": [{"message": "not found"}]}
elif method == "POST" and path == zone_root + "/rulesets":
    with open(payload_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    rule = payload["rules"][0]
    rule["id"] = "rule-id"
    state["phase_exists"] = True
    state["rules"] = [rule]
    state["last_mutation"] = "create-phase"
    response = {"success": True, "result": {"id": "ruleset-id", "rules": [rule]}}
elif method == "POST" and path == ruleset_path + "/rules":
    with open(payload_path, encoding="utf-8") as handle:
        rule = json.load(handle)
    rule["id"] = "rule-id"
    state["rules"].append(rule)
    state["last_mutation"] = "add-rule"
    response = {"success": True, "result": rule}
elif method == "PATCH" and path == ruleset_path + "/rules/rule-id":
    with open(payload_path, encoding="utf-8") as handle:
        rule = json.load(handle)
    rule["id"] = "rule-id"
    state["rules"] = [rule]
    state["last_mutation"] = "update-rule"
    response = {"success": True, "result": rule}
else:
    status = 500
    response = {
        "success": False,
        "errors": [{"message": f"unexpected request: {method} {path}"}],
    }

with open(state_path, "w", encoding="utf-8") as handle:
    json.dump(state, handle)
with open(output, "w", encoding="utf-8") as handle:
    json.dump(response, handle)
sys.stdout.write(str(status))
"""


def _existing_rule() -> dict[str, object]:
    return {
        "ref": "neuralstock_www_to_apex",
        "id": "rule-id",
        "enabled": True,
        "action": "redirect",
        "expression": 'http.host eq "www.neuralstock.ai"',
        "action_parameters": {
            "from_value": {
                "target_url": {
                    "expression": 'concat("https://wrong.example", http.request.uri.path)'
                },
                "status_code": 302,
                "preserve_query_string": False,
            }
        },
    }


def _dashboard_rule() -> dict[str, object]:
    rule = _existing_rule()
    rule["ref"] = "dashboard-generated-ref"
    rule["expression"] = '(http.host eq "www.neuralstock.ai")'
    return rule


def _managed_rule() -> dict[str, object]:
    rule = _existing_rule()
    rule["action_parameters"] = {
        "from_value": {
            "target_url": {"expression": 'concat("https://neuralstock.ai", http.request.uri.path)'},
            "status_code": 301,
            "preserve_query_string": True,
        }
    }
    return rule


@pytest.mark.parametrize(
    ("phase_exists", "rules", "expected_mutation"),
    [
        (False, [], "create-phase"),
        (True, [], "add-rule"),
        (True, [_existing_rule()], "update-rule"),
        (True, [_dashboard_rule()], "update-rule"),
        (True, [_managed_rule()], None),
    ],
)
def test_redirect_reconciler_creates_or_updates_only_its_stable_rule(
    tmp_path: Path,
    phase_exists: bool,
    rules: list[dict[str, object]],
    expected_mutation: str | None,
) -> None:
    binary_root = tmp_path / "bin"
    binary_root.mkdir()
    fake_curl = binary_root / "curl"
    fake_curl.write_text(textwrap.dedent(FAKE_CURL))
    fake_curl.chmod(0o755)
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"phase_exists": phase_exists, "rules": rules}))
    environment = {
        **os.environ,
        "PATH": f"{binary_root}{os.pathsep}{os.environ['PATH']}",
        "CLOUDFLARE_REDIRECT_API_TOKEN": "test-token",
        "NEURALSTOCK_CLOUDFLARE_ZONE_ID": ZONE_ID,
        "FAKE_CLOUDFLARE_STATE": str(state_path),
    }

    completed = subprocess.run(
        ["sh", str(ROOT / "tools/configure-cloudflare-www-redirect.sh")],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Verified Cloudflare zone rule" in completed.stdout
    state = json.loads(state_path.read_text())
    assert state.get("last_mutation") == expected_mutation
    assert len(state["rules"]) == 1
    rule = state["rules"][0]
    assert rule["ref"] == "neuralstock_www_to_apex"
    assert rule["expression"] == 'http.host eq "www.neuralstock.ai"'
    assert rule["action_parameters"]["from_value"] == {
        "target_url": {"expression": 'concat("https://neuralstock.ai", http.request.uri.path)'},
        "status_code": 301,
        "preserve_query_string": True,
    }
