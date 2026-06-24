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
      { url: "/mascots/kitty-mission.png", sizes: "1024x1024", type: "image/png" },
      { url: "/kitty-mark.svg", type: "image/svg+xml" },
    ],
    apple: [
      { url: "/mascots/kitty-mission.png", sizes: "1024x1024", type: "image/png" },
    ],
    shortcut: ["/kitty-mark.svg"],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0f0f14",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" style={{ height: '100%' }}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body style={{ height: '100%' }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
