import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const projectRoot = new URL("../", import.meta.url);

test("the workspace and client package carry the repository MIT license", async () => {
  const [rootLicense, clientLicense, rootPackageText, clientPackageText] = await Promise.all([
    readFile(new URL("LICENSE", projectRoot), "utf8"),
    readFile(new URL("packages/client/LICENSE", projectRoot), "utf8"),
    readFile(new URL("package.json", projectRoot), "utf8"),
    readFile(new URL("packages/client/package.json", projectRoot), "utf8"),
  ]);
  const rootPackage = JSON.parse(rootPackageText);
  const clientPackage = JSON.parse(clientPackageText);

  assert.equal(clientLicense, rootLicense);
  assert.equal(rootPackage.license, "MIT");
  assert.equal(clientPackage.license, "MIT");
  assert.ok(clientPackage.files.includes("LICENSE"));
});

test("the deployed website carries repository and three.js license notices", async () => {
  const [rootLicense, threeLicense, viteLicense, notices, index, sitePackageText] =
    await Promise.all([
      readFile(new URL("LICENSE", projectRoot), "utf8"),
      readFile(new URL("examples/room-zero/node_modules/three/LICENSE", projectRoot), "utf8"),
      readFile(new URL("examples/room-zero/node_modules/vite/LICENSE.md", projectRoot), "utf8"),
      readFile(
        new URL("examples/room-zero/public/THIRD_PARTY_NOTICES.txt", projectRoot),
        "utf8",
      ),
      readFile(new URL("examples/room-zero/index.html", projectRoot), "utf8"),
      readFile(new URL("examples/room-zero/package.json", projectRoot), "utf8"),
    ]);
  const viteCoreLicense = viteLicense
    .split("# Licenses of bundled dependencies", 1)[0]
    .split("Vite is released under the MIT license:", 2)[1]
    .trim();

  assert.ok(notices.includes(rootLicense.trim()));
  assert.ok(notices.includes(threeLicense.trim()));
  assert.ok(notices.includes(viteCoreLicense));
  assert.match(index, /href="\/THIRD_PARTY_NOTICES\.txt"/);
  assert.equal(JSON.parse(sitePackageText).license, "MIT");
});
