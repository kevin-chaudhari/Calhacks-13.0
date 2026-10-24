const { chromium } = require('playwright');
// Two laptops in one script: customer and vendor staff. Needs API :8000 and web :3000.
// Usage: node tests/e2e/two_sided_walk.js [out-dir]   (npm i -D playwright)
const S = process.argv[2] || 'tests/e2e';
require('fs').mkdirSync(S + '/shots', { recursive: true });
const API = 'http://localhost:8000', WEB = 'http://localhost:3000';
(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const watch = (p, tag) => { p.on('console', m => { if (m.type() === 'error') errors.push(tag + ': ' + m.text()); }); p.on('pageerror', e => errors.push(tag + ': ' + e)); };
  await fetch(API + '/v1/demo/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"scenario":"scuba"}' });
  // two browser contexts = two laptops: customer and vendor
  const cust = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage(); watch(cust, 'customer');
  const vend = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage(); watch(vend, 'vendor');
  await vend.goto(WEB + '/vendor');
  await vend.waitForSelector('text=Group requests');
  await vend.screenshot({ path: `${S}/shots/v01-vendor-empty.png` });

  await cust.goto(WEB + '/');
  await cust.waitForSelector('text=Signed in as');
  await cust.click('text=Scuba trip in Monterey');
  await cust.click('button:has-text("Find my people")');
  await cust.waitForURL(/review/);
  await cust.click('button:text-is("5")');
  await cust.click('button:has-text("Apply")');
  await cust.click('button:has-text("Publish and find people")');
  await cust.waitForURL(/matches/);
  await cust.waitForSelector('text=Start group with');
  await cust.screenshot({ path: `${S}/shots/c04-matches.png` });
  await cust.click('button:has-text("Start group with")');
  await cust.waitForURL(/deals\//);
  const dealUrl = cust.url(); const dealId = dealUrl.split('/').pop();
  await cust.waitForSelector('button:has-text("Start negotiation"):not([disabled])', { timeout: 15000 });
  await cust.click('button:has-text("Start negotiation")');
  await cust.waitForTimeout(3500);
  await cust.screenshot({ path: `${S}/shots/c06-room-negotiating.png`, fullPage: true });
  await cust.waitForSelector("text=drafted a quote", { timeout: 30000 });
  await cust.screenshot({ path: `${S}/shots/c07-room-waiting-vendor.png`, fullPage: true });
  // customer messages the vendor while waiting? chat opens after quote; vendor reviews now
  await vend.goto(WEB + '/vendor');
  await vend.waitForSelector('text=Quote needs your review');
  await vend.screenshot({ path: `${S}/shots/v02-vendor-dashboard.png` });
  await vend.click(`a[href="/vendor/requests/${dealId}"]`);
  await vend.waitForSelector('text=Your agent drafted a quote');
  await vend.screenshot({ path: `${S}/shots/v03-vendor-review.png`, fullPage: true });
  await vend.fill('input[aria-describedby="price-help"]', '175');
  await vend.fill('input[placeholder^="e.g."]', 'Meet at the Carmel shop at 7:30');
  await vend.click('button:has-text("Approve and send quote")');
  await vend.waitForSelector('text=Quote sent: $175');
  // vendor talks to the group (Spanish), customer replies
  await vend.fill('textarea[aria-label="Message"]', 'Hola a todos, el barco sale a las 8. Traigan protector solar.');
  await vend.selectOption('select[aria-label="My language"]', 'es-ES');
  await vend.fill('textarea[aria-label="Message"]', 'Hola a todos, el barco sale a las 8. Traigan protector solar.');
  await vend.click('button[aria-label="Send"]');
  await cust.waitForSelector('text=Review and approve', { timeout: 15000 });
  await cust.fill('textarea[aria-label="Message"]', 'Thanks Marcus! Can we bring our own GoPros?');
  await cust.click('button[aria-label="Send"]');
  await cust.waitForTimeout(1500);
  await cust.screenshot({ path: `${S}/shots/c08-room-agreed-chat.png`, fullPage: true });
  await vend.waitForSelector('text=Can we bring our own GoPros?');
  await vend.screenshot({ path: `${S}/shots/v04-vendor-chat.png`, fullPage: true });
  // approvals
  await cust.goto(dealUrl + '/approve');
  await cust.waitForSelector('button:has-text("Approve plan v")');
  await cust.click('button:has-text("Approve plan v")');
  await cust.waitForSelector('text=Approved v');
  for (const who of ['Ana', 'Ravi']) {
    await cust.selectOption('select[aria-label="Signed in as"]', { label: who });
    await cust.waitForTimeout(900);
    await cust.click('button:has-text("Approve plan v")');
    await cust.waitForSelector('text=Approved v');
  }
  await cust.selectOption('select[aria-label="Signed in as"]', { label: 'Kevin' });
  await cust.waitForTimeout(900);
  for (const n of ['Maya', 'Kai']) { await cust.click(`button:has-text("Approve for ${n}")`); await cust.waitForTimeout(900); }
  await cust.waitForURL(/confirmed/, { timeout: 10000 });
  // vendor confirms booking
  await vend.waitForSelector('button:has-text("Confirm booking")', { timeout: 10000 });
  await vend.click('button:has-text("Confirm booking")');
  await vend.waitForSelector('text=You confirmed this booking');
  await vend.screenshot({ path: `${S}/shots/v05-vendor-booked.png`, fullPage: true });
  await cust.waitForSelector('text=Booked by', { timeout: 10000 });
  await cust.screenshot({ path: `${S}/shots/c10-confirmed.png`, fullPage: true });
  await cust.goto(dealUrl);
  await cust.waitForSelector('text=Agent conversation');
  await cust.screenshot({ path: `${S}/shots/c11-room-final.png`, fullPage: true });
  await vend.goto(WEB + '/vendor/pricing');
  await vend.waitForSelector('text=Group-size tiers');
  await vend.screenshot({ path: `${S}/shots/v06-pricing.png`, fullPage: true });
  await cust.goto(WEB + '/diagnostics');
  await cust.waitForSelector('text=Every agent message');
  await cust.screenshot({ path: `${S}/shots/c12-agents.png` });
  const m = await (await browser.newContext({ viewport: { width: 400, height: 860 } })).newPage(); watch(m, 'mobile');
  await m.goto(WEB + '/vendor/requests/' + dealId);
  await m.waitForSelector('text=Talk to the group');
  const overflow = await m.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  await m.screenshot({ path: `${S}/shots/v07-vendor-mobile.png`, fullPage: true });
  const text = await cust.evaluate(() => document.body.innerText);
  console.log(JSON.stringify({ errors, overflow, demoWordOnPages: /\bDemo\b/.test(text), dealId }));
  await browser.close();
})().catch(e => { console.error('FAILED', e.message.split('\n')[0]); process.exit(1); });
