"""Publish and verify a portable, immutable NeuralStock static release."""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jsonschema.validators import validator_for

from neuralstock.canonical import canonical_json_bytes, read_json, sha256_file, sha256_json
from neuralstock.package import (
    INSPECTION_NONDETERMINISM,
    PREVIEW_NONDETERMINISM,
    SOURCE_NONDETERMINISM,
    SUMMARY_NONDETERMINISM,
    _budget_violations,
    _normalize_blender_version,
    _png_pixel_digest,
    _runtime_geometry_from_validator,
    _source_anchors_to_runtime,
    _source_bounds_to_runtime,
    _source_collisions_to_runtime,
    _validate_parameter_values,
    _validate_validator_report,
    run_gltf_validator,
)
from neuralstock.registry import (
    build_registry,
    revision_payload,
    semantic_version_key,
)
from neuralstock.schema import data_path, require_valid_document
from neuralstock.storage import (
    object_key,
    publish_named_immutable,
    publish_object,
    replace_alias,
    snapshot_key,
    version_manifest_key,
)


@dataclass(frozen=True)
class ReleaseResult:
    root: Path
    revision: str
    asset_count: int
    object_count: int
    registry_path: Path
    snapshot_path: Path
    latest_path: Path


@dataclass(frozen=True)
class VerificationResult:
    revision: str
    asset_count: int
    artifact_count: int
    verified_bytes: int


RELEASE_RUNTIME_GLB_HARD_CAP = 50 * 1024 * 1024
SCHEMA_ORIGIN = "https://schemas.neuralstock.ai"
DOCUMENT_LICENSE_SPDX = "MIT"
DOCUMENT_LICENSE_COPYRIGHT = "Copyright (c) 2026 NeuralStock contributors"
DOCUMENT_LICENSE_SHA256 = "db925e3df4ed5c6de89e903dd30ecb004f6ba4ae63d9aa98d8570ef50be87200"


@dataclass(frozen=True)
class CanonicalContractArtifact:
    source_path: Path
    release_key: str
    content_type: str


def _require_document_license(
    document: Mapping[str, Any],
    *,
    label: str,
    license_path: Path,
    license_uri: str,
) -> None:
    """Require a standalone contract to carry its complete, canonical MIT notice."""

    license_text = license_path.read_text(encoding="utf-8")
    if sha256_file(license_path) != DOCUMENT_LICENSE_SHA256:
        raise ValueError("packaged MIT license differs from the release policy digest")
    expected = {
        "spdx_id": DOCUMENT_LICENSE_SPDX,
        "copyright": DOCUMENT_LICENSE_COPYRIGHT,
        "license_uri": license_uri,
        "license_sha256": DOCUMENT_LICENSE_SHA256,
        "license_text": license_text,
    }
    if document.get("x-neuralstock-document-license") != expected:
        raise ValueError(f"canonical {label} must embed the complete MIT license metadata")


def canonical_contract_artifacts() -> tuple[CanonicalContractArtifact, ...]:
    """Return the owned, versioned contracts that ship beside every release."""

    schema_root = data_path("schemas")
    license_path = data_path("LICENSE")
    if not license_path.is_file():
        raise FileNotFoundError(f"canonical MIT license is missing from {license_path}")
    schema_paths = sorted(schema_root.glob("*.schema.json"))
    if not schema_paths:
        raise FileNotFoundError(f"canonical schemas are missing from {schema_root}")
    if not (schema_root / "discovery.schema.json").is_file():
        raise FileNotFoundError("canonical discovery.schema.json is missing")

    artifacts: list[CanonicalContractArtifact] = []
    for source_path in schema_paths:
        schema = read_json(source_path)
        expected_id = f"{SCHEMA_ORIGIN}/v0.2/{source_path.name}"
        if not isinstance(schema, dict) or schema.get("$id") != expected_id:
            raise ValueError(
                f"canonical schema {source_path.name} must declare $id {expected_id!r}"
            )
        _require_document_license(
            schema,
            label=f"schema {source_path.name}",
            license_path=license_path,
            license_uri=f"{SCHEMA_ORIGIN}/v0.2/LICENSE",
        )
        validator_for(schema).check_schema(schema)
        artifacts.append(
            CanonicalContractArtifact(
                source_path=source_path,
                release_key=f"v0.2/{source_path.name}",
                content_type="application/schema+json",
            )
        )
    artifacts.append(
        CanonicalContractArtifact(
            source_path=license_path,
            release_key="v0.2/LICENSE",
            content_type="text/plain",
        )
    )

    profile_path = data_path("profiles", "web-v1.json")
    profile = read_json(profile_path)
    require_valid_document("profile", profile)
    if profile.get("$schema") != f"{SCHEMA_ORIGIN}/v0.2/profile.schema.json":
        raise ValueError("canonical web-v1 profile must reference the owned profile schema")
    _require_document_license(
        profile,
        label="profile web-v1.json",
        license_path=license_path,
        license_uri=f"{SCHEMA_ORIGIN}/profiles/v0.2/LICENSE",
    )
    artifacts.append(
        CanonicalContractArtifact(
            source_path=profile_path,
            release_key="profiles/v0.2/web-v1.json",
            content_type="application/json",
        )
    )
    artifacts.append(
        CanonicalContractArtifact(
            source_path=license_path,
            release_key="profiles/v0.2/LICENSE",
            content_type="text/plain",
        )
    )
    return tuple(artifacts)


