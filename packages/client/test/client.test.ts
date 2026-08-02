import { describe, expect, it, vi } from "vitest";
import {
  NEURALSTOCK_DISCOVERY_URL,
  NEURALSTOCK_REGISTRY_URL,
  NEURALSTOCK_SCHEMA_ORIGIN,
  NeuralStockError,
  artifactDescriptor,
  artifactUrl,
  fetchArtifact,
  loadCanonicalRegistry,
  loadDiscovery,
  loadRegistry,
  registryRevision,
  registrySnapshotUrl,
  resolveAsset,
  searchAssets,
  searchResolvedAssets,
  sha256Hex,
  verifyRegistryRevision,
  type AssetArtifact,
  type AssetManifest,
  type RegistryAssetEntry,
  type RegistryManifest,
  type RegistryWithdrawal,
} from "../src/index.js";

const SHA_A = "a".repeat(64);
const SHA_B = "b".repeat(64);

const discoveryDocument = {
  $schema: "https://schemas.neuralstock.ai/v0.2/discovery.schema.json",
  schema_version: "0.2",
  document_type: "discovery",
  site: "https://neuralstock.ai/",
  asset_origin: "https://assets.neuralstock.ai",
  schema_origin: "https://schemas.neuralstock.ai",
  registry: {
    canonical: "https://assets.neuralstock.ai/registry.json",
    latest_snapshot: "https://assets.neuralstock.ai/snapshots/latest.json",
    immutable_snapshot_template:
      "https://assets.neuralstock.ai/snapshots/{revision}/registry.json",
  },
  license_policy: ["CC0-1.0"],
  clients: { npm: "@neuralstock/client", python: "neuralstock" },
} as const;

function artifact(
  role: AssetArtifact["role"],
  fileName: string,
  uri: string,
  mediaType = "application/octet-stream",
): AssetArtifact {
  return {
    role,
    file_name: fileName,
    media_type: mediaType,
    sha256: SHA_A,
    bytes: 42,
    uri,
  };
}

const tableManifest: AssetManifest = {
  $schema: "https://schemas.neuralstock.ai/v0.2/asset.schema.json",
  schema_version: "0.2",
  document_type: "asset",
  generated: true,
  id: "wooden_table",
  version: "1.2.0",
  name: "Wooden Table",
  description: "A procedural wooden table for interior scenes.",
  publication_status: "published",
  published_at: "2026-08-01T00:00:00Z",
  license: "CC0-1.0",
  target_profile: "web-v1",
  coordinate_system: {
    unit: "meter",
    meters_per_unit: 1,
    up_axis: "Y",
    forward_axis: "+Z",
    handedness: "right",
    space: "asset-local",
  },
  semantics: {
    categories: ["furniture"],
    tags: ["table", "wood"],
    affordances: ["place-items"],
    placement: "floor",
  },
  bounds_m: {
    minimum: [-0.9, -0.45, 0],
    maximum: [0.9, 0.45, 0.75],
    dimensions: [1.8, 0.9, 0.75],
  },
  geometry: {
    vertex_count: 1_200,
    triangle_count: 2_400,
    material_count: 1,
    texture_count: 0,
  },
  source_generator: { geometry_node_group: "TableGenerator", parameters: {} },
  anchors: [
    {
      name: "ANCHOR_top_surface",
      position_m: [0, 0, 0.75],
      rotation_xyzw: [0, 0, 0, 1],
      semantic: "top-surface",
    },
  ],
  collisions: [],
  build_key: SHA_B,
  artifacts: {
    source: artifact("source", "source.blend", "/objects/source.blend"),
    runtime: artifact(
      "runtime",
      "model.glb",
      "/objects/model.glb",
      "model/gltf-binary",
    ),
    provenance: artifact(
      "provenance",
      "provenance.json",
      "/objects/provenance.json",
      "application/json",
    ),
    inspection: artifact(
      "inspection",
      "inspection.json",
      "/objects/inspection.json",
      "application/json",
    ),
    build_receipt: artifact(
      "build_receipt",
      "build-receipt.json",
      "/objects/build-receipt.json",
      "application/json",
    ),
    previews: [
      artifact("preview", "preview.webp", "/objects/preview.webp", "image/webp"),
    ],
  },
};

