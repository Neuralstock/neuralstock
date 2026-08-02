"""Repository-owned furniture generators for the Room Zero collection."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

from asset_builder import AssetContext, MeshBuilder, begin_asset, float_parameter

Generator = Callable[[str, Mapping[str, Any]], None]


TABLE_PARAMETERS: dict[str, dict[str, Any]] = {
    "length_m": float_parameter(
        "Length",
        1.80,
        0.80,
        4.00,
        "Overall table length in meters.",
    ),
    "width_m": float_parameter(
        "Width",
        0.90,
        0.50,
        2.00,
        "Overall table width in meters.",
    ),
    "height_m": float_parameter(
        "Height",
        0.76,
        0.55,
        1.20,
        "Overall table height in meters.",
    ),
}


SHELF_PARAMETERS: dict[str, dict[str, Any]] = {
    "width_m": float_parameter(
        "Width",
        0.90,
        0.45,
        2.40,
        "Overall shelving-unit width in meters.",
    ),
    "depth_m": float_parameter(
        "Depth",
        0.35,
        0.20,
        0.80,
        "Overall shelving-unit depth in meters.",
    ),
    "height_m": float_parameter(
        "Height",
        1.80,
        0.70,
        3.00,
        "Overall shelving-unit height in meters.",
    ),
}


def _add_table_collisions(context: AssetContext) -> None:
    context.add_box_collision(
        "top",
        (0.0, 0.0, 0.95),
        (1.0, 1.0, 0.10),
        normalized=True,
    )
    for x_name, x_position in (("left", -0.44), ("right", 0.44)):
        for y_name, y_position in (("front", -0.42), ("back", 0.42)):
            context.add_box_collision(
                f"leg_{y_name}_{x_name}",
                (x_position, y_position, 0.40),
                (0.09, 0.09, 0.80),
                normalized=True,
            )


def generate_procedural_table_01(
    version: str,
    overrides: Mapping[str, Any],
) -> None:
    """Build a warm plank-top table with tapered legs and a dark underframe."""

    context = begin_asset("procedural_table_01", version)
    builder = MeshBuilder()

    # Three separated planks keep the silhouette readable without textures while
    # preserving the exact normalized X/Y/Z bounds.
    for y_position, material in (
        (-0.34, "wood_light"),
        (0.0, "wood"),
        (0.34, "wood_light"),
    ):
        builder.add_box(
            (0.0, y_position, 0.95),
            (1.0, 0.32, 0.10),
            material,
        )

    # Recessed aprons make the table structurally legible from every angle.
    for y_position in (-0.425, 0.425):
        builder.add_box((0.0, y_position, 0.825), (0.84, 0.045, 0.15), "wood_dark")
    for x_position in (-0.445, 0.445):
        builder.add_box((x_position, 0.0, 0.825), (0.045, 0.80, 0.15), "wood_dark")

    for x_position in (-0.44, 0.44):
        for y_position in (-0.42, 0.42):
            builder.add_tapered_cylinder(
                (x_position, y_position, 0.40),
                bottom_radius=0.032,
                top_radius=0.045,
                depth=0.80,
                material="wood_dark",
                segments=8,
            )

    # A centered stretcher gives the stylized table a strong side silhouette.
    builder.add_box((0.0, 0.0, 0.37), (0.78, 0.045, 0.055), "metal")
    table = context.add_visual("table_body", builder)

    context.add_anchor(
        "top_surface",
        (0.0, 0.0, 1.0),
        "support-surface",
        normalized=True,
    )
    context.add_anchor(
        "front_center",
        (0.0, -0.5, 0.95),
        "approach-point",
        normalized=True,
    )
    _add_table_collisions(context)
    context.finish_parametric(
        table,
        node_group="TableGenerator",
        parameters=TABLE_PARAMETERS,
        dimensions=("length_m", "width_m", "height_m"),
        bevel_m=0.006,
        overrides=overrides,
    )


def generate_chair_01(version: str, overrides: Mapping[str, Any]) -> None:
    """Build a compact dining chair with an octagonal timber frame."""

    context = begin_asset("chair_01", version)
    builder = MeshBuilder()

    builder.add_box((0.0, -0.015, 0.465), (0.48, 0.49, 0.065), "wood_light")
    builder.add_box((0.0, -0.225, 0.405), (0.42, 0.04, 0.11), "wood_dark")
    builder.add_box((0.0, 0.205, 0.405), (0.42, 0.04, 0.11), "wood_dark")
    for x_position in (-0.215, 0.215):
        builder.add_box((x_position, -0.01, 0.405), (0.04, 0.39, 0.11), "wood_dark")

    for x_position in (-0.205, 0.205):
        builder.add_tapered_cylinder(
            (x_position, -0.22, 0.21625),
            bottom_radius=0.018,
            top_radius=0.026,
            depth=0.4325,
            material="wood_dark",
            segments=8,
        )
        builder.add_tapered_cylinder(
            (x_position, 0.235, 0.44),
            bottom_radius=0.018,
            top_radius=0.025,
            depth=0.88,
            material="wood_dark",
            segments=8,
        )

    builder.add_box((0.0, 0.235, 0.655), (0.41, 0.05, 0.105), "wood_light")
    builder.add_box((0.0, 0.235, 0.805), (0.41, 0.05, 0.105), "wood_light")
    for x_position in (-0.205, 0.205):
        builder.add_cylinder(
            (x_position, 0.207, 0.655),
            radius=0.012,
            depth=0.014,
            material="metal",
            segments=8,
            axis="Y",
        )

    context.add_visual("chair_body", builder, bevel_m=0.005)
    context.add_anchor("seat_surface", (0.0, -0.015, 0.4975), "seat-surface")
    context.add_anchor("back_center", (0.0, 0.26, 0.73), "back-support")
    context.add_box_collision("seat", (0.0, -0.015, 0.465), (0.48, 0.49, 0.065))
    context.add_box_collision("back", (0.0, 0.235, 0.69), (0.46, 0.05, 0.38))
    context.finish_static(overrides)


def generate_stool_01(version: str, overrides: Mapping[str, Any]) -> None:
    """Build a round low-poly stool with four legs and a metal foot rail."""

    context = begin_asset("stool_01", version)
    builder = MeshBuilder()

    builder.add_cylinder(
        (0.0, 0.0, 0.475),
        radius=0.21,
        depth=0.05,
        material="wood_light",
        segments=16,
    )
    builder.add_cylinder(
        (0.0, 0.0, 0.447),
        radius=0.15,
        depth=0.025,
        material="wood_dark",
        segments=12,
    )
    for x_position in (-0.135, 0.135):
        for y_position in (-0.135, 0.135):
            builder.add_tapered_cylinder(
                (x_position, y_position, 0.225),
                bottom_radius=0.018,
                top_radius=0.025,
                depth=0.45,
                material="wood_dark",
                segments=8,
            )

    for y_position in (-0.135, 0.135):
        builder.add_box((0.0, y_position, 0.18), (0.27, 0.022, 0.022), "metal")
    for x_position in (-0.135, 0.135):
        builder.add_box((x_position, 0.0, 0.18), (0.022, 0.27, 0.022), "metal")

    context.add_visual("stool_body", builder, bevel_m=0.004)
    context.add_anchor("seat_surface", (0.0, 0.0, 0.50), "seat-surface")
    context.add_box_collision("seat", (0.0, 0.0, 0.475), (0.42, 0.42, 0.05))
    context.finish_static(overrides)


def _add_shelf_collisions(context: AssetContext) -> None:
    for name, center_z in (
        ("base", 0.0275),
        ("lower", 0.3425),
        ("middle", 0.6575),
        ("top", 0.9725),
    ):
        context.add_box_collision(
            f"shelf_{name}",
            (0.0, 0.0, center_z),
            (1.0, 1.0, 0.055),
            normalized=True,
        )


def generate_shelf_01(version: str, overrides: Mapping[str, Any]) -> None:
    """Build open timber shelves on an industrial metal frame."""

    context = begin_asset("shelf_01", version)
    builder = MeshBuilder()
    shelf_centers = (0.0275, 0.3425, 0.6575, 0.9725)
    shelf_materials = ("wood_dark", "wood_light", "wood", "wood_light")
    for center_z, material in zip(shelf_centers, shelf_materials, strict=True):
        builder.add_box((0.0, 0.0, center_z), (1.0, 1.0, 0.055), material)

    for x_position in (-0.47, 0.47):
        for y_position in (-0.46, 0.46):
            builder.add_box(
                (x_position, y_position, 0.50),
                (0.04, 0.04, 0.89),
                "metal",
            )

    brace_run = 0.86
    brace_rise = 0.84
    brace_length = math.hypot(brace_run, brace_rise)
    brace_angle = math.atan2(brace_run, brace_rise)
    for angle in (-brace_angle, brace_angle):
        builder.add_box(
            (0.0, 0.475, 0.50),
            (0.035, 0.025, brace_length),
            "metal_light",
            rotation=(0.0, angle, 0.0),
        )

    shelf = context.add_visual("shelf_body", builder)
    for name, surface_z in (
        ("base", 0.055),
        ("lower", 0.37),
        ("middle", 0.685),
        ("top", 1.0),
    ):
        context.add_anchor(
            f"shelf_{name}_surface",
            (0.0, 0.0, surface_z),
            "support-surface",
            normalized=True,
        )
    _add_shelf_collisions(context)
    context.finish_parametric(
        shelf,
        node_group="ShelfGenerator",
        parameters=SHELF_PARAMETERS,
        dimensions=("width_m", "depth_m", "height_m"),
        bevel_m=0.005,
        overrides=overrides,
    )


def generate_cabinet_01(version: str, overrides: Mapping[str, Any]) -> None:
    """Build a two-door painted cabinet with recessed fronts and metal feet."""

    context = begin_asset("cabinet_01", version)
    builder = MeshBuilder()

    builder.add_box((0.0, 0.0, 1.17), (0.90, 0.50, 0.06), "paint_cream")
    builder.add_box((0.0, 0.0, 0.14), (0.90, 0.50, 0.06), "paint_cream")
    for x_position in (-0.42, 0.42):
        builder.add_box((x_position, 0.0, 0.65), (0.06, 0.48, 0.98), "paint_cream")
    builder.add_box((0.0, 0.255, 0.65), (0.78, 0.03, 0.98), "wood_dark")
    builder.add_box((0.0, -0.225, 0.65), (0.04, 0.03, 0.94), "paint_cream")

    for x_position in (-0.205, 0.205):
        builder.add_box((x_position, -0.245, 0.65), (0.39, 0.05, 0.94), "paint_blue")
        builder.add_box(
            (x_position, -0.268, 0.90),
            (0.31, 0.004, 0.31),
            "paint_green",
        )
        builder.add_box(
            (x_position, -0.268, 0.40),
            (0.31, 0.004, 0.31),
            "paint_green",
        )

    for x_position in (-0.38, 0.38):
        for y_position in (-0.20, 0.20):
            builder.add_cylinder(
                (x_position, y_position, 0.05),
                radius=0.025,
                depth=0.10,
                material="metal",
                segments=8,
            )

    for x_position in (-0.055, 0.055):
        builder.add_box((x_position, -0.268, 0.65), (0.018, 0.004, 0.16), "metal")

    context.add_visual("cabinet_body", builder, bevel_m=0.004)
    context.add_anchor("top_surface", (0.0, 0.0, 1.20), "support-surface")
    context.add_anchor("door_pull_left", (-0.055, -0.27, 0.65), "interaction-point")
    context.add_anchor("door_pull_right", (0.055, -0.27, 0.65), "interaction-point")
    context.add_box_collision("body", (0.0, 0.0, 0.60), (0.90, 0.54, 1.20))
    context.finish_static(overrides)


GENERATORS: dict[str, Generator] = {
    "procedural_table_01": generate_procedural_table_01,
    "chair_01": generate_chair_01,
    "stool_01": generate_stool_01,
    "shelf_01": generate_shelf_01,
    "cabinet_01": generate_cabinet_01,
}
