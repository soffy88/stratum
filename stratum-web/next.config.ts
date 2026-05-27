import type { NextConfig } from "next";

// STRATUM_API_PORT: override the backend port for e2e browser tests.
// Default 9302 is the prod/dev Caddy gateway; tests pass 9311 for an
// isolated uvicorn server started by playwright.browser.config.ts.
const apiPort = process.env.STRATUM_API_PORT ?? "9302";
const apiBase = `http://localhost:${apiPort}`;

const config: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiBase}/api/:path*` },
      // NOTE: /share/:token is served by the Next.js Server Component at
      // app/share/[token]/page.tsx — do NOT add a rewrite here, it would
      // shadow the page and return raw JSON instead of rendered HTML.
    ];
  },
};
export default config;
