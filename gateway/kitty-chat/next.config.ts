import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Next 16 blocks dev-only HMR and font assets requested from the Tailnet
  // origin. Kitty's UI is intentionally reachable from a phone over Tailscale.
  allowedDevOrigins: ["100.84.78.1", "**.ts.net"],
};

export default nextConfig;
