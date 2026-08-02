from pathlib import Path
from types import SimpleNamespace

import pytest

from neuralstock import cli


def package_arguments() -> list[str]:
    return [
        "package",
        "--intent",
        "asset.intent.json",
        "--provenance",
        "provenance.json",
        "--blender-output",
        "blender-output",
        "--output",
        "package-output",
        "--generated-at",
        "2026-08-01T12:10:00Z",
        "--image-digest",
        "sha256:" + "d" * 64,
        "--parameters-json",
        '{"width_meters":1.0}',
    ]


def test_package_command_passes_explicit_reproducibility_inputs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured = {}

    def fake_package_asset(**arguments):
        captured.update(arguments)
        return SimpleNamespace(
            asset={"id": "procedural_crate_01", "version": "1.0.0"},
            build_key="a" * 64,
            output=Path("package-output"),
        )

    monkeypatch.setattr(cli, "package_asset", fake_package_asset)

    assert cli.main(package_arguments()) == 0
    assert captured["generated_at"] == "2026-08-01T12:10:00Z"
    assert captured["image_digest"] == "sha256:" + "d" * 64
    assert captured["parameter_values"] == {"width_meters": 1.0}
    assert captured["comparison_blender_output"] is None
    assert '"build_key":' in capsys.readouterr().out


def test_package_command_passes_comparison_blender_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_package_asset(**arguments):
        captured.update(arguments)
        return SimpleNamespace(
            asset={"id": "procedural_crate_01", "version": "1.0.0"},
            build_key="a" * 64,
            output=Path("package-output"),
        )

    monkeypatch.setattr(cli, "package_asset", fake_package_asset)
    arguments = package_arguments()
    arguments.extend(["--comparison-blender-output", "comparison-output"])

    assert cli.main(arguments) == 0
    assert captured["comparison_blender_output"] == Path("comparison-output")


@pytest.mark.parametrize(
    "required_option", ["--generated-at", "--image-digest", "--parameters-json"]
)
def test_package_command_requires_explicit_reproducibility_inputs(
    required_option: str,
) -> None:
    arguments = package_arguments()
    index = arguments.index(required_option)
    del arguments[index : index + 2]

    with pytest.raises(SystemExit):
        cli.parser().parse_args(arguments)
