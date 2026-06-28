import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Raise the proxied-request body cap (default 10MB) so real scRNA .h5ad uploads
  // pass through the /api rewrite — the pbmc3k demo alone is ~21MB. Next buffers the
  // body in memory per request, so this is a pragmatic dev/P0 limit, not unbounded.
  // Production should move large-file uploads off the in-memory proxy buffer
  // (direct-to-backend or chunked/presigned). See agent_handoff/RISKS.md.
  experimental: {
    proxyClientMaxBodySize: "512mb",
  },
  async rewrites() {
    // The backend URL is env-configurable so local dogfood can target a non-:8000 port and step-8
    // deploy can point at the deployed API, with the :8000 default unchanged for the normal inner loop.
    const target = process.env.API_PROXY_TARGET || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${target}/:path*`,
      },
    ];
  },
};

export default nextConfig;
