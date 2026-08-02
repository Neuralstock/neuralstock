"""Extensible, repository-owned procedural generators for the Room Zero pilot."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

import bpy
from asset_builder import apply_parameter_overrides
from generators_architecture import GENERATORS as ARCHITECTURE_GENERATORS
from generators_furniture import GENERATORS as FURNITURE_GENERATORS
from generators_props import GENERATORS as PROP_GENERATORS
from ns_common import (
    ANCHOR_PREFIX,
    ASSET_COLLECTION,
    COLLISION_COLLECTION,
    NeuralStockError,
    get_or_create_collection,
    reset_scene,
    set_deterministic_scene_defaults,
    store_parameter_schema,
)

Generator = Callable[[str, Mapping[str, Any]], None]
Updater = Callable[[Mapping[str, Any]], None]


CRATE_PARAMETERS: dict[str, dict[str, Any]] = {
    "width_m": {
        "type": "float",
        "default": 0.60,
        "minimum": 0.30,
        "maximum": 2.00,
        "unit": "meter",
        "label": "Width",
        "agent_safe": True,
        "description": "Overall crate width in meters.",
    },
    "depth_m": {
        "type": "float",
        "default": 0.40,
        "minimum": 0.25,
        "maximum": 1.50,
        "unit": "meter",
        "label": "Depth",
        "agent_safe": True,
        "description": "Overall crate depth in meters.",
    },
    "height_m": {
        "type": "float",
        "default": 0.45,
        "minimum": 0.25,
        "maximum": 2.00,
        "unit": "meter",
        "label": "Height",
        "agent_safe": True,
        "description": "Overall crate height in meters.",
    },
}


def available_generators() -> list[str]:
    return sorted(GENERATORS)


def _append_box(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int, int]],
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> None:
    cx, cy, cz = center
    sx, sy, sz = (component * 0.5 for component in size)
    offset = len(vertices)
    vertices.extend(
        [
            (cx - sx, cy - sy, cz - sz),
            (cx + sx, cy - sy, cz - sz),
            (cx + sx, cy + sy, cz - sz),
            (cx - sx, cy + sy, cz - sz),
            (cx - sx, cy - sy, cz + sz),
            (cx + sx, cy - sy, cz + sz),
            (cx + sx, cy + sy, cz + sz),
            (cx - sx, cy + sy, cz + sz),
        ]
    )
    faces.extend(
        [
            (offset + 0, offset + 3, offset + 2, offset + 1),
            (offset + 4, offset + 5, offset + 6, offset + 7),
            (offset + 0, offset + 1, offset + 5, offset + 4),
            (offset + 1, offset + 2, offset + 6, offset + 5),
            (offset + 2, offset + 3, offset + 7, offset + 6),
            (offset + 3, offset + 0, offset + 4, offset + 7),
        ]
    )


def _new_box_mesh(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> bpy.types.Mesh:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    _append_box(vertices, faces, center, size)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    return mesh


def _crate_mesh() -> bpy.types.Mesh:
    """Build a normalized, open wooden shipping crate from separate cuboids."""

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []

    # Five bottom planks with small gaps.
    for index in range(5):
        y = -0.40 + index * 0.20
        _append_box(vertices, faces, (0.0, y, 0.04), (0.92, 0.18, 0.08))

    # Structural corner posts.
    for x in (-0.455, 0.455):
        for y in (-0.455, 0.455):
            _append_box(vertices, faces, (x, y, 0.50), (0.09, 0.09, 1.0))

    # Horizontal slats on the front and back.
    for y in (-0.465, 0.465):
        for z in (0.18, 0.50, 0.82):
            _append_box(vertices, faces, (0.0, y, z), (0.82, 0.07, 0.18))

    # Horizontal slats on the two sides.
    for x in (-0.465, 0.465):
        for z in (0.18, 0.50, 0.82):
            _append_box(vertices, faces, (x, 0.0, z), (0.07, 0.82, 0.18))

    mesh = bpy.data.meshes.new("crate_body_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    return mesh


def _wood_material() -> bpy.types.Material:
    material = bpy.data.materials.new("MAT_Wood_Warm")
    material.use_nodes = True
    material.diffuse_color = (0.34, 0.135, 0.045, 1.0)
    principled = next(
        (node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"),
        None,
    )
    if principled is not None:
        principled.inputs["Base Color"].default_value = (0.34, 0.135, 0.045, 1.0)
        principled.inputs["Roughness"].default_value = 0.58
        principled.inputs["Metallic"].default_value = 0.0
    material["neuralstock_material_role"] = "wood"
    return material


def _make_geometry_node_controller(
    obj: bpy.types.Object,
    definitions: dict[str, dict[str, Any]],
) -> dict[str, str]:
    group = bpy.data.node_groups.new("CrateGenerator", "GeometryNodeTree")
    group.color_tag = "GEOMETRY"
    group.description = "Agent-safe dimensions for the NeuralStock procedural crate."

    geometry_in = group.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    geometry_out = group.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )
    del geometry_in, geometry_out

    socket_by_name: dict[str, Any] = {}
    for name in ("width_m", "depth_m", "height_m"):
        definition = definitions[name]
        socket = group.interface.new_socket(
            name=name, in_out="INPUT", socket_type="NodeSocketFloat"
        )
        socket.default_value = definition["default"]
        socket.min_value = definition["minimum"]
        socket.max_value = definition["maximum"]
        socket.description = definition["description"]
        socket.subtype = "DISTANCE"
        socket_by_name[name] = socket

    nodes = group.nodes
    links = group.links
    group_input = nodes.new("NodeGroupInput")
    group_input.name = "Declared Inputs"
    group_input.label = "Declared Inputs"
    group_input.location = (-420, 0)
    transform = nodes.new("GeometryNodeTransform")
    transform.name = "Apply Dimensions"
    transform.label = "Apply Dimensions"
    transform.location = (20, 0)
    combine = nodes.new("ShaderNodeCombineXYZ")
    combine.name = "Dimensions"
    combine.label = "Dimensions (m)"
    combine.location = (-200, -180)
    group_output = nodes.new("NodeGroupOutput")
    group_output.name = "Generated Geometry"
    group_output.label = "Generated Geometry"
    group_output.location = (260, 0)

    links.new(group_input.outputs["Geometry"], transform.inputs["Geometry"])
    links.new(group_input.outputs["width_m"], combine.inputs["X"])
    links.new(group_input.outputs["depth_m"], combine.inputs["Y"])
    links.new(group_input.outputs["height_m"], combine.inputs["Z"])
    links.new(combine.outputs["Vector"], transform.inputs["Scale"])
    links.new(transform.outputs["Geometry"], group_output.inputs["Geometry"])

    modifier = obj.modifiers.new("NS_Geometry", "NODES")
    modifier.node_group = group
    bindings: dict[str, str] = {}
    for name, socket in socket_by_name.items():
        modifier[socket.identifier] = definitions[name]["default"]
        bindings[name] = socket.identifier
    return bindings


def _create_crate(version: str, overrides: Mapping[str, Any]) -> None:
    reset_scene()
    scene = bpy.context.scene
    set_deterministic_scene_defaults(scene)

    asset_collection = get_or_create_collection(ASSET_COLLECTION)
    collision_collection = get_or_create_collection(COLLISION_COLLECTION)

    root = bpy.data.objects.new("ASSET_ROOT", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.08
    root["neuralstock_role"] = "asset_root"
    asset_collection.objects.link(root)

    body = bpy.data.objects.new("crate_body", _crate_mesh())
    body.parent = root
    body.data.materials.append(_wood_material())
    body["neuralstock_role"] = "visual"
    body["neuralstock_generator"] = "procedural_crate_01"
    asset_collection.objects.link(body)

    definitions = json.loads(json.dumps(CRATE_PARAMETERS))
    geometry_bindings = _make_geometry_node_controller(body, definitions)
    for name, identifier in geometry_bindings.items():
        definitions[name]["binding"] = {
            "kind": "geometry_nodes",
            "object": body.name,
            "modifier": "NS_Geometry",
            "node_group": "CrateGenerator",
            "socket_identifier": identifier,
        }

    bevel = body.modifiers.new("NS_Bevel", "BEVEL")
    bevel.width = 0.006
    bevel.segments = 2
    bevel.limit_method = "ANGLE"

    anchor = bpy.data.objects.new(f"{ANCHOR_PREFIX}top_surface", None)
    anchor.empty_display_type = "ARROWS"
    anchor.empty_display_size = 0.06
    anchor.parent = root
    anchor["neuralstock_anchor_role"] = "top-surface"
    anchor["neuralstock_accepts"] = "placeable"
    asset_collection.objects.link(anchor)

    collision = bpy.data.objects.new(
        "COLLISION_box",
        _new_box_mesh("collision_box_mesh", (0.0, 0.0, 0.5), (1.0, 1.0, 1.0)),
    )
    collision.display_type = "WIRE"
    collision.hide_render = True
    collision["neuralstock_collision"] = True
    collision["neuralstock_collision_shape"] = "box"
    collision_collection.objects.link(collision)

    scene["neuralstock_asset_id"] = "procedural_crate_01"
    scene["neuralstock_asset_version"] = version
    scene["neuralstock_target_profile"] = "web-v1"
    scene["neuralstock_geometry_node_group"] = "CrateGenerator"
    scene["neuralstock_origin_policy"] = "ground_center"
    scene["neuralstock_generator_version"] = "1"
    store_parameter_schema(definitions)
    apply_declared_parameters(overrides)


def _update_crate_derived(values: Mapping[str, Any]) -> None:
    anchor = bpy.data.objects.get("ANCHOR_top_surface")
    collision = bpy.data.objects.get("COLLISION_box")
    if anchor is None or collision is None:
        raise NeuralStockError("procedural crate is missing its anchor or collision proxy")
    anchor.location = (0.0, 0.0, float(values["height_m"]))
    collision.scale = (
        float(values["width_m"]),
        float(values["depth_m"]),
        float(values["height_m"]),
    )


def apply_declared_parameters(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Validate and apply overrides only through declarations embedded in the file."""

    values = apply_parameter_overrides(overrides)
    asset_id = str(bpy.context.scene.get("neuralstock_asset_id", ""))
    updater = UPDATERS.get(asset_id)
    if updater is not None:
        updater(values)
    bpy.context.view_layer.update()
    return values


def generate_asset(
    asset_id: str,
    *,
    version: str = "1.0.1",
    parameters: Mapping[str, Any] | None = None,
) -> None:
    generator = GENERATORS.get(asset_id)
    if generator is None:
        choices = ", ".join(available_generators())
        raise NeuralStockError(f"unknown Room Zero generator {asset_id!r}; available: {choices}")
    generator(version, parameters or {})


# New Room Zero generators register here without changing the command scripts.
GENERATORS: dict[str, Generator] = {
    **ARCHITECTURE_GENERATORS,
    **FURNITURE_GENERATORS,
    **PROP_GENERATORS,
    "procedural_crate_01": _create_crate,
}

UPDATERS: dict[str, Updater] = {
    "procedural_crate_01": _update_crate_derived,
}
