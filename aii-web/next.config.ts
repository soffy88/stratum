import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // @helios/blocks 用 "use client" 文件 + RSC,转译以避免 ESM/CJS 互操作问题
  transpilePackages: ['@helios/blocks', '@helios/oui'],
};

export default nextConfig;
