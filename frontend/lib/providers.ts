/**
 * Provider display metadata for the Settings + Admin UIs.
 *
 * The backend accepts any LiteLLM model id, so the model lists here are curated
 * *suggestions* — the Model field always allows a custom value. `available`
 * (from GET /api/config) still governs which providers can actually be selected;
 * these lists just make the full catalog visible with friendly names.
 */

export const LLM_PROVIDERS = [
  "mock",
  "anthropic",
  "openai",
  "gemini",
  "zai",
  "moonshot",
] as const;

export const SEARCH_PROVIDERS = [
  "mock",
  "duckduckgo",
  "tavily",
  "serper",
  "exa",
] as const;

const PROVIDER_LABELS: Record<string, string> = {
  mock: "Mock (offline)",
  anthropic: "Anthropic (Claude)",
  openai: "OpenAI",
  gemini: "Google Gemini",
  zai: "z.ai (GLM)",
  moonshot: "Moonshot (Kimi)",
  tavily: "Tavily",
  serper: "Serper",
  exa: "Exa",
  duckduckgo: "DuckDuckGo",
  jina: "Jina",
};

/** Friendly display name for a provider id (falls back to the id itself). */
export function providerLabel(id: string): string {
  return PROVIDER_LABELS[id] ?? id;
}

/** Curated model suggestions per LLM provider. Custom ids are still allowed. */
export const PROVIDER_MODELS: Record<string, string[]> = {
  mock: ["mock-1"],
  anthropic: ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5-20251001"],
  openai: ["gpt-4o", "gpt-4o-mini", "o3-mini"],
  gemini: ["gemini-2.5-pro", "gemini-2.5-flash"],
  zai: ["glm-4.6", "glm-4.5-air"],
  moonshot: ["kimi-k2-0905", "moonshot-v1-128k"],
};

/** The suggested default model when switching to a provider. */
export function defaultModelFor(provider: string): string | undefined {
  return PROVIDER_MODELS[provider]?.[0];
}
