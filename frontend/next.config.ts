import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const nextConfig: NextConfig = {
  // Next writes frontend/AGENTS.md and CLAUDE.md on every dev start. They would compete with the
  // root AGENTS.md / CLAUDE.md (AGENTS.md hard rule 9), so the generator stays off.
  agentRules: false,
  poweredByHeader: false,
  // Django's URLs end in "/". Next's built-in "/:path+/ -> /:path+" redirect would send
  // /api/health/ to /api/health, and Django's APPEND_SLASH would send it straight back.
  skipTrailingSlashRedirect: true,
  async redirects() {
    // Page URLs stay canonical without the slash (/home/ -> /home); the API relay keeps it.
    return [{ source: "/:path((?!api/).+)/", destination: "/:path", permanent: true }];
  },
};

export default async function config(phase: string): Promise<NextConfig> {
  // Gives `next dev` the Cloudflare bindings from wrangler.jsonc. Only the dev server needs it,
  // so `next build` and the OpenNext build never start workerd.
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    const { initOpenNextCloudflareForDev } = await import("@opennextjs/cloudflare");
    await initOpenNextCloudflareForDev();
  }
  return nextConfig;
}
