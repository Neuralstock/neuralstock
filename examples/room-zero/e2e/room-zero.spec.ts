import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const screenshotDirectory = fileURLToPath(
  new URL("../../../output/playwright/screenshots", import.meta.url),
);

interface BrowserFailures {
  consoleErrors: string[];
  pageErrors: string[];
  requestFailures: string[];
  responseErrors: string[];
  successfulResponses: string[];
}

function observeFailures(page: Page): BrowserFailures {
  const failures: BrowserFailures = {
    consoleErrors: [],
    pageErrors: [],
    requestFailures: [],
    responseErrors: [],
    successfulResponses: [],
  };
  page.on("console", (message) => {
    if (message.type() === "error") failures.consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => failures.pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    failures.requestFailures.push(
      `${request.method()} ${request.url()}: ${request.failure()?.errorText ?? "failed"}`,
    );
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      failures.responseErrors.push(`${response.status()} ${response.url()}`);
    } else if (response.ok()) {
      failures.successfulResponses.push(response.url());
    }
  });
  return failures;
}

async function expectCanvasMatchesViewport(page: Page): Promise<void> {
  const viewport = page.locator("#viewport");
  const canvas = page.locator("#viewport canvas");
  await expect(canvas).toBeVisible();
  const [viewportBox, canvasBox] = await Promise.all([
    viewport.boundingBox(),
    canvas.boundingBox(),
  ]);
  expect(viewportBox).not.toBeNull();
  expect(canvasBox).not.toBeNull();
  expect(canvasBox!.width).toBeCloseTo(viewportBox!.width, 0);
  expect(canvasBox!.height).toBeCloseTo(viewportBox!.height, 0);
  const backingSize = await canvas.evaluate((element) => {
    const canvasElement = element as HTMLCanvasElement;
    return { height: canvasElement.height, width: canvasElement.width };
  });
  expect(backingSize.width).toBeGreaterThan(1);
  expect(backingSize.height).toBeGreaterThan(1);
}

async function exerciseContextRecovery(page: Page): Promise<void> {
  const supported = await page.locator("#viewport canvas").evaluate((element) => {
    const canvas = element as HTMLCanvasElement;
    const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    const extension = context?.getExtension("WEBGL_lose_context");
    if (!extension) return false;
    (canvas as HTMLCanvasElement & { neuralstockContextLoss?: WEBGL_lose_context })
      .neuralstockContextLoss = extension;
    extension.loseContext();
    return true;
  });
  expect(supported, "Chromium should expose WEBGL_lose_context").toBe(true);
  await expect(page.locator("#status")).toContainText("WebGL context lost");

  await page.locator("#viewport canvas").evaluate((element) => {
    const canvas = element as HTMLCanvasElement & {
      neuralstockContextLoss?: WEBGL_lose_context;
    };
    canvas.neuralstockContextLoss?.restoreContext();
  });
  await expect(page.locator("#status")).toContainText("WebGL context restored");
  await expect
    .poll(() =>
      page.locator("#viewport canvas").evaluate((element) => {
        const canvas = element as HTMLCanvasElement;
        const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
        return context?.isContextLost() ?? true;
      }),
    )
    .toBe(false);
}

