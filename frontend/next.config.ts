import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    serverActions: {
      bodySizeLimit: "100mb",
    },
  },
  middlewareClientMaxBodySize: 100 * 1024 * 1024,
  async rewrites() {
    // Docker(프로덕션)에선 nginx가 처리 — 개발 시에만 프록시
    if (process.env.NODE_ENV === "production") return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8088/api/:path*",
      },
    ];
  },
};

export default nextConfig;
