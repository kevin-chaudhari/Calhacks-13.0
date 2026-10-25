"use client";

// Explore: what people want to do and where they're going, across every activity.

import Link from "next/link";
import { Search, TrendingUp, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Callout, Card, CardHeader, Skeleton, cx } from "@/components/ui/primitives";
import { CATEGORY_LABEL, Composer, FeedCard, PeopleToFollow, type FeedItem, type PersonRef } from "@/components/rally/social";

interface Feed { items: FeedItem[]; trending: { activity: string; label: string; openPlans: number }[] }
type Person = PersonRef & { interests: string[]; followedByMe: boolean };

export default function Explore() {
  const { me } = usePersona();
  const [scope, setScope] = useState<"all" | "following">("all");
  const [category, setCategory] = useState("");
  const [activity, setActivity] = useState("");
  const [feed, setFeed] = useState<Feed | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [people, setPeople] = useState<Person[] | null>(null);
  const [activities, setActivities] = useState<{ key: string; label: string; category: string }[]>([]);

  useEffect(() => {
    const a = new URLSearchParams(window.location.search).get("activity");
    if (a) setActivity(a);
  }, []);

  const load = useCallback(() => {
    const q = new URLSearchParams({ scope, category, activity });
    api<Feed>(`/v1/feed?${q}`).then((f) => (setFeed(f), setErr(null))).catch((e) => setErr(e.message));
  }, [scope, category, activity]);

  useEffect(() => {
    if (!me) return;
    setFeed(null);
    load();
  }, [me, load]);
  useEffect(() => {
    if (!me) return;
    api<Person[]>("/v1/people").then((p) => setPeople(p.filter((x) => x.id.startsWith("c_")).slice(0, 5))).catch(() => setPeople([]));
    api<{ key: string; label: string; category: string }[]>("/v1/activities", { token: null }).then(setActivities).catch(() => {});
  }, [me]);

  const cats = Object.keys(CATEGORY_LABEL);
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div>
        <h1 className="text-[34px] font-semibold leading-[40px] tracking-[-0.025em]">Explore</h1>
        <p className="mt-1 max-w-[60ch] text-muted">Plans people have posted and trips they&apos;re taking. Join someone&apos;s plan and your agents work out the rest.</p>

        <div className="mt-6 flex flex-wrap items-center gap-2">
          <div role="tablist" aria-label="Whose posts" className="inline-flex rounded-full border border-line bg-surface p-1 shadow-card">
            {(["all", "following"] as const).map((s) => (
              <button key={s} role="tab" aria-selected={scope === s} onClick={() => setScope(s)}
                className={cx("h-8 rounded-full px-4 text-[13px] font-medium", scope === s ? "bg-accent text-accent-ink" : "text-muted hover:text-ink")}>
                {s === "all" ? "Everyone" : "Following"}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by kind of activity">
            <button onClick={() => (setCategory(""), setActivity(""))} aria-pressed={!category && !activity}
              className={cx("h-8 rounded-full border px-3 text-[13px]", !category && !activity ? "border-ink text-ink" : "border-line text-muted hover:text-ink")}>All</button>
            {cats.map((c) => (
              <button key={c} onClick={() => (setCategory(c === category ? "" : c), setActivity(""))} aria-pressed={category === c}
                className={cx("h-8 rounded-full border px-3 text-[13px]", category === c ? "border-ink bg-surface text-ink" : "border-line text-muted hover:text-ink")}>
                {CATEGORY_LABEL[c]}
              </button>
            ))}
          </div>
        </div>
        {activity && (
          <div className="mt-3 text-[13px]">
            Showing <strong>{activities.find((a) => a.key === activity)?.label ?? activity}</strong>{" "}
            <button className="text-muted underline" onClick={() => setActivity("")}>clear</button>
          </div>
        )}

        <div className="mt-5 space-y-4">
          <Composer activities={activities} onPosted={load} />
          {err && <Callout tone="danger" title="Couldn't load the feed">{err}</Callout>}
          {!feed && !err && [0, 1, 2].map((i) => <Skeleton key={i} className="h-44" />)}
          {feed?.items.length === 0 && (
            <Callout tone="neutral" title={scope === "following" ? "Nothing from people you follow yet" : "Nothing here yet"}>
              {scope === "following" ? "Follow a few people on the right, or switch to Everyone." : "Post a plan on the Plan a trip page and it shows up here."}
            </Callout>
          )}
          {feed?.items.map((i) => <FeedCard key={`${i.type}:${i.id}`} item={i} />)}
        </div>
      </div>

      <aside className="space-y-5 lg:sticky lg:top-20 lg:self-start">
        <Card>
          <CardHeader icon={<Search size={16} />} title="Find real deals" meta="Live prices from vendors' own websites" />
          <form action="/discover" className="flex gap-2 p-4">
            <label htmlFor="dq" className="sr-only">What and where</label>
            <input id="dq" name="q" placeholder="surf lessons in Santa Cruz" className="h-10 flex-1 rounded-[10px] border border-line bg-surface px-3 text-[14px]" />
            <button className="inline-flex h-10 w-10 items-center justify-center rounded-[10px] bg-accent text-accent-ink" aria-label="Search deals"><Search size={16} /></button>
          </form>
        </Card>
        {feed && feed.trending.length > 0 && (
          <Card>
            <CardHeader icon={<TrendingUp size={16} />} title="Popular right now" meta="Open plans by activity" />
            <ul className="flex flex-wrap gap-1.5 p-4">
              {feed.trending.map((t) => (
                <li key={t.activity}>
                  <button onClick={() => (setActivity(t.activity), setCategory(""))}
                    className={cx("rounded-full border px-3 py-1 text-[13px]", activity === t.activity ? "border-ink text-ink" : "border-line text-muted hover:text-ink")}>
                    {t.label} <span className="num text-muted">{t.openPlans}</span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}
        <Card>
          <CardHeader icon={<Users size={16} />} title="People to follow" />
          {people === null ? <div className="p-4"><Skeleton className="h-24" /></div> : <PeopleToFollow people={people} />}
        </Card>
        <p className="px-1 text-[12px] text-muted">
          People in this feed are demo profiles. Private preferences are never shown; <Link className="underline" href="/demo">control room</Link> resets everything.
        </p>
      </aside>
    </div>
  );
}
