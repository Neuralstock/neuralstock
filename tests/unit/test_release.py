from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from neuralstock.canonical import read_json, sha256_file, sha256_json, write_json_atomic
from neuralstock.package import PackageResult, run_gltf_validator
from neuralstock.registry import build_registry, revision_payload
from neuralstock.release import (
    RELEASE_RUNTIME_GLB_HARD_CAP,
    _release_path,
    canonical_contract_artifacts,
    complete_artifact_descriptors,
    publish_canonical_contract_artifacts,
    publish_release,
    verify_release,
)
from neuralstock.storage import (
    object_key,
    publish_named_immutable,
    publish_object,
    replace_alias,
    snapshot_key,
    version_manifest_key,
)
from tests.unit.test_package import (
    make_candidate,
    make_comparison,
    minimal_glb,
    minimal_png,
    rewrite_output_summary,
    run_package,
)


def _package(tmp_path: Path) -> Path:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    return _run_release_package(candidate, comparison=comparison).output


def _run_release_package(
    candidate: dict[str, Any], *, comparison: Path | None = None
) -> PackageResult:
    report = run_gltf_validator(candidate["blender"] / "model.glb")
    return run_package(candidate, report=report, comparison=comparison)


GraphMutator = Callable[[Path, dict[str, Any], dict[str, Any]], None]


def _artifact_path(root: Path, descriptor: dict[str, Any]) -> Path:
    return root / descriptor["uri"].removeprefix("/")


def _find_output(receipt: dict[str, Any], file_name: str) -> dict[str, Any]:
    matches = [item for item in receipt["outputs"] if item["file_name"] == file_name]
    assert len(matches) == 1
    return matches[0]


def _replace_descriptor_references(
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    old: dict[str, Any],
    new: dict[str, Any],
) -> None:
    artifacts = manifest["artifacts"]
    for key in ("source", "runtime", "provenance", "inspection", "build_receipt"):
        if artifacts[key] == old:
            artifacts[key] = new
    for key in ("previews", "optional"):
        artifacts[key] = [new if item == old else item for item in artifacts.get(key, [])]
    for key in ("inputs", "outputs"):
        receipt[key] = [new if item == old else item for item in receipt[key]]
    if receipt["validation"]["inspection_sha256"] == old["sha256"]:
        receipt["validation"]["inspection_sha256"] = new["sha256"]


def _replace_artifact_bytes(
    package: Path,
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    old: dict[str, Any],
    payload: bytes,
) -> dict[str, Any]:
    scratch = package / "forged" / f"{old['sha256'][:12]}-{old['file_name']}"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_bytes(payload)
    published = publish_object(scratch, package)
    new = {
        **old,
        "sha256": published.digest,
        "bytes": published.size_bytes,
        "uri": f"/{published.key}",
    }
    _replace_descriptor_references(manifest, receipt, old, new)
    return new


def _replace_artifact_document(
    package: Path,
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    old: dict[str, Any],
    document: dict[str, Any],
) -> dict[str, Any]:
    scratch = package / "forged" / f"{old['sha256'][:12]}-{old['file_name']}"
    write_json_atomic(scratch, document)
    return _replace_artifact_bytes(
        package,
        manifest,
        receipt,
        old,
        scratch.read_bytes(),
    )


def _forge_package(package: Path, mutate: GraphMutator) -> dict[str, Any]:
    manifest = deepcopy(read_json(package / "asset.json"))
    receipt_descriptor = manifest["artifacts"]["build_receipt"]
    receipt = deepcopy(read_json(_artifact_path(package, receipt_descriptor)))
    mutate(package, manifest, receipt)

    scratch = package / "forged" / "build-receipt.json"
    write_json_atomic(scratch, receipt)
    published = publish_object(scratch, package)
    manifest["artifacts"]["build_receipt"] = {
        **receipt_descriptor,
        "sha256": published.digest,
        "bytes": published.size_bytes,
        "uri": f"/{published.key}",
    }
    write_json_atomic(package / "asset.json", manifest)
    return manifest


