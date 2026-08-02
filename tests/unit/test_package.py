from __future__ import annotations

import json
import shutil
import struct
import zlib
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from neuralstock.canonical import (
    pretty_json_bytes,
    read_json,
    sha256_file,
    write_json_atomic,
)
from neuralstock.package import (
    GLTF_VALIDATOR_VERSION,
    PackageError,
    _publishable_provenance,
    package_asset,
)
from neuralstock.schema import project_root, require_valid_document

IMAGE_DIGEST = "sha256:" + "d" * 64
BUILD_TIME = "2026-08-01T12:00:00Z"
PACKAGE_TIME = "2026-08-01T12:10:00Z"


def minimal_glb(document: dict[str, Any] | None = None) -> bytes:
    binary = b""
    if document is None:
        binary = struct.pack(
            "<9f3H",
            -0.5,
            0.0,
            0.0,
            0.5,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0,
            1,
            2,
        )
        document = {
            "asset": {"version": "2.0"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
            "buffers": [{"byteLength": len(binary)}],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": 36, "target": 34962},
                {"buffer": 0, "byteOffset": 36, "byteLength": 6, "target": 34963},
            ],
            "accessors": [
                {
                    "bufferView": 0,
                    "componentType": 5126,
                    "count": 3,
                    "type": "VEC3",
                    "min": [-0.5, 0.0, 0.0],
                    "max": [0.5, 1.0, 0.0],
                },
                {
                    "bufferView": 1,
                    "componentType": 5123,
                    "count": 3,
                    "type": "SCALAR",
                },
            ],
        }
    payload = json.dumps(document, separators=(",", ":")).encode()
    padded = payload + b" " * ((-len(payload)) % 4)
    binary_padded = binary + b"\0" * ((-len(binary)) % 4)
    chunks = len(padded).to_bytes(4, "little") + (0x4E4F534A).to_bytes(4, "little") + padded
    if binary:
        chunks += (
            len(binary_padded).to_bytes(4, "little")
            + (0x004E4942).to_bytes(4, "little")
            + binary_padded
        )
    total = 12 + len(chunks)
    return b"glTF" + (2).to_bytes(4, "little") + total.to_bytes(4, "little") + chunks


def minimal_png(*, comment: bytes = b"primary", red: int = 96) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return len(data).to_bytes(4, "big") + kind + data + checksum.to_bytes(4, "big")

    width = 2
    height = 2
    header = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes((8, 6, 0, 0, 0))
    row = bytes((red, 32, 16, 255)) * width
    pixels = b"".join(b"\x00" + row for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"tEXt", b"Comment\x00" + comment)
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def valid_validator_report() -> dict[str, Any]:
    return {
        "uri": "model.glb",
        "mimeType": "model/gltf-binary",
        "validatorVersion": GLTF_VALIDATOR_VERSION,
        "issues": {
            "numErrors": 0,
            "numWarnings": 0,
            "numInfos": 0,
            "numHints": 0,
            "messages": [],
            "truncated": False,
        },
        "info": {
            "version": "2.0",
            "animationCount": 0,
            "materialCount": 1,
            "totalVertexCount": 1240,
            "totalTriangleCount": 2380,
        },
    }


def _fixture(name: str) -> dict[str, Any]:
    value = read_json(project_root() / "tests" / "fixtures" / "schemas" / "valid" / name)
    assert isinstance(value, dict)
    return value


def _summary_descriptor(path: Path) -> dict[str, Any]:
    return {"sha256": sha256_file(path), "bytes": path.stat().st_size}


