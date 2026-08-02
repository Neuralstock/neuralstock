import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const releaseRoot = resolve(
  process.env.NEURALSTOCK_RELEASE_DIR ?? "dist/release",
);
const registryPath = resolve(releaseRoot, "registry.json");

if (!existsSync(registryPath)) {
  process.stdout.write(
    `Skipping Room Zero Playwright: no release at ${registryPath}.\n`,
  );
  process.exit(0);
}

process.stdout.write(
  `Running Room Zero Playwright against release ${releaseRoot}.\n`,
);
const executable = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
const result = spawnSync(
  executable,
  ["--filter", "@neuralstock/room-zero", "test:e2e"],
  {
    env: { ...process.env, NEURALSTOCK_RELEASE_DIR: releaseRoot },
    stdio: "inherit",
  },
);

if (result.error) throw result.error;
process.exit(result.status ?? 1);
