/**
 * Minimal Server-Sent-Events frame parsing, kept pure so it can be unit-tested
 * independently of the streaming hook.
 *
 * SSE frames are separated by a blank line, which the spec allows to be "\n\n",
 * "\r\n\r\n" (what sse-starlette emits), or "\r\r". Matching only "\n\n" silently
 * misses every "\r\n\r\n" boundary, so live events never parse until the stream
 * closes — fatal for paused/long-running runs.
 */

const FRAME_DELIM = /\r\n\r\n|\n\n|\r\r/;

/**
 * Split an accumulated SSE buffer into complete frames plus the trailing partial
 * frame (which stays buffered until more bytes complete it). Handles delimiters
 * that span read boundaries because callers re-feed `rest` with the next chunk.
 */
export function splitSseFrames(buffer: string): { frames: string[]; rest: string } {
  const frames: string[] = [];
  let rest = buffer;
  let match: RegExpExecArray | null;
  while ((match = FRAME_DELIM.exec(rest)) !== null) {
    frames.push(rest.slice(0, match.index));
    rest = rest.slice(match.index + match[0].length);
  }
  return { frames, rest };
}

/**
 * Extract the joined `data:` payload from one SSE frame, or null if the frame
 * carries no data lines (e.g. a `: ping` comment). A leading space after the
 * colon is stripped per the SSE spec.
 */
export function parseSseData(frame: string): string | null {
  const dataLines: string[] = [];
  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (!dataLines.length) return null;
  const payload = dataLines.join("\n").trim();
  return payload || null;
}
