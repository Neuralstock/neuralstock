export type Vector3Tuple = readonly [number, number, number];
export type QuaternionTuple = readonly [number, number, number, number];

export interface Vector3Object {
  x: number;
  y: number;
  z: number;
}

/** Accepted by viewer helpers; public v0.2 manifests use Vector3Tuple. */
export type Vector3Value = Vector3Tuple | Vector3Object;

export interface AssetReferenceValue {
  id: string;
  version: string;
}

export interface AssetBounds {
  minimum: Vector3Tuple;
  maximum: Vector3Tuple;
  dimensions: Vector3Tuple;
}

export interface RuntimeCoordinateSystem {
  unit: "meter";
  meters_per_unit: 1;
  up_axis: "Y";
  forward_axis: "+Z";
  handedness: "right";
  space: "asset-local";
}

export interface AssetSemantics {
  categories: readonly string[];
  tags: readonly string[];
  affordances: readonly string[];
  placement: "floor" | "wall" | "ceiling" | "surface" | "free";
}

export interface AssetAnchor {
  name: string;
  position_m: Vector3Tuple;
  rotation_xyzw: QuaternionTuple;
  semantic?: string;
}

export interface AssetCollision {
  name: string;
  kind: "box";
  bounds_m: AssetBounds;
  vertex_count: number;
  triangle_count: number;
}

export type AssetArtifactRole =
  | "source"
  | "runtime"
  | "preview"
  | "provenance"
  | "inspection"
  | "build_receipt"
  | "manifest"
  | "collision"
  | "lod"
  | "texture"
  | "registry_snapshot"
  | "evidence"
  | "build_evidence";

export interface AssetArtifact {
  role: AssetArtifactRole;
  file_name: string;
  media_type: string;
  sha256: string;
  bytes: number;
  uri: string;
}

export interface AssetArtifacts {
  source: AssetArtifact;
  runtime: AssetArtifact;
  provenance: AssetArtifact;
  inspection: AssetArtifact;
  build_receipt: AssetArtifact;
  previews: readonly AssetArtifact[];
  optional?: readonly AssetArtifact[];
}

export interface AssetGeometry {
  vertex_count: number;
  triangle_count: number;
  material_count: number;
  texture_count: number;
}

export interface FloatParameter {
  type: "float";
  default: number;
  minimum: number;
  maximum: number;
  agent_safe: true;
  label?: string;
  description?: string;
  step?: number;
  unit?: "meter" | "radian" | "ratio" | "unitless";
}

export interface IntegerParameter {
  type: "integer";
  default: number;
  minimum: number;
  maximum: number;
  agent_safe: true;
  label?: string;
  description?: string;
  step?: number;
  unit?: "meter" | "radian" | "unitless";
}

export interface BooleanParameter {
  type: "boolean";
  default: boolean;
  agent_safe: true;
  label?: string;
  description?: string;
}

export interface EnumParameter {
  type: "enum";
  default: string;
  options: readonly string[];
  agent_safe: true;
  label?: string;
  description?: string;
}

export type AssetParameter =
  | FloatParameter
  | IntegerParameter
  | BooleanParameter
  | EnumParameter;

export interface AssetSourceGenerator {
  geometry_node_group: string | null;
  parameters: Readonly<Record<string, AssetParameter>>;
}

export interface AssetManifest {
  $schema: "https://schemas.neuralstock.ai/v0.2/asset.schema.json";
  schema_version: "0.2";
  document_type: "asset";
  generated: true;
  id: string;
  version: string;
  name: string;
  description: string;
  publication_status: "published";
  published_at: string;
  license: "CC0-1.0";
  target_profile: "web-v1";
  coordinate_system: RuntimeCoordinateSystem;
  semantics: AssetSemantics;
  bounds_m: AssetBounds;
  geometry: AssetGeometry;
  source_generator: AssetSourceGenerator;
  anchors: readonly AssetAnchor[];
  collisions: readonly AssetCollision[];
  build_key: string;
  artifacts: AssetArtifacts;
}

