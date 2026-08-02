# Room Zero

The smallest NeuralStock browser consumer: a plain Three.js viewer that discovers models, bounds, anchors, and collision data from registry metadata.

```sh
pnpm --filter @neuralstock/room-zero dev
```

The bundled registry is intentionally empty, so a fresh checkout demonstrates the no-assets state. Point it at a populated snapshot with either:

```text
?registry=https://assets.example/registry.json&asset=wooden_table@1.2.0
```

or `VITE_NEURALSTOCK_REGISTRY_URL`. Registry and artifact origins must allow the viewer origin through CORS.

The viewer verifies the registry revision, each selected manifest, and every
preview, displayed GLB, and individual download against its declared byte count
and SHA-256 before use. It consumes bounds, anchor transforms, and exact
box-collider bounds from verified `asset.json` metadata. Those values use the GLB runtime coordinate system: meters,
right-handed Y-up, +Z-forward, and asset-local. Anchor markers apply both
`position_m` and the `[x, y, z, w]` `rotation_xyzw` quaternion, so their axes
show the attachment orientation as well as its location. Collision overlays are
constructed directly from `collisions[].bounds_m`; no second collision GLB is
required for the v0.2 box-only profile.

## Real-browser smoke test

The Playwright check serves the built viewer and a complete static release from one local origin. It loads a real GLB, exercises metadata overlays, resizes the renderer, simulates WebGL context loss and recovery, rejects browser/network errors, and captures desktop and narrow screenshots under the ignored `output/playwright/` directory.

Install Chromium once, then point the test at a release containing `registry.json`, `assets/`, and `objects/`:

```sh
pnpm --filter @neuralstock/room-zero test:e2e:install
NEURALSTOCK_RELEASE_DIR="$PWD/dist/release" pnpm test:e2e
```

The default release directory is `dist/release`. Set `NEURALSTOCK_E2E_ASSET=id@version` to require a specific published asset; otherwise the viewer opens the registry's first entry. A missing release fails before the browser starts with the exact expected path.
