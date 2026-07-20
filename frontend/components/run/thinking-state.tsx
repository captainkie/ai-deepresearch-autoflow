import type { RunStatus } from "@/lib/types";

const HEADLINES: Record<string, string> = {
  queued: "Warming up…",
  planning: "Planning the investigation",
  researching: "Searching the open web",
  writing: "Writing your report",
};

export function ThinkingState({
  status,
  message,
}: {
  status: RunStatus;
  message?: string;
}) {
  const headline = HEADLINES[status] ?? "Working…";

  return (
    <div className="rounded-2xl border border-border/70 bg-card/50 p-6 sm:p-8">
      <div className="flex items-center gap-3">
        <span className="relative flex size-2.5">
          <span className="absolute inline-flex size-full rounded-full bg-signal opacity-60 pulse-dot" />
          <span className="relative inline-flex size-2.5 rounded-full bg-signal" />
        </span>
        <div>
          <h2 className="font-display text-lg font-semibold tracking-tight">
            {headline}
          </h2>
          {message && (
            <p className="text-sm text-muted-foreground">{message}</p>
          )}
        </div>
      </div>

      {/* Forming-document shimmer */}
      <div className="mt-6 flex flex-col gap-3">
        <div className="shimmer-line h-6 w-1/2 rounded-lg" />
        <div className="mt-1 flex flex-col gap-2">
          {["w-full", "w-11/12", "w-full", "w-4/5"].map((w, i) => (
            <div key={i} className={`shimmer-line h-3 rounded-full ${w}`} />
          ))}
        </div>
        <div className="mt-3 shimmer-line h-5 w-2/5 rounded-lg" />
        <div className="mt-1 flex flex-col gap-2">
          {["w-full", "w-10/12", "w-3/4"].map((w, i) => (
            <div key={i} className={`shimmer-line h-3 rounded-full ${w}`} />
          ))}
        </div>
      </div>

      <p className="mt-6 text-xs text-muted-foreground">
        This can take a few minutes. You can keep this tab open — updates stream
        in live on the left.
      </p>
    </div>
  );
}