def make_candidate(tmp_path: Path) -> dict[str, Any]:
    blender = tmp_path / "blender-output"
    blender.mkdir()

    parameters = {"width_meters": 1.0, "wood_style": "plain"}
    source = blender / "source.blend"
    source.write_bytes(b"synthetic Blender source fixture")
    source_hash = sha256_file(source)

    intent = _fixture("asset.intent.json")
    intent["source"]["sha256"] = source_hash
    provenance = _fixture("provenance.json")
    provenance["source_sha256"] = source_hash
    authored = tmp_path / "catalog" / provenance["asset"]["id"] / provenance["asset"]["version"]
    authored.mkdir(parents=True)
    evidence_name = Path(provenance["evidence"][0]["uri"]).name
    provenance["evidence"][0]["uri"] = f"../../evidence/{evidence_name}"
    evidence_path = authored / provenance["evidence"][0]["uri"]
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text("Fixture contributor CC0 attestation.\n", encoding="utf-8")
    provenance["evidence"][0]["sha256"] = sha256_file(evidence_path)
    inspection = _fixture("inspection.json")
    inspection["source_sha256"] = source_hash
    inspection["parameters"] = {
        "node_group": intent["blender_source"]["geometry_node_group"],
        "inputs": deepcopy(intent["blender_source"]["parameters"]),
    }

    intent_path = authored / "asset.intent.json"
    provenance_path = authored / "provenance.json"
    write_json_atomic(intent_path, intent)
    write_json_atomic(provenance_path, provenance)
    write_json_atomic(blender / "inspection.json", inspection)
    write_json_atomic(
        blender / "blender-details.json",
        {
            "geometry_nodes": [
                {
                    "object": "crate_body",
                    "modifier": "NS_Geometry",
                    "node_group": intent["blender_source"]["geometry_node_group"],
                    "inputs": [
                        {
                            "name": name,
                            "type": definition["type"],
                            "agent_safe": definition["agent_safe"],
                            "linked": True,
                            "default": definition["default"],
                            "value": parameters.get(name, definition["default"]),
                            **(
                                {
                                    "min": definition["minimum"],
                                    "max": definition["maximum"],
                                }
                                if definition["type"] in {"float", "integer"}
                                else {}
                            ),
                            **(
                                {"options": definition["options"]}
                                if definition["type"] == "enum"
                                else {}
                            ),
                        }
                        for name, definition in intent["blender_source"]["parameters"].items()
                    ],
                }
            ]
        },
    )
    (blender / "model.glb").write_bytes(minimal_glb())
    (blender / "preview.png").write_bytes(minimal_png())

    names = (
        "source.blend",
        "model.glb",
        "inspection.json",
        "blender-details.json",
        "preview.png",
    )
    summary = {
        "schema_version": "0.2",
        "tool": "neuralstock-blender",
        "blender_version": "4.5.12 LTS",
        "asset": {"id": intent["id"], "version": intent["version"]},
        "generated_at": BUILD_TIME,
        "parameters": parameters,
        "profile_status": "pass",
        "preview": {"width": 512, "height": 512},
        "outputs": {name: _summary_descriptor(blender / name) for name in names},
        "limitations": [],
    }
    write_json_atomic(blender / "blender-build.json", summary)
    return {
        "intent": intent_path,
        "provenance": provenance_path,
        "evidence": evidence_path,
        "blender": blender,
        "output": tmp_path / "package",
        "parameters": parameters,
    }


def rewrite_output_summary(blender_directory: Path, name: str) -> None:
    summary_path = blender_directory / "blender-build.json"
    summary = read_json(summary_path)
    summary["outputs"][name] = _summary_descriptor(blender_directory / name)
    write_json_atomic(summary_path, summary)


def rewrite_summary_hash(candidate: dict[str, Any], name: str) -> None:
    rewrite_output_summary(candidate["blender"], name)


def make_comparison(candidate: dict[str, Any], tmp_path: Path) -> Path:
    comparison = tmp_path / "comparison-blender-output"
    shutil.copytree(candidate["blender"], comparison)
    return comparison


def run_package(
    candidate: dict[str, Any],
    report: dict[str, Any] | None = None,
    *,
    comparison: Path | None = None,
):
    validation_report = report or valid_validator_report()
    return package_asset(
        intent_path=candidate["intent"],
        provenance_path=candidate["provenance"],
        blender_output=candidate["blender"],
        output=candidate["output"],
        generated_at=PACKAGE_TIME,
        image_digest=IMAGE_DIGEST,
        parameter_values=candidate["parameters"],
        comparison_blender_output=comparison,
        validator_runner=lambda _path: deepcopy(validation_report),
    )


def point_provenance_evidence(
    candidate: dict[str, Any],
    *,
    uri: str,
    path: Path,
) -> None:
    provenance = read_json(candidate["provenance"])
    provenance["evidence"][0]["uri"] = uri
    provenance["evidence"][0]["sha256"] = sha256_file(path)
    write_json_atomic(candidate["provenance"], provenance)
    candidate["evidence"] = path