def _publish_without_contract(package: Path, release: Path) -> None:
    """Build a structurally valid release fixture while bypassing publish preflight."""

    publish_canonical_contract_artifacts(release)
    manifest = read_json(package / "asset.json")
    for descriptor in complete_artifact_descriptors(package, manifest):
        publish_object(_artifact_path(package, descriptor), release)
    publish_object(package / "asset.json", release)
    named_manifest = publish_named_immutable(
        package / "asset.json",
        release,
        version_manifest_key(manifest["id"], manifest["version"]),
    )
    registry_source = release.parent / f"{release.name}-registry-source.json"
    registry = build_registry(
        [named_manifest],
        output=registry_source,
        generated_at="2026-08-01T00:00:00Z",
    )
    publish_object(registry_source, release)
    publish_named_immutable(registry_source, release, snapshot_key(registry["revision"]))
    replace_alias(registry_source, release, "registry.json")
    replace_alias(registry_source, release, "snapshots/latest.json")


def test_publish_and_verify_static_release(tmp_path: Path) -> None:
    package = _package(tmp_path)
    release = tmp_path / "release"

    result = publish_release(
        [package],
        root=release,
        generated_at="2026-08-01T00:00:00Z",
    )
    verified = verify_release(release)

    assert result.asset_count == 1
    assert result.object_count == 16
    assert verified.asset_count == 1
    assert verified.artifact_count == 14
    assert (release / snapshot_key(result.revision)).is_file()
    assert (release / "registry.json").read_bytes() == result.snapshot_path.read_bytes()
    assert (release / version_manifest_key("procedural_crate_01", "1.0.0")).is_file()
    contract_keys = {artifact.release_key for artifact in canonical_contract_artifacts()}
    assert "v0.2/discovery.schema.json" in contract_keys
    assert "v0.2/LICENSE" in contract_keys
    assert "profiles/v0.2/web-v1.json" in contract_keys
    assert "profiles/v0.2/LICENSE" in contract_keys
    for artifact in canonical_contract_artifacts():
        assert (release / artifact.release_key).read_bytes() == artifact.source_path.read_bytes()


def test_verify_rejects_changed_canonical_contract_bytes(tmp_path: Path) -> None:
    release = tmp_path / "release"
    publish_release(
        [_package(tmp_path)],
        root=release,
        generated_at="2026-08-01T00:00:00Z",
    )
    contract = next(
        artifact
        for artifact in canonical_contract_artifacts()
        if artifact.release_key == "v0.2/discovery.schema.json"
    )
    (release / contract.release_key).write_bytes(b"tampered discovery contract")

    with pytest.raises(ValueError, match="canonical release contract differs"):
        verify_release(release)


def test_publish_and_verify_known_source_serialization_nondeterminism(
    tmp_path: Path,
) -> None:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    comparison_source = comparison / "source.blend"
    comparison_source.write_bytes(b"same modeled asset with different Blender session data")
    rewrite_output_summary(comparison, "source.blend")
    comparison_inspection_path = comparison / "inspection.json"
    comparison_inspection = read_json(comparison_inspection_path)
    comparison_inspection["source_sha256"] = sha256_file(comparison_source)
    write_json_atomic(comparison_inspection_path, comparison_inspection)
    rewrite_output_summary(comparison, "inspection.json")
    package = _run_release_package(candidate, comparison=comparison).output
    receipt = read_json(package / "build-receipt.json")
    assert receipt["reproducibility"]["status"] == "known-nondeterminism"

    release = tmp_path / "release"
    publish_release(
        [package],
        root=release,
        generated_at="2026-08-01T00:00:00Z",
    )

    assert verify_release(release).asset_count == 1


def test_publish_and_verify_not_yet_reproduced_receipt(tmp_path: Path) -> None:
    package = _run_release_package(make_candidate(tmp_path)).output
    receipt = read_json(package / "build-receipt.json")
    assert receipt["reproducibility"]["status"] == "not-yet-reproduced"

    release = tmp_path / "release"
    publish_release(
        [package],
        root=release,
        generated_at="2026-08-01T00:00:00Z",
    )

    assert verify_release(release).asset_count == 1


