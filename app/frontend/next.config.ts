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
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
