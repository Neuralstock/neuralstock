import { NeuralStockError } from "./errors.js";
import type {
  AssetArtifact,
  AssetManifest,
  FetchLike,
  RegistryAssetEntry,
  RegistryManifest,
} from "./types.js";

interface RegistryContext {
  documentUrl?: string;
  fetch: FetchLike;
  requestInit?: RequestInit;
  integrity: "none" | "strict";
  assetRequests: Map<string, Promise<AssetManifest>>;
}

interface AssetContext {
  documentUrl?: string;
  registryUrl?: string;
  fetch?: FetchLike;
  requestInit?: RequestInit;
}

const registryContexts = new WeakMap<RegistryManifest, RegistryContext>();
const assetContexts = new WeakMap<AssetManifest, AssetContext>();

export function defaultFetch(): FetchLike {
  if (typeof globalThis.fetch !== "function") {
    throw new NeuralStockError(
      "FETCH_FAILED",
      "No fetch implementation is available; pass options.fetch explicitly.",
    );
  }

  return globalThis.fetch.bind(globalThis);
}

function ambientBaseUrl(): string | undefined {
  return typeof globalThis.location?.href === "string"
    ? globalThis.location.href
    : undefined;
}

export function resolveUrl(
  reference: string,
  ...bases: Array<string | URL | undefined>
): string {
  try {
    return new URL(reference).href;
  } catch {
    for (const base of bases) {
      if (base === undefined) continue;
      try {
        return new URL(reference, base).href;
      } catch {
        // Try the next usable base.
      }
    }

    const ambient = ambientBaseUrl();
    return ambient === undefined ? reference : new URL(reference, ambient).href;
  }
}

export function setRegistryContext(
  registry: RegistryManifest,
  context: RegistryContext,
): void {
  registryContexts.set(registry, context);
}

export function getRegistryContext(
  registry: RegistryManifest,
): RegistryContext | undefined {
  return registryContexts.get(registry);
}

export function setAssetContext(
  asset: AssetManifest,
  context: AssetContext,
): void {
  assetContexts.set(asset, context);
}

export function getAssetContext(
  asset: AssetManifest,
): AssetContext | undefined {
  return assetContexts.get(asset);
}

export function registryEntries(
  registry: RegistryManifest,
): RegistryAssetEntry[] {
  return [...registry.entries];
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const SHA256_PATTERN = /^[a-f0-9]{64}$/;
const ARTIFACT_ROLES: ReadonlySet<string> = new Set([
  "source",
  "runtime",
  "preview",
  "provenance",
  "inspection",
  "build_receipt",
  "manifest",
  "collision",
  "lod",
  "texture",
  "registry_snapshot",
  "evidence",
  "build_evidence",
]);
const OPTIONAL_ARTIFACT_ROLES: ReadonlySet<string> = new Set([
  "collision",
  "lod",
  "texture",
]);
const PLACEMENTS: ReadonlySet<string> = new Set([
  "floor",
  "wall",
  "ceiling",
  "surface",
  "free",
]);
const WITHDRAWAL_REASONS: ReadonlySet<string> = new Set([
  "rights",
  "security",
  "malformed",
  "other",
]);

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isIntegerAtLeast(value: unknown, minimum: number): value is number {
  return Number.isInteger(value) && typeof value === "number" && value >= minimum;
}

function isStringArray(value: unknown, minimumLength = 0): value is string[] {
  return (
    Array.isArray(value) &&
    value.length >= minimumLength &&
    value.every((item) => typeof item === "string")
  );
}

function isVector3(
  value: unknown,
): value is readonly [number, number, number] {
  return (
    Array.isArray(value) &&
    value.length === 3 &&
    value.every(isFiniteNumber)
  );
}

function isAssetReference(value: unknown): boolean {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    isNonEmptyString(value.version)
  );
}

function isRuntimeCoordinateSystem(value: unknown): boolean {
  return (
    isRecord(value) &&
    value.unit === "meter" &&
    value.meters_per_unit === 1 &&
    value.up_axis === "Y" &&
    value.forward_axis === "+Z" &&
    value.handedness === "right" &&
    value.space === "asset-local"
  );
}

function isSemantics(value: unknown): boolean {
  return (
    isRecord(value) &&
    isStringArray(value.categories, 1) &&
    isStringArray(value.tags) &&
    isStringArray(value.affordances) &&
    typeof value.placement === "string" &&
    PLACEMENTS.has(value.placement)
  );
}

function isBounds(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const minimum = value.minimum;
  const maximum = value.maximum;
  const dimensions = value.dimensions;
  if (
    !isVector3(minimum) ||
    !isVector3(maximum) ||
    !isVector3(dimensions) ||
    !dimensions.every((component) => component > 0)
  ) {
    return false;
  }
  return minimum.every((component, index) => {
    const expected = maximum[index]! - component;
    const actual = dimensions[index]!;
    const tolerance = 1e-9 * Math.max(1, Math.abs(expected), Math.abs(actual));
    return expected > 0 && Math.abs(expected - actual) <= tolerance;
  });
}

