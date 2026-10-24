import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export { cx };

type BtnVariant = "primary" | "secondary" | "ghost" | "danger";
const btn: Record<BtnVariant, string> = {
  primary: "bg-accent text-accent-ink hover:brightness-110 disabled:opacity-50",
  secondary: "bg-surface text-ink border border-line hover:bg-surface-2 disabled:opacity-50",
  ghost: "text-muted hover:text-ink hover:bg-surface-2",
  danger: "bg-surface text-danger border border-line hover:bg-danger-soft",
};

export function Button({ variant = "primary", className, ...p }: ComponentProps<"button"> & { variant?: BtnVariant }) {
  return (
    <button
      {...p}
      className={cx(
        "inline-flex h-9 items-center justify-center gap-2 rounded-[6px] px-3.5 text-[13px] font-medium transition-colors disabled:cursor-not-allowed",
        btn[variant],
        className,
      )}
    />
  );
}

export function ButtonLink({ href, variant = "primary", className, children }: { href: string; variant?: BtnVariant; className?: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className={cx("inline-flex h-9 items-center justify-center gap-2 rounded-[6px] px-3.5 text-[13px] font-medium transition-colors", btn[variant], className)}
    >
      {children}
    </Link>
  );
}

export function Card({ className, ...p }: ComponentProps<"section">) {
  return <section {...p} className={cx("rounded-[10px] border border-line bg-surface", className)} />;
}

export function CardHeader({ title, meta, action }: { title: ReactNode; meta?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
      <div className="min-w-0">
        <h2 className="truncate text-[13px] font-semibold uppercase tracking-[0.06em] text-muted">{title}</h2>
        {meta && <div className="mt-0.5 text-[13px] text-muted">{meta}</div>}
      </div>
      {action}
    </div>
  );
}

type Tone = "neutral" | "accent" | "warn" | "danger" | "sim";
const tones: Record<Tone, string> = {
  neutral: "bg-surface-2 text-muted",
  accent: "bg-accent-soft text-accent",
  warn: "bg-warn-soft text-warn",
  danger: "bg-danger-soft text-danger",
  sim: "bg-sim-soft text-sim",
};

export function Chip({ tone = "neutral", className, children, title }: { tone?: Tone; className?: string; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={cx("inline-flex h-[22px] items-center gap-1 whitespace-nowrap rounded-full px-2 text-[12px] font-medium", tones[tone], className)}>
      {children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-[6px] bg-surface-2", className)} />;
}

export function Callout({ tone = "warn", title, children }: { tone?: Tone; title: ReactNode; children?: ReactNode }) {
  return (
    <div role="status" className={cx("rounded-[10px] border px-4 py-3", tones[tone], "border-transparent")}>
      <div className="text-[13px] font-semibold">{title}</div>
      {children && <div className="mt-1 text-[13px] text-ink/80">{children}</div>}
    </div>
  );
}

export function Avatar({ initials, demo, size = 32 }: { initials: string; demo?: boolean; size?: number }) {
  return (
    <span
      aria-hidden
      style={{ width: size, height: size }}
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-full text-[12px] font-semibold ring-2 ring-surface",
        "bg-accent-soft text-accent",
      )}
    >
      {initials}
    </span>
  );
}

export function PageTitle({ eyebrow, title, children }: { eyebrow?: ReactNode; title: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-6">
      {eyebrow && <div className="mb-1 text-[13px] text-muted">{eyebrow}</div>}
      <h1 className="text-[28px] font-semibold leading-[34px] tracking-[-0.01em]">{title}</h1>
      {children && <div className="mt-2 max-w-2xl text-muted">{children}</div>}
    </div>
  );
}
