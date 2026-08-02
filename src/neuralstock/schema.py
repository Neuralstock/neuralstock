"""Load and validate NeuralStock JSON documents."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker
from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for
from referencing import Registry, Resource

from neuralstock.canonical import read_json


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_path(*parts: str) -> Path:
    """Locate contract data in a wheel or, during development, the repository."""

    packaged = Path(__file__).resolve().parent.joinpath("data", *parts)
    if packaged.exists():
        return packaged
    return project_root().joinpath(*parts)


def schema_directory() -> Path:
    return data_path("schemas")


def normalize_schema_name(name: str) -> str:
    normalized = name.removesuffix(".schema.json").removesuffix(".json")
    aliases = {
        "asset-intent": "asset.intent",
        "build_receipt": "build-receipt",
        "build.receipt": "build-receipt",
    }
    return aliases.get(normalized, normalized)


def schema_path(name: str) -> Path:
    return schema_directory() / f"{normalize_schema_name(name)}.schema.json"


def load_schema(name: str) -> dict[str, Any]:
    path = schema_path(name)
    if not path.is_file():
        available = ", ".join(
            sorted(item.name for item in schema_directory().glob("*.schema.json"))
        )
        raise FileNotFoundError(f"unknown schema {name!r}; available: {available}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise TypeError(f"schema must be an object: {path}")
    return value


def schema_registry() -> Registry:
    resources: list[tuple[str, Resource[Any]]] = []
    for path in sorted(schema_directory().glob("*.schema.json")):
        contents = read_json(path)
        if not isinstance(contents, dict):
            raise TypeError(f"schema must be an object: {path}")
        identifier = contents.get("$id", path.resolve().as_uri())
        resources.append((identifier, Resource.from_contents(contents)))
    return Registry().with_resources(resources)


@dataclass(frozen=True)
class DocumentIssue:
    path: str
    message: str
    validator: str | None

    def render(self) -> str:
        location = self.path or "$"
        return f"{location}: {self.message}"


class DocumentValidationError(ValueError):
    def __init__(self, schema_name: str, issues: list[DocumentIssue]) -> None:
        self.schema_name = schema_name
        self.issues = issues
        details = "\n".join(f"- {issue.render()}" for issue in issues)
        super().__init__(f"document does not satisfy {schema_name}:\n{details}")


def _issue(error: ValidationError) -> DocumentIssue:
    path = "$" + "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path
    )
    return DocumentIssue(path=path, message=error.message, validator=error.validator)


def _semantic_parameter_issues(document: dict[str, Any]) -> list[DocumentIssue]:
    blender_source = document.get("blender_source")
    if not isinstance(blender_source, dict):
        return []
    parameters = blender_source.get("parameters")
    if not isinstance(parameters, dict):
        return []

    issues: list[DocumentIssue] = []
    for name, definition in parameters.items():
        if not isinstance(definition, dict):
            continue
        base = f"$.blender_source.parameters.{name}"
        parameter_type = definition.get("type")
        if parameter_type in {"float", "integer"}:
            minimum = definition.get("minimum")
            maximum = definition.get("maximum")
            default = definition.get("default")
            numeric_values = {
                "minimum": minimum,
                "maximum": maximum,
                "default": default,
            }
            for field, value in numeric_values.items():
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and not isfinite(float(value))
                ):
                    issues.append(
                        DocumentIssue(
                            path=f"{base}.{field}",
                            message="must be finite",
                            validator="semantic",
                        )
                    )
            if (
                all(
                    isinstance(value, (int, float)) and not isinstance(value, bool)
                    for value in (minimum, maximum)
                )
                and minimum > maximum
            ):
                issues.append(
                    DocumentIssue(
                        path=base,
                        message="minimum must be less than or equal to maximum",
                        validator="semantic",
                    )
                )
            if (
                all(
                    isinstance(value, (int, float)) and not isinstance(value, bool)
                    for value in (minimum, default, maximum)
                )
                and not minimum <= default <= maximum
            ):
                issues.append(
                    DocumentIssue(
                        path=f"{base}.default",
                        message="default must be within the inclusive minimum and maximum",
                        validator="semantic",
                    )
                )
        elif parameter_type == "enum":
            options = definition.get("options")
            default = definition.get("default")
            if isinstance(options, list) and isinstance(default, str) and default not in options:
                issues.append(
                    DocumentIssue(
                        path=f"{base}.default",
                        message="default must be one of the declared enum options",
                        validator="semantic",
                    )
                )
    return issues


def semantic_issues(schema_name: str, document: Any) -> list[DocumentIssue]:
    issues: list[DocumentIssue] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, float) and not isfinite(value):
            issues.append(
                DocumentIssue(path=path, message="number must be finite", validator="semantic")
            )
        elif isinstance(value, dict):
            for key, item in value.items():
                visit(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")

    visit(document, "$")
    if not isinstance(document, dict):
        return issues
    normalized = normalize_schema_name(schema_name)
    if normalized == "asset.intent":
        issues.extend(_semantic_parameter_issues(document))
    return issues


def validate_document(schema_name: str, document: Any) -> list[DocumentIssue]:
    schema = load_schema(schema_name)
    validator_type = validator_for(schema)
    validator_type.check_schema(schema)
    validator = validator_type(
        schema,
        registry=schema_registry(),
        format_checker=FormatChecker(),
    )
    structural = [_issue(error) for error in sorted(validator.iter_errors(document), key=str)]
    return [*structural, *semantic_issues(schema_name, document)]


def require_valid_document(schema_name: str, document: Any) -> None:
    issues = validate_document(schema_name, document)
    if issues:
        raise DocumentValidationError(schema_name, issues)
