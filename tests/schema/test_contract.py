from pathlib import Path
from urllib.parse import urlparse

import pytest
from jsonschema.validators import validator_for

from neuralstock.canonical import read_json
from neuralstock.schema import load_schema, schema_directory, validate_document

FIXTURES = Path(__file__).parents[1] / "fixtures" / "schemas"


def schema_name(document: dict[str, object]) -> str:
    identifier = document.get("$schema")
    if not isinstance(identifier, str):
        raise AssertionError("fixture must declare its target in $schema")
    filename = Path(urlparse(identifier).path).name
    if not filename.endswith(".schema.json"):
        raise AssertionError(f"fixture $schema must end in .schema.json: {identifier}")
    return filename.removesuffix(".schema.json")


def fixture_paths(kind: str) -> list[Path]:
    return sorted((FIXTURES / kind).glob("*.json"))


@pytest.mark.parametrize("path", sorted(schema_directory().glob("*.schema.json")))
def test_schema_is_valid_draft_2020_12(path: Path) -> None:
    schema = read_json(path)
    validator_type = validator_for(schema)
    validator_type.check_schema(schema)


@pytest.mark.parametrize("path", fixture_paths("valid"))
def test_valid_contract_fixture(path: Path) -> None:
    document = read_json(path)
    assert isinstance(document, dict)
    name = schema_name(document)

    assert load_schema(name)
    assert validate_document(name, document) == []


@pytest.mark.parametrize("path", fixture_paths("invalid"))
def test_invalid_contract_fixture(path: Path) -> None:
    document = read_json(path)
    assert isinstance(document, dict)

    assert validate_document(schema_name(document), document)
