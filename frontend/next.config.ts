import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next writes frontend/AGENTS.md and CLAUDE.md on every dev start. They would compete with the
  // root AGENTS.md / CLAUDE.md (AGENTS.md hard rule 9), so the generator stays off.
  agentRules: false,
};

export default nextConfig;
