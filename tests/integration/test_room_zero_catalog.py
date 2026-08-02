from __future__ import annotations

from pathlib import Path

from neuralstock.canonical import read_json, sha256_file
from neuralstock.schema import project_root, require_valid_document

EXPECTED_ASSETS = {
    "book_stack_01",
    "cabinet_01",
    "chair_01",
    "desk_lamp_01",
    "monitor_01",
    "mug_01",
    "potted_plant_01",
    "procedural_crate_01",
    "procedural_table_01",
    "room_door_01",
    "room_floor_panel_01",
    "room_wall_panel_01",
    "room_window_01",
    "shelf_01",
    "stool_01",
}

EXPECTED_PROCEDURAL = {
    "procedural_crate_01",
    "procedural_table_01",
    "room_door_01",
    "room_floor_panel_01",
    "room_wall_panel_01",
    "room_window_01",
    "shelf_01",
}

EXPECTED_DEDICATOR = "Joseph Nordqvist"
EXPECTED_PROJECT = "NeuralStock Open Asset Engine"
EXPECTED_PROJECT_URI = "https://neuralstock.ai/"
EXPECTED_VERIFICATION_URI = "https://neuralstock.ai/#mission"
CURRENT_VERSION = "1.0.1"
LOCKED_VERSION = "1.0.0"
EXPECTED_ATTESTATION = Path("catalog/evidence/room-zero-v1.0.1-migration-attestation.md")
EXPECTED_ATTESTATION_SHA256 = "95531e49b5da7616fa769cdbd7d97a84e51beb8798d5180fb3abfbb2a074c32e"
EXPECTED_ATTESTATION_CAPTURED_AT = "2026-08-01T22:52:12Z"
HISTORICAL_ATTESTATION = Path("catalog/evidence/room-zero-v1.0.0-author-attestation.md")
HISTORICAL_ATTESTATION_SHA256 = "e687b259dabc8080a610dd2de11be347e444d8f4a7a9a3df8548d92d9e77d58f"
SOURCE_MIGRATION_LEDGER = Path("catalog/room-zero-v1.0.1-source-migration.json")


def catalog_versions() -> list[Path]:
    return sorted((project_root() / "catalog").glob(f"*/{CURRENT_VERSION}"))


def test_room_zero_catalog_is_complete_cc0_and_self_consistent() -> None:
    versions = catalog_versions()
    assert {path.parent.name for path in versions} == EXPECTED_ASSETS

    procedural: set[str] = set()
    attestation_digests: set[str] = set()
    for version in versions:
        asset_id = version.parent.name
        intent = read_json(version / "asset.intent.json")
        provenance = read_json(version / "provenance.json")
        require_valid_document("asset.intent", intent)
        require_valid_document("provenance", provenance)

        assert intent["id"] == asset_id
        assert intent["version"] == CURRENT_VERSION
        assert provenance["asset"] == {"id": asset_id, "version": CURRENT_VERSION}
        assert intent["license"] == provenance["license"] == "CC0-1.0"
        assert intent["source"]["sha256"] == provenance["source_sha256"]
        assert provenance["dedication"]["dedicator"] == EXPECTED_DEDICATOR
        assert provenance["dedication"]["dedicator_type"] == "person"
        assert provenance["dedication"]["project"] == EXPECTED_PROJECT
        assert provenance["dedication"]["project_uri"] == EXPECTED_PROJECT_URI
        assert provenance["dedication"]["verification_uri"] == EXPECTED_VERIFICATION_URI
        assert {contributor["name"] for contributor in provenance["contributors"]} == {
            EXPECTED_DEDICATOR
        }
        accepted_source = project_root() / "assets" / "room-zero" / asset_id / "source.blend"
        assert accepted_source.is_file()
        assert sha256_file(accepted_source) == intent["source"]["sha256"]
        assert provenance["origin"]["kind"] == "original"
        assert provenance["dependencies"] == []
        assert provenance["attestation"]["accepted"] is True
        assert "needs-review" not in provenance["rights_review"].values()
        assert intent["required_anchors"]

        parameters = intent["blender_source"]["parameters"]
        node_group = intent["blender_source"]["geometry_node_group"]
        if parameters:
            procedural.add(asset_id)
            assert node_group
            assert all(definition["agent_safe"] is True for definition in parameters.values())
        else:
            assert node_group is None

        for evidence in provenance["evidence"]:
            assert "sha256" in evidence
            assert evidence["captured_at"] == EXPECTED_ATTESTATION_CAPTURED_AT
            evidence_path = (version / evidence["uri"]).resolve()
            assert evidence_path == (project_root() / EXPECTED_ATTESTATION).resolve()
            assert evidence_path.is_relative_to(project_root() / "catalog")
            assert evidence_path.is_file()
            assert sha256_file(evidence_path) == evidence["sha256"]
            attestation_digests.add(evidence["sha256"])

    assert procedural == EXPECTED_PROCEDURAL
    assert sha256_file(project_root() / EXPECTED_ATTESTATION) == (EXPECTED_ATTESTATION_SHA256)
    assert attestation_digests == {EXPECTED_ATTESTATION_SHA256}
    attestation_text = (project_root() / EXPECTED_ATTESTATION).read_text()
    assert f"Supplemented: {EXPECTED_ATTESTATION_CAPTURED_AT}" in attestation_text
    assert f"Project: {EXPECTED_PROJECT}" in attestation_text
    assert f"Project URI: {EXPECTED_PROJECT_URI}" in attestation_text
    assert f"Contact / verification: {EXPECTED_VERIFICATION_URI}" in attestation_text
    assert "does not modify, replace, amend, or revoke" in attestation_text
    assert HISTORICAL_ATTESTATION_SHA256 in attestation_text


