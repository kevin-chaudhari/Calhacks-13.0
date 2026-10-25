"use client";

// Social building blocks: feed cards for open plans, trips and posts; likes; comments; "I'm in too".

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Anchor, CircleDot, Heart, Map as MapIcon, MessageCircle, Mountain, Palette, PartyPopper, Plane, Send, Snowflake, UserPlus, Users, Waves,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { ago, money, shortDay } from "@/lib/format";
import { Avatar, Button, Card, Chip, cx } from "@/components/ui/primitives";

export interface PersonRef { id: string; name: string; initials: string; homeArea: string }
interface Base { id: string; at: number; user: PersonRef; activity: string | null; activityLabel: string | null; category: string; place: string | null; likes: number; likedByMe: boolean; comments: number }
export interface PlanItem extends Base { type: "plan"; text: string; dateFrom: string | null; dateTo: string | null; budget: number | null; groupMax: number | null; mine: boolean; joinable: boolean }
export interface TripItem extends Base { type: "trip"; title: string; solo: boolean; people: string[]; date: string | null; vendor: string; pricePerPerson: number; listed: boolean; status: string; member: boolean }
export interface PostItem extends Base { type: "post"; text: string; dealId: string | null }
export type FeedItem = PlanItem | TripItem | PostItem;

const GLYPH: Record<string, typeof Waves> = {
  water: Waves, air: Plane, mountain: Mountain, snow: Snowflake, court: CircleDot, fun: PartyPopper, class: Palette, tour: MapIcon,
};
export const CATEGORY_LABEL: Record<string, string> = {
  water: "On the water", air: "In the air", mountain: "Mountains and trails", snow: "Snow", court: "Courts and fields",
  fun: "Games and thrills", class: "Classes", tour: "Tours and tastings",
};

export function ActivityGlyph({ category, size = 14 }: { category: string; size?: number }) {
  const G = GLYPH[category] ?? Anchor;
  return (
    <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent" aria-hidden>
      <G size={size} strokeWidth={1.9} />
    </span>
  );
}

function dates(a: string | null, b: string | null) {
  if (!a) return null;
  return a === b || !b ? shortDay(a) : `${shortDay(a)} to ${shortDay(b)}`;
}

