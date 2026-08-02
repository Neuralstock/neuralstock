import { NeuralStockError } from "./errors.js";
import { verifyArtifactBytes } from "./integrity.js";
import { defaultFetch, getAssetContext, resolveUrl } from "./internal.js";
import type {
  ArtifactUrlOptions,
  AssetArtifact,
  AssetManifest,
  FetchArtifactOptions,
} from "./types.js";

interface NamedArtifact {
  key: string;
  value: AssetArtifact;
}

function artifactsOf(asset: AssetManifest): NamedArtifact[] {
  return [
    { key: "source", value: asset.artifacts.source },
    { key: "runtime", value: asset.artifacts.runtime },
    { key: "provenance", value: asset.artifacts.provenance },
    { key: "inspection", value: asset.artifacts.inspection },
    { key: "build_receipt", value: asset.artifacts.build_receipt },
    ...asset.artifacts.previews.map((value) => ({ key: "preview", value })),
    ...(asset.artifacts.optional ?? []).map((value) => ({
      key: value.role,
      value,
    })),
  ];
}

function normalize(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

const roleAliases: Readonly<Record<string, readonly string[]>> = {
  model: ["runtime", "model", "glb", "gltf"],
  runtime: ["runtime", "model", "glb", "gltf"],
  source: ["source", "blend", "blender"],
  collision: ["collision", "collider", "physics"],
  preview: ["preview", "thumbnail", "poster", "turntable"],
};

function scoreArtifact(candidate: NamedArtifact, requested: string): number {
  const wanted = normalize(requested);
  const fields = [
    candidate.key,
    candidate.value.role,
    candidate.value.file_name,
  ].map(normalize);
  if (fields.includes(wanted)) return 100;

  const aliases = (roleAliases[requested.toLowerCase()] ?? [requested]).map(
    normalize,
  );
  if (fields.some((field) => aliases.includes(field))) return 50;
  if (aliases.some((alias) => normalize(candidate.value.uri).includes(alias))) {
    return 10;
  }
  return 0;
}

export function artifactDescriptor(
  asset: AssetManifest,
  artifact: string | AssetArtifact,
): AssetArtifact {
  let selected: AssetArtifact | undefined;

  if (typeof artifact === "string") {
    selected = artifactsOf(asset)
      .map((candidate, index) => ({
        candidate,
        index,
        score: scoreArtifact(candidate, artifact),
      }))
      .filter(({ score }) => score > 0)
      .sort((left, right) => right.score - left.score || left.index - right.index)[0]
      ?.candidate.value;
  } else {
    selected = artifact;
  }

  if (!selected) {
    const requested = typeof artifact === "string" ? artifact : artifact.role;
    throw new NeuralStockError(
      "ARTIFACT_NOT_FOUND",
      `Asset ${asset.id}@${asset.version} has no ${requested} artifact.`,
    );
  }

  return selected;
}

export function artifactUrl(
  asset: AssetManifest,
  artifact: string | AssetArtifact,
  options: ArtifactUrlOptions = {},
): string {
  const selected = artifactDescriptor(asset, artifact);

  const context = getAssetContext(asset);
  return resolveUrl(
    selected.uri,
    options.baseUrl?.toString(),
    context?.registryUrl,
    context?.documentUrl,
  );
}

/** Fetch an artifact and verify its declared byte length and SHA-256. */
export async function fetchArtifact(
  asset: AssetManifest,
  artifact: string | AssetArtifact,
  options: FetchArtifactOptions = {},
): Promise<ArrayBuffer> {
  const descriptor = artifactDescriptor(asset, artifact);
  const url = artifactUrl(asset, descriptor, options);
  const context = getAssetContext(asset);
  const fetcher = options.fetch ?? context?.fetch ?? defaultFetch();

  let response: Response;
  try {
    response = await fetcher(url, options.requestInit ?? context?.requestInit);
  } catch (error) {
    throw new NeuralStockError("FETCH_FAILED", `Could not fetch ${url}.`, {
      cause: error,
    });
  }

  if (!response.ok) {
    throw new NeuralStockError(
      "FETCH_FAILED",
      `Could not fetch ${url}: ${response.status} ${response.statusText}`.trim(),
    );
  }

  const bytes = await response.arrayBuffer();
  await verifyArtifactBytes(descriptor, bytes);
  return bytes;
}