export interface RegistryAssetEntry {
  asset: AssetReferenceValue;
  name: string;
  description: string;
  license: "CC0-1.0";
  target_profile: "web-v1";
  coordinate_system: RuntimeCoordinateSystem;
  semantics: AssetSemantics;
  bounds_m: AssetBounds;
  triangle_count: number;
  manifest: AssetArtifact;
}

export interface RegistryAlias {
  id: string;
  alias: "latest";
  version: string;
}

export interface RegistryWithdrawal {
  asset: AssetReferenceValue;
  reason: "rights" | "security" | "malformed" | "other";
  recorded_at: string;
  notice_uri: string;
}

export interface RegistryManifest {
  $schema: "https://schemas.neuralstock.ai/v0.2/registry.schema.json";
  schema_version: "0.2";
  document_type: "registry";
  generated: true;
  revision: string;
  generated_at: string;
  profiles: readonly "web-v1"[];
  entries: readonly RegistryAssetEntry[];
  aliases: readonly RegistryAlias[];
  withdrawals: readonly RegistryWithdrawal[];
}

export type FetchLike = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export interface NeuralStockDiscoveryDocument {
  $schema: "https://schemas.neuralstock.ai/v0.2/discovery.schema.json";
  schema_version: "0.2";
  document_type: "discovery";
  site: string;
  asset_origin: string;
  schema_origin: string;
  registry: {
    canonical: string;
    latest_snapshot: string;
    immutable_snapshot_template: string;
  };
  license_policy: readonly ["CC0-1.0"];
  clients: {
    npm: string;
    python: string;
  };
}

export interface LoadDiscoveryOptions {
  fetch?: FetchLike;
  requestInit?: RequestInit;
}

export type RegistrySource = RegistryManifest | string | URL;

/**
 * `strict` verifies the registry revision and, when resolving a manifest,
 * checks the exact byte length and SHA-256 declared by its registry entry.
 */
export type IntegrityMode = "none" | "strict";

export interface LoadRegistryOptions {
  fetch?: FetchLike;
  baseUrl?: string | URL;
  requestInit?: RequestInit;
  integrity?: IntegrityMode;
}

export interface SearchAssetsOptions {
  query?: string;
  tags?: readonly string[];
  categories?: readonly string[];
  affordances?: readonly string[];
  placement?: AssetSemantics["placement"] | readonly AssetSemantics["placement"][];
  license?: "CC0-1.0";
  max_triangles?: number;
  min_dimensions_m?: Vector3Value;
  max_dimensions_m?: Vector3Value;
  /** Return only the version selected by each asset's `latest` alias. */
  latest_only?: boolean;
  limit?: number;
  include_withdrawn?: boolean;
}

export interface SearchResolvedAssetsOptions extends SearchAssetsOptions {
  /** Maximum bytes for the selected runtime/source artifact. */
  max_bytes?: number;
  /** Artifact budgeted by `max_bytes`; defaults to `runtime`. */
  byte_budget_artifact?: "runtime" | "source";
  /** Options forwarded to each manifest resolution. */
  resolve?: ResolveAssetOptions;
}

export interface ResolvedAssetSearchResult {
  entry: RegistryAssetEntry;
  asset: AssetManifest;
}

export type AssetReference = string | RegistryAssetEntry | AssetReferenceValue;

export interface ResolveAssetOptions {
  fetch?: FetchLike;
  baseUrl?: string | URL;
  requestInit?: RequestInit;
  includeWithdrawn?: boolean;
  integrity?: IntegrityMode;
}

export interface ArtifactUrlOptions {
  baseUrl?: string | URL;
}

export interface FetchArtifactOptions extends ArtifactUrlOptions {
  fetch?: FetchLike;
  requestInit?: RequestInit;
}
