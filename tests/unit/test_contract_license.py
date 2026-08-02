from __future__ import annotations

from pathlib import Path

from jsonschema.validators import validator_for

from neuralstock.canonical import read_json, sha256_file
from neuralstock.release import canonical_contract_artifacts
from neuralstock.schema import data_path, require_valid_document, schema_directory

LICENSE_SHA256 = "db925e3df4ed5c6de89e903dd30ecb004f6ba4ae63d9aa98d8570ef50be87200"
SCHEMA_LICENSE_URI = "https://schemas.neuralstock.ai/v0.2/LICENSE"
PROFILE_LICENSE_URI = "https://schemas.neuralstock.ai/profiles/v0.2/LICENSE"


def _expected_notice(license_path: Path, license_uri: str) -> dict[str, str]:
    return {
        "spdx_id": "MIT",
        "copyright": "Copyright (c) 2026 NeuralStock contributors",
        "license_uri": license_uri,
        "license_sha256": LICENSE_SHA256,
        "license_text": license_path.read_text(encoding="utf-8"),
    }


def test_standalone_contracts_embed_the_complete_repository_mit_notice() -> None:
    license_path = data_path("LICENSE")
    assert license_path.is_file()
    assert sha256_file(license_path) == LICENSE_SHA256

    schema_notice = _expected_notice(license_path, SCHEMA_LICENSE_URI)
    for path in sorted(schema_directory().glob("*.schema.json")):
        schema = read_json(path)
        validator_for(schema).check_schema(schema)
        assert schema["x-neuralstock-document-license"] == schema_notice

    profile = read_json(data_path("profiles", "web-v1.json"))
    require_valid_document("profile", profile)
    assert profile["x-neuralstock-document-license"] == _expected_notice(
        license_path, PROFILE_LICENSE_URI
    )


def test_release_contains_immutable_license_companions_with_exact_bytes() -> None:
    license_path = data_path("LICENSE")
    contracts = {artifact.release_key: artifact for artifact in canonical_contract_artifacts()}

    for key in ("v0.2/LICENSE", "profiles/v0.2/LICENSE"):
        artifact = contracts[key]
        assert artifact.source_path == license_path
        assert artifact.content_type == "text/plain"
        assert artifact.source_path.read_bytes() == license_path.read_bytes()
