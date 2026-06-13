import type { Metadata, Viewport } from "next";

import { Disclaimer } from "@optera/ui";

import { SiteNav } from "@/components/site-nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "Optera — Options Risk & Analytics Co-Pilot",
  description:
    "See your F&O risk clearly. Live Greeks, payoff, scenarios, and an AI co-pilot that explains and watches your book in Hinglish. Education & analytics only — not advice.",
};

export const viewport: Viewport = {
  themeColor: "#0b1220",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen">
        <SiteNav />
        <main className="container py-6">{children}</main>
        <footer className="border-t border-border">
          <div className="container py-5">
            <Disclaimer variant="footer" />
          </div>
        </footer>
      </body>
    </html>
  );
}
