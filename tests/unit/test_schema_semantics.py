from copy import deepcopy

from neuralstock.canonical import read_json
from neuralstock.schema import validate_document


def valid_intent() -> dict:
    return read_json("tests/fixtures/schemas/valid/asset.intent.json")


def valid_receipt() -> dict:
    return read_json("tests/fixtures/schemas/valid/build-receipt.json")


def test_numeric_parameter_default_must_be_in_range() -> None:
    document = deepcopy(valid_intent())
    parameter = next(
        value
        for value in document["blender_source"]["parameters"].values()
        if value["type"] in {"float", "integer"}
    )
    parameter["default"] = parameter["maximum"] + 1

    issues = validate_document("asset.intent", document)

    assert any(issue.validator == "semantic" and "inclusive" in issue.message for issue in issues)


def test_numeric_parameter_minimum_must_not_exceed_maximum() -> None:
    document = deepcopy(valid_intent())
    parameter = next(
        value
        for value in document["blender_source"]["parameters"].values()
        if value["type"] in {"float", "integer"}
    )
    parameter["minimum"] = parameter["maximum"] + 1

    issues = validate_document("asset.intent", document)

    assert any(issue.validator == "semantic" and "minimum" in issue.message for issue in issues)


def test_enum_parameter_default_must_be_an_option() -> None:
    document = deepcopy(valid_intent())
    document["blender_source"]["parameters"]["style"] = {
        "type": "enum",
        "default": "missing",
        "options": ["square", "rounded"],
        "agent_safe": True,
    }

    issues = validate_document("asset.intent", document)

    assert any(issue.validator == "semantic" and "enum" in issue.message for issue in issues)


def test_nonfinite_number_is_rejected_even_for_in_memory_documents() -> None:
    document = read_json("tests/fixtures/schemas/valid/inspection.json")
    document["bounds_m"]["minimum"][0] = float("nan")

    issues = validate_document("inspection", document)

    assert any(
        issue.path == "$.bounds_m.minimum[0]" and issue.message == "number must be finite"
        for issue in issues
    )


def test_reproduced_receipt_requires_comparison_build_id() -> None:
    document = deepcopy(valid_receipt())
    document["reproducibility"]["status"] = "reproduced"

    issues = validate_document("build-receipt", document)

    assert any("comparison_build_id" in issue.message for issue in issues)


def test_not_yet_reproduced_receipt_forbids_comparison_build_id() -> None:
    document = deepcopy(valid_receipt())
    document["reproducibility"]["comparison_build_id"] = "comparison_fixture_001"

    issues = validate_document("build-receipt", document)

    assert issues
