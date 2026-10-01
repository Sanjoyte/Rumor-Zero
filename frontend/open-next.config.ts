import { defineCloudflareConfig } from "@opennextjs/cloudflare";

// Default cache only: no R2 (free tier, no object storage; ARCHITECTURE §1).
export default defineCloudflareConfig();