def publish_canonical_contract_artifacts(root: str | Path) -> tuple[Path, ...]:
    """Publish versioned contracts without permitting an existing key to change."""

    release_root = Path(root).resolve()
    return tuple(
        publish_named_immutable(artifact.source_path, release_root, artifact.release_key)
        for artifact in canonical_contract_artifacts()
    )


def verify_canonical_contract_artifacts(root: str | Path) -> tuple[Path, ...]:
    """Require release contract objects to match their packaged sources byte-for-byte."""

    release_root = Path(root).resolve()
    verified: list[Path] = []
    for artifact in canonical_contract_artifacts():
        published = release_root / artifact.release_key
        if not published.is_file():
            raise FileNotFoundError(f"canonical release contract is missing: {published}")
        if published.stat().st_size != artifact.source_path.stat().st_size or sha256_file(
            published
        ) != sha256_file(artifact.source_path):
            raise ValueError(
                f"canonical release contract differs from packaged bytes: {artifact.release_key}"
            )
        verified.append(published)
    return tuple(verified)


def iter_asset_artifacts(manifest: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    artifacts = manifest["artifacts"]
    for role in ("source", "runtime", "provenance", "inspection", "build_receipt"):
        yield artifacts[role]
    yield from artifacts["previews"]
    yield from artifacts.get("optional", [])


def _artifact_source(root: Path, descriptor: Mapping[str, Any]) -> Path:
    expected_uri = f"/{object_key(descriptor['sha256'])}"
    if descriptor["uri"] != expected_uri:
        raise ValueError(
            f"artifact URI for {descriptor['role']!r} must be {expected_uri!r}, "
            f"got {descriptor['uri']!r}"
        )
    return root / object_key(descriptor["sha256"])


def complete_artifact_descriptors(
    root: str | Path,
    manifest: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Return the complete artifact graph, including build-receipt dependencies."""

    artifact_root = Path(root)
    top_level = list(iter_asset_artifacts(manifest))
    receipt_descriptor = manifest["artifacts"]["build_receipt"]
    receipt_path = _artifact_source(artifact_root, receipt_descriptor)
    _verify_descriptor(receipt_path, receipt_descriptor)
    receipt = read_json(receipt_path)
    require_valid_document("build-receipt", receipt)

    descriptors = [*top_level, *receipt["inputs"], *receipt["outputs"]]
    unique: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for descriptor in descriptors:
        identity = (
            descriptor["sha256"],
            descriptor["role"],
            descriptor["file_name"],
        )
        existing = unique.get(identity)
        if existing is not None and dict(existing) != dict(descriptor):
            raise ValueError(f"conflicting artifact descriptors for {identity!r}")
        unique[identity] = descriptor
    return tuple(unique.values())


def _verify_descriptor(path: Path, descriptor: Mapping[str, Any]) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"artifact does not exist: {path}")
    actual_size = path.stat().st_size
    if actual_size != descriptor["bytes"]:
        raise ValueError(
            f"artifact size mismatch for {path}: expected {descriptor['bytes']}, got {actual_size}"
        )
    actual_digest = sha256_file(path)
    if actual_digest != descriptor["sha256"]:
        raise ValueError(
            f"artifact digest mismatch for {path}: expected {descriptor['sha256']}, "
            f"got {actual_digest}"
        )


def _release_path(root: Path, uri: str) -> Path:
    if not isinstance(uri, str) or not uri.startswith("/") or uri.startswith("//"):
        raise ValueError(f"published URI must be root-relative: {uri!r}")
    relative = Path(uri[1:])
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts) or "\\" in uri:
        raise ValueError(f"unsafe published URI: {uri!r}")
    candidate = root.joinpath(*relative.parts).resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError(f"published URI escapes release root: {uri!r}")
    return candidate


def _matching_descriptor(
    descriptors: Iterable[Mapping[str, Any]],
    *,
    file_name: str,
    role: str | None = None,
) -> Mapping[str, Any]:
    matches = [
        descriptor
        for descriptor in descriptors
        if descriptor["file_name"] == file_name and (role is None or descriptor["role"] == role)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {role or '*'} descriptor named {file_name}, got {len(matches)}"
        )
    return matches[0]


def _same_json(left: Any, right: Any) -> bool:
    try:
        return canonical_json_bytes(left) == canonical_json_bytes(right)
    except (TypeError, ValueError):
        return False


def _read_artifact_json(
    root: Path,
    descriptor: Mapping[str, Any],
    *,
    label: str,
    schema: str | None = None,
) -> dict[str, Any]:
    path = _artifact_source(root, descriptor)
    _verify_descriptor(path, descriptor)
    document = read_json(path)
    if not isinstance(document, dict):
        raise ValueError(f"{label} must be a JSON object")
    if schema is not None:
        require_valid_document(schema, document)
    return document


def _require_passing_inspection(inspection: Mapping[str, Any], *, label: str) -> None:
    profile_validation = inspection["profile_validation"]
    if profile_validation["status"] != "pass" or any(
        check["status"] != "pass" for check in profile_validation["checks"]
    ):
        raise ValueError(f"{label} did not pass every target-profile check")


def _verify_validator_contract(
    release_root: Path,
    *,
    receipt: Mapping[str, Any],
    inspection: Mapping[str, Any],
    runtime_descriptor: Mapping[str, Any],
) -> dict[str, Any]:
    if receipt["validation"]["status"] != "pass":
        raise ValueError("build receipt validation status is not pass")

    gltf_validation = inspection["gltf_validation"]
    if (
        gltf_validation["status"] != "pass"
        or gltf_validation["errors"] != 0
        or gltf_validation["warnings"] != 0
    ):
        raise ValueError("published inspection does not report zero-error, zero-warning glTF")
    _require_passing_inspection(inspection, label="published inspection")

    validator_descriptor = _matching_descriptor(
        receipt["outputs"],
        file_name="gltf-validation.json",
        role="inspection",
    )
    if validator_descriptor["media_type"] != "application/json":
        raise ValueError("glTF validator report has an invalid media type")
    validator = _read_artifact_json(
        release_root,
        validator_descriptor,
        label="glTF validator report",
    )
    try:
        issues = _validate_validator_report(validator, runtime_descriptor["file_name"])
    except ValueError as error:
        raise ValueError("glTF validator report does not pass the package contract") from error
    if (
        validator.get("validatorVersion") != gltf_validation["validator_version"]
        or validator.get("validatedAt") != receipt["completed_at"]
        or issues["numErrors"] != gltf_validation["errors"]
        or issues["numWarnings"] != gltf_validation["warnings"]
    ):
        raise ValueError("glTF validator report does not substantiate published validation")

    runtime_path = _artifact_source(release_root, runtime_descriptor)
    try:
        rerun = run_gltf_validator(runtime_path)
        rerun["uri"] = runtime_descriptor["file_name"]
        _validate_validator_report(rerun, runtime_descriptor["file_name"])
    except ValueError as error:
        raise ValueError("runtime GLB fails pinned validator re-execution") from error

    published_deterministic = deepcopy(validator)
    published_deterministic.pop("validatedAt", None)
    published_deterministic["uri"] = runtime_descriptor["file_name"]
    rerun_deterministic = deepcopy(rerun)
    rerun_deterministic.pop("validatedAt", None)
    rerun_deterministic["uri"] = runtime_descriptor["file_name"]
    if not _same_json(published_deterministic, rerun_deterministic):
        raise ValueError("published glTF validator report differs from pinned re-execution")
    return validator


def _summary_output_contract(
    summary: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    *,
    label: str,
) -> None:
    outputs = summary.get("outputs")
    if not isinstance(outputs, Mapping):
        raise ValueError(f"{label} outputs must be an object")
    for name, descriptor in artifacts.items():
        output = outputs.get(name)
        if not isinstance(output, Mapping) or (
            output.get("sha256") != descriptor["sha256"]
            or output.get("bytes") != descriptor["bytes"]
        ):
            raise ValueError(f"{label} does not describe {name} consistently")


def _summary_identity_contract(
    summary: Mapping[str, Any],
    *,
    label: str,
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    identity = {"id": manifest["id"], "version": manifest["version"]}
    try:
        blender_version = _normalize_blender_version(summary.get("blender_version"))
    except ValueError as error:
        raise ValueError(f"{label} has an invalid Blender version") from error
    if (
        summary.get("asset") != identity
        or not _same_json(summary.get("parameters"), receipt["parameters"])
        or summary.get("profile_status") != "pass"
        or summary.get("generated_at") != receipt["started_at"]
        or blender_version != receipt["environment"]["blender_version"]
    ):
        raise ValueError(f"{label} does not match the build receipt/manifest")


def _normalized_inspection(inspection: Mapping[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(dict(inspection))
    normalized["source_sha256"] = "<normalized-source-sha256>"
    return normalized


def _normalized_build_summary(
    summary: Mapping[str, Any],
    *,
    volatile_outputs: set[str],
) -> dict[str, Any]:
    normalized = deepcopy(dict(summary))
    outputs = normalized.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("Blender build summary outputs must be an object")
    for name in volatile_outputs:
        if name not in outputs:
            raise ValueError(f"Blender build summary does not describe {name}")
        outputs[name] = {"documented_nondeterminism": name}
    return normalized


def _require_same_artifact(
    primary: Mapping[str, Any],
    comparison: Mapping[str, Any],
    *,
    label: str,
) -> None:
    if primary["sha256"] != comparison["sha256"] or primary["bytes"] != comparison["bytes"]:
        raise ValueError(f"reproduced receipt has inconsistent comparison {label}")


def _verify_reproducibility_contract(
    release_root: Path,
    *,
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    inspection: Mapping[str, Any],
) -> None:
    reproducibility = receipt["reproducibility"]
    status = reproducibility["status"]
    if status == "not-yet-reproduced":
        return

    outputs = receipt["outputs"]
    primary_source = manifest["artifacts"]["source"]
    primary_runtime = manifest["artifacts"]["runtime"]
    manifest_previews = manifest["artifacts"]["previews"]
    if len(manifest_previews) != 1 or manifest_previews[0]["file_name"] != "preview.png":
        raise ValueError("reproduced receipt requires exactly one published preview.png")
    primary_preview = manifest_previews[0]
    receipt_preview = _matching_descriptor(outputs, file_name="preview.png", role="preview")
    if dict(receipt_preview) != dict(primary_preview):
        raise ValueError("receipt preview evidence does not match the published manifest preview")
    primary_details = _matching_descriptor(
        outputs,
        file_name="blender-details.json",
        role="build_evidence",
    )
    primary_summary_descriptor = _matching_descriptor(
        outputs,
        file_name="blender-build.json",
        role="build_evidence",
    )
    comparison = {
        name: _matching_descriptor(
            outputs,
            file_name=f"comparison-{name}",
            role="build_evidence",
        )
        for name in (
            "source.blend",
            "model.glb",
            "inspection.json",
            "blender-details.json",
            "preview.png",
            "blender-build.json",
        )
    }
    expected_media_types = {
        "source.blend": "application/x-blender",
        "model.glb": "model/gltf-binary",
        "inspection.json": "application/json",
        "blender-details.json": "application/json",
        "preview.png": "image/png",
        "blender-build.json": "application/json",
    }
    primary_media = {
        "source.blend": primary_source,
        "model.glb": primary_runtime,
        "blender-details.json": primary_details,
        "preview.png": primary_preview,
        "blender-build.json": primary_summary_descriptor,
    }
    for artifact_set in (primary_media, comparison):
        for name, descriptor in artifact_set.items():
            if descriptor["media_type"] != expected_media_types[name]:
                raise ValueError(f"reproducibility evidence {name} has an invalid media type")

    source_is_exact = (
        primary_source["sha256"] == comparison["source.blend"]["sha256"]
        and primary_source["bytes"] == comparison["source.blend"]["bytes"]
    )
    if status == "reproduced" and not source_is_exact:
        raise ValueError("receipt claims reproduced but comparison source.blend differs")
    if status == "known-nondeterminism" and source_is_exact:
        raise ValueError("known-nondeterminism receipt has an exact comparison source.blend")
    _require_same_artifact(
        primary_runtime,
        comparison["model.glb"],
        label="model.glb",
    )
    _require_same_artifact(
        primary_details,
        comparison["blender-details.json"],
        label="blender-details.json",
    )

    comparison_inspection = _read_artifact_json(
        release_root,
        comparison["inspection.json"],
        label="comparison inspection",
        schema="inspection",
    )
    if (
        comparison_inspection["asset"] != {"id": manifest["id"], "version": manifest["version"]}
        or comparison_inspection["source_sha256"] != comparison["source.blend"]["sha256"]
        or comparison_inspection["target_profile"] != manifest["target_profile"]
    ):
        raise ValueError("comparison inspection does not match reproduced asset evidence")
    _require_passing_inspection(comparison_inspection, label="comparison inspection")

    published_projection = deepcopy(comparison_inspection)
    published_projection["source_sha256"] = inspection["source_sha256"]
    published_projection["gltf_validation"] = deepcopy(inspection["gltf_validation"])
    if not _same_json(published_projection, inspection):
        raise ValueError("comparison inspection is inconsistent with published inspection")

    primary_summary = _read_artifact_json(
        release_root,
        primary_summary_descriptor,
        label="primary Blender build summary",
    )
    comparison_summary = _read_artifact_json(
        release_root,
        comparison["blender-build.json"],
        label="comparison Blender build summary",
    )
    _summary_identity_contract(
        primary_summary,
        label="primary Blender build summary",
        manifest=manifest,
        receipt=receipt,
    )
    _summary_identity_contract(
        comparison_summary,
        label="comparison Blender build summary",
        manifest=manifest,
        receipt=receipt,
    )
    primary_summary_artifacts = {
        "source.blend": primary_source,
        "model.glb": primary_runtime,
        "blender-details.json": primary_details,
        "preview.png": primary_preview,
    }
    if source_is_exact:
        # Packaging patches the public inspection with validator results;
        # an exact raw primary inspection is retained by its equal comparison.
        primary_summary_artifacts["inspection.json"] = comparison["inspection.json"]
    _summary_output_contract(
        primary_summary,
        primary_summary_artifacts,
        label="primary Blender build summary",
    )
    _summary_output_contract(
        comparison_summary,
        {
            name: comparison[name]
            for name in (
                "source.blend",
                "model.glb",
                "inspection.json",
                "blender-details.json",
                "preview.png",
            )
        },
        label="comparison Blender build summary",
    )

    primary_preview_path = _artifact_source(release_root, primary_preview)
    comparison_preview_path = _artifact_source(release_root, comparison["preview.png"])
    primary_pixels = _png_pixel_digest(primary_preview_path)
    comparison_pixels = _png_pixel_digest(comparison_preview_path)
    if primary_pixels != comparison_pixels:
        raise ValueError("reproduced receipt comparison preview pixels differ")
    preview_is_exact = (
        primary_preview["sha256"] == comparison["preview.png"]["sha256"]
        and primary_preview["bytes"] == comparison["preview.png"]["bytes"]
    )
    volatile_outputs = set()
    if not source_is_exact:
        volatile_outputs.update({"source.blend", "inspection.json"})
    if not preview_is_exact:
        volatile_outputs.add("preview.png")
    normalized_primary_summary = _normalized_build_summary(
        primary_summary,
        volatile_outputs=volatile_outputs,
    )
    normalized_comparison_summary = _normalized_build_summary(
        comparison_summary,
        volatile_outputs=volatile_outputs,
    )
    if not _same_json(normalized_primary_summary, normalized_comparison_summary):
        raise ValueError("reproduced receipt Blender summaries are inconsistent")

    if status == "known-nondeterminism":
        expected_allowed = [
            SOURCE_NONDETERMINISM,
            INSPECTION_NONDETERMINISM,
            PREVIEW_NONDETERMINISM,
            SUMMARY_NONDETERMINISM,
        ]
    else:
        expected_allowed = (
            [] if preview_is_exact else [PREVIEW_NONDETERMINISM, SUMMARY_NONDETERMINISM]
        )
    if reproducibility["allowed_nondeterminism"] != expected_allowed:
        raise ValueError("reproduced receipt allowed_nondeterminism is inconsistent")

    comparison_key = sha256_json(
        {
            "classification": status,
            "contract": "neuralstock-reproducibility-v0.2",
            "inspection": sha256_json(_normalized_inspection(comparison_inspection)),
            "model_glb": comparison["model.glb"]["sha256"],
            "preview_pixels": comparison_pixels,
            "source_semantics": comparison["blender-details.json"]["sha256"],
            "summary": sha256_json(normalized_comparison_summary),
        }
    )
    expected_comparison_build_id = f"comparison_{comparison_key[:24]}"
    if reproducibility.get("comparison_build_id") != expected_comparison_build_id:
        raise ValueError(f"{status} receipt comparison_build_id does not match its evidence")


def _verify_intent_derivation(
    release_root: Path,
    *,
    descriptor: Mapping[str, Any],
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    inspection: Mapping[str, Any],
    source: Mapping[str, Any],
    validator: Mapping[str, Any],
) -> None:
    intent = _read_artifact_json(
        release_root,
        descriptor,
        label="authored asset intent",
        schema="asset.intent",
    )
    identity = {"id": manifest["id"], "version": manifest["version"]}
    if (
        {"id": intent["id"], "version": intent["version"]} != identity
        or intent["name"] != manifest["name"]
        or intent["description"] != manifest["description"]
        or intent["license"] != manifest["license"]
        or intent["target_profile"] != manifest["target_profile"]
        or intent["source"]["sha256"] != source["sha256"]
        or not _same_json(intent["semantics"], manifest["semantics"])
    ):
        raise ValueError("published manifest is not derived from its authored asset intent")

    expected_source_generator = {
        "geometry_node_group": intent["blender_source"]["geometry_node_group"],
        "parameters": intent["blender_source"]["parameters"],
    }
    if not _same_json(manifest["source_generator"], expected_source_generator):
        raise ValueError("manifest source_generator is not derived from its authored asset intent")
    try:
        _validate_parameter_values(receipt["parameters"], intent["blender_source"]["parameters"])
    except ValueError as error:
        raise ValueError("build receipt parameters violate authored asset intent") from error
    if inspection["parameters"]["node_group"] != intent["blender_source"][
        "geometry_node_group"
    ] or not _same_json(
        inspection["parameters"]["inputs"],
        intent["blender_source"]["parameters"],
    ):
        raise ValueError("published inspection parameters do not match authored asset intent")
    anchor_names = {anchor["name"] for anchor in inspection["anchors"]}
    missing_anchors = sorted(set(intent["required_anchors"]) - anchor_names)
    if missing_anchors:
        raise ValueError(
            "published inspection is missing intent-required anchors: " + ", ".join(missing_anchors)
        )

    expected_geometry = _runtime_geometry_from_validator(
        validator,
        texture_count=inspection["textures"]["count"],
    )
    if (
        manifest["published_at"] != receipt["completed_at"]
        or receipt["target_profile"] != manifest["target_profile"]
        or not _same_json(manifest["bounds_m"], _source_bounds_to_runtime(inspection["bounds_m"]))
        or not _same_json(manifest["geometry"], expected_geometry)
        or not _same_json(manifest["anchors"], _source_anchors_to_runtime(inspection["anchors"]))
        or not _same_json(
            manifest["collisions"],
            _source_collisions_to_runtime(inspection["collisions"]),
        )
    ):
        raise ValueError("published manifest metadata is not derived from its inspection")


def _verify_provenance_derivation(
    release_root: Path,
    *,
    descriptor: Mapping[str, Any],
    public_provenance: Mapping[str, Any],
    receipt_inputs: Iterable[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    source: Mapping[str, Any],
) -> None:
    authored = _read_artifact_json(
        release_root,
        descriptor,
        label="authored provenance",
        schema="provenance",
    )
    identity = {"id": manifest["id"], "version": manifest["version"]}
    if (
        authored["asset"] != identity
        or authored["source_sha256"] != source["sha256"]
        or authored["license"] != manifest["license"]
    ):
        raise ValueError("authored provenance does not match manifest/source contract")
    unresolved = [
        name
        for name, status in authored["rights_review"].items()
        if name != "notes" and status == "needs-review"
    ]
    if unresolved:
        raise ValueError("authored provenance contains unresolved rights review")

    expected_public = deepcopy(authored)
    published_by_authored_uri: dict[str, str] = {}
    linked_evidence: list[Mapping[str, Any]] = []
    for index, evidence in enumerate(expected_public["evidence"]):
        authored_uri = evidence["uri"]
        parsed_uri = urlsplit(authored_uri)
        uri_parts = Path(authored_uri).parts
        local_evidence_shape = len(uri_parts) == 4 and uri_parts[:3] == ("..", "..", "evidence")
        if (
            not authored_uri
            or "\\" in authored_uri
            or authored_uri.startswith("/")
            or parsed_uri.scheme
            or parsed_uri.netloc
            or parsed_uri.query
            or parsed_uri.fragment
            or not local_evidence_shape
            or uri_parts[-1] in {"", ".", ".."}
        ):
            raise ValueError("authored provenance evidence must be ../../evidence/<file>")
        evidence_name = Path(authored_uri).name
        if not evidence_name:
            raise ValueError("authored provenance evidence URI has no file name")
        evidence_descriptor = _matching_descriptor(
            receipt_inputs,
            file_name=f"evidence-{index + 1:02d}-{evidence_name}",
            role="evidence",
        )
        if evidence.get("sha256") != evidence_descriptor["sha256"]:
            raise ValueError("authored provenance evidence hash is not in the receipt graph")
        linked_evidence.append(evidence_descriptor)
        evidence["uri"] = evidence_descriptor["uri"]
        published_by_authored_uri[authored_uri] = evidence_descriptor["uri"]

    all_evidence = [item for item in receipt_inputs if item["role"] == "evidence"]
    linked_payloads = sorted(canonical_json_bytes(dict(item)) for item in linked_evidence)
    all_payloads = sorted(canonical_json_bytes(dict(item)) for item in all_evidence)
    if linked_payloads != all_payloads:
        raise ValueError("receipt contains evidence inputs not linked by authored provenance")

    for dependency in expected_public["dependencies"]:
        authored_uri = dependency["evidence_uri"]
        published_uri = published_by_authored_uri.get(authored_uri)
        if published_uri is None:
            raise ValueError("authored dependency evidence is not declared by provenance")
        dependency["evidence_uri"] = published_uri

    if not _same_json(expected_public, public_provenance):
        raise ValueError("published provenance is not derived from reviewed authored provenance")


def _verify_manifest_contract(
    release_root: Path,
    manifest: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    descriptors = complete_artifact_descriptors(release_root, manifest)
    for descriptor in descriptors:
        _verify_descriptor(_artifact_source(release_root, descriptor), descriptor)
    receipt_descriptor = manifest["artifacts"]["build_receipt"]
    receipt = _read_artifact_json(
        release_root,
        receipt_descriptor,
        label="build receipt",
        schema="build-receipt",
    )

    identity = {"id": manifest["id"], "version": manifest["version"]}
    if receipt["asset"] != identity:
        raise ValueError("build receipt asset identity does not match manifest")
    if receipt["build_key"] != manifest["build_key"]:
        raise ValueError("build receipt key does not match manifest")
    if receipt["build_id"] != f"build_{receipt['build_key'][:24]}":
        raise ValueError("build receipt ID is not derived from its build key")
    started_at = datetime.fromisoformat(receipt["started_at"].replace("Z", "+00:00"))
    completed_at = datetime.fromisoformat(receipt["completed_at"].replace("Z", "+00:00"))
    if completed_at < started_at:
        raise ValueError("build receipt completes before it starts")
    if receipt["normalized_parameters_sha256"] != sha256_json(receipt["parameters"]):
        raise ValueError("build receipt normalized parameter hash is invalid")

    inputs = receipt["inputs"]
    outputs = receipt["outputs"]
    source = manifest["artifacts"]["source"]
    if source not in inputs or receipt["source_sha256"] != source["sha256"]:
        raise ValueError("build receipt source input does not match manifest")
    expected_outputs = [
        manifest["artifacts"]["runtime"],
        manifest["artifacts"]["provenance"],
        manifest["artifacts"]["inspection"],
        *manifest["artifacts"]["previews"],
        *manifest["artifacts"].get("optional", []),
    ]
    for descriptor in expected_outputs:
        if descriptor not in outputs:
            raise ValueError(
                f"manifest artifact {descriptor['file_name']!r} is absent from receipt outputs"
            )
    inspection_descriptor = manifest["artifacts"]["inspection"]
    if receipt["validation"]["inspection_sha256"] != inspection_descriptor["sha256"]:
        raise ValueError("receipt validation does not identify the published inspection")

    inspection = _read_artifact_json(
        release_root,
        inspection_descriptor,
        label="published inspection",
        schema="inspection",
    )
    if (
        inspection["asset"] != identity
        or inspection["source_sha256"] != source["sha256"]
        or inspection["target_profile"] != manifest["target_profile"]
        or inspection["profile_validation"]["status"] != "pass"
    ):
        raise ValueError("published inspection does not match the manifest/source contract")

    profile = _matching_descriptor(
        inputs,
        file_name=f"profile-{manifest['target_profile']}.json",
        role="build_evidence",
    )
    profile_document = _read_artifact_json(
        release_root,
        profile,
        label="target profile",
        schema="profile",
    )
    if profile_document["id"] != manifest["target_profile"]:
        raise ValueError("target profile evidence does not match manifest")
    canonical_profile_path = data_path(
        "profiles",
        f"{manifest['target_profile']}.json",
    )
    canonical_profile = read_json(canonical_profile_path)
    if (
        profile["sha256"] != sha256_file(canonical_profile_path)
        or profile["bytes"] != canonical_profile_path.stat().st_size
        or not _same_json(profile_document, canonical_profile)
    ):
        raise ValueError("target profile evidence differs from packaged canonical profile")
    runtime_descriptor = manifest["artifacts"]["runtime"]
    runtime_path = _artifact_source(release_root, runtime_descriptor)
    runtime_limit = min(
        profile_document["budgets"]["glb_bytes"],
        RELEASE_RUNTIME_GLB_HARD_CAP,
    )
    if runtime_descriptor["bytes"] > runtime_limit or runtime_path.stat().st_size > runtime_limit:
        raise ValueError("runtime GLB exceeds target-profile byte budget")
    budget_violations = _budget_violations(
        inspection,
        profile_document,
        runtime_descriptor["bytes"],
    )
    if budget_violations:
        raise ValueError("published asset exceeds target-profile budget")

    validator = _verify_validator_contract(
        release_root,
        receipt=receipt,
        inspection=inspection,
        runtime_descriptor=runtime_descriptor,
    )
    _verify_reproducibility_contract(
        release_root,
        manifest=manifest,
        receipt=receipt,
        inspection=inspection,
    )

    provenance_descriptor = manifest["artifacts"]["provenance"]
    provenance = _read_artifact_json(
        release_root,
        provenance_descriptor,
        label="published provenance",
        schema="provenance",
    )
    if (
        provenance["asset"] != identity
        or provenance["source_sha256"] != source["sha256"]
        or provenance["license"] != manifest["license"]
    ):
        raise ValueError("published provenance does not match manifest/source contract")
    for evidence in provenance["evidence"]:
        if not any(
            descriptor["uri"] == evidence["uri"]
            and descriptor["role"] == "evidence"
            and descriptor["sha256"] == evidence.get("sha256")
            for descriptor in descriptors
        ):
            raise ValueError("published provenance evidence is not in the receipt graph")
    for dependency in provenance["dependencies"]:
        if not any(
            descriptor["uri"] == dependency["evidence_uri"] and descriptor["role"] == "evidence"
            for descriptor in descriptors
        ):
            raise ValueError("dependency evidence is not in the receipt graph")

    intent = _matching_descriptor(inputs, file_name="asset.intent.json", role="manifest")
    authored_provenance = _matching_descriptor(
        inputs, file_name="provenance.json", role="provenance"
    )
    _verify_intent_derivation(
        release_root,
        descriptor=intent,
        manifest=manifest,
        receipt=receipt,
        inspection=inspection,
        source=source,
        validator=validator,
    )
    _verify_provenance_derivation(
        release_root,
        descriptor=authored_provenance,
        public_provenance=provenance,
        receipt_inputs=inputs,
        manifest=manifest,
        source=source,
    )
    if not inspection["textures"]["all_packed"]:
        raise ValueError("published inspection reports unpacked texture resources")
    if receipt["export"]["geometry_compression"] != profile_document["runtime"][
        "geometry_compression"
    ] or receipt["export"]["animations"] is not bool(validator["info"]["animationCount"]):
        raise ValueError("build receipt export does not match profile/validator evidence")
    toolchain_descriptor = _matching_descriptor(
        inputs, file_name="toolchain.json", role="build_evidence"
    )
    toolchain = read_json(_artifact_source(release_root, toolchain_descriptor))
    if receipt["builder"].get("code_sha256") != sha256_json(toolchain):
        raise ValueError("receipt builder code hash does not match toolchain evidence")
    expected_build_key = sha256_json(
        {
            "builder": receipt["builder"],
            "evidence_sha256": sorted(
                descriptor["sha256"] for descriptor in inputs if descriptor["role"] == "evidence"
            ),
            "image_digest": receipt["environment"]["image_digest"],
            "intent_sha256": intent["sha256"],
            "normalized_parameters_sha256": receipt["normalized_parameters_sha256"],
            "platform": receipt["environment"]["platform"],
            "profile_sha256": profile["sha256"],
            "provenance_sha256": authored_provenance["sha256"],
            "source_sha256": receipt["source_sha256"],
            "target_profile": receipt["target_profile"],
            "validator_version": inspection["gltf_validation"]["validator_version"],
        }
    )
    if expected_build_key != receipt["build_key"]:
        raise ValueError("build receipt key does not cover the declared build inputs")
    return descriptors


def _validate_package_documents(package_directory: Path, manifest: Mapping[str, Any]) -> None:
    file_schemas = {
        "asset.intent.json": "asset.intent",
        "provenance.json": "provenance",
        "inspection.json": "inspection",
        "build-receipt.json": "build-receipt",
    }
    for descriptor in complete_artifact_descriptors(package_directory, manifest):
        path = _artifact_source(package_directory, descriptor)
        _verify_descriptor(path, descriptor)
        schema_name = file_schemas.get(descriptor["file_name"])
        if schema_name is not None:
            require_valid_document(schema_name, read_json(path))


def publish_release(
    package_directories: Iterable[str | Path],
    *,
    root: str | Path,
    generated_at: str,
) -> ReleaseResult:
    """Publish packages using immutable objects and atomic discovery aliases.

    The operation may leave harmless, unreachable content-addressed objects if a
    later package fails. Version manifests and registry aliases are not exposed
    until all package artifacts have passed verification.
    """

    release_root = Path(root).resolve()
    packages = sorted(
        (Path(value).resolve() for value in package_directories),
        key=lambda value: value.as_posix(),
    )
    if not packages:
        raise ValueError("at least one package directory is required")

    manifests: list[tuple[Path, dict[str, Any]]] = []
    for package_directory in packages:
        manifest_path = package_directory / "asset.json"
        manifest = read_json(manifest_path)
        require_valid_document("asset", manifest)
        _validate_package_documents(package_directory, manifest)
        _verify_manifest_contract(package_directory, manifest)
        manifests.append((manifest_path, manifest))

    identities: set[tuple[str, str]] = set()
    for _, manifest in manifests:
        identity = (manifest["id"], manifest["version"])
        if identity in identities:
            raise ValueError(f"duplicate package identity: {identity[0]}@{identity[1]}")
        identities.add(identity)

    publish_canonical_contract_artifacts(release_root)

    published_object_keys: set[str] = set()
    for package_directory, (_, manifest) in zip(packages, manifests, strict=True):
        for descriptor in complete_artifact_descriptors(package_directory, manifest):
            published = publish_object(
                _artifact_source(package_directory, descriptor), release_root
            )
            if (
                published.digest != descriptor["sha256"]
                or published.size_bytes != descriptor["bytes"]
            ):
                raise ValueError(
                    f"artifact changed after release preflight: {descriptor['file_name']}"
                )
            published_object_keys.add(published.key)

    named_manifests: list[Path] = []
    for manifest_path, manifest in manifests:
        published = publish_object(manifest_path, release_root)
        published_object_keys.add(published.key)
        named_manifests.append(
            publish_named_immutable(
                manifest_path,
                release_root,
                version_manifest_key(manifest["id"], manifest["version"]),
            )
        )

    with tempfile.TemporaryDirectory(prefix="neuralstock-release-") as temporary:
        registry_source = Path(temporary) / "registry.json"
        registry = build_registry(
            named_manifests,
            output=registry_source,
            generated_at=generated_at,
        )
        registry_object = publish_object(registry_source, release_root)
        published_object_keys.add(registry_object.key)
        immutable_snapshot = publish_named_immutable(
            registry_source,
            release_root,
            snapshot_key(registry["revision"]),
        )
        # Verify the staged immutable graph immediately before the only mutable,
        # discoverable pointers are advanced.
        verify_release(release_root, registry_path=immutable_snapshot)
        registry_path = replace_alias(registry_source, release_root, "registry.json")
        latest = replace_alias(
            registry_source,
            release_root,
            "snapshots/latest.json",
        )

    return ReleaseResult(
        root=release_root,
        revision=registry["revision"],
        asset_count=len(manifests),
        object_count=len(published_object_keys),
        registry_path=registry_path,
        snapshot_path=immutable_snapshot,
        latest_path=latest,
    )


def verify_release(
    root: str | Path,
    *,
    registry_path: str | Path | None = None,
) -> VerificationResult:
    release_root = Path(root).resolve()
    verify_canonical_contract_artifacts(release_root)
    selected_registry = (
        Path(registry_path).resolve()
        if registry_path is not None
        else release_root / "snapshots" / "latest.json"
    )
    registry = read_json(selected_registry)
    require_valid_document("registry", registry)
    expected_revision = sha256_json(revision_payload(registry))
    if registry["revision"] != expected_revision:
        raise ValueError(
            f"registry revision mismatch: expected {expected_revision}, got {registry['revision']}"
        )

    latest: dict[str, str] = {}
    for entry in registry["entries"]:
        identity = entry["asset"]
        current = latest.get(identity["id"])
        if current is None or semantic_version_key(identity["version"]) > semantic_version_key(
            current
        ):
            latest[identity["id"]] = identity["version"]
    expected_aliases = [
        {"id": asset_id, "alias": "latest", "version": version}
        for asset_id, version in sorted(latest.items())
    ]
    if registry["aliases"] != expected_aliases:
        raise ValueError("registry latest aliases do not match its entries")

    immutable_snapshot = release_root / snapshot_key(registry["revision"])
    if (
        not immutable_snapshot.is_file()
        or immutable_snapshot.read_bytes() != selected_registry.read_bytes()
    ):
        raise ValueError("selected registry does not match its immutable revision snapshot")
    registry_object = release_root / object_key(sha256_file(selected_registry))
    if (
        not registry_object.is_file()
        or registry_object.read_bytes() != selected_registry.read_bytes()
    ):
        raise ValueError("selected registry is missing its content-addressed object")
    if registry_path is None:
        alias = release_root / "registry.json"
        if not alias.is_file() or alias.read_bytes() != selected_registry.read_bytes():
            raise ValueError("registry.json does not match snapshots/latest.json")

    artifact_count = 0
    verified_bytes = 0
    seen_identities: set[tuple[str, str]] = set()
    for entry in registry["entries"]:
        manifest_descriptor = entry["manifest"]
        manifest_path = _release_path(release_root, manifest_descriptor["uri"])
        _verify_descriptor(manifest_path, manifest_descriptor)
        manifest = read_json(manifest_path)
        require_valid_document("asset", manifest)
        if (
            manifest["id"] != entry["asset"]["id"]
            or manifest["version"] != entry["asset"]["version"]
        ):
            raise ValueError(f"registry identity does not match manifest: {manifest_path}")
        identity = (manifest["id"], manifest["version"])
        if identity in seen_identities:
            raise ValueError(f"registry contains duplicate identity: {identity[0]}@{identity[1]}")
        seen_identities.add(identity)
        expected_entry_fields = {
            "name": manifest["name"],
            "description": manifest["description"],
            "license": manifest["license"],
            "target_profile": manifest["target_profile"],
            "coordinate_system": manifest["coordinate_system"],
            "semantics": manifest["semantics"],
            "bounds_m": manifest["bounds_m"],
            "triangle_count": manifest["geometry"]["triangle_count"],
        }
        for field, expected in expected_entry_fields.items():
            if entry[field] != expected:
                raise ValueError(f"registry {field} does not match manifest: {manifest_path}")

        manifest_object = release_root / object_key(manifest_descriptor["sha256"])
        _verify_descriptor(manifest_object, manifest_descriptor)
        seen_objects: set[str] = set()
        for descriptor in _verify_manifest_contract(release_root, manifest):
            artifact_path = _release_path(release_root, descriptor["uri"])
            _verify_descriptor(artifact_path, descriptor)
            if descriptor["sha256"] not in seen_objects:
                seen_objects.add(descriptor["sha256"])
                artifact_count += 1
                verified_bytes += descriptor["bytes"]

    return VerificationResult(
        revision=registry["revision"],
        asset_count=len(registry["entries"]),
        artifact_count=artifact_count,
        verified_bytes=verified_bytes,
    )
