"""Deterministic scene inspection and GLB export for NeuralStock assets."""

from __future__ import annotations

import math
import ntpath
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import bpy
from ns_common import (
    ANCHOR_PREFIX,
    ASSET_COLLECTION,
    COLLISION_COLLECTION,
    TOOL_NAME,
    TOOL_VERSION,
    NeuralStockError,
    anchor_objects,
    asset_objects,
    bounds_for_objects,
    collision_objects,
    custom_properties,
    evaluated_mesh_data,
    load_parameter_schema,
    object_is_collision,
    stable_json_value,
    visual_mesh_objects,
)

_RESOURCE_PATH_PROPERTIES = {
    "cache_files": ("filepath",),
    "fonts": ("filepath",),
    "images": ("filepath", "filepath_raw"),
    "libraries": ("filepath",),
    "movieclips": ("filepath",),
    "sounds": ("filepath",),
    "volumes": ("filepath",),
}
_INTERNAL_IMAGE_SOURCES = {"COMPOSITING", "GENERATED", "RENDER_RESULT", "VIEWER"}
_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_SCALE_TOLERANCE = 1e-6
_COLLISION_TOLERANCE = 1e-6
_ANCHOR_NAME = re.compile(r"^ANCHOR_[a-z][a-z0-9_]*$")
_COLLISION_NAME = re.compile(r"^COLLISION_[a-z][a-z0-9_]*$")
_PARAMETER_NAME = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_ALLOWED_COLLISION_KINDS = {"box"}
_ALLOWED_PARAMETER_TYPES = {"float", "integer", "boolean", "enum"}


def _collection_items(collection: Any) -> tuple[Any, ...]:
    """Materialize a Blender RNA collection without relying on mapping methods."""

    try:
        return tuple(collection)
    except (ReferenceError, RuntimeError, TypeError):
        return ()


def _data_block_key(value: Any) -> tuple[str, int]:
    try:
        return ("pointer", int(value.as_pointer()))
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        return ("python", id(value))


def _data_block_name(value: Any) -> str:
    for attribute in ("name_full", "name"):
        try:
            name = getattr(value, attribute, None)
        except (AttributeError, ReferenceError, RuntimeError):
            continue
        if name:
            return str(name)
    return type(value).__name__


def _summarize(values: Iterable[str], *, limit: int = 8, character_limit: int = 700) -> str:
    items = sorted(set(values))
    if not items:
        return "none"
    displayed = items[:limit]
    suffix = f" (+{len(items) - limit} more)" if len(items) > limit else ""
    summary = ", ".join(displayed) + suffix
    if len(summary) > character_limit:
        return summary[: character_limit - 3] + "..."
    return summary


def _collection_contains(collection: Any, target: Any) -> bool:
    target_key = _data_block_key(target)
    return any(_data_block_key(item) == target_key for item in _collection_items(collection))


def _objects_in_collection_tree(collection: Any) -> set[tuple[str, int]]:
    object_keys: set[tuple[str, int]] = set()
    pending = [collection]
    visited: set[tuple[str, int]] = set()
    while pending:
        current = pending.pop()
        current_key = _data_block_key(current)
        if current_key in visited:
            continue
        visited.add(current_key)
        object_keys.update(
            _data_block_key(obj) for obj in _collection_items(getattr(current, "objects", ()))
        )
        pending.extend(_collection_items(getattr(current, "children", ())))
    return object_keys


def _visual_meshes() -> list[bpy.types.Object]:
    return sorted(
        (
            obj
            for obj in _collection_items(getattr(bpy.data, "objects", ()))
            if getattr(obj, "type", None) == "MESH" and not object_is_collision(obj)
        ),
        key=_data_block_name,
    )


def _iter_blend_data_blocks() -> Iterable[Any]:
    """Yield every ID collection exposed by Blender 4.5's BlendData RNA."""

    seen: set[tuple[str, int]] = set()
    properties = _collection_items(getattr(getattr(bpy.data, "bl_rna", None), "properties", ()))
    for prop in properties:
        if getattr(prop, "type", None) != "COLLECTION":
            continue
        identifier = str(getattr(prop, "identifier", ""))
        if not identifier or identifier == "rna_type":
            continue
        for item in _collection_items(getattr(bpy.data, identifier, ())):
            key = _data_block_key(item)
            if key in seen:
                continue
            seen.add(key)
            yield item


def _iter_node_trees() -> Iterable[Any]:
    seen: set[tuple[str, int]] = set()
    for block in _iter_blend_data_blocks():
        candidates = [block] if hasattr(block, "nodes") else []
        try:
            node_tree = getattr(block, "node_tree", None)
        except (AttributeError, ReferenceError, RuntimeError):
            node_tree = None
        if node_tree is not None:
            candidates.append(node_tree)
        for tree in candidates:
            key = _data_block_key(tree)
            if key in seen:
                continue
            seen.add(key)
            yield tree


