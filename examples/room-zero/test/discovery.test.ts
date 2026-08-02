import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const canonicalDiscovery = fileURLToPath(
  new URL("../../../discovery/neuralstock.json", import.meta.url),
);
const publicDiscovery = fileURLToPath(
  new URL("../public/.well-known/neuralstock.json", import.meta.url),
);

describe("machine discovery mirror", () => {
  it("matches the canonical discovery document byte for byte", async () => {
    const [canonical, published] = await Promise.all([
      readFile(canonicalDiscovery),
      readFile(publicDiscovery),
    ]);
    expect(published.equals(canonical)).toBe(true);
  });
});
