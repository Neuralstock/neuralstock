import {
  fetchArtifact,
  loadRegistry,
  resolveAsset,
  searchAssets,
  type AssetArtifact,
  type AssetManifest,
  type RegistryAssetEntry,
  type RegistryManifest,
} from "@neuralstock/client";
import "./styles.css";
import { collectViewerElements, RoomZeroViewer } from "./viewer.js";

const SITE_TITLE = "NeuralStock · Open assets for machine-built worlds";
const SITE_DESCRIPTION =
  "NeuralStock is the open asset layer for machine-built worlds: trusted CC0 Blender sources, validated GLBs, and metadata agents can use.";
const PUBLIC_SITE_ORIGIN = "https://neuralstock.ai";
const ASSET_ROUTE = /^\/asset\/([^/]+)\/([^/]+)\/?$/;

const query = new URLSearchParams(window.location.search);
const registryUrl =
  query.get("registry") ??
  import.meta.env.VITE_NEURALSTOCK_REGISTRY_URL ??
  `${import.meta.env.BASE_URL}registry.json`;

function assetReferenceFromPath(pathname: string): string | undefined {
  const match = ASSET_ROUTE.exec(pathname);
  if (!match) return undefined;
  try {
    return `${decodeURIComponent(match[1]!)}@${decodeURIComponent(match[2]!)}`;
  } catch {
    return undefined;
  }
}

const routedAsset = assetReferenceFromPath(window.location.pathname);
const initialAsset = routedAsset ?? query.get("asset") ?? undefined;
const initialAssetWasRequested = initialAsset !== undefined;

document.documentElement.dataset.enhanced = "true";

function element<T extends HTMLElement>(id: string): T | undefined {
  const candidate = document.getElementById(id);
  return candidate instanceof HTMLElement ? (candidate as T) : undefined;
}

function assetReference(entry: RegistryAssetEntry): string {
  return `${entry.asset.id}@${entry.asset.version}`;
}

function splitAssetReference(reference: string): { id: string; version: string } | undefined {
  const separator = reference.lastIndexOf("@");
  if (separator <= 0 || separator === reference.length - 1) return undefined;
  return {
    id: reference.slice(0, separator),
    version: reference.slice(separator + 1),
  };
}

function assetPath(entry: RegistryAssetEntry): string {
  return `/asset/${encodeURIComponent(entry.asset.id)}/${encodeURIComponent(entry.asset.version)}`;
}

function shareUrl(entry: RegistryAssetEntry): string {
  return new URL(assetPath(entry), window.location.origin).href;
}

function entryForReference(
  registry: RegistryManifest | undefined,
  reference: string,
): RegistryAssetEntry | undefined {
  return registry?.entries.find((entry) => assetReference(entry) === reference);
}

function syncActiveCard(select: HTMLSelectElement): void {
  for (const card of document.querySelectorAll<HTMLElement>("[data-asset-ref]")) {
    const selected = card.dataset.assetRef === select.value;
    card.classList.toggle("is-active", selected);
    card
      .querySelector<HTMLButtonElement>("[data-view-asset]")
      ?.setAttribute("aria-pressed", String(selected));
  }
}

function textElement<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className: string,
  text: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

function formatBytes(bytes: number): string {
  if (bytes < 1_024) return `${bytes} B`;
  if (bytes < 1_048_576) {
    const kilobytes = bytes / 1_024;
    return `${kilobytes < 100 ? kilobytes.toFixed(1) : kilobytes.toFixed(0)} KB`;
  }
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function setPageContext(entry?: RegistryAssetEntry): void {
  const title = entry
    ? `${entry.name} ${entry.asset.version} · CC0 Blender asset · NeuralStock`
    : SITE_TITLE;
  const description = entry?.description ?? SITE_DESCRIPTION;
  const canonicalUrl = new URL(entry ? assetPath(entry) : "/", PUBLIC_SITE_ORIGIN).href;

  document.title = title;
  document.querySelector<HTMLMetaElement>('meta[name="description"]')?.setAttribute(
    "content",
    description,
  );
  document.querySelector<HTMLMetaElement>('meta[property="og:title"]')?.setAttribute(
    "content",
    title,
  );
  document.querySelector<HTMLMetaElement>('meta[property="og:description"]')?.setAttribute(
    "content",
    description,
  );
  document.querySelector<HTMLMetaElement>('meta[property="og:url"]')?.setAttribute(
    "content",
    canonicalUrl,
  );
  document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.setAttribute(
    "href",
    canonicalUrl,
  );
}

function setAssetRoute(entry: RegistryAssetEntry, mode: "push" | "replace"): void {
  const url = new URL(window.location.href);
  url.pathname = assetPath(entry);
  url.searchParams.delete("asset");
  window.history[mode === "push" ? "pushState" : "replaceState"]({}, "", url);
  setPageContext(entry);
}

async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const fallback = document.createElement("textarea");
  fallback.value = text;
  fallback.readOnly = true;
  fallback.style.position = "fixed";
  fallback.style.opacity = "0";
  document.body.append(fallback);
  fallback.select();
  const copied = document.execCommand("copy");
  fallback.remove();
  if (!copied) throw new Error("Clipboard access is unavailable.");
}

