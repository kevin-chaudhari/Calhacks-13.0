"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Moon, Sun, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { usePersona } from "@/lib/persona";
import { STATUS_LABEL } from "@/lib/format";
import { Chip, cx } from "@/components/ui/primitives";

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2" aria-label="Rally home">
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
        <circle cx="4" cy="5" r="2.5" fill="var(--muted)" />
        <circle cx="18" cy="5" r="2.5" fill="var(--muted)" />
        <circle cx="11" cy="19" r="2.5" fill="var(--muted)" />
        <path d="M5.8 6.6 10 10.4M16.2 6.6 12 10.4M11 16.4V12.6" stroke="var(--muted)" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="11" cy="11" r="3.2" fill="var(--accent)" />
      </svg>
      <span className="text-[17px] font-semibold tracking-[-0.02em]">Rally</span>
    </Link>
  );
}

function ThemeToggle() {
  const [dark, setDark] = useState<boolean | null>(null);
  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem("rally.theme");
    } catch {}
    const isDark = saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    setDark(isDark);
    document.documentElement.dataset.theme = isDark ? "dark" : "light";
  }, []);
  const flip = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    try {
      localStorage.setItem("rally.theme", next ? "dark" : "light");
    } catch {}
  };
  return (
    <button onClick={flip} className="rounded-[6px] p-2 text-muted hover:bg-surface-2 hover:text-ink" aria-label="Toggle dark mode">
      {dark ? <Sun size={16} strokeWidth={1.75} /> : <Moon size={16} strokeWidth={1.75} />}
    </button>
  );
}

function IdentitySwitcher({ vendorSide }: { vendorSide: boolean }) {
  const { personas, me, vendor, choose, chooseVendor, error } = usePersona();
  if (error) return <Chip tone="danger" title={error}>API offline</Chip>;
  const list = personas.filter((p) => (vendorSide ? p.role === "vendor" : p.role === "customer" && (p.isTeammate || p.isDemoPersona)));
  const current = vendorSide ? vendor : me;
  return (
    <label className="flex items-center gap-2 text-[13px]">
      <span className="hidden text-muted md:inline">{vendorSide ? "Staff" : "Signed in as"}</span>
      <span className="relative inline-flex items-center">
        <UserRound size={14} strokeWidth={1.75} className="pointer-events-none absolute left-2 text-muted" />
        <select
          aria-label={vendorSide ? "Vendor staff" : "Signed in as"}
          value={current?.id ?? ""}
          onChange={(e) => (vendorSide ? chooseVendor(e.target.value) : choose(e.target.value))}
          className="h-8 max-w-[140px] appearance-none sm:max-w-[220px] rounded-[6px] border border-line bg-surface pl-7 pr-3 text-[13px] font-medium"
        >
          {list.map((p) => (
            <option key={p.id} value={p.id}>
              {vendorSide ? `${p.name} · ${p.title}` : p.name}
            </option>
          ))}
        </select>
      </span>
    </label>
  );
}

export function AppHeader() {
  const path = usePathname();
  const vendorSide = path.startsWith("/vendor");
  const nav = vendorSide
    ? [
        { href: "/vendor", label: "Requests", exact: true },
        { href: "/vendor/pricing", label: "Agent & pricing" },
        { href: "/", label: "Customer app", exact: true },
      ]
    : [
        { href: "/", label: "Goals", exact: true },
        { href: "/diagnostics", label: "Agents" },
        { href: "/vendor", label: "Vendor portal" },
      ];
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-bg/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1280px] items-center gap-3 px-4 sm:gap-6 sm:px-6">
        <div className="flex items-center gap-2">
          <Logo />
          {vendorSide && <Chip tone="accent" className="hidden sm:inline-flex">for vendors</Chip>}
        </div>
        <nav className="hidden items-center gap-1 sm:flex">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={cx(
                "rounded-[6px] px-2.5 py-1.5 text-[13px] font-medium",
                (n.exact ? path === n.href : path.startsWith(n.href)) ? "text-ink" : "text-muted hover:text-ink",
              )}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex min-w-0 items-center gap-1 sm:gap-2">
          <IdentitySwitcher vendorSide={vendorSide} />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

export function StatusPill({ status, detail }: { status: string; detail?: string }) {
  const tone =
    status === "COMMITTED" || status === "published"
      ? "accent"
      : status === "NO_AGREEMENT" || status === "FAILED" || status === "CANCELLED" || status === "EXPIRED"
        ? "danger"
        : status === "AWAITING_APPROVAL" || status === "needs_input"
          ? "warn"
          : "neutral";
  return (
    <Chip tone={tone}>
      {STATUS_LABEL[status] ?? status}
      {detail && <span className="num opacity-80">{detail}</span>}
    </Chip>
  );
}

/** Always-visible honesty label (plan 7.6). */
export function ProvenanceBadge({ kind }: { kind: "simulated" | "cached" | "live" | string }) {
  if (kind === "live") return <Chip tone="accent">Live</Chip>;
  if (kind === "cached") return <Chip tone="neutral" title="Listed price, not a quote">Listed price</Chip>;
  return <Chip tone="sim" title="Generated by a seeded provider agent from a fixture price table">Simulated</Chip>;
}
