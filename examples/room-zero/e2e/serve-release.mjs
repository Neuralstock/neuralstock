import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, extname, isAbsolute, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const exampleRoot = resolve(scriptDirectory, "..");
const viewerRoot = resolve(exampleRoot, "dist");
const configuredRelease =
  process.env.NEURALSTOCK_RELEASE_DIR ?? resolve(exampleRoot, "../../dist/release");
const releaseRoot = isAbsolute(configuredRelease)
  ? resolve(configuredRelease)
  : resolve(process.cwd(), configuredRelease);
const registryPath = resolve(releaseRoot, "registry.json");
const port = Number.parseInt(process.env.NEURALSTOCK_E2E_PORT ?? "4173", 10);

if (!Number.isInteger(port) || port < 1 || port > 65_535) {
  throw new Error(`NEURALSTOCK_E2E_PORT must be a valid port; received ${String(port)}.`);
}
if (!existsSync(resolve(viewerRoot, "index.html"))) {
  throw new Error(`Room Zero is not built. Expected ${resolve(viewerRoot, "index.html")}.`);
}
if (!existsSync(registryPath)) {
  throw new Error(
    `A published NeuralStock release is required. Expected ${registryPath}. ` +
      "Set NEURALSTOCK_RELEASE_DIR to a release containing registry.json and objects/.",
  );
}

const mediaTypes = new Map([
  [".blend", "application/octet-stream"],
  [".css", "text/css; charset=utf-8"],
  [".glb", "model/gltf-binary"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".wasm", "application/wasm"],
]);

function safeFile(root, pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return undefined;
  }
  const candidate = resolve(root, `.${decoded}`);
  const relation = relative(root, candidate);
  if (relation === "" || relation.startsWith(`..${sep}`) || relation === "..") {
    return undefined;
  }
  try {
    return statSync(candidate).isFile() ? candidate : undefined;
  } catch {
    return undefined;
  }
}

function selectFile(pathname) {
  const published = safeFile(releaseRoot, pathname);
  if (published) return published;
  const viewerAsset = safeFile(viewerRoot, pathname);
  if (viewerAsset) return viewerAsset;
  const isAssetPage = /^\/asset\/[^/]+\/[^/]+\/?$/.test(pathname);
  return pathname === "/" || isAssetPage
    ? safeFile(viewerRoot, "/index.html")
    : undefined;
}

const server = createServer((request, response) => {
  const method = request.method ?? "GET";
  if (method !== "GET" && method !== "HEAD") {
    response.writeHead(405, { Allow: "GET, HEAD" }).end();
    return;
  }

  const requestUrl = new URL(request.url ?? "/", "http://127.0.0.1");
  const file = selectFile(requestUrl.pathname);
  if (!file) {
    response.writeHead(404, {
      "Cache-Control": "no-store",
      "Content-Type": "text/plain; charset=utf-8",
    });
    response.end("Not found");
    return;
  }

  const size = statSync(file).size;
  response.writeHead(200, {
    "Cache-Control": "no-store",
    "Content-Length": String(size),
    "Content-Type": mediaTypes.get(extname(file)) ?? "application/octet-stream",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
  });
  if (method === "HEAD") {
    response.end();
    return;
  }
  createReadStream(file).pipe(response);
});

server.listen(port, "127.0.0.1", () => {
  process.stdout.write(
    `Room Zero E2E server: http://127.0.0.1:${port} (release ${releaseRoot})\n`,
  );
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
