import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  boxFromMetadata,
  dimensionsLabel,
  frameBounds,
  vectorFromMetadata,
} from "../src/scene/metadata.js";

describe("metadata geometry", () => {
  it("accepts tuple and object vectors", () => {
    expect(vectorFromMetadata([1, 2, 3])?.toArray()).toEqual([1, 2, 3]);
    expect(vectorFromMetadata({ x: 4, y: 5, z: 6 })?.toArray()).toEqual([4, 5, 6]);
  });

  it("reads canonical v0.2 bounds", () => {
    const box = boxFromMetadata({
      minimum: [-0.5, 0, -0.25],
      maximum: [0.5, 1, 0.25],
      dimensions: [1, 1, 0.5],
    });

    expect(box?.min.toArray()).toEqual([-0.5, 0, -0.25]);
    expect(box?.max.toArray()).toEqual([0.5, 1, 0.25]);
    expect(dimensionsLabel(box)).toBe("1.00 × 1.00 × 0.50 m");
  });

  it("frames a perspective camera around the metadata bounds", () => {
    const camera = new THREE.PerspectiveCamera(50, 16 / 9, 0.1, 10);
    camera.position.set(4, 3, 5);
    const controls = {
      target: new THREE.Vector3(),
      update() {},
    };
    const box = new THREE.Box3(
      new THREE.Vector3(-1, 0, -2),
      new THREE.Vector3(1, 2, 2),
    );

    frameBounds(camera, controls, box);

    expect(controls.target.toArray()).toEqual([0, 1, 0]);
    expect(camera.position.distanceTo(controls.target)).toBeGreaterThan(2);
    expect(camera.near).toBeGreaterThan(0);
    expect(camera.far).toBeGreaterThan(camera.near);
  });
});
