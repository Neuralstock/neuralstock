#!/usr/bin/env node

import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { isAbsolute, relative, resolve, sep } from "node:path";
import { Readable } from "node:stream";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";

const DEFAULT_ENDPOINT = "http://127.0.0.1:8787/upload";
const DEFAULT_PLAN = "work/final-room-zero-v01-current/r2-plan.json";
const DEFAULT_ROOT = "dist/release";
const DEFAULT_CONCURRENCY = 4;
const MAX_CONCURRENCY = 16;
const MAX_CONTRACT_CONTENT_LENGTH = 1024 * 1024;

const IMMUTABLE_CACHE_CONTROL = "public,max-age=31536000,immutable";
const MUTABLE_CACHE_CONTROL = "public,max-age=60,must-revalidate";
const ALIAS_KEYS = ["registry.json", "snapshots/latest.json"];
const ALIAS_KEY_SET = new Set(ALIAS_KEYS);
const CONTENT_TYPES = new Set([
  "application/json",
  "application/schema+json",
  "application/x-blender",
  "image/png",
  "model/gltf-binary",
  "text/plain",
  "text/markdown",
]);
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]", "::1"]);
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const OBJECT_KEY_PATTERN = /^objects\/sha256\/([0-9a-f]{2})\/([0-9a-f]{64})$/;
const MANIFEST_KEY_PATTERN =
  /^assets\/[a-z0-9](?:[a-z0-9_]{0,126}[a-z0-9])?\/(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\/manifest\.json$/;
const SNAPSHOT_KEY_PATTERN = /^snapshots\/([0-9a-f]{64})\/registry\.json$/;
const SCHEMA_KEY_PATTERN = /^v0\.2\/[a-z][a-z0-9.-]*\.schema\.json$/;
const PROFILE_KEY = "profiles/v0.2/web-v1.json";
const LICENSE_KEYS = new Set(["v0.2/LICENSE", "profiles/v0.2/LICENSE"]);

function fail(message) {
  throw new Error(message);
}

function isPlainObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function keyPolicy(key, sha256) {
  if (ALIAS_KEY_SET.has(key)) {
    return { immutable: false, requiredContentType: "application/json" };
  }

  const objectMatch = OBJECT_KEY_PATTERN.exec(key);
  if (objectMatch !== null) {
    const [, prefix, objectSha256] = objectMatch;
    return objectSha256 === sha256 && objectSha256.startsWith(prefix)
      ? { immutable: true }
      : null;
  }

  if (MANIFEST_KEY_PATTERN.test(key) || SNAPSHOT_KEY_PATTERN.test(key)) {
    return { immutable: true, requiredContentType: "application/json" };
  }

  if (SCHEMA_KEY_PATTERN.test(key)) {
    return {
      immutable: true,
      requiredContentType: "application/schema+json",
      verifyExistingBytes: true,
    };
  }

  if (key === PROFILE_KEY) {
    return {
      immutable: true,
      requiredContentType: "application/json",
      verifyExistingBytes: true,
    };
  }

  if (LICENSE_KEYS.has(key)) {
    return {
      immutable: true,
      requiredContentType: "text/plain",
      verifyExistingBytes: true,
    };
  }

  return null;
}

function validateItem(value, index) {
  if (!isPlainObject(value)) {
    fail(`Plan item ${index} must be an object.`);
  }

  const { bytes, content_type: contentType, immutable, key, sha256 } = value;
  if (!Number.isSafeInteger(bytes) || bytes <= 0) {
    fail(`Plan item ${index} has invalid bytes.`);
  }
  if (typeof contentType !== "string" || !CONTENT_TYPES.has(contentType)) {
    fail(`Plan item ${index} has an unsupported content_type.`);
  }
  if (typeof immutable !== "boolean" || typeof key !== "string" || typeof sha256 !== "string") {
    fail(`Plan item ${index} has invalid field types.`);
  }
  if (key.length === 0 || key.length > 512 || !SHA256_PATTERN.test(sha256)) {
    fail(`Plan item ${index} has an invalid key or SHA-256.`);
  }

  const policy = keyPolicy(key, sha256);
  if (
    policy === null ||
    policy.immutable !== immutable ||
    (policy.requiredContentType !== undefined && policy.requiredContentType !== contentType)
  ) {
    fail(`Plan item ${index} violates the NeuralStock release key policy: ${key}`);
  }
  if (policy.verifyExistingBytes && bytes > MAX_CONTRACT_CONTENT_LENGTH) {
    fail(`Plan item ${index} canonical contract exceeds the accepted size.`);
  }

  return { bytes, contentType, immutable, key, sha256 };
}

export function validatePlan(value) {
  if (!isPlainObject(value) || !SHA256_PATTERN.test(value.revision) || !Array.isArray(value.items)) {
    fail("R2 plan must contain a SHA-256 revision and an items array.");
  }
  if (value.items.length === 0) {
    fail("R2 plan contains no items.");
  }

  const items = value.items.map(validateItem);
  const byKey = new Map();
  for (const item of items) {
    if (byKey.has(item.key)) {
      fail(`R2 plan contains a duplicate key: ${item.key}`);
    }
    byKey.set(item.key, item);
  }

  const mutableItems = items.filter((item) => !item.immutable);
  if (
    mutableItems.length !== ALIAS_KEYS.length ||
    ALIAS_KEYS.some((key) => !byKey.has(key) || byKey.get(key).immutable)
  ) {
    fail("The only mutable plan items must be registry.json and snapshots/latest.json.");
  }

  const snapshotKey = `snapshots/${value.revision}/registry.json`;
  const snapshot = byKey.get(snapshotKey);
  if (snapshot === undefined || !snapshot.immutable) {
    fail(`R2 plan is missing its immutable registry snapshot: ${snapshotKey}`);
  }

  for (const aliasKey of ALIAS_KEYS) {
    const alias = byKey.get(aliasKey);
    if (
      alias.sha256 !== snapshot.sha256 ||
      alias.bytes !== snapshot.bytes ||
      alias.contentType !== snapshot.contentType
    ) {
      fail(`${aliasKey} does not match the immutable registry snapshot.`);
    }
  }

  return { revision: value.revision, items };
}

export function validateEndpoint(value) {
  let endpoint;
  try {
    endpoint = new URL(value);
  } catch {
    fail(`Invalid upload endpoint: ${value}`);
  }

  if (
    endpoint.protocol !== "http:" ||
    !LOOPBACK_HOSTS.has(endpoint.hostname) ||
    endpoint.pathname !== "/upload" ||
    endpoint.search !== "" ||
    endpoint.hash !== "" ||
    endpoint.username !== "" ||
    endpoint.password !== ""
  ) {
    fail("The endpoint must be an unauthenticated http:// loopback URL ending in /upload.");
  }
  return endpoint;
}

function resolveReleaseFile(root, key) {
  const file = resolve(root, ...key.split("/"));
  const pathFromRoot = relative(root, file);
  if (pathFromRoot === "" || pathFromRoot === ".." || pathFromRoot.startsWith(`..${sep}`) || isAbsolute(pathFromRoot)) {
    fail(`Release key escapes the release root: ${key}`);
  }
  return file;
}

async function hashFile(file) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(file)) {
    hash.update(chunk);
  }
  return hash.digest("hex");
}

