"""Static, low-poly prop generators for the Room Zero collection."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

from asset_builder import AssetContext, MeshBuilder, begin_asset

Generator = Callable[[str, Mapping[str, Any]], None]


def _finish(
    context: AssetContext,
    builder: MeshBuilder,
    *,
    visual_name: str,
    overrides: Mapping[str, Any],
    bevel_m: float,
) -> None:
    """Create the single runtime visual and close a static asset definition."""

    _ground_center(context, builder)
    context.add_visual(visual_name, builder, bevel_m=bevel_m)
    context.finish_static(overrides)


def _ground_center(context: AssetContext, builder: MeshBuilder) -> None:
    """Center evaluated visual geometry on X/Y and place its minimum Z at zero."""

    minimum = tuple(min(vertex[axis] for vertex in builder.vertices) for axis in range(3))
    maximum = tuple(max(vertex[axis] for vertex in builder.vertices) for axis in range(3))
    shift = (
        -(minimum[0] + maximum[0]) * 0.5,
        -(minimum[1] + maximum[1]) * 0.5,
        -minimum[2],
    )
    builder.vertices = [
        (vertex[0] + shift[0], vertex[1] + shift[1], vertex[2] + shift[2])
        for vertex in builder.vertices
    ]

    # Anchors and collision geometry were authored in the same asset-local coordinates.
    for obj in context.asset_collection.objects:
        if obj.name.startswith("ANCHOR_"):
            obj.location = tuple(obj.location[axis] + shift[axis] for axis in range(3))
    for obj in context.collision_collection.objects:
        if obj.type == "MESH":
            for vertex in obj.data.vertices:
                for axis in range(3):
                    vertex.co[axis] += shift[axis]


def generate_monitor_01(version: str, overrides: Mapping[str, Any]) -> None:
    """Build a compact 24-inch desktop monitor with a weighted stand."""

    context = begin_asset("monitor_01", version)
    builder = MeshBuilder()

    # The front of Room Zero props faces -Y. The base touches Z=0 exactly.
    builder.add_box((0.0, 0.015, 0.014), (0.31, 0.18, 0.028), "metal")
    builder.add_box((0.0, 0.035, 0.105), (0.052, 0.050, 0.175), "metal")
    builder.add_cylinder((0.0, 0.006, 0.188), 0.037, 0.075, "metal_light", axis="X")

    # Housing, inset display, lower chin, and power indicator form a readable silhouette.
    builder.add_box((0.0, 0.0, 0.355), (0.59, 0.066, 0.34), "black")
    builder.add_box((0.0, -0.039, 0.362), (0.542, 0.014, 0.282), "screen")
    builder.add_box((0.0, -0.042, 0.204), (0.25, 0.010, 0.018), "metal")
    builder.add_box((0.258, -0.049, 0.205), (0.012, 0.005, 0.006), "paint_blue")

    context.add_anchor("screen_center", (0.0, -0.049, 0.362), "display-surface")
    context.add_anchor("base_center", (0.0, 0.0, 0.0), "support-origin")
    context.add_box_collision("body", (0.0, 0.0, 0.355), (0.59, 0.066, 0.34))
    context.add_box_collision("base", (0.0, 0.015, 0.014), (0.31, 0.18, 0.028))
    _finish(
        context,
        builder,
        visual_name="monitor",
        overrides=overrides,
        bevel_m=0.004,
    )


def generate_desk_lamp_01(version: str, overrides: Mapping[str, Any]) -> None:
    """Build a low-poly articulated task lamp with a broad conical shade."""

    context = begin_asset("desk_lamp_01", version)
    builder = MeshBuilder()

    builder.add_cylinder((0.0, 0.0, 0.025), 0.13, 0.05, "metal", segments=16)
    builder.add_cylinder((0.0, 0.0, 0.066), 0.035, 0.045, "metal_light", segments=12)

    # Two opposed arm angles communicate adjustability without a costly armature.
    builder.add_box(
        (0.0, 0.049, 0.207),
        (0.034, 0.044, 0.31),
        "metal",
        rotation=(-0.32, 0.0, 0.0),
    )
    builder.add_cylinder((0.0, 0.098, 0.354), 0.038, 0.074, "metal_light", axis="X")
    builder.add_box(
        (0.0, -0.002, 0.424),
        (0.034, 0.044, 0.245),
        "metal",
        rotation=(0.96, 0.0, 0.0),
    )
    builder.add_cylinder((0.0, -0.102, 0.494), 0.034, 0.074, "metal_light", axis="X")

    # Wide end points toward -Y, matching the collection's forward convention.
    builder.add_tapered_cylinder(
        (0.0, -0.162, 0.494),
        bottom_radius=0.11,
        top_radius=0.06,
        depth=0.145,
        material="paint_blue",
        segments=16,
        axis="Y",
    )
    builder.add_cylinder(
        (0.0, -0.238, 0.494),
        0.086,
        0.008,
        "paint_cream",
        segments=16,
        axis="Y",
    )

    context.add_anchor("light_origin", (0.0, -0.245, 0.494), "light-source")
    context.add_anchor("base_center", (0.0, 0.0, 0.0), "support-origin")
    context.add_box_collision("base", (0.0, 0.0, 0.025), (0.26, 0.26, 0.05))
    context.add_box_collision("shade", (0.0, -0.162, 0.494), (0.22, 0.16, 0.22))
    _finish(
        context,
        builder,
        visual_name="desk_lamp",
        overrides=overrides,
        bevel_m=0.002,
    )


def generate_potted_plant_01(version: str, overrides: Mapping[str, Any]) -> None:
    """Build a faceted ceramic pot with a layered broad-leaf plant."""

    context = begin_asset("potted_plant_01", version)
    builder = MeshBuilder()

    builder.add_tapered_cylinder(
        (0.0, 0.0, 0.15),
        bottom_radius=0.155,
        top_radius=0.205,
        depth=0.30,
        material="ceramic",
        segments=14,
    )
    builder.add_cylinder((0.0, 0.0, 0.302), 0.22, 0.045, "ceramic", segments=14)
    builder.add_cylinder((0.0, 0.0, 0.327), 0.19, 0.018, "soil", segments=14)

    # A central stem plus four angled branch segments support the foliage mass.
    builder.add_cylinder((0.0, 0.0, 0.555), 0.018, 0.44, "paint_green", segments=8)
    builder.add_box(
        (-0.073, 0.0, 0.535),
        (0.018, 0.018, 0.22),
        "paint_green",
        rotation=(0.0, -0.73, 0.0),
    )
    builder.add_box(
        (0.078, 0.012, 0.492),
        (0.018, 0.018, 0.21),
        "paint_green",
        rotation=(0.08, 0.82, 0.0),
    )
    builder.add_box(
        (0.0, -0.067, 0.555),
        (0.018, 0.018, 0.20),
        "paint_green",
        rotation=(-0.73, 0.0, 0.0),
    )
    builder.add_box(
        (0.0, 0.062, 0.455),
        (0.018, 0.018, 0.17),
        "paint_green",
        rotation=(0.82, 0.0, 0.0),
    )

    # Alternating axes and greens keep the plant legible from all viewpoints.
    builder.add_ellipsoid((0.0, 0.0, 0.745), (0.115, 0.055, 0.155), "leaf", rings=5)
    builder.add_ellipsoid((-0.16, 0.0, 0.625), (0.17, 0.052, 0.09), "leaf_light", rings=5)
    builder.add_ellipsoid((0.17, 0.025, 0.565), (0.17, 0.055, 0.09), "leaf", rings=5)
    builder.add_ellipsoid((0.0, -0.145, 0.635), (0.075, 0.16, 0.095), "leaf_light", rings=5)
    builder.add_ellipsoid((0.0, 0.13, 0.52), (0.07, 0.15, 0.09), "leaf", rings=5)

    context.add_anchor("soil_center", (0.0, 0.0, 0.338), "soil-surface")
    context.add_anchor("pot_base", (0.0, 0.0, 0.0), "support-origin")
    context.add_box_collision("pot", (0.0, 0.0, 0.165), (0.44, 0.44, 0.33))
    _finish(
        context,
        builder,
        visual_name="potted_plant",
        overrides=overrides,
        bevel_m=0.0,
    )


def generate_mug_01(version: str, overrides: Mapping[str, Any]) -> None:
    """Build a ground-centered coffee mug with a beveled square-loop handle."""

    context = begin_asset("mug_01", version)
    builder = MeshBuilder()

    # The cup is offset left so the complete handled silhouette remains centered on X=0.
    cup_x = -0.017
    builder.add_tapered_cylinder(
        (cup_x, 0.0, 0.048),
        bottom_radius=0.042,
        top_radius=0.048,
        depth=0.096,
        material="ceramic",
        segments=16,
    )
    builder.add_cylinder((cup_x, 0.0, 0.097), 0.049, 0.008, "ceramic", segments=16)
    builder.add_cylinder((cup_x, 0.0, 0.102), 0.039, 0.003, "wood_dark", segments=16)

    # Two round joins and a vertical grip create a clear open handle silhouette.
    builder.add_cylinder((0.037, 0.0, 0.078), 0.008, 0.042, "ceramic", axis="X")
    builder.add_cylinder((0.037, 0.0, 0.032), 0.008, 0.042, "ceramic", axis="X")
    builder.add_cylinder((0.058, 0.0, 0.055), 0.008, 0.046, "ceramic", axis="Z")

    context.add_anchor("drink_surface", (cup_x, 0.0, 0.104), "liquid-surface")
    context.add_anchor("grip_center", (0.058, 0.0, 0.055), "hand-grip")
    context.add_box_collision("body", (0.0, 0.0, 0.052), (0.13, 0.098, 0.104))
    _finish(context, builder, visual_name="mug", overrides=overrides, bevel_m=0.002)


def generate_book_stack_01(version: str, overrides: Mapping[str, Any]) -> None:
    """Build three individually bound books in a staggered tabletop stack."""

    context = begin_asset("book_stack_01", version)
    builder = MeshBuilder()

    def add_book(
        *,
        base_z: float,
        width: float,
        depth: float,
        page_height: float,
        rotation_z: float,
        cover_material: str,
    ) -> float:
        cover_height = 0.008
        page_width = width - 0.020
        page_depth = depth - 0.020
        builder.add_box(
            (0.0, 0.0, base_z + cover_height * 0.5),
            (width, depth, cover_height),
            cover_material,
            rotation=(0.0, 0.0, rotation_z),
        )
        builder.add_box(
            (0.0, 0.0, base_z + cover_height + page_height * 0.5),
            (page_width, page_depth, page_height),
            "paper",
            rotation=(0.0, 0.0, rotation_z),
        )
        top_z = base_z + cover_height + page_height
        builder.add_box(
            (0.0, 0.0, top_z + cover_height * 0.5),
            (width, depth, cover_height),
            cover_material,
            rotation=(0.0, 0.0, rotation_z),
        )
        return top_z + cover_height

    next_z = add_book(
        base_z=0.0,
        width=0.31,
        depth=0.215,
        page_height=0.034,
        rotation_z=math.radians(2.3),
        cover_material="paper_red",
    )
    next_z = add_book(
        base_z=next_z,
        width=0.27,
        depth=0.20,
        page_height=0.034,
        rotation_z=math.radians(-5.2),
        cover_material="paper_blue",
    )
    top_z = add_book(
        base_z=next_z,
        width=0.29,
        depth=0.17,
        page_height=0.042,
        rotation_z=math.radians(-8.0),
        cover_material="paint_green",
    )

    context.add_anchor("top_surface", (0.0, 0.0, top_z), "top-surface")
    context.add_anchor("stack_base", (0.0, 0.0, 0.0), "support-origin")
    context.add_box_collision("stack", (0.0, 0.0, top_z * 0.5), (0.32, 0.23, top_z))
    _finish(
        context,
        builder,
        visual_name="book_stack",
        overrides=overrides,
        bevel_m=0.0015,
    )


GENERATORS: dict[str, Generator] = {
    "book_stack_01": generate_book_stack_01,
    "desk_lamp_01": generate_desk_lamp_01,
    "monitor_01": generate_monitor_01,
    "mug_01": generate_mug_01,
    "potted_plant_01": generate_potted_plant_01,
}
