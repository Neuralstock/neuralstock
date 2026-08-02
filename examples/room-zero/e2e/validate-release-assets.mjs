import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const expectedAssetCount = 15;
const expectedCollisionCount = 25;
const boundsToleranceMeters = 1e-5;
const transformTolerance = 1e-5;
const defaultReleaseRoot = fileURLToPath(
  new URL("../../../dist/release/", import.meta.url),
);
const releaseRoot = resolve(
  process.env.NEURALSTOCK_RELEASE_DIR ?? defaultReleaseRoot,
);

function releasePath(uri) {
  if (typeof uri !== "string" || !uri.startsWith("/")) {
    throw new Error(`Release URI must be root-relative: ${JSON.stringify(uri)}`);
  }
  const parsed = new URL(uri, "https://release.neuralstock.invalid/");
  if (
    parsed.origin !== "https://release.neuralstock.invalid" ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(`Release URI is not a plain local path: ${uri}`);
  }
  const candidate = resolve(releaseRoot, `.${decodeURIComponent(parsed.pathname)}`);
  const local = relative(releaseRoot, candidate);
  if (isAbsolute(local) || local === ".." || local.startsWith(`..${process.platform === "win32" ? "\\" : "/"}`)) {
    throw new Error(`Release URI escapes the release root: ${uri}`);
  }
  return candidate;
}

