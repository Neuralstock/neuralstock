import type { FetchLike } from "@neuralstock/client";

const PUBLIC_ASSET_ORIGIN = "https://assets.neuralstock.ai";

/**
 * Bump only when response policy on immutable public objects changes in a way
 * that requires browsers to obtain fresh response headers.
 *
 * The v1 migration follows the launch CORS correction. Some browsers cached
 * the earlier CORS-less response headers under year-long immutable URLs. The
 * query parameter changes the HTTP cache key; artifact bytes are still checked
 * against their declared byte length and SHA-256 before use.
 */
export const ASSET_RESPONSE_POLICY_REVISION = "cors-v1";

export function revisedPublicAssetUrl(input: string | URL | Request): string | undefined {
  const raw = input instanceof Request ? input.url : input.toString();
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return undefined;
  }

  if (url.origin !== PUBLIC_ASSET_ORIGIN) return undefined;
  url.searchParams.set("ns-response-policy", ASSET_RESPONSE_POLICY_REVISION);
  return url.href;
}

/** Fetch public NeuralStock assets through the current response-policy cache key. */
export const fetchPublicAsset: FetchLike = (input, init) => {
  const method = (init?.method ?? (input instanceof Request ? input.method : "GET"))
    .toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    return globalThis.fetch(input, init);
  }

  const revisedUrl = revisedPublicAssetUrl(input);
  if (revisedUrl === undefined) return globalThis.fetch(input, init);

  if (input instanceof Request) {
    return globalThis.fetch(new Request(revisedUrl, input), init);
  }
  return globalThis.fetch(revisedUrl, init);
};
