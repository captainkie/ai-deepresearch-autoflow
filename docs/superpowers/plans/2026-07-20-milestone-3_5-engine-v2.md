# Milestone 3.5 — Engine v2: Claims, Verification & Structured Templates (TDD Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:test-driven-development. Steps use
> checkbox (`- [ ]`). Design source of truth: `docs/superpowers/specs/2026-07-20-engine-v2-trust-templates.md`.

**Goal:** turn the engine from *search → summarize → synthesize* into a **verifiable, claim-grounded**
system, and turn `template` from a string into a **structured marketing product**. The report becomes a
**projection of verified claims** — unsupported material moves to an "Unverified" appendix. Keeps `core/`
pure (providers via interfaces, events via sink); M2/M3 stay green (env/vault key path unchanged).

## Slices (each branch → PR → merge; CI green)

- **M3.5a — Claim + verification core (backend engine).** Claim as the atomic unit: extract → verify →
  contradiction-detect → adaptive stop. New tables/events. Mock verifier for offline E2E.
- **M3.5b — Structured templates + comparison-table synthesis.** `entity_schema` templates; synthesizer
  renders exec-summary + cited/confidence comparison table + contradictions + unverified appendix.
- **M3.5c — Frontend.** Render claim/verification/contradiction events (confidence badges, contradiction
  flags, comparison table) in the run + report views; `verification_level` toggle in Settings.

---

## New dependencies
None (reuses LiteLLM + the existing mock providers; verifier is just another LLM role/model).

## Data model additions (`backend/app/db/schema.sql`) — additive, new tables
```sql
CREATE TABLE IF NOT EXISTS claims (
  run_id TEXT NOT NULL, id TEXT NOT NULL, section_id TEXT,
  text TEXT NOT NULL, entity TEXT, attribute TEXT, quote TEXT, stance TEXT,
  created_at TEXT NOT NULL, PRIMARY KEY (run_id, id)
);
CREATE TABLE IF NOT EXISTS claim_sources (           -- m2m claim ↔ sources.ref_num
  run_id TEXT NOT NULL, claim_id TEXT NOT NULL, ref_num INTEGER NOT NULL,
  PRIMARY KEY (run_id, claim_id, ref_num)
);
CREATE TABLE IF NOT EXISTS verifications (
  run_id TEXT NOT NULL, claim_id TEXT NOT NULL,
  verdict TEXT NOT NULL, confidence REAL, rationale TEXT, verifier_model TEXT,
  created_at TEXT NOT NULL, PRIMARY KEY (run_id, claim_id)
);
CREATE TABLE IF NOT EXISTS contradictions (
  run_id TEXT NOT NULL, id TEXT NOT NULL, entity TEXT, attribute TEXT,
  claim_id_a TEXT NOT NULL, claim_id_b TEXT NOT NULL, note TEXT,
  PRIMARY KEY (run_id, id)
);
```

## Event contract additions (`docs/API_CONTRACT.md` — already documented in Engine v2)
`claim`, `verification`, `contradiction` (+ optional `confidence_summary` on `report`/`done`).
Section ordering: `section_start → search* → source* → claim* → verification* → (contradiction*) → note* → section_done`.

---

## M3.5a — Claim + verification core

**Files:** `models/schemas.py` (Claim, Verification, Verdict, Contradiction, ConfidenceSummary,
`EventType` +claim/verification/contradiction); `core/claims.py` (extraction), `core/verifier.py`
(verify + confidence), `core/contradictions.py` (cluster + detect); `core/researcher.py` (wire claim
loop + adaptive stop); `providers/llm/mock.py` (deterministic claims/verdicts); `db/schema.sql` +
`db/repositories.py` (ClaimRepo, VerificationRepo, ContradictionRepo); `services/run_service.py`
(persist new events + verifier provider); `settings`/`config` (`verifier_provider`, `verifier_model`,
`verification_level`).

### Task 1 — Schemas + event types (TESTS FIRST)
- [ ] Failing `tests/test_schemas.py`: `Claim`, `Verification(verdict∈{supported,partial,unsupported,
  contradicted})`, `Contradiction`, `ConfidenceSummary` validate; `EventType` has the 3 new values.
- [ ] Implement in `models/schemas.py`. PASS. Commit `feat(models): claim/verification schemas`.

### Task 2 — Claim extraction (`core/claims.py`)
- [ ] Failing `tests/test_claims.py`: given a `PageContent` + section goal + a (mock) LLM,
  `extract_claims(...)` returns atomic `Claim`s each with ≥1 `source_ids` and a `quote` copied from the
  page; entity/attribute tagged when the template is entity-mode; tolerant JSON parse (+1 repair).
- [ ] Implement + extend `providers/llm/mock.py` to emit deterministic claims. PASS.

