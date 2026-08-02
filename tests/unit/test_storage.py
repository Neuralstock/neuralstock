from pathlib import Path

import pytest

from neuralstock.storage import object_key, publish_named_immutable, publish_object


def test_object_key_partitions_digest() -> None:
    digest = "a1" + "0" * 62
    assert object_key(digest) == f"objects/sha256/a1/{digest}"


def test_publish_object_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "source.glb"
    source.write_bytes(b"asset bytes")
    store = tmp_path / "store"

    first = publish_object(source, store)
    second = publish_object(source, store)

    assert first.path.read_bytes() == b"asset bytes"
    assert first.digest == second.digest
    assert not first.already_present
    assert second.already_present


def test_named_immutable_refuses_different_bytes(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    publish_named_immutable(first, tmp_path / "store", "assets/a/1/manifest.json")

    with pytest.raises(FileExistsError):
        publish_named_immutable(second, tmp_path / "store", "assets/a/1/manifest.json")


@pytest.mark.parametrize("key", ["../escape", "/absolute", "nested/../../escape"])
def test_named_immutable_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    source = tmp_path / "source"
    source.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError):
        publish_named_immutable(source, tmp_path / "store", key)
