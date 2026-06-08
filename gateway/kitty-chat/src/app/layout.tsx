import type { Metadata } from "next";
import "./globals.css";
import "highlight.js/styles/github-dark.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Kitty",
  description: "Your personal AI companion",
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