export async function runBounded(items, concurrency, operation) {
  const results = new Array(items.length);
  let nextIndex = 0;

  async function runner() {
    while (nextIndex < items.length) {
      const index = nextIndex;
      nextIndex += 1;
      results[index] = await operation(items[index], index);
    }
  }

  const runnerCount = Math.min(concurrency, items.length);
  await Promise.all(Array.from({ length: runnerCount }, () => runner()));
  return results;
}

export async function preflightRelease(plan, root, concurrency = DEFAULT_CONCURRENCY) {
  const releaseRoot = resolve(root);
  return runBounded(plan.items, concurrency, async (item) => {
    const file = resolveReleaseFile(releaseRoot, item.key);
    let fileStat;
    try {
      fileStat = await stat(file);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      fail(`Cannot read release file for ${item.key}: ${detail}`);
    }
    if (!fileStat.isFile() || fileStat.size !== item.bytes) {
      fail(`Release file size mismatch for ${item.key}.`);
    }

    const actualSha256 = await hashFile(file);
    if (actualSha256 !== item.sha256) {
      fail(`Release file SHA-256 mismatch for ${item.key}.`);
    }
    return { ...item, file };
  });
}

async function uploadItem(endpoint, item) {
  const body = Readable.toWeb(createReadStream(item.file));
  const cacheControl = item.immutable ? IMMUTABLE_CACHE_CONTROL : MUTABLE_CACHE_CONTROL;
  const response = await fetch(endpoint, {
    method: "PUT",
    body,
    duplex: "half",
    headers: {
      "Cache-Control": cacheControl,
      "Content-Length": String(item.bytes),
      "Content-Type": item.contentType,
      "X-NeuralStock-Immutable": String(item.immutable),
      "X-NeuralStock-Key": item.key,
      "X-NeuralStock-SHA256": item.sha256,
    },
  });

  const responseText = await response.text();
  let payload;
  try {
    payload = JSON.parse(responseText);
  } catch {
    fail(`Upload bridge returned a non-JSON response for ${item.key} (${response.status}).`);
  }

  if (!response.ok || !isPlainObject(payload) || typeof payload.status !== "string") {
    const detail = isPlainObject(payload) && typeof payload.error === "string" ? payload.error : responseText;
    fail(`Upload failed for ${item.key} (${response.status}): ${detail}`);
  }
  if (!new Set(["created", "already-present", "updated"]).has(payload.status)) {
    fail(`Upload bridge returned an unknown status for ${item.key}: ${payload.status}`);
  }

  process.stdout.write(`[${payload.status}] ${item.key}\n`);
  return payload.status;
}

