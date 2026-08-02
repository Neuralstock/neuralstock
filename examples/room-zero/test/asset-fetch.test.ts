import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ASSET_RESPONSE_POLICY_REVISION,
  fetchPublicAsset,
  revisedPublicAssetUrl,
} from "../src/asset-fetch.js";

afterEach(() => {
  vi.unstubAllGlobals();
});

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

  it("passes a revisioned public URL to fetch", async () => {
    const fetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => new Response("ok"),
    );
    vi.stubGlobal("fetch", fetch);

    await fetchPublicAsset(
      "https://assets.neuralstock.ai/objects/sha256/ab/abcdef",
      { credentials: "omit", mode: "cors" },
    );

    expect(fetch).toHaveBeenCalledOnce();
    const [input, init] = fetch.mock.calls[0]!;
    expect(new URL(String(input)).searchParams.get("ns-response-policy")).toBe(
      ASSET_RESPONSE_POLICY_REVISION,
    );
    expect(init).toEqual({ credentials: "omit", mode: "cors" });
  });

  it("preserves public GET Request options while changing only its URL", async () => {
    const fetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => new Response("ok"),
    );
    vi.stubGlobal("fetch", fetch);
    const controller = new AbortController();
    const request = new Request(
      "https://assets.neuralstock.ai/assets/chair_01/1.0.1/manifest.json",
      {
        cache: "no-cache",
        credentials: "omit",
        headers: { "x-neuralstock-test": "preserved" },
        method: "GET",
        signal: controller.signal,
      },
    );

    await fetchPublicAsset(request, { redirect: "error" });

    const [input, init] = fetch.mock.calls[0]!;
    expect(input).toBeInstanceOf(Request);
    const revised = input as Request;
    expect(new URL(revised.url).searchParams.get("ns-response-policy")).toBe(
      ASSET_RESPONSE_POLICY_REVISION,
    );
    expect(revised.method).toBe("GET");
    expect(revised.cache).toBe("no-cache");
    expect(revised.credentials).toBe("omit");
    expect(revised.headers.get("x-neuralstock-test")).toBe("preserved");
    expect(revised.signal.aborted).toBe(false);
    expect(init).toEqual({ redirect: "error" });
  });

  it("passes through third-party and non-read requests", async () => {
    const fetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => new Response("ok"),
    );
    vi.stubGlobal("fetch", fetch);
    const thirdParty = "https://example.com/registry.json";
    const upload = new Request("https://assets.neuralstock.ai/upload", {
      body: "payload",
      method: "POST",
    });

    await fetchPublicAsset(thirdParty);
    await fetchPublicAsset(upload);

    expect(fetch.mock.calls[0]?.[0]).toBe(thirdParty);
    expect(fetch.mock.calls[1]?.[0]).toBe(upload);
  });
});
