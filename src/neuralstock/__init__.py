"""NeuralStock validation, packaging, registry, and publication tooling."""

from neuralstock.discovery import (
    ASSET_ORIGIN,
    CANONICAL_REGISTRY_URL,
    DISCOVERY_URL,
    IMMUTABLE_REGISTRY_SNAPSHOT_TEMPLATE,
    LATEST_REGISTRY_SNAPSHOT_URL,
    SCHEMA_ORIGIN,
    SITE_URL,
    registry_snapshot_url,
)

__version__ = "0.1.0"

__all__ = [
    "ASSET_ORIGIN",
    "CANONICAL_REGISTRY_URL",
    "DISCOVERY_URL",
    "IMMUTABLE_REGISTRY_SNAPSHOT_TEMPLATE",
    "LATEST_REGISTRY_SNAPSHOT_URL",
    "SCHEMA_ORIGIN",
    "SITE_URL",
    "__version__",
    "registry_snapshot_url",
]