export async function uploadRelease({ concurrency, endpoint, plan, root }) {
  const prepared = await preflightRelease(plan, root, concurrency);
  const immutableItems = prepared.filter((item) => item.immutable);
  const aliasByKey = new Map(prepared.filter((item) => !item.immutable).map((item) => [item.key, item]));

  process.stdout.write(`Validated ${prepared.length} release files before upload.\n`);
  const immutableStatuses = await runBounded(immutableItems, concurrency, (item) =>
    uploadItem(endpoint, item),
  );

  const aliasStatuses = [];
  for (const aliasKey of ALIAS_KEYS) {
    aliasStatuses.push(await uploadItem(endpoint, aliasByKey.get(aliasKey)));
  }

  const statuses = [...immutableStatuses, ...aliasStatuses];
  const summary = {
    total: statuses.length,
    created: statuses.filter((status) => status === "created").length,
    alreadyPresent: statuses.filter((status) => status === "already-present").length,
    updated: statuses.filter((status) => status === "updated").length,
  };
  process.stdout.write(`${JSON.stringify(summary)}\n`);
  return summary;
}

function usage() {
  return `Usage: node tools/r2-bootstrap-upload.mjs [options]

Options:
  --endpoint <url>      Local bridge endpoint (default: ${DEFAULT_ENDPOINT})
  --root <directory>    Release root (default: ${DEFAULT_ROOT})
  --plan <file>         R2 plan JSON (default: ${DEFAULT_PLAN})
  --concurrency <n>     Concurrent immutable uploads, 1-${MAX_CONCURRENCY} (default: ${DEFAULT_CONCURRENCY})
  --help                Show this help
`;
}

async function main(argv = process.argv.slice(2)) {
  const { values } = parseArgs({
    args: argv,
    allowPositionals: false,
    strict: true,
    options: {
      endpoint: { type: "string", default: DEFAULT_ENDPOINT },
      root: { type: "string", default: DEFAULT_ROOT },
      plan: { type: "string", default: DEFAULT_PLAN },
      concurrency: { type: "string", default: String(DEFAULT_CONCURRENCY) },
      help: { type: "boolean", short: "h", default: false },
    },
  });

  if (values.help) {
    process.stdout.write(usage());
    return;
  }

  const concurrency = Number(values.concurrency);
  if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > MAX_CONCURRENCY) {
    fail(`--concurrency must be an integer from 1 to ${MAX_CONCURRENCY}.`);
  }

  const endpoint = validateEndpoint(values.endpoint);
  const planPath = resolve(values.plan);
  const planText = await readFile(planPath, "utf8");
  let rawPlan;
  try {
    rawPlan = JSON.parse(planText);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    fail(`Cannot parse R2 plan ${planPath}: ${detail}`);
  }
  const plan = validatePlan(rawPlan);
  await uploadRelease({ concurrency, endpoint, plan, root: values.root });
}

const invokedPath = process.argv[1] === undefined ? "" : resolve(process.argv[1]);
if (invokedPath === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`r2-bootstrap-upload: ${message}\n`);
    process.exitCode = 1;
  });
}