function isGeometry(value: unknown): boolean {
  return (
    isRecord(value) &&
    isIntegerAtLeast(value.vertex_count, 1) &&
    isIntegerAtLeast(value.triangle_count, 1) &&
    isIntegerAtLeast(value.material_count, 0) &&
    isIntegerAtLeast(value.texture_count, 0)
  );
}

function isQuaternion(value: unknown): boolean {
  if (
    !Array.isArray(value) ||
    value.length !== 4 ||
    !value.every(
      (component) => isFiniteNumber(component) && Math.abs(component) <= 1,
    )
  ) {
    return false;
  }
  const lengthSquared = value.reduce<number>(
    (total, component) => total + component * component,
    0,
  );
  return Math.abs(lengthSquared - 1) <= 1e-4;
}

function isAnchor(value: unknown): boolean {
  return (
    isRecord(value) &&
    isNonEmptyString(value.name) &&
    isVector3(value.position_m) &&
    isQuaternion(value.rotation_xyzw) &&
    (value.semantic === undefined || typeof value.semantic === "string")
  );
}

function isCollision(value: unknown): boolean {
  return (
    isRecord(value) &&
    isNonEmptyString(value.name) &&
    value.kind === "box" &&
    isBounds(value.bounds_m) &&
    isIntegerAtLeast(value.vertex_count, 0) &&
    isIntegerAtLeast(value.triangle_count, 0)
  );
}

function hasOptionalString(value: Record<string, unknown>, key: string): boolean {
  return value[key] === undefined || typeof value[key] === "string";
}

function isParameterDefinition(value: unknown): boolean {
  if (
    !isRecord(value) ||
    value.agent_safe !== true ||
    !hasOptionalString(value, "label") ||
    !hasOptionalString(value, "description")
  ) {
    return false;
  }

  if (value.type === "float" || value.type === "integer") {
    const defaultValue = value.default;
    const minimum = value.minimum;
    const maximum = value.maximum;
    if (
      !isFiniteNumber(defaultValue) ||
      !isFiniteNumber(minimum) ||
      !isFiniteNumber(maximum) ||
      minimum > maximum ||
      defaultValue < minimum ||
      defaultValue > maximum
    ) {
      return false;
    }
    if (
      value.type === "integer" &&
      ![defaultValue, minimum, maximum].every((item) => Number.isInteger(item))
    ) {
      return false;
    }
    if (
      value.step !== undefined &&
      (!isFiniteNumber(value.step) ||
        value.step <= 0 ||
        (value.type === "integer" && !Number.isInteger(value.step)))
    ) {
      return false;
    }
    const units =
      value.type === "float"
        ? ["meter", "radian", "ratio", "unitless"]
        : ["meter", "radian", "unitless"];
    return (
      value.unit === undefined ||
      (typeof value.unit === "string" && units.includes(value.unit))
    );
  }

  if (value.type === "boolean") {
    return typeof value.default === "boolean";
  }

  if (value.type === "enum") {
    return (
      typeof value.default === "string" &&
      isStringArray(value.options, 2) &&
      value.options.includes(value.default)
    );
  }

  return false;
}

function isSourceGenerator(value: unknown): boolean {
  return (
    isRecord(value) &&
    (value.geometry_node_group === null ||
      typeof value.geometry_node_group === "string") &&
    isRecord(value.parameters) &&
    Object.values(value.parameters).every(isParameterDefinition)
  );
}

function isArtifact(value: unknown): value is AssetArtifact {
  return (
    isRecord(value) &&
    typeof value.role === "string" &&
    ARTIFACT_ROLES.has(value.role) &&
    isNonEmptyString(value.file_name) &&
    isNonEmptyString(value.media_type) &&
    typeof value.sha256 === "string" &&
    SHA256_PATTERN.test(value.sha256) &&
    isIntegerAtLeast(value.bytes, 1) &&
    isNonEmptyString(value.uri)
  );
}

function isExpectedArtifact(
  value: unknown,
  role: AssetArtifact["role"],
  fileName?: string,
  mediaType?: string,
): value is AssetArtifact {
  return (
    isArtifact(value) &&
    value.role === role &&
    (fileName === undefined || value.file_name === fileName) &&
    (mediaType === undefined || value.media_type === mediaType)
  );
}

