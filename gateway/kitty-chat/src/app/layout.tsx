import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kitty",
  description: "Your personal AI companion",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" style={{ height: '100%' }}>
      <body style={{ height: '100%' }}>{children}</body>
    </html>
  );
}
