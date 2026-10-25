"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Compass, MonitorPlay, Newspaper, Store, Tag, Tags, UserRound, Inbox } from "lucide-react";
import { usePersona } from "@/lib/persona";
import { STATUS_LABEL } from "@/lib/format";
import { Chip, cx } from "@/components/ui/primitives";

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2" aria-label="Parley home">
      {/* Two signal pennants meeting: yours and theirs, at the table. */}
      <svg width="26" height="22" viewBox="0 0 26 22" aria-hidden>
        <path d="M3 2v19M23 2v19" stroke="var(--ink)" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M3.8 3h8.6l-3.2 3.5 3.2 3.5H3.8z" fill="var(--accent)" />
        <path d="M22.2 3h-8.6l3.2 3.5-3.2 3.5h8.6z" fill="var(--buoy)" />
      </svg>
      <span className="display text-[21px] font-semibold tracking-[-0.03em]">Parley</span>
    </Link>
  );
}

function IdentitySwitcher({ vendorSide }: { vendorSide: boolean }) {
  const { personas, me, vendor, choose, chooseVendor, error } = usePersona();
  if (error) return <Chip tone="danger" title={error}>API offline</Chip>;
  const list = personas.filter((p) => (vendorSide ? p.role === "vendor" : p.role === "customer" && !p.id.startsWith("c_") && (p.isTeammate || p.isDemoPersona)));
  const current = vendorSide ? vendor : me;
  return (
    <label className="flex items-center gap-2 text-[13px]">
      <span className="hidden text-muted lg:inline">{vendorSide ? "Staff" : "You are"}</span>
      <span className="relative inline-flex items-center">
        <UserRound size={14} strokeWidth={1.75} className="pointer-events-none absolute left-3 text-accent" />
        <select
          aria-label={vendorSide ? "Vendor staff" : "Signed in as"}
          value={current?.id ?? ""}
          onChange={(e) => (vendorSide ? chooseVendor(e.target.value) : choose(e.target.value))}
          className="h-9 max-w-[150px] cursor-pointer appearance-none rounded-full border border-line bg-surface pl-8 pr-4 text-[13px] font-medium hover:border-accent/40 sm:max-w-[220px]"
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
  const { me } = usePersona();
  const vendorSide = path.startsWith("/vendor");
  const nav = vendorSide
    ? [
        { href: "/vendor", label: "Requests", icon: Inbox, exact: true },
        { href: "/vendor/pricing", label: "Agent & pricing", icon: Tags },
        { href: "/", label: "Traveller app", icon: Compass, exact: true },
      ]
    : [
        { href: "/", label: "Plan a trip", icon: Compass, exact: true },
        { href: "/explore", label: "Explore", icon: Newspaper },
        { href: "/discover", label: "Find deals", icon: Tag },
        { href: "/diagnostics", label: "Agents", icon: Bot },
        { href: "/vendor", label: "For shops", icon: Store },
        { href: "/demo", label: "Demo", icon: MonitorPlay },
        ...(me ? [{ href: `/people/${me.id}`, label: "Profile", icon: UserRound }] : []),
      ];
  const isOn = (n: (typeof nav)[number]) => (n.exact ? path === n.href : path.startsWith(n.href));
  const links = (mobile: boolean) =>
    nav.map((n) => (
      <Link
        key={n.href}
        href={n.href}
        aria-current={isOn(n) ? "page" : undefined}
        className={cx(
          "inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[14px] font-medium transition-colors",
          isOn(n) ? "bg-accent-soft text-accent" : "text-muted hover:bg-surface-2 hover:text-ink",
          mobile && "text-[13px]",
        )}
      >
        <n.icon size={15} strokeWidth={1.9} />
        {n.label}
      </Link>
    ));
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center gap-3 px-4 sm:gap-6 sm:px-6">
        <div className="flex items-center gap-2">
          <Logo />
          {vendorSide && <Chip tone="accent" className="hidden sm:inline-flex">for shops</Chip>}
        </div>
        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">{links(false)}</nav>
        <div className="ml-auto flex min-w-0 items-center gap-2">
          <IdentitySwitcher vendorSide={vendorSide} />
        </div>
      </div>
      {/* Phones: the same links in a row you can swipe, so nothing hides behind a menu. */}
      <nav aria-label="Main" className="no-scrollbar flex gap-1 overflow-x-auto border-t border-line px-3 py-2 md:hidden">{links(true)}</nav>
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
  if (kind === "cached") return <Chip tone="neutral" title="Taken from the vendor's public listing (Apify). The vendor's agent still has to quote.">Listed price, not a quote</Chip>;
  return <Chip tone="sim" title="Generated by a seeded provider agent from a fixture price table">Simulated</Chip>;
}
