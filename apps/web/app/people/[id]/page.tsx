"use client";

import { useParams } from "next/navigation";
import { MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Avatar, Button, Callout, Chip, Skeleton, cx } from "@/components/ui/primitives";
import { FeedCard, type PlanItem, type PostItem, type TripItem } from "@/components/rally/social";

interface Profile {
  id: string; name: string; initials: string; homeArea: string; bio: string; community: boolean;
  interests: { activity: string; label: string }[]; followers: number; following: number; followedByMe: boolean; isMe: boolean;
  plans: PlanItem[]; trips: TripItem[]; posts: PostItem[];
}

export default function PersonPage() {
  const { id } = useParams<{ id: string }>();
  const { me } = usePersona();
  const [p, setP] = useState<Profile | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<"plans" | "trips" | "posts">("plans");

  useEffect(() => {
    if (!me) return;
    api<Profile>(`/v1/people/${id}`).then(setP).catch((e) => setErr(e instanceof ApiError ? e.message : "Couldn't load."));
  }, [id, me]);

  async function follow() {
    if (!p) return;
    const r = await api<{ following: boolean; followers: number }>(`/v1/people/${id}/follow`, { body: {} });
    setP({ ...p, followedByMe: r.following, followers: r.followers });
  }

  if (err) return <Callout tone="danger" title="Can't open this profile">{err}</Callout>;
  if (!p) return <Skeleton className="h-64" />;
  const lists = { plans: p.plans, trips: p.trips, posts: p.posts };
  const items = lists[tab];
  return (
    <div className="mx-auto max-w-2xl">
      <header className="chart-field rounded-[24px] border border-line px-6 py-8">
        <div className="flex flex-wrap items-center gap-4">
          <Avatar initials={p.initials} size={72} />
          <div className="min-w-0 flex-1">
            <h1 className="text-[30px] font-semibold leading-9 tracking-[-0.02em]">{p.name}</h1>
            {p.homeArea && <div className="mt-0.5 inline-flex items-center gap-1 text-[14px] text-muted"><MapPin size={14} /> {p.homeArea}</div>}
          </div>
          {!p.isMe && (
            <Button variant={p.followedByMe ? "secondary" : "primary"} onClick={follow}>{p.followedByMe ? "Following" : "Follow"}</Button>
          )}
        </div>
        {p.bio && <p className="mt-4 max-w-[56ch] text-[15px] leading-6">{p.bio}</p>}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {p.interests.map((i) => <Chip key={i.activity} tone="accent">{i.label}</Chip>)}
        </div>
        <div className="num mt-4 flex gap-5 text-[14px]">
          <span><strong>{p.followers}</strong> <span className="text-muted">followers</span></span>
          <span><strong>{p.following}</strong> <span className="text-muted">following</span></span>
          <span><strong>{p.trips.length}</strong> <span className="text-muted">trips</span></span>
        </div>
        {p.community && <p className="mt-3 text-[12px] text-muted">Demo profile</p>}
      </header>

      <div role="tablist" aria-label="Profile sections" className="mt-6 flex gap-1 border-b border-line">
        {(["plans", "trips", "posts"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={cx("relative px-3 py-2 text-[14px] font-medium capitalize", tab === t ? "text-ink after:absolute after:inset-x-3 after:-bottom-px after:h-[3px] after:rounded-full after:bg-buoy" : "text-muted hover:text-ink")}>
            {t} <span className="num text-muted">{lists[t].length}</span>
          </button>
        ))}
      </div>
      <div className="mt-4 space-y-4">
        {items.length === 0 && (
          <p className="py-8 text-center text-[14px] text-muted">
            {tab === "plans" ? "No open plans." : tab === "trips" ? "No trips booked yet." : "No posts yet."}
          </p>
        )}
        {items.map((i) => <FeedCard key={`${i.type}:${i.id}`} item={i} />)}
      </div>
    </div>
  );
}
