import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // A verification build must never write into the .next the running UI is
  // serving from. `output: "standalone"` regenerates .next/standalone without
  // static/ or public/ — start_ui.sh mirrors those back in afterwards, a plain
  // `next build` does not. So a pre-push build against the live directory left
  // every chunk 500ing until the UI was restarted. Gates verify; they do not
  // mutate runtime state.
  distDir: process.env.KITTY_NEXT_DIST_DIR || ".next",
  // Next 16 blocks dev-only HMR and font assets requested from the Tailnet
  // origin. Kitty's UI is intentionally reachable from a phone over Tailscale.
  allowedDevOrigins: ["100.84.78.1", "**.ts.net"],
};

export default nextConfig;