function entryFor(
  manifest: AssetManifest,
  manifestUri = `/assets/${manifest.id}/${manifest.version}/asset.json`,
): RegistryAssetEntry {
  return {
    asset: { id: manifest.id, version: manifest.version },
    name: manifest.name,
    description: manifest.description,
    license: manifest.license,
    target_profile: manifest.target_profile,
    coordinate_system: manifest.coordinate_system,
    semantics: manifest.semantics,
    bounds_m: manifest.bounds_m,
    triangle_count: manifest.geometry.triangle_count,
    manifest: artifact(
      "manifest",
      "asset.json",
      manifestUri,
      "application/json",
    ),
  };
}

function registryWith(
  entries: readonly RegistryAssetEntry[],
  options: {
    aliases?: RegistryManifest["aliases"];
    withdrawals?: readonly RegistryWithdrawal[];
  } = {},
): RegistryManifest {
  return {
    $schema: "https://schemas.neuralstock.ai/v0.2/registry.schema.json",
    schema_version: "0.2",
    document_type: "registry",
    generated: true,
    revision: SHA_B,
    generated_at: "2026-08-01T00:00:00Z",
    profiles: ["web-v1"],
    entries,
    aliases: options.aliases ?? [],
    withdrawals: options.withdrawals ?? [],
  };
}

describe("loadRegistry", () => {
  it("loads the public v0.2 entries and aliases shape", async () => {
    const snapshot = registryWith([entryFor(tableManifest)], {
      aliases: [
        { id: tableManifest.id, alias: "latest", version: tableManifest.version },
      ],
    });
    const fetcher = vi.fn(async () => Response.json(snapshot));

    const registry = await loadRegistry("https://registry.test/registry.json", {
      fetch: fetcher,
    });

    expect(registry.entries).toHaveLength(1);
    expect(registry.aliases[0]).toEqual({
      id: "wooden_table",
      alias: "latest",
      version: "1.2.0",
    });
    expect(fetcher).toHaveBeenCalledWith(
      "https://registry.test/registry.json",
      undefined,
    );
  });

  it("rejects the obsolete assets collection shape", async () => {
    await expect(
      loadRegistry({ assets: [] } as unknown as RegistryManifest),
    ).rejects.toMatchObject<Partial<NeuralStockError>>({
      code: "INVALID_REGISTRY",
    });
  });

  it.each([
    [
      "semantics",
      {
        ...entryFor(tableManifest),
        semantics: { ...tableManifest.semantics, tags: null },
      },
    ],
    [
      "bounds",
      {
        ...entryFor(tableManifest),
        bounds_m: { ...tableManifest.bounds_m, dimensions: [1, "wide", 1] },
      },
    ],
    [
      "runtime coordinates",
      {
        ...entryFor(tableManifest),
        coordinate_system: { ...tableManifest.coordinate_system, up_axis: "Z" },
      },
    ],
    [
      "geometry summary",
      { ...entryFor(tableManifest), triangle_count: "many" },
    ],
    [
      "manifest artifact",
      {
        ...entryFor(tableManifest),
        manifest: { ...entryFor(tableManifest).manifest, bytes: "42" },
      },
    ],
  ])("rejects malformed nested registry %s", async (_label, entry) => {
    const candidate = registryWith([
      entry as unknown as RegistryAssetEntry,
    ]);

    await expect(loadRegistry(candidate)).rejects.toMatchObject<
      Partial<NeuralStockError>
    >({ code: "INVALID_REGISTRY" });
  });
});

