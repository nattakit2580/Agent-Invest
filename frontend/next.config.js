/** @type {import('next').NextConfig} */
const nextConfig = {
  // This repository may live below a home directory containing another
  // lockfile. Pin the trace root so Next does not package files above frontend/.
  outputFileTracingRoot: __dirname,
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
