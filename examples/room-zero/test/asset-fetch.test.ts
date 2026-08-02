import { describe, expect, it } from "vitest";
import {
  ASSET_RESPONSE_POLICY_REVISION,
  revisedPublicAssetUrl,
} from "../src/asset-fetch.js";

describe("public asset response-policy cache revision", () => {
  it("revisions public R2 URLs while preserving their existing URL components", () => {
    const revised = new URL(
      revisedPublicAssetUrl(
        "https://assets.neuralstock.ai/objects/sha256/ab/abcdef?download=1#asset",
      )!,
    );

    expect(revised.origin).toBe("https://assets.neuralstock.ai");
    expect(revised.pathname).toBe("/objects/sha256/ab/abcdef");
    expect(revised.searchParams.get("download")).toBe("1");
    expect(revised.searchParams.get("ns-response-policy")).toBe(
      ASSET_RESPONSE_POLICY_REVISION,
    );
    expect(revised.hash).toBe("#asset");
  });

  it("does not rewrite local or third-party registry URLs", () => {
    expect(revisedPublicAssetUrl("/registry.json")).toBeUndefined();
    expect(revisedPublicAssetUrl("https://example.com/registry.json")).toBeUndefined();
  });

  it("replaces an older response-policy revision", () => {
    const revised = new URL(
      revisedPublicAssetUrl(
        new URL(
          "https://assets.neuralstock.ai/registry.json?ns-response-policy=old",
        ),
      )!,
    );

    expect(revised.searchParams.getAll("ns-response-policy")).toEqual([
      ASSET_RESPONSE_POLICY_REVISION,
    ]);
  });
});