describe("searchAssets", () => {
  const stoolManifest: AssetManifest = {
    ...tableManifest,
    id: "steel_stool",
    version: "1.0.0",
    name: "Steel Stool",
    description: "A compact steel stool for an interior scene.",
    semantics: {
      categories: ["furniture"],
      tags: ["stool", "metal"],
      affordances: ["sit"],
      placement: "floor",
    },
    geometry: { ...tableManifest.geometry, triangle_count: 9_000 },
  };
  const registry = registryWith([entryFor(tableManifest), entryFor(stoolManifest)], {
    withdrawals: [
      {
        asset: { id: stoolManifest.id, version: stoolManifest.version },
        reason: "malformed",
        recorded_at: "2026-08-01T01:00:00Z",
        notice_uri: "notices/steel_stool-1.0.0.json",
      },
    ],
  });

  it("combines nested semantics and structured constraints", () => {
    expect(
      searchAssets(registry, {
        query: "wood table",
        tags: ["wood"],
        categories: ["furniture"],
        license: "CC0-1.0",
        max_triangles: 3_000,
      }).map((entry) => entry.asset.id),
    ).toEqual(["wooden_table"]);
  });

  it("excludes withdrawn versions unless requested", () => {
    expect(searchAssets(registry).map((entry) => entry.asset.id)).toEqual([
      "wooden_table",
    ]);
    expect(
      searchAssets(registry, { include_withdrawn: true }).map(
        (entry) => entry.asset.id,
      ),
    ).toEqual(["wooden_table", "steel_stool"]);
  });

  it("filters latest aliases, dimensions, placement, and affordances", () => {
    const oldTable = {
      ...tableManifest,
      version: "1.0.0",
      name: "Wooden Table Legacy",
    } satisfies AssetManifest;
    const versioned = registryWith(
      [entryFor(oldTable), entryFor(tableManifest), entryFor(stoolManifest)],
      {
        aliases: [
          { id: tableManifest.id, alias: "latest", version: tableManifest.version },
          { id: stoolManifest.id, alias: "latest", version: stoolManifest.version },
        ],
      },
    );

    expect(
      searchAssets(versioned, {
        query: "table",
        affordances: ["place-items"],
        placement: "floor",
        min_dimensions_m: [1.5, 0.5, 0.5],
        max_dimensions_m: { x: 2, y: 1, z: 1 },
        latest_only: true,
      }).map(({ asset }) => `${asset.id}@${asset.version}`),
    ).toEqual(["wooden_table@1.2.0"]);
  });

  it("resolves manifests only when applying a runtime byte budget", async () => {
    const oversizedManifest = {
      ...stoolManifest,
      artifacts: {
        ...stoolManifest.artifacts,
        runtime: { ...stoolManifest.artifacts.runtime, bytes: 5_000 },
      },
    } satisfies AssetManifest;
    const manifests = new Map([
      [tableManifest.id, tableManifest],
      [oversizedManifest.id, oversizedManifest],
    ]);
    const registry = await loadRegistry(
      registryWith([entryFor(tableManifest), entryFor(oversizedManifest)]),
      {
        baseUrl: "https://registry.test/registry.json",
        fetch: async (input) => {
          const id = [...manifests.keys()].find((candidate) =>
            input.toString().includes(candidate),
          );
          return Response.json(manifests.get(id ?? "") ?? {});
        },
      },
    );

    const matches = await searchResolvedAssets(registry, { max_bytes: 100 });
    expect(matches.map(({ entry }) => entry.asset.id)).toEqual(["wooden_table"]);
  });
});

describe("discovery and integrity", () => {
  it("loads and validates the canonical machine-discovery document", async () => {
    const fetcher = vi.fn(async () => Response.json(discoveryDocument));

    await expect(loadDiscovery({ fetch: fetcher })).resolves.toEqual(
      discoveryDocument,
    );
    expect(fetcher).toHaveBeenCalledWith(NEURALSTOCK_DISCOVERY_URL, undefined);
    expect(NEURALSTOCK_SCHEMA_ORIGIN).toBe(discoveryDocument.schema_origin);

    await expect(
      loadDiscovery("https://mirror.test/discovery.json", {
        fetch: async () => Response.json({ ...discoveryDocument, clients: {} }),
      }),
    ).rejects.toMatchObject<Partial<NeuralStockError>>({
      code: "INVALID_DISCOVERY",
    });
  });

  it("loads the canonical registry and derives an immutable snapshot URL", async () => {
    const snapshot = registryWith([entryFor(tableManifest)]);
    const fetcher = vi.fn(async () => Response.json(snapshot));

    await expect(loadCanonicalRegistry({ fetch: fetcher })).resolves.toEqual(
      snapshot,
    );
    expect(fetcher).toHaveBeenCalledWith(NEURALSTOCK_REGISTRY_URL, undefined);
    expect(registrySnapshotUrl(snapshot)).toBe(
      `https://assets.neuralstock.ai/snapshots/${SHA_B}/registry.json`,
    );
  });

  it("verifies and rejects tampering with the semantic registry revision", async () => {
    const snapshot = registryWith([entryFor(tableManifest)]);
    snapshot.revision = await registryRevision(snapshot);

    await expect(verifyRegistryRevision(snapshot)).resolves.toBeUndefined();
    await expect(loadRegistry(snapshot, { integrity: "strict" })).resolves.toBe(
      snapshot,
    );

    const tampered = { ...snapshot, generated_at: "2026-08-02T00:00:00Z" };
    await expect(
      loadRegistry(tampered, { integrity: "strict" }),
    ).rejects.toMatchObject<Partial<NeuralStockError>>({
      code: "INTEGRITY_MISMATCH",
    });
  });

  it("verifies exact manifest bytes during strict resolution", async () => {
    const manifestBytes = new TextEncoder().encode(JSON.stringify(tableManifest));
    const manifestSha = await sha256Hex(manifestBytes);
    const entry = entryFor(tableManifest);
    entry.manifest = {
      ...entry.manifest,
      bytes: manifestBytes.byteLength,
      sha256: manifestSha,
    };
    const registry = await loadRegistry(registryWith([entry]), {
      baseUrl: "https://registry.test/registry.json",
      fetch: async () => new Response(manifestBytes),
    });

    await expect(
      resolveAsset(registry, tableManifest.id, { integrity: "strict" }),
    ).resolves.toMatchObject({ id: tableManifest.id });

    const corruptRegistry = await loadRegistry(registryWith([entry]), {
      baseUrl: "https://registry.test/registry.json",
      fetch: async () => new Response(`${JSON.stringify(tableManifest)} `),
    });
    await expect(
      resolveAsset(corruptRegistry, tableManifest.id, { integrity: "strict" }),
    ).rejects.toMatchObject<Partial<NeuralStockError>>({
      code: "INTEGRITY_MISMATCH",
    });
  });

  it("fetches an artifact only when its bytes match the descriptor", async () => {
    const body = new TextEncoder().encode("verified model bytes");
    const runtime = {
      ...tableManifest.artifacts.runtime,
      uri: "https://assets.test/model.glb",
      bytes: body.byteLength,
      sha256: await sha256Hex(body),
    };
    const asset = {
      ...tableManifest,
      artifacts: { ...tableManifest.artifacts, runtime },
    } satisfies AssetManifest;

    expect(artifactDescriptor(asset, "model")).toBe(runtime);
    await expect(
      fetchArtifact(asset, "model", {
        fetch: async () => new Response(body),
      }),
    ).resolves.toEqual(body.buffer);
    await expect(
      fetchArtifact(asset, "model", {
        fetch: async () => new Response("corrupt"),
      }),
    ).rejects.toMatchObject<Partial<NeuralStockError>>({
      code: "INTEGRITY_MISMATCH",
    });
  });
});

