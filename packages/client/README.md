# `@neuralstock/client`

A small, dependency-free ESM client for static NeuralStock registry snapshots,
asset manifests, and content-addressed artifacts. It runs in modern browsers and
Node.js 20 or newer.

```sh
pnpm add @neuralstock/client
```

## Quick start

```ts
import {
  fetchArtifact,
  loadCanonicalRegistry,
  resolveAsset,
  searchAssets,
} from "@neuralstock/client";

const registry = await loadCanonicalRegistry({ integrity: "strict" });
const [entry] = searchAssets(registry, {
  query: "wooden table",
  license: "CC0-1.0",
  max_triangles: 20_000,
  max_dimensions_m: [4, 2, 3],
  placement: "floor",
  affordances: ["place-items"],
  latest_only: true,
});

if (entry) {
  // Strict mode inherited from loadCanonicalRegistry verifies the manifest
  // byte length and SHA-256 declared by the registry entry.
  const asset = await resolveAsset(registry, entry, { integrity: "strict" });
  // The runtime is returned only after its exact bytes and SHA-256 verify.
  const modelBytes = await fetchArtifact(asset, "runtime");
}
```

Registry entries are immutable asset versions; bare IDs and `@latest` resolve through the snapshot's top-level alias table. Absolute and root-relative artifact URIs are used directly, while relative references resolve from the registry snapshot's base URL so mirrored releases remain portable.

The canonical public endpoints are exported as
`NEURALSTOCK_REGISTRY_URL`, `NEURALSTOCK_LATEST_SNAPSHOT_URL`, and
`NEURALSTOCK_DISCOVERY_URL`. `registrySnapshotUrl(registry)` derives the
immutable URL for a loaded revision.

Agents that start with only the project domain can fetch and validate the
well-known discovery contract before loading its advertised registry:

```ts
import { loadDiscovery, loadRegistry } from "@neuralstock/client";

const discovery = await loadDiscovery();
const discoveredRegistry = await loadRegistry(discovery.registry.canonical, {
  integrity: "strict",
});
```

## Integrity

`integrity: "strict"` on `loadRegistry` recomputes the registry's semantic
revision. The same option on `resolveAsset` verifies the exact manifest bytes.
Loading the canonical registry in strict mode also makes strict manifest
verification the default for assets resolved from it.

Use `fetchArtifact` when a consumer needs verified artifact bytes:

```ts
import { fetchArtifact } from "@neuralstock/client";

const glb = await fetchArtifact(asset, "runtime");
// glb is an ArrayBuffer whose byte length and SHA-256 match asset.json.
```

This deliberately buffers the artifact for Web Crypto verification. Renderers
that need streaming should use `artifactUrl` and rely on their own incremental
integrity pipeline.

The v0.2 registry projects dimensions and semantic fields directly, so
`searchAssets` can filter them without manifest requests. Runtime/source file
sizes live in each manifest; use `searchResolvedAssets` only when an exact byte
budget is required:

```ts
import { searchResolvedAssets } from "@neuralstock/client";

const compact = await searchResolvedAssets(registry, {
  query: "chair",
  max_bytes: 2_000_000,
  byte_budget_artifact: "runtime",
  latest_only: true,
});
```

Pass `baseUrl` to `resolveAsset` to select a mirror for both the manifest request
and later verified artifact fetches:

```ts
const asset = await resolveAsset(registry, entry, {
  baseUrl: "https://mirror.example/registry.json",
  integrity: "strict",
});
const modelBytes = await fetchArtifact(asset, "runtime"); // fetched from mirror
```

## Coordinate contract

Published `asset.json` bounds and anchors are already expressed in the GLB's
right-handed, meter-based, Y-up, +Z-forward asset-local space. Anchor
`rotation_xyzw` is a unit quaternion in `[x, y, z, w]` order. Apply both the
anchor position and quaternion directly beneath the same transform as the
loaded model; do not repeat Blender's Z-up to glTF conversion in the client.
The same rule applies to `collisions[].bounds_m`, which exactly describes each
v0.2 axis-aligned box collider. Geometry counts in the public manifest describe
the runtime GLB; source mesh counts remain in `inspection.json`.
