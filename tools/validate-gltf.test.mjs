import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

const execFileAsync = promisify(execFile);
const tool = fileURLToPath(new URL("./validate-gltf.mjs", import.meta.url));

function minimalGlb(document) {
  const json = Buffer.from(JSON.stringify(document), "utf8");
  const paddedLength = Math.ceil(json.length / 4) * 4;
  const paddedJson = Buffer.alloc(paddedLength, 0x20);
  json.copy(paddedJson);

  const header = Buffer.alloc(12);
  header.write("glTF", 0, "ascii");
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(12 + 8 + paddedJson.length, 8);

  const chunkHeader = Buffer.alloc(8);
  chunkHeader.writeUInt32LE(paddedJson.length, 0);
  chunkHeader.writeUInt32LE(0x4e4f534a, 4);
  return Buffer.concat([header, chunkHeader, paddedJson]);
}

async function runTool(bytes) {
  const directory = await mkdtemp(join(tmpdir(), "neuralstock-gltf-validator-"));
  const model = join(directory, "model.glb");
  try {
    await writeFile(model, bytes);
    const { stdout } = await execFileAsync(process.execPath, [tool, model]);
    return JSON.parse(stdout);
  } finally {
    await rm(directory, { recursive: true });
  }
}

test("official validator accepts a minimal GLB without warnings", async () => {
  const report = await runTool(
    minimalGlb({ asset: { version: "2.0" }, scene: 0, scenes: [{}] }),
  );

  assert.equal(report.uri, "model.glb");
  assert.equal(report.issues.numErrors, 0);
  assert.equal(report.issues.numWarnings, 0);
  assert.equal("validatedAt" in report, false);
  assert.match(report.validatorVersion, /^2\./);
});

test("official validator reports malformed glTF content", async () => {
  const report = await runTool(minimalGlb({ asset: { version: "1.0" } }));

  assert.ok(report.issues.numErrors > 0);
  assert.ok(report.issues.messages.some((issue) => issue.severity === 0));
});