describe("resolveAsset and artifactUrl", () => {
  it("resolves a versioned manifest and sibling artifacts from canonical uris", async () => {
    const snapshot = registryWith(
      [entryFor(tableManifest, "content/table/asset.json")],
      {
        aliases: [
          {
            id: tableManifest.id,
            alias: "latest",
            version: tableManifest.version,
          },
        ],
      },
    );
    const fetcher = vi.fn(async (input: RequestInfo | URL) =>
      input.toString().endsWith("registry.json")
        ? Response.json(snapshot)
        : Response.json(tableManifest),
    );

    const registry = await loadRegistry("https://registry.test/registry.json", {
      fetch: fetcher,
    });
    const asset = await resolveAsset(registry, "wooden_table@1.2.0");

    expect(fetcher).toHaveBeenLastCalledWith(
      "https://registry.test/content/table/asset.json",
      undefined,
    );
    expect(artifactUrl(asset, "model")).toBe(
      "https://registry.test/objects/model.glb",
    );
    expect(artifactUrl(asset, "source")).toBe(
      "https://registry.test/objects/source.blend",
    );
  });

  it("retains a per-resolution mirror base for artifact urls", async () => {
    const snapshot = registryWith([
      entryFor(tableManifest, "/assets/wooden_table/1.2.0/asset.json"),
    ]);
    const fetcher = vi.fn(async () => Response.json(tableManifest));
    const registry = await loadRegistry(snapshot, {
      baseUrl: "https://origin.test/registry.json",
      fetch: fetcher,
    });

    const asset = await resolveAsset(registry, "wooden_table@1.2.0", {
      baseUrl: "https://mirror.test/registry.json",
    });

    expect(fetcher).toHaveBeenCalledWith(
      "https://mirror.test/assets/wooden_table/1.2.0/asset.json",
      undefined,
    );
    expect(artifactUrl(asset, "model")).toBe(
      "https://mirror.test/objects/model.glb",
    );
  });

  it("uses the top-level latest alias for bare and latest references", async () => {
    const registry = await loadRegistry(
      registryWith([entryFor(tableManifest)], {
        aliases: [
          {
            id: tableManifest.id,
            alias: "latest",
            version: tableManifest.version,
          },
        ],
      }),
      {
        baseUrl: "https://registry.test/registry.json",
        fetch: async () => Response.json(tableManifest),
      },
    );

    await expect(resolveAsset(registry, "wooden_table")).resolves.toMatchObject({
      id: "wooden_table",
      version: "1.2.0",
    });
    await expect(
      resolveAsset(registry, "wooden_table@latest"),
    ).resolves.toMatchObject({ id: "wooden_table", version: "1.2.0" });
  });

  it("recognizes canonical optional artifact descriptors", () => {
    const collision = artifact(
      "collision",
      "collision.glb",
      "https://cdn.test/collision.glb",
      "model/gltf-binary",
    );
    const asset: AssetManifest = {
      ...tableManifest,
      artifacts: {
        ...tableManifest.artifacts,
        optional: [collision],
      },
    };

    expect(artifactUrl(asset, "collision")).toBe(
      "https://cdn.test/collision.glb",
    );
    expect(artifactUrl(asset, collision)).toBe(
      "https://cdn.test/collision.glb",
    );
  });

  it("models common evidence sidecar descriptors", () => {
    const evidence = artifact(
      "evidence",
      "author-attestation.md",
      "https://cdn.test/author-attestation.md",
      "text/markdown",
    );
    const buildEvidence = artifact(
      "build_evidence",
      "reproduction.json",
      "https://cdn.test/reproduction.json",
      "application/json",
    );

    expect(artifactUrl(tableManifest, evidence)).toBe(
      "https://cdn.test/author-attestation.md",
    );
    expect(artifactUrl(tableManifest, buildEvidence)).toBe(
      "https://cdn.test/reproduction.json",
    );
  });

  it("reports artifacts absent from the manifest", () => {
    expect(() => artifactUrl(tableManifest, "collision")).toThrowError(
      expect.objectContaining({ code: "ARTIFACT_NOT_FOUND" }),
    );
  });

  it.each([
    [
      "semantics",
      {
        ...tableManifest,
        semantics: { ...tableManifest.semantics, affordances: null },
      },
    ],
    [
      "bounds",
      {
        ...tableManifest,
        bounds_m: { ...tableManifest.bounds_m, minimum: [0, "low", 0] },
      },
    ],
    [
      "geometry",
      {
        ...tableManifest,
        geometry: { ...tableManifest.geometry, vertex_count: "many" },
      },
    ],
    [
      "runtime coordinates",
      {
        ...tableManifest,
        coordinate_system: {
          ...tableManifest.coordinate_system,
          forward_axis: "-Z",
        },
      },
    ],
    [
      "anchor quaternion",
      {
        ...tableManifest,
        anchors: [
          {
            ...tableManifest.anchors[0],
            rotation_xyzw: [0, 0, 0, 0],
          },
        ],
      },
    ],
    [
      "collision",
      {
        ...tableManifest,
        collisions: [
          {
            name: "COLLISION_box",
            kind: "box",
            bounds_m: {
              minimum: [-0.5, 0, -0.5],
              maximum: [0.5, 1, 0.5],
              dimensions: [1, 1, 1],
            },
            vertex_count: "eight",
            triangle_count: 12,
          },
        ],
      },
    ],
    [
      "collision bounds",
      {
        ...tableManifest,
        collisions: [
          {
            name: "COLLISION_box",
            kind: "box",
            bounds_m: {
              minimum: [-0.5, 0, -0.5],
              maximum: [0.5, 1, 0.5],
              dimensions: [1, 99, 1],
            },
            vertex_count: 8,
            triangle_count: 12,
          },
        ],
      },
    ],
    [
      "artifact collection",
      {
        ...tableManifest,
        artifacts: { ...tableManifest.artifacts, previews: "preview.png" },
      },
    ],
    [
      "asset-optional evidence role",
      {
        ...tableManifest,
        artifacts: {
          ...tableManifest.artifacts,
          optional: [
            artifact(
              "evidence",
              "author-attestation.md",
              "/objects/author-attestation.md",
              "text/markdown",
            ),
          ],
        },
      },
    ],
    [
      "source generator",
      {
        ...tableManifest,
        source_generator: {
          ...tableManifest.source_generator,
          parameters: [],
        },
      },
    ],
  ])("rejects malformed nested asset %s", async (_label, candidate) => {
    const registry = await loadRegistry(registryWith([entryFor(tableManifest)]), {
      baseUrl: "https://registry.test/registry.json",
      fetch: async () => Response.json(candidate),
    });

    await expect(
      resolveAsset(registry, "wooden_table@1.2.0"),
    ).rejects.toMatchObject<Partial<NeuralStockError>>({
      code: "INVALID_ASSET",
    });
  });
});
