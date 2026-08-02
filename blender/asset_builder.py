"""Reusable construction primitives for coherent Room Zero Blender assets."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import bpy
from mathutils import Euler, Vector
from ns_common import (
    ANCHOR_PREFIX,
    ASSET_COLLECTION,
    COLLISION_COLLECTION,
    NeuralStockError,
    get_or_create_collection,
    load_parameter_schema,
    reset_scene,
    set_deterministic_scene_defaults,
    stable_json_value,
    store_parameter_schema,
    store_parameter_values,
    validate_parameter_value,
)

PALETTE: dict[str, dict[str, Any]] = {
    "wood": {"color": (0.34, 0.135, 0.045, 1.0), "roughness": 0.58},
    "wood_light": {"color": (0.64, 0.32, 0.12, 1.0), "roughness": 0.55},
    "wood_dark": {"color": (0.15, 0.055, 0.022, 1.0), "roughness": 0.62},
    "metal": {"color": (0.12, 0.15, 0.19, 1.0), "roughness": 0.28, "metallic": 0.82},
    "metal_light": {
        "color": (0.48, 0.53, 0.58, 1.0),
        "roughness": 0.23,
        "metallic": 0.78,
    },
    "paint_cream": {"color": (0.73, 0.67, 0.55, 1.0), "roughness": 0.52},
    "paint_blue": {"color": (0.08, 0.24, 0.38, 1.0), "roughness": 0.46},
    "paint_green": {"color": (0.12, 0.34, 0.24, 1.0), "roughness": 0.5},
    "paint_red": {"color": (0.48, 0.09, 0.055, 1.0), "roughness": 0.48},
    "fabric": {"color": (0.16, 0.27, 0.34, 1.0), "roughness": 0.78},
    "ceramic": {"color": (0.77, 0.74, 0.67, 1.0), "roughness": 0.26},
    "glass": {
        "color": (0.36, 0.62, 0.70, 0.32),
        "roughness": 0.12,
        "metallic": 0.0,
        "transmission": 0.72,
    },
    "screen": {
        "color": (0.018, 0.035, 0.055, 1.0),
        "roughness": 0.18,
        "metallic": 0.15,
    },
    "leaf": {"color": (0.055, 0.31, 0.12, 1.0), "roughness": 0.72},
    "leaf_light": {"color": (0.13, 0.47, 0.16, 1.0), "roughness": 0.7},
    "soil": {"color": (0.09, 0.035, 0.012, 1.0), "roughness": 0.95},
    "paper": {"color": (0.82, 0.77, 0.64, 1.0), "roughness": 0.75},
    "paper_blue": {"color": (0.10, 0.28, 0.46, 1.0), "roughness": 0.66},
    "paper_red": {"color": (0.55, 0.11, 0.07, 1.0), "roughness": 0.68},
    "black": {"color": (0.012, 0.016, 0.022, 1.0), "roughness": 0.42},
}


def palette_material(key: str) -> bpy.types.Material:
    definition = PALETTE.get(key)
    if definition is None:
        raise NeuralStockError(f"unknown Room Zero material {key!r}")
    name = f"MAT_{key.upper()}"
    existing = bpy.data.materials.get(name)
    if existing is not None:
        return existing

    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = definition["color"]
    principled = next(
        (node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"),
        None,
    )
    if principled is not None:
        principled.inputs["Base Color"].default_value = definition["color"]
        principled.inputs["Roughness"].default_value = definition.get("roughness", 0.5)
        principled.inputs["Metallic"].default_value = definition.get("metallic", 0.0)
        transmission = principled.inputs.get("Transmission Weight") or principled.inputs.get(
            "Transmission"
        )
        if transmission is not None:
            transmission.default_value = definition.get("transmission", 0.0)
    material["neuralstock_palette_key"] = key
    return material


class MeshBuilder:
    """Assemble disconnected low-poly parts into one editable material mesh."""

    def __init__(self) -> None:
        self.vertices: list[tuple[float, float, float]] = []
        self.faces: list[tuple[int, ...]] = []
        self.face_materials: list[int] = []
        self.material_keys: list[str] = []

    def _material_index(self, material: str) -> int:
        if material not in self.material_keys:
            self.material_keys.append(material)
        return self.material_keys.index(material)

    def _add_part(
        self,
        vertices: list[tuple[float, float, float]],
        faces: list[tuple[int, ...]],
        material: str,
    ) -> None:
        offset = len(self.vertices)
        self.vertices.extend(vertices)
        self.faces.extend(tuple(offset + index for index in face) for face in faces)
        self.face_materials.extend([self._material_index(material)] * len(faces))

    def add_box(
        self,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
        material: str,
        *,
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        if any(component <= 0 for component in size):
            raise NeuralStockError("box dimensions must be positive")
        sx, sy, sz = (component * 0.5 for component in size)
        local = [
            Vector((-sx, -sy, -sz)),
            Vector((sx, -sy, -sz)),
            Vector((sx, sy, -sz)),
            Vector((-sx, sy, -sz)),
            Vector((-sx, -sy, sz)),
            Vector((sx, -sy, sz)),
            Vector((sx, sy, sz)),
            Vector((-sx, sy, sz)),
        ]
        orientation = Euler(rotation, "XYZ")
        translation = Vector(center)
        vertices = [tuple(orientation.to_matrix() @ point + translation) for point in local]
        faces = [
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ]
        self._add_part(vertices, faces, material)

    def add_cylinder(
        self,
        center: tuple[float, float, float],
        radius: float,
        depth: float,
        material: str,
        *,
        segments: int = 12,
        axis: str = "Z",
    ) -> None:
        self.add_tapered_cylinder(
            center,
            bottom_radius=radius,
            top_radius=radius,
            depth=depth,
            material=material,
            segments=segments,
            axis=axis,
        )

    def add_tapered_cylinder(
        self,
        center: tuple[float, float, float],
        bottom_radius: float,
        top_radius: float,
        depth: float,
        material: str,
        *,
        segments: int = 12,
        axis: str = "Z",
    ) -> None:
        if min(bottom_radius, top_radius, depth) <= 0 or not 3 <= segments <= 64:
            raise NeuralStockError("invalid tapered cylinder dimensions or segment count")
        axis = axis.upper()
        if axis not in {"X", "Y", "Z"}:
            raise NeuralStockError("cylinder axis must be X, Y, or Z")
        cx, cy, cz = center
        half = depth * 0.5

        def point(longitudinal: float, radial_a: float, radial_b: float) -> tuple[float, ...]:
            if axis == "X":
                return (cx + longitudinal, cy + radial_a, cz + radial_b)
            if axis == "Y":
                return (cx + radial_a, cy + longitudinal, cz + radial_b)
            return (cx + radial_a, cy + radial_b, cz + longitudinal)

        vertices: list[tuple[float, float, float]] = []
        for longitudinal, radius in ((-half, bottom_radius), (half, top_radius)):
            for index in range(segments):
                angle = 2.0 * math.pi * index / segments
                vertices.append(
                    point(longitudinal, radius * math.cos(angle), radius * math.sin(angle))
                )
        faces: list[tuple[int, ...]] = [
            tuple(reversed(range(segments))),
            tuple(range(segments, segments * 2)),
        ]
        for index in range(segments):
            following = (index + 1) % segments
            faces.append((index, following, segments + following, segments + index))
        self._add_part(vertices, faces, material)

    def add_ellipsoid(
        self,
        center: tuple[float, float, float],
        radii: tuple[float, float, float],
        material: str,
        *,
        segments: int = 12,
        rings: int = 5,
    ) -> None:
        if min(radii) <= 0 or segments < 6 or rings < 2:
            raise NeuralStockError("invalid ellipsoid dimensions")
        cx, cy, cz = center
        rx, ry, rz = radii
        vertices: list[tuple[float, float, float]] = [(cx, cy, cz + rz)]
        for ring in range(1, rings):
            latitude = math.pi * ring / rings
            for segment in range(segments):
                longitude = 2.0 * math.pi * segment / segments
                vertices.append(
                    (
                        cx + rx * math.sin(latitude) * math.cos(longitude),
                        cy + ry * math.sin(latitude) * math.sin(longitude),
                        cz + rz * math.cos(latitude),
                    )
                )
        bottom_index = len(vertices)
        vertices.append((cx, cy, cz - rz))
        faces: list[tuple[int, ...]] = []
        for segment in range(segments):
            following = (segment + 1) % segments
            faces.append((0, 1 + segment, 1 + following))
        for ring in range(rings - 2):
            first = 1 + ring * segments
            following_ring = first + segments
            for segment in range(segments):
                following = (segment + 1) % segments
                faces.append(
                    (
                        first + segment,
                        following_ring + segment,
                        following_ring + following,
                        first + following,
                    )
                )
        last_ring = 1 + (rings - 2) * segments
        for segment in range(segments):
            following = (segment + 1) % segments
            faces.append((last_ring + following, last_ring + segment, bottom_index))
        self._add_part(vertices, faces, material)

    def build_mesh(self, name: str) -> bpy.types.Mesh:
        if not self.vertices or not self.faces:
            raise NeuralStockError(f"mesh builder {name!r} is empty")
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update(calc_edges=True)
        for polygon, material_index in zip(mesh.polygons, self.face_materials, strict=True):
            polygon.material_index = material_index
        return mesh


@dataclass
class AssetContext:
    asset_id: str
    version: str
    asset_collection: bpy.types.Collection
    collision_collection: bpy.types.Collection
    root: bpy.types.Object

    def add_visual(
        self,
        name: str,
        builder: MeshBuilder,
        *,
        bevel_m: float = 0.0,
    ) -> bpy.types.Object:
        mesh = builder.build_mesh(f"{name}_mesh")
        obj = bpy.data.objects.new(name, mesh)
        obj.parent = self.root
        obj["neuralstock_role"] = "visual"
        obj["neuralstock_generator"] = self.asset_id
        self.asset_collection.objects.link(obj)
        for key in builder.material_keys:
            mesh.materials.append(palette_material(key))
        if bevel_m > 0:
            modifier = obj.modifiers.new("NS_Bevel", "BEVEL")
            modifier.width = bevel_m
            modifier.segments = 2
            modifier.limit_method = "ANGLE"
        return obj

    def add_anchor(
        self,
        suffix: str,
        position: tuple[float, float, float],
        semantic: str,
        *,
        normalized: bool = False,
    ) -> bpy.types.Object:
        name = f"{ANCHOR_PREFIX}{suffix}"
        anchor = bpy.data.objects.new(name, None)
        anchor.empty_display_type = "ARROWS"
        anchor.empty_display_size = 0.06
        anchor.parent = self.root
        anchor.location = position
        anchor["neuralstock_anchor_role"] = semantic
        if normalized:
            anchor["neuralstock_normalized_position_json"] = json.dumps(list(position))
        self.asset_collection.objects.link(anchor)
        return anchor

    def add_box_collision(
        self,
        suffix: str,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
        *,
        normalized: bool = False,
    ) -> bpy.types.Object:
        name = f"COLLISION_{suffix}"
        builder = MeshBuilder()
        if normalized:
            builder.add_box((0.0, 0.0, 0.0), (1.0, 1.0, 1.0), "black")
        else:
            builder.add_box(center, size, "black")
        mesh = builder.build_mesh(f"{name}_mesh")
        collision = bpy.data.objects.new(name, mesh)
        collision.display_type = "WIRE"
        collision.hide_render = True
        collision["neuralstock_collision"] = True
        collision["neuralstock_collision_shape"] = "box"
        if normalized:
            collision["neuralstock_normalized_position_json"] = json.dumps(list(center))
            collision["neuralstock_normalized_size_json"] = json.dumps(list(size))
        self.collision_collection.objects.link(collision)
        return collision

    def finish_static(self, overrides: Mapping[str, Any] | None = None) -> None:
        _set_scene_metadata(self.asset_id, self.version, node_group=None)
        store_parameter_schema({})
        apply_parameter_overrides(overrides)

    def finish_parametric(
        self,
        primary: bpy.types.Object,
        *,
        node_group: str,
        parameters: Mapping[str, Mapping[str, Any]],
        dimensions: tuple[str, str, str],
        bevel_m: float = 0.0,
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        definitions = json.loads(json.dumps(parameters))
        bindings = _add_dimension_controller(
            primary,
            node_group=node_group,
            definitions=definitions,
            dimensions=dimensions,
        )
        for name, identifier in bindings.items():
            definitions[name]["binding"] = {
                "kind": "geometry_nodes",
                "object": primary.name,
                "modifier": "NS_Geometry",
                "node_group": node_group,
                "socket_identifier": identifier,
            }
        if bevel_m > 0:
            modifier = primary.modifiers.new("NS_Bevel", "BEVEL")
            modifier.width = bevel_m
            modifier.segments = 2
            modifier.limit_method = "ANGLE"

        _set_scene_metadata(self.asset_id, self.version, node_group=node_group)
        bpy.context.scene["neuralstock_dimension_parameters_json"] = json.dumps(dimensions)
        store_parameter_schema(definitions)
        apply_parameter_overrides(overrides)


def begin_asset(asset_id: str, version: str) -> AssetContext:
    reset_scene()
    scene = bpy.context.scene
    # A future batch runner may build several assets in one Blender process. Clear
    # generator metadata explicitly so static assets cannot inherit declarations
    # or identity fields from the asset built immediately before them.
    for key in list(scene.keys()):
        if key.startswith("neuralstock_"):
            del scene[key]
    set_deterministic_scene_defaults(scene)
    asset_collection = get_or_create_collection(ASSET_COLLECTION)
    collision_collection = get_or_create_collection(COLLISION_COLLECTION)
    root = bpy.data.objects.new("ASSET_ROOT", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.08
    root["neuralstock_role"] = "asset_root"
    asset_collection.objects.link(root)
    return AssetContext(asset_id, version, asset_collection, collision_collection, root)


def float_parameter(
    label: str,
    default: float,
    minimum: float,
    maximum: float,
    description: str,
    *,
    unit: str = "meter",
) -> dict[str, Any]:
    return {
        "type": "float",
        "label": label,
        "description": description,
        "default": default,
        "minimum": minimum,
        "maximum": maximum,
        "unit": unit,
        "agent_safe": True,
    }


def _set_scene_metadata(asset_id: str, version: str, node_group: str | None) -> None:
    scene = bpy.context.scene
    scene["neuralstock_asset_id"] = asset_id
    scene["neuralstock_asset_version"] = version
    scene["neuralstock_target_profile"] = "web-v1"
    scene["neuralstock_origin_policy"] = "ground-center-of-evaluated-bounds"
    scene["neuralstock_generator_version"] = "1"
    if node_group is not None:
        scene["neuralstock_geometry_node_group"] = node_group


def _add_dimension_controller(
    obj: bpy.types.Object,
    *,
    node_group: str,
    definitions: Mapping[str, Mapping[str, Any]],
    dimensions: tuple[str, str, str],
) -> dict[str, str]:
    group = bpy.data.node_groups.new(node_group, "GeometryNodeTree")
    group.color_tag = "GEOMETRY"
    group.description = f"Agent-safe dimensions for {bpy.context.scene.name}."
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    sockets: dict[str, Any] = {}
    for name in dict.fromkeys(dimensions):
        definition = definitions.get(name)
        if definition is None or definition.get("type") != "float":
            raise NeuralStockError(f"dimension parameter {name!r} must be a declared float")
        socket = group.interface.new_socket(
            name=name, in_out="INPUT", socket_type="NodeSocketFloat"
        )
        socket.default_value = definition["default"]
        socket.min_value = definition["minimum"]
        socket.max_value = definition["maximum"]
        socket.description = definition.get("description", "")
        socket.subtype = "DISTANCE"
        sockets[name] = socket

    group_input = group.nodes.new("NodeGroupInput")
    group_input.name = "Declared Inputs"
    group_input.location = (-400, 0)
    combine = group.nodes.new("ShaderNodeCombineXYZ")
    combine.name = "Dimensions"
    combine.location = (-170, -160)
    transform = group.nodes.new("GeometryNodeTransform")
    transform.name = "Apply Dimensions"
    transform.location = (20, 0)
    group_output = group.nodes.new("NodeGroupOutput")
    group_output.name = "Generated Geometry"
    group_output.location = (260, 0)
    group.links.new(group_input.outputs["Geometry"], transform.inputs["Geometry"])
    for axis, name in zip(("X", "Y", "Z"), dimensions, strict=True):
        group.links.new(group_input.outputs[name], combine.inputs[axis])
    group.links.new(combine.outputs["Vector"], transform.inputs["Scale"])
    group.links.new(transform.outputs["Geometry"], group_output.inputs["Geometry"])

    modifier = obj.modifiers.new("NS_Geometry", "NODES")
    modifier.node_group = group
    bindings: dict[str, str] = {}
    for name, socket in sockets.items():
        modifier[socket.identifier] = definitions[name]["default"]
        bindings[name] = socket.identifier
    return bindings


def _apply_binding(name: str, definition: Mapping[str, Any], value: Any) -> None:
    binding = definition.get("binding")
    if not isinstance(binding, Mapping):
        raise NeuralStockError(f"parameter {name!r} has no repository-owned binding")
    obj = bpy.data.objects.get(str(binding.get("object", "")))
    if obj is None:
        raise NeuralStockError(f"parameter {name!r} references a missing object")
    modifier = obj.modifiers.get(str(binding.get("modifier", "")))
    if modifier is None:
        raise NeuralStockError(f"parameter {name!r} references a missing modifier")
    kind = binding.get("kind")
    if kind == "geometry_nodes":
        identifier = str(binding.get("socket_identifier", ""))
        if not identifier:
            raise NeuralStockError(f"parameter {name!r} has no socket identifier")
        modifier[identifier] = value
    elif kind == "modifier_property":
        property_name = str(binding.get("property", ""))
        if not property_name or not hasattr(modifier, property_name):
            raise NeuralStockError(f"parameter {name!r} has an invalid modifier property")
        setattr(modifier, property_name, value)
    else:
        raise NeuralStockError(f"parameter {name!r} has unsupported binding {kind!r}")


def _update_normalized_dependents(values: Mapping[str, Any]) -> None:
    raw_dimensions = bpy.context.scene.get("neuralstock_dimension_parameters_json")
    if not raw_dimensions:
        return
    try:
        parameter_names = json.loads(raw_dimensions)
        dimensions = [float(values[name]) for name in parameter_names]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise NeuralStockError("invalid embedded dimension parameter mapping") from exc

    for obj in bpy.data.objects:
        raw_position = obj.get("neuralstock_normalized_position_json")
        if raw_position:
            normalized_position = json.loads(raw_position)
            obj.location = tuple(
                normalized_position[index] * dimensions[index] for index in range(3)
            )
        raw_size = obj.get("neuralstock_normalized_size_json")
        if raw_size:
            normalized_size = json.loads(raw_size)
            obj.scale = tuple(normalized_size[index] * dimensions[index] for index in range(3))


def apply_parameter_overrides(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    definitions = load_parameter_schema()
    supplied = dict(overrides or {})
    unknown = sorted(set(supplied) - set(definitions))
    if unknown:
        raise NeuralStockError(f"undeclared parameters are not allowed: {', '.join(unknown)}")
    values: dict[str, Any] = {}
    for name in sorted(definitions):
        definition = definitions[name]
        if not isinstance(definition, Mapping):
            raise NeuralStockError(f"parameter declaration {name!r} is invalid")
        if not bool(definition.get("agent_safe", False)) and name in supplied:
            raise NeuralStockError(f"parameter {name!r} is not agent-safe")
        raw_value = supplied[name] if name in supplied else definition.get("default")
        value = validate_parameter_value(name, definition, raw_value)
        _apply_binding(name, definition, value)
        values[name] = value
    _update_normalized_dependents(values)
    store_parameter_values(values)
    bpy.context.view_layer.update()
    return stable_json_value(values)