### Task 3 — Verifier + confidence (`core/verifier.py`)
- [ ] Failing `tests/test_verifier.py`: `verify(claim, source_text, llm) -> Verification`; adversarial
  prompt; a claim unsupported by the quote → `unsupported`; `confidence(claim, verifications, sources)`
  is a pure function → high/medium/low; mock verifier deterministic; batch claims per source into one call.
- [ ] Implement; add `verifier_provider`/`verifier_model` config (default a cheap model; falls back to
  the main LLM; mock offline). PASS.

### Task 4 — Contradiction detection (`core/contradictions.py`)
- [ ] Failing `tests/test_contradictions.py`: two supported claims on the same `(entity, attribute)` with
  conflicting text → one `Contradiction` referencing both + both sources; agreeing claims → none.
- [ ] Implement (group by (entity, attribute); LLM/簡 heuristic adjudication). PASS.

### Task 5 — Researcher v2 loop + adaptive stopping
- [ ] Failing `tests/test_researcher.py` (extend): per section — search → crawl → **extract claims** →
  **verify** → contradiction-detect → **compress verified claims** into notes; emits `claim`,
  `verification`, `contradiction` events via the sink; **stops** when a round adds 0 new sources AND 0 new
  *supported* claims (diminishing returns) or budget hit — not just iteration count.
- [ ] Implement; keep `verification_level: off|light|strict` (default light; off ⇒ legacy path,
  no new events → back-compat). PASS.

### Task 6 — Repos + persistence + config
- [ ] Failing `tests/test_db.py` (extend): ClaimRepo/VerificationRepo/ContradictionRepo CRUD + m2m.
- [ ] `run_service` sink persists `claim`/`verification`/`contradiction` to the new tables + fans out.
  `config_service` exposes `verification_level` + verifier model. PASS. PR **M3.5a**.

### M3.5a gates
- [ ] ruff + pytest green; offline E2E (mock) asserts: **report body contains only supported claims**,
  unsupported → appendix; `verification_level:off` reproduces M2 output. Update `API_CONTRACT` if shapes drift.

---

## M3.5b — Structured templates + comparison-table synthesis

**Files:** `prompts/templates/*.yaml` (or `prompts/templates.py` structured), `core/synthesizer.py`,
`prompts/synthesizer.py`.

### Task 1 — Template schema
- [ ] Failing `tests/test_prompts.py` (extend): a `ResearchTemplate` has `sections`, `entity_mode`,
  `entity_schema[{key,label,type}]`, `report_sections`, `verification_level`. Ship **Competitor Teardown,
  Market Landscape, SWOT, Pricing Analysis, Deep Research**. `GET /api/templates` returns the extended
  `Template` shape (entity_mode?, entity_schema?, verification_level?).
- [ ] Implement. PASS.

### Task 2 — Comparison-table synthesis (the payoff)
- [ ] Failing `tests/test_synthesizer.py`: for an `entity_mode` template, verified claims tagged
  `(entity, attribute)` **auto-fill a Markdown comparison table** (rows=entities, cols=entity_schema),
  each cell carrying its citation `[n]` + a confidence marker; report order = exec-summary → table →
  per-entity detail → contradictions → **unverified appendix** → next-actions → sources. Non-entity
  templates skip the table.
- [ ] Implement; synthesizer asserts only verified claims in the body. PASS. PR **M3.5b**.

---

## M3.5c — Frontend (render trust)

**Files:** `frontend/lib/types.ts` (+event/claim types), `lib/useResearchStream.ts` (reduce new events),
`components/run/*` (confidence badge, contradiction flag, comparison table), `components/settings/*`
(`verification_level`).

### Tasks
- [ ] Types + reducer for `claim`/`verification`/`contradiction` + `confidence_summary`.
- [ ] Run timeline shows per-section claims with confidence badges + contradiction flags; report view
  renders the comparison table (Markdown already handled) and an "Unverified / needs checking" section.
- [ ] Settings: `verification_level` (off/light/strict) toggle → `POST /api/config` (admin).
- [ ] Verify E2E in browser (mock, competitor template → cited comparison table + confidence). Gates:
  `next build` + `eslint`. PR **M3.5c**.

---

## Cross-cutting doctrine
- **Report = projection of verified claims** (the core rule). Body never contains unverified claims;
  tests assert this.
- **Cheap verifier model** (Haiku/GLM/Kimi) is the payoff of the provider abstraction — separate config.
- **Back-compat:** `verification_level:off` ⇒ legacy pipeline, no new events; M1/M2/M3 tests hold.
- **Rejected for v1 (bloat guard):** knowledge graph, evidence graph, hypothesis engine, multi-agent
  framework (see addendum §10).

## Self-Review
- Spec coverage: addendum §2–§7 (claims/verify/contradiction/confidence/adaptive/templates/comparison-table,
  data model, events). Seam preserved (providers/sink). Slices independently shippable + CI-gated.
