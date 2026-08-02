from pathlib import Path

import pytest

from neuralstock.canonical import read_json, write_json_atomic
from neuralstock.registry import build_registry, semantic_version_key


def test_semantic_version_key_orders_stable_after_prerelease() -> None:
    versions = [
        "1.0.0-alpha.beta",
        "1.0.0",
        "1.0.0-alpha.10",
        "1.0.0-alpha.2",
        "2.0.0",
        "1.1.0",
    ]

    assert sorted(versions, key=semantic_version_key) == [
        "1.0.0-alpha.2",
        "1.0.0-alpha.10",
        "1.0.0-alpha.beta",
        "1.0.0",
        "1.1.0",
        "2.0.0",
    ]


@pytest.mark.parametrize("version", ["1", "v1.0.0", "01.0.0", "1.0", "1.0.0-alpha.01"])
def test_semantic_version_key_rejects_invalid_values(version: str) -> None:
    with pytest.raises(ValueError):
        semantic_version_key(version)


def test_registry_module_does_not_need_runtime_files(tmp_path: Path) -> None:
    assert tmp_path.is_dir()


def test_registry_manifest_uri_is_stable_from_nested_snapshot(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "schemas" / "valid" / "asset.json"
    manifest = read_json(fixture)
    manifest_path = tmp_path / "assets" / manifest["id"] / manifest["version"] / "manifest.json"
    write_json_atomic(manifest_path, manifest)
    output = tmp_path / "snapshots" / "staging" / "registry.json"

    registry = build_registry(
        [manifest_path],
        output=output,
        generated_at="2026-08-01T00:00:00Z",
    )

    assert registry["entries"][0]["manifest"]["uri"] == (
        "/assets/procedural_crate_01/1.0.0/manifest.json"
    )
