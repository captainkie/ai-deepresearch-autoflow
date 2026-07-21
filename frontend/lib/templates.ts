import type { Template } from "./types";

/**
 * Fallback research templates.
 *
 * Used when `GET /api/v1/templates` is unavailable (e.g. backend offline) so the
 * home screen always has something meaningful to show. Ids are chosen to match
 * the backend's expected template slugs; `deep_research` is the contract default.
 */
export const FALLBACK_TEMPLATES: Template[] = [
  {
    id: "competitor_brand",
    name: "Competitor Brand Analysis",
    description:
      "A structured teardown of a rival brand — positioning, messaging, audience, channels, pricing signals, and where they're vulnerable.",
    audience: "Marketing & brand strategy",
  },
  {
    id: "market_landscape",
    name: "Market Landscape",
    description:
      "Map a category end to end: the major players, emerging challengers, trends shaping demand, and the whitespace worth chasing.",
    audience: "Growth & market research",
  },
  {
    id: "deep_research",
    name: "Deep Research (general)",
    description:
      "An open-ended, multi-source investigation into any question — planned, researched, and written up with citations.",
    audience: "Anyone",
  },
];

export const DEFAULT_TEMPLATE_ID = "deep_research";

/** Friendly display names for the built-in template ids (match the backend). */
const TEMPLATE_LABELS: Record<string, string> = {
  deep_research: "Deep Research",
  competitor_brand: "Competitor Teardown",
  market_landscape: "Market Landscape",
  swot: "SWOT Analysis",
  pricing_analysis: "Pricing Analysis",
};

/**
 * A human label for a template id — the friendly name for known templates,
 * otherwise the slug prettified (`market_landscape` → `Market Landscape`). Used
 * in the run header and history cards so the label matches the home composer.
 */
export function templateLabel(id?: string): string {
  if (!id) return "";
  return (
    TEMPLATE_LABELS[id] ??
    id
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}
