import Link from "next/link";
import { AlertCircle, Check, CheckCircle2, Info, TriangleAlert } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export { cx };

type BtnVariant = "primary" | "secondary" | "ghost" | "danger";
const btn: Record<BtnVariant, string> = {
  primary: "bg-accent text-accent-ink shadow-[0_1px_2px_rgb(8_99_107/0.25)] hover:bg-accent-strong disabled:opacity-40 disabled:shadow-none disabled:hover:bg-accent",
  secondary: "bg-surface text-ink border border-line shadow-[0_1px_2px_rgb(16_42_54/0.04)] hover:border-accent/40 hover:bg-accent-soft/50 disabled:opacity-50",
  ghost: "text-muted hover:text-ink hover:bg-surface-2",
  danger: "bg-surface text-danger border border-line hover:border-danger/30 hover:bg-danger-soft",
};

export function Button({ variant = "primary", className, ...p }: ComponentProps<"button"> & { variant?: BtnVariant }) {
  return (
    <button
      {...p}
      className={cx(
        "inline-flex h-10 items-center justify-center gap-2 rounded-[10px] px-4 text-[14px] font-medium transition-colors disabled:cursor-not-allowed",
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
      className={cx("inline-flex h-10 items-center justify-center gap-2 rounded-[10px] px-4 text-[14px] font-medium transition-colors", btn[variant], className)}
    >
      {children}
    </Link>
  );
}

export function Card({ className, ...p }: ComponentProps<"section">) {
  return <section {...p} className={cx("rounded-[18px] border border-line bg-surface shadow-card", className)} />;
}

export function CardHeader({ title, meta, action, icon }: { title: ReactNode; meta?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
      <div className="flex min-w-0 items-center gap-3">
        {icon && <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-accent-soft text-accent">{icon}</span>}
        <div className="min-w-0">
          <h2 className="truncate text-[17px] font-semibold leading-6 tracking-[-0.01em] text-ink">{title}</h2>
          {meta && <div className="mt-0.5 text-[13px] text-muted">{meta}</div>}
        </div>
      </div>
      {action}
    </div>
  );
}

type Tone = "neutral" | "accent" | "warn" | "danger" | "sim" | "buoy";
const tones: Record<Tone, string> = {
  neutral: "bg-surface-2 text-muted",
  accent: "bg-accent-soft text-accent",
  warn: "bg-warn-soft text-warn",
  danger: "bg-danger-soft text-danger",
  sim: "bg-sim-soft text-sim",
  buoy: "bg-buoy-soft text-ink",
};

export function Chip({ tone = "neutral", className, children, title }: { tone?: Tone; className?: string; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={cx("inline-flex h-6 items-center gap-1 whitespace-nowrap rounded-full px-2.5 text-[12px] font-medium", tones[tone], className)}>
      {children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-[14px] bg-surface-2", className)} />;
}

const CALLOUT_ICON: Partial<Record<Tone, typeof Info>> = { warn: TriangleAlert, danger: AlertCircle, accent: CheckCircle2, neutral: Info, sim: Info };

export function Callout({ tone = "warn", title, children }: { tone?: Tone; title: ReactNode; children?: ReactNode }) {
  const Icon = CALLOUT_ICON[tone] ?? Info;
  return (
    <div role="status" className={cx("flex gap-3 rounded-[14px] px-4 py-3", tones[tone])}>
      <Icon size={17} strokeWidth={2} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        <div className="text-[14px] font-semibold">{title}</div>
        {children && <div className="mt-0.5 text-[14px] text-ink/80">{children}</div>}
      </div>
    </div>
  );
}

// Initials get one of a few soft sea colours, picked from the letters, so people are easy to tell apart.
const AVATAR_TONES = [
  "bg-accent-soft text-accent",
  "bg-buoy-soft text-[#8a5a00]",
  "bg-sim-soft text-sim",
  "bg-[#e6f0fb] text-[#2f6aa8]",
  "bg-[#fbe9ef] text-[#b03a67]",
  "bg-[#e7f5ea] text-[#2f7d45]",
];

export function Avatar({ initials, demo, size = 32 }: { initials: string; demo?: boolean; size?: number }) {
  const tone = AVATAR_TONES[[...initials].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR_TONES.length];
  return (
    <span
      aria-hidden
      data-demo={demo || undefined}
      style={{ width: size, height: size, fontSize: Math.max(11, Math.round(size * 0.36)) }}
      className={cx("inline-flex shrink-0 items-center justify-center rounded-full font-semibold ring-2 ring-surface", tone)}
    >
      {initials}
    </span>
  );
}

export function PageTitle({ eyebrow, title, children, action }: { eyebrow?: ReactNode; title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1.5 text-[13px] text-muted">{eyebrow}</div>}
        <h1 className="text-[30px] font-semibold leading-[36px] tracking-[-0.025em] sm:text-[36px] sm:leading-[42px]">{title}</h1>
        {children && <div className="mt-2 max-w-2xl text-[15px] leading-6 text-muted">{children}</div>}
      </div>
      {action}
    </div>
  );
}

/** A row of tabs. Works the same on phones and desktops; scrolls sideways if it runs out of room. */
export function Tabs<T extends string>({
  value, onChange, items, className, label,
}: {
  value: T;
  onChange: (v: T) => void;
  items: { key: T; label: ReactNode; icon?: ReactNode; count?: number; className?: string }[];
  className?: string;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className={cx("no-scrollbar flex gap-1 overflow-x-auto rounded-[14px] border border-line bg-surface p-1 shadow-card", className)}>
      {items.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={value === t.key}
          onClick={() => onChange(t.key)}
          className={cx(
            "inline-flex h-9 shrink-0 items-center gap-2 rounded-[10px] px-3.5 text-[14px] font-medium transition-colors",
            value === t.key ? "bg-accent-soft text-accent" : "text-muted hover:bg-surface-2 hover:text-ink",
            t.className,
          )}
        >
          {t.icon}
          {t.label}
          {t.count != null && t.count > 0 && (
            <span className={cx("num rounded-full px-1.5 text-[11px] leading-[18px]", value === t.key ? "bg-accent text-accent-ink" : "bg-surface-2 text-muted")}>{t.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}

/** Where you are in the four-step trip flow: describe, review, who's going, the deal. */
export const FLOW = ["Describe it", "Check the details", "Who's going", "Agents make the deal"] as const;

export function FlowSteps({ at }: { at: number }) {
  return (
    <ol className="no-scrollbar mb-6 flex items-center gap-2 overflow-x-auto" aria-label="Trip steps">
      {FLOW.map((label, i) => {
        const done = i < at;
        const current = i === at;
        return (
          <li key={label} className="flex shrink-0 items-center gap-2" aria-current={current ? "step" : undefined}>
            {i > 0 && <span className={cx("h-px w-6 sm:w-10", done || current ? "bg-accent" : "bg-line")} aria-hidden />}
            <span
              className={cx(
                "inline-flex h-7 w-7 items-center justify-center rounded-full text-[12px] font-semibold",
                done ? "bg-accent text-accent-ink" : current ? "bg-accent-soft text-accent ring-2 ring-accent" : "bg-surface-2 text-muted",
              )}
            >
              {done ? <Check size={14} strokeWidth={2.5} /> : i + 1}
            </span>
            <span className={cx("text-[13px] font-medium", current ? "text-ink" : "text-muted", !current && "hidden sm:inline")}>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
