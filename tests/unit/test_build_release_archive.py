from __future__ import annotations

import gzip
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "tools" / "build-release-archive.py"


def run_archive(source: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(source), str(output)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_release_archive_is_deterministic_and_normalized(tmp_path: Path) -> None:
    source = tmp_path / "release"
    (source / "z").mkdir(parents=True)
    (source / "a").mkdir()
    (source / "z" / "asset.bin").write_bytes(b"asset")
    (source / "a" / "manifest.json").write_text('{"ok":true}\n')
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"

    assert run_archive(source, first).returncode == 0
    assert run_archive(source, second).returncode == 0
    assert first.read_bytes() == second.read_bytes()

    with first.open("rb") as compressed:
        assert compressed.read(10)[4:8] == b"\x00\x00\x00\x00"
    with gzip.open(first, "rb") as tar_bytes, tarfile.open(fileobj=tar_bytes) as archive:
        members = archive.getmembers()
        assert [member.name for member in members] == [
            "./a/manifest.json",
            "./z/asset.bin",
        ]
        assert all(member.mtime == member.uid == member.gid == 0 for member in members)
        assert all(member.mode == 0o644 for member in members)


def test_release_archive_refuses_symlinks_and_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "release"
    source.mkdir()
    target = source / "target"
    target.write_text("target")
    link = source / "link"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("filesystem does not permit symlink creation")

    output = tmp_path / "candidate.tar.gz"
    first = run_archive(source, output)
    assert first.returncode != 0
    assert "must not use symlinks" in first.stderr

    link.unlink()
    output.write_bytes(b"existing")
    second = run_archive(source, output)
    assert second.returncode != 0
    assert "refusing to overwrite" in second.stderr
    assert output.read_bytes() == b"existing"