def _driver_descriptions() -> list[str]:
    owners = list(_iter_blend_data_blocks())
    owners.extend(_iter_node_trees())
    descriptions: list[str] = []
    seen: set[tuple[str, int]] = set()
    for owner in owners:
        owner_key = _data_block_key(owner)
        if owner_key in seen:
            continue
        seen.add(owner_key)
        try:
            animation_data = getattr(owner, "animation_data", None)
            drivers = _collection_items(getattr(animation_data, "drivers", ()))
        except (AttributeError, ReferenceError, RuntimeError):
            continue
        for driver in drivers:
            data_path = str(getattr(driver, "data_path", "<unknown>"))
            array_index = int(getattr(driver, "array_index", 0))
            descriptions.append(
                f"{type(owner).__name__}:{_data_block_name(owner)}:{data_path}[{array_index}]"
            )
    return sorted(descriptions)


def _script_node_descriptions() -> list[str]:
    descriptions: list[str] = []
    for tree in _iter_node_trees():
        for node in _collection_items(getattr(tree, "nodes", ())):
            node_type = str(getattr(node, "type", "")).upper()
            identifier = str(getattr(node, "bl_idname", "")).upper()
            if "SCRIPT" not in node_type and "SCRIPT" not in identifier:
                continue
            descriptions.append(f"{_data_block_name(tree)}/{_data_block_name(node)}")
    return sorted(descriptions)


def _resource_is_packed(resource: Any) -> bool:
    try:
        if getattr(resource, "packed_file", None) is not None:
            return True
        return len(_collection_items(getattr(resource, "packed_files", ()))) > 0
    except (AttributeError, ReferenceError, RuntimeError):
        return False


def _resource_is_internal(collection_name: str, resource: Any, path: str) -> bool:
    if collection_name == "images":
        source = str(getattr(resource, "source", "")).upper()
        return source in _INTERNAL_IMAGE_SOURCES
    if collection_name == "fonts":
        return path == "<builtin>"
    return False


def _path_violation(path: str, *, packed: bool) -> str | None:
    value = path.strip()
    if not value:
        return None if packed else "external"

    # Blender's leading // denotes a path relative to the .blend file, not a
    # protocol-relative network location.
    blender_relative = value.startswith("//") and not value.startswith("///")
    windows_drive = re.match(r"^[A-Za-z]:", value) is not None
    if value.startswith("\\\\") or (_URI_SCHEME.match(value) and not windows_drive):
        return "network-or-uri"
    if not blender_relative and (os.path.isabs(value) or ntpath.isabs(value)):
        return "absolute"
    if windows_drive:
        return "absolute"
    return None if packed else "external"


def _rna_path_values(owner: Any) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    properties = _collection_items(getattr(getattr(owner, "bl_rna", None), "properties", ()))
    for prop in properties:
        if getattr(prop, "type", None) != "STRING":
            continue
        if getattr(prop, "subtype", None) not in {"DIR_PATH", "FILE_PATH"}:
            continue
        identifier = str(getattr(prop, "identifier", ""))
        if not identifier or identifier == "rna_type":
            continue
        try:
            path = str(getattr(owner, identifier, "") or "")
        except (AttributeError, ReferenceError, RuntimeError):
            continue
        if path:
            values.append((identifier, path))
    return values


def _resource_path_descriptions() -> list[str]:
    descriptions: set[str] = set()
    for collection_name, properties in _RESOURCE_PATH_PROPERTIES.items():
        resources = _collection_items(getattr(bpy.data, collection_name, ()))
        for resource in resources:
            packed = _resource_is_packed(resource)
            found_path = False
            for attribute in properties:
                try:
                    path = str(getattr(resource, attribute, "") or "")
                except (AttributeError, ReferenceError, RuntimeError):
                    continue
                if not path:
                    continue
                found_path = True
                internal = _resource_is_internal(collection_name, resource, path)
                reason = _path_violation(path, packed=packed or internal)
                if reason is not None:
                    descriptions.add(
                        f"{collection_name}:{_data_block_name(resource)}.{attribute} ({reason})"
                    )
            if found_path or _resource_is_internal(collection_name, resource, ""):
                continue
            if not packed:
                descriptions.add(
                    f"{collection_name}:{_data_block_name(resource)}.filepath (external)"
                )

    path_owners: list[tuple[str, Any]] = []
    for tree in _iter_node_trees():
        path_owners.extend(
            (f"node:{_data_block_name(tree)}", node)
            for node in _collection_items(getattr(tree, "nodes", ()))
        )
    for obj in _collection_items(getattr(bpy.data, "objects", ())):
        path_owners.extend(
            (f"modifier:{_data_block_name(obj)}", modifier)
            for modifier in _collection_items(getattr(obj, "modifiers", ()))
        )
    for scene in _collection_items(getattr(bpy.data, "scenes", ())):
        sequence_editor = getattr(scene, "sequence_editor", None)
        if sequence_editor is None:
            continue
        strips = getattr(sequence_editor, "strips_all", None)
        if strips is None:
            strips = getattr(sequence_editor, "sequences_all", ())
        path_owners.extend(
            (f"strip:{_data_block_name(scene)}", strip) for strip in _collection_items(strips)
        )

    for category, owner in path_owners:
        for attribute, path in _rna_path_values(owner):
            reason = _path_violation(path, packed=False)
            if reason is not None:
                descriptions.add(f"{category}:{_data_block_name(owner)}.{attribute} ({reason})")
    return sorted(descriptions)


