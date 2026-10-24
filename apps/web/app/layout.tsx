import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { Providers } from "./providers";
import { AppHeader } from "@/components/rally/shell";

export const metadata: Metadata = {
  title: "Rally",
  description: "Your agents find your people, agree on the plan, and turn shared goals into group deals.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <body className="min-h-dvh font-sans">
        <Providers>
          <AppHeader />
          <main className="mx-auto max-w-[1280px] px-4 pb-24 pt-8 sm:px-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
