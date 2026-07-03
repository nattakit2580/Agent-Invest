import { defineCloudflareConfig } from "@opennextjs/cloudflare";

// This app is fully dynamic / client-rendered (no ISR), so no incremental cache
// override is needed. Add an R2 incremental cache here later if you introduce ISR.
export default defineCloudflareConfig({});