let downloadStatusGeneration = 0;

function setDownloadStatus(
  message: string,
  tone: "progress" | "ok" | "error",
  clearAfterMs?: number,
): void {
  const status = element<HTMLElement>("download-status");
  if (!status) return;
  const generation = ++downloadStatusGeneration;
  status.textContent = message;
  status.dataset.tone = tone;
  if (clearAfterMs === undefined) return;
  window.setTimeout(() => {
    if (generation !== downloadStatusGeneration) return;
    status.textContent = "";
    delete status.dataset.tone;
  }, clearAfterMs);
}

async function downloadArtifact(
  button: HTMLButtonElement,
  asset: AssetManifest,
  artifact: AssetArtifact,
  fileName: string,
  assetName: string,
  artifactLabel: string,
): Promise<void> {
  const defaultLabel = button.dataset.defaultLabel ?? `Download ${artifactLabel}`;
  const operation = String(Number(button.dataset.downloadOperation ?? "0") + 1);
  button.dataset.downloadOperation = operation;
  button.disabled = true;
  button.dataset.verified = "pending";
  button.classList.add("is-loading");
  button.textContent = "Fetching…";
  setDownloadStatus(
    `Downloading and verifying ${assetName} ${artifactLabel}…`,
    "progress",
  );

  let objectUrl: string | undefined;
  try {
    const bytes = await fetchArtifact(asset, artifact, {
      requestInit: {
        credentials: "omit",
        mode: "cors",
      },
    });
    objectUrl = URL.createObjectURL(
      new Blob([bytes], { type: artifact.media_type }),
    );
    const download = document.createElement("a");
    download.href = objectUrl;
    download.download = fileName;
    download.hidden = true;
    document.body.append(download);
    download.click();
    download.remove();

    button.textContent = "Downloaded";
    button.dataset.verified = "true";
    button.classList.add("is-complete");
    setDownloadStatus(`${fileName} passed SHA-256 verification and is ready.`, "ok", 4_000);
  } catch (error) {
    const detail = error instanceof Error ? ` ${error.message}` : "";
    button.textContent = "Try again";
    button.dataset.verified = "false";
    button.classList.add("is-error");
    setDownloadStatus(
      `Could not download ${assetName} ${artifactLabel}.${detail}`,
      "error",
      7_000,
    );
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
    const urlToRevoke = objectUrl;
    if (urlToRevoke) {
      window.setTimeout(() => URL.revokeObjectURL(urlToRevoke), 1_000);
    }
    window.setTimeout(() => {
      if (button.dataset.downloadOperation !== operation) return;
      button.textContent = defaultLabel;
      button.classList.remove("is-complete", "is-error");
    }, 2_400);
  }
}

function makeDownloadButton(
  artifactKey: string,
  label: string,
  asset: AssetManifest,
  artifact: AssetArtifact,
  fileName: string,
  assetName: string,
  bytes: number,
): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "asset-action asset-download";
  button.dataset.artifact = artifactKey;
  button.dataset.defaultLabel = `${label} · ${formatBytes(bytes)} ↓`;
  button.textContent = button.dataset.defaultLabel;
  button.setAttribute(
    "aria-label",
    `Download and verify ${assetName} ${label}, ${formatBytes(bytes)}`,
  );
  button.addEventListener("click", () => {
    void downloadArtifact(button, asset, artifact, fileName, assetName, label);
  });
  return button;
}

