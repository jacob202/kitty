import type { Metadata, Viewport } from "next";
import "./globals.css";
import "highlight.js/styles/github-dark.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Kitty",
  description: "Your personal AI companion",
  applicationName: "Kitty",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Kitty",
  },
  icons: {
    icon: [
      { url: "/app-icons/kitty-192.png", sizes: "192x192", type: "image/png" },
      { url: "/app-icons/kitty-512.png", sizes: "512x512", type: "image/png" },
      { url: "/kitty-mark.svg", type: "image/svg+xml" },
    ],
    apple: [
      { url: "/app-icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
    shortcut: ["/kitty-mark.svg"],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#F7F8FC",
  colorScheme: "light dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      data-theme="cosmic"
      style={{ height: '100%' }}
    >
      <body style={{ height: '100%' }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
