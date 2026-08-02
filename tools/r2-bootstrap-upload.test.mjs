import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";

import {
  keyPolicy,
  preflightRelease,
  uploadRelease,
  validateEndpoint,
  validatePlan,
} from "./r2-bootstrap-upload.mjs";

const projectRoot = new URL("../", import.meta.url);
const releasePlanPath = process.env.NEURALSTOCK_R2_PLAN;
const releaseDirectory = process.env.NEURALSTOCK_RELEASE_DIR;

test(
  "the canonical R2 plan and every release file pass bootstrap preflight",
  {
    skip:
      releasePlanPath && releaseDirectory
        ? false
        : "set NEURALSTOCK_R2_PLAN and NEURALSTOCK_RELEASE_DIR for release integration",
  },
  async () => {
    const rawPlan = JSON.parse(await readFile(releasePlanPath, "utf8"));
    const plan = validatePlan(rawPlan);
    const prepared = await preflightRelease(plan, releaseDirectory, 4);

    assert.equal(prepared.length, rawPlan.items.length);
    assert.equal(prepared.filter((item) => !item.immutable).length, 2);
  },
);

test("only the two registry aliases are mutable", () => {
  assert.deepEqual(keyPolicy("registry.json", "0".repeat(64)), {
    immutable: false,
    requiredContentType: "application/json",
  });
  assert.deepEqual(keyPolicy("snapshots/latest.json", "0".repeat(64)), {
    immutable: false,
    requiredContentType: "application/json",
  });
  assert.equal(keyPolicy("assets/latest.json", "0".repeat(64)), null);
});

test("versioned schemas, profiles, and their licenses are immutable contract keys", () => {
  assert.deepEqual(keyPolicy("v0.2/discovery.schema.json", "0".repeat(64)), {
    immutable: true,
    requiredContentType: "application/schema+json",
    verifyExistingBytes: true,
  });
  assert.deepEqual(keyPolicy("profiles/v0.2/web-v1.json", "0".repeat(64)), {
    immutable: true,
    requiredContentType: "application/json",
    verifyExistingBytes: true,
  });
  for (const key of ["v0.2/LICENSE", "profiles/v0.2/LICENSE"]) {
    assert.deepEqual(keyPolicy(key, "0".repeat(64)), {
      immutable: true,
      requiredContentType: "text/plain",
      verifyExistingBytes: true,
    });
  }
  assert.equal(keyPolicy("v0.1/discovery.schema.json", "0".repeat(64)), null);
  assert.equal(keyPolicy("v0.1/LICENSE", "0".repeat(64)), null);
  assert.equal(keyPolicy("v0.3/discovery.schema.json", "0".repeat(64)), null);
  assert.equal(keyPolicy("v0.3/LICENSE", "0".repeat(64)), null);
  assert.equal(keyPolicy("profiles/v0.2/unreviewed.json", "0".repeat(64)), null);
});

test("the uploader only accepts an unauthenticated loopback endpoint", () => {
  assert.equal(validateEndpoint("http://127.0.0.1:8787/upload").pathname, "/upload");
  assert.throws(() => validateEndpoint("https://assets.neuralstock.ai/upload"), /loopback/);
  assert.throws(() => validateEndpoint("http://user:secret@127.0.0.1:8787/upload"), /loopback/);
});

test("a mutable non-alias plan item is rejected", () => {
  assert.throws(
    () =>
      validatePlan({
        revision: "0".repeat(64),
        items: [
          {
            bytes: 1,
            content_type: "application/json",
            immutable: false,
            key: "assets/latest.json",
            sha256: "0".repeat(64),
          },
        ],
      }),
    /release key policy/,
  );
});

test("a schema plan item must use application/schema+json", () => {
  const revision = "a".repeat(64);
  const sha256 = "b".repeat(64);
  const snapshot = {
    bytes: 1,
    content_type: "application/json",
    immutable: true,
    key: `snapshots/${revision}/registry.json`,
    sha256,
  };
  const aliases = ["registry.json", "snapshots/latest.json"].map((key) => ({
    ...snapshot,
    immutable: false,
    key,
  }));

  assert.throws(
    () =>
      validatePlan({
        revision,
        items: [
          {
            bytes: 1,
            content_type: "application/json",
            immutable: true,
            key: "v0.2/discovery.schema.json",
            sha256: "c".repeat(64),
          },
          snapshot,
          ...aliases,
        ],
      }),
    /release key policy/,
  );
});

test("all immutable uploads finish before the two aliases are sent in order", async () => {
  const directory = await mkdtemp(join(tmpdir(), "neuralstock-r2-bootstrap-upload-"));
  const revision = "a".repeat(64);
  const snapshotBody = Buffer.from('{"revision":"test"}');
  const objectBodies = [Buffer.from("first immutable"), Buffer.from("second immutable")];

  function itemFor(key, body, immutable, contentType = "application/json") {
    return {
      bytes: body.byteLength,
      content_type: contentType,
      immutable,
      key,
      sha256: createHash("sha256").update(body).digest("hex"),
    };
  }

  const objectItems = objectBodies.map((body) => {
    const sha256 = createHash("sha256").update(body).digest("hex");
    return itemFor(`objects/sha256/${sha256.slice(0, 2)}/${sha256}`, body, true, "text/markdown");
  });
  const snapshot = itemFor(`snapshots/${revision}/registry.json`, snapshotBody, true);
  const aliases = [
    itemFor("registry.json", snapshotBody, false),
    itemFor("snapshots/latest.json", snapshotBody, false),
  ];
  const rawItems = [...objectItems, snapshot, ...aliases];

  for (const [index, item] of rawItems.entries()) {
    const body = index < objectBodies.length ? objectBodies[index] : snapshotBody;
    const file = join(directory, ...item.key.split("/"));
    await mkdir(dirname(file), { recursive: true });
    await writeFile(file, body);
  }

  const receivedKeys = [];
  const server = createServer(async (request, response) => {
    const key = request.headers["x-neuralstock-key"];
    receivedKeys.push(key);
    for await (const _chunk of request) {
      // Drain each streaming request before responding.
    }
    if (!key.endsWith("latest.json") && key !== "registry.json") {
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 10));
    }
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ status: key === "registry.json" || key.endsWith("latest.json") ? "updated" : "created" }));
  });

  try {
    await new Promise((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
    const address = server.address();
    assert.notEqual(address, null);
    assert.equal(typeof address, "object");
    const endpoint = new URL(`http://127.0.0.1:${address.port}/upload`);
    const plan = validatePlan({ revision, items: rawItems });

    await uploadRelease({ concurrency: 2, endpoint, plan, root: directory });
    assert.deepEqual(receivedKeys.slice(-2), ["registry.json", "snapshots/latest.json"]);
    assert.equal(
      receivedKeys.slice(0, -2).every((key) => !["registry.json", "snapshots/latest.json"].includes(key)),
      true,
    );
  } finally {
    await new Promise((resolveClose) => server.close(resolveClose));
    await rm(directory, { recursive: true });
  }
});
