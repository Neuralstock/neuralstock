from pathlib import Path

import pytest

from neuralstock import (
    ASSET_ORIGIN,
    CANONICAL_REGISTRY_URL,
    DISCOVERY_URL,
    IMMUTABLE_REGISTRY_SNAPSHOT_TEMPLATE,
    LATEST_REGISTRY_SNAPSHOT_URL,
    SCHEMA_ORIGIN,
    SITE_URL,
    registry_snapshot_url,
)
from neuralstock.canonical import read_json
from neuralstock.schema import validate_document

PROJECT_ROOT = Path(__file__).parents[2]


def test_canonical_endpoint_helpers() -> None:
    revision = "a" * 64

    assert SITE_URL == "https://neuralstock.ai/"
    assert ASSET_ORIGIN == "https://assets.neuralstock.ai"
    assert SCHEMA_ORIGIN == "https://schemas.neuralstock.ai"
    assert CANONICAL_REGISTRY_URL == "https://assets.neuralstock.ai/registry.json"
    assert LATEST_REGISTRY_SNAPSHOT_URL == ("https://assets.neuralstock.ai/snapshots/latest.json")
    assert DISCOVERY_URL == "https://neuralstock.ai/.well-known/neuralstock.json"
    assert IMMUTABLE_REGISTRY_SNAPSHOT_TEMPLATE == (
        "https://assets.neuralstock.ai/snapshots/{revision}/registry.json"
    )
    assert registry_snapshot_url(revision) == (
        f"https://assets.neuralstock.ai/snapshots/{revision}/registry.json"
    )


def test_machine_discovery_source_matches_package_constants() -> None:
    document = read_json(PROJECT_ROOT / "discovery" / "neuralstock.json")

    assert validate_document("discovery", document) == []
    assert document["site"] == SITE_URL
    assert document["asset_origin"] == ASSET_ORIGIN
    assert document["schema_origin"] == SCHEMA_ORIGIN
    assert document["registry"] == {
        "canonical": CANONICAL_REGISTRY_URL,
        "latest_snapshot": LATEST_REGISTRY_SNAPSHOT_URL,
        "immutable_snapshot_template": IMMUTABLE_REGISTRY_SNAPSHOT_TEMPLATE,
    }


@pytest.mark.parametrize("revision", ["", "A" * 64, "a" * 63, "../registry.json"])
def test_snapshot_url_rejects_invalid_revisions(revision: str) -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        registry_snapshot_url(revision)
