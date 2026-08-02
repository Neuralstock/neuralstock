const IMMUTABLE_CACHE_CONTROL = "public,max-age=31536000,immutable";
const MUTABLE_CACHE_CONTROL = "public,max-age=60,must-revalidate";
const MAX_CONTENT_LENGTH = 5 * 1024 * 1024 * 1024;
const MAX_CONTRACT_CONTENT_LENGTH = 1024 * 1024;

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
const MUTABLE_ALIASES = new Set(["registry.json", "snapshots/latest.json"]);
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const OBJECT_KEY_PATTERN = /^objects\/sha256\/([0-9a-f]{2})\/([0-9a-f]{64})$/;
const MANIFEST_KEY_PATTERN =
  /^assets\/[a-z0-9](?:[a-z0-9_]{0,126}[a-z0-9])?\/(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\/manifest\.json$/;
const SNAPSHOT_KEY_PATTERN = /^snapshots\/[0-9a-f]{64}\/registry\.json$/;
const SCHEMA_KEY_PATTERN = /^v0\.2\/[a-z][a-z0-9.-]*\.schema\.json$/;
const PROFILE_KEY = "profiles/v0.2/web-v1.json";
const LICENSE_KEYS = new Set(["v0.2/LICENSE", "profiles/v0.2/LICENSE"]);

type KeyPolicy = {
  immutable: boolean;
  requiredContentType?: string;
  verifyExistingBytes?: true;
};

type UploadHeaders = {
  key: string;
  sha256: string;
  contentLength: number;
  contentType: string;
  cacheControl: string;
  immutable: boolean;
  verifyExistingBytes: boolean;
};

function jsonResponse(payload: Record<string, unknown>, status: number): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}