def _points_are_axis_aligned_box(points: Iterable[Any]) -> bool:
    coordinates: list[tuple[float, float, float]] = []
    for point in points:
        try:
            coordinate = tuple(float(point[index]) for index in range(3))
        except (IndexError, TypeError, ValueError):
            return False
        if not all(math.isfinite(value) for value in coordinate):
            return False
        coordinates.append(coordinate)
    if len(coordinates) != 8:
        return False

    minimum = tuple(min(point[index] for point in coordinates) for index in range(3))
    maximum = tuple(max(point[index] for point in coordinates) for index in range(3))
    if any(high - low <= _COLLISION_TOLERANCE for low, high in zip(minimum, maximum, strict=True)):
        return False

    unmatched = [
        (x, y, z)
        for x in (minimum[0], maximum[0])
        for y in (minimum[1], maximum[1])
        for z in (minimum[2], maximum[2])
    ]
    for point in coordinates:
        match = next(
            (
                index
                for index, corner in enumerate(unmatched)
                if all(
                    abs(actual - expected) <= _COLLISION_TOLERANCE
                    for actual, expected in zip(point, corner, strict=True)
                )
            ),
            None,
        )
        if match is None:
            return False
        unmatched.pop(match)
    return not unmatched


def _web_v1_source_checks() -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    def check(code: str, passed: bool, success: str, failure: str) -> None:
        checks.append(
            {
                "code": code,
                "status": "pass" if passed else "fail",
                "message": success if passed else failure,
            }
        )

    collections = _collection_items(getattr(bpy.data, "collections", ()))
    asset_collections = [
        collection
        for collection in collections
        if str(getattr(collection, "name", "")) == ASSET_COLLECTION
    ]
    asset_collection = asset_collections[0] if len(asset_collections) == 1 else None
    nested_parents: list[str] = []
    root_scenes: list[str] = []
    if asset_collection is not None:
        nested_parents = [
            _data_block_name(collection)
            for collection in collections
            if _collection_contains(getattr(collection, "children", ()), asset_collection)
        ]
        root_scenes = [
            _data_block_name(scene)
            for scene in _collection_items(getattr(bpy.data, "scenes", ()))
            if _collection_contains(getattr(scene.collection, "children", ()), asset_collection)
        ]
    active_scene_name = _data_block_name(bpy.context.scene)
    single_top_level = (
        asset_collection is not None and not nested_parents and root_scenes == [active_scene_name]
    )
    check(
        "single_top_level_asset_collection",
        single_top_level,
        "Exactly one ASSET collection is linked directly to the active scene root.",
        "Expected one ASSET collection linked only at the active scene root; "
        f"found {len(asset_collections)}, nested parents [{_summarize(nested_parents)}], "
        f"root scenes [{_summarize(root_scenes)}].",
    )

    visual_meshes = _visual_meshes()
    contained_keys = (
        _objects_in_collection_tree(asset_collection) if asset_collection is not None else set()
    )
    outside_meshes = [
        _data_block_name(obj) for obj in visual_meshes if _data_block_key(obj) not in contained_keys
    ]
    check(
        "visual_meshes_in_asset_collection",
        not outside_meshes,
        "Every visual mesh belongs to the ASSET collection tree.",
        "Visual meshes outside the ASSET collection tree: " + _summarize(outside_meshes) + ".",
    )

    anchor_violations: list[str] = []
    anchor_candidates = [
        obj
        for obj in _collection_items(getattr(bpy.data, "objects", ()))
        if _data_block_name(obj).startswith(ANCHOR_PREFIX) or "neuralstock_anchor_role" in obj
    ]
    for obj in anchor_candidates:
        name = _data_block_name(obj)
        if getattr(obj, "type", None) != "EMPTY":
            anchor_violations.append(f"{name} is not an EMPTY")
        if _ANCHOR_NAME.fullmatch(name) is None:
            anchor_violations.append(f"{name} has an invalid name")
        if _data_block_key(obj) not in contained_keys:
            anchor_violations.append(f"{name} is outside the ASSET collection tree")
    check(
        "anchor_contract",
        not anchor_violations,
        "Every anchor is a correctly named EMPTY in the ASSET collection tree.",
        "Anchor contract violations: " + _summarize(anchor_violations) + ".",
    )

    collision_collections = [
        collection
        for collection in collections
        if str(getattr(collection, "name", "")) == COLLISION_COLLECTION
    ]
    collision_collection = collision_collections[0] if len(collision_collections) == 1 else None
    collision_keys = (
        _objects_in_collection_tree(collision_collection)
        if collision_collection is not None
        else set()
    )
    collision_violations: list[str] = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    if collision_collection is None:
        collision_violations.append(
            f"expected exactly one {COLLISION_COLLECTION} collection; "
            f"found {len(collision_collections)}"
        )
    for obj in collision_objects():
        name = _data_block_name(obj)
        if getattr(obj, "type", None) != "MESH":
            collision_violations.append(f"{name} is not a MESH")
        if _COLLISION_NAME.fullmatch(name) is None:
            collision_violations.append(f"{name} has an invalid name")
        if _data_block_key(obj) not in collision_keys:
            collision_violations.append(f"{name} is outside the COLLISION collection tree")
        if not bool(getattr(obj, "hide_render", False)):
            collision_violations.append(f"{name} is renderable")
        kind = str(obj.get("neuralstock_collision_shape", "mesh"))
        if kind not in _ALLOWED_COLLISION_KINDS:
            collision_violations.append(f"{name} has unsupported kind {kind!r}")
        elif getattr(obj, "type", None) == "MESH":
            points, counts = evaluated_mesh_data(obj, depsgraph)
            if counts["vertices"] != 8 or counts["triangles"] != 12:
                collision_violations.append(f"{name} is not an 8-vertex, 12-triangle box")
            elif not _points_are_axis_aligned_box(points):
                collision_violations.append(
                    f"{name} is not an exact positive-volume asset-local AABB"
                )
    check(
        "collision_contract",
        not collision_violations,
        "Collision proxies are exact nonrendered asset-local boxes in the required collection.",
        "Collision contract violations: " + _summarize(collision_violations) + ".",
    )

    parameter_violations = _parameter_interface_violations()
    check(
        "geometry_node_parameter_interface",
        not parameter_violations,
        "Every declared agent parameter is an exact, linked Geometry Nodes group input.",
        "Geometry Nodes parameter violations: " + _summarize(parameter_violations) + ".",
    )

    unapplied_scale = []
    for obj in visual_meshes:
        try:
            scale = tuple(float(value) for value in obj.scale)
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            scale = ()
        if len(scale) != 3 or any(
            not math.isfinite(value) or abs(value - 1.0) > _SCALE_TOLERANCE for value in scale
        ):
            unapplied_scale.append(f"{_data_block_name(obj)}={scale}")
    check(
        "applied_visual_mesh_scale",
        not unapplied_scale,
        "Every visual mesh has applied local scale [1, 1, 1].",
        "Visual meshes with unapplied local scale: " + _summarize(unapplied_scale) + ".",
    )

    text_blocks = [
        _data_block_name(text) for text in _collection_items(getattr(bpy.data, "texts", ()))
    ]
    check(
        "no_embedded_text_blocks",
        not text_blocks,
        "The source contains no embedded text or Python blocks.",
        "Embedded text or Python blocks are forbidden: " + _summarize(text_blocks) + ".",
    )

    script_nodes = _script_node_descriptions()
    check(
        "no_script_nodes",
        not script_nodes,
        "The source contains no script nodes.",
        "Script nodes are forbidden: " + _summarize(script_nodes) + ".",
    )

    drivers = _driver_descriptions()
    check(
        "no_arbitrary_drivers",
        not drivers,
        "The source contains no animation drivers.",
        "Animation drivers are forbidden: " + _summarize(drivers) + ".",
    )

    libraries = [
        _data_block_name(library)
        for library in _collection_items(getattr(bpy.data, "libraries", ()))
    ]
    check(
        "no_linked_libraries",
        not libraries,
        "The source contains no linked Blender libraries.",
        "Linked Blender libraries are forbidden: " + _summarize(libraries) + ".",
    )

    resource_paths = _resource_path_descriptions()
    check(
        "no_external_resource_paths",
        not resource_paths,
        "The source contains no external, absolute, or network resource paths.",
        "Forbidden resource paths: " + _summarize(resource_paths) + ".",
    )
    return checks


