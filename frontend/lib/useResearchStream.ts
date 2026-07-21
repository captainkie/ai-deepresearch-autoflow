"use client";

/**
 * useResearchStream — opens the live SSE stream for a run and exposes reactive,
 * fully-typed research state (plan, sections with searches/sources/notes, the
 * accumulating report, status and errors).
 *
 * The stream endpoint is GET `/api/runs/{id}/stream`, but we consume it with
 * `fetch` + a `ReadableStream` reader (not `EventSource`) so we get full control
 * over headers, aborting, and reconnection. On reconnect the server replays
 * buffered events (each carries a monotonic `seq`), so we de-duplicate by `seq`
 * to avoid double-applying — notably for `report_delta` accumulation.
 *
 * Flow: hydrate run metadata via `getRun` FIRST, then open the stream. If the
 * run is already finished and fully hydrated, we skip the stream entirely so a
 * completed report renders instantly without replay duplication.
 */
import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { getRun, streamUrl, submitPlan, cancelRun } from "./api";
import { splitSseFrames, parseSseData } from "./sse";
import {
  getAccessToken,
  notifyUnauthenticated,
  refreshAccessToken,
} from "./auth";
import type {
  ClaimData,
  ConfidenceSummary,
  ContradictionData,
  DoneData,
  ErrorData,
  NoteData,
  PlanData,
  PlanSection,
  ReportData,
  ReportDeltaData,
  ResearchEvent,
  RunStatus,
  SearchData,
  SectionDoneData,
  SectionStartData,
  Source,
  SourceData,
  StatusData,
  Verdict,
  VerificationData,
} from "./types";

/** A claim plus the verifier's verdict once it arrives. */
export type ClaimState = ClaimData & {
  verdict?: Verdict;
  confidence?: number;
};

export type SectionState = {
  id: string;
  title: string;
  goal?: string;
  queries: string[];
  searches: string[];
  sources: Source[];
  notes: string[];
  summary?: string;
  sourceCount?: number;
  status: "pending" | "active" | "done";
};

export type StreamState = {
  query?: string;
  template?: string;
  createdAt?: string;
  status: RunStatus;
  statusMessage: string;
  brief?: string;
  planSections: PlanSection[];
  awaitingPlan: boolean;
  sections: SectionState[];
  report: string;
  reportFinal: boolean;
  title?: string;
  sourceCount?: number;
  error?: string;
  // Engine v2 trust data.
  claims: ClaimState[];
  contradictions: ContradictionData[];
  confidenceSummary?: ConfidenceSummary;
};

const INITIAL: StreamState = {
  status: "queued",
  statusMessage: "",
  planSections: [],
  awaitingPlan: false,
  sections: [],
  report: "",
  reportFinal: false,
  claims: [],
  contradictions: [],
};

type Action =
  | { type: "hydrate"; payload: Partial<StreamState> }
  | { type: "event"; event: ResearchEvent }
  | { type: "report_append"; text: string }
  | { type: "approved" }
  | { type: "cancelled" }
  | { type: "reset" };

function emptySection(id: string, title = ""): SectionState {
  return {
    id,
    title,
    queries: [],
    searches: [],
    sources: [],
    notes: [],
    status: "pending",
  };
}

function upsertSection(
  sections: SectionState[],
  id: string,
  update: (s: SectionState) => SectionState,
): SectionState[] {
  const idx = sections.findIndex((s) => s.id === id);
  if (idx === -1) return [...sections, update(emptySection(id))];
  const next = sections.slice();
  next[idx] = update(next[idx]);
  return next;
}