def test_publish_and_verify_reproduced_preview_with_different_encoding(
    tmp_path: Path,
) -> None:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    (comparison / "preview.png").write_bytes(minimal_png(comment=b"second encoding"))
    rewrite_output_summary(comparison, "preview.png")
    package = _run_release_package(candidate, comparison=comparison).output
    receipt = read_json(package / "build-receipt.json")
    assert receipt["reproducibility"]["status"] == "reproduced"
    assert len(receipt["reproducibility"]["allowed_nondeterminism"]) == 2

    release = tmp_path / "release"
    publish_release(
        [package],
        root=release,
        generated_at="2026-08-01T00:00:00Z",
    )

    assert verify_release(release).asset_count == 1


def test_publish_refuses_tampered_package_artifact(tmp_path: Path) -> None:
    package = _package(tmp_path)
    manifest = read_json(package / "asset.json")
    runtime = manifest["artifacts"]["runtime"]
    (package / object_key(runtime["sha256"])).write_bytes(b"tampered")

    with pytest.raises(ValueError, match=r"artifact (size|digest) mismatch"):
        publish_release(
            [package],
            root=tmp_path / "release",
            generated_at="2026-08-01T00:00:00Z",
        )


def test_publish_preflights_full_contract_before_discovery_aliases(tmp_path: Path) -> None:
    package = _package(tmp_path)

    def tamper(_package: Path, _manifest: dict[str, Any], receipt: dict[str, Any]) -> None:
        receipt["validation"]["status"] = "fail"

    _forge_package(package, tamper)
    release = tmp_path / "release"

    with pytest.raises(ValueError, match="validation status"):
        publish_release(
            [package],
            root=release,
            generated_at="2026-08-01T00:00:00Z",
        )

    assert not (release / "registry.json").exists()
    assert not (release / "snapshots" / "latest.json").exists()
    assert not (release / version_manifest_key("procedural_crate_01", "1.0.0")).exists()


@pytest.mark.parametrize("surface", ["publish", "verify"])
def test_release_reruns_validator_and_rejects_unresolved_scene_reference(
    tmp_path: Path,
    surface: str,
) -> None:
    package = _run_release_package(make_candidate(tmp_path)).output

    def tamper(
        package: Path,
        manifest: dict[str, Any],
        receipt: dict[str, Any],
    ) -> None:
        runtime = manifest["artifacts"]["runtime"]
        invalid_runtime = minimal_glb({"asset": {"version": "2.0"}, "scene": 1, "scenes": [{}]})
        _replace_artifact_bytes(
            package,
            manifest,
            receipt,
            runtime,
            invalid_runtime,
        )

    _forge_package(package, tamper)
    release = tmp_path / "release"

    if surface == "publish":
        with pytest.raises(ValueError, match="pinned validator re-execution"):
            publish_release(
                [package],
                root=release,
                generated_at="2026-08-01T00:00:00Z",
            )
        assert not (release / "registry.json").exists()
        assert not (release / "snapshots" / "latest.json").exists()
    else:
        _publish_without_contract(package, release)
        with pytest.raises(ValueError, match="pinned validator re-execution"):
            verify_release(release)


def test_release_requires_published_validator_report_to_equal_rerun(
    tmp_path: Path,
) -> None:
    package = _package(tmp_path)

    def tamper(
        package: Path,
        manifest: dict[str, Any],
        receipt: dict[str, Any],
    ) -> None:
        descriptor = _find_output(receipt, "gltf-validation.json")
        report = read_json(_artifact_path(package, descriptor))
        report["info"]["totalVertexCount"] += 1
        _replace_artifact_document(package, manifest, receipt, descriptor, report)

    _forge_package(package, tamper)

    with pytest.raises(ValueError, match="differs from pinned re-execution"):
        publish_release(
            [package],
            root=tmp_path / "release",
            generated_at="2026-08-01T00:00:00Z",
        )


