import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import "highlight.js/styles/github-dark.css";
import { Providers } from "./providers";

const display = Bricolage_Grotesque({
  subsets: ["latin"],
  weight: ["700", "800"],
  variable: "--font-display",
});
const body = Hanken_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

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
  themeColor: "#0A0F1F",
  colorScheme: "light dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      data-theme="cosmic"
      className={`${display.variable} ${body.variable} ${mono.variable}`}
      style={{ height: '100%' }}
    >
      <body style={{ height: '100%' }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