test("loads a published GLB and survives viewer interactions", async ({ page }, testInfo) => {
  test.setTimeout(60_000);
  const failures = observeFailures(page);
  const selectedAsset = process.env.NEURALSTOCK_E2E_ASSET;
  const query = new URLSearchParams({ registry: "/registry.json" });
  if (selectedAsset) query.set("asset", selectedAsset);

  const documentResponse = await page.goto(`/?${query.toString()}`);
  expect(documentResponse).not.toBeNull();
  expect(documentResponse!.headers()["content-security-policy"]).toContain(
    "connect-src 'self' blob: https://assets.neuralstock.ai",
  );
  const status = page.locator("#status");
  await expect(status).toContainText(
    /loaded from verified runtime bytes(?: and framed from published bounds)?\./,
  );
  await expect(status).toHaveAttribute("data-tone", "ok");
  await expect(page.locator("#empty-state")).toBeHidden();

  const select = page.locator("#asset-select");
  await expect(select).toBeEnabled();
  const identity = await select.inputValue();
  expect(identity).toMatch(/^[a-z][a-z0-9_]*@\d+\.\d+\.\d+$/);
  if (selectedAsset?.endsWith("@latest")) {
    expect(identity.startsWith(`${selectedAsset.slice(0, -"@latest".length)}@`)).toBe(true);
  } else if (selectedAsset) {
    expect(identity).toBe(selectedAsset);
  }

  const artifactUrls = await page.evaluate(async (resolvedIdentity) => {
    const registryResponse = await fetch("/registry.json");
    if (!registryResponse.ok) throw new Error("Could not inspect the E2E registry.");
    const registry = (await registryResponse.json()) as {
      entries: Array<{
        asset: { id: string; version: string };
        manifest: { uri: string };
      }>;
    };
    const separator = resolvedIdentity.lastIndexOf("@");
    const id = resolvedIdentity.slice(0, separator);
    const version = resolvedIdentity.slice(separator + 1);
    const entry = registry.entries.find(
      (candidate) => candidate.asset.id === id && candidate.asset.version === version,
    );
    if (!entry) throw new Error(`Registry entry missing for ${resolvedIdentity}.`);
    const manifestResponse = await fetch(entry.manifest.uri);
    if (!manifestResponse.ok) throw new Error(`Could not inspect ${entry.manifest.uri}.`);
    const manifest = (await manifestResponse.json()) as {
      artifacts: { runtime: { uri: string }; source: { uri: string } };
    };
    return {
      runtime: new URL(manifest.artifacts.runtime.uri, window.location.href).href,
      source: new URL(manifest.artifacts.source.uri, window.location.href).href,
    };
  }, identity);
  expect(
    failures.successfulResponses,
    `the GLB request ${artifactUrls.runtime} should complete before the viewer reports loaded`,
  ).toContain(artifactUrls.runtime);

  const metadata = page.locator("#asset-metadata");
  await expect(metadata).toBeVisible();
  await expect(metadata.locator("dd").first()).toHaveText(identity);
  await expect(metadata).toContainText("CC0-1.0");
  await expect(metadata).toContainText("Collisions");

  const selectedCard = page.locator(`.asset-card[data-asset-ref="${identity}"]`);
  await expect(selectedCard).toBeVisible();
  await expect(selectedCard.locator(".asset-card-name")).toHaveAttribute(
    "href",
    new RegExp(`/asset/.+/\\d+\\.\\d+\\.\\d+$`),
  );
  await selectedCard.scrollIntoViewIfNeeded();
  await expect(selectedCard).toHaveAttribute("data-manifest-state", "loaded");
  await selectedCard.locator(".asset-download-panel summary").click();
  const expectedFileStem = identity.replace("@", "-");
  const glbDownload = selectedCard.getByRole("button", {
    name: /Download .* GLB/,
  });
  const blendDownload = selectedCard.getByRole("button", {
    name: /Download .* BLEND/,
  });
  const previewDownload = selectedCard.getByRole("button", {
    name: /Download .* Preview PNG/,
  });
  const manifestDownload = selectedCard.getByRole("button", {
    name: /Download .* Manifest JSON/,
  });
  const provenanceDownload = selectedCard.getByRole("button", {
    name: /Download .* Provenance JSON/,
  });
  const validationDownload = selectedCard.getByRole("button", {
    name: /Download .* Validation JSON/,
  });
  await expect(glbDownload).toBeEnabled();
  await expect(blendDownload).toBeEnabled();
  await expect(previewDownload).toBeEnabled();
  await expect(manifestDownload).toBeEnabled();
  await expect(provenanceDownload).toBeEnabled();
  await expect(validationDownload).toBeEnabled();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    glbDownload.click(),
  ]);
  expect(download.suggestedFilename()).toBe(`${expectedFileStem}.glb`);
  await expect(page.locator("#download-status")).toContainText(
    `${expectedFileStem}.glb passed SHA-256 verification and is ready.`,
  );
  await expect(glbDownload).toHaveAttribute("data-verified", "true");

  const tamperedDownloads: string[] = [];
  page.on("download", (candidate) => tamperedDownloads.push(candidate.suggestedFilename()));
  await page.route(artifactUrls.source, async (route) => {
    const response = await route.fetch();
    const bytes = Buffer.from(await response.body());
    const midpoint = Math.floor(bytes.length / 2);
    bytes[midpoint] = bytes[midpoint]! ^ 1;
    await route.fulfill({ response, body: bytes });
  });
  await blendDownload.click();
  await expect(page.locator("#download-status")).toContainText("SHA-256 mismatch");
  await expect(blendDownload).toHaveAttribute("data-verified", "false");
  expect(tamperedDownloads, "tampered bytes must never reach a browser download").toEqual([]);

  const bounds = page.getByLabel("Bounds", { exact: true });
  const anchors = page.getByLabel("Anchors", { exact: true });
  const collision = page.getByLabel("Collision", { exact: true });
  await expect(bounds).toBeEnabled();
  await expect(anchors).toBeEnabled();
  await expect(collision).toBeEnabled();
  await bounds.check();
  await anchors.check();
  await collision.check();
  await expect(bounds).toBeChecked();
  await expect(anchors).toBeChecked();
  await expect(collision).toBeChecked();

  await expectCanvasMatchesViewport(page);
  await mkdir(screenshotDirectory, { recursive: true });
  // Capture the bounded WebGL experience rather than the full mission page.
  // Large full-page mobile captures can exhaust Chromium's SwiftShader surface
  // and lose the WebGL context before the recovery assertion runs.
  await page.locator(".viewer-frame").screenshot({
    path: `${screenshotDirectory}/${testInfo.project.name}.png`,
  });

  const originalViewport = page.viewportSize();
  expect(originalViewport).not.toBeNull();
  await page.setViewportSize({
    height: Math.max(480, originalViewport!.height - 96),
    width: Math.max(320, originalViewport!.width - 72),
  });
  await expectCanvasMatchesViewport(page);
  await page.setViewportSize(originalViewport!);
  await expectCanvasMatchesViewport(page);

  await exerciseContextRecovery(page);
  await expect(metadata.locator("dd").first()).toHaveText(identity);

  expect(failures.consoleErrors, "console errors").toEqual([]);
  expect(failures.pageErrors, "uncaught page errors").toEqual([]);
  expect(failures.requestFailures, "failed requests").toEqual([]);
  expect(failures.responseErrors, "HTTP error responses").toEqual([]);
});

