import type {
  AssetBounds,
  Vector3Object,
  Vector3Tuple,
  Vector3Value,
} from "@neuralstock/client";
import * as THREE from "three";

export interface CameraTarget {
  target: THREE.Vector3;
  update(): void;
}

export function vectorFromMetadata(
  value: Vector3Value | undefined,
): THREE.Vector3 | undefined {
  if (value === undefined) return undefined;

  const vector = Array.isArray(value)
    ? new THREE.Vector3(
        (value as Vector3Tuple)[0],
        (value as Vector3Tuple)[1],
        (value as Vector3Tuple)[2],
      )
    : new THREE.Vector3(
        (value as Vector3Object).x,
        (value as Vector3Object).y,
        (value as Vector3Object).z,
      );
  return [vector.x, vector.y, vector.z].every(Number.isFinite) ? vector : undefined;
}

export function boxFromMetadata(bounds: AssetBounds | undefined): THREE.Box3 | undefined {
  if (bounds === undefined) return undefined;

  const minimum = vectorFromMetadata(bounds.minimum);
  const maximum = vectorFromMetadata(bounds.maximum);
  if (!minimum || !maximum) return undefined;

  const box = new THREE.Box3(minimum, maximum);
  if (box.isEmpty()) return undefined;
  return box;
}

export function frameBounds(
  camera: THREE.PerspectiveCamera,
  controls: CameraTarget,
  box: THREE.Box3,
  padding = 1.35,
): void {
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const radius = Math.max(sphere.radius, 0.1);
  const verticalFov = THREE.MathUtils.degToRad(camera.fov);
  const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
  const limitingFov = Math.max(0.01, Math.min(verticalFov, horizontalFov));
  const distance = (radius / Math.sin(limitingFov / 2)) * padding;

  const direction = camera.position.clone().sub(controls.target);
  if (direction.lengthSq() < 0.0001) direction.set(1, 0.65, 1);
  direction.normalize();

  controls.target.copy(sphere.center);
  camera.position.copy(sphere.center).addScaledVector(direction, distance);
  camera.near = Math.max(0.01, distance - radius * 2.5);
  camera.far = Math.max(100, distance + radius * 8);
  camera.updateProjectionMatrix();
  controls.update();
}

export function dimensionsLabel(box: THREE.Box3 | undefined): string {
  if (box === undefined) return "Unknown";
  const size = box.getSize(new THREE.Vector3());
  return `${size.x.toFixed(2)} × ${size.y.toFixed(2)} × ${size.z.toFixed(2)} m`;
}
