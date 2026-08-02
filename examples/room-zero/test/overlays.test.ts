import type { AssetManifest, QuaternionTuple } from "@neuralstock/client";
import { describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { MetadataOverlays } from "../src/scene/overlays.js";

describe("metadata overlays", () => {
  it("applies a non-identity anchor quaternion to its marker", () => {
    const expected = new THREE.Quaternion().setFromAxisAngle(
      new THREE.Vector3(0, 1, 0),
      Math.PI / 2,
    );
    const rotation = expected.toArray() as QuaternionTuple;
    const asset = {
      anchors: [
        {
          name: "ANCHOR_rotated",
          position_m: [0, 1, 0],
          rotation_xyzw: rotation,
        },
      ],
      collisions: [],
    } as unknown as AssetManifest;
    const overlays = new MetadataOverlays();

    overlays.setAsset(
      asset,
      new THREE.Box3(
        new THREE.Vector3(-0.5, 0, -0.5),
        new THREE.Vector3(0.5, 1, 0.5),
      ),
    );

    const marker = overlays.root.getObjectByName("anchor:ANCHOR_rotated");
    expect(marker).toBeDefined();
    expect(marker!.quaternion.angleTo(expected)).toBeLessThan(1e-12);

    overlays.dispose();
  });

  it("disposes textures before replacing collision materials", () => {
    const texture = new THREE.Texture();
    const material = new THREE.MeshStandardMaterial({ map: texture });
    const textureDispose = vi.spyOn(texture, "dispose");
    const materialDispose = vi.spyOn(material, "dispose");
    const collision = new THREE.Group();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), material);
    collision.add(mesh);
    const overlays = new MetadataOverlays();

    overlays.setCollisionObject(collision);

    expect(textureDispose).toHaveBeenCalledOnce();
    expect(materialDispose).toHaveBeenCalledOnce();
    expect(mesh.material).toBeInstanceOf(THREE.MeshBasicMaterial);
    expect(mesh.material).not.toBe(material);

    overlays.dispose();
  });

  it("renders collision boxes directly from manifest bounds", () => {
    const asset = {
      anchors: [],
      collisions: [
        {
          name: "COLLISION_body",
          kind: "box",
          bounds_m: {
            minimum: [-1, 0.25, -0.5],
            maximum: [1, 1.25, 0.5],
            dimensions: [2, 1, 1],
          },
          vertex_count: 8,
          triangle_count: 12,
        },
      ],
    } as unknown as AssetManifest;
    const overlays = new MetadataOverlays();

    overlays.setAsset(asset, undefined);

    const mesh = overlays.root.getObjectByName(
      "collision:COLLISION_body",
    ) as THREE.Mesh;
    expect(mesh).toBeInstanceOf(THREE.Mesh);
    expect(mesh.position.toArray()).toEqual([0, 0.75, 0]);
    mesh.geometry.computeBoundingBox();
    expect(mesh.geometry.boundingBox?.getSize(new THREE.Vector3()).toArray()).toEqual([
      2, 1, 1,
    ]);

    overlays.dispose();
  });
});
