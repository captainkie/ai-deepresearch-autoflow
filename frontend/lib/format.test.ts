import { describe, it, expect } from "vitest";

import { slugify } from "./format";

describe("slugify", () => {
  it("slugifies ASCII headings", () => {
    expect(slugify("Executive Summary")).toBe("executive-summary");
    expect(slugify("  Key   Findings  ")).toBe("key-findings");
  });

  it("keeps Thai (non-Latin) letters instead of collapsing to empty", () => {
    // Regression: the old `\w`-based slugify stripped all Thai chars, producing an
    // empty id → duplicate React keys and a `querySelector('#')` crash.
    const slug = slugify("บทสรุปผู้บริหาร");
    expect(slug.length).toBeGreaterThan(0);
    expect(slug).toContain("บทสรุป");
  });

  it("gives distinct Thai headings distinct slugs", () => {
    expect(slugify("บทสรุปผู้บริหาร")).not.toBe(slugify("ผลการค้นพบสำคัญ"));
  });

  it("is deterministic for the same input", () => {
    expect(slugify("บทสรุป")).toBe(slugify("บทสรุป"));
  });

  it("never returns an empty string, even for punctuation/emoji-only headings", () => {
    expect(slugify("!!!").length).toBeGreaterThan(0);
    expect(slugify("★ ☆ ★").length).toBeGreaterThan(0);
    expect(slugify("")).toMatch(/^h-/);
  });

  it("produces a valid, non-'#' anchor id for any input", () => {
    for (const h of ["Overview", "ภาพรวม", "###", "😀"]) {
      const id = slugify(h);
      expect(id).not.toBe("");
      // `#${id}` must be a usable selector fragment (never a bare '#').
      expect(`#${id}`).not.toBe("#");
    }
  });
});
