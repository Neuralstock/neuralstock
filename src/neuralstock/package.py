"""Strict outer gate that turns Blender output into a publishable v0.2 package."""

from __future__ import annotations

import json
import math
import os
import re
import struct
import subprocess
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from neuralstock import __version__
from neuralstock.canonical import (
    canonical_json_bytes,
    pretty_json_bytes,
    read_json,
    sha256_bytes,
    sha256_file,
    sha256_json,
    write_json_atomic,
)
from neuralstock.schema import data_path, require_valid_document, schema_directory
from neuralstock.storage import object_key, publish_object, require_sha256

GLTF_VALIDATOR_VERSION = "2.0.0-dev.3.10"
GLTF_VALIDATOR_SCRIPT = data_path("tools", "validate-gltf.bundle.cjs")
GLTF_VALIDATOR_LEGAL_FILES = (
    data_path("tools", "gltf-validator.LICENSE"),
    data_path("tools", "gltf-validator.NOTICES"),
)
REQUIRED_BLENDER_OUTPUTS = (
    "source.blend",
    "model.glb",
    "inspection.json",
    "blender-details.json",
    "preview.png",
)
EXACT_REPRODUCIBLE_OUTPUTS = ("model.glb", "blender-details.json")
SOURCE_NONDETERMINISM = (
    "source.blend: Blender serialization may vary session identifiers while "
    "blender-details.json, model.glb, and normalized inspection remain exact."
)
INSPECTION_NONDETERMINISM = (
    "inspection.json: source_sha256 may differ only when source.blend serialization differs."
)
PREVIEW_NONDETERMINISM = (
    "preview.png: lossless PNG encoding bytes may differ while decoded RGBA pixels remain exact."
)
SUMMARY_NONDETERMINISM = (
    "blender-build.json: only descriptors propagated from documented nondeterministic outputs "
    "may differ."
)


class PackageError(ValueError):
    """Raised when a candidate cannot cross the publication gate."""


@dataclass(frozen=True)
class PackageResult:
    asset: dict[str, Any]
    build_receipt: dict[str, Any]
    validation_report: dict[str, Any]
    output: Path

    @property
    def build_key(self) -> str:
        return str(self.build_receipt["build_key"])


@dataclass(frozen=True)
class ReproducibilityResult:
    status: str
    allowed_nondeterminism: tuple[str, ...]
    comparison_build_id: str


ValidatorRunner = Callable[[Path], dict[str, Any]]


def _toolchain_document() -> dict[str, Any]:
    """Describe every repository/wheel file that controls the package gate."""

    package_directory = Path(__file__).resolve().parent
    grouped_paths = [
        (
            "python",
            package_directory,
            sorted(package_directory.glob("*.py")),
        ),
        ("schemas", schema_directory(), sorted(schema_directory().glob("*.schema.json"))),
        (
            "profiles",
            data_path("profiles"),
            sorted(data_path("profiles").glob("*.json")),
        ),
        ("legal", data_path("LICENSE").parent, [data_path("LICENSE")]),
        (
            "tools",
            GLTF_VALIDATOR_SCRIPT.parent,
            [GLTF_VALIDATOR_SCRIPT, *GLTF_VALIDATOR_LEGAL_FILES],
        ),
    ]
    files = {
        f"{group}/{path.relative_to(base).as_posix()}": sha256_file(path)
        for group, base, paths in grouped_paths
        for path in paths
    }
    return {
        "contract": "neuralstock-package-toolchain-v0.2",
        "package_version": __version__,
        "files": dict(sorted(files.items())),
    }


