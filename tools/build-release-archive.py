#!/usr/bin/env python3
"""Create a deterministic, traversal-safe tar.gz from a verified release tree."""

from __future__ import annotations

import argparse
import gzip
import tarfile
from pathlib import Path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("release_root", type=Path)
    result.add_argument("output", type=Path)
    return result


def release_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for candidate in sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()):
        if candidate.is_symlink():
            raise ValueError(f"release archive input must not use symlinks: {candidate}")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ValueError(f"release archive input must contain only regular files: {candidate}")
        files.append(candidate)
    if not files:
        raise ValueError("release archive input contains no files")
    return files


def build_archive(root: Path, output: Path) -> None:
    resolved_root = root.resolve(strict=True)
    if not resolved_root.is_dir():
        raise ValueError(f"release root is not a directory: {resolved_root}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite release archive: {output}")
    files = release_files(resolved_root)

    with (
        output.open("xb") as raw_output,
        gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=raw_output, mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as archive,
    ):
        for path in files:
            relative = path.relative_to(resolved_root).as_posix()
            info = tarfile.TarInfo(name=f"./{relative}")
            info.size = path.stat().st_size
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            with path.open("rb") as source:
                archive.addfile(info, source)


def main() -> None:
    arguments = parser().parse_args()
    build_archive(arguments.release_root, arguments.output)


if __name__ == "__main__":
    main()