function makeViewButton(
  entry: RegistryAssetEntry,
  select: HTMLSelectElement,
): HTMLButtonElement {
  const reference = assetReference(entry);
  const view = document.createElement("button");
  view.type = "button";
  view.className = "asset-action asset-view";
  view.dataset.viewAsset = reference;
  view.textContent = "View in 3D";
  view.disabled = select.disabled;
  view.setAttribute("aria-pressed", "false");
  view.setAttribute("aria-label", `View ${entry.name} in the Room Zero 3D viewer`);
  view.addEventListener("click", () => {
    if (select.disabled) return;
    select.value = reference;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    document.querySelector(".viewer-frame")?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "center",
    });
  });
  return view;
}

function makeShareButton(entry: RegistryAssetEntry): HTMLButtonElement {
  const share = document.createElement("button");
  share.type = "button";
  share.className = "asset-action asset-share";
  share.textContent = "Copy link";
  share.setAttribute("aria-label", `Copy a stable link to ${entry.name}`);
  share.addEventListener("click", async () => {
    try {
      await copyText(shareUrl(entry));
      share.textContent = "Link copied";
      share.classList.add("is-complete");
      setDownloadStatus(`Stable link copied for ${entry.name}.`, "ok", 4_000);
    } catch {
      share.textContent = "Copy failed";
      share.classList.add("is-error");
      setDownloadStatus("The asset link could not be copied.", "error", 5_000);
    }
    window.setTimeout(() => {
      share.textContent = "Copy link";
      share.classList.remove("is-complete", "is-error");
    }, 2_400);
  });
  return share;
}

interface DownloadSpec {
  key: string;
  label: string;
  fileName: string;
  artifact: AssetArtifact;
}

function artifactDownloads(
  entry: RegistryAssetEntry,
  asset: AssetManifest,
): DownloadSpec[] {
  const stem = `${entry.asset.id}-${entry.asset.version}`;
  const preview = asset.artifacts.previews[0];
  const downloads: DownloadSpec[] = [
    {
      key: "runtime",
      label: "GLB",
      fileName: `${stem}.glb`,
      artifact: asset.artifacts.runtime,
    },
    {
      key: "source",
      label: "BLEND",
      fileName: `${stem}.blend`,
      artifact: asset.artifacts.source,
    },
    {
      key: "manifest",
      label: "Manifest JSON",
      fileName: `${stem}-manifest.json`,
      artifact: entry.manifest,
    },
    {
      key: "provenance",
      label: "Provenance JSON",
      fileName: `${stem}-provenance.json`,
      artifact: asset.artifacts.provenance,
    },
    {
      key: "inspection",
      label: "Validation JSON",
      fileName: `${stem}-validation.json`,
      artifact: asset.artifacts.inspection,
    },
    {
      key: "build_receipt",
      label: "Build receipt",
      fileName: `${stem}-build-receipt.json`,
      artifact: asset.artifacts.build_receipt,
    },
  ];
  if (preview) {
    downloads.splice(2, 0, {
      key: "preview",
      label: "Preview PNG",
      fileName: `${stem}-preview.png`,
      artifact: preview,
    });
  }
  return downloads;
}

const manifestRequests = new Map<string, Promise<AssetManifest>>();
let catalogRegistry: RegistryManifest | undefined;
let manifestObserver: IntersectionObserver | undefined;
const manifestLoaders = new WeakMap<Element, () => void>();

function loadManifest(entry: RegistryAssetEntry): Promise<AssetManifest> {
  if (!catalogRegistry) return Promise.reject(new Error("Registry is not loaded."));
  const reference = assetReference(entry);
  let request = manifestRequests.get(reference);
  if (!request) {
    request = resolveAsset(catalogRegistry, entry, { integrity: "strict" });
    manifestRequests.set(reference, request);
  }
  return request;
}

