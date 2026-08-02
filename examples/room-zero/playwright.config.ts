import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

const host = "127.0.0.1";
const port = Number.parseInt(process.env.NEURALSTOCK_E2E_PORT ?? "4173", 10);
const artifactsRoot = fileURLToPath(
  new URL("../../output/playwright", import.meta.url),
);

export default defineConfig({
  testDir: "./e2e",
  outputDir: `${artifactsRoot}/results`,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [["line"], ["html", { outputFolder: `${artifactsRoot}/report`, open: "never" }]]
    : "line",
  timeout: 45_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: `http://${host}:${port}`,
    browserName: "chromium",
    launchOptions: {
      args: ["--enable-webgl", "--ignore-gpu-blocklist", "--use-angle=swiftshader"],
    },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: "narrow-chromium",
      use: {
        hasTouch: true,
        isMobile: true,
        viewport: { width: 390, height: 844 },
      },
    },
  ],
  webServer: {
    command: "node ./e2e/serve-release.mjs",
    env: {
      NEURALSTOCK_E2E_PORT: String(port),
      ...(process.env.NEURALSTOCK_RELEASE_DIR
        ? { NEURALSTOCK_RELEASE_DIR: process.env.NEURALSTOCK_RELEASE_DIR }
        : {}),
    },
    port,
    reuseExistingServer: false,
    timeout: 10_000,
  },
});
