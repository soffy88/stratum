import type { NextConfig } from "next";

// STRATUM_API_BASE / STRATUM_SL_BASE: full URL for API rewrites.
// ⚠ Next bakes these at *build* time into routes-manifest.json.
// Production Docker must either:
//   1) build with STRATUM_API_BASE=http://stratum-api:9302 (and SL similarly), or
//   2) run deploy/aii-web-entrypoint.sh which rewrites localhost → service names at start.
// Runtime env alone does NOT update already-baked rewrites.
// STRATUM_API_PORT: port for the legacy DuckDB API (default 9302).
// STRATUM_SL_PORT:  port for the new service layer (default 9304).
// Tests override STRATUM_API_PORT to 9311 for an isolated uvicorn server.
const apiBase =
  process.env.STRATUM_API_BASE ??
  `http://localhost:${process.env.STRATUM_API_PORT ?? "9302"}`;
const slBase =
  process.env.STRATUM_SL_BASE ??
  `http://localhost:${process.env.STRATUM_SL_PORT ?? "9304"}`;
// P2: AII routes now served by Stratum SL under /api/aii/* (unified backend).
// The aiiBase points to slBase so all backend traffic goes through one process.
const aiiBase = slBase;

const config: NextConfig = {
  reactStrictMode: true,
  // AII merge P3.5: next build's type-check doesn't honour tsconfig `exclude` for the
  // ported (aii) pages, so @helios/blocks's .d.ts packaging incompat (see commit
  // fccda01) resurfaces. SWC still compiles everything correctly. Type safety for
  // Stratum's own code is gated separately by `pnpm type-check` (tsc honours exclude,
  // 0 errors); the AII pages run un-strict-checked exactly as they do in AII itself.
  typescript: { ignoreBuildErrors: true },
  // Standalone output for Docker — produces .next/standalone/server.js
  // with minimal node_modules (~40MB vs full node_modules ~500MB).
  output: "standalone",
  // AII merge P3.1: adopt the real @helios/blocks + @helios/oui design system
  // (vendored tarballs) instead of the local stub. These ship ESM/TS and must
  // be transpiled by Next.
  transpilePackages: ["@helios/blocks", "@helios/oui"],
  async redirects() {
    return [
      // 这两个页面不存在(导航已指向 /profile、/jobs);兜底旧链接/书签不再 404。
      { source: "/my", destination: "/profile", permanent: false },
      { source: "/tasks", destination: "/jobs", permanent: false },
    ];
  },
  async rewrites() {
    return [
      // AII epistemic-engine backend — must come before the catch-alls below.
      // AII's api-client paths already include the `/api` prefix (e.g.
      // /api/stats/overview), so forward verbatim — do NOT add another /api.
      { source: "/api/aii/:path*", destination: `${aiiBase}/:path*` },
      // Service layer (v1 routes) — must come before the catch-all below.
      { source: "/api/v1/:path*", destination: `${slBase}/api/v1/:path*` },
      // Legacy DuckDB API (auth, substrates, legacy notes/search, etc.)
      { source: "/api/:path*", destination: `${apiBase}/api/:path*` },
      // NOTE: /share/:token is a Next.js Server Component — no rewrite here.
    ];
  },
};
export default config;
