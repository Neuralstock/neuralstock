"""Blender-owned smoke checks for the web-v1 source preflight.

Run this file with Blender 4.5 rather than CPython. It creates only in-memory
scenes and a temporary linked-library fixture; it does not regenerate catalog
assets.
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "blender"))

from inspection import (  # noqa: E402, I001
    _enforce_web_v1_source,
    _path_violation,
    _web_v1_source_checks,
    export_glb,
)
from asset_builder import MeshBuilder, begin_asset, float_parameter  # noqa: E402
from ns_common import NeuralStockError, load_parameter_schema, store_parameter_schema  # noqa: E402


SOURCE_CHECK_CODES = {
    "anchor_contract",
    "applied_visual_mesh_scale",
    "collision_contract",
    "geometry_node_parameter_interface",
    "no_arbitrary_drivers",
    "no_embedded_text_blocks",
    "no_external_resource_paths",
    "no_linked_libraries",
    "no_script_nodes",
    "single_top_level_asset_collection",
    "visual_meshes_in_asset_collection",
}


def _baseline() -> bpy.types.Object:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    asset = bpy.data.collections.new("ASSET")
    bpy.context.scene.collection.children.link(asset)
    collision = bpy.data.collections.new("COLLISION")
    bpy.context.scene.collection.children.link(collision)
    mesh = bpy.data.meshes.new("visual_mesh")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    obj = bpy.data.objects.new("visual", mesh)
    asset.objects.link(obj)
    return obj


def _parametric_baseline() -> bpy.types.Object:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    context = begin_asset("profile_smoke", "1.0.0")
    builder = MeshBuilder()
    builder.add_box((0.0, 0.0, 0.5), (1.0, 1.0, 1.0), "wood")
    obj = context.add_visual("body", builder)
    parameters = {
        name: float_parameter(name, 1.0, 0.25, 4.0, f"{name} dimension")
        for name in ("width_m", "depth_m", "height_m")
    }
    context.finish_parametric(
        obj,
        node_group="ProfileSmokeGenerator",
        parameters=parameters,
        dimensions=("width_m", "depth_m", "height_m"),
        bevel_m=0.003,
    )
    return obj


def _collision_cube(name: str) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(
        [
            (-0.5, -0.5, -0.5),
            (-0.5, -0.5, 0.5),
            (-0.5, 0.5, -0.5),
            (-0.5, 0.5, 0.5),
            (0.5, -0.5, -0.5),
            (0.5, -0.5, 0.5),
            (0.5, 0.5, -0.5),
            (0.5, 0.5, 0.5),
        ],
        [],
        [
            (0, 4, 6, 2),
            (1, 3, 7, 5),
            (0, 1, 5, 4),
            (2, 6, 7, 3),
            (0, 2, 3, 1),
            (4, 5, 7, 6),
        ],
    )
    collision = bpy.data.objects.new(name, mesh)
    collision.hide_render = True
    collision["neuralstock_collision"] = True
    collision["neuralstock_collision_shape"] = "box"
    bpy.data.collections["COLLISION"].objects.link(collision)
    return collision


def _statuses() -> dict[str, str]:
    return {item["code"]: item["status"] for item in _web_v1_source_checks()}


def _expect_failure(code: str) -> None:
    statuses = _statuses()
    assert statuses.keys() >= SOURCE_CHECK_CODES, statuses
    assert statuses[code] == "fail", statuses
    try:
        _enforce_web_v1_source()
    except NeuralStockError as error:
        assert code in str(error), error
    else:
        raise AssertionError(f"source preflight did not enforce {code}")

    destination = Path(f"/tmp/{code}.glb")
    destination.unlink(missing_ok=True)
    try:
        export_glb(destination)
    except NeuralStockError as error:
        assert code in str(error), error
    else:
        raise AssertionError(f"GLB export did not enforce {code}")
    assert not destination.exists()


def main() -> None:
    _baseline()
    statuses = _statuses()
    assert all(statuses[code] == "pass" for code in SOURCE_CHECK_CODES), statuses
    _enforce_web_v1_source()

    _parametric_baseline()
    statuses = _statuses()
    assert all(statuses[code] == "pass" for code in SOURCE_CHECK_CODES), statuses
    _enforce_web_v1_source()

    _parametric_baseline()
    definitions = load_parameter_schema()
    definitions["width_m"]["binding"] = {
        "kind": "modifier_property",
        "object": "body",
        "modifier": "NS_Bevel",
        "property": "width",
    }
    store_parameter_schema(definitions)
    _expect_failure("geometry_node_parameter_interface")

    _parametric_baseline()
    group = bpy.data.node_groups["ProfileSmokeGenerator"]
    width_link = next(
        link
        for link in group.links
        if link.from_node.type == "GROUP_INPUT" and link.from_socket.name == "width_m"
    )
    group.links.remove(width_link)
    _expect_failure("geometry_node_parameter_interface")

    _baseline()
    asset = bpy.data.collections["ASSET"]
    invalid_anchor_mesh = bpy.data.meshes.new("invalid_anchor_mesh")
    invalid_anchor = bpy.data.objects.new("ANCHOR_bad", invalid_anchor_mesh)
    invalid_anchor["neuralstock_anchor_role"] = "bad-anchor"
    asset.objects.link(invalid_anchor)
    _expect_failure("anchor_contract")

    _baseline()
    collision = bpy.data.collections["COLLISION"]
    collision_mesh = bpy.data.meshes.new("invalid_collision_mesh")
    invalid_collision = bpy.data.objects.new("COLLISION_Bad", collision_mesh)
    invalid_collision.hide_render = True
    invalid_collision["neuralstock_collision"] = True
    invalid_collision["neuralstock_collision_shape"] = "box"
    collision.objects.link(invalid_collision)
    _expect_failure("collision_contract")

    _baseline()
    collision = bpy.data.collections["COLLISION"]
    collision_mesh = bpy.data.meshes.new("renderable_collision_mesh")
    renderable_collision = bpy.data.objects.new("COLLISION_renderable", collision_mesh)
    renderable_collision.hide_render = False
    renderable_collision["neuralstock_collision"] = True
    renderable_collision["neuralstock_collision_shape"] = "box"
    collision.objects.link(renderable_collision)
    _expect_failure("collision_contract")

    _baseline()
    collision = bpy.data.collections["COLLISION"]
    triangle_mesh = bpy.data.meshes.new("triangle_collision_mesh")
    triangle_mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    triangle = bpy.data.objects.new("COLLISION_triangle", triangle_mesh)
    triangle.hide_render = True
    triangle["neuralstock_collision"] = True
    triangle["neuralstock_collision_shape"] = "box"
    collision.objects.link(triangle)
    _expect_failure("collision_contract")

    _baseline()
    rotated = _collision_cube("COLLISION_rotated")
    rotated.rotation_euler[2] = 0.25
    _expect_failure("collision_contract")

    _baseline()
    asset = bpy.data.collections["ASSET"]
    bpy.context.scene.collection.children.unlink(asset)
    wrapper = bpy.data.collections.new("wrapper")
    bpy.context.scene.collection.children.link(wrapper)
    wrapper.children.link(asset)
    _expect_failure("single_top_level_asset_collection")

    _baseline()
    outside = bpy.data.collections.new("outside")
    bpy.context.scene.collection.children.link(outside)
    mesh = bpy.data.meshes.new("outside_mesh")
    outside.objects.link(bpy.data.objects.new("outside_visual", mesh))
    _expect_failure("visual_meshes_in_asset_collection")

    obj = _baseline()
    obj.scale = (2.0, 1.0, 1.0)
    _expect_failure("applied_visual_mesh_scale")

    _baseline()
    bpy.data.texts.new("embedded.py").write("print('must never execute')")
    _expect_failure("no_embedded_text_blocks")

    _baseline()
    material = bpy.data.materials.new("scripted")
    material.use_nodes = True
    assert material.node_tree is not None
    material.node_tree.nodes.new("ShaderNodeScript")
    _expect_failure("no_script_nodes")

    obj = _baseline()
    obj.driver_add("hide_render")
    _expect_failure("no_arbitrary_drivers")

    _baseline()
    image = bpy.data.images.new("external_image", width=1, height=1)
    image.source = "FILE"
    image.filepath = "https://example.invalid/texture.png"
    _expect_failure("no_external_resource_paths")

    _baseline()
    material = bpy.data.materials.new("external_ies")
    material.use_nodes = True
    assert material.node_tree is not None
    ies = material.node_tree.nodes.new("ShaderNodeTexIES")
    ies.mode = "EXTERNAL"
    ies.filepath = "//lighting/profile.ies"
    _expect_failure("no_external_resource_paths")

    obj = _baseline()
    mesh_cache = obj.modifiers.new("external_cache", "MESH_CACHE")
    mesh_cache.filepath = "//cache/deformation.mdd"
    _expect_failure("no_external_resource_paths")

    _baseline()
    library_mesh = bpy.data.meshes.new("linked_mesh")
    library_path = Path("/tmp/neuralstock-inspection-library.blend")
    bpy.data.libraries.write(str(library_path), {library_mesh})
    bpy.data.meshes.remove(library_mesh)
    with bpy.data.libraries.load(str(library_path), link=True) as (available, loaded):
        loaded.meshes = [available.meshes[0]]
    _expect_failure("no_linked_libraries")

    assert _path_violation("//textures/packed.png", packed=True) is None
    assert _path_violation("textures/unpacked.png", packed=False) == "external"
    assert _path_violation("/tmp/texture.png", packed=True) == "absolute"
    assert _path_violation(r"C:\\textures\\texture.png", packed=True) == "absolute"
    assert _path_violation("https://example.invalid/a.png", packed=True) == "network-or-uri"
    print("NEURALSTOCK inspection profile smoke passed")


if __name__ == "__main__":
    main()
