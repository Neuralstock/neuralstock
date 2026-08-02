"""Shared utilities for NeuralStock's repository-owned Blender scripts.

This module intentionally depends only on Blender's bundled Python runtime.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector

TOOL_NAME = "neuralstock-blender"
TOOL_VERSION = "0.1.0"
ASSET_COLLECTION = "ASSET"
COLLISION_COLLECTION = "COLLISION"
ANCHOR_PREFIX = "ANCHOR_"
PREVIEW_COLLECTION = "NEURALSTOCK_PREVIEW"
PARAMETER_SCHEMA_PROPERTY = "neuralstock_parameters_json"
PARAMETER_VALUES_PROPERTY = "neuralstock_parameter_values_json"


class NeuralStockError(RuntimeError):
    """Raised when an asset violates the repository-owned Blender contract."""


class BlenderArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports errors as Python failures to Blender."""

    def error(self, message: str) -> None:
        raise NeuralStockError(f"invalid arguments: {message}")


def script_arguments(argv: Sequence[str] | None = None) -> list[str]:
    """Return arguments following Blender's ``--`` script separator."""

    values = list(sys.argv if argv is None else argv)
    if "--" not in values:
        return []
    return values[values.index("--") + 1 :]


def read_json_value(value: str | None, *, label: str) -> dict[str, Any]:
    """Read a JSON object from an inline value, ``@path``, or existing path."""

    if value is None or value == "":
        return {}

    candidate = value[1:] if value.startswith("@") else value
    path = Path(candidate)
    try:
        if value.startswith("@") or path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = json.loads(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise NeuralStockError(f"could not read {label} JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise NeuralStockError(f"{label} must be a JSON object")
    return payload


def stable_json_value(value: Any) -> Any:
    """Convert Blender/mathutils values into stable JSON-compatible values."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise NeuralStockError("non-finite numeric value cannot be serialized")
        normalized = round(value, 9)
        return 0.0 if normalized == 0 else normalized
    if isinstance(value, Mapping):
        return {
            str(key): stable_json_value(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple, set, Vector)):
        return [stable_json_value(item) for item in value]
    if hasattr(value, "to_list"):
        return stable_json_value(value.to_list())
    return str(value)


def write_json(path: str | os.PathLike[str], payload: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized = stable_json_value(payload)
    destination.write_text(
        json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generated_at(value: str | None = None) -> str:
    """Return a UTC timestamp, honoring SOURCE_DATE_EPOCH when configured."""

    if value:
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise NeuralStockError("--generated-at must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None:
            raise NeuralStockError("--generated-at must include a timezone")
        return parsed.astimezone(dt.UTC).isoformat().replace("+00:00", "Z")

    source_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_epoch is not None:
        try:
            instant = dt.datetime.fromtimestamp(int(source_epoch), tz=dt.UTC)
        except (ValueError, OverflowError, OSError) as exc:
            raise NeuralStockError("SOURCE_DATE_EPOCH must be a valid Unix timestamp") from exc
    else:
        instant = dt.datetime.now(tz=dt.UTC)
    return instant.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_blender_45() -> None:
    if bpy.app.version < (4, 5, 0) or bpy.app.version >= (4, 6, 0):
        raise NeuralStockError(
            f"this release is pinned to Blender 4.5 LTS; running {bpy.app.version_string}"
        )


def set_deterministic_scene_defaults(scene: bpy.types.Scene) -> None:
    """Set project-wide units, color, and frame defaults."""

    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0
    scene.frame_start = 1
    scene.frame_end = 1
    scene.frame_set(1)
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.use_file_extension = True


def reset_scene() -> None:
    """Remove startup data before generating a repository-owned source."""

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.node_groups,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)

    set_deterministic_scene_defaults(bpy.context.scene)


def get_or_create_collection(
    name: str,
    *,
    parent: bpy.types.Collection | None = None,
) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
    parent_collection = parent or bpy.context.scene.collection
    if collection.name not in {child.name for child in parent_collection.children}:
        parent_collection.children.link(collection)
    return collection


def collection_objects_recursive(collection: bpy.types.Collection) -> list[bpy.types.Object]:
    objects: dict[str, bpy.types.Object] = {}

    def visit(current: bpy.types.Collection) -> None:
        for obj in current.objects:
            objects[obj.name_full] = obj
        for child in current.children:
            visit(child)

    visit(collection)
    return [objects[name] for name in sorted(objects)]


def object_is_collision(obj: bpy.types.Object) -> bool:
    if bool(obj.get("neuralstock_collision", False)):
        return True
    if obj.name.startswith("COLLISION_"):
        return True
    return any(collection.name == COLLISION_COLLECTION for collection in obj.users_collection)


def asset_objects(*, include_collision: bool = False) -> list[bpy.types.Object]:
    collection = bpy.data.collections.get(ASSET_COLLECTION)
    if collection is None:
        raise NeuralStockError(f"required collection {ASSET_COLLECTION!r} does not exist")
    objects = collection_objects_recursive(collection)
    if include_collision:
        collision_collection = bpy.data.collections.get(COLLISION_COLLECTION)
        if collision_collection is not None:
            merged = {obj.name_full: obj for obj in objects}
            merged.update(
                {obj.name_full: obj for obj in collection_objects_recursive(collision_collection)}
            )
            objects = [merged[name] for name in sorted(merged)]
    return [obj for obj in objects if obj.name != PREVIEW_COLLECTION]


def visual_mesh_objects() -> list[bpy.types.Object]:
    return [
        obj
        for obj in asset_objects(include_collision=False)
        if obj.type == "MESH" and not object_is_collision(obj)
    ]


def collision_objects() -> list[bpy.types.Object]:
    objects: dict[str, bpy.types.Object] = {}
    collection = bpy.data.collections.get(COLLISION_COLLECTION)
    if collection is not None:
        objects.update({obj.name_full: obj for obj in collection_objects_recursive(collection)})
    for obj in bpy.data.objects:
        if object_is_collision(obj):
            objects[obj.name_full] = obj
    return [objects[name] for name in sorted(objects)]


def anchor_objects() -> list[bpy.types.Object]:
    return sorted(
        (
            obj
            for obj in bpy.data.objects
            if obj.type == "EMPTY" and obj.name.startswith(ANCHOR_PREFIX)
        ),
        key=lambda item: item.name,
    )


def evaluated_mesh_data(
    obj: bpy.types.Object,
    depsgraph: bpy.types.Depsgraph,
) -> tuple[list[Vector], dict[str, int]]:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    if mesh is None:
        return [], {"vertices": 0, "edges": 0, "polygons": 0, "triangles": 0}
    try:
        mesh.calc_loop_triangles()
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        counts = {
            "vertices": len(mesh.vertices),
            "edges": len(mesh.edges),
            "polygons": len(mesh.polygons),
            "triangles": len(mesh.loop_triangles),
        }
        return points, counts
    finally:
        evaluated.to_mesh_clear()


def bounds_for_objects(
    objects: Iterable[bpy.types.Object],
    depsgraph: bpy.types.Depsgraph | None = None,
) -> dict[str, list[float]]:
    graph = depsgraph or bpy.context.evaluated_depsgraph_get()
    points: list[Vector] = []
    for obj in objects:
        if obj.type == "MESH":
            object_points, _ = evaluated_mesh_data(obj, graph)
            points.extend(object_points)
    if not points:
        raise NeuralStockError("asset contains no evaluated mesh vertices")
    minimum = Vector(tuple(min(point[index] for point in points) for index in range(3)))
    maximum = Vector(tuple(max(point[index] for point in points) for index in range(3)))
    return {
        "minimum": stable_json_value(minimum),
        "maximum": stable_json_value(maximum),
        "dimensions": stable_json_value(maximum - minimum),
    }


def custom_properties(owner: Any) -> dict[str, Any]:
    ignored = {"_RNA_UI"}
    return {
        key: stable_json_value(owner[key])
        for key in sorted(owner.keys())
        if key not in ignored and not key.startswith("neuralstock_internal_")
    }


def load_parameter_schema(scene: bpy.types.Scene | None = None) -> dict[str, Any]:
    target = scene or bpy.context.scene
    raw = target.get(PARAMETER_SCHEMA_PROPERTY, "{}")
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise NeuralStockError("embedded NeuralStock parameter declarations are invalid") from exc
    if not isinstance(parsed, dict):
        raise NeuralStockError("embedded NeuralStock parameter declarations must be an object")
    return parsed


def store_parameter_schema(parameters: Mapping[str, Any]) -> None:
    bpy.context.scene[PARAMETER_SCHEMA_PROPERTY] = json.dumps(
        stable_json_value(parameters), sort_keys=True, separators=(",", ":")
    )


def store_parameter_values(values: Mapping[str, Any]) -> None:
    bpy.context.scene[PARAMETER_VALUES_PROPERTY] = json.dumps(
        stable_json_value(values), sort_keys=True, separators=(",", ":")
    )


def load_parameter_values(scene: bpy.types.Scene | None = None) -> dict[str, Any]:
    target = scene or bpy.context.scene
    raw = target.get(PARAMETER_VALUES_PROPERTY, "{}")
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise NeuralStockError("embedded NeuralStock parameter values are invalid") from exc
    return parsed if isinstance(parsed, dict) else {}


def validate_parameter_value(name: str, definition: Mapping[str, Any], value: Any) -> Any:
    parameter_type = definition.get("type")
    if parameter_type == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise NeuralStockError(f"parameter {name!r} must be a number")
        normalized: Any = float(value)
        if not math.isfinite(normalized):
            raise NeuralStockError(f"parameter {name!r} must be finite")
    elif parameter_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise NeuralStockError(f"parameter {name!r} must be an integer")
        normalized = value
    elif parameter_type == "boolean":
        if not isinstance(value, bool):
            raise NeuralStockError(f"parameter {name!r} must be a boolean")
        normalized = value
    elif parameter_type == "enum":
        if not isinstance(value, str) or value not in definition.get("options", []):
            raise NeuralStockError(
                f"parameter {name!r} must be one of {definition.get('options', [])!r}"
            )
        normalized = value
    elif parameter_type == "vector":
        if (
            not isinstance(value, list)
            or len(value) != int(definition.get("size", 3))
            or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value)
        ):
            raise NeuralStockError(f"parameter {name!r} must be a numeric vector")
        normalized = [float(item) for item in value]
        if not all(math.isfinite(item) for item in normalized):
            raise NeuralStockError(f"parameter {name!r} must contain finite values")
    else:
        raise NeuralStockError(f"parameter {name!r} has unsupported type {parameter_type!r}")

    if parameter_type in {"float", "integer"}:
        minimum = definition.get("minimum", definition.get("min"))
        maximum = definition.get("maximum", definition.get("max"))
        if minimum is not None and normalized < minimum:
            raise NeuralStockError(f"parameter {name!r} is below its minimum {minimum}")
        if maximum is not None and normalized > maximum:
            raise NeuralStockError(f"parameter {name!r} is above its maximum {maximum}")
    return normalized


def save_blend(path: str | os.PathLike[str]) -> None:
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Build outputs are immutable artifacts; editor-style .blend1 backups would
    # make the output set depend on whether a prior build happened to exist.
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(destination), compress=False, relative_remap=False)


def require_current_blend_path() -> Path:
    if not bpy.data.filepath:
        raise NeuralStockError("the current scene has not been saved as a .blend file")
    path = Path(bpy.data.filepath)
    if not path.is_file():
        raise NeuralStockError(f"current .blend path does not exist: {path}")
    return path


def finish_message(action: str, **fields: Any) -> None:
    details = " ".join(f"{key}={fields[key]}" for key in sorted(fields))
    print(f"NEURALSTOCK {action}{(' ' + details) if details else ''}", flush=True)