async function hydrateAssetCard(
  card: HTMLElement,
  entry: RegistryAssetEntry,
): Promise<void> {
  if (card.dataset.manifestState === "loading" || card.dataset.manifestState === "loaded") {
    return;
  }
  card.dataset.manifestState = "loading";
  const files = card.querySelector<HTMLElement>(".asset-card-files");
  if (files) files.textContent = "Loading artifact manifest…";

  try {
    const asset = await loadManifest(entry);
    if (!card.isConnected) return;
    const preview = card.querySelector<HTMLElement>(".asset-card-preview");
    const previewArtifact = asset.artifacts.previews[0];
    if (preview && previewArtifact) {
      try {
        const previewBytes = await fetchArtifact(asset, previewArtifact);
        if (!card.isConnected) return;
        const previewUrl = URL.createObjectURL(
          new Blob([previewBytes], { type: previewArtifact.media_type }),
        );
        const image = document.createElement("img");
        image.src = previewUrl;
        image.alt = `Verified preview of ${entry.name}`;
        image.loading = "lazy";
        image.decoding = "async";
        image.dataset.verified = "true";
        image.addEventListener("load", () => {
          URL.revokeObjectURL(previewUrl);
          preview.classList.remove("asset-preview-loading");
        });
        image.addEventListener("error", () => {
          URL.revokeObjectURL(previewUrl);
          preview.classList.remove("asset-preview-loading");
          preview.classList.add("preview-unavailable");
          image.remove();
        });
        preview.replaceChildren(image);
      } catch {
        preview.classList.remove("asset-preview-loading");
        preview.classList.add("preview-unavailable");
        preview.replaceChildren(
          textElement("span", "asset-manifest-pending", "preview verification failed"),
        );
      }
    }

    const parameterCount = Object.keys(asset.source_generator.parameters).length;
    const detail = card.querySelector<HTMLElement>(".asset-card-detail");
    if (detail) {
      detail.textContent = parameterCount > 0
        ? `${entry.triangle_count.toLocaleString()} tris · ${parameterCount} safe inputs`
        : `${entry.triangle_count.toLocaleString()} tris · ready to load`;
    }
    if (files) {
      files.textContent = `GLB ${formatBytes(asset.artifacts.runtime.bytes)} · BLEND ${formatBytes(asset.artifacts.source.bytes)}`;
    }

    const details = document.createElement("details");
    details.className = "asset-download-panel";
    const summary = document.createElement("summary");
    summary.textContent = "Download files & evidence";
    const downloads = document.createElement("div");
    downloads.className = "asset-download-grid";
    downloads.append(
      ...artifactDownloads(entry, asset).map((spec) =>
        makeDownloadButton(
          spec.key,
          spec.label,
          asset,
          spec.artifact,
          spec.fileName,
          entry.name,
          spec.artifact.bytes,
        ),
      ),
    );
    details.append(summary, downloads);
    card.querySelector(".asset-card-content")?.append(details);
    card.dataset.manifestState = "loaded";
  } catch {
    if (!card.isConnected) return;
    card.dataset.manifestState = "error";
    card.classList.add("manifest-unavailable");
    if (files) files.textContent = "Artifact manifest unavailable · reload to retry";
  }
}

function observeManifest(card: HTMLElement, loader: () => void): void {
  if (!window.IntersectionObserver) {
    loader();
    return;
  }
  manifestLoaders.set(card, loader);
  manifestObserver?.observe(card);
}

function makeAssetCard(
  entry: RegistryAssetEntry,
  select: HTMLSelectElement,
): HTMLElement {
  const reference = assetReference(entry);
  const card = document.createElement("article");
  card.className = "asset-card";
  card.dataset.assetRef = reference;
  card.dataset.manifestState = "idle";

  const preview = document.createElement("span");
  preview.className = "asset-card-preview asset-preview-loading";
  preview.append(textElement("span", "asset-manifest-pending", "manifest on approach"));

  const content = document.createElement("div");
  content.className = "asset-card-content";
  const labelRow = document.createElement("span");
  labelRow.className = "asset-card-labels";
  labelRow.append(
    textElement("span", "asset-license", "CC0"),
    textElement("span", "asset-category", entry.semantics.categories[0] ?? "asset"),
  );

  const name = document.createElement("a");
  name.className = "asset-card-name";
  name.href = assetPath(entry);
  name.textContent = entry.name;
  name.setAttribute(
    "aria-label",
    `Open the stable page for ${entry.name} version ${entry.asset.version}`,
  );

  const actions = document.createElement("div");
  actions.className = "asset-actions";
  actions.append(makeViewButton(entry, select), makeShareButton(entry));

  content.append(
    labelRow,
    name,
    textElement(
      "span",
      "asset-card-detail",
      `${entry.triangle_count.toLocaleString()} tris · ${entry.semantics.placement}`,
    ),
    textElement("span", "asset-card-files", "Artifact details load on approach"),
    actions,
  );
  card.append(preview, content);
  observeManifest(card, () => {
    manifestObserver?.unobserve(card);
    void hydrateAssetCard(card, entry);
  });
  return card;
}