def run_gltf_validator(
    model: Path,
    *,
    node_executable: str = "node",
    script: Path = GLTF_VALIDATOR_SCRIPT,
) -> dict[str, Any]:
    """Run the pinned repository-owned wrapper around Khronos glTF Validator."""

    try:
        completed = subprocess.run(
            [node_executable, str(script), str(model)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PackageError(f"unable to execute Khronos glTF Validator: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise PackageError(f"Khronos glTF Validator did not complete: {detail}")
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise PackageError("Khronos glTF Validator returned invalid JSON") from error
    if not isinstance(report, dict):
        raise PackageError("Khronos glTF Validator report must be an object")
    return report


def parse_parameter_values(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise PackageError(f"--parameters-json must contain valid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise PackageError("--parameters-json must be a JSON object")
    return parsed


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = read_json(path)
    except (OSError, json.JSONDecodeError) as error:
        raise PackageError(f"cannot read {label} at {path}: {error}") from error
    if not isinstance(value, dict):
        raise PackageError(f"{label} must be a JSON object: {path}")
    return value


def _same_json(left: Any, right: Any) -> bool:
    try:
        return canonical_json_bytes(left) == canonical_json_bytes(right)
    except (TypeError, ValueError):
        return False


def _require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise PackageError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _require_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PackageError(f"{label} must be an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PackageError(f"{label} must be an RFC 3339 timestamp: {value!r}") from error
    if parsed.tzinfo is None:
        raise PackageError(f"{label} must include a timezone: {value!r}")
    return value


def _verify_summary_output(
    directory: Path,
    outputs: Mapping[str, Any],
    name: str,
    *,
    build_label: str = "Blender",
) -> Path:
    path = directory / name
    if not path.is_file():
        raise PackageError(f"required {build_label} output is missing: {path}")
    descriptor = outputs.get(name)
    if not isinstance(descriptor, Mapping):
        raise PackageError(f"{build_label} blender-build.json does not describe {name}")
    actual_hash = sha256_file(path)
    actual_bytes = path.stat().st_size
    _require_equal(f"{build_label} output hash for {name}", descriptor.get("sha256"), actual_hash)
    _require_equal(f"{build_label} output size for {name}", descriptor.get("bytes"), actual_bytes)
    if actual_bytes <= 0:
        raise PackageError(f"required {build_label} output is empty: {path}")
    return path


def _validate_parameter_values(values: Mapping[str, Any], definitions: Mapping[str, Any]) -> None:
    for name, value in values.items():
        definition = definitions.get(name)
        if not isinstance(definition, Mapping):
            raise PackageError(f"parameter {name!r} is not declared by asset.intent.json")
        kind = definition.get("type")
        if kind == "float":
            valid_type = isinstance(value, (int, float)) and not isinstance(value, bool)
            if not valid_type or not math.isfinite(float(value)):
                raise PackageError(f"parameter {name!r} must be a finite number")
            if not float(definition["minimum"]) <= float(value) <= float(definition["maximum"]):
                raise PackageError(f"parameter {name!r} is outside its inclusive bounds")
        elif kind == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise PackageError(f"parameter {name!r} must be an integer")
            if not int(definition["minimum"]) <= value <= int(definition["maximum"]):
                raise PackageError(f"parameter {name!r} is outside its inclusive bounds")
        elif kind == "boolean":
            if not isinstance(value, bool):
                raise PackageError(f"parameter {name!r} must be a boolean")
        elif kind == "enum":
            if not isinstance(value, str) or value not in definition["options"]:
                raise PackageError(f"parameter {name!r} must be one of its declared options")
        else:
            raise PackageError(f"parameter {name!r} has unsupported type {kind!r}")


def _parameter_detail_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return False
        return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-6)
    return actual == expected


def _validate_geometry_node_parameter_details(
    details: Mapping[str, Any],
    *,
    node_group: Any,
    definitions: Mapping[str, Any],
    parameter_values: Mapping[str, Any],
) -> None:
    geometry_nodes = details.get("geometry_nodes")
    if not isinstance(geometry_nodes, list):
        raise PackageError("blender-details.json must report Geometry Nodes interfaces")
    public_groups = [
        group
        for group in geometry_nodes
        if isinstance(group, Mapping) and isinstance(group.get("inputs"), list) and group["inputs"]
    ]
    if not definitions:
        if public_groups:
            raise PackageError("static asset exposes undeclared Geometry Nodes parameters")
        return
    if not isinstance(node_group, str) or not node_group:
        raise PackageError("procedural asset has no declared Geometry Nodes group")

    matching_groups = [group for group in public_groups if group.get("node_group") == node_group]
    if len(matching_groups) != 1:
        raise PackageError(
            f"blender-details.json must report exactly one public {node_group!r} interface"
        )
    unexpected_groups = [group for group in public_groups if group.get("node_group") != node_group]
    if unexpected_groups:
        raise PackageError("blender-details.json reports undeclared public node-group inputs")

    inputs = matching_groups[0]["inputs"]
    if not all(isinstance(item, Mapping) and isinstance(item.get("name"), str) for item in inputs):
        raise PackageError("blender-details.json contains an invalid Geometry Nodes input")
    actual_by_name = {str(item["name"]): item for item in inputs}
    if len(actual_by_name) != len(inputs):
        raise PackageError("blender-details.json contains duplicate Geometry Nodes input names")
    if set(actual_by_name) != set(definitions):
        raise PackageError("blender-details.json Geometry Nodes inputs differ from asset intent")

    for name, definition in definitions.items():
        if not isinstance(definition, Mapping):
            raise PackageError(f"parameter {name!r} declaration must be an object")
        actual = actual_by_name[name]
        if actual.get("type") != definition.get("type"):
            raise PackageError(f"Geometry Nodes input {name!r} has the wrong type")
        if actual.get("agent_safe") is not True or definition.get("agent_safe") is not True:
            raise PackageError(f"Geometry Nodes input {name!r} is not agent-safe")
        if actual.get("linked") is not True:
            raise PackageError(f"Geometry Nodes input {name!r} is not linked into the node graph")
        if not _parameter_detail_matches(actual.get("default"), definition.get("default")):
            raise PackageError(f"Geometry Nodes input {name!r} has the wrong default")

        parameter_type = definition.get("type")
        if parameter_type in {"float", "integer"}:
            if not _parameter_detail_matches(actual.get("min"), definition.get("minimum")):
                raise PackageError(f"Geometry Nodes input {name!r} has the wrong minimum")
            if not _parameter_detail_matches(actual.get("max"), definition.get("maximum")):
                raise PackageError(f"Geometry Nodes input {name!r} has the wrong maximum")
        if parameter_type == "enum" and actual.get("options") != definition.get("options"):
            raise PackageError(f"Geometry Nodes input {name!r} has the wrong enum options")

        expected_value = parameter_values.get(name, definition.get("default"))
        if not _parameter_detail_matches(actual.get("value"), expected_value):
            raise PackageError(f"Geometry Nodes input {name!r} has the wrong applied value")


def _validate_validator_report(report: dict[str, Any], model_name: str) -> dict[str, Any]:
    _require_equal("glTF validator version", report.get("validatorVersion"), GLTF_VALIDATOR_VERSION)
    _require_equal("glTF validator URI", report.get("uri"), model_name)
    _require_equal("glTF validator MIME type", report.get("mimeType"), "model/gltf-binary")
    issues = report.get("issues")
    if not isinstance(issues, dict):
        raise PackageError("Khronos glTF Validator report is missing issues")
    counts: dict[str, int] = {}
    for field in ("numErrors", "numWarnings", "numInfos", "numHints"):
        count = issues.get(field)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise PackageError(f"Khronos glTF Validator issues.{field} must be non-negative")
        counts[field] = count
    if issues.get("truncated") is not False:
        raise PackageError("Khronos glTF Validator report is truncated")
    messages = issues.get("messages")
    if not isinstance(messages, list) or any(not isinstance(message, dict) for message in messages):
        raise PackageError("Khronos glTF Validator issues.messages must be an array of objects")
    for message in messages:
        severity = message.get("severity")
        if (
            not isinstance(message.get("code"), str)
            or not isinstance(message.get("message"), str)
            or not isinstance(severity, int)
            or isinstance(severity, bool)
            or severity not in range(4)
        ):
            raise PackageError("Khronos glTF Validator emitted a malformed issue message")
    severe_messages = [message for message in messages if message["severity"] <= 1]
    if counts["numErrors"] or counts["numWarnings"]:
        raise PackageError(
            "GLB rejected by Khronos glTF Validator: "
            f"{counts['numErrors']} error(s), {counts['numWarnings']} warning(s)"
        )
    if severe_messages:
        raise PackageError("GLB rejected because validator messages contradict zero issue counts")
    info = report.get("info")
    if not isinstance(info, dict) or info.get("version") != "2.0":
        raise PackageError("Khronos glTF Validator did not confirm glTF 2.0")
    for field, minimum in (
        ("animationCount", 0),
        ("materialCount", 0),
        ("totalVertexCount", 1),
        ("totalTriangleCount", 1),
    ):
        count = info.get(field)
        if not isinstance(count, int) or isinstance(count, bool) or count < minimum:
            raise PackageError(
                f"Khronos glTF Validator info.{field} must be an integer >= {minimum}"
            )
    return issues


def _runtime_geometry_from_validator(
    report: Mapping[str, Any], *, texture_count: int
) -> dict[str, int]:
    info = report["info"]
    return {
        "vertex_count": int(info["totalVertexCount"]),
        "triangle_count": int(info["totalTriangleCount"]),
        "material_count": int(info["materialCount"]),
        "texture_count": texture_count,
    }


def _normalize_blender_version(value: Any) -> str:
    if not isinstance(value, str):
        raise PackageError("blender-build.json must include blender_version")
    match = re.match(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?", value)
    if match is None:
        raise PackageError(f"invalid Blender version in build summary: {value!r}")
    return match.group(0)


def _budget_violations(
    inspection: Mapping[str, Any], profile: Mapping[str, Any], glb_bytes: int
) -> list[str]:
    budgets = profile["budgets"]
    geometry = inspection["geometry"]
    materials = inspection["materials"]
    textures = inspection["textures"]
    measured = {
        "triangle_count": geometry["triangle_count"],
        "vertex_count": geometry["vertex_count"],
        "material_count": materials["count"],
        "texture_count": textures["count"],
        "texture_max_dimension_px": textures["max_dimension_px"],
        "packed_texture_bytes": textures["total_bytes"],
        "glb_bytes": glb_bytes,
    }
    return [
        f"{name}={value} exceeds web-v1 maximum {budgets[name]}"
        for name, value in measured.items()
        if value > budgets[name]
    ]


def _runtime_budget_violations(
    validator_report: Mapping[str, Any], profile: Mapping[str, Any]
) -> list[str]:
    budgets = profile["budgets"]
    info = validator_report["info"]
    measured = {
        "vertex_count": info["totalVertexCount"],
        "triangle_count": info["totalTriangleCount"],
        "material_count": info["materialCount"],
    }
    return [
        f"runtime {name}={value} exceeds web-v1 maximum {budgets[name]}"
        for name, value in measured.items()
        if value > budgets[name]
    ]


def _stable_coordinate(value: float) -> float:
    normalized = round(float(value), 12)
    return 0.0 if normalized == 0 else normalized


def _source_position_to_runtime(position: list[float]) -> list[float]:
    """Map Blender (X, Y, Z) into glTF runtime (X, Z, -Y)."""

    x, y, z = position
    return [_stable_coordinate(x), _stable_coordinate(z), _stable_coordinate(-y)]


def _source_bounds_to_runtime(bounds: Mapping[str, Any]) -> dict[str, list[float]]:
    minimum = bounds["minimum"]
    maximum = bounds["maximum"]
    runtime_minimum = _source_position_to_runtime([minimum[0], maximum[1], minimum[2]])
    runtime_maximum = _source_position_to_runtime([maximum[0], minimum[1], maximum[2]])
    return {
        "minimum": runtime_minimum,
        "maximum": runtime_maximum,
        "dimensions": [
            _stable_coordinate(high - low)
            for low, high in zip(runtime_minimum, runtime_maximum, strict=True)
        ],
    }


def _multiply_quaternions(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def _source_quaternion_to_runtime(quaternion: list[float]) -> list[float]:
    """Change an XYZW rotation basis from Blender space to glTF space."""

    half_sqrt = math.sqrt(0.5)
    basis = (-half_sqrt, 0.0, 0.0, half_sqrt)
    inverse = (half_sqrt, 0.0, 0.0, half_sqrt)
    source = tuple(float(component) for component in quaternion)
    runtime = _multiply_quaternions(_multiply_quaternions(basis, source), inverse)
    length = math.sqrt(sum(component * component for component in runtime))
    if not math.isfinite(length) or length == 0:
        raise PackageError("anchor quaternion cannot be converted into runtime coordinates")
    return [_stable_coordinate(component / length) for component in runtime]


def _source_anchors_to_runtime(anchors: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for anchor in anchors:
        converted.append(
            {
                **anchor,
                "position_m": _source_position_to_runtime(anchor["position_m"]),
                "rotation_xyzw": _source_quaternion_to_runtime(anchor["rotation_xyzw"]),
            }
        )
    return converted


def _source_collisions_to_runtime(
    collisions: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            **collision,
            "bounds_m": _source_bounds_to_runtime(collision["bounds_m"]),
        }
        for collision in collisions
    ]


def _artifact_from_path(
    path: Path,
    *,
    role: str,
    file_name: str,
    media_type: str,
) -> dict[str, Any]:
    digest = sha256_file(path)
    return {
        "role": role,
        "file_name": file_name,
        "media_type": media_type,
        "sha256": digest,
        "bytes": path.stat().st_size,
        "uri": f"/{object_key(digest)}",
    }


def _artifact_from_json(
    value: Any,
    *,
    role: str,
    file_name: str,
) -> dict[str, Any]:
    payload = pretty_json_bytes(value)
    digest = sha256_bytes(payload)
    return {
        "role": role,
        "file_name": file_name,
        "media_type": "application/json",
        "sha256": digest,
        "bytes": len(payload),
        "uri": f"/{object_key(digest)}",
    }


def _media_type(path: Path) -> str:
    return {
        ".blend": "application/x-blender",
        ".glb": "model/gltf-binary",
        ".json": "application/json",
        ".md": "text/markdown",
        ".png": "image/png",
        ".txt": "text/plain",
    }.get(path.suffix.lower(), "application/octet-stream")


def _catalog_evidence_root(
    provenance_path: Path,
    provenance: Mapping[str, Any],
) -> Path:
    """Return the sole local tree from which authored legal evidence may be read."""

    absolute_provenance = Path(os.path.abspath(provenance_path))
    asset = provenance.get("asset")
    if not isinstance(asset, Mapping):
        raise PackageError("provenance asset identity is required before resolving evidence")
    asset_id = asset.get("id")
    version = asset.get("version")
    version_directory = absolute_provenance.parent
    asset_directory = version_directory.parent
    catalog_root = asset_directory.parent
    if (
        absolute_provenance.name != "provenance.json"
        or not isinstance(asset_id, str)
        or not isinstance(version, str)
        or version_directory.name != version
        or asset_directory.name != asset_id
        or catalog_root.name != "catalog"
    ):
        raise PackageError(
            "authored provenance must be stored at catalog/<asset-id>/<version>/provenance.json"
        )

    for path in (catalog_root, asset_directory, version_directory, absolute_provenance):
        if path.is_symlink():
            raise PackageError(f"catalog provenance path must not use symlinks: {path}")

    evidence_root = catalog_root / "evidence"
    if evidence_root.is_symlink():
        raise PackageError(f"catalog evidence root must not be a symlink: {evidence_root}")
    if not evidence_root.is_dir():
        raise PackageError(f"catalog evidence root does not exist: {evidence_root}")
    return evidence_root


def _resolve_local_evidence(
    provenance_path: Path,
    uri: Any,
    *,
    evidence_root: Path,
) -> Path:
    if not isinstance(uri, str) or not uri or "\\" in uri:
        raise PackageError("provenance evidence URI must be a non-empty local path")
    parsed = urlsplit(uri)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or uri.startswith("/"):
        raise PackageError(f"provenance evidence must use a local relative URI: {uri!r}")
    uri_parts = Path(uri).parts
    if (
        len(uri_parts) != 4
        or uri_parts[:3] != ("..", "..", "evidence")
        or uri_parts[-1] in {"", ".", ".."}
    ):
        raise PackageError("provenance evidence must be ../../evidence/<file>")

    root = Path(os.path.abspath(evidence_root))
    try:
        candidate = Path(os.path.abspath(provenance_path.parent / uri))
    except (OSError, RuntimeError, ValueError) as error:
        raise PackageError(f"provenance evidence path is invalid: {uri!r}") from error
    if not candidate.is_relative_to(root):
        raise PackageError(f"provenance evidence escapes the catalog evidence root: {uri!r}")

    relative = candidate.relative_to(root)
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise PackageError(f"provenance evidence must not use symlinks: {uri!r}")

    try:
        resolved_root = root.resolve(strict=True)
        resolved_candidate = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise PackageError(f"provenance evidence does not exist: {uri!r}") from error
    if not resolved_candidate.is_relative_to(resolved_root):
        raise PackageError(f"provenance evidence escapes the catalog evidence root: {uri!r}")
    if not resolved_candidate.is_file():
        raise PackageError(f"provenance evidence is not a regular file: {uri!r}")
    if resolved_candidate.stat().st_size <= 0:
        raise PackageError(f"provenance evidence is empty: {uri!r}")
    return resolved_candidate


def _publishable_provenance(
    provenance: Mapping[str, Any],
    provenance_path: Path,
) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    """Resolve, hash, and content-address every legal-evidence reference."""

    evidence_root = _catalog_evidence_root(provenance_path, provenance)
    public = json.loads(json.dumps(provenance))
    evidence_files: list[tuple[Path, dict[str, Any]]] = []
    published_by_authored_uri: dict[str, str] = {}
    for index, evidence in enumerate(public["evidence"]):
        authored_uri = evidence["uri"]
        path = _resolve_local_evidence(
            provenance_path,
            authored_uri,
            evidence_root=evidence_root,
        )
        expected_digest = evidence.get("sha256")
        if not isinstance(expected_digest, str):
            raise PackageError(f"provenance evidence {authored_uri!r} must declare sha256")
        actual_digest = sha256_file(path)
        _require_equal(
            f"provenance evidence hash for {authored_uri}", expected_digest, actual_digest
        )
        artifact = _artifact_from_path(
            path,
            role="evidence",
            file_name=f"evidence-{index + 1:02d}-{path.name}",
            media_type=_media_type(path),
        )
        evidence["uri"] = artifact["uri"]
        published_by_authored_uri[authored_uri] = artifact["uri"]
        evidence_files.append((path, artifact))

    for dependency in public["dependencies"]:
        authored_uri = dependency["evidence_uri"]
        published_uri = published_by_authored_uri.get(authored_uri)
        if published_uri is None:
            raise PackageError(
                f"dependency evidence_uri {authored_uri!r} must reference an item in evidence"
            )
        dependency["evidence_uri"] = published_uri

    require_valid_document("provenance", public)
    return public, evidence_files


def _build_evidence_artifact(path: Path, *, file_name: str) -> dict[str, Any]:
    return _artifact_from_path(
        path,
        role="build_evidence",
        file_name=file_name,
        media_type=_media_type(path),
    )


def _write_json_immutable(path: Path, value: Any) -> None:
    expected = pretty_json_bytes(value)
    if path.exists():
        if not path.is_file() or path.read_bytes() != expected:
            raise FileExistsError(f"immutable generated document already differs: {path}")
        return
    write_json_atomic(path, value)


def _require_nonoverlapping(
    input_directory: Path,
    output_directory: Path,
    *,
    input_option: str = "--blender-output",
    output_option: str = "--output",
) -> None:
    source = input_directory.resolve()
    destination = output_directory.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise PackageError(f"{output_option} and {input_option} must be separate directory trees")


def _verified_blender_output(
    directory: Path,
    *,
    build_label: str,
) -> tuple[dict[str, Any], dict[str, Path]]:
    summary = _read_object(directory / "blender-build.json", f"{build_label} build summary")
    outputs = summary.get("outputs")
    if not isinstance(outputs, Mapping):
        raise PackageError(f"{build_label} blender-build.json outputs must be an object")
    verified = {
        name: _verify_summary_output(
            directory,
            outputs,
            name,
            build_label=build_label,
        )
        for name in REQUIRED_BLENDER_OUTPUTS
    }
    return summary, verified


def _require_exact_file_match(name: str, primary_path: Path, comparison_path: Path) -> str:
    primary_bytes = primary_path.stat().st_size
    comparison_bytes = comparison_path.stat().st_size
    if comparison_bytes != primary_bytes:
        raise PackageError(
            f"reproducibility mismatch for {name}: "
            f"expected {primary_bytes} bytes, got {comparison_bytes} bytes"
        )
    primary_hash = sha256_file(primary_path)
    comparison_hash = sha256_file(comparison_path)
    if comparison_hash != primary_hash:
        raise PackageError(
            f"reproducibility mismatch for {name}: "
            f"expected sha256 {primary_hash}, got {comparison_hash}"
        )
    return primary_hash


def _paeth_predictor(left: int, above: int, upper_left: int) -> int:
    candidate = left + above - upper_left
    left_distance = abs(candidate - left)
    above_distance = abs(candidate - above)
    upper_left_distance = abs(candidate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _png_pixel_digest(path: Path) -> str:
    """Validate an 8-bit RGBA PNG and hash its decoded pixels, not its encoding."""

    try:
        encoded_size = path.stat().st_size
        if encoded_size > 64 * 1024 * 1024:
            raise PackageError(f"preview PNG exceeds the 64 MiB encoded-size safety limit: {path}")
        payload = path.read_bytes()
    except OSError as error:
        raise PackageError(f"cannot read preview PNG at {path}: {error}") from error
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PackageError(f"preview is not a valid PNG: {path}")

    offset = 8
    header: bytes | None = None
    compressed = bytearray()
    saw_end = False
    chunk_index = 0
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise PackageError(f"preview PNG contains a truncated chunk: {path}")
        length = int.from_bytes(payload[offset : offset + 4], "big")
        chunk_type = payload[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        chunk_end = data_end + 4
        if chunk_end > len(payload):
            raise PackageError(f"preview PNG contains a truncated chunk: {path}")
        chunk_data = payload[data_start:data_end]
        expected_crc = int.from_bytes(payload[data_end:chunk_end], "big")
        actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise PackageError(f"preview PNG contains an invalid chunk checksum: {path}")
        if chunk_index == 0 and chunk_type != b"IHDR":
            raise PackageError(f"preview PNG must begin with IHDR: {path}")
        if chunk_type == b"IHDR":
            if header is not None or len(chunk_data) != 13:
                raise PackageError(f"preview PNG contains an invalid IHDR chunk: {path}")
            header = chunk_data
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            if chunk_data:
                raise PackageError(f"preview PNG contains an invalid IEND chunk: {path}")
            saw_end = True
            if chunk_end != len(payload):
                raise PackageError(f"preview PNG contains data after IEND: {path}")
        offset = chunk_end
        chunk_index += 1

    if header is None or not compressed or not saw_end:
        raise PackageError(f"preview PNG is missing required chunks: {path}")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", header
    )
    if (
        width <= 0
        or height <= 0
        or bit_depth != 8
        or color_type != 6
        or compression != 0
        or filtering != 0
        or interlace != 0
    ):
        raise PackageError(
            "preview PNG must be non-interlaced 8-bit RGBA with standard compression and "
            f"filtering: {path}"
        )
    row_bytes = width * 4
    expected_size = height * (row_bytes + 1)
    if expected_size > 64 * 1024 * 1024:
        raise PackageError(f"preview PNG exceeds the 64 MiB decoded-pixel safety limit: {path}")
    decompressor = zlib.decompressobj()
    try:
        filtered = decompressor.decompress(bytes(compressed), expected_size + 1)
        pending = decompressor.unconsumed_tail
        while pending and not decompressor.eof:
            more = decompressor.decompress(pending, 1)
            if more:
                filtered += more
                break
            next_pending = decompressor.unconsumed_tail
            if len(next_pending) >= len(pending):
                break
            pending = next_pending
    except zlib.error as error:
        raise PackageError(f"preview PNG image data cannot be decompressed: {path}") from error
    if (
        len(filtered) != expected_size
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise PackageError(f"preview PNG decoded data has an invalid size: {path}")

    decoded = bytearray()
    previous = bytearray(row_bytes)
    cursor = 0
    for _row in range(height):
        filter_type = filtered[cursor]
        cursor += 1
        current = bytearray(filtered[cursor : cursor + row_bytes])
        cursor += row_bytes
        if filter_type not in range(5):
            raise PackageError(f"preview PNG uses an invalid row filter: {path}")
        for index in range(row_bytes):
            left = current[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 1:
                current[index] = (current[index] + left) & 0xFF
            elif filter_type == 2:
                current[index] = (current[index] + above) & 0xFF
            elif filter_type == 3:
                current[index] = (current[index] + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                current[index] = (current[index] + _paeth_predictor(left, above, upper_left)) & 0xFF
        decoded.extend(current)
        previous = current

    return sha256_bytes(struct.pack(">II", width, height) + decoded)


def _normalized_inspection(inspection: Mapping[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(inspection))
    normalized["source_sha256"] = "<normalized-source-sha256>"
    return normalized


def _normalized_build_summary(
    summary: Mapping[str, Any],
    *,
    volatile_outputs: set[str],
) -> dict[str, Any]:
    normalized = json.loads(json.dumps(summary))
    outputs = normalized.get("outputs")
    if not isinstance(outputs, dict):
        raise PackageError("Blender build summary outputs must be an object")
    for name in volatile_outputs:
        if name not in outputs:
            raise PackageError(f"Blender build summary does not describe {name}")
        outputs[name] = {"documented_nondeterminism": name}
    return normalized


def _require_reproduced_build(
    *,
    primary_directory: Path,
    primary_summary: Mapping[str, Any],
    primary_files: Mapping[str, Path],
    comparison_directory: Path,
) -> ReproducibilityResult:
    """Classify an independent Blender result using exact and semantic evidence."""

    comparison_summary, comparison_files = _verified_blender_output(
        comparison_directory,
        build_label="comparison Blender",
    )
    primary_inspection = _read_object(primary_files["inspection.json"], "inspection")
    comparison_inspection = _read_object(
        comparison_files["inspection.json"],
        "comparison inspection",
    )
    require_valid_document("inspection", comparison_inspection)
    _require_equal(
        "comparison inspection source hash",
        comparison_inspection.get("source_sha256"),
        sha256_file(comparison_files["source.blend"]),
    )

    exact_hashes = {
        name: _require_exact_file_match(name, primary_files[name], comparison_files[name])
        for name in EXACT_REPRODUCIBLE_OUTPUTS
    }
    primary_source_hash = sha256_file(primary_files["source.blend"])
    comparison_source_hash = sha256_file(comparison_files["source.blend"])
    source_is_exact = (
        primary_source_hash == comparison_source_hash
        and primary_files["source.blend"].stat().st_size
        == comparison_files["source.blend"].stat().st_size
    )

    normalized_primary_inspection = _normalized_inspection(primary_inspection)
    normalized_comparison_inspection = _normalized_inspection(comparison_inspection)
    if source_is_exact:
        _require_exact_file_match(
            "inspection.json",
            primary_files["inspection.json"],
            comparison_files["inspection.json"],
        )
    elif not _same_json(normalized_primary_inspection, normalized_comparison_inspection):
        raise PackageError(
            "reproducibility mismatch for inspection.json outside documented source_sha256 "
            "nondeterminism"
        )

    primary_preview_digest = _png_pixel_digest(primary_files["preview.png"])
    comparison_preview_digest = _png_pixel_digest(comparison_files["preview.png"])
    if comparison_preview_digest != primary_preview_digest:
        raise PackageError("reproducibility mismatch for preview.png decoded RGBA pixels")
    preview_is_exact = (
        sha256_file(primary_files["preview.png"]) == sha256_file(comparison_files["preview.png"])
        and primary_files["preview.png"].stat().st_size
        == comparison_files["preview.png"].stat().st_size
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
        raise PackageError(
            "reproducibility mismatch for blender-build.json outside documented output descriptors"
        )

    if source_is_exact:
        status = "reproduced"
        allowed = (PREVIEW_NONDETERMINISM, SUMMARY_NONDETERMINISM) if not preview_is_exact else ()
    else:
        status = "known-nondeterminism"
        allowed = (
            SOURCE_NONDETERMINISM,
            INSPECTION_NONDETERMINISM,
            PREVIEW_NONDETERMINISM,
            SUMMARY_NONDETERMINISM,
        )

    comparison_key = sha256_json(
        {
            "classification": status,
            "contract": "neuralstock-reproducibility-v0.2",
            "inspection": sha256_json(normalized_comparison_inspection),
            "model_glb": exact_hashes["model.glb"],
            "preview_pixels": comparison_preview_digest,
            "source_semantics": exact_hashes["blender-details.json"],
            "summary": sha256_json(normalized_comparison_summary),
        }
    )
    return ReproducibilityResult(
        status=status,
        allowed_nondeterminism=allowed,
        comparison_build_id=f"comparison_{comparison_key[:24]}",
    )


def package_asset(
    *,
    intent_path: str | Path,
    provenance_path: str | Path,
    blender_output: str | Path,
    output: str | Path,
    generated_at: str,
    image_digest: str,
    parameter_values: Mapping[str, Any],
    platform: str = "linux/amd64",
    comparison_blender_output: str | Path | None = None,
    validator_runner: ValidatorRunner | None = None,
) -> PackageResult:
    """Validate and package one immutable asset version without mutating inputs."""

    intent_file = Path(intent_path)
    provenance_file = Path(provenance_path)
    blender_directory = Path(blender_output)
    output_directory = Path(output)
    _require_nonoverlapping(blender_directory, output_directory)
    comparison_directory = (
        Path(comparison_blender_output) if comparison_blender_output is not None else None
    )
    if comparison_directory is not None:
        _require_nonoverlapping(
            comparison_directory,
            output_directory,
            input_option="--comparison-blender-output",
        )
        _require_nonoverlapping(
            blender_directory,
            comparison_directory,
            output_option="--comparison-blender-output",
        )
    completed_at = _require_timestamp(generated_at, "--generated-at")
    if not image_digest.startswith("sha256:"):
        raise PackageError("--image-digest must use the sha256:<64 lowercase hex> form")
    try:
        normalized_image_hash = require_sha256(image_digest.removeprefix("sha256:"))
    except ValueError as error:
        raise PackageError("--image-digest must use the sha256:<64 lowercase hex> form") from error
    if image_digest != f"sha256:{normalized_image_hash}":
        raise PackageError("--image-digest must use the sha256:<64 lowercase hex> form")
    if platform not in {"linux/amd64", "linux/arm64"}:
        raise PackageError(f"unsupported build platform: {platform!r}")

    intent = _read_object(intent_file, "asset intent")
    provenance = _read_object(provenance_file, "provenance")
    require_valid_document("asset.intent", intent)
    require_valid_document("provenance", provenance)
    asset_id = intent["id"]
    version = intent["version"]
    target_profile = intent["target_profile"]
    expected_asset = {"id": asset_id, "version": version}
    _require_equal("provenance asset", provenance.get("asset"), expected_asset)
    public_provenance, evidence_files = _publishable_provenance(provenance, provenance_file)

    summary, verified = _verified_blender_output(blender_directory, build_label="Blender")
    inspection = _read_object(verified["inspection.json"], "inspection")
    blender_details = _read_object(verified["blender-details.json"], "Blender details")
    require_valid_document("inspection", inspection)

    reproducibility_result = None
    if comparison_directory is not None:
        reproducibility_result = _require_reproduced_build(
            primary_directory=blender_directory,
            primary_summary=summary,
            primary_files=verified,
            comparison_directory=comparison_directory,
        )

    _require_equal("inspection asset", inspection.get("asset"), expected_asset)
    _require_equal("Blender summary asset", summary.get("asset"), expected_asset)
    _require_equal("inspection target profile", inspection.get("target_profile"), target_profile)
    _require_equal(
        "Blender profile status",
        summary.get("profile_status"),
        inspection["profile_validation"]["status"],
    )
    _require_equal("provenance license", provenance.get("license"), intent["license"])

    source_hash = sha256_file(verified["source.blend"])
    _require_equal("intent source hash", intent["source"]["sha256"], source_hash)
    _require_equal("provenance source hash", provenance.get("source_sha256"), source_hash)
    _require_equal("inspection source hash", inspection.get("source_sha256"), source_hash)

    inspection_parameters = inspection["parameters"]
    _require_equal(
        "inspection Geometry Nodes group",
        inspection_parameters["node_group"],
        intent["blender_source"]["geometry_node_group"],
    )
    if not _same_json(inspection_parameters["inputs"], intent["blender_source"]["parameters"]):
        raise PackageError("inspection parameter declarations differ from asset intent")
    actual_anchors = {anchor["name"] for anchor in inspection["anchors"]}
    missing_anchors = sorted(set(intent["required_anchors"]) - actual_anchors)
    if missing_anchors:
        raise PackageError(f"inspection is missing required anchors: {', '.join(missing_anchors)}")

    profile_validation = inspection["profile_validation"]
    if profile_validation["status"] != "pass" or any(
        check["status"] != "pass" for check in profile_validation["checks"]
    ):
        raise PackageError("inspection did not pass every web-v1 profile check")
    if not inspection["textures"]["all_packed"]:
        raise PackageError("inspection reports unpacked texture resources")
    unresolved_rights = [
        name
        for name, state in provenance["rights_review"].items()
        if name != "notes" and state == "needs-review"
    ]
    if unresolved_rights:
        names = ", ".join(unresolved_rights)
        raise PackageError(f"provenance has unresolved rights review: {names}")

    parameters = dict(parameter_values)
    _validate_parameter_values(parameters, intent["blender_source"]["parameters"])
    summary_parameters = summary.get("parameters")
    if not isinstance(summary_parameters, dict) or not _same_json(summary_parameters, parameters):
        raise PackageError("explicit parameter values differ from blender-build.json")
    _validate_geometry_node_parameter_details(
        blender_details,
        node_group=intent["blender_source"]["geometry_node_group"],
        definitions=intent["blender_source"]["parameters"],
        parameter_values=parameters,
    )

    profile_path = data_path("profiles", f"{target_profile}.json")
    profile = _read_object(profile_path, "profile")
    require_valid_document("profile", profile)
    violations = _budget_violations(inspection, profile, verified["model.glb"].stat().st_size)
    if violations:
        raise PackageError("asset exceeds target-profile budget: " + "; ".join(violations))

    runner = validator_runner or run_gltf_validator
    validation_report = runner(verified["model.glb"])
    if not isinstance(validation_report, dict):
        raise PackageError("Khronos glTF Validator runner must return an object")
    issues = _validate_validator_report(validation_report, "model.glb")
    runtime_violations = _runtime_budget_violations(validation_report, profile)
    if runtime_violations:
        raise PackageError(
            "runtime GLB exceeds target-profile budget: " + "; ".join(runtime_violations)
        )
    validation_report = dict(validation_report)
    validation_report.pop("validatedAt", None)
    validation_report["validatedAt"] = completed_at

    patched_inspection = json.loads(json.dumps(inspection))
    patched_inspection["gltf_validation"] = {
        "validator_version": validation_report["validatorVersion"],
        "status": "pass",
        "errors": issues["numErrors"],
        "warnings": issues["numWarnings"],
    }
    require_valid_document("inspection", patched_inspection)

    source_artifact = _artifact_from_path(
        verified["source.blend"],
        role="source",
        file_name="source.blend",
        media_type="application/x-blender",
    )
    intent_artifact = _artifact_from_path(
        intent_file,
        role="manifest",
        file_name="asset.intent.json",
        media_type="application/json",
    )
    authored_provenance_artifact = _artifact_from_path(
        provenance_file,
        role="provenance",
        file_name="provenance.json",
        media_type="application/json",
    )
    provenance_artifact = _artifact_from_json(
        public_provenance,
        role="provenance",
        file_name="provenance.json",
    )
    runtime_artifact = _artifact_from_path(
        verified["model.glb"],
        role="runtime",
        file_name="model.glb",
        media_type="model/gltf-binary",
    )
    preview_artifact = _artifact_from_path(
        verified["preview.png"],
        role="preview",
        file_name="preview.png",
        media_type="image/png",
    )
    inspection_artifact = _artifact_from_json(
        patched_inspection,
        role="inspection",
        file_name="inspection.json",
    )
    validator_artifact = _artifact_from_json(
        validation_report,
        role="inspection",
        file_name="gltf-validation.json",
    )

    toolchain = _toolchain_document()
    toolchain_sha256 = sha256_json(toolchain)
    toolchain_artifact = _artifact_from_json(
        toolchain,
        role="build_evidence",
        file_name="toolchain.json",
    )
    profile_artifact = _artifact_from_path(
        profile_path,
        role="build_evidence",
        file_name=f"profile-{target_profile}.json",
        media_type="application/json",
    )
    primary_evidence_files = [
        (
            verified["blender-details.json"],
            _build_evidence_artifact(
                verified["blender-details.json"], file_name="blender-details.json"
            ),
        ),
        (
            blender_directory / "blender-build.json",
            _build_evidence_artifact(
                blender_directory / "blender-build.json", file_name="blender-build.json"
            ),
        ),
    ]
    comparison_evidence_files: list[tuple[Path, dict[str, Any]]] = []
    if comparison_directory is not None:
        _comparison_summary, comparison_files = _verified_blender_output(
            comparison_directory,
            build_label="comparison Blender evidence",
        )
        for name, path in [
            *sorted(comparison_files.items()),
            ("blender-build.json", comparison_directory / "blender-build.json"),
        ]:
            comparison_evidence_files.append(
                (
                    path,
                    _build_evidence_artifact(path, file_name=f"comparison-{name}"),
                )
            )

    normalized_parameters_sha256 = sha256_json(parameters)
    build_key = sha256_json(
        {
            "builder": {
                "tool": "neuralstock-package",
                "version": __version__,
                "code_sha256": toolchain_sha256,
            },
            "evidence_sha256": sorted(artifact["sha256"] for _path, artifact in evidence_files),
            "image_digest": image_digest,
            "intent_sha256": intent_artifact["sha256"],
            "normalized_parameters_sha256": normalized_parameters_sha256,
            "platform": platform,
            "profile_sha256": profile_artifact["sha256"],
            "provenance_sha256": authored_provenance_artifact["sha256"],
            "source_sha256": source_hash,
            "target_profile": target_profile,
            "validator_version": GLTF_VALIDATOR_VERSION,
        }
    )
    started_at = _require_timestamp(summary.get("generated_at"), "Blender generated_at")
    if datetime.fromisoformat(completed_at.replace("Z", "+00:00")) < datetime.fromisoformat(
        started_at.replace("Z", "+00:00")
    ):
        raise PackageError("--generated-at cannot precede the Blender build timestamp")

    info = validation_report["info"]
    blender_version = _normalize_blender_version(summary.get("blender_version"))
    build_receipt: dict[str, Any] = {
        "$schema": "https://schemas.neuralstock.ai/v0.2/build-receipt.schema.json",
        "schema_version": "0.2",
        "document_type": "build-receipt",
        "generated": True,
        "asset": expected_asset,
        "build_id": f"build_{build_key[:24]}",
        "build_key": build_key,
        "started_at": started_at,
        "completed_at": completed_at,
        "source_sha256": source_hash,
        "parameters": parameters,
        "normalized_parameters_sha256": normalized_parameters_sha256,
        "target_profile": target_profile,
        "builder": {
            "tool": "neuralstock-package",
            "version": __version__,
            "code_sha256": toolchain_sha256,
        },
        "environment": {
            "blender_version": blender_version,
            "image_digest": image_digest,
            "platform": platform,
        },
        "export": {
            "format": "GLB",
            "geometry_compression": profile["runtime"]["geometry_compression"],
            "materials": "PBR-metallic-roughness",
            "animations": bool(info.get("animationCount", 0)),
        },
        "inputs": [
            source_artifact,
            intent_artifact,
            authored_provenance_artifact,
            profile_artifact,
            toolchain_artifact,
            *[artifact for _path, artifact in evidence_files],
        ],
        "outputs": [
            runtime_artifact,
            inspection_artifact,
            validator_artifact,
            preview_artifact,
            provenance_artifact,
            *[artifact for _path, artifact in primary_evidence_files],
            *[artifact for _path, artifact in comparison_evidence_files],
        ],
        "validation": {
            "status": "pass",
            "inspection_sha256": inspection_artifact["sha256"],
        },
        "reproducibility": (
            {
                "status": reproducibility_result.status,
                "allowed_nondeterminism": list(reproducibility_result.allowed_nondeterminism),
                "comparison_build_id": reproducibility_result.comparison_build_id,
            }
            if reproducibility_result is not None
            else {
                "status": "not-yet-reproduced",
                "allowed_nondeterminism": [],
            }
        ),
    }
    require_valid_document("build-receipt", build_receipt)
    receipt_artifact = _artifact_from_json(
        build_receipt,
        role="build_receipt",
        file_name="build-receipt.json",
    )

    asset: dict[str, Any] = {
        "$schema": "https://schemas.neuralstock.ai/v0.2/asset.schema.json",
        "schema_version": "0.2",
        "document_type": "asset",
        "generated": True,
        "id": asset_id,
        "version": version,
        "name": intent["name"],
        "description": intent["description"],
        "publication_status": "published",
        "published_at": completed_at,
        "license": intent["license"],
        "target_profile": target_profile,
        "coordinate_system": {
            "unit": "meter",
            "meters_per_unit": 1,
            "up_axis": "Y",
            "forward_axis": "+Z",
            "handedness": "right",
            "space": "asset-local",
        },
        "semantics": intent["semantics"],
        "bounds_m": _source_bounds_to_runtime(patched_inspection["bounds_m"]),
        "geometry": _runtime_geometry_from_validator(
            validation_report,
            texture_count=patched_inspection["textures"]["count"],
        ),
        "source_generator": {
            "geometry_node_group": intent["blender_source"]["geometry_node_group"],
            "parameters": intent["blender_source"]["parameters"],
        },
        "anchors": _source_anchors_to_runtime(patched_inspection["anchors"]),
        "collisions": _source_collisions_to_runtime(patched_inspection["collisions"]),
        "build_key": build_key,
        "artifacts": {
            "source": source_artifact,
            "runtime": runtime_artifact,
            "provenance": provenance_artifact,
            "inspection": inspection_artifact,
            "build_receipt": receipt_artifact,
            "previews": [preview_artifact],
        },
    }
    require_valid_document("asset", asset)

    generated_documents = {
        "provenance.json": public_provenance,
        "inspection.json": patched_inspection,
        "gltf-validation.json": validation_report,
        "toolchain.json": toolchain,
        "build-receipt.json": build_receipt,
    }
    for name, document in generated_documents.items():
        _write_json_immutable(output_directory / name, document)

    publish_plan = [
        (verified["source.blend"], source_artifact),
        (intent_file, intent_artifact),
        (provenance_file, authored_provenance_artifact),
        (profile_path, profile_artifact),
        *evidence_files,
        (verified["model.glb"], runtime_artifact),
        (verified["preview.png"], preview_artifact),
        (output_directory / "provenance.json", provenance_artifact),
        (output_directory / "inspection.json", inspection_artifact),
        (output_directory / "gltf-validation.json", validator_artifact),
        (output_directory / "toolchain.json", toolchain_artifact),
        *primary_evidence_files,
        *comparison_evidence_files,
        (output_directory / "build-receipt.json", receipt_artifact),
    ]
    for path, expected in publish_plan:
        published = publish_object(path, output_directory)
        if published.digest != expected["sha256"] or published.size_bytes != expected["bytes"]:
            raise PackageError(f"artifact changed while packaging: {path}")
    _write_json_immutable(output_directory / "asset.json", asset)

    return PackageResult(
        asset=asset,
        build_receipt=build_receipt,
        validation_report=validation_report,
        output=output_directory,
    )
