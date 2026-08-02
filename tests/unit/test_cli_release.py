from pathlib import Path
from types import SimpleNamespace

import pytest

from neuralstock import cli


def test_release_publish_command_reports_revision(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured = {}

    def fake_publish_release(packages, **arguments):
        captured["packages"] = packages
        captured.update(arguments)
        return SimpleNamespace(
            asset_count=2,
            object_count=12,
            revision="a" * 64,
            root=Path("release"),
        )

    monkeypatch.setattr(cli, "publish_release", fake_publish_release)

    result = cli.main(
        [
            "release",
            "publish",
            "package-a",
            "package-b",
            "--root",
            "release",
            "--generated-at",
            "2026-08-01T00:00:00Z",
        ]
    )

    assert result == 0
    assert captured["packages"] == [Path("package-a"), Path("package-b")]
    assert captured["generated_at"] == "2026-08-01T00:00:00Z"
    assert '"revision":' in capsys.readouterr().out


def test_r2_sync_reads_neuralstock_scoped_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured = {}
    monkeypatch.setenv("NEURALSTOCK_R2_ACCESS_KEY_ID", "access")
    monkeypatch.setenv("NEURALSTOCK_R2_SECRET_ACCESS_KEY", "secret")

    def fake_client(**arguments):
        captured.update(arguments)
        return object()

    monkeypatch.setattr(cli, "r2_client", fake_client)
    monkeypatch.setattr(
        cli,
        "build_upload_plan",
        lambda *_args, **_kwargs: SimpleNamespace(revision="b" * 64),
    )

    def fake_execute(*_args, **arguments):
        captured["immutable_only"] = arguments["immutable_only"]
        return SimpleNamespace(
            aliases_updated=("registry.json",),
            already_present=(),
            uploaded=("object",),
        )

    monkeypatch.setattr(cli, "execute_upload_plan", fake_execute)

    result = cli.main(
        [
            "r2",
            "sync",
            "--root",
            "release",
            "--bucket",
            "assets",
            "--endpoint-url",
            "https://account.r2.cloudflarestorage.com",
            "--immutable-only",
        ]
    )

    assert result == 0
    assert captured["access_key_id"] == "access"
    assert captured["secret_access_key"] == "secret"
    assert captured["immutable_only"] is True
    output = capsys.readouterr().out
    assert '"immutable_only": true' in output
    assert '"uploaded": 1' in output
