"""Canonical public NeuralStock endpoint helpers."""

from __future__ import annotations

import re

SITE_URL = "https://neuralstock.ai/"
ASSET_ORIGIN = "https://assets.neuralstock.ai"
SCHEMA_ORIGIN = "https://schemas.neuralstock.ai"
CANONICAL_REGISTRY_URL = f"{ASSET_ORIGIN}/registry.json"
LATEST_REGISTRY_SNAPSHOT_URL = f"{ASSET_ORIGIN}/snapshots/latest.json"
IMMUTABLE_REGISTRY_SNAPSHOT_TEMPLATE = f"{ASSET_ORIGIN}/snapshots/{{revision}}/registry.json"
DISCOVERY_URL = f"{SITE_URL}.well-known/neuralstock.json"

_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def registry_snapshot_url(revision: str, *, asset_origin: str = ASSET_ORIGIN) -> str:
    """Return the immutable registry snapshot URL for a validated revision."""

    if _SHA256_PATTERN.fullmatch(revision) is None:
        raise ValueError("registry revision must be a lowercase SHA-256 digest")
    return f"{asset_origin.rstrip('/')}/snapshots/{revision}/registry.json"
