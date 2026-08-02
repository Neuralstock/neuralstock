import {
  fetchArtifact,
  loadRegistry,
  resolveAsset,
  searchAssets,
  type AssetManifest,
  type RegistryAssetEntry,
  type RegistryManifest,
} from "@neuralstock/client";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { boxFromMetadata, dimensionsLabel, frameBounds } from "./scene/metadata.js";
import { MetadataOverlays } from "./scene/overlays.js";

interface ViewerElements {
  viewport: HTMLElement;
  select: HTMLSelectElement;
  boundsToggle: HTMLInputElement;
  anchorsToggle: HTMLInputElement;
  collisionToggle: HTMLInputElement;
  metadata: HTMLElement;
  emptyState: HTMLElement;
  status: HTMLElement;
}

function disposeObject(root: THREE.Object3D): void {
  root.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return;
    object.geometry.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      for (const value of Object.values(material)) {
        if (value instanceof THREE.Texture) value.dispose();
      }
      material.dispose();
    }
  });
  root.removeFromParent();
}

function setDefinitionList(
  element: HTMLElement,
  rows: ReadonlyArray<readonly [string, string]>,
): void {
  element.replaceChildren();
  for (const [term, description] of rows) {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = term;
    dd.textContent = description;
    element.append(dt, dd);
  }
}

export class RoomZeroViewer {
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.PerspectiveCamera(48, 1, 0.01, 500);
  private readonly renderer: THREE.WebGLRenderer;
  private readonly controls: OrbitControls;
  private readonly loader = new GLTFLoader();
  private readonly modelLayer = new THREE.Group();
  private readonly overlays = new MetadataOverlays();
  private readonly clock = new THREE.Clock();
  private readonly resizeObserver: ResizeObserver;
  private registry: RegistryManifest | undefined;
  private entries: RegistryAssetEntry[] = [];
  private currentAsset: AssetManifest | undefined;
  private currentModel: THREE.Object3D | undefined;
  private generation = 0;
  private contextLost = false;

