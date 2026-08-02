# NeuralStock Blender tooling

These scripts form the Blender-owned stage of the v0.2 build. They use only
Blender's bundled Python packages and are pinned to Blender 4.5 LTS.

## Commands

- `generate_room_zero.py` generates a repository-owned `.blend` fixture.
- `inspect_export.py` applies declared bounded parameters, extracts asset facts,
  emits schema-shaped inspection JSON plus an optional detailed sidecar, and
  exports GLB.
- `render_preview.py` frames evaluated geometry and renders a deterministic
  512x512 transparent PNG with Workbench where available, or a fixed EEVEE
  lighting rig in headless Blender builds.
- `build_asset.py` runs the full local golden path and writes `source.blend`,
  `model.glb`, `preview.png`, `inspection.json`, `blender-details.json`, and
  `blender-build.json`.
- `build_room_zero.py` builds all 15 Room Zero packages in one Blender process
  and emits an aggregate `room-zero-build.json` receipt. Its `--source-root`
  mode rebuilds every runtime artifact from accepted, immutable `.blend`
  inputs for collection-wide reproducibility checks.

All script arguments follow Blender's `--` separator. For example:

```sh
blender \
  --background \
  --factory-startup \
  --disable-autoexec \
  --python-exit-code 1 \
  --python blender/build_asset.py \
  -- \
  --generate procedural_crate_01 \
  --asset-version 1.0.1 \
  --output-dir dist/procedural_crate_01/1.0.1
```

To process an existing source, place its filename before `--python` and omit
`--generate`.

Parameter overrides may be inline JSON, a path to JSON, or `@path`. Unknown,
wrongly typed, non-finite, out-of-range, or non-agent-safe parameters fail the
build. Bindings are embedded by repository generators; no expressions are
evaluated and no contributor Python is loaded.

Before GLB export, the web-v1 source preflight requires exactly one top-level
`ASSET` collection, keeps every non-collision mesh inside its collection tree,
and requires `[1, 1, 1]` local scale on every visual mesh. It rejects Blender
text blocks, script nodes, animation drivers, linked libraries, unpacked file
dependencies, absolute paths, and network/URI resource paths. Resource scanning
covers images, fonts, sounds, movie clips, cache files, volumes, linked
libraries, and path-bearing nodes, modifiers, and sequencer strips. A v0.2
collision proxy must be an exact, positive-volume, asset-local axis-aligned box
with eight evaluated corner vertices and twelve triangles; its bounds are
published in `inspection.json`. The same checks and their pass/fail status are
emitted there.

## Generator extension

Room Zero generators register through `room_zero_generators.py`; reusable mesh,
material, anchor, collision, and safe parameter bindings live in
`asset_builder.py`. A generator must create an `ASSET` collection, use metric
units, keep evaluated visual bounds ground-centered, declare bounded
parameters, create useful `ANCHOR_*` empties and `COLLISION_*` meshes, and set
scene identity metadata. The collection includes four architectural modules,
five furniture assets, the procedural crate, and five tabletop props. Floor,
wall, door, window, table, shelf, and crate are parametric.

## Intentional v0.2 boundaries

- The Blender stage records glTF validation as not yet run. The outer pipeline
  must run Khronos glTF Validator and replace that result before publication.
- GLB pruning, meshopt compression, KTX2 transcoding, LOD generation, and
  automatic convex hulls are later pipeline stages.
- Previews are deterministic for a pinned image and CPU renderer;
  byte identity across different Blender builds or graphics drivers is not
  promised.
- Room Zero is deliberately small; later collections can register additional
  repository-owned generators without changing the inspection/export contract.
