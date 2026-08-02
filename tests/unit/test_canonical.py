from pathlib import Path

import pytest

from neuralstock.canonical import canonical_json_bytes, read_json, sha256_bytes, sha256_json


def test_canonical_json_is_stable_across_key_order() -> None:
    first = {"z": [3, 2, 1], "a": {"enabled": True}}
    second = {"a": {"enabled": True}, "z": [3, 2, 1]}

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert sha256_json(first) == sha256_json(second)


def test_known_sha256() -> None:
    expected = "0d5fcc7f9947b4c7970e84c5bef4eb35dd98b1af09cfe4a52def614e73072e21"
    assert sha256_bytes(b"neuralstock") == expected


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_read_json_rejects_nonfinite_extensions(tmp_path: Path, token: str) -> None:
    path = tmp_path / "not-json.json"
    path.write_text(f'{{"value": {token}}}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="non-finite JSON number"):
        read_json(path)