function reduceEvent(state: StreamState, event: ResearchEvent): StreamState {
  switch (event.type) {
    case "status": {
      const d = event.data as StatusData;
      return {
        ...state,
        status: d.stage ?? state.status,
        statusMessage: d.message ?? state.statusMessage,
        // Leaving awaiting_plan (e.g. -> researching) clears the pause flag.
        awaitingPlan: d.stage === "awaiting_plan",
      };
    }
    case "plan": {
      const d = event.data as PlanData;
      const planSections = d.sections ?? [];
      // Seed section shells from the plan, preserving any already-streamed data.
      let sections = state.sections;
      for (const ps of planSections) {
        sections = upsertSection(sections, ps.id, (s) => ({
          ...s,
          title: s.title || ps.title,
          goal: s.goal ?? ps.goal,
          queries: s.queries.length ? s.queries : (ps.queries ?? []),
        }));
      }
      return { ...state, brief: d.brief, planSections, sections };
    }
    case "awaiting_plan":
      return { ...state, awaitingPlan: true, status: "awaiting_plan" };
    case "section_start": {
      const d = event.data as SectionStartData;
      return {
        ...state,
        sections: upsertSection(state.sections, d.section_id, (s) => ({
          ...s,
          title: d.title || s.title,
          status: "active",
        })),
      };
    }
    case "search": {
      const d = event.data as SearchData;
      return {
        ...state,
        sections: upsertSection(state.sections, d.section_id, (s) => ({
          ...s,
          status: s.status === "done" ? s.status : "active",
          searches: [...s.searches, d.query],
        })),
      };
    }
    case "source": {
      const d = event.data as SourceData;
      return {
        ...state,
        sections: upsertSection(state.sections, d.section_id, (s) => ({
          ...s,
          sources: s.sources.some((x) => x.id === d.source.id)
            ? s.sources
            : [...s.sources, d.source],
        })),
      };
    }
    case "claim": {
      const d = event.data as ClaimData;
      if (state.claims.some((c) => c.claim_id === d.claim_id)) return state;
      return { ...state, claims: [...state.claims, { ...d }] };
    }
    case "verification": {
      const d = event.data as VerificationData;
      return {
        ...state,
        claims: state.claims.map((c) =>
          c.claim_id === d.claim_id
            ? { ...c, verdict: d.verdict, confidence: d.confidence }
            : c,
        ),
      };
    }
    case "contradiction": {
      const d = event.data as ContradictionData;
      if (state.contradictions.some((c) => c.id === d.id)) return state;
      return { ...state, contradictions: [...state.contradictions, d] };
    }
    case "note": {
      const d = event.data as NoteData;
      return {
        ...state,
        sections: upsertSection(state.sections, d.section_id, (s) => ({
          ...s,
          notes: [...s.notes, d.content],
        })),
      };
    }
    case "section_done": {
      const d = event.data as SectionDoneData;
      return {
        ...state,
        sections: upsertSection(state.sections, d.section_id, (s) => ({
          ...s,
          summary: d.summary,
          sourceCount: d.source_count,
          status: "done",
        })),
      };
    }
    case "report_delta": {
      const d = event.data as ReportDeltaData;
      return { ...state, report: state.report + (d.text ?? "") };
    }
    case "report": {
      const d = event.data as ReportData;
      return {
        ...state,
        report: d.markdown ?? state.report,
        reportFinal: true,
        title: d.title ?? state.title,
        confidenceSummary: d.confidence_summary ?? state.confidenceSummary,
      };
    }
    case "error": {
      const d = event.data as ErrorData;
      return {
        ...state,
        error: d.message ?? "Something went wrong",
        status: "error",
      };
    }
    case "done": {
      const d = event.data as DoneData;
      return {
        ...state,
        status: "done",
        awaitingPlan: false,
        reportFinal: true,
        title: d.title ?? state.title,
        sourceCount: d.source_count ?? state.sourceCount,
        confidenceSummary: d.confidence_summary ?? state.confidenceSummary,
      };
    }
    default:
      return state;
  }
}

function reducer(state: StreamState, action: Action): StreamState {
  switch (action.type) {
    case "hydrate":
      return { ...state, ...action.payload };
    case "event":
      return reduceEvent(state, action.event);
    case "report_append":
      return { ...state, report: state.report + action.text };
    case "approved":
      return { ...state, awaitingPlan: false };
    case "cancelled":
      return { ...state, status: "cancelled", awaitingPlan: false };
    case "reset":
      return INITIAL;
    default:
      return state;
  }
}

