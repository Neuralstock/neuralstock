from __future__ import annotations

import importlib.util
import struct
import zlib
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[2] / "blender" / "png_normalize.py"
SPEC = importlib.util.spec_from_file_location("neuralstock_png_normalize", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
normalize_png = MODULE.normalize_png


def _chunk(kind: bytes, value: bytes) -> bytes:
    return (
        struct.pack(">I", len(value))
        + kind
        + value
        + struct.pack(">I", zlib.crc32(kind + value) & 0xFFFFFFFF)
    )


def _png(text: bytes) -> bytes:
    return b"".join(
        (
            MODULE.PNG_SIGNATURE,
            _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)),
            _chunk(b"tEXt", b"RenderTime\x00" + text),
            _chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00")),
            _chunk(b"IEND", b""),
        )
    )


def test_normalization_removes_only_volatile_chunks(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(_png(b"00:00.10"))
    second.write_bytes(_png(b"00:42.00"))

    normalize_png(first)
    normalize_png(second)

    assert first.read_bytes() == second.read_bytes()
    assert b"tEXt" not in first.read_bytes()
    assert b"IDAT" in first.read_bytes()


def test_normalization_rejects_truncated_png(tmp_path: Path) -> None:
    path = tmp_path / "broken.png"
    path.write_bytes(MODULE.PNG_SIGNATURE + b"\x00\x00")

    with pytest.raises(ValueError, match="truncated PNG"):
        normalize_png(path)