async function readJson(path, label) {
  const value = JSON.parse(await readFile(path, "utf8"));
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return value;
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function requireDescriptor(bytes, descriptor, label) {
  if (descriptor.bytes !== bytes.byteLength) {
    throw new Error(`${label} byte count does not match its descriptor.`);
  }
  if (descriptor.sha256 !== sha256(bytes)) {
    throw new Error(`${label} hash does not match its descriptor.`);
  }
}

function maximumBoundsError(actual, expected) {
  const actualValues = [
    actual.min.x,
    actual.min.y,
    actual.min.z,
    actual.max.x,
    actual.max.y,
    actual.max.z,
  ];
  const expectedValues = [...expected.minimum, ...expected.maximum];
  return Math.max(
    ...actualValues.map((value, index) => Math.abs(value - expectedValues[index])),
  );
}

function runtimeGeometry(scene, parserJson) {
  const geometries = new Set();
  scene.traverse((object) => {
    if (object instanceof THREE.Mesh) geometries.add(object.geometry);
  });
  let vertexCount = 0;
  let triangleCount = 0;
  for (const geometry of geometries) {
    const positions = geometry.getAttribute("position");
    if (!positions) throw new Error("Runtime mesh is missing POSITION data.");
    vertexCount += positions.count;
    triangleCount += (geometry.index?.count ?? positions.count) / 3;
  }
  if (!Number.isInteger(triangleCount)) {
    throw new Error("Runtime mesh has a non-integral triangle count.");
  }
  return {
    vertex_count: vertexCount,
    triangle_count: triangleCount,
    material_count: parserJson.materials?.length ?? 0,
  };
}

function maximumVectorError(actual, expected) {
  return Math.max(...actual.map((value, index) => Math.abs(value - expected[index])));
}

function requireCollision(collision, identity) {
  if (collision.kind !== "box") {
    throw new Error(`${identity} collision ${collision.name} is not a box.`);
  }
  const { minimum, maximum, dimensions } = collision.bounds_m;
  const expectedDimensions = maximum.map((value, index) => value - minimum[index]);
  if (
    expectedDimensions.some((value) => !Number.isFinite(value) || value <= 0) ||
    maximumVectorError(dimensions, expectedDimensions) > transformTolerance
  ) {
    throw new Error(`${identity} collision ${collision.name} has invalid bounds.`);
  }
}

function disposeScene(scene) {
  scene.traverse((object) => {
    object.geometry?.dispose?.();
    const materials = Array.isArray(object.material)
      ? object.material
      : object.material
        ? [object.material]
        : [];
    for (const material of materials) {
      for (const value of Object.values(material)) {
        if (value?.isTexture) value.dispose();
      }
      material.dispose?.();
    }
  });
}

async function main() {
  const registryPath = resolve(releaseRoot, "registry.json");
  const registry = await readJson(registryPath, "registry.json");
  if (!Array.isArray(registry.entries) || registry.entries.length !== expectedAssetCount) {
    throw new Error(
      `Expected ${expectedAssetCount} registry entries, found ${registry.entries?.length ?? "invalid"}.`,
    );
  }

  const identities = new Set();
  const loader = new GLTFLoader();
  let maxBoundsErrorMeters = 0;
  let maxAnchorPositionErrorMeters = 0;
  let maxAnchorRotationErrorRadians = 0;
  let collisionCount = 0;

  for (const entry of registry.entries) {
    const identity = `${entry.asset.id}@${entry.asset.version}`;
    if (identities.has(identity)) throw new Error(`Duplicate registry entry: ${identity}.`);
    identities.add(identity);

    const manifestPath = releasePath(entry.manifest.uri);
    const manifestBytes = await readFile(manifestPath);
    requireDescriptor(manifestBytes, entry.manifest, `${identity} manifest`);
    const manifest = JSON.parse(manifestBytes.toString("utf8"));
    if (`${manifest.id}@${manifest.version}` !== identity) {
      throw new Error(`${identity} manifest has the wrong identity.`);
    }

    const runtime = manifest.artifacts.runtime;
    const glbBytes = await readFile(releasePath(runtime.uri));
    requireDescriptor(glbBytes, runtime, `${identity} runtime`);
    const arrayBuffer = glbBytes.buffer.slice(
      glbBytes.byteOffset,
      glbBytes.byteOffset + glbBytes.byteLength,
    );
    const gltf = await loader.parseAsync(arrayBuffer, "");
    try {
      gltf.scene.updateMatrixWorld(true);
      const bounds = new THREE.Box3().setFromObject(gltf.scene, true);
      if (bounds.isEmpty()) throw new Error(`${identity} runtime has empty bounds.`);
      const error = maximumBoundsError(bounds, manifest.bounds_m);
      maxBoundsErrorMeters = Math.max(maxBoundsErrorMeters, error);
      if (error > boundsToleranceMeters) {
        throw new Error(
          `${identity} runtime bounds differ from its manifest by ${error} meters.`,
        );
      }

      const geometry = runtimeGeometry(gltf.scene, gltf.parser.json);
      for (const field of ["vertex_count", "triangle_count", "material_count"]) {
        if (geometry[field] !== manifest.geometry[field]) {
          throw new Error(
            `${identity} runtime ${field} is ${geometry[field]}, manifest says ${manifest.geometry[field]}.`,
          );
        }
      }

      for (const anchor of manifest.anchors) {
        const object = gltf.scene.getObjectByName(anchor.name);
        if (!object) throw new Error(`${identity} runtime is missing ${anchor.name}.`);
        const position = object.getWorldPosition(new THREE.Vector3());
        const quaternion = object.getWorldQuaternion(new THREE.Quaternion());
        const positionError = maximumVectorError(position.toArray(), anchor.position_m);
        const rotationError = quaternion.angleTo(
          new THREE.Quaternion().fromArray(anchor.rotation_xyzw),
        );
        maxAnchorPositionErrorMeters = Math.max(
          maxAnchorPositionErrorMeters,
          positionError,
        );
        maxAnchorRotationErrorRadians = Math.max(
          maxAnchorRotationErrorRadians,
          rotationError,
        );
        if (positionError > transformTolerance || rotationError > transformTolerance) {
          throw new Error(`${identity} runtime transform differs for ${anchor.name}.`);
        }
      }

      if (manifest.collisions.length === 0) {
        throw new Error(`${identity} must demonstrate at least one collision box.`);
      }
      for (const collision of manifest.collisions) {
        requireCollision(collision, identity);
        collisionCount += 1;
      }
    } finally {
      disposeScene(gltf.scene);
    }
  }

  if (collisionCount !== expectedCollisionCount) {
    throw new Error(
      `Expected ${expectedCollisionCount} collision boxes, found ${collisionCount}.`,
    );
  }

  console.log(
    JSON.stringify({
      assets: identities.size,
      collisions: collisionCount,
      boundsToleranceMeters,
      maxBoundsErrorMeters,
      maxAnchorPositionErrorMeters,
      maxAnchorRotationErrorRadians,
      releaseRoot,
    }),
  );
}

await main();
