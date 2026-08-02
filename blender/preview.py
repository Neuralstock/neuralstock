"""Deterministic thumbnail rendering for NeuralStock assets."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector
from ns_common import (
    PREVIEW_COLLECTION,
    NeuralStockError,
    bounds_for_objects,
    get_or_create_collection,
    visual_mesh_objects,
)
from png_normalize import normalize_png


def _remove_preview_collection() -> None:
    collection = bpy.data.collections.get(PREVIEW_COLLECTION)
    if collection is None:
        return
    for obj in list(collection.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(collection)


def _available_render_engines() -> set[str]:
    try:
        items = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
        return {item.identifier for item in items}
    except (AttributeError, KeyError):
        return set()


def _aim_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def _add_area_light(
    collection: bpy.types.Collection,
    *,
    name: str,
    position: Vector,
    target: Vector,
    energy: float,
    size: float,
) -> None:
    light_data = bpy.data.lights.new(name, "AREA")
    light_data.energy = energy
    light_data.shape = "DISK"
    light_data.size = size
    light = bpy.data.objects.new(name, light_data)
    light.location = position
    _aim_at(light, target)
    collection.objects.link(light)


def _configure_renderer(
    scene: bpy.types.Scene,
    preview_collection: bpy.types.Collection,
    center: Vector,
    radius: float,
) -> None:
    engines = _available_render_engines()
    if "BLENDER_WORKBENCH" in engines:
        scene.render.engine = "BLENDER_WORKBENCH"
        shading = scene.display.shading
        shading.light = "STUDIO"
        shading.color_type = "MATERIAL"
        shading.show_shadows = True
        shading.show_cavity = True
        shading.cavity_type = "WORLD"
        shading.curvature_ridge_factor = 1.5
        shading.curvature_valley_factor = 1.0
        shading.show_specular_highlight = True
        shading.show_object_outline = True
        shading.background_type = "WORLD"
        return

    if "BLENDER_EEVEE_NEXT" not in engines:
        raise NeuralStockError("neither Workbench nor EEVEE Next is available")
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    # A fixed, modest sample count keeps CI previews deterministic and bounded.
    # The pilot thumbnail is an inspection aid, not a production beauty render.
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 16
        scene.eevee.taa_samples = 16
    world = scene.world or bpy.data.worlds.new("NEURALSTOCK_PREVIEW_WORLD")
    scene.world = world
    world.use_nodes = True
    background = next(
        (node for node in world.node_tree.nodes if node.type == "BACKGROUND"),
        None,
    )
    if background is not None:
        background.inputs["Color"].default_value = (0.035, 0.045, 0.065, 1.0)
        background.inputs["Strength"].default_value = 0.45

    scale = max(radius, 0.25)
    _add_area_light(
        preview_collection,
        name="NEURALSTOCK_KEY_LIGHT",
        position=center + Vector((2.5, -3.0, 3.5)) * scale,
        target=center,
        energy=900.0 * scale * scale,
        size=2.5 * scale,
    )
    _add_area_light(
        preview_collection,
        name="NEURALSTOCK_FILL_LIGHT",
        position=center + Vector((-3.0, -1.0, 1.8)) * scale,
        target=center,
        energy=500.0 * scale * scale,
        size=3.0 * scale,
    )
    _add_area_light(
        preview_collection,
        name="NEURALSTOCK_RIM_LIGHT",
        position=center + Vector((1.0, 3.0, 2.5)) * scale,
        target=center,
        energy=650.0 * scale * scale,
        size=2.0 * scale,
    )


def render_preview(
    path: str | os.PathLike[str],
    *,
    resolution: int = 512,
    margin: float = 1.20,
) -> dict[str, Any]:
    if resolution < 64 or resolution > 2048:
        raise NeuralStockError("preview resolution must be between 64 and 2048 pixels")
    if margin < 1.0 or margin > 3.0 or not math.isfinite(margin):
        raise NeuralStockError("preview margin must be finite and between 1.0 and 3.0")

    destination = Path(path).resolve()
    if destination.suffix.lower() != ".png":
        raise NeuralStockError("preview output path must end in .png")
    destination.parent.mkdir(parents=True, exist_ok=True)

    objects = visual_mesh_objects()
    bounds = bounds_for_objects(objects)
    minimum = Vector(bounds["minimum"])
    maximum = Vector(bounds["maximum"])
    center = (minimum + maximum) * 0.5
    dimensions = maximum - minimum
    radius = max(dimensions.length * 0.5, 0.05)

    _remove_preview_collection()
    preview_collection = get_or_create_collection(PREVIEW_COLLECTION)
    camera_data = bpy.data.cameras.new("NEURALSTOCK_PREVIEW_CAMERA")
    camera = bpy.data.objects.new("NEURALSTOCK_PREVIEW_CAMERA", camera_data)
    preview_collection.objects.link(camera)

    camera_data.type = "PERSP"
    camera_data.lens = 58.0
    camera_data.sensor_width = 36.0
    camera_data.clip_start = max(0.001, radius / 1000.0)
    camera_data.clip_end = max(100.0, radius * 100.0)

    direction = Vector((1.35, -1.65, 1.10)).normalized()
    half_fov = max(camera_data.angle_y * 0.5, math.radians(5.0))
    distance = margin * radius / math.sin(half_fov)
    camera.location = center + direction * distance
    _aim_at(camera, center)

    scene = bpy.context.scene
    scene.camera = camera
    _configure_renderer(scene, preview_collection, center, radius)
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 1.0
    scene.render.pixel_aspect_y = 1.0
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 100
    scene.render.filepath = str(destination)
    scene.render.use_file_extension = True

    bpy.ops.render.render(write_still=True)
    if not destination.is_file() or destination.stat().st_size == 0:
        raise NeuralStockError("Blender did not produce a non-empty preview PNG")
    normalize_png(destination)

    return {
        "camera_position_m": list(camera.location),
        "target_position_m": list(center),
        "resolution_px": [resolution, resolution],
        "margin": margin,
        "render_engine": scene.render.engine,
    }