def _enforce_web_v1_source() -> None:
    failures = [check for check in _web_v1_source_checks() if check["status"] == "fail"]
    if not failures:
        return
    summary = "; ".join(f"{check['code']}: {check['message']}" for check in failures)
    raise NeuralStockError(f"web-v1 source preflight failed: {summary}")


def _mesh_metrics(
    objects: Iterable[bpy.types.Object],
    depsgraph: bpy.types.Depsgraph,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    totals = {
        "mesh_count": 0,
        "vertex_count": 0,
        "edge_count": 0,
        "polygon_count": 0,
        "triangle_count": 0,
        "primitive_count": 0,
    }
    details: list[dict[str, Any]] = []
    for obj in sorted(objects, key=lambda item: item.name):
        if obj.type != "MESH":
            continue
        points, counts = evaluated_mesh_data(obj, depsgraph)
        del points
        totals["mesh_count"] += 1
        totals["vertex_count"] += counts["vertices"]
        totals["edge_count"] += counts["edges"]
        totals["polygon_count"] += counts["polygons"]
        totals["triangle_count"] += counts["triangles"]

        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
        material_indices: set[int] = set()
        try:
            if mesh is not None:
                material_indices = {polygon.material_index for polygon in mesh.polygons}
        finally:
            if mesh is not None:
                evaluated.to_mesh_clear()
        primitive_count = max(1, len(material_indices)) if counts["polygons"] else 0
        totals["primitive_count"] += primitive_count
        details.append(
            {
                "name": obj.name,
                "counts": counts,
                "primitive_count": primitive_count,
                "modifiers": [
                    {"name": modifier.name, "type": modifier.type} for modifier in obj.modifiers
                ],
                "material_slots": [
                    slot.material.name if slot.material is not None else None
                    for slot in obj.material_slots
                ],
                "custom_properties": custom_properties(obj),
            }
        )
    return totals, details


def _input_value(node: bpy.types.Node, name: str) -> Any:
    socket = node.inputs.get(name)
    if socket is None or not hasattr(socket, "default_value"):
        return None
    return stable_json_value(socket.default_value)


def _materials(objects: Iterable[bpy.types.Object]) -> tuple[dict[str, Any], dict[str, Any]]:
    material_map: dict[str, bpy.types.Material] = {}
    for obj in objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            if slot.material is not None:
                material_map[slot.material.name] = slot.material

    details: list[dict[str, Any]] = []
    image_map: dict[str, bpy.types.Image] = {}
    for name in sorted(material_map):
        material = material_map[name]
        principled = None
        if material.use_nodes and material.node_tree is not None:
            principled = next(
                (node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"),
                None,
            )
            for node in material.node_tree.nodes:
                if node.type == "TEX_IMAGE" and getattr(node, "image", None) is not None:
                    image_map[node.image.name] = node.image
        details.append(
            {
                "name": material.name,
                "uses_nodes": material.use_nodes,
                "base_color": _input_value(principled, "Base Color") if principled else None,
                "metallic": _input_value(principled, "Metallic") if principled else None,
                "roughness": _input_value(principled, "Roughness") if principled else None,
                "custom_properties": custom_properties(material),
            }
        )

    texture_details: list[dict[str, Any]] = []
    public_texture_items: list[dict[str, Any]] = []
    total_bytes = 0
    maximum_dimension = 0
    all_packed = True
    missing: list[str] = []
    for name in sorted(image_map):
        image = image_map[name]
        width = int(image.size[0]) if len(image.size) > 0 else 0
        height = int(image.size[1]) if len(image.size) > 1 else 0
        maximum_dimension = max(maximum_dimension, width, height)
        packed = image.packed_file is not None
        byte_count = 0
        resolved_path = ""
        if packed:
            try:
                byte_count = len(image.packed_file.data)
            except (AttributeError, TypeError):
                byte_count = 0
        elif image.source == "FILE" and image.filepath:
            # web-v1 forbids unpacked source dependencies. Do not resolve or
            # probe contributor-controlled paths during inspection.
            resolved_path = str(image.filepath)
            missing.append(image.name)
        elif image.source not in {"GENERATED", "VIEWER", "RENDER_RESULT", "COMPOSITING"}:
            missing.append(image.name)
        total_bytes += byte_count
        all_packed = all_packed and packed
        texture_details.append(
            {
                "name": image.name,
                "source": image.source,
                "size_px": [width, height],
                "bytes": byte_count,
                "packed": packed,
                "path": Path(resolved_path).name if resolved_path else None,
                "missing": image.name in missing,
            }
        )

        media_type = {
            "PNG": "image/png",
            "JPEG": "image/jpeg",
            "WEBP": "image/webp",
        }.get(str(getattr(image, "file_format", "")).upper())
        if width > 0 and height > 0 and byte_count > 0 and media_type is not None:
            public_texture_items.append(
                {
                    "name": image.name,
                    "width_px": width,
                    "height_px": height,
                    "bytes": byte_count,
                    "media_type": media_type,
                    "packed": packed,
                }
            )

    public_materials = {"count": len(material_map), "names": sorted(material_map)}
    public_textures = {
        "count": len(image_map),
        "total_bytes": total_bytes,
        "max_dimension_px": maximum_dimension,
        "all_packed": all_packed,
        "items": public_texture_items,
    }
    detailed = {
        "materials": details,
        "textures": texture_details,
        "missing_textures": missing,
    }
    return {"materials": public_materials, "textures": public_textures}, detailed


def _transform(obj: bpy.types.Object) -> dict[str, Any]:
    matrix = obj.matrix_world
    translation, rotation, scale = matrix.decompose()
    return {
        "position_m": stable_json_value(translation),
        "rotation_quaternion_wxyz": stable_json_value(
            [rotation.w, rotation.x, rotation.y, rotation.z]
        ),
        "scale": stable_json_value(scale),
    }


def _anchors() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    public: list[dict[str, Any]] = []
    detailed: list[dict[str, Any]] = []
    for obj in anchor_objects():
        role = str(obj.get("neuralstock_anchor_role", obj.name[len(ANCHOR_PREFIX) :]))
        transform = _transform(obj)
        public.append(
            {
                "name": obj.name,
                "position_m": transform["position_m"],
                "rotation_xyzw": [
                    transform["rotation_quaternion_wxyz"][1],
                    transform["rotation_quaternion_wxyz"][2],
                    transform["rotation_quaternion_wxyz"][3],
                    transform["rotation_quaternion_wxyz"][0],
                ],
                "semantic": role,
            }
        )
        detailed.append(
            {
                "name": obj.name,
                "role": role,
                "transform": transform,
                "custom_properties": custom_properties(obj),
            }
        )
    return public, detailed


def _collisions(
    depsgraph: bpy.types.Depsgraph,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    public: list[dict[str, Any]] = []
    detailed: list[dict[str, Any]] = []
    for obj in collision_objects():
        if obj.type != "MESH":
            continue
        _, counts = evaluated_mesh_data(obj, depsgraph)
        shape = str(obj.get("neuralstock_collision_shape", "mesh"))
        bounds = bounds_for_objects([obj], depsgraph)
        public.append(
            {
                "name": obj.name,
                "kind": shape,
                "bounds_m": bounds,
                "vertex_count": counts["vertices"],
                "triangle_count": counts["triangles"],
            }
        )
        detailed.append(
            {
                "name": obj.name,
                "shape": shape,
                "bounds_m": bounds,
                "counts": counts,
                "transform": _transform(obj),
                "custom_properties": custom_properties(obj),
            }
        )
    return public, detailed


def _socket_type(socket: Any) -> str:
    socket_name = str(getattr(socket, "socket_type", ""))
    return {
        "NodeSocketFloat": "float",
        "NodeSocketInt": "integer",
        "NodeSocketBool": "boolean",
        "NodeSocketVector": "vector",
        "NodeSocketString": "string",
        "NodeSocketColor": "color",
        "NodeSocketObject": "object",
        "NodeSocketMaterial": "material",
        "NodeSocketCollection": "collection",
        "NodeSocketGeometry": "geometry",
        "NodeSocketMenu": "enum",
    }.get(socket_name, socket_name or "unknown")


def _socket_is_linked(node_group: Any, socket: Any) -> bool:
    identifier = str(getattr(socket, "identifier", ""))
    name = str(getattr(socket, "name", ""))
    for link in _collection_items(getattr(node_group, "links", ())):
        from_node = getattr(link, "from_node", None)
        if (
            getattr(from_node, "type", None) != "GROUP_INPUT"
            and getattr(from_node, "bl_idname", None) != "NodeGroupInput"
        ):
            continue
        from_socket = getattr(link, "from_socket", None)
        if (
            str(getattr(from_socket, "identifier", "")) == identifier
            or str(getattr(from_socket, "name", "")) == name
        ):
            return True
    return False


def _non_geometry_input_sockets(modifier: Any) -> list[Any]:
    node_group = getattr(modifier, "node_group", None)
    if node_group is None:
        return []
    return [
        socket
        for socket in _collection_items(getattr(node_group.interface, "items_tree", ()))
        if getattr(socket, "item_type", None) == "SOCKET"
        and getattr(socket, "in_out", None) == "INPUT"
        and _socket_type(socket) != "geometry"
    ]


def _values_match(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and not isinstance(left, bool):
        if not isinstance(right, (int, float)) or isinstance(right, bool):
            return False
        return math.isclose(float(left), float(right), rel_tol=1e-6, abs_tol=1e-6)
    return left == right


def _parameter_interface_violations() -> list[str]:
    try:
        declarations = load_parameter_schema()
    except NeuralStockError as error:
        return [str(error)]

    generator = bpy.context.scene.get("neuralstock_geometry_node_group")
    node_group_name = str(generator) if generator else None
    modifiers: list[tuple[Any, Any, list[Any]]] = []
    for obj in _collection_items(getattr(bpy.data, "objects", ())):
        for modifier in _collection_items(getattr(obj, "modifiers", ())):
            if getattr(modifier, "type", None) != "NODES" or modifier.node_group is None:
                continue
            modifiers.append((obj, modifier, _non_geometry_input_sockets(modifier)))

    violations: list[str] = []
    if not declarations:
        if node_group_name is not None:
            violations.append("a generator group is declared without public parameters")
        exposed = [
            f"{_data_block_name(obj)}/{modifier.name}/{socket.name}"
            for obj, modifier, sockets in modifiers
            for socket in sockets
        ]
        if exposed:
            violations.append("undeclared group inputs: " + _summarize(exposed))
        return violations

    if node_group_name is None:
        violations.append("public parameters exist without a declared generator group")
    if len(declarations) > 32:
        violations.append(f"{len(declarations)} parameters exceed the web-v1 maximum of 32")

    targets = [
        item for item in modifiers if _data_block_name(item[1].node_group) == node_group_name
    ]
    if len(targets) != 1:
        violations.append(f"expected one modifier using {node_group_name!r}; found {len(targets)}")
        target = None
    else:
        target = targets[0]

    exposed_elsewhere = [
        f"{_data_block_name(obj)}/{modifier.name}/{socket.name}"
        for obj, modifier, sockets in modifiers
        if _data_block_name(modifier.node_group) != node_group_name
        for socket in sockets
    ]
    if exposed_elsewhere:
        violations.append(
            "unexpected public inputs outside the generator: " + _summarize(exposed_elsewhere)
        )

    actual_by_name: dict[str, Any] = {}
    if target is not None:
        actual_by_name = {str(socket.name): socket for socket in target[2]}
        if set(actual_by_name) != set(declarations):
            missing = sorted(set(declarations) - set(actual_by_name))
            extra = sorted(set(actual_by_name) - set(declarations))
            violations.append(f"group input names differ; missing {missing}, extra {extra}")

    for name in sorted(declarations):
        declaration = declarations[name]
        if not isinstance(declaration, Mapping):
            violations.append(f"{name!r} declaration is not an object")
            continue
        if _PARAMETER_NAME.fullmatch(name) is None:
            violations.append(f"{name!r} has an invalid identifier")
        declared_type = declaration.get("type")
        if declared_type not in _ALLOWED_PARAMETER_TYPES:
            violations.append(f"{name!r} has unsupported type {declared_type!r}")
        if not bool(declaration.get("agent_safe", False)):
            violations.append(f"{name!r} is not agent-safe")

        binding = declaration.get("binding")
        if not isinstance(binding, Mapping) or binding.get("kind") != "geometry_nodes":
            violations.append(f"{name!r} is not bound to a Geometry Nodes input")
            continue
        if binding.get("node_group") != node_group_name:
            violations.append(f"{name!r} binding names the wrong node group")
        if target is None:
            continue
        obj, modifier, _ = target
        if binding.get("object") != _data_block_name(obj):
            violations.append(f"{name!r} binding names the wrong object")
        if binding.get("modifier") != modifier.name:
            violations.append(f"{name!r} binding names the wrong modifier")

        socket = actual_by_name.get(name)
        if socket is None:
            continue
        if binding.get("socket_identifier") != str(getattr(socket, "identifier", "")):
            violations.append(f"{name!r} binding names the wrong socket identifier")
        if _socket_type(socket) != declared_type:
            violations.append(
                f"{name!r} socket type {_socket_type(socket)!r} differs from {declared_type!r}"
            )
        if not _values_match(getattr(socket, "default_value", None), declaration.get("default")):
            violations.append(f"{name!r} socket default differs from its declaration")
        if declared_type in {"float", "integer"}:
            if not _values_match(getattr(socket, "min_value", None), declaration.get("minimum")):
                violations.append(f"{name!r} socket minimum differs from its declaration")
            if not _values_match(getattr(socket, "max_value", None), declaration.get("maximum")):
                violations.append(f"{name!r} socket maximum differs from its declaration")
        if not _socket_is_linked(modifier.node_group, socket):
            violations.append(f"{name!r} is exposed but not linked into the node graph")
    return violations


def _geometry_nodes() -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    declarations = load_parameter_schema()
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        for modifier in obj.modifiers:
            if modifier.type != "NODES" or modifier.node_group is None:
                continue
            inputs: list[dict[str, Any]] = []
            for socket in modifier.node_group.interface.items_tree:
                if getattr(socket, "item_type", None) != "SOCKET":
                    continue
                if getattr(socket, "in_out", None) != "INPUT":
                    continue
                parameter_type = _socket_type(socket)
                if parameter_type == "geometry":
                    continue
                identifier = str(socket.identifier)
                value = modifier.get(identifier, getattr(socket, "default_value", None))
                declaration = declarations.get(socket.name, {})
                item: dict[str, Any] = {
                    "name": socket.name,
                    "identifier": identifier,
                    "type": declaration.get("type", parameter_type),
                    "value": stable_json_value(value),
                    "default": stable_json_value(getattr(socket, "default_value", None)),
                    "description": getattr(socket, "description", ""),
                    "agent_safe": bool(declaration.get("agent_safe", False)),
                    "linked": _socket_is_linked(modifier.node_group, socket),
                }
                for key, attribute in (("min", "min_value"), ("max", "max_value")):
                    if hasattr(socket, attribute):
                        item[key] = stable_json_value(getattr(socket, attribute))
                if "options" in declaration:
                    item["options"] = stable_json_value(declaration["options"])
                inputs.append(item)
            groups.append(
                {
                    "object": obj.name,
                    "modifier": modifier.name,
                    "node_group": modifier.node_group.name,
                    "inputs": inputs,
                }
            )
    return groups


def _public_parameters() -> dict[str, Any]:
    declarations = load_parameter_schema()
    parameters: dict[str, Any] = {}
    for name in sorted(declarations):
        declaration = declarations[name]
        if not isinstance(declaration, Mapping):
            continue
        public = {
            key: stable_json_value(value) for key, value in declaration.items() if key != "binding"
        }
        parameters[name] = public
    node_group = bpy.context.scene.get("neuralstock_geometry_node_group")
    return {"node_group": str(node_group) if node_group else None, "inputs": parameters}


def _profile_validation(
    bounds: Mapping[str, Any],
    geometry: Mapping[str, Any],
    texture_summary: Mapping[str, Any],
    source_checks: Iterable[Mapping[str, str]],
) -> dict[str, Any]:
    scene = bpy.context.scene
    checks = [dict(item) for item in source_checks]

    def check(name: str, passed: bool, message: str) -> None:
        checks.append({"code": name, "status": "pass" if passed else "fail", "message": message})

    check(
        "metric_units",
        scene.unit_settings.system == "METRIC"
        and abs(scene.unit_settings.scale_length - 1.0) <= 1e-9,
        "Scene units must be meters with scale_length=1.",
    )
    minimum = bounds["minimum"]
    maximum = bounds["maximum"]
    ground_centered = (
        abs(float(minimum[2])) <= 1e-5
        and abs((float(minimum[0]) + float(maximum[0])) * 0.5) <= 1e-5
        and abs((float(minimum[1]) + float(maximum[1])) * 0.5) <= 1e-5
    )
    check(
        "ground_center_origin",
        ground_centered,
        "Evaluated visual bounds must be centered on X/Y with minimum Z at zero.",
    )
    check(
        "nonempty_geometry",
        int(geometry["mesh_count"]) > 0 and int(geometry["triangle_count"]) > 0,
        "At least one non-empty evaluated visual mesh is required.",
    )
    check(
        "packed_textures",
        bool(texture_summary["all_packed"]),
        "All material texture images must be packed in the source.",
    )
    check(
        "anchor_names",
        all(obj.name.startswith(ANCHOR_PREFIX) for obj in anchor_objects()),
        f"Anchor empties must use the {ANCHOR_PREFIX} prefix.",
    )
    status = "pass" if all(item["status"] == "pass" for item in checks) else "fail"
    return {"status": status, "checks": checks}


def build_inspection(
    *,
    asset_id: str,
    asset_version: str,
    source_sha256: str,
    target_profile: str,
    generated_timestamp: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_checks = _web_v1_source_checks()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    visual_objects = visual_mesh_objects()
    bounds = bounds_for_objects(visual_objects, depsgraph)
    geometry, mesh_details = _mesh_metrics(visual_objects, depsgraph)
    public_resources, resource_details = _materials(visual_objects)
    anchors, anchor_details = _anchors()
    collisions, collision_details = _collisions(depsgraph)
    parameters = _public_parameters()
    geometry_nodes = _geometry_nodes()
    profile_validation = _profile_validation(
        bounds,
        geometry,
        public_resources["textures"],
        source_checks,
    )

    inspection = {
        "$schema": "https://schemas.neuralstock.ai/v0.2/inspection.schema.json",
        "schema_version": "0.2",
        "document_type": "inspection",
        "generated": True,
        "asset": {"id": asset_id, "version": asset_version},
        "generated_at": generated_timestamp,
        "generator": {"tool": TOOL_NAME, "version": TOOL_VERSION},
        "source_sha256": source_sha256,
        "target_profile": target_profile,
        "coordinate_system": {
            "unit": "meter",
            "meters_per_unit": 1,
            "up_axis": "Z",
            "forward_axis": "-Y",
            "handedness": "right",
            "space": "asset-local",
        },
        "bounds_m": bounds,
        "origin": {
            "policy": "ground-center-of-evaluated-bounds",
            "position_m": [0, 0, 0],
        },
        "geometry": {
            key: geometry[key]
            for key in (
                "mesh_count",
                "vertex_count",
                "triangle_count",
                "primitive_count",
            )
        },
        "materials": public_resources["materials"],
        "textures": public_resources["textures"],
        "anchors": anchors,
        "collisions": collisions,
        "parameters": parameters,
        "gltf_validation": {
            "validator_version": "not-run-by-blender-stage",
            "status": "fail",
            "errors": 1,
            "warnings": 0,
        },
        "profile_validation": profile_validation,
    }

    details = {
        "schema_version": "0.2",
        "asset": {"id": asset_id, "version": asset_version},
        "blender": {
            "version": bpy.app.version_string,
            "version_cycle": bpy.app.version_cycle,
            "build_hash": bpy.app.build_hash.decode("utf-8", errors="replace")
            if isinstance(bpy.app.build_hash, bytes)
            else str(bpy.app.build_hash),
        },
        "scene": {
            "name": bpy.context.scene.name,
            "custom_properties": custom_properties(bpy.context.scene),
        },
        "objects": mesh_details,
        "anchors": anchor_details,
        "collisions": collision_details,
        "geometry_nodes": geometry_nodes,
        "materials": resource_details["materials"],
        "textures": resource_details["textures"],
        "linked_libraries": [
            {"name": library.name, "path": Path(bpy.path.abspath(library.filepath)).name}
            for library in sorted(bpy.data.libraries, key=lambda item: item.name)
        ],
        "profile_validation": profile_validation,
        "evaluated_geometry": geometry,
    }
    return stable_json_value(inspection), stable_json_value(details)


def _supported_operator_arguments(operator: Any, values: Mapping[str, Any]) -> dict[str, Any]:
    properties = {prop.identifier for prop in operator.get_rna_type().properties}
    return {key: value for key, value in values.items() if key in properties}


def export_glb(path: str | os.PathLike[str], *, include_collision: bool = False) -> None:
    destination = Path(path).resolve()
    if destination.suffix.lower() != ".glb":
        raise NeuralStockError("GLB output path must end in .glb")
    _enforce_web_v1_source()
    destination.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="DESELECT")
    selected = asset_objects(include_collision=include_collision)
    selected = [
        obj
        for obj in selected
        if obj.type in {"MESH", "EMPTY", "ARMATURE"}
        and (include_collision or not object_is_collision(obj))
    ]
    if not any(obj.type == "MESH" for obj in selected):
        raise NeuralStockError("nothing exportable was found in the ASSET collection")
    for obj in selected:
        obj.hide_set(False)
        obj.select_set(True)
    mesh_objects = [obj for obj in selected if obj.type == "MESH"]
    bpy.context.view_layer.objects.active = mesh_objects[0]

    arguments = _supported_operator_arguments(
        bpy.ops.export_scene.gltf,
        {
            "filepath": str(destination),
            "export_format": "GLB",
            "use_selection": True,
            "export_apply": True,
            "export_yup": True,
            "export_extras": True,
            "export_cameras": False,
            "export_lights": False,
            "export_animations": False,
            "export_skins": False,
            "export_morph": False,
            "export_texcoords": True,
            "export_normals": True,
            "export_tangents": False,
            "export_materials": "EXPORT",
            "export_image_format": "AUTO",
            "export_unused_images": False,
            "export_unused_textures": False,
            "will_save_settings": False,
            "check_existing": False,
        },
    )
    result = bpy.ops.export_scene.gltf(**arguments)
    if "FINISHED" not in result or not destination.is_file() or destination.stat().st_size == 0:
        raise NeuralStockError("Blender's glTF exporter did not produce a non-empty GLB")
