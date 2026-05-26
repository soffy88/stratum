import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://localhost:9302/api/:path*" },
      { source: "/share/:token", destination: "http://localhost:9302/share/:token" },
    ];
  },
};
export default config;
