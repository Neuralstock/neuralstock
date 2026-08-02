import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const packageDirectory = dirname(fileURLToPath(new URL("../package.json", import.meta.url)));
const temporaryRoot = await mkdtemp(join(tmpdir(), "neuralstock-client-package-"));

function run(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    encoding: "utf8",
    env: { ...process.env, NO_COLOR: "1" },
  });
  if (result.status !== 0) {
    throw new Error(
      `${command} ${args.join(" ")} failed.\n${result.stdout}\n${result.stderr}`,
    );
  }
  return result.stdout;
}

try {
  const packOutput = run(
    "npm",
    ["pack", "--json", "--ignore-scripts", "--pack-destination", temporaryRoot],
    packageDirectory,
  );
  const [packed] = JSON.parse(packOutput);
  assert.equal(packed.name, "@neuralstock/client");
  const packedFiles = new Set(packed.files.map(({ path }) => path));
  for (const required of ["LICENSE", "README.md", "dist/index.js", "dist/index.d.ts"]) {
    assert.ok(packedFiles.has(required), `package is missing ${required}`);
  }
  assert.ok(
    [...packedFiles].every((path) => !path.startsWith("src/") && !path.startsWith("test/")),
    "source and test files must not leak into the npm package",
  );

  const consumer = join(temporaryRoot, "consumer");
  await mkdir(consumer);
  await writeFile(
    join(consumer, "package.json"),
    JSON.stringify({ name: "neuralstock-client-smoke", private: true, type: "module" }),
  );
  run(
    "npm",
    [
      "install",
      "--ignore-scripts",
      "--no-audit",
      "--no-fund",
      "--no-package-lock",
      join(temporaryRoot, packed.filename),
    ],
    consumer,
  );

  const entry = join(
    consumer,
    "node_modules",
    "@neuralstock",
    "client",
    "dist",
    "index.js",
  );
  const installed = await import(pathToFileURL(entry).href);
  assert.equal(
    installed.NEURALSTOCK_REGISTRY_URL,
    "https://assets.neuralstock.ai/registry.json",
  );
  assert.equal(typeof installed.loadCanonicalRegistry, "function");
  assert.equal(typeof installed.loadDiscovery, "function");
  assert.equal(typeof installed.fetchArtifact, "function");

  const installedManifest = JSON.parse(
    await readFile(
      join(consumer, "node_modules", "@neuralstock", "client", "package.json"),
      "utf8",
    ),
  );
  assert.equal(
    installedManifest.repository.url,
    "https://github.com/Neuralstock/neuralstock",
  );
  assert.equal(installedManifest.repository.directory, "packages/client");
} finally {
  await rm(temporaryRoot, { recursive: true, force: true });
}
