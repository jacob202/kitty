import type { Metadata } from "next";
import "./globals.css";

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
          href="https://fonts.googleapis.com/css2?family=VT323&family=JetBrains+Mono:wght@400;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body style={{ height: '100%' }}>{children}</body>
    </html>
  );
}