def test_over_budget_runtime_is_rejected_before_validator_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _package(tmp_path)
    manifest = read_json(package / "asset.json")
    runtime_bytes = manifest["artifacts"]["runtime"]["bytes"]
    validator_called = False

    def forbidden_validator(_runtime: Path) -> dict[str, Any]:
        nonlocal validator_called
        validator_called = True
        raise AssertionError("validator must not run for an over-budget runtime")

    monkeypatch.setattr(
        "neuralstock.release.RELEASE_RUNTIME_GLB_HARD_CAP",
        runtime_bytes - 1,
    )
    monkeypatch.setattr("neuralstock.release.run_gltf_validator", forbidden_validator)
    release = tmp_path / "release"

    with pytest.raises(ValueError, match="runtime GLB exceeds target-profile byte budget"):
        publish_release(
            [package],
            root=release,
            generated_at="2026-08-01T00:00:00Z",
        )

    assert validator_called is False
    assert not (release / "registry.json").exists()


def test_forged_higher_profile_cannot_bypass_owned_runtime_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _package(tmp_path)
    oversized_bytes = RELEASE_RUNTIME_GLB_HARD_CAP + 1

    def tamper(
        package: Path,
        manifest: dict[str, Any],
        receipt: dict[str, Any],
    ) -> None:
        runtime = manifest["artifacts"]["runtime"]
        oversized_runtime = b"glTF" + bytes(oversized_bytes - 4)
        _replace_artifact_bytes(
            package,
            manifest,
            receipt,
            runtime,
            oversized_runtime,
        )
        profile_descriptor = next(
            item for item in receipt["inputs"] if item["file_name"] == "profile-web-v1.json"
        )
        profile = read_json(_artifact_path(package, profile_descriptor))
        profile["budgets"]["glb_bytes"] = oversized_bytes
        _replace_artifact_document(
            package,
            manifest,
            receipt,
            profile_descriptor,
            profile,
        )

    _forge_package(package, tamper)
    validator_called = False

    def forbidden_validator(_runtime: Path) -> dict[str, Any]:
        nonlocal validator_called
        validator_called = True
        raise AssertionError("validator must not run with forged profile evidence")

    monkeypatch.setattr("neuralstock.release.run_gltf_validator", forbidden_validator)
    release = tmp_path / "release"

    with pytest.raises(ValueError, match="packaged canonical profile"):
        publish_release(
            [package],
            root=release,
            generated_at="2026-08-01T00:00:00Z",
        )

    assert validator_called is False
    assert not (release / "registry.json").exists()


@pytest.mark.parametrize("field", ["name", "semantics", "source_generator"])
def test_publish_rejects_manifest_fields_not_derived_from_intent(
    tmp_path: Path,
    field: str,
) -> None:
    package = _package(tmp_path)

    def tamper(_package: Path, manifest: dict[str, Any], _receipt: dict[str, Any]) -> None:
        if field == "name":
            manifest["name"] = "Forged catalog display name"
        elif field == "semantics":
            manifest["semantics"]["tags"].append("forged")
        else:
            manifest["source_generator"]["geometry_node_group"] = "ForgedGenerator"

    _forge_package(package, tamper)
    release = tmp_path / "release"

    with pytest.raises(ValueError, match="authored asset intent"):
        publish_release(
            [package],
            root=release,
            generated_at="2026-08-01T00:00:00Z",
        )
    assert not (release / "registry.json").exists()


@pytest.mark.parametrize("field", ["collisions", "runtime-geometry"])
def test_publish_rejects_runtime_metadata_not_derived_from_evidence(
    tmp_path: Path,
    field: str,
) -> None:
    package = _package(tmp_path)

    def tamper(_package: Path, manifest: dict[str, Any], _receipt: dict[str, Any]) -> None:
        if field == "collisions":
            manifest["collisions"][0]["bounds_m"]["maximum"][0] += 0.1
            manifest["collisions"][0]["bounds_m"]["dimensions"][0] += 0.1
        else:
            manifest["geometry"]["vertex_count"] += 1

    _forge_package(package, tamper)

    with pytest.raises(ValueError, match="inspection"):
        publish_release(
            [package],
            root=tmp_path / "release",
            generated_at="2026-08-01T00:00:00Z",
        )


