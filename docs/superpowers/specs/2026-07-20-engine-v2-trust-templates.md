# Engine v2 — Trust, Verification & Structured Templates (Spec Addendum)

**Date:** 2026-07-20 · **Status:** Draft for review · **Owner:** captainkie (Narenrit)
**Amends:** `2026-07-20-ai-deepresearch-autoflow-design.md` (§1, §4, §5, §7, §8, §11, §13)
**Scope:** design only — no code yet. This is the redesign that turns the engine from
*search → summarize → report* into a **verifiable, claim-grounded** research system, and turns
`template` from a string into a **structured, marketing-grade** research product.

## 0. Why this addendum (the thesis)

The original spec builds a competent deep-research pipeline. But its edge over the OSS field
(open_deep_research, deer-flow, gpt-researcher, Alibaba DeepResearch) is **not** reasoning depth
— those projects have more compute and researchers. Our real, defensible edge is two things the
field neglects:

1. **Operational trust** — a *self-hosted, multi-user, secure* platform (vault + RBAC + audit +
   first-run setup) that a non-technical marketing team can actually use. Already ~60% built.
2. **Verified output** — every claim in the report is grounded in a cited source and checked by a
   separate verifier, with explicit confidence and surfaced contradictions.

This addendum invests in (2) and in the **product shape** (marketing templates) that makes the
output visibly better than a generic AI summary. It deliberately **rejects** feature-bloat that
sounds impressive but does not pay off in v1: multi-agent frameworks, knowledge graphs, evidence
graphs, hypothesis-generation engines, and rejected-hypothesis stores. Those stay as "Future" in §7.

## 1. Positioning (reframe)

**One-liner:** *Deep research your team can trust — self-hosted, secure, every claim cited and verified.*

Reframe the three pillars, loudest first:

- **Secure by default** — encrypted vault, RBAC, audit, first-run setup. Hand it to marketers; the
  admin holds the keys. (No other OSS deep-research tool does this.)
- **Verified, not just generated** — claim-level citations + an adversarial verifier + confidence +
  contradiction detection. Being wrong about a competitor is expensive; the system is honest about
  what it could and couldn't confirm.
- **Self-hostable** — one deploy, whole team, swappable providers.

**Naming — OPEN DECISION (do not rename until confirmed).** "AI DeepResearch AutoFlow" is three
stacked buzzwords and communicates none of the above. The deliverable is effectively a *dossier* on
a competitor/market. Candidates that carry the "intel + trustworthy" meaning: **Dossier**, **Verity**,
**Corroborate**, **Citadel Research**. No change is made in code/docs until the owner picks one; this
is tracked as an open item in §8.

## 2. Trust & Verification architecture (core change)

### 2.1 Problem in the current loop

Current flow (spec §4): `search → crawl → LLM-summarize page → reflect → follow-up → compress to
section notes with [n] → synthesize`. Citations live at the **note** level, and the **synthesizer**
is free to write connective sentences that no source supports. That synthesis step is the single
largest hallucination surface, and it is exactly where a competitor report goes wrong.

### 2.2 The rule that fixes it

> **A claim is the atomic unit. The report is a projection of the set of verified claims — not
> free-form generation.**

The synthesizer may only assert claims that passed verification. Unsupported/contradicted material
is dropped from the body and moved to an explicit **"Unverified / needs checking"** appendix.

### 2.3 New per-section pipeline

```
old:  search → crawl → summarize note → reflect → follow-up → compress note
new:  search → crawl → EXTRACT CLAIMS → VERIFY (vs source text) → cluster & detect contradictions
      → adaptive stop → compress verified claims into section notes
final: synthesize report = render verified claims + comparison table + contradictions + unverified
```

1. **Extract claims** — from each crawled page (already cached), the LLM extracts atomic claims:
   `{ text, entity?, attribute?, quote, source_ids[] }`. Every claim MUST carry ≥1 source and a
   supporting `quote` copied from the page (verbatim span), so verification is a grounding check,
   not a re-derivation.
