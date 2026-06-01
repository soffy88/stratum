import type { NextConfig } from "next";

// STRATUM_API_PORT: port for the legacy DuckDB API (default 9302).
// STRATUM_SL_PORT:  port for the new PostgreSQL service layer (default 9304).
// Tests override STRATUM_API_PORT to 9311 for an isolated uvicorn server.
const apiPort = process.env.STRATUM_API_PORT ?? "9302";
const slPort = process.env.STRATUM_SL_PORT ?? "9304";
const apiBase = `http://localhost:${apiPort}`;
const slBase = `http://localhost:${slPort}`;

const config: NextConfig = {
  reactStrictMode: true,
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
