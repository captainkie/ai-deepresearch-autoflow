<h1 align="center">🔎 AI DeepResearch AutoFlow</h1>

<p align="center">
  <b>Deep research your team can trust — self-hosted, secure, every claim cited &amp; verified.</b><br/>
  A multi-user web platform that turns a research goal into a thorough, source-cited report with
  claim-level verification, confidence, and surfaced contradictions —
  built for marketing teams researching competitors and markets.
</p>

<p align="center">
  <i>🚧 Under active construction — see the <a href="./docs/superpowers/specs/2026-07-20-ai-deepresearch-autoflow-design.md">design spec</a>.</i>
</p>

<p align="center">
  <a href="https://github.com/captainkie/ai-deepresearch-autoflow/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/captainkie/ai-deepresearch-autoflow/actions/workflows/ci.yml/badge.svg"></a>
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%20%7C%203.12-blue">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-16-black">
  <a href="https://github.com/sponsors/captainkie"><img alt="Sponsor" src="https://img.shields.io/badge/Sponsor-%E2%9D%A4-ff69b4"></a>
  <a href="https://buymeacoffee.com/captainkiez"><img alt="Buy Me a Coffee" src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?logo=buymeacoffee&logoColor=black"></a>
</p>

---

## What it does

Type a goal like *"Analyze competitor brand X"*, optionally review the AI-generated research
plan, then watch the system search the web, read sources, and synthesize a detailed
**Markdown report with citations** — live, in Thai or English.

## Highlights

- 🔐 **Secure by default** — API keys live in an encrypted vault (AES-256-GCM), write-only, with
  revoke / expire / rotate and a full audit log. Hand the app to non-technical teammates; the admin
  holds the keys.
- ✅ **Verified, not just generated** *(Engine v2, in progress)* — every claim is grounded in a cited
  source and checked by a separate verifier, with a **confidence** badge and **surfaced
  contradictions**. The report body renders only verified claims; the rest goes to an "Unverified" appendix.
- 🧠 **Custom async deep-research engine** — plan → parallel multi-step research loop →
  extract & verify claims → synthesize, with a live event stream (SSE) and adaptive stopping.
- 🔌 **Swappable providers** — LLM (Claude / OpenAI / Gemini via LiteLLM, + z.ai GLM / Moonshot Kimi)
  and search (Tavily / Serper / Exa / DuckDuckGo). Run the verifier on a cheap/fast model. Mock
  providers run the whole pipeline offline.
- 👥 **Auth + RBAC** — email/password + Google OAuth; `admin` / `member` / `viewer` roles;
  an admin panel to manage users and provider credentials.
- 📊 **Marketing-grade reports** *(Engine v2, in progress)* — structured templates (Competitor
  Teardown, Market Landscape, SWOT, Pricing) with cited, confidence-scored comparison tables.
- 🌏 **i18n reports** — choose Thai or English output per job.
- ✅ **Quality gates** — lint, type-check, tests, and secret-scanning in CI.

## Tech stack

**Backend:** Python · FastAPI · SQLite · LiteLLM · async · `uv`
**Frontend:** Next.js 15 · TypeScript · Tailwind · shadcn/ui · `pnpm`

## Status / roadmap

Built in milestone PRs (see the design spec + the
[Engine v2 addendum](./docs/superpowers/specs/2026-07-20-engine-v2-trust-templates.md)):
engine core ✅ → API + DB ✅ → security/auth → **Engine v2 (verification + templates)** →
frontend → admin panel → CI & docs.

## Authors

Built by **Narenrit Hadsadintorn** ([@captainkie](https://github.com/captainkie)) together
with **Claude** (Anthropic) as an AI pair-builder. Both are credited in-app on the
**About / Credits** page and in the site footer.

## Acknowledgements

Inspired by [open_deep_research](https://github.com/langchain-ai/open_deep_research),
[deer-flow](https://github.com/bytedance/deer-flow),
[DeepResearch](https://github.com/Alibaba-NLP/DeepResearch), and
[autoresearch](https://github.com/karpathy/autoresearch).
See [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) for credits and licenses.

## Support

If this project is useful to you, consider supporting its development 💛

- ⭐ Star the repo
- 💖 [GitHub Sponsors](https://github.com/sponsors/captainkie)
- ☕ [Buy Me a Coffee](https://buymeacoffee.com/captainkiez)

## License

[MIT](./LICENSE) © 2026 Narenrit Hadsadintorn
