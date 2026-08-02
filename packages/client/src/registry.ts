import { NeuralStockError } from "./errors.js";
import { verifyArtifactBytes, verifyRegistryRevision } from "./integrity.js";
import {
  assertAsset,
  assertRegistry,
  defaultFetch,
  getRegistryContext,
  registryEntries,
  resolveUrl,
  setAssetContext,
  setRegistryContext,
} from "./internal.js";
import type {
  AssetManifest,
  AssetArtifact,
  AssetReference,
  FetchLike,
  IntegrityMode,
  LoadRegistryOptions,
  RegistryAssetEntry,
  RegistryManifest,
  RegistrySource,
  ResolvedAssetSearchResult,
  ResolveAssetOptions,
  SearchAssetsOptions,
  SearchResolvedAssetsOptions,
  Vector3Value,
} from "./types.js";

function requestedUrl(source: string | URL): string {
  return source instanceof URL ? source.href : source;
}

async function readJson(
  url: string,
  fetcher: FetchLike,
  requestInit?: RequestInit,
  expected?: AssetArtifact,
  integrity: IntegrityMode = "none",
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetcher(url, requestInit);
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

  try {
    if (integrity === "strict" && expected) {
      const bytes = await response.arrayBuffer();
      await verifyArtifactBytes(expected, bytes);
      return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    }
    return await response.json();
  } catch (error) {
    if (error instanceof NeuralStockError) throw error;
    throw new NeuralStockError(
      "FETCH_FAILED",
      `Response from ${url} was not valid JSON.`,
      { cause: error },
    );
  }
}

export async function loadRegistry(
  source: RegistrySource,
  options: LoadRegistryOptions = {},
): Promise<RegistryManifest> {
  const fetcher = options.fetch ?? defaultFetch();
  const optionBase = options.baseUrl?.toString();
  const integrity = options.integrity ?? "none";
  let registry: RegistryManifest;
  let documentUrl: string | undefined;

  if (typeof source === "string" || source instanceof URL) {
    const requestUrl = requestedUrl(source);
    registry = assertRegistry(await readJson(requestUrl, fetcher, options.requestInit));
    documentUrl = resolveUrl(requestUrl, optionBase);
  } else {
    registry = assertRegistry(source);
    documentUrl = optionBase === undefined ? undefined : resolveUrl(optionBase);
  }

  if (integrity === "strict") await verifyRegistryRevision(registry);

  setRegistryContext(registry, {
    ...(documentUrl === undefined ? {} : { documentUrl }),
    fetch: fetcher,
    ...(options.requestInit === undefined
      ? {}
      : { requestInit: options.requestInit }),
    integrity,
    assetRequests: new Map(),
  });

  return registry;
}