def test_verify_rejects_public_provenance_not_derived_from_authored_review(
    tmp_path: Path,
) -> None:
    package = _package(tmp_path)

    def tamper(
        package: Path,
        manifest: dict[str, Any],
        receipt: dict[str, Any],
    ) -> None:
        descriptor = manifest["artifacts"]["provenance"]
        provenance = read_json(_artifact_path(package, descriptor))
        provenance["dedication"]["dedicator"] = "Forged Public Dedicator"
        _replace_artifact_document(package, manifest, receipt, descriptor, provenance)

    _forge_package(package, tamper)
    release = tmp_path / "release"
    _publish_without_contract(package, release)

    with pytest.raises(ValueError, match="reviewed authored provenance"):
        verify_release(release)


def test_verify_requires_canonical_authored_evidence_uri(tmp_path: Path) -> None:
    package = _package(tmp_path)

    def tamper(
        package: Path,
        manifest: dict[str, Any],
        receipt: dict[str, Any],
    ) -> None:
        descriptor = next(
            item
            for item in receipt["inputs"]
            if item["role"] == "provenance" and item["file_name"] == "provenance.json"
        )
        provenance = read_json(_artifact_path(package, descriptor))
        evidence_name = Path(provenance["evidence"][0]["uri"]).name
        provenance["evidence"][0]["uri"] = f"evidence/{evidence_name}"
        _replace_artifact_document(package, manifest, receipt, descriptor, provenance)

    _forge_package(package, tamper)
    release = tmp_path / "release"
    _publish_without_contract(package, release)

    with pytest.raises(ValueError, match=r"\.\./\.\./evidence/<file>"):
        verify_release(release)


