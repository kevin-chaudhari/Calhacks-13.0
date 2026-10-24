/// <reference types="vite/client" />
// Convex function tests with the official convex-test harness (an in-memory Convex backend).
// Run: npm run test:convex
import { convexTest } from "convex-test";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { api } from "./_generated/api";
import schema from "./schema";

const modules = import.meta.glob("./**/*.ts");
const SERVER = "server-key-for-tests";
const SECRET = "rally-secret-for-tests";

/** Same as core.py::sign_persona. */
async function token(userId: string, secret = SECRET) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = [...new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(userId)))]
    .map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 24);
  return `${userId}.${mac}`;
}

beforeEach(() => {
  vi.stubEnv("RALLY_SERVER_KEY", SERVER);
  vi.stubEnv("RALLY_SECRET", SECRET);
});
afterEach(() => vi.unstubAllEnvs());

describe("writes", () => {
  test("only the server key can write", async () => {
    const t = convexTest(schema, modules);
    await expect(t.mutation(api.rally.putSnapshot, { serverKey: "wrong", dealId: "d1", snapshot: {} })).rejects.toThrow(/forbidden/);
    await t.mutation(api.rally.putSnapshot, { serverKey: SERVER, dealId: "d1", snapshot: { deal: { id: "d1" } }, access: ["u_kevin"] });
    const dump = await t.query(api.rally.dumpAll, { serverKey: SERVER });
    expect(dump.snapshots).toHaveLength(1);
    await expect(t.query(api.rally.dumpAll, { serverKey: "wrong" })).rejects.toThrow(/forbidden/);
  });

  test("putMany upserts snapshots and rows in one transaction", async () => {
    const t = convexTest(schema, modules);
    await t.mutation(api.rally.putMany, {
      serverKey: SERVER,
      snapshots: [{ dealId: "d1", snapshot: { v: 1 }, access: ["u_kevin"] }],
      rows: [{ table: "goals", rid: "g1", doc: { text: "scuba" }, access: ["u_kevin"] }],
    });
    await t.mutation(api.rally.putMany, {
      serverKey: SERVER,
      snapshots: [{ dealId: "d1", snapshot: { v: 2 }, access: ["u_kevin"] }],
      rows: [],
    });
    const dump = await t.query(api.rally.dumpAll, { serverKey: SERVER });
    expect(dump.snapshots).toEqual([{ dealId: "d1", snapshot: { v: 2 }, access: ["u_kevin"] }]);
    expect(dump.rows).toEqual([{ table: "goals", rid: "g1", doc: { text: "scuba" }, access: ["u_kevin"] }]);
  });

  test("resetAll empties both tables", async () => {
    const t = convexTest(schema, modules);
    await t.mutation(api.rally.putRow, { serverKey: SERVER, table: "intents", rid: "i1", doc: {} });
    await t.mutation(api.rally.resetAll, { serverKey: SERVER });
    expect(await t.query(api.rally.dumpAll, { serverKey: SERVER })).toEqual({ snapshots: [], rows: [] });
  });
});

describe("reads are token- and access-checked", () => {
  test("members read the group room; outsiders and forged tokens get null", async () => {
    const t = convexTest(schema, modules);
    await t.mutation(api.rally.putSnapshot, { serverKey: SERVER, dealId: "d1", snapshot: { deal: { id: "d1" } }, access: ["u_kevin", "v_marcus"] });
    expect(await t.query(api.rally.dealSnapshot, { dealId: "d1", token: await token("u_kevin") })).toEqual({ deal: { id: "d1" } });
    expect(await t.query(api.rally.dealSnapshot, { dealId: "d1", token: await token("v_marcus") })).not.toBeNull();
    expect(await t.query(api.rally.dealSnapshot, { dealId: "d1", token: await token("u_luis") })).toBeNull();
    expect(await t.query(api.rally.dealSnapshot, { dealId: "d1", token: "u_kevin.forged0000000000000000" })).toBeNull();
    expect(await t.query(api.rally.dealSnapshot, { dealId: "d1", token: await token("u_kevin", "other-secret") })).toBeNull();
    expect(await t.query(api.rally.dealSnapshot, { dealId: "d1" })).toBeNull();
  });

  test("rows with an empty access list are readable by any signed-in persona", async () => {
    const t = convexTest(schema, modules);
    await t.mutation(api.rally.putRow, { serverKey: SERVER, table: "intents", rid: "i1", doc: { text: "dive" }, access: [] });
    await t.mutation(api.rally.putRow, { serverKey: SERVER, table: "goals", rid: "g1", doc: { text: "mine" }, access: ["u_kevin"] });
    expect(await t.query(api.rally.row, { table: "intents", rid: "i1", token: await token("u_ana") })).toEqual({ text: "dive" });
    expect(await t.query(api.rally.row, { table: "intents", rid: "i1" })).toBeNull();
    expect(await t.query(api.rally.row, { table: "goals", rid: "g1", token: await token("u_ana") })).toBeNull();
    expect(await t.query(api.rally.row, { table: "goals", rid: "g1", token: await token("u_kevin") })).toEqual({ text: "mine" });
  });
});
