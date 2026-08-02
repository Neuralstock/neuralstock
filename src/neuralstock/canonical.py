"""Deterministic JSON and SHA-256 helpers used by the public artifact contract."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

BUFFER_SIZE = 1024 * 1024


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON using the NeuralStock v1 canonical representation.

    This deliberately supports ordinary JSON values only. NaN and infinities
    fail rather than producing implementation-specific output.
    """

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(BUFFER_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: str | Path) -> Any:
    def reject_nonfinite(token: str) -> None:
        raise ValueError(f"non-finite JSON number is forbidden: {token}")

    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_nonfinite)


def pretty_json_bytes(value: Any) -> bytes:
    """Serialize generated JSON exactly as it is written to disk."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    )
    return f"{payload}\n".encode()


def write_json_atomic(path: str | Path, value: Any) -> None:
    """Write pretty JSON atomically while hashing its canonical form separately."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = pretty_json_bytes(value)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        text=False,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
