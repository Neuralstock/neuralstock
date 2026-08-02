import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

import { build } from "esbuild";

const workerEntry = new URL("../cloudflare/r2-bootstrap/src/index.ts", import.meta.url).pathname;

class FakeR2Bucket {
  objects = new Map();
  putCallCount = 0;

  async put(key, value, options = {}) {
    this.putCallCount += 1;
    if (options.onlyIf?.etagDoesNotMatch === "*" && this.objects.has(key)) {
      return null;
    }

    const bytes = new Uint8Array(await new Response(value).arrayBuffer());
    const actualSha256 = createHash("sha256").update(bytes).digest("hex");
    const expectedSha256 =
      options.sha256 === undefined ? undefined : Buffer.from(options.sha256).toString("hex");
    if (expectedSha256 !== undefined && actualSha256 !== expectedSha256) {
      throw new Error("checksum mismatch");
    }

    const object = {
      key,
      bytes,
      size: bytes.byteLength,
      etag: actualSha256.slice(0, 32),
      checksums: { sha256: options.sha256 },
      customMetadata: options.customMetadata,
      httpMetadata: options.httpMetadata,
    };
    this.objects.set(key, object);
    return object;
  }

  async head(key) {
    return this.objects.get(key) ?? null;
  }

  async get(key) {
    const object = this.objects.get(key);
    if (object === undefined) return null;
    return {
      ...object,
      arrayBuffer: async () => Uint8Array.from(object.bytes).buffer,
    };
  }
}

function uploadRequest(key, body, immutable = true, contentType = "application/json") {
  const bytes = Buffer.from(body);
  const sha256 = createHash("sha256").update(bytes).digest("hex");
  return {
    request: new Request("http://127.0.0.1:8787/upload", {
      method: "PUT",
      body: bytes,
      duplex: "half",
      headers: {
        "Cache-Control": immutable
          ? "public,max-age=31536000,immutable"
          : "public,max-age=60,must-revalidate",
        "Content-Length": String(bytes.byteLength),
        "Content-Type": contentType,
        "X-NeuralStock-Immutable": String(immutable),
        "X-NeuralStock-Key": key,
        "X-NeuralStock-SHA256": sha256,
      },
    }),
    sha256,
  };
}

async function loadWorker() {
  const directory = await mkdtemp(join(tmpdir(), "neuralstock-r2-bootstrap-worker-"));
  const outfile = join(directory, "worker.mjs");
  await build({
    entryPoints: [workerEntry],
    bundle: true,
    format: "esm",
    platform: "browser",
    outfile,
    logLevel: "silent",
  });
  const module = await import(`${pathToFileURL(outfile).href}?test=${Date.now()}`);
  return { directory, worker: module.default };
}

test("the Worker creates immutable objects once and reports matching reruns", async () => {
  const { directory, worker } = await loadWorker();
  try {
    const bucket = new FakeR2Bucket();
    const first = uploadRequest("placeholder", '{"hello":"world"}');
    const key = `objects/sha256/${first.sha256.slice(0, 2)}/${first.sha256}`;

    const created = await worker.fetch(uploadRequest(key, '{"hello":"world"}').request, {
      REGISTRY_BUCKET: bucket,
    });
    assert.equal(created.status, 201);
    assert.equal((await created.json()).status, "created");

    const repeated = await worker.fetch(uploadRequest(key, '{"hello":"world"}').request, {
      REGISTRY_BUCKET: bucket,
    });
    assert.equal(repeated.status, 200);
    assert.equal((await repeated.json()).status, "already-present");
    assert.equal(bucket.putCallCount, 1);
  } finally {
    await rm(directory, { recursive: true });
  }
});

test("the Worker accepts an existing graph object with only an R2 SHA-256 checksum", async () => {
  const { directory, worker } = await loadWorker();
  try {
    const bucket = new FakeR2Bucket();
    const body = "existing-checksum";
    const upload = uploadRequest("placeholder", body, true, "application/x-blender");
    const key = `objects/sha256/${upload.sha256.slice(0, 2)}/${upload.sha256}`;
    const bytes = Buffer.from(body);
    bucket.objects.set(key, {
      key,
      bytes,
      size: bytes.byteLength,
      etag: "r2-checksum-only",
      checksums: {
        sha256: Uint8Array.from(Buffer.from(upload.sha256, "hex")).buffer,
      },
      customMetadata: {},
      httpMetadata: {
        contentType: "application/x-blender",
        cacheControl: "public,max-age=31536000,immutable",
      },
    });

    const response = await worker.fetch(
      uploadRequest(key, body, true, "application/x-blender").request,
      { REGISTRY_BUCKET: bucket },
    );

    assert.equal(response.status, 200);
    assert.equal((await response.json()).status, "already-present");
    assert.equal(bucket.putCallCount, 0);
  } finally {
    await rm(directory, { recursive: true });
  }
});

