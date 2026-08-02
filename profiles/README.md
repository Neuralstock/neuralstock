# Runtime profiles

Profiles are versioned, machine-readable policy. `web-v1` fixes both the source
authoring convention and the exported runtime convention so clients never have
to guess which coordinate space a value describes.

Blender source uses meters, Z-up, and -Y object-forward. Blender's glTF export
maps that into glTF's right-handed, meter-based Y-up runtime coordinates. Values
in `inspection.json` are explicitly source/asset-local values. Packaging maps
positions from `(X, Y, Z)` to `(X, Z, -Y)` and changes quaternion basis before
publishing `asset.json` and `registry.json`; those documents therefore describe
the GLB's meter-based, Y-up, +Z-forward runtime space.

The budgets are v0.2 acceptance ceilings for a single ordinary prop, not a
promise that every client can render that maximum cheaply. Collections may add
stricter profiles later without mutating `web-v1`.

`web-v1.json` embeds the complete repository MIT notice in
`x-neuralstock-document-license`. The identical notice is also published at
the indefinitely locked
`https://schemas.neuralstock.ai/profiles/v0.2/LICENSE`. A profile mirror must
preserve both objects byte-for-byte.
