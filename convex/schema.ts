import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

// Interim schema for the first PR (see docs/decisions.md, D2).
// FastAPI is the only writer. It mirrors each row it changes into `rows`, and writes one
// denormalised DealSnapshot per deal into `snapshots`, which the group room subscribes to.
// The typed per-table schema in plan section 11.3 replaces `rows` once the vertical slice is stable.
export default defineSchema({
  snapshots: defineTable({
    dealId: v.string(),
    snapshot: v.any(),          // DealSnapshot (packages/contracts/rally_contracts/snapshot.py)
    updatedAt: v.number(),
  }).index("by_deal", ["dealId"]),
  rows: defineTable({
    table: v.string(),          // goals | intents | matches
    rid: v.string(),            // Rally id (g_…, i_…)
    doc: v.any(),
    updatedAt: v.number(),
  }).index("by_table_rid", ["table", "rid"]),
});
