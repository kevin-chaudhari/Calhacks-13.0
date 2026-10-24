import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Writes: only FastAPI, which holds RALLY_SERVER_KEY (`npx convex env set RALLY_SERVER_KEY …`).
// Reads: the browser, with the persona token FastAPI issued (`<userId>.<hmac>`). The token is verified
// here with RALLY_SECRET (`npx convex env set RALLY_SECRET …`, same value as the API's) and the user must
// be on the document's access list. Demo identities, not real auth: see README "Identity".

function assertServer(key: string) {
  const expected = process.env.RALLY_SERVER_KEY;
  if (!expected || key !== expected) throw new Error("forbidden: server key required");
}

const hex = (buf: ArrayBuffer) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");

/** Same scheme as services/api/rally/core.py::sign_persona: hex(HMAC-SHA256(secret, userId))[:24]. */
export async function verifyPersona(token: string | undefined, secret: string | undefined): Promise<string | null> {
  if (!token || !secret || !token.includes(".")) return null;
  const cut = token.lastIndexOf(".");
  const userId = token.slice(0, cut);
  const sig = token.slice(cut + 1);
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = hex(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(userId))).slice(0, 24);
  if (mac.length !== sig.length) return null;
  let diff = 0;
  for (let i = 0; i < mac.length; i++) diff |= mac.charCodeAt(i) ^ sig.charCodeAt(i);
  return diff === 0 ? userId : null;
}

const allowed = (userId: string | null, access: string[] | undefined) =>
  userId !== null && (access === undefined || access.length === 0 || access.includes(userId));

export const putSnapshot = mutation({
  args: { serverKey: v.string(), dealId: v.string(), snapshot: v.any(), access: v.optional(v.array(v.string())) },
  handler: async (ctx, { serverKey, dealId, snapshot, access }) => {
    assertServer(serverKey);
    const existing = await ctx.db.query("snapshots").withIndex("by_deal", (q) => q.eq("dealId", dealId)).unique();
    if (existing) await ctx.db.patch(existing._id, { snapshot, access, updatedAt: Date.now() });
    else await ctx.db.insert("snapshots", { dealId, snapshot, access, updatedAt: Date.now() });
  },
});

export const putRow = mutation({
  args: { serverKey: v.string(), table: v.string(), rid: v.string(), doc: v.any(), access: v.optional(v.array(v.string())) },
  handler: async (ctx, { serverKey, table, rid, doc, access }) => {
    assertServer(serverKey);
    const existing = await ctx.db
      .query("rows")
      .withIndex("by_table_rid", (q) => q.eq("table", table).eq("rid", rid))
      .unique();
    if (existing) await ctx.db.patch(existing._id, { doc, access, updatedAt: Date.now() });
    else await ctx.db.insert("rows", { table, rid, doc, access, updatedAt: Date.now() });
  },
});

/** Several writes in one transaction: the API's background writer batches coalesced updates. */
export const putMany = mutation({
  args: {
    serverKey: v.string(),
    snapshots: v.array(v.object({ dealId: v.string(), snapshot: v.any(), access: v.optional(v.array(v.string())) })),
    rows: v.array(v.object({ table: v.string(), rid: v.string(), doc: v.any(), access: v.optional(v.array(v.string())) })),
  },
  handler: async (ctx, { serverKey, snapshots, rows }) => {
    assertServer(serverKey);
    const now = Date.now();
    for (const s of snapshots) {
      const existing = await ctx.db.query("snapshots").withIndex("by_deal", (q) => q.eq("dealId", s.dealId)).unique();
      if (existing) await ctx.db.patch(existing._id, { snapshot: s.snapshot, access: s.access, updatedAt: now });
      else await ctx.db.insert("snapshots", { ...s, updatedAt: now });
    }
    for (const r of rows) {
      const existing = await ctx.db
        .query("rows")
        .withIndex("by_table_rid", (q) => q.eq("table", r.table).eq("rid", r.rid))
        .unique();
      if (existing) await ctx.db.patch(existing._id, { doc: r.doc, access: r.access, updatedAt: now });
      else await ctx.db.insert("rows", { ...r, updatedAt: now });
    }
  },
});

export const resetAll = mutation({
  args: { serverKey: v.string() },
  handler: async (ctx, { serverKey }) => {
    assertServer(serverKey);
    for (const s of await ctx.db.query("snapshots").collect()) await ctx.db.delete(s._id);
    for (const r of await ctx.db.query("rows").collect()) await ctx.db.delete(r._id);
  },
});

/** Server only: everything the API needs to rebuild its working copy after a restart. */
export const dumpAll = query({
  args: { serverKey: v.string() },
  handler: async (ctx, { serverKey }) => {
    assertServer(serverKey);
    const snapshots = await ctx.db.query("snapshots").collect();
    const rows = await ctx.db.query("rows").collect();
    return {
      snapshots: snapshots.map((s) => ({ dealId: s.dealId, snapshot: s.snapshot, access: s.access ?? [] })),
      rows: rows.map((r) => ({ table: r.table, rid: r.rid, doc: r.doc, access: r.access ?? [] })),
    };
  },
});

/** Group room subscription. null = not found or not allowed (the UI shows the same message for both). */
export const dealSnapshot = query({
  args: { dealId: v.string(), token: v.optional(v.string()) },
  handler: async (ctx, { dealId, token }) => {
    const userId = await verifyPersona(token, process.env.RALLY_SECRET);
    const s = await ctx.db.query("snapshots").withIndex("by_deal", (q) => q.eq("dealId", dealId)).unique();
    if (!s || !allowed(userId, s.access)) return null;
    return s.snapshot;
  },
});

export const row = query({
  args: { table: v.string(), rid: v.string(), token: v.optional(v.string()) },
  handler: async (ctx, { table, rid, token }) => {
    const userId = await verifyPersona(token, process.env.RALLY_SECRET);
    const r = await ctx.db
      .query("rows")
      .withIndex("by_table_rid", (q) => q.eq("table", table).eq("rid", rid))
      .unique();
    if (!r || !allowed(userId, r.access)) return null;
    return r.doc;
  },
});