2. **Verify** — a **separate LLM role** (adversarial prompt) receives `claim + the actual source
   text/quote` and returns `{ verdict, confidence, rationale }`. It checks *grounding* ("does the
   source actually say this?"), not truth-in-the-world. Because it reads real text, it is cheap and
   accurate.
   - `verdict ∈ { supported | partial | unsupported | contradicted }`
3. **Cluster & detect contradictions** — group claims by `(entity, attribute)`, e.g.
   `(BrandX, pricing)`. If two supported claims disagree, emit a **contradiction** carrying both
   claims + both sources. This is the analyst's core value: *surfacing* the conflict, not hiding it.
4. **Adaptive stop** (see §3) — reuse the claim/source registry as the diminishing-returns signal.
5. **Compress** — fold the verified claims into section notes for synthesis.

### 2.4 Verifier model routing (leverages our swappable providers)

Verification is high-volume and shallow → run it on a **cheap, fast model** (Haiku / z.ai GLM /
Moonshot Kimi), while planner/synthesizer use a strong model. This is a first-class config, and it
is the concrete reason our provider abstraction earns its keep — not a demo feature.

New settings: `verifier_provider`, `verifier_model` (default: a cheap model; fall back to the main
LLM if unset). Mock verifier returns deterministic verdicts for offline E2E.

### 2.5 Confidence scoring (simple, defensible)

Per-claim confidence is a small, transparent function — **not** an opaque model score:

```
confidence(claim) = f(
  independent_supporting_sources,   # count of distinct domains asserting it
  verifier_verdict,                 # supported > partial > unsupported
  source_recency,                   # optional: newer weighted higher
)
→ label: high (≥2 independent + supported) | medium (1 source + supported/partial) | low (else)
```

Surfaced in the report as a badge next to each finding, and aggregated into a per-run
**"confidence summary"**. Keep the formula in one pure function so it's testable and tunable.

### 2.6 Cost / latency tradeoff (stated honestly)

Verification adds ~1 LLM call per claim and extra latency. Mitigations, all config-gated:

- **Batch** claims per source into a single verify call.
- **Verify only** claims that are candidates for the synthesis body (not every extracted fragment).
- **`verification_level: off | light | strict`** (default `light`). Marketing/competitor templates
  default to `strict`; quick lookups can run `off`.
- Cheap verifier model (§2.4).

Claim extraction is itself lossy; that's acceptable — a missed claim degrades gracefully to "less
covered", never to "confidently wrong".

## 3. Adaptive stopping (folds into the engine)

Stop researching a section on **evidence**, not iteration count. Stop when **any** holds:

- **Diminishing returns** — the last iteration added 0 new sources AND 0 new *supported* claims.
- **Confidence target met** — section has enough supported claims to answer its `goal`.
- **Budget guard** — per-run `max_llm_calls` / wallclock / token budget (some already in M2 Task 9).
- **Hard cap** — `max_iters_per_section` (existing) as the backstop, not the primary reason.

Global run stops on budget/wallclock. The claim+source registry from §2 is the natural signal, so
this costs almost nothing to add once §2 exists.

## 4. Structured templates (the product wedge)

Today `template` is a string passed to the planner. Upgrade it to a **structured, data-driven
template** so the output is a domain artifact, not a generic essay. Templates are data
(`backend/app/prompts/templates/*.yaml` or the `settings`/DB), so **the community can contribute new
ones** — a natural OSS extension point.

### 4.1 Template schema

```yaml
id: competitor_teardown
name: Competitor Teardown
description: Structured intel on one or more competitor brands.
audience: marketing
default_language: en
verification_level: strict
entity_mode: true                       # this template compares entities (brands)
entity_schema:                          # attributes to extract & compare per entity
  - { key: positioning,     label: Positioning,      type: text }
  - { key: pricing,         label: Pricing,          type: text }
  - { key: target_segment,  label: Target segment,   type: text }
  - { key: key_features,    label: Key features,     type: list }
  - { key: funding,         label: Funding/scale,    type: text }
  - { key: weaknesses,      label: Weaknesses,       type: list }
sections:                               # skeleton plan seed
  - { title: Positioning & messaging, goal: "...", seed_queries: ["..."] }
  - { title: Pricing & packaging,     goal: "...", seed_queries: ["..."] }
  - { title: Go-to-market,            goal: "...", seed_queries: ["..."] }
report_sections: [exec_summary, comparison_table, per_entity, contradictions, unverified, next_actions, sources]
```

Ship four to start: **Competitor Teardown**, **Market Landscape**, **SWOT**, **Pricing Analysis**.
Plus a generic **Deep Research** (no `entity_mode`) as today.

### 4.2 Why §2 + §4 must ship together (the payoff)

Claims are already tagged with `(entity, attribute)`. The template's `entity_schema` keys ARE those
attributes. So the verified claim set **auto-fills a comparison table**: rows = entities, columns =
`entity_schema`, and **every cell carries its citation `[n]` and confidence badge**. Generic
deep-research tools cannot produce this because they never structured the claims. This is the
McKinsey/Gartner-grade artifact that makes the difference visible at a glance.

## 5. Report structure (marketing-grade)

Synthesizer output for `entity_mode` templates, in order:

1. **Executive summary** — answer-first, ≤5 bullets, each with a confidence badge.
2. **Comparison table** — entities × `entity_schema`; cited + confidence per cell (§4.2).
3. **Per-entity / per-section detail** — verified claims, prose, inline `[n]`.
4. **Contradictions & open questions** — surfaced conflicts with both sources.
5. **Unverified / needs checking** — claims that failed verification, kept out of the body.
6. **Recommended next actions** — decision-support, not just facts.
7. **Sources** — the existing global numbered registry.

Non-entity templates skip (2) and collapse (3). All sections remain valid Markdown so the existing
streamed-report + TOC frontend keeps working; new blocks are additive.

## 6. Data model additions (spec §7)

New SQLite tables (repository-accessed, created by the startup migration runner):

```sql
CREATE TABLE claims (
  run_id TEXT NOT NULL, id TEXT NOT NULL, section_id TEXT,
  text TEXT NOT NULL, entity TEXT, attribute TEXT, quote TEXT,
  stance TEXT, created_at TEXT NOT NULL, PRIMARY KEY (run_id, id)
);
CREATE TABLE claim_sources (            -- many-to-many claim ↔ source(ref_num)
  run_id TEXT NOT NULL, claim_id TEXT NOT NULL, ref_num INTEGER NOT NULL,
  PRIMARY KEY (run_id, claim_id, ref_num)
);
CREATE TABLE verifications (
  run_id TEXT NOT NULL, claim_id TEXT NOT NULL,
  verdict TEXT NOT NULL, confidence REAL, rationale TEXT,
  verifier_model TEXT, created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, claim_id)
);
CREATE TABLE contradictions (
  run_id TEXT NOT NULL, id TEXT NOT NULL, entity TEXT, attribute TEXT,
  claim_id_a TEXT NOT NULL, claim_id_b TEXT NOT NULL, note TEXT,
  PRIMARY KEY (run_id, id)
);
```

`sources` is unchanged (still the global numbered registry). Templates, if DB-backed, live in
`settings`; if file-backed, under `backend/app/prompts/templates/`.

## 7. Event contract additions (spec §8, `docs/API_CONTRACT.md`)

New event types on the existing SSE stream (additive; frontend de-dupes by `seq`):

```ts
type EventType = /* …existing… */
  | "claim"          // { claim_id, section_id, text, entity?, attribute?, source_ids: number[], quote? }
  | "verification"   // { claim_id, verdict: "supported"|"partial"|"unsupported"|"contradicted", confidence: number, rationale?: string }
  | "contradiction"  // { id, entity?, attribute?, claim_ids: [string, string], note?: string }
```

`report` / `done` gain an optional `confidence_summary`. Event ordering within a section becomes:
`section_start → search* → source* → claim* → verification* → (contradiction*) → note* → section_done`.

The `Template` type in the contract is extended (backward-compatible — list view still needs only
`id/name/description/audience`; the full schema is fetched per template or applied server-side):

```ts
type Template = {
  id: string; name: string; description: string; audience: string;
  entity_mode?: boolean;
  entity_schema?: { key: string; label: string; type: "text" | "list" }[];
  verification_level?: "off" | "light" | "strict";
}
```

## 8. Milestone plan changes (spec §11)

The change touches the **engine (M1 code)** and **report shape**, which the frontend must render.
Sequencing:

- **Do not derail M3 (security).** It is nearly a differentiator; finish it as planned.
- **Insert M3.5 — "Engine v2: claims + verify + templates"** *before* the research-UX frontend.
  Building the frontend against the old event/report shape and reworking it later wastes effort.

Revised build order:

1. Scaffold + engine core + providers + mocks + CLI + tests. *(done)*
2. API + SQLite + SSE + config/templates. *(done)*
3. Security: vault, auth, RBAC, audit, first-run setup, Google OAuth. *(next, unchanged)*
4. **NEW — M3.5 Engine v2:** claim extraction, verifier role + model routing, contradiction
   detection, confidence scoring, adaptive stopping, structured templates + comparison-table
   synthesis. New tables (§6), new events (§7), `verification_level` config. Mock verifier for
   offline E2E; tests assert "report body contains only supported claims" + "unsupported → appendix".
5. Frontend: setup + auth + research UX + streaming + report — now including **confidence badges,
   contradiction flags, and the comparison table**.
6. Frontend: admin panel + settings (+ verifier model, verification_level toggles).
7. CI, full docs, README (hero rewrite per §1), THIRD_PARTY_NOTICES, screenshots, polish.

A dedicated `docs/superpowers/plans/2026-07-20-milestone-3_5-engine-v2.md` will be written (TDD task
breakdown) before execution, mirroring the M1/M2 plan format.

## 9. Risks & tradeoffs (spec §13 additions)

- **Cost/latency of verification** — mitigated by batching, candidate-only verification, cheap
  verifier model, and `verification_level` (§2.6). Default `light`.
- **Claim extraction is lossy** — degrades to lower coverage, never to confident-but-wrong. Tests
  assert the body never contains unverified claims.
- **Template maintenance** — templates are data; a bad template yields a bad plan. Ship four
  curated ones; treat community templates as reviewed contributions.
- **Scope creep** — this addendum is bounded to §2–§5; the rejected ideas in §0 stay out of v1.

## 10. Explicitly rejected for v1 (guard against bloat)

Multi-agent orchestration framework · knowledge graph · evidence graph · hypothesis-generation
engine · rejected-hypothesis store · autonomous browser-agent research. Each sounds impressive and
none earns its complexity before §2–§5 exist. Revisit only with evidence of need.
