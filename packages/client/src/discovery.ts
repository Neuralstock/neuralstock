import { NeuralStockError } from "./errors.js";
import { defaultFetch } from "./internal.js";
import { loadRegistry } from "./registry.js";
import type {
  LoadDiscoveryOptions,
  LoadRegistryOptions,
  NeuralStockDiscoveryDocument,
  RegistryManifest,
} from "./types.js";

export const NEURALSTOCK_SITE_URL = "https://neuralstock.ai/";
export const NEURALSTOCK_ASSET_ORIGIN = "https://assets.neuralstock.ai";
export const NEURALSTOCK_SCHEMA_ORIGIN = "https://schemas.neuralstock.ai";
export const NEURALSTOCK_REGISTRY_URL = `${NEURALSTOCK_ASSET_ORIGIN}/registry.json`;
export const NEURALSTOCK_LATEST_SNAPSHOT_URL =
  `${NEURALSTOCK_ASSET_ORIGIN}/snapshots/latest.json`;
export const NEURALSTOCK_DISCOVERY_URL =
  "https://neuralstock.ai/.well-known/neuralstock.json";

const SHA256_PATTERN = /^[a-f0-9]{64}$/u;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function assertDiscovery(value: unknown): NeuralStockDiscoveryDocument {
  if (!isRecord(value)) {
    throw new NeuralStockError(
      "INVALID_DISCOVERY",
      "Discovery response must be a NeuralStock v0.2 document.",
    );
  }
  const registry = value.registry;
  const clients = value.clients;
  if (
    value.$schema !==
      "https://schemas.neuralstock.ai/v0.2/discovery.schema.json" ||
    value.schema_version !== "0.2" ||
    value.document_type !== "discovery" ||
    !isNonEmptyString(value.site) ||
    !isNonEmptyString(value.asset_origin) ||
    !isNonEmptyString(value.schema_origin) ||
    !isRecord(registry) ||
    !isNonEmptyString(registry.canonical) ||
    !isNonEmptyString(registry.latest_snapshot) ||
    !isNonEmptyString(registry.immutable_snapshot_template) ||
    !Array.isArray(value.license_policy) ||
    value.license_policy.length !== 1 ||
    value.license_policy[0] !== "CC0-1.0" ||
    !isRecord(clients) ||
    !isNonEmptyString(clients.npm) ||
    !isNonEmptyString(clients.python)
  ) {
    throw new NeuralStockError(
      "INVALID_DISCOVERY",
      "Discovery response must be a NeuralStock v0.2 document.",
    );
  }
  return value as unknown as NeuralStockDiscoveryDocument;
}

export function registrySnapshotUrl(
  registryOrRevision: RegistryManifest | string,
  assetOrigin = NEURALSTOCK_ASSET_ORIGIN,
): string {
  const revision =
    typeof registryOrRevision === "string"
      ? registryOrRevision
      : registryOrRevision.revision;
  if (!SHA256_PATTERN.test(revision)) {
    throw new TypeError("Registry revision must be a lowercase SHA-256 digest.");
  }
  return new URL(`/snapshots/${revision}/registry.json`, assetOrigin).href;
}

export function loadCanonicalRegistry(
  options: LoadRegistryOptions = {},
): Promise<RegistryManifest> {
  return loadRegistry(NEURALSTOCK_REGISTRY_URL, options);
}

export function loadDiscovery(
  options?: LoadDiscoveryOptions,
): Promise<NeuralStockDiscoveryDocument>;
export function loadDiscovery(
  source: string | URL,
  options?: LoadDiscoveryOptions,
): Promise<NeuralStockDiscoveryDocument>;
export async function loadDiscovery(
  sourceOrOptions: string | URL | LoadDiscoveryOptions = {},
  explicitOptions: LoadDiscoveryOptions = {},
): Promise<NeuralStockDiscoveryDocument> {
  const hasSource =
    typeof sourceOrOptions === "string" || sourceOrOptions instanceof URL;
  const source = hasSource ? sourceOrOptions : NEURALSTOCK_DISCOVERY_URL;
  const options = hasSource ? explicitOptions : sourceOrOptions;
  const fetcher = options.fetch ?? defaultFetch();
  const url = source instanceof URL ? source.href : source;
  let response: Response;
  try {
    response = await fetcher(url, options.requestInit);
  } catch (error) {
    throw new NeuralStockError(
      "FETCH_FAILED",
      `Could not fetch discovery document ${url}.`,
      { cause: error },
    );
  }
  if (!response.ok) {
    throw new NeuralStockError(
      "FETCH_FAILED",
      `Could not fetch discovery document ${url}: ${response.status} ${response.statusText}`.trim(),
    );
  }
  try {
    return assertDiscovery(await response.json());
  } catch (error) {
    if (error instanceof NeuralStockError) throw error;
    throw new NeuralStockError(
      "INVALID_DISCOVERY",
      `Response from ${url} was not a valid discovery document.`,
      { cause: error },
    );
  }
}