function requestLink(): HTMLAnchorElement {
  const link = document.createElement("a");
  link.className = "text-link";
  link.href =
    "https://github.com/Neuralstock/neuralstock/issues/new?labels=asset-request&title=Asset%20request%3A%20";
  link.textContent = "Request a missing asset ↗";
  return link;
}

function catalogSearchOptions(): {
  query?: string;
  categories?: string[];
  max_triangles?: number;
  limit: number;
} {
  const queryInput = element<HTMLInputElement>("catalog-query");
  const categorySelect = element<HTMLSelectElement>("catalog-category");
  const budgetSelect = element<HTMLSelectElement>("catalog-budget");
  const search = queryInput?.value.trim();
  const category = categorySelect?.value;
  const budget = Number.parseInt(budgetSelect?.value ?? "", 10);
  return {
    ...(search ? { query: search } : {}),
    ...(category ? { categories: [category] } : {}),
    ...(Number.isFinite(budget) ? { max_triangles: budget } : {}),
    limit: 1_000,
  };
}

function normalizedWords(value: string): string[] {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

function matchesCatalogQuery(entry: RegistryAssetEntry, queryValue: string): boolean {
  const queryWords = normalizedWords(queryValue);
  if (queryWords.length === 0) return true;
  const assetWords = normalizedWords(
    [
      entry.asset.id,
      entry.name,
      entry.description,
      ...entry.semantics.tags,
      ...entry.semantics.categories,
      ...entry.semantics.affordances,
      entry.semantics.placement,
    ].join(" "),
  );
  return queryWords.every((queryWord) =>
    assetWords.some((assetWord) => assetWord.startsWith(queryWord)),
  );
}

function renderCatalog(select: HTMLSelectElement): void {
  const grid = element<HTMLElement>("asset-grid");
  const status = element<HTMLElement>("catalog-status");
  if (!grid || !status || !catalogRegistry) return;

  manifestObserver?.disconnect();
  manifestObserver = window.IntersectionObserver
    ? new IntersectionObserver(
        (observations) => {
          for (const observation of observations) {
            if (!observation.isIntersecting) continue;
            manifestLoaders.get(observation.target)?.();
          }
        },
        { rootMargin: "260px 0px" },
      )
    : undefined;

  const searchOptions = catalogSearchOptions();
  const entries = searchAssets(catalogRegistry, searchOptions).filter((entry) =>
    matchesCatalogQuery(entry, searchOptions.query ?? ""),
  );
  if (entries.length === 0) {
    const empty = document.createElement("div");
    empty.className = "catalog-unavailable catalog-no-results";
    empty.append(
      textElement(
        "strong",
        "",
        "No registry-verified entries match those constraints.",
      ),
      textElement(
        "span",
        "",
        "Try a broader term or tell the project which building block is missing.",
      ),
      requestLink(),
    );
    grid.replaceChildren(empty);
  } else {
    grid.replaceChildren(
      ...entries.map((entry) => makeAssetCard(entry, select)),
    );
  }
  grid.setAttribute("aria-busy", "false");
  status.textContent = `${entries.length} of ${catalogRegistry.entries.length} registry-verified entries match. Manifests verify on approach.`;
  syncActiveCard(select);
  setCatalogAvailability(select);
}

function enableCatalogControls(select: HTMLSelectElement): void {
  const form = element<HTMLFormElement>("catalog-controls");
  const queryInput = element<HTMLInputElement>("catalog-query");
  const categorySelect = element<HTMLSelectElement>("catalog-category");
  const budgetSelect = element<HTMLSelectElement>("catalog-budget");
  if (!form || !queryInput || !categorySelect || !budgetSelect) return;

  const render = (): void => renderCatalog(select);
  queryInput.addEventListener("input", render);
  categorySelect.addEventListener("change", render);
  budgetSelect.addEventListener("change", render);
  form.addEventListener("reset", (event) => {
    event.preventDefault();
    queryInput.value = "";
    categorySelect.value = "";
    budgetSelect.value = "";
    queryInput.focus();
    render();
  });
}

async function populateCatalog(url: string, select: HTMLSelectElement): Promise<void> {
  const grid = element<HTMLElement>("asset-grid");
  const status = element<HTMLElement>("catalog-status");
  const categorySelect = element<HTMLSelectElement>("catalog-category");
  if (!grid || !status) return;

  try {
    catalogRegistry = await loadRegistry(url, { integrity: "strict" });
    if (categorySelect) {
      const categories = [
        ...new Set(catalogRegistry.entries.flatMap((entry) => entry.semantics.categories)),
      ].sort((left, right) => left.localeCompare(right));
      categorySelect.append(
        ...categories.map((category) => {
          const option = document.createElement("option");
          option.value = category;
          option.textContent = category.replaceAll("-", " ");
          return option;
        }),
      );
    }
    enableCatalogControls(select);
    renderCatalog(select);
  } catch {
    grid.replaceChildren(
      textElement(
        "p",
        "catalog-unavailable",
        "The live collection is temporarily unavailable. The open registry can still be mirrored and inspected independently.",
      ),
    );
    grid.setAttribute("aria-busy", "false");
    status.textContent = "Live registry unavailable.";
  }
}

function setCatalogAvailability(select: HTMLSelectElement): void {
  for (const button of document.querySelectorAll<HTMLButtonElement>("[data-view-asset]")) {
    button.disabled = select.disabled;
  }
  syncActiveCard(select);
}

function enableSnippetControls(): void {
  const tabs = [...document.querySelectorAll<HTMLButtonElement>("[data-snippet-tab]")];
  const copy = document.querySelector<HTMLButtonElement>("[data-copy-active-snippet]");
  if (tabs.length === 0 || !copy) return;

  const selectSnippet = (name: string): void => {
    for (const tab of tabs) {
      const selected = tab.dataset.snippetTab === name;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      const panelId = tab.getAttribute("aria-controls");
      const panel = panelId ? element<HTMLElement>(panelId) : undefined;
      if (panel) panel.hidden = !selected;
    }
    copy.dataset.copyTarget = name === "direct" ? "quickstart-direct" : "quickstart-sdk";
    copy.textContent = name === "direct" ? "Copy direct-ID snippet" : "Copy SDK snippet";
  };

  for (const [index, tab] of tabs.entries()) {
    tab.addEventListener("click", () => selectSnippet(tab.dataset.snippetTab ?? "sdk"));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(index + direction + tabs.length) % tabs.length];
      if (!next) return;
      selectSnippet(next.dataset.snippetTab ?? "sdk");
      next.focus();
    });
  }

  copy.addEventListener("click", async () => {
    const code = element<HTMLElement>(copy.dataset.copyTarget ?? "");
    if (!code) return;
    const defaultLabel = copy.textContent ?? "Copy snippet";
    try {
      await copyText(code.textContent ?? "");
      copy.textContent = "Copied";
    } catch {
      copy.textContent = "Select code to copy";
    }
    window.setTimeout(() => {
      copy.textContent = defaultLabel;
    }, 1_800);
  });

  selectSnippet("sdk");
}

