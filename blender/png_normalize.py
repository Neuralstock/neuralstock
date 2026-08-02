"""Normalize Blender PNG output by removing volatile ancillary metadata."""

from __future__ import annotations

from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
VOLATILE_CHUNKS = {b"tEXt", b"zTXt", b"iTXt", b"tIME"}


def normalize_png(path: str | Path) -> None:
    """Remove non-pixel metadata whose values vary between identical renders.

    Blender records the source path, wall-clock render time, and render duration
    in PNG text chunks. Keeping all image and color-management chunks byte-for-
    byte while dropping those text/time chunks makes identical pixel output
    content-addressable without re-encoding it.
    """

    destination = Path(path)
    payload = destination.read_bytes()
    if not payload.startswith(PNG_SIGNATURE):
        raise ValueError(f"not a PNG file: {destination}")

    normalized = bytearray(PNG_SIGNATURE)
    offset = len(PNG_SIGNATURE)
    saw_iend = False

    while offset < len(payload):
        if offset + 12 > len(payload):
            raise ValueError(f"truncated PNG chunk header: {destination}")
        length = int.from_bytes(payload[offset : offset + 4], "big")
        chunk_end = offset + 12 + length
        if chunk_end > len(payload):
            raise ValueError(f"truncated PNG chunk payload: {destination}")

        chunk_type = payload[offset + 4 : offset + 8]
        if chunk_type not in VOLATILE_CHUNKS:
            normalized.extend(payload[offset:chunk_end])
        if chunk_type == b"IEND":
            saw_iend = True
            if chunk_end != len(payload):
                raise ValueError(f"PNG contains bytes after IEND: {destination}")
        offset = chunk_end

    if not saw_iend:
        raise ValueError(f"PNG does not contain IEND: {destination}")
    destination.write_bytes(normalized)
