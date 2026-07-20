<h1 align="center">🔎 AI DeepResearch AutoFlow</h1>

<p align="center">
  <b>Auto-research → deep research → detailed cited reports.</b><br/>
  A secure, multi-user web platform that turns a research goal into a thorough,
  source-cited report — built for marketing teams researching competitors and markets.
</p>

<p align="center">
  <i>🚧 Under active construction — see the <a href="./docs/superpowers/specs/2026-07-20-ai-deepresearch-autoflow-design.md">design spec</a>.</i>
</p>

---

## What it does

Type a goal like *"Analyze competitor brand X"*, optionally review the AI-generated research
plan, then watch the system search the web, read sources, and synthesize a detailed
**Markdown report with citations** — live, in Thai or English.

## Highlights

- 🧠 **Custom async deep-research engine** — plan → parallel multi-step research loop →
  compress → synthesize, with a live event stream (SSE).
- 🔌 **Swappable providers** — LLM (Claude / OpenAI / Gemini via LiteLLM) and search
  (Tavily / Serper / Exa / DuckDuckGo). Mock providers run the whole pipeline offline.
- 🔐 **Secure key vault** — API keys encrypted at rest (AES-256-GCM), write-only, with
  revoke / expire / rotate and a full audit log.
- 👥 **Auth + RBAC** — email/password + Google OAuth; `admin` / `member` / `viewer` roles;
  an admin panel to manage users and provider credentials.
- 🌏 **i18n reports** — choose Thai or English output per job.
- ✅ **Quality gates** — lint, type-check, tests, and secret-scanning in CI.

## Tech stack

**Backend:** Python · FastAPI · SQLite · LiteLLM · async · `uv`
**Frontend:** Next.js 15 · TypeScript · Tailwind · shadcn/ui · `pnpm`

## Status / roadmap

Built in milestone PRs (see the design spec): engine core → API + DB → security/auth →
frontend → admin panel → CI & docs.

## Acknowledgements

Inspired by [open_deep_research](https://github.com/langchain-ai/open_deep_research),
[deer-flow](https://github.com/bytedance/deer-flow),
[DeepResearch](https://github.com/Alibaba-NLP/DeepResearch), and
[autoresearch](https://github.com/karpathy/autoresearch).
See [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) for credits and licenses.

## License

[MIT](./LICENSE) © 2026 Narenrit Hadsadintorn
