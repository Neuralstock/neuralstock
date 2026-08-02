from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "tools" / "verify-github-release-state.py"
VERSION = "0.1.0"
REVISION = "7" * 64
SOURCE_COMMIT = "a" * 40


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path, *, state: str = "draft") -> tuple[Path, Path, str]:
    assets = tmp_path / "assets"
    assets.mkdir()
    evidence_name = f"neuralstock-r2-release-lock-{REVISION}.json"
    payloads = {
        "SHA256SUMS": b"checksums\n",
        f"neuralstock-release-{VERSION}.tar.gz": b"archive\n",
        "r2-plan.json": b'{"items":[],"revision":"' + REVISION.encode() + b'"}\n',
        "release-metadata.json": json.dumps(
            {
                "package_version": VERSION,
                "registry_revision": REVISION,
                "release_archive": f"neuralstock-release-{VERSION}.tar.gz",
                "release_tag": f"v{VERSION}",
                "release_version": VERSION,
                "source_commit": SOURCE_COMMIT,
            }
        ).encode(),
        "worker-image-metadata.json": b"{}\n",
        evidence_name: b'{"mode":"already-present"}\n',
    }
    for name, payload in payloads.items():
        (assets / name).write_bytes(payload)
    release = {
        "assets": [
            {
                "digest": f"sha256:{_sha256(assets / name)}",
                "id": index,
                "name": name,
                "size": (assets / name).stat().st_size,
                "state": "uploaded",
            }
            for index, name in enumerate(sorted(payloads), 1)
        ],
        "draft": state == "draft",
        "id": 42,
        "immutable": state == "immutable",
        "name": f"NeuralStock {VERSION}",
        "prerelease": False,
        "published_at": None if state == "draft" else "2026-08-01T21:00:00Z",
        "tag_name": f"v{VERSION}",
    }
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(release))
    return release_path, assets, _sha256(assets / evidence_name)


def _run(
    release_path: Path,
    assets: Path,
    evidence_sha256: str,
    *,
    state: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(release_path),
            str(assets),
            VERSION,
            REVISION,
            SOURCE_COMMIT,
            evidence_sha256,
            "--state",
            state,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_accepts_exact_draft_asset_set(tmp_path: Path) -> None:
    release_path, assets, evidence_sha256 = _fixture(tmp_path)

    result = _run(release_path, assets, evidence_sha256, state="draft")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["assets"] == 6


def test_retry_accepts_exact_already_immutable_release(tmp_path: Path) -> None:
    release_path, assets, evidence_sha256 = _fixture(tmp_path, state="immutable")

    result = _run(release_path, assets, evidence_sha256, state="immutable")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "immutable"


def test_retry_rejects_published_mutable_release(tmp_path: Path) -> None:
    release_path, assets, evidence_sha256 = _fixture(tmp_path, state="published-mutable")

    result = _run(release_path, assets, evidence_sha256, state="immutable")

    assert result.returncode == 65
    assert "not published and immutable" in result.stderr


def test_workflows_preserve_retry_and_release_boundary_guards() -> None:
    release_workflow = (ROOT / ".github/workflows/release.yml").read_text()
    finalize_workflow = (ROOT / ".github/workflows/finalize-release.yml").read_text()
    deploy_workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
    shared_group = "group: release-boundary-${{ inputs.version }}"

    assert shared_group in release_workflow
    assert shared_group in finalize_workflow
    assert "release_mode=immutable-recovery" in finalize_workflow
    assert "release_commit:" in finalize_workflow
    assert 'tools/verify-release-tag.sh "$RELEASE_VERSION" "$RELEASE_COMMIT"' in finalize_workflow
    assert 'test "$GITHUB_SHA" = "$controller_main"' in finalize_workflow
    assert 'test "$GITHUB_SHA" = "$RELEASE_COMMIT"' in finalize_workflow
    assert 'test "$RELEASE_COMMIT" = "$controller_main"' in finalize_workflow
    assert '--source-ref "refs/tags/v$RELEASE_VERSION"' in finalize_workflow
    assert '--source-digest "$RELEASE_COMMIT"' in finalize_workflow
    assert "attestations: read" in deploy_workflow
    assert "id: release_source" in deploy_workflow
    assert 'tools/verify-release-tag.sh "$RELEASE_VERSION" "$release_commit"' in deploy_workflow
    assert 'test "$GITHUB_SHA" = "$controller_main"' in deploy_workflow
    assert 'test "$GITHUB_SHA" = "$release_commit"' in deploy_workflow
    assert 'test "$run_sha" = "$RELEASE_COMMIT"' in deploy_workflow
    assert "steps.release_source.outputs.commit" in deploy_workflow
    assert "jq -r .source_commit dist/release-candidate/release-metadata.json" in deploy_workflow

    step_start = finalize_workflow.index(
        "- name: Re-verify and publish the draft or recover immutable state"
    )
    step_end = finalize_workflow.index(
        "- name: Verify immutable state and GitHub release attestation", step_start
    )
    publish_step = finalize_workflow[step_start:step_end]
    draft_refetch = publish_step.index(">dist-prepublish-release.json")
    draft_verify = publish_step.index("--state draft", draft_refetch)
    tag_check = publish_step.index("tools/verify-release-tag.sh", draft_verify)
    controller_recheck = publish_step.index('test "$GITHUB_SHA" = "$controller_main"', tag_check)
    publication = publish_step.index("--method PATCH", controller_recheck)

    assert draft_refetch < draft_verify < tag_check < controller_recheck < publication
    assert publish_step.index("immutable-recovery)") > publication
    assert publish_step.index("--state immutable") > publication


def test_rejects_an_extra_release_asset(tmp_path: Path) -> None:
    release_path, assets, evidence_sha256 = _fixture(tmp_path)
    extra = assets / "unexpected.txt"
    extra.write_text("unexpected\n")

    result = _run(release_path, assets, evidence_sha256, state="draft")

    assert result.returncode == 65
    assert "exact expected set" in result.stderr


def test_rejects_remote_digest_that_differs_from_download(tmp_path: Path) -> None:
    release_path, assets, evidence_sha256 = _fixture(tmp_path)
    release = json.loads(release_path.read_text())
    release["assets"][0]["digest"] = f"sha256:{'0' * 64}"
    release_path.write_text(json.dumps(release))

    result = _run(release_path, assets, evidence_sha256, state="draft")

    assert result.returncode == 65
    assert "digest differs locally" in result.stderr
