import type { Metadata, Viewport } from "next";
import "./globals.css";
import "highlight.js/styles/github.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Kitty",
  description: "Your personal AI companion",
  applicationName: "Kitty",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
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
  themeColor: "#F3EAD6",
  colorScheme: "light dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="day" style={{ height: '100%' }}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body style={{ height: '100%' }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
