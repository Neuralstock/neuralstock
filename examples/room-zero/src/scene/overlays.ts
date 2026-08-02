import type { AssetManifest } from "@neuralstock/client";
import * as THREE from "three";
import { boxFromMetadata, vectorFromMetadata } from "./metadata.js";

function disposeMaterial(material: THREE.Material): void {
  const textures = new Set<THREE.Texture>();
  for (const value of Object.values(material)) {
    if (value instanceof THREE.Texture) textures.add(value);
  }
  textures.forEach((texture) => texture.dispose());
  material.dispose();
}

function disposeChildren(group: THREE.Group): void {
  group.traverse((object) => {
    const renderable = object as THREE.Mesh | THREE.LineSegments;
    renderable.geometry?.dispose();
    if (Array.isArray(renderable.material)) {
      renderable.material.forEach(disposeMaterial);
    } else {
      renderable.material?.dispose();
    }
  });
  group.clear();
}

export class MetadataOverlays {
  readonly root = new THREE.Group();
  private readonly boundsLayer = new THREE.Group();
  private readonly anchorLayer = new THREE.Group();
  private readonly collisionLayer = new THREE.Group();
  private collisionObject: THREE.Object3D | undefined;

  constructor() {
    this.root.name = "metadata-overlays";
    this.root.add(this.boundsLayer, this.anchorLayer, this.collisionLayer);
    this.boundsLayer.visible = false;
    this.anchorLayer.visible = false;
    this.collisionLayer.visible = false;
  }

  clear(): void {
    disposeChildren(this.boundsLayer);
    disposeChildren(this.anchorLayer);
    disposeChildren(this.collisionLayer);
    this.collisionObject = undefined;
  }

  setAsset(asset: AssetManifest, effectiveBounds: THREE.Box3 | undefined): void {
    this.clear();

    if (effectiveBounds) {
      this.boundsLayer.add(new THREE.Box3Helper(effectiveBounds, 0x5eead4));
    }

    const markerScale = Math.max(
      0.025,
      (effectiveBounds?.getSize(new THREE.Vector3()).length() ?? 1) * 0.025,
    );
    for (const anchor of asset.anchors) {
      const position = vectorFromMetadata(anchor.position_m);
      if (!position) continue;

      const marker = new THREE.Group();
      marker.name = `anchor:${anchor.name}`;
      marker.position.copy(position);
      marker.quaternion.fromArray(anchor.rotation_xyzw);
      marker.add(
        new THREE.Mesh(
          new THREE.SphereGeometry(markerScale, 12, 8),
          new THREE.MeshBasicMaterial({ color: 0xfbbf24 }),
        ),
        new THREE.AxesHelper(markerScale * 4),
      );
      this.anchorLayer.add(marker);
    }

    const collisionGroup = new THREE.Group();
    collisionGroup.name = "collision-metadata";
    for (const collision of asset.collisions) {
      const box = boxFromMetadata(collision.bounds_m);
      if (!box) continue;
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(size.x, size.y, size.z),
        new THREE.MeshBasicMaterial({
          color: 0xfb7185,
          depthWrite: false,
          opacity: 0.7,
          transparent: true,
          wireframe: true,
        }),
      );
      mesh.name = `collision:${collision.name}`;
      mesh.position.copy(center);
      collisionGroup.add(mesh);
    }
    if (collisionGroup.children.length > 0) {
      this.collisionObject = collisionGroup;
      this.collisionLayer.add(collisionGroup);
    }
  }

  setBoundsVisible(visible: boolean): void {
    this.boundsLayer.visible = visible;
  }

  setAnchorsVisible(visible: boolean): void {
    this.anchorLayer.visible = visible;
  }

  setCollisionVisible(visible: boolean): void {
    this.collisionLayer.visible = visible;
  }

  setCollisionObject(object: THREE.Object3D): void {
    if (this.collisionObject) {
      this.collisionLayer.remove(this.collisionObject);
      const old = new THREE.Group().add(this.collisionObject);
      disposeChildren(old);
    }

    object.name = "collision-artifact";
    object.traverse((child) => {
      if (!(child instanceof THREE.Mesh)) return;
      if (Array.isArray(child.material)) {
        child.material.forEach(disposeMaterial);
      } else {
        disposeMaterial(child.material);
      }
      child.material = new THREE.MeshBasicMaterial({
        color: 0xfb7185,
        depthWrite: false,
        opacity: 0.7,
        transparent: true,
        wireframe: true,
      });
    });
    this.collisionObject = object;
    this.collisionLayer.add(object);
  }

  dispose(): void {
    this.clear();
    this.root.removeFromParent();
  }
}
