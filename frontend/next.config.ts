
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  poweredByHeader: false,

  // Keep browser-side source maps disabled in production.
  productionBrowserSourceMaps: false,

  // Allow the application to be deployed behind a hosting platform.
  output: "standalone",
};

export default nextConfig;