function isAssetArtifacts(value: unknown): boolean {
  if (!isRecord(value)) return false;
  if (
    !isExpectedArtifact(value.source, "source", "source.blend") ||
    !isExpectedArtifact(
      value.runtime,
      "runtime",
      "model.glb",
      "model/gltf-binary",
    ) ||
    !isExpectedArtifact(
      value.provenance,
      "provenance",
      "provenance.json",
      "application/json",
    ) ||
    !isExpectedArtifact(
      value.inspection,
      "inspection",
      "inspection.json",
      "application/json",
    ) ||
    !isExpectedArtifact(
      value.build_receipt,
      "build_receipt",
      "build-receipt.json",
      "application/json",
    ) ||
    !Array.isArray(value.previews) ||
    value.previews.length === 0 ||
    !value.previews.every((item) => isExpectedArtifact(item, "preview"))
  ) {
    return false;
  }
  return (
    value.optional === undefined ||
    (Array.isArray(value.optional) &&
      value.optional.every(
        (item) => isArtifact(item) && OPTIONAL_ARTIFACT_ROLES.has(item.role),
      ))
  );
}

function isRegistryEntry(value: unknown): value is RegistryAssetEntry {
  return (
    isRecord(value) &&
    isAssetReference(value.asset) &&
    isNonEmptyString(value.name) &&
    isNonEmptyString(value.description) &&
    value.license === "CC0-1.0" &&
    value.target_profile === "web-v1" &&
    isRuntimeCoordinateSystem(value.coordinate_system) &&
    isSemantics(value.semantics) &&
    isBounds(value.bounds_m) &&
    isIntegerAtLeast(value.triangle_count, 1) &&
    isExpectedArtifact(
      value.manifest,
      "manifest",
      "asset.json",
      "application/json",
    )
  );
}

function isRegistryAlias(value: unknown): boolean {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    value.alias === "latest" &&
    isNonEmptyString(value.version)
  );
}

function isRegistryWithdrawal(value: unknown): boolean {
  return (
    isRecord(value) &&
    isAssetReference(value.asset) &&
    typeof value.reason === "string" &&
    WITHDRAWAL_REASONS.has(value.reason) &&
    isNonEmptyString(value.recorded_at) &&
    isNonEmptyString(value.notice_uri)
  );
}

export function assertRegistry(value: unknown): RegistryManifest {
  if (
    !isRecord(value) ||
    value.$schema !==
      "https://schemas.neuralstock.ai/v0.2/registry.schema.json" ||
    value.schema_version !== "0.2" ||
    value.document_type !== "registry" ||
    value.generated !== true ||
    typeof value.revision !== "string" ||
    !SHA256_PATTERN.test(value.revision) ||
    !isNonEmptyString(value.generated_at) ||
    !Array.isArray(value.profiles) ||
    value.profiles.length === 0 ||
    !value.profiles.every((profile) => profile === "web-v1") ||
    !Array.isArray(value.entries) ||
    !value.entries.every(isRegistryEntry) ||
    !Array.isArray(value.aliases) ||
    !value.aliases.every(isRegistryAlias) ||
    !Array.isArray(value.withdrawals) ||
    !value.withdrawals.every(isRegistryWithdrawal)
  ) {
    throw new NeuralStockError(
      "INVALID_REGISTRY",
      "Registry must be a generated NeuralStock v0.2 document with entries, aliases, and withdrawals arrays.",
    );
  }

  return value as unknown as RegistryManifest;
}

export function assertAsset(value: unknown): AssetManifest {
  if (
    !isRecord(value) ||
    value.$schema !== "https://schemas.neuralstock.ai/v0.2/asset.schema.json" ||
    value.schema_version !== "0.2" ||
    value.document_type !== "asset" ||
    value.generated !== true ||
    !isNonEmptyString(value.id) ||
    !isNonEmptyString(value.version) ||
    !isNonEmptyString(value.name) ||
    !isNonEmptyString(value.description) ||
    value.publication_status !== "published" ||
    !isNonEmptyString(value.published_at) ||
    value.license !== "CC0-1.0" ||
    value.target_profile !== "web-v1" ||
    !isRuntimeCoordinateSystem(value.coordinate_system) ||
    !isSemantics(value.semantics) ||
    !isBounds(value.bounds_m) ||
    !isGeometry(value.geometry) ||
    !isSourceGenerator(value.source_generator) ||
    !Array.isArray(value.anchors) ||
    !value.anchors.every(isAnchor) ||
    !Array.isArray(value.collisions) ||
    !value.collisions.every(isCollision) ||
    typeof value.build_key !== "string" ||
    !SHA256_PATTERN.test(value.build_key) ||
    !isAssetArtifacts(value.artifacts)
  ) {
    throw new NeuralStockError(
      "INVALID_ASSET",
      "Asset manifest must be a generated NeuralStock v0.2 asset with bounds, semantics, and canonical artifacts.",
    );
  }

  return value as unknown as AssetManifest;
}
