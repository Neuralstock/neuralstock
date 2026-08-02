"""Parametric architectural pieces for the Room Zero starter collection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from asset_builder import MeshBuilder, begin_asset, float_parameter


def generate_floor_panel(version: str, overrides: Mapping[str, Any]) -> None:
    context = begin_asset("room_floor_panel_01", version)
    mesh = MeshBuilder()
    mesh.add_box((0.0, 0.0, 0.06), (1.0, 1.0, 0.12), "wood_dark")
    plank_width = 0.19
    for index in range(5):
        x = -0.4 + index * 0.2
        mesh.add_box((x, 0.0, 0.56), (plank_width, 1.0, 0.88), "wood_light")
    body = context.add_visual("floor_panel", mesh)
    context.add_anchor("top_surface", (0.0, 0.0, 1.0), "top-surface", normalized=True)
    context.add_box_collision("panel", (0.0, 0.0, 0.5), (1.0, 1.0, 1.0), normalized=True)
    context.finish_parametric(
        body,
        node_group="FloorPanelGenerator",
        parameters={
            "width_m": float_parameter(
                "Width", 2.0, 0.25, 8.0, "Panel width along the local X axis."
            ),
            "depth_m": float_parameter(
                "Depth", 2.0, 0.25, 8.0, "Panel depth along the local Y axis."
            ),
            "thickness_m": float_parameter(
                "Thickness", 0.12, 0.03, 0.5, "Finished panel thickness."
            ),
        },
        dimensions=("width_m", "depth_m", "thickness_m"),
        bevel_m=0.003,
        overrides=overrides,
    )


def generate_wall_panel(version: str, overrides: Mapping[str, Any]) -> None:
    context = begin_asset("room_wall_panel_01", version)
    mesh = MeshBuilder()
    mesh.add_box((0.0, 0.0, 0.50), (0.90, 0.42, 0.88), "paint_cream")
    mesh.add_box((-0.47, 0.0, 0.50), (0.06, 1.0, 1.0), "wood_dark")
    mesh.add_box((0.47, 0.0, 0.50), (0.06, 1.0, 1.0), "wood_dark")
    mesh.add_box((0.0, 0.0, 0.04), (0.88, 1.0, 0.08), "wood_dark")
    mesh.add_box((0.0, 0.0, 0.96), (0.88, 1.0, 0.08), "wood_dark")
    mesh.add_box((0.0, 0.0, 0.50), (0.025, 0.55, 0.82), "wood_light")
    body = context.add_visual("wall_panel", mesh)
    context.add_anchor("front_center", (0.0, -0.5, 0.5), "front-surface", normalized=True)
    context.add_anchor("top_center", (0.0, 0.0, 1.0), "top-surface", normalized=True)
    context.add_box_collision("panel", (0.0, 0.0, 0.5), (1.0, 1.0, 1.0), normalized=True)
    context.finish_parametric(
        body,
        node_group="WallPanelGenerator",
        parameters={
            "width_m": float_parameter(
                "Width", 3.0, 0.4, 12.0, "Wall module width along the local X axis."
            ),
            "thickness_m": float_parameter(
                "Thickness", 0.14, 0.06, 0.6, "Wall module depth along local Y."
            ),
            "height_m": float_parameter("Height", 2.5, 0.5, 6.0, "Wall module height."),
        },
        dimensions=("width_m", "thickness_m", "height_m"),
        bevel_m=0.003,
        overrides=overrides,
    )


def generate_door(version: str, overrides: Mapping[str, Any]) -> None:
    context = begin_asset("room_door_01", version)
    mesh = MeshBuilder()
    # Door leaf, inset panels, and a full-height frame form a readable closed door.
    mesh.add_box((0.0, 0.04, 0.48), (0.78, 0.34, 0.86), "wood_light")
    mesh.add_box((0.0, -0.15, 0.67), (0.61, 0.07, 0.27), "wood")
    mesh.add_box((0.0, -0.15, 0.28), (0.61, 0.07, 0.30), "wood")
    mesh.add_box((-0.46, 0.0, 0.50), (0.08, 1.0, 1.0), "wood_dark")
    mesh.add_box((0.46, 0.0, 0.50), (0.08, 1.0, 1.0), "wood_dark")
    mesh.add_box((0.0, 0.0, 0.96), (0.84, 1.0, 0.08), "wood_dark")
    mesh.add_box((0.0, 0.0, 0.025), (0.84, 0.75, 0.05), "wood_dark")
    mesh.add_cylinder((0.27, -0.42, 0.50), 0.035, 0.16, "metal_light", axis="Y")
    body = context.add_visual("door_and_frame", mesh)
    context.add_anchor("handle", (0.27, -0.5, 0.50), "handle", normalized=True)
    context.add_anchor("hinge", (-0.39, 0.0, 0.50), "hinge", normalized=True)
    context.add_box_collision("closed_door", (0.0, 0.0, 0.5), (1.0, 1.0, 1.0), normalized=True)
    context.finish_parametric(
        body,
        node_group="DoorGenerator",
        parameters={
            "width_m": float_parameter("Width", 0.95, 0.55, 2.2, "Outer frame width."),
            "thickness_m": float_parameter("Thickness", 0.14, 0.06, 0.5, "Outer frame depth."),
            "height_m": float_parameter("Height", 2.10, 1.2, 4.0, "Outer frame height."),
        },
        dimensions=("width_m", "thickness_m", "height_m"),
        bevel_m=0.004,
        overrides=overrides,
    )


def generate_window(version: str, overrides: Mapping[str, Any]) -> None:
    context = begin_asset("room_window_01", version)
    mesh = MeshBuilder()
    mesh.add_box((0.0, 0.08, 0.50), (0.76, 0.15, 0.76), "glass")
    mesh.add_box((-0.46, 0.0, 0.50), (0.08, 1.0, 1.0), "wood_dark")
    mesh.add_box((0.46, 0.0, 0.50), (0.08, 1.0, 1.0), "wood_dark")
    mesh.add_box((0.0, 0.0, 0.04), (0.84, 1.0, 0.08), "wood_dark")
    mesh.add_box((0.0, 0.0, 0.96), (0.84, 1.0, 0.08), "wood_dark")
    mesh.add_box((0.0, -0.10, 0.50), (0.045, 0.25, 0.78), "metal_light")
    mesh.add_box((0.0, -0.10, 0.50), (0.78, 0.25, 0.045), "metal_light")
    body = context.add_visual("window_and_frame", mesh)
    context.add_anchor("opening_center", (0.0, -0.5, 0.5), "opening-center", normalized=True)
    context.add_box_collision("window", (0.0, 0.0, 0.5), (1.0, 1.0, 1.0), normalized=True)
    context.finish_parametric(
        body,
        node_group="WindowGenerator",
        parameters={
            "width_m": float_parameter("Width", 1.20, 0.4, 4.0, "Outer window frame width."),
            "thickness_m": float_parameter(
                "Thickness", 0.12, 0.04, 0.5, "Outer window frame depth."
            ),
            "height_m": float_parameter("Height", 1.05, 0.4, 3.0, "Outer window frame height."),
        },
        dimensions=("width_m", "thickness_m", "height_m"),
        bevel_m=0.003,
        overrides=overrides,
    )


GENERATORS = {
    "room_floor_panel_01": generate_floor_panel,
    "room_wall_panel_01": generate_wall_panel,
    "room_door_01": generate_door,
    "room_window_01": generate_window,
}
