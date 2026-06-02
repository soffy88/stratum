import type { NextConfig } from "next";

// STRATUM_API_BASE / STRATUM_SL_BASE: full URL overrides for Docker environments.
// Falls back to localhost:{port} for host dev server and tests.
// STRATUM_API_PORT: port for the legacy DuckDB API (default 9302).
// STRATUM_SL_PORT:  port for the new service layer (default 9304).
// Tests override STRATUM_API_PORT to 9311 for an isolated uvicorn server.
const apiBase =
  process.env.STRATUM_API_BASE ??
  `http://localhost:${process.env.STRATUM_API_PORT ?? "9302"}`;
const slBase =
  process.env.STRATUM_SL_BASE ??
  `http://localhost:${process.env.STRATUM_SL_PORT ?? "9304"}`;

const config: NextConfig = {
  reactStrictMode: true,
  // Standalone output for Docker — produces .next/standalone/server.js
  // with minimal node_modules (~40MB vs full node_modules ~500MB).
  output: "standalone",
  async rewrites() {
    return [
      // Service layer (v1 routes) — must come before the catch-all below.
      { source: "/api/v1/:path*", destination: `${slBase}/api/v1/:path*` },
      // Legacy DuckDB API (auth, substrates, legacy notes/search, etc.)
      { source: "/api/:path*", destination: `${apiBase}/api/:path*` },
      // NOTE: /share/:token is a Next.js Server Component — no rewrite here.
    ];
  },
};
export default config;
