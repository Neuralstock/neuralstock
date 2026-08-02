import { NeuralStockError } from "./errors.js";
import type { AssetArtifact, RegistryManifest } from "./types.js";

export type IntegrityBytes = ArrayBuffer | Uint8Array;

function byteView(value: IntegrityBytes): Uint8Array<ArrayBuffer> {
  if (value instanceof ArrayBuffer) return new Uint8Array(value);
  const copy = new Uint8Array(value.byteLength);
  copy.set(value);
  return copy;
}

function hex(value: ArrayBuffer): string {
  return Array.from(new Uint8Array(value), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

export async function sha256Hex(value: string | IntegrityBytes): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    throw new NeuralStockError(
      "INTEGRITY_UNAVAILABLE",
      "SHA-256 verification requires the Web Crypto API.",
    );
  }

  const bytes =
    typeof value === "string" ? new TextEncoder().encode(value) : byteView(value);
  return hex(await subtle.digest("SHA-256", bytes));
}

function isBoundsFloat(path: readonly string[]): boolean {
  const field = path.at(-2);
  return (
    path.includes("bounds_m") &&
    (field === "minimum" || field === "maximum" || field === "dimensions")
  );
}

function canonicalNumber(value: number, path: readonly string[]): string {
  if (!Number.isFinite(value)) {
    throw new NeuralStockError(
      "INTEGRITY_MISMATCH",
      "Registry revision input contains a non-finite number.",
    );
  }

  if (isBoundsFloat(path) && Number.isInteger(value)) {
    return Object.is(value, -0) ? "-0.0" : `${value}.0`;
  }

  const encoded = JSON.stringify(value);
  if (encoded === undefined) {
    throw new NeuralStockError(
      "INTEGRITY_MISMATCH",
      "Registry revision input contains an unsupported number.",
    );
  }
  // Python's JSON encoder pads a one-digit negative exponent (1e-07). The
  // public revision algorithm is defined by the Python reference publisher.
  return encoded.replace(/e([+-])(\d)$/u, "e$10$2");
}

function canonicalJson(value: unknown, path: readonly string[] = []): string {
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return canonicalNumber(value, path);
  if (Array.isArray(value)) {
    return `[${value
      .map((item, index) => canonicalJson(item, [...path, String(index)]))
      .join(",")}]`;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map(
        (key) =>
          `${JSON.stringify(key)}:${canonicalJson(record[key], [...path, key])}`,
      )
      .join(",")}}`;
  }
  throw new NeuralStockError(
    "INTEGRITY_MISMATCH",
    "Registry revision input contains a non-JSON value.",
  );
}

function revisionPayload(registry: RegistryManifest): object {
  return {
    generated_at: registry.generated_at,
    profiles: registry.profiles,
    entries: registry.entries,
    aliases: registry.aliases,
    withdrawals: registry.withdrawals,
  };
}

export async function verifyRegistryRevision(
  registry: RegistryManifest,
): Promise<void> {
  const actual = await registryRevision(registry);
  if (actual !== registry.revision) {
    throw new NeuralStockError(
      "INTEGRITY_MISMATCH",
      `Registry revision mismatch: expected ${registry.revision}, calculated ${actual}.`,
    );
  }
}

export function registryRevision(registry: RegistryManifest): Promise<string> {
  return sha256Hex(canonicalJson(revisionPayload(registry)));
}

export async function verifyArtifactBytes(
  artifact: AssetArtifact,
  value: IntegrityBytes,
): Promise<void> {
  const bytes = byteView(value);
  if (bytes.byteLength !== artifact.bytes) {
    throw new NeuralStockError(
      "INTEGRITY_MISMATCH",
      `${artifact.file_name} byte length mismatch: expected ${artifact.bytes}, received ${bytes.byteLength}.`,
    );
  }

  const actual = await sha256Hex(bytes);
  if (actual !== artifact.sha256) {
    throw new NeuralStockError(
      "INTEGRITY_MISMATCH",
      `${artifact.file_name} SHA-256 mismatch: expected ${artifact.sha256}, calculated ${actual}.`,
    );
  }
}
