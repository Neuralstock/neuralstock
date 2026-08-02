#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import validator from "gltf-validator";

function usage() {
  process.stderr.write("usage: node tools/validate-gltf.mjs MODEL.glb\n");
}

async function main() {
  const [modelPath, ...extra] = process.argv.slice(2);
  if (!modelPath || extra.length > 0) {
    usage();
    process.exitCode = 64;
    return;
  }

  try {
    const bytes = await readFile(modelPath);
    const report = await validator.validateBytes(new Uint8Array(bytes), {
      format: "glb",
      maxIssues: 0,
      uri: basename(modelPath),
      writeTimestamp: false,
    });
    process.stdout.write(`${JSON.stringify(report)}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`glTF validation failed to run: ${message}\n`);
    process.exitCode = 1;
  }
}

void main();
