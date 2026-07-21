import { describe, it, expect } from "vitest";

import { splitSseFrames, parseSseData } from "./sse";

describe("splitSseFrames", () => {
  it("splits frames on \\n\\n", () => {
    const { frames, rest } = splitSseFrames("data: a\n\ndata: b\n\n");
    expect(frames).toEqual(["data: a", "data: b"]);
    expect(rest).toBe("");
  });

  it("splits frames on \\r\\n\\r\\n (sse-starlette's delimiter — the regression)", () => {
    // The original code only matched "\n\n" and never found these boundaries,
    // so live events never parsed until the stream closed.
    const { frames, rest } = splitSseFrames("data: a\r\n\r\ndata: b\r\n\r\n");
    expect(frames).toEqual(["data: a", "data: b"]);
    expect(rest).toBe("");
  });

  it("splits frames on \\r\\r", () => {
    const { frames } = splitSseFrames("data: a\r\rdata: b\r\r");
    expect(frames).toEqual(["data: a", "data: b"]);
  });

  it("keeps a trailing partial frame in rest", () => {
    const { frames, rest } = splitSseFrames("data: a\r\n\r\ndata: b");
    expect(frames).toEqual(["data: a"]);
    expect(rest).toBe("data: b");
  });

  it("reassembles a delimiter split across two reads", () => {
    // First chunk ends mid-delimiter ("...\r\n\r"); the tail carries over and the
    // next chunk completes the boundary.
    let buffer = "data: a\r\n\r";
    let out = splitSseFrames(buffer);
    expect(out.frames).toEqual([]);
    buffer = out.rest + "\ndata: b\r\n\r\n";
    out = splitSseFrames(buffer);
    expect(out.frames).toEqual(["data: a", "data: b"]);
    expect(out.rest).toBe("");
  });

  it("returns no frames for a buffer with no delimiter yet", () => {
    const { frames, rest } = splitSseFrames("data: incomplete");
    expect(frames).toEqual([]);
    expect(rest).toBe("data: incomplete");
  });
});

describe("parseSseData", () => {
  it("extracts a single data line and strips the leading space", () => {
    expect(parseSseData("data: {\"seq\":0}")).toBe('{"seq":0}');
  });

  it("joins multiple data lines with newlines", () => {
    expect(parseSseData("data: line1\ndata: line2")).toBe("line1\nline2");
  });

  it("ignores comment/ping frames with no data line", () => {
    expect(parseSseData(": ping")).toBeNull();
    expect(parseSseData("event: message")).toBeNull();
  });

  it("returns null for an all-whitespace payload", () => {
    expect(parseSseData("data: ")).toBeNull();
  });

  it("handles \\r\\n line endings inside a frame", () => {
    expect(parseSseData("data: a\r\ndata: b")).toBe("a\nb");
  });
});