function keyPolicy(key: string, sha256: string): KeyPolicy | null {
  if (MUTABLE_ALIASES.has(key)) {
    return { immutable: false, requiredContentType: "application/json" };
  }

  const objectMatch = OBJECT_KEY_PATTERN.exec(key);
  if (objectMatch !== null) {
    const [, prefix, objectSha256] = objectMatch;
    if (objectSha256 === sha256 && objectSha256.startsWith(prefix)) {
      return { immutable: true };
    }
    return null;
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

function parseUploadHeaders(request: Request):
  | { ok: true; value: UploadHeaders }
  | { ok: false; response: Response } {
  const key = request.headers.get("x-neuralstock-key") ?? "";
  const sha256 = request.headers.get("x-neuralstock-sha256") ?? "";
  const immutableHeader = request.headers.get("x-neuralstock-immutable") ?? "";
  const contentLengthHeader = request.headers.get("content-length") ?? "";
  const contentType = request.headers.get("content-type") ?? "";
  const cacheControl = request.headers.get("cache-control") ?? "";

  if (key.length === 0 || key.length > 512 || !SHA256_PATTERN.test(sha256)) {
    return {
      ok: false,
      response: jsonResponse({ error: "Invalid NeuralStock key or SHA-256 header." }, 400),
    };
  }

  if (immutableHeader !== "true" && immutableHeader !== "false") {
    return {
      ok: false,
      response: jsonResponse({ error: "Invalid x-neuralstock-immutable header." }, 400),
    };
  }

  if (!/^[1-9]\d*$/.test(contentLengthHeader)) {
    return {
      ok: false,
      response: jsonResponse({ error: "A positive Content-Length header is required." }, 411),
    };
  }

  const contentLength = Number(contentLengthHeader);
  if (
    !Number.isSafeInteger(contentLength) ||
    contentLength <= 0 ||
    contentLength > MAX_CONTENT_LENGTH
  ) {
    return {
      ok: false,
      response: jsonResponse({ error: "Content-Length is outside the accepted range." }, 413),
    };
  }

  if (!CONTENT_TYPES.has(contentType)) {
    return {
      ok: false,
      response: jsonResponse({ error: "Unsupported Content-Type." }, 415),
    };
  }

  const policy = keyPolicy(key, sha256);
  const immutable = immutableHeader === "true";
  if (
    policy === null ||
    policy.immutable !== immutable ||
    (policy.requiredContentType !== undefined && policy.requiredContentType !== contentType)
  ) {
    return {
      ok: false,
      response: jsonResponse({ error: "The key does not match the NeuralStock release policy." }, 400),
    };
  }

  if (policy.verifyExistingBytes && contentLength > MAX_CONTRACT_CONTENT_LENGTH) {
    return {
      ok: false,
      response: jsonResponse({ error: "Canonical contract exceeds the accepted size." }, 413),
    };
  }

  const expectedCacheControl = immutable ? IMMUTABLE_CACHE_CONTROL : MUTABLE_CACHE_CONTROL;
  if (cacheControl !== expectedCacheControl) {
    return {
      ok: false,
      response: jsonResponse({ error: "Invalid Cache-Control header for this key." }, 400),
    };
  }

  if (request.headers.has("content-encoding") || request.headers.has("content-range")) {
    return {
      ok: false,
      response: jsonResponse({ error: "Encoded and partial upload bodies are not accepted." }, 400),
    };
  }

  return {
    ok: true,
    value: {
      key,
      sha256,
      contentLength,
      contentType,
      cacheControl,
      immutable,
      verifyExistingBytes: policy.verifyExistingBytes === true,
    },
  };
}

function sha256Bytes(hex: string): ArrayBuffer {
  const bytes = new Uint8Array(32);
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes.buffer;
}

function bytesToHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function normalizedCacheControl(value: string): string {
  return value
    .split(",")
    .map((directive) => directive.trim())
    .join(",");
}

async function existingObjectMatches(
  bucket: R2Bucket,
  object: R2Object,
  upload: UploadHeaders,
): Promise<boolean> {
  const metadataSha256 = object.customMetadata?.["neuralstock-sha256"]?.toLowerCase();
  const checksumSha256 = object.checksums.sha256;
  const metadataMatches = metadataSha256 === upload.sha256;
  const checksumMatches =
    checksumSha256 !== undefined && bytesToHex(checksumSha256) === upload.sha256;

  if (metadataSha256 !== undefined && !metadataMatches) {
    return false;
  }
  if (checksumSha256 !== undefined && !checksumMatches) {
    return false;
  }

  const contentType = object.httpMetadata?.contentType?.split(";", 1)[0]?.trim().toLowerCase();
  const cacheControl = object.httpMetadata?.cacheControl;
  if (
    object.size !== upload.contentLength ||
    contentType !== upload.contentType.toLowerCase() ||
    cacheControl === undefined ||
    normalizedCacheControl(cacheControl) !== normalizedCacheControl(upload.cacheControl)
  ) {
    return false;
  }

  if (!upload.verifyExistingBytes) {
    return metadataMatches || checksumMatches;
  }

  const existing = await bucket.get(upload.key);
  if (existing === null || existing.size !== upload.contentLength) {
    return false;
  }
  const bytes = await existing.arrayBuffer();
  if (bytes.byteLength !== upload.contentLength) {
    return false;
  }
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return bytesToHex(digest) === upload.sha256;
}

async function responseForExistingObject(
  bucket: R2Bucket,
  upload: UploadHeaders,
): Promise<Response | null> {
  const existing = await bucket.head(upload.key);
  if (existing === null) {
    return null;
  }
  if (await existingObjectMatches(bucket, existing, upload)) {
    return jsonResponse(
      {
        status: "already-present",
        key: upload.key,
        sha256: upload.sha256,
        bytes: existing.size,
        etag: existing.etag,
      },
      200,
    );
  }
  return jsonResponse(
    {
      error: "An immutable object already exists with different content or metadata.",
      key: upload.key,
    },
    409,
  );
}

async function storeUpload(request: Request, env: Env, upload: UploadHeaders): Promise<Response> {
  if (request.body === null) {
    return jsonResponse({ error: "An upload body is required." }, 400);
  }

  const putOptions = {
    httpMetadata: {
      cacheControl: upload.cacheControl,
      contentType: upload.contentType,
    },
    customMetadata: {
      "neuralstock-sha256": upload.sha256,
    },
    sha256: sha256Bytes(upload.sha256),
  };

  if (!upload.immutable) {
    const stored = await env.REGISTRY_BUCKET.put(upload.key, request.body, putOptions);
    return jsonResponse(
      {
        status: "updated",
        key: upload.key,
        sha256: upload.sha256,
        bytes: stored.size,
        etag: stored.etag,
      },
      200,
    );
  }

  const existingResponse = await responseForExistingObject(env.REGISTRY_BUCKET, upload);
  if (existingResponse !== null) {
    return existingResponse;
  }

  const stored = await env.REGISTRY_BUCKET.put(upload.key, request.body, {
    ...putOptions,
    onlyIf: { etagDoesNotMatch: "*" },
  });

  if (stored !== null) {
    return jsonResponse(
      {
        status: "created",
        key: upload.key,
        sha256: upload.sha256,
        bytes: stored.size,
        etag: stored.etag,
      },
      201,
    );
  }

  return (
    (await responseForExistingObject(env.REGISTRY_BUCKET, upload)) ??
    jsonResponse({ error: "R2 did not return the immutable object after a collision." }, 409)
  );
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (!LOOPBACK_HOSTS.has(url.hostname)) {
      return jsonResponse({ error: "This bootstrap bridge accepts loopback requests only." }, 403);
    }
    if (url.pathname !== "/upload" || url.search !== "") {
      return jsonResponse({ error: "Not found." }, 404);
    }
    if (request.method !== "PUT") {
      const response = jsonResponse({ error: "Method not allowed." }, 405);
      response.headers.set("Allow", "PUT");
      return response;
    }

    const parsed = parseUploadHeaders(request);
    if (!parsed.ok) {
      return parsed.response;
    }

    try {
      return await storeUpload(request, env, parsed.value);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error(
        JSON.stringify({
          message: "R2 bootstrap upload failed",
          key: parsed.value.key,
          error: message,
        }),
      );
      return jsonResponse({ error: "R2 rejected the upload." }, 422);
    }
  },
} satisfies ExportedHandler<Env>;
