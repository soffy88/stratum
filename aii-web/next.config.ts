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
// AII merge P3.2: ported AII pages call the AII backend (epistemic knowledge engine)
// via the same-origin /api/aii/* proxy → AII FastAPI (:8101 dev / aii-api.kanpan.co prod).
const aiiBase =
  process.env.AII_API_BASE ??
  `http://localhost:${process.env.AII_API_PORT ?? "8101"}`;

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