const select = element<HTMLSelectElement>("asset-select");
let suppressRouteUpdate = false;

try {
  const viewer = new RoomZeroViewer(collectViewerElements());
  const viewerReady = viewer.start(registryUrl, initialAsset);
  if (select) {
    select.addEventListener("change", () => {
      syncActiveCard(select);
      const selectedEntry = entryForReference(catalogRegistry, select.value);
      if (!selectedEntry) return;
      if (!suppressRouteUpdate) setAssetRoute(selectedEntry, "push");
    });
    void populateCatalog(registryUrl, select);
    void viewerReady.finally(() => {
      setCatalogAvailability(select);
      const selectedEntry = entryForReference(catalogRegistry, select.value);
      if (selectedEntry && initialAssetWasRequested) {
        setAssetRoute(selectedEntry, "replace");
      }
    });

    window.addEventListener("popstate", () => {
      const reference = assetReferenceFromPath(window.location.pathname);
      if (!reference) {
        setPageContext();
        return;
      }
      const routeEntry = entryForReference(catalogRegistry, reference);
      if (!routeEntry || select.disabled) return;
      suppressRouteUpdate = true;
      select.value = reference;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      suppressRouteUpdate = false;
      setPageContext(routeEntry);
    });
  }
} catch (error) {
  const status = element<HTMLElement>("status");
  if (status) {
    status.textContent =
      error instanceof Error ? error.message : "This browser could not start WebGL.";
    status.dataset.tone = "error";
  }
}

enableSnippetControls();
