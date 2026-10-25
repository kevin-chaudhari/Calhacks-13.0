import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "@fontsource-variable/bricolage-grotesque";
import "./globals.css";
import { Providers } from "./providers";
import { AppHeader } from "@/components/rally/shell";

export const metadata: Metadata = {
  title: "Parley",
  description: "Say what you want to do. Your agent finds people to go with, or goes alone, and negotiates the deal with the shops.",
};

export const viewport: Viewport = { themeColor: "#ffffff", colorScheme: "light" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <body className="min-h-dvh font-sans">
        <Providers>
          <AppHeader />
          <main className="mx-auto max-w-[1280px] px-4 pb-24 pt-6 sm:px-6 sm:pt-10">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
