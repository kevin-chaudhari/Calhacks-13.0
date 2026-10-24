import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Writes: only FastAPI, which holds RALLY_SERVER_KEY (set it with `npx convex env set RALLY_SERVER_KEY …`).
// Reads: the browser. NOTE: reads are not yet membership-checked (demo identities are not Convex auth);
// plan section 11.2 requires that before anything leaves demo mode.

function assertServer(key: string) {
  const expected = process.env.RALLY_SERVER_KEY;
  if (!expected || key !== expected) throw new Error("forbidden: server key required");
}

export const putSnapshot = mutation({
  args: { serverKey: v.string(), dealId: v.string(), snapshot: v.any() },
  handler: async (ctx, { serverKey, dealId, snapshot }) => {
    assertServer(serverKey);
    const existing = await ctx.db.query("snapshots").withIndex("by_deal", (q) => q.eq("dealId", dealId)).unique();
    if (existing) await ctx.db.patch(existing._id, { snapshot, updatedAt: Date.now() });
    else await ctx.db.insert("snapshots", { dealId, snapshot, updatedAt: Date.now() });
  },
});

export const putRow = mutation({
  args: { serverKey: v.string(), table: v.string(), rid: v.string(), doc: v.any() },
  handler: async (ctx, { serverKey, table, rid, doc }) => {
    assertServer(serverKey);
    const existing = await ctx.db
      .query("rows")
      .withIndex("by_table_rid", (q) => q.eq("table", table).eq("rid", rid))
      .unique();
    if (existing) await ctx.db.patch(existing._id, { doc, updatedAt: Date.now() });
    else await ctx.db.insert("rows", { table, rid, doc, updatedAt: Date.now() });
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

export const dealSnapshot = query({
  args: { dealId: v.string() },
  handler: async (ctx, { dealId }) => {
    const s = await ctx.db.query("snapshots").withIndex("by_deal", (q) => q.eq("dealId", dealId)).unique();
    return s ? s.snapshot : null;
  },
});

export const row = query({
  args: { table: v.string(), rid: v.string() },
  handler: async (ctx, { table, rid }) => {
    const r = await ctx.db
      .query("rows")
      .withIndex("by_table_rid", (q) => q.eq("table", table).eq("rid", rid))
      .unique();
    return r ? r.doc : null;
  },
});
