import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { loadRegistry } from "@neuralstock/client";
import { describe, expect, it } from "vitest";

const bundledRegistry = fileURLToPath(
  new URL("../public/registry.json", import.meta.url),
);

describe("strict website integrity", () => {
  it("ships a valid empty registry and rejects semantic tampering", async () => {
    const registry = JSON.parse(await readFile(bundledRegistry, "utf8"));

    await expect(
      loadRegistry(registry, { integrity: "strict" }),
    ).resolves.toBe(registry);

    await expect(
      loadRegistry(
        { ...registry, generated_at: "2026-08-01T00:00:01Z" },
        { integrity: "strict" },
      ),
    ).rejects.toMatchObject({ code: "INTEGRITY_MISMATCH" });
  });
});
