from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "tools" / "verify-release-tag.sh"


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def run_verifier(repository: Path, version: str, commit: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("GITHUB_REPOSITORY", None)
    environment.pop("GH_TOKEN", None)
    return subprocess.run(
        [str(SCRIPT), version, commit],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def release_repository(tmp_path: Path) -> tuple[Path, str]:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(work)],
        check=True,
        capture_output=True,
    )
    git(work, "config", "user.name", "NeuralStock test")
    git(work, "config", "user.email", "test@neuralstock.invalid")
    (work / "release.txt").write_text("release\n")
    git(work, "add", "release.txt")
    git(work, "commit", "-m", "release")
    commit = git(work, "rev-parse", "HEAD")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "origin", "main")
    git(work, "tag", "v0.1.0")
    git(work, "push", "origin", "v0.1.0")
    return work, commit


def test_accepts_exact_release_tag_on_main(tmp_path: Path) -> None:
    repository, commit = release_repository(tmp_path)

    result = run_verifier(repository, "0.1.0", commit)

    assert result.returncode == 0, result.stderr
    assert f"Verified v0.1.0 at {commit}" in result.stdout


def test_accepts_annotated_release_tag_on_main(tmp_path: Path) -> None:
    repository, commit = release_repository(tmp_path)
    git(repository, "tag", "--annotate", "--message", "release", "v0.1.1", commit)
    git(repository, "push", "origin", "v0.1.1")

    result = run_verifier(repository, "0.1.1", commit)

    assert result.returncode == 0, result.stderr
    assert f"Verified v0.1.1 at {commit}" in result.stdout


def test_rejects_tag_that_is_not_on_main(tmp_path: Path) -> None:
    repository, _ = release_repository(tmp_path)
    git(repository, "switch", "--orphan", "unmerged")
    (repository / "release.txt").write_text("unmerged\n")
    git(repository, "add", "release.txt")
    git(repository, "commit", "-m", "unmerged")
    commit = git(repository, "rev-parse", "HEAD")
    git(repository, "tag", "v0.2.0")
    git(repository, "push", "origin", "v0.2.0")

    result = run_verifier(repository, "0.2.0", commit)

    assert result.returncode != 0
    assert "is not an ancestor of origin/main" in result.stderr


def test_rejects_commit_other_than_tag_target(tmp_path: Path) -> None:
    repository, tagged_commit = release_repository(tmp_path)
    (repository / "release.txt").write_text("later\n")
    git(repository, "commit", "-am", "later")
    later_commit = git(repository, "rev-parse", "HEAD")
    git(repository, "push", "origin", "main")

    result = run_verifier(repository, "0.1.0", later_commit)

    assert result.returncode != 0
    assert f"v0.1.0 resolves to {tagged_commit}, expected {later_commit}" in result.stderr