def test_room_zero_catalog_evidence_resolves_only_from_shared_catalog_root() -> None:
    catalog_root = project_root() / "catalog"
    provenance_paths = sorted(catalog_root.glob("*/*/provenance.json"))

    assert len(provenance_paths) == 15
    for provenance_path in provenance_paths:
        provenance = read_json(provenance_path)
        public, evidence_files = _publishable_provenance(provenance, provenance_path)

        assert len(evidence_files) == len(provenance["evidence"])
        assert all(
            path.is_relative_to((catalog_root / "evidence").resolve())
            for path, _artifact in evidence_files
        )
        assert all(item["uri"].startswith("/objects/sha256/") for item in public["evidence"])


def test_package_rejects_evidence_file_symlink(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    evidence = candidate["evidence"]
    outside = tmp_path / "outside-attestation.md"
    outside.write_bytes(evidence.read_bytes())
    evidence.unlink()
    evidence.symlink_to(outside)

    with pytest.raises(PackageError, match="evidence must not use symlinks"):
        run_package(candidate)

    assert not candidate["output"].exists()


def test_package_rejects_nested_evidence_path(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    nested = candidate["evidence"].parent / "nested" / "attestation.md"
    nested.parent.mkdir()
    nested.write_text("Nested attestation.\n", encoding="utf-8")
    point_provenance_evidence(
        candidate,
        uri="../../evidence/nested/attestation.md",
        path=nested,
    )

    with pytest.raises(PackageError, match=r"evidence must be \.\./\.\./evidence/<file>"):
        run_package(candidate)

    assert not candidate["output"].exists()


def test_package_rejects_symlinked_catalog_evidence_root(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    evidence_root = candidate["evidence"].parent
    outside_root = tmp_path / "outside-evidence-root"
    evidence_root.rename(outside_root)
    evidence_root.symlink_to(outside_root, target_is_directory=True)

    with pytest.raises(PackageError, match="catalog evidence root must not be a symlink"):
        run_package(candidate)

    assert not candidate["output"].exists()


def test_package_rejects_evidence_traversal_outside_catalog_root(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    outside = tmp_path / "outside-attestation.md"
    outside.write_text("External attestation.\n", encoding="utf-8")
    point_provenance_evidence(
        candidate,
        uri="../../../outside-attestation.md",
        path=outside,
    )

    with pytest.raises(PackageError, match=r"evidence must be \.\./\.\./evidence/<file>"):
        run_package(candidate)

    assert not candidate["output"].exists()


def test_package_rejects_provenance_outside_catalog_layout(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    misplaced = tmp_path / "authored" / "provenance.json"
    misplaced.parent.mkdir()
    shutil.copy2(candidate["provenance"], misplaced)
    candidate["provenance"] = misplaced

    with pytest.raises(PackageError, match=r"catalog/<asset-id>/<version>/provenance\.json"):
        run_package(candidate)

    assert not candidate["output"].exists()


def test_package_emits_valid_content_addressed_documents_without_mutating_inputs(
    tmp_path: Path,
) -> None:
    candidate = make_candidate(tmp_path)
    authored_before = {name: candidate[name].read_bytes() for name in ("intent", "provenance")}

    result = run_package(candidate)

    assert result.validation_report["validatedAt"] == PACKAGE_TIME
    require_valid_document("inspection", read_json(result.output / "inspection.json"))
    require_valid_document("build-receipt", read_json(result.output / "build-receipt.json"))
    require_valid_document("asset", read_json(result.output / "asset.json"))
    assert result.asset["artifacts"]["runtime"]["uri"].startswith("/objects/sha256/")
    assert result.build_receipt["parameters"] == candidate["parameters"]
    assert result.build_receipt["environment"]["image_digest"] == IMAGE_DIGEST
    assert result.build_receipt["environment"]["blender_version"] == "4.5.12"
    assert len(result.build_receipt["builder"]["code_sha256"]) == 64
    assert result.build_receipt["reproducibility"] == {
        "status": "not-yet-reproduced",
        "allowed_nondeterminism": [],
    }
    assert result.asset["coordinate_system"] == {
        "unit": "meter",
        "meters_per_unit": 1,
        "up_axis": "Y",
        "forward_axis": "+Z",
        "handedness": "right",
        "space": "asset-local",
    }
    assert result.asset["bounds_m"] == {
        "minimum": [-0.4, 0.0, -0.3],
        "maximum": [0.4, 0.6, 0.3],
        "dimensions": [0.8, 0.6, 0.6],
    }
    assert result.asset["anchors"][0]["position_m"] == [0.0, 0.6, 0.0]
    assert result.asset["collisions"][0]["bounds_m"] == {
        "minimum": [-0.4, 0.0, -0.3],
        "maximum": [0.4, 0.6, 0.3],
        "dimensions": [0.8, 0.6, 0.6],
    }
    assert any(
        artifact["file_name"] == "gltf-validation.json"
        for artifact in result.build_receipt["outputs"]
    )
    assert any(artifact["role"] == "evidence" for artifact in result.build_receipt["inputs"])
    assert any(
        artifact["file_name"] == "comparison-blender-build.json"
        for artifact in run_package(
            {**candidate, "output": tmp_path / "package-with-comparison"},
            comparison=make_comparison(candidate, tmp_path),
        ).build_receipt["outputs"]
    )
    public_provenance = read_json(result.output / "provenance.json")
    assert public_provenance["evidence"][0]["uri"].startswith("/objects/sha256/")
    assert public_provenance["evidence"][0]["sha256"] == sha256_file(candidate["evidence"])

    descriptors = [
        *result.build_receipt["inputs"],
        *result.build_receipt["outputs"],
        result.asset["artifacts"]["build_receipt"],
    ]
    for descriptor in descriptors:
        object_path = result.output / descriptor["uri"].removeprefix("/")
        assert object_path.is_file()
        assert sha256_file(object_path) == descriptor["sha256"]
        assert object_path.stat().st_size == descriptor["bytes"]

    for name in ("inspection.json", "gltf-validation.json", "build-receipt.json", "asset.json"):
        path = result.output / name
        assert path.read_bytes() == pretty_json_bytes(read_json(path))
    assert {name: candidate[name].read_bytes() for name in authored_before} == authored_before

    repeated = run_package(candidate)
    assert repeated.asset == result.asset
    assert repeated.build_receipt == result.build_receipt


def test_package_marks_exact_independent_blender_result_reproduced(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)

    result = run_package(candidate, comparison=comparison)

    reproducibility = result.build_receipt["reproducibility"]
    assert reproducibility["status"] == "reproduced"
    assert reproducibility["allowed_nondeterminism"] == []
    assert reproducibility["comparison_build_id"].startswith("comparison_")
    require_valid_document("build-receipt", result.build_receipt)

    repeated = run_package(candidate, comparison=comparison)
    assert (
        repeated.build_receipt["reproducibility"]["comparison_build_id"]
        == reproducibility["comparison_build_id"]
    )


def test_package_accepts_exact_preview_pixels_with_different_png_encoding(
    tmp_path: Path,
) -> None:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    (comparison / "preview.png").write_bytes(minimal_png(comment=b"comparison encoding"))
    rewrite_output_summary(comparison, "preview.png")

    result = run_package(candidate, comparison=comparison)

    reproducibility = result.build_receipt["reproducibility"]
    assert reproducibility["status"] == "reproduced"
    assert len(reproducibility["allowed_nondeterminism"]) == 2
    assert reproducibility["allowed_nondeterminism"][0].startswith("preview.png:")
    assert reproducibility["allowed_nondeterminism"][1].startswith("blender-build.json:")

    (comparison / "preview.png").write_bytes(minimal_png(comment=b"third encoding"))
    rewrite_output_summary(comparison, "preview.png")
    candidate["output"] = tmp_path / "package-third-encoding"
    repeated = run_package(candidate, comparison=comparison)
    assert repeated.build_key == result.build_key
    assert (
        repeated.build_receipt["reproducibility"]["comparison_build_id"]
        == reproducibility["comparison_build_id"]
    )
    assert repeated.build_receipt != result.build_receipt


def test_package_classifies_semantically_identical_regenerated_source_as_known_nondeterminism(
    tmp_path: Path,
) -> None:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    source = comparison / "source.blend"
    source.write_bytes(b"synthetic Blender source with different session identifiers")
    comparison_source_hash = sha256_file(source)
    rewrite_output_summary(comparison, "source.blend")
    inspection_path = comparison / "inspection.json"
    inspection = read_json(inspection_path)
    inspection["source_sha256"] = comparison_source_hash
    write_json_atomic(inspection_path, inspection)
    rewrite_output_summary(comparison, "inspection.json")
    (comparison / "preview.png").write_bytes(minimal_png(comment=b"second render encoding"))
    rewrite_output_summary(comparison, "preview.png")

    result = run_package(candidate, comparison=comparison)

    reproducibility = result.build_receipt["reproducibility"]
    assert reproducibility["status"] == "known-nondeterminism"
    assert len(reproducibility["allowed_nondeterminism"]) == 4
    assert [item.split(":", 1)[0] for item in reproducibility["allowed_nondeterminism"]] == [
        "source.blend",
        "inspection.json",
        "preview.png",
        "blender-build.json",
    ]
    require_valid_document("build-receipt", result.build_receipt)


def test_package_refuses_same_size_reproducibility_hash_mismatch(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    model = comparison / "model.glb"
    changed = bytearray(model.read_bytes())
    changed[-1] ^= 1
    model.write_bytes(changed)
    rewrite_output_summary(comparison, "model.glb")

    with pytest.raises(PackageError, match=r"reproducibility mismatch for model\.glb.*sha256"):
        run_package(candidate, comparison=comparison)

    assert not candidate["output"].exists()


def test_package_refuses_reproducibility_byte_size_mismatch(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    model = comparison / "model.glb"
    model.write_bytes(model.read_bytes() + b"different size")
    rewrite_output_summary(comparison, "model.glb")

    with pytest.raises(PackageError, match=r"reproducibility mismatch for model\.glb.*bytes"):
        run_package(candidate, comparison=comparison)

    assert not candidate["output"].exists()


def test_package_validates_comparison_summary_before_comparing(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    (comparison / "preview.png").write_bytes(b"changed without updating its descriptor")

    with pytest.raises(PackageError, match=r"comparison Blender output hash for preview\.png"):
        run_package(candidate, comparison=comparison)

    assert not candidate["output"].exists()


def test_package_refuses_semantic_inspection_drift_in_regenerated_source(
    tmp_path: Path,
) -> None:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    source = comparison / "source.blend"
    source.write_bytes(b"another serialized Blender session")
    rewrite_output_summary(comparison, "source.blend")
    inspection_path = comparison / "inspection.json"
    inspection = read_json(inspection_path)
    inspection["source_sha256"] = sha256_file(source)
    inspection["geometry"]["triangle_count"] += 1
    write_json_atomic(inspection_path, inspection)
    rewrite_output_summary(comparison, "inspection.json")

    with pytest.raises(PackageError, match=r"inspection\.json outside documented"):
        run_package(candidate, comparison=comparison)

    assert not candidate["output"].exists()


def test_package_refuses_preview_pixel_drift(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    comparison = make_comparison(candidate, tmp_path)
    (comparison / "preview.png").write_bytes(minimal_png(comment=b"same format", red=97))
    rewrite_output_summary(comparison, "preview.png")

    with pytest.raises(PackageError, match=r"preview\.png decoded RGBA pixels"):
        run_package(candidate, comparison=comparison)

    assert not candidate["output"].exists()


def test_package_requires_comparison_to_be_a_separate_directory(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)

    with pytest.raises(PackageError, match="must be separate directory trees"):
        run_package(candidate, comparison=candidate["blender"])


@pytest.mark.parametrize(("field", "count"), [("numErrors", 1), ("numWarnings", 1)])
def test_package_refuses_validator_errors_and_warnings(
    tmp_path: Path, field: str, count: int
) -> None:
    candidate = make_candidate(tmp_path)
    report = valid_validator_report()
    report["issues"][field] = count

    with pytest.raises(PackageError, match="GLB rejected"):
        run_package(candidate, report)

    assert not candidate["output"].exists()


def test_package_refuses_tampered_blender_output(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    with (candidate["blender"] / "model.glb").open("ab") as handle:
        handle.write(b"tampered")

    with pytest.raises(PackageError, match="Blender output hash"):
        run_package(candidate)

    assert not candidate["output"].exists()


def test_package_refuses_source_hash_disagreement(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    intent = read_json(candidate["intent"])
    intent["source"]["sha256"] = "a" * 64
    write_json_atomic(candidate["intent"], intent)

    with pytest.raises(PackageError, match="intent source hash"):
        run_package(candidate)


def test_package_refuses_asset_identity_disagreement(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    provenance = read_json(candidate["provenance"])
    provenance["asset"]["id"] = "different_crate_01"
    write_json_atomic(candidate["provenance"], provenance)

    with pytest.raises(PackageError, match="provenance asset"):
        run_package(candidate)


def test_package_refuses_profile_budget_violation_before_validator(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    inspection_path = candidate["blender"] / "inspection.json"
    inspection = read_json(inspection_path)
    inspection["geometry"]["triangle_count"] = 100001
    write_json_atomic(inspection_path, inspection)
    rewrite_summary_hash(candidate, "inspection.json")
    called = False

    def validator(_path: Path) -> dict[str, Any]:
        nonlocal called
        called = True
        return valid_validator_report()

    with pytest.raises(PackageError, match="triangle_count"):
        package_asset(
            intent_path=candidate["intent"],
            provenance_path=candidate["provenance"],
            blender_output=candidate["blender"],
            output=candidate["output"],
            generated_at=PACKAGE_TIME,
            image_digest=IMAGE_DIGEST,
            parameter_values=candidate["parameters"],
            validator_runner=validator,
        )

    assert not called
    assert not candidate["output"].exists()


def test_package_refuses_runtime_vertex_budget_violation(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    report = valid_validator_report()
    report["info"]["totalVertexCount"] = 100001

    with pytest.raises(PackageError, match="runtime vertex_count"):
        run_package(candidate, report=report)

    assert not candidate["output"].exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("totalVertexCount", 0),
        ("totalTriangleCount", False),
        ("materialCount", -1),
    ],
)
def test_package_rejects_malformed_runtime_metrics(tmp_path: Path, field: str, value: Any) -> None:
    candidate = make_candidate(tmp_path)
    report = valid_validator_report()
    report["info"][field] = value

    with pytest.raises(PackageError, match=rf"info\.{field}"):
        run_package(candidate, report=report)

    assert not candidate["output"].exists()


def test_package_refuses_profile_check_failure_before_validator(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    inspection_path = candidate["blender"] / "inspection.json"
    inspection = read_json(inspection_path)
    inspection["profile_validation"]["status"] = "fail"
    inspection["profile_validation"]["checks"][0]["status"] = "fail"
    write_json_atomic(inspection_path, inspection)
    rewrite_summary_hash(candidate, "inspection.json")
    summary_path = candidate["blender"] / "blender-build.json"
    summary = read_json(summary_path)
    summary["profile_status"] = "fail"
    write_json_atomic(summary_path, summary)

    with pytest.raises(PackageError, match="profile check"):
        run_package(candidate)

    assert not candidate["output"].exists()


def test_package_refuses_parameter_values_different_from_blender_summary(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    candidate["parameters"] = {"width_meters": 1.2, "wood_style": "plain"}

    with pytest.raises(PackageError, match="parameter values differ"):
        run_package(candidate)


def test_package_refuses_geometry_nodes_input_missing_from_details(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    details_path = candidate["blender"] / "blender-details.json"
    details = read_json(details_path)
    details["geometry_nodes"][0]["inputs"].pop()
    write_json_atomic(details_path, details)
    rewrite_summary_hash(candidate, "blender-details.json")

    with pytest.raises(PackageError, match="inputs differ from asset intent"):
        run_package(candidate)


def test_package_refuses_unlinked_geometry_nodes_input(tmp_path: Path) -> None:
    candidate = make_candidate(tmp_path)
    details_path = candidate["blender"] / "blender-details.json"
    details = read_json(details_path)
    details["geometry_nodes"][0]["inputs"][0]["linked"] = False
    write_json_atomic(details_path, details)
    rewrite_summary_hash(candidate, "blender-details.json")

    with pytest.raises(PackageError, match="not linked into the node graph"):
        run_package(candidate)
