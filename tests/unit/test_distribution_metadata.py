import re
from importlib.metadata import metadata
from pathlib import Path

import neuralstock
from neuralstock import __version__

PROJECT_ROOT = Path(__file__).parents[2]


def test_runtime_version_matches_project_release() -> None:
    assert __version__ == "0.1.0"


def test_installed_package_carries_typing_marker() -> None:
    assert (Path(neuralstock.__file__).parent / "py.typed").is_file()


def test_distribution_points_to_canonical_rollout_repository() -> None:
    project_urls = metadata("neuralstock").get_all("Project-URL") or []

    assert "Source, https://github.com/Neuralstock/neuralstock" in project_urls
    assert "Issues, https://github.com/Neuralstock/neuralstock/issues" in project_urls
    assert (
        "Release-Record, "
        "https://github.com/Neuralstock/neuralstock/blob/v0.1.0/docs/releases/v0.1.0.md"
    ) in project_urls


def test_pypi_readme_has_install_cli_api_and_portable_links() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text()
    targets = re.findall(r"\[[^]]+\]\(([^)]+)\)", readme)

    assert "python -m pip install neuralstock" in readme
    assert "neuralstock validate --schema asset.intent" in readme
    assert "from neuralstock import (" in readme
    assert "CANONICAL_REGISTRY_URL" in readme
    assert targets
    assert all(target.startswith(("https://", "#")) for target in targets)


def test_v010_release_record_separates_version_domains() -> None:
    record = (PROJECT_ROOT / "docs" / "releases" / "v0.1.0.md").read_text()

    assert "`neuralstock==0.1.0`" in record
    assert "`@neuralstock/client@0.1.0`" in record
    assert "| JSON Schema contract | `v0.2`" in record
    assert "| Room Zero assets | `1.0.1`" in record
    assert re.search(r"\| Canonical registry revision \| `(?:PENDING|[0-9a-f]{64})`", record)
    assert "5389b46066d3cd60886deb5ce44c4b274e3925e9af80dfa0f1c17a3304bc02a8" not in record