def _tamper_reproducibility_case(
    case: str,
    package: Path,
    manifest: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    if case == "inspection-gltf-warning":
        descriptor = manifest["artifacts"]["inspection"]
        inspection = read_json(_artifact_path(package, descriptor))
        inspection["gltf_validation"]["warnings"] = 1
        _replace_artifact_document(package, manifest, receipt, descriptor, inspection)
    elif case == "profile-check-warning":
        descriptor = manifest["artifacts"]["inspection"]
        inspection = read_json(_artifact_path(package, descriptor))
        inspection["profile_validation"]["checks"][0]["status"] = "warning"
        _replace_artifact_document(package, manifest, receipt, descriptor, inspection)
    elif case == "missing-comparison-model":
        receipt["outputs"] = [
            item for item in receipt["outputs"] if item["file_name"] != "comparison-model.glb"
        ]
    elif case == "comparison-model-drift":
        descriptor = _find_output(receipt, "comparison-model.glb")
        _replace_artifact_bytes(
            package,
            manifest,
            receipt,
            descriptor,
            b"different comparison GLB bytes",
        )
    elif case == "comparison-build-id":
        receipt["reproducibility"]["comparison_build_id"] = "comparison_" + "0" * 24
    elif case == "malformed-validator-message":
        descriptor = _find_output(receipt, "gltf-validation.json")
        validator = read_json(_artifact_path(package, descriptor))
        validator["issues"]["messages"] = [
            {"code": "FORGED", "message": "malformed severity", "severity": "0"}
        ]
        _replace_artifact_document(package, manifest, receipt, descriptor, validator)
    elif case == "summary-identity":
        for name in ("blender-build.json", "comparison-blender-build.json"):
            descriptor = _find_output(receipt, name)
            summary = read_json(_artifact_path(package, descriptor))
            summary["asset"] = {"id": "unrelated_asset_99", "version": "9.9.9"}
            _replace_artifact_document(package, manifest, receipt, descriptor, summary)
    elif case == "manifest-preview-substitution":
        primary_preview = manifest["artifacts"]["previews"][0]
        scratch = package / "forged" / "divergent-preview.png"
        scratch.parent.mkdir(parents=True, exist_ok=True)
        scratch.write_bytes(b"a divergent public preview")
        published = publish_object(scratch, package)
        divergent = {
            **primary_preview,
            "file_name": "divergent-preview.png",
            "sha256": published.digest,
            "bytes": published.size_bytes,
            "uri": f"/{published.key}",
        }
        manifest["artifacts"]["previews"] = [divergent]
        receipt["outputs"].append(divergent)
    else:  # pragma: no cover - protects the parameter table itself
        raise AssertionError(case)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("inspection-gltf-warning", "zero-error, zero-warning"),
        ("profile-check-warning", "target-profile check"),
        ("missing-comparison-model", "comparison-model.glb"),
        ("comparison-model-drift", "comparison model.glb"),
        ("comparison-build-id", "comparison_build_id"),
        ("malformed-validator-message", "validator report"),
        ("summary-identity", "build receipt/manifest"),
        ("manifest-preview-substitution", "published preview.png"),
    ],
)
def test_verify_rejects_unsubstantiated_reproduced_receipt(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    package = _package(tmp_path)
    _forge_package(
        package,
        lambda package, manifest, receipt: _tamper_reproducibility_case(
            case,
            package,
            manifest,
            receipt,
        ),
    )
    release = tmp_path / "release"
    _publish_without_contract(package, release)

    with pytest.raises(ValueError, match=message):
        verify_release(release)


def test_verify_detects_tampered_release_object(tmp_path: Path) -> None:
    package = _package(tmp_path)
    release = tmp_path / "release"
    publish_release(
        [package],
        root=release,
        generated_at="2026-08-01T00:00:00Z",
    )
    manifest = read_json(package / "asset.json")
    runtime = manifest["artifacts"]["runtime"]
    (release / object_key(runtime["sha256"])).write_bytes(b"tampered")

    with pytest.raises(ValueError, match=r"artifact (size|digest) mismatch"):
        verify_release(release)


def _replace_registry(release: Path, registry: dict, *, immutable: bool = True) -> None:
    for path in (release / "registry.json", release / "snapshots" / "latest.json"):
        write_json_atomic(path, registry)
    if immutable:
        write_json_atomic(release / snapshot_key(registry["revision"]), registry)
    publish_object(release / "registry.json", release)


def test_verify_recomputes_registry_revision(tmp_path: Path) -> None:
    release = tmp_path / "release"
    publish_release(
        [_package(tmp_path)],
        root=release,
        generated_at="2026-08-01T00:00:00Z",
    )
    registry = read_json(release / "registry.json")
    registry["entries"][0]["name"] = "A syntactically valid tampered name"
    _replace_registry(release, registry)

    with pytest.raises(ValueError, match="registry revision mismatch"):
        verify_release(release)


def test_verify_recomputes_latest_aliases(tmp_path: Path) -> None:
    release = tmp_path / "release"
    publish_release(
        [_package(tmp_path)],
        root=release,
        generated_at="2026-08-01T00:00:00Z",
    )
    registry = read_json(release / "registry.json")
    registry["aliases"] = []
    registry["revision"] = sha256_json(revision_payload(registry))
    _replace_registry(release, registry)

    with pytest.raises(ValueError, match="latest aliases"):
        verify_release(release)


def test_verify_compares_registry_metadata_to_manifest(tmp_path: Path) -> None:
    release = tmp_path / "release"
    publish_release(
        [_package(tmp_path)],
        root=release,
        generated_at="2026-08-01T00:00:00Z",
    )
    registry = read_json(release / "registry.json")
    registry["entries"][0]["name"] = "A syntactically valid tampered name"
    registry["revision"] = sha256_json(revision_payload(registry))
    _replace_registry(release, registry)

    with pytest.raises(ValueError, match="registry name does not match manifest"):
        verify_release(release)


def test_release_path_rejects_network_path_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="root-relative"):
        _release_path(tmp_path.resolve(), "//etc/passwd")
