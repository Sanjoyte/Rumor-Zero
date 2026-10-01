import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests against both real servers: Django on 127.0.0.1:8000 and Next on localhost:3000, with
 * the API relay between them. Locally this needs `docker compose up -d` (Postgres + Redis) and a
 * backend virtualenv. A server that is already running is reused outside CI.
 */
const CI = Boolean(process.env.CI);
const BACKEND_ORIGIN = "http://127.0.0.1:8000";
const backendDir = path.resolve(__dirname, "../backend");
// An absolute path, built per platform: cmd.exe misreads forward slashes in a program path.
const python =
  process.platform === "win32"
    ? path.join(backendDir, ".venv", "Scripts", "python.exe")
    : path.join(backendDir, ".venv", "bin", "python");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  reporter: CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${python}" manage.py migrate --noinput && "${python}" manage.py runserver 127.0.0.1:8000 --noreload`,
      cwd: backendDir,
      url: `${BACKEND_ORIGIN}/api/health/`,
      reuseExistingServer: !CI,
      timeout: 120_000,
    },
    {
      // CI tests the production build (`npm run build` runs first); locally the dev server.
      command: CI ? "npm run start" : "npm run dev",
      // Ready only when the relay reaches Django.
      url: "http://localhost:3000/api/health/",
      // The process env wins over .env.local, so the relay always targets this Django.
      env: { BACKEND_ORIGIN },
      reuseExistingServer: !CI,
      timeout: 180_000,
    },
  ],
});