test("rejects a semantically tampered registry before resolving assets", async ({ page }) => {
  const downstreamRequests: string[] = [];
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (
      /^\/assets\/[^/]+\/[^/]+\/manifest\.json$/.test(pathname) ||
      pathname.startsWith("/objects/")
    ) {
      downstreamRequests.push(request.url());
    }
  });
  await page.route(
    (url) => url.pathname === "/registry.json",
    async (route) => {
      const response = await route.fetch();
      const registry = (await response.json()) as Record<string, unknown>;
      await route.fulfill({
        response,
        json: { ...registry, generated_at: "2026-08-01T00:00:01Z" },
      });
    },
  );

  await page.goto("/?registry=/registry.json");

  await expect(page.locator("#status")).toContainText("Registry revision mismatch");
  await expect(page.locator("#catalog-status")).toHaveText("Live registry unavailable.");
  expect(downstreamRequests).toEqual([]);
});

test("rejects a tampered manifest before fetching its runtime", async ({ page }) => {
  let selectedRuntimeUrl: string | undefined;
  const objectRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/objects/")) {
      objectRequests.push(request.url());
    }
  });
  await page.route(
    "**/assets/procedural_table_01/1.0.1/manifest.json",
    async (route) => {
      const response = await route.fetch();
      const manifest = (await response.json()) as {
        name: string;
        artifacts: { runtime: { uri: string } };
      };
      selectedRuntimeUrl = new URL(manifest.artifacts.runtime.uri, response.url()).href;
      await route.fulfill({
        response,
        json: { ...manifest, name: `${manifest.name} tampered` },
      });
    },
  );

  await page.goto(
    "/asset/procedural_table_01/1.0.1?registry=/registry.json",
  );

  await expect(page.locator("#status")).toContainText("asset.json byte length mismatch");
  expect(selectedRuntimeUrl).toBeDefined();
  expect(objectRequests).not.toContain(selectedRuntimeUrl);
});