test("the Worker rejects a graph object without metadata or an R2 checksum", async () => {
  const { directory, worker } = await loadWorker();
  try {
    const bucket = new FakeR2Bucket();
    const body = "unverified-graph";
    const upload = uploadRequest("placeholder", body, true, "application/x-blender");
    const key = `objects/sha256/${upload.sha256.slice(0, 2)}/${upload.sha256}`;
    const bytes = Buffer.from(body);
    bucket.objects.set(key, {
      key,
      bytes,
      size: bytes.byteLength,
      etag: "no-integrity-proof",
      checksums: {},
      customMetadata: {},
      httpMetadata: {
        contentType: "application/x-blender",
        cacheControl: "public,max-age=31536000,immutable",
      },
    });

    const response = await worker.fetch(
      uploadRequest(key, body, true, "application/x-blender").request,
      { REGISTRY_BUCKET: bucket },
    );

    assert.equal(response.status, 409);
    assert.equal(bucket.putCallCount, 0);
  } finally {
    await rm(directory, { recursive: true });
  }
});

test("the Worker rejects a conflicting immutable object", async () => {
  const { directory, worker } = await loadWorker();
  try {
    const bucket = new FakeR2Bucket();
    const upload = uploadRequest("placeholder", "expected");
    const key = `objects/sha256/${upload.sha256.slice(0, 2)}/${upload.sha256}`;
    bucket.objects.set(key, {
      key,
      bytes: Buffer.from("wrong"),
      size: 5,
      etag: "different",
      checksums: {},
      customMetadata: { "neuralstock-sha256": "f".repeat(64) },
      httpMetadata: {
        contentType: "application/json",
        cacheControl: "public,max-age=31536000,immutable",
      },
    });

    const response = await worker.fetch(uploadRequest(key, "expected").request, {
      REGISTRY_BUCKET: bucket,
    });
    assert.equal(response.status, 409);
  } finally {
    await rm(directory, { recursive: true });
  }
});

test("the Worker byte-verifies locked schema contracts without custom metadata", async () => {
  const { directory, worker } = await loadWorker();
  try {
    const bucket = new FakeR2Bucket();
    const body = '{"$id":"https://schemas.neuralstock.ai/v0.2/discovery.schema.json"}';
    const upload = uploadRequest(
      "v0.2/discovery.schema.json",
      body,
      true,
      "application/schema+json",
    );
    const bytes = Buffer.from(body);
    bucket.objects.set("v0.2/discovery.schema.json", {
      key: "v0.2/discovery.schema.json",
      bytes,
      size: bytes.byteLength,
      etag: "locked-schema",
      checksums: {},
      customMetadata: {},
      httpMetadata: {
        contentType: "application/schema+json",
        cacheControl: "public, max-age=31536000, immutable",
      },
    });

    const response = await worker.fetch(upload.request, {
      REGISTRY_BUCKET: bucket,
    });

    assert.equal(response.status, 200);
    assert.equal((await response.json()).status, "already-present");
  } finally {
    await rm(directory, { recursive: true });
  }
});

test("the Worker accepts only immutable plain-text schema license companions", async () => {
  const { directory, worker } = await loadWorker();
  try {
    const bucket = new FakeR2Bucket();
    const body = "MIT License\n\nCopyright (c) 2026 NeuralStock contributors\n";
    for (const key of ["v0.2/LICENSE", "profiles/v0.2/LICENSE"]) {
      const created = await worker.fetch(
        uploadRequest(key, body, true, "text/plain").request,
        { REGISTRY_BUCKET: bucket },
      );
      assert.equal(created.status, 201);

      const repeated = await worker.fetch(
        uploadRequest(key, body, true, "text/plain").request,
        { REGISTRY_BUCKET: bucket },
      );
      assert.equal(repeated.status, 200);
      assert.equal((await repeated.json()).status, "already-present");
    }

    const rejected = await worker.fetch(
      uploadRequest("v0.2/LICENSE", body, true, "application/json").request,
      { REGISTRY_BUCKET: bucket },
    );
    assert.equal(rejected.status, 400);
  } finally {
    await rm(directory, { recursive: true });
  }
});

test("the Worker rejects different bytes for a metadata-less locked contract", async () => {
  const { directory, worker } = await loadWorker();
  try {
    const bucket = new FakeR2Bucket();
    const expected = '{"schema":"expected"}';
    const different = Buffer.from('{"schema":"differnt"}');
    assert.equal(different.byteLength, Buffer.byteLength(expected));
    bucket.objects.set("v0.2/discovery.schema.json", {
      key: "v0.2/discovery.schema.json",
      bytes: different,
      size: different.byteLength,
      etag: "locked-schema",
      checksums: {},
      customMetadata: {},
      httpMetadata: {
        contentType: "application/schema+json",
        cacheControl: "public,max-age=31536000,immutable",
      },
    });

    const response = await worker.fetch(
      uploadRequest(
        "v0.2/discovery.schema.json",
        expected,
        true,
        "application/schema+json",
      ).request,
      { REGISTRY_BUCKET: bucket },
    );

    assert.equal(response.status, 409);
  } finally {
    await rm(directory, { recursive: true });
  }
});

test("the Worker overwrites mutable aliases and refuses non-loopback requests", async () => {
  const { directory, worker } = await loadWorker();
  try {
    const bucket = new FakeR2Bucket();
    const alias = uploadRequest("registry.json", '{"revision":1}', false);
    const updated = await worker.fetch(alias.request, { REGISTRY_BUCKET: bucket });
    assert.equal(updated.status, 200);
    assert.equal((await updated.json()).status, "updated");

    const remote = new Request("https://example.com/upload", { method: "PUT" });
    const rejected = await worker.fetch(remote, { REGISTRY_BUCKET: bucket });
    assert.equal(rejected.status, 403);
  } finally {
    await rm(directory, { recursive: true });
  }
});