def test_room_zero_101_migration_preserves_locked_100_inputs_and_evidence() -> None:
    root = project_root()
    ledger = read_json(root / SOURCE_MIGRATION_LEDGER)

    assert ledger["schema_version"] == "1.0"
    assert ledger["collection"] == "room-zero"
    assert ledger["locked_publication"] == {
        "asset_version": LOCKED_VERSION,
        "state": "immutable-historical",
    }
    assert ledger["current_publication"] == {
        "asset_version": CURRENT_VERSION,
        "schema_origin": "https://schemas.neuralstock.ai",
    }
    accepted_source = ledger["accepted_source"]
    assert accepted_source["embedded_asset_version"] == LOCKED_VERSION
    assert accepted_source["reuse"] == "byte-for-byte"
    assert set(accepted_source["sha256_by_asset"]) == EXPECTED_ASSETS

    # The catalog intentionally has no editable copy of the locked live version.
    assert not list((root / "catalog").glob(f"*/{LOCKED_VERSION}"))
    for asset_id, expected_sha256 in accepted_source["sha256_by_asset"].items():
        source = root / "assets" / "room-zero" / asset_id / "source.blend"
        assert sha256_file(source) == expected_sha256
        source_bytes = source.read_bytes()
        assert b"neuralstock_asset_version" in source_bytes
        assert LOCKED_VERSION.encode() in source_bytes

        intent = read_json(root / "catalog" / asset_id / CURRENT_VERSION / "asset.intent.json")
        assert intent["version"] == CURRENT_VERSION
        assert intent["source"]["sha256"] == expected_sha256

    assert sha256_file(root / HISTORICAL_ATTESTATION) == (HISTORICAL_ATTESTATION_SHA256)
    assert sha256_file(root / EXPECTED_ATTESTATION) == EXPECTED_ATTESTATION_SHA256
    assert HISTORICAL_ATTESTATION_SHA256 != EXPECTED_ATTESTATION_SHA256

    release_script = (root / "tools" / "release-room-zero.sh").read_text()
    assert f"--asset-version {CURRENT_VERSION}" in release_script
    assert f"catalog/*/{CURRENT_VERSION}/asset.intent.json" in release_script
    assert f"catalog/*/{LOCKED_VERSION}/asset.intent.json" not in release_script


def test_catalog_contains_only_authored_documents_and_evidence() -> None:
    catalog = project_root() / "catalog"
    prohibited_suffixes = {".blend", ".glb", ".png", ".jpg", ".jpeg", ".webp"}
    assert not [path for path in catalog.rglob("*") if path.suffix.lower() in prohibited_suffixes]