function normalizeText(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function searchableText(entry: RegistryAssetEntry): string {
  return normalizeText(
    [
      entry.asset.id,
      entry.name,
      entry.description,
      ...entry.semantics.tags,
      ...entry.semantics.categories,
      ...entry.semantics.affordances,
      entry.semantics.placement,
    ].join(" "),
  );
}

function includesEvery(
  haystack: readonly string[],
  needles: readonly string[],
): boolean {
  const normalized = new Set(haystack.map(normalizeText));
  return needles.every((needle) => normalized.has(normalizeText(needle)));
}

function vector3(value: Vector3Value): readonly [number, number, number] {
  return "x" in value ? [value.x, value.y, value.z] : value;
}

function dimensionsWithin(
  dimensions: readonly [number, number, number],
  minimum?: Vector3Value,
  maximum?: Vector3Value,
): boolean {
  const min = minimum === undefined ? undefined : vector3(minimum);
  const max = maximum === undefined ? undefined : vector3(maximum);
  return dimensions.every(
    (value, index) =>
      (min === undefined || value >= min[index]!) &&
      (max === undefined || value <= max[index]!),
  );
}

function assetKey(id: string, version: string): string {
  return `${id}@${version}`;
}

function withdrawnKeys(registry: RegistryManifest): Set<string> {
  return new Set(
    registry.withdrawals.map(({ asset }) => assetKey(asset.id, asset.version)),
  );
}

function latestKeys(registry: RegistryManifest): Set<string> {
  const aliases = new Map(
    registry.aliases.map((alias) => [alias.id, alias.version] as const),
  );
  const counts = new Map<string, number>();
  for (const entry of registry.entries) {
    counts.set(entry.asset.id, (counts.get(entry.asset.id) ?? 0) + 1);
  }

  return new Set(
    registry.entries
      .filter((entry) => {
        const version = aliases.get(entry.asset.id);
        return version === entry.asset.version || (version === undefined && counts.get(entry.asset.id) === 1);
      })
      .map((entry) => assetKey(entry.asset.id, entry.asset.version)),
  );
}

export function searchAssets(
  registry: RegistryManifest,
  search: string | SearchAssetsOptions = {},
): RegistryAssetEntry[] {
  const options: SearchAssetsOptions =
    typeof search === "string" ? { query: search } : search;
  const query = normalizeText(options.query ?? "");
  const tokens = query.split(/\s+/).filter(Boolean);
  const withdrawn = options.include_withdrawn
    ? new Set<string>()
    : withdrawnKeys(registry);
  const latest = options.latest_only ? latestKeys(registry) : undefined;
  const placements =
    options.placement === undefined
      ? undefined
      : new Set(
          typeof options.placement === "string"
            ? [options.placement]
            : options.placement,
        );

  const matches = registryEntries(registry)
    .map((entry, index) => ({ entry, index, text: searchableText(entry) }))
    .filter(({ entry, text }) => {
      const key = assetKey(entry.asset.id, entry.asset.version);
      if (withdrawn.has(key)) return false;
      if (latest && !latest.has(key)) return false;
      if (!tokens.every((token) => text.includes(token))) return false;
      if (options.tags && !includesEvery(entry.semantics.tags, options.tags)) {
        return false;
      }
      if (
        options.categories &&
        !includesEvery(entry.semantics.categories, options.categories)
      ) {
        return false;
      }
      if (options.license && entry.license !== options.license) return false;
      if (
        options.affordances &&
        !includesEvery(entry.semantics.affordances, options.affordances)
      ) {
        return false;
      }
      if (placements && !placements.has(entry.semantics.placement)) return false;
      if (
        options.max_triangles !== undefined &&
        entry.triangle_count > options.max_triangles
      ) {
        return false;
      }
      if (
        !dimensionsWithin(
          entry.bounds_m.dimensions,
          options.min_dimensions_m,
          options.max_dimensions_m,
        )
      ) {
        return false;
      }
      return true;
    })
    .map(({ entry, index, text }) => {
      const normalizedId = normalizeText(entry.asset.id);
      const normalizedName = normalizeText(entry.name);
      let score = 0;
      if (query && normalizedId === query) score += 100;
      if (query && normalizedName === query) score += 80;
      if (query && normalizedName.startsWith(query)) score += 30;
      score += tokens.reduce(
        (sum, token) => sum + (text.includes(token) ? 1 : 0),
        0,
      );
      return { entry, index, score };
    })
    .sort((left, right) => right.score - left.score || left.index - right.index)
    .map(({ entry }) => entry);

  if (options.limit === undefined) return matches;
  return matches.slice(0, Math.max(0, options.limit));
}

/**
 * Resolve static search matches and optionally apply an exact runtime/source
 * byte budget. The v0.2 registry snapshot does not duplicate artifact sizes,
 * so byte filtering necessarily reads each candidate manifest.
 */
export async function searchResolvedAssets(
  registry: RegistryManifest,
  options: SearchResolvedAssetsOptions = {},
): Promise<ResolvedAssetSearchResult[]> {
  const {
    byte_budget_artifact: budgetArtifact = "runtime",
    limit,
    max_bytes: maxBytes,
    resolve,
    ...staticOptions
  } = options;
  const entries = searchAssets(registry, staticOptions);
  const results = await Promise.all(
    entries.map(async (entry) => ({
      entry,
      asset: await resolveAsset(registry, entry, resolve),
    })),
  );
  const withinBudget =
    maxBytes === undefined
      ? results
      : results.filter(
          ({ asset }) => asset.artifacts[budgetArtifact].bytes <= maxBytes,
        );
  return limit === undefined
    ? withinBudget
    : withinBudget.slice(0, Math.max(0, limit));
}

interface ParsedReference {
  id: string;
  version?: string;
}

function parseReference(reference: AssetReference): ParsedReference {
  if (typeof reference !== "string") {
    if ("asset" in reference) {
      return {
        id: reference.asset.id,
        version: reference.asset.version,
      };
    }
    return { id: reference.id, version: reference.version };
  }

  const separator = reference.lastIndexOf("@");
  if (separator > 0 && separator < reference.length - 1) {
    return {
      id: reference.slice(0, separator),
      version: reference.slice(separator + 1),
    };
  }
  return { id: reference };
}

function resolveVersion(
  registry: RegistryManifest,
  id: string,
  requested: string | undefined,
): string {
  if (requested !== undefined && requested !== "latest") return requested;

  const alias = registry.aliases.find(
    (candidate) => candidate.id === id && candidate.alias === "latest",
  );
  if (alias) return alias.version;

  const candidates = registry.entries.filter((entry) => entry.asset.id === id);
  if (requested === undefined && candidates.length === 1) {
    return candidates[0]!.asset.version;
  }

  throw new NeuralStockError(
    "VERSION_NOT_FOUND",
    requested === "latest"
      ? `Asset ${id} has no latest alias in this registry.`
      : `Asset ${id} requires an explicit version because no latest alias is present.`,
  );
}

function withdrawalFor(
  registry: RegistryManifest,
  id: string,
  version: string,
) {
  return registry.withdrawals.find(
    (withdrawal) =>
      withdrawal.asset.id === id && withdrawal.asset.version === version,
  );
}

function assertResolvedIdentity(
  asset: AssetManifest,
  id: string,
  version: string,
): void {
  if (asset.id !== id || asset.version !== version) {
    throw new NeuralStockError(
      "INVALID_ASSET",
      `Manifest identity mismatch: expected ${id}@${version}, received ${asset.id}@${asset.version}.`,
    );
  }
}

export async function resolveAsset(
  registry: RegistryManifest,
  reference: AssetReference,
  options: ResolveAssetOptions = {},
): Promise<AssetManifest> {
  const parsed = parseReference(reference);
  const version = resolveVersion(registry, parsed.id, parsed.version);
  const entry = registry.entries.find(
    (candidate) =>
      candidate.asset.id === parsed.id && candidate.asset.version === version,
  );

  if (!entry) {
    throw new NeuralStockError(
      parsed.version === undefined || parsed.version === "latest"
        ? "ASSET_NOT_FOUND"
        : "VERSION_NOT_FOUND",
      `Asset ${parsed.id}@${version} is not present in this registry.`,
    );
  }

  const withdrawal = withdrawalFor(registry, parsed.id, version);
  if (withdrawal && !options.includeWithdrawn) {
    throw new NeuralStockError(
      "ASSET_NOT_FOUND",
      `Asset ${parsed.id}@${version} was withdrawn for ${withdrawal.reason}.`,
    );
  }

  const context = getRegistryContext(registry);
  const optionBase = options.baseUrl?.toString();
  const effectiveRegistryUrl =
    optionBase === undefined
      ? context?.documentUrl
      : resolveUrl(optionBase, context?.documentUrl);
  const manifestUrl = resolveUrl(
    entry.manifest.uri,
    effectiveRegistryUrl,
    context?.documentUrl,
  );
  const fetcher = options.fetch ?? context?.fetch ?? defaultFetch();
  const requestInit = options.requestInit ?? context?.requestInit;
  const integrity = options.integrity ?? context?.integrity ?? "none";
  const requestCache = context?.assetRequests;
  const requestKey = `${integrity}:${manifestUrl}`;
  let request = requestCache?.get(requestKey);

  if (!request) {
    request = (async () => {
      const asset = assertAsset(
        await readJson(
          manifestUrl,
          fetcher,
          requestInit,
          entry.manifest,
          integrity,
        ),
      );
      assertResolvedIdentity(asset, parsed.id, version);
      setAssetContext(asset, {
        documentUrl: manifestUrl,
        ...(effectiveRegistryUrl === undefined
          ? {}
          : { registryUrl: effectiveRegistryUrl }),
        fetch: fetcher,
        ...(requestInit === undefined ? {} : { requestInit }),
      });
      return asset;
    })();
    requestCache?.set(requestKey, request);
  }

  try {
    return await request;
  } catch (error) {
    requestCache?.delete(requestKey);
    throw error;
  }
}
