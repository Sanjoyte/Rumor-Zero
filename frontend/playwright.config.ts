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
      // In-memory cache, so every run starts with empty allauth rate-limit counters. Emails go to
      // backend/tmp/mail/ (git-ignored), where e2e/mailbox.ts reads them. The process env wins over
      // backend/.env, so this holds in CI and locally. A reused `runserver` must also use "file"
      // and the kick off (below).
      // No Google client ID: "Continue with Google" is a 404 here, and the tests never reach Google.
      // The fact-check pipeline is the stub and checks nothing by itself (no inline kick): tests
      // expect a new fact to stay CHECKING FACTS…, and the one that wants a verdict runs the
      // pipeline for its own post (`processPost` in e2e/helpers.ts).
      env: {
        REDIS_URL: "",
        EMAIL_PROVIDER: "file",
        GOOGLE_OAUTH_CLIENT_ID: "",
        PIPELINE_BACKEND: "stub",
        PIPELINE_INLINE_KICK: "False",
      },
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
      // The Google button is hidden too (a local .env.local may hold a real client ID).
      env: { BACKEND_ORIGIN, NEXT_PUBLIC_GOOGLE_CLIENT_ID: "" },
      reuseExistingServer: !CI,
      timeout: 180_000,
    },
  ],
});