test("supports stable asset routes, lazy manifests, catalog filters, and snippets", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name === "narrow-chromium",
    "The primary flow already covers narrow layout.",
  );
  const failures = observeFailures(page);
  const manifestRequests: string[] = [];
  page.on("request", (request) => {
    if (/\/assets\/[^/]+\/[^/]+\/manifest\.json$/.test(new URL(request.url()).pathname)) {
      manifestRequests.push(request.url());
    }
  });

  const reference = "procedural_table_01@1.0.1";
  await page.goto("/asset/procedural_table_01/1.0.1?registry=/registry.json");
  await expect(page.locator("#status")).toContainText(
    "Procedural wooden table loaded from verified runtime bytes and framed from published bounds.",
  );
  await expect(page.locator("#asset-select")).toHaveValue(reference);
  await expect(page).toHaveURL(
    /\/asset\/procedural_table_01\/1\.0\.1\?registry=(?:%2F|\/)registry\.json$/,
  );
  await expect(page.locator("#catalog-status")).toContainText(
    "15 of 15 registry-verified entries match",
  );

  expect(
    new Set(manifestRequests).size,
    "the catalog should not eagerly request all 15 manifests before it enters view",
  ).toBeLessThan(15);

  const query = page.locator("#catalog-query");
  await query.fill("table");
  await expect(page.locator("#catalog-status")).toContainText(
    "1 of 15 registry-verified entries match",
  );
  await expect(page.locator(".asset-card")).toHaveCount(1);
  await expect(page.locator(".asset-card-name")).toHaveText("Procedural wooden table");
  await expect(page.locator(".asset-card-name")).toHaveAttribute(
    "href",
    "/asset/procedural_table_01/1.0.1",
  );

  await page.locator("#catalog-category").selectOption("furniture");
  await expect(page.locator(".asset-card")).toHaveCount(1);
  await page.locator("#catalog-budget").selectOption("1000");
  await expect(page.locator("#catalog-status")).toContainText(
    "0 of 15 registry-verified entries match",
  );
  await expect(page.locator(".catalog-no-results")).toContainText(
    "No registry-verified entries match those constraints.",
  );
  await page.locator("#catalog-clear").click();
  await expect(page.locator("#catalog-status")).toContainText(
    "15 of 15 registry-verified entries match",
  );
  await expect(page.locator(".asset-card")).toHaveCount(15);

  await page.getByRole("tab", { name: "Direct ID" }).click();
  await expect(page.locator("#quickstart-direct")).toBeVisible();
  await expect(page.locator("#quickstart-sdk")).toBeHidden();
  await expect(page.locator("[data-copy-active-snippet]")).toHaveText(
    "Copy direct-ID snippet",
  );

  const community = page.locator(".community-links");
  await expect(community.getByRole("link", { name: "GitHub", exact: true })).toHaveAttribute(
    "href",
    "https://github.com/Neuralstock/neuralstock",
  );
  await expect(community.getByRole("link", { name: "Docs", exact: true })).toHaveAttribute(
    "href",
    "https://github.com/Neuralstock/neuralstock/tree/main/docs",
  );
  await expect(community.getByRole("link", { name: "Issues", exact: true })).toHaveAttribute(
    "href",
    "https://github.com/Neuralstock/neuralstock/issues",
  );
  await expect(community.getByRole("link", { name: "Show what you built" })).toHaveAttribute(
    "href",
    /labels=showcase/,
  );
  await expect(page.getByRole("link", { name: /Request an asset/ }).first()).toHaveAttribute(
    "href",
    /labels=asset-request/,
  );

  expect(failures.consoleErrors, "console errors").toEqual([]);
  expect(failures.pageErrors, "uncaught page errors").toEqual([]);
  expect(
    failures.requestFailures.filter((failure) => !failure.endsWith("net::ERR_ABORTED")),
    "non-aborted failed requests",
  ).toEqual([]);
  expect(failures.responseErrors, "HTTP error responses").toEqual([]);
});
