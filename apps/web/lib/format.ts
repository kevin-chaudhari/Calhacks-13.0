export const money = (n: number, cur = "USD") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n);

export const day = (iso: string) => {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
};

export const shortDay = (iso: string) => {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

export const time = (ms: number) =>
  new Date(ms).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });

export const TERM_LABELS: Record<string, string> = {
  date: "Date",
  site: "Dive site",
  dive_type: "Boat or shore",
  gear_included: "Gear",
  dropzone: "Drop zone",
  altitude: "Jump altitude",
  video_package: "Video package",
  launch: "Launch point",
  tour_type: "Tour",
  wetsuit_included: "Wetsuit",
  price_per_person: "Price per person",
  group_size: "Group size",
};

const BOOL_LABELS: Record<string, [string, string]> = {
  gear_included: ["Included", "Bring your own"],
  video_package: ["Photo + video", "No video"],
  wetsuit_included: ["Included", "Bring your own"],
};

export function termValue(key: string, v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (key === "date" && typeof v === "string") return day(v);
  if (typeof v === "boolean") return (BOOL_LABELS[key] ?? ["Yes", "No"])[v ? 0 : 1];
  if (key === "dive_type") return v === "boat" ? "Boat dive" : "Shore dive";
  if (key === "tour_type") return v === "guided" ? "Guided tour" : "Self-guided rental";
  if (key === "price_per_person" && typeof v === "number") return money(v);
  return String(v);
}

/** Date first, booleans last, everything else in between, alphabetical within a group. */
export const orderedTerms = (terms: Record<string, unknown>) =>
  Object.entries(terms).sort(([a, va], [b, vb]) => {
    const rank = (k: string, v: unknown) => (k === "date" ? 0 : typeof v === "boolean" ? 2 : 1);
    return rank(a, va) - rank(b, vb) || a.localeCompare(b);
  });

export const STATUS_LABEL: Record<string, string> = {
  GROUP_FORMING: "Group forming",
  NEGOTIATING: "Negotiating",
  PROVIDER_QUOTES_PENDING: "Getting quotes",
  AWAITING_APPROVAL: "Awaiting approval",
  COMMITMENT_PENDING: "Committing",
  COMMITTED: "Committed",
  NO_AGREEMENT: "No agreement",
  EXPIRED: "Expired",
  CANCELLED: "Cancelled",
  FAILED: "Failed",
  needs_input: "Needs review",
  needs_review: "Quote needs your review",
  quote_sent: "Quote sent",
  confirm_booking: "Confirm booking",
  booked: "Booked",
  lost: "Group chose another vendor",
  closed: "Closed",
  ready: "Ready to publish",
  published: "Published",
};