export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error";

export type UseResearchStream = StreamState & {
  connection: ConnectionStatus;
  connectionError?: string;
  loadingDetail: boolean;
  approving: boolean;
  /** All sources across sections, ordered by citation id. */
  allSources: Source[];
  approvePlan: (sections?: PlanSection[]) => Promise<void>;
  cancel: () => Promise<void>;
  retry: () => void;
};

const TERMINAL: RunStatus[] = ["done", "error"];

export function useResearchStream(
  runId: string | undefined,
  options: { enabled?: boolean } = {},
): UseResearchStream {
  const enabled = options.enabled ?? true;
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const [connection, setConnection] = useState<ConnectionStatus>("idle");
  const [connectionError, setConnectionError] = useState<string | undefined>();
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [approving, setApproving] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const seenSeqs = useRef<Set<number>>(new Set());
  const reportBuffer = useRef("");
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevRunId = useRef(runId);

  // Reset state when the run changes (adjust-during-render, per React docs —
  // avoids a cascading setState-in-effect).
  if (prevRunId.current !== runId) {
    prevRunId.current = runId;
    seenSeqs.current = new Set();
    reportBuffer.current = "";
    dispatch({ type: "reset" });
    setConnection("idle");
    setConnectionError(undefined);
  }

  const flushReport = useCallback(() => {
    if (flushTimer.current) {
      clearTimeout(flushTimer.current);
      flushTimer.current = null;
    }
    if (reportBuffer.current) {
      const text = reportBuffer.current;
      reportBuffer.current = "";
      dispatch({ type: "report_append", text });
    }
  }, []);

  const scheduleFlush = useCallback(() => {
    if (flushTimer.current) return;
    flushTimer.current = setTimeout(() => {
      flushTimer.current = null;
      const text = reportBuffer.current;
      reportBuffer.current = "";
      if (text) dispatch({ type: "report_append", text });
    }, 90);
  }, []);

  const handleEvent = useCallback(
    (event: ResearchEvent) => {
      if (typeof event.seq === "number") {
        if (seenSeqs.current.has(event.seq)) return;
        seenSeqs.current.add(event.seq);
      }
      // Batch high-frequency report tokens; apply everything else immediately.
      if (event.type === "report_delta") {
        reportBuffer.current += (event.data as ReportDeltaData)?.text ?? "";
        scheduleFlush();
        return;
      }
      if (event.type === "report" || event.type === "done") {
        flushReport();
      }
      dispatch({ type: "event", event });
    },
    [flushReport, scheduleFlush],
  );

  // Hydrate metadata, then open the stream (sequenced to avoid races).
  useEffect(() => {
    if (!runId || !enabled) return;
    const controller = new AbortController();
    let closed = false;

    const hydrate = async (): Promise<boolean> => {
      setLoadingDetail(true);
      // A freshly-created run may not be persisted yet — retry once.
      for (let i = 0; i < 2; i++) {
        try {
          const detail = await getRun(runId);
          if (closed) return false;
          const payload: Partial<StreamState> = {
            query: detail.query,
            template: detail.template,
            createdAt: detail.created_at,
            title: detail.title,
            status: detail.status ?? "queued",
            awaitingPlan: detail.status === "awaiting_plan",
          };
          if (detail.plan) {
            payload.brief = detail.plan.brief;
            payload.planSections = detail.plan.sections ?? [];
          }
          const planSecs = detail.plan?.sections ?? detail.sections ?? [];
          if (planSecs.length) {
            const byId = new Map<string, Source[]>();
            for (const src of detail.sources ?? []) {
              if (!src.section_id) continue;
              byId.set(src.section_id, [
                ...(byId.get(src.section_id) ?? []),
                src,
              ]);
            }
            payload.sections = planSecs.map((ps) => ({
              ...emptySection(ps.id, ps.title),
              goal: ps.goal,
              queries: ps.queries ?? [],
              sources: byId.get(ps.id) ?? [],
              status: detail.status === "done" ? "done" : "pending",
            }));
          }
          if (detail.report) {
            payload.report = detail.report;
            payload.reportFinal = detail.status === "done";
          }
          if (detail.confidence_summary) {
            payload.confidenceSummary = detail.confidence_summary;
          }
          dispatch({ type: "hydrate", payload });
          setLoadingDetail(false);
          // Fully-finished run with a report needs no live stream.
          return TERMINAL.includes(detail.status) && !!detail.report;
        } catch {
          if (i === 0) await delay(600, controller.signal);
        }
      }
      if (!closed) setLoadingDetail(false);
      return false;
    };

    const openStream = async () => {
      setConnection("connecting");
      setConnectionError(undefined);
      try {
        const openWithAuth = () => {
          const token = getAccessToken();
          return fetch(streamUrl(runId), {
            signal: controller.signal,
            credentials: "include",
            headers: {
              Accept: "text/event-stream",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            cache: "no-store",
          });
        };
        let res = await openWithAuth();
        if (res.status === 401) {
          // Access token expired mid-session — refresh once and reconnect.
          if (await refreshAccessToken()) {
            res = await openWithAuth();
          } else {
            notifyUnauthenticated();
            throw new Error("Your session has expired. Please sign in again.");
          }
        }
        if (!res.ok || !res.body) {
          throw new Error(`Stream unavailable (${res.status})`);
        }
        setConnection("open");
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        const processFrame = (frame: string) => {
          const payload = parseSseData(frame);
          if (!payload || payload === "[DONE]") return;
          try {
            handleEvent(JSON.parse(payload) as ResearchEvent);
          } catch {
            // ignore malformed/partial payloads
          }
        };

        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const { frames, rest } = splitSseFrames(buffer);
          buffer = rest;
          for (const frame of frames) processFrame(frame);
        }
        if (buffer.trim()) processFrame(buffer);
        flushReport();
        if (!closed) setConnection("closed");
      } catch (err) {
        if (closed || controller.signal.aborted) return;
        flushReport();
        setConnection("error");
        setConnectionError(
          err instanceof Error ? err.message : "Connection failed",
        );
      }
    };

    (async () => {
      const finished = await hydrate();
      if (closed || finished) {
        if (finished) setConnection("closed");
        return;
      }
      await openStream();
    })();

    return () => {
      closed = true;
      controller.abort();
      if (flushTimer.current) {
        clearTimeout(flushTimer.current);
        flushTimer.current = null;
      }
    };
  }, [runId, enabled, attempt, handleEvent, flushReport]);

  const approvePlan = useCallback(
    async (sections?: PlanSection[]) => {
      if (!runId) return;
      setApproving(true);
      try {
        await submitPlan(runId, sections ? { sections } : { approve: true });
        dispatch({ type: "approved" });
      } finally {
        setApproving(false);
      }
    },
    [runId],
  );

  const cancel = useCallback(async () => {
    if (!runId) return;
    await cancelRun(runId);
    // The server marks the run cancelled and closes the stream, but never emits
    // a terminal event — reflect the cancellation locally so the UI leaves its
    // "working" state immediately instead of spinning forever.
    dispatch({ type: "cancelled" });
  }, [runId]);

  const retry = useCallback(() => {
    // Keep `seenSeqs` — on reconnect the server replays already-applied events
    // (incl. report_delta), and clearing it would re-append them and duplicate
    // the report. Only drop the pending, un-flushed delta buffer.
    reportBuffer.current = "";
    setAttempt((a) => a + 1);
  }, []);

  const allSources = flattenSources(state.sections);

  return {
    ...state,
    connection,
    connectionError,
    loadingDetail,
    approving,
    allSources,
    approvePlan,
    cancel,
    retry,
  };
}

function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(t);
      resolve();
    });
  });
}

function flattenSources(sections: SectionState[]): Source[] {
  const map = new Map<number, Source>();
  for (const s of sections) {
    for (const src of s.sources) {
      if (!map.has(src.id)) map.set(src.id, src);
    }
  }
  return Array.from(map.values()).sort((a, b) => a.id - b.id);
}
