import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

// FastAPI is the only writer (server key). The browser subscribes to:
//   snapshots  one DealSnapshot per deal (group room)            access = members + quoting vendor staff
//   rows       goals | intents | matches | vendor views           access = owner / staff, or [] = any signed-in persona
// On restart, the API rebuilds its working copy from these two tables (rally:dumpAll), so Convex is the
// system of record for everything except private preferences, which never leave the personal agent.
export default defineSchema({
  snapshots: defineTable({
    dealId: v.string(),
    snapshot: v.any(),          // DealSnapshot (packages/contracts/rally_contracts/snapshot.py)
    access: v.optional(v.array(v.string())),
    updatedAt: v.number(),
  }).index("by_deal", ["dealId"]),
  rows: defineTable({
    table: v.string(),          // goals | intents | matches | vendor
    rid: v.string(),            // Rally id (g_…, i_…, <providerId>:<dealId>, <providerId>:dashboard)
    doc: v.any(),
    access: v.optional(v.array(v.string())),
    updatedAt: v.number(),
  }).index("by_table_rid", ["table", "rid"]),
});
