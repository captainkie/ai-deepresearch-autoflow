#!/usr/bin/env node
/**
 * Reproducible product screenshots (docs §10a).
 *
 * Drives the finished app on **mock providers** (deterministic, offline, no real
 * keys or PII) with Playwright and writes the `docs/screenshots/m7-*.png` set —
 * the same images embedded in the README gallery + hero.
 *
 * Prerequisites:
 *   1. A FRESH backend (no superadmin yet) + the frontend, both running. e.g.:
 *        cd backend  && AUTOFLOW_DB_PATH=/tmp/shots.db uv run autoflow serve   # :8000
 *        cd frontend && pnpm dev                                               # :3000
 *   2. This tool's deps + a browser:
 *        cd scripts && npm install && npx playwright install chromium
 *
 * Run (from scripts/):
 *   npm run capture                 # → docs/screenshots/m7-*.png
 *   # override targets / output:
 *   FRONTEND=http://localhost:3000 API=http://localhost:8000 OUT=/tmp/shots npm run capture
 *
 * Config via env: FRONTEND (default http://localhost:3000),
 *                 API      (default http://localhost:8000),
 *                 OUT      (default ../docs/screenshots).
 */

import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import path from "node:path";

const FRONTEND = process.env.FRONTEND ?? "http://localhost:3000";
const API = process.env.API ?? "http://localhost:8000";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = process.env.OUT ?? path.resolve(HERE, "..", "docs", "screenshots");
const VIEWPORT = { width: 1280, height: 832 };

const ADMIN = { name: "Alex Morgan", email: "alex@brightwave.co", password: "researchdesk2026" };
const TEAM = [
  { name: "Priya Sharma", email: "priya@brightwave.co", role: "admin" },
  { name: "Marco Ruiz", email: "marco@brightwave.co", role: "member" },
  { name: "Jenna Kim", email: "jenna@brightwave.co", role: "member" },
  { name: "Tom Becker", email: "tom@brightwave.co", role: "viewer" },
];
const CREDS = [
  { provider: "anthropic", label: "Claude — production", secret: "sk-ant-demo-0000000000000000" },
  { provider: "tavily", label: "Tavily — web search", secret: "tvly-demo-000000000000000000" },
  { provider: "openai", label: "OpenAI — verifier (cheap model)", secret: "sk-demo-00000000000000000000" },
];
const HISTORY = [
  { query: "How is Liquid Death winning at brand marketing?", template: "deep_research" },
  { query: "Map the direct-to-consumer coffee market in 2026", template: "market_landscape" },
  { query: "Figma vs. Sketch vs. Adobe XD — pricing and plans compared", template: "pricing_analysis" },
  { query: "SWOT analysis of Oatly in the plant-based milk market", template: "swot" },
];

async function api(pathname, { method = "GET", token, body } = {}) {
  const res = await fetch(`${API}${pathname}`, {
    method,
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${pathname} → ${res.status}`);
  return res.status === 204 ? null : res.json();
}

async function shoot(page, name) {
  // Hide the Next.js dev badge (SPA navigations don't re-run the init script).
  await page
    .addStyleTag({ content: "nextjs-portal{display:none!important}" })
    .catch(() => {});
  await page.screenshot({ path: path.join(OUT, name), scale: "css" });
  console.log(`  ✓ ${name}`);
}

async function main() {
  console.log(`Capturing from ${FRONTEND} (API ${API}) → ${OUT}`);

  // 1) Authenticate: fresh backend ⇒ first-run setup; otherwise log in.
  const status = await api("/api/v1/setup/status");
  const session = status.needs_setup
    ? await api("/api/v1/setup", { method: "POST", body: ADMIN })
    : await api("/api/v1/auth/login", {
        method: "POST",
        body: { email: ADMIN.email, password: ADMIN.password },
      });
  const token = session.access_token;

  // 2) Seed a team + a few provider keys so the admin views look real.
  for (const m of TEAM) {
    const u = await api("/api/v1/auth/register", {
      method: "POST",
      body: { name: m.name, email: m.email, password: "teamdemo2026" },
    });
    if (m.role !== "member") {
      await api(`/api/v1/admin/users/${u.user.id}`, {
        method: "PATCH",
        token,
        body: { role: m.role },
      });
    }
  }
  for (const c of CREDS) await api("/api/v1/admin/credentials", { method: "POST", token, body: c });

  // 3) Seed a few completed runs (no plan gate) for the history view.
  const historyIds = [];
  for (const r of HISTORY) {
    const { run_id } = await api("/api/v1/runs", {
      method: "POST",
      token,
      body: { ...r, require_plan_approval: false, language: "en" },
    });
    historyIds.push(run_id);
  }

  // 4) Browser session (dev badge hidden on every page).
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  await ctx.addInitScript(() => {
    const s = document.createElement("style");
    s.textContent = "nextjs-portal{display:none!important}";
    document.documentElement.appendChild(s);
  });
  const page = await ctx.newPage();

  // Sign in through the UI so the browser holds a real session.
  await page.goto(`${FRONTEND}/login`);
  await page.getByRole("textbox", { name: "Email" }).fill(ADMIN.email);
  await page.getByRole("textbox", { name: "Password" }).fill(ADMIN.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((u) => new URL(u).pathname === "/");

  // 5) Home / composer (clean landing).
  await page.getByRole("heading", { level: 1 }).first().waitFor();
  await shoot(page, "m7-02-home.png");

  // 6) Hero flow: Competitor Teardown → plan review → report.
  await page
    .getByRole("textbox", { name: /What do you want to research/i })
    .fill("Competitive teardown of Notion vs. Coda for a productivity launch");
  await page.getByRole("radio", { name: /Competitor Teardown/i }).click();
  await page.getByRole("button", { name: "Start research" }).click();
  await page.getByText("Review the research plan").waitFor();
  await shoot(page, "m7-03-plan.png");

  await page.getByRole("button", { name: /Approve & start research/i }).click();
  await page.getByRole("table").first().waitFor({ timeout: 60_000 }); // comparison table ⇒ report done
  // Let the "research is starting" toast auto-dismiss before capturing.
  await page
    .getByText(/research is starting/i)
    .waitFor({ state: "hidden", timeout: 10_000 })
    .catch(() => {});
  await page.evaluate(() => {
    const a = document.querySelector("main article");
    if (a) { a.scrollIntoView({ block: "start" }); window.scrollBy(0, -88); }
  });
  await shoot(page, "m7-05-report.png");
  await page.evaluate(() => {
    const t = document.querySelector("main article table");
    if (t) { t.scrollIntoView({ block: "start" }); window.scrollBy(0, -160); }
  });
  await shoot(page, "m7-04-run-live.png");

  // 7) Drive the seeded runs to completion (runs start lazily on stream connect),
  //    then capture the history grid.
  for (const id of historyIds) {
    await page.goto(`${FRONTEND}/runs/${id}`);
    await page.getByText("Complete").first().waitFor({ timeout: 60_000 });
  }
  await page.goto(`${FRONTEND}/history`);
  await page.getByRole("heading", { name: /Research history/i }).waitFor();
  await shoot(page, "m7-06-history.png");

  // 8) Admin — users, then the provider-key vault.
  await page.goto(`${FRONTEND}/admin`);
  await page.getByRole("cell", { name: ADMIN.email }).waitFor();
  await shoot(page, "m7-07-admin-users.png");
  await page.getByRole("tab", { name: "Provider keys" }).click();
  await page.getByText("Add a provider key").waitFor();
  await shoot(page, "m7-08-admin-credentials.png");

  await browser.close();
  console.log("Done.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