  constructor(private readonly elements: ViewerElements) {
    this.scene.background = new THREE.Color(0x0a0d10);
    this.scene.fog = new THREE.Fog(0x0a0d10, 12, 35);

    this.camera.position.set(3.5, 2.5, 4.5);
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      powerPreference: "high-performance",
    });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.elements.viewport.append(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.07;
    this.controls.target.set(0, 0.6, 0);
    this.controls.update();

    const hemisphere = new THREE.HemisphereLight(0xc7e6ff, 0x182018, 2.1);
    const key = new THREE.DirectionalLight(0xffffff, 3.2);
    key.position.set(4, 7, 5);
    const rim = new THREE.DirectionalLight(0x76e4f7, 1.1);
    rim.position.set(-5, 3, -4);
    const grid = new THREE.GridHelper(20, 40, 0x334155, 0x172033);
    grid.material.transparent = true;
    grid.material.opacity = 0.55;
    this.scene.add(hemisphere, key, rim, grid, this.modelLayer, this.overlays.root);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.elements.viewport);
    this.resize();

    this.elements.select.addEventListener("change", () => {
      void this.selectAsset(this.elements.select.value);
    });
    this.elements.boundsToggle.addEventListener("change", () => {
      this.overlays.setBoundsVisible(this.elements.boundsToggle.checked);
    });
    this.elements.anchorsToggle.addEventListener("change", () => {
      this.overlays.setAnchorsVisible(this.elements.anchorsToggle.checked);
    });
    this.elements.collisionToggle.addEventListener("change", () => {
      this.overlays.setCollisionVisible(this.elements.collisionToggle.checked);
    });

    this.renderer.domElement.addEventListener("webglcontextlost", (event) => {
      event.preventDefault();
      this.contextLost = true;
      this.renderer.setAnimationLoop(null);
      this.setStatus("WebGL context lost. Waiting for the browser to restore it…", "warning");
    });
    this.renderer.domElement.addEventListener("webglcontextrestored", () => {
      this.contextLost = false;
      this.setStatus("WebGL context restored.");
      this.renderer.setAnimationLoop(this.renderFrame);
    });

    this.renderer.setAnimationLoop(this.renderFrame);
  }

  async start(registryUrl: string, initialAsset?: string): Promise<void> {
    this.setStatus(`Loading registry from ${registryUrl}…`);
    try {
      this.registry = await loadRegistry(registryUrl, { integrity: "strict" });
      this.entries = searchAssets(this.registry, { limit: 1_000 });
    } catch (error) {
      this.showEmpty("Registry unavailable", "The empty room remains usable while metadata is fixed.");
      this.setStatus(error instanceof Error ? error.message : "Could not load registry.", "error");
      return;
    }

    this.populateSelect();
    if (this.entries.length === 0) {
      this.showEmpty("No published assets yet", "Room Zero is ready for a registry snapshot.");
      this.setStatus("Registry loaded. There are no published assets yet.");
      return;
    }

    const separator = initialAsset?.lastIndexOf("@") ?? -1;
    const requestedId =
      initialAsset === undefined
        ? undefined
        : separator > 0
          ? initialAsset.slice(0, separator)
          : initialAsset;
    const requestedLabel =
      initialAsset !== undefined && separator > 0
        ? initialAsset.slice(separator + 1)
        : "latest";
    const requestedVersion =
      requestedLabel === "latest"
        ? this.registry.aliases.find(
            (alias) => alias.id === requestedId && alias.alias === "latest",
          )?.version
        : requestedLabel;
    const requestedEntry = this.entries.find(
      (entry) =>
        entry.asset.id === requestedId &&
        (requestedVersion === undefined || entry.asset.version === requestedVersion),
    );
    const first = requestedEntry ?? this.entries[0];
    if (!first) return;
    const firstReference = `${first.asset.id}@${first.asset.version}`;
    this.elements.select.value = firstReference;
    await this.selectAsset(requestedEntry ? initialAsset ?? firstReference : firstReference);
  }

  private populateSelect(): void {
    this.elements.select.replaceChildren();
    for (const entry of this.entries) {
      const option = document.createElement("option");
      option.value = `${entry.asset.id}@${entry.asset.version}`;
      option.textContent = `${entry.name} · ${entry.asset.version}`;
      this.elements.select.append(option);
    }
    this.elements.select.disabled = this.entries.length === 0;
  }

  private async selectAsset(reference: string): Promise<void> {
    if (!this.registry) return;
    const generation = ++this.generation;
    this.elements.emptyState.hidden = true;
    this.setStatus(`Resolving ${reference}…`);
    this.resetAsset();

    try {
      const asset = await resolveAsset(this.registry, reference, { integrity: "strict" });
      if (generation !== this.generation) return;
      this.currentAsset = asset;

      this.setStatus(`Verifying ${asset.name} runtime bytes…`);
      const modelBytes = await fetchArtifact(asset, "runtime");
      if (generation !== this.generation) return;
      const modelUrl = URL.createObjectURL(
        new Blob([modelBytes], { type: asset.artifacts.runtime.media_type }),
      );
      const gltf = await this.loader
        .loadAsync(modelUrl)
        .finally(() => URL.revokeObjectURL(modelUrl));
      if (generation !== this.generation) {
        disposeObject(gltf.scene);
        return;
      }

      gltf.scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.castShadow = true;
          object.receiveShadow = true;
        }
      });
      this.currentModel = gltf.scene;
      this.modelLayer.add(gltf.scene);

      const metadataBox = boxFromMetadata(asset.bounds_m);
      const effectiveBox = metadataBox ?? new THREE.Box3().setFromObject(gltf.scene);
      this.overlays.setAsset(asset, effectiveBox.isEmpty() ? undefined : effectiveBox);
      if (!effectiveBox.isEmpty()) frameBounds(this.camera, this.controls, effectiveBox);
      this.updateControls(asset, effectiveBox.isEmpty() ? undefined : effectiveBox);
      this.setStatus(
        metadataBox
          ? `${asset.name} loaded from verified runtime bytes and framed from published bounds.`
          : `${asset.name} loaded from verified runtime bytes. Published bounds were absent, so the viewer used mesh bounds.`,
        metadataBox ? "ok" : "warning",
      );
    } catch (error) {
      if (generation !== this.generation) return;
      this.showEmpty("Asset could not be displayed", "Check its manifest and runtime artifact.");
      this.setStatus(error instanceof Error ? error.message : "Asset loading failed.", "error");
    }
  }

  private updateControls(asset: AssetManifest, box: THREE.Box3 | undefined): void {
    this.elements.boundsToggle.disabled = box === undefined;
    this.elements.anchorsToggle.disabled = asset.anchors.length === 0;

    this.elements.collisionToggle.disabled = asset.collisions.length === 0;

    setDefinitionList(this.elements.metadata, [
      ["ID", `${asset.id}@${asset.version}`],
      ["License", asset.license],
      ["Bounds", dimensionsLabel(box)],
      ["Triangles", asset.geometry.triangle_count.toLocaleString()],
      ["Anchors", String(asset.anchors.length)],
      ["Collisions", String(asset.collisions.length)],
    ]);
  }

  private resetAsset(): void {
    if (this.currentModel) disposeObject(this.currentModel);
    this.currentModel = undefined;
    this.currentAsset = undefined;
    this.overlays.clear();
    for (const toggle of [
      this.elements.boundsToggle,
      this.elements.anchorsToggle,
      this.elements.collisionToggle,
    ]) {
      toggle.checked = false;
      toggle.disabled = true;
    }
    this.elements.metadata.replaceChildren();
  }

  private showEmpty(title: string, detail: string): void {
    this.resetAsset();
    const strong = this.elements.emptyState.querySelector("strong");
    const span = this.elements.emptyState.querySelector("span");
    if (strong) strong.textContent = title;
    if (span) span.textContent = detail;
    this.elements.emptyState.hidden = false;
  }

  private setStatus(
    message: string,
    tone: "ok" | "warning" | "error" = "ok",
  ): void {
    this.elements.status.textContent = message;
    this.elements.status.dataset.tone = tone;
  }

  private resize(): void {
    const width = Math.max(1, this.elements.viewport.clientWidth);
    const height = Math.max(1, this.elements.viewport.clientHeight);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  private readonly renderFrame = (): void => {
    if (this.contextLost) return;
    this.clock.getDelta();
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  };
}

export function collectViewerElements(): ViewerElements {
  const get = <T extends HTMLElement>(id: string): T => {
    const element = document.getElementById(id);
    if (!(element instanceof HTMLElement)) throw new Error(`Missing #${id}.`);
    return element as T;
  };

  return {
    viewport: get("viewport"),
    select: get<HTMLSelectElement>("asset-select"),
    boundsToggle: get<HTMLInputElement>("toggle-bounds"),
    anchorsToggle: get<HTMLInputElement>("toggle-anchors"),
    collisionToggle: get<HTMLInputElement>("toggle-collision"),
    metadata: get("asset-metadata"),
    emptyState: get("empty-state"),
    status: get("status"),
  };
}