function Comments({ itemId, onCount }: { itemId: string; onCount: (n: number) => void }) {
  const [list, setList] = useState<{ id: string; text: string; at: number; user: PersonRef }[] | null>(null);
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api<NonNullable<typeof list>>(`/v1/feed/${itemId}/comments`).then((l) => setList(l ?? [])).catch(() => setList([]));
  }, [itemId]);
  async function send() {
    if (!text.trim()) return;
    try {
      const l = await api<NonNullable<typeof list>>(`/v1/feed/${itemId}/comments`, { body: { text } });
      setList(l);
      onCount(l.length);
      setText("");
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Couldn't post that.");
    }
  }
  return (
    <div className="border-t border-line bg-surface-2/50 px-5 py-3">
      <ul className="space-y-2">
        {(list ?? []).map((c) => (
          <li key={c.id} className="flex gap-2 text-[13px]">
            <Link href={`/people/${c.user.id}`}><Avatar initials={c.user.initials} size={24} /></Link>
            <div>
              <Link href={`/people/${c.user.id}`} className="font-medium hover:underline">{c.user.name}</Link>{" "}
              <span className="text-ink/85">{c.text}</span>
              <div className="text-[11px] text-muted">{ago(c.at)}</div>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex gap-2">
        <label className="sr-only" htmlFor={`c-${itemId}`}>Write a comment</label>
        <input id={`c-${itemId}`} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Write a comment" maxLength={500}
          className="h-9 flex-1 rounded-[8px] border border-line bg-surface px-3 text-[13px]" />
        <Button variant="secondary" onClick={send} aria-label="Send comment"><Send size={14} /></Button>
      </div>
      {err && <div className="mt-1 text-[12px] text-danger">{err}</div>}
    </div>
  );
}

export function FeedCard({ item }: { item: FeedItem }) {
  const router = useRouter();
  const [likes, setLikes] = useState({ n: item.likes, mine: item.likedByMe });
  const [count, setCount] = useState(item.comments);
  const [open, setOpen] = useState(false);
  const [joining, setJoining] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function like() {
    setLikes((l) => ({ n: l.n + (l.mine ? -1 : 1), mine: !l.mine }));
    try {
      const r = await api<{ likes: number; likedByMe: boolean }>(`/v1/feed/${item.id}/like`, { body: {} });
      setLikes({ n: r.likes, mine: r.likedByMe });
    } catch {
      setLikes({ n: item.likes, mine: item.likedByMe });
    }
  }

  async function join() {
    setJoining(true);
    setErr(null);
    try {
      const r = await api<{ goalId: string }>(`/v1/feed/plans/${item.id}/join`, { body: {} });
      router.push(`/goals/${r.goalId}/matches?with=${item.id}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Couldn't join.");
      setJoining(false);
    }
  }

  const who = (
    <Link href={`/people/${item.user.id}`} className="font-semibold hover:underline">{item.user.name}</Link>
  );
  let headline: React.ReactNode;
  let body: React.ReactNode = null;
  if (item.type === "plan") {
    headline = <>{who} wants to go <strong className="font-semibold">{item.activityLabel?.toLowerCase()}</strong>{item.place && <> in {item.place.split(",")[0]}</>}</>;
    body = (
      <>
        <p className="mt-2 text-[15px] leading-6">&ldquo;{item.text}&rdquo;</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {dates(item.dateFrom, item.dateTo) && <Chip>{dates(item.dateFrom, item.dateTo)}</Chip>}
          {item.budget != null && <Chip>up to {money(item.budget)} each</Chip>}
          {item.groupMax != null && <Chip>{item.groupMax === 1 ? "solo" : `up to ${item.groupMax} people`}</Chip>}
        </div>
      </>
    );
  } else if (item.type === "trip") {
    headline = item.solo
      ? <>{who} is going <strong className="font-semibold">{item.activityLabel?.toLowerCase()}</strong> solo</>
      : <><span className="font-semibold">{item.people.join(", ")}</span> are going <strong className="font-semibold">{item.activityLabel?.toLowerCase()}</strong></>;
    body = (
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-[12px] border border-line bg-buoy-soft/60 px-4 py-3 text-[14px]">
        <span className="font-semibold">{item.vendor}</span>
        {item.date && <span>{shortDay(item.date)}</span>}
        <span className="num">{money(item.pricePerPerson)} each</span>
        {item.listed && <Chip tone="neutral" title="From the vendor's own website">Listed price</Chip>}
        <Chip tone={item.status === "COMMITTED" ? "accent" : "warn"}>{item.status === "COMMITTED" ? "Booked in" : "Approving"}</Chip>
      </div>
    );
  } else {
    headline = <>{who}{item.activityLabel && <> · <span className="text-muted">{item.activityLabel}</span></>}</>;
    body = <p className="mt-2 whitespace-pre-line text-[15px] leading-6">{item.text}</p>;
  }

  return (
    <Card>
      <article className="px-5 pb-3 pt-4">
        <header className="flex items-start gap-3">
          <Link href={`/people/${item.user.id}`}><Avatar initials={item.user.initials} size={36} /></Link>
          <div className="min-w-0 flex-1">
            <div className="text-[14px] leading-5">{headline}</div>
            <div className="text-[12px] text-muted">{ago(item.at)}{item.place && item.type !== "plan" && <> · {item.place}</>}</div>
          </div>
          <ActivityGlyph category={item.category} />
        </header>
        {body}
        <footer className="mt-3 flex flex-wrap items-center gap-1">
          <button onClick={like} aria-pressed={likes.mine} className={cx("inline-flex h-8 items-center gap-1.5 rounded-[8px] px-2.5 text-[13px]", likes.mine ? "text-danger" : "text-muted hover:text-ink")}>
            <Heart size={15} fill={likes.mine ? "currentColor" : "none"} /> <span className="num">{likes.n}</span>
          </button>
          <button onClick={() => setOpen(!open)} aria-expanded={open} className="inline-flex h-8 items-center gap-1.5 rounded-[8px] px-2.5 text-[13px] text-muted hover:text-ink">
            <MessageCircle size={15} /> <span className="num">{count}</span>
          </button>
          {item.type === "plan" && item.joinable && (
            <Button className="ml-auto" onClick={join} disabled={joining}>
              <UserPlus size={14} /> {joining ? "Finding your group…" : "I'm in too"}
            </Button>
          )}
          {item.type === "plan" && item.mine && <span className="ml-auto text-[12px] text-muted">Your plan</span>}
          {item.type === "trip" && item.member && (
            <Link href={`/deals/${item.id}`} className="ml-auto text-[13px] font-medium text-accent underline">Open trip</Link>
          )}
        </footer>
        {err && <div className="text-[12px] text-danger">{err}</div>}
      </article>
      {open && <Comments itemId={item.id} onCount={setCount} />}
    </Card>
  );
}

export function Composer({ onPosted, activities }: { onPosted: () => void; activities: { key: string; label: string }[] }) {
  const [text, setText] = useState("");
  const [activity, setActivity] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function post() {
    if (!text.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await api("/v1/posts", { body: { text, activity } });
      setText("");
      onPosted();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Couldn't post.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card className="p-3">
      <label htmlFor="compose" className="sr-only">Share a trip or ask for company</label>
      <textarea id="compose" rows={2} value={text} onChange={(e) => setText(e.target.value)} maxLength={1000}
        placeholder="Share a trip, or ask who's in for something this weekend"
        className="no-ring w-full resize-none bg-transparent px-2 py-1.5 text-[15px] leading-6 outline-none placeholder:text-muted/70" />
      <div className="flex flex-wrap items-center justify-between gap-2 px-1">
        <select aria-label="Activity" value={activity} onChange={(e) => setActivity(e.target.value)}
          className="h-8 rounded-[8px] border border-line bg-surface px-2 text-[13px]">
          <option value="">Tag an activity</option>
          {activities.map((a) => <option key={a.key} value={a.key}>{a.label}</option>)}
        </select>
        <Button onClick={post} disabled={busy || !text.trim()}>{busy ? "Posting…" : "Post"}</Button>
      </div>
      {err && <div className="px-2 text-[12px] text-danger">{err}</div>}
    </Card>
  );
}

export function PeopleToFollow({ people }: { people: (PersonRef & { interests: string[]; followedByMe: boolean })[] }) {
  const [state, setState] = useState<Record<string, boolean>>(() => Object.fromEntries(people.map((p) => [p.id, p.followedByMe])));
  async function toggle(id: string) {
    setState((s) => ({ ...s, [id]: !s[id] }));
    try {
      const r = await api<{ following: boolean }>(`/v1/people/${id}/follow`, { body: {} });
      setState((s) => ({ ...s, [id]: r.following }));
    } catch {
      setState((s) => ({ ...s, [id]: !s[id] }));
    }
  }
  return (
    <ul className="divide-y divide-line">
      {people.map((p) => (
        <li key={p.id} className="flex items-center gap-3 px-5 py-2.5">
          <Link href={`/people/${p.id}`}><Avatar initials={p.initials} size={32} /></Link>
          <div className="min-w-0 flex-1">
            <Link href={`/people/${p.id}`} className="block truncate text-[14px] font-medium hover:underline">{p.name}</Link>
            <div className="truncate text-[12px] text-muted">{p.interests.join(", ") || p.homeArea}</div>
          </div>
          <Button variant={state[p.id] ? "secondary" : "primary"} className="h-8 px-3" onClick={() => toggle(p.id)}>
            {state[p.id] ? "Following" : "Follow"}
          </Button>
        </li>
      ))}
    </ul>
  );
}

export { Users };
